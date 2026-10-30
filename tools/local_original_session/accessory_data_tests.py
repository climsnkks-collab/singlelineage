"""Accessory catalog/slot contracts; file reads only, no client or socket."""
from collections import Counter
import json
import unittest

from tools.local_original_session import game_data as g


class AccessoryDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = g.load_items()
        cls.raw = json.loads((g.M1_DATA_DIR / 'items_ext/accessories.json').read_text(encoding='utf-8'))

    def test_all_official_accessories_activate_with_originals_preserved(self):
        rows = self.raw['items']
        self.assertEqual(len(rows), 56)
        self.assertEqual(Counter(row['slot']['value'] for row in rows),
                         {'ring': 17, 'amulet': 18, 'belt': 21})
        for row in rows:
            item = self.items[row['id']['value']]
            original = row['accessory_original']
            self.assertEqual(item.name_ko, original['official_original']['value']['name'])
            self.assertTrue(item.equippable)
            self.assertFalse(item.stackable)
            self.assertEqual(item.classes, frozenset(row['classes']['value']))
        self.assertEqual(sum(row['accessory_original']['client_id'] is not None for row in rows), 55)

    def test_original_ui_keys_and_two_ring_capacity(self):
        self.assertEqual(self.items[64].slot_keys, (13, 14))
        self.assertEqual(self.items[306].slot_keys, (11,))
        self.assertEqual(self.items[502].slot_keys, (12,))
        self.assertEqual((self.items[744].slot, self.items[744].slot_keys), ('belt', (12,)))
        self.assertEqual(self.items[103].slot_keys, (2,))
        self.assertEqual(self.items[14].slot_keys, ())
        starter = json.loads((g.M1_DATA_DIR / 'starter.json').read_text(encoding='utf-8'))
        # Existing startup validation admits two distinct ring positions, not a third.
        row = lambda iid: {'value': {'item': iid, 'count': 1, 'equipped': True},
                           'source': 'local_policy', 'ref': 'unit fixture'}
        starter['classes']['1'] = [row(64), row(65)]
        self.assertEqual(len(g._starter(starter, self.items).classes[1]), 2)
        starter['classes']['1'].append(row(496))
        with self.assertRaises(ValueError):
            g._starter(starter, self.items)

    def test_official_numeric_options_and_native_class_weight(self):
        self.assertEqual(dict(self.items[508].modifiers), {'str': 1, 'dex': -2})
        self.assertEqual(dict(self.items[497].modifiers), {'mr': 10})
        self.assertEqual(dict(self.items[504].modifiers), {'max_hp': 15, 'max_mp': 15})
        self.assertEqual(dict(self.items[3934].modifiers), {'weight_bonus': 500, 'resist_fire': 10})
        self.assertEqual((self.items[565].classes, self.items[565].sources['classes'].kind),
                         (frozenset({0, 1, 2}), 'client'))
        self.assertEqual((self.items[502].weight, self.items[502].sources['weight'].kind), (50000, 'client'))
        self.assertEqual(dict(self.items[815].modifiers), {})  # descriptive poison immunity remains unresolved
        with self.assertRaises(TypeError):
            self.items[508].modifiers['str'] = 99

    def test_official_only_template_and_graphic_uncertainty(self):
        item = self.items[614]
        original = next(row['accessory_original'] for row in self.raw['items']
                        if row['id']['value'] == 614)
        self.assertIsNone(original['client_id'])
        self.assertIsNone(original['client_raw'])
        self.assertEqual((item.ac, item.weight, item.icon), (-2, 1000, 20650))
        self.assertEqual(item.sources['id'].kind, 'local_policy')
        self.assertEqual(item.sources['icon'].kind, 'official')
        self.assertEqual(item.name_token, item.name_ko)
        gfx = json.loads((g.M1_DATA_DIR / 'item_gfx_ext/accessories.json').read_text(encoding='utf-8'))['items']
        self.assertEqual(set(gfx), {str(row['id']['value']) for row in self.raw['items']})
        self.assertEqual((gfx['614']['ground'], gfx['614']['source']), (22, 'local_policy'))

    def test_armor_numeric_options_and_class_conditions(self):
        self.assertEqual(dict(self.items[706].modifiers),
                         {'cha': 1, 'con': 1, 'dex': 1, 'int': 1, 'str': 1, 'wis': 1})
        self.assertEqual(dict(self.items[768].modifiers), {'max_hp': 20, 'max_mp': 10})
        self.assertEqual(dict(self.items[670].modifiers), {'hp_regen': 5, 'mp_regen': 3})
        self.assertEqual(dict(self.items[111].modifiers), {'mr': 10})
        self.assertEqual(dict(self.items[12350].modifiers), {'melee_hit': 1})
        self.assertEqual(dict(self.items[12351].modifiers), {'ranged_hit': 1})
        self.assertEqual(dict(self.items[105].modifiers), {})
        self.assertEqual(dict(self.items[105].class_modifiers[2]), {'hp_regen': 1})
        self.assertEqual(dict(self.items[114].class_modifiers[2]), {'mr': 5})
        self.assertEqual(dict(self.items[545].modifiers), {})  # damage reduction is not guessed
        self.assertEqual(self.items[706].sources['modifiers'].kind, 'official')
        with self.assertRaises(TypeError):
            self.items[105].class_modifiers[2]['hp_regen'] = 20

    def test_classic_set_definitions_attach_to_base_and_extended_rows(self):
        bonuses = {bonus.set_id: bonus for item in self.items.values()
                   for bonus in item.set_bonuses}
        self.assertEqual(len(bonuses), 14)
        orc = self.items[88].set_bonuses[0]  # base items.json member
        self.assertEqual((orc.members, orc.degree, dict(orc.modifiers)),
                         ((88, 101, 106, 115), 4, {'ac': -3}))
        self.assertEqual(orc, self.items[101].set_bonuses[0])
        self.assertEqual((self.items[88].ac, self.items[101].ac), (-1, -2))
        dwarf = self.items[89].set_bonuses[0]
        self.assertEqual(dict(dwarf.modifiers), {'ac': -1, 'max_hp': 5})
        self.assertEqual(dict(self.items[497].set_bonuses[0].modifiers), {'mr': 10})
        self.assertEqual(dict(self.items[727].set_bonuses[0].modifiers),
                         {'mp_regen': 12, 'ac': -2, 'max_mp': 100})
        for bonus in bonuses.values():
            self.assertEqual(bonus.degree, len(bonus.members))
            self.assertTrue(set(bonus.members) <= self.items.keys())
            self.assertEqual(bonus.sources['id'].kind, 'local_policy')
            self.assertTrue(all(bonus.sources[key].kind == 'official'
                                for key in ('members', 'degree', 'modifiers')))
        self.assertEqual((self.items[14].set_bonuses, dict(self.items[14].class_modifiers)),
                         ((), {}))
        with self.assertRaises(TypeError):
            orc.modifiers['ac'] = -100

    def test_standalone_item_row_optional_set_field(self):
        raw = g._read(g.M1_DATA_DIR, 'items.json')
        bonus = g._read(g.M1_DATA_DIR, 'equipment_sets.json')['sets'][0]
        member = bonus['members']['value'][0]
        row = next(row for row in raw['items'] if row['id']['value'] == member)
        row['set_bonuses'] = {'value': [bonus], 'source': 'local_policy',
                              'ref': 'explicit optional item-row field fixture'}
        item = g._items(raw)[member]
        self.assertEqual(item.set_bonuses[0], self.items[member].set_bonuses[0])
        self.assertEqual(item.sources['set_bonuses'].kind, 'local_policy')


if __name__ == '__main__':
    unittest.main()
