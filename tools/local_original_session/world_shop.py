"""M2 shop data and pure trade calculations (stdlib only).

Load once with ``load_shops()``, call ``open_shop(data, l1j_npc_id)`` on the
caller's NPC-click route, then ``calculate_purchase`` / ``calculate_sale``.
Results are proposals: the existing inventory owner must apply the debit,
grants/removals and save together. This module issues no UID, packet or credit.

M2_SHOP_DATA.md selects *candidate* Classic item IDs; these calculations use
them as explicit LOCAL backend policy, at DB prices x1 and zero tax. NPC keys
are L1J IDs, NOT live NPC UIDs or confirmed Classic templates. OfferKey is a
source-row identity, NOT a wire row key. Unselected item mappings stay visible
in ShopListing.unavailable and cannot be traded. The two input tables cover
sale rows plus selected buyback-only reference rows. Item weight and stacking
come from game_data items/items_ext metadata by selected Classic ID.
L1J bless is retained as L1J metadata, never converted into a Classic grade.

References under D:/SingleLineageRef/l1j-en-classic/src/l1j/server/server/:
* datatables/ShopTable.java:80-91: -1 unavailable, zero valid, pack0 -> 1.
* model/shop/L1ShopBuyOrderList.java:55-100: price per pack, exact raw weight,
  stackable delivery / one inventory slot per nonstackable delivered item.
* model/shop/L1Shop.java:127-158: 0..2G total, funds, pre-debit weight and
  180 slots. This SHOP path permits weight == maximum; the different
  L1PcInventory.checkAddItem +1/weight240 pickup rule is not used here.
* model/shop/L1Shop.java:73-88,107-122: no equipped/enchant!=0/bless>=128
  resale; unit buyback = int(purchasing_price / pack_count) at x1.
* model/shop/L1Shop.java:301-332: removed count * assessed unit price;
  payout clamped to 2G. model/L1Inventory.java:44,95: stack maximum 2G.

LOCAL batch policy aggregates duplicate selections and rejects insufficient
stock or wallet/stack overflow as a whole, without L1J's partial removals or
Java overflow. stack_counts must describe compatible candidate item stacks
(including variant compatibility already established by the inventory owner).
current_weight/max_weight use whole burden units; item weights are in
1/1000 units. SHOP checks weight before spending Adena and frees no wallet
slot in this calculation. No state-after inventory weight is manufactured.

Packet reuse under work/local_original_session/implementation-4/shop-quest/
(do not import its native/broker graph here):
* dialogue-contract/shop-list-wire/shop_list_wire.py:Value/encode/decode:
  BUY4E48 and SELL4EE7 outer f1:i32(context), f2:i32, f3:repeated rows.
  BUY row f1:i32(key), f2:i32(CommonItem), f3:i32(icon), f4:u32(price),
  f5:bytes(token), required f6:i32/f7:u64/f8:i64 (semantics unknown).
  SELL row f1:i32, f2:u32; keys require the existing listing/UID mapping.
* buy-row-content-v1/buy_row_content.py:build_buy constructs the existing BUY
  reply/OfferListing from explicit current catalog/offer/row keys and unknown
  6/7/8 inputs; this numeric listing does not supply those wire values.
* dialogue-contract/dialogue_wire.py:encode_haction_normal/decode_haction_normal
  handle HACTION4ED4. Existing haction-list-ingress-v1/haction_list_ingress.py
  Feature publishes the list and detached trade listing (BUYmode5/SELLmode6).
* dialogue-contract/trade-request-wire/trade_request_wire.py:
  Item/Request/encode_normal/decode_normal handle CS_BUYSELL_REQ4ED1,
  f1:context u32, f2:mode5/6, repeated f3:{f1:key u32,f2:quantity u64},
  f4/f5:explicit i32 coordinates. Normal quantities are positive i32.
  shop-first-adena-sale-v38/trade_ingress.py:aggregate consumes that listing;
  canonical inventory owner remains responsible for debit/credit/commit.
SHOP396-v8 (integration-1/shop-human-manual-serial396-v8/API.md) only fixes
decoder trailer length, not the catalog, economy or unknown wire producers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from tools.local_original_session.game_data import load_items

M2_DATA_DIR = Path(__file__).resolve().parent / 'data' / 'm2'
MAX_ITEMS = 180
MAX_AMOUNT = 2_000_000_000
CLASSIC_ADENA_ID = 7  # MAPPING_SCOPE.md; no wallet/UID is created here.
OfferKey = tuple[int, int, int]  # L1J npc_id, item_id, order_id.

# Previously supported selected items with no game_data definition. Preserve
# this attributed compatibility subset only; new items use game_data metadata.
# Classic ID: (raw weight, stackable), from db/l1jdb_m10.sql etcitem.
_LEGACY_ITEM_RULES = MappingProxyType({
    243: (0, True),     # L1J40310, l1jdb:16764 letter
    357: (0, True),     # L1J40311, l1jdb:16765 clan letter
    343: (8000, False), # L1J40315, l1jdb:16769 pet whistle
    348: (4000, True),  # L1J40317, l1jdb:16771 whetstone
})


class ShopError(ValueError):
    """A trade cannot be proposed; str(error) is a stable reason code."""


@dataclass(frozen=True, slots=True)
class ShopNpc:
    npc_id: int
    name: str
    map_id: int
    x: int
    y: int
    spawn_count: int
    classic_npc_id: int | None
    sprite_candidate: int | None
    mapping_status: str
    source_ref: str
    spawn_ref: str


@dataclass(frozen=True, slots=True)
class ShopOffer:
    key: OfferKey
    classic_item_id: int | None
    name_token: str | None
    name_ko: str | None
    icon_id: int | None
    selling_price: int  # Per pack, NPC -> player; -1 unavailable.
    purchasing_price: int  # Per pack, player -> NPC; -1 unavailable.
    pack_count: int  # Effective count, at least 1.
    weight_milli: int | None
    stackable: bool | None
    l1j_bless: int | None
    mapping_status: str
    source_ref: str
    item_source_ref: str | None
    classic_source_ref: str | None

    @property
    def calculable(self) -> bool:
        return (self.classic_item_id is not None and self.weight_milli is not None
                and self.stackable is not None and self.l1j_bless is not None)

    @property
    def buyback_unit_price(self) -> int | None:
        if self.purchasing_price < 0:
            return None
        return self.purchasing_price // self.pack_count


@dataclass(frozen=True, slots=True)
class ShopData:
    npcs: Mapping[int, ShopNpc]
    offers: Mapping[OfferKey, ShopOffer]


@dataclass(frozen=True, slots=True)
class ShopListing:
    npc: ShopNpc
    offers: tuple[ShopOffer, ...]
    unavailable: tuple[ShopOffer, ...]  # Unresolved sale identity/metadata.
    buyback_only: tuple[ShopOffer, ...] = ()  # Includes unresolved reference rows.


@dataclass(frozen=True, slots=True)
class InventorySnapshot:
    adena: int
    slots_used: int
    current_weight: int
    max_weight: int
    stack_counts: Mapping[int, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ItemGrant:
    offer_key: OfferKey
    item_id: int  # Candidate Classic ID; no live UID.
    count: int  # One per grant for nonstackables, one combined stack otherwise.
    l1j_bless: int  # Not a Classic grade.


@dataclass(frozen=True, slots=True)
class Purchase:
    cost: int
    adena_after: int
    grants: tuple[ItemGrant, ...]
    slots_after: int
    added_weight_milli: int


@dataclass(frozen=True, slots=True)
class InventoryItem:
    uid: int
    item_id: int
    count: int
    l1j_bless: int  # Caller must supply an established L1J-policy equivalent.
    equipped: bool = False
    enchant_level: int = 0


@dataclass(frozen=True, slots=True)
class Sale:
    proceeds: int
    adena_after: int
    removals: tuple[tuple[int, int], ...]  # Existing UID, quantity.


def _integer(value: int, low: int, high: int | None = None) -> int:
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ShopError('INVALID_INTEGER')
    return value


def load_shops(directory: str | Path = M2_DATA_DIR) -> ShopData:
    """Read regional shops and item metadata once; preserve unresolved rows."""
    directory = Path(directory)
    npc_rows = json.loads((directory / 'shop_npcs.json').read_text(encoding='utf-8'))['npcs']
    sale_rows = json.loads((directory / 'shop_sales.json').read_text(encoding='utf-8'))['sales']
    reference = directory / 'shop_buyback_reference.json'
    if reference.is_file():
        # Some regional tables already include these rows in sales. The sale
        # table remains authoritative for the same source-row key.
        sale_keys = {(r['npc_id'], r['item_id'], r['order_id']) for r in sale_rows}
        sale_rows += [r for r in json.loads(reference.read_text(encoding='utf-8'))['rows']
                      if (r['npc_id'], r['item_id'], r['order_id']) not in sale_keys]
    items = load_items()
    if (directory / 'items.json').is_file():
        # Match game_data regional merge: shared M1 definitions take priority.
        items = dict(load_items(directory)) | dict(items)
    npcs = {}
    for row in npc_rows:
        spawn = row['spawn']
        sprite = row.get('same_number_classic_sprite_candidate')
        npc = ShopNpc(row['l1j_npc_id'], row['l1j_name'], spawn['mapid'],
                      spawn['locx'], spawn['locy'], spawn['count'],
                      row['selected_classic_npc_id'],
                      sprite['sprite_id'] if sprite else None,
                      row['mapping_status'], row['l1j_npc_ref'], row['spawn_ref'])
        if npc.npc_id in npcs:
            raise ValueError('Duplicate shop NPC')
        npcs[npc.npc_id] = npc
    offers = {}
    for row in sale_rows:
        key = (row['npc_id'], row['item_id'], row['order_id'])
        selected = row.get('selected_classic_item_id')
        candidates = [c for c in row.get('classic_item_candidates', ()) if c['id'] == selected]
        if selected is not None and len(candidates) != 1:
            raise ValueError('Selected Classic item has no unique candidate')
        candidate = candidates[0] if candidates else {}
        definition = items.get(selected)
        if definition is None:
            weight, stackable = _LEGACY_ITEM_RULES.get(selected, (None, None))
        else:
            weight, stackable = definition.weight, definition.stackable
        pack = row['pack_count']
        _integer(pack, 0)
        pack = pack or 1
        _integer(row['selling_price'], -1)
        _integer(row['purchasing_price'], -1)
        if key in offers or key[0] not in npcs:
            raise ValueError('Duplicate offer or unknown shop NPC')
        offers[key] = ShopOffer(
            key, selected, candidate.get('name_token'), candidate.get('name_ko'),
            candidate.get('icon_f5'), row['selling_price'], row['purchasing_price'],
            pack, weight, stackable, row.get('l1j_bless'),
            row.get('mapping_status', 'unresolved'), row['source_ref'],
            row.get('l1j_item_ref'), candidate.get('source_ref'))
    return ShopData(MappingProxyType(npcs), MappingProxyType(offers))


def _npc(data: ShopData, npc_id: int) -> ShopNpc:
    _integer(npc_id, 1)
    try:
        return data.npcs[npc_id]
    except KeyError:
        raise ShopError('UNKNOWN_SHOP') from None


def open_shop(data: ShopData, npc_id: int) -> ShopListing:
    """Calculate the sale-list DATA for a caller-resolved NPC click.

    The caller supplies the live UID -> L1J NPC mapping and checks map/range and
    lifetime. No synthetic spawn, menu context or unknown BUY fields are issued.
    """
    npc = _npc(data, npc_id)
    rows = sorted((o for o in data.offers.values()
                   if o.key[0] == npc_id and o.selling_price >= 0),
                  key=lambda o: o.key[2]) if npc.spawn_count > 0 else []
    buyback = sorted((o for o in data.offers.values()
                      if o.key[0] == npc_id and o.selling_price < 0),
                     key=lambda o: o.key[2]) if npc.spawn_count > 0 else []
    return ShopListing(npc, tuple(o for o in rows if o.calculable),
                       tuple(o for o in rows if not o.calculable), tuple(buyback))


def _offer(data: ShopData, npc_id: int, key: OfferKey) -> ShopOffer:
    if not isinstance(key, tuple) or len(key) != 3:
        raise ShopError('UNKNOWN_OFFER')
    for value in key:
        _integer(value, 0)
    if key[0] != npc_id or key not in data.offers:
        raise ShopError('UNKNOWN_OFFER')
    offer = data.offers[key]
    if not offer.calculable:
        raise ShopError('ITEM_MAPPING_UNRESOLVED')
    return offer


def calculate_purchase(data: ShopData, npc_id: int, inventory: InventorySnapshot,
                       orders: Iterable[tuple[OfferKey, int]]) -> Purchase:
    """Buy pack counts; return a debit and grants without mutating inventory.

    Example: ``[(potion.key, 3)]`` costs 111 at Pandora's DB price37, grants
    three item14 with the selected metadata raw weight. Empty selection is a no-op.
    """
    if _npc(data, npc_id).spawn_count <= 0:
        raise ShopError('NPC_INACTIVE')
    _integer(inventory.adena, 0, MAX_AMOUNT)
    _integer(inventory.slots_used, 0, MAX_ITEMS)
    _integer(inventory.current_weight, 0)
    _integer(inventory.max_weight, 1)
    for item_id, count in inventory.stack_counts.items():
        _integer(item_id, 1)
        _integer(count, 1, MAX_AMOUNT)
    if len(inventory.stack_counts) > inventory.slots_used:
        raise ShopError('INVALID_INVENTORY')
    quantities: dict[OfferKey, int] = {}
    for key, packs in orders:
        _offer(data, npc_id, key)
        quantities[key] = quantities.get(key, 0) + _integer(packs, 1, MAX_AMOUNT)
    if not quantities:
        return Purchase(0, inventory.adena, (), inventory.slots_used, 0)
    total = weight = 0
    slots = inventory.slots_used
    stacks = dict(inventory.stack_counts)
    deliveries = []
    for key, packs in quantities.items():
        offer = _offer(data, npc_id, key)
        if offer.selling_price < 0:
            raise ShopError('SHOP_DOES_NOT_SELL')
        count = packs * offer.pack_count
        _integer(count, 1, MAX_AMOUNT)
        total += offer.selling_price * packs
        weight += offer.weight_milli * count
        if offer.stackable:
            previous = stacks.get(offer.classic_item_id, 0)
            if previous + count > MAX_AMOUNT:
                raise ShopError('STACK_LIMIT')
            slots += int(previous == 0)
            stacks[offer.classic_item_id] = previous + count
        else:
            slots += count
        deliveries.append((offer, count))
    if total > MAX_AMOUNT:
        raise ShopError('PRICE_LIMIT')
    if total > inventory.adena:
        raise ShopError('INSUFFICIENT_ADENA')
    if inventory.current_weight * 1000 + weight > inventory.max_weight * 1000:
        raise ShopError('OVERWEIGHT')
    if slots > MAX_ITEMS:
        raise ShopError('ITEM_LIMIT')
    # Construct nonstackable grants only after the bounded 180-slot check.
    grants = []
    for offer, count in deliveries:
        if offer.stackable:
            grants.append(ItemGrant(offer.key, offer.classic_item_id, count, offer.l1j_bless))
        else:
            grants.extend(ItemGrant(offer.key, offer.classic_item_id, 1, offer.l1j_bless)
                          for _ in range(count))
    return Purchase(total, inventory.adena - total, tuple(grants), slots, weight)


def calculate_sale(data: ShopData, npc_id: int, *, adena: int,
                   items: Iterable[InventoryItem],
                   selections: Iterable[tuple[int, int]]) -> Sale:
    """Sell existing UID quantities using this shop's assessed per-item price.

    Ownership, actual removal, Adena credit and persistence belong to the caller.
    Unknown Classic grades cannot be guessed: l1j_bless is explicit input.
    """
    if _npc(data, npc_id).spawn_count <= 0:
        raise ShopError('NPC_INACTIVE')
    _integer(adena, 0, MAX_AMOUNT)
    owned = {}
    for item in items:
        _integer(item.uid, 1)
        _integer(item.item_id, 1)
        _integer(item.count, 1, MAX_AMOUNT)
        _integer(item.l1j_bless, 0)
        _integer(item.enchant_level, -(1 << 31), (1 << 31) - 1)
        if type(item.equipped) is not bool or item.uid in owned:
            raise ShopError('INVALID_INVENTORY')
        owned[item.uid] = item
    counts: dict[int, int] = {}
    for uid, count in selections:
        _integer(uid, 1)
        counts[uid] = counts.get(uid, 0) + _integer(count, 1, MAX_AMOUNT)
    total = 0
    for uid, count in counts.items():
        if uid not in owned:
            raise ShopError('ITEM_NOT_OWNED')
        item = owned[uid]
        if count > item.count:
            raise ShopError('INSUFFICIENT_ITEMS')
        if item.equipped or item.enchant_level != 0 or item.l1j_bless >= 128:
            raise ShopError('ITEM_NOT_PURCHASEABLE')
        matches = [o for o in data.offers.values()
                   if o.key[0] == npc_id and o.classic_item_id == item.item_id
                   and o.purchasing_price >= 0 and o.calculable]
        if not matches:
            raise ShopError('SHOP_DOES_NOT_BUY')
        if len(matches) != 1:
            raise ShopError('AMBIGUOUS_BUYBACK')
        total += matches[0].buyback_unit_price * count
    proceeds = min(total, MAX_AMOUNT)
    if adena + proceeds > MAX_AMOUNT:
        raise ShopError('ADENA_LIMIT')
    return Sale(proceeds, adena + proceeds, tuple(counts.items()))
