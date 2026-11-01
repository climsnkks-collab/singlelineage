"""M2 town-service calculations; stdlib only, no runtime or persistence effects.

Future ``world_handlers`` connection API::

    data = load_town_services()                     # once at startup
    menu = teleport_destinations(data, l1j_npc_id)
    rest = calculate_inn_rest(data, 70012, adena=wallet, hp=hp, max_hp=mh,
                              mp=mp, max_mp=mm, price=explicit_local_price)
    trip = calculate_teleport(data, npc_id, action, adena=wallet, level=level)
    bank = calculate_deposit(data, player_rows, warehouse_rows,
                             selections, level=level)
    bank = calculate_withdrawal(data, player_rows, warehouse_rows,
                                selections, level=level, max_weight=capacity)

These frozen results are proposals, never commits/UIDs/wire row references.
The handler resolves the actual NPC UID/lifetime/map/range and selected menu
generation, authenticates ownership/account, maps received list keys to current
UIDs, obtains exact item eligibility/variant/weight, and calls under the existing
owner lock. Commit Adena + HP/MP, Adena + position, or both inventories + fee
together with the existing revision/CAS/once transaction. Publish only after
commit; preserve committed partial outcomes on IO failure. Recompute a stale
proposal from a fresh snapshot, never apply/recharge an old proposal blindly.
``wallet`` means the balance of that same inventory's canonical Adena stack,
never a separate currency ledger. Banking derives it from item7 exactly once;
adena_after includes both currency transferred and withdrawal fees.

Storage PROPOSAL ONLY: a separate warehouse sidecar may mirror inventory_store's
kit envelope ``{'version':1,'inventories':[{'uid':character_uid,'frame':hex}]}``;
frame is the original canonical kit/add collection, preserving every raw field.
Do not place warehouse rows in the player's inventory.json, overwrite v2 account
custody, or treat this per-character envelope as L1J account-wide storage. The
storage owner must decide account scope/locking/atomic recovery and empty-store
representation (current kit codec requires >=1 item). No codec/store is imported
here. TransferLine retains the input item metadata; the owner preserves its raw
canonical fields while changing only proven UID/count fields with the real codec.
Full transfers, splits and merges require the existing UID/custody owner; a
``new_slot`` is merely a plan-local ordinal, never an allocated item UID.

L1J policies and exact references are in data/m2/town_services.json. The saved
L1J inn action is a stub: immediate full recovery is a separate requested LOCAL
calculation, with no invented default fee. Single-key LOCAL rental/return and
nearby recovery now belong to world_feature_town/world_inn. The native numeric
input panel and interior-map entry remain unresolved; this calculator is separate.
Healer71030's 5A rule is NOT an inn rule. Teleport
IDs/coordinates are L1J candidates, not verified Classic menu/map transitions.
Warehouse uses configured personal150 slots, player180, level>=5, free deposit,
30A per distinct withdrawn UID, before-fee slot/weight checks. Unlike L1J's
sequential partial commits this LOCAL batch is all-or-nothing, aggregates repeated
UID selections and requires all fees from already-carried Adena. Weight uses
explicit item raw weights (1/1000), the L1J +1 check and rounded weight240 <240;
weight-limit rate is fixed x1. Caller must supply effective weight/capacity for
the selected policy. Stack compatibility is exact (item_id, variant), never a
guess from name. Protected/equipped/controlled deposits refuse. No request path
reads files, hashes sources, waits, sends packets, mutates inputs or issues IDs.
Historical warehouse-business-v1-final remains a separate proven source family;
its packet/native/account/3-tile success is not inherited by this pure module.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

M2_DATA_DIR = Path(__file__).resolve().parent / 'data' / 'm2'
MAX_AMOUNT = 2_000_000_000
ADENA_ID = 7


class TownServiceError(ValueError):
    """Stable calculation refusal; no side effects have occurred."""


@dataclass(frozen=True, slots=True)
class ServiceMenuSource:
    """Startup-resolved native stems/actions; NPC correspondence remains LOCAL."""
    placement_key: tuple[int, int]
    stem: str
    pages: Mapping[str, tuple[str, ...]]
    service_kind: str | None = None

    def current(self):
        return True


def load_service_menus(town, *, warehouse_experiment=True) -> tuple[ServiceMenuSource, ...]:
    document = json.loads((M2_DATA_DIR / 'npc_menus.json').read_text(encoding='utf-8'))
    resources = document['resources']
    result = []
    # Only these native resources exist. Missing zeno/telefire are not sent.
    # run403 exact case and native action literals. The other inn inputs and
    # Lucas tax inquiry are retained as known inputs, not invented services.
    # Gludin uses the same preserved native inn page. Mainland pages are
    # contributed by the M5 town_setup owner after its placements are loaded.
    selections = ((70012, 'inn', ('inn',)), (70019, 'inn', ('inn',)),
                  (50015, 'lucas1', ('lucas1', 'lucas2')))
    if warehouse_experiment:
        # Native storage stem/actions exist; Dorin identity/sprite is LOCAL only.
        selections += ((60001, 'storage', ('storage',)),)
    for npc_id, initial, stems in selections:
        pages = {}
        for stem in stems:
            resource = resources[stem]
            if (resource['current_catalog_present'] is True
                    and resource['current_catalog_comparison'] == 'identical'):
                pages[resource['f2_candidate']] = tuple(a['literal'] for a in resource['actions'])
        if initial not in pages:
            continue
        for key, npc in town.data.placements.items():
            if npc.npc_id == npc_id and npc.spawn['count'] > 0:
                result.append(ServiceMenuSource(key, initial, MappingProxyType(pages)))
    return tuple(result)


def _int(value, low=0, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise TownServiceError('INVALID_INTEGER')
    return value


@dataclass(frozen=True, slots=True)
class TeleportDestination:
    npc_id: int
    action: str
    name: str
    map_id: int
    x: int
    y: int
    heading: int
    price: int
    max_level_exclusive: int | None
    source_ref: str


@dataclass(frozen=True, slots=True)
class TownServices:
    teleports: Mapping[tuple[int, str], TeleportDestination]
    teleporter_ids: frozenset[int]
    inn_ids: frozenset[int]
    warehouse_slots: int
    player_slots: int
    withdrawal_fee: int
    minimum_level: int
    inn_price: int | None = None


def load_town_services(directory: str | Path = M2_DATA_DIR, *, experimental: bool = False) -> TownServices:
    """Load the attributed table once; no reference-checkout runtime dependency."""
    raw = json.loads((Path(directory) / 'town_services.json').read_text(encoding='utf-8'))
    routes = {}
    for row in (*raw['teleporters'], *(raw.get('experimental_teleporters', ()) if experimental else ())):
        for route in row['destinations']:
            entry = TeleportDestination(row['l1j_npc_id'], route['action'], route['name'],
                route['map_id'], route['x'], route['y'], route['heading'], route['price'],
                route['max_level_exclusive'], route['source_ref'])
            key = (entry.npc_id, entry.action)
            if key in routes:
                raise TownServiceError('DUPLICATE_DESTINATION')
            for value in (entry.npc_id, entry.map_id, entry.x, entry.y, entry.price):
                _int(value)
            _int(entry.heading, 0, 7)
            if entry.max_level_exclusive is not None:
                _int(entry.max_level_exclusive, 1)
            routes[key] = entry
    bank = raw['warehouse']['policy']
    for key in ('slots', 'player_slots', 'withdrawal_fee', 'minimum_level'):
        _int(bank[key], 1)
    return TownServices(MappingProxyType(routes),
        frozenset(r['l1j_npc_id'] for r in raw['teleporters']),
        frozenset(r['l1j_npc_id'] for r in raw['inns']),
        bank['slots'], bank['player_slots'], bank['withdrawal_fee'], bank['minimum_level'],
        raw['inns'][0]['price'])


@dataclass(frozen=True, slots=True)
class InnRest:
    npc_id: int
    cost: int
    adena_after: int
    hp_after: int
    mp_after: int


def calculate_inn_rest(data: TownServices, npc_id: int, *, adena: int,
                       hp: int, max_hp: int, mp: int, max_mp: int,
                       price: int | None = None) -> InnRest:
    """LOCAL instant full recovery for a living player; fee must be explicit."""
    _int(npc_id, 1)
    if npc_id not in data.inn_ids:
        raise TownServiceError('UNKNOWN_INN')
    if price is None:
        raise TownServiceError('INN_PRICE_UNRESOLVED')
    _int(price, 1, MAX_AMOUNT)
    _int(adena, 0, MAX_AMOUNT)
    _int(max_hp, 1)
    _int(max_mp)
    _int(hp, 1, max_hp)
    _int(mp, 0, max_mp)
    if adena < price:
        raise TownServiceError('INSUFFICIENT_ADENA')
    return InnRest(npc_id, price, adena - price, max_hp, max_mp)


def teleport_destinations(data: TownServices, npc_id: int) -> tuple[TeleportDestination, ...]:
    """A known but unresolved teleporter (Keith) returns no fabricated routes."""
    _int(npc_id, 1)
    if npc_id not in data.teleporter_ids:
        raise TownServiceError('UNKNOWN_TELEPORTER')
    return tuple(route for key, route in data.teleports.items() if key[0] == npc_id)


@dataclass(frozen=True, slots=True)
class TeleportProposal:
    destination: TeleportDestination
    cost: int
    adena_after: int


def calculate_teleport(data: TownServices, npc_id: int, action: str, *,
                       adena: int, level: int) -> TeleportProposal:
    teleport_destinations(data, npc_id)
    _int(adena, 0, MAX_AMOUNT)
    _int(level, 1)
    if type(action) is not str or (npc_id, action) not in data.teleports:
        raise TownServiceError('UNKNOWN_DESTINATION')
    destination = data.teleports[npc_id, action]
    if destination.max_level_exclusive is not None and level >= destination.max_level_exclusive:
        raise TownServiceError('DESTINATION_LEVEL_LIMIT')
    if adena < destination.price:
        raise TownServiceError('INSUFFICIENT_ADENA')
    return TeleportProposal(destination, destination.price, adena - destination.price)


@dataclass(frozen=True, slots=True)
class ServiceItem:
    uid: int
    item_id: int  # Already mapped Classic template; never an L1J item ID.
    count: int
    stackable: bool
    variant: bytes  # Owner's exact proven stack compatibility key.
    weight_milli: int
    deposit_allowed: bool
    equipped: bool = False
    controlled: bool = False  # Active pet/doll etc.; supplied by current owner.


@dataclass(frozen=True, slots=True)
class TransferLine:
    item: ServiceItem  # Original immutable item; not a final canonical row.
    count: int
    destination_uid: int | None
    new_slot: int | None  # Same ordinal means same future stack; NOT a UID.


@dataclass(frozen=True, slots=True)
class WarehouseProposal:
    direction: str
    fee: int
    fee_debits: tuple[tuple[int, int], ...]
    adena_before: int
    adena_after: int  # Includes deposited/withdrawn Adena as well as fees.
    transfers: tuple[TransferLine, ...]
    player_slots_after: int
    warehouse_slots_after: int


def _rows(items: Iterable[ServiceItem], limit: int) -> dict[int, ServiceItem]:
    rows = {}
    identities = set()
    for item in items:
        if type(item) is not ServiceItem:
            raise TownServiceError('INVALID_ITEM')
        _int(item.uid, 1, 0xffffffff)
        _int(item.item_id, 1)
        _int(item.count, 1, MAX_AMOUNT)
        _int(item.weight_milli)
        if (any(type(value) is not bool for value in
                (item.stackable, item.deposit_allowed, item.equipped, item.controlled))
                or type(item.variant) is not bytes or item.uid in rows
                or (not item.stackable and item.count != 1)):
            raise TownServiceError('INVALID_ITEM')
        identity = (item.item_id, item.variant)
        if item.stackable and identity in identities:
            raise TownServiceError('AMBIGUOUS_STACK')
        if item.stackable:
            identities.add(identity)
        rows[item.uid] = item
    if len(rows) > limit:
        raise TownServiceError('SLOT_LIMIT')
    # Currency is one explicit canonical stack, not a second mutable wallet.
    coins = [row for row in rows.values() if row.item_id == ADENA_ID]
    if len(coins) > 1 or (coins and (not coins[0].stackable or coins[0].weight_milli != 0)):
        raise TownServiceError('INVALID_ADENA_STACK')
    return rows


def _wallet(rows):
    return next((row.count for row in rows.values() if row.item_id == ADENA_ID), 0)


def _remove(rows, uid, count):
    item = rows[uid]
    if count == item.count:
        del rows[uid]
    else:
        rows[uid] = replace(item, count=item.count - count)


def _target(rows, item):
    if item.stackable:
        for key, row in rows.items():
            if (row.item_id, row.variant) == (item.item_id, item.variant):
                if (row.stackable, row.weight_milli) != (True, item.weight_milli):
                    raise TownServiceError('INCONSISTENT_ITEM_METADATA')
                return key
        if item.item_id == ADENA_ID and any(r.item_id == ADENA_ID for r in rows.values()):
            raise TownServiceError('INCOMPATIBLE_ADENA_STACK')
    return None


def _bank(data, player_items, warehouse_items, selections, *, level, max_weight, withdraw):
    _int(level, 1)
    if level < data.minimum_level:
        raise TownServiceError('WAREHOUSE_LEVEL_REQUIRED')
    player = _rows(player_items, data.player_slots)
    warehouse = _rows(warehouse_items, data.warehouse_slots)
    if player.keys() & warehouse.keys():
        raise TownServiceError('DUPLICATE_UID')
    if withdraw:
        _int(max_weight, 1)
    source, destination = (warehouse, player) if withdraw else (player, warehouse)
    selected = {}
    for uid, count in selections:
        _int(uid, 1, 0xffffffff)
        selected[uid] = selected.get(uid, 0) + _int(count, 1, MAX_AMOUNT)
    for uid, count in selected.items():
        if uid not in source:
            raise TownServiceError('ITEM_NOT_OWNED')
        item = source[uid]
        if count > item.count:
            raise TownServiceError('INSUFFICIENT_ITEMS')
        if not withdraw and (not item.deposit_allowed or item.equipped or item.controlled):
            raise TownServiceError('ITEM_NOT_DEPOSITABLE')
    before = _wallet(player)
    fee = len(selected) * data.withdrawal_fee if withdraw else 0
    if before < fee:
        raise TownServiceError('INSUFFICIENT_ADENA')
    lines, debits = [], []
    for uid, count in selected.items():
        item = source[uid]
        target = _target(destination, item)
        limit = data.player_slots if withdraw else data.warehouse_slots
        if target is None and len(destination) >= limit:
            raise TownServiceError('SLOT_LIMIT')
        if target is not None and destination[target].count + count > MAX_AMOUNT:
            raise TownServiceError('STACK_LIMIT')
        if withdraw:
            # L1PcInventory checks capacity before paying this entry's fee.
            # L1ItemInstance.getWeight: nonzero raw weight has minimum1 per
            # existing stack; genuinely zero-weight items (Adena) stay zero.
            weight = sum(max(r.weight_milli * r.count // 1000, 1)
                         if r.weight_milli else 0 for r in player.values())
            checked_weight = weight + item.weight_milli * count // 1000 + 1
            # Java Math.round(240 * weight / maxWeight), positive exact ratio.
            weight240 = (checked_weight * 480 + max_weight) // (2 * max_weight)
            if weight240 >= 240:
                raise TownServiceError('OVERWEIGHT')
            coin = next(row for row in player.values() if row.item_id == ADENA_ID)
            debits.append((coin.uid, data.withdrawal_fee))
            _remove(player, coin.uid, data.withdrawal_fee)
            # Paying the last coins can remove the previous merge target.
            target = _target(destination, item)
        _remove(source, uid, count)
        if target is None:
            # Negative dictionary keys are internal plan slots only.
            target = -(len(lines) + 1)
            destination[target] = replace(item, count=count)
        else:
            destination[target] = replace(destination[target], count=destination[target].count + count)
        lines.append(TransferLine(item, count, target if target > 0 else None,
                                  -target - 1 if target < 0 else None))
    combined = {}
    for uid, amount in debits:
        combined[uid] = combined.get(uid, 0) + amount
    return WarehouseProposal('withdraw' if withdraw else 'deposit', fee,
        tuple(combined.items()), before, _wallet(player), tuple(lines), len(player), len(warehouse))


def calculate_deposit(data: TownServices, player_items: Iterable[ServiceItem],
                      warehouse_items: Iterable[ServiceItem],
                      selections: Iterable[tuple[int, int]], *, level: int) -> WarehouseProposal:
    """Free personal deposit proposal; equipped/protected/controlled items refuse."""
    return _bank(data, player_items, warehouse_items, selections,
                 level=level, max_weight=None, withdraw=False)


def calculate_withdrawal(data: TownServices, player_items: Iterable[ServiceItem],
                         warehouse_items: Iterable[ServiceItem],
                         selections: Iterable[tuple[int, int]], *, level: int,
                         max_weight: int) -> WarehouseProposal:
    """30A per selected UID, paid from carried coins; entire batch or refusal."""
    return _bank(data, player_items, warehouse_items, selections,
                 level=level, max_weight=max_weight, withdraw=True)
