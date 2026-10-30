"""Broker world integration checks prepared for an authorized test worker.

InjectedBrokerTests use real world/codec methods with in-memory ownership and
CAS collaborators. RegisteredMovementLoopbackTests starts a local broker at
the logical 12000/14030 endpoints; SL_TEST_PORT_BASE selects separate physical
ports. Keep those physical ports free. These tests do not establish native UI
parity.
"""
import asyncio
from dataclasses import replace
import os
import random
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker as b, inventory, restart, world_combat as wc
from tools.local_original_session import inventory_store
from tools.local_original_session import world_handlers as handlers, world_item_effects
from tools.local_original_session import world_reward, world_spawn_tests as spawn_tests
from tools.local_original_session import world_visibility as visibility
from tools.local_original_session.broker_tests import c2s, response
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import Group, InterestSpawner, Slot, SlotState
from tools.local_original_session.world_maps import TRANSITIONS
from tools.local_original_session.world_m1_reward_tests import enable_world_kit, status_values
from tools.local_original_session.world_progress import exp_percent
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_town import TownNpcs, attach_view, confirmed_npc_ids, load_town
from tools.local_original_session.world_bridge import Context


def opcode(frame):
    return int.from_bytes(frame[2:4], 'little')


def item_request(item_uid, *, raw0=True):
    """Reviewed 0960 raw0 body; malformed variant preserves its outer item UID."""
    params = pb.encode_message([pb.encode_uint32(1, 1), pb.encode_uint32(15, 0),
                                pb.encode_uint32(16, 0 if raw0 else 1)])
    body = pb.encode_message([pb.encode_uint32(1, item_uid), pb.encode_bytes(2, params)])
    return b.Frame(body, b.ITEM_USE_REQUEST, len(body) + 10)


class Terrain:
    def passable(self, *_):
        return True

    def can_step(self, *_):
        return True

    def bounds(self, map_id):
        return (90, 90, 110, 110) if map_id == 0 else None

    def can_stand(self, map_id, x, y):
        return map_id == 0 and 90 <= x <= 110 and 90 <= y <= 110


class InjectedBrokerTests(unittest.IsolatedAsyncioTestCase):
    """No socket/process: real adapter methods, injected selected owner and store."""

    async def asyncSetUp(self):
        self.now = 100.0
        data = replace(load_m1(), spawns=())
        runtime = WorldRuntime(clock=lambda: self.now)
        self.world = visibility.WorldView(runtime,
            InterestSpawner(runtime.entities, data, passable=lambda *_: True), Terrain(),
            data=data, rng=random.Random(7))
        attach_view(self.world, TownNpcs(self.world.entities, load_town()))
        fields = {1: 1, 2: 10, 4: 13, 5: 13, 6: 10, 7: 15, 8: 12, 9: 10,
                  10: 30, 11: 30, 12: 2, 13: 10, 14: -10,
                  15: 0, 16: 0, 17: 0, 18: 0, 20: 0}
        self.world.bind_pc(1, wc.PcProfile(10, 1, 0, 13, 13, weapon=wc.ATHAME,
                                         con=12, wis=15), fields)
        self.world.update_pc(1, 0, 100, 100, reset=True)
        self.writer = object()
        self.lock = asyncio.Lock()
        self.row = {'writer': self.writer, 'operation_lock': self.lock}
        self.position = SimpleNamespace(uid=1, name='SyntheticKnight', map_id=0,
                                        word0=100, word1=100)
        self.service = SimpleNamespace(snapshot=lambda: self.position, last_result=None)
        self.game = SimpleNamespace(selection=object(), received=AsyncMock(return_value=()))
        host = self.host = object.__new__(b.PersistentBroker)
        host._world = self.world
        host._world_pcs = {id(self.writer): (self.writer, 1)}
        host._world_handler_bindings = SimpleNamespace(town=self.world.town,
            wire=SimpleNamespace(), interaction_distance=3, sources={})
        host._world_handler_errors, host._world_item_errors = [], []
        host._world_progress_errors, host._world_ailments = [], {}
        host._world_death_risks = []
        host._world_respawn_errors = []
        host._world_respawn, host._world_relocations = {}, {}
        host._world_map_exp = 0
        host._world_names = {1: self.position.name}
        host.restart_policy = None
        # The real ProgressStore also owns optional bonus-stat rows (none here).
        host._world_progress = SimpleNamespace(commit=Mock(),
            bonus_stats=lambda uid: ((0,) * 6, (0,) * 6))
        host._world_events = {1: asyncio.Event()}
        host._inventory_kit_policy = inventory.KIT_POLICY
        self.profile_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.profile_directory.cleanup)
        profile = Path(self.profile_directory.name) / 'characters.json'
        b.ack.realm.CharacterStore(profile).create(
            b.ack.realm.Creation(self.position.name, 1, 0, (13, 13, 12, 15, 10, 10)))
        host._inventory_store = inventory_store.InventoryStore(
            profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        host._inventory_store.replace_kit = Mock(return_value=True)
        host._world_item_effects = world_item_effects.WorldItemEffects(self.world.combat,
                                                                       self.world.terrain)
        host._item_equipment_effect = None
        host._world_bound = Mock(return_value=True)
        host._world_ready = Mock(return_value=self.service)
        host._checkpoint = AsyncMock()
        host._world_send = AsyncMock()
        host.realm = SimpleNamespace(service=lambda writer: self.service,
            registry=SimpleNamespace(resolve=lambda writer: self.game),
            store=SimpleNamespace(select=lambda name: (1, {
                3: 1, 5: 0, 10: 10, 11: 13, 12: 13, 13: 12, 14: 15, 15: 10, 16: 10})))
        # This fixture bypasses PersistentBroker.__init__; initialize the same
        # optional hook owners that production prepares before requests.
        context = Context(host)
        host.realm._world_context = context
        with patch.dict(os.environ, {'SL_PET': '0', 'SL_COMPANION': '0'}):
            for name in ('_pet_initialize', '_companion_initialize',
                         '_world_dungeons_initialize', '_world_magic_initialize',
                         '_m5_initialize', '_ship_initialize'):
                getattr(context, name)()
        self.world.prepare_pc_attack = host._world_prepare_pc_attack
        self.world.on_pc_death = host._world_pc_died
        self.world.on_npc_hit = host._world_npc_hit

    def kit(self, *entries):
        """Synthetic owned ItemInfo rows, encoded/validated by the existing codec."""
        rows = []
        for uid, template, count in entries:
            row = dict(b.INVENTORY_STARTER_FIELDS)
            row.update({1: uid, 2: template, 4: count})
            rows.append(row)
        self.host._inventory_current_frame = inventory.build_kit_frame(rows)

    def target(self, x=101):
        original = load_m1()
        spec = original.spawns[0]
        monster = original.monsters[spec.template_id]
        target = self.world.entities.add(Kind.NPC, 0, x, 100, template_id=monster.template_id)
        slot = Slot(0, SlotState.ALIVE, target.uid, 10000, (x, 100))
        self.world.spawner._slots[target.uid] = (Group(spec, monster, [slot], True), slot)
        return target, slot

    async def use(self, item_uid, **kwargs):
        async with self.lock:
            return await self.host._world_use_item(self.writer, self.row, self.game,
                                                  item_request(item_uid, **kwargs), self.lock)

    async def test_registered_move_dispatches_once_sends_frames_and_preserves_unknown_transition(self):
        trigger = next(iter(TRANSITIONS))
        queued = visibility.remove_frame(0x10000001)  # opaque prior visibility reply
        self.world._queue(1, queued)

        async def received(frame):
            self.assertEqual(frame.opcode, handlers.MOVE)
            self.service.last_result = dict(accepted=True)  # MovementService stores MoveResult.metadata()
            self.position = SimpleNamespace(uid=1, name='SyntheticKnight', map_id=trigger[0],
                                             word0=trigger[1], word1=trigger[2])
            return ()

        self.game.received.side_effect = received
        move = b.Frame(b'owned-movement-body', handlers.MOVE, 29)
        with patch.object(handlers, 'dispatch', wraps=handlers.dispatch) as dispatch:
            async with self.lock:
                self.assertTrue(await self.host._world_dispatch(
                    self.writer, self.row, self.game, move, self.lock))
            dispatch.assert_awaited_once()
        self.game.received.assert_awaited_once()
        self.host._world_send.assert_awaited_once_with(self.writer, self.row, (queued,), self.lock)
        self.assertEqual(self.world.pcs[1], trigger)
        self.assertIn('MAP_TRANSITION_NATIVE_PUBLICATION_UNKNOWN', self.host._world_handler_errors)
        self.assertNotIn(0x4e95, [opcode(w) for w in self.host._world_send.await_args.args[2]])
        self.host._world_send.reset_mock()
        async with self.lock:
            self.assertFalse(await self.host._world_dispatch(self.writer, self.row, self.game,
                b.Frame(b'', 0x7fff, 10), self.lock))
        self.host._world_send.assert_not_awaited()

    async def test_item_raw0_save_precedes_effect_and_failed_save_has_no_reply(self):
        self.kit((1001, 14, 2), (1002, 7, 5))
        state = self.world.combat.pcs[1]
        state.hp = 1
        before = self.host._inventory_current_frame
        events = []

        def save(*args):
            self.assertEqual(state.hp, 1)
            self.assertEqual(args[:2], (1, before))
            events.append('save')
            return True

        self.host._inventory_store.replace_kit.side_effect = save
        original_use = self.host._world_item_effects.use

        def effect(*args, **kwargs):
            self.assertEqual(events, ['save'])
            events.append('effect')
            return original_use(*args, **kwargs)

        with patch.object(self.host._world_item_effects, 'use', side_effect=effect):
            self.assertTrue(await self.use(1001))
        self.assertEqual(events, ['save', 'effect'])
        self.assertGreater(state.hp, 1)
        sent = self.host._world_send.await_args.args[2]
        self.assertEqual([opcode(w) for w in sent], [0x0965, 0x4ed8, 0x4e38])  # 4ED8 use effect
        self.host._world_send.reset_mock()
        state.hp = 1
        current = self.host._inventory_current_frame
        self.host._inventory_store.replace_kit.side_effect = ValueError('SYNTHETIC_SAVE_FAILURE')
        with patch.object(self.host._world_item_effects, 'use', wraps=original_use) as use:
            with self.assertRaisesRegex(ValueError, 'SYNTHETIC_SAVE_FAILURE'):
                await self.use(1001)
            use.assert_not_called()
        self.assertEqual(state.hp, 1)
        self.assertEqual(self.host._inventory_current_frame, current)
        self.host._world_send.assert_not_awaited()

    async def test_item_unsupported_falls_through_bad_raw0_refuses_and_speed_expires(self):
        haste = next(definition for definition in self.host._world_item_effects.definitions.values()
            if definition.kind == 'speed'
            and self.world.data.items[definition.buff_template_id].buff.kind == 'haste')
        self.kit((1001, haste.template_id, 2), (1002, 7, 5))
        self.assertFalse(await self.use(1002))
        self.assertTrue(await self.use(1001, raw0=False))
        self.host._inventory_store.replace_kit.assert_not_called()
        self.host._world_send.assert_not_awaited()
        self.assertTrue(await self.use(1001))
        sent = self.host._world_send.await_args.args[2]
        self.assertEqual([opcode(w) for w in sent],
                         [0x0965, 0x4ed8, 0x4e5b, 0x4e91])
        key = (1, 'haste')
        self.assertIn(key, self.world.buffs)
        catalog, image_key, _ = world_item_effects.CONSUMABLE_BUFF_ICONS[haste.template_id]
        self.assertEqual(sent[-1], world_item_effects.buff_icon_frame(
            catalog, image_key, self.world.buffs[key].at - self.now))
        self.now = self.world.buffs[key].at
        self.world.runtime.scheduler.run_due(self.now)
        self.assertNotIn(key, self.world.buffs)
        expired = [w for w in self.world.drain(1) if opcode(w) == 0x4e5b]
        self.assertEqual(len(expired), 1)
        self.assertEqual(self.world.combat.speed_factor(1, self.now), 1.0)

    async def test_arrow_cost_quantity_last_stack_shortage_and_cooldown(self):
        from tools.local_original_session import equipment_store
        bow = self.world.data.items[11]
        saved_equipment = equipment_store.EquipmentStore(self.host._inventory_store,
            policy=equipment_store.POLICY, kit_policy=inventory.KIT_POLICY,
            item_defs=self.world.data.items)
        self.host._item_equipment_effect = SimpleNamespace(
            combat_inputs=lambda uid: (bow, 0), store=saved_equipment)
        target, slot = self.target(x=103)
        self.kit((1001, 29, 2), (1002, 7, 5))
        frames = self.world.pc_attack(1, target.uid)
        self.assertEqual([opcode(w) for w in frames], [0x0965, 0x4e31])
        from tools.local_original_session.hunt_bot import fields, scalar
        notification = fields(frames[-1][4:-2])
        self.assertEqual([scalar(notification, n) for n in (1, 6, 7, 13, 14)], [1, 0, 66, 1, 1])
        hp_after_swing = slot.hp
        prep = self.host._world_prepare_pc_attack(1, target, self.now)
        self.assertIsNotNone(prep.arrow)
        self.assertEqual([opcode(w) for w in self.world.drain(1)], [0x0978])
        saves = self.host._inventory_store.replace_kit.call_count
        self.assertIsNone(self.host._world_prepare_pc_attack(1, target, self.now))
        self.assertEqual(self.host._inventory_store.replace_kit.call_count, saves)
        self.assertEqual(self.world.drain(1), [])
        self.kit((1001, 29, 1), (1002, 7, 5))
        self.world.combat.pcs[1].next_attack_at = self.now + 10
        self.assertEqual(self.world.pc_attack(1, target.uid), [])
        self.assertEqual(self.host._inventory_store.replace_kit.call_count, saves)
        self.assertEqual(slot.hp, hp_after_swing)

    async def test_return_and_random_refresh_map_after_cost(self):
        from tools.local_game_session import session
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        from tools.local_original_session.world_status_frames import full_status_frame
        host = self.host
        host.realm._world_frames = {}

        def frames_for(position, *, status_fields, heading):
            def frame(opcode, values):
                body = session.world.encode_payload(opcode, values)
                return ((len(body) + 6).to_bytes(2, 'little')
                        + opcode.to_bytes(2, 'little') + body + b'\0\0')
            fields = dict(actor_hook.profiles()[0].fields)
            fields.update(status_fields)
            fields[1] = position.uid
            actor = dict(visibility.MONSTER_BASE_FIELDS)
            actor.update({1: position.packed, 2: position.uid, 3: 61, 4: 0,
                          5: heading, 9: position.name, 16: True})
            return (frame(0x4e95, {1: position.map_id, 2: 0, 3: False, 4: False}),
                    full_status_frame(fields), frame(0x4e96, actor))

        host.realm._frames_for = frames_for
        for kind in ('return_town', 'random_teleport'):
            with self.subTest(kind=kind):
                definition = next(d for d in host._world_item_effects.definitions.values()
                                  if d.kind == kind)
                self.kit((1001, definition.template_id, 2), (1002, 7, 5))
                destination = world_item_effects.MapDestination(0, 105, 105, 5)
                result = world_item_effects.ItemEffectResult(definition.template_id,
                    definition.kind, 'destination_proposed', 1,
                    frames=(world_item_effects.teleport_effect_frame(1),), destination=destination)
                old = b.movement.Position(1, self.position.name, 0,
                                          self.position.word0, self.position.word1)
                saved = [old]
                def relocate(updated):
                    self.assertEqual(dict(inventory.validate_kit_frame(
                        host._inventory_current_frame)[0].raw_fields)[4], 1)
                    saved[0] = updated
                    self.position = updated
                self.service.relocate = Mock(side_effect=relocate)
                host.realm.serves_map = lambda map_id: map_id == 0
                host._selected_owner_current = Mock(return_value=True)
                host._world_map_transitions = 0
                host._prepare_restart = AsyncMock()
                host._world_leave = AsyncMock()
                with patch.object(host._world_item_effects, 'use', return_value=result):
                    self.assertTrue(await self.use(1001))
                frames = host._world_send.await_args.args[2]
                opcodes = [opcode(w) for w in frames]
                self.assertEqual(opcodes[:2], [0x0965, 0x4ed8])
                self.assertNotIn(0x4ee0, opcodes)
                self.assertLess(opcodes.index(0x4ed8), opcodes.index(0x4e95))
                self.assertLess(opcodes.index(0x4e95), opcodes.index(0x4e38))
                self.assertLess(opcodes.index(0x4e38), next(i for i, wire in enumerate(frames)
                    if opcode(wire) == 0x4e96
                    and session.world.decode_payload(0x4e96, wire[4:-2])[2] == 1))
                self.assertEqual((saved[0].word0, saved[0].word1), (105, 105))
                self.assertEqual(self.world.pcs[1], (0, 105, 105))
                host._prepare_restart.assert_not_awaited()
                host._world_leave.assert_not_awaited()
                self.assertEqual(host._world_relocations, {})
                self.assertEqual(host._world_map_transitions, 1)

    async def test_teleport_unknown_map_or_tile_refused_before_cost(self):
        host = self.host
        definition = next(d for d in host._world_item_effects.definitions.values()
                          if d.kind == 'return_town')
        self.kit((1001, definition.template_id, 2), (1002, 7, 5))
        host.realm.serves_map = lambda map_id: map_id == 0
        for map_id, x in ((1, 105), (0, 500)):
            with self.subTest(map_id=map_id, x=x):
                result = world_item_effects.ItemEffectResult(definition.template_id,
                    definition.kind, 'destination_proposed', 1,
                    destination=world_item_effects.MapDestination(map_id, x, 105, 5))
                with patch.object(host._world_item_effects, 'use', return_value=result):
                    self.assertTrue(await self.use(1001))
                self.assertIn('WORLD_MAP_KNOWN_DESTINATION_REQUIRED', host._world_item_errors)
        host._inventory_store.replace_kit.assert_not_called()
        host._world_send.assert_not_awaited()
        self.assertEqual(host._world_respawn, {})
        self.assertEqual(host._world_relocations, {})

    async def test_death_updates_exp_full_hp0_before_death_and_saves_progress(self):
        for level in (11, 30, 50, 65, 99):
            with self.subTest(level=level):
                # Stats projection can replace PcState with EquipmentPcState;
                # each death must act on the currently bound combat owner.
                state = self.world.combat.pcs[1]
                original = self.world.data.exp_for_level(level) + 100
                self.world.exp[1] = original
                state.profile = replace(state.profile, level=level)
                state.status_fields[2] = level
                expected = world_reward.death_exp_penalty(original, data=self.world.data)
                growth_rng = random.Random()
                growth_rng.setstate(self.world.combat.rng.getstate())
                expected_hp, expected_mp = world_reward.delevel_maxima(
                    world_reward.RewardPcState.from_combat(state, exp=original),
                    expected.new_level, growth_rng, data=self.world.data)
                state.hp, state.dead = 0, True
                self.host._world_progress.commit.reset_mock()
                self.world._queue(1, wc.status_frame(state.status_fields, 0))
                self.world._pc_died(1, self.now)
                frames = self.world.drain(1)
                self.assertEqual([opcode(w) for w in frames], [0x4e38, 0x4e39])
                fields = status_values(frames[0])
                self.assertEqual(fields[10], 0)
                self.assertEqual(fields[2], expected.new_level)
                self.assertAlmostEqual(fields[26], exp_percent(
                    self.world.data, expected.new_exp, expected.new_level))
                self.assertEqual((fields[11], fields[13]), (expected_hp, expected_mp))
                current = self.world.combat.pcs[1]
                self.assertEqual((current.profile.level, current.hp, current.dead),
                                 (expected.new_level, 0, True))
                self.assertEqual(self.host._world_progress_errors, [])
                self.host._world_progress.commit.assert_called_once()
                saved_uid, progress = self.host._world_progress.commit.call_args.args
                self.assertEqual((saved_uid, progress.exp, progress.level),
                                 (1, expected.new_exp, expected.new_level))
                self.assertEqual((progress.max_hp, progress.max_mp), (expected_hp, expected_mp))
                self.assertNotIn(1, self.world.progress_dirty)

    async def test_hpbar_default_silent_and_each_optin_queues_one_candidate(self):
        target, _ = self.target()
        self.world.visibility.known[1] = {target.uid}
        with patch.dict(os.environ, {'SL_EXPERIMENT_HPBAR': ''}):
            self.host._world_npc_hit(target.uid)
            self.assertEqual(self.world.drain(1), [])
        for mode, expected_opcode in (('1', 0x4f1a), ('2', 0x4f1a), ('3', 0x4ec8)):
            with self.subTest(mode=mode), patch.dict(os.environ, {'SL_EXPERIMENT_HPBAR': mode}):
                self.host._world_npc_hit(target.uid)
                frames = self.world.drain(1)
                self.assertEqual([opcode(w) for w in frames], [expected_opcode])
                self.assertEqual(status_values(frames[0])[1], target.uid)


class RegisteredMovementLoopbackTests(spawn_tests.BrokerWorldTests):
    """Future single-owner loopback run; inherited startup uses the real ctor."""
    test_quit_ack_then_late_alive_closes_normally = None
    test_walk_north_shows_mobs_and_walk_back_removes_them = None

    async def asyncSetUp(self):
        self.environment = patch.dict(os.environ, {'SL_WORLD_TOWN_CANDIDATES': '',
                                                    'SL_EXPERIMENT_HPBAR': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        await super().asyncSetUp()

    async def test_ctor_confirmed_town_and_registered_move_reaches_alive_once(self):
        town = self.broker._world.town
        # confirmed_npc_ids selects catalog identity only; TownConfig keeps the
        # scope check, so adjacent/special placements outside the town stay off.
        # Town setup adds inn, warehouse and merchant menu owners with explicit
        # service sprites; warehouse and LOCAL shop menus default to enabled.
        from tools.local_original_session import world_shop_menu, world_town_services
        service_ids = {source.placement_key[0]
                       for source in world_town_services.load_service_menus(town,
                           warehouse_experiment=bool(self.broker._world_warehouse_exp))
                       if source.stem in ('inn', 'storage')}
        shop_ids = (set() if self.broker._world_shop_experiment is None else
                    {source.placement_key[0] for source in world_shop_menu.load_menu_sources(
                        town, experiment=self.broker._world_shop_experiment)})
        confirmed = confirmed_npc_ids(town.data) | service_ids | shop_ids
        self.assertEqual({town.npc_for(e.uid).npc_id for e in town.entities
                          if town.npc_for(e.uid) is not None},
                         {npc.npc_id for npc in town.data.placements.values()
                          if npc.npc_id in confirmed and npc.scope == 'village'
                          and npc.spawn['count'] > 0})
        reader, writer = await self.selected()
        # Existing harness grants the actual current kit; no native admission claim.
        enable_world_kit(self.broker, 0)
        server_writer = self.broker._claims[12000][-1]['writer']
        service = self.broker.realm.service(server_writer)
        start = service.snapshot()
        payload = pb.encode_message([pb.encode_uint32(1, start.packed), pb.encode_uint32(2, 0)])
        with patch.object(handlers, 'dispatch', wraps=handlers.dispatch) as dispatch:
            writer.write(c2s(handlers.MOVE, payload))
            writer.write(c2s(b.ALIVE_REQUEST))
            await writer.drain()
            while await response(reader) != b.ALIVE_FRAME:
                pass  # existing town entry/AI packets may precede the barrier
            dispatch.assert_awaited_once()
        current = service.snapshot()
        self.assertEqual((current.map_id, current.word0, current.word1),
                         (start.map_id, start.word0, start.word1 - 1))
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())


class MapExperimentLoopbackTests(unittest.IsolatedAsyncioTestCase):
    """LOCAL candidates through FIRST/selection/router; no native screen claim."""

    async def experiment(self, mode, origin=None, *, earned_exp=0):
        from tools.local_original_session import hunt_bot as hb, hunt_bot_scenarios as scenarios
        root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
        root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=f'map-exp{mode}-', dir=root))
        args = scenarios.parser().parse_args([])
        scene = scenarios.Scenario(args, 'map_experiment', directory)
        with patch.dict(os.environ, {'SL_EXPERIMENT_MAP': str(mode)}):
            # Fixture-only start position before FIRST/login; no selected live
            # position, readiness, response or transition result is forced.
            if origin is not None:
                broker, _, _ = await scenarios.build_epoch(directory, str(uuid.uuid4()), seed=True)
                try:
                    terrain = broker._world.terrain
                    map_id, x, y = origin
                    starts = [(x - dx, y - dy, h) for h, (dx, dy) in enumerate(hb.DELTAS)
                              if terrain.can_stand(map_id, x - dx, y - dy) is True]
                    self.assertTrue(starts, origin)
                    sx, sy, heading = starts[0]
                    from tools.local_original_session.hunt_bot_loopback import START, KNIGHT
                    old = broker.realm.positions.restore(b.movement.Position(1, KNIGHT[0], 0, *START))
                    broker.realm.positions.commit(old, b.movement.Position(1, old.name, map_id, sx, sy),
                                                   transition=True)
                    if earned_exp:
                        from tools.local_original_session.world_progress import Progress
                        broker._world_progress.commit(1, Progress(earned_exp, 1, 20, 10))
                finally:
                    closed = await broker.close()
                    self.assertTrue(closed['cleanup_complete'], closed)
                try:
                    await scene.open(seed=False)
                except BaseException:
                    await scene.close()
                    print(f'MAP_OPEN_FAILED ORIGIN={origin} EPOCHS={scene.epochs} CHECKS={scene.checks}')
                    raise
            else:
                try:
                    await scene.open(seed=True)
                except BaseException:
                    await scene.close()
                    raise
            try:
                bot = scene.bot
                if earned_exp:
                    self.assertEqual(scene.broker._world.exp[bot.self_uid], earned_exp)
                    self.assertGreater(scene.broker._world.combat.pcs[bot.self_uid].status_fields[26], 0)
                marker = bot.peer.ordinal
                if origin is None:
                    uid = next(uid for uid, row in bot.inventory.items() if row[2] == 162)
                    params = hb.uint(1, 1) + hb.uint(15, 0) + hb.uint(16, 0)
                    await bot.peer.request(0x0960, hb.uint(1, uid) + hb.pb.encode_bytes(2, params),
                        check=lambda batch: hb.find(batch, 0x4e96, **{'2': bot.self_uid}))
                    town = bot.data.town
                    expected = (town.map_id, town.respawn_x, town.respawn_y)
                else:
                    destination = TRANSITIONS[origin].destination
                    expected = (destination.map_id, destination.x, destination.y)
                    await bot.peer.request(handlers.MOVE, hb.uint(1, hb.pack(bot.position)) + hb.uint(2, heading),
                        alive=True, check=lambda batch: hb.find(batch, 0x4f57))
                frames = [f for f in bot.peer.frames if f.ordinal > marker]
                maps = [f for f in frames if f.opcode == 0x4e95]
                # Same-map relocation now republishes MapNotify in every mode.
                # MapExp3 retains its historical omission only for cross-map.
                self.assertEqual(len(maps), 0 if mode == 3 and origin is not None
                                 and origin[0] != expected[0] else 1)
                own = next(f for f in frames if f.opcode == 0x4e96 and hb.scalar(f.values, 2) == bot.self_uid)
                status = next(f for f in frames if f.opcode == 0x4e38 and hb.scalar(f.values, 1) == bot.self_uid)
                if earned_exp:
                    self.assertAlmostEqual(status_values(status.wire)[26],
                        exp_percent(bot.data, earned_exp, 1))
                self.assertLess(status.ordinal, own.ordinal)
                if maps:
                    self.assertLess(maps[0].ordinal, status.ordinal)
                surrounding = [f for f in frames if f.opcode == 0x4e96 and f is not own]
                self.assertTrue(all(f.ordinal > own.ordinal for f in surrounding))
                self.assertEqual((bot.map_id, *bot.position), expected)
                selected = scene.broker.realm.service(scene.broker._claims[12000][-1]['writer']).snapshot()
                saved = scene.broker.realm.positions.restore(selected)
                self.assertEqual((saved.map_id, saved.word0, saved.word1), expected)
                self.assertEqual(scene.broker._world.pcs[bot.self_uid], expected)
                self.assertEqual(scene.broker._world_map_transitions, 1)
                if mode == 2:
                    self.assertTrue(any(g.spec.map_id == 1 for g in scene.broker._world.spawner.groups))
                    self.assertTrue(any(g.spec.map_id == 2 for g in scene.broker._world.spawner.groups))
                # Follow the received arrival with an ordinary socket MOVE,
                # using a clear static edge away from another stair trigger.
                # This checks the restored movement owner, not native input.
                from tools.local_original_session.world_maps import resolve_transition
                choices = [(h, (expected[1] + dx, expected[2] + dy))
                           for h, (dx, dy) in enumerate(hb.DELTAS)
                           if scene.broker._world_edge_fallback(expected[0], *expected[1:], h) is True
                           and resolve_transition(expected[0], expected[1] + dx, expected[2] + dy) is None]
                self.assertTrue(choices, expected)
                move_heading, next_cell = choices[0]
                moved = await bot.peer.request(handlers.MOVE,
                    hb.uint(1, hb.pack(expected[1:])) + hb.uint(2, move_heading),
                    alive=True, check=lambda batch: hb.find(batch, 0x4f57))
                self.assertIsNone(hb.find(moved, 0x4ee0), moved)
                after_move = (expected[0], *next_cell)
                selected = scene.broker.realm.service(scene.broker._claims[12000][-1]['writer']).snapshot()
                saved = scene.broker.realm.positions.restore(selected)
                self.assertEqual((saved.map_id, saved.word0, saved.word1), after_move)
                self.assertEqual(scene.broker._world.pcs[bot.self_uid], after_move)
                character = bot.character
                self.assertTrue(await scene.close())
                await scene.open(seed=False, character=character)
                self.assertEqual((scene.bot.map_id, *scene.bot.position), after_move)
                if earned_exp:
                    self.assertEqual(scene.broker._world_progress.get(scene.bot.self_uid).exp, earned_exp)
                print(f'MAP_EXP={mode} ORIGIN={origin} DEST={expected} FRAMES=' +
                      ','.join(f'{f.opcode:04X}' for f in frames) +
                      f' MAP_FIELDS={[f.values for f in maps]} NEXT_MOVE={after_move} PROFILE={directory}')
            finally:
                self.assertTrue(await scene.close(), scene.epochs)

    async def test_same_map_baseline(self):
        await self.experiment(1)

    async def test_same_map_mode3_republishes_map_frame(self):
        await self.experiment(3)

    async def test_dungeon_each_direction(self):
        for origin in TRANSITIONS:
            with self.subTest(origin=origin):
                await self.experiment(2, origin)

    async def test_earned_experience_survives_map_transition_and_reconnect(self):
        await self.experiment(2, (0, 32478, 32851), earned_exp=37)


if __name__ == '__main__':
    unittest.main(verbosity=2)
