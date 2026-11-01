"""M1 data tables load and cross-reference each other; file reads only."""
import unittest
import random
from pathlib import Path
from unittest.mock import patch

from tools.local_original_session import game_data as g


class GameDataTests(unittest.TestCase):
    def test_m1_tables_load_and_link(self):
        data = g.load_m1()
        self.assertTrue({0, 245, 1, 8} <= set(data.monsters))
        # FILL_MONSTERS registers catalog-only species (fixtures, other maps)
        # that have no M1 spawn row; every M1 spawn still names a monster.
        self.assertLessEqual({s.template_id for s in data.spawns}, set(data.monsters))
        self.assertTrue(set(data.drops) <= set(data.monsters))
        self.assertTrue({u.template_id for u in data.drops_unresolved} <= set(data.monsters))
        for monster in data.monsters.values():
            speed = data.action_speed.monsters.get(monster.sprite_id)
            if speed is None:
                # FILL_MONSTERS catalog-only species carry their own client
                # list.spr interval sources instead of an action_speed row.
                self.assertIn(monster.sources['move_interval_ms'].kind, ('client', 'local_policy'))
                # move 0 = stationary species (e.g. sea anemone 535/536).
                self.assertTrue(monster.move_interval_ms >= 0 and monster.attack_interval_ms > 0)
            else:
                self.assertEqual((monster.move_interval_ms, monster.attack_interval_ms),
                                 (speed.walk_ms, speed.attack_ms))
            self.assertTrue(all(s.kind in g.SOURCE_KINDS for s in monster.sources.values()))
            # The original eleven M1 rows promise Adena. Expanded animals
            # keep their separately sourced drop lists, including empty lists.
            drops = data.drops[monster.template_id]
            if monster.template_id in (0, 245, 1, 8, 249, 4, 2, 27, 29, 5, 17):
                self.assertTrue(any(d.item_id == 7 for d in drops))
        for spawn in data.spawns:
            self.assertEqual(spawn.map_id, data.town.map_id)
            self.assertFalse(spawn.rect.contains(data.town.respawn_x, data.town.respawn_y))
        self.assertTrue(data.town.bounds.contains(data.town.respawn_x, data.town.respawn_y))
        self.assertEqual(len(data.pc_exp), 99)
        self.assertEqual((data.exp_for_level(30), data.exp_for_level(31),
                          data.exp_for_level(50), data.exp_for_level(99)),
                         (810016, 923537, 55810962, 1823000470))
        self.assertEqual(data.level_for_exp(data.pc_exp[-1] + 100), 99)
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
        self.assertEqual({key for i in data.items.values() if i.kind == 'armor'
                          for key in i.slot_keys}, {1, 2, 3, 4, 6, 7, 8, 11, 12, 13, 14})
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
        self.assertEqual(sum(data.items[e.template_id].ac for e in kit[:8]), -13)
        self.assertEqual({e.template_id: e.count for e in kit if not e.equipped},
                         {89: 1, 104: 1, 128: 1, 129: 1, 14: 100, 17: 20, 296: 20, 7: 1000,
                          41: 1, 6: 1, 4: 1, 12: 1, 11: 1, 230: 1, 29: 200,
                          299: 5, 162: 10, 23: 10, 25: 5, 26: 5,
                          102: 1, 90: 1, 106: 1, 120: 1, 113: 1, 28: 10})
        self.assertEqual([(e.template_id, e.grade, e.count) for e in kit if e.template_id in (25, 26)],
                         [(25, 1, 5), (25, 0, 5), (25, 2, 5),
                          (26, 1, 5), (26, 0, 5), (26, 2, 5)])
        self.assertEqual(data.starter.entries(0, 'test_knight'), data.starter.classes[0])  # other class: class table
        haste, brave = data.items[17].buff, data.items[296].buff
        self.assertEqual((haste.kind, haste.add_s, haste.cap_s, haste.rate), ('haste', 300, 1800, 0.745))
        self.assertEqual((brave.kind, brave.classes), ('brave', frozenset({1})))

    def test_shared_mage_starter_supplies_match_supported_spell_books(self):
        from tools.local_original_session.world_magic import PlayerMagic, load_catalog
        data = g.load_m1()
        magic = PlayerMagic(load_catalog())
        kit = data.starter.entries(3, 'test_knight')
        self.assertEqual(kit, data.starter.entries(3))
        supplies = {entry.template_id: entry.count for entry in kit if not entry.equipped}
        books = {magic.spells[key].book for key in range(16)}
        self.assertEqual({book: supplies.get(book) for book in books},
                         {book: 1 for book in books})
        self.assertEqual(len(books), 16)
        self.assertEqual((supplies[14], supplies[17]), (100, 50))
        self.assertEqual(len([entry for entry in kit if entry.template_id == 17]), 1)
        self.assertEqual((supplies[492], supplies[12273]), (20, 1))
        self.assertEqual((data.items[492].icon, data.items[492].weight), (75, 7813))
        self.assertEqual((data.items[12273].icon, data.items[12273].weight), (20256, 1000))

    def test_weapon_stance_items_and_kit_keep_existing_uid_order(self):
        data = g.load_m1()
        kit = data.starter.entries(1, 'test_knight')
        self.assertEqual([e.template_id for e in kit[:12]],
                         [3, 117, 89, 98, 104, 109, 128, 129, 14, 17, 296, 7])
        self.assertEqual([e.template_id for e in kit if e.equipped], [3, 117, 98, 109])
        # Classic IDs and native CommonItemInfo f5, never the L1J inventory icon.
        expected = {41: ('dagger', 35), 6: ('twohand', 4), 4: ('blunt', 1),
                    12: ('spear', 101), 11: ('bow', 20), 230: ('staff', 291)}
        self.assertEqual([e.template_id for e in kit[12:]],
                         [*expected, 29, 299, 162, 23, 25, 25, 25, 26, 26, 26,
                          102, 90, 106, 120, 113, 28])
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

    def test_official_stats_keep_client_weight_precision_and_l1j_gaps(self):
        data = g.load_m1()
        sword = data.items[6]
        self.assertEqual((sword.dmg_small, sword.dmg_large), (14, 16))
        self.assertEqual(sword.sources['weapon'].kind, 'official')
        self.assertEqual(data.items[1].classes, frozenset({0, 1, 2, 3}))
        self.assertEqual(data.items[296].classes, frozenset({1}))
        self.assertEqual(data.items[103].safe_enchant, 4)
        self.assertEqual(data.items[103].sources['safe_enchant'].kind, 'official')
        self.assertEqual(data.items[98].ac, -4)
        self.assertEqual(data.items[98].sources['ac'].kind, 'official')
        self.assertEqual((data.items[29].dmg_small, data.items[29].dmg_large), (6, 5))
        self.assertEqual({n: data.items[n].weight for n in (263, 14, 17, 296, 29, 23)},
                         {263: 25000, 14: 5859, 17: 4688, 296: 9375, 29: 47, 23: 625})
        self.assertEqual(data.items[14].heal_hp_range, (6, 27))
        for item in data.items.values():
            if item.template_id == 614:
                # Official-only LOCAL template: no native weight/ID correspondence.
                self.assertEqual(item.sources['weight'].kind, 'local_policy')
                self.assertEqual((item.weight, item.sources['id'].kind), (1000, 'local_policy'))
                self.assertIn('official', item.sources['weight'].ref)
            else:
                self.assertEqual(item.sources['weight'].kind, 'client')
        spawned = {s.template_id for s in data.spawns}
        for monster in data.monsters.values():
            self.assertEqual(monster.sources['level'].kind, 'official')
            # Newly added Black Knight/Kurtz rows and the FILL_MONSTERS
            # catalog-only (unspawned) species explicitly select raw L1J values
            # as LOCAL policy; all existing spawned L1J expectations stay.
            backend_source = ('local_policy' if monster.template_id in (15, 16)
                              or monster.template_id not in spawned else 'l1j')
            self.assertEqual(monster.sources['hp'].kind, backend_source)
            self.assertEqual(monster.sources['kill_exp'].kind, backend_source)
        for drops in data.drops.values():
            for drop in drops:
                self.assertIn(drop.sources['roll'].kind, ('l1j', 'local_policy'))

    def test_official_heal_ranges_drive_rng_and_preserve_status(self):
        from tools.local_original_session import world_combat as wc
        from tools.local_original_session.world_item_effects import WorldItemEffects
        from tools.local_world_protocol import model as protocol

        combat = wc.WorldCombat(g.load_m1(), random.Random(3))
        fields = {1: 65537, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
                  10: 1, 11: 200, 12: 3, 13: 10, 14: -10, 15: 1793000000,
                  16: 200, 17: 7, 18: -123, 20: 9}
        pc = combat.bind_pc(65537, wc.PcProfile(1, 1, 0, 13, 13), fields)
        rng = random.Random(23)
        effects = WorldItemEffects(combat, rng=rng)
        for template, endpoints in ((14, (6, 27)), (15, (26, 68)), (130, (44, 107))):
            self.assertEqual(effects.definitions[template].heal_hp_range, endpoints)
            for amount in endpoints:
                pc.hp = 1
                with patch.object(rng, 'randint', return_value=amount) as roll, \
                        patch.object(combat, 'heal', side_effect=AssertionError('Gaussian path')):
                    result = effects.use(65537, template, 100.0)
                roll.assert_called_once_with(*endpoints)
                self.assertEqual((result.healed_hp, pc.hp, result.consume_count),
                                 (amount, 1 + amount, 1))
                # Leading 4ED8 use effect (S_SkillSound), then the status frame.
                effect, frame = result.frames
                self.assertEqual(effect, effects.use_effect_frame(65537, template, result))
                status = protocol.decode_payload(0x4E38, frame[4:-2])
                self.assertEqual((status[10], status[12], status[18]), (1 + amount, 3, -123))
        expected_rng = random.Random(23)
        amounts = []
        for _ in range(40):
            pc.hp = 1
            result = effects.use(65537, 14, 100.0)
            self.assertEqual(result.healed_hp, expected_rng.randint(6, 27))
            amounts.append(result.healed_hp)
        self.assertGreater(len(set(amounts)), 1)
        pc.hp = 199
        self.assertEqual(effects.use(65537, 130, 100.0).healed_hp, 1)
        full = effects.use(65537, 130, 100.0)
        self.assertEqual((full.outcome, full.healed_hp, full.consume_count), ('no_effect', 0, 1))
        pc.hp, pc.dead = 0, True
        with patch.object(rng, 'randint', side_effect=AssertionError('dead PC rolled')):
            dead = effects.use(65537, 14, 100.0)
        self.assertEqual((dead.outcome, dead.consume_count, pc.hp), ('refused', 0, 0))


if __name__ == '__main__':
    unittest.main()
