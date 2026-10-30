"""Pure quest calculations for explicit snapshots; no inventory, Store or wire IO.

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
from types import MappingProxyType


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
    result_stem: str | None = None
    experience_reward: int = 0  # Explicit LOCAL policy; never inferred from UI fields.
    completed_reference_step: tuple[str, int] | None = None
    settlement_prices: tuple[ItemAmount, ...] = ()  # item_id -> per-item ADENA
    renewable: bool = False
    required_quests: tuple[str, ...] = ()
    issued_items: tuple[ItemAmount, ...] = ()
    recipient_key: str | None = None
    # One completion marker owns all alternatives; keys are native numeric AL.
    choice_rewards: tuple[tuple[int, tuple[ItemAmount, ...]], ...] = ()
    # Attributed LOCAL class-step transitions. The adapter commits acceptance
    # together with the first value; a later NPC can require a different step.
    accepted_reference_step: tuple[str, int] | None = None
    required_completion_step: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class QuestState:
    quest_id: str
    accepted: bool = False
    completed: bool = False
    counts: tuple[int, ...] = ()
    seen_events: tuple[str, ...] = ()
    cycles: int = 0
    issued: tuple[tuple[int, int, int], ...] = ()  # actual (UID, template, quantity)
    closed: bool = False


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
        if objective.kind not in ('collect', 'deliver', 'kill', 'talk'):
            raise ValueError('unsupported objective kind')
        if objective.count is not None and _quantity(objective.count, 'required') == 0:
            raise ValueError('required must be positive')
    return state.counts or (0,) * len(definition.objectives)


def _prerequisite_reason(definition, completed_quests):
    if definition.required_quests and completed_quests is None:
        return 'prerequisite_state_required'
    if any(name not in completed_quests for name in definition.required_quests):
        return 'prerequisite_missing'
    return None


def _reference_reason(definition: QuestDef, reference_steps: Mapping[str, int] | None,
                      *, completing=False) -> str | None:
    requirement = (definition.required_completion_step if completing
                   and definition.required_completion_step is not None
                   else definition.required_reference_step)
    if requirement is None:
        return None
    name, required = requirement
    if reference_steps is None or name not in reference_steps:
        return 'reference_state_required'
    actual = _quantity(reference_steps[name], 'reference quest step')
    return None if actual == required else 'reference_step_mismatch'


def accept_quest(definition: QuestDef, state: QuestState, *,
                 class_key: str, level: int,
                 reference_steps: Mapping[str, int] | None = None,
                 completed_quests: frozenset[str] | None = None) -> QuestResult:
    """Propose one acceptance; eligibility here is the attributed LOCAL policy."""
    counts = _check(definition, state)
    _quantity(level, 'level')
    if state.completed and not definition.renewable:
        return QuestResult(state, 'already_completed')
    if state.accepted and not state.completed:
        return QuestResult(state, 'already_accepted')
    if class_key not in definition.class_keys or level < definition.min_level:
        return QuestResult(state, 'ineligible')
    reason = _reference_reason(definition, reference_steps)
    if reason:
        return QuestResult(state, reason)
    reason = _prerequisite_reason(definition, completed_quests)
    if reason:
        return QuestResult(state, reason)
    return QuestResult(replace(state, accepted=True, completed=False,
        counts=(0,) * len(definition.objectives), seen_events=(), issued=(), closed=False),
        'accepted', rewards=definition.issued_items)


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
    if tuple(counts) == _check(definition, state):
        return QuestResult(state, 'requirements_already_met')
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
        elif objective.kind in ('collect', 'deliver'):
            if type(objective.key) is not int:
                raise ValueError('collection template must be an integer')
            material_totals[objective.key] = material_totals.get(objective.key, 0) + objective.count
            counts.append(min(inventory.get(objective.key, 0), objective.count))
        else:
            counts.append(min(stored[index], objective.count))
    if definition.settlement_prices:
        prices = {item.item_id: item.count for item in definition.settlement_prices}
        unresolved = any(key is None or value is None for key, value in prices.items())
        met = (state.accepted and not state.completed and not unresolved
               and any(inventory.get(key, 0) > 0 for key in prices))
        return QuestProgress(tuple(inventory.get(o.key, 0) for o in definition.objectives),
                             tuple(None for _ in definition.objectives), met, unresolved)
    met = (state.accepted and not state.completed and not unresolved
           and all(count == objective.count for count, objective in zip(counts, definition.objectives))
           and all(inventory.get(key, 0) >= total for key, total in material_totals.items()))
    return QuestProgress(tuple(counts), tuple(o.count for o in definition.objectives), met, unresolved)


def complete_quest(definition: QuestDef, state: QuestState,
                   inventory: Mapping[int, int], *, npc_key: str, action: str,
                   policy: str = 'classic',
                   reference_steps: Mapping[str, int] | None = None,
                   completed_quests: frozenset[str] | None = None,
                   completion_choice: int | None = None) -> QuestResult:
    """Propose turn-in; never consume/award partial or unresolved definitions."""
    progress = evaluate_quest(definition, state, inventory)
    if state.completed:
        return QuestResult(state, 'already_completed')
    if not state.accepted:
        return QuestResult(state, 'not_accepted')
    if npc_key != (definition.recipient_key or definition.npc_key) or not definition.completion_action or action != definition.completion_action:
        return QuestResult(state, 'wrong_turn_in')
    reason = _reference_reason(definition, reference_steps, completing=True)
    if reason:
        return QuestResult(state, reason)
    reason = _prerequisite_reason(definition, completed_quests)
    if reason:
        return QuestResult(state, reason)
    rewards = definition.rewards
    if definition.choice_rewards:
        choices = dict(definition.choice_rewards)
        if type(completion_choice) is not int or completion_choice not in choices:
            return QuestResult(state, 'reward_choice_required')
        rewards = choices[completion_choice]
    if not progress.conditions_met:
        return QuestResult(state, 'unresolved' if progress.unresolved else 'requirements_missing')
    if policy != 'l1j_local' or definition.calculation_policy != 'l1j_local':
        return QuestResult(state, 'policy_unselected')
    if definition.settlement_prices:
        consumed = tuple(ItemAmount(price.item_id, inventory.get(price.item_id, 0))
                         for price in definition.settlement_prices if inventory.get(price.item_id, 0))
        total = sum(item.count * price.count for item, price in
                    ((item, next(p for p in definition.settlement_prices if p.item_id == item.item_id))
                     for item in consumed))
        if not 0 < total <= 2_000_000_000:
            return QuestResult(state, 'settlement_amount_invalid')
        return QuestResult(replace(state, completed=True, counts=progress.counts,
                                  cycles=state.cycles + 1), 'completion_proposed',
                           consumed, (ItemAmount(7, total),), policy)
    if any(r.item_id is None or r.count is None for r in rewards):
        return QuestResult(state, 'unresolved_reward')
    for reward in rewards:
        _quantity(reward.item_id, 'reward template')
        if _quantity(reward.count, 'reward count') == 0:
            raise ValueError('reward count must be positive')
    consumed: dict[int, int] = {}
    for objective in definition.objectives:
        if objective.kind in ('collect', 'deliver'):
            consumed[objective.key] = consumed.get(objective.key, 0) + objective.count
    _quantity(definition.experience_reward, 'experience reward')
    return QuestResult(replace(state, completed=True, counts=progress.counts,
                              cycles=state.cycles + 1), 'completion_proposed',
                       tuple(ItemAmount(key, count) for key, count in consumed.items()),
                       rewards, policy)


def load_quests(path: Path | str | None = None) -> tuple[QuestDef, ...]:
    """Explicit startup read; event and calculation functions perform no IO."""
    source = Path(path) if path is not None else Path(__file__).parent / 'data' / 'm2' / 'quests.json'
    rows = json.loads(source.read_text(encoding='utf-8'))['quests']
    return tuple(QuestDef(row['quest_id'], row['name_ko'], row['npc_key'],
                         tuple(row['eligibility']['class_keys']), row['eligibility']['min_level'],
                         tuple(Objective(o['kind'], o.get('key', o.get('classic_item_id')), o['count']) for o in row['objectives']),
                         tuple(ItemAmount(r['classic_item_id'], r['count']) for r in row['rewards']),
                         row['classic']['completion_action'], row['calculation_policy'],
                         row['reference_repeatable'],
                         ((row['l1j']['quest_id'], row['l1j']['quest_step'])
                          if row['l1j'].get('quest_id') is not None else None),
                         row['classic']['result_stem'], row.get('experience_reward', {}).get('amount', 0),
                         ((row['l1j']['quest_id'], 255 if row['l1j']['after_step'] == 'End'
                           else row['l1j']['after_step'])
                          if row['l1j'].get('after_step') is not None else None),
                         tuple(ItemAmount(int(key), value) for key, value in row.get('settlement_prices', {}).items()),
                         row.get('renewable', False), tuple(row.get('required_quests', ())),
                         tuple(ItemAmount(r['classic_item_id'], r['count']) for r in row.get('issued_items', ())),
                         row.get('recipient_key'),
                         tuple((int(key), tuple(ItemAmount(r['classic_item_id'], r['count']) for r in values))
                               for key, values in row.get('choice_rewards', {}).items()),
                         ((row['l1j']['quest_id'], row['l1j']['accepted_step'])
                          if row['l1j'].get('accepted_step') is not None else None),
                         ((row['l1j']['quest_id'], row['l1j']['completion_step'])
                          if row['l1j'].get('completion_step') is not None else None)) for row in rows)


def load_reward_items(path: Path | str | None = None):
    """Startup-only LOCAL plain-kit prototypes with source-backed native icons.

    The 17 raw fields are the existing kit producer, not reconstructed native
    quest flags. Template/icon and nonstackability have separate cited sources.
    """
    from tools.local_original_session import inventory
    from tools.local_original_session.world_handlers import _starter_fields
    source = Path(path) if path is not None else Path(__file__).parent / 'data' / 'm2' / 'quests.json'
    rows = json.loads(source.read_text(encoding='utf-8'))['inventory_rewards']
    result = {}
    for template, row in rows.items():
        template = int(template)
        _quantity(template, 'reward template')
        _quantity(row['icon'], 'reward icon')
        if type(row['stackable']) is not bool:
            raise ValueError('reward stackability must be explicit')
        fields = _starter_fields()
        fields.update({2: template, 7: row['icon']})
        inventory.validate_kit_frame(inventory.build_kit_frame([fields]))
        result[template] = (MappingProxyType(fields), row['stackable'])
    return MappingProxyType(result)


def load_runtime(path: Path | str | None = None):
    source = Path(path) if path is not None else Path(__file__).parent / 'data' / 'm2' / 'quests.json'
    return json.loads(source.read_text(encoding='utf-8')).get('quest_runtime', {})


def load_inventory_policies(path: Path | str | None = None):
    """Keep quest materials/rewards usable by the existing kit shop snapshot.

    Native f5/f10 supply icon/raw weight; the cited L1J item kinds supply the
    LOCAL nonstackable policy. This grants no new shop offer or resale price.
    """
    from tools.local_original_session.world_handlers import KitItemPolicy, _starter_fields
    source = Path(path) if path is not None else Path(__file__).parent / 'data' / 'm2' / 'quests.json'
    document = json.loads(source.read_text(encoding='utf-8'))
    rows = {**document['inventory_rewards'], **document['inventory_materials']}
    policies = []
    for template, row in rows.items():
        template = int(template)
        fields = _starter_fields()
        fields.update({2: template, 7: row['icon']})
        policies.append(KitItemPolicy(template, row['raw_weight'], row['stackable'], fields))
    return tuple(policies)


@dataclass(frozen=True, slots=True)
class QuestDialogue:
    npc_id: int  # L1J definition identity, never a live UID or Classic template.
    initial: str
    pages: Mapping[str, tuple[str, ...]]
    starts: Mapping[str, tuple[str, str]]  # accept stem -> (quest_id, objective stem)
    completions: Mapping[str, str]  # objective stem -> quest_id


def load_quest_dialogues(path: Path | str | None = None) -> tuple[QuestDialogue, ...]:
    """Startup-only run403 resource selection; official menu predicates UNKNOWN.

    Gunter's p1 is a Zero introduction, not a start of secret_of_life. No start
    mapping is supplied for it. Cookies are not quest identities: questcomplete
    uses DF660's decimal strtol result AL as one byte. Only Oth's source-backed
    0/1 links currently assign a reward-selection meaning to that byte.
    """
    source = Path(path) if path is not None else Path(__file__).parent / 'data' / 'm2' / 'quests.json'
    rows = json.loads(source.read_text(encoding='utf-8'))['native_dialogues']
    return tuple(QuestDialogue(row['l1j_npc_id'], row['initial'],
        MappingProxyType({stem: tuple(actions) for stem, actions in row['pages'].items()}),
        MappingProxyType({stem: tuple(value) for stem, value in row['starts'].items()}),
        MappingProxyType(dict(row['completions']))) for row in rows)
