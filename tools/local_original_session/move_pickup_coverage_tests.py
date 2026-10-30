"""GET payload -> world pickup -> temporary inventory CAS; no game or sockets.

run98 worker/findings.md section 3: B9A10 accepts a nonzero uint64 popup
quantity without a ground-count clamp. Quantity refusal below is the existing
LOCAL GroundItems policy, not a reconstructed official-server rule.
"""
from pathlib import Path
import tempfile
from types import MethodType, SimpleNamespace
import unittest
from unittest import mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, inventory_store, item_transfer_protocol
from tools.local_original_session import world_core_reward as reward, world_visibility
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import InterestSpawner
from tools.local_original_session.world_runtime import WorldRuntime


def get_payload(item, quantity):
    child = b''.join(pb.encode_varint(n << 3) + pb.encode_varint(value)
                     for n, value in enumerate((item.x, item.y, item.ref.uid, quantity), 1))
    return pb.encode_bytes(1, child)


class PickupQuantityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        profile = Path(self.temp.name) / 'characters.json'
        characters = inventory_store.realm.CharacterStore(profile)
        characters.create(inventory_store.realm.Creation('PickupCase', 0, 0, (13,) * 6))
        self.profile = profile
        self.profile_bytes = profile.read_bytes()
        self.store = inventory_store.InventoryStore(profile, policy=inventory_store.POLICY,
                                                     kit_policy=inventory.KIT_POLICY)
        self.fields = {1: 100, 2: 7, 3: 0, 4: 5, 5: 0, 7: load_m1().items[7].icon,
                       9: 0, 10: 0, 13: 0, 14: 0, 16: 0, 17: 0, 18: b'',
                       22: 0, 24: False, 25: 0, 26: False}
        frame = inventory.build_kit_frame([self.fields])
        self.store.grant(1, frame)
        runtime = WorldRuntime(clock=lambda: 100.0)
        data = load_m1()
        self.world = world_visibility.WorldView(
            runtime, InterestSpawner(runtime.entities, data, passable=lambda *_: True), data=data)
        pc = self.world.entities.add(Kind.PC, 0, 100, 100, uid=1)
        npc = self.world.entities.add(Kind.NPC, 0, 100, 100, template_id=0)
        self.world.entities.kill(npc.uid)
        self.item, = self.world.ground.spawn_drops(npc.ref, [(7, 10)], owner_uid=pc.uid)
        self.world.pcs[1] = (0, 100, 100)
        self.world.item_known[1] = {self.item.ref.uid}
        self.writer = object()
        self.sent = []

        async def send(writer, row, frames, operation_lock):
            self.sent.extend(frames)

        self.ctx = SimpleNamespace(
            _world=self.world, _world_pcs={id(self.writer): (self.writer, 1)},
            _world_ready=lambda *_: True, _world_events={}, _world_pickup_errors=[],
            _world_pickups=0, _inventory_store=self.store, _inventory_kit_policy=inventory.KIT_POLICY,
            inventory_frame=frame, starter_fields=self.fields,
            fold_sync_hooks=lambda name, value, *args: value, _world_send=send)
        self.ctx._world_pickup_commit = MethodType(reward._world_pickup_commit, self.ctx)

    async def request(self, quantity):
        frame = SimpleNamespace(payload=get_payload(self.item, quantity))
        return await reward._world_pickup(self.ctx, self.writer, {}, object(), frame, None)

    def assert_bag_quantity(self, expected):
        item, = inventory.validate_kit_frame(self.ctx.inventory_frame)
        self.assertEqual(dict(item.raw_fields)[4], expected)
        restored = inventory_store.InventoryStore(
            self.profile, policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        self.assertEqual(restored.restore(1), self.ctx.inventory_frame)
        self.assertEqual(self.profile.read_bytes(), self.profile_bytes)

    async def test_uint64_popup_over_quantity_preserves_ground_and_inventory(self):
        before = self.store.path.read_bytes()
        for quantity in (11, 1 << 32, (1 << 64) - 1, 0):
            with self.subTest(quantity=quantity):
                parsed = item_transfer_protocol.parse_get_payload_prevalidated(
                    get_payload(self.item, quantity))
                self.assertEqual(parsed.quantity, quantity)
                self.assertTrue(await self.request(quantity))
                self.assertEqual(self.world.ground.get(self.item.ref), self.item)
                self.assertEqual(self.store.path.read_bytes(), before)
                self.assertEqual(self.sent, [])
                self.assertEqual(self.ctx._world_pickups, 0)
        self.assert_bag_quantity(5)

    async def test_partial_then_remaining_pickup_persists_exact_requested_counts(self):
        timer = self.world.ground._expiry[self.item.ref.uid]
        self.assertTrue(await self.request(3))
        remaining = self.world.ground.get(self.item.ref)
        self.assertEqual(remaining.count, 7)
        self.assertEqual((remaining.ref, remaining.expires_at), (self.item.ref, self.item.expires_at))
        self.assertIs(self.world.ground._expiry[self.item.ref.uid], timer)
        self.assert_bag_quantity(8)
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in self.sent],
                         [0x4e39, 0x0965])
        self.sent.clear()
        self.assertTrue(await self.request(7))
        self.assert_bag_quantity(15)
        self.assertIsNone(self.world.ground.get(self.item.ref))
        self.assertTrue(timer.cancelled)
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in self.sent],
                         [0x4e40, 0x4e39, 0x0965])
        self.assertEqual(self.ctx._world_pickups, 2)

    async def test_full_pickup_and_repeat_do_not_duplicate_inventory(self):
        self.assertTrue(await self.request(10))
        self.assert_bag_quantity(15)
        self.assertIsNone(self.world.ground.get(self.item.ref))
        self.sent.clear()
        self.assertTrue(await self.request(10))
        self.assert_bag_quantity(15)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.ctx._world_pickups, 1)

    async def test_failed_inventory_cas_preserves_ground_and_saved_quantity(self):
        before = self.store.path.read_bytes()
        with mock.patch.object(self.store, 'replace_kit', return_value=False):
            self.assertTrue(await self.request(3))
        self.assertEqual(self.world.ground.get(self.item.ref), self.item)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assert_bag_quantity(5)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.ctx._world_pickups, 0)
        self.assertEqual(self.ctx._world_pickup_errors, ['WORLD_PICKUP_PERSISTED_CHANGE_REQUIRED'])


class PlayerDropTests(unittest.IsolatedAsyncioTestCase):
    """DROP decoder -> existing save CAS -> shared ground -> GET decoder."""
    setUp = PickupQuantityTests.setUp

    async def drop(self, count=3, uid=100, x=100, y=100):
        request = item_transfer_protocol.DropRequest(x, y, uid, count)
        frame = SimpleNamespace(payload=item_transfer_protocol.build_drop_payload(request))
        return await reward._world_drop(self.ctx, self.writer, {}, object(), frame, None)

    def player_drop(self):
        return next(value for value in self.world.ground._items.values() if value.inventory_fields)

    def quantity(self, uid=1):
        return sum(dict(value.raw_fields)[4] for value in
                   inventory.validate_kit_frame(self.store.restore(uid)) if value.template_bits == 7)

    def other_player(self):
        chars = inventory_store.realm.CharacterStore(self.profile)
        chars.create(inventory_store.realm.Creation('SecondCase', 0, 0, (13,) * 6))
        frame = inventory.build_kit_frame([self.fields | {1: 200, 4: 0}])
        self.store.grant(2, frame)
        self.world.update_pc(2, 0, 100, 100)
        self.world.drain(2)
        writer = object()
        self.ctx._world_pcs[id(writer)] = (writer, 2)
        self.ctx.inventory_frame = frame
        return writer

    async def pickup(self, item, count, writer=None):
        frame = SimpleNamespace(payload=get_payload(item, count))
        return await reward._world_pickup(self.ctx, writer or self.writer, {}, object(), frame, None)

    async def test_drop_is_saved_then_visible_and_another_pc_can_pick_immediately(self):
        self.world.update_pc(2, 0, 100, 100)
        self.world.drain(2)
        self.assertTrue(await self.drop())
        item = self.player_drop()
        self.assertEqual(self.quantity(), 2)
        self.assertEqual(dict(item.inventory_fields), self.fields | {4: 3})
        self.assertIn(world_visibility.ground_frame(item), self.sent)
        self.assertIn(world_visibility.ground_frame(item), self.world.drain(2))
        other = self.other_player()
        self.assertTrue(await self.pickup(item, 3, other))
        self.assertEqual((self.quantity(1), self.quantity(2)), (2, 3))
        self.assertIsNone(self.world.ground.get(item.ref))
        self.assertIn(world_visibility.remove_frame(item.ref.uid), self.world.drain(1))
        self.assertTrue(await self.pickup(item, 3, other))
        self.assertEqual(self.quantity(2), 3)

    async def test_partial_drop_and_stack_pickup_force_existing_writebehind_to_disk(self):
        from tools.local_original_session.world_persist import WorldPersist
        persist = WorldPersist(self.world.runtime.scheduler,
            lambda key, frame: self.store.flush_world_snapshot(key[1], frame))
        self.store.enable_world_persist(persist)
        await self.drop(3)
        item = self.player_drop()
        fresh = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                               kit_policy=inventory.KIT_POLICY)
        self.assertEqual(dict(inventory.validate_kit_frame(fresh.restore(1))[0].raw_fields)[4], 2)
        await self.pickup(item, 2)
        self.assertEqual(dict(inventory.validate_kit_frame(fresh.restore(1))[0].raw_fields)[4], 4)
        self.assertEqual(self.world.ground.get(item.ref).count, 1)
        self.assertFalse(persist.pending_keys)

    async def test_map_leave_reconnect_keep_ground_and_restart_does_not_restore_it(self):
        await self.drop()
        item = self.player_drop()
        frames = self.world.update_pc(1, 1, 100, 100)
        self.assertIn(world_visibility.remove_frame(item.ref.uid), frames)
        self.assertIsNotNone(self.world.ground.get(item.ref))
        self.world.leave_pc(1)
        frames = self.world.update_pc(1, 0, 100, 100, reset=True)
        self.assertIn(world_visibility.ground_frame(item), frames)
        self.assertEqual(self.quantity(), 2)
        runtime = WorldRuntime(clock=lambda: 100.0)
        data = load_m1()
        restarted = world_visibility.WorldView(runtime,
            InterestSpawner(runtime.entities, data, passable=lambda *_: True), data=data)
        self.assertEqual(len(restarted.ground), 0)
        self.assertEqual(self.quantity(), 2)

    async def test_std_expiry_removes_for_observers_without_restoring_inventory(self):
        self.world.update_pc(2, 0, 100, 100)
        self.world.drain(2)
        await self.drop()
        item = self.player_drop()
        self.world.drain(2)
        self.world.runtime.scheduler.run_due(item.expires_at)
        self.assertIsNone(self.world.ground.get(item.ref))
        self.assertIn(world_visibility.remove_frame(item.ref.uid), self.world.drain(1))
        self.assertIn(world_visibility.remove_frame(item.ref.uid), self.world.drain(2))
        self.assertEqual(self.quantity(), 2)

    async def test_refused_quantity_equipped_and_cas_keep_inventory_and_publish_nothing(self):
        before = self.store.path.read_bytes()
        for count, uid, x in ((0, 100, 100), (6, 100, 100), (1, 999, 100), (1, 100, 105)):
            await self.drop(count, uid, x)
            self.assertFalse(any(i.inventory_fields for i in self.world.ground._items.values()))
        self.ctx._item_equipment_effect = SimpleNamespace(store=SimpleNamespace(
            restore=lambda *_: SimpleNamespace(weapon_uid=100, slots=())))
        await self.drop()
        del self.ctx._item_equipment_effect
        with mock.patch.object(self.store, 'replace_kit', return_value=False):
            await self.drop()
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse(any(i.inventory_fields for i in self.world.ground._items.values()))
        self.assertEqual(self.sent, [])

    async def test_drop_and_pickup_preserve_opaque_enchant_fields_for_new_owner(self):
        before = self.ctx.inventory_frame
        changed = self.fields | {5: 7, 18: b'+7 original opaque instance'}
        self.store.replace_kit(1, before, inventory.build_kit_frame([changed]))
        self.ctx.inventory_frame = self.store.restore(1)
        await self.drop()
        item = self.player_drop()
        other = self.other_player()
        await self.pickup(item, 3, other)
        picked = inventory.validate_kit_frame(self.store.restore(2))[-1]
        self.assertEqual({k: v for k, v in picked.raw_fields if k not in (1, 4)},
                         {k: v for k, v in changed.items() if k not in (1, 4)})

    async def test_error_after_durable_pickup_consumes_ground_and_prevents_repeat_credit(self):
        await self.drop()
        item = self.player_drop()
        original = self.store._atomic_write
        def fail_after(rows):
            original(rows)
            raise OSError('AFTER_REPLACE')
        with mock.patch.object(self.store, '_atomic_write', side_effect=fail_after):
            with self.assertRaisesRegex(RuntimeError, 'GROUND_INVENTORY_COMMIT_COMMITTED'):
                await self.pickup(item, 3)
        self.assertEqual(self.quantity(), 5)
        self.assertIsNone(self.world.ground.get(item.ref))
        await self.pickup(item, 3)
        self.assertEqual(self.quantity(), 5)

    async def test_unknown_save_blocks_repeat_and_known_unchanged_save_keeps_ground(self):
        await self.drop()
        item = self.player_drop()
        with mock.patch.object(self.store, 'replace_kit', side_effect=OSError('BEFORE_WRITE')):
            with self.assertRaisesRegex(RuntimeError, 'GROUND_INVENTORY_COMMIT_UNCHANGED'):
                await self.pickup(item, 3)
        self.assertIsNotNone(self.world.ground.get(item.ref))
        with mock.patch.object(self.store, 'replace_kit', side_effect=OSError('SAVE_UNKNOWN')), \
                mock.patch.object(self.store, '_read_disk', side_effect=OSError('READ_UNKNOWN')):
            with self.assertRaisesRegex(RuntimeError, 'GROUND_INVENTORY_COMMIT_UNKNOWN'):
                await self.pickup(item, 3)
        await self.pickup(item, 3)
        self.assertEqual(self.quantity(), 2)
        self.assertIsNotNone(self.world.ground.get(item.ref))

    async def test_drop_error_after_durable_debit_keeps_published_ground(self):
        original = self.store._atomic_write
        def fail_after(rows):
            original(rows)
            raise OSError('AFTER_DROP_REPLACE')
        with mock.patch.object(self.store, '_atomic_write', side_effect=fail_after):
            with self.assertRaisesRegex(RuntimeError, 'GROUND_INVENTORY_COMMIT_COMMITTED'):
                await self.drop()
        item = self.player_drop()
        self.assertEqual(self.quantity(), 2)
        self.assertIn(item.ref.uid, self.world.item_known[1])

    def test_drop_opcode_is_registered_and_legacy_custody_is_not_selected(self):
        from tools.local_original_session.world_handlers import feature_registry
        from tools.local_original_session.world_bridge import kit_policy
        registry = feature_registry()
        self.assertIn(0x4e3f, registry.frames)
        self.assertNotEqual(0x4e3c, item_transfer_protocol.DROP_OPCODE)
        self.assertIsNone(kit_policy('world', 'missing', None, 'legacy', inventory_store.POLICY))


class PickupActionFrameTests(unittest.TestCase):
    """Only in-memory ground state, commit callback and original wire fields."""

    def setUp(self):
        runtime = WorldRuntime(clock=lambda: 100.0)
        data = load_m1()
        self.world = world_visibility.WorldView(
            runtime, InterestSpawner(runtime.entities, data, passable=lambda *_: True), data=data)
        pc = self.world.entities.add(Kind.PC, 0, 100, 100, uid=1)
        corpse = self.world.entities.add(Kind.NPC, 0, 100, 100, template_id=0)
        self.world.entities.kill(corpse.uid)
        self.item, = self.world.ground.spawn_drops(corpse.ref, [(7, 10)], owner_uid=pc.uid)
        # Nearby, distant, other-map and outside-diamond viewers respectively.
        for uid, map_id, x, y in ((1, 0, 100, 100), (2, 0, 101, 100),
                                 (3, 0, 120, 100), (4, 1, 100, 100), (5, 0, 117, 117)):
            if uid != 1:
                self.world.entities.add(Kind.PC, map_id, x, y, uid=uid)
            self.world.pcs[uid] = (map_id, x, y)
        self.world.item_known[1] = {self.item.ref.uid}
        self.world.item_known[2] = {self.item.ref.uid}
        self.commits = []
        self.addCleanup(self.world.close)

    def commit(self, item, quantity):
        self.commits.append((item.ref, quantity))
        return [b'inventory-change']

    def assert_pickup_action(self, wire, uid=1):
        self.assertEqual(int.from_bytes(wire[:2], 'little'), len(wire))
        self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x4e39)
        self.assertEqual(wire[-2:], b'\0\0')
        with pb.parse_message(wire[4:-2], schema={1: 0, 2: 0}) as parsed:
            self.assertEqual([(field.number, field.value) for field in parsed.fields],
                             [(1, uid), (2, 15)])

    def test_raw_get15_frame_uses_actor_uid_and_existing_framing(self):
        self.assert_pickup_action(world_visibility.pickup_frame(0x123456789), 0x123456789)

    def test_success_publishes_raw_get15_to_self_and_only_screen_viewers(self):
        frames = self.world.pc_pickup(1, self.item.ref.uid, 3, self.commit)
        self.assertEqual(len(frames), 2)
        self.assert_pickup_action(frames[0])
        self.assertEqual(frames[1], b'inventory-change')
        observer = self.world.drain(2)
        self.assertEqual(len(observer), 1)
        self.assert_pickup_action(observer[0])
        self.assertEqual(observer[0], frames[0])
        for uid in (3, 4, 5):
            self.assertEqual(self.world.drain(uid), [])

        frames = self.world.pc_pickup(1, self.item.ref.uid, 7, self.commit)
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in frames[:2]],
                         [0x4e40, 0x4e39])
        self.assertEqual(frames[2], b'inventory-change')
        self.assert_pickup_action(frames[1])
        observer = self.world.drain(2)
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in observer],
                         [0x4e40, 0x4e39])
        self.assert_pickup_action(observer[1])
        self.assertIsNone(self.world.pc_pickup(1, self.item.ref.uid, 7, self.commit))
        self.assertEqual(self.world.drain(2), [])
        self.assertEqual(self.commits, [(self.item.ref, 3), (self.item.ref, 7)])

    def test_refused_or_failed_pickup_never_publishes_action_to_viewers(self):
        with mock.patch.object(self.world.combat, 'is_dead', return_value=True):
            self.assertEqual(self.world.pc_pickup(1, self.item.ref.uid, 3, self.commit), [])
        self.world.entities.move(1, 0, 120, 100)
        self.assertEqual(self.world.pc_pickup(1, self.item.ref.uid, 3, self.commit), [])
        self.world.entities.move(1, 0, 100, 100)
        for quantity in (0, 11, (1 << 64) - 1):
            self.assertEqual(self.world.pc_pickup(1, self.item.ref.uid, quantity, self.commit), [])
        with self.assertRaisesRegex(ValueError, 'persist-failed'):
            self.world.pc_pickup(1, self.item.ref.uid, 3,
                                 mock.Mock(side_effect=ValueError('persist-failed')))
        self.assertEqual(self.world.ground.get(self.item.ref), self.item)
        self.assertEqual(self.commits, [])
        for uid in (1, 2, 3, 4, 5):
            self.assertEqual(self.world.drain(uid), [])


if __name__ == '__main__':
    unittest.main()
