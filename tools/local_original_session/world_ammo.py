"""Pure bow preparation and ammunition cost proposals; no inventory mutations.

Public integration contract::

    prepare_attack(weapon, inventory, *, attacker, target, items)
    in_weapon_range(weapon_range, attacker, target)
    roll_arrow_damage(arrow, rng, *, target_size, hard_skinned=False)

``weapon`` is the caller's currently equipped game_data.ItemDef (or None).
``inventory`` contains AmmoStack(item_uid, template_id, count) snapshots of the
actual owned stacks, in caller-selected order; positions are (map_id, x, y).
Load ``items`` once at startup with game_data.load_items(), then pass that
Mapping on every request. This module performs no file reads.
The first positive supported stack is selected. This ordering is LOCAL policy;
L1PcInventory's remembered/preferred arrow selection is not implemented.

Future caller order: check living target/current ownership, cadence and LOS;
prepare; refuse on allowed=False without inventory, cooldown or damage cost;
recheck/apply the exact returned item_uid's one-unit cost through the inventory
owner as part of committing ONE fired attack; resolve hit/miss and damage.
Every fired bow attack costs one arrow, including a miss. Hit/miss is not an
input to this preparation API. Do not consume again
after hit resolution, reuse a proposal for another shot, or resolve damage if
the inventory owner cannot commit its cost. Preparation itself changes nothing
and reserves nothing. Its allowed=True is only this module's admission, not a
substitute for caller target/life/cadence/LOS checks. Non-bows pass through with
no cost; their reach and combat rules remain the caller's responsibility.

On a landed bow shot, roll_arrow_damage returns ONLY the ammunition die.
L1J ranged attacks omit the melee weapon die and use DEX status damage for
bows. world_combat.try_pc_swing(..., arrow=preparation.arrow) supplies this
separate base-damage path; adding the die to its default melee resolver is
incorrect. Use pc_swing_ready before the inventory owner's cost commit, under
the same world lock. No inventory mutation, persistence, packet or live-client
proof is supplied here. Materials/blessing/undead bonuses and other combat
modifiers also remain outside this module.

Read-only reference root: D:/SingleLineageRef/l1j-en-classic/.
* src/l1j/server/server/model/L1Attack.java:289,343-355: item.range;
  finite range permits tile-line distance <= range+1, -1 uses isInScreen.
  types/Point.java:110-113,137-155 supplies Chebyshev and screen predicates.
* L1Attack.java:297-308,750-806,924-929: arrow acquisition; ranged weapon die
  zero; bow DEX status damage (:324); small/large arrow die (zero becomes one,
  then integer half on hard skin). actionPc :1285-1291 consumes one whether
  _isHit is true or false. L1PcInventory.java:569-617 selects actual stacks;
  L1Inventory.java:261-290 removes count or the exhausted item.
* db/l1jdb_m10.sql:2091-2104,63873: L1J172 Bow/$24 has range=-1.
  etcitem schema :716-731 and rows :17197-17202: Arrow6/5, Silver7/6,
  Golden9/9, Mithril10/9, Black Mithril11/15, Oriharukon12/12.

Classic identity comes from data/m1/items.json and game_data.load_items:
Classic11/$24 -> L1J172 is the existing bow mapping. Classic29/$61 is ammo,
but its weight47 differs from L1J40743 weight30. Using Arrow6/5 for29 is an
explicit LOCAL fallback policy, NOT an established Classic numeric mapping.
Only Classic29 is selectable; the other L1J arrow rows below are reference
damage definitions, not invented mappings to29,30 or other Classic IDs.
ItemDef has no range field and ammo29 has weapon=null, so these two narrow
supplements live here without changing the data. The mapping method follows
work/local_original_session/game-core-prep/MAPPING_SCOPE.md section3.
Existing shared-api/implementation/integration HANDOFF searches supplied no
ammo-cost implementation. run74_item_equipment_client_contract/
weapon_key9_source/findings.md only supplies weapon-slot context, not ammo
consumption. All rules above are attributed L1J backend/local policies, not
verified Classic attack/range/arrow behavior.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import random
from types import MappingProxyType

from tools.local_original_session.game_data import ItemDef

POLICY = 'LOCAL_L1J_BOW_AMMO_PREPARATION'
Position = tuple[int, int, int]  # map_id, x, y


@dataclass(frozen=True, slots=True)
class AmmoStack:
    item_uid: int
    template_id: int
    count: int


@dataclass(frozen=True, slots=True)
class AmmoCost:
    item_uid: int
    template_id: int
    count: int = 1


@dataclass(frozen=True, slots=True)
class ArrowDef:
    l1j_item_id: int
    name: str
    small: int
    large: int


# L1J reference IDs only. These do NOT expand the supported Classic inventory.
L1J_ARROWS: Mapping[int, ArrowDef] = MappingProxyType({
    40743: ArrowDef(40743, 'Arrow', 6, 5),
    40744: ArrowDef(40744, 'Silver Arrow', 7, 6),
    40745: ArrowDef(40745, 'Golden Arrow', 9, 9),
    40746: ArrowDef(40746, 'Mithril Arrow', 10, 9),
    40747: ArrowDef(40747, 'Black Mithril Arrow', 11, 15),
    40748: ArrowDef(40748, 'Oriharukon Arrow', 12, 12),
})
BOW_RANGES: Mapping[int, int] = MappingProxyType({11: -1})
CLASSIC_ARROW_POLICY: Mapping[int, int] = MappingProxyType({29: 40743})


@dataclass(frozen=True, slots=True)
class AttackPreparation:
    allowed: bool
    reason: str | None = None
    cost: AmmoCost | None = None
    arrow: ArrowDef | None = None
    weapon_range: int | None = None


def in_weapon_range(weapon_range: int, attacker: Position, target: Position) -> bool:
    """L1J reach only, with explicit same-map admission; does not check LOS."""
    source_map, source_x, source_y = attacker
    target_map, target_x, target_y = target
    if source_map != target_map:
        return False
    dx, dy = target_x - source_x, target_y - source_y
    if weapon_range != -1:
        if weapon_range < 0:
            raise ValueError('weapon_range must be -1 or nonnegative')
        return max(abs(dx), abs(dy)) <= weapon_range + 1
    distance = abs(dx) + abs(dy)
    if distance > 17:
        return False
    if distance <= 13:
        return True
    return 17 <= abs(dx + 15) + abs(dy + 15) <= 43


def prepare_attack(weapon: ItemDef | None, inventory: Iterable[AmmoStack], *,
                   attacker: Position, target: Position,
                   items: Mapping[int, ItemDef]) -> AttackPreparation:
    """Return one shot proposal; no hit roll, writes, reservation or consumption."""
    if weapon is None or weapon.weapon_type != 'bow':
        return AttackPreparation(True)
    reach = BOW_RANGES.get(weapon.template_id)
    if reach is None:
        return AttackPreparation(False, 'BOW_RANGE_UNSUPPORTED')
    if not in_weapon_range(reach, attacker, target):
        return AttackPreparation(False, 'OUT_OF_RANGE', weapon_range=reach)
    for stack in inventory:
        definition = items.get(stack.template_id)
        arrow_id = CLASSIC_ARROW_POLICY.get(stack.template_id)
        if (stack.count > 0 and definition is not None
                and definition.kind == 'ammo' and arrow_id is not None):
            return AttackPreparation(
                True, cost=AmmoCost(stack.item_uid, stack.template_id),
                arrow=L1J_ARROWS[arrow_id], weapon_range=reach)
    return AttackPreparation(False, 'NO_ARROW', weapon_range=reach)


def roll_arrow_damage(arrow: ArrowDef, rng: random.Random, *, target_size: str,
                      hard_skinned: bool = False) -> int:
    """L1J ammunition die only; call for a landed shot, never for admission."""
    if target_size not in ('small', 'large'):
        raise ValueError('target_size must be small or large')
    maximum = arrow.small if target_size == 'small' else arrow.large
    if maximum == 0:
        maximum = 1
    if hard_skinned:
        maximum //= 2
    # Preserve the reference's invalid zero-sided hard-skin die as ValueError;
    # clamping after the half would invent a different damage rule.
    return rng.randint(1, maximum)
