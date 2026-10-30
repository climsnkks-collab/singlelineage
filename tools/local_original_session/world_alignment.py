"""Pure L1J-derived alignment policy, not verified Classic server rules.

Integration API (no broker/server/save changes in this module)::

    catalog = load_alignment_catalog()  # startup ONLY; explicit JSON read
    change = on_kill(saved_lawful, monster_def, catalog=catalog)
    stage = display_stage(change.new_lawful)
    result = roll_death_penalty(saved_lawful, items, rng,
                                penalty_applies=death_context_allows_penalty)
    healed = healing_amount(rolled_heal, caster_lawful, leverage=10)

The caller applies change.new_lawful once for an actual eligible kill, saves it,
and publishes the current value. All calculation functions, including on_kill,
perform NO file reads. catalog is mandatory and caller-owned. kill_change is the
numeric primitive for an already resolved NPC lawful/hate share. delta is the
actually applied, clamped change; requested_delta retains the rate calculation.
No kill-once, UID/custody, ground transfer, equipment removal, storage or packet
authority is supplied here. Repeating a roll repeats RNG consumption.

Fixed reference root: D:/SingleLineageRef/l1j-en-classic/.
src/l1j/server/server/utils/CalcExp.java:457-467 shares NPC lawful by hate with
Java integer division (truncate toward zero); :517-529 skips dead recipients,
casts (npc_share * RATE_LA) BEFORE negation, then separately truncates the
RATE_CHAO_LA multiplier when the PC was negative before the kill. There is no
level-difference factor in this path. M1 is one direct player, full hate share;
party/pet/summon distribution is not provided. config/rates.properties:70-75
defaults both rates to 1.0. model/L1Character.java:1015-1017 clamps addLawful to
[-32768,32767]. Arithmetic preserves Java truncation, not int32 overflow.
NPC lawful is SQL data, not inferred from sprite, level or Classic template ID.
M1's four NPCs have randomlawful=0 (L1NpcInstance.java:1084-1091).

Display stage adopts serverpackets/S_WhoCharinfo.java:35-42: negative chaotic,
0..499 neutral, >=500 lawful. command/executor/L1Who.java:111 uses a different
sign-only label; this API deliberately uses the packet's three ranges. Classic
name colors, exact visual thresholds and any stage bonuses remain UNKNOWN.

Death: model/Instance/L1PcInstance.java:419-440 rolls 1..1000 only when the
original signed lostRate is negative; negative PC lawful doubles its absolute
value. >=31983 therefore has zero item-loss probability, including full lawful.
Chaotic count is uniform 1..4/3/2/1 at <=-30000/-20000/-10000/<0; nonnegative
count is fixed one. penalty_applies MUST be supplied by the death caller after
the original early-return conditions (:254-260 missing attacker, :361-384 zone,
simulation-war and map death-penalty flag, :394-400 reciprocal duel). Those
contexts and EXP loss are outside this API; do not infer them from alignment.
caoPenaltyResult (:3462-3474) and model/L1PcInventory.java:645-663 select from
ALL inventory entries on every attempt, then protect Adena, nontradable entries
and active-pet amulets WITHOUT reroll. Equipment and blessed status alone are
not protection. Successful stacks drop in full; nonstacks drop one and may be
selected again if count remains. Caller must resolve current tradability/pet
bindings, unequip and transfer through existing owners. Empty inventory returns
no further candidates here (local total-function behavior; Java nextInt(0)
would throw). Protection reduces actual losses, not the initial roll chance.

Healing: model/L1Magic.java:714-735 applies 1+max(lawful,0)/32768 to the CASTING
character's rolled heal, truncates it, then integer-divides heal*leverage by10.
This is magic healing only: HpRegeneration.java and MpRegeneration.java contain
no lawful factor. No natural-regeneration or potion bonus is invented.

Existing Classic field evidence is reused without importing its hash-checking
wrappers: tools/local_self_info_profile/source.py OFFSETS[18] and model.py
provenance(): SC_SELF_INFO/SC_STATUS 0x4E38 f18 is Alignment, compiled protobuf
offset0x78 -> CharacterData offset0x7A4. Existing underlying evidence:
work/online_world_packet_source/world-notify-contract.json (0x4E38 f18 card
0x1091; tools/local_world_protocol/model.py CARD_TYPES maps it to signed int32)
and self-info-receiver.json (receiver RVA0x113540..0x114BFB).
work/online_character_field_meaning/source-contract.json separately identifies
character-list f6 as Alignment and Root.Alignment.Tx_Alignment; that is NOT
world SelfInfo f6. These are source/field connections, not proof that a new
value redraws the world UI. Mid-world update opcode/native refresh, actual
negative display/color and save/reconnect/runtime behavior are UNRUN/UNKNOWN.
Do not send L1J S_Lawful's unrelated legacy opcode to this Classic client.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from tools.local_original_session.game_data import M1_DATA_DIR, MonsterDef, Source

LAWFUL_MIN = -32768
LAWFUL_MAX = 32767
DEATH_CHANCE_DENOMINATOR = 1000


class RandomSource(Protocol):
    def randint(self, a: int, b: int) -> int: ...


def _integer(value: int) -> int:
    if type(value) is not int:
        raise ValueError('alignment requires integer values')
    return value


def clamp_lawful(lawful: int) -> int:
    return min(LAWFUL_MAX, max(LAWFUL_MIN, _integer(lawful)))


def _lawful(value: int) -> int:
    if clamp_lawful(value) != value:
        raise ValueError('PC lawful must be in -32768..32767')
    return value


def java_div(numerator: int, denominator: int) -> int:
    """Integer division toward zero without an intermediate float."""
    _integer(numerator)
    _integer(denominator)
    if denominator == 0:
        raise ZeroDivisionError('integer division by zero')
    result = abs(numerator) // abs(denominator)
    return -result if (numerator < 0) != (denominator < 0) else result


@dataclass(frozen=True, slots=True)
class AlignmentNpc:
    template_id: int
    l1j_npcid: int
    lawful: int
    source: Source


def load_alignment_catalog(directory: Path | str = M1_DATA_DIR) -> Mapping[int, AlignmentNpc]:
    """Startup-only loading boundary; joins explicit Classic and L1J IDs."""
    directory = Path(directory)
    document = json.loads((directory / 'alignment.json').read_text(encoding='utf-8'))
    monsters = json.loads((directory / 'monsters.json').read_text(encoding='utf-8'))
    known = {r['template_id']['value']: r['l1j_npcid']['value'] for r in monsters['monsters']}
    result = {}
    for row in document['monsters']:
        template, npc_id = row['template_id']['value'], row['l1j_npcid']['value']
        if template in result or known.get(template) != npc_id:
            raise ValueError('alignment NPC mapping differs from monsters.json')
        cell = row['lawful']
        if cell['source'] != 'l1j' or not cell['ref'] or row['randomlawful']['value'] != 0:
            raise ValueError('explicit fixed L1J lawful source required')
        result[template] = AlignmentNpc(template, npc_id, _integer(cell['value']),
                                         Source('l1j', cell['ref'], cell.get('note', '')))
    # Monsters without a fixed L1J lawful source (e.g. randomlawful rows) are
    # simply absent: the alignment feature leaves the kill's lawful unchanged.
    if not set(result) <= set(known):
        raise ValueError('alignment catalog has templates outside current M1 monsters')
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class AlignmentChange:
    old_lawful: int
    delta: int
    new_lawful: int
    shared_npc_lawful: int
    requested_delta: int


def kill_change(lawful: int, npc_lawful: int, *, hate: int = 1, total_hate: int = 1,
                rate: float = 1.0, chaotic_rate: float = 1.0,
                pc_dead: bool = False) -> AlignmentChange:
    """Calculate one direct player's share; caller owns actual kill eligibility."""
    lawful = _lawful(lawful)
    _integer(npc_lawful)
    if _integer(total_hate) <= 0 or not 0 <= _integer(hate) <= total_hate:
        raise ValueError('positive total hate and valid player share required')
    for value in (rate, chaotic_rate):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 32767:
            raise ValueError('L1J lawful rates must be finite in 0..32767')
    share = java_div(npc_lawful * hate, total_hate)
    requested = 0 if pc_dead else -int(share * rate)
    if lawful < 0 and not pc_dead:
        requested = int(requested * chaotic_rate)
    new_lawful = clamp_lawful(lawful + requested)
    return AlignmentChange(lawful, new_lawful - lawful, new_lawful, share, requested)


def on_kill(lawful: int, monster_def: MonsterDef, *, catalog: Mapping[int, AlignmentNpc],
            hate: int = 1, total_hate: int = 1, rate: float = 1.0,
            chaotic_rate: float = 1.0, pc_dead: bool = False) -> AlignmentChange:
    """Table-backed kill calculation. Mandatory catalog prevents per-kill I/O."""
    npc = catalog[monster_def.template_id]
    if npc.l1j_npcid != monster_def.l1j_npcid:
        raise ValueError('monster and lawful table NPC IDs differ')
    return kill_change(lawful, npc.lawful, hate=hate, total_hate=total_hate,
                       rate=rate, chaotic_rate=chaotic_rate, pc_dead=pc_dead)


def display_stage(lawful: int) -> str:
    """run395 B41AD0/1D04A8: Classic stat stage/color, 500 inclusive neutral.

    The signed numeric domain is unchanged; no evidence supports a +500 wire
    offset to L1J arithmetic. This does not claim every world name-color path.
    """
    lawful = _lawful(lawful)
    return 'chaotic' if lawful < 0 else 'neutral' if lawful <= 500 else 'lawful'


def death_drop_chance(lawful: int) -> int:
    """Initial death item-loss roll probability, integer numerator out of 1000."""
    lawful = _lawful(lawful)
    signed_rate = int(((lawful + 32768.0) / 1000.0 - 65.0) * 4.0)
    return -signed_rate * (2 if lawful < 0 else 1) if signed_rate < 0 else 0


def death_drop_max_attempts(lawful: int) -> int:
    lawful = _lawful(lawful)
    return 4 if lawful <= -30000 else 3 if lawful <= -20000 else 2 if lawful <= -10000 else 1


@dataclass(frozen=True, slots=True)
class DeathItem:
    uid: int
    template_id: int
    count: int
    stackable: bool
    tradable: bool
    active_pet_amulet: bool = False


@dataclass(frozen=True, slots=True)
class DeathDrop:
    item: DeathItem
    quantity: int


@dataclass(frozen=True, slots=True)
class DeathPenalty:
    chance_per_mille: int
    attempts: int
    drops: tuple[DeathDrop, ...]


def roll_death_penalty(lawful: int, items: Sequence[DeathItem], rng: RandomSource, *,
                       penalty_applies: bool, adena_template_id: int = 7) -> DeathPenalty:
    """Return loss proposals only, preserving inventory order and protected rolls.

    Requires caller's completed death-context decision, not a map/zone guess.
    Adena uses existing Classic7 <-> L1J40308 mapping (MAPPING_SCOPE.md section1).
    """
    chance = death_drop_chance(lawful)
    if not penalty_applies or chance == 0:
        return DeathPenalty(0, 0, ())
    remaining = []
    for item in items:
        if _integer(item.count) <= 0:
            raise ValueError('death inventory must contain positive-count entries')
        remaining.append([item, item.count])
    if rng.randint(1, DEATH_CHANCE_DENOMINATOR) > chance:
        return DeathPenalty(chance, 0, ())
    maximum = death_drop_max_attempts(lawful)
    # L1J also draws nextInt(1)+1 for negative lawful -9999..-1.
    attempts = rng.randint(1, maximum) if lawful < 0 else 1
    drops = []
    for _ in range(attempts):
        if not remaining:
            break
        index = rng.randint(0, len(remaining) - 1)
        item, count = remaining[index]
        if item.template_id == adena_template_id or not item.tradable or item.active_pet_amulet:
            continue
        quantity = count if item.stackable else 1
        drops.append(DeathDrop(item, quantity))
        if quantity == count:
            remaining.pop(index)
        else:
            remaining[index][1] -= quantity
    return DeathPenalty(chance, attempts, tuple(drops))


def healing_multiplier(caster_lawful: int) -> float:
    return 1.0 + max(_lawful(caster_lawful), 0) / 32768.0


def healing_amount(base_heal: int, caster_lawful: int, *, leverage: int = 10) -> int:
    """Apply only L1Magic.calcHealing's alignment/leverage steps to a rolled heal."""
    if _integer(base_heal) < 0 or _integer(leverage) < 0:
        raise ValueError('nonnegative rolled heal and leverage required')
    aligned = int(base_heal * healing_multiplier(caster_lawful))
    return java_div(aligned * leverage, 10)
