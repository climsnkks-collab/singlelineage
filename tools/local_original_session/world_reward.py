"""Pure M1 solo kill arithmetic; no kill authority, delivery, UID or persistence.

Usage::

    inputs = RewardPcState.from_combat(pc_state, exp=stored_cumulative_exp)
    reward = on_kill(inputs, monster_def, rng)

The caller applies the result through its existing progression/resource/custody
owners. Calling this function twice rolls twice: it is NOT a kill-once service.
The previous progression-kill-delivery-v1/API.md consumes an actual Death/KillPort
and native owner, and npc-born-single-delivery-parent/native-npc-born-item-custody
consume source-owned birth rolls. They cannot be invoked by a numeric preview.
Their distinction between calculation DATA and a committed reward is preserved.

Reference: D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/
  utils/CalcExp.java:457-468 solo hate share; :517-560 AddExp.
  datatables/ExpTable.java:83-89 PC-level penalty (1 below level 50).
The inspected solo calculation has NO PC-versus-monster level difference
correction. M1 uses the full monster EXP at x1, one player/no party, food or map
bonus. Levels are limited to the supplied pc_exp table (currently 1..99); EXP
above its last threshold is retained without inventing higher-level thresholds.

Growth adopts utils/CalcStat.java:101-156 HP, :168-250 MP and
model/Instance/L1PcInstance.java:3546-3551 (one HP/MP roll per gained level).
Class original bonuses: model/classes/L1{Royal,Knight,Elf,Wizard}ClassFeature.java
:87-99. Caps: config/charsettings.properties:6-13. These are L1J-derived LOCAL
backend policy, not verified Classic formulas. M1 supports classes 0..3 only.
PcProfile itself has no base/original stat distinction. The core equipment
adapter preserves saved CON/WIS and growth maxima on the bound state;
from_combat uses those bases, with legacy PcState profile/maxima as fallback.
LOCAL policy uses saved CON/WIS as both base and creation stats.
L1J clamps the base increment BEFORE adding the original-stat bonus; retained.

DropTable.java:158-184 supplies a 1..1,000,000 chance die and inclusive count.
Only resolved data.drops rows are rolled, at x1 rates, independently in table
order after growth. Unresolved rows are never awarded. Drops are calculation
tuples, not inventory/ground items. rolled_rows retains grade/source identities
for a later custody caller; do not reconstruct grade from item_id alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import random
from typing import TYPE_CHECKING

from tools.local_original_session.game_data import CHANCE_DENOMINATOR, DropDef, M1Data, MonsterDef, load_m1

if TYPE_CHECKING:
    from tools.local_original_session.world_combat import PcProfile, PcState


@dataclass(frozen=True, slots=True)
class RewardPcState:
    """Snapshot of explicit cumulative EXP plus the combat growth inputs."""
    exp: int
    profile: PcProfile
    max_hp: int
    max_mp: int | None

    @classmethod
    def from_combat(cls, pc_state: PcState, *, exp: int) -> RewardPcState:
        # SC_STATUS f2 is level; f10..13 are HP/MP. EXP has no established
        # SC_STATUS field, so the caller must provide its saved progression EXP.
        from dataclasses import replace
        from tools.local_original_session.world_progress import base_maxima
        hp, mp = base_maxima(pc_state)
        profile = replace(pc_state.profile,
            con=getattr(pc_state, 'base_growth_con', pc_state.profile.con),
            wis=getattr(pc_state, 'base_growth_wis', pc_state.profile.wis))
        return cls(exp, profile, hp, mp)

    @classmethod
    def from_companion(cls, record, profile, *, attributes=None):
        """Record maxima are growth bases; worn CON/WIS do not affect rolls."""
        from dataclasses import replace
        profile = replace(profile, level=record.level,
            con=profile.con if attributes is None else attributes[2],
            wis=profile.wis if attributes is None else attributes[3])
        return cls(record.exp, profile, record.max_hp, record.max_mp)


@dataclass(frozen=True, slots=True)
class KillReward:
    exp_gained: int
    new_exp: int
    old_level: int
    new_level: int
    level_ups: int
    max_hp: int
    max_mp: int | None
    drops: list[tuple[int, int]]
    rolled_rows: tuple[DropDef, ...]  # Same order as drops; preserves grade.


def _original_hp(character_class: int, con: int) -> int:
    if character_class == 0:
        return 3 if con >= 16 else 2 if con >= 14 else 1 if con >= 12 else 0
    if character_class == 1:
        return 3 if con >= 17 else 1 if con >= 15 else 0
    if character_class == 2:
        return 2 if con == 18 else 1 if con >= 13 else 0
    return 2 if con >= 16 else 1 if con >= 14 else 0


def _original_mp(character_class: int, wis: int) -> int:
    if character_class == 0:
        return int(wis >= 16)
    if character_class == 1:
        return 0
    if character_class == 2:
        return 2 if wis >= 17 else 1 if wis >= 14 else 0
    return 2 if wis >= 17 else 1 if wis >= 13 else 0


def _mp_die(wis: int, rng: random.Random) -> int:
    if wis < 9 or 9 < wis < 12:
        sides = 2
    elif wis == 9 or 12 <= wis <= 17:
        sides = 3
    elif 18 <= wis <= 23 or wis in (25, 26, 29, 30, 33, 34):
        sides = 4
    else:
        sides = 5
    bonus = 0 if wis < 10 else 1 if wis < 15 else 2 if wis < 21 else 3 if wis < 25 else 4 if wis < 29 else 5 if wis < 33 else 6
    return rng.randint(1, sides) + bonus


@lru_cache(maxsize=1)
def _default_data() -> M1Data:
    return load_m1()


def _growth_roll(profile, max_hp, max_mp, rng, data):
    """One existing L1J LOCAL growth roll, capped before original bonuses."""
    character_class = profile.character_class
    growth = data.level_growth[character_class]
    hp_roll = growth.hp_base + rng.randint(0, 1) + max(profile.con - 15, 0)
    hp = max(0, min(hp_roll, growth.hp_cap - max_hp)
             + _original_hp(character_class, profile.con))
    mp = None
    if max_mp is not None:
        mp_roll = _mp_die(profile.wis, rng) * growth.mp_numerator // growth.mp_denominator
        mp = max(0, min(mp_roll, growth.mp_cap - max_mp)
                 + _original_mp(character_class, profile.wis))
    return hp, mp


def delevel_maxima(pc_state: RewardPcState, new_level: int, rng: random.Random,
                   *, data: M1Data | None = None) -> tuple[int, int | None]:
    """Calculate base maxima after level loss; no state, save or refill changes.

    L1J-derived LOCAL backend policy, not verified fixed-client behavior:
    L1PcInstance.java:3504-3511 draws a fresh CalcStat HP/MP roll with base=0
    for EACH lost level, rather than undoing a prior level-up. :937-957 floors
    base HP at 1 and base MP at 0. Unknown MP stays unknown without an MP draw.
    Regaining a level uses the ordinary fresh on_kill roll and no full heal.
    Caller supplies equipment-free maxima/CON/WIS, as with on_kill.
    """
    data = _default_data() if data is None else data
    profile = pc_state.profile
    if not 1 <= new_level <= profile.level:
        raise ValueError('new level must be between one and the current level')
    if data.level_for_exp(pc_state.exp) != profile.level:
        raise ValueError('profile level must match explicit cumulative EXP')
    if profile.character_class not in range(4):
        raise ValueError('M1 growth supports character classes 0..3 only')
    hp, mp = pc_state.max_hp, pc_state.max_mp
    for _ in range(profile.level - new_level):
        hp_loss, mp_loss = _growth_roll(profile, 0, None if mp is None else 0, rng, data)
        hp = max(1, hp - hp_loss)
        if mp is not None:
            mp = max(0, mp - mp_loss)
    return hp, mp


def on_kill(pc_state: RewardPcState, monster_def: MonsterDef, rng: random.Random,
            *, data: M1Data | None = None) -> KillReward:
    """Return a calculation without changing PcState, progression or inventory.

    Pass RewardPcState.from_combat(pc_state, exp=stored_exp). Optional ``data``
    selects already loaded immutable tables. Unknown max MP stays None: the HP
    roll still works, but no MP is fabricated and no MP RNG draw is consumed.
    No packet, refill or store operation is performed here.
    """
    data = _default_data() if data is None else data
    profile = pc_state.profile
    character_class = profile.character_class
    if character_class not in range(4):
        raise ValueError('M1 growth supports character classes 0..3 only')
    if pc_state.exp < 0 or monster_def.kill_exp < 0:
        raise ValueError('cumulative and kill EXP must be nonnegative')
    if data.level_for_exp(pc_state.exp) != profile.level:
        raise ValueError('profile level must match explicit cumulative EXP')
    gained = monster_def.kill_exp
    new_exp = pc_state.exp + gained
    new_level = data.level_for_exp(new_exp)
    level_ups = new_level - profile.level
    max_hp, max_mp = pc_state.max_hp, pc_state.max_mp
    for _ in range(level_ups):
        hp_gain, mp_gain = _growth_roll(profile, max_hp, max_mp, rng, data)
        max_hp += hp_gain
        if max_mp is not None:
            max_mp += mp_gain
    drops, rolled_rows = [], []
    for row in data.drops.get(monster_def.template_id, ()):
        if rng.randint(1, CHANCE_DENOMINATOR) <= row.chance:
            count = rng.randint(row.min_count, row.max_count)
            if count > 0:
                drops.append((row.item_id, count))
                rolled_rows.append(row)
    return KillReward(gained, new_exp, profile.level, new_level, level_ups,
                      max_hp, max_mp, drops, tuple(rolled_rows))


@dataclass(frozen=True, slots=True)
class DeathExpPenalty:
    """EXP calculation only; the caller owns death-once, growth and saving."""
    old_exp: int
    new_exp: int
    exp_lost: int
    old_level: int
    new_level: int
    loss_rate: float
    need_exp: int | None


def death_exp_loss_rate(level: int, *, penalty_divisor: int | None = None) -> float:
    """L1J-derived LOCAL backend rate, not a verified Classic death formula.

    Reference root: D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/.
    model/Instance/L1PcInstance.java:1227-1247 uses 0% at levels 1..10,
    10% at 11..44, 9/8/7/6/5% at 45/46/47/48/49, and 5% times
    datatables/ExpTable.java:83-89 getPenaltyRate at 50..99. That multiplier
    is 1 / Config.LVxx_EXP, not a second percentage of cumulative EXP.
    For 50+, supply that level's explicit configured positive divisor; this
    function does not invent config values outside the current M1 table.
    """
    if not 1 <= level <= 99:
        raise ValueError('L1J death EXP rates support levels 1..99 only')
    if level <= 10:
        return 0.0
    if level < 45:
        return 0.1
    if level < 50:
        return (54 - level) / 100.0
    if penalty_divisor is None or penalty_divisor <= 0:
        raise ValueError('level 50+ needs its configured positive EXP penalty divisor')
    return 0.05 * (1.0 / penalty_divisor)


def death_exp_penalty(exp: int, *, data: M1Data | None = None,
                      next_level_exp: int | None = None,
                      penalty_divisor: int | None = None) -> DeathExpPenalty:
    """Preview one death's EXP loss without changing a player or stored state.

    L1J-derived LOCAL backend policy, not verified original-client policy.
    Uses existing GameData cumulative pc_exp thresholds. ExpTable.java:40-52
    defines the loss basis as next-level minus current-level threshold;
    L1PcInstance.java:1227-1261 truncates the loss toward zero, subtracts it,
    then recalculates level immediately. Loss can cross the current level's
    lower threshold. There is no minimum-one loss or current-level floor.
    L1PcInstance.java:1005-1010 addExp has no zero floor either; the sourced
    table and 1..10 exemption already keep normal inputs nonnegative here.

    In this exact fork Death.run calls deathPenalty at :252 BEFORE its null
    attacker, zone, simulated-war, disabled-map-penalty and duel early returns
    (:254-260, :363-397). Those later conditions therefore do NOT exempt EXP.
    No invented zone/map/duel exemption flags are accepted by this calculator.

    The supplied LOCAL table provides levels 1..99. Missing penalty_divisor
    uses config/charsettings.properties:21-71's L1J defaults (50..64=1,
    65..69=2, 70..74=4, 75..78=8, 79..99=2**(level-75)). This death-only
    policy does not change the existing x1 kill reward. At the final supplied
    level, absent next_level_exp preserves EXP (zero loss); no missing next
    threshold is extrapolated. This preservation policy is LOCAL, not L1J.
    No HP/MP delevel rolls, packets, recovery eligibility, item loss, death-once
    authority or persistence are performed. L1J onChangeExp (:2189-2205) and
    levelDown (:3504-3526) handle resource changes and saving separately.
    """
    if exp < 0:
        raise ValueError('cumulative EXP must be nonnegative')
    data = _default_data() if data is None else data
    old_level = data.level_for_exp(exp)
    if old_level >= 50 and penalty_divisor is None:
        penalty_divisor = (1 if old_level < 65 else 2 if old_level < 70 else
                           4 if old_level < 75 else 8 if old_level < 79 else
                           1 << (old_level - 75))
    rate = death_exp_loss_rate(old_level, penalty_divisor=penalty_divisor)
    if next_level_exp is not None and old_level != len(data.pc_exp):
        raise ValueError('next_level_exp only supplies the last table level boundary')
    if old_level < len(data.pc_exp):
        next_exp = data.exp_for_level(old_level + 1)
    else:
        next_exp = next_level_exp
    if next_exp is not None and next_exp <= exp:
        raise ValueError('cumulative EXP reaches an unavailable next level')
    need_exp = None if next_exp is None else next_exp - data.exp_for_level(old_level)
    if rate == 0 or need_exp is None:
        lost = 0
    else:
        # Keep Java's multiply order and floating-point truncation, including
        # its separate reciprocal multiply for configured levels 50+.
        if old_level >= 50:
            lost = int(need_exp * 0.05 * (1.0 / penalty_divisor))
        else:
            lost = int(need_exp * rate)
    new_exp = exp - lost
    return DeathExpPenalty(exp, new_exp, lost, old_level,
                           data.level_for_exp(new_exp), rate, need_exp)
