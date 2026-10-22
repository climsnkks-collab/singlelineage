"""Pure direction-specific PvE resolver under LOCAL_L1J_EN_103e6f6 policy.

Source parent is pinned in combat_stats. Implements L1Attack.java 624-710,
750-855,924-1047,1106-1150. Zero post-reduction damage deliberately remains a
landed zero-damage result, so the existing attack owner can finish the action.
No HP writer, sender, persistence, stat-file loading or RNG cache lives here.
"""
from dataclasses import dataclass
from typing import Protocol
try:
    from .combat_stats import DerivedStats, STR_DAMAGE, DEX_DAMAGE, POLICY
except ImportError:
    from combat_stats import DerivedStats, STR_DAMAGE, DEX_DAMAGE, POLICY

class Rng(Protocol):
    def randint(self, a: int, b: int) -> int: ...

@dataclass(frozen=True)
class Ammo:
    small: int
    large: int
    material: int = 0
    bless: int = 1
    def __post_init__(self):
        if min(self.small,self.large) < 0:
            raise ValueError("negative ammo damage")

@dataclass(frozen=True)
class Weapon:
    kind: str
    small: int
    large: int
    enchant: int = 0
    damage: int = 0
    add_hit: int = 0
    add_damage: int = 0
    double_chance: int = 0
    material: int = 0
    bless: int = 1
    holy_damage: int = 0
    ammo: Ammo | None = None
    def __post_init__(self):
        if self.kind not in ("melee","bow","gauntlet","claw","edoryu","fist"):
            raise ValueError("unsupported weapon kind; special weapon must have its own source rule")
        if min(self.small,self.large,self.damage,self.holy_damage) < 0 or not 0 <= self.double_chance <= 100:
            raise ValueError("invalid weapon damage/chance")
        if self.kind in ("bow","gauntlet") and self.ammo is None:
            raise ValueError("ranged weapon requires actual ammo; special infinite-ammo bows unsupported")
        if self.kind not in ("bow","gauntlet") and self.ammo is not None:
            raise ValueError("ammo attached to melee weapon")
        if self.double_chance and self.kind not in ("claw","edoryu"):
            raise ValueError("no generic physical critical/double coefficient")
        if self.kind not in ("bow","gauntlet","fist") and min(self.small,self.large) < 1:
            raise ValueError("melee requires positive small/large die")

@dataclass(frozen=True)
class NpcDefense:
    ac: int
    reduction: int
    size: str
    undead: int = 0
    hard_skin: bool = False
    immune: bool = False
    hit_adjustment: int = 0
    def __post_init__(self):
        if self.size not in ("small","large") or self.reduction < 0:
            raise ValueError("explicit NPC size/reduction required")

@dataclass(frozen=True)
class NpcOffense:
    level: int
    strength: int
    hitup: int
    dmgup: int
    leverage: int = 10
    undead_night_bonus: bool = False
    weapon_broken: bool = False
    def __post_init__(self):
        if self.level < 1 or self.strength < 0 or self.leverage < 0:
            raise ValueError("explicit valid NPC offense required")

@dataclass(frozen=True)
class PcNpcContext:
    player: DerivedStats
    weapon: Weapon
    target: NpcDefense
    ranged: bool = False
    weight240: int = 0
    effects: tuple[str,...] = ()
    def __post_init__(self):
        if self.ranged != (self.weapon.kind in ("bow","gauntlet")):
            raise ValueError("ranged/weapon kind mismatch")
        if not isinstance(self.effects,tuple) or len(set(self.effects)) != len(self.effects) or any(e not in ("soul_of_flame","double_brake","burning_slash") for e in self.effects):
            raise ValueError("unsupported or duplicate source effect")
        if "double_brake" in self.effects and self.weapon.kind not in ("claw","edoryu"):
            raise ValueError("double brake requires claw/edoryu")
        if "soul_of_flame" in self.effects and self.ranged:
            raise ValueError("soul of flame is melee only")
        if not 0 <= self.weight240 <= 240:
            raise ValueError("weight240 out of range")

@dataclass(frozen=True)
class NpcPcContext:
    npc: NpcOffense
    player: DerivedStats
    ranged: bool = False
    distance: int = 1
    ranged_template: int = 0
    target_hit_adjustment: int = 0
    target_immune: bool = False
    soft_ac: bool = True
    immune_to_harm: bool = False
    reduction_armor: bool = False
    patience: bool = False
    def __post_init__(self):
        if self.ranged != (self.ranged_template >= 10 and self.distance >= 2):
            raise ValueError("ranged mode must match source template/distance condition")

@dataclass(frozen=True)
class PhysicalResult:
    landed: bool
    damage: int
    procs: tuple[str,...] = ()
    consume_effects: tuple[str,...] = ()
    policy: str = POLICY
    # These are distinct channels, currently unsupported rather than fabricated.
    critical: bool = False
    extra_attacks: tuple = ()


def _d20_hit(rng, hit, adjustment, defender, npc=False):
    attack = rng.randint(1,20) + hit - (1 if npc else 10) + adjustment
    fumble = hit if npc else hit - 9
    critical = hit + (19 if npc else 10)
    # 'critical' here is an automatic HIT boundary, not critical damage.
    return False if attack <= fumble else True if attack >= critical else attack > defender


def _material_damage(rng, weapon, target):
    material, bless = weapon.material, weapon.bless
    if weapon.ammo is not None:
        material = weapon.ammo.material
        bless = 0 if weapon.bless == 0 or weapon.ammo.bless == 0 else weapon.ammo.bless
    damage = 0
    if material in (14,17,22) and target.undead in (1,3,5):
        damage += rng.randint(1,20)
    if material in (17,22) and target.undead == 2:
        damage += rng.randint(1,3)
    if bless == 0 and target.undead in (1,2,3):
        damage += rng.randint(1,4)
    if weapon.ammo is None and target.undead in (1,3):
        damage += weapon.holy_damage
    return damage


def resolve_pc_npc(context: PcNpcContext, rng: Rng) -> PhysicalResult:
    p,w,t = context.player,context.weapon,context.target
    enchant = w.enchant if context.ranged else w.enchant - w.damage
    weight = context.weight240
    weight_hit = -1 if 80 < weight <= 120 else -3 if 121 <= weight <= 160 else -5 if 161 <= weight <= 200 else 0
    hit = (p.ranged_hit if context.ranged else p.melee_hit) + w.add_hit + int(enchant/2) + weight_hit
    if not _d20_hit(rng,hit,t.hit_adjustment,10-t.ac) or t.immune:
        return PhysicalResult(False,0)
    procs = []
    maximum = w.small if t.size == "small" else w.large
    if w.kind == "claw" and rng.randint(1,100) <= w.double_chance:
        base = maximum
        procs.append("claw_maximum")
    elif w.kind == "fist" or context.ranged:
        base = 0
    else:
        base = rng.randint(1,maximum)
    if "soul_of_flame" in context.effects:
        base = maximum
    weapon_total = base+w.add_damage+enchant+_material_damage(rng,w,t)
    if w.kind == "edoryu" and rng.randint(1,100) <= w.double_chance:
        weapon_total *= 2
        procs.append("edoryu_double")
    if "double_brake" in context.effects and rng.randint(1,100) <= 33:
        weapon_total *= 2
        procs.append("double_brake")
    damage = weapon_total + (p.ranged_damage if context.ranged else p.melee_damage)
    if w.kind == "gauntlet":
        # Pinned constructor uses STR for gauntlet; ranged direct modifiers remain ranged.
        damage += STR_DAMAGE[p.current.str] - DEX_DAMAGE[p.current.dex]
    if w.ammo is not None:
        maximum_ammo = w.ammo.small if t.size == "small" else w.ammo.large
        maximum_ammo = max(1,maximum_ammo)
        if w.kind == "bow" and t.hard_skin:
            maximum_ammo //= 2
        if maximum_ammo < 1:
            # Java nextInt(0) is invalid: surface unsupported template, don't invent a die.
            raise ValueError("hard-skinned target leaves invalid zero ammo die in pinned reference")
        damage += rng.randint(1,maximum_ammo)
    consume = ()
    if "burning_slash" in context.effects:
        damage += 10
        consume = ("burning_slash",)
    if w.kind == "fist":
        damage = rng.randint(4,8)//4 + p.equipment_melee_damage
    return PhysicalResult(True,max(0,int(damage-t.reduction)),tuple(procs),consume)


def resolve_npc_pc(context: NpcPcContext, rng: Rng) -> PhysicalResult:
    n,p = context.npc,context.player
    hit = n.level+n.hitup
    attack = rng.randint(1,20)+hit-1+context.target_hit_adjustment
    defender = 10-p.ac if p.ac >= 0 else 10+rng.randint(1,-p.ac)
    landed = False if attack <= hit else True if attack >= hit+19 else attack > defender
    if not landed or context.target_immune:
        return PhysicalResult(False,0)
    # ER is only the source-backed ranged NPC branch, not a second melee avoidance roll.
    if context.ranged and p.er >= rng.randint(1,100):
        return PhysicalResult(False,0)
    damage = rng.randint(1,n.level) + n.strength//2 + n.dmgup
    if n.undead_night_bonus:
        damage *= 1.1
    damage = damage*n.leverage/10
    divisor = {"royal":3,"knight":2,"elf":3,"wizard":5}[p.character_class] if context.soft_ac else 2
    damage -= rng.randint(0,max(0,10-p.ac)//divisor)
    if n.weapon_broken:
        damage /= 2
    damage -= p.reduction
    if context.reduction_armor:
        damage -= (max(50,p.level)-50)//5+1
    if context.patience:
        damage -= 2
    if context.immune_to_harm:
        damage /= 2
    return PhysicalResult(True,max(0,int(damage)))
