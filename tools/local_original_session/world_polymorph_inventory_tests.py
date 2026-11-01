"""Polymorph cost/takeoff and old-row projection on temporary stores; no ports.

Direct helper tests are development checks, not native or socket gameplay PASS.
"""
from pathlib import Path
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store, equipment_store
from tools.local_original_session import world_feature_items as feature
from tools.local_original_session.game_data import load_items
from tools.local_original_session.world_state_services import InventoryTransactions


def row(uid, template, count=1):
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
        13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0, 24: False, 25: 0, 26: False}


class PolymorphInventoryTests(unittest.TestCase):
    def test_default_startup_supplies_native_scroll_without_poly_experiment(self):
        policies = {}
        def add(values, **kwargs):
            policies.update((value.template_id, value) for value in values)
        owner = SimpleNamespace(world=SimpleNamespace(data=SimpleNamespace(items=load_items())),
            item_policies=policies, starter_fields=row(10, 299), add_item_policies=add,
            _world_enchant_exp=None)
        with patch.dict(os.environ):
            os.environ.pop('SL_EXPERIMENT_POLY', None)
            feature.setup_polymorph(owner)
            kit = feature._world_items_kit_frame(owner,
                inventory.build_kit_frame([row(10, 299)]), 1)
            pickup = feature._world_items_pickup_fields(owner, row(11, 299),
                SimpleNamespace(item_id=299, grade=1))
        self.assertEqual(policies[299].grant_fields[5], 16)
        self.assertEqual(dict(inventory.validate_kit_frame(kit)[0].raw_fields)[5], 16)
        self.assertEqual(pickup[5], 16)
        self.assertEqual(owner._world_poly_catalog.native_names['orc morph'], 'orc')
        self.assertEqual(owner._world_polymorphs, {})

    def test_owned_polymorph_uses_existing_immediate_save_boundary(self):
        owner = SimpleNamespace(_inventory_kit_policy=inventory.KIT_POLICY,
            _inventory_current_frame=inventory.build_kit_frame([row(10, 299), row(11, 3)]))
        boundary = feature.SAVE_BOUNDARIES['_world_polymorph_use']
        self.assertTrue(boundary(owner, (object(), b'\x08\x0a\x12\x00')))
        self.assertFalse(boundary(owner, (object(), b'\x08\x0b\x12\x00')))
        self.assertFalse(boundary(owner, (object(), b'\x08\x0c\x12\x00')))

    def test_scroll_cost_and_weapon_takeoff_use_one_existing_joint_transaction(self):
        for quantity in (1, 2):
            with self.subTest(quantity=quantity), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'characters.json'
                roster = inventory_store.realm.CharacterStore(path)
                roster.create(inventory_store.realm.Creation('PolyOne', 1, 0, (13,) * 6))
                store = inventory_store.InventoryStore(path, policy=inventory_store.POLICY,
                    kit_policy=inventory.KIT_POLICY)
                before = inventory.build_kit_frame([row(10, 299, quantity), row(11, 3), row(12, 7, 100)])
                store.grant(1, before)
                defs = load_items()
                equipment = equipment_store.EquipmentStore(store, policy=equipment_store.POLICY,
                    kit_policy=inventory.KIT_POLICY, item_defs=defs)
                equipment.initialize_kit(1, before, initialization=equipment_store.FIRST_ENABLE_EMPTY,
                    weapon_uid=11, slots=())
                old = equipment.restore(1, before)
                changes = []
                owner = SimpleNamespace(inventory_frame=before,
                    _item_equipment_effect=SimpleNamespace(store=equipment),
                    inventory_transactions=InventoryTransactions(store),
                    run_sync_hooks=lambda *args: changes.append(args))
                ctx = SimpleNamespace(pc_uid=1, writer=object(), row={}, commit_attempted=False)
                scroll = inventory.validate_kit_frame(before)[0]
                wire, after_equipment, notifications = feature._world_polymorph_takeoff(
                    owner, ctx, scroll, defs[3])
                after = store.restore(1)
                items = {i.identifier: dict(i.raw_fields) for i in inventory.validate_kit_frame(after)}
                self.assertTrue(ctx.commit_attempted)
                self.assertEqual(owner.inventory_frame, after)
                self.assertEqual(equipment.restore(1, after), after_equipment)
                self.assertEqual(after_equipment.weapon_uid, 0)
                self.assertEqual(after_equipment.revision, old.revision + 1)
                self.assertEqual(items[11], row(11, 3))
                self.assertEqual(items[12], row(12, 7, 100))
                self.assertEqual(notifications, ((11, defs[3].slot_key, False),))
                self.assertEqual(changes[0][0], 'inventory_changed')
                self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x0978 if quantity == 1 else 0x0965)
                self.assertEqual(items.get(10, {}).get(4, 0), quantity - 1)
                self.assertEqual(after_equipment.item_uid, 11 if quantity == 1 else 10)


class ProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_raw0_save_is_projected_without_rewriting_current_or_store(self):
        before = inventory.build_kit_frame([row(10, 299, 5), row(11, 3)])
        sent = []
        async def send(*args):
            sent.extend(args[2])
        owner = SimpleNamespace(inventory_frame=before, _world_send=send)
        await feature._world_items_inventory_delivered(owner, object(), {}, object(), object())
        self.assertEqual(owner.inventory_frame, before)
        self.assertEqual(len(sent), 1)
        from tools.local_original_session.world_enchant_inventory_tests import update_fields
        self.assertEqual(update_fields(sent[0]), {1: 10, 5: 16})


if __name__ == '__main__':
    unittest.main()
