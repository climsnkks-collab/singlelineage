"""Pure pet proposals, with L1J backend rules separated from Classic identity.

Future caller contract (no inventory/entity/save/packet writes happen here)::

    catalog = load_pets()  # explicit startup read, never on a request path
    proposal = offer_food(catalog, owner, target, food, quantity=1,
                          tiger_roll=actual_rng.randrange(16))
    pet = create_tamed_pet(catalog, proposal, pet_id=durable_id,
                           collar_uid=issued_item_uid, actor_ref=issued_ref)
    result = command_pet(pet, owner, PetCommand.DEFEND)
    intent = ai_intent(result.state, owner_ref=actual_owner_ref)
    growth = award_pet_exp(catalog, pet, allocated_exp=share,
                           growth_rolls=((actual_hp_roll, actual_mp_roll),))
    payload = collar_payload(catalog, pet)
    pet = restore_collar(catalog, payload, owner_uid=actual_owner_uid,
                         collar_uid=actual_owned_collar_uid)
    pet = activate_pet(pet, actor_ref=actual_new_ref)

``offer_food`` proposes a giver->target transfer BEFORE taming, just as
C_GiveItem.java:154,175,180-187 does. transfer_count is loss from the giver,
NOT destruction, a debit receipt, or evidence that onGetItem consumed food.
A valid transfer remains proposed on taming failure (wrong food, insufficient
CHA, HP, capacity, already-owned target, resurrection or failed tiger roll).
The caller supplies inventory_slots_after_transfer, since giving the final
stack can free a collar slot. Quantity does not multiply taming attempts.
Malformed/unauthorized offers do not propose transfer. This API models the
reviewed four item definitions, not arbitrary give-item trading.

Caller must resolve actual live generations/selection, map/range, ownership,
online/living owner, NPC item-receivability, tradability/equipment, inventory
capacity and onGetItem side effects under its existing world/inventory lock.
Commit transfer, collar issue, wild->pet replacement, pet/collar save, and
publication together through existing transaction owners. A successful pure
proposal is not authority, is not single-use, and cannot allocate real IDs.
``pet_id`` is durable pet identity, ``collar_uid`` an owned inventory instance,
``actor_ref`` a live world UID+generation; none is a template ID. The actual
collar template candidate is Classic361/L1J40314, not the collar instance UID.
No original inventory schema is extended here. Restoring returns STORED with
no actor/target; caller must prevent duplicate live adoption by collar/pet ID.
Dismiss means L1J liberate: release a wild replacement, remove collar and pet
record atomically. This module only proposes those effects, with no undo.

Modes are backend intent, never wire enums. Attack/defend/stay use L1J1/2/3;
follow is explicit LOCAL continuous following with no target acquisition.
L1J7 is instead one-shot come->stay. Classic4F02 producer enum2/3/4/5/7 and
4F14 display values are a different namespace; follow/dismiss wire mapping
remains UNKNOWN (implementation-companion/companion-4f14-response-source-v1/
HANDOFF.md:8-22). Switching mode clears old targets as explicit LOCAL policy.
ai_intent reuses npc_ai.State/EntityRef as adapter input only; NpcAi currently
does not control pets, and this module adds no AI loop, pathing or cadence.

All numbers/formulas and candidate IDs are sourced in data/m1/pets.json.
14 base pettypes, HP<floor(maxHP/3), CHA residual>=6, slots<180 and Tiger1/16
come from read-only D:/SingleLineageRef/l1j-en-classic. Species candidates are
token/name/f2 matches, not proof of Classic tameability; duplicates survive.
Food9 is a name/type/field6=3176 candidate for L1J40057 (changed name token),
and is separate from ordinary meat10/L1J40056. Tiger and Jindo have no proven
Classic template candidate. Backend-only snapshots may explicitly use None;
they cannot activate a real pet. No packet/client/server integration or formal
gameplay PASS is supplied. Existing companion functionality is not resumed.

Growth accepts an ALREADY allocated integer share; kill-once and the approved
50:50 half-unit ledger belong to the existing reward/transaction owner. Rate
defaults to1; integer rational scaling matches positive Java truncation without
floating-point drift. Growth draws are caller-provided inclusive HP/MP pairs,
one per level. Full HP/MP refill occurs on level gain. LOCAL cap is MAX_EXP,
with excess reported. LOCAL collar JSON preserves current HP/MP and mode;
L1J restore instead refills and resets stay. Active refs/targets never persist.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from enum import Enum
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from tools.local_original_session.npc_ai import State
from tools.local_original_session.world_entities import EntityRef

DEFAULT_PATH = Path(__file__).resolve().parent / 'data' / 'm1' / 'pets.json'


class PetCommand(str, Enum):
    ATTACK = 'attack'
    DEFEND = 'defend'
    STAY = 'stay'
    FOLLOW = 'follow'
    DISMISS = 'dismiss'


class PetLife(str, Enum):
    STORED = 'stored'
    ACTIVE = 'active'
    RELEASED = 'released'


@dataclass(frozen=True, slots=True)
class PetSpecies:
    key: str
    l1j_npc_id: int
    name: str
    classic_candidates: tuple[int, ...]
    food_l1j_item_id: int
    hp_growth: tuple[int, int]
    mp_growth: tuple[int, int]
    initial_level: int
    initial_exp: int
    pet_cost: int
    forbid_resurrected: bool
    tiger_roll_denominator: int | None


@dataclass(frozen=True, slots=True)
class PetItem:
    key: str
    l1j_item_id: int
    classic_candidates: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class PetCatalog:
    species: Mapping[str, PetSpecies]
    items: Mapping[int, PetItem]
    class_bonus: Mapping[str, int]
    cumulative_exp: tuple[int, ...]
    max_level: int
    max_exp: int


def load_pets(path: Path | str = DEFAULT_PATH) -> PetCatalog:
    """Read definitions once at startup. Imports/calculations perform no IO."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    species = {}
    for row in raw['species']:
        p = row['backend_policy']
        species[row['key']] = PetSpecies(
            row['key'], row['l1j_npc_id'], row['l1j_name'],
            tuple(c['template_id'] for c in row['classic_mapping']['candidates']),
            p['food_l1j_item_id'], tuple(p['hp_growth_inclusive']),
            tuple(p['mp_growth_inclusive']), p['initial_template_level'],
            p['initial_exp'], p['pet_cost'], p['forbid_resurrected'],
            p['tiger_roll_denominator'])
    items = {r['l1j_item_id']: PetItem(
        r['key'], r['l1j_item_id'],
        tuple(c['template_id'] for c in r['classic_mapping']['candidates']))
        for r in raw['items']}
    exp = raw['experience']
    return PetCatalog(MappingProxyType(species), MappingProxyType(items),
                      MappingProxyType(raw['rules']['taming']['class_bonus']),
                      tuple(exp['cumulative']), exp['max_level'], exp['max_exp'])


def _integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')


def _ref(ref: EntityRef) -> None:
    if not isinstance(ref, EntityRef):
        raise ValueError('EntityRef required')
    _integer(ref.uid, 'actor UID', 1)
    _integer(ref.generation, 'actor generation')


@dataclass(frozen=True, slots=True)
class PetOwner:
    uid: int
    level: int
    charisma: int
    class_key: str
    used_pet_cost: int = 0
    inventory_slots_after_transfer: int = 0


@dataclass(frozen=True, slots=True)
class TameTarget:
    ref: EntityRef
    species_key: str
    classic_template_id: int | None
    hp: int
    max_hp: int
    mp: int = 0
    max_mp: int = 0
    master_uid: int | None = None
    is_summon: bool = False
    resurrected: bool = False


@dataclass(frozen=True, slots=True)
class FoodOffer:
    owner_uid: int
    item_uid: int
    l1j_item_id: int
    classic_template_id: int | None
    count: int


@dataclass(frozen=True, slots=True)
class TameResult:
    owner: PetOwner
    target: TameTarget
    food: FoodOffer
    tamed: bool
    reason: str
    transfer_count: int = 0


def offer_food(catalog: PetCatalog, owner: PetOwner, target: TameTarget,
               food: FoodOffer, *, quantity: int = 1,
               tiger_roll: int | None = None) -> TameResult:
    """One backend attempt after a proposed food transfer; no actual debit.

    Explicit l1j_item_id/species_key select reviewed backend policy. Provided
    Classic IDs must match listed candidates; None means backend calculation
    only, never permission for an unresolved actual packet/item translation.
    Caller supplies actual post-onGetItem target HP and target/collar capacity.
    A tiger roll is needed only after all deterministic admission checks pass.
    """
    _integer(owner.uid, 'owner UID', 1)
    _integer(owner.level, 'owner level', 1)
    _integer(owner.charisma, 'charisma')
    _integer(owner.used_pet_cost, 'used pet cost')
    _integer(owner.inventory_slots_after_transfer, 'inventory slots')
    _ref(target.ref)
    _integer(target.max_hp, 'max HP', 1)
    _integer(target.hp, 'HP')
    _integer(target.max_mp, 'max MP')
    _integer(target.mp, 'MP')
    if target.hp > target.max_hp or target.mp > target.max_mp:
        raise ValueError('target resources exceed maxima')
    _integer(food.item_uid, 'food item UID', 1)
    _integer(food.count, 'food count')
    _integer(quantity, 'quantity', 1)
    def result(reason: str, transferred: int = 0, tamed: bool = False):
        return TameResult(owner, target, food, tamed, reason, transferred)
    if food.owner_uid != owner.uid:
        return result('food_not_owned')
    if quantity > food.count:
        return result('insufficient_food')
    item = catalog.items.get(food.l1j_item_id)
    if item is None or item.key == 'pet_collar':
        return result('unsupported_food')
    if food.classic_template_id is not None and food.classic_template_id not in item.classic_candidates:
        return result('food_mapping_mismatch')
    species = catalog.species.get(target.species_key)
    if species is None:
        return result('unknown_species')
    if target.classic_template_id is not None and target.classic_template_id not in species.classic_candidates:
        return result('species_mapping_mismatch')
    if owner.class_key not in catalog.class_bonus:
        return result('unknown_owner_class')
    # Below this point the source gives food before checking taming eligibility.
    if target.hp == 0:
        return result('target_dead', quantity)
    if target.master_uid is not None or target.is_summon:
        return result('target_already_owned', quantity)
    if food.l1j_item_id != species.food_l1j_item_id:
        return result('wrong_food', quantity)
    if owner.charisma + catalog.class_bonus[owner.class_key] - owner.used_pet_cost < species.pet_cost:
        return result('insufficient_charisma', quantity)
    if owner.inventory_slots_after_transfer >= 180:
        return result('no_collar_slot', quantity)
    if target.hp >= target.max_hp // 3:
        return result('target_hp_too_high', quantity)
    if target.resurrected and species.forbid_resurrected:
        return result('resurrected_target', quantity)
    if species.tiger_roll_denominator is not None:
        if type(tiger_roll) is not int or not 0 <= tiger_roll < species.tiger_roll_denominator:
            raise ValueError('tiger_roll must be an actual integer draw in [0,15]')
        if tiger_roll != 15:
            return result('tiger_roll_failed', quantity)
    return result('tamed', quantity, True)


@dataclass(frozen=True, slots=True)
class PetRecord:
    pet_id: int
    collar_uid: int
    owner_uid: int
    species_key: str
    classic_template_id: int | None
    name: str
    exp: int
    level: int
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    mode: PetCommand = PetCommand.STAY


@dataclass(frozen=True, slots=True)
class PetState:
    record: PetRecord
    life: PetLife = PetLife.STORED
    actor_ref: EntityRef | None = None
    target_ref: EntityRef | None = None

    def __post_init__(self):
        if not isinstance(self.life, PetLife):
            raise ValueError('PetLife required')
        if self.actor_ref is not None:
            _ref(self.actor_ref)
        if self.target_ref is not None:
            _ref(self.target_ref)
        if self.life == PetLife.ACTIVE and self.actor_ref is None:
            raise ValueError('active pet requires actor ref')
        if self.life == PetLife.STORED and self.actor_ref is not None:
            raise ValueError('stored pet cannot retain actor ref')
        if self.life != PetLife.ACTIVE and self.target_ref is not None:
            raise ValueError('inactive pet cannot retain target ref')


def level_by_exp(catalog: PetCatalog, exp: int) -> int:
    _integer(exp, 'EXP')
    if exp > catalog.max_exp:
        raise ValueError('EXP exceeds supported maximum')
    return min(catalog.max_level, bisect_right(catalog.cumulative_exp, exp))


def exp_percent(catalog: PetCatalog, exp: int) -> int:
    level = level_by_exp(catalog, exp)
    low, high = catalog.cumulative_exp[level - 1:level + 1]
    return 100 * (exp - low) // (high - low)


def _record(catalog: PetCatalog, record: PetRecord) -> None:
    for name in ('pet_id', 'collar_uid', 'owner_uid', 'max_hp'):
        _integer(getattr(record, name), name, 1)
    for name in ('hp', 'mp', 'max_mp'):
        _integer(getattr(record, name), name)
    if record.hp > record.max_hp or record.mp > record.max_mp:
        raise ValueError('pet resources exceed maxima')
    species = catalog.species.get(record.species_key)
    if species is None:
        raise ValueError('unknown pet species')
    if record.classic_template_id is not None and record.classic_template_id not in species.classic_candidates:
        raise ValueError('pet Classic mapping mismatch')
    if not isinstance(record.name, str) or not record.name.strip() or len(record.name) > 45:
        raise ValueError('invalid pet name')
    if type(record.level) is not int or record.level != level_by_exp(catalog, record.exp):
        raise ValueError('pet level/EXP inconsistent')
    if not isinstance(record.mode, PetCommand) or record.mode == PetCommand.DISMISS:
        raise ValueError('invalid persistent pet mode')


def create_tamed_pet(catalog: PetCatalog, outcome: TameResult, *, pet_id: int,
                     collar_uid: int, actor_ref: EntityRef) -> PetState:
    """Bind caller-issued identities to a successful proposal, not a receipt.

    Existing target inventory transfers to the pet; caller replaces/retires the
    wild actor and cancels its old scheduler owner. IDs/generations are issued
    by existing owners; never reuse the wild actor ref as the new pet actor.
    """
    if not outcome.tamed:
        raise ValueError('successful tame proposal required')
    if outcome.food.classic_template_id is None:
        raise ValueError('actual Classic food template unresolved')
    target, species = outcome.target, catalog.species[outcome.target.species_key]
    _ref(actor_ref)
    if actor_ref.uid == target.ref.uid:
        raise ValueError('new pet actor UID required')
    record = PetRecord(pet_id, collar_uid, outcome.owner.uid, species.key,
                       target.classic_template_id, species.name,
                       species.initial_exp, species.initial_level,
                       target.hp, target.max_hp, target.mp, target.max_mp)
    _record(catalog, record)
    if record.classic_template_id is None:
        raise ValueError('actual Classic pet template unresolved')
    return PetState(record, PetLife.ACTIVE, actor_ref)


@dataclass(frozen=True, slots=True)
class PetCommandResult:
    state: PetState
    allowed: bool
    reason: str
    remove_collar_count: int = 0
    release_to_wild: bool = False


def command_pet(state: PetState, owner: PetOwner, command: PetCommand | str,
                *, target_ref: EntityRef | None = None) -> PetCommandResult:
    """Propose one owner's command. Caller verifies live refs/attack legality.

    Owner level must cover pet level except for dismissal (L1J onFinalAction).
    Target refs are accepted only for ATTACK; modes clear all prior targets.
    Dismissal retains the old actor ref only as cleanup input, never active AI.
    """
    try:
        command = PetCommand(command)
    except (ValueError, TypeError):
        return PetCommandResult(state, False, 'unknown_command')
    if owner.uid != state.record.owner_uid:
        return PetCommandResult(state, False, 'not_owner')
    if state.life != PetLife.ACTIVE or state.actor_ref is None:
        return PetCommandResult(state, False, 'pet_not_active')
    if state.record.hp == 0:
        return PetCommandResult(state, False, 'pet_dead')
    if command != PetCommand.DISMISS and owner.level < state.record.level:
        return PetCommandResult(state, False, 'owner_level_too_low')
    if target_ref is not None:
        _ref(target_ref)
        if command != PetCommand.ATTACK:
            return PetCommandResult(state, False, 'target_requires_attack')
        if target_ref.uid in (owner.uid, state.actor_ref.uid):
            return PetCommandResult(state, False, 'invalid_attack_target')
    if command == PetCommand.DISMISS:
        released = replace(state, life=PetLife.RELEASED, target_ref=None)
        return PetCommandResult(released, True, 'released', 1, True)
    return PetCommandResult(replace(state, record=replace(state.record, mode=command),
                                    target_ref=target_ref), True, 'commanded')


@dataclass(frozen=True, slots=True)
class PetAiIntent:
    state: State
    target_ref: EntityRef | None
    follow_owner: bool
    accept_master_target: bool
    retaliate: bool


def ai_intent(state: PetState, *, owner_ref: EntityRef,
              master_target: EntityRef | None = None,
              attacker: EntityRef | None = None) -> PetAiIntent:
    """Describe reusable AI inputs only, without registering/running NpcAi.

    RETURN+owner_ref denotes continuous follow intent, not a claim that the
    current monster RETURN(home) implementation can already follow a pet owner.
    Caller resolves all generations, same-map/liveness/legality on every tick.
    """
    _ref(owner_ref)
    if owner_ref.uid != state.record.owner_uid:
        raise ValueError('owner reference mismatch')
    if state.life != PetLife.ACTIVE or state.record.hp == 0:
        return PetAiIntent(State.IDLE, None, False, False, False)
    mode = state.record.mode
    if mode == PetCommand.STAY:
        return PetAiIntent(State.IDLE, None, False, False, False)
    if mode == PetCommand.FOLLOW:
        return PetAiIntent(State.RETURN, owner_ref, True, False, False)
    target = state.target_ref or attacker or (master_target if mode == PetCommand.ATTACK else None)
    if target is not None:
        _ref(target)
        if target.uid in (owner_ref.uid, state.actor_ref.uid):
            raise ValueError('invalid AI attack target')
    return PetAiIntent(State.CHASE if target else State.RETURN,
                       target or owner_ref, True, mode == PetCommand.ATTACK, True)


@dataclass(frozen=True, slots=True)
class PetExpResult:
    state: PetState
    levels_gained: int
    applied_exp: int
    capped_excess: int


def award_pet_exp(catalog: PetCatalog, state: PetState, *, allocated_exp: int,
                  growth_rolls: tuple[tuple[int, int], ...] = (),
                  rate_numerator: int = 1, rate_denominator: int = 1) -> PetExpResult:
    """Pure growth for an already allocated share; no kill/store/UID mutation."""
    _record(catalog, state.record)
    if state.life != PetLife.ACTIVE or state.record.hp == 0:
        raise ValueError('living active pet required for EXP')
    _integer(allocated_exp, 'allocated EXP')
    _integer(rate_numerator, 'EXP rate numerator')
    _integer(rate_denominator, 'EXP rate denominator', 1)
    old = state.record
    requested = allocated_exp * rate_numerator // rate_denominator
    new_exp = min(catalog.max_exp, old.exp + requested)
    new_level = level_by_exp(catalog, new_exp)
    gap = new_level - old.level
    if len(growth_rolls) != gap:
        raise ValueError('one HP/MP growth pair required per gained level')
    species = catalog.species[old.species_key]
    hp, mp = old.max_hp, old.max_mp
    for hp_roll, mp_roll in growth_rolls:
        if (type(hp_roll) is not int or not species.hp_growth[0] <= hp_roll <= species.hp_growth[1]
                or type(mp_roll) is not int or not species.mp_growth[0] <= mp_roll <= species.mp_growth[1]):
            raise ValueError('growth draw outside inclusive species range')
        hp += hp_roll
        mp += mp_roll
    record = replace(old, exp=new_exp, level=new_level, max_hp=hp, max_mp=mp,
                     hp=hp if gap else old.hp, mp=mp if gap else old.mp)
    return PetExpResult(replace(state, record=record), gap, new_exp - old.exp,
                         requested - (new_exp - old.exp))


def collar_payload(catalog: PetCatalog, state: PetState) -> dict:
    """Return a new JSON-compatible LOCAL record; never write a save file.

    Caller persists this with the actual owned collar and pet inventory in its
    existing transaction. Current actor/target/life are deliberately excluded.
    """
    if state.life == PetLife.RELEASED:
        raise ValueError('released pet has no persistent collar record')
    _record(catalog, state.record)
    row = asdict(state.record)
    row['mode'] = state.record.mode.value
    return {'version': 1, 'pet': row}


def restore_collar(catalog: PetCatalog, payload: dict, *, owner_uid: int,
                   collar_uid: int) -> PetState:
    """Decode one actual owner's collar to STORED; no active actor resurrection.

    owner_uid/collar_uid come from actual inventory custody. Duplicate records,
    transfer of custody and live adoption are the existing caller's responsibility.
    Malformed, mismatched, unknown, inconsistent records fail without mutation.
    """
    _integer(owner_uid, 'owner UID', 1)
    _integer(collar_uid, 'collar UID', 1)
    if type(payload) is not dict or set(payload) != {'version', 'pet'} or type(payload['version']) is not int or payload['version'] != 1:
        raise ValueError('unsupported pet collar schema')
    row = payload['pet']
    if type(row) is not dict or set(row) != set(PetRecord.__dataclass_fields__):
        raise ValueError('invalid pet collar fields')
    row = dict(row)
    try:
        row['mode'] = PetCommand(row['mode'])
        record = PetRecord(**row)
    except (ValueError, TypeError):
        raise ValueError('invalid pet collar record') from None
    _record(catalog, record)
    if record.owner_uid != owner_uid or record.collar_uid != collar_uid:
        raise ValueError('pet collar custody mismatch')
    return PetState(record)


def activate_pet(state: PetState, *, actor_ref: EntityRef) -> PetState:
    """Bind an actual newly issued actor after real collar custody/adoption."""
    if state.life != PetLife.STORED:
        raise ValueError('stored pet required')
    if state.record.classic_template_id is None:
        raise ValueError('actual Classic pet template unresolved')
    if state.record.hp == 0:
        raise ValueError('dead pet cannot activate without revival')
    _ref(actor_ref)
    return replace(state, life=PetLife.ACTIVE, actor_ref=actor_ref, target_ref=None)
