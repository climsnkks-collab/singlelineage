"""Temporary profiles only; no runtime, source decoder, socket or sender."""
from pathlib import Path
from contextlib import contextmanager
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store as s
from tools.local_original_session.inventory_tests import explicit_fields


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        self.characters = s.realm.CharacterStore(self.profile)
        for name in ('StoredOne', 'StoredTwo'):
            self.characters.create(s.realm.Creation(name, 0, 0, (13,) * 6))
        self.profile_bytes = self.profile.read_bytes()
        self.store = s.InventoryStore(self.profile, policy=s.POLICY)
        self.fields = explicit_fields()  # Pure fixture; never a runtime default.
        self.wire = inventory.build_add(self.fields)

    def assert_profile_preserved(self):
        self.assertTrue(self.profile.read_bytes() == self.profile_bytes)
        self.assertEqual(list(self.profile.parent.glob('.inventory-*.tmp')), [])

    @contextmanager
    def trace_character_snapshot(self):
        """Trace real file bytes; the original roster validator still runs."""
        trace = dict(opens=0, reads=[], validated=0)
        original_open, original_bytes = Path.open, Path.read_bytes
        original_validation = s.realm.CharacterStore._read
        case = self
        class Tracked:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def fileno(self): return self.stream.fileno()
            def read(self, count):
                case.assertEqual(count, 65537)
                raw = self.stream.read(count)
                trace['reads'].append(dict(requested=count, raw=raw))
                return raw
        def opened(path, mode='r', *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            if path == self.profile:
                self.assertEqual(mode, 'rb')
                trace['opens'] += 1
                return Tracked(stream)
            return stream
        def physical_read_bytes(path):
            if path == self.profile:
                self.fail('unsafe second physical character read')
            return original_bytes(path)
        def validate(validator):
            self.assertIs(type(validator), s.realm.CharacterStore)
            self.assertIs(type(validator.path), s._CharacterSnapshot)
            self.assertIs(type(validator.path.raw), bytes)
            self.assertTrue(trace['reads'])
            self.assertIs(validator.path.raw, trace['reads'][-1]['raw'])
            trace['validated'] += 1
            return original_validation(validator)
        with patch.object(Path, 'open', opened), patch.object(Path, 'read_bytes', physical_read_bytes), \
                patch.object(s.realm.CharacterStore, '_read', validate):
            yield trace

    def test_finding1_character_duplicates_oversize_and_malformed_roster_refuse_all_entrypoints(self):
        self.store.grant(1, self.wire)
        sidecar = self.store.path.read_bytes()
        original = json.loads(self.profile_bytes)
        raw = json.dumps(original, separators=(',', ':')).encode()
        schema = json.dumps(original['schema']).encode()
        first = original['characters'][0]
        row = json.dumps(first, separators=(',', ':')).encode()
        malformed = json.loads(raw); malformed['characters'][0]['attributes'] = [13]
        duplicated_roster = json.loads(raw); duplicated_roster['characters'][1]['uid'] = first['uid']
        variants = [
            ('duplicate_schema', raw.replace(b'"schema":' + schema, b'"schema":' + schema + b',"schema":' + schema, 1), 'CHARACTER_JSON', 0),
            ('duplicate_next_uid', raw.replace(b'"next_uid":3', b'"next_uid":3,"next_uid":3', 1), 'CHARACTER_JSON', 0),
            ('duplicate_characters', raw.replace(b'"characters":[', b'"characters":[],"characters":[', 1), 'CHARACTER_JSON', 0),
            ('duplicate_row_uid', raw.replace(row, row.replace(b'"uid":1', b'"uid":1,"uid":1', 1), 1), 'CHARACTER_JSON', 0),
            ('duplicate_row_name', raw.replace(row, row.replace(b'"name":"StoredOne"', b'"name":"StoredOne","name":"StoredOne"', 1), 1), 'CHARACTER_JSON', 0),
            ('oversize', b' ' * 65537, 'CHARACTER_SIZE', 0),
            ('malformed_attributes', json.dumps(malformed).encode(), 'CREATE_STORE_ROW_TYPE', 1),
            ('malformed_duplicate_uid', json.dumps(duplicated_roster).encode(), 'CREATE_STORE_DUPLICATE', 1),
        ]
        refusal_count, max_request, max_returned = 0, 0, 0
        for label, content, reason, validator_calls in variants:
            self.profile.write_bytes(content)
            for action in (lambda: s.InventoryStore(self.profile, policy=s.POLICY),
                           lambda: self.store.restore(1), lambda: self.store.grant(2, self.wire)):
                with self.subTest(case=label), self.trace_character_snapshot() as trace:
                    with self.assertRaisesRegex(ValueError, reason): action()
                    self.assertEqual(trace['opens'], 1)
                    self.assertLessEqual(len(trace['reads']), 1)
                    self.assertEqual(trace['validated'], validator_calls)
                    if trace['reads']:
                        max_request = max(max_request, trace['reads'][0]['requested'])
                        max_returned = max(max_returned, len(trace['reads'][0]['raw']))
                self.assertTrue(self.profile.read_bytes() == content)
                self.assertTrue(self.store.path.read_bytes() == sidecar)
                self.assertEqual(list(self.profile.parent.glob('.inventory-*.tmp')), [])
                refusal_count += 1
        # Even stale/underreported fstat cannot cause an unbounded read.
        real_fstat = s.os.fstat
        def underreported(fd):
            info = real_fstat(fd)
            return type('StatFixture', (), {'st_size': 65536})() if info.st_size > 65536 else info
        self.profile.write_bytes(b' ' * 65537)
        with self.trace_character_snapshot() as trace, patch.object(s.os, 'fstat', underreported):
            with self.assertRaisesRegex(ValueError, 'CHARACTER_SIZE'): self.store.restore(1)
            self.assertEqual((trace['opens'], len(trace['reads']), trace['validated']), (1, 1, 0))
            self.assertEqual(len(trace['reads'][0]['raw']), 65537)
        self.assertTrue(self.store.path.read_bytes() == sidecar)
        self.profile.write_bytes(self.profile_bytes)
        self.assert_profile_preserved()
        print('inventory_store_finding1_refusals=' + str(refusal_count + 1)
              + '; max_character_read_request=' + str(max_request)
              + '; regular_max_returned=' + str(max_returned)
              + '; underreported_fstat_returned=65537; second_physical_read=0')

    def test_finding1_same_immutable_snapshot_original_validator_and_one_read_per_operation(self):
        with self.trace_character_snapshot() as trace:
            store = s.InventoryStore(self.profile, policy=s.POLICY)
            self.assertTrue(store.grant(1, self.wire))
            self.assertTrue(store.restore(1) == self.wire)
            reopened = s.InventoryStore(self.profile, policy=s.POLICY)
            self.assertIs(reopened.grant(1, self.wire), False)
            self.assertIsNone(reopened.restore(2))
        self.assertEqual((trace['opens'], len(trace['reads']), trace['validated']), (6, 6, 6))
        self.assertTrue(all(read['requested'] == 65537 and len(read['raw']) <= 65536 for read in trace['reads']))
        self.assert_profile_preserved()
        print('inventory_store_finding1_snapshot_operations=6; physical_reads=6; same_object_original_validations=6; max_request=65537')

    def test_explicit_policy_empty_and_exact_opaque_reopen_idempotence(self):
        with self.assertRaises(TypeError): s.InventoryStore(self.profile)
        for policy in (None, False, '', s.POLICY.lower()):
            with self.assertRaisesRegex(ValueError, 'EXPLICIT_POLICY'):
                s.InventoryStore(self.profile, policy=policy)
        self.assertIsNone(self.store.restore(1))
        self.assertIsNone(self.store.restore(2))
        self.assertFalse(self.store.path.exists())
        real_fsync, real_replace = os.fsync, os.replace
        with patch.object(s.os, 'fsync', wraps=real_fsync) as sync, patch.object(s.os, 'replace', wraps=real_replace) as replace:
            self.assertIs(self.store.grant(1, self.wire), True)
            self.assertEqual((sync.call_count, replace.call_count), (1, 1))
        before = self.store.path.read_bytes()
        reopened = s.InventoryStore(self.profile, policy=s.POLICY)
        restored = reopened.restore(1)
        self.assertIs(type(restored), bytes)
        self.assertTrue(restored == self.wire)
        self.assertTrue(dict(inventory.validate_frame(restored).raw_fields) == self.fields)
        self.assertIsNone(reopened.restore(2))
        with patch.object(s.os, 'replace', side_effect=AssertionError('idempotence must not replace')):
            self.assertIs(self.store.grant(1, bytes(bytearray(self.wire))), False)
            self.assertIs(reopened.grant(1, self.wire), False)
        self.assertTrue(self.store.path.read_bytes() == before)
        self.assert_profile_preserved()
        print('inventory_store_opaque17_presence_roundtrip=PASS; idempotent_rewrites=0; missing_restore_writes=0')

    def test_character_uid_and_item_identifier_are_separate_without_cross_uid_merge(self):
        self.assertNotEqual(1, self.fields[1])
        self.assertTrue(self.store.grant(1, self.wire))
        # Item global uniqueness is not an established rule: equal item f1 and
        # equal bytes under a second saved character remain separate records.
        self.assertTrue(self.store.grant(2, self.wire))
        self.assertTrue(self.store.restore(1) == self.store.restore(2) == self.wire)
        before = self.store.path.read_bytes()
        for uid in (True, False, 0, -1, 1 << 32, '1', 3):
            for action in (lambda: self.store.restore(uid), lambda: self.store.grant(uid, self.wire)):
                with self.assertRaises(ValueError): action()
        # A new known character has empty state; it cannot receive either row
        # through a UID lookup, and no other record is removed or rewritten.
        self.characters.create(s.realm.Creation('StoredThree', 0, 0, (13,) * 6))
        self.assertIsNone(self.store.restore(3))
        self.assertTrue(self.store.path.read_bytes() == before)
        self.assertEqual(len(json.loads(before)['inventories']), 2)

    def test_same_item_different_raw_conflict_and_second_item_limit(self):
        self.store.grant(1, self.wire)
        before = self.store.path.read_bytes()
        changed = dict(self.fields); changed[3] -= 1
        other = dict(self.fields); other[1] -= 1
        with self.assertRaisesRegex(ValueError, 'ITEM_CONFLICT'):
            self.store.grant(1, inventory.build_add(changed))
        with self.assertRaisesRegex(ValueError, 'ONE_ROW_LIMIT'):
            self.store.grant(1, inventory.build_add(other))
        self.assertTrue(self.store.path.read_bytes() == before)
        self.assert_profile_preserved()

    def test_existing_only_exact_row_is_locked_no_write_and_missing_never_grants(self):
        with patch.object(s.InventoryStore, '_write', side_effect=AssertionError('unexpected write')):
            with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'):
                self.store.grant(1, self.wire, existing_only=True)
        self.assertFalse(self.store.path.exists())
        self.store.grant(1, self.wire)
        prior = self.store.path.read_bytes()
        original_read = self.store._read
        reads = []
        def read():
            self.assertTrue(s._lock._is_owned() and s.realm._lock._is_owned())
            reads.append(1)
            return original_read()
        with patch.object(self.store, '_read', read), patch.object(s.InventoryStore, '_write',
                side_effect=AssertionError('unexpected write')):
            self.assertIs(self.store.grant(1, bytes(bytearray(self.wire)), existing_only=True), False)
            with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'):
                self.store.grant(2, self.wire, existing_only=True)
        self.assertEqual(len(reads), 2)
        self.assertEqual(self.store.path.read_bytes(), prior)
        self.store.path.unlink()
        with patch.object(s.InventoryStore, '_write', side_effect=AssertionError('unexpected write')):
            with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'):
                self.store.grant(1, self.wire, existing_only=True)
        self.assertFalse(self.store.path.exists())
        self.assert_profile_preserved()

    def test_existing_only_changed_frame_conflicts_and_strict_bool_preserve_file(self):
        self.store.grant(1, self.wire)
        prior = self.store.path.read_bytes()
        changed, other = dict(self.fields), dict(self.fields)
        changed[2] += 1
        other[1] -= 1
        with patch.object(s.InventoryStore, '_write', side_effect=AssertionError('unexpected write')):
            for fields, reason in ((changed, 'ITEM_CONFLICT'), (other, 'ONE_ROW_LIMIT')):
                with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                    self.store.grant(1, inventory.build_add(fields), existing_only=True)
            for mode in (None, 0, 1, '', 'true', object()):
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'EXISTING_ONLY_BOOL_REQUIRED'):
                    self.store.grant(2, self.wire, existing_only=mode)
        self.assertEqual(self.store.path.read_bytes(), prior)
        self.assert_profile_preserved()

    def test_mutable_noncanonical_or_invalid_frames_and_parent_change_refuse_without_write(self):
        self.store.grant(1, self.wire)
        before = self.store.path.read_bytes()
        for frame in (True, bytearray(self.wire), memoryview(self.wire), self.wire[:-1],
                      self.wire + b'\0', self.wire[:2] + b'\0\0' + self.wire[4:]):
            with self.assertRaises(ValueError): self.store.grant(2, frame)
            self.assertTrue(self.store.path.read_bytes() == before)
        # The parent inventory.py source hash pin was removed: a changed pin value
        # no longer refuses Store reads/grants.
        with patch.object(s, 'INVENTORY_SOURCE_SHA', '0' * 64):
            self.assertEqual(self.store.restore(1), self.wire)
        self.assert_profile_preserved()

    def test_corrupt_existing_store_is_never_replaced_or_defaulted_empty(self):
        canonical = dict(uid=1, frame=self.wire.hex())
        variants = [b'{', b'{"version":1,"version":1,"inventories":[]}',
            json.dumps(dict(version=True, inventories=[])).encode(),
            json.dumps(dict(version=1, inventories=[canonical, canonical])).encode(),
            json.dumps(dict(version=1, inventories=[dict(uid=True, frame=self.wire.hex())])).encode(),
            json.dumps(dict(version=1, inventories=[dict(uid=3, frame=self.wire.hex())])).encode(),
            json.dumps(dict(version=1, inventories=[dict(uid=1, frame=self.wire.hex().upper())])).encode(),
            json.dumps(dict(version=1, inventories=[dict(uid=1, frame=self.wire[:-1].hex())])).encode(),
            json.dumps(dict(version=1, inventories=[dict(uid=1, frame='00' * 6)])).encode(),
            json.dumps(dict(version=1, inventories=[], extra=0)).encode(), b' ' * (s.InventoryStore.MAX_BYTES + 1)]
        for raw in variants:
            self.store.path.write_bytes(raw)
            for action in (lambda: s.InventoryStore(self.profile, policy=s.POLICY),
                           lambda: self.store.restore(1), lambda: self.store.grant(2, self.wire)):
                with self.assertRaises(ValueError): action()
                self.assertTrue(self.store.path.read_bytes() == raw)
        self.assert_profile_preserved()

    def test_partial_write_fsync_and_replace_failures_preserve_prior_file_and_cleanup(self):
        self.store.grant(1, self.wire)
        before = self.store.path.read_bytes()
        for name in ('fsync', 'replace'):
            with patch.object(s.os, name, side_effect=OSError('fixture failure')):
                with self.assertRaises(OSError): self.store.grant(2, self.wire)
            self.assertTrue(self.store.path.read_bytes() == before)
            self.assertIsNone(s.InventoryStore(self.profile, policy=s.POLICY).restore(2))
            self.assert_profile_preserved()
        original_open = Path.open
        class Partial:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *_): self.stream.close()
            def write(self, raw): return self.stream.write(raw[:len(raw) // 2])
        def partial_open(path, mode='r', *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            return Partial(stream) if mode == 'xb' and path.suffix == '.tmp' else stream
        with patch.object(Path, 'open', partial_open):
            with self.assertRaisesRegex(ValueError, 'PARTIAL_WRITE'): self.store.grant(2, self.wire)
        self.assertTrue(self.store.path.read_bytes() == before)
        self.assertIsNone(self.store.restore(2))
        self.assert_profile_preserved()
        print('inventory_store_failure_preserve=partial_write,fsync,replace; orphan_temporary_files=0')

    def test_exception_after_replace_has_complete_reload_outcome_without_duplicate_grant(self):
        self.store.grant(1, self.wire)
        replace = os.replace
        def replaced_then_failed(source, destination):
            replace(source, destination)
            raise OSError('fixture after replace')
        with patch.object(s.os, 'replace', replaced_then_failed):
            with self.assertRaises(OSError): self.store.grant(2, self.wire)
        reopened = s.InventoryStore(self.profile, policy=s.POLICY)
        self.assertTrue(reopened.restore(1) == reopened.restore(2) == self.wire)
        with patch.object(s.os, 'replace', side_effect=AssertionError('duplicate replacement')):
            self.assertIs(reopened.grant(2, self.wire), False)
        self.assert_profile_preserved()

    def test_replace_existing_full_frame_success_one_write_noop_and_other_uid_preserved(self):
        self.store.grant(1, self.wire)
        self.store.grant(2, self.wire)  # Same identifier in another UID remains independent.
        changed = dict(self.fields); changed.update({4: 0, 5: 0, 7: 17, 18: b'updated\x00raw'})
        replacement = inventory.build_add(changed)
        real_write, writes = self.store._write, []
        def write(rows):
            self.assertTrue(s._lock._is_owned() and s.realm._lock._is_owned())
            writes.append(dict(rows))
            return real_write(rows)
        with patch.object(self.store, '_write', write):
            self.assertIs(self.store.replace_existing(1, self.wire, replacement), True)
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0], {1: replacement, 2: self.wire})
        reopened = s.InventoryStore(self.profile, policy=s.POLICY)
        self.assertEqual(reopened.restore(1), replacement)
        self.assertEqual(reopened.restore(2), self.wire)
        prior = self.store.path.read_bytes()
        with patch.object(s.InventoryStore, '_write', side_effect=AssertionError('no-op write')):
            self.assertIs(self.store.replace_existing(1, replacement, replacement), False)
        self.assertEqual(self.store.path.read_bytes(), prior)
        self.assert_profile_preserved()

    def test_replace_existing_stale_noop_missing_and_wrong_uid_never_write(self):
        changed = dict(self.fields); changed[5] = 0
        replacement = inventory.build_add(changed)
        self.store.grant(1, self.wire)
        self.store.grant(2, replacement)
        prior = self.store.path.read_bytes()
        with patch.object(s.InventoryStore, '_write', side_effect=AssertionError('refused update wrote')):
            for uid, expected, new, reason in (
                    (1, replacement, replacement, 'EXPECTED_FRAME_CHANGED'),
                    (2, self.wire, replacement, 'EXPECTED_FRAME_CHANGED'),
                    (3, self.wire, replacement, 'UNKNOWN_CHARACTER_UID'),
                    (True, self.wire, replacement, 'CHARACTER_UID_REQUIRED')):
                with self.subTest(uid=uid, reason=reason), self.assertRaisesRegex(ValueError, reason):
                    self.store.replace_existing(uid, expected, new)
            self.assertEqual(self.store.path.read_bytes(), prior)
            self.characters.create(s.realm.Creation('StoredThree', 0, 0, (13,) * 6))
            with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'):
                self.store.replace_existing(3, self.wire, replacement)
            self.store.path.unlink()
            with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'):
                self.store.replace_existing(1, self.wire, replacement)
        self.assertFalse(self.store.path.exists())
        self.assertEqual(list(self.profile.parent.glob('.inventory-*.tmp')), [])

    def test_replace_existing_only_source_confirmed_fields_and_exact_full_frames(self):
        self.store.grant(1, self.wire)
        prior = self.store.path.read_bytes()
        with patch.object(s.InventoryStore, '_write', side_effect=AssertionError('invalid update wrote')):
            for key in (1, 2, 3, 9, 10, 13, 14, 16, 17, 22, 24, 25, 26):
                changed = dict(self.fields)
                value = changed[key]
                if key == 2:
                    changed[key] = next(k for k in sorted(inventory._source()[1])
                                        if k != value and 0 < k < (1 << 31))
                else:
                    changed[key] = not value if type(value) is bool else value ^ 1
                replacement = inventory.build_add(changed)
                reason = 'ITEM_CONFLICT' if key == 1 else 'UPDATE_FIELDS_REQUIRED'
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, reason):
                    self.store.replace_existing(1, self.wire, replacement)
            for value in (bytearray(self.wire), memoryview(self.wire), self.wire[:-1],
                          self.wire + b'\0', b'', None,
                          inventory._encode(inventory.ItemInfo(tuple(sorted(
                              (n, v) for n, v in self.fields.items() if n != 18))))):
                for args in ((value, self.wire), (self.wire, value)):
                    with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                        self.store.replace_existing(1, *args)
        self.assertEqual(self.store.path.read_bytes(), prior)
        self.assert_profile_preserved()

    def test_replace_existing_each_allowed_field_independently_preserves_raw_others(self):
        self.store.grant(1, self.wire)
        previous = self.wire
        values = dict(self.fields)
        for key, value in ((4, (1 << 64) - 1), (5, -(1 << 31)), (7, 0), (18, b'')):
            values[key] = value
            new = inventory.build_add(values)
            with self.subTest(key=key):
                self.assertIs(self.store.replace_existing(1, previous, new), True)
                restored = self.store.restore(1)
                self.assertEqual(restored, new)
                self.assertEqual(dict(inventory.validate_frame(restored).raw_fields), values)
            previous = new
        self.assert_profile_preserved()

    def test_replace_existing_original_source_and_saved_update_source_fail_closed(self):
        from tools.local_original_session import inventory_update
        self.store.grant(1, self.wire)
        prior = self.store.path.read_bytes()
        pins = dict(inventory_update.SOURCE_PINS)
        pins[inventory_update.EVIDENCE_DIR + 'findings.md'] = '0' * 64
        for mutation, reason in (
                (patch.object(inventory_update, 'SOURCE_PINS', pins), 'UPDATE_SOURCE_CHANGED'),
                (patch.object(inventory_update, 'ROOT', self.profile.parent), 'UPDATE_SOURCE_UNAVAILABLE')):
            with mutation, patch.object(s.InventoryStore, '_write', side_effect=AssertionError('source failure wrote')):
                with self.assertRaisesRegex(ValueError, reason):
                    self.store.replace_existing(1, self.wire, self.wire)
            self.assertEqual(self.store.path.read_bytes(), prior)
        self.assert_profile_preserved()

    def test_replace_existing_read_partial_fsync_and_replace_failures_preserve_prior(self):
        self.store.grant(1, self.wire)
        changed = dict(self.fields); changed[5] = 0
        replacement = inventory.build_add(changed)
        prior = self.store.path.read_bytes()
        original_open = Path.open
        class Partial:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *_): self.stream.close()
            def write(self, raw): return self.stream.write(raw[:len(raw) // 2])
        def partial_open(path, mode='r', *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            return Partial(stream) if mode == 'xb' and path.suffix == '.tmp' else stream
        def denied_open(path, mode='r', *args, **kwargs):
            if path == self.store.path and mode == 'rb': raise PermissionError('fixture inventory read')
            return original_open(path, mode, *args, **kwargs)
        real_sync = s.os.fsync
        def synced_then_failed(fd):
            real_sync(fd)
            raise OSError('fixture after fsync')
        for label, mutation, error in (
                ('read', patch.object(Path, 'open', denied_open), PermissionError),
                ('partial', patch.object(Path, 'open', partial_open), ValueError),
                ('fsync_before', patch.object(s.os, 'fsync', side_effect=OSError('fixture before fsync')), OSError),
                ('fsync_after', patch.object(s.os, 'fsync', synced_then_failed), OSError),
                ('replace_before', patch.object(s.os, 'replace', side_effect=OSError('fixture before replace')), OSError)):
            with self.subTest(label=label), mutation, self.assertRaises(error):
                self.store.replace_existing(1, self.wire, replacement)
            self.assertEqual(self.store.path.read_bytes(), prior)
            self.assertEqual(s.InventoryStore(self.profile, policy=s.POLICY).restore(1), self.wire)
            self.assert_profile_preserved()

    def test_replace_existing_after_replace_error_remains_error_with_complete_new_row(self):
        self.store.grant(1, self.wire)
        self.store.grant(2, self.wire)
        changed = dict(self.fields); changed[4] = 0
        replacement = inventory.build_add(changed)
        real_replace, replacements = s.os.replace, []
        def replaced_then_failed(source, destination):
            replacements.append((source, destination))
            real_replace(source, destination)
            raise OSError('fixture after replacement')
        with patch.object(s.os, 'replace', replaced_then_failed):
            with self.assertRaisesRegex(OSError, 'fixture after replacement'):
                self.store.replace_existing(1, self.wire, replacement)
        self.assertEqual(len(replacements), 1)
        reopened = s.InventoryStore(self.profile, policy=s.POLICY)
        self.assertEqual(reopened.restore(1), replacement)
        self.assertEqual(reopened.restore(2), self.wire)
        # Inspecting the resulting row does not retry the failed operation.
        self.assert_profile_preserved()

    def test_explicit_path_and_regular_single_file_convention(self):
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_CHARACTER_PROFILE'):
            s.InventoryStore(Path('relative-characters.json'), policy=s.POLICY)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_CHARACTER_PROFILE'):
            s.InventoryStore(self.store.path, policy=s.POLICY)
        with self.assertRaisesRegex(ValueError, 'CHARACTER_PROFILE_REQUIRED'):
            s.InventoryStore(self.profile.with_name('missing.json'), policy=s.POLICY)
        self.store.path.mkdir()
        with self.assertRaisesRegex(ValueError, 'REGULAR_SINGLE_FILE'):
            self.store.restore(1)
        self.store.path.rmdir()
        self.store.grant(1, self.wire)
        alias = self.profile.with_name('inventory-hardlink.json')
        os.link(self.store.path, alias)
        try:
            with self.assertRaisesRegex(ValueError, 'REGULAR_SINGLE_FILE'):
                self.store.restore(1)
        finally:
            alias.unlink()
        self.assert_profile_preserved()


if __name__ == '__main__':
    unittest.main()
