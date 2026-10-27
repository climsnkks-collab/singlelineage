"""Pure companion decisions on the existing entity-owned world scheduler.

Movement/basic intents and the feature's optional magic consumer share this
scheduler. No damage, packets, MP spending or extra timer loop live here. All
intervals are supplied by the caller from the companion's own admitted data;
follow distance, leash and tile-range defaults are explicitly LOCAL policy.
HOLD forbids every move, including combat positioning, but permits an in-range
basic intent. The installed magic consumer owns CAST/RECOVER decisions.

Wiring under the existing world lock:
* broker/world_combat: owner_attacked(owner.ref, target.ref, now), and
  on_hit(victim.ref, attacker.ref, now) after the real combat event.
* manager.set_commands(...): command_changed(actor.ref, now) wakes the AI.
* the existing WorldView tick calls sync(now) to clean stale actor/owner state
  even when the scheduler skipped an obsolete generation; no new loop/thread.
* WorldView.companion_step(entity, x, y, heading) is the move_consumer seam;
  without it only the registry moves, with no claim of visible client motion.
* world_combat consumes AttackIntent(actor_ref, target_ref, at), revalidates both
  generations/allies/range/current state, adjudicates damage once, and publishes
  through world_visibility. The optional consumer here receives intent only.
* manager release_target(uid, now) connects to NpcAi.release_target for immediate
  monster disengagement. Monster death/removal calls this AI's release_target.
* WorldView.npc_attack branches to world_combat.npc_companion_swing, which
  debits the existing CompanionRecord and invokes manager.die on lethal damage.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from tools.local_original_session.npc_ai import (
    BFS_RADIUS, DELTAS, bounded_path_step, distance, local_line_clear,
)
from tools.local_original_session.world_entities import EntityRef, Kind


class State(str, Enum):
    FOLLOW = 'FOLLOW'
    HOLD = 'HOLD'
    POSITION = 'POSITION'
    ATTACK = 'ATTACK'  # basic intent; spell consumer uses CAST
    CAST = 'CAST'
    RECOVER = 'RECOVER'
    RETURN = 'RETURN'
    DEAD = 'DEAD'


@dataclass(frozen=True, slots=True)
class AttackIntent:
    actor_ref: EntityRef
    target_ref: EntityRef
    at: float


class CompanionAI:
    def __init__(self, view, *, move_interval, attack_interval, tick_interval,
                 attack_range=1, follow_distance=2, owner_leash=15,
                 attack_consumer=None, move_consumer=None):
        self.view = view
        self.move_interval, self.attack_interval = move_interval, attack_interval
        self.tick_interval = self._positive(tick_interval)
        for interval in (move_interval, attack_interval):
            if not callable(interval):
                self._positive(interval)
        if (type(attack_range) is not int or attack_range < 1
                or type(follow_distance) is not int or follow_distance < 1
                or type(owner_leash) is not int or owner_leash < follow_distance):
            raise ValueError('COMPANION_LOCAL_RANGE_INVALID')
        self.attack_range, self.follow_distance = attack_range, follow_distance
        self.owner_leash = owner_leash
        self.attack_consumer, self.move_consumer = attack_consumer, move_consumer
        self.magic = None  # installed by the companion feature at startup

    @staticmethod
    def _positive(value):
        if isinstance(value, bool):
            raise ValueError('COMPANION_INTERVAL_INVALID')
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('COMPANION_INTERVAL_INVALID')
        return value

    def _interval(self, source, runtime):
        return self._positive(source(runtime) if callable(source) else source)

    @property
    def scheduler(self):
        return self.view.runtime.scheduler

    def _runtime(self, ref):
        # Active entries also retain dead runtimes; get_actor intentionally
        # excludes a killed/stale generation, which still needs local cleanup.
        return next((rt for rt in self.view.companions.active.values()
                     if rt.ref == ref), None)

    def _cancel(self, runtime):
        if runtime.handle is not None:
            self.scheduler.cancel(runtime.handle)
        runtime.handle = None

    def _schedule(self, runtime, at):
        self._cancel(runtime)
        entity = self.view.entities.resolve(runtime.ref)
        if (self._runtime(runtime.ref) is not runtime or not runtime.record.alive
                or entity is None or not entity.alive):
            return
        ref = runtime.ref
        runtime.handle = self.scheduler.schedule(
            at, ref, 'companion_ai', lambda now: self.step(ref, now))

    def start(self, ref: EntityRef, now: float):
        runtime = self._runtime(ref)
        if runtime is not None:
            self._schedule(runtime, now)

    def sync(self, now: float):
        """Existing-tick lifetime cleanup, plus wake for a missing AI handle."""
        for runtime in tuple(self.view.companions.active.values()):
            if not runtime.record.alive:
                self._cancel(runtime)
                runtime.target, runtime.action = None, State.DEAD.value
                # die() intentionally invalidates runtime.ref. Inspect the
                # retained corpse by UID while validating the owner's current
                # lifetime normally; departure must remove old-map corpses too.
                corpse = self.view.entities.get(runtime.ref.uid)
                if corpse is None or self._owner(runtime, corpse) is None:
                    self.view.companions.dismiss(runtime.record.character_id, now)
                continue  # same-map owner's corpse remains; never revive/wake
            actor = self.view.entities.resolve(runtime.ref)
            if actor is None or not actor.alive or self._owner(runtime, actor) is None:
                self.view.companions.dismiss(runtime.record.character_id, now)
                continue
            handle = runtime.handle
            if handle is None or handle.cancelled or handle.done:
                self._schedule(runtime, now)

    def command_changed(self, ref: EntityRef, now: float):
        runtime = self._runtime(ref)
        if runtime is not None:
            runtime.target = None
            runtime.position_key = runtime.position_failed = None
            if not runtime.record.alive:
                self._cancel(runtime)
                runtime.action = State.DEAD.value
                return
            runtime.action = runtime.record.movement_mode
            self._schedule(runtime, now)

    def release_target(self, uid: int, now: float):
        """A monster died/left: clear every referring companion immediately."""
        for runtime in tuple(self.view.companions.active.values()):
            if runtime.target is None or runtime.target.uid != uid:
                continue
            runtime.target = None
            runtime.action = (runtime.record.movement_mode if runtime.record.alive
                              else State.DEAD.value)
            self._schedule(runtime, now)

    def _owner(self, runtime, actor):
        owner = self.view.entities.resolve(runtime.owner_ref)
        return owner if (owner is not None and owner.alive and owner.kind is Kind.PC
                         and owner.uid in self.view.pcs
                         and owner.map_id == actor.map_id
                         and self.view.combat.can_be_attacked(owner.uid)) else None

    def _hostile(self, runtime, ref):
        if not isinstance(ref, EntityRef):
            return None
        target = self.view.entities.resolve(ref)
        actor = self.view.entities.resolve(runtime.ref)
        if (target is None or not target.alive or target.kind is not Kind.NPC
                or actor is None or not actor.alive or target.map_id != actor.map_id
                or target.uid == actor.uid
                or self.view.companions.get_actor(target.uid) is not None
                or self.view.companions.are_allies(actor.uid, target.uid)):
            return None
        # A plain NPC is not automatically an enemy (town actors included).
        found = self.view.spawner.slot_for(target.uid)
        return target if found is not None and found[0].active and found[1].hp > 0 else None

    def owner_attacked(self, owner_ref: EntityRef, target_ref: EntityRef, now: float):
        """ASSIST follows every real owner target change, retaining cooldowns."""
        for runtime in tuple(self.view.companions.active.values()):
            if runtime.owner_ref != owner_ref or runtime.record.combat_mode != 'ASSIST':
                continue
            self._select(runtime, target_ref, now)

    def on_hit(self, victim_ref: EntityRef, attacker_ref: EntityRef, now: float):
        """DEFEND reacts to either the owner or the companion being hit."""
        for runtime in tuple(self.view.companions.active.values()):
            if (victim_ref not in (runtime.owner_ref, runtime.ref)
                    or runtime.record.combat_mode != 'DEFEND'):
                continue
            self._select(runtime, attacker_ref, now)

    def _select(self, runtime, target_ref, now):
        actor = self.view.entities.resolve(runtime.ref)
        if actor is None or not actor.alive or not runtime.record.alive:
            return
        if self._owner(runtime, actor) is None:
            self.view.companions.dismiss(runtime.record.character_id, now)
            return
        runtime.target = target_ref if self._hostile(runtime, target_ref) is not None else None
        runtime.position_key = runtime.position_failed = None
        self._schedule(runtime, now)

    def step(self, ref: EntityRef, now: float) -> AttackIntent | None:
        """One decision/move/intent maximum; late ticks never catch up repeats."""
        runtime = self._runtime(ref)
        if runtime is None:
            return None
        self._cancel(runtime)
        actor = self.view.entities.resolve(ref)
        if not runtime.record.alive:
            runtime.target, runtime.action = None, State.DEAD.value
            return None
        if actor is None or not actor.alive:
            # Never leave an alive saved companion attached to a stale actor.
            self.view.companions.dismiss(runtime.record.character_id, now)
            return None
        owner = self._owner(runtime, actor)
        if owner is None:
            self.view.companions.dismiss(runtime.record.character_id, now)
            return None
        target = self._hostile(runtime, runtime.target)
        if runtime.record.combat_mode == 'PASSIVE' or target is None:
            runtime.target = target = None
        returning = distance(actor.x, actor.y, owner.x, owner.y) > self.owner_leash
        if returning:
            runtime.target = target = None
        hold = runtime.record.movement_mode == 'HOLD'

        bags = getattr(self, 'inventory', None)
        if bags is not None:
            bags.potion(runtime, now)

        if self.magic is not None and self.magic.step(runtime, actor, owner, target, now, returning):
            self._schedule(runtime, now + self.tick_interval)
            return None
        if target is not None:
            if self._attack_position(actor, actor.x, actor.y, target):
                runtime.action = State.ATTACK.value
                if now >= runtime.next_attack_at:
                    intent = AttackIntent(ref, target.ref, now)
                    runtime.next_attack_at = now + self._interval(self.attack_interval, runtime)
                    if self.attack_consumer is not None:
                        self.attack_consumer(intent)
                    # The real consumer can kill/remove this target now. Clear
                    # its retained reference before any next callback is armed.
                    if (self._runtime(ref) is runtime and runtime.record.alive
                            and self._hostile(runtime, runtime.target) is None):
                        runtime.target = None
                        runtime.action = runtime.record.movement_mode
                    self._schedule(runtime, min(runtime.next_attack_at, now + self.tick_interval))
                    return intent
                self._schedule(runtime, min(runtime.next_attack_at, now + self.tick_interval))
                return None
            if not hold:
                runtime.action = State.POSITION.value
                self._move(runtime, actor,
                           lambda x, y: self._attack_position(actor, x, y, target),
                           (target.x, target.y), now)
            else:
                runtime.action = State.HOLD.value
        elif hold:
            runtime.action = State.HOLD.value
        else:
            runtime.action = (State.RETURN if returning else State.FOLLOW).value
            if distance(actor.x, actor.y, owner.x, owner.y) > self.follow_distance:
                self._move(runtime, actor,
                           lambda x, y: distance(x, y, owner.x, owner.y) <= self.follow_distance,
                           (owner.x, owner.y), now)
        self._schedule(runtime, now + self.tick_interval)
        return None

    def _attack_position(self, actor, x, y, target):
        return (distance(x, y, target.x, target.y) <= self.attack_range
                and local_line_clear(self.view.terrain, actor.map_id, x, y, target.x, target.y))

    def _can_move(self, actor, x, y, heading, occupied):
        if self.view.terrain is None:
            return False
        dx, dy = DELTAS[heading]
        return (self.view.terrain.can_step(actor.map_id, x, y, heading) is True
                and (x + dx, y + dy) not in occupied)

    def _move(self, runtime, actor, reached, goal, now, tile_allowed=None):
        if now < runtime.next_move_at:
            return
        # All registered actors, including corpses, conservatively occupy their
        # tile. Items do not. Snapshot is valid inside the caller's world lock.
        occupied = {(other.x, other.y) for other in self.view.entities.near(
            actor.map_id, actor.x, actor.y, BFS_RADIUS, alive_only=False)
            if other.uid != actor.uid and other.kind is not Kind.ITEM}
        def can_move(x, y, h):
            dx, dy = DELTAS[h]
            return (self._can_move(actor, x, y, h, occupied)
                    and (tile_allowed is None or tile_allowed(x + dx, y + dy)))
        heading = bounded_path_step((actor.x, actor.y), reached, goal, can_move)
        runtime.next_move_at = now + self._interval(self.move_interval, runtime)
        if heading is None or not self._can_move(actor, actor.x, actor.y, heading, occupied):
            return False
        dx, dy = DELTAS[heading]
        x, y = actor.x + dx, actor.y + dy
        if self.move_consumer is None:
            self.view.entities.move(actor.uid, actor.map_id, x, y, heading)
        else:
            self.move_consumer(actor, x, y, heading)
        runtime.regen_activity = min(runtime.regen_activity, 2)
        return True
