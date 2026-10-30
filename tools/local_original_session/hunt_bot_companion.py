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
import os
from pathlib import Path
import random
import tempfile
import time
import traceback
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
def test_environment(*, magic=False, revive_exp=False, map_exp=False, bridge_directory=None):
    keys = ('SL_COMPANION', 'SL_COMPANION_PET_UI', 'SL_SPELL_EXP', 'SL_COMPANION_REVIVE_EXP',
            'SL_EXPERIMENT_MAP', 'SL_COMPANION_BRIDGE_DIR')
    old = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            if key == 'SL_COMPANION_BRIDGE_DIR':
                if bridge_directory is not None:
                    os.environ[key] = str(bridge_directory)
                continue
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
        self.owner_vitals = None     # pre-login owner HP fixture (owner_death)
        self.enable_settings = False  # explicit settings store for the ATS epochs
        self.view_epochs = {}
        self.bridge_sequence = 0

    def record(self, name, ok, **evidence):
        if name == 'scenario_execution' and ok is False:
            traceback.print_exc()
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
        self.view_epochs.clear()
        expected = str(uuid.uuid4())
        self.broker, self.store, self.equipment = await hs.build_epoch(self.directory, expected, seed=seed)
        if seed:
            self.initialize_mage_fixture()
        if self.owner_vitals is not None:
            owner = next(r['uid'] for r in self.broker.realm.store._read()['characters'] if r['class'] == 1)
            self.broker._world.combat.vitals[owner] = self.owner_vitals
        if self.enable_settings:
            from tools.local_original_session import settings
            # One fixed store identity across this scenario's epochs.
            self.settings_uuid = getattr(self, 'settings_uuid', None) or str(uuid.uuid4())
            self.broker.realm.settings = settings.SettingsStore(self.directory / 'account-settings.bin',
                self.settings_uuid, profile_path=self.directory / 'characters.json')
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
            if frame.opcode in (0x4f14, 0x4ed8, 0x4f16, 0x4ed5, 0x4eea):
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
        level = 30 if self.args.scenario == 'elemental' else self.args.fixture_level
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
        owner_level = 30 if self.args.scenario == 'elemental' else 6
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
        if self.args.scenario == 'elemental':
            from tools.local_original_session import inventory, movement
            from tools.local_original_session.hunt_bot_spawn_audit import start_cell
            group = next(g for g in data.spawns if g.group_id == 'population_m1_0_7')
            map_id, x, y = start_cell(self.world.terrain, 0, group.rect)
            current = self.broker.realm.positions.restore(movement.Position(
                owner['uid'], owner['name'], map_id, x, y))
            self.broker.realm.positions.commit(current, movement.Position(
                current.uid, current.name, map_id, x, y))
            rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.store.restore(owner['uid']))]
            for template in (501, 3937):
                item = dict(rows[0])
                item.update({1: max(r[1] for r in rows) + 1, 2: template, 4: 1,
                             7: data.items[template].icon, 18: b''})
                rows.append(item)
            self.store.replace_kit(owner['uid'], self.store.restore(owner['uid']),
                                   inventory.build_kit_frame(rows), append=True)
            self.broker._inventory_current_frame = self.store.restore(owner['uid'])
            self.fixture_growth.update(elemental_supplies=[501, 3937],
                source='owned fresh pre-login bag fixture; GIVE/equipment through real router',
                initial_position=[map_id, x, y])
        if self.args.scenario in ('ats_edit', 'ats_window'):
            from tools.local_original_session.world_companion import CompanionRecord
            # Fresh pre-login learned list so the owner's spell-window swap is observable.
            member = CompanionRecord(uid, owner['uid'], 'owned-local-test', level=level, exp=exp,
                hp=calculated.max_hp, max_hp=calculated.max_hp, mp=calculated.max_mp,
                max_mp=calculated.max_mp, learned_spells=(0, 2, 3))
            self.broker._companion_store.payload['records'] = [dataclasses.asdict(member)]
            self.fixture_growth.update(learned_spells=[0, 2, 3], learning_scope='explicit fresh pre-login fixture')
            if self.args.scenario == 'ats_window':
                from tools.local_original_session.world_magic import MagicStore
                # The current learning hook reads MagicStore, not the roster's
                # historical learned_spells copy. Initialize before FIRST only.
                MagicStore(self.store).save(dict(uid=uid, learned=[0, 2, 3], buffs=[],
                    reuse_remaining=0, saved_at=time.time()))
                self.fixture_growth['learning_store'] = 'fresh pre-login magic.json via MagicStore.save'
        if self.args.scenario == 'magic':
            from tools.local_original_session.world_companion import CompanionRecord
            from tools.local_original_session.world_magic import MagicStore
            if level < 4:
                raise ValueError('MAGIC_FIXTURE_LEARN_LEVEL4_REQUIRED')
            # Explicit fresh pre-login learning/resources fixture; product never
            # grants spells merely because they exist in a reference catalog.
            member = CompanionRecord(uid, owner['uid'], 'owned-local-test', level=level,
                exp=exp, hp=calculated.max_hp, max_hp=calculated.max_hp,
                mp=calculated.max_mp, max_mp=calculated.max_mp, learned_spells=(0, 2, 3),
                equipment={'weapon_template': 230})
            self.broker._companion_store.payload['records'] = [dataclasses.asdict(member)]
            # The registered learning authority reads this existing ordinary
            # character store; a CompanionRecord projection grants no spells.
            MagicStore(self.store).save(dict(uid=uid, learned=[0, 2, 3], buffs=[],
                reuse_remaining=0, saved_at=time.time()))
            initial_hp = max(1, int(owner_growth.max_hp * .3))
            self.broker._world.combat.vitals[owner['uid']] = initial_hp
            self.owner_fixture['initial_current_hp'] = initial_hp
            self.fixture_growth.update(initial_current_mp=calculated.max_mp, learned_spells=[0, 2, 3],
                learning_scope='explicit fresh pre-login LOCAL scenario fixture',
                learning_store='magic.json via MagicStore.save before FIRST')

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
        bot = self.bot
        if (not bot.dead and bot.hp is not None
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
        from tools.local_original_session.world_feature_companion import TOKEN_TEMPLATE
        token_counts = {uid: row[4] for uid, row in self.bot.inventory.items()
                        if row.get(2) == TOKEN_TEMPLATE}
        ref, marker = self.actor.ref, self.bot.peer.ordinal
        await self.toggle()
        self.record('living_call_same_actor_beside_owner_permanent_item',
            self.actor.ref == ref and hb.distance(self.member_position(), self.bot.position) <= 1
            and self.member.movement_mode == 'HOLD' and self.member.combat_mode == 'PASSIVE'
            and token_counts == {uid: row[4] for uid, row in self.bot.inventory.items()
                                 if row.get(2) == TOKEN_TEMPLATE}
            and bool(self.frames(marker, 0x4e40, **{'1': ref.uid}))
            and bool(self.frames(marker, 0x4e96, **{'2': ref.uid, '16': 1})),
            member_uid=ref.uid, position=self.member_position())
        await self.command(2)

    async def toggle(self):
        # Product publishes the actual native etc-item UID. LOCAL summon/call
        # behavior is permanent and does not toggle dismissal.
        from tools.local_original_session.world_feature_companion import TOKEN_TEMPLATE
        choices = [(uid, row) for uid, row in self.bot.inventory.items() if
                   row.get(2) == TOKEN_TEMPLATE and row.get(4, 0) > 0]
        if not choices:
            raise hs.Unconfirmed('RECEIVED_COMPANION_SUMMON_ITEM_UID_REQUIRED')
        uid, _ = min(choices)
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        return await self.bot.peer.request(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
            alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='COMPANION_SUMMON_ALIVE')

    async def resummon(self):
        # COMPANION_DESIGN_DECISION: no dismissal. The legacy mode-8 request
        # must leave the same living actor in place.
        self.stage = 'dismiss_ignored'
        old, ref = self.actor.ref.uid, self.actor.ref
        marker = await self.command(8)
        self.record('dismiss_request_keeps_actor', self.actor is not None and self.actor.ref.uid == old
            and self.world.entities.resolve(ref) is not None
            and not self.frames(marker, 0x4e40, **{'1': old}), old_uid=old)

    async def target(self, *, odd=False, strong=False, weak=False, stop_on_member_death=False):
        until = time.monotonic() + self.args.navigation_timeout
        while time.monotonic() < until:
            if stop_on_member_death and not self.member.alive:
                return None
            if await self.bot.retreat_threat():
                await self.tick_wait(.1)
                continue
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
                if (hb.distance(self.bot.position, actor['position']) > 1
                        and self.travel_heading(actor['position'], 1) is None):
                    continue  # current terrain/occupancy cannot approach this target
                candidates.append((monster.hp if odd else 0,
                    hb.distance(self.bot.position, actor['position']), uid, actor))
            if candidates:
                _, _, uid, actor = min(candidates)
                goal = actor['position']
                # Monsters move/die while this request is in flight. Take one
                # ordinary guarded packet step, then reselect from the current
                # received actors instead of chasing a fixed position snapshot.
                if hb.distance(self.bot.position, goal) > 1:
                    await self.bot.step(goal, radius=1)
                if stop_on_member_death and not self.member.alive:
                    return None
                current = self.bot.actors.get(uid)
                if current and current['alive'] and hb.distance(self.bot.position, current['position']) <= 1:
                    return uid
            else:
                groups = [g for g in self.bot.data.spawns if
                    g.map_id == self.bot.map_id and
                    self.bot.data.monsters[g.template_id].level <= (self.bot.level or 1) + 3 and
                    self.bot.safe_hunt_cell(((g.rect.x1 + g.rect.x2)//2,
                                             (g.rect.y1 + g.rect.y2)//2)) and
                    (not odd or self.bot.data.monsters[g.template_id].kill_exp % 2 == 1) and
                    (not strong or self.bot.data.monsters[g.template_id].hp >= 40) and
                    (not weak or self.bot.data.monsters[g.template_id].hp <= 6)]
                if not groups:
                    raise hs.Unconfirmed('NATURAL_TARGET_GROUP_REQUIRED')
                group = min(groups, key=lambda g: (
                    self.bot.data.monsters[g.template_id].hp if odd else 0,
                    hb.distance(self.bot.position, (g.rect.x1, g.rect.y2))))
                goal = ((group.rect.x1 + group.rect.x2)//2, (group.rect.y1 + group.rect.y2)//2)
                self.navigation_observation = dict(group=group.group_id, goal=goal,
                    position=self.bot.position, goal_safe=self.bot.safe_hunt_cell(goal),
                    waiting_for_received_target=hb.distance(self.bot.position, goal) <= 2)
                if hb.distance(self.bot.position, goal) > 2:
                    await self.bot.step(goal, radius=2)
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
                # NPCs target their last attacker. Repeated owner swings turn
                # the target back to the owner and ASSIST kills it, preventing
                # the very incoming-member/death observation required here.
                attack_marker = self.bot.peer.ordinal
                await self.command(1, target)
                def target_gone():
                    actor = self.bot.actors.get(target)
                    return actor is None or not actor['alive']
                remaining = until - time.monotonic()
                if remaining <= 0:
                    raise hs.Unconfirmed('NATURAL_REPEAT_COMPANION_DEATH_DEADLINE')
                await self.wait_current('repeat_member_actual_attack', lambda:
                    not self.member.alive or target_gone() or bool(self.frames(
                        attack_marker, 0x4e31, **{'2': ref.uid, '3': target})), timeout=remaining)
                if not self.member.alive:
                    break
                if target_gone():
                    continue
                await self.command(4)
                remaining = until - time.monotonic()
                if remaining <= 0:
                    raise hs.Unconfirmed('NATURAL_REPEAT_COMPANION_DEATH_DEADLINE')
                await self.wait_current('repeat_natural_incoming_death', lambda:
                    not self.member.alive or target_gone(), timeout=remaining)
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
        await self.check_corpse_stopped(marker, member_uid)
        await self.check_dead_call(member_uid)

    async def check_corpse_stopped(self, marker, member_uid):
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

    async def check_dead_call(self, member_uid):
        # Mage-token semantics only; the pet harness reuses check_corpse_stopped.
        from tools.local_original_session.world_feature_companion import TOKEN_TEMPLATE
        entity = self.world.entities.get(member_uid)
        corpse = (entity.ref, entity.map_id, entity.x, entity.y)
        tokens = {uid: row[4] for uid, row in self.bot.inventory.items()
                  if row.get(2) == TOKEN_TEMPLATE}
        marker = self.bot.peer.ordinal
        await self.toggle()
        notices = self.frames(marker, 0x4eea, **{'1': 12066})
        self.record('dead_call_preserves_corpse_and_sends_scroll_notice',
            not self.member.alive and self.member.hp == 0 and
            (entity.ref, entity.map_id, entity.x, entity.y) == corpse and
            tokens == {uid: row[4] for uid, row in self.bot.inventory.items()
                       if row.get(2) == TOKEN_TEMPLATE} and bool(notices),
            member_uid=member_uid, notice_count=len(notices))

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
        """ATS-only socket checks; no implicit owner heal/reserve expectations."""
        from tools.local_original_session import ats_config_codec as codec
        self.stage = 'magic'
        owner = self.bot.character
        magic = self.world.companion_ai.magic
        await self.command(4)
        await self.tick_wait(1.2)
        self.record('magic_unsaved_ats_has_no_default_casts',
            not any(e['spell'] in ('heal', 'shield', 'energy_bolt') for e in magic.events))
        # Persist actual settings through the existing selected mage's 4ED6
        # and companion-scope switch, then restore the owner's normal session.
        if not await self.close():
            raise hs.Unconfirmed('MAGIC_SETTINGS_EPOCH_CLOSE_FAILED')
        self.enable_settings = True
        await self.open(seed=False, character='SoloMage')
        config = codec.wrap_blob(b'\x08\x01')
        async def save(ats):
            await self.bot.peer.request(0x4ed6, hb.pb.encode_bytes(1, config) + hb.pb.encode_bytes(2, ats),
                alive=True, check=lambda batch: hb.find(batch, 0x4f57), label='ATS_MAGIC_SAVE')
        await save(codec.wrap_blob(codec.build_ats()))
        _, result = await self.signal('ats-select', ('companion',), actor=False)
        if result.get('status') != 'SUPPLIED':
            raise hs.Unconfirmed('MAGIC_COMPANION_ATS_SCOPE_REQUIRED')
        await save(codec.wrap_blob(codec.build_ats(buff_spells=(2,), sequence_spells=(3, 0))))
        if not await self.close():
            raise hs.Unconfirmed('MAGIC_MEMBER_SETTINGS_CLOSE_FAILED')
        self.enable_settings = False
        await self.open(seed=False, character=owner)
        await self.wait_current('magic_saved_ats_actor', lambda: self.actor is not None,
                                timeout=self.args.timeout)
        magic = self.world.companion_ai.magic
        if not all(magic.eligible(self.actor, name) for name in ('shield', 'energy_bolt', 'heal')):
            raise hs.Unconfirmed('ATS_MAGIC_SELECTED_LEARNED_SPELLS_REQUIRED')
        events = lambda name: [e for e in magic.events if e['spell'] == name]
        await self.wait_current('ats_selected_self_shield', lambda: bool(events('shield')), timeout=35)
        shield = events('shield')[0]
        self.record('magic_selected_self_shield_effect', shield['target'] == self.actor.ref.uid and
            shield['mp_before'] - shield['mp_after'] == 2 and
            bool(self.frames(0, 0x4ed8, **{'1': self.actor.ref.uid, '2': 221})), actual=shield)
        # The initial no-ATS observation used HOLD. Restore FOLLOW/PASSIVE
        # through its existing bridge socket signal before walking to a target.
        if self.member.movement_mode == 'HOLD':
            await self.signal('movement-follow')
        target = await self.target(weak=True)
        marker = await self.command(1, target)
        await self.wait_current('ats_sequence_first_usable_bolt', lambda: bool(events('energy_bolt')), timeout=100)
        bolt = events('energy_bolt')[0]
        self.record('magic_selected_bolt_real_target_and_cost', bolt['target'] == target and
            bolt['amount'] > 0 and bolt['mp_before'] - bolt['mp_after'] == 3 and
            bool(self.frames(marker, 0x4e31, **{'1': 18, '2': self.actor.ref.uid, '3': target})), actual=bolt)
        self.record('magic_selected_heal_owned_living_targets_only',
            bool(events('heal')) and
            all(e['target'] in (self.actor.ref.uid, self.bot.self_uid) for e in events('heal')),
            actual=events('heal'))
        await self.command(4)
        before = len(events('energy_bolt'))
        await self.tick_wait(1.2)
        self.record('magic_passive_cancels_offense_keeps_deadline',
            len(events('energy_bolt')) == before and self.actor.target is None)

    async def elemental(self):
        """Natural NPC AI -> registered target -> member elemental HP consumer."""
        from tools.local_original_session import inventory
        self.stage = 'natural_elemental_incoming'
        await self.summon()
        await self.command(4)
        bags = self.broker._companion_inventory
        for template in (501, 3937):
            item_uid = next(uid for uid, row in self.bot.inventory.items()
                            if row.get(2) == template and row.get(4, 0) > 0)
            await self.bot.peer.request(0x4ef5, hb.uint(1, self.actor.ref.uid)
                + hb.uint(2, item_uid) + hb.uint(3, 1),
                check=lambda batch: next((f for f in batch if f.opcode in (0x0965, 0x0978)), None))
        profile = self.world.companion_profiles[self.member_id]
        self.record('give_equipment_projects_member_wind20', profile.resist_wind == 20,
            equipped=dataclasses.asdict(bags.states[self.member_id]), templates=[501, 3937])
        target = None
        until = time.monotonic() + self.args.navigation_timeout
        # Elders are passive. Every movement and the one companion provocation
        # uses the ordinary router; read-only positions guide the bot.
        self.bot.safe_hunt_cell = lambda point: True
        await self.command(2)
        while time.monotonic() < until:
            candidates = [(uid, row) for uid, row in self.bot.actors.items()
                if row['alive'] and self.world.spawner.slot_for(uid) is not None
                and self.world.spawner.slot_for(uid)[0].monster.template_id == 7]
            if candidates:
                target, row = min(candidates, key=lambda pair: hb.distance(self.bot.position, pair[1]['position']))
                if hb.distance(self.bot.position, row['position']) <= 1:
                    break
                await self.bot.step(row['position'], radius=1)
            await self.tick_wait(.1)
        self.record('approached_received_natural_elder', target is not None and
            hb.distance(self.bot.position, self.bot.actors[target]['position']) <= 1, target=target)
        member_uid, marker = self.actor.ref.uid, self.bot.peer.ordinal
        await self.command(1, target)
        await self.wait_current('companion_provokes_elder', lambda: bool(self.frames(
            marker, 0x4e31, **{'2': member_uid, '3': target})), timeout=30)
        await self.command(4)
        samples = []
        for resistance in (20, 0):
            if resistance == 0:
                by_uid = {r.identifier: r.template_bits for r in inventory.validate_kit_frame(
                    bags.frames[self.member_id])}
                for key, item_uid in tuple(bags.states[self.member_id].slots):
                    if by_uid[item_uid] in (501, 3937):
                        _, result = await self.signal('item-unequip', (self.member_id,
                            self.actor.ref.generation, 1, item_uid, key))
                        self.record('unequip_elemental_' + str(by_uid[item_uid]), result.get('status') == 'OK')
            def events():
                return [e for e in self.broker._world_magic_events
                    if e.get('outcome') == 'npc_magic' and e['npc_uid'] == target
                    and e['target'] == member_uid and e['resist_wind'] == resistance]
            await self.wait_current('natural_member_spell_wind_' + str(resistance),
                lambda: bool(events()), timeout=self.args.death_timeout)
            event = events()[0]
            trace = event['trace']
            bonus = max(event['intelligence'] - 12, 1) * 3 / 32
            expected = int(int(trace['base_damage'] * max(1 - trace['elemental_defense'] + bonus, 0))
                           * event['leverage'] / 10)
            bare = int(int(trace['base_damage'] * (1 + bonus)) * event['leverage'] / 10)
            if trace['mr_roll'] <= trace['mr']:
                expected //= 2
                bare //= 2
            _, children = await self.pet_status()
            self.record('member_elemental_dice_hp_consumer_' + str(resistance),
                event['rolled_damage'] == expected and event['amount'] == min(event['hp_before'], expected)
                and event['hp_after'] == event['hp_before'] - event['amount']
                and (expected < bare if resistance else expected == bare)
                and bool(self.frames(marker, 0x4e31, **{'2': target, '3': member_uid}))
                and any(hb.scalar(c, 3) == self.member.hp for c in children),
                event=event, calculated=expected, same_dice_mr_without_resist=bare,
                actual_member_hp=self.member.hp, pet_status_observed=True)
            samples.append(event)
        self.elemental_samples = samples

    async def receive_equipment(self, template, *, bridge=False, equip=True):
        """Receive into the saved bag, then explicitly equip through item-equip."""
        from tools.local_original_session import inventory
        bags, uid = self.broker._companion_inventory, self.member_id
        prefix = 'bridge_' if bridge else ''
        before_state = bags.states[uid]
        before_look = dict(self.world.companion_looks[uid])
        before_ac = self.world.companion_profiles[uid].ac
        before_items = {r.identifier for r in inventory.validate_kit_frame(bags.frames[uid])}
        await self.wait_current('owner_supply_' + str(template), lambda: any(
            r.get(2) == template and r.get(4, 0) > 0 for r in self.bot.inventory.values()))
        source = next(key for key, row in self.bot.inventory.items()
                      if row.get(2) == template and row.get(4, 0) > 0)
        before_quantity = self.bot.inventory[source][4]
        marker = self.bot.peer.ordinal
        if bridge:
            _, result = await self.item_signal('item-give', source, 1)
            self.record(prefix + 'give_equipment_' + str(template), result.get('status') == 'OK'
                and self.bot.inventory.get(source, {}).get(4, 0) == before_quantity - 1, result=result)
        else:
            await self.bot.peer.request(0x4ef5, hb.uint(1, self.actor.ref.uid)
                + hb.uint(2, source) + hb.uint(3, 1), check=lambda batch: next(
                    (f for f in batch if f.opcode in (0x0965, 0x0978)), None))
            self.record('give_' + str(template),
                self.bot.inventory.get(source, {}).get(4, 0) == before_quantity - 1, item_uid=source, count=1)
        received = next((r.identifier for r in inventory.validate_kit_frame(bags.frames[uid])
            if r.identifier not in before_items and r.template_bits == template and dict(r.raw_fields)[4] == 1), None)
        self.record(prefix + 'received_equipment_bag_only_' + str(template), received is not None
            and self.store.restore(uid) == bags.frames[uid]
            and bags.states[uid] == before_state
            and bags.equipment.restore(uid, bags.frames[uid]) == before_state
            and self.world.companion_looks[uid] == before_look
            and self.world.companion_profiles[uid].ac == before_ac
            and not self.frames(marker, 0x4ed5, **{'1': self.actor.ref.uid}),
            template=template, received_uid=received, ac=before_ac, stance=before_look['stance'])
        if not equip:
            return received
        marker, result = await self.item_signal('item-equip', received)
        state, definition = bags.states[uid], self.world.data.items[template]
        if definition.kind == 'weapon':
            stance = self.broker._world_stances[definition.weapon_type]
            effect = state.weapon_uid == received and self.world.companion_looks[uid]['stance'] == stance
            if stance != before_look['stance']:
                effect = effect and bool(self.frames(marker, 0x4ed5, **{'1': self.actor.ref.uid, '2': stance}))
        else:
            effect = ((definition.slot_key, received) in state.slots
                and self.world.companion_profiles[uid].ac < before_ac)
        self.record(prefix + 'explicit_item_equip_saved_and_live_' + str(template),
            result.get('status') == 'OK' and effect and state != before_state
            and self.store.restore(uid) == bags.frames[uid]
            and bags.equipment.restore(uid, bags.frames[uid]) == state,
            result=result, template=template, received_uid=received,
            ac_before=before_ac, ac_after=self.world.companion_profiles[uid].ac,
            stance_before=before_look['stance'], stance_after=self.world.companion_looks[uid]['stance'])
        return received

    async def conflicting_equipment(self, staff):
        """Both conflict directions using the existing mage-compatible kit bow/shield."""
        bags, uid = self.broker._companion_inventory, self.member_id
        shield = await self.receive_equipment(113)
        bow = await self.receive_equipment(11, equip=False)

        async def refused(item, label):
            before_frame, before_state = bags.frames[uid], bags.states[uid]
            before_look = dict(self.world.companion_looks[uid])
            before_ac = self.world.companion_profiles[uid].ac
            marker, result = await self.item_signal('item-equip', item)
            notices = [hb.scalar(frame.values, 2).decode('utf-8')
                for frame in self.frames(marker, 0x4eea, **{'1': 12066})
                if isinstance(hb.scalar(frame.values, 2), bytes)]
            self.record(label, result.get('status') == 'REFUSED'
                and 'EQUIPMENT_TWO_HANDED_SHIELD_CONFLICT' in result.get('error', '')
                and any('양손' in text and '방패' in text for text in notices)
                and bags.frames[uid] == before_frame and bags.states[uid] == before_state
                and self.store.restore(uid) == before_frame
                and bags.equipment.restore(uid, before_frame) == before_state
                and self.world.companion_looks[uid] == before_look
                and self.world.companion_profiles[uid].ac == before_ac
                and not self.frames(marker, 0x4ed5, **{'1': self.actor.ref.uid}),
                result=result, notices=notices)

        await refused(bow, 'two_handed_bow_with_shield_refused_unchanged')
        _, result = await self.item_signal('item-unequip', shield, 8)
        self.record('explicit_shield_unequip_before_bow', result.get('status') == 'OK'
            and shield not in dict(bags.states[uid].slots).values(), result=result)
        _, result = await self.item_signal('item-equip', bow)
        self.record('two_handed_bow_equips_without_shield', result.get('status') == 'OK'
            and bags.states[uid].weapon_uid == bow
            and bags.equipment.restore(uid, bags.frames[uid]) == bags.states[uid], result=result)
        await refused(shield, 'shield_with_two_handed_bow_refused_unchanged')
        _, result = await self.item_signal('item-equip', staff)
        self.record('one_handed_staff_restored_after_conflicts', result.get('status') == 'OK'
            and bags.states[uid].weapon_uid == staff
            and self.world.companion_looks[uid]['stance'] == 50
            and bags.equipment.restore(uid, bags.frames[uid]) == bags.states[uid], result=result)

    async def equipment_flow(self):
        """Real GIVE/explicit equip, no-ATS bag retention and saved mage login."""
        from tools.local_original_session import inventory
        await self.summon()
        await self.command(4)  # real pet-window barrier; keep fixture near owner
        self.stage = 'equipment'
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
        staff = await self.receive_equipment(230)
        await self.receive_equipment(102)
        await self.conflicting_equipment(staff)
        def potion_quantities(frame):
            rows = inventory.validate_kit_frame(frame)
            return {template: sum(dict(row.raw_fields)[4] for row in rows if row.template_bits == template)
                    for template in (14, 492)}
        before_potions = potion_quantities(bags.frames[uid])
        before_blue = bags.blue_until.get(uid, 0)
        await give(14, 5)
        await give(492, 2)
        expected_potions = {14: before_potions[14] + 5, 492: before_potions[492] + 2}
        await self.tick_wait(2.5)
        policy = bags._ats(self.member)
        self.record('no_ats_received_potions_stay_saved_without_auto_use',
            (not policy or policy.get('status') != 'valid')
            and potion_quantities(bags.frames[uid]) == expected_potions
            and self.store.restore(uid) == bags.frames[uid]
            and potion_quantities(self.store.restore(uid)) == expected_potions
            and not any(event.get('template') in (14, 492) for event in bags.events)
            and bags.blue_until.get(uid, 0) == before_blue,
            quantities=expected_potions, events=bags.events,
            reason='No saved ATS setting: automatic HP/MP potion use is disabled; configured use belongs to ATS scenarios')
        before_frame = bags.frames[uid]
        before_state = bags.states[uid]
        owner = self.bot.character
        if not await self.close():
            raise hs.Unconfirmed('EQUIPMENT_FIRST_CLOSE_FAILED')
        await self.open(seed=False, character=owner)
        bags = self.broker._companion_inventory
        self.record('companion_bag_and_equipment_survive_reconnect',
            bags.frames[uid] == before_frame and bags.states[uid] == before_state
            and potion_quantities(bags.frames[uid]) == expected_potions,
            potion_quantities=potion_quantities(bags.frames[uid]))
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
        # In all, bridge() already gave the owner's staff to this member. Take
        # it back through the real route before selection's original GIVE.
        if not any(row.get(2) == 230 and row.get(4, 0) > 0
                   for row in self.bot.inventory.values()):
            bags = self.broker._companion_inventory
            state = bags.states[uid]
            member_staff = min((item.identifier for item in
                inventory.validate_kit_frame(bags.frames[uid])
                if item.template_bits == 230 and dict(item.raw_fields)[4] > 0),
                key=lambda item: item == state.item_uid)
            if state.weapon_uid == member_staff:
                await self.item_signal('item-unequip', member_staff, 9)
            await self.item_signal('item-take', member_staff, 1)
            await self.bot.alive()
        # TAKE allocates an owner UID; always read the received inventory again.
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

    # ---- companion part1/part2 server rules (LOCAL bridge signals over socket) ----
    async def signal(self, operation, args=(), *, actor=True, label=None):
        """Send one LOCAL marker 4F02 body (SIGNALS.md) through the real router."""
        from tools.local_original_session import companion_signals as cs
        low32 = self.actor.ref.uid & 0xFFFFFFFF if actor else 0
        body = cs.encode_signal(operation, low32, tuple(str(a) for a in args))
        marker = self.bot.peer.ordinal
        if operation in ('bag-open-take', 'equipment-open'):
            # Socket 4F02 has no view metadata. Use the existing DLL IPC ingress
            # for window opens, including its positive per-window lifetime epoch.
            self.bridge_sequence += 1
            seq = self.bridge_sequence
            directory = Path(os.environ['SL_COMPANION_BRIDGE_DIR'])
            body_name = f'companion-signal-{seq}.bin'
            (directory / body_name).write_bytes(body)
            metadata = dict(schema='companion-native-signal-v1', transport='LOCAL_IPC',
                event_seq=seq, view_epoch=seq, body_file=body_name)
            (directory / f'companion-signal-{seq}.json').write_text(
                json.dumps(metadata), encoding='utf-8')
            await self.wait_current('window_open_' + operation, lambda: any(
                event.get('transport') == 'LOCAL_IPC' and event.get('event_seq') == seq
                for event in self.broker._bridge_signals), timeout=self.args.timeout)
            await self.bot.alive()
            result = next(event for event in self.broker._bridge_signals
                if event.get('transport') == 'LOCAL_IPC' and event.get('event_seq') == seq)
            if result.get('status') == 'OK':
                kind = 'bag' if operation == 'bag-open-take' else 'equipment'
                self.view_epochs[(self.actor.ref, kind)] = seq
            return marker, result
        await self.bot.peer.request(0x4f02, body, alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label=label or 'SIGNAL_' + operation)
        return marker, (self.broker._bridge_signals[-1] if self.broker._bridge_signals else {})

    async def item_signal(self, operation, item, *args):
        """Reuse the epoch of this actor's successfully opened logical window."""
        kind = 'equipment' if operation == 'item-unequip' else 'bag'
        key = (self.actor.ref, kind)
        if key not in self.view_epochs:
            _, result = await self.signal('equipment-open' if kind == 'equipment' else 'bag-open-take')
            if result.get('status') != 'OK':
                raise hs.Unconfirmed('ITEM_WINDOW_OPEN_REQUIRED')
        entity = self.world.entities.resolve(self.actor.ref)
        return await self.signal(operation,
            (self.member_id, entity.generation, self.view_epochs[key], item, *args))

    def tile_path_time(self, positions):
        moves = [(t, p) for (t, p), (_, q) in zip(positions[1:], positions) if p != q]
        if len(moves) < 3:
            return None, len(moves)
        span = moves[-1][0] - moves[0][0]
        return span / (len(moves) - 1), len(moves)

    async def walk_speed(self):
        """Companion walks at its own walk interval and keeps up with the owner."""
        self.stage = 'walk_speed'
        await self.wait_current('walk_actor', lambda: self.actor is not None, timeout=self.args.timeout)
        await self.signal('movement-hold')
        self.record('signal_movement_hold_support_only', self.member.movement_mode == 'HOLD'
                    and self.member.combat_mode == 'PASSIVE')
        start = self.bot.position
        goal = next(((start[0] + dx * 8, start[1] + dy * 8) for dx, dy in hb.DELTAS
                     if self.travel_heading((start[0] + dx * 8, start[1] + dy * 8), 0) is not None), None)
        if goal is None:
            raise hs.Unconfirmed('WALK_SPEED_OPEN_LINE_REQUIRED')
        await self.navigate(goal, radius=0)
        await self.bot.alive()
        if self.member_position() is None:
            raise hs.Unconfirmed('WALK_SPEED_LIVING_MEMBER_REQUIRED')
        gap = hb.distance(self.bot.position, self.member_position())
        positions = [(time.monotonic(), self.member_position())]
        await self.signal('movement-follow')
        self.record('signal_movement_follow_support_only', self.member.movement_mode == 'FOLLOW'
                    and self.member.combat_mode == 'PASSIVE')
        until = time.monotonic() + 20
        while hb.distance(self.bot.position, self.member_position()) > 1 and time.monotonic() < until:
            await asyncio.sleep(.02)
            position = self.member_position()
            if position != positions[-1][1]:
                positions.append((time.monotonic(), position))
            if time.monotonic() - self.bot.last_alive >= .5:
                await self.bot.alive()
        interval, moves = self.tile_path_time(positions)
        walk = 16 / 24
        self.record('companion_walk_interval_matches_walk_ms', interval is not None
                    and abs(interval - walk) <= .05, measured_interval=interval, walk_s=walk,
                    tile_moves=moves, starting_gap=gap, previous_tick_rounded_interval=0.75)
        # Owner walks back at its normal pace; the companion stays close behind.
        trace, back = [], start
        until = time.monotonic() + self.args.navigation_timeout
        while hb.distance(self.bot.position, back) > 0 and time.monotonic() < until:
            await self.bot.step(back, 0)
            trace.append(hb.distance(self.bot.position, self.member_position()))
            if time.monotonic() - self.bot.last_alive >= 1:
                await self.bot.alive()
            await asyncio.sleep(.02)
        await self.tick_wait(1.5)
        final = hb.distance(self.bot.position, self.member_position())
        self.record('companion_keeps_up_with_owner_same_speed', bool(trace) and max(trace) <= 2
                    and final <= 1, max_distance=max(trace or [99]), final_distance=final,
                    owner_steps=len(trace))

    async def bridge(self):
        """Pet-window rows 1-7 and companion bag/equipment requests over 4F02."""
        from tools.local_original_session import world_companion_ui as ui
        from tools.local_original_session import inventory
        self.stage = 'bridge_rows'
        await self.wait_current('bridge_actor', lambda: self.actor is not None, timeout=self.args.timeout)
        member = self.member_id
        bags = self.broker._companion_inventory
        # Rows 1-3 keep the original 4F02 mode1/2/3 path.
        await self.command(2)
        self.record('row_attack_stance_assist', self.member.combat_mode == 'ASSIST'
                    and self.member.movement_mode == 'FOLLOW')
        await self.command(3)
        self.record('row_defend_stance', self.member.combat_mode == 'DEFEND')
        marker, result = await self.signal('settings-load')
        # Row 4 opens the owner's edit of this member's ATS setting (ats_edit
        # scenario); with no saved owner setting yet it is refused with a notice.
        self.record('row_companion_settings_routes_to_ats_edit', result.get('status') == 'EDIT_STARTED'
                    or (result.get('status') == 'REFUSED' and bool(self.frames(marker, 0x4eea))), result=result)
        if result.get('status') == 'EDIT_STARTED':
            await self.signal('ats-edit-close', actor=False)
            await self.signal('ats-edit-restored', actor=False)
        marker, result = await self.signal('bag-open-take')
        published = self.broker._companion_published[-1]
        outbox = self.broker._bridge_outbox[-1]
        frame = outbox.get('frame')
        decoded = ui.decode_model_frame(frame) if frame else None
        bag_rows = [r for r in inventory.validate_kit_frame(bags.frames[member]) if dict(r.raw_fields)[4] > 0]
        self.record('row_companion_bag_model_published', result.get('status') == 'OK'
                    and published['kind'] == 'model' and decoded is not None
                    and decoded['member'] == member and decoded['owner'] == self.bot.self_uid
                    and decoded['packets'][0][0] == 0x0964 and decoded['packets'][-1][0] == 0x4E38
                    and outbox['status'] in ('HOST_UNATTACHED', 'POSTED'),
                    bag_rows=len(bag_rows), packets=[hex(op) for op, _ in (decoded or {}).get('packets', ())],
                    transport=outbox['status'])
        marker, result = await self.signal('equipment-open')
        decoded = ui.decode_model_frame(self.broker._bridge_outbox[-1]['frame'])
        state = bags.states[member]
        worn = (1 if state.weapon_uid else 0) + len(state.slots)
        self.record('row_companion_equipment_model_published', result.get('status') == 'OK'
                    and sum(op == 0x097A for op, _ in decoded['packets']) == worn
                    and decoded['revision'] > 1, worn=worn, revision=decoded['revision'])
        # Give (owner -> member) then take back (member -> owner) one red potion.
        self.stage = 'bridge_items'
        await self.receive_equipment(230, bridge=True)
        await self.receive_equipment(102, bridge=True)
        uid, row = min(((k, r) for k, r in self.bot.inventory.items()
                        if r.get(2) == 14 and r.get(4, 0) > 1), key=lambda p: p[0])
        before_owner = row[4]
        count = lambda: sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(bags.frames[member])
                            if r.template_bits == 14)
        before_member = count()
        _, result = await self.item_signal('item-give', uid, 1)
        self.record('bag_give_owner_to_member', result.get('status') == 'OK' and count() == before_member + 1
                    and self.bot.inventory.get(uid, {}).get(4) == before_owner - 1, result=result)
        member_item = next(r.identifier for r in inventory.validate_kit_frame(bags.frames[member])
                           if r.template_bits == 14 and dict(r.raw_fields)[4] > 0)
        owner_total = lambda: sum(r.get(4, 0) for r in self.bot.inventory.values() if r.get(2) == 14)
        owner_before = owner_total()
        _, result = await self.item_signal('item-take', member_item, 1)
        await self.bot.alive()
        self.record('bag_take_member_to_owner', result.get('status') == 'OK' and count() == before_member
                    and owner_total() == owner_before + 1, result=result)
        state = bags.states[member]
        if state.slots:
            key, item = state.slots[0]
            _, result = await self.item_signal('item-unequip', item, key)
            off = item not in {v for _, v in bags.states[member].slots}
            _, again = await self.item_signal('item-equip', item)
            self.record('equipment_unequip_then_equip', result.get('status') == 'OK' and off
                        and again.get('status') == 'OK' and (key, item) in bags.states[member].slots,
                        slot_key=key, item=item)
            worn_take = await self.item_signal('item-take', item, 1)
            self.record('bag_take_worn_item_refused', worn_take[1].get('status') == 'REFUSED'
                        and 'UNEQUIP_FIRST' in worn_take[1].get('error', ''))
        else:
            self.record('equipment_unequip_then_equip', None, reason='MEMBER_HAS_NO_WORN_ARMOR')
        saved = self.store.restore(member)
        self.record('bag_changes_saved_on_real_mage_rows', saved == bags.frames[member]
                    and self.equipment.restore(member, saved) == bags.states[member])
        _, result = await self.signal('f4-pickup', actor=False)
        self.record('f4_pickup_signal_routed', result.get('status') in ('QUEUED', 'NO_ITEMS'), result=result)
        # Row 1: attack target designation focuses one monster.
        self.stage = 'bridge_focus'
        await self.command(2)
        target = await self.target()
        if target is not None and self.actor is not None:
            await self.command(1, target)
            self.record('row_attack_target_focus', self.actor.focus is not None
                        and self.actor.focus.uid == target, target=target)
        else:
            self.record('row_attack_target_focus', None, reason='NO_VISIBLE_HOSTILE')
        await self.signal('movement-follow')

    async def auto_resummon(self):
        """Out at logout -> back automatically. No dismissal (design decision):
        the legacy mode-8 request keeps the member summoned."""
        self.stage = 'auto_resummon'
        character = self.bot.character
        await self.wait_current('resummon_actor', lambda: self.actor is not None, timeout=self.args.timeout)
        await self.command(8)
        self.record('dismiss_request_keeps_summoned_flag', self.actor is not None and self.member.summoned)
        await self.close()
        await self.open(seed=False, character=character)
        await self.wait_current('auto_resummon_after_login', lambda: self.actor is not None, timeout=self.args.timeout)
        self.record('summoned_member_resummoned_at_login', self.actor is not None and self.member.summoned
                    and hb.distance(self.member_position(), self.bot.position) <= 1)

    async def owner_death(self):
        """Owner dies: member reads its own return scroll, or waits and is left behind."""
        from tools.local_original_session import inventory
        bags = None
        for with_scroll in (True, False):
            self.stage = 'owner_death_' + ('scroll' if with_scroll else 'wait')
            character = self.bot.character
            await self.close()
            self.owner_vitals = 1  # pre-login fixture: one hit kills the owner
            await self.open(seed=False, character=character)
            self.owner_vitals = None
            await self.wait_current('death_actor', lambda: self.actor is not None, timeout=self.args.timeout)
            bags = self.broker._companion_inventory
            member = self.member_id
            scrolls = lambda: sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(bags.frames[member])
                                  if r.template_bits == 162)
            if with_scroll and scrolls() == 0:
                uid = next(k for k, r in self.bot.inventory.items() if r.get(2) == 162 and r.get(4, 0) > 0)
                await self.bot.peer.request(0x4ef5, hb.uint(1, self.actor.ref.uid) + hb.uint(2, uid)
                    + hb.uint(3, 1), alive=True, check=lambda b: hb.find(b, 0x4f57), label='GIVE_RETURN_SCROLL')
            elif not with_scroll:
                while scrolls():
                    item = next(r.identifier for r in inventory.validate_kit_frame(bags.frames[member])
                                if r.template_bits == 162 and dict(r.raw_fields)[4] > 0)
                    _, result = await self.item_signal('item-take', item, 1)
                    self.record('owner_death_return_scroll_taken', result.get('status') == 'OK', result=result)
            before = scrolls()
            await self.signal('movement-follow')
            self.args.potion_threshold_saved = self.args.potion_threshold
            self.args.potion_threshold = 0.0001
            try:
                await self.receive_damage(lethal=True)
            finally:
                self.args.potion_threshold = self.args.potion_threshold_saved
            await asyncio.sleep(.3)
            returns = self.broker._companion_returns[-1] if self.broker._companion_returns else {}
            if with_scroll:
                self.record('owner_death_member_uses_own_return_scroll',
                            returns.get('result') == 'RETURN_SCROLL_TO_TOWN' and scrolls() == before - 1
                            and self.actor is None and self.member.summoned, scrolls_before=before,
                            scrolls_after=scrolls())
            else:
                self.record('owner_death_member_waits_without_scroll',
                            returns.get('result') == 'WAIT_NO_RETURN_SCROLL' and self.actor is not None
                            and self.actor.owner_down)
            await self.bot.peer.request(0x4eec, check=lambda batch: hb.find(batch, 0x4e3b, **{'1': 1}),
                                        label='OWNER_DEAD_RESTART')
            await self.bot.reselect()
            await self.tick_wait(1)
            if with_scroll:
                self.record('returned_member_reappears_beside_owner_in_town', self.actor is not None
                            and hb.distance(self.member_position(), self.bot.position) <= 1)
            else:
                self.record('waiting_member_left_behind_after_restart', self.actor is None
                            and not self.member.summoned)
                await self.toggle()
                await self.wait_current('call_left_behind_member', lambda: self.actor is not None)

    async def ats(self):
        """ATS me/companion scope on the mage, save attribution, reconnect, AI use."""
        from tools.local_original_session import ats_config_codec as codec
        from tools.local_entry_server import protobuf as pb
        self.stage = 'ats_scope'
        owner = self.bot.character
        member = self.member_id
        await self.close()
        self.enable_settings = True
        await self.open(seed=False, character='SoloMage')
        self_cfg = codec.wrap_blob(b'\x08\x01\x10\x02')
        self_ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=50.0))
        mate_ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=80.0,
                                                   function_templates=(17,), options={1: 5, 7: 50}))
        save = lambda f2: self.bot.peer.request(0x4ed6, pb.encode_bytes(1, self_cfg) + pb.encode_bytes(2, f2),
                                                alive=True, check=lambda b: hb.find(b, 0x4f57), label='ATS_SAVE')
        await save(self_ats)
        marker, result = await self.signal('ats-select', ('companion',), actor=False)
        noti = self.frames(marker, 0x4ed7)
        fields = hb.fields(noti[-1].wire[4:-2]) if noti else {}
        self.record('ats_select_supplies_full_4ed7', result.get('status') == 'SUPPLIED'
                    and hb.scalar(fields, 1) == self_cfg.hex().encode()
                    and hb.scalar(fields, 2) == codec.loadable_ats(self_ats).hex().encode(),
                    published=[e['kind'] for e in self.broker._bridge_outbox[-2:]])
        await save(mate_ats)
        sidecar = self.broker.realm.settings._load()
        with pb.parse_message(sidecar.raw) as message:
            account_f2 = bytes(message.occurrences(2)[0].value)
        self.record('ats_companion_save_attributed', account_f2 == self_ats
                    and self.broker._ats_store['characters'][str(member)]['companion_ats'] == mate_ats.hex())
        marker, result = await self.signal('ats-select', ('self',), actor=False)
        noti = self.frames(marker, 0x4ed7)
        self.record('ats_select_self_restores_self', bool(noti) and
                    hb.scalar(hb.fields(noti[-1].wire[4:-2]), 2) == codec.loadable_ats(self_ats).hex().encode())
        await self.close()
        await self.open(seed=False, character='SoloMage')
        marker, result = await self.signal('ats-select', ('companion',), actor=False)
        noti = self.frames(marker, 0x4ed7)
        self.record('ats_companion_setting_restored_after_reconnect', bool(noti) and
                    hb.scalar(hb.fields(noti[-1].wire[4:-2]), 2) == codec.loadable_ats(mate_ats).hex().encode())
        await self.close()
        self.enable_settings = False
        await self.open(seed=False, character=owner)
        await self.wait_current('ats_actor', lambda: self.actor is not None, timeout=self.args.timeout)
        policy = self.broker._companion_ats_policy(self.member)
        self.record('ats_policy_normalized_for_companion_ai', policy is not None
                    and policy['potion_hp']['threshold'] == 0.8 and policy['function_items'] == [17]
                    and policy['scan_tiles'] == 5 and policy['pickup_weight'] == 50)
        # AI application: the configured function item (green potion) is used.
        bags = self.broker._companion_inventory
        green = next((k for k, r in self.bot.inventory.items() if r.get(2) == 17 and r.get(4, 0) > 0), None)
        if green is None:
            self.record('ats_function_item_used_by_companion', None, reason='OWNER_GREEN_POTION_UNSUPPLIED')
            return
        await self.bot.peer.request(0x4ef5, hb.uint(1, self.actor.ref.uid) + hb.uint(2, green) + hb.uint(3, 1),
            alive=True, check=lambda b: hb.find(b, 0x4f57), label='GIVE_GREEN')
        await self.wait_current('companion_green_effect', lambda: bags.speed_factor(member, self.world.runtime.clock()) < 1,
                                timeout=10)
        walk, _ = self.broker._world.companion_intervals(self.actor)
        self.record('ats_function_item_used_by_companion', walk < 0.6,
                    speed_factor=bags.speed_factor(member, self.world.runtime.clock()), walk_s=walk)

    async def ats_edit(self):
        """Owner (knight) edits the summoned mage's companion ATS from pet row 4 (2차)."""
        from tools.local_original_session import ats_config_codec as codec
        from tools.local_entry_server import protobuf as pb
        self.stage = 'ats_edit'
        owner, member = self.bot.character, self.member_id
        await self.close()
        self.enable_settings = True
        try:
            await self.open(seed=False, character='SoloMage')
            save = lambda f1, f2: self.bot.peer.request(0x4ed6, pb.encode_bytes(1, f1) + pb.encode_bytes(2, f2),
                alive=True, check=lambda b: hb.find(b, 0x4f57), label='ATS_EDIT_SAVE')
            mage_self = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=55.0))
            await save(codec.wrap_blob(b'\x08\x02'), mage_self)
            await self.close()
            await self.open(seed=False, character=owner)
            await self.wait_current('ats_edit_actor', lambda: self.actor is not None, timeout=self.args.timeout)
            store = lambda uid: self.broker._ats_store['characters'].get(str(uid), {})
            owner_uid = self.bot.self_uid
            knight_cfg = codec.wrap_blob(b'\x08\x01\x10\x01')
            knight_ats = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=35.0))
            await save(knight_cfg, knight_ats)
            f2 = lambda frame: hb.scalar(hb.fields(frame.wire[4:-2]), 2)

            def sidecar_f2():
                with pb.parse_message(self.broker.realm.settings._load().raw) as message:
                    return bytes(message.occurrences(2)[0].value)

            def spells(frames):
                rows = {}
                for frame in frames:
                    for raw in hb.fields(frame.wire[4:-2]).get(1, ()):
                        child = hb.fields(raw)
                        rows[hb.scalar(child, 1)] = hb.scalar(child, 2)
                return rows
            magic = getattr(self.broker, '_world_magic', None)
            state = None if magic is None else magic.states.get(owner_uid)
            knight_spells = set(getattr(state, 'learned', ()) or ())
            mate_spells = set(self.member.learned_spells)
            if self.args.scenario == 'ats_edit' and not mate_spells:
                raise hs.Unconfirmed('ATS_EDIT_MEMBER_LEARNED_FIXTURE_REQUIRED')
            # Pet row 4: member setting (its own SELF until a companion one exists) + its spells.
            shown = (store(member).get('companion_ats') or mage_self.hex()).encode()
            marker, result = await self.signal('settings-load')
            noti, listed = self.frames(marker, 0x4ed7), spells(self.frames(marker, 0x4e60))
            request = self.broker._bridge_outbox[-1].get('request', {})
            self.record('ats_edit_start_supplies_member_4ed7_and_spells', result.get('status') == 'EDIT_STARTED'
                        and bool(noti) and hb.scalar(hb.fields(noti[-1].wire[4:-2]), 1) == (
                            bytes.fromhex(store(member)['companion_config']) if store(member).get('companion_config')
                            else codec.companion_character_config(knight_cfg)).hex().encode()
                        and f2(noti[-1]) == codec.loadable_ats(bytes.fromhex(shown.decode())).hex().encode()
                        and all(listed.get(key) == 1 for key in mate_spells)
                        and all(listed.get(key) == 0 for key in knight_spells - mate_spells),
                        result=result, spells=listed)
            self.record('ats_edit_apply_published_with_member_label', request.get('command') == 'ats-edit-apply'
                        and request.get('member_id') == member
                        and bytes.fromhex(request.get('label_hex', '')).decode() == '동료: SoloMage',
                        request={k: v for k, v in request.items() if k != 'label_hex'})
            # Play (4F36 CS_START_ATS_REQ) while editing: notice only, never a start ACK.
            marker = self.bot.peer.ordinal
            await self.bot.peer.request(0x4f36, b'', alive=True, check=lambda b: hb.find(b, 0x4f57),
                                        label='ATS_EDIT_PLAY')
            self.record('ats_edit_play_refused_with_notice', bool(self.frames(marker, 0x4eea))
                        and not self.frames(marker, 0x4f37))
            edited = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=65.0, options={1: 4}))
            await save(knight_cfg, edited)
            self.record('ats_edit_save_attributed_to_member', store(member).get('companion_ats') == edited.hex()
                        and store(owner_uid).get('self_ats') == knight_ats.hex() and sidecar_f2() == knight_ats)
            marker, result = await self.signal('ats-edit-close', actor=False)
            noti, listed = self.frames(marker, 0x4ed7), spells(self.frames(marker, 0x4e60))
            self.record('ats_edit_close_restores_owner_setting_and_spells', result.get('status') == 'RESTORING'
                        and bool(noti) and f2(noti[-1]) == codec.loadable_ats(knight_ats).hex().encode()
                        and all(listed.get(key) == 0 for key in mate_spells - knight_spells)
                        and all(listed.get(key) == 1 for key in knight_spells), result=result, spells=listed)
            late = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=70.0, options={1: 4}))
            await save(knight_cfg, late)  # composed before the restore 4ED7 was parsed
            _, result = await self.signal('ats-edit-restored', actor=False)
            mine = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=40.0))
            await save(knight_cfg, mine)
            self.record('ats_edit_late_save_member_then_owner_after_restore', result.get('status') == 'RESTORED'
                        and store(member).get('companion_ats') == late.hex()
                        and store(owner_uid).get('self_ats') == mine.hex() and sidecar_f2() == mine)
            # Disconnect in the middle of an edit: the owner keeps its own setting.
            marker, result = await self.signal('settings-load')
            noti = self.frames(marker, 0x4ed7)
            self.record('ats_edit_reopens_saved_companion_setting', result.get('status') == 'EDIT_STARTED'
                        and bool(noti) and f2(noti[-1]) == codec.loadable_ats(late).hex().encode())
            await self.close()
            await self.open(seed=False, character=owner)
            await self.wait_current('ats_edit_actor_again', lambda: self.actor is not None, timeout=self.args.timeout)
            noti = self.frames(0, 0x4ed7)
            listed = spells(self.frames(0, 0x4e60))
            self.record('ats_edit_reconnect_erases_member_spells',
                        all(listed.get(key) == 0 for key in mate_spells - knight_spells), spells=listed)
            self.record('ats_edit_disconnect_keeps_owner_setting', not self.broker._ats_edit and bool(noti)
                        and f2(noti[-1]) == codec.loadable_ats(mine).hex().encode() and store(owner_uid).get('self_ats') == mine.hex()
                        and store(member).get('companion_ats') == late.hex())
            policy = self.broker._companion_ats_policy(self.member)
            self.record('ats_edit_member_policy_from_owner_edit', policy is not None
                        and abs(policy['potion_hp']['threshold'] - 0.7) < 1e-6 and policy['scan_tiles'] == 4,
                        policy=policy)
        finally:
            self.enable_settings = False

    async def ats_window(self):
        """Independent ATS view/delta/result files over the existing socket router."""
        from tools.local_original_session import ats_config_codec as codec
        self.stage = 'ats_window'
        await self.summon()
        owner, member = self.bot.character, self.member_id
        await self.close()
        self.enable_settings = True
        try:
            # Prepare saved ATS through the existing settings packets, not by
            # replacing product state. Learning is the fresh pre-login fixture.
            await self.open(seed=False, character='SoloMage')
            async def save_native(config, ats):
                await self.bot.peer.request(0x4ed6,
                    hb.pb.encode_bytes(1, config) + hb.pb.encode_bytes(2, ats),
                    alive=True, check=lambda b: hb.find(b, 0x4f57), label='ATS_WINDOW_FIXTURE')
            config = codec.wrap_blob(b'\x08\x01\x10\x02')
            initial = codec.wrap_blob(codec.build_ats(hp_templates=(14,), hp_percent=50,
                mp_templates=(14,), mp_percent=80, function_templates=(17,), buff_spells=(0,),
                options={1: 4}))
            await save_native(config, initial)
            _, selected = await self.signal('ats-select', ('companion',), actor=False)
            self.record('ats_window_fixture_companion_scope', selected.get('status') == 'SUPPLIED',
                        result=selected)
            await save_native(config, initial)
            await self.close()
            await self.open(seed=False, character=owner)
            await self.wait_current('ats_window_actor', lambda: self.actor is not None,
                                    timeout=self.args.timeout)
            knight_config = codec.wrap_blob(b'\x08\x01\x10\x01')
            knight_ats = codec.wrap_blob(codec.build_ats(hp_percent=35))
            await save_native(knight_config, knight_ats)
            directory = Path(os.environ['SL_COMPANION_BRIDGE_DIR'])
            row = lambda: self.broker._ats_store['characters'][str(member)]
            owner_row = dict(self.broker._ats_store['characters'][str(self.bot.self_uid)])
            sidecar = self.broker.realm.settings._load().raw

            def owner_unchanged():
                saved = json.loads(self.broker._ats_path.read_text(encoding='utf-8'))['characters']
                return (self.broker._ats_store['characters'][str(self.bot.self_uid)] == owner_row
                    and saved[str(self.bot.self_uid)] == owner_row
                    and self.broker.realm.settings._load().raw == sidecar)

            async def exchange(operation, args, command, file_key):
                previous = list(self.broker._bridge_outbox)
                _, result = await self.signal(operation, args)
                requests = [e.get('request', {}) for e in self.broker._bridge_outbox
                            if e not in previous and e.get('request', {}).get('command') == command]
                self.record('ats_window_' + operation + '_file_published', len(requests) == 1,
                            result=result, requests=requests)
                request = requests[0]
                name = request.get(file_key, '')
                self.record('ats_window_' + operation + '_file_identity',
                    Path(name).name == name and name.startswith('companion-ats-' +
                        ('view-' if file_key == 'view_file' else 'result-'))
                    and request.get('member_id') == member
                    and request.get('ats_epoch') == result.get('edit_epoch'), request=request)
                payload = json.loads((directory / name).read_text(encoding='utf-8'))
                self.record('ats_window_' + operation + '_payload_identity',
                    payload.get('schema') == ('companion-ats-view-v1' if file_key == 'view_file'
                                             else 'companion-ats-result-v1')
                    and payload.get('member_id') == member
                    and payload.get('edit_epoch') == result.get('edit_epoch'), result=result)
                return result, payload

            async def open_window():
                result, view = await exchange('ats-window-open', (member,), 'ats-window-view', 'view_file')
                self.record('ats_window_open_supplied', result.get('status') == 'SUPPLIED', result=result)
                return view

            async def save_window(epoch, changes):
                self.bridge_sequence += 1
                name = f'companion-ats-delta-{self.bridge_sequence}.json'
                # Only identity plus changed keys; never echo the entire view.
                with (directory / name).open('x', encoding='utf-8') as stream:
                    json.dump(dict(member_id=member, edit_epoch=epoch, **changes), stream)
                return await exchange('ats-window-save', (member, epoch, name),
                                      'ats-window-result', 'result_file')

            view = await open_window()
            self.record('ats_window_view_items_percent_and_learning',
                [len(view[key]) for key in ('hp_slots', 'mp_slots', 'function_slots')] == [2, 2, 6]
                and [view[key][0].get('template') for key in ('hp_slots', 'mp_slots', 'function_slots')]
                    == [14, 14, 17]
                and all(view[key][1:] == [None] * (len(view[key]) - 1)
                        for key in ('hp_slots', 'mp_slots', 'function_slots'))
                and (view['hp_percent'], view['mp_percent']) == (50, 80)
                and {s['spell_row'] for s in view['learned_spells']} == {0, 2, 3}
                and all(isinstance(s.get('name'), str) and bool(s['name'])
                        and type(s.get('icon')) is int for s in view['learned_spells'])
                and not view.get('learned_spells_unknown') and owner_unchanged(), view=view)
            before = codec.decode_options(codec.unwrap_blob(bytes.fromhex(row()['companion_ats'])))
            result, feedback = await save_window(view['edit_epoch'],
                dict(hp_slots=[None, dict(template=14)], hp_percent=61))
            saved = json.loads(self.broker._ats_path.read_text(encoding='utf-8'))['characters'][str(member)]
            after = codec.decode_options(codec.unwrap_blob(bytes.fromhex(saved['companion_ats'])))
            self.record('ats_window_delta_saved_preserves_other_fields_and_knight',
                result.get('status') == feedback.get('status') == 'OK' and feedback.get('reason') == ''
                and saved['companion_ats'] == row()['companion_ats']
                and after['hp_percent'] == 61 and after['hp_slots'][1].get(4) == 14
                and all(after[key] == value for key, value in before.items()
                        if key not in ('hp_slots', 'hp_percent'))
                and feedback.get('view', {}).get('hp_slots') == [None, dict(template=14, name='빨간 물약')]
                and owner_unchanged(), result=result, feedback=feedback)
            buffs = [dict(slot) if slot is not None else None for slot in feedback['view']['buff_slots']]
            buffs[0] = dict(spell_row=2)  # learned Shield, existing buff slot
            result, feedback = await save_window(view['edit_epoch'], dict(buff_slots=buffs))
            decoded = codec.decode_options(codec.unwrap_blob(bytes.fromhex(row()['companion_ats'])))
            self.record('ats_window_learned_buff_saved',
                result.get('status') == feedback.get('status') == 'OK'
                and decoded['buff_slots'][0].get(1) == 1 and decoded['buff_slots'][0].get(4) == 2
                and feedback.get('view', {}).get('buff_slots', [{}])[0].get('spell_row') == 2
                and json.loads(self.broker._ats_path.read_text(encoding='utf-8'))['characters'][str(member)] == row()
                and owner_unchanged(), result=result, feedback=feedback)
            unchanged = self.broker._ats_path.read_bytes()
            member_before = dict(row())
            buffs[0] = dict(spell_row=1)  # mapped Light, absent from fixture learning
            result, feedback = await save_window(view['edit_epoch'], dict(buff_slots=buffs))
            self.record('ats_window_unlearned_buff_refused',
                result.get('status') == feedback.get('status') == 'REFUSED'
                and result.get('reason') == feedback.get('reason') == 'ATS_WINDOW_SPELL_NOT_LEARNED'
                and self.broker._ats_path.read_bytes() == unchanged and row() == member_before
                and owner_unchanged(), result=result, feedback=feedback)
            reopened = await open_window()
            self.record('ats_window_reopen_saved_view', reopened['edit_epoch'] != view['edit_epoch']
                and reopened['hp_percent'] == 61 and reopened['buff_slots'][0]['spell_row'] == 2)
            result, feedback = await save_window(view['edit_epoch'], dict(hp_percent=1))
            self.record('ats_window_stale_epoch_refused',
                result.get('status') == feedback.get('status') == 'REFUSED'
                and result.get('reason') == feedback.get('reason') == 'ATS_WINDOW_EDIT_EPOCH_MISMATCH'
                and self.broker._ats_path.read_bytes() == unchanged and row() == member_before
                and owner_unchanged(), result=result, feedback=feedback)
        finally:
            self.enable_settings = False

    def death_exp_rule(self):
        """The member's death applied the ordinary character EXP loss once."""
        from tools.local_original_session import world_reward
        rows = [r for r in self.broker._companion_death_penalties if r['character_id'] == self.member_id]
        last = rows[-1] if rows else None
        expected = None if last is None else world_reward.death_exp_penalty(last['old_exp'], data=self.world.data)
        self.record('member_death_ordinary_exp_loss_rule', last is not None
                    and (last['new_exp'], last['new_level']) == (expected.new_exp, expected.new_level)
                    and self.member.exp <= last['new_exp'] + 0 or False, deaths=len(rows), last=last,
                    note='fixture level <= 10 loses 0 by the same L1J-derived rule')

    async def pickup(self):
        """Natural kill/drop, finite F4 request, own bag and reconnect."""
        from tools.local_original_session import inventory
        self.stage = 'f4_pickup'
        await self.summon()
        await self.signal('movement-follow')
        target = await self.target()
        until = time.monotonic() + self.args.death_timeout
        while (entity := self.world.entities.get(target)) is not None and entity.alive:
            if time.monotonic() >= until:
                raise hs.Unconfirmed('PICKUP_NATURAL_KILL_DEADLINE')
            await self.owner_attack_current(target)
            await self.tick_wait(.05)
        # Ground is produced only by the actual kill; do not create test loot.
        items = [self.world.ground.get(e.ref) for e in self.world.entities.near(
            self.bot.map_id, *self.bot.position, 16) if e.kind.value == 'item']
        items = [item for item in items if item is not None]
        self.record('natural_kill_produced_ground', bool(items), target=target)
        item = min(items, key=lambda row: hb.distance(self.bot.position, (row.x, row.y)))
        while hb.distance(self.bot.position, (item.x, item.y)) > 0:
            if time.monotonic() >= until:
                raise hs.Unconfirmed('PICKUP_GROUND_APPROACH_DEADLINE')
            await self.bot.step((item.x, item.y))
            await self.tick_wait(.05)
        await self.wait_current('member_near_natural_ground', lambda:
            hb.distance(self.member_position(), (item.x, item.y)) <= 1, timeout=10)
        # Free the actual item cell so the follower must use its walk consumer.
        goal = next(((item.x+dx, item.y+dy) for dx, dy in hb.DELTAS
            if (item.x+dx, item.y+dy) != self.member_position()
            and self.travel_heading((item.x+dx, item.y+dy), 0) is not None), None)
        if goal is not None:
            while self.bot.position == (item.x, item.y):
                if time.monotonic() >= until:
                    raise hs.Unconfirmed('PICKUP_FREE_ITEM_TILE_DEADLINE')
                await self.bot.step(goal)
                await self.tick_wait(.05)
        await self.wait_current('member_adjacent_free_ground', lambda:
            self.member_position() != (item.x, item.y)
            and hb.distance(self.member_position(), (item.x, item.y)) <= 1, timeout=10)
        bags = self.broker._companion_inventory
        owner_before = self.broker._inventory_current_frame
        before = bags.frames[self.member_id]
        marker = self.bot.peer.ordinal
        _, result = await self.signal('f4-pickup', actor=False)
        self.record('f4_accepted_natural_ground', result.get('status') == 'QUEUED', result=result)
        await self.wait_current('member_consumes_one_natural_ground', lambda:
            any(e.get('event') == 'pickup' for e in bags.events), timeout=10)
        await self.bot.alive()
        event = next(e for e in reversed(bags.events) if e.get('event') == 'pickup')
        after = bags.frames[self.member_id]
        total = lambda frame: sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(frame)
                                  if r.template_bits == event['template'])
        self.record('f4_credits_only_member_and_retires_ground',
            total(after) - total(before) == event['count']
            and total(self.broker._inventory_current_frame) == total(owner_before)
            and self.world.entities.get(event['ground']) is None
            and bool(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid}))
            and bool(self.frames(marker, 0x4e40))
            and self.store.restore(self.member_id) == after, event=event,
            member_gain=total(after)-total(before), owner_gain=total(self.broker._inventory_current_frame)-total(owner_before),
            removed=self.world.entities.get(event['ground']) is None,
            walk_frames=len(self.frames(marker, 0x4e2c, **{'1': self.actor.ref.uid})),
            retire_frames=len(self.frames(marker, 0x4e40)), saved=self.store.restore(self.member_id) == after)
        _, again = await self.signal('f4-pickup', actor=False)
        await self.tick_wait(.4)
        self.record('same_consumed_ref_not_credited_twice',
            len([e for e in bags.events if e.get('event') == 'pickup'
                 and e.get('ground') == event['ground']]) == 1)
        character = self.bot.character
        await self.close()
        await self.open(seed=False, character=character)
        self.record('f4_member_bag_restored_after_reconnect',
            self.store.restore(self.member_id) == after
            and self.broker._companion_inventory.frames[self.member_id] == after)

    async def rules(self):
        await self.summon()
        await self.walk_speed()
        await self.bridge()
        await self.auto_resummon()
        await self.owner_death()
        await self.ats()
        await self.ats_edit()

    async def all(self):
        await self.summon()
        await self.follow_hold()
        await self.walk_speed()
        await self.bridge()
        await self.resummon()
        await self.exp()
        await self.combat_death()
        self.death_exp_rule()
        await self.revive()
        await self.combat_death(repeated=True)
        await self.teleport_scroll(23)
        await self.teleport_scroll(162)
        await self.reconnect()
        await self.revive()
        await self.auto_resummon()
        await self.selection()
        await self.owner_death()
        await self.ats()
        await self.ats_edit()
        # Keep the new learned-spell fixture out of every existing all-stage.
        # Reuse the normal harness in a fresh retained profile after closing it.
        await self.close()
        window_args = argparse.Namespace(**vars(self.args))
        window_args.scenario = 'ats_window'
        window_result = await run(window_args)
        self.stage = 'ats_window_isolated'
        self.record('ats_window_isolated_profile',
            True if window_result['status'] == 'SUCCESS' else
            None if window_result['status'] == 'UNCONFIRMED' else False, result=window_result)


def parser():
    result = hs.parser()
    result.description = __doc__
    # Existing harness options are retained, but only the complete companion
    # lifecycle is an executable scenario in this module.
    next(action for action in result._actions if action.dest == 'scenario').choices = (
        'all', 'magic', 'elemental', 'death_revive', 'travel', 'map_travel', 'map_travel_dead', 'equipment', 'selection',
        'rules', 'walk_speed', 'bridge', 'auto_resummon', 'owner_death', 'ats', 'ats_edit', 'ats_window', 'pickup')
    result.add_argument('--companion-revive-exp', action='store_true',
                        help='run404 experimental 4F16 in-place restore; default same-UID 4E96 replacement')
    result.add_argument('--fixture-level', type=int, choices=(1, 5), default=5,
                        help='pre-login mage fixture level; LOCAL pure growth from baseline HP12/MP8')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work' / 'local_original_session' / 'runs'
    root.mkdir(parents=True, exist_ok=True)
    # Python 3.13 Windows mode0700 temp directories exclude the managed
    # runner's inherited write identity. Keep normal workspace inheritance.
    directory = root / ('hunt-companion-' + uuid.uuid4().hex[:12])
    directory.mkdir()
    bridge_directory = directory / 'bridge-signals'
    bridge_directory.mkdir()
    with test_environment(magic=args.scenario == 'magic', revive_exp=args.companion_revive_exp,
                          map_exp=args.scenario in ('map_travel', 'map_travel_dead'),
                          bridge_directory=bridge_directory):
        scenario = CompanionScenario(args, directory)
        result = await scenario.run()
    result['scope'] = ('owned test profile, real FIRST/login/selection/socket router; LOCAL companion modes/reward, '
        'experimental run400 pet wire; native input/rendering unverified')
    result['fixture'] = dict(owner=scenario.owner_fixture, mage=scenario.fixture_growth,
        scope='fresh pre-login ProgressStore initialization; no live HP or clock forcing')
    result['elemental_samples'] = getattr(scenario, 'elemental_samples', None)
    result['navigation_observation'] = getattr(scenario, 'navigation_observation', None)
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
