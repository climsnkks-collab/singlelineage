"""Optional, sourced LOCAL boss windows; ordinary spawn tables stay immutable.

SQL locations/counts/parties and XML windows are reference backend policy,
not an assertion about the fixed client's official server. No socket or client
input is owned here. Spawner events run under its existing world lock.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
import os
from pathlib import Path
import random
import time
from types import MappingProxyType
import uuid

from tools.local_original_session.game_data import Rect, Source, SpawnGroupDef
from tools.local_original_session.world_interest_spawn import Group, Slot, SlotState

POLICY_PATH = Path(__file__).with_name('data') / 'm6/boss_cycles.json'


@dataclass(frozen=True)
class BossWave:
    key: str
    cycle: str
    period: int
    start: int
    end: int
    groups: tuple[SpawnGroupDef, ...]
    suppress: frozenset[tuple[int, int]]


def load_policy(data, *, serves_map=lambda map_id: True, path=POLICY_PATH):
    """Resolve only already registered fixed-client monsters, once at startup."""
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    waves = []
    for row in document['bosses']:
        if not serves_map(row['map_id']):
            continue
        # A removed data feature must not silently import its monster catalog.
        if any(member['template_id'] not in data.monsters for member in row['members']):
            continue
        cycle = document['cycles'][row['cycle']]
        period, start, end = (cycle[key] for key in ('period_s', 'start_s', 'end_s'))
        if not 0 <= start < end <= period:
            raise ValueError('BOSS_CYCLE_WINDOW_REQUIRED')
        specs = []
        for index, member in enumerate(row['members']):
            ref = '; '.join(filter(None, (row['ref'], row['group_ref'], cycle['ref'],
                                          member['monster_ref'], member['identity_ref'])))
            sources = MappingProxyType({'boss_cycle': Source('local_policy', ref,
                'L1J reference window/party/location; official Classic behavior UNKNOWN')})
            specs.append(SpawnGroupDef(f"boss_{row['spawn_id']}_{index}",
                member['template_id'], row['map_id'], Rect(*row['rect']), member['count'],
                0, 0, sources))
        waves.append(BossWave(str(row['spawn_id']), row['cycle'], period, start, end,
            tuple(specs), frozenset((row['map_id'], tid) for tid in row['suppress_templates'])))
    return tuple(waves)


def state_path_for(store_path):
    """Isolated sibling of this character-store path; never edits that store."""
    path = Path(store_path)
    return path.with_name(path.name + '.boss_cycles.json')


class BossCycles:
    """One persisted wave per sourced SQL row, with no replay of missed waves.

    A wave contains all its party slots. Dead members wait for every member
    (including unplaced members) before the next window can be selected.
    Absolute wall deadlines survive process/monotonic-clock restart. Living
    records materialize once with fresh entity UIDs and their saved HP/tile.
    """

    def __init__(self, spawner, data, waves, *, path=None, wall_clock=time.time,
                 rng=None):
        self.spawner, self.waves = spawner, tuple(waves)
        self.path = None if path is None else Path(path)
        self.wall_clock = wall_clock
        self.rng = rng if rng is not None else random.Random()
        self.by_group = {spec.group_id: wave for wave in self.waves for spec in wave.groups}
        self.handles = []
        self.closed = False
        now = self.wall_clock()
        self.document = self._load(now)
        self._prepare(data)
        self.spawn_groups = {group.spec.group_id: group for group in self.spawner.groups
                             if group.spec.group_id in self.by_group}
        events = spawner.events
        for name, callback in (
            ('group_interested', self._interest), ('hold_refill', self._hold),
            ('respawn_at', self._respawn_at), ('spawn_position', self._position),
            ('spawn_hp', self._hp), ('spawned', self._spawned),
            ('dead', self._dead), ('hp_changed', self._hp_changed)):
            self.handles.append((name, events.add('boss_cycles', name, callback)))
        if self.waves:
            self._save()

    def _load(self, now):
        if self.path is not None and self.path.exists():
            document = json.loads(self.path.read_text(encoding='utf-8'))
            if (document.get('version') != 1 or not isinstance(document.get('waves'), dict)
                    or not isinstance(document.get('anchor_epoch'), (int, float))
                    or not math.isfinite(document['anchor_epoch'])):
                raise ValueError('BOSS_CYCLE_STATE_INVALID')
            return document
        local = time.localtime(now)
        anchor = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0,
                              local.tm_wday, local.tm_yday, -1))
        return {'version': 1, 'anchor_epoch': anchor, 'waves': {}}

    def _schedule(self, wave, now, *, after=None):
        anchor = self.document['anchor_epoch']
        current = math.floor((now - anchor) / wave.period)
        index = current if after is None else max(current + 1, after + 1)
        # XML End is exclusive for L1J's nextInt(window seconds). If chosen
        # time is already past, one wave becomes due immediately; no catch-up.
        deadline = anchor + index * wave.period + self.rng.randrange(wave.start, wave.end)
        return {'cycle_index': index, 'due_epoch': deadline,
            'members': {spec.group_id: [{'phase': 'pending'} for _ in range(spec.target_count)]
                        for spec in wave.groups}}

    def _prepare(self, data):
        # Startup before any PC binds. A live world cannot exchange spawn ownership.
        suppressed = set().union(*(wave.suppress for wave in self.waves)) if self.waves else set()
        replacing = [group for group in self.spawner.groups
                     if (group.spec.map_id, group.spec.template_id) in suppressed]
        if any(slot.uid is not None for group in replacing for slot in group.slots):
            raise ValueError('BOSS_CYCLE_STARTUP_ONLY')
        existing = self.document['waves']
        for wave in self.waves:
            row = existing.get(wave.key)
            if row is None:
                existing[wave.key] = self._schedule(wave, self.wall_clock())
            else:
                self._validate(wave, row)
        self.spawner.groups[:] = [group for group in self.spawner.groups if group not in replacing]
        self.spawner.groups.extend(Group(spec, data.monsters[spec.template_id],
            [Slot(index) for index in range(spec.target_count)], active=True)
            for wave in self.waves for spec in wave.groups)

    @staticmethod
    def _validate(wave, row):
        if (type(row.get('cycle_index')) is not int
                or not isinstance(row.get('due_epoch'), (int, float))
                or not math.isfinite(row['due_epoch'])
                or set(row.get('members', {})) != {spec.group_id for spec in wave.groups}):
            raise ValueError('BOSS_CYCLE_STATE_WAVE_INVALID')
        for spec in wave.groups:
            members = row['members'][spec.group_id]
            if len(members) != spec.target_count:
                raise ValueError('BOSS_CYCLE_STATE_SLOT_COUNT')
            for member in members:
                if member.get('phase') not in ('pending', 'alive', 'dead'):
                    raise ValueError('BOSS_CYCLE_STATE_PHASE')
                if member['phase'] == 'alive':
                    pos = member.get('position')
                    if (type(member.get('hp')) is not int or member['hp'] <= 0
                            or not isinstance(pos, list) or len(pos) != 3
                            or any(type(value) is not int for value in pos)
                            or not 0 <= pos[2] < 8):
                        raise ValueError('BOSS_CYCLE_STATE_ALIVE_INVALID')

    def _record(self, group, slot):
        wave = self.by_group.get(group.spec.group_id)
        if wave is None:
            return None, None, None
        row = self.document['waves'][wave.key]
        return wave, row, row['members'][group.spec.group_id][slot.index]

    def _interest(self, interested, group, now):
        # Boss time/life advances without a nearby PC; ordinary groups retain
        # the existing interest/dormancy policy and their original counts.
        return interested or group.spec.group_id in self.by_group

    def _hold(self, group, slot, now):
        wave, row, member = self._record(group, slot)
        if wave is None:
            return False
        if member['phase'] == 'alive':
            return False  # restore a single saved living slot after restart
        leader = wave.groups[0].group_id
        if group.spec.group_id != leader and 'position' not in row['members'][leader][0]:
            return True  # first materialize the sourced party leader
        return member['phase'] == 'dead' or self.wall_clock() < row['due_epoch']

    def _respawn_at(self, deadline, group, slot, now):
        return slot.corpse_at if group.spec.group_id in self.by_group else deadline

    def _position(self, group, slot, now):
        wave, row, member = self._record(group, slot)
        if member and member['phase'] == 'alive':
            return tuple(member['position'])
        if wave is not None and group.spec.group_id != wave.groups[0].group_id:
            # L1MobGroupSpawn.java: leader coordinate + nextInt(5)-2.
            # Failed standability/occupancy retries, with no forced overlap.
            x, y, heading = row['members'][wave.groups[0].group_id][0]['position']
            leader = self.spawn_groups[wave.groups[0].group_id].slots[0]
            entity = self.spawner.entities.get(leader.uid) if leader.uid is not None else None
            if entity is not None:
                x, y, heading = entity.x, entity.y, entity.heading
            return x + self.rng.randrange(-2, 3), y + self.rng.randrange(-2, 3), heading
        return None

    def _hp(self, hp, group, slot):
        _, _, member = self._record(group, slot)
        return min(hp, member['hp']) if member and member['phase'] == 'alive' else hp

    def _snapshot(self, group, slot):
        _, _, member = self._record(group, slot)
        if member is None or slot.state is not SlotState.ALIVE:
            return
        entity = self.spawner.entities.get(slot.uid)
        if entity is not None:
            member.update(phase='alive', hp=slot.hp,
                          position=[entity.x, entity.y, entity.heading], home=list(slot.home))

    def _spawned(self, group, slot, now):
        if group.spec.group_id in self.by_group:
            _, _, member = self._record(group, slot)
            if member['phase'] == 'alive' and 'home' in member:
                slot.home = tuple(member['home'])
            self._snapshot(group, slot)
            self._save()

    def _hp_changed(self, group, slot):
        if group.spec.group_id in self.by_group:
            self._snapshot(group, slot)
            self._save()

    def _dead(self, group, slot, now):
        wave, row, member = self._record(group, slot)
        if wave is None:
            return
        entity = self.spawner.entities.get(slot.uid)
        if entity is not None:
            member['position'] = [entity.x, entity.y, entity.heading]
        member.update(phase='dead', corpse_until=self.wall_clock() + group.monster.corpse_ms / 1000)
        if all(value['phase'] == 'dead' for values in row['members'].values() for value in values):
            upcoming = self._schedule(wave, self.wall_clock(), after=row['cycle_index'])
            upcoming['due_epoch'] = max(upcoming['due_epoch'],
                *(value['corpse_until'] for values in row['members'].values() for value in values))
            self.document['waves'][wave.key] = upcoming
        self._save()

    def _save(self):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        with temporary.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(self.document, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def close(self):
        if self.closed:
            return
        for group in self.spawner.groups:
            if group.spec.group_id in self.by_group:
                for slot in group.slots:
                    self._snapshot(group, slot)
        if self.waves:
            self._save()
        for event, handle in self.handles:
            self.spawner.events.remove(event, handle)
        self.handles.clear()
        self.closed = True

    def status(self):
        result = []
        for wave in self.waves:
            row = self.document['waves'][wave.key]
            phases = [member['phase'] for members in row['members'].values() for member in members]
            state = 'alive' if 'alive' in phases else 'placing' if 'dead' in phases else 'scheduled'
            result.append({'key': wave.key, 'cycle': wave.cycle, 'state': state,
                'due_epoch': None if 'alive' in phases or 'dead' in phases else row['due_epoch'],
                'alive': phases.count('alive'), 'pending': phases.count('pending'),
                'dead': phases.count('dead')})
        return result


def _boss_cycles_started(ctx):
    world = ctx.world
    waves = load_policy(world.data, serves_map=ctx.realm.serves_map)
    owner = BossCycles(world.spawner, world.data, waves,
                       path=state_path_for(ctx.world_options['store_path']))
    ctx._world_boss_cycles = owner
    # replace_data keeps combat, ground rewards and catalog subscribers aligned.
    world.replace_data(replace(world.data, spawns=tuple(group.spec for group in world.spawner.groups)))
    world.events.add('boss_cycles', 'close', owner.close)


def _boss_cycles_stopped(ctx):
    owner = getattr(ctx, '_world_boss_cycles', None)
    if owner is not None:
        owner.close()


def _boss_cycles_report(ctx, result):
    owner = getattr(ctx, '_world_boss_cycles', None)
    if owner is not None:
        result['boss_cycles'] = {'policy': 'LOCAL_L1J_REFERENCE_BOSS_WINDOWS',
            'waves': len(owner.waves), 'state_path': str(owner.path),
            'closed': owner.closed, 'schedule': owner.status()}


METHODS = (_boss_cycles_started, _boss_cycles_stopped, _boss_cycles_report)
HOOKS = {'runtime_started': ('_boss_cycles_started',),
         'runtime_stopped': ('_boss_cycles_stopped',), 'report': ('_boss_cycles_report',)}
