"""Targeted loopback fixtures only. No game, native owner or preserved secret."""
import asyncio
import socket
import struct
import time
import tempfile
import types
import unittest
from unittest import mock
import uuid
from pathlib import Path

from tools.local_original_session import broker as b
from tools.local_original_session import movement as m
from tools.local_original_session import test_ports
from tools.local_entry_server.cli import load_plan
from tools.local_entry_server.counts import CountsSession
from tools.local_entry_server.server import Session, MetadataLog
from tools.local_entry_server import protobuf as pb
from tools.local_own_login_request.codec import LocalLoginRequest


def c2s(opcode, payload=b'', sequence=1):
    size = ((10 + len(payload) + 1) & ~3) + 2
    return struct.pack('<HIHH', size, sequence, opcode, len(payload)) + payload + bytes(size - 10 - len(payload))


def version_request():
    return pb.encode_message([pb.encode_uint32(1, 52), pb.encode_uint32(2, 949),
                              pb.encode_uint32(3, 1), pb.encode_uint32(4, 26092901)])


class FixtureConversation(CountsSession):
    """Production parser/state; synthetic VERSION has no real resource material."""
    def __init__(self, cid, sink):
        super().__init__(load_plan(), Session(cid, 'reviewed_counts'), MetadataLog(sink=sink))

    async def received(self, frame):
        response = await super().received(frame)
        if frame.opcode == 0x4e34:
            return (bytearray(struct.pack('<HH', 76, 0x4e35) + bytes(72)),)
        return response


async def response(reader):
    header = await asyncio.wait_for(reader.readexactly(2), 2)
    size = int.from_bytes(header, 'little')
    return header + await asyncio.wait_for(reader.readexactly(size - 2), 2)


def reserve():
    result = {}
    try:
        for port in (12000, 14030):
            sock = socket.socket()
            result[port] = sock
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(('127.0.0.1', test_ports.port(port)))
            sock.listen(1)
        return result
    except BaseException:
        for sock in result.values():
            sock.close()
        raise


async def connected_motion_setup(self):
    """Existing connected motion flow with a fully initialized, unstarted broker."""
    from tools.local_original_session import npc_motion as motion
    from tools.local_original_session.npc_tests import spawn
    self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
    self.edge_result = True
    self.edge_mutation = None
    self.edges = []

    async def npc_edge(*edge):
        self.edges.append(edge)
        if self.edge_mutation:
            self.edge_mutation()
        return self.edge_result

    self.producer = b.PersistentBroker(sockets={12000: object(), 14030: object()},
        retained_owner=object(), owner_handle=object(), owner_job=object(),
        owner_guard=lambda _: True, owner_liveness_guard=lambda: True, source_guard=lambda: None,
        conversation_factory=FixtureConversation, expected_uuid=str(uuid.uuid4()),
        store_path=Path(self.temp.name) / 'characters.json', npc_spawns=(spawn(),),
        npc_motion_interval_ns=100, npc_edge_passability=npc_edge,
        npc_motion_policy=motion.LOCAL_PRE_STEP)
    self.realm, self.policy = self.producer.realm, self.producer.policy
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
    self.producer._claims = {12000: [], 14030: [self.row]}
    async def owned_sample(_):
        return sample(peer)
    self.producer._sample = owned_sample
    await self.producer._send(self.writer, self.row, frames, game=True)
    self.writer.write.reset_mock(); self.writer.drain.reset_mock()
    self.mover = self.realm.npc_mover(self.writer)
    self.initial = self.mover.state
    self.x, self.y = b.movement.authority.unpack_grid(self.initial.packed)


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.uuid = str(uuid.uuid4())
        self.owners = []
        self.owner_allowed = True
        self.liveness_calls = 0
        self.source_allowed = True
        self.accepts, self.releases = [], []

        async def owner(peer):
            self.owners.append((peer['connection_id'], peer['client_port']))
            return self.owner_allowed

        def guard():
            b.need(self.source_allowed, 'FIXTURE_SOURCE_CHANGED')

        def live():
            self.liveness_calls += 1
            return True

        self.broker = b.PersistentBroker(sockets=reserve(), listener_ports=test_ports.listener_ports(), retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=owner,
            owner_liveness_guard=live,
            source_guard=guard, conversation_factory=FixtureConversation,
            expected_uuid=self.uuid, store_path=Path(self.temp.name) / 'characters.json',
            on_accept=self.accepts.append, on_release=self.releases.append)
        self.clients = []
        await self.broker.start()

    async def asyncTearDown(self):
        await self.broker.close()
        for _, writer in self.clients:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        self.temp.cleanup()

    async def connect(self, port=12000):
        reader, writer = await asyncio.open_connection('127.0.0.1', test_ports.port(port))
        self.clients.append((reader, writer))
        self.assertEqual(await response(reader), b.KEY12)
        return reader, writer

    async def bootstrap(self, port=12000):
        reader, writer = await self.connect(port)
        writer.write(c2s(0x4e34, version_request()))
        await writer.drain()
        self.assertEqual(len(await response(reader)), 76)
        writer.write(c2s(0x4f3d))
        await writer.drain()
        self.assertEqual(await response(reader), b.EMPTY_COUNTS)
        return reader, writer

    async def first_closed(self, port=12000):
        _, writer = await self.bootstrap(port)
        writer.close()
        await writer.wait_closed()
        for _ in range(100):
            if self.broker._claims[port][0]['promotable']:
                return
            await asyncio.sleep(.005)
        self.fail('bootstrap predecessor not closed and joined')

    async def active_game(self):
        await self.first_closed()
        reader, writer = await self.bootstrap()
        payload = LocalLoginRequest(0x0100007f, 'standalone.local', self.uuid).payload()
        writer.write(c2s(0x263, payload))
        await writer.drain()
        self.assertEqual(await response(reader), b.ack.ACK_FRAME)
        self.assertEqual(int.from_bytes((await response(reader))[2:4], 'little'), 0x4e21)
        return reader, writer

    async def test_complete_login_create_select_world_and_shutdown(self):
        reader, writer = await self.active_game()
        fields = [pb.encode_bytes(1, b'SoloKnight')]
        fields += [pb.encode_uint32(n, value) for n, value in
                   ((2, 0), (3, 0), (4, 13), (5, 13), (6, 13), (7, 13), (8, 13), (9, 13))]
        writer.write(c2s(0x4e24, pb.encode_message(fields)))
        await writer.drain()
        self.assertEqual(await response(reader), b.ack.realm.create_ack(0))
        self.assertEqual(int.from_bytes((await response(reader))[2:4], 'little'), 0x4e21)
        self.assertEqual(int.from_bytes((await response(reader))[2:4], 'little'), 0x4e22)
        payload = pb.encode_message([pb.encode_bytes(1, b'SoloKnight'), pb.encode_uint32(2, 0),
                                     pb.encode_uint32(3, 0)])
        writer.write(c2s(0x4e28, payload))
        await writer.drain()
        replies = tuple([await response(reader) for _ in range(4)])
        self.assertEqual(replies, (b.ack.ENTER_ACK_FRAME, self.broker.realm.map_frame,
                                  self.broker.realm.self_frame, self.broker.realm.actor_frame))
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        self.assertEqual(result['state'], 'CLOSED')
        self.assertEqual(result['active_tasks'], 0)
        self.assertEqual(result['registry_sessions'], 0)
        self.assertEqual(self.releases, [1, 3])
        self.assertTrue(all(sock.fileno() == -1 for sock in self.broker.sockets.values()))
        self.assertEqual(self.broker.realm.store.select('SoloKnight')[0], 1)
        self.assertGreater(len(self.owners), 12)

    async def test_active_idle_past_old_total_deadline_and_bounded_ring(self):
        _, writer = await self.active_game()
        original_time = b.time
        offset = 121_000_000_000
        try:
            b.time = types.SimpleNamespace(monotonic_ns=lambda: original_time.monotonic_ns() + offset)
            await asyncio.sleep(.25)
            self.assertFalse(self.broker.failure.is_set())
            self.assertFalse(writer.is_closing())
            self.assertEqual(len(self.broker._tasks), 1)
            # Ring overflow is metadata only; no packet route or replay fabricated.
            for _ in range(400):
                self.broker.policy._emit('rx', 12000, 0x267, 10)
            self.assertEqual(len(self.broker.report()['ring']), 256)
            self.assertGreater(self.broker.report()['dropped_events'], 0)
        finally:
            b.time = original_time
        # Restore policy clock before real-time close (no further IO check).
        await self.broker.close()

    async def test_unknown_game_opcode_refused_without_echo(self):
        reader, writer = await self.active_game()
        writer.write(c2s(0x4e2d))
        await writer.drain()
        await asyncio.wait_for(self.broker.failure.wait(), 2)
        self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        self.assertTrue(result['connections'][-1]['failed'])

    async def selected_game(self):
        self.broker.realm.store.create(b.ack.realm.Creation('SoloKnight', 0, 0, (13,) * 6))
        reader, writer = await self.active_game()
        self.assertEqual(int.from_bytes((await response(reader))[2:4], 'little'), 0x4e22)
        request = pb.encode_message([pb.encode_bytes(1, b'SoloKnight'), pb.encode_uint32(2, 0),
                                     pb.encode_uint32(3, 0)])
        writer.write(c2s(0x4e28, request))
        await writer.drain()
        frames = tuple([await response(reader) for _ in range(4)])
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames],
                         [0x4e29, 0x4e95, 0x4e38, 0x4e96])
        return reader, writer, frames

    def selected_service(self):
        row = self.broker._claims[12000][-1]
        return row, self.broker.realm.service(row['writer'])

    @staticmethod
    def move_payload(position, direction=2):
        return pb.encode_message([pb.encode_uint32(1, position.packed), pb.encode_uint32(2, direction)])

    async def test_selected_unknown_move_corrects_current_without_killing_session(self):
        reader, writer, _ = await self.selected_game()
        row, service = self.selected_service()
        initial = service.snapshot()
        writer.write(c2s(0x4e2b, self.move_payload(initial)))
        await writer.drain()
        self.assertEqual(await response(reader), m.correction_frame(initial))
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        self.assertEqual(service.snapshot(), initial)
        self.assertEqual(service.last_result['reason'], 'EDGE_UNKNOWN')
        self.assertFalse(self.broker.realm.positions.path.exists())
        # The new S2C allowance still enforces literal current correction bytes.
        incorrect = m.correction_frame(m.Position(1, 'SoloKnight', 0, initial.word0 + 1, initial.word1))
        with self.assertRaisesRegex(ValueError, 'EXACT_CURRENT_MOVEMENT_CORRECTION_REQUIRED'):
            self.broker.realm.validate_reply(incorrect, writer=row['writer'])

    async def test_selected_writer_loss_removes_movement_registry(self):
        await self.selected_game()
        _, service = self.selected_service()
        self.owner_allowed = False
        await asyncio.wait_for(self.broker.failure.wait(), 2)
        report = await self.broker.close()
        self.assertTrue(report['cleanup_complete'])
        self.assertEqual(report['movement']['active_services'], 0)
        self.assertEqual(self.broker.realm._world_frames, {})
        self.assertEqual(service.committed, 0)
        self.assertTrue(report['movement']['sessions'][0]['closed'])

    async def test_selected_world_reloads_saved_grid_in_actor_field1(self):
        packed = self.broker.realm._actor_fields[1]
        word0, word1 = m.authority.unpack_grid(packed)
        initial = m.Position(1, 'SoloKnight', 0, word0, word1)
        restored = m.Position(1, 'SoloKnight', 0, word0 + 2, word1 - 1)
        self.broker.realm.positions.commit(initial, restored)
        _, _, frames = await self.selected_game()
        row, service = self.selected_service()
        self.assertEqual(service.snapshot(), restored)
        actor = b.session.world.decode_payload(0x4e96, frames[3][4:-2])
        self_info = b.session.world.decode_payload(0x4e38, frames[2][4:-2])
        self.assertEqual(actor[1], restored.packed)
        self.assertEqual(actor[2], self_info[1])
        self.broker.realm.validate_reply(frames[3], writer=row['writer'])
        with self.assertRaisesRegex(ValueError, 'EXACT_LOCAL_WORLD_REQUIRED'):
            self.broker.realm.validate_reply(self.broker.realm.actor_frame, writer=row['writer'])

    async def test_selected_save_failure_is_fatal_and_closes_connection(self):
        self.broker.realm.edge_passability = lambda *_: True
        reader, writer, _ = await self.selected_game()
        _, service = self.selected_service()
        initial = service.snapshot()
        with mock.patch.object(m.os, 'fsync', side_effect=OSError('fixture fsync failure')):
            writer.write(c2s(0x4e2b, self.move_payload(initial)))
            await writer.drain()
            await asyncio.wait_for(self.broker.failure.wait(), 2)
        self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        report = await self.broker.close()
        self.assertEqual(report['failure_code'], 'POSITION_SAVE_FAILED')
        self.assertEqual(report['movement']['active_services'], 0)
        self.assertTrue(report['movement']['sessions'][0]['fatal'])
        self.assertEqual(service.snapshot(), initial)
        self.assertFalse(self.broker.realm.positions.path.exists())

    async def test_owner_loss_during_idle_stops_and_joins(self):
        await self.active_game()
        self.owner_allowed = False
        await asyncio.wait_for(self.broker.failure.wait(), 2)
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['active_tasks'], 0)

    async def test_eof_without_live_tcp_tuple_uses_only_retained_liveness(self):
        _, writer = await self.bootstrap()
        # The client leaves ESTABLISHED before the already admitted stream's
        # reader returns EOF. It is still the same living retained process.
        self.owner_allowed = False
        writer.close()
        await writer.wait_closed()
        for _ in range(100):
            if self.broker._claims[12000][0]['joined']:
                break
            await asyncio.sleep(.005)
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        self.assertTrue(self.broker._claims[12000][0]['promotable'])
        self.assertEqual(self.liveness_calls, 1)
        # EOF promotion grants no future packet admission under a missing tuple.
        reader, _ = await self.connect()
        await asyncio.wait_for(self.broker.failure.wait(), 2)
        self.assertEqual(self.broker.failure_code, 'CURRENT_OWNER_REQUIRED')
        self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'])

    async def test_overlapping_connection_no_queue(self):
        await self.connect()
        reader, writer = await asyncio.open_connection('127.0.0.1', test_ports.port(12000))
        self.clients.append((reader, writer))
        try:
            self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        except ConnectionResetError:
            pass
        self.assertEqual(self.broker.report()['rejected_connections'], 1)
        self.assertLessEqual(len(self.broker._tasks), 1)

    async def test_third_connection_and_tuple_reconnect_not_promoted(self):
        await self.first_closed()
        _, writer = await self.bootstrap()
        writer.close()
        await writer.wait_closed()
        for _ in range(100):
            if self.broker._claims[12000][-1]['joined']:
                break
            await asyncio.sleep(.005)
        reader, writer = await asyncio.open_connection('127.0.0.1', test_ports.port(12000))
        self.clients.append((reader, writer))
        try:
            self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        except ConnectionResetError:
            pass
        self.assertEqual(len(self.broker._claims[12000]), 2)
        self.assertEqual(self.broker.report()['rejected_connections'], 1)

    async def test_release_failure_still_closes_writer_and_reports_unknown(self):
        await self.bootstrap()
        def failed_release(_):
            raise ValueError('FIXTURE_RESOURCE_RELEASE_FAILED')
        self.broker.on_release = failed_release
        result = await self.broker.close()
        self.assertFalse(result['cleanup_complete'])
        self.assertEqual(result['state'], 'CLOSING')
        self.assertEqual(result['failure_code'], 'FIXTURE_RESOURCE_RELEASE_FAILED')
        self.assertEqual(result['active_tasks'], 0)
        self.assertTrue(result['connections'][0]['positive_close'])

    async def test_full_roster_five_replies_and_no_second_login(self):
        store = self.broker.realm.store
        for name in ('SoloKnight', 'Second', 'Third'):
            store.create(b.ack.realm.Creation(name, 0, 0, (13,) * 6))
        await self.first_closed()
        reader, writer = await self.bootstrap()
        payload = LocalLoginRequest(0x0100007f, 'standalone.local', self.uuid).payload()
        writer.write(c2s(0x263, payload))
        await writer.drain()
        replies = [await response(reader) for _ in range(5)]
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in replies],
                         [0x264, 0x4e21, 0x4e22, 0x4e22, 0x4e22])
        writer.write(c2s(0x263, payload))
        await writer.drain()
        await asyncio.wait_for(self.broker.failure.wait(), 2)
        self.assertEqual(self.broker.failure_code, 'OWN_LOGIN_ORDER_OR_REPLAY')

    async def test_two_endpoints_and_cancelled_close_finishes(self):
        await self.first_closed(12000)
        await self.first_closed(14030)
        await self.bootstrap(12000)
        await self.bootstrap(14030)
        task = asyncio.create_task(self.broker.close())
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['active_tasks'], 0)
        self.assertEqual(sorted(self.releases), [1, 2, 3, 4])


class MovementCounterMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_service_events_reach_status_and_missing_stays_unknown(self):
        from tools.local_original_session.observe import public_movement
        async def admitted(*_): return True
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'characters.json'
            profile.write_text('{}', encoding='utf-8')
            selected = m.Position(1, 'SoloKnight', 0, 32571, 32951)
            service = m.MovementService(selected, connection=object(), owner_guard=admitted,
                edge_passability=admitted, store=m.PositionStore(profile))
            payload = pb.encode_message([pb.encode_uint32(1, selected.packed), pb.encode_uint32(2, 2)])
            self.assertTrue((await service.handle_CS4E2B(payload)).accepted)
            self.assertEqual((await service.handle_CS4E2B(payload)).reason, 'STALE_START')
            row = b.LocalRealm._movement_metadata((object(), service, 4))
            result = public_movement(dict(committed=1, active_services=1, sessions=[row]))['sessions'][0]
            self.assertEqual((result['committed'], result['requests_received'], result['corrections_prepared']),
                             (1, 2, 1))
            del service.requests_received, service.corrections_prepared
            row = b.LocalRealm._movement_metadata((object(), service, 4))
            self.assertIsNone(row['requests_received'])
            self.assertIsNone(row['corrections_prepared'])


class EdgeMetadataTests(unittest.TestCase):
    def test_own_self_success_is_observable_without_exposing_adapter_fields(self):
        from tools.local_original_session import edge
        realm = b.LocalRealm.__new__(b.LocalRealm)
        realm.edge_passability = types.SimpleNamespace(last_result=dict(
            status='CLEAR_OWN_SELF_SUBSET', reason=None, typed_bytes_requested=30884,
            own_self_pointer=0x1234, candidates=[0x1234]))
        self.assertEqual(realm.edge_report(), dict(status='CLEAR_OWN_SELF_SUBSET',
            reason=None, typed_bytes_requested=30884))
        for requested in (32814, edge.LIMIT):
            realm.edge_passability.last_result['typed_bytes_requested'] = requested
            self.assertEqual(realm.edge_report(), dict(status='CLEAR_OWN_SELF_SUBSET',
                reason=None, typed_bytes_requested=requested))
        realm.edge_passability.last_result.update(status='UNRECOGNIZED_CLEAR',
            reason='unbounded/private/path', typed_bytes_requested=edge.LIMIT + 1)
        self.assertEqual(realm.edge_report(), dict(status='UNKNOWN',
            reason='EDGE_READ_FAILED', typed_bytes_requested=None))


class OwnerFailureMetadataTests(unittest.IsolatedAsyncioTestCase):
    def bootstrap_poll_fixture(self):
        broker, writer, row = self.fixture()
        now = time.monotonic_ns()
        peer = b.Peer(14030, 52001, now)
        broker.policy.rows[14030].clear()
        def sample():
            return b.OwnerSample(broker.policy.owner, broker.policy.handle, broker.policy.job,
                                peer, time.monotonic_ns(), True, True)
        connection = broker.policy.admit(writer, peer, sample(), time.monotonic_ns(), key_already_drained=True)
        for opcode, size, reply, reply_size in ((0x4e34, 158, 0x4e35, 76), (0x4f3d, 10, 0x4f3e, 6)):
            broker.policy.received_frame(writer, sample(), opcode, size, time.monotonic_ns())
            broker.policy.begin_write(writer, sample(), reply, reply_size, 0, time.monotonic_ns())
            broker.policy.drained(writer, sample(), 0, time.monotonic_ns())
        row.update(policy_row=connection, failed=False, joined=False, eof=False,
                   operation_lock=asyncio.Lock())
        row['peer'].update(endpoint_port=14030, accepted_monotonic_ns=now)
        broker._claims = {12000: [], 14030: [row]}
        broker.failure, broker._closing = asyncio.Event(), False
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        broker.realm = b.LocalRealm(str(uuid.uuid4()), Path(directory.name) / 'characters.json')
        broker.owner_liveness_guard = mock.Mock(return_value=True)
        broker.source_guard = mock.Mock()
        return broker, writer, row

    async def test_first_bootstrap_empty_read_finishes_after_checkpoint_refusal(self):
        broker, writer, row = self.bootstrap_poll_fixture()
        read, lock = row['_read_task'], row['operation_lock']
        original = broker._checkpoint
        broker.owner_guard = lambda _: False
        async def checkpoint(writer, current):
            try:
                return await original(writer, current)
            except ValueError as error:
                self.assertEqual(error.args, ('CURRENT_OWNER_REQUIRED',))
                self.assertFalse(read.done())
                asyncio.get_running_loop().call_soon(read.set_result, b'')
                raise
        broker._checkpoint = checkpoint  # Original owner/policy path executes; only EOF scheduling differs.
        async with lock:
            self.assertTrue(await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                decoder_empty=row['_decoder'].buffered_bytes == 0,
                operation_lock=lock))
        self.assertTrue(row['eof'] and row['boot_complete'] and row['policy_row'].eof)
        self.assertFalse(row['failed'] or broker.failure.is_set())
        self.assertEqual(broker.policy.log[-1], ('eof', 14030, 0, 0))

    async def test_first_bootstrap_actual_eof_completes_during_owner_poll_uses_existing_eof(self):
        broker, writer, row = self.bootstrap_poll_fixture()
        read = row['_read_task']
        async def departing(_):
            self.assertFalse(read.done())
            read.set_result(b'')
            await asyncio.sleep(0)
            return False
        broker.owner_guard = departing
        async with row['operation_lock']:
            self.assertTrue(await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                decoder_empty=row['_decoder'].buffered_bytes == 0,
                operation_lock=row['operation_lock']))
        self.assertTrue(row['eof'] and row['boot_complete'] and row['policy_row'].eof)
        self.assertFalse(row['failed'] or broker.failure.is_set())
        broker.owner_liveness_guard.assert_called_once_with()
        broker.source_guard.assert_called_once_with()
        self.assertEqual(broker.policy.log[-1], ('eof', 14030, 0, 0))
        # Completing this old stream never creates a live tuple for new traffic.
        broker.owner_guard = lambda _: False
        with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$'):
            await broker._sample(row)

    async def test_bootstrap_poll_eof_never_accepts_pending_data_error_other_stage_or_changed_binding(self):
        for mode in ('pending', 'payload', 'cancel', 'error', 'stage1', 'partial', 'incomplete', 'no_caller_lock',
                     'claim', 'policyrow', 'readtask', 'lock', 'liveness', 'source', 'already_done'):
            broker, writer, row = self.bootstrap_poll_fixture()
            read, lock = row['_read_task'], row['operation_lock']
            replacement_lock = None
            if mode == 'already_done': read.set_result(b'')
            if mode == 'partial': row['_decoder'].feed(b'\x0a')
            async def departing(_):
                nonlocal replacement_lock
                if mode not in ('pending', 'already_done'):
                    if mode == 'payload': read.set_result(b'payload still needs its live checkpoint')
                    elif mode == 'cancel': read.cancel()
                    elif mode == 'error': read.set_exception(OSError('READ_ERROR'))
                    else: read.set_result(b'')
                if mode == 'stage1': row['policy_row'].stage = 1
                elif mode == 'incomplete': row['policy_row'].tx_boot = 2
                elif mode == 'claim': broker._claims[14030] = [dict(row)]
                elif mode == 'policyrow': row['policy_row'] = types.SimpleNamespace(writer=writer, rx_boot=2, tx_boot=3)
                elif mode == 'readtask':
                    row['_read_task'] = asyncio.get_running_loop().create_future()
                    row['_read_task'].set_result(b'')
                elif mode == 'lock':
                    replacement_lock = asyncio.Lock(); await replacement_lock.acquire()
                    row['operation_lock'] = replacement_lock
                elif mode == 'liveness': broker.owner_liveness_guard.return_value = False
                elif mode == 'source': broker.source_guard.side_effect = ValueError('FIXTURE_SOURCE_CHANGED')
                await asyncio.sleep(0)
                return False
            broker.owner_guard = departing
            try:
                async with lock:
                    with self.subTest(mode=mode), self.assertRaises(ValueError):
                        await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                            decoder_empty=row['_decoder'].buffered_bytes == 0,
                            operation_lock=None if mode == 'no_caller_lock' else lock)
                self.assertFalse(row['eof'])
                self.assertFalse(any(event[0] == 'eof' for event in broker.policy.log))
                if mode not in ('pending', 'liveness', 'source'):
                    broker.owner_liveness_guard.assert_not_called()
                self.assertFalse(broker.failure.is_set())  # Caller still owns original failure cleanup.
            finally:
                if replacement_lock is not None: replacement_lock.release()

    async def test_bootstrap_poll_uses_caller_lock_captured_before_acquire_wait(self):
        broker, writer, row = self.bootstrap_poll_fixture()
        old, replacement = row['operation_lock'], asyncio.Lock()
        await old.acquire(); await replacement.acquire()
        read = row['_read_task']
        async def departing(_):
            read.set_result(b''); await asyncio.sleep(0)
            return False
        broker.owner_guard = departing
        async def caller():
            async with old:
                return await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                    decoder_empty=row['_decoder'].buffered_bytes == 0,
                    operation_lock=old)
        task = asyncio.create_task(caller())
        try:
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            row['operation_lock'] = replacement
            old.release()
            with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$'): await task
            self.assertFalse(row['eof'] or row['policy_row'].eof)
            broker.owner_liveness_guard.assert_not_called()
        finally:
            if old.locked(): old.release()
            replacement.release()
            if not task.done():
                task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task

    async def test_late_bootstrap_read_refuses_data_errors_timeout_partial_and_changed_bindings(self):
        modes = ('payload', 'bytearray', 'error', 'read_cancel', 'timeout', 'partial', 'stage1', 'incomplete',
                 'claim', 'policyrow', 'readtask', 'lock', 'peer', 'policypeer', 'owner', 'handle', 'job',
                 'source_guard', 'liveness_guard', 'owner_guard', 'phase', 'close', 'policyclose',
                 'pendingwrite', 'buffered', 'source', 'liveness', 'initial_incomplete')
        for mode in modes:
            broker, writer, row = self.bootstrap_poll_fixture()
            read, lock = row['_read_task'], row['operation_lock']
            original = broker._checkpoint
            broker.owner_guard = lambda _: False
            if mode == 'timeout': broker.policy.CLOSE_NS = 1_000_000
            if mode == 'partial': row['policy_row'].partial_started_ns = time.monotonic_ns()
            if mode == 'source': broker.source_guard.side_effect = ValueError('FIXTURE_SOURCE_CHANGED')
            if mode == 'liveness': broker.owner_liveness_guard.return_value = False
            if mode == 'initial_incomplete': row['policy_row'].tx_boot = 2
            replacement = None
            def completed():
                nonlocal replacement
                if mode == 'payload': read.set_result(b'not EOF')
                elif mode == 'bytearray': read.set_result(bytearray())
                elif mode == 'error': read.set_exception(OSError('fixture read error'))
                elif mode == 'read_cancel': read.cancel()
                elif mode != 'timeout': read.set_result(b'')
                if mode == 'stage1': row['policy_row'].stage = 1
                elif mode == 'incomplete': row['policy_row'].tx_boot = 2
                elif mode == 'initial_incomplete': row['policy_row'].tx_boot = 3
                elif mode == 'claim': broker._claims[14030] = [dict(row)]
                elif mode == 'policyrow': row['policy_row'] = types.SimpleNamespace(writer=writer)
                elif mode == 'readtask': row['_read_task'] = asyncio.get_running_loop().create_future()
                elif mode == 'lock':
                    replacement = asyncio.Lock(); row['operation_lock'] = replacement
                elif mode == 'peer': row['peer'] = dict(row['peer'])
                elif mode == 'policypeer': row['policy_row'].peer = b.Peer(14030, 52001, 10)
                elif mode == 'owner': broker.policy.owner = object()
                elif mode == 'handle': broker.policy.handle = object()
                elif mode == 'job': broker.policy.job = object()
                elif mode == 'source_guard': broker.source_guard = lambda: None
                elif mode == 'liveness_guard': broker.owner_liveness_guard = lambda: True
                elif mode == 'owner_guard': broker.owner_guard = lambda _: False
                elif mode == 'phase': row['await_phase'] = 'CHANGED'
                elif mode == 'close': broker._closing = True
                elif mode == 'policyclose': broker.policy.state = 'CLOSING'
                elif mode == 'pendingwrite': row['policy_row'].pending_opcode = 0x4e35
                elif mode == 'buffered': row['policy_row'].buffered = 1
            async def checkpoint(writer, current):
                try: return await original(writer, current)
                except ValueError:
                    asyncio.get_running_loop().call_soon(completed)
                    raise
            broker._checkpoint = checkpoint
            try:
                async with lock:
                    with self.subTest(mode=mode), self.assertRaises((ValueError, OSError, asyncio.CancelledError)):
                        await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                            decoder_empty=row['_decoder'].buffered_bytes == 0, operation_lock=lock)
                self.assertFalse(row['eof'])
                self.assertFalse(any(event[0] == 'eof' for event in broker.policy.log))
            finally:
                await asyncio.sleep(0)  # Flush this case's deferred read before changing loop fixtures.
                if not read.done(): read.cancel()
                changed_read = row.get('_read_task')
                if changed_read is not read and not changed_read.done(): changed_read.cancel()

    async def test_late_bootstrap_complete_eof_await_mutation_and_sync_cancel_precede_eof_sideeffect(self):
        for mode in ('source', 'cancel'):
            broker, writer, row = self.bootstrap_poll_fixture()
            read, lock = row['_read_task'], row['operation_lock']
            original = broker._checkpoint
            broker.owner_guard = lambda _: False
            calls = [0]
            async def alive():
                calls[0] += 1
                if calls[0] == 2:  # Existing _complete_eof's own retained-owner await.
                    if mode == 'owner': broker.policy.owner = object()
                    elif mode == 'claim': broker._claims[14030] = [dict(row)]
                    elif mode == 'source': broker.source_guard.side_effect = ValueError('FIXTURE_SOURCE_CHANGED')
                await asyncio.sleep(0)
                return True
            broker.owner_liveness_guard = alive
            async def checkpoint(writer, current):
                try: return await original(writer, current)
                except ValueError:
                    asyncio.get_running_loop().call_soon(read.set_result, b'')
                    raise
            broker._checkpoint = checkpoint
            def source():
                if mode == 'cancel' and calls[0] == 2:
                    asyncio.current_task().cancel('fixture synchronous source callback cancellation')
            if mode == 'cancel': broker.source_guard = source
            async def poll():
                async with lock:
                    return await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                        decoder_empty=row['_decoder'].buffered_bytes == 0, operation_lock=lock)
            task = asyncio.create_task(poll())
            with self.subTest(mode=mode), self.assertRaises((ValueError, asyncio.CancelledError)):
                await task
            self.assertFalse(row['eof'] or row['policy_row'].eof)
            self.assertEqual(calls, [2])
            self.assertFalse(any(event[0] == 'eof' for event in broker.policy.log))

    async def drained_quit_poll_fixture(self):
        broker, prior, old = self.bootstrap_poll_fixture()
        broker.policy.eof_retained(prior, retained_alive=True, decoder_empty=True, now=time.monotonic_ns())
        broker.policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        writer = types.SimpleNamespace(transport=types.SimpleNamespace(get_write_buffer_size=lambda: 0),
            write=mock.Mock(), drain=mock.AsyncMock())
        now = time.monotonic_ns()
        peer = b.Peer(14030, 52002, now)
        sample = lambda: b.OwnerSample(broker.policy.owner, broker.policy.handle, broker.policy.job,
            peer, time.monotonic_ns(), True, True)
        connection = broker.policy.admit(writer, peer, sample(), time.monotonic_ns(), key_already_drained=True)
        for op, size, reply, reply_size in ((0x4e34, 158, 0x4e35, 76), (0x4f3d, 10, 0x4f3e, 6)):
            broker.policy.received_frame(writer, sample(), op, size, time.monotonic_ns())
            broker.policy.begin_write(writer, sample(), reply, reply_size, 0, time.monotonic_ns())
            broker.policy.drained(writer, sample(), 0, time.monotonic_ns())
        read = asyncio.get_running_loop().create_future(); self.addCleanup(read.cancel)
        row = dict(writer=writer, policy_row=connection, failed=False, joined=False, eof=False,
            operation_lock=asyncio.Lock(), _read_task=read, peer=dict(endpoint_port=14030,
                server_port=14030, client_port=peer.client_port, accepted_monotonic_ns=now, connection_id=4))
        row['_decoder'] = b.ClientPlaintextDecoder(
            cipher_pointer='present_disabled', max_buffer=broker.policy.MAX_BUFFER)
        broker._claims[14030] = [row]
        broker.owner_guard = lambda _: True
        broker.owner_exit_proof = mock.Mock(side_effect=ValueError('NATIVE_STILL_ALIVE'))
        realm = broker.realm
        realm.store.create(b.ack.realm.Creation(realm.profile_name, 0, 0, (13,) * 6))
        game = realm.grant(writer, connection_id=4,
            movement_owner_guard=lambda w, _: broker._account_owner(w, row),
            account_owner_guard=lambda w: broker._account_owner(w, row))
        async def received(opcode, payload=b''):
            broker.policy.received_frame(writer, await broker._checkpoint(writer, row),
                opcode, 10 + len(payload), time.monotonic_ns())
            return await game.received(types.SimpleNamespace(opcode=opcode, payload=payload))
        await received(0x263, LocalLoginRequest(0, 'standalone.local', realm.expected_uuid).payload())
        await received(0x4e28, pb.encode_bytes(1, realm.profile_name.encode()) + b'\x10\0\x18\0')
        replies = await received(b.QUIT_REQUEST)
        await broker._send(writer, row, replies, game=True)
        self.assertEqual(writer.write.call_count, 1)
        self.assertEqual(writer.drain.await_count, 1)
        self.assertTrue(all(realm.quit_state(writer)[key] is True for key in
            ('request_verified', 'response_drain_returned', 'response_queue_empty', 'response_drained')))
        self.assertIs(broker.policy._quit_drained[id(writer)], writer)
        return broker, writer, row

    async def test_drained_quit_actual_empty_eof_during_owner_poll_keeps_retained_alive(self):
        broker, writer, row = await self.drained_quit_poll_fixture()
        read, lock = row['_read_task'], row['operation_lock']
        async def departing(_):
            self.assertFalse(read.done())
            read.set_result(b'')
            await asyncio.sleep(0)
            return False
        broker.owner_guard = departing
        before = tuple(broker.policy.log)
        async with lock:
            self.assertTrue(await broker._poll_checkpoint(writer, row, read,
                decoder=row['_decoder'], decoder_empty=row['_decoder'].buffered_bytes == 0, operation_lock=lock))
        self.assertTrue(row['eof'] and row['policy_row'].eof)
        self.assertFalse(row.get('quit_terminal_exit', False))
        broker.owner_exit_proof.assert_not_called()
        broker.owner_liveness_guard.assert_called_once_with()
        broker.source_guard.assert_called()
        self.assertEqual(tuple(broker.policy.log), before + (('eof', 14030, 0, 0),))
        self.assertEqual((writer.write.call_count, writer.drain.await_count), (1, 1))
        self.assertFalse(row['failed'] or broker.failure.is_set())
        broker.owner_guard = lambda _: False
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            await broker._sample(row)

    async def test_quit_poll_empty_eof_handoff_rejects_incomplete_or_changed_actual_binding(self):
        from dataclasses import replace
        from copy import copy
        modes = ('pending', 'payload', 'error', 'cancel_read', 'cancel_owner', 'source', 'liveness')
        for mode in modes:
            broker, writer, row = await self.drained_quit_poll_fixture()
            read, lock = row['_read_task'], row['operation_lock']
            replacement_lock = None
            if mode == 'already_done': read.set_result(b'')
            async def departing(_):
                nonlocal replacement_lock
                if mode not in ('pending', 'already_done'):
                    if mode == 'payload': read.set_result(b'not-eof')
                    elif mode == 'error': read.set_exception(OSError('FIXTURE_READ_ERROR'))
                    elif mode == 'cancel_read': read.cancel()
                    else: read.set_result(b'')
                state = broker.realm._quit[id(writer)]
                if mode == 'writer': row['writer'] = object()
                if mode == 'claim': broker._claims[14030] = [dict(row)]
                if mode == 'policyrow': row['policy_row'] = copy(row['policy_row'])
                if mode == 'readtask':
                    row['_read_task'] = asyncio.get_running_loop().create_future()
                    row['_read_task'].set_result(b'')
                if mode == 'lock':
                    replacement_lock = asyncio.Lock(); await replacement_lock.acquire()
                    row['operation_lock'] = replacement_lock
                if mode == 'peer': row['peer']['client_port'] += 1
                if mode == 'verified': state['request_verified'] = False
                if mode == 'drain_returned': state['response_drain_returned'] = False
                if mode == 'queue': state['response_queue_empty'] = False
                if mode == 'drained': state['response_drained'] = False
                if mode == 'policy_mark': broker.policy._quit_drained.clear()
                if mode == 'selection': broker.realm.registry.selected.clear()
                if mode == 'position':
                    service = broker.realm.service(writer)
                    service._position = replace(service.snapshot())
                if mode == 'registry': broker.realm.registry = copy(broker.realm.registry)
                if mode == 'quitstate': broker.realm._quit[id(writer)] = dict(state)
                if mode == 'source': broker.source_guard.side_effect = ValueError('FIXTURE_SOURCE_CHANGED')
                if mode == 'liveness': broker.owner_liveness_guard.return_value = False
                if mode == 'post_await_selection':
                    async def retained():
                        await asyncio.sleep(0)
                        broker.realm.registry.selected.clear()
                        return True
                    broker.owner_liveness_guard.side_effect = retained
                if mode == 'cancel_owner': asyncio.current_task().cancel()
                await asyncio.sleep(0)
                return False
            broker.owner_guard = departing
            async def poll():
                async with lock:
                    return await broker._poll_checkpoint(writer, row, read, decoder=row['_decoder'],
                        decoder_empty=row['_decoder'].buffered_bytes == 0,
                        operation_lock=None if mode == 'no_caller_lock' else lock)
            try:
                expected_error = {
                    'error': OSError,
                    'cancel_read': asyncio.CancelledError,
                    'cancel_owner': asyncio.CancelledError,
                }.get(mode, ValueError)
                with self.subTest(mode=mode), self.assertRaises(
                        expected_error):
                    await asyncio.create_task(poll())
                if mode != 'post_await_selection':
                    self.assertFalse(row['eof'] or row['policy_row'].eof)
                self.assertEqual((writer.write.call_count, writer.drain.await_count), (1, 1))
                self.assertFalse(broker.failure.is_set())  # Original caller owns failure cleanup.
                if read.done() and not read.cancelled(): read.exception()  # Join actual read errors too.
            finally:
                if replacement_lock is not None: replacement_lock.release()

    async def test_quit_empty_eof_handoff_source_callback_cancel_is_not_suppressed(self):
        broker, writer, row = await self.drained_quit_poll_fixture()
        read, lock = row['_read_task'], row['operation_lock']
        async def departing(_):
            read.set_result(b''); await asyncio.sleep(0)
            return False
        broker.owner_guard = departing
        broker.source_guard.side_effect = lambda: asyncio.current_task().cancel()
        async def poll():
            async with lock:
                return await broker._poll_checkpoint(writer, row, read,
                    decoder=row['_decoder'], decoder_empty=row['_decoder'].buffered_bytes == 0, operation_lock=lock)
        with self.assertRaises(asyncio.CancelledError): await asyncio.create_task(poll())
        self.assertEqual((writer.write.call_count, writer.drain.await_count), (1, 1))
        broker.owner_exit_proof.assert_not_called()
        self.assertFalse(row.get('quit_terminal_exit', False))


    def fixture(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        # The freshness cases below intentionally use the original 10ns epoch.
        with mock.patch.object(b.time, 'monotonic_ns', return_value=10):
            broker = b.PersistentBroker(sockets={12000: object(), 14030: object()},
                retained_owner=object(), owner_handle=object(), owner_job=object(),
                owner_guard=lambda peer: False, owner_liveness_guard=lambda: True, source_guard=lambda: None,
                conversation_factory=FixtureConversation, expected_uuid=str(uuid.uuid4()),
                store_path=Path(directory.name) / 'characters.json')
        writer = object()
        connection = types.SimpleNamespace(writer=writer, peer=b.Peer(14030, 52001, 10),
            positive_close=False, failed=False, rx_boot=2, tx_boot=3)
        broker.policy.rows[14030].append(connection)
        row = dict(writer=writer, policy_row=connection, await_phase='READ_POLL_CHECKPOINT',
            peer=dict(server_port=14030, client_port=52001, accepted_monotonic_ns=10, connection_id=2),
            _read_task=asyncio.get_running_loop().create_future())
        self.addCleanup(row['_read_task'].cancel)
        row['_decoder'] = b.ClientPlaintextDecoder(
            cipher_pointer='present_disabled', max_buffer=broker.policy.MAX_BUFFER)
        return broker, writer, row

    async def test_callback_false_preserves_original_exception_and_first_metadata(self):
        broker, writer, row = self.fixture()
        with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$'):
            await broker._checkpoint(writer, row)
        self.assertEqual(broker.owner_failure, dict(scope='CALLBACK_FALSE', connection_id=2,
            rx_boot=2, tx_boot=3, await_phase='READ_POLL_CHECKPOINT', read_task_done=False))
        first = dict(broker.owner_failure)
        row['await_phase'] = 'POST_DRAIN_OWNER'
        with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$'):
            await broker._sample(row)
        self.assertEqual(broker.owner_failure, first)

    async def test_policy_freshness_records_exact_call_age_and_original_refusal(self):
        broker, writer, row = self.fixture()
        row['_read_task'].set_result(b'')
        policy = broker.policy
        sample = b.OwnerSample(policy.owner, policy.handle, policy.job,
            row['policy_row'].peer, 20, True, True)
        now = 250_000_021
        original_owner, refusals = policy._owner, []
        def actual_owner(*args):
            try:
                return original_owner(*args)
            except ValueError as error:
                refusals.append(error)
                raise
        calls = (
            ('checkpoint', policy.checkpoint, (writer, sample, now), {}),
            ('begin_write', policy.begin_write, (writer, sample, b.ALIVE_RESPONSE, 6, 0, now), {}),
            ('drained', policy.drained, (writer, sample, 0, now), {}),
            ('received_chunk', policy.received_chunk, (writer, sample, 1, 0, now), {'decoded_frames': 0}),
            ('received_frame', policy.received_frame, (writer, sample, b.ALIVE_REQUEST, 10, now), {}),
        )
        with (mock.patch.object(policy, '_owner', side_effect=actual_owner),
              mock.patch.object(b.time, 'monotonic_ns', side_effect=AssertionError('EXTRA_CLOCK')) as clock,
              mock.patch.object(broker, 'owner_guard', side_effect=AssertionError('EXTRA_OWNER_QUERY')) as guard,
              mock.patch.object(broker, 'source_guard', side_effect=AssertionError('EXTRA_SOURCE_QUERY')) as source):
            for name, operation, args, kwargs in calls:
                with self.subTest(operation=name):
                    broker.owner_failure = None
                    with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$') as raised:
                        broker._policy_sample(row, operation, *args, **kwargs)
                    self.assertIs(raised.exception, refusals[-1])
                    self.assertEqual(broker.owner_failure, dict(scope='POLICY_FRESHNESS', connection_id=2,
                        rx_boot=2, tx_boot=3, await_phase='READ_POLL_CHECKPOINT', read_task_done=True,
                        policy_sample=dict(operation=name, observed_ns=20, now_ns=250_000_021,
                            fresh_ns=250_000_000, age_ns=250_000_001, peer_equal=True,
                            observed_ns_is_int=True, accepted_le_observed=True, observed_le_now=True,
                            age_within_freshness=False, exact_identity_and_tuple_is_true=True, alive_is_true=True)))
                    first = dict(broker.owner_failure)
                    with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$'):
                        broker._policy_sample(row, policy.checkpoint, writer, sample, now)
                    self.assertEqual(broker.owner_failure, first)
            clock.assert_not_called(); guard.assert_not_called(); source.assert_not_called()

    async def test_policy_freshness_admit_zero_unknown_and_diagnostic_failure_isolation(self):
        broker, writer, row = self.fixture()
        policy, peer = broker.policy, row['policy_row'].peer
        row['policy_row'] = None  # Admission has no existing policy connection.
        sample = b.OwnerSample(policy.owner, policy.handle, policy.job, peer, 0, True, True)
        with self.assertRaisesRegex(ValueError, '^CURRENT_OWNER_REQUIRED$'):
            broker._policy_sample(row, policy.admit, writer, peer, sample, 250_000_001,
                key_already_drained=True)
        diagnostic = broker.owner_failure['policy_sample']
        self.assertEqual(diagnostic, dict(operation='admit', observed_ns=0, now_ns=250_000_001,
            fresh_ns=250_000_000, age_ns=250_000_001, peer_equal=True,
            observed_ns_is_int=True, accepted_le_observed=False, observed_le_now=True,
            age_within_freshness=False, exact_identity_and_tuple_is_true=True, alive_is_true=True))
        self.assertIsNone(broker.owner_failure['rx_boot'])
        first = broker.owner_failure
        original = ValueError('CURRENT_OWNER_REQUIRED')
        unsupported = mock.Mock(side_effect=original)
        with self.assertRaises(ValueError) as raised:
            broker._policy_sample(row, unsupported)
        self.assertIs(raised.exception, original)
        self.assertIs(broker.owner_failure, first)
        broker.owner_failure = None
        with self.assertRaises(ValueError) as raised:
            broker._policy_sample(row, unsupported)
        self.assertIs(raised.exception, original)
        self.assertEqual(set(broker.owner_failure['policy_sample']), set(diagnostic))
        self.assertTrue(all(value is None for value in broker.owner_failure['policy_sample'].values()))
        broker.owner_failure = None
        with mock.patch.object(b.inspect, 'ismethod', side_effect=RuntimeError('DIAGNOSTIC_FAILED')):
            with self.assertRaises(ValueError) as raised:
                broker._policy_sample(row, unsupported)
        self.assertIs(raised.exception, original)
        self.assertEqual(broker.owner_failure, dict(scope='POLICY_FRESHNESS', connection_id=2,
            rx_boot=None, tx_boot=None, await_phase='READ_POLL_CHECKPOINT', read_task_done=False))


class WorldProfileTests(unittest.IsolatedAsyncioTestCase):
    """Pure DTO/route/tempstore only; never reserve or start a listener."""
    async def test_stored_character_selection_switches_identity_and_rejects_unknown_only(self):
        with tempfile.TemporaryDirectory() as directory:
            realm = b.LocalRealm(str(uuid.uuid4()), Path(directory) / 'characters.json')
            realm.store.create(b.ack.realm.Creation('SoloKnight', 1, 0, (18, 13, 16, 10, 10, 10)))
            realm.store.create(b.ack.realm.Creation('SoloMage', 3, 0, (8, 7, 16, 18, 8, 18)))
            writer = object()
            game = realm.grant(writer, movement_owner_guard=lambda *_: True)
            await game.received(types.SimpleNamespace(opcode=0x263,
                payload=LocalLoginRequest(0, 'standalone.local', realm.expected_uuid).payload()))
            async def select(name):
                return await game.received(types.SimpleNamespace(opcode=0x4e28,
                    payload=pb.encode_bytes(1, name.encode()) + b'\x10\0\x18\0'))
            before = (realm.profile_uid, realm.profile_name, realm._self_fields, realm._actor_fields)
            self.assertEqual(await select('NoSuchCharacter'), ())
            self.assertIsNone(game.selection)
            self.assertEqual(realm._movement, {})
            self.assertEqual(before, (realm.profile_uid, realm.profile_name,
                                     realm._self_fields, realm._actor_fields))
            frames = await select('SoloMage')
            self.assertEqual((realm.profile_uid, realm.profile_name), (2, 'SoloMage'))
            self.assertEqual(b.session.world.decode_payload(0x4e38, frames[2][4:-2])[1], 2)
            actor = b.session.world.decode_payload(0x4e96, frames[3][4:-2])
            self.assertEqual((actor[2], actor[9]), (2, 'SoloMage'))
            second_writer = object()
            second = realm.grant(second_writer, movement_owner_guard=lambda *_: True)
            second.list_request(source_kind='CS_CHAR_LIST_ENTER_REQ', payload=b'')
            self.assertEqual(await second.received(types.SimpleNamespace(opcode=0x4e28,
                payload=pb.encode_bytes(1, b'SoloKnight') + b'\x10\0\x18\0')), ())
            self.assertIsNone(second.selection)
            self.assertEqual(realm.profile_name, 'SoloMage')
            realm.close(writer)
            frames = await second.received(types.SimpleNamespace(opcode=0x4e28,
                payload=pb.encode_bytes(1, b'SoloKnight') + b'\x10\0\x18\0'))
            self.assertEqual((realm.profile_uid, realm.profile_name), (1, 'SoloKnight'))
            self.assertEqual(b.session.world.decode_payload(0x4e38, frames[2][4:-2])[1], 1)

    async def test_mage_first_status_uses_joint_growth_vitals_and_stored_appearance(self):
        from tools.local_original_session.world_companion import CompanionRecord
        from tools.local_original_session.world_progress import Progress
        with tempfile.TemporaryDirectory() as directory:
            realm = b.LocalRealm(str(uuid.uuid4()), Path(directory) / 'characters.json')
            realm.store.create(b.ack.realm.Creation('SoloKnight', 1, 0, (18, 13, 16, 10, 10, 10)))
            realm.store.create(b.ack.realm.Creation('SoloMage', 3, 0, (8, 7, 16, 18, 8, 18)))
            member = CompanionRecord(2, 1, 'development-fixture', level=5, exp=100,
                hp=17, max_hp=55, mp=9, max_mp=40)
            realm._world_companion_record = lambda uid: member if uid == 2 else None
            realm._world_progress = lambda uid: Progress(0, 1, 20, 10)
            realm._world_hp, realm._world_mp = lambda uid: 20, lambda uid: 10
            realm._world_stance = lambda uid: 50
            game = realm.grant(object(), movement_owner_guard=lambda *_: True)
            await game.received(types.SimpleNamespace(opcode=0x263,
                payload=LocalLoginRequest(0, 'standalone.local', realm.expected_uuid).payload()))
            frames = await game.received(types.SimpleNamespace(opcode=0x4e28,
                payload=pb.encode_bytes(1, b'SoloMage') + b'\x10\0\x18\0'))
            status = b.session.world.decode_payload(0x4e38, frames[2][4:-2])
            self.assertEqual(tuple(status[key] for key in (1, 2, 10, 11, 12, 13)),
                             (2, 5, 17, 55, 9, 40))
            self.assertEqual(tuple(status[key] for key in (4, 5, 6, 7, 8, 9)),
                             (8, 7, 18, 18, 16, 8))
            actor = b.session.world.decode_payload(0x4e96, frames[3][4:-2])
            self.assertEqual((actor[2], actor[3], actor[4], actor[9]), (2, 734, 50, 'SoloMage'))

    async def test_selected_mage_binds_canonical_state_and_exit_save_captures_last_vitals(self):
        import json
        import os
        from tools.local_original_session import world_visibility
        from tools.local_original_session.world_m1_reward_tests import enable_world_kit
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'SL_COMPANION': '1'}):
            host = b.PersistentBroker(sockets={12000: object(), 14030: object()},
                retained_owner=object(), owner_handle=object(), owner_job=object(),
                owner_guard=lambda _: True, owner_liveness_guard=lambda: True,
                source_guard=lambda: None, conversation_factory=FixtureConversation,
                expected_uuid=str(uuid.uuid4()), store_path=Path(directory) / 'characters.json',
                world_policy=world_visibility.POLICY)
            try:
                host.realm.store.create(b.ack.realm.Creation('SoloKnight', 1, 0, (18, 13, 16, 10, 10, 10)))
                enable_world_kit(host, 1)
                host._companion_started()
                member = next(iter(host._world.companions.records.values()))
                member.level, member.hp, member.max_hp = 5, 17, 55
                member.mp, member.max_mp = 9, 40
                writer = object()
                game = host.realm.grant(writer, movement_owner_guard=lambda *_: True)
                await game.received(types.SimpleNamespace(opcode=0x263,
                    payload=LocalLoginRequest(0, 'standalone.local', host.realm.expected_uuid).payload()))
                await game.received(types.SimpleNamespace(opcode=0x4e28,
                    payload=pb.encode_bytes(1, b'SoloMage') + b'\x10\0\x18\0'))
                host._world_send = mock.AsyncMock()
                await host._world_after_request(writer, {}, game, 0x4e28, asyncio.Lock())
                state = host._world.combat.pcs[member.character_id]
                self.assertEqual((state.profile.level, state.profile.character_class,
                    state.hp, state.max_hp, state.mp, state.max_mp), (5, 3, 17, 55, 9, 40))
                self.assertNotIn(member.character_id, host._world.companions.active)
                # Development-only stand-in for the last resource tick. The
                # exit save must sample this state without another request.
                state.hp, state.status_fields[12] = 11, 3
                host._companion_save(0)
                stored = json.loads(host._companion_store.path.read_text(encoding='utf-8'))['records'][0]
                self.assertEqual((stored['level'], stored['hp'], stored['mp']), (5, 11, 3))
            finally:
                host._world.close()

    async def test_default_attack_unbound_and_close_preserves_movement_history(self):
        with tempfile.TemporaryDirectory() as directory:
            realm = b.LocalRealm(str(uuid.uuid4()), Path(directory) / 'characters.json')
            _, frames = await self.select(realm)
            self.assertEqual(len(frames), 4)
            game, = realm.registry._sessions.values()
            self.assertNotIn(b.ATTACK_REQUEST, game.routes)
            with self.assertRaisesRegex(ValueError, 'GAME_REQUEST_OPCODE_UNBOUND'):
                await game.received(types.SimpleNamespace(opcode=b.ATTACK_REQUEST, payload=b'\x08\x02'))
            realm.close(game.connection)
            report = realm.movement_report()
            self.assertEqual(report['active_services'], 0)
            self.assertEqual(len(report['sessions']), 1)
            self.assertTrue(report['sessions'][0]['closed'])
            self.assertIsNone(realm._attack_session)

    async def select(self, realm):
        writer = object()
        realm.store.create(b.ack.realm.Creation(realm.profile_name, 0, 0, (13,) * 6))
        game = realm.grant(writer, movement_owner_guard=lambda *_: True)
        await game.received(types.SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', realm.expected_uuid).payload()))
        request = pb.encode_message([pb.encode_bytes(1, realm.profile_name.encode()),
                                     pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        frames = await game.received(types.SimpleNamespace(opcode=0x4e28, payload=request))
        return realm.service(writer).snapshot(), frames

    async def test_default_baseline_and_pinned_cp73_spawn_keep_all_other_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root, expected_uuid = Path(directory), str(uuid.uuid4())
            with mock.patch('time.time', return_value=1792114864):
                baseline = b.LocalRealm(expected_uuid, root / 'base.json')
                experiment = b.LocalRealm(expected_uuid, root / 'spawn.json', world_profile=b.CP73_SPAWN_WORLD)
            original, _ = await self.select(baseline)
            spawned, frames = await self.select(experiment)
            self.assertEqual((original.word0, original.word1), (32571, 32951))
            self.assertEqual((spawned.uid, spawned.map_id, spawned.word0, spawned.word1), (1, 0, 32571, 32950))
            self.assertEqual(baseline._self_fields, experiment._self_fields)
            self.assertEqual([key for key in baseline._actor_fields
                              if baseline._actor_fields[key] != experiment._actor_fields[key]], [1])
            actor = b.session.world.decode_payload(0x4e96, frames[3][4:-2])
            self.assertEqual(actor, experiment._actor_fields)
            self.assertEqual(experiment.world_profile_report()['fallback_policy'], b.CP73_SPAWN_WORLD)
            self.assertFalse(experiment.world_profile_report()['fallback_is_original_spawn'])
            self.assertEqual(baseline.world_profile_report()['fallback_policy'], 'EXPLICIT_LOCAL_SOURCE_BASELINE')

    async def test_saved_uid_position_precedes_cp73_fallback_without_store_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path, expected_uuid = Path(directory) / 'characters.json', str(uuid.uuid4())
            realm = b.LocalRealm(expected_uuid, path, world_profile=b.CP73_SPAWN_WORLD)
            initial = m.Position(realm.profile_uid, realm.profile_name, 0, 32571, 32950)
            saved = m.Position(realm.profile_uid, realm.profile_name, 0, 32572, 32950)
            realm.positions.commit(initial, saved)
            before = realm.positions.path.read_bytes()
            restored, frames = await self.select(realm)
            self.assertEqual(restored, saved)
            self.assertEqual(b.session.world.decode_payload(0x4e96, frames[3][4:-2])[1], saved.packed)
            self.assertEqual(realm.positions.path.read_bytes(), before)

    def test_unknown_world_profile_rejected_before_store_and_broker_forwards_known_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'characters.json'
            with self.assertRaisesRegex(ValueError, 'KNOWN_LOCAL_WORLD_PROFILE_REQUIRED'):
                b.LocalRealm(str(uuid.uuid4()), path, world_profile='caller-coordinates')
            self.assertFalse(path.exists())
            with mock.patch.object(b, 'LocalRealm') as realm:
                b.PersistentBroker(sockets={12000: object(), 14030: object()}, retained_owner=object(),
                    owner_handle=object(), owner_job=object(), owner_guard=lambda _: True,
                    owner_liveness_guard=lambda: True, source_guard=lambda: None,
                    conversation_factory=lambda *_: None, expected_uuid=str(uuid.uuid4()),
                    store_path=path, world_profile=b.CP73_SPAWN_WORLD)
            self.assertEqual(realm.call_args.kwargs['world_profile'], b.CP73_SPAWN_WORLD)


class AliveSchemaTests(unittest.TestCase):
    """Existing bounded protobuf codec only; no listener or payload persistence."""
    def test_optional_duplicates_order_negative_varints_and_unknown_wire02(self):
        self.assertEqual(b.alive_request_metadata(b''), dict(body_bytes=0, field1_count=0,
            field2_count=0, field3_count=0, unknown_field_count=0))
        secret = b'private-alive-data'
        payload = pb.encode_message([
            pb.encode_bytes(3, secret), b'\x10' + pb.encode_varint((1 << 64) - 1),
            b'\x08' + pb.encode_varint((1 << 64) - 1), pb.encode_uint32(1, 7),
            pb.encode_bytes(3, b''), pb.encode_uint32(40, 1), pb.encode_bytes(41, b'unknown'),
            pb.encode_bytes(1, b'wrong-wire-known-number'), pb.encode_uint32(3, 1)])
        result = b.alive_request_metadata(payload)
        self.assertEqual(result, dict(body_bytes=len(payload), field1_count=2,
            field2_count=1, field3_count=2, unknown_field_count=4))
        self.assertNotIn(secret.decode(), repr(result))
        self.assertTrue(all(type(value) is int for value in result.values()))

    def test_malformed_bounds_and_unsupported_wire_types_keep_existing_codec_limits(self):
        bad = (b'\x08', b'\x1a\x02a', b'\x08' + b'\x80' * 10 + b'\x00',
               b'\x00', b'\x21' + bytes(8), b'\x25' + bytes(4), b'\x23\x24',
               b'\x08\x00' * 129, bytes(65525))
        for payload in bad:
            with self.subTest(size=len(payload)), self.assertRaises(ValueError):
                b.alive_request_metadata(payload)


class AliveRouteTests(unittest.IsolatedAsyncioTestCase):
    """Direct production realm/route/tempstore; never reserve or start a port."""
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.realm = b.LocalRealm(str(uuid.uuid4()), Path(self.temp.name) / 'characters.json')
        self.writer = object()
        self.owner_allowed, self.owner_mutation = True, None
        self.owner_calls = 0

        async def owner(writer, position):
            self.assertIs(writer, self.writer)
            self.owner_calls += 1
            if self.owner_mutation is not None:
                self.owner_mutation()
            return self.owner_allowed

        self.realm.store.create(b.ack.realm.Creation(self.realm.profile_name, 0, 0, (13,) * 6))
        self.game = self.realm.grant(self.writer, movement_owner_guard=owner)

    async def login(self):
        await self.game.received(types.SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))

    async def selected(self):
        await self.login()
        payload = pb.encode_message([pb.encode_bytes(1, self.realm.profile_name.encode()),
                                     pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        await self.game.received(types.SimpleNamespace(opcode=0x4e28, payload=payload))

    async def alive(self, payload=b''):
        return await self.game.received(types.SimpleNamespace(opcode=b.ALIVE_REQUEST, payload=payload))

    async def test_selected_typed_reply_is_exact_empty_body_repeatable_and_no_store_change(self):
        await self.selected()
        path = self.realm.store.path
        before = path.read_bytes()
        position = self.realm.service(self.writer).snapshot()
        payload = pb.encode_message([pb.encode_uint32(1, 5), pb.encode_uint32(2, 7),
                                     pb.encode_bytes(3, b'not-for-storage-or-echo'.ljust(256, b'\0'))])
        self.assertEqual(len(c2s(b.ALIVE_REQUEST, payload)), 274)  # Synthetic normal shape, not manual50 bytes.
        for value in (payload, b'', payload):
            replies = await self.alive(value)
            self.assertEqual(replies, (b'\x06\0\x57\x4f\0\0',))
            for reply in replies:
                self.realm.validate_reply(reply, writer=self.writer)  # Actual _send(game=True) consumer.
        self.assertEqual(self.owner_calls, 3)
        self.assertIs(self.realm.service(self.writer).snapshot(), position)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.realm.positions.path.exists())
        self.assertEqual(self.realm._quit, {})

    async def test_modified_alive_frame_body_or_foreign_writer_never_validates(self):
        await self.selected()
        reply = (await self.alive())[0]
        for changed in (b'\x08\0\x57\x4f\x08\x01\0\0', b'\x06\0\x58\x4f\0\0',
                        reply[:-1] + b'\x01'):
            with self.subTest(frame=changed.hex()), self.assertRaises(ValueError):
                self.realm.validate_reply(changed, writer=self.writer)
        for other in (None, object()):
            with self.assertRaises(ValueError):
                self.realm.validate_reply(reply, writer=other)
        self.realm._quit[id(self.writer)] = {}
        with self.assertRaisesRegex(ValueError, 'ALIVE_REPLY_SELECTED_AUTHORITY_REQUIRED'):
            self.realm.validate_reply(reply, writer=self.writer)

    async def test_unbound_account_and_unselected_foreign_writer_never_reply(self):
        with self.assertRaisesRegex(ValueError, 'SAME_0263_BOUND_ACCOUNT_WRITER_REQUIRED'):
            await self.alive()
        await self.login()
        with self.assertRaisesRegex(ValueError, 'ALIVE_SELECTED_OWNER_REQUIRED'):
            await self.alive()
        foreign = self.realm.grant(object(), movement_owner_guard=lambda *_: True)
        with self.assertRaisesRegex(ValueError, 'SAME_0263_BOUND_ACCOUNT_WRITER_REQUIRED'):
            await foreign.received(types.SimpleNamespace(opcode=b.ALIVE_REQUEST, payload=b''))
        self.assertEqual(self.owner_calls, 0)

    async def test_owner_loss_or_mutated_authority_after_await_never_reply(self):
        await self.selected()
        self.owner_allowed = False
        with self.assertRaisesRegex(ValueError, 'ALIVE_CURRENT_SELECTED_OWNER_REQUIRED'):
            await self.alive()
        self.owner_allowed = True
        self.owner_mutation = lambda: self.realm.registry.selected.clear()
        with self.assertRaisesRegex(ValueError, 'ALIVE_CURRENT_SELECTED_AUTHORITY_REQUIRED'):
            await self.alive()

    async def test_terminal_and_fatal_state_and_malformed_payload_never_reply(self):
        await self.selected()
        with self.assertRaises(ValueError):
            await self.alive(b'\x1a\x02a')
        self.assertEqual(self.owner_calls, 0)
        self.realm._quit[id(self.writer)] = {}
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_SESSION'):
            await self.alive()
        self.realm._quit.clear()
        self.realm._settings_failed = True
        with self.assertRaisesRegex(ValueError, 'SETTINGS_PERSISTENCE_FATAL'):
            await self.alive()
        self.assertEqual(self.owner_calls, 0)


class AttackIntentRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tools.local_original_session import attack_tests, feature_config, launcher, npc_motion_tests
        from tools.local_original_session.npc_tests import spawn
        # Reuse only its source-pinned real retained-validator fixture, then
        # construct this unit's broker through the actual product factory.
        with mock.patch.object(npc_motion_tests.ConnectedMotionTests, 'asyncSetUp', connected_motion_setup):
            await attack_tests.TargetTests.asyncSetUp(self)
        retained = self.reader.owner
        config = feature_config.Features(spawns=(spawn(),), attack_policy=b.ATTACK_INTENT_POLICY,
                                         attack_feedback=getattr(self, 'feedback_config', None),
                                         restart_policy=getattr(self, 'restart_policy', None))
        feature = launcher.ProductFeatureFactory(self.reader, product='sibling-manual-play-spawn',
            control_mode='manual', directory=Path(self.temp.name), config=config)
        self.producer = b.PersistentBroker(sockets={12000: object(), 14030: object()},
            retained_owner=retained, owner_handle=retained.owner_handle, owner_job=retained.owner_job,
            owner_guard=lambda _: True, owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=FixtureConversation, expected_uuid=self.realm.expected_uuid,
            store_path=self.realm.store.path,
            settings_path=(Path(self.temp.name) / 'settings.bin') if getattr(self, 'restart_policy', None) else None,
            **feature.broker_options())
        self.realm, self.policy = self.producer.realm, self.producer.policy
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
        prior = object()
        peer = b.Peer(14030, 41000, time.monotonic_ns())
        boot(prior, peer)
        self.policy.eof(prior, sample(peer), True, time.monotonic_ns())
        self.policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        peer = b.Peer(14030, 41001, time.monotonic_ns())
        policy_row = boot(self.writer, peer)
        self.row = dict(writer=self.writer, policy_row=policy_row,
            peer=dict(connection_id=4, endpoint_port=14030, server_port=14030,
                      client_port=peer.client_port, accepted_monotonic_ns=peer.accepted_ns),
            joined=False, failed=False, operation_lock=asyncio.Lock(), eof=False,
            positive_close=False, registry_removed=False, boot_complete=True)
        self.producer._claims[14030] = [self.row]
        async def owner(writer, position):
            return await self.producer._movement_owner(writer, self.row, position)
        async def account(writer):
            return await self.producer._account_owner(writer, self.row)
        self.game = self.realm.grant(self.writer, movement_owner_guard=owner, account_owner_guard=account,
                                     connection_id=4)
        await self.game.received(types.SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))
        payload = pb.encode_message([pb.encode_bytes(1, self.realm.profile_name.encode()),
                                     pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        await self.producer._send(self.writer, self.row,
            await self.game.received(types.SimpleNamespace(opcode=0x4e28, payload=payload)), game=True)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.service = self.producer._attack_session

    async def dispatch(self, raw):
        decoder = b.ClientPlaintextDecoder(cipher_pointer='present_disabled', max_buffer=self.policy.MAX_BUFFER)
        operation_lock = self.row['operation_lock']
        async with operation_lock:
            sample = await self.producer._checkpoint(self.writer, self.row)
            frames = decoder.feed(raw)
            self.policy.received_chunk(self.writer, sample, len(raw), decoder.buffered_bytes,
                                       time.monotonic_ns(), decoded_frames=len(frames))
            for frame in frames:
                sample = await self.producer._checkpoint(self.writer, self.row)
                self.policy.received_frame(self.writer, sample, frame.opcode, frame.wire_length,
                                           time.monotonic_ns())
                await self.producer._send(self.writer, self.row, await self.game.received(frame),
                                          game=True, operation_lock=operation_lock)
        decoder.finish()

    async def test_original_c2s_frame_product_factory_real_route_records_one_intent_no_reply(self):
        self.assertTrue(self.policy.attack_intent)
        self.assertIn(b.ATTACK_REQUEST, self.game.routes)
        await asyncio.wait_for(self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02')), 2)
        self.assertEqual(self.service.accepted_count, 1)
        self.assertEqual(self.service.metadata()['last_outcome']['kind'], 'ACCEPTED')
        self.assertEqual(self.policy.log[-1][0:3], ('rx', 14030, b.ATTACK_REQUEST))
        self.assertFalse(self.row['operation_lock'].locked())
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)

    async def test_local_coordinate_refusal_is_empty_but_foreign_malformed_and_source_errors_propagate(self):
        from tools.local_original_session import attack
        fields = self.realm._npc_spawns[0][0].fields
        x, _ = m.authority.unpack_grid(fields[1])
        await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02' + attack._field(2, x + 1)))
        self.assertEqual(self.service.metadata()['last_outcome']['kind'], 'REJECTED')
        self.assertEqual(self.service.accepted_count, 0)
        with self.assertRaisesRegex(ValueError, 'MALFORMED_ATTACK_PAYLOAD'):
            await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x80'))
        with self.assertRaises(ValueError):
            await self.service.handle(object(), b'\x08\x02')
        pins = dict(attack.SOURCE_PINS); pins[next(iter(pins))] = '0' * 64
        with mock.patch.object(attack, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'ATTACK_SOURCE_CHANGED'):
            await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02'))
        self.assertEqual(self.service.accepted_count, 0)
        self.writer.write.assert_not_called()

    async def test_selection_loss_and_close_cannot_reuse_accepted_intent(self):
        await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02'))
        self.realm.registry.selected.clear()
        self.assertIsNone(self.service.current_intent())
        with self.assertRaises(ValueError):
            await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02'))
        self.realm.close(self.writer)
        with self.assertRaises(ValueError):
            await self.game.received(types.SimpleNamespace(opcode=b.ATTACK_REQUEST, payload=b'\x08\x02'))
        self.producer._fail('FIXTURE_SESSION_STOPPED')
        self.assertTrue(self.service.fatal)
        self.assertIsNone(self.service.current_intent())
        self.assertEqual(self.service.accepted_count, 1)
        self.writer.write.assert_not_called()

    async def test_writer_release_revokes_only_matching_current_intent_preserving_history(self):
        await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02'))
        self.realm.close(object())
        self.assertEqual(self.service.current_intent().accepted_ordinal, 1)
        self.realm.close(self.writer)
        self.assertEqual(self.service.last_invalidation, 'ATTACK_SESSION_WRITER_RELEASED')
        self.assertIsNone(self.service.current_intent())
        self.assertFalse(self.service.closed)
        self.assertEqual(self.service.accepted_count, 1)
        with self.assertRaises(ValueError):
            await self.game.received(types.SimpleNamespace(opcode=b.ATTACK_REQUEST, payload=b'\x08\x02'))
        self.writer.write.assert_not_called()


class InventoryPolicyTests(unittest.TestCase):
    def test_only_explicit_s2c_switch_preserves_frozen_stage_size_owner_and_drain_checks(self):
        from tools.local_original_session import inventory
        policy = b._TransportPolicy(object(), object(), object(),
            {12000: object(), 14030: object()}, now=time.monotonic_ns())
        row = types.SimpleNamespace(drain_started_ns=None, rx_boot=2, tx_boot=3, stage=1,
            tx_frames=mock.Mock(), tx_bytes=mock.Mock())
        policy.checkpoint = mock.Mock(return_value=row)
        writer, sample, now = object(), object(), time.monotonic_ns()
        with self.assertRaisesRegex(ValueError, 'SERVER_OPCODE_UNBOUND'):
            policy.begin_write(writer, sample, inventory.OPCODE, 20, 0, now)
        policy.inventory_add = True
        policy.begin_write(writer, sample, inventory.OPCODE, 20, 0, now)
        self.assertEqual((row.pending_opcode, row.pending_size, row.drain_started_ns), (inventory.OPCODE, 20, now))
        row.tx_frames.take.assert_called_once_with(1, now)
        row.tx_bytes.take.assert_called_once_with(20, now)
        with self.assertRaisesRegex(ValueError, 'ONE_WRITE_DRAIN'):
            policy.begin_write(writer, sample, inventory.OPCODE, 20, 0, now)
        row.drain_started_ns = None
        with self.assertRaisesRegex(ValueError, 'INVENTORY_FRAME_BOUND'):
            policy.begin_write(writer, sample, inventory.OPCODE, inventory.MAX_FRAME + 1, 0, now)
        row.stage = 0
        with self.assertRaisesRegex(ValueError, 'SERVER_OPCODE_UNBOUND'):
            policy.begin_write(writer, sample, inventory.OPCODE, 20, 0, now)
        row.stage = 1
        policy.checkpoint.side_effect = ValueError('CURRENT_OWNER_REQUIRED')
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            policy.begin_write(writer, sample, inventory.OPCODE, 20, 0, now)
        policy.checkpoint.side_effect = None
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            policy.received_frame(writer, sample, inventory.OPCODE, 20, now)


class AttackIntentPolicyTests(unittest.TestCase):
    def test_only_explicit_attack_c2s_extends_frozen_policy_with_existing_checks(self):
        policy = b._TransportPolicy(object(), object(), object(),
            {12000: object(), 14030: object()}, now=123)
        row = types.SimpleNamespace(drain_started_ns=None, rx_boot=2, tx_boot=3, stage=1,
            rx_frames=mock.Mock(), received=0, peer=types.SimpleNamespace(port=14030))
        policy.checkpoint, policy._emit = mock.Mock(return_value=row), mock.Mock()
        writer, sample, now = object(), object(), 123
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            policy.received_frame(writer, sample, b.ATTACK_REQUEST, 14, now)
        policy.attack_intent = True
        policy.received_frame(writer, sample, b.ATTACK_REQUEST, 14, now)
        self.assertEqual(row.received, 1)
        row.rx_frames.take.assert_called_once_with(1, now)
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            policy.received_frame(writer, sample, 0x4e31, 14, now)
        row.stage = 0
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            policy.received_frame(writer, sample, b.ATTACK_REQUEST, 14, now)
        row.stage, row.drain_started_ns = 1, now
        with self.assertRaisesRegex(ValueError, 'DISPATCH_PAUSED_UNTIL_DRAIN'):
            policy.received_frame(writer, sample, b.ATTACK_REQUEST, 14, now)
        row.drain_started_ns = None
        policy.checkpoint.side_effect = ValueError('CURRENT_OWNER_REQUIRED')
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            policy.received_frame(writer, sample, b.ATTACK_REQUEST, 14, now)
        self.assertEqual(row.received, 1)


class AlivePolicyTests(unittest.TestCase):
    """Pure existing policy extension, no sockets/native owner/runtime."""
    def test_only_typed_alive_extends_policy_with_stage_owner_and_drain_checks(self):
        policy = b._TransportPolicy(object(), object(), object(),
            {12000: object(), 14030: object()}, now=123)
        row = types.SimpleNamespace(drain_started_ns=None, rx_boot=2, tx_boot=3, stage=1,
            rx_frames=mock.Mock(), tx_frames=mock.Mock(), tx_bytes=mock.Mock(), received=0,
            peer=types.SimpleNamespace(port=14030))
        policy.checkpoint, policy._emit = mock.Mock(return_value=row), mock.Mock()
        writer, sample, now = object(), object(), 123
        policy.received_frame(writer, sample, b.ALIVE_REQUEST, 274, now)
        policy.checkpoint.assert_called_once_with(writer, sample, now)
        row.rx_frames.take.assert_called_once_with(1, now)
        policy.begin_write(writer, sample, b.ALIVE_RESPONSE, len(b.ALIVE_FRAME), 0, now)
        self.assertEqual((row.pending_opcode, row.pending_size), (0x4f57, 6))
        row.drain_started_ns = None
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            policy.received_frame(writer, sample, 0x4e2d, 274, now)
        row.stage = 0
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            policy.received_frame(writer, sample, b.ALIVE_REQUEST, 274, now)
        row.stage, row.drain_started_ns = 1, now
        with self.assertRaisesRegex(ValueError, 'DISPATCH_PAUSED_UNTIL_DRAIN'):
            policy.received_frame(writer, sample, b.ALIVE_REQUEST, 274, now)


class AttackFeedbackRouteTests(unittest.IsolatedAsyncioTestCase):
    """Reuse the original factory/real policy/retained Native transport fixture."""
    dispatch = AttackIntentRouteTests.dispatch

    async def asyncSetUp(self):
        from tools.local_original_session import attack_feedback, attack_session
        self.feedback_config = attack_session.FeedbackConfig(attack_feedback.POLICY, 0, 8, True)
        await AttackIntentRouteTests.asyncSetUp(self)

    async def prepared(self):
        # Caller holds exactly the same operation lock as production _serve.
        replies = await self.game.received(types.SimpleNamespace(opcode=b.ATTACK_REQUEST, payload=b'\x08\x02'))
        self.assertEqual(len(replies), 1)
        return replies[0]

    async def test_original_frame_factory_route_one_write_drain_new_intent_and_old_frame_refused(self):
        from tools.local_original_session import attack_feedback
        await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02'))
        wire = self.writer.write.call_args.args[0]
        self.assertIs(wire, self.service._feedback_frame)
        view = attack_feedback.validate_frame(wire, policy=attack_feedback.POLICY)
        self.assertEqual((view.kind, view.attacker_uid, view.target_uid, view.raw_effect,
                          view.direction, view.self_action), (1, 1, 2, 0, 8, True))
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual((self.service.accepted_count, self.service.feedback_reserved,
                          self.service.feedback_write_attempted, self.service.feedback_drained), (1, 1, 1, 1))
        self.assertEqual(self.policy.log[-1][0:3], ('tx', 14030, b.ATTACK_FEEDBACK))
        self.assertIsNone(self.row['policy_row'].pending_opcode)
        async with self.row['operation_lock']:
            with self.assertRaisesRegex(ValueError, 'CURRENT_FRAME'):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        self.assertEqual(self.writer.write.call_count, 1)
        # A new original request is independently authorized; never an old-frame retry.
        await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02', sequence=2))
        self.assertEqual((self.service.accepted_count, self.service.feedback_drained), (2, 2))
        self.assertIsNot(self.service._feedback_frame, wire)
        meta = self.service.metadata()['feedback']
        self.assertEqual((meta['proof_scope'], meta['client_action'], meta['hp']),
                         ('TRANSPORT_DRAIN_ONLY', 'UNKNOWN', 'UNKNOWN'))

    async def test_equal_copied_frame_foreign_writer_close_and_malformed_never_write(self):
        async with self.row['operation_lock']:
            wire = await self.prepared()
            for invalid_writer, invalid_wire in ((self.writer, bytes(bytearray(wire))),
                                                  (object(), wire),
                                                  (self.writer, wire[:-2] + b'\x01\x00')):
                with self.assertRaises(ValueError):
                    self.realm.validate_reply(invalid_wire, writer=invalid_writer)
            self.service.close()
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        self.writer.write.assert_not_called()
        self.assertEqual(self.service.feedback_write_attempted, 0)

    async def test_write_checkpoint_selection_loss_is_terminal_zero_write(self):
        async with self.row['operation_lock']:
            wire = await self.prepared()
            original = self.producer.owner_guard
            async def owner(peer):
                await asyncio.sleep(0)
                self.realm.registry.selected.clear()
                return original(peer)
            self.producer.owner_guard = owner
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
            self.assertTrue(self.service.fatal)
            self.assertEqual(self.service._feedback_state, 'TERMINAL')
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        self.writer.write.assert_not_called()
        self.assertEqual(self.service.feedback_reserved, 1)

    async def test_actual_source_loss_at_final_policy_callback_zero_write(self):
        from tools.local_original_session import attack_feedback
        async with self.row['operation_lock']:
            wire = await self.prepared()
            original = self.policy.begin_write
            pins = dict(attack_feedback.SOURCE_PINS)
            def begin(*args, **kwargs):
                result = original(*args, **kwargs)
                attack_feedback.SOURCE_PINS[next(iter(pins))] = '0' * 64
                return result
            self.policy.begin_write = begin
            try:
                with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                    await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
            finally:
                attack_feedback.SOURCE_PINS.clear(); attack_feedback.SOURCE_PINS.update(pins)
        self.writer.write.assert_not_called()
        self.assertTrue(self.service.fatal)
        self.assertIsNotNone(self.row['policy_row'].drain_started_ns)
        self.assertEqual(self.service.feedback_write_attempted, 0)

    async def test_sync_policy_cancel_after_reservation_never_write_and_propagates(self):
        async def operation():
            async with self.row['operation_lock']:
                wire = await self.prepared()
                original = self.policy.begin_write
                def begin(*args, **kwargs):
                    result = original(*args, **kwargs)
                    asyncio.current_task().cancel('cancel at last sync callback')
                    return result
                self.policy.begin_write = begin
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        task = asyncio.create_task(operation())
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.writer.write.assert_not_called()
        self.assertTrue(self.service.fatal)
        self.assertEqual(self.service.feedback_write_attempted, 0)

    async def test_pending_checkpoint_cancel_no_write_and_no_retry(self):
        entered = asyncio.Event()
        async def operation():
            async with self.row['operation_lock']:
                wire = await self.prepared()
                async def owner(_):
                    entered.set()
                    await asyncio.Event().wait()
                self.producer.owner_guard = owner
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        task = asyncio.create_task(operation())
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.writer.write.assert_not_called()
        self.assertTrue(self.service.fatal)
        self.assertEqual(self.service.feedback_reserved, 1)

    async def test_drain_ambiguity_one_write_terminal_and_no_resend(self):
        async with self.row['operation_lock']:
            wire = await self.prepared()
            self.writer.drain.side_effect = ConnectionError('ambiguous actual drain')
            with self.assertRaises(ConnectionError):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            self.assertEqual((self.service.feedback_write_attempted, self.service.feedback_drained), (1, 0))
            self.assertTrue(self.service.fatal)
            self.assertIsNone(self.service.current_intent())
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_unbound_feedback_policy_refuses_and_local_attack_rejects_no_frame(self):
        from tools.local_original_session import attack
        self.policy.attack_feedback = False
        async with self.row['operation_lock']:
            wire = await self.prepared()
            with self.assertRaisesRegex(ValueError, 'SERVER_OPCODE_UNBOUND'):
                await self.producer._send(self.writer, self.row, (wire,), game=True, operation_lock=self.row['operation_lock'])
        self.writer.write.assert_not_called()
        self.assertEqual(self.service.feedback_write_attempted, 0)

    async def test_local_target_refusal_and_malformed_intent_return_no_feedback(self):
        from tools.local_original_session import attack
        async with self.row['operation_lock']:
            replies = await self.service.handle(self.writer, attack._field(1, 47))
        self.assertEqual(replies, ())
        self.assertEqual(self.service.last_outcome.kind.value, 'REJECTED')
        async with self.row['operation_lock']:
            with self.assertRaisesRegex(ValueError, 'MALFORMED_ATTACK'):
                await self.service.handle(self.writer, b'\x08\x80')
        self.writer.write.assert_not_called()
        self.assertEqual(self.service.feedback_prepared, 0)


    async def test_native_owner_refusal_at_write_checkpoint_zero_write_terminal(self):
        async with self.row['operation_lock']:
            wire = await self.prepared()
            self.producer.owner_guard = lambda _: False
            with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                    operation_lock=self.row['operation_lock'])
        self.writer.write.assert_not_called()
        self.assertTrue(self.service.fatal)
        self.assertEqual((self.service.feedback_write_attempted, self.service.feedback_drained), (0, 0))

    async def test_native_owner_loss_after_actual_drain_remains_unproven_no_retry(self):
        async with self.row['operation_lock']:
            wire = await self.prepared()
            calls = 0
            def owner(_):
                nonlocal calls
                calls += 1
                return calls == 1
            self.producer.owner_guard = owner
            with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                    operation_lock=self.row['operation_lock'])
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            self.assertTrue(self.service.fatal)
            self.assertEqual((self.service.feedback_write_attempted, self.service.feedback_drained), (1, 0))
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                    operation_lock=self.row['operation_lock'])
        self.assertEqual(self.writer.write.call_count, 1)


class RestartRouteTests(unittest.IsolatedAsyncioTestCase):
    dispatch = AttackIntentRouteTests.dispatch

    async def asyncSetUp(self):
        from tools.local_original_session import restart
        self.restart_policy = restart.POLICY
        await AttackIntentRouteTests.asyncSetUp(self)

    async def prepared(self):
        replies = await self.game.received(types.SimpleNamespace(opcode=b.RESTART_REQUEST, payload=b''))
        self.assertEqual(len(replies), 1)
        return replies[0]

    async def test_original_request_true_ack_drains_then_selection_only_cleanup_and_same_game_reselect(self):
        from tools.local_original_session import restart
        game, service, selected = self.game, self.realm.service(self.writer), self.game.selection
        position, account, roster = service.snapshot(), self.realm._account_bound[id(self.writer)], self.game.roster
        self.realm.positions.commit(position, position)  # Existing original TempStore format only.
        await self.dispatch(c2s(b.settings.OPCODE, pb.encode_bytes(1, b'explicit-settings-fixture')))
        await self.dispatch(c2s(b.ATTACK_REQUEST, b'\x08\x02'))
        self.assertIsNotNone(self.service.current_intent())
        position_bytes = self.realm.positions.path.read_bytes()
        settings_bytes = self.realm.settings.path.read_bytes()
        await self.dispatch(c2s(b.RESTART_REQUEST))
        wire = self.writer.write.call_args.args[0]
        self.assertIs(wire, self.row['_restart']['frame'])
        self.assertTrue(restart.validate_ack(wire, policy=restart.POLICY))
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertIs(self.realm.registry.resolve(self.writer), game)
        self.assertIs(self.realm._account_bound[id(self.writer)], account)
        self.assertIs(game.roster, roster)
        self.assertTrue(game.list_sent)
        self.assertIsNone(game.selection)
        self.assertNotIn(selected.reference, self.realm.registry.selected)
        self.assertNotIn(id(self.writer), self.realm._movement)
        self.assertNotIn(id(self.writer), self.realm._npc_frames)
        self.assertIsNone(self.service.current_intent())
        self.assertEqual(self.row['_restart']['phase'], 'DRAINED')
        self.assertIsNone(self.row['policy_row'].pending_opcode)
        self.assertEqual(position_bytes, self.realm.positions.path.read_bytes())
        self.assertEqual(settings_bytes, self.realm.settings.path.read_bytes())
        self.assertNotIn(id(self.writer), self.realm._quit)
        self.assertEqual(self.policy.log[-1][0:3], ('tx', 14030, b.RESTART_ACK))
        selection = pb.encode_message([pb.encode_bytes(1, position.name.encode()),
                                       pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        await self.dispatch(c2s(0x4e28, selection))
        self.assertIs(self.realm.registry.resolve(self.writer), game)
        self.assertIsNot(game.selection, selected)
        self.assertIsNot(self.realm.service(self.writer), service)
        self.assertEqual(self.realm.service(self.writer).snapshot(), position)
        self.assertIs(self.realm.positions.restore(position).__class__, position.__class__)

    async def test_malformed_and_foreign_or_copied_ack_never_write(self):
        with self.assertRaisesRegex(ValueError, 'EMPTY_SOURCE_BODY'):
            await self.dispatch(c2s(b.RESTART_REQUEST, b'\x08\x01'))
        self.assertNotIn('_restart', self.row)
        async with self.row['operation_lock']:
            wire = await self.prepared()
            for writer, raw in ((object(), wire), (self.writer, bytes(bytearray(wire)))):
                with self.assertRaises(ValueError):
                    self.realm.validate_reply(raw, writer=writer)
        self.writer.write.assert_not_called()
        self.assertIsNotNone(self.game.selection)

    async def test_write_checkpoint_selection_change_is_terminal_no_cleanup_or_retry(self):
        from dataclasses import replace
        mode = dict(change=False)
        async def owner(_):
            await asyncio.sleep(0)
            if mode['change']:
                self.game.selection = replace(self.game.selection, field2=1)
            return True
        self.producer.owner_guard = owner
        async with self.row['operation_lock']:
            wire = await self.prepared()
            mode['change'] = True
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                                          operation_lock=self.row['operation_lock'])
        self.writer.write.assert_not_called()
        self.assertEqual(self.row['_restart']['phase'], 'TERMINAL')
        self.assertFalse(self.row['_restart']['selection_cleared'])

    async def test_final_policy_callback_cancel_zero_write_no_cleanup_no_retry(self):
        async def operation():
            async with self.row['operation_lock']:
                wire = await self.prepared()
                begin = self.policy.begin_write
                def cancelling(*args, **kwargs):
                    result = begin(*args, **kwargs)
                    asyncio.current_task().cancel('Restart final callback')
                    return result
                self.policy.begin_write = cancelling
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                                          operation_lock=self.row['operation_lock'])
        task = asyncio.create_task(operation())
        with self.assertRaises(asyncio.CancelledError): await task
        self.writer.write.assert_not_called()
        self.assertEqual(self.row['_restart']['phase'], 'TERMINAL')
        self.assertFalse(self.row['_restart']['selection_cleared'])
        self.assertIsNotNone(self.game.selection)


    async def test_drain_unknown_one_attempt_no_cleanup_no_resend(self):
        async with self.row['operation_lock']:
            wire = await self.prepared()
            self.writer.drain.side_effect = ConnectionError('unknown Restart drain')
            with self.assertRaises(ConnectionError):
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                                          operation_lock=self.row['operation_lock'])
            with self.assertRaises(ValueError):
                await self.prepared()
            with self.assertRaises(ValueError):
                await self.producer._send(self.writer, self.row, (wire,), game=True,
                                          operation_lock=self.row['operation_lock'])
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertFalse(self.row['_restart']['selection_cleared'])
        self.assertIsNotNone(self.game.selection)

    async def arm_restart_eof(self):
        self.row['_decoder'] = b.ClientPlaintextDecoder(
            cipher_pointer='present_disabled', max_buffer=self.policy.MAX_BUFFER)
        mode = dict(closing=False, action=None, alive=True, source_error=False)
        def source():
            if mode['source_error']:
                raise ValueError('FIXTURE_SOURCE_CHANGED')
        async def owner(_):
            await asyncio.sleep(0)
            if mode['closing']:
                if mode['action'] is not None: mode['action']()
                return False
            return True
        self.producer.owner_guard = owner
        self.producer.owner_liveness_guard = lambda: mode['alive']
        self.producer.source_guard = self.producer.key_guard = source
        await self.dispatch(c2s(b.RESTART_REQUEST))
        mode['closing'] = True
        return mode

    async def test_drained_restart_actual_eof_during_owner_await_retained_alive(self):
        mode = await self.arm_restart_eof()
        before = self.writer.write.call_count
        read_task = asyncio.get_running_loop().create_future()
        self.row['_read_task'] = read_task
        mode['action'] = lambda: read_task.set_result(b'')
        async with self.row['operation_lock']:
            self.assertTrue(await self.producer._poll_checkpoint(self.writer, self.row, read_task,
                decoder=self.row['_decoder'], decoder_empty=self.row['_decoder'].buffered_bytes == 0,
                operation_lock=self.row['operation_lock']))
        self.assertTrue(self.row['eof'])
        self.assertEqual(self.row['account_terminal_reason'], 'DRAINED_RESTART_ACTUAL_EOF')
        self.assertEqual(self.writer.write.call_count, before)
        self.assertNotIn(id(self.writer), self.realm._quit)
        self.assertTrue(self.producer.owner_liveness_guard())

    async def test_restart_eof_handoff_pending_data_error_cancel_changed_undrained_refuse(self):
        mode = await self.arm_restart_eof()
        state = self.row['_restart']
        for case in ('pending', 'data', 'error', 'cancel', 'undrained', 'peer', 'frame'):
            future = asyncio.get_running_loop().create_future()
            self.row['_read_task'] = future
            peer = dict(self.row['peer']); frame = state['frame']
            def action():
                if case == 'pending': return
                if case == 'data': future.set_result(b'payload'); return
                if case == 'error': future.set_exception(ConnectionError('actual read failed')); return
                if case == 'cancel': future.cancel(); return
                future.set_result(b'')
                if case == 'undrained': state['response_drained'] = False
                if case == 'peer': self.row['peer']['client_port'] += 1
                if case == 'frame': state['frame'] = bytes(bytearray(frame))
            mode['action'] = action
            try:
                async with self.row['operation_lock']:
                    with self.subTest(case=case), self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
                        await self.producer._poll_checkpoint(self.writer, self.row, future,
                            decoder=self.row['_decoder'], decoder_empty=self.row['_decoder'].buffered_bytes == 0,
                            operation_lock=self.row['operation_lock'])
                self.assertFalse(self.row['eof'])
                self.assertNotIn('account_terminal_reason', self.row)
            finally:
                future.cancel()
                self.row['peer'].clear(); self.row['peer'].update(peer)
                state['response_drained'], state['frame'] = True, frame
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_restart_eof_retained_liveness_and_source_failure_stay_refused(self):
        mode = await self.arm_restart_eof()
        for case, expected in (('alive', 'CURRENT_RETAINED_OWNER_REQUIRED'),
                               ('source', 'FIXTURE_SOURCE_CHANGED')):
            future = asyncio.get_running_loop().create_future(); self.row['_read_task'] = future
            def action():
                future.set_result(b'')
                mode['alive'] = case != 'alive'
                mode['source_error'] = case == 'source'
            mode['action'] = action
            try:
                async with self.row['operation_lock']:
                    with self.subTest(case=case), self.assertRaisesRegex(ValueError, expected):
                        await self.producer._poll_checkpoint(self.writer, self.row, future,
                            decoder=self.row['_decoder'], decoder_empty=self.row['_decoder'].buffered_bytes == 0,
                            operation_lock=self.row['operation_lock'])
                self.assertFalse(self.row['eof'])
            finally:
                mode['alive'], mode['source_error'] = True, False
        self.assertEqual(self.writer.write.call_count, 1)


class RestartDisabledRouteTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = AttackIntentRouteTests.asyncSetUp
    dispatch = AttackIntentRouteTests.dispatch

    async def test_default_off_real_policy_and_route_remain_unbound(self):
        self.assertIsNone(self.producer.restart_policy)
        self.assertNotIn(b.RESTART_REQUEST, self.game.routes)
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'):
            await self.dispatch(c2s(b.RESTART_REQUEST))
        self.writer.write.assert_not_called()


class InventoryRestoreOnlyBrokerTests(unittest.IsolatedAsyncioTestCase):
    """Existing real retained-source fixture, actual broker/policy/Store only."""
    async def asyncSetUp(self):
        from tools.local_original_session import launcher_tests as fixture
        self.rebuild = types.MethodType(fixture.InventoryPersistenceProductTests.rebuild, self)
        await fixture.InventoryPersistenceProductTests.asyncSetUp(self)
        fixture.InventoryProductTests.product_clock(self)
        self.producer.key_guard = lambda: True

    async def adopt_restored(self):
        uid = self.realm.service(self.writer).snapshot().uid
        frame = self.producer._inventory_frame
        self.service.store.grant(uid, frame)
        async with self.row['operation_lock']:
            await self.producer._restore_inventory_selection(self.writer)
        self.assertIs(self.producer._inventory_restored, True)
        self.assertEqual(self.producer._inventory_frame, frame)
        return uid

    async def assert_terminal_no_retry(self, *, restore_only=True):
        self.assertTrue(self.service._closed)
        before = len(self.memory.calls)
        with self.assertRaises(ValueError):
            await self.producer.add_inventory(self.writer, restore_only=restore_only)
        self.assertEqual(len(self.memory.calls), before)

    async def test_real_restored_existing_only_uses_same_frame_once_and_original_reads(self):
        from tools.local_original_session import inventory_store
        await self.adopt_restored()
        frame = self.producer._inventory_frame
        stored = self.service.store.path.read_bytes()
        with mock.patch.object(inventory_store.InventoryStore, '_write',
                               side_effect=AssertionError('restore-only must never persist')):
            result = await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertEqual(result['proof_scope'], 'TRANSPORT_DRAIN_ONLY')
        self.assertIs(self.producer._inventory_restore_only, True)
        self.assertIs(self.producer._inventory_operation_frame, frame)
        self.assertIs(self.writer.write.call_args.args[0], frame)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(self.service.store.path.read_bytes(), stored)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer, restore_only=True)

    async def test_deleted_row_after_real_selection_is_never_regranted_or_sent(self):
        from tools.local_original_session import inventory_store
        uid = await self.adopt_restored()
        self.service.store.path.write_text('{"version":1,"inventories":[]}\n', encoding='ascii')
        stored = self.service.store.path.read_bytes()
        with mock.patch.object(inventory_store.InventoryStore, '_write',
                               side_effect=AssertionError('deleted row must remain deleted')):
            with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'):
                await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertIsNone(self.service.store.restore(uid))
        self.assertEqual(self.service.store.path.read_bytes(), stored)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        await self.assert_terminal_no_retry()

    async def test_mode_requires_literal_bool_and_real_restored_selection(self):
        for mode in (0, 1, None, 'true'):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'RESTORE_MODE_REQUIRED'):
                await self.producer.add_inventory(self.writer, restore_only=mode)
        self.assertFalse(self.producer._inventory_attempted)
        with self.assertRaisesRegex(ValueError, 'RESTORE_SELECTED_STORE_REQUIRED'):
            await self.producer.add_inventory(self.writer, restore_only=True)
        self.writer.write.assert_not_called()
        self.assertEqual(self.memory.calls, [])
        await self.assert_terminal_no_retry()


    async def test_await_checkpoint_mode_swap_stops_before_leaf(self):
        await self.adopt_restored()
        checkpoint = self.producer._checkpoint
        async def changed(writer, row):
            sample = await checkpoint(writer, row)
            self.producer._inventory_restore_only = False
            return sample
        self.producer._checkpoint = changed
        with self.assertRaisesRegex(ValueError, 'RESTORE_MODE_CHANGED'):
            await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_final_policy_callback_cannot_change_mode_before_write(self):
        await self.adopt_restored()
        original = self.policy.begin_write
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.producer._inventory_restore_only = False
            return result
        with mock.patch.object(self.policy, 'begin_write', changed):
            with self.assertRaisesRegex(ValueError, 'RESTORE_MODE_CHANGED'):
                await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertTrue(self.service._claimed)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_drain_mode_swap_is_terminal_without_resend(self):
        await self.adopt_restored()
        async def changed(): self.producer._inventory_restore_only = False
        self.writer.drain.side_effect = changed
        with self.assertRaisesRegex(ValueError, 'RESTORE_MODE_CHANGED'):
            await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertIsNone(self.producer._inventory_delivery_authority)
        await self.assert_terminal_no_retry()

    async def test_default_false_keeps_original_grant_call_without_keyword(self):
        from tools.local_original_session import inventory_store
        original = inventory_store.InventoryStore.grant
        calls = []
        def granted(store, *args, **kwargs):
            calls.append((args, kwargs)); return original(store, *args, **kwargs)
        with mock.patch.object(inventory_store.InventoryStore, 'grant', granted):
            result = await self.producer.add_inventory(self.writer)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertIs(self.producer._inventory_restore_only, False)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], {})
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))



    async def test_continuation_two_frame_swap_cannot_reauthorize_restored_mode(self):
        await self.adopt_restored()
        InventoryReadonlyAdmissionBrokerTests.changed_physical_read(self)
        deadline = self.product_ns + 10_000_000_000
        first = await self.producer.add_inventory(self.writer, deadline_ns=deadline, restore_only=True)
        self.assertEqual(first['phase'], 'ADMISSION')
        original_frame = self.producer._inventory_prewrite_refusal[4]
        self.assertIs(original_frame, self.producer._inventory_frame)
        self.memory.fault = None
        self.product_ns += 500_000_000
        replacement = bytes(bytearray(original_frame))
        self.producer._inventory_frame = self.producer._inventory_operation_frame = replacement
        self.producer._inventory_selection_binding = (*self.producer._inventory_selection_binding[:-1], replacement)
        before = len(self.memory.calls)
        with self.assertRaisesRegex(ValueError, 'PRE_WRITE_PROOF_REQUIRED'):
            await self.producer.add_inventory(self.writer, deadline_ns=deadline, restore_only=True)
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()




class InventoryReadonlyAdmissionBrokerTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = InventoryRestoreOnlyBrokerTests.asyncSetUp
    adopt_restored = InventoryRestoreOnlyBrokerTests.adopt_restored
    assert_terminal_no_retry = InventoryRestoreOnlyBrokerTests.assert_terminal_no_retry

    def changed_physical_read(self, *, postgrant=False):
        hits = [0]
        target = self.memory.header if postgrant else 0x250008
        def changed(at, size, raw):
            if at == target:
                hits[0] += 1
                if hits[0] == 2: return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = changed
        return hits

    async def pending_readonly(self, *, postgrant=False, adopt=True):
        if adopt: await self.adopt_restored()
        self.deadline = self.product_ns + 10_000_000_000
        self.stored = self.service.store.path.read_bytes()
        self.changed_physical_read(postgrant=postgrant)
        result = await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual((result['status'], result['phase'], result['reason']),
            ('PENDING', 'ADMISSION', 'INVENTORY_READONLY_ADMISSION_WAIT'))
        self.assertFalse(self.service._claimed or self.service._closed or self.producer._inventory_write_attempted)
        self.assertIsNone(self.row['policy_row'].drain_started_ns)
        self.assertFalse(self.row['operation_lock'].locked())
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.assertEqual(self.service.store.path.read_bytes(), self.stored)
        return self.producer._inventory_prewrite_refusal[0]

    async def strict_continuation(self):
        self.memory.fault = None
        self.product_ns += 500_000_000
        frame = self.producer._inventory_operation_frame
        result = await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertEqual(result['proof_scope'], 'TRANSPORT_DRAIN_ONLY')
        self.assertEqual(self.producer._inventory_deadline_ns, self.deadline)
        self.assertIs(self.writer.write.call_args.args[0], frame)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertTrue(self.service._claimed)
        self.assertEqual(self.service.last_result['status'], 'OBSERVED')
        self.assertEqual(self.service.store.path.read_bytes(), self.stored)

    async def test_original_pregrant_readonly_refusal_next_slot_fullproof_once_send(self):
        from tools.local_original_session import inventory
        error = await self.pending_readonly()
        self.assertIs(type(error), inventory.ReadOnlyPreWriteRefusal)
        self.assertEqual(error.stage, 'WORLD_TYPED')
        await self.strict_continuation()
        with self.assertRaises(ValueError): await self.producer.add_inventory(self.writer, restore_only=True)

    async def test_original_postreadonlygrant_refusal_does_not_persist_then_fullproof_once_send(self):
        from tools.local_original_session import inventory_store
        await self.adopt_restored()
        with mock.patch.object(inventory_store.InventoryStore, '_write',
                               side_effect=AssertionError('read-only grant must not persist')):
            error = await self.pending_readonly(postgrant=True, adopt=False)
            self.assertEqual(error.stage, 'FINAL_READBACK')
            await self.strict_continuation()

    async def test_original_deadline_closes_without_read_or_write_and_allows_only_terminal_report(self):
        from tools.local_original_session import inventory
        error = await self.pending_readonly(postgrant=True)
        before = len(self.memory.calls)
        self.product_ns = self.deadline
        with self.assertRaises(inventory.ReadOnlyPreWriteRefusal) as caught:
            await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.producer._inventory_deadline_ns, self.deadline)
        self.assertTrue(self.producer._inventory_admission_expired)
        self.assertTrue(self.service._closed)
        self.assertFalse(self.producer.failure.is_set())
        self.assertTrue(self.producer._inventory_refusal_current(error))
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_false_mode_same_physical_difference_is_terminal(self):
        await self.adopt_restored()
        self.changed_physical_read(postgrant=True)
        with self.assertRaisesRegex(ValueError, '^EDGE_TYPED_READ_CHANGED$'):
            await self.producer.add_inventory(self.writer, deadline_ns=self.product_ns + 10_000_000_000)
        self.assertIsNone(self.producer._inventory_prewrite_refusal)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry(restore_only=False)

    async def test_copied_last_result_cannot_authorize_stale_original_error(self):
        await self.pending_readonly()
        before = len(self.memory.calls)
        self.service.last_result = dict(self.service.last_result)
        bypass = self.service.validate_readonly_refusal = mock.Mock(return_value=True)
        self.product_ns += 500_000_000
        with self.assertRaises(ValueError):
            await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual(len(self.memory.calls), before)
        bypass.assert_not_called()
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_nonbool_expiry_never_enables_terminal_report_or_readmission(self):
        await self.pending_readonly()
        before = len(self.memory.calls)
        self.producer._inventory_admission_expired = 1
        with self.assertRaisesRegex(ValueError, 'INVENTORY_ADMISSION_EXPIRY_REQUIRED'):
            await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_forged_exact_exception_with_instance_fake_proof_is_terminal(self):
        from tools.local_original_session import inventory
        await self.adopt_restored()
        forged = inventory.ReadOnlyPreWriteRefusal('WORLD_TYPED')
        def false_leaf(*args, **kwargs): raise forged
        self.service.validate_pre_write_locked = false_leaf
        bypass = self.service.validate_readonly_refusal = mock.Mock(return_value=True)
        with self.assertRaisesRegex(ValueError, 'READONLY_REFUSAL_PROOF_REQUIRED'):
            await self.producer.add_inventory(self.writer, deadline_ns=self.product_ns + 10_000_000_000, restore_only=True)
        bypass.assert_not_called()
        self.assertEqual(self.memory.calls, [])
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_pending_source_change_refuses_before_fresh_query(self):
        await self.pending_readonly()
        before = len(self.memory.calls)
        def changed(): raise ValueError('FIXTURE_SOURCE_CHANGED')
        self.producer.source_guard = changed
        self.product_ns += 500_000_000
        with self.assertRaisesRegex(ValueError, 'FIXTURE_SOURCE_CHANGED'):
            await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_pending_owner_change_refuses_before_fresh_query(self):
        await self.pending_readonly()
        before = len(self.memory.calls)
        self.reader.member.process = object()
        self.product_ns += 500_000_000
        with self.assertRaises(ValueError):
            await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_pending_cancel_is_terminal_without_query_or_write(self):
        await self.pending_readonly()
        before = len(self.memory.calls)
        async def cancelled():
            asyncio.current_task().cancel('fixture readonly admission cancellation')
            return await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        with self.assertRaises(asyncio.CancelledError): await asyncio.create_task(cancelled())
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()
        await self.assert_terminal_no_retry()

    async def test_fullproof_success_then_ambiguous_drain_never_readmits(self):
        await self.pending_readonly()
        self.memory.fault = None; self.product_ns += 500_000_000
        self.writer.drain.side_effect = OSError('fixture ambiguous drain')
        with self.assertRaises(OSError):
            await self.producer.add_inventory(self.writer, deadline_ns=self.deadline, restore_only=True)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertTrue(self.producer._inventory_write_attempted)
        self.assertIsNone(self.producer._inventory_delivery_authority)
        await self.assert_terminal_no_retry()


class ItemUseIntentRouteTests(unittest.IsolatedAsyncioTestCase):
    dispatch = AttackIntentRouteTests.dispatch

    async def asyncSetUp(self):
        from tools.local_original_session import inventory_tests, inventory_store, item_use_session, launcher_tests
        await inventory_tests.GateTests.asyncSetUp(self)
        self.rebuild = types.MethodType(launcher_tests.InventoryProductTests.rebuild, self)
        await self.rebuild(store_policy=inventory_store.POLICY, item_use_policy=item_use_session.POLICY)
        self.use = self.producer._item_use_session

    def request(self, identifier=None):
        from tools.local_original_session import item_use_tests, inventory
        if identifier is None: identifier = inventory.validate_frame(self.producer._inventory_frame).identifier
        return c2s(b.ITEM_USE_REQUEST, item_use_tests.body(item_use_tests.scalar(17, 1), identifier))

    async def deliver(self):
        result = await self.producer.add_inventory(self.writer)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()

    async def test_actual_factory_grant_drain_received_0960_intent_then_old_move_alive_quit(self):
        await self.deliver()
        self.assertIs(self.realm._item_use_session, self.use)
        self.assertTrue(self.policy.item_use_intent)
        self.assertIn(b.ITEM_USE_REQUEST, self.game.routes)
        stored = self.service.store.path.read_bytes()
        reads = len(self.memory.calls)
        await self.dispatch(self.request())
        self.assertEqual(self.use.accepted_count, 1)
        report = self.producer.report()['item_use_intent']
        self.assertEqual(report['proof_scope'], 'VALIDATED_ITEM_USE_INTENT_ONLY')
        self.assertEqual(report['last_outcome']['kind'], 'ACCEPTED')
        self.assertEqual(self.policy.log[-1][0:3], ('rx', 14030, b.ITEM_USE_REQUEST))
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.assertEqual(len(self.memory.calls), reads)
        position = self.realm.service(self.writer).snapshot()
        move = pb.encode_message([pb.encode_uint32(1, position.packed), pb.encode_uint32(2, 2)])
        await self.dispatch(c2s(0x4e2b, move))
        self.assertEqual(self.writer.write.call_args.args[0], m.correction_frame(position))
        self.assertFalse(self.producer.failure.is_set())  # Existing no-edge correction remains unchanged.
        await self.dispatch(c2s(b.ALIVE_REQUEST))
        self.assertEqual(self.writer.write.call_args.args[0], b.ALIVE_FRAME)
        await self.dispatch(c2s(b.QUIT_REQUEST))
        self.assertEqual(self.writer.write.call_args.args[0], b.QUIT_SUCCESS_FRAME)
        self.assertTrue(self.realm.quit_state(self.writer)['response_drained'])
        self.assertEqual(self.service.store.path.read_bytes(), stored)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (3, 3))

    async def test_every_received_identical_payload_is_freshly_validated_no_replay_identifier(self):
        await self.deliver()
        raw = self.request()
        await self.dispatch(raw); await self.dispatch(raw)
        self.assertEqual(self.use.accepted_count, 2)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.realm.close(self.writer)
        self.assertFalse(self.use.metadata()['intent_recorded'])
        self.assertEqual(self.use.accepted_count, 2)
        self.producer._fail('FIXTURE_STORE_FATAL')
        self.assertTrue(self.use.closed)

    async def test_before_delivery_malformed_and_foreign_request_have_no_reply(self):
        # Use before the inventory delivery completed is refused alone (no reply, no raise).
        await self.dispatch(self.request())
        self.writer.write.assert_not_called()
        self.assertEqual(self.use.last_outcome.reason, 'ITEM_USE_CURRENT_CANONICAL_FRAME_REQUIRED')
        self.assertEqual(self.use.accepted_count, 0)
        await self.deliver()
        with self.assertRaises(ValueError): await self.dispatch(c2s(b.ITEM_USE_REQUEST, b'\x08\x80'))
        raw = self.request()
        payload = raw[10:10 + int.from_bytes(raw[8:10], 'little')]
        async with self.row['operation_lock']:
            with self.assertRaises(ValueError):
                await self.use.handle(object(), payload)
        self.assertEqual(self.use.accepted_count, 0)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    async def test_selection_lost_during_actual_owner_checkpoint_cannot_accept_or_reply(self):
        await self.deliver()
        calls = [0]
        async def changed(peer):
            calls[0] += 1
            if calls[0] == 3: self.realm.registry.selected.clear()
            return True
        self.producer.owner_guard = changed
        with self.assertRaises(ValueError): await self.dispatch(self.request())
        self.assertEqual(calls, [3])
        self.assertEqual(self.use.accepted_count, 0)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    async def test_default_off_retains_policy_and_route_unknown_and_explicit_close_is_terminal(self):
        from tools.local_original_session import inventory_store
        # Existing fixture owns inert socket placeholders; only their close methods are needed.
        self.producer.sockets = {port: types.SimpleNamespace(close=mock.Mock()) for port in b.PORTS}
        await self.producer.close()
        self.assertTrue(self.use.closed)
        await self.rebuild(store_policy=inventory_store.POLICY)
        self.assertIsNone(self.producer._item_use_session)
        self.assertIsNone(self.realm._item_use_session)
        self.assertFalse(self.policy.item_use_intent)
        self.assertNotIn(b.ITEM_USE_REQUEST, self.game.routes)
        with self.assertRaisesRegex(ValueError, 'GAME_OPCODE_UNBOUND'): await self.dispatch(self.request())
        self.assertNotIn('item_use_intent', self.producer.report())
        self.writer.write.assert_not_called()
        self.assertTrue(self.use.closed)  # Rebuilding never reopens the prior session.


class InventoryUpdateBrokerTests(unittest.IsolatedAsyncioTestCase):
    dispatch = AttackIntentRouteTests.dispatch
    request = ItemUseIntentRouteTests.request

    async def asyncSetUp(self):
        from tools.local_original_session import inventory_tests, inventory_store, item_use_session, launcher_tests
        await inventory_tests.GateTests.asyncSetUp(self)
        self.rebuild = types.MethodType(launcher_tests.InventoryProductTests.rebuild, self)
        await self.rebuild(store_policy=inventory_store.POLICY, item_use_policy=item_use_session.POLICY,
            inventory_update_policy=b.INVENTORY_UPDATE_POLICY)
        self.producer.key_guard = lambda: True  # Existing injected retained-key fixture contract.
        launcher_tests.InventoryProductTests.product_clock(self)
        await self.producer.add_inventory(self.writer)
        self.old = self.producer._inventory_current_frame
        self.initial = self.producer._inventory_frame
        self.delivery = self.producer._inventory_delivery_authority
        self.use = self.producer._item_use_session
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()

    async def update(self, **kwargs):
        from tools.local_original_session import inventory
        options = dict(item_identifier=inventory.validate_frame(self.old).identifier,
            changes={4: 2}, policy=b.INVENTORY_UPDATE_POLICY)
        options.update(kwargs)
        return await self.producer.update_inventory(self.writer, **options)

    def unchanged_initial(self):
        self.assertIs(self.producer._inventory_frame, self.initial)
        self.assertIs(self.producer._inventory_operation_frame, self.initial)
        self.assertIs(self.producer._inventory_delivery_authority, self.delivery)
        self.assertTrue(self.service._claimed)

    async def terminal(self):
        self.assertTrue(self.producer.failure.is_set())
        self.assertEqual(self.producer._inventory_update_operation['phase'], 'TERMINAL')
        self.assertIs(self.producer._inventory_current_frame, self.old)
        counts = self.writer.write.call_count, self.writer.drain.await_count
        with self.assertRaises(ValueError): await self.update()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), counts)

    async def test_real_store_cas_precedes_one_0965_drain_and_revokes_old_intent(self):
        from tools.local_original_session import inventory, inventory_update
        await self.dispatch(self.request())
        self.assertTrue(self.use.metadata()['intent_recorded'])
        count = len(self.memory.calls)
        position = self.realm.service(self.writer).snapshot()
        def write(wire):
            op = self.producer._inventory_update_operation
            self.assertTrue(self.row['operation_lock'].locked())
            self.assertEqual(op['phase'], 'WRITE_ATTEMPTED')
            self.assertIs(self.producer._inventory_current_frame, self.old)
            self.assertEqual(self.service.store.restore(position.uid), op['new'])
            self.assertIs(wire, op['wire'])
            fields = dict(inventory_update.validate_frame(wire).raw_fields)
            self.assertEqual(fields, {1: inventory.validate_frame(self.old).identifier, 4: 2})
        self.writer.write.side_effect = write
        result = await self.update()
        self.assertEqual(result['proof_scope'], 'TRANSPORT_DRAIN_ONLY')
        op = self.producer._inventory_update_operation
        self.assertEqual(op['phase'], 'DRAINED')
        self.assertIs(self.producer._inventory_current_frame, op['new'])
        self.assertEqual(op['sent_after'], op['sent_before'] + 1)
        self.assertTrue(all(op[k] is True for k in ('persist_attempted', 'persisted',
            'write_attempted', 'drain_returned', 'post_owner_verified')))
        self.assertFalse(self.use.metadata()['intent_recorded'])
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(len(self.memory.calls), count)  # Update adds no native memory sampler.
        self.unchanged_initial()
        # Fresh received Use binds the real drained new frame; old intent is not revived.
        self.writer.write.side_effect = None
        await self.dispatch(self.request())
        self.assertTrue(self.use.metadata()['intent_recorded'])
        await self.dispatch(c2s(b.ALIVE_REQUEST))
        await self.update(changes={4: 3})
        self.assertEqual(self.producer._inventory_update_operation['phase'], 'DRAINED')
        self.assertEqual(dict(inventory.validate_frame(self.producer._inventory_current_frame).raw_fields)[4], 3)

    async def test_invalid_noop_or_oversize_carry_never_enters_store_or_replaces_prior_state(self):
        from tools.local_original_session import inventory_store
        stored = self.service.store.path.read_bytes()
        for changes in ({}, {4: True}, {4: -1}, {4: 1 << 64}, {2: 2}, {5: 1 << 31},
                        {7: True}, {18: bytearray(b'x')}, {18: b'x' * 257}, {4: 1 << 63}):
            with self.subTest(changes=repr(changes)[:70]),                  mock.patch.object(inventory_store.InventoryStore, 'replace_existing',
                                   side_effect=AssertionError('invalid before IO')):
                with self.assertRaises(ValueError): await self.update(changes=changes)
        for options in (dict(item_identifier=True), dict(item_identifier=999), dict(policy=None),
                        dict(deadline_ns=True), dict(deadline_ns=self.product_ns + 10_000_000_001)):
            with self.subTest(options=options), self.assertRaises(ValueError): await self.update(**options)
        self.assertIsNone(self.producer._inventory_update_operation)
        self.assertEqual(stored, self.service.store.path.read_bytes())
        self.writer.write.assert_not_called()

    async def test_checkpoint_position_owner_source_and_frame_replacement_refuse_before_store(self):
        from dataclasses import replace
        from tools.local_original_session import inventory, inventory_store
        mover = self.realm.service(self.writer)
        source_pins = inventory.SOURCE_PINS
        mutations = (lambda: setattr(mover, '_position', replace(mover.snapshot())),
            lambda: self.realm.registry.selected.clear(),
            lambda: setattr(self.reader.member, 'process', object()),
            lambda: setattr(self.producer, '_inventory_current_frame', bytes(bytearray(self.old))),
            lambda: setattr(inventory, 'SOURCE_PINS', {key: '0' * 64 for key in source_pins}))
        original_checkpoint = self.producer._checkpoint
        initial_position = mover.snapshot(); selected = dict(self.realm.registry.selected)
        for mutation in mutations:
            reached = []
            async def changed(writer, row):
                result = await original_checkpoint(writer, row); reached.append(True); mutation(); return result
            with self.subTest(mutation=mutation), mock.patch.object(self.producer, '_checkpoint', changed),                  mock.patch.object(inventory_store.InventoryStore, '_write',
                    side_effect=AssertionError('authority changed before IO')):
                with self.assertRaises(ValueError): await self.update()
            self.assertEqual(reached, [True])
            inventory.SOURCE_PINS = source_pins
            mover._position = initial_position; self.realm.registry.selected.update(selected)
            self.reader.member.process = self.policy.handle
            self.producer._inventory_current_frame = self.old
        self.writer.write.assert_not_called()

    async def test_original_lock_replacement_while_waiting_refuses_before_store(self):
        original = self.row['operation_lock']; await original.acquire()
        task = asyncio.create_task(self.update())
        await asyncio.sleep(0)
        replacement = asyncio.Lock(); await replacement.acquire()
        self.row['operation_lock'] = replacement
        original.release()
        with self.assertRaises(ValueError): await task
        replacement.release()
        self.writer.write.assert_not_called()
        self.assertIsNone(self.producer._inventory_update_operation)

    async def test_store_deleted_or_conflicting_cannot_be_regranted(self):
        from tools.local_original_session import inventory, inventory_store
        store = self.service.store; contents = store.path.read_bytes()
        uid = self.realm.service(self.writer).snapshot().uid
        for conflict in (None, inventory.build_add(dict(inventory.validate_frame(self.old).raw_fields) | {4: 9})):
            if conflict is None: store.path.write_text('{"version":1,"inventories":[]}\n')
            else:
                store.path.write_bytes(contents); store.replace_existing(uid, self.old, conflict)
            preserved = store.path.read_bytes()
            with mock.patch.object(inventory_store.InventoryStore, '_write', side_effect=AssertionError('no recreate')):
                with self.assertRaises(ValueError): await self.update()
            self.assertEqual(store.path.read_bytes(), preserved)
            self.assertIsNone(self.producer._inventory_update_operation)
        self.writer.write.assert_not_called()

    async def test_store_io_failure_after_entry_terminal_no_send_or_retry(self):
        from tools.local_original_session import inventory_store
        with mock.patch.object(inventory_store.os, 'fsync', side_effect=OSError('actual temporary IO failure')):
            with self.assertRaises(OSError): await self.update()
        self.writer.write.assert_not_called()
        await self.terminal()

    async def test_after_persist_checkpoint_failure_never_rolls_back_or_retries(self):
        checkpoint = self.producer._checkpoint
        async def changed(writer, row):
            result = await checkpoint(writer, row)
            if self.producer._inventory_update_operation['persisted']:
                self.realm.registry.selected.clear()
            return result
        with mock.patch.object(self.producer, '_checkpoint', changed):
            with self.assertRaises(ValueError): await self.update()
        self.writer.write.assert_not_called()
        self.assertNotEqual(self.service.store.restore(self.delivery[0].uid), self.old)
        await self.terminal()

    async def test_begin_write_sync_cancel_or_deadline_expiry_never_writes(self):
        begin = self.policy.begin_write
        def cancelling(*args, **kwargs):
            result = begin(*args, **kwargs)
            asyncio.current_task().cancel('final policy callback')
            return result
        with mock.patch.object(self.policy, 'begin_write', cancelling):
            task = asyncio.create_task(self.update())
            with self.assertRaises(asyncio.CancelledError): await task
        self.writer.write.assert_not_called()
        await self.terminal()

    async def test_final_sync_source_deadline_expiry_after_reservation_write_zero(self):
        guard = self.producer.source_guard
        def expired():
            guard()
            op = self.producer._inventory_update_operation
            if op and op['phase'] == 'RESERVING': self.product_ns = op['deadline_ns']
        with mock.patch.object(self.producer, 'source_guard', expired):
            with self.assertRaisesRegex(ValueError, 'DEADLINE'): await self.update()
        self.writer.write.assert_not_called()
        await self.terminal()

    async def test_drain_ambiguity_is_one_attempt_never_promotes_or_retries(self):
        self.writer.drain.side_effect = OSError('unobserved transport drain')
        with self.assertRaises(OSError): await self.update()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        await self.terminal()

    async def test_post_drain_owner_loss_never_promotes_current_frame(self):
        async def changed():
            self.reader.member.process = object()
        self.writer.drain.side_effect = changed
        with self.assertRaises(ValueError): await self.update()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        await self.terminal()


class InventoryReselectionTests(unittest.IsolatedAsyncioTestCase):
    """Actual broker/Store/Restart/selected source; no listener, Native init or launcher."""
    async def asyncSetUp(self):
        from tools.local_original_session import inventory_tests
        await inventory_tests.GateTests.asyncSetUp(self)
        await self.rebuild()

    async def rebuild(self, *, enabled=True, saved=True):
        from tools.local_original_session import inventory, inventory_store, inventory_tests, item_use_session, restart
        retained, expected_uuid, path = self.reader.owner, self.realm.expected_uuid, self.realm.store.path
        self.options = dict(sockets={12000: object(), 14030: object()}, retained_owner=retained,
            owner_handle=retained.owner_handle, owner_job=retained.owner_job,
            owner_guard=lambda _: True, owner_liveness_guard=lambda: True, source_guard=lambda: None,
            key_guard=lambda: True, conversation_factory=lambda *_: None,
            expected_uuid=expected_uuid, store_path=path,
            inventory_policy=inventory.POLICY, inventory_frame=self.wire, inventory_reader=self.reader,
            inventory_store_policy=inventory_store.POLICY, item_use_policy=item_use_session.POLICY,
            inventory_update_policy=b.INVENTORY_UPDATE_POLICY, restart_policy=restart.POLICY,
            inventory_delivery_policy=b.INVENTORY_RESELECTION_DELIVERY,
            inventory_reselection_policy=b.INVENTORY_RESELECTION_POLICY if enabled else None)
        self.producer = b.PersistentBroker(**self.options)
        self.realm, self.policy = self.producer.realm, self.producer.policy
        if saved and self.producer._inventory_store.restore(self.realm.profile_uid) is None:
            # Explicit test input only; production reselection never grants.
            self.producer._inventory_store.grant(self.realm.profile_uid, self.wire)
        def sample(peer):
            return b.OwnerSample(retained, retained.owner_handle, retained.owner_job,
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
        admitted = boot(self.writer, peer)
        self.row = dict(writer=self.writer, policy_row=admitted, failed=False, joined=False,
            eof=False, operation_lock=asyncio.Lock(), peer=dict(connection_id=4, endpoint_port=14030,
                server_port=14030, client_port=peer.client_port, accepted_monotonic_ns=peer.accepted_ns))
        self.producer._claims[14030] = [self.row]
        self.game = self.realm.grant(self.writer, movement_owner_guard=lambda *_: True, connection_id=4)
        await self.game.received(types.SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))
        await self.select()
        self.service = self.producer._inventory_service
        self.memory = inventory_tests.Memory(self)
        self.reset_writes()

    def reset_writes(self):
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()

    async def dispatch(self, opcode, payload=b''):
        async with self.row['operation_lock']:
            frames = await self.game.received(types.SimpleNamespace(opcode=opcode, payload=payload))
            await self.producer._send(self.writer, self.row, frames, game=True,
                                     operation_lock=self.row['operation_lock'])
        return frames

    async def select(self):
        payload = pb.encode_bytes(1, self.realm.profile_name.encode()) + b'\x10\0\x18\0'
        return await self.dispatch(0x4e28, payload)

    async def add(self):
        result = await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertEqual(result['status'], 'COMMITTED')
        return result

    async def restart_reselect(self):
        await self.dispatch(b.RESTART_REQUEST)
        await self.select()
        self.service = self.producer._inventory_service
        return self.producer.inventory_selection_current(self.writer)

    async def test_actual_restart_new_selected_saved_restore_once_and_retired_evidence(self):
        initial = self.producer.inventory_selection_current(self.writer)
        await self.add()
        old = self.producer.inventory_selection_current(self.writer)
        old_evidence = (old.attempted, old.write_attempted, old.service._claimed,
            old.frame, old.operation_frame, old.current_frame, old.selection_binding, old.delivery_authority)
        game, account, store, reader = self.game, old.account, old.store, old.reader
        saved = store.path.read_bytes()
        await self.dispatch(b.RESTART_REQUEST)
        operation = old.update_operation
        with self.assertRaisesRegex(ValueError, 'INVENTORY_RESELECTION_UPDATE_ACTIVE_REQUIRED'):
            await self.producer.update_inventory(self.writer, item_identifier=1, changes={4: 1},
                                                 policy=b.INVENTORY_UPDATE_POLICY)
        self.assertIs(old.update_operation, operation)
        await self.select()
        self.service = self.producer._inventory_service
        new = self.producer.inventory_selection_current(self.writer)
        self.assertIs(new.previous, old)
        self.assertEqual(old.phase, 'RETIRED')
        self.assertTrue(old.service._closed and old.item_use_session.closed)
        self.assertIs(new.game, game); self.assertIs(new.account, account)
        self.assertIs(new.store, store); self.assertIs(new.reader, reader)
        self.assertIsNot(new.selected, old.selected); self.assertIsNot(new.mover, old.mover)
        self.assertIsNot(new.service, old.service); self.assertIsNot(new.item_use_session, old.item_use_session)
        self.assertIs(self.realm._item_use_session, new.item_use_session)
        self.assertFalse(new.attempted or new.service._claimed)
        self.assertTrue(new.restored)
        self.assertIs(new.selection_binding[7], new.selected)
        self.assertIs(new.selection_binding[8], new.service)
        self.reset_writes()
        await self.add()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertIs(new.current_frame, new.frame)
        self.assertEqual(store.path.read_bytes(), saved)
        for before, after in zip(old_evidence, (old.attempted, old.write_attempted, old.service._claimed,
                old.frame, old.operation_frame, old.current_frame, old.selection_binding, old.delivery_authority)):
            self.assertIs(before, after)
        with self.assertRaises(ValueError): await self.add()

    async def test_on_first_missing_row_and_retired_before_add_never_fallback_or_mutate_once(self):
        self.producer._inventory_store.path.unlink()
        await self.rebuild(saved=False)
        initial = self.producer.inventory_selection_current(self.writer)
        self.assertIsNone(initial.frame); self.assertIsNone(initial.selection_binding)
        self.assertFalse(initial.restored or initial.attempted)
        self.reset_writes()
        for mode in (False, True):
            with self.assertRaises(ValueError):
                await self.producer.add_inventory(self.writer, restore_only=mode)
        self.writer.write.assert_not_called()
        self.assertFalse(initial.attempted or initial.service._claimed)
        self.assertFalse(initial.store.path.exists())
        await self.dispatch(b.RESTART_REQUEST)
        self.assertEqual(initial.phase, 'RETIRED')
        self.reset_writes()
        for mode in (False, True):
            with self.assertRaises(ValueError):
                await self.producer.add_inventory(self.writer, restore_only=mode)
        self.assertFalse(initial.attempted or initial.service._claimed)
        self.writer.write.assert_not_called()
        self.assertIsNone(self.producer.inventory_selection_current(self.writer))
        await self.select()
        new = self.producer.inventory_selection_current(self.writer)
        self.assertIs(new.previous, initial)
        self.assertIsNone(new.frame); self.assertIsNone(new.selection_binding)
        self.assertFalse(new.restored or new.attempted or new.service._claimed)
        self.assertFalse(new.store.path.exists())

    async def test_off_default_once_and_explicit_dependency_policy_validation(self):
        await self.rebuild(enabled=False)
        await self.add()
        old = self.producer._inventory_generation
        await self.dispatch(b.RESTART_REQUEST)
        await self.select()
        self.assertIs(self.producer._inventory_generation, old)
        self.assertTrue(old.attempted)
        self.assertIsNone(self.producer.inventory_selection_current(self.writer))
        with self.assertRaises(ValueError): await self.add()
        for changes in (dict(inventory_reselection_policy=True),
                        dict(inventory_reselection_policy=b.INVENTORY_RESELECTION_POLICY,
                             inventory_delivery_policy=None),
                        dict(inventory_reselection_policy=b.INVENTORY_RESELECTION_POLICY, restart_policy=None),
                        dict(inventory_reselection_policy=b.INVENTORY_RESELECTION_POLICY, inventory_store_policy=None)):
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                b.PersistentBroker(**dict(self.options, **changes))

    async def test_new_generation_owner_cancel_and_drain_failure_are_terminal_without_old_reset(self):
        await self.add()
        old = self.producer.inventory_selection_current(self.writer)
        await self.dispatch(b.RESTART_REQUEST)
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.producer._sample
        async def held(row):
            result = await original(row)
            entered.set()
            await release.wait()
            return result
        self.producer._sample = held
        task = asyncio.create_task(self.select())
        await asyncio.wait_for(entered.wait(), 2)
        preparing = self.producer._inventory_generation
        self.assertEqual(preparing.phase, 'PREPARING')
        self.assertIsNone(self.producer.inventory_selection_current(self.writer))
        task.cancel('reselection fixture cancel')
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(preparing.phase, 'TERMINAL')
        self.assertTrue(preparing.service._closed and preparing.item_use_session.closed)
        self.assertTrue(old.service._closed and old.attempted and old.service._claimed)
        self.assertEqual(old.phase, 'RETIRED')
        self.producer._sample = original
        with self.assertRaises(ValueError): await self.add()

    async def test_restore_checkpoint_poll_waits_then_exposes_active_generation(self):
        from tools.local_original_session.launcher import ManualMoveRequests
        await self.add()
        old = self.producer.inventory_selection_current(self.writer)
        await self.dispatch(b.RESTART_REQUEST)
        self.reset_writes()
        entered, release = asyncio.Event(), asyncio.Event()
        checkpoint = self.producer._checkpoint
        async def held(writer, row):
            result = await checkpoint(writer, row)
            entered.set()
            await release.wait()
            return result
        self.producer._checkpoint = held
        task = asyncio.create_task(self.select())
        await asyncio.wait_for(entered.wait(), 2)
        try:
            preparing = self.producer._inventory_generation
            hook = ManualMoveRequests.__new__(ManualMoveRequests)
            hook.inventory_broker, hook.inventory_reselection_policy = self.producer, b.INVENTORY_RESELECTION_POLICY
            hook.consumer = types.SimpleNamespace(reader=self.reader)
            self.assertEqual(preparing.phase, 'PREPARING')
            self.assertIs(preparing.previous, old)
            self.assertIsNone(self.producer.inventory_selection_current(self.writer))
            self.assertIsNone(hook._inventory_reselection_current(self.writer))
            self.writer.write.assert_not_called(); self.writer.drain.assert_not_called()
            self.assertFalse(preparing.attempted or preparing.service._claimed)
        finally:
            release.set()
            await task
            self.producer._checkpoint = checkpoint
        active = self.producer.inventory_selection_current(self.writer)
        self.assertIs(active, preparing)
        self.assertEqual(active.phase, 'ACTIVE')
        self.assertIs(hook._inventory_reselection_current(self.writer), active)
        self.assertTrue(active.restored)
        self.assertIs(active.selection_binding[7], active.selected)
        self.assertFalse(active.attempted or active.service._claimed)

    async def test_new_generation_restore_source_owner_and_send_failure_no_retry(self):
        for mode in ('source', 'owner'):
            if mode == 'owner':
                await self.rebuild()
            await self.add()
            previous = self.producer.inventory_selection_current(self.writer)
            await self.dispatch(b.RESTART_REQUEST)
            error = ValueError('fixture source invalid')
            if mode == 'source':
                def fail_source(): raise error
                self.producer.source_guard = fail_source
            else:
                self.producer.owner_guard = lambda _: False
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                await self.select()
            current = self.producer._inventory_generation
            self.assertEqual(current.phase, 'TERMINAL')
            self.assertTrue(current.service._closed and current.item_use_session.closed)
            self.assertEqual(previous.phase, 'RETIRED')
            self.assertTrue(previous.attempted and previous.service._claimed)
            with self.assertRaises(ValueError): await self.add()
        await self.rebuild()
        await self.add()
        old = self.producer.inventory_selection_current(self.writer)
        new = await self.restart_reselect()
        self.reset_writes()
        error = OSError('fixture ambiguous drain')
        self.writer.drain.side_effect = error
        with self.assertRaises(OSError) as caught: await self.add()
        self.assertIs(caught.exception, error)
        self.assertEqual(new.phase, 'TERMINAL')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertTrue(new.service._closed and new.item_use_session.closed)
        self.assertEqual(old.phase, 'RETIRED')
        self.assertTrue(old.service._claimed and old.attempted)
        with self.assertRaises(ValueError): await self.add()


if __name__ == '__main__':
    unittest.main()
