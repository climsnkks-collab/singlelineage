"""M2 shop arithmetic/data tests only; no game, server, native graph or save."""
from dataclasses import replace
from types import MappingProxyType
import unittest

from tools.local_original_session.world_shop import (
    MAX_AMOUNT, InventoryItem, InventorySnapshot, ShopError,
    calculate_purchase, calculate_sale, load_shops, open_shop,
)


class WorldShopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_shops()
        cls.potion = next(o for o in cls.data.offers.values()
                          if o.key[0] == 70014 and o.classic_item_id == 14)
        cls.dagger = next(o for o in cls.data.offers.values()
                          if o.key[0] == 70014 and o.classic_item_id == 41)
        cls.jacket = next(o for o in cls.data.offers.values()
                          if o.key[0] == 70014 and o.classic_item_id == 103)

    def inventory(self, **changes):
        return replace(InventorySnapshot(10_000, 1, 0, 1800), **changes)

    def buy(self, orders, *, inventory=None, data=None, npc=70014):
        return calculate_purchase(self.data if data is None else data, npc,
                                  self.inventory() if inventory is None else inventory,
                                  orders)

    def sell(self, selections, *, adena=100, items=None, data=None, npc=70014):
        if items is None:
            items = (InventoryItem(101, 14, 5, 1),)
        return calculate_sale(self.data if data is None else data, npc,
                              adena=adena, items=items, selections=selections)

    def changed_offer(self, offer, **changes):
        offer = replace(offer, **changes)
        offers = dict(self.data.offers)
        offers[offer.key] = offer
        return replace(self.data, offers=MappingProxyType(offers))

    def fails(self, code, fn, *args, **kwargs):
        with self.assertRaisesRegex(ShopError, '^' + code + '$'):
            fn(*args, **kwargs)

    def test_real_loader_keeps_candidates_unknowns_and_provenance(self):
        self.assertEqual((len(self.data.npcs), len(self.data.offers)), (21, 84))
        self.assertEqual(sum(o.calculable for o in self.data.offers.values()), 43)
        self.assertEqual(self.potion.pack_count, 1)  # Raw JSON pack_count0.
        self.assertEqual((self.potion.weight_milli, self.potion.stackable), (3900, True))
        self.assertEqual((self.potion.selling_price, self.potion.buyback_unit_price), (37, 19))
        self.assertEqual(self.potion.item_source_ref, 'l1jdb:16464')
        self.assertTrue(self.potion.classic_source_ref.startswith('native-dump:'))
        with self.assertRaises(TypeError):
            self.data.offers[self.potion.key] = self.dagger

    def test_npc_click_listing_has_classic_icons_and_retains_unknowns(self):
        listing = open_shop(self.data, 70014)
        self.assertEqual((len(listing.offers), len(listing.unavailable)), (42, 13))
        self.assertEqual((listing.npc.map_id, listing.npc.x, listing.npc.y),
                         (0, 32645, 32951))
        self.assertIsNone(listing.npc.classic_npc_id)
        self.assertEqual(listing.npc.sprite_candidate, 98)
        self.assertEqual(self.jacket.icon_id, 62)  # L1J1196 must not leak to display.
        self.assertEqual((self.potion.name_token, self.potion.icon_id), ('$237', 80))
        self.assertEqual([o.key[2] for o in listing.offers],
                         sorted(o.key[2] for o in listing.offers))
        self.assertTrue(all(not o.calculable for o in listing.unavailable))

    def test_other_shops_empty_and_inactive_shops(self):
        self.assertEqual(len(open_shop(self.data, 70011).offers), 1)
        self.assertEqual((len(open_shop(self.data, 70013).offers),
                          len(open_shop(self.data, 70013).unavailable)), (0, 26))
        no_sales = next(n for n in self.data.npcs.values()
                        if not any(k[0] == n.npc_id for k in self.data.offers))
        self.assertEqual(open_shop(self.data, no_sales.npc_id).offers, ())
        inactive = next(n for n in self.data.npcs.values() if n.spawn_count == 0)
        self.assertEqual(open_shop(self.data, inactive.npc_id).offers, ())
        self.fails('NPC_INACTIVE', self.buy, [], npc=inactive.npc_id)
        self.fails('NPC_INACTIVE', self.sell, [], npc=inactive.npc_id)
        self.fails('UNKNOWN_SHOP', open_shop, self.data, 999999)

    def test_buy_potions_returns_debit_and_no_mutation(self):
        counts = {14: 5}
        inv = self.inventory(adena=111, slots_used=2, stack_counts=counts)
        result = self.buy([(self.potion.key, 3)], inventory=inv)
        self.assertEqual((result.cost, result.adena_after, result.slots_after,
                          result.added_weight_milli), (111, 0, 2, 11700))
        self.assertEqual([(g.item_id, g.count, g.l1j_bless) for g in result.grants],
                         [(14, 3, 1)])
        self.assertEqual((inv.adena, inv.stack_counts, counts), (111, {14: 5}, {14: 5}))
        # Recalculation is deliberately not a commit/deduplication service.
        self.assertEqual(result, self.buy([(self.potion.key, 3)], inventory=inv))

    def test_mixed_buy_and_separate_nonstackable_grants(self):
        result = self.buy([(self.potion.key, 3), (self.dagger.key, 2)])
        self.assertEqual((result.cost, result.adena_after, result.slots_after,
                          result.added_weight_milli), (127, 9873, 4, 31700))
        self.assertEqual([(g.item_id, g.count) for g in result.grants],
                         [(14, 3), (41, 1), (41, 1)])

    def test_pack_price_is_not_rounded_to_unit_buy_price(self):
        # Synthetic pack10 policy to exercise the real L1J arrow-style1/10
        # arithmetic without selecting the unresolved Classic arrow variant.
        data = self.changed_offer(self.potion, pack_count=10, selling_price=1,
                                  purchasing_price=19)
        result = self.buy([(self.potion.key, 3)], data=data)
        self.assertEqual((result.cost, result.grants[0].count,
                          result.added_weight_milli), (3, 30, 117000))
        sale = self.sell([(101, 3)], data=data)
        self.assertEqual(sale.proceeds, 3)  # floor(19/10)*3, NOT floor(19*3/10).

    def test_nonstackable_packs_take_one_slot_per_delivered_item(self):
        data = self.changed_offer(self.dagger, pack_count=3)
        result = self.buy([(self.dagger.key, 2)], data=data)
        self.assertEqual((result.cost, result.slots_after, len(result.grants)), (16, 7, 6))
        self.assertTrue(all(g.count == 1 for g in result.grants))

    def test_duplicate_buy_rows_are_aggregated(self):
        result = self.buy([(self.potion.key, 2), (self.potion.key, 3)])
        self.assertEqual((result.cost, result.slots_after, len(result.grants),
                          result.grants[0].count), (185, 2, 1, 5))

    def test_funds_and_total_price_limit(self):
        self.fails('INSUFFICIENT_ADENA', self.buy, [(self.potion.key, 3)],
                   inventory=self.inventory(adena=110))
        self.fails('PRICE_LIMIT', self.buy, [(self.potion.key, MAX_AMOUNT)],
                   inventory=self.inventory(adena=MAX_AMOUNT))

    def test_full_inventory_allows_existing_stack_only(self):
        inv = self.inventory(slots_used=180, stack_counts={14: 5})
        self.assertEqual(self.buy([(self.potion.key, 1)], inventory=inv).slots_after, 180)
        self.fails('ITEM_LIMIT', self.buy, [(self.dagger.key, 1)], inventory=inv)
        self.fails('ITEM_LIMIT', self.buy, [(self.potion.key, 1)],
                   inventory=replace(inv, stack_counts={}))

    def test_180_slot_boundary_and_debit_does_not_free_wallet_slot(self):
        inv = self.inventory(slots_used=178, adena=16)
        self.assertEqual(self.buy([(self.dagger.key, 2)], inventory=inv).slots_after, 180)
        self.fails('ITEM_LIMIT', self.buy, [(self.dagger.key, 2)],
                   inventory=replace(inv, slots_used=179))

    def test_stack_amount_limit_across_repeated_selections(self):
        inv = self.inventory(slots_used=2, stack_counts={14: MAX_AMOUNT - 1})
        self.assertEqual(self.buy([(self.potion.key, 1)], inventory=inv).grants[0].count, 1)
        self.fails('STACK_LIMIT', self.buy,
                   [(self.potion.key, 1), (self.potion.key, 1)], inventory=inv)

    def test_shop_weight_maximum_is_inclusive_before_debit(self):
        inv = self.inventory(current_weight=1790)
        self.assertEqual(self.buy([(self.dagger.key, 1)], inventory=inv).added_weight_milli,
                         10000)
        self.fails('OVERWEIGHT', self.buy, [(self.dagger.key, 1)],
                   inventory=replace(inv, current_weight=1791))
        self.assertEqual(self.buy([(self.potion.key, 1)],
                                  inventory=replace(inv, current_weight=1796)).cost, 37)
        self.fails('OVERWEIGHT', self.buy, [(self.potion.key, 1)],
                   inventory=replace(inv, current_weight=1797, adena=37))

    def test_unresolved_rows_and_wrong_shop_cannot_be_bought(self):
        unresolved = open_shop(self.data, 70014).unavailable[0]
        self.fails('ITEM_MAPPING_UNRESOLVED', self.buy, [(unresolved.key, 1)])
        self.fails('UNKNOWN_OFFER', self.buy, [(self.potion.key, 1)], npc=70011)
        self.fails('UNKNOWN_OFFER', self.buy, [((70014, 999999, 0), 1)])
        self.fails('SHOP_DOES_NOT_SELL', self.buy, [(self.potion.key, 1)],
                   data=self.changed_offer(self.potion, selling_price=-1))

    def test_zero_prices_are_valid_in_both_directions(self):
        data = self.changed_offer(self.potion, selling_price=0)
        self.assertEqual(self.buy([(self.potion.key, 3)], data=data,
                                  inventory=self.inventory(adena=0)).cost, 0)
        result = self.sell([(202, 1)], items=(InventoryItem(202, 103, 1, 1),))
        self.assertEqual((result.proceeds, result.adena_after, result.removals),
                         (0, 100, ((202, 1),)))

    def test_nonpositive_and_noninteger_quantities(self):
        for count in (0, -1, True, 1.5, '1'):
            with self.subTest(count=count):
                self.fails('INVALID_INTEGER', self.buy, [(self.potion.key, count)])
                self.fails('INVALID_INTEGER', self.sell, [(101, count)])

    def test_empty_selections_are_noop(self):
        buy = self.buy([])
        self.assertEqual((buy.cost, buy.adena_after, buy.grants, buy.slots_after),
                         (0, 10_000, (), 1))
        sale = self.sell([])
        self.assertEqual((sale.proceeds, sale.adena_after, sale.removals), (0, 100, ()))

    def test_sale_returns_existing_uid_removals_without_mutation(self):
        items = (InventoryItem(101, 14, 5, 1), InventoryItem(102, 41, 1, 1))
        result = self.sell([(101, 3), (102, 1)], items=items)
        self.assertEqual((result.proceeds, result.adena_after, result.removals),
                         (61, 161, ((101, 3), (102, 1))))
        self.assertEqual((items[0].count, items[1].count), (5, 1))

    def test_duplicate_sale_uid_is_aggregated_before_stock_check(self):
        result = self.sell([(101, 2), (101, 3)])
        self.assertEqual((result.proceeds, result.removals), (95, ((101, 5),)))
        self.fails('INSUFFICIENT_ITEMS', self.sell, [(101, 3), (101, 3)])
        self.fails('ITEM_NOT_OWNED', self.sell, [(999, 1)])

    def test_l1j_sale_excludes_equipped_enchanted_and_sealed(self):
        item = InventoryItem(101, 14, 5, 1)
        for changed in (replace(item, equipped=True), replace(item, enchant_level=1),
                        replace(item, enchant_level=-1), replace(item, l1j_bless=128)):
            with self.subTest(item=changed):
                self.fails('ITEM_NOT_PURCHASEABLE', self.sell, [(101, 1)], items=(changed,))
        self.assertEqual(self.sell([(101, 1)], items=(replace(item, l1j_bless=127),)).proceeds, 19)

    def test_sale_uses_only_this_shop_and_loaded_buyback_subset(self):
        self.fails('SHOP_DOES_NOT_BUY', self.sell, [(101, 1)], npc=70011)
        self.fails('SHOP_DOES_NOT_BUY', self.sell, [(101, 1)],
                   data=self.changed_offer(self.potion, purchasing_price=-1))
        self.fails('SHOP_DOES_NOT_BUY', self.sell, [(101, 1)],
                   items=(InventoryItem(101, 999999, 5, 1),))

    def test_sale_2g_payout_clamp_and_wallet_overflow(self):
        items = (InventoryItem(101, 14, MAX_AMOUNT, 1),)
        result = self.sell([(101, MAX_AMOUNT)], adena=0, items=items)
        self.assertEqual((result.proceeds, result.adena_after), (MAX_AMOUNT, MAX_AMOUNT))
        self.fails('ADENA_LIMIT', self.sell, [(101, MAX_AMOUNT)], adena=1, items=items)
        self.assertEqual(self.sell([(101, 1)], adena=MAX_AMOUNT - 19).adena_after, MAX_AMOUNT)
        self.fails('ADENA_LIMIT', self.sell, [(101, 1)], adena=MAX_AMOUNT - 18)

    def test_sale_cannot_duplicate_inventory_uid(self):
        item = InventoryItem(101, 14, 5, 1)
        self.fails('INVALID_INVENTORY', self.sell, [(101, 1)], items=(item, item))

    def test_buy_then_sell_is_a_numeric_round_trip_only(self):
        purchase = self.buy([(self.potion.key, 3)], inventory=self.inventory(adena=111))
        # Test-owned example UID: no runtime item is created or applied.
        item = InventoryItem(9001, purchase.grants[0].item_id, 3,
                             purchase.grants[0].l1j_bless)
        sale = self.sell([(9001, 3)], adena=purchase.adena_after, items=(item,))
        self.assertEqual((purchase.cost, sale.proceeds, sale.adena_after), (111, 57, 57))


if __name__ == '__main__':
    unittest.main(verbosity=2)
