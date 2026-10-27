"""Owned companion socket lifecycle on the existing Scenario/build_epoch fixture.

python -X utf8 -B -m tools.local_original_session.hunt_bot_companion --scenario all

Import/help never starts a broker. Execution opts the fresh retained test profile
into SL_COMPANION and the experimental run400 pet commands. All actions use the
real peer.request router; observations only read current product state. No game,
user save, live HP/clock mutation, automatic resurrection, or native pixel claim.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import dataclasses
import json
import math
import os
from pathlib import Path
import random
import tempfile
import time
import uuid

from tools.local_original_session import hunt_bot as hb
from tools.local_original_session import hunt_bot_scenarios as hs
from tools.local_original_session import test_ports

PERSISTENT_FIELDS = tuple(('character_id owner_character_id account_id level exp exp_half hp mp '
    'max_hp max_mp equipment learned_spells movement_mode combat_mode support_enabled mp_reserve alive').split())


def command_payload(command, member_uid, target_uid=None):
    """run400/PET_EVIDENCE wire; mode semantics are explicit LOCAL policy."""
    if command not in (1, 2, 3, 4, 8) or type(member_uid) is not int or member_uid <= 0:
        raise ValueError('COMPANION_COMMAND_INPUT')
    if command == 1 and (type(target_uid) is not int or target_uid <= 0):
        raise ValueError('COMPANION_TARGET_INPUT')
    return (hb.uint(1, command) + (b'' if target_uid is None else
        hb.pb.encode_bytes(2, str(target_uid).encode('ascii'))) + hb.uint(3, member_uid))


def half_share(amount, half):
    if type(amount) is not int or amount <= 0 or type(half) is not int or half not in (0, 1):
        raise ValueError('COMPANION_TYPED_HALF_REQUIRED')
    return divmod(amount + half, 2)


@contextmanager
def test_environment(*, magic=False, revive_exp=False, map_exp=False):
    keys = ('SL_COMPANION', 'SL_COMPANION_PET_UI', 'SL_SPELL_EXP', 'SL_COMPANION_REVIVE_EXP',
            'SL_EXPERIMENT_MAP')
    old = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            if key == 'SL_EXPERIMENT_MAP':
                os.environ[key] = '2' if map_exp else '0'
                continue
            enabled = magic if key == 'SL_SPELL_EXP' else revive_exp if key == 'SL_COMPANION_REVIVE_EXP' else True
            os.environ[key] = '1' if enabled else '0'
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class CompanionScenario(hs.Scenario):
    """Uses the original Scenario finally/close and retained per-epoch profiles."""
    def __init__(self, args, directory):
        super().__init__(args, 'equipment_flow' if args.scenario == 'equipment' else args.scenario, directory)
        self.member_id = None
        self.pet_wire = []
        self.stage = 'startup'
        self.fixture_growth = None
        self.owner_fixture = None

    def record(self, name, ok, **evidence):
        super().record(name, ok, stage=self.stage, **evidence)
        # Scenario.run/close record the first exception and cleanup failures.
        # Those summaries must not raise again and erase the retained JSON.
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    @property
    def world(self):
        return self.broker._world

    @property
    def manager(self):
        manager = getattr(self.world, 'companions', None)
        if manager is None:
            raise hs.Unconfirmed('COMPANION_PRODUCT_MANAGER_REQUIRED')
        return manager

    @property
    def member(self):
        if self.member_id not in self.manager.records:
            raise hs.Unconfirmed('OWNED_SAVED_MAGE_RECORD_REQUIRED')
        return self.manager.records[self.member_id]

    @property
    def actor(self):
        return self.manager.active.get(self.member_id)

    def member_position(self):
        actor = self.actor
        entity = None if actor is None else self.world.entities.resolve(actor.ref)
        return None if entity is None else (entity.x, entity.y)

    def frames(self, marker, opcode, **wanted):
        return [frame for frame in self.bot.peer.frames if frame.ordinal > marker and
            frame.opcode == opcode and all(hb.scalar(frame.values, int(key)) == value
                                         for key, value in wanted.items())]

    async def open(self, *, seed, character=None):
        # Same FIRST/login/selection and build_epoch fixture, with no saved-state
        # initialization on reconnect. No second broker runs in parallel.
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(self.directory, expected, seed=seed)
        if seed:
            self.initialize_mage_fixture()
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--minutes', str(self.args.minutes),
            '--timeout', str(self.args.timeout), '--potion-threshold', str(self.args.potion_threshold)])
        options.port, options.character = test_ports.port(options.port), character
        self.bot = hs.ScenarioBot(options)
        self.bot.heading = self.travel_heading
        original_step = self.bot.step
        async def step(goal, radius=0):
            await self.owner_potion()
            return await original_step(goal, radius)
        self.bot.step = step
        # Extend decoding locally; shared HuntBot behavior and frames stay intact.
        original_apply = self.bot.apply
        def apply(frame):
            if frame.opcode in (0x4f14, 0x4ed8, 0x4f16, 0x4ed5):
                frame.values = hb.fields(frame.wire[4:-2])
                if frame.opcode == 0x4f14:
                    self.pet_wire.append(frame)
            original_apply(frame)
        self.bot.apply = apply
        self.bots.append(self.bot)
        from tools.local_original_session.game_data import load_m1
        self.bot.data, self.bot.started = load_m1(), time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')
        records = [record for record in self.manager.records.values()
                   if record.owner_character_id == self.bot.self_uid]
        if self.member_id is None:
            if not records:
                raise hs.Unconfirmed('STARTUP_OWNED_MAGE_REQUIRED')
            self.member_id = min(record.character_id for record in records)

    def travel_heading(self, goal, radius):
        """Reuse bounded static-terrain navigation after random travel.

        This is a bot decision only: every step still uses the real movement
        request/Alive barrier and the product's terrain/owner checks.
        """
        from tools.local_original_session.npc_ai import bounded_path_step, DELTAS
        bot, terrain, now = self.bot, self.world.terrain, time.monotonic()
        occupied = {(e.x, e.y) for e in self.world.entities.near(
            bot.map_id, *bot.position, 16, alive_only=False)
            if e.uid != bot.self_uid and e.kind.value != 'item'}
        def can_step(x, y, heading):
            dx, dy = DELTAS[heading]
            point = (x + dx, y + dy)
            return (terrain.can_step(bot.map_id, x, y, heading) is True and
                point not in occupied and bot.safe_hunt_cell(point) and
                bot.blocked_edges.get(((x, y), heading), 0) <= now)
        return bounded_path_step(bot.position,
            lambda x, y: hb.distance((x, y), goal) <= radius, goal, can_step)

    def initialize_mage_fixture(self):
        """Fresh fixture only: existing pure LOCAL growth, before server/login.

        This initializes the existing ProgressStore, never an active HP ledger.
        Product fresh mages retain their ordinary level1 HP12/MP8 baseline.
        """
        from tools.local_native_login_local_ack_hook import ack_enter_world as ack
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        data = load_m1()
        growth_path = Path(__file__).parent / 'data' / 'companion' / 'mage_growth.json'
        build = json.loads(growth_path.read_text(encoding='utf-8'))['local_build']['creation_original_stats']
        stats = tuple(build[key] for key in ('STR', 'DEX', 'CON', 'WIS', 'CHA', 'INT'))
        uid, _, _ = self.broker.realm.store.create(ack.realm.Creation('SoloMage', 3, 0, stats))
        level = self.args.fixture_level
        exp = data.pc_exp[level - 1]
        profile = PcProfile(1, 3, 0, stats[0], stats[1], con=stats[2], wis=stats[3])
        calculated = on_kill(RewardPcState(0, profile, 12, 8),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x434f4d50), data=data)
        self.broker._world_progress.commit(uid, Progress(exp, level, calculated.max_hp, calculated.max_mp))
        self.fixture_growth = dict(character_id=uid, initial_level=level, initial_exp=exp,
            initial_max_hp=calculated.max_hp, initial_max_mp=calculated.max_mp,
            baseline_level=1, baseline_hp=12, baseline_mp=8, rng_seed='0x434f4d50',
            formula='LOCAL existing world_reward.on_kill level growth / data.m1.level_growth; pure calculation then pre-login ProgressStore initialization')
        if self.args.scenario in ('selection', 'all'):
            from tools.local_original_session import movement
            from tools.local_original_session.hunt_bot_loopback import START
            fallback = movement.authority.unpack_grid(self.broker.realm._actor_fields[1])
            current = self.broker.realm.positions.restore(
                movement.Position(uid, 'SoloMage', 0, *fallback))
            self.broker.realm.positions.commit(current,
                movement.Position(uid, current.name, 0, *START))
            self.fixture_growth['initial_position'] = dict(map_id=0, grid=list(START),
                source='existing hunt_bot_loopback.START; fresh pre-login PositionStore initialization',
                reason='current S32 mask1 blocks all eight edges at unsaved profile fallback; native movement unverified')
        if self.args.scenario in ('map_travel', 'map_travel_dead'):
            from tools.local_original_session import movement
            current = self.broker.realm.positions.restore(
                movement.Position(1, 'SoloKnight', 0, 0, 0))
            self.broker.realm.positions.commit(current,
                movement.Position(1, current.name, 0, 32479, 32852))
            self.fixture_growth['start'] = 'pre-login S32 passable tile southeast of LOCAL stair trigger'
            if self.args.scenario == 'map_travel_dead':
                from tools.local_original_session.world_companion import CompanionRecord
                member = CompanionRecord(uid, 1, 'owned-local-test', level=level,
                    exp=exp, hp=0, alive=False, max_hp=calculated.max_hp,
                    mp=calculated.max_mp, max_mp=calculated.max_mp,
                    equipment={'weapon_template': 230})
                self.broker._companion_store.payload['records'] = [dataclasses.asdict(member)]
                self.fixture_growth['initial_dead'] = True
        # The bot's ordinary danger ceiling is owner level + 3. A level6
        # pre-login fixture can approach the level9 werewolf through that same
        # guard, while retaining the exact saved KNIGHT creation attributes.
        owner = next(row for row in self.broker.realm.store._read()['characters'] if row['class'] == 1)
        owner_stats = owner['attributes']
        # Travel also retains earned EXP: the realm status encoder supports f26.
        owner_level = 6
        owner_exp = data.pc_exp[owner_level - 1]
        baseline = actor_hook.profiles()[0].fields
        owner_profile = PcProfile(1, owner['class'], owner['gender'], owner_stats[0], owner_stats[1],
                                  con=owner_stats[2], wis=owner_stats[3])
        owner_growth = on_kill(RewardPcState(0, owner_profile, baseline[11], baseline[13]),
            dataclasses.replace(data.monsters[0], kill_exp=owner_exp), random.Random(0x4f574e52), data=data)
        self.broker._world_progress.commit(owner['uid'], Progress(owner_exp, owner_level,
            owner_growth.max_hp, owner_growth.max_mp))
        self.owner_fixture = dict(character_id=owner['uid'], creation_attributes=owner_stats,
            initial_level=owner_level, initial_exp=owner_exp, initial_max_hp=owner_growth.max_hp,
            initial_max_mp=owner_growth.max_mp, baseline_level=1,
            baseline_hp=baseline[11], baseline_mp=baseline[13], rng_seed='0x4f574e52',
            formula='LOCAL existing world_reward.on_kill level growth / saved KNIGHT attributes; pre-login ProgressStore initialization')
        if self.args.scenario == 'equipment':
            from tools.local_original_session import inventory
            from tools.local_original_session.world_companion import CompanionRecord
            member = CompanionRecord(uid, owner['uid'], 'owned-local-test', level=level,
                exp=exp, hp=max(1, calculated.max_hp // 4), max_hp=calculated.max_hp,
                mp=0, max_mp=calculated.max_mp)
            self.broker._companion_store.payload['records'] = [dataclasses.asdict(member)]
            # Fresh pre-login ordinary PC bag fixture: potions must be received
            # over GIVE before AI can consume them; no live resource mutation.
            rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(
                self.broker._inventory_kit_frame(3))]
            for index, item in enumerate(rows):
                item[1] = 0x20000000 + uid * inventory.KIT_MAX_ITEMS + index
                if item[2] == 14:
                    item[4] = 0
            self.store.grant(uid, inventory.build_kit_frame(rows))
            self.fixture_growth.update(initial_current_hp=member.hp, initial_current_mp=0,
                potion_bag='ordinary mage inventory.json red14 Q0 before first login')
        if self.args.scenario == 'magic':
            from tools.local_original_session.world_companion import CompanionRecord
            if level < 4:
                raise ValueError('MAGIC_FIXTURE_LEARN_LEVEL4_REQUIRED')
            # Explicit fresh pre-login learning/resources fixture; product never
            # grants spells merely because they exist in a reference catalog.
            member = CompanionRecord(uid, owner['uid'], 'owned-local-test', level=level,
                exp=exp, hp=calculated.max_hp, max_hp=calculated.max_hp,
                mp=14, max_mp=calculated.max_mp, learned_spells=(0, 2, 3),
                equipment={'weapon_template': 230})
            self.broker._companion_store.payload['records'] = [dataclasses.asdict(member)]
            initial_hp = max(1, int(owner_growth.max_hp * .3))
            self.broker._world.combat.vitals[owner['uid']] = initial_hp
            self.owner_fixture['initial_current_hp'] = initial_hp
            self.fixture_growth.update(initial_current_mp=14, learned_spells=[0, 2, 3],
                learning_scope='explicit fresh pre-login LOCAL scenario fixture')

    def require_living_member(self, label, marker, target_uid):
        if self.member.alive and self.member.hp > 0:
            return
        runtime = self.actor
        member_uid = None if runtime is None else runtime.ref.uid
        trace = []
        for frame in self.bot.peer.frames:
            if frame.ordinal <= marker or frame.opcode not in (0x4e31, 0x4e39, 0x4e40):
                continue
            if (frame.opcode == 0x4e31 and member_uid not in
                    (hb.scalar(frame.values, 2), hb.scalar(frame.values, 3))):
                continue
            if frame.opcode in (0x4e39, 0x4e40) and hb.scalar(frame.values, 1) != member_uid:
                continue
            trace.append(dict(ordinal=frame.ordinal, opcode=f'0x{frame.opcode:04X}',
                values={str(k): hb.scalar(frame.values, k) for k in range(1, 6) if k in frame.values}))
        self.record('member_death_first_observation', None, operation=label,
            target_uid=target_uid, member_uid=member_uid, hp=self.member.hp,
            max_hp=self.member.max_hp, alive=self.member.alive,
            last_observed_attacker=self.bot.last_attacker.get(member_uid), trace=trace[-12:])
        raise hs.Unconfirmed('COMPANION_DIED_DURING_' + label.upper())

    async def wait_current(self, label, predicate, *, timeout=None, member_required=False,
                           marker=0, target_uid=None, action=None):
        until = time.monotonic() + (self.args.death_timeout if timeout is None else timeout)
        while not predicate():
            if member_required:
                self.require_living_member(label, marker, target_uid)
            if self.bot.dead:
                raise hs.Unconfirmed('OWNER_DIED:' + label)
            await self.owner_potion()
            if time.monotonic() >= until:
                raise hs.Unconfirmed('OBSERVATION_TIMEOUT:' + label)
            if action is not None:
                await action()
            if time.monotonic() - self.bot.last_alive >= .5:
                await self.bot.alive()
            await asyncio.sleep(.05)
        await self.bot.alive()

    async def pet_status(self, uid=None):
        actor = self.actor
        uid = actor.ref.uid if uid is None and actor is not None else uid
        if uid is None:
            raise hs.Unconfirmed('PET_CURRENT_UID_REQUIRED')
        batch = await self.bot.peer.request(0x4f13, hb.uint(1, uid),
            check=lambda batch: hb.find(batch, 0x4f14), label='PET_QUERY_RESPONSE')
        frame = hb.find(batch, 0x4f14)
        # SC4F14 repeats pet child messages. Observe status/resource fields from
        # the real response rather than treating an Alive as a successful query.
        children = []
        for values in frame.values.values():
            for raw in values:
                if isinstance(raw, bytes):
                    try:
                        child = hb.fields(raw)
                        if all(number in child for number in range(1, 7)):
                            children.append(child)
                    except hb.BotFailure:
                        pass
        return frame, children

    async def command(self, mode, target=None):
        actor = self.actor
        if actor is None:
            raise hs.Unconfirmed('LIVE_COMPANION_FOR_COMMAND_REQUIRED')
        # The pet window is server-bound to this current actor UID. Re-query
        # before every control action, including new UID and reconnect paths;
        # an Alive barrier cannot substitute for a current SC4F14 window.
        await self.pet_status(actor.ref.uid)
        marker = self.bot.peer.ordinal
        await self.bot.peer.request(0x4f02, command_payload(mode, actor.ref.uid, target), alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label='PET_COMMAND_ALIVE_BARRIER')
        return marker

    async def owner_potion(self):
        # Lifecycle tests need the owner alive while the member takes natural
        # damage. Use the received potion UID through the real item-use route.
        # The magic scenario instead observes the companion's urgent heal.
        bot = self.bot
        if (self.args.scenario != 'magic' and not bot.dead and bot.hp is not None
                and bot.max_hp and bot.hp <= bot.max_hp * self.args.potion_threshold
                and any(row.get(2) == 14 and row.get(4, 0) > 0
                        for row in bot.inventory.values())):
            await bot.potion()

    async def tick_wait(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            await self.owner_potion()
            await self.bot.alive()
            await asyncio.sleep(min(.2, max(0, until - time.monotonic())))

    def check_saved(self, path, owner_uid, current, owner_exp, owner_half, name):
        """Read the product's joint file only after normal epoch close."""
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        saved = next((row for row in payload.get('records', ())
                      if row.get('character_id') == self.member_id), None)
        owner = payload.get('owners', {}).get(str(owner_uid), {})
        canonical = json.loads(json.dumps(current))
        self.record(name, payload.get('schema') == 1 and saved is not None and
            all(saved.get(key) == canonical[key] for key in PERSISTENT_FIELDS) and
            owner.get('exp') == owner_exp and owner.get('exp_half') == owner_half,
            path=str(path), owner_exp=owner.get('exp'), owner_half=owner.get('exp_half'),
            member_half=None if saved is None else saved.get('exp_half'))

    async def summon(self):
        self.stage = 'summon'
        await self.wait_current('automatic_owned_saved_mage', lambda: self.actor is not None, timeout=self.args.timeout)
        uid = self.actor.ref.uid
        frames = self.frames(0, 0x4e96, **{'2': uid, '16': 1})
        self.record('normal_login_selected_owned_mage_appearance', bool(self.bot.selected and frames and
            uid != self.bot.self_uid and self.member.alive), member_uid=uid, saved_member_id=self.member_id)
        _, children = await self.pet_status()
        self.record('pet_query_real_resources', any(hb.scalar(c, 2) == self.member.max_hp and
            hb.scalar(c, 3) == self.member.hp and hb.scalar(c, 4) == self.member.max_mp and
            hb.scalar(c, 5) == self.member.mp and hb.scalar(c, 6) == self.member.level for c in children),
            children=len(children), hp=self.member.hp, mp=self.member.mp)

    async def follow_hold(self):
        self.stage = 'follow_hold'
        await self.command(2)
        self.record('LOCAL_follow_assist_consumed', self.member.movement_mode == 'FOLLOW' and self.member.combat_mode == 'ASSIST')
        start, member_start = self.bot.position, self.member_position()
        marker = self.bot.peer.ordinal
        await self.navigate((start[0], start[1] + 4))
        await self.wait_current('companion_follow_distance', lambda: self.member_position() is not None and
            hb.distance(self.bot.position, self.member_position()) <= 2, timeout=15)
        self.record('follow_owner_motion', self.member_position() != member_start and
            bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})), start=member_start,
            finish=self.member_position(), distance=hb.distance(self.bot.position, self.member_position()))
        await self.command(4)
        self.record('LOCAL_hold_passive_consumed', self.member.movement_mode == 'HOLD' and self.member.combat_mode == 'PASSIVE')
        member_start, marker = self.member_position(), self.bot.peer.ordinal
        await self.navigate(start)
        await self.tick_wait(2)
        self.record('hold_while_owner_moves', self.member_position() == member_start and
            not self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid}), position=member_start, observed_seconds=2)
        await self.command(2)

    async def toggle(self):
        # Product publishes the actual UID and LOCAL token name in the kit.
        # Template1 is the existing athame visual, not a summon native opcode.
        choices = [(uid, row) for uid, row in self.bot.inventory.items() if
                   row.get(18) == '동료 소환/해산'.encode('utf-8') and row.get(4, 0) > 0]
        if not choices:
            raise hs.Unconfirmed('RECEIVED_COMPANION_TOGGLE_ITEM_UID_REQUIRED')
        uid, _ = min(choices)
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        return await self.bot.peer.request(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='COMPANION_TOGGLE_ALIVE')

    async def resummon(self):
        self.stage = 'dismiss_resummon'
        old, ref = self.actor.ref.uid, self.actor.ref
        marker = await self.command(8)
        self.record('dismiss_removes_old_actor', self.actor is None and self.world.entities.resolve(ref) is None and
            bool(self.frames(marker, 0x4e40, **{'1': old})), old_uid=old)
        marker = self.bot.peer.ordinal
        await self.toggle()
        await self.wait_current('resummon_new_actor', lambda: self.actor is not None, timeout=self.args.timeout)
        new = self.actor.ref.uid
        self.record('living_resummon_fresh_uid', new != old and self.world.entities.resolve(ref) is None and
            bool(self.frames(marker, 0x4e96, **{'2': new, '16': 1})), old_uid=old, new_uid=new)

    async def target(self, *, odd=False, strong=False, weak=False, stop_on_member_death=False):
        until = time.monotonic() + self.args.navigation_timeout
        while time.monotonic() < until:
            if stop_on_member_death and not self.member.alive:
                return None
            candidates = []
            for uid, actor in self.bot.actors.items():
                entity = self.world.entities.get(uid)
                if not actor['alive'] or entity is None or self.manager.get_actor(uid) is not None:
                    continue
                monster = self.bot.data.monsters.get(entity.template_id)
                if (monster is None or (odd and monster.kill_exp % 2 != 1)
                        or (strong and monster.hp < 40) or (weak and monster.hp > 6)):
                    continue
                if (monster.level > (self.bot.level or 1) + 3
                        or not self.bot.safe_hunt_cell(actor['position'])):
                    continue  # navigation uses these same existing safety rules
                candidates.append((monster.hp if odd else 0,
                    hb.distance(self.bot.position, actor['position']), uid, actor))
            if candidates:
                _, _, uid, actor = min(candidates)
                goal = actor['position']
                await self.navigate(goal, radius=1,
                    predicate=(lambda: not self.member.alive or
                        hb.distance(self.bot.position, goal) <= 1)
                        if stop_on_member_death else None)
                if stop_on_member_death and not self.member.alive:
                    return None
                current = self.bot.actors.get(uid)
                if current and current['alive'] and hb.distance(self.bot.position, current['position']) <= 1:
                    return uid
            else:
                groups = [g for g in self.bot.data.spawns if
                    g.map_id == self.bot.map_id and
                    self.bot.data.monsters[g.template_id].level <= (self.bot.level or 1) + 3 and
                    (not odd or self.bot.data.monsters[g.template_id].kill_exp % 2 == 1) and
                    (not strong or self.bot.data.monsters[g.template_id].hp >= 40) and
                    (not weak or self.bot.data.monsters[g.template_id].hp <= 6)]
                if not groups:
                    raise hs.Unconfirmed('NATURAL_TARGET_GROUP_REQUIRED')
                group = min(groups, key=lambda g: (
                    self.bot.data.monsters[g.template_id].hp if odd else 0,
                    hb.distance(self.bot.position, (g.rect.x1, g.rect.y2))))
                await self.bot.step(((group.rect.x1 + group.rect.x2)//2, (group.rect.y1 + group.rect.y2)//2), radius=2)
            await self.tick_wait(.1)
        raise hs.Unconfirmed('CURRENT_NATURAL_TARGET_REQUIRED')

    async def exp(self):
        self.stage = 'odd_exp'
        await self.command(2)
        seen = set()
        kill_ids = set()
        for index in range(2):
            target = await self.target(odd=True)
            # A fresh world runtime may reuse a numeric UID after normal close.
            # Keep target identity scoped to its current connected broker epoch.
            target_key = (len(self.bots), target)
            entity = self.world.entities.get(target)
            amount = self.bot.data.monsters[entity.template_id].kill_exp
            before_owner = self.world.exp[self.bot.self_uid]
            before_member = self.member.exp
            owner_half = self.world.companion_owner_half[self.bot.self_uid]
            member_half = self.member.exp_half
            if index == 0 and (owner_half != 0 or member_half != 0):
                raise hs.Unconfirmed('FRESH_ZERO_HALF_START_REQUIRED_NO_RESET')
            receipts = len(self.world.companion_reward_receipts)
            marker = await self.command(1, target)
            member_uid = self.actor.ref.uid
            await self.wait_current('companion_first_odd_target_swing', lambda:
                bool(self.frames(marker, 0x4e31, **{'2': member_uid, '3': target})),
                member_required=True, marker=marker, target_uid=target)
            # An actual companion swing establishes participation. The owner
            # then attacks through the normal cadence until the natural kill;
            # the contract does not require an unsupported solo pet kill.
            until = time.monotonic() + self.args.death_timeout
            while len(self.world.companion_reward_receipts) <= receipts:
                self.require_living_member('odd_target_owner_finish', marker, target)
                if time.monotonic() >= until:
                    raise hs.Unconfirmed('NATURAL_ODD_KILL_DEADLINE')
                await self.owner_attack_current(target)
                await self.tick_wait(.05)
            reward = self.world.companion_reward_receipts[-1]
            owner_gain, expected_owner_half = half_share(amount, owner_half)
            member_gain, expected_member_half = half_share(amount, member_half)
            self.record('odd_kill_50_50_carry_' + str(index + 1),
                self.world.exp[self.bot.self_uid] - before_owner == owner_gain and
                self.member.exp - before_member == member_gain and
                self.world.companion_owner_half[self.bot.self_uid] == expected_owner_half and
                self.member.exp_half == expected_member_half and target_key not in seen and
                reward.get('target_uid') == target and reward.get('joint_commit_count') == 1 and
                reward.get('durable') is True and reward.get('kill_id') not in kill_ids and
                bool(self.frames(marker, 0x4e31, **{'2': self.actor.ref.uid, '3': target})),
                target_uid=target, kill_exp=amount, owner_exp_gain=owner_gain,
                member_exp_gain=member_gain, owner_half=expected_owner_half, member_half=expected_member_half,
                actual_receipt=reward)
            seen.add(target_key)
            kill_ids.add(reward['kill_id'])
            if index == 0:
                # Preserve a real nonzero 0.5 ledger through normal logout and
                # FIRST/relogin before the next odd kill consumes its carry.
                before = dataclasses.asdict(self.member)
                character = self.bot.character
                path, owner_uid = self.broker._companion_store.path, self.bot.self_uid
                if not await self.close():
                    raise hs.Unconfirmed('ODD_HALF_EPOCH_CLOSE_FAILED')
                self.check_saved(path, owner_uid, before, before_owner + owner_gain, 1,
                                 'odd_half_joint_file_saved')
                await self.open(seed=False, character=character)
                self.record('odd_half_saved_across_relogin',
                    dataclasses.asdict(self.member) == before and self.actor is not None and
                    self.member.exp_half == 1 and self.world.companion_owner_half[self.bot.self_uid] == 1 and
                    self.world.exp[self.bot.self_uid] == before_owner + owner_gain,
                    member_half=self.member.exp_half, owner_half=self.world.companion_owner_half[self.bot.self_uid])

    async def owner_attack_current(self, target):
        """Follow the last received target and use an admitted melee LOS tile.

        This is navigation only: movement/attacks still use the socket. The
        existing static terrain is read, never changed, and all server admission
        and attack cadence remain in force.
        """
        from tools.local_original_session.npc_ai import DELTAS, local_line_clear
        actor = self.bot.actors.get(target)
        if actor is None or not actor['alive']:
            return
        tx, ty = actor['position']
        px, py = self.bot.position
        if hb.distance((px, py), (tx, ty)) > 1:
            await self.bot.step((tx, ty), radius=1)
            return
        terrain, map_id = self.world.terrain, self.bot.map_id
        if not local_line_clear(terrain, map_id, px, py, tx, ty):
            candidates = [(tx + dx, ty + dy) for dx, dy in DELTAS
                if terrain.can_stand(map_id, tx + dx, ty + dy) is True
                and local_line_clear(terrain, map_id, tx + dx, ty + dy, tx, ty)
                and not any(e.kind.value != 'item' for e in self.world.entities.near(
                    map_id, tx + dx, ty + dy, 0))]
            if not candidates:
                raise hs.Unconfirmed('OWNER_MELEE_LOS_TILE_UNAVAILABLE')
            await self.bot.step(min(candidates, key=lambda p: hb.distance((px, py), p)))
            return
        await self.bot.attack(target)

    async def combat_death(self, *, repeated=False):
        if repeated:
            # Revival restores a quarter HP, not a fresh full-health fixture.
            # Observe a real second death even if it happens en route; do not
            # query/control the corpse as though the first combat were reset.
            self.stage = 'natural_repeat_companion_death'
            marker, ref = self.bot.peer.ordinal, self.actor.ref
            until = time.monotonic() + self.args.death_timeout
            while self.member.alive:
                if time.monotonic() >= until:
                    raise hs.Unconfirmed('NATURAL_REPEAT_COMPANION_DEATH_DEADLINE')
                target = await self.target(strong=True, stop_on_member_death=True)
                if not self.member.alive:
                    break
                await self.owner_attack_current(target)
                await self.tick_wait(.2)
            corpse = self.world.entities.get(ref.uid)
            if corpse is not None:
                await self.navigate((corpse.x, corpse.y), radius=2)
            self.record('repeat_death_uses_actual_incoming_and_invalidates_ref',
                self.member.hp == 0 and self.world.entities.resolve(ref) is None
                and bool(self.frames(marker, 0x4e31, **{'3': ref.uid})))
            await self.check_corpse(marker, ref.uid)
            return
        self.stage = 'defend_assist_incoming_death'
        target = await self.target(strong=True)
        await self.command(3)
        self.record('LOCAL_defend_follow_consumed', self.member.combat_mode == 'DEFEND' and self.member.movement_mode == 'FOLLOW')
        marker, member_uid = self.bot.peer.ordinal, self.actor.ref.uid
        # One owner attack legitimately provokes the monster. DEFEND must wait
        # for its incoming attack, then generate its own companion swing.
        await self.wait_current('owner_attack_cadence', lambda: time.monotonic() >= self.bot.next_attack,
                                timeout=self.args.timeout)
        await self.wait_current('owner_actual_defend_trigger', lambda:
            bool(self.frames(marker, 0x4e31, **{'2': self.bot.self_uid, '3': target})),
            timeout=20, action=lambda: self.owner_attack_current(target))
        await self.wait_current('defend_after_owner_incoming', lambda:
            bool(self.frames(marker, 0x4e31, **{'2': target, '3': self.bot.self_uid})) and
            bool(self.frames(marker, 0x4e31, **{'2': member_uid, '3': target})))
        incoming = self.frames(marker, 0x4e31, **{'2': target, '3': self.bot.self_uid})
        defended = self.frames(marker, 0x4e31, **{'2': member_uid, '3': target})
        self.record('defend_follows_actual_owner_incoming', defended[0].ordinal > incoming[0].ordinal,
            incoming_ordinal=incoming[0].ordinal, companion_ordinal=defended[0].ordinal)
        await self.command(2)
        marker = self.bot.peer.ordinal
        await self.wait_current('assist_owner_attack_cadence', lambda: time.monotonic() >= self.bot.next_attack,
                                timeout=self.args.timeout)
        await self.wait_current('owner_actual_assist_trigger', lambda:
            bool(self.frames(marker, 0x4e31, **{'2': self.bot.self_uid, '3': target})),
            timeout=20, action=lambda: self.owner_attack_current(target))
        await self.wait_current('assist_owner_then_companion', lambda:
            bool(self.frames(marker, 0x4e31, **{'2': self.bot.self_uid, '3': target})) and
            bool(self.frames(marker, 0x4e31, **{'2': member_uid, '3': target})))
        owner = self.frames(marker, 0x4e31, **{'2': self.bot.self_uid, '3': target})
        companion = self.frames(marker, 0x4e31, **{'2': member_uid, '3': target})
        self.record('assist_same_target_after_owner', companion[0].ordinal > owner[0].ordinal,
            owner_ordinal=owner[0].ordinal, companion_ordinal=companion[0].ordinal)
        hp, ref = self.member.hp, self.actor.ref
        marker = self.bot.peer.ordinal
        await self.command(4)
        await self.wait_current('natural_companion_hp_decrease', lambda: self.member.hp < hp)
        self.record('incoming_changes_only_companion_ledger', self.member.hp < hp and
            bool(self.frames(marker, 0x4e31, **{'2': target, '3': member_uid})),
            hp_before=hp, hp_after=self.member.hp)
        await self.wait_current('natural_companion_death', lambda: not self.member.alive)
        actor = self.actor
        brains = self.world.ai.brains.values() if self.world.ai is not None else ()
        self.record('death_invalidates_ref_cancels_ai_releases_monster', self.member.hp == 0 and
            self.world.entities.resolve(ref) is None and (actor is None or actor.handle is None and actor.target is None) and
            not any(brain.target == member_uid for brain in brains), hp=self.member.hp, dead_uid=member_uid)
        await self.check_corpse(marker, member_uid)

    async def check_corpse(self, marker, member_uid):
        await self.wait_current('received_member_death_action', lambda:
            bool(self.frames(marker, 0x4e39, **{'1': member_uid, '2': 8})))
        stop_marker = self.bot.peer.ordinal
        mp = self.member.mp
        await self.tick_wait(1.2)
        self.record('death_corpse_retained_and_actions_stopped', self.actor is not None and
            self.actor.action == 'DEAD' and self.actor.handle is None and self.member.mp == mp and
            not self.frames(stop_marker, 0x4e2c, **{'1': member_uid}) and
            not self.frames(stop_marker, 0x4e31, **{'2': member_uid}) and
            not self.frames(marker, 0x4e40, **{'1': member_uid}), member_uid=member_uid)

    def resurrection_scroll(self):
        choices = [(uid, row) for uid, row in self.bot.inventory.items()
                   if row.get(2) == 28 and row.get(4, 0) > 0]
        if not choices:
            raise hs.Unconfirmed('RECEIVED_RESURRECTION_SCROLL_UID_REQUIRED')
        return min(choices)

    async def revive(self):
        self.stage = 'targeted_resurrection_scroll'
        before = dataclasses.asdict(self.member)
        actor, ref = self.actor, None if self.actor is None else self.actor.ref
        if actor is None or self.member.alive:
            raise hs.Unconfirmed('CURRENT_DEAD_OWNED_COMPANION_TARGET_REQUIRED')
        scroll_uid, scroll = self.resurrection_scroll()
        quantity = scroll[4]
        position = None if actor is None else self.world.entities.get(ref.uid)
        pose = None if position is None else (position.map_id, position.x, position.y)
        marker = self.bot.peer.ordinal
        from tools.local_original_session import inventory
        bags = self.broker._companion_inventory
        def healing_quantity():
            return sum(dict(row.raw_fields)[4] for row in inventory.validate_kit_frame(
                bags.frames[self.member_id]) if row.template_bits == 14)
        healing_before = healing_quantity()
        requested_at = time.monotonic()
        # run393: use UID outerf1, target UID nestedf2:int64 (not ZigZag).
        params = b''.join(hb.uint(n, value) for n, value in
            ((1, 1), (2, ref.uid), (3, 0), (15, 0), (16, 0)))
        await self.bot.peer.request(0x0960, hb.uint(1, scroll_uid) + hb.pb.encode_bytes(2, params),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='COMPANION_SCROLL_ALIVE')
        await self.wait_current('targeted_scroll_revived_member', lambda: self.member.alive and self.actor is not None)
        entity = self.world.entities.resolve(self.actor.ref)
        opcode = 0x4f16 if self.args.companion_revive_exp else 0x4e96
        field = '1' if opcode == 0x4f16 else '2'
        await self.wait_current('revive_display_received', lambda:
            bool(self.frames(marker, opcode, **{field: self.actor.ref.uid})))
        await self.wait_current('resurrection_scroll_cost_received', lambda:
            self.bot.inventory.get(scroll_uid, {}).get(4, 0) == quantity - 1)
        # The normal AI can drink its own potion before the display/cost reaches
        # the peer. Its existing consumption events retain the exact revived HP.
        healing = [dict(event) for event in bags.events
                   if event['character_id'] == self.member_id and event['at'] >= requested_at]
        revived_hp = healing[0]['hp_before'] if healing else self.member.hp
        observed_hp, healing_valid = revived_hp, True
        low, high = self.world.data.items[14].heal_hp_range
        for event in healing:
            healing_valid = healing_valid and (event['template'] == 14
                and event['hp_before'] == observed_hp
                and event['mp_before'] == event['mp_after'] == before['mp']
                and min(self.member.max_hp, observed_hp + low) <= event['hp_after']
                    <= min(self.member.max_hp, observed_hp + high))
            observed_hp = event['hp_after']
        healing_valid = (healing_valid and observed_hp == self.member.hp
                         and healing_before - healing_quantity() == len(healing))
        self.record('targeted_scroll_revive_retained',
            revived_hp == max(1, self.member.max_hp // 4) and healing_valid and self.member.mp == before['mp'] and
            all(dataclasses.asdict(self.member)[k] == before[k] for k in PERSISTENT_FIELDS if k not in ('hp', 'alive')) and
            self.actor.ref.uid == ref.uid and self.actor.ref != ref and
            self.world.entities.resolve(ref) is None and (entity.map_id, entity.x, entity.y) == pose,
            opcode=hex(opcode), member_uid=self.actor.ref.uid, hp=self.member.hp, mp=self.member.mp,
            revived_hp=revived_hp, healing_events=healing,
            healing_quantity_before=healing_before, healing_quantity_after=healing_quantity(),
            scroll_uid=scroll_uid, quantity_before=quantity, quantity_after=quantity - 1,
            policy='LOCAL normal L1J40089 NPC/pet HP=max(1,maxHP//4), unchanged MP; owned visible corpse only')
        await self.command(2)
        start = self.member_position()
        # This observation needs a real follow step, not arrival at an arbitrary
        # south tile. waxmra5i revived successfully, then the terrain-blind bot
        # wandered/retried that fixed tile for 180s (132 corrections). Reuse the
        # existing bounded terrain/occupancy search for this short separation;
        # movement still goes through bot.step's normal wire/Alive/correction.
        from tools.local_original_session.npc_ai import bounded_path_step, DELTAS
        bot, terrain, map_id = self.bot, self.world.terrain, self.bot.map_id
        hint = (bot.position[0], bot.position[1] + 4)
        previous_heading = bot.heading
        def follow_heading(_goal, _radius):
            now = time.monotonic()
            occupied = {(e.x, e.y) for e in self.world.entities.near(map_id,
                *bot.position, 16) if e.uid != bot.self_uid and e.kind.value != 'item'}
            def can_step(x, y, heading):
                dx, dy = DELTAS[heading]
                point = (x + dx, y + dy)
                return (terrain.can_step(map_id, x, y, heading) is True
                    and point not in occupied and bot.safe_hunt_cell(point)
                    and bot.blocked_edges.get(((x, y), heading), 0) <= now)
            return bounded_path_step(bot.position,
                lambda x, y: hb.distance((x, y), start) >= 4, hint, can_step)
        bot.heading = follow_heading
        try:
            await self.wait_current('revived_member_follows', lambda: self.member_position() != start,
                timeout=15, member_required=True, marker=marker,
                action=lambda: bot.step(hint))
        finally:
            bot.heading = previous_heading
        self.record('revived_member_follows', self.actor.handle is not None and
            bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})))
        target = await self.target(weak=True)
        marker = await self.command(1, target)
        await self.wait_current('revived_member_attacks', lambda:
            bool(self.frames(marker, 0x4e31, **{'2': self.actor.ref.uid, '3': target})),
            member_required=True, marker=marker, target_uid=target)
        self.record('revived_member_attacks', self.member.alive and
            bool(self.frames(marker, 0x4e31, **{'2': self.actor.ref.uid, '3': target})))
        # The next stage navigates to another spawn group. Keep the member
        # following so its native pet query still refers to a visible actor.
        await self.command(2)

    async def death_revive(self):
        await self.summon()
        await self.combat_death()
        await self.revive()
        # A second ordinary combat death proves logout does not grant revival.
        await self.combat_death(repeated=True)
        await self.reconnect()
        await self.revive()

    async def teleport_scroll(self, template):
        self.stage = ('living_' if self.member.alive else 'corpse_') + str(template)
        choices = [(uid, item) for uid, item in self.bot.inventory.items()
                   if item.get(2) == template and item.get(4, 0) > 0]
        if not choices:
            raise hs.Unconfirmed('RECEIVED_TRAVEL_SCROLL_REQUIRED:' + str(template))
        uid, item = min(choices)
        old, quantity = self.actor, item[4]
        old_ref, marker = old.ref, self.bot.peer.ordinal
        saved = dataclasses.asdict(self.member)
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        await self.bot.peer.request(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
            alive=True, check=lambda batch: hb.find(batch, 0x4ee0), label='COMPANION_TRAVEL_SCROLL')
        await self.wait_current('travel_member_spawn_received', lambda: self.actor is not None and
            self.actor.ref != old_ref and bool(self.frames(marker, 0x4e96, **{'2': self.actor.ref.uid})),
            timeout=self.args.timeout)
        actor = self.actor
        entity = self.world.entities.get(actor.ref.uid)
        remove = self.frames(marker, 0x4e40, **{'1': old_ref.uid})
        correction = self.frames(marker, 0x4ee0)
        spawn = self.frames(marker, 0x4e96, **{'2': actor.ref.uid})
        self.record(self.stage + '_travels_with_owner',
            bool(remove and correction and spawn and remove[0].ordinal < correction[0].ordinal < spawn[0].ordinal)
            and entity.map_id == self.bot.map_id and hb.distance((entity.x, entity.y), self.bot.position) <= 1
            and self.world.entities.get(old_ref.uid) is None and old.handle is None and old.target is None
            and actor.target is None and self.bot.inventory.get(uid, {}).get(4, 0) == quantity - 1,
            member_uid=actor.ref.uid, destination=self.bot.position,
            removed=remove[0].ordinal if remove else None, spawned=spawn[0].ordinal if spawn else None)
        self.record(self.stage + '_preserves_life_resources',
            all(dataclasses.asdict(self.member)[key] == saved[key] for key in PERSISTENT_FIELDS))
        if not self.member.alive:
            await self.wait_current('travel_corpse_death_received', lambda:
                bool(self.frames(marker, 0x4e39, **{'1': actor.ref.uid, '2': 8})), timeout=self.args.timeout)
            death = self.frames(marker, 0x4e39, **{'1': actor.ref.uid, '2': 8})[0]
            self.record('teleported_corpse_spawn_then_death', spawn[0].ordinal < death.ordinal and
                self.member.hp == 0 and actor.handle is None)

    async def travel(self):
        await self.summon()
        await self.teleport_scroll(162)
        await self.teleport_scroll(23)
        await self.teleport_scroll(162)
        await self.combat_death()
        await self.teleport_scroll(23)
        await self.teleport_scroll(162)
        await self.reconnect()
        await self.revive()

    async def map_travel(self):
        self.stage = 'map_transition'
        await self.wait_current('map_member_visible', lambda: self.actor is not None,
                                timeout=self.args.timeout)
        saved, old_ref = dataclasses.asdict(self.member), self.actor.ref
        marker = self.bot.peer.ordinal
        await self.bot.step((32478, 32851))
        # Shared HuntBot predicts one ordinary step after Alive. A map change
        # instead has an authoritative destination self spawn in that batch.
        own = self.frames(marker, 0x4e96, **{'2': self.bot.self_uid})
        if own:
            self.bot.position = hb.unpack(hb.scalar(own[-1].values, 1))
        await self.wait_current('map1_owner_and_member', lambda: self.bot.map_id == 1 and
            self.actor is not None and self.actor.ref != old_ref and
            bool(self.frames(marker, 0x4e96, **{'2': self.actor.ref.uid})), timeout=self.args.timeout)
        entity = self.world.entities.get(self.actor.ref.uid)
        self.record('mapexp2_member_reappears_in_new_map', entity.map_id == 1 and
            hb.distance((entity.x, entity.y), self.bot.position) <= 1 and
            self.world.entities.get(old_ref.uid) is None and self.actor.target is None and
            all(dataclasses.asdict(self.member)[key] == saved[key] for key in PERSISTENT_FIELDS),
            alive=self.member.alive, map_id=entity.map_id, member_uid=entity.uid)
        if not self.member.alive:
            await self.wait_current('map1_corpse_death', lambda:
                bool(self.frames(marker, 0x4e39, **{'1': entity.uid, '2': 8})), timeout=self.args.timeout)
            self.record('mapexp2_corpse_remains_dead', self.member.hp == 0 and self.actor.handle is None)
        # MapExp2 enables cross-map publication; same-map companion travel
        # still uses the normal remove/correction/spawn sequence.
        await self.teleport_scroll(23)

    async def map_travel_dead(self):
        await self.map_travel()

    async def reconnect(self):
        self.stage = 'reconnect'
        saved = dataclasses.asdict(self.member)
        owner_half = self.world.companion_owner_half[self.bot.self_uid]
        owner_exp = self.world.exp[self.bot.self_uid]
        character = self.bot.character
        scrolls = {uid: r[4] for uid, r in self.bot.inventory.items() if r.get(2) == 28}
        path, owner_uid = self.broker._companion_store.path, self.bot.self_uid
        if not await self.close():
            raise hs.Unconfirmed('FIRST_EPOCH_CLOSE_FAILED_NO_RECONNECT')
        self.check_saved(path, owner_uid, saved, owner_exp, owner_half, 'dead_member_joint_file_saved')
        await self.open(seed=False, character=character)
        restored = dataclasses.asdict(self.member)
        self.record('normal_relogin_preserves_member_and_half', all(saved[key] == restored[key] for key in PERSISTENT_FIELDS) and
            self.world.companion_owner_half[self.bot.self_uid] == owner_half and
            self.world.exp[self.bot.self_uid] == owner_exp and self.actor is not None,
            member_exp=self.member.exp, member_half=self.member.exp_half,
            owner_exp=owner_exp, owner_half=owner_half, hp=self.member.hp, alive=self.member.alive)
        self.record('dead_member_no_free_resurrection', not self.member.alive and
            self.member.hp == 0 and self.actor is not None and self.actor.action == 'DEAD' and
            self.actor.handle is None)
        actor = self.actor
        await self.wait_current('relogin_corpse_death_received', lambda:
            bool(self.frames(0, 0x4e39, **{'1': actor.ref.uid, '2': 8})), timeout=self.args.timeout)
        spawn = self.frames(0, 0x4e96, **{'2': actor.ref.uid})
        death = self.frames(0, 0x4e39, **{'1': actor.ref.uid, '2': 8})
        entity = self.world.entities.get(actor.ref.uid)
        self.record('relogin_corpse_spawn_then_death_beside_owner', bool(spawn and death) and
            spawn[0].ordinal < death[0].ordinal and entity.map_id == self.bot.map_id and
            hb.distance((entity.x, entity.y), self.bot.position) <= 1)
        self.record('resurrection_scroll_cost_saved_across_relogin', scrolls ==
            {uid: r[4] for uid, r in self.bot.inventory.items() if r.get(2) == 28})

    async def magic(self):
        """One real socket epoch; wait for real MP recovery, never force time/HP."""
        self.stage = 'magic'
        magic = self.world.companion_ai.magic
        events = lambda name: [e for e in magic.events if e['spell'] == name]
        await self.wait_current('urgent_owner_heal', lambda: bool(events('heal')), timeout=35)
        heal = events('heal')[0]
        self.record('magic_urgent_heal_hp_status_and_mp_debit', heal['amount'] > 0 and
            heal['mp_before'] - heal['mp_after'] == 4 and
            bool(self.frames(0, 0x4e38, **{'1': self.bot.self_uid})) and
            bool(self.frames(0, 0x4ed8, **{'1': self.bot.self_uid, '2': 744})), actual=heal)
        await self.wait_current('self_shield_with_heal_reserve', lambda: bool(events('shield')), timeout=100)
        shield = events('shield')[0]
        self.record('magic_self_shield_effect_and_priority', shield['target'] == self.actor.ref.uid and
            shield['mp_before'] - shield['mp_after'] == 2 and shield['mp_after'] >= 8 and
            shield['at'] > heal['at'] and self.actor.shield_until > time.monotonic() and
            bool(self.frames(0, 0x4ed8, **{'1': self.actor.ref.uid, '2': 221})), actual=shield)
        target = await self.target(weak=True)
        marker = await self.command(1, target)
        await self.wait_current('magic_recover_or_first_attack', lambda:
            self.actor.action == 'RECOVER' or bool(events('energy_bolt')), timeout=20)
        # This fixture spends14 MP on real support first. Recovery preserves
        # reserve8 and resumes at T=max(11,ceil(.4*maxMP)); natural ticks only.
        recovering = self.actor.action == 'RECOVER'
        await self.wait_current('natural_mp_recovery_then_bolt', lambda: bool(events('energy_bolt')),
                                timeout=100)
        bolt = events('energy_bolt')[0]
        self.record('magic_bolt_after_recovery_real_target', bool(events('recover')) and
            bolt['target'] == target and bolt['amount'] > 0 and
            bolt['mp_before'] - bolt['mp_after'] == 3 and bolt['mp_after'] >= 8 and
            bool(self.frames(marker, 0x4e31, **{'1': 18, '2': self.actor.ref.uid, '3': target})),
            observed_recover_state=recovering, actual=bolt, recovery_events=events('recover'))
        # Continue using published, unprovoked monsters until actual offense
        # hits its MP reserve. Never lower live MP or fabricate a cast request.
        deadline = time.monotonic() + 60
        from tools.local_original_session.npc_ai import local_line_clear
        while self.actor.action != 'RECOVER':
            self.require_living_member('magic_consume_to_recover', marker, target)
            if time.monotonic() >= deadline:
                raise hs.Unconfirmed('NATURAL_RECOVER_STATE_REQUIRED')
            if self.actor.target is None:
                member_entity = self.world.entities.resolve(self.actor.ref)
                choices = []
                for uid, observed in self.bot.actors.items():
                    entity = self.world.entities.get(uid)
                    found = self.world.spawner.slot_for(uid)
                    if (observed['alive'] and entity is not None and found is not None and
                            0 < found[1].hp <= 6 and hb.distance(self.member_position(), observed['position']) <= 10 and
                            local_line_clear(self.world.terrain, entity.map_id, member_entity.x,
                                             member_entity.y, entity.x, entity.y)):
                        choices.append(uid)
                target = min(choices) if choices else await self.target(weak=True)
                await self.command(1, target)
            await self.tick_wait(.15)
        recovering_at, recovering_mp = time.monotonic(), self.member.mp
        before_count = len(events('energy_bolt'))
        self.record('magic_actual_recover_preserves_reserve', recovering_mp >= 8 and
            self.actor.target is not None, mp=recovering_mp, target=self.actor.target.uid)
        await self.wait_current('actual_recover_resumes_offense',
            lambda: len(events('energy_bolt')) > before_count, timeout=110,
            member_required=True, marker=marker, target_uid=target)
        resumed = events('energy_bolt')[-1]
        self.record('magic_actual_recover_then_resume', resumed['at'] >= recovering_at and
            resumed['mp_before'] >= max(11, math.ceil(.4 * self.member.max_mp)) and
            any(e['at'] >= recovering_at for e in events('recover')),
            mp_at_recover=recovering_mp, actual=resumed)
        await self.command(4)
        before = len(events('energy_bolt'))
        await self.tick_wait(1.2)
        self.record('magic_passive_cancels_offense_keeps_deadline',
            len(events('energy_bolt')) == before and self.actor.target is None)

    async def equipment_flow(self):
        """run406 real GIVE, own bag potions, reconnect and direct mage login."""
        from tools.local_original_session import inventory
        self.stage = 'equipment'
        await self.summon()
        await self.command(4)  # real pet-window barrier; keep fixture near owner
        bags = self.broker._companion_inventory
        uid = self.member_id
        async def give(template, count=1):
            await self.wait_current('owner_supply_' + str(template), lambda: any(
                r.get(2) == template and r.get(4, 0) >= count for r in self.bot.inventory.values()))
            item_uid = next(key for key, r in self.bot.inventory.items()
                if r.get(2) == template and r.get(4, 0) >= count)
            before = self.bot.inventory[item_uid][4]
            marker = self.bot.peer.ordinal
            # Peer marker is an ordinal; existing request waits for the actual
            # inventory debit notification before permitting the next action.
            try:
                await self.bot.peer.request(0x4ef5, hb.uint(1, self.actor.ref.uid)
                    + hb.uint(2, item_uid) + hb.uint(3, count),
                    check=lambda batch: next((f for f in batch if f.opcode in (0x0965, 0x0978)), None))
            except Exception:
                self.record('give_refusal_observed', None, errors=self.broker._companion_errors)
                raise
            self.record('give_' + str(template), self.bot.inventory.get(item_uid, {}).get(4, 0) == before - count,
                item_uid=item_uid, count=count)
            return marker
        initial_ac = self.world.companion_profiles[uid].ac
        marker = await give(230)
        state = bags.states[uid]
        by_uid = {r.identifier: r.template_bits for r in inventory.validate_kit_frame(bags.frames[uid])}
        self.record('received_staff_auto_equipped_saved_and_live_wield',
            by_uid[state.weapon_uid] == 230 and self.world.companion_looks[uid]['stance'] == 50
            and bool(self.frames(marker, 0x4ed5, **{'1': self.actor.ref.uid, '2': 50}))
            and bags.equipment.restore(uid, bags.frames[uid]) == state)
        await give(102)
        self.record('received_armour_changes_actual_companion_ac',
            self.world.companion_profiles[uid].ac < initial_ac,
            before=initial_ac, after=self.world.companion_profiles[uid].ac)
        await give(14, 5)
        await give(492, 2)
        await self.wait_current('own_bag_hp_and_mp_potions_consumed', lambda:
            {e['template'] for e in bags.events} >= {14, 492}, timeout=8)
        self.record('hp_potion_raises_hp_and_blue_potion_has_no_instant_mp',
            any(e['template'] == 14 and e['hp_after'] > e['hp_before'] for e in bags.events)
            and any(e['template'] == 492 and e['mp_after'] == e['mp_before'] for e in bags.events),
            events=bags.events)
        await self.wait_current('blue_potion_actual_recovery', lambda: self.member.mp > 0, timeout=45)
        before_frame = bags.frames[uid]
        before_state = bags.states[uid]
        owner = self.bot.character
        if not await self.close():
            raise hs.Unconfirmed('EQUIPMENT_FIRST_CLOSE_FAILED')
        await self.open(seed=False, character=owner)
        bags = self.broker._companion_inventory
        self.record('companion_bag_and_equipment_survive_reconnect',
            bags.frames[uid] == before_frame and bags.states[uid] == before_state)
        if not await self.close():
            raise hs.Unconfirmed('EQUIPMENT_SECOND_CLOSE_FAILED')
        await self.open(seed=False, character='SoloMage')
        actual = {r.identifier: dict(r.raw_fields) for r in inventory.validate_kit_frame(before_frame)
                  if dict(r.raw_fields)[4] > 0}
        observed = {key: value for key, value in self.bot.inventory.items() if value.get(4, 0) > 0}
        self.record('direct_mage_login_same_bag_and_equipment',
            self.bot.self_uid == uid and set(observed) == set(actual)
            and all(observed[key][2] == row[2] and observed[key][4] == row[4] for key, row in actual.items())
            and self.equipment.restore(uid, self.store.restore(uid)) == before_state
            and uid not in self.manager.active)

    async def selection(self):
        """Stored mage selection through the product route, with no profile edits.

        Each terminal Quit is followed by a new broker epoch. The retained
        transport does not admit another login after Quit.
        """
        from tools.local_original_session import inventory
        await self.summon()
        await self.command(4)
        owner = self.bot.character
        uid = self.member_id
        staff = next(key for key, row in self.bot.inventory.items()
                     if row.get(2) == 230 and row.get(4, 0) > 0)
        await self.bot.peer.request(0x4ef5, hb.uint(1, self.actor.ref.uid)
            + hb.uint(2, staff) + hb.uint(3, 1), check=lambda batch: next(
                (frame for frame in batch if frame.opcode in (0x0965, 0x0978)), None))
        before_frame = self.store.restore(uid)
        before_equipment = self.equipment.restore(uid, before_frame)
        before_level = self.member.level

        def capture_bag():
            nonlocal before_frame, before_equipment
            # Movement may legitimately consume a received potion. Compare the
            # saved result of that action at the next selection boundary.
            before_frame = self.store.restore(uid)
            before_equipment = self.equipment.restore(uid, before_frame)

        def check_mage(label):
            actual = {item.identifier: dict(item.raw_fields) for item in
                      inventory.validate_kit_frame(before_frame) if dict(item.raw_fields)[4] > 0}
            observed = {key: row for key, row in self.bot.inventory.items() if row.get(4, 0) > 0}
            state = self.world.combat.pcs.get(uid)
            appearances = self.frames(0, 0x4e96, **{'2': uid})
            self.record(label, self.bot.self_uid == uid and self.bot.level == before_level
                and set(actual) == set(observed) and all(observed[key][2] == row[2]
                    and observed[key][4] == row[4] for key, row in actual.items())
                and self.equipment.restore(uid, self.store.restore(uid)) == before_equipment
                and state is not None and state.profile.character_class == 3
                and state.profile.level == before_level and state.hp == self.member.hp
                and state.mp == self.member.mp and state.max_hp == self.member.max_hp
                and state.max_mp == self.member.max_mp and uid not in self.manager.active
                and bool(appearances) and hb.scalar(appearances[-1].values, 3) == 734,
                character_uid=uid, level=before_level, hp=self.member.hp, mp=self.member.mp)

        async def move_mage(label):
            start, moves = self.bot.position, self.bot.moves
            # Choose one currently clear, unoccupied adjacent tile through the
            # same terrain-aware navigation used by the travel scenarios.
            goals = [(start[0] + dx, start[1] + dy) for dx, dy in hb.DELTAS]
            goal = next((point for heading, point in enumerate(goals)
                         if self.travel_heading(point, 0) == heading), None)
            if goal is None:
                raise hs.Unconfirmed('SELECTED_MAGE_PASSABLE_NEIGHBOR_UNSUPPLIED')
            await self.navigate(goal)
            self.record(label, self.bot.position != start and self.bot.moves > moves,
                        start=start, finish=self.bot.position)

        if not await self.close():
            raise hs.Unconfirmed('SELECTION_KNIGHT_QUIT_CLOSE_FAILED')
        capture_bag()
        self.stage = 'quit_broker_restart_selection'
        await self.open(seed=False, character='SoloMage')
        check_mage('quit_restart_mage_bag_equipment_level_class_vitals')
        await move_mage('quit_restart_selected_mage_moves')
        capture_bag()
        if not await self.close():
            raise hs.Unconfirmed('SELECTION_MAGE_QUIT_CLOSE_FAILED')
        capture_bag()
        await self.open(seed=False, character=owner)
        await self.wait_current('quit_restart_member_restored', lambda: self.actor is not None)
        await self.resummon()
        self.record('quit_restart_knight_resummons_saved_mage',
            self.member.level == before_level and self.store.restore(uid) == before_frame
            and self.equipment.restore(uid, before_frame) == before_equipment
            and not self.broker.failure.is_set())

    async def all(self):
        await self.summon()
        await self.follow_hold()
        await self.resummon()
        await self.exp()
        await self.combat_death()
        await self.revive()
        await self.combat_death(repeated=True)
        await self.teleport_scroll(23)
        await self.teleport_scroll(162)
        await self.reconnect()
        await self.revive()
        await self.selection()


def parser():
    result = hs.parser()
    result.description = __doc__
    # Existing harness options are retained, but only the complete companion
    # lifecycle is an executable scenario in this module.
    next(action for action in result._actions if action.dest == 'scenario').choices = (
        'all', 'magic', 'death_revive', 'travel', 'map_travel', 'map_travel_dead', 'equipment', 'selection')
    result.add_argument('--companion-revive-exp', action='store_true',
                        help='run404 experimental 4F16 in-place restore; default same-UID 4E96 replacement')
    result.add_argument('--fixture-level', type=int, choices=(1, 5), default=5,
                        help='pre-login mage fixture level; LOCAL pure growth from baseline HP12/MP8')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work' / 'local_original_session' / 'runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-companion-', dir=root))
    with test_environment(magic=args.scenario == 'magic', revive_exp=args.companion_revive_exp,
                          map_exp=args.scenario in ('map_travel', 'map_travel_dead')):
        scenario = CompanionScenario(args, directory)
        result = await scenario.run()
    result['scope'] = ('owned test profile, real FIRST/login/selection/socket router; LOCAL companion modes/reward, '
        'experimental run400 pet wire; native input/rendering unverified')
    result['fixture'] = dict(owner=scenario.owner_fixture, mage=scenario.fixture_growth,
        scope='fresh pre-login ProgressStore initialization; no live HP or clock forcing')
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.potion_threshold > 1:
        cli.error('--potion-threshold must be in (0, 1]')
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
