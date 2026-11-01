"""Pet lifecycle regression, reusing the existing single-owner socket bot.

Default discovery runs only development checks. For the real decoder/router
lifecycle, explicitly own the configured SL_TEST_PORT_BASE endpoints and set
SL_RUN_PET_INTEGRATION=1 (this merge verification uses 26000/28030).
The socket fixture and all failed results are retained by hunt_bot_pet.
"""
from __future__ import annotations

import os
import dataclasses
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


class PetHarnessTests(unittest.TestCase):
    def test_pet_travel_detours_beyond_short_ai_search_window(self):
        from types import SimpleNamespace
        from tools.local_original_session import hunt_bot as hb
        from tools.local_original_session.hunt_bot_pet import PetScenario, parser
        from tools.local_original_session.npc_ai import DELTAS, bounded_path_step
        def passable(map_id, x, y, direction):
            dx, dy = DELTAS[direction]
            dest = (x+dx, y+dy)
            return (-16 <= dest[0] <= 16 and -16 <= dest[1] <= 16
                    and not (dest[0] == 1 and -12 <= dest[1] <= 12))
        goal, start = (2, 0), (0, 0)
        self.assertIsNone(bounded_path_step(start,
            lambda x, y: (x, y) == goal, goal,
            lambda x, y, direction: passable(0, x, y, direction)))
        scenario = PetScenario(parser().parse_args([]), Path('.'))
        scenario.bot = SimpleNamespace(position=start, self_uid=1, map_id=0, level=6,
            blocked_edges={}, safe_hunt_cell=lambda point: True)
        scenario.broker = SimpleNamespace(_world=SimpleNamespace(
            terrain=SimpleNamespace(can_step=passable),
            entities=SimpleNamespace(near=lambda *args, **kwargs: [])))
        first = scenario.travel_heading(goal, 0)
        import time
        scenario.bot.blocked_edges[(start, first)] = time.monotonic()+60
        self.assertNotEqual(scenario.travel_heading(goal, 0), first)
        steps = 0
        while scenario.bot.position != goal and steps < 60:
            point = scenario.bot.position
            heading = scenario.travel_heading(goal, 0)
            self.assertIsNotNone(heading)
            self.assertTrue(passable(0, *point, heading))
            dx, dy = DELTAS[heading]
            scenario.bot.position = (point[0]+dx, point[1]+dy)
            steps += 1
        self.assertEqual(scenario.bot.position, goal)
        self.assertGreater(steps, hb.distance(start, goal))

    def test_command_uses_real_actor_uid_and_decimal_current_target(self):
        from tools.local_original_session import hunt_bot as hb
        from tools.local_original_session.hunt_bot_pet import command_payload
        uid, target = 0x10000311, 0x10000312
        message = hb.fields(command_payload(1, uid, target))
        self.assertEqual(hb.scalar(message, 1), 1)
        self.assertEqual(hb.scalar(message, 2), str(target).encode('ascii'))
        self.assertEqual(hb.scalar(message, 3), uid)
        for mode in range(2, 8):
            message = hb.fields(command_payload(mode, uid))
            self.assertEqual(set(message), {1, 3})
            self.assertEqual(hb.scalar(message, 1), mode)

    def test_invalid_wire_input_fails_before_dispatch(self):
        from tools.local_original_session.hunt_bot_pet import command_payload
        for args in ((0, 1), (8, 1), (True, 1), (2, True), (2, 0),
                     (2, 1 << 32), (1, 1), (1, 1, 0), (1, 1, True)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                command_payload(*args)

    def test_environment_restores_caller_configuration_on_failure(self):
        from tools.local_original_session.hunt_bot_pet import test_environment
        before = {key: os.environ.get(key) for key in
                  ('SL_PET', 'SL_COMPANION', 'SL_COMPANION_PET_UI')}
        with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            with test_environment(companion=True):
                self.assertEqual(os.environ['SL_PET'], '1')
                self.assertEqual(os.environ['SL_COMPANION'], '1')
                self.assertEqual(os.environ['SL_COMPANION_PET_UI'], '1')
                raise RuntimeError('fixture failure')
        self.assertEqual({key: os.environ.get(key) for key in before}, before)

    def test_disabled_feature_never_constructs_pet_state(self):
        from types import SimpleNamespace
        from tools.local_original_session import world_feature_pet
        ctx = SimpleNamespace()
        with patch.dict(os.environ, {'SL_PET': '0'}), patch.object(world_feature_pet, 'PetSystem') as construct:
            world_feature_pet._pet_initialize(ctx)
        construct.assert_not_called()
        self.assertIsNone(ctx._pet_system)
        self.assertFalse(ctx._pet_enabled)

    def test_existing_registry_loads_with_pet_feature_omitted(self):
        from tools.local_original_session import world_handlers
        world_handlers.feature_registry.cache_clear()
        try:
            original = world_handlers.FEATURE_MODULES
            with patch.object(world_handlers, 'FEATURE_MODULES', tuple(
                    name for name in original if name != 'world_feature_pet')):
                registry = world_handlers.feature_registry()
                self.assertIn('_companion_frame', registry.methods)
                self.assertFalse(any(name.startswith('_pet_') for name in registry.methods))
        finally:
            world_handlers.feature_registry.cache_clear()


class PetFailureReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_startup_error_and_finally_cleanup_remain_visible(self):
        from tools.local_original_session.hunt_bot_pet import PetScenario, parser
        with tempfile.TemporaryDirectory() as directory:
            scenario = PetScenario(parser().parse_args([]), Path(directory))
            with patch.object(scenario, 'open', AsyncMock(side_effect=RuntimeError('PET_FIRST_ERROR'))):
                result = await scenario.run()
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error'], 'RuntimeError: PET_FIRST_ERROR')
        self.assertTrue(result['cleanup_complete'])


class PetPersistenceDevelopmentTests(unittest.TestCase):
    """Direct WorldView/store inputs, with no sockets or formal packet PASS."""
    def setUp(self):
        from types import SimpleNamespace
        from tools.local_original_session.world_companion_integration_tests import CompanionWorldViewTests
        from tools.local_original_session.world_companion import CompanionRecord, CompanionStore
        from tools.local_original_session.world_progress import ProgressStore
        from tools.local_original_session import world_feature_pet as product
        from tools.local_original_session.world_pet import load_pets
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture = CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view = self.fixture.view
        self.view.terrain.can_stand = self.view.terrain.passable
        self.view.companions.dismiss(2)
        self.regular = CompanionStore(Path(self.directory.name) / 'characters.json')
        self.view.companion_save = lambda uid, receipt=None: self.regular.commit(self.view, uid, receipt,
            records=(record for record in self.view.companions.records.values()
                     if not product.pet_record(record)),
            reward_receipts=(row for row in self.view.companion_reward_receipts
                             if row['member_character_id'] == 2))
        ctx = SimpleNamespace(world=self.view,
            realm=SimpleNamespace(store=SimpleNamespace(path=Path(self.directory.name) / 'characters.json')),
            progress_store=ProgressStore(Path(self.directory.name) / 'characters.json'),
            collect_sync_hooks=lambda *_: (), run_sync_hooks=lambda *_: None,
            _world_names={1: 'FixtureKnight'})
        raw = json.loads(product.DATA.read_text(encoding='utf-8'))
        self.system = product.PetSystem(ctx, raw, load_pets())
        self.system.install()
        self.addCleanup(self.system.close)
        self.pet_id = 0x60000001
        self.record = CompanionRecord(self.pet_id, 1, 'development-pet', level=5,
            exp=1295, hp=1, max_hp=30, mp=0, max_mp=5, support_enabled=False,
            equipment={'_pet': dict(species='wolf', collar_uid=65550, mode=2, out=True)})
        self.system.records[self.pet_id] = self.record
        self.system.profile(self.record)
        self.system.summon(self.record, 1)
        self.view._save_companion(1)

    def kill(self):
        monster, definition = self.fixture.monster()
        for _ in range(30):
            self.view.pc_attack(1, monster.uid)
            self.fixture.now += 1
            if self.view.companion_reward_receipts:
                return monster, definition
        self.fail('development normal WorldView attack did not reach a kill')

    def test_atomic_failure_preserves_growth_typed_half_and_pending_without_replay(self):
        before_owner = self.view.exp[1]
        with patch('tools.local_original_session.world_companion.os.replace',
                   side_effect=OSError('PET_DEVELOPMENT_ATOMIC_FAILURE')):
            monster, definition = self.kill()
        self.assertEqual(definition.kill_exp, 5)
        self.assertEqual((self.record.exp, self.record.level, self.record.exp_half), (1297, 6, 1))
        self.assertEqual(self.record.hp, self.record.max_hp)
        self.assertEqual(self.view.exp[1], before_owner + 2)
        self.assertEqual(self.view.companion_owner_half[1], 1)
        self.assertIsNotNone(self.system.store.pending)
        pending = self.system.store.pending
        self.assertEqual(pending['owners']['1']['exp_half'], 1)
        saved = next(row for row in pending['records'] if row['character_id'] == self.pet_id)
        self.assertEqual(saved, dataclasses.asdict(self.record))
        receipt = self.view.companion_reward_receipts[0]
        self.assertFalse(receipt['durable'])
        self.assertEqual(receipt['joint_commit_count'], 0)
        grown = dataclasses.asdict(self.record)
        for _ in range(3):
            self.fixture.now += 1
            self.view.pc_attack(1, monster.uid)
        self.assertEqual(dataclasses.asdict(self.record), grown)
        self.assertEqual(len(self.view.companion_reward_receipts), 1)
        self.view._save_companion(1)
        self.assertIsNone(self.system.store.pending)
        self.assertEqual(dataclasses.asdict(self.record), grown)
        self.assertTrue(receipt['durable'])
        self.assertEqual(receipt['joint_commit_count'], 1)
        self.assertEqual(len(self.system.store.payload['rewards']), 1)

    def test_active_pet_regenerates_hp_by_l1j_fixed_rate_timer(self):
        # wolf npc45043: hprinterval5000/hpr5, mprinterval0 -> no MP regen.
        start = 1000.0
        self.system.regenerate(start)
        self.system.regenerate(start + 4.9)
        self.assertEqual((self.record.hp, self.record.mp), (1, 0))
        self.system.regenerate(start + 5)
        self.assertEqual(self.record.hp, 6)
        self.system.regenerate(start + 10)
        self.assertEqual((self.record.hp, self.record.mp), (11, 0))
        for step in range(3, 12):
            self.system.regenerate(start + 5 * step)
        self.assertEqual(self.record.hp, self.record.max_hp)
        self.assertNotIn((self.pet_id, 'hp'), self.system.regen_due)
        self.record.hp, self.record.alive = 0, False
        self.system.regenerate(start + 100)
        self.system.regenerate(start + 200)
        self.assertEqual(self.record.hp, 0)

    def test_pet_and_regular_companion_files_keep_separate_records(self):
        self.kill()
        self.view._save_companion(1)
        regular = json.loads(self.regular.path.read_text(encoding='utf-8'))
        pets = json.loads(self.system.store.path.read_text(encoding='utf-8'))
        self.assertEqual({row['character_id'] for row in regular['records']}, {2})
        self.assertEqual({row['character_id'] for row in pets['records']}, {self.pet_id})
        self.assertFalse(regular['rewards'])
        self.assertEqual({row['member_character_id'] for row in pets['rewards']}, {self.pet_id})
        self.assertEqual(regular['owners']['1']['exp'], pets['owners']['1']['exp'])
        self.assertEqual(regular['owners']['1']['exp_half'], pets['owners']['1']['exp_half'])

    def test_saved_pet_restores_the_record_collection_type(self):
        from tools.local_original_session import world_feature_pet as product
        from tools.local_original_session.world_pet import load_pets
        before = dataclasses.asdict(self.record)
        self.system.close()
        restored = product.PetSystem(self.system.ctx, self.system.raw, load_pets())
        restored.install()
        self.addCleanup(restored.close)
        self.assertEqual(dataclasses.asdict(restored.records[self.pet_id]), before)
        self.assertIsInstance(restored.records[self.pet_id].learned_spells, tuple)

    def test_stationary_guard_attacks_near_enemy_before_older_distant_enemy(self):
        actor = self.view.companions.active[self.pet_id]
        self.assertIsNone(self.view.companion_ai.magic.previous)
        entity = self.view.entities.resolve(actor.ref)
        position = (entity.x, entity.y)
        distant, _ = self.fixture.monster()
        self.view.entities.move(distant.uid, 0, entity.x+5, entity.y)
        nearby, _ = self.fixture.monster()
        self.view.entities.move(nearby.uid, 0, entity.x+1, entity.y)
        self.system.command(actor, 5, ())
        self.view.drain(1)
        self.view.companion_ai.step(actor.ref, self.fixture.now)
        self.fixture.now += .2
        self.view.companion_ai.step(actor.ref, self.fixture.now)
        wires = self.view.drain(1)
        self.assertEqual(actor.target, nearby.ref)
        self.assertTrue(self.fixture.decoded(wires, 0x4e31, 3, nearby.uid))
        self.assertFalse(self.fixture.decoded(wires, 0x4e31, 3, distant.uid))
        self.assertEqual((entity.x, entity.y), position)
        self.assertEqual(self.record.movement_mode, 'HOLD')

    def test_pet_command_preserves_enabled_magic_sequence_reset(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        actor = self.view.companions.active[self.pet_id]
        reset = Mock()
        self.view.companion_ai.magic.previous = SimpleNamespace(reset_sequence=reset)
        self.system.command(actor, 5, ())
        reset.assert_called_once_with(actor)
        self.assertEqual((self.record.movement_mode, self.record.combat_mode), ('HOLD', 'DEFEND'))


    def relocation(self, *, corpse=False, cross_map=False):
        from tools.local_original_session import world_feature_pet as product
        if corpse:
            self.view.companions.die(self.pet_id)
        self.system.ctx._pet_system = self.system
        owner = self.view.entities.get(1)
        destination = (owner.x+10, owner.y+10)
        destination_map = 1 if cross_map else owner.map_id
        if cross_map:
            from types import SimpleNamespace
            writer = object()
            self.system.ctx._world_pcs = {id(writer): (writer, 1)}
            self.system.ctx.realm.service = lambda selected: SimpleNamespace(_actor_heading=5)
        self.view.update_pc(3, destination_map, *destination)
        before = dataclasses.asdict(self.record)
        transit = {}
        with patch.object(self.system.store, 'commit', wraps=self.system.store.commit) as saves:
            product._pet_before_relocate(self.system.ctx, 1, transit)
            self.assertEqual(saves.call_count, 0)
            self.view.update_pc(1, destination_map, *destination)
            self.view.entities.move(1, destination_map, *destination, 2 if cross_map else 5)
            self.view.drain(1)
            self.view.drain(3)
            frames = product._pet_after_relocate(self.system.ctx, 1, transit)
        actor = self.view.companions.active[self.pet_id]
        entity = self.view.entities.get(actor.ref.uid)
        self.assertEqual(entity.heading, 5)
        self.assertEqual(max(abs(entity.x-destination[0]), abs(entity.y-destination[1])), 1)
        self.assertEqual(saves.call_count, 1)
        self.assertIsNone(self.system.relocation_owner)
        self.assertEqual(dataclasses.asdict(self.record), before)
        saved = json.loads(self.system.store.path.read_text(encoding='utf-8'))
        self.assertEqual(next(row for row in saved['records'] if row['character_id'] == self.pet_id), json.loads(json.dumps(before)))
        for wires in (frames, self.view.drain(3)):
            self.assertTrue(self.fixture.decoded(wires, 0x4e96, 2, entity.uid))
            self.assertTrue(self.fixture.decoded(wires, 0x4e96, 5, 5))
            self.assertTrue(self.fixture.decoded(wires, 0x4f1a, 1, entity.uid))
            if corpse:
                self.assertTrue(self.fixture.decoded(wires, 0x4e39, 1, entity.uid))
        if corpse:
            self.assertEqual(actor.action, 'DEAD')
            self.assertIsNone(actor.handle)

    def test_living_relocation_heading_watchers_and_single_destination_save(self):
        self.relocation()

    def test_corpse_relocation_heading_watchers_death_and_single_destination_save(self):
        self.relocation(corpse=True)

    def test_cross_map_living_pet_uses_committed_self_actor_heading(self):
        self.relocation(cross_map=True)

    def test_cross_map_corpse_uses_committed_self_actor_heading(self):
        self.relocation(corpse=True, cross_map=True)

    def test_failed_retirement_preserves_snapshot_and_restores_save_behavior(self):
        from tools.local_original_session import world_feature_pet as product
        self.system.ctx._pet_system = self.system
        original = self.view.companions.dismiss
        def fail_after_retirement(character_id):
            original(character_id)
            raise RuntimeError('PET_RETIREMENT_FAILURE')
        with patch.object(self.system.store, 'commit', wraps=self.system.store.commit) as saves:
            with patch.object(self.view.companions, 'dismiss', side_effect=fail_after_retirement):
                with self.assertRaisesRegex(RuntimeError, 'PET_RETIREMENT_FAILURE'):
                    product._pet_before_relocate(self.system.ctx, 1, {})
            self.assertIsNone(self.system.relocation_owner)
            self.assertEqual(saves.call_count, 1)
            self.view._save_companion(1)
            self.assertEqual(saves.call_count, 2)
        saved = json.loads(self.system.store.path.read_text(encoding='utf-8'))
        self.assertEqual(next(row for row in saved['records'] if row['character_id'] == self.pet_id),
                         json.loads(json.dumps(dataclasses.asdict(self.record))))


@unittest.skipUnless(os.environ.get('SL_RUN_PET_INTEGRATION') == '1',
                     'explicit sequential pet socket ownership required')
class PetSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_pet_lifecycle_and_companion_coexistence(self):
        from tools.local_original_session.hunt_bot_pet import parser, run
        result = await run(parser().parse_args(['--with-companion', '--navigation-timeout', '900',
                                               '--death-timeout', '600']))
        self.assertTrue(result['cleanup_complete'], result)
        self.assertEqual(result['status'], 'SUCCESS', result)
        self.assertFalse(result['source_changes_during_run'], result)
        checks = {check['check']: check['status'] for check in result['checks']}
        for name in ('normal_food_tame_issued_owned_collar_and_actor',
                     'pet_window_current_resources',
                     'collar_stores_without_cost_or_resource_reset',
                     'collar_summons_new_actor_preserving_saved_pet',
                     'odd_kill_50_50_carry_1', 'odd_kill_50_50_carry_2',
                     'first_odd_kill_has_typed_half', 'odd_half_saved_across_relogin',
                     'natural_pet_level6_hp_growth_and_refill',
                     'natural_pet_growth_saved_across_relogin',
                     'mode2_attack_follows_owner_with_real_motion',
                     'defend_follows_actual_owner_incoming',
                     'mode4_rest_stops_motion_and_attacks',
                     'mode5_guard_acquires_enemy_without_owner_attack',
                     'mode6_collect_consumes_ground_and_increases_owner_inventory',
                     'mode7_scatter_actual_patrol',
                     'death_invalidates_ref_cancels_ai_releases_monster',
                     'pet_targeted_resurrection_cost_and_life',
                     'trainer_deposit_preserves_collar_and_resources',
                     'trainer_retrieve_real_fee50_and_new_actor',
                     'normal_pet_reconnect_preserves_identity_resources_modes',
                     'pet_return_scroll_adjacent_heading_frames_save_once',
                     'pet_random_teleport_scroll_adjacent_heading_frames_save_once',
                     'pet_map2_stairs_adjacent_heading_frames_save_once',
                     'pet_dungeon_return_scroll_adjacent_heading_frames_save_once',
                     'pet_corpse_random_teleport_scroll_adjacent_heading_frames_save_once'):
            self.assertEqual(checks.get(name), 'SUCCESS', name)


if __name__ == '__main__':
    unittest.main()
