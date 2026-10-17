"""Fixture-only Land presence and CP50 integration checks; no process access."""
import hashlib
import json
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import inspect_land as land

sys.path.insert(0, str(land.ROOT / 'tools/local_native_auto_login'))
import auto_enter_land_probe as helper


class Native:
    def __init__(self):
        self.contract = {}
        self.expected = {'pid': 1, 'birth': '2'}
        self.validations = 0

    def validate(self):
        self.validations += 1


class Sampler:
    def __init__(self, native, *, actors=1, maps=1, count=1):
        self.b, self.c = native, native.contract
        self.g = {'base': 0x140000000, 'size': 0x2000}
        self.bytes = 0
        self.memory = {}
        self.state, self.actor, self.map_sub = 0x20000, 0x30000, 0x40000
        self.begin, self.obj, self.ctrl = 0x50000, 0x60000, 0x70000
        self.public = {'Player': {'vector_begin': 0x8a8, 'vector_end': 0x8b0,
                                 'stride': 16, 'max_actor_elements': 512},
                       'Map': {'context_pointer': 0x6e0, 'field718': 0x718}}
        for key, rva in (('ActorSubsystem', 0x100), ('MyPlayer', 0x200), ('table', 0x300)):
            row = {'rva': rva, 'prefix_bytes': 40,
                   'normalized_sha256': hashlib.sha256(struct.pack('<5Q', *([0x1000] * 5))).hexdigest()}
            (self.public['Map'] if key == 'table' else self.public['Player'])[key] = row
            self.put(self.g['base'] + rva, struct.pack('<5Q', *([self.g['base'] + 0x1000] * 5)))
        self.put(self.actor, struct.pack('<Q', self.g['base'] + 0x100))
        self.put(self.map_sub, struct.pack('<Q', self.g['base'] + 0x300))
        self.put(self.obj, struct.pack('<Q', self.g['base'] + 0x200))
        self.put(self.ctrl + 8, struct.pack('<i', 1))
        self.put(self.actor + 0x8a8, struct.pack('<QQ', self.begin if count else 0,
                                              self.begin + count * 16 if count else 0))
        self.put(self.map_sub + 0x6e0, struct.pack('<Q', 0))
        self.put(self.map_sub + 0x718, struct.pack('<i', -1))
        self.put(self.state + 0x360, bytes(36))
        for i in range(count):
            self.put(self.begin + i * 16, struct.pack('<QQ', self.obj, self.ctrl))
        entries = [(struct.pack('<QQ', self.actor, self.ctrl), self.g['base'] + 0x100)] * actors
        entries += [(struct.pack('<QQ', self.map_sub, self.ctrl), self.g['base'] + 0x300)] * maps
        self.route_value = (1, True, 4, 2, 3, 4, tuple(entries), {'GameState': [self.state]})
        self.read_hook = None

    def put(self, at, raw):
        self.memory.update({at + index: byte for index, byte in enumerate(raw)})

    def read(self, at, size, image=False):
        land.watch.need(self.bytes + size <= self.read_limit, 'sample_byte_budget')
        self.bytes += size
        raw = bytes(self.memory[at + index] for index in range(size))
        if self.read_hook:
            self.read_hook(at, size)
        return raw

    def pointer(self, at, nullable=False):
        value = struct.unpack('<Q', self.read(at, 8))[0]
        land.watch.need((nullable and value == 0) or value >= 0x10000 and value % 8 == 0,
                        'pointer_noncanonical')
        return value

    def strong_pair(self, raw):
        obj, ctrl = struct.unpack('<QQ', raw)
        land.watch.need(struct.unpack('<i', self.read(ctrl + 8, 4))[0] > 0,
                        'shared_owner_not_positive')
        return obj, ctrl

    def route(self):
        return self.route_value

    def unique(self, objects, role):
        return objects[role][0]

    def scene(self, state):
        return {'current': {'kind': 'Land'}, 'pending': {'kind': 'none'}}, bytes(36)


class LandTests(unittest.TestCase):
    def fixture(self, **kwargs):
        native = Native()
        return native, Sampler(native, **kwargs)

    def inspect(self, native, sampler):
        with patch.object(land, 'public_contract', return_value=sampler.public):
            return land.inspect_attached(native, sampler)

    def test_exact_player_and_empty_map_values_remain_observations(self):
        native, sampler = self.fixture()
        row = self.inspect(native, sampler)
        self.assertEqual((row['status'], row['actor_count'], row['my_player_count']), ('OBSERVED', 1, 1))
        self.assertFalse(row['map_context_present'])
        self.assertEqual(row['map_field718'], -1)
        self.assertEqual(native.validations, 2)
        self.assertFalse(row['actual_gameplay_proven'])

    def test_empty_actor_is_zero_and_missing_actor_is_unknown_count(self):
        native, sampler = self.fixture(count=0)
        self.assertEqual(self.inspect(native, sampler)['my_player_count'], 0)
        native, sampler = self.fixture(actors=0)
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'OBSERVED_PARTIAL')
        self.assertEqual(row['actor_subsystem_count'], 0)
        self.assertIsNone(row['my_player_count'])
        self.assertEqual(row['map_field718'], -1)

    def test_changed_map_invalidates_presence(self):
        native, sampler = self.fixture()
        def mutate(at, size):
            if at == sampler.map_sub + 0x718:
                sampler.put(at, struct.pack('<i', 3))
        sampler.read_hook = mutate
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertIsNone(row['map_context_present'])
        self.assertIsNone(row['my_player_count'])

    def test_vtable_change_is_not_presence(self):
        native, sampler = self.fixture()
        sampler.put(sampler.g['base'] + 0x300, struct.pack('<Q', sampler.g['base'] + 0x1100))
        row = self.inspect(native, sampler)
        self.assertEqual(row['reason'], 'PUBLIC_LAND_VTABLE_SOURCE_CHANGED')
        self.assertIsNone(row['actor_count'])

    def test_large_vector_read_stays_bounded_and_unknown(self):
        native, sampler = self.fixture(count=512)
        row = self.inspect(native, sampler)
        self.assertEqual(row['reason'], 'sample_byte_budget')
        self.assertLessEqual(row['typed_bytes_requested'], land.READ_LIMIT)
        self.assertIsNone(row['my_player_count'])

    def test_wrong_retained_reader_rejected_before_validation(self):
        native, sampler = self.fixture()
        sampler.b = Native()
        row = self.inspect(native, sampler)
        self.assertEqual(row['reason'], 'EXACT_RETAINED_LAND_READER_REQUIRED')
        self.assertEqual(native.validations, 0)

    def test_public_source_is_still_pinned(self):
        self.assertEqual(land.public_contract()['Player']['stride'], 16)

    def test_successor_persists_unknown_probe_and_capture_independently(self):
        native, sampler = self.fixture()
        fake_watch = types.SimpleNamespace(sample=lambda n, s: {'status': 'OBSERVED', 'current': 'Land'})
        fake_probe = types.SimpleNamespace(inspect_attached=lambda n, s: land.empty_result('fixture_read_failure'))
        fake_base = types.SimpleNamespace(parent=helper.parent)
        def loader(path, name):
            if path == helper.BASE:
                return fake_base
            if path == helper.PROBE:
                return fake_probe
            if path == helper.parent.WATCH:
                return fake_watch
            raise AssertionError(path)
        def base_run(candidate, digest, context, metadata, result):
            watch = fake_base.parent.load(helper.parent.WATCH, 'fixture')
            watch.sample(native, sampler)
            watch.sample(native, sampler)
            helper.save(result, {'pid': 1, 'birth': '2', 'land_scene_seen': True})
        fake_base.run = base_run
        with tempfile.TemporaryDirectory() as directory, patch.object(helper.parent, 'load', side_effect=loader), \
                patch.object(helper, 'capture_land_screen', return_value={'status': 'UNKNOWN', 'reason': 'fixture'}) as capture:
            path = Path(directory) / 'auto-ok-result.json'
            helper.run(Path('candidate'), 'digest', Path('context'), Path('metadata'), path)
            row = json.loads(path.read_bytes())
            self.assertEqual(row['land_public_presence']['status'], 'UNKNOWN')
            self.assertEqual(row['land_screen_capture']['status'], 'UNKNOWN')
            self.assertTrue(path.with_name('land-public-presence.json').is_file())
            self.assertEqual(capture.call_count, 1)


if __name__ == '__main__':
    unittest.main()
