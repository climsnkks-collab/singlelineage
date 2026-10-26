"""Pure quest previews for explicit snapshots; no inventory, Store or wire IO.

Load definitions once with load_quests(). The adapter seam is::

    accept_quest(definition, state, *, class_key, level,
                 reference_steps=None) -> QuestResult
    on_event(definition, state, event, inventory) -> QuestResult
    complete_quest(definition, state, inventory, *, npc_key, action,
                   policy='classic', reference_steps=None) -> QuestResult

Inventory maps Classic template IDs to available UNEQUIPPED quantities. Its
owner must exclude locked/traded items and select actual owned UID stacks.
Events must come from the caller's real committed kill/dialogue path. event_id
only deduplicates the supplied snapshot, and is not a receipt or kill authority.
npc_key is a definition identity (e.g. l1j:70531), NEVER a live NPC UID.

A completion returns a proposed completed state plus consumption/reward DATA.
The caller must apply all three atomically through existing inventory, quest
participant and persistence owners, then publish responses. On failure retain
the prior state; do not save this proposed state before committing inventory.
Concurrent calls against the same preimage can propose the same reward: the
existing owner's CAS/transaction and once marker remain necessary. This module
does not implement that adapter or alter EXPLICIT_LOCAL_SHOP_QUEST_PARTICIPANT
V1/V2 (count/rewarded/cursor), whose genuine issuer authority is separate.

The bundled material quantities/rewards are attributed L1J LOCAL candidates.
Default 'classic' mode never emits their reward/consumption proposals. Only an
explicit policy='l1j_local' selection enables that calculation, still without
granting any application authority or claiming original server equivalence.
reference_steps maps L1J quest names to the current PC's class-scoped steps;
it must come from the caller's actual quest snapshot. A required missing or
changed shared step blocks acceptance/turn-in. Completion does not propose a
new shared step: the caller still owns the full class-quest transition.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ItemAmount:
    item_id: int | None
    count: int | None


@dataclass(frozen=True, slots=True)
class Objective:
    kind: str
    key: int | str | None
    count: int | None


@dataclass(frozen=True, slots=True)
class QuestDef:
    quest_id: str
    name: str
    npc_key: str
    class_keys: tuple[str, ...]
    min_level: int
    objectives: tuple[Objective, ...]
    rewards: tuple[ItemAmount, ...]
    completion_action: str | None
    calculation_policy: str
    # Repeatability in the reference is separate from this one-acceptance state.
    reference_repeatable: bool | None = None
    required_reference_step: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class QuestState:
    quest_id: str
    accepted: bool = False
    completed: bool = False
    counts: tuple[int, ...] = ()
    seen_events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestEvent:
    kind: str  # kill or talk; collection always uses the current inventory
    key: int | str
    event_id: str


@dataclass(frozen=True, slots=True)
class QuestProgress:
    counts: tuple[int, ...]
    required: tuple[int | None, ...]
    conditions_met: bool
    unresolved: bool


@dataclass(frozen=True, slots=True)
class QuestResult:
    state: QuestState
    reason: str
    consumed: tuple[ItemAmount, ...] = ()
    rewards: tuple[ItemAmount, ...] = ()
    policy: str | None = None


def _quantity(value: int, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    return value


def _check(definition: QuestDef, state: QuestState) -> tuple[int, ...]:
    if state.quest_id != definition.quest_id:
        raise ValueError('quest identity mismatch')
    if state.completed and not state.accepted:
        raise ValueError('completed state must have been accepted')
    if state.counts and len(state.counts) != len(definition.objectives):
        raise ValueError('objective count mismatch')
    for value in state.counts:
        _quantity(value, 'objective progress')
    for objective in definition.objectives:
        if objective.kind not in ('collect', 'kill', 'talk'):
            raise ValueError('unsupported objective kind')
        if objective.count is not None and _quantity(objective.count, 'required') == 0:
            raise ValueError('required must be positive')
    return state.counts or (0,) * len(definition.objectives)


def _reference_reason(definition: QuestDef, reference_steps: Mapping[str, int] | None) -> str | None:
    if definition.required_reference_step is None:
        return None
    name, required = definition.required_reference_step
    if reference_steps is None or name not in reference_steps:
        return 'reference_state_required'
    actual = _quantity(reference_steps[name], 'reference quest step')
    return None if actual == required else 'reference_step_mismatch'


def accept_quest(definition: QuestDef, state: QuestState, *,
                 class_key: str, level: int,
                 reference_steps: Mapping[str, int] | None = None) -> QuestResult:
    """Propose one acceptance; eligibility here is the attributed LOCAL policy."""
    counts = _check(definition, state)
    _quantity(level, 'level')
    if state.completed:
        return QuestResult(state, 'already_completed')
    if state.accepted:
        return QuestResult(state, 'already_accepted')
    if class_key not in definition.class_keys or level < definition.min_level:
        return QuestResult(state, 'ineligible')
    reason = _reference_reason(definition, reference_steps)
    if reason:
        return QuestResult(state, reason)
    return QuestResult(replace(state, accepted=True, counts=counts), 'accepted')


def on_event(definition: QuestDef, state: QuestState, event: QuestEvent,
             inventory: Mapping[int, int]) -> QuestResult:
    """Count a matching committed event once. No pickup event grants items."""
    counts = list(_check(definition, state))
    evaluate_quest(definition, state, inventory)
    if not state.accepted or state.completed:
        return QuestResult(state, 'inactive')
    if not isinstance(event.event_id, str) or not event.event_id:
        raise ValueError('event_id must be nonempty')
    if event.kind not in ('kill', 'talk'):
        raise ValueError('unsupported event kind; collection uses inventory')
    if event.event_id in state.seen_events:
        return QuestResult(state, 'duplicate_event')
    matched = False
    for index, objective in enumerate(definition.objectives):
        if (objective.kind == event.kind and objective.key == event.key
                and objective.key is not None and objective.count is not None):
            counts[index] = min(counts[index] + 1, objective.count)
            matched = True
    if not matched:
        return QuestResult(state, 'unrelated_event')
    return QuestResult(replace(state, counts=tuple(counts),
                               seen_events=state.seen_events + (event.event_id,)),
                       'progressed')


def evaluate_quest(definition: QuestDef, state: QuestState,
                   inventory: Mapping[int, int]) -> QuestProgress:
    """Current possession, not historical pickups, satisfies collection goals."""
    stored = _check(definition, state)
    for item_id, quantity in inventory.items():
        _quantity(item_id, 'inventory template')
        _quantity(quantity, 'inventory quantity')
    counts = []
    unresolved = not definition.objectives
    material_totals: dict[int, int] = {}
    for index, objective in enumerate(definition.objectives):
        if objective.key is None or objective.count is None:
            unresolved = True
            counts.append(0)
        elif objective.kind == 'collect':
            if type(objective.key) is not int:
                raise ValueError('collection template must be an integer')
            material_totals[objective.key] = material_totals.get(objective.key, 0) + objective.count
            counts.append(min(inventory.get(objective.key, 0), objective.count))
        else:
            counts.append(min(stored[index], objective.count))
    met = (state.accepted and not state.completed and not unresolved
           and all(count == objective.count for count, objective in zip(counts, definition.objectives))
           and all(inventory.get(key, 0) >= total for key, total in material_totals.items()))
    return QuestProgress(tuple(counts), tuple(o.count for o in definition.objectives), met, unresolved)


def complete_quest(definition: QuestDef, state: QuestState,
                   inventory: Mapping[int, int], *, npc_key: str, action: str,
                   policy: str = 'classic',
                   reference_steps: Mapping[str, int] | None = None) -> QuestResult:
    """Propose turn-in; never consume/award partial or unresolved definitions."""
    progress = evaluate_quest(definition, state, inventory)
    if state.completed:
        return QuestResult(state, 'already_completed')
    if not state.accepted:
        return QuestResult(state, 'not_accepted')
    if npc_key != definition.npc_key or not definition.completion_action or action != definition.completion_action:
        return QuestResult(state, 'wrong_turn_in')
    reason = _reference_reason(definition, reference_steps)
    if reason:
        return QuestResult(state, reason)
    if not progress.conditions_met:
        return QuestResult(state, 'unresolved' if progress.unresolved else 'requirements_missing')
    if policy != 'l1j_local' or definition.calculation_policy != 'l1j_local':
        return QuestResult(state, 'policy_unselected')
    if any(r.item_id is None or r.count is None for r in definition.rewards):
        return QuestResult(state, 'unresolved_reward')
    for reward in definition.rewards:
        _quantity(reward.item_id, 'reward template')
        if _quantity(reward.count, 'reward count') == 0:
            raise ValueError('reward count must be positive')
    consumed: dict[int, int] = {}
    for objective in definition.objectives:
        if objective.kind == 'collect':
            consumed[objective.key] = consumed.get(objective.key, 0) + objective.count
    return QuestResult(replace(state, completed=True), 'completion_proposed',
                       tuple(ItemAmount(key, count) for key, count in consumed.items()),
                       definition.rewards, policy)


def load_quests(path: Path | str | None = None) -> tuple[QuestDef, ...]:
    """Explicit startup read; event and calculation functions perform no IO."""
    source = Path(path) if path is not None else Path(__file__).parent / 'data' / 'm2' / 'quests.json'
    rows = json.loads(source.read_text(encoding='utf-8'))['quests']
    return tuple(QuestDef(row['quest_id'], row['name_ko'], row['npc_key'],
                         tuple(row['eligibility']['class_keys']), row['eligibility']['min_level'],
                         tuple(Objective(o['kind'], o['classic_item_id'], o['count']) for o in row['objectives']),
                         tuple(ItemAmount(r['classic_item_id'], r['count']) for r in row['rewards']),
                         row['classic']['completion_action'], row['calculation_policy'],
                         row['reference_repeatable'],
                         ((row['l1j']['quest_id'], row['l1j']['quest_step'])
                          if row['l1j'].get('quest_id') is not None else None)) for row in rows)
