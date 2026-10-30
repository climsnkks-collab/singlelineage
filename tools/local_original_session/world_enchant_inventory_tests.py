"""Pure inventory/name/wire proposal tests; no save, game, ports or server."""
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory
from tools.local_original_session.game_data import load_items
from tools.local_original_session.world_enchant import EnchantResult
from tools.local_original_session import world_enchant_inventory as e


def row(uid, template, *, count=1, name=b''):
    fields = {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 71,
              9: 0, 10: 0, 13: 0, 14: 0, 16: 0, 17: 0, 18: name,
              22: 0, 24: False, 25: 0, 26: False}
    return inventory.ItemInfo(tuple(sorted(fields.items())))


def result(status='success', before=0, after=1):
    destroyed = status == 'destroyed'
    return EnchantResult(status, 'local_l1j_policy', before,
                         None if destroyed else after,
                         None if destroyed else after - before,
                         0 if status == 'rejected' else 1, destroyed)


def fields(frame):
    with pb.parse_message(frame[4:-2]) as parsed:
        return {f.number: bytes(f.value) if f.wire_type == 2 else f.value for f in parsed.fields}


def update_fields(frame):
    with pb.parse_message(frame[4:-2]) as outer:
        with pb.parse_message(bytes(outer.occurrences(1)[0].value)) as child:
            return {f.number: bytes(f.value) if f.wire_type == 2 else f.value for f in child.fields}


class EnchantInventoryTests(unittest.TestCase):
    def test_default_startup_keeps_target_use_and_mutation_without_unknown_result(self):
        from tools.local_original_session import world_feature_items as feature
        owner = SimpleNamespace()
        with patch.dict(os.environ):
            os.environ.pop('SL_EXPERIMENT_ENCHANT', None)
            feature.setup_enchant(owner)
            self.assertIsNone(owner._world_enchant_exp)
            for template in (25, 26):
                display = feature._world_items_display_fields(owner,
                    dict(row(81, template).raw_fields), row(81, template))
                self.assertEqual(display[5], 7)
            mutation = e.kit_mutation(self.items(), 81, 82, result(), self.defs)
            self.assertIsNone(e.result_frame(81, 82, result(), owner._world_enchant_exp,
                                            scroll_template_id=25))
        restored = inventory.validate_kit_frame(mutation.frame)
        self.assertEqual(dict(restored[1].raw_fields)[4], 1)
        self.assertEqual(e.enchant_level(restored[2], self.weapon), 1)
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in mutation.frames],
                         [0x0965, 0x0965, 0x4eea])

    @classmethod
    def setUpClass(cls):
        cls.defs = load_items()
        cls.weapon = cls.defs[1]

    def items(self, *, count=2, level=0, reverse=False):
        values = (row(80, 7, count=100),
                  row(81, 25, count=count, name=e.scroll_name(25, 1)),
                  row(82, 1, name=e.enchanted_name(self.weapon, level)))
        return tuple(reversed(values)) if reverse else values

    def test_grade_requires_exact_local_instance_marker(self):
        for template in (25, 26):
            for grade, label in ((0, '축복'), (1, '일반'), (2, '저주')):
                name = e.scroll_name(template, grade)
                self.assertTrue(name.decode().startswith(f'[{label}] '))
                self.assertEqual(e.scroll_grade(row(1, template, name=name)), grade)
                self.assertIsNone(e.scroll_grade(row(1, template, name=name + b' ')))
            self.assertIsNone(e.scroll_grade(row(1, template)))
        self.assertIsNone(e.scroll_grade(row(1, 1, name=e.scroll_name(25, 1))))

    def test_names_restore_positive_zero_and_cursed_negative_levels(self):
        for level in (-7, -1, 0, 1, 12):
            self.assertEqual(e.enchant_level(row(82, 1, name=e.enchanted_name(self.weapon, level)),
                                             self.weapon), level)
        self.assertEqual(e.enchant_level(row(82, 1), self.weapon), 0)
        for prefix in ('+0 ', '-0 ', '+01 ', '+1  ', '+x ', '1 ', ' +1 '):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                e.enchant_level(row(82, 1, name=(prefix + self.weapon.name_ko).encode()), self.weapon)

    def test_instance_grade_is_separate_from_enchant_and_survives_enchant(self):
        for grade in (0, 1, 2):
            target = row(82, 1, name=e.enchanted_name(self.weapon, -1, grade=grade))
            self.assertEqual((target.bless, target.blessed, target.cursed),
                             (grade, grade == 0, grade == 2))
            self.assertEqual(e.enchant_level(target, self.weapon), -1)
            items = (row(80, 7), row(81, 25, count=2, name=e.scroll_name(25, 2)), target)
            mutation = e.kit_mutation(items, 81, 82, result('success', -1, -2), self.defs)
            restored = inventory.validate_kit_frame(mutation.frame)[-1]
            self.assertEqual((restored.bless, e.enchant_level(restored, self.weapon)), (grade, -2))
        self.assertEqual(row(82, 1).bless, 1)
        self.assertFalse(row(82, 1, name=e.enchanted_name(self.weapon, -1)).cursed)

    def test_success_changes_only_quantity_and_target_name_keeps_order(self):
        for reverse in (False, True):
            items = self.items(reverse=reverse)
            before = tuple(dict(i.raw_fields) for i in items)
            mutation = e.kit_mutation(items, 81, 82, result(), self.defs)
            restored = inventory.validate_kit_frame(mutation.frame)
            self.assertEqual([i.identifier for i in restored], [i.identifier for i in items])
            self.assertEqual(tuple(dict(i.raw_fields) for i in items), before)
            for old, changed in zip(items, restored):
                expected = dict(old.raw_fields)
                if old.identifier == 81:
                    expected[4] = 1
                if old.identifier == 82:
                    expected[18] = e.enchanted_name(self.weapon, 1)
                self.assertEqual(dict(changed.raw_fields), expected)
                self.assertEqual(dict(changed.raw_fields)[7], 71)
            self.assertEqual(mutation.removed_uids, ())
            updates = {update_fields(f)[1]: update_fields(f) for f in mutation.frames[:-1]}
            self.assertEqual(updates[81], {1: 81, 4: 1})
            self.assertEqual(updates[82], {1: 82, 18: e.enchanted_name(self.weapon, 1)})
            self.assertEqual(e.enchant_level(restored[[i.identifier for i in restored].index(82)],
                                             self.weapon), 1)

    def test_last_scroll_and_destroyed_target_are_removed_without_f7_changes(self):
        mutation = e.kit_mutation(self.items(count=1), 81, 82,
                                  result('destroyed', 0, 0), self.defs)
        self.assertEqual([i.identifier for i in inventory.validate_kit_frame(mutation.frame)], [80])
        self.assertEqual(mutation.removed_uids, (81, 82))
        self.assertIsNone(mutation.target_level)
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in mutation.frames], [0x978, 0x978, 0x4eea])
        self.assertEqual([fields(f) for f in mutation.frames[:-1]], [{1: 81}, {1: 82}])

    def test_unchanged_consumes_only_scroll_and_rejection_changes_nothing(self):
        items = self.items(level=9)
        unchanged = e.kit_mutation(items, 81, 82, result('unchanged', 9, 9), self.defs)
        self.assertEqual([update_fields(f) for f in unchanged.frames[:-1]], [{1: 81, 4: 1}])
        rejected = e.kit_mutation(items, 81, 82, result('rejected', 9, 9), self.defs)
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in rejected.frames], [0x4eea])
        self.assertEqual(rejected.frame, inventory.build_kit_frame([dict(i.raw_fields) for i in items]))

    def test_cursed_success_uses_signed_local_name_and_last_scroll_removal(self):
        items = list(self.items(count=1))
        items[1] = row(81, 25, name=e.scroll_name(25, 2))
        mutation = e.kit_mutation(items, 81, 82, result('success', 0, -1), self.defs)
        restored = inventory.validate_kit_frame(mutation.frame)
        self.assertEqual(mutation.removed_uids, (81,))
        self.assertEqual(e.enchant_level(restored[1], self.weapon), -1)
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in mutation.frames], [0x978, 0x965, 0x4eea])

    def test_local_result_notice_distinguishes_outcomes_without_native_enchant_enum(self):
        cases = (('success', 0, 1, '+0 → +1'),
                 ('success', 0, -1, '+0 → -1'),
                 ('unchanged', 9, 9, '변하지 않았습니다'),
                 ('destroyed', 9, 9, '소멸했습니다'),
                 ('rejected', 9, 9, '소모되지 않았습니다'))
        for status, before, after, expected in cases:
            with self.subTest(status=status, after=after):
                outcome = result(status, before, after)
                mutation = e.kit_mutation(self.items(level=before), 81, 82, outcome, self.defs)
                frame = mutation.frames[-1]
                self.assertEqual(int.from_bytes(frame[:2], 'little'), len(frame))
                self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x4eea)
                message = fields(frame)
                self.assertEqual(message[1], 12066)
                text = bytes(message[2]).decode('utf-8')
                self.assertTrue(text.startswith(self.weapon.name_ko + ': '))
                self.assertIn(self.weapon.name_ko, text)
                self.assertIn(expected, text)
                self.assertIsNone(e.result_frame(81, 82, outcome, None, scroll_template_id=25))

    def test_bad_selection_stale_level_and_empty_kit_fail_before_commit(self):
        for target, changed_result in ((81, result()), (999, result()), (82, result(before=1, after=2))):
            with self.assertRaises(ValueError):
                e.kit_mutation(self.items(), 81, target, changed_result, self.defs)
        with self.assertRaisesRegex(ValueError, 'EMPTY_KIT'):
            e.kit_mutation(self.items(count=1)[1:], 81, 82, result('destroyed', 0, 0), self.defs)
        items = list(self.items())
        items[1] = row(81, 25, count=2)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_SCROLL_GRADE'):
            e.kit_mutation(items, 81, 82, result(), self.defs)

    def test_result_is_absent_by_default_and_only_candidate_behind_experiment(self):
        for raw in (None, '', '0'):
            self.assertIsNone(e.result_frame(81, 82, result(), e.parse_experiment(raw), scroll_template_id=25))
        wire = e.result_frame(81, 82, result(), e.parse_experiment('1'), scroll_template_id=25)
        self.assertEqual(int.from_bytes(wire[2:4], 'little'), 0x967)
        self.assertEqual(fields(wire), {1: 82, 2: 25, 3: 0, 4: 0, 5: 1})
        wire = e.result_frame(81, 82, result(), e.parse_experiment('1,f1=81,f3=5,f4=-1'), scroll_template_id=25)
        self.assertEqual(fields(wire), {1: 81, 2: 25, 3: 5, 4: (1 << 64) - 1, 5: 1})
        self.assertEqual(e.parse_experiment('f3=2').overrides, ((3, 2),))
        for raw in ('yes', '1,', '0,f3=2', 'f3=2,f3=3', 'f6=0', 'f1=-1', 'f3=2147483648'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                e.parse_experiment(raw)


if __name__ == '__main__':
    unittest.main()
