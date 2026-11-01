"""Pure ammunition preparation tests; no game/server/native imports or writes."""
from dataclasses import replace
import random
import unittest

from tools.local_original_session.game_data import load_items
from tools.local_original_session.world_ammo import (
    AmmoCost, AmmoStack, ArrowDef, L1J_ARROWS, in_weapon_range, prepare_attack,
    roll_arrow_damage,
)


class WorldAmmoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load_items()
        cls.bow = cls.items[11]

    def prepare(self, stacks=(), *, weapon=None, attacker=(0, 100, 100),
                target=(0, 101, 100), items=None):
        return prepare_attack(self.bow if weapon is None else weapon, stacks,
                              attacker=attacker, target=target,
                              items=self.items if items is None else items)

    def test_nonbow_and_unarmed_do_not_select_or_consume_ammo(self):
        def unused_inventory():
            raise AssertionError('nonbow must not inspect ammunition')
            yield
        for weapon in (None, self.items[12]):
            result = prepare_attack(weapon, unused_inventory(), attacker=(0, 0, 0),
                                    target=(1, 999, 999), items=self.items)
            self.assertTrue(result.allowed)
            self.assertIsNone(result.cost)
            self.assertIsNone(result.arrow)
            self.assertIsNone(result.weapon_range)

    def test_bow_requests_exact_stack_one_unit_and_leaves_input_unchanged(self):
        stacks = [AmmoStack(7001, 29, 8), AmmoStack(7002, 29, 20)]
        before = list(stacks)
        result = self.prepare(stacks)
        self.assertTrue(result.allowed)
        self.assertEqual(result.cost, AmmoCost(7001, 29, 1))
        self.assertEqual(result.arrow, L1J_ARROWS[40743])
        self.assertEqual(result.weapon_range, -1)
        self.assertEqual(stacks, before)

    def test_hit_and_miss_cost_is_per_fired_attack(self):
        # The API has no hit/miss input: each fired shot costs one before that
        # separate outcome. The caller supplies its updated snapshot each time.
        original = AmmoStack(901, 29, 2)
        first = self.prepare([original])
        self.assertEqual(first.cost, AmmoCost(901, 29, 1))
        after_first = replace(original, count=original.count - first.cost.count)
        self.assertEqual(after_first.count, 1)
        second = self.prepare([after_first])
        self.assertEqual(second.cost, AmmoCost(901, 29, 1))
        after_second = replace(after_first, count=after_first.count - second.cost.count)
        self.assertEqual(after_second.count, 0)
        third = self.prepare([after_second])
        self.assertFalse(third.allowed)
        self.assertEqual(third.reason, 'NO_ARROW')
        self.assertIsNone(third.cost)
        self.assertEqual(original.count, 2)

    def test_absent_zero_and_negative_stacks_refuse_without_cost(self):
        for stacks in ([], [AmmoStack(1, 29, 0)], [AmmoStack(1, 29, -1)]):
            result = self.prepare(stacks)
            self.assertFalse(result.allowed)
            self.assertEqual(result.reason, 'NO_ARROW')
            self.assertIsNone(result.cost)
            self.assertIsNone(result.arrow)

    def test_multiple_stacks_skip_empty_and_preserve_caller_order(self):
        stacks = [AmmoStack(99, 12, 3), AmmoStack(100, 29, 0),
                  AmmoStack(7, 29, 1), AmmoStack(2, 29, 8)]
        result = self.prepare(stacks)
        self.assertEqual(result.cost, AmmoCost(7, 29, 1))
        self.assertEqual(self.prepare(list(reversed(stacks))).cost, AmmoCost(2, 29, 1))

    def test_last_arrow_then_exhaustion_requires_caller_update(self):
        stacks = [AmmoStack(44, 29, 1)]
        first = self.prepare(stacks)
        self.assertEqual(first.cost, AmmoCost(44, 29, 1))
        self.assertEqual(self.prepare(stacks).cost, first.cost)  # no reservation
        exhausted = [replace(stacks[0], count=0)]
        self.assertEqual(self.prepare(exhausted).reason, 'NO_ARROW')
        self.assertEqual(self.prepare([]).reason, 'NO_ARROW')

    def test_reference_arrow_types_do_not_create_classic_mappings(self):
        for template in (30, 40743, 40744, 40745, 40746, 40747, 40748):
            with self.subTest(template=template):
                # Even an injected ammo definition is not an approved mapping.
                items = dict(self.items)
                items[template] = replace(self.items[29], template_id=template)
                result = self.prepare([AmmoStack(8, template, 100)], items=items)
                self.assertEqual(result.reason, 'NO_ARROW')
                self.assertIsNone(result.cost)

    def test_selection_requires_loaded_ammo_definition(self):
        missing = dict(self.items)
        del missing[29]
        wrong_kind = dict(self.items)
        wrong_kind[29] = replace(self.items[29], kind='potion')
        for items in (missing, wrong_kind):
            self.assertEqual(self.prepare([AmmoStack(9, 29, 2)], items=items).reason,
                             'NO_ARROW')

    def test_explicit_preloaded_items_and_unsupported_bow(self):
        result = prepare_attack(self.bow, [AmmoStack(5, 29, 1)],
                                attacker=(0, 0, 0), target=(0, 1, 0), items=self.items)
        self.assertEqual(result.cost, AmmoCost(5, 29, 1))
        unknown = self.prepare([AmmoStack(5, 29, 1)],
                               weapon=replace(self.bow, template_id=244))
        self.assertEqual(unknown.reason, 'BOW_RANGE_UNSUPPORTED')
        self.assertIsNone(unknown.cost)

    def test_bow_screen_shape_boundary_and_map_refusal_have_no_cost(self):
        # Point.isInScreen is a shaped Manhattan envelope, not Chebyshev17.
        for dx, dy, expected in ((13, 0, True), (14, 0, False),
                                 (15, -2, True), (16, -2, False),
                                 (-2, 15, True), (2, 15, False), (0, -13, True),
                                 (0, -14, False), (-15, 2, True),
                                 (9, 9, False), (-2, -15, False)):
            with self.subTest(dx=dx, dy=dy):
                result = self.prepare([AmmoStack(4, 29, 1)],
                                      target=(0, 100 + dx, 100 + dy))
                self.assertEqual(result.allowed, expected)
                self.assertEqual(in_weapon_range(-1, (0, 0, 0), (0, dx, dy)), expected)
                if not expected:
                    self.assertEqual(result.reason, 'OUT_OF_RANGE')
                    self.assertIsNone(result.cost)
        different_map = self.prepare([AmmoStack(4, 29, 1)], target=(1, 101, 100))
        self.assertEqual(different_map.reason, 'OUT_OF_RANGE')
        self.assertIsNone(different_map.cost)

    def test_finite_weapon_range_uses_plus_one_and_chebyshev(self):
        origin = (0, 10, 10)
        self.assertTrue(in_weapon_range(2, origin, (0, 13, 13)))
        self.assertFalse(in_weapon_range(2, origin, (0, 14, 10)))
        self.assertTrue(in_weapon_range(0, origin, (0, 11, 11)))
        self.assertFalse(in_weapon_range(2, origin, (1, 10, 10)))
        with self.assertRaises(ValueError):
            in_weapon_range(-2, origin, origin)

    def test_l1j_arrow_species_small_large_dice_and_hard_skin(self):
        expected = {40743: (6, 5), 40744: (7, 6), 40745: (9, 9),
                    40746: (10, 9), 40747: (11, 15), 40748: (12, 12)}
        for item_id, (small, large) in expected.items():
            arrow = L1J_ARROWS[item_id]
            self.assertEqual((arrow.small, arrow.large), (small, large))
            for size, maximum in (('small', small), ('large', large)):
                for hard in (False, True):
                    with self.subTest(item_id=item_id, size=size, hard=hard):
                        sides = maximum // 2 if hard else maximum
                        rng, reference = random.Random(71), random.Random(71)
                        rolls = [roll_arrow_damage(arrow, rng, target_size=size,
                                                   hard_skinned=hard) for _ in range(128)]
                        self.assertEqual(rolls, [reference.randint(1, sides) for _ in rolls])
                        self.assertEqual(set(rolls), set(range(1, sides + 1)))

    def test_zero_die_becomes_one_before_hard_skin_and_bad_size_is_explicit(self):
        zero = ArrowDef(0, 'reference zero-die rule', 0, 0)
        self.assertEqual(roll_arrow_damage(zero, random.Random(1), target_size='small'), 1)
        with self.assertRaises(ValueError):
            roll_arrow_damage(zero, random.Random(1), target_size='small', hard_skinned=True)
        with self.assertRaises(ValueError):
            roll_arrow_damage(L1J_ARROWS[40743], random.Random(1), target_size='typo')


if __name__ == '__main__':
    unittest.main()
