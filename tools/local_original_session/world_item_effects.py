"""M1 consumable effects, independent of broker, inventory and persistence.

Call under the existing world lock, after the caller admits the owned item use.
``use`` changes only WorldCombat's HP/buffs or explicitly supplied PcAilments.
It neither removes an item nor commits a position. ``consume_count`` describes
the caller's inventory proposal; for destination_proposed it must wait for the
actual relocation to succeed. A movement proposal has unresolved wire needs
and is not a successful native teleport. Apply a destination through the
existing position owner and EntityRegistry.move, never by editing Entity fields.

Healing/speed arithmetic and SC4E38/4E5B encoding reuse WorldCombat. Its existing
nonnegative potion roll and simplified speed policy remain LOCAL policy, not
full L1J effects (DECAY_POTION, POLLUTE_WATER, barriers, equipment haste, etc.).
No animation/sound, poison-display or teleport opcode is invented here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import random
from types import MappingProxyType
from typing import Mapping, Protocol

from tools.local_original_session.game_data import M1_DATA_DIR
from tools.local_original_session.world_combat import WorldCombat
from tools.local_original_session.world_maps import MapDestination

DEFAULT_PATH = M1_DATA_DIR / 'item_effects.json'


class Terrain(Protocol):
    def bounds(self, map_id: int) -> tuple[int, int, int, int] | None: ...
    def can_stand(self, map_id: int, x: int, y: int) -> bool | None: ...


@dataclass(frozen=True, slots=True)
class ItemEffectDef:
    template_id: int
    name_ko: str
    kind: str
    reference_id: int
    heal_hp: int = 0
    buff_template_id: int | None = None
    buff_add_s: int | None = None
    teleport_radius: int = 200


def load_effects(path: str | Path = DEFAULT_PATH) -> Mapping[int, ItemEffectDef]:
    """Load explicit classic IDs; no numeric L1J-to-classic conversion."""
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    return MappingProxyType({row['template_id']: ItemEffectDef(
        row['template_id'], row['name_ko'], row['kind'], row['l1j_item_id'],
        row.get('heal_hp', 0), row.get('buff_template_id'), row.get('buff_add_s'),
        row.get('teleport_radius', 200)) for row in raw['effects']})


@dataclass(slots=True)
class PcAilments:
    """Optional caller-owned poison state; PcState currently has no poison field.

    None = healthy. The poison owner must also stop its damage/timer when the
    effect result reports poison_cured; this module runs no poison ticker.
    """
    poison: str | None = None


@dataclass(frozen=True, slots=True)
class FrameRequirement:
    kind: str
    opcode: int | None
    unresolved: str


@dataclass(frozen=True, slots=True)
class ItemEffectResult:
    template_id: int
    kind: str
    outcome: str  # applied / no_effect / destination_proposed / refused / unsupported
    consume_count: int = 0  # proposal only; this module never changes inventory
    frames: tuple[bytes, ...] = ()
    requirements: tuple[FrameRequirement, ...] = ()
    destination: MapDestination | None = None
    healed_hp: int = 0
    buff_kind: str | None = None
    buff_expires_at: float | None = None  # caller uses its existing expiry scheduler
    poison_cured: bool = False
    reason: str = ''


def random_destination(position: MapDestination, terrain: Terrain, rng: random.Random,
                       radius: int = 200) -> MapDestination | None:
    """Uniform sample of known standable cells in the same-map square.

    L1J randomLocation(200,true) supplies the radius only. This bounded scan is
    LOCAL selection policy; unknown/unloaded cells and the current cell cannot
    be destinations. Static can_stand does not establish doors/actor occupancy.
    Short uniform rejection sampling avoids a full scan on ordinary open maps.
    If all attempts fail, reservoir sampling still finds a sparse destination.
    Each path selects uniformly among eligible cells, so their mixture does too.
    """
    bounds = terrain.bounds(position.map_id)
    if bounds is None:
        return None
    x1, y1, x2, y2 = bounds
    x1, y1 = max(x1, position.x - radius), max(y1, position.y - radius)
    x2, y2 = min(x2, position.x + radius), min(y2, position.y + radius)
    if x1 > x2 or y1 > y2:
        return None
    for _ in range(32):
        x, y = rng.randint(x1, x2), rng.randint(y1, y2)
        if (x, y) != (position.x, position.y) and terrain.can_stand(position.map_id, x, y) is True:
            return MapDestination(position.map_id, x, y, 5)
    found, chosen = 0, None
    for y in range(y1, y2 + 1):
        for x in range(x1, x2 + 1):
            if (x, y) == (position.x, position.y):
                continue
            if terrain.can_stand(position.map_id, x, y) is True:
                found += 1
                if rng.randrange(found) == 0:
                    chosen = MapDestination(position.map_id, x, y, 5)
    return chosen


def movement_requirements(source_map: int, destination: MapDestination) -> tuple[FrameRequirement, ...]:
    requirements = [FrameRequirement('teleport', None,
        'Native teleport publication/order UNKNOWN. 4E2C is walking; '
        '4EE0 is position correction, not a verified teleport producer.')]
    if source_map != destination.map_id:
        requirements.append(FrameRequirement('map_notify', 0x4E95,
            'REA273: f1 map ID known; required f2 meaning/value, f3/f4 normal '
            'values and actor/currentPlayer re-establishment order UNKNOWN. '
            '03EB is not a map ACK.'))
    return tuple(requirements)


class WorldItemEffects:
    """Effect dispatcher; shares the combat RNG unless explicitly supplied."""

    def __init__(self, combat: WorldCombat, terrain: Terrain | None = None, *,
                 definitions: Mapping[int, ItemEffectDef] | None = None,
                 rng: random.Random | None = None):
        self.combat, self.terrain = combat, terrain
        self.definitions = load_effects() if definitions is None else definitions
        self.rng = combat.rng if rng is None else rng

    def use(self, uid: int, template_id: int, now: float, *,
            position: MapDestination | None = None,
            ailments: PcAilments | None = None) -> ItemEffectResult:
        definition = self.definitions.get(template_id)
        if definition is None:
            return ItemEffectResult(template_id, 'unknown', 'unsupported', reason='CLASSIC_ITEM_NOT_SUPPORTED')
        kind = definition.kind
        state = self.combat.pcs.get(uid)
        if state is None or state.dead or state.hp <= 0:
            return ItemEffectResult(template_id, kind, 'refused', reason='LIVING_BOUND_PC_REQUIRED')
        if kind == 'heal':
            healed, frame = self.combat.heal(uid, definition.heal_hp)
            return ItemEffectResult(template_id, kind, 'applied' if healed else 'no_effect',
                                    1, (frame,), healed_hp=healed)
        if kind == 'speed':
            # Use the existing data definition/rate and existing stacking and
            # class handling. Greater haste differs only in added duration.
            buff = self.combat.data.items[definition.buff_template_id].buff
            if definition.buff_add_s is not None:
                buff = replace(buff, add_s=definition.buff_add_s)
            effect = self.combat.apply_buff(uid, buff, now)
            if effect is None:
                return ItemEffectResult(template_id, kind, 'no_effect', 1, reason='CLASS_HAS_NO_EFFECT')
            expiry, frame = effect
            return ItemEffectResult(template_id, kind, 'applied', 1, (frame,),
                                    buff_kind=buff.kind, buff_expires_at=expiry)
        if kind == 'cure_poison':
            if ailments is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='POISON_STATE_UNSUPPLIED')
            cured = ailments.poison is not None
            ailments.poison = None
            return ItemEffectResult(template_id, kind, 'applied' if cured else 'no_effect', 1,
                requirements=(FrameRequirement('poison_status', None,
                    'Native poison-state display/sound wire UNKNOWN; poison owner must cancel its ticker.'),),
                poison_cured=cured)
        if position is None:
            return ItemEffectResult(template_id, kind, 'refused', reason='CURRENT_POSITION_REQUIRED')
        if kind == 'return_town':
            town = self.combat.data.town
            destination = MapDestination(town.map_id, town.respawn_x, town.respawn_y, 5)
        elif kind == 'random_teleport':
            if self.terrain is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='TERRAIN_UNSUPPLIED')
            destination = random_destination(position, self.terrain, self.rng, definition.teleport_radius)
            if destination is None:
                return ItemEffectResult(template_id, kind, 'refused', reason='NO_KNOWN_STANDABLE_DESTINATION')
        else:
            return ItemEffectResult(template_id, kind, 'unsupported', reason='EFFECT_NOT_SUPPORTED')
        return ItemEffectResult(template_id, kind, 'destination_proposed', 1,
            requirements=movement_requirements(position.map_id, destination), destination=destination,
            reason='POSITION_AND_NATIVE_WIRE_NOT_COMMITTED')
