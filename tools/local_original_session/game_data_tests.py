"""M1 data tables load and cross-reference each other; file reads only."""
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.local_original_session import game_data as g


class GameDataTests(unittest.TestCase):
    def test_m1_tables_load_and_link(self):
        data = g.load_m1()
        self.assertEqual(set(data.monsters), {0, 245, 1, 8})
        self.assertEqual({s.template_id for s in data.spawns}, set(data.monsters))
        self.assertTrue(set(data.drops) <= set(data.monsters))
        self.assertTrue({u.template_id for u in data.drops_unresolved} <= set(data.monsters))
        for monster in data.monsters.values():
            speed = data.action_speed.monsters[monster.sprite_id]
            self.assertEqual((monster.move_interval_ms, monster.attack_interval_ms),
                             (speed.walk_ms, speed.attack_ms))
            self.assertTrue(all(s.kind in g.SOURCE_KINDS for s in monster.sources.values()))
            self.assertTrue(any(d.item_id == 7 for d in data.drops[monster.template_id]))
        for spawn in data.spawns:
            self.assertEqual(spawn.map_id, data.town.map_id)
            self.assertFalse(spawn.rect.contains(data.town.respawn_x, data.town.respawn_y))
        self.assertTrue(data.town.bounds.contains(data.town.respawn_x, data.town.respawn_y))
        self.assertEqual(len(data.pc_exp), 30)
        self.assertEqual(data.level_for_exp(data.exp_for_level(10)), 10)
        self.assertEqual(set(data.level_growth), {0, 1, 2, 3})
        self.assertEqual((data.level_growth[1].hp_base, data.level_growth[1].hp_cap,
                          data.level_growth[3].mp_cap), (17, 2000, 1200))

    def test_m1_items_and_class_starter(self):
        data = g.load_m1()
        dagger, jacket, potion, adena = (data.items[n] for n in (41, 103, 14, 7))
        self.assertEqual((dagger.kind, dagger.slot_key, dagger.dmg_small, dagger.dmg_large, dagger.hit),
                         ('weapon', 9, 4, 2, 2))
        self.assertEqual((jacket.kind, jacket.slot_key, jacket.ac), ('armor', 2, -1))
        self.assertEqual((potion.kind, potion.heal_hp, potion.stackable, potion.slot_key), ('potion', 15, True, None))
        self.assertEqual((adena.kind, adena.stackable), ('currency', True))
        self.assertEqual({i.slot_key for i in data.items.values() if i.kind == 'armor'}, {1, 2, 3, 4, 6, 7, 8})
        for item in data.items.values():
            self.assertTrue(all(s.kind in g.SOURCE_KINDS for s in item.sources.values()))
        royal = [(e.template_id, e.count, e.equipped) for e in data.starter.classes[0]]
        self.assertEqual(royal, [(41, 1, True), (103, 1, True), (14, 20, False), (7, 100, False)])
        self.assertEqual(set(data.starter.classes), {0, 1, 2, 3})
        self.assertEqual(data.starter.uid_base, 65537)

    def test_test_knight_kit_and_speed_potions(self):
        data = g.load_m1()
        kit = data.starter.entries(1, 'test_knight')
        worn = [data.items[e.template_id] for e in kit if e.equipped]
        self.assertEqual(sorted(i.slot_key for i in worn), [2, 4, 8, 9])  # first grant: 4 x 097A fit the 10s wait
        self.assertEqual(sum(data.items[e.template_id].ac for e in kit), -13)
        self.assertEqual({e.template_id: e.count for e in kit if not e.equipped},
                         {89: 1, 104: 1, 128: 1, 129: 1, 14: 100, 17: 20, 296: 20, 7: 1000,
                          41: 1, 6: 1, 4: 1, 12: 1, 11: 1, 230: 1, 29: 200,
                          299: 5, 162: 10, 23: 10})
        self.assertEqual(data.starter.entries(0, 'test_knight'), data.starter.classes[0])  # other class: class table
        haste, brave = data.items[17].buff, data.items[296].buff
        self.assertEqual((haste.kind, haste.add_s, haste.cap_s, haste.rate), ('haste', 300, 1800, 0.745))
        self.assertEqual((brave.kind, brave.classes), ('brave', frozenset({1})))

    def test_weapon_stance_items_and_kit_keep_existing_uid_order(self):
        data = g.load_m1()
        kit = data.starter.entries(1, 'test_knight')
        self.assertEqual([e.template_id for e in kit[:12]],
                         [3, 117, 89, 98, 104, 109, 128, 129, 14, 17, 296, 7])
        self.assertEqual([e.template_id for e in kit if e.equipped], [3, 117, 98, 109])
        # Classic IDs and native CommonItemInfo f5, never the L1J inventory icon.
        expected = {41: ('dagger', 35), 6: ('twohand', 4), 4: ('blunt', 1),
                    12: ('spear', 101), 11: ('bow', 20), 230: ('staff', 291)}
        self.assertEqual([e.template_id for e in kit[12:]], [*expected, 29, 299, 162, 23])
        for entry in kit[12:18]:
            self.assertEqual((entry.count, entry.equipped), (1, False))
        for template, values in expected.items():
            item = data.items[template]
            self.assertEqual((item.weapon_type, item.icon), values)
            self.assertTrue(item.equippable)
            self.assertIn(1, item.classes)
            self.assertEqual(item.sources['weapon_type'].kind, 'l1j')
        self.assertEqual(data.items[1].weapon_type, 'blunt')  # Athame follows cited type, not its shape.
        arrow = data.items[29]
        self.assertEqual((arrow.kind, arrow.icon, arrow.weapon_type, arrow.slot_key), ('ammo', 7, None, None))
        self.assertFalse(arrow.equippable)
        for item in data.items.values():
            self.assertEqual(item.weapon_type is not None, item.kind == 'weapon')

    def test_stance_table_is_editable_and_immutable_after_loading(self):
        expected = {'bow': 40, 'sword': 30, 'axe': 35, 'blunt': 35, 'spear': 45,
                    'staff': 50, 'dagger': 55, 'twohand': 60, 'unarmed': 0}
        self.assertEqual(g.load_stances(), expected)
        with self.assertRaises(TypeError):
            g.load_stances()['bow'] = 99
        # A caller-supplied directory is read afresh; tuning requires no code edit.
        raw = g._read(g.M1_DATA_DIR, 'stance.json')
        raw['stances']['sword']['value'] = 32
        with patch.object(g, '_read', return_value=raw) as read:
            self.assertEqual(g.load_stances(Path('stance-fixture'))['sword'], 32)
            read.assert_called_once_with(Path('stance-fixture'), 'stance.json')
        raw['stances']['sword']['value'] = True
        with patch.object(g, '_read', return_value=raw), self.assertRaisesRegex(ValueError, 'stance.sword'):
            g.load_stances()


if __name__ == '__main__':
    unittest.main()
