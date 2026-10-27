"""Offline command/sequence contracts. No game, server, port or input APIs."""
import asyncio
import importlib.util
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import ui_open_commands as ui

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ui_shots_tests_scenario',
    ROOT / 'work/local_original_session/run_ui_shots_scenario.py')
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)


class UIContractsTests(unittest.TestCase):
    identity = dict(pid=17, birth=31, candidate_sha256='a' * 64)

    def fixture(self, request, *, status='RETURNED', reason=0, invoked=True, action='toggle'):
        # Use the actual C++ Output format, so adding a native field breaks this
        # parser test rather than silently drifting between duplicated DTOs.
        source = (ROOT / 'tools/local_original_session/native/ui_open_bridge.hpp').read_text(encoding='utf-8')
        literal = next(line.strip().rstrip(',') for line in source.splitlines()
                       if line.strip().startswith('"{\\"schema\\":\\"own-ui-open-result-v1'))
        template = json.loads(literal)
        template = template.replace('%llu', '%d').replace('%lu', '%d').replace('%u', '%d')
        return json.loads(template % (request['pid'], request['birth'], request['candidate_sha256'],
            request['seq'], request['command'], request['slot'], request['target_uid'],
            status, reason, 'true' if invoked else 'false', action))

    def test_cpp_result_and_request_contract(self):
        request = ui.build_request(self.identity, 7, 'open_magic_window')
        self.assertEqual(list(request), ['schema', 'pid', 'birth', 'candidate_sha256',
                                        'seq', 'command', 'slot', 'target_uid'])
        row = ui.validate_result(self.fixture(request), request)
        self.assertEqual((row['status'], row['action'], row['window_state'], row['effect']),
                         ('RETURNED', 'toggle', 'UNKNOWN', 'UNKNOWN'))
        for field, value in [('seq', 8), ('pid', 18), ('target_uid', 1), ('effect', 'PASS')]:
            changed = self.fixture(request)
            changed[field] = value
            with self.assertRaises(ValueError):
                ui.validate_result(changed, request)

    def test_slot_bounds_and_real_pet_target_required(self):
        self.assertEqual(ui.build_request(self.identity, 1, 'hotbar_cast', 7)['slot'], 7)
        self.assertEqual(ui.build_request(self.identity, 1, 'open_pet_window', target_uid=2**40)['target_uid'], 2**40)
        for command, slot, target in [('hotbar_cast', 8, 0), ('open_magic_window', 1, 0),
                                      ('open_pet_window', 0, 0), ('open_stats_window', 0, 22)]:
            with self.assertRaises(ValueError):
                ui.build_request(self.identity, 1, command, slot, target)

    def test_hotbar_unsupported_is_preserved_without_claiming_cast(self):
        request = ui.build_request(self.identity, 1, 'hotbar_cast', 0)
        row = ui.validate_result(self.fixture(request, status='UNSUPPORTED',
            reason=8, invoked=False, action='none'), request)
        self.assertEqual((row['status'], row['reason'], row['invoked'], row['effect']),
                         ('UNSUPPORTED', 8, False, 'UNKNOWN'))

    def test_original_function_address_table(self):
        source = (ROOT / 'tools/local_original_session/native/ui_open_bridge.hpp').read_text(encoding='utf-8')
        actual = {key: int(value, 16) for key, value in
                  re.findall(r'constexpr uintptr_t (\w+)=0x([0-9a-f]+);', source)}
        self.assertEqual(actual, dict(MagicShortcutRva=0x15EAF0, StatsShortcutRva=0x15EBF0,
            HotbarSubsystemGetterRva=0x9DC8D0, HotbarDispatchRva=0x59B630,
            ActorLookupRva=0x627B0, PetRequestRva=0xB8710))

    def test_retained_request_transport_and_publication(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as tmp:
                posts = []
                async def movement_owner(*args):
                    return True
                owner = SimpleNamespace(child=SimpleNamespace(tid=9), native=SimpleNamespace(
                    u=SimpleNamespace(RegisterWindowMessageW=lambda message: 0xC123)),
                    private_desktop=SimpleNamespace(post_command=lambda *args: posts.append(args) or True))
                consumer = SimpleNamespace(pending=None, _busy=False, _readonly_pending=None,
                    sequence=2, _window=lambda current: 100, reader=SimpleNamespace(owner=owner))
                manual = SimpleNamespace(consumer=consumer, pending=False, _polling=False,
                    _inventory_request=None, _inventory_wait=None)
                current = (SimpleNamespace(broker=SimpleNamespace(_movement_owner=movement_owner), writer=object()),
                    {'operation_lock': asyncio.Lock()}, None, SimpleNamespace(uid=3, map_id=0),
                    None, Path(tmp), self.identity)
                life = tuple(object() for _ in range(6)) + (65537, 3, 0)
                api = ui.UIOpenCommands(manual)
                with patch.object(ui, 'current_kit', return_value=(current, life)):
                    self.assertTrue(await api.request('open_magic_window'))
                    self.assertEqual(len(posts), 1)
                    self.assertFalse(await api.request('open_magic_window'))
                    request = json.loads((Path(tmp) / 'ui-open-request-3.json').read_text())
                    self.assertEqual(request, ui.build_request(self.identity, 3, 'open_magic_window'))
                    pending = ValueError('INPUT_REQUEST_OPEN_FAILED')
                    pending.input_read_metadata = dict(stage='OPEN', winerror=32, same_file=False)
                    with patch.object(ui.commands, '_json', side_effect=pending):
                        self.assertEqual(api.collect()['status'], 'PENDING')
                    self.assertIs(consumer._readonly_pending, api)
                    (Path(tmp) / 'ui-open-result-3.json').write_text(json.dumps(self.fixture(request)))
                    self.assertEqual(api.collect()['status'], 'RETURNED')
                    self.assertIsNone(consumer._readonly_pending)
                    self.assertEqual(consumer.sequence, 3)
        asyncio.run(exercise())

    def test_sequence_order_and_first_failure_preservation(self):
        class Ops:
            def __init__(self, failure=None):
                self.started = []
                self.failure = failure
            async def start(self, kind, name):
                self.started.append((kind, name))
                return True
            async def collect(self, kind, name):
                return (dict(status='REFUSED', reason=42, invoked=False)
                        if name == self.failure else dict(status='OBSERVED' if kind == 'capture' else 'RETURNED'))
        async def exercise():
            good = Ops()
            sequence = scenario.UISequence(good)
            for _ in scenario.STEPS:
                await sequence.tick()
            self.assertTrue(sequence.done)
            self.assertIsNone(sequence.error)
            self.assertEqual(tuple(good.started), scenario.STEPS)
            bad = Ops('talking_scroll')
            sequence = scenario.UISequence(bad)
            for _ in range(10):
                await sequence.tick()
            self.assertEqual(bad.started, list(scenario.STEPS[:3]))
            self.assertEqual(sequence.error['result']['reason'], 42)
            self.assertEqual(len(sequence.results), 3)
        asyncio.run(exercise())

    def test_current_raw133_uid_and_existing_native_use_transport(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as tmp:
                posts = []
                async def movement_owner(*args):
                    return True
                owner = SimpleNamespace(child=SimpleNamespace(tid=9), native=SimpleNamespace(
                    u=SimpleNamespace(RegisterWindowMessageW=lambda message: 0xC456)),
                    private_desktop=SimpleNamespace(post_command=lambda *args: posts.append(args) or True))
                consumer = SimpleNamespace(pending=None, _busy=False, _readonly_pending=None,
                    sequence=22, _window=lambda current: 100, reader=SimpleNamespace(owner=owner))
                manual = SimpleNamespace(consumer=consumer, pending=False, _polling=False,
                    _inventory_request=None, _inventory_wait=None)
                broker = SimpleNamespace(_movement_owner=movement_owner, _inventory_current_frame=b'current-kit')
                current = (SimpleNamespace(broker=broker, writer=object()),
                    {'operation_lock': asyncio.Lock()}, None, SimpleNamespace(uid=3, map_id=0),
                    None, Path(tmp), self.identity)
                life = tuple(object() for _ in range(6)) + (60001, 3, 0)
                # Current issued UID differs from the starter UID; raw133 by
                # itself does not turn another item template into the scroll.
                items = (SimpleNamespace(identifier=60001, template_bits=14, raw_fields={4: 1, 5: 133}),
                    SimpleNamespace(identifier=98765, template_bits=12273, raw_fields={4: 1, 5: 133}))
                api = ui.UIOpenCommands(manual)
                with patch.object(ui, 'current_kit', return_value=(current, life)), \
                     patch.object(ui.inventory, 'validate_kit_frame', return_value=items):
                    self.assertTrue(await api.use_talking_scroll())
                    request = json.loads((Path(tmp) / 'use-item-request.json').read_text())
                    self.assertEqual((request['schema'], request['command'], request['item_identifier']),
                                     ('own-use-item-request-v1', 'UseItem', 98765))
                    reply = dict(request, schema='own-use-item-result-v1', status='RETURNED', reason=0, invoked=True)
                    (Path(tmp) / 'use-item-result-23.json').write_text(json.dumps(reply))
                    result = api.collect()
                    self.assertEqual((result['status'], result['effect'], result['server_commit']),
                                     ('RETURNED', 'UNKNOWN', 'NOT_REQUIRED_CLIENT_LOCAL_UI'))
                    self.assertIsNone(consumer._readonly_pending)
                    self.assertEqual(len(posts), 1)
                    with patch.object(ui.inventory, 'validate_kit_frame', return_value=items[:1]):
                        with self.assertRaisesRegex(ValueError, 'CURRENT_TALKING_SCROLL'):
                            ui.talking_scroll(manual)
        asyncio.run(exercise())

    def test_runtime_staging_preserves_fixed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / 'fixed'
            fixed.mkdir()
            (fixed / 'LC.guard.exe').write_bytes(b'original executable')
            (fixed / 'own-login-bridge-dg49.dll').write_bytes(b'fixed bridge')
            candidate = root / 'candidate.dll'
            candidate.write_bytes(b'candidate bridge')
            old = scenario.launcher.PRODUCTS[scenario.PROFILE]
            original = dict(old, image=fixed / 'LC.guard.exe',
                            bridges={'own-login-bridge-dg49.dll': 'a' * 64}, resource_directory=fixed)
            with patch.dict(scenario.launcher.PRODUCTS, {scenario.PROFILE: original}):
                image, saved = scenario.prepare_runtime(root / 'runtime', candidate)
                self.assertIs(saved, original)
                self.assertEqual(image.read_bytes(), b'original executable')
                self.assertEqual((image.parent / 'own-login-bridge-dg49.dll').read_bytes(), b'candidate bridge')
                self.assertEqual((fixed / 'own-login-bridge-dg49.dll').read_bytes(), b'fixed bridge')
                self.assertEqual(scenario.launcher.PRODUCTS[scenario.PROFILE]['resource_directory'], fixed)


if __name__ == '__main__':
    unittest.main()
