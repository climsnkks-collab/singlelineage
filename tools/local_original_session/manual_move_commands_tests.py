"""Real edge/MovementService contracts over existing synthetic memory and IO.

No game, process attachment, native initialization, packet sender or port. The
existing edge fixture supplies typed memory; no boolean edge callback admits
these goals. Reader samples replace process IO only and enter through sample().
"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import (commands_tests, edge_tests, manual_move_commands as m,
                                          movement, move_state, npc_motion_tests)
from tools.local_original_session import attack, attack_session, npc_observe_tests
from tools.local_original_session import desktop_tests
import threading
import struct


class ManualMoveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio
        asyncio.get_running_loop().slow_callback_duration = 10
        await npc_motion_tests.ConnectedMotionTests.asyncSetUp(self)
        self.f = edge_tests.Fixture()
        self.reader = self.f.adapter.reader
        self.reader.backend.handle = 707  # Synthetic duplicated read handle only.
        self.writer.is_closing = lambda: False
        self.directory = Path(self.temp.name) / 'manual'
        self.directory.mkdir()
        member = SimpleNamespace(pid=7, tid=44, process=self.policy.handle, job=self.policy.job,
                                 identity=dict(birth='303'))
        self.posts, self.window = [], 500
        self.post_result = True
        self.post_callback = None

        def rect(hwnd, pointer):
            value = C.cast(pointer, C.POINTER(W.RECT)).contents
            value.left, value.top, value.right, value.bottom = 0, 0, 800, 600
            return True

        def thread(hwnd, pointer):
            C.cast(pointer, C.POINTER(W.DWORD)).contents.value = member.pid
            return member.tid

        def post(*args):
            self.posts.append(args)
            if self.post_callback:
                self.post_callback()
            return self.post_result

        fn = commands_tests.Fn
        self.owner = SimpleNamespace(child=member, owner_handle=member.process, owner_job=member.job,
            directory=self.directory, image_sha='a' * 64, closed=False, validate=lambda child: True,
            native=SimpleNamespace(windows=lambda child: [dict(hwnd=self.window, visible=True, **{'class': 'GLFW30'})],
                owned_hwnd=lambda child, hwnd: hwnd == self.window,
                u=SimpleNamespace(RegisterWindowMessageW=fn(lambda name: 0xc123),
                                  GetClientRect=fn(rect), GetWindowThreadProcessId=fn(thread),
                                  PostMessageW=fn(post))))
        self.reader.owner, self.reader.member, self.reader.closed = self.owner, member, False
        self.policy.owner = self.owner
        self.realm.edge_passability = self.f.adapter
        self.service = self.realm.service(self.writer)
        self.service._edge_passability = self.f.adapter
        async def service_owner(writer, position):
            return await self.producer._movement_owner(writer, self.row, position)
        self.service._owner_guard = service_owner
        self.realm._movement[id(self.writer)] = (self.writer, self.service, 4)
        self.reader.sample = self.sample
        self.sample_mutation = None
        self.sample_error = None
        self.initialize_sampler = False
        self.sample_calls = 0
        self.sample_input_flags = []
        self.scene = 'Land'
        self.client_grid = None
        self.queue_unknown = False
        self.not_idle = False
        self.now = 1_000_000_000
        self.binding = m.ManualMoveBinding(self.writer, self.producer)
        self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
                                           clock_ns=lambda: self.now)
        for index, buckets in enumerate((0x660000, 0x670000)):
            head = 0x600000 + index * 0x10000
            self.f.put(self.f.actor + 0x798 + index * 64, '<fI7Q', 1., 0, head, 0,
                       buckets, buckets + 128, buckets + 128, 7, 8)
            self.f.put(head, '<QQ', head, head)
            for bucket in range(8):
                self.f.put(buckets + bucket * 16, '<QQ', head, head)
        self.memory()

    def memory(self):
        position = self.service.snapshot()
        grid = (position.word0, position.word1)
        self.f.grid = grid
        self.f.put(self.f.player + 24, '<Q', position.uid)
        self.f.put(self.f.map + 0x718, '<ii', position.map_id, position.map_id)
        self.f.put(self.f.context, '<i', position.map_id)
        self.f.put(self.f.transform + self.f.adapter.public['Position']['pair_offset'], '<ii',
                   *((n >> 6) + 0x7e00 for n in grid))
        self.f.put(self.f.transform + self.f.adapter.position_source['coordinates']['transform_grid_offset'],
                   '<ii', *grid)
        self.f.put(0x1a0000 + 32, '<I', (((grid[0] >> 6) + 0x7e00) << 16) | ((grid[1] >> 6) + 0x7e00))
        for direction in range(8):
            for _, (x, y) in self.f.adapter.tile.probe_cells(grid, direction):
                row = 0x400000 + y * 0x1000
                self.f.put(0x300000 + y * 24, '<QQQ', row, row + 128 * 8, row + 128 * 8)
                self.f.put(row + x * 8, '<IHH', 0, 0, 0)

    def sample(self, *, include_input_state=True):
        self.sample_calls += 1
        self.sample_input_flags.append(include_input_state)
        if self.initialize_sampler:
            self.reader.sampler = self.f.s
        if self.sample_error:
            raise self.sample_error
        position = self.service.snapshot()
        grid = list(self.client_grid or (position.word0, position.word1))
        if self.sample_mutation:
            self.sample_mutation()
        return dict(status='OBSERVED', root_ready=True, current=self.scene, pending='none',
            world=dict(status='OBSERVED', stable_double_read=True, my_player_uid=position.uid,
                       map_requested_i32=position.map_id, map_resolved_i32=position.map_id, grid_words=grid),
            move_state=dict(status='OBSERVED', source_contract_valid=True, stable_double_read=True,
                actor_uid=position.uid,
                controller=dict(status='OBSERVED', command_present=self.not_idle),
                navigation=dict(status='OBSERVED', active=self.not_idle),
                transform=dict(status='OBSERVED', current_grid=grid, predicted_grid=grid),
                action=dict(status='OBSERVED', queue_status='UNKNOWN' if self.queue_unknown else 'OBSERVED',
                    queue_count=0, busy_source_eval=dict(status='EVALUATED', value=self.not_idle)))), 10

    def submit(self):
        p = self.service.snapshot()
        return self.consumer.submit_goal(p.uid, p.word0 + 1, p.word1)

    def native_result(self, **changes):
        request = self.consumer.pending['request']
        row = {k: request[k] for k in ('pid', 'birth', 'candidate_sha256', 'seq', 'command')}
        row.update(schema='own-manual-move-result-v1', status='RETURNED', reason=0, invoked=True)
        row.update(changes)
        path = self.directory / ('manual-move-result-' + str(self.consumer.sequence) + '.json')
        path.write_text(json.dumps(row), encoding='ascii')
        return path

    async def move(self, *, rx=True):
        p = self.service.snapshot()
        pb = movement.pb
        payload = pb.encode_message([pb.encode_uint32(1, p.packed), pb.encode_uint32(2, 2)])
        if rx:
            row = self.row['policy_row']
            from tools.local_original_session.broker import OwnerSample
            sample = OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                                 row.peer, self.policy.now, True, True)
            self.policy.received_frame(self.writer, sample, 0x4e2b, len(payload) + 6, self.policy.now)
        game = self.realm.registry.resolve(self.writer)
        await game.received(SimpleNamespace(opcode=0x4e2b, payload=payload))
        self.memory()
        self.now += m.SAMPLE_NS

    async def test_two_explicit_goals_use_real_edge_service_store_and_sequence(self):
        for sequence in (1, 2):
            self.assertEqual(self.submit()['status'], 'PENDING', self.consumer.state)
            request = (self.directory / 'manual-move-request.json').read_bytes()
            self.assertLessEqual(len(request), 512)
            self.assertEqual(json.loads(request)['seq'], sequence)
            self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_PENDING')
            self.assertEqual(len(self.posts), sequence)
            self.native_result()
            self.assertEqual(self.consumer.poll()['status'], 'PENDING')
            await self.move()
            self.assertEqual(self.consumer.poll()['status'], 'COMMITTED', self.consumer.state)
            self.assertEqual(self.realm.positions.restore(self.service.snapshot()), self.service.snapshot())
        self.assertEqual([post[2:] for post in self.posts], [(1, 0), (2, 0)])
        self.assertTrue(self.sample_input_flags)
        self.assertEqual(self.sample_input_flags, [False] * len(self.sample_input_flags))
        self.writer.write.assert_not_called()
        position = self.service.snapshot()
        rejected = self.consumer.submit_goal(position.uid, position.word0 + 2, position.word1)
        self.assertEqual(rejected['status'], 'UNKNOWN')
        self.assertEqual(rejected['phase'], 'ADMISSION')
        self.assertIs(rejected['native_attempted'], False)
        self.assertEqual(len(self.posts), 2)  # Metadata describes this rejected goal.

    async def test_native_return_alone_does_not_free_pending(self):
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.native_result()
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'PENDING')
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_PENDING')
        self.assertEqual(len(self.posts), 1)

    async def test_real_blocked_and_unknown_exact_edge_prevent_post(self):
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                if unknown:
                    self.f.data.pop(self.f.resource)
                else:
                    _, (x, y) = self.f.adapter.tile.probe_cells(self.f.grid, 2)[0]
                    self.f.put(0x400000 + y * 0x1000 + x * 8 + 4, '<H', 1)
                self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding, clock_ns=lambda: self.now)
                self.assertEqual(self.submit()['status'], 'UNKNOWN')
                self.assertEqual(self.posts, [])

    async def test_closed_partial_or_missing_result_expires_without_retry(self):
        self.submit()
        path = self.directory / 'manual-move-result-1.json'
        path.write_text('{"schema":', encoding='ascii')
        self.assertEqual(self.consumer.poll()['status'], 'PENDING')
        path.unlink()
        self.now += m.WAIT_NS
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertTrue(result['cleanup_required'])
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_result_identity_nonreturn_or_immutable_replacement_is_terminal(self):
        self.submit()
        self.native_result(seq=2)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_RESULT_IDENTITY_OR_SCHEMA')
        self.assertEqual(len(self.posts), 1)

    async def test_native_refusal_terminal(self):
        self.submit(); self.native_result(status='REFUSED', invoked=False, reason=6)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_NATIVE_NOT_RETURNED')

    async def test_result_replaced_after_first_observation_is_terminal(self):
        self.submit(); path = self.native_result()
        self.consumer.poll()
        row = json.loads(path.read_text()); path.unlink(); path.write_text(json.dumps(row) + ' ')
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_IMMUTABLE_RESULT_CHANGED')

    async def test_post_failure_claim_blocks_reload_and_replay(self):
        self.post_result = False
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_POST_UNKNOWN')
        self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding, clock_ns=lambda: self.now)
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)
        self.assertTrue((self.directory / 'manual-move-adapter-claim-1.json').exists())

    async def test_scene_loss_or_idle_unknown_is_terminal(self):
        self.submit(); self.scene = 'Login'; self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_KNOWN_SCENE_CONTRADICTION')

    async def test_queue_unknown_before_post_is_terminal(self):
        self.queue_unknown = True
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_IDLE_QUEUE_UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_writer_service_identity_and_window_changes_are_terminal(self):
        self.submit()
        self.realm._movement[id(self.writer)] = (self.writer, self.service, 999)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_CURRENT_SERVICE_REQUIRED')
        self.assertEqual(len(self.posts), 1)

    async def test_post_callback_owner_change_is_terminal(self):
        self.post_callback = lambda: setattr(self.owner, 'image_sha', 'b' * 64)
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_BOUNDARY_OR_LIFETIME_CHANGED')
        self.assertEqual(len(self.posts), 1)

    async def test_unrelated_rx_does_not_replace_real_connection_service_proof(self):
        self.submit(); self.native_result()
        self.policy._emit('rx', 12000, 0x4e2b, 8)
        await self.move(rx=False)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_CS4E2B_UNKNOWN')

    async def reject_after_clear_admission(self, *, send=True, unknown=False):
        # Client admission was genuinely clear. Only synthetic IO changes before
        # the real service's subsequent exact edge read; no verdict is stubbed.
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.native_result()
        self.rejection_initial = self.service.snapshot()
        store = self.service._store.path
        self.rejection_saved = store.read_bytes() if store.exists() else None
        if unknown:
            self.f.data.pop(self.f.resource)
        else:
            _, (x, y) = self.f.adapter.tile.probe_cells(self.f.grid, 2)[0]
            self.blocked_cell = 0x400000 + y * 0x1000 + x * 8 + 4
            self.f.put(self.blocked_cell, '<H', 1)
        payload = movement.pb.encode_message([movement.pb.encode_uint32(1, self.rejection_initial.packed),
                                             movement.pb.encode_uint32(2, 2)])
        from tools.local_original_session.broker import OwnerSample
        row = self.row['policy_row']
        sample = OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                            row.peer, self.policy.now, True, True)
        self.policy.received_frame(self.writer, sample, 0x4e2b, len(payload) + 6, self.policy.now)
        async with self.row['operation_lock']:
            self.rejection_frames = await self.realm.registry.resolve(self.writer).received(
                SimpleNamespace(opcode=0x4e2b, payload=payload))
            if send:
                await self.producer._send(self.writer, self.row, self.rejection_frames, game=True)
        self.assertEqual(self.rejection_frames, (movement.correction_frame(self.rejection_initial),))
        self.assertIs(self.service.snapshot(), self.rejection_initial)
        self.assertEqual((self.service.requests_received, self.service.committed, self.service.corrections_prepared), (1, 0, 1))
        self.now += m.SAMPLE_NS

    def install_backward_producer(self, mode='backward'):
        from tools.local_original_session import observe_tests
        self.back_fixture = observe_tests.MoveStateTests().fixture()
        self.back_mode = mode
        f = self.back_fixture
        self.back_action = f.action + 0x20000
        base = f.reader.sampler.g['base']
        targets = f.probe.action_tables[0x1180c60]['targets']
        f.put(base + 0x1180c60, struct.pack('<8Q', *(base + rva for rva in targets)))
        f.q(self.back_action, base + 0x1180c60)
        f.q(self.back_action + 8, f.action)
        self.reader.sample = self.backward_producer_sample

    def backward_producer_sample(self, *, include_input_state=True):
        row, count = self.sample(include_input_state=include_input_state)
        f, position = self.back_fixture, self.service.snapshot()
        f.q(f.actor + 0x18, position.uid); f.q(0x220000 + 0x6d8, position.uid)
        f.world['my_player_uid'] = position.uid
        f.q(f.controller + 0x58, 0)
        f.q(f.action + 0xc0, 0 if self.back_mode == 'idle' else self.back_action)
        f.q(f.action + 0xb8, 0)
        f.put(f.nav + 0x1ec, b'\0')
        grid = (position.word0, position.word1)
        segment = tuple((n >> 6) + 0x7e00 for n in grid)
        coordinate = struct.pack('<iiii', *segment, *grid) + bytes(24)
        f.put(0x260000 + 0x38, coordinate * 2)
        back_grid = (grid[0] + (self.back_mode == 'wrong_target'), grid[1])
        back_segment = (segment[0] + (self.back_mode == 'wrong_segment'), segment[1])
        f.put(self.back_action + 0x80, struct.pack('<iiii', *back_segment, *back_grid) + bytes(24))
        if self.back_mode == 'wrong_owner': f.q(self.back_action + 8, f.action + 8)
        if self.back_mode == 'wrong_type': f.q(self.back_action, f.reader.sampler.g['base'] + 8)
        motion = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        row['move_state'] = motion
        self.last_backward_motion = motion
        return row, count + motion['typed_bytes_requested']

    async def test_real_rejection_back_snapshot_then_idle_allows_next_explicit_move(self):
        await self.reject_after_clear_admission()
        self.assertEqual(self.service.last_result['reason'], 'EDGE_BLOCKED')
        self.assertFalse(self.service.last_result['accepted'] or self.service.last_result['unknown'])
        self.install_backward_producer()
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_TYPED_BACKWARD_PENDING', result)
        action = self.last_backward_motion['action']
        self.assertEqual(action['current']['kind'], 'MovingBackAction')
        self.assertEqual(action['current']['observation_scope'], 'READONLY_SNAPSHOT')
        self.assertEqual(action['busy_source_eval']['status'], 'UNKNOWN')
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_PENDING')
        self.assertEqual(len(self.posts), 1)
        self.back_mode = 'idle'
        self.assertEqual(self.consumer.poll()['status'], 'PENDING')  # No same-slot completion.
        self.now += m.SAMPLE_NS
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'REJECTED', result)
        self.assertEqual(result['reason'], 'EDGE_BLOCKED')
        self.assertFalse(result['accepted'] or result['automatic_retry'] or result['cleanup_required'])
        self.assertEqual(result['proof_scope'], 'SC4EE0_DRAIN_WITH_CLIENT_SETTLED')
        self.assertTrue(result['moving_back_snapshot_observed'])
        self.assertFalse(result['moving_back_start_observed'])
        store = self.service._store.path
        self.assertEqual(store.read_bytes() if store.exists() else None, self.rejection_saved)
        self.assertIs(self.service.snapshot(), self.rejection_initial)
        self.assertEqual(self.writer.write.call_args.args[0], self.rejection_frames[0])
        self.assertEqual(self.writer.drain.await_count, 1)
        self.f.put(self.blocked_cell, '<H', 0)
        self.assertEqual(self.submit()['status'], 'PENDING')  # A new explicit goal, never replay.
        self.assertEqual(self.consumer.sequence, 2)
        self.native_result(); await self.move()
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED', self.consumer.state)
        self.assertEqual((self.service.requests_received, self.service.committed, self.service.corrections_prepared), (2, 1, 1))
        self.assertEqual([post[2] for post in self.posts], [1, 2])

    async def test_prepared_rejection_without_actual_drain_does_not_consume_snapshot(self):
        await self.reject_after_clear_admission(send=False)
        self.install_backward_producer()
        samples = self.sample_calls
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_CORRECTION_DRAIN_PENDING')
        self.assertEqual(self.sample_calls, samples)
        self.assertIsNone(self.consumer.pending.get('backward_sample_ns'))
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_drained_rejection_without_back_snapshot_cannot_finish(self):
        await self.reject_after_clear_admission()
        self.install_backward_producer('idle')
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_BACKWARD_SNAPSHOT_PENDING')
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def reject_invalid_backward(self, mode):
        await self.reject_after_clear_admission()
        self.install_backward_producer(mode)
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_rejection_wrong_back_target_is_terminal(self):
        await self.reject_invalid_backward('wrong_target')

    async def test_rejection_wrong_back_segment_is_terminal(self):
        await self.reject_invalid_backward('wrong_segment')

    async def test_rejection_wrong_back_owner_is_terminal(self):
        await self.reject_invalid_backward('wrong_owner')

    async def test_rejection_wrong_back_type_is_terminal(self):
        await self.reject_invalid_backward('wrong_type')

    async def test_edge_unknown_is_not_a_known_rejected_move(self):
        await self.reject_after_clear_admission(unknown=True)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_REJECTION_UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_rejection_tx_before_current_rx_does_not_prove_this_response(self):
        await self.reject_after_clear_admission()
        events = list(self.policy.log)
        rx = next(i for i, event in enumerate(events) if event[0] == 'rx' and event[2] == 0x4e2b)
        tx = next(i for i, event in enumerate(events) if event[0] == 'tx' and event[2] == 0x4ee0)
        events[rx], events[tx] = events[tx], events[rx]
        self.policy.log.clear(); self.policy.log.extend(events)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_REJECTION_TRANSPORT_AMBIGUOUS')
        self.assertEqual(len(self.posts), 1)

    async def test_rejection_global_tx_without_same_writer_sent_advance_is_not_proof(self):
        await self.reject_after_clear_admission(send=False)
        self.policy._emit('tx', self.row['peer']['endpoint_port'], 0x4ee0, len(self.rejection_frames[0]))
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_REJECTION_TRANSPORT_AMBIGUOUS')
        self.assertEqual(len(self.posts), 1)

    async def test_rejection_last_resolver_cancel_cannot_release_pending(self):
        await self.reject_after_clear_admission()
        self.install_backward_producer(); self.consumer.poll()
        self.back_mode = 'idle'; self.now += m.SAMPLE_NS
        calls = 0
        def current():
            nonlocal calls
            calls += 1
            if calls == 4: self.consumer.cancel()
            return self.binding
        self.consumer.current = current
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assertIsNotNone(self.consumer.pending)
        self.assertEqual(len(self.posts), 1)

    async def test_additional_or_correction_counter_is_ambiguous(self):
        self.submit()
        self.service.corrections_prepared += 1
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_SEND_OR_COUNTER_AMBIGUOUS')

    async def test_long_goal_or_caller_authority_objects_do_not_admit(self):
        p = self.service.snapshot()
        self.assertEqual(self.consumer.submit_goal(p.uid, p.word0 + 2, p.word1)['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_sample_failure_stamp_and_cancel_close_are_terminal_only(self):
        self.assertIsNone(self.consumer.last_sample_monotonic_ns)
        self.consumer.poll()
        self.assertEqual(self.sample_calls, 0)
        self.sample_error = ValueError('READ_UNKNOWN')
        self.assertEqual(self.submit()['reason'], 'READ_UNKNOWN')
        self.assertEqual(self.consumer.last_sample_monotonic_ns, self.now)
        self.consumer.close()
        self.assertFalse(self.owner.closed)
        self.assertEqual(self.posts, [])

    async def test_clock_mutation_cancellation_and_counter_change_before_post(self):
        def mutation():
            self.consumer.cancel()
        self.sample_mutation = mutation
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_two_tuple_movement_row_is_not_current_position(self):
        self.realm._movement[id(self.writer)] = (self.writer, self.service)
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_CURRENT_SERVICE_REQUIRED')
        self.assertEqual(self.posts, [])

    async def test_writer_replacement_and_closed_lifetime_are_not_rebound(self):
        self.submit()
        self.binding = m.ManualMoveBinding(object(), self.producer)
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_same_writer_service_replacement_is_terminal(self):
        self.submit()
        other = movement.MovementService(self.service.snapshot(), connection=self.writer,
                    owner_guard=self.service._owner_guard, edge_passability=self.f.adapter,
                    store=self.realm.positions)
        self.realm._movement[id(self.writer)] = (self.writer, other, 4)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_BOUNDARY_OR_LIFETIME_CHANGED')

    async def test_owner_birth_window_and_sampler_are_bound(self):
        self.submit()
        self.owner.child.identity['birth'] = '304'
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_BOUNDARY_OR_LIFETIME_CHANGED')

    async def test_sampler_replacement_is_terminal(self):
        self.submit()
        self.reader.sampler = object()
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_SAMPLER_CHANGED')

    async def test_window_replacement_is_terminal(self):
        self.submit(); self.window = 501
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_WINDOW_CHANGED')

    async def test_existing_manual_boundary_is_not_a_fresh_sequence(self):
        (self.directory / 'manual-move-request.json').write_text('{}')
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
        self.assertEqual(self.posts, [])

    async def test_unknown_client_never_commits_and_original_clock_cannot_renew(self):
        self.submit(); self.native_result(); await self.move()
        self.client_grid = (1, 2)
        self.assertEqual(self.consumer.poll()['status'], 'PENDING')
        self.now = 1
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_CLOCK_UNKNOWN')

    async def test_extra_request_never_commits(self):
        self.submit(); self.native_result(); await self.move()
        self.service.requests_received += 1
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_SEND_OR_COUNTER_AMBIGUOUS')

    async def test_post_exception_is_unknown_and_never_reposted(self):
        def fail():
            raise OSError('synthetic post outcome')
        self.post_callback = fail
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_sample_callback_extra_request_before_post_is_rejected(self):
        def mutate():
            self.service.requests_received += 1
        self.sample_mutation = mutate
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_AUTHORITY_CHANGED_DURING_READ')
        self.assertEqual(self.posts, [])

    async def test_reentrant_submission_cannot_reset_outer_terminal(self):
        self.sample_mutation = self.submit
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_first_reader_sampler_initialization_is_allowed(self):
        self.reader.sampler = None
        self.initialize_sampler = True
        self.assertEqual(self.submit()['status'], 'PENDING', self.consumer.state)
        self.assertIs(self.consumer._sampler, self.f.s)

    async def test_backend_replacement_is_terminal_even_with_same_metadata(self):
        self.submit()
        self.reader.backend = SimpleNamespace(**vars(self.reader.backend))
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_BOUNDARY_OR_LIFETIME_CHANGED')

    async def test_last_commit_resolver_cancellation_cannot_revive_terminal(self):
        self.submit(); self.native_result(); await self.move()
        calls = 0
        def current():
            nonlocal calls
            calls += 1
            if calls == 4:  # Last admission after sample and final clock check.
                self.consumer.cancel()
            return self.binding
        self.consumer.current = current
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assertEqual(calls, 4)
        self.assertIsNotNone(self.consumer.pending)
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_durable_request_publication_expiry_never_posts(self):
        atomic = m.commands._atomic
        def publish(*args):
            atomic(*args)
            self.now += m.WAIT_NS
        with patch.object(m.commands, '_atomic', side_effect=publish):
            result = self.submit()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertFalse(result['native_attempted'])
        self.assertEqual(result['phase'], 'NATIVE_WAIT')  # Claim spent; Post never attempted.
        self.assertEqual(self.posts, [])
        self.assertTrue((self.directory / 'manual-move-adapter-claim-1.json').exists())
        self.assertTrue((self.directory / 'manual-move-request.json').exists())
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_same_backend_duplicate_read_handle_replacement_is_terminal(self):
        self.submit()
        backend = self.reader.backend
        backend.handle = 708
        self.assertIs(self.reader.backend, backend)
        self.assertEqual(self.consumer.poll()['reason'], 'MANUAL_MOVE_READ_HANDLE_CHANGED')
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    def sampled_unknown(self, *, world=False, include_input_state=True):
        row, count = self.sample(include_input_state=include_input_state)
        if world:
            # Genuine producer empty_result, then genuine dependent MoveState
            # empty shape when world status was not OBSERVED in the same read.
            from tools.local_original_session import observe
            module = observe.load('tools/local_native_world_read_dormant/inspect_world.py', '_manual_world_empty')
            row['world'] = module.empty_result('WORLD_TYPED_READ_CHANGED')
            row['move_state'] = move_state.empty('MOVE_CURRENT_WORLD_PROOF_REQUIRED')
        else:
            row['move_state'] = move_state.empty('MOVE_TYPED_READ_CHANGED')
        return row, count

    async def test_actual_busy_producer_moving_is_pending_until_fresh_strict_idle(self):
        self.submit(); self.native_result(); await self.move()
        plain_sample = self.reader.sample
        def moving_sample(*, include_input_state=True):
            row, count = plain_sample(include_input_state=include_input_state)
            p = self.service.snapshot()
            action = row['move_state']['action']
            current = dict(status='OBSERVED', reason=None, present=True, kind='MovingAction',
                type_table_rva=0x1180ca8, finished=False, direction_i32=2, token_u32=1, phase_u32=0,
                saved_start_grid=[p.word0 - 1, p.word1], predicted_target_grid=[p.word0, p.word1])
            action['current'] = current
            action['busy_source_eval'] = move_state.busy_source_eval(current, 0, 0,
                dict(status='OBSERVED', present=False, kind='none'))
            self.assertEqual(action['busy_source_eval']['reason'], 'CURRENT_ACTION_PREDICATE_NOT_SUPPORTED')
            return row, count
        self.reader.sample = moving_sample
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['reason'], 'MANUAL_MOVE_TYPED_MOVING_PENDING')
        self.assertEqual(result['observation']['busy_status'], 'UNKNOWN')
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_PENDING')
        self.assertEqual(len(self.posts), 1)
        self.reader.sample = plain_sample
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.reader.sample = moving_sample
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_IDLE_QUEUE_UNKNOWN')
        self.assertEqual(len(self.posts), 1)  # No next goal through moving UNKNOWN.

    async def test_actual_move_empty_read_changed_waits_then_needs_new_known_sample(self):
        self.submit(); self.native_result(); await self.move()
        self.reader.sample = self.sampled_unknown
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['observation']['move_state_reason'], 'MOVE_TYPED_READ_CHANGED')
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_PENDING')
        self.reader.sample = self.sample
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.assertEqual(len(self.posts), 1)

    async def test_actual_world_empty_read_changed_chain_waits_only_until_original_deadline(self):
        self.submit(); self.native_result(); await self.move()
        self.reader.sample = lambda *, include_input_state=True: self.sampled_unknown(
            world=True, include_input_state=include_input_state)
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['observation']['world_reason'], 'WORLD_TYPED_READ_CHANGED')
        self.assertEqual(result['observation']['move_state_reason'], 'MOVE_CURRENT_WORLD_PROOF_REQUIRED')
        self.now += m.WAIT_NS
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(result['observation']['world_reason'], 'WORLD_TYPED_READ_CHANGED')
        self.assertEqual(len(self.posts), 1)

    async def test_known_uid_map_scene_source_contradictions_win_over_transient_shape(self):
        # No command or new boundary needed: invoke the same production sampler
        # admission for each genuine empty shape, checking positive conflicts
        # before the allowlist. It cannot publish or acknowledge a movement.
        current = self.consumer._current()
        mutations = (
            (lambda row: row['world'].update(my_player_uid=999), 'MANUAL_MOVE_KNOWN_UID_CONTRADICTION'),
            (lambda row: row['world'].update(map_requested_i32=99), 'MANUAL_MOVE_KNOWN_MAP_CONTRADICTION'),
            (lambda row: row.update(current='Login'), 'MANUAL_MOVE_KNOWN_SCENE_CONTRADICTION'),
            (lambda row: row['world'].update(source_segment_grid_relation_match=False),
             'MANUAL_MOVE_KNOWN_SOURCE_CONTRADICTION'),
        )
        for mutate, reason in mutations:
            with self.subTest(reason=reason):
                row, count = self.sampled_unknown(world=True)
                mutate(row)
                self.reader.sample = lambda row=row, count=count, *, include_input_state=True: (row, count)
                with self.assertRaisesRegex(ValueError, reason):
                    self.consumer._observe(current, self.now, waiting=True)
        self.assertEqual(self.posts, [])

    async def test_unknown_source_owner_and_type_failures_are_never_pending_exceptions(self):
        current = self.consumer._current()
        for reason in ('MOVE_OBJECT_TYPE_CHANGED', 'MOVE_ACTION_TYPE_TABLE_CHANGED',
                       'MOVE_COMPONENT_BORROWED_ACTOR_MISMATCH', 'MOVE_ROOT_OR_SCENE_CHANGED'):
            with self.subTest(reason=reason):
                row, count = self.sample()
                row['move_state'] = move_state.empty(reason)
                self.reader.sample = lambda row=row, count=count, *, include_input_state=True: (row, count)
                with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_SCENE_ACTOR_UNKNOWN'):
                    self.consumer._observe(current, self.now, waiting=True)
        self.assertEqual(self.posts, [])

    async def test_world_read_changed_cannot_admit_new_submit(self):
        self.reader.sample = lambda *, include_input_state=True: self.sampled_unknown(
            world=True, include_input_state=include_input_state)
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_movement_only_keyword_does_not_turn_budget_failure_into_pending(self):
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.native_result(); await self.move()
        def budget_sample(*, include_input_state=True):
            row, count = self.sample(include_input_state=include_input_state)
            row['move_state'] = move_state.empty('RETAINED_SAMPLE_BYTE_BUDGET')
            return row, count
        self.reader.sample = budget_sample
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['reason'], 'MANUAL_MOVE_SCENE_ACTOR_UNKNOWN')
        self.assertEqual(result['observation']['move_state_reason'], 'RETAINED_SAMPLE_BYTE_BUDGET')
        self.assertEqual(self.sample_input_flags, [False, False])
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    def incoherent_motion_sample(self, *, include_input_state=True):
        # The real producer discards every group when a recorded byte changes
        # during its final double read. Only memory IO is synthetic here.
        from tools.local_original_session import observe_tests
        f = observe_tests.MoveStateTests().fixture()
        original = f.reader.backend.read
        reads = 0
        def read(at, length, image):
            nonlocal reads
            raw = original(at, length, image)
            if at == f.controller + 0x58 and length == 12:
                reads += 1
                if reads == 2:
                    return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        f.reader.backend.read = read
        motion = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        self.assertEqual(reads, 2)
        self.assertEqual(motion['reason'], 'MOVE_TYPED_READ_CHANGED')
        self.assertFalse(motion['source_contract_valid'])
        self.assertTrue(all(motion[group]['status'] == 'UNKNOWN' for group in move_state.GROUPS))
        row, count = self.sample(include_input_state=include_input_state)
        row['move_state'] = motion
        return row, count + motion['typed_bytes_requested']

    async def test_motion_read_changed_admission_waits_for_new_strict_read_and_once_commit(self):
        self.reader.sample = self.incoherent_motion_sample
        result = self.submit()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'ADMISSION'), result)
        self.assertEqual(result['reason'], 'MANUAL_MOVE_TYPED_READ_CHANGED_ADMISSION')
        self.assertEqual(result['observation']['move_state_typed_read_changed_field'], 'CONTROLLER_COMMAND_AND_STATE')
        self.assertFalse(result['native_attempted'])
        self.assertEqual(result['observation']['move_state_reason'], 'MOVE_TYPED_READ_CHANGED')
        self.assert_no_native_claim()
        started, samples = self.consumer.pending['started'], self.sample_calls
        self.assertEqual(self.submit()['reason'], 'MANUAL_MOVE_PENDING')
        self.consumer.poll()
        self.assertEqual(self.sample_calls, samples)  # Same memory slot cannot re-read.
        self.reader.sample = self.sample
        self.now += m.SAMPLE_NS
        result = self.consumer.poll()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'NATIVE_WAIT'), result)
        self.assertNotIn('move_state_typed_read_changed_field', result['observation'])
        self.assertEqual(self.consumer.pending['started'], started)
        self.assertEqual(self.consumer.sequence, 1)
        self.assertEqual(len(self.posts), 1)
        self.native_result()
        await self.move()
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.assertEqual((self.service.requests_received, self.service.committed), (1, 1))
        self.assertEqual(len(self.posts), 1)

    async def test_motion_admission_last_current_cancel_is_terminal_without_native_claim(self):
        self.reader.sample = self.incoherent_motion_sample
        calls = 0
        def current():
            nonlocal calls
            calls += 1
            if calls == 4:  # Last admission resolver after the clock/window callbacks.
                self.consumer.cancel()
            return self.binding
        self.consumer.current = current
        result = self.submit()
        self.assertEqual(calls, 4)
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(result['reason'], 'MANUAL_MOVE_TERMINAL')
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assert_no_native_claim()

    async def test_motion_read_changed_diagnostic_absent_invalid_and_subclass_are_omitted(self):
        current = self.consumer._current()
        class Tag(str):
            pass
        for supplied, value in ((False, None), (True, None), (True, 'UNRECOGNIZED_FIELD'),
                                (True, ['ACTION_TIMER']), (True, Tag('ACTION_TIMER'))):
            with self.subTest(supplied=supplied, value_type=type(value).__name__):
                row, count = self.sampled_unknown()
                if supplied:
                    row['move_state']['typed_read_changed_field'] = value
                self.reader.sample = lambda row=row, count=count, *, include_input_state=True: (row, count)
                self.assertEqual(self.consumer._observe(current, self.now, admitting=True), (False, False))
                self.assertNotIn('move_state_typed_read_changed_field', self.consumer.state['observation'])
        self.assert_no_native_claim()

    async def test_motion_read_changed_admission_expires_with_original_reason_and_no_retry(self):
        self.reader.sample = self.incoherent_motion_sample
        self.assertEqual(self.submit()['status'], 'PENDING')
        started = self.consumer.pending['started']
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'PENDING')
        self.assertEqual(self.consumer.pending['started'], started)
        self.now = started + m.WAIT_NS
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(result['observation']['move_state_reason'], 'MOVE_TYPED_READ_CHANGED')
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assert_no_native_claim()

    async def test_motion_admission_unknown_allowlist_keeps_known_contradictions_and_other_errors_terminal(self):
        current = self.consumer._current()
        for reason in ('WORLD_TYPED_READ_CHANGED', 'MOVE_OBJECT_TYPE_CHANGED',
                       'MOVE_ROOT_OR_SCENE_CHANGED', 'MOVE_FIELDS_PARTIAL', 'RETAINED_SAMPLE_BYTE_BUDGET'):
            with self.subTest(reason=reason):
                row, count = self.sample()
                row['move_state'] = move_state.empty(reason)
                self.reader.sample = lambda row=row, count=count, *, include_input_state=True: (row, count)
                with self.assertRaisesRegex(ValueError, 'MANUAL_MOVE_SCENE_ACTOR_UNKNOWN'):
                    self.consumer._observe(current, self.now, admitting=True)
        for mutate, reason in (
            (lambda r: r['world'].update(my_player_uid=999), 'MANUAL_MOVE_KNOWN_UID_CONTRADICTION'),
            (lambda r: r['world'].update(map_requested_i32=99), 'MANUAL_MOVE_KNOWN_MAP_CONTRADICTION'),
            (lambda r: r.update(current='Login'), 'MANUAL_MOVE_KNOWN_SCENE_CONTRADICTION'),
            (lambda r: r['world'].update(source_segment_grid_relation_match=False),
             'MANUAL_MOVE_KNOWN_SOURCE_CONTRADICTION')):
            row, count = self.sampled_unknown()
            mutate(row)
            self.reader.sample = lambda row=row, count=count, *, include_input_state=True: (row, count)
            with self.assertRaisesRegex(ValueError, reason):
                self.consumer._observe(current, self.now, admitting=True)
        self.assert_no_native_claim()

    def incoherent_edge(self):
        """Change one typed recheck byte in the actual EdgeAdapter memory IO."""
        original = self.reader.backend.read
        reads = 0
        def read(at, size, image=None):
            nonlocal reads
            raw = original(at, size, image)
            if at == self.f.map + 0x718 and size == 4:
                reads += 1
                if reads % 2 == 0:
                    return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.reader.backend.read = read
        return original

    def assert_no_native_claim(self):
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(list(self.directory.glob('manual-move-adapter-claim-*.json')), [])
        self.assertFalse((self.directory / 'manual-move-request.json').exists())
        self.assertEqual(self.posts, [])

    async def test_admission_edge_recheck_then_clear_posts_once_and_real_commit(self):
        original = self.incoherent_edge()
        result = self.submit()
        self.assertEqual(result['status'], 'PENDING', result)
        self.assertEqual(result['phase'], 'ADMISSION')
        self.assertIs(result['native_attempted'], False)
        self.assertEqual(result['observation']['edge_reason'], 'EDGE_TYPED_READ_CHANGED')
        self.assertEqual(result['observation']['edge_phase'], 'TYPED_RECHECK')
        self.assert_no_native_claim()
        started, samples = self.consumer.pending['started'], self.sample_calls
        self.assertEqual(self.consumer.poll()['phase'], 'ADMISSION')
        self.assertEqual(self.sample_calls, samples)  # No extra 0.5s slot.
        self.assertEqual(self.consumer.submit_goal(1, 1, 1)['reason'], 'MANUAL_MOVE_PENDING')
        self.reader.backend.read = original
        self.now += m.SAMPLE_NS
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'PENDING', result)
        self.assertEqual(result['phase'], 'NATIVE_WAIT')
        self.assertIs(result['native_attempted'], True)
        self.assertEqual(self.consumer.pending['started'], started)
        self.assertEqual(len(self.posts), 1)
        self.native_result(); await self.move()
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.assertEqual(self.service.committed, 1)
        self.assertEqual(len(self.posts), 1)

    async def test_admission_persistent_incoherence_expires_without_claim_or_post(self):
        self.incoherent_edge()
        self.assertEqual(self.submit()['phase'], 'ADMISSION')
        started = self.consumer.pending['started']
        for _ in range(2):
            self.now += m.SAMPLE_NS
            self.assertEqual(self.consumer.poll()['phase'], 'ADMISSION')
            self.assertEqual(self.consumer.pending['started'], started)
            self.assert_no_native_claim()
        self.now = started + m.WAIT_NS
        result = self.consumer.poll()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertFalse(result['native_attempted'])
        self.assert_no_native_claim()

    async def test_admission_blocked_edge_is_terminal_with_no_native_attempt(self):
        _, (x, y) = self.f.adapter.tile.probe_cells(self.f.grid, 2)[0]
        self.f.put(0x400000 + y * 0x1000 + x * 8 + 4, '<H', 1)
        result = self.submit()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['observation']['edge_status'], 'BLOCKED_MASK1')
        self.assert_no_native_claim()

    async def test_admission_source_change_is_not_a_transient_edge_exception(self):
        self.f.put(self.f.base + 0x5000, '4s', b'abcd')
        self.f.adapter.checks = [dict(rva=0x5000, length=4, sha256=hashlib.sha256(b'wxyz').hexdigest())]
        result = self.submit()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['observation']['edge_reason'], 'WORLD_RUNTIME_SOURCE_CHANGED')
        self.assert_no_native_claim()

    async def test_admission_same_value_new_authority_object_is_terminal(self):
        self.incoherent_edge(); self.submit()
        self.service._position = replace(self.service.snapshot())
        self.now += m.SAMPLE_NS
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ADMISSION_AUTHORITY_CHANGED')
        self.assert_no_native_claim()

    async def test_admission_selected_writer_change_is_terminal(self):
        self.incoherent_edge(); self.submit()
        self.binding = m.ManualMoveBinding(object(), self.producer)
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assert_no_native_claim()

    async def test_admission_reentrant_read_cannot_publish_or_recover(self):
        self.incoherent_edge(); self.submit()
        self.sample_mutation = self.submit
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assert_no_native_claim()

    async def test_admission_clear_after_original_deadline_does_not_allocate_native_sequence(self):
        self.incoherent_edge(); self.submit()
        self.reader.backend.read = self.f.read
        self.now += m.SAMPLE_NS
        def expire():
            self.now = self.consumer.pending['started'] + m.WAIT_NS
        self.sample_mutation = expire
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assert_no_native_claim()

    async def test_window_candidate_unknown_ambiguous_stale_and_bound_changes_refuse(self):
        class ClassName(str):
            pass
        modes = ('stale', 'rect', 'pid', 'tid', 'multi', 'hidden_multi', 'small_multi', 'hidden',
                 'missing_class', 'empty_class', 'nonstring_class', 'class_subclass', 'class_error',
                 'helper_class_unknown', 'bound_class', 'hidden_bound_class', 'bound_missing', 'bound_replaced')
        original_owned = self.owner.native.owned_hwnd
        original_rect = self.owner.native.u.GetClientRect
        original_thread = self.owner.native.u.GetWindowThreadProcessId
        for mode in modes:
            with self.subTest(mode=mode):
                self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding, clock_ns=lambda: self.now)
                rows = [dict(hwnd=500, visible=True, **{'class': 'GLFW30'})]
                self.owner.native.windows = lambda child: rows
                self.owner.native.owned_hwnd = original_owned
                self.owner.native.u.GetClientRect = original_rect
                self.owner.native.u.GetWindowThreadProcessId = original_thread
                if mode.startswith('bound') or mode == 'hidden_bound_class':
                    self.assertEqual(self.consumer._window(self.consumer._current()), 500)
                if mode == 'stale':
                    self.owner.native.owned_hwnd = lambda *args: False
                elif mode == 'rect':
                    self.owner.native.u.GetClientRect = commands_tests.Fn(lambda *args: False)
                elif mode in ('pid', 'tid'):
                    def thread(hwnd, pointer):
                        C.cast(pointer, C.POINTER(W.DWORD)).contents.value = self.owner.child.pid + (mode == 'pid')
                        return self.owner.child.tid + (mode == 'tid')
                    self.owner.native.u.GetWindowThreadProcessId = commands_tests.Fn(thread)
                elif mode in ('multi', 'hidden_multi', 'small_multi'):
                    rows.append(dict(hwnd=501, visible=mode != 'hidden_multi', **{'class': 'GLFW30'}))
                    self.owner.native.owned_hwnd = lambda child, hwnd: hwnd in (500, 501)
                elif mode == 'hidden': rows[0]['visible'] = False
                elif mode == 'missing_class': rows[0].pop('class')
                elif mode == 'empty_class': rows[0]['class'] = ''
                elif mode == 'nonstring_class': rows[0]['class'] = 1
                elif mode == 'class_subclass': rows[0]['class'] = ClassName('GLFW30')
                elif mode == 'class_error': rows[0]['public_metadata_errors'] = [dict(operation='class', winerror=5)]
                elif mode == 'helper_class_unknown': rows.append(dict(hwnd=501, visible=False, **{'class': ''}))
                elif mode in ('bound_class', 'hidden_bound_class'):
                    rows[0].update(visible=mode != 'hidden_bound_class', **{'class': 'Static'})
                    rows.append(dict(hwnd=501, visible=True, **{'class': 'GLFW30'}))
                elif mode in ('bound_missing', 'bound_replaced'):
                    rows.clear()
                    if mode == 'bound_replaced':
                        rows.append(dict(hwnd=501, visible=True, **{'class': 'GLFW30'}))
                        self.owner.native.owned_hwnd = lambda child, hwnd: hwnd == 501
                if mode == 'small_multi':
                    def rect(hwnd, pointer):
                        value = C.cast(pointer, C.POINTER(W.RECT)).contents
                        value.left = value.top = 0
                        value.right, value.bottom = ((10, 10) if hwnd == 501 else (800, 600))
                        return True
                    self.owner.native.u.GetClientRect = commands_tests.Fn(rect)
                result = self.submit()
                self.assertEqual(result['status'], 'UNKNOWN', (mode, result))
                self.assertEqual(self.posts, [])
                self.assertEqual(self.consumer.sequence, 0)
                self.assertFalse(list(self.directory.glob('manual-move-adapter-claim-*')))
                if mode in ('missing_class', 'empty_class', 'nonstring_class', 'class_subclass', 'class_error', 'helper_class_unknown'):
                    self.assertEqual(result['reason'], 'MANUAL_MOVE_WINDOW_CLASS_UNKNOWN')
                elif mode in ('bound_class', 'hidden_bound_class'):
                    self.assertEqual(result['reason'], 'MANUAL_MOVE_BOUND_WINDOW_CLASS_CHANGED')
                elif mode == 'bound_replaced':
                    self.assertEqual(result['reason'], 'MANUAL_MOVE_WINDOW_CHANGED')

    def private_desktop_fixture(self):
        fake, state = desktop_tests.DesktopTests.fake_native(self)
        native = self.owner.native
        for name, value in vars(fake.u).items():
            setattr(native.u, name, value)
        native.k = SimpleNamespace(**vars(fake.k))
        native.u.IsWindow = commands_tests.Fn(lambda hwnd: hwnd == 500)
        original_post = native.u.PostMessageW
        post_threads, validations = [], []
        def post(*args):
            tid = threading.get_ident()
            post_threads.append((tid, state['threads'].get(tid, 11)))
            return original_post(*args)
        native.u.PostMessageW = commands_tests.Fn(post)
        original_validate = self.owner.validate
        def validate(child):
            validations.append(threading.get_ident())
            return original_validate(child)
        self.owner.validate = validate
        private = desktop_tests.l.PrivateDesktop(native)  # Actual launcher-loaded product class.
        self.owner.private_desktop = private
        self.addCleanup(private.close)
        return private, state, post_threads, validations

    async def test_private_desktop_posts_on_actual_joined_helper_not_parent(self):
        private, state, threads, validations = self.private_desktop_fixture()
        parent = threading.get_ident()
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(len(threads), 1)
        tid, hdesk = threads[0]
        self.assertNotEqual(tid, parent)
        self.assertEqual(hdesk, 55)
        self.assertIn(tid, validations)  # owner.validate really executes in helper thread.
        self.assertEqual(state['threads'][tid], 11)
        self.assertEqual(private._users, 0)

    async def test_private_desktop_owner_loss_in_helper_never_posts(self):
        private, state, threads, _validations = self.private_desktop_fixture()
        state['on_join'] = lambda: setattr(self.owner, 'closed', True)
        result = self.submit()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['reason'], 'COMMAND_OWNER_CHANGED')
        self.assertEqual(self.posts, [])
        self.assertEqual(threads, [])
        self.assertEqual(private._users, 0)
        self.assertEqual(self.consumer.sequence, 1)  # Consumed claim cannot be replayed.
        self.assertEqual(self.submit()['status'], 'UNKNOWN')


    def breath_admission_sample(self, *, include_input_state=True):
        from tools.local_original_session import observe_tests
        fixture = observe_tests.MoveStateTests()
        f = fixture.fixture()
        p = self.service.snapshot()
        f.q(f.actor + 24, p.uid); f.q(0x220000 + 0x6d8, p.uid)
        f.world['my_player_uid'] = p.uid
        coordinate = struct.pack('<iiii', (p.word0 >> 6) + 0x7e00, (p.word1 >> 6) + 0x7e00,
                                 p.word0, p.word1) + bytes(24)
        f.q(f.controller + 0x58, 0)
        if getattr(self, 'breath_command', False):
            f.q(f.controller + 0x58, f.command)
            f.q(f.command + 0x10, p.uid)
            f.put(f.command + 0x18, coordinate)
        f.put(0x260000 + 0x38, coordinate * 2)
        f.put(f.nav + 0x1c0, coordinate + struct.pack('<iBB2xiii', 0, self.breath_active, 0, 0, 0, 0))
        fixture.set_source_action(f, 0x480000, 'BreathAction')
        f.q(f.action + 0xc0, 0x480000)
        f.put(f.action + 0xa0, bytes(32))
        if getattr(self, 'breath_queue', False):
            f.put(f.action + 0xa0, struct.pack('<4Q', 0x430000, 8, 0, 1))
            f.q(0x440000, 0x480000)
        motion = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        self.assertEqual(motion['status'], 'OBSERVED', motion)
        self.assertEqual(motion['action']['busy_source_eval']['reason'], 'SOURCE_CURRENT_BREATH')
        row, count = self.sample(include_input_state=include_input_state)
        row['world']['source_segment_grid_relation_match'] = True
        row['move_state'] = motion
        if self.breath_mutation is not None:
            self.breath_mutation(row)
        return row, count + motion['typed_bytes_requested']

    async def test_return_admission_source_breath_nonidle_waits_then_fresh_once_commit(self):
        origin = self.service.snapshot()
        self.submit(); self.native_result(); await self.move()
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.breath_active, self.breath_mutation = True, None
        self.reader.sample = self.breath_admission_sample
        result = self.consumer.submit_goal(origin.uid, origin.word0, origin.word1)
        print('return_breath_admission status=' + result['status'] + ' reason=' + str(result['reason'])
              + ' posts=' + str(len(self.posts)) + ' sequence=' + str(self.consumer.sequence))
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'ADMISSION'), result)
        self.assertIs(result['native_attempted'], False)
        self.assertEqual(len(self.posts), 1)
        started, samples = self.consumer.pending['started'], self.sample_calls
        self.consumer.poll()
        self.assertEqual(self.sample_calls, samples)
        self.breath_active = False
        self.now += m.SAMPLE_NS
        result = self.consumer.poll()
        self.assertEqual(result['phase'], 'NATIVE_WAIT', result)
        self.assertEqual(self.consumer.pending['started'], started)
        self.assertEqual(len(self.posts), 2)
        self.native_result()
        p = self.service.snapshot()
        wire = movement.pb.encode_message([movement.pb.encode_uint32(1, p.packed),
            movement.pb.encode_uint32(2, self.consumer.pending['direction'])])
        from tools.local_original_session.broker import OwnerSample
        row = self.row['policy_row']
        sampled = OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                             row.peer, self.policy.now, True, True)
        self.policy.received_frame(self.writer, sampled, 0x4e2b, len(wire) + 6, self.policy.now)
        await self.realm.registry.resolve(self.writer).received(SimpleNamespace(opcode=0x4e2b, payload=wire))
        self.memory(); self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'COMMITTED')
        self.assertEqual((self.service.requests_received, self.service.committed, self.service.corrections_prepared), (2, 2, 0))
        self.assertEqual(self.service.snapshot(), origin)

    async def test_source_breath_known_command_or_queue_waits_without_idle_promotion(self):
        for index, mode in enumerate(('command', 'queue')):
            with self.subTest(mode=mode):
                if index:
                    await self.asyncSetUp()
                self.breath_active, self.breath_mutation = False, None
                self.breath_command, self.breath_queue = mode == 'command', mode == 'queue'
                self.reader.sample = self.breath_admission_sample
                result = self.submit()
                self.assertEqual(result['reason'], 'MANUAL_MOVE_SETTLING_ADMISSION_PENDING', result)
                self.assertIs(result['native_attempted'], False)
                self.assertEqual(self.posts, [])
                self.breath_command = self.breath_queue = False
                self.now += m.SAMPLE_NS
                self.assertEqual(self.consumer.poll()['phase'], 'NATIVE_WAIT')
                self.assertEqual(len(self.posts), 1)

    async def test_source_breath_wait_original_deadline_is_terminal_without_native_claim(self):
        self.breath_active, self.breath_mutation = True, None
        self.reader.sample = self.breath_admission_sample
        result = self.submit()
        self.assertEqual(result['status'], 'PENDING')
        started = self.consumer.pending['started']
        self.now = started + m.WAIT_NS - 1
        self.assertEqual(self.consumer.poll()['status'], 'PENDING')
        self.assertEqual(self.consumer.pending['started'], started)
        self.now += 1
        result = self.consumer.poll()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(self.posts, [])
        self.assertEqual(self.consumer.sequence, 0)
        self.assertFalse(list(self.directory.glob('manual-move-adapter-claim-*')))

    async def test_source_breath_grid_uid_map_source_busy_type_unknown_stay_terminal(self):
        cases = (lambda row: row['move_state']['transform'].update(predicted_grid=[1, 2]),
                 lambda row: row['world'].update(my_player_uid=99),
                 lambda row: row['world'].update(map_resolved_i32=99),
                 lambda row: row['world'].update(source_segment_grid_relation_match=False),
                 lambda row: row['move_state']['action']['busy_source_eval'].update(value=True),
                 lambda row: row['move_state']['action']['current'].update(type_table_rva=0x1180938),
                 lambda row: row['move_state']['navigation'].update(status='UNKNOWN'))
        for index, mutate in enumerate(cases):
            with self.subTest(case=index):
                if index:
                    await self.asyncSetUp()
                self.breath_active, self.breath_mutation = True, mutate
                self.reader.sample = self.breath_admission_sample
                result = self.submit()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertEqual(self.posts, [])
                self.assertEqual(self.consumer.sequence, 0)

    async def test_source_breath_wait_cancel_and_owner_loss_cannot_publish(self):
        self.breath_active, self.breath_mutation = True, None
        self.reader.sample = self.breath_admission_sample
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.consumer.cancel()
        self.now += m.SAMPLE_NS
        self.assertEqual(self.consumer.poll()['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])
        await self.asyncSetUp()
        self.breath_active = True
        self.breath_mutation = lambda row: setattr(self.owner, 'validate', lambda _: False)
        self.reader.sample = self.breath_admission_sample
        result = self.submit()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    async def test_source_breath_same_slot_six_scalar_diagnostic_fits_existing_2048_sink(self):
        self.breath_active, self.breath_mutation = True, None
        self.reader.sample = self.breath_admission_sample
        result = self.submit()
        expected = dict(grid_matches=True, command_ready=True, command_present=False,
                        navigation_active=True, queue_count=0, busy_value=False)
        self.assertEqual({key: result['observation'][key] for key in expected}, expected)
        from tools.local_original_session.launcher import ManualMoveRequests
        sink = ManualMoveRequests.__new__(ManualMoveRequests)
        sink.directory, sink.sequence, sink._inventory_auto_selection = self.directory, (1 << 31) - 1, None
        sink._record(self.consumer._terminal('X' * 110))
        size = (self.directory / 'command.result.json').stat().st_size
        self.assertLessEqual(size, 2048)
        print('move_admission_diagnostic_public_bytes=' + str(size))


class ManualAttackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncio
        asyncio.get_running_loop().slow_callback_duration = 10
        await npc_observe_tests.NpcObservationTests.asyncSetUp(self)
        self.directory = Path(self.temp.name) / 'combined'
        self.directory.mkdir()
        self.owner = self.reader.owner
        self.owner.directory, self.owner.image_sha = self.directory, 'a' * 64
        self.owner.child = self.reader.member
        self.owner.child.tid = 44
        self.posts, self.window = [], 500
        self.post_failure = False
        def rect(hwnd, pointer):
            row = C.cast(pointer, C.POINTER(W.RECT)).contents
            row.left, row.top, row.right, row.bottom = 0, 0, 800, 600
            return True
        def thread(hwnd, pointer):
            C.cast(pointer, C.POINTER(W.DWORD)).contents.value = self.owner.child.pid
            return self.owner.child.tid
        def post(*args):
            self.posts.append(args)
            return not self.post_failure
        fn = commands_tests.Fn
        self.owner.native.windows = lambda child: [dict(hwnd=500, visible=True, **{'class': 'GLFW30'})]
        self.owner.native.owned_hwnd = lambda child, hwnd: hwnd == 500
        self.owner.native.u = SimpleNamespace(GetClientRect=fn(rect), GetWindowThreadProcessId=fn(thread),
            RegisterWindowMessageW=fn(lambda name: 0xc124 if name == m.ATTACK_MESSAGE else 0xc123),
            PostMessageW=fn(post))
        self.writer.is_closing = lambda: False
        self.service = self.realm.service(self.writer)
        self.realm._movement[id(self.writer)] = (self.writer, self.service, 4)
        self.realm.edge_passability = self.service._edge_passability = self.observer.proof
        self.session = attack_session.AttackSession(self.targets,
            policy=attack_session.EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT)
        self.producer._attack_session = self.realm._attack_session = self.session
        self.policy.attack_intent = True
        # Register the real route with the real realm after opt-in; do not stub
        # AttackSession.handle or inject a fake CS4E30 route into the game.
        self.realm.close(self.writer)
        from tools.local_original_session import broker as b
        self.realm = b.LocalRealm(self.realm.expected_uuid, self.directory / 'characters-attack.json',
            edge_passability=self.observer.proof, npc_spawns=tuple(row[0] for row in self.realm._npc_spawns),
            npc_motion_interval_ns=100, npc_edge_passability=lambda *args: True,
            npc_motion_policy=b.npc_motion.LOCAL_PRE_STEP)
        self.realm.store.create(b.ack.realm.Creation(self.realm.profile_name, 0, 0, (13,) * 6))
        self.producer.realm = self.realm
        self.realm.bind_attack_session(self.session)
        async def owner(writer, position):
            return await self.producer._movement_owner(writer, self.row, position)
        game = self.realm.grant(self.writer, movement_owner_guard=owner, connection_id=4)
        await game.received(SimpleNamespace(opcode=0x263, payload=npc_motion_tests.LocalLoginRequest(
            0, 'standalone.local', self.realm.expected_uuid).payload()))
        pb = movement.pb
        frames = await game.received(SimpleNamespace(opcode=0x4e28, payload=pb.encode_message([
            pb.encode_bytes(1, self.realm.profile_name.encode()), pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await self.producer._send(self.writer, self.row, frames, game=True)
        self.service, self.mover = self.realm.service(self.writer), self.realm.npc_mover(self.writer)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.binding = m.ManualMoveBinding(self.writer, self.producer)
        self.now = 1_000_000_000
        self.sample_calls, self.sample_input_flags = 0, []
        self.initialize_sampler, self.sample_mutation, self.sample_error = False, None, None
        self.scene, self.client_grid, self.queue_unknown, self.not_idle = 'Land', None, False, False
        self.reader.sample = lambda *, include_input_state=True: ManualMoveTests.sample(
            self, include_input_state=include_input_state)
        self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
            clock_ns=lambda: self.now, allow_attack=True)
        self.tiles()

    def tiles(self):
        grid = (self.service.snapshot().word0, self.service.snapshot().word1)
        mem, proof = self.memory, self.observer.proof
        resource, rows, context, header, node = 0x700000, 0x710000, 0x330000, 0x720000, 0x730000
        mem.put(context + 8, '<QQ', header, 1)
        mem.put(header, '<QQQBB', node, node, node, 1, 1)
        segment = tuple((n >> 6) + 0x7e00 for n in grid)
        mem.put(node, '<QQQBB6xI4xQQ', header, header, header, 1, 0,
                (segment[0] << 16) | segment[1], resource, 0x250000)
        mem.put(resource, '<QQQ', rows, rows + 64 * 24, rows + 64 * 24)
        mem.put(resource + 24, '<QQ', 0x740000, 0)
        mem.put(0x740000, '<QQQBB', 0x740000, 0x740000, 0x740000, 1, 1)
        for direction in range(8):
            for _, (x, y) in proof.tile.probe_cells(grid, direction):
                cells = 0x800000 + y * 0x1000
                mem.put(rows + y * 24, '<QQQ', cells, cells + 128 * 8, cells + 128 * 8)
                mem.put(cells + x * 8, '<IHH', 0, 0, 0)
        for index in range(2):
            head, buckets = 0x900000 + index * 0x10000, 0xa00000 + index * 0x10000
            mem.put(mem.actors + 0x798 + index * 64, '<fI7Q', 1., 0, head, 0,
                    buckets, buckets + 128, buckets + 128, 7, 8)
            mem.put(head, '<QQ', head, head)
            for bucket in range(8):
                mem.put(buckets + bucket * 16, '<QQ', head, head)

    def submit_attack(self):
        return self.consumer.submit_attack(self.service.snapshot().uid, self.mover.state.uid, 0)

    async def admit_attack(self):
        self.assertEqual(self.submit_attack()['phase'], 'ADMISSION')
        self.assertEqual(self.posts, [])
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'PENDING', result)
        self.assertEqual(result['phase'], 'ADMISSION')
        self.assertEqual(self.sample_calls, 0)  # The first slot is actual NPC observation.
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['phase'], 'NATIVE_WAIT', result)
        self.assertEqual(result['status'], 'PENDING', result)

    def native_result(self, **changes):
        request = self.consumer.pending['request']
        attack_kind = request['command'] == 'AttackTarget'
        if attack_kind:
            row = dict(request, schema='own-attack-target-result-v1')
        else:
            row = {key: request[key] for key in ('pid', 'birth', 'candidate_sha256', 'seq', 'command')}
            row['schema'] = 'own-manual-move-result-v1'
        row.update(status='RETURNED', reason=0, invoked=True)
        row.update(changes)
        path = self.directory / (('attack-target-result-' if attack_kind else 'manual-move-result-')
                                  + str(self.consumer.sequence) + '.json')
        path.write_text(json.dumps(row), encoding='ascii')

    async def received(self, opcode, payload):
        from tools.local_original_session.broker import OwnerSample
        policy_row = self.row['policy_row']
        sample = OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                            policy_row.peer, self.policy.now, True, True)
        self.policy.received_frame(self.writer, sample, opcode, len(payload) + 6, self.policy.now)
        async with self.row['operation_lock']:
            replies = await self.realm.registry.resolve(self.writer).received(
                SimpleNamespace(opcode=opcode, payload=payload))
        self.assertEqual(replies, ())

    async def accepted_attack(self):
        x, y = movement.authority.unpack_grid(self.mover.state.packed)
        payload = attack._field(1, self.mover.state.uid) + attack._field(2, x) + attack._field(3, y)
        await self.received(0x4e30, payload)

    async def test_actual_observer_session_intent_and_native_return_are_distinct(self):
        await self.admit_attack()
        self.native_result()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        await self.accepted_attack()
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'COMMITTED', result)
        self.assertEqual(result['command'], 'AttackTarget')
        self.assertEqual(result['proof_scope'], 'VALIDATED_ATTACK_INTENT_ONLY')
        self.assertEqual(result['combat_effect'], 'UNKNOWN')
        self.assertEqual(self.session.accepted_count, 1)
        self.assertEqual(len(self.posts), 1)
        self.writer.write.assert_not_called()

    async def test_move_attack_move_share_actual_native_sequence_and_pending(self):
        p = self.service.snapshot()
        self.assertEqual(self.consumer.submit_goal(p.uid, p.word0 + 1, p.word1)['phase'], 'NATIVE_WAIT')
        self.assertEqual(self.submit_attack()['reason'], 'MANUAL_MOVE_PENDING')
        self.native_result()
        await self.received(0x4e2b, attack._field(1, p.packed) + attack._field(2, 2))
        self.memory.grid(0x470000, [p.word0 + 1, p.word1])
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'COMMITTED')
        self.assertEqual(self.submit_attack()['phase'], 'ADMISSION')
        self.assertEqual(self.consumer.submit_goal(p.uid, p.word0, p.word1)['reason'], 'MANUAL_MOVE_PENDING')
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['phase'], 'ADMISSION')
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['phase'], 'NATIVE_WAIT')
        self.native_result(); await self.accepted_attack()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'COMMITTED')
        position = self.service.snapshot()
        self.assertEqual(self.consumer.submit_goal(p.uid, p.word0, p.word1)['phase'], 'NATIVE_WAIT')
        self.native_result()
        await self.received(0x4e2b, attack._field(1, position.packed) + attack._field(2, 6))
        self.memory.grid(0x470000, [p.word0, p.word1])
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'COMMITTED')
        self.assertEqual([post[2] for post in self.posts], [1, 2, 3])
        self.assertEqual([post[1] for post in self.posts], [0xc123, 0xc124, 0xc123])

    async def test_attack_default_off_and_nonbool_cannot_authorize(self):
        self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding, clock_ns=lambda: self.now)
        self.assertEqual(self.submit_attack()['reason'], 'MANUAL_ATTACK_DISABLED')
        with self.assertRaisesRegex(ValueError, 'MANUAL_ATTACK_EXPLICIT_BOOL_REQUIRED'):
            m.ManualMoveCommands(self.reader, current=lambda: self.binding, allow_attack=1)
        self.assertEqual(self.posts, [])

    async def test_actual_npc_observer_unknown_is_terminal_before_claim(self):
        self.memory.put(self.memory.npc + 24, '<Q', 999)
        self.submit_attack()
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['observation']['npc_status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])
        self.assertEqual(self.consumer.sequence, 0)

    async def test_npc_proof_age_and_started_are_not_renewed(self):
        self.submit_attack()
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        started = self.consumer.pending['started']
        self.now += 1_000_000_001
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_ATTACK_NPC_PROOF_STALE')
        self.assertEqual(self.consumer.pending['started'], started)
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(self.posts, [])

    async def test_target_authority_change_between_two_slots_is_terminal(self):
        self.submit_attack(); await self.consumer.poll_async()
        self.mover.state = replace(self.mover.state)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_ATTACK_TARGET_AUTHORITY_CHANGED')
        self.assertEqual(self.posts, [])

    async def test_awaited_observer_callback_reentry_cannot_publish(self):
        original = self.producer._sample
        async def reentry(row):
            result = await original(row)
            self.consumer.submit_goal(self.service.snapshot().uid, 1, 1)
            return result
        self.producer._sample = reentry
        self.submit_attack()
        self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])
        self.assertEqual(self.consumer.sequence, 0)

    async def test_cancelled_await_keeps_terminal_without_background_task(self):
        import asyncio
        entered = asyncio.Event()
        original = self.producer._sample
        async def pause(row):
            entered.set()
            await asyncio.Event().wait()
            return await original(row)
        self.producer._sample = pause
        self.submit_attack()
        task = asyncio.create_task(self.consumer.poll_async())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_ATTACK_CANCELLED')
        self.assertFalse(self.consumer._busy)
        self.assertEqual(self.posts, [])

    async def test_attack_post_failure_is_one_attempt_and_never_replayed(self):
        self.submit_attack(); await self.consumer.poll_async()
        self.post_failure = True
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertTrue(result['native_attempted'])
        self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_attack_result_target_mismatch_and_missing_result_fail_closed(self):
        await self.admit_attack()
        self.native_result(target_uid=999)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_ATTACK_RESULT_IDENTITY_OR_SCHEMA')
        self.assertEqual(len(self.posts), 1)

    async def test_attack_missing_result_deadline_never_posts_next_sequence(self):
        await self.admit_attack()
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(self.submit_attack()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_two_real_attack_frames_are_ambiguous_for_one_native_command(self):
        await self.admit_attack(); self.native_result()
        await self.accepted_attack(); await self.accepted_attack()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_ATTACK_INTENT_COUNTER_AMBIGUOUS')
        self.assertEqual(self.session.accepted_count, 2)

    async def test_existing_attack_files_refuse_fresh_boundary_before_post(self):
        (self.directory / 'attack-target-request.json').write_text('{}')
        self.submit_attack(); await self.consumer.poll_async()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(self.posts, [])

    async def test_npc_sample_completion_sets_conservative_spacing(self):
        original = self.producer._sample
        async def delayed(row):
            result = await original(row)
            self.now += 100_000_000
            return result
        self.producer._sample = delayed
        self.submit_attack()
        await self.consumer.poll_async()
        self.assertEqual(self.consumer.last_sample_monotonic_ns, self.now)
        completed = self.now
        await self.consumer.poll_async()
        self.assertEqual(self.sample_calls, 0)
        self.now = completed + m.SAMPLE_NS
        self.producer._sample = original
        self.assertEqual((await self.consumer.poll_async())['phase'], 'NATIVE_WAIT')
        self.assertEqual(len(self.posts), 1)

    async def test_strict_player_read_cost_expires_npc_proof_before_native_claim(self):
        self.submit_attack(); await self.consumer.poll_async()
        self.now += m.SAMPLE_NS
        def consume_time():
            self.now += 500_000_001
        self.sample_mutation = consume_time
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_ATTACK_NPC_PROOF_STALE')
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(self.posts, [])

    async def test_awaited_read_clock_deadline_is_original_and_post_zero(self):
        original = self.producer._sample
        async def late(row):
            result = await original(row)
            self.now += m.WAIT_NS
            return result
        self.producer._sample = late
        self.submit_attack()
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(self.posts, [])

    async def test_sync_player_callback_task_cancel_spends_claim_without_post(self):
        import asyncio
        self.submit_attack(); await self.consumer.poll_async()
        self.now += m.SAMPLE_NS
        self.sample_mutation = lambda: asyncio.current_task().cancel()
        task = asyncio.create_task(self.consumer.poll_async())
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_ATTACK_CANCELLED')
        self.assertEqual(self.consumer.state['status'], 'UNKNOWN')
        self.assertFalse(self.consumer.state['native_attempted'])
        self.assertTrue((self.directory / 'manual-move-adapter-claim-1.json').exists())
        self.assertEqual(self.consumer.sequence, 1)
        self.assertEqual(self.posts, [])
        self.assertEqual(self.submit_attack()['status'], 'UNKNOWN')

    async def test_last_intent_resolver_task_cancel_never_revives_committed(self):
        import asyncio
        await self.admit_attack(); self.native_result(); await self.accepted_attack()
        self.now += m.SAMPLE_NS
        calls = 0
        def current():
            nonlocal calls
            calls += 1
            if calls == 8:  # Final _attack_current after current_intent revalidation.
                asyncio.current_task().cancel()
            return self.binding
        self.consumer.current = current
        task = asyncio.create_task(self.consumer.poll_async())
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(calls, 8)
        self.assertEqual(self.consumer.state['status'], 'UNKNOWN')
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_ATTACK_CANCELLED')
        self.assertIsNotNone(self.consumer.pending)
        self.assertEqual(self.submit_attack()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_post_callback_task_cancel_is_terminal_after_single_native_attempt(self):
        import asyncio
        self.submit_attack(); await self.consumer.poll_async()
        self.now += m.SAMPLE_NS
        original = self.owner.native.u.PostMessageW.callback
        def post(*args):
            result = original(*args)
            asyncio.current_task().cancel()
            return result
        self.owner.native.u.PostMessageW.callback = post
        task = asyncio.create_task(self.consumer.poll_async())
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.consumer.state['status'], 'UNKNOWN')
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_ATTACK_CANCELLED')
        self.assertTrue(self.consumer.state['native_attempted'])
        self.assertEqual(self.consumer.sequence, 1)
        self.assertTrue((self.directory / 'manual-move-adapter-claim-1.json').exists())
        self.assertEqual(self.submit_attack()['status'], 'UNKNOWN')
        self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)


    async def test_npc_observation_stage_actual_positive_preserves_intent_scope(self):
        self.assertEqual(self.submit_attack()['phase'], 'ADMISSION')
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'PENDING', result)
        self.assertEqual(result['observation']['npc_observation_stage'], 'COMPLETE')
        self.assertEqual(self.posts, [])
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['phase'], 'NATIVE_WAIT')
        self.native_result()
        await self.accepted_attack()
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'COMMITTED', result)
        self.assertEqual(result['proof_scope'], 'VALIDATED_ATTACK_INTENT_ONLY')
        self.assertEqual(result['combat_effect'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.session.accepted_count, 1)

    async def test_npc_final_readback_stage_unknown_stays_terminal_after_post_and_intent(self):
        await self.admit_attack()
        self.native_result()
        await self.accepted_attack()
        grid_at = self.memory.transform + self.observer.proof.position_source['coordinates']['transform_grid_offset']
        hits = 0
        def fault(at, size, raw):
            nonlocal hits
            if at == grid_at:
                hits += 1
                if hits == 2:
                    return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = fault
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(result['reason'], 'MANUAL_ATTACK_NPC_OBSERVATION_UNKNOWN')
        self.assertEqual(result['observation']['npc_reason'], 'EDGE_TYPED_READ_CHANGED')
        self.assertEqual(result['observation']['npc_observation_stage'], 'FINAL_READBACK')
        self.assertTrue(result['native_attempted'])
        self.assertEqual(self.consumer.sequence, 1)
        self.assertEqual(self.session.accepted_count, 1)
        self.assertEqual(self.submit_attack()['status'], 'UNKNOWN')
        self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_npc_sample_replacement_cannot_inject_diagnostic_or_ready_row(self):
        self.submit_attack()
        original = npc_observe_tests.n.NpcObserver.sample
        class Stage(str):
            pass
        for supplied, value in ((False, None), (True, None), (True, 'INVALID_STAGE'),
                                (True, ['COMPLETE']), (True, Stage('COMPLETE'))):
            self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
                clock_ns=lambda: self.now, allow_attack=True)
            self.submit_attack()
            async def sample(observer, *args, **kwargs):
                row = await original(observer, *args, **kwargs)
                self.assertEqual(row['status'], 'OBSERVED', row)  # Real proof is unchanged.
                row.pop('observation_stage', None)
                if supplied:
                    row['observation_stage'] = value
                return row
            self.now += m.SAMPLE_NS
            with patch.object(npc_observe_tests.n.NpcObserver, 'sample', sample):
                result = await self.consumer.poll_async()
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertEqual(result['reason'], 'MANUAL_ATTACK_SAME_OBSERVER_TARGETS_REQUIRED')
            self.assertNotIn('observation', result)
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(self.posts, [])

    def count_drift(self, origin='INITIAL_DUPLICATE', *, after=None, count=None):
        """Use the original Native.read fixture; never forge a ready verdict."""
        from contextlib import contextmanager
        n = npc_observe_tests.n
        @contextmanager
        def installed():
            final, hits = [False], [0]
            original, previous = n._ObservationBudget.verify, self.memory.fault
            def verify(budget):
                final[0] = True
                try:
                    return original(budget)
                finally:
                    final[0] = False
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if ((origin in ('INITIAL_DUPLICATE', 'BOTH') and hits[0] == 2)
                            or (origin in ('FINAL_READBACK', 'BOTH') and final[0])):
                        if after is not None:
                            after()
                        value = struct.unpack('<i', raw)[0] + 1 if count is None else count
                        return struct.pack('<i', value)
                return previous(at, size, raw) if previous is not None else raw
            self.memory.fault = fault
            try:
                with patch.object(n._ObservationBudget, 'verify', verify):
                    yield
            finally:
                self.memory.fault = previous
        return installed()

    async def test_rechecked_count_admission_preserves_pending_then_public_attack_commits_once(self):
        from tools.local_original_session import launcher
        from tools.local_original_session.commands import REQUEST_SCHEMA
        public = self.directory / 'public-incomplete'; public.mkdir()
        ingress = launcher.ManualMoveRequests(public, self.consumer, allow_attack=True)
        self.addCleanup(ingress.close)
        position = self.service.snapshot()
        (public / 'command.request.json').write_text(json.dumps(dict(schema=REQUEST_SCHEMA,
            sequence=9, command='AttackTarget', uid=position.uid, target_uid=self.mover.state.uid, map_id=0)))
        await ingress.poll_async()
        pending = self.consumer.pending
        started = pending['started']
        with self.count_drift():
            result = await ingress.poll_async()
        self.assertEqual((result['status'], result['phase'], result['sequence']), ('PENDING', 'ADMISSION', 9))
        self.assertEqual(result['observation']['npc_read_consistency'], 'RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE')
        self.assertIs(self.consumer.pending, pending)
        self.assertFalse(pending['npc_ready'])
        self.assertNotIn('npc_completed_ns', pending)
        self.assertEqual(pending['started'], started)
        self.assertEqual(self.consumer.sequence, 0)
        self.assertEqual(self.posts, [])
        reads = len(self.memory.calls)
        await ingress.poll_async()  # Same memory slot never resamples.
        self.assertEqual(len(self.memory.calls), reads)
        self.now += m.SAMPLE_NS
        await ingress.poll_async()  # Actual strict producer row; still no Post.
        self.assertTrue(pending['npc_ready'])
        self.now += m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['phase'], 'NATIVE_WAIT')
        self.native_result(); await self.accepted_attack()
        self.now += m.SAMPLE_NS
        self.assertEqual((await ingress.poll_async())['status'], 'COMMITTED')
        durable = json.loads((public / 'command.result.json').read_text())
        self.assertEqual((durable['sequence'], durable['status']), (9, 'COMMITTED'))
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.session.accepted_count, 1)
        self.assertEqual(self.consumer.sequence, 1)
        self.writer.write.assert_not_called()

    async def test_rechecked_count_native_wait_retains_result_phase_clock_without_repost(self):
        await self.admit_attack(); self.native_result(); await self.accepted_attack()
        pending = self.consumer.pending
        started, completed = pending['started'], pending['npc_completed_ns']
        for origin in ('FINAL_READBACK', 'BOTH'):
            self.now += m.SAMPLE_NS
            with self.count_drift(origin):
                result = await self.consumer.poll_async()
            self.assertEqual((result['status'], result['phase']), ('PENDING', 'NATIVE_WAIT'))
            self.assertEqual(result['observation']['npc_read_consistency'], 'RECHECKED_SHARED_COUNT_' + origin)
            self.assertIs(self.consumer.pending, pending)
            self.assertEqual((pending['started'], pending['npc_completed_ns']), (started, completed))
            self.assertIsNotNone(pending['native'])
            self.assertEqual(self.consumer.sequence, 1)
            self.assertEqual(len(self.posts), 1)
            self.assertEqual(self.session.accepted_count, 1)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'COMMITTED')
        self.assertEqual(len(self.posts), 1)
        self.writer.write.assert_not_called()

    async def test_incomplete_contract_rejects_malformed_fields_from_actual_incomplete_row(self):
        class Text(str):
            pass
        with self.count_drift():
            row = await self.observer.sample(self.writer, self.mover.state.uid, now_ns=self.now)
        projection = self.targets._project(self.writer, attack.AttackRequest(self.mover.state.uid))
        args = self.mover.state.uid, self.service.snapshot().map_id, projection[2:4]
        self.assertTrue(m._rechecked_npc_incomplete(row, *args), row)
        for key, value in (('status', Text('UNKNOWN')), ('reason', 'OTHER'),
                ('stable_double_read', 0), ('source_contract_valid', 0), ('source_owner_revalidated', 1),
                ('source_owner_revalidated', False), ('client_grid', row['server_grid']),
                ('coordinates_match', False), ('coordinates_match', True), ('snapshot_atomic', True),
                ('uid', True), ('uid', 999), ('map_id', False), ('map_id', 999),
                ('server_grid', [1, 1]), ('read_consistency', 'NOT_CLASSIFIED'),
                ('read_consistency', ['RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE']),
                ('read_consistency', Text('RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE'))):
            with self.subTest(key=key, value=value):
                self.assertFalse(m._rechecked_npc_incomplete(dict(row, **{key: value}), *args))
        for key in ('client_grid', 'coordinates_match', 'source_owner_revalidated', 'read_consistency'):
            value = dict(row); value.pop(key)
            self.assertFalse(m._rechecked_npc_incomplete(value, *args))

    async def test_zero_negative_or_semantic_mixed_count_remains_terminal_and_cannot_revive(self):
        saved = dict(self.memory.data)
        for kind in ('zero', 'negative', 'mixed_uid', 'wrong_grid'):
            self.memory.data = dict(saved)
            self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
                clock_ns=lambda: self.now, allow_attack=True)
            self.submit_attack()
            after = (lambda: self.memory.put(self.memory.npc + 24, '<Q', 999)) if kind == 'mixed_uid' else None
            if kind == 'wrong_grid':
                self.memory.grid(self.memory.transform, [self.x + 1, self.y])
            with self.count_drift(after=after, count=0 if kind == 'zero' else -1 if kind == 'negative' else None):
                result = await self.consumer.poll_async()
            self.assertEqual(result['status'], 'UNKNOWN', (kind, result))
            self.assertNotIn('npc_read_consistency', result.get('observation', {}))
            self.memory.data = dict(saved)
            self.now += m.SAMPLE_NS
            reads = len(self.memory.calls)
            self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
            self.assertEqual(len(self.memory.calls), reads)
            self.assertEqual(self.posts, [])

    async def test_literal_observer_instance_bound_method_and_class_replacements_refuse(self):
        from types import MethodType
        async def forged(*args, **kwargs):
            self.fail('A replaced producer must never execute')
        for kind in ('instance', 'method', 'class'):
            self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
                clock_ns=lambda: self.now, allow_attack=True)
            self.submit_attack()
            observer = self.consumer._attack_observer
            if kind == 'instance':
                self.consumer._attack_observer = npc_observe_tests.n.NpcObserver(self.producer, self.reader)
                context = patch.object(observer, '_inflight', False)
            elif kind == 'method':
                context = patch.object(observer, 'sample', MethodType(forged, observer))
            else:
                context = patch.object(npc_observe_tests.n.NpcObserver, 'sample', forged)
            with context:
                result = await self.consumer.poll_async()
            self.assertEqual(result['status'], 'UNKNOWN', kind)
            self.assertEqual(result['reason'], 'MANUAL_ATTACK_SAME_OBSERVER_TARGETS_REQUIRED')
            self.assertEqual(self.posts, [])

    async def test_incomplete_count_followed_by_owner_or_deadline_change_stays_terminal(self):
        from types import MethodType
        original = self.producer._sample
        for kind in ('owner', 'deadline', 'replacement', 'sample_replacement'):
            self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
                clock_ns=lambda: self.now, allow_attack=True)
            self.submit_attack()
            restore = self.reader.owner.validate
            async def alter(row):
                result = await original(row)
                if kind == 'owner':
                    self.reader.owner.validate = lambda member: False
                elif kind == 'deadline':
                    self.now += m.WAIT_NS
                elif kind == 'replacement':
                    self.consumer._attack_observer = npc_observe_tests.n.NpcObserver(self.producer, self.reader)
                else:
                    async def forged(*args, **kwargs):
                        self.fail('A replaced sample must never execute')
                    observer = self.consumer._attack_observer
                    observer.sample = MethodType(forged, observer)
                return result
            self.producer._sample = alter
            try:
                with self.count_drift():
                    result = await self.consumer.poll_async()
                self.assertEqual(result['status'], 'UNKNOWN', (kind, result))
                self.assertEqual(self.posts, [])
            finally:
                self.reader.owner.validate = restore
                self.producer._sample = original
            self.now += m.SAMPLE_NS

    async def test_count_incomplete_cancelled_during_actual_read_is_terminal_without_post(self):
        import asyncio
        self.submit_attack()
        with self.count_drift(after=lambda: asyncio.current_task().cancel()):
            task = asyncio.create_task(self.consumer.poll_async())
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(self.consumer.state['status'], 'UNKNOWN')
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_ATTACK_CANCELLED')
        self.assertFalse(self.consumer._busy)
        self.assertEqual(self.posts, [])
        self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')

    def ctypes_authority_member(self):
        # Reuse the actual PROCESS-shaped HANDLE getter fixture, no Native init.
        from tools.local_original_session import attack_tests
        member = attack_tests.TargetTests.ctypes_primary(self)
        member.tid = 44
        first, second = member.process, member.process
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        return member

    async def test_ctypes_handle_attack_consumer_positive(self):
        self.ctypes_authority_member()
        await self.test_actual_observer_session_intent_and_native_return_are_distinct()

    async def test_ctypes_handle_read_duplicate_change_refuses_before_post(self):
        self.ctypes_authority_member()
        self.assertEqual(self.submit_attack()['phase'], 'ADMISSION')
        self.assertEqual((await self.consumer.poll_async())['phase'], 'ADMISSION')
        self.native.handle += 16
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(result['reason'], 'MANUAL_MOVE_READ_HANDLE_CHANGED')
        self.assertEqual(self.consumer.sequence, 0)
        self.assertFalse(result['native_attempted'])
        self.assertEqual(self.posts, [])
        self.assertFalse(list(self.directory.glob('manual-move-adapter-claim-*')))
        self.assertEqual(self.submit_attack()['status'], 'UNKNOWN')
        self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
        self.assertEqual(self.posts, [])

    def feedback_setup(self):
        from tools.local_original_session import attack_feedback
        from tools.local_original_session.attack_action_observe_tests import full_retained_reader
        self.session = attack_session.AttackSession(self.targets,
            policy=attack_session.EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT,
            feedback=attack_session.FeedbackConfig(attack_feedback.POLICY, 1, 3, True))
        self.producer._attack_session = self.realm._attack_session = self.session
        self.policy.attack_feedback = True
        self.action_component, self.target_component = 0x510000, 0x520000
        self.attack_action = 0x530000
        mem = self.memory
        mem.put(mem.npc + 0x20, '<QQ', 0x480000, 0x480020)
        mem.put(0x480010, '<QQ', self.target_component, 0x250000)
        mem.put(self.target_component, '<QQ', mem.base + 0x1180df0, mem.npc)
        mem.put(self.target_component + 0xa0, '<QQQQ', 0, 0, 0, 0)
        mem.put(self.target_component + 0xc0, '<Q', 0)
        full_retained_reader(self)
        self.real_samples = []
        original = self.reader.sample
        def sample(**kwargs):
            self.assertTrue(self.row['operation_lock'].locked())
            row, count = original(**kwargs)
            self.real_samples.append((self.now, row, count))
            return row, count
        self.reader.sample = sample
        self.consumer = m.ManualMoveCommands(self.reader, current=lambda: self.binding,
            clock_ns=lambda: self.now, allow_attack=True, observe_attack_feedback=True)

    async def feedback_admit(self):
        self.feedback_setup()
        self.assertEqual(self.submit_attack()['status'], 'PENDING')
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        self.assertEqual(len(self.real_samples), 0)  # Original NPC slot remains separate.
        self.now += m.SAMPLE_NS
        row = await self.consumer.poll_async()
        self.assertEqual(row['phase'], 'NATIVE_WAIT', row)
        self.assertEqual(len(self.real_samples), 1)
        self.assertTrue(row['attack_observations']['pre_command']['strict_idle'])
        self.native_result()

    async def feedback_receive(self):
        from tools.local_original_session.broker import OwnerSample
        policy_row = self.row['policy_row']
        sample = OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                            policy_row.peer, self.policy.now, True, True)
        x, y = movement.authority.unpack_grid(self.mover.state.packed)
        payload = attack._field(1, self.mover.state.uid) + attack._field(2, x) + attack._field(3, y)
        self.policy.received_frame(self.writer, sample, 0x4e30, len(payload) + 6, self.policy.now)
        async with self.row['operation_lock']:
            replies = await self.realm.registry.resolve(self.writer).received(SimpleNamespace(opcode=0x4e30, payload=payload))
            self.assertEqual(len(replies), 1)
            await self.producer._send(self.writer, self.row, replies, game=True,
                                      operation_lock=self.row['operation_lock'])
        self.assertEqual(self.session._feedback_state, 'DRAINED')

    async def feedback_tick(self):
        self.now += m.SAMPLE_NS
        return await self.consumer.poll_async()

    async def actual_attack_approach_move(self, direction=1):
        position = self.service.snapshot()
        payload = movement.pb.encode_message([movement.pb.encode_uint32(1, position.packed),
                                              movement.pb.encode_uint32(2, direction)])
        await self.received(0x4e2b, payload)
        position = self.service.snapshot()
        coordinate = struct.pack('<iiii', (position.word0 >> 6) + 0x7e00, (position.word1 >> 6) + 0x7e00,
                                 position.word0, position.word1) + bytes(24)
        self.memory.put(0x470038, '<80s', coordinate + coordinate)
        self.memory.put(0x5901c0, '<40s', coordinate)
        self.tiles()
        return position

    async def test_real_attack_approach_commit_then_current_intent_feedback_fresh_idle_once(self):
        await self.feedback_admit()
        initial, started = self.consumer.pending['initial'], self.consumer.pending['started']
        position = await self.actual_attack_approach_move()
        self.assertIsNot(position, initial)
        self.assertEqual(self.service._store.restore(position), position)
        await self.feedback_receive()
        self.assertIs(self.session.current_intent()._bound.attacker, position)
        first = await self.feedback_tick()
        self.assertEqual(first['status'], 'PENDING', first)
        self.assertIs(self.consumer.pending['initial'], position)
        self.assertEqual(self.consumer.pending['approach_commits'], 1)
        self.assertEqual(self.consumer.pending['started'], started)
        for _ in range(3):
            done = await self.feedback_tick()
        self.assertEqual(done['status'], 'COMMITTED', done)
        self.assertEqual(done['proof_scope'], 'VALIDATED_ATTACK_INTENT_ONLY')
        self.assertTrue(done['attack_observations']['next_strict_idle']['strict_idle'])
        self.assertEqual((self.service.requests_received, self.service.committed, self.service.corrections_prepared), (1, 1, 0))
        self.assertEqual(len(self.posts), 1)
        self.assertEqual((self.session.accepted_count, self.session.feedback_write_attempted, self.session.feedback_drained), (1, 1, 1))

    async def test_attack_approach_without_current_intent_cannot_commit_or_repost(self):
        await self.feedback_admit()
        await self.actual_attack_approach_move()
        for _ in range(3):
            result = await self.feedback_tick()
            self.assertEqual(result['status'], 'PENDING', result)
        self.assertEqual(self.session.accepted_count, 0)
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(len(self.posts), 1)

    async def test_attack_approach_forged_multi_correction_stale_owner_selection_are_terminal(self):
        from dataclasses import replace
        for index, mode in enumerate(('forged_position', 'missing_rx', 'multiple', 'correction',
                                     'stale_intent', 'owner', 'selection', 'deadline')):
            with self.subTest(mode=mode):
                if index:
                    await self.asyncSetUp()
                await self.feedback_admit()
                if mode == 'stale_intent': await self.feedback_receive()
                if mode == 'forged_position':
                    self.service._position = replace(self.service.snapshot())
                else:
                    await self.actual_attack_approach_move()
                    if mode == 'missing_rx':
                        self.policy.log = type(self.policy.log)([event for event in self.policy.log
                            if not (event[0] == 'rx' and event[2] == 0x4e2b)], maxlen=self.policy.log.maxlen)
                        self.policy.events -= 1
                    elif mode == 'multiple': await self.actual_attack_approach_move()
                    elif mode == 'correction': self.service.corrections_prepared += 1
                    elif mode == 'owner': self.owner.validate = lambda _: False
                    elif mode == 'selection':
                        game = self.realm.registry.resolve(self.writer)
                        game.selection = replace(game.selection)
                        self.realm.registry.selected[game.selection.reference] = game.selection
                if mode == 'deadline': self.now = self.consumer.pending['started'] + m.WAIT_NS
                else: self.now += m.SAMPLE_NS
                result = await self.consumer.poll_async()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertEqual(len(self.posts), 1)

    async def test_attack_approach_prepost_or_changed_uid_map_never_rebases(self):
        from dataclasses import replace
        for index, mode in enumerate(('prepost', 'uid', 'map')):
            with self.subTest(mode=mode):
                if index:
                    await self.asyncSetUp()
                if mode == 'prepost':
                    self.feedback_setup()
                    self.submit_attack()
                    await self.consumer.poll_async()  # NPC, still before first native Post.
                else:
                    await self.feedback_admit()
                original = self.consumer.pending['initial']
                await self.actual_attack_approach_move()
                if mode == 'uid': self.service._position = replace(self.service.snapshot(), uid=99)
                elif mode == 'map': self.service._position = replace(self.service.snapshot(), map_id=1)
                self.now += m.SAMPLE_NS
                result = await self.consumer.poll_async()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertIs(self.consumer.pending['initial'], original)
                self.assertEqual(len(self.posts), 0 if mode == 'prepost' else 1)
                if mode == 'prepost':
                    self.assertEqual(result['reason'], 'MANUAL_ATTACK_PLAYER_AUTHORITY_CHANGED')

    async def test_feedback_actual_retained_slots_drain_snapshot_then_distinct_strict_idle(self):
        await self.feedback_admit()
        await self.feedback_receive()
        mem = self.memory
        mem.put(self.attack_action, '<QQ', mem.base + 0x1180b78, self.action_component)
        mem.put(self.attack_action + 0x18, '<i', 3)
        mem.put(self.attack_action + 0x20, '<IB', 1, 0)
        mem.put(self.attack_action + 0x80, '<QQi', self.service.snapshot().uid, self.mover.state.uid, 1)
        mem.put(self.action_component + 0xc0, '<Q', self.attack_action)
        self.assertEqual((await self.feedback_tick())['status'], 'PENDING')  # NPC only.
        post = await self.feedback_tick()
        self.assertEqual(post['status'], 'PENDING', post)
        self.assertTrue(post['attack_observations']['post_feedback']['current_attack'])
        self.assertTrue(post['attack_observations']['post_feedback']['current_pair'])
        self.assertIsNotNone(self.consumer.pending)
        self.assertEqual((await self.feedback_tick())['status'], 'PENDING')  # NPC only.
        still_busy = await self.feedback_tick()
        self.assertEqual(still_busy['status'], 'PENDING', still_busy)
        self.assertFalse(still_busy['attack_observations']['next_strict_idle']['strict_idle'])
        await self.feedback_tick()  # NPC only.
        mem.put(self.action_component + 0xc0, '<Q', 0)
        done = await self.feedback_tick()
        self.assertEqual(done['status'], 'COMMITTED', done)
        self.assertIsNone(self.consumer.pending)
        self.assertEqual(done['proof_scope'], 'VALIDATED_ATTACK_INTENT_ONLY')
        snapshots = done['attack_observations']
        self.assertEqual(set(snapshots), {'pre_command', 'post_feedback', 'next_strict_idle'})
        self.assertGreater(snapshots['next_strict_idle']['at_ns'], snapshots['post_feedback']['at_ns'])
        self.assertTrue(snapshots['next_strict_idle']['strict_idle'])
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertEqual(self.writer.drain.await_count, 1)
        self.assertTrue(all(count <= 16384 for _, _, count in self.real_samples))
        self.assertTrue(all(row['attack_action']['status'] == 'OBSERVED' for _, row, _ in self.real_samples))

    async def test_feedback_replaced_literal_frame_or_current_writer_refuses(self):
        for kind in ('frame', 'writer'):
            with self.subTest(kind=kind):
                await self.asyncSetUp()
                await self.feedback_admit()
                await self.feedback_receive()
                await self.feedback_tick()
                self.assertEqual((await self.feedback_tick())['status'], 'PENDING')
                await self.feedback_tick()
                if kind == 'frame':
                    self.session._feedback_frame = bytes(bytearray(self.session._feedback_frame))
                else:
                    self.row['writer'] = object()
                done = await self.feedback_tick()
                self.assertEqual(done['status'], 'UNKNOWN', done)
                self.assertEqual(self.writer.write.call_count, 1)
                self.assertIsNotNone(self.consumer.pending)

    async def test_feedback_snapshots_fit_actual_2048_record_sink(self):
        from tools.local_original_session import commands
        from tools.local_original_session import attack_action_observe
        row = attack_action_observe.empty('X' * 127)
        row['status'] = 'UNKNOWN'
        row.update(combined_typed_bytes_requested=24576, refused_read_bytes=4096,
                   shortfall_at_refused_read=4096)
        self.consumer._attack_observations = {
            name: self.consumer._action_projection(row, (1 << 63) - 1, False)
            for name in ('pre_command', 'post_feedback', 'next_strict_idle')}
        self.consumer.state.update(phase='NATIVE_WAIT', native_attempted=True)
        self.consumer._window_failure('GET_CLIENT_RECT', 0xffffffff, 7, [None] * 8,
                                      {'class': 'GLFW30', 'hwnd': 500})
        state = self.consumer._terminal('X' * 110)
        state.update(sequence=(1 << 64) - 1, command='AttackTarget')
        from tools.local_original_session.launcher import ManualMoveRequests
        sink = ManualMoveRequests.__new__(ManualMoveRequests)
        sink.directory, sink.sequence = self.directory, (1 << 64) - 1
        sink._inventory_auto_selection = None  # Original Add-only metadata branch is disabled for this attack sink.
        recorded = sink._record(state)
        self.assertEqual(recorded['last_sequence'], sink.sequence)
        self.assertLessEqual((self.directory / 'command.result.json').stat().st_size, 2048)
        type(self).feedback_metrics = dict(record_bytes=(self.directory / 'command.result.json').stat().st_size)
        print('feedback_public_record_bytes=' + str(type(self).feedback_metrics['record_bytes']))
        invalid = dict(row, combined_typed_bytes_requested=True, refused_read_bytes=0,
                       shortfall_at_refused_read=4097)
        projected = self.consumer._action_projection(invalid, 1, None)
        self.assertTrue(all(projected[key] is None for key in ('combined_bytes', 'refused_bytes', 'shortfall_bytes')))

    async def test_feedback_final_resolver_cancel_or_deadline_cannot_commit(self):
        import asyncio
        for kind in ('cancel', 'deadline', 'clock_writer'):
            with self.subTest(kind=kind):
                await self.asyncSetUp()
                await self.feedback_admit()
                await self.feedback_receive()
                await self.feedback_tick()  # NPC.
                await self.feedback_tick()  # Post feedback.
                await self.feedback_tick()  # NPC.
                original = self.consumer._action_sample
                async def finish_sample(*args, **kwargs):
                    result = await original(*args, **kwargs)
                    if result is True:
                        if kind == 'deadline':
                            self.now = self.consumer.pending['started'] + m.WAIT_NS
                        elif kind == 'cancel':
                            def cancel_resolver():
                                asyncio.current_task().cancel()
                                return self.binding
                            self.consumer.current = cancel_resolver
                        else:
                            def changed_clock():
                                self.row['writer'] = object()
                                return self.now
                            self.consumer.clock_ns = changed_clock
                    return result
                self.consumer._action_sample = finish_sample
                if kind == 'cancel':
                    task = asyncio.create_task(self.feedback_tick())
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    self.assertEqual((await self.feedback_tick())['status'], 'UNKNOWN')
                self.assertEqual(self.consumer.state['status'], 'UNKNOWN')
                self.assertIsNotNone(self.consumer.pending)
                self.assertEqual(self.writer.write.call_count, 1)

    async def test_feedback_prepare_override_refuses_and_followup_move_clears_projection(self):
        from types import MethodType
        await self.feedback_admit()
        await self.feedback_receive()
        await self.feedback_tick()
        leaf = self.consumer._attack_action_observer
        async def fake_prepare(*args, **kwargs):
            self.fail('overridden prepare must never execute')
        leaf.prepare = MethodType(fake_prepare, leaf)
        self.assertEqual((await self.feedback_tick())['status'], 'UNKNOWN')
        self.assertEqual(self.writer.write.call_count, 1)
        await self.asyncSetUp()
        await self.feedback_admit()
        await self.feedback_receive()
        for _ in range(4):
            done = await self.feedback_tick()
        self.assertEqual(done['status'], 'COMMITTED', done)
        self.reader.__dict__.pop('sample', None)
        selected = self.service.snapshot()
        next_move = self.consumer.submit_goal(selected.uid, selected.word0 + 1, selected.word1)
        self.assertNotIn('attack_observations', next_move)
        self.assertIsNone(self.consumer._attack_observations)
        self.assertIsNone(self.consumer._last_attack_action)


    def cache_changed_physical(self):
        flags = dict(move=False, route=False)
        def physical(at, size, raw):
            if at == 0x580058:
                flags['move'] = True
            if flags['move'] and at == 0x320360 and size == 36:
                flags['route'] = True
            if flags['route'] and at == 0x250008 and size == 4:
                return struct.pack('<i', 5)  # Positive refcount changes in final Move route.
            return raw
        return physical

    async def attack_cache_read_changed(self, mutate=None):
        self.feedback_setup()
        self.assertEqual(self.submit_attack()['status'], 'PENDING')
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        self.memory.fault = self.cache_changed_physical()
        original = self.reader.sample
        if mutate is not None:
            def sample(**kwargs):
                row, count = original(**kwargs)
                mutate(row)
                return row, count
            self.reader.sample = sample
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        raw = self.real_samples[-1][1]
        self.assertEqual(raw['attack_action']['reason'], 'ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED', raw)
        self.assertEqual(raw['move_state']['status'], 'OBSERVED', raw['move_state'])
        return original, result

    async def test_attack_cache_changed_unknown_waits_for_fresh_npc_player_before_once_post(self):
        original, result = await self.attack_cache_read_changed()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'ADMISSION'), result)
        self.assertFalse(self.consumer.pending['npc_ready'])
        self.assertEqual(self.posts, [])
        self.assertEqual(self.consumer.sequence, 0)
        snapshot = result['attack_observations']['pre_command']
        self.assertEqual(snapshot['status'], 'UNKNOWN')
        self.assertIsNone(snapshot['strict_idle'])
        started, samples = self.consumer.pending['started'], len(self.real_samples)
        await self.consumer.poll_async()
        self.assertEqual(len(self.real_samples), samples)
        self.memory.fault = None
        self.reader.sample = original
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['phase'], 'ADMISSION')
        self.assertTrue(self.consumer.pending['npc_ready'])
        self.assertEqual(len(self.real_samples), samples)
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['phase'], 'NATIVE_WAIT', result)
        self.assertEqual(self.consumer.pending['started'], started)
        self.assertEqual(len(self.posts), 1)

    async def test_attack_cache_changed_wait_deadline_owner_source_and_uid_remain_terminal(self):
        for index, mode in enumerate(('deadline', 'owner', 'source', 'uid', 'shape')):
            with self.subTest(mode=mode):
                if index:
                    await self.asyncSetUp()
                def mutate(row):
                    if mode == 'source': row['world']['source_segment_grid_relation_match'] = False
                    if mode == 'uid': row['world']['my_player_uid'] = 99
                    if mode == 'shape': row['attack_action']['source_contract_valid'] = True
                original, result = await self.attack_cache_read_changed(mutate)
                if mode in ('deadline', 'owner'):
                    self.assertEqual(result['status'], 'PENDING', result)
                    if mode == 'deadline': self.now = self.consumer.pending['started'] + m.WAIT_NS
                    else:
                        self.owner.validate = lambda _: False
                        self.now += m.SAMPLE_NS
                    result = await self.consumer.poll_async()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertEqual(self.posts, [])
                self.assertEqual(self.consumer.sequence, 0)

    async def test_attack_cache_changed_after_native_stays_terminal_without_second_post(self):
        await self.feedback_admit()
        await self.feedback_receive()
        await self.feedback_tick()  # Existing NPC slot.
        self.memory.fault = self.cache_changed_physical()
        result = await self.feedback_tick()
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(result['reason'], 'MANUAL_ATTACK_ACTION_SNAPSHOT_UNKNOWN')
        self.assertEqual(self.real_samples[-1][1]['attack_action']['reason'],
                         'ATTACK_OBSERVE_CACHE_TYPED_READ_CHANGED')
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.session.feedback_drained, 1)

    async def attack_admission_read_changed(self, mutate=None):
        self.feedback_setup()
        self.assertEqual(self.submit_attack()['status'], 'PENDING')
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        original = self.reader.sample
        def sample(**kwargs):
            row, count = original(**kwargs)
            # Reuse the actual MoveState double-read producer fixture; only IO
            # races its controller bytes. AttackAction remains the real read.
            proxy = SimpleNamespace(sample=lambda **_: (row, count), assertEqual=self.assertEqual,
                                    assertFalse=self.assertFalse, assertTrue=self.assertTrue)
            row, count = ManualMoveTests.incoherent_motion_sample(proxy, include_input_state=False)
            if mutate is not None:
                mutate(row)
            return row, count
        self.reader.sample = sample
        self.now += m.SAMPLE_NS
        return original, await self.consumer.poll_async()

    async def test_attack_precommand_real_read_changed_waits_then_refreshes_npc_and_player(self):
        original, result = await self.attack_admission_read_changed()
        print('attack_precommand_real_read_changed status=' + result['status'] + ' reason='
              + str(result['reason']) + ' posts=' + str(len(self.posts)))
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'ADMISSION'), result)
        self.assertFalse(result['native_attempted'])
        self.assertFalse(self.consumer.pending['npc_ready'])
        started = self.consumer.pending['started']
        count = len(self.real_samples)
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        self.assertEqual(len(self.real_samples), count)
        self.reader.sample = original
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['phase'], 'ADMISSION')
        self.assertTrue(self.consumer.pending['npc_ready'])
        self.assertEqual(len(self.real_samples), count)  # Next existing slot is NPC only.
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['phase'], 'NATIVE_WAIT', result)
        self.assertEqual(self.consumer.pending['started'], started)
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.consumer.sequence, 1)

    async def test_attack_precommand_missing_tampered_and_busy_shapes_are_terminal(self):
        cases = (lambda row: row['move_state'].pop('navigation'),
                 lambda row: row['move_state'].update(stable_double_read=0),
                 lambda row: row['move_state']['action'].update(queue_count=1),
                 lambda row: row['move_state']['controller'].update(command_present=True),
                 lambda row: row['move_state'].update(reason='MOVE_ACTION_TYPE_TABLE_CHANGED'),
                 lambda row: row['world'].update(status='UNKNOWN', reason='WORLD_TYPED_READ_CHANGED',
                                               stable_double_read=False))
        for index, mutate in enumerate(cases):
            with self.subTest(case=index):
                if index:
                    await self.asyncSetUp()
                _, result = await self.attack_admission_read_changed(mutate)
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertFalse(result['native_attempted'])
                self.assertEqual(self.posts, [])
                self.assertEqual(self.consumer.sequence, 0)

    async def test_attack_precommand_known_uid_map_source_conflicts_remain_terminal(self):
        cases = ((lambda row: row['world'].update(my_player_uid=99), 'MANUAL_MOVE_KNOWN_UID_CONTRADICTION'),
                 (lambda row: row['world'].update(map_requested_i32=99), 'MANUAL_MOVE_KNOWN_MAP_CONTRADICTION'),
                 (lambda row: row['world'].update(source_segment_grid_relation_match=False),
                  'MANUAL_MOVE_KNOWN_SOURCE_CONTRADICTION'))
        for index, (mutate, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                if index:
                    await self.asyncSetUp()
                _, result = await self.attack_admission_read_changed(mutate)
                self.assertEqual(result['reason'], reason)
                self.assertEqual(result['observation']['move_state_reason'], 'MOVE_TYPED_READ_CHANGED')
                self.assertEqual(self.posts, [])

    async def test_attack_admission_wait_keeps_owner_cancel_deadline_and_npc_age_guards(self):
        for index, mode in enumerate(('owner', 'cancel', 'deadline', 'npc_age')):
            with self.subTest(mode=mode):
                if index:
                    await self.asyncSetUp()
                original, result = await self.attack_admission_read_changed()
                self.assertEqual(result['status'], 'PENDING')
                self.reader.sample = original
                started = self.consumer.pending['started']
                if mode == 'owner':
                    self.owner.validate = lambda _: False
                elif mode == 'cancel':
                    self.consumer.cancel()
                elif mode == 'deadline':
                    self.now = started + m.WAIT_NS
                else:
                    self.now += m.SAMPLE_NS
                    self.assertEqual((await self.consumer.poll_async())['phase'], 'ADMISSION')
                    self.now += 1_000_000_001
                result = await self.consumer.poll_async()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                if mode == 'deadline':
                    self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
                elif mode == 'npc_age':
                    self.assertEqual(result['reason'], 'MANUAL_ATTACK_NPC_PROOF_STALE')
                self.assertEqual(self.consumer.pending['started'], started)
                self.assertEqual(self.posts, [])

    async def test_attack_admission_failure_diagnostic_same_slot_and_bounded_public_result(self):
        _, result = await self.attack_admission_read_changed(
            lambda row: row['world'].update(status='UNKNOWN', reason='WORLD_TYPED_READ_CHANGED',
                                           stable_double_read=False))
        self.assertEqual(result['reason'], 'MANUAL_MOVE_SCENE_ACTOR_UNKNOWN')
        self.assertEqual(result['observation'], dict(scene_status='OBSERVED', scene_reason=None,
            world_status='UNKNOWN', world_reason='WORLD_TYPED_READ_CHANGED',
            move_state_status='UNKNOWN', move_state_reason='MOVE_TYPED_READ_CHANGED'))
        self.consumer._observation = {key: 'X' * 95 for key in result['observation']}
        self.consumer._attack_observations['pre_command']['reason'] = 'X' * 120
        self.consumer._window_failure('GET_CLIENT_RECT', 0xffffffff, 7, [None] * 8,
                                      {'class': 'GLFW30', 'hwnd': 500})
        bounded = self.consumer._terminal('X' * 110)
        from tools.local_original_session.launcher import ManualMoveRequests
        sink = ManualMoveRequests.__new__(ManualMoveRequests)
        sink.directory, sink.sequence, sink._inventory_auto_selection = self.directory, (1 << 31) - 1, None
        sink._record(bounded)
        size = (self.directory / 'command.result.json').stat().st_size
        self.assertLessEqual(size, 2048)
        print('attack_admission_worst_public_result_bytes=' + str(size))

    async def test_attack_refreshed_npc_failure_does_not_reuse_prior_player_diagnostic(self):
        original, result = await self.attack_admission_read_changed()
        self.assertEqual(result['status'], 'PENDING')
        self.reader.sample = original
        self.now += m.SAMPLE_NS
        self.owner.validate = lambda _: False
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertNotIn('observation', result)  # No new player sample on this failed entry.
        self.assertEqual(len(self.real_samples), 1)
        self.assertEqual(self.posts, [])


    async def feedback_discarded_idle(self, kind, mutate=None):
        await self.feedback_admit()
        await self.feedback_receive()
        mem = self.memory
        mem.put(self.attack_action, '<QQ', mem.base + 0x1180b78, self.action_component)
        mem.put(self.attack_action + 0x18, '<i', 3)
        mem.put(self.attack_action + 0x20, '<IB', 1, 0)
        mem.put(self.attack_action + 0x80, '<QQi', self.service.snapshot().uid, self.mover.state.uid, 1)
        mem.put(self.action_component + 0xc0, '<Q', self.attack_action)
        await self.feedback_tick()  # Original NPC slot.
        post = await self.feedback_tick()
        self.assertEqual(post['status'], 'PENDING', post)
        self.assertIs(post['attack_observations']['post_feedback']['current_pair'], True)
        mem.put(self.action_component + 0xc0, '<Q', 0)
        await self.feedback_tick()  # Original next NPC slot.
        mem.fault = self.discarded_idle_physical(kind)
        original = self.reader.sample
        if mutate is not None:
            def sample(**kwargs):
                row, count = original(**kwargs)
                mutate(row)
                return row, count
            self.reader.sample = sample
        result = await self.feedback_tick()
        raw = self.real_samples[-1][1]['attack_action']
        self.assertEqual(raw['status'], 'UNKNOWN', raw)
        return original, result

    def discarded_idle_physical(self, kind):
        if kind == 'CACHE': return self.cache_changed_physical()
        reads = [0]
        def changed(at, size, raw):
            if at == self.target_component + 0xc0 and size == 8:
                reads[0] += 1
                if reads[0] == 2: return bytes([raw[0] ^ 8]) + raw[1:]
            return raw
        return changed

    async def test_feedback_discarded_next_idle_waits_then_fresh_npc_action_commits_once(self):
        for index, kind in enumerate(('TYPED', 'CACHE')):
            if index: await self.asyncSetUp()
            original, result = await self.feedback_discarded_idle(kind)
            self.assertEqual(result['status'], 'PENDING', result)
            raw = self.real_samples[-1][1]['attack_action']
            expected = 'ATTACK_OBSERVE_' + ('CACHE_' if kind == 'CACHE' else '') + 'TYPED_READ_CHANGED'
            self.assertEqual(raw['reason'], expected)
            projection = result['attack_observations']['next_strict_idle']
            self.assertEqual(projection['status'], 'UNKNOWN')
            self.assertIsNone(projection['strict_idle'])
            self.assertIsNone(projection['current_attack'])
            pending, samples = self.consumer.pending, len(self.real_samples)
            started, sequence = pending['started'], self.consumer.sequence
            await self.consumer.poll_async()
            self.assertEqual(len(self.real_samples), samples)
            self.assertFalse(pending['feedback_action_next'])
            self.memory.fault, self.reader.sample = None, original
            self.assertEqual((await self.feedback_tick())['status'], 'PENDING')
            self.assertTrue(pending['feedback_action_next'])
            self.assertEqual(len(self.real_samples), samples)  # Fresh NPC, no extra action query.
            done = await self.feedback_tick()
            self.assertEqual(done['status'], 'COMMITTED', done)
            self.assertEqual(done['proof_scope'], 'VALIDATED_ATTACK_INTENT_ONLY')
            self.assertTrue(done['attack_observations']['next_strict_idle']['strict_idle'])
            self.assertGreater(done['attack_observations']['next_strict_idle']['at_ns'], projection['at_ns'])
            self.assertEqual((pending['started'], self.consumer.sequence), (started, sequence))
            self.assertEqual((len(self.posts), self.session.feedback_drained), (1, 1))

    async def test_feedback_discarded_repeated_unknown_expires_first_deadline_without_repost(self):
        for index, kind in enumerate(('TYPED', 'CACHE')):
            if index: await self.asyncSetUp()
            _, result = await self.feedback_discarded_idle(kind)
            self.assertEqual(result['status'], 'PENDING', result)
            pending, started = self.consumer.pending, self.consumer.pending['started']
            path = self.directory / 'attack-target-request.json'
            original = path.read_bytes(), path.stat().st_mtime_ns
            repeats = 1
            while self.now + m.SAMPLE_NS < started + m.WAIT_NS:
                if pending['feedback_action_next']:
                    self.memory.fault = self.discarded_idle_physical(kind)
                    repeats += 1
                result = await self.feedback_tick()
                self.assertEqual(result['status'], 'PENDING', result)
                self.assertEqual(pending['started'], started)
            self.now = started + m.WAIT_NS
            result = await self.consumer.poll_async()
            self.assertEqual((result['status'], result['reason']),
                             ('UNKNOWN', 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE'))
            self.assertGreater(repeats, 1)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), original)
            self.assertEqual((len(self.posts), self.consumer.sequence, self.session.feedback_drained), (1, 1, 1))

    async def test_feedback_discarded_shape_counts_none_fields_and_other_reason_are_terminal(self):
        cases = (('typed_bool', lambda r: r.update(typed_bytes_requested=True)),
                 ('combined_bound', lambda r: r.update(combined_typed_bytes_requested=24577)),
                 ('typed_gt_combined', lambda r: r.update(typed_bytes_requested=r['combined_typed_bytes_requested'] + 1)),
                 ('source_true', lambda r: r.update(source_contract_valid=True)),
                 ('uid_present', lambda r: r.update(actor_uid=1)),
                 ('refused_present', lambda r: r.update(refused_read_bytes=1)),
                 ('missing', lambda r: r.pop('hp_claimed')),
                 ('extra', lambda r: r.update(extra=0)),
                 ('other_reason', lambda r: r.update(reason='ATTACK_OBSERVE_TYPE_CHANGED')))
        for index, (name, change) in enumerate(cases):
            with self.subTest(name=name):
                if index: await self.asyncSetUp()
                _, result = await self.feedback_discarded_idle('TYPED', lambda row: change(row['attack_action']))
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertEqual(result['reason'], 'MANUAL_ATTACK_ACTION_SNAPSHOT_UNKNOWN' if name == 'other_reason'
                                 else 'MANUAL_ATTACK_IDLE_READ_SHAPE_REQUIRED')
                self.assertEqual((len(self.posts), self.session.feedback_drained), (1, 1))

    async def test_feedback_discarded_current_authority_and_other_unknown_are_terminal(self):
        modes = ('uid', 'map', 'grid', 'source', 'move_unknown', 'owner', 'writer', 'frame', 'intent', 'count', 'post_proof')
        for index, mode in enumerate(modes):
            with self.subTest(mode=mode):
                if index: await self.asyncSetUp()
                def change(row):
                    if mode == 'uid': row['world']['my_player_uid'] = 99
                    elif mode == 'map': row['world']['map_resolved_i32'] = 1
                    elif mode == 'grid': row['move_state']['transform']['predicted_grid'] = [0, 0]
                    elif mode == 'source': row['world']['source_segment_grid_relation_match'] = False
                    elif mode == 'move_unknown': row['move_state']['status'] = 'UNKNOWN'
                    elif mode == 'owner': self.owner.validate = lambda _: False
                    elif mode == 'writer': self.row['writer'] = object()
                    elif mode == 'frame': self.session._feedback_frame = bytes(bytearray(self.session._feedback_frame))
                    elif mode == 'intent': self.session._current = None
                    elif mode == 'count': self.session.accepted_count += 1
                    elif mode == 'post_proof': self.consumer._attack_observations['post_feedback']['status'] = 'UNKNOWN'
                _, result = await self.feedback_discarded_idle('CACHE', change)
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertEqual((len(self.posts), self.session.feedback_drained), (1, 1))

    async def test_feedback_discarded_sample_cancel_and_end_clock_authority_are_terminal(self):
        import asyncio
        for index, mode in enumerate(('cancel', 'clock_owner', 'clock_deadline')):
            if index: await self.asyncSetUp()
            def change(row):
                if mode == 'cancel': asyncio.current_task().cancel('discarded idle')
                else:
                    def clock():
                        if mode == 'clock_owner': self.owner.validate = lambda _: False
                        else: self.now = self.consumer.pending['started'] + m.WAIT_NS
                        return self.now
                    self.consumer.clock_ns = clock
            if mode == 'cancel':
                task = asyncio.create_task(self.feedback_discarded_idle('TYPED', change))
                with self.assertRaises(asyncio.CancelledError): await task
                result = self.consumer.state
            else:
                _, result = await self.feedback_discarded_idle('TYPED', change)
            self.assertEqual(result['status'], 'UNKNOWN', result)
            self.assertEqual((len(self.posts), self.session.feedback_drained), (1, 1))

    async def test_feedback_discarded_final_clock_and_real_store_loss_are_terminal(self):
        for index, mode in enumerate(('end_owner', 'end_deadline', 'store')):
            if index: await self.asyncSetUp()
            def change(row):
                if mode == 'store':
                    position = self.service.snapshot()
                    self.realm.positions.commit(position, replace(position, word0=position.word0 + 1))
                    return
                calls = [0]
                def clock():
                    calls[0] += 1
                    if calls[0] == 2:  # After same-query _observe, at the final deadline callback.
                        if mode == 'end_owner': self.owner.validate = lambda _: False
                        else: self.now = self.consumer.pending['started'] + m.WAIT_NS
                    return self.now
                self.consumer.clock_ns = clock
            _, result = await self.feedback_discarded_idle('TYPED', change)
            self.assertEqual(result['status'], 'UNKNOWN', result)
            self.assertEqual((len(self.posts), self.session.feedback_drained), (1, 1))


class ManualUseItemTests(unittest.IsolatedAsyncioTestCase):
    """Real Store/drained Inventory/I2 hooks; only process IO and native IPC mocked."""
    async def asyncSetUp(self):
        from tools.local_original_session.item_use_session_tests import SessionTests
        await SessionTests.asyncSetUp(self)
        self.owner, member = self.reader.owner, self.reader.member
        self.directory = Path(self.temp.name) / 'use-item-native'
        self.directory.mkdir()
        self.owner.directory, self.owner.image_sha = self.directory, m.USE_ITEM_IMAGE_SHA
        member.tid = 44
        self.reader.backend.handle = 707
        self.writer.is_closing = lambda: False
        self.posts, self.messages = [], []
        self.post_result, self.post_callback = True, None
        def rect(hwnd, pointer):
            value = C.cast(pointer, C.POINTER(W.RECT)).contents
            value.left, value.top, value.right, value.bottom = 0, 0, 800, 600
            return True
        def thread(hwnd, pointer):
            C.cast(pointer, C.POINTER(W.DWORD)).contents.value = member.pid
            return member.tid
        def post(*args):
            self.posts.append(args)
            if self.post_callback:
                self.post_callback()
            return self.post_result
        def register(name):
            self.messages.append(name)
            return 0xc123
        fn = commands_tests.Fn
        self.owner.native.u = SimpleNamespace(RegisterWindowMessageW=fn(register),
            GetClientRect=fn(rect), GetWindowThreadProcessId=fn(thread), PostMessageW=fn(post))
        self.owner.native.windows = lambda child: [dict(hwnd=500, visible=True, **{'class': 'GLFW30'})]
        self.owner.native.owned_hwnd = lambda child, hwnd: hwnd == 500
        self.realm.edge_passability = self.service.proof
        self.movement_service = self.realm.service(self.writer)
        self.movement_service._edge_passability = self.service.proof
        self.reader.sample = self.sample
        self.now, self.sample_calls = 1_000_000_000, 0
        await SessionTests.deliver(self)
        self.leaf = SessionTests.bind(self)
        from tools.local_original_session import inventory
        self.item_identifier = inventory.validate_frame(self.producer._inventory_frame).identifier
        self.binding = m.ManualMoveBinding(self.writer, self.producer)
        self.consumer = self.adapter()

    def adapter(self, **options):
        options = dict(allow_use_item=True) | options
        return m.ManualMoveCommands(self.reader, current=lambda: self.binding,
            clock_ns=lambda: self.now, **options)

    def sample(self, *, include_input_state=True):
        self.assertIs(include_input_state, False)
        self.sample_calls += 1
        p = self.movement_service.snapshot()
        grid = [p.word0, p.word1]
        return dict(status='OBSERVED', root_ready=True, current='Land', pending='none',
            world=dict(status='OBSERVED', stable_double_read=True, my_player_uid=p.uid,
                map_requested_i32=p.map_id, map_resolved_i32=p.map_id, grid_words=grid),
            move_state=dict(status='OBSERVED', source_contract_valid=True, stable_double_read=True,
                actor_uid=p.uid, controller=dict(status='OBSERVED', command_present=False),
                navigation=dict(status='OBSERVED', active=False),
                transform=dict(status='OBSERVED', current_grid=grid, predicted_grid=grid),
                action=dict(status='OBSERVED', queue_status='OBSERVED', queue_count=0,
                    busy_source_eval=dict(status='EVALUATED', value=False)))), 10

    def submit(self, **changes):
        p = self.movement_service.snapshot()
        values = dict(player_uid=p.uid, item_identifier=self.item_identifier, map_id=p.map_id)
        values.update(changes)
        return self.consumer.submit_use_item(**values)

    async def publish(self):
        self.assertEqual(self.submit()['status'], 'PENDING', self.consumer.state)
        self.assertFalse(self.posts)
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'PENDING', result)
        self.assertEqual(result['phase'], 'NATIVE_WAIT', result)
        return self.consumer.pending['request']

    def native_result(self, **changes):
        row = dict(self.consumer.pending['request'], schema='own-use-item-result-v1',
                   status='RETURNED', reason=0, invoked=True)
        row.update(changes)
        path = self.directory / ('use-item-result-' + str(self.consumer.sequence) + '.json')
        path.write_text(json.dumps(row, separators=(',', ':')) + '\n', encoding='ascii')
        return path

    async def receive(self, *, params=None, record_rx=True):
        from tools.local_original_session.item_use_tests import scalar, body
        from tools.local_original_session.broker import OwnerSample
        if params is None:
            params = scalar(1, 1) + scalar(15, 0) + scalar(16, 0)
        wire = body(params, self.item_identifier)
        async with self.row['operation_lock']:
            if record_rx:
                row = self.row['policy_row']
                sample = OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                                     row.peer, self.policy.now, True, True)
                self.policy.received_frame(self.writer, sample, 0x0960, len(wire) + 6, self.policy.now)
            self.assertEqual(await self.leaf.handle(self.writer, wire), ())

    async def test_actual_drained_inventory_received_intent_and_shared_sequence(self):
        for sequence in (1, 2):
            if sequence == 1:
                request = await self.publish()
            else:
                self.assertEqual(self.submit()['status'], 'PENDING')
                self.now += m.SAMPLE_NS
                self.assertEqual((await self.consumer.poll_async())['phase'], 'NATIVE_WAIT')
                request = self.consumer.pending['request']
            self.assertEqual(list(request), ['schema', 'pid', 'birth', 'candidate_sha256', 'seq',
                'command', 'player_uid', 'item_identifier', 'map_id'])
            self.assertEqual(request['candidate_sha256'], m.USE_ITEM_IMAGE_SHA)
            self.assertEqual(request['seq'], sequence)
            self.assertLessEqual(len((self.directory / 'use-item-request.json').read_bytes()), 512)
            self.native_result()
            self.now += m.SAMPLE_NS
            self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
            p = self.movement_service.snapshot()
            self.assertIs(self.consumer.submit_goal(p.uid, p.word0 + 1, p.word1)['accepted'], False)
            self.assertIs(self.consumer.submit_attack(p.uid, p.uid + 1, p.map_id)['accepted'], False)
            await self.receive()
            self.now += m.SAMPLE_NS
            result = await self.consumer.poll_async()
            self.assertEqual(result['status'], 'COMMITTED', result)
            self.assertEqual(result['proof_scope'], 'VALIDATED_ITEM_USE_INTENT_ONLY')
            self.assertTrue(all(result[k] == 'UNKNOWN' for k in ('use_effect', 'ack', 'equipped', 'render', 'save')))
        self.assertEqual([post[2:] for post in self.posts], [(1, 0), (2, 0)])
        self.assertEqual(self.messages, [m.USE_ITEM_MESSAGE] * 2)
        self.assertEqual(self.sample_calls, 2)
        self.assertEqual(len(self.memory.calls), self.reads_after_delivery)
        self.assertEqual(self.service.store.path.read_bytes(), self.saved_after_delivery)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    async def test_default_off_exact_bool_input_domains_and_program_image(self):
        for option in (0, 1, None, 'true'):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, 'EXPLICIT_BOOL'):
                self.adapter(allow_use_item=option)
        self.consumer = self.adapter(allow_use_item=False)
        self.assertEqual(self.submit()['reason'], 'MANUAL_USE_ITEM_DISABLED')
        for changes in (dict(player_uid=True), dict(item_identifier=0), dict(item_identifier=1 << 64),
                        dict(map_id=True), dict(map_id=1 << 31)):
            self.consumer = self.adapter()
            self.assertEqual(self.submit(**changes)['reason'], 'MANUAL_USE_ITEM_UID_MAP_REQUIRED')
        self.owner.image_sha = '9ffc24fe' + '0' * 56
        self.consumer = self.adapter()
        self.assertEqual(self.submit()['reason'], 'MANUAL_USE_ITEM_PROGRAM_IMAGE_REQUIRED')
        self.assertEqual(self.posts, [])

    async def test_admission_requires_actual_delivery_store_and_original_hook(self):
        delivery = self.producer._inventory_delivery_authority
        self.producer._inventory_delivery_authority = None
        self.assertEqual(self.submit()['reason'], 'MANUAL_USE_ITEM_DELIVERED_INVENTORY_REQUIRED')
        self.producer._inventory_delivery_authority = delivery
        self.consumer = self.adapter()
        self.leaf.validate_native_request = lambda *_: True
        self.assertEqual(self.submit()['reason'], 'MANUAL_USE_ITEM_ORIGINAL_OBSERVER_REQUIRED')
        del self.leaf.validate_native_request
        self.consumer = self.adapter()
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.service.store.path.unlink()
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'UNKNOWN', result)
        self.assertEqual(result['reason'], 'ITEM_USE_CURRENT_STORED_FRAME_REQUIRED')
        self.assertEqual(self.posts, [])

    async def test_native_return_alone_deadline_no_retry_and_fresh_slot(self):
        await self.publish()
        self.native_result()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        checked = self.consumer.pending['checked_ns']
        for _ in range(3):
            self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        self.assertEqual(self.consumer.pending['checked_ns'], checked)
        self.now = self.consumer.pending['started'] + m.WAIT_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE')
        self.assertEqual(self.submit(), result)
        self.assertEqual(await self.consumer.poll_async(), result)
        self.assertEqual(len(self.posts), 1)

    async def test_different_received_params_cannot_commit_by_count(self):
        from tools.local_original_session.item_use_tests import scalar
        await self.publish(); self.native_result()
        await self.receive(params=scalar(1, 1))
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_USE_ITEM_RECEIVED_REQUEST_MISMATCH')
        self.assertEqual(self.leaf.accepted_count, 1)
        self.assertEqual(len(self.posts), 1)

    async def test_received_intent_without_cs0960_is_unknown(self):
        await self.publish(); self.native_result()
        await self.receive(record_rx=False)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_USE_ITEM_CS0960_UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_polling_store_loss_is_terminal_before_matching(self):
        await self.publish(); self.native_result(); await self.receive()
        self.service.store.path.unlink()
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'ITEM_USE_CURRENT_STORED_FRAME_REQUIRED')
        self.assertEqual(len(self.posts), 1)

    async def test_received_before_native_result_waits_without_another_post(self):
        await self.publish(); await self.receive()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        self.native_result()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'COMMITTED')
        self.assertEqual(len(self.posts), 1)

    async def test_published_request_register_store_loss_prevents_post(self):
        await self.prepost_store_change('register')

    async def test_published_request_final_window_store_loss_prevents_post(self):
        await self.prepost_store_change('window')

    async def prepost_store_change(self, stage):
        from tools.local_original_session import inventory
        for index, change in enumerate(('delete', 'conflict')):
            with self.subTest(stage=stage, change=change):
                if index:
                    await self.asyncSetUp()
                store = self.service.store.path
                def mutate():
                    self.assertTrue((self.directory / 'use-item-request.json').is_file())
                    self.assertTrue(self.row['operation_lock'].locked())
                    if change == 'delete':
                        store.unlink()
                    else:
                        value = json.loads(store.read_bytes())
                        fields = dict(inventory.validate_frame(self.producer._inventory_frame).raw_fields)
                        fields[4] += 1
                        value['inventories'][0]['frame'] = inventory.build_add(fields).hex()
                        store.write_text(json.dumps(value), encoding='ascii')
                user, mutated = self.owner.native.u, []
                if stage == 'register':
                    original = user.RegisterWindowMessageW.callback
                    def callback(name):
                        result = original(name)
                        mutated.append(True); mutate()
                        return result
                    user.RegisterWindowMessageW.callback = callback
                else:
                    original = user.GetWindowThreadProcessId.callback
                    def callback(*args):
                        result = original(*args)
                        if (self.directory / 'use-item-request.json').is_file() and not mutated:
                            mutated.append(True); mutate()
                        return result
                    user.GetWindowThreadProcessId.callback = callback
                self.assertEqual(self.submit()['status'], 'PENDING')
                result = await self.consumer.poll_async()
                print('use_item_prepost_store stage=' + stage + ' change=' + change
                      + ' posts=' + str(len(self.posts)) + ' status=' + result['status']
                      + ' reason=' + str(result['reason']))
                self.assertEqual(mutated, [True])
                self.assertEqual(self.posts, [])
                self.assertEqual(result['reason'], 'ITEM_USE_CURRENT_STORED_FRAME_REQUIRED')
                self.assertIs(result['native_attempted'], False)
                self.assertEqual(self.submit(), result)

    async def test_numeric_uid_item_alias_and_uint64_item_remain_distinct_domains(self):
        p = self.movement_service.snapshot()
        self.assertEqual(self.submit(item_identifier=p.uid)['status'], 'PENDING')
        # The source hook still requires the actual delivered item, even though
        # neither equality with player UID nor full uint64 is a parse error.
        self.consumer = self.adapter()
        self.assertEqual(self.submit(item_identifier=(1 << 64) - 1)['status'], 'PENDING')
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
        self.assertEqual(self.posts, [])

    async def test_immutable_result_replacement_is_terminal(self):
        await self.publish()
        path = self.native_result()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        raw = path.read_bytes(); path.unlink(); path.write_bytes(raw + b' ')
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_USE_ITEM_IMMUTABLE_RESULT_CHANGED')
        self.assertEqual(len(self.posts), 1)

    async def test_native_nonreturned_is_terminal(self):
        await self.publish()
        self.native_result(status='REFUSED', invoked=False, reason=3)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_USE_ITEM_NATIVE_NOT_RETURNED')
        self.assertEqual(len(self.posts), 1)

    async def test_native_result_bool_is_not_int(self):
        await self.publish(); self.native_result(invoked=1)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_USE_ITEM_RESULT_IDENTITY_OR_SCHEMA')
        self.assertEqual(len(self.posts), 1)

    async def test_native_result_other_item_is_not_current(self):
        await self.publish(); self.native_result(item_identifier=self.item_identifier + 1)
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_USE_ITEM_RESULT_IDENTITY_OR_SCHEMA')
        self.assertEqual(len(self.posts), 1)

    async def test_accepted_counter_more_than_one_is_ambiguous(self):
        await self.publish(); self.native_result()
        self.leaf.accepted_count += 2
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['reason'], 'MANUAL_USE_ITEM_INTENT_COUNTER_AMBIGUOUS')
        self.assertEqual(len(self.posts), 1)

    async def test_post_failure_and_boundary_replay_refused(self):
        self.post_result = False
        self.assertEqual(self.submit()['status'], 'PENDING')
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_POST_UNKNOWN')
        self.assertEqual(self.submit(), result)
        self.consumer = self.adapter()
        self.assertEqual(self.submit()['status'], 'PENDING')
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_MOVE_BOUNDARY_PREVIOUSLY_USED')
        self.assertEqual(len(self.posts), 1)

    async def test_current_literal_missing_or_identity_copy_before_post_refuses(self):
        initial = self.producer._inventory_current_frame
        self.assertIs(initial, self.producer._inventory_operation_frame)
        self.producer._inventory_current_frame = None
        self.assertEqual(self.submit()['reason'], 'MANUAL_USE_ITEM_DELIVERED_INVENTORY_REQUIRED')
        self.producer._inventory_current_frame = initial
        self.consumer = self.adapter()
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.producer._inventory_current_frame = bytes(bytearray(initial))
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_USE_ITEM_INVENTORY_BINDING_CHANGED')
        self.assertIs(result['native_attempted'], False)
        self.assertEqual(self.posts, [])
        self.assertIs(self.producer._inventory_frame, initial)
        self.assertIs(self.producer._inventory_operation_frame, initial)

    async def test_current_literal_changed_in_prepost_callback_refuses_without_post(self):
        initial = self.producer._inventory_current_frame
        original = self.owner.native.u.RegisterWindowMessageW.callback
        def changed(name):
            result = original(name)
            self.producer._inventory_current_frame = bytes(bytearray(initial))
            return result
        self.owner.native.u.RegisterWindowMessageW.callback = changed
        self.assertEqual(self.submit()['status'], 'PENDING')
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_USE_ITEM_INVENTORY_BINDING_CHANGED')
        self.assertIs(result['native_attempted'], False)
        self.assertEqual(self.posts, [])
        self.assertEqual(self.consumer.sequence, 1)  # Original immutable claim remains spent.
        self.assertEqual(self.submit(), result)

    async def test_current_literal_changed_during_received_wait_is_terminal_no_repost(self):
        await self.publish(); self.native_result()
        initial = self.producer._inventory_current_frame
        self.producer._inventory_current_frame = bytes(bytearray(initial))
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['reason'], 'MANUAL_USE_ITEM_INVENTORY_BINDING_CHANGED')
        self.assertIs(result['native_attempted'], True)
        self.assertEqual(self.submit(), result)
        self.assertEqual(await self.consumer.poll_async(), result)
        self.assertEqual(len(self.posts), 1)

    async def test_cancel_during_post_is_terminal_without_repost(self):
        import asyncio
        self.post_callback = lambda: asyncio.current_task().cancel()
        self.assertEqual(self.submit()['status'], 'PENDING')
        with self.assertRaises(asyncio.CancelledError):
            await self.consumer.poll_async()
        asyncio.current_task().uncancel()
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_USE_ITEM_CANCELLED')
        self.assertEqual(self.submit(), self.consumer.state)
        self.assertEqual(len(self.posts), 1)
        # Consume the event-loop cancellation scheduled by the mocked Post.
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass


class ManualSourceRestartTests(unittest.IsolatedAsyncioTestCase):
    """Real restart/settings route and retained reader; only process IO/IPC mocked."""
    async def asyncSetUp(self):
        from tools.local_original_session import broker_tests, npc_observe
        from tools.local_original_session.attack_action_observe_tests import full_retained_reader
        await broker_tests.RestartRouteTests.asyncSetUp(self)
        self.service = self.realm.service(self.writer)
        self.targets = attack.AttackTargets(self.producer, self.reader)
        self.observer = npc_observe.NpcObserver(self.producer, self.reader)
        self.memory = npc_observe_tests.Memory(self)
        self.action_component = 0x510000
        ManualAttackTests.tiles(self)
        full_retained_reader(self)
        self.realm.edge_passability = self.service._edge_passability = self.observer.proof
        self.owner, member = self.reader.owner, self.reader.member
        self.directory = Path(self.temp.name) / 'source-restart-native'
        self.directory.mkdir()
        self.owner.directory, self.owner.image_sha = self.directory, m.USE_ITEM_IMAGE_SHA
        member.tid = 44
        self.writer.is_closing = lambda: False
        self.posts, self.messages = [], []
        self.post_result, self.post_callback = True, None
        def rect(hwnd, pointer):
            value = C.cast(pointer, C.POINTER(W.RECT)).contents
            value.left, value.top, value.right, value.bottom = 0, 0, 800, 600
            return True
        def thread(hwnd, pointer):
            C.cast(pointer, C.POINTER(W.DWORD)).contents.value = member.pid
            return member.tid
        def post(*args):
            self.posts.append(args)
            if self.post_callback: self.post_callback()
            return self.post_result
        def register(name):
            self.messages.append(name)
            return 0xc123
        fn = commands_tests.Fn
        self.owner.native.u = SimpleNamespace(RegisterWindowMessageW=fn(register), GetClientRect=fn(rect),
            GetWindowThreadProcessId=fn(thread), PostMessageW=fn(post))
        self.owner.native.windows = lambda child: [dict(hwnd=500, visible=True, **{'class': 'GLFW30'})]
        self.owner.native.owned_hwnd = lambda child, hwnd: hwnd == 500
        self.binding = m.ManualMoveBinding(self.writer, self.producer)
        self.now = 1_000_000_000
        self.consumer = self.adapter()

    def adapter(self, **options):
        return m.ManualMoveCommands(self.reader, current=lambda: self.binding, clock_ns=lambda: self.now,
                                   **(dict(allow_source_restart=True) | options))

    def submit(self):
        p = self.service.snapshot()
        return self.consumer.submit_source_restart(p.uid, p.map_id)

    async def publish(self):
        self.assertEqual(self.submit()['status'], 'PENDING', self.consumer.state)
        self.assertFalse(self.posts)
        self.assertEqual(self.consumer.poll()['phase'], 'ADMISSION')  # Async owner only; sync cannot claim.
        self.assertFalse(self.posts)
        result = await self.consumer.poll_async()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'NATIVE_WAIT'), result)
        return self.consumer.pending['request']

    def native_result(self, **changes):
        result = dict(self.consumer.pending['request'], schema='own-source-restart-result-v1',
                      status='RETURNED', reason=0, invoked=True)
        result.update(changes)
        path = self.directory / ('source-restart-result-' + str(self.consumer.sequence) + '.json')
        path.write_text(json.dumps(result, separators=(',', ':')) + '\n', encoding='ascii')
        return path

    async def receive_restart(self):
        from tools.local_original_session import broker_tests
        await broker_tests.RestartRouteTests.dispatch(self, broker_tests.c2s(0x4ed6,
            movement.pb.encode_bytes(1, b'explicit-settings-fixture')))
        await broker_tests.RestartRouteTests.dispatch(self, broker_tests.c2s(0x4e33))

    async def test_real_settings_restart_drain_selection_clear_and_return_required(self):
        request = await self.publish()
        self.assertEqual(list(request), ['schema', 'pid', 'birth', 'candidate_sha256', 'seq', 'command', 'phase'])
        self.assertEqual(request['candidate_sha256'], '8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684')
        self.assertEqual((request['seq'], request['phase']), (1, 'LandRestart'))
        self.assertEqual(self.messages, ['LC-Owned-Manual-SourceRestart-v1'])
        self.native_result()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        before = self.realm.settings.committed
        await self.receive_restart()
        self.assertEqual(self.realm.settings.committed, before + 1)
        self.assertIsNone(self.game.selection)
        self.binding = None  # Cleared selection must not require the regular binding resolver.
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result, dict(status='COMMITTED', reason=None, sequence=1, automatic_retry=False,
            cleanup_required=False, phase='COMMITTED', native_attempted=True, command='SourceRestart',
            proof_scope='LOCAL_RESTART_ACK_DRAIN_ONLY', response_drained=True, selection_cleared=True,
            ui='UNKNOWN', inventory_restore='UNKNOWN'))
        self.assertEqual((len(self.posts), self.writer.write.call_count, self.writer.drain.await_count), (1, 1, 1))
        self.assertIsNone(self.consumer.pending)

    async def test_default_flag_exact_bool_and_one_claim_post_sequence(self):
        for value in (None, 0, 1, 'true'):
            with self.assertRaisesRegex(ValueError, 'EXPLICIT_BOOL'):
                self.adapter(allow_source_restart=value)
        self.consumer = self.adapter(allow_source_restart=False)
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertFalse(self.posts)
        self.consumer = self.adapter()
        self.consumer.sequence = 7
        request = await self.publish()
        self.assertEqual(request['seq'], 8)
        self.assertEqual(self.submit()['accepted'], False)
        for _ in range(3):
            self.now += m.SAMPLE_NS
            self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
        self.assertEqual(len(self.posts), 1)
        self.native_result()
        await self.receive_restart()
        self.now += m.SAMPLE_NS
        self.assertEqual((await self.consumer.poll_async())['status'], 'COMMITTED')
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 1)

    async def test_missing_return_and_return_without_ack_do_not_complete_deadline(self):
        for mode in ('missing_return', 'return_only'):
            with self.subTest(mode=mode):
                if mode != 'missing_return': await self.asyncSetUp()
                await self.publish()
                if mode == 'missing_return': await self.receive_restart()
                else: self.native_result()
                self.now += m.SAMPLE_NS
                self.assertEqual((await self.consumer.poll_async())['status'], 'PENDING')
                self.now = self.consumer.pending['started'] + m.WAIT_NS
                result = await self.consumer.poll_async()
                self.assertEqual((result['status'], result['reason']),
                                 ('UNKNOWN', 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE'))
                self.assertEqual(len(self.posts), 1)

    async def test_native_result_schema_sequence_status_and_image_not_dll(self):
        cases = (dict(seq=2), dict(phase='Other'), dict(invoked=False), dict(reason=True),
                 dict(status='UNKNOWN'), dict(candidate_sha256='90dee4d8d7f56ef6400c059acaa0134309bc07d6bec14c59ffe575f9450004ed'))
        for index, changes in enumerate(cases):
            with self.subTest(changes=changes):
                if index: await self.asyncSetUp()
                await self.publish()
                self.native_result(**changes)
                self.now += m.SAMPLE_NS
                self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
                self.assertEqual(len(self.posts), 1)
                self.writer.write.assert_not_called()

    async def test_false_ack_ambiguous_drain_old_selection_and_unproven_settings_terminal(self):
        from tools.local_original_session import broker_tests
        for index, mode in enumerate(('false_ack', 'ambiguous_drain', 'old_selection', 'no_settings')):
            with self.subTest(mode=mode):
                if index: await self.asyncSetUp()
                await self.publish(); self.native_result()
                selected = self.game.selection
                if mode == 'no_settings':
                    await broker_tests.RestartRouteTests.dispatch(self, broker_tests.c2s(0x4e33))
                else:
                    await self.receive_restart()
                    if mode == 'false_ack': self.row['_restart']['frame'] = b'\x08\x00'
                    elif mode == 'ambiguous_drain': self.row['_restart']['drain_returned'] = None
                    else: self.game.selection = selected
                self.now += m.SAMPLE_NS
                self.assertEqual((await self.consumer.poll_async())['status'], 'UNKNOWN')
                self.assertEqual(len(self.posts), 1)

    async def test_owner_source_prepost_postfault_and_deadline_never_repost(self):
        for index, mode in enumerate(('owner_pre', 'source_pre', 'post_failure', 'owner_wait', 'source_wait', 'deadline')):
            with self.subTest(mode=mode):
                if index: await self.asyncSetUp()
                self.assertEqual(self.submit()['status'], 'PENDING')
                if mode == 'owner_pre': self.owner.closed = True
                elif mode == 'source_pre':
                    self.producer.source_guard = lambda: (_ for _ in ()).throw(ValueError('SOURCE_CHANGED'))
                elif mode == 'post_failure': self.post_result = False
                elif mode == 'deadline': self.now += m.WAIT_NS
                result = await self.consumer.poll_async()
                if mode.endswith('_wait'):
                    self.assertEqual(result['phase'], 'NATIVE_WAIT')
                    if mode == 'owner_wait': self.owner.closed = True
                    else: self.producer.source_guard = lambda: (_ for _ in ()).throw(ValueError('SOURCE_CHANGED'))
                    self.now += m.SAMPLE_NS
                    result = await self.consumer.poll_async()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                count = 1 if mode in ('post_failure', 'owner_wait', 'source_wait') else 0
                self.assertEqual(len(self.posts), count)
                await self.consumer.poll_async()
                self.assertEqual(len(self.posts), count)

    async def test_final_registration_cancel_prevents_post_and_never_rearms(self):
        import asyncio
        self.assertEqual(self.submit()['status'], 'PENDING')
        def cancel(name):
            asyncio.current_task().cancel('source restart registration')
            return 0xc123
        self.owner.native.u.RegisterWindowMessageW = commands_tests.Fn(cancel)
        with self.assertRaises(asyncio.CancelledError):
            await self.consumer.poll_async()
        self.assertEqual(self.consumer.state['reason'], 'MANUAL_SOURCE_RESTART_CANCELLED')
        self.assertFalse(self.posts)
        self.assertEqual(self.submit()['status'], 'UNKNOWN')
        try: await asyncio.sleep(0)
        except asyncio.CancelledError: pass


class ManualSourceReselectTests(unittest.IsolatedAsyncioTestCase):
    """Same real Restart/Store source plus its real selected-generation route."""
    async def asyncSetUp(self):
        from tools.local_original_session import broker as b, feature_config as fc, inventory, inventory_store, inventory_tests, launcher, restart
        # The existing fixture supplies the retained Native.read/physical world
        # and named IPC mock; rebuild only through the real product constructor.
        await ManualSourceRestartTests.asyncSetUp(self)
        retained, profile_path, expected_uuid = self.owner, self.realm.store.path, self.realm.expected_uuid
        wire = inventory.build_add(inventory_tests.explicit_fields())
        config = fc.Features(inventory_policy=inventory.POLICY, inventory_frame=wire,
            inventory_store_policy=inventory_store.POLICY, inventory_delivery_policy=fc.LOCAL_WORLD_READY_ONCE,
            inventory_reselection_policy=fc.LOCAL_SAVED_ROW_ON_RESELECTION, restart_policy=restart.POLICY)
        factory = launcher.ProductFeatureFactory(self.reader, product='sibling-background-source-restart-spawn',
            control_mode='manual', directory=self.directory, config=config)
        self.producer = b.PersistentBroker(sockets={12000: object(), 14030: object()},
            retained_owner=retained, owner_handle=retained.owner_handle, owner_job=retained.owner_job,
            owner_guard=lambda _: True, owner_liveness_guard=lambda: True, source_guard=lambda: None,
            key_guard=lambda: True, conversation_factory=lambda *_: None, expected_uuid=expected_uuid,
            store_path=profile_path, settings_path=profile_path.with_name('reselect-settings.bin'),
            edge_passability=self.observer.proof, **factory.broker_options())
        self.realm, self.policy = self.producer.realm, self.producer.policy
        self.producer._inventory_store.grant(self.realm.profile_uid, wire)  # Temporary saved input only.
        def sample(peer):
            return b.OwnerSample(retained, retained.owner_handle, retained.owner_job,
                peer, b.time.monotonic_ns(), True, True)
        def boot(writer, peer):
            row = self.policy.admit(writer, peer, sample(peer), b.time.monotonic_ns())
            for opcode, size, request in ((0x4e20, 12, None), (0x4e35, 76, 0x4e34), (0x4f3e, 6, 0x4f3d)):
                if request is not None: self.policy.received_frame(writer, sample(peer), request, 10, b.time.monotonic_ns())
                self.policy.begin_write(writer, sample(peer), opcode, size, 0, b.time.monotonic_ns())
                self.policy.drained(writer, sample(peer), 0, b.time.monotonic_ns())
            return row
        prior, peer = object(), b.Peer(14030, 41000, b.time.monotonic_ns())
        boot(prior, peer)
        self.policy.eof(prior, sample(peer), True, b.time.monotonic_ns())
        self.policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        peer = b.Peer(14030, 41001, b.time.monotonic_ns())
        admitted = boot(self.writer, peer)
        import asyncio
        self.row = dict(writer=self.writer, policy_row=admitted, failed=False, joined=False, eof=False,
            operation_lock=asyncio.Lock(), peer=dict(connection_id=4, endpoint_port=14030, server_port=14030,
                client_port=peer.client_port, accepted_monotonic_ns=peer.accepted_ns))
        self.producer._claims[14030] = [self.row]
        async def owner(writer, position): return await self.producer._movement_owner(writer, self.row, position)
        async def account(writer): return await self.producer._account_owner(writer, self.row)
        self.game = self.realm.grant(self.writer, movement_owner_guard=owner, account_owner_guard=account, connection_id=4)
        from tools.local_own_login_request.codec import LocalLoginRequest
        await self.game.received(SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', expected_uuid).payload()))
        await self.receive_selection()
        self.service = self.realm.service(self.writer)
        self.binding = m.ManualMoveBinding(self.writer, self.producer)
        self.consumer = self.adapter()
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()

    def adapter(self, **options):
        return m.ManualMoveCommands(self.reader, current=lambda: self.binding, clock_ns=lambda: self.now,
            **(dict(allow_source_restart=True, allow_source_reselect=True) | options))

    async def receive_selection(self, reference=None):
        from tools.local_original_session import broker_tests
        body = movement.pb.encode_bytes(1, (self.realm.profile_name if reference is None else reference).encode('utf-8')) + b'\x10\0\x18\0'
        await broker_tests.RestartRouteTests.dispatch(self, broker_tests.c2s(0x4e28, body))

    async def ready_reselect(self, *, native_before=None):
        if native_before is not None: self.consumer.sequence = native_before
        await ManualSourceRestartTests.publish(self)
        ManualSourceRestartTests.native_result(self)
        await ManualSourceRestartTests.receive_restart(self)
        self.now += m.SAMPLE_NS
        result = await self.consumer.poll_async()
        self.assertEqual(result['status'], 'COMMITTED', result)
        self.old_bound = self.consumer._bound
        self.old_generation = self.producer._inventory_generation
        self.assertEqual(self.old_generation.phase, 'RETIRED')
        p = self.service.snapshot()
        result = self.consumer.submit_source_reselect(p.uid, p.map_id)
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'ADMISSION'), result)
        self.assertEqual(len(self.posts), 1)
        self.scene('Select')

    def submit(self): return ManualSourceRestartTests.submit(self)

    def scene(self, name):
        row, = [value for value in self.memory.c['scenes'] if value['kind'] == ('CharacterSelect' if name == 'Select' else name)]
        index = 4 if name == 'Select' else 5
        self.memory.put(0x340000, '<QQI', self.memory.base + row['rva'], 0, index)
        self.memory.put(0x320360, '<QQQQI', 0x340000, 0x250000, 0, 0, index)

    def native_result(self, **changes):
        row = dict(self.consumer.pending['request'], schema='own-source-reselect-result-v1',
            status='RETURNED', reason=0, invoked=True)
        row.update(changes)
        path = self.directory / ('source-reselect-result-' + str(self.consumer.sequence) + '.json')
        path.write_text(json.dumps(row, separators=(',', ':')) + '\n', encoding='ascii')
        return path

    async def tick(self):
        self.now += m.SAMPLE_NS
        return await self.consumer.poll_async()

    async def test_real_two_phase_reselect_new_generation_world_rebind_keeps_global_once(self):
        await self.ready_reselect()
        started, bound = self.consumer.pending['started'], self.consumer._bound
        result = await self.tick()
        self.assertEqual((result['status'], result['phase']), ('PENDING', 'NATIVE_WAIT'), result)
        request = self.consumer.pending['request']
        self.assertEqual(list(request), ['schema', 'pid', 'birth', 'candidate_sha256', 'seq', 'command', 'phase',
                                        'saved_character_uid', 'canonical_reference_utf8_hex'])
        self.assertEqual((request['seq'], request['phase']), (2, 'SelectSlot'))
        self.assertEqual(bytes.fromhex(request['canonical_reference_utf8_hex']).decode('utf-8'), self.realm.profile_name)
        self.native_result()
        self.assertEqual((await self.tick())['phase'], 'ADMISSION')
        self.assertEqual(len(self.posts), 2)  # Slot RETURNED did not immediately Post SelectOK.
        self.assertEqual((await self.tick())['phase'], 'NATIVE_WAIT')
        self.assertEqual((self.consumer.sequence, self.consumer.pending['request']['phase']), (3, 'SelectOK'))
        self.assertIs(self.consumer._bound, bound)
        self.native_result()
        result = await self.tick()
        self.assertEqual(result['status'], 'PENDING')  # RETURNED alone is not selection/world.
        await self.receive_selection()
        self.scene('Land')
        result = await self.tick()
        self.assertEqual(result, dict(status='COMMITTED', reason=None, sequence=3, automatic_retry=False,
            cleanup_required=False, phase='COMMITTED', native_attempted=True, command='SourceReselect',
            proof_scope='LOCAL_RESELECT_LAND_READY_ONLY', selection_changed=True, world_ready=True,
            ui='UNKNOWN', inventory_restore='UNKNOWN'))
        complete = self.consumer._source_reselect_completed
        self.assertIs(complete[0], self.consumer._source_restart_completed)
        self.assertIs(complete[1], self.producer._inventory_generation)
        self.assertIs(complete[1].previous, self.old_generation)
        self.assertIs(complete[2], self.consumer._bound)
        for index, (before, after) in enumerate(zip(bound[0], complete[2][0])):
            if index in (9, 12): self.assertIsNot(before, after)
            else: self.assertIs(before, after)
        self.assertTrue(self.consumer._reservation and self.consumer._source_restart_claimed and self.consumer._source_reselect_claimed)
        self.assertEqual(self.consumer._source_restart_completed['started'] < started, True)
        self.assertEqual([post[2] for post in self.posts], [1, 2, 3])
        self.assertEqual(self.consumer.submit_source_reselect(self.service.snapshot().uid, 0)['status'], 'UNKNOWN')
        self.assertEqual(len(self.posts), 3)

    async def slot_returned(self):
        await self.ready_reselect()
        self.assertEqual((await self.tick())['phase'], 'NATIVE_WAIT')
        first = self.native_result()
        self.assertEqual((await self.tick())['phase'], 'ADMISSION')
        return first

    async def ok_returned(self):
        await self.slot_returned()
        self.assertEqual((await self.tick())['phase'], 'NATIVE_WAIT')
        self.native_result()
        return self.consumer.pending

    async def test_reselect_default_bool_restart_and_saved_uid_map_are_strict(self):
        for value in (None, 0, 1, 'true'):
            with self.assertRaisesRegex(ValueError, 'BOOL_REQUIRED'):
                self.adapter(allow_source_reselect=value)
        with self.assertRaisesRegex(ValueError, 'BOOL_REQUIRED'):
            self.adapter(allow_source_restart=False)
        consumer = self.adapter(allow_source_reselect=False)
        self.assertEqual(consumer.submit_source_reselect(1, 0)['status'], 'UNKNOWN')
        self.assertEqual(self.consumer.submit_source_reselect(1, 0)['status'], 'UNKNOWN')
        self.assertFalse(self.posts)

    async def test_reselect_scene_wait_and_partial_return_keep_original_deadline_no_repost(self):
        for index, mode in enumerate(('scene', 'slot_missing', 'ok_only')):
            if index: await self.asyncSetUp()
            if mode == 'ok_only': await self.ok_returned()
            else: await self.ready_reselect()
            pending, started = self.consumer.pending, self.consumer.pending['started']
            if mode == 'scene': self.scene('Land')
            for _ in range(3):
                self.assertEqual((await self.tick())['status'], 'PENDING')
                self.assertEqual(pending['started'], started)
            self.now = started + m.WAIT_NS
            result = await self.consumer.poll_async()
            self.assertEqual((result['status'], result['reason']), ('UNKNOWN', 'MANUAL_MOVE_ORIGINAL_CLAIM_DEADLINE'))
            self.assertEqual(len(self.posts), {'scene': 1, 'slot_missing': 2, 'ok_only': 3}[mode])
            self.assertIs(self.consumer._bound, self.old_bound)

    async def test_reselect_native_ref_uid_phase_status_and_first_immutable_result_refuse(self):
        cases = ('uid', 'ref', 'phase', 'not_returned', 'first_deleted', 'first_changed')
        for index, mode in enumerate(cases):
            with self.subTest(mode=mode):
                if index: await self.asyncSetUp()
                if mode.startswith('first_'):
                    path = await self.slot_returned()
                    if mode == 'first_deleted': path.unlink()
                    else: path.write_text(path.read_text(encoding='ascii').replace('"reason":0', '"reason":1'), encoding='ascii')
                else:
                    await self.ready_reselect(); await self.tick()
                    changes = {'uid': dict(saved_character_uid=2), 'ref': dict(canonical_reference_utf8_hex='61'),
                        'phase': dict(phase='SelectOK'), 'not_returned': dict(status='UNKNOWN', invoked=False)}[mode]
                    self.native_result(**changes)
                result = await self.tick()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertEqual(len(self.posts), 2)
                self.assertIs(self.consumer._bound, self.old_bound)

    async def test_reselect_generation_restart_store_source_owner_and_early_selection_refuse(self):
        for index, mode in enumerate(('owner', 'source', 'store_uid', 'old_restart_copy', 'old_generation', 'early_selection', 'counter')):
            with self.subTest(mode=mode):
                if index: await self.asyncSetUp()
                await self.ready_reselect()
                if mode == 'owner': self.owner.closed = True
                elif mode == 'source': self.producer.source_guard = lambda: (_ for _ in ()).throw(ValueError('SOURCE_CHANGED'))
                elif mode == 'store_uid':
                    data = self.realm.store._read()
                    data['characters'][0]['uid'], data['next_uid'] = 2, 3
                    self.realm.store._write(data)
                elif mode == 'old_restart_copy': self.row['_restart'] = dict(self.row['_restart'])
                elif mode == 'old_generation': self.old_generation.phase = 'ACTIVE'
                elif mode == 'early_selection': await self.receive_selection()
                else:
                    await self.ok_returned_after_ready()
                    await self.receive_selection()
                    self.realm.service(self.writer).requests_received += 1
                result = await self.tick()
                self.assertEqual(result['status'], 'UNKNOWN', result)
                self.assertIs(self.consumer._bound, self.old_bound)
                self.assertEqual(len(self.posts), 3 if mode == 'counter' else 1)

    async def ok_returned_after_ready(self):
        await self.tick(); self.native_result(); await self.tick(); await self.tick(); self.native_result()

    async def test_reselect_sample_cancel_deadline_and_world_uid_mismatch_never_rebind(self):
        import asyncio
        for index, mode in enumerate(('cancel', 'deadline', 'world_uid')):
            if index: await self.asyncSetUp()
            await self.ok_returned()
            await self.receive_selection()
            self.scene('Land')
            original = self.reader.sample
            def sample(**kwargs):
                row, count = original(**kwargs)
                if mode == 'cancel': asyncio.current_task().cancel('reselect sample')
                elif mode == 'deadline': self.now = self.consumer.pending['started'] + m.WAIT_NS
                else: row['world']['my_player_uid'] = 99
                return row, count
            self.reader.sample = sample
            if mode == 'cancel':
                task = asyncio.create_task(self.tick())
                with self.assertRaises(asyncio.CancelledError): await task
                result = self.consumer.state
            else: result = await self.tick()
            self.assertEqual(result['status'], 'UNKNOWN', result)
            self.assertIs(self.consumer._bound, self.old_bound)
            self.assertEqual(len(self.posts), 3)

    async def test_reselect_old_ack_literal_and_late_sequence_bound_never_rearm(self):
        for index, mode in enumerate(('ack_literal', 'late_sequence')):
            if index: await self.asyncSetUp()
            await self.ready_reselect(native_before=m.MAX_SEQUENCE - 2 if mode == 'late_sequence' else None)
            if mode == 'ack_literal':
                self.row['_restart']['frame'] = bytes(bytearray(self.row['_restart']['frame']))
            else:
                self.assertEqual((await self.tick())['phase'], 'NATIVE_WAIT')
                self.native_result()
                self.assertEqual((await self.tick())['phase'], 'ADMISSION')
            result = await self.tick()
            self.assertEqual(result['status'], 'UNKNOWN', result)
            self.assertEqual(len(self.posts), 1 if mode == 'ack_literal' else 2)
            self.assertIs(self.consumer._bound, self.old_bound)

    async def test_reselect_select_ok_result_replacement_during_last_sample_never_commits(self):
        await self.ok_returned()
        await self.receive_selection()
        self.scene('Land')
        path = self.directory / ('source-reselect-result-' + str(self.consumer.sequence) + '.json')
        original = self.reader.sample
        def sample(**kwargs):
            row, count = original(**kwargs)
            replacement = path.with_suffix('.replacement')
            replacement.write_bytes(path.read_bytes())
            replacement.replace(path)  # Same JSON, different immutable file identity.
            return row, count
        self.reader.sample = sample
        result = await self.tick()
        self.assertEqual((result['status'], result['reason']),
                         ('UNKNOWN', 'MANUAL_SOURCE_RESELECT_IMMUTABLE_RESULT_CHANGED'))
        self.assertIsNone(self.consumer._source_reselect_completed)
        self.assertIs(self.consumer._bound, self.old_bound)
        self.assertEqual(len(self.posts), 3)


if __name__ == '__main__':
    unittest.main()
