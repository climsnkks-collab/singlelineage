"""Opt-in current-inventory validation of CS0960; no use effect or reply.

The receiving broker owns the actual row operation_lock. This service performs
read-only canonical Store checks and the original native-owner checkpoint; it
never grants inventory, queries item memory, writes a frame or commits a Store.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from types import MethodType

from tools.local_original_session import inventory, item_use, movement, observe
from tools.local_original_session.inventory_store import InventoryStore
from tools.local_original_session import inventory_store

POLICY = 'EXPLICIT_LOCAL_VALIDATED_ITEM_USE_INTENT'
U64_MAX = item_use.U64_MAX
need = inventory.need
RAW0_SOURCE_PINS = {
    'work/local_server_rea_20261016/run40_item_raw0_branch/findings.md':
        '9d51db3062ed47934da2b9d5843f3c2111232a5f688e7447abad77b2cd71aec7',
    'work/local_server_rea_20261016/run40_item_raw0_branch/source-evidence.json':
        '0f9b83dc5ec9ac8f4d07cf0efc508ff521ef5a0ba1186be16a24a7afd19ee567',
}
_INVENTORY_SOURCE_ERRORS = frozenset({
    'INVENTORY_SOURCE_BOUND', 'INVENTORY_SOURCE_CHANGED', 'INVENTORY_SOURCE_CONTROL_CHANGED',
    'INVENTORY_EXACT_QUERY_SOURCE_REQUIRED', 'INVENTORY_REQUIRED_SOURCE_CHANGED',
    'INVENTORY_FIELD_SOURCE_CHANGED', 'INVENTORY_FIXED_CATALOG_CHANGED',
    'INVENTORY_EXACT_CURRENT_MAP_SOURCE_REQUIRED', 'INVENTORY_STORE_PARENT_SOURCE_CHANGED',
})


def _raw0_source_ready():
    # Existing run37 pins include the original sender's absent-f15/f16 ->
    # present-zero copy behavior. Run40 pins only the selected raw0 producer.
    item_use.source_ready()
    proof = None
    for relative, expected in RAW0_SOURCE_PINS.items():
        try:
            with (item_use.ROOT / relative).open('rb') as stream:
                raw = stream.read(1048577)
        except OSError:
            raise item_use.ItemUseSourceError('ITEM_USE_RAW0_SOURCE_UNAVAILABLE') from None
        if not 0 < len(raw) <= 1048576 or hashlib.sha256(raw).hexdigest() != expected:
            raise item_use.ItemUseSourceError('ITEM_USE_RAW0_SOURCE_CHANGED')
        if relative.endswith('.json'):
            proof = json.loads(raw)
    if not (proof['CONTROL_sha256'] == item_use.CONTROL_SHA256
            and proof['schema'] == 'run40-item-raw0-main-index-v1'
            and proof['raw0_table']['key'] == 0
            and proof['raw0_table']['target_rva'] == '0x4fe1fc'
            and proof['claims']['params'] == 'original inline UseItemReqParam stack object; '
                'ownhasbits8000; nestedf1 int32=1 only ownoptionalpresent; f17 absent; '
                'bool+74 raw1 but bit16 absent'):
        raise item_use.ItemUseSourceError('ITEM_USE_RAW0_SOURCE_CONTRACT_CHANGED')


class OutcomeKind(str, Enum):
    DISABLED = 'DISABLED'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'
    ERROR = 'ERROR'
    CANCELLED = 'CANCELLED'
    CLOSED = 'CLOSED'


@dataclass(frozen=True, slots=True)
class ItemUseOutcome:
    kind: OutcomeKind
    reason: str
    accepted_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class _Intent:
    # Private immutable received bytes/ordered typed params, never a capability
    # exported for later requests. Every frame is freshly validated.
    request: item_use.ItemUseRequest = field(repr=False)
    writer: object = field(repr=False)
    accepted_ordinal: int
    frame: bytes = field(repr=False)
    selection_binding: tuple = field(repr=False)


def _original(owner, name, function):
    method = getattr(owner, name, None)
    need(type(method) is MethodType and method.__self__ is owner
         and method.__func__ is function, 'ITEM_USE_ORIGINAL_METHOD_REQUIRED')
    return method


def _category(error):
    if isinstance(error, item_use.ItemUseSourceError):
        return 'ITEM_USE_SOURCE_INVALID'
    if isinstance(error, item_use.MalformedItemUse):
        return 'MALFORMED_ITEM_USE_PAYLOAD'
    if isinstance(error, item_use.UnsupportedItemUse):
        return 'UNSUPPORTED_ITEM_USE_PAYLOAD'
    if isinstance(error, (ValueError, OSError)):
        return 'ITEM_USE_CURRENT_AUTHORITY_INVALID'
    return 'ITEM_USE_UNEXPECTED_ERROR'


class ItemUseSession:
    """One private intent and an exact uint64 accepted counter, default off."""
    def __init__(self, broker, *, policy=None):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker, 'ITEM_USE_REAL_BROKER_REQUIRED')
        need(policy is None or type(policy) is str and policy == POLICY,
             'ITEM_USE_EXPLICIT_POLICY_REQUIRED')
        service = broker._inventory_service
        need(type(service) is inventory.InventoryService and service.broker is broker,
             'ITEM_USE_REAL_INVENTORY_SERVICE_REQUIRED')
        reader = service.reader
        need(type(reader) is observe.RetainedSceneReader,
             'ITEM_USE_REAL_RETAINED_READER_REQUIRED')
        self._collection_policy = getattr(broker, '_inventory_collection_policy', None)
        need(self._collection_policy is None or (type(self._collection_policy) is str
             and self._collection_policy == inventory.COLLECTION_POLICY),
             'ITEM_USE_EXPLICIT_COLLECTION_POLICY_REQUIRED')
        # M1 kit: the saved Store row is the current-frame authority (potion
        # quantity/removal changes it without an UPDATE operation record).
        self._kit_policy = getattr(broker, '_inventory_kit_policy', None)
        need(self._kit_policy is None or (self._kit_policy == inventory.KIT_POLICY
             and self._collection_policy is None), 'ITEM_USE_EXPLICIT_KIT_POLICY_REQUIRED')
        self.broker, self.policy = broker, policy
        self._service, self._reader, self._backend = service, reader, reader.backend
        self._store = service._persistence_store()
        self._store_bound = service._store_bound
        self._realm = broker.realm
        self.closed = False
        self.accepted_count = 0
        self.last_outcome = None
        self.last_invalidation = None
        self._current = None
        self._inflight_writer, self._released = None, False
        self._lock = asyncio.Lock()  # Never acquire the caller's row lock again.

    def _clear(self, reason):
        self._current = None
        self.last_invalidation = reason

    def _outcome(self, kind, reason, ordinal=None):
        self.last_outcome = ItemUseOutcome(kind, reason, ordinal)
        return ()

    def _unavailable(self):
        if self.closed:
            return OutcomeKind.CLOSED, 'ITEM_USE_SESSION_CLOSED'
        need(self.policy is None or type(self.policy) is str and self.policy == POLICY,
             'ITEM_USE_EXPLICIT_POLICY_REQUIRED')
        if self.policy is None:
            return OutcomeKind.DISABLED, 'ITEM_USE_SESSION_DISABLED'
        if self._released:
            return OutcomeKind.REJECTED, 'ITEM_USE_WRITER_RELEASED'
        need(type(self.accepted_count) is int and 0 <= self.accepted_count <= U64_MAX,
             'ITEM_USE_UINT64_COUNTER_REQUIRED')
        if self.accepted_count == U64_MAX:
            return OutcomeKind.REJECTED, 'ITEM_USE_COUNTER_CAPACITY'
        return None

    def _current_authority(self, writer, *, equipment_operation=None, item_identifier=None):
        from tools.local_original_session.broker import PersistentBroker
        broker, service, reader = self.broker, self._service, self._reader
        mode = getattr(broker, '_inventory_collection_policy', None)
        need(type(mode) is type(self._collection_policy) and mode == self._collection_policy,
             'ITEM_USE_COLLECTION_POLICY_CHANGED')
        need(type(broker) is PersistentBroker and broker.realm is self._realm
             and broker._item_use_session is self and broker.realm._item_use_session is self,
             'ITEM_USE_SAME_REGISTERED_SESSION_REQUIRED')
        need(broker._inventory_service is service and service.broker is broker
             and service.reader is reader and reader.backend is self._backend
             and service.policy == inventory.POLICY
             and getattr(broker.policy, 'item_use_intent', None) is True,
             'ITEM_USE_CURRENT_INVENTORY_SERVICE_REQUIRED')
        _original(service, '_current', inventory.InventoryService._current)
        _original(service, '_authority', inventory.InventoryService._authority)
        _original(service, '_persistence_store', inventory.InventoryService._persistence_store)
        _original(broker, '_inventory_selection_frame_current',
                  PersistentBroker._inventory_selection_frame_current)
        _original(broker, '_checkpoint', PersistentBroker._checkpoint)
        _original(reader, 'validate', observe.RetainedSceneReader.validate)
        validator = reader.backend.validate
        need(type(validator) is MethodType and validator.__self__ is reader
             and validator.__func__ is observe.RetainedSceneReader.validate,
             'ITEM_USE_ORIGINAL_RETAINED_VALIDATOR_REQUIRED')
        store = service._persistence_store()
        need(type(store) is InventoryStore and store is self._store
             and service._store_bound is self._store_bound
             and broker._inventory_store is store,
             'ITEM_USE_CURRENT_STORE_BINDING_REQUIRED')
        restore = _original(store, 'restore', InventoryStore.restore)
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows) == 1, 'ITEM_USE_CURRENT_CLAIM_REQUIRED')
        row, = rows
        restart = row.get('_restart')
        need(restart is None or type(restart) is dict and restart.get('phase') == 'DRAINED'
             and restart.get('selection_cleared') is True,
             'ITEM_USE_NO_PENDING_RESTART_REQUIRED')
        authority = service._current(writer, row)  # Current position, saved selection, lock/owner.
        transfer = getattr(broker._inventory_generation, 'transfer_session', None)
        if getattr(broker, '_item_transfer_policy_bound', None) is not None:
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            need(type(transfer) is ItemTransferSession, 'ITEM_USE_REAL_CUSTODY_SESSION_REQUIRED')
            transfer.validate_use_locked(writer, read_only_initialization=item_identifier is None)
        initial_frame = broker._inventory_frame
        need(type(initial_frame) is bytes and broker._inventory_operation_frame is initial_frame,
             'ITEM_USE_CURRENT_CANONICAL_FRAME_REQUIRED')
        broker._inventory_selection_frame_current(writer, row, initial_frame)  # Original 11 identities.
        need(type(broker._inventory_selection_binding) is tuple
             and len(broker._inventory_selection_binding) == 11,
             'ITEM_USE_ORIGINAL_SELECTION_BINDING_REQUIRED')
        delivered = broker._inventory_delivery_authority
        need(type(delivered) is tuple and len(delivered) == 3
             and type(delivered[1]) is tuple and len(delivered[1]) == 24
             and broker._inventory_attempted is True and broker._inventory_write_attempted is True
             and broker._inventory_prewrite_refusal is None
             and broker._inventory_admission_expired is False
             and service._claimed is True and service._inflight is False,
             'ITEM_USE_COMPLETED_INVENTORY_DELIVERY_REQUIRED')
        # Successful delivery proves this selection/owner/frame lifetime. Its
        # historical Position is not current movement authority: only identity
        # uid/name/map is retained across ordinary movement in the same selection.
        old_position = delivered[0]
        need(type(old_position) is movement.Position and delivered[1][14] is old_position
             and (old_position.uid, old_position.name, old_position.map_id)
                 == (authority[0].uid, authority[0].name, authority[0].map_id)
             and len(authority[1]) == len(delivered[1])
             and all(a is b for index, (a, b) in enumerate(zip(delivered[1], authority[1]))
                     if index != 14)
             and delivered[2] == authority[2], 'ITEM_USE_SAME_DELIVERED_SELECTION_REQUIRED')
        admitted = row['policy_row']
        if equipment_operation is None:
            need(admitted.drain_started_ns is None and admitted.pending_opcode is None
                 and admitted.pending_size == 0, 'ITEM_USE_NO_PENDING_INVENTORY_DELIVERY_REQUIRED')
        else:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            effect = getattr(broker, '_item_equipment_effect', None)
            need(type(effect) is ItemEquipmentEffect and effect.broker is broker and
                 effect is getattr(broker.realm, '_item_equipment_effect', None) and
                 effect.validate_pending.__func__ is ItemEquipmentEffect.validate_pending,
                 'ITEM_USE_EXACT_EQUIPMENT_CONSUMER_REQUIRED')
            effect.validate_pending(writer, row, equipment_operation, admitted)
        # The initial ADD literal/once proof never becomes an UPDATE or current
        # value. Only the broker's post-drain canonical current frame is used.
        frame = broker._inventory_current_frame
        need(type(frame) is bytes, 'ITEM_USE_DRAINED_CURRENT_FRAME_REQUIRED')
        operation = broker._inventory_update_operation
        if operation is None:
            need(frame is initial_frame or self._kit_policy is not None,
                 'ITEM_USE_INITIAL_CURRENT_LITERAL_REQUIRED')
        else:
            need(type(operation) is dict and type(operation.get('phase')) is str
                 and operation.get('phase') == 'DRAINED'
                 and operation.get('writer') is writer and operation.get('row') is row
                 and operation.get('lock') is row['operation_lock'] and operation.get('new') is frame
                 and all(operation.get(key) is True for key in (
                     'persist_attempted', 'persisted', 'write_attempted', 'drain_returned',
                     'post_owner_verified')),
                 'ITEM_USE_DRAINED_UPDATE_LITERAL_REQUIRED')
            refs, updated = operation.get('refs'), operation.get('authority')
            current_refs = (broker.realm, broker.realm.registry, broker.realm.registry.resolve(writer),
                broker.realm.service(writer), authority[0], broker.realm.registry.resolve(writer).selection,
                service, reader, store, broker._inventory_selection_binding, delivered, initial_frame,
                broker._inventory_restore_only)
            need(type(refs) is tuple and len(refs) == 13
                 and all(a is b for index, (a, b) in enumerate(zip(refs, current_refs)) if index != 4)
                 and type(refs[4]) is movement.Position
                 and (refs[4].uid, refs[4].name, refs[4].map_id)
                     == (authority[0].uid, authority[0].name, authority[0].map_id)
                 and type(updated) is tuple and len(updated) == 3
                 and type(updated[1]) is tuple and len(updated[1]) == 24
                 and type(updated[0]) is movement.Position and updated[1][14] is updated[0]
                 and refs[4] is updated[0]
                 and (updated[0].uid, updated[0].name, updated[0].map_id)
                     == (authority[0].uid, authority[0].name, authority[0].map_id)
                 and all(a is b for index, (a, b) in enumerate(zip(updated[1], authority[1])) if index != 14)
                 and updated[2] == authority[2], 'ITEM_USE_SAME_DRAINED_UPDATE_SELECTION_REQUIRED')
            sent_before, sent_after = operation.get('sent_before'), operation.get('sent_after')
            need(type(sent_before) is int and type(sent_after) is int
                 and type(admitted.sent) is int
                 and 0 <= sent_before < sent_after <= U64_MAX and sent_after == sent_before + 1
                 and admitted.sent >= sent_after, 'ITEM_USE_DRAINED_UPDATE_COUNTER_REQUIRED')
        if self._kit_policy is not None:
            need(operation is None, 'ITEM_USE_KIT_NO_UPDATE_OPERATION_REQUIRED')
            current_items = inventory.validate_kit_frame(frame)
            initial_items = {item.identifier: item for item in inventory.validate_kit_frame(initial_frame)}
            need(all(current.identifier in initial_items and
                     {n for n, value in initial_items[current.identifier].raw_fields
                      if dict(current.raw_fields)[n] != value} <= {4, 5, 7, 18}
                     for current in current_items), 'ITEM_USE_SAME_CURRENT_COLLECTION_FIELDS_REQUIRED')
            if item_identifier is None:
                item = current_items[0]  # Initial/preparation anchor, not a selected-use UID.
            else:
                members = tuple(item for item in current_items if item.identifier == item_identifier)
                need(type(item_identifier) is int and len(members) == 1, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                item, = members
        elif self._collection_policy is None:
            item = inventory.validate_frame(frame)
            initial = inventory.validate_frame(initial_frame)
            initial_fields, current_fields = dict(initial.raw_fields), dict(item.raw_fields)
            need(item.identifier == initial.identifier
                 and {n for n in initial_fields if initial_fields[n] != current_fields[n]} <= {4, 5, 7, 18},
                 'ITEM_USE_SAME_CURRENT_ITEM_FIELDS_REQUIRED')
        else:
            need(store._collection_policy == inventory_store.COLLECTION_STORE_POLICY,
                 'ITEM_USE_COLLECTION_STORE_POLICY_REQUIRED')
            current_items = inventory.validate_collection_frame(frame, policy=self._collection_policy)
            initial_items = inventory.validate_collection_frame(initial_frame, policy=self._collection_policy)
            need(len(current_items) == len(initial_items) and all(
                 current.identifier == initial.identifier and
                 {n for n, value in initial.raw_fields if dict(current.raw_fields)[n] != value} <= {4, 5, 7, 18}
                 for current, initial in zip(current_items, initial_items)),
                 'ITEM_USE_SAME_CURRENT_COLLECTION_FIELDS_REQUIRED')
            if item_identifier is None:
                item = current_items[0] # Initial/preparation anchor, not a selected-use UID.
            else:
                need(type(item_identifier) is int and 0 < item_identifier < 1 << 32,
                     'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                members = tuple(item for item in current_items if item.identifier == item_identifier)
                need(len(members) == 1, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                item, = members
        restored = restore(authority[0].uid)  # Original bounded read, never grant/write.
        need(type(restored) is bytes and restored == frame,
             'ITEM_USE_CURRENT_STORED_FRAME_REQUIRED')
        return row, authority, frame, delivered, broker._inventory_selection_binding, store, item

    def _project(self, writer, *, equipment_operation=None, item_identifier=None):
        operation = self.broker._inventory_update_operation
        before = self._current_authority(writer, equipment_operation=equipment_operation, item_identifier=item_identifier)
        self._reader.validate()  # Retained identity/Job, not an item-memory query.
        after = self._current_authority(writer, equipment_operation=equipment_operation, item_identifier=item_identifier)
        self._same(before, after)
        need(self.broker._inventory_update_operation is operation,
             'ITEM_USE_CURRENT_UPDATE_OPERATION_CHANGED')
        return after

    def _same(self, before, after):
        need(before[0] is after[0] and all(before[n] is after[n] for n in (2, 3, 4, 5)),
             'ITEM_USE_CURRENT_BINDING_CHANGED')
        inventory.InventoryService._same(before[1], after[1])  # Request-local position stays identical.
        need(before[6] == after[6], 'ITEM_USE_CURRENT_ITEM_CHANGED')

    @staticmethod
    def _source(request):
        item_use.source_ready()
        if 17 in request.params.present_fields:
            item_use._enum17_one_source_ready()

    async def handle(self, writer, payload) -> tuple[bytes, ...]:
        """Validate this received request only, returning no ACK/effect frames.

        Identifier mismatch is a local REJECTED result. Parser/source/current
        owner/Store errors propagate unchanged after fixed-category reporting.
        """
        async with self._lock:
            self._released = False
            self._inflight_writer = writer
            try:
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                request = item_use.parse_payload(payload)
                operation = self.broker._inventory_update_operation
                try:
                    before = self._project(writer, item_identifier=request.identifier)
                except ValueError as error:
                    if str(error) != 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM':raise
                    self._clear('ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                    return self._outcome(OutcomeKind.REJECTED, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                if request.identifier != before[6].identifier:
                    self._clear('ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                    return self._outcome(OutcomeKind.REJECTED, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                await self.broker._checkpoint(writer, before[0])
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                self._source(request)
                after = self._project(writer, item_identifier=request.identifier)
                self._same(before, after)
                need(self.broker._inventory_update_operation is operation,
                     'ITEM_USE_CURRENT_UPDATE_OPERATION_CHANGED')
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                ordinal = self.accepted_count + 1
                self._current = _Intent(request, writer, ordinal, after[2], after[4])
                self.accepted_count = ordinal
                self.last_invalidation = None
                return self._outcome(OutcomeKind.ACCEPTED, 'VALIDATED_ITEM_USE_INTENT_ONLY', ordinal)
            except asyncio.CancelledError:
                self._clear('ITEM_USE_SESSION_CANCELLED')
                self._outcome(OutcomeKind.CANCELLED, 'ITEM_USE_SESSION_CANCELLED')
                raise
            except Exception as error:
                category = _category(error)
                self._clear(category)
                self._outcome(OutcomeKind.ERROR, category)
                raise
            finally:
                self._inflight_writer = None
                self._released = False

    async def validate_native_request(self, writer, item_identifier):
        """Current read-only admission before the caller's native request.

        Caller holds the real row lock. True is no request/params, send, native
        item query, received intent or transferable permission. Any refusal
        raises; original source/owner/Store/cancellation errors propagate. Only
        the existing transient in-flight state changes during this call.
        """
        async with self._lock:
            self._inflight_writer, self._released = writer, False
            try:
                need(self._unavailable() is None, 'ITEM_USE_NATIVE_VALIDATION_UNAVAILABLE')
                need(type(item_identifier) is int and 0 <= item_identifier <= U64_MAX,
                     'ITEM_USE_UINT64_IDENTIFIER_REQUIRED')
                item_use.source_ready()
                operation = self.broker._inventory_update_operation
                before = self._project(writer, item_identifier=item_identifier)
                need(item_identifier == before[6].identifier, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                await self.broker._checkpoint(writer, before[0])
                need(self._unavailable() is None, 'ITEM_USE_NATIVE_VALIDATION_UNAVAILABLE')
                item_use.source_ready()
                after = self._project(writer, item_identifier=item_identifier)
                self._same(before, after)
                need(self.broker._inventory_update_operation is operation,
                     'ITEM_USE_CURRENT_UPDATE_OPERATION_CHANGED')
                need(self._unavailable() is None, 'ITEM_USE_NATIVE_VALIDATION_UNAVAILABLE')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                return True
            finally:
                self._inflight_writer, self._released = None, False

    def matches_received(self, writer, item_identifier, accepted_ordinal):
        """Observe the current received raw0-shaped intent under caller row lock.

        Missing read authority or mismatched writer/id/ordinal/params returns
        False. Source and IO failures propagate unchanged; other unexpected
        errors also propagate. This never consumes a receipt or records a new
        acceptance: repeated True observes the same ordinal only.
        """
        current = self._current
        if (self.closed or type(self.policy) is not str or self.policy != POLICY
                or type(item_identifier) is not int or not 0 <= item_identifier <= U64_MAX
                or type(accepted_ordinal) is not int or not 1 <= accepted_ordinal <= U64_MAX
                or current is None or current.writer is not writer
                or current.request.identifier != item_identifier
                or current.accepted_ordinal != accepted_ordinal):
            return False
        params = current.request.params
        if params.present_fields != {1, 15, 16} or len(params.fields) != 3:
            return False
        expected = {1: 1, 15: 0, 16: 0}
        if any(part.kind != 'int32' or type(part.value) is not int
               or part.value != expected[part.number] for part in params.fields):
            return False
        _raw0_source_ready()
        try:
            current_authority = self._project(writer, item_identifier=item_identifier)
        except item_use.ItemUseSourceError:
            raise
        except ValueError as error:
            if str(error) in _INVENTORY_SOURCE_ERRORS:
                raise
            return False
        _raw0_source_ready()
        return (self._current is current and not self.closed
                and type(self.policy) is str and self.policy == POLICY
                and current_authority[2] is current.frame
                and current_authority[4] is current.selection_binding
                and current_authority[6].identifier == item_identifier)

    def release(self, writer):
        if self._inflight_writer is writer:
            self._released = True
        if self._current is not None and self._current.writer is writer:
            self._clear('ITEM_USE_WRITER_RELEASED')

    def close(self):
        self.closed = True
        self._clear('ITEM_USE_SESSION_CLOSED')
        self._outcome(OutcomeKind.CLOSED, 'ITEM_USE_SESSION_CLOSED')

    def metadata(self):
        # Recent history only. Calling metadata never grants current authority,
        # reads Store/native data, exposes request values or requires a row lock.
        outcome = self.last_outcome
        enabled = type(self.policy) is str and self.policy == POLICY
        return dict(enabled=enabled, policy=POLICY if enabled else None, closed=self.closed,
            accepted_count=self.accepted_count, intent_recorded=self._current is not None,
            last_invalidation=self.last_invalidation,
            last_outcome=None if outcome is None else dict(kind=outcome.kind.value,
                reason=outcome.reason, accepted_ordinal=outcome.accepted_ordinal),
            proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY',
            response_policy='NO_ITEM_USE_REPLY_OR_EFFECT')
