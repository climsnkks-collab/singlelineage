"""Explicit current-NPC attack then one positive selected-player HP decrease.

Damage one is local policy, never SC4E31's raw effect scalar. Reviewed run94
supports these wire roles conditionally, not a client action/HP receipt.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import struct

from tools.local_original_session import attack, attack_feedback, attack_session, hp_status, npc_hp, npc_motion, observe

POLICY = 'EXPLICIT_LOCAL_CURRENT_NPC_ONE_POSITIVE_PLAYER_HIT'
REPEATED_POLICY = 'EXPLICIT_LOCAL_CURRENT_NPC_REPEATED_POSITIVE_PLAYER_HIT'
need = attack.need
SOURCE_PINS = {
    'work/local_server_rea_20261016/run94_player_hit_status/implementation-conditions.md':
        'baebe8cab69093797d9a84f796743b937ec8240a67cc3df67ff687e50d557f98',
    'work/local_server_rea_20261016/run94_player_hit_status/findings.md':
        'f72cb73bcad73cfa66a482e9d940c920fe7ff70e7e6ed0b229730f9c2618f253',
    'work/local_server_rea_20261016/run94_player_hit_status/source-evidence.json':
        '809b00dd126d2023629d3d900c9ab28d28b906caacab329347be05889a451c5d',
    'work/local_server_rea_20261016/run94_player_hit_status/main-review.json':
        '3fc0e90e3650b91eaa0acafd35b6cea8046334eac5460999320decf099fbfead',
}


def source_ready():
    for relative, expected in SOURCE_PINS.items():
        raw = observe.ordinary(observe.ROOT / relative).read_bytes()
        need(0 < len(raw) <= 1048576 and hashlib.sha256(raw).hexdigest() == expected,
             'NPC_PLAYER_HIT_SOURCE_CHANGED')
    attack_feedback.source_ready()


def _hp(snapshot):
    return dict(current_hp=snapshot.current_hp, maximum_hp=snapshot.maximum_hp,
                revision=snapshot.revision)


@dataclass(frozen=True, slots=True)
class Result:
    before: hp_status.Snapshot = field(repr=False)
    after: hp_status.Snapshot = field(repr=False)
    source_uid: int
    _service: object = field(repr=False)
    _operation: object = field(repr=False)

    def require_current_locked(self, writer):
        return self._service.validate_result_locked(writer, self)

    def metadata(self):
        return dict(status='COMMITTED', source_uid=self.source_uid, target_uid=self.after.target_uid,
                    map_id=self.after.map_id, damage=1, attack_transport='DRAINED', hp_committed=True,
                    hp_transport='DRAINED', before=_hp(self.before), after=_hp(self.after),
                    client_hit='UNKNOWN', client_hp='UNKNOWN')


@dataclass(frozen=True, slots=True)
class Context:
    """Opaque exact current life and selected status; UID equality is insufficient."""
    source_uid: int
    target_uid: int
    map_id: int
    snapshot: hp_status.Snapshot = field(repr=False)
    _service: object = field(repr=False)
    _writer: object = field(repr=False)
    _identities: tuple = field(repr=False)
    _values: tuple = field(repr=False)
    _previous: object = field(default=None, repr=False)
    _approach: object = field(default=None, repr=False)


@dataclass(slots=True)
class _Prepared:
    context: Context = field(repr=False)
    phase: str = 'PREPARED_AUTHORITY_ONLY'
    wire: bytes | None = field(default=None, repr=False)
    attack_transport: str = 'NOT_REQUESTED'
    hp_operation: object = field(default=None, repr=False)
    hp_transport: str = 'NOT_REQUESTED'
    sent_before: int | None = None
    result: object = field(default=None, repr=False)
    previous: object = field(default=None, repr=False)


class Service:
    """One explicit request per selected player, under its original row lock.

    No own lock, timer, queued AI or HP authority is added. Capture/prepare use
    real HP Status and AttackSession NPC life validators; the latter's original
    retained validator is identity-only here, never a new memory collector.
    """
    def __init__(self, broker, *, policy):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker and type(policy) is str and policy in (POLICY, REPEATED_POLICY),
             'NPC_PLAYER_HIT_EXPLICIT_REAL_BROKER_REQUIRED')
        status, combat = broker._hp_status, broker._attack_session
        need(type(status) is hp_status.Service and status is broker.realm._hp_status
             and type(combat) is attack_session.AttackSession and combat is broker.realm._attack_session
             and type(combat._hp) is npc_hp.Authority,
             'NPC_PLAYER_HIT_EXISTING_HP_AND_NPC_LIFE_REQUIRED')
        self.broker, self.policy = broker, policy
        self.status, self.combat, self.source_guard = status, combat, broker.source_guard
        need(policy != REPEATED_POLICY or status.repeated_policy == hp_status.REPEATED_POLICY,
             'NPC_PLAYER_HIT_REPEATED_HP_SERVICE_REQUIRED')
        self._contexts, self._operations = {}, {}
        self._repeated_histories = {}  # Append only; never recycle an accepted context.
        self.closed = False
        self.last_result = None

    def _current(self, writer, *, player_life_context=None):
        broker, realm = self.broker, self.broker.realm
        need(not self.closed and broker._npc_player_hit is self and realm._npc_player_hit is self
             and broker._hp_status is self.status and realm._hp_status is self.status
             and broker._attack_session is self.combat and realm._attack_session is self.combat
             and broker.source_guard is self.source_guard and self.policy in (POLICY, REPEATED_POLICY)
             and not self.combat.closed and not self.combat.fatal,
             'NPC_PLAYER_HIT_CURRENT_SERVICE_REQUIRED')
        lifetime = self.status._checked(writer, locked=True)
        row = lifetime[3]
        snapshot = (self.status.current(writer) if player_life_context is None else
                    self.status.current_player_life(writer, player_life_context))
        # One original current spawn and drained mover; neither an old UID nor
        # another client's same recipe can stand in for this selection's life.
        spawn, = (spawn for spawn, _ in realm._npc_spawns)
        self.combat.require_live_npc_motion(writer, row, spawn.uid)
        npc_lifetime, target = self.combat._hp_binding(writer, row, spawn.uid)
        owner_projection = self.combat.targets._current(writer, attack.AttackRequest(spawn.uid))
        entry = self.combat._hp._entries.get((id(writer), spawn.uid))
        hp = (self.combat._hp.provider.initial_hp(target) if entry is None else entry.hp)
        need(type(hp) is npc_hp.Hp and hp.alive, 'NPC_PLAYER_HIT_CURRENT_LIVE_NPC_REQUIRED')
        # Provider is synchronous external backend code; revalidate after it.
        self.combat.require_live_npc_motion(writer, row, spawn.uid)
        after_lifetime, after_target = self.combat._hp_binding(writer, row, spawn.uid)
        need(target == after_target and all(a is b for a, b in zip(npc_lifetime, after_lifetime))
             and self.combat._hp._entries.get((id(writer), spawn.uid)) is entry,
             'NPC_PLAYER_HIT_LIFE_CHANGED')
        mover = realm.npc_mover(writer)
        need(type(mover) is npc_motion.NpcMotion and mover.spawn_drained and not mover.closed
             and not mover.fatal and mover.pending is None and mover.state.uid == spawn.uid
             and mover.state.map_id == spawn.map_id == snapshot.map_id
             and spawn.uid != snapshot.target_uid,
             'NPC_PLAYER_HIT_CURRENT_DRAINED_MOVER_REQUIRED')
        lifecycle = getattr(broker, '_npc_respawn', None)
        generation = None
        if lifecycle is not None:
            from tools.local_original_session import npc_respawn
            need(type(lifecycle) is npc_respawn.Service and lifecycle is realm._npc_respawn,
                 'NPC_PLAYER_HIT_CURRENT_LIFECYCLE_REQUIRED')
            generation = lifecycle.current_generation(writer)
            need(generation.writer is writer and generation.row is row and generation.mover is mover
                 and generation.frames is npc_lifetime[5] and generation.spawn.uid == spawn.uid,
                 'NPC_PLAYER_HIT_CURRENT_GENERATION_REQUIRED')
        final = self.status._checked(writer, locked=True)
        final_npc_lifetime, final_target = self.combat._hp_binding(writer, row, spawn.uid)
        need(all(a is b for a, b in zip(lifetime, final))
             and self.status._states.get(id(writer)) is snapshot
             and len(npc_lifetime) == len(final_npc_lifetime)
             and all(a is b for a, b in zip(npc_lifetime, final_npc_lifetime))
             and final_target == target and realm.npc_mover(writer) is mover
             and mover.spawn_drained and not mover.closed and not mover.fatal
             and mover.pending is None and mover.state.uid == spawn.uid
             and mover.state.map_id == spawn.map_id == snapshot.map_id
             and self.combat._hp._entries.get((id(writer), spawn.uid)) is entry
             and getattr(broker, '_npc_respawn', None) is lifecycle
             and (lifecycle is None or lifecycle.current_generation(writer) is generation)
             and not self.closed and broker._npc_player_hit is realm._npc_player_hit is self
             and broker._attack_session is realm._attack_session is self.combat
             and not self.combat.closed and not self.combat.fatal,
             'NPC_PLAYER_HIT_SELECTION_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        final_projection = self.combat.targets._current(writer, attack.AttackRequest(spawn.uid))
        need(attack.AttackTargets.same_authority(owner_projection, final_projection),
             'NPC_PLAYER_HIT_OWNER_PROJECTION_CHANGED')
        # Preserve the original complete retained-owner/typed-handle/peer values
        # and references. Position/state are the two motion identities in the
        # fixed attack.py projection; like the original NPC HP lifetime they
        # are validated fresh, not retained across normal movement.
        owner_identities = tuple(value for index, value in enumerate(final_projection[-1])
                                 if index not in (17, 22))
        identities = (*lifetime, *npc_lifetime, self.combat, self.combat._hp,
                      self.combat._hp.provider, entry, mover, lifecycle, generation,
                      self.combat.targets, *owner_identities)
        values = (spawn.uid, snapshot.target_uid, spawn.map_id, snapshot.revision,
                  hp.current, hp.maximum, mover.state.uid, mover.state.map_id,
                  None if generation is None else generation.ordinal, final_projection[-2])
        return row, snapshot, identities, values

    def operation_for(self, writer):
        history = self._repeated_histories.get(id(writer))
        return history[-1] if self.policy == REPEATED_POLICY and history else self._operations.get(id(writer))

    def require_repeated_ready(self, writer, row, snapshot):
        need(self.policy == REPEATED_POLICY and id(writer) not in self._operations,
             'NPC_PLAYER_HIT_REPEATED_POLICY_REQUIRED')
        previous = self.operation_for(writer)
        need(previous is None or previous.phase == 'COMMITTED' and previous.hp_operation is not None
             and previous.hp_transport == 'DRAINED' and previous.hp_operation.result.after is snapshot,
             'NPC_PLAYER_HIT_PREVIOUS_REPEATED_COMMIT_REQUIRED')
        if previous is not None:
            self._validate_after_locked(writer, previous)
        _, _, hp_previous = self.status.require_repeated_ready(writer, row, expected_snapshot=snapshot,
            expected_revision=snapshot.revision, policy=hp_status.REPEATED_POLICY)
        need(hp_previous is (None if previous is None else previous.hp_operation),
             'NPC_PLAYER_HIT_MATCHING_HP_PREDECESSOR_REQUIRED')
        return previous

    def capture_locked(self, writer, *, approach=None):
        row, snapshot, identities, values = self._current(writer)
        need(snapshot.current_hp > 1, 'NPC_PLAYER_HIT_POSITIVE_HP_MINUS_ONE_REQUIRED')
        previous = None
        if self.policy == REPEATED_POLICY:
            previous = self.require_repeated_ready(writer, row, snapshot)
        else:
            need(id(writer) not in self._operations, 'NPC_PLAYER_HIT_ONCE_REQUEST_REQUIRED')
        if approach is not None:
            from tools.local_original_session import npc_approach_hit
            need(type(approach) is npc_approach_hit.Arrival, 'NPC_PLAYER_HIT_TYPED_APPROACH_REQUIRED')
            approach.ready_locked(writer)
        context = Context(values[0], values[1], values[2], snapshot, self, writer, identities, values, previous, approach)
        if approach is not None:
            approach.claim_context_locked(writer, context)
        # Re-capture does not reset a deadline or consume a request. Retain only
        # the last opaque context so an older equal-value capability is stale.
        self._contexts[id(writer)] = context
        return context

    def validate_locked(self, writer, context):
        need(type(context) is Context and context._service is self and context._writer is writer
             and self._contexts.get(id(writer)) is context,
             'NPC_PLAYER_HIT_EXACT_CONTEXT_REQUIRED')
        row, snapshot, identities, values = self._current(writer)
        need(snapshot is context.snapshot and values == context._values
             and len(identities) == len(context._identities)
             and all(a is b for a, b in zip(identities, context._identities)),
             'NPC_PLAYER_HIT_STALE_CONTEXT')
        if context._approach is not None:
            context._approach.require_current_locked(writer, context)
        return row

    def prepare_locked(self, writer, *, expected_context):
        self.validate_locked(writer, expected_context)
        if self.policy == REPEATED_POLICY:
            previous = self.require_repeated_ready(writer, self._current(writer)[0], expected_context.snapshot)
            need(expected_context._previous is previous, 'NPC_PLAYER_HIT_REPEATED_PREDECESSOR_CHANGED')
            operation = _Prepared(expected_context, previous=previous)
            history = self._repeated_histories.setdefault(id(writer), [])
            history.append(operation)
        else:
            need(id(writer) not in self._operations, 'NPC_PLAYER_HIT_ONCE_REQUEST_REQUIRED')
            operation = _Prepared(expected_context)
            self._operations[id(writer)] = operation
        return operation

    def build_locked(self, writer, operation, *, raw_effect, direction):
        need(self.operation_for(writer) is operation
             and operation.phase == 'PREPARED_AUTHORITY_ONLY', 'NPC_PLAYER_HIT_CURRENT_OPERATION_REQUIRED')
        self.validate_locked(writer, operation.context)
        source_ready()
        attack._int32(raw_effect)
        need(raw_effect > 0 and type(direction) is int and 0 <= direction <= 8,
             'NPC_PLAYER_HIT_EXPLICIT_EFFECT_DIRECTION_REQUIRED')
        context = operation.context
        # Source-bound roles come only from this operation's exact capability.
        # Do not reverse a player->NPC BoundTarget or accept arbitrary UID args.
        fields = (attack._field(1, 1), attack._field(2, context.source_uid),
                  attack._field(3, context.target_uid), attack._field(4, raw_effect),
                  attack._field(5, direction), attack.pb.encode_bool(13, False))
        body = attack.pb.encode_message(fields)
        wire = struct.pack('<HH', len(body)+6, attack_feedback.OPCODE)+body+b'\0\0'
        parsed = attack_feedback.validate_frame(wire, policy=attack_feedback.POLICY)
        need(parsed.attacker_uid == context.source_uid and parsed.target_uid == context.target_uid
             and parsed.attacker_uid != parsed.target_uid and parsed.self_action is False,
             'NPC_PLAYER_HIT_EXACT_SOURCE_ROLES_REQUIRED')
        if context._approach is not None:
            context._approach.require_direction_locked(writer, parsed.direction)
            context._approach.bind_body_locked(writer,context,operation,wire,parsed)
        self.validate_locked(writer, context)
        operation.wire, operation.phase, operation.attack_transport = wire, 'ATTACK', 'PREPARED'
        self.remember(operation)
        return wire

    def validate_delivery(self, writer, row, wire, operation):
        need(self.operation_for(writer) is operation
             and operation.context._writer is writer and operation.phase in ('ATTACK', 'STATUS'),
             'NPC_PLAYER_HIT_CURRENT_OPERATION_REQUIRED')
        source_ready()
        if operation.phase == 'ATTACK':
            need(wire is operation.wire and operation.attack_transport in
                 ('PREPARED', 'RESERVED', 'WRITE_ATTEMPTED'), 'NPC_PLAYER_HIT_EXACT_ATTACK_WIRE_REQUIRED')
            actual = self.validate_locked(writer, operation.context)
            if operation.context._approach is not None:
                parsed = attack_feedback.validate_frame(wire, policy=attack_feedback.POLICY)
                operation.context._approach.require_direction_locked(writer, parsed.direction)
        else:
            need(operation.hp_operation is not None and wire is operation.hp_operation.wire
                 and operation.attack_transport == 'DRAINED', 'NPC_PLAYER_HIT_EXACT_STATUS_WIRE_REQUIRED')
            actual = self._validate_after_locked(writer, operation)
        need(actual is row, 'NPC_PLAYER_HIT_SAME_ROW_REQUIRED')
        return operation

    def _validate_after_locked(self, writer, operation):
        actual, current, identities, values = self._current(writer)
        context = operation.context
        expected_values = (*context._values[:3], current.revision, *context._values[4:])
        need(operation.hp_operation is not None
             and (self.status.repeated_delivery(writer) is operation.hp_operation
                  if self.policy == REPEATED_POLICY else
                  self.status._operations.get(id(writer)) is operation.hp_operation)
             and current is operation.hp_operation.result.after
             and values == expected_values and len(identities) == len(context._identities)
             and all(a is b for a, b in zip(identities, context._identities)),
             'NPC_PLAYER_HIT_STATUS_LIFETIME_CHANGED')
        if context._approach is not None:
            context._approach.require_current_locked(writer, context)
        return actual

    def validate_result_locked(self, writer, result):
        need(type(result) is Result and result._service is self
             and self.operation_for(writer) is result._operation
             and result._operation.result is result and result._operation.phase == 'COMMITTED',
             'NPC_PLAYER_HIT_CURRENT_RESULT_REQUIRED')
        source_ready()
        return self._validate_after_locked(writer, result._operation)

    def reserve(self, writer, row, wire, operation):
        self.validate_delivery(writer, row, wire, operation)
        need(operation.attack_transport == 'PREPARED' and operation.phase == 'ATTACK',
             'NPC_PLAYER_HIT_ATTACK_ONCE_REQUIRED')
        operation.sent_before = row['policy_row'].sent
        operation.attack_transport = 'RESERVED'
        self.remember(operation)

    def attempt(self, writer, row, wire, operation):
        self.validate_delivery(writer, row, wire, operation)
        need(operation.attack_transport == 'RESERVED' and operation.phase == 'ATTACK',
             'NPC_PLAYER_HIT_ATTACK_ONCE_REQUIRED')
        if operation.context._approach is not None:
            operation.context._approach.consume_attack_locked(writer,operation.context,operation,wire)
        operation.attack_transport = 'WRITE_ATTEMPTED'
        self.remember(operation)

    def drained(self, writer, row, wire, operation):
        self.validate_delivery(writer, row, wire, operation)
        admitted = row['policy_row']
        need(operation.attack_transport == 'WRITE_ATTEMPTED' and admitted.pending_opcode is None
             and admitted.drain_started_ns is None and admitted.sent == operation.sent_before+1,
             'NPC_PLAYER_HIT_EXACT_ATTACK_DRAIN_REQUIRED')
        operation.attack_transport = 'DRAINED'
        operation.phase = 'ATTACK_DRAINED'
        self.remember(operation)

    def remember(self, operation, *, terminal=False):
        context = operation.context
        after = None if operation.hp_operation is None else operation.hp_operation.result.after
        self.last_result = dict(status='TERMINAL' if terminal else operation.phase,
            source_uid=context.source_uid, target_uid=context.target_uid, map_id=context.map_id,
            damage=1, attack_transport=operation.attack_transport,
            hp_committed=operation.hp_operation is not None, hp_transport=operation.hp_transport,
            before=_hp(context.snapshot), after=None if after is None else _hp(after),
            client_hit='UNKNOWN', client_hp='UNKNOWN')

    def terminal(self, operation):
        self.remember(operation, terminal=True)
        operation.phase = 'TERMINAL'

    def release(self, writer):
        self._contexts.pop(id(writer), None)
        history = self._repeated_histories.pop(id(writer), ())
        for value in history:
            if value.phase != 'COMMITTED': self.terminal(value)
        operation = self._operations.pop(id(writer), None)
        if operation is not None:
            if operation.phase != 'COMMITTED': self.terminal(operation)

    def close(self):
        self.closed = True
        for context in tuple(self._contexts.values()):
            self.release(context._writer)
