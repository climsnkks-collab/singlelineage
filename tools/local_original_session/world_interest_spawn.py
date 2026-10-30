"""Nearby spawn groups with dormant slots (GAME_CORE_DESIGN p3, M1 local policy).

A group activates when some PC is within RON tiles of its spawn rectangle and
goes dormant when every PC is farther than ROFF (RON < ROFF). Dormant groups
are skipped by the tick. A living dormant slot keeps its entity (same UID and
generation), HP and position; reactivation does not refill HP. A dead slot
keeps ``corpse_at``/``respawn_at`` and is refilled only when that deadline has
passed, with no virtual kill/drop/EXP. Placement draws random tiles inside the
rectangle (milk cows use their L1J triangular metadata) and needs
``passable(map_id, x, y) is True`` (world_terrain.can_stand
from client S32 mask1; None/no data is refused) plus no current entity
on that tile; after PLACE_ATTEMPTS failures the slot stays empty and retries
after PLACE_RETRY_S. Never forced onto a blocked or unknown tile.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
import random
from types import MappingProxyType

from tools.local_original_session import game_data
from tools.local_original_session.game_data import M1Data, MonsterDef, Rect, SpawnGroupDef
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_extensions import WorldEvents

# Local policy (no client/official source): RON is above the L1J screen limit
# (17 tiles, world_visibility) so a group is filled before its rectangle can be
# on screen; ROFF leaves a 15-tile band so walking along the edge does not
# toggle a group, and exceeds perception 13 + leash 20 of every M1 monster.
RON = 30
ROFF = 45
PLACE_ATTEMPTS = 8
PLACE_RETRY_S = 5.0


def with_dungeon_data(data: M1Data, directory: Path | str | None = None) -> M1Data:
    """Opt in to the existing map1/2 tables before constructing the world.

    Reuses game_data's sourced table readers; M1 items/town/speeds and all
    non-dungeon inputs keep their original identity. Pass this same returned
    data to the spawner, combat and reward owners. It neither loads terrain nor
    enables a native map transition. The six monsters/nine spawn groups are
    the M3_DUNGEON_DATA.md local backend subset, not the full native dungeon.
    """
    directory = game_data.M1_DATA_DIR.parent / 'm3' if directory is None else Path(directory)
    monsters = game_data._monsters(game_data._read(directory, 'monsters.json'))
    spawns = game_data._spawns(game_data._read(directory, 'spawns.json'))
    drops, unresolved = game_data._drops(game_data._read(directory, 'drops.json'))
    merged = replace(data, monsters=MappingProxyType(dict(data.monsters) | dict(monsters)),
                   spawns=data.spawns + spawns,
                   drops=MappingProxyType(dict(data.drops) | dict(drops)),
                   drops_unresolved=data.drops_unresolved + unresolved)
    # The host already uses this startup map-data entry point. Keep its M3
    # behavior, adding M4 only for the explicit cross-map experiment.
    import os
    return game_data.load_m4(merged) if os.environ.get('SL_EXPERIMENT_MAP', '0') == '2' else merged


def need(ok, code):
    if not ok:
        raise ValueError(code)


class SlotState(str, Enum):
    EMPTY = 'empty'
    ALIVE = 'alive'
    WAIT = 'wait'  # dead: corpse until corpse_at, refill at respawn_at


@dataclass(slots=True)
class Slot:
    index: int
    state: SlotState = SlotState.EMPTY
    uid: int | None = None
    hp: int = 0
    home: tuple[int, int] | None = None
    died_at: float | None = None
    corpse_at: float | None = None
    respawn_at: float | None = None
    retry_at: float = 0.0


@dataclass(slots=True)
class Group:
    spec: SpawnGroupDef
    monster: MonsterDef
    slots: list[Slot] = field(default_factory=list)
    active: bool = False


def rect_distance(rect: Rect, x: int, y: int) -> int:
    """Chebyshev tile distance from (x, y) to the inclusive rectangle (0 inside)."""
    dx = max(rect.x1 - x, 0, x - rect.x2)
    dy = max(rect.y1 - y, 0, y - rect.y2)
    return max(dx, dy)


class InterestSpawner:
    """Owns spawn slots; callers serialize access (world lock / tick hook)."""

    def __init__(self, entities: EntityRegistry, data: M1Data, *,
                 passable: Callable[[int, int, int], object],
                 rng: random.Random | None = None, ron: int = RON, roff: int = ROFF,
                 attempts: int = PLACE_ATTEMPTS, retry_s: float = PLACE_RETRY_S):
        need(0 < ron < roff, 'WORLD_SPAWN_RON_LT_ROFF')
        need(callable(passable) and attempts > 0, 'WORLD_SPAWN_PLACEMENT_POLICY')
        self.entities = entities
        self.passable = passable
        self.rng = rng if rng is not None else random.Random()
        self.ron, self.roff, self.attempts, self.retry_s = ron, roff, attempts, retry_s
        self.groups = [Group(spec, data.monsters[spec.template_id],
                             [Slot(i) for i in range(spec.target_count)])
                       for spec in data.spawns]
        self._slots: dict[int, tuple[Group, Slot]] = {}
        # Optional lifecycle policies subscribe once at startup. With no
        # subscribers these folds/events preserve ordinary interest spawning.
        self.events = WorldEvents()

    # ---- queries ---------------------------------------------------------
    def slot_for(self, uid: int) -> tuple[Group, Slot] | None:
        return self._slots.get(uid)

    def visible(self, uid: int) -> bool:
        """A registered NPC of an active group (alive, or a corpse not yet removed)."""
        found = self._slots.get(uid)
        return found is not None and found[0].active

    def monster_for(self, uid: int) -> MonsterDef | None:
        found = self._slots.get(uid)
        return None if found is None else found[0].monster

    # ---- interest --------------------------------------------------------
    def update_interest(self, pcs: Iterable[tuple[int, int, int]], now: float) -> bool:
        """Activate/dormant groups for PC positions ``(map_id, x, y)``; True if entities changed."""
        positions: dict[int, list[tuple[int, int]]] = {}
        for map_id, x, y in pcs:
            positions.setdefault(map_id, []).append((x, y))
        changed = False
        for group in self.groups:
            # Chebyshev distance <= radius is exactly membership in this
            # expanded inclusive rectangle; no nearest-distance value is used.
            radius = self.roff if group.active else self.ron
            rect = group.spec.rect
            interested = False
            for x, y in positions.get(group.spec.map_id, ()):
                if (rect.x1 - radius <= x <= rect.x2 + radius
                        and rect.y1 - radius <= y <= rect.y2 + radius):
                    interested = True
                    break
            interested = self.events.fold('group_interested', interested, group, now)
            if not group.active and interested:
                group.active = True
                changed |= self._refill(group, now, retry_now=True)
            elif group.active and not interested:
                group.active = False  # Slots keep entity/HP/deadlines untouched.
        return changed

    def tick(self, now: float) -> bool:
        """Corpse removal and refill for active groups only."""
        changed = False
        for group in self.groups:
            if group.active:
                changed |= self._refill(group, now, retry_now=False)
        return changed

    # ---- life (death handling arrives with combat) ------------------------
    def mark_dead(self, uid: int, now: float) -> Slot:
        group, slot = self._slots[uid]
        need(slot.state is SlotState.ALIVE, 'WORLD_SPAWN_SLOT_NOT_ALIVE')
        self.entities.kill(uid)  # Corpse stays registered until corpse_at.
        delay = self.rng.randint(group.spec.respawn_delay_min_ms, group.spec.respawn_delay_max_ms)
        slot.state, slot.hp, slot.died_at = SlotState.WAIT, 0, now
        slot.corpse_at = now + group.monster.corpse_ms / 1000
        slot.respawn_at = slot.corpse_at + delay / 1000
        slot.respawn_at = self.events.fold('respawn_at', slot.respawn_at, group, slot, now)
        self.events.emit('dead', group, slot, now)
        return slot

    def set_hp(self, uid: int, hp: int) -> None:
        _, slot = self._slots[uid]
        need(slot.state is SlotState.ALIVE and 0 < hp, 'WORLD_SPAWN_LIVE_HP_REQUIRED')
        slot.hp = hp
        group, _ = self._slots[uid]
        self.events.emit('hp_changed', group, slot)

    # ---- internals -------------------------------------------------------
    def _refill(self, group: Group, now: float, *, retry_now: bool) -> bool:
        changed = False
        for slot in group.slots:
            if slot.state is SlotState.WAIT:
                if slot.uid is not None and slot.corpse_at <= now:
                    self._remove_corpse(slot)
                    changed = True
                if self.events.chain('hold_refill', group, slot, now):
                    continue
                if slot.respawn_at <= now:
                    if slot.uid is not None:
                        self._remove_corpse(slot)
                    slot.state = SlotState.EMPTY
                    slot.died_at = slot.corpse_at = slot.respawn_at = None
                    slot.retry_at = now
            if slot.state is SlotState.EMPTY and (retry_now or slot.retry_at <= now):
                if self.events.chain('hold_refill', group, slot, now):
                    continue
                changed |= self._place(group, slot, now)
        return changed

    def _remove_corpse(self, slot: Slot) -> None:
        if self.entities.get(slot.uid) is not None:
            self.entities.remove(slot.uid)
        self._slots.pop(slot.uid, None)
        slot.uid = None

    def _occupied(self, map_id: int, x: int, y: int) -> bool:
        return any(entity.kind is not Kind.ITEM  # ground items never block a spawn
                   for entity in self.entities.near(map_id, x, y, 0, alive_only=False))

    def _place(self, group: Group, slot: Slot, now: float) -> bool:
        spec, rect = group.spec, group.spec.rect
        for _ in range(self.attempts):
            restored = self.events.first('spawn_position', group, slot, now)
            if restored is not None:
                x, y, heading = restored
            elif spec.template_id == 188 and spec.placement is not None and spec.placement.get('kind') == 'triangular':
                # Milk cow: L1J L1Spawn draws two independent differences,
                # rather than sampling uniformly over their support rectangle.
                ox, oy = spec.placement['origin']
                rx, ry = spec.placement['random']
                x = ox + self.rng.randrange(rx) - self.rng.randrange(rx)
                y = oy + self.rng.randrange(ry) - self.rng.randrange(ry)
            else:
                x, y = self.rng.randint(rect.x1, rect.x2), self.rng.randint(rect.y1, rect.y2)
            try:
                ok = self.passable(spec.map_id, x, y)
            except Exception:
                ok = None
            if ok is not True or self._occupied(spec.map_id, x, y):
                continue
            heading = restored[2] if restored is not None else self.rng.randrange(8)
            entity = self.entities.add(Kind.NPC, spec.map_id, x, y, heading=heading,
                                       template_id=spec.template_id)
            slot.state, slot.uid, slot.hp, slot.home = SlotState.ALIVE, entity.uid, group.monster.hp, (x, y)
            self._slots[entity.uid] = (group, slot)
            slot.hp = self.events.fold('spawn_hp', slot.hp, group, slot)
            self.events.emit('spawned', group, slot, now)
            return True
        slot.retry_at = now + self.retry_s  # Keep the vacancy; no forced tile.
        return False
