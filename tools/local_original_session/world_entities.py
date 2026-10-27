"""World entity registry: PC/NPC/ground-item UID, generation, position, life.

Pure in-memory state for one local realm. HP, growth and items stay with their
existing owners; this only ties identity, location and liveness together.
Death or removal changes generation so stale references stop resolving.
Dead/removed UIDs are never reused. An inactive PC keeps its profile identity,
outside the spatial index, and may enter again with a fresh generation.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum

# PC is profile_uid=1, configured NPC spawns use small explicit UIDs (2, ...),
# inventory instances grow by max(used)+1 from small values; start high in u32.
DEFAULT_UID_START = 0x10000000
UID_MAX = 0xffffffff
DEFAULT_BUCKET = 16


class Kind(str, Enum):
    PC = 'pc'
    NPC = 'npc'
    ITEM = 'item'


class UidAllocator:
    """Monotonic UID source; never hands out the same value twice."""

    def __init__(self, start: int = DEFAULT_UID_START, stop: int = UID_MAX + 1):
        if not 0 < start < stop <= UID_MAX + 1:
            raise ValueError('WORLD_UID_RANGE_INVALID')
        self._next = start
        self._stop = stop

    def __call__(self) -> int:
        if self._next >= self._stop:
            raise ValueError('WORLD_UID_EXHAUSTED')
        uid = self._next
        self._next += 1
        return uid


@dataclass(frozen=True, slots=True)
class EntityRef:
    uid: int
    generation: int


@dataclass(slots=True)
class Entity:
    uid: int
    generation: int
    kind: Kind
    map_id: int
    x: int
    y: int
    heading: int = 0
    alive: bool = True
    template_id: int | None = None

    @property
    def ref(self) -> EntityRef:
        return EntityRef(self.uid, self.generation)


def _distance(ax: int, ay: int, bx: int, by: int) -> int:
    # Tile distance (Chebyshev), matching 8-direction movement.
    return max(abs(ax - bx), abs(ay - by))


class EntityRegistry:
    def __init__(self, *, allocate_uid: Callable[[], int] | None = None,
                 bucket_size: int = DEFAULT_BUCKET):
        if bucket_size <= 0:
            raise ValueError('WORLD_BUCKET_SIZE_INVALID')
        self._allocate = allocate_uid if allocate_uid is not None else UidAllocator()
        self._bucket = bucket_size
        self._entities: dict[int, Entity] = {}
        self._buckets: dict[tuple[int, int, int], set[int]] = {}
        self._used: set[int] = set()

    def __len__(self) -> int:
        return len(self._entities)

    def __iter__(self) -> Iterator[Entity]:
        return iter(tuple(self._entities.values()))

    def _key(self, map_id: int, x: int, y: int) -> tuple[int, int, int]:
        return map_id, x // self._bucket, y // self._bucket

    def _index(self, entity: Entity) -> None:
        self._buckets.setdefault(self._key(entity.map_id, entity.x, entity.y), set()).add(entity.uid)

    def _unindex(self, entity: Entity) -> None:
        key = self._key(entity.map_id, entity.x, entity.y)
        bucket = self._buckets.get(key)
        if bucket is not None:
            bucket.discard(entity.uid)
            if not bucket:
                del self._buckets[key]

    def add(self, kind: Kind, map_id: int, x: int, y: int, *, heading: int = 0,
            template_id: int | None = None, uid: int | None = None) -> Entity:
        """Register a new entity. Pass ``uid`` only for an existing identity (the PC)."""
        if uid is None:
            uid = self._allocate()
        if uid in self._used:
            raise ValueError('WORLD_UID_ALREADY_USED')
        self._used.add(uid)
        entity = Entity(uid, 1, Kind(kind), map_id, x, y, heading, True, template_id)
        self._entities[uid] = entity
        self._index(entity)
        return entity

    def get(self, uid: int) -> Entity | None:
        return self._entities.get(uid)

    def resolve(self, ref: EntityRef) -> Entity | None:
        entity = self._entities.get(ref.uid)
        if entity is None or entity.generation != ref.generation:
            return None
        return entity

    def is_current(self, ref: EntityRef) -> bool:
        return self.resolve(ref) is not None

    def deactivate_pc(self, uid: int) -> Entity:
        """End a selected PC's life and occupancy without unburning its profile UID."""
        entity = self._entities[uid]
        if entity.kind is not Kind.PC:
            raise ValueError('WORLD_PC_REQUIRED')
        self._unindex(entity)  # even a dead PC may still have corpse occupancy
        entity.alive = False
        entity.generation += 1
        return entity

    def activate_pc(self, uid: int, map_id: int, x: int, y: int) -> Entity:
        """Re-enter a preserved inactive PC identity, never an NPC/item/removed UID."""
        entity = self._entities[uid]
        if entity.kind is not Kind.PC or entity.alive:
            raise ValueError('WORLD_INACTIVE_PC_REQUIRED')
        self._unindex(entity)
        entity.generation += 1
        entity.alive = True
        entity.map_id, entity.x, entity.y = map_id, x, y
        self._index(entity)
        return entity

    def move(self, uid: int, map_id: int, x: int, y: int, heading: int | None = None) -> Entity:
        entity = self._entities[uid]
        self._unindex(entity)
        entity.map_id, entity.x, entity.y = map_id, x, y
        if heading is not None:
            entity.heading = heading
        self._index(entity)
        return entity

    def kill(self, uid: int) -> Entity:
        """Mark dead (corpse stays registered); old references become stale."""
        entity = self._entities[uid]
        entity.alive = False
        entity.generation += 1
        return entity

    def remove(self, uid: int) -> Entity:
        entity = self._entities.pop(uid)
        self._unindex(entity)
        entity.alive = False
        entity.generation += 1
        return entity

    def near(self, map_id: int, x: int, y: int, radius: int, *, kind: Kind | None = None,
             alive_only: bool = True) -> list[Entity]:
        """Entities within tile ``radius`` of (x, y) on ``map_id``, ordered by UID."""
        size = self._bucket
        found = []
        for bx in range((x - radius) // size, (x + radius) // size + 1):
            for by in range((y - radius) // size, (y + radius) // size + 1):
                for uid in self._buckets.get((map_id, bx, by), ()):
                    entity = self._entities[uid]
                    if alive_only and not entity.alive:
                        continue
                    if kind is not None and entity.kind is not Kind(kind):
                        continue
                    if _distance(entity.x, entity.y, x, y) <= radius:
                        found.append(entity)
        found.sort(key=lambda entity: entity.uid)
        return found
