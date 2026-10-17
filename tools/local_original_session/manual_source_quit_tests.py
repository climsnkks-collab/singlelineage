"""Real wrapper/broker/service plus existing synthetic memory and WinAPI only."""
import asyncio
import ctypes as C
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import broker as b, launcher, manual_move_commands as m, commands
from tools.local_original_session import manual_move_commands_tests as existing
from tools.local_original_session.manual_source_quit import SourceQuitRequests


class SourceQuitTests(unittest.IsolatedAsyncioTestCase):
    tiles = existing.ManualAttackTests.tiles
    submit_attack = existing.ManualAttackTests.submit_attack
    admit_attack = existing.ManualAttackTests.admit_attack
    accepted_attack = existing.ManualAttackTests.accepted_attack
    received = existing.ManualAttackTests.received
    native_result = existing.ManualAttackTests.native_result
    private_desktop_fixture = existing.ManualMoveTests.private_desktop_fixture

    async def asyncSetUp(self):
        await existing.ManualAttackTests.asyncSetUp(self)
        retained_kernel = vars(self.owner.native.k).copy()
        self.private, self.desktop_state, self.post_threads, _ = self.private_desktop_fixture()
        for name, value in retained_kernel.items():
            if not hasattr(self.owner.native.k, name):
                setattr(self.owner.native.k, name, value)
        # The real dynamic loader intentionally does not register this alias.
        self.alias = launcher._module('_source_quit_actual_launcher', Path(launcher.__file__))
        self.command_directory = self.directory / 'public-run'
        self.command_directory.mkdir()
        self.requests = self.alias.ManualMoveRequests(self.command_directory, self.consumer, allow_attack=True)
        request = dict(schema=commands.REQUEST_SCHEMA, sequence=17, command='AttackTarget',
                       uid=self.service.snapshot().uid, target_uid=self.mover.state.uid, map_id=0)
        (self.command_directory / 'command.request.json').write_text(json.dumps(request), encoding='ascii')
        try:
            admitted = await self.requests.poll_async()
        except Exception:
            self.fail(repr(self.consumer.state))
        self.assertEqual(admitted['phase'], 'ADMISSION')
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.requests.poll_async())['phase'], 'ADMISSION')
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.requests.poll_async())['phase'], 'NATIVE_WAIT')
        self.native_result()
        await self.accepted_attack()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.requests.poll_async())['status'], 'COMMITTED')
        self.assertFalse(self.requests.pending)
        self._prior_posts = list(self.posts)
        self.host = SourceQuitRequests(self.owner, self.requests, self.producer, self.command_directory)

    def result(self, **changes):
        row = dict(self.consumer.pending['request'], schema='own-manual-source-quit-result-v1',
                   status='RETURNED', reason=0, invoked=True)
        row.update(changes)
        path = self.directory / ('source-quit-result-' + str(self.consumer.sequence) + '.json')
        path.write_text(json.dumps(row), encoding='ascii')
        return path

    async def quit_request(self, *, send=True):
        # The actual source-empty C2S route and real broker write/drain path.
        policy_row = self.row['policy_row']
        sample = b.OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
            policy_row.peer, self.policy.now, True, True)
        self.policy.received_frame(self.writer, sample, b.QUIT_REQUEST, 10, self.policy.now)
        async with self.row['operation_lock']:
            frames = await self.realm.registry.resolve(self.writer).received(
                SimpleNamespace(opcode=b.QUIT_REQUEST, payload=b''))
            if send:
                await self.producer._send(self.writer, self.row, frames, game=True)
        return frames

    def assert_no_post(self):
        self.assertEqual(self.posts, self._prior_posts)
        self.assertEqual(self.consumer.sequence, 1)

    async def test_actual_alias_attack_sequence_first_drain_late_and_return_is_not_exit(self):
        self.assertEqual(self.consumer.sequence, 1)
        # Constructor is safe before prepare, start is the fresh binding point.
        old_child, old_desktop = self.owner.child, self.owner.private_desktop
        self.owner.child = self.owner.private_desktop = None
        host = SourceQuitRequests(self.owner, self.requests, self.producer, self.command_directory)
        self.owner.child, self.owner.private_desktop = old_child, old_desktop
        self.host = host
        first = self.host.start(3)
        self.assertEqual(first['status'], 'PENDING', first)
        self.assertEqual(self.consumer.sequence, 2)
        self.assertTrue(self.requests.closed)
        raw = (self.directory / 'source-quit-request.json').read_bytes()
        self.assertLessEqual(len(raw), 512)
        self.assertFalse((self.command_directory / 'source-quit-request.json').exists())
        request = json.loads(raw)
        self.assertEqual(list(request), ['schema','pid','birth','candidate_sha256','seq','command','phase'])
        self.assertEqual(request['phase'], 'FirstLandQuit')
        self.result()
        self.assertEqual(self.host.poll()['reason'], 'SOURCE_QUIT_SAME_WRITER_DRAIN_PENDING')
        self.assertEqual(len(self.posts), 2)
        await self.quit_request()
        self.assertTrue(self.realm.quit_report()['source_quit_response_drained'])
        late = self.host.poll()
        self.assertEqual(late['phase'], 'Quit6Approval', late)
        self.assertEqual(self.consumer.sequence, 3)
        self.result()
        done = self.host.poll()
        self.assertEqual(done['status'], 'RETURNED', done)
        self.assertFalse(done['normal_exit_verified'])
        self.assertEqual(done['reason'], 'SOURCE_QUIT_EXIT_UNVERIFIED')
        self.host.start(3); self.host.poll()
        self.assertEqual([post[2] for post in self.posts], [1, 2, 3])
        self.assertTrue(all(tid != threading.get_ident() and desk == 55 for tid, desk in self.post_threads))
        self.assertEqual(len(list(self.directory.glob('manual-move-adapter-claim-*.json'))), 3)
        self.assertEqual(self.consumer.pending['kind'], 'SourceQuit')

    async def test_unresolved_native_pending_refuses_without_new_post(self):
        self.submit_attack()
        result = self.host.start(1)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['reason'], 'SOURCE_QUIT_NATIVE_OUTCOME_UNRESOLVED')
        self.assert_no_post()

    async def test_unknown_consumer_is_not_recovered(self):
        self.consumer.cancel()
        self.assertEqual(self.host.start(1)['status'], 'UNKNOWN')
        self.assert_no_post()

    async def test_missing_partial_result_expires_at_original_deadline_without_repost(self):
        self.assertEqual(self.host.start(1)['status'], 'PENDING')
        path = self.directory / 'source-quit-result-2.json'
        path.write_text('{"schema":', encoding='ascii')
        self.assertEqual(self.host.poll()['status'], 'PENDING')
        path.unlink()
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        self.assertEqual(self.host.poll()['reason'], 'SOURCE_QUIT_ORIGINAL_DEADLINE')
        self.host.start(1); self.host.poll()
        self.assertEqual(len(self.posts), 2)
        self.assertEqual(self.consumer.sequence, 2)

    async def test_wrong_result_identity_and_nonreturn_are_terminal(self):
        self.host.start(1)
        self.result(seq=3)
        result = self.host.poll()
        self.assertEqual(result['reason'], 'SOURCE_QUIT_RESULT_SCHEMA_OR_IDENTITY')
        self.assertEqual(len(self.posts), 2)

    async def test_immutable_first_result_change_blocks_late(self):
        self.host.start(1); path = self.result(); self.host.poll()
        row = json.loads(path.read_bytes()); row['invoked'] = False
        path.write_text(json.dumps(row), encoding='ascii')
        await self.quit_request()
        self.assertEqual(self.host.poll()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 2)
        self.assertEqual(self.consumer.sequence, 2)

    async def test_request_without_real_drain_cannot_publish_late(self):
        self.host.start(1); self.result()
        await self.quit_request(send=False)
        report = self.host.poll()
        self.assertEqual(report['status'], 'PENDING', report)
        self.assertEqual(len(self.posts), 2)
        self.assertFalse(report['late_claimed'])

    async def test_helper_owner_loss_consumes_sequence_without_post_or_retry(self):
        self.desktop_state['on_join'] = lambda: setattr(self.owner, 'closed', True)
        result = self.host.start(1)
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(self.consumer.sequence, 2)
        self.assertEqual(self.posts, self._prior_posts)
        self.assertTrue((self.directory / 'manual-move-adapter-claim-2.json').exists())
        self.host.start(1)
        self.assertEqual(self.consumer.sequence, 2)

    async def test_changed_read_handle_before_late_is_terminal(self):
        self.host.start(1); self.result(); self.host.poll()
        self.reader.backend.handle += 1
        self.assertEqual(self.host.poll()['reason'], 'MANUAL_MOVE_READ_HANDLE_CHANGED')
        self.assertEqual(len(self.posts), 2)

    async def test_last_publish_callback_cancel_never_posts(self):
        original = self.consumer.current
        def current():
            if self.consumer.sequence == 2 and self.posts == self._prior_posts:
                self.consumer.cancel()
            return original()
        self.consumer.current = current
        report = self.host.start(1)
        self.assertEqual(report['status'], 'UNKNOWN', report)
        self.assertEqual(self.posts, self._prior_posts)
        self.assertEqual(self.consumer.sequence, 2)
        self.assertTrue((self.directory / 'manual-move-adapter-claim-2.json').exists())

    async def test_task_cancellation_before_post_is_terminal_and_propagates(self):
        original = self.consumer.current
        def current():
            if self.consumer.sequence == 2 and self.posts == self._prior_posts:
                asyncio.current_task().cancel()
            return original()
        self.consumer.current = current
        async def run():
            self.host.start(1)
        task = asyncio.create_task(run())
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.host.report()['status'], 'UNKNOWN')
        self.assertEqual(self.posts, self._prior_posts)
        self.assertEqual(self.consumer.sequence, 2)

    async def test_reentrant_start_is_terminal_and_never_publishes(self):
        original = self.consumer.current
        called = False
        def current():
            nonlocal called
            if not called:
                called = True
                self.host.start(1)
            return original()
        self.consumer.current = current
        self.assertEqual(self.host.start(1)['status'], 'UNKNOWN')
        self.assert_no_post()

    async def test_visible_stale_other_is_excluded_before_real_glfw_source_quit_proof(self):
        original = self.owner.native.owned_hwnd
        owned_queries = []
        def owned(child, hwnd):
            owned_queries.append(hwnd)
            return original(child, hwnd)
        self.owner.native.owned_hwnd = owned
        self.owner.native.windows = lambda child: [dict(hwnd=500, visible=True, **{'class': 'GLFW30'}),
                                                  dict(hwnd=501, visible=True, **{'class': 'Static'})]
        await self.test_actual_alias_attack_sequence_first_drain_late_and_return_is_not_exit()
        self.assertTrue(owned_queries)
        self.assertEqual(set(owned_queries), {500})

    async def test_window_owned_false_keeps_short_circuit_and_reports_composite_error(self):
        counts = dict(owned=0, rect=0)
        def owned(child, hwnd):
            counts['owned'] += 1
            self.assertEqual(C.get_last_error(), 0)
            C.set_last_error(1400)
            return False
        def rect(*args):
            counts['rect'] += 1
            self.fail('GetClientRect must not follow failed ownership')
        self.owner.native.owned_hwnd = owned
        self.owner.native.u.GetClientRect.callback = rect
        C.set_last_error(999)
        report = self.host.start(3)
        self.assertEqual(report['reason'], 'MANUAL_MOVE_WINDOW_UNKNOWN')
        self.assertEqual(counts, dict(owned=1, rect=0))
        self.assertEqual(report['window_observation'], dict(operation='OWNED_HWND', returned=False,
            winerror=1400, row_index=0, row_count=1, window_class='GLFW30',
            known_bound_match=True, primary_tid_match=None))
        self.assertFalse(report['first_claimed'] or report['native_attempted'])
        self.assertEqual(self.posts, self._prior_posts)
        self.assertEqual(self.consumer.sequence, 1)

    async def test_window_rect_false_is_one_query_and_source_report_preserves_error(self):
        counts = dict(owned=0, rect=0)
        original = self.owner.native.owned_hwnd
        def owned(*args):
            counts['owned'] += 1
            C.set_last_error(1400)  # Ownership succeeded; this must not leak to rect.
            return original(*args)
        def rect(*args):
            counts['rect'] += 1
            self.assertEqual(C.get_last_error(), 0)
            C.set_last_error(5)
            return False
        self.owner.native.owned_hwnd = owned
        self.owner.native.u.GetClientRect.callback = rect
        report = self.host.start(3)
        self.assertEqual(report['reason'], 'MANUAL_MOVE_WINDOW_UNKNOWN')
        self.assertEqual(counts, dict(owned=1, rect=1))
        self.assertEqual(report['window_observation']['operation'], 'GET_CLIENT_RECT')
        self.assertEqual(report['window_observation']['winerror'], 5)
        self.assertIsNone(report['window_observation']['primary_tid_match'])
        self.assertEqual(report['window_observation'], self.consumer.state['window_observation'])
        self.assertFalse(report['first_claimed'] or report['native_attempted'])
        self.assertEqual(self.posts, self._prior_posts)
        self.assertEqual(self.consumer.sequence, 1)

    async def prepare_late_result(self):
        self.assertEqual(self.host.start(3)['status'], 'PENDING')
        self.result()
        self.assertEqual(self.host.poll()['reason'], 'SOURCE_QUIT_SAME_WRITER_DRAIN_PENDING')
        await self.quit_request()
        self.assertEqual(self.host.poll()['phase'], 'Quit6Approval')
        return self.result()

    async def test_collected_terminal_result_survives_exit_and_never_queries_or_reposts(self):
        late_path = await self.prepare_late_result()
        original = commands._closed_health_json
        calls = []
        def forbidden(*args, **kwargs):
            calls.append(True)
            raise AssertionError('completed result must not query live state')
        def read(path):
            row = original(path)
            if path == late_path:
                self.owner.closed = True
                self.consumer.current = forbidden
                self.owner.native.windows = forbidden
            return row
        with patch.object(commands, '_closed_health_json', read):
            done = self.host.poll()
        self.assertEqual(done['status'], 'RETURNED', done)
        self.assertFalse(done['normal_exit_verified'])
        pending, posts = self.consumer.pending, list(self.posts)
        self.reader.closed = True
        self.consumer.cancel()  # Root cleanup cannot erase already collected history.
        self.consumer.clock_ns = forbidden
        self.consumer.sequence = 999  # Report sequence is the collection-time value.
        self.owner.native.u.PostMessageW.callback = forbidden
        for path in self.directory.glob('source-quit-result-*.json'):
            path.unlink()  # Collected immutable history survives cleanup of its files.
        with patch.object(commands, '_closed_health_json', forbidden):
            for operation in (lambda: self.host.start(3), self.host.poll, self.host.report, self.host.close,
                              self.host.poll, self.host.report):
                report = operation()
                self.assertEqual(report, done)
                report.update(status='UNKNOWN', sequence=0, normal_exit_verified=True)
        self.assertEqual(self.host.report(), done)
        self.assertEqual(done['sequence'], 3)
        self.assertEqual(calls, [])
        self.assertEqual(self.posts, posts)
        self.assertIs(self.consumer.pending, pending)
        self.assertEqual(pending['kind'], 'SourceQuit')

    async def test_uncollected_public_or_state_returned_is_not_completion_evidence(self):
        report = self.host.report()
        report.update(status='RETURNED', first_claimed=True, late_claimed=True,
                      first_returned=True, late_returned=True, sequence=999)
        self.assertEqual(self.host.report()['status'], 'NOT_REQUESTED')
        self.host._state.update(status='RETURNED', first_returned=True, late_returned=True)
        self.assertEqual(self.host.report()['status'], 'UNKNOWN')
        self.assertEqual(self.host.start(3)['reason'], 'SOURCE_QUIT_COMPLETION_EVIDENCE_REQUIRED')
        self.assertIsNone(self.host._completion)
        self.assert_no_post()

    async def test_partial_late_and_unknown_cannot_be_promoted_to_terminal_returned(self):
        path = await self.prepare_late_result()
        path.write_text('{"schema":', encoding='ascii')
        self.assertEqual(self.host.poll()['status'], 'PENDING')
        self.assertIsNone(self.host._completion)
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        self.assertEqual(self.host.poll()['status'], 'UNKNOWN')
        self.host._state.update(status='RETURNED')
        self.assertEqual(self.host.poll()['status'], 'UNKNOWN')
        self.assertIsNone(self.host._completion)
        self.assertEqual(len(self.posts), 3)

    async def test_first_immutable_change_before_seal_still_refuses_completion(self):
        await self.prepare_late_result()
        sequence = self.host._requests['FirstLandQuit']['seq']
        path = self.directory / ('source-quit-result-' + str(sequence) + '.json')
        # Same values, changed immutable file identity/size still violate the contract.
        path.write_text(path.read_text(encoding='ascii') + ' ', encoding='ascii')
        report = self.host.poll()
        self.assertEqual(report['reason'], 'SOURCE_QUIT_IMMUTABLE_RESULT_CHANGED')
        self.assertIsNone(self.host._completion)
        self.assertEqual(len(self.posts), 3)

    async def test_final_clock_original_deadline_crossing_cannot_seal(self):
        await self.prepare_late_result()
        def clock():
            return (self.consumer.pending['started'] + m.WAIT_NS
                    if 'Quit6Approval' in self.host._returned else self.now)
        self.consumer.clock_ns = clock
        report = self.host.poll()
        self.assertEqual(report['reason'], 'SOURCE_QUIT_ORIGINAL_DEADLINE')
        self.assertIsNone(self.host._completion)
        self.assertEqual(len(self.posts), 3)

    async def test_final_clock_consumer_cancel_does_not_seal_collected_results(self):
        await self.prepare_late_result()
        def clock():
            if 'Quit6Approval' in self.host._returned:
                self.consumer.cancel()
            return self.now
        self.consumer.clock_ns = clock
        report = self.host.poll()
        self.assertEqual(report['status'], 'UNKNOWN', report)
        self.assertIsNone(self.host._completion)
        self.assertEqual(len(self.posts), 3)

    async def test_final_clock_task_cancel_is_terminal_and_propagates(self):
        await self.prepare_late_result()
        def clock():
            if 'Quit6Approval' in self.host._returned:
                asyncio.current_task().cancel()
            return self.now
        self.consumer.clock_ns = clock
        async def poll():
            self.host.poll()
        task = asyncio.create_task(poll())
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.host.report()['reason'], 'SOURCE_QUIT_CANCELLED')
        self.assertIsNone(self.host._completion)
        self.assertEqual(len(self.posts), 3)

    async def test_native_refusal_is_terminal_not_a_late_admission(self):
        self.host.start(1)
        self.result(status='REFUSED', invoked=False, reason=11)
        self.assertEqual(self.host.poll()['reason'], 'SOURCE_QUIT_NATIVE_NOT_RETURNED')
        self.assertEqual(self.consumer.sequence, 2)
        self.assertEqual(len(self.posts), 2)


if __name__ == '__main__':
    unittest.main()
