"""Source-bound attack wire parts plus current selected-realm target binding.

No route, sender, combat calculation, HP mutation, timer or client prediction is
installed here. The bounded parser and current-coordinate target restriction are
explicit local subsets, not a reconstruction of official server acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import struct
from types import MethodType

from tools.local_original_session import movement, npc, npc_motion, observe

pb = movement.pb
ROOT = Path(__file__).resolve().parents[2]
REQUEST_OPCODE = 0x4e30
ACTION_OPCODE = 0x4e31
TARGET_POLICY = 'EXPLICIT_LOCAL_CURRENT_TARGET_COORDINATES'
SOURCE_PINS = {
    'work/local_server_rea_20261016/run24_normal_attack/findings.md':
        '6efc85b1a8da53dc4fdcf40c7ca88da2e098568b0e95ef8ba3341e11329d7ebc',
    'work/local_server_rea_20261016/run24_normal_attack/source-evidence.json':
        'ee7ae07d4c3928a02c8d91db0fa642f64106901c35ff90c654ff8c01b724a6aa',
}
U64_MAX = (1 << 64) - 1


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _typed_value(value):
    # Keep snapshots primitive and immutable: equality must never call an
    # arbitrary authority object's __eq__, or equate True with handle/PID 1.
    need(type(value) in (int, str, bool, bytes, type(None)),
         'ATTACK_TYPED_AUTHORITY_VALUE_REQUIRED')
    return type(value), value


def _handle_value(value):
    need(type(value) is int and value > 0, 'ATTACK_TYPED_HANDLE_REQUIRED')
    return _typed_value(value)


def _same_binding(left_identities, left_values, right_identities, right_values):
    return (len(left_identities) == len(right_identities)
            and all(a is b for a, b in zip(left_identities, right_identities))
            and left_values == right_values)


def source_ready():
    """Consume the fixed reviewed text evidence; never inspect an executable."""
    for relative, digest in SOURCE_PINS.items():
        need(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest,
             'ATTACK_SOURCE_CHANGED')


def _int32(value):
    need(type(value) is int and -(1 << 31) <= value < (1 << 31), 'ATTACK_INT32_REQUIRED')
    return value


def _signed(value):
    if 0 <= value < (1 << 31):
        return value
    need(0xffffffff80000000 <= value <= U64_MAX, 'ATTACK_INT32_WIRE_REQUIRED')
    return value - (1 << 64)


def _field(number, value):
    return pb.encode_varint(number << 3) + pb.encode_varint(value & U64_MAX)


@dataclass(frozen=True, slots=True)
class AttackRequest:
    target_uid: int
    target_x: int | None = None
    target_y: int | None = None

    def __post_init__(self):
        # The wire schema allows zero and the complete uint64 range. The actor
        # target policy below, separately, refuses zero/sentinel/self targets.
        need(type(self.target_uid) is int and 0 <= self.target_uid <= U64_MAX,
             'ATTACK_TARGET_UINT64_REQUIRED')
        for value in (self.target_x, self.target_y):
            if value is not None:
                _int32(value)


def parse_payload(payload):
    """4E30: required f1 uint64, optional f2/f3 signed int32, no self UID.

    Local parser policy rejects unknown/duplicate/wrong-wire fields, truncation,
    overflow and non-sign-extended negative int32 values. The reused parser's
    bounded overlong varints remain accepted; field order is unrestricted.
    Optional coordinates retain independent presence, including explicit zero.
    """
    source_ready()
    try:
        with pb.parse_message(payload, schema={1: 0, 2: 0, 3: 0},
                limits=pb.WireLimits(max_body=33, max_fields=3, max_field_bytes=33)) as parsed:
            need(len(parsed.occurrences(1)) == 1
                 and all(len(parsed.occurrences(n)) <= 1 for n in (2, 3)),
                 'ATTACK_REQUIRED_UNIQUE_FIELDS')
            values = {item.number: item.value for item in parsed.fields}
            return AttackRequest(values[1],
                _signed(values[2]) if 2 in values else None,
                _signed(values[3]) if 3 in values else None)
    except (ValueError, TypeError, BufferError):
        raise ValueError('MALFORMED_ATTACK_PAYLOAD') from None


@dataclass(frozen=True, slots=True)
class BoundTarget:
    """A short-lived proof tied to its resolver; revalidate after every await.

    This is no queued command or atomic snapshot. The owning broker must hold
    its existing row operation lock while routing and writing. Revalidation at
    the actual write remains necessary after the broker's write checkpoint.
    """
    request: AttackRequest
    attacker: movement.Position
    target_uid: int
    map_id: int
    target_x: int
    target_y: int
    source: str
    _authority: object = field(repr=False, compare=False)
    _writer: object = field(repr=False, compare=False)
    _identities: tuple = field(repr=False, compare=False)
    _values: tuple = field(repr=False, compare=False)


class AttackTargets:
    """Use the actual broker/realm/retained reader, with no cached NPC authority.

    authorize/checkpoint await the existing broker native-owner check and then
    repeat the same authority projection. They do not acquire a second lock.
    Motion-off static targets have no separate spawn-drain marker in LocalRealm;
    the caller's existing serialized select/write/drain path owns that ordering.
    """
    def __init__(self, broker, reader):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker, 'ATTACK_REAL_BROKER_REQUIRED')
        need(type(reader) is observe.RetainedSceneReader, 'ATTACK_RETAINED_READER_REQUIRED')
        source_ready()
        self.broker, self.reader = broker, reader
        self._reader, self._reader_backend = reader, reader.backend
        self._reader_binding()

    def _reader_binding(self):
        reader = self.reader
        need(type(reader) is observe.RetainedSceneReader and reader is self._reader,
             'ATTACK_SAME_RETAINED_READER_REQUIRED')
        native = reader.backend
        need(native is self._reader_backend, 'ATTACK_SAME_RETAINED_BACKEND_REQUIRED')
        for validator in (reader.validate, getattr(native, 'validate', None)):
            need(type(validator) is MethodType and validator.__self__ is reader
                 and validator.__func__ is observe.RetainedSceneReader.validate,
                 'ATTACK_EXACT_RETAINED_VALIDATOR_REQUIRED')
        return native

    def _current(self, writer, request):
        from tools.local_original_session.broker import LocalRealm, _TransportPolicy
        need(type(request) is AttackRequest, 'ATTACK_TYPED_REQUEST_REQUIRED')
        need(0 < request.target_uid < U64_MAX, 'ATTACK_LOCAL_ACTOR_TARGET_REQUIRED')
        broker, reader = self.broker, self.reader
        native = self._reader_binding()
        policy, retained, member = broker.policy, reader.owner, reader.member
        need(not getattr(reader, 'closed', False)
             and type(policy) is _TransportPolicy and retained is not None and not retained.closed
             and policy.owner is retained and member is not None and retained.child is member
             and _handle_value(policy.handle) == _handle_value(retained.owner_handle)
             and _handle_value(policy.job) == _handle_value(retained.owner_job)
             and member.process == retained.owner_handle and member.job == retained.owner_job,
             'ATTACK_SAME_RETAINED_BROKER_REQUIRED')
        need(not broker._closing and not broker.failure.is_set() and policy.state == 'OPEN',
             'ATTACK_BROKER_LIFETIME_REQUIRED')
        claims = [row for rows in broker._claims.values() for row in rows if row['writer'] is writer]
        need(len(claims) == 1, 'ATTACK_CURRENT_CLAIM_REQUIRED')
        row, = claims
        policy_row = policy._connection(writer)
        need(row['policy_row'] is policy_row and policy_row.writer is writer
             and policy_row.stage == 1 and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
             and not any((row['failed'], row['joined'], policy_row.failed, policy_row.eof,
                          policy_row.task_joined, policy_row.registry_removed)),
             'ATTACK_CURRENT_POLICY_ADMISSION_REQUIRED')
        realm = broker.realm
        need(type(realm) is LocalRealm, 'ATTACK_REAL_REALM_REQUIRED')
        game = realm.registry.resolve(writer)
        service = realm.service(writer)
        selected = service.snapshot()
        need(type(service) is movement.MovementService and type(selected) is movement.Position
             and service._connection is writer, 'ATTACK_SAME_SELECTED_SERVICE_REQUIRED')
        realm._npc_authority(writer, game, service, selected)
        need(request.target_uid != selected.uid, 'ATTACK_LOCAL_SELF_TARGET_REFUSED')
        bound = realm._npc_frames.get(id(writer))
        need(bound is not None and bound[0] is writer and bound[1] is game and bound[2] is service,
             'ATTACK_CURRENT_BOUND_NPC_REQUIRED')
        candidates = [(spawn, wire) for spawn, wire in realm._npc_spawns
                      if type(spawn) is npc.NpcSpawn and spawn.uid == request.target_uid]
        need(len(candidates) == 1, 'ATTACK_CURRENT_TYPED_NPC_REQUIRED')
        spawn, wire = candidates[0]
        body = npc.session.world.encode_payload(0x4e96, spawn.fields)
        expected = struct.pack('<HH', len(body) + 6, 0x4e96) + body + b'\0\0'
        need(spawn.map_id == selected.map_id and type(wire) is bytes
             and wire == expected and wire in bound[3], 'ATTACK_CURRENT_NPC_MAP_FRAME_REQUIRED')
        if realm._npc_motion_interval_ns is not None:
            mover = realm.npc_mover(writer)
            state = mover.state
            need(type(mover) is npc_motion.NpcMotion and type(state) is npc_motion.State
                 and not mover.closed and not mover.fatal and mover.pending is None
                 and mover.spawn_drained is True and state.uid == spawn.uid
                 and state.map_id == spawn.map_id == selected.map_id,
                 'ATTACK_CURRENT_DRAINED_NPC_STATE_REQUIRED')
            x, y = movement.authority.unpack_grid(state.packed)
            source = 'CURRENT_NPC_MOTION_STATE'
        else:
            need(id(writer) not in realm._npc_motion, 'ATTACK_INCONSISTENT_STATIC_NPC_REQUIRED')
            mover, state = None, spawn
            x, y = movement.authority.unpack_grid(spawn.fields[1])
            source = 'CURRENT_BOUND_TYPED_NPC_SPAWN'
        # Request coordinates are comparisons only, never authority or direction.
        need((request.target_x is None or request.target_x == x)
             and (request.target_y is None or request.target_y == y),
             'ATTACK_LOCAL_CURRENT_TARGET_COORDINATES_REQUIRED')
        identities = (broker, policy, retained, member, member.identity,
            broker.failure, row, row['peer'], policy_row, policy_row.peer, realm,
            realm.registry, realm.store, realm.positions, game, game.selection,
            service, selected, realm._npc_spawns, bound, spawn, mover, state,
            reader, reader.owner, reader.member, native)
        # PROCESS.process is a ctypes HANDLE field: every access can produce a
        # fresh Python int. Bind its exact typed value, together with all other
        # handles and process/peer metadata, while retaining real objects above.
        values = tuple(_handle_value(value) for value in (
            policy.handle, policy.job, retained.owner_handle, retained.owner_job,
            member.process, member.job, native.handle))
        values += tuple(_typed_value(value) for value in (
            member.pid, *(member.identity.get(key) for key in ('pid', 'birth', 'image', 'parent_pid')),
            policy_row.peer.port, policy_row.peer.client_port, policy_row.peer.accepted_ns,
            wire, *row['peer'].keys(), *row['peer'].values()))
        return row, selected, x, y, source, values, identities

    @staticmethod
    def same_authority(left, right):
        """Compare two _project results, retaining references and typed values.

        Consumers that hold a projection across reads/awaits must use both
        components; the final reference-only tuple alone is insufficient.
        """
        return _same_binding(left[-1], left[-2], right[-1], right[-2])

    def _project(self, writer, request):
        before = self._current(writer, request)
        self.reader.validate()  # Existing injected/read-only identity verifier.
        after = self._current(writer, request)
        need(self.same_authority(before, after), 'ATTACK_AUTHORITY_CHANGED')
        return after

    def observe_committed_approach(self, writer, request, previous, counters, event_start):
        """Observe one real received Move commit; never authorize an Attack.

        The complete authority comparator remains unchanged. Only this source
        boundary separates its exact Position reference after a verified move.
        No BoundTarget, Position, packet, Store write or retry is created.
        """
        source_ready()
        current = AttackTargets._project(self, writer, request)
        row, position = current[:2]
        need(type(previous) is tuple and len(previous) == 7, 'ATTACK_APPROACH_BINDING_CHANGED')
        old = previous[1]
        need(type(old) is movement.Position and type(position) is movement.Position
             and position is not old and len(previous[-1]) == len(current[-1]) == 27
             and previous[-1][17] is old and current[-1][17] is position
             and current[0] is previous[0] and current[2:5] == previous[2:5]
             and _same_binding(current[-1][:17] + current[-1][18:], current[-2],
                               previous[-1][:17] + previous[-1][18:], previous[-2]),
             'ATTACK_APPROACH_BINDING_CHANGED')
        service, policy = self.broker.realm.service(writer), self.broker.policy
        actual = (service.requests_received, service.committed, service.corrections_prepared)
        need(type(service) is movement.MovementService and service._connection is writer
             and service._store is self.broker.realm.positions and not service.fatal
             and type(counters) is tuple and len(counters) == 3
             and all(type(n) is int and 0 <= n < movement.MAX_COUNTER for n in (*counters, *actual))
             and actual == (counters[0] + 1, counters[1] + 1, counters[2])
             and (position.uid, position.name, position.map_id) == (old.uid, old.name, old.map_id)
             and (position.word0 - old.word0, position.word1 - old.word1) in movement.authority.DELTAS,
             'ATTACK_APPROACH_SINGLE_COMMIT_REQUIRED')
        last = service.last_result
        need(type(last) is dict and last.get('accepted') is True and last.get('reason') == 'COMMITTED'
             and last.get('unknown') is False and last.get('fatal') is False
             and last.get('authority') == position.metadata()
             and last.get('reply_count') == 0 and last.get('own_SC4E2C_count') == 0
             and self.broker.realm.positions.restore(position) == position,
             'ATTACK_APPROACH_CURRENT_STORE_COMMIT_REQUIRED')
        need(type(event_start) is int, 'ATTACK_APPROACH_RECEIVED_MOVE_REQUIRED')
        end = policy.events
        offset = event_start - (end - len(policy.log))
        need(0 <= offset <= len(policy.log), 'ATTACK_APPROACH_RECEIVED_MOVE_REQUIRED')
        received = [event for event in list(policy.log)[offset:] if event[0] == 'rx'
                    and event[1] == row['peer']['endpoint_port'] and event[2] == 0x4e2b]
        need(len(received) == 1 and row['policy_row'].received > 0,
             'ATTACK_APPROACH_RECEIVED_MOVE_REQUIRED')
        after = AttackTargets._project(self, writer, request)
        need(AttackTargets.same_authority(current, after)
             and actual == (service.requests_received, service.committed, service.corrections_prepared)
             and service.last_result is last and self.broker.policy is policy and policy.events == end,
             'ATTACK_APPROACH_CHANGED_DURING_OBSERVATION')
        return after, actual, end

    async def authorize(self, writer, request):
        source_ready()
        row, selected, x, y, source, values, identities = self._project(writer, request)
        bound = BoundTarget(request, selected, request.target_uid, selected.map_id, x, y,
                            source, self, writer, identities, values)
        need(await self.broker._movement_owner(writer, row, selected) is True,
             'ATTACK_CURRENT_NATIVE_OWNER_REQUIRED')
        self.revalidate(bound)
        return bound

    def revalidate(self, bound):
        need(type(bound) is BoundTarget and bound._authority is self,
             'ATTACK_SAME_TARGET_AUTHORITY_REQUIRED')
        row, selected, x, y, source, values, identities = self._project(bound._writer, bound.request)
        need(_same_binding(identities, values, bound._identities, bound._values)
             and selected is bound.attacker
             and (bound.target_uid, bound.map_id, bound.target_x, bound.target_y, bound.source)
                 == (bound.request.target_uid, selected.map_id, x, y, source),
             'ATTACK_BOUND_TARGET_STALE')
        return row

    async def checkpoint(self, bound):
        row = self.revalidate(bound)
        need(await self.broker._movement_owner(bound._writer, row, bound.attacker) is True,
             'ATTACK_CURRENT_NATIVE_OWNER_REQUIRED')
        self.revalidate(bound)
        return bound

    def action_frame(self, bound, *, raw_effect, direction, self_action):
        """Build kind1; all policy inputs explicit, f13 None omits the field.

        raw_effect is source f4, not a verified damage/HP value. Direction0..8
        is this local builder's subset; value8 reuses current Transform+88.
        f13 False skips an own action; True takes common admission. Omission's
        default, own prediction/Start side effects and official reply duty are
        UNKNOWN. A built frame is not authorization to send or a combat result.
        """
        source_ready()
        self.revalidate(bound)
        _int32(raw_effect)
        need(type(direction) is int and 0 <= direction <= 8, 'ATTACK_EXPLICIT_DIRECTION_REQUIRED')
        need(self_action is None or type(self_action) is bool, 'ATTACK_EXPLICIT_F13_REQUIRED')
        fields = [_field(1, 1), _field(2, bound.attacker.uid), _field(3, bound.target_uid),
                  _field(4, raw_effect), _field(5, direction)]
        if self_action is not None:
            fields.append(pb.encode_bool(13, self_action))
        body = pb.encode_message(fields)
        wire = struct.pack('<HH', len(body) + 6, ACTION_OPCODE) + body + b'\0\0'
        self.revalidate(bound)
        return wire
