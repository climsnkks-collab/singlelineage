"""Pure polymorph proposals; no inventory, entity, packet, clock or save writes.

Integration API (world_feature_items owns the transaction)::

    catalog = load_polymorphs()                 # explicit startup file read
    state = initial_appearance(actual_actor_sprite)
    result = use_scroll(state, catalog, item_template_id=299, grade=1,
                        form_key='orc', character_level=1, now_ms=clock_ms,
                        weapon_type='sword')
    result = expire_polymorph(state, now_ms=clock_ms)
    result = remove_polymorph(state)

All operations return immutable proposals; commit result.state ONLY with the
caller's actual owned scroll cost, equipment removal and appearance publication
under the existing world lock. ``consume_count`` is a proposal, not a debit or
receipt. Rejections preserve the input state and have zero cost. Incompatible
weapons request removal rather than rejecting the form, matching L1J. Unknown
weapon kinds cannot supply a reliable takeoff decision and are refused. None
means actually unarmed, not an unknown equipment snapshot. Armor masks and
can_use_skill remain definitions for their future owners; this module does not
claim to apply armor takeoff, skill restrictions or special quest/map states.
Caller-owned life, selection, ownership and such restrictions remain necessary.

``base_sprite_id`` must come from the caller's real current base appearance,
never a character class ID. It survives refresh/re-polymorph unchanged and is
restored on removal/expiry; no equipment is automatically re-equipped. A new
form replaces its timer (no additive stacking), and expiry is inclusive at the
deadline. Times are caller-provided integer milliseconds in ONE clock domain.
An active state must be expired before independent weapon/skill decisions.
Persisting these absolute deadlines across restart requires the clock/save
owner's conversion policy; no persistence or restart equivalence is supplied.

Identity sources are data/m1/polymorph.json: 70 reviewed L1J mappings plus7
explicit client XML label aliases, against Classic SPR names/resources, including7 different-ID
mappings and10 dedicated30012..30021 morph selections with their ordinary
alternatives preserved. Native selection uses exact XML monster names (see
POLYMORPH_SELECT_UI.md); sprite mappings remain attributed local policy,
not numeric poly-ID equivalence. Normal XML menu levels supply explicit LOCAL
admission for matched labels; old L1J levels remain in the data as provenance.
Special-scroll/event availability and policy-less visuals stay inactive.
Classic native-dump has no polymorph table. Ordinary NPC f2 is supporting
identity only: orc bow morph3860 uses resource57, but is NOT sprite57. File IDs,
SPR keys, L1J poly/template IDs and character class IDs are separate namespaces.
The JSON separates Classic facts, static mapping candidates and L1J-derived
LOCAL backend policies (levels, masks, durations). None proves Classic play.

Reuse/evidence: work/local_original_session/game-core-prep/MAPPING_SCOPE.md
section3; implementation-1/item-use-effect/provenance/authority-findings.md
:7-17 documents ActorNotify4E96 f3/current SPR authority, no old form producer,
and no proven class->base mapping. Existing shared-api/implementation/integration
API/HANDOFF searches found no reusable polymorph producer. Native appearance
CHANGE is now integrated by world_feature_items using source-confirmed
SC4E5C (run390); native rendering remains unobserved. Earlier run380_map_transition_receive/
fields_findings.md:19 identifies PolymorphSubsystem via the RTTI instruction
at RVA4454C4 within getter445470; it supplies no change-frame contract. L1J
src/l1j/server/server/serverpackets/S_ChangeShape.java:29-42 is an older protocol,
NOT a Classic packet contract; neither that opcode nor ActorNotify4E96 is
invented as a polymorph change frame here. POLYMORPH_SELECT_UI.md records the
static raw16/local-list/params.f7 path. Socket tests establish only saved cost,
server state and expiry; original input, rendering and animation remain unknown.

Read-only reference root D:/SingleLineageRef/l1j-en-classic: L1PolyMorph.java
:43-63,:104-125,:238-263,:277-290,:297-313 supplies masks/timer/takeoff/undo;
datatables/ItemTable.java:122-139 supplies weapon strings; C_ItemUSe.java
:3023-3054 supplies normal1800s/blessed2100s and level admission. The current
module intentionally exposes local state calculation only, not formal PASS.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

DEFAULT_PATH = Path(__file__).resolve().parent / 'data' / 'm1' / 'polymorph.json'

# L1J bit positions, NOT weapon type numbers or Classic stance values.
WEAPON_MASKS: Mapping[str, int] = MappingProxyType({
    'dagger': 1, 'sword': 2, 'twohand': 4, 'axe': 8, 'blunt': 8,
    'spear': 16, 'staff': 32, 'edoryu': 64, 'claw': 128, 'bow': 256,
    'kiringku': 512, 'chainsword': 1024,
    'tohandsword': 4, 'tohandblunt': 8, 'tohandstaff': 32,
    'singlespear': 16, 'singlebow': 256, 'throwingknife': 256,
    'arrow': 256, 'gauntlet': 256,
})


@dataclass(frozen=True, slots=True)
class PolymorphDef:
    key: str
    name: str
    classic_sprite_id: int
    l1j_polymorph_id: int
    l1j_poly_id: int
    min_level: int
    weapon_mask: int
    armor_mask: int
    can_use_skill: bool
    cause_mask: int
    mapping_status: str


@dataclass(frozen=True, slots=True)
class ScrollDef:
    item_template_id: int
    grade: int
    l1j_item_id: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class PolymorphCatalog:
    forms: Mapping[str, PolymorphDef]
    scrolls: Mapping[tuple[int, int], ScrollDef]
    native_names: Mapping[str, str]


def load_polymorphs(path: Path | str = DEFAULT_PATH) -> PolymorphCatalog:
    """Explicit read-only startup loader. Import and calculations perform no IO."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    forms = {}
    for row in raw['forms']:
        p = row['backend_policy']
        form = PolymorphDef(
            row['key'], row.get('display_name', row['l1j_name']), row['classic_sprite']['sprite_id'],
            row['l1j_polymorph_id'], row['l1j_poly_id'], p['min_level'],
            p['weapon_mask'], p['armor_mask'], p['can_use_skill'], p['cause_mask'],
            row['mapping']['status'])
        forms[form.key] = form
    scrolls = {}
    for row in raw['scrolls']:
        scroll = ScrollDef(row['classic_item_template_id'], row['grade'],
                           row['l1j_item_id'], row['backend_policy']['duration_s'] * 1000)
        scrolls[(scroll.item_template_id, scroll.grade)] = scroll
    # The native list sends the exact XML monster name, not a sprite/desc/key.
    # Keep the reviewed XML -> runtime mapping; aliases share existing policy.
    names = {row['display_name']: row['runtime_form_key']
             for row in raw['classic_catalog']['entries']
             if row['runtime_form_key'] is not None}
    return PolymorphCatalog(MappingProxyType(forms), MappingProxyType(scrolls),
                            MappingProxyType(names))


@dataclass(frozen=True, slots=True)
class ActivePolymorph:
    form_key: str
    sprite_id: int
    started_at_ms: int
    expires_at_ms: int


@dataclass(frozen=True, slots=True)
class AppearanceState:
    base_sprite_id: int
    current_sprite_id: int
    active: ActivePolymorph | None = None


@dataclass(frozen=True, slots=True)
class PolymorphResult:
    state: AppearanceState
    allowed: bool
    reason: str
    appearance_changed: bool = False
    unequip_weapon: bool = False
    consume_count: int = 0


def initial_appearance(actual_base_sprite_id: int) -> AppearanceState:
    """Capture caller-observed appearance; no class/gender->sprite inference."""
    return AppearanceState(actual_base_sprite_id, actual_base_sprite_id)


def level_allowed(form: PolymorphDef, character_level: int) -> bool:
    return character_level >= form.min_level


def weapon_allowed(form: PolymorphDef, weapon_type: str | None) -> bool | None:
    """True=may remain, False=take off, None=unknown type (not permission)."""
    if weapon_type is None or weapon_type == 'unarmed':
        return True
    bit = WEAPON_MASKS.get(weapon_type)
    return None if bit is None else bool(form.weapon_mask & bit)


def _time_ms(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer millisecond value')


def apply_polymorph(state: AppearanceState, form: PolymorphDef, *,
                    character_level: int, now_ms: int, duration_ms: int,
                    weapon_type: str | None = None) -> PolymorphResult:
    """Calculate a replacement timer and appearance; no scroll cost at this layer.

    ``form`` is an explicitly selected definition from the caller's catalog.
    Only item-magic cause1 is supported, without GM/event level bypasses.
    """
    _time_ms(now_ms, 'now_ms')
    _time_ms(duration_ms, 'duration_ms')
    if not duration_ms:
        raise ValueError('duration_ms must be positive')
    if not level_allowed(form, character_level):
        return PolymorphResult(state, False, 'level_too_low')
    if not form.cause_mask & 1:
        return PolymorphResult(state, False, 'item_magic_not_allowed')
    allowed_weapon = weapon_allowed(form, weapon_type)
    if allowed_weapon is None:
        return PolymorphResult(state, False, 'unknown_weapon_type')
    active = ActivePolymorph(form.key, form.classic_sprite_id, now_ms,
                              now_ms + duration_ms)
    proposed = AppearanceState(state.base_sprite_id, form.classic_sprite_id, active)
    return PolymorphResult(proposed, True, 'applied',
                           state.current_sprite_id != form.classic_sprite_id,
                           not allowed_weapon)


def use_scroll(state: AppearanceState, catalog: PolymorphCatalog, *,
               item_template_id: int, grade: int, form_key: str,
               character_level: int, now_ms: int,
               weapon_type: str | None = None) -> PolymorphResult:
    """Propose one actual Classic template+grade use; no numeric ID translation.

    An empty form key is the L1J scroll's explicit undo selection. A supported
    scroll is still consumed for undo when no effect is active, as in L1J.
    Explicit remove_polymorph() (dispel/cleanup) never proposes a scroll cost.
    """
    _time_ms(now_ms, 'now_ms')
    scroll = catalog.scrolls.get((item_template_id, grade))
    if scroll is None:
        return PolymorphResult(state, False, 'unsupported_scroll')
    if form_key == '':
        return replace(remove_polymorph(state), consume_count=1)
    form = catalog.forms.get(form_key)
    if form is None:
        return PolymorphResult(state, False, 'unknown_form')
    result = apply_polymorph(state, form, character_level=character_level,
                            now_ms=now_ms, duration_ms=scroll.duration_ms,
                            weapon_type=weapon_type)
    return replace(result, consume_count=1) if result.allowed else result


def remove_polymorph(state: AppearanceState) -> PolymorphResult:
    """Restore captured base appearance; idempotent, with no re-equip proposal."""
    if state.active is None:
        return PolymorphResult(state, True, 'not_polymorphed')
    proposed = initial_appearance(state.base_sprite_id)
    return PolymorphResult(proposed, True, 'removed',
                           state.current_sprite_id != state.base_sprite_id)


def remaining_ms(state: AppearanceState, *, now_ms: int) -> int:
    _time_ms(now_ms, 'now_ms')
    return 0 if state.active is None else max(0, state.active.expires_at_ms - now_ms)


def expire_polymorph(state: AppearanceState, *, now_ms: int) -> PolymorphResult:
    _time_ms(now_ms, 'now_ms')
    if state.active is None:
        return PolymorphResult(state, True, 'not_polymorphed')
    if now_ms < state.active.expires_at_ms:
        return PolymorphResult(state, True, 'not_due')
    return replace(remove_polymorph(state), reason='expired')
