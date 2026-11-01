"""Explicit synthetic spawn/real realm routes only; no listener/native/UI."""
import tempfile
import time
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

from tools.local_original_session import broker as b, npc
from tools.local_own_login_request.codec import LocalLoginRequest


def fields(uid=2):
    # Every required value is explicit synthetic local configuration. No player
    # profile, NPC f2, official stats or inferred template defaults are copied.
    return {1: 0x80b6803c, 2: uid, 3: 56, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0,
            9: 'Synthetic NPC', 10: '', 11: 0, 12: 0, 13: 0, 14: False,
            15: False, 16: False, 17: False, 18: False, 19: 0, 20: '', 21: '',
            22: 0, 23: 0, 24: 0, 27: 0, 28: 0, 39: 0}


def spawn(values=None):
    return npc.NpcSpawn(fields() if values is None else values, map_id=0, policy=npc.POLICY)


class SpawnTests(unittest.TestCase):
    def test_exact_schema_and_immutable_explicit_values(self):
        values = fields()
        candidate = spawn(values)
        values[3] = 57
        self.assertEqual(candidate.fields[3], 56)
        with self.assertRaises(TypeError):
            candidate.fields[39] = 1
        # Actual reviewed source evidence and independent persisted data pins;
        # no source-ready mock on this construction/frame path.
        wire = npc.prepare((candidate,), self_uid=1)[0][1]
        self.assertEqual(int.from_bytes(wire[:2], 'little'), len(wire))
        self.assertEqual(wire[2:4], b'\x96\x4e')
        self.assertEqual(b.session.world.decode_payload(0x4e96, wire[4:-2]), fields())

    def test_missing_optional_override_and_wrong_dispatch_never_build(self):
        for change in ({16: True}, {21: 'not-empty'}, {39: -1}, {39: 1}, {3: 57},
                       {69: 56}, {2: 0}, {2: 1 << 32}, {2: True}, {1: -1}, {5: -1}, {5: 8}):
            values = fields(); values.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                spawn(values)
        for number in npc.FIELDS:
            values = fields(); del values[number]
            with self.subTest(missing=number), self.assertRaises(ValueError):
                spawn(values)
        with self.assertRaisesRegex(ValueError, 'NPC_MAP0_ONLY'):
            npc.NpcSpawn(fields(), map_id=1, policy=npc.POLICY)
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_NPC_LOCAL_POLICY_REQUIRED'):
            npc.NpcSpawn(fields(), map_id=0, policy='official-default')

    def test_no_implicit_enable_source_bypass_collision_duplicate_or_growth(self):
        self.assertEqual(npc.prepare((), self_uid=1), ())
        with mock.patch.object(npc, 'DISPATCH_SHA', None):
            with self.assertRaisesRegex(ValueError, 'UNSAFE_NOT_EMITTED'):
                spawn().frame()
        for candidates, reason in (((spawn(fields(1)),), 'NPC_SELF_UID_COLLISION'),
                                   ((spawn(), spawn()), 'NPC_DUPLICATE_UID'),
                                   ((spawn(), spawn(fields(3))), 'NPC_BOUNDED_EXPLICIT_TUPLE_REQUIRED')):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                npc.prepare(candidates, self_uid=1)


class RealmSpawnTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Source readiness is independently tested against final contract. These
        # route tests exercise exact synthetic fields without an LC process.
        self.pin = mock.patch.object(npc, 'source_ready')
        self.pin.start(); self.addCleanup(self.pin.stop)
        self.realm = b.LocalRealm(str(uuid.uuid4()), Path(self.temp.name) / 'characters.json',
                                  npc_spawns=(spawn(),))
        self.writer = types.SimpleNamespace(transport=types.SimpleNamespace(get_write_buffer_size=lambda: 0),
                                            write=mock.Mock(), drain=mock.AsyncMock())
        self.allowed, self.mutation = True, None

        async def owner(writer, position):
            self.assertIs(writer, self.writer)
            if self.mutation:
                self.mutation()
            return self.allowed

        self.realm.store.create(b.ack.realm.Creation(self.realm.profile_name, 0, 0, (13,) * 6))
        self.game = self.realm.grant(self.writer, movement_owner_guard=owner)
        await self.game.received(types.SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))

    async def selected(self):
        pb = b.ack.realm.pb
        payload = pb.encode_message([pb.encode_bytes(1, self.realm.profile_name.encode()),
                                     pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        return await self.game.received(types.SimpleNamespace(opcode=0x4e28, payload=payload))

    async def test_selected_route_emits_exact_fifth_frame_and_preserves_saved_position(self):
        before = self.realm.store.path.read_bytes()
        frames = await self.selected()
        self.assertEqual([int.from_bytes(frame[2:4], 'little') for frame in frames],
                         [0x4e29, 0x4e95, 0x4e38, 0x4e96, 0x4e96])
        self.assertEqual(b.session.world.decode_payload(0x4e96, frames[4][4:-2]), fields())
        for frame in frames:
            self.realm.validate_reply(frame, writer=self.writer)
        self.assertEqual(self.realm.store.path.read_bytes(), before)
        self.assertFalse(self.realm.positions.path.exists())
        self.assertEqual(self.realm.service(self.writer).snapshot().uid, 1)

    async def test_owner_loss_or_mutation_after_await_prepares_no_npc_frame(self):
        self.allowed = False
        with self.assertRaisesRegex(ValueError, 'NPC_CURRENT_SELECTED_OWNER_REQUIRED'):
            await self.selected()
        self.assertEqual(self.realm._npc_frames, {})

    async def test_selection_loss_during_owner_await_never_prepares_frame(self):
        self.mutation = self.realm.registry.selected.clear
        with self.assertRaisesRegex(ValueError, 'NPC_CURRENT_SELECTED_AUTHORITY_REQUIRED'):
            await self.selected()
        self.assertEqual(self.realm._npc_frames, {})

    async def test_foreign_writer_changed_frame_and_terminal_fatal_selection_loss(self):
        wire = (await self.selected())[-1]
        for other in (None, object()):
            with self.assertRaises(ValueError):
                self.realm.validate_reply(wire, writer=other)
        changed = bytearray(wire); changed[5] ^= 1
        with self.assertRaises(ValueError):
            self.realm.validate_reply(changed, writer=self.writer)
        service = self.realm.service(self.writer)
        for change, undo in ((lambda: self.realm._quit.update({id(self.writer): {}}), self.realm._quit.clear),
                             (lambda: setattr(service, 'fatal', True), lambda: setattr(service, 'fatal', False)),
                             (lambda: setattr(self.realm, '_settings_failed', True),
                              lambda: setattr(self.realm, '_settings_failed', False))):
            change()
            with self.assertRaisesRegex(ValueError, 'NPC_CURRENT_SELECTED_AUTHORITY_REQUIRED'):
                self.realm.validate_reply(wire, writer=self.writer)
            undo()
        self.realm.registry.selected.clear()
        with self.assertRaisesRegex(ValueError, 'NPC_CURRENT_SELECTED_AUTHORITY_REQUIRED'):
            self.realm.validate_reply(wire, writer=self.writer)

    async def test_close_discards_bound_frames_and_old_writer_cannot_reuse(self):
        wire = (await self.selected())[-1]
        self.realm.close(self.writer)
        self.assertEqual(self.realm._npc_frames, {})
        with self.assertRaises(ValueError):
            self.realm.validate_reply(wire, writer=self.writer)

    async def test_checkpoint_selection_loss_prevents_actual_write(self):
        wire = (await self.selected())[-1]
        fake = object.__new__(b.PersistentBroker)
        fake._npc_respawn = None
        fake.realm = self.realm
        fake.policy = types.SimpleNamespace(begin_write=mock.Mock())
        fake._policy_sample = mock.Mock()
        fake._fail = mock.Mock()
        writer = self.writer

        async def checkpoint(*_):
            self.realm.registry.selected.clear()
            return object()

        fake._checkpoint = checkpoint
        # _send must refuse before it needs a transport or writer.write at all.
        with self.assertRaises(ValueError):
            await fake._send(writer, {}, (wire,), game=True)
        fake._policy_sample.assert_not_called()

    async def test_actual_send_drains_five_frames_through_existing_real_policy(self):
        frames = await self.selected()
        policy = b._TransportPolicy(object(), object(), object(),
                                    {12000: object(), 14030: object()}, now=time.monotonic_ns())

        def sample(peer):
            return b.OwnerSample(policy.owner, policy.handle, policy.job, peer,
                                 time.monotonic_ns(), True, True)

        def boot(writer, peer):
            policy.admit(writer, peer, sample(peer), time.monotonic_ns())
            for opcode, size, request in ((0x4e20, 12, None),
                                           (0x4e35, 76, 0x4e34), (0x4f3e, 6, 0x4f3d)):
                if request is not None:
                    policy.received_frame(writer, sample(peer), request, 10, time.monotonic_ns())
                policy.begin_write(writer, sample(peer), opcode, size, 0, time.monotonic_ns())
                policy.drained(writer, sample(peer), 0, time.monotonic_ns())

        prior = object()
        peer = b.Peer(14030, 41000, time.monotonic_ns())
        boot(prior, peer)
        policy.eof(prior, sample(peer), True, time.monotonic_ns())
        policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        peer = b.Peer(14030, 41001, time.monotonic_ns())
        boot(self.writer, peer)
        fake = object.__new__(b.PersistentBroker)
        fake._npc_respawn = None
        fake.realm, fake.policy = self.realm, policy

        async def checkpoint(writer, row):
            fresh = sample(peer)
            policy.checkpoint(writer, fresh, time.monotonic_ns())
            return fresh

        async def owned_sample(row):
            return sample(peer)

        fake._checkpoint = checkpoint
        fake._sample = owned_sample
        await fake._send(self.writer, {}, frames, game=True)
        self.assertEqual([call.args[0] for call in self.writer.write.call_args_list], list(frames))
        self.assertEqual(self.writer.drain.await_count, 5)
        self.assertEqual([row[2] for row in list(policy.log)[-5:]],
                         [0x4e29, 0x4e95, 0x4e38, 0x4e96, 0x4e96])

    def test_broker_forwards_explicit_spawn_without_starting_listener(self):
        candidates = (spawn(),)
        with mock.patch.object(b, 'LocalRealm') as realm:
            b.PersistentBroker(sockets={12000: object(), 14030: object()}, retained_owner=object(),
                owner_handle=object(), owner_job=object(), owner_guard=lambda _: True,
                owner_liveness_guard=lambda: True, source_guard=lambda: None,
                conversation_factory=lambda *_: None, expected_uuid=str(uuid.uuid4()),
                store_path=Path(self.temp.name) / 'unused.json', npc_spawns=candidates)
        self.assertIs(realm.call_args.kwargs['npc_spawns'], candidates)


class DefaultRealmTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_saved_grid_keeps_exact_self_world_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            realm = b.LocalRealm(str(uuid.uuid4()), Path(directory) / 'characters.json')
            realm.store.create(b.ack.realm.Creation(realm.profile_name, 0, 0, (13,) * 6))
            word0, word1 = b.movement.authority.unpack_grid(realm._actor_fields[1])
            initial = b.movement.Position(realm.profile_uid, realm.profile_name, 0, word0, word1)
            restored = b.movement.Position(realm.profile_uid, realm.profile_name, 0, word0 + 2, word1 - 1)
            realm.positions.commit(initial, restored)
            writer = object()
            game = realm.grant(writer, movement_owner_guard=lambda *_: True)
            await game.received(types.SimpleNamespace(opcode=0x263,
                payload=LocalLoginRequest(0, 'standalone.local', realm.expected_uuid).payload()))
            pb = b.ack.realm.pb
            request = pb.encode_message([pb.encode_bytes(1, realm.profile_name.encode()),
                                         pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
            frames = await game.received(types.SimpleNamespace(opcode=0x4e28, payload=request))
            self.assertEqual(len(frames), 4)
            self.assertEqual(realm.service(writer).snapshot(), restored)
            realm.validate_reply(frames[3], writer=writer)
            with self.assertRaisesRegex(ValueError, '^EXACT_LOCAL_WORLD_REQUIRED$'):
                realm.validate_reply(realm.actor_frame, writer=writer)


if __name__ == '__main__':
    unittest.main()
