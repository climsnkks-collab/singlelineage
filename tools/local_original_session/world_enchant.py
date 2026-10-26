"""Pure LOCAL backend enchant policy; no inventory, packets, persistence or RNG.

This adopts the fixed L1J Enchant.java rules documented in data/m1/enchant.json,
not a claim about Classic probabilities or native grade encoding. Classic scroll
templates 25/26 identify weapon/armor only. Scroll.grade MUST be supplied by a
local instance contract (0 blessed, 1 normal, 2 cursed); None is rejected. Never
pass L1J item IDs as Classic IDs or infer grade from a template ID.

Pure function signatures for the future world_handlers consumer::

    propose_enchant(scroll: EnchantScroll,
                    target: EnchantTarget) -> EnchantProposal
    resolve_enchant(proposal: EnchantProposal, *, outcome_roll: int,
                    blessing_roll: int) -> EnchantResult
    weapon_enchant_bonus(level: int, *, durability: int = 0,
                         ranged: bool = False) -> EnchantCombatBonus
    armor_enchant_ac_bonus(level: int, *, accessory: bool = False) -> int

The intended handler call order is::

    proposal = propose_enchant(EnchantScroll(template_id, grade),
                               EnchantTarget(template_id, kind, level, ...))
    result = resolve_enchant(proposal, outcome_roll=randint(1, 100),
                             blessing_roll=randint(1, 100))

The handler owns actual instance lookup, ownership/count and target selection,
request ordering, and an atomic inventory/persistence transaction. A rejection
consumes nothing. Every accepted result consumes exactly one scroll, including
unchanged/destroyed results; destruction removes the actual target instance,
unequips it and updates stats. Success changes only that target's level. Commit
scroll consumption, target mutation/removal, equipment stat changes and save
together before publishing success; this module performs none of those writes.
No proposal is an authorization or a receipt, and resolving it has no effects.

The M1 table reuses existing item correspondences and each SQL safenchant value.
Unknown targets need explicit safe_enchant AND normal_scroll_eligible=True;
special/quest/illusion/Ivory Tower eligibility must be established by the caller.
No GM bypass, accessory, elemental or special-scroll path is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import json
from pathlib import Path


POLICY_PATH = Path(__file__).resolve().parent / 'data' / 'm1' / 'enchant.json'


@dataclass(frozen=True, slots=True)
class EnchantScroll:
    template_id: int
    grade: int | None  # required LOCAL instance grade, never inferred


@dataclass(frozen=True, slots=True)
class EnchantTarget:
    template_id: int
    kind: str  # weapon / armor (accessories are outside this contract)
    level: int
    safe_enchant: int | None = None
    bless: int = 1  # L1J >=128 disallows enchanting; not a native wire claim
    normal_scroll_eligible: bool | None = None


@dataclass(frozen=True, slots=True)
class EnchantProposal:
    scroll: EnchantScroll
    target: EnchantTarget
    accepted: bool
    reason: str
    safe_enchant: int | None
    success_rolls: int = 0
    unchanged_rolls: int = 0
    destroyed_rolls: int = 0
    # (level delta, number of blessing rolls out of 100), conditional on success
    delta_rolls: tuple[tuple[int, int], ...] = ()

    @property
    def success_probability(self) -> Fraction:
        return Fraction(self.success_rolls, 100)

    @property
    def unchanged_probability(self) -> Fraction:
        return Fraction(self.unchanged_rolls, 100)

    @property
    def destroyed_probability(self) -> Fraction:
        return Fraction(self.destroyed_rolls, 100)

    @property
    def delta_probabilities(self) -> tuple[tuple[int, Fraction], ...]:
        """Unconditional probability for each successful level delta."""
        return tuple((delta, Fraction(count * self.success_rolls, 10000))
                     for delta, count in self.delta_rolls)


@dataclass(frozen=True, slots=True)
class EnchantResult:
    status: str  # rejected / success / unchanged / destroyed
    reason: str
    level_before: int
    level_after: int | None
    level_delta: int | None  # None on destruction: the instance no longer exists
    consume_scroll: int
    remove_target: bool


@lru_cache(maxsize=1)
def _policy() -> dict:
    # Private policy data; callers receive only immutable proposals/results.
    return json.loads(POLICY_PATH.read_text(encoding='utf-8'))


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f'{name} must be an integer')
    return value


def _delta_rolls(grade: int, level: int) -> tuple[tuple[int, int], ...]:
    if grade == 2:
        return ((-1, 100),)
    if grade == 0 and level <= 2:
        return ((1, 32), (2, 44), (3, 24))
    if grade == 0 and level <= 5:
        return ((2, 49), (1, 51))
    return ((1, 100),)


def propose_enchant(scroll: EnchantScroll, target: EnchantTarget) -> EnchantProposal:
    """Return exact roll counts/probabilities and eligibility without effects.

    Known M1 equipment uses its per-item SQL safenchant. Unknown equipment is
    rejected unless both safety and ordinary-scroll eligibility are explicit.
    Explicit safety conflicting with a known row is rejected, not substituted.
    """
    for value, name in ((scroll.template_id, 'scroll.template_id'),
                        (target.template_id, 'target.template_id'),
                        (target.level, 'target.level'), (target.bless, 'target.bless')):
        _integer(value, name)
    if target.safe_enchant is not None:
        _integer(target.safe_enchant, 'target.safe_enchant')
    if target.normal_scroll_eligible is not None and type(target.normal_scroll_eligible) is not bool:
        raise TypeError('normal_scroll_eligible must be bool or None')
    safe = target.safe_enchant

    def reject(reason: str) -> EnchantProposal:
        return EnchantProposal(scroll, target, False, reason, safe)

    policy = _policy()
    scroll_row = next((row for row in policy['scrolls']
                       if row['classic_id'] == scroll.template_id), None)
    if scroll_row is None:
        return reject('unsupported_scroll_template')
    if type(scroll.grade) is not int or scroll.grade not in (0, 1, 2):
        return reject('unresolved_or_invalid_local_grade')
    if target.kind != scroll_row['kind']:
        return reject('scroll_target_kind_mismatch')
    row = next((row for row in policy['equipment']
                if row['classic_id'] == target.template_id), None)
    if row is not None:
        if target.kind != row['kind']:
            return reject('target_template_kind_mismatch')
        if safe is not None and safe != row['safe_enchant']:
            return reject('target_safety_conflicts_with_policy')
        safe = row['safe_enchant']
    if safe is None:
        return reject('unresolved_target_safety')
    if safe < 0 or target.bless >= 128:
        return reject('target_cannot_be_enchanted')
    eligible = target.normal_scroll_eligible
    if eligible is False:
        return reject('target_requires_special_scroll')
    if row is None and eligible is not True:
        return reject('unresolved_normal_scroll_eligibility')

    if scroll.grade == 2:
        success, unchanged = (100 if target.level > -7 else 0), 0
    elif target.level < safe:
        success, unchanged = 100, 0
    else:
        if target.kind == 'weapon':
            divisor = 6 if target.level >= 9 else 3
            threshold = (103 + policy['rates']['weapon']) // divisor
        else:
            divisor = target.level + 2 if safe == 0 else target.level
            threshold = ((100 + divisor * policy['rates']['armor'])
                         // (divisor * (2 if target.level >= 9 else 1)))
        # Java rolls are 1..100 and comparisons are STRICT <, not <=.
        success = sum(roll < threshold for roll in range(1, 101))
        unchanged = sum(threshold <= roll < threshold * 2
                        for roll in range(1, 101)) if target.level >= 9 else 0
    return EnchantProposal(scroll, target, True, 'local_l1j_policy', safe,
                           success, unchanged, 100 - success - unchanged,
                           _delta_rolls(scroll.grade, target.level))


def _roll(value: int, name: str) -> int:
    _integer(value, name)
    if not 1 <= value <= 100:
        raise ValueError(f'{name} must be in 1..100')
    return value


def resolve_enchant(proposal: EnchantProposal, *, outcome_roll: int,
                    blessing_roll: int) -> EnchantResult:
    """Resolve explicit independent 1..100 rolls; never draw RNG or mutate data.

    Production callers must supply unbiased independent rolls for probabilistic
    paths (constant 1 is sufficient for guaranteed paths). The module does
    not maintain replay state; handlers must not apply a result more than once.
    """
    level = proposal.target.level
    if not proposal.accepted:
        return EnchantResult('rejected', proposal.reason, level, level, 0, 0, False)
    _roll(outcome_roll, 'outcome_roll')
    _roll(blessing_roll, 'blessing_roll')
    if outcome_roll <= proposal.success_rolls:
        remaining = blessing_roll
        for delta, count in proposal.delta_rolls:
            remaining -= count
            if remaining <= 0:
                return EnchantResult('success', proposal.reason, level,
                                     level + delta, delta, 1, False)
        raise ValueError('proposal has no complete successful delta distribution')
    if outcome_roll <= proposal.success_rolls + proposal.unchanged_rolls:
        return EnchantResult('unchanged', proposal.reason, level, level, 0, 1, False)
    return EnchantResult('destroyed', proposal.reason, level, None, None, 1, True)


@dataclass(frozen=True, slots=True)
class EnchantCombatBonus:
    effective_enchant: int
    damage: int
    hit: int


def weapon_enchant_bonus(level: int, *, durability: int = 0,
                         ranged: bool = False) -> EnchantCombatBonus:
    """L1Attack enchant contribution before other damage/hit calculations.

    Ranged means bow/gauntlet in the referenced L1J policy. Negative effective
    enchant is retained and Java /2 truncates toward zero, unlike Python //2.
    """
    _integer(level, 'level')
    _integer(durability, 'durability')
    if durability < 0:
        raise ValueError('durability must be nonnegative')
    if type(ranged) is not bool:
        raise TypeError('ranged must be bool')
    effective = level - (0 if ranged else durability)
    hit = effective // 2 if effective >= 0 else -((-effective) // 2)
    return EnchantCombatBonus(effective, effective, hit)


def armor_enchant_ac_bonus(level: int, *, accessory: bool = False) -> int:
    """AC contribution only; add to base/magic AC. Accessories gain no such AC."""
    _integer(level, 'level')
    if type(accessory) is not bool:
        raise TypeError('accessory must be bool')
    return 0 if accessory else -level
