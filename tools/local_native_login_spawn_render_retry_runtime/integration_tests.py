"""CP74 post-stability integration fixtures; no game/process/window APIs."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

h = load(HERE / 'auto_enter_tile_render.py', '_cp74_integration_helper')
adapter = load(h.ADAPTER, '_cp74_integration_frozen_adapter')

class IntegrationTests(unittest.TestCase):
    def fixture(self, root, mode='success', world=None):
        self.world = copy.deepcopy(world or json.loads((ROOT / 'work/local_native_login_spawn_candidate_runtime/world-read-stability.json').read_bytes()))
        identity = dict(self.world['identity'])
        self.native = SimpleNamespace(handle=88, expected=identity, validate=lambda: None)
        self.sampler = object()
        self.events = []
        self.sleeps = []
        self.rect = [0, 0, 200, 100]
        self.result = root / 'result.json'
        (root / 'world-read-stability.json').write_text(json.dumps(self.world), encoding='utf-8')
        def tile(native, sampler, *, expected_uid):
            self.assertIs(native, self.native)
            self.assertIs(sampler, self.sampler)
            self.assertEqual(expected_uid, 1)
            self.events.append('tile')
            return {'status': 'OBSERVED', 'directions': [{'direction': d, 'full_navigation_passability': 'UNKNOWN'} for d in range(8)]}
        def capture(pid, birth, *, hwnd, output, timeout):
            self.assertEqual((pid, birth, hwnd, output, timeout), (identity['pid'], identity['birth'], 777, root / 'render', 6.0))
            self.events.append('wgc')
            if mode == 'capture_exception':
                raise RuntimeError('private pointer must not be printed')
            if mode == 'handle_changed':
                self.native.handle = 99
            count = self.events.count('wgc')
            return {'status': 'UNKNOWN' if mode == 'unknown' or (mode == 'unknown_second' and count == 2) else 'PIXELS_OBSERVED_CONTENT_UNVERIFIED',
                    'report': str(root / ('capture-%s.json' % count)), 'image': None, 'world_visibility_verified': False}
        def snapshot(pid, birth, hwnd):
            self.assertEqual((pid, birth, hwnd), (identity['pid'], identity['birth'], 777))
            return {'hwnd': hwnd, 'thread': 3, 'rect': list(self.rect), 'visible': mode != 'hidden', 'minimized': False}
        def sleep(delay):
            self.sleeps.append(delay)
            if mode == 'rect_changed':
                self.rect = [0, 0, 300, 100]
        render = SimpleNamespace(capture=capture, offscreen=SimpleNamespace(checked_snapshot=snapshot))
        def sequence(native, module, pid, birth, **kwargs):
            self.assertIs(native, self.native)
            self.assertIs(module, render)
            return adapter.sequence(native, module, pid, birth, sleep=sleep, monotonic=lambda: 0.0, **kwargs)
        modules = {h.TILE: SimpleNamespace(inspect_all_attached=tile), h.RENDER: render,
                   h.ADAPTER: SimpleNamespace(sequence=sequence),
                   h.WINDOW: SimpleNamespace(identity=lambda *args: self.events.append('identity'),
                                             windows=lambda pid: [] if mode == 'no_window' else [(1, 777, 200, 100)])}
        self.loader = lambda path, name: modules[path]
    def run_post(self):
        h.post_stability(self.native, self.sampler, self.result, self.loader)
    def row(self, name):
        return json.loads(self.result.with_name(name).read_bytes())
    def test_stable_cp73_one_tile_three_same_owner_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp)); self.run_post()
            self.assertEqual(self.events, ['tile', 'identity', 'wgc', 'wgc', 'wgc'])
            self.assertEqual(self.sleeps, [2.0, 2.0])
            sequence = self.row('render-sequence.json')
            self.assertEqual(sequence['status'], 'THREE_UNVERIFIED_CAPTURES')
            self.assertEqual(self.row('render-capture.json')['capture']['report'], str(Path(tmp) / 'capture-1.json'))
            self.assertEqual(self.row('tile-passability.json')['read_attempts'], 1)
            self.assertFalse(sequence['world_visibility_verified'])
            self.assertFalse(sequence['actual_gameplay_proven'])
    def test_unknown_first_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'unknown'); self.run_post()
            self.assertEqual(self.events.count('wgc'), 1); self.assertEqual(self.sleeps, [])
            self.assertEqual(self.row('render-sequence.json')['status'], 'UNKNOWN')
    def test_unknown_second_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'unknown_second'); self.run_post()
            self.assertEqual(self.events.count('wgc'), 2); self.assertEqual(self.sleeps, [2.0])
    def test_capture_exception_no_additional_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'capture_exception'); self.run_post()
            self.assertEqual(self.events.count('wgc'), 1)
            self.assertEqual(self.row('render-capture.json')['reason'], 'WGC_CAPTURE_EXCEPTION:RuntimeError')
            self.assertNotIn('private pointer', self.result.with_name('render-sequence.json').read_text())
    def test_metadata_change_abort_preserves_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'rect_changed'); self.run_post()
            self.assertEqual(self.events.count('wgc'), 1)
            self.assertEqual(self.row('render-sequence.json')['status'], 'UNKNOWN')
    def test_hidden_exact_window_no_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'hidden'); self.run_post()
            self.assertEqual(self.events.count('wgc'), 0)
    def test_retained_handle_change_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'handle_changed')
            with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_CP73_OBSERVATION_OWNER'):
                self.run_post()
            self.assertEqual(self.events.count('wgc'), 1)
            self.assertEqual(self.row('render-sequence.json')['status'], 'UNKNOWN')
    def test_no_unique_window_no_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), 'no_window'); self.run_post()
            self.assertFalse(self.result.with_name('render-sequence.json').exists())
            self.assertEqual(self.events.count('wgc'), 0)
    def test_unstable_world_never_loads_tile_or_adapter(self):
        world = json.loads((ROOT / 'work/local_native_login_spawn_candidate_runtime/world-read-stability.json').read_bytes())
        world['samples'][-1]['observation']['status'] = 'UNKNOWN'
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(Path(tmp), world=world); self.run_post()
            self.assertEqual(self.events, [])
            self.assertEqual(self.row('tile-passability.json')['read_attempts'], 0)
            self.assertEqual(self.row('render-capture.json')['capture_attempts'], 0)
    def test_create_new_sequence_report_refused_without_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            (root / 'render-sequence.json').write_text('preserve', encoding='utf-8')
            self.run_post()
            self.assertEqual((root / 'render-sequence.json').read_text(), 'preserve')
            self.assertEqual(self.events.count('wgc'), 0)

if __name__ == '__main__':
    unittest.main()
