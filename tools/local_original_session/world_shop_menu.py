"""Startup-prepared M2 merchant menus and pure current-inventory shop lists.

The JSON records resource/action evidence, not official NPC menu conditions.
Prices, packs and resale rules remain world_shop's attributed LOCAL policy.
run382 establishes exact UML stems/action literals; run388 establishes SELL
unit prices. run394 follow-up establishes the Adena icon lookup and required
BUY f6/7/8 presence; the LOCAL policy supplies 7/0/0/0.

Load sources once at host startup. The default ShopExperiment supplies LOCAL
Adena operands; explicit None disables list creation. No request-path file
read, source scan, UID issuance, transport or inventory mutation occurs here.
The host owns current NPC/session, publication, inventory CAS and persistence.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from tools.local_original_session.world_shop import (
    M2_DATA_DIR, OfferKey, ShopData, ShopError, calculate_sale,
)

if TYPE_CHECKING:
    from tools.local_original_session.world_handlers import KitItemPolicy, TradeSnapshot
    from tools.local_original_session.world_town import TownInteraction, TownNpcs


class MenuError(ValueError):
    """Stable LOCAL refusal code; no official-server equivalence implied."""


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise MenuError(code)


def _in_range(value, low, high):
    return type(value) is int and low <= value <= high


@dataclass(frozen=True, slots=True)
class ShopExperiment:
    """LOCAL operands, never a claim about official-server supply values.

    outer2=7 resolves Adena's Common_5.png icon. Required BUY f6/7/8 are
    present zero; no stock/pack/flags meaning is inferred for these fields.
    """
    outer2: int = 7
    buy_f6: int = 0
    buy_f7: int = 0
    buy_f8: int = 0

    def __post_init__(self):
        _need(_in_range(self.outer2, 1, (1 << 31) - 1), 'SHOP_EXPERIMENT_OUTER2_RANGE')
        _need(_in_range(self.buy_f6, -(1 << 31), (1 << 31) - 1),
              'SHOP_EXPERIMENT_F6_RANGE')
        _need(_in_range(self.buy_f7, 0, (1 << 64) - 1), 'SHOP_EXPERIMENT_F7_RANGE')
        _need(_in_range(self.buy_f8, -(1 << 63), (1 << 63) - 1),
              'SHOP_EXPERIMENT_F8_RANGE')


def parse_experiment(value: str | None) -> ShopExperiment | None:
    """Default to LOCAL Adena; 0/off disable, or accept explicit operands."""
    if value is None:
        return ShopExperiment()
    _need(type(value) is str, 'SHOP_EXPERIMENT_STRING_REQUIRED')
    value = value.strip()
    if value.lower() in ('0', 'off'):
        return None
    if value.lower() in ('', '1', 'adena'):
        return ShopExperiment()
    parts = value.split(',')
    _need(len(parts) == 4, 'SHOP_EXPERIMENT_FOUR_INTEGERS_REQUIRED')
    try:
        operands = tuple(int(part.strip(), 10) for part in parts)
    except ValueError:
        raise MenuError('SHOP_EXPERIMENT_FOUR_INTEGERS_REQUIRED') from None
    return ShopExperiment(*operands)


@dataclass(frozen=True, slots=True)
class MenuSource:
    placement_key: tuple[int, int]
    stem: str
    actions: tuple[str, ...]
    experiment: ShopExperiment | None = ShopExperiment()
    descriptions: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def current(self) -> bool:
        """Immutable startup data; the host separately validates live ownership."""
        return True


def load_menu_sources(town: TownNpcs, experiment: ShopExperiment | None = ShopExperiment()
                      ) -> tuple[MenuSource, ...]:
    """Read npc_menus.json once at startup; select evidenced merchant resources.

    This installs three LOCAL candidate NPC-to-resource correspondences, not a
    claim that the official server issues those menus under every condition.
    Missing resource merchants (pump1), refusal menus, unrelated shared menus,
    nonmerchant services stay unused. Unmapped reference items cannot trade.
    """
    _need(experiment is None or type(experiment) is ShopExperiment,
          'SHOP_EXPERIMENT_REQUIRED')
    document = json.loads((M2_DATA_DIR / 'npc_menus.json').read_text(encoding='utf-8'))
    resources = document['resources']
    result = []
    for npc in document['npcs']:
        if not npc['shop']['has_l1j_product_rows']:
            continue
        declared = {}
        for action in npc['shop']['open_action_literals']:
            declared.setdefault(action['resource_ref'], set()).add(action['literal'])
        candidates = []
        for resource_ref, literals in declared.items():
            resource = resources.get(resource_ref)
            if (resource is None or resource['current_catalog_present'] is not True
                    or resource.get('current_catalog_comparison') != 'identical'):
                continue
            actions = tuple(dict.fromkeys(a['literal'] for a in resource['actions']))
            if not {'buy', 'sell'} <= literals.intersection(actions):
                continue
            stem = resource.get('f2_candidate')
            if type(stem) is str and stem and not stem.endswith('.uml'):
                candidates.append((stem, actions))
        _need(len(candidates) <= 1, 'SHOP_MENU_RESOURCE_AMBIGUOUS')
        if not candidates:
            continue
        stem, actions = candidates[0]
        for spawn in npc['placements']:
            key = (npc['l1j_npc_id'], spawn['id'])
            placement = town.data.placements.get(key)
            if (placement is not None and placement.spawn['count'] > 0
                    and placement.shop_row is not None
                    and placement.shop_row['shop_row_count'] > 0):
                result.append(MenuSource(key, stem, actions, experiment))
    return tuple(result)


def _buy_rows(codec, listing, snapshot, policies, experiment, descriptions):
    _need(isinstance(policies, Mapping), 'GRANT_ITEM_POLICY_UNAVAILABLE')
    rows, rowmap = [], {}
    for offer in listing.offers:
        if not (offer.calculable
                and _in_range(offer.classic_item_id, 1, (1 << 31) - 1)
                and _in_range(offer.icon_id, 0, (1 << 31) - 1)
                and _in_range(offer.selling_price, 0, (1 << 32) - 1)
                and type(offer.name_token) is str and offer.name_token):
            continue
        policy = policies.get(offer.classic_item_id)
        if (policy is None or policy.template_id != offer.classic_item_id
                or policy.stackable != offer.stackable):
            continue
        prototype = policy.grant_fields
        if prototype is None:
            # The existing owner permits a prototype-less compatible stack
            # change only when that stack already exists in this snapshot.
            if not (policy.stackable
                    and snapshot.inventory.stack_counts.get(offer.classic_item_id, 0) > 0):
                continue
        elif (prototype.get(2, 0) & 0xffffffff != offer.classic_item_id
              or prototype.get(7) != offer.icon_id):
            continue
        rowkey = len(rows) + 1  # A new listing-local key, never source order_id.
        fields = (
            (1, rowkey), (2, offer.classic_item_id), (3, offer.icon_id),
            (4, offer.selling_price), (5, offer.name_token.encode('utf-8')),
            (6, experiment.buy_f6), (7, experiment.buy_f7), (8, experiment.buy_f8))
        children = tuple(codec.Value('ItemDescription', ((1, token), (2, value)))
                         for token, value in descriptions.get(offer.classic_item_id, ()))
        if children:
            fields += ((9, children),)
        rows.append(codec.Value('BuyListItem', fields))
        rowmap[rowkey] = offer.key
    return tuple(rows), MappingProxyType(rowmap)


def _sell_rows(codec, listing, snapshot):
    # run388: SELL has only the owned Inventory UID and unit price. The same
    # Inventory ItemEntity receives its description at initial 0964/0977;
    # there is no confirmed SELL description field to populate here.
    # Reuse the actual trade calculator, including its ambiguous-buyback rule.
    # Buyback-only rows keep selling_price=-1 and never enter the BUY list.
    data = ShopData(MappingProxyType({listing.npc.npc_id: listing.npc}),
                    MappingProxyType({offer.key: offer
                                      for offer in (*listing.offers, *listing.unavailable,
                                                    *listing.buyback_only)}))
    calculate_sale(data, listing.npc.npc_id, adena=snapshot.inventory.adena,
                   items=snapshot.items, selections=())
    rows, rowmap = [], {}
    for item in snapshot.items:
        # run388: Inventory lookup sign-extends row.f1. Do not rewrite this UID
        # or pretend low32 echo proves a valid sign-extended Inventory lookup.
        if item.uid > 0x7fffffff:
            continue
        try:
            calculate_sale(data, listing.npc.npc_id, adena=0, items=snapshot.items,
                           selections=((item.uid, 1),))
        except ShopError as error:
            if str(error) in ('ITEM_NOT_PURCHASEABLE', 'SHOP_DOES_NOT_BUY',
                              'AMBIGUOUS_BUYBACK'):
                continue
            raise
        offer = next(offer for offer in data.offers.values()
                     if offer.calculable and offer.classic_item_id == item.item_id
                     and offer.purchasing_price >= 0)
        price = offer.buyback_unit_price
        if not _in_range(price, 0, (1 << 32) - 1):
            continue
        rows.append(codec.Value('SellListItem', ((1, item.uid), (2, price))))
        rowmap[item.uid] = item.uid
    return tuple(rows), MappingProxyType(rowmap)


def build_listing(source: MenuSource, wire_lists, interaction: TownInteraction,
                  snapshot: TradeSnapshot, context: int, action: str, *,
                  item_policies: Mapping[int, KitItemPolicy] | None = None
                  ) -> tuple[int, object, Mapping[int, OfferKey | int]]:
    """Return (BUY5/SELL6, exact existing codec.Value, current row mapping).

    The host supplies a freshly owned interaction and TradeSnapshot, and
    binds the returned mapping to its existing publication/lifetime owner.
    BUY policies must be startup-prepared HostBindings.item_policies. Lists
    describe available products/items; funds, capacity and selected quantities
    are evaluated by the existing trade calculator when confirmation arrives.
    """
    _need(type(source) is MenuSource, 'PREPARED_MENU_SOURCE_REQUIRED')
    _need(source.experiment is not None, 'SHOP_EXPERIMENT_REQUIRED')
    _need(source.placement_key == interaction.npc.key, 'SHOP_MENU_PLACEMENT_MISMATCH')
    _need(action in ('buy', 'sell') and action in source.actions,
          'SHOP_MENU_ACTION_UNAVAILABLE')
    _need(_in_range(context, -(1 << 31), (1 << 31) - 1), 'SHOP_LIST_CONTEXT_I32_REQUIRED')
    listing = interaction.shop_listing
    _need(listing is not None and listing.npc.npc_id == interaction.npc.npc_id,
          'SHOP_ACTION_OWNER_UNAVAILABLE')
    if action == 'buy':
        rows, rowmap = _buy_rows(wire_lists, listing, snapshot, item_policies,
                                 source.experiment, source.descriptions)
        mode, kind = 5, wire_lists.BUY
    else:
        rows, rowmap = _sell_rows(wire_lists, listing, snapshot)
        mode, kind = 6, wire_lists.SELL
    value = wire_lists.Value(kind, ((1, context), (2, source.experiment.outer2), (3, rows)))
    return mode, value, rowmap
