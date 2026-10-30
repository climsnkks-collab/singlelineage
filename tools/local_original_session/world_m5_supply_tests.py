"""Supply-base registration and default trade/store paths; no client or socket.

These development dispatch fixtures do not establish native click/render PASS.
"""
import asyncio
import json
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, world_bridge, world_feature_m5 as m5
from tools.local_original_session import world_feature_town, world_handlers as h
from tools.local_original_session import world_shop, world_town
from tools.local_original_session import world_shop_warehouse_tests as defaults
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_shop_menu import ShopExperiment
from tools.local_original_session.world_town_services import load_town_services
from tools.local_original_session.world_terrain import WorldTerrain


class SupplyDataTests(unittest.TestCase):
    def test_supply_regions_are_actual_l1j_regional_return_destinations(self):
        doc = json.loads((m5.M5_DATA_DIR / 'towns.json').read_text(encoding='utf8'))
        self.assertEqual({r['town_id'] for r in doc['supply_bases']},
                         {'silver_knight', 'fire_farmer'})
        policy = m5.load_m5_policy()
        self.assertEqual(tuple(t['town_id'] for t in policy.towns),
                         ('gludin', 'kent', 'windawood', 'giran', 'oren', 'heine'))
        for x, y, town_id in ((33096, 33402, 2), (32738, 32448, 4)):
            candidates = policy.return_candidates(4, x, y, 1)
            self.assertEqual(candidates, policy.getback.towns[town_id])
            self.assertIn(policy.return_for(4, x, y, 1), candidates)
        self.assertIsNone(policy.return_for(0, 33096, 33402))

    def test_source_shop_rows_preserve_prices_and_defer_unsupported_individually(self):
        doc = json.loads((m5.M5_DATA_DIR / 'shop_sales.json').read_text(encoding='utf8'))
        shops = world_shop.load_shops(m5.M5_DATA_DIR)
        for npc_id, count, refs in ((70073, 32, (31931, 31962)),
                                     (70074, 964, (31963, 32926)),
                                     (70078, 25, (32928, 32952))):
            rows = [r for r in doc['sales'] if r['npc_id'] == npc_id]
            self.assertEqual(len(rows), count)
            self.assertEqual({r['source_ref'] for r in rows},
                             {f'l1jdb:{i}' for i in range(refs[0], refs[1] + 1)})
            for row in rows:
                raw = row['l1j_source_row']
                offer = shops.offers[npc_id, row['item_id'], row['order_id']]
                self.assertEqual((offer.selling_price, offer.purchasing_price, offer.pack_count),
                    (int(raw['selling_price']), int(raw['purchasing_price']), int(raw['pack_count']) or 1))
                if row['selected_classic_item_id'] is None:
                    self.assertFalse(offer.calculable)
                    self.assertTrue(row['deferred_reason'])
            listing = world_shop.open_shop(shops, npc_id)
            if npc_id == 70078:
                self.assertTrue(all(not o.calculable for o in shops.offers.values() if o.key[0] == npc_id))
                self.assertEqual(len(listing.unavailable), 25)
            else:
                self.assertTrue(any(o.calculable for o in listing.offers))


class SupplyFixture:
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.configure_m5()

    def configure_m5(self):
        self.broker._world_map_exp = 2
        self.broker._world.terrain = WorldTerrain.load(map_ids=(0, 4))
        self.broker._world_registry = h.build_registry((world_feature_town, m5))
        ctx = world_bridge.Context(self.broker)
        for function in m5.METHODS:
            setattr(self.broker, function.__name__, MethodType(function, ctx))
        with patch.dict('os.environ', {'SL_EXPERIMENT_M5': '1'}):
            configured = m5._m5_town_setup(ctx, world_town.TownSetup(
                self.broker._world.town, self.broker._world_services,
                tuple(self.broker._world_handler_bindings.sources.values()),
                self.broker._world_shop_experiment))
        self.broker._world_services = configured.services
        ctx.configure_town(configured.town, configured.sources)
        self.position.map_id = 4
        self.entities.move(1, 4, 33096, 33401)

    async def open(self, npc_id, action):
        return await super().open({70014: self.merchant_id, 60001: self.warehouse_id}.get(npc_id, npc_id), action)


class SupplyClickTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_five_live_placements_have_source_coordinates_visible_appearance_and_click_menus(self):
        # Registration and dialogue need no save fixture. The six inherited
        # transfer/save tests below still require real writable temporary saves.
        terrain = WorldTerrain.load(map_ids=(0, 4))
        entities = EntityRegistry()
        old = world_town.TownNpcs(entities,
            world_town.with_gludin_town(world_town.load_town()),
            world_town.TownConfig(), passable=terrain.can_stand)
        setup_ctx = SimpleNamespace(_world_map_exp=2,
            world=SimpleNamespace(entities=entities, terrain=terrain))
        with patch.dict('os.environ', {'SL_EXPERIMENT_M5': '1'}):
            configured = m5._m5_town_setup(setup_ctx, world_town.TownSetup(
                old, load_town_services(), (), ShopExperiment()))
        self.addCleanup(configured.town.close)
        entities.add(Kind.PC, 4, 33096, 33401, uid=1)
        writer, lock = object(), asyncio.Lock()
        await lock.acquire()
        self.addCleanup(lock.release)
        broker = SimpleNamespace(_world=setup_ctx.world,
            _world_registry=h.build_registry(()), _world_pcs={id(writer): (writer, 1)},
            _world_handler_bindings=h.prepare_host_bindings(configured.town,
                sources=configured.sources), _inventory_current_frame=None)
        row = dict(writer=writer, operation_lock=lock)
        expected = {70073: (33096, 33402, 4), 70074: (33097, 33385, 4),
                    60024: (33079, 33395, 5), 70078: (32738, 32448, 6),
                    60027: (32746, 32444, 5)}
        for npc_id, (x, y, heading) in expected.items():
            with self.subTest(npc_id=npc_id):
                entity = next(e for e in entities if configured.town.npc_for(e.uid)
                    and configured.town.npc_for(e.uid).npc_id == npc_id)
                self.assertEqual((entity.map_id, entity.x, entity.y, entity.heading), (4, x, y, heading))
                self.assertIs(terrain.can_stand(4, x, y), True)
                appearance = configured.town.appearance(entity.uid)
                self.assertIsNotNone(appearance.sprite_id)
                entities.move(1, 4, x, y)
                host = h.HostContext(broker, writer, row, True, lock)
                await h.dispatch(host, h.CLICK, host.wire.click.encode_request(entity.uid))
                self.assertEqual(host.state.menu.fields[2],
                    {70073: b'glen', 70074: b'mellin', 60024: b'storage',
                     70078: b'orcm1', 60027: b'storage'}[npc_id])
                host.mark_delivered()


class SilverKnightSupplyTests(SupplyFixture, defaults.DefaultTownAssetTests):
    merchant_id = 70073
    warehouse_id = 60024


class FireFarmerSupplyTests(SupplyFixture, defaults.DefaultTownAssetTests):
    # Mellin exercises the second Silver Knight merchant's broad buyback path;
    # Fire Farmer Orcm has only unsupported fireworks, preserved unavailable.
    merchant_id = 70074
    warehouse_id = 60027


class RestoredMerchantTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the default initializer and real temporary save, then the existing
    # M5 setup. No NPC or trade state is injected to bypass registration.
    fresh_store = defaults.DefaultTownAssetTests.fresh_store
    kit = defaults.DefaultTownAssetTests.kit
    context = defaults.DefaultTownAssetTests.context
    saved = defaults.DefaultTownAssetTests.saved
    open = defaults.DefaultTownAssetTests.open
    close = defaults.DefaultTownAssetTests.close

    async def asyncSetUp(self):
        await defaults.DefaultTownAssetTests.asyncSetUp(self)
        SupplyFixture.configure_m5(self)

    async def round_trip(self, npc_id, stem, template, buy_price, sell_price):
        entity = next(e for e in self.entities
            if self.broker._world.town.npc_for(e.uid)
            and self.broker._world.town.npc_for(e.uid).npc_id == npc_id)
        self.assertIs(self.broker._world.terrain.can_stand(
            entity.map_id, entity.x, entity.y), True)
        self.assertIsNotNone(self.broker._world.town.appearance(entity.uid).sprite_id)
        before = self.store.restore(1)
        before_rows = {r.identifier: dict(r.raw_fields)
                       for r in inventory.validate_kit_frame(before)}
        ctx = await self.open(npc_id, 'buy')
        self.assertEqual(ctx.state.menu.fields[2], stem)
        window, codec = ctx.state.window, ctx.wire.trade
        key = next(k for k, offer in window.rows.items()
            if self.broker._world.town.data.shops.offers[offer].classic_item_id == template)
        listed = next(dict(r.fields) for r in dict(window.value.fields)[3]
                      if dict(r.fields)[1] == key)
        self.assertEqual((listed[2], listed[4]), (template, buy_price))
        await h.dispatch(self.context(), h.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 5, (codec.Item(key, 1),), 0, 0)))
        purchased = self.store.restore(1)
        self.assertEqual(self.saved()[7][4], 1000 - buy_price)
        item = self.saved()[template]
        original_count = next((r[4] for r in before_rows.values() if r[2] == template), 0)
        self.assertEqual(item[4], original_count + 1)
        if original_count:
            self.assertIn(item[1], before_rows)
        else:
            self.assertNotIn(item[1], before_rows)
        self.assertEqual(self.fresh_store().restore(1), purchased)
        await self.close()
        ctx = await self.open(npc_id, 'sell')
        window = ctx.state.window
        key = next(k for k, uid in window.rows.items() if uid == item[1])
        listed = next(dict(r.fields) for r in dict(window.value.fields)[3]
                      if dict(r.fields)[1] == key)
        self.assertEqual(listed[2], sell_price)
        await h.dispatch(self.context(), h.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 6, (codec.Item(key, 1),), 0, 0)))
        self.assertEqual(self.saved()[7][4], 1000 - buy_price + sell_price)
        after_rows = {r.identifier: dict(r.raw_fields)
                      for r in inventory.validate_kit_frame(self.store.restore(1))}
        # The purchased unit is gone; original item ownership and all other
        # quantities/metadata survive both commits, except for the adena delta.
        for uid, row in before_rows.items():
            expected = dict(row)
            if row[2] == 7:
                expected[4] = 1000 - buy_price + sell_price
            self.assertEqual(after_rows[uid], expected)
        self.assertEqual(set(after_rows), set(before_rows))
        self.assertEqual(self.fresh_store().restore(1), self.store.restore(1))
        await self.close()

    async def test_mayer_buy_sell_and_fresh_restore(self):
        await self.round_trip(70030, b'mayer1', 41, 8, 4)

    async def test_verita_buy_sell_and_fresh_restore(self):
        await self.round_trip(70033, b'verita1', 14, 37, 19)

    async def test_werner_buy_sell_and_fresh_restore(self):
        await self.round_trip(70039, b'werner1', 4, 20, 10)

    async def test_vergil_buy_sell_and_fresh_restore(self):
        await self.round_trip(70032, b'vergil1', 113, 60, 30)

    async def test_mandra_buy_sell_and_fresh_restore(self):
        await self.round_trip(70061, b'mandra1', 4, 22, 11)

    async def test_shivan_buy_sell_and_fresh_restore(self):
        await self.round_trip(70083, b'shivan1', 35, 33, 17)

    async def test_restored_inns_are_registered_and_open_their_current_menu(self):
        for npc_id in (70031, 70065, 70084):
            with self.subTest(npc_id=npc_id):
                entity = next(e for e in self.entities
                    if self.broker._world.town.npc_for(e.uid)
                    and self.broker._world.town.npc_for(e.uid).npc_id == npc_id)
                self.assertIs(self.broker._world.terrain.can_stand(
                    entity.map_id, entity.x, entity.y), True)
                self.assertIsNotNone(self.broker._world.town.appearance(entity.uid).sprite_id)
                self.entities.move(1, entity.map_id, entity.x, entity.y)
                ctx = self.context()
                await h.dispatch(ctx, h.CLICK, ctx.wire.click.encode_request(entity.uid))
                self.assertEqual(ctx.state.menu.fields[2], b'inn')
                ctx.mark_delivered()
                await self.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
