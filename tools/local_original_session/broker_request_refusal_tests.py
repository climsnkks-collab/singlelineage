"""Request refusal regressions through real decoder/policy/dispatch; no sockets."""
import asyncio
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools.local_original_session import broker as b, world_visibility
from tools.local_original_session.broker_tests import FixtureConversation, c2s, version_request
from tools.local_entry_server import protobuf as pb
from tools.local_own_login_request.codec import LocalLoginRequest


class MemoryWriter:
    def __init__(self, client_port):
        self.client_port = client_port
        self.transport = mock.Mock()
        self.transport.get_write_buffer_size.return_value = 0
        self.writes = asyncio.Queue()
        self.closed = False

    def get_extra_info(self, name):
        return ('127.0.0.1', self.client_port if name == 'peername' else 12000)

    def write(self, wire):
        self.writes.put_nowait(bytes(wire))

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass

    async def response(self):
        return await asyncio.wait_for(self.writes.get(), 2)


class RequestRefusalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.uuid = str(uuid.uuid4())
        self.broker = b.PersistentBroker(sockets={12000: object(), 14030: object()},
            retained_owner=object(), owner_handle=object(), owner_job=object(),
            owner_guard=lambda _: True, owner_liveness_guard=lambda: True,
            source_guard=lambda: None, conversation_factory=FixtureConversation,
            expected_uuid=self.uuid, store_path=Path(self.temp.name) / 'characters.json',
            edge_passability=lambda *_: True, world_policy=world_visibility.POLICY)
        self.rows = []

    async def asyncTearDown(self):
        for reader, writer, row in self.rows:
            reader.feed_eof()
        await asyncio.gather(*(row['task'] for _, _, row in self.rows))

    async def connect(self):
        reader, writer = asyncio.StreamReader(), MemoryWriter(41000 + len(self.rows))
        self.broker._accept(12000, reader, writer)
        row = self.broker._claims[12000][-1]
        self.rows.append((reader, writer, row))
        self.assertEqual(await writer.response(), b.KEY12)
        reader.feed_data(c2s(0x4e34, version_request()))
        self.assertEqual(int.from_bytes((await writer.response())[2:4], 'little'), 0x4e35)
        reader.feed_data(c2s(0x4f3d))
        self.assertEqual(await writer.response(), b.EMPTY_COUNTS)
        return reader, writer, row

    async def selected(self):
        reader, writer, row = await self.connect()
        reader.feed_eof()
        await row['task']
        await asyncio.sleep(0)  # existing _joined callback promotes the first stream
        self.broker.realm.store.create(b.ack.realm.Creation('SoloKnight', 0, 0, (13,) * 6))
        reader, writer, row = await self.connect()
        reader.feed_data(c2s(0x263, LocalLoginRequest(0x0100007f,
            'standalone.local', self.uuid).payload()))
        self.assertEqual(await writer.response(), b.ack.ACK_FRAME)
        await writer.response()
        await writer.response()
        self.assertEqual(await writer.response(), b.LOGIN_AUTH_FINISH_FRAME)
        reader.feed_data(c2s(0x4e28, pb.encode_message([pb.encode_bytes(1, b'SoloKnight'),
            pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        for opcode in (0x4e29, 0x4e95, 0x4e38, 0x4e96):
            self.assertEqual(int.from_bytes((await writer.response())[2:4], 'little'), opcode)
        reader.feed_data(c2s(b.ALIVE_REQUEST))
        while await writer.response() != b.ALIVE_FRAME:
            pass  # selection also publishes nearby world actors
        return reader, writer, row

    async def test_unknown_then_stage_inappropriate_then_alive_keeps_same_stream(self):
        reader, writer, row = await self.selected()
        before = row['policy_row'].received
        dropped_before = getattr(self.broker, '_world_dropped_requests', 0)
        # Deliberately independent of 4E2F, which may acquire a feature handler.
        reader.feed_data(c2s(0x7fff) + c2s(0x4e28) + c2s(b.ALIVE_REQUEST))
        self.assertEqual(await writer.response(), b.ALIVE_FRAME)
        self.assertFalse(self.broker.failure.is_set(), self.broker.failure_code)
        self.assertFalse(writer.closed)
        self.assertFalse(row['task'].done())
        self.assertEqual(row['policy_row'].received, before + 3)
        self.assertIn('GAME_OPCODE_UNBOUND@0x7fff', self.broker._world_handler_errors)
        self.assertEqual(self.broker._world_dropped_requests, dropped_before + 2,
                         self.broker._world_handler_errors)
        self.assertTrue(any(error.endswith('@0x4e28') for error in self.broker._world_handler_errors))

    async def test_non_world_unknown_remains_fail_closed(self):
        reader, writer, row = await self.selected()
        self.broker._world = None
        self.broker.policy.world = False
        reader.feed_data(c2s(0x7fff) + c2s(b.ALIVE_REQUEST))
        await asyncio.wait_for(row['task'], 2)
        self.assertEqual(self.broker.failure_code, 'GAME_OPCODE_UNBOUND')
        self.assertTrue(writer.closed)
        self.assertTrue(writer.writes.empty())

    async def test_first_stream_game_request_drops_without_advancing_bootstrap(self):
        reader, writer, row = await self.connect()
        reader.feed_data(c2s(0x7fff))
        for _ in range(20):
            if getattr(self.broker, '_world_dropped_requests', 0):
                break
            await asyncio.sleep(0)
        self.assertFalse(self.broker.failure.is_set(), self.broker.failure_code)
        self.assertEqual((row['policy_row'].rx_boot, row['policy_row'].tx_boot,
                          row['policy_row'].stage), (2, 3, 0))
        self.assertEqual(self.broker._world_handler_errors, ['GAME_OPCODE_UNBOUND@0x7fff'])

    async def test_bad_bootstrap_sequence_remains_fatal(self):
        reader, writer = asyncio.StreamReader(), MemoryWriter(41000)
        self.broker._accept(12000, reader, writer)
        row = self.broker._claims[12000][-1]
        self.rows.append((reader, writer, row))
        self.assertEqual(await writer.response(), b.KEY12)
        reader.feed_data(c2s(0x7fff))
        await asyncio.wait_for(row['task'], 2)
        self.assertEqual(self.broker.failure_code, 'BOOTSTRAP_REQUEST_SEQUENCE')
        self.assertTrue(writer.closed)

    async def test_known_game_extension_before_bootstrap_remains_fatal(self):
        reader, writer = asyncio.StreamReader(), MemoryWriter(41000)
        self.broker._accept(12000, reader, writer)
        row = self.broker._claims[12000][-1]
        self.rows.append((reader, writer, row))
        self.assertEqual(await writer.response(), b.KEY12)
        reader.feed_data(c2s(b.ALIVE_REQUEST))
        await asyncio.wait_for(row['task'], 2)
        self.assertEqual(self.broker.failure_code, 'GAME_OPCODE_UNBOUND')
        self.assertTrue(writer.closed)

    async def test_refused_opcode_preserves_rate_owner_size_and_drain_checks(self):
        _, writer, row = await self.selected()
        sample = await self.broker._sample(row)
        policy, state = self.broker.policy, row['policy_row']
        now = time.monotonic_ns()
        for size in (9, policy.MAX_FRAME + 1):
            with self.assertRaisesRegex(ValueError, 'CLIENT_FRAME_BOUND'):
                policy.received_frame(writer, sample, 0x7fff, size, now)
        state.drain_started_ns = now
        with self.assertRaisesRegex(ValueError, 'DISPATCH_PAUSED_UNTIL_DRAIN'):
            policy.received_frame(writer, sample, 0x7fff, 10, now)
        state.drain_started_ns = None
        bad_sample = b.OwnerSample(object(), policy.handle, policy.job, sample.peer,
                                  sample.observed_ns, True, True)
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_OWNER_REQUIRED'):
            policy.received_frame(writer, bad_sample, 0x7fff, 10, now)
        state.rx_frames.tokens = 0
        state.rx_frames.now = now
        with self.assertRaisesRegex(ValueError, 'RATE_BOUND'):
            policy.received_frame(writer, sample, 0x7fff, 10, now)


if __name__ == '__main__':
    unittest.main()
