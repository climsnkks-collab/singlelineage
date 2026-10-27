"""Pure arithmetic/table tests only; no game, server, broker, port or save I/O.

Run: python -X utf8 -B -m tools.local_original_session.world_alignment_tests
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from tools.local_original_session import game_data as g, world_alignment as a


class ScriptedRng:
    """Assert the actual ranges/order, including protected item attempts."""
    def __init__(self, *draws):
        self.draws = list(draws)

    def randint(self, low, high):
        if not self.draws:
            raise AssertionError('unexpected RNG draw')
        expected_low, expected_high, value = self.draws.pop(0)
        if (low, high) != (expected_low, expected_high):
            raise AssertionError(f'RNG bounds {(low, high)} != {(expected_low, expected_high)}')
        if not low <= value <= high:
            raise AssertionError('script value outside RNG bounds')
        return value


class AlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = g.load_m1()
        cls.catalog = a.load_alignment_catalog()

    def test_real_m1_table_join_and_solo_awards(self):
        self.assertEqual(set(self.catalog), set(self.data.monsters))
        for template, npc_id, lawful in ((0, 45009, -2), (245, 45008, -3),
                                          (1, 45019, -3), (8, 45024, -9)):
            npc = self.catalog[template]
            self.assertEqual((npc.l1j_npcid, npc.lawful), (npc_id, lawful))
            self.assertEqual(npc.source.kind, 'l1j')
            change = a.on_kill(0, self.data.monsters[template], catalog=self.catalog)
            self.assertEqual((change.new_lawful, change.delta), (-lawful, -lawful))

    def test_calculation_path_reads_no_files(self):
        with patch.object(a.Path, 'read_text', side_effect=AssertionError('request-path I/O')):
            self.assertEqual(a.on_kill(100, self.data.monsters[0], catalog=self.catalog).new_lawful, 102)
            self.assertEqual(a.healing_amount(10, 32767), 19)
            self.assertEqual(a.roll_death_penalty(32767, (), ScriptedRng(),
                                                  penalty_applies=True).drops, ())

    def test_mapping_mismatch_is_not_guessed(self):
        wrong = replace(self.data.monsters[0], l1j_npcid=45017)
        with self.assertRaises(ValueError):
            a.on_kill(0, wrong, catalog=self.catalog)

    def test_java_negative_division_and_cast_order(self):
        self.assertEqual(a.java_div(-3, 2), -1)
        self.assertEqual(a.java_div(3, -2), -1)
        self.assertEqual(a.java_div(-3, -2), 1)
        change = a.kill_change(0, -3, hate=1, total_hate=2)
        self.assertEqual((change.shared_npc_lawful, change.delta), (-1, 1))
        # Two integer casts matter: int(3*.5)=1, then int(1*1.5)=1.
        self.assertEqual(a.kill_change(-100, -3, rate=.5, chaotic_rate=1.5).delta, 1)
        self.assertEqual(a.kill_change(-100, 3, rate=.5, chaotic_rate=1.5).delta, -1)

    def test_pre_kill_chaotic_rate_and_dead_recipient(self):
        self.assertEqual(a.kill_change(-1, -3, chaotic_rate=2).new_lawful, 5)
        self.assertEqual(a.kill_change(0, -3, chaotic_rate=2).new_lawful, 3)
        self.assertEqual(a.kill_change(0, -3, pc_dead=True).delta, 0)
        self.assertEqual(a.kill_change(-1, -3, pc_dead=True, chaotic_rate=2).new_lawful, -1)

    def test_pc_range_and_applied_vs_requested_change(self):
        positive = a.kill_change(32766, -9)
        self.assertEqual((positive.new_lawful, positive.delta, positive.requested_delta), (32767, 1, 9))
        negative = a.kill_change(-32767, 9)
        self.assertEqual((negative.new_lawful, negative.delta, negative.requested_delta), (-32768, -1, -9))
        self.assertEqual(a.clamp_lawful(-40000), -32768)
        self.assertEqual(a.clamp_lawful(40000), 32767)
        for bad in (-32769, 32768):
            with self.assertRaises(ValueError):
                a.kill_change(bad, -2)

    def test_classic_stat_display_stage_boundaries(self):
        for value, expected in ((-32768, 'chaotic'), (-1, 'chaotic'), (0, 'neutral'),
                                (499, 'neutral'), (500, 'neutral'), (501, 'lawful'), (32767, 'lawful')):
            self.assertEqual(a.display_stage(value), expected)

    def test_death_integer_probability_and_protection_threshold(self):
        for lawful, numerator in ((-32768, 520), (-30000, 496), (-20000, 416),
                                   (-10000, 336), (-1, 256), (0, 128), (30000, 8),
                                   (31982, 1), (31983, 0), (32232, 0), (32767, 0)):
            self.assertEqual(a.death_drop_chance(lawful), numerator)
        for lawful, maximum in ((-32768, 4), (-30000, 4), (-29999, 3), (-20000, 3),
                                (-19999, 2), (-10000, 2), (-9999, 1), (-1, 1), (0, 1)):
            self.assertEqual(a.death_drop_max_attempts(lawful), maximum)

    def test_death_probability_inclusive_boundary_and_nonnegative_count(self):
        item = a.DeathItem(1, 40, 1, False, True)
        rng = ScriptedRng((1, 1000, 128), (0, 0, 0))
        result = a.roll_death_penalty(0, (item,), rng, penalty_applies=True)
        self.assertEqual((result.attempts, result.drops[0].quantity), (1, 1))
        self.assertFalse(rng.draws)
        rng = ScriptedRng((1, 1000, 129))
        result = a.roll_death_penalty(0, (item,), rng, penalty_applies=True)
        self.assertEqual((result.attempts, result.drops), (0, ()))
        self.assertFalse(rng.draws)

    def test_death_early_return_consumes_no_rng(self):
        for lawful, applies in ((-32768, False), (31983, True), (32767, True)):
            result = a.roll_death_penalty(lawful, (), ScriptedRng(), penalty_applies=applies)
            self.assertEqual((result.chance_per_mille, result.attempts, result.drops), (0, 0, ()))

    def test_all_entries_selected_before_protection_without_reroll(self):
        items = (a.DeathItem(1, 7, 100, True, True),
                 a.DeathItem(2, 40, 1, False, False),
                 a.DeathItem(3, 100, 1, False, True, active_pet_amulet=True),
                 a.DeathItem(4, 14, 12, True, True))
        rng = ScriptedRng((1, 1000, 496), (1, 4, 4),
                          (0, 3, 0), (0, 3, 1), (0, 3, 2), (0, 3, 3))
        result = a.roll_death_penalty(-30000, items, rng, penalty_applies=True)
        self.assertEqual(result.attempts, 4)
        self.assertEqual([(d.item.uid, d.quantity) for d in result.drops], [(4, 12)])
        self.assertEqual(items[-1].count, 12)  # Pure proposal, input unchanged.
        self.assertFalse(rng.draws)

    def test_successive_attempts_use_reduced_inventory_and_full_stack(self):
        items = (a.DeathItem(1, 14, 10, True, True), a.DeathItem(2, 40, 2, False, True))
        rng = ScriptedRng((1, 1000, 1), (1, 4, 4),
                          (0, 1, 0), (0, 0, 0), (0, 0, 0))
        result = a.roll_death_penalty(-32768, items, rng, penalty_applies=True)
        self.assertEqual([(d.item.uid, d.quantity) for d in result.drops], [(1, 10), (2, 1), (2, 1)])
        self.assertFalse(rng.draws)

    def test_negative_single_count_still_draws_rng(self):
        item = a.DeathItem(1, 40, 1, False, True)
        rng = ScriptedRng((1, 1000, 256), (1, 1, 1), (0, 0, 0))
        result = a.roll_death_penalty(-1, (item,), rng, penalty_applies=True)
        self.assertEqual(result.attempts, 1)
        self.assertFalse(rng.draws)

    def test_empty_inventory_is_local_safe_no_candidate(self):
        rng = ScriptedRng((1, 1000, 1), (1, 4, 4))
        self.assertEqual(a.roll_death_penalty(-32768, (), rng, penalty_applies=True).drops, ())
        self.assertFalse(rng.draws)

    def test_magic_heal_is_caster_bonus_then_leverage_with_two_truncations(self):
        self.assertEqual(a.healing_amount(10, -32768), 10)
        self.assertEqual(a.healing_amount(10, 0), 10)
        self.assertEqual(a.healing_amount(10, 16384), 15)
        self.assertEqual(a.healing_amount(10, 32767), 19)  # Not exactly double.
        self.assertEqual(a.healing_amount(3, 16384, leverage=15), 6)  # 4.5->4, 6.
        self.assertEqual(a.healing_multiplier(-1), 1.0)
        self.assertEqual(a.healing_amount(0, 32767), 0)


if __name__ == '__main__':
    unittest.main()
