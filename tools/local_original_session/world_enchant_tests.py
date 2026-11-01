"""Focused policy tests; no live game/server, ports or inventory writes."""
from dataclasses import FrozenInstanceError
from fractions import Fraction
import unittest

from .world_enchant import (
    EnchantScroll, EnchantTarget, armor_enchant_ac_bonus, propose_enchant,
    resolve_enchant, weapon_enchant_bonus,
)


class EnchantPolicyTests(unittest.TestCase):
    def proposal(self, kind='weapon', level=6, safe=6, grade=1):
        return propose_enchant(EnchantScroll(25 if kind == 'weapon' else 26, grade),
                               EnchantTarget(999999, kind, level, safe,
                                             normal_scroll_eligible=True))

    def resolve(self, proposal, roll=1, blessing=1):
        return resolve_enchant(proposal, outcome_roll=roll, blessing_roll=blessing)

    def test_weapon_strict_threshold_all_100_rolls(self):
        p = self.proposal()
        self.assertEqual(p.success_probability, Fraction(33, 100))
        self.assertEqual(p.destroyed_probability, Fraction(67, 100))
        self.assertEqual(self.resolve(p, 33).status, 'success')
        self.assertEqual(self.resolve(p, 34).status, 'destroyed')
        results = [self.resolve(p, roll) for roll in range(1, 101)]
        self.assertEqual(sum(r.status == 'success' for r in results), 33)
        self.assertTrue(all(r.consume_scroll == 1 for r in results))
        failed = results[-1]
        self.assertTrue(failed.remove_target)
        self.assertIsNone(failed.level_after)
        self.assertIsNone(failed.level_delta)

    def test_weapon_high_level_unchanged(self):
        p = self.proposal(level=9)
        self.assertEqual((p.success_rolls, p.unchanged_rolls, p.destroyed_rolls),
                         (16, 17, 67))
        self.assertEqual(self.resolve(p, 16).status, 'success')
        self.assertEqual(self.resolve(p, 17).status, 'unchanged')
        unchanged = self.resolve(p, 33)
        self.assertEqual((unchanged.status, unchanged.level_after,
                          unchanged.level_delta, unchanged.consume_scroll,
                          unchanged.remove_target), ('unchanged', 9, 0, 1, False))
        self.assertEqual(self.resolve(p, 34).status, 'destroyed')

    def test_armor_exact_probabilities_and_zero_safety(self):
        for level, safe, expected in ((4, 4, (25, 0, 75)),
                                      (5, 4, (20, 0, 80)),
                                      (9, 4, (5, 6, 89)),
                                      (0, 0, (50, 0, 50)),
                                      (1, 0, (33, 0, 67)),
                                      (9, 0, (4, 5, 91))):
            with self.subTest(level=level, safe=safe):
                p = self.proposal('armor', level, safe)
                self.assertEqual((p.success_rolls, p.unchanged_rolls,
                                  p.destroyed_rolls), expected)
                self.assertEqual(self.resolve(p, expected[0]).status, 'success')
                self.assertNotEqual(self.resolve(p, expected[0] + 1).status, 'success')

    def test_blessed_delta_exact_roll_boundaries_and_frequencies(self):
        for level, expected in ((2, {1: 32, 2: 44, 3: 24}),
                                (3, {1: 51, 2: 49}),
                                (5, {1: 51, 2: 49}), (6, {1: 100})):
            with self.subTest(level=level):
                p = self.proposal(level=level, grade=0)
                counts = {}
                for roll in range(1, 101):
                    delta = self.resolve(p, blessing=roll).level_delta
                    counts[delta] = counts.get(delta, 0) + 1
                self.assertEqual(counts, expected)
                self.assertEqual(sum(prob for _, prob in p.delta_probabilities),
                                 p.success_probability)
        p = self.proposal(level=2, grade=0)
        for roll, delta in ((32, 1), (33, 2), (76, 2), (77, 3)):
            self.assertEqual(self.resolve(p, blessing=roll).level_delta, delta)
        p = self.proposal(level=3, grade=0)
        self.assertEqual(self.resolve(p, blessing=49).level_delta, 2)
        self.assertEqual(self.resolve(p, blessing=50).level_delta, 1)

    def test_safe_checks_starting_level_not_resulting_level(self):
        # Blessed jump beyond safe remains guaranteed if starting below safe.
        p = self.proposal(level=5, safe=6, grade=0)
        result = self.resolve(p, roll=100, blessing=1)
        self.assertEqual((p.success_rolls, result.level_after), (100, 7))
        p = self.proposal('armor', level=3, safe=4, grade=0)
        self.assertEqual(self.resolve(p, 100, 1).level_after, 5)
        self.assertEqual(self.proposal('armor', 0, 0).success_rolls, 50)

    def test_cursed_decrements_and_destroys_at_minus_seven(self):
        for kind in ('weapon', 'armor'):
            for level in (-6, 0, 12):
                p = self.proposal(kind, level, 0, 2)
                r = self.resolve(p, 100, 100)
                self.assertEqual((r.status, r.level_delta, r.level_after,
                                  r.consume_scroll), ('success', -1, level - 1, 1))
            for level in (-7, -8):
                r = self.resolve(self.proposal(kind, level, 0, 2))
                self.assertEqual((r.status, r.consume_scroll, r.remove_target),
                                 ('destroyed', 1, True))

    def test_rejection_never_consumes_scroll_or_target(self):
        cases = [
            (EnchantScroll(25, None), EnchantTarget(1, 'weapon', 0)),
            (EnchantScroll(25, 3), EnchantTarget(1, 'weapon', 0)),
            (EnchantScroll(140087, 0), EnchantTarget(1, 'weapon', 0)),
            (EnchantScroll(25, 1), EnchantTarget(103, 'armor', 0)),
            (EnchantScroll(25, 1), EnchantTarget(103, 'weapon', 0)),
            (EnchantScroll(25, 1), EnchantTarget(1, 'weapon', 0, 4)),
            (EnchantScroll(25, 1), EnchantTarget(1, 'weapon', 0, bless=128)),
            (EnchantScroll(25, 1), EnchantTarget(1, 'weapon', 0,
                                               normal_scroll_eligible=False)),
            (EnchantScroll(25, 1), EnchantTarget(999999, 'weapon', 0)),
            (EnchantScroll(25, 1), EnchantTarget(999999, 'weapon', 0, 6)),
            (EnchantScroll(25, 1), EnchantTarget(999999, 'weapon', 0, -1,
                                               normal_scroll_eligible=True)),
        ]
        for scroll, target in cases:
            with self.subTest(scroll=scroll, target=target):
                p = propose_enchant(scroll, target)
                r = self.resolve(p)
                self.assertFalse(p.accepted)
                self.assertEqual((r.status, r.consume_scroll, r.remove_target,
                                  r.level_after), ('rejected', 0, False, target.level))

    def test_known_m1_safety_is_per_item(self):
        # Classic103's fixed official enchantDescription allows +4. The current
        # policy keeps that safety ahead of historical L1J20322's value 0;
        # the zero-safety probability cases above remain separate LOCAL rules.
        for template, kind, safe in ((1, 'weapon', 6), (40, 'weapon', 6),
                                      (103, 'armor', 4), (102, 'armor', 4),
                                      (109, 'armor', 4)):
            p = propose_enchant(EnchantScroll(25 if kind == 'weapon' else 26, 1),
                                EnchantTarget(template, kind, 0))
            self.assertTrue(p.accepted)
            self.assertEqual(p.safe_enchant, safe)

    def test_roll_bounds_and_immutable_proposals(self):
        p = self.proposal()
        for roll in (0, 101):
            with self.assertRaises(ValueError):
                self.resolve(p, roll)
            with self.assertRaises(ValueError):
                self.resolve(p, blessing=roll)
        with self.assertRaises(TypeError):
            self.resolve(p, True)
        with self.assertRaises(FrozenInstanceError):
            p.accepted = False


class EnchantCombatTests(unittest.TestCase):
    def test_melee_durability_and_java_negative_division(self):
        for effective, hit in ((-5, -2), (-3, -1), (-1, 0), (0, 0), (5, 2)):
            b = weapon_enchant_bonus(effective + 7, durability=7)
            self.assertEqual((b.effective_enchant, b.damage, b.hit),
                             (effective, effective, hit))

    def test_ranged_ignores_durability(self):
        b = weapon_enchant_bonus(7, durability=9, ranged=True)
        self.assertEqual((b.damage, b.hit), (7, 3))

    def test_armor_ac_and_accessory_exception(self):
        self.assertEqual(armor_enchant_ac_bonus(4), -4)
        self.assertEqual(armor_enchant_ac_bonus(-3), 3)
        self.assertEqual(armor_enchant_ac_bonus(9, accessory=True), 0)


if __name__ == '__main__':
    unittest.main()
