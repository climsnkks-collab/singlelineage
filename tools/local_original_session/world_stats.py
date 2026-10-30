"""Pure, reference-derived LOCAL character calculations; no live integration.

Public connection API (all calculations are side-effect free)::

    base = CharacterStats(level, character_class, Attributes(strength, dexterity,
                           con, wis, charisma, intelligence))
    worn = (EquippedItem(item_def, enchant=0, modifiers=StatModifiers()), ...)
    result = calculate_stats(base, worn, buffs=(StatModifiers(...), ...),
                             original=StatModifiers(),
                             weight=WeightOptions(), regen=RegenOptions())
    fields = self_info_fields(existing_full_4e38_fields, result)

``worn`` contains only actually equipped ItemDefs, not the whole bag. The caller
owns selection, slots, provenance, enchant persistence, buff expiry and locks.
``buffs`` are already selected active numeric effects, not skill IDs or BuffDef
speed multipliers. ``original`` is the caller's known starting-stat bonuses;
it is never inferred from current attributes. Recalculate from BASE attributes
after equip/unequip, enchant, buff apply/expiry or level change. Do not feed a
previous result back as the base or bonuses will be applied twice.

Sources under D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/:
* utils/CalcStat.java:41-94: base AC and WIS MR. Instance/L1PcInstance.java:
  2505-2550 uses BASE DEX for AC, effective WIS for MR, level/class hit/damage.
  model/classes/L1*ClassFeature.java:getBaseMR supplies class MR (0..6 L1J IDs).
* model/L1Attack.java:172-249,378-395,792-795: stat hit/damage, weapon enchant
  hit truncated toward zero /2, class/original bonuses. The arithmetic tables
  already present in world_combat.py are reproduced here because importing
  that module imports attack/hp_status/native infrastructure. These values are
  ADDITIVE BONUSES, not final hit probabilities or damage: dice, target, weight
  hit penalties, procs and damage multipliers remain the combat owner's work.
* model/L1EquipmentSlot.java:87-96: armor AC = ac-enchant-acByMagic, except
  L1J accessory types8..12 ignore enchant. Mapped amulet/ring/belt/earring slots
  therefore ignore armor enchant AC under this explicit backend policy. ItemDef
  modifiers contribute only supported official numeric effects; unknown effects
  stay in the catalog. ItemDef hit/dmg_bonus remain weapon values.
* model/HpRegeneration.java:98-164; model/MpRegeneration.java:52-125: HP random
  bonus bounds, MP base, original/equipment/skill adds, hunger/berserk/weight.
  Regen output is per recovery event, not per world tick. Scheduling, HP/MP
  caps, underwater/location damage, dead-state admission remain with owners.
  Existing town.json M1 regen is simplified (MP1/2/3 without the later WIS
  term); this module neither replaces nor connects that world_combat policy.
* model/L1Character.java:658-661,674-709,944-960: effective AC clamps to
  -128..127, effective stats to1..127 and MR to >=0. ERASE_MAGIC's later MR
  division is outside numeric-add effects; no such skill is inferred here.
* world_weight.maximum_weight/weight_state and regen helpers reuse the
  reference's capacity, weight suppression and later CON/WIS terms (including
  this fork's unusual max(WIS-12,12)). No weight catalog or I/O is invoked.

Classic formulas remain UNVERIFIED; these are explicit L1J backend policies,
following game-core-prep/MAPPING_SCOPE.md section3. Generic modifiers do not
invent a Classic item/skill mapping. ItemDef native name-token mapping remains
with game_data. RoyalLevelDamage defaults false (Config.java:952-953).
Known source-backed 4E38 fields come from local_self_info_profile/model.py:
73-84 via spawn_hook.profiles, hp_status and player_life_codec: f2 level,
f4 STR,f5 DEX,f6 INT,f7 WIS,f8 CON,f9 CHA,f14 NEGATED AC. self_info_fields
copies the FULL seed, preserving HP/MP, EXP f26, unknown fields and identity.
f17 is integer weight PERCENT: restored CONTROL 5D760 reads info+C0 without
scaling; 9A93BD..9A948D formats '{}%' and clamps its gauge to0..100. The
burden/capacity formula and floor rounding below remain LOCAL server policy.
MR/hit/damage/capacity/regen have no inferred SelfInfo field numbers. No frame
codec, save, RNG, broker, socket, timer, game, or capstone import occurs here.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields

from tools.local_original_session.game_data import ItemDef
from tools.local_original_session.world_weight import (
    WeightState, hp_regen_after_weight, maximum_weight, mp_regen_after_weight,
    weight_state,
)

POLICY = 'LOCAL_L1J_CHARACTER_STATS'
CLASS_BASE_MR = (10, 10, 25, 15, 10, 18, 20)
STR_HIT = (-2, -2, -2, -2, -2, -2, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2,
           3, 3, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9,
           10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14,
           15, 15, 15, 16, 16, 16, 17, 17, 17)
DEX_HIT = (-2, -2, -2, -2, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 3, 3,
           4, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
           19, 19, 20, 20, 20, 21, 21, 21, 22, 22, 22, 23, 23, 23, 24,
           24, 24, 25, 25, 25, 26, 26, 26, 27, 27, 27, 28)


def _int(value: int, minimum: int | None = None, maximum: int | None = None) -> int:
    if (type(value) is not int or minimum is not None and value < minimum
            or maximum is not None and value > maximum):
        raise ValueError('STATS_INTEGER_OUT_OF_RANGE')
    return value


@dataclass(frozen=True, slots=True)
class Attributes:
    """Saved INFO order: STR, DEX, CON, WIS, CHA, INT (not SelfInfo order)."""
    strength: int
    dexterity: int
    con: int
    wis: int
    charisma: int
    intelligence: int

    def __post_init__(self):
        for member in fields(self):
            _int(getattr(self, member.name), 1, 127)


@dataclass(frozen=True, slots=True)
class StatModifiers:
    strength: int = 0
    dexterity: int = 0
    con: int = 0
    wis: int = 0
    charisma: int = 0
    intelligence: int = 0
    ac: int = 0  # negative improves AC; includes any explicit magic-AC add
    mr: int = 0
    melee_hit: int = 0
    ranged_hit: int = 0
    melee_damage: int = 0
    ranged_damage: int = 0
    hpr: int = 0  # worn equipment/passive contribution, suppressed if positive
    mpr: int = 0
    hp_bonus: int = 0  # skill/location/original bonus; wholly suppressed
    mp_bonus: int = 0
    weight_bonus: int = 0  # official fixed capacity addition, not armor percent
    resist_earth: int = 0
    resist_fire: int = 0
    resist_water: int = 0
    resist_wind: int = 0
    max_hp: int = 0
    max_mp: int = 0

    def __post_init__(self):
        for member in fields(self):
            _int(getattr(self, member.name))


@dataclass(frozen=True, slots=True)
class CharacterStats:
    level: int
    character_class: int
    attributes: Attributes
    royal_level_damage: bool = False

    def __post_init__(self):
        _int(self.level, 1)
        _int(self.character_class, 0, 6)
        if not isinstance(self.attributes, Attributes) or type(self.royal_level_damage) is not bool:
            raise ValueError('STATS_BASE_ATTRIBUTES_REQUIRED')


@dataclass(frozen=True, slots=True)
class EquippedItem:
    item: ItemDef
    enchant: int = 0
    modifiers: StatModifiers = StatModifiers()
    armor_enchant_ac: bool = True

    def __post_init__(self):
        if not isinstance(self.item, ItemDef) or self.item.kind not in ('weapon', 'armor'):
            raise ValueError('STATS_EQUIPPABLE_ITEM_REQUIRED')
        _int(self.enchant)
        if type(self.armor_enchant_ac) is not bool or not isinstance(self.modifiers, StatModifiers):
            raise ValueError('STATS_EQUIPMENT_MODIFIERS_REQUIRED')


@dataclass(frozen=True, slots=True)
class WeightOptions:
    """Explicit L1J modifiers; no starting-stat/class bonus is guessed."""
    armor_percent: float = 0
    doll_percent: float = 0
    original_str_points: int = 0
    original_con_points: int = 0
    decrease_weight: bool = False
    rate: float = 1.0
    carried_weight: int = 0
    exotic_vitalize: bool = False
    additional_fire: bool = False
    hp_equipped_20049: bool = False


@dataclass(frozen=True, slots=True)
class RegenOptions:
    food: int = 3  # only <3 matters in the reference regen path
    berserk: bool = False
    blue_potion: bool = False
    meditation: bool = False
    concentration: bool = False
    natures_touch: bool = False

    def __post_init__(self):
        _int(self.food, 0)
        if any(type(getattr(self, f.name)) is not bool for f in fields(self) if f.name != 'food'):
            raise ValueError('STATS_REGEN_BOOLEAN_REQUIRED')


@dataclass(frozen=True, slots=True)
class CalculatedStats:
    level: int
    attributes: Attributes
    ac: int
    mr: int
    melee_hit_bonus: int  # excludes the common level term
    ranged_hit_bonus: int
    melee_damage_bonus: int  # excludes weapon/arrow dice
    ranged_damage_bonus: int
    max_weight: float
    weight: WeightState
    hp_regen_min: int
    hp_regen_max: int
    mp_regen: int
    weight_bonus: int = 0
    resist_earth: int = 0
    resist_fire: int = 0
    resist_water: int = 0
    resist_wind: int = 0
    max_hp_bonus: int = 0
    max_mp_bonus: int = 0
    equipment_melee_hit: int = 0
    equipment_ranged_hit: int = 0
    equipment_melee_damage: int = 0
    equipment_ranged_damage: int = 0
    hp_regen_bonus: int = 0
    mp_regen_bonus: int = 0
    carried_weight: int = 0  # authoritative burden; distinct from weight.gauge240

    @property
    def melee_hit(self) -> int:
        return self.level + self.melee_hit_bonus

    @property
    def ranged_hit(self) -> int:
        return self.level + self.ranged_hit_bonus


def base_ac(level: int, base_dex: int) -> int:
    """CalcStat.calcAc; equipment/buff DEX must NOT be supplied here."""
    _int(level, 1)
    _int(base_dex, 1, 127)
    divisor = 8 if base_dex <= 9 else 7 if base_dex <= 12 else 6 if base_dex <= 15 else 5 if base_dex <= 17 else 4
    return 10 - level // divisor


def wisdom_mr(wis: int) -> int:
    _int(wis, 1, 127)
    return 0 if wis <= 14 else (3, 3, 6, 10, 15, 21, 28, 37, 47, 50)[min(wis, 24) - 15]


def strength_damage(strength: int) -> int:
    """L1Attack.strDmg without importing the native-dependent combat module."""
    _int(strength, 1, 127)
    damage = -6
    for value in range(1, strength + 1):
        damage += (value % 2 == 1 if value <= 22 else value % 3 == 2 if value <= 28
                   else value % 2 == 1 if value <= 32 else True if value <= 34
                   else (value + 1) % 4 == 0)
    return damage


def dexterity_damage(dexterity: int) -> int:
    _int(dexterity, 1, 127)
    if dexterity <= 14:
        return 0
    if dexterity <= 23:
        return (1, 2, 3, 4, 4, 4, 5, 5, 5)[dexterity - 15]
    return 5 + sum(v % (3 if v <= 35 else 4) == 0 for v in range(24, dexterity + 1))


def catalog_modifiers(values: Mapping[str, int]) -> StatModifiers:
    """Translate explicit catalog numeric keys; maxima are never HPR/MPR."""
    names = {'str': 'strength', 'dex': 'dexterity', 'con': 'con', 'wis': 'wis',
             'cha': 'charisma', 'int': 'intelligence', 'mr': 'mr', 'ac': 'ac',
             'hp_regen': 'hpr', 'mp_regen': 'mpr', 'weight_bonus': 'weight_bonus',
             'max_hp': 'max_hp', 'max_mp': 'max_mp',
             'resist_earth': 'resist_earth', 'resist_fire': 'resist_fire',
             'resist_water': 'resist_water', 'resist_wind': 'resist_wind',
             'melee_hit': 'melee_hit', 'ranged_hit': 'ranged_hit',
             'melee_damage': 'melee_damage', 'ranged_damage': 'ranged_damage'}
    result = {names[key]: value for key, value in values.items() if key in names}
    for key in ('melee_hit', 'ranged_hit'):
        result[key] = result.get(key, 0) + values.get('hit_bonus', 0)
    for key in ('melee_damage', 'ranged_damage'):
        result[key] = result.get(key, 0) + values.get('damage_bonus', 0)
    return StatModifiers(**result)


def equipment_modifiers(item: ItemDef, character_class: int | None = None) -> StatModifiers:
    """Supported catalog options, added once whenever BASE stats are rebuilt.

    Official accessories options (work/official_data/raw/item/565.json,
    "무게추가" +500)
    supply a fixed capacity addition in burden units, not native raw item weight
    or L1J armor percent. Elemental resistance uses the explicit catalog keys;
    L1Character.addEarth/Fire/Water/Wind clamps the final sum to -128..127.
    Class-conditioned options are selected from the same saved class.
    """
    values = dict(getattr(item, 'modifiers', {}))
    for key, value in getattr(item, 'class_modifiers', {}).get(character_class, {}).items():
        values[key] = values.get(key, 0) + value
    return catalog_modifiers(values)


def equipment_set_modifiers(equipped: Iterable[EquippedItem]) -> tuple[StatModifiers, ...]:
    """One bonus per completed catalog set; duplicate instances add no pieces."""
    equipped = tuple(equipped)
    selected = {entry.item.template_id for entry in equipped}
    sets = {bonus.set_id: bonus for entry in equipped
            for bonus in getattr(entry.item, 'set_bonuses', ())}
    return tuple(catalog_modifiers(bonus.modifiers) for bonus in sets.values()
                 if len(selected.intersection(bonus.members)) >= bonus.degree)


def calculate_stats(base: CharacterStats, equipped: Iterable[EquippedItem] = (), *,
                    buffs: Iterable[StatModifiers] = (), original: StatModifiers = StatModifiers(),
                    weight: WeightOptions = WeightOptions(), regen: RegenOptions = RegenOptions()) -> CalculatedStats:
    """Recompute current numeric state; never reads definitions or live state.

    Hit/damage pairs are the two attack-mode views of the SAME selected weapon.
    The combat consumer chooses its actual mode; this does not equip two weapons.
    Use original.hp_bonus/mp_bonus for original HPR/MPR (not hpr/mpr), because
    the reference suppresses the original contribution along with random/base.
    """
    if not isinstance(base, CharacterStats):
        raise ValueError('STATS_BASE_REQUIRED')
    equipped, buffs = tuple(equipped), tuple(buffs)
    if (not all(isinstance(e, EquippedItem) for e in equipped)
            or not all(isinstance(b, StatModifiers) for b in buffs)
            or not isinstance(original, StatModifiers)):
        raise ValueError('STATS_TYPED_EFFECTS_REQUIRED')
    weapons = [e for e in equipped if e.item.kind == 'weapon']
    if len(weapons) > 1:
        raise ValueError('STATS_ONE_SELECTED_WEAPON_REQUIRED')
    equipment_effects = (tuple(e.modifiers for e in equipped)
                         + tuple(equipment_modifiers(e.item, base.character_class) for e in equipped)
                         + equipment_set_modifiers(equipped))
    modifiers = (original,) + equipment_effects + buffs
    equipment_adds = {f.name: sum(getattr(m, f.name) for m in equipment_effects)
                      for f in fields(StatModifiers)}
    adds = {f.name: sum(getattr(m, f.name) for m in modifiers) for f in fields(StatModifiers)}
    attrs = Attributes(**{f.name: min(127, max(1, getattr(base.attributes, f.name) + adds[f.name]))
                          for f in fields(Attributes)})
    ac = base_ac(base.level, base.attributes.dexterity) + adds['ac']
    ac += sum(e.item.ac - (e.enchant if e.armor_enchant_ac and
              e.item.slot not in ('amulet', 'ring', 'belt', 'earring') else 0)
              for e in equipped if e.item.kind == 'armor')
    cls = base.character_class
    class_hit = base.level // (5 if cls in (0, 2, 6) else 3) if cls != 3 else 0
    melee_level_damage = base.level // 10 if cls in (1, 4, 5) or cls == 0 and base.royal_level_damage else 0
    ranged_level_damage = base.level // 10 if cls == 2 else 0
    weapon_hit = weapon_damage = 0
    if weapons:
        selected = weapons[0]
        half_enchant = (abs(selected.enchant) // 2) * (-1 if selected.enchant < 0 else 1)
        weapon_hit = selected.item.hit + half_enchant
        weapon_damage = selected.item.dmg_bonus + selected.enchant
    common_hit = STR_HIT[min(attrs.strength, 59) - 1] + DEX_HIT[min(attrs.dexterity, 60) - 1] + weapon_hit + class_hit
    capacity = maximum_weight(attrs.strength, attrs.con, armor_percent=weight.armor_percent,
                              doll_percent=weight.doll_percent, original_str_points=weight.original_str_points,
                              original_con_points=weight.original_con_points,
                              decrease_weight=weight.decrease_weight, rate=weight.rate)
    capacity += adds['weight_bonus'] * weight.rate
    burden = weight_state(weight.carried_weight, capacity, rate=weight.rate,
                          exotic_vitalize=weight.exotic_vitalize, additional_fire=weight.additional_fire,
                          hp_equipped_20049=weight.hp_equipped_20049)
    hp_max = min(attrs.con - 12, 14) if base.level > 11 and attrs.con >= 14 else 1
    hp_bonus = adds['hp_bonus'] + (15 if regen.natures_touch else 0)
    mp_base = 1 if attrs.wis < 15 else 2 if attrs.wis <= 16 else 3
    mp_base += adds['mp_bonus'] + (max(attrs.wis, 11) - 5 if regen.blue_potion else 0)
    mp_base += (5 if regen.meditation else 0) + (2 if regen.concentration else 0)
    hpr, mpr = adds['hpr'], adds['mpr']
    hp_min = 1 + hp_bonus
    hp_max += hp_bonus
    if regen.food < 3 or regen.berserk:
        hp_min = hp_max = 0
        hpr = min(hpr, 0)
    if regen.food < 3:
        mp_base, mpr = 0, min(mpr, 0)
    return CalculatedStats(base.level, attrs, min(127, max(-128, ac)),
                           max(0, CLASS_BASE_MR[cls] + wisdom_mr(attrs.wis) + base.level // 2 + adds['mr']),
                           common_hit + adds['melee_hit'], common_hit + adds['ranged_hit'],
                           strength_damage(attrs.strength) + weapon_damage + melee_level_damage + adds['melee_damage'],
                           dexterity_damage(attrs.dexterity) + weapon_damage + ranged_level_damage + adds['ranged_damage'],
                           capacity, burden,
                           hp_regen_after_weight(hp_min, hpr, attrs.con, burden),
                           hp_regen_after_weight(hp_max, hpr, attrs.con, burden),
                           mp_regen_after_weight(mp_base, mpr, attrs.wis, burden),
                           adds['weight_bonus'],
                           *(min(127, max(-128, adds['resist_' + element]))
                             for element in ('earth', 'fire', 'water', 'wind')),
                           adds['max_hp'], adds['max_mp'],
                           *(equipment_adds[name] for name in
                             ('melee_hit', 'ranged_hit', 'melee_damage', 'ranged_damage', 'hpr', 'mpr')),
                           weight.carried_weight)


def companion_stats(record, attributes, frame, equipment, definitions, weights):
    """Same saved PC bag/eight slots/enchant/base calculations for a mage."""
    from tools.local_original_session import inventory, world_enchant_inventory, world_weight
    rows = inventory.validate_kit_frame(frame)
    selected = {equipment.weapon_uid, *(uid for _, uid in equipment.slots)} - {0}
    worn = tuple(EquippedItem(definitions[row.template_bits],
        enchant=world_enchant_inventory.enchant_level(row, definitions[row.template_bits]))
        for row in rows if row.identifier in selected and dict(row.raw_fields)[4] > 0)
    carried = world_weight.inventory_weight(
        (row for row in rows if dict(row.raw_fields)[4] > 0), weights)
    base = CharacterStats(record.level, 3, Attributes(*attributes))
    return calculate_stats(base, worn, weight=WeightOptions(carried_weight=carried)), worn


def self_info_fields(existing: Mapping[int, object], calculated: CalculatedStats) -> dict[int, object]:
    """Full copied SC4E38 fields; preserve vitals, EXP, identity, unknowns exactly.

    This is a data adapter, not a full-packet validator. Caller must provide the
    existing full authoritative field dict and use the existing schema encoder.
    f17 is percent, not L1J gauge240. LOCAL policy floors burden*100/capacity,
    then clamps to0..100. Zero capacity (disabled limits) projects0. The fixed
    Classic client reads f17 directly: 5D760/91CD38/9A93BD; '{}'+'%' literal
    RVA1213B38, gauge bound100 at126ED50. Native33/50/67/83/100 weight stages
    (111E40) and50/83 HUD colors (91E2F0) remain client-owned. This establishes
    the client unit, not the original server's capacity/rounding policy.
    """
    result = dict(existing)
    stats = calculated.attributes
    weight_percent = (0 if calculated.max_weight <= 0 else
                      min(100, max(0, int(calculated.carried_weight * 100 / calculated.max_weight))))
    result.update({2: calculated.level, 4: stats.strength, 5: stats.dexterity,
                   6: stats.intelligence, 7: stats.wis, 8: stats.con,
                   9: stats.charisma, 14: -calculated.ac, 17: weight_percent})
    return result
