"""Actual inventory delivery/Store/retained fixture; no process/UI/listener.

Reuse existing root broker-product setup only, never its test suite. Positive
delivery is the original add_inventory -> _send -> write/drain operation.
"""
import asyncio
from copy import copy
import json
from unittest.mock import patch
import unittest

from tools.local_original_session import broker, inventory, item_use, item_use_session as session
from tools.local_original_session import broker_tests as broker_fixture
from tools.local_original_session.item_use_tests import body, scalar, blob
from tools.local_original_session.movement_tests import payload as move_payload


class SessionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = broker_fixture.InventoryRestoreOnlyBrokerTests.asyncSetUp

    def bind(self, *, policy=session.POLICY):
        leaf = session.ItemUseSession(self.producer, policy=policy)
        self.producer._item_use_session = self.realm._item_use_session = leaf
        self.policy.item_use_intent = True
        return leaf

    def request_payload(self, *, params=b'', identifier=None):
        if identifier is None:
            identifier = inventory.validate_frame(self.producer._inventory_frame).identifier
        return body(params, identifier)

    async def routed(self, leaf, wire=None, writer=None):
        async with self.row['operation_lock']:
            return await leaf.handle(self.writer if writer is None else writer,
                                     self.request_payload() if wire is None else wire)

    async def deliver(self, *, deadline=None):
        result = await self.producer.add_inventory(self.writer, deadline_ns=deadline)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertIsNotNone(self.producer._inventory_delivery_authority)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.reads_after_delivery = len(self.memory.calls)
        self.saved_after_delivery = self.service.store.path.read_bytes()

    def no_effect(self):
        self.writer.write.assert_not_called()
        self.writer.drain.assert_not_awaited()
        self.assertEqual(len(self.memory.calls), self.reads_after_delivery)

    async def test_default_off_registration_and_first_delivery_boundary(self):
        disabled = self.bind(policy=None)
        self.assertEqual(await self.routed(disabled, b''), ())
        self.assertEqual(disabled.last_outcome.kind, session.OutcomeKind.DISABLED)
        self.assertEqual(disabled.accepted_count, 0)
        leaf = self.bind()
        # Before the inventory delivery completed, a use is refused alone (no raise).
        self.assertEqual(await self.routed(leaf), ())
        self.assertEqual(leaf.last_outcome.kind, session.OutcomeKind.REJECTED)
        self.assertEqual(leaf.last_outcome.reason, 'ITEM_USE_CURRENT_CANONICAL_FRAME_REQUIRED')
        self.assertEqual(leaf.accepted_count, 0)
        self.writer.write.assert_not_called()
        self.assertFalse(self.service.store.path.exists())
        await self.deliver()
        self.assertEqual(await asyncio.wait_for(self.routed(leaf), 2), ())
        self.assertEqual(leaf.accepted_count, 1)
        self.assertFalse(self.row['operation_lock'].locked())
        self.no_effect()

    async def test_actual_delivery_params_preserved_each_frame_revalidates_and_no_effect(self):
        await self.deliver()
        leaf = self.bind()
        params = scalar(18, -3) + scalar(17, 1) + blob(7, b'\xffopaque\0') + scalar(1, 1) + scalar(18, 2)
        wire = self.request_payload(params=params)
        original, calls = self.producer.owner_guard, []
        def owner(peer):
            calls.append(peer)
            return original(peer)
        self.producer.owner_guard = owner
        for ordinal in (1, 2):
            self.assertEqual(await self.routed(leaf, wire), ())
            self.assertEqual(leaf.accepted_count, ordinal)
            self.assertEqual(leaf.last_outcome,
                session.ItemUseOutcome(session.OutcomeKind.ACCEPTED, 'VALIDATED_ITEM_USE_INTENT_ONLY', ordinal))
            self.assertEqual(leaf._current.request.raw_payload, wire)
            self.assertEqual(leaf._current.request.params.raw, params)
            self.assertEqual([field.number for field in leaf._current.request.params.fields], [18, 17, 7, 1, 18])
            self.assertEqual(leaf._current.request.params.present_fields, {1, 7, 17, 18})
        self.assertEqual(len(calls), 2)
        meta = leaf.metadata()
        self.assertEqual(meta['proof_scope'], 'VALIDATED_ITEM_USE_INTENT_ONLY')
        self.assertTrue(meta['intent_recorded'])
        encoded = json.dumps(meta)
        for value in ('opaque', 'identifier', 'raw_payload', 'writer', 'BoundTarget'):
            self.assertNotIn(value, encoded)
        self.assertEqual(self.service.store.path.read_bytes(), self.saved_after_delivery)
        self.no_effect()

    async def test_normal_committed_movement_uses_current_position_not_delivery_position(self):
        await self.deliver(deadline=self.product_ns + 500_000_000)
        leaf = self.bind()
        old = self.producer._inventory_delivery_authority[0]
        mover = self.realm.service(self.writer)
        mover._edge_passability = lambda *_: True  # Explicit local fixture edge only.
        moved = await mover.handle_CS4E2B(move_payload(old, 2))
        self.assertTrue(moved.accepted)
        self.assertIsNot(mover.snapshot(), old)
        self.assertEqual(self.realm.positions.restore(mover.snapshot()), mover.snapshot())
        self.product_ns += 1_000_000_000  # Original Add deadline is past; delivery completed.
        self.assertLess(self.producer._inventory_deadline_ns, self.product_ns)
        self.assertEqual(await self.routed(leaf), ())
        self.assertEqual(leaf.accepted_count, 1)
        self.assertIs(self.producer._inventory_delivery_authority[0], old)
        self.no_effect()

    async def test_full_uint64_identifier_never_truncates_or_substitutes_character_template(self):
        await self.deliver()
        leaf = self.bind()
        item = inventory.validate_frame(self.producer._inventory_frame)
        self.assertEqual(item.identifier, 0xffffffff)
        for identifier in (0, item.identifier + (1 << 32), item_use.U64_MAX,
                           self.realm.service(self.writer).snapshot().uid, item.template_bits):
            with self.subTest(identifier=identifier):
                self.assertEqual(await self.routed(leaf, self.request_payload(identifier=identifier)), ())
                self.assertEqual(leaf.last_outcome.kind, session.OutcomeKind.REJECTED)
                self.assertEqual(leaf.last_outcome.reason, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                self.assertEqual(leaf.accepted_count, 0)
        self.assertEqual(self.service.store.path.read_bytes(), self.saved_after_delivery)
        self.no_effect()

    async def test_current_service_frame_store_selection_policy_and_restart_replacements_refuse(self):
        await self.deliver()
        leaf = self.bind()
        game = self.realm.registry.resolve(self.writer)
        values = (
            (self.producer, '_inventory_service', copy(self.service)),
            (self.producer, '_inventory_frame', bytes(bytearray(self.producer._inventory_frame))),
            (self.producer, '_inventory_operation_frame', bytes(bytearray(self.producer._inventory_frame))),
            (self.producer, '_inventory_store', copy(self.service.store)),
            (self.producer, '_inventory_selection_binding', self.producer._inventory_selection_binding[:-1]),
            (self.producer, '_inventory_admission_expired', True),
            (self.reader, 'closed', True), (game, 'selection', copy(game.selection)),
            (self.policy, 'item_use_intent', False), (leaf, 'policy', True),
            (leaf, 'policy', 'unknown_policy'), (self.realm, '_item_use_session', None))
        for owner, name, replacement in values:
            previous = getattr(owner, name)
            try:
                setattr(owner, name, replacement)
                if name in ('_inventory_frame', '_inventory_operation_frame', '_inventory_admission_expired'):
                    # Not-yet-delivered/expired delivery state refuses this use only.
                    with self.subTest(name=name):
                        self.assertEqual(await self.routed(leaf), ())
                        self.assertEqual(leaf.last_outcome.kind, session.OutcomeKind.REJECTED)
                else:
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        await self.routed(leaf)
                self.assertEqual(leaf.accepted_count, 0)
            finally:
                setattr(owner, name, previous)
        for phase in ('PREPARING', 'PREPARED', 'RESERVED', 'WRITE_ATTEMPTED', 'TERMINAL', 'DRAINED'):
            self.row['_restart'] = dict(phase=phase, selection_cleared=False)
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, 'NO_PENDING_RESTART'):
                await self.routed(leaf)
        self.row.pop('_restart')
        with self.assertRaisesRegex(ValueError, 'CURRENT_CLAIM'):
            await self.routed(leaf, writer=object())
        with self.assertRaisesRegex(ValueError, 'LOCKED_ADMISSION'):
            await leaf.handle(self.writer, self.request_payload())
        self.assertEqual(leaf.accepted_count, 0)
        self.no_effect()

    async def test_store_missing_deleted_conflicting_during_original_checkpoint_is_read_only(self):
        await self.deliver()
        path, original_sample = self.service.store.path, self.producer._sample
        original_file = path.read_bytes()
        fields = dict(inventory.validate_frame(self.producer._inventory_frame).raw_fields)
        fields[4] += 1
        conflicting = inventory.build_add(fields)
        uid = self.realm.service(self.writer).snapshot().uid
        for mode in ('missing', 'deleted', 'conflicting'):
            leaf = self.bind()
            path.write_bytes(original_file)
            async def changed(row):
                result = await original_sample(row)
                if mode == 'missing':
                    path.unlink()  # Test-owned temporary Store only.
                else:
                    rows = [] if mode == 'deleted' else [dict(uid=uid, frame=conflicting.hex())]
                    path.write_text(json.dumps(dict(version=1, inventories=rows)), encoding='ascii')
                return result
            self.producer._sample = changed
            try:
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'CURRENT_STORED_FRAME'):
                    await self.routed(leaf)
                self.assertEqual(leaf.accepted_count, 0)
                self.assertIsNone(leaf._current)
                if mode == 'missing':
                    self.assertFalse(path.exists())
                elif mode == 'deleted':
                    self.assertEqual(json.loads(path.read_text())['inventories'], [])
                else:
                    self.assertEqual(self.service.store.restore(uid), conflicting)
            finally:
                self.producer._sample = original_sample
        path.write_bytes(original_file)
        self.no_effect()

    async def test_close_release_and_cancel_first_inflight_checkpoint_cannot_accept(self):
        await self.deliver()
        original = self.producer._sample
        for mode in ('close', 'release', 'cancel'):
            leaf = self.bind()
            entered, release = asyncio.Event(), asyncio.Event()
            async def hold(row):
                result = await original(row)
                entered.set()
                await release.wait()
                return result
            self.producer._sample = hold
            task = asyncio.create_task(self.routed(leaf))
            entered_task = asyncio.create_task(entered.wait())
            await asyncio.wait((task, entered_task), return_when=asyncio.FIRST_COMPLETED)
            if not entered.is_set():
                entered_task.cancel()
                await task  # Surface a pre-checkpoint error with the fixture's frozen clock.
            self.assertIsNone(leaf._current)
            leaf.release(object())  # Foreign release must not close or release this in-flight writer.
            self.assertFalse(leaf._released or leaf.closed)
            if mode == 'cancel':
                task.cancel('fixture cancel')
                with self.assertRaises(asyncio.CancelledError) as caught:
                    await task
                self.assertEqual(caught.exception.args, ('fixture cancel',))
                self.assertEqual(leaf.last_outcome.kind, session.OutcomeKind.CANCELLED)
            else:
                leaf.close() if mode == 'close' else leaf.release(self.writer)
                release.set()
                self.assertEqual(await asyncio.wait_for(task, 2), ())
                self.assertEqual(leaf.last_outcome.reason,
                    'ITEM_USE_SESSION_CLOSED' if mode == 'close' else 'ITEM_USE_WRITER_RELEASED')
            self.assertEqual(leaf.accepted_count, 0)
            self.assertIsNone(leaf._current)
            self.assertFalse(self.producer._closing or self.reader.closed or self.reader.owner.closed)
            self.assertFalse(self.row['operation_lock'].locked())
            self.producer._sample = original
        self.no_effect()

    async def test_await_source_policy_and_current_selection_mutations_propagate(self):
        await self.deliver()
        original = self.producer._sample
        pins = dict(item_use.SOURCE_PINS)
        game = self.realm.registry.resolve(self.writer)
        selected = game.selection
        for mode in ('source', 'policy', 'selection'):
            leaf = self.bind()
            async def changed(row):
                result = await original(row)
                if mode == 'source':
                    item_use.SOURCE_PINS[next(iter(item_use.SOURCE_PINS))] = '0' * 64
                elif mode == 'policy':
                    leaf.policy = True
                else:
                    game.selection = copy(selected)
                return result
            self.producer._sample = changed
            try:
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    await self.routed(leaf)
                self.assertEqual(leaf.accepted_count, 0)
                self.assertEqual(leaf.last_outcome.kind, session.OutcomeKind.ERROR)
            finally:
                item_use.SOURCE_PINS.clear(); item_use.SOURCE_PINS.update(pins)
                game.selection = selected
                self.producer._sample = original
        self.no_effect()

    async def test_malformed_unsupported_counter_capacity_and_original_error_identity(self):
        await self.deliver()
        leaf = self.bind()
        for wire, exception in ((b'', item_use.MalformedItemUse),
                                (self.request_payload(params=scalar(17, 2)), item_use.UnsupportedItemUse)):
            with self.assertRaises(exception):
                await self.routed(leaf, wire)
            self.assertEqual(leaf.accepted_count, 0)
        error = OSError('never serialize arbitrary error contents')
        original = self.producer._sample
        async def failure(_):
            raise error
        self.producer._sample = failure
        with self.assertRaises(OSError) as caught:
            await self.routed(leaf)
        self.assertIs(caught.exception, error)
        self.assertNotIn('arbitrary', json.dumps(leaf.metadata()))
        self.producer._sample = original
        leaf.accepted_count = item_use.U64_MAX - 1  # Counter boundary, no public test-hook API.
        self.assertEqual(await self.routed(leaf), ())
        self.assertEqual(leaf.accepted_count, item_use.U64_MAX)
        self.assertEqual(await self.routed(leaf), ())
        self.assertEqual(leaf.accepted_count, item_use.U64_MAX)
        self.assertEqual(leaf.last_outcome.reason, 'ITEM_USE_COUNTER_CAPACITY')
        self.no_effect()

    async def test_ambiguous_add_drain_never_becomes_item_use_authority(self):
        leaf = self.bind()
        self.writer.drain.side_effect = OSError('fixture drain failure')
        with self.assertRaises(OSError):
            await self.producer.add_inventory(self.writer)
        self.assertIsNone(self.producer._inventory_delivery_authority)
        self.assertIsNone(self.producer._inventory_current_frame)
        self.assertEqual(self.writer.write.call_count, 1)
        before = len(self.memory.calls)
        self.assertTrue(leaf.closed)  # The original broker _fail closes the registered leaf.
        self.assertEqual(await self.routed(leaf), ())
        self.assertEqual(leaf.last_outcome.kind, session.OutcomeKind.CLOSED)
        self.assertEqual(leaf.accepted_count, 0)
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertEqual(len(self.memory.calls), before)

    async def test_native_validation_reuses_real_delivery_without_recording_a_request(self):
        await self.deliver()
        leaf = self.bind()
        identifier = inventory.validate_frame(self.producer._inventory_frame).identifier
        before = leaf.metadata()
        async with self.row['operation_lock']:
            self.assertIs(await session.ItemUseSession.validate_native_request(
                leaf, self.writer, identifier), True)
            with self.assertRaisesRegex(ValueError, 'IDENTIFIER_NOT_CURRENT_ITEM'):
                await session.ItemUseSession.validate_native_request(
                    leaf, self.writer, identifier + (1 << 32))
        self.assertEqual(leaf.metadata(), before)
        self.assertIsNone(leaf._current)
        self.assertEqual(leaf.accepted_count, 0)
        self.assertEqual(self.service.store.path.read_bytes(), self.saved_after_delivery)
        self.no_effect()

    async def test_native_validation_close_release_cancel_cannot_return_admission(self):
        await self.deliver()
        original = self.producer._sample
        identifier = inventory.validate_frame(self.producer._inventory_frame).identifier
        for mode in ('close', 'release', 'cancel'):
            leaf = self.bind()
            entered, release = asyncio.Event(), asyncio.Event()
            async def held(row):
                result = await original(row)
                entered.set()
                await release.wait()
                return result
            async def validate():
                async with self.row['operation_lock']:
                    return await session.ItemUseSession.validate_native_request(leaf, self.writer, identifier)
            self.producer._sample = held
            task = asyncio.create_task(validate())
            entered_task = asyncio.create_task(entered.wait())
            await asyncio.wait((task, entered_task), return_when=asyncio.FIRST_COMPLETED)
            if not entered.is_set():
                entered_task.cancel()
                await task
            if mode == 'cancel':
                task.cancel('cancel native validation')
                with self.assertRaises(asyncio.CancelledError):
                    await task
            else:
                leaf.close() if mode == 'close' else leaf.release(self.writer)
                release.set()
                with self.assertRaisesRegex(ValueError, 'NATIVE_VALIDATION_UNAVAILABLE'):
                    await task
            self.assertEqual(leaf.accepted_count, 0)
            self.assertIsNone(leaf._current)
            if mode != 'close':
                self.assertIsNone(leaf.last_outcome)
            self.assertFalse(self.row['operation_lock'].locked())
            self.producer._sample = original
        self.no_effect()

    async def test_raw0_received_match_current_identity_params_ordinal_source_owner_and_release(self):
        await self.deliver()
        leaf = self.bind()
        identifier = inventory.validate_frame(self.producer._inventory_frame).identifier
        params = scalar(16, 0) + scalar(1, 1) + scalar(15, 0)
        await self.routed(leaf, self.request_payload(params=params))
        matches = session.ItemUseSession.matches_received
        async with self.row['operation_lock']:
            self.assertTrue(matches(leaf, self.writer, identifier, 1))
            self.assertTrue(matches(leaf, self.writer, identifier, 1))  # Same observation, count stays1.
            for writer, uid, ordinal in ((object(), identifier, 1), (self.writer, identifier + (1 << 32), 1),
                    (self.writer, identifier, 0), (self.writer, identifier, 2),
                    (self.writer, identifier, True)):
                self.assertFalse(matches(leaf, writer, uid, ordinal))
            pins = dict(session.RAW0_SOURCE_PINS)
            pins[next(iter(pins))] = '0' * 64
            with patch.object(session, 'RAW0_SOURCE_PINS', pins):
                with self.assertRaises(item_use.ItemUseSourceError):
                    matches(leaf, self.writer, identifier, 1)
            self.reader.owner.closed = True
            try:
                self.assertFalse(matches(leaf, self.writer, identifier, 1))
            finally:
                self.reader.owner.closed = False
            self.assertTrue(matches(leaf, self.writer, identifier, 1))
        self.assertFalse(matches(leaf, self.writer, identifier, 1))  # No caller row lock.
        mover = self.realm.service(self.writer)
        mover._edge_passability = lambda *_: True
        moved = await mover.handle_CS4E2B(move_payload(mover.snapshot(), 2))
        self.assertTrue(moved.accepted)
        async with self.row['operation_lock']:
            self.assertTrue(matches(leaf, self.writer, identifier, 1))  # Prior request position is not authority.
        for wrong_params in (scalar(1, 1), scalar(1, 1) + scalar(15, 1) + scalar(16, 0),
                params + scalar(17, 1)):
            await self.routed(leaf, self.request_payload(params=wrong_params))
            async with self.row['operation_lock']:
                self.assertFalse(matches(leaf, self.writer, identifier, leaf.accepted_count))
                self.assertFalse(matches(leaf, self.writer, identifier, 1))
        await self.routed(leaf, self.request_payload(params=params))
        ordinal = leaf.accepted_count
        leaf.release(self.writer)
        async with self.row['operation_lock']:
            self.assertFalse(matches(leaf, self.writer, identifier, ordinal))
        self.no_effect()

    async def test_real_update_drain_current_use_stale_intent_move_alive_and_literal_guards(self):
        await self.deliver()
        leaf = self.bind()
        params = scalar(1, 1) + scalar(15, 0) + scalar(16, 0)
        await self.routed(leaf, self.request_payload(params=params))
        identifier = leaf._current.request.identifier
        previous_intent = leaf._current
        original_frame = self.producer._inventory_current_frame
        original_binding = self.producer._inventory_selection_binding
        initial = (self.producer._inventory_frame, self.producer._inventory_operation_frame,
                   original_binding, self.producer._inventory_delivery_authority)
        fields = dict(inventory.validate_frame(original_frame).raw_fields)
        fields[4] += 1
        uid = self.realm.service(self.writer).snapshot().uid
        self.producer.inventory_update_policy = broker.INVENTORY_UPDATE_POLICY
        self.realm._inventory_update_broker = self.producer
        self.policy.inventory_update = True
        result = await self.producer.update_inventory(self.writer, item_identifier=identifier,
            changes={4: fields[4]}, policy=broker.INVENTORY_UPDATE_POLICY)
        self.assertEqual(result['proof_scope'], 'TRANSPORT_DRAIN_ONLY')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(int.from_bytes(self.writer.write.call_args.args[0][2:4], 'little'), 0x0965)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        changed_frame = self.producer._inventory_current_frame
        operation = self.producer._inventory_update_operation
        self.assertIs(operation['new'], changed_frame)
        self.assertEqual(operation['phase'], 'DRAINED')
        self.assertEqual(self.service.store.restore(uid), changed_frame)
        self.assertIsNone(leaf._current)  # Original broker's post-drain release.
        leaf._current = previous_intent  # Negative: even retained old history cannot match new current.
        async with self.row['operation_lock']:
            self.assertIs(leaf._project(self.writer)[2], changed_frame)  # Current authority independently valid.
            self.assertFalse(session.ItemUseSession.matches_received(leaf, self.writer, identifier, 1))
        self.assertEqual(leaf.accepted_count, 1)
        self.assertIs(leaf._current.frame, original_frame)
        self.assertIs(leaf._current.selection_binding, original_binding)
        self.assertTrue(all(a is b for a, b in zip(initial, (
            self.producer._inventory_frame, self.producer._inventory_operation_frame,
            self.producer._inventory_selection_binding, self.producer._inventory_delivery_authority))))
        async with self.row['operation_lock']:
            self.assertIs(await session.ItemUseSession.validate_native_request(leaf, self.writer, identifier), True)
        leaf.release(self.writer)
        await self.routed(leaf, self.request_payload(params=params))
        self.assertEqual(leaf.accepted_count, 2)
        self.assertIs(leaf._current.frame, changed_frame)
        async with self.row['operation_lock']:
            self.assertFalse(session.ItemUseSession.matches_received(leaf, self.writer, identifier, 1))
            self.assertTrue(session.ItemUseSession.matches_received(leaf, self.writer, identifier, 2))
        for phase in ('CLAIMED', 'PERSISTING', 'PERSISTED', 'RESERVING', 'WRITE_ATTEMPTED', 'TERMINAL'):
            operation['phase'] = phase
            self.producer._inventory_current_frame = original_frame
            try:
                with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, 'DRAINED_UPDATE_LITERAL'):
                    async with self.row['operation_lock']:
                        await session.ItemUseSession.validate_native_request(leaf, self.writer, identifier)
            finally:
                operation['phase'] = 'DRAINED'
                self.producer._inventory_current_frame = changed_frame
        class NonExactPhase(str):
            pass
        operation['phase'] = NonExactPhase('DRAINED')
        try:
            with self.assertRaisesRegex(ValueError, 'DRAINED_UPDATE_LITERAL'):
                async with self.row['operation_lock']:
                    await session.ItemUseSession.validate_native_request(leaf, self.writer, identifier)
        finally:
            operation['phase'] = 'DRAINED'
        original_refs = operation['refs']
        copied_position = copy(original_refs[4])
        self.assertIsNot(copied_position, original_refs[4])
        operation['refs'] = (*original_refs[:4], copied_position, *original_refs[5:])
        try:
            with self.assertRaisesRegex(ValueError, 'SAME_DRAINED_UPDATE_SELECTION'):
                async with self.row['operation_lock']:
                    await session.ItemUseSession.validate_native_request(leaf, self.writer, identifier)
        finally:
            operation['refs'] = original_refs
        self.producer._inventory_current_frame = bytes(bytearray(changed_frame))
        with self.assertRaisesRegex(ValueError, 'DRAINED_UPDATE_LITERAL'):
            async with self.row['operation_lock']:
                await session.ItemUseSession.validate_native_request(leaf, self.writer, identifier)
        self.producer._inventory_current_frame = changed_frame
        original_sample = self.producer._sample
        async def swapped_operation(row):
            sample = await original_sample(row)
            self.producer._inventory_update_operation = dict(operation)
            return sample
        self.producer._sample = swapped_operation
        try:
            with self.assertRaisesRegex(ValueError, 'CURRENT_UPDATE_OPERATION_CHANGED'):
                await self.routed(leaf, self.request_payload(params=params))
            self.assertEqual(leaf.accepted_count, 2)
        finally:
            self.producer._sample = original_sample
            self.producer._inventory_update_operation = operation
        mover = self.realm.service(self.writer)
        mover._edge_passability = lambda *_: True
        moved = await mover.handle_CS4E2B(move_payload(mover.snapshot(), 2))
        self.assertTrue(moved.accepted)
        async with self.row['operation_lock']:
            await self.producer._send(self.writer, self.row, (broker.ALIVE_FRAME,), game=True)
        self.assertGreater(self.row['policy_row'].sent, operation['sent_after'])
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        await self.routed(leaf, self.request_payload(params=params))
        self.assertEqual(leaf.accepted_count, 3)
        async with self.row['operation_lock']:
            self.assertTrue(session.ItemUseSession.matches_received(leaf, self.writer, identifier, 3))
        self.no_effect()

    async def test_current_none_and_unstored_frame_refuse_without_initial_fallback(self):
        await self.deliver()
        leaf = self.bind()
        original_frame = self.producer._inventory_current_frame
        self.assertIs(original_frame, self.producer._inventory_frame)
        fields = dict(inventory.validate_frame(original_frame).raw_fields)
        fields[4] += 1
        changed = inventory.build_add(fields)
        fields[3] -= 1  # Canonical bytes, outside accepted UPDATE callback fields.
        unsupported = inventory.build_add(fields)
        for current, code in ((None, 'DRAINED_CURRENT_FRAME'),
                              (bytes(bytearray(original_frame)), 'INITIAL_CURRENT_LITERAL'),
                              (changed, 'INITIAL_CURRENT_LITERAL'),
                              (unsupported, 'INITIAL_CURRENT_LITERAL')):
            self.producer._inventory_current_frame = current
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                await self.routed(leaf)
            self.assertEqual(leaf.accepted_count, 0)
        self.producer._inventory_current_frame = original_frame
        self.assertEqual(self.service.store.path.read_bytes(), self.saved_after_delivery)
        self.no_effect()

    async def test_current_literal_copy_and_position_change_during_checkpoint_refuse(self):
        await self.deliver()
        leaf = self.bind()
        original_sample = self.producer._sample
        current = self.producer._inventory_current_frame
        mover = self.realm.service(self.writer)
        original_position = mover.snapshot()
        for mode in ('copy', 'position'):
            async def changed(row):
                result = await original_sample(row)
                if mode == 'copy':
                    self.producer._inventory_current_frame = bytes(bytearray(current))
                else:
                    mover._edge_passability = lambda *_: True
                    moved = await mover.handle_CS4E2B(move_payload(mover.snapshot(), 2))
                    self.assertTrue(moved.accepted)
                return result
            self.producer._sample = changed
            try:
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError,
                        'CURRENT_BINDING_CHANGED|INVENTORY_AUTHORITY_CHANGED|INITIAL_CURRENT_LITERAL'):
                    await self.routed(leaf)
                self.assertEqual(leaf.accepted_count, 0)
            finally:
                self.producer._sample = original_sample
                self.producer._inventory_current_frame = current
        self.assertIsNot(mover.snapshot(), original_position)
        self.no_effect()

    async def test_original_restored_delivery_seed_and_committed_move_keep_current_authority(self):
        await broker_fixture.InventoryRestoreOnlyBrokerTests.adopt_restored(self)
        initial = self.producer._inventory_frame
        stored = self.service.store.path.read_bytes()
        result = await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertIs(self.producer._inventory_current_frame, initial)
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.reads_after_delivery = len(self.memory.calls)
        leaf = self.bind()
        mover = self.realm.service(self.writer)
        mover._edge_passability = lambda *_: True
        moved = await mover.handle_CS4E2B(move_payload(mover.snapshot(), 2))
        self.assertTrue(moved.accepted)
        params = scalar(1, 1) + scalar(15, 0) + scalar(16, 0)
        await self.routed(leaf, self.request_payload(params=params))
        async with self.row['operation_lock']:
            self.assertTrue(session.ItemUseSession.matches_received(
                leaf, self.writer, leaf._current.request.identifier, 1))
        self.assertEqual(self.service.store.path.read_bytes(), stored)
        self.no_effect()


class ReselectionConsumerTests(unittest.IsolatedAsyncioTestCase):
    from tools.local_original_session.broker_tests import InventoryReselectionTests as _Fixture
    asyncSetUp = _Fixture.asyncSetUp
    rebuild, dispatch, select = _Fixture.rebuild, _Fixture.dispatch, _Fixture.select
    add, reset_writes = _Fixture.add, _Fixture.reset_writes
    restart_reselect = _Fixture.restart_reselect

    async def test_actual_reselection_retires_old_use_and_accepts_only_new_binding(self):
        from tools.local_original_session import broker
        await self.add()
        old = self.producer.inventory_selection_current(self.writer)
        old_service, old_leaf = old.service, old.item_use_session
        fields = dict(inventory.validate_frame(old.current_frame).raw_fields)
        identifier = fields[1]
        result = await self.producer.update_inventory(self.writer, item_identifier=identifier,
            changes={4: fields[4] + 1}, policy=broker.INVENTORY_UPDATE_POLICY)
        self.assertEqual(result['status'], 'COMMITTED')
        old_operation = old.update_operation
        self.assertEqual(old_operation['phase'], 'DRAINED')
        params = scalar(1, 1) + scalar(15, 0) + scalar(16, 0)
        request = body(params, identifier)
        await self.dispatch(item_use.OPCODE, request)
        old_intent = old_leaf._current
        old_ordinal = old_leaf.accepted_count
        self.assertIsNotNone(old_intent)
        self.assertGreater(old_ordinal, 0)
        evidence = (old.attempted, old.write_attempted, old_service._claimed, old.frame,
                    old.operation_frame, old.current_frame, old.selection_binding, old.delivery_authority)
        stored = old.store.path.read_bytes()
        new = await self.restart_reselect()
        self.assertIs(new.previous, old)
        self.assertTrue(old_service._closed and old_leaf.closed)
        self.assertIsNone(old_leaf._current)
        self.assertEqual(old_leaf.accepted_count, old_ordinal)
        self.assertIs(self.producer._item_use_session, new.item_use_session)
        self.assertIs(self.realm._item_use_session, new.item_use_session)
        self.assertIsNone(new.update_operation)
        self.assertIsNot(new.service, old_service)
        self.assertIsNot(new.selection_binding, old.selection_binding)
        self.assertEqual(new.frame, old.current_frame)
        self.assertIsNot(new.frame, old.current_frame)
        self.reset_writes()
        count = len(self.memory.calls)
        async with self.row['operation_lock']:
            with self.assertRaises(ValueError): old_service._current(self.writer, self.row)
            self.assertEqual(await old_leaf.handle(self.writer, request), ())
            self.assertEqual(old_leaf.last_outcome.kind, session.OutcomeKind.CLOSED)
            with self.assertRaises(ValueError): await old_leaf.validate_native_request(self.writer, identifier)
            self.assertFalse(old_leaf.matches_received(self.writer, identifier, old_ordinal))
        self.assertEqual(len(self.memory.calls), count)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        await self.add()
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertIs(new.current_frame, new.frame)
        self.assertEqual(new.store.path.read_bytes(), stored)
        self.reset_writes()
        leaf = new.item_use_session
        self.assertEqual(leaf.accepted_count, 0)
        async with self.row['operation_lock']:
            self.assertFalse(leaf.matches_received(self.writer, identifier, old_ordinal))
            # Negative stale private history, never a positive generation fixture.
            leaf._current = old_intent
            self.assertFalse(leaf.matches_received(self.writer, identifier, old_ordinal))
            leaf.release(self.writer)
            self.producer._inventory_update_operation = old_operation
            try:
                with self.assertRaises(ValueError): await leaf.validate_native_request(self.writer, identifier)
            finally:
                self.producer._inventory_update_operation = None  # Restore the real new generation's original value.
        count = len(self.memory.calls)
        await self.dispatch(item_use.OPCODE, request)  # Original route reads the new active session.
        self.assertEqual(leaf.accepted_count, 1)
        self.assertIs(leaf._current.selection_binding, new.selection_binding)
        self.assertIs(leaf._current.frame, new.current_frame)
        self.assertIsNot(leaf._current, old_intent)
        async with self.row['operation_lock']:
            self.assertTrue(leaf.matches_received(self.writer, identifier, 1))
        self.assertEqual(len(self.memory.calls), count)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        self.assertIs(old.update_operation, old_operation)
        self.assertEqual(old_operation['phase'], 'DRAINED')
        self.assertIs(old_intent.selection_binding, old.selection_binding)
        for before, after in zip(evidence, (old.attempted, old.write_attempted, old_service._claimed,
                old.frame, old.operation_frame, old.current_frame, old.selection_binding, old.delivery_authority)):
            self.assertIs(before, after)


if __name__ == '__main__':
    unittest.main()
