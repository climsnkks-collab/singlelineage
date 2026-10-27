"""Owned pet packet lifecycle on the existing FIRST/login/selection fixture.

No original client, UI input, user profile or default game port is used. Fresh
fixture saves and every failed run stay under work/local_original_session/runs.
Only startup supplies declared test resources; actions use the real socket
decoder/router. SUCCESS is local packet behavior, never native UI equivalence.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import dataclasses
import hashlib
import heapq
import json
import os
from pathlib import Path
import random
import shutil
import tempfile
import time
import traceback
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import hunt_bot_companion as hc
from tools.local_original_session import test_ports


def command_payload(command, actor_uid, target_uid=None):
    """Actual Classic wire enums stay separate from backend mode strings."""
    if type(command) is not int or command not in range(1, 8):
        raise ValueError('PET_WIRE_COMMAND_1_TO_7_REQUIRED')
    if type(actor_uid) is not int or not 0 < actor_uid < 1 << 32:
        raise ValueError('PET_CURRENT_ACTOR_UID_REQUIRED')
    if target_uid is not None and (type(target_uid) is not int or not 0 < target_uid < 1 << 32):
        raise ValueError('PET_CURRENT_TARGET_UID_REQUIRED')
    if command == 1 and target_uid is None:
        raise ValueError('PET_ATTACK_TARGET_REQUIRED')
    return (hb.uint(1, command) + (b'' if target_uid is None else
        hb.pb.encode_bytes(2, str(target_uid).encode('ascii'))) + hb.uint(3, actor_uid))


@contextmanager
def test_environment(*, companion=False):
    values = dict(SL_PET='1', SL_COMPANION='1' if companion else '0',
                  SL_COMPANION_PET_UI='1' if companion else '0')
    old = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class PetScenario(hs.Scenario):
    """One broker epoch at a time, retaining the existing Scenario finally."""
    frames = hc.CompanionScenario.frames
    owner_attack_current = hc.CompanionScenario.owner_attack_current
    owner_potion = hc.CompanionScenario.owner_potion
    tick_wait = hc.CompanionScenario.tick_wait
    member_position = hc.CompanionScenario.member_position
    target = hc.CompanionScenario.target
    require_living_member = hc.CompanionScenario.require_living_member
    check_saved = hc.CompanionScenario.check_saved
    combat_death = hc.CompanionScenario.combat_death
    check_corpse = hc.CompanionScenario.check_corpse

    def __init__(self, args, directory):
        super().__init__(args, 'all', directory)
        self.stage = 'startup'
        self.member_id = None
        self.fixture = None
        self.pet_epochs = []
        self.broker_exception_observations = []
        self.navigation_failure = None
        self.travel_route = None
        self.travel_safe = {}

    def travel_heading(self, goal, radius):
        """Find a detour beyond the companion AI's short local BFS window.

        This changes only packet-bot route selection. Terrain, live occupancy,
        hunt safety and previously refused edges remain movement constraints.
        """
        from tools.local_original_session.npc_ai import DELTAS
        bot, terrain, now = self.bot, self.world.terrain, time.monotonic()
        start = bot.position
        occupied = {(e.x, e.y) for e in self.world.entities.near(
            bot.map_id, *start, 16, alive_only=False)
            if e.uid != bot.self_uid and e.kind.value != 'item'}
        def allowed(point, direction):
            dx, dy = DELTAS[direction]
            dest = (point[0]+dx, point[1]+dy)
            key = (bot.map_id, bot.level, dest)
            if key not in self.travel_safe:
                self.travel_safe[key] = bot.safe_hunt_cell(dest)
            return (dest not in occupied and self.travel_safe[key]
                and terrain.can_step(bot.map_id, *point, direction) is True
                and bot.blocked_edges.get((point, direction), 0) <= now)
        route_key = (bot.map_id, goal, radius)
        if self.travel_route is not None and self.travel_route[0] == route_key:
            direction = self.travel_route[1].get(start)
            if direction is not None and allowed(start, direction):
                return direction
        self.travel_route = None
        queue = [(max(0, hb.distance(start, goal)-radius), 0, start)]
        costs = {start: 0}
        parents = {}
        for _ in range(75000):
            if not queue:
                break
            _, cost, point = heapq.heappop(queue)
            if costs[point] != cost:
                continue
            if hb.distance(point, goal) <= radius:
                steps = {}
                while point != start:
                    parent, direction = parents[point]
                    steps[parent] = direction
                    point = parent
                self.travel_route = (route_key, steps)
                return steps.get(start)
            for direction, (dx, dy) in enumerate(DELTAS):
                dest = (point[0]+dx, point[1]+dy)
                if not allowed(point, direction):
                    continue
                next_cost = cost+1
                if next_cost >= costs.get(dest, float('inf')):
                    continue
                costs[dest] = next_cost
                parents[dest] = (point, direction)
                heapq.heappush(queue, (next_cost+max(0, hb.distance(dest, goal)-radius),
                                      next_cost, dest))
        return None

    def record(self, name, ok, **evidence):
        super().record(name, ok, stage=self.stage, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    @property
    def world(self):
        return self.broker._world

    @property
    def manager(self):
        return self.world.companions

    @property
    def member(self):
        return self.broker._pet_system.records[self.member_id]

    @property
    def actor(self):
        return self.manager.active.get(self.member_id)

    async def wait_current(self, label, predicate, *, timeout=None, action=None,
                           member_required=False, marker=0, target_uid=None):
        until = time.monotonic() + (self.args.death_timeout if timeout is None else timeout)
        while not predicate():
            if member_required:
                self.require_living_member(label, marker, target_uid)
            if self.bot.dead:
                raise hs.Unconfirmed('OWNER_DIED:' + label)
            if time.monotonic() >= until:
                raise hs.Unconfirmed('OBSERVATION_TIMEOUT:' + label)
            await self.owner_potion()
            if action is not None:
                await action()
            if time.monotonic() - self.bot.last_alive >= .5:
                await self.bot.alive()
            await asyncio.sleep(.05)
        await self.bot.alive()

    async def open(self, *, seed, character=None):
        self.travel_route, self.travel_safe = None, {}
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(self.directory, expected, seed=seed)
        original_failure_code = self.broker._failure_code
        def observed_failure_code(error):
            code = original_failure_code(error)
            self.broker_exception_observations.append(dict(code=code, error=repr(error),
                traceback=''.join(traceback.format_exception(error))[-6000:]))
            del self.broker_exception_observations[:-8]
            return code
        self.broker._failure_code = observed_failure_code
        if seed:
            self.initialize_fixture()
            starting = self.directory / 'starting-save'
            starting.mkdir()
            for path in self.directory.glob('*.json'):
                shutil.copy2(path, starting / path.name)
            self.fixture['start_save'] = str(starting)
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--minutes', str(self.args.minutes),
            '--timeout', str(self.args.timeout), '--potion-threshold', str(self.args.potion_threshold)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = hs.ScenarioBot(options)
        self.bot.heading = self.travel_heading
        original_step = self.bot.step
        async def step(goal, radius=0):
            await self.owner_potion()
            try:
                return await original_step(goal, radius)
            except hb.BotFailure:
                self.navigation_failure = dict(stage=self.stage, position=self.bot.position,
                    goal=goal, radius=radius, accepted_steps=self.bot.moves,
                    corrections=sum(frame.opcode == 0x4ee0 for frame in self.bot.peer.frames))
                raise
        self.bot.step = step
        original_apply = self.bot.apply
        def apply(frame):
            self.bot.data = self.world.data
            if frame.opcode in (0x4f14, 0x4f16, 0x4ed5, 0x4e44, 0x4f1a):
                frame.values = hb.fields(frame.wire[4:-2])
            original_apply(frame)
        self.bot.apply = apply
        self.bots.append(self.bot)
        self.bot.data, self.bot.started = self.world.data, time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')
        if self.args.with_companion:
            await self.suspend_mage()

    async def close(self):
        if self.broker is not None:
            system = getattr(self.broker, '_pet_system', None)
            if system is not None:
                self.pet_epochs.append(dict(stage=self.stage, errors=list(system.errors),
                    events=list(system.events)[-32:],
                    records=[dict(pet_id=key, owner=row.owner_character_id, hp=row.hp,
                        level=row.level, exp=row.exp, alive=row.alive,
                        metadata={field: row.equipment['_pet'].get(field)
                            for field in ('species', 'collar_uid', 'mode', 'out')},
                        pending_bag=bool(row.equipment['_pet'].get('pending_bag')))
                        for key, row in system.records.items()]))
        return await super().close()

    def initialize_fixture(self):
        """Fresh saved resources only, before broker start and selection."""
        from tools.local_original_session import inventory
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        before = self.store.restore(1)
        rows = [dict(row.raw_fields) for row in inventory.validate_kit_frame(before)]
        next_uid = max(row[1] for row in rows) + 1
        additions = []
        for template, count in ((10, 20), (28, 5)):
            if any(row[2] == template and row[4] >= count for row in rows):
                continue
            row = dict(self.broker.INVENTORY_STARTER_FIELDS)
            row.update({1: next_uid, 2: template, 4: count, 7: 0})
            rows.append(row)
            additions.append(dict(uid=next_uid, template=template, count=count))
            next_uid += 1
        after = inventory.build_kit_frame(rows)
        if after != before:
            if not self.store.replace_kit(1, before, after, append=True):
                raise hs.Unconfirmed('FRESH_PET_SUPPLY_CAS_REQUIRED')
            self.broker._inventory_current_frame = after
        data = self.world.data
        owner = self.broker.realm.store._read()['characters'][0]
        stats = owner['attributes']
        baseline = actor_hook.profiles()[0].fields
        profile = PcProfile(1, owner['class'], owner['gender'], stats[0], stats[1], con=stats[2], wis=stats[3])
        growth = on_kill(RewardPcState(0, profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=data.pc_exp[5]), random.Random(0x504554), data=data)
        self.broker._world_progress.commit(1, Progress(data.pc_exp[5], 6, growth.max_hp, growth.max_mp))
        self.fixture = dict(character_uid=1, initial_level=6, initial_exp=data.pc_exp[5],
            initial_max_hp=growth.max_hp, initial_max_mp=growth.max_mp,
            growth='existing pure world_reward.on_kill / saved knight stats / RNG0x504554',
            supplied_items=additions, inventory_sha256=hashlib.sha256(after).hexdigest(),
            start_save=str(self.directory / 'characters.json'),
            scope='fresh pre-login saved test_knight + explicit meat10/resurrection28 resources and Lv6; '
                  'no live HP, NPC, UID, clock, reward or readiness mutation')

    def pets(self):
        return {key: value for key, value in self.broker._pet_system.records.items()
                if isinstance(value.equipment.get('_pet'), dict)
                and value.owner_character_id == self.bot.self_uid}

    async def suspend_mage(self):
        """Exercise the existing feature route, then keep pet reward unambiguous."""
        from tools.local_original_session.world_feature_companion import TOKEN_NAME
        mages = [actor for actor in self.manager.active.values()
                 if not isinstance(actor.record.equipment.get('_pet'), dict)
                 and actor.record.owner_character_id == self.bot.self_uid]
        if not mages:
            self.record('existing_mage_not_duplicated_when_pet_restores',
                self.member_id is not None and self.actor is not None and bool(self.pets()))
            return
        mage = min(mages, key=lambda actor: actor.character_id)
        await self.bot.peer.request(0x4f13, hb.uint(1, mage.ref.uid),
            check=lambda batch: hb.find(batch, 0x4f14, **{'1': mage.ref.uid}), label='COEXIST_MAGE_QUERY')
        await self.bot.peer.request(0x4f02, hc.command_payload(4, mage.ref.uid), alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='COEXIST_MAGE_HOLD')
        self.record('existing_mage_query_and_command_survive_pet_routes',
            mage.record.combat_mode == 'PASSIVE' and mage.record.movement_mode == 'HOLD')
        tokens = [uid for uid, row in self.bot.inventory.items() if row.get(18) == TOKEN_NAME]
        if not tokens:
            raise hs.Unconfirmed('RECEIVED_COMPANION_MANAGEMENT_TOKEN_REQUIRED')
        await self.use(min(tokens))
        await self.wait_current('mage_management_toggle_off',
            lambda: mage.character_id not in self.manager.active, timeout=10)

    async def use(self, item_uid, target_uid=None):
        params = b''.join(hb.uint(n, value) for n, value in
            (((1, 1), (15, 0), (16, 0)) if target_uid is None else
             ((1, 1), (2, target_uid), (3, 0), (15, 0), (16, 0))))
        marker = self.bot.peer.ordinal
        await self.bot.peer.request(0x0960, hb.uint(1, item_uid) + hb.pb.encode_bytes(2, params),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='PET_ITEM_USE_ALIVE')
        return marker

    async def pet_status(self, uid=None):
        uid = self.actor.ref.uid if uid is None else uid
        before = dataclasses.asdict(self.member)
        batch = await self.bot.peer.request(0x4f13, hb.uint(1, uid),
            check=lambda batch: hb.find(batch, 0x4f14, **{'1': uid}), label='PET_CURRENT_STATUS')
        frame = hb.find(batch, 0x4f14, **{'1': uid})
        child = hb.fields(hb.scalar(frame.values, 3))
        self.record('pet_window_current_resources', hb.scalar(frame.values, 2) == 1 and
            all(hb.scalar(child, number) == value for number, value in
                ((2, self.member.max_hp), (4, self.member.max_mp), (6, self.member.level))) and
            min(before['hp'], self.member.hp) <= hb.scalar(child, 3) <= max(before['hp'], self.member.hp) and
            min(before['mp'], self.member.mp) <= hb.scalar(child, 5) <= max(before['mp'], self.member.mp),
            actor_uid=uid, mode=hb.scalar(child, 1), hp=hb.scalar(child, 3), level=hb.scalar(child, 6))
        return frame, child

    async def command(self, mode, target=None):
        if self.actor is None:
            raise hs.Unconfirmed('CURRENT_ACTIVE_PET_REQUIRED')
        await self.pet_status()
        marker = self.bot.peer.ordinal
        await self.bot.peer.request(0x4f02, command_payload(mode, self.actor.ref.uid, target),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='PET_COMMAND_' + str(mode))
        return marker

    async def tame(self):
        self.stage = 'natural_wild_tame'
        until = time.monotonic() + self.args.navigation_timeout
        candidates = set()
        from tools.local_original_session.world_pet import load_pets
        for species in load_pets().species.values():
            candidates.update(species.classic_candidates)
        await self.damage_wild_for_taming(until, candidates)

    async def damage_wild_for_taming(self, until, candidates):
        """A lethal ordinary swing needs another wild animal, never HP repair."""
        wild = None
        while time.monotonic() < until:
            eligible = [(hb.distance(self.bot.position, row['position']), uid)
                for uid, row in self.bot.actors.items() if row['template'] in candidates
                and row['alive'] and self.manager.get_actor(uid) is None]
            if eligible:
                _, wild = min(eligible)
                break
            groups = [group.spec for group in self.world.spawner.groups if group.spec.map_id == self.bot.map_id
                and group.spec.template_id in candidates]
            if not groups:
                raise hs.Unconfirmed('PRODUCT_WILD_PET_SPAWN_REQUIRED')
            group = min(groups, key=lambda g: hb.distance(self.bot.position, (g.rect.x1, g.rect.y1)))
            await self.bot.step(((group.rect.x1 + group.rect.x2)//2, (group.rect.y1 + group.rect.y2)//2), radius=2)
            await self.tick_wait(.1)
        if wild is None:
            raise hs.Unconfirmed('RECEIVED_WILD_PET_REQUIRED')
        entity = self.world.entities.get(wild)
        definition = self.world.data.monsters[entity.template_id]
        marker = self.bot.peer.ordinal
        def current_hp():
            found = self.world.spawner.slot_for(wild)
            return None if found is None else found[1].hp
        initial_hp = current_hp()
        while (hp := current_hp()) is not None and hp >= definition.hp // 3:
            if time.monotonic() >= until:
                raise hs.Unconfirmed('NATURAL_WILD_DAMAGE_DEADLINE')
            await self.owner_attack_current(wild)
            await self.tick_wait(.05)
        hp = current_hp()
        if hp == 0:
            self.record('wild_taming_attempt_ended_in_combat_death',
                bool(self.frames(marker, 0x4e31, **{'2': self.bot.self_uid, '3': wild})),
                wild_uid=wild, initial_hp=initial_hp, hp=hp, max_hp=definition.hp)
            if time.monotonic() >= until:
                raise hs.Unconfirmed('NATURAL_WILD_DAMAGE_DEADLINE')
            return await self.damage_wild_for_taming(until, candidates)
        self.record('wild_hp_reduced_by_received_owner_attacks', hp is not None and 0 < hp < definition.hp // 3
            and bool(self.frames(marker, 0x4e31, **{'2': self.bot.self_uid, '3': wild})),
            wild_uid=wild, initial_hp=initial_hp, hp=hp, max_hp=definition.hp)
        supplies = [(uid, row) for uid, row in self.bot.inventory.items()
                    if row.get(2) == 10 and row.get(4, 0) > 0]
        if not supplies:
            raise hs.Unconfirmed('RECEIVED_MEAT10_REQUIRED')
        item_uid, item = min(supplies)
        count, before = item[4], set(self.pets())
        marker = await self.use(item_uid, wild)
        await self.wait_current('new_pet_and_collar', lambda: bool(set(self.pets()) - before), timeout=10)
        self.member_id = min(set(self.pets()) - before)
        collar_uid = self.member.equipment['_pet']['collar_uid']
        await self.wait_current('received_issued_collar', lambda: collar_uid in self.bot.inventory, timeout=10)
        self.record('normal_food_tame_issued_owned_collar_and_actor',
            self.bot.inventory.get(item_uid, {}).get(4, 0) == count - 1 and
            self.bot.inventory[collar_uid].get(2) == 361 and self.actor is not None and
            self.actor.ref.uid != wild and self.world.entities.get(wild) is None and
            bool(self.frames(marker, 0x4e96, **{'2': self.actor.ref.uid})),
            pet_id=self.member_id, wild_uid=wild, actor_uid=self.actor.ref.uid,
            collar_uid=collar_uid, food_uid=item_uid, food_before=count, food_after=count-1)

    async def collar(self):
        self.stage = 'collar_store_summon'
        collar_uid, ref = self.member.equipment['_pet']['collar_uid'], self.actor.ref
        before = dataclasses.asdict(self.member)
        quantity = self.bot.inventory[collar_uid][4]
        marker = await self.use(collar_uid)
        await self.wait_current('collar_stored', lambda: self.actor is None, timeout=10)
        stored = dataclasses.asdict(self.member)
        stored['equipment']['_pet']['out'] = before['equipment']['_pet']['out']
        self.record('collar_stores_without_cost_or_resource_reset',
            self.world.entities.get(ref.uid) is None and stored == before and
            self.bot.inventory[collar_uid][4] == quantity and
            bool(self.frames(marker, 0x4e40, **{'1': ref.uid})))
        marker = await self.use(collar_uid)
        await self.wait_current('collar_summoned', lambda: self.actor is not None, timeout=10)
        self.record('collar_summons_new_actor_preserving_saved_pet',
            self.actor.ref != ref and dataclasses.asdict(self.member) == before and
            self.bot.inventory[collar_uid][4] == quantity and
            bool(self.frames(marker, 0x4e96, **{'2': self.actor.ref.uid})),
            old_uid=ref.uid, new_uid=self.actor.ref.uid)

    async def owner_separate(self, *, distance=4):
        """Find real passable separation steps using existing bounded search."""
        from tools.local_original_session.npc_ai import bounded_path_step, DELTAS
        bot, start = self.bot, self.member_position()
        hint = (bot.position[0], bot.position[1] + distance)
        previous_heading = bot.heading
        def heading(_goal, _radius):
            now, terrain, map_id = time.monotonic(), self.world.terrain, bot.map_id
            occupied = {(e.x, e.y) for e in self.world.entities.near(map_id, *bot.position, 16)
                        if e.uid != bot.self_uid and e.kind.value != 'item'}
            def allowed(x, y, direction):
                dx, dy = DELTAS[direction]
                return (terrain.can_step(map_id, x, y, direction) is True and
                    (x+dx, y+dy) not in occupied and bot.safe_hunt_cell((x+dx, y+dy)) and
                    bot.blocked_edges.get(((x, y), direction), 0) <= now)
            return bounded_path_step(bot.position,
                lambda x, y: hb.distance((x, y), start) >= distance, hint, allowed)
        bot.heading = heading
        try:
            await self.wait_current('owner_real_separation', lambda:
                hb.distance(bot.position, start) >= distance, timeout=20,
                member_required=True, action=lambda: bot.step(hint))
        finally:
            bot.heading = previous_heading

    async def movement_commands(self):
        self.stage = 'pet_modes_2_4_7_motion'
        await self.command(4)
        start, marker = self.member_position(), self.bot.peer.ordinal
        await self.owner_separate()
        await self.tick_wait(1)
        self.record('mode4_rest_stops_motion_and_attacks', self.member_position() == start and
            self.member.movement_mode == 'HOLD' and self.member.combat_mode == 'PASSIVE' and
            self.actor.target is None and not self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid}) and
            not self.frames(marker, 0x4e31, **{'2': self.actor.ref.uid}), position=start)
        marker = await self.command(2)
        await self.wait_current('mode2_follow_motion', lambda: self.member_position() != start and
                                bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})),
                                timeout=15, member_required=True)
        self.record('mode2_attack_follows_owner_with_real_motion',
            self.member.movement_mode == 'FOLLOW' and self.member.combat_mode == 'ASSIST' and
            bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})),
            start=start, finish=self.member_position())
        await self.wait_current('pet_returns_to_owner', lambda:
            hb.distance(self.bot.position, self.member_position()) <= 2, timeout=15, member_required=True)
        start = self.member_position()
        marker = await self.command(7)
        await self.wait_current('mode7_scatter_step', lambda: self.member_position() != start and
                                bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})),
                                timeout=15, member_required=True)
        self.record('mode7_scatter_actual_patrol',
            bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})),
            start=start, finish=self.member_position(), owner_position=self.bot.position)
        await self.command(2)

    async def guarded_participation(self, target):
        """Use the owner's real incoming/cadence window for one pet swing."""
        await self.command(4)
        begin = self.bot.peer.ordinal
        await self.wait_current('owner_first_participation_swing', lambda:
            bool(self.frames(begin, 0x4e31, **{'2': self.bot.self_uid, '3': target})),
            timeout=20, member_required=True, action=lambda: self.owner_attack_current(target))
        await self.wait_current('owner_participation_cadence_ready', lambda:
            time.monotonic() >= self.bot.next_attack, timeout=15, member_required=True)
        incoming = self.bot.peer.ordinal
        await self.wait_current('received_npc_attack_before_pet_participation', lambda:
            bool(self.frames(incoming, 0x4e31, **{'2': target, '3': self.bot.self_uid})),
            timeout=20, member_required=True, marker=begin, target_uid=target)
        begin = await self.command(1, target)
        actor_uid = self.actor.ref.uid
        await self.wait_current('actual_guarded_pet_participation_swing', lambda:
            bool(self.frames(begin, 0x4e31, **{'2': actor_uid, '3': target})),
            timeout=20, member_required=True, marker=begin, target_uid=target)
        await self.owner_attack_current(target)
        await self.command(4)
        return begin

    async def exp(self):
        self.stage = 'pet_50_50_exp'
        await self.command(2)
        kills = set()
        for index in range(2):
            target = await self.growth_target(odd=True)
            monster = self.world.data.monsters[self.world.entities.get(target).template_id]
            owner_before, member_before = self.world.exp[self.bot.self_uid], self.member.exp
            owner_half = self.world.companion_owner_half.get(self.bot.self_uid, 0)
            member_half, receipts = self.member.exp_half, len(self.world.companion_reward_receipts)
            marker = await self.guarded_participation(target)
            await self.wait_current('natural_pet_shared_kill', lambda:
                len(self.world.companion_reward_receipts) > receipts,
                member_required=True, marker=marker, target_uid=target,
                action=lambda: self.owner_attack_current(target))
            reward = self.world.companion_reward_receipts[-1]
            owner_gain, next_owner_half = hc.half_share(monster.kill_exp, owner_half)
            pet_gain, next_pet_half = hc.half_share(monster.kill_exp, member_half)
            self.record('odd_kill_50_50_carry_' + str(index + 1),
                self.world.exp[self.bot.self_uid] - owner_before == owner_gain and
                self.member.exp - member_before == pet_gain and
                self.world.companion_owner_half[self.bot.self_uid] == next_owner_half and
                self.member.exp_half == next_pet_half and reward['member_character_id'] == self.member_id and
                reward['kill_id'] not in kills and reward['joint_commit_count'] == 1 and reward['durable'],
                kill_exp=monster.kill_exp, owner_exp_gain=owner_gain, pet_exp_gain=pet_gain,
                owner_half=next_owner_half, pet_half=next_pet_half, receipt=reward)
            kills.add(reward['kill_id'])
            if index == 0:
                self.record('first_odd_kill_has_typed_half',
                    next_owner_half == 1 and next_pet_half == 1,
                    owner_half=next_owner_half, pet_half=next_pet_half)
                await self.reconnect()
                self.record('odd_half_saved_across_relogin', self.member.exp_half == 1 and
                    self.world.companion_owner_half.get(self.bot.self_uid) == 1,
                    owner_exp=self.world.exp[self.bot.self_uid], pet_exp=self.member.exp,
                    owner_half=self.world.companion_owner_half.get(self.bot.self_uid),
                    pet_half=self.member.exp_half)
                self.stage = 'pet_50_50_exp'
        await self.command(2)

    async def guard_collect(self):
        self.stage = 'pet_mode5_guard_and_mode6_collect'
        await self.command(2)
        target = await self.target(weak=True)
        # Guard is HOLD, including combat positioning. Bring the following
        # pet into an actual melee tile through ordinary owner movement first;
        # an owner standing adjacent does not put its trailing pet in range.
        from tools.local_original_session.npc_ai import local_line_clear
        def guard_position():
            entity = self.world.entities.get(target)
            point = self.member_position()
            return (entity is not None and entity.alive and point is not None and
                hb.distance(point, (entity.x, entity.y)) <= 1 and
                local_line_clear(self.world.terrain, entity.map_id, *point, entity.x, entity.y))
        async def lead_pet():
            entity = self.world.entities.get(target)
            if entity is None or not entity.alive:
                raise hs.Unconfirmed('GUARD_PREY_LEFT_BEFORE_POSITIONING')
            tx, ty = entity.x, entity.y
            occupied = {(e.x, e.y) for e in self.world.entities.near(
                entity.map_id, tx, ty, 3, alive_only=False) if e.kind.value != 'item'}
            goals = [(tx+dx, ty+dy) for dx in range(-2, 3) for dy in range(-2, 3)
                if max(abs(dx), abs(dy)) == 2 and (tx+dx, ty+dy) not in occupied
                and self.world.terrain.can_stand(entity.map_id, tx+dx, ty+dy) is True
                and self.bot.safe_hunt_cell((tx+dx, ty+dy))]
            if not goals:
                raise hs.Unconfirmed('GUARD_OWNER_LEAD_TILE_REQUIRED')
            goal = min(goals, key=lambda point: (-hb.distance(point, self.member_position()),
                       hb.distance(self.bot.position, point), point))
            if self.bot.position != goal:
                await self.bot.step(goal)
        await self.wait_current('pet_actual_guard_melee_position', guard_position,
                                timeout=45, member_required=True, action=lead_pet)
        await self.command(4)
        actor_uid = self.actor.ref.uid
        marker = await self.command(5)
        await self.wait_current('mode5_autonomous_guard_attack', lambda:
            bool(self.frames(marker, 0x4e31, **{'2': actor_uid})),
            timeout=20, member_required=True)
        swings = self.frames(marker, 0x4e31, **{'2': actor_uid})
        guarded_target = hb.scalar(swings[0].values, 3)
        self.record('mode5_guard_acquires_enemy_without_owner_attack',
            guarded_target != self.bot.self_uid and
            not self.frames(marker, 0x4e31, **{'2': self.bot.self_uid}),
            target_uid=guarded_target, swing_ordinal=swings[0].ordinal)
        await self.command(4)
        await self.wait_current('guard_target_natural_kill', lambda:
            not self.bot.actors.get(guarded_target, {}).get('alive', False),
            timeout=30, member_required=True,
            action=lambda: self.owner_attack_current(guarded_target))
        ground = []
        for uid in self.bot.ground:
            entity = self.world.entities.get(uid)
            item = None if entity is None else self.world.ground.get(entity.ref)
            if item is not None and item.item_id in self.world.data.items:
                ground.append((hb.distance(self.bot.position, (item.x, item.y)), uid, item))
        if not ground:
            raise hs.Unconfirmed('NATURAL_OWNED_LOOT_FOR_COLLECTION_REQUIRED')
        _, loot_uid, item = min(ground)
        await self.navigate((item.x, item.y), radius=1)
        template, count = item.item_id, item.count
        before = sum(row.get(4, 0) for row in self.bot.inventory.values() if row.get(2) == template)
        marker = await self.command(6)
        await self.wait_current('mode6_real_inventory_collection', lambda:
            loot_uid not in self.bot.ground and sum(row.get(4, 0) for row in self.bot.inventory.values()
                if row.get(2) == template) >= before + count, timeout=20, member_required=True)
        after = sum(row.get(4, 0) for row in self.bot.inventory.values() if row.get(2) == template)
        self.record('mode6_collect_consumes_ground_and_increases_owner_inventory',
            self.world.entities.get(loot_uid) is None and after >= before + count and
            bool(self.frames(marker, 0x4e40, **{'1': loot_uid})) and
            bool(self.frames(marker, 0x0965) or self.frames(marker, 0x0964)),
            loot_uid=loot_uid, template=template, count=count,
            inventory_before=before, inventory_after=after)
        await self.command(2)

    async def growth_target(self, *, odd=False):
        """Choose current ordinary prey inside the existing hunt safety ceiling."""
        until = time.monotonic() + self.args.navigation_timeout
        allowed = {key for key, definition in self.world.data.monsters.items()
            if 20 <= definition.hp <= 50 and definition.level <= (self.bot.level or 1)+3
            and definition.kill_exp >= 20 and (not odd or definition.kill_exp % 2 == 1)}
        destination = None
        while time.monotonic() < until:
            candidates = []
            for uid, row in self.bot.actors.items():
                entity = self.world.entities.get(uid)
                if (entity is None or not row['alive'] or row['template'] not in allowed
                        or self.manager.get_actor(uid) is not None or not self.bot.safe_hunt_cell(row['position'])):
                    continue
                definition = self.world.data.monsters[row['template']]
                separation = hb.distance(self.bot.position, row['position'])
                candidates.append((separation//8, -definition.kill_exp, separation, uid))
            if candidates:
                target = min(candidates)[3]
                await self.navigate(self.bot.actors[target]['position'], radius=1)
                if self.bot.actors.get(target, {}).get('alive'):
                    return target
            groups = [group for group in self.world.spawner.groups if group.spec.map_id == self.bot.map_id
                      and group.spec.template_id in allowed and self.bot.safe_hunt_cell(
                          ((group.spec.rect.x1+group.spec.rect.x2)//2,
                           (group.spec.rect.y1+group.spec.rect.y2)//2))]
            if not groups:
                raise hs.Unconfirmed('NATURAL_PET_GROWTH_PREY_GROUP_REQUIRED')
            # Search a live or not-yet-activated ordinary spawn before camping
            # an exhausted group. Merely reaching its center is not a refused
            # movement: wait for the real respawn clock without sending steps.
            if destination is None:
                group = min(groups, key=lambda group: (
                    0 if any(slot.hp > 0 for slot in group.slots) else 1 if not group.active else 2,
                    hb.distance(self.bot.position, (group.spec.rect.x1, group.spec.rect.y1)) /
                    (group.monster.kill_exp * group.spec.target_count)))
                destination = ((group.spec.rect.x1+group.spec.rect.x2)//2,
                               (group.spec.rect.y1+group.spec.rect.y2)//2)
            if hb.distance(self.bot.position, destination) > 2:
                await self.bot.step(destination, radius=2)
            await self.tick_wait(.2)
        raise hs.Unconfirmed('NATURAL_PET_GROWTH_PREY_TIMEOUT')

    async def growth(self):
        self.stage = 'natural_pet_level6_growth'
        from tools.local_original_session.world_pet import load_pets
        catalog = load_pets()
        start = dataclasses.asdict(self.member)
        marker, kills = self.bot.peer.ordinal, []
        until = time.monotonic() + self.args.growth_timeout
        while self.member.level < 6:
            if time.monotonic() >= until:
                raise hs.Unconfirmed('NATURAL_PET_LEVEL6_GROWTH_DEADLINE')
            await self.command(2)
            target = await self.growth_target()
            await self.command(4)
            definition = self.world.data.monsters[self.world.entities.get(target).template_id]
            begin = self.bot.peer.ordinal
            prior_kill = (self.world.companion_reward_receipts[-1]['kill_id']
                          if self.world.companion_reward_receipts else None)
            before, owner_before = self.member.exp, self.world.exp[self.bot.self_uid]
            owner_half, pet_half = self.world.companion_owner_half.get(self.bot.self_uid, 0), self.member.exp_half
            begin = await self.guarded_participation(target)
            await self.wait_current('growth_shared_natural_kill', lambda:
                bool(self.world.companion_reward_receipts) and
                self.world.companion_reward_receipts[-1]['kill_id'] != prior_kill,
                timeout=60, member_required=True, marker=begin, target_uid=target,
                action=lambda: self.owner_attack_current(target))
            owner_gain, expected_owner_half = hc.half_share(definition.kill_exp, owner_half)
            pet_gain, expected_pet_half = hc.half_share(definition.kill_exp, pet_half)
            receipt = self.world.companion_reward_receipts[-1]
            valid = (self.member.exp == before+pet_gain and self.world.exp[self.bot.self_uid] == owner_before+owner_gain
                and self.member.exp_half == expected_pet_half
                and self.world.companion_owner_half[self.bot.self_uid] == expected_owner_half
                and receipt['durable'] and receipt['joint_commit_count'] == 1
                and receipt['member_character_id'] == self.member_id)
            self.record('natural_growth_shared_kill_' + str(len(kills)+1), valid,
                target_uid=target, kill_exp=definition.kill_exp, pet_exp=self.member.exp,
                owner_gain=owner_gain, pet_gain=pet_gain)
            kills.append(receipt['kill_id'])
        species = catalog.species[self.member.equipment['_pet']['species']]
        gain = self.member.max_hp-start['max_hp']
        # Reward persistence completes before the tick publishes the changed
        # Pet percentage. Observe that real response instead of treating the
        # immediately preceding attack/Alive barrier as a Pet-HP barrier.
        await self.wait_current('growth_full_hp_publication', lambda:
            bool(self.frames(marker, 0x4f1a, **{'1': self.actor.ref.uid, '2': 100})), timeout=10)
        self.record('natural_pet_level6_hp_growth_and_refill', self.member.level == 6 and
            start['level'] == 5 and start['exp'] >= 750 and self.member.exp >= catalog.cumulative_exp[5] and
            species.hp_growth[0] <= gain <= species.hp_growth[1] and len(set(kills)) == len(kills) and
            bool(self.frames(marker, 0x4f1a, **{'1': self.actor.ref.uid, '2': 100})),
            kills=len(kills), initial_exp=start['exp'], final_exp=self.member.exp,
            initial_max_hp=start['max_hp'], final_max_hp=self.member.max_hp,
            initial_level=start['level'], final_level=self.member.level)
        grown = dataclasses.asdict(self.member)
        await self.reconnect()
        self.record('natural_pet_growth_saved_across_relogin', dataclasses.asdict(self.member) == grown,
            pet_level=self.member.level, pet_exp=self.member.exp, pet_max_hp=self.member.max_hp)

    async def revive(self):
        self.stage = 'targeted_pet_revive'
        ref, before = self.actor.ref, dataclasses.asdict(self.member)
        uid, row = min((uid, row) for uid, row in self.bot.inventory.items()
                      if row.get(2) == 28 and row.get(4, 0) > 0)
        count = row[4]
        marker = await self.use(uid, ref.uid)
        await self.wait_current('pet_revived', lambda: self.member.alive and
            bool(self.frames(marker, 0x4e96, **{'2': ref.uid})), timeout=10)
        await self.wait_current('received_scroll_debit', lambda: self.bot.inventory.get(uid, {}).get(4, 0) == count-1, timeout=10)
        after = dataclasses.asdict(self.member)
        self.record('pet_targeted_resurrection_cost_and_life',
            self.member.hp == max(1, self.member.max_hp//4) and self.actor.ref.uid == ref.uid and
            self.actor.ref != ref and self.world.entities.resolve(ref) is None and
            all(after[key] == before[key] for key in before.keys() - {'hp', 'alive'}) and
            bool(self.frames(marker, 0x4e96, **{'2': ref.uid})),
            scroll_uid=uid, quantity_before=count, quantity_after=count-1,
            old_generation=ref.generation, new_generation=self.actor.ref.generation,
            hp=self.member.hp)

    async def trainer(self):
        self.stage = 'original_trainer_menu_local_store_retrieve'
        candidates = [(uid, ref, spec) for uid, (ref, spec) in self.broker._pet_system.trainers.items()
                      if spec['position'][0] == self.bot.map_id]
        if not candidates:
            raise hs.Unconfirmed('CURRENT_MAP_PET_TRAINER_REQUIRED')
        uid, ref, spec = min(candidates, key=lambda entry:
            hb.distance(self.bot.position, tuple(entry[2]['position'][1:])))
        await self.command(2)
        await self.navigate(tuple(spec['position'][1:]), radius=2)
        await self.wait_current('trainer_received_appearance', lambda:
            uid in self.bot.live_appearances, timeout=10)
        before, actor_ref = dataclasses.asdict(self.member), self.actor.ref
        collar_uid = self.member.equipment['_pet']['collar_uid']
        quantity = self.bot.inventory[collar_uid][4]
        def money():
            return sum(row.get(4, 0) for row in self.bot.inventory.values() if row.get(2) == 7)
        coins = money()
        for action in ('depositpet', 'retrievepet'):
            batch = await self.bot.peer.request(0x4e43, hb.uint(1, uid),
                check=lambda batch: hb.find(batch, 0x4e44), label='PET_TRAINER_CLICK')
            dialogue = hb.find(batch, 0x4e44)
            self.record('original_trainer_dick1_menu_received',
                hb.scalar(dialogue.values, 2) == b'dick1', trainer_uid=uid, action=action)
            marker = self.bot.peer.ordinal
            payload = hb.uint(1, uid) + hb.pb.encode_bytes(2, action.encode('ascii')) + hb.uint(4, 0) + hb.uint(5, 0)
            await self.bot.peer.request(0x4ed4, payload,
                check=lambda batch: hb.find(batch, 0x4e44), label='PET_TRAINER_' + action)
            if action == 'depositpet':
                await self.wait_current('trainer_pet_stored', lambda: self.actor is None, timeout=10)
                stored = dataclasses.asdict(self.member)
                stored['equipment']['_pet']['out'] = before['equipment']['_pet']['out']
                self.record('trainer_deposit_preserves_collar_and_resources',
                    stored == before and self.bot.inventory[collar_uid][4] == quantity and
                    self.world.entities.get(actor_ref.uid) is None and money() == coins and
                    bool(self.frames(marker, 0x4e40, **{'1': actor_ref.uid})))
            else:
                await self.wait_current('trainer_pet_retrieved', lambda: self.actor is not None and money() == coins-50,
                                        timeout=10)
                self.record('trainer_retrieve_real_fee50_and_new_actor',
                    dataclasses.asdict(self.member) == before and self.actor.ref != actor_ref and
                    self.bot.inventory[collar_uid][4] == quantity and
                    bool(self.frames(marker, 0x4e96, **{'2': self.actor.ref.uid})),
                    adena_before=coins, adena_after=money(), policy='LOCAL unique collar/direct original retrievepet action, fee50')

    async def reconnect(self):
        self.stage = 'pet_saved_reconnect'
        before, character = dataclasses.asdict(self.member), self.bot.character
        owner_exp = self.world.exp[self.bot.self_uid]
        owner_half = self.world.companion_owner_half.get(self.bot.self_uid, 0)
        path = self.broker._pet_system.store.path
        owner_uid = self.bot.self_uid
        if not await self.close():
            raise hs.Unconfirmed('PET_NORMAL_QUIT_CLOSE_REQUIRED')
        self.check_saved(path, owner_uid, before, owner_exp, owner_half, 'pet_joint_saved_before_reconnect')
        await self.open(seed=False, character=character)
        self.record('normal_pet_reconnect_preserves_identity_resources_modes',
            dataclasses.asdict(self.member) == before and self.actor is not None and
            self.world.exp[self.bot.self_uid] == owner_exp and
            self.world.companion_owner_half.get(self.bot.self_uid, 0) == owner_half and
            self.member.equipment['_pet']['collar_uid'] in self.bot.inventory,
            pet_id=self.member_id, actor_uid=self.actor.ref.uid, saved_path=str(path),
            owner_exp=self.world.exp[self.bot.self_uid], owner_half=owner_half, pet_half=self.member.exp_half)
        await self.pet_status()

    async def all(self):
        await self.tame()
        await self.pet_status()
        await self.collar()
        await self.exp()
        await self.growth()
        await self.movement_commands()
        await self.guard_collect()
        await self.combat_death()
        await self.revive()
        await self.trainer()
        await self.reconnect()


def parser():
    result = hs.parser()
    result.description = __doc__
    next(action for action in result._actions if action.dest == 'scenario').choices = ('all',)
    result.add_argument('--with-companion', action='store_true', help='also enable the existing companion feature and pet UI')
    result.add_argument('--growth-timeout', type=hb.positive, default=3600,
                        help='ordinary hunting deadline for pet750 EXP to level6; no EXP fixture or clock change')
    return result


async def run(args):
    if os.environ.get('SL_TEST_PORT_BASE') != '16000':
        raise ValueError('PET_TEST_REQUIRES_SL_TEST_PORT_BASE_16000')
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-pet-', dir=root))
    source_paths = ('hunt_bot_pet.py', 'hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_companion.py',
        'world_pet.py', 'world_feature_pet.py', 'world_handlers.py', 'world_companion.py',
        'world_feature_companion.py', 'companion_ai.py', 'npc_ai.py', 'world_visibility.py',
        'world_combat.py', 'world_reward.py', 'world_bridge.py', 'world_persist.py',
        'inventory.py', 'inventory_store.py', 'equipment_store.py', 'broker.py',
        'data/m1/pets.json', 'data/m1/pet_runtime.json')
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).exists()}
    started_sources = sources()
    with test_environment(companion=args.with_companion):
        scenario = PetScenario(args, directory)
        result = await scenario.run()
    result.update(scope='owned fresh test profile; real FIRST/login/select/world/socket decoder/router; '
        'LOCAL pet policy and Classic candidate wire; native input/rendering unverified',
        fixture=scenario.fixture, pet_epochs=scenario.pet_epochs,
        navigation_failure=scenario.navigation_failure,
        broker_exception_observations=scenario.broker_exception_observations,
        source_sha256_start=started_sources, source_sha256=sources())
    result['source_changes_during_run'] = [name for name in source_paths
        if started_sources.get(name) != result['source_sha256'].get(name)]
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    result = asyncio.run(run(parser().parse_args(argv)))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
