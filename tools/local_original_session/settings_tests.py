"""Pure parser/route/fake-writer/tempfile checks; no ports, game or native."""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from tools.local_original_session import settings as s, broker as b
from tools.local_persistent_broker_policy import policy as p


def payload(first=b'\xff\0\x80', second=None):
    fields = [s.pb.encode_bytes(1, first)]
    if second is not None: fields.append(s.pb.encode_bytes(2, second))
    return s.pb.encode_message(fields)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        self.profile.write_bytes(b'preserved-character-fixture')
        self.positions = self.profile.with_name('positions.json')
        self.positions.write_bytes(b'preserved-position-fixture')
        self.path = self.profile.with_name('account-settings.bin')
        self.account = str(uuid.uuid4())
        self.store = s.SettingsStore(self.path, self.account, profile_path=self.profile)

    def test_binary_presence_last_request_and_large_blob_roundtrip_without_text_decode(self):
        for raw, optional in ((payload(b''), False), (payload(b'', b''), True),
                              (payload(b'\xff' * 5000, b'\x80\0'), True)):
            record = s.parse(raw)
            self.store.save(record)
            loaded = self.store._load()
            self.assertEqual(hashlib.sha256(loaded.raw).digest(), hashlib.sha256(raw).digest())
            self.assertEqual(loaded.metadata()['field2_present'], optional)
            json.dumps(self.store.metadata())  # Metadata contains no raw bytes.
        self.assertEqual(self.profile.read_bytes(), b'preserved-character-fixture')
        self.assertEqual(self.positions.read_bytes(), b'preserved-position-fixture')

    def test_missing_required_wrong_wire_unknown_field_and_oversize_refuse(self):
        for raw in (b'', s.pb.encode_bytes(2, b''), s.pb.encode_uint32(1, 1),
                    payload() + s.pb.encode_bytes(3, b''), b'\0' * (s.LIMITS.max_body + 1)):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError): s.parse(raw)
        self.assertFalse(self.path.exists())

    def test_account_corruption_and_replace_failure_preserve_store_and_latch_fatal(self):
        self.store.save(s.parse(payload()))
        before = hashlib.sha256(self.path.read_bytes()).digest()
        with self.assertRaises(ValueError):
            s.SettingsStore(self.path, str(uuid.uuid4()), profile_path=self.profile)
        with patch.object(s.os, 'replace', side_effect=OSError('fixture')):
            with self.assertRaises(OSError): self.store.save(s.parse(payload(b'changed')))
        self.assertTrue(self.store.failed)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(), before)
        self.assertFalse(list(self.path.parent.glob('.settings-*.tmp')))
        with self.assertRaises(ValueError): self.store.save(s.parse(payload()))
        self.path.write_bytes(b'corrupt-fixture')
        with self.assertRaises(ValueError):
            s.SettingsStore(self.path, self.account, profile_path=self.profile)
        self.assertEqual(self.path.read_bytes(), b'corrupt-fixture')


class Writer:
    def __init__(self, owner):
        self.owner, self.wires = owner, []
        self.exit_on_drain, self.drain_failure = False, False
        self.transport = SimpleNamespace(get_write_buffer_size=lambda: 0)
    def write(self, wire): self.wires.append(bytes(wire))
    async def drain(self):
        if self.drain_failure: raise OSError('fixture')
        if self.exit_on_drain: self.owner.alive = False


class SourceRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'characters.json'
        self.alive = True
        self.owner, self.handle, self.job = object(), object(), object()
        self.proof_changes = {}
        self.broker = b.PersistentBroker(sockets={12000: object(), 14030: object()},
            retained_owner=self.owner, owner_handle=self.handle, owner_job=self.job,
            owner_guard=lambda peer: self.alive, owner_liveness_guard=lambda: self.alive,
            owner_exit_proof=self.exit_proof, source_guard=lambda: None,
            conversation_factory=lambda *args: None, expected_uuid=str(uuid.uuid4()),
            store_path=self.profile, settings_path=self.profile.with_name('account-settings.bin'))
        self.realm = self.broker.realm
        self.realm.store.create(b.ack.realm.Creation(self.realm.profile_name, 0, 0, (13,) * 6))
        self.writer = Writer(self)
        now = time.monotonic_ns()
        peer = p.Peer(12000, 52001, now)
        bucket = lambda: p.Bucket(131070, 65536, now)
        connection = p.Connection(self.writer, peer, 1, bucket(), bucket(), bucket(), bucket(), rx_boot=2, tx_boot=3)
        self.broker.policy.rows[12000].append(connection)
        self.row = dict(writer=self.writer, policy_row=connection, joined=False, failed=False, eof=False,
            peer=dict(server_port=12000, client_port=52001, accepted_monotonic_ns=now, connection_id=4))
        async def account(writer): return await self.broker._account_owner(writer, self.row)
        async def selected(writer, position): return await self.broker._movement_owner(writer, self.row, position)
        self.game = self.realm.grant(self.writer, movement_owner_guard=selected, account_owner_guard=account)
        login = b.login.LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()
        await self.receive(0x263, login)

    def exit_proof(self):
        return dict(dict(status='VERIFIED', owner=self.owner, handle=self.handle, job=self.job,
                    signaled=True, identity_verified=True, job_empty=True, forced_cleanup_requested=False,
                    exit_code=0, observed_ns=time.monotonic_ns()), **self.proof_changes)

    async def receive(self, opcode, raw=b''):
        sample = await self.broker._checkpoint(self.writer, self.row)
        self.broker.policy.received_frame(self.writer, sample, opcode, 10 + len(raw), time.monotonic_ns())
        return await self.game.received(SimpleNamespace(opcode=opcode, payload=raw))

    async def select(self):
        raw = s.pb.encode_message([s.pb.encode_bytes(1, self.realm.profile_name.encode()),
                                   s.pb.encode_uint32(2, 0), s.pb.encode_uint32(3, 0)])
        await self.receive(0x4e28, raw)

    async def test_settings_account_scope_preserves_binary_and_emits_no_reply(self):
        before = hashlib.sha256(self.profile.read_bytes()).digest()
        self.assertIsNone(self.game.selection)
        raw = payload(b'\xff' * 5000, b'\x80\0')
        self.assertEqual(await self.receive(s.OPCODE, raw), ())
        self.assertEqual(self.realm.settings.metadata()['committed'], 1)
        self.assertEqual(hashlib.sha256(self.realm.settings._load().raw).digest(), hashlib.sha256(raw).digest())
        self.assertEqual(self.writer.wires, [])
        self.assertEqual(hashlib.sha256(self.profile.read_bytes()).digest(), before)
        foreign = object()
        game = self.realm.grant(foreign)
        with self.assertRaisesRegex(ValueError, 'SAME_0263_BOUND_ACCOUNT_WRITER_REQUIRED'):
            await game.received(SimpleNamespace(opcode=s.OPCODE, payload=raw))

    async def test_settings_save_failure_prevents_later_quit_success(self):
        await self.select()
        with patch.object(s.os, 'replace', side_effect=OSError('fixture')):
            with self.assertRaisesRegex(ValueError, 'SETTINGS_PERSISTENCE_FATAL'):
                await self.receive(s.OPCODE, payload())
        with self.assertRaisesRegex(ValueError, 'SETTINGS_PERSISTENCE_FATAL'):
            await self.receive(b.QUIT_REQUEST)
        self.assertEqual(self.writer.wires, [])
        self.assertEqual(self.realm._quit, {})

    async def test_quit_requires_empty_selected_current_owner_and_is_terminal(self):
        with self.assertRaisesRegex(ValueError, 'QUIT_SELECTED_OWNER_REQUIRED'):
            await self.receive(b.QUIT_REQUEST)
        await self.select()
        with self.assertRaisesRegex(ValueError, 'QUIT_EMPTY_SOURCE_BODY_REQUIRED'):
            await self.receive(b.QUIT_REQUEST, b'\0')
        replies = await self.receive(b.QUIT_REQUEST)
        self.assertEqual(replies, (b'\x08\0\xef\x4e\x08\x2d\0\0',))
        self.realm.validate_reply(replies[0], writer=self.writer)
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_SESSION'):
            await self.receive(b.QUIT_REQUEST)
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_SESSION'):
            await self.receive(s.OPCODE, payload())

    async def test_exact_quit_drain_exit_then_eof_uses_terminal_proof_without_alive_sample(self):
        await self.select()
        await self.receive(s.OPCODE, payload())
        replies = await self.receive(b.QUIT_REQUEST)
        self.writer.exit_on_drain = True
        await self.broker._send(self.writer, self.row, replies, game=True)
        self.assertFalse(self.alive)
        self.assertTrue(self.realm.quit_state(self.writer)['response_drained'])
        self.assertIsNone(self.row['policy_row'].drain_started_ns)
        await self.broker._complete_eof(self.writer, self.row, decoder_empty=True)
        self.assertTrue(self.row['eof'])
        self.assertTrue(self.row['quit_terminal_exit'])
        self.assertFalse(self.broker.failure.is_set())

    async def test_drained_empty_quit_duplicate_keeps_first_state_and_one_response_then_eof(self):
        await self.select(); await self.receive(s.OPCODE, payload())
        replies = await self.receive(b.QUIT_REQUEST)
        state = self.realm.quit_state(self.writer)
        await self.broker._send(self.writer, self.row, replies, game=True)
        before = dict(state)
        for _ in range(2):
            duplicate = await self.receive(b.QUIT_REQUEST)
            self.assertEqual(duplicate, ())
            await self.broker._send(self.writer, self.row, duplicate, game=True)
        self.assertIs(self.realm.quit_state(self.writer), state)
        self.assertEqual({key: value for key, value in state.items() if key != 'duplicate_requests'},
                         {key: value for key, value in before.items() if key != 'duplicate_requests'})
        self.assertEqual(state['duplicate_requests'], 2)
        self.assertEqual(self.writer.wires, [b.QUIT_SUCCESS_FRAME])
        self.assertEqual(self.realm.settings.committed, 1)
        self.assertEqual(self.realm.quit_report()['duplicate_policy'], 'LOCAL_DRAINED_EMPTY_QUIT_NO_EFFECT')
        state['duplicate_requests'] = b.MAX_COUNTER
        await self.receive(b.QUIT_REQUEST)
        self.assertEqual(state['duplicate_requests'], b.MAX_COUNTER)
        self.alive = False
        await self.broker._complete_eof(self.writer, self.row, decoder_empty=True)
        self.assertTrue(self.row['quit_terminal_exit'])

    async def test_duplicate_quit_refuses_undrained_nonempty_other_opcode_and_changed_owner(self):
        await self.select(); replies = await self.receive(b.QUIT_REQUEST)
        state = self.realm.quit_state(self.writer)
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_SESSION'):
            await self.receive(b.QUIT_REQUEST)
        await self.broker._send(self.writer, self.row, replies, game=True)
        with self.assertRaisesRegex(ValueError, 'QUIT_EMPTY_SOURCE_BODY_REQUIRED'):
            await self.receive(b.QUIT_REQUEST, b'\0')
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_SESSION'):
            await self.receive(s.OPCODE, payload())
        state['response_queue_empty'] = False
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_SESSION'):
            await self.receive(b.QUIT_REQUEST)
        state['response_queue_empty'] = True
        bound = self.realm._account_bound[id(self.writer)]
        self.realm._account_bound[id(self.writer)] = (object(), self.game)
        with self.assertRaisesRegex(ValueError, 'SAME_0263_BOUND_ACCOUNT_WRITER_REQUIRED'):
            await self.receive(b.QUIT_REQUEST)
        self.realm._account_bound[id(self.writer)] = bound
        state['uid'] += 1
        with self.assertRaisesRegex(ValueError, 'QUIT_CURRENT_SELECTED_AUTHORITY_REQUIRED'):
            await self.receive(b.QUIT_REQUEST)
        state['uid'] -= 1
        self.alive = False
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            await self.receive(b.QUIT_REQUEST)
        self.alive = True
        self.realm._settings_failed = True
        with self.assertRaisesRegex(ValueError, 'SETTINGS_PERSISTENCE_FATAL'):
            await self.receive(b.QUIT_REQUEST)
        self.assertEqual(state['duplicate_requests'], 0)
        self.assertEqual(self.writer.wires, [b.QUIT_SUCCESS_FRAME])

    async def test_no_quit_or_no_drained_reply_never_qualifies_false_owner_eof(self):
        self.alive = False
        with self.assertRaisesRegex(ValueError, 'CURRENT_RETAINED_OWNER_REQUIRED'):
            await self.broker._complete_eof(self.writer, self.row, decoder_empty=True)
        pending = asyncio.get_running_loop().create_future()
        with self.assertRaisesRegex(ValueError, 'CURRENT_OWNER_REQUIRED'):
            await self.broker._poll_checkpoint(self.writer, self.row, pending, decoder_empty=True)
        self.assertFalse(pending.done())
        pending.cancel()
        self.alive = True
        await self.select(); await self.receive(b.QUIT_REQUEST)
        self.alive = False
        with self.assertRaisesRegex(ValueError, 'VERIFIED_QUIT_DRAIN_EXIT_REQUIRED'):
            await self.broker._complete_eof(self.writer, self.row, decoder_empty=True)
        self.assertFalse(self.row['eof'])

    async def test_exit_poll_before_actual_eof_waits_only_for_terminal_empty_read(self):
        await self.select(); replies = await self.receive(b.QUIT_REQUEST)
        await self.broker._send(self.writer, self.row, replies, game=True)
        self.alive = False
        reader = asyncio.get_running_loop().create_future()
        poll = asyncio.create_task(self.broker._poll_checkpoint(
            self.writer, self.row, reader, decoder_empty=True))
        await asyncio.sleep(0)
        self.assertFalse(poll.done()); self.assertFalse(self.row['eof'])
        reader.set_result(b'')
        self.assertTrue(await poll)
        self.assertTrue(self.row['eof'])
        self.assertTrue(self.row['quit_terminal_exit'])
        self.assertEqual(self.writer.wires, [b.QUIT_SUCCESS_FRAME])

    async def test_terminal_poll_rejects_payload_and_native_exit_join_preserves_task(self):
        await self.select(); replies = await self.receive(b.QUIT_REQUEST)
        await self.broker._send(self.writer, self.row, replies, game=True)
        self.alive = False
        reader = asyncio.get_running_loop().create_future()
        poll = asyncio.create_task(self.broker._poll_checkpoint(
            self.writer, self.row, reader, decoder_empty=True))
        self.row['task'] = poll
        self.broker._claims[12000].append(self.row)
        joining = asyncio.create_task(self.broker.join_quit_exit())
        await asyncio.sleep(0); await asyncio.sleep(0)
        self.assertFalse(joining.done()); self.assertFalse(poll.cancelled())
        reader.set_result(b'not-eof')
        with self.assertRaisesRegex(ValueError, 'QUIT_TERMINAL_EOF_REQUIRED'):
            await poll
        self.assertEqual(await joining, dict(eligible=1, joined=1))
        self.assertFalse(self.row['eof'])

    async def test_drain_error_or_wrong_exit_proof_never_finalizes_quit(self):
        await self.select(); replies = await self.receive(b.QUIT_REQUEST)
        self.writer.drain_failure = True
        with self.assertRaises(OSError): await self.broker._send(self.writer, self.row, replies, game=True)
        self.assertFalse(self.realm.quit_state(self.writer)['response_drain_returned'])
        for changes in (dict(handle=object()), dict(owner=object()), dict(job_empty=False),
                        dict(identity_verified=False), dict(exit_code=1), dict(observed_ns=0),
                        dict(forced_cleanup_requested=True), dict(status='UNKNOWN')):
            self.proof_changes = changes
            with self.assertRaisesRegex(ValueError, 'QUIT_RETAINED_EXIT_UNVERIFIED'):
                self.broker.policy._verified_exit(self.exit_proof(), time.monotonic_ns())
        self.assertFalse(self.row['eof'])
