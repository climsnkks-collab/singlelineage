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
    """One explicit request per selected player life, under its original row lock.

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
        self._repeated_histories = {}  # Append only within the current explicit life.
        self._resource_lives = {}  # Source-issued life/token once registration; no new epoch.
        self.closed = False
        self.last_result = None

    def adopt_resource_new_life_locked(self, writer, life, cycle, baseline):
        """Retire prior-life requests only after an exact owner-issued baseline."""
        from tools.local_original_session import player_life, hp_resource_owner
        owner = getattr(self.status, '_resource_owner', None)
        need(type(cycle) is player_life._Cycle, 'NPC_PLAYER_HIT_TYPED_NEW_LIFE_CYCLE_REQUIRED')
        token, original_context, restore = cycle.new_token, cycle.context, cycle.status
        deliveries = tuple(cycle.deliveries)
        need(type(self) is Service and not self.closed
             and self.broker._npc_player_hit is self and life.hit is self
             and type(life) is player_life.Service and self.broker._player_life is life
             and life.status is self.status and not life.closed
             and type(cycle) is player_life._Cycle and life._cycles.get(id(writer)) is cycle
             and cycle.stage == 'NEW_LIFE' and not cycle.terminal
             and cycle.after_context is None and token is not None
             and life.token(writer) is token
             and restore.phase == 'DRAINED'
             and all(delivery.phase == 'DRAINED' for delivery in cycle.deliveries)
             and type(owner) is hp_resource_owner.ResourceOwner and owner.status is self.status
             and type(baseline) is hp_status.Snapshot and baseline._service is self.status
             and baseline.revision == 0
             and baseline.current_hp == original_context.snapshot.maximum_hp,
             'NPC_PLAYER_HIT_SOURCE_NEW_LIFE_BASELINE_REQUIRED')
        row = self.status._checked(writer, locked=True)[3]
        previous = tuple(self._repeated_histories.get(id(writer), ()))
        single = self._operations.get(id(writer))
        operations = previous + (() if single is None else (single,))
        def ready():
            return all(type(op) is _Prepared and op.context._service is self
                       and op.context._writer is writer and op.phase == 'COMMITTED'
                       and op.hp_operation is not None and op.hp_transport == 'DRAINED'
                       and op.attack_transport == 'DRAINED' for op in operations)
        need(self._resource_lives.get(id(writer)) is not token and ready(),
             'NPC_PLAYER_HIT_NEW_LIFE_PENDING_OR_ALREADY_ADOPTED')
        need(self.status.current(writer) is baseline
             and owner.hp_lineage_ready(writer, baseline, None) is True,
             'NPC_PLAYER_HIT_EXACT_RESOURCE_BASELINE_REQUIRED')
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        final_snapshot = self.status.current(writer)
        final_row = self.status._checked(writer, locked=True)[3]
        final_token = life.token(writer)
        current = tuple(self._repeated_histories.get(id(writer), ()))
        need(len(previous) == len(current) and all(a is b for a,b in zip(previous,current))
             and self._operations.get(id(writer)) is single and ready()
             and self._resource_lives.get(id(writer)) is not token
             and life._cycles.get(id(writer)) is cycle and not cycle.terminal
             and cycle.stage == 'NEW_LIFE' and cycle.after_context is None
             and cycle.new_token is token and final_token is token
             and cycle.context is original_context and cycle.status is restore
             and restore.phase == 'DRAINED'
             and len(cycle.deliveries) == len(deliveries)
             and all(a is b and b.phase == 'DRAINED' for a,b in zip(deliveries,cycle.deliveries))
             and self.status._resource_owner is owner
             and final_snapshot is baseline and self.status._states.get(id(writer)) is baseline
             and final_row is row,
             'NPC_PLAYER_HIT_NEW_LIFE_ADOPTION_CHANGED')
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        # All fallible owner/cancel/once checks precede this synchronous revoke.
        # Existing release revokes old opaque Contexts and delivery histories;
        # it never rolls back HP, replays an attempt or mints a resource token.
        self.release(writer)
        self._resource_lives[id(writer)] = token

    def _current(self, writer, *, player_life_context=None, source_uid=None):
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
        source_uid=realm.npc_target_uid(source_uid)
        spawn=next(spawn for spawn,_ in realm._npc_spawns if spawn.uid==source_uid)
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
        mover = realm.npc_mover(writer,target_uid=source_uid)
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
            generation = lifecycle.current_generation(writer,target_uid=source_uid)
            need(generation.writer is writer and generation.row is row and generation.mover is mover
                 and generation.frames is npc_lifetime[5] and generation.spawn.uid == spawn.uid,
                 'NPC_PLAYER_HIT_CURRENT_GENERATION_REQUIRED')
        final = self.status._checked(writer, locked=True)
        final_npc_lifetime, final_target = self.combat._hp_binding(writer, row, spawn.uid)
        need(all(a is b for a, b in zip(lifetime, final))
             and self.status._states.get(id(writer)) is snapshot
             and len(npc_lifetime) == len(final_npc_lifetime)
             and all(a is b for a, b in zip(npc_lifetime, final_npc_lifetime))
             and final_target == target and realm.npc_mover(writer,target_uid=source_uid) is mover
             and mover.spawn_drained and not mover.closed and not mover.fatal
             and mover.pending is None and mover.state.uid == spawn.uid
             and mover.state.map_id == spawn.map_id == snapshot.map_id
             and self.combat._hp._entries.get((id(writer), spawn.uid)) is entry
             and getattr(broker, '_npc_respawn', None) is lifecycle
             and (lifecycle is None or lifecycle.current_generation(writer,target_uid=source_uid) is generation)
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

    def require_repeated_ready(self, writer, row, snapshot, *, _capture_authority=None, source_uid=None):
        need(self.policy == REPEATED_POLICY and id(writer) not in self._operations,
             'NPC_PLAYER_HIT_REPEATED_POLICY_REQUIRED')
        previous = self.operation_for(writer)
        owner = getattr(self.status, '_resource_owner', None)
        need(previous is None or previous.phase == 'COMMITTED' and previous.hp_operation is not None
             and previous.hp_transport == 'DRAINED'
             and (owner.hp_lineage_ready(writer, snapshot, previous.hp_operation) is True
                  if owner is not None else previous.hp_operation.result.after is snapshot),
             'NPC_PLAYER_HIT_PREVIOUS_REPEATED_COMMIT_REQUIRED')
        _, _, hp_previous = self.status.require_repeated_ready(writer, row, expected_snapshot=snapshot,
            expected_revision=snapshot.revision, policy=hp_status.REPEATED_POLICY)
        need(hp_previous is (None if previous is None else previous.hp_operation),
             'NPC_PLAYER_HIT_MATCHING_HP_PREDECESSOR_REQUIRED')
        if previous is not None:
            self._require_hp_predecessor_locked(writer, row, snapshot, previous,
                                                expected_authority=_capture_authority,source_uid=source_uid)
        return previous

    def _require_hp_predecessor_locked(self, writer, row, snapshot, previous, *, expected_authority=None, source_uid=None):
        """Validate historical player-HP delivery; independently validate current NPC.

        The old NPC may have been damaged or respawned. Its Context/Result is
        never made current again: only the registered committed HP predecessor
        is consumed. New attack authority comes entirely from the original
        current-source projection (and actual adopted receipt after respawn).
        """
        broker, realm, context = self.broker, self.broker.realm, previous.context
        source_uid=realm.npc_target_uid(source_uid)
        history = self._repeated_histories.get(id(writer))
        hp_history = self.status._repeated_histories.get(id(writer))
        result, delivery = previous.result, previous.hp_operation
        need(type(history) is list and history and history[-1] is previous
             and type(hp_history) is list and hp_history and hp_history[-1] is delivery
             and type(previous) is _Prepared and context._service is self and context._writer is writer
             and previous.phase == 'COMMITTED' and previous.attack_transport == previous.hp_transport == 'DRAINED'
             and type(result) is Result and result._service is self and result._operation is previous
             and delivery is not None and delivery.phase == 'DRAINED'
             and delivery.writer is writer and delivery.row is row
             and result.before is context.snapshot is delivery.result.before
             and result.after is delivery.result.after
             and context.target_uid == snapshot.target_uid and context.map_id == snapshot.map_id
             and len(result.after._lifetime) == len(snapshot._lifetime)
             and all(a is b for a,b in zip(result.after._lifetime,snapshot._lifetime)),
             'NPC_PLAYER_HIT_REGISTERED_HP_PREDECESSOR_REQUIRED')
        saved_history, saved_hp_history = tuple(history), tuple(hp_history)
        hp_result = delivery.result
        lifecycle = getattr(broker, '_npc_respawn', None)
        generation = receipt = None
        if lifecycle is not None:
            from tools.local_original_session import npc_respawn
            need(type(lifecycle) is npc_respawn.Service and lifecycle.broker is broker
                 and lifecycle is realm._npc_respawn, 'NPC_PLAYER_HIT_CURRENT_LIFECYCLE_REQUIRED')
            generation = lifecycle.current_generation(writer,target_uid=source_uid)
            if generation.ordinal != 0:
                receipt = lifecycle._receipts.get(lifecycle._key(writer,source_uid))
                need(type(receipt) is npc_respawn.Receipt and receipt._service is lifecycle
                     and receipt.writer is writer and receipt.row is row
                     and receipt.generation is generation and receipt.old_generation is not generation
                     and receipt.mover is generation.mover and receipt.mover is not receipt.old_generation.mover
                     and lifecycle._phases.get(lifecycle._key(writer,source_uid)) == 'COMMITTED',
                     'NPC_PLAYER_HIT_CURRENT_COMMITTED_RESPAWN_REQUIRED')
                # 입력 edge receipt의 global adapter 권위는 singleton에서만 이 검사에 필요하다.
                # multi의 현재 source는 아래 UID generation/frame/mover와 _current로 확인한다.
                if len(realm._npc_spawns) == 1:
                    lifecycle.require_current(receipt)
        actual, current, identities, values = self._current(writer,source_uid=source_uid)
        motion=realm._npc_motion.get(id(writer),(None,None))[1]
        current_mover=motion.get(source_uid) if type(motion) is dict else motion
        current_frames=(realm._npc_frames.get(id(writer)) if len(realm._npc_spawns)==1 else
                        realm._npc_frames_by_uid.get((id(writer),source_uid)))
        # Final callback-free checks: source validation cannot silently replace
        # either history, the selected player, service or committed receipt.
        need(actual is row and current is snapshot and not self.closed
             and broker._npc_player_hit is realm._npc_player_hit is self
             and self.operation_for(writer) is previous and previous.context is context
             and previous.phase == 'COMMITTED' and previous.attack_transport == previous.hp_transport == 'DRAINED'
             and previous.result is result and result._operation is previous
             and previous.hp_operation is delivery and delivery.phase == 'DRAINED'
             and delivery.result is hp_result and result.before is hp_result.before
             and result.after is hp_result.after
             and self._repeated_histories.get(id(writer)) is history
             and len(history) == len(saved_history) and all(a is b for a,b in zip(history,saved_history))
             and self.status._repeated_histories.get(id(writer)) is hp_history
             and len(hp_history) == len(saved_hp_history) and all(a is b for a,b in zip(hp_history,saved_hp_history))
             and self.status._states.get(id(writer)) is snapshot
             and getattr(broker, '_npc_respawn', None) is lifecycle
             and (lifecycle is None or lifecycle is realm._npc_respawn
                  and lifecycle._generations.get(lifecycle._key(writer,source_uid)) is generation
                  and generation.writer is writer and generation.row is row
                  and generation.mover.spawn_drained and not generation.mover.closed
                  and not generation.mover.fatal and generation.mover.pending is None
                  and current_mover is generation.mover
                  and current_frames is generation.frames)
             and (receipt is None or lifecycle._receipts.get(lifecycle._key(writer,source_uid)) is receipt
                  and lifecycle._phases.get(lifecycle._key(writer,source_uid)) == 'COMMITTED'
                  and receipt.generation is generation and receipt.writer is writer and receipt.row is row)
             and (expected_authority is None or values == expected_authority[1]
                  and len(identities) == len(expected_authority[0])
                  and all(a is b for a,b in zip(identities,expected_authority[0]))),
             'NPC_PLAYER_HIT_HP_PREDECESSOR_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()

    def capture_locked(self, writer, *, approach=None, source_uid=None):
        row, snapshot, identities, values = self._current(writer,source_uid=source_uid)
        need(snapshot.current_hp > 1, 'NPC_PLAYER_HIT_POSITIVE_HP_MINUS_ONE_REQUIRED')
        previous = None
        if self.policy == REPEATED_POLICY:
            previous = self.require_repeated_ready(writer, row, snapshot, _capture_authority=(identities,values),source_uid=values[0])
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
        row, snapshot, identities, values = self._current(writer,source_uid=context.source_uid)
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
            previous = self.require_repeated_ready(writer, self._current(writer,source_uid=expected_context.source_uid)[0], expected_context.snapshot,source_uid=expected_context.source_uid,
                _capture_authority=(expected_context._identities,expected_context._values))
            if previous is None:
                self.validate_locked(writer, expected_context)
            need(expected_context._previous is previous and self._contexts.get(id(writer)) is expected_context
                 and not self.closed and self.operation_for(writer) is previous,
                 'NPC_PLAYER_HIT_REPEATED_PREDECESSOR_CHANGED')
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
        context = operation.context
        actual, current, identities, values = self._current(writer,source_uid=context.source_uid)
        expected_values = (*context._values[:3], current.revision, *context._values[4:])
        owner = getattr(self.status, '_resource_owner', None)
        need(operation.hp_operation is not None, 'NPC_PLAYER_HIT_STATUS_OPERATION_REQUIRED')
        exact = ((self.status.repeated_delivery(writer) is operation.hp_operation
                  if self.policy == REPEATED_POLICY else
                  self.status._operations.get(id(writer)) is operation.hp_operation)
                 and current is operation.hp_operation.result.after)
        linked = (owner.hp_lineage_ready(writer, current, operation.hp_operation) is True
                  if owner is not None and (not exact or operation.phase == 'COMMITTED')
                  else exact)
        need(linked
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
        self._resource_lives.pop(id(writer), None)
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
        self._resource_lives.clear()
