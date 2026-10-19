"""One explicit source-reference melee approach and current arrival capability.

The existing session owns steps; its caller owns polls and observation slots.
No new sender/collector/task/timer exists. The reference arrow/door gate stays
unresolved. A separate explicit policy consumes one bounded static source-step
contact observation, without claiming original attack/arrow/door equivalence.
"""
from dataclasses import dataclass, field
import hashlib
import time

from tools.local_original_session import attack, movement, npc_motion, npc_observe, npc_player_hit, npc_session, observe

LOCAL_REFERENCE_MELEE_RANGE_ONE = 'EXPLICIT_LOCAL_REFERENCE_MELEE_RANGE_ONE_APPROACH_HIT'
POLICY = LOCAL_REFERENCE_MELEE_RANGE_ONE
LOCAL_ADJACENT_SOURCE_STEP_CONTACT = 'EXPLICIT_LOCAL_ADJACENT_SOURCE_STEP_CONTACT'
STATIC_STEP_CONTACT_POLICY = LOCAL_ADJACENT_SOURCE_STEP_CONTACT
need = attack.need
_SAMPLE = npc_observe.NpcObserver.sample_motion
REFERENCE = 'work/local_original_session/implementation-2/npc-motion-goal/approach-player-hit/core/references/'
SOURCE_PINS = {
    REFERENCE+'Point.java': 'c119a17d2d89755e65ba73be9bbe77e78bdf4fea5341e1e74b539343665ff048',
    REFERENCE+'L1V1Map.java': 'e459b46984aeb935d543bf32cb11e359582700844c1e802c47f4b2a2dde5328f',
    REFERENCE+'NpcTable.java': '2c50ee7ac2de87f0e2bcb1d1fafadd5dc6a896dbae021a1dcdf18ab0a0aa7819',
    REFERENCE+'npc-melee-range-one.sql': '7c1bdc269a1b33400e0dc6aa93ed06b2440dc8dae957a7f4c59df02b24e9803e',
    'work/combat_formula_research/sources/l1j-L1Character.java':
        'fbc1609d73160930c6cdcf749dc34ad6eacea63bad57c543d6cff0b829d77213',
}


def source_ready():
    npc_motion.source_ready(npc_motion.LOCAL_PRE_STEP)
    for relative, expected in SOURCE_PINS.items():
        raw = observe.ordinary(observe.ROOT/relative).read_bytes()
        need(0 < len(raw) <= 100000 and hashlib.sha256(raw).hexdigest() == expected,
             'NPC_APPROACH_REFERENCE_CHANGED')


def melee_geometry(npc_grid, player_grid):
    """Range1 uses the reference's tile-line distance; no overlapping target.

    For adjacent cells each nonzero normalized axis is exactly1, so the saved
    targetDirection floor(axis/max +0.59f) is precisely this eight-way delta.
    This intentionally does not generalize direction or range to farther cells.
    """
    for grid in (npc_grid, player_grid):
        need(type(grid) is tuple and len(grid) == 2, 'NPC_APPROACH_TYPED_GRID_REQUIRED')
        movement.authority.pack_grid(*grid)
    delta = tuple(b-a for a,b in zip(npc_grid, player_grid))
    distance = max(abs(value) for value in delta)
    need(distance == 1, 'NPC_APPROACH_REFERENCE_MELEE_ADJACENCY_REQUIRED')
    return distance, movement.authority.DELTAS.index(delta)


def _require_current_arrow(_plan, _writer):
    # REQ93/run99 must bind this to a real current terrain/spatial predicate.
    # Walk mask1, a prior goal success and a raw callback are not arrow/door LOS.
    raise ValueError('NPC_APPROACH_CURRENT_ARROW_DOOR_SOURCE_UNRESOLVED')


def _require_policy_context(plan, writer):
    if plan.policy == LOCAL_REFERENCE_MELEE_RANGE_ONE:
        _require_current_arrow(plan, writer)
    else:
        from tools.local_original_session import npc_source_step
        need(plan.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT,'NPC_APPROACH_STATIC_POLICY_REQUIRED')
        npc_source_step.source_ready()
        plan.session.factory.adapter._proof._binding()
        # A Context before firstattempt is authority preparation, never contact
        # admission. Only Plan.attack may arm the exact context/body for JIT.
        if plan.contact is not None:
            need(type(plan.contact) is npc_source_step.Contact,'NPC_APPROACH_TYPED_CONTACT_REQUIRED')
            plan.contact._require_binding_locked(writer)


@dataclass(slots=True)
class Arrival:
    _plan: object = field(repr=False)
    _writer: object = field(repr=False)
    _state: object = field(repr=False)
    direction: int
    phase: str = 'ARRIVED'
    _context: object = field(default=None, repr=False)

    def ready_locked(self, writer):
        need(type(self) is Arrival and self._plan.arrival is self and self._writer is writer
             and self.phase == 'ARRIVED' and self._context is None,
             'NPC_APPROACH_FRESH_ARRIVAL_REQUIRED')
        self._plan._check(writer, arrived=True)
        _require_policy_context(self._plan, writer)

    def claim_context_locked(self, writer, context):
        need(self._writer is writer and self.phase == 'ARRIVED' and self._context is None
             and context._approach is self, 'NPC_APPROACH_ARRIVAL_CONTEXT_ONCE_REQUIRED')
        self._context, self.phase = context, 'CONTEXT_ISSUED'

    def require_current_locked(self, writer, context):
        need(self._plan.arrival is self and self._writer is writer and self._context is context
             and context._approach is self and self.phase in ('CONTEXT_ISSUED','ATTACKING','COMMITTED'),
             'NPC_APPROACH_CURRENT_ARRIVAL_CONTEXT_REQUIRED')
        self._plan._check(writer, arrived=True)
        _require_policy_context(self._plan, writer)
        return self._plan.row

    def require_direction_locked(self, writer, direction):
        need(self._plan.arrival is self and self._writer is writer,
             'NPC_APPROACH_CURRENT_ARRIVAL_DIRECTION_REQUIRED')
        self._plan._check(writer,arrived=True)
        need(type(direction) is int and direction == self.direction,
             'NPC_APPROACH_EXACT_WIRE_DIRECTION_REQUIRED')

    def bind_body_locked(self,writer,context,operation,wire,parsed):
        if self._plan.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT:
            self._plan._bind_arm_body_locked(writer,context,operation,wire,parsed)

    def consume_attack_locked(self, writer, context, operation, wire):
        self.require_current_locked(writer,context)
        if self._plan.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT:
            self._plan._jit_contact_locked(writer,context,operation,wire)
            # Fresh full current projection after the actual passive query.
            context._service.validate_locked(writer,context)
            self._plan._require_arm_body_locked(writer,context,operation,wire)
            self.require_direction_locked(writer,self._plan._armed_body[3].direction)
            self._plan.contact.consume_attack_locked(writer,context,operation)


class Plan:
    def __init__(self, session, *, goal, policy):
        need(type(session) is npc_session.NpcSession and type(policy) is str
             and policy in (POLICY, LOCAL_ADJACENT_SOURCE_STEP_CONTACT),
             'NPC_APPROACH_EXPLICIT_REAL_SESSION_REQUIRED')
        need(type(goal) is tuple and len(goal) == 2, 'NPC_APPROACH_EXPLICIT_GOAL_REQUIRED')
        movement.authority.pack_grid(*goal)
        source_ready()
        self.session, self.goal, self.policy = session, goal, policy
        self.writer = self.row = self.service = self.position = self.mover = self.before = None
        self.identities = self.values = self.factory = self.configuration = None
        self.event_start = self.sent_before = None
        self.arrival = None
        self.contact = None
        self.contact_claimed = False
        self.contact_result = None
        self.contact_consumed_by = None
        self.contact_consumed_monotonic_ns = None
        self.last_motion_sample_ns = None
        self._armed = self._armed_body = None
        self.contact_query_role = None
        self.phase, self.closed, self.attack_claimed = 'NEW', False, False

    @staticmethod
    def _values(values):
        return (*values[:3], *values[4:])  # HP revision is authority elsewhere, not NPC/player position.

    def _view(self, writer):
        broker = self.session.broker
        service = broker._npc_player_hit_repeated_service(npc_player_hit.REPEATED_POLICY)
        row, _, identities, values = service._current(writer)
        need(row['operation_lock'].locked() and type(self.session) is npc_session.NpcSession
             and not self.closed and not self.session._closed and not self.session.factory._closed
             and self.session.factory._session is self.session
             and self.session.factory.reader is service.combat.targets.reader,
             'NPC_APPROACH_CURRENT_SESSION_REQUIRED')
        binding = self.session.current_binding()
        need(binding is not None and binding.owner is writer and binding.broker is broker,
             'NPC_APPROACH_CURRENT_SESSION_BINDING_REQUIRED')
        return service, row, identities, self._values(values), broker.realm.service(writer).snapshot(), broker.realm.npc_mover(writer)

    def _bind(self, writer):
        need(self.phase == 'NEW' and self.writer is None, 'NPC_APPROACH_BIND_ONCE_REQUIRED')
        service, row, identities, values, position, mover = self._view(writer)
        current = movement.authority.unpack_grid(mover.state.packed)
        player = (position.word0, position.word1)
        final_distance,_ = melee_geometry(self.goal, player)
        initial_distance = max(abs(a-b) for a,b in zip(current,player))
        need(max(abs(a-b) for a,b in zip(current,self.goal)) == 1 and current != self.goal
             and mover.state.goal is mover.state.last_step_ns is self.session._goal is None,
             'NPC_APPROACH_FRESH_NONZERO_SINGLE_STEP_REQUIRED')
        if self.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT:
            need(initial_distance > 1 and initial_distance > final_distance,
                 'NPC_APPROACH_STRICT_DISTANCE_DECREASE_REQUIRED')
        self.writer, self.row, self.service, self.position, self.mover = writer, row, service, position, mover
        self.before, self.identities, self.values = mover.state, identities, values
        self.factory, self.configuration = self.session.factory, self.session.factory.config
        self.event_start, self.sent_before = self.session.broker.policy.events, row['policy_row'].sent
        self.phase = 'BOUND'

    def _check(self, writer, *, arrived=False):
        need(self.writer is writer and self.row is not None and self.phase != 'FAILED',
             'NPC_APPROACH_BOUND_PLAN_REQUIRED')
        source_ready()
        service, row, identities, values, position, mover = self._view(writer)
        need(service is self.service and row is self.row and mover is self.mover
             and position is self.position and self.session.factory is self.factory
             and self.session.factory.config is self.configuration
             and len(identities) == len(self.identities)
             and all(a is b for a,b in zip(identities,self.identities)) and values == self.values,
             'NPC_APPROACH_CURRENT_PLAYER_OR_NPC_LIFE_CHANGED')
        _, expected_direction = melee_geometry(self.goal,(position.word0,position.word1))
        state = mover.state
        need(mover.spawn_drained and not mover.closed and not mover.fatal and mover.pending is None
             and (state is self.before or state.goal is self.goal
                  and movement.authority.unpack_grid(state.packed) == self.goal)
             and (self.session._goal is None or self.session._goal is self.goal),
             'NPC_APPROACH_CURRENT_GOAL_STATE_CHANGED')
        if arrived:
            need(self.arrival is not None and state is self.arrival._state and state is not self.before
                 and state.goal is self.goal and self.session._goal is self.goal,
                 'NPC_APPROACH_EXACT_ARRIVAL_STATE_REQUIRED')
            need(type(self.arrival.direction) is int and self.arrival.direction == expected_direction,
                 'NPC_APPROACH_SOURCE_DIRECTION_CHANGED')
        return state

    async def sample_motion_locked(self, writer, observer, *, now_ns):
        if self.phase == 'NEW': self._bind(writer)
        self._check(writer)
        need(self.arrival is None and type(observer) is npc_observe.NpcObserver
             and observer.sample_motion.__func__ is _SAMPLE and type(observer).sample_motion is _SAMPLE
             and observer.targets.broker is self.session.broker
             and observer.targets.reader is self.session.factory.reader,
             'NPC_APPROACH_CANONICAL_FRESH_POSE_REQUIRED')
        result = await _SAMPLE(observer,writer,self.before.uid,now_ns=now_ns)
        self.last_motion_sample_ns = now_ns
        state = self._check(writer)
        if result.get('status') != 'OBSERVED':
            self.phase = 'FAILED'
            return result
        actual_goal = movement.authority.unpack_grid(state.packed) == self.goal and state is not self.before
        matched = (result.get('uid') == state.uid and result.get('map_id') == state.map_id
            and tuple(result.get('server_grid') or ()) == self.goal
            and tuple(result.get('client_grid') or ()) == self.goal
            and result.get('coordinates_match') is True and result.get('npc_idle') is True
            and result.get('source_contract_valid') is True and result.get('source_owner_revalidated') is True)
        if actual_goal and matched:
            events = list(self.session.broker.policy.log)
            start = self.event_start-(self.session.broker.policy.events-len(events))
            need(0 <= start <= len(events), 'NPC_APPROACH_ORIGINAL_MOVE_EVENTS_REQUIRED')
            drained = [event for event in events[start:] if event[0] == 'tx' and event[2] == npc_motion.OPCODE]
            admitted = self.row['policy_row']
            need(len(drained) == 1 and admitted.sent >= self.sent_before+1
                 and admitted.pending_opcode is admitted.drain_started_ns is None
                 and admitted.pending_size == 0, 'NPC_APPROACH_ONE_DRAINED_STEP_REQUIRED')
            _, direction = melee_geometry(self.goal,(self.position.word0,self.position.word1))
            self.arrival = Arrival(self,writer,state,direction)
            self.phase = 'ARRIVED_SOURCE_PENDING'
        return result  # Original producer DTO, never supplied by a caller as authority.

    async def sample_contact_locked(self, writer, *, now_ns):
        """Diagnostic observation only; it cannot arm or authorize a send."""
        from tools.local_original_session import npc_source_step
        need(self.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT and self.arrival is not None
             and not self.contact_claimed,'NPC_APPROACH_STATIC_CONTACT_ONCE_REQUIRED')
        self.contact_claimed = True
        self.contact_query_role = 'DIAGNOSTIC_NO_SEND_ADMISSION'
        adapter=npc_source_step.ContactAdapter(self)
        try:
            need(type(now_ns) is int and self.last_motion_sample_ns is not None
                 and now_ns-self.last_motion_sample_ns >= npc_observe.MIN_INTERVAL_NS,
                 'NPC_APPROACH_SEPARATE_CONTACT_QUERY_SLOT_REQUIRED')
            await self.session.broker._checkpoint(writer,self.row)
            self.contact=adapter.sample_locked(writer,now_ns=now_ns)
            self.contact_result=self.contact.metadata()
            self.phase='CONTACT_READY' if self.contact.admitted else 'CONTACT_REFUSED'
            return dict(self.contact_result)
        except BaseException:
            self.phase='FAILED'
            self.contact_result=dict(adapter.last_result)
            raise

    def contact_metadata(self):
        return (self.contact.metadata() if self.contact is not None else
                None if self.contact_result is None else dict(self.contact_result))

    def preparation_metadata(self):
        return dict(status='PREPARED_AUTHORITY_NO_SEND_ADMISSION',contact_query_count=int(self.contact_claimed),
                    predicate_scope='STATIC_SOURCE_STEP_CONTINUE',original_arrow_door='UNKNOWN')

    def _bind_arm_body_locked(self,writer,context,operation,wire,parsed):
        need(self._armed is not None and self._armed_body is None
             and self._armed[0] is writer and self._armed[1] is context
             and self._armed[2] is context.snapshot and operation.context is context,
             'NPC_APPROACH_EXPLICIT_BODY_ARM_REQUIRED')
        need(parsed.attacker_uid==context.source_uid and parsed.target_uid==context.target_uid
             and parsed.raw_effect==self._armed[3] and parsed.direction==self._armed[4],
             'NPC_APPROACH_EXACT_ARMED_BODY_REQUIRED')
        self._armed_body=(self._armed,operation,wire,parsed)

    def _require_arm_body_locked(self,writer,context,operation,wire):
        arm,body=self._armed,self._armed_body
        need(arm is not None and body is not None and body[0] is arm and arm[0] is writer
             and arm[1] is context and arm[2] is context.snapshot and body[1] is operation
             and operation.context is context and operation.context._approach is self.arrival
             and body[2] is wire and operation.wire is wire
             and context._service.operation_for(writer) is operation
             and operation.phase=='ATTACK' and operation.attack_transport=='RESERVED'
             and body[3].attacker_uid==context.source_uid and body[3].target_uid==context.target_uid
             and body[3].raw_effect==arm[3] and body[3].direction==arm[4]==self.arrival.direction,
             'NPC_APPROACH_CURRENT_ARMED_BODY_REQUIRED')

    def _jit_contact_locked(self,writer,context,operation,wire):
        from tools.local_original_session import npc_source_step
        self._require_arm_body_locked(writer,context,operation,wire)
        need(self.attack_claimed and not self.contact_claimed and self.contact is None,
             'NPC_APPROACH_JIT_CONTACT_ONCE_REQUIRED')
        now_ns=time.monotonic_ns()
        need(self.last_motion_sample_ns is not None
             and now_ns-self.last_motion_sample_ns>=npc_observe.MIN_INTERVAL_NS,
             'NPC_APPROACH_SEPARATE_CONTACT_QUERY_SLOT_REQUIRED')
        self.contact_claimed=True
        self.contact_query_role='JIT_FIRST_ATTACK_ATTEMPT'
        adapter=npc_source_step.ContactAdapter(self)
        try:
            self.contact=adapter.sample_locked(writer,now_ns=now_ns)
            self.contact_result=self.contact.metadata()
        except BaseException:
            self.contact_result=dict(adapter.last_result,query_role=self.contact_query_role)
            raise

    async def context(self, writer):
        need(self.arrival is not None, 'NPC_APPROACH_OBSERVED_ARRIVAL_REQUIRED')
        if self.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT:
            need(self.contact is None and not self.contact_claimed,'NPC_APPROACH_UNQUERIED_PREPARATION_REQUIRED')
        async with self.row['operation_lock']:
            await self.session.broker._checkpoint(writer,self.row)
            self.arrival.ready_locked(writer)
            return self.service.capture_locked(writer,approach=self.arrival)

    async def attack(self, writer, *, expected_context, raw_effect):
        need(self.arrival is not None and expected_context._approach is self.arrival
             and not self.attack_claimed, 'NPC_APPROACH_ONCE_CONTEXT_REQUIRED')
        self.attack_claimed = True
        if self.policy == LOCAL_ADJACENT_SOURCE_STEP_CONTACT:
            need(self.contact is None and not self.contact_claimed,'NPC_APPROACH_UNQUERIED_JIT_REQUIRED')
            attack._int32(raw_effect)
            need(raw_effect>0,'NPC_APPROACH_POSITIVE_RAW_EFFECT_REQUIRED')
            self._armed=(writer,expected_context,expected_context.snapshot,raw_effect,self.arrival.direction)
        self.arrival.phase = 'ATTACKING'
        try:
            result = await self.session.broker.attack_player_repeated(writer,expected_context=expected_context,
                raw_effect=raw_effect,direction=self.arrival.direction,policy=npc_player_hit.REPEATED_POLICY)
            self.arrival.phase, self.phase = 'COMMITTED', 'COMMITTED'
            return result
        except BaseException:
            self.phase = self.arrival.phase = 'FAILED'
            raise
        finally:
            self._armed = self._armed_body = None

    def close(self):
        self.closed = True
        self._armed = self._armed_body = None
        if self.arrival is not None: self.arrival.phase = 'CLOSED'
