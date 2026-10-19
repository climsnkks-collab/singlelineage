"""Source-bound local item custody preflight; live transfer remains unavailable.

The codec and single-file custody store are usable static/local components.
No ground appearance, observed-current authority or transfer operation is
invented here. A real source-closed provider/binder is not installed.
"""
from __future__ import annotations

POLICY = 'EXPLICIT_LOCAL_SOURCE_BOUND_ITEM_TRANSFER'
PROFILE = 'sibling-background-item-drop-pickup-spawn' # Deliberately not registered before UI/source closure.
GROUND_INPUT_ERROR = 'ITEM_TRANSFER_GROUND_APPEARANCE_SOURCE_REQUIRED'
MISSING_HARD_INPUTS = (
    'template1_authoritative_ground_appearance_and_complete_raw_creation_input',
)
# Mapping and ordering may be selected as explicit local backend policy; their
# original-server values remain unknown and are not the permanent blocker.
FUTURE_BINDING_REQUIREMENTS = (
    'current_retained_owner_selected_player_writer_row_generation_and_scene',
    'actual_drop_inventory_uid_current_whole_B_quantity_and_unequipped_state',
    'owned_ground_publication_and_unique_Item_lifetime_epoch',
    'explicit_local_inventory_ground_return_uid_mapping_and_conservation',
    'authenticated_get_ground_key_quantity_coordinates_current_local_epoch_binding',
    'same_operation_lock_single_commit_once_drain_fatal_unknown_no_replay',
)


def need(value, code):
    if not value:
        raise ValueError(code)


class GroundSourceNotReady(ValueError):
    """Closed source contract has no valid template1 ground creation input."""


def validate_mode(*, policy, custody_policy, inventory_policy, frame,
                  store_policy, collection_policy, collection_grant,
                  reselection_policy, delivery_policy, missing_row_policy,
                  restart_policy):
    from tools.local_original_session import inventory, inventory_store, restart
    from tools.local_original_session.item_custody import CUSTODY_POLICY
    from tools.local_original_session.feature_config import LOCAL_SAVED_ROW_ON_RESELECTION, LOCAL_WORLD_READY_ONCE
    need(type(policy) is str and policy == POLICY
         and type(custody_policy) is str and custody_policy == CUSTODY_POLICY,
         'ITEM_TRANSFER_EXPLICIT_CUSTODY_POLICY_REQUIRED')
    need(inventory_policy == inventory.POLICY and type(frame) is bytes
         and store_policy == inventory_store.COLLECTION_STORE_POLICY
         and collection_policy == inventory.COLLECTION_POLICY
         and collection_grant is None and missing_row_policy is None
         and reselection_policy == LOCAL_SAVED_ROW_ON_RESELECTION
         and delivery_policy == LOCAL_WORLD_READY_ONCE and restart_policy == restart.POLICY,
         'ITEM_TRANSFER_STRICT_CUSTODY_READONLY_RESTORE_REQUIRED')
    item = inventory.validate_frame(frame)
    fields = dict(item.raw_fields)
    need(fields[1] > 0 and fields[2] == 1 and fields[4] > 0,
         'ITEM_TRANSFER_TEMPLATE1_CANONICAL_CONFIG_REQUIRED')
    return True


def configuration(config):
    from tools.local_original_session.feature_config import Features
    need(type(config) is Features, 'ITEM_TRANSFER_EXACT_FEATURES_REQUIRED')
    validate_mode(policy=config.item_transfer_policy,
        custody_policy=config.inventory_custody_policy,
        inventory_policy=config.inventory_policy, frame=config.inventory_frame,
        store_policy=config.inventory_store_policy,
        collection_policy=config.inventory_collection_policy,
        collection_grant=config.inventory_collection_grant,
        reselection_policy=config.inventory_reselection_policy,
        delivery_policy=config.inventory_delivery_policy,
        missing_row_policy=config.inventory_missing_row_policy,
        restart_policy=config.restart_policy)
    need(not config.spawns and config.attack_policy is None
         and config.inventory_update_policy is None
         and config.item_equipment_first_enable is False,
         'ITEM_TRANSFER_NO_OTHER_MUTATION_POLICY_REQUIRED')
    return True


def require_ground_source():
    from tools.local_original_session import item_transfer_protocol
    # Actual original codec/schema/source check, never a live ground-ready bool.
    need(item_transfer_protocol.source_ready() is True,
         'ITEM_TRANSFER_STATIC_PROTOCOL_SOURCE_REQUIRED')
    try:
        from tools.local_original_session import item_ground
    except ImportError as error:
        if error.name not in ('tools.local_original_session.item_ground', 'tools.local_original_session', 'item_ground'):
            raise
        raise GroundSourceNotReady(GROUND_INPUT_ERROR) from None
    checker = getattr(item_ground, 'require_ground_source', None)
    if checker is None:
        raise GroundSourceNotReady(GROUND_INPUT_ERROR)
    return checker()


from dataclasses import dataclass, replace
from types import MethodType
import asyncio


@dataclass(frozen=True, slots=True)
class CustodyMembership:
    generation: object
    snapshot: object
    frame: bytes
    phase: str


@dataclass(frozen=True, slots=True)
class TransferContext:
    session: object
    broker: object
    writer: object
    row: object
    generation: object
    inventory_service: object
    item_use_session: object
    store: object
    selection_binding: tuple
    initial_frame: bytes
    current_frame: bytes
    delivery: tuple
    authority: tuple
    snapshot: object
    equipment: object
    position: object
    membership: CustodyMembership


@dataclass(frozen=True, slots=True, init=False)
class BoundTransferOperation:
    session: object
    context: TransferContext
    kind: str
    ground: object
    replacement: object
    wires: tuple

    def __new__(cls):
        # No caller-selected UID/epoch/provider/observed=True issuance API.
        require_ground_source()
        raise ValueError('ITEM_TRANSFER_OPERATION_ISSUANCE_PRIVATE')


def _original(owner, name, function):
    method = getattr(owner, name, None)
    need(type(method) is MethodType and method.__self__ is owner and
         method.__func__ is function, 'ITEM_TRANSFER_ORIGINAL_METHOD_REQUIRED')
    return method


def validate_custody_operation(operation, store, expected_snapshot):
    from tools.local_original_session.inventory_store import InventoryStore
    from tools.local_original_session.item_custody import CustodySnapshot
    need(type(operation) is BoundTransferOperation and type(store) is InventoryStore and
         type(expected_snapshot) is CustodySnapshot,
         'ITEM_TRANSFER_EXACT_STORE_OPERATION_SNAPSHOT_REQUIRED')
    require_ground_source()
    session = operation.session
    need(type(session) is ItemTransferSession and session.pending is operation and
         operation.context.store is store and operation.context.snapshot is expected_snapshot,
         'ITEM_TRANSFER_CURRENT_ISSUED_OPERATION_REQUIRED')
    session.validate_operation_locked(operation, before_commit=True)
    return operation.replacement


def restore_owned_custody(store, character_uid):
    """Actual Store read-only projection; no generation/live permission."""
    from tools.local_original_session.inventory_store import InventoryStore
    from tools.local_original_session import item_custody
    need(type(store) is InventoryStore and store.custody_policy == item_custody.CUSTODY_POLICY,
         'ITEM_TRANSFER_ACTUAL_CUSTODY_STORE_REQUIRED')
    snapshot = store.custody_snapshot(character_uid)
    frame = store.restore(character_uid)
    need(type(frame) is bytes and frame == item_custody.owned_frame(snapshot),
         'ITEM_TRANSFER_CURRENT_OWNED_PROJECTION_REQUIRED')
    return snapshot, frame


def require_pretransfer_snapshot(snapshot):
    from tools.local_original_session import item_custody
    item_custody._validate(snapshot)
    need(snapshot.phase == 'READY' and snapshot.owner == 'PLAYER',
         'ITEM_TRANSFER_USE_OPEN_AFTER_TRANSFER_REFUSED')


def validate_membership_value(expected, expected_frame, actual, current_frame):
    """Storage/current-literal consumer only; generation is checked separately."""
    from tools.local_original_session import item_custody
    item_custody._validate(expected)
    item_custody._validate(actual)
    need(expected == actual and type(expected_frame) is bytes and
         current_frame is expected_frame and current_frame == item_custody.owned_frame(actual),
         'ITEM_TRANSFER_CURRENT_MEMBERSHIP_REVISION_REQUIRED')


class ItemTransferSession:
    """One real selection, one whole-B roundtrip; no Native/helper receipt gate.

    The immutable initial ADD/binding is never repurposed. Current membership
    is separately bound to the actual single-file custody revision and object
    identity, so an AB return cannot resurrect pre-drop intents or pending work.
    """
    def __init__(self, broker, generation):
        from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
        from tools.local_original_session.item_custody import CUSTODY_POLICY
        need(type(broker) is PersistentBroker and type(generation) is _InventoryGeneration and
             broker._inventory_generation is generation and generation.broker is broker and
             broker.item_transfer_policy == POLICY and
             broker.inventory_custody_policy == CUSTODY_POLICY,
             'ITEM_TRANSFER_ACTUAL_BROKER_GENERATION_REQUIRED')
        self.broker, self.generation = broker, generation
        self.membership = self.pending = None
        self.closed = False
        self.phase = 'READY'
        self._send_index = 0
        self._wire_phase = None
        self._sent_before = None
        self._drain_started = None
        self._committed = None

    def _registered(self, writer):
        from tools.local_original_session.broker import PersistentBroker
        from tools.local_original_session.item_custody import CUSTODY_POLICY
        b, g = self.broker, self.generation
        need(not self.closed and b.item_transfer_policy == b._item_transfer_policy_bound == POLICY and
             b.inventory_custody_policy == b._inventory_custody_policy_bound == CUSTODY_POLICY and
             b.inventory_selection_current.__func__ is PersistentBroker.inventory_selection_current and
             b.inventory_selection_current(writer) is g and g.phase == 'ACTIVE' and
             g.transfer_session is self and g.writer is writer,
             'ITEM_TRANSFER_CURRENT_REGISTERED_GENERATION_REQUIRED')
        return b, g

    def helper_open_allowed(self, writer):
        # Additional refusal only; original helper owner/lifetime/source guards
        # still run. No row lock, memory observation or helper receipt is minted.
        b, g = self._registered(writer)
        need(self.phase == 'READY' and self.pending is None and
             (self.membership is None or self.membership.snapshot.phase == 'READY'),
             'ITEM_TRANSFER_USE_OPEN_AFTER_TRANSFER_REFUSED')
        snapshot, _ = restore_owned_custody(b._inventory_store,g.mover.snapshot().uid)
        require_pretransfer_snapshot(snapshot)

    def validate_use_locked(self, writer, *, read_only_initialization=False):
        b, g = self._registered(writer)
        need(g.lock.locked(), 'ITEM_TRANSFER_CURRENT_ROW_LOCK_REQUIRED')
        if read_only_initialization:
            # Initial equipment restoration is a read-only projection. It is
            # not a received item-use intent or native-helper admission.
            need(self.pending is None and self.phase in ('READY', 'RESTORED_CUSTODY'),
                 'ITEM_TRANSFER_INITIAL_SYNC_PENDING_REFUSED')
            return
        self.helper_open_allowed(writer)
        need(b._inventory_current_frame is b._inventory_frame,
             'ITEM_TRANSFER_USE_INITIAL_MEMBERSHIP_REQUIRED')

    def context_locked(self, writer):
        from tools.local_original_session import inventory, inventory_store, equipment_store
        from tools.local_original_session.item_custody import CUSTODY_POLICY, owned_frame
        b, g = self._registered(writer)
        service, store, use = g.service, g.store, g.item_use_session
        need(type(service) is inventory.InventoryService and service is b._inventory_service and
             service.broker is b and type(store) is inventory_store.InventoryStore and
             store is b._inventory_store and store is service._persistence_store() and
             store.custody_policy == CUSTODY_POLICY and g.lock is g.row['operation_lock'] and
             g.lock.locked(), 'ITEM_TRANSFER_CURRENT_SERVICE_STORE_LOCK_REQUIRED')
        _original(service, '_current', inventory.InventoryService._current)
        authority = service._current(writer, g.row)
        restart = g.row.get('_restart')
        need(restart is None or type(restart) is dict and restart.get('phase') == 'DRAINED' and
             restart.get('selection_cleared') is True, 'ITEM_TRANSFER_NO_PENDING_RESTART_REQUIRED')
        effect = getattr(b,'_item_equipment_effect',None)
        if effect is not None:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            need(type(effect) is ItemEquipmentEffect and effect.broker is b and
                 (effect._operation is None or effect._operation.get('phase') == 'DRAINED'),
                 'ITEM_TRANSFER_NO_PENDING_EQUIPMENT_REQUIRED')
        b._inventory_selection_frame_current(writer, g.row, g.frame)
        need(type(g.selection_binding) is tuple and len(g.selection_binding) == 11 and
             g.frame is g.operation_frame and type(g.frame) is bytes and
             type(g.current_frame) is bytes and g.delivery_authority is not None and
             g.attempted is True and g.write_attempted is True and
             service._claimed is True and not service._inflight and not service._closed and
             b._inventory_update_operation is None,
             'ITEM_TRANSFER_INITIAL_DELIVERY_REQUIRED')
        delivered = g.delivery_authority
        need(type(delivered) is tuple and len(delivered) == 3 and
             type(delivered[1]) is tuple and len(delivered[1]) == 24 and
             len(authority[1]) == 24 and delivered[2] == authority[2] and
             all(a is z for n, (a, z) in enumerate(zip(delivered[1], authority[1])) if n != 14) and
             (delivered[0].uid, delivered[0].name, delivered[0].map_id) ==
             (authority[0].uid, authority[0].name, authority[0].map_id),
             'ITEM_TRANSFER_SAME_INITIAL_DELIVERED_AUTHORITY_REQUIRED')
        snapshot, restored = restore_owned_custody(store,authority[0].uid)
        frame = g.current_frame
        need(restored == frame, 'ITEM_TRANSFER_CURRENT_OWNED_PROJECTION_REQUIRED')
        if self.membership is None:
            need(frame is g.frame, 'ITEM_TRANSFER_INITIAL_LITERAL_REQUIRED')
            self.membership = CustodyMembership(g, snapshot, frame, 'READY')
            if snapshot.phase != 'READY':self.phase = 'RESTORED_CUSTODY'
        member = self.membership
        need(type(member) is CustodyMembership and member.generation is g and
             member.phase in ('READY', 'COMMITTING', 'DRAINED'),
             'ITEM_TRANSFER_CURRENT_MEMBERSHIP_REVISION_REQUIRED')
        validate_membership_value(member.snapshot,member.frame,snapshot,frame)
        equipment = equipment_store.EquipmentStore(store, policy=equipment_store.POLICY,
            collection_policy=equipment_store.COLLECTION_POLICY).restore(authority[0].uid, frame)
        need(type(equipment) is equipment_store.EquipmentState,
             'ITEM_TRANSFER_ACTUAL_EQUIPMENT_REQUIRED')
        return TransferContext(self,b,writer,g.row,g,service,use,store,g.selection_binding,
            g.frame,frame,delivered,authority,member.snapshot,equipment,authority[0],member)

    @staticmethod
    def _same(before, after):
        from tools.local_original_session.inventory import InventoryService
        need(type(before) is TransferContext and type(after) is TransferContext and
             all(getattr(before,n) is getattr(after,n) for n in (
                 'session','broker','writer','row','generation','inventory_service','item_use_session',
                 'store','selection_binding','initial_frame','current_frame','delivery','position','membership')) and
             before.snapshot is after.snapshot and before.equipment == after.equipment,
             'ITEM_TRANSFER_CONTEXT_CHANGED')
        InventoryService._same(before.authority,after.authority)

    def validate_operation_locked(self, operation, *, before_commit=False):
        from tools.local_original_session import item_ground
        need(type(operation) is BoundTransferOperation and self.pending is operation and
             operation.session is self and operation.context.session is self,
             'ITEM_TRANSFER_EXACT_PENDING_OPERATION_REQUIRED')
        current = self.context_locked(operation.context.writer)
        if before_commit:
            self._same(operation.context,current)
            need(self.phase == 'COMMITTING' and self._committed is None,
                 'ITEM_TRANSFER_SINGLE_DURABLE_COMMIT_REQUIRED')
        else:
            need(self._committed is not None and current.membership is self.membership and
                 current.snapshot is self._committed and current.generation is operation.context.generation and
                 current.initial_frame is operation.context.initial_frame and
                 current.selection_binding is operation.context.selection_binding and
                 current.equipment == operation.context.equipment,
                 'ITEM_TRANSFER_CURRENT_COMMITTED_MEMBERSHIP_REQUIRED')
        registry = self.broker._item_ground_registry
        need(type(registry) is item_ground.GroundRegistry,
             'ITEM_TRANSFER_REAL_GROUND_REGISTRY_REQUIRED')
        _original(registry,'validate_locked',item_ground.GroundRegistry.validate_locked)(self,current,operation.ground)
        return current

    async def handle(self, writer, payload, *, kind):
        from tools.local_original_session import item_transfer_protocol as protocol, item_ground, item_custody
        require_ground_source()
        need(kind in ('DROP','PICKUP') and type(kind) is str and self.pending is None,
             'ITEM_TRANSFER_NO_PENDING_REPLAY_REQUIRED')
        request = (protocol.parse_drop_payload(payload) if kind == 'DROP' else protocol.parse_get_payload(payload))
        before = self.context_locked(writer)
        need((kind == 'DROP' and self.phase == 'READY' and before.snapshot.phase == 'READY') or
             (kind == 'PICKUP' and self.phase == 'DROPPED' and before.snapshot.phase == 'DROPPED'),
             'ITEM_TRANSFER_ORDER_OR_RECOVERY_REQUIRED')
        a,b = item_custody._members(before.snapshot.frame_ab)
        quantity = dict(b.raw_fields)[4]
        need(0 < quantity <= protocol.I32_MAX and request.quantity == quantity and
             request.x == before.position.word0 and request.y == before.position.word1,
             'ITEM_TRANSFER_WHOLE_CURRENT_QUANTITY_POSITION_REQUIRED')
        need(0 < request.uid < 1 << 32 and request.uid == b.identifier,
             'ITEM_TRANSFER_EXPLICIT_SAME_B_GROUND_UID_REQUIRED')
        if kind == 'DROP':
            need(before.equipment.weapon_uid != b.identifier,
                 'ITEM_TRANSFER_CURRENT_OWNED_UNEQUIPPED_B_REQUIRED')
        need(before.row['policy_row'].drain_started_ns is None and
             before.row['policy_row'].pending_opcode is None and before.row['policy_row'].pending_size == 0,
             'ITEM_TRANSFER_NO_OLD_PENDING_DELIVERY_REQUIRED')
        use = before.item_use_session
        from tools.local_original_session.item_use_session import ItemUseSession
        need(use is None or type(use) is ItemUseSession and not use.closed and
             use._inflight_writer is None and not use._lock.locked(),
             'ITEM_TRANSFER_NO_OLD_PENDING_USE_REQUIRED')
        await self.broker._checkpoint(writer,before.row)
        after = self.context_locked(writer)
        self._same(before,after)
        self.broker.source_guard()
        registry = self.broker._item_ground_registry
        need(type(registry) is item_ground.GroundRegistry, 'ITEM_TRANSFER_REAL_GROUND_REGISTRY_REQUIRED')
        ground = None
        self.phase = 'PREPARING'
        try:
            method = 'prepare_drop_locked' if kind == 'DROP' else 'prepare_pickup_locked'
            ground = _original(registry,method,getattr(item_ground.GroundRegistry,method))(self,after,request,after.snapshot)
            need(type(ground) is item_ground.GroundOperation, 'ITEM_TRANSFER_ORIGINAL_GROUND_OPERATION_REQUIRED')
            ground_wires = _original(registry,'ground_wires',item_ground.GroundRegistry.ground_wires)(ground)
            need(type(ground_wires) is tuple and len(ground_wires) == 1,
                 'ITEM_TRANSFER_EXACT_ONE_GROUND_WIRE_REQUIRED')
            if kind == 'DROP':
                replacement = item_custody._drop_storage_plan(after.snapshot,
                    item_custody.GroundLocation(after.position.map_id,request.x,request.y),after.equipment)
                wires = (protocol.build_remove(uid=b.identifier),) + ground_wires
            else:
                replacement = item_custody._pickup_storage_plan(after.snapshot,after.equipment)
                wires = ground_wires + (inventory_return_b(after.snapshot),)
            operation = object.__new__(BoundTransferOperation)
            for name,value in dict(session=self,context=after,kind=kind,ground=ground,
                                   replacement=replacement,wires=wires).items():object.__setattr__(operation,name,value)
            self.pending = operation
            self.phase = 'COMMITTING'
            self._send_index,self._wire_phase,self._committed = 0,None,None
            # Invalidate the actual previous request; do not reset accepted_count or
            # initialize an ordinal/receipt. New intents are rejected after transfer.
            if use is not None:use._clear('ITEM_TRANSFER_MEMBERSHIP_CHANGED')
            self._committed = after.store.commit_custody(after.snapshot,operation)
            new_frame = item_custody.owned_frame(self._committed)
            self.broker._inventory_current_frame = new_frame
            self.membership = CustodyMembership(self.generation,self._committed,new_frame,'COMMITTING')
            _original(registry,'persisted',item_ground.GroundRegistry.persisted)(ground,self._committed)
            await self.broker._send(writer,after.row,wires,game=True,
                operation_lock=after.row['operation_lock'],item_transfer_operation=operation)
            need(self._send_index == len(wires) and self._wire_phase is None,
                 'ITEM_TRANSFER_ALL_EXACT_WIRES_DRAINED_REQUIRED')
            _original(registry,'complete',item_ground.GroundRegistry.complete)(ground)
            self.membership = replace(self.membership,phase='DRAINED')
            self.phase = 'DROPPED' if kind == 'DROP' else 'RETURNED'
            self.pending = None
            return ()
        except BaseException:
            self.closed = True
            self.phase = 'TERMINAL'
            if self.membership is not None:self.membership = replace(self.membership,phase='TERMINAL')
            after.row['failed'] = True
            self.broker._fail('ITEM_TRANSFER_OUTCOME_UNKNOWN')
            if ground is not None:
                _original(registry,'fail',item_ground.GroundRegistry.fail)(ground)
            raise

    def release(self, writer):
        """Retire only this actual generation/epoch; never replay/roll back IO."""
        if writer is not self.generation.writer:
            return
        self.closed = True
        self.phase = 'TERMINAL'
        if self.membership is not None:self.membership = replace(self.membership,phase='TERMINAL')
        from tools.local_original_session import item_ground
        registry = self.broker._item_ground_registry
        need(type(registry) is item_ground.GroundRegistry, 'ITEM_TRANSFER_REAL_GROUND_REGISTRY_REQUIRED')
        _original(registry,'release_generation',item_ground.GroundRegistry.release_generation)(self.generation)

    def validate_wire(self, writer, row, wire, operation):
        current = self.validate_operation_locked(operation)
        need(writer is operation.context.writer and row is operation.context.row and
             self._send_index < len(operation.wires) and wire is operation.wires[self._send_index] and
             self._wire_phase in (None,'WRITE_ATTEMPTED'),
             'ITEM_TRANSFER_EXACT_ORDERED_WIRE_REQUIRED')
        return current

    def validate_write_binding(self, writer, row, wire, operation):
        self._registered(writer)
        # No source/file IO or await after begin_write. The exact current
        # operation was fully validated before the fresh exact-owner query.
        need(type(operation) is BoundTransferOperation and self.pending is operation and
             operation.session is self and self.broker._inventory_generation is self.generation and
             self.generation.transfer_session is self and self.generation.phase == 'ACTIVE' and
             self.generation.mover.snapshot() is operation.context.position and
             self.membership.snapshot is self._committed and
             self.membership.frame is self.broker._inventory_current_frame and
             writer is operation.context.writer and row is operation.context.row and
             row['operation_lock'] is self.generation.lock and self.generation.lock.locked() and
             self._send_index < len(operation.wires) and wire is operation.wires[self._send_index] and
             not self.closed and self.phase == 'COMMITTING', 'ITEM_TRANSFER_WRITE_BINDING_CHANGED')
    def attempt(self, writer, row, wire, operation):
        from tools.local_original_session import item_ground
        self.validate_write_binding(writer,row,wire,operation)
        need(self._wire_phase is None and row['policy_row'].pending_opcode == int.from_bytes(wire[2:4],'little') and
             row['policy_row'].pending_size == len(wire) and row['policy_row'].drain_started_ns is not None,
             'ITEM_TRANSFER_SINGLE_RESERVED_WRITE_REQUIRED')
        self._wire_phase = 'WRITE_ATTEMPTED'
        self._sent_before = row['policy_row'].sent
        self._drain_started = row['policy_row'].drain_started_ns
        registry=self.broker._item_ground_registry
        _original(registry,'attempt',item_ground.GroundRegistry.attempt)(operation.ground,wire)

    def drained(self, writer, row, wire, operation, queued):
        from tools.local_original_session import item_ground
        self.validate_write_binding(writer,row,wire,operation)
        admitted=row['policy_row']
        need(self._wire_phase == 'WRITE_ATTEMPTED' and queued == 0 and
             admitted.pending_opcode is None and admitted.pending_size == 0 and admitted.drain_started_ns is None and
             admitted.sent == self._sent_before+1, 'ITEM_TRANSFER_EXACT_DRAIN_REQUIRED')
        registry=self.broker._item_ground_registry
        _original(registry,'drained',item_ground.GroundRegistry.drained)(operation.ground,wire)
        self._send_index += 1
        self._wire_phase = None


def inventory_return_b(snapshot):
    from tools.local_original_session import item_custody, inventory
    _,b=item_custody._members(snapshot.frame_ab)
    return inventory.build_collection_add((b,),policy=inventory.COLLECTION_POLICY)


def factory_preflight(config, *, control_mode, swap_saved_b_tail=False, zero_use_reselect=False, product=None):
    need(product == PROFILE and control_mode == 'manual' and swap_saved_b_tail is False and zero_use_reselect is False,
         'ITEM_TRANSFER_EXPLICIT_SEPARATE_MODE_REQUIRED')
    configuration(config)
    require_ground_source()
