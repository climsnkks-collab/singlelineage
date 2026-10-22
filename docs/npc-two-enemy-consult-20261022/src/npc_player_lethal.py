"""Explicit local NPC hit1 at ownHP1, with one existing HP/death authority.

The existing approach/contact query is inherited unchanged. Raw effect is not
damage; transport drain is not a client AttackAction/Next receipt.
"""
from dataclasses import dataclass, field
import struct
import asyncio
import time
from tools.local_original_session import attack, attack_feedback, npc_approach_hit as approach, npc_player_hit, player_life, movement, npc_motion

need = attack.need

@dataclass(frozen=True, slots=True)
class Context:
    life_context: object = field(repr=False)
    _service: object = field(repr=False)
    _writer: object = field(repr=False)
    _approach: object = field(repr=False)
    continuous_target: object = field(default=None,repr=False)

    @property
    def snapshot(self): return self.life_context.snapshot
    @property
    def source_uid(self): return self.life_context.source_uid
    @property
    def target_uid(self): return self.life_context.target_uid

@dataclass(slots=True)
class _Attack:
    context: Context = field(repr=False)
    wire: bytes = field(repr=False)
    raw_effect: int
    direction: int
    cycle: object = field(repr=False)
    kind: str = 'NPC_ATTACK'
    phase: str = 'ATTACK'
    attack_transport: str = 'PREPARED'
    sent: int | None = None
    write_attempted: bool = False
    drain_returned: bool = False

class Service:
    def __init__(self, broker):
        from tools.local_original_session import broker as bm
        need(type(broker) is bm.PersistentBroker and type(broker._player_life) is player_life.Service
             and broker._player_life.policy.label == player_life.NPC_POLICY_LABEL,
             'NPC_LETHAL_EXACT_REAL_LIFE_SERVICE_REQUIRED')
        self.broker, self.life, self.hit = broker, broker._player_life, broker._npc_player_hit
        expected_hit = (npc_player_hit.REPEATED_POLICY
                        if self.life.policy.newlife == player_life.REPEATED_NEWLIFE_POLICY
                        else npc_player_hit.POLICY)
        need(type(self.hit) is npc_player_hit.Service and self.hit.policy == expected_hit,
             'NPC_LETHAL_CURRENT_NPC_SOURCE_REQUIRED')
        self._contexts, self._operations = {}, {}
        self.closed = False

    def current(self, writer, *, source_uid=None):
        need(not self.closed and self.broker._npc_player_lethal is self
             and self.broker._player_life is self.life and self.broker._npc_player_hit is self.hit,
             'NPC_LETHAL_CURRENT_SERVICE_REQUIRED')
        return self.hit._current(writer, source_uid=source_uid)

    def capture_locked(self, writer, *, life_context, arrival):
        from tools.local_original_session import npc_approach_hit
        need(type(life_context) is player_life.Context and type(arrival) is npc_approach_hit.Arrival
             and type(arrival._plan) is Plan and arrival._plan.service is self
             and id(writer) not in self._contexts and id(writer) not in self._operations,
             'NPC_LETHAL_ONCE_TYPED_CONTEXT_REQUIRED')
        continuous_target=arrival._plan._continuous_authority
        self.life.current_locked(writer, life_context)
        row, snapshot, _, _ = self.current(writer, source_uid=life_context.source_uid)
        need(snapshot is life_context.snapshot and snapshot.current_hp == 1,
             'NPC_LETHAL_SAME_CURRENT_HP_ONE_REQUIRED')
        arrival.ready_locked(writer)
        if continuous_target is not None:
            continuous_target.issuer.lethal_current_locked(continuous_target,life_context)
        context = Context(life_context, self, writer, arrival,continuous_target)
        self._contexts[id(writer)] = context
        arrival.claim_context_locked(writer, context)
        return context

    def validate_locked(self, writer, context):
        need(type(context) is Context and context._service is self and context._writer is writer
             and self._contexts.get(id(writer)) is context,
             'NPC_LETHAL_EXACT_CONTEXT_REQUIRED')
        if context.continuous_target is not None:
            context.continuous_target.issuer.lethal_current_locked(context.continuous_target,context.life_context,context)
        self.life.current_locked(writer, context.life_context)
        row, snapshot, _, _ = self.current(writer, source_uid=context.source_uid)
        need(snapshot is context.snapshot and snapshot.current_hp == 1,
             'NPC_LETHAL_CURRENT_HP_SNAPSHOT_CHANGED')
        context._approach.require_current_locked(writer, context)
        return row

    def operation_for(self, writer): return self._operations.get(id(writer))

    def prepare_locked(self, writer, context, *, raw_effect, direction, cycle):
        self.validate_locked(writer, context)
        need(id(writer) not in self._operations, 'NPC_LETHAL_ATTACK_ONCE_REQUIRED')
        npc_player_hit.source_ready()
        attack._int32(raw_effect)
        need(raw_effect > 0 and type(direction) is int and 0 <= direction <= 8,
             'NPC_LETHAL_EXPLICIT_EFFECT_DIRECTION_REQUIRED')
        context._approach.require_direction_locked(writer, direction)
        body=attack.pb.encode_message((attack._field(1,1),attack._field(2,context.source_uid),
            attack._field(3,context.target_uid),attack._field(4,raw_effect),attack._field(5,direction),
            attack.pb.encode_bool(13,False)))
        wire=struct.pack('<HH',len(body)+6,attack_feedback.OPCODE)+body+b'\0\0'
        parsed=attack_feedback.validate_frame(wire,policy=attack_feedback.POLICY)
        need(parsed.attacker_uid==context.source_uid and parsed.target_uid==context.target_uid
             and parsed.attacker_uid!=parsed.target_uid and parsed.self_action is False,
             'NPC_LETHAL_CANONICAL_NPC_OWN_ROLES_REQUIRED')
        need(type(cycle) is player_life._Cycle and cycle.context is context.life_context
             and cycle.stage=='PREPARED' and not cycle.terminal
             and id(writer) not in self.life._cycles,'NPC_LETHAL_UNCOMMITTED_LIFE_CYCLE_REQUIRED')
        operation=_Attack(context,wire,raw_effect,direction,cycle)
        self._operations[id(writer)]=operation
        context._approach.bind_body_locked(writer,context,operation,wire,parsed)
        return operation

    def validate_attack(self, writer, operation):
        need(type(operation) is _Attack and self.operation_for(writer) is operation
             and operation.phase=='ATTACK' and operation.attack_transport in ('PREPARED','RESERVED','WRITE_ATTEMPTED'),
             'NPC_LETHAL_EXACT_ATTACK_OPERATION_REQUIRED')
        self.validate_locked(writer,operation.context)
        parsed=attack_feedback.validate_frame(operation.wire,policy=attack_feedback.POLICY)
        need(parsed.attacker_uid==operation.context.source_uid and parsed.target_uid==operation.context.target_uid
             and parsed.raw_effect==operation.raw_effect and parsed.direction==operation.direction
             and parsed.self_action is False,'NPC_LETHAL_CURRENT_CANONICAL_WIRE_REQUIRED')
        return operation

    def validate(self, writer, row, wire, operation, phase):
        self.validate_attack(writer,operation)
        need(operation.wire is wire and operation.attack_transport==phase
             and self.life.current_locked(writer,operation.context.life_context) is row
             and id(writer) not in self.life._cycles and not operation.cycle.terminal,
             'NPC_LETHAL_CURRENT_DELIVERY_REQUIRED')

    def reserve(self, writer, row, wire, operation):
        self.validate(writer,row,wire,operation,'PREPARED')
        need(operation.attack_transport=='PREPARED','NPC_LETHAL_RESERVE_ONCE_REQUIRED')
        operation.sent=row['policy_row'].sent
        operation.attack_transport='RESERVED'

    def attempt(self, writer, row, wire, operation):
        self.validate(writer,row,wire,operation,'RESERVED')
        need(operation.attack_transport=='RESERVED','NPC_LETHAL_WRITE_ONCE_REQUIRED')
        task=asyncio.current_task()
        if task is not None and task.cancelling():raise asyncio.CancelledError()
        operation.context._approach.consume_attack_locked(writer,operation.context,operation,operation.wire)
        if task is not None and task.cancelling():raise asyncio.CancelledError()
        self.validate_attack(writer,operation)
        operation.write_attempted=True
        operation.attack_transport='WRITE_ATTEMPTED'

    def drained(self, writer, row, wire, operation):
        self.validate(writer,row,wire,operation,'WRITE_ATTEMPTED')
        need(operation.drain_returned and row['policy_row'].sent==operation.sent+1
             and row['policy_row'].pending_opcode is row['policy_row'].drain_started_ns is None,
             'NPC_LETHAL_EXACT_ATTACK_DRAIN_REQUIRED')
        operation.attack_transport=operation.phase='DRAINED'

    def terminal(self, writer):
        operation=self.operation_for(writer)
        if operation is not None:
            # An attempted/ambiguous send retires this exact pending cycle;
            # the ordinary alive binding remains unchanged before this point.
            if id(writer) not in self.life._cycles:
                self.life._cycles[id(writer)]=operation.cycle
            operation.cycle.terminal=True
            if operation.attack_transport!='DRAINED':
                operation.phase=operation.attack_transport='TERMINAL'

    def release(self, writer):
        self.terminal(writer)
        self._contexts.pop(id(writer),None);self._operations.pop(id(writer),None)

    def check_completed_cycle_locked(self, writer, cycle):
        need(self.life.policy.newlife == player_life.REPEATED_NEWLIFE_POLICY
             and self.life._cycles.get(id(writer)) is cycle and cycle.recovery_observed
             and not cycle.terminal and cycle.stage == 'NEW_LIFE'
             and self.broker._npc_player_lethal is self and not self.closed,
             'NPC_LETHAL_REPEAT_COMPLETED_CYCLE_REQUIRED')
        operation = self.operation_for(writer)
        context = self._contexts.get(id(writer))
        need(type(operation) is _Attack and operation is cycle.npc_attack
             and operation.cycle is cycle and operation.context is context
             and type(context) is Context and context.life_context is cycle.context
             and context._writer is writer and context._service is self
             and operation.phase == operation.attack_transport == 'DRAINED'
             and operation.write_attempted and operation.drain_returned
             and type(context._approach._plan) is Plan,
             'NPC_LETHAL_REPEAT_EXACT_DRAINED_OPERATION_REQUIRED')
        plan = context._approach._plan
        need(plan.session.broker is self.broker and not plan.session._closed
             and plan.session.factory._session is plan.session and not plan.session.factory._closed
             and attack.npc_mover(self.broker.realm, writer, context.source_uid) is plan.mover,
             'NPC_LETHAL_REPEAT_SAME_MOVER_REQUIRED')
        return plan.session, plan.mover

    def _retire_completed_fields(self, writer):
        # release() terminalizes/reinserts cycles and is deliberately unused.
        context = self._contexts.pop(id(writer))
        self._operations.pop(id(writer))
        approach.Plan.close(context._approach._plan)  # Literal field cleanup, no bound callback.

class Plan(approach.Plan):
    def __init__(self, session, *, goal, policy=approach.LOCAL_ADJACENT_SOURCE_STEP_CONTACT,
                 life_context=None, continuous_target=None):
        need(policy==approach.LOCAL_ADJACENT_SOURCE_STEP_CONTACT,'NPC_LETHAL_STATIC_CONTACT_POLICY_REQUIRED')
        super().__init__(session,goal=goal,policy=policy)
        self._repeat_context = life_context
        self._continuous_target = continuous_target
        self._continuous_authority = continuous_target
        self._repeat_stationary = False
        self._repeat_arrival_claimed = False

    def _bind(self, writer):
        if self._continuous_authority is not None:
            from tools.local_original_session import npc_continuous_retaliation as continuous
            target=self._continuous_authority;context=self._repeat_context
            need(self._continuous_target is target,'NPC_LETHAL_CONTINUOUS_ANCHOR_CHANGED')
            need(type(target) is continuous.TargetReceipt and target.writer is writer
                 and type(context) is player_life.Context and self.phase=='NEW' and self.writer is None,
                 'NPC_LETHAL_LITERAL_CONTINUOUS_TARGET_REQUIRED')
            target.issuer.current_locked(target)
            self.session.broker._player_life.current_locked(writer,context)
            service,row,identities,values,position,mover=self._view(writer)
            current=movement.authority.unpack_grid(mover.state.packed)
            approach.melee_geometry(current,(position.word0,position.word1))
            need(self.goal==current and mover is target.mover and context.snapshot.current_hp==1,
                 'NPC_LETHAL_CONTINUOUS_CURRENT_GOAL_REQUIRED')
            self.session.submit_goal(goal=self.goal)
            self.writer,self.row,self.service,self.position,self.mover=writer,row,service,position,mover
            self.before,self.identities,self.values=mover.state,identities,values
            self.factory,self.configuration=self.session.factory,self.session.factory.config
            self.event_start,self.sent_before=self.session.broker.policy.events,row['policy_row'].sent
            self._repeat_stationary=True;self.phase='BOUND'
            return
        if self._repeat_context is None:
            return super()._bind(writer)
        context, life = self._repeat_context, self.session.broker._player_life
        need(type(context) is player_life.Context and life.policy.newlife == player_life.REPEATED_NEWLIFE_POLICY
             and context._repeat_session is self.session and context._repeat_mover is not None
             and self.phase == 'NEW' and self.writer is None and self.goal is not self.session._goal,
             'NPC_LETHAL_REPEAT_SOURCE_ISSUED_CONTEXT_REQUIRED')
        life.current_locked(writer, context)
        service,row,identities,values,position,mover = self._view(writer)
        need(mover is context._repeat_mover, 'NPC_LETHAL_REPEAT_CURRENT_MOVER_REQUIRED')
        current = movement.authority.unpack_grid(mover.state.packed)
        player = (position.word0, position.word1)
        final_distance,_ = approach.melee_geometry(self.goal,player)
        distance = max(abs(a-b) for a,b in zip(current,self.goal))
        need(distance in (0,1) and (distance == 0 or
             max(abs(a-b) for a,b in zip(current,player)) > final_distance),
             'NPC_LETHAL_REPEAT_EXPLICIT_ADJACENT_GOAL_REQUIRED')
        need(self.phase == 'NEW' and self.writer is None and self._repeat_context is context,
             'NPC_LETHAL_REPEAT_PLAN_CHANGED_DURING_BIND')
        self.session.submit_goal(goal=self.goal,player_life_context=context)
        self.writer,self.row,self.service,self.position,self.mover = writer,row,service,position,mover
        self.before,self.identities,self.values = mover.state,identities,values
        self.factory,self.configuration = self.session.factory,self.session.factory.config
        self.event_start,self.sent_before = self.session.broker.policy.events,row['policy_row'].sent
        self._repeat_stationary = distance == 0
        self.phase = 'BOUND'

    async def arrive_current_goal(self, writer, runtime, observer, *, now_ns, monitor=None):
        """New repeated life at an existing adjacent tile: real poll, fresh pose.

        No old Arrival, old motion receipt or fabricated AT_GOAL is accepted.
        Existing nonzero approach still uses original sample/tick/sample path.
        """
        from tools.local_original_session import launcher, npc_observe
        need(not self._repeat_arrival_claimed and self._repeat_context is not None
             and type(runtime) is launcher.ProductFeatures and runtime.npc_session is self.session
             and type(observer) is npc_observe.NpcObserver
             and observer.targets.reader is self.session.factory.reader
             and observer.targets.broker is self.session.broker,
             'NPC_LETHAL_REPEAT_REAL_PRODUCT_AND_OBSERVER_REQUIRED')
        rows = [row for rows in self.session.broker._claims.values() for row in rows
                if row['writer'] is writer]
        need(len(rows) == 1 and not rows[0]['operation_lock'].locked(),
             'NPC_LETHAL_REPEAT_OUTSIDE_ROW_LOCK_REQUIRED')
        async with self.session.broker._row_operation(writer,rows[0]):
            if self.phase == 'NEW': self._bind(writer)
            need(self._repeat_stationary and self.arrival is None,
                 'NPC_LETHAL_REPEAT_CURRENT_GOAL_ONCE_REQUIRED')
            self._check(writer)
        slot = runtime._npc_poll_monitor if monitor is None else monitor
        need(type(now_ns) is int and now_ns >= 0 and now_ns/1e9 >= slot.next_memory,
             'NPC_LETHAL_REPEAT_ORIGINAL_QUERY_CADENCE_REQUIRED')
        self._repeat_arrival_claimed = True
        slot.next_memory = max(slot.next_memory, now_ns/1e9 + .5, time.monotonic()+.5)
        outcome = await runtime.poll(slot)
        need(outcome.get('npc',{}).get('status') == 'AT_GOAL'
             and outcome['npc'].get('typed_slot_reserved') is False,
             'NPC_LETHAL_REPEAT_ORIGINAL_AT_GOAL_REQUIRED')
        async with self.session.broker._row_operation(writer,self.row):
            state = self._check(writer)
            need(state is self.before and self.session._goal is self.goal,
                 'NPC_LETHAL_REPEAT_STATIONARY_STATE_CHANGED')
            try:
                sample = await approach._SAMPLE(observer,writer,state.uid,now_ns=now_ns)
            finally:
                slot.next_memory = max(slot.next_memory, time.monotonic()+.5)
            self.last_motion_sample_ns = now_ns
            need(self._check(writer) is state and self.session._goal is self.goal,
                 'NPC_LETHAL_REPEAT_POSE_STATE_CHANGED')
            need(sample.get('status') == 'OBSERVED' and sample.get('uid') == state.uid
                 and sample.get('map_id') == state.map_id and sample.get('coordinates_match') is True
                 and tuple(sample.get('server_grid') or ()) == self.goal
                 and tuple(sample.get('client_grid') or ()) == self.goal
                 and sample.get('npc_idle') is True and sample.get('source_contract_valid') is True
                 and sample.get('source_owner_revalidated') is True,
                 'NPC_LETHAL_REPEAT_FRESH_CURRENT_POSE_REQUIRED')
            events = list(self.session.broker.policy.log)
            start = self.event_start-(self.session.broker.policy.events-len(events))
            need(0 <= start <= len(events) and not any(event[0] == 'tx'
                 and event[2] == npc_motion.OPCODE for event in events[start:]),
                 'NPC_LETHAL_REPEAT_STATIONARY_EXTRA_MOVE')
            _,direction = approach.melee_geometry(self.goal,(self.position.word0,self.position.word1))
            self.arrival = approach.Arrival(self,writer,state,direction)
            self.phase = 'ARRIVED_SOURCE_PENDING'
            return sample

    def _check(self, writer, *, arrived=False):
        if self._continuous_authority is not None:
            target=self._continuous_authority
            need(self._continuous_target is target,'NPC_LETHAL_CONTINUOUS_ANCHOR_CHANGED')
            target.issuer.lethal_current_locked(target,self._repeat_context)
        if not self._repeat_stationary or not arrived:
            return super()._check(writer,arrived=arrived)
        state = super()._check(writer,arrived=False)
        need(self.arrival is not None and self.arrival._state is state is self.before
             and self.session._goal is self.goal,
             'NPC_LETHAL_REPEAT_CURRENT_ARRIVAL_REQUIRED')
        _,direction = approach.melee_geometry(self.goal,(self.position.word0,self.position.word1))
        need(self.arrival.direction == direction, 'NPC_LETHAL_REPEAT_CURRENT_DIRECTION_CHANGED')
        return state

    def _view(self, writer):
        broker=self.session.broker
        service=broker._npc_player_lethal
        need(type(service) is Service,'NPC_LETHAL_EXACT_SERVICE_REQUIRED')
        row,_,identities,values=service.current(writer,source_uid=self.session._target_uid)
        from tools.local_original_session import npc_session
        need(row['operation_lock'].locked() and not self.closed and type(self.session) is npc_session.NpcSession
             and not self.closed and not self.session._closed and not self.session.factory._closed
             and self.session.factory._session is self.session
             and self.session.factory.reader is service.hit.combat.targets.reader,
             'NPC_LETHAL_CURRENT_SESSION_REQUIRED')
        if self._repeat_context is not None:
            broker._player_life.owns_context(writer,self._repeat_context)
        binding=self.session.current_binding(_new_goal=self._repeat_context is not None)
        need(binding is not None and binding.owner is writer and binding.broker is broker,
             'NPC_LETHAL_CURRENT_SESSION_BINDING_REQUIRED')
        return service,row,identities,self._values(values),broker.realm.service(writer).snapshot(),attack.npc_mover(broker.realm,writer,self.session._target_uid)

    async def context(self, writer, *, life_context):
        need(self.arrival is not None and not self.contact_claimed and self.contact is None,
             'NPC_LETHAL_OBSERVED_UNQUERIED_ARRIVAL_REQUIRED')
        return await self.session.broker.npc_lethal_context(writer,expected_context=life_context,
            arrival=self.arrival,policy=self.session.broker._player_life.policy)

    def prepared_context_locked(self, writer, *, life_context, context):
        # Revalidate the original issuance, never recapture an Arrival/context.
        broker=self.session.broker;service=broker._npc_player_lethal
        need(type(service) is Service and type(context) is Context
             and context._service is service and context._writer is writer
             and type(self.arrival) is approach.Arrival
             and self.service is service and self.writer is writer and self.arrival._writer is writer
             and context.life_context is life_context
             and service.life is broker._player_life and not self.closed
             and self.arrival is context._approach and self.arrival._plan is self
             and self.arrival._context is context and self.arrival.phase == 'CONTEXT_ISSUED'
             and not self.attack_claimed and not self.contact_claimed and self.contact is None
             and service._operations.get(id(writer)) is None,
             'NPC_LETHAL_EXACT_PREPARED_QUERY_CONTEXT_REQUIRED')
        service.validate_locked(writer,context)
        # Every source/current callback precedes these final pure checks.
        need(broker._npc_player_lethal is service and service.life is broker._player_life
             and service._contexts.get(id(writer)) is context
             and service.life._contexts.get(id(writer)) is life_context
             and self.arrival is context._approach and self.arrival._context is context
             and self.arrival.phase == 'CONTEXT_ISSUED' and not self.attack_claimed
             and not self.contact_claimed and self.contact is None and not self.closed
             and not service.closed and service._operations.get(id(writer)) is None
             and self.session.broker is broker and self.session.factory._session is self.session
             and not self.session._closed and not self.session.factory._closed,
             'NPC_LETHAL_PREPARED_QUERY_CONTEXT_CHANGED')
        task=asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        return context

    def retire_prepared_context(self, context):
        # Failure/close cleanup only: no callbacks or row acquisition and no
        # effect on another context or an attempted/committed operation.
        if (type(context) is not Context or type(self.arrival) is not approach.Arrival
                or context._approach is not self.arrival):
            return
        service=context._service;writer=context._writer
        if (type(service) is Service and service is self.service and writer is self.writer
                and self.arrival._writer is writer and service._operations.get(id(writer)) is None
                and self.arrival is not None and self.arrival._plan is self
                and self.arrival._context is context and self.arrival.phase == 'CONTEXT_ISSUED'
                and not self.attack_claimed):
            if service._contexts.get(id(writer)) is context:
                service._contexts.pop(id(writer))
            self.arrival._context=None
            self.arrival.phase='CLOSED'

    async def attack(self, writer, *, expected_context, recovery_inputs, raw_effect):
        need(not self.attack_claimed,'NPC_LETHAL_PLAN_ATTACK_ONCE_REQUIRED')
        context=await self.context(writer,life_context=expected_context)
        self.attack_claimed=True
        attack._int32(raw_effect)
        need(raw_effect>0,'NPC_LETHAL_POSITIVE_RAW_EFFECT_REQUIRED')
        self._armed=(writer,context,context.snapshot,raw_effect,self.arrival.direction)
        self.arrival.phase='ATTACKING'
        try:
            result=await self.session.broker.npc_lethal_player(writer,expected_context=context,
                recovery_inputs=recovery_inputs,raw_effect=raw_effect,direction=self.arrival.direction,
                policy=self.session.broker._player_life.policy)
            self.arrival.phase,self.phase='COMMITTED','COMMITTED'
            return result
        except BaseException:
            self.phase=self.arrival.phase='FAILED'
            raise
        finally:self._armed=self._armed_body=None

    async def attack_scoped(self, writer, *, expected_context, recovery_inputs, raw_effect):
        # Context was issued by the original context caller before PRE. No new
        # capability is issued here, and the leaf validates its registry/current.
        broker=self.session.broker
        need(not self.attack_claimed,'NPC_LETHAL_PLAN_ATTACK_ONCE_REQUIRED')
        need(type(expected_context) is Context and expected_context._service is broker._npc_player_lethal
             and expected_context._writer is writer and expected_context._approach is self.arrival
             and type(self.arrival) is approach.Arrival and self.arrival._plan is self
             and self.arrival._writer is writer and self.arrival._context is expected_context
             and self.arrival.phase == 'CONTEXT_ISSUED'
             and type(expected_context._service) is Service and not expected_context._service.closed
             and expected_context._service._contexts.get(id(writer)) is expected_context
             and expected_context._service.life is broker._player_life
             and broker._player_life._contexts.get(id(writer)) is expected_context.life_context,
             'NPC_LETHAL_EXACT_CURRENT_CONTEXT_REQUIRED')
        attack._int32(raw_effect)
        need(raw_effect>0,'NPC_LETHAL_POSITIVE_RAW_EFFECT_REQUIRED')
        task=asyncio.current_task()
        if task is not None and task.cancelling(): raise asyncio.CancelledError()
        self.attack_claimed=True
        self._armed=(writer,expected_context,expected_context.snapshot,raw_effect,self.arrival.direction)
        self.arrival.phase='ATTACKING'
        try:
            result=await broker.npc_lethal_player_scoped(writer,expected_context=expected_context,
                recovery_inputs=recovery_inputs,raw_effect=raw_effect,direction=self.arrival.direction,
                policy=broker._player_life.policy)
            self.arrival.phase,self.phase='COMMITTED','COMMITTED'
            return result
        except BaseException:
            self.phase=self.arrival.phase='FAILED'
            raise
        finally:self._armed=self._armed_body=None
