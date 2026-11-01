"""Pure calculation tests; not a packet, native appearance or gameplay PASS.

Run at project root: python -X utf8 -B -m tools.local_original_session.world_polymorph_tests
Only world_polymorph and standard-library modules are imported.
"""
from dataclasses import replace
import json
import subprocess
import sys
import unittest

from tools.local_original_session.world_polymorph import (
    DEFAULT_PATH, apply_polymorph, expire_polymorph, initial_appearance, level_allowed,
    load_polymorphs, remaining_ms, remove_polymorph, use_scroll, weapon_allowed,
)


class PolymorphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_polymorphs()
        cls.raw = json.loads(DEFAULT_PATH.read_text(encoding='utf-8'))

    def scroll(self, state, form='orc', *, grade=1, now=100, level=60,
               weapon='sword', item=299):
        return use_scroll(state, self.catalog, item_template_id=item, grade=grade,
                          form_key=form, character_level=level, now_ms=now,
                          weapon_type=weapon)

    def test_reviewed_catalog_keeps_distinct_sprite_and_item_namespaces(self):
        self.assertEqual(len(self.catalog.forms), 77)
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

    def test_catalog_labels_have_unique_keys_and_explicit_runtime_scope(self):
        entries = self.raw['classic_catalog']['entries']
        self.assertEqual(len(entries), 85)
        self.assertEqual(len({row['key'] for row in entries}), 85)
        # POLYMORPH_UPDATE: three more Classic sprites resolved (75 -> 78).
        self.assertEqual(sum(row['classic_sprite']['sprite_id'] is not None for row in entries), 78)
        self.assertEqual(sum(row['weapon_restriction']['mask'] is not None for row in entries), 70)
        self.assertEqual(sum(row['runtime_form_key'] is not None for row in entries), 63)
        self.assertEqual(sum(row['runtime_status'] == 'UNKNOWN_SPECIAL_SCROLL_AVAILABILITY'
                             for row in entries), 7)
        self.assertEqual(sum(row['runtime_status'] == 'UNKNOWN_MISSING_SPR_OR_WEAPON_POLICY'
                             for row in entries), 15)
        for row in entries:
            with self.subTest(label=row['display_name']):
                if row['runtime_form_key'] is None:
                    self.assertNotIn(row['key'], self.catalog.forms)
                    self.assertEqual(self.scroll(initial_appearance(61), row['key']).reason,
                                     'unknown_form')
                    continue
                form = self.catalog.forms[row['runtime_form_key']]
                self.assertEqual(form.classic_sprite_id, row['classic_sprite']['sprite_id'])
                self.assertEqual(form.weapon_mask, row['weapon_restriction']['mask'])
                self.assertEqual(form.min_level, row['menu_condition']['min_level'])

    def test_native_selection_uses_exact_reviewed_xml_names_only(self):
        self.assertEqual(len(self.catalog.native_names), 63)
        self.assertEqual(self.catalog.native_names['orc morph'], 'orc')
        self.assertEqual(self.catalog.native_names['orc bow morph'], 'orc_bow_morph')
        self.assertNotIn('orc', self.catalog.native_names)
        self.assertNotIn('3906', self.catalog.native_names)
        self.assertNotIn('invented polymorph', self.catalog.native_names)
        for row in self.raw['classic_catalog']['entries']:
            with self.subTest(name=row['display_name']):
                if row['runtime_form_key'] is None:
                    self.assertNotIn(row['display_name'], self.catalog.native_names)
                else:
                    self.assertEqual(self.catalog.native_names[row['display_name']],
                                     row['runtime_form_key'])

    def test_promoted_xml_labels_use_reviewed_alias_policy_and_scroll_lifetime(self):
        expected = {
            'orc_bow_morph': ('bow_orc', 3860, 1, 256),
            'ghast_olive_morph': ('ghast', 3875, 10, 751),
            'bandit_archer_morph': ('bandit_bow_morph', 30458, 30, 256),
            'necromancer_one_morph': ('necromancer1', 3882, 45, 751),
            'necromancer_two_morph': ('necromancer2', 3883, 45, 751),
            'necromancer_three_morph': ('necromancer3', 3884, 45, 751),
            'necromancer_four_morph': ('necromancer4', 3885, 45, 751),
        }
        for key, (legacy, sprite, level, mask) in expected.items():
            with self.subTest(key=key):
                form, old = self.catalog.forms[key], self.catalog.forms[legacy]
                self.assertEqual((form.classic_sprite_id, form.min_level, form.weapon_mask),
                                 (sprite, level, mask))
                self.assertEqual((old.classic_sprite_id, old.min_level, old.weapon_mask),
                                 (sprite, level, mask))
                rejected = self.scroll(initial_appearance(61), key, level=level-1)
                self.assertFalse(rejected.allowed)
                self.assertEqual(rejected.consume_count, 0)
                for grade, duration in ((1, 1800_000), (0, 2100_000)):
                    result = self.scroll(initial_appearance(61), key, level=level,
                                         grade=grade, now=100, weapon='sword')
                    self.assertTrue(result.allowed)
                    self.assertEqual(result.consume_count, 1)
                    self.assertEqual(result.state.current_sprite_id, sprite)
                    self.assertEqual(result.state.active.expires_at_ms, 100+duration)
                    self.assertEqual(result.unequip_weapon, mask == 256)
                    self.assertEqual(expire_polymorph(result.state, now_ms=100+duration).state,
                                     initial_appearance(61))
                if mask == 256:
                    self.assertFalse(self.scroll(initial_appearance(61), key,
                                                 level=level, weapon='bow').unequip_weapon)

    def test_normal_xml_levels_do_not_enable_event_level_lowering(self):
        for key, expected in (('giant_a_morph', 30), ('yeti_morph', 30),
                              ('gelatincube', 30), ('darkelf_ranger_morph', 40),
                              ('elmor_soldier_morph', 45), ('black_knight_morph', 50)):
            with self.subTest(key=key):
                self.assertEqual(self.catalog.forms[key].min_level, expected)
                self.assertFalse(self.scroll(initial_appearance(61), key,
                                             level=expected-1).allowed)
                self.assertTrue(self.scroll(initial_appearance(61), key,
                                            level=expected, weapon=None).allowed)
        # Separate event labels belong to special item groups, not ordinary299.
        self.assertFalse(self.scroll(initial_appearance(61), 'death_knight', level=1).allowed)
        self.assertEqual(self.scroll(initial_appearance(61), 'event_death_knight', level=1).reason,
                         'unknown_form')

    def test_every_selectable_catalog_form_applies_level_lifetime_and_weapon_policy(self):
        original = initial_appearance(61)
        for entry in self.raw['classic_catalog']['entries']:
            key = entry['runtime_form_key']
            if key is None:
                continue
            form = self.catalog.forms[key]
            with self.subTest(key=key):
                rejected = self.scroll(original, key, level=form.min_level - 1)
                self.assertEqual(rejected.reason, 'level_too_low')
                self.assertIs(rejected.state, original)
                self.assertEqual(rejected.consume_count, 0)
                for grade, duration in ((1, 1800_000), (0, 2100_000)):
                    applied = self.scroll(original, key, level=form.min_level,
                                          grade=grade, now=700, weapon='sword')
                    self.assertTrue(applied.allowed)
                    self.assertEqual(applied.consume_count, 1)
                    self.assertEqual(applied.unequip_weapon, not bool(form.weapon_mask & 2))
                    self.assertEqual(applied.state.current_sprite_id, form.classic_sprite_id)
                    self.assertEqual(remaining_ms(applied.state, now_ms=700), duration)
                    self.assertEqual(expire_polymorph(applied.state,
                        now_ms=700 + duration).state, original)

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
        # Other discovered suites legitimately import native modules. Check
        # this pure module's import contract in a fresh interpreter.
        isolated = subprocess.run([sys.executable, '-c',
            "import sys; import tools.local_original_session.world_polymorph; "
            "assert 'capstone' not in sys.modules; "
            "assert 'tools.local_original_session.broker' not in sys.modules"],
            capture_output=True, text=True)
        self.assertEqual(isolated.returncode, 0, isolated.stderr)


if __name__ == '__main__':
    unittest.main()
