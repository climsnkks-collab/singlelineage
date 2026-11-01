"""Video-calibrated LOCAL arithmetic checks, without game, sockets or saves.

The supplied VIDEO_UNDEAD_ELEMENT_NOTES.md is ASR/user measurement evidence,
not an original-server formula. Compare relative reductions independently of
the retained L1J spell baseline, INT/SP interpretation and critical range.
"""
from dataclasses import replace
import json
import random
import unittest
from unittest.mock import patch

from tools.local_original_session import world_combat as combat
from tools.local_original_session.world_magic import PlayerMagic, load_catalog


class VideoMagicDamageTests(unittest.TestCase):
    def test_ice_dagger_fixed_seed_samples_match_reductions_within_five_points(self):
        parameters = PlayerMagic(load_catalog()).spells[5].raw['formula']['parameters']
        target = combat.PcProfile(42, 3, 0, 8, 7)
        # The video's SP12 is total SP; item_sp is an extra item delta. It is
        # deliberately zero here rather than adding twelve to INT18 again.
        samples = 100_000
        rows = []
        for name, mr, water, observed in (
                ('bare', 0, 0, 0), ('MR30', 30, 0, 20.5),
                ('MR50', 50, 0, 26.9), ('MR70', 70, 0, 34.1),
                ('water30', 0, 30, 35.9), ('water50', 0, 50, 51.4),
                ('MR50_water30', 50, 30, 100 * (1 - 9.14 / 18.2))):
            rng = random.Random(20261030)
            defender = replace(target, mr=mr, resist_water=water)
            values = [combat.magic_damage(parameters, 18, rng, target=defender)
                      for _ in range(samples)]
            mean = sum(values) / samples
            if not rows:
                baseline = mean
            reduction = 100 * (1 - mean / baseline)
            error = abs(reduction - observed)
            self.assertLessEqual(error, 5, name)
            rows.append(dict(condition=name, mean=mean, minimum=min(values),
                maximum=max(values), reduction_percent=reduction,
                video_error_percentage_points=error,
                video_baseline_equivalent_mean=18.2 * mean / baseline))
        # This is a ratio comparison, not an adjustment of the L1J V10/D10/N1
        # baseline to the video's 18.2 (range 11..27).
        self.assertAlmostEqual(baseline, 24.99267, places=5)
        print('VIDEO_MAGIC_SAMPLES', json.dumps(dict(seed=20261030,
            count_per_condition=samples, intelligence=18, item_sp=0, rows=rows)))

    def test_combined_measurement_prefers_nominal_resistance_interpretation(self):
        # Supplied ASR notes disagree internally: nominal 30% =>9.31 versus
        # measured-alone reduction35.9% =>8.5253. Actual combined mean is9.14.
        # Choose the closer interpretation without inventing caps or a floor.
        observed = 9.14
        self.assertAlmostEqual(13.3 * .70, 9.31)
        self.assertAlmostEqual(13.3 * .641, 8.5253)
        self.assertLess(abs(13.3 * .70 - observed),
                        abs(13.3 * .641 - observed))

    def test_int_sp_bonus_is_reduced_by_the_independent_element_multiplier(self):
        parameters = dict(damage_value=100, damage_dice=1,
            damage_dice_count=0, skill_level=7, element_attr_raw=4)
        bare = combat.PcProfile(42, 3, 0, 8, 7)
        defended = replace(bare, resist_water=30)
        # No random damage/critical; large baseline separates integer rounding
        # from the reduction policy, across INT and extra item SP changes.
        for intelligence, item_sp in ((12, 0), (18, 0), (18, 12), (30, 4)):
            kwargs = dict(item_sp=item_sp)
            before = combat.magic_damage(parameters, intelligence, random.Random(1),
                                         target=bare, **kwargs)
            after = combat.magic_damage(parameters, intelligence, random.Random(1),
                                        target=defended, **kwargs)
            self.assertLess(abs(100 * (1 - after / before) - 30), 1)

    def test_actual_single_and_area_consumers_use_shared_mr_arithmetic(self):
        from tools.local_original_session.world_magic_tests import WorldConsumerTests
        fixture = WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.prepare_new_tiers()
        original = combat.magic_damage
        for key in (5, 27):
            target = fixture.enemy()
            fixture.view.entities.move(target.uid, 0, 101, 100)
            group, slot = fixture.view.spawner.slot_for(target.uid)
            before = slot.hp = 10000
            fixture.view._refresh(1)
            fixture.fixture.now += 2
            with patch.object(combat, 'magic_damage', wraps=original) as observed:
                fixture.ctx._world_magic_cast(1, key, target.uid, fixture.fixture.now)
            self.assertTrue(observed.call_args_list)
            self.assertTrue(any(call.kwargs['mr'] == group.monster.mr
                                for call in observed.call_args_list))
            self.assertLess(slot.hp, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
