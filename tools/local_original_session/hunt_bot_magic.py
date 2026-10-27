"""Player M3 socket scenarios on declared, independent SoloMage test profiles.

All actions use FIRST/login/selection/world and the existing socket decoder,
router and feature handlers. Fixture initialization precedes login. The 10s
buff duration is an explicit LOCAL test setting; no clock/HP/MP is forced
after entry. No original client or user profile is opened.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import dataclasses
import hashlib
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


@contextmanager
def test_environment():
    settings = {'SL_PLAYER_MAGIC_BUFF_SECONDS': '10', 'SL_SPELL_EXP': '1',
                'SL_COMPANION': '0'}
    previous = {key: os.environ.get(key) for key in settings}
    try:
        os.environ.update(settings)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class MagicBot(hs.ScenarioBot):
    def __init__(self, args):
        super().__init__(args)
        self.mp = self.max_mp = self.ac = None
        self.dexterity = None
        self.spell_info = set()
        self.status_stage = False

    async def survive(self):
        if (self.status_stage and not self.dead and self.hp is not None
                and self.hp <= self.max_hp * self.args.potion_threshold):
            await self.potion()

    async def step(self, goal, radius=0):
        await self.survive()
        return await super().step(goal, radius)

    def apply(self, frame):
        if frame.opcode in (0x4e60, 0x4ed8, 0x4f25):
            frame.values = hb.fields(frame.wire[4:-2])
        super().apply(frame)
        if frame.opcode == 0x4e38 and hb.scalar(frame.values, 1) == self.self_uid:
            self.mp = hb.scalar(frame.values, 12, self.mp)
            self.max_mp = hb.scalar(frame.values, 13, self.max_mp)
            self.ac = hb.scalar(frame.values, 14, self.ac)
            self.dexterity = hb.scalar(frame.values, 5, self.dexterity)
            if self.ac is not None and self.ac >= 1 << 63:
                self.ac -= 1 << 64
        if frame.opcode == 0x4e60:
            for child in frame.values.get(1, ()):
                if isinstance(child, bytes):
                    spell = hb.fields(child)
                    if hb.scalar(spell, 2) == 1:
                        self.spell_info.add(hb.scalar(spell, 1))


class MagicScenario(hs.Scenario):
    def __init__(self, args, directory):
        super().__init__(args, 'magic', directory)
        self.fixture = None
        self.initial_profile_directory = directory
        self.profile_fixtures = []
        self.cast_observations = []
        self.magic_epochs = []
        self.melee_observations = []
        self.npc_magic_observations = []
        self.status_spawn_enabled = False
        self.broker_exception_observations = []

    def record(self, name, ok, **evidence):
        super().record(name, ok, **evidence)
        if ok is False and name not in ('cleanup', 'scenario_execution'):
            raise AssertionError(name)

    @property
    def world(self):
        return self.broker._world

    def initialize_mage_fixture(self):
        """Existing pure growth and store APIs, fresh profile before first login."""
        from tools.local_native_login_local_ack_hook import ack_enter_world as ack
        from tools.local_original_session import inventory, equipment_store, movement
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.hunt_bot_loopback import START
        from tools.local_original_session.world_combat import PcProfile
        from tools.local_original_session.world_progress import Progress
        from tools.local_original_session.world_reward import RewardPcState, on_kill
        data = load_m1()
        growth = json.loads((Path(__file__).parent / 'data/companion/mage_growth.json').read_text(encoding='utf-8'))
        attributes = growth['local_build']['creation_original_stats']
        stats = tuple(attributes[key] for key in ('STR', 'DEX', 'CON', 'WIS', 'CHA', 'INT'))
        uid, _, _ = self.broker.realm.store.create(ack.realm.Creation('SoloMage', 3, 0, stats))
        level = 30  # highest supplied ordinary EXP/growth row; no invented levels
        exp = data.pc_exp[level - 1]
        calculated = on_kill(RewardPcState(0, PcProfile(1, 3, 0, stats[0], stats[1],
            con=stats[2], wis=stats[3]), 12, 8),
            dataclasses.replace(data.monsters[0], kill_exp=exp), random.Random(0x4d334d47), data=data)
        self.broker._world_progress.commit(uid, Progress(exp, level, calculated.max_hp, calculated.max_mp))
        self.broker._world_progress.save_vitals(uid, (1, calculated.max_mp))
        fallback = movement.authority.unpack_grid(self.broker.realm._actor_fields[1])
        current = self.broker.realm.positions.restore(movement.Position(uid, 'SoloMage', 0, *fallback))
        self.broker.realm.positions.commit(current, movement.Position(uid, 'SoloMage', 0, *START))
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(self.broker._inventory_kit_frame(3))]
        for index, row in enumerate(rows):
            row[1] = 0x20000000 + uid * inventory.KIT_MAX_ITEMS + index
        # Preserve the product starter. Tier 3-5 books are an explicitly owned
        # pre-login test fixture, persisted by the same first-grant kit owner.
        catalog = json.loads((Path(__file__).parent / 'data/m3/player_spells.json').read_text(encoding='utf-8'))
        product_books = [row[2] for row in rows if row[2] in self.broker._world_magic.books]
        books = self.catalog_books(catalog) if self.args.scenario == 'all' else product_books
        added = []
        book_fields = next(row for row in rows if row[2] == 164)
        for book in books:
            if book in product_books:
                continue
            row = dict(book_fields)
            row.update({1: 0x20000000 + uid * inventory.KIT_MAX_ITEMS + len(rows),
                        2: book, 4: 1})
            # Packet tests consume template/owned UID/count. The retained book
            # icon remains LOCAL presentation metadata; no native render claim.
            rows.append(row)
            added.append(book)
        if self.args.scenario == 'all':
            catalyst = dict(book_fields)
            catalyst.update({1: 0x20000000 + uid * inventory.KIT_MAX_ITEMS + len(rows),
                             2: 166, 4: 50})
            rows.append(catalyst)
        # The first learned book is deliberately the EquipmentStore anchor.
        # Its real removal must use the product's shared kit replacement and
        # preserve a valid saved anchor for the remaining bag on reconnect.
        heal_book = next(row for row in rows if row[2] == 164)
        rows = [heal_book] + [row for row in rows if row is not heal_book]
        frame = inventory.build_kit_frame(rows)
        self.store.grant(uid, frame)
        weapon = next(row for row in rows if data.items.get(row[2]) is not None
                      and data.items[row[2]].kind == 'weapon')
        armor = next(row for row in rows if data.items.get(row[2]) is not None
                     and data.items[row[2]].slot == 'armor')
        self.equipment.initialize_kit(uid, frame, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                                     weapon_uid=weapon[1], slots=((2, armor[1]),))
        # Positive Detection starts from a declared pre-login status fixture.
        # Its sole removal is the player's ordinary cast packet.
        self.broker._world_magic.state(uid).invisible_until = self.broker._world.runtime.clock() + 120
        self.fixture = dict(character_uid=uid, character='SoloMage', character_class=3,
            attributes=stats, level=level, exp=exp, initial_hp=1, initial_mp=calculated.max_mp,
            max_hp=calculated.max_hp, max_mp=calculated.max_mp, books=books,
            product_books=product_books, prelogin_test_books=added,
            prelogin_test_catalyst166=50 if self.args.scenario == 'all' else 0,
            armor_uid=armor[1], armor_template=armor[2],
            initial_invisible_seconds=120, weapon_uid=weapon[1], weapon_template=weapon[2],
            initial_equipment_anchor_uid=heal_book[1], initial_equipment_anchor_template=164,
            position=list(START), inventory_sha256=hashlib.sha256(frame).hexdigest(),
            scope='LOCAL pre-login Lv30/HP1/invisibility/equipment-anchor fixture; '
                  'product mage starter plus declared tier3-5 test books with owned UIDs; '
                  'saved body armor equipped; first-grant lifecycle unverified')

    async def open(self, *, seed, character=None):
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
        if self.args.scenario == 'all' and self.status_spawn_enabled:
            # Declare one ordinary empty spawn slot before login. The existing
            # interest/spawn owner alone allocates its EntityRef, HP and timers.
            # The retained skeleton definition is unchanged; the known orc
            # rectangle keeps this spell test inside the existing walk route.
            from tools.local_original_session.world_interest_spawn import Group, Slot
            data = self.world.data
            original = next(spec for spec in data.spawns if spec.template_id == 29)
            nearby = next(spec for spec in data.spawns if spec.group_id == 'm1_orc')
            declared = dataclasses.replace(original, group_id='test_magic_undead29',
                rect=nearby.rect, target_count=1)
            self.world.data = dataclasses.replace(data, spawns=data.spawns + (declared,))
            self.world.spawner.groups.append(Group(declared, data.monsters[29], [Slot(0)]))
            spawn_fixture = dict(group_id=declared.group_id, template_id=29,
                l1j_npcid=data.monsters[29].l1j_npcid, original_group=original.group_id,
                original_rect=dataclasses.asdict(original.rect),
                trial_rect=dataclasses.asdict(declared.rect), trial_count=1,
                placement='normal InterestSpawner empty slot; pre-login declaration only',
                reason='known orc route; existing undead29 and unchanged full drops; '
                       'undead27 retained failure references missing ground graphic23')
        # build_epoch's older melee fixture overwrites AC with 10 + armour.
        # Retain the actual product stats projection so Shield and Bless Armor
        # reach both combat AC and SC_STATUS for the saved worn armor.
        self.broker._world_pc_profile = type(self.broker)._world_pc_profile.__get__(self.broker)
        if seed:
            self.initialize_mage_fixture()
        if self.args.scenario == 'all' and self.status_spawn_enabled:
            self.fixture['prelogin_test_undead_spawn'] = spawn_fixture
        if seed:
            self.profile_fixtures.append(dict(profile_path=str(self.directory),
                scope='new eleven status spells' if self.status_spawn_enabled else 'existing spells',
                fixture=self.fixture))
        # Reuse Lane4's saved-equipment-only socket fixture boundary. The
        # production kit replacement owner needs the real equipment/bank stores
        # to move a removed anchor atomically; no native preparation is claimed.
        from tools.local_original_session import inventory
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        from tools.local_original_session.world_warehouse import WarehouseStore
        effect = object.__new__(ItemEquipmentEffect)
        effect.store, effect._defs = self.equipment, self.broker._world.data.items
        effect._kit_policy, effect._collection_policy = inventory.KIT_POLICY, None
        effect._selection, effect._last = None, dict(status='FIXTURE_SAVED_EQUIPMENT_ONLY')
        self.broker._item_equipment_effect = effect
        self.broker._world_warehouse_store = WarehouseStore(self.store)
        # Read-only observation of the product's actual swing. Clone the RNG
        # state for a base-profile comparison, without advancing its owner or
        # changing admission, RNG, returned damage, HP or downstream handling.
        from tools.local_original_session import world_combat
        combat, original_swing = self.world.combat, self.world.combat.try_pc_swing
        def observed_swing(uid, monster, now, **kwargs):
            pc = combat.pcs.get(uid)
            clone = random.Random()
            clone.setstate(combat.rng.getstate())
            baseline = None if pc is None else world_combat.pc_hits_npc(
                pc.profile, monster, clone, arrow=kwargs.get('arrow'))
            actual = original_swing(uid, monster, now, **kwargs)
            if actual is not None:
                self.melee_observations.append(dict(uid=uid, at=now,
                    baseline=dataclasses.asdict(baseline), actual=dataclasses.asdict(actual),
                    buffs=sorted(self.engine.state(uid).buffs)))
            return actual
        combat.try_pc_swing = observed_swing
        for action in ('npc_step', 'npc_attack'):
            original = getattr(self.world, action)
            def observe(*values, _original=original, _action=action):
                entity = values[0]
                now = self.world.runtime.clock()
                self.npc_magic_observations.append(dict(action=_action, uid=entity.uid, at=now,
                    effects={kind: dict(row) for kind, row in
                        self.engine.npc_statuses.get(entity.uid, {}).get('effects', {}).items()
                        if row['starts_at'] <= now
                        and (row['until'] is None or now < row['until'])}))
                return _original(*values)
            setattr(self.world, action, observe)
        await self.broker.start()
        options = hb.parser().parse_args(['--expected-uuid', expected, '--minutes', str(self.args.minutes),
            '--timeout', str(self.args.timeout), '--potion-threshold', str(self.args.potion_threshold)])
        options.port, options.character = test_ports.port(options.port), 'SoloMage'
        self.bot = MagicBot(options)
        self.bot.status_stage = self.status_spawn_enabled
        self.bots.append(self.bot)
        from tools.local_original_session.game_data import load_m1
        self.bot.data, self.bot.started = self.world.data, time.monotonic()
        await self.bot.login()
        if not self.bot.inventory_received:
            await self.bot.peer.wait(0, lambda batch: hb.find(batch, 0x0964), 'FIXTURE_KIT_DELIVERY')

    async def close(self):
        if self.broker is not None:
            engine = getattr(self.broker, '_world_magic', None)
            self.magic_epochs.append(dict(
                profile_path=str(self.directory),
                errors=list(getattr(self.broker, '_world_magic_errors', ())),
                events=list(getattr(self.broker, '_world_magic_events', ())),
                learned={} if engine is None else
                    {str(uid): sorted(state.learned) for uid, state in engine.states.items()}))
        before = len(self.epochs)
        result = await super().close()
        for epoch in self.epochs[before:]:
            epoch['profile_path'] = str(self.directory)
        return result

    @staticmethod
    def catalog_books(catalog):
        return [row['player_policy']['book_classic_key'] for row in catalog['spells']
                if row['player_policy'].get('book_classic_key') is not None]

    def frames(self, marker, opcode, **wanted):
        return [frame for frame in self.bot.peer.frames if frame.ordinal > marker
                and frame.opcode == opcode and all(hb.scalar(frame.values, int(key)) == value
                                                  for key, value in wanted.items())]

    async def wait_current(self, label, predicate, *, timeout=None):
        until = time.monotonic() + (self.args.timeout if timeout is None else timeout)
        while not predicate():
            if self.bot.dead:
                raise hs.Unconfirmed('PLAYER_DIED:' + label)
            await self.bot.survive()
            if time.monotonic() >= until:
                raise hs.Unconfirmed('OBSERVATION_TIMEOUT:' + label)
            if time.monotonic() - self.bot.last_alive >= .5:
                await self.bot.alive()
            await asyncio.sleep(.05)
        await self.bot.alive()

    async def ready_status_resources(self, spell):
        """Recover at the received safe start before selecting a live target."""
        await self.bot.survive()
        state = self.world.combat.pcs[self.bot.self_uid]
        hp_cost = (spell.raw.get('hp_cost') or {}).get('value') or 0
        needed = spell.mp
        if state.mp < needed or state.hp <= hp_cost:
            from tools.local_original_session.hunt_bot_loopback import START
            await self.navigate(START)
        await self.wait_current('safe_status_resources_' + spell.name,
            lambda: state.mp >= needed and state.hp > hp_cost
                and self.world.runtime.clock() >= self.magic_state.next_cast_at, timeout=360)

    async def target_for(self, spell, *, templates=None):
        await self.ready_status_resources(spell)
        return await self.target(spell.range, templates=templates)

    def travel_heading(self, goal, radius):
        """Existing terrain path decision, with every move still sent normally."""
        from tools.local_original_session.npc_ai import bounded_path_step, DELTAS
        bot, terrain, now = self.bot, self.world.terrain, time.monotonic()
        occupied = {(entity.x, entity.y) for entity in self.world.entities.near(
            bot.map_id, *bot.position, 16, alive_only=False)
            if entity.uid != bot.self_uid and entity.kind.value != 'item'}

        def can_step(x, y, heading):
            dx, dy = DELTAS[heading]
            point = (x + dx, y + dy)
            return (terrain.can_step(bot.map_id, x, y, heading) is True and point not in occupied
                    and bot.safe_hunt_cell(point)
                    and bot.blocked_edges.get(((x, y), heading), 0) <= now)
        return bounded_path_step(bot.position,
            lambda x, y: hb.distance((x, y), goal) <= radius, goal, can_step)

    async def target(self, limit, *, templates=None):
        from tools.local_original_session.npc_ai import local_line_clear
        await self.wait_current('reuse_before_current_target_selection',
            lambda: self.world.runtime.clock() >= self.magic_state.next_cast_at)
        limit = max(1, limit - 1)
        until = time.monotonic() + self.args.navigation_timeout
        self.bot.heading = self.travel_heading
        while time.monotonic() < until:
            bot = self.bot
            if bot.dead:
                raise hs.Unconfirmed('MAGE_DIED_APPROACHING_MONSTER')
            await bot.survive()
            living = [(uid, row) for uid, row in bot.actors.items() if bot.hunt_target(row)
                      and (templates is None or row['template'] in templates)]
            admitted = [(uid, row) for uid, row in living
                if hb.distance(bot.position, row['position']) <= limit
                and local_line_clear(self.world.terrain, bot.map_id, *bot.position, *row['position'])]
            if admitted:
                return min(admitted, key=lambda pair: hb.distance(bot.position, pair[1]['position']))[0]
            if living:
                uid, row = min(living, key=lambda pair: hb.distance(bot.position, pair[1]['position']))
                await bot.step(row['position'], radius=max(1, limit - 2))
            else:
                groups = [group for group in bot.data.spawns if group.map_id == bot.map_id
                          and bot.data.monsters[group.template_id].level <= (bot.level or 1) + 3
                          and (templates is None or group.template_id in templates)]
                group = min(groups, key=lambda g: hb.distance(bot.position, (g.rect.x1, g.rect.y2)))
                await bot.step(((group.rect.x1 + group.rect.x2) // 2,
                               (group.rect.y1 + group.rect.y2) // 2), radius=2)
            if time.monotonic() - bot.last_alive >= .5:
                await bot.alive()
            await asyncio.sleep(.05)
        raise hs.Unconfirmed('CURRENT_NATURAL_MONSTER_TARGET_REQUIRED')

    @property
    def engine(self):
        return self.broker._world_magic

    @property
    def magic_state(self):
        return self.engine.states[self.bot.self_uid]

    @staticmethod
    def contains_spell(frame, key):
        return frame.opcode == 0x4e60 and any(isinstance(raw, bytes)
            and hb.scalar(hb.fields(raw), 1) == key
            and hb.scalar(hb.fields(raw), 2) == 1 for raw in frame.values.get(1, ()))

    async def learn(self, name):
        from tools.local_original_session import inventory
        spell = next(spell for spell in self.engine.spells.values() if spell.name == name)
        item_uid = next(uid for uid, fields in self.bot.inventory.items()
                        if fields.get(2) == spell.book and fields.get(4, 0) > 0)
        before = self.bot.inventory[item_uid][4]
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        marker = self.bot.peer.ordinal
        def learned(batch):
            changed = next((frame for frame in batch if frame.opcode in (0x0965, 0x0978)
                           and hb.scalar(frame.values, 1) == item_uid), None)
            available = next((frame for frame in batch if self.contains_spell(frame, spell.key)), None)
            return available if changed is not None else None
        await self.bot.peer.request(0x0960, hb.uint(1, item_uid) + hb.pb.encode_bytes(2, params),
                                    check=learned, label='BOOK_' + name)
        saved_frame = self.store.restore(self.bot.self_uid)
        saved_items = inventory.validate_kit_frame(saved_frame)
        saved = next((dict(item.raw_fields)[4] for item in saved_items
            if item.identifier == item_uid), 0)
        self.record('book_' + name + '_consumed_learned_and_saved',
            self.bot.inventory.get(item_uid, {}).get(4, 0) == saved == before - 1
            and spell.key in self.magic_state.learned and spell.key in self.bot.spell_info,
            book_template=spell.book, item_uid=item_uid, key=spell.key,
            before=before, after=saved, available_ordinals=[frame.ordinal for frame in
                self.bot.peer.frames if frame.ordinal > marker and self.contains_spell(frame, spell.key)])
        equipment = self.equipment.restore(self.bot.self_uid, saved_frame)
        self.record('book_' + name + '_saved_equipment_anchor_matches_current_bag',
            equipment.item_uid == saved_items[0].identifier
            and equipment.template == saved_items[0].template_bits
            and equipment.item_uid != self.fixture['initial_equipment_anchor_uid'],
            saved_anchor_uid=equipment.item_uid, saved_anchor_template=equipment.template,
            consumed_initial_anchor_uid=self.fixture['initial_equipment_anchor_uid'])
        return spell

    async def cast(self, spell, target):
        await self.wait_current('reuse_' + spell.name,
            lambda: self.world.runtime.clock() >= self.magic_state.next_cast_at)
        await self.wait_current('natural_mp_recovery_' + spell.name,
            lambda: self.world.combat.pcs[self.bot.self_uid].mp >= spell.mp, timeout=180)
        hp_cost = (spell.raw.get('hp_cost') or {}).get('value') or 0
        if hp_cost:
            await self.wait_current('natural_hp_recovery_' + spell.name,
                lambda: self.world.combat.pcs[self.bot.self_uid].hp > hp_cost, timeout=180)
        bot, marker = self.bot, self.bot.peer.ordinal
        state = self.world.combat.pcs[bot.self_uid]
        before_mp, before_hp = state.mp, state.hp
        materials = (spell.raw.get('materials') or {}).get('value') or []
        material_costs = {row['classic_item_key']: row['count'] for row in materials}
        material_before = {template: sum(row.get(4, 0) for row in bot.inventory.values()
            if row.get(2) == template) for template in material_costs}
        self.record('cast_' + spell.name + '_received_current_mp', bot.mp == before_mp,
                    mp=before_mp)
        slot = self.world.spawner.slot_for(target)
        before_npc_hp = None if slot is None else slot[1].hp
        payload = hb.uint(1, spell.key) + hb.pb.encode_bytes(2, hb.uint(1, target))
        # No guessed coordinate, success enum, or delay clock is supplied.
        batch = await bot.peer.request(0x4ee6, payload,
            check=lambda frames: hb.find(frames, 0x4e38,
                **({'1': bot.self_uid} if spell.kind == 'mana_drain' else
                   {'1': bot.self_uid, '12': before_mp - spell.mp})), label='CAST_' + spell.name)
        events = [event for event in self.broker._world_magic_events
                  if event.get('outcome') in ('cast', 'failed', 'countered') and event.get('key') == spell.key
                  and event.get('uid') == bot.self_uid]
        if not events:
            raise hs.Unconfirmed('CAST_EFFECT_EVENT_REQUIRED:' + spell.name)
        event = events[-1]
        after_slot = self.world.spawner.slot_for(target)
        after_npc_hp = None if after_slot is None else after_slot[1].hp
        observation = dict(profile_path=str(self.directory), spell=spell.name, key=spell.key, target=target,
            mp_before=before_mp, mp_after=state.mp, hp_before=before_hp, hp_after=state.hp,
            npc_hp_before=before_npc_hp, npc_hp_after=after_npc_hp,
            status_ordinals=[f.ordinal for f in batch if f.opcode == 0x4e38], event=dict(event),
            display_ordinals=[f.ordinal for f in batch if f.opcode in (0x4e31, 0x4ed8)])
        self.cast_observations.append(observation)
        self.record('cast_' + spell.name + '_actual_mp_debit',
            (event['mp_before'] - event['mp_after'] == spell.mp
             if spell.kind != 'mana_drain' else event['mp_after'] >= event['mp_before'] - spell.mp)
            and event['mp_after'] == bot.mp,
            **observation)
        if hp_cost:
            self.record('cast_' + spell.name + '_actual_hp_cost',
                before_hp - state.hp == hp_cost, hp_cost=hp_cost, **observation)
        if material_costs:
            from tools.local_original_session import inventory
            saved_items = inventory.validate_kit_frame(self.store.restore(bot.self_uid))
            received = {template: sum(row.get(4, 0) for row in bot.inventory.values()
                if row.get(2) == template) for template in material_costs}
            saved = {template: sum(dict(item.raw_fields)[4] for item in saved_items
                if item.template_bits == template) for template in material_costs}
            self.record('cast_' + spell.name + '_actual_catalyst_consumed_received_and_saved',
                received == saved == {template: material_before[template] - count
                                     for template, count in material_costs.items()},
                costs=material_costs, before=material_before, received=received, saved=saved)
        if spell.name == 'energy_bolt':
            killed = any(kill.npc_uid == target and kill.pc_uid == bot.self_uid
                         for kill in self.world.combat.kills)
            self.record('energy_bolt_actual_monster_hp_decrease_or_kill',
                before_npc_hp is not None and event['amount'] > 0 and
                ((after_npc_hp is not None and after_npc_hp < before_npc_hp) or killed),
                killed=killed, **observation)
        elif spell.name == 'heal':
            self.record('heal_actual_hp_increase', event['amount'] > 0 and state.hp > before_hp
                        and bot.hp == state.hp, **observation)
        return marker

    def effective_weapon(self):
        state = self.world.combat.pcs[self.bot.self_uid]
        return self.world.combat.magic_profile(self.bot.self_uid, state.profile,
                                               self.world.runtime.clock()).weapon

    async def melee(self, label, *, damage_bonus=0, target=None):
        if target is None:
            target = await self.target(1)
        bot = self.bot
        before = self.world.spawner.slot_for(target)[1].hp
        marker = bot.peer.ordinal
        observed = len(self.melee_observations)
        until = time.monotonic() + self.args.timeout
        while time.monotonic() < until:
            await bot.attack(target)
            await bot.alive()
            slot = self.world.spawner.slot_for(target)
            killed = any(k.npc_uid == target and k.pc_uid == bot.self_uid
                         for k in self.world.combat.kills)
            if killed or (slot is not None and slot[1].hp < before):
                paired = [row for row in self.melee_observations[observed:]
                          if row['actual']['landed'] and row['baseline']['landed']]
                if not paired:
                    target = await self.target(1)
                    before = self.world.spawner.slot_for(target)[1].hp
                    continue
                self.record(label, bool(self.frames(marker, 0x4e31,
                    **{'1': 1, '2': bot.self_uid, '3': target})) and bool(paired)
                    and all(row['actual']['damage'] == row['baseline']['damage'] + damage_bonus
                            for row in paired), target=target,
                    hp_before=before, hp_after=None if slot is None else slot[1].hp,
                    killed=killed, damage_bonus=damage_bonus, paired_actual_swings=paired,
                    effective_weapon=dataclasses.asdict(self.effective_weapon()))
                return
            if slot is None or hb.distance(bot.position, bot.actors[target]['position']) > 1:
                target = await self.target(1)
                before = self.world.spawner.slot_for(target)[1].hp
            await asyncio.sleep(.05)
        raise hs.Unconfirmed('ACTUAL_MELEE_DAMAGE_REQUIRED:' + label)

    async def magic(self):
        bot, uid = self.bot, self.bot.self_uid
        self.record('selected_real_mage_world_and_fixture',
            bot.character == 'SoloMage' and uid == self.fixture['character_uid']
            and bot.level == self.fixture['level'] and bot.sprite == 734
            and self.world.combat.pcs[uid].profile.character_class == 3
            and not self.magic_state.learned and self.broker._world_magic_store is not None,
            character=bot.character, uid=uid, level=bot.level, hp=bot.hp, mp=bot.mp,
            sprite=bot.sprite)
        expected = {book: 1 for book in self.fixture['books']} | {492: 20, 12273: 1}
        if self.fixture['prelogin_test_catalyst166']:
            expected[166] = self.fixture['prelogin_test_catalyst166']
        received = {template: sum(item.get(4, 0) for item in bot.inventory.values()
                    if item.get(2) == template) for template in expected}
        from tools.local_original_session import inventory
        saved_items = inventory.validate_kit_frame(self.store.restore(uid))
        saved = {template: sum(dict(item.raw_fields)[4] for item in saved_items
                 if item.template_bits == template) for template in expected}
        self.record('product_starter_and_declared_prelogin_test_books_received_and_saved',
            received == saved == expected, expected=expected, received=received, saved=saved)
        names = [self.engine.spells[key].name for key in range(16)]
        spells = {name: await self.learn(name) for name in names}
        self.record('all_sixteen_books_received_consumed_and_learned',
            self.magic_state.learned == set(range(16)) == bot.spell_info)
        await self.cast(spells['heal'], uid)
        if self.args.scenario == 'all':
            # All recovery tests share the declared HP1 pre-login fixture.
            # Do these before entering combat; no NPC/RNG damage setup occurs.
            for key in (18, 34):
                spell = await self.learn(self.engine.spells[key].name)
                state = self.world.combat.pcs[uid]
                self.record(spell.name + '_precombat_initial_hp_fixture_has_healing_room',
                    0 < state.hp < state.max_hp and self.bot.incoming_swings == 0,
                    hp=state.hp, max_hp=state.max_hp, initial_hp=self.fixture['initial_hp'],
                    incoming_swings=self.bot.incoming_swings)
                await self.cast(spell, uid)
                observation = self.cast_observations[-1]
                self.record(spell.name + '_actual_hp_heal_and_status',
                    observation['event']['amount'] > 0
                    and observation['hp_after'] > observation['hp_before']
                    and self.bot.hp == observation['hp_after'], **observation)
        before_invisible = self.engine.is_invisible(uid, self.world.runtime.clock())
        await self.cast(spells['detection'], uid)
        self.record('detection_removes_declared_prelogin_invisibility',
            before_invisible and not self.engine.is_invisible(uid, self.world.runtime.clock()))
        hp = self.world.combat.pcs[uid].hp
        buffs = dict(self.magic_state.buffs)
        await self.cast(spells['detection'], uid)
        self.record('detection_without_invisibility_only_spends_mp',
            not self.engine.is_invisible(uid, self.world.runtime.clock())
            and self.magic_state.buffs == buffs and self.world.combat.pcs[uid].hp == hp)
        for name in ('energy_bolt', 'ice_dagger', 'wind_cutter', 'fire_arrow', 'stalac', 'chill_touch'):
            target = await self.target_for(spells[name])
            await self.cast(spells[name], target)
            observation = self.cast_observations[-1]
            self.record(name + '_actual_monster_damage',
                observation['event']['amount'] > 0 and observation['npc_hp_before'] is not None
                and (observation['npc_hp_after'] is None
                     or observation['npc_hp_after'] < observation['npc_hp_before']))
            if name == 'chill_touch':
                self.record('chill_touch_actual_hp_drain',
                    observation['hp_after'] > observation['hp_before'], **observation)
        target = await self.target_for(spells['curse_poison'])
        await self.cast(spells['curse_poison'], target)
        self.record('curse_poison_applies_to_current_monster',
                    self.engine.is_poisoned(target, self.world.runtime.clock()), target=target)
        await self.cast(spells['cure_poison'], target)
        hp = self.world.spawner.slot_for(target)[1].hp
        await self.wait_current('cure_real_tick_window', lambda:
            self.world.runtime.clock() >= self.magic_state.next_cast_at + 2.3)
        slot = self.world.spawner.slot_for(target)
        self.record('cure_poison_removes_poison_and_stops_real_ticks',
            not self.engine.is_poisoned(target, self.world.runtime.clock())
            and slot is not None and slot[1].hp == hp, target=target, hp=hp)
        target = await self.target_for(spells['curse_poison'])
        await self.cast(spells['curse_poison'], target)
        before = self.world.spawner.slot_for(target)[1].hp
        await self.wait_current('curse_poison_real_tick', lambda:
            self.world.spawner.slot_for(target) is None
            or self.world.spawner.slot_for(target)[1].hp < before, timeout=8)
        slot = self.world.spawner.slot_for(target)
        self.record('curse_poison_real_tick_decreases_hp',
            slot is None or slot[1].hp < before, target=target, hp_before=before,
            hp_after=None if slot is None else slot[1].hp)
        await self.wait_current('curse_poison_lifetime', lambda:
            not self.engine.is_poisoned(target, self.world.runtime.clock()), timeout=12)
        self.record('curse_poison_expiry_or_lethal_cleanup',
            target not in self.engine.npc_poison, target=target,
            killed=any(k.npc_uid == target and k.pc_uid == uid for k in self.world.combat.kills))
        await self.melee('baseline_actual_melee_damage')
        base_weapon = self.effective_weapon()
        target = await self.target(1)
        await self.cast(spells['holy_weapon'], uid)
        holy_weapon = self.effective_weapon()
        self.record('holy_weapon_consumed_by_combat_hit_and_damage',
            holy_weapon.hit == base_weapon.hit + 1 and holy_weapon.damage == base_weapon.damage + 1,
            before=dataclasses.asdict(base_weapon), after=dataclasses.asdict(holy_weapon))
        await self.melee('holy_weapon_actual_melee_damage', damage_bonus=1, target=target)
        target = await self.target(1)
        # The explicit 10-second test duration can elapse while travelling to
        # another received monster. Refresh normally only after arriving.
        await self.cast(spells['holy_weapon'], uid)
        holy_weapon = self.effective_weapon()
        await self.cast(spells['enchant_weapon'], uid)
        enchanted = self.effective_weapon()
        self.record('enchant_weapon_consumed_by_combat_damage',
            enchanted.damage == holy_weapon.damage + 2,
            before=dataclasses.asdict(holy_weapon), after=dataclasses.asdict(enchanted))
        await self.melee('enchant_weapon_actual_melee_damage', damage_bonus=3, target=target)
        # Return by actual movement before checking real buff lifetime/reconnect.
        from tools.local_original_session.hunt_bot_loopback import START
        await self.navigate(START)
        baseline_ac = self.world.combat.pcs[uid].profile.ac
        writer = next(value[0] for value in self.broker._world_pcs.values() if value[1] == uid)
        position = self.broker.realm.service(writer).snapshot()
        before_capacity = self.broker._world_stats_for(position)[0].max_weight
        await self.cast(spells['decrease_weight'], uid)
        after_capacity = self.broker._world_stats_for(position)[0].max_weight
        self.record('decrease_weight_actual_capacity_increase',
            after_capacity == before_capacity + 180, before=before_capacity, after=after_capacity)
        await self.cast(spells['light'], uid)
        self.record('light_active_status', self.engine.is_lit(uid, self.world.runtime.clock())
                    and uid in self.world.light_sources)
        marker = await self.cast(spells['shield'], uid)
        self.record('shield_actual_ac_and_duration',
            self.world.combat.pcs[uid].profile.ac == baseline_ac - 2
            and bool(self.frames(marker, 0x4ed8, **{'1': uid, '2': 221})),
            base_ac=baseline_ac, buff_ac=self.world.combat.pcs[uid].profile.ac)
        # Refresh both weapon buffs so all five lifetimes are saved together.
        await self.cast(spells['holy_weapon'], uid)
        await self.cast(spells['enchant_weapon'], uid)
        learned, active = set(self.magic_state.learned), set(self.magic_state.buffs)
        self.record('five_buffs_active_before_quit', active == {1, 2, 7, 11, 13}, active=sorted(active))
        saved_path = self.broker._world_magic_store.path
        if not await self.close():
            raise hs.Unconfirmed('MAGIC_ACTIVE_BUFF_FIRST_CLOSE_FAILED')
        saved = json.loads(saved_path.read_text(encoding='utf-8'))
        saved_row = next(row for row in saved['rows'] if row['uid'] == uid)
        self.record('all_learned_and_five_buffs_saved_by_normal_quit',
            set(saved_row['learned']) == learned and len(saved_row['buffs']) == 5
            and all(0 < row['remaining'] <= 10 for row in saved_row['buffs']), saved=saved_row)
        await self.open(seed=False)
        self.record('all_learned_and_five_buffs_survive_first_reconnect',
            self.magic_state.learned == learned and learned <= self.bot.spell_info
            and set(self.magic_state.buffs) == active
            and self.world.combat.pcs[uid].profile.ac == baseline_ac - 2
            and self.engine.is_lit(uid, self.world.runtime.clock()))
        await self.wait_current('five_buffs_real_tick_expiry', lambda:
            not self.magic_state.buffs, timeout=15)
        self.record('all_five_buffs_expire_on_real_tick',
            self.world.combat.pcs[uid].profile.ac == baseline_ac
            and not self.engine.is_lit(uid, self.world.runtime.clock())
            and self.effective_weapon() == base_weapon
            and self.broker._world_stats_for(self.broker.realm.service(next(value[0]
                for value in self.broker._world_pcs.values() if value[1] == uid)).snapshot())[0].max_weight == before_capacity)
        if not await self.close():
            raise hs.Unconfirmed('MAGIC_EXPIRED_BUFF_SECOND_CLOSE_FAILED')
        await self.open(seed=False)
        self.record('expired_buffs_absent_on_second_reconnect',
            self.magic_state.learned == learned and not self.magic_state.buffs
            and learned <= self.bot.spell_info)
        if self.args.scenario == 'all':
            await self.expanded_magic()
        else:
            await self.verify_teleport(spells['teleport'])
        self.record('all_sixteen_spells_cast_via_normal_packets',
            {row['key'] for row in self.cast_observations if row['key'] < 16
             and row['profile_path'] == str(self.initial_profile_directory)} == set(range(16)),
            profile_path=str(self.initial_profile_directory))
        if self.args.scenario == 'all':
            self.record('all_thirty_eight_supported_spells_cast_across_two_declared_profiles',
                {row['key'] for row in self.cast_observations} == {
                    key for key, spell in self.engine.spells.items() if spell.kind != 'unsupported'},
                scope='two independent test profiles; no single-character continuity claim')
        self.record('magic_handler_errors_empty', not self.broker._world_magic_errors,
                    errors=self.broker._world_magic_errors)

    async def verify_teleport(self, spell):
        uid, before_position = self.bot.self_uid, self.bot.position
        marker = await self.cast(spell, uid)
        position = self.broker.realm.service(next(value[0] for value in self.broker._world_pcs.values()
                                                 if value[1] == uid)).snapshot()
        self.record('teleport_walkable_received_and_saved_arrival',
            self.bot.position != before_position and bool(self.frames(marker, 0x4ee0))
            and self.world.terrain.can_stand(self.bot.map_id, *self.bot.position) is True
            and (position.word0, position.word1) == self.bot.position,
            before=before_position, after=self.bot.position, map_id=self.bot.map_id,
            profile_path=str(self.directory))

    async def refused_request(self, label, opcode, payload, reason):
        """Liveness is the ordered barrier; it is never a spell success ACK."""
        from tools.local_original_session import inventory
        uid = self.bot.self_uid
        before = self.store.restore(uid)
        learned, reuse = set(self.magic_state.learned), self.magic_state.next_cast_at
        mp = self.world.combat.pcs[uid].mp
        await self.bot.peer.request(opcode, payload, alive=True,
            check=lambda batch: hb.find(batch, 0x4f57), label=label)
        self.record(label + '_refused_without_inventory_learning_mp_or_reuse_mutation',
            self.broker._world_magic_errors[-1:] == [reason]
            and self.store.restore(uid) == before and self.magic_state.learned == learned
            and self.magic_state.next_cast_at == reuse and self.world.combat.pcs[uid].mp == mp,
            reason=reason, saved_item_count=len(inventory.validate_kit_frame(before)),
            learned=sorted(learned), mp=mp)

    async def expanded_magic(self):
        uid = self.bot.self_uid
        spells = {}
        for key, spell in sorted(self.engine.spells.items()):
            if key >= 16 and spell.kind != 'unsupported':
                spells[key] = spell if key in self.magic_state.learned else await self.learn(spell.name)
        supported = {key for key, spell in self.engine.spells.items() if spell.kind != 'unsupported'}
        self.record('expanded_books_consumed_and_all_thirty_eight_learned',
            self.magic_state.learned == self.bot.spell_info == supported)
        params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
        for key, spell in sorted(self.engine.spells.items()):
            if spell.kind != 'unsupported':
                continue
            item_uid = next(item_uid for item_uid, row in self.bot.inventory.items()
                            if row.get(2) == spell.book and row.get(4, 0) == 1)
            await self.refused_request('unsupported_book_' + spell.name, 0x0960,
                hb.uint(1, item_uid) + hb.pb.encode_bytes(2, params), 'MAGIC_EFFECT_UNSUPPORTED')
        await self.refused_request('unknown_spell', 0x4ee6, hb.uint(1, 0xffffffff), 'MAGIC_UNKNOWN_SPELL')
        for key in (27, 33, 37, 16, 21, 24, 29):
            spell = spells[key]
            # Choose the current moving NPC only after reuse/resources are
            # ready, leaving one tile of range margin where the spell allows.
            target = await self.target_for(spell)
            # Observe current real monster slots before issuing the request.
            before = {entity.uid: slot[1].hp for entity in self.world.entities
                      if (slot := self.world.spawner.slot_for(entity.uid)) is not None}
            await self.cast(spell, target)
            observation = self.cast_observations[-1]
            decreases = {}
            for target_uid, hp in before.items():
                slot = self.world.spawner.slot_for(target_uid)
                after = 0 if slot is None else slot[1].hp
                if after < hp:
                    decreases[target_uid] = hp - after
            self.record(spell.name + '_actual_current_monster_damage',
                target in decreases and observation['event']['amount'] > 0,
                affected_monsters=decreases, **observation)
            if spell.kind == 'area_damage':
                self.record(spell.name + '_area_actual_hp_consumption',
                    sum(decreases.values()) == observation['event']['amount'],
                    affected_count=len(decreases), affected_monsters=decreases,
                    radius=spell.raw['player_policy']['area_radius'],
                    scope='socket current received targets; independent unit test covers multiple targets/exclusions')
            if spell.kind == 'drain':
                self.record(spell.name + '_drain_clamps_to_actual_monster_loss_and_pc_maximum',
                    observation['hp_after'] == min(self.world.combat.pcs[uid].max_hp,
                        observation['hp_before'] + observation['event']['amount']), **observation)
        from tools.local_original_session.hunt_bot_loopback import START
        await self.navigate(START)
        # Both 10s lifetimes must overlap through normal Quit/reconnect. Wait
        # for their combined actual MP before the first debit starts its clock.
        await self.wait_current('new_buffs_combined_natural_mp_recovery', lambda:
            self.world.combat.pcs[uid].mp >= spells[20].mp + spells[25].mp, timeout=180)
        base = self.world.combat.pcs[uid].profile
        await self.cast(spells[20], uid)
        armor_ac = self.world.combat.pcs[uid].profile.ac
        self.record('blessed_armor_bound_to_actual_equipped_uid_and_status_ac',
            self.magic_state.armor_uids.get(20) == self.fixture['armor_uid']
            and armor_ac == base.ac - 3 and self.bot.ac == -armor_ac,
            armor_uid=self.fixture['armor_uid'], base_ac=base.ac, buff_ac=armor_ac, status_ac=self.bot.ac)
        await self.cast(spells[25], uid)
        buffed = self.world.combat.pcs[uid].profile
        self.record('enchant_dexterity_reaches_actual_combat_profile_and_status',
            buffed.dexterity == base.dexterity + 5 and self.bot.dexterity == buffed.dexterity,
            base_dexterity=base.dexterity, buffed_dexterity=buffed.dexterity,
            status_dexterity=self.bot.dexterity)
        learned = set(self.magic_state.learned)
        saved_path = self.broker._world_magic_store.path
        if not await self.close():
            raise hs.Unconfirmed('NEW_BUFF_ACTIVE_FIRST_CLOSE_FAILED')
        saved = next(row for row in json.loads(saved_path.read_text(encoding='utf-8'))['rows'] if row['uid'] == uid)
        self.record('armor_and_dexterity_saved_with_exact_armor_uid',
            {row['spell'] for row in saved['buffs']} == {20, 25}
            and next(row for row in saved['buffs'] if row['spell'] == 20)['armor_uid'] == self.fixture['armor_uid'],
            saved=saved)
        await self.open(seed=False)
        self.record('new_buffs_and_all_learned_restore_by_first_login_world',
            set(self.magic_state.buffs) == {20, 25} and self.magic_state.learned == learned
            and self.bot.spell_info == learned
            and self.world.combat.pcs[uid].profile.ac == base.ac - 3
            and self.world.combat.pcs[uid].profile.dexterity == base.dexterity + 5
            and self.bot.dexterity == base.dexterity + 5)
        await self.wait_current('new_buffs_real_tick_expiry', lambda: not self.magic_state.buffs, timeout=15)
        self.record('new_buffs_real_expiry_restores_combat_status_and_clears_uid_binding',
            not self.magic_state.armor_uids and self.world.combat.pcs[uid].profile.ac == base.ac
            and self.world.combat.pcs[uid].profile.dexterity == base.dexterity
            and self.bot.ac == -base.ac and self.bot.dexterity == base.dexterity)
        if not await self.close():
            raise hs.Unconfirmed('NEW_BUFF_EXPIRED_SECOND_CLOSE_FAILED')
        await self.open(seed=False)
        self.record('new_buffs_absent_and_all_learning_preserved_on_second_login_world',
            not self.magic_state.buffs and not self.magic_state.armor_uids
            and self.magic_state.learned == self.bot.spell_info == learned)
        await self.verify_teleport(self.engine.spells[4])
        existing = set(range(16)) | {16, 18, 20, 21, 24, 25, 27, 29, 33, 34, 37}
        self.record('existing_twenty_seven_spells_complete_on_first_profile',
            {row['key'] for row in self.cast_observations
             if row['profile_path'] == str(self.initial_profile_directory)} == existing,
            profile_path=str(self.initial_profile_directory), spell_keys=sorted(existing))
        if not await self.close():
            raise hs.Unconfirmed('PRE_STATUS_FIXTURE_TRANSITION_CLOSE_FAILED')
        # The original profile's spent MP and saves remain intact. A separately
        # declared profile starts from the same ordinary Lv30 growth calculation.
        self.directory = self.initial_profile_directory / 'status-profile'
        self.directory.mkdir()
        self.status_spawn_enabled = True
        await self.open(seed=True)
        spells = {key: await self.learn(spell.name)
                  for key, spell in sorted(self.engine.spells.items()) if spell.kind != 'unsupported'}
        self.record('independent_status_profile_thirty_eight_books_learned',
            self.magic_state.learned == self.bot.spell_info == set(spells),
            profile_path=str(self.directory),
            scope='independent fresh growth fixture; original profile resources preserved')
        for key in (0, 18, 34):
            await self.cast(spells[key], self.bot.self_uid)
        await self.status_magic(spells)

    async def status_magic(self, spells):
        """New spells use current targets and resources; no live fixture edits."""
        uid = self.bot.self_uid
        from tools.local_original_session.hunt_bot_loopback import START
        await self.navigate(START)
        await self.ready_status_resources(spells[17])
        self.record('status_stage_safe_start_minimum_cast_resources_ready',
            self.bot.position == START
            and self.world.combat.pcs[uid].mp >= spells[17].mp,
            mp=self.world.combat.pcs[uid].mp, hp=self.world.combat.pcs[uid].hp)
        for key in (17, 22, 38):
            spell = spells[key]
            hp_cost = (spell.raw.get('hp_cost') or {}).get('value') or 0
            await self.ready_status_resources(spell)
            if key == 17:
                exp_before = self.world.exp[uid]
                references = self.engine.catalog['local_policy']['npc_status_reference']
                templates = {int(template) for template, row in references.items()
                             if row.get('undead') in (1, 3) and row.get('is_tu')}
                for attempt in range(8):
                    target = await self.target_for(spell, templates=templates)
                    await self.cast(spell, target)
                    if self.cast_observations[-1]['event']['outcome'] == 'cast':
                        break
                    await self.navigate(START)
                else:
                    raise hs.Unconfirmed('NATURAL_TURN_UNDEAD_SUCCESS_REQUIRED')
                self.record('turn_undead_actual_classified_undead_kill',
                    any(k.npc_uid == target and k.pc_uid == uid for k in self.world.combat.kills),
                    target=target, attempts=attempt + 1)
                kill = next(k for k in self.world.combat.kills
                            if k.npc_uid == target and k.pc_uid == uid)
                self.record('turn_undead_real_once_kill_experience_consumed',
                    self.world.exp[uid] == exp_before + kill.kill_exp,
                    exp_before=exp_before, exp_after=self.world.exp[uid], kill_exp=kill.kill_exp)
            else:
                for attempt in range(8 if key == 38 else 1):
                    mana_templates = ({template for template, monster in self.world.data.monsters.items()
                                       if monster.mp > 0} if key == 38 else None)
                    target = await self.target_for(spell, templates=mana_templates)
                    await self.cast(spell, target)
                    if self.cast_observations[-1]['event']['outcome'] == 'cast':
                        break
                else:
                    raise hs.Unconfirmed('NATURAL_STATUS_SUCCESS_REQUIRED:' + spell.name)
            observation = self.cast_observations[-1]
            self.record(spell.name + '_socket_result_and_actual_current_target',
                observation['event']['target'] == target, **observation)
            if key == 38:
                self.record('mana_drain_actual_hp_cost_and_capped_mp_gain',
                    observation['hp_before'] - observation['hp_after'] == hp_cost
                    and observation['mp_after'] <= self.world.combat.pcs[uid].max_mp
                    and observation['mp_after'] > observation['mp_before']
                    and observation['event']['amount'] > 0, **observation)
        for key in (19, 26, 28, 32, 39):
            spell = spells[key]
            for attempt in range(8):
                target = await self.target_for(spell)
                baseline_ai = self.world.magic_status(target, self.world.runtime.clock())
                await self.cast(spell, target)
                row = self.engine.npc_statuses.get(target, {}).get('effects', {}).get(spell.kind)
                if row is not None:
                    break
            else:
                raise hs.Unconfirmed('NATURAL_STATUS_SUCCESS_REQUIRED:' + spell.name)
            await self.wait_current('status_onset_' + spell.name,
                lambda: self.engine.status(target, spell.kind, self.world.runtime.clock()) is not None,
                timeout=12)
            self.record(spell.name + '_actual_current_npc_status',
                self.engine.status(target, spell.kind, self.world.runtime.clock()) is not None,
                target=target, effect_state=dict(row), attempts=attempt + 1)
            if key == 28:
                self.record('slow_reaches_actual_npc_ai_interval_consumer',
                    self.world.magic_status(target, self.world.runtime.clock())['move_factor']
                        == baseline_ai['move_factor'] * 2.0
                    and self.world.magic_status(target, self.world.runtime.clock())['attack_factor']
                        == baseline_ai['attack_factor'] * 2.0,
                    target=target, effect_state=dict(row),
                    scope='socket applied status; scheduler deadline behavior also checked by development test')
            if key == 32:
                start = self.world.runtime.clock()
                observed = len(self.npc_magic_observations)
                await self.wait_current('paralyze_actual_hold',
                    lambda: self.world.runtime.clock() >= min(start + 2, row['until'] - .1), timeout=4)
                actions = [item for item in self.npc_magic_observations[observed:]
                           if item['uid'] == target and item['at'] < row['until']]
                self.record('paralyzed_current_monster_no_move_or_attack', not actions,
                    target=target, observation_start=start, observation_end=self.world.runtime.clock(),
                    deadline=row['until'], actions=actions)
            if key in (19, 39):
                await self.cast(spells[36], target)
                self.record(spell.name + '_removed_by_actual_remove_curse_packet',
                    self.engine.status(target, spell.kind, self.world.runtime.clock()) is None,
                    target=target)
            elif key != 26:
                await self.wait_current('status_expiry_' + spell.name,
                    lambda: self.engine.status(target, spell.kind, self.world.runtime.clock()) is None,
                    timeout=15)
                self.record(spell.name + '_real_tick_expiry_or_target_lifetime_end',
                    self.engine.status(target, spell.kind, self.world.runtime.clock()) is None,
                    target=target, deadline=row['until'])
        from tools.local_original_session.hunt_bot_loopback import START
        await self.navigate(START)
        potions_before = self.bot.potions_used
        while self.world.combat.pcs[uid].hp < self.world.combat.pcs[uid].max_hp * .9:
            await self.bot.potion()
        self.record('meditation_safe_hp_prepared_by_owned_normal_potions',
            self.world.combat.pcs[uid].hp >= self.world.combat.pcs[uid].max_hp * .9,
            hp=self.world.combat.pcs[uid].hp, potions_used=self.bot.potions_used - potions_before)
        await self.cast(spells[31], uid)
        observation = self.cast_observations[-1]
        self.record('meditation_actual_hp_cost_and_active_recovery_status',
            observation['hp_before'] - observation['hp_after'] == 40
            and self.engine.status(uid, 'meditation', self.world.runtime.clock()) is not None,
            **observation)
        meditation = self.engine.status(uid, 'meditation', self.world.runtime.clock())
        due = meditation['params']['next_tick']
        before_mp = self.world.combat.pcs[uid].mp
        await self.wait_current('meditation_actual_mp_recovery',
            lambda: meditation['params']['next_tick'] > due, timeout=12)
        self.record('meditation_real_tick_consumes_recovery_and_clamps_actual_mp',
            self.world.combat.pcs[uid].mp >= before_mp,
            before=before_mp, after=self.world.combat.pcs[uid].mp, initial_due=due,
            next_due=meditation['params']['next_tick'],
            scope='actual meditation tick; ordinary recovery may also run')
        # A fresh normal cast supplies the short LOCAL lifetime for reconnect;
        # the first 10s lifetime has just completed its actual recovery tick.
        await self.cast(spells[31], uid)
        saved_path = self.broker._world_magic_store.path
        if not await self.close():
            raise hs.Unconfirmed('MEDITATION_ACTIVE_FIRST_CLOSE_FAILED')
        meditation_saved = next(row for row in json.loads(saved_path.read_text(encoding='utf-8'))['rows']
                                if row['uid'] == uid)
        self.record('meditation_saved_without_old_monotonic_tick',
            'meditation' in meditation_saved.get('statuses', {}).get('effects', {})
            and 'next_tick' not in meditation_saved['statuses']['effects']['meditation']['params'],
            saved=meditation_saved)
        await self.open(seed=False)
        meditation = self.engine.status(uid, 'meditation', self.world.runtime.clock())
        self.record('meditation_restored_on_real_reconnect', meditation is not None)
        await self.wait_current('meditation_reconnected_expiry',
            lambda: self.engine.status(uid, 'meditation', self.world.runtime.clock()) is None,
            timeout=15)
        self.record('meditation_real_expiry_after_reconnect',
            self.engine.status(uid, 'meditation', self.world.runtime.clock()) is None)
        await self.cast(spells[30], uid)
        self.record('counter_magic_actual_single_absorption_status',
            self.engine.status(uid, 'counter_magic', self.world.runtime.clock()) is not None,
            scope='socket cast; incoming damage-spell absorption is development-tested, no reflection')
        learned = set(self.magic_state.learned)
        active = set(self.magic_state.effects)
        saved_path = self.broker._world_magic_store.path
        if not await self.close():
            raise hs.Unconfirmed('NEW_STATUS_ACTIVE_FIRST_CLOSE_FAILED')
        saved = next(row for row in json.loads(saved_path.read_text(encoding='utf-8'))['rows']
                     if row['uid'] == uid)
        self.record('new_timed_statuses_saved_by_normal_quit',
            set(saved.get('statuses', {}).get('effects', {})) == active, saved=saved)
        await self.open(seed=False)
        self.record('new_timed_status_and_thirty_eight_learned_restore_on_login_world',
            set(self.magic_state.effects) == active
            and self.magic_state.learned == self.bot.spell_info == learned,
            active=sorted(active), learned=sorted(learned))
        await self.wait_current('new_status_real_tick_expiry',
            lambda: not self.magic_state.effects, timeout=15)
        self.record('new_timed_statuses_expire_after_reconnect', not self.magic_state.effects)
        expected = {17, 19, 22, 26, 28, 30, 31, 32, 36, 38, 39}
        self.record('new_eleven_spells_complete_on_independent_status_profile',
            expected <= {row['key'] for row in self.cast_observations
                         if row['profile_path'] == str(self.directory)},
            profile_path=str(self.directory), spell_keys=sorted(expected))


def parser():
    result = hs.parser()
    result.description = __doc__
    next(action for action in result._actions if action.dest == 'scenario').choices = ('magic', 'all')
    return result


async def run(args):
    root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='hunt-magic-', dir=root))
    source_paths = ['hunt_bot_magic.py', 'hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_loopback.py',
                    'world_magic.py', 'world_feature_magic.py', 'world_magic_status.py',
                    'npc_ai.py', 'world_combat.py',
                    'world_weight.py', 'world_stats.py', 'world_feature_stats.py',
                    'world_item_effects.py', 'world_handlers.py', 'broker.py',
                    'inventory.py', 'inventory_store.py', 'equipment_store.py', 'world_bridge.py',
                    'world_feature_kit.py', 'world_warehouse.py',
                    'item_equipment_effect.py', 'world_lane4_connection_tests.py',
                    'data/m3/player_spells.json']
    def sources():
        return {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in source_paths if (Path(__file__).parent / name).exists()}
    started_sources = sources()
    with test_environment():
        scenario = MagicScenario(args, directory)
        result = await scenario.run()
    result.update(scope='owned test profile; real FIRST/login/selection/world and socket decoder/router; '
        'LOCAL player spell policy and 10s buff duration; native input/rendering unverified',
        fixture=scenario.fixture, profile_fixtures=scenario.profile_fixtures,
        casts=scenario.cast_observations, magic_epochs=scenario.magic_epochs,
        actual_melee_swings=scenario.melee_observations,
        actual_npc_magic_actions=scenario.npc_magic_observations,
        broker_exception_observations=scenario.broker_exception_observations)
    result['profile_path'] = str(directory)
    if args.scenario == 'all':
        result['scope'] += '; two independent declared profiles: existing27 and new11; no single-character continuity claim'
    result['source_sha256_start'], result['source_sha256'] = started_sources, sources()
    result['source_changes_during_run'] = [name for name in source_paths
        if started_sources.get(name) != result['source_sha256'].get(name)]
    result['reused_from'] = {name: result['source_sha256'][name]
                           for name in ('hunt_bot.py', 'hunt_bot_scenarios.py', 'hunt_bot_loopback.py',
                                        'world_lane4_connection_tests.py')}
    (directory / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
