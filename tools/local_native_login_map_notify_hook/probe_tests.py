"""Injected read-only Map/Environment and bounded stabilization fixtures."""
import importlib.util
import json
import struct
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(path, name):
    paths = sys.path[:]
    try:
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = paths


def run_checks():
    probe = load(ROOT / 'tools/local_native_scene_current/inspect_land_map.py', '_map_probe_fixture')
    checks = []
    public = probe.public_contract()
    class Native:
        def __init__(self):
            self.contract = object()
            self.expected = {'pid': 123, 'birth': '12345'}
            self.handle = object()
            self.validations = 0
        def validate(self):
            self.validations += 1
    class Sampler:
        def __init__(self, native, resolved=0, request=0, header=0, torn=False, bad_bool=False):
            self.b, self.c = native, native.contract
            self.g = {'base': 0x140000000, 'size': 65630208}
            self.bytes = 0
            self.reads = {}
            self.resolved, self.requested, self.header = resolved, request, header
            self.torn, self.bad_bool = torn, bad_bool
            self.actor, self.map, self.environment, self.context, self.state = 0x10000, 0x20000, 0x30000, 0x40000, 0x50000
            self.vfts = {self.actor: self.g['base'] + public['Player']['ActorSubsystem']['rva'],
                         self.map: self.g['base'] + public['Map']['table']['rva'],
                         self.environment: self.g['base'] + public['WorldEnvironment']['owner']['rva']}
            self.fixed_route = [None, [((obj, 1), vft) for obj, vft in self.vfts.items()], {'GameState': self.state}]
        def route(self):
            return self.fixed_route
        def unique(self, nodes, name):
            return self.state
        def scene(self, state):
            return {'current': {'kind': 'Land'}, 'pending': {'kind': 'none'}}, b'S' * 36
        def strong_pair(self, pair):
            return pair
        def pointer(self, address, nullable=False):
            if address in self.vfts:
                return self.vfts[address]
            if address == self.map + public['Map']['context_pointer']:
                return self.context
            raise ValueError('FIXTURE_UNKNOWN_POINTER')
        def read(self, address, size, image=False):
            self.bytes += size
            self.reads[address] = self.reads.get(address, 0) + 1
            if address == self.actor + public['Player']['vector_begin']:
                return b'\0' * 16
            if address == self.map + 0x718:
                return struct.pack('<i', self.resolved)
            if address == self.map + 0x71c:
                return struct.pack('<i', self.requested + (1 if self.torn and self.reads[address] > 1 else 0))
            if address == self.context:
                return struct.pack('<I', self.header)
            if address in (self.environment + 0x88, self.environment + 0x38):
                return b'\2' if self.bad_bool else b'\0'
            if address == self.state + 0x360:
                return b'S' * 36
            raise ValueError('FIXTURE_UNKNOWN_TYPED_READ')
    original_table = probe.table
    probe.table = lambda sampler, row: None
    try:
        native = Native()
        sampler = Sampler(native)
        row = probe.inspect_attached(native, sampler)
        assert row['status'] == 'OBSERVED' and row['map_field71c'] == row['map_field718'] == row['map_context_header_u32'] == 0
        assert row['actor_count'] == row['my_player_count'] == 0 and row['environment_field88_bool'] is False and row['environment_field38_bool'] is False
        assert native.validations == 2 and sampler.reads[sampler.map + 0x71c] == sampler.reads[sampler.context] == 2
        checks.append('same_retained_owner_map71C_718_context_header_environment_and_reread')
        row = probe.inspect_attached(native, Sampler(native, resolved=-1, request=-1, header=0xffffffff))
        assert row['status'] == 'OBSERVED' and row['map_field718'] == -1 and row['map_context_header_u32'] == 0xffffffff
        checks.append('initial_minus1_and_unsigned_FFFFFFFF_preserved_no_zero_inference')
        row = probe.inspect_attached(native, Sampler(native, torn=True))
        assert row['status'] == 'UNKNOWN' and row['map_field71c'] is None and row['map_field718'] is None
        checks.append('torn_map_request_reread_becomes_unknown_all_values_cleared')
        row = probe.inspect_attached(native, Sampler(native, bad_bool=True))
        assert row['status'] == 'UNKNOWN' and row['environment_field88_bool'] is None
        checks.append('noncanonical_environment_bool_refused_unknown')
        sampler = Sampler(native)
        sampler.b = object()
        row = probe.inspect_attached(native, sampler)
        assert row['status'] == 'UNKNOWN' and row['map_field71c'] is None
        checks.append('foreign_retained_sampler_refused_before_map_read')
    finally:
        probe.table = original_table
    helper = load(ROOT / 'tools/local_native_auto_login/auto_enter_land_probe_map.py', '_map_stability_fixture')
    compile(helper.land_stability_tree(), str(helper.LAND), 'exec')
    checks.append('frozen_first_Land_capture_boundary_then_bounded_stability_hook')
    class Clock:
        def __init__(self):
            self.elapsed = 0
            self.sleeps = []
        def monotonic(self):
            return self.elapsed
        def sleep(self, seconds):
            assert seconds == 1.0
            self.elapsed += seconds
            self.sleeps.append(seconds)
    with tempfile.TemporaryDirectory(prefix='cp56-map-probe-fixture-') as directory:
        result = Path(directory) / 'auto-ok-result.json'
        metadata = Path(directory) / 'packet-metadata.jsonl'
        metadata.write_text(json.dumps({'event': 'reply_sent', 'opcode': 0x4e95, 'frame_size': 14}) + '\n', encoding='utf-8')
        clock = Clock()
        original_time, original_load = helper.time, helper.parent.load
        observations = []
        def observed(native, sampler):
            observations.append(1)
            return {'status': 'OBSERVED', 'map_field71c': 0, 'map_field718': 0, 'map_context_header_u32': 0,
                    'actor_count': 0, 'my_player_count': 0, 'actual_gameplay_proven': False}
        fake_probe = types.SimpleNamespace(inspect_attached=observed, empty_result=lambda reason: {'status': 'UNKNOWN', 'reason': reason})
        helper.time, helper.parent.load = clock, lambda *args: fake_probe
        try:
            native = Native()
            helper.observe_map(native, object(), lambda *args: {'status': 'OBSERVED', 'current': 'Land'}, metadata, result)
            row = json.loads(result.with_name('map-stability.json').read_bytes())
            assert len(observations) == len(row['samples']) == 5 and clock.sleeps == [1.0] * 4
            assert all(item['map_reply_metadata_seen'] for item in row['samples']) and row['world_ready_claim'] is False
            checks.append('five_one_second_samples_same_handle_MAP_metadata_no_world_claim')
            try:
                helper.observe_map(native, object(), lambda *args: {'status': 'OBSERVED', 'current': 'Land'}, metadata, result)
                raise AssertionError('STABILITY_OVERWRITTEN')
            except ValueError:
                pass
            checks.append('stability_output_CREATE_NEW_no_overwrite')
        finally:
            helper.time, helper.parent.load = original_time, original_load
    return checks


if __name__ == '__main__':
    rows = run_checks()
    print(json.dumps({'status': 'PASS_MAP_PROBE_AND_STABILITY_FIXTURES', 'checks': rows,
                      'actual_Native_game_slot_actions': 0}))
