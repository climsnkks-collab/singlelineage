"""Explicit selected-player death/recovery, once by default; optional observed repeat.

The existing HP service remains the sole status writer. This service owns local
life capabilities and delivery order, never native calls, action flags or UI.
"""
from dataclasses import dataclass, field
import asyncio
import time
from tools.local_original_session import observe, player_life_codec as codec

need = observe.need
POLICY_LABEL = 'EXPLICIT_LOCAL_OWN_PLAYER_HP1_DEAD_RESTART_MAX_SAME_GRID_V1'
NPC_POLICY_LABEL = 'EXPLICIT_LOCAL_CURRENT_NPC_HP1_DEAD_RESTART_MAX_SAME_GRID_V1'
NEWLIFE_POLICY = 'REQUIRED_MESSAGES_DRAINED_LOCAL_TOKEN'
REPEATED_NEWLIFE_POLICY = 'OBSERVED_RESTORED_MESSAGES_DRAINED_REPEATED_LOCAL_TOKEN'

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
             and self.newlife in (NEWLIFE_POLICY, REPEATED_NEWLIFE_POLICY),
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

    _repeat_session: object = field(default=None, repr=False)
    _repeat_mover: object = field(default=None, repr=False)

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
    recovery_inputs: object = field(default=None, repr=False)
    npc_attack: object = field(default=None, repr=False)
    native_pending: object = field(default=None, repr=False)

@dataclass(slots=True)
class _NativeRequest:
    # Historical strict input + local posted invocation, never a fresh cap.
    requester: object
    cycle: object
    refs: tuple
    sequence: int
    started_ns: int
    window: int
    posted: bool = False

    def retire(self):
        self.requester = self.cycle = None
        self.refs = ()
        self.posted = False

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
        need(cycle.stage == 'NEW_LIFE' and service._existing_token(writer) is self._token,
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
        self._native_requester = None
        self._native_required = False
        self.closed = False

    def token(self, writer):
        selected = self.broker.realm.registry.resolve(writer).selection
        record = self._tokens.get(id(writer))
        if record is None or record[0] is not writer or record[1] is not selected:
            record = (writer, selected, object())
            self._tokens[id(writer)] = record
        return record[2]

    def _existing_token(self, writer):
        """Current validation never issues a replacement token on refusal."""
        selected = self.broker.realm.registry.resolve(writer).selection
        record = self._tokens.get(id(writer))
        need(record is not None and record[0] is writer and record[1] is selected,
             'PLAYER_LIFE_EXISTING_SELECTION_TOKEN_REQUIRED')
        return record[2]

    def capture_locked(self, writer, *, source_uid=None):
        need(not self.closed, 'PLAYER_LIFE_SERVICE_CLOSED')
        previous = self._cycles.get(id(writer))
        need(previous is None or self.policy.newlife == REPEATED_NEWLIFE_POLICY,
             'PLAYER_LIFE_ONE_EXPLICIT_CYCLE_PER_SELECTION')
        row, snapshot, identities, values = self.hit._current(writer, source_uid=source_uid)
        need(snapshot.current_hp == 1, 'PLAYER_LIFE_EXPLICIT_CURRENT_HP_ONE_REQUIRED')
        need(codec.u32(snapshot.target_uid) > 0, 'PLAYER_LIFE_OWN_UID_UINT32_REQUIRED')
        realm = self.broker.realm
        service = realm.service(writer)
        position = service.snapshot()
        registry = realm.registry
        game = registry.resolve(writer)
        selection = game.selection
        token = self.token(writer) if previous is None else self._existing_token(writer)
        repeated = (None, None) if previous is None else self._retire_completed_locked(
            writer, previous, row, snapshot, identities, values, token,
            service, position, registry, game, selection)
        context = Context(values[0], values[1], values[2], snapshot, self, writer,
                          identities, values, position, token,
                          *repeated)
        self._contexts[id(writer)] = context
        return context

    def owns_context(self, writer, context):
        need(not self.closed and type(context) is Context and context._service is self
             and context._writer is writer and self._contexts.get(id(writer)) is context
             and self.broker._player_life is self
             and self._existing_token(writer) is context._token, 'PLAYER_LIFE_EXACT_CURRENT_CONTEXT_REQUIRED')

    def current_locked(self, writer, context):
        self.owns_context(writer, context)
        row, snapshot, identities, values = self.hit._current(writer, source_uid=context.source_uid, player_life_context=context)
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
             and self.broker._player_life is self and self._existing_token(writer) is context._token,
             'PLAYER_LIFE_EXACT_AFTER_CONTEXT_REQUIRED')
        cycle = self._cycles.get(id(writer))
        need(cycle is not None and cycle.stage == 'NEW_LIFE' and not cycle.terminal
             and cycle.after_context is context and cycle.status.phase == 'DRAINED',
             'PLAYER_LIFE_CURRENT_NEW_LIFE_REQUIRED')
        row,snapshot,identities,values = self.hit._current(writer, source_uid=context.source_uid)
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
        need(type(context) is (AfterContext if stage == 'RESTORED' else Context)
             and context._service is self and self.broker._player_life is self
             and not self.closed, 'PLAYER_LIFE_EXACT_CURRENT_CONTEXT_REQUIRED')
        # require_stage includes the original exact Context/AfterContext current
        # validation and receipt TTL check. Do not run that callback three times.
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

    async def _send(self, writer, row, context, kind, wire, *, continuous_context=None):
        delivery = self.prepare_delivery(writer, context, kind, wire)
        await self.broker._send(writer, row, (wire,), game=True,
            operation_lock=row['operation_lock'], player_life_operation=delivery,
            continuous_lethal_context=continuous_context)

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
        continuous_context = attack_context if getattr(attack_context,'continuous_target',None) is not None else None
        context = attack_context.life_context
        row = self.current_locked(writer,context)
        need(id(writer) not in self._cycles,'PLAYER_LIFE_CYCLE_ALREADY_CONSUMED')
        cap = self._inputs(writer,context,inputs,'PRE')
        cycle = _Cycle(context,cap,(cap.f2,cap.f3))
        try:
            cycle.npc_attack = self.broker._npc_player_lethal.prepare_locked(writer,attack_context,
                raw_effect=raw_effect,direction=direction,cycle=cycle)
            await self.broker._send(writer,row,(cycle.npc_attack.wire,),game=True,
                operation_lock=row['operation_lock'],npc_player_lethal_operation=cycle.npc_attack,
                continuous_lethal_context=continuous_context)
            need(cycle.npc_attack.attack_transport == 'DRAINED','PLAYER_LIFE_NPC_ATTACK_NOT_DRAINED')
            self._cycles[id(writer)] = cycle
            cycle.deliveries.append(cycle.npc_attack)
            return await self._zero_death_locked(writer,row,context,cycle,continuous_context=continuous_context)
        except BaseException:
            self.terminal(writer)
            raise

    async def _zero_death_locked(self, writer, row, context, cycle, *, continuous_context=None):
        try:
            if cycle.npc_attack is not None:
                need(cycle.npc_attack.attack_transport == 'DRAINED',
                     'PLAYER_LIFE_NPC_ATTACK_DRAIN_BEFORE_ZERO_REQUIRED')
            operation = self.status.prepare_player_life(writer, row, context=context, kind='ZERO')
            cycle.status = operation
            await self.broker._send(writer, row, (operation.wire,), game=True,
                operation_lock=row['operation_lock'], status_operation=operation,
                continuous_lethal_context=continuous_context)
            cycle.stage = 'HP_ZERO_DRAINED'
            await self._send(writer, row, context, 'DEATH', codec.death(context.target_uid),
                continuous_context=continuous_context)
            cycle.result = Result(context, self, cycle)
            return cycle.result
        except BaseException:
            self.terminal(writer)
            raise

    def confirm_death_locked(self, writer, result, *, dead_observation=None):
        need(type(result) is Result and result._service is self,
             'PLAYER_LIFE_EXACT_DEATH_RESULT_REQUIRED')
        result.require_current_locked(writer)
        cycle = result._cycle
        need(self._cycles.get(id(writer)) is cycle and cycle.stage == 'DEATH_DRAINED',
             'PLAYER_LIFE_DEATH_DELIVERY_REQUIRED')
        if dead_observation is None:
            self._stage(writer, result.context, 'DEAD')
        else:
            cap = self._stage(writer, result.context, 'DEAD')
            record, completed = cap._record, cap._observer._last_completed
            from tools.local_original_session import continuous_lethal
            continuous_lethal.confirm_dead_observation_locked(
                dead_observation,self,writer,result,cap,record,completed)
        cycle.stage = 'DEATH_OBSERVED'

    def bind_native_requester(self, requester):
        from tools.local_original_session import repeated_dead_restart as native
        need(type(requester) is native.RepeatedSourceDeadRestartRequests
             and requester.broker is self.broker and self.broker._player_life is self
             and self.policy.newlife == REPEATED_NEWLIFE_POLICY and not self.closed
             and self._native_requester in (None, requester),
             'PLAYER_LIFE_EXACT_NATIVE_REQUESTER_REQUIRED')
        self._native_requester = requester
        self._native_required = True # Restriction persists after close; no once fallback.

    def _native_refs(self, writer, requester, cycle):
        registry = self.broker.realm.registry
        game = registry._sessions.get(id(writer))
        need(game is not None, 'PLAYER_LIFE_NATIVE_SELECTED_SESSION_REQUIRED')
        return (self.broker, self.broker.realm, registry, game, game.selection,
            game.connection, cycle.context, self._tokens.get(id(writer)),
            cycle.context._token, cycle.status, cycle.status.result.after,
            requester, requester.reader, requester.reader.owner, requester.reader.owner.child,
            requester.consumer, requester.requests, requester.request, requester.row,
            requester.row['peer'], requester.row['peer'].get('connection_id'),
            requester.consumer._bound, requester.consumer._window_bound,
            self.broker._player_life_observer)

    def begin_native_request_locked(self, writer, context, result, requester):
        from tools.local_original_session import repeated_dead_restart as native
        need(type(requester) is native.RepeatedSourceDeadRestartRequests
             and self._native_requester is requester and self._native_required
             and requester.writer is writer and requester.context is context
             and requester.result is result and requester.broker is self.broker
             and requester.state in ('DEAD_PREPARED', 'NOT_REQUESTED', 'RESTORED_ARMED')
             and requester._native_pending is None,
             'PLAYER_LIFE_EXACT_NATIVE_POST_INPUT_REQUIRED')
        cycle = result._cycle
        need(cycle.native_pending is None, 'PLAYER_LIFE_NATIVE_REQUEST_ALREADY_PENDING')
        refs = self._native_refs(writer,requester,cycle)
        # Last original literal DEAD authority check includes source/current and
        # the unchanged 500ms input TTL. No pending is issued on refusal.
        row, cap = self.current_dead_request_locked(writer,context,result,expected_token=context._token)
        actual = self._native_refs(writer,requester,cycle)
        need(row is requester.row and len(actual) == len(refs)
             and all(a is b for a,b in zip(actual,refs)), 'PLAYER_LIFE_NATIVE_INPUT_CHANGED')
        task=asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        pending = _NativeRequest(requester,cycle,refs,requester.request['seq'],
            requester.started_ns,requester.consumer._window_bound[0])
        cycle.native_pending = pending
        return pending

    def _native_pending_refs(self, writer, requester, pending):
        need(type(pending) is _NativeRequest and pending.requester is requester
             and self._native_requester is requester and self._native_required
             and type(pending.cycle) is _Cycle and self._cycles.get(id(writer)) is pending.cycle
             and pending.cycle.native_pending is pending and not pending.cycle.terminal
             and pending.cycle.stage == 'DEATH_OBSERVED' and not pending.cycle.request_seen
             and requester.writer is writer and requester.broker is self.broker
             and requester.result is pending.cycle.result and requester.context is pending.cycle.context
             and requester.state == 'PENDING' and requester._native_pending is pending
             and requester.reader.owner is requester._owner
             and type(requester.request['seq']) is int and requester.request['seq'] == pending.sequence
             and requester.consumer.sequence == pending.sequence
             and requester.started_ns == pending.started_ns
             and 0 <= time.monotonic_ns()-pending.started_ns < 15_000_000_000
             and not self.closed and not self.broker._closing and not self.broker.failure.is_set(),
             'PLAYER_LIFE_CURRENT_NATIVE_INVOCATION_REQUIRED')
        actual=self._native_refs(writer,requester,pending.cycle)
        need(len(actual) == len(pending.refs) and all(a is b for a,b in zip(actual,pending.refs))
             and not actual[3].closed and actual[3].connection is writer,
             'PLAYER_LIFE_NATIVE_INVOCATION_BINDING_CHANGED')
        task=asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()

    def native_posted_locked(self, writer, requester, pending):
        self._native_pending_refs(writer,requester,pending)
        need(not pending.posted, 'PLAYER_LIFE_NATIVE_POST_ONCE_REQUIRED')
        pending.posted = True

    def retire_native_request(self, requester):
        # No callbacks/row acquisition: valid from failure/close/cancellation.
        for cycle in self._cycles.values():
            pending=cycle.native_pending
            if type(pending) is _NativeRequest and pending.requester is requester:
                cycle.native_pending=None
                pending.retire()
        requester._native_pending=None

    def unbind_native_requester(self, requester):
        self.retire_native_request(requester)
        if self._native_requester is requester: self._native_requester=None

    def _consume_native_request_locked(self, writer, cycle):
        pending=cycle.native_pending
        requester=self._native_requester
        self._native_pending_refs(writer,requester,pending)
        need(pending.posted, 'PLAYER_LIFE_NATIVE_POST_SUCCESS_REQUIRED')
        current=requester._current_locked()
        need(requester.consumer._window(current) == pending.window,
             'PLAYER_LIFE_NATIVE_WINDOW_CHANGED')
        requester._check_files()
        row=self.current_locked(writer,cycle.context)
        need(row is requester.row and self.status.current_player_life(writer,cycle.context) is cycle.status.result.after
             and cycle.status.result.after.current_hp == 0 and cycle.status.phase == 'DRAINED'
             and all(d.phase == 'DRAINED' for d in cycle.deliveries),
             'PLAYER_LIFE_CURRENT_NATIVE_DEAD_BACKEND_REQUIRED')
        # All fallible callbacks precede the final pure identity/cancel check.
        self._native_pending_refs(writer,requester,pending)
        cycle.native_pending=None;requester._native_pending=None;pending.retire()
        return row

    async def request_locked(self, writer, payload):
        codec.dead_request(payload)
        cycle = self._cycles.get(id(writer))
        need(cycle is not None and cycle.stage == 'DEATH_OBSERVED'
             and not cycle.request_seen and not cycle.terminal,
             'PLAYER_LIFE_CURRENT_DEAD_REQUEST_ONCE_REQUIRED')
        context = cycle.context
        if self._native_required:
            try: row = self._consume_native_request_locked(writer,cycle)
            except BaseException:
                self.terminal(writer)
                raise
        else:
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
        owner = getattr(self.status, '_resource_owner', None)
        if owner is not None:
            baseline = owner.new_life_baseline_locked(writer, self, cycle)
            self.hit.adopt_resource_new_life_locked(writer, self, cycle, baseline)
        row,snapshot,identities,values = self.hit._current(writer, source_uid=context.source_uid)
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
        cap = self._stage(writer, context, 'RESTORED')
        context.require_current_locked(writer)
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        cycle.recovery_inputs = cap
        cycle.recovery_observed = True
        return result

    def completed_recovery_locked(self, writer, result):
        """Read current RESTORED proof immediately after recovery, before HP changes.

        The returned issued cap is historical after a positive hit; it cannot
        authorize a later PRE or a Native rearm after the AfterContext expires.
        """
        from tools.local_original_session import player_life_observe as observed
        need(type(result) is Result and result._service is self,
             'PLAYER_LIFE_EXACT_RECOVERY_RESULT_REQUIRED')
        registry = self.broker.realm.registry
        game = registry.resolve(writer)
        token_record = self._tokens.get(id(writer))
        row = result.require_current_locked(writer)
        cycle, token = result._cycle, result._token
        need(token is not None and cycle.stage == 'NEW_LIFE' and cycle.recovery_observed
             and cycle.request_seen and cycle.new_token is token
             and cycle.status.phase == 'DRAINED'
             and cycle.status.result.after.current_hp == cycle.context.snapshot.maximum_hp
             and all(d.phase == 'DRAINED' for d in cycle.deliveries),
             'PLAYER_LIFE_COMPLETE_RECOVERY_REQUIRED')
        observer = self.broker._player_life_observer
        need(type(observer) is observed.PlayerLifeObserver,
             'PLAYER_LIFE_LITERAL_ISSUED_RECOVERY_INPUTS_REQUIRED')
        cap = self._stage(writer, result.after_context, 'RESTORED')
        need(cap is cycle.recovery_inputs and any(record is cap._record for record in observer._issued),
             'PLAYER_LIFE_EXACT_COMPLETED_RECOVERY_CAP_REQUIRED')
        need(result.require_current_locked(writer) is row
             and self._cycles.get(id(writer)) is cycle and cycle.result is result
             and cycle.recovery_observed and cycle.new_token is token
             and observer.inputs is cap and cycle.recovery_inputs is cap
             and cycle.status.phase == 'DRAINED' and all(d.phase == 'DRAINED' for d in cycle.deliveries)
             and self._tokens.get(id(writer)) is token_record and token_record is not None
             and token_record[0] is writer and token_record[1] is game.selection and token_record[2] is token
             and self.broker.realm.registry is registry and registry._sessions.get(id(writer)) is game
             and game.connection is writer and not game.closed,
             'PLAYER_LIFE_COMPLETED_RECOVERY_AUTHORITY_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        return row, token, cap

    def current_dead_request_locked(self, writer, context, result, *, expected_token):
        """Read a fresh DEAD cap before publish; ACK polling keeps its own guard."""
        need(type(context) is Context and type(result) is Result
             and result._service is self and result.context is context and result._token is None,
             'PLAYER_LIFE_EXACT_UNTOKENED_DEATH_RESULT_REQUIRED')
        registry = self.broker.realm.registry
        game = registry.resolve(writer)
        token_record = self._tokens.get(id(writer))
        row = result.require_current_locked(writer)
        cycle = result._cycle
        need(cycle.stage == 'DEATH_OBSERVED' and not cycle.request_seen
             and cycle.new_token is None and context._token is expected_token
             and self._existing_token(writer) is expected_token
             and cycle.status.phase == 'DRAINED' and cycle.status.result.after.current_hp == 0
             and cycle.status.writer is writer and cycle.status.row is row
             and all(d.phase == 'DRAINED' for d in cycle.deliveries)
             and (self.policy.label != NPC_POLICY_LABEL or cycle.npc_attack is not None
                  and cycle.npc_attack.attack_transport == 'DRAINED'),
             'PLAYER_LIFE_CURRENT_DEAD_PUBLISH_REQUIRED')
        cap = self._stage(writer, context, 'DEAD')
        need(result.require_current_locked(writer) is row
             and self._cycles.get(id(writer)) is cycle and cycle.result is result
             and cycle.stage == 'DEATH_OBSERVED' and not cycle.request_seen
             and self._existing_token(writer) is expected_token and context._token is expected_token
             and self.broker._player_life_observer.inputs is cap
             and self._cycles.get(id(writer)) is cycle and cycle.result is result
             and cycle.stage == 'DEATH_OBSERVED' and not cycle.request_seen and not cycle.terminal
             and cycle.status.phase == 'DRAINED' and all(d.phase == 'DRAINED' for d in cycle.deliveries)
             and self._tokens.get(id(writer)) is token_record and token_record is not None
             and token_record[0] is writer and token_record[1] is game.selection
             and token_record[2] is expected_token
             and self.broker.realm.registry is registry and registry._sessions.get(id(writer)) is game
             and game.connection is writer and not game.closed,
             'PLAYER_LIFE_DEAD_PUBLISH_AUTHORITY_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        return row, cap

    def _retire_completed_locked(self, writer, cycle, row, snapshot, identities, values, token,
                                 service, position, registry, game, selection):
        """Retire only a source-observed complete life; preserve its actual token.

        Historical RESTORED inputs authorize retirement, never the next PRE.
        No old cycle/context chain is retained in the new source-issued Context.
        """
        from tools.local_original_session import player_life_observe as observed
        realm, operation_lock = self.broker.realm, row['operation_lock']
        need(self.policy.newlife == REPEATED_NEWLIFE_POLICY
             and self._cycles.get(id(writer)) is cycle and not cycle.terminal
             and cycle.stage == 'NEW_LIFE' and cycle.recovery_observed
             and cycle.new_token is token and cycle.result._token is token
             and cycle.after_context is self._after_contexts.get(id(writer))
             and self._contexts.get(id(writer)) is cycle.context
             and cycle.status.phase == 'DRAINED'
             and cycle.status.result.after.current_hp == cycle.context.snapshot.maximum_hp
             and cycle.status.writer is writer and cycle.status.row is row
             and row['operation_lock'].locked() and cycle.request_seen
             and all(d.phase == 'DRAINED' for d in cycle.deliveries),
             'PLAYER_LIFE_REPEAT_COMPLETE_OBSERVED_CYCLE_REQUIRED')
        after = cycle.after_context
        expected = (*after._values[:3], snapshot.revision, *after._values[4:])
        need(after._token is token and values == expected
             and len(identities) == len(after._identities)
             and all(a is b for a,b in zip(identities,after._identities)),
             'PLAYER_LIFE_REPEAT_SELECTION_OR_NPC_CHANGED')
        observer = self.broker._player_life_observer
        need(type(observer) is observed.PlayerLifeObserver,
             'PLAYER_LIFE_REPEAT_ORIGINAL_OBSERVER_REQUIRED')
        cap = observed.PlayerLifeObserver.check_completed_cycle_locked(observer, writer, self, cycle)
        restore, deliveries = cycle.status, tuple(cycle.deliveries)
        restore_result = restore.result
        old_context, completed_result = cycle.context, cycle.result
        token_record = self._tokens.get(id(writer))
        before, issued_list, issued, cap_record = observer.before, observer._issued, tuple(observer._issued), cap._record
        npc = getattr(self.broker, '_npc_player_lethal', None)
        repeat = (None, None)
        if self.policy.label == NPC_POLICY_LABEL:
            from tools.local_original_session import npc_player_lethal
            need(type(npc) is npc_player_lethal.Service,
                 'PLAYER_LIFE_REPEAT_ORIGINAL_NPC_SERVICE_REQUIRED')
            repeat = npc_player_lethal.Service.check_completed_cycle_locked(npc, writer, cycle)
            npc_context, npc_operation = npc._contexts[id(writer)], npc._operations[id(writer)]
            npc_plan = npc_context._approach._plan
        # Original source callback and full current borrow must be the final
        # validation; cancellation or rebinding cannot partially retire owners.
        self.broker.source_guard()
        actual = self.hit._current(writer, source_uid=cycle.context.source_uid)
        need(actual[0] is row and actual[1] is snapshot and actual[3] == values
             and len(actual[2]) == len(identities)
             and all(a is b for a,b in zip(actual[2],identities))
             and self._existing_token(writer) is token and self._cycles.get(id(writer)) is cycle
             and not self.closed and self.broker._player_life is self
             and self.broker._npc_player_hit is self.hit and self.broker._hp_status is self.status
             and self._contexts.get(id(writer)) is cycle.context
             and self._after_contexts.get(id(writer)) is after
             and cycle.status is restore and restore.phase == 'DRAINED'
             and len(cycle.deliveries) == len(deliveries)
             and all(a is b and a.phase == 'DRAINED' for a,b in zip(cycle.deliveries,deliveries)),
             'PLAYER_LIFE_REPEAT_FINAL_AUTHORITY_CHANGED')
        need(observed.PlayerLifeObserver.check_completed_cycle_locked(observer, writer, self, cycle) is cap,
             'PLAYER_LIFE_REPEAT_OBSERVER_CHANGED')
        if self.policy.label == NPC_POLICY_LABEL:
            need(npc_player_lethal.Service.check_completed_cycle_locked(npc, writer,cycle) == repeat,
                 'PLAYER_LIFE_REPEAT_NPC_CHANGED')
        # No callback is allowed after this final snapshot producer. Registry,
        # token, observer and NPC state are then compared through captured refs.
        final_position = service.snapshot()
        need(type(realm._movement) is dict and type(registry._sessions) is dict,
             'PLAYER_LIFE_REPEAT_FINAL_REGISTRY_TYPE_CHANGED')
        movement_row = realm._movement.get(id(writer))
        need(self.broker.realm is realm and final_position is position and service._position is position
             and realm.registry is registry and registry._sessions.get(id(writer)) is game
             and game.connection is writer and not game.closed and game.selection is selection
             and movement_row is not None and movement_row[0] is writer and movement_row[1] is service
             and self._tokens.get(id(writer)) is token_record
             and token_record[0] is writer and token_record[1] is selection and token_record[2] is token
             and self._cycles.get(id(writer)) is cycle and cycle.stage == 'NEW_LIFE'
             and not cycle.terminal and cycle.recovery_observed and cycle.new_token is token
             and cycle.result is completed_result and completed_result._token is token
             and cycle.context is old_context and self._contexts.get(id(writer)) is old_context
             and self._after_contexts.get(id(writer)) is after and cycle.after_context is after
             and cycle.status is restore and restore.phase == 'DRAINED' and restore.result is restore_result
             and restore.writer is writer and restore.row is row
             and row['operation_lock'] is operation_lock and operation_lock.locked()
             and len(cycle.deliveries) == len(deliveries)
             and all(a is b and a.phase == 'DRAINED' for a,b in zip(cycle.deliveries,deliveries))
             and self.broker._player_life_observer is observer and observer.inputs is cap
             and cycle.recovery_inputs is cap and observer.before is before
             and observer._prepared is None and not observer._preparing
             and observer._issued is issued_list and len(observer._issued) == len(issued)
             and all(a is b for a,b in zip(observer._issued,issued))
             and cap._record is cap_record and cap._context is after and cap._writer is writer
             and cap._observer is observer and cap._stage == 'RESTORED'
             and (cap._f2,cap._f3) == cycle.init_values == observer._baseline
             and observer._pending_identity is cap_record[1]
             and not self.closed and self.broker._player_life is self
             and self.broker._npc_player_hit is self.hit and self.broker._hp_status is self.status,
             'PLAYER_LIFE_REPEAT_FINAL_REFERENCES_CHANGED')
        if self.policy.label == NPC_POLICY_LABEL:
            bound = self.broker.realm._npc_motion.get(id(writer))
            need(self.broker._npc_player_lethal is npc and not npc.closed
                 and npc._contexts.get(id(writer)) is npc_context
                 and npc._operations.get(id(writer)) is npc_operation
                 and cycle.npc_attack is npc_operation and npc_operation.cycle is cycle
                 and npc_operation.context is npc_context and npc_context._approach._plan is npc_plan
                 and npc_operation.phase == npc_operation.attack_transport == 'DRAINED'
                 and npc_operation.write_attempted and npc_operation.drain_returned
                 and npc_plan.session is repeat[0] and npc_plan.mover is repeat[1]
                 and not npc_plan.session._closed and not npc_plan.session.factory._closed
                 and npc_plan.session.factory._session is npc_plan.session
                 and bound is not None and bound[0] is writer and bound[1] is repeat[1],
                 'PLAYER_LIFE_REPEAT_FINAL_NPC_REFERENCES_CHANGED')
        task = asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        # All mutations below are synchronous, callback-free dictionary/field
        # retirement. Existing last-step/query cadence and current token stay.
        observed.PlayerLifeObserver._retire_completed_fields(observer)
        if self.policy.label == NPC_POLICY_LABEL:
            npc_player_lethal.Service._retire_completed_fields(npc, writer)
        self._contexts.pop(id(writer)); self._after_contexts.pop(id(writer))
        self._cycles.pop(id(writer))
        cycle.recovery_inputs = None
        return repeat

    def terminal(self, writer):
        npc = getattr(self.broker,'_npc_player_lethal',None)
        if npc is not None: npc.terminal(writer)
        cycle = self._cycles.get(id(writer))
        if cycle is not None:
            pending=cycle.native_pending
            if type(pending) is _NativeRequest:
                requester=pending.requester
                cycle.native_pending=None
                if requester is not None: requester._native_pending=None
                pending.retire()
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
            additional_local_penalty=0, backend_newlife_gate=self.policy.newlife,
            delayed_fieldless_request_epoch_identifiable=False,
            client_death='OBSERVED' if cycle.stage in ('DEATH_OBSERVED','ACK_DRAINED','INIT_DRAINED',
                'RESTORE_DRAINED','NEW_LIFE') else 'UNKNOWN', newlife=cycle.stage == 'NEW_LIFE',
            client_recovery='OBSERVED' if cycle.recovery_observed else 'UNKNOWN')

    def release(self, writer):
        continuous=getattr(self.broker,'_npc_continuous',None)
        if continuous is not None:
            from tools.local_original_session.npc_continuous_retaliation import Controller
            need(type(continuous) is Controller,'PLAYER_LIFE_REGISTERED_CONTINUOUS_REQUIRED')
            continuous.release_player(self,writer)
        self.terminal(writer)
        npc = getattr(self.broker,'_npc_player_lethal',None)
        if npc is not None: npc.release(writer)
        self._contexts.pop(id(writer), None)
        self._cycles.pop(id(writer), None)
        self._tokens.pop(id(writer), None)
        self._after_contexts.pop(id(writer), None)

    def close(self):
        for context in tuple(self._contexts.values()): self.release(context._writer)
        self._native_requester=None
        self.closed = True
