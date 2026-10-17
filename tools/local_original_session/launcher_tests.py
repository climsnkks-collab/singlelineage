"""Launcher-only fixtures: no game, broker listeners, UAC or native process."""
import asyncio
import copy
import ctypes as C
from pathlib import Path
from types import SimpleNamespace
import unittest
import contextlib
import io
import json
import socket
import struct
import tempfile
import threading
import types
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from tools.local_original_session import launcher as l
from tools.local_original_session import observe as obs


class FakeOwner:
    def __init__(self, rows=None):
        self.events = []
        self.rows = iter(rows or [True])
        self.last = True
        self.closed = False
    def prepare(self):
        self.events.append('prepare')
        return dict(pid=11, birth=22)
    def resume(self): self.events.append('resume')
    def tick(self):
        self.last = next(self.rows, self.last)
        return self.last
    def request_close(self):
        self.events.append('wm_close')
        return 1
    def close(self):
        self.events.append('cleanup')
        self.closed = True
        return dict(positive_exit=True, owned_job_empty=True)


class FakeBroker:
    def __init__(self, owner, fail_start=False, fail_close=False):
        self.owner = owner
        self.failure = asyncio.Event()
        self.fail_start, self.fail_close = fail_start, fail_close
    async def start(self):
        self.owner.events.append('broker_start')
        if self.fail_start: raise ValueError('START_FAILED')
    async def close(self):
        self.owner.events.append('broker_close_save')
        if self.fail_close: raise ValueError('CLOSE_FAILED')
        return dict(cleanup_complete=True)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_source_quit_host_binds_after_features_and_closes_after_two_phase_poll(self):
        for close_error in (False, True):
            events = []
            owner = FakeOwner([True, True, True, False])
            broker = FakeBroker(owner)
            manual = object()
            features = SimpleNamespace(manual=manual, close=lambda: events.append('features_close'))
            async def feature_poll(monitor):
                events.append('feature_poll')
                return {}
            features.poll = feature_poll
            def factory(current):
                self.assertIs(current, broker)
                self.assertEqual(owner.events, ['prepare', 'broker_start'])
                events.append('features_bind')
                return features
            class Adapter:
                def __init__(adapter, actual_owner, requests, actual_broker, directory):
                    self.assertIs(actual_owner, owner); self.assertIs(requests, manual)
                    self.assertIs(actual_broker, broker); self.assertEqual(directory, 'explicit-run')
                    self.assertNotIn('resume', owner.events)
                    events.append('source_bind')
                    adapter.returned = False
                def start(adapter, count):
                    self.assertEqual(owner.events[-1], 'wm_close')
                    self.assertEqual(count, 1)
                    self.assertNotIn('features_close', events)
                    events.append('source_start')
                    return adapter.report()
                def poll(adapter):
                    self.assertNotIn('features_close', events)
                    self.assertNotIn('broker_close_save', owner.events)
                    events.append('source_poll')
                    adapter.returned = True
                    return adapter.report()
                def report(adapter):
                    return dict(status='RETURNED' if adapter.returned else 'PENDING',
                        first_returned=adapter.returned, normal_exit_verified=False)
                def close(adapter):
                    events.append('source_close')
                    if close_error: raise ValueError('FIXTURE_CLOSE_ERROR')
            from tools.local_original_session import manual_source_quit
            with patch.object(manual_source_quit, 'SourceQuitRequests', Adapter):
                report = await l.run_session(owner, lambda _: broker, asyncio.Event(),
                    poll_seconds=0, test_duration=0, close_grace_seconds=1, feature_factory=factory,
                    source_quit_directory='explicit-run')
            self.assertEqual(events, ['features_bind', 'source_bind', 'feature_poll', 'source_start',
                                      'source_poll', 'source_poll', 'source_close', 'features_close'])
            self.assertTrue(report['source_quit']['first_returned'])
            self.assertFalse(report['normal_exit_verified'])
            self.assertEqual(owner.events[-2:], ['broker_close_save', 'cleanup'])
            self.assertEqual(report.get('source_quit_close_error'), 'ValueError' if close_error else None)

    async def test_source_quit_start_uses_existing_close_deadline_without_extending_grace(self):
        from tools.local_original_session import manual_source_quit
        now, polls = [0.0], []
        owner = FakeOwner()
        async def feature_poll(monitor): return {}
        features = SimpleNamespace(manual=object(), poll=feature_poll, close=Mock())
        class Adapter:
            def __init__(adapter, *args): pass
            def report(adapter): return dict(status='PENDING', first_returned=False)
            def start(adapter, count):
                self.assertEqual(owner.events[-1], 'wm_close')
                now[0] += 11  # Existing private helper can consume synchronous time.
                return adapter.report()
            def poll(adapter):
                polls.append(True)
                now[0] += 11
                return adapter.report()
            def close(adapter): pass
        with patch.object(manual_source_quit, 'SourceQuitRequests', Adapter),                 patch.object(l.time, 'monotonic', lambda: now[0]):
            report = await l.run_session(owner, FakeBroker, asyncio.Event(),
                test_duration=0, poll_seconds=0, close_grace_seconds=10,
                feature_factory=lambda broker: features, source_quit_directory='explicit')
        self.assertEqual(polls, [])
        self.assertEqual(report['close_wait_end'], 'GRACE_EXPIRED')
        self.assertEqual(report['product_lifetime_seconds'], 11)
        self.assertEqual(owner.events[-2:], ['broker_close_save', 'cleanup'])

    async def test_feature_failure_normal_close_requires_current_source_owner_and_preserves_error(self):
        for mode in ('valid', 'source', 'owner', 'changed', 'broker'):
            owner = FakeOwner([True, True, False])
            child = SimpleNamespace(pid=11, process=101, job=102, members={})
            child.members[11] = child
            owner.child, owner.owner_handle, owner.owner_job = child, 101, 102
            def sources():
                if mode == 'source': raise ValueError('FIXTURE_SOURCE_CHANGED')
            def key_guard():
                if mode == 'changed': owner.owner_handle = 103
                return mode != 'owner'
            owner.verify_sources, owner.key_guard = sources, key_guard
            owner.validate = lambda member: member is child
            broker = FakeBroker(owner)
            async def failed_poll(_):
                if mode == 'broker': broker.failure.set()
                raise ValueError('FEATURE_STRICT_UNKNOWN')
            runtime = SimpleNamespace(poll=failed_poll, close=Mock())
            closing = []
            class Monitor:
                def bind(self, target): pass
                def tick(self, source, state=None, **kw):
                    if state == 'CLOSING':
                        self_outer.assertNotIn('broker_close_save', owner.events)
                        closing.append(state)
                def close(self): pass
                def finish(self, report): pass
            self_outer = self
            result = await l.run_session(owner, lambda _: broker, asyncio.Event(),
                poll_seconds=0, close_grace_seconds=1, monitor=Monitor(), feature_factory=lambda _: runtime)
            with self.subTest(mode=mode):
                self.assertEqual((result['reason'], result['error_type'], result['error']),
                                 ('SESSION_FAILURE', 'ValueError', 'FEATURE_STRICT_UNKNOWN'))
                self.assertEqual(result['session_failure_close']['attempted'], mode == 'valid')
                self.assertEqual(owner.events.count('wm_close'), int(mode == 'valid'))
                if mode == 'valid':
                    self.assertEqual(closing, ['CLOSING'])
                    self.assertEqual(result['close_wait_end'], 'NATIVE_EXIT')
                    self.assertIsNone(result['session_failure_close']['refusal_reason'])
                else:
                    reasons = dict(source='FIXTURE_SOURCE_CHANGED', owner='SESSION_CLOSE_CURRENT_PRIMARY_REQUIRED',
                        changed='SESSION_CLOSE_PRIMARY_CHANGED', broker='SESSION_CLOSE_BROKER_ALREADY_FAILED')
                    self.assertEqual(result['session_failure_close']['refusal_reason'], reasons[mode])
                    self.assertEqual(closing, [])
                self.assertEqual(owner.events[-2:], ['broker_close_save', 'cleanup'])
                self.assertTrue(owner.closed)

    async def test_source_quit_outcome_is_classified_after_final_owned_cleanup(self):
        fixture = ExitOutcomeTests.source_report()
        class Owner(FakeOwner):
            def close(self):
                super().close()
                return fixture['cleanup']
        class Broker(FakeBroker):
            async def close(self):
                await super().close()
                return fixture['broker']
        owner = Owner([False])
        owner.prepare = lambda: fixture['primary']
        result = await l.run_session(owner, Broker, asyncio.Event(), poll_seconds=0)
        self.assertTrue(owner.closed)
        self.assertTrue(result['normal_exit_verified'])
        self.assertEqual(result['game_logout_protocol'], 'SOURCE_QUIT_DRAIN_EOF_EXIT0')
    async def test_natural_exit_has_no_timeout_or_close_input(self):
        owner = FakeOwner([True, False])
        result = await l.run_session(owner, FakeBroker, asyncio.Event(), poll_seconds=0)
        self.assertEqual(result['reason'], 'NATIVE_EXIT')
        self.assertEqual(owner.events, ['prepare', 'broker_start', 'resume', 'broker_close_save', 'cleanup'])
    async def test_native_exit_allows_bounded_terminal_join_before_broker_cancel(self):
        for cancelled in (False, True):
            class Broker(FakeBroker):
                async def join_quit_exit(self):
                    self.owner.events.append('quit_terminal_join')
                    if cancelled: raise asyncio.CancelledError()
                    return dict(eligible=1, joined=1)
            owner = FakeOwner([False])
            result = await l.run_session(owner, Broker, asyncio.Event(), poll_seconds=0)
            self.assertEqual(owner.events[-3:], ['quit_terminal_join', 'broker_close_save', 'cleanup'])
            if cancelled:
                self.assertEqual(result['quit_terminal_join']['status'], 'UNKNOWN')
            else:
                self.assertEqual(result['quit_terminal_join'], dict(eligible=1, joined=1))
    async def test_explicit_user_exit_requests_native_close_before_broker_cleanup(self):
        owner = FakeOwner()
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, FakeBroker, stop, close_grace_seconds=0)
        self.assertEqual(result['reason'], 'USER_CLOSE')
        self.assertEqual(owner.events[-3:], ['wm_close', 'broker_close_save', 'cleanup'])
        self.assertEqual(result['close_wait_end'], 'GRACE_EXPIRED')
        self.assertFalse(result['normal_exit_verified'])
        self.assertEqual(result['game_logout_protocol'], 'UNVERIFIED')
    async def test_close_traffic_can_finish_while_broker_and_observer_stay_live(self):
        owner = FakeOwner()
        broker = FakeBroker(owner)
        closed = False
        async def close_broker():
            nonlocal closed
            closed = True
            return await FakeBroker.close(broker)
        broker.close = close_broker
        async def native_close():
            self.assertFalse(closed)
            owner.events.append('native_close_traffic')
            owner.rows = iter([False])
        native_task = None
        def request_close():
            nonlocal native_task
            owner.events.append('wm_close')
            native_task = asyncio.create_task(native_close())
            return 1
        owner.request_close = request_close
        class Monitor:
            def bind(self, target): pass
            def tick(self, source, state=None, **kw):
                if state == 'CLOSING':
                    self_outer.assertFalse(closed)
                    owner.events.append('closing_observation')
            def close(self): owner.events.append('observer_close')
            def finish(self, report): pass
        self_outer = self
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, lambda o: broker, stop, monitor=Monitor(),
                                     poll_seconds=0, close_grace_seconds=1)
        await native_task
        self.assertEqual(result['close_wait_end'], 'NATIVE_EXIT')
        self.assertEqual(owner.events[-6:], ['wm_close', 'closing_observation',
            'native_close_traffic', 'broker_close_save', 'observer_close', 'cleanup'])
    async def test_broker_failure_during_grace_stops_wait_and_still_cleans(self):
        owner = FakeOwner()
        broker = FakeBroker(owner)
        def request_close():
            owner.events.append('wm_close')
            broker.failure.set()
            return 1
        owner.request_close = request_close
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, lambda o: broker, stop, close_grace_seconds=60)
        self.assertEqual(result['close_wait_end'], 'BROKER_FAILURE')
        self.assertEqual(owner.events[-3:], ['wm_close', 'broker_close_save', 'cleanup'])
    async def test_existing_broker_failure_skips_native_grace(self):
        owner = FakeOwner()
        broker = FakeBroker(owner); broker.failure.set()
        result = await l.run_session(owner, lambda o: broker, asyncio.Event())
        self.assertEqual(result['reason'], 'BROKER_FAILURE')
        self.assertNotIn('wm_close', owner.events)
        self.assertEqual(owner.events[-2:], ['broker_close_save', 'cleanup'])
    async def test_observation_duration_is_opt_in_test_reason(self):
        owner = FakeOwner()
        result = await l.run_session(owner, FakeBroker, asyncio.Event(),
                                     test_duration=0, close_grace_seconds=0)
        self.assertEqual(result['reason'], 'TEST_DURATION')
    async def test_broker_start_failure_always_cleans_owned_process(self):
        owner = FakeOwner()
        result = await l.run_session(owner, lambda o: FakeBroker(o, fail_start=True),
                                     asyncio.Event(), close_grace_seconds=0)
        self.assertEqual(result['reason'], 'SESSION_FAILURE')
        self.assertNotIn('resume', owner.events)
        self.assertNotIn('wm_close', owner.events)
        self.assertTrue(owner.closed)
    async def test_broker_close_failure_preserves_report_and_owned_cleanup(self):
        owner = FakeOwner([False])
        result = await l.run_session(owner, lambda o: FakeBroker(o, fail_close=True), asyncio.Event())
        self.assertEqual(result['broker_close_error'], 'ValueError')
        self.assertTrue(result['cleanup']['positive_exit'])
    async def test_cancelled_product_run_still_saves_and_cleans(self):
        owner = FakeOwner()
        task = asyncio.create_task(l.run_session(owner, FakeBroker, asyncio.Event(), close_grace_seconds=0))
        await asyncio.sleep(0)
        task.cancel()
        result = await task
        self.assertEqual(result['reason'], 'USER_INTERRUPT')
        self.assertEqual(owner.events[-3:], ['wm_close', 'broker_close_save', 'cleanup'])
    async def test_cancel_during_grace_still_joins_broker_cleanup(self):
        owner = FakeOwner()
        closing = asyncio.Event()
        def request_close():
            owner.events.append('wm_close'); closing.set()
            return 1
        owner.request_close = request_close
        stop = asyncio.Event(); stop.set()
        task = asyncio.create_task(l.run_session(owner, FakeBroker, stop, close_grace_seconds=60))
        await closing.wait()
        task.cancel()
        result = await task
        self.assertEqual(result['native_close_error'], 'CancelledError')
        self.assertEqual(owner.events[-3:], ['wm_close', 'broker_close_save', 'cleanup'])
    async def test_repeated_cancel_during_broker_close_joins_same_task(self):
        owner = FakeOwner([False])
        closing, release = asyncio.Event(), asyncio.Event()
        broker = FakeBroker(owner)
        async def close():
            owner.events.append('broker_close_started'); closing.set()
            await release.wait()
            return await FakeBroker.close(broker)
        broker.close = close
        task = asyncio.create_task(l.run_session(owner, lambda o: broker, asyncio.Event()))
        await closing.wait()
        for _ in range(2):
            task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertFalse(owner.closed)
        release.set()
        result = await task
        self.assertTrue(result['cleanup_interrupted'])
        self.assertTrue(result['broker']['cleanup_complete'])
        self.assertNotIn('broker_close_error', result)
        self.assertEqual(owner.events.count('broker_close_started'), 1)
        self.assertEqual(owner.events[-2:], ['broker_close_save', 'cleanup'])
    async def test_close_request_failure_cannot_skip_owned_cleanup(self):
        owner = FakeOwner()
        owner.request_close = lambda: (_ for _ in ()).throw(ValueError('WINDOW_UNKNOWN'))
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, FakeBroker, stop)
        self.assertTrue(owner.closed)
        self.assertEqual(result['native_close_error'], 'ValueError')
        self.assertEqual(owner.events[-2:], ['broker_close_save', 'cleanup'])
    async def test_observer_final_cancel_cannot_skip_owned_cleanup(self):
        owner = FakeOwner([False])
        class Monitor:
            def bind(self, target): pass
            def tick(self, *args, **kwargs): raise asyncio.CancelledError()
            def close(self): owner.events.append('observer_close')
            def finish(self, report): raise asyncio.CancelledError()
        result = await l.run_session(owner, FakeBroker, asyncio.Event(), monitor=Monitor())
        self.assertTrue(owner.closed)
        self.assertEqual(result['status_error_type'], 'CancelledError')
        self.assertEqual(owner.events[-3:], ['broker_close_save', 'observer_close', 'cleanup'])


class InputIntegrationTests(unittest.IsolatedAsyncioTestCase):
    class Monitor:
        def __init__(self, owner): self.owner = owner
        def bind(self, target): pass
        def tick(self, broker, *, state='RUNNING', **kwargs):
            self.owner.events.append('observe_' + state)
            return None
        def close(self): self.owner.events.append('observer_close')
        def finish(self, report): pass

    async def test_running_and_closing_poll_after_observation_before_broker_cleanup(self):
        owner = FakeOwner([True, True, False])
        class Requests:
            sequence = 0
            def poll(self):
                owner.events.append('input_poll')
                self.sequence += 1
                return dict(status='POSTED', sequence=self.sequence, ui_result='UNPROVEN_TEXT')
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, FakeBroker, stop, monitor=self.Monitor(owner),
            input_requests=Requests(), poll_seconds=0, close_grace_seconds=1)
        self.assertEqual(owner.events, ['prepare', 'broker_start', 'resume',
            'observe_RUNNING', 'input_poll', 'wm_close', 'observe_CLOSING', 'input_poll',
            'broker_close_save', 'observe_USER_CLOSE', 'observer_close', 'cleanup'])
        self.assertEqual(result['input'], dict(status='POSTED', sequence=2, ui_result='UNKNOWN',
            automatic_retry=False, disabled=False))
        self.assertEqual(result['close_wait_end'], 'NATIVE_EXIT')
        self.assertFalse(result['normal_exit_verified'])
        self.assertEqual(result['game_logout_protocol'], 'UNVERIFIED')

    async def test_native_exit_and_broker_failure_never_poll_input(self):
        for mode in ('NATIVE_EXIT', 'BROKER_FAILURE'):
            with self.subTest(mode=mode):
                owner = FakeOwner([False] if mode == 'NATIVE_EXIT' else [True])
                broker = FakeBroker(owner)
                if mode == 'BROKER_FAILURE': broker.failure.set()
                class Requests:
                    def poll(self): raise AssertionError('MUST_NOT_POLL')
                result = await l.run_session(owner, lambda o: broker, asyncio.Event(),
                    monitor=self.Monitor(owner), input_requests=Requests())
                self.assertEqual(result['reason'], mode)
                self.assertEqual(result['input']['status'], 'NOT_REQUESTED')
                self.assertTrue(owner.closed)

    async def test_poll_error_disables_input_without_retry_or_session_failure(self):
        owner = FakeOwner([True, True, False])
        class Requests:
            calls = 0
            def poll(self):
                self.calls += 1
                raise ValueError('PRIVATE_INPUT_DETAIL')
        requests = Requests()
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, FakeBroker, stop, monitor=self.Monitor(owner),
            input_requests=requests, poll_seconds=0, close_grace_seconds=1)
        self.assertEqual(requests.calls, 1)
        self.assertEqual(result['reason'], 'USER_CLOSE')
        self.assertEqual(result['input'], dict(status='DISABLED', error_type='ValueError',
            ui_result='UNKNOWN', automatic_retry=False, disabled=True))
        self.assertNotIn('PRIVATE_INPUT_DETAIL', json.dumps(result))
        self.assertTrue(owner.closed)


class CommandIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_integrity_failure_prevents_monitor_control_and_keeps_cleanup(self):
        from tools.local_original_session.commands import IntegrityFailure
        owner = FakeOwner(); owner.require_lifecycle_health = True
        commands = SimpleNamespace(checked_health=Mock(side_effect=IntegrityFailure(
            'COMMAND_INTEGRITY_HEALTH_COUNTS_FAILED')), poll=Mock(), request_quit=Mock())
        monitor = MagicMock()
        result = await l.run_session(owner, FakeBroker, asyncio.Event(), command_requests=commands,
                                     monitor=monitor, poll_seconds=0)
        self.assertEqual(result['reason'], 'NATIVE_GUARD_INTEGRITY_FAILURE')
        commands.poll.assert_not_called(); commands.request_quit.assert_not_called()
        self.assertTrue(owner.closed)
        self.assertEqual(result['native_guard_health']['reason'], 'COMMAND_INTEGRITY_HEALTH_COUNTS_FAILED')
        self.assertEqual(monitor.tick.call_count, 1)  # Existing final observation only.

    async def test_integrity_absent_waits_without_commands_and_post_race_failure_stops(self):
        from tools.local_original_session.commands import IntegrityFailure
        for race in (False, True):
            owner = FakeOwner([True, False] if not race else [True, True])
            owner.require_lifecycle_health = True
            commands = SimpleNamespace(checked_health=Mock(return_value=dict(status='VERIFIED' if race else 'WAIT')),
                poll=Mock(side_effect=IntegrityFailure('COMMAND_INTEGRITY_HEALTH_COUNTS_FAILED')),
                request_quit=Mock())
            monitor = InputIntegrationTests.Monitor(owner)
            result = await l.run_session(owner, FakeBroker, asyncio.Event(), command_requests=commands,
                                         monitor=monitor, poll_seconds=0)
            self.assertEqual(result['reason'], 'NATIVE_GUARD_INTEGRITY_FAILURE' if race else 'NATIVE_EXIT')
            self.assertEqual(commands.poll.call_count, int(race))
            commands.request_quit.assert_not_called()
            self.assertTrue(owner.closed)
    async def test_internal_control_never_uses_mouse_or_window_close(self):
        owner = FakeOwner([True, True, False])
        class Commands:
            def poll(self): owner.events.append('command_poll')
            def request_quit(self):
                owner.events.append('internal_quit')
                return dict(status='UNSUPPORTED', sequence=1, invoked=False,
                            native_reason=8, native_ui_thread_conditional=True)
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, FakeBroker, stop,
            monitor=InputIntegrationTests.Monitor(owner), command_requests=Commands(),
            poll_seconds=0, close_grace_seconds=1)
        self.assertNotIn('wm_close', owner.events)
        self.assertNotIn('input', result)
        self.assertEqual(owner.events, ['prepare', 'broker_start', 'resume', 'observe_RUNNING',
            'command_poll', 'internal_quit', 'observe_CLOSING', 'command_poll', 'broker_close_save',
            'observe_USER_CLOSE', 'observer_close', 'cleanup'])
        self.assertEqual(result['close_via'], 'INTERNAL_QUIT')
        self.assertEqual(result['commands']['status'], 'UNSUPPORTED')
        self.assertFalse(result['commands']['invoked'])
        self.assertFalse(result['normal_exit_verified'])
        self.assertEqual(result['game_logout_protocol'], 'UNVERIFIED')

    async def test_native_exit_broker_failure_or_mixed_control_never_dispatches_command(self):
        commands = MagicMock()
        for mode in ('NATIVE_EXIT', 'BROKER_FAILURE'):
            owner = FakeOwner([False] if mode == 'NATIVE_EXIT' else [True])
            broker = FakeBroker(owner)
            if mode == 'BROKER_FAILURE': broker.failure.set()
            result = await l.run_session(owner, lambda o: broker, asyncio.Event(),
                monitor=InputIntegrationTests.Monitor(owner), command_requests=commands)
            self.assertEqual(result['reason'], mode)
        commands.poll.assert_not_called()
        commands.request_quit.assert_not_called()
        owner = FakeOwner()
        with self.assertRaisesRegex(ValueError, 'EXCLUSIVE_SESSION_CONTROL_REQUIRED'):
            await l.run_session(owner, FakeBroker, asyncio.Event(),
                                command_requests=commands, input_requests=MagicMock())
        self.assertEqual(owner.events, [])


class Fn:
    def __init__(self, fn): self.fn = fn
    def __call__(self, *args): return self.fn(*args)


class IdentityTests(unittest.TestCase):
    def owner(self, **flags):
        real = l.native_module(Path('C:/fixture/LC.local.exe'))
        state = dict(pid=7, birth=33, alive=True, nt='\\Device\\HarddiskVolume3\\fixture\\LC.local.exe', query_ok=True)
        def times(handle, birth, *rest):
            birth._obj.low = state['birth']; birth._obj.high = 0
            return True
        def image(handle, flags, name, size):
            self.assertEqual(handle, 123)
            self.assertEqual(flags, 1)
            name.value = state['nt']
            return state['query_ok']
        class Parent:
            retained_alive = real.Native.retained_alive
            def capture_member(self, root, pid):
                if pid not in root.members:
                    root.members[pid] = SimpleNamespace(process=123, pid=pid,
                        identity=dict(pid=pid, birth='33', image='fixture'))
            def __init__(self, profile):
                self.k = SimpleNamespace(
                    GetProcessId=Fn(lambda h: state['pid']),
                    QueryFullProcessImageNameW=Fn(image), GetProcessTimes=Fn(times),
                    WaitForSingleObject=Fn(lambda *a: 258 if state['alive'] else 0),
                    IsProcessInJob=Fn(lambda h, j, result: setattr(result._obj, 'value', True) or True),
                    GetFinalPathNameByHandleW=Fn(lambda *a: 0))
                self.u = SimpleNamespace(PostMessageW=Fn(lambda *a: True))
            def identity(self, *a, **kw): raise ValueError('native_image_required')
            def token(self, handle): return dict(elevated=False, integrity_rid=8192)
        fake = SimpleNamespace(Native=Parent, FT=real.FT, ENTRY=real.ENTRY, STARTUP=real.STARTUP)
        profile = dict(l.PRODUCTS['baseline'], background_display_guard=
                       flags.get('internal', False) or flags.get('background', False))
        with patch.object(l, 'preflight', return_value={}), patch.object(l, 'native_module', return_value=fake), \
             patch.dict(l.PRODUCTS, {'baseline': profile}):
            owner = l.NativeOwner(Path('C:/fixture/LC.local.exe'),
                l.ROOT / 'work/local_native_login_key_invoke_boundary/runs/fixture', **flags)
        owner.native.image_nt = state['nt']
        return owner, state
    def test_flags1_same_live_handle_path_and_birth(self):
        owner, state = self.owner()
        row = owner.native.identity(123, 7)
        self.assertEqual(row['birth'], '33')
        self.assertEqual(row['image'], str(owner.image))
    def test_flags1_success_with_wrong_path_refused(self):
        owner, state = self.owner(); state['nt'] += '.other'
        with self.assertRaisesRegex(ValueError, 'IMAGE_MISMATCH'): owner.native.identity(123, 7)
    def test_flags1_unknown_refused(self):
        owner, state = self.owner(); state['query_ok'] = False
        with self.assertRaisesRegex(ValueError, 'IMAGE_UNKNOWN'): owner.native.identity(123, 7)
    def test_same_handle_pid_mismatch_refused(self):
        owner, state = self.owner(); state['pid'] = 8
        with self.assertRaisesRegex(ValueError, 'PID_MISMATCH'): owner.native.identity(123, 7)
    def test_exited_fallback_refused(self):
        owner, state = self.owner(); state['alive'] = False
        with self.assertRaisesRegex(ValueError, 'PROCESS_EXITED'): owner.native.identity(123, 7)
    def test_retained_birth_change_refused(self):
        owner, state = self.owner()
        member = SimpleNamespace(process=123, pid=7, identity=owner.native.identity(123, 7))
        state['birth'] = 34
        with self.assertRaisesRegex(ValueError, 'birth_image'): owner.native.retained_alive(member)
    def test_capture_member_observation_runs_after_retained_capture_once(self):
        owner, _ = self.owner()
        root = SimpleNamespace(members={}, job=456)
        public = dict(pid=7, birth='33', observed_parent_pid=91, status='OBSERVED')
        with patch.object(l, 'observed_member_parent', return_value=public) as observe:
            owner.native.capture_member(root, 7)
            owner.native.capture_member(root, 7)
        observe.assert_called_once_with(owner.native, root, root.members[7], owner._entry_type)
        self.assertEqual(owner.process_tree(), [public])

    def test_manual_owner_uses_original_visible_startup_without_private_desktop(self):
        owner, _ = self.owner()
        parent = type(owner.native).__mro__[1]
        with patch.object(parent, 'create_suspended', return_value='original', create=True) as original, \
             patch.object(l, 'hidden_desktop_launch') as hidden:
            self.assertEqual(owner.native.create_suspended(), 'original')
            original.assert_called_once(); hidden.assert_not_called()
        self.assertFalse(owner.internal)
        self.assertIsNone(owner.private_desktop)
        module = l.native_module(l.PRODUCTS['sibling-manual-play-spawn']['image'])
        native, startup_values = module.Native.__new__(module.Native), []
        def create(application, command, process_sec, thread_sec, inherit, flags, environment, cwd, startup, process):
            startup_values.append((startup._obj.flags, startup._obj.show, startup._obj.desktop, flags))
            process._obj.process, process._obj.thread, process._obj.pid, process._obj.tid = 101, 202, 7, 8
            return True
        native.k = SimpleNamespace(CreateProcessW=Fn(create))
        native.identity = lambda *args: dict(pid=7, birth='303', image=module.EXE, parent_pid=1)
        native.create_suspended()
        self.assertEqual(startup_values, [(1, 1, None, 4)])


class BackgroundOwnerTests(unittest.TestCase):
    def test_background_requires_exact_bool_and_required_profile_before_preflight(self):
        product = 'sibling-background-move-continuous-spawn'
        for background, code in ((None, 'BACKGROUND_BOOL_REQUIRED'), (1, 'BACKGROUND_BOOL_REQUIRED'),
                                 (False, 'BACKGROUND_DISPLAY_REQUIRED')):
            with self.subTest(background=background), patch.object(l, 'preflight') as preflight, \
                 patch.object(l, 'native_module') as native:
                with self.assertRaisesRegex(ValueError, code):
                    l.NativeOwner(l.PRODUCTS[product]['image'],
                        l.ROOT / 'work/local_native_login_key_invoke_boundary/runs/test-background',
                        product=product, background=background)
                preflight.assert_not_called(); native.assert_not_called()

    def test_manual_background_uses_existing_hidden_startup_and_missing_desktop_never_falls_through(self):
        owner, _ = IdentityTests().owner(background=True)
        parent = type(owner.native).__mro__[1]
        with patch.object(parent, 'create_suspended', return_value='unwanted', create=True) as original:
            with self.assertRaisesRegex(ValueError, 'PRIVATE_DESKTOP_PREPARE_REQUIRED'):
                owner.native.create_suspended()
            original.assert_not_called()
            owner.private_desktop = SimpleNamespace(name='private-test', verify_non_input=Mock())
            with patch.object(l, 'hidden_desktop_launch', return_value='hidden') as hidden:
                self.assertEqual(owner.native.create_suspended(), 'hidden')
                self.assertIs(hidden.call_args.args[3], owner.private_desktop)
                original.assert_not_called()
        self.assertFalse(owner.internal)
        self.assertTrue(owner.background)

    def prepare_owner(self, directory, *, internal=False, background=True, create_error=None, matches=True):
        owner, _ = IdentityTests().owner(internal=internal, background=background)
        owner.directory = Path(directory) / 'boundary'
        owner.verify_sources_full = Mock()
        owner._file_identity = lambda handle: ('file', handle)
        owner._observe_parent = Mock()
        events, inherited = [], []
        desktop = SimpleNamespace(name='private-test', probe_thread=lambda _: dict(
            status='OBSERVED', matches_private=matches), close=lambda: events.append('desktop_close'))
        child = SimpleNamespace(pid=7, tid=44, process=123, job=None,
            identity=dict(image=str(owner.image), birth='303', elevated=False, integrity_rid=8192))
        def create():
            self.assertIs(owner.private_desktop, desktop)
            events.append('create')
            inherited.append({key: l.os.environ.get(key) for key in
                ('OWN_INTERNAL_COMMAND_MODE', 'OWN_INTERNAL_COMMAND_DESKTOP', 'OWN_KEY_INVOKE_BOUNDARY_DIR')})
            if create_error:
                raise create_error
            return child
        def path(handle, output, *args):
            output.value = '\\Device\\Fake\\LC.exe'
            return len(output.value)
        owner.native = SimpleNamespace(controller=lambda: dict(elevated=False, integrity_rid=8192),
            source=lambda: dict(sha256=owner.image_sha, path=str(owner.image)), handles=[99],
            k=SimpleNamespace(GetFinalPathNameByHandleW=Fn(path)), pin_evidence=Mock(),
            create_suspended=create, attach_single_process_job=lambda child: setattr(child, 'job', 456),
            cleanup_owned=lambda _: events.append('owned_cleanup') or dict(positive_exit=True, owned_job_empty=True),
            close=lambda: events.append('native_close'))
        return owner, desktop, events, inherited

    def test_background_manual_clears_internal_env_and_internal_mode_is_preserved_then_all_restore(self):
        for internal, background in ((False, True), (True, False), (True, True)):
            with self.subTest(internal=internal, background=background), tempfile.TemporaryDirectory() as directory:
                owner, desktop, events, inherited = self.prepare_owner(directory, internal=internal, background=background)
                with patch.dict(l.os.environ, {'OWN_INTERNAL_COMMAND_MODE': 'prior-mode',
                        'OWN_INTERNAL_COMMAND_DESKTOP': 'prior-desktop'}), \
                     patch.object(l, 'PrivateDesktop', side_effect=lambda _: events.append('desktop_create') or desktop):
                    owner.prepare()
                    self.assertEqual(l.os.environ['OWN_INTERNAL_COMMAND_MODE'], 'prior-mode')
                    self.assertEqual(l.os.environ['OWN_INTERNAL_COMMAND_DESKTOP'], 'prior-desktop')
                self.assertEqual(events[:2], ['desktop_create', 'create'])
                self.assertEqual(inherited[0]['OWN_INTERNAL_COMMAND_MODE'], '1' if internal else None)
                self.assertEqual(inherited[0]['OWN_INTERNAL_COMMAND_DESKTOP'], desktop.name if internal else None)
                self.assertEqual(inherited[0]['OWN_KEY_INVOKE_BOUNDARY_DIR'], str(owner.directory))
                self.assertTrue(owner.desktop_status['matches_private'])
                owner.close()
                self.assertEqual(events[-3:], ['owned_cleanup', 'native_close', 'desktop_close'])

    def test_background_create_and_thread_mismatch_restore_env_and_cleanup_without_job_promotion(self):
        for error, matches in ((ValueError('FIXTURE_CREATE_FAILED'), True), (None, False)):
            with self.subTest(error=error, matches=matches), tempfile.TemporaryDirectory() as directory:
                owner, desktop, events, inherited = self.prepare_owner(directory, create_error=error, matches=matches)
                with patch.dict(l.os.environ, {'OWN_INTERNAL_COMMAND_MODE': 'prior'}), \
                     patch.object(l, 'PrivateDesktop', return_value=desktop):
                    with self.assertRaises(ValueError):
                        owner.prepare()
                    self.assertEqual(l.os.environ['OWN_INTERNAL_COMMAND_MODE'], 'prior')
                self.assertIsNone(owner.owner_job)
                self.assertFalse(owner.directory.exists())
                owner.close()
                self.assertEqual(events[-2:], ['native_close', 'desktop_close'])

    def test_private_close_posts_only_on_existing_joined_helper_and_rejects_input_or_owner_loss(self):
        from tools.local_original_session.desktop_tests import DesktopTests
        for failure in (None, 'owner', 'input'):
            with self.subTest(failure=failure):
                fixture = DesktopTests()
                native, state = fixture.fake_native()
                desktop = l.PrivateDesktop(native)
                self.addCleanup(desktop.close)
                proxy, _ = fixture.command_owner(desktop, native, state)
                owner = l.NativeOwner.__new__(l.NativeOwner)
                owner.__dict__.update(vars(proxy))
                owner.image = Path('C:/fixture.exe')
                owner.child.identity['image'] = str(owner.image)
                owner.child.members = {owner.child.pid: owner.child}
                native.windows = lambda _: [dict(hwnd=500, visible=True)]
                native.owned_hwnd = lambda child, hwnd: hwnd == 500
                if failure == 'owner':
                    state['on_join'] = lambda: setattr(owner, 'closed', True)
                if failure == 'input':
                    state['names'][12] = desktop.name
                if failure:
                    with self.assertRaises(ValueError):
                        owner.request_close()
                    self.assertEqual(state['posts'], [])
                else:
                    self.assertEqual(owner.request_close(), 1)
                    thread, actual_desktop, args = state['posts'][0]
                    self.assertNotEqual(thread, threading.get_ident())
                    self.assertEqual((actual_desktop, args), (55, (500, 0x10, 0, 0)))
                self.assertTrue(all(value == 11 for value in state['threads'].values()))


class GuardMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_snapshot_false_scope_and_primary_match_are_bounded_once(self):
        for state, pid, guards in ((8, 11, [True]), (5, 12, [True]),
                                   (5, 11, [True, True]), (5, 11, [True, False]),
                                   (None, None, [True]), (None, None, [False])):
            with self.subTest(state=state, pid=pid, guards=guards):
                owner = l.NativeOwner.__new__(l.NativeOwner)
                owner.child, owner.guard_failure = SimpleNamespace(pid=11), None
                guard_values, calls = iter(guards), []
                owner.key_guard = lambda: next(guard_values)
                table = (struct.pack('<I', 0) if state is None else struct.pack('<7I',
                    1, state, 0x0100007f, socket.htons(52001), 0x0100007f, socket.htons(14030), pid))
                def tcp(data, size, *args):
                    calls.append(data is not None)
                    size._obj.value = len(table)
                    if data is None: return 122
                    C.memmove(data, table, len(table)); return 0
                with patch.object(l.C, 'WinDLL', return_value=SimpleNamespace(GetExtendedTcpTable=Fn(tcp))):
                    answer = await owner.guard(dict(client_host='127.0.0.1', server_host='127.0.0.1',
                                                    server_port=14030, client_port=52001))
                expected = state == 5 and pid == 11 and guards[-1] is True
                self.assertIs(answer, expected)
                self.assertEqual(calls, [] if guards == [False] else [False, True])
                if expected:
                    self.assertIsNone(owner.guard_failure)
                else:
                    first = copy.deepcopy(owner.guard_failure)
                    owner._guard_false('OTHER', False, None, None, None, None)
                    self.assertEqual(owner.guard_failure, first)
                    self.assertEqual(set(first), {'reason', 'key_guard_before', 'key_guard_after',
                        'tcp_snapshot', 'tcp_state_counts', 'primary_pid_match', 'established_match_count'})
                    self.assertEqual(first['tcp_snapshot'], 'UNKNOWN' if guards == [False] else 'OBSERVED')
                    if state is not None:
                        self.assertEqual(first['tcp_state_counts'], {str(state): 1})
                        self.assertIs(first['primary_pid_match'], pid == 11)
                        self.assertEqual(first['established_match_count'], int(state == 5))


class ParentObservationTests(unittest.TestCase):
    def fixture(self):
        entry_type = l.native_module(Path('C:/fixture/LC.local.exe')).ENTRY
        member = SimpleNamespace(process=123, pid=7,
                                 identity=dict(pid=7, birth='33', image='fixture', parent_pid=None))
        root = SimpleNamespace(members={7: member}, job=456)
        state = dict(pid=7, alive=True, inside=True, birth='33', image='fixture',
                     rows=[(9, 2), (7, 91)], index=0, complete=True, closed=0, snapshots=0,
                     exit_after_snapshot=False)
        def snapshot(*args):
            state['snapshots'] += 1; return 999
        def row(pointer, first=False):
            if first: state['index'] = 0
            else: state['index'] += 1
            if state['index'] >= len(state['rows']): return False
            pointer._obj.pid, pointer._obj.parent = state['rows'][state['index']]
            return True
        def close(handle):
            self.assertEqual(handle, 999)
            state['closed'] += 1
            if state['exit_after_snapshot']: state['alive'] = False
            return True
        native = SimpleNamespace(k=SimpleNamespace(
            GetProcessId=Fn(lambda h: state['pid']),
            WaitForSingleObject=Fn(lambda *a: 258 if state['alive'] else 0),
            IsProcessInJob=Fn(lambda h, j, out: setattr(out._obj, 'value', state['inside']) or True),
            CreateToolhelp32Snapshot=Fn(snapshot), Process32FirstW=Fn(lambda h, out: row(out, True)),
            Process32NextW=Fn(lambda h, out: row(out)), CloseHandle=Fn(close)),
            identity=lambda *args, **kw: dict(pid=state['pid'], birth=state['birth'], image=state['image']))
        return native, root, member, entry_type, state

    def observe(self, fixture):
        native, root, member, entry_type, state = fixture
        with patch.object(C, 'get_last_error', side_effect=lambda: 18 if state['complete'] else 5):
            return l.observed_member_parent(native, root, member, entry_type)

    def test_exact_retained_member_reads_only_its_parent_and_closes_snapshot(self):
        fixture = self.fixture()
        self.assertEqual(self.observe(fixture), dict(pid=7, birth='33', observed_parent_pid=91, status='OBSERVED'))
        self.assertEqual(fixture[-1]['closed'], 1)
        self.assertEqual(fixture[2].identity['parent_pid'], None)

    def test_fast_exit_changed_identity_membership_or_incomplete_snapshot_is_unknown(self):
        for changed in (dict(alive=False), dict(pid=8), dict(birth='34'), dict(image='other'),
                        dict(inside=False), dict(rows=[(9, 2)]), dict(complete=False),
                        dict(exit_after_snapshot=True), dict(rows=[(7, 91), (7, 92)]),
                        dict(rows=[(9, 2)] * 4097)):
            with self.subTest(fields=tuple(changed)):
                fixture = self.fixture(); fixture[-1].update(changed)
                public = self.observe(fixture)
                self.assertEqual(public['status'], 'UNKNOWN')
                self.assertIsNone(public['observed_parent_pid'])
                self.assertEqual(fixture[-1]['closed'], fixture[-1]['snapshots'])

    def test_member_once_three_row_bound_and_status_use_only_public_copy(self):
        native, root, member, entry_type, state = fixture = self.fixture()
        owner = l.NativeOwner.__new__(l.NativeOwner)
        owner.native, owner._parent_observations = native, {}
        with patch.object(C, 'get_last_error', return_value=18):
            owner._observe_parent(root, 7, entry_type)
            owner._observe_parent(root, 7, entry_type)
            for pid in (8, 9, 10): owner._observe_parent(root, pid, entry_type)
        self.assertEqual(state['snapshots'], 1)
        self.assertEqual(len(owner.process_tree()), 3)
        self.assertTrue(all(set(row) == {'pid', 'birth', 'observed_parent_pid', 'status'}
                            for row in owner.process_tree()))
        monitor = SimpleNamespace(publish=lambda public: public)
        l.add_process_tree_status(monitor, owner)
        row = monitor.publish(dict(state='CLOSED'))
        self.assertEqual(row['process_tree'], owner.process_tree())
        row['process_tree'][0]['observed_parent_pid'] = 999
        self.assertEqual(owner.process_tree()[0]['observed_parent_pid'], 91)


class ExitProofTests(unittest.TestCase):
    def fixture(self):
        real = l.native_module(Path('C:/fixture/LC.local.exe'))
        owner = l.NativeOwner.__new__(l.NativeOwner)
        owner.image = Path('C:/fixture/LC.local.exe')
        owner.closed = owner._cleanup_requested = False
        owner.owner_handle, owner.owner_job = 123, 456
        child = SimpleNamespace(process=123, job=456, pid=7, identity=dict(birth='33'))
        child.members = {7: child}; owner.child = child
        owner._filetime_type = real.FT
        state = dict(pid=7, birth=33, signaled=True, member=True, active=0, code=0,
                     code_ok=True, times_ok=True, image=str(owner.image), query0=True,
                     query1=True, nt='\\Device\\HarddiskVolume3\\fixture\\LC.local.exe',
                     pinned='\\Device\\HarddiskVolume3\\fixture\\LC.local.exe', pin_ok=True)
        def times(handle, birth, *rest):
            birth._obj.low = state['birth']; birth._obj.high = 0
            return state['times_ok']
        def image(handle, flags, name, length):
            self.assertEqual(handle, owner.child.process)
            name.value = state['image'] if flags == 0 else state['nt']
            return state['query0'] if flags == 0 else state['query1']
        def pinned(handle, name, length, flags):
            self.assertEqual((handle, flags), (999, 2))
            name.value = state['pinned']; return len(name.value)
        def sources():
            if not state['pin_ok']: raise ValueError('SOURCE_PIN_CHANGED')
        owner.verify_sources = sources
        owner.native = SimpleNamespace(handles=[999], active_job_count=lambda c: state['active'],
            k=SimpleNamespace(
                WaitForSingleObject=Fn(lambda *a: 0 if state['signaled'] else 258),
                GetProcessId=Fn(lambda h: state['pid']), GetProcessTimes=Fn(times),
                QueryFullProcessImageNameW=Fn(image), GetFinalPathNameByHandleW=Fn(pinned),
                IsProcessInJob=Fn(lambda h, j, result: setattr(result._obj, 'value', state['member']) or True),
                GetExitCodeProcess=Fn(lambda h, result: setattr(result._obj, 'value', state['code']) or state['code_ok'])))
        return owner, state

    def test_current_exact_handles_and_nt_fallback_prove_os_exit_only(self):
        owner, state = self.fixture()
        for flags0, code in ((True, 0), (False, 0), (True, 1)):
            state.update(query0=flags0, code=code)
            proof = owner.exit_proof()
            self.assertEqual(proof['status'], 'VERIFIED')
            self.assertIs(proof['owner'], owner)
            self.assertIs(proof['handle'], owner.owner_handle)
            self.assertIs(proof['job'], owner.owner_job)
            self.assertEqual(proof['exit_code'], code)
            self.assertIs(proof['forced_cleanup_requested'], False)

    def test_unknown_identity_lifetime_job_or_source_never_proves_exit(self):
        for change in (dict(signaled=False), dict(pid=8), dict(birth=34), dict(times_ok=False),
                       dict(image='C:/other.exe'), dict(query0=False, query1=False),
                       dict(query0=False, nt='\\Device\\HarddiskVolume4\\other.exe'),
                       dict(member=False), dict(active=1), dict(code_ok=False), dict(pin_ok=False)):
            with self.subTest(fields=tuple(change)):
                owner, state = self.fixture(); state.update(change)
                proof = owner.exit_proof()
                self.assertEqual(proof['status'], 'UNKNOWN')
                self.assertEqual(set(proof), {'status', 'reason'})
        for field in ('closed', '_cleanup_requested'):
            owner, _ = self.fixture(); setattr(owner, field, True)
            self.assertEqual(owner.exit_proof()['status'], 'UNKNOWN')
        owner, _ = self.fixture()
        owner.verify_sources = lambda: setattr(owner, 'owner_handle', 124)
        self.assertEqual(owner.exit_proof()['status'], 'UNKNOWN')


class StartupReportTests(unittest.TestCase):
    def test_source_quit_product_and_explicit_flag_are_required_before_native(self):
        for product, flags, code in (
                ('sibling-background-source-quit-spawn', ['--background'], 'SOURCE_QUIT_EXPLICIT_TEST_REQUIRED'),
                ('sibling-background-source-quit-spawn', ['--source-quit-test'], 'SOURCE_QUIT_BACKGROUND_PRODUCT_REQUIRED'),
                ('sibling-background-move-attack-target-spawn', ['--background', '--source-quit-test'],
                 'SOURCE_QUIT_BACKGROUND_PRODUCT_REQUIRED')):
            with self.subTest(product=product, flags=flags), tempfile.TemporaryDirectory() as root:
                directory = Path(root) / 'run'
                args = ['launcher', '--run', '--control-mode', 'manual', '--image', str(Path(root) / 'fixture.exe'),
                        '--product', product, '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                        '--run-directory', str(directory), *flags]
                with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight') as preflight, \
                     patch.object(l, 'NativeOwner') as owner, patch.object(l.socket, 'socket') as socket, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(l.main(), 2)
                preflight.assert_not_called(); owner.assert_not_called(); socket.assert_not_called()
                self.assertEqual(json.loads((directory / 'result.json').read_text())['error_code'], code)

    def test_background_requirement_and_unknown_guard_refuse_before_any_native_or_socket(self):
        for product, background, code in (
                ('sibling-background-move-continuous-spawn', False, 'BACKGROUND_DISPLAY_REQUIRED'),
                ('sibling-background-move-attack-target-spawn', False, 'BACKGROUND_DISPLAY_REQUIRED'),
                ('sibling-manual-move-continuous-spawn', True, 'BACKGROUND_DISPLAY_GUARD_UNVERIFIED')):
            with self.subTest(product=product), tempfile.TemporaryDirectory() as root:
                directory = Path(root) / 'run'
                args = ['launcher', '--run', '--image', str(Path(root) / 'fixture.exe'), '--product', product,
                        '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                        '--run-directory', str(directory), '--control-mode', 'manual']
                if background:
                    args.append('--background')
                with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight') as preflight, \
                     patch.object(l, 'NativeOwner') as owner, patch.object(l, 'GenuineConversations') as source, \
                     patch.object(l.socket, 'socket') as socket, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(l.main(), 2)
                preflight.assert_not_called(); owner.assert_not_called()
                source.assert_not_called(); socket.assert_not_called()
                self.assertEqual(json.loads((directory / 'result.json').read_text())['error_code'], code)

    def test_source_build_attack_product_refuses_run_before_preflight_native_or_socket(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'run'
            args = ['launcher', '--run', '--image', str(Path(root) / 'fixture.exe'),
                    '--product', 'sibling-manual-move-attack-target-spawn',
                    '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                    '--run-directory', str(directory), '--control-mode', 'manual']
            with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight') as preflight, \
                 patch.object(l, 'NativeOwner') as owner, patch.object(l, 'GenuineConversations') as source, \
                 patch.object(l.socket, 'socket') as socket, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(l.main(), 2)
            preflight.assert_not_called(); owner.assert_not_called()
            source.assert_not_called(); socket.assert_not_called()
            report = json.loads((directory / 'result.json').read_text())
            self.assertEqual(report['error_code'], 'PRODUCT_RUNTIME_UNVERIFIED')
            self.assertFalse(report['native_executed'] or report['listeners_started'])

    def test_continuous_product_refuses_internal_mode_before_any_native_or_resource(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'run'
            args = ['launcher', '--run', '--image', str(Path(root) / 'fixture.exe'),
                    '--product', 'sibling-manual-move-continuous-spawn',
                    '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                    '--run-directory', str(directory), '--control-mode', 'internal']
            with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight'), \
                 patch.object(l, 'NativeOwner') as owner, patch.object(l, 'GenuineConversations') as source, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(l.main(), 2)
            owner.assert_not_called(); source.assert_not_called()
            self.assertEqual(json.loads((directory / 'result.json').read_text())['error_code'],
                             'MANUAL_CONTROL_MODE_REQUIRED')

    def test_close_grace_parser_rejects_nonpositive_nonfinite_and_excessive_values(self):
        for value in ('0', '-1', '120.1', 'nan', 'inf'):
            with self.subTest(value=value), patch.object(l.sys, 'argv',
                    ['launcher', '--preflight', '--image', 'fixture.exe', '--close-grace-seconds', value]), \
                 patch.object(l, 'preflight') as preflight, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    l.main()
                self.assertEqual(failure.exception.code, 2)
                preflight.assert_not_called()

    def test_close_grace_parser_accepts_positive_upper_boundary(self):
        with patch.object(l.sys, 'argv', ['launcher', '--preflight', '--image', 'fixture.exe',
                '--close-grace-seconds', '120']), patch.object(l, 'preflight', return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(l.main(), 0)

    def test_close_grace_default_and_explicit_value_reach_session(self):
        from tools.local_original_session import input as input_module
        from tools.local_original_session import edge as edge_module, broker as broker_module, commands as command_module
        for extra, expected, mode in (([], 10, 'manual'), (['--close-grace-seconds', '30'], 30, 'manual'),
                                      (['--close-grace-seconds', '30'], 30, 'internal'),
                                      (['--product', 'sibling-internal-quit-source-retry-spawn'], 10, 'internal'),
                                      (['--product', 'sibling-manual-play-spawn'], 10, 'manual'),
                                      (['--product', 'sibling-background-move-continuous-spawn', '--background'], 10, 'manual')):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as root:
                directory = Path(root) / 'run'
                args = ['launcher', '--run', '--image', str(Path(root) / 'fixture.exe'),
                        '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                        '--run-directory', str(directory), '--control-mode', mode, *extra]
                owner = MagicMock(image=Path(root) / 'fixture.exe', resource_directory=Path(root), closed=True)
                owner.process_tree.return_value = []
                async def fake_session(retained, factory, stop, **kwargs):
                    factory(retained)
                    if mode == 'internal':
                        result = ExitOutcomeTests.source_report()
                        result.update(l.source_logout_outcome(result), exit_outcome='NATIVE_EXIT_NO_FORCE')
                        return result
                    return dict(reason='USER_CLOSE', exit_outcome='NATIVE_EXIT_NO_FORCE',
                                normal_exit_verified=False, game_logout_protocol='UNVERIFIED',
                                cleanup=dict(positive_exit=True))
                session = AsyncMock(side_effect=fake_session)
                edge = MagicMock(last_result=dict(status='UNKNOWN', reason='NOT_SAMPLED'))
                output = io.StringIO()
                with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight'), \
                     patch.dict(l.PRODUCTS, {'baseline': dict(l.PRODUCTS['baseline'], background_display_guard=True)}), \
                     patch.object(l, 'GenuineConversations'), patch.object(l, 'NativeOwner', return_value=owner) as native_owner, \
                     patch.object(obs, 'RetainedSceneReader') as reader, patch.object(obs, 'SessionMonitor'), \
                     patch.object(edge_module, 'EdgeAdapter', return_value=edge) as adapter, \
                     patch.object(broker_module, 'PersistentBroker') as broker, \
                     patch.object(input_module, 'OwnedMouse') as mouse, patch.object(input_module, 'InputRequests') as inputs, \
                     patch.object(command_module, 'CommandRequests') as commands, \
                     patch.object(l, 'socket', SimpleNamespace(socket=MagicMock(), AF_INET=2, SOCK_STREAM=1)), \
                     patch.object(l, 'run_session', session), \
                     contextlib.redirect_stdout(output):
                    self.assertEqual(l.main(), 0)
                session.assert_awaited_once()
                self.assertIs(native_owner.call_args.kwargs['background'], '--background' in extra)
                self.assertIs(native_owner.call_args.kwargs['internal'], mode == 'internal')
                self.assertEqual(session.await_args.kwargs['close_grace_seconds'], expected)
                mouse.assert_not_called(); inputs.assert_not_called()
                if mode == 'internal':
                    commands.assert_called_once_with(directory, owner)
                    self.assertIs(session.await_args.kwargs['command_requests'], commands.return_value)
                else:
                    commands.assert_not_called()
                    self.assertIsNone(session.await_args.kwargs['command_requests'])
                adapter.assert_called_once_with(reader.return_value)
                self.assertIs(broker.call_args.kwargs['edge_passability'], edge)
                self.assertEqual(broker.call_args.kwargs['owner_exit_proof'], owner.exit_proof)
                self.assertEqual(broker.call_args.kwargs['settings_path'],
                                 Path(root).absolute() / 'account-settings.bin')
                self.assertEqual(broker.call_args.kwargs['world_profile'],
                    'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73' if '--product' in extra else 'baseline')
                self.assertEqual(json.loads((directory / 'result.json').read_text())['edge_check'],
                                 edge.last_result)
                self.assertEqual(json.loads(output.getvalue())['normal_exit_verified'], mode == 'internal')
                self.assertEqual(json.loads((directory / 'result.json').read_text())['normal_exit_verified'],
                                 mode == 'internal')

    def test_internal_mode_rejects_unverified_display_guard_before_any_native(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'run'
            args = ['launcher', '--run', '--image', str(Path(root) / 'fixture.exe'),
                    '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                    '--run-directory', str(directory)]
            with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight'), \
                 patch.object(l, 'NativeOwner') as owner, patch.object(l, 'GenuineConversations') as resource, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(l.main(), 2)
            owner.assert_not_called(); resource.assert_not_called()
            row = json.loads((directory / 'result.json').read_text())
            self.assertEqual(row['error_code'], 'INTERNAL_DISPLAY_GUARD_UNVERIFIED')
            self.assertFalse(row['native_executed'])

    def failure(self, fail_preflight):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'fresh-run'
            args = ['launcher', '--run', '--image', str(Path(root) / 'LC.local.exe'),
                    '--expected-uuid', 'fixture', '--store', str(Path(root) / 'store.json'),
                    '--run-directory', str(directory), '--control-mode', 'manual']
            output = io.StringIO()
            error = ModuleNotFoundError('PRIVATE_RESOURCE_SENTINEL')
            with patch.object(l.sys, 'argv', args), contextlib.redirect_stdout(output), \
                 patch.object(l, 'preflight', side_effect=error if fail_preflight else None), \
                 patch.object(l, 'GenuineConversations', side_effect=error), \
                 patch.object(l, 'NativeOwner') as native:
                self.assertEqual(l.main(), 2)
            native.assert_not_called()
            raw = (directory / 'result.json').read_text(encoding='utf-8')
            report = json.loads(raw)
            self.assertEqual(report['phase'], 'BEFORE_NATIVE')
            self.assertFalse(report['native_executed'])
            self.assertFalse(report['listeners_started'])
            self.assertEqual(report['error_type'], 'ModuleNotFoundError')
            self.assertNotIn('PRIVATE_RESOURCE_SENTINEL', raw + output.getvalue())
    def test_initial_source_failure_reports_no_native(self): self.failure(True)
    def test_resource_import_failure_reports_no_native(self): self.failure(False)


class ExitOutcomeTests(unittest.TestCase):
    @staticmethod
    def source_report():
        connection = dict(eof=True, positive_close=True, joined=True, registry_removed=True,
                          bootstrap_complete=True, failed=False, port=14030)
        member = dict(retained_handle_signaled=True, natural_exit_observed_before_cleanup=True,
                      forced_cleanup_requested_while_active=False)
        return dict(reason='NATIVE_EXIT', primary=dict(pid=31568, birth=134365853065789694),
            cleanup=dict(positive_exit=True, forced_exit=False, job_members_forced_cleanup=False,
                retained_members_signaled=True, owned_job_empty=True, exit_code=0,
                method='retained_exact_owned_job_handle', retained_member_count=2,
                final_owned_members=[dict(member, pid=31568, birth='134365853065789694', exit_code=0),
                                     dict(member, pid=22196, birth='134365853084843309', exit_code=1)]),
            broker=dict(failure_code=None, cleanup_complete=True, active_tasks=0, registry_sessions=0,
                settings=dict(session_fatal=False),
                connections=[dict(connection, connection_id=2), dict(connection, connection_id=4)],
                quit=dict(active=0, sessions=[dict(source_connection_id=4, uid=1, request_verified=True,
                    response_drain_returned=True, response_queue_empty=True, response_drained=True,
                    duplicate_requests=1)])))

    def test_explicit_source_quit_first_return_alone_never_marks_normal_exit(self):
        report = self.source_report()
        report['source_quit'] = dict(first_returned=False)
        self.assertFalse(l.source_logout_outcome(report)['normal_exit_verified'])
        report['source_quit']['first_returned'] = True
        self.assertTrue(l.source_logout_outcome(report)['normal_exit_verified'])
        report['broker']['quit']['sessions'][0]['response_drain_returned'] = False
        self.assertFalse(l.source_logout_outcome(report)['normal_exit_verified'])
        report = self.source_report()
        report.update(reason='SESSION_FAILURE', source_quit=dict(first_returned=True),
            inventory_pre_write_refusal=dict(write_attempted=False))
        self.assertTrue(l.source_logout_outcome(report)['normal_exit_verified'])
        report.pop('inventory_pre_write_refusal')
        self.assertFalse(l.source_logout_outcome(report)['normal_exit_verified'])

    def test_source_quit_drain_same_connection_eof_and_primary_exit0_are_verified(self):
        self.assertEqual(l.source_logout_outcome(self.source_report()),
            dict(normal_exit_verified=True, game_logout_protocol='SOURCE_QUIT_DRAIN_EOF_EXIT0'))

    def test_archived_quit_and_broker_row_publish_the_same_source_connection_id(self):
        from tools.local_original_session import broker as b
        from collections import deque
        realm = b.LocalRealm.__new__(b.LocalRealm)
        writer = object()
        state = dict(writer=writer, uid=1, source_connection_id=4, request_verified=True,
                     response_drain_returned=True, response_queue_empty=True, response_drained=True,
                     duplicate_requests=1)
        realm._quit, realm._quit_closed = {id(writer): state}, deque(maxlen=4)
        realm._account_bound, realm._movement, realm._world_frames = {}, {}, {}
        realm.registry = SimpleNamespace(close=lambda target: None, _sessions={})
        realm.movement_report = realm.edge_report = lambda: {}
        realm.world_profile_report = lambda: {}
        realm.settings, realm._settings_failed = None, False
        realm.close(writer)
        with patch.object(b, 'LocalRealm', return_value=realm):
            broker = b.PersistentBroker(sockets={12000: object(), 14030: object()},
                retained_owner=object(), owner_handle=object(), owner_job=object(),
                owner_guard=lambda peer: True, owner_liveness_guard=lambda: True,
                source_guard=lambda: None, conversation_factory=lambda *args: None,
                expected_uuid='fixture', store_path=Path('fixture'))
        broker._claims[14030].append(dict(peer=dict(connection_id=4), eof=True, boot_complete=True,
            positive_close=True, joined=True, registry_removed=True, failed=False))
        report = broker.report()
        self.assertEqual(report['quit']['sessions'][0]['source_connection_id'], 4)
        self.assertEqual(report['connections'][0]['connection_id'], 4)
        self.assertEqual(report['quit']['scope'], 'SOURCE_QUIT_RESPONSE_DRAIN_ONLY')
        self.assertTrue(report['quit']['source_quit_response_drained'])
        self.assertNotIn('normal_logout_verified', report['quit'])

    def test_generic_missing_failed_forced_or_foreign_evidence_is_unverified(self):
        changes = ((('cleanup', 'forced_exit'), True), (('cleanup', 'job_members_forced_cleanup'), True),
            (('cleanup', 'exit_code'), 1), (('cleanup', 'retained_members_signaled'), False),
            (('cleanup', 'owned_job_empty'), False), (('cleanup', 'positive_exit'), False),
            (('cleanup', 'final_owned_members', 0, 'exit_code'), 1),
            (('cleanup', 'final_owned_members', 0, 'birth'), 'other'),
            (('cleanup', 'final_owned_members', 1, 'forced_cleanup_requested_while_active'), True),
            (('broker', 'failure_code'), 'CURRENT_OWNER_REQUIRED'),
            (('broker', 'cleanup_complete'), False), (('broker', 'active_tasks'), 1),
            (('broker', 'registry_sessions'), 1), (('broker', 'settings', 'session_fatal'), True),
            (('broker', 'connections', 1, 'failed'), True), (('broker', 'connections', 1, 'eof'), False),
            (('broker', 'connections', 1, 'positive_close'), False),
            (('broker', 'connections', 1, 'joined'), False),
            (('broker', 'connections', 1, 'registry_removed'), False),
            (('broker', 'connections', 1, 'connection_id'), 2),
            (('broker', 'quit', 'sessions', 0, 'source_connection_id'), 3),
            (('broker', 'quit', 'sessions', 0, 'source_connection_id'), None),
            (('broker', 'quit', 'sessions', 0, 'request_verified'), False),
            (('broker', 'quit', 'sessions', 0, 'response_drain_returned'), False),
            (('broker', 'quit', 'sessions', 0, 'response_queue_empty'), False),
            (('broker', 'quit', 'sessions', 0, 'response_drained'), False),
            (('broker', 'quit', 'sessions'), []))
        for path, value in changes:
            with self.subTest(field=path):
                report = copy.deepcopy(self.source_report()); target = report
                for key in path[:-1]: target = target[key]
                target[path[-1]] = value
                self.assertFalse(l.source_logout_outcome(report)['normal_exit_verified'])
        for missing in ('broker', 'primary', 'cleanup'):
            report = self.source_report(); del report[missing]
            self.assertEqual(l.source_logout_outcome(report),
                             dict(normal_exit_verified=False, game_logout_protocol='UNVERIFIED'))

    def test_positive_owned_cleanup_with_force_is_not_normal_exit(self):
        self.assertEqual(l.exit_outcome(dict(positive_exit=True, owned_job_empty=True,
            forced_exit=True, job_members_forced_cleanup=True)), 'FORCED_CLEANUP')
    def test_even_helper_only_force_is_explicit(self):
        self.assertEqual(l.exit_outcome(dict(positive_exit=True, forced_exit=False,
            job_members_forced_cleanup=True)), 'FORCED_CLEANUP')
    def test_native_no_force_has_separate_outcome(self):
        self.assertEqual(l.exit_outcome(dict(positive_exit=True, forced_exit=False,
            job_members_forced_cleanup=False)), 'NATIVE_EXIT_NO_FORCE')
    def test_missing_force_evidence_is_unknown(self):
        self.assertEqual(l.exit_outcome(dict(positive_exit=True, owned_job_empty=True)), 'CLEANUP_UNKNOWN')
    def test_unconfirmed_exit_is_unknown(self):
        self.assertEqual(l.exit_outcome(dict(positive_exit=False, forced_exit=True)), 'CLEANUP_UNKNOWN')
    def test_never_launched_is_explicit(self):
        self.assertEqual(l.exit_outcome(dict(positive_exit=True, launched=False)), 'NOT_LAUNCHED')


class FeatureLifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_feature_binding_poll_and_close_follow_real_session_order(self):
        owner = FakeOwner([True, False])
        class Runtime:
            async def poll(self, monitor):
                owner.events.append('feature_poll')
                return dict(npc=dict(status='IDLE'))
            def close(self):
                owner.events.append('feature_close')
        def factory(broker):
            owner.events.append('feature_bind')
            return Runtime()
        result = await l.run_session(owner, FakeBroker, asyncio.Event(),
                                      poll_seconds=0, feature_factory=factory)
        self.assertEqual(owner.events, ['prepare', 'broker_start', 'feature_bind', 'resume',
            'feature_poll', 'feature_close', 'broker_close_save', 'cleanup'])
        self.assertEqual(result['features']['npc']['status'], 'IDLE')

    async def test_explicit_close_stops_feature_poll_before_native_close(self):
        owner, runtime = FakeOwner(), Mock()
        runtime.poll = AsyncMock()
        stop = asyncio.Event(); stop.set()
        result = await l.run_session(owner, FakeBroker, stop, close_grace_seconds=0,
                                    feature_factory=lambda _: runtime)
        runtime.poll.assert_not_awaited()
        runtime.close.assert_called_once()
        self.assertEqual(result['reason'], 'USER_CLOSE')

    async def test_manual_sampling_consumes_monitor_slot_only_when_reader_sampled(self):
        consumer = SimpleNamespace(last_sample_monotonic_ns=None, close=Mock())
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        ingress = l.ManualMoveRequests(Path(directory.name), consumer)
        calls = []
        async def poll():
            calls.append(True)
            consumer.last_sample_monotonic_ns = 2_000_000_000
            return dict(status='PENDING')
        consumer.poll_async = poll
        feature = l.ProductFeatures(ingress, None)
        monitor = SimpleNamespace(next_memory=2.0)
        with patch.object(l.time, 'monotonic', return_value=1.9):
            await feature.poll(monitor)
        self.assertEqual(calls, [])
        with patch.object(l.time, 'monotonic', return_value=2.0):
            await feature.poll(monitor)
        self.assertEqual((calls, monitor.next_memory), ([True], 2.5))
        consumer.last_sample_monotonic_ns = None
        consumer.poll_async = AsyncMock(return_value=dict(status='NOT_REQUESTED'))
        with patch.object(l.time, 'monotonic', return_value=3.0):
            await feature.poll(monitor)
        self.assertEqual(monitor.next_memory, 2.5)


class ManualIngressTests(unittest.TestCase):
    def test_durable_claim_one_pending_commit_then_explicit_next_no_duplicate(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            state = dict(status='READY')
            calls = []
            def submit(uid, x, y):
                self.assertEqual(json.loads((directory / 'command.result.json').read_text())['status'],
                                 'CLAIMED')
                calls.append((uid, x, y))
                state.update(status='PENDING')
                return dict(state)
            consumer = SimpleNamespace(poll=lambda: dict(state), submit_goal=submit, close=Mock())
            ingress = l.ManualMoveRequests(directory, consumer)
            request = dict(schema=REQUEST_SCHEMA, sequence=7, command='MoveGoal', uid=1, x=2, y=3)
            (directory / 'command.request.json').write_text(json.dumps(request))
            self.assertEqual(ingress.poll()['status'], 'PENDING')
            request['sequence'] = 8
            (directory / 'command.request.json').write_text(json.dumps(request))
            ingress.poll()
            self.assertEqual(len(calls), 1)
            state.update(status='COMMITTED')
            self.assertEqual(ingress.poll()['status'], 'COMMITTED')
            self.assertEqual(ingress.poll()['sequence'], 8)
            self.assertEqual(len(calls), 2)
            state.update(status='COMMITTED')
            ingress.poll(); ingress.poll()
            self.assertEqual(len(calls), 2)

    def test_rejected_shape_from_nonactual_consumer_is_unknown_and_never_replayed(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        state = dict(status='READY')
        def submit(*args):
            state.update(status='PENDING')
            return dict(state)
        consumer = SimpleNamespace(poll=lambda: dict(state), submit_goal=Mock(side_effect=submit), close=Mock())
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            request = dict(schema=REQUEST_SCHEMA, sequence=7, command='MoveGoal', uid=1, x=2, y=3)
            (directory / 'command.request.json').write_text(json.dumps(request))
            wrapper = l.ManualMoveRequests(directory, consumer)
            self.assertEqual(wrapper.poll()['status'], 'PENDING')
            state.clear(); state.update(status='REJECTED', phase='REJECTED', reason='EDGE_BLOCKED',
                command='MoveGoal', sequence=1, accepted=False, native_attempted=True, automatic_retry=False,
                cleanup_required=False, proof_scope='SC4EE0_DRAIN_WITH_CLIENT_SETTLED',
                moving_back_snapshot_observed=True, moving_back_start_observed=False)
            with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'): wrapper.poll()
            self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
            self.assertTrue(wrapper.closed)
            request['sequence'] = 8
            (directory / 'command.request.json').write_text(json.dumps(request))
            self.assertEqual(wrapper.poll()['status'], 'UNKNOWN')
            consumer.submit_goal.assert_called_once()
            consumer.close.assert_called_once()

    def test_unknown_consumer_and_non_move_request_end_without_retry(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        for request, result in ((dict(schema=REQUEST_SCHEMA, sequence=1, command='Quit', uid=0, x=0, y=0),
                                 dict(status='READY')),
                                (None, dict(status='UNKNOWN', cleanup_required=True))):
            with self.subTest(request=request), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                consumer = SimpleNamespace(poll=lambda: result, submit_goal=Mock(), close=Mock())
                ingress = l.ManualMoveRequests(directory, consumer)
                if request is not None:
                    (directory / 'command.request.json').write_text(json.dumps(request))
                with self.assertRaises(ValueError):
                    ingress.poll()
                self.assertTrue(ingress.closed)
                consumer.close.assert_called_once()
                consumer.submit_goal.assert_not_called()


class AsyncManualIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_consumer_common_sequence_durable_claim_move_attack_move(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            state, calls = dict(status='READY'), []
            def submit(command, *args):
                claim = json.loads((directory / 'command.result.json').read_text())
                self.assertEqual((claim['status'], claim['command']), ('CLAIMED', command))
                calls.append((command, *args))
                state.clear(); state.update(status='PENDING', phase='ADMISSION', command=command)
                return dict(state)
            consumer = SimpleNamespace(poll_async=AsyncMock(side_effect=lambda: dict(state)), poll=Mock(),
                submit_goal=lambda *args: submit('MoveGoal', *args),
                submit_attack=lambda *args: submit('AttackTarget', *args), close=Mock())
            ingress = l.ManualMoveRequests(directory, consumer, allow_attack=True)
            commands = [dict(command='MoveGoal', uid=1, x=2, y=3),
                        dict(command='AttackTarget', uid=1, target_uid=47, map_id=0),
                        dict(command='MoveGoal', uid=1, x=1, y=3)]
            for sequence, request in zip((2, 5, 8), commands):
                request.update(schema=REQUEST_SCHEMA, sequence=sequence)
                (directory / 'command.request.json').write_text(json.dumps(request))
                self.assertEqual((await ingress.poll_async())['phase'], 'ADMISSION')
                state.update(status='RETURNED')
                self.assertEqual((await ingress.poll_async())['status'], 'RETURNED')
                self.assertTrue(ingress.pending)
                state.update(status='COMMITTED')
                if request['command'] == 'AttackTarget':
                    state.update(proof_scope='VALIDATED_ATTACK_INTENT_ONLY', combat_effect='UNKNOWN')
                result = await ingress.poll_async()
                self.assertFalse(ingress.pending)
                self.assertEqual(result['sequence'], sequence)
                if request['command'] == 'AttackTarget':
                    self.assertEqual(result['proof_scope'], 'VALIDATED_ATTACK_INTENT_ONLY')
                    self.assertEqual(result['combat_effect'], 'UNKNOWN')
                await ingress.poll_async()  # Same public seq is never resubmitted.
            self.assertEqual(calls, [('MoveGoal', 1, 2, 3), ('AttackTarget', 1, 47, 0), ('MoveGoal', 1, 1, 3)])
            consumer.poll.assert_not_called()

    async def test_attack_requires_opt_in_exact_keys_and_cancellation_is_terminal(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        base = dict(schema=REQUEST_SCHEMA, sequence=1, command='AttackTarget', uid=1, target_uid=2, map_id=0)
        for allow, request in ((False, base), (True, dict(base, x=1)),
                               (True, {key: value for key, value in base.items() if key != 'map_id'})):
            with self.subTest(allow=allow, keys=tuple(request)), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                consumer = SimpleNamespace(poll_async=AsyncMock(return_value=dict(status='READY')),
                                           submit_attack=Mock(), close=Mock())
                ingress = l.ManualMoveRequests(directory, consumer, allow_attack=allow)
                (directory / 'command.request.json').write_text(json.dumps(request))
                with self.assertRaises(ValueError):
                    await ingress.poll_async()
                consumer.submit_attack.assert_not_called()
                self.assertTrue(ingress.closed)
        with tempfile.TemporaryDirectory() as directory:
            consumer = SimpleNamespace(poll_async=AsyncMock(side_effect=asyncio.CancelledError()), close=Mock())
            ingress = l.ManualMoveRequests(Path(directory), consumer)
            with self.assertRaises(asyncio.CancelledError):
                await ingress.poll_async()
            self.assertTrue(ingress.closed)
            consumer.close.assert_called_once()


class SourceRestartIngressValidationTests(unittest.IsolatedAsyncioTestCase):
    def test_exact_background_sourcequit_parent_new_candidate_and_only_explicit_restart_capability(self):
        old = l.PRODUCTS['sibling-background-source-quit-spawn']
        candidate = l.PRODUCTS['sibling-background-source-restart-spawn']
        expected = dict(old, bridges={**old['bridges'], 'own-login-bridge-dg49.dll':
            'f3496b5075f069316b4a65db0242cc11f311bc5a0cc5920cceb3116223460902'},
            bridge_artifact=l.ROOT / 'work/local_original_session/implementation-1/manual-source-restart-code-gate/own-login-bridge-dg49.dll',
            manual_source_restart=True, require_source_quit=False)
        self.assertEqual(candidate, expected)
        self.assertTrue(candidate['require_background'])
        self.assertIs(candidate['require_source_quit'], False)
        self.assertNotIn('manual_source_restart', old)
        self.assertEqual(l.digest(candidate['bridge_artifact']), candidate['bridges']['own-login-bridge-dg49.dll'])
        self.assertEqual(old['bridges']['own-login-bridge-dg49.dll'],
            'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d')

    def test_restart_startup_without_sourcequit_reaches_preflight_before_native(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'run'
            args = ['launcher', '--run', '--control-mode', 'manual', '--background',
                '--image', str(Path(folder) / 'fixture.exe'), '--product', 'sibling-background-source-restart-spawn',
                '--expected-uuid', 'fixture', '--store', str(Path(folder) / 'store.json'),
                '--run-directory', str(directory)]
            with patch.object(l.sys, 'argv', args), \
                 patch.object(l, 'preflight', side_effect=ValueError('TEST_PREFLIGHT_REACHED')) as preflight, \
                 patch.object(l, 'NativeOwner') as owner, patch.object(l.socket, 'socket') as socket, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(l.main(), 2)
            preflight.assert_called_once_with(Path(folder) / 'fixture.exe', 'sibling-background-source-restart-spawn')
            owner.assert_not_called(); socket.assert_not_called()
            report = json.loads((directory / 'result.json').read_text())
            self.assertEqual((report['phase'], report['error_code']), ('BEFORE_NATIVE', 'TEST_PREFLIGHT_REACHED'))
            self.assertIs(report['native_executed'], False)
            self.assertIs(report['listeners_started'], False)
            self.test_exact_background_sourcequit_parent_new_candidate_and_only_explicit_restart_capability()

    async def test_lookalike_completed_dictionary_cannot_release_public_pending(self):
        result = dict(status='COMMITTED', reason=None, sequence=1, automatic_retry=False,
            cleanup_required=False, phase='COMMITTED', native_attempted=True, command='SourceRestart',
            proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY', response_drained=True, selection_cleared=True,
            ui='UNKNOWN', inventory_restore='UNKNOWN')
        with tempfile.TemporaryDirectory() as folder:
            consumer = SimpleNamespace(state=result, sequence=1, pending=None, allow_source_restart=True,
                poll_async=AsyncMock(return_value=dict(result)), close=Mock())
            wrapper = l.ManualMoveRequests(Path(folder), consumer, allow_source_restart=True)
            wrapper.sequence, wrapper.pending, wrapper._pending_command = 7, True, 'SourceRestart'
            with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'):
                await wrapper.poll_async()
            self.assertEqual((wrapper.last_result['status'], wrapper.last_result['sequence']), ('UNKNOWN', 7))
            self.assertTrue(wrapper.closed)
            consumer.close.assert_called_once()

    async def test_off_malformed_or_sync_request_never_claims_or_calls_native_consumer(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        request = dict(schema=REQUEST_SCHEMA, sequence=1, command='SourceRestart', uid=1, map_id=0)
        cases = [(False, True, request), (True, False, request)]
        cases += [(True, True, dict(request, **edit)) for edit in
            ({'uid': True}, {'uid': 0}, {'uid': 1 << 64}, {'map_id': False}, {'map_id': -1},
             {'map_id': 1 << 31}, {'extra': 0}, {'sequence': True})]
        cases.append((True, True, {k: v for k, v in request.items() if k != 'map_id'}))
        for allow, asynchronous, value in cases:
            with self.subTest(allow=allow, asynchronous=asynchronous, value=value), tempfile.TemporaryDirectory() as folder:
                consumer = SimpleNamespace(poll=lambda: dict(status='READY'),
                    poll_async=AsyncMock(return_value=dict(status='READY')), submit_source_restart=Mock(), close=Mock())
                wrapper = l.ManualMoveRequests(Path(folder), consumer, allow_source_restart=allow)
                (Path(folder) / 'command.request.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    if asynchronous:
                        await wrapper.poll_async()
                    else:
                        wrapper.poll()
                consumer.submit_source_restart.assert_not_called()
                self.assertEqual(wrapper.sequence, 0)
                self.assertFalse((Path(folder) / 'command.result.json').exists())
        for bad in (0, 1, None, 'True'):
            with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, 'SOURCE_RESTART_CAPABILITY_BOOL'):
                l.ManualMoveRequests(Path(folder), SimpleNamespace(), allow_source_restart=bad)


class SourceReselectIngressValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_off_and_caller_reference_never_claim_or_dispatch(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        request = dict(schema=REQUEST_SCHEMA, sequence=1, command='SourceReselect', uid=1, map_id=0)
        for value in (request, dict(request, reference='caller-controlled')):
            with tempfile.TemporaryDirectory() as folder:
                consumer = SimpleNamespace(poll_async=AsyncMock(return_value=dict(status='READY')),
                                           submit_source_reselect=Mock(), close=Mock())
                wrapper = l.ManualMoveRequests(Path(folder), consumer)
                (Path(folder) / 'command.request.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    await wrapper.poll_async()
                self.assertEqual(wrapper.sequence, 0)
                consumer.submit_source_reselect.assert_not_called()
                self.assertFalse((Path(folder) / 'command.result.json').exists())
        for bad in (0, 1, None, 'true'):
            with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, 'SOURCE_RESELECT_CAPABILITY_BOOL'):
                l.ManualMoveRequests(Path(folder), SimpleNamespace(), allow_source_reselect=bad)

    def test_existing_product_capabilities_never_enable_reselection_by_policy_alone(self):
        from tools.local_original_session import feature_config_tests, feature_config
        config = feature_config.parse(feature_config_tests.InventoryReselectionConfigTests().enabled())
        for product in ('sibling-background-source-restart-spawn', 'sibling-background-source-quit-spawn',
                        'sibling-background-use-item-source-quit-spawn',
                        'sibling-background-inventory-update-source-quit-spawn'):
            factory = l.ProductFeatureFactory(None, product=product, control_mode='manual',
                                              directory=Path('.'), config=config)
            self.assertFalse(factory.allow_source_reselect)

    def test_new_profile_exact_candidate_inherits_only_explicit_background_restart_settings(self):
        from tools.local_original_session import feature_config_tests, feature_config
        product = 'sibling-background-source-reselect-spawn'
        parent, actual = l.PRODUCTS['sibling-background-source-restart-spawn'], l.PRODUCTS[product]
        for key in parent:
            if key not in ('bridges', 'bridge_artifact'): self.assertEqual(actual[key], parent[key])
        self.assertIs(actual['manual_source_reselect'], True)
        self.assertIs(actual['require_background'], True)
        self.assertIs(actual['require_source_quit'], False)
        self.assertEqual(actual['bridges']['own-login-bridge-dg49.dll'],
                         'bd24d868ad95394a9ed48ba1368afce805836ee58e5cb83435295e47746af1a9')
        self.assertEqual(l.digest(actual['bridge_artifact']), actual['bridges']['own-login-bridge-dg49.dll'])
        configured = feature_config.parse(feature_config_tests.InventoryReselectionConfigTests().enabled())
        for config, expected in ((configured, True), (feature_config.Features(), False)):
            factory = l.ProductFeatureFactory(None, product=product, control_mode='manual',
                                              directory=Path('.'), config=config)
            self.assertIs(factory.allow_source_reselect, expected)


class SourceRestartProductTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tools.local_original_session import manual_move_commands_tests as fixture, feature_config, restart
        for name in ('adapter', 'native_result', 'receive_restart'):
            setattr(self, name, types.MethodType(getattr(fixture.ManualSourceRestartTests, name), self))
        await fixture.ManualSourceRestartTests.asyncSetUp(self)
        from tools.local_original_session.desktop_tests import DesktopTests
        desktop_native, self.menu_state = DesktopTests().fake_native()
        owner = l.NativeOwner.__new__(l.NativeOwner)
        owner.__dict__.update(vars(self.owner))
        owner.image = Path(self.reader.member.identity['image'])
        self.reader.member.identity['image'] = str(owner.image)
        owner.child.members = {owner.child.pid: owner.child}
        owner.source_guard = self.producer.source_guard
        owner.native.handles, owner.file_pins = [999], ((999, b'fixture-file-identity'),)
        owner._file_identity = lambda handle: b'fixture-file-identity'  # Native file-handle IO only.
        for name, fn in vars(desktop_native.u).items():
            setattr(owner.native.u, name, fn)
        owner.native.k.GetCurrentThreadId = desktop_native.k.GetCurrentThreadId
        owner.native.u.IsWindow = Fn(lambda hwnd: hwnd == 500)
        owner.private_desktop = l.PrivateDesktop(owner.native)
        owner.internal, owner.background = False, True
        self.addCleanup(owner.private_desktop.close)
        self.owner = self.reader.owner = self.policy.owner = owner
        self.producer.source_guard = owner.verify_sources
        self.menu_callback, self.menu_events, self.menu_fail_at = None, [], None
        post = owner.native.u.PostMessageW
        def posted(*args):
            if args[1] == 0x10:
                self.menu_events.append((threading.get_ident(), self.menu_state['threads'].get(threading.get_ident(), 11), args))
                if self.menu_callback:
                    self.menu_callback()
                return len(self.menu_events) != self.menu_fail_at
            return post(*args)
        owner.native.u.PostMessageW = Fn(posted)
        # The real runner installs this observation wrapper. Menu preparation
        # must call the original class implementation, never this callback.
        owner.request_close = Mock(side_effect=AssertionError('runner close wrapper must not be delegated to'))
        self.run = self.directory
        self.factory = l.ProductFeatureFactory(self.reader, product='sibling-background-source-restart-spawn',
            control_mode='manual', directory=self.run, config=feature_config.Features(restart_policy=restart.POLICY))
        self.runtime = self.factory(self.producer)
        self.consumer = self.runtime.manual.consumer
        self.consumer.clock_ns = lambda: self.now
        self.addCleanup(self.runtime.close)

    def publish_request(self, sequence=7):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position = self.realm.service(self.writer).snapshot()
        request = dict(schema=REQUEST_SCHEMA, sequence=sequence, command='SourceRestart',
                       uid=position.uid, map_id=position.map_id)
        (self.run / 'command.request.json').write_text(json.dumps(request))

    async def complete(self):
        from tools.local_original_session import manual_move_commands as m
        self.publish_request()
        wrapper = self.runtime.manual
        record, claims = wrapper._record, []
        def recorded(row):
            result = record(row)
            if row['status'] == 'CLAIMED': claims.append(wrapper.sequence)
            return result
        wrapper._record = recorded
        first = await wrapper.poll_async()
        self.assertEqual((first['status'], first['phase'], wrapper.sequence), ('PENDING', 'ADMISSION', 7))
        self.assertEqual(claims, [7]); self.assertFalse(self.posts)
        self.assertEqual(len(self.menu_events), 1)
        self.assertEqual(self.menu_events[0][1:], (55, (500, 0x10, 0, 0)))
        self.assertNotEqual(self.menu_events[0][0], threading.get_ident())
        self.owner.request_close.assert_not_called()
        samples, stamp = len(self.memory.calls), wrapper.last_sample_monotonic_ns
        self.assertEqual((await wrapper.poll_async())['phase'], 'ADMISSION')
        self.now += m.SAMPLE_NS - 1
        self.assertEqual((await wrapper.poll_async())['phase'], 'ADMISSION')
        self.assertEqual((len(self.memory.calls), wrapper.last_sample_monotonic_ns), (samples, stamp))
        self.assertEqual((self.consumer.sequence, self.consumer.pending['native_attempted']), (0, False))
        self.now += 1
        self.assertEqual((await wrapper.poll_async())['phase'], 'NATIVE_WAIT')
        self.assertEqual((len(self.posts), self.consumer.sequence), (1, 1))
        self.publish_request(8)
        self.assertEqual((await wrapper.poll_async())['sequence'], 7)
        self.assertEqual(self.consumer.sequence, 1)
        self.publish_request(7)
        self.native_result(); self.now += m.SAMPLE_NS
        self.assertEqual((await wrapper.poll_async())['status'], 'PENDING')  # RETURNED alone is not ACK.
        await self.receive_restart()
        self.now += m.SAMPLE_NS
        result = await wrapper.poll_async()
        self.assertEqual((result['status'], result['command'], result['sequence']), ('COMMITTED', 'SourceRestart', 7))
        return result

    async def test_real_factory_public_claim_native_return_settings_ack_drain_once(self):
        result = await self.complete()
        wrapper = self.runtime.manual
        self.assertEqual(result['proof_scope'], 'LOCAL_RESTART_ACK_DRAIN_ONLY')
        self.assertIs(result['response_drained'], True); self.assertIs(result['selection_cleared'], True)
        self.assertEqual((result['ui'], result['inventory_restore']), ('UNKNOWN', 'UNKNOWN'))
        self.assertFalse(wrapper.pending or wrapper.closed)
        self.assertIs(self.consumer._reservation, True)
        self.assertIsNone(self.game.selection)
        self.assertEqual((len(self.posts), self.writer.write.call_count, self.writer.drain.await_count), (1, 1, 1))
        self.assertEqual((await wrapper.poll_async())['sequence'], 7)
        self.assertEqual((len(self.posts), self.consumer.sequence), (1, 1))
        self.assertLessEqual((self.run / 'command.result.json').stat().st_size, 2048)

    async def test_actual_completion_scope_copy_fake_stale_null_and_pending_are_strict(self):
        await self.complete()
        wrapper, consumer = self.runtime.manual, self.consumer
        original = dict(consumer.state)
        self.assertTrue(wrapper._actual_source_restart_commit(original, asynchronous=True))
        for change in ({'proof_scope': 'OTHER'}, {'command': 'MoveGoal'}, {'response_drained': False},
                       {'selection_cleared': False}, {'sequence': True}, {'ui': True}, {'extra': 0}):
            bad = dict(original, **change); consumer.state = bad
            with self.subTest(change=change):
                self.assertFalse(wrapper._actual_source_restart_commit(bad, asynchronous=True))
        consumer.state = original
        for replacement in (copy.copy(consumer), None, SimpleNamespace(state=original)):
            wrapper.consumer = replacement
            self.assertFalse(wrapper._actual_source_restart_commit(original, asynchronous=True))
        wrapper.consumer = consumer
        consumer.pending = dict(kind='SourceRestart')
        self.assertFalse(wrapper._actual_source_restart_commit(original, asynchronous=True))
        consumer.pending = None
        consumer.sequence += 1
        self.assertFalse(wrapper._actual_source_restart_commit(original, asynchronous=True))
        consumer.sequence -= 1
        async def fake_poll(): return dict(original)
        with patch.object(consumer, 'poll_async', fake_poll):
            self.assertFalse(wrapper._actual_source_restart_commit(original, asynchronous=True))
        self.assertTrue(wrapper._actual_source_restart_commit(original, asynchronous=True))
        self.assertEqual(len(self.posts), 1)

    async def test_factory_two_gates_keep_old_product_and_unconfigured_candidate_off(self):
        from tools.local_original_session import feature_config, restart
        cases = (('sibling-background-source-quit-spawn', feature_config.Features(restart_policy=restart.POLICY)),
                 ('sibling-background-source-restart-spawn', feature_config.Features()))
        for index, (product, config) in enumerate(cases):
            directory = Path(self.temp.name) / ('restart-off-' + str(index)); directory.mkdir()
            factory = l.ProductFeatureFactory(self.reader, product=product, control_mode='manual',
                                              directory=directory, config=config)
            runtime = factory(self.producer)
            try:
                self.assertFalse(factory.allow_source_restart or runtime.manual.allow_source_restart
                                 or runtime.manual.consumer.allow_source_restart)
                from tools.local_original_session.commands import REQUEST_SCHEMA
                position = self.realm.service(self.writer).snapshot()
                request = dict(schema=REQUEST_SCHEMA, sequence=1, command='SourceRestart', uid=position.uid, map_id=0)
                (directory / 'command.request.json').write_text(json.dumps(request))
                with self.assertRaisesRegex(ValueError, 'SOURCE_RESTART_NOT_ENABLED'):
                    await runtime.manual.poll_async()
                self.assertEqual(runtime.manual.sequence, 0)
            finally:
                runtime.close()
        self.assertFalse(self.posts)
        self.assertFalse(self.menu_events)
        self.writer.write.assert_not_called()

    async def test_menu_zero_partial_failure_and_changed_owner_source_reader_are_terminal_once(self):
        for index, mode in enumerate(('zero', 'partial', 'owner', 'source', 'reader', 'method')):
            if index:
                await self.asyncSetUp()
            with self.subTest(mode=mode):
                if mode == 'zero':
                    self.owner.native.windows = lambda _: []
                elif mode == 'partial':
                    self.owner.native.windows = lambda _: [dict(hwnd=n, visible=True) for n in (500, 501)]
                    self.owner.native.owned_hwnd = lambda *args: True
                    self.menu_fail_at = 2
                elif mode == 'owner':
                    self.menu_callback = lambda: setattr(self.owner, 'closed', True)
                elif mode == 'source':
                    self.menu_callback = lambda: setattr(self.owner, 'source_guard', lambda: None)
                elif mode == 'reader':
                    self.menu_callback = lambda: setattr(self.consumer, 'reader', copy.copy(self.reader))
                self.publish_request()
                guard = (patch.object(l.NativeOwner, 'request_close', Mock()) if mode == 'method'
                         else contextlib.nullcontext())
                with guard, self.assertRaises(ValueError):
                    await self.runtime.manual.poll_async()
                wrapper = self.runtime.manual
                self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
                self.assertIs(wrapper.last_result['native_attempted'], False)
                self.assertEqual(wrapper.sequence, 7)
                self.assertTrue(wrapper.closed)
                count = len(self.menu_events)
                self.assertEqual(count, 0 if mode in ('zero', 'method') else 2 if mode == 'partial' else 1)
                self.assertFalse(self.posts)
                self.assertEqual(self.memory.calls, [])
                await wrapper.poll_async()
                self.assertEqual(len(self.menu_events), count)
                self.writer.write.assert_not_called()

    async def test_menu_original_deadline_and_clock_never_extend_or_repost(self):
        from tools.local_original_session.manual_move_commands import WAIT_NS
        for index, mode in enumerate(('during_close', 'floor_wait', 'backward')):
            if index:
                await self.asyncSetUp()
            with self.subTest(mode=mode):
                if mode == 'during_close':
                    self.menu_callback = lambda: setattr(self, 'now', self.consumer.pending['started'] + WAIT_NS)
                elif mode == 'backward':
                    self.menu_callback = lambda: setattr(self, 'now', self.now - 1)
                self.publish_request()
                wrapper = self.runtime.manual
                if mode == 'floor_wait':
                    result = await wrapper.poll_async()
                    self.assertEqual(result['phase'], 'ADMISSION')
                    started = self.consumer.pending['started']
                    self.now = started + WAIT_NS
                with self.assertRaises(ValueError):
                    await wrapper.poll_async()
                self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
                self.assertEqual(len(self.menu_events), 1)
                self.assertFalse(self.posts)
                self.assertEqual((self.consumer.sequence, self.memory.calls), (0, []))
                await wrapper.poll_async()
                self.assertEqual(len(self.menu_events), 1)

    async def test_menu_final_clock_callback_cannot_change_source_or_current_selection(self):
        for index, mode in enumerate(('source', 'selection')):
            if index:
                await self.asyncSetUp()
            wrapper, changed = self.runtime.manual, []
            def clock():
                if wrapper._source_restart_menu_attempted and self.menu_events and not changed:
                    changed.append(True)
                    if mode == 'source':
                        self.owner.source_guard = lambda: None
                    else:
                        self.game.selection = None
                return self.now
            self.consumer.clock_ns = clock
            self.publish_request()
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'MENU_BINDING_CHANGED'):
                await wrapper.poll_async()
            self.assertEqual(changed, [True])
            self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
            self.assertTrue(wrapper.closed)
            self.assertEqual(len(self.menu_events), 1)
            self.assertFalse(self.posts)
            self.assertEqual((self.consumer.sequence, self.memory.calls), (0, []))

    async def test_menu_cancellation_propagates_and_never_reposts_or_publishes_native(self):
        task = asyncio.current_task()
        self.menu_callback = lambda: task.cancel()
        self.publish_request()
        with self.assertRaises(asyncio.CancelledError):
            await self.runtime.manual.poll_async()
        task.uncancel()
        self.assertEqual(self.runtime.manual.last_result['reason'], 'FEATURE_SOURCE_RESTART_MENU_CANCELLED')
        self.assertTrue(self.runtime.manual.closed)
        self.assertEqual(len(self.menu_events), 1)
        self.assertFalse(self.posts)
        self.assertEqual((self.consumer.sequence, self.memory.calls), (0, []))
        await self.runtime.manual.poll_async()
        self.assertEqual(len(self.menu_events), 1)
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass

    async def test_other_explicit_move_uses_original_native_path_without_menu_request(self):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position = self.realm.service(self.writer).snapshot()
        (self.run / 'command.request.json').write_text(json.dumps(dict(schema=REQUEST_SCHEMA,
            sequence=7, command='MoveGoal', uid=position.uid, x=position.word0 + 1, y=position.word1)))
        result = await self.runtime.manual.poll_async()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'NATIVE_WAIT'))
        self.assertEqual((len(self.posts), self.consumer.sequence), (1, 1))
        self.assertFalse(self.menu_events)
        self.assertIs(self.runtime.manual._source_restart_menu_attempted, False)
        self.owner.request_close.assert_not_called()

    async def reselection_fixture(self, product='sibling-background-source-restart-spawn'):
        from tools.local_original_session import broker, broker_tests, feature_config as fc, inventory, inventory_tests
        from tools.local_original_session import inventory_store, npc_observe, restart
        from tools.local_original_session.attack_action_observe_tests import full_retained_reader
        # Compose the two existing real fixtures. Keep B's retained owner/IPC and
        # SettingsStore; I2 provides actual generation/Store/selection routes.
        settings, full_memory = self.realm.settings, dict(self.memory.data)
        fixture = broker_tests.InventoryReselectionTests
        for name in ('rebuild', 'dispatch', 'select', 'reset_writes', 'restart_reselect'):
            setattr(self, name, types.MethodType(getattr(fixture, name), self))
        self.wire = inventory.build_add(inventory_tests.explicit_fields())
        grant = broker.LocalRealm.grant
        def owned_grant(realm, writer, **options):
            async def account(current_writer):
                return await self.producer._account_owner(current_writer, self.row)
            return grant(realm, writer, **dict(options, account_owner_guard=account))
        # I2's inventory-only fixture has no Settings route guard; compose B's
        # original broker account callback at construction, never a True stub.
        with patch.object(broker.LocalRealm, 'grant', owned_grant):
            await self.rebuild()
        self.producer.source_guard = self.owner.verify_sources
        self.memory.data = full_memory | self.memory.data
        self.realm.settings = settings
        InventoryProductTests.product_clock(self)
        self.now = self.product_ns
        config = fc.Features(inventory_policy=inventory.POLICY, inventory_frame=self.producer._inventory_config_frame,
            inventory_store_policy=inventory_store.POLICY, inventory_delivery_policy=fc.LOCAL_WORLD_READY_ONCE,
            inventory_reselection_policy=fc.LOCAL_SAVED_ROW_ON_RESELECTION, restart_policy=restart.POLICY)
        self.factory = l.ProductFeatureFactory(self.reader, product=product,
            control_mode='manual', directory=self.run, config=config)
        self.runtime = self.factory(self.producer); self.addCleanup(self.runtime.close)
        wrapper = self.runtime.manual
        self.consumer = wrapper.consumer; self.consumer.clock_ns = lambda: self.product_ns
        self.monitor = obs.SessionMonitor.__new__(obs.SessionMonitor)
        self.monitor.reader, self.monitor.owner = self.reader, self.reader.owner
        self.monitor.next_memory, self.monitor.samples = 0, 1
        self.monitor.last_memory = dict(status='OBSERVED', current='Land', pending='none', root_ready=True)
        self.monitor.last_world = dict(status='OBSERVED', scene='Land', pending='none', stable_double_read=True,
            my_player_uid=self.realm.profile_uid, map_requested_i32=0, map_resolved_i32=0)
        await self.runtime.poll(self.monitor)
        self.monitor.samples += 1; self.product_ns += 500_000_000
        self.assertEqual((await self.runtime.poll(self.monitor))['manual_move']['phase'], 'CLIENT_WAIT')
        InventoryPersistenceProductTests.materialize(self)
        self.product_ns += 500_000_000
        self.assertEqual((await self.runtime.poll(self.monitor))['manual_move']['status'], 'COMMITTED')
        old, old_observer = wrapper._inventory_generation, wrapper._inventory_observer
        self.observer = npc_observe.NpcObserver(self.producer, self.reader)
        self.realm.edge_passability = self.realm.service(self.writer)._edge_passability = self.observer.proof
        self.memory.actors = 0x300000
        inventory_pair = self.memory.read(0x220000 + 48, 16)
        full_retained_reader(self)
        # Extend the existing full-reader projection without replacing its
        # Inventory pair: CharacterData occupies the following real slot.
        self.memory.put(0x220000 + 48, '<16s', inventory_pair)
        self.memory.put(0x220000 + 64, '<QQ', 0x600000, 0x250000)
        self.memory.put(0x210000 + self.memory.c['layout']['GI_end'], '<Q', 0x220000 + 80)
        self.reset_writes()
        return old, old_observer

    async def test_reselection_on_actual_old_generation_none_handoff_then_active_rebind(self):
        old, old_observer = await self.reselection_fixture()
        wrapper = self.runtime.manual
        self.publish_request()
        self.product_ns += 500_000_000
        record = wrapper._record
        def recorded(row):
            if row.get('status') == 'UNKNOWN':
                print('reselection_source_restart_original_reason=' + str(row.get('reason')))
                print('reselection_source_restart_observation=' + json.dumps(row.get('observation', {}), sort_keys=True))
            return record(row)
        wrapper._record = recorded
        try:
            admitted = (await self.runtime.poll(self.monitor))['manual_move']
        except ValueError:
            print('reselection_source_restart_admission_reason=' + str(self.consumer.state.get('reason')))
            raise
        self.assertEqual(admitted['phase'], 'ADMISSION')
        self.product_ns += 500_000_000
        self.assertEqual((await self.runtime.poll(self.monitor))['manual_move']['phase'], 'NATIVE_WAIT')
        self.native_result()
        await self.receive_restart()
        self.assertIsNone(self.producer.inventory_selection_current(self.writer))
        self.assertEqual(old.phase, 'RETIRED')
        self.product_ns += 500_000_000
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((result['status'], result['command'], result['sequence']), ('COMMITTED', 'SourceRestart', 7))
        self.assertFalse(wrapper.pending or wrapper.closed)
        self.product_ns += 500_000_000
        self.assertEqual((await self.runtime.poll(self.monitor))['manual_move'], result)
        self.assertTrue(old_observer._closed)
        await self.select()
        self.service = self.producer._inventory_service
        self.reset_writes()
        new = self.producer.inventory_selection_current(self.writer)
        self.assertIs(wrapper._inventory_source_restart_reservation(new, old), old.restart_state)
        restart_state = new.restart_state
        new.restart_state = dict(restart_state)
        self.assertIsNone(wrapper._inventory_source_restart_reservation(new, old))
        new.restart_state = restart_state
        await wrapper.poll_async(monitor=self.monitor)
        self.assertIs(wrapper._inventory_generation, new); self.assertIs(new.previous, old)
        self.assertIsNot(wrapper._inventory_observer, old_observer)
        self.assertEqual((wrapper.sequence, self.consumer.sequence), (7, 1))
        self.assertIs(self.consumer._reservation, True)
        self.assertFalse(new.attempted or new.service._claimed or wrapper.pending)
        self.writer.write.assert_not_called()
        self.assertEqual(len(self.posts), 1)


class SourceReselectProductTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the existing actual owner/PrivateDesktop and real saved-generation
    # fixture; only its native OS IO is mocked by the original fixture.
    asyncSetUp = SourceRestartProductTests.asyncSetUp
    publish_request = SourceRestartProductTests.publish_request
    reselection_fixture = SourceRestartProductTests.reselection_fixture

    async def prepare_reselect(self):
        from tools.local_original_session import manual_move_commands_tests as fixture
        self.old, self.old_observer = await self.reselection_fixture('sibling-background-source-reselect-spawn')
        self.wrapper = self.runtime.manual
        self.claims = []
        original = self.wrapper._record
        def record(row):
            if row['status'] == 'CLAIMED': self.claims.append(self.wrapper.sequence)
            return original(row)
        self.wrapper._record = record
        self.publish_request(7)
        await self.advance()
        await self.advance()
        self.native_result()
        await self.receive_restart()
        result = await self.advance()
        self.assertEqual((result['status'], result['command']), ('COMMITTED', 'SourceRestart'))
        self.assertTrue(self.old.service._closed)
        fixture.ManualSourceReselectTests.scene(self, 'Select')
        self.old_position = self.consumer._source_restart_completed['initial']
        from tools.local_original_session.commands import REQUEST_SCHEMA
        self.reselect_request = dict(schema=REQUEST_SCHEMA, sequence=8, command='SourceReselect',
            uid=self.old_position.uid, map_id=self.old_position.map_id)
        (self.run / 'command.request.json').write_text(json.dumps(self.reselect_request))
        result = await self.advance()
        self.assertEqual((result['status'], result['phase'], result['sequence']), ('PENDING', 'ADMISSION', 8))
        self.assertEqual(self.claims, [7, 8])
        self.assertEqual(len(self.menu_events), 1)  # Restart only; Reselect has no menu Post.
        self.first_deadline = self.wrapper._source_reselect_started_ns + 10_000_000_000

    async def advance(self):
        self.product_ns += 500_000_000
        return (await self.runtime.poll(self.monitor))['manual_move']

    async def land_ready(self):
        from tools.local_original_session import manual_move_commands_tests as fixture
        result = await self.advance()
        self.assertEqual((result['phase'], self.consumer.sequence), ('NATIVE_WAIT', 2))
        fixture.ManualSourceReselectTests.native_result(self)
        self.assertEqual((await self.advance())['phase'], 'ADMISSION')
        self.assertEqual((await self.advance())['phase'], 'NATIVE_WAIT')
        self.assertEqual(self.consumer.sequence, 3)
        fixture.ManualSourceReselectTests.native_result(self)
        self.assertEqual((await self.advance())['status'], 'PENDING')
        self.assertEqual(self.writer.write.call_count, 1)  # Real Restart ACK only; Settings is C2S.
        await fixture.ManualSourceReselectTests.receive_selection(self)  # Real policy rx + route + ENTER/world drain.
        self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500000, 0x500040)
        fixture.ManualSourceReselectTests.scene(self, 'Land')
        self.reset_writes()
        result = await self.advance()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'INVENTORY_RESTORE'), result)
        self.assertEqual(result['selection_proof_scope'], 'LOCAL_RESELECT_LAND_READY_ONLY')
        self.assertTrue(self.wrapper.pending)
        self.writer.write.assert_not_called()

    async def test_actual_two_phase_then_same_public_saved_add_and_client_five_scalars_once(self):
        await self.prepare_reselect()
        await self.land_ready()
        proof, native_state = self.consumer._source_reselect_completed, self.consumer.state
        result = await self.advance()  # New observer binds; old monitor sample cannot trigger.
        new_observer = self.wrapper._inventory_observer
        self.assertIsNot(new_observer, self.old_observer)
        self.assertTrue(self.old_observer._closed)
        self.assertIs(self.wrapper._inventory_generation, proof[1])
        self.assertFalse(proof[1].attempted or proof[1].service._claimed)
        self.writer.write.assert_not_called()
        self.monitor.samples += 1
        result = await self.advance()
        self.assertEqual((result['phase'], result['sequence'], result['command']), ('CLIENT_WAIT', 8, 'SourceReselect'))
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(self.wrapper._inventory_started_ns + 10_000_000_000, self.first_deadline)
        self.assertEqual(self.claims, [7, 8])
        self.assertIs(self.consumer.state, native_state)
        self.assertIs(self.wrapper._source_reselect_proof, proof)
        stamp, reads = self.wrapper.last_sample_monotonic_ns, len(self.memory.calls)
        await self.runtime.poll(self.monitor)
        self.assertEqual((self.wrapper.last_sample_monotonic_ns, len(self.memory.calls)), (stamp, reads))
        InventoryPersistenceProductTests.materialize(self)
        result = await self.advance()
        self.assertEqual((result['status'], result['phase'], result['sequence']), ('COMMITTED', 'CLIENT_CONFIRMED', 8))
        self.assertEqual(result['proof_scope'], 'CLIENT_SAVED_ITEM_ROW_SCALARS_AFTER_RESELECT')
        self.assertEqual(result['client_inventory'], 'ROW_5_SCALARS_MATCHED')
        self.assertTrue(result['native_attempted'])
        self.assertFalse(self.wrapper.pending or self.wrapper.closed)
        self.assertEqual((self.consumer.sequence, len(self.posts), len(self.menu_events)), (3, 3, 1))
        for _ in range(2): self.assertEqual((await self.advance())['status'], 'COMMITTED')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual((self.wrapper.sequence, self.consumer.sequence, self.claims), (8, 3, [7, 8]))
        self.assertTrue(self.wrapper.quiesce_for_source_quit())

    async def test_native_only_partial_selection_retains_original_deadline_no_inventory_send(self):
        await self.prepare_reselect()
        self.product_ns = self.first_deadline
        calls = self.writer.write.call_count
        with self.assertRaisesRegex(ValueError, 'SOURCE_RESELECT_ORIGINAL_DEADLINE'):
            await self.runtime.poll(self.monitor)
        self.assertEqual(self.wrapper.last_result['status'], 'UNKNOWN')
        self.assertEqual(self.wrapper.last_result['command'], 'SourceReselect')
        self.assertFalse(self.wrapper.last_result['native_attempted'])
        self.assertTrue(self.wrapper.closed)
        self.assertEqual(self.writer.write.call_count, calls)

    async def test_completed_private_proof_or_state_copy_cannot_authorize_restore(self):
        await self.prepare_reselect()
        await self.land_ready()
        original = self.consumer._source_reselect_completed
        for changed in (None, tuple(list(original)), (dict(original[0]), *original[1:])):
            self.consumer._source_reselect_completed = changed
            with self.assertRaises(ValueError): self.wrapper._source_reselect_current()
            self.writer.write.assert_not_called()
        self.consumer._source_reselect_completed = original
        state = self.consumer.state
        for changed in (dict(state), dict(state, proof_scope='UNVERIFIED_RESELECT')):
            self.consumer.state = changed
            with self.assertRaises(ValueError): self.wrapper._source_reselect_current()
            self.writer.write.assert_not_called()
        self.consumer.state = state
        self.consumer._source_reselect_completed = tuple(list(original))
        with self.assertRaisesRegex(ValueError, 'SOURCE_RESELECT_REAL_PROOF'):
            await self.advance()
        self.assertTrue(self.wrapper.closed)
        self.assertEqual(self.wrapper.last_result['status'], 'UNKNOWN')
        self.writer.write.assert_not_called()

    async def test_forged_native_completion_shape_without_real_completion_is_terminal(self):
        await self.prepare_reselect()
        forged = dict(status='COMMITTED', reason=None, sequence=self.consumer.sequence,
            automatic_retry=False, cleanup_required=False, phase='COMMITTED', native_attempted=True,
            command='SourceReselect', proof_scope='LOCAL_RESELECT_LAND_READY_ONLY',
            selection_changed=True, world_ready=True, ui='UNKNOWN', inventory_restore='UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'):
            self.wrapper._receive(forged, asynchronous=True)
        self.assertEqual(self.wrapper.last_result['status'], 'UNKNOWN')
        self.assertEqual(self.consumer.pending['kind'], 'SourceReselect')
        self.assertEqual((self.consumer.sequence, len(self.posts)), (1, 1))
        self.assertEqual(self.writer.write.call_count, 1)  # Only old Restart ACK.

    async def test_public_deadline_clock_callback_cancel_stops_before_next_native_phase(self):
        await self.prepare_reselect()
        clock = self.consumer.clock_ns
        task = None
        def cancelled():
            task.cancel()
            return clock()
        self.consumer.clock_ns = cancelled
        task = asyncio.create_task(self.wrapper.poll_async(monitor=self.monitor))
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(self.wrapper.closed)
        self.assertEqual((self.wrapper.last_result['status'], self.wrapper.last_result['command']),
                         ('UNKNOWN', 'SourceReselect'))
        self.assertEqual((self.consumer.sequence, len(self.posts)), (1, 1))
        self.assertEqual(self.writer.write.call_count, 1)


class ProductFeatureManualTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_replacement_capability_reaches_real_consumer_only_with_explicit_attack_config(self):
        from tools.local_original_session import feature_config
        await self.attack_fixture()
        configured = feature_config.Features(spawns=(self.realm._npc_spawns[0][0],),
                                             attack_policy=feature_config.ATTACK_INTENT_POLICY)
        new = 'sibling-background-move-attack-target-spawn'
        cases = ((new, configured, True), (new, feature_config.Features(), False),
                 ('sibling-manual-move-continuous-spawn', configured, False),
                 ('sibling-manual-move-attack-target-spawn', configured, False))
        for index, (product, config, expected) in enumerate(cases):
            directory = self.directory / ('replacement-' + str(index)); directory.mkdir()
            factory = l.ProductFeatureFactory(self.reader, product=product, control_mode='manual',
                                              directory=directory, config=config)
            runtime = factory(self.producer)
            self.assertIs(factory.allow_attack_replacement, expected)
            self.assertIs(runtime.manual.consumer.allow_attack_replacement, expected)
            runtime.close()
        self.assertEqual(self.posts, [])
        self.writer.write.assert_not_called()

    async def rejection_fixture(self):
        from tools.local_original_session import manual_move_commands_tests as fixture, feature_config
        for name in ('memory', 'sample', 'native_result', 'move', 'install_backward_producer', 'backward_producer_sample'):
            setattr(self, name, types.MethodType(getattr(fixture.ManualMoveTests, name), self))
        await fixture.ManualMoveTests.asyncSetUp(self)
        factory = l.ProductFeatureFactory(self.reader, product='sibling-manual-move-continuous-spawn',
            control_mode='manual', directory=self.directory, config=feature_config.Features())
        self.runtime = factory(self.producer)
        self.consumer = self.runtime.manual.consumer
        self.consumer.clock_ns = lambda: self.now
        self.submit = self.runtime.manual.poll
        from tools.local_original_session.commands import REQUEST_SCHEMA
        def publish(sequence):
            position = self.service.snapshot()
            (self.directory / 'command.request.json').write_text(json.dumps(dict(schema=REQUEST_SCHEMA,
                sequence=sequence, command='MoveGoal', uid=position.uid, x=position.word0 + 1, y=position.word1)))
        self.publish_move = publish
        publish(2)
        await fixture.ManualMoveTests.reject_after_clear_admission(self)
        self.install_backward_producer()
        self.assertEqual((await self.runtime.poll())['manual_move']['status'], 'PENDING')
        self.back_mode = 'idle'
        self.now += fixture.m.SAMPLE_NS
        return fixture

    async def test_real_product_rejected_public_sequence_ends_once_then_new_explicit_move_commits(self):
        fixture = await self.rejection_fixture()
        wrapper = self.runtime.manual
        rejected = (await self.runtime.poll())['manual_move']
        self.assertEqual((rejected['status'], rejected['sequence'], rejected['native_sequence']), ('REJECTED', 2, 1))
        self.assertEqual(rejected['proof_scope'], 'SC4EE0_DRAIN_WITH_CLIENT_SETTLED')
        self.assertFalse(rejected['accepted'] or rejected['cleanup_required'] or rejected['automatic_retry'])
        self.assertFalse(wrapper.pending or wrapper.closed)
        self.assertFalse(wrapper.quiesce_for_source_quit())  # Existing host still requires COMMITTED/READY.
        before = self.service._store.path.read_bytes() if self.service._store.path.exists() else None
        self.assertEqual(before, self.rejection_saved)
        self.assertIs(self.service.snapshot(), self.rejection_initial)
        self.assertEqual((self.service.requests_received, self.service.committed, self.service.corrections_prepared), (1, 0, 1))
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(self.writer.write.call_args.args[0], self.rejection_frames[0])
        for _ in range(2):
            self.assertEqual((await wrapper.poll_async())['status'], 'REJECTED')
        self.assertEqual(self.consumer.sequence, 1)
        self.assertEqual(len(self.posts), 1)
        self.publish_move(2)
        self.assertEqual(wrapper.poll()['status'], 'REJECTED')
        self.assertEqual(len(self.posts), 1)
        self.f.put(self.blocked_cell, '<H', 0)
        self.publish_move(5); self.now += fixture.m.SAMPLE_NS
        self.assertEqual((await self.runtime.poll())['manual_move']['status'], 'PENDING')
        self.assertEqual(self.consumer.sequence, 2)
        self.native_result(); await self.move()
        committed = (await self.runtime.poll())['manual_move']
        self.assertEqual((committed['status'], committed['sequence']), ('COMMITTED', 5))
        self.assertFalse(wrapper.pending)
        self.assertTrue(wrapper.quiesce_for_source_quit())  # Success restores the unchanged host handoff.
        self.assertEqual((self.service.requests_received, self.service.committed, self.service.corrections_prepared), (2, 1, 1))
        self.assertEqual([post[2] for post in self.posts], [1, 2])

    async def test_exact_rejection_shape_other_command_and_changed_producer_cannot_release_pending(self):
        await self.rejection_fixture()
        wrapper = self.runtime.manual
        actual = self.consumer.poll()
        self.assertEqual(actual['status'], 'REJECTED')
        expected = dict(actual)
        variants = [dict(actual, **{key: value}) for key, value in (
            ('reason', 'OTHER_REJECTION'), ('command', 'AttackTarget'), ('command', 'AddInventory'),
            ('accepted', True), ('cleanup_required', True), ('native_attempted', False),
            ('proof_scope', 'SC4EE0_DRAIN_ONLY'), ('moving_back_snapshot_observed', False),
            ('moving_back_start_observed', True), ('automatic_retry', True), ('sequence', True))]
        for row in variants:
            self.consumer.state = row
            with self.subTest(changed=row): self.assertFalse(wrapper._actual_move_rejection(row, asynchronous=True))
        self.consumer.state = expected
        self.assertTrue(wrapper._actual_move_rejection(expected, asynchronous=True))
        wrapper._pending_command = 'AttackTarget'
        with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'):
            await wrapper.poll_async()
        self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
        self.assertTrue(wrapper.closed)
        self.assertEqual(len(self.posts), 1)

    async def test_real_rejection_original_producer_source_and_function_are_required(self):
        await self.rejection_fixture()
        wrapper = self.runtime.manual
        original = self.consumer.poll()
        self.assertEqual(original['status'], 'REJECTED')
        with patch.object(l, '_MANUAL_REJECTION_SOURCE_SHA', '0' * 64):
            self.assertFalse(wrapper._actual_move_rejection(original, asynchronous=True))
        async def fake(consumer): return dict(consumer.state)
        with patch.object(type(self.consumer), 'poll_async', fake):
            with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'): await wrapper.poll_async()
        self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
        self.assertTrue(wrapper.closed)
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.writer.write.call_count, 1)

    async def attack_fixture(self):
        from tools.local_original_session import manual_move_commands_tests as fixture
        for name in ('tiles', 'native_result', 'received', 'accepted_attack'):
            setattr(self, name, types.MethodType(getattr(fixture.ManualAttackTests, name), self))
        await fixture.ManualAttackTests.asyncSetUp(self)
        return fixture

    async def test_public_move_attack_move_uses_one_real_consumer_and_intent_proof_only(self):
        from tools.local_original_session import attack, feature_config
        from tools.local_original_session.commands import REQUEST_SCHEMA
        fixture = await self.attack_fixture()
        run = self.directory / 'public'
        run.mkdir()
        factory = l.ProductFeatureFactory(self.reader,
            product='sibling-manual-move-attack-target-spawn', control_mode='manual', directory=run,
            config=feature_config.Features(spawns=(self.realm._npc_spawns[0][0],),
                                            attack_policy=feature_config.ATTACK_INTENT_POLICY))
        runtime = factory(self.producer)
        ingress = runtime.manual
        self.consumer = ingress.consumer
        self.consumer.clock_ns = lambda: self.now
        claims = []
        record, post = ingress._record, self.owner.native.u.PostMessageW
        def recorded(row):
            result = record(row)
            if row['status'] == 'CLAIMED':
                claims.append(ingress.sequence)
            return result
        def posted(*args):
            self.assertIn(ingress.sequence, claims)
            return post(*args)
        ingress._record = recorded
        self.owner.native.u.PostMessageW = posted
        def publish(sequence, command, **values):
            (run / 'command.request.json').write_text(json.dumps(
                dict(schema=REQUEST_SCHEMA, sequence=sequence, command=command, **values)))
        position = self.service.snapshot()
        publish(2, 'MoveGoal', uid=position.uid, x=position.word0 + 1, y=position.word1)
        self.assertEqual((await ingress.poll_async())['phase'], 'NATIVE_WAIT')
        publish(5, 'AttackTarget', uid=position.uid, target_uid=self.mover.state.uid, map_id=0)
        await ingress.poll_async()
        self.assertEqual(len(self.posts), 1)
        self.native_result()
        await self.received(0x4e2b, attack._field(1, position.packed) + attack._field(2, 2))
        self.memory.grid(0x470000, [position.word0 + 1, position.word1])
        self.now += fixture.m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['status'], 'COMMITTED')
        self.assertEqual((await ingress.poll_async())['phase'], 'ADMISSION')
        self.now += fixture.m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['phase'], 'ADMISSION')
        self.now += fixture.m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['phase'], 'NATIVE_WAIT')
        publish(8, 'MoveGoal', uid=position.uid, x=position.word0, y=position.word1)
        self.native_result()
        await self.accepted_attack()
        self.now += fixture.m.SAMPLE_NS
        result = await ingress.poll_async()
        self.assertEqual((result['status'], result['command'], result['sequence']), ('COMMITTED', 'AttackTarget', 5))
        self.assertEqual((result['proof_scope'], result['combat_effect']), ('VALIDATED_ATTACK_INTENT_ONLY', 'UNKNOWN'))
        self.assertEqual(self.session.accepted_count, 1)
        self.now += fixture.m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['phase'], 'NATIVE_WAIT')
        current = self.service.snapshot()
        self.native_result()
        await self.received(0x4e2b, attack._field(1, current.packed) + attack._field(2, 6))
        self.memory.grid(0x470000, [position.word0, position.word1])
        self.now += fixture.m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['sequence'], 8)
        self.assertEqual(ingress.last_result['status'], 'COMMITTED')
        await ingress.poll_async()
        self.assertEqual(claims, [2, 5, 8])
        self.assertEqual([item[2] for item in self.posts], [1, 2, 3])
        self.assertEqual([item[1] for item in self.posts], [0xc123, 0xc124, 0xc123])
        self.assertEqual(self.service.committed, 2)
        self.assertIsNone(self.session.current_intent())  # Next move invalidates the old attacker authority.
        self.writer.write.assert_not_called()
        ingress.close()

    async def test_old_move_product_and_new_product_default_off_never_submit_attack(self):
        from tools.local_original_session import feature_config
        from tools.local_original_session.commands import REQUEST_SCHEMA
        await self.attack_fixture()
        configured = feature_config.Features(spawns=(self.realm._npc_spawns[0][0],),
                                             attack_policy=feature_config.ATTACK_INTENT_POLICY)
        for index, (product, config) in enumerate((('sibling-manual-move-continuous-spawn', configured),
                ('sibling-manual-move-attack-target-spawn', feature_config.Features()))):
            run = self.directory / ('disabled-' + str(index))
            run.mkdir()
            runtime = l.ProductFeatureFactory(self.reader, product=product, control_mode='manual',
                                              directory=run, config=config)(self.producer)
            self.assertFalse(runtime.manual.allow_attack)
            self.assertFalse(runtime.manual.consumer.allow_attack)
            (run / 'command.request.json').write_text(json.dumps(dict(schema=REQUEST_SCHEMA,
                sequence=1, command='AttackTarget', uid=self.service.snapshot().uid,
                target_uid=self.mover.state.uid, map_id=0)))
            with self.assertRaisesRegex(ValueError, 'FEATURE_MANUAL_ATTACK_NOT_ENABLED'):
                await runtime.manual.poll_async()
            self.assertTrue(runtime.manual.closed)
        self.assertEqual(self.posts, [])
        self.assertEqual(self.session.accepted_count, 0)
        self.writer.write.assert_not_called()

    async def test_existing_command_ingress_real_consumer_two_committed_goals_and_current_registry(self):
        from tools.local_original_session import manual_move_commands_tests as fixture, feature_config
        for name in ('memory', 'sample', 'native_result', 'move'):
            setattr(self, name, types.MethodType(getattr(fixture.ManualMoveTests, name), self))
        await fixture.ManualMoveTests.asyncSetUp(self)
        run = self.directory / 'run'
        run.mkdir()
        factory = l.ProductFeatureFactory(self.reader,
            product='sibling-manual-move-continuous-spawn', control_mode='manual', directory=run,
            config=feature_config.Features())
        features = factory(self.producer)
        self.consumer = features.manual.consumer
        self.consumer.clock_ns = lambda: self.now
        from tools.local_original_session.commands import REQUEST_SCHEMA
        for sequence in (7, 9):
            position = self.service.snapshot()
            request = dict(schema=REQUEST_SCHEMA, sequence=sequence, command='MoveGoal',
                           uid=position.uid, x=position.word0 + 1, y=position.word1)
            (run / 'command.request.json').write_text(json.dumps(request))
            self.assertEqual((await features.poll())['manual_move']['status'], 'PENDING')
            self.native_result()
            self.assertEqual((await features.poll())['manual_move']['status'], 'PENDING')
            await self.move()
            self.assertEqual((await features.poll())['manual_move']['status'], 'COMMITTED')
            self.assertEqual((await features.poll())['manual_move']['sequence'], sequence)
        self.assertEqual([post[2:] for post in self.posts], [(1, 0), (2, 0)])
        self.assertEqual((self.service.requests_received, self.service.committed), (2, 2))
        self.assertIs(l.current_manual_binding(self.producer).writer, self.writer)
        self.realm.registry.selected.clear()
        self.assertIsNone(l.current_manual_binding(self.producer))
        self.writer.write.assert_not_called()
        report = await l.run_session(FakeOwner([True, False]), FakeBroker, asyncio.Event(),
                                     poll_seconds=0, feature_factory=lambda _: features)
        self.assertFalse(report['normal_input_only'])
        self.assertEqual(report['features']['manual_move']['status'], 'COMMITTED')


class InventoryProductTests(unittest.IsolatedAsyncioTestCase):
    async def test_physical_prewrite_refusal_is_unknown_once_and_keeps_real_broker_for_quit(self):
        from tools.local_original_session import inventory
        self.producer.key_guard = lambda: True
        query = self.native.k.VirtualQueryEx
        def unreadable(handle, at, info, size):
            value = query(handle, at, info, size)
            if at == self.memory.header: info._obj.protect = 1
            return value
        self.native.k.VirtualQueryEx = unreadable
        self.publish()
        monitor = SimpleNamespace(next_memory=0)
        with self.assertRaises(inventory.PreWriteReadRefusal) as caught:
            await self.runtime.poll(monitor)
        error = caught.exception
        public = self.runtime.manual.last_result
        self.assertEqual((public['status'], public['phase'], public['refusal_reason'], public['stage']),
                         ('UNKNOWN', 'PRE_WRITE', 'region_not_readable', 'EMPTY_VECTOR'))
        self.assertIs(public['write_attempted'], False)
        self.assertNotIn('inventory_pre_write', public)  # Typed PRE_WRITE output is unchanged.
        self.assertFalse(self.producer.failure.is_set())
        self.assertFalse(self.row['failed'])
        self.assertIsNone(self.row['policy_row'].drain_started_ns)
        self.assertTrue(self.service._closed)
        self.assertIs(self.producer._inventory_prewrite_refusal[0], error)
        self.assertIsNone(self.producer._inventory_delivery_authority)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.assertEqual(monitor.next_memory, self.producer.inventory_sample_monotonic_ns / 1e9 + .5)
        self.assertTrue(self.runtime.manual.quiesce_for_source_quit())
        self.assertFalse(self.runtime.manual.pending or self.runtime.manual._polling)
        self.assertTrue(self.runtime.manual.closed)
        self.assertIsNone(self.runtime.manual.consumer.pending)
        self.assertIn(self.runtime.manual.consumer.state['status'], ('READY', 'COMMITTED'))
        self.assertIsNone(self.runtime.manual._inventory_request)
        self.assertIsNone(self.runtime.manual._inventory_wait)
        self.assertFalse(self.reader.closed)
        from dataclasses import replace
        movement = self.realm.service(self.writer)
        def final_key_guard():
            movement._position = replace(movement.snapshot())
            return True
        self.producer.key_guard = final_key_guard
        self.assertFalse(self.runtime.manual.quiesce_for_source_quit())
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)
        self.runtime.close()
        self.assertEqual(self.runtime.manual.consumer.state['status'], 'UNKNOWN')
        self.writer.write.assert_not_called()

    async def test_prewrite_plain_error_or_fresh_authority_loss_remains_failfast(self):
        from tools.local_original_session import inventory
        for mode in ('plain', 'owner', 'reserved', 'cancel'):
            await self.rebuild()
            self.producer.key_guard = lambda: True
            self.publish()
            checkpoint = self.producer._checkpoint
            calls = [0]
            async def changed(writer, row):
                calls[0] += 1
                if calls[0] == 2:
                    if mode == 'owner': self.reader.owner.closed = True
                    if mode == 'reserved': row['policy_row'].drain_started_ns = 1
                    if mode == 'cancel': asyncio.current_task().cancel()
                return await checkpoint(writer, row)
            self.producer._checkpoint = changed
            query = self.native.k.VirtualQueryEx
            def unreadable(handle, at, info, size):
                value = query(handle, at, info, size)
                if at == self.memory.header: info._obj.protect = 1
                return value
            self.native.k.VirtualQueryEx = unreadable
            guard = patch.object(inventory, '_source', side_effect=ValueError('region_not_readable')) if mode == 'plain' else contextlib.nullcontext()
            task = asyncio.create_task(self.runtime.manual.poll_async())
            with guard, self.subTest(mode=mode):
                with self.assertRaises(asyncio.CancelledError if mode == 'cancel' else ValueError):
                    await task
                self.assertTrue(self.producer.failure.is_set())
                self.assertIsNone(self.producer._inventory_prewrite_refusal)
                self.assertFalse(self.runtime.manual.quiesce_for_source_quit())
                self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
            self.reader.owner.closed = False
            self.native.k.VirtualQueryEx = query

    async def test_quiesce_unrequested_requires_exact_initial_native_state(self):
        wrapper = self.runtime.manual
        self.assertTrue(wrapper.quiesce_for_source_quit())
        self.assertTrue(wrapper.closed)
        self.assertEqual(wrapper.consumer.state['status'], 'READY')
        wrapper.consumer.sequence = 1
        self.assertFalse(wrapper.quiesce_for_source_quit())
        wrapper.consumer.sequence = 0
        wrapper.consumer.state['status'] = 'COMMITTED'
        self.assertFalse(wrapper.quiesce_for_source_quit())
        wrapper.close()
        self.assertEqual(wrapper.consumer.state['status'], 'UNKNOWN')

    async def test_prewrite_final_sync_owner_check_cancel_propagates_without_write(self):
        query = self.native.k.VirtualQueryEx
        def unreadable(handle, at, info, size):
            value = query(handle, at, info, size)
            if at == self.memory.header: info._obj.protect = 1
            return value
        self.native.k.VirtualQueryEx = unreadable
        calls = [0]
        def cancel_at_proof():
            if self.producer._inventory_prewrite_refusal is not None:
                calls[0] += 1
                asyncio.current_task().cancel()
            return True
        self.producer.key_guard = cancel_at_proof
        self.publish()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.create_task(self.runtime.manual.poll_async())
        self.assertEqual(calls, [1])
        self.assertTrue(self.producer.failure.is_set())
        self.assertTrue(self.row['failed'])
        self.assertIsNone(self.producer._inventory_prewrite_refusal)
        self.assertTrue(self.service._closed and self.runtime.manual.closed)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    def code_page_refusal(self, *, after=False):
        from tools.local_original_session import inventory
        checks = self.service._checks(self.memory.s, *inventory._source()[::2])
        target = self.memory.base + checks[0]['rva']
        query, hits = self.native.k.VirtualQueryEx, [0]
        def unreadable(handle, at, info, size):
            value = query(handle, at, info, size)
            if at == target:
                hits[0] += 1
                if not after or hits[0] == 2: info._obj.protect = 1
            return value
        self.native.k.VirtualQueryEx = unreadable
        return query, hits

    async def test_code_before_admission_wait_uses_next_shared_slot_once_write_and_client_confirm(self):
        self.product_clock(); self.producer.key_guard = lambda: True
        query, hits = self.code_page_refusal()
        self.publish()
        monitor = SimpleNamespace(next_memory=0)
        first = (await self.runtime.poll(monitor))['manual_move']
        wrapper = self.runtime.manual
        original = wrapper._inventory_started_ns
        request = wrapper._inventory_request
        authority = self.producer._inventory_prewrite_refusal[1]
        self.assertEqual((first['status'], first['phase'], first['stage'], first['sequence']),
                         ('PENDING', 'ADMISSION', 'CODE_GUARD_BEFORE_0001', 2))
        self.assertFalse(first['write_attempted'] or wrapper.closed or self.service._closed or self.service._claimed)
        self.assertFalse(self.row['operation_lock'].locked())
        self.assertIsNone(self.row['policy_row'].drain_started_ns)
        self.assertFalse(self.producer.failure.is_set())
        self.writer.write.assert_not_called()
        count = len(self.memory.calls)
        self.assertEqual(wrapper.poll()['phase'], 'ADMISSION')
        for _ in range(2):
            await self.runtime.poll(monitor)
            await wrapper.poll_async()
        self.assertEqual(len(self.memory.calls), count)
        self.assertEqual(hits, [1])
        self.assertEqual(monitor.next_memory, self.product_ns / 1e9 + .5)
        self.assertIs(wrapper._inventory_request, request)
        self.native.k.VirtualQueryEx = query
        self.product_ns += 500_000_000
        sent = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual((sent['status'], sent['phase']), ('PENDING', 'CLIENT_WAIT'))
        self.assertIs(self.producer._inventory_delivery_authority[0], authority[0])
        self.assertEqual(wrapper._inventory_started_ns, original)
        self.assertEqual(self.producer._inventory_deadline_ns, original + 10_000_000_000)
        self.assertIsNone(wrapper._inventory_request)
        self.assertIsNone(wrapper._inventory_observer.last_sample_monotonic_ns)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.materialize(); self.product_ns += 500_000_000
        done = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual((done['status'], done['proof_scope'], done['sequence']),
                         ('COMMITTED', 'CLIENT_ITEM_ROW_SCALARS_ONLY', 2))
        await wrapper.poll_async()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))

    async def test_code_before_all_fail_keeps_original_deadline_then_safe_typed_close(self):
        from tools.local_original_session import inventory
        self.product_clock(); self.producer.key_guard = lambda: True
        query, hits = self.code_page_refusal(); self.publish()
        first = await self.runtime.manual.poll_async()
        wrapper = self.runtime.manual
        captured = wrapper._inventory_diagnostic_capture()
        original = wrapper._inventory_started_ns
        self.product_ns += 500_000_000
        self.assertEqual((await wrapper.poll_async())['phase'], 'ADMISSION')
        self.assertEqual(hits, [2])
        self.assertEqual(wrapper._inventory_started_ns, original)
        count = len(self.memory.calls)
        self.product_ns = original + 10_000_000_000
        with self.assertRaises(inventory.PreWriteReadRefusal) as caught: await wrapper.poll_async()
        self.assertEqual(len(self.memory.calls), count)
        self.assertEqual((wrapper.last_result['status'], wrapper.last_result['reason']),
                         ('UNKNOWN', 'FEATURE_INVENTORY_ADMISSION_DEADLINE'))
        diagnostic = wrapper.last_result['inventory_pre_write']
        self.assertEqual(diagnostic, {key: self.service.last_result[key] for key in
                         ('pre_write_stage', 'typed_read_requests', 'changed_read', 'refused_read')})
        self.assertIsNone(diagnostic['changed_read'])
        original = dict(self.service.last_result['refused_read'])
        self.assertEqual(diagnostic['refused_read'], caught.exception.refused_read)
        self.assertIsNot(diagnostic['refused_read'], self.service.last_result['refused_read'])
        self.assertLessEqual((self.run / 'command.result.json').stat().st_size, 2048)
        # Invalid optional evidence never replaces the original refusal, reads
        # again, or creates write/retry authority. The other three keys survive.
        for change in ({'extra': 1}, {'at': True}, {'size': 0}, {'image_base': -1},
                       {'requested_bytes': 4097}, {'state': '4096'}, {'guard': 1},
                       {'protection': original['protection'] ^ 1}):
            self.service.last_result['refused_read'] = dict(original, **change)
            reduced = wrapper._inventory_pre_write_diagnostic(caught.exception, captured,
                refusal=self.producer._inventory_prewrite_refusal)
            self.assertEqual(reduced, {key: diagnostic[key] for key in
                ('pre_write_stage', 'typed_read_requests', 'changed_read')})
        self.service.last_result['refused_read'] = original
        self.assertEqual(wrapper._inventory_pre_write_diagnostic(caught.exception, captured,
            refusal=self.producer._inventory_prewrite_refusal), diagnostic)
        self.assertEqual(len(self.memory.calls), count)
        self.assertEqual(wrapper.last_result['refusal_reason'], 'region_not_readable')
        self.assertFalse(wrapper.last_result['write_attempted'])
        self.assertTrue(self.service._closed)
        self.assertFalse(self.producer.failure.is_set())
        self.assertTrue(wrapper.quiesce_for_source_quit())
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer, deadline_ns=self.producer._inventory_deadline_ns)
        wrapper.close()

    async def test_admission_fresh_authority_source_cancel_or_frame_change_never_continues(self):
        from dataclasses import replace
        self.product_clock()
        for mode in ('selection', 'owner', 'source', 'cancel', 'frame', 'hash', 'clock'):
            await self.rebuild(); self.producer.key_guard = lambda: True
            query, hits = self.code_page_refusal(); self.publish()
            await self.runtime.manual.poll_async()
            self.native.k.VirtualQueryEx = query
            count = len(self.memory.calls)
            self.product_ns += 500_000_000
            if mode == 'selection':
                movement = self.realm.service(self.writer)
                movement._position = replace(movement.snapshot())
            if mode == 'owner': self.reader.owner.closed = True
            if mode == 'source': self.producer.source_guard = Mock(side_effect=ValueError('FIXTURE_SOURCE_CHANGED'))
            if mode == 'cancel':
                def cancelled():
                    asyncio.current_task().cancel()
                    return True
                self.producer.key_guard = cancelled
            if mode == 'frame': self.producer._inventory_frame = bytes(bytearray(self.producer._inventory_frame))
            if mode == 'hash':
                from tools.local_original_session import inventory
                checks = self.service._checks(self.memory.s, *inventory._source()[::2])
                target = self.memory.base + checks[0]['rva']
                self.memory.data[target] = self.memory.source().read(checks[0]['rva'], 1)[0] ^ 1
            if mode == 'clock': self.product_ns = self.runtime.manual._inventory_started_ns - 1
            task = asyncio.create_task(self.runtime.manual.poll_async())
            with self.subTest(mode=mode), self.assertRaises(asyncio.CancelledError if mode == 'cancel' else ValueError):
                await task
            if mode != 'hash': self.assertEqual(len(self.memory.calls), count)
            self.assertEqual(self.runtime.manual.last_result['status'], 'UNKNOWN')
            self.assertTrue(self.runtime.manual.closed and self.service._closed)
            self.assertFalse(self.runtime.manual.quiesce_for_source_quit())
            self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
            self.reader.owner.closed = False
            self.product_ns += 500_000_000

    async def test_direct_call_and_code_after_refusal_stay_terminal_and_postwrite_never_retries(self):
        from tools.local_original_session import inventory
        self.product_clock()
        for mode in ('direct', 'after', 'drain'):
            await self.rebuild(); self.producer.key_guard = lambda: True
            if mode != 'drain': query, _ = self.code_page_refusal(after=mode == 'after')
            else:
                query = self.native.k.VirtualQueryEx
                self.writer.drain.side_effect = ValueError('FIXTURE_DRAIN_UNKNOWN')
            self.publish()
            with self.subTest(mode=mode):
                with self.assertRaises(inventory.PreWriteReadRefusal if mode != 'drain' else ValueError):
                    if mode == 'direct': await self.producer.add_inventory(self.writer)
                    else: await self.runtime.manual.poll_async()
                self.assertTrue(self.service._closed)
                self.assertEqual(self.writer.write.call_count, int(mode == 'drain'))
                with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
                    await self.producer.add_inventory(self.writer, deadline_ns=self.producer._inventory_deadline_ns)
                self.assertEqual(self.writer.write.call_count, int(mode == 'drain'))
            self.native.k.VirtualQueryEx = query
            self.writer.drain.side_effect = None
            self.product_ns += 500_000_000

    async def test_admission_deadline_survives_lock_checkpoint_and_successful_leaf(self):
        from tools.local_original_session import inventory
        self.product_clock()
        for mode in ('lock', 'checkpoint', 'leaf', 'extension'):
            await self.rebuild(); self.producer.key_guard = lambda: True
            query, _ = self.code_page_refusal(); self.publish()
            await self.runtime.manual.poll_async()
            wrapper = self.runtime.manual
            original = wrapper._inventory_started_ns
            self.native.k.VirtualQueryEx = query
            count = len(self.memory.calls)
            self.product_ns += 500_000_000
            if mode == 'checkpoint':
                checkpoint = self.producer._checkpoint
                async def expired(writer, row):
                    sample = await checkpoint(writer, row)
                    self.product_ns = original + 10_000_000_000
                    return sample
                self.producer._checkpoint = expired
            if mode == 'leaf':
                checks = self.service._checks(self.memory.s, *inventory._source()[::2])
                target, hits = self.memory.base + checks[-1]['rva'], [0]
                def expire_leaf(at, size, raw):
                    if at == target:
                        hits[0] += 1
                        if hits[0] == 2: self.product_ns = original + 10_000_000_000
                    return raw
                self.memory.fault = expire_leaf
            if mode == 'lock': await self.row['operation_lock'].acquire()
            if mode == 'extension':
                task = asyncio.create_task(self.producer.add_inventory(self.writer,
                    deadline_ns=original + 10_000_000_001))
            else:
                task = asyncio.create_task(wrapper.poll_async())
            if mode == 'lock':
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                self.product_ns = original + 10_000_000_000
                self.row['operation_lock'].release()
            with self.subTest(mode=mode), self.assertRaises(ValueError) as caught:
                await task
            if mode in ('lock', 'checkpoint'):
                self.assertIs(type(caught.exception), inventory.PreWriteReadRefusal)
                self.assertEqual(len(self.memory.calls), count)
                self.assertTrue(wrapper.quiesce_for_source_quit())
                self.assertFalse(self.producer.failure.is_set())
            if mode == 'leaf':
                self.assertEqual(str(caught.exception), 'INVENTORY_ADMISSION_DEADLINE')
                self.assertTrue(self.producer.failure.is_set())
                self.assertTrue(self.service._claimed)
            if mode == 'extension':
                self.assertEqual(str(caught.exception), 'INVENTORY_ORIGINAL_DEADLINE_REQUIRED')
                self.assertEqual(len(self.memory.calls), count)
            self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
            self.assertIsNone(self.row['policy_row'].drain_started_ns)
            self.assertTrue(self.service._closed)
            self.memory.fault = None
            self.product_ns = max(self.product_ns, original) + 500_000_000

    async def test_admission_final_sync_policy_clock_expiry_after_reservation_is_write_zero_terminal(self):
        self.product_clock(); self.producer.key_guard = lambda: True
        query, _ = self.code_page_refusal(); self.publish()
        self.assertEqual((await self.runtime.manual.poll_async())['phase'], 'ADMISSION')
        self.native.k.VirtualQueryEx = query
        self.product_ns += 500_000_000
        original = self.policy.begin_write
        deadline = self.runtime.manual._inventory_started_ns + 10_000_000_000
        def expired(*args, **kwargs):
            value = original(*args, **kwargs)
            self.assertIsNotNone(self.row['policy_row'].drain_started_ns)
            self.product_ns = deadline
            return value
        self.policy.begin_write = expired
        with self.assertRaisesRegex(ValueError, 'INVENTORY_ADMISSION_DEADLINE'):
            await self.runtime.manual.poll_async()
        self.assertTrue(self.producer.failure.is_set())
        self.assertTrue(self.service._claimed and self.service._closed)
        self.assertIsNone(self.producer._inventory_prewrite_refusal)
        self.assertFalse(self.producer._inventory_admission_expired)
        self.assertFalse(self.producer._inventory_write_attempted)
        self.assertTrue(self.runtime.manual.closed)
        self.assertEqual(self.runtime.manual.last_result['status'], 'UNKNOWN')
        self.assertFalse(self.runtime.manual.quiesce_for_source_quit())
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer, deadline_ns=deadline)
        self.writer.write.assert_not_called()

    def client_count_drift(self):
        target, hits = self.control + 8, [0]
        def changed(at, size, raw):
            if at == target and size == 4:
                hits[0] += 1
                return struct.pack('<i', 4 + hits[0])
            return raw
        self.memory.fault = changed
        return hits

    async def test_actual_client_incomplete_keeps_same_wait_until_next_strict_scalar_query(self):
        self.product_clock(); self.publish(); monitor = SimpleNamespace(next_memory=0)
        await self.runtime.poll(monitor)
        wrapper = self.runtime.manual
        original, started = wrapper._inventory_client_binding, wrapper._inventory_started_ns
        self.materialize(); hits = self.client_count_drift()
        self.product_ns += 500_000_000
        pending = (await self.runtime.poll(monitor))['manual_move']
        self.assertGreater(hits[0], 1)
        self.assertEqual((pending['status'], pending['phase'], pending['reason'], pending['sequence']),
                         ('PENDING', 'CLIENT_WAIT', 'EDGE_TYPED_READ_CHANGED', 2))
        self.assertIn(pending['read_consistency'], l._INVENTORY_INCOMPLETE_READS)
        self.assertFalse(pending['stable_double_read'] or pending['source_contract_valid'])
        self.assertIs(wrapper._inventory_client_binding, original)
        self.assertEqual(wrapper._inventory_started_ns, started)
        observer = wrapper._inventory_observer
        self.assertIsNone(observer.last_result['entry_count'])
        self.assertEqual(observer.last_result['rows'], [])
        self.assertEqual(monitor.next_memory, observer.last_sample_monotonic_ns / 1e9 + .5)
        before = len(self.memory.calls)
        await wrapper.poll_async(); await self.runtime.poll(monitor)
        self.assertEqual(len(self.memory.calls), before)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.memory.fault = None; self.product_ns += 500_000_000
        completed = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual((completed['status'], completed['proof_scope'], completed['sequence']),
                         ('COMMITTED', 'CLIENT_ITEM_ROW_SCALARS_ONLY', 2))
        self.assertEqual(wrapper._inventory_started_ns, started)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))

    async def test_actual_client_incomplete_never_extends_original_claim_deadline(self):
        self.product_clock(); self.publish()
        await self.runtime.manual.poll_async()
        wrapper = self.runtime.manual
        original = wrapper._inventory_started_ns
        self.materialize(); self.client_count_drift()
        for _ in range(2):
            self.product_ns += 500_000_000
            self.assertEqual((await wrapper.poll_async())['status'], 'PENDING')
            self.assertEqual(wrapper._inventory_started_ns, original)
        calls = len(self.memory.calls)
        self.product_ns = original + 10_000_000_000
        with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'):
            await wrapper.poll_async()
        self.assertEqual(wrapper.last_result['reason'], 'FEATURE_INVENTORY_CLIENT_DEADLINE')
        self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
        self.assertEqual(len(self.memory.calls), calls)
        self.assertTrue(wrapper.closed)
        self.assertFalse(wrapper.quiesce_for_source_quit())
        await wrapper.poll_async()
        self.assertEqual(len(self.memory.calls), calls)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))

    async def test_client_wait_replaced_actual_producer_or_delivery_never_queries_or_rebinds(self):
        from tools.local_original_session import inventory_observe
        from dataclasses import replace
        self.product_clock()
        for mode in ('observer', 'sample', 'delivery', 'service', 'reader', 'frame', 'selection'):
            await self.rebuild(); self.publish(); await self.runtime.manual.poll_async()
            wrapper = self.runtime.manual
            original = wrapper._inventory_client_binding
            self.materialize(); self.client_count_drift()
            self.product_ns += 500_000_000
            count = len(self.memory.calls)
            if mode == 'observer': wrapper._inventory_observer = inventory_observe.InventoryObserver(self.producer, self.reader)
            if mode == 'sample':
                async def fake(*args, **kwargs): raise AssertionError('FAKE_SAMPLE_MUST_NOT_RUN')
                wrapper._inventory_observer.sample = types.MethodType(fake, wrapper._inventory_observer)
            if mode == 'delivery': self.producer._inventory_delivery_authority = tuple(list(original[8]))
            if mode == 'service': self.producer._inventory_service = copy.copy(self.service)
            if mode == 'reader': wrapper.consumer.reader = copy.copy(self.reader)
            if mode == 'frame': self.producer._inventory_frame = bytes(bytearray(self.producer._inventory_frame))
            if mode == 'selection':
                movement = self.realm.service(self.writer)
                movement._position = replace(movement.snapshot())
            with self.subTest(mode=mode), self.assertRaises(ValueError): await wrapper.poll_async()
            self.assertEqual(len(self.memory.calls), count)
            self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
            self.assertTrue(wrapper.closed)
            self.assertFalse(wrapper.quiesce_for_source_quit())
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            self.memory.fault = None
            self.product_ns += 500_000_000

    async def test_client_generic_unknown_and_mid_query_original_sample_replacement_are_terminal(self):
        from tools.local_original_session import inventory_observe
        self.product_clock()
        for mode in ('scalar', 'budget', 'sample'):
            await self.rebuild(); self.publish(); await self.runtime.manual.poll_async()
            wrapper = self.runtime.manual
            self.materialize(); self.product_ns += 500_000_000
            original_sample = inventory_observe.InventoryObserver.sample
            if mode == 'sample':
                target = self.control + 8
                hits = [0]
                async def fake(*args, **kwargs): raise AssertionError('REPLACED_SAMPLE_MUST_NOT_RUN')
                def changed(at, size, raw):
                    if at == target and size == 4:
                        hits[0] += 1
                        inventory_observe.InventoryObserver.sample = fake
                        return struct.pack('<i', 4 + hits[0])
                    return raw
                self.memory.fault = changed
            if mode == 'scalar':
                target, hits = self.item + 24, [0]
                def changed(at, size, raw):
                    if at == target:
                        hits[0] += 1
                        if hits[0] == 2: return bytes([raw[0] ^ 1]) + raw[1:]
                    return raw
                self.memory.fault = changed
            budget = patch.object(inventory_observe, 'BYTE_LIMIT', 100) if mode == 'budget' else contextlib.nullcontext()
            try:
                with budget, self.subTest(mode=mode), self.assertRaises(ValueError): await wrapper.poll_async()
                self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
                self.assertTrue(wrapper.closed)
                self.assertFalse(wrapper.quiesce_for_source_quit())
                self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            finally:
                inventory_observe.InventoryObserver.sample = original_sample
                self.memory.fault = None
            self.product_ns += 500_000_000

    async def test_client_wait_source_pin_and_writer_change_inside_owner_await_fail_closed(self):
        self.product_clock()
        for mode in ('pin', 'writer_await'):
            await self.rebuild(); self.publish(); await self.runtime.manual.poll_async()
            wrapper = self.runtime.manual
            self.materialize(); self.client_count_drift(); self.product_ns += 500_000_000
            calls = len(self.memory.calls)
            if mode == 'writer_await':
                sample = self.producer._sample
                async def changed(row):
                    result = await sample(row)
                    await asyncio.sleep(0)
                    wrapper._inventory_wait = object()
                    return result
                self.producer._sample = changed
            guard = patch.object(l, '_INVENTORY_OBSERVER_SOURCE_SHA', '0' * 64) if mode == 'pin' else contextlib.nullcontext()
            with guard, self.subTest(mode=mode), self.assertRaises(ValueError): await wrapper.poll_async()
            if mode == 'pin': self.assertEqual(len(self.memory.calls), calls)
            else:
                self.assertGreater(len(self.memory.calls), calls)
                self.assertIn(wrapper._inventory_observer.last_result['read_consistency'], l._INVENTORY_INCOMPLETE_READS)
            self.assertEqual(wrapper.last_result['status'], 'UNKNOWN')
            self.assertTrue(wrapper.closed)
            self.assertFalse(wrapper.quiesce_for_source_quit())
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            self.memory.fault = None; self.product_ns += 500_000_000

    def product_clock(self):
        from tools.local_original_session import inventory_observe
        self.product_ns = l.time.monotonic_ns()
        for module, name, value in ((l.time, 'monotonic_ns', lambda: self.product_ns),
                                    (l.time, 'monotonic', lambda: self.product_ns / 1e9),
                                    (inventory_observe, 'monotonic_ns', lambda: self.product_ns)):
            patched = patch.object(module, name, value)
            patched.start(); self.addCleanup(patched.stop)

    def materialize(self):
        from tools.local_original_session import inventory, inventory_observe_tests
        # The existing actual shared-pair/typed-row source fixture is reused;
        # values come from the exact configured wire, not an observer verdict.
        inventory_observe_tests.ObservationTests.one(self)
        layout = inventory._source()[0]['inventory']
        fields = dict(inventory.validate_frame(self.factory.config.inventory_frame).raw_fields)
        for key, fmt, value in (('row_id_u64', '<Q', fields[1]),
                ('row_template_id_u32', '<I', fields[2] & 0xffffffff),
                ('row_field18_u64', '<Q', fields[3]),
                ('row_quantity_i64', '<Q', fields[4]), ('row_field30_bool', '<B', fields[24])):
            self.memory.put(self.item + layout[key], fmt, value)

    async def test_public_drain_waits_for_next_slot_empty_then_exact_real_row_scalars(self):
        self.product_clock()
        self.publish()
        monitor = SimpleNamespace(next_memory=0)
        first = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual((first['status'], first['phase'], first['proof_scope']),
                         ('PENDING', 'CLIENT_WAIT', 'TRANSPORT_DRAIN_ONLY'))
        observer = self.runtime.manual._inventory_observer
        self.assertIsNone(observer.last_sample_monotonic_ns)
        self.assertIsNotNone(self.producer._inventory_delivery_authority)
        count = len(self.memory.calls)
        await self.runtime.poll(monitor)
        self.assertEqual(len(self.memory.calls), count)
        self.product_ns += 500_000_000
        empty = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual(empty['status'], 'PENDING')
        self.assertEqual(observer.last_result['entry_count'], 0)
        self.assertEqual(monitor.next_memory, self.product_ns / 1e9 + .5)
        self.assertEqual(observer.last_result['typed_bytes_requested'], 2343)
        self.materialize()
        self.product_ns += 500_000_000
        complete = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual((complete['status'], complete['sequence'], complete['proof_scope']),
                         ('COMMITTED', 2, 'CLIENT_ITEM_ROW_SCALARS_ONLY'))
        self.assertEqual((complete['render'], complete['equipped'], complete['save']), ('UNKNOWN',) * 3)
        self.assertFalse(complete['all_17_wire_fields_proven'] or complete['wire_field18_bytes_observed']
                         or complete['catalog_live_materialization_proven'])
        self.assertLessEqual(observer.last_result['typed_bytes_requested'], 16384)
        self.assertEqual(len(observer.last_result['rows']), 1)
        self.assertFalse(observer.last_result['visible_screen_claimed'])
        self.assertFalse(self.runtime.manual.pending)
        await self.runtime.manual.poll_async()  # Public duplicate never sends again.
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))

    async def test_client_wait_does_not_rebind_changed_selection_after_delivery(self):
        self.product_clock(); self.publish()
        await self.runtime.poll(SimpleNamespace(next_memory=0))
        original = self.producer._inventory_delivery_authority
        movement = self.realm.service(self.writer)
        from dataclasses import replace
        movement._position = replace(movement.snapshot())
        count = len(self.memory.calls)
        self.product_ns += 500_000_000
        with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'):
            await self.runtime.manual.poll_async()
        self.assertEqual(self.runtime.manual.last_result['status'], 'UNKNOWN')
        self.assertEqual(len(self.memory.calls), count)
        self.assertIs(self.producer._inventory_delivery_authority, original)
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertTrue(self.runtime.manual.closed)

    async def test_client_query_recheck_unknown_and_budget_consume_slot_without_retransmission(self):
        from tools.local_original_session import inventory_observe
        self.product_clock()
        for mode in ('recheck', 'budget', 'mismatch'):
            await self.rebuild()
            self.publish(); monitor = SimpleNamespace(next_memory=0)
            await self.runtime.poll(monitor)
            self.materialize()
            self.product_ns += 500_000_000
            target, hits = self.item + 24, [0]
            def fault(at, size, raw):
                if at == target:
                    hits[0] += 1
                    if hits[0] == 2: return bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            if mode == 'recheck': self.memory.fault = fault
            if mode == 'mismatch': self.memory.put(self.item + 24, '<Q', 7)
            budget = patch.object(inventory_observe, 'BYTE_LIMIT', 100) if mode == 'budget' else contextlib.nullcontext()
            with budget, self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'):
                await self.runtime.poll(monitor)
            observer = self.runtime.manual._inventory_observer
            self.assertEqual(self.runtime.manual.last_result['status'], 'UNKNOWN')
            self.assertEqual(monitor.next_memory, self.product_ns / 1e9 + .5)
            self.assertEqual(observer.last_sample_monotonic_ns, self.product_ns)
            if mode == 'budget': self.assertLessEqual(observer.last_result['typed_bytes_requested'], 100)
            self.assertEqual(self.writer.write.call_count, 1)
            self.assertTrue(self.runtime.manual.closed)
            with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
                await self.producer.add_inventory(self.writer)
            self.memory.fault = None

    async def test_client_wait_original_claim_deadline_clock_and_cancel_never_retry(self):
        self.product_clock()
        for mode in ('deadline', 'clock', 'cancel'):
            await self.rebuild(); self.publish()
            await self.runtime.poll(SimpleNamespace(next_memory=0))
            claimed = self.runtime.manual._inventory_started_ns
            self.product_ns += 500_000_000
            if mode == 'deadline':
                await self.runtime.manual.poll_async()  # Stable empty is pending.
                self.assertEqual(self.runtime.manual._inventory_started_ns, claimed)
                self.product_ns = claimed + 10_000_000_000
            elif mode == 'clock': self.product_ns = claimed - 1
            else:
                def fault(at, size, raw):
                    if at == self.memory.header: asyncio.current_task().cancel()
                    return raw
                self.memory.fault = fault
            count = len(self.memory.calls)
            task = asyncio.create_task(self.runtime.manual.poll_async())
            if mode == 'cancel':
                with self.assertRaises(asyncio.CancelledError): await task
            else:
                with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_TERMINAL_UNKNOWN'): await task
                self.assertEqual(len(self.memory.calls), count)
                expected = 'FEATURE_INVENTORY_CLIENT_DEADLINE' if mode == 'deadline' else 'FEATURE_INVENTORY_CLOCK_UNKNOWN'
                self.assertEqual(self.runtime.manual.last_result['reason'], expected)
            self.assertTrue(self.runtime.manual.closed)
            self.assertFalse(self.reader.closed)
            self.assertFalse(self.producer._closing)
            self.assertEqual(self.writer.write.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
                await self.producer.add_inventory(self.writer)
            self.memory.fault = None
            self.product_ns = max(self.product_ns, claimed) + 500_000_000

    async def asyncSetUp(self):
        from tools.local_original_session import inventory_tests as fixture
        await fixture.GateTests.asyncSetUp(self)  # Original retained/source fixture only.
        await self.rebuild()

    async def rebuild(self, *, enabled=True, store_policy=None, fallback_fields=None, restart_policy=None,
                      delivery_policy=None, item_use_policy=None, inventory_update_policy=None,
                      product='sibling-manual-play-spawn'):
        from tools.local_original_session import inventory as inv, inventory_tests as fixture, feature_config as fc
        from tools.local_original_session import broker as b
        from tools.local_own_login_request.codec import LocalLoginRequest
        raw = {str(k): list(v) if type(v) is bytes else v
               for k, v in (fixture.explicit_fields() if fallback_fields is None else fallback_fields).items()}
        inventory_config = dict(policy=inv.POLICY, fields=raw) if enabled else None
        if enabled and store_policy is not None:
            inventory_config['store_policy'] = store_policy
        if enabled and delivery_policy is not None:
            inventory_config['delivery_policy'] = delivery_policy
        value = dict(schema=fc.SCHEMA, npc=None, inventory=inventory_config,
                     restart=None if restart_policy is None else dict(policy=restart_policy))
        if item_use_policy is not None:
            value['item_use'] = dict(policy=item_use_policy)
        if inventory_update_policy is not None:
            value['inventory_update'] = dict(policy=inventory_update_policy)
        config = fc.parse(value)
        run = Path(tempfile.mkdtemp(dir=self.temp.name))
        self.factory = l.ProductFeatureFactory(self.reader, product=product,
            control_mode='manual', directory=run, config=config)
        retained = self.reader.owner
        self.producer = b.PersistentBroker(sockets={12000: object(), 14030: object()},
            retained_owner=retained, owner_handle=retained.owner_handle, owner_job=retained.owner_job,
            owner_guard=lambda _: True, owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=lambda *_: None, expected_uuid=self.realm.expected_uuid,
            store_path=self.realm.store.path, **self.factory.broker_options())
        self.realm, self.policy = self.producer.realm, self.producer.policy
        def sample(peer):
            return b.OwnerSample(retained, retained.owner_handle, retained.owner_job,
                                peer, l.time.monotonic_ns(), True, True)
        def boot(writer, peer):
            row = self.policy.admit(writer, peer, sample(peer), l.time.monotonic_ns())
            for opcode, size, request in ((0x4e20, 12, None), (0x4e35, 76, 0x4e34), (0x4f3e, 6, 0x4f3d)):
                if request is not None:
                    self.policy.received_frame(writer, sample(peer), request, 10, l.time.monotonic_ns())
                self.policy.begin_write(writer, sample(peer), opcode, size, 0, l.time.monotonic_ns())
                self.policy.drained(writer, sample(peer), 0, l.time.monotonic_ns())
            return row
        prior = object(); peer = b.Peer(14030, 41000, l.time.monotonic_ns())
        boot(prior, peer)
        self.policy.eof(prior, sample(peer), True, l.time.monotonic_ns())
        self.policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        peer = b.Peer(14030, 41001, l.time.monotonic_ns())
        policy_row = boot(self.writer, peer)
        self.row = dict(writer=self.writer, policy_row=policy_row, failed=False, joined=False,
            eof=False, positive_close=False, registry_removed=False, boot_complete=True,
            operation_lock=asyncio.Lock(), peer=dict(connection_id=4, endpoint_port=14030,
                server_port=14030, client_port=peer.client_port, accepted_monotonic_ns=peer.accepted_ns))
        self.producer._claims[14030] = [self.row]
        guards = dict(movement_owner_guard=lambda *_: True)
        if item_use_policy is not None or inventory_update_policy is not None:
            async def owner(writer, position):
                return await self.producer._movement_owner(writer, self.row, position)
            async def account(writer):
                return await self.producer._account_owner(writer, self.row)
            guards = dict(movement_owner_guard=owner, account_owner_guard=account)
        self.game = self.realm.grant(self.writer, connection_id=4, **guards)
        await self.game.received(SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))
        payload = inv.pb.encode_bytes(1, self.realm.profile_name.encode()) + b'\x10\0\x18\0'
        # Production binds features before resume/selection; persistence adopts
        # the authoritative restored frame later, at the first explicit Add.
        self.runtime = self.factory(self.producer)
        async with self.row['operation_lock']:
            await self.game.received(SimpleNamespace(opcode=0x4e28, payload=payload))
        self.service = self.producer._inventory_service
        if self.service is not None:
            self.memory = fixture.Memory(self)
        self.run = run
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()

    def publish(self, sequence=2, **extra):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position = self.realm.service(self.writer).snapshot()
        request = dict(schema=REQUEST_SCHEMA, sequence=sequence, command='AddInventory',
                       uid=position.uid, map_id=position.map_id)
        request.update(extra)
        (self.run / 'command.request.json').write_text(json.dumps(request))

    async def test_actual_factory_public_add_checkpoint_real_gate_write_drain_once_and_memory_slot(self):
        self.assertEqual(self.realm._npc_spawns, ())
        self.assertFalse(self.runtime.manual.allow_move)
        self.assertFalse(self.runtime.manual.allow_attack)
        self.assertEqual(self.memory.calls, [])  # Config/bind/selection sent/sampled nothing.
        self.writer.write.assert_not_called()
        self.publish()
        phases = []
        checkpoint = self.producer._checkpoint
        async def checked(writer, row):
            self.assertTrue(row['operation_lock'].locked())
            self.assertTrue(self.runtime.manual.pending)
            self.assertEqual(json.loads((self.run / 'command.result.json').read_text())['status'], 'CLAIMED')
            phases.append(row['await_phase'])
            with self.assertRaisesRegex(ValueError, 'POLL_INFLIGHT'):
                await self.runtime.manual.poll_async()
            return await checkpoint(writer, row)
        self.producer._checkpoint = checked
        def written(wire):
            self.assertEqual(self.service.last_result['status'], 'OBSERVED')
            self.assertTrue(self.service._claimed)
            self.assertIsNotNone(self.row['policy_row'].drain_started_ns)
            self.assertEqual(self.row['await_phase'], 'WRITE_CHECKPOINT')
        self.writer.write.side_effect = written
        monitor = SimpleNamespace(next_memory=float('inf'))
        await self.runtime.poll(monitor)
        self.assertEqual(self.memory.calls, [])
        monitor.next_memory = 0
        result = (await self.runtime.poll(monitor))['manual_move']
        self.assertEqual((result['status'], result['sequence'], result['command']), ('PENDING', 2, 'AddInventory'))
        self.assertEqual(result['phase'], 'CLIENT_WAIT')
        self.assertEqual(result['proof_scope'], 'TRANSPORT_DRAIN_ONLY')
        self.assertEqual(result['client_inventory'], 'UNKNOWN')
        self.assertFalse(result['automatic_retry'])
        self.assertEqual(phases, ['WRITE_CHECKPOINT'])
        self.writer.write.assert_called_once_with(self.factory.config.inventory_frame)
        self.assertEqual(self.writer.drain.await_count, 1)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 2343)
        self.assertEqual(monitor.next_memory, self.producer.inventory_sample_monotonic_ns / 1e9 + .5)
        self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
        await self.runtime.manual.poll_async()  # Duplicate public sequence performs nothing.
        self.assertEqual(self.writer.write.call_count, 1)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_public_schema_uid_and_default_off_cannot_write_or_enable_move(self):
        for extra in ({'uid': True}, {'map_id': 1}, {'raw_frame': []}, {'command': 'MoveGoal', 'x': 1, 'y': 1}):
            await self.rebuild()
            self.publish(**extra)
            with self.assertRaises(ValueError): await self.runtime.manual.poll_async()
            self.writer.write.assert_not_called()
            self.assertEqual(self.memory.calls, [])
        await self.rebuild(enabled=False)
        self.assertEqual(self.factory.broker_options(), {})
        self.assertIsNone(self.runtime.manual)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)
        with self.assertRaises(ValueError):
            await self.producer._send(self.writer, self.row, (self.wire,), game=True)
        self.writer.write.assert_not_called()

    async def test_checkpoint_await_mutations_refuse_before_query_and_never_retry(self):
        from tools.local_original_session import inventory as inv
        for mutation in ('selection', 'registry', 'claim', 'reader', 'owner', 'closed', 'ingress_close', 'source'):
            await self.rebuild()
            original = self.producer._checkpoint
            async def changed(writer, row):
                result = await original(writer, row)
                await asyncio.sleep(0)  # Actual await boundary before mutation/query.
                if mutation == 'selection': self.realm.registry.selected.clear()
                elif mutation == 'registry': self.realm.registry = copy.copy(self.realm.registry)
                elif mutation == 'claim': self.producer._claims[14030] = []
                elif mutation == 'reader': self.reader.backend = copy.copy(self.reader.backend)
                elif mutation == 'owner': self.reader.owner.child = copy.copy(self.reader.owner.child)
                elif mutation == 'closed': self.producer._closing = True
                elif mutation == 'ingress_close': self.runtime.manual.close()
                else: inv.SOURCE_PINS = dict(inv.SOURCE_PINS, **{inv.EVIDENCE: '0' * 64})
                return result
            pins, backend, child = inv.SOURCE_PINS, self.reader.backend, self.reader.owner.child
            self.producer._checkpoint = changed
            try:
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    await self.producer.add_inventory(self.writer)
                self.writer.write.assert_not_called()
                self.assertEqual(self.writer.drain.await_count, 0)
                with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
                    await self.producer.add_inventory(self.writer)
            finally:
                inv.SOURCE_PINS, self.reader.backend, self.reader.owner.child = pins, backend, child

    async def test_final_sync_policy_cancel_is_write_zero_with_consumed_admission(self):
        original = self.policy.begin_write
        def cancelled(*args, **kwargs):
            value = original(*args, **kwargs)
            asyncio.current_task().cancel()  # No yield between successful gate and write.
            return value
        self.policy.begin_write = cancelled
        self.publish()
        task = asyncio.create_task(self.runtime.manual.poll_async())
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(self.service._claimed)
        self.assertTrue(self.service._closed)
        self.assertTrue(self.runtime.manual.closed)
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)

    async def test_lock_replaced_while_acquire_waits_refuses_before_typed_memory_or_write(self):
        original, replacement = self.row['operation_lock'], asyncio.Lock()
        await original.acquire()
        await replacement.acquire()
        task = asyncio.create_task(self.producer.add_inventory(self.writer))
        try:
            await asyncio.sleep(0)  # Operation is waiting on the literal old lock.
            self.assertFalse(task.done())
            self.assertTrue(self.producer._inventory_attempted)
            self.row['operation_lock'] = replacement
            original.release()
            with self.assertRaisesRegex(ValueError, 'INVENTORY_OPERATION_LOCK_CHANGED'):
                await task
            self.assertTrue(replacement.locked())
            self.assertFalse(original.locked())
            self.assertEqual(self.memory.calls, [])
            self.assertIsNone(self.producer.inventory_sample_monotonic_ns)
            self.writer.write.assert_not_called()
            self.assertEqual(self.writer.drain.await_count, 0)
            with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
                await self.producer.add_inventory(self.writer)
        finally:
            if original.locked(): original.release()
            if replacement.locked(): replacement.release()
            if not task.done():
                task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task

    async def test_ambiguous_drain_failure_and_explicit_close_do_not_retry(self):
        self.writer.drain.side_effect = RuntimeError('injected ambiguous drain')
        self.publish()
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'):
            await self.runtime.manual.poll_async()
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertTrue(self.producer.failure.is_set())
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)
        self.assertEqual(self.writer.write.call_count, 1)
        self.writer.drain.side_effect = None
        await self.rebuild()
        self.service.close()
        with self.assertRaisesRegex(ValueError, 'LIFETIME'):
            await self.producer.add_inventory(self.writer)
        self.writer.write.assert_not_called()


class ProductFeatureNpcTests(unittest.IsolatedAsyncioTestCase):
    async def test_config_factory_real_session_edge_policy_write_drain_commit(self):
        from tools.local_original_session import feature_config, npc_session, npc_edge_tests
        await npc_edge_tests.NpcEdgeTests.asyncSetUp(self)
        try:
            candidate, _ = self.realm._npc_spawns[0]
            config = feature_config.Features((candidate,), 100, npc_session.npc_motion.LOCAL_PRE_STEP,
                npc_session.AXIS_SIGN_GOAL, (self.x + 1, self.y))
            factory = l.ProductFeatureFactory(self.f.adapter.reader, product='sibling-manual-play-spawn',
                control_mode='manual', directory=Path('.'), config=config)
            options = factory.broker_options()
            self.assertIs(options['npc_spawns'][0], candidate)
            self.factory = factory.npc_factory
            self.factory.adapter._proof = self.f.adapter
            self.realm.npc_edge_passability = options['npc_edge_passability']
            features = factory(self.producer)
            result = await features.poll()
            self.assertEqual(result['npc']['status'], 'MOVED', self.factory.adapter.last_result)
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            self.assertEqual(self.policy.log[-1][2], 0x4e2c)
            self.assertGreater(self.mover.state.last_step_ns, 0)
            features.close()
            self.assertEqual((await features.poll())['npc']['status'], 'CLOSED')
            self.assertEqual(self.writer.write.call_count, 1)
            report = await l.run_session(FakeOwner([True, False]), FakeBroker, asyncio.Event(),
                                         poll_seconds=0, feature_factory=lambda _: features)
            self.assertTrue(report['normal_input_only'])
        finally:
            await npc_edge_tests.NpcEdgeTests.asyncTearDown(self)

    def binding(self):
        from tools.local_original_session.npc_edge import NpcEdgeBinding
        return NpcEdgeBinding(self.writer, self.producer)


class ProductProfileTests(unittest.TestCase):
    def test_source_quit_candidate_changes_only_pinned_bridge_and_explicit_capability(self):
        old = l.PRODUCTS['sibling-background-move-attack-target-spawn']
        candidate = l.PRODUCTS['sibling-background-source-quit-spawn']
        expected = {**old, 'bridges': {**old['bridges'], 'own-login-bridge-dg49.dll':
            'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d'},
            'bridge_artifact': l.ROOT / 'work/local_original_session/implementation-1/manual-source-quit-codegate-bounds/'
                                       'own-login-bridge-dg49.dll',
            'manual_source_quit': True, 'require_source_quit': True}
        self.assertEqual(candidate, expected)
        self.assertEqual(l.digest(candidate['bridge_artifact']), candidate['bridges']['own-login-bridge-dg49.dll'])
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'LC.local.exe'
            image.write_bytes(b'fixture-no-execution')
            for name in candidate['bridges']:
                (image.parent / name).write_bytes(b'fixture-no-execution')
            spec = {**candidate, 'image': image, 'resource_directory': image.parent}
            def old_pin(path):
                return (spec['image_sha256'] if path == image else
                        'cba9b12f7efa7eedecd753e64d08ddd5d87e2f2e7c4e88dee06cb07ed5fdf2c2'
                        if path.name == 'own-login-bridge-dg49.dll' else spec['bridges'][path.name])
            with patch.dict(l.PRODUCTS, {'sibling-background-source-quit-spawn': spec}), \
                    patch.object(l, 'digest', side_effect=old_pin):
                with self.assertRaisesRegex(ValueError, 'CP69_BRIDGE_REQUIRED:own-login-bridge-dg49.dll'):
                    l.preflight(image, 'sibling-background-source-quit-spawn')
        self.assertNotIn('manual_source_quit', old)
        self.assertEqual(old['bridges']['own-login-bridge-dg49.dll'],
                         '2c0bcd6e53eb5d86e4ef87115f899b976a86d5e820912d63ab3de29e1344073d')

    def test_background_attack_candidate_has_exact_pin_and_preserves_foreground_source_block(self):
        original = l.PRODUCTS['sibling-manual-move-attack-target-spawn']
        candidate = l.PRODUCTS['sibling-background-move-attack-target-spawn']
        self.assertEqual(candidate['bridges'], {**original['bridges'], 'own-login-bridge-dg49.dll':
            '2c0bcd6e53eb5d86e4ef87115f899b976a86d5e820912d63ab3de29e1344073d'})
        self.assertEqual(candidate['bridge_artifact'], l.ROOT / 'work/local_original_session/'
            'implementation-1/manual-attack-to-move/own-login-bridge-dg49.dll')
        self.assertEqual(l.digest(candidate['bridge_artifact']), candidate['bridges']['own-login-bridge-dg49.dll'])
        for key in ('image', 'candidate', 'image_sha256', 'resource_directory', 'world_profile'):
            self.assertEqual(candidate[key], original[key])
        for flag in ('manual_only', 'continuous_manual_move', 'continuous_manual_attack',
                     'background_display_guard', 'require_background', 'manual_attack_move_replacement'):
            self.assertIs(candidate[flag], True)
        self.assertIs(candidate['source_build_only'], False)
        self.assertEqual(candidate['runtime_verdict'], 'EXPLICIT_BACKGROUND_TEST_CANDIDATE')
        self.assertFalse(candidate.get('internal_only', False))
        self.assertFalse(candidate.get('require_lifecycle_health', False))
        self.assertIs(original['source_build_only'], True)
        self.assertNotIn('manual_attack_move_replacement', original)
        self.assertEqual(original['bridges']['own-login-bridge-dg49.dll'],
                         'c55d601df697dfad3b1ebb0c80b091930caa1b9fdd00e98cd11b0ba7d79353c7')

    def test_background_product_changes_only_display_isolation_flags_from_660f(self):
        original = l.PRODUCTS['sibling-manual-move-continuous-spawn']
        background = l.PRODUCTS['sibling-background-move-continuous-spawn']
        self.assertEqual(background, dict(original, background_display_guard=True, require_background=True))
        self.assertEqual(background['bridges']['own-login-bridge-dg49.dll'],
                         '660f98fa25323baeffd1bf9389f78bb9010816607c4e7e5ae48c3446f282dea4')
        for flag in ('internal_only', 'require_lifecycle_health'):
            self.assertFalse(background.get(flag, False))
    def test_attack_product_exact_postpredicate_pin_and_two_explicit_capability_gates(self):
        from tools.local_original_session import feature_config, npc_tests
        name = 'sibling-manual-move-attack-target-spawn'
        original = l.PRODUCTS['sibling-manual-move-continuous-spawn']
        attack = l.PRODUCTS[name]
        self.assertEqual(attack['bridges']['own-login-bridge-dg49.dll'],
                         'c55d601df697dfad3b1ebb0c80b091930caa1b9fdd00e98cd11b0ba7d79353c7')
        self.assertEqual(l.digest(attack['bridge_artifact']), attack['bridges']['own-login-bridge-dg49.dll'])
        self.assertEqual(attack['bridge_artifact'], l.ROOT / 'work/local_original_session/implementation-1/'
                         'manual-attack-target/postpredicate-build/own-login-bridge-dg49.dll')
        self.assertEqual(attack['runtime_status'], 'NOT_FOR_INSTALL_RUNTIME_UNVERIFIED')
        for key in ('image', 'candidate', 'image_sha256', 'resource_directory', 'world_profile', 'manual_only'):
            self.assertEqual(attack[key], original[key])
        self.assertTrue(attack['continuous_manual_move'] and attack['continuous_manual_attack'])
        self.assertNotIn('continuous_manual_attack', original)
        configured = feature_config.Features(spawns=(npc_tests.spawn(),),
                                             attack_policy=feature_config.ATTACK_INTENT_POLICY)
        for product, config, expected in ((name, configured, True),
                (name, feature_config.Features(), False),
                ('sibling-manual-move-continuous-spawn', configured, False)):
            factory = l.ProductFeatureFactory(None, product=product, control_mode='manual',
                                             directory=Path('.'), config=config)
            self.assertIs(factory.allow_attack, expected)

    def test_continuous_manual_has_exact_pin_and_preserves_manual_startup_contract(self):
        old = l.PRODUCTS['sibling-manual-play-spawn']
        new = l.PRODUCTS['sibling-manual-move-continuous-spawn']
        self.assertEqual(new['bridges']['own-login-bridge-dg49.dll'],
                         '660f98fa25323baeffd1bf9389f78bb9010816607c4e7e5ae48c3446f282dea4')
        for key in ('image', 'candidate', 'image_sha256', 'resource_directory', 'world_profile'):
            self.assertEqual(new[key], old[key])
        self.assertTrue(new['manual_only'] and new['continuous_manual_move'])
        for flag in ('internal_only', 'background_display_guard', 'require_lifecycle_health'):
            self.assertFalse(new.get(flag, False))
    def test_lifecycle_details_keeps_internal_health_and_changes_only_dg49_pin(self):
        original = l.PRODUCTS['sibling-internal-lifecycle-integrity-spawn']
        details = l.PRODUCTS['sibling-internal-lifecycle-details-spawn']
        expected = {**original, 'bridges': {**original['bridges'],
            'own-login-bridge-dg49.dll':
            '906953e195688fae8f88c8a2bfcc28b21a26ed95b63dd32c8f9076894d884a5b'}}
        self.assertEqual(details, expected)
        self.assertIs(details['require_lifecycle_health'], True)
        self.assertIs(details['background_display_guard'], True)
        self.assertIs(details['internal_only'], True)

    def test_manual_play_copies_1d1f_and_only_selects_existing_cp73_world(self):
        baseline = l.PRODUCTS['sibling-verified-socket-duplicate']
        manual = l.PRODUCTS['sibling-manual-play-spawn']
        self.assertEqual({key: value for key, value in manual.items() if key != 'world_profile'}, baseline)
        self.assertEqual(manual['world_profile'], 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73')
        self.assertEqual(manual['bridges']['own-login-bridge-dg49.dll'],
                         '1d1f60a03144f0214bee56c4a875d4444d51811649135a1eaab82ec2e2899f75')
        for flag in ('internal_only', 'background_display_guard', 'require_lifecycle_health'):
            self.assertFalse(manual.get(flag, False))
    def test_spawn_profile_changes_only_the_explicit_local_world_profile(self):
        original = l.PRODUCTS['sibling-internal-quit-source-retry']
        spawned = l.PRODUCTS['sibling-internal-quit-source-retry-spawn']
        self.assertEqual({key: value for key, value in spawned.items() if key != 'world_profile'}, original)
        self.assertEqual(spawned['world_profile'], 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73')
    def test_connect_fix_is_separate_known_pin_with_same_candidate_and_cwd(self):
        diagnostic = l.PRODUCTS['sibling-guard-diagnostic']
        fixed = l.PRODUCTS['sibling-connect-fix']
        self.assertEqual(diagnostic['bridges']['own-login-bridge-dg49.dll'],
            '2af9a217a78eb061b95aacd725dfba55d806ae878878d3a1ab5e5a6e6701d0d9')
        self.assertEqual(fixed['bridges']['own-login-bridge-dg49.dll'],
            '39b5647702ae14b53826bc476668b0b6ed9d75ae9d241e29ed3a5f5be7903013')
        for key in ('image', 'resource_directory', 'image_sha256', 'candidate'):
            self.assertEqual(fixed[key], diagnostic[key])
        bridges, cwd = l.product_configuration('sibling-connect-fix', fixed['image'])
        self.assertEqual(bridges, fixed['bridges'])
        self.assertEqual(cwd, diagnostic['resource_directory'])
        memory = l.PRODUCTS['sibling-memory-query']
        self.assertEqual(memory['bridges']['own-login-bridge-dg49.dll'],
            'bdb1d851d618cd0c821e60b0ed6aa8b63d1b60aa16370bd1a373ba03eb90c167')
        self.assertEqual(memory['bridges']['own-creation-entry001.dll'],
                         l.BRIDGES['own-creation-entry001.dll'])
        for key in ('image', 'resource_directory', 'image_sha256', 'candidate'):
            self.assertEqual(memory[key], fixed[key])
    def test_baseline_keeps_image_folder_as_cwd(self):
        image = Path('C:/fixture/LC.local.exe')
        bridges, cwd = l.product_configuration('baseline', image)
        self.assertEqual(bridges, l.BRIDGES)
        self.assertEqual(cwd, image.parent)
    def test_unknown_product_cannot_supply_a_pin(self):
        with self.assertRaisesRegex(ValueError, 'KNOWN_PRODUCT_REQUIRED'):
            l.product_configuration('caller-hash', Path('C:/fixture/LC.local.exe'))
    def test_wrong_bridge_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'LC.local.exe'
            image.write_bytes(b'fixture-no-execution')
            for name in l.BRIDGES:
                (image.parent / name).write_bytes(b'fixture-no-execution')
            def fake_digest(path):
                return l.CP69 if path == image else '0' * 64
            with patch.object(l, 'digest', side_effect=fake_digest):
                with self.assertRaisesRegex(ValueError, 'CP69_BRIDGE_REQUIRED'):
                    l.preflight(image, 'baseline')
    def test_diagnostic_native_namespace_uses_fixed_resource_cwd(self):
        profile = l.PRODUCTS['guard-diagnostic']
        module = l.native_module(profile['image'], profile['resource_directory'])
        self.assertEqual(module.EXE, str(profile['image']))
        self.assertEqual(module.CLONE, str(l.ROOT / 'work/standalone_boot/current-unmodified-clone'))
    def test_diagnostic_profile_rejects_baseline_bridge(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'LC.local.exe'
            image.write_bytes(b'fixture-no-execution')
            for name in l.BRIDGES:
                (image.parent / name).write_bytes(b'fixture-no-execution')
            spec = {**l.PRODUCTS['guard-diagnostic'], 'image': image,
                    'resource_directory': image.parent}
            def fake_digest(path):
                return l.CP69 if path == image else l.BRIDGES[path.name]
            with patch.dict(l.PRODUCTS, {'guard-diagnostic': spec}), \
                 patch.object(l, 'digest', side_effect=fake_digest):
                with self.assertRaisesRegex(ValueError, 'CP69_BRIDGE_REQUIRED'):
                    l.preflight(image, 'guard-diagnostic')


class FakeSceneReader:
    def __init__(self): self.reads = 0; self.closed = False
    def bind(self, owner): self.owner = owner
    def sample(self):
        self.reads += 1
        return dict(status='OBSERVED', current='Login', pending='none', root_ready=True), 8192
    def close(self): self.closed = True


class MonitorTests(unittest.TestCase):
    def setup_monitor(self, directory):
        now = [0.0]
        reader = FakeSceneReader()
        owner = SimpleNamespace(alive=True, child=object())
        owner.validate = lambda child: owner.alive
        owner.native = SimpleNamespace(job_windows=lambda child: [dict(
            title='PRIVATE_UNKNOWN_CAPTION', **{'class': '#32770'}, visible=True,
            geometry=dict(left=0, top=0, width=320, height=120),
            children=[{'class': 'Static', 'text': 'PRIVATE_UNKNOWN_STATIC'},
                      {'class': 'Edit', 'text': 'PRIVATE_PASSWORD'},
                      {'class': 'Static', 'text': next(iter(obs.KNOWN_ERRORS))}])])
        monitor = obs.SessionMonitor(Path('C:/fixture.exe'), directory,
            reader=reader, clock=lambda: now[0])
        monitor.bind(owner)
        return monitor, reader, owner, now
    def test_status_is_bounded_redacted_and_only_written_on_change(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor, reader, owner, now = self.setup_monitor(folder)
            first = monitor.tick()
            raw = (Path(folder) / 'status.json').read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE_', raw)
            self.assertLessEqual(len(raw.encode('utf-8')), obs.STATUS_LIMIT)
            self.assertIn('known_error_text', raw)
            now[0] = .1; monitor.tick()
            self.assertEqual(reader.reads, 1)
            now[0] = .75; second = monitor.tick()
            self.assertEqual(reader.reads, 2)
            self.assertEqual(second['revision'], first['revision'])
            self.assertEqual((Path(folder) / 'status.json').read_text(encoding='utf-8'), raw)
            self.assertFalse((Path(folder) / 'status.json.tmp').exists())
            monitor.close(); self.assertTrue(reader.closed)
    def test_native_exit_keeps_first_scene_and_immediately_records_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor, reader, owner, now = self.setup_monitor(folder)
            monitor.tick(); owner.alive = False; now[0] = .1
            row = monitor.tick(state='NATIVE_EXIT', force=True)
            self.assertEqual(reader.reads, 1)
            self.assertEqual(row['memory']['scene']['reason'], 'PROCESS_EXITED')
            self.assertEqual(row['memory']['first_observed_scene']['current'], 'Login')
            self.assertEqual(row['state'], 'NATIVE_EXIT')
            self.assertIsNotNone(row['first_known_error'])
            monitor.close()
    def test_session_counter_saturates_without_stopping_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor, reader, owner, now = self.setup_monitor(folder)
            monitor.total_bytes = obs.MAX_COUNTER - 1
            monitor.tick(); now[0] = .75; monitor.tick()
            self.assertEqual(reader.reads, 2)
            self.assertEqual(monitor.total_bytes, obs.MAX_COUNTER)
            monitor.close()
    def test_heavy_snapshot_waits_for_first_key_drain(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor, reader, owner, now = self.setup_monitor(folder)
            broker = SimpleNamespace(policy=SimpleNamespace(rows={12000: [], 14030: []}),
                report=lambda: {'state': 'OPEN', 'connections': [], 'failure_code': None})
            first = monitor.tick(broker)
            self.assertEqual(reader.reads, 0)
            self.assertEqual(first['windows'], [])
            self.assertEqual(first['memory']['scene']['reason'], 'WAITING_FIRST_KEY_DRAIN')
            broker.policy.rows[12000].append(SimpleNamespace(tx_boot=1))
            now[0] = .75
            monitor.tick(broker)
            self.assertEqual(reader.reads, 1)
            monitor.close()
    def test_quiet_initial_dialog_is_visible_after_five_seconds_without_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor, reader, owner, now = self.setup_monitor(folder)
            broker = SimpleNamespace(policy=SimpleNamespace(rows={12000: [], 14030: []}),
                report=lambda: {'state': 'OPEN', 'connections': [], 'failure_code': None})
            monitor.tick(broker)
            now[0] = 5.25
            row = monitor.tick(broker)
            self.assertEqual(reader.reads, 0)
            self.assertTrue(row['windows'])
            self.assertIsNotNone(row['first_known_error'])
            self.assertEqual(row['memory']['scene']['reason'], 'WAITING_FIRST_KEY_DRAIN')
            monitor.close()


class ReadonlyDuplicateTests(unittest.TestCase):
    def test_duplicate_uses_readonly_mask_and_only_closes_its_handle(self):
        closed, calls = [], []
        member = SimpleNamespace(process=123, pid=7,
            identity=dict(pid=7, birth='33', image='C:/fixture.exe', parent_pid=9))
        def duplicate(srcproc, source, dstproc, output, mask, inherit, options):
            calls.append((source, mask, inherit, options)); output._obj.value = 456; return True
        kernel = SimpleNamespace(GetCurrentProcess=Fn(lambda: 1),
            DuplicateHandle=Fn(duplicate), CloseHandle=Fn(lambda h: closed.append(h)),
            IsProcessInJob=Fn(lambda h, j, result: setattr(result._obj, 'value', True) or True))
        owner = SimpleNamespace(child=member, owner_job=789, validate=lambda m: m is member,
            native=SimpleNamespace(k=kernel, identity=lambda *a, **kw: dict(member.identity)))
        reader = obs.RetainedSceneReader.__new__(obs.RetainedSceneReader)
        reader.owner = None; reader.member = None; reader.closed = False
        reader.backend = SimpleNamespace(stack=contextlib.ExitStack())
        reader.backend.close = reader.backend.stack.close
        reader.bind(owner)
        self.assertEqual(calls, [(123, 0x101010, False, 0)])
        reader.close(); reader.close()
        self.assertEqual(closed, [456])
        self.assertEqual(member.process, 123)


class BridgeStatusTests(unittest.TestCase):
    def test_only_current_context_fixed_fields_are_exported(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = SimpleNamespace(directory=Path(folder), image_sha=l.CP69,
                child=SimpleNamespace(pid=7, identity={'birth': '33'}))
            row = dict(schema='own-cp13-connect-probe-v1', pid=7, birth=33,
                candidate_sha256=l.CP69, binding_reason=9, binding_stage=1,
                failed_record_id=6, source_check_step=2, source_check_passed=False,
                phase=2, wrapper_selected=True, untrusted='PRIVATE_NOT_EXPORTED')
            path = Path(folder) / 'connect-probe-0.json'
            path.write_text(json.dumps(row), encoding='utf-8')
            actual = obs.bridge_status(owner)
            self.assertEqual(actual['status'], 'OBSERVED')
            self.assertFalse(actual['admission_evidence'])
            self.assertEqual(actual['probes'][0]['failed_record_id'], 6)
            self.assertNotIn('PRIVATE_', json.dumps(actual))
            row['birth'] = 34; path.write_text(json.dumps(row), encoding='utf-8')
            self.assertEqual(obs.bridge_status(owner)['probes'][0]['status'], 'UNKNOWN')
    def test_oversized_and_partial_json_are_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            owner = SimpleNamespace(directory=Path(folder), image_sha=l.CP69,
                child=SimpleNamespace(pid=7, identity={'birth': '33'}))
            (Path(folder) / 'connect-probe-0.json').write_bytes(b' ' * 8193)
            (Path(folder) / 'connect-probe-1.json').write_bytes(b'{')
            self.assertTrue(all(p['status'] == 'UNKNOWN' for p in obs.bridge_status(owner)['probes']))
    def test_connect_fix_flags_require_exact_bool_and_current_context(self):
        with tempfile.TemporaryDirectory() as folder:
            expected = l.PRODUCTS['sibling-connect-fix']['image_sha256']
            owner = SimpleNamespace(directory=Path(folder), image_sha=expected,
                child=SimpleNamespace(pid=7, identity={'birth': '33'}))
            row = dict(schema='own-cp13-connect-probe-v1', pid=7, birth=33,
                candidate_sha256=expected, current_original_verified=True,
                prior_all_roles_verified=True, connect_role_revalidated=False,
                fresh_verified_duplicate=True)
            path = Path(folder) / 'connect-probe-0.json'
            path.write_text(json.dumps(row), encoding='utf-8')
            actual = obs.bridge_status(owner)['probes'][0]
            self.assertIs(actual['current_original_verified'], True)
            self.assertIs(actual['prior_all_roles_verified'], True)
            self.assertIs(actual['connect_role_revalidated'], False)
            self.assertIs(actual['fresh_verified_duplicate'], True)
            for key in ('current_original_verified', 'prior_all_roles_verified',
                        'connect_role_revalidated', 'fresh_verified_duplicate'):
                invalid = dict(row); invalid[key] = 1
                path.write_text(json.dumps(invalid), encoding='utf-8')
                self.assertEqual(obs.bridge_status(owner)['probes'][0]['status'], 'UNKNOWN')
            row['candidate_sha256'] = l.CP69
            path.write_text(json.dumps(row), encoding='utf-8')
            self.assertEqual(obs.bridge_status(owner)['probes'][0]['status'], 'UNKNOWN')


class MonitorConditionTests(unittest.IsolatedAsyncioTestCase):
    async def test_scene_condition_is_explicit_and_closes_observer(self):
        owner = FakeOwner()
        class Monitor:
            closed = False
            def bind(self, target): self.target = target
            def tick(self, *a, **kw): return {'memory': {'scene': {'status': 'OBSERVED', 'current': 'Land',
                'pending': 'none', 'root_ready': True}}}
            def close(self): self.closed = True
            def finish(self, report): self.reason = report['reason']
        monitor = Monitor()
        result = await l.run_session(owner, FakeBroker, asyncio.Event(), monitor=monitor,
            until_scene='Land', close_grace_seconds=0)
        self.assertEqual(result['reason'], 'OBSERVATION_CONDITION')
        self.assertFalse(result['normal_exit_verified'])
        self.assertTrue(monitor.closed)
        self.assertTrue(owner.closed)


if __name__ == '__main__':
    unittest.main()


class AttackFeedbackFactoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_feedback_observer_optin_requires_explicit_config_same_real_session_feedback(self):
        from tools.local_original_session import broker_tests, feature_config as fc, attack_session
        # The real product broker and retained Native fixture; no listener or native API.
        await broker_tests.AttackFeedbackRouteTests.asyncSetUp(self)
        spawn = self.realm._npc_spawns[0][0]
        enabled = fc.Features(spawns=(spawn,), attack_policy=fc.ATTACK_INTENT_POLICY,
                              attack_feedback=self.feedback_config)
        legacy = fc.Features(spawns=(spawn,), attack_policy=fc.ATTACK_INTENT_POLICY)
        equal_config = attack_session.FeedbackConfig(self.feedback_config.policy, 0, 8, True)
        different = fc.Features(spawns=(spawn,), attack_policy=fc.ATTACK_INTENT_POLICY,
                                attack_feedback=equal_config)
        for index, (config, expected) in enumerate(((enabled, True), (legacy, False),
                                                    (different, False), (fc.Features(), False))):
            folder = Path(self.temp.name) / ('feedback-factory-' + str(index)); folder.mkdir()
            factory = l.ProductFeatureFactory(self.reader,
                product='sibling-manual-move-attack-target-spawn', control_mode='manual',
                directory=folder, config=config)
            runtime = factory(self.producer)
            self.assertIs(runtime.manual.consumer.observe_attack_feedback, expected)
            runtime.close()
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)


class PublicPrewriteDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    rebuild = InventoryProductTests.rebuild
    publish = InventoryProductTests.publish
    product_clock = InventoryProductTests.product_clock

    async def asyncSetUp(self):
        from tools.local_original_session import inventory_tests
        await inventory_tests.GateTests.asyncSetUp(self)
        await self.rebuild()

    def change_on_readback(self):
        hits = []
        def fault(at, width, raw):
            if at == self.memory.header:
                hits.append(1)
                if len(hits) == 2: return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = fault

    async def fail_actual(self, *, monitor=None):
        from tools.local_original_session import inventory
        if not hasattr(self, 'product_ns'): self.product_clock()
        self.change_on_readback()
        if monitor is None:
            self.publish()
            captured = self.runtime.manual._inventory_diagnostic_capture()
            with self.assertRaisesRegex(ValueError, '^EDGE_TYPED_READ_CHANGED$') as caught:
                await self.runtime.manual.poll_async()
            self.assertIs(type(caught.exception), ValueError)
        else:
            self.producer.key_guard = lambda: True  # Existing retained-owner fixture verdict, as physical refusal tests.
            first = await self.runtime.manual.poll_async(monitor=monitor)
            self.assertEqual((first['status'], first['phase']), ('PENDING', 'ADMISSION'))
            self.assertNotIn('inventory_pre_write', first)
            captured = self.runtime.manual._inventory_diagnostic_capture()
            self.product_ns += 10_000_000_000  # Original deadline; no wall sleep or new read.
            before = len(self.memory.calls)
            with self.assertRaisesRegex(inventory.ReadOnlyPreWriteRefusal, '^EDGE_TYPED_READ_CHANGED$') as caught:
                await self.runtime.manual.poll_async(monitor=monitor)
            self.assertIs(type(caught.exception), inventory.ReadOnlyPreWriteRefusal)
            self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.assertTrue(self.runtime.manual.closed)
        self.assertFalse(self.runtime.manual.last_result['automatic_retry'])
        return caught.exception, captured

    def diagnostic(self, error, captured):
        return self.runtime.manual._inventory_pre_write_diagnostic(error, captured,
            refusal=self.producer._inventory_prewrite_refusal)

    async def test_explicit_real_prewrite_failure_exports_exact_three_keys_and_copies_changed_read(self):
        error, captured = await self.fail_actual()
        public, actual = self.runtime.manual.last_result, self.service.last_result
        diagnostic = public['inventory_pre_write']
        self.assertEqual(set(diagnostic), {'pre_write_stage', 'typed_read_requests', 'changed_read'})
        self.assertEqual(diagnostic, {key: actual[key] for key in diagnostic})
        self.assertEqual((diagnostic['pre_write_stage'], diagnostic['changed_read']['comparison']),
                         ('FINAL_READBACK', 'WORLD_READBACK'))
        self.assertEqual((public['reason'], public['phase']), ('EDGE_TYPED_READ_CHANGED', 'ADMISSION'))
        self.assertTrue(self.service._closed)  # Closed real failed service remains diagnostic evidence.
        self.assertIsNot(diagnostic['changed_read'], actual['changed_read'])
        before = len(self.memory.calls)
        self.assertEqual(self.diagnostic(error, captured), diagnostic)
        self.assertEqual(len(self.memory.calls), before)
        actual['changed_read']['image'] = not actual['changed_read']['image']
        self.assertIsNot(diagnostic['changed_read']['image'], actual['changed_read']['image'])

    async def test_auto_real_prewrite_failure_keeps_public_sequence_and_original_failure(self):
        await InventoryWorldDeliveryTests.asyncSetUp(self)
        error, captured = await self.fail_actual(monitor=self.monitor)
        result = self.runtime.manual.last_result
        self.assertEqual((result['sequence'], result['last_sequence'], result['delivery_policy']),
                         (1, 1, 'LOCAL_WORLD_READY_ONCE'))
        self.assertEqual(result['inventory_pre_write']['pre_write_stage'], 'FINAL_READBACK')
        self.assertEqual((result['phase'], result['reason'], result['refusal_reason']),
                         ('PRE_WRITE', 'FEATURE_INVENTORY_ADMISSION_DEADLINE', 'EDGE_TYPED_READ_CHANGED'))
        self.assertFalse(self.producer._inventory_write_attempted)
        self.assertEqual(self.service.store.path.read_bytes(), self.persisted)
        self.assertIs(self.service.last_result, captured[3])  # Deadline performs no new leaf call.
        self.assertIsNone(self.runtime.manual._inventory_pre_write_diagnostic(error, captured))
        proof = self.producer._inventory_prewrite_refusal
        for index, value in ((0, ValueError(error.reason)), (2, copy.copy(self.service)),
                             (3, 1), (3, False), (4, bytes(bytearray(proof[4])))):
            changed = tuple(value if n == index else item for n, item in enumerate(proof))
            self.producer._inventory_prewrite_refusal = changed
            self.assertIsNone(self.runtime.manual._inventory_pre_write_diagnostic(error, captured, refusal=changed))
        self.producer._inventory_prewrite_refusal = proof
        self.producer._inventory_admission_expired = False
        self.assertIsNone(self.diagnostic(error, captured))
        self.producer._inventory_admission_expired = True
        self.assertEqual(self.diagnostic(error, captured), result['inventory_pre_write'])

    async def test_generic_real_empty_refusal_exports_new_report_only_in_admission(self):
        self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500010, 0x500040)
        self.publish()
        previous = self.service.last_result
        with self.assertRaisesRegex(ValueError, '^INVENTORY_EMPTY_ONLY_LOCAL_POLICY$'):
            await self.runtime.manual.poll_async()
        self.assertIsNot(self.service.last_result, previous)
        row = self.runtime.manual.last_result
        self.assertEqual((row['phase'], row['reason']), ('ADMISSION', 'INVENTORY_EMPTY_ONLY_LOCAL_POLICY'))
        self.assertEqual(row['inventory_pre_write']['pre_write_stage'], 'EMPTY_VECTOR')
        self.assertIsNone(row['inventory_pre_write']['changed_read'])
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    async def test_early_zero_metadata_and_try_outside_cadence_missing_keys(self):
        self.publish()
        with patch.object(self.service, '_restore_mode', side_effect=ValueError('EARLY_FIXTURE_FAILURE')):
            with self.assertRaisesRegex(ValueError, '^EARLY_FIXTURE_FAILURE$'):
                await self.runtime.manual.poll_async()
        self.assertEqual(self.runtime.manual.last_result['inventory_pre_write'],
                         dict(pre_write_stage='SOURCE_BEFORE', typed_read_requests=0, changed_read=None))
        self.assertEqual(self.memory.calls, [])
        await self.rebuild(); self.publish()
        self.service._last_ns = l.time.monotonic_ns()
        with self.assertRaisesRegex(ValueError, '^INVENTORY_CALLER_CADENCE_REQUIRED$'):
            await self.runtime.manual.poll_async()
        self.assertNotIn('inventory_pre_write', self.runtime.manual.last_result)
        self.assertNotIn('pre_write_stage', self.service.last_result)
        self.assertEqual(self.memory.calls, [])

    async def test_polluted_metadata_ranges_types_and_stale_success_are_not_copied(self):
        error, captured = await self.fail_actual()
        manual, actual = self.runtime.manual, copy.deepcopy(self.service.last_result)
        class Text(str):
            pass
        invalid = [lambda r: r.pop('changed_read'),
            lambda r: r.update(status='OBSERVED'), lambda r: r.update(status=Text('UNKNOWN')),
            lambda r: r.update(status=object()), lambda r: r.update(reason='OTHER_ERROR'),
            lambda r: r.update(pre_write_stage='address_0x1234'),
            lambda r: r.update(pre_write_stage='CODE_GUARD_BEFORE_00001'),
            lambda r: r.update(typed_read_requests=True), lambda r: r.update(typed_read_requests=16386),
            lambda r: r.update(typed_bytes_requested=True), lambda r: r.update(typed_bytes_requested=16385),
            lambda r: r.update(pre_write_stage='WORLD_TYPED', typed_read_requests=0, changed_read=None),
            lambda r: r.update(changed_read={Text(key): value for key, value in r['changed_read'].items()}),
            lambda r: r['changed_read'].update(extra=0), lambda r: r['changed_read'].pop('image'),
            lambda r: r['changed_read'].update(stage='CODE_GUARD_BEFORE_123'),
            lambda r: r['changed_read'].update(comparison='raw'),
            lambda r: r['changed_read'].update(request_ordinal=True),
            lambda r: r['changed_read'].update(request_ordinal=16386),
            lambda r: r['changed_read'].update(record_ordinal=True),
            lambda r: r['changed_read'].update(record_ordinal=r['changed_read']['record_count'] + 1),
            lambda r: r['changed_read'].update(record_count=True),
            lambda r: r['changed_read'].update(record_count=16385),
            lambda r: r['changed_read'].update(requested_width=True),
            lambda r: r['changed_read'].update(requested_width=4097),
            lambda r: r['changed_read'].update(typed_bytes_requested=True),
            lambda r: r['changed_read'].update(typed_bytes_requested=16385),
            lambda r: r['changed_read'].update(image=1)]
        calls = len(self.memory.calls)
        for mutate in invalid:
            report = copy.deepcopy(actual); mutate(report); self.service.last_result = report
            with self.subTest(report=report):
                self.assertIsNone(self.diagnostic(error, captured))
        self.service.last_result = actual
        stale = (*captured[:3], actual, *captured[4:])
        self.assertIsNone(manual._inventory_pre_write_diagnostic(ValueError(error.args[0]), stale))
        self.assertEqual(manual.last_result['reason'], 'EDGE_TYPED_READ_CHANGED')
        self.assertEqual(len(self.memory.calls), calls)

    async def test_current_service_frame_reader_or_write_binding_change_omits_metadata(self):
        error, captured = await self.fail_actual()
        manual, service = self.runtime.manual, self.service
        mutations = [('service', self.producer, '_inventory_service', copy.copy(service)),
                     ('broker', service, 'broker', copy.copy(self.producer)),
                     ('reader', service, 'reader', copy.copy(self.reader)),
                     ('frame', self.producer, '_inventory_operation_frame', bytes(bytearray(self.producer._inventory_frame))),
                     ('write', self.producer, '_inventory_write_attempted', True)]
        for mode, obj, name, value in mutations:
            original = getattr(obj, name)
            try:
                setattr(obj, name, value)
                with self.subTest(mode=mode):
                    self.assertIsNone(self.diagnostic(error, captured))
            finally:
                setattr(obj, name, original)
        self.assertEqual(manual.last_result['reason'], 'EDGE_TYPED_READ_CHANGED')
        import builtins
        original_import = builtins.__import__
        def unavailable(name, *args, **kwargs):
            if name == 'tools.local_original_session.inventory': raise ImportError('diagnostic-only fixture')
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, '__import__', side_effect=unavailable):
            self.assertIsNone(manual._inventory_diagnostic_capture())
            self.assertIsNone(manual._inventory_pre_write_diagnostic(error, captured))
        self.assertEqual(manual.last_result['reason'], 'EDGE_TYPED_READ_CHANGED')

    async def test_success_and_client_wait_failure_never_export_prewrite_metadata(self):
        self.product_clock(); self.publish()
        result = await self.runtime.manual.poll_async()
        self.assertEqual(result['phase'], 'CLIENT_WAIT')
        self.assertNotIn('inventory_pre_write', result)
        self.assertEqual(self.service.last_result['status'], 'OBSERVED')
        self.product_ns += 10_000_000_000
        with self.assertRaises(ValueError): await self.runtime.manual.poll_async()
        self.assertEqual(self.runtime.manual.last_result['phase'], 'CLIENT_WAIT')
        self.assertNotIn('inventory_pre_write', self.runtime.manual.last_result)

    async def test_maximum_metadata_stays_within_existing_2048_byte_result_sink(self):
        error, captured = await self.fail_actual()
        manual = self.runtime.manual
        reason, stage = 'E' * 96, 'CODE_GUARD_BEFORE_9999'
        changed = dict(stage=stage, comparison='BUDGET_READBACK', request_ordinal=16385,
            record_ordinal=16384, record_count=16384, requested_width=4096,
            typed_bytes_requested=16384, image=False)
        self.service.last_result = dict(status='UNKNOWN', reason=reason, typed_bytes_requested=16384,
            pre_write_stage=stage, typed_read_requests=16385, changed_read=changed)
        diagnostic = manual._inventory_pre_write_diagnostic(ValueError(reason), captured)
        self.assertIsNotNone(diagnostic)
        manual.sequence = 2147483647
        manual._inventory_auto_selection = (object(),)
        manual.inventory_delivery_policy = 'LOCAL_WORLD_READY_ONCE'
        row = manual._record(dict(status='UNKNOWN', command='AddInventory', phase='ADMISSION',
            reason=reason, write_attempted=False, invoked=False, cleanup_required=True,
            client_inventory='UNKNOWN', inventory_pre_write=diagnostic))
        raw = (self.run / 'command.result.json').read_bytes()
        self.assertEqual(json.loads(raw), row)
        self.assertLessEqual(len(raw), 2048)
        print('public_prewrite_max_record_bytes=' + str(len(raw)))


class InventoryWorldDeliveryTests(unittest.IsolatedAsyncioTestCase):
    """Real source/Empty/readback gate; only the existing monitor projection is injected."""
    publish = InventoryProductTests.publish
    product_clock = InventoryProductTests.product_clock

    async def asyncSetUp(self):
        from tools.local_original_session import feature_config, inventory, inventory_store, inventory_tests
        await inventory_tests.GateTests.asyncSetUp(self)
        await InventoryProductTests.rebuild(self, store_policy=inventory_store.POLICY,
                                            delivery_policy=feature_config.LOCAL_WORLD_READY_ONCE)
        self.product_clock()
        self.saved_fields = inventory_tests.explicit_fields()
        self.saved_fields[4], self.saved_fields[18] = 3, b'saved-original-row'
        self.saved_frame = inventory.build_add(self.saved_fields)
        self.uid = self.realm.service(self.writer).snapshot().uid
        # Only this test-owned temporary store is seeded. Production auto
        # delivery requires select-time restore, and never seeds a store.
        self.service.store.grant(self.uid, self.saved_frame)
        async with self.row['operation_lock']:
            await self.producer._restore_inventory_selection(self.writer)
        self.persisted = self.service.store.path.read_bytes()
        self.monitor = obs.SessionMonitor.__new__(obs.SessionMonitor)
        self.monitor.reader, self.monitor.owner = self.reader, self.reader.owner
        self.monitor.next_memory = 0
        self.monitor.last_memory = dict(status='OBSERVED', current='Land', pending='none', root_ready=True)
        self.monitor.last_world = dict(status='OBSERVED', scene='Land', pending='none', stable_double_read=True,
            my_player_uid=self.uid, map_requested_i32=0, map_resolved_i32=0)

    def materialize(self):
        InventoryPersistenceProductTests.materialize(self)

    async def test_stored_literal_without_command_real_gate_once_readback_and_shared_slot(self):
        self.assertFalse((self.run / 'command.request.json').exists())
        self.assertTrue(self.producer._inventory_restored)
        literal = self.producer._inventory_frame
        self.assertNotEqual(literal, self.factory.config.inventory_frame)
        self.producer.add_inventory = AsyncMock(wraps=self.producer.add_inventory)
        first = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertIs(self.producer.add_inventory.call_args.kwargs['restore_only'], True)
        self.assertEqual((first['status'], first['phase'], first['sequence']), ('PENDING', 'CLIENT_WAIT', 1))
        self.assertEqual(first['delivery_policy'], 'LOCAL_WORLD_READY_ONCE')
        self.assertEqual(first['same_broker_reselection_delivery'], 'UNSUPPORTED')
        self.assertIs(self.writer.write.call_args.args[0], literal)
        self.assertIs(self.producer._inventory_operation_frame, literal)
        self.assertTrue(self.service._claimed)
        self.assertIs(self.producer._inventory_restore_only, True)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 2343)
        self.assertEqual(self.monitor.next_memory, self.producer.inventory_sample_monotonic_ns / 1e9 + .5)
        before = len(self.memory.calls)
        await self.runtime.poll(self.monitor)
        self.assertEqual(len(self.memory.calls), before)
        self.materialize(); self.product_ns += 500_000_000
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual(result['client_inventory'], 'ROW_5_SCALARS_MATCHED')
        self.assertEqual(result['proof_scope'], 'CLIENT_ITEM_ROW_SCALARS_ONLY')
        self.assertFalse(result['automatic_retry'])
        self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(self.service.store.path.read_bytes(), self.persisted)
        self.assertEqual(result['last_sequence'], 1)
        self.publish(sequence=result['last_sequence'] + 1)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.runtime.manual.poll_async(monitor=self.monitor)
        self.assertEqual(self.runtime.manual.last_result['sequence'], 2)
        self.assertNotIn('delivery_policy', self.runtime.manual.last_result)
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_default_off_keeps_explicit_add_without_auto_policy_marker(self):
        self.runtime.manual.inventory_delivery_policy = None
        await self.runtime.poll(self.monitor)
        self.writer.write.assert_not_called(); self.assertEqual(self.memory.calls, [])
        self.publish()
        self.producer.add_inventory = AsyncMock(wraps=self.producer.add_inventory)
        await self.runtime.poll(self.monitor)
        self.assertNotIn('restore_only', self.producer.add_inventory.call_args.kwargs)
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertNotIn('delivery_policy', self.runtime.manual.last_result)
        self.assertIs(self.producer._inventory_restore_only, False)
        self.assertEqual(self.service.store.path.read_bytes(), self.persisted)

    async def test_before_selection_world_unknown_wrong_monitor_and_no_saved_row_do_nothing(self):
        original_scene, original_world = self.monitor.last_memory, self.monitor.last_world
        selected, binding = self.game.selection, self.producer._inventory_selection_binding
        for mode in ('selection', 'restored', 'scene', 'pending', 'world', 'uid', 'map', 'bool_uid', 'reader', 'none'):
            with self.subTest(mode=mode):
                self.monitor.last_memory, self.monitor.last_world = dict(original_scene), dict(original_world)
                self.monitor.reader = self.reader
                self.game.selection, self.producer._inventory_selection_binding = selected, binding
                self.producer._inventory_restored = True
                monitor = self.monitor
                if mode == 'selection': self.game.selection = None
                elif mode == 'restored': self.producer._inventory_restored = False
                elif mode == 'scene': self.monitor.last_memory['current'] = 'Select'
                elif mode == 'pending': self.monitor.last_memory['pending'] = 'Land'
                elif mode == 'world': self.monitor.last_world['status'] = 'UNKNOWN'
                elif mode == 'uid': self.monitor.last_world['my_player_uid'] += 1
                elif mode == 'map': self.monitor.last_world['map_resolved_i32'] = 1
                elif mode == 'bool_uid': self.monitor.last_world['my_player_uid'] = True
                elif mode == 'reader': self.monitor.reader = object()
                else: monitor = None
                await self.runtime.manual.poll_async(monitor=monitor)
                self.assertFalse(self.producer._inventory_attempted)
                self.assertIsNone(self.runtime.manual._inventory_auto_selection)
                self.writer.write.assert_not_called(); self.assertEqual(self.memory.calls, [])
        self.assertEqual(self.service.store.path.read_bytes(), self.persisted)

    async def test_explicit_request_wins_same_slot_with_one_shared_broker_claim(self):
        self.publish(sequence=4)
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((result['status'], result['sequence']), ('PENDING', 4))
        self.assertIsNone(self.runtime.manual._inventory_auto_selection)
        self.assertNotIn('delivery_policy', result)
        self.assertIs(self.producer._inventory_restore_only, False)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_auto_claim_blocks_explicit_race_while_real_operation_lock_waits(self):
        lock = self.row['operation_lock']; await lock.acquire()
        task = asyncio.create_task(self.runtime.manual.poll_async(monitor=self.monitor))
        try:
            await asyncio.sleep(0)
            self.assertTrue(self.producer._inventory_attempted)
            self.writer.write.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
                await self.producer.add_inventory(self.writer)
            lock.release()
            result = await task
            self.assertEqual(result['phase'], 'CLIENT_WAIT')
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        finally:
            if lock.locked(): lock.release()
            if not task.done():
                task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task

    async def test_owner_change_during_checkpoint_is_terminal_write_zero_and_no_retry(self):
        original = self.producer._checkpoint
        child = self.reader.owner.child
        async def changed(writer, row):
            result = await original(writer, row)
            self.reader.owner.child = copy.copy(child)
            return result
        self.producer._checkpoint = changed
        try:
            with self.assertRaises(ValueError): await self.runtime.manual.poll_async(monitor=self.monitor)
        finally:
            self.reader.owner.child = child
        self.assertTrue(self.runtime.manual.closed)
        await self.runtime.manual.poll_async(monitor=self.monitor)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'): await self.producer.add_inventory(self.writer)
        self.writer.write.assert_not_called()
        self.assertEqual(self.service.store.path.read_bytes(), self.persisted)

    async def test_cancelled_auto_lock_wait_never_sends_or_retries(self):
        lock = self.row['operation_lock']; await lock.acquire()
        task = asyncio.create_task(self.runtime.manual.poll_async(monitor=self.monitor))
        try:
            await asyncio.sleep(0)
            self.assertTrue(self.producer._inventory_attempted)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        finally:
            lock.release()
        self.assertTrue(self.runtime.manual.closed)
        self.assertTrue(self.service._closed)
        await self.runtime.manual.poll_async(monitor=self.monitor)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'): await self.producer.add_inventory(self.writer)
        self.writer.write.assert_not_called(); self.assertEqual(self.memory.calls, [])

    async def test_ambiguous_drain_failure_closes_without_resend_or_store_change(self):
        self.writer.drain.side_effect = RuntimeError('fixture ambiguous drain')
        with self.assertRaisesRegex(RuntimeError, 'ambiguous'):
            await self.runtime.manual.poll_async(monitor=self.monitor)
        self.assertTrue(self.runtime.manual.closed)
        self.assertTrue(self.producer._inventory_write_attempted)
        await self.runtime.manual.poll_async(monitor=self.monitor)
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'): await self.producer.add_inventory(self.writer)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(self.service.store.path.read_bytes(), self.persisted)

    async def test_restore_only_auto_deleted_store_at_checkpoint_refuses_without_recreating_row(self):
        from tools.local_original_session import inventory_store
        store, checkpoint = self.service.store, self.producer._checkpoint
        self.assertEqual(store.path.parent, Path(self.temp.name))  # This fixture's temporary sidecar only.
        async def deleted(writer, row):
            result = await checkpoint(writer, row)
            store.path.unlink()
            return result
        self.producer._checkpoint = deleted
        with patch.object(inventory_store.InventoryStore, '_write') as write:
            with self.assertRaisesRegex(ValueError, 'INVENTORY_STORE_EXISTING_ROW_REQUIRED'):
                await self.runtime.manual.poll_async(monitor=self.monitor)
            write.assert_not_called()
        self.assertIs(self.producer._inventory_restore_only, True)
        self.assertFalse(store.path.exists())
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.assertTrue(self.runtime.manual.closed)
        await self.runtime.manual.poll_async(monitor=self.monitor)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertFalse(store.path.exists())


class InventoryReselectionProductTests(unittest.IsolatedAsyncioTestCase):
    """Original broker Restart/Store/source fixture; existing monitor projection only."""
    product_clock = InventoryProductTests.product_clock
    publish = InventoryProductTests.publish
    materialize = lambda self: InventoryPersistenceProductTests.materialize(self)

    async def asyncSetUp(self):
        from tools.local_original_session import broker_tests, feature_config as fc, inventory, inventory_store, restart
        fixture = broker_tests.InventoryReselectionTests
        for name in ('rebuild', 'dispatch', 'select', 'reset_writes', 'restart_reselect'):
            setattr(self, name, types.MethodType(getattr(fixture, name), self))
        await fixture.asyncSetUp(self)
        self.product_clock()
        config = fc.Features(inventory_policy=inventory.POLICY,
            inventory_frame=self.producer._inventory_config_frame, inventory_store_policy=inventory_store.POLICY,
            inventory_delivery_policy=fc.LOCAL_WORLD_READY_ONCE,
            inventory_reselection_policy=fc.LOCAL_SAVED_ROW_ON_RESELECTION, restart_policy=restart.POLICY)
        self.run = Path(self.temp.name) / 'reselection-product'; self.run.mkdir()
        self.factory = l.ProductFeatureFactory(self.reader, product='sibling-manual-play-spawn',
            control_mode='manual', directory=self.run, config=config)
        self.runtime = self.factory(self.producer)
        self.addCleanup(self.runtime.close)
        self.uid = self.realm.service(self.writer).snapshot().uid
        self.monitor = obs.SessionMonitor.__new__(obs.SessionMonitor)
        self.monitor.reader, self.monitor.owner = self.reader, self.reader.owner
        self.monitor.next_memory, self.monitor.samples = 0, 1
        self.monitor.last_memory = dict(status='OBSERVED', current='Land', pending='none', root_ready=True)
        self.monitor.last_world = dict(status='OBSERVED', scene='Land', pending='none', stable_double_read=True,
            my_player_uid=self.uid, map_requested_i32=0, map_resolved_i32=0)

    async def first_delivery(self, *, confirm=True):
        wrapper = self.runtime.manual
        await self.runtime.poll(self.monitor)
        self.assertEqual(wrapper.sequence, 0)
        self.assertEqual(self.memory.calls, [])
        self.monitor.samples += 1
        self.product_ns += 500_000_000
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((result['status'], result['phase'], result['sequence']), ('PENDING', 'CLIENT_WAIT', 1))
        self.assertIs(self.producer._inventory_restore_only, True)
        if confirm:
            self.materialize(); self.product_ns += 500_000_000
            result = (await self.runtime.poll(self.monitor))['manual_move']
            self.assertEqual((result['status'], result['sequence']), ('COMMITTED', 1))
        return result

    def fresh_memory(self):
        from tools.local_original_session import inventory_tests
        self.service = self.producer._inventory_service
        self.memory = inventory_tests.Memory(self)
        self.reset_writes()

    async def test_real_restart_rebind_fresh_sample_restore_only_once_and_global_sequences(self):
        await self.first_delivery()
        wrapper, consumer = self.runtime.manual, self.runtime.manual.consumer
        old, old_observer = wrapper._inventory_generation, wrapper._inventory_observer
        evidence = (old.attempted, old.write_attempted, old.service._claimed, old.frame,
                    old.operation_frame, old.current_frame, old.selection_binding, old.delivery_authority)
        stored = old.store.path.read_bytes()
        stamp = wrapper.last_sample_monotonic_ns
        new = await self.restart_reselect(); self.fresh_memory()
        await wrapper.poll_async(monitor=self.monitor)
        self.assertIs(wrapper._inventory_generation, new)
        self.assertIs(new.previous, old)
        self.assertIsNot(wrapper._inventory_observer, old_observer)
        self.assertTrue(old_observer._closed)
        self.assertTrue(old.service._closed)
        self.assertIs(wrapper.consumer, consumer)
        self.assertEqual((wrapper.sequence, consumer.sequence), (1, 0))
        self.assertEqual(wrapper.last_sample_monotonic_ns, stamp)
        self.assertFalse(new.attempted or new.service._claimed)
        self.assertEqual(self.memory.calls, [])
        self.monitor.samples += 1
        await wrapper.poll_async(monitor=self.monitor)
        self.assertEqual(wrapper.sequence, 2)  # Shared slot still blocks this tick's leaf.
        self.assertFalse(new.attempted)
        self.assertEqual(self.memory.calls, [])
        self.product_ns += 500_000_000
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((result['status'], result['phase'], result['sequence']), ('PENDING', 'CLIENT_WAIT', 2))
        self.assertIs(new.restore_only, True)
        self.assertIs(self.writer.write.call_args.args[0], new.frame)
        self.materialize(); self.product_ns += 500_000_000
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((result['status'], result['sequence'], consumer.sequence), ('COMMITTED', 2, 0))
        self.assertEqual(result['same_broker_reselection_delivery'], 'LOCAL_SAVED_ROW_ON_RESELECTION')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertFalse((self.run / 'command.request.json').exists())
        self.assertEqual(old.store.path.read_bytes(), stored)
        for before, after in zip(evidence, (old.attempted, old.write_attempted, old.service._claimed,
                old.frame, old.operation_frame, old.current_frame, old.selection_binding, old.delivery_authority)):
            self.assertIs(before, after)
        self.assertFalse(self.reader.closed)
        self.assertTrue(wrapper.quiesce_for_source_quit())

    async def test_missing_saved_generation_auto_and_explicit_add_cannot_grant(self):
        await self.first_delivery()
        from tools.local_original_session import broker, inventory_store
        await self.dispatch(broker.RESTART_REQUEST)
        self.producer._inventory_store.path.unlink()  # This fixture's temporary sidecar only.
        await self.select(); self.fresh_memory()
        generation = self.producer.inventory_selection_current(self.writer)
        self.assertFalse(generation.restored)
        self.assertIsNone(generation.frame); self.assertIsNone(generation.selection_binding)
        await self.runtime.manual.poll_async(monitor=self.monitor)
        self.monitor.samples += 1; self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        self.assertEqual(self.runtime.manual.sequence, 1)
        self.publish(sequence=2)
        with patch.object(inventory_store.InventoryStore, '_write') as write:
            with self.assertRaisesRegex(ValueError, 'RESELECTION_SAVED_ROW_REQUIRED'):
                await self.runtime.manual.poll_async(monitor=self.monitor)
            write.assert_not_called()
        self.assertFalse(generation.attempted or generation.service._claimed or generation.store.path.exists())
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    async def test_old_client_wait_and_terminal_consumer_are_not_reused(self):
        await self.first_delivery(confirm=False)
        await self.restart_reselect(); self.fresh_memory()
        wrapper = self.runtime.manual
        with self.assertRaisesRegex(ValueError, 'RESELECTION_PENDING_OR_TERMINAL'):
            await wrapper.poll_async(monitor=self.monitor)
        self.assertTrue(wrapper.closed)
        self.assertEqual(wrapper.sequence, 1)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()

    async def test_native_terminal_unknown_cannot_be_revived_by_new_generation(self):
        await self.first_delivery()
        self.runtime.manual.consumer.cancel()
        await self.restart_reselect(); self.fresh_memory()
        with self.assertRaisesRegex(ValueError, 'RESELECTION_PENDING_OR_TERMINAL'):
            await self.runtime.manual.poll_async(monitor=self.monitor)
        self.assertEqual(self.runtime.manual.consumer.state['status'], 'UNKNOWN')
        self.assertEqual(self.runtime.manual.sequence, 1)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()

    async def test_actual_accessor_reader_and_monitor_identity_are_required(self):
        wrapper, producer = self.runtime.manual, self.producer
        generation = producer.inventory_selection_current(self.writer)
        original = producer.inventory_selection_current
        producer.inventory_selection_current = Mock(return_value=generation)
        with self.assertRaisesRegex(ValueError, 'ACTUAL_GENERATION_API_REQUIRED'):
            wrapper._inventory_reselection_current(self.writer)
        producer.inventory_selection_current.assert_not_called()
        producer.inventory_selection_current = original
        reader = wrapper.consumer.reader
        wrapper.consumer.reader = copy.copy(reader)
        with self.assertRaisesRegex(ValueError, 'CURRENT_GENERATION_REQUIRED'):
            wrapper._inventory_reselection_current(self.writer)
        wrapper.consumer.reader = reader
        await wrapper.poll_async(monitor=self.monitor)
        monitor = copy.copy(self.monitor); monitor.samples += 1
        with self.assertRaisesRegex(ValueError, 'RESELECTION_MONITOR_CHANGED'):
            await wrapper.poll_async(monitor=monitor)
        self.assertEqual(wrapper.sequence, 0)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()

    async def test_observer_constructor_callback_cannot_replace_literal_selection_binding(self):
        from tools.local_original_session.inventory_observe import InventoryObserver
        generation = self.producer.inventory_selection_current(self.writer)
        original = InventoryObserver.__init__
        def swapped(observer, *args, **kwargs):
            original(observer, *args, **kwargs)
            generation.selection_binding = tuple(list(generation.selection_binding))
        with patch.object(InventoryObserver, '__init__', swapped):
            with self.assertRaisesRegex(ValueError, 'GENERATION_CHANGED'):
                await self.runtime.manual.poll_async(monitor=self.monitor)
        self.assertEqual(self.runtime.manual.sequence, 0)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()

    async def test_actual_preparing_checkpoint_does_not_claim_public_request_then_active_rebinds(self):
        from tools.local_original_session import broker
        await self.first_delivery()
        self.publish(sequence=2)
        await self.dispatch(broker.RESTART_REQUEST)
        self.reset_writes()
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.producer._checkpoint
        async def held(writer, row):
            result = await original(writer, row)
            if self.producer._inventory_generation.phase == 'PREPARING':
                entered.set(); await release.wait()
            return result
        self.producer._checkpoint = held
        task = asyncio.create_task(self.select())
        await asyncio.wait_for(entered.wait(), 2)
        try:
            preparing = self.producer._inventory_generation
            calls = len(self.memory.calls)
            result = await self.runtime.manual.poll_async(monitor=self.monitor)
            self.assertEqual((result['status'], self.runtime.manual.sequence), ('COMMITTED', 1))
            self.assertFalse(self.runtime.manual.pending or preparing.attempted or preparing.service._claimed)
            self.assertIsNone(self.runtime.manual._inventory_request)
            self.assertEqual(len(self.memory.calls), calls)
            self.writer.write.assert_not_called()
        finally:
            release.set(); await task; self.producer._checkpoint = original
        self.fresh_memory(); self.product_ns += 500_000_000
        result = await self.runtime.manual.poll_async(monitor=self.monitor)
        self.assertIs(self.runtime.manual._inventory_generation, preparing)
        self.assertEqual((result['status'], result['phase'], result['sequence']), ('PENDING', 'CLIENT_WAIT', 2))
        self.assertIs(preparing.restore_only, True)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))


class InventoryPersistenceProductTests(unittest.IsolatedAsyncioTestCase):
    publish = InventoryProductTests.publish
    product_clock = InventoryProductTests.product_clock

    async def asyncSetUp(self):
        from tools.local_original_session import inventory_tests
        await inventory_tests.GateTests.asyncSetUp(self)
        await self.rebuild()

    async def rebuild(self, **kwargs):
        from tools.local_original_session import inventory_store
        await InventoryProductTests.rebuild(self, store_policy=inventory_store.POLICY, **kwargs)

    def materialize(self):
        from tools.local_original_session import inventory, inventory_observe_tests
        inventory_observe_tests.ObservationTests.one(self)
        layout = inventory._source()[0]['inventory']
        fields = dict(inventory.validate_frame(self.producer._inventory_frame).raw_fields)
        for key, fmt, value in (('row_id_u64', '<Q', fields[1]),
                ('row_template_id_u32', '<I', fields[2] & 0xffffffff),
                ('row_field18_u64', '<Q', fields[3]), ('row_quantity_i64', '<Q', fields[4]),
                ('row_field30_bool', '<B', fields[24])):
            self.memory.put(self.item + layout[key], fmt, value)

    async def test_real_grant_before_write_client_confirmation_and_fresh_broker_adopts_opaque_frame(self):
        from tools.local_original_session import inventory_store, inventory_tests
        self.product_clock()
        self.assertIsNone(self.runtime.manual._inventory_frame)  # Factory bound before select.
        self.assertFalse(self.producer._inventory_restored)
        self.assertIs(self.service.store, self.producer._inventory_store)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()
        saved_uid = self.realm.service(self.writer).snapshot().uid
        adopted = self.producer._inventory_frame
        def written(wire):
            self.assertIs(wire, adopted)
            self.assertTrue(self.service._claimed)
            self.assertEqual(self.service.last_result['status'], 'OBSERVED')
            self.assertEqual(self.service.store.restore(saved_uid), wire)  # Value, not read identity.
            self.assertIsNotNone(self.row['policy_row'].drain_started_ns)
        self.writer.write.side_effect = written
        self.publish()
        first = (await self.runtime.poll(SimpleNamespace(next_memory=0)))['manual_move']
        self.assertEqual((first['status'], first['phase']), ('PENDING', 'CLIENT_WAIT'))
        self.assertIs(self.producer._inventory_operation_frame, adopted)
        self.assertIs(self.runtime.manual._inventory_frame, adopted)
        self.materialize(); self.product_ns += 500_000_000
        result = await self.runtime.manual.poll_async()
        self.assertEqual(result['proof_scope'], 'CLIENT_ITEM_ROW_SCALARS_ONLY')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        persisted = self.service.store.path.read_bytes()
        old = self.producer
        self.runtime.close(); old._fail('FIXTURE_CLOSED'); old.realm.close(self.writer)
        self.writer = SimpleNamespace(transport=SimpleNamespace(get_write_buffer_size=lambda: 0),
                                      write=Mock(), drain=AsyncMock())
        fallback = inventory_tests.explicit_fields(); fallback[4] = 2; fallback[18] = b'new-explicit-fallback'
        await self.rebuild(fallback_fields=fallback)
        self.assertIsNot(self.producer, old)
        self.assertFalse(self.producer._inventory_attempted)
        self.assertTrue(self.producer._inventory_restored)
        restored = self.producer._inventory_frame
        self.assertEqual(restored, adopted)
        self.assertIsNot(restored, adopted)  # A new read's bytes are not old send authority.
        self.assertNotEqual(restored, self.factory.config.inventory_frame)
        self.assertIsNone(self.producer._inventory_operation_frame)
        self.assertIsNone(self.runtime.manual._inventory_frame)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()
        self.publish(); await self.runtime.poll(SimpleNamespace(next_memory=0))
        self.assertIs(self.writer.write.call_args.args[0], restored)
        self.materialize(); self.product_ns += 500_000_000
        result = await self.runtime.manual.poll_async()
        self.assertEqual(result['proof_scope'], 'CLIENT_ITEM_ROW_SCALARS_ONLY')
        self.assertIs(self.runtime.manual._inventory_frame, restored)
        self.assertIs(self.producer._inventory_operation_frame, restored)
        self.assertEqual(self.service.store.path.read_bytes(), persisted)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)

    def inventory_temporary_fd(self, fd):
        from tools.local_original_session import inventory_store
        inode = inventory_store.os.fstat(fd).st_ino
        return any(p.stat().st_ino == inode for p in self.service.store.path.parent.glob('.inventory-*.tmp'))

    async def test_real_grant_io_failure_terminal_zero_write_no_retry(self):
        from tools.local_original_session import inventory_store
        self.publish()
        fsync = inventory_store.os.fsync
        def failed(fd):
            if self.inventory_temporary_fd(fd): raise OSError('fixture durable failure')
            return fsync(fd)
        with patch.object(inventory_store.os, 'fsync', failed):
            with self.assertRaises(ValueError): await self.runtime.manual.poll_async()
        self.assertTrue(self.service._closed)
        self.writer.write.assert_not_called()
        before = len(self.memory.calls)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer)
        self.assertEqual(len(self.memory.calls), before)

    async def test_real_grant_cancel_preserves_durable_row_but_never_writes_or_retries(self):
        from tools.local_original_session import inventory_store
        fsync = inventory_store.os.fsync
        def cancelling(fd):
            fsync(fd)
            if self.inventory_temporary_fd(fd):
                asyncio.current_task().cancel('cancel during actual durable grant')
        self.publish()
        with patch.object(inventory_store.os, 'fsync', cancelling):
            task = asyncio.create_task(self.runtime.manual.poll_async())
            with self.assertRaises(asyncio.CancelledError): await task
        self.writer.write.assert_not_called()
        self.assertTrue(self.service._closed)
        uid = self.realm.service(self.writer).snapshot().uid
        self.assertEqual(self.service.store.restore(uid), self.producer._inventory_frame)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer)

    async def test_after_grant_native_readback_unknown_has_no_write_or_retry(self):
        self.publish()
        hits = [0]
        def fault(at, size, raw):
            if at == self.memory.header and size == 24:
                hits[0] += 1
                if hits[0] == 2: return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = fault
        with self.assertRaises(ValueError): await self.runtime.manual.poll_async()
        self.assertTrue(self.service._closed)
        self.writer.write.assert_not_called()
        uid = self.realm.service(self.writer).snapshot().uid
        self.assertEqual(self.service.store.restore(uid), self.producer._inventory_frame)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer)

    async def test_restore_file_io_selection_loss_never_adopts_or_allows_add(self):
        from tools.local_original_session import inventory_store
        original_frame, original_binding = self.producer._inventory_frame, self.producer._inventory_selection_binding
        original = inventory_store.os.fstat
        profile_inode = self.realm.store.path.stat().st_ino
        changed = [False]
        def stale(fd):
            result = original(fd)
            if result.st_ino == profile_inode and not changed[0]:
                changed[0] = True
                self.realm.registry.selected.clear()
            return result
        async with self.row['operation_lock']:
            with patch.object(inventory_store.os, 'fstat', stale), self.assertRaises(ValueError):
                await self.producer._restore_inventory_selection(self.writer)
        self.assertTrue(changed[0])
        self.assertIs(self.producer._inventory_frame, original_frame)
        self.assertIs(self.producer._inventory_selection_binding, original_binding)
        self.assertTrue(self.service._closed)
        self.writer.write.assert_not_called()

    async def test_restore_file_io_cancel_does_not_publish_replacement_authority(self):
        from tools.local_original_session import inventory_store
        original_frame, original_binding = self.producer._inventory_frame, self.producer._inventory_selection_binding
        original = inventory_store.os.fstat
        profile_inode = self.realm.store.path.stat().st_ino
        hit = [False]
        def cancelling(fd):
            result = original(fd)
            if result.st_ino == profile_inode and not hit[0]:
                hit[0] = True
                asyncio.current_task().cancel('cancel on actual restore file read')
            return result
        async def operation():
            async with self.row['operation_lock']:
                await self.producer._restore_inventory_selection(self.writer)
        with patch.object(inventory_store.os, 'fstat', cancelling):
            task = asyncio.create_task(operation())
            with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(hit[0])
        self.assertIs(self.producer._inventory_frame, original_frame)
        self.assertIs(self.producer._inventory_selection_binding, original_binding)
        self.assertTrue(self.service._closed)
        self.writer.write.assert_not_called()

    async def test_after_delivery_frame_copy_policy_callback_refuses_no_resend(self):
        begin = self.producer.policy.begin_write
        def changed(*args, **kwargs):
            result = begin(*args, **kwargs)
            self.producer._inventory_frame = bytes(bytearray(self.producer._inventory_frame))
            return result
        self.producer.policy.begin_write = changed
        self.publish()
        with self.assertRaises(ValueError): await self.runtime.manual.poll_async()
        self.writer.write.assert_not_called()
        self.assertTrue(self.service._closed)
        self.assertTrue(self.producer._inventory_attempted)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer)

    async def test_persisted_grant_ambiguous_drain_is_one_attempt_not_redelivery(self):
        self.publish()
        self.writer.drain.side_effect = ConnectionError('actual drain outcome unknown')
        with self.assertRaises(ConnectionError): await self.runtime.manual.poll_async()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        uid = self.realm.service(self.writer).snapshot().uid
        self.assertEqual(self.service.store.restore(uid), self.producer._inventory_frame)
        self.assertTrue(self.service._closed)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer)
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_same_broker_game_restart_reselect_preserves_once_no_redelivery(self):
        from tools.local_original_session import restart, broker_tests, broker
        await self.rebuild(restart_policy=restart.POLICY)
        self.product_clock(); self.publish()
        await self.runtime.poll(SimpleNamespace(next_memory=0))
        self.materialize(); self.product_ns += 500_000_000
        self.assertEqual((await self.runtime.manual.poll_async())['status'], 'COMMITTED')
        frame, authority = self.producer._inventory_frame, self.producer._inventory_delivery_authority
        position = self.realm.service(self.writer).snapshot()
        await broker_tests.AttackIntentRouteTests.dispatch(self, broker_tests.c2s(broker.RESTART_REQUEST))
        self.assertIsNone(self.game.selection)
        payload = broker.movement.pb.encode_bytes(1, position.name.encode()) + b'\x10\0\x18\0'
        await broker_tests.AttackIntentRouteTests.dispatch(self, broker_tests.c2s(0x4e28, payload))
        self.assertIsNotNone(self.game.selection)
        self.assertTrue(self.producer._inventory_attempted)
        self.assertIs(self.producer._inventory_frame, frame)
        self.assertIs(self.producer._inventory_delivery_authority, authority)
        before, writes = len(self.memory.calls), self.writer.write.call_count
        with self.assertRaisesRegex(ValueError, 'ONCE_OPERATION'):
            await self.producer.add_inventory(self.writer)
        self.assertEqual((len(self.memory.calls), self.writer.write.call_count), (before, writes))

    async def test_restore_callback_cannot_replace_canonical_fallback_after_file_read(self):
        from tools.local_original_session import inventory, inventory_tests
        original, binding = self.producer._inventory_frame, self.producer._inventory_selection_binding
        fields = inventory_tests.explicit_fields(); fields[4] = 2
        replacement = inventory.build_add(fields)
        self.assertNotEqual(replacement, original)
        async def owner(_):
            await asyncio.sleep(0)
            self.producer._inventory_config_frame = replacement
            return True
        self.producer.owner_guard = owner
        async with self.row['operation_lock']:
            with self.assertRaisesRegex(ValueError, 'SELECTED_CONFIG_FRAME_CHANGED'):
                await self.producer._restore_inventory_selection(self.writer)
        self.assertIs(self.producer._inventory_frame, original)
        self.assertIs(self.producer._inventory_selection_binding, binding)
        self.assertTrue(self.service._closed)
        self.writer.write.assert_not_called()
        self.assertEqual(self.memory.calls, [])


class ItemUseFactoryOptionTests(unittest.TestCase):
    def test_explicit_item_use_config_passes_policy_only_and_default_options_stay_absent(self):
        from tools.local_original_session import feature_config, inventory, inventory_tests, inventory_store, item_use_session
        raw = {str(k): list(v) if type(v) is bytes else v for k, v in inventory_tests.explicit_fields().items()}
        config = feature_config.parse(dict(schema=feature_config.SCHEMA, npc=None,
            inventory=dict(policy=inventory.POLICY, fields=raw, store_policy=inventory_store.POLICY),
            item_use=dict(policy=item_use_session.POLICY)))
        reader = object()
        factory = l.ProductFeatureFactory(reader, product='sibling-manual-play-spawn',
            control_mode='manual', directory=Path('.'), config=config)
        options = factory.broker_options()
        self.assertEqual(options['item_use_policy'], item_use_session.POLICY)
        self.assertIs(options['inventory_frame'], config.inventory_frame)
        self.assertIs(options['inventory_reader'], reader)
        default = l.ProductFeatureFactory(reader, product='sibling-manual-play-spawn',
            control_mode='manual', directory=Path('.'), config=feature_config.Features())
        self.assertEqual(default.broker_options(), {})


class UseItemProductLinkTests(unittest.IsolatedAsyncioTestCase):
    async def fixture(self, *, product='sibling-background-use-item-source-quit-spawn', enabled=True):
        from tools.local_original_session import manual_move_commands_tests as source, feature_config, inventory_store, item_use_session
        for name in ('adapter', 'sample', 'native_result', 'receive'):
            setattr(self, name, types.MethodType(getattr(source.ManualUseItemTests, name), self))
        await source.ManualUseItemTests.asyncSetUp(self)
        config = feature_config.Features(inventory_policy=self.service.policy,
            inventory_frame=self.producer._inventory_frame, inventory_store_policy=inventory_store.POLICY,
            item_use_policy=item_use_session.POLICY if enabled else None)
        self.factory = l.ProductFeatureFactory(self.reader, product=product, control_mode='manual',
            directory=self.directory, config=config)
        self.runtime = self.factory(self.producer)
        self.wrapper = self.runtime.manual
        self.consumer = self.wrapper.consumer
        self.consumer.clock_ns = lambda: self.now
        return source

    def public(self, sequence=2, **changes):
        from tools.local_original_session.commands import REQUEST_SCHEMA
        p = self.movement_service.snapshot()
        values = dict(schema=REQUEST_SCHEMA, sequence=sequence, command='UseItem', uid=p.uid,
                      item_identifier=self.item_identifier, map_id=p.map_id)
        values.update(changes)
        (self.directory / 'command.request.json').write_text(json.dumps(values), encoding='utf-8')

    async def complete(self):
        from tools.local_original_session.manual_move_commands import SAMPLE_NS
        self.now += SAMPLE_NS
        native = await self.wrapper.poll_async()
        self.assertEqual(native['phase'], 'NATIVE_WAIT', native)
        self.native_result()
        self.now += SAMPLE_NS
        returned = await self.wrapper.poll_async()
        self.assertEqual(returned['status'], 'PENDING', returned)
        await self.receive()
        self.now += SAMPLE_NS
        result = await self.wrapper.poll_async()
        self.assertEqual((result['status'], result['command'], result['proof_scope']),
            ('COMMITTED', 'UseItem', 'VALIDATED_ITEM_USE_INTENT_ONLY'))
        return result

    async def test_real_factory_public_once_claim_native_sequence_and_sourcequit_handoff(self):
        await self.fixture()
        self.assertTrue(self.factory.allow_use_item and self.consumer.allow_use_item and self.wrapper.allow_use_item)
        record, post = self.wrapper._record, self.owner.native.u.PostMessageW
        claimed = []
        def recorded(row):
            result = record(row)
            if row['status'] == 'CLAIMED': claimed.append(self.wrapper.sequence)
            return result
        def posted(*args):
            self.assertIn(self.wrapper.sequence, claimed)
            return post(*args)
        self.wrapper._record = recorded
        self.owner.native.u.PostMessageW = posted
        self.public(2)
        result = await self.wrapper.poll_async()
        self.assertEqual((result['sequence'], result['phase']), (2, 'ADMISSION'))
        self.assertFalse(self.posts)
        result = await self.complete()
        self.assertEqual(result['sequence'], 2)
        self.assertEqual(self.consumer.sequence, 1)
        self.assertFalse(self.wrapper.pending)
        self.public(2)
        self.assertEqual((await self.wrapper.poll_async())['sequence'], 2)
        self.assertEqual(len(self.posts), 1)
        self.public(5)
        self.assertEqual((await self.wrapper.poll_async())['phase'], 'ADMISSION')
        result = await self.complete()
        self.assertEqual((result['sequence'], self.consumer.sequence, len(self.posts)), (5, 2, 2))
        self.assertTrue(self.wrapper.quiesce_for_source_quit())
        self.assertTrue(self.wrapper.closed)
        self.assertEqual(self.consumer.state['status'], 'COMMITTED')
        self.assertIsNone(self.consumer.pending)
        self.writer.write.assert_not_called()  # Fixture reset after original Inventory; UseItem reply0.

    async def test_old_product_or_missing_policy_and_sync_request_cannot_post(self):
        for product, enabled in (('sibling-background-source-quit-spawn', True),
                                 ('sibling-background-use-item-source-quit-spawn', False)):
            await self.fixture(product=product, enabled=enabled)
            self.assertFalse(self.factory.allow_use_item or self.consumer.allow_use_item or self.wrapper.allow_use_item)
            self.public()
            with self.assertRaisesRegex(ValueError, 'USE_ITEM_NOT_ENABLED'):
                await self.wrapper.poll_async()
            self.assertFalse(self.posts)
        await self.fixture()
        self.public()
        with self.assertRaisesRegex(ValueError, 'USE_ITEM_NOT_ENABLED'): self.wrapper.poll()
        self.assertFalse(self.posts)

    async def test_exact_six_keys_u64_bool_and_incomplete_or_other_completion_are_not_accepted(self):
        await self.fixture()
        self.public(extra=True)
        with self.assertRaisesRegex(ValueError, 'SCHEMA_REQUIRED'): await self.wrapper.poll_async()
        self.assertFalse(self.posts)
        # Each malformed public request precedes any consumer operation.
        await self.fixture()
        self.public(item_identifier=True)
        with self.assertRaisesRegex(ValueError, 'USE_ITEM_UID_MAP_REQUIRED'): await self.wrapper.poll_async()
        self.assertFalse(self.posts)
        await self.fixture()
        self.public()
        await self.wrapper.poll_async()
        result = await self.complete()
        original = dict(self.consumer.state)
        for change in ({'proof_scope': 'NATIVE_RETURNED'}, {'command': 'AttackTarget'},
                       {'ack': 'OBSERVED'}, {'use_effect': 'COMPLETED'}, {'native_attempted': False}):
            changed = dict(original, **change)
            self.consumer.state = changed
            with self.subTest(change=change):
                self.assertFalse(self.wrapper._actual_use_item_commit(changed, asynchronous=True))
        self.consumer.state = original
        with patch.object(l, '_MANUAL_REJECTION_SOURCE_SHA', '0' * 64):
            self.assertFalse(self.wrapper._actual_use_item_commit(original, asynchronous=True))
        self.assertEqual(result['status'], 'COMMITTED')


class UseItemProductMetadataTests(unittest.TestCase):
    def test_exact_new_bridge_only_capability_and_trial_preserve_old_sourcequit(self):
        old = l.PRODUCTS['sibling-background-source-quit-spawn']
        candidate = l.PRODUCTS['sibling-background-use-item-source-quit-spawn']
        expected = {**old, 'bridges': {**old['bridges'], 'own-login-bridge-dg49.dll':
            '90dee4d8d7f56ef6400c059acaa0134309bc07d6bec14c59ffe575f9450004ed'},
            'bridge_artifact': l.ROOT / 'work/local_original_session/implementation-1/manual-source-restart/own-login-bridge-dg49.dll',
            'manual_use_item': True}
        self.assertEqual(candidate, expected)
        self.assertEqual(l.digest(candidate['bridge_artifact']), candidate['bridges']['own-login-bridge-dg49.dll'])
        self.assertNotIn('manual_use_item', old)
        self.assertEqual(old['bridges']['own-login-bridge-dg49.dll'],
            'd5865458c910415c4007f169cea64c5f99e31e78ad6c19a7d0dd7f635d53da8d')
        root = l.ROOT / 'work/local_original_session/integration-1/use-item-product-link'
        original = json.loads((root / 'before-runtime-config.json').read_bytes())
        trial = json.loads((root / 'attack-inventory-auto-use-item-runtime-config.json').read_bytes())
        self.assertEqual(trial.pop('item_use'), dict(policy='EXPLICIT_LOCAL_VALIDATED_ITEM_USE_INTENT'))
        self.assertEqual(trial, original)

    def test_new_product_requires_background_and_sourcequit_before_native_or_socket(self):
        for flags, code in (([], 'SOURCE_QUIT_EXPLICIT_TEST_REQUIRED'),
                            (['--background'], 'SOURCE_QUIT_EXPLICIT_TEST_REQUIRED'),
                            (['--source-quit-test'], 'SOURCE_QUIT_BACKGROUND_PRODUCT_REQUIRED')):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as root:
                directory = Path(root) / 'run'
                args = ['launcher', '--run', '--control-mode', 'manual', '--image', str(Path(root) / 'fixture.exe'),
                    '--product', 'sibling-background-use-item-source-quit-spawn', '--expected-uuid', 'fixture',
                    '--store', str(Path(root) / 'store.json'), '--run-directory', str(directory), *flags]
                with patch.object(l.sys, 'argv', args), patch.object(l, 'preflight') as preflight, \
                     patch.object(l, 'NativeOwner') as owner, patch.object(l.socket, 'socket') as socket, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(l.main(), 2)
                preflight.assert_not_called(); owner.assert_not_called(); socket.assert_not_called()
                self.assertEqual(json.loads((directory / 'result.json').read_text())['error_code'], code)


class InventoryUpdateProductTests(unittest.IsolatedAsyncioTestCase):
    product_clock = InventoryProductTests.product_clock

    async def asyncSetUp(self):
        from tools.local_original_session import broker, inventory_tests, inventory_store
        await inventory_tests.GateTests.asyncSetUp(self)
        await InventoryProductTests.rebuild(self, store_policy=inventory_store.POLICY,
            inventory_update_policy=broker.INVENTORY_UPDATE_POLICY,
            product='sibling-background-inventory-update-source-quit-spawn')
        self.producer.key_guard = lambda: True  # Existing injected retained-key fixture contract.
        self.product_clock()
        self.monitor = SimpleNamespace(next_memory=0)
        InventoryProductTests.publish(self, sequence=1)
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual(result['status'], 'PENDING')
        self.materialize(self.producer._inventory_current_frame)
        self.product_ns += 500_000_000
        result = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual(result['status'], 'COMMITTED')
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.initial = self.producer._inventory_frame
        self.old = self.producer._inventory_current_frame

    def materialize(self, frame):
        from tools.local_original_session import inventory, inventory_observe_tests
        inventory_observe_tests.ObservationTests.one(self)
        layout = inventory._source()[0]['inventory']
        fields = dict(inventory.validate_frame(frame).raw_fields)
        for key, fmt, value in (('row_id_u64', '<Q', fields[1]),
                ('row_template_id_u32', '<I', fields[2] & 0xffffffff),
                ('row_field18_u64', '<Q', fields[3]), ('row_quantity_i64', '<Q', fields[4]),
                ('row_field30_bool', '<B', fields[24])):
            self.memory.put(self.item + layout[key], fmt, value)

    def publish(self, sequence=3, **extra):
        from tools.local_original_session import inventory
        from tools.local_original_session.commands import REQUEST_SCHEMA
        position = self.realm.service(self.writer).snapshot()
        request = dict(schema=REQUEST_SCHEMA, sequence=sequence, command='UpdateInventory',
            uid=position.uid, item_identifier=inventory.validate_frame(self.old).identifier,
            map_id=position.map_id, field4_u64=2)
        request.update(extra)
        (self.run / 'command.request.json').write_text(json.dumps(request))

    async def test_exact_public_update_actual_cas_wire_drain_next_slot_scalar_commit_then_old_quit(self):
        from tools.local_original_session import broker, broker_tests, inventory
        self.publish()
        self.product_ns += 500_000_000
        checkpoint = self.producer._checkpoint
        claimed = []
        async def checked(writer, row):
            claimed.append(json.loads((self.run / 'command.result.json').read_text())['status'])
            self.assertTrue(row['operation_lock'].locked())
            return await checkpoint(writer, row)
        with patch.object(self.producer, '_checkpoint', checked):
            first = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual(first['status'], 'PENDING')
        self.assertEqual(first['phase'], 'CLIENT_WAIT')
        self.assertEqual(claimed[:2], ['CLAIMED', 'CLAIMED'])
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(int.from_bytes(self.writer.write.call_args.args[0][2:4], 'little'), 0x0965)
        self.assertIs(self.producer._inventory_frame, self.initial)
        self.assertIs(self.producer._inventory_operation_frame, self.initial)
        current = self.producer._inventory_current_frame
        self.assertEqual(dict(inventory.validate_frame(current).raw_fields)[4], 2)
        self.materialize(current)
        self.product_ns += 500_000_000
        complete = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((complete['status'], complete['sequence'], complete['last_sequence'],
            complete['command'], complete['phase'], complete['proof_scope'], complete['storage']),
            ('COMMITTED', 3, 3, 'UpdateInventory', 'CLIENT_CONFIRMED',
             'CLIENT_ITEM_FIELD4_MATCHED', 'LOCAL_OPAQUE_FRAME_REPLACED'))
        self.assertFalse(complete['native_attempted'] or complete['automatic_retry'] or complete['cleanup_required'])
        self.assertEqual(tuple(complete[k] for k in ('effect', 'ack', 'hp', 'equipped', 'render')), ('UNKNOWN',) * 5)
        self.assertLessEqual((self.run / 'command.result.json').stat().st_size, 2048)
        self.assertEqual(self.producer._inventory_update_operation['phase'], 'DRAINED')
        await self.runtime.manual.poll_async()  # Same public sequence is consumed, never resent.
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertTrue(self.runtime.manual.quiesce_for_source_quit())
        await broker_tests.AttackIntentRouteTests.dispatch(self, broker_tests.c2s(broker.QUIT_REQUEST))
        self.assertTrue(self.realm.quit_state(self.writer)['response_drained'])
        self.assertEqual(self.writer.write.call_args.args[0], broker.QUIT_SUCCESS_FRAME)

    async def test_default_old_product_or_policy_off_cannot_admit_update(self):
        from tools.local_original_session import feature_config as fc
        old_product = 'sibling-background-source-quit-spawn'
        old = l.ProductFeatureFactory(self.reader, product=old_product, control_mode='manual',
            directory=Path(self.temp.name), config=self.factory.config)
        self.assertFalse(old.allow_inventory_update)
        no_policy = fc.Features(inventory_policy=self.factory.config.inventory_policy,
            inventory_frame=self.factory.config.inventory_frame,
            inventory_store_policy=self.factory.config.inventory_store_policy)
        off = l.ProductFeatureFactory(self.reader, product='sibling-background-inventory-update-source-quit-spawn',
            control_mode='manual', directory=Path(self.temp.name), config=no_policy)
        self.assertFalse(off.allow_inventory_update)
        self.assertNotIn('inventory_update_policy', off.broker_options())
        candidate, source = (l.PRODUCTS[k] for k in ('sibling-background-inventory-update-source-quit-spawn', old_product))
        self.assertEqual({k: v for k, v in candidate.items() if k != 'manual_inventory_update'}, source)
        self.runtime.manual.allow_inventory_update = False
        self.publish(); self.product_ns += 500_000_000
        with self.assertRaisesRegex(ValueError, 'UPDATE_NOT_ENABLED'): await self.runtime.poll(self.monitor)
        self.writer.write.assert_not_called()

    async def test_malformed_uid_map_field_and_exact_keys_never_claim_or_send(self):
        for edit in ({'field4_u64': True}, {'field4_u64': -1}, {'field4_u64': 1 << 64},
                     {'item_identifier': True}, {'uid': True}, {'map_id': True}, {'extra': 0}):
            self.publish(**edit)
            self.product_ns += 500_000_000
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                self.runtime.manual._receive(self.runtime.manual.consumer.state, asynchronous=True)
        self.assertEqual(self.runtime.manual.sequence, 1)
        self.writer.write.assert_not_called()

    async def test_client_wait_keeps_first_deadline_no_resend_and_unknown_closes(self):
        from tools.local_original_session.manual_move_commands import WAIT_NS
        self.publish(); self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        original_deadline = self.runtime.manual._inventory_started_ns + WAIT_NS
        self.product_ns = original_deadline
        with self.assertRaisesRegex(ValueError, 'TERMINAL_UNKNOWN'):
            await self.runtime.poll(self.monitor)
        result = json.loads((self.run / 'command.result.json').read_text())
        self.assertEqual((result['status'], result['command'], result['phase']),
            ('UNKNOWN', 'UpdateInventory', 'CLIENT_WAIT'))
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertTrue(self.runtime.manual.closed)


    async def test_exact_previous_field4_waits_same_deadline_then_new_row_commits_without_resend(self):
        self.publish(); self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        started = self.runtime.manual._inventory_started_ns
        self.product_ns += 500_000_000
        previous = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual((previous['status'], previous['phase'], previous['reason']),
            ('PENDING', 'CLIENT_WAIT', 'INVENTORY_OBSERVE_PREVIOUS_FIELD4_PENDING'))
        self.assertEqual(self.runtime.manual._inventory_started_ns, started)
        self.materialize(self.producer._inventory_current_frame)
        self.product_ns += 500_000_000
        complete = (await self.runtime.poll(self.monitor))['manual_move']
        self.assertEqual(complete['proof_scope'], 'CLIENT_ITEM_FIELD4_MATCHED')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))

    async def test_previous_success_then_new_noop_sequence_never_reports_previous_write(self):
        self.publish(); self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        self.materialize(self.producer._inventory_current_frame); self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        operation = self.producer._inventory_update_operation
        frame = self.producer._inventory_current_frame
        stored = self.producer._inventory_store.path.read_bytes()
        self.publish(sequence=4, field4_u64=2); self.product_ns += 500_000_000
        with self.assertRaisesRegex(ValueError, 'ACTUAL_CHANGE_REQUIRED'):
            await self.runtime.poll(self.monitor)
        result = json.loads((self.run / 'command.result.json').read_text())
        self.assertEqual((result['status'], result['sequence'], result['write_attempted'], result['invoked']),
            ('UNKNOWN', 4, False, False))
        self.assertIs(self.producer._inventory_update_operation, operation)
        self.assertIs(self.producer._inventory_current_frame, frame)
        self.assertEqual(self.producer._inventory_store.path.read_bytes(), stored)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))

    async def test_after_real_drain_store_deleted_or_conflicting_blocks_client_confirmation(self):
        from tools.local_original_session import inventory
        self.publish(); self.product_ns += 500_000_000
        await self.runtime.poll(self.monitor)
        frame = self.producer._inventory_current_frame
        operation = self.producer._inventory_update_operation
        self.materialize(frame)
        store = self.producer._inventory_store; saved = store.path.read_bytes()
        for conflict in (False, True):
            store.path.write_bytes(saved)
            if conflict:
                uid = self.realm.service(self.writer).snapshot().uid
                wrong = inventory.build_add(dict(inventory.validate_frame(frame).raw_fields) | {4: 7})
                store.replace_existing(uid, frame, wrong)
            else: store.path.write_text('{"version":1,"inventories":[]}\n')
            self.product_ns += 500_000_000
            before = len(self.memory.calls)
            with self.subTest(conflict=conflict), self.assertRaisesRegex(ValueError, 'STORED_FRAME_CHANGED'):
                self.runtime.manual._inventory_client_current()
            self.assertEqual(len(self.memory.calls), before)
        with self.assertRaisesRegex(ValueError, 'STORED_FRAME_CHANGED'):
            await self.runtime.poll(self.monitor)
        result = json.loads((self.run / 'command.result.json').read_text())
        self.assertEqual((result['status'], result['command']), ('UNKNOWN', 'UpdateInventory'))
        self.assertIs(self.producer._inventory_update_operation, operation)
        self.assertIs(self.producer._inventory_current_frame, frame)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))

    async def test_update_admission_deadline_never_uses_initial_add_deadline_state(self):
        from tools.local_original_session.manual_move_commands import WAIT_NS
        self.publish()
        manual = self.runtime.manual
        manual._receive(manual.consumer.state, asynchronous=True)
        self.product_ns = manual._inventory_started_ns + WAIT_NS
        with patch.object(self.producer, '_inventory_admission_time',
                side_effect=AssertionError('Update must not consume old Add admission state')):
            with self.assertRaisesRegex(ValueError, 'TERMINAL_UNKNOWN'):
                await manual.poll_async()
        result = json.loads((self.run / 'command.result.json').read_text())
        self.assertEqual(result['reason'], 'FEATURE_INVENTORY_ADMISSION_DEADLINE')
        self.assertEqual(result['command'], 'UpdateInventory')
        self.writer.write.assert_not_called()
