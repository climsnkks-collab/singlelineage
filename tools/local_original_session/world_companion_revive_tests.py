"""Stage6 development tests; real socket death/revive is hunt_bot_companion.

Fixture damage/time inputs here are unit inputs, not native gameplay evidence.
"""
from dataclasses import asdict
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tools.local_original_session import world_companion_integration_tests as fixtures
from tools.local_original_session.hunt_bot import scalar
from tools.local_original_session.world_companion import CompanionStore
from tools.local_original_session.world_feature_companion import _companion_revive


class CompanionReviveTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.view = self.fixture.view
        self.actor, self.record = self.fixture.actor, self.fixture.record
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.fixture.tearDown)
        self.store = CompanionStore(Path(self.directory.name) / 'characters.json')
        self.ctx = SimpleNamespace(world=self.view, _companion_revive_exp=False,
            _companion_save=lambda uid: self.store.commit(self.view, uid))
        self.view.companion_save = lambda uid, receipt=None: self.store.commit(self.view, uid, receipt)
        self.view.drain(1)

    def die(self):
        old = self.actor.ref
        self.view.companions.die(2, self.fixture.now)
        self.ctx._companion_save(1)
        return old

    def test_death_discards_shield_regen_position_and_never_runs_stale_cast(self):
        self.actor.shield_until = 900
        self.actor.regen_at, self.actor.regen_points = 20, 30
        self.actor.emergency_owner = self.actor.recovering = True
        self.actor.position_key = self.actor.position_failed = ('heal',)
        called = []
        self.view.runtime.scheduler.schedule(11, self.actor.ref, 'cast', called.append)
        ref = self.die()
        self.assertEqual(self.actor.shield_until, 0)
        self.assertIsNone(self.actor.regen_at)
        self.assertEqual(self.actor.regen_points, 0)
        self.assertFalse(self.actor.recovering)
        self.assertIsNone(self.actor.position_key)
        self.assertIsNone(self.actor.position_failed)
        self.view.runtime.scheduler.run_due(30)
        self.assertEqual(called, [])
        self.assertIsNone(self.view.entities.resolve(ref))
        payload = CompanionStore(self.store.path.with_name('characters.json')).payload
        self.assertEqual((payload['records'][0]['hp'], payload['records'][0]['alive']), (0, False))

    def test_default_same_uid_replacement_preserves_position_mp_growth_and_settings(self):
        self.record.exp, self.record.exp_half = 7, 1
        old = self.die()
        before = asdict(self.record)
        corpse = self.view.entities.get(old.uid)
        pose = corpse.map_id, corpse.x, corpse.y
        result = _companion_revive(self.ctx, 1, self.record)
        self.assertIs(result, self.actor)
        self.assertEqual(result.ref.uid, old.uid)
        self.assertNotEqual(result.ref, old)
        self.assertIsNone(self.view.entities.resolve(old))
        self.assertEqual((corpse.map_id, corpse.x, corpse.y), pose)
        self.assertTrue(self.view.companions.can_be_attacked(old.uid))
        self.assertEqual((self.record.hp, self.record.alive), (max(1, self.record.max_hp // 4), True))
        for key in before.keys() - {'hp', 'alive'}:
            self.assertEqual(asdict(self.record)[key], before[key], key)
        wires = self.view.drain(1)
        self.assertEqual(len(self.fixture.decoded(wires, 0x4e96, 2, old.uid)), 1)
        self.assertFalse(self.fixture.decoded(wires, 0x4f16, 1, old.uid))
        self.assertFalse(self.fixture.decoded(wires, 0x4e40, 1, old.uid))
        self.assertTrue(self.store.payload['records'][0]['alive'])
        self.assertIsNotNone(self.actor.handle)

    def test_opt_in_4f16_has_required_fields_and_uses_current_look(self):
        self.ctx._companion_revive_exp = True
        old = self.die()
        _companion_revive(self.ctx, 1, self.record)
        wires = self.view.drain(1)
        revived = self.fixture.decoded(wires, 0x4f16, 1, old.uid)
        self.assertEqual(len(revived), 1)
        self.assertEqual({k: scalar(revived[0], k) for k in range(1, 5)},
                         {1: old.uid, 2: 50, 3: 734, 4: 0})
        self.assertFalse(self.fixture.decoded(wires, 0x4e96, 2, old.uid))

    def test_repeated_effect_cannot_revive_living_member(self):
        self.die()
        _companion_revive(self.ctx, 1, self.record)
        self.view.drain(1)
        ref = self.actor.ref
        with self.assertRaisesRegex(ValueError, 'DEAD_MEMBER_REQUIRED'):
            _companion_revive(self.ctx, 1, self.record)
        self.assertEqual(self.actor.ref, ref)
        self.assertEqual(self.view.drain(1), [])

    def test_departed_corpse_cannot_be_recreated_by_resurrection(self):
        old = self.die()
        self.view.companions.dismiss(2)
        self.view.drain(1)
        with self.assertRaisesRegex(ValueError, 'RESURRECTION_REQUIRED'):
            self.view.summon_companion(2, 1)
        self.assertFalse(self.store.payload['records'][0]['alive'])
        with self.assertRaisesRegex(ValueError, 'CURRENT_CORPSE_REQUIRED'):
            _companion_revive(self.ctx, 1, self.record)
        self.assertEqual(self.record.mp, 8)
        self.assertEqual((self.record.hp, self.record.alive), (0, False))
        self.assertNotIn(2, self.view.companions.active)
        self.assertFalse(self.store.payload['records'][0]['alive'])

    def test_stale_owner_cannot_revive_current_corpse(self):
        self.die()
        self.view.entities.deactivate_pc(1)
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNED_ACTOR_REQUIRED'):
            _companion_revive(self.ctx, 1, self.record)
        self.assertFalse(self.record.alive)

    def test_failed_revive_save_preserves_pending_partial_life_without_replaying_it(self):
        old = self.die()
        with patch('tools.local_original_session.world_companion.os.replace', side_effect=OSError('SAVE_FAILED')):
            with self.assertRaisesRegex(OSError, 'SAVE_FAILED'):
                _companion_revive(self.ctx, 1, self.record)
        self.assertTrue(self.store.pending['records'][0]['alive'])
        self.assertFalse(self.store.payload['records'][0]['alive'])
        self.assertEqual(len(self.fixture.decoded(self.view.drain(1), 0x4e96, 2, old.uid)), 1)
        self.assertIsNotNone(self.actor.handle)
        ref = self.actor.ref
        self.ctx._companion_save(1)
        self.assertEqual(self.actor.ref, ref)
        self.assertIsNone(self.store.pending)
        self.assertTrue(self.store.payload['records'][0]['alive'])

    def test_two_odd_kills_and_duplicate_attacks_credit_each_half_once(self):
        for index in range(2):
            monster, definition = self.fixture.monster()
            self.assertEqual(definition.kill_exp % 2, 1)
            previous_owner, previous_member = self.view.exp[1], self.record.exp
            previous_half = self.record.exp_half
            for _ in range(30):
                self.view.pc_attack(1, monster.uid)
                self.fixture.now += 1
                if len(self.view.companion_reward_receipts) == index + 1:
                    break
            gain, half = divmod(definition.kill_exp + previous_half, 2)
            self.assertEqual((self.view.exp[1] - previous_owner, self.record.exp - previous_member), (gain, gain))
            self.assertEqual((self.view.companion_owner_half[1], self.record.exp_half), (half, half))
            before = (self.view.exp[1], asdict(self.record), list(self.view.companion_reward_receipts))
            for _ in range(3):
                self.fixture.now += 1
                self.view.pc_attack(1, monster.uid)
            self.assertEqual((self.view.exp[1], asdict(self.record), self.view.companion_reward_receipts), before)
        payload = CompanionStore(self.store.path.with_name('characters.json')).payload
        self.assertEqual(len(payload['rewards']), 2)
        self.assertEqual(len({r['kill_id'] for r in payload['rewards']}), 2)
        self.assertTrue(all(r['joint_commit_count'] == 1 and r['durable'] for r in payload['rewards']))
        self.assertEqual((payload['owners']['1']['exp_half'], payload['records'][0]['exp_half']), (0, 0))


class CompanionScrollRequestTests(unittest.IsolatedAsyncioTestCase):
    """Development handler/store boundaries; no broker or socket execution."""
    def setUp(self):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
        from tools.local_original_session.world_item_effects import load_effects
        from tools.local_original_session.world_core_kit import _world_consume_kit
        self.fixture = CompanionReviveTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.view, self.record, self.actor = self.fixture.view, self.fixture.record, self.fixture.actor
        self.writer, self.game = object(), object()
        self.ctx = self.fixture.ctx
        self.ctx._companion_enabled = True
        self.ctx._companion_errors = []
        self.ctx._world_bound = lambda _: True
        self.ctx._world_ready = lambda *_: self.game
        self.ctx._world_pcs = {id(self.writer): (None, 1)}
        self.ctx.realm = SimpleNamespace(registry=SimpleNamespace(resolve=lambda _: self.game),
            service=lambda _: SimpleNamespace(snapshot=lambda: object()))
        self.ctx.owner_current = lambda *_: True
        self.ctx._world_send = AsyncMock()
        self.ctx._companion_item_effects = load_effects(owner='companion')
        self.ctx._inventory_kit_policy = inventory.KIT_POLICY
        rows = []
        for uid, template, count in ((65537, 28, 2), (65538, 41, 1)):
            fields = dict(INVENTORY_STARTER_FIELDS)
            fields.update({1: uid, 2: template, 4: count})
            rows.append(fields)
        self.ctx.inventory_frame = inventory.build_kit_frame(rows)
        self.ctx.inventory_store = SimpleNamespace(replace_kit=Mock(return_value=True))
        self.ctx._world_consume_kit = lambda writer, uid: _world_consume_kit(self.ctx, writer, uid)

    async def request(self, target=None, *, token=False, params=None):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_feature_companion import _companion_frame, TOKEN_NAME
        from tools.local_entry_server import protobuf as pb
        if token:
            rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.ctx.inventory_frame)]
            rows[0].update({2: 1, 18: TOKEN_NAME})
            self.ctx.inventory_frame = inventory.build_kit_frame(rows)
        if params is None:
            values = ((1, 1), (15, 0), (16, 0)) if token else (
                (1, 1), (2, self.actor.ref.uid if target is None else target), (3, 0), (15, 0), (16, 0))
            params = b''.join(pb.encode_varint(n << 3) + pb.encode_varint(v) for n, v in values)
        frame = SimpleNamespace(opcode=0x0960,
            payload=pb.encode_varint(8) + pb.encode_varint(65537) + pb.encode_bytes(2, params))
        return await _companion_frame(self.ctx, self.writer, {}, self.game, frame, None)

    def quantity(self):
        from tools.local_original_session import inventory
        return dict(inventory.validate_kit_frame(self.ctx.inventory_frame)[0].raw_fields)[4]

    async def test_targeted_scroll_debits_one_before_life_save_and_resumes_ai(self):
        self.fixture.die()
        old = self.actor.ref
        original_save = self.ctx._companion_save
        def save(uid):
            self.assertEqual(self.quantity(), 1)
            original_save(uid)
        self.ctx._companion_save = save
        self.assertTrue(await self.request())
        self.assertEqual(self.quantity(), 1)
        self.assertEqual((self.record.hp, self.record.alive), (3, True))
        self.assertNotEqual(old, self.actor.ref)
        self.assertIsNotNone(self.actor.handle)
        self.ctx.inventory_store.replace_kit.assert_called_once()
        frames = self.ctx._world_send.await_args.args[2]
        self.assertEqual(int.from_bytes(frames[0][2:4], 'little'), 0x0965)
        self.assertTrue(self.fixture.store.payload['records'][0]['alive'])
        self.assertTrue(await self.request())
        self.assertEqual(self.quantity(), 1)  # repeated request cannot debit a living target
        self.ctx.inventory_store.replace_kit.assert_called_once()

    async def test_live_noncompanion_other_owner_and_wide_target_reject_without_cost(self):
        self.assertTrue(await self.request())  # living owned member
        self.fixture.die()
        for target in (1, 999, self.actor.ref.uid + (1 << 32)):
            self.assertTrue(await self.request(target))
        self.record.owner_character_id = 7
        self.assertTrue(await self.request())
        self.assertEqual(self.quantity(), 2)
        self.assertFalse(self.record.alive)
        self.ctx.inventory_store.replace_kit.assert_not_called()

    async def test_failed_inventory_commit_keeps_dead_life_and_original_stack(self):
        self.fixture.die()
        old = self.actor.ref
        self.ctx.inventory_store.replace_kit.return_value = False
        with self.assertRaisesRegex(ValueError, 'PERSISTED_CHANGE_REQUIRED'):
            await self.request()
        self.assertEqual(self.quantity(), 2)
        self.assertEqual(self.actor.ref, old)
        self.assertFalse(self.record.alive)
        self.assertFalse(self.fixture.store.payload['records'][0]['alive'])

    async def test_failed_life_save_keeps_spent_scroll_and_pending_life_without_replay(self):
        self.fixture.die()
        with patch('tools.local_original_session.world_companion.os.replace', side_effect=OSError('SAVE_FAILED')):
            with self.assertRaisesRegex(OSError, 'SAVE_FAILED'):
                await self.request()
        self.assertEqual(self.quantity(), 1)
        self.assertTrue(self.fixture.store.pending['records'][0]['alive'])
        self.assertFalse(self.fixture.store.payload['records'][0]['alive'])
        self.assertIsNotNone(self.actor.handle)
        ref = self.actor.ref
        await self.request()
        self.assertEqual((self.quantity(), self.actor.ref), (1, ref))
        self.ctx._companion_save(1)
        self.assertIsNone(self.fixture.store.pending)
        self.assertTrue(self.fixture.store.payload['records'][0]['alive'])

    async def test_management_token_cannot_revive_dead_member(self):
        self.fixture.die()
        self.assertTrue(await self.request(token=True))
        self.assertFalse(self.record.alive)
        self.assertEqual(self.quantity(), 2)
        self.ctx.inventory_store.replace_kit.assert_not_called()
        self.assertIn('COMPANION_TARGETED_SCROLL_REQUIRED', self.ctx._companion_errors)

    def test_targeted_effect_is_excluded_from_earlier_raw0_item_dispatcher(self):
        from tools.local_original_session.world_item_effects import load_effects
        self.assertNotIn(28, load_effects())
        self.assertEqual(self.ctx._companion_item_effects[28].reference_id, 40089)


if __name__ == '__main__':
    unittest.main()
