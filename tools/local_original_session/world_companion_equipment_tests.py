"""Saved PC bag/equipment transfer development tests; no game or listener."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import inventory, inventory_store, equipment_store
from tools.local_original_session.game_data import load_stances
from tools.local_original_session import world_companion_integration_tests as fixtures
from tools.local_original_session.world_feature_trade import CompanionInventory
from tools.local_original_session.world_enchant_inventory import enchanted_name
from tools.local_native_login_local_ack_hook import ack_enter_world as ack


def item(uid, template, count=1, name=b''):
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 71, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: name, 22: 0, 24: False, 25: 0, 26: False}


class CompanionEquipmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name).resolve() / 'characters.json'
        chars = ack.realm.CharacterStore(path)
        chars.create(ack.realm.Creation('FixtureKnight', 1, 0, (18, 13, 16, 10, 10, 10)))
        chars.create(ack.realm.Creation('FixtureMage', 3, 0, (8, 7, 16, 18, 8, 18)))
        self.store = inventory_store.InventoryStore(path, policy=inventory_store.POLICY,
                                                    kit_policy=inventory.KIT_POLICY)
        self.templates = (230, 90, 102, 104, 106, 120, 129, 113)
        fields = [item(10, 7, 100)] + [item(11 + index, template)
            for index, template in enumerate(self.templates)] + [item(30, 14, 20), item(31, 492, 10)]
        owner_frame = inventory.build_kit_frame(fields)
        self.store.grant(1, owner_frame)
        self.ctx = SimpleNamespace(world=self.fixture.view, inventory_store=self.store,
            inventory_frame=owner_frame, _companion_rows={r['uid']: r for r in chars._read()['characters']},
            _world_stances=load_stances(), _companion_save=Mock(),
            _companion_policy={'thresholds': {'hp': {'companion_emergency_enter': .35},
                                             'mp': {'recover_fraction': .4}}},
            _inventory_kit_frame=lambda _: inventory.build_kit_frame([
                item(50, 41), item(51, 103), item(52, 14, 0), item(53, 7, 100)]))
        self.bags = CompanionInventory(self.ctx)
        self.bags.equipment.initialize_kit(1, owner_frame,
            initialization=equipment_store.FIRST_ENABLE_EMPTY, weapon_uid=0, slots=())
        self.bags.initialize(2)
        self.record, self.actor = self.fixture.record, self.fixture.actor

    def give(self, source, count=1):
        return self.bags.give(1, self.actor, source, count, self.ctx.inventory_frame)

    def test_eight_slots_use_real_pc_save_and_unequip_changes_profile_and_wield(self):
        for index, template in enumerate(self.templates):
            self.give(11 + index)
        state = self.bags.states[2]
        self.assertEqual(len(state.slots), 7)
        self.assertEqual(self.bags.equipment.restore(2, self.store.restore(2)), state)
        self.assertEqual(self.ctx.world.companion_looks[2]['stance'], 50)
        self.assertEqual(self.ctx.world.companion_profiles[2].ac, self.bags.calculated(2)[0].ac)
        equipped = {state.weapon_uid, *(v for _, v in state.slots)}
        self.assertEqual(len(equipped), 8)
        self.assertTrue(self.bags.equip(2, state.weapon_uid))
        self.assertEqual(self.bags.states[2].weapon_uid, 0)
        self.assertEqual(self.ctx.world.companion_looks[2]['stance'], 0)
        self.assertTrue(any(int.from_bytes(w[2:4], 'little') == 0x4ed5
                            for w in self.ctx.world.drain(1)))

    def test_capacity_rejects_before_debit_and_never_uses_owner_capacity(self):
        before = self.ctx.inventory_frame
        self.bags.weights[230] = replace(self.bags.weights[230], raw_weight=100_000_000)
        with self.assertRaisesRegex(ValueError, 'COMPANION_WEIGHT_CAPACITY'):
            self.give(11)
        self.assertEqual(self.store.restore(1), before)
        self.assertFalse(self.bags.intent_path.exists())

    def test_interrupt_after_owner_debit_recovers_forward_once_with_auto_equip(self):
        original = self.store.replace_kit
        def fail_target(uid, *args, **kwargs):
            if uid == 2:
                raise OSError('TARGET_WRITE_FAILED')
            return original(uid, *args, **kwargs)
        with patch.object(self.store, 'replace_kit', side_effect=fail_target):
            with self.assertRaisesRegex(OSError, 'TARGET_WRITE_FAILED'):
                self.give(11)
        self.assertTrue(self.bags.intent_path.exists())
        self.assertNotIn(11, [r.identifier for r in inventory.validate_kit_frame(self.store.restore(1))])
        recovered = CompanionInventory(self.ctx)
        recovered.initialize(2)
        self.assertFalse(recovered.intent_path.exists())
        rows = inventory.validate_kit_frame(self.store.restore(2))
        staff = [r for r in rows if r.template_bits == 230]
        self.assertEqual(len(staff), 1)
        self.assertEqual(recovered.states[2].weapon_uid, staff[0].identifier)
        self.assertEqual(self.ctx.inventory_frame, self.store.restore(1))
        again = CompanionInventory(self.ctx)
        again.initialize(2)
        self.assertEqual(again.frames[2], recovered.frames[2])

    def test_equipped_owner_item_and_excess_quantity_cannot_be_given(self):
        state = self.bags.equipment.restore(1, self.ctx.inventory_frame)
        self.bags.equipment.compare_and_swap_kit(1, self.ctx.inventory_frame, state,
                                               weapon_uid=11, slots=())
        with self.assertRaisesRegex(ValueError, 'UNEQUIP_FIRST'):
            self.give(11)
        with self.assertRaisesRegex(ValueError, 'OWNED_QUANTITY'):
            self.give(30, 21)
        self.assertFalse(self.bags.intent_path.exists())

    def test_enchant_metadata_survives_transfer_and_affects_damage(self):
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.ctx.inventory_frame)]
        rows[1][18] = enchanted_name(self.ctx.world.data.items[230], 3)
        changed = inventory.build_kit_frame(rows)
        self.store.replace_kit(1, self.ctx.inventory_frame, changed)
        self.ctx.inventory_frame = changed
        self.give(11)
        self.assertEqual(self.ctx.world.companion_profiles[2].weapon.enchant, 3)

    def test_potions_consume_only_member_bag_and_persist_effect_without_refill(self):
        self.record.hp, self.record.mp = 1, 0
        self.give(30, 5)
        self.give(31, 2)
        owner = self.store.restore(1)
        self.assertTrue(self.bags.potion(self.actor, 10))
        self.assertGreater(self.record.hp, 1)
        self.assertTrue(self.bags.potion(self.actor, 11))
        self.assertEqual(self.record.mp, 0)
        self.assertGreater(self.record.equipment['blue_expires_unix'], 0)
        self.assertEqual(self.store.restore(1), owner)
        frame = self.store.restore(2)
        reopened = CompanionInventory(self.ctx)
        reopened.initialize(2)
        self.assertEqual(reopened.frames[2], frame)
        self.assertGreater(reopened.blue_until[2], self.ctx.world.runtime.clock())
        blue_count = sum(dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(frame)
                         if r.template_bits == 492)
        self.assertEqual(blue_count, 1)


if __name__ == '__main__':
    unittest.main()
