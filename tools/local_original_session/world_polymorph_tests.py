"""Pure calculation tests; not a packet, native appearance or gameplay PASS.

Run at project root: python -X utf8 -B -m tools.local_original_session.world_polymorph_tests
Only world_polymorph and standard-library modules are imported.
"""
from dataclasses import replace
import sys
import unittest

from tools.local_original_session.world_polymorph import (
    apply_polymorph, expire_polymorph, initial_appearance, level_allowed,
    load_polymorphs, remaining_ms, remove_polymorph, use_scroll, weapon_allowed,
)


class PolymorphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_polymorphs()

    def scroll(self, state, form='orc', *, grade=1, now=100, level=60,
               weapon='sword', item=299):
        return use_scroll(state, self.catalog, item_template_id=item, grade=grade,
                          form_key=form, character_level=level, now_ms=now,
                          weapon_type=weapon)

    def test_reviewed_catalog_keeps_distinct_sprite_and_item_namespaces(self):
        self.assertEqual(len(self.catalog.forms), 70)
        bow = self.catalog.forms['bow_orc']
        self.assertEqual(bow.classic_sprite_id, 3860)  # morph key, not NPC f2=57
        self.assertEqual(self.catalog.forms['orc'].classic_sprite_id, 3906)
        self.assertEqual(self.catalog.forms['goblin'].classic_sprite_id, 3861)
        self.assertEqual(self.catalog.forms['floating_eye'].classic_sprite_id, 30015)
        self.assertEqual(self.catalog.forms['shelob'].classic_sprite_id, 30018)
        self.assertEqual(self.catalog.forms['ungoliant'].classic_sprite_id, 30019)
        self.assertEqual(self.catalog.forms['yeti_morph'].classic_sprite_id, 30456)
        self.assertEqual(self.catalog.forms['yeti_morph'].l1j_poly_id, 2385)
        self.assertEqual(self.catalog.forms['giant_a_morph'].classic_sprite_id, 30455)
        self.assertEqual(self.catalog.scrolls[(299, 1)].l1j_item_id, 40088)
        self.assertEqual(self.catalog.scrolls[(299, 0)].l1j_item_id, 140088)
        with self.assertRaises(TypeError):
            self.catalog.forms['made_up'] = bow

    def test_level_threshold_inclusive_without_class_or_gm_bypass(self):
        form = self.catalog.forms['death_knight']
        self.assertFalse(level_allowed(form, 51))
        self.assertTrue(level_allowed(form, 52))
        original = initial_appearance(0)
        low = self.scroll(original, 'death_knight', level=51)
        self.assertFalse(low.allowed)
        self.assertEqual(low.reason, 'level_too_low')
        self.assertIs(low.state, original)
        self.assertEqual(low.consume_count, 0)
        at = self.scroll(original, 'death_knight', level=52)
        self.assertTrue(at.allowed)
        self.assertEqual(at.state.current_sprite_id, 3784)

    def test_weapon_mask_is_kind_specific_and_current_aliases_work(self):
        bow = self.catalog.forms['bow_orc']
        self.assertTrue(weapon_allowed(bow, 'bow'))
        self.assertTrue(weapon_allowed(bow, 'singlebow'))
        self.assertFalse(weapon_allowed(bow, 'sword'))
        melee = self.catalog.forms['orc']  # mask751 includes dagger/twohand, no spear/bow
        for kind in ('dagger', 'sword', 'twohand', 'tohandsword', 'axe', 'blunt', 'staff'):
            with self.subTest(kind=kind):
                self.assertTrue(weapon_allowed(melee, kind))
        self.assertFalse(weapon_allowed(melee, 'bow'))
        self.assertFalse(weapon_allowed(melee, 'spear'))
        spear = self.catalog.forms['black_knight_morph']  # mask1080
        self.assertTrue(weapon_allowed(spear, 'spear'))
        self.assertTrue(weapon_allowed(spear, 'chainsword'))
        self.assertFalse(weapon_allowed(spear, 'sword'))

    def test_mask_zero_still_allows_unarmed_and_proposes_weapon_takeoff(self):
        form = self.catalog.forms['floating_eye']
        self.assertTrue(weapon_allowed(form, None))
        self.assertTrue(weapon_allowed(form, 'unarmed'))
        self.assertFalse(weapon_allowed(form, 'dagger'))
        original = initial_appearance(0)
        result = self.scroll(original, 'floating_eye', weapon='sword')
        self.assertTrue(result.allowed)
        self.assertTrue(result.unequip_weapon)
        self.assertEqual(result.consume_count, 1)
        self.assertEqual(result.state.current_sprite_id, 30015)
        self.assertEqual(original, initial_appearance(0))

    def test_normal_and_blessed_durations_are_separate_local_policies(self):
        original = initial_appearance(61)
        normal = self.scroll(original, now=700)
        blessed = self.scroll(original, grade=0, now=700)
        self.assertEqual(normal.state.active.expires_at_ms, 1_800_700)
        self.assertEqual(blessed.state.active.expires_at_ms, 2_100_700)
        self.assertEqual(normal.consume_count, 1)
        self.assertEqual(blessed.consume_count, 1)

    def test_repolymorph_preserves_actual_original_and_replaces_timer(self):
        first = self.scroll(initial_appearance(61), grade=0, now=0)
        second = self.scroll(first.state, 'bow_orc', now=100)
        self.assertEqual(second.state.base_sprite_id, 61)
        self.assertEqual(second.state.current_sprite_id, 3860)
        self.assertEqual(second.state.active.started_at_ms, 100)
        self.assertEqual(second.state.active.expires_at_ms, 1_800_100)
        self.assertTrue(second.unequip_weapon)
        self.assertEqual(remove_polymorph(second.state).state, initial_appearance(61))
        self.assertEqual(first.state.current_sprite_id, 3906)

    def test_same_form_refresh_costs_one_without_appearance_change(self):
        first = self.scroll(initial_appearance(0), now=0)
        again = self.scroll(first.state, now=1000)
        self.assertTrue(again.allowed)
        self.assertFalse(again.appearance_changed)
        self.assertEqual(again.consume_count, 1)
        self.assertEqual(again.state.active.expires_at_ms, 1_801_000)

    def test_expiry_before_exact_and_after_deadline_is_idempotent(self):
        active = self.scroll(initial_appearance(0), now=100).state
        deadline = active.active.expires_at_ms
        before = expire_polymorph(active, now_ms=deadline - 1)
        self.assertIs(before.state, active)
        self.assertEqual(before.reason, 'not_due')
        self.assertEqual(remaining_ms(active, now_ms=deadline - 1), 1)
        at = expire_polymorph(active, now_ms=deadline)
        after = expire_polymorph(active, now_ms=deadline + 1)
        self.assertEqual(at.state, initial_appearance(0))
        self.assertEqual(after.state, at.state)
        self.assertEqual(at.reason, 'expired')
        self.assertTrue(at.appearance_changed)
        self.assertEqual(at.consume_count, 0)
        self.assertFalse(at.unequip_weapon)
        again = expire_polymorph(at.state, now_ms=deadline + 1)
        self.assertIs(again.state, at.state)
        self.assertFalse(again.appearance_changed)
        self.assertEqual(remaining_ms(active, now_ms=deadline + 1), 0)

    def test_remove_and_empty_scroll_selection_restore_without_requip(self):
        active = self.scroll(initial_appearance(901), 'floating_eye').state
        removed = remove_polymorph(active)
        undo_scroll = self.scroll(active, '')
        self.assertEqual(removed.state, initial_appearance(901))
        self.assertEqual(removed.consume_count, 0)
        self.assertFalse(removed.unequip_weapon)
        self.assertEqual(undo_scroll.state, removed.state)
        self.assertEqual(undo_scroll.consume_count, 1)
        noop = self.scroll(removed.state, '')
        self.assertTrue(noop.allowed)
        self.assertFalse(noop.appearance_changed)
        self.assertEqual(noop.consume_count, 1)

    def test_unknown_or_unmapped_inputs_preserve_active_state_without_cost(self):
        active = self.scroll(initial_appearance(0)).state
        for args, reason in (({'item': 40088}, 'unsupported_scroll'),
                             ({'item': 40096}, 'unsupported_scroll'),
                             ({'grade': 2}, 'unsupported_scroll'),
                             ({'form': 'ordinary_orc_sprite_56'}, 'unknown_form'),
                             ({'weapon': 'unknown'}, 'unknown_weapon_type'),
                             ({'form': 'death_knight', 'level': 1}, 'level_too_low')):
            with self.subTest(args=args):
                result = self.scroll(active, **args)
                self.assertFalse(result.allowed)
                self.assertIs(result.state, active)
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.consume_count, 0)
                self.assertFalse(result.unequip_weapon)

    def test_direct_layer_has_no_cost_and_rejects_non_item_cause(self):
        original = initial_appearance(0)
        form = self.catalog.forms['orc']
        result = apply_polymorph(original, form, character_level=1, now_ms=0,
                                  duration_ms=1000)
        self.assertTrue(result.allowed)
        self.assertEqual(result.consume_count, 0)
        blocked = apply_polymorph(original, replace(form, cause_mask=2),
                                   character_level=1, now_ms=0, duration_ms=1000)
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.reason, 'item_magic_not_allowed')
        self.assertIs(blocked.state, original)

    def test_invalid_time_units_rejected_without_loading_native_dependencies(self):
        original = initial_appearance(0)
        for now in (-1, 0.5, True):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.scroll(original, now=now)
        for duration in (0, -1, 1.5):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                apply_polymorph(original, self.catalog.forms['orc'],
                                 character_level=1, now_ms=0, duration_ms=duration)
        self.assertNotIn('capstone', sys.modules)
        self.assertNotIn('tools.local_original_session.broker', sys.modules)


if __name__ == '__main__':
    unittest.main()
