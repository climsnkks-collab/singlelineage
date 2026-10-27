"""World save semantics on temporary profiles; no sockets, game or native input."""
from dataclasses import replace
import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_character_creation.realm import CharacterStore, Creation
from tools.local_original_session import inventory, inventory_store, movement, world_bridge
from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
from tools.local_original_session.world_persist import WorldPersist
from tools.local_original_session.world_progress import Progress, ProgressStore
from tools.local_original_session.world_scheduler import Scheduler


class WorldWritebehindTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.profile = Path(temp.name) / 'characters.json'
        self.characters = CharacterStore(self.profile)
        self.characters.create(Creation('SaveHero', 1, 0, (18, 12, 16, 9, 9, 8)))
        self.now = 0.
        self.scheduler = Scheduler(clock=lambda: self.now)

    def positions(self):
        disk = movement.PositionStore(self.profile)
        holder = {}
        persist = WorldPersist(self.scheduler,
            lambda key, snapshot: holder['store'].flush_snapshot(key[1], snapshot))
        store = holder['store'] = world_bridge._WorldPositions(disk, persist)
        return disk, store, persist

    def kit(self, quantity=20):
        return inventory.build_kit_frame([dict(INVENTORY_STARTER_FIELDS) |
            {1: 65537, 2: 1, 4: quantity}, dict(INVENTORY_STARTER_FIELDS) |
            {1: 65538, 2: 14, 4: 10}])

    def inventory(self):
        disk = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        initial = self.kit()
        disk.grant(1, initial)
        persist = WorldPersist(self.scheduler,
            lambda key, snapshot: disk.flush_world_snapshot(key[1], snapshot))
        disk.enable_world_persist(persist)
        return disk, persist, initial

    def test_many_moves_are_memory_cas_then_one_latest_atomic_save(self):
        disk, store, persist = self.positions()
        start = movement.Position(1, 'SaveHero', 0, 100, 100)
        store.restore(start)
        service = movement.MovementService(start, connection=object(), store=store,
            owner_guard=lambda *_: True, edge_passability=lambda *_: True)
        self.assertEqual(service.snapshot(), start)
        current = start
        with patch.object(disk, '_read', wraps=disk._read) as reads, \
                patch.object(disk, '_write', wraps=disk._write) as writes:
            for x in range(101, 201):
                updated = replace(current, word0=x)
                store.commit(current, updated)
                self.assertEqual(store.restore(start), updated)
                current = updated
            self.assertEqual((reads.call_count, writes.call_count), (0, 0))
            with self.assertRaisesRegex(ValueError, 'AUTHORITY_CHANGED'):
                store.commit(start, replace(start, word1=101))
            self.now = 45
            self.scheduler.run_due()
            self.assertEqual(writes.call_count, 1)
        self.assertEqual(disk.restore(start), current)
        self.assertFalse(persist.pending_keys)

    def test_position_external_cas_conflict_preserves_pending_latest(self):
        disk, store, persist = self.positions()
        initial = movement.Position(1, 'SaveHero', 0, 100, 100)
        store.restore(initial)
        latest = replace(initial, word0=101)
        store.commit(initial, latest)
        external = replace(initial, word1=200)
        disk.commit(initial, external)
        with self.assertLogs('tools.local_original_session.world_persist', level='ERROR'):
            result = persist.flush_all()
        self.assertFalse(result.ok)
        self.assertEqual(persist.snapshot(('position', 1)), latest)
        self.assertEqual(disk.restore(initial), external)

    def test_map_transition_flushes_immediately(self):
        disk, store, persist = self.positions()
        initial = movement.Position(1, 'SaveHero', 0, 100, 100)
        final = replace(initial, map_id=1)
        store.commit(initial, final, transition=True)
        self.assertEqual(disk.restore(initial), final)
        self.assertFalse(persist.pending_keys)

    def test_position_replace_then_raise_can_flush_a_newer_absolute_snapshot(self):
        disk, store, persist = self.positions()
        initial = movement.Position(1, 'SaveHero', 0, 100, 100)
        first, latest = replace(initial, word0=101), replace(initial, word0=102)
        store.commit(initial, first)
        atomic = disk._write
        def ambiguous(data):
            atomic(data)
            raise OSError('after replace')
        with patch.object(disk, '_write', side_effect=ambiguous), \
                self.assertLogs('tools.local_original_session.world_persist', level='ERROR'):
            self.assertFalse(persist.flush_all().ok)
        store.commit(first, latest)
        self.assertTrue(persist.flush_all().ok)
        self.assertEqual(disk.restore(initial), latest)

    def test_quantity_latest_snapshot_and_item_removal_boundary(self):
        store, persist, initial = self.inventory()
        before = store.path.read_bytes()
        updated = self.kit(19)
        store.replace_kit(1, initial, updated)
        latest = self.kit(18)
        store.replace_kit(1, updated, latest)
        self.assertEqual(store.restore(1), latest)
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual(inventory_store.InventoryStore._read(store)[0][1], latest)
        removed = inventory.build_kit_frame([dict(inventory.validate_kit_frame(latest)[0].raw_fields)])
        store.replace_kit(1, latest, removed)
        self.assertFalse(persist.pending_keys)
        self.assertEqual(store._read_disk()[0][1], removed)

    def test_last_row_zero_quantity_is_an_immediate_consumption_boundary(self):
        store, persist, initial = self.inventory()
        final_row = inventory.build_kit_frame([dict(inventory.validate_kit_frame(initial)[0].raw_fields)])
        store.replace_kit(1, initial, final_row)
        zero = inventory.build_kit_frame([dict(inventory.validate_kit_frame(final_row)[0].raw_fields) | {4: 0}])
        store.replace_kit(1, final_row, zero)
        self.assertFalse(persist.pending_keys)
        self.assertEqual(store._read_disk()[0][1], zero)

    def test_ordinary_potion_candidate_does_not_open_enchant_flush_boundary(self):
        store, persist, initial = self.inventory()
        broker = SimpleNamespace(_world_persist=persist, _inventory_store=store,
            _inventory_kit_policy=inventory.KIT_POLICY, _inventory_current_frame=initial)
        pb = world_bridge.ack.realm.pb
        payload = pb.encode_message([pb.encode_uint32(1, 65538), pb.encode_bytes(2, b'')])
        self.assertFalse(world_bridge._save_boundary(broker, '_world_enchant_use',
                                                    (object(), payload, 0.)))
        scroll = inventory.build_kit_frame([dict(item.raw_fields) | ({2: 25} if item.identifier == 65538 else {})
                                           for item in inventory.validate_kit_frame(initial)])
        broker._inventory_current_frame = scroll
        self.assertTrue(world_bridge._save_boundary(broker, '_world_enchant_use',
                                                   (object(), payload, 0.)))

    def test_inventory_immediate_and_deferred_external_conflicts_refuse(self):
        store, persist, initial = self.inventory()
        external = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        external_frame = self.kit(17)
        external.replace_kit(1, initial, external_frame)
        removed = inventory.build_kit_frame([dict(inventory.validate_kit_frame(initial)[0].raw_fields)])
        with self.assertRaisesRegex(ValueError, 'EXPECTED_FRAME_CHANGED'):
            store.replace_kit(1, initial, removed)
        self.assertEqual(store.restore(1), initial)
        latest = self.kit(19)
        store.replace_kit(1, initial, latest)
        with self.assertLogs('tools.local_original_session.world_persist', level='ERROR'):
            result = persist.flush_all()
        self.assertFalse(result.ok)
        self.assertEqual(persist.snapshot(('inventory', 1)), latest)
        self.assertEqual(external.restore(1), external_frame)

    def test_inventory_replace_then_raise_can_flush_a_newer_absolute_snapshot(self):
        store, persist, initial = self.inventory()
        first, latest = self.kit(19), self.kit(18)
        store.replace_kit(1, initial, first)
        atomic = store._atomic_write
        def ambiguous(rows):
            atomic(rows)
            raise OSError('after replace')
        with patch.object(store, '_atomic_write', side_effect=ambiguous), \
                self.assertLogs('tools.local_original_session.world_persist', level='ERROR'):
            self.assertFalse(persist.flush_all().ok)
        store.replace_kit(1, first, latest)
        self.assertTrue(persist.flush_all().ok)
        self.assertEqual(store._read_disk()[0][1], latest)

    def test_external_inventory_row_deletion_cannot_be_revived_by_flush(self):
        store, persist, initial = self.inventory()
        latest = self.kit(19)
        store.replace_kit(1, initial, latest)
        external = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        external._atomic_write({})
        with self.assertLogs('tools.local_original_session.world_persist', level='ERROR'):
            result = persist.flush_all()
        self.assertFalse(result.ok)
        self.assertEqual(str(result.failures[0].error), 'INVENTORY_STORE_EXPECTED_FRAME_CHANGED')
        self.assertEqual(persist.snapshot(('inventory', 1)), latest)
        self.assertIsNone(external.restore(1))

    def test_new_roster_member_can_receive_kit_and_other_disk_rows_survive(self):
        store, persist, initial = self.inventory()
        self.characters.create(Creation('SecondHero', 1, 0, (18, 12, 16, 9, 9, 8)))
        external = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        external.grant(2, self.kit(8))
        removed = inventory.build_kit_frame([dict(inventory.validate_kit_frame(initial)[0].raw_fields)])
        store.replace_kit(1, initial, removed)
        self.assertEqual(external.restore(2), self.kit(8))
        self.assertEqual(store.restore(2), self.kit(8))
        self.assertFalse(store.grant(2, self.kit(8)))
        with self.assertRaisesRegex(ValueError, 'ITEM_CONFLICT'):
            store.grant(2, self.kit(6))
        self.assertEqual(external.restore(2), self.kit(8))
        self.characters.create(Creation('ThirdHero', 1, 0, (18, 12, 16, 9, 9, 8)))
        store.grant(3, self.kit(7))
        self.assertEqual(external.restore(3), self.kit(7))

    def test_progress_memory_stage_and_vitals_fresh_reload(self):
        store = ProgressStore(self.profile)
        value = Progress(15, 1, 200, 50)
        store.stage(1, value)
        self.assertEqual(store.get(1), value)
        self.assertFalse(store.path.exists())
        store.commit(1, value)  # Direct quest callers retain synchronous commits.
        store.save_vitals(1, (37, 12))
        fresh = ProgressStore(self.profile)
        self.assertEqual(fresh.get(1), value)
        self.assertEqual(fresh.vitals(1), (37, 12))
        fresh.path.with_name('vitals.json').write_text('{"version":1,"rows":[{}]}', encoding='ascii')
        invalid = ProgressStore(self.profile)
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'VITALS_STORE_ROW'):
                invalid.vitals(1)

    def test_trade_wrapper_flushes_quantity_before_return_and_leave_stays_open(self):
        store, persist, initial = self.inventory()
        broker = SimpleNamespace(_world_persist=persist, _inventory_store=store,
            _world=SimpleNamespace(progress_dirty={}, combat=SimpleNamespace(pcs={}, vitals={})),
            _world_vital_snapshots={})
        def _world_quest_action(context):
            context._inventory_store.replace_kit(1, initial, self.kit(19))
        wrapped = world_bridge._adapter(_world_quest_action)
        wrapped(broker)
        self.assertEqual(store._read_disk()[0][1], self.kit(19))
        self.assertFalse(persist.pending_keys)
        self.assertFalse(persist.closed)

    def test_save_failure_does_not_skip_leave_and_exit_request_cannot_ack(self):
        failures, left = [], []
        def unavailable(key, snapshot):
            raise OSError('disk unavailable')
        persist = WorldPersist(self.scheduler, unavailable)
        persist.enqueue(('inventory', 1), b'latest')
        broker = SimpleNamespace(_world_persist=persist, _inventory_store=None,
            _world=SimpleNamespace(progress_dirty={}, combat=SimpleNamespace(pcs={}, vitals={})),
            _world_vital_snapshots={}, _fail=failures.append)
        async def _world_leave(context, writer):
            left.append(writer)
        writer = object()
        with self.assertLogs('tools.local_original_session.world_persist', level='ERROR'):
            asyncio.run(world_bridge._adapter(_world_leave)(broker, writer))
        self.assertEqual(left, [writer])
        self.assertIn('WORLD_PERSIST_FAILED', failures)
        self.assertEqual(persist.snapshot(('inventory', 1)), b'latest')
        self.assertFalse(persist.closed)
        frame = SimpleNamespace(opcode=0x4e3c)
        with self.assertLogs('tools.local_original_session.world_persist', level='ERROR'), \
                self.assertRaisesRegex(OSError, 'disk unavailable'):
            asyncio.run(world_bridge.receive(broker, writer, {}, None, frame, None))


if __name__ == '__main__':
    unittest.main()
