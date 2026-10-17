"""Optional explicit-goal NPC controller over the existing retained broker.

Axis-sign direction choice is a named local policy, not original AI/pathfinding.
No timers, attachment, spawning sender, retry, or broker lifetime ownership live
here. Spawn and move frames retain the broker's actual write/drain/commit path.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tools.local_original_session import broker as b, movement, npc, npc_edge, npc_motion

EXPLICIT_LOCAL_AXIS_SIGN_GOAL = 'EXPLICIT_LOCAL_AXIS_SIGN_GOAL'
AXIS_SIGN_GOAL = EXPLICIT_LOCAL_AXIS_SIGN_GOAL
need = b.need


@dataclass(frozen=True, slots=True)
class NpcSessionConfig:
    spawns: tuple = ()
    interval_ns: int | None = None
    policy: str | None = None
    goal_policy: str | None = None

    def __post_init__(self):
        need(type(self.spawns) is tuple and len(self.spawns) <= npc.MAX_SPAWNS
             and all(type(spawn) is npc.NpcSpawn for spawn in self.spawns),
             'NPC_SESSION_TYPED_BOUNDED_SPAWNS_REQUIRED')
        if not self.spawns:
            need(self.interval_ns is self.policy is self.goal_policy is None,
                 'NPC_SESSION_DISABLED_CONFIGURATION_REQUIRED')
        else:
            need(type(self.interval_ns) is int and 0 < self.interval_ns < (1 << 63),
                 'NPC_SESSION_EXPLICIT_INTERVAL_REQUIRED')
            need(self.policy == npc_motion.LOCAL_PRE_STEP,
                 'NPC_SESSION_EXPLICIT_PRE_STEP_POLICY_REQUIRED')
            need(self.goal_policy == AXIS_SIGN_GOAL, 'NPC_SESSION_EXPLICIT_GOAL_POLICY_REQUIRED')


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str
    state: npc_motion.State | None = None
    reason: str | None = None


class NpcSessionFactory:
    """Prepare broker kwargs before construction, then bind that exact broker.

    The existing launcher retains reader preparation/attach and broker start/
    close ownership. Disabled construction never builds/reads an edge adapter.
    Do not pass overlapping NPC kwargs alongside broker_options().
    """
    def __init__(self, reader, *, config=NpcSessionConfig()):
        need(type(config) is NpcSessionConfig, 'NPC_SESSION_CONFIG_REQUIRED')
        self.config, self.reader = config, reader
        self._session = None
        self._closed = False
        self.adapter = (npc_edge.NpcEdgeAdapter(reader, current=self.current_binding)
                        if config.spawns else None)

    def current_binding(self):
        return None if self._closed or self._session is None else self._session.current_binding()

    def broker_options(self):
        if not self.config.spawns:
            return {}
        return dict(npc_spawns=self.config.spawns,
                    npc_motion_interval_ns=self.config.interval_ns,
                    npc_motion_policy=self.config.policy, npc_edge_passability=self.adapter)

    def bind(self, broker):
        need(not self._closed, 'NPC_SESSION_FACTORY_CLOSED')
        need(self._session is None, 'NPC_SESSION_FACTORY_ALREADY_BOUND')
        session = NpcSession(broker, factory=self)
        self._session = session
        return session

    def close(self):
        self._closed = True
        if self._session is not None:
            self._session.close()


class NpcSession:
    def __init__(self, broker, *, factory):
        need(type(broker) is b.PersistentBroker and type(factory) is NpcSessionFactory,
             'NPC_SESSION_REAL_BROKER_AND_FACTORY_REQUIRED')
        self.broker, self.factory = broker, factory
        self._closed = False
        self._lock = asyncio.Lock()  # Never acquire the broker row lock here.
        self._last_now_ns = None
        self._goal = None
        self._configuration()

    def _configuration(self):
        config, realm = self.factory.config, self.broker.realm
        need(type(realm) is b.LocalRealm, 'NPC_SESSION_REAL_REALM_REQUIRED')
        actual = tuple(spawn for spawn, _ in realm._npc_spawns)
        need(len(actual) == len(config.spawns)
             and all(a is expected for a, expected in zip(actual, config.spawns)),
             'NPC_SESSION_SAME_SPAWNS_REQUIRED')
        need(realm._npc_motion_interval_ns == config.interval_ns
             and realm._npc_motion_policy == config.policy
             and realm.npc_edge_passability is self.factory.adapter,
             'NPC_SESSION_SAME_MOTION_CONFIGURATION_REQUIRED')

    def current_binding(self):
        """Resolve unique live selected writer from current claims on each call.

        No writer, Position or State survives this call. The edge adapter then
        independently binds the actual retained reader/claim before/after read.
        """
        if self._closed or self.factory._closed or not self.factory.config.spawns:
            return None
        try:
            self._configuration()
            broker, reader = self.broker, self.factory.reader
            policy, retained, member = broker.policy, reader.owner, reader.member
            need(type(policy) is b._TransportPolicy and retained is not None
                 and policy.owner is retained and not retained.closed
                 and member is retained.child and member is not None
                 and policy.handle is retained.owner_handle and policy.job is retained.owner_job
                 and member.process == retained.owner_handle and member.job == retained.owner_job,
                 'NPC_SESSION_SAME_RETAINED_READER_REQUIRED')
            need(not broker._closing and not broker.failure.is_set() and policy.state == 'OPEN',
                 'NPC_SESSION_CURRENT_BROKER_REQUIRED')
            candidates = []
            for rows in broker._claims.values():
                for row in rows:
                    if row['failed'] or row['joined']:
                        continue
                    writer = row['writer']
                    try:
                        service = broker.realm.service(writer)
                        selected = service.snapshot()
                        mover = broker.realm.npc_mover(writer)
                    except (ValueError, KeyError):
                        continue  # Unselected/retired writers do not authorize movement.
                    policy_row = policy._connection(writer)
                    need(row['policy_row'] is policy_row and policy_row.writer is writer
                         and policy_row.stage == 1 and not policy_row.eof
                         and not policy_row.task_joined and not policy_row.registry_removed,
                         'NPC_SESSION_CURRENT_CLAIM_REQUIRED')
                    config = self.factory.config
                    need(type(service) is movement.MovementService
                         and type(selected) is movement.Position
                         and type(mover) is npc_motion.NpcMotion
                         and type(mover.state) is npc_motion.State
                         and not mover.closed and not mover.fatal and mover.pending is None
                         and mover.spawn_drained is True
                         and mover.interval_ns == config.interval_ns and mover.policy == config.policy
                         and mover.state.uid == config.spawns[0].uid
                         and mover.state.map_id == config.spawns[0].map_id == selected.map_id,
                         'NPC_SESSION_CURRENT_MATCHING_DRAINED_MOVER_REQUIRED')
                    candidates.append(writer)
            need(len(candidates) == 1, 'NPC_SESSION_UNAMBIGUOUS_SELECTED_WRITER_REQUIRED')
            return npc_edge.NpcEdgeBinding(candidates[0], broker)
        except Exception:
            return None

    def submit_goal(self, *, goal):
        """Replace the one explicit goal; no queue, timer or immediate send.

        An in-flight tick finishes its one captured goal. AT_GOAL retains that
        goal until a later submit/close, so an older tick cannot clear a new one.
        """
        need(not self._closed and not self.factory._closed, 'NPC_SESSION_CLOSED')
        need(type(goal) is tuple and len(goal) == 2, 'NPC_SESSION_EXPLICIT_GOAL_REQUIRED')
        movement.authority.pack_grid(*goal)
        self._goal = goal

    async def tick(self, *, now_ns):
        """One caller-driven poll of the captured goal; never starts a task."""
        if self._closed or self.factory._closed:
            return Outcome('CLOSED')
        if not self.factory.config.spawns:
            return Outcome('DISABLED')
        goal = self._goal
        if goal is None:
            return Outcome('IDLE')
        return await self.approach(goal=goal, now_ns=now_ns)

    async def approach(self, *, goal, now_ns):
        """Try one local axis-sign step using caller's explicit monotonic clock.

        Only known no-send cadence/edge refusals become outcomes. Broker send
        failures and cancellation propagate unchanged, without retry. close()
        suppresses future calls; caller still owns any in-flight broker close.
        """
        need(type(goal) is tuple and len(goal) == 2, 'NPC_SESSION_EXPLICIT_GOAL_REQUIRED')
        movement.authority.pack_grid(*goal)
        need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'NPC_SESSION_CLOCK_REQUIRED')
        async with self._lock:
            if self._closed or self.factory._closed:
                return Outcome('CLOSED')
            if not self.factory.config.spawns:
                return Outcome('DISABLED')
            need(self._last_now_ns is None or now_ns >= self._last_now_ns,
                 'NPC_SESSION_MONOTONIC_CLOCK_REQUIRED')
            self._last_now_ns = now_ns
            binding = self.current_binding()
            if binding is None:
                return Outcome('UNKNOWN', reason='NPC_SESSION_CURRENT_BINDING_UNAVAILABLE')
            mover = self.broker.realm.npc_mover(binding.owner)
            state = mover.state
            grid = movement.authority.unpack_grid(state.packed)
            if grid == goal:
                return Outcome('AT_GOAL', state)
            if state.last_step_ns is not None and now_ns < state.last_step_ns + mover.interval_ns:
                return Outcome('CADENCE', state)
            delta = tuple((target > current) - (target < current)
                          for current, target in zip(grid, goal))
            direction = movement.authority.DELTAS.index(delta)
            try:
                state = await self.broker.step_npc(binding.owner, goal=goal,
                                                  direction=direction, now_ns=now_ns)
            except ValueError as error:
                if str(error) == 'NPC_MOVE_LOCAL_CADENCE':
                    return Outcome('CADENCE')
                if str(error) == 'NPC_MOVE_EDGE_BLOCKED_OR_UNKNOWN':
                    edge_result = self.factory.adapter.last_result
                    status = 'BLOCKED' if edge_result['status'] == 'BLOCKED_MASK1' else 'UNKNOWN'
                    return Outcome(status, reason=edge_result['reason'])
                raise
            return Outcome('MOVED', state)

    def close(self):
        """Stop accepting goals; native reader/broker ownership stays in caller."""
        self._closed = True
        self._goal = None
