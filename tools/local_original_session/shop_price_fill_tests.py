"""Attributed price fill: pure loader/trade checks, not socket/native PASS."""
import json
from pathlib import Path
import unittest

from tools.local_original_session import game_data, world_shop


class ShopPriceFillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.data = Path(__file__).resolve().parent / 'data'
        cls.shops = {r: world_shop.load_shops(cls.data / r) for r in ('m2', 'm4', 'm5')}
        cls.additions = []
        for region, filename, field in (('m2', 'shop_buyback_reference.json', 'rows'),
                                        ('m4', 'shop_buyback_reference.json', 'rows'),
                                        ('m5', 'shop_sales.json', 'sales')):
            for row in json.loads((cls.data / region / filename).read_text(encoding='utf8'))[field]:
                if (row.get('mapping_status') == 'local_policy_exact_token_kind_icon_ground'
                        and row['npc_id'] in (70014, 70021, 70018)
                        and row['selling_price'] == -1):
                    cls.additions.append(dict(row, file=f'tools/local_original_session/data/{region}/{filename}',
                                              classic_item_id=row['selected_classic_item_id']))

    def test_new_buyback_rows_pay_their_own_npc_price_and_never_enter_buy_list(self):
        # Exercise every new selected source row through the real calculators.
        self.assertEqual(len(self.additions), 168)
        for row in self.additions:
            region = row['file'].split('/')[3]
            shops = self.shops[region]
            key = (row['npc_id'], row['item_id'], row['order_id'])
            offer = shops.offers[key]
            self.assertTrue(offer.calculable)
            self.assertEqual(offer.selling_price, -1)
            listing = world_shop.open_shop(shops, row['npc_id'])
            self.assertNotIn(key, {x.key for x in listing.offers})
            self.assertIn(key, {x.key for x in listing.buyback_only})
            sale = world_shop.calculate_sale(shops, row['npc_id'], adena=17,
                items=(world_shop.InventoryItem(123, row['classic_item_id'], 2, offer.l1j_bless),),
                selections=((123, 2),))
            expected = row['purchasing_price'] // (row['pack_count'] or 1) * 2
            self.assertEqual((sale.proceeds, sale.adena_after, sale.removals),
                             (expected, 17 + expected, ((123, 2),)))
            with self.assertRaisesRegex(world_shop.ShopError, 'SHOP_DOES_NOT_SELL'):
                world_shop.calculate_purchase(shops, row['npc_id'],
                    world_shop.InventorySnapshot(100000, 0, 0, 100000), ((key, 1),))

    def test_references_preserve_original_sql_prices_and_source_directions(self):
        lines = Path('D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql').read_text(encoding='utf8').splitlines()
        for row in self.additions:
            raw = lines[int(row['source_ref'].split(':')[1]) - 1]
            self.assertIn(f"'{row['npc_id']}',", raw)
            self.assertTrue(raw.endswith(f"'{row['selling_price']}', '{row['pack_count']}', '{row['purchasing_price']}');"))
        official = json.loads((self.data / 'official/items.json').read_text(encoding='utf8'))['items']
        self.assertTrue(all(not ({'selling_price', 'purchasing_price', 'sellingPrice', 'purchasingPrice', 'price'} & x['official'].keys()) for x in official))

    def test_npc_scoped_metadata_and_unknown_item_do_not_create_universal_free_price(self):
        paths = [self.data / 'm1/items.json', *(self.data / 'm1/items_ext').glob('*.json')]
        rows = {x['id']['value']: x for p in paths for x in json.loads(p.read_text(encoding='utf8'))['items']}
        self.assertIsNone(rows[210]['price_reference']['value'])
        self.assertEqual(rows[210]['price_reference']['official']['status'], 'UNKNOWN_NOT_PROVIDED')
        self.assertTrue(any(x['npc_id'] == 70018 and x['purchasing_price'] == 4000
                            for x in rows[210]['price_reference']['existing_offers']))
        self.assertEqual(rows[895]['price_reference']['status'], 'UNKNOWN_NO_CONFIRMED_PRICED_MAPPING')
        self.assertFalse(rows[895]['price_reference']['existing_offers'])
        self.assertFalse(rows[895]['price_reference']['buyback_offers'])
        self.assertFalse(rows[895]['price_reference']['l1j_reference_offers'])
        self.assertFalse(any(x.classic_item_id == 895 and x.calculable for s in self.shops.values() for x in s.offers.values()))
        # Preserve an existing normal purchase and real pack calculation.
        shops = self.shops['m2']
        offer = next(x for x in shops.offers.values() if x.key[0] == 70014 and x.classic_item_id == 343 and x.selling_price >= 0)
        result = world_shop.calculate_purchase(shops, 70014,
            world_shop.InventorySnapshot(2000, 0, 0, 10000), ((offer.key, 2),))
        self.assertEqual(result.cost, 1000)
        self.assertEqual(sum(x.count for x in result.grants), 2 * offer.pack_count)
        self.assertIn(210, game_data.load_items())


if __name__ == '__main__':
    unittest.main()
