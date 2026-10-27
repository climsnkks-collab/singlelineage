"""Pure M1 ground drops, pickup rules and scheduler lifetime; no packets/store.

L1J reference root: D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/.
clientpackets/C_PickUpItem.java checks positive count <= 2,000,000,000,
available quantity, nonstackable count=1, owner and tile-line distance <=3.
types/Point.java:110-112 defines that distance as Chebyshev. DropTable.java
:330-380 chooses a passable adjacent direction; L1Inventory.storeItem splits
nonstackables and permits several items at one ground location.

LOCAL backend policies (not verified original Classic behavior):
* Use only adjacent cells for which the supplied terrain callback returns True,
  in heading order, distributing rows round-robin. Occupancy does not block
  items. Keep separate entities, including equal stackable templates, so owner
  and grade are never accidentally merged. No usable cell raises an error;
  the caller retains the uncommitted reward and must not roll it again.
* Give the supplied killer UID exclusive pickup for 10 seconds. L1J's
  L1ItemInstance.startItemOwnerTimer (:1129-1133) and L1ItemOwnerTimer clear an
  owner after 10000ms, but its sole call site is C_FishClick.java:114, NOT mob
  DropTable. Applying it to monster loot is our explicit local extension.
* Fixed 600-second per-entity expiry adopts L1GroundInventory.setTimer's `std`
  duration. config/altsettings.properties:54,57 actually defaults to `auto`
  and ItemDeletionTime=10 minutes; we do NOT implement that auto/range policy.
  Partial pickup keeps both original deadlines; final pickup cancels expiry.
* Missing rolled_rows means normal grade=1, an explicit fallback for tuple-only
  callers. Pass KillReward.rolled_rows to preserve actual rolled grades.
* data.items is the primary stackability source. Nine currently resolved M1
  drops have no ItemDef yet: the bounded fallback below fills only that field
  from L1J. It does not fabricate an inventory ItemDef or claim that the later
  inventory owner can already insert/display those templates.

Caller contract: run on one serialized world loop. After EntityRegistry.kill,
pass the CURRENT dead NPC ref (the old live generation is stale), before its
corpse is removed. Successful placement is once per corpse ref; this is not
authority to kill, roll rewards, award EXP or persist loot. A failed placement
does not consume that ref. UID allocations on an exceptional failed creation
remain burned by EntityRegistry; the reward itself remains the caller's input.

pickup returns exactly (item_id, count) AFTER consuming in-memory ground state.
Read get(item_ref) first, in the same synchronous world section, to carry grade
to the existing inventory owner. Do not consume, then try a fallible durable
insert: capacity/grade mapping and an atomic inventory/ground save transaction
must be supplied by the later integration. This API has no inventory insertion,
rollback, persistence, restart restoration, packet decoder or broker binding.
expiry/removal here is only in-memory lifetime. close() releases owned items.

Packet integration references only: item_ground_wire builds 4E96 appearance,
item_ground GET uses 4E40 retirement, item_transfer_protocol parses 4E3E pickup.
The older whole-B GroundRegistry has a different custody contract; not reused.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
import math
from typing import TYPE_CHECKING

from tools.local_original_session.game_data import DropDef, M1Data
from tools.local_original_session.world_entities import EntityRef, EntityRegistry, Kind
from tools.local_original_session.world_scheduler import Handle, Scheduler
from tools.local_original_session.world_terrain import DELTAS

if TYPE_CHECKING:
    from tools.local_original_session.world_reward import KillReward

OWNER_PRIORITY_S = 10.0
ITEM_LIFETIME_S = 600.0
PICKUP_DISTANCE = 3
MAX_COUNT = 2_000_000_000

# Classic IDs mapped by data/m1/drops.json sources['roll']: weapon 171/23/21,
# armor 220125/20136/20135, etcitem 40171/40173/40405 respectively.
# L1J L1Inventory.storeItem uses isStackable, weapons/armor are nonstackable;
# db/l1jdb_m10.sql etcitem stackable column :727 and rows :16625/:16627/:16859
# give 0/0/1. This is a temporary L1J-derived LOCAL metadata adapter.
_STACKABLE_FALLBACK = {
    34: False, 35: False, 74: False, 96: False, 97: False, 101: False,
    195: False, 197: False, 332: True,
}


@dataclass(frozen=True, slots=True)
class GroundItem:
    ref: EntityRef
    source_ref: EntityRef
    item_id: int
    count: int
    grade: int
    stackable: bool
    map_id: int
    x: int
    y: int
    owner_uid: int
    owner_until: float
    expires_at: float


def _positive_int(value, error: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(error)
    return value


class GroundItems:
    """Own Kind.ITEM entities and frozen metadata; use the existing Scheduler."""

    def __init__(self, entities: EntityRegistry, scheduler: Scheduler, data: M1Data,
                 *, passable: Callable[[int, int, int], bool | None]):
        self.entities, self.scheduler, self.data = entities, scheduler, data
        self.passable = passable
        self._items: dict[int, GroundItem] = {}
        self._expiry: dict[int, Handle] = {}
        self._spawned: set[EntityRef] = set()
        # Optional callable(GroundItem) after an item leaves the ground (final
        # pickup, expiry or close); the world view uses it to send 4E40.
        self.on_remove: Callable[[GroundItem], None] | None = None

    def __len__(self) -> int:
        return len(self._items)

    def _now(self, now: float | None) -> float:
        value = self.scheduler.clock() if now is None else now
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('GROUND_TIME_INVALID')
        return value

    def get(self, ref: EntityRef) -> GroundItem | None:
        """Snapshot, including grade. Expired items may await the next world tick."""
        if not isinstance(ref, EntityRef):
            return None
        item = self._items.get(ref.uid)
        entity = self.entities.resolve(ref)
        if (item is None or item.ref != ref or entity is None
                or entity.kind is not Kind.ITEM or not entity.alive):
            return None
        return item

    def spawn_reward(self, npc_ref: EntityRef, reward: KillReward, *, owner_uid: int,
                     now: float | None = None) -> tuple[GroundItem, ...]:
        return self.spawn_drops(npc_ref, reward.drops, owner_uid=owner_uid,
                                rolled_rows=reward.rolled_rows, now=now)

    def spawn_drops(self, npc_ref: EntityRef, drops: Sequence[tuple[int, int]], *,
                    owner_uid: int, rolled_rows: Sequence[DropDef] | None = None,
                    now: float | None = None) -> tuple[GroundItem, ...]:
        """Place all rows or raise, with no partial reward consumption.

        Rejected arguments/terrain do not change items, timers or entities.
        Duplicate successful placement for this corpse ref raises as well.
        Nonstackable quantity N becomes N independent count-one entities.
        """
        now = self._now(now)
        if not isinstance(npc_ref, EntityRef):
            raise ValueError('GROUND_SOURCE_INVALID')
        npc = self.entities.resolve(npc_ref)
        if npc is None or npc.kind is not Kind.NPC or npc.alive:
            raise ValueError('GROUND_CURRENT_DEAD_NPC_REQUIRED')
        # A removed corpse cannot be submitted again: retain once markers only
        # while their exact corpse generation still exists, independent of loot.
        self._spawned = {ref for ref in self._spawned if self.entities.is_current(ref)}
        if npc_ref in self._spawned:
            raise ValueError('GROUND_CORPSE_ALREADY_DROPPED')
        _positive_int(owner_uid, 'GROUND_OWNER_INVALID')
        owner = self.entities.get(owner_uid)
        if owner is None or owner.kind is not Kind.PC:
            raise ValueError('GROUND_PC_OWNER_REQUIRED')
        rows = tuple(drops)
        definitions = None if rolled_rows is None else tuple(rolled_rows)
        if definitions is not None and len(definitions) != len(rows):
            raise ValueError('GROUND_ROLLED_ROWS_MISMATCH')
        planned = []
        for index, row in enumerate(rows):
            if not isinstance(row, (tuple, list)) or len(row) != 2:
                raise ValueError('GROUND_DROP_INVALID')
            item_id, count = row
            _positive_int(item_id, 'GROUND_TEMPLATE_INVALID')
            _positive_int(count, 'GROUND_COUNT_INVALID')
            if count > MAX_COUNT:
                raise ValueError('GROUND_COUNT_INVALID')
            template = self.data.items.get(item_id)
            stackable = (template.stackable if template is not None
                         else _STACKABLE_FALLBACK.get(item_id))
            if stackable is None:
                raise ValueError('GROUND_TEMPLATE_UNKNOWN')
            grade = 1
            if definitions is not None:
                definition = definitions[index]
                if (not isinstance(definition, DropDef) or definition.item_id != item_id
                        or type(definition.grade) is not int or definition.grade not in (0, 1, 2)):
                    raise ValueError('GROUND_ROLLED_ROWS_MISMATCH')
                grade = definition.grade
            planned.append((item_id, count, grade, stackable))
        cells = []
        if planned:
            for dx, dy in DELTAS:
                x, y = npc.x + dx, npc.y + dy
                if self.passable(npc.map_id, x, y) is True:
                    cells.append((x, y))
            if not cells:
                raise ValueError('GROUND_NO_PASSABLE_TILE')
        created = []
        try:
            for index, (item_id, count, grade, stackable) in enumerate(planned):
                x, y = cells[index % len(cells)]
                for _ in range(1 if stackable else count):
                    entity = self.entities.add(Kind.ITEM, npc.map_id, x, y, template_id=item_id)
                    item = GroundItem(entity.ref, npc_ref, item_id, count if stackable else 1,
                                      grade, stackable, npc.map_id, x, y, owner_uid,
                                      now + OWNER_PRIORITY_S, now + ITEM_LIFETIME_S)
                    self._items[entity.uid] = item
                    created.append(item)
                    # Manager-owned callback also clears metadata if a caller
                    # incorrectly removed an entity outside this lifetime owner.
                    self._expiry[entity.uid] = self.scheduler.schedule(
                        item.expires_at, None, 'ground_item_expire',
                        lambda _now, ref=item.ref: self._discard(ref))
        except Exception:
            for item in created:
                self._discard(item.ref)
            raise
        self._spawned.add(npc_ref)
        return tuple(created)

    def pickup(self, pc_ref: EntityRef, item_ref: EntityRef, count: int, *,
               now: float | None = None) -> tuple[int, int]:
        """Validate then consume once; rejected requests preserve all state.

        At owner_until other PCs may pick up. At expires_at nobody may pick up,
        even when the scheduler has not ticked yet. Expiry cleanup is its job.
        A partial pickup leaves this UID, generation and expiry handle intact.
        """
        item = self.check_pickup(pc_ref, item_ref, count, now=now)
        if count == item.count:
            self._discard(item.ref)
        else:
            self._items[item.ref.uid] = replace(item, count=item.count - count)
        return item.item_id, count

    def check_pickup(self, pc_ref: EntityRef, item_ref: EntityRef, count: int, *,
                     now: float | None = None) -> GroundItem:
        """pickup()'s complete validation without consuming; returns the snapshot."""
        now = self._now(now)
        _positive_int(count, 'GROUND_COUNT_INVALID')
        if count > MAX_COUNT:
            raise ValueError('GROUND_COUNT_INVALID')
        pc = self.entities.resolve(pc_ref) if isinstance(pc_ref, EntityRef) else None
        if pc is None or pc.kind is not Kind.PC or not pc.alive:
            raise ValueError('GROUND_CURRENT_ALIVE_PC_REQUIRED')
        item = self.get(item_ref)
        if item is None:
            raise ValueError('GROUND_ITEM_NOT_FOUND')
        if now >= item.expires_at:
            raise ValueError('GROUND_ITEM_EXPIRED')
        if pc.map_id != item.map_id or max(abs(pc.x - item.x), abs(pc.y - item.y)) > PICKUP_DISTANCE:
            raise ValueError('GROUND_PICKUP_TOO_FAR')
        if now < item.owner_until and pc.uid != item.owner_uid:
            raise ValueError('GROUND_OWNER_PRIORITY')
        if count > item.count or (not item.stackable and count != 1):
            raise ValueError('GROUND_COUNT_INVALID')
        return item

    def _discard(self, ref: EntityRef) -> None:
        item = self._items.get(ref.uid)
        if item is None or item.ref != ref:
            return
        handle = self._expiry.pop(ref.uid, None)
        if handle is not None:
            self.scheduler.cancel(handle)
        del self._items[ref.uid]
        if self.entities.is_current(ref):
            self.entities.remove(ref.uid)
        if self.on_remove is not None:
            self.on_remove(item)

    def close(self) -> None:
        """Release owned entities and callbacks; no save/restore is performed."""
        for item in tuple(self._items.values()):
            self._discard(item.ref)
        self._spawned.clear()

