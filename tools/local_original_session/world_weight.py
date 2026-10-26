"""Pure L1J-derived weight policy; no broker, save, game or server integration.

Reference root: D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/.
* model/Instance/L1ItemInstance.java:getWeight (:252-257): raw SQL weight is
  divided by 1000 AFTER multiplying one instance's count; nonzero raw has a
  minimum burden of 1. model/L1Inventory.java:getWeight (:66-71) sums instances.
* model/Instance/L1PcInstance.java:getMaxWeight (:1670-1698): current STR/CON,
  armor/doll percentages, original-stat reduction points, Decrease Weight and
  RateWeightLimit. Original-stat points are explicit inputs, NOT inferred from
  current stats or class. config/rates.properties:92 defaults the rate to 1.0.
* model/L1PcInventory.java:calcWeight240 (:70-87), checkAddItem (:107-121):
  Java Math.round (nonnegative half-up), cap 240; forecast adds floor(raw*Q/1000)
  PLUS 1 and refuses gauge >=240. This is not the post-merge inventory weight.
* model/HpRegeneration.java:isOverWeight (:210-218) and regenHp (:149-164),
  model/MpRegeneration.java:isOverWeight (:151-156) and regenMp (:107-122):
  gauge >=120 suppresses the bonus/base and positive equipment contribution.
  It does NOT stop all recovery: the later CON HP / WIS MP contribution remains.
* clientpackets/C_Attack.java:68 and model/skill/L1SkillUse.java:389 refuse
  attacks / NORMAL skill use at gauge >=197 (about 82%, not 100%). No movement
  weight refusal was found in clientpackets/C_MoveChar.java.

The existing warehouse-unit-weight-source-v1/API.md publishes the same stack
formula; loot-current-capacity-v2/API.md publishes the existing capacity/gauge
contract. Their native ownership wrappers are intentionally not reused here.
These are reference-derived LOCAL backend rules, not verified Classic rules.
Integer products/sums use Python precision, not Java signed-int wraparound.

Current data/m1/items.json has no weight cells. load_weight_catalog therefore
reports missing actual template IDs; nothing supplies a guessed/zero default.
Future weight cells must hold RAW weights (1000 raw units per burden unit)
with the same value/source/ref provenance format as the other M1 fields.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from tools.local_original_session.game_data import (
    ItemDef, M1_DATA_DIR, SOURCE_KINDS, Source, load_items,
)

RAW_PER_WEIGHT = 1000
REGEN_GAUGE = 120
ATTACK_GAUGE = 197
CAPACITY_GAUGE = 240


def _integer(value: int, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('WEIGHT_NONNEGATIVE_INTEGER_REQUIRED')
    return value


def _number(value: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('WEIGHT_NONNEGATIVE_FINITE_NUMBER_REQUIRED')
    return float(value)


@dataclass(frozen=True, slots=True)
class ItemWeight:
    item: ItemDef
    raw_weight: int
    source: Source


def weight_catalog(document: Mapping, definitions: Mapping[int, ItemDef]) -> Mapping[int, ItemWeight]:
    """Decode explicit provenance-wrapped RAW weight cells, using existing ItemDefs.

    Missing templates are an error even if the caller's inventory is empty.
    This is table loading only; it authenticates no live inventory or ownership.
    """
    rows = {row['id']['value']: row for row in document['items']}
    missing = sorted(template for template in definitions
                     if template not in rows or 'weight' not in rows[template])
    if missing:
        raise ValueError('ITEM_WEIGHT_MISSING: ' + ','.join(map(str, missing)))
    result = {}
    for template, definition in definitions.items():
        cell = rows[template]['weight']
        raw = _integer(cell['value'])
        if cell['source'] not in SOURCE_KINDS or not isinstance(cell['ref'], str) or not cell['ref']:
            raise ValueError(f'ITEM_WEIGHT_PROVENANCE_REQUIRED: {template}')
        result[template] = ItemWeight(definition, raw,
                                      Source(cell['source'], cell['ref'], cell.get('note', '')))
    return MappingProxyType(result)


def load_weight_catalog(directory: Path | str = M1_DATA_DIR) -> Mapping[int, ItemWeight]:
    """Explicit file-reading boundary; calculations below perform no I/O."""
    directory = Path(directory)
    definitions = load_items(directory)
    document = json.loads((directory / 'items.json').read_text(encoding='utf-8'))
    return weight_catalog(document, definitions)


def stack_weight(raw_weight: int, count: int) -> int:
    """Burden of ONE live item instance, including equipped items; count >=1."""
    raw_weight, count = _integer(raw_weight), _integer(count, 1)
    return 0 if raw_weight == 0 else max(raw_weight * count // RAW_PER_WEIGHT, 1)


class InventoryRow(Protocol):
    raw_fields: tuple


def inventory_weight(rows: Iterable[InventoryRow], catalog: Mapping[int, ItemWeight]) -> int:
    """Sum existing inventory.ItemInfo-shaped rows without mutation or imports.

    ItemInfo stores signed template bits in f2 and uint64 quantity in f4
    (run30_inventory_first_wire/findings.md:41). Each row is a separate stack:
    do not combine equal templates before rounding. Unknown weight is an error.
    The existing inventory owner remains responsible for validating the rows.
    """
    total = 0
    for row in rows:
        fields = dict(row.raw_fields)
        template = fields[2] & 0xffffffff
        if template not in catalog:
            raise ValueError(f'ITEM_WEIGHT_MISSING: {template}')
        total += stack_weight(catalog[template].raw_weight, fields[4])
    return total


def maximum_weight(strength: int, con: int, *, armor_percent: float = 0,
                   doll_percent: float = 0, original_str_points: int = 0,
                   original_con_points: int = 0, decrease_weight: bool = False,
                   rate: float = 1.0) -> float:
    """L1PcInstance.getMaxWeight; original-stat points are explicit caller data.

    No artificial STR/CON clamp or final integer truncation. Effects/class
    features are outside this module; no modifier is inferred from inventory.
    Pass the same rate to weight240, weight_state and can_add_weight as here;
    max_weight=0 alone does not communicate that rate=0 disables weight limits.
    """
    strength, con = _integer(strength, 1), _integer(con, 1)
    armor_percent, doll_percent, rate = map(_number, (armor_percent, doll_percent, rate))
    original = _integer(original_str_points) + _integer(original_con_points)
    if type(decrease_weight) is not bool:
        raise ValueError('WEIGHT_BOOLEAN_EFFECT_REQUIRED')
    base = 150 * math.floor(0.6 * strength + 0.4 * con + 1)
    multiplier = 1 + armor_percent / 100 + doll_percent / 100 + 0.04 * original
    return (base * multiplier + (180 if decrease_weight else 0)) * rate


def weight240(weight: int, max_weight: float, *, rate: float = 1.0) -> int:
    """L1J gauge 0..240, half-up (Python round would incorrectly tie to even).

    Rate 0 disables the gauge. A positive burden over capacity clamps to 240.
    Java's zero/zero -> NaN -> Math.round(NaN)==0 is explicit for empty weight.
    """
    weight, max_weight, rate = _integer(weight), _number(max_weight), _number(rate)
    if rate == 0:
        return 0
    if weight > max_weight:
        return CAPACITY_GAUGE
    if max_weight == 0:
        return 0
    value = (weight * 100 / max_weight) * 240.0 / 100.0
    return math.floor(value + 0.5)


@dataclass(frozen=True, slots=True)
class WeightState:
    gauge: int
    hp_bonus_suppressed: bool
    mp_base_suppressed: bool
    attack_blocked: bool
    normal_skill_blocked: bool
    at_capacity_gauge: bool


def weight_state(weight: int, max_weight: float, *, rate: float = 1.0,
                 exotic_vitalize: bool = False, additional_fire: bool = False,
                 hp_equipped_20049: bool = False) -> WeightState:
    """Only weight effects; no overall action eligibility or all-regen-stop flag.

    Both skill exceptions bypass the HP/MP weight suppression. Equipped 20049
    bypasses only HP suppression. That boolean refers to L1J equipment 20049,
    not an established Classic template-ID mapping. None bypasses
    attack/normal-skill refusal. Use the same rate that produced max_weight.
    """
    gauge = weight240(weight, max_weight, rate=rate)
    over = gauge >= REGEN_GAUGE and not (exotic_vitalize or additional_fire)
    blocked = gauge >= ATTACK_GAUGE
    return WeightState(gauge, over and not hp_equipped_20049, over, blocked,
                       blocked, gauge >= CAPACITY_GAUGE)


def hp_regen_after_weight(bonus: int, equipment: int, con: int, state: WeightState) -> int:
    """HP weight stage plus later CON term; excludes hunger/berserk/location harm.

    Negative equipment contribution persists. CON=10 gives 0; CON<10 gives 1,
    exactly as this reference fork, not max(CON-10, 1).
    """
    con_hp = _integer(con, 1) - 10
    if state.hp_bonus_suppressed:
        bonus, equipment = 0, min(equipment, 0)
    return bonus + equipment + (1 if con_hp < 0 else con_hp)


def mp_regen_after_weight(base: int, equipment: int, wis: int, state: WeightState) -> int:
    """MP weight stage plus later max(WIS-12,12); excludes hunger/final clamp."""
    wis_mp = max(_integer(wis, 1) - 12, 12)
    if state.mp_base_suppressed:
        base, equipment = 0, min(equipment, 0)
    return base + equipment + wis_mp


def can_add_weight(current_weight: int, raw_weight: int, count: int,
                   max_weight: float, *, rate: float = 1.0) -> bool:
    """Only L1PcInventory.checkAddItem's weight test, not admission authority.

    Size/count/ownership checks and atomic insertion remain with their owners.
    +1 applies even to raw zero; do not substitute stack_weight or a merged
    post-add weight. Thus the forecast can refuse slightly below 100%.
    """
    current_weight = _integer(current_weight)
    raw_weight, count = _integer(raw_weight), _integer(count, 1)
    forecast = current_weight + raw_weight * count // RAW_PER_WEIGHT + 1
    return weight240(forecast, max_weight, rate=rate) < CAPACITY_GAUGE
