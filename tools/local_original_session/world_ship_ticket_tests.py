"""Ticket12017 startup metadata/selection regression; no ports, game or native UI.

Synthetic inventory is a development input. The socket voyage worker owns the
normal login/select proof and fare-consumption/persistence verification.
"""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from tools.local_original_session import game_data, inventory, world_handlers
from tools.local_original_session import world_core_stats, world_weight


class ShipTicketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = game_data.load_m1()
        # Exercise the actual startup producer, including prototype validation.
        cls.bindings = world_handlers.prepare_host_bindings(None)

    def test_fixed_client_identity_and_separate_reference_policy(self):
        item = self.data.items[12017]
        self.assertEqual((item.template_id, item.name_token, item.name_ko,
                          item.icon, item.weight),
                         (12017, '$1930', '잊혀진 섬행 배표', 138, 1000))
        source = Path(__file__).resolve().parents[2] / 'work/source_game_data/native-dump-v1.jsonl'
        with source.open(encoding='utf-8') as stream:
            row = next(parsed for parsed in map(json.loads, stream)
                       if parsed['table'] == 'item' and parsed['id'] == 12017)
        raw = {field['number']: field['scalar'] for field in row['fields'] if field['wire'] == 0}
        self.assertEqual((item.icon, item.weight), (raw[5], raw[10]))
        self.assertEqual((row['name']['reference'], row['name']['KR']),
                         (item.name_token, item.name_ko))
        self.assertEqual(item.sources['id'].kind, 'client')
        self.assertEqual(item.sources['weight'].kind, 'client')
        self.assertEqual(item.sources['stackable'].kind, 'l1j')
        self.assertIn('40300', item.sources['stackable'].ref)
        self.assertFalse(item.stackable)
        self.assertFalse(item.equippable)

    def test_startup_policy_generates_the_client_ticket_inventory_row(self):
        policy = self.bindings.item_policies[12017]
        self.assertEqual((policy.template_id, policy.raw_weight, policy.stackable),
                         (12017, 1000, False))
        fields = dict(policy.grant_fields)
        fields.update({1: 65572, 4: 1})  # explicit development UID/count
        frame = inventory.build_kit_frame((fields,))
        item, = inventory.validate_kit_frame(frame)
        self.assertEqual((item.identifier, item.template_bits, dict(item.raw_fields)[7]),
                         (65572, 12017, 138))

    def test_selection_stats_uses_ticket_definition_without_magic_weight_fallback(self):
        policy = self.bindings.item_policies[12017]
        fields = dict(policy.grant_fields)
        fields.update({1: 65572, 4: 1})
        frame = inventory.build_kit_frame((fields,))
        info = {3: 1, 10: 60, 11: 13, 12: 13, 13: 13, 14: 13, 15: 13, 16: 13}
        equipment = NS(weapon_uid=0, slots=())
        visited = []

        def fold(name, current, *args, **kwargs):
            visited.append(name)
            # This is the old select failure: unknown ticket reached magic's
            # material lookup, which has no key '12017'. It must not be called.
            if name == 'item_weight':
                raise KeyError('12017')
            return current

        world = NS(data=self.data)
        ctx = NS(realm=NS(store=NS(select=lambda name: (None, info))),
                 _world=world, world=world, item_policies=self.bindings.item_policies,
                 _item_equipment_effect=NS(store=NS(peek=lambda uid: (equipment, frame))),
                 fold_sync_hooks=fold)
        position = NS(uid=1, name='TicketKnight')
        calculated, worn, _ = world_core_stats._world_stats_for(ctx, position, level=60)
        self.assertEqual(worn, ())
        self.assertNotIn('item_weight', visited)
        self.assertEqual(calculated.weight,
                         world_weight.weight_state(1, calculated.max_weight))


if __name__ == '__main__':
    unittest.main()
