"""Fake-only command transport checks; no native process, port or UI APIs."""
import ctypes as C
from contextlib import contextmanager, ExitStack
import os
from ctypes import wintypes as W
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import commands as c


class Fn:
    def __init__(self, callback): self.callback = callback
    def __call__(self, *args): return self.callback(*args)


class CommandsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.boundary = self.directory / 'native'
        self.boundary.mkdir()
        self.posts = []
        child = SimpleNamespace(pid=7, process=101, job=202, identity=dict(birth='303'))
        def thread(hwnd, pid):
            C.cast(pid, C.POINTER(W.DWORD)).contents.value = child.pid
            return 44
        self.owner = SimpleNamespace(closed=False, child=child, owner_handle=101, owner_job=202,
            image_sha='a' * 64, directory=self.boundary, validate=lambda child: True,
            private_desktop=SimpleNamespace(contains=lambda hwnd: hwnd == 500),
            native=SimpleNamespace(owned_hwnd=lambda child, hwnd: hwnd == 500,
                u=SimpleNamespace(RegisterWindowMessageW=Fn(lambda name: 0xc123),
                    IsWindow=Fn(lambda hwnd: hwnd == 500), GetWindowThreadProcessId=Fn(thread),
                    PostMessageW=Fn(lambda *args: self.posts.append(args) or True))))
        self.dispatches = []
        def dispatch(owner, identity, hwnd, thread_id, message, sequence):
            self.dispatches.append((owner, identity, hwnd, thread_id, message, sequence))
            self.assertTrue(owner.private_desktop.contains(hwnd))
            self.assertTrue(owner.validate(child))
            return bool(owner.native.u.PostMessageW(hwnd, message, sequence, 0))
        self.owner.private_desktop.post_command = dispatch
        self.identity = dict(pid=7, birth=303, candidate_sha256='a' * 64)
        (self.boundary / 'command-bridge.json').write_text(json.dumps(dict(
            **self.identity, ready=True, message=0xc123, window=500, thread_id=44, supported_commands=[1, 2])))
        self.handler = c.CommandRequests(self.directory, self.owner)

    def request(self, **changes):
        row = dict(schema=c.REQUEST_SCHEMA, sequence=1, command='LoginOK', uid=0, x=0, y=0)
        row.update(changes)
        self.handler.request.write_text(json.dumps(row))

    def native_result(self, **changes):
        row = dict(schema='own-internal-command-result-v1', **self.identity,
                   seq=1, command=1, status='RETURNED', reason=0, invoked=True)
        row.update(changes)
        (self.boundary / 'command-result.json').write_text(json.dumps(row))

    def health(self, phase='ready', **changes):
        row = dict(schema='own-lifecycle-integrity-v1', **self.identity, phase=phase,
            baseline_after_commit=True, guard_physical=17, guard_signature_matched=17,
            guard_signature_mismatched=0, guard_signature_unknown=0, lifecycle_logical=8,
            lifecycle_physical=4, lifecycle_signature_matched=4, lifecycle_signature_mismatched=0,
            lifecycle_signature_unknown=0, logger_calls=0,
            entered_k32_w_a_exit_kb_w_a_exit_k32_kb_terminate=[0] * 8)
        row.update(changes)
        (self.boundary / ('lifecycle-health-' + phase + '.json')).write_text(json.dumps(row))
        return row

    def test_required_health_missing_or_busy_waits_without_consuming_request_then_posts(self):
        self.owner.require_lifecycle_health = True
        self.request()
        self.assertIsNone(self.handler.poll())
        self.assertEqual(self.handler.last_sequence, 0)
        self.assertFalse(self.handler.result.exists())
        self.health()
        with patch.object(c, '_read', side_effect=ValueError('INPUT_REQUEST_OPEN_FAILED')), \
             patch.object(c.C, 'get_last_error', return_value=32):
            self.assertIsNone(self.handler.poll())
        with patch.object(c, '_read', side_effect=ValueError('INPUT_REQUEST_CHANGED')):
            self.assertIsNone(self.handler.poll())
        self.assertFalse(self.posts)
        self.assertEqual(self.handler.poll()['status'], 'QUEUED')
        self.assertEqual(len(self.posts), 1)

    def test_required_health_identity_malformed_boolean_and_failed_counts_never_post(self):
        self.owner.require_lifecycle_health = True
        self.request()
        for changes in (dict(pid=8), dict(birth=True), dict(baseline_after_commit=1),
                        dict(guard_physical=True), dict(guard_signature_matched=5, guard_signature_mismatched=12),
                        dict(guard_signature_unknown=1), dict(lifecycle_logical=True),
                        dict(lifecycle_physical=3), dict(lifecycle_signature_matched=3),
                        dict(lifecycle_signature_unknown=1)):
            with self.subTest(fields=tuple(changes)):
                self.health(**changes)
                with self.assertRaises(c.IntegrityFailure): self.handler.poll()
        (self.boundary / 'lifecycle-health-ready.json').write_text('{')
        with self.assertRaisesRegex(c.IntegrityFailure, 'COMMAND_INTEGRITY_HEALTH_MALFORMED'):
            self.handler.poll()
        self.assertFalse(self.posts)
        self.assertEqual(self.handler.last_sequence, 0)

    def test_late_health_and_final_prepost_recheck_fail_closed_legacy_unchanged(self):
        # Legacy profiles do not consume even a malformed health file.
        (self.boundary / 'lifecycle-health-ready.json').write_text('{')
        self.assertEqual(self.handler.checked_health()['status'], 'NOT_REQUIRED')
        self.owner.require_lifecycle_health = True
        self.health(); self.health('late', lifecycle_signature_mismatched=1)
        with self.assertRaises(c.IntegrityFailure): self.handler.checked_health()
        self.health('late', lifecycle_physical=8, lifecycle_signature_matched=8)
        self.assertEqual(self.handler.checked_health()['status'], 'VERIFIED')
        self.request()
        original = self.handler._ready
        checks = []
        def ready(identity):
            result = original(identity); checks.append(1)
            if len(checks) == 2: self.health(guard_signature_unknown=1)
            return result
        with patch.object(self.handler, '_ready', side_effect=ready):
            with self.assertRaises(c.IntegrityFailure): self.handler.poll()
        self.assertFalse(self.posts)
        self.assertEqual(self.handler.last_sequence, 1)  # Durable claim is never replayed.

    def test_canonical_identity_request_and_seq_only_owned_post(self):
        self.request()
        self.assertEqual(self.handler.poll()['status'], 'QUEUED')
        request = json.loads((self.boundary / 'command-request.json').read_bytes())
        self.assertEqual(list(request), ['schema', 'pid', 'birth', 'candidate_sha256', 'seq', 'command', 'uid', 'x', 'y'])
        self.assertEqual(request, dict(schema='own-internal-command-v1', **self.identity,
                                      seq=1, command=1, uid=0, x=0, y=0))
        self.assertEqual(self.posts, [(500, 0xc123, 1, 0)])
        self.assertEqual(len(self.dispatches), 1)
        self.assertEqual(self.dispatches[0][2:], (500, 44, 0xc123, 1))
        self.native_result()
        result = self.handler.poll()
        self.assertEqual(result['status'], 'RETURNED')
        self.assertTrue(result['invoked'])
        self.assertTrue(result['native_ui_thread_conditional'])
        self.assertEqual(result['ui_result'], 'UNKNOWN')

    def test_pending_poll_and_handler_reload_never_repost_or_overwrite(self):
        self.request(); self.handler.poll()
        self.request(sequence=2, command='Select')
        second = c.CommandRequests(self.directory, self.owner)
        for _ in range(3): self.assertIsNone(second.poll())
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(json.loads((self.boundary / 'command-request.json').read_bytes())['seq'], 1)
        self.native_result()
        self.assertEqual(second.poll()['status'], 'RETURNED')
        self.assertEqual(second.poll()['status'], 'QUEUED')
        self.assertEqual(self.posts[-1], (500, 0xc123, 2, 0))

    def test_consumed_sequence_and_external_identity_fields_never_dispatch(self):
        self.request(pid=999)
        self.assertEqual(self.handler.poll()['reason'], 'COMMAND_REQUEST_SCHEMA_REQUIRED')
        self.request()
        self.assertEqual(self.handler.poll()['reason'], 'COMMAND_SEQUENCE_ALREADY_CONSUMED')
        self.assertFalse(self.posts)

    def test_bounds_and_nonzero_unused_fields_are_refused(self):
        for sequence, changes in enumerate((dict(x=True), dict(y=1), dict(command='Pointer', x=0),
                dict(command='MoveGoal', x=1 << 31)), 1):
            self.request(sequence=sequence, **changes)
            self.assertEqual(self.handler.poll()['status'], 'REFUSED')
        self.assertFalse(self.posts)

    def test_owner_desktop_or_ready_identity_loss_never_posts(self):
        self.owner.private_desktop.contains = lambda hwnd: False
        self.request()
        self.assertEqual(self.handler.poll()['reason'], 'COMMAND_PRIVATE_DESKTOP_WINDOW_REQUIRED')
        self.owner.private_desktop.contains = lambda hwnd: True
        self.owner.validate = lambda child: False
        self.request(sequence=2)
        self.assertEqual(self.handler.poll()['reason'], 'COMMAND_OWNER_LOST')
        self.assertFalse(self.posts)

    def test_native_identity_mismatch_and_bool_confusion_are_not_execution_proof(self):
        self.request(); self.handler.poll()
        self.native_result(pid=999)
        self.assertEqual(self.handler.poll()['reason'], 'COMMAND_RESULT_IDENTITY_MISMATCH')
        self.request(sequence=2); self.handler.poll()
        self.native_result(seq=2, invoked=1)
        self.assertEqual(self.handler.poll()['reason'], 'COMMAND_NATIVE_RESULT_INVALID')
        self.assertEqual(len(self.posts), 2)

    def test_claim_failure_prevents_any_native_request_or_post(self):
        self.request()
        with patch.object(c, '_atomic', side_effect=OSError('fixture')):
            with self.assertRaises(OSError): self.handler.poll()
        self.assertTrue(self.handler.disabled)
        self.assertFalse(self.posts)
        self.assertFalse((self.boundary / 'command-request.json').exists())

    def test_quit_and_move_unknown_contract_are_explicit_native_results(self):
        result = self.handler.request_quit()
        self.assertEqual(result['status'], 'QUEUED')
        self.native_result(command=3, status='UNSUPPORTED', reason=8, invoked=False)
        result = self.handler.poll()
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertFalse(result['invoked'])
        self.request(sequence=2, command='MoveGoal', uid=1, x=100, y=200)
        self.assertEqual(self.handler.poll()['status'], 'QUEUED')
        self.assertEqual(json.loads((self.boundary / 'command-request.json').read_bytes())['command'], 4)


    def test_default_result_real_sharing_error_disables_without_command_or_retry(self):
        held = ObservationAtomicTests.held_without_share_delete
        c._atomic(self.handler.result, {'status': 'OLD'}, 2048)
        replace = c.os.replace
        def blocked(source, target):
            with held(self, source): return replace(source, target)
        with patch.object(c.os, 'replace', blocked) as unused:
            with self.assertRaises(OSError) as error: self.handler._record({'status': 'CLAIMED'})
        self.assertEqual(error.exception.winerror, 32)
        self.assertTrue(self.handler.disabled)
        self.assertIsNone(self.handler.poll())
        self.assertFalse(self.posts or self.dispatches)
        self.assertFalse((self.boundary / 'command-request.json').exists())
        self.assertEqual(json.loads(self.handler.result.read_text()), {'status': 'OLD'})


class ObservationAtomicTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / 'observation.json'

    @contextmanager
    def held_without_share_delete(self, path):
        if os.name != 'nt': self.skipTest('requires actual Windows file sharing')
        kernel = C.WinDLL('kernel32', use_last_error=True)
        create, close = kernel.CreateFileW, kernel.CloseHandle
        create.argtypes = (W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE)
        create.restype = W.HANDLE
        close.argtypes, close.restype = (W.HANDLE,), W.BOOL
        handle = create(str(path), 0x80000000, 3, None, 3, 0x80, None)
        if handle in (None, C.c_void_p(-1).value): raise C.WinError(C.get_last_error())
        try:
            yield
        finally:
            if not close(handle): raise C.WinError(C.get_last_error())

    def test_original_windows_replace_failure_leaves_temp_then_file_exists(self):
        c._atomic(self.path, {'tick': 0}, 4096)
        with self.held_without_share_delete(self.path):
            with self.assertRaises(OSError) as first:
                c._atomic(self.path, {'tick': 1}, 4096)
            self.assertEqual(first.exception.winerror, 5)
            self.assertTrue(self.path.with_name(self.path.name + '.tmp').is_file())
            with self.assertRaises(FileExistsError) as second:
                c._atomic(self.path, {'tick': 2}, 4096)
        self.assertEqual(json.loads(self.path.read_text()), {'tick': 0})
        evidence = Path(__file__).resolve().parents[2] / 'work/local_original_session/integration-1/observation-atomic-fix'
        (evidence / 'old-windows-reproduction.json').write_text(json.dumps(dict(
            first_type=type(first.exception).__name__, first_errno=first.exception.errno,
            first_winerror=first.exception.winerror, second_type=type(second.exception).__name__,
            second_errno=second.exception.errno, second_winerror=second.exception.winerror,
            target_still_old=True, stale_fixed_temp=True, native_or_request_calls=0), indent=2)+'\n')


    def test_original_real_source_temp_read_sharing_failure_then_file_exists(self):
        replace = c.os.replace
        def held_replace(source, target):
            with self.held_without_share_delete(source):
                return replace(source, target)
        c._atomic(self.path, {'tick': 0}, 4096)
        with patch.object(c.os, 'replace', held_replace):
            with self.assertRaises(OSError) as first:
                c._atomic(self.path, {'tick': 1}, 4096)
        self.assertEqual(first.exception.winerror, 32)
        self.assertTrue(self.path.with_name(self.path.name + '.tmp').is_file())
        with self.assertRaises(FileExistsError): c._atomic(self.path, {'tick': 2}, 4096)
        evidence = Path(__file__).resolve().parents[2] / 'work/local_original_session/integration-1/observation-atomic-fix'
        (evidence / 'old-source-sharing-reproduction.json').write_text(json.dumps(dict(
            first_type=type(first.exception).__name__, errno=first.exception.errno,
            winerror=first.exception.winerror, stale_fixed_temp=True,
            second_type='FileExistsError', native_or_request_calls=0), indent=2)+'\n')


    def test_observation_real32_defer_keeps_unique_locked_temp_then_latest_save_succeeds(self):
        c._atomic(self.path, {'tick': 0}, 4096)
        replace = c.os.replace
        held_sources = []
        with ExitStack() as readers:
            def blocked(source, target):
                held_sources.append(source)
                readers.enter_context(self.held_without_share_delete(source))
                return replace(source, target)
            with patch.object(c.os, 'replace', side_effect=blocked) as rename:
                self.assertIs(c._atomic(self.path, {'tick': 1}, 4096, output_only=True), False)
            self.assertEqual(rename.call_count, 5)
            self.assertEqual(held_sources, [held_sources[0]] * 5)
            self.assertTrue(held_sources[0].exists())  # Cleanup tried but the actual handle still denies delete.
            self.assertEqual(json.loads(self.path.read_text()), {'tick': 0})
        self.assertIs(c._atomic(self.path, {'tick': 2}, 4096, output_only=True), True)
        self.assertEqual(json.loads(self.path.read_text()), {'tick': 2})
        self.assertFalse(self.path.with_name(self.path.name + '.tmp').exists())
        self.assertEqual(list(self.directory.glob('*.tmp')), [held_sources[0]])
        self.assertFalse((self.directory / 'command.request.json').exists())

    def test_real_target_access5_stays_fatal_and_cleans_only_created_temp(self):
        c._atomic(self.path, {'tick': 0}, 4096)
        with self.held_without_share_delete(self.path):
            with self.assertRaises(OSError) as error:
                c._atomic(self.path, {'tick': 1}, 4096, output_only=True)
        self.assertEqual(error.exception.winerror, 5)
        self.assertEqual(list(self.directory.glob('*.tmp')), [])
        self.assertEqual(json.loads(self.path.read_text()), {'tick': 0})

    def test_exact_bool_bounds_and_other_io_refuse_and_33_only_defers(self):
        for flag in (None, 0, 1, 'True'):
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'OUTPUT_ONLY_BOOL_REQUIRED'):
                c._atomic(self.path, {}, 2048, output_only=flag)
        for limit in (2048, 4096):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, 'BYTE_BOUND'):
                c._atomic(self.path, {'x': 'x' * limit}, limit, output_only=True)
        self.assertEqual(list(self.directory.iterdir()), [])
        for primary in (PermissionError(13, 'ordinary denied'), C.WinError(5), OSError(28, 'disk full')):
            with self.subTest(error=str(primary)), patch.object(c.os, 'replace', side_effect=primary) as rename:
                with self.assertRaises(OSError) as raised:
                    c._atomic(self.path, {'tick': 1}, 4096, output_only=True)
                self.assertIs(raised.exception, primary)
                self.assertEqual(rename.call_count, 5 if getattr(primary, 'winerror', None) == 5 else 1)
            self.assertEqual(list(self.directory.iterdir()), [])
        with patch.object(c.os, 'replace', side_effect=C.WinError(33)) as rename:
            self.assertIs(c._atomic(self.path, {'tick': 1}, 4096, output_only=True), False)
        self.assertEqual(rename.call_count, 5)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_foreign_unique_temp_collision_is_fatal_and_never_deleted(self):
        fixed = c.uuid.UUID(int=1)
        foreign = self.path.with_name(self.path.name + '.' + fixed.hex + '.tmp')
        foreign.write_bytes(b'foreign unique file')
        legacy = self.path.with_name(self.path.name + '.tmp'); legacy.write_bytes(b'foreign legacy file')
        with patch.object(c.uuid, 'uuid4', return_value=fixed), patch.object(c.os, 'replace') as rename:
            with self.assertRaises(FileExistsError): c._atomic(self.path, {}, 4096, output_only=True)
        rename.assert_not_called()
        self.assertEqual(foreign.read_bytes(), b'foreign unique file')
        self.assertEqual(legacy.read_bytes(), b'foreign legacy file')

    def test_first_io_error_survives_cleanup_failure_and_foreign_replacement(self):
        primary = OSError(13, 'first replace refused')
        with patch.object(c.os, 'replace', side_effect=primary), \
             patch.object(Path, 'unlink', side_effect=OSError(5, 'cleanup refused')):
            with self.assertRaises(OSError) as error: c._atomic(self.path, {}, 4096, output_only=True)
        self.assertIs(error.exception, primary)
        self.assertEqual(len(list(self.directory.glob('*.tmp'))), 1)
        foreign = []
        def swapped(source, target):
            source.rename(source.with_suffix('.preserved'))
            source.write_bytes(b'foreign replacement'); foreign.append(source)
            raise primary
        with patch.object(c.os, 'replace', swapped):
            with self.assertRaises(OSError) as error: c._atomic(self.path, {}, 4096, output_only=True)
        self.assertIs(error.exception, primary)
        self.assertEqual(foreign[0].read_bytes(), b'foreign replacement')

    def test_write_error_survives_stream_close_error_and_owned_temp_is_cleaned(self):
        primary = OSError(28, 'first write refused')
        opened = Path.open
        def failed_open(path, *args, **kwargs):
            stream = opened(path, *args, **kwargs)
            def write(raw): raise primary
            def close():
                stream.close(); raise OSError(5, 'secondary close failure')
            return SimpleNamespace(fileno=stream.fileno, write=write, flush=stream.flush, close=close)
        with patch.object(Path, 'open', failed_open):
            with self.assertRaises(OSError) as error: c._atomic(self.path, {}, 4096, output_only=True)
        self.assertIs(error.exception, primary)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_real_runner_save_defers_only_output_and_later_saves_latest(self):
        import asyncio
        import importlib.util
        root = Path(__file__).resolve().parents[2]
        path = root / 'work/local_original_session/run_manual_baseline_scenario.py'
        spec = importlib.util.spec_from_file_location('observation_atomic_scenario', path)
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        owner = SimpleNamespace(product=runner.PROFILE, image_sha=runner.IMAGE_SHA,
                                internal=False, private_desktop=None)
        monitor = SimpleNamespace(directory=self.directory, reader=object())
        stop = asyncio.Event()
        scenario = runner.Scenario(owner, monitor, stop, 60)
        scenario.save()
        previous = scenario.path.read_bytes()
        replace = c.os.replace
        with ExitStack() as readers:
            def blocked(source, target):
                readers.enter_context(self.held_without_share_delete(source))
                return replace(source, target)
            scenario.stage = 'WAITING'
            with patch.object(c.os, 'replace', side_effect=blocked) as rename: scenario.save()
            self.assertEqual(rename.call_count, 5)
            self.assertEqual(scenario.path.read_bytes(), previous)
        scenario.stage = 'LATEST'
        scenario.save()
        self.assertEqual(json.loads(scenario.path.read_text())['stage'], 'LATEST')
        self.assertIsNone(scenario.error); self.assertFalse(stop.is_set())
        self.assertEqual(scenario.actions, [])
        self.assertFalse((self.directory / 'command.request.json').exists())
