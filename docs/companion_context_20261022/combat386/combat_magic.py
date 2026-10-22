"""Pure PvE LOCAL_REFERENCE_L1J magic adjudication, not NC Classic formulas.

Policy: l1j-en/classic 103e6f6c9dd83545959d8e87d3f59f8de1f40ef0,
L1Magic.java. No spell table is inferred from client spell.bin. Callers supply
the actual selected spell's dice/parameters and canonical active effects once.
An accepted skill operation owns its input and this single result; HP/MP,
status application, costs, expiry, reflection and effect consumption remain
with existing owners. No file reads, mutable actor state or global RNG cache.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class RandomSource(Protocol):
    def randint(self, low: int, high: int) -> int: ...


class Direction(str, Enum):
    PC_NPC = "PC_NPC"
    NPC_PC = "NPC_PC"


class Element(str, Enum):
    NONE = "none"
    EARTH = "earth"
    FIRE = "fire"
    WATER = "water"
    WIND = "wind"


def _div(value: int, divisor: int) -> int:
    """Java integer division, including negative original-hit/MR differences."""
    return (abs(value) // divisor) * (-1 if value < 0 else 1)


@dataclass(frozen=True)
class MagicActor:
    level: int
    intelligence: int
    sp: int
    true_sp: int
    magic_bonus: int
    magic_level: int
    is_wizard: bool = False
    original_magic_hit: int = 0
    original_magic_damage: int = 0
    original_magic_critical: int = 0
    weapon_magic_damage: int = 0
    lawful: int = 0
    current_mp: int = 0
    current_hp: int = 0
    max_hp: int = 0
    illusion_avatar: bool = False
    # Exact NPC template predicate for Counter Mirror, selected by NPC owner.
    npc_id: int = 0
    npc_is_erase: bool = False

    @classmethod
    def from_derived(cls, stats, **explicit) -> MagicActor:
        """Bridge to combat_stats.DerivedStats without adding equipment twice."""
        values = dict(level=stats.level, intelligence=stats.current.intel,
                      sp=stats.sp, true_sp=stats.magic_bonus + stats.magic_level,
                      magic_bonus=stats.magic_bonus, magic_level=stats.magic_level,
                      is_wizard=stats.character_class == "wizard",
                      original_magic_hit=stats.original_magic_hit,
                      original_magic_damage=stats.original_magic_damage,
                      original_magic_critical=stats.original_magic_critical)
        values.update(explicit)
        return cls(**values)


@dataclass(frozen=True)
class Resists:
    earth: int = 0
    fire: int = 0
    water: int = 0
    wind: int = 0
    sustain: int = 0
    stun: int = 0
    stone: int = 0
    sleep: int = 0
    freeze: int = 0
    blind: int = 0


@dataclass(frozen=True)
class MagicTarget:
    level: int
    mr: int
    resists: Resists = field(default_factory=Resists)
    weak_element: Element = Element.NONE
    # Armor+doll+canonical cooking/skill reductions selected once by owner.
    reduction: int = 0
    immune_to_harm: bool = False
    immune: bool = False
    missing_required_effect: bool = False
    earth_bound: bool = False
    counter_mirror: bool = False
    frozen: bool = False
    counter_magic: bool = False
    wisdom: int = 0
    current_hp: int = 0
    max_hp: int = 0
    # RETURN_TO_NATURE uses the summon's master level, not summon level.
    master_level: int | None = None

    @classmethod
    def from_derived(cls, stats, **explicit) -> MagicTarget:
        values = dict(level=stats.level, mr=stats.mr, reduction=stats.reduction)
        values.update(explicit)
        return cls(**values)


@dataclass(frozen=True)
class DamageSpell:
    name: str
    damage_dice: int
    dice_count: int
    damage_value: int
    skill_level: int
    element: Element = Element.NONE
    leverage: int = 10

    def __post_init__(self):
        if not self.name or self.dice_count < 0 or self.leverage < 0:
            raise ValueError("explicit spell name, nonnegative count/leverage required")
        if self.dice_count and self.damage_dice < 1:
            raise ValueError("damage dice must be positive when dice are rolled")


@dataclass(frozen=True)
class DamageResult:
    damage: int
    critical: bool = False
    mr_halved: bool = False
    reflected_damage: int = 0
    consume_effects: tuple[str, ...] = ()
    policy: str = "LOCAL_REFERENCE_L1J"


def _attribute(target: MagicTarget, element: Element, direction: Direction) -> float:
    # L1Magic.calcAttrResistance only consults PC elemental resistance.
    resist = getattr(target.resists, element.value) if direction == Direction.NPC_PC and element != Element.NONE else 0
    return (int(0.32 * abs(resist)) * (-1 if resist < 0 else 1)) / 32.0


def _mr(damage: int, actor: MagicActor, target: MagicTarget,
        direction: Direction, rng: RandomSource) -> tuple[int, bool]:
    if direction == Direction.PC_NPC:
        # Java performs integer division BEFORE Math.floor in this source.
        floor = _div(target.mr - actor.original_magic_hit, 2 if target.mr <= 100 else 10)
        factor = (1.0 if target.mr <= 100 else 0.6) - .01 * floor
        return int(damage * factor), False
    halved = target.mr >= rng.randint(1, 100)
    return (_div(damage, 2) if halved else damage), halved


def resolve_damage(actor: MagicActor, target: MagicTarget, spell: DamageSpell,
                   direction: Direction, rng: RandomSource) -> DamageResult:
    """Dice→INT/SP+attribute→weakness→crit→original→leverage→defense→MR.

    Counter Mirror returns a separate reflection+consume intent before MR.
    No recursion, physical hit merge or implicit spell resource application.
    """
    direction = Direction(direction)  # rejects PvP and unrecognized directions
    critical = False
    if spell.name == "FINAL_BURN":
        damage = actor.current_mp
    elif spell.name == "JOY_OF_PAIN" and direction == Direction.PC_NPC:
        damage = max(_div(actor.max_hp - actor.current_hp, 5), 5)
    else:
        damage = sum(rng.randint(1, spell.damage_dice) for _ in range(spell.dice_count)) + spell.damage_value
        if direction == Direction.PC_NPC:
            damage += actor.weapon_magic_damage
        intelligence = max(actor.intelligence + actor.sp - actor.true_sp - 12, 1)
        coefficient = max(1 - _attribute(target, spell.element, direction) + intelligence * 3.0 / 32, 0)
        damage = int(damage * coefficient)
        if direction == Direction.PC_NPC:
            if spell.element != Element.NONE and target.weak_element == spell.element:
                damage = int(damage * 1.2)
            if spell.skill_level <= 6:
                critical = rng.randint(1, 100) <= 10 + actor.original_magic_critical
                if critical:
                    damage = int(damage * 1.5)
            damage += actor.original_magic_damage
            if actor.illusion_avatar:
                damage += 10
        damage = _div(damage * spell.leverage, 10)

    reflected = 0
    consumed: tuple[str, ...] = ()
    if direction == Direction.NPC_PC:
        damage -= target.reduction
        if target.immune_to_harm:
            damage = _div(damage, 2)
        if target.immune:
            damage = 0
        # Preserve Java evaluation order: WIS random precedes NPC exclusions.
        if target.counter_mirror and target.wisdom > rng.randint(0, 99):
            if actor.npc_id not in (45681, 45682, 45683, 45684) and actor.npc_is_erase:
                reflected = max(damage, 0)
                consumed = ("COUNTER_MIRROR",)
                damage = 0
        damage = max(damage, 0)
        # Source overrides previous defenses for these two spells at this point.
        if spell.name == "FINAL_BURN":
            damage = max(actor.current_mp, 0)
        elif spell.name == "JOY_OF_PAIN":
            damage = max(_div(actor.max_hp - actor.current_hp, 5), 5)
    elif target.immune or target.missing_required_effect:
        damage = 0

    halved = False
    if spell.name != "JOY_OF_PAIN":
        damage, halved = _mr(damage, actor, target, direction, rng)
    return DamageResult(max(damage, 0), critical, halved, reflected, consumed)


@dataclass(frozen=True)
class StatusSpell:
    name: str
    probability_dice: int
    probability_value: int
    leverage: int = 10

    def __post_init__(self):
        special = self.name in _LEVEL_STATUS or self.name in ("SHOCK_STUN", "COUNTER_BARRIER", "GUARD_BRAKE", "RESIST_FEAR", "HORROR_OF_DEATH", "THUNDER_GRAB", "PHANTASM", "CANCELLATION")
        if not self.name or self.probability_dice < (0 if special else 1) or self.leverage < 0:
            raise ValueError("explicit status parameters required; rolling paths need positive dice")


@dataclass(frozen=True)
class StatusResult:
    succeeded: bool
    probability: int
    roll: int | None
    effect: str
    policy: str = "LOCAL_REFERENCE_L1J"


_LEVEL_STATUS = frozenset(("ELEMENTAL_FALL_DOWN", "RETURN_TO_NATURE", "ENTANGLE", "ERASE_MAGIC", "AREA_OF_SILENCE", "WIND_SHACKLE", "STRIKER_GALE", "POLLUTE_WATER", "EARTH_BIND", "DARK_BLIND"))
_RESIST_STATUS = {"EARTH_BIND": ("sustain", 1), "SHOCK_STUN": ("stun", 2),
                  "CURSE_PARALYZE": ("stone", 1), "FOG_OF_SLEEPING": ("sleep", 1),
                  "ICE_LANCE": ("freeze", 1), "FREEZING_BLIZZARD": ("freeze", 1),
                  "FREEZING_BREATH": ("freeze", 1), "CURSE_BLIND": ("blind", 1),
                  "DARKNESS": ("blind", 1), "DARK_BLIND": ("blind", 1)}


def resolve_status(actor: MagicActor, target: MagicTarget, spell: StatusSpell,
                   direction: Direction, rng: RandomSource) -> StatusResult:
    """Return success intent; SKILL owner applies existing duration/effect rules."""
    direction = Direction(direction)
    name = spell.name
    if target.missing_required_effect:
        return StatusResult(False, 0, None, name)
    if name == "CANCELLATION":
        return StatusResult(True, 100, None, name)
    if target.earth_bound and name != "WEAPON_BREAK":
        return StatusResult(False, 0, None, name)
    defense_level = target.master_level if name == "RETURN_TO_NATURE" and target.master_level is not None else target.level
    diff = actor.level - defense_level
    original = 2 * actor.original_magic_hit if direction == Direction.PC_NPC else 0
    if name in _LEVEL_STATUS:
        probability = spell.probability_value + int(spell.probability_dice / 10.0 * _div(diff, 2)) + original
    elif name == "SHOCK_STUN":
        probability = spell.probability_value + diff * 2 + original
    elif name == "COUNTER_BARRIER":
        probability = spell.probability_value + max(0, _div(actor.level - max(60, target.level), 4)) + original
    elif name in ("GUARD_BRAKE", "RESIST_FEAR", "HORROR_OF_DEATH"):
        probability = 100
    elif name == "THUNDER_GRAB":
        probability = spell.probability_value * _div(actor.level, max(1, defense_level)) + rng.randint(0, 20) + original
    elif name == "PHANTASM":
        probability = 30
    else:
        count = max(1, actor.magic_bonus + actor.magic_level + ((1 if actor.is_wizard else -1) if direction == Direction.PC_NPC else 0))
        probability = _div(sum(rng.randint(1, spell.probability_dice) for _ in range(count)) * spell.leverage, 10) + original - target.mr
        if name == "TAMING_MONSTER":
            fraction = next((factor for numerator, factor in ((1, 1.3), (2, 1.2), (3, 1.1)) if _div(target.max_hp * numerator, 4) > target.current_hp), 1.0)
            probability = int(probability * fraction)
    if direction == Direction.NPC_PC and name in _RESIST_STATUS:
        resist, multiplier = _RESIST_STATUS[name]
        probability -= getattr(target.resists, resist) * multiplier
    probability = min(probability, 90)
    roll = rng.randint(1, 100)
    return StatusResult(probability >= roll, probability, roll, name)


@dataclass(frozen=True)
class HealingSpell:
    name: str
    damage_dice: int
    damage_value: int
    leverage: int = 10

    def __post_init__(self):
        if not self.name or self.damage_dice < 1 or self.leverage < 0:
            raise ValueError("explicit healing name, positive dice and nonnegative leverage required")


@dataclass(frozen=True)
class HealingResult:
    amount: int
    policy: str = "LOCAL_REFERENCE_L1J"


def resolve_heal(actor: MagicActor, spell: HealingSpell, rng: RandomSource) -> HealingResult:
    """L1Magic.calcHealing; HP owner clamps max HP and rejects dead targets."""
    count = max(0, spell.damage_value + min(10, actor.magic_bonus))
    amount = sum(rng.randint(1, spell.damage_dice) for _ in range(count))
    if actor.lawful > 0:
        amount = int(amount * (1.0 + actor.lawful / 32768.0))
    return HealingResult(max(0, _div(amount * spell.leverage, 10)))


def resolve_firewall(target: MagicTarget, damage_value: int,
                     direction: Direction) -> DamageResult:
    """Separate source path: firewall has attribute reduction, no INT/crit/MR."""
    direction = Direction(direction)
    damage = int((1 - _attribute(target, Element.FIRE, direction)) * damage_value)
    return DamageResult(0 if target.immune else max(0, damage))


@dataclass(frozen=True)
class WeaponProc:
    """Explicit selected L1WeaponSkill table row; no NC item-ID translation.

    use_int_procs selects that source's Config policy, including its documented
    arbitrary INT18/SP13 floors and multiplier boost. Caller must choose it.
    Special weapons with bespoke switch branches are not generic table rows.
    """
    name: str
    probability: int
    fix_damage: int
    random_damage: int
    element: Element
    use_int_procs: bool
    multiplier: float
    effect_id: int
    buff_name: str | None = None
    buff_seconds: int = 0
    effect_on_attacker: bool = False
    arrow_visual: bool = False
    area: int = 0

    def __post_init__(self):
        if not self.name or self.random_damage < 0 or self.multiplier < 0 or self.buff_seconds < 0:
            raise ValueError("explicit weapon row and nonnegative dice/multiplier/duration required")
        if self.area:
            raise NotImplementedError("area procs require the world owner's selected target set; single-target only")


@dataclass(frozen=True)
class EffectIntent:
    name: str
    duration_ms: int


@dataclass(frozen=True)
class WeaponProcResult:
    triggered: bool
    damage: int = 0
    effects: tuple[EffectIntent, ...] = ()
    consume_effects: tuple[str, ...] = ()
    effect_id: int | None = None
    effect_on_attacker: bool = False
    arrow_visual: bool = False
    policy: str = "LOCAL_REFERENCE_L1J"


def resolve_weapon_proc(actor: MagicActor, target: MagicTarget, proc: WeaponProc,
                        rng: RandomSource, *, berserkers: bool = False) -> WeaponProcResult:
    """PC→NPC table proc only, separate from physical hit and spell critical.

    L1WeaponSkill lines 239-282,402-410,479-545. Physical caller decides the
    source-backed invocation boundary, then keeps this separate result on its
    operation. It does not turn physical miss into Hit(False, positive).
    """
    if proc.probability < rng.randint(1, 100):
        return WeaponProcResult(False)
    # A buff row calls isImmune before applying the buff or visual.
    blocked = target.immune or target.frozen or target.counter_magic
    consumed = ("COUNTER_MAGIC",) if target.counter_magic and not (target.immune or target.frozen) else ()
    if proc.buff_name and blocked:
        return WeaponProcResult(True, consume_effects=consumed)
    effects = (EffectIntent(proc.buff_name, proc.buff_seconds * 1000),) if proc.buff_name else ()
    damage = 0.0
    # Source deliberately gates BOTH Config branches by randomDamage > 0.
    if proc.random_damage > 0:
        if proc.use_int_procs:
            combined = max(actor.intelligence, 18) + max(actor.sp, 13)
            damage = combined * (proc.multiplier * 1.5 + (.2 if berserkers else 0)) + rng.randint(0, combined - 1) * proc.multiplier * 1.5
        else:
            damage = proc.fix_damage + rng.randint(1, proc.random_damage)
    if blocked:
        damage = 0
    else:
        floor = _div(target.mr - actor.original_magic_hit, 2 if target.mr <= 100 else 10)
        damage *= (1.0 if target.mr <= 100 else .6) - .01 * floor
        resist = getattr(target.resists, proc.element.value) if proc.element != Element.NONE else 0
        damage *= 1 - resist / 100.0
    return WeaponProcResult(True, max(0, int(damage)), effects, consumed,
                            proc.effect_id, proc.effect_on_attacker, proc.arrow_visual)
