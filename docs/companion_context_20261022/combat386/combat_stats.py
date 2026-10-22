"""Frozen PvE inputs; LOCAL L1J-EN reference policy, never an NC formula claim.

Reference: l1j-en/classic 103e6f6c9dd83545959d8e87d3f59f8de1f40ef0:
L1Attack.java, L1Character.java, L1PcInstance.java, CalcStat.java and the
four L1*ClassFeature.java files. Independent Python implementation.
"""
from dataclasses import dataclass, fields

REFERENCE_COMMIT = "103e6f6c9dd83545959d8e87d3f59f8de1f40ef0"
POLICY = "LOCAL_L1J_EN_103e6f6"

@dataclass(frozen=True)
class Stats:
    str: int
    dex: int
    con: int
    intel: int
    wis: int
    cha: int

ZERO_STATS = Stats(0, 0, 0, 0, 0, 0)

@dataclass(frozen=True)
class StatModifier:
    """One canonical equipment/skill contribution, excluding weapon fields.

    source_id must identify the actual item/effect instance, across both lists.
    stats are deltas; direct values exclude any derived stat bonus. Effects are
    named semantic rules, not an alternate encoding of these numeric fields.
    """
    source_id: str
    stats: Stats = ZERO_STATS
    melee_hit: int = 0
    ranged_hit: int = 0
    melee_damage: int = 0
    ranged_damage: int = 0
    ac: int = 0
    er: int = 0
    mr: int = 0
    sp: int = 0
    reduction: int = 0

@dataclass(frozen=True)
class PcStats:
    """permanent already includes creation and permanent growth.

    current is an optional assertion, never a second contribution. Equipment
    and canonical skill deltas are applied exactly once. Do not feed a fully
    effective permanent value and then supply its modifiers again.
    """
    creation: Stats
    permanent: Stats
    character_class: str
    level: int
    equipment: tuple[StatModifier, ...] = ()
    skills: tuple[StatModifier, ...] = ()
    current: Stats | None = None

@dataclass(frozen=True)
class DerivedStats:
    character_class: str
    level: int
    creation: Stats
    permanent: Stats
    current: Stats
    ac: int
    er: int
    mr: int
    magic_bonus: int
    magic_level: int
    sp: int
    melee_hit: int
    ranged_hit: int
    melee_damage: int
    ranged_damage: int
    reduction: int
    original_magic_hit: int
    original_magic_damage: int
    original_magic_critical: int
    equipment_melee_damage: int
    equipment_ranged_damage: int

STR_HIT = (-2,-2,-2,-2,-2,-2,-2,-2,-1,-1,0,0,1,1,2,2,3,3,4,4,5,5,5,6,6,6,7,7,7,8,8,8,9,9,9,10,10,10,11,11,11,12,12,12,13,13,13,14,14,14,15,15,15,16,16,16,17,17,17)
DEX_HIT = (-2,-2,-2,-2,-2,-2,-1,-1,0,0,1,1,2,2,3,3,4,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,19,19,20,20,20,21,21,21,22,22,22,23,23,23,24,24,24,25,25,25,26,26,26,27,27,27,28)
MAGIC_BONUS = (-2,-2,-2,-2,-2,-2,-1,-1,-1,0,0,0,1,1,1,2,2,2,3,4,5,6,7,8,9,10,10,10,10,10,10,10,10,10,10,10,11,11,11,11,11,11,11,12,12,12,12,12,12,12,13)

def _damage_tables():
    strength = [0] * 128
    damage = -6
    for value in range(128):
        if (value <= 22 and value % 2 == 1 or
            23 <= value <= 28 and value % 3 == 2 or
            29 <= value <= 32 and value % 2 == 1 or
            33 <= value <= 34 or value >= 35 and (value + 1) % 4 == 0):
            damage += 1
        strength[value] = damage
    dexterity = [0] * 128
    dexterity[15:24] = [1,2,3,4,4,4,5,5,5]
    damage = 5
    for value in range(24, 128):
        if value <= 35 and value % 3 == 0 or value >= 36 and value % 4 == 0:
            damage += 1
        dexterity[value] = damage
    return tuple(strength), tuple(dexterity)
STR_DAMAGE, DEX_DAMAGE = _damage_tables()

def _tier(value, *pairs):
    return next((bonus for minimum, bonus in pairs if value >= minimum), 0)

def _original(c, s):
    """melee hit/damage, ranged hit/damage, AC, ER, MR, magic hit/dmg/crit."""
    if c == "royal":
        return (_tier(s.str,(19,2),(16,1)), _tier(s.str,(18,2),(15,1)), 0,
                _tier(s.dex,(13,1)), _tier(s.dex,(17,3),(15,2),(12,1)),
                3 if s.dex == 18 else _tier(s.dex,(16,2),(14,1)),
                _tier(s.wis,(14,2),(12,1)), _tier(s.intel,(14,2),(12,1)),0,0)
    if c == "knight":
        return (_tier(s.str,(19,4),(16,2)),4 if s.str == 20 else _tier(s.str,(18,2)),0,0,
                _tier(s.dex,(15,3),(13,1)), _tier(s.dex,(16,3),(14,1)),
                _tier(s.wis,(12,2),(10,1)),_tier(s.intel,(12,2),(10,1)),0,0)
    if c == "elf":
        return (_tier(s.str,(15,2),(13,1)),_tier(s.str,(14,2),(13,1)),
                _tier(s.dex,(16,3),(13,2)),_tier(s.dex,(17,3),(14,2)),
                2 if s.dex == 18 else _tier(s.dex,(15,1)),0,
                _tier(s.wis,(16,2),(13,1)),_tier(s.intel,(15,2),(13,1)),0,
                _tier(s.intel,(16,4),(14,2)))
    return (_tier(s.str,(13,2),(11,1)),_tier(s.str,(12,2),(10,1)),0,0,
            _tier(s.dex,(10,2),(8,1)),_tier(s.dex,(11,2),(9,1)),
            _tier(s.wis,(15,1)),_tier(s.intel,(14,1)),_tier(s.intel,(13,1)),
            {15:2,16:4,17:6,18:8}.get(s.intel,0))

def derive_stats(player: PcStats) -> DerivedStats:
    """Build once when the owner's stat/equipment/skill snapshot changes."""
    c, level = player.character_class, player.level
    if c not in ("royal", "knight", "elf", "wizard") or type(level) is not int or level < 1:
        raise ValueError("unsupported class or invalid level")
    if not isinstance(player.equipment, tuple) or not isinstance(player.skills, tuple):
        raise ValueError("modifier inputs must be immutable tuples")
    for stats in (player.creation, player.permanent):
        if any(type(getattr(stats, f.name)) is not int or not 1 <= getattr(stats, f.name) <= 127 for f in fields(Stats)):
            raise ValueError("stat outside supported 1..127 reference table")
    modifiers = player.equipment + player.skills
    ids = [m.source_id for m in modifiers]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("duplicate/empty modifier source: double representation")
    for m in modifiers:
        if any(type(getattr(m, f.name)) is not int for f in fields(StatModifier) if f.name not in ("source_id", "stats")) or any(type(getattr(m.stats, f.name)) is not int for f in fields(Stats)):
            raise ValueError("modifier values must be integers")
    current = Stats(*(getattr(player.permanent, f.name) + sum(getattr(m.stats, f.name) for m in modifiers) for f in fields(Stats)))
    if any(not 1 <= getattr(current, f.name) <= 127 for f in fields(Stats)):
        raise ValueError("effective stat outside reference table")
    if player.current is not None and player.current != current:
        raise ValueError("current must equal permanent plus unique modifiers")
    def total(name):
        return sum(getattr(m, name) for m in modifiers)
    mh, md, rh, rd, original_ac, original_er, original_mr, omh, omd, omc = _original(c, player.creation)
    # resetBaseAc uses permanent/base DEX, not buffed current DEX.
    dex = player.permanent.dex
    divisor = 8 if dex <= 9 else 7 if dex <= 12 else 6 if dex <= 15 else 5 if dex <= 17 else 4
    ac = 10 - level // divisor - original_ac + total("ac")
    er = level // {"royal":8,"knight":4,"elf":8,"wizard":10}[c] + int((current.dex - 8) / 2) + original_er + total("er")
    mr_bonus = _tier(current.wis,(24,50),(23,47),(22,37),(21,28),(20,21),(19,15),(18,10),(17,6),(15,3))
    mr = max(0,{"royal":10,"knight":10,"elf":25,"wizard":15}[c] + level // 2 + mr_bonus + original_mr + total("mr"))
    mb = MAGIC_BONUS[current.intel] if current.intel <= 50 else current.intel - 25
    ml = {"royal":min(2,level//10),"knight":level//50,"elf":min(6,level//8),"wizard":min(10,level//4)}[c]
    hit = level + STR_HIT[min(current.str,59)-1] + DEX_HIT[min(current.dex,60)-1]
    class_hit = level // 3 if c == "knight" else level // 5 if c in ("royal","elf") else 0
    # RoyalLevelDamage is explicitly off in this LOCAL policy; knight/elf source defaults.
    return DerivedStats(c,level,player.creation,player.permanent,current,ac,er,mr,mb,ml,mb+ml+total("sp"),
        hit+class_hit+mh+total("melee_hit"),hit+class_hit+rh+total("ranged_hit"),
        STR_DAMAGE[current.str]+md+(level//10 if c=="knight" else 0)+total("melee_damage"),
        DEX_DAMAGE[current.dex]+rd+(level//10 if c=="elf" else 0)+total("ranged_damage"),
        total("reduction"),omh,omd,omc,
        sum(m.melee_damage for m in player.equipment),sum(m.ranged_damage for m in player.equipment))

@dataclass(frozen=True)
class GrowthContext:
    """One real level-up input; never derive historical maxima from current buffs.

    Caps are explicit owner policy/config values. Existing max HP/MP remain the
    resource owner's authority; this pure function returns only new deltas.
    """
    character_class: str
    creation: Stats
    permanent: Stats
    previous_max_hp: int
    previous_max_mp: int
    hp_cap: int
    mp_cap: int

@dataclass(frozen=True)
class GrowthResult:
    hp_delta: int
    mp_delta: int
    policy: str = POLICY

def resolve_level_growth(context: GrowthContext, rng) -> GrowthResult:
    """CalcStat.calcStatHp/Mp + four class creation bonuses, pinned source.

    Preserves source order: cap base growth BEFORE adding original bonus. Thus
    a creation bonus can exceed configured cap; silently recapping would change
    the chosen reference policy. Caller must use only once for a real level-up.
    """
    c,s,b = context.character_class,context.creation,context.permanent
    if c not in ("royal","knight","elf","wizard"):
        raise ValueError("unsupported growth class")
    if min(context.previous_max_hp,context.previous_max_mp,context.hp_cap,context.mp_cap) < 0:
        raise ValueError("negative resource maximum/cap")
    hp_original = {"royal":_tier(s.con,(16,3),(14,2),(12,1)),
                   "knight":_tier(s.con,(17,3),(15,1)),
                   "elf":2 if s.con==18 else _tier(s.con,(13,1)),
                   "wizard":_tier(s.con,(16,2),(14,1))}[c]
    mp_original = {"royal":_tier(s.wis,(16,1)),"knight":0,
                   "elf":_tier(s.wis,(17,2),(14,1)),
                   "wizard":_tier(s.wis,(17,2),(13,1))}[c]
    hp = max(0,b.con-15) + {"royal":11,"knight":17,"elf":10,"wizard":7}[c] + rng.randint(0,1)
    hp = max(0,min(hp,context.hp_cap-context.previous_max_hp)+hp_original)
    wis = b.wis
    if not 1 <= wis <= 127 or not 1 <= b.con <= 127:
        raise ValueError("permanent CON/WIS outside reference range")
    seed_y = 2 if wis < 9 or 9 < wis < 12 else 3 if wis == 9 or 12 <= wis <= 17 else 4 if 18 <= wis <= 23 or wis in (25,26,29,30,33,34) else 5
    seed_z = 0 if wis < 10 else 1 if wis <= 14 else 2 if wis <= 20 else 3 if wis <= 24 else 4 if wis <= 28 else 5 if wis <= 32 else 6
    mp = rng.randint(1,seed_y)+seed_z
    mp = mp*2//3 if c == "knight" else int(mp*1.5) if c == "elf" else mp*2 if c == "wizard" else mp
    mp = max(0,min(mp,context.mp_cap-context.previous_max_mp)+mp_original)
    return GrowthResult(hp,mp)
