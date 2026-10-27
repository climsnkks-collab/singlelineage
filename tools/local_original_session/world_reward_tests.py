"""Fixed-seed reward arithmetic; no game, server, native owner or saved writes."""
from dataclasses import replace
import random
from types import MappingProxyType
import unittest

from tools.local_original_session.game_data import CHANCE_DENOMINATOR, load_m1
from tools.local_original_session.world_combat import PcProfile, PcState
from tools.local_original_session.world_reward import RewardPcState, on_kill


class WorldRewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()
        cls.no_drops = replace(cls.data, drops=MappingProxyType({}))

    def state(self, exp=0, *, character_class=0, con=10, wis=10, max_hp=20, max_mp=10):
        profile = PcProfile(self.data.level_for_exp(exp), character_class, 0, 13, 10,
                            con=con, wis=wis)
        fields = {1: 65537, 2: profile.level, 10: 8, 11: max_hp}
        if max_mp is not None:
            fields.update({12: 3, 13: max_mp})
        return PcState(profile, fields, 8, max_hp)

    def reward(self, state, exp, kill_exp, seed=7, *, data=None):
        inputs = RewardPcState.from_combat(state, exp=exp)
        monster = replace(self.data.monsters[0], kill_exp=kill_exp)
        return on_kill(inputs, monster, random.Random(seed),
                       data=self.no_drops if data is None else data)

    def test_accumulation_requires_caller_application_and_does_not_mutate(self):
        state = self.state(20)
        before = (state.profile, dict(state.status_fields), state.hp, state.max_hp,
                  state.max_mp, state.next_attack_at)
        first = self.reward(state, 20, 5)
        self.assertEqual((first.exp_gained, first.new_exp, first.level_ups), (5, 25, 0))
        second = self.reward(state, first.new_exp, 5)
        self.assertEqual(second.new_exp, 30)
        self.assertEqual((second.max_hp, second.max_mp), (20, 10))
        self.assertEqual((state.profile, state.status_fields, state.hp, state.max_hp,
                          state.max_mp, state.next_attack_at), before)

    def test_level_one_boundary_and_seeded_growth(self):
        state = self.state(123)
        before = self.reward(state, 123, 1)
        self.assertEqual((before.new_exp, before.new_level, before.level_ups), (124, 1, 0))
        at = self.reward(state, 124, 1)
        self.assertEqual((at.new_exp, at.old_level, at.new_level, at.level_ups), (125, 1, 2, 1))
        # Seed7: HP die=1, MP die=1; royal CON10/WIS10 => +12HP/+2MP.
        self.assertEqual((at.max_hp, at.max_mp), (32, 12))

    def test_multiple_levels_roll_growth_for_each_level(self):
        reward = self.reward(self.state(), 0, 750)
        self.assertEqual((reward.new_exp, reward.new_level, reward.level_ups), (750, 5, 4))
        # Seed7 HP/MP dice: (1,1),(1,1),(0,1),(1,1).
        self.assertEqual((reward.max_hp, reward.max_mp), (67, 18))

    def test_class_and_original_stat_growth(self):
        # Same die rolls, but different class scaling and original-stat bonuses.
        # Seed7 WIS18 d4=2, +2 WIS seedZ before class scaling/bonus.
        expected = ((38, 15), (44, 12), (36, 18), (33, 20))
        for character_class, maxima in enumerate(expected):
            with self.subTest(character_class=character_class):
                state = self.state(124, character_class=character_class, con=18, wis=18)
                result = self.reward(state, 124, 1)
                self.assertEqual((result.max_hp, result.max_mp), maxima)

    def test_unknown_mp_is_preserved(self):
        state = self.state(124, max_mp=None)
        result = self.reward(state, 124, 1)
        self.assertEqual(result.max_hp, 32)
        self.assertIsNone(result.max_mp)
        self.assertNotIn(13, state.status_fields)

    def test_growth_cap_precedes_original_bonus_like_l1j(self):
        result = self.reward(self.state(124, con=18, wis=18, max_hp=1399, max_mp=799), 124, 1)
        self.assertEqual((result.max_hp, result.max_mp), (1403, 801))

    def test_zero_full_chance_count_range_and_resolved_rows_only(self):
        row = self.data.drops[0][0]
        none = replace(row, item_id=10001, chance=0, min_count=1, max_count=1)
        full = replace(row, item_id=10002, chance=CHANCE_DENOMINATOR, min_count=2, max_count=5)
        cursed = replace(full, grade=2)
        data = replace(self.data, drops=MappingProxyType({0: (none, full, cursed)}))
        seen = set()
        for seed in range(16):
            result = self.reward(self.state(), 0, 0, seed, data=data)
            self.assertEqual([item for item, _ in result.drops], [10002, 10002])
            self.assertTrue(all(2 <= count <= 5 for _, count in result.drops))
            self.assertEqual([row.grade for row in result.rolled_rows], [1, 2])
            seen.update(count for _, count in result.drops)
        self.assertEqual(seen, {2, 3, 4, 5})

    def test_exp_uses_monster_value_without_level_gap_correction_and_retains_overflow(self):
        exp = self.data.pc_exp[-1]
        result = self.reward(self.state(exp), exp, 17)
        self.assertEqual((result.exp_gained, result.new_exp, result.new_level, result.level_ups),
                         (17, exp + 17, 30, 0))

    def test_three_argument_api_uses_m1_tables(self):
        state = self.state()
        monster = self.data.monsters[0]
        result = on_kill(RewardPcState.from_combat(state, exp=0), monster, random.Random(7))
        self.assertEqual(result.exp_gained, monster.kill_exp)
        self.assertTrue(any(item_id == 7 for item_id, _ in result.drops))


from tools.local_original_session.world_reward import death_exp_loss_rate, death_exp_penalty


class DeathExpPenaltyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()

    def test_all_l1j_rate_tiers_and_explicit_high_level_configuration(self):
        for level, expected in ((1, 0.0), (10, 0.0), (11, 0.1), (44, 0.1),
                                (45, 0.09), (46, 0.08), (47, 0.07),
                                (48, 0.06), (49, 0.05)):
            with self.subTest(level=level):
                self.assertEqual(death_exp_loss_rate(level), expected)
        self.assertEqual(death_exp_loss_rate(50, penalty_divisor=1), 0.05)
        self.assertEqual(death_exp_loss_rate(65, penalty_divisor=2), 0.025)
        self.assertEqual(death_exp_loss_rate(99, penalty_divisor=16777216),
                         0.05 * (1.0 / 16777216))

    def test_levels_one_through_ten_have_no_loss(self):
        for exp in (0, 124, 125, 10000, 14660):
            with self.subTest(exp=exp):
                result = death_exp_penalty(exp, data=self.data)
                self.assertEqual((result.old_exp, result.new_exp, result.exp_lost),
                                 (exp, exp, 0))
                self.assertEqual(result.old_level, result.new_level)
        self.assertEqual(death_exp_penalty(0).exp_lost, 0)

    def test_loss_uses_whole_level_span_and_can_delevel(self):
        at_boundary = death_exp_penalty(14661, data=self.data)
        self.assertEqual((at_boundary.need_exp, at_boundary.exp_lost), (6095, 609))
        self.assertEqual((at_boundary.old_level, at_boundary.new_level,
                          at_boundary.new_exp), (11, 10, 14052))
        above_boundary = death_exp_penalty(16000, data=self.data)
        self.assertEqual((above_boundary.exp_lost, above_boundary.new_exp,
                          above_boundary.new_level), (609, 15391, 11))
        # Calling a preview twice neither compounds the loss nor modifies data.
        self.assertEqual(death_exp_penalty(14661, data=self.data), at_boundary)

    def test_last_m1_level_requires_its_next_threshold(self):
        with self.assertRaisesRegex(ValueError, 'next cumulative level threshold'):
            death_exp_penalty(810016, data=self.data)
        # ExpTable.java:99 _expTable[30] = 0xe1791 = 923537 (Lv31).
        result = death_exp_penalty(810016, data=self.data, next_level_exp=923537)
        self.assertEqual((result.need_exp, result.exp_lost, result.new_exp,
                          result.old_level, result.new_level),
                         (113521, 11352, 798664, 30, 29))
        self.assertEqual(len(self.data.pc_exp), 30)

    def test_every_supported_nonexempt_m1_level_uses_its_existing_span(self):
        for level in range(11, 30):
            exp = self.data.exp_for_level(level)
            need = self.data.exp_for_level(level + 1) - exp
            result = death_exp_penalty(exp, data=self.data)
            with self.subTest(level=level):
                self.assertEqual(result.exp_lost, int(need * 0.1))
                self.assertGreaterEqual(result.new_exp, 0)

    def test_integer_truncation_has_no_minimum_one_loss(self):
        data = replace(self.data, pc_exp=tuple(range(0, 1100, 100)) + (1007,))
        result = death_exp_penalty(1000, data=data)
        self.assertEqual((result.old_level, result.need_exp, result.exp_lost,
                          result.new_exp), (11, 7, 0, 1000))

    def test_configured_high_level_reciprocal_is_applied_once(self):
        data = replace(self.data, pc_exp=tuple(range(0, 51000, 1000)))
        result = death_exp_penalty(49000, data=data, penalty_divisor=2)
        self.assertEqual((result.need_exp, result.exp_lost, result.new_exp,
                          result.old_level, result.new_level),
                         (1000, 25, 48975, 50, 49))

    def test_missing_or_invalid_inputs_are_explicit(self):
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            death_exp_penalty(-1, data=self.data)
        for level in (0, 100):
            with self.subTest(level=level), self.assertRaises(ValueError):
                death_exp_loss_rate(level)
        for divisor in (None, 0, -1):
            with self.subTest(divisor=divisor), self.assertRaises(ValueError):
                death_exp_loss_rate(50, penalty_divisor=divisor)
        with self.assertRaisesRegex(ValueError, 'last table level'):
            death_exp_penalty(14661, data=self.data, next_level_exp=923537)
        with self.assertRaisesRegex(ValueError, 'unavailable next level'):
            death_exp_penalty(923537, data=self.data, next_level_exp=923537)


if __name__ == '__main__':
    unittest.main()
