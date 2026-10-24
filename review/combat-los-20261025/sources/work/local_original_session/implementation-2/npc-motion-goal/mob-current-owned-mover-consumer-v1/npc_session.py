"""Optional explicit-goal NPC controller over the existing retained broker.

Axis-sign direction choice is a named local policy, not original AI/pathfinding.
No timers, attachment, spawning sender, retry, or broker lifetime ownership live
here. Spawn and move frames retain the broker's actual write/drain/commit path.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tools.local_original_session import broker as b, movement, npc, npc_edge, npc_motion, attack

EXPLICIT_LOCAL_AXIS_SIGN_GOAL = 'EXPLICIT_LOCAL_AXIS_SIGN_GOAL'
AXIS_SIGN_GOAL = EXPLICIT_LOCAL_AXIS_SIGN_GOAL
need = b.need
SERVER_NAVIGATION=npc_edge.SERVER_NAVIGATION_POLICY


@dataclass(frozen=True, slots=True)
class NpcSessionConfig:
    spawns: tuple = ()
    interval_ns: int | None = None
    policy: str | None = None
    goal_policy: str | None = None
    respawn_policy: str | None = None

    def __post_init__(self):
        need(type(self.spawns) is tuple
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
        if self.respawn_policy is not None:
            from tools.local_original_session import npc_respawn
            need(bool(self.spawns) and type(self.respawn_policy) is str
                 and self.respawn_policy == npc_respawn.POLICY,
                 'NPC_SESSION_EXPLICIT_RESPAWN_POLICY_REQUIRED')


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
    def __init__(self, reader, *, config=NpcSessionConfig(), navigation_policy=None):
        need(type(config) is NpcSessionConfig, 'NPC_SESSION_CONFIG_REQUIRED')
        need(navigation_policy in (None,SERVER_NAVIGATION),'NPC_SESSION_EXPLICIT_NAVIGATION_POLICY_REQUIRED')
        self.packet_server=None
        self.navigation_policy=navigation_policy
        self.config, self.reader = config, reader
        self._session = None
        self._closed = False
        self.adapter = ((npc_edge.ServerNpcEdgeAdapter(current=self.current_binding)
                         if navigation_policy==SERVER_NAVIGATION else
                         npc_edge.NpcEdgeAdapter(reader,current=self.current_binding))
                        if config.spawns else None)

    @classmethod
    def for_packet(cls, server, *, config):
        """Explicit cold packet binding; no retained reader/native substitute.

        May prepare configuration before PacketServer.prepare; this issues no
        current authority. The official pre-broker feature seam supplies these
        broker_options unchanged. Bind only after prepare, before start.
        """
        from packet_server import PacketServer
        need(cls is NpcSessionFactory and type(server) is PacketServer
             and type(config) is NpcSessionConfig
             and not server.started and not server.closed
             and ((not server.prepared and server.broker is None)
                  or (server.prepared and type(server.broker) is b.PersistentBroker
                      and not server.broker._started)),
             'NPC_SESSION_EXACT_COLD_PACKET_SERVER_REQUIRED')
        factory=cls.__new__(cls)
        factory.packet_server=server
        factory.navigation_policy=SERVER_NAVIGATION
        factory.config,factory.reader=config,None
        factory._session=None;factory._closed=False
        factory.adapter=(npc_edge.ServerNpcEdgeAdapter(current=factory.current_binding)
                         if config.spawns else None)
        return factory

    def _packet_current(self, writer):
        from packet_server import PacketServer
        from packet_peer import PacketCurrent
        server=self.packet_server
        need(type(server) is PacketServer and not self._closed
             and self._session is not None and not self._session._closed
             and server.broker is self._session.broker,
             'NPC_SESSION_SAME_PACKET_SERVER_REQUIRED')
        broker=server.broker
        rows=[row for claims in broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows)==1,'NPC_SESSION_PACKET_CURRENT_CLAIM_REQUIRED')
        row,=rows
        if row['operation_lock'].locked():
            need(broker._canonical_operation_task is asyncio.current_task(),
                 'NPC_SESSION_PACKET_FOREIGN_OPERATION_REFUSED')
            context=server.current_for(writer)
        else:
            context=server.current(row['peer']['connection_id'])
        need(type(context) is PacketCurrent and server.check_current(context) is context
             and context.broker is broker and context.writer is writer
             and context.row['writer'] is writer and context.row['policy_row'] is context.policy_row
             and context.row is row
             and context.game is broker.realm.registry.resolve(writer)
             and context.selection is context.game.selection
             and context.mover is broker.realm.service(writer)
             and context.position is context.mover.snapshot(),
             'NPC_SESSION_SOURCE_PACKET_CURRENT_REQUIRED')
        return context

    def current_binding(self, *, target_uid=None):
        return None if self._closed or self._session is None else self._session.current_binding(target_uid=target_uid)

    def player_edge(self, uid, map_id, start, direction, destination):
        """One source-bound server navigation provider for PC and NPC edges."""
        from packet_server import PacketServer
        from tools.local_original_session import npc_world_navigation as navigation
        server,session,adapter=self.packet_server,self._session,self.adapter
        need(type(self) is NpcSessionFactory and type(server) is PacketServer
             and server.prepared and server.started and not server.closed and not self._closed
             and self.navigation_policy==SERVER_NAVIGATION
             and type(session) is NpcSession and not session._closed and session.factory is self
             and session.broker is server.broker
             and type(adapter) is npc_edge.ServerNpcEdgeAdapter and not adapter.closed
             and adapter.broker is server.broker
             and server.broker.realm.npc_edge_passability is adapter
             and getattr(server.broker.realm.edge_passability,'__self__',None) is self
             and getattr(server.broker.realm.edge_passability,'__func__',None) is NpcSessionFactory.player_edge,
             'NPC_SESSION_SAME_PLAYER_EDGE_OWNER_REQUIRED')
        provider=adapter.provider
        need(type(provider) is navigation.NpcWorldNavigation and provider.broker is server.broker
             and provider.current is adapter.current
             and getattr(provider.current,'__self__',None) is self
             and getattr(provider.current,'__func__',None) is NpcSessionFactory.current_binding
             and getattr(provider.player_edge,'__self__',None) is provider
             and getattr(provider.player_edge,'__func__',None) is navigation.NpcWorldNavigation.player_edge,
             'NPC_SESSION_SAME_PLAYER_EDGE_PROVIDER_REQUIRED')
        return provider.player_edge(uid,map_id,start,direction,destination)

    def broker_options(self):
        if not self.config.spawns:
            return {}
        options = dict(npc_spawns=self.config.spawns,
                    npc_motion_interval_ns=self.config.interval_ns,
                    npc_motion_policy=self.config.policy, npc_edge_passability=self.adapter)
        if self.config.respawn_policy is not None:
            options['npc_respawn_policy'] = self.config.respawn_policy
        return options

    def bind(self, broker, *, generation=None):
        need(not self._closed, 'NPC_SESSION_FACTORY_CLOSED')
        need(self._session is None, 'NPC_SESSION_FACTORY_ALREADY_BOUND')
        if self.packet_server is not None:
            need(self.packet_server.prepared and not self.packet_server.started
                 and not self.packet_server.closed
                 and broker is self.packet_server.broker and not broker._started
                 and self.reader is None and self.navigation_policy==SERVER_NAVIGATION,
                 'NPC_SESSION_PACKET_COLD_BIND_REQUIRED')
        if self.navigation_policy==SERVER_NAVIGATION and self.adapter is not None:
            self.adapter.bind(broker)
        session = NpcSession(broker, factory=self, generation=generation)
        self._session = session
        return session

    def close(self):
        self._closed = True
        if self._session is not None:
            self._session.close()
        if self.navigation_policy==SERVER_NAVIGATION and self.adapter is not None:
            self.adapter.close()


@dataclass(slots=True)
class MotionLane:
 uid: int
 generation: object=None
 mover: object=None
 goal: object=None
 goal_player_life: object=None
 last_now_ns: object=None

class NpcSession:
    def __init__(self, broker, *, factory, generation=None):
        need(type(broker) is b.PersistentBroker and type(factory) is NpcSessionFactory,
             'NPC_SESSION_REAL_BROKER_AND_FACTORY_REQUIRED')
        self.broker, self.factory = broker, factory
        self._closed = False
        self._lock = asyncio.Lock()  # Never acquire the broker row lock here.
        self._lanes = {}
        self._configuration()
        if generation is not None:self.bind_lane(generation.recipe.uid,generation)
    @property
    def server_navigation(self):
        return self.factory.navigation_policy==SERVER_NAVIGATION

    def _configuration(self):
        config, realm = self.factory.config, self.broker.realm
        if self.server_navigation:
            need(type(self.factory.adapter) is npc_edge.ServerNpcEdgeAdapter
                 and self.factory.adapter.broker is self.broker
                 and self.factory.adapter.provider is not None,
                 'NPC_SESSION_BOUND_SERVER_PROVIDER_REQUIRED')
        need(type(realm) is b.LocalRealm, 'NPC_SESSION_REAL_REALM_REQUIRED')
        actual = tuple(spawn for spawn, _ in realm._npc_spawns)
        need(len(actual) == len(config.spawns)
             and all(a is expected for a, expected in zip(actual, config.spawns)),
             'NPC_SESSION_SAME_SPAWNS_REQUIRED')
        need(realm._npc_motion_interval_ns == config.interval_ns
             and realm._npc_motion_policy == config.policy
             and realm.npc_edge_passability is self.factory.adapter,
             'NPC_SESSION_SAME_MOTION_CONFIGURATION_REQUIRED')

    def _singleton_lane(self):
        need(len(self.factory.config.spawns)==1,'NPC_SESSION_EXPLICIT_UID_REQUIRED')
        return self.lane_for(self.factory.config.spawns[0].uid)

    @property
    def _goal(self):return self._singleton_lane().goal
    @property
    def _generation(self):return self._singleton_lane().generation
    @property
    def _owned_mover(self):return self._singleton_lane().mover
    @property
    def _target_uid(self):return self._singleton_lane().uid
    @property
    def _goal_player_life(self):return self._singleton_lane().goal_player_life

    def resolve_uid(self,target_uid=None):
        return self.broker.realm.npc_target_uid(target_uid)

    def lane_for(self,target_uid):
        uid=self.resolve_uid(target_uid)
        lane=self._lanes.get(uid)
        if lane is None:
            lane=MotionLane(uid);self._lanes[uid]=lane
        return lane

    def bind_lane(self,target_uid,generation):
        uid=self.resolve_uid(target_uid);realm=self.broker.realm
        need(not self._closed and not self.factory._closed and generation.recipe.uid==uid
             and attack.registered_npc_generation(self.broker._npc_respawn,realm,generation.writer,uid) is generation
             and attack.npc_mover(realm,generation.writer,uid) is generation.mover,
             'NPC_SESSION_SOURCE_OWNED_TARGET_GENERATION_REQUIRED')
        old=self._lanes.get(uid)
        if old is not None and old.generation is generation:return old
        need(old is None or old.goal is None and (old.mover is None or old.mover.pending is None),
             'NPC_SESSION_GENERATION_REPLACE_IN_FLIGHT_REFUSED')
        lane=MotionLane(uid,generation,generation.mover);self._lanes[uid]=lane
        return lane

    def retire_generation(self,writer,generation):
        lane=self._lanes.get(generation.recipe.uid)
        if lane is not None and lane.generation is generation and generation.writer is writer:
            lane.goal=lane.goal_player_life=None
            del self._lanes[lane.uid]
            return True
        return False

    def clear_lanes(self):
        for lane in self._lanes.values():lane.goal=lane.goal_player_life=None
        self._lanes.clear()
    def release_continuous_targets(self,controller,writer):
        from tools.local_original_session import npc_continuous_retaliation as continuous
        need(type(controller) is continuous.Controller and controller.broker is self.broker
             and controller.npc_session is self and self.broker._npc_continuous is controller,
             'NPC_SESSION_LITERAL_SELECTION_RELEASE_REQUIRED')
        for lane in tuple(self._lanes.values()):
            if lane.generation is not None and lane.generation.writer is writer:
                self.retire_generation(writer,lane.generation)
    def current_binding(self, *, _new_goal=False, target_uid=None):
        """Resolve unique live selected writer from current claims on each call.

        No writer, Position or State survives this call. The edge adapter then
        independently binds the actual retained reader/claim before/after read.
        """
        if self._closed or self.factory._closed or not self.factory.config.spawns:
            return None
        lane=self.lane_for(target_uid)
        if self._closed or self.factory._closed or not self.factory.config.spawns:
            return None
        try:
            self._configuration()
            broker, reader = self.broker, self.factory.reader
            server=self.factory.packet_server
            packet_contexts={}
            policy=broker.policy
            if server is None:
                policy, retained, member = broker.policy, reader.owner, reader.member
                need(type(policy) is b._TransportPolicy and retained is not None
                     and policy.owner is retained and not retained.closed
                     and member is retained.child and member is not None
                     and policy.handle is retained.owner_handle and policy.job is retained.owner_job
                     and member.process == retained.owner_handle and member.job == retained.owner_job,
                     'NPC_SESSION_SAME_RETAINED_READER_REQUIRED')
            else:
                need(server.broker is broker and reader is None and self.server_navigation,
                     'NPC_SESSION_PACKET_SOURCE_REQUIRED')
            need(not broker._closing and not broker.failure.is_set() and policy.state == 'OPEN',
                 'NPC_SESSION_CURRENT_BROKER_REQUIRED')
            candidates = []
            for rows in broker._claims.values():
                for row in rows:
                    if row['failed'] or row['joined']:
                        continue
                    writer = row['writer']
                    try:
                        if server is not None:
                            context=self.factory._packet_current(writer)
                            need(context.row is row,'NPC_SESSION_PACKET_CURRENT_ROW_REQUIRED')
                            packet_contexts[id(writer)]=context
                        service = broker.realm.service(writer)
                        selected = service.snapshot()
                        life = getattr(broker, '_player_life', None)
                        if life is not None:
                            life.check_normal_locked(writer)
                            if not _new_goal and lane.goal is not None:
                                need(lane.goal_player_life is life.token(writer),
                                     'NPC_SESSION_OLD_PLAYER_LIFE_GOAL')
                        mover = attack.npc_mover(broker.realm, writer, lane.uid)
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
                         and mover.state.uid == lane.uid
                         and mover.state.map_id == attack.npc_recipe(broker.realm, lane.uid).map_id == selected.map_id,
                         'NPC_SESSION_CURRENT_MATCHING_DRAINED_MOVER_REQUIRED')
                    candidates.append(writer)
            need(len(candidates) == 1, 'NPC_SESSION_UNAMBIGUOUS_SELECTED_WRITER_REQUIRED')
            if self.factory.config.respawn_policy is not None:
                from tools.local_original_session import npc_respawn
                writer = candidates[0]
                mover = attack.npc_mover(broker.realm, writer, lane.uid)
                lifecycle = broker._npc_respawn
                need(type(lifecycle) is npc_respawn.Service
                     and lifecycle.policy == self.factory.config.respawn_policy,
                     'NPC_SESSION_SAME_RESPAWN_SERVICE_REQUIRED')
                generation = attack.npc_generation(lifecycle, broker.realm, writer, lane.uid)
                need(type(generation) is npc_respawn.Generation and generation.mover is mover,
                     'NPC_SESSION_CURRENT_GENERATION_REQUIRED')
                if lane.generation is None:
                    need(generation.ordinal == 0, 'NPC_SESSION_INITIAL_GENERATION_REQUIRED')
                    lane.generation, lane.mover = generation, mover
                    self._lanes[lane.uid] = lane
                need(generation is lane.generation and mover is lane.mover,
                     'NPC_SESSION_OWNED_GENERATION_CHANGED')
            if server is not None:
                context=packet_contexts[id(candidates[0])]
                need(server.check_current(context) is context
                     and context.mover is broker.realm.service(candidates[0])
                     and context.position is context.mover.snapshot(),
                     'NPC_SESSION_PACKET_BINDING_CHANGED')
            return npc_edge.NpcEdgeBinding(candidates[0], broker, lane.uid)
        except Exception:
            return None

    def submit_goal(self, *, goal, player_life_context=None, target_uid=None):
        """Replace the one explicit goal; no queue, timer or immediate send.

        An in-flight tick finishes its one captured goal. AT_GOAL retains that
        goal until a later submit/close, so an older tick cannot clear a new one.
        """
        lane=self.lane_for(target_uid)
        need(not self._closed and not self.factory._closed, 'NPC_SESSION_CLOSED')
        need(type(goal) is tuple and len(goal) == 2, 'NPC_SESSION_EXPLICIT_GOAL_REQUIRED')
        movement.authority.pack_grid(*goal)
        life = getattr(self.broker, '_player_life', None)
        binding = self.current_binding(_new_goal=True,target_uid=lane.uid) if life is not None else None
        need(life is None or binding is not None, 'NPC_SESSION_PLAYER_LIFE_BINDING_REQUIRED')
        if player_life_context is not None:
            from tools.local_original_session import player_life
            context = player_life_context
            need(type(context) is player_life.Context and context._service is life
                 and life.policy.newlife == player_life.REPEATED_NEWLIFE_POLICY
                 and context._repeat_session is self and context._writer is binding.owner,
                 'NPC_SESSION_REPEAT_SOURCE_ISSUED_CONTEXT_REQUIRED')
            writer, realm, factory, config = binding.owner,self.broker.realm,self.factory,self.factory.config
            registry = realm.registry
            game = registry.resolve(writer)
            mover = attack.npc_mover(realm, writer, lane.uid)
            state, old_goal = mover.state,lane.goal
            token_record = life._tokens.get(id(writer))
            row = life.current_locked(writer,context)  # Last source/callback validation.
            motion = (writer, attack.npc_mover(realm, writer, lane.uid))
            position = realm._movement.get(id(writer))
            need(self.factory is factory and not self._closed and not factory._closed
                 and factory._session is self and factory.config is config and lane.goal is old_goal
                 and goal is not old_goal and self.broker._player_life is life and not life.closed
                 and life._contexts.get(id(writer)) is context and life._cycles.get(id(writer)) is None
                 and life._tokens.get(id(writer)) is token_record and token_record is not None
                 and token_record[0] is writer and token_record[1] is game.selection
                 and token_record[2] is context._token and self.broker.realm is realm
                 and realm.registry is registry and registry._sessions.get(id(writer)) is game
                 and game.connection is writer and not game.closed
                 and motion is not None and motion[0] is writer and motion[1] is mover is context._repeat_mover
                 and mover.state is state and mover.spawn_drained and not mover.closed and not mover.fatal
                 and mover.pending is None and row['operation_lock'].locked()
                 and position is not None and position[0] is writer
                 and position[1]._position is context._position,
                 'NPC_SESSION_REPEAT_FINAL_AUTHORITY_CHANGED')
            import asyncio
            task = asyncio.current_task()
            if task is not None and task.cancelling(): raise asyncio.CancelledError()
            lane.goal_player_life, lane.goal = context._token,goal
            return
        lane.goal_player_life = None if life is None else life.token(binding.owner)
        lane.goal = goal

    def edge_query_pending(self, *, now_ns, target_uid=None):
        """Read-free scheduling hint; never permission to query or send.

        Call tick(allow_edge_query=False) without a reserved memory slot: the
        hint can become stale across the controller lock's await boundary.
        """
        if self._closed or self.factory._closed or not self.factory.config.spawns:
            return False
        lane=self.lane_for(target_uid)
        need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'NPC_SESSION_CLOCK_REQUIRED')
        if self._closed or self.factory._closed or not self.factory.config.spawns or lane.goal is None:
            return False
        binding = self.current_binding(target_uid=lane.uid)
        if binding is None:
            return False
        state = attack.npc_mover(self.broker.realm, binding.owner, lane.uid).state
        return (movement.authority.unpack_grid(state.packed) != lane.goal
                and (state.last_step_ns is None
                     or now_ns >= state.last_step_ns + self.factory.config.interval_ns))

    async def tick(self, *, now_ns, allow_edge_query=True, continuous_motion_lease=None, target_uid=None):
        """One caller-driven poll of the captured goal; never starts a task."""
        if self._closed or self.factory._closed:return Outcome('CLOSED')
        if not self.factory.config.spawns:return Outcome('DISABLED')
        lane=self.lane_for(target_uid)
        if self._closed or self.factory._closed:
            return Outcome('CLOSED')
        if not self.factory.config.spawns:
            return Outcome('DISABLED')
        goal = lane.goal
        if goal is None:
            return Outcome('IDLE')
        return await self.approach(goal=goal, now_ns=now_ns, allow_edge_query=allow_edge_query,
                                   continuous_motion_lease=continuous_motion_lease,target_uid=lane.uid)

    async def approach(self, *, goal, now_ns, allow_edge_query=True, continuous_motion_lease=None, target_uid=None):
        """Try one local axis-sign step using caller's explicit monotonic clock.

        Only known no-send cadence/edge refusals become outcomes. Broker send
        failures and cancellation propagate unchanged, without retry. close()
        suppresses future calls; caller still owns any in-flight broker close.
        """
        lane=self.lane_for(target_uid)
        need(type(goal) is tuple and len(goal) == 2, 'NPC_SESSION_EXPLICIT_GOAL_REQUIRED')
        movement.authority.pack_grid(*goal)
        need(type(now_ns) is int and 0 <= now_ns < (1 << 63), 'NPC_SESSION_CLOCK_REQUIRED')
        need(type(allow_edge_query) is bool, 'NPC_SESSION_TYPED_QUERY_PERMISSION_REQUIRED')
        async with self._lock:
            if self._closed or self.factory._closed:
                return Outcome('CLOSED')
            if not self.factory.config.spawns:
                return Outcome('DISABLED')
            need(lane.last_now_ns is None or now_ns >= lane.last_now_ns,
                 'NPC_SESSION_MONOTONIC_CLOCK_REQUIRED')
            lane.last_now_ns = now_ns
            binding = self.current_binding(target_uid=lane.uid)
            if binding is None:
                return Outcome('UNKNOWN', reason='NPC_SESSION_CURRENT_BINDING_UNAVAILABLE')
            mover = attack.npc_mover(self.broker.realm, binding.owner, lane.uid)
            if self.factory.config.respawn_policy is not None:
                need(mover is lane.mover, 'NPC_SESSION_OWNED_MOVER_CHANGED')
            state = mover.state
            grid = movement.authority.unpack_grid(state.packed)
            if grid == goal:
                # Arrival is still a live gameplay decision. A later lethal
                # hit/removal must retire this captured goal even though no
                # further step/edge query will pass through broker.step_npc.
                try:
                    if self.server_navigation:
                        await self._require_server_arrival(binding,mover,state)
                    else:
                        await self._require_live_arrival(binding,mover,state)
                except ValueError as error:
                    if type(error) is not ValueError or str(error) != 'NPC_HP_DEAD_MOTION_REFUSED':
                        raise
                    if lane.goal is goal:
                        lane.goal = None
                    return Outcome('DEAD', state, reason='NPC_HP_DEAD_MOTION_REFUSED')
                return Outcome('AT_GOAL',state,reason=('SERVER_GRID_ONLY_CLIENT_UNOBSERVED'
                    if self.server_navigation else None))
            if state.last_step_ns is not None and now_ns < state.last_step_ns + mover.interval_ns:
                return Outcome('CADENCE', state)
            if not allow_edge_query and not self.server_navigation:
                return Outcome('OBSERVATION_CADENCE', state)
            delta = tuple((target > current) - (target < current)
                          for current, target in zip(grid, goal))
            direction = movement.authority.DELTAS.index(delta)
            try:
                options = (dict(expected_mover=lane.mover)
                           if self.factory.config.respawn_policy is not None else
                           dict(expected_mover=mover) if self.broker._npc_respawn is not None else {})
                if len(self.factory.config.spawns) > 1:
                    options['target_uid'] = lane.uid
                if continuous_motion_lease is not None:
                    options['continuous_motion_lease'] = continuous_motion_lease
                state = await self.broker.step_npc(binding.owner, goal=goal,
                                                  direction=direction, now_ns=now_ns, **options)
            except ValueError as error:
                if type(error) is ValueError and str(error) == 'NPC_HP_DEAD_MOTION_REFUSED':
                    # A dead actor is a normal gameplay stop. Keep source/owner/
                    # lifetime errors exceptional and never clear a newer goal.
                    if lane.goal is goal:
                        lane.goal = None
                    return Outcome('DEAD', state, reason='NPC_HP_DEAD_MOTION_REFUSED')
                if str(error) == 'NPC_MOVE_LOCAL_CADENCE':
                    return Outcome('CADENCE')
                if str(error) == 'NPC_MOVE_EDGE_BLOCKED_OR_UNKNOWN':
                    edge_result = self.factory.adapter.last_result
                    status = 'BLOCKED' if edge_result['status'] in ('BLOCKED_MASK1','BLOCKED_SERVER_ACTOR') else 'UNKNOWN'
                    return Outcome(status, reason=edge_result['reason'])
                raise
            return Outcome('MOVED', state)

    async def _require_server_arrival(self,binding,mover,state):
        """Server goal/live state only; no client arrival or pose is inferred."""
        broker=self.broker;writer=binding.owner
        rows=[row for claims in broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows)==1,'NPC_SERVER_ARRIVAL_CURRENT_ROW_REQUIRED')
        row,=rows
        async with broker._row_operation(writer,row):
            await broker._checkpoint(writer,row)
            actual,owned,position,current,generation=self.factory.adapter.require_current(state.uid)
            lane=self.lane_for(state.uid)
            need(actual.owner is writer and actual.broker is broker and owned is row
                 and current is mover is lane.mover and mover.state is state
                 and generation is lane.generation and generation.mover is mover
                 and broker.realm.service(writer).snapshot() is position,
                 'NPC_SERVER_ARRIVAL_CURRENT_GENERATION_REQUIRED')

    async def _require_live_arrival(self, binding, mover, state):
        """Reuse original owner/HP authority under the existing selected lock.

        No movement, edge query, packet, new HP authority or lock is produced.
        Revalidate after await: an old state or connection cannot clear a goal.
        """
        lane=self.lane_for(state.uid)
        broker, writer = self.broker, binding.owner
        combat = getattr(broker, '_attack_session', None)
        if combat is None:
            return
        from tools.local_original_session import attack_session
        need(type(combat) is attack_session.AttackSession
             and combat is broker.realm._attack_session,
             'NPC_SESSION_ARRIVAL_CURRENT_COMBAT_REQUIRED')
        rows = [row for claims in broker._claims.values() for row in claims
                if row['writer'] is writer]
        need(len(rows) == 1, 'NPC_SESSION_ARRIVAL_CURRENT_CLAIM_REQUIRED')
        row, = rows
        scope = (broker._row_operation(writer,row) if getattr(broker,'_npc_continuous',None) is not None
                 else row['operation_lock'])
        async with scope:
            current = self.current_binding(target_uid=lane.uid)
            need(current is not None and current.owner is writer and current.broker is broker
                 and attack.npc_mover(broker.realm, writer, lane.uid) is mover and mover.state is state,
                 'NPC_SESSION_ARRIVAL_CURRENT_BINDING_REQUIRED')
            selected = broker.realm.service(writer).snapshot()
            need(await broker._movement_owner(writer, row, selected) is True,
                 'NPC_SESSION_ARRIVAL_CURRENT_OWNER_REQUIRED')
            current = self.current_binding(target_uid=lane.uid)
            need(current is not None and current.owner is writer and current.broker is broker
                 and broker.realm.service(writer).snapshot() is selected
                 and attack.npc_mover(broker.realm, writer, lane.uid) is mover and mover.state is state,
                 'NPC_SESSION_ARRIVAL_AUTHORITY_CHANGED')
            need(broker._attack_session is combat and broker.realm._attack_session is combat,
                 'NPC_SESSION_ARRIVAL_CURRENT_COMBAT_REQUIRED')
            combat.require_live_npc_motion(writer, row, state.uid)

    def retire_continuous_goal(self,target,goal):
        from tools.local_original_session import npc_continuous_retaliation as continuous
        need(type(target) is continuous.TargetReceipt and type(target.issuer) is continuous.Controller
             and target.issuer.broker is self.broker and target.issuer.original.npc_session is self,
             'NPC_SESSION_LITERAL_CONTINUOUS_OWNED_GOAL_REQUIRED')
        state=target.issuer.state_for_exact_receipt(target,allow_retired_lethal=True)
        need(state.owned_goal==(target,goal),'NPC_SESSION_LITERAL_CONTINUOUS_OWNED_GOAL_REQUIRED')
        lane=self._lanes.get(target.target_uid)
        if lane is not None and lane.goal is goal and lane.generation is target.generation and lane.mover is target.mover:
            lane.goal=lane.goal_player_life=None;return True
        return False
    def close(self):
        self._closed=True;self.clear_lanes()
        if self.server_navigation:self.factory.adapter.close()