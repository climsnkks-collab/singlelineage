"""Development tame/store checks only: no sockets, game, or formal packet PASS."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store
from tools.local_original_session import world_feature_pet as product
from tools.local_original_session.world_pet import load_pets
from tools.local_original_session.world_progress import ProgressStore
from tools.local_original_session.world_state_services import InventoryTransactions


def fields(uid, template=1, count=1):
    return {1: uid, 2: template, 3: 0, 4: count, 5: 0, 7: 1, 9: 0, 10: 0,
            13: 0, 14: 0, 16: 0, 17: 0, 18: b'development tame item', 22: 0,
            24: False, 25: 0, 26: False}


class TameDevelopmentTests(unittest.TestCase):
    def setUp(self):
        from tools.local_original_session.world_companion_integration_tests import CompanionWorldViewTests
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = CompanionWorldViewTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.view = self.fixture.view
        self.view.terrain.can_stand = self.view.terrain.passable
        self.view.companions.dismiss(2)
        self.view.companion_save = lambda *_: None
        profile = Path(self.temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(profile)
        roster.create(inventory_store.realm.Creation('FixtureKnight', 1, 0, (13,) * 6))
        self.inv = inventory_store.InventoryStore(profile, policy=inventory_store.POLICY,
                                                  kit_policy=inventory.KIT_POLICY)
        self.ctx = SimpleNamespace(world=self.view, realm=SimpleNamespace(store=roster),
            progress_store=ProgressStore(profile), inventory_store=self.inv,
            inventory_transactions=InventoryTransactions(self.inv), starter_fields=fields(65536),
            collect_sync_hooks=lambda *_: (), run_sync_hooks=lambda *_: None,
            _world_names={1: 'FixtureKnight'})
        self.raw = json.loads(product.DATA.read_text(encoding='utf-8'))
        self.system = product.PetSystem(self.ctx, self.raw, load_pets())
        self.system.install()
        self.addCleanup(self.system.close)

    def bag(self, *, count=2, size=2, template=10, anchor_food=False):
        rows = [fields(65536 + n) for n in range(size)]
        food_index = 0 if anchor_food else size - 1
        rows[food_index] = fields(65536 + food_index, template, count)
        self.ctx.inventory_frame = inventory.build_kit_frame(rows)
        self.inv.grant(1, self.ctx.inventory_frame)
        return inventory.validate_kit_frame(self.ctx.inventory_frame)[food_index]

    def target(self, template=177, hp=5):
        target, definition = self.fixture.monster(template)
        self.view.spawner.slot_for(target.uid)[1].hp = hp
        self.view.visibility.known.setdefault(1, set()).add(target.uid)
        return target, definition

    def saved_bag(self):
        self.assertEqual(self.inv.restore(1), self.ctx.inventory_frame)
        return inventory.validate_kit_frame(self.ctx.inventory_frame)

    def test_selected_species_connect_existing_wild_catalog_without_selecting_variants(self):
        for key, template in (('wolf', 9), ('shepherd', 179), ('doberman', 177)):
            spec = self.raw['species'][key]
            definition = self.view.data.monsters[template]
            self.assertEqual(spec['template'], template)
            self.assertEqual((spec['token'], spec['sprite'], spec['name']),
                             (definition.name_token, definition.sprite_id, definition.name_ko))
            self.assertIn(template, load_pets().species[key].classic_candidates)
        self.assertEqual(self.raw['species']['doberman']['spawns'], [])
        self.assertTrue(any(s.template_id == 177 for s in self.fixture.data.spawns))
        self.assertNotIn(183, {s['template'] for s in self.raw['species'].values()})

    def test_tame_debits_once_retires_wild_and_preserves_pet_through_collar_and_restore(self):
        item = self.bag()
        target, definition = self.target()
        old_ref = target.ref
        old_exp = dict(self.view.exp)
        old_rewards = list(self.view.companion_reward_receipts)
        wires = self.system.tame(1, target.uid, item)
        rows = self.saved_bag()
        self.assertEqual(dict(rows[1].raw_fields)[4], 1)
        self.assertEqual(rows[-1].template_bits, 361)
        self.assertEqual(len(wires), 2)
        self.assertEqual(len(self.system.records), 1)
        record = next(iter(self.system.records.values()))
        self.assertEqual((record.level, record.exp, record.hp, record.max_hp), (5, 750, 5, definition.hp))
        actor = self.view.companions.active[record.character_id]
        self.assertNotEqual(actor.ref.uid, old_ref.uid)
        self.assertIsNone(self.view.entities.resolve(old_ref))
        self.assertIsNone(self.view.spawner.slot_for(old_ref.uid))
        self.assertFalse(self.view.runtime.scheduler._by_owner.get(old_ref.uid))
        self.assertEqual(self.view.exp, old_exp)
        self.assertEqual(self.view.companion_reward_receipts, old_rewards)
        before = self.ctx.inventory_frame
        with self.assertRaisesRegex(ValueError, 'PET_CURRENT_VISIBLE_WILD_TARGET_REQUIRED'):
            self.system.tame(1, old_ref.uid, item)
        self.assertEqual(self.ctx.inventory_frame, before)
        self.assertEqual(len(self.system.records), 1)
        collar_uid = record.equipment['_pet']['collar_uid']
        self.system.toggle(1, collar_uid)
        stored = asdict(record)
        self.system.toggle(1, collar_uid)
        self.assertEqual((record.hp, record.mp, record.exp), (5, 5, 750))
        self.assertNotEqual(self.view.companions.active[record.character_id].ref.uid, actor.ref.uid)
        self.assertEqual(self.ctx.inventory_frame, before)
        self.system.close()
        restored = product.PetSystem(self.ctx, self.raw, load_pets())
        restored.install()
        self.addCleanup(restored.close)
        self.assertEqual(restored.records[record.character_id].hp, stored['hp'])
        self.assertEqual(restored.records[record.character_id].equipment['_pet']['collar_uid'], collar_uid)

    def test_full_bag_final_food_frees_slot_and_pending_intent_matches_real_commit(self):
        item = self.bag(count=1, size=inventory.KIT_MAX_ITEMS)
        target, _ = self.target()
        original = self.ctx.inventory_transactions.commit_inventory
        def commit_pending(uid, before, after, **kwargs):
            record = next(iter(self.system.records.values()))
            pending = record.equipment['_pet']['pending_bag']
            self.assertEqual(bytes.fromhex(pending['before']), before)
            self.assertEqual(bytes.fromhex(pending['after']), after)
            return original(uid, before, after, **kwargs)
        with patch.object(self.ctx.inventory_transactions, 'commit_inventory',
                          side_effect=commit_pending) as commit:
            self.system.tame(1, target.uid, item)
        rows = self.saved_bag()
        self.assertEqual(len(rows), inventory.KIT_MAX_ITEMS)
        self.assertNotIn(item.identifier, {r.identifier for r in rows})
        self.assertEqual(rows[-1].template_bits, 361)
        self.assertGreater(rows[-1].identifier, item.identifier)
        self.assertEqual(rows[0].identifier, 65536)
        record = next(iter(self.system.records.values()))
        self.assertNotIn('pending_bag', record.equipment['_pet'])
        self.assertEqual(commit.call_count, 1)
        self.assertEqual(commit.call_args.args[2], self.ctx.inventory_frame)

    def test_full_bag_nonfinal_food_consumes_once_without_collar_or_wild_retirement(self):
        item = self.bag(count=2, size=inventory.KIT_MAX_ITEMS)
        target, _ = self.target()
        self.system.tame(1, target.uid, item)
        self.assertEqual(dict(self.saved_bag()[-1].raw_fields)[4], 1)
        self.assertEqual(self.system.events[-1]['reason'], 'no_collar_slot')
        self.assertFalse(self.system.records)
        self.assertIs(self.view.entities.resolve(target.ref), target)

    def test_full_bag_food_anchor_is_retained_on_capacity_failure(self):
        item = self.bag(count=1, size=inventory.KIT_MAX_ITEMS, anchor_food=True)
        target, _ = self.target()
        self.system.tame(1, target.uid, item)
        self.assertEqual(self.saved_bag()[0].identifier, item.identifier)
        self.assertEqual(dict(self.saved_bag()[0].raw_fields)[4], 0)
        self.assertEqual(self.system.events[-1]['reason'], 'no_collar_slot')
        self.assertFalse(self.system.records)

    def test_hp_failure_consumes_food_without_resetting_wild_hp(self):
        item = self.bag(template=9)
        target, _ = self.target(hp=6)
        self.system.tame(1, target.uid, item)
        self.assertEqual(dict(self.saved_bag()[1].raw_fields)[4], 1)
        self.assertEqual(self.system.events[-1]['reason'], 'target_hp_too_high')
        self.assertEqual(self.view.spawner.slot_for(target.uid)[1].hp, 6)
        self.assertFalse(self.system.records)

    def test_unknown_backend_class_does_not_consume_a_rejected_transfer(self):
        item = self.bag()
        target, _ = self.target()
        catalog = self.system.catalog
        self.system.catalog = type(catalog)(catalog.species, catalog.items, {},
            catalog.cumulative_exp, catalog.max_level, catalog.max_exp)
        before = self.ctx.inventory_frame
        self.assertEqual(self.system.tame(1, target.uid, item), ())
        self.assertEqual(self.ctx.inventory_frame, before)
        self.assertEqual(self.system.events[-1]['consumed'], 0)
        self.assertFalse(self.system.records)


if __name__ == '__main__':
    unittest.main()
