"""Recheck data and retained admission/lifetime; no original-client claims."""
import json
import unittest

from tools.local_original_session import world_polymorph as poly


class PolymorphRecheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(poly.DEFAULT_PATH.read_text(encoding='utf-8'))
        cls.catalog = poly.load_polymorphs()
        cls.entries = {row['key']: row for row in cls.raw['classic_catalog']['entries']}

    def test_new_sprite_identity_does_not_create_unattributed_weapon_policy(self):
        for key, sprite in (('chipao_man', 30148), ('chipao_woman', 30161),
                            ('hanbok_woman', 30191)):
            with self.subTest(key=key):
                row = self.entries[key]
                self.assertEqual(row['classic_sprite']['sprite_id'], sprite)
                self.assertIsNone(row['weapon_restriction']['mask'])
                self.assertIsNone(row['runtime_form_key'])
                self.assertNotIn(row['display_name'], self.catalog.native_names)
        candidate = self.entries['hanbok_man']
        self.assertIsNone(candidate['classic_sprite']['sprite_id'])
        self.assertEqual(candidate['sprite_candidate']['sprite_id'], 30217)

    def test_every_disabled_form_keeps_its_specific_missing_contract(self):
        disabled = [row for row in self.entries.values() if row['runtime_form_key'] is None]
        self.assertEqual(len(disabled), 22)
        for row in disabled:
            with self.subTest(key=row['key']):
                missing = row['recheck_20261028']['missing_contracts']
                self.assertTrue(missing)
                if row['classic_sprite']['sprite_id'] is None:
                    self.assertIn('confirmed_XML_name_to_Classic_SPR', missing)
                if row['weapon_restriction']['mask'] is None:
                    self.assertIn('attributed_weapon_mask_for_this_form', missing)
                result = poly.use_scroll(poly.initial_appearance(61), self.catalog,
                    item_template_id=299, grade=1, form_key=row['key'],
                    character_level=99, now_ms=0)
                self.assertEqual((result.allowed, result.consume_count), (False, 0))

    def test_special_items_cannot_borrow_general_scroll_lifetime_or_event_level(self):
        special = self.raw['recheck_20261028']['special_items']
        self.assertEqual(len(special), 9)
        for row in special:
            with self.subTest(item=row['client_item_id']):
                self.assertEqual(row['http_status'], 200)
                self.assertEqual(row['response'], 'empty_object')
                self.assertTrue(row['client_name_token'].startswith('$'))
                result = poly.use_scroll(poly.initial_appearance(61), self.catalog,
                    item_template_id=row['client_item_id'], grade=1, form_key='orc',
                    character_level=99, now_ms=0)
                self.assertEqual((result.reason, result.consume_count), ('unsupported_scroll', 0))
        result = poly.use_scroll(poly.initial_appearance(61), self.catalog,
            item_template_id=299, grade=1, form_key='death_knight',
            character_level=1, now_ms=0)
        self.assertEqual((result.reason, result.consume_count), ('level_too_low', 0))

    def test_retained_native_choices_apply_weapon_takeoff_and_timer_boundaries(self):
        for key in self.catalog.native_names.values():
            form = self.catalog.forms[key]
            with self.subTest(key=key):
                state = poly.initial_appearance(61)
                refused = poly.use_scroll(state, self.catalog, item_template_id=299,
                    grade=1, form_key=key, character_level=form.min_level-1, now_ms=0)
                self.assertEqual((refused.reason, refused.consume_count), ('level_too_low', 0))
                for grade, duration in ((1, 1_800_000), (0, 2_100_000)):
                    applied = poly.use_scroll(state, self.catalog, item_template_id=299,
                        grade=grade, form_key=key, character_level=form.min_level,
                        now_ms=1000, weapon_type='sword')
                    self.assertEqual(applied.consume_count, 1)
                    self.assertEqual(applied.unequip_weapon, not bool(form.weapon_mask & 2))
                    self.assertEqual(poly.remaining_ms(applied.state, now_ms=1000), duration)
                    self.assertIsNotNone(poly.expire_polymorph(applied.state,
                        now_ms=1000+duration-1).state.active)
                    self.assertEqual(poly.expire_polymorph(applied.state,
                        now_ms=1000+duration).state, state)


if __name__ == '__main__':
    unittest.main()
