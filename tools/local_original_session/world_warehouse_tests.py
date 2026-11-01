"""Warehouse codec and interrupted asset saves on temporary profiles only."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store, equipment_store
from tools.local_original_session import world_warehouse as w


def fields(uid, count=1):
    return {1: uid, 2: 1, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'\0metadata', 22: 0,
            24: False, 25: 0, 26: False}


def kit(*rows):
    return inventory.build_kit_frame(list(rows))


class WireTests(unittest.TestCase):
    def test_count_required_fields_and_context_are_explicit(self):
        frame = w.count_frame(123, kind=1, f1=8, f3=150)
        self.assertEqual(frame[2:4], bytes.fromhex('d24e'))
        with w.pb.parse_message(frame[4:-2]) as parsed:
            self.assertEqual({f.number: f.value for f in parsed.fields}, {1: 8, 2: 1, 3: 150, 4: 123})
        self.assertEqual([w.request_mode('deposit', kind) for kind in (1, 2, 3)], [1, 3, 1])
        self.assertEqual([w.request_mode('withdraw', kind) for kind in (1, 2, 3)], [2, 4, 2])

    def test_list_full_iteminfo_and_opaque_key_are_separate(self):
        item = inventory.validate_kit_frame(kit(fields(19, 7)))[0]
        frame = w.list_frame(123, [(9001, item)], kind=3, f2=4, f4=5, f5=1 << 40, f6=6)
        self.assertEqual(frame[2:4], bytes.fromhex('7109'))
        with w.pb.parse_message(frame[4:-2]) as outer:
            self.assertEqual({f.number: f.value for f in outer.fields if f.wire_type == 0},
                             {1: 123, 2: 4, 3: 3, 4: 5, 5: 1 << 40, 6: 6, 8: 1})
            with w.pb.parse_message(outer.occurrences(7)[0].value) as row:
                self.assertEqual(row.occurrences(1)[0].value, 9001)
                full = bytes(row.occurrences(2)[0].value)
                with w.pb.parse_message(full) as original:
                    self.assertEqual(original.occurrences(1)[0].value, 19)
                    self.assertEqual(bytes(original.occurrences(18)[0].value), b'\0metadata')
                with w.pb.parse_message(kit(fields(19, 7))[4:-2]) as expected:
                    self.assertEqual(full, bytes(expected.occurrences(1)[0].value))

    def test_150_slots_and_empty_list(self):
        items = inventory.validate_kit_frame(kit(*(fields(uid) for uid in range(1, 151))))
        self.assertTrue(w.list_frame(1, enumerate(items, 1), kind=1, f2=0, f4=0, f5=0, f6=0))
        self.assertTrue(w.list_frame(1, (), kind=1, f2=0, f4=0, f5=0, f6=0))
        with self.assertRaises(ValueError):
            w.list_frame(1, [(1, items[0]), (1, items[1])], kind=1, f2=0, f4=0, f5=0, f6=0)

    def test_native_close_empty_and_optional_enum_are_not_business_success(self):
        self.assertIsNone(w.close_body(b''))
        self.assertIsNone(w.close_body(b'\x08\x01'))
        with self.assertRaises(ValueError):
            w.close_body(b'\x10\x01')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('WarehouseOne', 0, 0, (13,) * 6))
        roster.create(inventory_store.realm.Creation('WarehouseTwo', 0, 0, (13,) * 6))
        self.inv = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                  kit_policy=inventory.KIT_POLICY)
        self.before = kit(fields(10, 10), fields(11, 1))
        self.after = kit(fields(10, 5), fields(11, 1))
        self.bank = kit(fields(20, 5))
        self.inv.grant(1, self.before)
        self.inv.grant(2, kit(fields(30)))
        self.other = self.inv.restore(2)
        self.store = w.WarehouseStore(self.inv)

    def commit(self, **kwargs):
        return self.store.commit(1, self.before, self.after, None, self.bank, **kwargs)

    def assert_recovered(self):
        recovered = w.WarehouseStore(self.inv)
        self.assertEqual(self.inv.restore(1), self.after)
        self.assertEqual(self.inv.restore(2), self.other)
        self.assertEqual(recovered.restore(1), self.bank)
        self.assertFalse(recovered.intent_path.exists())

    def test_transfer_persists_exact_envelope_and_empty_deletes_only_row(self):
        self.assertTrue(self.commit())
        data = json.loads(self.store.path.read_bytes())
        self.assertEqual(data, {'version': 1, 'inventories': [{'uid': 1, 'frame': self.bank.hex()}]})
        self.assert_recovered()
        self.assertTrue(self.store.commit(1, self.after, self.before, self.bank, None))
        self.assertEqual(json.loads(self.store.path.read_bytes()), {'version': 1, 'inventories': []})
        self.assertEqual(self.inv.restore(1), self.before)

    def test_cache_reads_no_files_and_noop_creates_no_intent(self):
        with patch.object(Path, 'open', side_effect=AssertionError('REQUEST_READ')):
            self.assertIsNone(self.store.restore(1))
            self.assertEqual(self.store.rows(), {})
        self.assertFalse(self.store.commit(1, self.before, self.before, None, None))
        self.assertFalse(self.store.intent_path.exists())

    def test_interrupt_before_inventory_save_recovers_forward_once(self):
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('inventory interrupted')):
            with self.assertRaises(OSError):
                self.commit()
        self.assertEqual(self.inv.restore(1), self.before)
        self.assertTrue(self.store.intent_path.exists())
        with self.assertRaisesRegex(ValueError, 'RECOVERY_REQUIRED'):
            self.commit()
        self.assert_recovered()

    def test_interrupt_after_inventory_save_recovers_missing_warehouse(self):
        with patch.object(self.store, '_write_rows', side_effect=OSError('warehouse interrupted')):
            with self.assertRaises(OSError):
                self.commit()
        self.assertEqual(self.inv.restore(1), self.after)
        self.assert_recovered()

    def test_interrupt_after_both_saves_does_not_recharge_or_repeat_inventory_cas(self):
        original = Path.unlink
        def interrupted(path, *args, **kwargs):
            if path == self.store.intent_path:
                raise OSError('intent cleanup interrupted')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'unlink', interrupted), self.assertRaises(OSError):
            self.commit()
        with patch.object(self.inv, 'replace_kit', side_effect=AssertionError('REPEATED_CAS')):
            self.assert_recovered()

    def test_unrelated_recovery_state_is_preserved_and_refused(self):
        with patch.object(self.inv, 'replace_kit', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.commit()
        intent = self.store.intent_path.read_bytes()
        unrelated = kit(fields(10, 9), fields(11))
        self.inv.replace_kit(1, self.before, unrelated)
        with self.assertRaisesRegex(ValueError, 'RECOVERY_STATE_CONFLICT'):
            w.WarehouseStore(self.inv)
        self.assertEqual(self.store.intent_path.read_bytes(), intent)
        self.assertEqual(self.inv.restore(1), unrelated)

    def test_anchor_removal_saves_equipment_and_recovers_before_equipment_constructor(self):
        definitions = {1: SimpleNamespace(kind='weapon')}
        equip = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=definitions)
        old = equip.initialize_kit(1, self.before, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                                   weapon_uid=10, slots=())
        after = kit(fields(11))
        new = replace(old, item_uid=11, weapon_uid=0, revision=old.revision + 1)
        atomic = w._atomic_raw
        def interrupt_equipment(path, raw):
            if path == equip.path:
                raise OSError('equipment interrupted')
            atomic(path, raw)
        with patch.object(w, '_atomic_raw', side_effect=interrupt_equipment):
            with self.assertRaises(OSError):
                self.store.commit(1, self.before, after, None, None,
                    equipment_store=equip, equipment_before=old, equipment_after=new)
        self.assertEqual(self.inv.restore(1), after)
        recovered = w.WarehouseStore(self.inv)
        fresh = equipment_store.EquipmentStore(self.inv, policy=equipment_store.POLICY,
            kit_policy=inventory.KIT_POLICY, item_defs=definitions)
        self.assertEqual(fresh.restore(1, after), new)
        self.assertIsNone(recovered.restore(1))
        self.assertFalse(recovered.intent_path.exists())


if __name__ == '__main__':
    unittest.main()
