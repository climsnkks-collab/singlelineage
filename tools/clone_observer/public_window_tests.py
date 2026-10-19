"""Portable serializer contract checks; loads core only, never Windows adapters.

Optionally set PUBLIC_WINDOW_CORE to a baseline core.py for the same checks.
"""
import hashlib
import importlib.util
import os
import random
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'serializer_core', os.environ.get('PUBLIC_WINDOW_CORE', str(Path(__file__).with_name('core.py'))))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def opaque(text):
    return {'chars': len(text), 'sha256': digest(text)}


class PublicWindowTests(unittest.TestCase):
    def test_missing_fields_and_key_order(self):
        self.assertEqual(list(core.public_window({}).items()), [
            ('title_chars', 0), ('title_sha256', digest('')),
            ('class_chars', 0), ('class_sha256', digest('')),
            ('child_class_counts', {}), ('public_launcher_text', []),
            ('exact_source_launcher_message_detected', False), ('unknown_static_text', [])])

    def test_all_known_titles_and_classes(self):
        for title in core.PUBLIC_TITLES:
            with self.subTest(title=title):
                self.assertEqual(core.public_window({'title': title})['public_caption'], title)
        for name in core.PUBLIC_CLASSES:
            with self.subTest(name=name):
                row = core.public_window({'class': name, 'children': [{'class': name}]})
                self.assertEqual(row['public_class'], name)
                self.assertEqual(row['child_class_counts'], {name: 1})

    def test_unknown_duplicate_class_aggregation_and_order(self):
        names = ['private', 'Static', 'private', '', 'other', 'Static']
        row = core.public_window({'children': [{'class': name} for name in names]})
        self.assertEqual(list(row['child_class_counts'].items()), [
            ('unknown:' + digest('private'), 2), ('Static', 2),
            ('unknown:' + digest(''), 1), ('unknown:' + digest('other'), 1)])

    def test_static_matching_preserves_whitespace_and_duplicates(self):
        message = next(iter(core.PUBLIC_LAUNCHER_MESSAGES))
        known = '\t ' + message + '\r\n'
        texts = [known, 'private', known, ' ', '', message + '!', message]
        row = core.public_window({'children': [{'class': 'Static', 'text': t} for t in texts]})
        self.assertEqual(row['public_launcher_text'], [known, known, message])
        self.assertTrue(row['exact_source_launcher_message_detected'])
        self.assertEqual(row['unknown_static_text'], [opaque('private'), opaque(' '), opaque(message + '!')])

    def test_non_static_text_is_never_accessed(self):
        class Control(dict):
            def get(self, key, default=None):
                if key == 'text':
                    raise AssertionError('non-Static text access')
                return super().get(key, default)
        row = core.public_window({'children': [Control({'class': name}) for name in
            ('Edit', 'ComboBox', 'ComboBoxEx32', 'StaticSuffix', 'private')]})
        self.assertEqual(row['unknown_static_text'], [])
        self.assertEqual(row['public_launcher_text'], [])

    def test_string_slicing_boundaries(self):
        for length in (0, 63, 64, 65, 239, 240, 241, 479, 480, 481):
            with self.subTest(length=length):
                value = '한' * length
                row = core.public_window({'title': value, 'class': value,
                    'children': [{'class': 'Static', 'text': value}]})
                self.assertEqual(row['title_chars'], min(length, 240))
                self.assertEqual(row['title_sha256'], digest(value[:240]))
                self.assertEqual(row['class_chars'], min(length, 64))
                self.assertEqual(row['class_sha256'], digest(value[:64]))
                self.assertEqual(row['unknown_static_text'], [opaque(value[:480])] if value else [])
        prefix = 'x' * 64
        row = core.public_window({'children': [{'class': prefix + 'a'}, {'class': prefix + 'b'}]})
        self.assertEqual(row['child_class_counts'], {'unknown:' + digest(prefix): 2})

    def test_children_bound_and_ignored_invalid_tail(self):
        for length in (0, 63, 64, 65):
            with self.subTest(length=length):
                children = [{'class': 'Static', 'text': str(i)} for i in range(length)]
                row = core.public_window({'children': children})
                self.assertEqual(row['child_class_counts'], {'Static': min(length, 64)} if length else {})
                self.assertEqual(row['unknown_static_text'], [opaque(str(i)) for i in range(min(length, 64))])
        core.public_window({'children': [{}] * 64 + [None]})

    def test_truncate_before_strip(self):
        message = next(iter(core.PUBLIC_LAUNCHER_MESSAGES))
        value = ' ' * (480 - len(message)) + message + 'private tail'
        row = core.public_window({'children': [{'class': 'Static', 'text': value}]})
        self.assertEqual(row['public_launcher_text'], [value[:480]])

    def test_ime_requires_exact_title_class_and_bool(self):
        for title in ('Default IME', 'Default IME '):
            for name in ('IME', 'IME ', ''):
                for visible in (True, False, 0, 1, None, 'true'):
                    row = core.public_window({'title': title, 'class': name, 'visible': visible})
                    expected = title == 'Default IME' and name == 'IME' and type(visible) is bool
                    self.assertEqual('window_role' in row, expected)
                    if expected:
                        self.assertEqual(row['public_caption'], 'Default IME')
                        self.assertEqual(row['window_role'], 'Windows_default_IME_infrastructure')
                        self.assertIs(row['game_UI_evidence'], False)
        self.assertNotIn('window_role', core.public_window({'title': 'Default IME', 'class': 'IME'}))

    def test_metadata_presence_values_and_order(self):
        keys = ('visible', 'geometry', 'owner_relation', 'parent_relation', 'same_process_child_count',
                'foreign_child_count', 'child_enumeration_truncated', 'public_metadata_errors')
        values = [False, [1, 2, 3, 4], None, 'none', 0, 2, True, ['denied']]
        source = dict(reversed(list(zip(keys, values))))
        source.update(title='Notice', owned_member={'pid': 7}, ignored='private')
        row = core.public_window(source)
        self.assertEqual(list(row)[5:13], list(keys))
        for key, value in zip(keys, values):
            self.assertIs(row[key], value)
        self.assertEqual(list(row)[-1], 'owned_member')
        self.assertIs(row['owned_member'], source['owned_member'])
        self.assertNotIn('ignored', row)
        self.assertIsNone(core.public_window({'owned_member': None})['owned_member'])

    @unittest.skipUnless(os.environ.get('PUBLIC_WINDOW_BASELINE'), 'optional frozen core path not supplied')
    def test_frozen_output_differential(self):
        baseline_spec = importlib.util.spec_from_file_location(
            'baseline_serializer_core', os.environ['PUBLIC_WINDOW_BASELINE'])
        baseline = importlib.util.module_from_spec(baseline_spec)
        baseline_spec.loader.exec_module(baseline)
        rng = random.Random(768)
        names = ['', 'Static', 'Edit', 'ComboBox', 'IME', 'private', 'x' * 64, 'x' * 65]
        titles = ['', 'Notice', 'private', 'Default IME', '한' * 241]
        message = next(iter(core.PUBLIC_LAUNCHER_MESSAGES))
        texts = ['', ' ', message, '\t' + message + '\n', message + '!', '한' * 481]
        rows = []
        for _ in range(1000):
            row = {'title': rng.choice(titles), 'class': rng.choice(names),
                   'children': [{'class': rng.choice(names), 'text': rng.choice(texts)}
                                for _ in range(rng.choice((0, 1, 63, 64, 65, 80)))]}
            for key in ('visible', 'geometry', 'owner_relation', 'parent_relation',
                        'same_process_child_count', 'foreign_child_count',
                        'child_enumeration_truncated', 'public_metadata_errors', 'owned_member'):
                if rng.randrange(2):
                    row[key] = rng.choice((None, False, True, 0, '', {'sample': [1, 2]}))
            rows.append(row)
        rows.extend([{'title': None}, {'class': None}, {'children': None},
                     {'children': [None]}, {'children': [{'class': 'Static', 'text': None}]},
                     {'title': '\ud800'}, {'children': [{'class': 'Static', 'text': '\ud800'}]}])

        def outcome(module, row):
            try:
                # repr preserves dict/list insertion order, values and types.
                return ('return', repr(module.public_window(row)))
            except Exception as error:
                return ('raise', type(error), error.args)

        for index, row in enumerate(rows):
            with self.subTest(index=index):
                self.assertEqual(outcome(core, row), outcome(baseline, row))

    def test_existing_invalid_value_errors(self):
        for source, error in [({'title': None}, TypeError), ({'class': None}, TypeError),
                ({'children': None}, TypeError), ({'children': [None]}, AttributeError),
                ({'children': [{'class': 'Static', 'text': None}]}, TypeError),
                ({'title': '\ud800'}, UnicodeEncodeError)]:
            with self.subTest(source=source), self.assertRaises(error):
                core.public_window(source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
