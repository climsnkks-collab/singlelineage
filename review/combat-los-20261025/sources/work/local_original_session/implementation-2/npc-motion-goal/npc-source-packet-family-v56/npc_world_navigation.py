"""Local server NPC walk subset; no client query, sender or autonomous clock.

S32 flags and mask1 probes reuse the existing original-resource decoding facts.
Actor occupancy is explicit local backend policy, not full original Navigation.
The broker retains all MOVE/current/HP/write-drain-commit responsibilities.
"""
import asyncio
from dataclasses import dataclass
import struct

POLICY = 'EXPLICIT_LOCAL_SERVER_NPC_MAP_MASK1_OCCUPANCY'
DELTAS = ((0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1))
EVEN = ((0,0),(1,0),(0,1),(-1,0))
ODD = (((1,-1),(1,0),(-1,0),(-1,-1)),
       ((0,0),(0,1),(-2,1),(-2,0)),
       ((2,0),(2,1),(0,1),(0,0)),
       ((1,0),(1,1),(-1,1),(-1,0)))


class NavigationError(ValueError):
    pass


def _need(value, reason):
    if not value:
        raise NavigationError(reason)


def _grid(packed):
    _need(type(packed) is int and 0 <= packed <= 0xffffffff, 'NAV_GRID_U32')
    return packed & 65535, packed >> 16


def probe_cells(start, direction):
    """Original type4 Coordinate offsets, matching scene_rules.probes only."""
    x,y = _grid(start)
    _need(type(direction) is int and 0 <= direction < 8, 'NAV_DIRECTION')
    dx,dy = DELTAS[direction]
    _need(0 <= x+dx <= 65535 and 0 <= y+dy <= 65535, 'NAV_TARGET_BOUNDARY')
    offsets = (EVEN[direction//2],) if direction % 2 == 0 else tuple(t[direction//2] for t in ODD)
    out = []
    for dx,dy in offsets:
        ax,ay = 2*x-0x8000+dx,y+dy
        gx = ((ax-0x8000) >> 1)+0x8000
        _need(0 <= gx <= 65535 and 0 <= ay <= 65535, 'NAV_PROBE_BOUNDARY')
        sx,sy = (gx>>6)+0x7e00,(ay>>6)+0x7e00
        lx,ly = (0x7f00-sx)*128+ax,(0x7e00-sy)*64+ay
        _need(0 <= sx <= 65535 and 0 <= sy <= 65535
              and 0 <= lx < 128 and 0 <= ly < 64, 'NAV_SEGMENT_BOUNDARY')
        out.append(((sx,sy),(lx,ly)))
    return tuple(out)


def flag_blocked(direction, flags):
    _need(type(direction) is int and 0 <= direction < 8
          and len(flags) == (4 if direction % 2 else 1)
          and all(type(f) is int and 0 <= f <= 65535 for f in flags), 'NAV_FLAGS')
    bits = tuple(bool(f & 1) for f in flags)
    if direction % 2 == 0:
        return bits[0]
    a,b,c,d = bits
    return (a or c) and (b or d) if direction in (3,7) else (a or b) and (c or d)


def parse_flags(raw):
    """S32 floor8192*4, decoration u16+6*n, then 128*64 raw u16 flags.

    Later object/tile/render sections are outside this flags-only consumer.
    Every byte it consumes must exist; no missing-cell default is created.
    """
    _need(type(raw) is bytes and len(raw) <= 64*1024*1024, 'NAV_S32_BYTES')
    pos = 8192*4
    _need(len(raw) >= pos+2, 'NAV_S32_FLOOR_TRUNCATED')
    # The existing source decoder rejects nonzero floor reserved bytes.
    _need(not any(raw[3:pos:4]), 'NAV_S32_FLOOR_RESERVED')
    count = struct.unpack_from('<H',raw,pos)[0]
    pos += 2
    _need(len(raw) >= pos+6*count+16384, 'NAV_S32_FLAGS_TRUNCATED')
    for at in range(pos,pos+6*count,6):
        _need(raw[at] < 128 and raw[at+1] < 64, 'NAV_S32_DECOR_COORD')
    return struct.unpack_from('<8192H',raw,pos+6*count)


@dataclass(frozen=True, slots=True)
class _Actor:
    uid: int
    generation: object
    mover: object
    state: object
    alive: bool


class NpcWorldNavigation:
    """One bound broker/provider lifetime; all queries use its actual row scope.

    Cached flags are immutable authenticated resource data, never client poses.
    UNKNOWN loads are retained for this provider lifetime (no retry/fallback).
    """
    policy = POLICY

    def __init__(self, broker, *, current):
        from tools.local_original_session.broker import PersistentBroker
        _need(type(broker) is PersistentBroker and callable(current), 'NAV_REAL_BROKER')
        self.broker, self.current = broker, current
        self._current_function = getattr(current, '__func__', None)
        self._packet_current_function = getattr(getattr(getattr(current, '__self__', None),
                                                        '_packet_current', None), '__func__', None)
        self._assets = None
        self._provider_failed = False
        self._chunks = {}
        self.closed = False
        self.last_result = dict(status='UNKNOWN',reason='NOT_QUERIED',policy=POLICY)

    def _flags(self, map_id, segment):
        key = (map_id,*segment)
        if key not in self._chunks:
            flags = None
            try:
                if self._assets is None:
                    _need(not self._provider_failed, 'NAV_PROVIDER_UNAVAILABLE')
                    from tools.local_resource_provider.provider import AssetProvider
                    try:
                        self._assets = AssetProvider()
                    except Exception:
                        self._provider_failed = True
                        raise
                # AssetProvider.read authenticates signed catalog/hash/size;
                # never call save/materialize or copy its keys/events to status.
                raw,_ = self._assets.read(f'map/{map_id}/{segment[0]:04x}{segment[1]:04x}.s32')
                flags = parse_flags(raw)
            except Exception:
                pass  # One UNKNOWN entry, never a guessed clear/fallback.
            self._chunks[key] = flags
        return self._chunks[key]

    def _scope(self, uid):
        from tools.local_original_session import npc_edge, movement
        from tools.local_original_session.broker import PersistentBroker, LocalRealm
        b = self.broker
        _need(not self.closed and type(b) is PersistentBroker
              and type(b.realm) is LocalRealm and not b._closing
              and not b.failure.is_set(), 'NAV_BROKER_LIFETIME')
        binding = self.current(target_uid=uid)
        _need(type(binding) is npc_edge.NpcEdgeBinding and binding.broker is b
              and binding.target_uid == uid, 'NAV_SOURCE_BINDING')
        writer = binding.owner
        rows = tuple(r for rows in b._claims.values() for r in rows if r['writer'] is writer)
        _need(len(rows) == 1, 'NAV_CURRENT_CLAIM')
        row, = rows
        _need(row['operation_lock'].locked() and not row['failed'] and not row['joined'], 'NAV_ROW_SCOPE')
        task = asyncio.current_task()
        _need(task is not None, 'NAV_CURRENT_TASK')
        if b._canonical_provider is not None:
            _need(b._canonical_operation_task is task, 'NAV_CANONICAL_TASK_SCOPE')
        policy_row = b.policy._connection(writer)
        _need(row['policy_row'] is policy_row and policy_row.writer is writer
              and policy_row.stage == 1 and not policy_row.eof
              and not policy_row.task_joined and not policy_row.registry_removed
              and b.policy.state == 'OPEN', 'NAV_CURRENT_POLICY_ROW')
        realm = b.realm
        service = realm.service(writer)
        position = service.snapshot()
        _need(type(service) is movement.MovementService and type(position) is movement.Position,
              'NAV_CURRENT_POSITION')
        realm._npc_authority(writer,realm.registry.resolve(writer),service,position)
        life = b._player_life
        if life is None:
            self._resource_counter_scope(writer)
        else:
            life.check_normal_locked(writer)
        return binding,row,position

    def _actors(self, binding, row, position):
        return self._actors_for_writer(binding.owner,row,position)

    def _actors_for_writer(self, writer, row, position):
        from tools.local_original_session import npc, npc_motion, npc_respawn, attack_session, npc_hp
        b = self.broker
        realm,respawn,combat = b.realm,b._npc_respawn,b._attack_session
        _need(type(respawn) is npc_respawn.Service and realm._npc_respawn is respawn
              and type(combat) is attack_session.AttackSession and realm._attack_session is combat
              and not combat.closed and not combat.fatal and type(combat._hp) is npc_hp.Authority,
              'NAV_REGISTERED_OWNERS')
        respawn._canonical()
        bound = realm._npc_motion.get(id(writer))
        _need(bound is not None and bound[0] is writer, 'NAV_CURRENT_MOVER_SET')
        movers = bound[1] if type(bound[1]) is dict else {bound[1].state.uid:bound[1]}
        actors = []
        seen = set()
        for spawn,_ in realm._npc_spawns:
            _need(type(spawn) is npc.NpcSpawn and spawn.uid not in seen, 'NAV_ROSTER_UID')
            seen.add(spawn.uid)
            # Removed actors stay absent. A new generation uses a new component
            # and the existing Death owner then rejects the old removed record.
            removed = combat._notifications is not None and combat._notifications.is_removed(writer,spawn.uid)
            if removed:
                continue
            mover = movers.get(spawn.uid)
            _need(type(mover) is npc_motion.NpcMotion and type(mover.state) is npc_motion.State
                  and mover.state.uid == spawn.uid and mover.state.map_id == spawn.map_id
                  and not mover.closed and not mover.fatal and mover.pending is None
                  and mover.spawn_drained, 'NAV_CURRENT_DRAINED_MOVER')
            key = realm.npc_key(writer,spawn.uid)
            generation = respawn._generations.get(key)
            if generation is None:
                generation = respawn.current_generation(writer,target_uid=spawn.uid)
            frames = realm.npc_frames(writer,target_uid=spawn.uid)
            _need(type(generation) is npc_respawn.Generation
                  and respawn._generations.get(key) is generation
                  and generation.writer is writer and generation.row is row
                  and generation.frames is frames and generation.recipe is spawn
                  and generation.mover is mover, 'NAV_CURRENT_GENERATION')
            lifetime,target = combat._hp_binding(writer,row,spawn.uid)
            entry = combat._hp._entries.get((id(writer),spawn.uid))
            if entry is None:
                hp = combat._hp.provider.initial_hp(target)
            else:
                _need(type(entry) is npc_hp._Entry and entry.writer is writer and entry.row is row
                      and entry.lock is row['operation_lock'] and entry.target == target
                      and len(entry.lifetime) == len(lifetime)
                      and all(a is c for a,c in zip(entry.lifetime,lifetime)), 'NAV_CURRENT_HP_ENTRY')
                hp = entry.hp
            _need(type(hp) is npc_hp.Hp, 'NAV_CURRENT_HP')
            if spawn.map_id == position.map_id:
                actors.append(_Actor(spawn.uid,generation,mover,mover.state,hp.alive))
        _need(set(movers) == seen, 'NAV_EXACT_MOVER_ROSTER')
        return tuple(actors)

    def _resource_counter_scope(self, writer):
        from tools.local_original_session import npc_continuous_retaliation as continuous
        controller = self.broker._npc_continuous
        _need(type(controller) is continuous.Controller and not controller.closed
              and controller.broker is self.broker and controller.life is None
              and controller.packet_runtime is not None and controller.packet_runtime.controller is controller
              and controller.npc_session.broker is self.broker
              and controller.npc_session.factory.adapter.provider is self,
              'NAV_NAMED_RESOURCE_COUNTER_REQUIRED')
        continuous.require_resource_npc_pc(self.broker,controller.binding,writer=writer)

    def _player_scope(self, uid):
        """Actual packet PC owner; no NPC binding or retained-reader substitute."""
        from types import MethodType
        from packet_server import PacketServer
        from packet_peer import PacketCurrent
        from tools.local_original_session import npc_session, movement
        from tools.local_original_session.broker import PersistentBroker, LocalRealm
        b = self.broker
        _need(not self.closed and type(b) is PersistentBroker and type(b.realm) is LocalRealm
              and not b._closing and not b.failure.is_set(), 'NAV_BROKER_LIFETIME')
        factory = getattr(self.current,'__self__',None)
        _need(type(self.current) is MethodType and type(factory) is npc_session.NpcSessionFactory
              and self.current.__func__ is self._current_function
              and self._current_function is npc_session.NpcSessionFactory.current_binding
              and type(factory._packet_current) is MethodType
              and factory._packet_current.__self__ is factory
              and factory._packet_current.__func__ is self._packet_current_function
              and self._packet_current_function is npc_session.NpcSessionFactory._packet_current
              and not factory._closed and factory._session is not None
              and not factory._session._closed and factory._session.broker is b
              and factory.adapter is not None and factory.adapter.provider is self,
              'NAV_PLAYER_BOUND_FACTORY')
        server = factory.packet_server
        _need(type(server) is PacketServer and server.broker is b and server.prepared
              and server.started and not server.closed, 'NAV_PLAYER_PACKET_SERVER')
        candidates = []
        for claims in b._claims.values():
            for row in claims:
                writer = row['writer']
                game = b.realm.registry._sessions.get(id(writer))
                if game is None or game.selection is None:
                    continue
                service = b.realm.service(writer)
                position = service.snapshot()
                _need(type(service) is movement.MovementService and type(position) is movement.Position,
                      'NAV_PLAYER_REGISTERED_POSITION')
                if position.uid == uid:
                    candidates.append((writer,row,position))
        _need(len(candidates) == 1, 'NAV_PLAYER_EXACT_UID')
        writer,row,position = candidates[0]
        _need(row['operation_lock'].locked() and not row['failed'] and not row['joined']
              and b._canonical_operation_task is asyncio.current_task()
              and asyncio.current_task() is not None, 'NAV_PLAYER_OWNED_ROW')
        context = factory._packet_current(writer)
        _need(type(context) is PacketCurrent and context.broker is b and context.writer is writer
              and context.row is row and context.position is position
              and context.game is b.realm.registry.resolve(writer)
              and context.selection is context.game.selection
              and context.mover is b.realm.service(writer), 'NAV_PLAYER_CURRENT')
        if b._player_life is None:
            self._resource_counter_scope(writer)
        else:
            b._player_life.check_normal_locked(writer)
        return factory,context

    def _other_players(self, factory, current):
        """Read actual registered WORLD owners; a busy/unknown row stays UNKNOWN."""
        from packet_peer import PacketCurrent
        from tools.local_original_session import movement
        positions = []
        seen = {current.position.uid}
        for claims in self.broker._claims.values():
            for row in claims:
                writer = row['writer']
                if writer is current.writer:
                    continue
                game = self.broker.realm.registry._sessions.get(id(writer))
                if game is None or game.selection is None:
                    _need(id(writer) not in self.broker.realm._movement,
                          'NAV_OTHER_PLAYER_UNSELECTED_MOVER')
                    continue
                # Only an actually idle other row may use official current.
                # Never infer another lock owner from this task's global scope.
                _need(not row['operation_lock'].locked(), 'NAV_OTHER_PLAYER_IDLE_ROW_REQUIRED')
                context = factory._packet_current(writer)
                position = context.position
                _need(type(context) is PacketCurrent and context.row is row
                      and context.writer is writer and context.game is game
                      and context.selection is game.selection
                      and type(position) is movement.Position and position.uid not in seen,
                      'NAV_OTHER_PLAYER_CURRENT')
                seen.add(position.uid)
                if position.map_id == current.position.map_id:
                    positions.append(position)
        return tuple(positions)

    def player_edge(self, uid, map_id, start, direction, destination):
        """Same local mask1/real occupancy for a packet PC one-step request.

        This is edge adjudication only. Original broker owns MOVE/send/drain/
        Position commit; no current, spawn, clock or player displacement is made.
        """
        self.last_result = dict(status='UNKNOWN',reason='CURRENT_UNKNOWN',policy=POLICY)
        try:
            _need(type(uid) is int and 0 < uid <= 0xffffffff and type(map_id) is int and map_id >= 0,
                  'NAV_TYPED_REQUEST')
            factory,current = self._player_scope(uid)
            position = current.position
            _need(position.uid == uid and position.packed == start and position.map_id == map_id,
                  'NAV_PLAYER_CURRENT_START_MAP')
            actors = self._actors_for_writer(current.writer,current.row,position)
            _need(all(a.uid != uid for a in actors), 'NAV_PLAYER_NPC_UID_COLLISION')
            others = self._other_players(factory,current)
            _need(not any(p.uid == a.uid for p in others for a in actors), 'NAV_ACTOR_UID_COLLISION')
            probes = probe_cells(start,direction)
            x,y = _grid(start)
            dx,dy = DELTAS[direction]
            _need(_grid(destination) == (x+dx,y+dy), 'NAV_EXACT_DESTINATION')
            flags = []
            for segment,(lx,ly) in probes:
                chunk = self._flags(map_id,segment)
                _need(chunk is not None, 'NAV_RESOURCE_UNKNOWN')
                flags.append(chunk[ly*128+lx])
            if flag_blocked(direction,tuple(flags)):
                status = 'BLOCKED_MASK1'
            elif any(a.alive and a.state.packed == destination for a in actors) or any(
                    p.packed == destination for p in others):
                status = 'BLOCKED_SERVER_ACTOR'
            else:
                status = 'CLEAR_SERVER_MAP_SUBSET'
            self.last_result = dict(status=status,reason=None,policy=POLICY,uid=uid,map_id=map_id)
            return status == 'CLEAR_SERVER_MAP_SUBSET'
        except Exception as error:
            reason = str(error) if type(error) is NavigationError else 'NAV_CURRENT_UNKNOWN'
            self.last_result = dict(status='UNKNOWN',reason=reason,policy=POLICY)
            return None

    def current_melee_goal(self, uid, *, position, mover_state):
        """Choose a local free neighbouring goal, never grant a MOVE/edge.

        Preserve the original preferred cell when free. Otherwise choose the
        closest free neighbour in Chebyshev distance, with DELTAS order ties.
        A saturated ring retains the preferred cell for normal BLOCKED waiting.
        """
        _need(type(uid) is int and 0 < uid <= 0xffffffff, 'NAV_UID')
        binding,row,current_position = self._scope(uid)
        _need(current_position is position, 'NAV_GOAL_CURRENT_POSITION')
        actors = self._actors(binding,row,current_position)
        own = tuple(a for a in actors if a.uid == uid)
        _need(len(own) == 1, 'NAV_OWN_LIVE_GENERATION')
        actor, = own
        if not actor.alive:
            raise ValueError('NPC_HP_DEAD_MOTION_REFUSED')
        _need(actor.state is mover_state, 'NAV_GOAL_CURRENT_MOVER_STATE')
        x,y = _grid(actor.state.packed)
        px,py = _grid(current_position.packed)
        _need((x,y) != (px,py), 'NAV_GOAL_OVERLAP')
        preferred = (px-((px>x)-(px<x)),py-((py>y)-(py<y)))
        occupied = {_grid(a.state.packed) for a in actors if a.uid != uid and a.alive}
        free = tuple((px+dx,py+dy) for dx,dy in DELTAS
                     if 0 <= px+dx <= 65535 and 0 <= py+dy <= 65535
                     and (px+dx,py+dy) not in occupied)
        if preferred in free or not free:
            return preferred
        return min(free,key=lambda cell:max(abs(cell[0]-x),abs(cell[1]-y)))

    def require_current(self, uid):
        _need(type(uid) is int and 0 < uid <= 0xffffffff, 'NAV_UID')
        binding,row,position = self._scope(uid)
        actors = self._actors(binding,row,position)
        own = tuple(a for a in actors if a.uid == uid)
        _need(len(own) == 1, 'NAV_OWN_LIVE_GENERATION')
        actor, = own
        if not actor.alive:
            raise ValueError('NPC_HP_DEAD_MOTION_REFUSED')
        return binding,row,position,actor.mover,actor.generation

    def __call__(self, uid, map_id, start, direction, destination):
        self.last_result = dict(status='UNKNOWN',reason='CURRENT_UNKNOWN',policy=POLICY)
        try:
            _need(type(uid) is int and 0 < uid <= 0xffffffff and type(map_id) is int and map_id >= 0,
                  'NAV_TYPED_REQUEST')
            binding,row,position = self._scope(uid)
            actors = self._actors(binding,row,position)
            own = tuple(a for a in actors if a.uid == uid)
            _need(len(own) == 1 and own[0].alive, 'NAV_OWN_LIVE_GENERATION')
            own, = own
            _need(own.state.packed == start and own.state.map_id == map_id == position.map_id,
                  'NAV_CURRENT_START_MAP')
            probes = probe_cells(start,direction)
            x,y = _grid(start)
            dx,dy = DELTAS[direction]
            _need(_grid(destination) == (x+dx,y+dy), 'NAV_EXACT_DESTINATION')
            flags = []
            for segment,(lx,ly) in probes:
                chunk = self._flags(map_id,segment)
                _need(chunk is not None, 'NAV_RESOURCE_UNKNOWN')
                flags.append(chunk[ly*128+lx])
            # No await or actor mutation inside this query. Earlier MOVE drain
            # committed before a later actor enters; collect occupancy afresh.
            if flag_blocked(direction,tuple(flags)):
                status = 'BLOCKED_MASK1'
            elif position.packed == destination or any(a.uid != uid and a.alive
                    and a.state.packed == destination for a in actors):
                status = 'BLOCKED_SERVER_ACTOR'
            else:
                status = 'CLEAR_SERVER_MAP_SUBSET'
            self.last_result = dict(status=status,reason=None,policy=POLICY,uid=uid,map_id=map_id)
            return status == 'CLEAR_SERVER_MAP_SUBSET'
        except Exception as error:
            reason = str(error) if type(error) is NavigationError else 'NAV_CURRENT_UNKNOWN'
            self.last_result = dict(status='UNKNOWN',reason=reason,policy=POLICY)
            return None

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                if self._assets is not None:
                    self._assets.close()
            finally:
                self._assets = None
                self._chunks.clear()
