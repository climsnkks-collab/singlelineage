"""Headless explicit NPC steps and real realm/send/policy; no listener/native."""
import asyncio
from dataclasses import replace
import tempfile
import time
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools.local_original_session import broker as b, npc, npc_motion as motion
from tools.local_original_session.npc_tests import spawn
from tools.local_own_login_request.codec import LocalLoginRequest


class StateTests(unittest.TestCase):
    def test_direction_goal_wire_and_local_time_are_separate(self):
        candidate = spawn()
        mover = motion.NpcMotion(candidate, self_uid=1, interval_ns=100, policy=motion.LOCAL_PRE_STEP)
        start = b.movement.authority.unpack_grid(mover.state.packed)
        for direction, delta in enumerate(b.movement.authority.DELTAS):
            goal = tuple(a + d for a, d in zip(start, delta))
            step = mover.plan(goal=goal, direction=direction, now_ns=1234)
            self.assertIs(step.before, mover.state)
            self.assertEqual(b.movement.authority.unpack_grid(step.after.packed), goal)
            self.assertEqual(step.after.last_step_ns, 1234)
            with b.movement.pb.parse_message(step.frame[4:-2], schema={1: 0, 2: 0, 3: 0}) as parsed:
                self.assertEqual([(f.number, f.value) for f in parsed.fields],
                                 [(1, candidate.uid), (2, mover.state.packed), (3, direction)])
            self.assertEqual(int.from_bytes(step.frame[2:4], 'little'), 0x4e2c)
        self.assertIsNone(mover.state.last_step_ns)  # Planning never commits.

    def test_remote_uid_explicit_cadence_goal_bounds_and_once_commit(self):
        for policy in (None, 'ORIGINAL_SERVER_POLICY_UNKNOWN', 'POST_STEP', True):
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_SERVER_POLICY_UNKNOWN'):
                motion.NpcMotion(spawn(), self_uid=1, interval_ns=100, policy=policy)
        for interval in (None, 0, -1, True):
            with self.assertRaises(ValueError):
                motion.NpcMotion(spawn(), self_uid=1, interval_ns=interval, policy=motion.LOCAL_PRE_STEP)
        with self.assertRaises(ValueError):
            motion.NpcMotion(spawn(), self_uid=2, interval_ns=100, policy=motion.LOCAL_PRE_STEP)
        mover = motion.NpcMotion(spawn(), self_uid=1, interval_ns=100, policy=motion.LOCAL_PRE_STEP)
        x, y = b.movement.authority.unpack_grid(mover.state.packed)
        for kwargs in (dict(goal=(x, y), direction=2), dict(goal=(x + 1, y), direction=6),
                       dict(goal=(-1, y), direction=6), dict(goal=(x + 1, y), direction=8)):
            with self.assertRaises(ValueError):
                mover.plan(**kwargs, now_ns=1000)
        step = mover.plan(goal=(x + 1, y), direction=2, now_ns=1000)
        with self.assertRaises(ValueError):
            mover.begin(step)  # NPC has not actually been drained yet.
        mover.spawn_drained = True
        with self.assertRaisesRegex(ValueError, 'EXACT_LOCAL_PRE_STEP_REQUIRED'):
            mover.begin(replace(step, reported_grid=step.after.packed))
        mover.begin(step); mover.validate_frame(step.frame); mover.commit(step)
        with self.assertRaises(ValueError):
            mover.commit(step)
        with self.assertRaisesRegex(ValueError, 'CADENCE'):
            mover.plan(goal=(x + 2, y), direction=2, now_ns=1099)
        mover.close()
        with self.assertRaises(ValueError):
            mover.plan(goal=(x + 2, y), direction=2, now_ns=1100)


class ConnectedMotionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.edge_result = True
        self.edge_mutation = None
        self.edges = []

        async def npc_edge(*edge):
            self.edges.append(edge)
            if self.edge_mutation:
                self.edge_mutation()
            return self.edge_result

        self.realm = b.LocalRealm(str(uuid.uuid4()), Path(self.temp.name) / 'characters.json',
            npc_spawns=(spawn(),), npc_motion_interval_ns=100, npc_edge_passability=npc_edge,
            npc_motion_policy=motion.LOCAL_PRE_STEP)
        self.writer = types.SimpleNamespace(transport=types.SimpleNamespace(get_write_buffer_size=lambda: 0),
                                            write=mock.Mock(), drain=mock.AsyncMock())
        self.realm.store.create(b.ack.realm.Creation(self.realm.profile_name, 0, 0, (13,) * 6))
        async def owner(*_):
            return True
        game = self.realm.grant(self.writer, movement_owner_guard=owner)
        await game.received(types.SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))
        pb = b.ack.realm.pb
        payload = pb.encode_message([pb.encode_bytes(1, self.realm.profile_name.encode()),
                                    pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        frames = await game.received(types.SimpleNamespace(opcode=0x4e28, payload=payload))
        self.policy = b._TransportPolicy(object(), object(), object(),
                                        {12000: object(), 14030: object()}, now=time.monotonic_ns())
        def sample(peer):
            return b.OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                                 peer, time.monotonic_ns(), True, True)
        def boot(writer, peer):
            row = self.policy.admit(writer, peer, sample(peer), time.monotonic_ns())
            for opcode, size, request in ((0x4e20, 12, None), (0x4e35, 76, 0x4e34), (0x4f3e, 6, 0x4f3d)):
                if request is not None:
                    self.policy.received_frame(writer, sample(peer), request, 10, time.monotonic_ns())
                self.policy.begin_write(writer, sample(peer), opcode, size, 0, time.monotonic_ns())
                self.policy.drained(writer, sample(peer), 0, time.monotonic_ns())
            return row
        prior, peer = object(), b.Peer(14030, 41000, time.monotonic_ns())
        boot(prior, peer)
        self.policy.eof(prior, sample(peer), True, time.monotonic_ns())
        self.policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        peer = b.Peer(14030, 41001, time.monotonic_ns())
        policy_row = boot(self.writer, peer)
        self.row = dict(writer=self.writer, policy_row=policy_row, peer=dict(connection_id=4, endpoint_port=14030),
                        joined=False, failed=False, operation_lock=asyncio.Lock())
        self.producer = object.__new__(b.PersistentBroker)
        self.producer._npc_respawn = None
        self.producer.realm, self.producer.policy = self.realm, self.policy
        self.producer._claims = {12000: [], 14030: [self.row]}
        self.producer._closing = False
        self.producer.failure = asyncio.Event(); self.producer.failure_code = None
        self.producer.owner_failure = None; self.producer._servers = []
        async def owned_sample(_):
            return sample(peer)
        self.producer._sample = owned_sample
        await self.producer._send(self.writer, self.row, frames, game=True)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.mover = self.realm.npc_mover(self.writer)
        self.initial = self.mover.state
        self.x, self.y = b.movement.authority.unpack_grid(self.initial.packed)

    async def step(self, **changes):
        options = dict(goal=(self.x + 1, self.y), direction=2, now_ns=1000)
        options.update(changes)
        return await self.producer.step_npc(self.writer, **options)

    async def test_missing_consumer_pin_is_hard_block_despite_selected_reference_policy(self):
        with mock.patch.object(motion, 'REMOTE_CONTRACT_SHA', None):
            with self.assertRaisesRegex(ValueError, 'FIELD2_SOURCE_UNKNOWN_UNSAFE_NOT_SENT'):
                await self.step()
        self.writer.write.assert_not_called()
        self.assertIs(self.mover.state, self.initial)
        self.assertFalse(self.mover.fatal)

    async def test_exact_remote_step_real_send_commit_and_cadence(self):
        state = await self.step()
        self.assertEqual((state.uid, state.packed), (2, b.movement.authority.pack_grid(self.x + 1, self.y)))
        self.assertEqual(self.edges, [(2, 0, self.initial.packed, 2, state.packed)])
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertEqual(self.writer.drain.await_count, 1)
        self.assertEqual(self.policy.log[-1][2], 0x4e2c)
        with self.assertRaisesRegex(ValueError, 'CADENCE'):
            await self.step(goal=(self.x + 2, self.y), now_ns=1099)
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_blocked_unknown_or_owner_loss_before_send_preserves_authority(self):
        for result in (False, None):
            self.edge_result = result
            with self.assertRaisesRegex(ValueError, 'EDGE_BLOCKED_OR_UNKNOWN'):
                await self.step()
        self.edge_result = True
        self.edge_mutation = self.realm.registry.selected.clear
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            await self.step()
        self.writer.write.assert_not_called()
        self.assertIs(self.mover.state, self.initial)
        self.assertFalse(self.mover.fatal)

    async def test_drain_failure_is_unknown_fatal_and_never_retried(self):
        self.writer.drain.side_effect = OSError('synthetic')
        with self.assertRaises(OSError):
            await self.step()
        with self.assertRaises(ValueError):
            await self.step()
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertTrue(self.mover.fatal)
        self.assertTrue(self.producer.failure.is_set())
        self.assertIs(self.mover.state, self.initial)

    async def test_post_checkpoint_selection_loss_never_writes_or_commits(self):
        checkpoint = self.producer._checkpoint
        count = 0
        async def mutation(*args):
            nonlocal count
            count += 1
            result = await checkpoint(*args)
            if count == 3:
                self.realm.registry.selected.clear()
            return result
        self.producer._checkpoint = mutation
        with self.assertRaises(ValueError):
            await self.step()
        self.writer.write.assert_not_called()
        self.assertIs(self.mover.state, self.initial)
        self.assertTrue(self.mover.fatal)  # _send began: conservative unknown delivery policy.

    async def test_same_row_serializes_two_steps_during_drain(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def drain():
            entered.set()
            await release.wait()
        self.writer.drain.side_effect = drain
        first = asyncio.create_task(self.step())
        await entered.wait()
        second = asyncio.create_task(self.step(goal=(self.x + 2, self.y), now_ns=1100))
        await asyncio.sleep(0)
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertFalse(second.done())
        release.set()
        await asyncio.gather(first, second)
        self.assertEqual(self.writer.write.call_count, 2)
        self.assertEqual(self.mover.state.packed, b.movement.authority.pack_grid(self.x + 2, self.y))

    async def test_closed_foreign_default_and_nonpending_frames_never_validate(self):
        proposed = self.mover.plan(goal=(self.x + 1, self.y), direction=2, now_ns=1000)
        for writer in (None, object(), self.writer):
            with self.assertRaises(ValueError):
                self.realm.validate_reply(proposed.frame, writer=writer)
        self.realm.close(self.writer)
        self.assertTrue(self.mover.closed)
        self.assertEqual(self.realm._npc_motion, {})
        with self.assertRaises(ValueError):
            await self.step()

    async def test_close_during_write_drain_is_unknown_and_never_commits(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def drain():
            entered.set()
            await release.wait()
        self.writer.drain.side_effect = drain
        moving = asyncio.create_task(self.step())
        await entered.wait()
        self.realm.close(self.writer)
        release.set()
        with self.assertRaises(ValueError):
            await moving
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertIs(self.mover.state, self.initial)
        self.assertTrue(self.mover.closed and self.mover.fatal)
        self.assertFalse(self.row['operation_lock'].locked())

    async def test_cancellation_during_drain_marks_unknown_and_releases_row_lock(self):
        entered = asyncio.Event()
        async def drain():
            entered.set()
            await asyncio.Future()
        self.writer.drain.side_effect = drain
        moving = asyncio.create_task(self.step())
        await entered.wait()
        moving.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await moving
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertIs(self.mover.state, self.initial)
        self.assertTrue(self.mover.fatal and self.producer.failure.is_set())
        self.assertIsNone(self.mover.pending)
        self.assertFalse(self.row['operation_lock'].locked())



if __name__ == '__main__':
    unittest.main()
