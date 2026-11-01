"""Focused development arithmetic checks; not game/packet/runtime PASS.

Run from project root: python -X utf8 -B -m tools.local_original_session.world_stats_tests
"""
from dataclasses import replace
import unittest

from tools.local_original_session.game_data import load_items
from tools.local_original_session import world_stats as s


class StatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load_items()

    def setUp(self):
        self.base = s.CharacterStats(20, 1, s.Attributes(18, 12, 16, 10, 12, 8))

    def test_reference_unarmed_numbers(self):
        value = s.calculate_stats(self.base)
        self.assertEqual((value.ac, value.mr, value.max_weight), (8, 20, 2700))
        self.assertEqual((value.melee_hit_bonus, value.melee_hit, value.ranged_hit), (10, 30, 30))
        self.assertEqual((value.melee_damage_bonus, value.ranged_damage_bonus), (5, 0))
        self.assertEqual((value.hp_regen_min, value.hp_regen_max, value.mp_regen), (7, 10, 13))

    def test_equipment_enchant_and_unequip_recompute(self):
        weapon = s.EquippedItem(self.items[1], enchant=6)
        armor = s.EquippedItem(self.items[102], enchant=4)
        value = s.calculate_stats(self.base, (weapon, armor))
        # Actual mapped Athame hit2; leather armor AC-2. No guessed native fields.
        self.assertEqual((value.ac, value.melee_hit, value.melee_damage_bonus), (2, 35, 11))
        negative = s.calculate_stats(self.base, (replace(weapon, enchant=-3),))
        self.assertEqual((negative.melee_hit, negative.melee_damage_bonus), (31, 2))
        self.assertEqual(s.calculate_stats(self.base), s.calculate_stats(self.base, ()))
        self.assertEqual(s.calculate_stats(self.base, (weapon,)).ac, 8)
        self.assertEqual(weapon.enchant, 6)

    def test_active_buff_then_expiry_and_base_dex(self):
        worn = (s.EquippedItem(self.items[1], enchant=6), s.EquippedItem(self.items[102], enchant=4))
        buff = s.StatModifiers(strength=2, dexterity=6, con=2, wis=8, ac=-3, mr=5,
                               melee_hit=1, melee_damage=2, hpr=2, mpr=3, hp_bonus=15, mp_bonus=5)
        before = s.calculate_stats(self.base, worn)
        value = s.calculate_stats(self.base, worn, buffs=(buff,))
        self.assertEqual(value.attributes, s.Attributes(20, 18, 18, 18, 12, 8))
        self.assertEqual((value.ac, value.mr, value.max_weight), (-1, 35, 3000))
        self.assertEqual((value.melee_hit, value.melee_damage_bonus), (40, 14))
        self.assertEqual((value.hp_regen_min, value.hp_regen_max, value.mp_regen), (26, 31, 23))
        # Effective DEX18 does not change level20/baseDEX12 AC8.
        dex_only = s.calculate_stats(self.base, buffs=(s.StatModifiers(dexterity=6),))
        self.assertEqual(dex_only.ac, before.ac + 6)
        self.assertEqual(s.calculate_stats(self.base, worn, buffs=()), before)

    def test_armor_explicit_accessory_and_magic_policy(self):
        row = s.EquippedItem(self.items[102], enchant=6,
                             armor_enchant_ac=False, modifiers=s.StatModifiers(ac=-2, mr=9))
        result = s.calculate_stats(self.base, (row,))
        self.assertEqual((result.ac, result.mr), (4, 29))
        # MR enchant requires actual mapping/evidence; enchant alone adds no MR.
        self.assertEqual(s.calculate_stats(self.base, (replace(row, enchant=12),)).mr, 29)

    def test_base_ac_dex_and_level_boundaries(self):
        for dex, divisor in ((9, 8), (10, 7), (12, 7), (13, 6), (15, 6),
                             (16, 5), (17, 5), (18, 4), (127, 4)):
            with self.subTest(dex=dex):
                self.assertEqual(s.base_ac(divisor - 1, dex), 10)
                self.assertEqual(s.base_ac(divisor, dex), 9)
                self.assertEqual(s.base_ac(56, dex), 10 - 56 // divisor)

    def test_wis_mr_steps_and_effective_wis(self):
        expected = {14: 0, 15: 3, 16: 3, 17: 6, 18: 10, 19: 15,
                    20: 21, 21: 28, 22: 37, 23: 47, 24: 50, 127: 50}
        for wis, mr in expected.items():
            with self.subTest(wis=wis):
                self.assertEqual(s.wisdom_mr(wis), mr)
        for cls, mr in enumerate((10, 10, 25, 15, 10, 18, 20)):
            self.assertEqual(s.calculate_stats(replace(self.base, level=1, character_class=cls)).mr, mr)
        self.assertEqual(s.calculate_stats(self.base, buffs=(s.StatModifiers(mr=-99),)).mr, 0)

    def test_class_hit_damage_and_level_thresholds(self):
        for cls, hit20, melee20, bow20 in ((0, 28, 3, 0), (1, 30, 5, 0),
                                          (2, 28, 3, 2), (3, 24, 3, 0),
                                          (4, 30, 5, 0), (5, 30, 5, 0), (6, 28, 3, 0)):
            value = s.calculate_stats(replace(self.base, character_class=cls))
            self.assertEqual((value.melee_hit, value.melee_damage_bonus, value.ranged_damage_bonus),
                             (hit20, melee20, bow20))
        royal = replace(self.base, character_class=0, royal_level_damage=True)
        self.assertEqual(s.calculate_stats(royal).melee_damage_bonus, 5)
        nine = s.calculate_stats(replace(self.base, level=9))
        ten = s.calculate_stats(replace(self.base, level=10))
        self.assertEqual((nine.melee_damage_bonus, ten.melee_damage_bonus), (3, 4))

    def test_stat_damage_table_thresholds_and_clamps(self):
        for stat, dmg in ((1, -5), (18, 3), (22, 5), (23, 6), (28, 7),
                          (29, 8), (32, 9), (33, 10), (34, 11), (35, 12), (39, 13), (127, 35)):
            self.assertEqual(s.strength_damage(stat), dmg)
        for stat, dmg in ((14, 0), (15, 1), (18, 4), (21, 5), (24, 6), (35, 9), (36, 10), (127, 32)):
            self.assertEqual(s.dexterity_damage(stat), dmg)
        value = s.calculate_stats(self.base, buffs=(s.StatModifiers(strength=500, dexterity=-500, ac=-500),))
        self.assertEqual((value.attributes.strength, value.attributes.dexterity, value.ac), (127, 1, -128))
        self.assertEqual(s.calculate_stats(self.base, buffs=(s.StatModifiers(ac=500),)).ac, 127)

    def test_explicit_original_and_capacity_reuse(self):
        original = s.StatModifiers(melee_hit=2, ranged_damage=3, ac=-1, mr=2,
                                   hp_bonus=2, mp_bonus=1)
        value = s.calculate_stats(self.base, original=original,
                                  weight=s.WeightOptions(armor_percent=10, original_str_points=1,
                                                         original_con_points=2, decrease_weight=True, rate=2))
        self.assertEqual(value.melee_hit, 32)
        self.assertEqual(value.ranged_damage_bonus, 3)
        self.assertAlmostEqual(value.max_weight, 6948)
        self.assertEqual((value.hp_regen_min, value.hp_regen_max, value.mp_regen), (9, 12, 14))

    def test_regen_random_bounds_hunger_berserk_and_weight(self):
        for level, con, bounds in ((11, 14, (5, 5)), (12, 14, (5, 6)),
                                   (12, 25, (16, 28)), (12, 26, (17, 30)), (12, 9, (2, 2))):
            value = s.calculate_stats(replace(self.base, level=level, attributes=replace(self.base.attributes, con=con)))
            self.assertEqual((value.hp_regen_min, value.hp_regen_max), bounds)
        extra = s.StatModifiers(hpr=3, mpr=4, hp_bonus=15, mp_bonus=5)
        over = s.WeightOptions(carried_weight=1350)  # exactly gauge120 of capacity2700
        value = s.calculate_stats(self.base, buffs=(extra,), weight=over)
        self.assertEqual((value.hp_regen_min, value.hp_regen_max, value.mp_regen), (6, 6, 12))
        self.assertEqual(value.weight.gauge, 120)
        food = s.calculate_stats(self.base, buffs=(extra,), regen=s.RegenOptions(food=2))
        self.assertEqual((food.hp_regen_min, food.hp_regen_max, food.mp_regen), (6, 6, 12))
        berserk = s.calculate_stats(self.base, buffs=(extra,), regen=s.RegenOptions(berserk=True))
        self.assertEqual((berserk.hp_regen_min, berserk.mp_regen), (6, 22))
        negative = s.calculate_stats(self.base, buffs=(s.StatModifiers(hpr=-3, mpr=-4),), weight=over)
        self.assertEqual((negative.hp_regen_min, negative.mp_regen), (3, 8))
        immune = s.calculate_stats(self.base, weight=replace(over, exotic_vitalize=True))
        self.assertEqual((immune.hp_regen_min, immune.hp_regen_max, immune.mp_regen), (7, 10, 13))

    def test_regen_skill_adds_and_no_implicit_speed_buff(self):
        value = s.calculate_stats(self.base, regen=s.RegenOptions(blue_potion=True, meditation=True,
                                                                 concentration=True, natures_touch=True))
        self.assertEqual((value.hp_regen_min, value.hp_regen_max, value.mp_regen), (22, 25, 26))
        # WIS10 blue potion uses WIS11 for the bonus only; effective stats stay10.
        self.assertEqual(value.attributes.wis, 10)

    def test_full_self_info_field_contract_preserves_vitals_unknown_exp(self):
        # Source profile's field names/order, plus observed full-status EXP.
        seed = {1: 65537, 2: 1, 3: 919, 4: 13, 5: 10, 6: 10, 7: 10, 8: 10, 9: 13,
                10: 0, 11: 200, 12: 7, 13: 40, 14: -10, 15: 1700000000,
                16: 0, 17: 34, 18: 0, 20: 123, 26: 42.5, 99: b'unknown'}
        before = dict(seed)
        value = s.calculate_stats(self.base)
        result = s.self_info_fields(seed, value)
        self.assertEqual({f: result[f] for f in (2, 4, 5, 6, 7, 8, 9, 14)},
                         {2: 20, 4: 18, 5: 12, 6: 8, 7: 10, 8: 16, 9: 12, 14: -8})
        self.assertEqual(result[17], 0)
        self.assertEqual({k: v for k, v in result.items() if k not in (2, 4, 5, 6, 7, 8, 9, 14, 17)},
                         {k: v for k, v in seed.items() if k not in (2, 4, 5, 6, 7, 8, 9, 14, 17)})
        self.assertEqual(seed, before)
        result[10] = 199
        self.assertEqual(seed[10], 0)
        naked = s.calculate_stats(replace(self.base, level=1))
        self.assertEqual(s.self_info_fields(seed, naked)[14], -10)
        improved = s.calculate_stats(self.base, buffs=(s.StatModifiers(ac=-20),))
        self.assertEqual(s.self_info_fields(seed, improved)[14], 12)

    def test_weight_hud_uses_percent_before_gauge240_rounding_and_refreshes_capacity(self):
        # 13/2700 gives gauge240=1, but native percent must floor to0.
        value = s.calculate_stats(self.base, weight=s.WeightOptions(carried_weight=13))
        self.assertEqual((value.carried_weight, value.weight.gauge), (13, 1))
        self.assertEqual(s.self_info_fields({17: 73}, value)[17], 0)
        # Preserve the native stage boundaries; the client owns warning colors.
        for percent in (32, 33, 49, 50, 66, 67, 82, 83, 99, 100, 101):
            value = s.calculate_stats(self.base,
                weight=s.WeightOptions(carried_weight=27 * percent))
            self.assertEqual(s.self_info_fields({}, value)[17], min(percent, 100))
        carried = s.WeightOptions(carried_weight=1350)
        value = s.calculate_stats(self.base, weight=carried)
        self.assertEqual(s.self_info_fields({}, value)[17], 50)
        relieved = s.calculate_stats(self.base, buffs=(s.StatModifiers(weight_bonus=2700),), weight=carried)
        self.assertEqual(s.self_info_fields({}, relieved)[17], 25)
        disabled = s.calculate_stats(self.base, weight=s.WeightOptions(rate=0, carried_weight=1350))
        self.assertEqual(s.self_info_fields({}, disabled)[17], 0)

    def test_invalid_inputs_and_non_equipment(self):
        for attrs in ((0, 12, 16, 10, 12, 8), (18, True, 16, 10, 12, 8)):
            with self.assertRaises(ValueError):
                s.Attributes(*attrs)
        with self.assertRaises(ValueError):
            s.calculate_stats(replace(self.base, level=0))
        with self.assertRaises(ValueError):
            s.EquippedItem(self.items[7])
        with self.assertRaises(ValueError):
            s.calculate_stats(self.base, (s.EquippedItem(self.items[1]), s.EquippedItem(self.items[40])))


if __name__ == '__main__':
    unittest.main(verbosity=2)
