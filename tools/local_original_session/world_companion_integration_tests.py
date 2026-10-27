"""Opt-in real socket lifecycle, reusing hunt_bot_companion's one broker owner.

SL_RUN_COMPANION_INTEGRATION=1 python -X utf8 -B -m unittest \
    tools.local_original_session.world_companion_integration_tests

The default discovery run skips socket execution. Run only while owning the
test ports; SL_TEST_PORT_BASE is consumed by the existing test_ports module.
Profiles, failure JSON and FIRST/close results remain under the existing runs/.
"""
from __future__ import annotations

import os
import dataclasses
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


class _OpenTerrain:
    """Development fixture terrain only; no native LOS/passability claim."""
    def passable(self, *_):
        return True

    def can_step(self, *_):
        return True


class CompanionWorldViewTests(unittest.TestCase):
    """Pure WorldView/store integration; direct calls are development checks.

    No broker, sockets, runtime task, user save, or formal gameplay PASS. The
    test fixture supplies positions/terrain and advances only its own clock.
    """
    def setUp(self):
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_companion import CompanionRecord
        from tools.local_original_session.world_combat import PcProfile, ATHAME
        from tools.local_original_session.world_interest_spawn import InterestSpawner
        from tools.local_original_session.world_runtime import WorldRuntime
        from tools.local_original_session.world_visibility import WorldView
        from tools.local_original_session.world_companion_runtime import install_companion_runtime
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        self.now = 10.0
        self.data = load_m1()
        data = dataclasses.replace(self.data, spawns=())
        runtime = WorldRuntime(clock=lambda: self.now)
        spawner = InterestSpawner(runtime.entities, data, passable=lambda *_: True,
                                  rng=random.Random(7))
        self.view = WorldView(runtime, spawner, _OpenTerrain(), data=data,
                              rng=random.Random(7))
        install_companion_runtime(self.view)
        self.view.update_pc(1, 0, 100, 100)
        status = dict(actor_hook.profiles()[0].fields)
        status.update({1: 1, 2: 1, 10: 100, 11: 100, 12: 20, 13: 20, 18: 500})
        self.view.bind_pc(1, PcProfile(1, 1, 0, 18, 13, con=16, weapon=ATHAME),
                          status)
        self.record = CompanionRecord(2, 1, 'development-fixture', hp=12, max_hp=12,
                                      mp=8, max_mp=8, movement_mode='HOLD',
                                      combat_mode='PASSIVE')
        self.view.companions.register(self.record, roster={
            1: dict(account_id='development-fixture', class_id=1),
            2: dict(account_id='development-fixture', class_id=3)})
        self.view.companion_profiles[2] = PcProfile(1, 3, 0, 8, 7, con=16, wis=18)
        self.view.companion_looks[2] = dict(name='FixtureMage', owner_name='FixtureKnight',
                                           sprite_id=734, stance=50)
        self.actor = self.view.summon_companion(2, 1)

    def tearDown(self):
        self.view.close()

    def decoded(self, wires, opcode, field, value):
        from tools.local_original_session.hunt_bot import fields, scalar
        return [values for wire in wires if int.from_bytes(wire[2:4], 'little') == opcode
                and scalar(values := fields(wire[4:-2]), field) == value]

    def monster(self, template=245):
        from tools.local_original_session.world_entities import Kind
        from tools.local_original_session.world_interest_spawn import Group, Slot, SlotState
        definition = self.data.monsters[template]
        entity = self.view.entities.add(Kind.NPC, 0, 101, 100, template_id=template)
        spec = next(group for group in self.data.spawns if group.template_id == template)
        slot = Slot(0, SlotState.ALIVE, entity.uid, definition.hp, (101, 100))
        group = Group(spec, definition, [slot], True)
        self.view.spawner.groups.append(group)
        self.view.spawner._slots[entity.uid] = (group, slot)
        self.view.ai.sync(self.now)
        return entity, definition

    def test_registered_mage_appearance_is_player_and_carries_owner_name(self):
        from tools.local_original_session.hunt_bot import scalar
        appearances = self.decoded(self.view.drain(1), 0x4e96, 2, self.actor.ref.uid)
        self.assertEqual(len(appearances), 1)
        self.assertEqual(scalar(appearances[0], 16), 1)
        self.assertEqual(scalar(appearances[0], 21), b'FixtureKnight')
        self.assertEqual(scalar(appearances[0], 3), 734)
        self.assertNotIn(self.actor.ref.uid, self.view.combat.pcs)

    def test_hold_owner_screen_exit_and_reentry_use_current_actor(self):
        self.view.drain(1)
        ref = self.actor.ref
        entity = self.view.entities.resolve(ref)
        position = (entity.map_id, entity.x, entity.y)
        departed = self.view.update_pc_and_drain(1, 0, 150, 100)
        self.assertEqual(len(self.decoded(departed, 0x4e40, 1, ref.uid)), 1)
        returned = self.view.update_pc_and_drain(1, 0, 100, 100)
        self.assertEqual(len(self.decoded(returned, 0x4e96, 2, ref.uid)), 1)
        self.assertIs(self.view.entities.resolve(ref), entity)
        self.assertEqual((entity.map_id, entity.x, entity.y), position)
        self.assertEqual(self.record.movement_mode, 'HOLD')

    def test_map_change_and_owner_leave_remove_actor_and_its_timers(self):
        for action in ('map_change', 'owner_leave'):
            with self.subTest(action=action):
                ref, handle = self.actor.ref, self.actor.handle
                self.assertIsNotNone(handle)
                if action == 'map_change':
                    self.view.update_pc(1, 1, 100, 100)
                else:
                    self.view.leave_pc(1)
                self.assertIsNone(self.view.entities.get(ref.uid))
                self.assertNotIn(2, self.view.companions.active)
                self.assertTrue(handle.cancelled)
                self.assertIsNone(self.actor.handle)
                self.assertIsNone(self.actor.target)
                self.assertFalse(self.view.runtime.scheduler._by_owner.get(ref.uid))
                if action == 'map_change':
                    self.view.update_pc(1, 0, 100, 100)
                    self.actor = self.view.summon_companion(2, 1)

    def test_actual_npc_attack_debits_only_record_and_cleans_lethal_lifetime(self):
        monster, definition = self.monster()
        entity = self.view.entities.resolve(self.actor.ref)
        self.view.entities.move(monster.uid, 0, entity.x + 1, entity.y)
        self.view.ai.on_hit(monster.uid, self.actor.ref.uid, self.now)
        brain = self.view.ai.brains[monster.uid]
        self.assertEqual(brain.target, self.actor.ref.uid)
        owner_hp, ref = self.view.combat.pcs[1].hp, self.actor.ref
        self.view.drain(1)
        observed_hp = [self.record.hp]
        wires = []
        for _ in range(30):
            self.view.npc_attack(monster, definition, ref.uid, self.now)
            wires.extend(self.view.drain(1))
            observed_hp.append(self.record.hp)
            if not self.record.alive:
                break
            self.now += definition.attack_interval_ms / 1000
        self.assertEqual(self.record.hp, 0, observed_hp)
        self.assertFalse(self.record.alive)
        self.assertTrue(any(a > b for a, b in zip(observed_hp, observed_hp[1:])))
        self.assertEqual(self.view.combat.pcs[1].hp, owner_hp)
        self.assertNotIn(ref.uid, self.view.combat.pcs)
        self.assertIsNone(self.view.entities.resolve(ref))
        self.assertIsNone(self.actor.handle)
        self.assertIsNone(self.actor.target)
        self.assertIsNone(brain.target)
        self.assertIsNone(brain.target_ref)
        self.assertTrue(self.decoded(wires, 0x4e31, 3, ref.uid))
        self.assertTrue(self.decoded(wires, 0x4e39, 1, ref.uid))
        self.assertFalse(self.decoded(wires, 0x4e38, 1, ref.uid))

    def test_archer_keeps_existing_ranged_attack_recipe_when_target_is_companion(self):
        from tools.local_original_session.hunt_bot import scalar
        entity, definition = self.monster(1)
        self.view.drain(1)
        self.view.npc_attack(entity, definition, self.actor.ref.uid, self.now)
        attacks = self.decoded(self.view.drain(1), 0x4e31, 3, self.actor.ref.uid)
        self.assertEqual(len(attacks), 1)
        self.assertEqual(scalar(attacks[0], 2), entity.uid)
        self.assertEqual(scalar(attacks[0], 6), self.view.arrow_id)
        self.assertEqual(scalar(attacks[0], 7), 66)
        self.assertEqual(scalar(attacks[0], 14), self.view.arrow_mode)

    def test_joint_store_atomic_failure_and_absolute_retry_do_not_repeat_reward(self):
        from tools.local_original_session.world_companion import CompanionStore
        with tempfile.TemporaryDirectory() as directory:
            store = CompanionStore(Path(directory) / 'characters.json')
            store.commit(self.view, 1)
            original = store.path.read_bytes()
            original_payload = json.loads(original)
            monster, _ = self.monster()
            for _ in range(30):
                self.view.pc_attack(1, monster.uid)
                if self.view.companion_reward_receipts:
                    break
                self.now += 1
            self.assertEqual(len(self.view.companion_reward_receipts), 1)
            receipt = self.view.companion_reward_receipts[0]
            self.assertTrue(receipt['kill_once'])
            self.assertEqual((self.view.exp[1], self.record.exp), (2, 2))

            self.assertEqual((self.view.companion_owner_half[1], self.record.exp_half), (1, 1))
            with patch('tools.local_original_session.world_companion.os.replace',
                       side_effect=OSError('DEVELOPMENT_ATOMIC_REPLACE_FAILURE')):
                with self.assertRaisesRegex(OSError, 'DEVELOPMENT_ATOMIC_REPLACE_FAILURE'):
                    store.commit(self.view, 1, receipt)
            self.assertEqual(store.path.read_bytes(), original)
            self.assertEqual(json.loads(json.dumps(store.payload)), original_payload)
            self.assertFalse(receipt['durable'])
            self.assertEqual(receipt['joint_commit_count'], 0)
            with patch('tools.local_original_session.world_companion.os.replace', wraps=os.replace) as replace:
                store.commit(self.view, 1, receipt)
                self.assertEqual(replace.call_count, 1)
            recovered = store.path.read_bytes()
            store.commit(self.view, 1, receipt)
            self.assertEqual(store.path.read_bytes(), recovered)
            restored = CompanionStore(Path(directory) / 'characters.json').payload
            self.assertEqual((restored['owners']['1']['exp'], restored['owners']['1']['exp_half']), (2, 1))
            self.assertEqual((restored['records'][0]['exp'], restored['records'][0]['exp_half']), (2, 1))
            self.assertEqual(len(restored['rewards']), 1)
            self.assertEqual(restored['rewards'][0]['kill_id'], receipt['kill_id'])
            self.assertEqual(restored['rewards'][0]['joint_commit_count'], 1)
            self.assertTrue(restored['rewards'][0]['durable'])
            self.assertEqual((self.view.exp[1], self.record.exp), (2, 2))


    def test_failed_joint_save_does_not_skip_owner_cleanup_or_lose_pending_owner(self):
        from tools.local_original_session.world_companion import CompanionStore
        with tempfile.TemporaryDirectory() as directory:
            store = CompanionStore(Path(directory) / 'characters.json')
            store.commit(self.view, 1)
            self.view.companion_save = lambda uid, receipt: store.commit(self.view, uid, receipt)
            self.view.exp[1] = 2
            self.view.companion_owner_half[1] = 1
            self.record.exp, self.record.exp_half = 2, 1
            with patch('tools.local_original_session.world_companion.os.replace',
                       side_effect=OSError('DEVELOPMENT_LEAVE_SAVE_FAILURE')):
                with self.assertLogs('tools.local_original_session.world_visibility', level='ERROR'):
                    self.view.leave_pc(1)
            self.assertNotIn(1, self.view.pcs)
            self.assertNotIn(1, self.view.combat.pcs)
            self.assertFalse(self.view.entities.get(1).alive)
            self.assertIsNone(self.view.entities.get(self.actor.ref.uid))
            self.assertEqual((store.pending['owners']['1']['exp'],
                              store.pending['owners']['1']['exp_half']), (2, 1))
            self.assertEqual(store.payload['owners']['1']['exp'], 0)
            store.commit(self.view, 0)
            self.assertIsNone(store.pending)
            self.assertEqual(store.payload['owners']['1']['exp'], 2)
            self.assertTrue(self.view.companion_save_errors)


class CompanionFailureReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_initial_inventory_pending_does_not_change_kit(self):
        from types import SimpleNamespace
        from tools.local_original_session import inventory
        from tools.local_original_session.world_feature_companion import _companion_kit
        writer = object()
        ctx = SimpleNamespace(_companion_enabled=True, _world_bound=lambda _: True,
            _inventory_kit_policy=inventory.KIT_POLICY, inventory_frame=None)
        with patch.object(inventory, 'validate_kit_frame') as parse:
            await _companion_kit(ctx, writer, {}, None, 0x4e28, None)
        parse.assert_not_called()

    async def test_manual_initial_equipment_sync_retains_its_original_kit(self):
        from types import SimpleNamespace
        from tools.local_original_session import inventory
        from tools.local_original_session.world_feature_companion import _companion_kit
        writer = object()
        ctx = SimpleNamespace(_companion_enabled=True, _world_bound=lambda _: True,
            _inventory_kit_policy=inventory.KIT_POLICY, inventory_frame=b'initial-kit',
            _item_equipment_effect=SimpleNamespace(_selection={'synced': False}))
        ctx.broker = ctx
        with patch.object(inventory, 'validate_kit_frame') as parse:
            await _companion_kit(ctx, writer, {}, None, 0x4e2a, None)
        parse.assert_not_called()

    async def test_startup_failure_retains_first_error_and_cleanup_summary(self):
        from tools.local_original_session.hunt_bot_companion import CompanionScenario, parser
        with tempfile.TemporaryDirectory() as directory:
            scenario = CompanionScenario(parser().parse_args([]), Path(directory))
            with patch.object(scenario, 'open', AsyncMock(side_effect=RuntimeError('FIRST_STARTUP_ERROR'))):
                result = await scenario.run()
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error'], 'RuntimeError: FIRST_STARTUP_ERROR')
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['checks'][-1]['check'], 'scenario_execution')


@unittest.skipUnless(os.environ.get('SL_RUN_COMPANION_INTEGRATION') == '1',
                     'explicit sequential socket-test ownership required')
class CompanionSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_companion_socket_lifecycle(self):
        from tools.local_original_session.hunt_bot_companion import parser, run
        result = await run(parser().parse_args(['--scenario', 'all']))
        self.assertTrue(result['cleanup_complete'], result)
        self.assertEqual(result['status'], 'SUCCESS', result)
        checks = {check['check']: check for check in result['checks']}
        for name in ('normal_login_selected_owned_mage_appearance',
                     'pet_query_real_resources', 'follow_owner_motion',
                     'hold_while_owner_moves', 'living_resummon_fresh_uid',
                     'odd_kill_50_50_carry_1', 'odd_kill_50_50_carry_2',
                     'odd_half_saved_across_relogin',
                     'odd_half_joint_file_saved',
                     'defend_follows_actual_owner_incoming',
                     'assist_same_target_after_owner',
                     'incoming_changes_only_companion_ledger',
                     'death_invalidates_ref_cancels_ai_releases_monster',
                     'death_corpse_retained_and_actions_stopped',
                     'targeted_scroll_revive_retained',
                     'resurrection_scroll_cost_saved_across_relogin',
                     'revived_member_follows',
                     'revived_member_attacks',
                     'dead_member_no_free_resurrection',
                     'dead_member_joint_file_saved',
                     'normal_relogin_preserves_member_and_half'):
            self.assertEqual(checks.get(name, {}).get('status'), 'SUCCESS', name)


if __name__ == '__main__':
    unittest.main()
