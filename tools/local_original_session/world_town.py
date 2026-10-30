"""M2 town placement and NPC-click decisions; stdlib and pure world modules only.

Broker integration API::

    data = load_town()
    town = TownNpcs(world.entities, data, TownConfig(candidate_npc_ids={70523}))
    town.register()                 # under the existing world lock
    present = town.present(map_id, x, y, radius)
    appearance = town.appearance(present[0].uid)
    decision = town.route_click(decoded_signed_f1, player_map_id=map_id,
                                player_x=x, player_y=y, max_distance=owner_range)

``present`` supplies living Kind.NPC entities for the existing known-set
enter/exit diff; ``appearance`` supplies catalog template/sprite/name metadata.
WorldView.town consumes these entities through the existing known-set diff and
Actor codec. This module does not install an AI or send a frame.

All supplied placements remain attributed L1J placement policy. Registration is
empty by default. The broker explicitly opts confirmed_npc_ids(data) into its
product defaults; other catalog candidates require separate opt-in. Scope flags,
disabled_npc_ids and count0 still apply. Selected
catalog IDs are Entity.template_id metadata, NOT general Actor wire f39.
Unknown identities/sprites remain None even when placement is enabled. Fixed
headings and seeded selection are explicit LOCAL placement policy. Random
placements consume the attributed L1J difference-of-two-randoms rule; movement
distance and repeated source placements remain available in source metadata.

route_click accepts only the already decoded signed int32 4E43.f1, converting
its low32 bits to a live UID (run106 dialog-request-main-review.json:29).
It checks the registered lifetime and the caller's explicit map/range policy.
It returns dialogue/teleport/service decisions or world_shop.open_shop DATA;
it sends nothing. ShopListing.unavailable is retained. A shop decision is a
proposed list for the later menu action, not permission to skip 4E44 -> 4ED4.

Reuse: work/local_original_session/game-core-prep/M2_TOWN_NPCS.md; existing
implementation-4/shop-quest/dialogue-contract/{dialogue_wire.py,INTEGRATION.md},
hypertext-field4/INTEGRATION.md; menu-resource-stem-v1/INSTALL_API.md; and
world_shop.py. run106 establishes 4E43 -> 4E44 -> 4ED4; run122 establishes
data/uml/ + explicit 4E44.f2 stem + .uml. L1J dialogue stems are source hints,
never verified Classic resource keys. run143 does not establish catalog ID
consumption by general NPC f39. type6 appearance is not type15 input proof.
The broker must reuse the existing normal-NPC/dialogue producers with their
actual source inputs; no default f39, menu, action or teleport is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import random
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from tools.local_original_session.world_entities import Entity, EntityRef, EntityRegistry, Kind
from tools.local_original_session.world_shop import M2_DATA_DIR, ShopData, ShopListing, load_shops, open_shop

PlacementKey = tuple[int, int]  # L1J NPC ID, original placement row ID; never a live UID.


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class TownNpc:
    key: PlacementKey
    scope: str  # village / special / adjacent
    row: Mapping
    spawn: Mapping
    shop_row: Mapping | None = None

    @property
    def npc_id(self) -> int:
        return self.key[0]

    @property
    def mapping_status(self) -> str:
        return self.row['mapping_status']

    @property
    def classification(self) -> str:
        return self.row['classification']


@dataclass(frozen=True, slots=True)
class TownData:
    placements: Mapping[PlacementKey, TownNpc]
    shops: ShopData
    source_documents: Mapping  # Both complete JSON documents, recursively read-only.


def load_town(directory: str | Path = M2_DATA_DIR) -> TownData:
    """Read both NPC tables plus world_shop data; preserve unknown and zero rows.

    Town and shop services sharing (npc ID, spawn ID) are one placement. The
    richer town row owns role/dialogue; its original shop row remains attached.
    Special and adjacent tables are retained but require separate scope opt-in.
    """
    directory = Path(directory)
    town = _freeze(json.loads((directory / 'town_npcs.json').read_text(encoding='utf-8')))
    shops = _freeze(json.loads((directory / 'shop_npcs.json').read_text(encoding='utf-8')))
    shop_rows = {(row['l1j_npc_id'], row['spawn']['id']): row for row in shops['npcs']}
    placements = {}
    for table, scope in (('npcs', 'village'), ('special_npcs', 'special'),
                         ('adjacent_npcs', 'adjacent')):
        for row in town[table]:
            for spawn in row['spawns']:
                key = (row['l1j_npc_id'], spawn['id'])
                placements[key] = TownNpc(key, scope, row, spawn, shop_rows.get(key))
    for key, row in shop_rows.items():
        if key not in placements:
            placements[key] = TownNpc(key, 'village', row, row['spawn'], row)
    return TownData(MappingProxyType(placements), load_shops(directory),
                    MappingProxyType({'town_npcs': town, 'shop_npcs': shops}))


def with_gludin_town(base: TownData, directory: str | Path | None = None) -> TownData:
    """Startup merge; keep M2 menus and repeated M4 source placements intact.

    Some generic L1J merchants occur on both maps. Their existing shop/offer
    records win, while each (NPC, placement) keeps its own town metadata.
    No NPC identity, native menu or unsupported product is inferred here.
    """
    extra = load_town(M2_DATA_DIR.parent / 'm4' if directory is None else directory)
    return TownData(MappingProxyType(dict(extra.placements) | dict(base.placements)),
        ShopData(MappingProxyType(dict(extra.shops.npcs) | dict(base.shops.npcs)),
                 MappingProxyType(dict(extra.shops.offers) | dict(base.shops.offers))),
        MappingProxyType(dict(base.source_documents) | {'m4': extra.source_documents}))


@dataclass(frozen=True, slots=True)
class TownConfig:
    enable_candidates: bool = False
    candidate_npc_ids: frozenset[int] = field(default_factory=frozenset)
    disabled_npc_ids: frozenset[int] = field(default_factory=frozenset)
    include_special: bool = False
    include_adjacent: bool = False
    shop_sprite_candidates: frozenset[PlacementKey] = field(default_factory=frozenset)

    def __post_init__(self):
        object.__setattr__(self, 'candidate_npc_ids', frozenset(self.candidate_npc_ids))
        object.__setattr__(self, 'disabled_npc_ids', frozenset(self.disabled_npc_ids))
        object.__setattr__(self, 'shop_sprite_candidates', frozenset(self.shop_sprite_candidates))

    def enabled(self, npc: TownNpc) -> bool:
        return (npc.spawn['count'] > 0 and npc.npc_id not in self.disabled_npc_ids
                and (self.enable_candidates or npc.npc_id in self.candidate_npc_ids)
                and (npc.scope != 'special' or self.include_special)
                and (npc.scope != 'adjacent' or self.include_adjacent))


@dataclass(frozen=True, slots=True)
class TownAppearance:
    """Catalog presentation metadata, not Actor fields or render readiness.

    name is the selected Classic Korean name when supplied, otherwise the
    attributed L1J label. sprite_candidate is kept separate from selected sprite.
    wire_f39 stays None even for a selected catalog template.
    """
    catalog_template_id: int | None
    sprite_id: int | None
    name: str
    name_source: str
    sprite_candidate: Mapping | None
    mapping_status: str
    wire_f39: int | None = None


def appearance_for(npc: TownNpc) -> TownAppearance:
    row = npc.row
    template = row.get('selected_classic_npc_id')
    selected = next((candidate for candidate in row['classic_npc_candidates']
                     if candidate['id'] == template), None)
    # Do not select a same-number graphic or a multiple-template candidate.
    sprite = row.get('selected_classic_sprite_id')
    if sprite is None and selected is not None:
        sprite = selected.get('sprite_f2')
    name = selected.get('name_ko') if selected is not None else None
    return TownAppearance(template, sprite, name if name is not None else row['l1j_name'],
                          'classic_catalog' if name is not None else 'l1j_reference_label',
                          row.get('same_number_classic_sprite_candidate'), row['mapping_status'])


def confirmed_npc_ids(data: TownData) -> frozenset[int]:
    """Unique selected catalog identities/sprites for explicit broker opt-in.

    This selects catalog correspondence only. Placements remain attributed
    L1J policy and TownConfig retains scope, disabled-ID and count0 checks.
    """
    selected = set()
    for npc in data.placements.values():
        appearance = appearance_for(npc)
        if (appearance.catalog_template_id is not None and appearance.sprite_id is not None
                and len(npc.row['classic_npc_candidates']) == 1
                and npc.row['classic_npc_candidates'][0]['id'] == appearance.catalog_template_id):
            selected.add(npc.npc_id)
    return frozenset(selected)


@dataclass(frozen=True, slots=True)
class TownInteraction:
    ref: EntityRef
    npc: TownNpc
    kind: str
    appearance: TownAppearance
    dialogue: Mapping | None  # L1J SQL hints; null/empty/case preserved.
    shop_listing: ShopListing | None
    missing: tuple[str, ...]
    classic_menu_stem: str | None = None


class TownError(ValueError):
    """Unresolvable decoded click; reason is a stable local code."""


class TownNpcs:
    """Owned static placements in an existing registry; no tick/AI/scheduler.

    register(config) reconciles this owner's registrations only. Disable/remove
    uses EntityRegistry.remove so existing references become stale; re-enabling
    obtains new UIDs. Shutdown calls close(), leaving unrelated entities intact.
    Call all methods under the existing world owner lock.
    """
    def __init__(self, entities: EntityRegistry, data: TownData,
                 config: TownConfig | None = None, *, passable=None, random_passable=None):
        self.entities = entities
        self.data = data
        self.config = config if config is not None else TownConfig()
        self.passable = passable
        # Startup may retain already accepted fixed-tile policy while checking
        # actual sampled tiles against loaded terrain on every enabled map.
        self.random_passable = passable if random_passable is None else random_passable
        self._owned: dict[int, tuple[EntityRef, TownNpc, int]] = {}

    def adopt_registration(self, previous):
        """Transfer this catalog owner's already-issued actors during startup."""
        self._owned, previous._owned = previous._owned, {}

    def _entity(self, uid: int) -> Entity | None:
        owned = self._owned.get(uid)
        entity = self.entities.resolve(owned[0]) if owned is not None else None
        return entity if entity is not None and entity.alive and entity.kind is Kind.NPC else None

    def register(self, config: TownConfig | None = None) -> tuple[Entity, ...]:
        """Apply explicit candidate configuration; return newly registered NPCs.

        Multiple source placements stay separate, including overlapping centres.
        A positive count attempts that many actors; count0 is never enabled.
        Passability applies to the selected tile, not a random area's centre.
        No movement or service behavior is inferred.
        """
        if config is not None:
            self.config = config
        for uid, (_, npc, _) in tuple(self._owned.items()):
            if self._entity(uid) is None or not self.config.enabled(npc):
                # The registry never reuses UIDs; a generation change can be
                # our killed actor and still needs removal on reconciliation.
                if self.entities.get(uid) is not None:
                    self.entities.remove(uid)
                del self._owned[uid]
        existing = {(npc.key, ordinal) for _, npc, ordinal in self._owned.values()}
        created = []
        for npc in self.data.placements.values():
            if not self.config.enabled(npc):
                continue
            spawn = npc.spawn
            for ordinal in range(spawn['count']):
                if (npc.key, ordinal) in existing:
                    continue
                position = self._placement(npc, ordinal)
                if position is None:
                    continue
                x, y = position
                entity = self.entities.add(Kind.NPC, spawn['mapid'], x, y,
                                           heading=spawn['heading'],
                                           template_id=appearance_for(npc).catalog_template_id)
                self._owned[entity.uid] = (entity.ref, npc, ordinal)
                created.append(entity)
        return tuple(created)

    def _placement(self, npc: TownNpc, ordinal: int) -> tuple[int, int] | None:
        # L1Spawn.java:435-438 uses floor(random*range)-floor(random*range),
        # so range25 means -24..24 with triangular rather than uniform weight.
        # The seed, 64-attempt budget and NPC occupancy check are LOCAL policy;
        # they do not establish an original Classic fixed NPC position.
        spawn = npc.spawn
        cx, cy = spawn['locx'], spawn['locy']
        rx, ry = spawn.get('randomx') or 0, spawn.get('randomy') or 0
        if rx <= 0 and ry <= 0:
            if self.passable is not None and self.passable(spawn['mapid'], cx, cy) is not True:
                return None
            return cx, cy
        rng = random.Random(f'{npc.key}:{ordinal}')
        for _ in range(64):
            x = cx + int(rng.random() * rx) - int(rng.random() * rx)
            y = cy + int(rng.random() * ry) - int(rng.random() * ry)
            if self.random_passable is not None and self.random_passable(spawn['mapid'], x, y) is not True:
                continue
            if self.entities.near(spawn['mapid'], x, y, 0, kind=Kind.NPC):
                continue
            return x, y
        # Never turn exhausted invalid candidates into a blocked/occupied
        # centre. A later registration may retry this still-unregistered slot.
        return None

    def npc_for(self, uid: int) -> TownNpc | None:
        return self._owned[uid][1] if self._entity(uid) is not None else None

    def appearance(self, uid: int) -> TownAppearance | None:
        npc = self.npc_for(uid)
        if npc is None:
            return None
        result = appearance_for(npc)
        if (result.sprite_id is None and npc.key in self.config.shop_sprite_candidates
                and (npc.shop_row is not None or npc.classification == 'warehouse')
                and result.sprite_candidate is not None):
            # Explicit -ShopExp only. Keep unknown catalog identity/f39 and the
            # original candidate provenance; this is a LOCAL display experiment.
            result = replace(result, sprite_id=result.sprite_candidate['sprite_id'],
                mapping_status='LOCAL_SHOP_EXPERIMENT_SPRITE_CANDIDATE')
        return result

    def present(self, map_id: int, x: int, y: int, radius: int) -> list[Entity]:
        """Nearby owned live NPCs; caller applies world_visibility's screen test."""
        return [entity for entity in self.entities.near(map_id, x, y, radius, kind=Kind.NPC)
                if self._entity(entity.uid) is not None]

    def route_click(self, target_i32: int, *, player_map_id: int,
                    player_x: int, player_y: int, max_distance: int) -> TownInteraction:
        """Resolve decoded 4E43 live UID; return data only, no menu/HACTION execution.

        max_distance is the existing caller's local interaction policy, not an
        inferred original range. Catalog IDs, L1J IDs and placement keys cannot
        select an NPC unless they independently are a currently owned live UID.
        """
        if type(target_i32) is not int or not -(1 << 31) <= target_i32 < (1 << 31):
            raise TownError('DIALOG_TARGET_I32_REQUIRED')
        if type(max_distance) is not int or max_distance < 0:
            raise TownError('INTERACTION_RANGE_REQUIRED')
        uid = target_i32 & 0xffffffff
        entity = self._entity(uid)
        if entity is None:
            raise TownError('TOWN_TARGET_NOT_CURRENT')
        if entity.map_id != player_map_id:
            raise TownError('TOWN_TARGET_MAP_MISMATCH')
        if max(abs(entity.x - player_x), abs(entity.y - player_y)) > max_distance:
            raise TownError('TOWN_TARGET_OUT_OF_RANGE')
        npc = self._owned[uid][1]
        row = npc.row
        listing = None
        if npc.shop_row is not None and npc.shop_row['shop_row_count'] > 0:
            kind = 'shop'
            listing = open_shop(self.data.shops, npc.npc_id)
        elif row['l1j_impl'] == 'L1Teleporter':
            kind = 'teleport'
        elif npc.classification == 'warehouse':
            kind = 'warehouse'
        elif npc.classification == 'inn_menu_candidate':
            kind = 'inn'
        elif npc.classification == 'message_board':
            kind = 'board'
        else:
            kind = 'dialogue'
        appearance = appearance_for(npc)
        missing = ['NPC_WIRE_F39_SOURCE_UNKNOWN', 'NPC_INPUT_DISPATCH_UNVERIFIED',
                   'CLASSIC_MENU_RESOURCE_UNKNOWN']
        if appearance.catalog_template_id is None:
            missing.append('CLASSIC_NPC_IDENTITY_UNKNOWN')
        if appearance.sprite_id is None:
            missing.append('CLASSIC_NPC_SPRITE_UNSELECTED')
        if kind == 'teleport':
            missing.append('TELEPORT_DESTINATION_AND_COST_UNVERIFIED')
        return TownInteraction(entity.ref, npc, kind, appearance, row.get('dialogue'),
                               listing, tuple(missing))

    def close(self) -> None:
        """Remove this owner's remaining entities, including corpses; never reuse UIDs."""
        for uid in tuple(self._owned):
            if self.entities.get(uid) is not None:
                self.entities.remove(uid)
        self._owned.clear()


@dataclass(frozen=True)
class TownSetup:
    """Startup contribution passed through the registered town_setup fold."""
    town: TownNpcs
    services: object
    sources: tuple
    shop_experiment: object


def attach_view(view, town):
    """Register town visibility/lifetime without making WorldView own this feature."""
    from tools.local_original_session.world_visibility import SCREEN_LIMIT, town_spawn_frame
    view.town = town
    if 'town' in view.extensions:
        return
    view.extensions['town'] = True

    def present(pc_uid, map_id, x, y, known):
        return tuple(entity for entity in view.town.present(map_id, x, y, SCREEN_LIMIT)
                     if view.town.appearance(entity.uid).sprite_id is not None)

    def spawn(entity):
        appearance = view.town.appearance(entity.uid)
        return None if appearance is None else town_spawn_frame(entity, appearance)

    view.events.add('town', 'visible_entities', present, priority=10)
    view.events.add('town', 'spawn_frame', spawn)
    view.events.add('town', 'close', lambda: view.town.close())
