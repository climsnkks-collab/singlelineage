"""Pure M2 menu/list tests; no game, server, socket, store or UID mutation."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from tools.local_original_session import world_handlers as h
from tools.local_original_session.world_entities import EntityRegistry
from tools.local_original_session.world_handlers_tests import WIRES
from tools.local_original_session.world_shop import InventoryItem, InventorySnapshot
from tools.local_original_session.world_shop_menu import (
    MenuError, ShopExperiment, build_listing, load_menu_sources, parse_experiment,
)
from tools.local_original_session.world_town import TownConfig, TownNpcs, load_town


class WorldShopMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.town = TownNpcs(EntityRegistry(), load_town(),
                           TownConfig(candidate_npc_ids={70014, 70013, 70011}))
        cls.town.register()
        cls.sources = load_menu_sources(cls.town, ShopExperiment())
        cls.source = next(s for s in cls.sources if s.stem == 'pandora')
        entity = next(e for e in cls.town.entities
                      if cls.town.npc_for(e.uid).key == cls.source.placement_key)
        cls.interaction = cls.town.route_click(entity.uid, player_map_id=entity.map_id,
                                             player_x=entity.x, player_y=entity.y,
                                             max_distance=1)
        cls.potion = next(o for o in cls.interaction.shop_listing.offers
                          if o.classic_item_id == 14)
        cls.policies = {}
        for offer in cls.interaction.shop_listing.offers:
            fields = h._starter_fields()
            fields.update({2: offer.classic_item_id, 7: offer.icon_id})
            cls.policies[offer.classic_item_id] = h.KitItemPolicy(
                offer.classic_item_id, offer.weight_milli, offer.stackable, fields)

    def snapshot(self, items=None, **inventory):
        if items is None:
            items = (InventoryItem(101, 14, 10, 0),)
        return h.TradeSnapshot(replace(InventorySnapshot(1000, 2, 0, 1800, {14: 10}),
                                       **inventory), tuple(items), object())

    def build(self, action='buy', *, source=None, interaction=None,
              snapshot=None, policies=None, context=43):
        return build_listing(self.source if source is None else source, WIRES.lists,
                             self.interaction if interaction is None else interaction,
                             self.snapshot() if snapshot is None else snapshot,
                             context, action,
                             item_policies=self.policies if policies is None else policies)

    def test_default_local_parser_and_all_operand_boundaries(self):
        for value in ('0', 'off', 'OFF'):
            self.assertIsNone(parse_experiment(value))
        for value in (None, '', '  ', '1', 'adena', ' ADENA '):
            self.assertEqual(parse_experiment(value), ShopExperiment(7, 0, 0, 0))
        self.assertEqual(parse_experiment('2147483647,-2147483648,18446744073709551615,-9223372036854775808'),
                         ShopExperiment((1 << 31) - 1, -(1 << 31), (1 << 64) - 1, -(1 << 63)))
        self.assertEqual(parse_experiment(' 7, 2147483647, 0, 9223372036854775807 '),
                         ShopExperiment(7, (1 << 31) - 1, 0, (1 << 63) - 1))

    def test_bad_experiment_operands_refuse(self):
        for value in ('7,0,0', '7,zero,0,0', '-1,0,0,0', '0,0,0,0',
                      '2147483648,0,0,0', '7,2147483648,0,0',
                      '7,-2147483649,0,0', '7,0,-1,0',
                      '7,0,18446744073709551616,0',
                      '7,0,0,9223372036854775808', '7,0,0,-9223372036854775809'):
            with self.subTest(value=value), self.assertRaises(MenuError):
                parse_experiment(value)
        with self.assertRaises(MenuError):
            ShopExperiment(True)

    def test_startup_reads_once_and_selects_only_evidenced_merchants(self):
        original = Path.read_text
        with patch.object(Path, 'read_text', autospec=True, side_effect=original) as read:
            sources = load_menu_sources(self.town)
        self.assertEqual(read.call_count, 1)
        self.assertEqual([(s.placement_key, s.stem) for s in sources],
                         [((70014, 60801), 'pandora'), ((70013, 60956), 'cold1'),
                          ((70011, 60993), 'ShipEvM3'), ((70010, 60820), 'balsim')])
        self.assertTrue(all(s.experiment == ShopExperiment() for s in sources))
        self.assertTrue(all({'buy', 'sell'} <= set(s.actions) for s in sources))

    def test_explicit_disabled_source_refuses_lists_and_is_immutable_io_free(self):
        source = replace(self.source, experiment=None)
        with patch.object(Path, 'read_text', side_effect=AssertionError('REQUEST_IO')):
            self.assertTrue(source.current())
            with self.assertRaisesRegex(MenuError, '^SHOP_EXPERIMENT_REQUIRED$'):
                self.build(source=source)
        with self.assertRaises(FrozenInstanceError):
            source.stem = 'pixel'

    def test_buy_current_offers_rowkeys_prices_and_real_codec_roundtrip(self):
        snapshot = self.snapshot(adena=0)
        with patch.object(Path, 'read_text', side_effect=AssertionError('REQUEST_IO')):
            mode, value, rowmap = self.build(snapshot=snapshot, context=-1)
        self.assertEqual(mode, 5)
        outer = dict(value.fields)
        self.assertEqual((outer[1], outer[2]), (-1, 7))
        self.assertEqual(list(rowmap), list(range(1, len(rowmap) + 1)))
        row = next(dict(r.fields) for r in outer[3] if rowmap[dict(r.fields)[1]] == self.potion.key)
        self.assertEqual(row, {1: row[1], 2: 14, 3: 80, 4: 37, 5: b'$237', 6: 0, 7: 0, 8: 0})
        payload = WIRES.lists.encode(WIRES.lists.BUY, value)
        self.assertEqual(WIRES.lists.decode(WIRES.lists.BUY, 0x4E48, payload), value)
        self.assertEqual(snapshot.inventory.adena, 0)
        with self.assertRaises(TypeError):
            rowmap[1] = self.potion.key

    def test_override_unknown_fields_are_explicit_exact_values(self):
        source = replace(self.source, experiment=ShopExperiment(14, -2, (1 << 64) - 1, -3))
        _, value, _ = self.build(source=source)
        self.assertEqual(dict(value.fields)[2], 14)
        for row in dict(value.fields)[3]:
            fields = dict(row.fields)
            self.assertEqual((fields[6], fields[7], fields[8]), (-2, (1 << 64) - 1, -3))

    def test_startup_backend_descriptions_reach_real_buy_f9_codec(self):
        from tools.local_original_session import world_feature_iteminfo as feature
        from tools.local_original_session.game_data import load_m1
        from tools.local_original_session.world_visibility import item_names
        policies = dict(self.policies)
        prepared = []
        def add(rows, *, replace_existing):
            policies.update((p.template_id, p) for p in rows)
        ctx = NS(world=NS(data=load_m1()), item_policies=policies,
                 _iteminfo_names=item_names(), add_item_policies=add,
                 broker=NS(_world_handler_bindings=NS(town=self.town,
                            sources={self.source.placement_key: self.source})),
                 configure_town=lambda town, sources, **kw: prepared.extend(sources))
        feature._iteminfo_started(ctx)
        with patch.object(Path, 'read_text', side_effect=AssertionError('REQUEST_IO')):
            mode, value, rowmap = self.build(source=prepared[-1], policies=policies)
            payload = WIRES.lists.encode(WIRES.lists.BUY, value)
        self.assertEqual(WIRES.lists.decode(WIRES.lists.BUY, 0x4E48, payload), value)
        row = next(dict(r.fields) for r in dict(value.fields)[3]
                   if rowmap[dict(r.fields)[1]] == self.potion.key)
        children = tuple(dict(child.fields) for child in row[9])
        self.assertEqual(children, ({1: 48, 2: str(load_m1().items[14].weight // 1000).encode()},))
        self.assertNotIn(140, {child[1] for child in children})

    def test_buy_requires_policy_and_excludes_unknown_display_or_grant(self):
        with self.assertRaisesRegex(MenuError, '^GRANT_ITEM_POLICY_UNAVAILABLE$'):
            build_listing(self.source, WIRES.lists, self.interaction, self.snapshot(), 1, 'buy')
        listing = self.interaction.shop_listing
        for offer in (replace(self.potion, icon_id=None), replace(self.potion, name_token=None),
                      replace(self.potion, selling_price=-1)):
            changed = replace(self.interaction, shop_listing=replace(listing, offers=(offer,)))
            self.assertEqual(self.build(interaction=changed)[2], {})
        self.assertEqual(self.build(policies={})[2], {})
        policy = replace(self.policies[14], grant_fields={2: 14, 7: 999})
        self.assertNotIn(self.potion.key, self.build(policies={14: policy})[2].values())

    def test_prototypeless_grant_requires_existing_compatible_stack(self):
        policies = {14: replace(self.policies[14], grant_fields=None)}
        self.assertEqual(list(self.build(policies=policies)[2].values()), [self.potion.key])
        self.assertEqual(self.build(policies=policies,
                                    snapshot=self.snapshot(stack_counts={}))[2], {})

    def test_sell_uses_owned_uid_unit_price_and_real_codec_roundtrip(self):
        snapshot = self.snapshot()
        with patch.object(Path, 'read_text', side_effect=AssertionError('REQUEST_IO')):
            mode, value, rowmap = self.build('sell', snapshot=snapshot)
        self.assertEqual((mode, dict(value.fields)[1], dict(value.fields)[2]), (6, 43, 7))
        self.assertEqual([dict(r.fields) for r in dict(value.fields)[3]], [{1: 101, 2: 19}])
        self.assertEqual(rowmap, {101: 101})
        payload = WIRES.lists.encode(WIRES.lists.SELL, value)
        self.assertEqual(WIRES.lists.decode(WIRES.lists.SELL, 0x4EE7, payload), value)
        self.assertEqual(snapshot.items[0].count, 10)

    def test_buyback_only_offer_reaches_sell_but_never_buy(self):
        listing = self.interaction.shop_listing
        only = replace(self.potion, selling_price=-1)
        changed = replace(self.interaction, shop_listing=replace(
            listing, offers=(), unavailable=(), buyback_only=(only,)))
        self.assertEqual(self.build('buy', interaction=changed)[2], {})
        _, value, rowmap = self.build('sell', interaction=changed)
        self.assertEqual(rowmap, {101: 101})
        self.assertEqual([dict(r.fields) for r in dict(value.fields)[3]],
                         [{1: 101, 2: 19}])

    def test_sell_excludes_equipped_enchanted_bless_unknown_and_highbit_uid(self):
        plain = InventoryItem(101, 14, 10, 0)
        items = (replace(plain, uid=102, equipped=True),
                 replace(plain, uid=103, enchant_level=1),
                 replace(plain, uid=104, l1j_bless=128),
                 replace(plain, uid=105, item_id=999999),
                 replace(plain, uid=0x80000000), replace(plain, uid=0xffffffff),
                 replace(plain, uid=0x7fffffff))
        self.assertEqual(self.build('sell', snapshot=self.snapshot(items))[2],
                         {0x7fffffff: 0x7fffffff})

    def test_sell_ambiguous_mapping_is_excluded_and_zero_price_is_valid(self):
        listing = self.interaction.shop_listing
        duplicate = replace(self.potion, key=(70014, 999999, 0))
        changed = replace(self.interaction,
                          shop_listing=replace(listing, offers=(*listing.offers, duplicate)))
        self.assertEqual(self.build('sell', interaction=changed)[2], {})
        free = replace(self.potion, purchasing_price=0)
        changed = replace(self.interaction, shop_listing=replace(listing, offers=(free,)))
        rows = dict(self.build('sell', interaction=changed)[1].fields)[3]
        self.assertEqual(dict(rows[0].fields), {1: 101, 2: 0})

    def test_action_placement_and_context_must_match_inputs(self):
        with self.assertRaisesRegex(MenuError, '^SHOP_MENU_ACTION_UNAVAILABLE$'):
            self.build('asktax')
        with self.assertRaisesRegex(MenuError, '^SHOP_MENU_PLACEMENT_MISMATCH$'):
            self.build(source=replace(self.source, placement_key=(70013, 60956)))
        for context in (True, 1 << 31, -(1 << 31) - 1):
            with self.assertRaisesRegex(MenuError, '^SHOP_LIST_CONTEXT_I32_REQUIRED$'):
                self.build(context=context)


if __name__ == '__main__':
    unittest.main()
