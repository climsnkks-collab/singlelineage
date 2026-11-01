"""Expanded enchant policy and inventory projections; no game/server/ports."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from . import inventory, world_enchant as e, world_enchant_inventory as projection
from .game_data import load_items


def item(uid, template, name=b'', count=1):
    return inventory.ItemInfo(tuple(sorted({
        1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 71,
        9: 0, 10: 0, 13: 0, 14: 0, 16: 0, 17: 0, 18: name,
        22: 0, 24: False, 25: 0, 26: False,
    }.items())))


class ExpandedEnchantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = e._policy()['equipment']
        cls.defs = load_items()
        cls.official = {r['official_id']: r for r in json.loads(
            (Path(__file__).parent / 'data/official/items.json').read_text(encoding='utf-8'))['items']}

    def proposal(self, row, grade, level=0, **overrides):
        return e.propose_enchant(e.EnchantScroll(25 if row['kind'] == 'weapon' else 26, grade),
                                 e.EnchantTarget(row['classic_id'], row['kind'], level, **overrides))

    def test_all_275_rows_keep_official_safety_and_identity_boundary(self):
        self.assertEqual(len(self.rows), 275)
        self.assertEqual(len({r['classic_id'] for r in self.rows}), 275)
        self.assertEqual(sum(r['safe_enchant'] is not None for r in self.rows), 203)
        self.assertEqual(sum(r['enchantable'] is False for r in self.rows), 72)
        for row in self.rows:
            with self.subTest(template=row['classic_id']):
                official = self.official[row['classic_id']]
                self.assertEqual(row['safe_enchant'], official['derived']['safe_enchant']['value'])
                self.assertEqual(row['enchantable'], official['derived']['enchantable']['value'])
                self.assertEqual(row['safety_source'], 'official')
                self.assertEqual(row['official_ref']['enchantDescription'],
                                 official['official']['enchantDescription'])
                self.assertEqual(row['normal_scroll_eligible'], row['enchantable'])
                if row['classic_id'] == 614:
                    self.assertIsNone(row['native_ref'])
                else:
                    self.assertIn('identity only', row['native_ref'])

    def test_203_numeric_targets_enter_policy_in_all_three_grades(self):
        for row in self.rows:
            if not row['enchantable']:
                continue
            for grade in (0, 1, 2):
                with self.subTest(template=row['classic_id'], grade=grade):
                    p = self.proposal(row, grade)
                    self.assertTrue(p.accepted)
                    self.assertEqual(p.reason, 'local_l1j_policy')
                    self.assertEqual(p.safe_enchant, self.defs[row['classic_id']].safe_enchant)
                    result = e.resolve_enchant(p, outcome_roll=1, blessing_roll=100)
                    self.assertEqual(result.status, 'success')
                    self.assertEqual(result.consume_scroll, 1)
                    if grade == 2:
                        self.assertEqual(result.level_after, -1)
                    if row['safe_enchant'] > 0:
                        self.assertEqual(p.success_rolls, 100)
                    elif grade != 2:
                        self.assertLess(p.success_rolls, 100)

    def test_72_official_denials_cannot_be_overridden_and_consume_nothing(self):
        accessories = [r for r in self.rows if r.get('slot') in ('ring', 'amulet', 'belt')]
        self.assertEqual(len(accessories), 56)
        for row in self.rows:
            if row['enchantable']:
                continue
            for grade in (0, 1, 2):
                for overrides in ({}, {'safe_enchant': 0, 'normal_scroll_eligible': True}):
                    with self.subTest(template=row['classic_id'], grade=grade, overrides=overrides):
                        p = self.proposal(row, grade, **overrides)
                        result = e.resolve_enchant(p, outcome_roll=100, blessing_roll=100)
                        self.assertFalse(p.accepted)
                        self.assertEqual(result.reason, 'target_cannot_be_enchanted')
                        self.assertEqual((result.consume_scroll, result.remove_target,
                                          result.level_after), (0, False, 0))

    def test_unknown_safety_sql_minus_one_and_policy_scroll_denial_are_distinct(self):
        policy = e._policy()
        cases = ((None, None, 'unresolved_target_safety'),
                 (-1, True, 'target_cannot_be_enchanted'),
                 (4, False, 'target_requires_special_scroll'))
        for safe, eligible, reason in cases:
            row = dict(classic_id=999999, kind='armor', safe_enchant=safe,
                       normal_scroll_eligible=eligible)
            with patch.object(e, '_policy', return_value={**policy, 'equipment': [row]}):
                for grade in (0, 1, 2):
                    p = self.proposal(row, grade, normal_scroll_eligible=True)
                    self.assertFalse(p.accepted)
                    self.assertEqual(p.reason, reason)
                    self.assertEqual(e.resolve_enchant(p, outcome_roll=1,
                                                       blessing_roll=1).consume_scroll, 0)

    def test_official_safety_wins_over_historical_l1j_values(self):
        by_id = {r['classic_id']: r for r in self.rows}
        # Classic Pan's Horn is unsafe from +1 despite the L1J +6 reference.
        horn = by_id[268]
        self.assertEqual((horn['safe_enchant'], horn['l1j_reference']['safe_enchant']), (0, 6))
        self.assertLess(self.proposal(horn, 1).success_rolls, 100)
        # L1J zero on the hood/forgotten armor does not override Classic denial.
        for template in (651, 654, 655, 656, 657):
            self.assertEqual(by_id[template]['l1j_reference']['safe_enchant'], 0)
            self.assertFalse(self.proposal(by_id[template], 1).accepted)
        self.assertEqual(by_id[671]['l1j_reference']['safe_enchant'], -1)
        self.assertFalse(self.proposal(by_id[671], 1).accepted)

    def test_added_equipment_success_failure_and_restore_use_existing_inventory_format(self):
        by_id = {r['classic_id']: r for r in self.rows}
        # Japanese sword, bone armor and an additional ordinary armor target.
        armor = next(r for r in self.rows[30:]
                     if r['kind'] == 'armor' and r['safe_enchant'] == 4)
        for row in (by_id[2], by_id[331], armor):
            definition = self.defs[row['classic_id']]
            scroll_template = 25 if row['kind'] == 'weapon' else 26
            for grade in (0, 1, 2):
                for destroyed in (False, True):
                    level = -7 if grade == 2 and destroyed else row['safe_enchant'] if destroyed else 0
                    p = self.proposal(row, grade, level)
                    result = e.resolve_enchant(p, outcome_roll=100 if destroyed else 1,
                                               blessing_roll=100)
                    self.assertEqual(result.status, 'destroyed' if destroyed else 'success')
                    items = (item(80, 7, count=100),
                             item(81, scroll_template, projection.scroll_name(scroll_template, grade), 2),
                             item(82, row['classic_id'], projection.enchanted_name(definition, level)))
                    mutation = projection.kit_mutation(items, 81, 82, result, self.defs)
                    restored = {r.identifier: r for r in inventory.validate_kit_frame(mutation.frame)}
                    self.assertEqual(dict(restored[81].raw_fields)[4], 1)
                    if destroyed:
                        self.assertNotIn(82, restored)
                        self.assertEqual(mutation.removed_uids, (82,))
                    else:
                        self.assertEqual(projection.enchant_level(restored[82], definition), result.level_after)
                        self.assertEqual(dict(restored[82].raw_fields)[7], 71)
                    self.assertEqual(dict(restored[80].raw_fields), dict(items[0].raw_fields))


if __name__ == '__main__':
    unittest.main()
