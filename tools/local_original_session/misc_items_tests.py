"""Official fixed-client remainder: metadata and inert-use regression checks.

These are development tests, not native-client or socket gameplay PASS.
"""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.local_original_session import game_data, item_equipment_effect, world_item_effects, world_handlers, world_magic, world_visibility


class MiscItemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((game_data.M1_DATA_DIR / 'items_ext/misc.json').read_text(encoding='utf-8'))
        cls.rows = cls.raw['items']
        cls.items = game_data.load_items()
        cls.ids = {row['id']['value'] for row in cls.rows}
        data = game_data.M1_DATA_DIR.parent
        cls.official = {row['official_id']: row for row in json.loads(
            (data / 'official/items.json').read_text(encoding='utf-8'))['items']}
        cls.catalog = {row['id']['value']: row for row in json.loads(
            (data / 'catalog/items_all.json').read_text(encoding='utf-8'))['items']}

    def test_additions_are_unique_fixed_client_official_rows(self):
        self.assertEqual(len(self.ids), len(self.rows))
        self.assertFalse(self.ids & set(self.raw['registration_baseline']['baseline_ids']))
        for row in self.rows:
            ident = row['id']['value']
            self.assertEqual(self.official[ident]['client_id'], ident)
            client = self.catalog[ident]
            raw = {f['number']: f['scalar'] for f in client['client_original']['fields'] if f['wire'] == 0}
            definition = self.items[ident]
            self.assertEqual((definition.name_ko, definition.name_token, definition.icon, definition.weight),
                             (client['name_ko']['value'], client['name_token']['value'], raw[5], raw[10]))
            self.assertEqual(row['ground_graphic']['value'], raw.get(6))
            self.assertEqual(row['official_category']['value'], self.official[ident]['official'].get('categoryName'))
            self.assertIsNone(row['price_reference']['value'])
            for offer in row['price_reference']['existing_offers']:
                path = Path(offer['file'])
                original = json.loads(path.read_text(encoding='utf-8'))['sales'][offer['sales_index']]
                self.assertEqual(original['selected_classic_item_id'], ident)
                for key in ('selling_price', 'purchasing_price', 'effective_pack_count', 'source_ref'):
                    self.assertEqual(offer[key], original[key])

    def test_new_rows_only_activate_the_sourced_tower_charm_dispatcher(self):
        item_effects = world_item_effects.load_effects()
        effects = set(item_effects) | set(world_item_effects.load_effects(owner='consumables'))
        # B15 explicitly connects the reusable 11F charm; other additions stay inert.
        self.assertEqual(self.ids & effects, {15430})
        charm = item_effects[15430]
        self.assertEqual((charm.kind, charm.consume_count, charm.destination, charm.entry_bounds),
                         ('tower_teleport', 0, (111, 32669, 32814),
                          (101, 32816, 32778, 32821, 32783)))
        self.assertFalse(self.ids & world_magic.PlayerMagic(world_magic.load_catalog()).books.keys())
        for ident in self.ids:
            definition = self.items[ident]
            self.assertEqual(definition.kind, 'misc')
            self.assertFalse(definition.equippable)
            self.assertEqual(definition.heal_hp, 0)
            self.assertIsNone(definition.buff)

    def test_existing_inventory_policy_consumes_new_metadata(self):
        policies = {policy.template_id: policy for policy in world_handlers._default_item_policies(None)}
        for ident in self.ids:
            definition, policy = self.items[ident], policies[ident]
            self.assertEqual((policy.raw_weight, policy.stackable),
                             (definition.weight, definition.stackable))

    def test_existing_ground_graphic_loader_consumes_fixed_client_values(self):
        graphics = world_visibility.item_gfx()
        for row in self.rows:
            self.assertEqual(graphics[row['id']['value']],
                             (row['icon']['value'], row['ground_graphic']['value']))

    def test_raw0_use_refuses_before_inventory_or_equipment_mutation(self):
        consumer = SimpleNamespace(_defs=self.items, _kit_params_raw0=lambda intent: True,
                                   _blocked=lambda receipt, reason: reason)
        for ident in self.ids:
            context = {'item': SimpleNamespace(template_bits=ident)}
            reason = asyncio.run(item_equipment_effect.ItemEquipmentEffect._consume_kit(
                consumer, None, context, None, {}, None))
            self.assertEqual(reason, 'ITEM_USE_KIT_NO_EFFECT')


if __name__ == '__main__':
    unittest.main()
