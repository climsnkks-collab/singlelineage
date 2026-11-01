"""Pure reference-policy tests; no game/server/broker/save or temporary files.

Positive item-weight fixtures are explicit L1J reference inputs, NOT current
M1 table weights: Classic14 -> etcitem40010 raw3900 (SQL:16464), Classic40 ->
weapon1 raw10000 (SQL:63702), Classic7 -> etcitem40308 raw0 (existing
spellbook/adena-normal-acquisition-v1 facts, published by
integration-1/warehouse-unit-weight-source-v1/API.md). Current M1 weight cells
are absent, and the separate real-table test requires their explicit failure.
"""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from tools.local_original_session import game_data as g, world_weight as w


def row(uid, template, count):
    # inventory.ItemInfo's actual public raw_fields shape: f1 UID/f2 ID/f4 Q.
    return SimpleNamespace(raw_fields=((1, uid), (2, template), (4, count)))


class WeightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = g.load_items()
        cls.reference_document = {'items': [
            {'id': {'value': 14}, 'weight': {
                'value': 3900, 'source': 'l1j',
                'ref': 'D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql:16464 etcitem40010'}},
            {'id': {'value': 40}, 'weight': {
                'value': 10000, 'source': 'l1j',
                'ref': 'D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql:63702 weapon1'}},
            {'id': {'value': 7}, 'weight': {
                'value': 0, 'source': 'l1j',
                'ref': 'warehouse-unit-weight-source-v1/API.md: optional Adena etcitem40308'}},
        ]}
        cls.definitions = {template: cls.items[template] for template in (14, 40, 7)}
        cls.catalog = w.weight_catalog(cls.reference_document, cls.definitions)

    def test_actual_m1_weight_loading_reports_missing_or_preserves_values(self):
        document = json.loads((g.M1_DATA_DIR / 'items.json').read_text(encoding='utf-8'))
        missing = sorted(row['id']['value'] for row in document['items'] if 'weight' not in row)
        if missing:
            with self.assertRaises(ValueError) as caught:
                w.load_weight_catalog()
            self.assertEqual(str(caught.exception), 'ITEM_WEIGHT_MISSING: ' + ','.join(map(str, missing)))
        else:
            catalog = w.load_weight_catalog()
            self.assertEqual(set(catalog), set(self.items))
            for entry in document['items']:
                template, cell = entry['id']['value'], entry['weight']
                self.assertEqual(catalog[template].item, self.items[template])
                self.assertEqual(catalog[template].raw_weight, cell['value'])
                self.assertEqual(catalog[template].source,
                                 g.Source(cell['source'], cell['ref'], cell.get('note', '')))

    def test_catalog_retains_actual_itemdef_and_weight_provenance(self):
        self.assertIs(self.catalog[14].item, self.items[14])
        self.assertEqual((self.items[14].name_ko, self.items[14].stackable), ('빨간 물약', True))
        self.assertEqual(self.catalog[14].source.kind, 'l1j')
        self.assertIn('etcitem40010', self.catalog[14].source.ref)
        self.assertEqual(self.catalog[7].raw_weight, 0)
        with self.assertRaises(TypeError):
            self.catalog[14] = self.catalog[7]

    def test_missing_or_invalid_weight_does_not_become_zero(self):
        document = deepcopy(self.reference_document)
        del document['items'][0]['weight']
        with self.assertRaisesRegex(ValueError, 'ITEM_WEIGHT_MISSING: 14'):
            w.weight_catalog(document, self.definitions)
        for value in (-1, True, 3.9):
            document = deepcopy(self.reference_document)
            document['items'][0]['weight']['value'] = value
            with self.assertRaises(ValueError):
                w.weight_catalog(document, self.definitions)
        document = deepcopy(self.reference_document)
        document['items'][0]['weight']['source'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'PROVENANCE_REQUIRED: 14'):
            w.weight_catalog(document, self.definitions)

    def test_reference_stack_rounds_after_count_and_clamps_nonzero(self):
        self.assertEqual([w.stack_weight(3900, n) for n in (1, 2, 10)], [3, 7, 39])
        self.assertEqual(w.stack_weight(1, 1), 1)
        self.assertEqual(w.stack_weight(1, 999), 1)
        self.assertEqual(w.stack_weight(1, 2000), 2)
        self.assertEqual(w.stack_weight(0, 2_000_000_000), 0)
        for args in ((1, 0), (1, -1), (-1, 1), (True, 1)):
            with self.assertRaises(ValueError):
                w.stack_weight(*args)

    def test_inventory_sums_instances_not_templates_or_per_unit_rounds(self):
        rows = [row(101, 40, 1), row(102, 14, 10), row(103, 7, 1000)]
        before = [entry.raw_fields for entry in rows]
        self.assertEqual(w.inventory_weight(rows, self.catalog), 49)
        self.assertEqual([entry.raw_fields for entry in rows], before)
        split = [row(104, 14, 1), row(105, 14, 1)]
        self.assertEqual(w.inventory_weight(split, self.catalog), 6)
        self.assertEqual(w.inventory_weight([row(106, 14, 2)], self.catalog), 7)
        self.assertEqual(w.inventory_weight([], self.catalog), 0)
        with self.assertRaisesRegex(ValueError, 'ITEM_WEIGHT_MISSING: 41'):
            w.inventory_weight([row(107, 41, 1)], self.catalog)

    def test_capacity_current_str_con_floor_and_no_stat_clamp(self):
        self.assertEqual(w.maximum_weight(13, 10), 1800)
        self.assertEqual(w.maximum_weight(14, 10), 1950)
        self.assertEqual(w.maximum_weight(1, 1), 300)
        self.assertEqual(w.maximum_weight(100, 100), 15150)
        self.assertEqual(w.maximum_weight(13, 10, rate=0), 0)

    def test_capacity_modifier_order_and_fractional_capacity(self):
        # 1800*(1+.10+.05+.04*(1+2)) +180, then server rate 2.
        self.assertAlmostEqual(w.maximum_weight(13, 10, armor_percent=10, doll_percent=5,
            original_str_points=1, original_con_points=2, decrease_weight=True, rate=2), 4932)
        self.assertAlmostEqual(w.maximum_weight(13, 10, armor_percent=0.01), 1800.18)
        # Bonuses are caller-supplied original-stat points, not inferred stats.
        self.assertEqual(w.maximum_weight(13, 10), 1800)
        with self.assertRaises(ValueError):
            w.maximum_weight(13, 10, rate=-1)

    def test_gauge_half_up_and_maximum_clamp(self):
        self.assertEqual(w.weight240(5, 2400), 1)  # .5, not Python round(.5)==0
        self.assertEqual(w.weight240(15, 2400), 2)
        self.assertEqual(w.weight240(1194, 2400), 119)
        self.assertEqual(w.weight240(1195, 2400), 120)
        self.assertEqual(w.weight240(2400, 2400), 240)
        self.assertEqual(w.weight240(4000, 2400), 240)
        self.assertEqual(w.weight240(0, 0), 0)
        self.assertEqual(w.weight240(1, 0), 240)
        self.assertEqual(w.weight240(4000, 0, rate=0), 0)

    def test_fifty_percent_and_rounded_early_suppression(self):
        self.assertFalse(w.weight_state(1194, 2400).hp_bonus_suppressed)
        self.assertTrue(w.weight_state(1195, 2400).hp_bonus_suppressed)
        half = w.weight_state(1200, 2400)
        self.assertTrue(half.hp_bonus_suppressed)
        self.assertTrue(half.mp_base_suppressed)
        self.assertFalse(half.attack_blocked)

    def test_attack_and_normal_skill_refuse_at_197_not_100_percent(self):
        self.assertFalse(w.weight_state(1964, 2400).attack_blocked)
        state = w.weight_state(1965, 2400)
        self.assertEqual(state.gauge, 197)
        self.assertTrue(state.attack_blocked)
        self.assertTrue(state.normal_skill_blocked)
        self.assertFalse(state.at_capacity_gauge)
        for weight in (2395, 2400, 2500):
            state = w.weight_state(weight, 2400)
            self.assertEqual(state.gauge, 240)
            self.assertTrue(state.at_capacity_gauge)
            self.assertTrue(state.attack_blocked)

    def test_regen_exemptions_do_not_override_attack_limit(self):
        for kwargs in ({'exotic_vitalize': True}, {'additional_fire': True}):
            state = w.weight_state(2400, 2400, **kwargs)
            self.assertFalse(state.hp_bonus_suppressed)
            self.assertFalse(state.mp_base_suppressed)
            self.assertTrue(state.attack_blocked)
        state = w.weight_state(2400, 2400, hp_equipped_20049=True)
        self.assertFalse(state.hp_bonus_suppressed)
        self.assertTrue(state.mp_base_suppressed)

    def test_hp_suppression_preserves_later_con_and_negative_equipment(self):
        over = w.weight_state(1200, 2400)
        self.assertEqual(w.hp_regen_after_weight(5, 3, 16, over), 6)
        self.assertEqual(w.hp_regen_after_weight(5, 3, 10, over), 0)
        self.assertEqual(w.hp_regen_after_weight(5, 3, 9, over), 1)
        self.assertEqual(w.hp_regen_after_weight(5, -2, 16, over), 4)
        light = w.weight_state(0, 2400)
        self.assertEqual(w.hp_regen_after_weight(5, 3, 16, light), 14)

    def test_mp_suppression_still_has_at_least_twelve_wis_contribution(self):
        over = w.weight_state(1200, 2400)
        self.assertEqual(w.mp_regen_after_weight(5, 3, 10, over), 12)
        self.assertEqual(w.mp_regen_after_weight(5, 3, 25, over), 13)
        self.assertEqual(w.mp_regen_after_weight(5, -2, 25, over), 11)
        self.assertEqual(w.mp_regen_after_weight(5, 3, 10, w.weight_state(0, 2400)), 20)

    def test_add_forecast_extra_one_and_rounded_capacity(self):
        self.assertTrue(w.can_add_weight(2393, 0, 1, 2400))
        self.assertFalse(w.can_add_weight(2394, 0, 1, 2400))
        self.assertFalse(w.can_add_weight(2399, 0, 1, 2400))
        self.assertTrue(w.can_add_weight(2390, 3900, 1, 2400))
        self.assertFalse(w.can_add_weight(2391, 3900, 1, 2400))
        # Count10 weighs39; count11 after merge weighs42, but forecast is39+3+1=43.
        self.assertEqual(w.stack_weight(3900, 11), 42)
        self.assertFalse(w.can_add_weight(39, 3900, 1, 43))
        self.assertTrue(w.can_add_weight(2400, 3900, 100, 0, rate=0))


if __name__ == '__main__':
    unittest.main()
