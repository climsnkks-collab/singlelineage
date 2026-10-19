"""Explicit local NPC hit1 at ownHP1, with one existing HP/death authority.

The existing approach/contact query is inherited unchanged. Raw effect is not
damage; transport drain is not a client AttackAction/Next receipt.
"""
from dataclasses import dataclass, field
import struct
import asyncio
from tools.local_original_session import attack, attack_feedback, npc_approach_hit as approach, npc_player_hit, player_life

need = attack.need

@dataclass(frozen=True, slots=True)
class Context:
    life_context: object = field(repr=False)
    _service: object = field(repr=False)
    _writer: object = field(repr=False)
    _approach: object = field(repr=False)

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
        need(type(self.hit) is npc_player_hit.Service and self.hit.policy == npc_player_hit.POLICY,
             'NPC_LETHAL_CURRENT_NPC_SOURCE_REQUIRED')
        self._contexts, self._operations = {}, {}
        self.closed = False

    def current(self, writer):
        need(not self.closed and self.broker._npc_player_lethal is self
             and self.broker._player_life is self.life and self.broker._npc_player_hit is self.hit,
             'NPC_LETHAL_CURRENT_SERVICE_REQUIRED')
        return self.hit._current(writer)

    def capture_locked(self, writer, *, life_context, arrival):
        from tools.local_original_session import npc_approach_hit
        need(type(life_context) is player_life.Context and type(arrival) is npc_approach_hit.Arrival
             and type(arrival._plan) is Plan and arrival._plan.service is self
             and id(writer) not in self._contexts and id(writer) not in self._operations,
             'NPC_LETHAL_ONCE_TYPED_CONTEXT_REQUIRED')
        self.life.current_locked(writer, life_context)
        row, snapshot, _, _ = self.current(writer)
        need(snapshot is life_context.snapshot and snapshot.current_hp == 1,
             'NPC_LETHAL_SAME_CURRENT_HP_ONE_REQUIRED')
        arrival.ready_locked(writer)
        context = Context(life_context, self, writer, arrival)
        self._contexts[id(writer)] = context
        arrival.claim_context_locked(writer, context)
        return context

    def validate_locked(self, writer, context):
        need(type(context) is Context and context._service is self and context._writer is writer
             and self._contexts.get(id(writer)) is context,
             'NPC_LETHAL_EXACT_CONTEXT_REQUIRED')
        self.life.current_locked(writer, context.life_context)
        row, snapshot, _, _ = self.current(writer)
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

class Plan(approach.Plan):
    def __init__(self, session, *, goal, policy=approach.LOCAL_ADJACENT_SOURCE_STEP_CONTACT):
        need(policy==approach.LOCAL_ADJACENT_SOURCE_STEP_CONTACT,'NPC_LETHAL_STATIC_CONTACT_POLICY_REQUIRED')
        super().__init__(session,goal=goal,policy=policy)

    def _view(self, writer):
        broker=self.session.broker
        service=broker._npc_player_lethal
        need(type(service) is Service,'NPC_LETHAL_EXACT_SERVICE_REQUIRED')
        row,_,identities,values=service.current(writer)
        from tools.local_original_session import npc_session
        need(row['operation_lock'].locked() and type(self.session) is npc_session.NpcSession
             and not self.closed and not self.session._closed and not self.session.factory._closed
             and self.session.factory._session is self.session
             and self.session.factory.reader is service.hit.combat.targets.reader,
             'NPC_LETHAL_CURRENT_SESSION_REQUIRED')
        binding=self.session.current_binding()
        need(binding is not None and binding.owner is writer and binding.broker is broker,
             'NPC_LETHAL_CURRENT_SESSION_BINDING_REQUIRED')
        return service,row,identities,self._values(values),broker.realm.service(writer).snapshot(),broker.realm.npc_mover(writer)

    async def context(self, writer, *, life_context):
        need(self.arrival is not None and not self.contact_claimed and self.contact is None,
             'NPC_LETHAL_OBSERVED_UNQUERIED_ARRIVAL_REQUIRED')
        return await self.session.broker.npc_lethal_context(writer,expected_context=life_context,
            arrival=self.arrival,policy=self.session.broker._player_life.policy)

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
