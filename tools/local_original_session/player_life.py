"""One explicit selected-player death/recovery cycle, not an official rule set.

The existing HP service remains the sole status writer. This service owns local
life capabilities and delivery order, never native calls, action flags or UI.
"""
from dataclasses import dataclass, field
import asyncio
from tools.local_original_session import observe, player_life_codec as codec

need = observe.need
POLICY_LABEL = 'EXPLICIT_LOCAL_OWN_PLAYER_HP1_DEAD_RESTART_MAX_SAME_GRID_V1'
NPC_POLICY_LABEL = 'EXPLICIT_LOCAL_CURRENT_NPC_HP1_DEAD_RESTART_MAX_SAME_GRID_V1'
NEWLIFE_POLICY = 'REQUIRED_MESSAGES_DRAINED_LOCAL_TOKEN'

@dataclass(frozen=True, slots=True)
class Policy:
    label: str
    lethal: str
    sequence: str
    recovery: str
    init: str
    newlife: str

    def __post_init__(self):
        need(type(self.label) is str and self.label in (POLICY_LABEL,'TEST_LOCAL_POLICY',NPC_POLICY_LABEL),
             'PLAYER_LIFE_EXPLICIT_POLICY_LABEL_REQUIRED')
        need((self.lethal,self.sequence) == (
                 ('CURRENT_HP_ONE_NPC_HIT','NPC_HIT_HP0_DEATH_REQUEST_ACK_INIT_FULL_STATUS')
                 if self.label == NPC_POLICY_LABEL else
                 ('CURRENT_HP_ONE_STATUS_ONLY','HP0_DEATH_REQUEST_ACK_INIT_FULL_STATUS'))
             and self.recovery == 'MAX_HP_UNCHANGED_POSITION'
             and self.init == 'F4_PRESENT_ZERO_F5_OMIT'
             and self.newlife == NEWLIFE_POLICY,
             'PLAYER_LIFE_UNSUPPORTED_OR_MISSING_EXPLICIT_POLICY')

@dataclass(frozen=True, slots=True)
class Context:
    source_uid: int
    target_uid: int
    map_id: int
    snapshot: object = field(repr=False)
    _service: object = field(repr=False)
    _writer: object = field(repr=False)
    _identities: tuple = field(repr=False)
    _values: tuple = field(repr=False)
    _position: object = field(repr=False)
    _token: object = field(repr=False)

    def require_current_locked(self, writer):
        return self._service.current_locked(writer, self)

@dataclass(frozen=True, slots=True)
class AfterContext:
    """Fresh new-life read-only observation authority; never lethal authority."""
    source_uid: int
    target_uid: int
    map_id: int
    snapshot: object = field(repr=False)
    _service: object = field(repr=False)
    _writer: object = field(repr=False)
    _identities: tuple = field(repr=False)
    _values: tuple = field(repr=False)
    _position: object = field(repr=False)
    _token: object = field(repr=False)

    def require_current_locked(self, writer):
        return self._service.current_after_locked(writer,self)

@dataclass(slots=True)
class _Delivery:
    context: Context = field(repr=False)
    kind: str
    wire: bytes = field(repr=False)
    phase: str = 'PREPARED'
    sent: int | None = None
    write_attempted: bool = False
    drain_returned: bool = False

@dataclass(slots=True)
class _Cycle:
    context: Context = field(repr=False)
    inputs: object = field(repr=False)
    init_values: tuple = field(repr=False)
    stage: str = 'PREPARED'
    deliveries: list = field(default_factory=list, repr=False)
    status: object = field(default=None, repr=False)
    request_seen: bool = False
    new_token: object = field(default=None, repr=False)
    terminal: bool = False
    result: object = field(default=None, repr=False)
    after_context: object = field(default=None, repr=False)
    recovery_observed: bool = False
    npc_attack: object = field(default=None, repr=False)

@dataclass(frozen=True, slots=True)
class Result:
    context: Context = field(repr=False)
    _service: object = field(repr=False)
    _cycle: object = field(repr=False)
    _token: object = field(default=None, repr=False)

    def require_current_locked(self, writer):
        service, cycle = self._service, self._cycle
        need(type(cycle) is _Cycle and service._cycles.get(id(writer)) is cycle
             and cycle.result is self and not cycle.terminal,
             'PLAYER_LIFE_EXACT_CURRENT_RESULT_REQUIRED')
        if self._token is None:
            return self.context.require_current_locked(writer)
        need(cycle.stage == 'NEW_LIFE' and service.token(writer) is self._token,
             'PLAYER_LIFE_NEW_LIFE_RESULT_STALE')
        return self.after_context.require_current_locked(writer)

    @property
    def after_context(self):
        need(self._token is not None and type(self._cycle) is _Cycle and self._cycle.result is self
             and type(self._cycle.after_context) is AfterContext,
             'PLAYER_LIFE_NEW_READONLY_CONTEXT_NOT_ISSUED')
        return self._cycle.after_context

    def metadata(self):
        return self._service.report(self._cycle)

class Service:
    def __init__(self, broker, *, policy):
        from tools.local_original_session import broker as b, hp_status, npc_player_hit
        need(type(broker) is b.PersistentBroker and type(policy) is Policy
             and type(broker._hp_status) is hp_status.Service
             and type(broker._npc_player_hit) is npc_player_hit.Service,
             'PLAYER_LIFE_REAL_BROKER_HP_NPC_REQUIRED')
        codec.source_ready()
        self.broker, self.policy, self.status = broker, policy, broker._hp_status
        self.hit = broker._npc_player_hit
        self._contexts, self._cycles, self._tokens, self._after_contexts = {}, {}, {}, {}
        self.closed = False

    def token(self, writer):
        selected = self.broker.realm.registry.resolve(writer).selection
        record = self._tokens.get(id(writer))
        if record is None or record[0] is not writer or record[1] is not selected:
            record = (writer, selected, object())
            self._tokens[id(writer)] = record
        return record[2]

    def capture_locked(self, writer):
        need(not self.closed and id(writer) not in self._cycles,
             'PLAYER_LIFE_ONE_EXPLICIT_CYCLE_PER_SELECTION')
        row, snapshot, identities, values = self.hit._current(writer)
        need(snapshot.current_hp == 1, 'PLAYER_LIFE_EXPLICIT_CURRENT_HP_ONE_REQUIRED')
        need(codec.u32(snapshot.target_uid) > 0, 'PLAYER_LIFE_OWN_UID_UINT32_REQUIRED')
        token = self.token(writer)
        context = Context(values[0], values[1], values[2], snapshot, self, writer,
                          identities, values, self.broker.realm.service(writer).snapshot(), token)
        self._contexts[id(writer)] = context
        return context

    def owns_context(self, writer, context):
        need(not self.closed and type(context) is Context and context._service is self
             and context._writer is writer and self._contexts.get(id(writer)) is context
             and self.broker._player_life is self
             and self.token(writer) is context._token, 'PLAYER_LIFE_EXACT_CURRENT_CONTEXT_REQUIRED')

    def current_locked(self, writer, context):
        self.owns_context(writer, context)
        row, snapshot, identities, values = self.hit._current(writer, player_life_context=context)
        expected = (*context._values[:3], snapshot.revision, *context._values[4:])
        need(values == expected and len(identities) == len(context._identities)
             and all(a is b for a, b in zip(identities, context._identities))
             and self.broker.realm.service(writer).snapshot() is context._position,
             'PLAYER_LIFE_SELECTION_NPC_OR_POSITION_CHANGED')
        cycle = self._cycles.get(id(writer))
        need(cycle is None or cycle.context is context and not cycle.terminal,
             'PLAYER_LIFE_TERMINAL_OR_FOREIGN_CYCLE')
        return row

    def current_after_locked(self, writer, context):
        need(not self.closed and type(context) is AfterContext and context._service is self
             and context._writer is writer and self._after_contexts.get(id(writer)) is context
             and self.broker._player_life is self and self.token(writer) is context._token,
             'PLAYER_LIFE_EXACT_AFTER_CONTEXT_REQUIRED')
        cycle = self._cycles.get(id(writer))
        need(cycle is not None and cycle.stage == 'NEW_LIFE' and not cycle.terminal
             and cycle.after_context is context and cycle.status.phase == 'DRAINED',
             'PLAYER_LIFE_CURRENT_NEW_LIFE_REQUIRED')
        row,snapshot,identities,values = self.hit._current(writer)
        need(snapshot is context.snapshot and values == context._values
             and len(identities) == len(context._identities)
             and all(a is b for a,b in zip(identities,context._identities))
             and self.broker.realm.service(writer).snapshot() is context._position,
             'PLAYER_LIFE_AFTER_OBSERVATION_AUTHORITY_CHANGED')
        return row

    def _inputs(self, writer, context, cap, stage):
        # Literal product service and exact issued object, never a duck-typed
        # provider or configurable callback. The product owns typed sampling.
        service = getattr(self.broker, '_player_life_observer', None)
        need(service is not None, 'PLAYER_LIFE_TYPED_OBSERVER_REQUIRED')
        from tools.local_original_session import player_life_observe as typed
        need(type(service) is typed.PlayerLifeObserver and service.broker is self.broker
             and type(cap) is typed.RecoveryInputs and service.inputs is cap,
             'PLAYER_LIFE_LITERAL_ISSUED_RECOVERY_INPUTS_REQUIRED')
        if stage == 'RESTORED':
            self.current_after_locked(writer,context)
        else:
            self.current_locked(writer, context)
        cap.require_current_locked(writer, context)
        cap.require_stage_locked(writer, context, stage=stage)
        codec.u32(cap.f2); codec.u32(cap.f3)
        return cap

    def _stage(self, writer, context, stage):
        service = getattr(self.broker, '_player_life_observer', None)
        need(service is not None, 'PLAYER_LIFE_TYPED_OBSERVER_REQUIRED')
        return self._inputs(writer, context, service.inputs, stage)

    def check_normal_locked(self, writer):
        cycle = self._cycles.get(id(writer))
        need(cycle is None or cycle.stage == 'NEW_LIFE' and not cycle.terminal,
             'PLAYER_LIFE_NORMAL_ACTION_WHILE_DEAD_OR_PENDING')

    def permits_positive(self, writer, snapshot):
        cycle = self._cycles.get(id(writer))
        need(cycle is None or not cycle.terminal and
             (cycle.stage == 'PREPARED' and snapshot is cycle.context.snapshot
              or cycle.stage == 'NEW_LIFE'), 'PLAYER_LIFE_POSITIVE_AUTHORITY_RETIRED')

    def prepare_delivery(self, writer, context, kind, wire):
        self.current_locked(writer, context)
        cycle = self._cycles[id(writer)]
        need(not cycle.deliveries or cycle.deliveries[-1].phase == 'DRAINED',
             'PLAYER_LIFE_PREVIOUS_DELIVERY_NOT_DRAINED')
        delivery = _Delivery(context, kind, wire)
        cycle.deliveries.append(delivery)
        return delivery

    def validate(self, writer, row, wire, delivery, phase):
        need(type(delivery) is _Delivery and delivery.phase == phase
             and delivery.wire is wire and self.current_locked(writer, delivery.context) is row,
             'PLAYER_LIFE_EXACT_DELIVERY_REQUIRED')
        cycle = self._cycles[id(writer)]
        need(cycle.deliveries[-1] is delivery, 'PLAYER_LIFE_HEAD_DELIVERY_REQUIRED')
        expected = {'DEATH': codec.death(delivery.context.target_uid), 'ACK': codec.ack(True)}
        if delivery.kind == 'INIT':
            expected['INIT'] = codec.init(delivery.context.target_uid, *cycle.init_values)
        need(expected.get(delivery.kind) == wire, 'PLAYER_LIFE_CANONICAL_WIRE_REQUIRED')
        return cycle

    def reserve(self, writer, row, wire, delivery):
        self.validate(writer, row, wire, delivery, 'PREPARED')
        delivery.sent, delivery.phase = row['policy_row'].sent, 'RESERVED'

    def attempt(self, writer, row, wire, delivery):
        self.validate(writer, row, wire, delivery, 'RESERVED')
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        delivery.phase, delivery.write_attempted = 'WRITE_ATTEMPTED', True

    def drained(self, writer, row, wire, delivery):
        cycle = self.validate(writer, row, wire, delivery, 'WRITE_ATTEMPTED')
        need(delivery.drain_returned and row['policy_row'].sent == delivery.sent + 1
             and row['policy_row'].pending_opcode is row['policy_row'].drain_started_ns is None,
             'PLAYER_LIFE_EXACT_DRAIN_REQUIRED')
        delivery.phase = 'DRAINED'
        cycle.stage = {'DEATH': 'DEATH_DRAINED', 'ACK': 'ACK_DRAINED', 'INIT': 'INIT_DRAINED'}[delivery.kind]

    async def _send(self, writer, row, context, kind, wire):
        delivery = self.prepare_delivery(writer, context, kind, wire)
        await self.broker._send(writer, row, (wire,), game=True,
            operation_lock=row['operation_lock'], player_life_operation=delivery)

    async def lethal_locked(self, writer, context, inputs):
        need(self.policy.label != NPC_POLICY_LABEL,'PLAYER_LIFE_STATUS_ONLY_POLICY_REQUIRED')
        row = self.current_locked(writer, context)
        need(id(writer) not in self._cycles, 'PLAYER_LIFE_CYCLE_ALREADY_CONSUMED')
        cap = self._inputs(writer, context, inputs, 'PRE')
        cycle = _Cycle(context, cap, (cap.f2,cap.f3))
        self._cycles[id(writer)] = cycle
        return await self._zero_death_locked(writer,row,context,cycle)

    async def lethal_npc_locked(self, writer, attack_context, inputs, *, raw_effect, direction):
        need(self.policy.label == NPC_POLICY_LABEL,'PLAYER_LIFE_NPC_ONLY_POLICY_REQUIRED')
        context = attack_context.life_context
        row = self.current_locked(writer,context)
        need(id(writer) not in self._cycles,'PLAYER_LIFE_CYCLE_ALREADY_CONSUMED')
        cap = self._inputs(writer,context,inputs,'PRE')
        cycle = _Cycle(context,cap,(cap.f2,cap.f3))
        try:
            cycle.npc_attack = self.broker._npc_player_lethal.prepare_locked(writer,attack_context,
                raw_effect=raw_effect,direction=direction,cycle=cycle)
            await self.broker._send(writer,row,(cycle.npc_attack.wire,),game=True,
                operation_lock=row['operation_lock'],npc_player_lethal_operation=cycle.npc_attack)
            need(cycle.npc_attack.attack_transport == 'DRAINED','PLAYER_LIFE_NPC_ATTACK_NOT_DRAINED')
            self._cycles[id(writer)] = cycle
            cycle.deliveries.append(cycle.npc_attack)
            return await self._zero_death_locked(writer,row,context,cycle)
        except BaseException:
            self.terminal(writer)
            raise

    async def _zero_death_locked(self, writer, row, context, cycle):
        try:
            if cycle.npc_attack is not None:
                need(cycle.npc_attack.attack_transport == 'DRAINED',
                     'PLAYER_LIFE_NPC_ATTACK_DRAIN_BEFORE_ZERO_REQUIRED')
            operation = self.status.prepare_player_life(writer, row, context=context, kind='ZERO')
            cycle.status = operation
            await self.broker._send(writer, row, (operation.wire,), game=True,
                operation_lock=row['operation_lock'], status_operation=operation)
            cycle.stage = 'HP_ZERO_DRAINED'
            await self._send(writer, row, context, 'DEATH', codec.death(context.target_uid))
            cycle.result = Result(context, self, cycle)
            return cycle.result
        except BaseException:
            self.terminal(writer)
            raise

    def confirm_death_locked(self, writer, result):
        need(type(result) is Result and result._service is self,
             'PLAYER_LIFE_EXACT_DEATH_RESULT_REQUIRED')
        result.require_current_locked(writer)
        cycle = result._cycle
        need(self._cycles.get(id(writer)) is cycle and cycle.stage == 'DEATH_DRAINED',
             'PLAYER_LIFE_DEATH_DELIVERY_REQUIRED')
        self._stage(writer, result.context, 'DEAD')
        cycle.stage = 'DEATH_OBSERVED'

    async def request_locked(self, writer, payload):
        codec.dead_request(payload)
        cycle = self._cycles.get(id(writer))
        need(cycle is not None and cycle.stage == 'DEATH_OBSERVED'
             and not cycle.request_seen and not cycle.terminal,
             'PLAYER_LIFE_CURRENT_DEAD_REQUEST_ONCE_REQUIRED')
        context = cycle.context
        row = self.current_locked(writer, context)
        self._stage(writer, context, 'DEAD')
        cycle.request_seen = True
        try:
            await self._send(writer, row, context, 'ACK', codec.ack(True))
        except BaseException:
            self.terminal(writer)
            raise
        return ()  # ACK sent here; ordinary route reply loop must not replay it.

    async def recover_locked(self, writer, context, inputs):
        row = self.current_locked(writer, context)
        cycle = self._cycles[id(writer)]
        need(cycle.stage == 'ACK_DRAINED', 'PLAYER_LIFE_ACK_DRAINED_REQUIRED')
        cap = self._inputs(writer, context, inputs, 'RECOVERY')
        need((cap.f2, cap.f3) == cycle.init_values,
             'PLAYER_LIFE_ORIGINAL_INIT_INPUT_CHANGED')
        # Keep PRE opaque values; fresh cap proves their current same owner and
        # resource, rather than replacing an unknown value with zero/default.
        try:
            await self._send(writer, row, context, 'INIT', codec.init(context.target_uid, cap.f2, cap.f3))
            operation = self.status.prepare_player_life(writer, row, context=context, kind='RESTORE')
            cycle.status = operation
            await self.broker._send(writer, row, (operation.wire,), game=True,
                operation_lock=row['operation_lock'], status_operation=operation)
            cycle.stage = 'RESTORE_DRAINED'
            return self._newlife_after_drained_locked(writer,cycle)
        except BaseException:
            self.terminal(writer)
            raise

    def _newlife_after_drained_locked(self,writer,cycle):
        context = cycle.context
        self.current_locked(writer,context)
        need(cycle.stage == 'RESTORE_DRAINED' and cycle.request_seen
             and cycle.status.phase == 'DRAINED'
             and cycle.status.result.after.current_hp == context.snapshot.maximum_hp
             and [d.kind for d in cycle.deliveries] == (
                 ['NPC_ATTACK','DEATH','ACK','INIT'] if self.policy.label == NPC_POLICY_LABEL
                 else ['DEATH','ACK','INIT'])
             and (self.policy.label != NPC_POLICY_LABEL or cycle.npc_attack is not None
                  and cycle.npc_attack.attack_transport == 'DRAINED')
             and all(d.phase == 'DRAINED' for d in cycle.deliveries),
             'PLAYER_LIFE_REQUIRED_RECOVERY_MESSAGES_NOT_DRAINED')
        # This explicit backend policy advances under the same original lock.
        # Original Action, numeric HP and HUD observation are separate product
        # completion evidence, never prerequisites for this local token.
        token = object()
        cycle.new_token, cycle.stage = token, 'NEW_LIFE'
        self._tokens[id(writer)] = (writer,self.broker.realm.registry.resolve(writer).selection,token)
        row,snapshot,identities,values = self.hit._current(writer)
        after = AfterContext(values[0],values[1],values[2],snapshot,self,writer,
                             identities,values,context._position,token)
        cycle.after_context = self._after_contexts[id(writer)] = after
        cycle.result = Result(context,self,cycle,token)
        return cycle.result

    def confirm_recovery_locked(self, writer, result):
        need(type(result) is Result and result._service is self,
             'PLAYER_LIFE_EXACT_RECOVERY_RESULT_REQUIRED')
        result.require_current_locked(writer)
        cycle, context = result._cycle, result.after_context
        need(cycle.stage == 'NEW_LIFE' and not cycle.recovery_observed,
             'PLAYER_LIFE_CURRENT_RECOVERY_OBSERVATION_ONCE_REQUIRED')
        self._stage(writer, context, 'RESTORED')
        context.require_current_locked(writer)
        cycle.recovery_observed = True
        return result

    def terminal(self, writer):
        npc = getattr(self.broker,'_npc_player_lethal',None)
        if npc is not None: npc.terminal(writer)
        cycle = self._cycles.get(id(writer))
        if cycle is not None:
            cycle.terminal = True
            for delivery in cycle.deliveries:
                if delivery.phase != 'DRAINED': delivery.phase = 'TERMINAL'

    def report(self, cycle):
        operation = cycle.status
        return dict(stage=cycle.stage, terminal=cycle.terminal, policy=self.policy.label,
            target_uid=cycle.context.target_uid, source_uid=cycle.context.source_uid,
            npc_attack=('NOT_REQUESTED_BY_EXPLICIT_STATUS_ONLY_POLICY' if cycle.npc_attack is None
                else dict(transport=cycle.npc_attack.attack_transport,damage=1,
                          raw_effect=cycle.npc_attack.raw_effect,client_hit='UNKNOWN')),
            hp=None if operation is None else dict(current=operation.result.after.current_hp,
                maximum=operation.result.after.maximum_hp, revision=operation.result.after.revision,
                transport=operation.phase),
            deliveries=[dict(kind=d.kind, phase=d.phase, write_attempted=d.write_attempted,
                drain_returned=d.drain_returned) for d in cycle.deliveries],
            original_order='UNKNOWN', official_recovery='UNKNOWN', penalty='UNKNOWN',
            additional_local_penalty=0, backend_newlife_gate=NEWLIFE_POLICY,
            delayed_fieldless_request_epoch_identifiable=False,
            client_death='OBSERVED' if cycle.stage in ('DEATH_OBSERVED','ACK_DRAINED','INIT_DRAINED',
                'RESTORE_DRAINED','NEW_LIFE') else 'UNKNOWN', newlife=cycle.stage == 'NEW_LIFE',
            client_recovery='OBSERVED' if cycle.recovery_observed else 'UNKNOWN')

    def release(self, writer):
        self.terminal(writer)
        npc = getattr(self.broker,'_npc_player_lethal',None)
        if npc is not None: npc.release(writer)
        self._contexts.pop(id(writer), None)
        self._cycles.pop(id(writer), None)
        self._tokens.pop(id(writer), None)
        self._after_contexts.pop(id(writer), None)

    def close(self):
        for context in tuple(self._contexts.values()): self.release(context._writer)
        self.closed = True
