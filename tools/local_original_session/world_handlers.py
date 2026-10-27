"""Pure world-mode opcode registry; no broker import, socket, timer or save path.

Host, under its existing world lock::

    handled = await dispatch(context, opcode, protobuf_body)

Registered C2S: movement4E2B, NPC click4E43, menu action4ED4, trade4ED1.
Unknown opcodes return False. Exceptions leave refusal/reporting to the host.
Context.send_frame appends plaintext frames to the existing reply collection;
the broker retains framing encryption, write/drain, FIRST/close and ownership.

run106 establishes 4E43 -> 4E44 -> 4ED4, and run122 establishes
data/uml/<4E44.f2 stem>.uml. Town/L1J dialogue hints are never resource keys.
Bind the existing dialogue_route, latest dialogue_wire_f4, shop_list_wire and
trade_request_wire modules once via WireBindings. BUY f6/7/8, list context,
menu actions and SELL UID mapping are explicit current owner inputs.

HostContext/HostStore below connect the existing kit inventory owner, queued
reply frames and original host movement operations. Source-backed ResourceMenu
NPC correspondences remain explicit startup inputs; none are inferred here.
Store.commit revalidates the snapshot/listing, applies the proposal and saves
with the existing inventory owner; only it supplies committed reply frames.
Movement and transitions likewise use existing host operations (including
session.world.encode_payload and current persistence/visibility), never guessed
map fields. A queued list is not evidence of delivery: current_source must
cover the host's original listing publication/write/drain ownership contract.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
import inspect
from types import MappingProxyType
from typing import Awaitable, Callable, Protocol

from tools.local_original_session.world_entities import Entity, EntityRegistry, EntityRef, Kind
from tools.local_original_session.world_maps import MapDestination, resolve_transition
from tools.local_original_session.world_shop import (
    InventoryItem, InventorySnapshot, OfferKey, Purchase, Sale,
    calculate_purchase, calculate_sale,
)
from tools.local_original_session.world_town import TownInteraction, TownNpcs

MOVE, CLICK, HACTION, TRADE = 0x4E2B, 0x4E43, 0x4ED4, 0x4ED1
HYPERTEXT, BUY_LIST, SELL_LIST = 0x4E44, 0x4E48, 0x4EE7
BUY, SELL = 5, 6


class HandlerError(ValueError):
    """Constant local refusal codes; no request or source content in messages."""


def _need(value: bool, code: str) -> None:
    if not value:
        raise HandlerError(code)


def _frame(opcode: int, body: bytes) -> bytes:
    # Existing normal_npc_source.frame / world_status_frames envelope, unchanged.
    return ((len(body) + 6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little')
            + body + b'\0\0')


@dataclass(frozen=True)
class WireBindings:
    """Actual existing codec modules, preserving their exact DTO module identity.

    No source scans or codec reloads occur in dispatch. An existing host may
    supply dialogue_wire's older subset, but that subset will reject f4.
    """
    click: object
    dialogue: object
    lists: object
    trade: object

    def dialogue_frame(self, fields: Mapping) -> bytes:
        return _frame(HYPERTEXT, self.dialogue.encode(HYPERTEXT, dict(fields)))

    def list_frame(self, window: ShopWindow) -> bytes:
        operation = self.lists.BUY if window.mode == BUY else self.lists.SELL
        return _frame(self.lists.OPCODES[operation], self.lists.encode(operation, window.value))


@dataclass(frozen=True)
class Dialogue:
    fields: Mapping
    source: object  # Existing resource/menu owner identity, never a guessed stem.

    def __post_init__(self):
        object.__setattr__(self, 'fields', MappingProxyType(dict(self.fields)))


@dataclass(frozen=True)
class ShopWindow:
    mode: int
    value: object  # Exact existing shop_list_wire.Value, all wire operands explicit.
    rows: Mapping[int, OfferKey | int]  # BUY row -> OfferKey; SELL row -> owned UID.
    source: object  # Existing detached listing owner, generation and publication.

    def __post_init__(self):
        _need(type(self.mode) is int and self.mode in (BUY, SELL), 'SHOP_MODE_REQUIRED')
        object.__setattr__(self, 'rows', MappingProxyType(dict(self.rows)))


@dataclass(frozen=True)
class TradeSnapshot:
    inventory: InventorySnapshot
    items: tuple[InventoryItem, ...]
    revision: object  # Existing store revision/CAS identity, not a new save protocol.


class Store(Protocol):
    def snapshot(self, pc_uid: int, now: float) -> TradeSnapshot | Awaitable[TradeSnapshot]: ...

    def commit(self, pc_uid: int, snapshot: TradeSnapshot, window: ShopWindow,
               request: object, proposal: Purchase | Sale, now: float
               ) -> tuple[bytes, ...] | Awaitable[tuple[bytes, ...]]:
        """Atomic current ownership/listing + revision check, mutation and save.

        Raise on failure; return only already committed existing inventory frames.
        The proposal alone supplies neither real UIDs nor successful persistence.
        """
        ...


@dataclass(frozen=True)
class MovementResult:
    accepted: bool
    frames: tuple[bytes, ...]  # Preserve host movement reply order; no self4E2C.
    transitioned: bool = False


@dataclass
class HandlerState:
    """One connection's transient interaction state; discard on rebind/close."""
    interaction: TownInteraction | None = None
    menu: Dialogue | None = None
    window: ShopWindow | None = None

    def clear(self) -> None:
        self.interaction = self.menu = self.window = None


class WorldState(Protocol):
    entities: EntityRegistry


class Context(Protocol):
    """Host-bound current session; no usable fake defaults for missing services.

    Use the host's existing world operation ownership for the whole dispatch. Bind
    world/PC/store to the same current selected connection. current_source owns
    resource/menu/listing validity, including delivered-list and row ownership.
    """
    world: WorldState
    pc_uid: int
    town: TownNpcs
    store: Store
    wire: WireBindings
    state: HandlerState
    interaction_distance: int  # Explicit local host policy, not an original range.

    def now(self) -> float: ...
    def send_frame(self, frame: bytes) -> None: ...
    def current_source(self, source: object) -> bool: ...
    def dialogue_for(self, interaction: TownInteraction, now: float) -> Dialogue | Awaitable[Dialogue]: ...
    def shop_action(self, interaction: TownInteraction, menu: Dialogue,
                    fields: Mapping, now: float) -> ShopWindow | Awaitable[ShopWindow]:
        """Resolve actual current menu action; no assumed buy/sell action literal."""
        ...
    def move(self, payload: bytes, now: float) -> MovementResult | Awaitable[MovementResult]:
        """Run existing decoder/router/movement/persistence and update live state."""
        ...
    def transition(self, destination: MapDestination, now: float
                   ) -> tuple[bytes, ...] | Awaitable[tuple[bytes, ...]]:
        """Existing atomic map/position/visibility/store operation and encoders."""
        ...


def _pc(ctx: Context) -> Entity:
    pc = ctx.world.entities.get(ctx.pc_uid)
    _need(pc is not None and pc.kind is Kind.PC and pc.alive, 'CURRENT_LIVE_PC_REQUIRED')
    _need(ctx.town.entities is ctx.world.entities, 'SAME_WORLD_TOWN_REQUIRED')
    return pc


def _interaction(ctx: Context, ref: EntityRef) -> TownInteraction:
    pc = _pc(ctx)
    _need(ctx.world.entities.resolve(ref) is not None, 'STALE_NPC_REFERENCE')
    signed = ref.uid if ref.uid < (1 << 31) else ref.uid - (1 << 32)
    result = ctx.town.route_click(signed, player_map_id=pc.map_id,
                                  player_x=pc.x, player_y=pc.y,
                                  max_distance=ctx.interaction_distance)
    _need(result.ref == ref, 'STALE_NPC_REFERENCE')
    return result


def _emit(ctx: Context, frames: tuple[bytes, ...]) -> None:
    _need(type(frames) is tuple and all(type(frame) is bytes for frame in frames),
          'EXISTING_REPLY_FRAMES_REQUIRED')
    for frame in frames:
        ctx.send_frame(frame)


async def _result(value):
    return await value if inspect.isawaitable(value) else value


async def handle_click(ctx: Context, payload: bytes, now: float) -> None:
    begin = getattr(ctx, 'begin_click', None)
    if begin is not None:
        begin()
    target = ctx.wire.click.decode_request(payload)
    pc = _pc(ctx)
    interaction = ctx.town.route_click(target, player_map_id=pc.map_id,
                                      player_x=pc.x, player_y=pc.y,
                                      max_distance=ctx.interaction_distance)
    # An attempted new dialogue invalidates the preceding local shop selection.
    ctx.state.clear()
    menu = await _result(ctx.dialogue_for(interaction, now))
    _interaction(ctx, interaction.ref)
    _need(isinstance(menu, Dialogue) and menu.source is not None
          and ctx.current_source(menu.source), 'CURRENT_DIALOGUE_SOURCE_REQUIRED')
    _need(menu.fields.get(1) == target, 'DIALOGUE_TARGET_BITS_CHANGED')
    frame = ctx.wire.dialogue_frame(menu.fields)
    ctx.send_frame(frame)
    ctx.state.interaction, ctx.state.menu = interaction, menu


async def handle_action(ctx: Context, payload: bytes, now: float) -> None:
    fields = ctx.wire.dialogue.decode_haction_normal(payload)
    state = ctx.state
    _need(state.interaction is not None and state.menu is not None, 'CURRENT_MENU_REQUIRED')
    interaction = _interaction(ctx, state.interaction.ref)
    _need(fields[1] == state.menu.fields[1] and ctx.current_source(state.menu.source),
          'CURRENT_MENU_TARGET_REQUIRED')
    service = getattr(ctx, 'service_action', None)
    if service is not None and await _result(service(interaction, state.menu, fields, now)):
        return
    _need(interaction.shop_listing is not None, 'SHOP_ACTION_OWNER_UNAVAILABLE')
    state.window = None
    window = await _result(ctx.shop_action(interaction, state.menu, fields, now))
    _interaction(ctx, interaction.ref)
    _need(isinstance(window, ShopWindow) and window.source is not None
          and ctx.current_source(window.source), 'CURRENT_SHOP_LIST_SOURCE_REQUIRED')
    codec = ctx.wire.lists
    operation = codec.BUY if window.mode == BUY else codec.SELL
    _need(type(window.value) is codec.Value and window.value.kind == operation,
          'EXACT_SHOP_LIST_VALUE_REQUIRED')
    values = dict(window.value.fields)
    # Wire keys are signed i32; selections echo low32, including high-bit keys.
    keys = [dict(row.fields)[1] & 0xffffffff for row in values.get(3, ())]
    _need(len(keys) == len(set(keys)) and set(keys) == set(window.rows),
          'EXACT_LISTING_ROW_MAP_REQUIRED')
    if window.mode == BUY:
        allowed = {offer.key for offer in interaction.shop_listing.offers}
        _need(all(key in allowed for key in window.rows.values()), 'SHOP_OFFER_NOT_LISTED')
    else:
        _need(all(type(uid) is int and uid > 0 for uid in window.rows.values()),
              'EXPLICIT_SELL_UID_MAPPING_REQUIRED')
    ctx.send_frame(ctx.wire.list_frame(window))
    state.window = window


async def handle_trade(ctx: Context, payload: bytes, now: float) -> None:
    warehouse = getattr(ctx, 'warehouse_trade', None)
    if warehouse is not None and await _result(warehouse(payload, now)):
        return
    request = ctx.wire.trade.decode_normal(payload)
    state, window = ctx.state, ctx.state.window
    _need(state.interaction is not None and state.menu is not None and window is not None,
          'CURRENT_SHOP_WINDOW_REQUIRED')
    interaction = _interaction(ctx, state.interaction.ref)
    _need(ctx.current_source(state.menu.source) and ctx.current_source(window.source),
          'CURRENT_SHOP_LIST_SOURCE_REQUIRED')
    values = dict(window.value.fields)
    _need(request.mode == window.mode and request.context_u32 == (values[1] & 0xffffffff),
          'SHOP_LIST_CONTEXT_MISMATCH')
    _need(all(row.row_key_u32 in window.rows for row in request.items), 'UNKNOWN_SHOP_ROW')
    snapshot = await _result(ctx.store.snapshot(ctx.pc_uid, now))
    _need(isinstance(snapshot, TradeSnapshot), 'CURRENT_TRADE_SNAPSHOT_REQUIRED')
    selections = tuple((window.rows[row.row_key_u32], row.quantity) for row in request.items)
    data, npc_id = ctx.town.data.shops, interaction.npc.npc_id
    if request.mode == BUY:
        proposal = calculate_purchase(data, npc_id, snapshot.inventory, selections)
    else:
        proposal = calculate_sale(data, npc_id, adena=snapshot.inventory.adena,
                                  items=snapshot.items, selections=selections)
    frames = await _result(ctx.store.commit(ctx.pc_uid, snapshot, window, request, proposal, now))
    # After an owner commit the old snapshot/listing is not reusable locally.
    state.window = None
    _emit(ctx, frames)


async def handle_move(ctx: Context, payload: bytes, now: float) -> None:
    _pc(ctx)
    result = await _result(ctx.move(payload, now))
    _need(isinstance(result, MovementResult) and type(result.accepted) is bool,
          'EXPLICIT_MOVEMENT_RESULT_REQUIRED')
    _emit(ctx, result.frames)
    if not result.accepted:
        return
    if result.transitioned:
        ctx.state.clear()
        return  # arrival may itself be the inverse stair's source cell
    pc = _pc(ctx)  # Read committed destination, never infer from requested bytes.
    destination = resolve_transition(pc.map_id, pc.x, pc.y)
    if destination is not None:
        frames = await _result(ctx.transition(destination, now))
        ctx.state.clear()
        _emit(ctx, frames)


async def handle_item_use(ctx: Context, payload: bytes, now: float):
    use = getattr(ctx, 'use_item', None)
    return False if use is None else await _result(use(payload, now))


async def handle_warehouse_close(ctx: Context, payload: bytes, now: float):
    close = getattr(ctx, 'warehouse_close', None)
    return False if close is None else await _result(close(payload, now))


Handler = Callable[[Context, bytes, float], Awaitable[None]]
HANDLERS: Mapping[int, Handler] = MappingProxyType({
    MOVE: handle_move, CLICK: handle_click, HACTION: handle_action, TRADE: handle_trade,
    0x0960: handle_item_use,
    0x097B: handle_warehouse_close,
})


async def dispatch(ctx: Context, opcode: int, payload: bytes) -> bool:
    """One world-mode dispatch call. Return False only for an unregistered opcode."""
    handler = HANDLERS.get(opcode)
    if handler is None:
        return False
    _need(type(payload) is bytes, 'PROTOBUF_BODY_BYTES_REQUIRED')
    return await handler(ctx, payload, ctx.now()) is not False


# Host integration. All file/source preparation is explicit and startup-only.
@dataclass(frozen=True)
class KitItemPolicy:
    """Explicit LOCAL shop policy; prototype comes from an existing ItemInfo producer.

    A missing prototype permits existing-stack changes but never a new item.
    No Classic grade, enchantment, equipment state or UID is inferred here.
    """
    template_id: int
    raw_weight: int
    stackable: bool
    grant_fields: Mapping | None = None

    def __post_init__(self):
        _need(type(self.template_id) is int and self.template_id > 0
              and type(self.raw_weight) is int and self.raw_weight >= 0
              and type(self.stackable) is bool, 'EXPLICIT_KIT_ITEM_POLICY_REQUIRED')
        if self.grant_fields is not None:
            object.__setattr__(self, 'grant_fields', MappingProxyType(dict(self.grant_fields)))


@dataclass(frozen=True)
class HostNpcSource:
    """Consume an existing prepared ResourceMenu, retaining its original owner.

    placement_key is the explicit live town placement correspondence. row_keys
    maps the producer's wire row to world_shop OfferKey (BUY) or owned UID
    (SELL); it is never manufactured from an array position or catalog number.
    ResourceMenu.current checks its original projection without file IO.
    """
    resource: object
    placement_key: tuple[int, int]
    row_keys: Mapping

    @classmethod
    def from_resource(cls, resource, placement_key, row_keys):
        resource.current(cold=True)
        result = cls(resource, placement_key, MappingProxyType(dict(row_keys)))
        _need(len(resource.policy.replies) == 1
              and resource.policy.listing.reply_index == 0,
              'SINGLE_EXISTING_SHOP_REPLY_REQUIRED')
        return result

    def current(self):
        self.resource.current()
        return True


@dataclass(frozen=True)
class HostBindings:
    wire: WireBindings
    town: TownNpcs
    sources: Mapping
    item_policies: Mapping
    interaction_distance: int
    allocate_uid: Callable | None
    sale_item: Callable | None


def _starter_fields():
    # Same complete raw prototype as broker.INVENTORY_STARTER_FIELDS and its
    # _inventory_kit_frame/_world_pickup_commit producers; LOCAL plain kit only.
    return {1: 65537, 2: 1, 3: 0, 4: 1, 5: 0, 7: 0, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0,
            24: False, 25: 0, 26: False}


def _default_item_policies(town):
    """Startup-only native f10 burden and existing M1/M2 stacking policy.

    f10's weight name/unit remain a LOCAL interpretation (fields.json); M2's
    calculations retain their attributed L1J weights. This does not assert
    verified Classic economics. Unknown stacking/weight remains unavailable.
    """
    import json
    from pathlib import Path
    from tools.local_original_session.game_data import load_items
    from tools.local_original_session.world_ground_items import _STACKABLE_FALLBACK
    definitions = load_items()
    native = {}
    path = Path(__file__).resolve().parents[2] / 'work/source_game_data/native-dump-v1.jsonl'
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['table'] == 'item':
                fields = {entry['number']: entry['scalar'] for entry in row['fields'] if entry['wire'] == 0}
                if 10 in fields and 5 in fields:
                    native[row['id']] = (fields[10], fields[5])
    fallback = {}
    for offer in town.data.shops.offers.values():
        if offer.calculable:
            fallback.setdefault(offer.classic_item_id, (offer.weight_milli, offer.stackable))
    policies = []
    for template in definitions.keys() | fallback.keys() | _STACKABLE_FALLBACK.keys():
        definition = definitions.get(template)
        weight = native.get(template, (fallback.get(template, (None, None))[0], None))[0]
        stackable = (definition.stackable if definition is not None else
                     fallback.get(template, (None, _STACKABLE_FALLBACK.get(template)))[1])
        icon = definition.icon if definition is not None else native.get(template, (None, None))[1]
        if weight is None or stackable is None or icon is None:
            continue
        fields = _starter_fields()
        fields.update({2: template, 7: icon})
        policies.append(KitItemPolicy(template, weight, stackable, fields))
    return tuple(policies)


def _default_sale_item(ctx, row):
    # The unmodified kit producer's plain instance is LOCAL normal bless0 and
    # enchant0. Unknown raw changes are ineligible, never decoded speculatively.
    fields = dict(row.raw_fields)
    prototype = ctx.bindings.item_policies[row.template_bits].grant_fields
    plain = prototype is not None and all(fields[n] == value for n, value in prototype.items()
                                           if n not in (1, 4, 7))
    effect = getattr(ctx.broker, '_item_equipment_effect', None)
    state = None if effect is None else effect.store.restore(ctx.pc_uid, ctx.broker._inventory_current_frame)
    # No equipment state cannot establish resale eligibility for equipment.
    definition = (getattr(effect, '_defs', None) or {}).get(row.template_bits) if effect is not None else None
    unknown_equipment = state is None and (
        definition.equippable if definition is not None else not ctx.bindings.item_policies[row.template_bits].stackable)
    equipped = unknown_equipment or (state is not None and (
        state.weapon_uid == row.identifier or any(uid == row.identifier for _, uid in state.slots)))
    return InventoryItem(row.identifier, row.template_bits, fields[4],
                         0 if plain else 128, bool(equipped), 0)


def prepare_host_bindings(town: TownNpcs, *, sources=(), item_policies=None,
                          interaction_distance: int = 15, allocate_uid=None,
                          sale_item=None, wire: WireBindings | None = None) -> HostBindings:
    """Call once before receiving requests; never call from an opcode handler.

    Range15 is explicit LOCAL host policy. No Classic menu mapping is installed.
    Existing ResourceMenu inputs
    must already contain a real stem, verified resource/command and all BUY
    operands. allocate_uid optionally overrides the existing pickup max+1 policy;
    sale_item(ctx, ItemInfo) may override the existing plain-kit/equipment facts.
    """
    from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
    if wire is None:
        import importlib.util
        from pathlib import Path
        import sys
        contract = (Path(__file__).resolve().parents[2]
                    / 'work/local_original_session/implementation-4/shop-quest/dialogue-contract')

        def load(name, relative):
            path = contract / relative
            module = sys.modules.get(name)
            if module is not None:
                _need(Path(module.__file__).resolve() == path.resolve(),
                      'EXISTING_CODEC_MODULE_IDENTITY_MISMATCH')
                return module
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(name, None)
                raise
            return module

        wire = WireBindings(load('dialogue_route', 'dialogue_route.py'),
                            load('dialogue_wire_f4', 'hypertext-field4/dialogue_wire_f4.py'),
                            load('shop_list_wire', 'shop-list-wire/shop_list_wire.py'),
                            load('trade_request_wire', 'trade-request-wire/trade_request_wire.py'))
    # Existing inventory codec sources are prepared here, not by a trade request.
    inventory._source()
    inventory_update.source_ready()
    item_transfer_protocol.source_ready()
    _need(type(interaction_distance) is int and interaction_distance >= 0,
          'INTERACTION_RANGE_REQUIRED')
    if item_policies is None:
        item_policies = _default_item_policies(town)
    if sale_item is None:
        sale_item = _default_sale_item
    mapped, policies = {}, {}
    from tools.local_original_session.world_shop_menu import MenuSource
    from tools.local_original_session.world_town_services import ServiceMenuSource
    for source in sources:
        _need(type(source) in (HostNpcSource, MenuSource, ServiceMenuSource) and source.placement_key not in mapped,
              'UNIQUE_EXISTING_RESOURCE_SOURCE_REQUIRED')
        if type(source) is HostNpcSource:
            source.resource.current(cold=True)
        else:
            source.current()
        mapped[source.placement_key] = source
    for policy in item_policies:
        _need(type(policy) is KitItemPolicy and policy.template_id not in policies,
              'UNIQUE_KIT_ITEM_POLICY_REQUIRED')
        if policy.grant_fields is not None:
            item = inventory.validate_frame(inventory.build_add(dict(policy.grant_fields)))
            _need(item.template_bits == policy.template_id, 'GRANT_TEMPLATE_MISMATCH')
        policies[policy.template_id] = policy
    _need((allocate_uid is None or callable(allocate_uid))
          and (sale_item is None or callable(sale_item)), 'SYNC_OWNER_CALLBACK_REQUIRED')
    return HostBindings(wire, town, MappingProxyType(mapped), MappingProxyType(policies),
                        interaction_distance, allocate_uid, sale_item)


@dataclass(eq=False)
class _HostSource:
    owner: object  # prepared ResourceMenu or startup-loaded MenuSource
    ref: EntityRef
    kind: str
    inventory: bytes | None = None
    delivered: bool = False
    retired: bool = False


class HostStore:
    """Existing kit CAS owner adapter; no new sidecar, rollback or save format."""
    def __init__(self, ctx):
        self.ctx = ctx

    def snapshot(self, pc_uid, now):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_weight import stack_weight, maximum_weight
        ctx = self.ctx
        ctx._owned()
        _need(pc_uid == ctx.pc_uid, 'SAME_CURRENT_PC_REQUIRED')
        frame = ctx.broker._inventory_current_frame
        _need(type(frame) is bytes, 'CURRENT_KIT_FRAME_REQUIRED')
        rows = inventory.validate_kit_frame(frame)
        counts, weight, adena, sale_items = {}, 0, [], []
        for row in rows:
            values = dict(row.raw_fields)
            policy = ctx.bindings.item_policies.get(row.template_bits)
            # A row without a shop policy or with no quantity (kept Q0 anchor) is
            # simply not offered; it never closes the whole shop.
            if policy is None or not 0 < values[4] <= 2_000_000_000:
                continue
            weight += stack_weight(policy.raw_weight, values[4])
            if policy.stackable:
                # A complete producer prototype is the compatibility contract.
                compatible = policy.grant_fields is None or all(
                    values[n] == value for n, value in policy.grant_fields.items() if n not in (1, 4))
                # LOCAL grade markers create distinct scroll stacks. Only the
                # exact producer variant may receive this shop's new quantity.
                if compatible:
                    _need(row.template_bits not in counts, 'AMBIGUOUS_COMPATIBLE_STACK')
                    counts[row.template_bits] = values[4]
            if row.template_bits == 7:
                adena.append(values[4])
            if ctx.bindings.sale_item is not None:
                item = ctx.bindings.sale_item(ctx, row)
                _need(isinstance(item, InventoryItem) and item.uid == row.identifier
                      and item.item_id == row.template_bits and item.count == values[4],
                      'CURRENT_SALE_ITEM_FACTS_REQUIRED')
                sale_items.append(item)
        _need(len(adena) <= 1, 'UNIQUE_ADENA_STACK_REQUIRED')
        position = ctx.broker.realm.service(ctx.writer).snapshot()
        profile = ctx.broker._world_pc_profile(ctx.writer, position)
        capacity = int(maximum_weight(profile.strength, profile.con))
        return TradeSnapshot(InventorySnapshot(adena[0] if adena else 0, len(rows), weight,
                                               capacity, MappingProxyType(counts)),
                             tuple(sale_items), frame)

    def commit(self, pc_uid, snapshot, window, request, proposal, now):
        from tools.local_original_session import inventory, inventory_update, item_transfer_protocol
        ctx = self.ctx
        ctx._owned()
        _need(pc_uid == ctx.pc_uid and ctx.current_source(window.source)
              and window.source.delivered, 'DRAINED_CURRENT_SHOP_LIST_REQUIRED')
        old = ctx.broker._inventory_current_frame
        _need(old is snapshot.revision and window.source.inventory is old,
              'CURRENT_SHOP_INVENTORY_CHANGED')
        fresh = self.snapshot(pc_uid, now)
        _need(fresh == snapshot, 'CURRENT_SHOP_INVENTORY_CHANGED')
        if isinstance(proposal, Sale):
            _need(ctx.bindings.sale_item is not None, 'SALE_ITEM_SOURCE_UNAVAILABLE')
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(old)]
        before = {row[1]: dict(row) for row in rows}
        allocated = set(before)

        def grant(template, count):
            policy = ctx.bindings.item_policies.get(template)
            _need(policy is not None, 'GRANT_ITEM_POLICY_UNAVAILABLE')
            existing = next((row for row in rows if row[2] & 0xffffffff == template
                and (policy.grant_fields is None or all(row[n] == value
                     for n, value in policy.grant_fields.items() if n not in (1, 4)))), None)
            if policy.stackable and existing is not None:
                existing[4] += count
                _need(existing[4] <= 2_000_000_000, 'SHOP_STACK_LIMIT')
                return
            _need(policy.grant_fields is not None, 'GRANT_PRODUCER_REQUIRED')
            # Same LOCAL identifier policy as the existing kit ground pickup:
            # max current/this-batch identifier +1. No new UID persistence layer.
            uid = (max(allocated, default=0) + 1 if ctx.bindings.allocate_uid is None
                   else ctx.bindings.allocate_uid(ctx))
            _need(type(uid) is int and 0 < uid <= 0xffffffff and uid not in allocated,
                  'FRESH_OWNER_ITEM_UID_REQUIRED')
            allocated.add(uid)
            values = dict(policy.grant_fields)
            values.update({1: uid, 4: count})
            rows.append(values)

        if isinstance(proposal, Purchase):
            for grant_item in proposal.grants:
                grant(grant_item.item_id, grant_item.count)
        else:
            _need(isinstance(proposal, Sale), 'SHOP_PROPOSAL_REQUIRED')
            remove = dict(proposal.removals)
            for row in rows:
                row[4] -= remove.get(row[1], 0)
        wallet = next((row for row in rows if row[2] & 0xffffffff == 7), None)
        if wallet is None:
            if proposal.adena_after:
                grant(7, proposal.adena_after)
        else:
            wallet[4] = proposal.adena_after
        rows = [row for row in rows if row[4] > 0]
        new = inventory.build_kit_frame(rows)
        after = {row[1]: row for row in rows}
        frames = []
        for uid, previous in before.items():
            current = after.get(uid)
            if current is None:
                frames.append(item_transfer_protocol._remove_frame(item_transfer_protocol.RemoveInventory(uid)))
            elif current[4] != previous[4]:
                frames.append(inventory_update._encode(inventory_update._values({1: uid, 4: current[4]})))
        for row in rows:
            if row[1] not in before:
                frames.append(inventory.build_add(row))
        # Retire before CAS: an ambiguous store failure cannot authorize replay.
        window.source.retired = True
        ctx.state.window = None
        if new == old:
            return ()
        ctx.commit_attempted = True
        # A sold equipment anchor row moves to a remaining item in the same save.
        replace_kit = (getattr(ctx.broker, '_world_replace_kit', None)
                       or ctx.broker._inventory_store.replace_kit)
        _need(replace_kit(pc_uid, old, new, append=True) is True,
              'SHOP_PERSISTED_CHANGE_REQUIRED')
        ctx.broker._inventory_current_frame = new
        return tuple(frames)


class HostContext:
    """Duck-typed broker adapter; caller holds its existing operation/world lock.

    Set broker._world_handler_bindings once with prepare_host_bindings(). Send
    ctx.frames through the original _world_send; call mark_delivered only after
    that exact write/drain succeeds. State belongs to this selected writer/PC.
    """
    def __init__(self, broker, writer, row, game, operation_lock):
        self.broker, self.writer, self.row, self.game = broker, writer, row, game
        self.operation_lock = operation_lock
        self.world = broker._world
        self.pc_uid = broker._world_pcs[id(writer)][1]
        self.bindings = broker._world_handler_bindings
        self.wire, self.town = self.bindings.wire, self.bindings.town
        self.interaction_distance = self.bindings.interaction_distance
        identity = (writer, self.world, self.pc_uid, self.bindings)
        slot = row.get('_world_handler_state')
        if (slot is None or any(a is not b for a, b in zip(slot[0], identity[:2]))
                or slot[0][2] != self.pc_uid or slot[0][3] is not self.bindings):
            slot = (identity, HandlerState(), [])
            row['_world_handler_state'] = slot
        self.state, self.sources = slot[1:]
        self.frames, self.pending = [], []
        self.commit_attempted = False
        self.store = HostStore(self)
        self._owned()

    def _owned(self):
        bound = self.broker._world_pcs.get(id(self.writer))
        _need(bound is not None and bound[0] is self.writer and bound[1] == self.pc_uid
              and self.broker._world is self.world and self.row['writer'] is self.writer
              and self.row['operation_lock'] is self.operation_lock and self.operation_lock.locked()
              and self.broker._world_handler_bindings is self.bindings,
              'CURRENT_LOCKED_WORLD_OWNER_REQUIRED')

    def now(self):
        import time
        return time.monotonic()

    def send_frame(self, frame):
        _need(type(frame) is bytes, 'EXISTING_REPLY_FRAMES_REQUIRED')
        self.frames.append(frame)

    def current_source(self, source):
        self._owned()
        if not isinstance(source, _HostSource) or source not in self.sources or source.retired:
            return False
        if self.world.entities.resolve(source.ref) is None:
            return False
        if self.bindings.sources.get(source.owner.placement_key) is not source.owner:
            return False
        return source.owner.current()

    def _source(self, interaction, kind, inventory=None):
        owner = self.bindings.sources.get(interaction.npc.key)
        _need(owner is not None, 'CLASSIC_MENU_SOURCE_UNAVAILABLE')
        owner.current()
        # Preserve exact real target identity; never rewrite an old fixture UID.
        if isinstance(owner, HostNpcSource):
            _need(owner.resource.policy.spawn.uid & 0xffffffff == interaction.ref.uid,
                  'RESOURCE_CURRENT_NPC_UID_REQUIRED')
        source = _HostSource(owner, interaction.ref, kind, inventory)
        self.sources.append(source)
        self.pending.append(source)
        return source

    def begin_click(self):
        """Invalidate the preceding selection, including unsupported click attempts."""
        self._owned()
        for source in self.sources:
            source.retired = True
        self.sources.clear()
        self.state.clear()

    def dialogue_for(self, interaction, now):
        source = self._source(interaction, 'menu')
        from tools.local_original_session.world_shop_menu import MenuSource
        from tools.local_original_session.world_town_services import ServiceMenuSource
        if isinstance(source.owner, (MenuSource, ServiceMenuSource)):
            target = interaction.ref.uid
            target = target if target < (1 << 31) else target - (1 << 32)
            return Dialogue({1: target, 2: source.owner.stem.encode('utf-8')}, source)
        return Dialogue(dict(source.owner.resource.policy.response_fields), source)

    def service_action(self, interaction, menu, fields, now):
        from tools.local_original_session.world_town_services import ServiceMenuSource
        if not isinstance(menu.source.owner, ServiceMenuSource):
            return False
        _need(self.current_source(menu.source) and menu.source.delivered,
              'DRAINED_CURRENT_MENU_REQUIRED')
        self.broker._world_service_action(self, interaction, menu, fields, now)
        return True

    async def use_item(self, payload, now):
        self._owned()
        if await self.broker._world_enchant_use(self, payload, now):
            return True
        return self.broker._world_polymorph_use(self, payload, now)

    def warehouse_trade(self, payload, now):
        return self.broker._world_warehouse_trade(self, payload, now)

    def warehouse_close(self, payload, now):
        from tools.local_original_session.world_warehouse import close_body
        close_body(payload)
        self.row.pop('_world_warehouse_window', None)
        self.begin_click()
        return True

    def shop_action(self, interaction, menu, fields, now):
        source = menu.source
        _need(self.current_source(source) and source.delivered, 'DRAINED_CURRENT_MENU_REQUIRED')
        from tools.local_original_session.world_shop_menu import MenuSource, build_listing
        if isinstance(source.owner, MenuSource):
            # A fresh list context belongs to this selected connection, not the NPC.
            context = self.row.get('_world_shop_context', 0) + 1
            _need(context < (1 << 31), 'SHOP_CONTEXT_EXHAUSTED')
            self.row['_world_shop_context'] = context
            snapshot = self.store.snapshot(self.pc_uid, now)
            mode, value, rows = build_listing(source.owner, self.wire.lists, interaction,
                snapshot, context, fields[2].decode('utf-8'), item_policies=self.bindings.item_policies)
            listing_source = self._source(interaction, 'listing', self.broker._inventory_current_frame)
            return ShopWindow(mode, value, rows, listing_source)
        policy = source.owner.resource.policy
        _need(fields[2] == policy.command, 'RESOURCE_MENU_ACTION_MISMATCH')
        reply = policy.replies[0]
        value = reply.source.value
        _need(type(value) is self.wire.lists.Value, 'EXACT_SHOP_LIST_VALUE_REQUIRED')
        mode = BUY if value.kind == self.wire.lists.BUY else SELL if value.kind == self.wire.lists.SELL else None
        _need(mode is not None, 'SHOP_MODE_REQUIRED')
        if mode == BUY:
            for member in dict(value.fields).get(3, ()):
                row = dict(member.fields)
                key = source.owner.row_keys.get(row[1] & 0xffffffff)
                offer = self.town.data.shops.offers.get(key)
                _need(offer is not None and row[2] & 0xffffffff == offer.classic_item_id
                      and row[4] == offer.selling_price, 'SHOP_DISPLAY_CALCULATION_MISMATCH')
        listing_source = self._source(interaction, 'listing', self.broker._inventory_current_frame)
        return ShopWindow(mode, value, source.owner.row_keys, listing_source)

    def mark_delivered(self):
        self._owned()
        for source in self.pending:
            _need(self.current_source(source), 'DRAINED_SOURCE_CHANGED')
            source.delivered = True
        self.pending.clear()

    def move(self, payload, now):
        self._owned()
        return self.broker._world_move_for_handler(self.writer, self.row, self.game, payload, now, self)

    def transition(self, destination, now):
        self._owned()
        return self.broker._world_transition_for_handler(self.writer, self.row, self.game, destination, now, self)


# Broker-facing features: append one module name to register an independent file.
FEATURE_MODULES = (
    'world_feature_pet',
    'world_feature_session',
    'world_feature_kit',
    'world_feature_combat',
    'world_feature_reward',
    'world_feature_life',
    'world_feature_town',
    'world_feature_items',
    'world_feature_maps',
    'world_feature_dungeons',
    'world_feature_stats',
    'world_feature_alignment',
    'world_feature_companion',
    'world_feature_quest',
    'world_feature_magic',
    'world_feature_talkscroll',
    'world_feature_m5',
)

# Available lifecycle hooks. Empty lists are intentional extension points.
HOOK_NAMES = ('initialize', 'runtime_started', 'runtime_stopped', 'after_request',
              'after_enter', 'after_move', 'after_kill', 'after_death',
              'after_leave', 'prepare_attack', 'npc_hit', 'stats_changed')


@dataclass(frozen=True)
class FeatureRegistry:
    methods: Mapping
    realm_methods: Mapping
    frames: Mapping
    hooks: Mapping
    outgoing_opcodes: tuple


@lru_cache(maxsize=1)
def feature_registry():
    # Import/register once, before broker construction; no request-time discovery.
    from importlib import import_module
    methods, realm_methods, frames = {}, {}, {}
    hooks = {name: [] for name in HOOK_NAMES}
    outgoing = []
    for name in FEATURE_MODULES:
        feature = import_module('tools.local_original_session.' + name)
        for function in getattr(feature, 'METHODS', ()):
            methods[function.__name__] = function
        for function in getattr(feature, 'REALM_METHODS', ()):
            realm_methods[function.__name__] = function
        for opcode, names in getattr(feature, 'FRAMES', {}).items():
            frames.setdefault(opcode, []).extend(names)
        for hook, names in getattr(feature, 'HOOKS', {}).items():
            hooks.setdefault(hook, []).extend(names)
        outgoing.extend(getattr(feature, 'OUTGOING_OPCODES', ()))
    return FeatureRegistry(MappingProxyType(methods), MappingProxyType(realm_methods),
        MappingProxyType({op: tuple(names) for op, names in frames.items()}),
        MappingProxyType({hook: tuple(names) for hook, names in hooks.items()}), tuple(outgoing))


async def run_hooks(name, context, *args):
    result = None
    for method in feature_registry().hooks.get(name, ()):
        result = await _result(getattr(context, method)(*args))
    return result


def run_sync_hooks(name, context, *args):
    result = None
    for method in feature_registry().hooks.get(name, ()):
        result = getattr(context, method)(*args)
    return result
