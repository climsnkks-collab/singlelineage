"""Per-monster AI on the world scheduler: IDLE/WANDER/CHASE/ATTACK/FLEE/RETURN.

GAME_CORE_DESIGN p3 "AI와 타이머". Every M1 monster is non-aggressive (L1J agro=0),
so those four fight only the PC that attacked them. Aggressive definitions
recognize a living attackable PC inside perception_range. One entry per living
monster of an active spawn group, owned by its EntityRef: death bumps the
generation (stale entries never run) and dormancy/death/removal call
cancel_owner. Movement is one tile per data move_interval_ms, checked by
WorldTerrain.can_step plus current occupancy; chasing uses a bounded BFS whose
best frontier node is an intermediate goal when the target is farther away.
Attacks repeat every attack_interval_ms while within attack_range and local
static-edge LOS, including point-blank ranged attacks. Reference behavior:
D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/model/Instance/
L1NpcInstance.java:427-450 (zero attack speed + positive move speed flees;
otherwise attack in range, no minimum distance), model/L1Character.java:378-386
(range + glanceCheck), Instance/L1MonsterInstance.java:114-129,174-176 (aggro
and living targets). These are backend references, not original-client proof.
MonsterDef exposes intervals, not raw L1J atkspeed/passispeed: their zero/positive
sentinels are the local adapter for FLEE; current M1 intervals are all positive.
LOS is a local Bresenham tile ray requiring can_step is True on every edge;
it is not L1J glanceCheck or verified client projectile/door geometry. Occupancy
does not block the ray; unknown terrain does. Leash (home
distance > leash_range), target loss (logout, off screen, other map) or the
target PC's death (release_target, also can_be_attacked) end the chase with
RETURN, then IDLE at home.
Runs inside scheduler callbacks / tick hooks under the world lock: never calls
WorldRuntime.dispatch_now. Registered living companions are eligible targets via
view.companions, independently of the existing PC combat predicate. The future
WorldView.npc_attack(entity, monster, target_uid, now) consumer must branch for
companions and debit their record HP; its current PC-only implementation is not
that consumer. Target selection / fake-view callbacks alone prove no damage.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from enum import Enum
import random
from typing import TYPE_CHECKING

from tools.local_original_session.game_data import MonsterDef
from tools.local_original_session.world_entities import Entity, EntityRef, Kind
from tools.local_original_session.world_scheduler import Handle

if TYPE_CHECKING:
    from tools.local_original_session.world_visibility import WorldView

DELTAS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))

# Local policy (no client/official source).
IDLE_MIN_S, IDLE_MAX_S = 3.0, 8.0     # pause between wanders
WANDER_RADIUS = 5                     # wander stays this close to home
WANDER_MAX_STEPS = 4
BFS_RADIUS = 10                       # bounded search window around the monster
BFS_MAX_NODES = 500
BLOCKED_LIMIT = 6                     # failed step attempts before giving up a goal
FLEE_DISTANCE = 15                    # L1NpcInstance.java:429; no skill-40 adapter


class State(str, Enum):
    IDLE = 'idle'
    WANDER = 'wander'
    CHASE = 'chase'
    ATTACK = 'attack'
    FLEE = 'flee'
    RETURN = 'return'


@dataclass(slots=True)
class Brain:
    uid: int
    ref: EntityRef
    monster: MonsterDef
    home: tuple[int, int]
    state: State = State.IDLE
    target: int | None = None
    wander_left: int = 0
    wander_heading: int = 0
    blocked: int = 0
    next_move_at: float = 0.0
    next_attack_at: float = 0.0
    handle: Handle | None = field(default=None, repr=False)
    target_ref: EntityRef | None = None


def distance(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def heading_to(fx: int, fy: int, tx: int, ty: int) -> int:
    dx, dy = (tx > fx) - (tx < fx), (ty > fy) - (ty < fy)
    return DELTAS.index((dx, dy)) if (dx, dy) != (0, 0) else 0


def local_line_clear(terrain, map_id: int, x: int, y: int, tx: int, ty: int) -> bool:
    """Shared LOCAL static mask1 ray; absent/unknown terrain refuses an attack.

    This is not the original projectile predicate or a dynamic-door decision.
    """
    if terrain is None:
        return False
    dx, dy = abs(tx - x), abs(ty - y)
    sx, sy = (tx > x) - (tx < x), (ty > y) - (ty < y)
    error = dx - dy
    while (x, y) != (tx, ty):
        twice = 2 * error
        nx, ny = x, y
        if twice > -dy:
            error -= dy
            nx += sx
        if twice < dx:
            error += dx
            ny += sy
        heading = heading_to(x, y, nx, ny)
        if terrain.can_step(map_id, x, y, heading) is not True:
            return False
        x, y = nx, ny
    return True


def bounded_path_step(start, reached, goal, can_step, *, radius=BFS_RADIUS,
                      max_nodes=BFS_MAX_NODES, start_checked=False) -> int | None:
    """Pure bounded BFS over a caller-owned terrain/occupancy snapshot.

    ``can_step(x, y, heading)`` must refuse unknown terrain and occupied cells.
    The closest explored node is an intermediate goal for a distant destination.
    Pass ``start_checked`` only after ``reached(*start)`` returned False.
    """
    if not start_checked and reached(*start):
        return None
    first, depth = {start: None}, {start: 0}
    queue = deque([start])
    best, best_key = None, (distance(*start, *goal), 0)
    while queue and len(first) < max_nodes:
        x, y = queue.popleft()
        for heading, (dx, dy) in enumerate(DELTAS):
            nxt = (x + dx, y + dy)
            if nxt in first or distance(*nxt, *start) > radius:
                continue
            if not can_step(x, y, heading):
                continue
            first[nxt] = heading if (x, y) == start else first[(x, y)]
            depth[nxt] = depth[(x, y)] + 1
            if reached(*nxt):
                return first[nxt]
            key = (distance(*nxt, *goal), depth[nxt])
            if key < best_key:
                best, best_key = nxt, key
            queue.append(nxt)
    return None if best is None else first[best]


class NpcAi:
    def __init__(self, view: 'WorldView', rng: random.Random | None = None):
        self.view = view
        self.rng = rng if rng is not None else random.Random()
        self.brains: dict[int, Brain] = {}

    # ---- lifetime ----------------------------------------------------------
    @property
    def scheduler(self):
        return self.view.runtime.scheduler

    def sync(self, now: float) -> None:
        """Brains for living monsters of active groups only; cancel the rest."""
        spawner, entities = self.view.spawner, self.view.entities
        for uid, brain in tuple(self.brains.items()):
            found = spawner.slot_for(uid)
            if found is None or not found[0].active or not entities.is_current(brain.ref):
                self.drop(uid)
        for group in spawner.groups:
            if not group.active:
                continue
            for slot in group.slots:
                if slot.uid is None or slot.uid in self.brains:
                    continue
                entity = entities.get(slot.uid)
                if entity is None or not entity.alive:
                    continue
                brain = Brain(entity.uid, entity.ref, group.monster, slot.home or (entity.x, entity.y))
                self.brains[entity.uid] = brain
                self._idle(brain, now)
        # Tick-time recognition does not wait for the 3-8s wander timer. Returning
        # monsters finish going home before acquiring another target.
        for brain in self.brains.values():
            if brain.state in (State.IDLE, State.WANDER) and brain.monster.aggressive:
                entity = entities.resolve(brain.ref)
                if entity is not None and entity.alive:
                    self._perceive(brain, entity, now)

    def drop(self, uid: int) -> None:
        brain = self.brains.pop(uid, None)
        if brain is not None:
            self.scheduler.cancel_owner(brain.ref)
            brain.handle = None

    def _schedule(self, brain: Brain, at: float) -> None:
        if brain.handle is not None:
            self.scheduler.cancel(brain.handle)
        uid = brain.uid
        brain.handle = self.scheduler.schedule(at, brain.ref, 'npc_ai', lambda now: self._act(uid, now))

    # ---- inputs ------------------------------------------------------------
    def on_hit(self, uid: int, pc_uid: int, now: float) -> None:
        """A PC or registered living companion attacked this monster: retaliate."""
        brain = self.brains.get(uid)
        if brain is None or brain.target == pc_uid:
            return
        attacker = self.view.entities.get(pc_uid)
        # Preserve the existing PC event path. Only the new companion branch
        # needs manager admission and generation retention here.
        target_ref = None
        if attacker is None or attacker.kind is not Kind.PC:
            entity = self.view.entities.resolve(brain.ref)
            if entity is None or not self._pc_ok(entity, pc_uid):
                return
            target_ref = attacker.ref
        brain.target, brain.state, brain.blocked = pc_uid, State.CHASE, 0
        brain.target_ref = target_ref
        self._schedule(brain, max(now, min(brain.next_move_at, brain.next_attack_at)))

    def release_target(self, pc_uid: int, now: float) -> None:
        """That PC/companion died or left: immediately stop targeting it."""
        for brain in self.brains.values():
            if brain.target == pc_uid:
                brain.target, brain.state, brain.blocked = None, State.RETURN, 0
                brain.target_ref = None
                self._schedule(brain, max(now, brain.next_move_at))

    # ---- behaviour ---------------------------------------------------------
    def _act(self, uid: int, now: float) -> None:
        # Optional feature-owned status reader. A world without magic retains
        # the exact ordinary path; no feature import or required callback.
        reader = getattr(self.view, 'magic_status', None)
        brain = self.brains.get(uid)
        if reader is None or brain is None:
            return self._act_normal(uid, now)
        status = reader(uid, now)
        if status.get('blocked'):
            self._schedule(brain, now + .25)
            return
        original = brain.monster
        brain.monster = replace(original,
            move_interval_ms=int(original.move_interval_ms * status.get('move_factor', 1)),
            attack_interval_ms=int(original.attack_interval_ms * status.get('attack_factor', 1)))
        try:
            if status.get('sight') is not None and brain.target is not None:
                entity, target = self.view.entities.resolve(brain.ref), self.view.entities.get(brain.target)
                if (entity is not None and target is not None and
                        distance(entity.x, entity.y, target.x, target.y) > status['sight']):
                    self._schedule(brain, now + .25)
                    return
            return self._act_normal(uid, now)
        finally:
            brain.monster = original

    def _act_normal(self, uid: int, now: float) -> None:
        brain = self.brains.get(uid)
        if brain is None:
            return
        brain.handle = None
        entity = self.view.entities.resolve(brain.ref)
        if entity is None or not entity.alive:
            self.drop(uid)
            return
        if brain.target is not None and not self._target_ok(brain, entity):
            brain.target, brain.state, brain.blocked = None, State.RETURN, 0
            brain.target_ref = None
        if brain.state in (State.CHASE, State.ATTACK, State.FLEE):
            self._fight(brain, entity, now)
        elif brain.state is State.RETURN:
            self._return(brain, entity, now)
        elif brain.state is State.WANDER:
            self._wander(brain, entity, now)
        else:
            self._start_wander(brain, entity, now)

    def _target_ok(self, brain: Brain, entity: Entity) -> bool:
        return (self._pc_ok(entity, brain.target)
                and (brain.target_ref is None or self.view.entities.is_current(brain.target_ref))
                and distance(entity.x, entity.y, *brain.home) <= brain.monster.leash_range)

    def _pc_ok(self, entity: Entity, pc_uid: int | None) -> bool:
        from tools.local_original_session.world_visibility import in_screen
        pc = self.view.entities.get(pc_uid)
        if (pc is None or not pc.alive or pc.map_id != entity.map_id
                or not in_screen(pc.x, pc.y, entity.x, entity.y)):
            return False
        if pc.kind is Kind.PC:
            return pc_uid in self.view.pcs and self.view.combat.can_be_attacked(pc_uid)
        companions = getattr(self.view, 'companions', None)
        return (pc.kind is Kind.NPC and companions is not None
                and companions.get_actor(pc_uid) is not None
                and companions.can_be_attacked(pc_uid))

    def _perceive(self, brain: Brain, entity: Entity, now: float) -> None:
        if distance(entity.x, entity.y, *brain.home) > brain.monster.leash_range:
            return
        candidates = [pc for pc in self.view.entities.near(
            entity.map_id, entity.x, entity.y, brain.monster.perception_range)
            if self._pc_ok(entity, pc.uid)]
        if candidates:
            # Local policy: nearest admitted target, then UID; no hate model.
            pc = min(candidates, key=lambda pc: (distance(entity.x, entity.y, pc.x, pc.y), pc.uid))
            self.on_hit(brain.uid, pc.uid, now)

    def _line_clear(self, map_id: int, x: int, y: int, tx: int, ty: int) -> bool:
        """Local static mask1 LOS: every Bresenham edge must be known and clear."""
        return local_line_clear(self.view.terrain, map_id, x, y, tx, ty)

    def _attack_position(self, brain: Brain, entity: Entity, x: int, y: int, pc: Entity) -> bool:
        return (distance(x, y, pc.x, pc.y) <= brain.monster.attack_range
                and self._line_clear(entity.map_id, x, y, pc.x, pc.y))

    def _fight(self, brain: Brain, entity: Entity, now: float) -> None:
        pc = self.view.entities.get(brain.target)
        if brain.monster.attack_interval_ms == 0:
            if brain.monster.move_interval_ms > 0:
                self._flee(brain, entity, pc, now)
            else:
                self._idle(brain, now)  # stationary non-attacker: no zero-delay swing
            return
        if self._attack_position(brain, entity, entity.x, entity.y, pc):
            brain.state = State.ATTACK
            if now >= brain.next_attack_at:
                target = brain.target
                self.view.npc_attack(entity, brain.monster, target, now)
                brain.next_attack_at = now + brain.monster.attack_interval_ms / 1000
                if brain.target != target or brain.state is not State.ATTACK:
                    return  # PC death release_target already scheduled RETURN
            self._schedule(brain, brain.next_attack_at)
            return
        if brain.monster.move_interval_ms <= 0:
            self._idle(brain, now)
            return
        brain.state = State.CHASE
        if now < brain.next_move_at:
            self._schedule(brain, brain.next_move_at)
            return
        step = self._path_step(entity, lambda x, y: self._attack_position(brain, entity, x, y, pc),
                               (pc.x, pc.y))
        if not self._step(brain, entity, step, now):
            brain.blocked += 1
            if brain.blocked > BLOCKED_LIMIT:
                brain.target, brain.state, brain.blocked = None, State.RETURN, 0
                brain.target_ref = None
        self._schedule(brain, brain.next_move_at)

    def _flee(self, brain: Brain, entity: Entity, pc: Entity, now: float) -> None:
        """Zero-attack mobile NPC only; local step choice retains terrain/occupancy."""
        brain.state = State.FLEE
        current = distance(entity.x, entity.y, pc.x, pc.y)
        if current > FLEE_DISTANCE:
            brain.target, brain.state, brain.blocked = None, State.RETURN, 0
            brain.target_ref = None
            self._schedule(brain, max(now, brain.next_move_at))
            return
        if now < brain.next_move_at:
            self._schedule(brain, brain.next_move_at)
            return
        # Prefer directly away; equally distant alternatives follow heading order.
        away = heading_to(pc.x, pc.y, entity.x, entity.y)
        choices = [(distance(entity.x + dx, entity.y + dy, pc.x, pc.y), heading)
                   for heading, (dx, dy) in enumerate(DELTAS)
                   if distance(entity.x + dx, entity.y + dy, pc.x, pc.y) > current
                   and self._can_move(entity, entity.x, entity.y, heading)]
        step = max(choices, key=lambda pair: (pair[0], pair[1] == away, -pair[1]))[1] if choices else None
        if not self._step(brain, entity, step, now):
            brain.blocked += 1
            if brain.blocked > BLOCKED_LIMIT:
                brain.target, brain.state, brain.blocked = None, State.RETURN, 0
                brain.target_ref = None
        self._schedule(brain, brain.next_move_at)

    def _return(self, brain: Brain, entity: Entity, now: float) -> None:
        hx, hy = brain.home
        if distance(entity.x, entity.y, hx, hy) <= 1 or brain.monster.move_interval_ms <= 0:
            brain.blocked = 0
            self._idle(brain, now)
            return
        if now < brain.next_move_at:
            self._schedule(brain, brain.next_move_at)
            return
        step = self._path_step(entity, lambda x, y: distance(x, y, hx, hy) <= 1, (hx, hy))
        if not self._step(brain, entity, step, now):
            brain.blocked += 1
            if brain.blocked > BLOCKED_LIMIT:
                # Local policy: stop where it is (never teleport home); wander resumes from here.
                brain.blocked = 0
                self._idle(brain, now)
                return
        self._schedule(brain, brain.next_move_at)

    def _idle(self, brain: Brain, now: float) -> None:
        brain.state, brain.target, brain.wander_left = State.IDLE, None, 0
        brain.target_ref = None
        self._schedule(brain, max(now, brain.next_move_at) + self.rng.uniform(IDLE_MIN_S, IDLE_MAX_S))

    def _start_wander(self, brain: Brain, entity: Entity, now: float) -> None:
        if brain.monster.move_interval_ms <= 0:
            self._idle(brain, now)
            return
        brain.state = State.WANDER
        brain.wander_left = self.rng.randint(1, WANDER_MAX_STEPS)
        brain.wander_heading = self.rng.randrange(8)
        self._wander(brain, entity, now)

    def _wander(self, brain: Brain, entity: Entity, now: float) -> None:
        if now < brain.next_move_at:
            self._schedule(brain, brain.next_move_at)
            return
        dx, dy = DELTAS[brain.wander_heading]
        nx, ny = entity.x + dx, entity.y + dy
        if (brain.wander_left <= 0 or distance(nx, ny, *brain.home) > WANDER_RADIUS
                or not self._step(brain, entity, brain.wander_heading, now)):
            self._idle(brain, now)
            return
        brain.wander_left -= 1
        if brain.wander_left <= 0:
            self._idle(brain, now)
        else:
            self._schedule(brain, brain.next_move_at)

    # ---- movement ----------------------------------------------------------
    def _free(self, map_id: int, x: int, y: int, self_uid: int) -> bool:
        # Ground items never block a step (L1J: items share tiles with actors).
        return not any(other.uid != self_uid and other.kind is not Kind.ITEM
                       for other in self.view.entities.near(map_id, x, y, 0))

    def _can_move(self, entity: Entity, x: int, y: int, heading: int, *,
                  occupied: set[tuple[int, int]] | None = None) -> bool:
        dx, dy = DELTAS[heading]
        return (self.view.terrain.can_step(entity.map_id, x, y, heading) is True
                and (self._free(entity.map_id, x + dx, y + dy, entity.uid)
                     if occupied is None else (x + dx, y + dy) not in occupied))

    def _step(self, brain: Brain, entity: Entity, heading: int | None, now: float) -> bool:
        if heading is None or not self._can_move(entity, entity.x, entity.y, heading):
            brain.next_move_at = now + brain.monster.move_interval_ms / 1000
            return False
        dx, dy = DELTAS[heading]
        self.view.npc_step(entity, entity.x + dx, entity.y + dy, heading)
        brain.blocked = 0
        brain.next_move_at = now + brain.monster.move_interval_ms / 1000
        return True

    def _path_step(self, entity: Entity, reached, goal: tuple[int, int]) -> int | None:
        """First heading of a bounded BFS path; the closest explored node stands in for a far goal."""
        start = (entity.x, entity.y)
        if reached(*start):
            return None
        # The synchronous search runs under the world lock: occupancy cannot
        # change mid-search. Query its bounded window once instead of querying
        # and sorting a bucket for every explored edge. Rebuild on every search
        # so later movement, death and removal are immediately reflected.
        occupied = {(other.x, other.y) for other in self.view.entities.near(
            entity.map_id, entity.x, entity.y, BFS_RADIUS)
            if other.uid != entity.uid and other.kind is not Kind.ITEM}
        return bounded_path_step(start, reached, goal,
                                 lambda x, y, heading: self._can_move(
                                     entity, x, y, heading, occupied=occupied),
                                 start_checked=True)
