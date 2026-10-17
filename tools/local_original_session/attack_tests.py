"""Pinned attack wire and actual realm/policy targets; no native/UI/listener.

Reuse ConnectedMotionTests' actual broker, store, policy and source-pinned NPC
fixture. Only retained identity reads are injected; no source-ready bypass.
"""
from dataclasses import replace
import copy
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from tools.local_original_session import attack as a, broker as b, edge_tests, npc_motion_tests
from tools.local_original_session.npc_tests import spawn
from tools.local_own_login_request.codec import LocalLoginRequest


def payload(*fields):
    return b''.join(a._field(number, value) for number, value in fields)


class WireTests(unittest.TestCase):
    def test_required_optional_presence_uint64_and_signed32(self):
        for uid in (0, 1, 1 << 40, a.U64_MAX):
            self.assertEqual(a.parse_payload(payload((1, uid))), a.AttackRequest(uid))
        for x in (-(1 << 31), -1, 0, (1 << 31) - 1):
            result = a.parse_payload(payload((3, x), (1, 2), (2, x)))
            self.assertEqual(result, a.AttackRequest(2, x, x))
        self.assertEqual(a.parse_payload(payload((1, 2), (2, 0))), a.AttackRequest(2, 0, None))
        self.assertEqual(a.parse_payload(payload((1, 2), (3, 0))), a.AttackRequest(2, None, 0))
        # Existing parser accepts bounded overlong varints; not claimed to be
        # the original complete duplicate/unknown/canonical protobuf behavior.
        self.assertEqual(a.parse_payload(b'\x08\x82\x00'), a.AttackRequest(2))

    def test_malformed_required_duplicate_unknown_wire_range_and_truncated(self):
        cases = [b'', payload((2, 0)), payload((1, 2), (1, 2)),
            payload((1, 2), (2, 0), (2, 0)), payload((1, 2), (4, 0)),
            b'\x0a\x01\x02', b'\x08\x80', b'\x08' + b'\xff' * 10 + b'\x01',
            payload((1, 2), (2, 0x80000000)), payload((1, 2), (3, 0xffffffff)),
            payload((1, 2), (2, 0xffffffff7fffffff)), b'\x08\x02' + b'\0' * 34]
        for value in cases:
            with self.subTest(size=len(value)), self.assertRaisesRegex(ValueError, 'MALFORMED_ATTACK'):
                a.parse_payload(value)
        for changes in (dict(target_uid=True), dict(target_uid=-1), dict(target_uid=1 << 64),
                        dict(target_uid=2, target_x=True), dict(target_uid=2, target_y=1 << 31)):
            with self.assertRaises(ValueError):
                a.AttackRequest(**changes)

    def test_changed_source_blocks_real_parser(self):
        pins = dict(a.SOURCE_PINS)
        pins[next(iter(pins))] = '0' * 64
        with patch.object(a, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'ATTACK_SOURCE_CHANGED'):
            a.parse_payload(payload((1, 2)))


class TargetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await npc_motion_tests.ConnectedMotionTests.asyncSetUp(self)
        # Keep the exact production reader validator and Native instance.
        # The existing fixture injects only identity/Job results; no Native
        # initializer, attach, process open, or real process API is performed.
        _, self.reader, self.native = edge_tests.Tests.retained_binding(self)
        member, retained = self.reader.member, self.reader.owner
        self.policy.handle, self.policy.job = 0x123456, 0x234567
        member.process, member.job = self.policy.handle, self.policy.job
        retained.child, retained.closed = member, False
        retained.owner_handle, retained.owner_job = self.policy.handle, self.policy.job
        self.policy.owner = retained
        self.targets = a.AttackTargets(self.producer, self.reader)

    def request(self, **changes):
        options = dict(target_uid=self.mover.state.uid, target_x=self.x, target_y=self.y)
        options.update(changes)
        return a.AttackRequest(**options)

    async def step(self, **changes):
        return await npc_motion_tests.ConnectedMotionTests.step(self, **changes)

    def ctypes_primary(self):
        # clone_observer/windows.py PROCESS's actual field types. Constructing
        # this structure calls no Native initializer or process API.
        class Primary(C.Structure):
            _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE),
                        ('pid', W.DWORD), ('tid', W.DWORD)]
        old = self.reader.member
        member = Primary(process=0x12345678, pid=old.pid)
        member.identity, member.job = dict(old.identity, birth=12), 0x23456789
        self.reader.member = self.reader.owner.child = member
        # Match NativeOwner.prepare: capture process/job once, then pass the
        # retained attributes to the broker policy. backend.handle likewise
        # stores DuplicateHandle's .value once in RetainedSceneReader.bind.
        retained = self.reader.owner
        retained.owner_handle, retained.owner_job = member.process, member.job
        self.policy.handle, self.policy.job = retained.owner_handle, retained.owner_job
        self.native.handle = C.c_void_p(0x3456789a).value
        return member

    async def test_ctypes_process_same_value_survives_validation_and_checkpoint(self):
        member = self.ctypes_primary()
        self.assertEqual(member.process, member.process)
        self.assertIsNot(member.process, member.process)
        bound = await self.targets.authorize(self.writer, self.request())
        self.assertIs(await self.targets.checkpoint(bound), bound)
        self.targets.action_frame(bound, raw_effect=0, direction=0, self_action=False)
        self.writer.write.assert_not_called()

    async def test_approach_keeps_complete_authority_comparison_and_refuses_forged_projection(self):
        request = self.request()
        before = self.targets._project(self.writer, request)
        selected = replace(before[1], word0=before[1].word0 + 1)
        identities = before[-1][:17] + (selected,) + before[-1][18:]
        forged = (before[0], selected, *before[2:6], identities)
        self.assertFalse(self.targets.same_authority(before, forged))
        self.assertTrue(self.targets.same_authority(before, self.targets._project(self.writer, request)))
        with self.assertRaisesRegex(ValueError, 'ATTACK_APPROACH_'):
            a.AttackTargets.observe_committed_approach(self.targets, self.writer, request,
                                                      forged, (0, 0, 0), self.policy.events)
        self.assertIs(self.realm.service(self.writer).snapshot(), before[1])
        self.writer.write.assert_not_called()

    async def test_typed_handle_values_and_peer_values_survive_fresh_equal_scalars(self):
        member = self.ctypes_primary()
        self.row['peer']['connection_id'] = 0x456789ab
        before = self.targets._project(self.writer, self.request())
        # Every value is fresh but unchanged, as with ctypes field/.value reads.
        fresh = lambda value: int(str(value))
        self.policy.handle = fresh(self.policy.handle)
        self.policy.job = fresh(self.policy.job)
        self.reader.owner.owner_handle = fresh(self.reader.owner.owner_handle)
        self.reader.owner.owner_job = fresh(self.reader.owner.owner_job)
        member.job = fresh(member.job)
        self.native.handle = fresh(self.native.handle)
        self.row['peer']['connection_id'] = fresh(self.row['peer']['connection_id'])
        after = self.targets._project(self.writer, self.request())
        self.assertTrue(self.targets.same_authority(before, after))
        bound = await self.targets.authorize(self.writer, self.request())
        self.assertIs(await self.targets.checkpoint(bound), bound)
        self.writer.write.assert_not_called()

    async def test_changed_typed_values_during_validation_and_after_await_refuse(self):
        original_identity = self.reader.owner.native.identity
        original_sample = self.producer._sample
        for phase in ('validate', 'authorize_await', 'checkpoint_await'):
            for field in ('process', 'job', 'duplicate', 'pid', 'birth', 'peer', 'peer_type'):
                with self.subTest(phase=phase, field=field):
                    member = self.ctypes_primary()
                    self.row['peer']['connection_id'] = 1
                    def mutate():
                        retained = self.reader.owner
                        if field == 'process':
                            member.process += 16
                            retained.owner_handle = self.policy.handle = member.process
                        elif field == 'job':
                            member.job += 16
                            retained.owner_job = self.policy.job = member.job
                        elif field == 'duplicate': self.native.handle += 16
                        elif field == 'pid':
                            member.pid += 16
                            member.identity['pid'] = member.pid
                        elif field == 'birth': member.identity['birth'] += 1
                        elif field == 'peer': self.row['peer']['connection_id'] = 2
                        else: self.row['peer']['connection_id'] = True
                    try:
                        if phase == 'validate':
                            def changed_identity(*args, **kwargs):
                                mutate()
                                return original_identity(*args, **kwargs)
                            self.reader.owner.native.identity = changed_identity
                            with self.assertRaisesRegex(ValueError, 'ATTACK_AUTHORITY_CHANGED'):
                                await self.targets.authorize(self.writer, self.request())
                        else:
                            bound = (await self.targets.authorize(self.writer, self.request())
                                     if phase == 'checkpoint_await' else None)
                            async def changed_sample(row):
                                mutate()
                                return await original_sample(row)
                            self.producer._sample = changed_sample
                            with self.assertRaisesRegex(ValueError, 'ATTACK_BOUND_TARGET_STALE'):
                                if bound is None:
                                    await self.targets.authorize(self.writer, self.request())
                                else:
                                    await self.targets.checkpoint(bound)
                    finally:
                        self.reader.owner.native.identity = original_identity
                        self.producer._sample = original_sample
        self.writer.write.assert_not_called()

    async def test_invalid_handle_types_and_equal_reference_replacements_refuse(self):
        member = self.ctypes_primary()
        for value in (True, 0, -1, str(self.native.handle)):
            saved = self.native.handle
            try:
                self.native.handle = value
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'TYPED_HANDLE'):
                    await self.targets.authorize(self.writer, self.request())
            finally:
                self.native.handle = saved
        bound = await self.targets.authorize(self.writer, self.request())
        service = self.realm.service(self.writer)
        game = self.realm.registry.resolve(self.writer)
        for obj, key, replacement in (
                (self.realm, 'registry', copy.copy(self.realm.registry)),
                (service, '_position', replace(service.snapshot())),
                (game, 'selection', replace(game.selection)),
                (member, 'identity', dict(member.identity))):
            saved = getattr(obj, key)
            try:
                setattr(obj, key, replacement)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    self.targets.revalidate(bound)
            finally:
                setattr(obj, key, saved)
        self.targets.revalidate(bound)
        pins = dict(a.SOURCE_PINS)
        pins[next(iter(pins))] = '0' * 64
        with patch.object(a, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'ATTACK_SOURCE_CHANGED'):
            await self.targets.authorize(self.writer, self.request())
        self.writer.write.assert_not_called()

    async def test_current_target_and_exact_kind1_builder_with_explicit_inputs(self):
        request = a.parse_payload(payload((1, 2), (2, self.x), (3, self.y)))
        bound = await self.targets.authorize(self.writer, request)
        self.assertIs(bound.request, request)
        self.assertIs(bound.attacker, self.realm.service(self.writer).snapshot())
        self.assertEqual((bound.target_uid, bound.map_id, bound.target_x, bound.target_y, bound.source),
            (2, 0, self.x, self.y, 'CURRENT_NPC_MOTION_STATE'))
        for effect in (-(1 << 31), -1, 0, (1 << 31) - 1):
            for flag in (None, False, True):
                wire = self.targets.action_frame(bound, raw_effect=effect, direction=7, self_action=flag)
                self.assertEqual(int.from_bytes(wire[:2], 'little'), len(wire))
                self.assertEqual((wire[2:4], wire[-2:]), (b'\x31\x4e', b'\0\0'))
                with a.pb.parse_message(wire[4:-2], schema={n: 0 for n in (1, 2, 3, 4, 5, 13)}) as msg:
                    actual = {item.number: item.value for item in msg.fields}
                expected = {1: 1, 2: bound.attacker.uid, 3: 2, 4: effect & a.U64_MAX, 5: 7}
                if flag is not None:
                    expected[13] = int(flag)
                self.assertEqual(actual, expected)
        self.assertIs(await self.targets.checkpoint(bound), bound)
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)

    async def test_builder_refuses_implicit_or_out_of_domain_policy_values(self):
        bound = await self.targets.authorize(self.writer, self.request())
        for options in (dict(raw_effect=True, direction=0, self_action=True),
                dict(raw_effect=1 << 31, direction=0, self_action=True),
                dict(raw_effect=0, direction=True, self_action=True),
                dict(raw_effect=0, direction=9, self_action=True),
                dict(raw_effect=0, direction=0, self_action=0)):
            with self.assertRaises(ValueError):
                self.targets.action_frame(bound, **options)
        with self.assertRaises(TypeError):
            self.targets.action_frame(bound, direction=0, self_action=True)
        with self.assertRaises(TypeError):
            self.targets.action_frame(bound, raw_effect=0, direction=0)
        other = a.AttackTargets(self.producer, self.reader)
        with self.assertRaisesRegex(ValueError, 'SAME_TARGET_AUTHORITY'):
            other.revalidate(bound)

    async def test_optional_coordinates_are_comparisons_only_and_actor_subset_is_separate(self):
        before = self.mover.state
        selected = self.realm.service(self.writer).snapshot()
        for request in (a.AttackRequest(2), a.AttackRequest(2, self.x), a.AttackRequest(2, None, self.y)):
            bound = await self.targets.authorize(self.writer, request)
            self.assertIs(bound.request, request)
        for request in (a.AttackRequest(0), a.AttackRequest(a.U64_MAX),
                a.AttackRequest(selected.uid), a.AttackRequest(47),
                self.request(target_x=self.x + 1), self.request(target_y=-1)):
            with self.assertRaises(ValueError):
                await self.targets.authorize(self.writer, request)
        self.assertIs(self.mover.state, before)
        self.assertIs(self.realm.service(self.writer).snapshot(), selected)
        self.writer.write.assert_not_called()

    async def test_after_actual_npc_step_uses_current_state_and_stale_bound_refuses(self):
        bound = await self.targets.authorize(self.writer, self.request())
        moved = await self.step()
        self.assertIs(self.mover.state, moved)
        with self.assertRaises(ValueError):
            self.targets.revalidate(bound)
        with self.assertRaises(ValueError):
            await self.targets.authorize(self.writer, self.request())
        current = await self.targets.authorize(self.writer, self.request(target_x=self.x + 1))
        self.assertEqual((current.target_x, current.target_y), (self.x + 1, self.y))
        self.assertTrue(any(value is moved for value in current._identities))
        # Exactly the existing NPC movement wrote; authorizing attack wrote none.
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_native_checkpoint_and_reader_revalidation_reject_racing_mutations(self):
        original = self.producer._sample
        async def changed(row):
            result = await original(row)
            self.realm.registry.selected.clear()
            return result
        self.producer._sample = changed
        with self.assertRaises(ValueError):
            await self.targets.authorize(self.writer, self.request())
        self.writer.write.assert_not_called()

    async def test_reader_revalidation_rejects_in_place_peer_and_typed_spawn_frame_mismatch(self):
        bound = await self.targets.authorize(self.writer, a.AttackRequest(2))
        original_identity = self.reader.owner.native.identity
        def changed(*args, **kwargs):
            self.row['peer']['connection_id'] += 1
            return original_identity(*args, **kwargs)
        self.reader.owner.native.identity = changed
        with self.assertRaisesRegex(ValueError, 'AUTHORITY_CHANGED'):
            self.targets.revalidate(bound)
        self.reader.owner.native.identity = original_identity
        candidate, wire = self.realm._npc_spawns[0]
        fields = dict(candidate.fields)
        fields[9] = 'Different local NPC'
        self.realm._npc_spawns = ((spawn(fields), wire),)
        with self.assertRaisesRegex(ValueError, 'NPC_MAP_FRAME'):
            await self.targets.authorize(self.writer, a.AttackRequest(2))
        self.writer.write.assert_not_called()

    async def test_exact_reader_validators_and_backend_cannot_be_substituted(self):
        duck = SimpleNamespace(validate=lambda: True, owner=self.reader.owner,
                               member=self.reader.member, backend=self.native)
        with self.assertRaisesRegex(ValueError, 'RETAINED_READER_REQUIRED'):
            a.AttackTargets(self.producer, duck)
        bound = await self.targets.authorize(self.writer, self.request())
        original_validate, original_backend_validate = self.reader.validate, self.native.validate
        self.reader.validate = lambda: True
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_VALIDATOR'):
            a.AttackTargets(self.producer, self.reader)
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_VALIDATOR'):
            self.targets.revalidate(bound)
        self.reader.validate = original_validate
        self.native.validate = lambda: True
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_VALIDATOR'):
            await self.targets.checkpoint(bound)
        self.native.validate = original_backend_validate
        _, other_reader, _ = edge_tests.Tests.retained_binding(self)
        self.reader.validate = other_reader.validate
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_VALIDATOR'):
            self.targets.action_frame(bound, raw_effect=0, direction=0, self_action=False)
        self.reader.validate = original_validate
        self.reader.backend = SimpleNamespace(handle=self.native.handle, validate=self.reader.validate)
        with self.assertRaisesRegex(ValueError, 'SAME_RETAINED_BACKEND'):
            await self.targets.authorize(self.writer, self.request())
        self.reader.backend = self.native
        self.assertIs(await self.targets.checkpoint(bound), bound)
        self.writer.write.assert_not_called()

    async def test_backend_and_owner_member_changes_during_real_reader_validation_refuse(self):
        bound = await self.targets.authorize(self.writer, self.request())
        owner, member = self.reader.owner, self.reader.member
        original_identity = owner.native.identity
        async def check(mutate, restore):
            def changed(*args, **kwargs):
                result = original_identity(*args, **kwargs)
                mutate()
                return result
            owner.native.identity = changed
            try:
                with self.assertRaises(ValueError):
                    self.targets.revalidate(bound)
            finally:
                restore()
                owner.native.identity = original_identity
        await check(lambda: setattr(self.reader, 'backend', SimpleNamespace(
                        handle=self.native.handle, validate=self.reader.validate)),
                    lambda: setattr(self.reader, 'backend', self.native))
        await check(lambda: setattr(self.reader, 'member', SimpleNamespace(**vars(member))),
                    lambda: setattr(self.reader, 'member', member))
        await check(lambda: setattr(self.reader, 'owner', SimpleNamespace(**vars(owner))),
                    lambda: setattr(self.reader, 'owner', owner))
        self.targets.revalidate(bound)
        self.writer.write.assert_not_called()

    async def test_checkpoint_and_prewrite_builder_reject_changed_target_and_authority(self):
        bound = await self.targets.authorize(self.writer, a.AttackRequest(2))
        original = self.producer._sample
        async def changed(row):
            result = await original(row)
            self.mover.state = replace(self.mover.state, packed=self.mover.state.packed + 1)
            return result
        self.producer._sample = changed
        with self.assertRaisesRegex(ValueError, 'BOUND_TARGET_STALE'):
            await self.targets.checkpoint(bound)
        with self.assertRaises(ValueError):
            self.targets.action_frame(bound, raw_effect=0, direction=0, self_action=False)
        self.writer.write.assert_not_called()

    async def test_wrong_writer_closed_removed_policy_storage_and_npc_lifetime_refuse(self):
        with self.assertRaises(ValueError):
            await self.targets.authorize(object(), self.request())
        service = self.realm.service(self.writer)
        saved = self.realm._npc_frames[id(self.writer)]
        cases = (
            (self.row, 'failed', True), (self.row, 'joined', True),
            (self.policy._connection(self.writer), 'eof', True),
            (self.producer, '_closing', True), (self.reader, 'closed', True),
            (self.reader.owner, 'closed', True), (self.mover, 'closed', True),
            (self.mover, 'fatal', True), (self.mover, 'spawn_drained', False),
            (self.mover, 'pending', object()), (service, 'fatal', True))
        for obj, key, value in cases:
            previous = obj[key] if type(obj) is dict else getattr(obj, key)
            with self.subTest(key=key):
                try:
                    if type(obj) is dict: obj[key] = value
                    else: setattr(obj, key, value)
                    with self.assertRaises(ValueError):
                        await self.targets.authorize(self.writer, self.request())
                finally:
                    if type(obj) is dict: obj[key] = previous
                    else: setattr(obj, key, previous)
        self.realm._npc_frames[id(self.writer)] = (object(), *saved[1:])
        with self.assertRaises(ValueError):
            await self.targets.authorize(self.writer, self.request())
        self.realm._npc_frames[id(self.writer)] = saved
        self.realm.positions.commit(service.snapshot(),
                                    replace(service.snapshot(), word0=service.snapshot().word0 + 1))
        with self.assertRaises(ValueError):
            await self.targets.authorize(self.writer, self.request())
        self.writer.write.assert_not_called()

    async def test_static_motion_off_resolves_real_bound_spawn_and_never_retains_removed_target(self):
        directory = Path(self.temp.name) / 'static'
        directory.mkdir()
        realm = b.LocalRealm(str(uuid.uuid4()), directory / 'characters.json', npc_spawns=(spawn(),))
        realm.store.create(b.ack.realm.Creation(realm.profile_name, 0, 0, (13,) * 6))
        async def owner(*_): return True
        game = realm.grant(self.writer, movement_owner_guard=owner)
        await game.received(SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', realm.expected_uuid).payload()))
        select = a.pb.encode_message([a.pb.encode_bytes(1, realm.profile_name.encode()),
                                    a.pb.encode_uint32(2, 0), a.pb.encode_uint32(3, 0)])
        frames = await game.received(SimpleNamespace(opcode=0x4e28, payload=select))
        self.producer.realm = realm
        await self.producer._send(self.writer, self.row, frames, game=True)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        targets = a.AttackTargets(self.producer, self.reader)
        bound = await targets.authorize(self.writer, a.AttackRequest(2))
        self.assertEqual(bound.source, 'CURRENT_BOUND_TYPED_NPC_SPAWN')
        self.assertEqual((bound.target_x, bound.target_y), (self.x, self.y))
        realm._npc_spawns = ()
        with self.assertRaises(ValueError): targets.revalidate(bound)
        with self.assertRaises(ValueError): await targets.authorize(self.writer, a.AttackRequest(2))
        self.writer.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
