"""Explicit local whole-B ground custody, owned by the real transfer session.

Registrations describe backend publication/drain, not observed client Items.
The original client owns its normal Actor/Item initialization and rendering.
"""
from dataclasses import dataclass
import hashlib
import json
import struct
from types import MappingProxyType, MethodType

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import item_ground_wire as wire

ROOT = wire.ROOT
REQ95 = wire.REQ95
CHOICE = 'work/local_original_session/integration-1/item-equipment-ui-link/LOCAL_GROUND14_PROFILE_CHOICE.json'
PROFILE_PROVENANCE = 'root가 선택한 최초 local ground14 opaque profile'
PARAMETERS = ((6,0),(8,0),(9,b''),(10,b''),(11,0),(12,0),(13,0),
              (14,False),(15,False),(17,False),(18,False),(19,0),
              (20,b''),(21,b''),(22,0),(23,0),(24,0),(27,0),(28,0))
PROFILE = wire.LocalItemProfile(PARAMETERS, action=0, direction=0, nonnegative_state=0)
SOURCE_PINS = MappingProxyType({
    CHOICE: '83dc98ad6519e1832b51242bda95438e09cb8db042731aa8e60e3632a7caba75',
    REQ95+'sprite_producer/findings.md': 'acdbf13cf9ec235536e92a06f50a4aa1837b30e76d248946f00a886f83f592d4',
    REQ95+'sprite_producer/source-evidence.json': '9d4a3bbd0d5e91c39ce169f6fe46074191494de1778aae79767c8c8667c064d2',
    REQ95+'sprite_producer/reproducer.py': '16301fc2c18e1ff507948e0c5640033a575085d28119ee25dbf32c086b514b72',
    REQ95+'sprite_producer/owner_delta/findings.md': 'd3094af323bfb21853fa0bbbd21820c9ca792064dadf584fccba31b653c552a6',
    REQ95+'sprite_producer/owner_delta/source-evidence.json': '9e29dc040be44a316987e5c1b62530eda604eea313165f7ce08801c3b800923d',
    REQ95+'sprite_producer/owner_delta/reproducer.py': '91d7dfdd5c0e17a2eb2de48dfb61bc1f01dfd8d4eba78a1ec3a313e947777750',
    REQ95+'main-sprite-check.json': '13164cf71c2da13f982285a48f6b0b9fba3fed928837bcff6fa4705d91646968',
    'work/local_server_rea_20261016/run98_item_drop_pickup_contract/worker/source-evidence.json': '4159a5fb87749ebc91a79849b68240551cfe9e50bcb0f64b6b20c55890ec65af',
    REQ95+'spawn_recipe/action_delta/findings.md': '0c4e33346c5fa672b1fadc75275c25e33f7dce8a45b1e2c518e78dd368814055',
    REQ95+'spawn_recipe/action_delta/source-evidence.json': 'ed67bde38fce5958117b0112ee435371a13873277162c323a5b3d2153e98f679',
    REQ95+'spawn_recipe/action_delta/reproducer.py': 'a4df0878d4c4cd50a76e89917add58bf35159857e20f3eb9b4b1f0d2c2f8f309',
    REQ95+'main-action-check.json': 'a4154d5b9b95e66b0008a68cec7f71bace5cc94e51d069cb190d924c77f05ca4',
})


class GroundError(ValueError):
    """Fixed codes; no raw bytes, addresses or private item data."""


class GroundSourceNotReady(GroundError):
    pass


def need(condition, reason):
    if not condition:
        raise GroundError(reason)


def _read_sources():
    docs = {}
    for name, digest in SOURCE_PINS.items():
        try:
            with (ROOT/name).open('rb') as stream:
                raw = stream.read(1_048_577)
        except OSError:
            raise GroundSourceNotReady('GROUND_STATIC_SOURCE_UNAVAILABLE') from None
        need(0 < len(raw) <= 1_048_576 and hashlib.sha256(raw).hexdigest() == digest,
             'GROUND_STATIC_SOURCE_CHANGED')
        if name.endswith('.json'):
            try:
                docs[name] = json.loads(raw)
            except (ValueError, UnicodeError):
                raise GroundError('GROUND_STATIC_SOURCE_JSON_INVALID') from None
    return docs


def _static_contract(docs):
    try:
        choice = docs[CHOICE]
        need(choice['schema'] == 'root-local-ground14-profile-choice-v1', 'GROUND_LOCAL_CHOICE_SCHEMA')
        values = []
        for row in choice['selected_required_parameters']:
            value = row['value']
            expected_kind = {'i32':'int32','u64':'uint64','bool':'bool','bytes':'bytes'}[wire.KINDS[row['field']]]
            need(row['kind'] == expected_kind, 'GROUND_LOCAL_CHOICE_KIND')
            if row['kind'] == 'bytes':
                need(type(value) is list and value == [], 'GROUND_LOCAL_CHOICE_BYTES')
                value = b''
            values.append((row['field'], value))
        need(tuple(values) == PARAMETERS and
             all(type(value) is type(expected) for (_,value),(_,expected) in zip(values,PARAMETERS)) and
             choice['selected_other_fields'] == {'3':14,'4':0,'5':0,'16':False,'39':0} and
             choice['omitted_optional_fields'] == [44,69], 'GROUND_LOCAL_CHOICE_CHANGED')
        sprite = docs[REQ95+'sprite_producer/source-evidence.json']
        owner = docs[REQ95+'sprite_producer/owner_delta/source-evidence.json']
        check = docs[REQ95+'main-sprite-check.json']
        need(sprite['schema'] == 'req95-sprite14-original-producer-v1' and
             sprite['CONTROL_sha256'] == wire.CONTROL_SHA and
             sprite['contract']['sprite14']['record0'] == 14 and
             sprite['contract']['sprite14']['recordC'] == 0 and
             sprite['contract']['sprite14']['record5C'] == 9 and
             sprite['contract']['sprite14']['normal_resource'] == 14 and
             owner['schema'] == 'req95-sprite-loader-owner-delta-v1' and
             owner['conclusion']['status'] == 'STATIC_SAME_MAP_OWNER_BINDING_CLOSED' and
             check['schema'] == 'req95-main-sprite-and-owner-check/v1' and check['passed'] is True and
             check['worker']['sha256'] == SOURCE_PINS[REQ95+'sprite_producer/source-evidence.json'] and
             check['owner_delta']['sha256'] == SOURCE_PINS[REQ95+'sprite_producer/owner_delta/source-evidence.json'],
             'GROUND_SPRITE_OWNER_SOURCE_CHANGED')
        retire = docs['work/local_server_rea_20261016/run98_item_drop_pickup_contract/worker/source-evidence.json']
        need(retire['schema'] == 'req92-drop-pickup-source-v1' and
             retire['CONTROL_sha256'] == wire.CONTROL_SHA and
             retire['contracts']['GROUND_RETIRE']['opcode'] == '0x4e40' and
             retire['contracts']['GROUND_RETIRE']['field1'] == 'required uint64 wire0 ActorUID' and
             retire['contracts']['GROUND_RETIRE']['HP_Death_gate'] is False,
             'GROUND_NORMAL_RETIRE_SOURCE_CHANGED')
    except (KeyError,TypeError,IndexError):
        raise GroundError('GROUND_STATIC_CONTRACT_CHANGED') from None


def _action_contract(docs):
    try:
        action = docs[REQ95+'spawn_recipe/action_delta/source-evidence.json']
        check = docs[REQ95+'main-action-check.json']
        need(action['schema'] == 'REQ95-local-Item-action-delta-v1' and
             action['CONTROL_sha256'] == wire.CONTROL_SHA and
             check['schema'] == 'req95-main-action-saved-check/v1' and check['passed'] is True and
             check['worker']['sha256'] == SOURCE_PINS[REQ95+'spawn_recipe/action_delta/source-evidence.json'] and
             [(r['id'],r['rva'],r['end']) for r in action['selected_saved_source']] ==
             [('A1','0x96e66','0x96e75'),('A2','0x96faf','0x96fb8'),('A3','0x96fbd','0x96fc0'),
              ('A4','0x97032','0x9705d'),('A5','0x97093','0x970a1'),('A6','0x970c4','0x970e3'),('A7','0x97251','0x97264')],
             'GROUND_ACTION_SOURCE_IDENTITY_CHANGED')
        need(action['contract']['condition'] ==
             'Normal appearance-update completed for this same Action and same effective record, record10==record18 and resulting Action48!=0. Same-appearance fast return does not recompute flag; raw equality to appearance14 alone is insufficient.' and
             action['contract']['ctor_limit'] ==
             'No new ctor state claim. Accepted ctor identity prefix does not establish initial Action3C/48; contract is limited to normal changed-appearance update/current state.',
             'GROUND_ACTION_SOURCE_CONDITION_CHANGED')
    except (KeyError,TypeError,IndexError):
        raise GroundError('GROUND_ACTION_CONTRACT_CHANGED') from None


@dataclass(frozen=True, slots=True, init=False, repr=False)
class GroundSource:
    profile: str
    pins: tuple
    runtime_scope: str

    def __new__(cls):
        raise GroundError('GROUND_SOURCE_ISSUANCE_PRIVATE')


_SOURCE = object.__new__(GroundSource)
object.__setattr__(_SOURCE,'profile',PROFILE_PROVENANCE)
object.__setattr__(_SOURCE,'pins',tuple(SOURCE_PINS.items()))
object.__setattr__(_SOURCE,'runtime_scope',
    'STATIC_LOCAL_RECIPE_ONLY_CURRENT_RECORD_ACTION48_RESOURCE_AND_RENDER_UNOBSERVED')


def require_ground_source():
    """Validate fixed static recipe/policy; never report current flag/render.

    Empty record action-range -> normal updated Action48/static resource is
    conditional source behavior, not an assertion of runtime flag or action0.
    The original client performs its own initialization and runtime branches.
    """
    wire.source_ready()
    docs = _read_sources()
    _static_contract(docs)
    _action_contract(docs)
    return _SOURCE


@dataclass(frozen=True, slots=True, init=False, repr=False)
class GroundOperation:
    registry: object
    source: GroundSource
    context: object
    kind: str
    epoch: object
    uid: int
    quantity: int
    location: tuple
    wire: bytes

    def __new__(cls):
        raise GroundError('GROUND_OPERATION_ISSUANCE_PRIVATE')


def _original(owner, name, function):
    method = getattr(owner,name,None)
    need(type(method) is MethodType and method.__self__ is owner and method.__func__ is function,
         'GROUND_ORIGINAL_METHOD_REQUIRED')
    return method


class GroundRegistry:
    """One actual broker, one whole-B roundtrip per current selection.

    Collision coverage is the backend's known published Actors/own registry,
    not a statement that the entire client heap has no other Actors.
    """
    def __init__(self, broker):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker and getattr(broker,'_item_ground_registry',None) is None,
             'GROUND_ACTUAL_UNBOUND_BROKER_REQUIRED')
        self.broker = broker
        self._source_guard = broker.source_guard
        self._pending = self._registration = self._generation = None
        self._epoch = None
        self._terminal = False
        self._snapshot = self._member = self._frame = None
        self._index, self._attempted = 0, False
        self._ground_attempted = self._ground_drained = False

    def _context(self, session, context):
        from tools.local_original_session.item_transfer_session import ItemTransferSession, TransferContext
        need(type(session) is ItemTransferSession and type(context) is TransferContext and
             context.session is session and context.broker is self.broker and session.broker is self.broker and
             self.broker._item_ground_registry is self and not self.broker.realm._npc_spawns and not self._terminal,
             'GROUND_EXACT_REGISTERED_SESSION_CONTEXT_REQUIRED')
        need(self.broker.source_guard is self._source_guard, 'GROUND_RETAINED_SOURCE_GUARD_CHANGED')
        self._source_guard()
        current = _original(session,'context_locked',ItemTransferSession.context_locked)(context.writer)
        ItemTransferSession._same(context,current)
        return current

    def _collision(self, context, uid):
        realm = self.broker.realm
        need(not realm._npc_spawns and uid != context.position.uid and uid != realm.profile_uid,
             'GROUND_KNOWN_PUBLISHED_ACTOR_COLLISION')
        need(self._registration is None, 'GROUND_PREVIOUS_REGISTRATION_PRESENT')

    def _prepare(self, session, context, request, snapshot, kind):
        from tools.local_original_session import item_custody, item_transfer_protocol as protocol
        source = require_ground_source()
        self._context(session,context)
        need(self._pending is None and session.pending is None and session.phase == 'PREPARING' and
             snapshot is context.snapshot, 'GROUND_CURRENT_PREPARATION_REQUIRED')
        _, b = item_custody._validate(snapshot)
        quantity = dict(b.raw_fields)[4]
        need(type(request) is (protocol.DropRequest if kind == 'DROP' else protocol.GetRequest) and
             0 < request.uid < 1 << 32 and request.uid == b.identifier and
             0 < request.quantity == quantity <= protocol.I32_MAX and
             (request.x,request.y) == (context.position.word0,context.position.word1) and
             context.equipment.weapon_uid != b.identifier,
             'GROUND_ACTUAL_WHOLE_UNEQUIPPED_B_POSITION_REQUIRED')
        location = (context.position.map_id,request.x,request.y)
        if kind == 'DROP':
            need(snapshot.phase == 'READY' and self._generation is None, 'GROUND_FRESH_DROP_ONLY')
            self._collision(context,request.uid)
            epoch = object()
            candidate = wire.local_candidate(PROFILE,actor_uid=request.uid,
                packed_position=context.position.packed,quantity=quantity)
            packet = wire.build_candidate(candidate)
        else:
            previous = self._registration
            need(type(previous) is GroundOperation and self._generation is context.generation and
                 previous.epoch is self._epoch and previous.kind == 'DROP' and
                 previous.uid == request.uid and previous.quantity == quantity and previous.location == location and
                 previous.context.selection_binding is context.selection_binding and
                 previous.context.initial_frame is context.initial_frame and
                 previous.context.store is context.store and snapshot is self._snapshot and
                 snapshot.phase == 'DROPPED' and snapshot.frame_ab == previous.context.snapshot.frame_ab,
                 'GROUND_SAME_PUBLISHED_EPOCH_PICKUP_REQUIRED')
            epoch = previous.epoch
            body = pb.encode_varint(8)+pb.encode_varint(request.uid)
            packet = struct.pack('<HH',len(body)+6,0x4e40)+body+b'\0\0'
        op = object.__new__(GroundOperation)
        for name,value in dict(registry=self,source=source,context=context,kind=kind,epoch=epoch,
             uid=request.uid,quantity=quantity,location=location,wire=packet).items():
            object.__setattr__(op,name,value)
        self._pending, self._generation, self._epoch = op,context.generation,epoch
        # Only the pre-commit context is authoritative until persisted().
        self._snapshot, self._member, self._frame = context.snapshot, context.membership, context.current_frame
        self._index,self._attempted = 0,False
        self._ground_attempted = self._ground_drained = False
        return op

    def prepare_drop_locked(self, session, context, request, snapshot):
        return self._prepare(session,context,request,snapshot,'DROP')

    def prepare_pickup_locked(self, session, context, request, snapshot):
        return self._prepare(session,context,request,snapshot,'PICKUP')

    def _issued(self, op):
        need(type(op) is GroundOperation and self._pending is op and op.registry is self and
             op.source is _SOURCE and op.epoch is self._epoch and
             op.context.generation is self._generation and not self._terminal,
             'GROUND_ORIGINAL_PENDING_EPOCH_REQUIRED')
        return op.context.session

    def ground_wires(self, op):
        self._issued(op)
        return (op.wire,)

    @staticmethod
    def _bound(session, op):
        from tools.local_original_session.item_transfer_session import BoundTransferOperation
        bound = session.pending
        need(type(bound) is BoundTransferOperation and bound.session is session and
             bound.ground is op and bound.context is op.context and bound.kind == op.kind,
             'GROUND_ORIGINAL_TRANSFER_OPERATION_REQUIRED')
        return bound

    def validate_locked(self, session, context, op):
        from tools.local_original_session.item_transfer_session import ItemTransferSession
        need(self._issued(op) is session, 'GROUND_SAME_SESSION_REQUIRED')
        require_ground_source()
        self._context(session,context)
        before = op.context
        if self._snapshot is before.snapshot:
            ItemTransferSession._same(before,context)
        else:
            need(all(getattr(before,n) is getattr(context,n) for n in (
                 'session','broker','writer','row','generation','inventory_service','item_use_session',
                 'store','selection_binding','initial_frame','delivery','position')) and
                 before.equipment == context.equipment and context.snapshot is self._snapshot and
                 context.membership is self._member and context.current_frame is self._frame,
                 'GROUND_COMMITTED_CONTEXT_CONTINUITY_REQUIRED')
            from tools.local_original_session.inventory import InventoryService
            InventoryService._same(before.authority,context.authority)
        self._bound(session,op)

    def persisted(self, op, new_snapshot):
        from tools.local_original_session import item_custody
        session = self._issued(op)
        self._bound(session,op)
        need(self._snapshot is op.context.snapshot and session._committed is new_snapshot and
             session.pending is not None and session.pending.ground is op,
             'GROUND_ACTUAL_SINGLE_STORE_COMMIT_REQUIRED')
        current = session.context_locked(op.context.writer)
        need(current.snapshot is new_snapshot and current.membership is session.membership and
             current.current_frame is self.broker._inventory_current_frame and
             current.membership.phase == 'COMMITTING' and
             current.snapshot.phase == ('DROPPED' if op.kind == 'DROP' else 'RETURNED'),
             'GROUND_ACTUAL_COMMITTED_MEMBERSHIP_REQUIRED')
        item_custody._validate(new_snapshot)
        old = op.context.snapshot
        need(new_snapshot.revision == old.revision+1 and new_snapshot.frame_ab == old.frame_ab and
             new_snapshot.character_uid == old.character_uid and new_snapshot.profile_path == old.profile_path and
             new_snapshot.equipment_guard == item_custody._equipment_guard(op.context.equipment),
             'GROUND_COMMITTED_CUSTODY_TRANSITION_REQUIRED')
        if op.kind == 'DROP':
            loc = new_snapshot.location
            need((loc.map_id,loc.x,loc.y) == op.location, 'GROUND_COMMITTED_LOCATION_CHANGED')
        self._snapshot,self._member,self._frame = new_snapshot,current.membership,current.current_frame
        self.validate_locked(session,current,op)

    def _wire(self, op, packet):
        """No file/source reads after the broker's begin_write boundary."""
        session = self._issued(op)
        bound = self._bound(session,op)
        need(bound is not None and bound.ground is op and bound.session is session and
             session.phase == 'COMMITTING' and not session.closed and
             self.broker._inventory_generation is self._generation and self._generation.phase == 'ACTIVE' and
             self._generation.transfer_session is session and self._generation.lock.locked() and
             self._generation.writer is op.context.writer and self._generation.row is op.context.row and
             self._generation.selection_binding is op.context.selection_binding and
             self._generation.frame is op.context.initial_frame and
             self.broker.source_guard is self._source_guard and
             session.membership is self._member and self._member.snapshot is session._committed is self._snapshot and
             self._member.frame is self.broker._inventory_current_frame is self._frame and
             type(bound.wires) is tuple and len(bound.wires) == 2 and self._index < 2 and
             session._send_index == self._index and packet is bound.wires[self._index] and
             bound.wires[1 if op.kind == 'DROP' else 0] is op.wire,
             'GROUND_EXACT_CURRENT_ORDERED_WIRE_REQUIRED')
        return session

    def attempt(self, op, packet):
        session = self._wire(op,packet)
        need(not self._attempted and session._wire_phase == 'WRITE_ATTEMPTED', 'GROUND_SINGLE_WRITE_ATTEMPT_REQUIRED')
        self._attempted = True
        if packet is op.wire:
            need(not self._ground_attempted, 'GROUND_SINGLE_PUBLICATION_ATTEMPT_REQUIRED')
            self._ground_attempted = True

    def drained(self, op, packet):
        session = self._wire(op,packet)
        need(self._attempted and session._wire_phase == 'WRITE_ATTEMPTED', 'GROUND_SINGLE_ATTEMPT_BEFORE_DRAIN_REQUIRED')
        if packet is op.wire:
            need(self._ground_attempted and not self._ground_drained, 'GROUND_SINGLE_PUBLICATION_DRAIN_REQUIRED')
            self._ground_drained = True
        self._index += 1
        self._attempted = False

    def complete(self, op):
        session = self._issued(op)
        need(self._index == 2 and not self._attempted and self._ground_attempted and self._ground_drained and
             session._send_index == 2 and
             session._wire_phase is None, 'GROUND_EXACT_TWO_WIRE_DRAINS_REQUIRED')
        current = session.context_locked(op.context.writer)
        self.validate_locked(session,current,op)
        self._registration = op if op.kind == 'DROP' else None
        self._pending = None
        if op.kind == 'PICKUP':
            self._terminal = True  # One roundtrip; no rearm of this registry epoch.

    def fail(self, op):
        self._issued(op)
        self._terminal = True
        # Preserve uncertain attempted registration and durable custody; no rollback.

    def release_generation(self, generation):
        if generation is not self._generation:
            return
        self._terminal = True
        self._pending = self._registration = None
        # No fabricated retirement packet, client disappearance or Store rewrite.
