"""CP59 fixture-only dormant source-anchor and mandatory-read regression suite."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
reader_path = Path(__file__).with_name('inspect_world.py')
reader_spec = importlib.util.spec_from_file_location('_cp59_world_dormant_fixtures_reader', reader_path)
world = importlib.util.module_from_spec(reader_spec)
reader_spec.loader.exec_module(world)
old_path = ROOT / 'tools/local_native_world_read/tests.py'
if hashlib.sha256(old_path.read_bytes()).hexdigest() != '64776d91002b2ace4c13101c2d6c093a8f5847b3f32d9517acaa7381986c5f3a':
    raise ValueError('CP58_FIXTURES_FROZEN_SOURCE_REQUIRED')
spec = importlib.util.spec_from_file_location('_cp58_fixture_reuse', old_path)
old = importlib.util.module_from_spec(spec)
# The frozen CP58 tests import inspect_world by name. Bind this successor only
# during that file's load, and restore both the module alias and search path.
missing = object()
previous_reader = sys.modules.get('inspect_world', missing)
previous_path = list(sys.path)
sys.modules['inspect_world'] = world
try:
    sys.path.insert(0, str(old_path.parent))
    spec.loader.exec_module(old)
finally:
    sys.path[:] = previous_path
    if previous_reader is missing:
        sys.modules.pop('inspect_world', None)
    else:
        sys.modules['inspect_world'] = previous_reader


class RegionError(Exception):
    def __init__(self, reason='region_not_readable', region=None):
        self.reason = reason
        self.region = region


class WorldRegressionTests(old.Tests):
    pass


class DormantTests(unittest.TestCase):
    def permitted_region(self, size=1):
        return {'state': 0x1000, 'type': 0x1000000, 'image_allocation_matches': True,
                'length_fits': True, 'guard': False, 'protection': 1, 'requested_bytes': size}

    def fixture(self):
        native = old.Native()
        sampler = old.Fixture(native)
        sampler.source['source_checks'] = [{'rva': 0x1000, 'length': 1,
                                           'sha256': hashlib.sha256(b'a').hexdigest()}]
        sampler.put(sampler.g['base'] + 0x1000, b'a')
        return native, sampler

    def inspect(self, native, sampler):
        with patch.object(world, 'contracts', return_value=(sampler.public, sampler.source)):
            return world.inspect_attached(native, sampler)

    def unreadable(self, sampler, at, region=None, reason='region_not_readable'):
        original = sampler.read
        def read(address, size, image=False):
            if address == at:
                sampler.bytes += size
                raise RegionError(reason, self.permitted_region(size) if region is None else region)
            return original(address, size, image)
        sampler.read = read

    def test_exact_dormant_source_anchor_allows_independent_world_observation(self):
        native, sampler = self.fixture()
        self.unreadable(sampler, sampler.g['base'] + 0x1000)
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'OBSERVED')
        self.assertEqual(row['diagnostic']['stage'], 'COMPLETE')
        self.assertEqual(row['diagnostic']['source_anchors_checked'], 1)
        self.assertEqual(row['diagnostic']['source_anchors_dormant'], 1)
        self.assertEqual(row['diagnostic']['source_anchors_readable'], 0)
        self.assertFalse(row['diagnostic']['source_anchors_all_live_hash_verified'])
        self.assertFalse(row['diagnostic']['dormant_is_execution_evidence'])
        self.assertEqual(row['my_player_uid'], 12345)
        self.assertFalse(row['actual_gameplay_proven'])

    def test_readable_source_anchor_is_live_hash_verified(self):
        native, sampler = self.fixture()
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'OBSERVED')
        self.assertEqual(row['diagnostic']['source_anchors_readable'], 1)
        self.assertTrue(row['diagnostic']['source_anchors_all_live_hash_verified'])

    def test_every_region_condition_is_required(self):
        invalid = [('state', 0), ('state', True), ('type', 0x20000),
                   ('image_allocation_matches', False), ('image_allocation_matches', 1),
                   ('length_fits', False), ('guard', True), ('guard', 0),
                   ('protection', 0x101), ('protection', 2), ('protection', True),
                   ('requested_bytes', 2), ('requested_bytes', True)]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                native, sampler = self.fixture()
                region = self.permitted_region()
                region[field] = value
                self.unreadable(sampler, sampler.g['base'] + 0x1000, region)
                row = self.inspect(native, sampler)
                self.assertEqual(row['status'], 'UNKNOWN')
                self.assertEqual(row['diagnostic']['stage'], 'SOURCE_ANCHORS')
                self.assertEqual(row['diagnostic']['source_anchor_index'], 0)
                self.assertEqual(row['diagnostic']['source_anchors_dormant'], 0)
                self.assertIsNone(row['my_player_uid'])

    def test_missing_region_field_is_rejected(self):
        for field in self.permitted_region():
            native, sampler = self.fixture()
            region = self.permitted_region()
            del region[field]
            self.unreadable(sampler, sampler.g['base'] + 0x1000, region)
            self.assertEqual(self.inspect(native, sampler)['status'], 'UNKNOWN')

    def test_other_read_failure_reasons_are_rejected(self):
        for reason in ('region_query_denied', 'region_not_committed_or_short',
                       'RPM_failed_or_partial', 'module_allocation_mismatch'):
            native, sampler = self.fixture()
            self.unreadable(sampler, sampler.g['base'] + 0x1000, reason=reason)
            self.assertEqual(self.inspect(native, sampler)['status'], 'UNKNOWN')

    def test_dormant_metadata_does_not_allow_vtable_read(self):
        native, sampler = self.fixture()
        self.unreadable(sampler, sampler.g['base'] + sampler.source['GameLayer']['rva'])
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(row['diagnostic']['stage'], 'LAND_OBJECTS')
        self.assertEqual(row['diagnostic']['source_anchors_dormant'], 0)
        self.assertIsNone(row['land_game_layer_present'])

    def test_dormant_metadata_does_not_allow_object_read(self):
        native, sampler = self.fixture()
        self.unreadable(sampler, sampler.transform + 0x40)
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(row['diagnostic']['stage'], 'ACTOR_UID_POSITION')
        self.assertIsNone(row['grid_words'])

    def test_live_hash_mismatch_remains_unknown_at_source_stage(self):
        native, sampler = self.fixture()
        sampler.put(sampler.g['base'] + 0x1000, b'b')
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(row['reason'], 'WORLD_RUNTIME_SOURCE_CHANGED')
        self.assertEqual(row['diagnostic']['stage'], 'SOURCE_ANCHORS')
        self.assertEqual(row['diagnostic']['source_anchors_dormant'], 0)

    def test_torn_recheck_is_stage_coded_and_unknown(self):
        native, sampler = self.fixture()
        fired = [False]
        def mutate(at, size):
            if at == sampler.obj + 0x18 and not fired[0]:
                fired[0] = True
                sampler.put(at, struct.pack('<Q', 99))
        sampler.read_hook = mutate
        row = self.inspect(native, sampler)
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(row['diagnostic']['stage'], 'TYPED_RECHECK')
        self.assertIsNone(row['my_player_uid'])

    def test_empty_result_has_no_dormant_success(self):
        row = world.empty_result('NOT_ATTACHED')
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(row['diagnostic']['stage'], 'NOT_INSPECTED')
        self.assertFalse(row['diagnostic']['source_anchors_all_live_hash_verified'])
        self.assertEqual(row['diagnostic']['source_anchors_dormant'], 0)


def run_checks():
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(WorldRegressionTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(DormantTests)])
    labels = [case.id().split('.')[-1] for group in suite for case in group]
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise ValueError('WORLD_DORMANT_FIXTURES_FAILED')
    return labels


if __name__ == '__main__':
    run_checks()
