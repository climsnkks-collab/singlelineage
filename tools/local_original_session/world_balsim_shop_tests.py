"""Balsim's LOCAL data/default dispatch/save flow; no socket or native client.

The shared fixture marks delivery itself. These development calls establish
backend connection and fresh-save behavior, never native input/render PASS.
"""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tools.local_original_session import equipment_store, inventory, world_handlers as h
from tools.local_original_session import world_feature_town as town_feature
from tools.local_original_session import world_shop_warehouse_tests as fixtures
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_handlers_tests import WIRES
from tools.local_original_session.world_shop import (
    InventoryItem, InventorySnapshot, calculate_purchase, calculate_sale, open_shop,
)
from tools.local_original_session.world_shop_menu import build_listing, load_menu_sources
from tools.local_original_session.world_terrain import default_terrain
from tools.local_original_session.world_town import TownConfig, TownNpcs, load_town


class BalsimDataTests(unittest.TestCase):
    """Store-independent data/list checks; registration here is explicit."""
    def setUp(self):
        self.town = TownNpcs(EntityRegistry(), load_town())
        self.source = next(s for s in load_menu_sources(self.town)
                           if s.placement_key == (70010, 60820))
        config = TownConfig(candidate_npc_ids={70010},
                            shop_sprite_candidates={self.source.placement_key})
        self.entity, = self.town.register(config)

    def test_fixed_terrain_and_local_sprite_leave_identity_unknown(self):
        self.assertEqual((self.entity.map_id, self.entity.x, self.entity.y),
                         (0, 32436, 32983))
        self.assertIs(default_terrain().can_stand(0, 32436, 32983), True)
        appearance = self.town.appearance(self.entity.uid)
        self.assertEqual(appearance.sprite_id, 118)
        self.assertIsNone(appearance.catalog_template_id)
        self.assertEqual(appearance.mapping_status, 'LOCAL_SHOP_EXPERIMENT_SPRITE_CANDIDATE')
        self.assertFalse(self.town.config.include_adjacent)
        self.assertEqual(self.town.register(replace(self.town.config,
                                                   disabled_npc_ids={70010})), ())
        self.assertIsNone(self.town.npc_for(self.entity.uid))

    def test_balsim_menu_lists_eleven_supported_products_and_preserves_five_unknowns(self):
        self.assertEqual(self.source.stem, 'balsim')
        interaction = self.town.route_click(self.entity.uid, player_map_id=0,
            player_x=32437, player_y=32983, max_distance=1)
        listing = interaction.shop_listing
        self.assertEqual({o.key[1] for o in listing.unavailable},
                         {20011, 20013, 20014, 20015, 20036})
        policies = {p.template_id: p for p in h._default_item_policies(self.town)}
        snapshot = h.TradeSnapshot(InventorySnapshot(1000, 1, 0, 10000), (), object())
        mode, value, rows = build_listing(self.source, WIRES.lists, interaction,
            snapshot, 43, 'buy', item_policies=policies)
        self.assertEqual((mode, len(rows)), (5, 11))
        self.assertEqual({listing_offer.key[1] for listing_offer in listing.offers},
                         {20006, 20043, 20089, 20096, 20114, 20122, 20147,
                          20229, 20231, 20239, 20242})
        fields = dict(value.fields)
        self.assertEqual(fields[2], 7)
        self.assertEqual([(dict(r.fields)[2], dict(r.fields)[4]) for r in fields[3]],
                         [(113, 60), (119, 10000), (117, 1200), (155, 7000),
                          (90, 200), (140, 5000), (102, 100), (99, 300),
                          (234, 1000), (100, 500), (98, 2000)])

    def test_existing_trade_calculators_use_balsim_prices(self):
        shops = self.town.data.shops
        offer = next(o for o in shops.offers.values()
                     if o.key[0] == 70010 and o.classic_item_id == 90)
        purchase = calculate_purchase(shops, 70010,
            InventorySnapshot(1000, 1, 0, 10000), ((offer.key, 1),))
        self.assertEqual((purchase.cost, purchase.adena_after), (200, 800))
        self.assertEqual([(g.item_id, g.count) for g in purchase.grants], [(90, 1)])
        sale = calculate_sale(shops, 70010, adena=800,
            items=(InventoryItem(123, 90, 1, 1),), selections=((123, 1),))
        self.assertEqual((sale.proceeds, sale.adena_after, sale.removals),
                         (100, 900, ((123, 1),)))
        policies = {p.template_id: p for p in h._default_item_policies(self.town)}
        frame = inventory.build_kit_frame([{**policies[90].grant_fields, 1: 123, 4: 1}])
        row, = inventory.validate_kit_frame(frame)
        broker = SimpleNamespace(_item_equipment_effect=None, _inventory_current_frame=frame)
        ctx = SimpleNamespace(broker=broker, pc_uid=1,
                              bindings=SimpleNamespace(item_policies=policies))
        self.assertFalse(town_feature._shop_sale_item(ctx, row).equipped)
        # The absence of a saved row is the same empty-slot policy as no owner.
        for state, worn in ((None, False),
                            (equipment_store.EquipmentState(1, 123, 90, 0, 1), False),
                            (equipment_store.EquipmentState(1, 123, 90, 123, 1), True),
                            (equipment_store.EquipmentState(1, 123, 90, 0, 1, ((9, 123),)), True)):
            broker._item_equipment_effect = SimpleNamespace(
                store=SimpleNamespace(restore=lambda uid, current, value=state: value))
            self.assertEqual(town_feature._shop_sale_item(ctx, row).equipped, worn)
        broker._item_equipment_effect = None
        changed = inventory.build_kit_frame([{**dict(row.raw_fields), 18: b'+1 variant'}])
        variant, = inventory.validate_kit_frame(changed)
        self.assertEqual(town_feature._shop_sale_item(ctx, variant).l1j_bless, 128)


class BalsimShopTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the actual default initializer/temporary store/HostContext fixture.
    asyncSetUp = fixtures.DefaultTownAssetTests.asyncSetUp
    fresh_store = fixtures.DefaultTownAssetTests.fresh_store
    kit = fixtures.DefaultTownAssetTests.kit
    context = fixtures.DefaultTownAssetTests.context
    saved = fixtures.DefaultTownAssetTests.saved
    open = fixtures.DefaultTownAssetTests.open
    close = fixtures.DefaultTownAssetTests.close

    def balsim(self):
        return next(e for e in self.entities
                    if self.broker._world.town.npc_for(e.uid)
                    and self.broker._world.town.npc_for(e.uid).key == (70010, 60820))

    async def test_default_placement_terrain_and_explicit_candidate_visual(self):
        entity = self.balsim()
        self.assertEqual((entity.map_id, entity.x, entity.y, entity.heading),
                         (0, 32436, 32983, 6))
        terrain = default_terrain()
        self.assertIs(terrain.can_stand(entity.map_id, entity.x, entity.y), True)
        for x, y in ((32435, 32983), (32437, 32983), (32436, 32982), (32436, 32984)):
            self.assertIs(terrain.can_stand(0, x, y), True)
        appearance = self.broker._world.town.appearance(entity.uid)
        self.assertEqual(appearance.sprite_id, 118)
        self.assertIsNone(appearance.catalog_template_id)
        self.assertIsNone(appearance.wire_f39)
        self.assertEqual(appearance.mapping_status, 'LOCAL_SHOP_EXPERIMENT_SPRITE_CANDIDATE')
        self.assertFalse(self.broker._world.town.config.include_adjacent)

    async def test_menu_supported_assortment_and_unresolved_rows_remain_untradeable(self):
        ctx = await self.open(70010, 'buy')
        self.assertEqual(ctx.state.menu.fields[2], b'balsim')
        listing = open_shop(self.broker._world.town.data.shops, 70010)
        self.assertEqual(len(listing.offers), 11)
        self.assertEqual({o.key[1] for o in listing.unavailable},
                         {20011, 20013, 20014, 20015, 20036})
        window = ctx.state.window
        self.assertEqual(len(window.rows), 11)
        self.assertEqual({self.broker._world.town.data.shops.offers[key].key[1]
                          for key in window.rows.values()},
                         {20006, 20043, 20089, 20096, 20114, 20122, 20147,
                          20229, 20231, 20239, 20242})
        self.assertEqual(dict(window.value.fields)[2], 7)
        for row in dict(window.value.fields)[3]:
            self.assertEqual(tuple(dict(row.fields)[n] for n in (6, 7, 8)), (0, 0, 0))

    async def test_buy_sell_new_uid_and_fresh_save_restore(self):
        self.assertIs(self.broker._world_handler_bindings.sale_item, town_feature._shop_sale_item)
        self.assertIsNone(self.broker._item_equipment_effect)
        self.assertFalse(self.profile.with_name('equipment.json').exists())
        before = self.store.restore(1)
        ctx = await self.open(70010, 'buy')
        window = ctx.state.window
        key = next(k for k, offer in window.rows.items()
                   if self.broker._world.town.data.shops.offers[offer].classic_item_id == 90)
        codec = ctx.wire.trade
        await h.dispatch(self.context(), h.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 5, (codec.Item(key, 1),), -2, -2)))
        purchased = self.store.restore(1)
        self.assertNotEqual(purchased, before)
        self.assertEqual(self.saved()[7][4], 800)
        helmet_uid = self.saved()[90][1]
        self.assertNotIn(helmet_uid, {r.identifier for r in inventory.validate_kit_frame(before)})
        self.assertEqual(self.fresh_store().restore(1), purchased)
        self.assertIsNone(self.broker._item_equipment_effect)
        self.assertFalse(self.profile.with_name('equipment.json').exists())
        await self.close()
        ctx = await self.open(70010, 'sell')
        window = ctx.state.window
        self.assertEqual([dict(r.fields) for r in dict(window.value.fields)[3]],
                         [{1: helmet_uid, 2: 100}])
        await h.dispatch(self.context(), h.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 6, (codec.Item(helmet_uid, 1),), -2, -2)))
        self.assertEqual(self.saved()[7][4], 900)
        self.assertNotIn(90, self.saved())
        self.assertEqual((self.saved()[14][4], self.saved()[15][4]), (10, 5))
        self.assertEqual(self.fresh_store().restore(1), self.store.restore(1))
        self.assertFalse(self.profile.with_name('equipment.json').exists())
        await self.close()


if __name__ == '__main__':
    unittest.main()
