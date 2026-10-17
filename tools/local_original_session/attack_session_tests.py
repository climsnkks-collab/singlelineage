"""Real attack authority/service headless tests; no source-ready bypass/native.

Reuse only TargetTests setup (real realm, broker, policy, retained validator,
TempStore and pinned NPC fixture), without inheriting/repeating its test suite.
"""
import asyncio
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from tools.local_original_session import attack as a, attack_session as s
from tools.local_original_session.attack_tests import TargetTests, payload


class SessionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = TargetTests.asyncSetUp
    step = TargetTests.step

    def service(self, **changes):
        options = dict(policy=s.EXPLICIT_LOCAL_VALIDATED_ATTACK_INTENT)
        options.update(changes)
        return s.AttackSession(self.targets, **options)

    def wire(self, *, uid=2, x=None, y=None):
        fields = [(1, uid)]
        if x is not None:
            fields.append((2, x))
        if y is not None:
            fields.append((3, y))
        return payload(*fields)

    async def routed(self, service, wire=None, writer=None):
        async with self.row['operation_lock']:
            return await service.handle(self.writer if writer is None else writer,
                                        self.wire() if wire is None else wire)

    async def test_default_off_explicit_config_and_no_nested_row_lock(self):
        service = s.AttackSession(self.targets)
        self.assertEqual(await self.routed(service, b''), ())
        self.assertEqual(service.last_outcome.kind, s.OutcomeKind.DISABLED)
        self.assertEqual(service.accepted_count, 0)
        self.assertIsNone(service.current_intent())
        for config in (dict(policy=True), dict(policy='on'), dict(counter_limit=True),
                       dict(counter_limit=0), dict(counter_limit=1 << 64)):
            with self.assertRaises(ValueError):
                s.AttackSession(self.targets, **config)
        with self.assertRaises(ValueError):
            s.AttackSession(object())
        enabled = self.service()
        self.assertEqual(await asyncio.wait_for(self.routed(enabled), 2), ())
        self.assertEqual(enabled.accepted_count, 1)
        self.assertFalse(self.row['operation_lock'].locked())
        self.writer.write.assert_not_called()

    async def test_each_identical_frame_fresh_authority_once_ordinal_no_reply(self):
        service = self.service()
        original = self.producer._sample
        calls = []
        async def sample(row):
            calls.append(row)
            return await original(row)
        self.producer._sample = sample
        wire = self.wire(x=self.x, y=self.y)
        for ordinal in (1, 2):
            self.assertEqual(await self.routed(service, wire), ())
            self.assertEqual(service.accepted_count, ordinal)
            self.assertEqual(service.last_outcome,
                s.AttackOutcome(s.OutcomeKind.ACCEPTED, 'LOCAL_VALIDATED_ATTACK_INTENT', ordinal))
            self.assertEqual(service.current_intent().accepted_ordinal, ordinal)
        self.assertEqual(len(calls), 4)  # Real native owner checkpoint twice per call.
        self.assertTrue(all(row is self.row for row in calls))
        meta = service.metadata()
        self.assertEqual(meta['current_ordinal'], 2)
        self.assertEqual(meta['response_policy'], 'NO_COMBAT_REPLY_UNTIL_SOURCE_CONTRACT')
        encoded = json.dumps(meta)
        self.assertNotIn('BoundTarget', encoded)
        self.assertNotIn('target_uid', encoded)
        self.assertNotIn(str(self.native.handle), encoded)
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)

    async def test_known_local_target_and_explicit_coordinate_rejections_only(self):
        service = self.service()
        before = self.mover.state
        for wire, reason in ((self.wire(uid=0), 'ATTACK_LOCAL_ACTOR_TARGET_REQUIRED'),
                (self.wire(uid=a.U64_MAX), 'ATTACK_LOCAL_ACTOR_TARGET_REQUIRED'),
                (self.wire(uid=self.realm.service(self.writer).snapshot().uid), 'ATTACK_LOCAL_SELF_TARGET_REFUSED'),
                (self.wire(uid=47), 'ATTACK_CURRENT_TYPED_NPC_REQUIRED'),
                (self.wire(x=self.x + 1), 'ATTACK_LOCAL_CURRENT_TARGET_COORDINATES_REQUIRED'),
                (self.wire(y=-1), 'ATTACK_LOCAL_CURRENT_TARGET_COORDINATES_REQUIRED')):
            with self.subTest(reason=reason):
                self.assertEqual(await self.routed(service, wire), ())
                self.assertEqual(service.last_outcome, s.AttackOutcome(s.OutcomeKind.REJECTED, reason))
                self.assertEqual(service.accepted_count, 0)
        self.assertIs(self.mover.state, before)
        self.writer.write.assert_not_called()

    async def test_current_target_change_clears_old_intent_new_call_uses_current_state(self):
        service = self.service()
        await self.routed(service)
        previous = service.current_intent()
        await self.step()
        self.assertIsNone(service.current_intent())
        self.assertEqual(service.metadata()['last_invalidation'], 'CURRENT_AUTHORITY_INVALID')
        self.assertEqual(await self.routed(service, self.wire(x=self.x)), ())
        self.assertEqual(service.last_outcome.kind, s.OutcomeKind.REJECTED)
        self.assertEqual(service.accepted_count, 1)
        await self.routed(service, self.wire(x=self.x + 1, y=self.y))
        current = service.current_intent()
        self.assertIsNot(current, previous)
        self.assertEqual(current._bound.target_x, self.x + 1)
        self.assertEqual(service.accepted_count, 2)
        self.assertEqual(self.writer.write.call_count, 1)  # Only existing NPC step wrote.

    async def test_selection_and_wrong_binding_are_errors_not_local_rejection(self):
        service = self.service()
        await self.routed(service)
        self.realm.registry.selected.clear()
        self.assertIsNone(service.current_intent())
        with self.assertRaisesRegex(ValueError, 'NPC_CURRENT_SELECTED_AUTHORITY'):
            await self.routed(service)
        self.assertEqual(service.last_outcome.kind, s.OutcomeKind.ERROR)
        self.assertEqual(service.accepted_count, 1)
        self.writer.write.assert_not_called()

    async def test_current_claim_npc_binding_and_reader_owner_errors_propagate(self):
        for mutation, restore, code in (
                (lambda: self.realm._npc_frames.pop(id(self.writer)),
                 lambda: self.realm._npc_frames.update({id(self.writer): saved}), 'CURRENT_BOUND_NPC'),
                (lambda: setattr(self.reader, 'closed', True),
                 lambda: setattr(self.reader, 'closed', False), 'SAME_RETAINED_BROKER')):
            service = self.service()
            saved = self.realm._npc_frames[id(self.writer)]
            mutation()
            try:
                with self.assertRaisesRegex(ValueError, code):
                    await self.routed(service)
                self.assertEqual(service.last_outcome.kind, s.OutcomeKind.ERROR)
                self.assertEqual(service.accepted_count, 0)
            finally:
                restore()
        service = self.service()
        with self.assertRaisesRegex(ValueError, 'CURRENT_CLAIM'):
            await self.routed(service, writer=object())
        self.assertEqual(service.last_outcome.reason, 'CURRENT_AUTHORITY_INVALID')
        self.writer.write.assert_not_called()

    async def test_malformed_sourcepin_and_unexpected_errors_keep_exception_objects(self):
        service = self.service()
        await self.routed(service)
        with self.assertRaisesRegex(ValueError, 'MALFORMED_ATTACK_PAYLOAD'):
            await self.routed(service, b'')
        self.assertIsNone(service.current_intent())
        self.assertEqual(service.last_outcome.reason, 'MALFORMED_ATTACK_PAYLOAD')
        pins = dict(a.SOURCE_PINS)
        pins[next(iter(pins))] = '0' * 64
        with patch.object(a, 'SOURCE_PINS', pins):
            with self.assertRaisesRegex(ValueError, 'ATTACK_SOURCE_CHANGED'):
                await self.routed(service)
        self.assertEqual(service.last_outcome.reason, 'ATTACK_SOURCE_CHANGED')
        error = RuntimeError('do not serialize payload or arbitrary failure text')
        async def failed(_):
            raise error
        self.producer._sample = failed
        with self.assertRaises(RuntimeError) as caught:
            await self.routed(service)
        self.assertIs(caught.exception, error)
        self.assertEqual(service.last_outcome.reason, 'UNEXPECTED_ERROR')
        self.assertNotIn('do not serialize', json.dumps(service.metadata()))
        self.assertEqual(service.accepted_count, 1)
        self.writer.write.assert_not_called()

    async def _hold_checkpoint(self):
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.producer._sample
        calls = 0
        async def sample(row):
            nonlocal calls
            calls += 1
            result = await original(row)
            if calls == 2:
                entered.set()
                await release.wait()
            return result
        self.producer._sample = sample
        return entered, release

    async def test_close_and_fatal_during_checkpoint_never_accept_or_close_caller_resources(self):
        original = self.producer._sample
        for terminal, kind in (('close', s.OutcomeKind.CLOSED), ('fail', s.OutcomeKind.FATAL)):
            self.producer._sample = original
            service = self.service()
            entered, release = await self._hold_checkpoint()
            task = asyncio.create_task(self.routed(service))
            await asyncio.wait_for(entered.wait(), 2)
            getattr(service, terminal)()
            release.set()
            self.assertEqual(await asyncio.wait_for(task, 2), ())
            self.assertEqual(service.last_outcome.kind, kind)
            self.assertEqual(service.accepted_count, 0)
            self.assertIsNone(service.current_intent())
            self.assertFalse(self.producer._closing)
            self.assertFalse(self.reader.closed)
            self.assertFalse(self.reader.owner.closed)
            self.assertEqual(await self.routed(service), ())
        self.writer.write.assert_not_called()

    async def test_cancel_checkpoint_propagates_clears_current_and_keeps_counter(self):
        service = self.service()
        await self.routed(service)
        entered, _ = await self._hold_checkpoint()
        task = asyncio.create_task(self.routed(service))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel('cancel checkpoint')
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertIsNone(service.current_intent())
        self.assertEqual(service.accepted_count, 1)
        self.assertEqual(service.last_outcome.kind, s.OutcomeKind.CANCELLED)
        self.assertFalse(self.row['operation_lock'].locked())
        self.writer.write.assert_not_called()

    async def test_checkpoint_current_target_mutation_and_source_loss_never_accept(self):
        original = self.producer._sample
        for change, code in ((lambda: setattr(self.mover, 'state', replace(
                self.mover.state, packed=self.mover.state.packed + 1)), 'BOUND_TARGET_STALE'),
                (lambda: a.SOURCE_PINS.update({next(iter(a.SOURCE_PINS)): '0' * 64}), 'SOURCE_CHANGED')):
            service = self.service()
            entered, release = await self._hold_checkpoint()
            task = asyncio.create_task(self.routed(service))
            await asyncio.wait_for(entered.wait(), 2)
            state, pins = self.mover.state, dict(a.SOURCE_PINS)
            try:
                change()
                release.set()
                with self.assertRaisesRegex(ValueError, code):
                    await task
                self.assertEqual(service.accepted_count, 0)
                self.assertEqual(service.last_outcome.kind, s.OutcomeKind.ERROR)
            finally:
                self.mover.state = state
                a.SOURCE_PINS.clear(); a.SOURCE_PINS.update(pins)
                self.producer._sample = original
        self.writer.write.assert_not_called()

    async def test_counter_capacity_refuses_without_wrap_or_false_accept(self):
        service = self.service(counter_limit=1)
        await self.routed(service)
        self.assertEqual(service.accepted_count, 1)
        self.assertEqual(await self.routed(service), ())
        self.assertEqual(service.last_outcome,
            s.AttackOutcome(s.OutcomeKind.REJECTED, 'ATTACK_SESSION_COUNTER_CAPACITY'))
        self.assertIsNone(service.current_intent())
        self.assertEqual(service.accepted_count, 1)
        self.writer.write.assert_not_called()

    async def test_synchronous_checkpoint_cancel_request_never_commits(self):
        service = self.service()
        original = self.producer._sample
        calls = 0
        async def sample(row):
            nonlocal calls
            calls += 1
            result = await original(row)
            if calls == 2:
                asyncio.current_task().cancel('cancel without another await')
            return result
        self.producer._sample = sample
        task = asyncio.create_task(self.routed(service))
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(service.accepted_count, 0)
        self.assertIsNone(service.current_intent())
        self.assertEqual(service.last_outcome.kind, s.OutcomeKind.CANCELLED)
        self.writer.write.assert_not_called()

    async def test_release_same_writer_only_preserves_history_and_new_handle_is_fresh(self):
        service = self.service()
        await self.routed(service)
        current, outcome = service.current_intent(), service.last_outcome
        service.release(object())
        self.assertIs(service.current_intent(), current)
        self.assertIs(service.last_outcome, outcome)
        self.assertIsNone(service.last_invalidation)
        service.release(self.writer)
        self.assertIsNone(service.current_intent())
        self.assertEqual(service.last_invalidation, 'ATTACK_SESSION_WRITER_RELEASED')
        self.assertEqual(service.accepted_count, 1)
        self.assertIs(service.last_outcome, outcome)
        service.release(self.writer)  # Already empty: no metadata/history change.
        service.release(object())
        self.assertEqual(service.last_invalidation, 'ATTACK_SESSION_WRITER_RELEASED')
        self.assertIs(service.last_outcome, outcome)
        self.assertFalse(service.closed or service.fatal or self.producer._closing)
        await self.routed(service)
        self.assertEqual(service.accepted_count, 2)
        self.assertIsNot(service.current_intent(), current)
        service.release(self.writer)
        self.realm.registry.selected.clear()
        with self.assertRaisesRegex(ValueError, 'NPC_CURRENT_SELECTED_AUTHORITY'):
            await self.routed(service)
        self.assertEqual(service.accepted_count, 2)
        self.assertEqual(service.last_outcome.kind, s.OutcomeKind.ERROR)
        self.writer.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
