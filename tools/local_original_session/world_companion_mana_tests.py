"""Offline worn-weapon/MP/save/party integration; no game, bot or listener.

Use only fixture characters and temporary stores. Direct admitted attack calls
are development checks, not a formal login/gameplay or native display PASS.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, world_combat as wc
from tools.local_original_session import world_npc_resources as npc_mp
from tools.local_original_session import world_feature_weapon_effects as effects
from tools.local_original_session import world_stats
from tools.local_original_session import world_companion_equipment_tests as equipment_fixture
from tools.local_original_session.companion_ai import AttackIntent
from tools.local_original_session.world_companion import CompanionStore
from tools.local_original_session.world_enchant_inventory import enchanted_name
from tools.local_original_session.world_feature_companion import CompanionParty, _companion_save


class CompanionManaTests(unittest.TestCase):
    def setUp(self, *, weapon_effects=True):
        self.fixture = equipment_fixture.CompanionEquipmentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ctx, self.bags = self.fixture.ctx, self.fixture.bags
        self.view = self.ctx.world
        self.actor, self.record = self.fixture.actor, self.fixture.record
        self.view.combat.companion_inventory = self.bags
        self.view.companion_ai.inventory = self.bags
        self.record.mp, self.record.max_mp = 0, 100
        self.record.combat_mode = 'ASSIST'
        self.target, _ = self.fixture.fixture.monster()
        self.group, self.slot = self.view.spawner.slot_for(self.target.uid)
        self.group.monster = replace(self.group.monster, mp=100, hp=10000)
        self.slot.hp = 10000
        attacker = self.view.entities.resolve(self.actor.ref)
        self.view.entities.move(attacker.uid, 0, self.target.x - 1, self.target.y - 1)
        self.actor.target = self.target.ref
        if weapon_effects:
            effects._world_weapon_effects_initialize(self.ctx)
        self.resources = self.view.extensions.get(npc_mp.EXTENSION_KEY)
        self.ctx._companion_store = CompanionStore(Path(self.fixture.temp.name) / 'characters.json')
        self.ctx._companion_inventory = self.bags
        self.ctx._companion_windows, self.ctx._companion_pet_modes = {}, {}
        self.ctx._companion_views = {}
        self.ctx._companion_party = CompanionParty(self.ctx)
        self.ctx._companion_save = lambda uid, receipt=None: _companion_save(self.ctx, uid, receipt)
        self.view.companion_save = self.ctx._companion_save
        self.addCleanup(setattr, self.view, 'companion_save', None)
        self.equip()
        self.view._save_companion(1)
        self.view.drain(1)

    def equip(self, template=342, enchant=0):
        before = self.bags.frames[2]
        rows = [dict(row.raw_fields) for row in inventory.validate_kit_frame(before)]
        uid = max(row[1] for row in rows) + 1
        definition = self.view.data.items[template]
        rows.append(equipment_fixture.item(uid, template, name=enchanted_name(definition, enchant)))
        after = inventory.build_kit_frame(rows)
        self.fixture.store.replace_kit(2, before, after, append=True)
        self.bags.frames[2] = after
        self.bags.set_equipped(2, uid, True)
        return uid

    def strike(self, swing=wc.Swing(True, 1), *, roll=None):
        rng = self.view.combat.rng
        side_effect = lambda low, high: high if roll is None else min(high, roll)
        with patch.object(wc, 'pc_hits_npc', return_value=swing), patch.object(rng, 'randint', side_effect=side_effect):
            self.view.companion_attack(AttackIntent(self.actor.ref, self.target.ref, 10))

    def remaining(self):
        return self.resources.mana_of(self.target.ref, self.group.monster.mp)

    def saved_mp(self):
        store = CompanionStore(Path(self.fixture.temp.name) / 'characters.json')
        return next(row['mp'] for row in store.payload['records'] if row['character_id'] == 2)

    def test_hit_debits_target_and_saves_member_mp_and_party_without_owner_status(self):
        owner = self.view.combat.pcs[1].mp
        self.strike()
        self.assertEqual((self.record.mp, self.saved_mp(), self.remaining()), (3, 3, 97))
        wires = self.view.drain(1)
        self.assertIn(0x4e31, [int.from_bytes(w[2:4], 'little') for w in wires])
        self.assertNotIn(0x4e38, [int.from_bytes(w[2:4], 'little') for w in wires])
        rows = []
        for wire in wires:
            if int.from_bytes(wire[2:4], 'little') != 0x08a3:
                continue
            with pb.parse_message(wire[4:-2]) as message:
                for child in message.occurrences(1):
                    with pb.parse_message(bytes(child.value)) as row:
                        if bytes(row.occurrences(1)[0].value) == b'FixtureMage':
                            rows.append(int(row.occurrences(4)[0].value))
        self.assertEqual(rows, [3])
        self.assertEqual(self.view.combat.pcs[1].mp, owner)
        self.assertIsNone(self.ctx._companion_store.pending)

    def test_enchant_in_actual_worn_row_controls_roll_and_per_hit_cap(self):
        self.equip(enchant=12)
        self.assertEqual(self.view.companion_profiles[2].weapon.enchant, 12)
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (9, 91))

    def test_target_depletion_zero_mp_and_owner_max_clamp(self):
        self.group.monster = replace(self.group.monster, mp=2)
        self.record.mp = 99
        self.strike()
        self.assertEqual((self.record.mp, self.saved_mp(), self.remaining()), (100, 100, 0))
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (100, 0))

    def test_full_member_still_drains_actual_target_like_pc(self):
        self.record.mp = 100
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (100, 97))

    def test_miss_does_not_drain_or_save(self):
        before = self.ctx._companion_store.path.read_bytes()
        self.strike(wc.Swing(False, 0))
        self.assertEqual((self.record.mp, self.remaining()), (0, 100))
        self.assertEqual(self.ctx._companion_store.path.read_bytes(), before)

    def test_zero_damage_landed_hit_still_drains_in_pc_and_companion(self):
        self.install_pc_effects()
        with patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 0)), patch.object(self.view.combat.rng, 'randint', return_value=3):
            wires = self.view.pc_attack(1, self.target.uid)
        self.assertEqual(self.view.combat.pcs[1].mp, 3)
        self.assertIn(0x4e38, [int.from_bytes(w[2:4], 'little') for w in wires])
        self.strike(wc.Swing(True, 0))
        self.assertEqual((self.record.mp, self.remaining()), (3, 94))
        self.assertEqual(self.slot.hp, 10000)

    def test_nonmana_weapon_and_unequipped_mana_staff_never_drain(self):
        self.equip(230)
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (0, 100))
        self.bags.set_equipped(2, self.bags.states[2].weapon_uid, False)
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (0, 100))

    def test_pet_or_missing_inventory_never_enables_mana_effect(self):
        self.record.equipment['_pet'] = {}
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (0, 100))
        del self.record.equipment['_pet']
        self.view.combat.companion_inventory = None
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (0, 100))

    def test_passive_or_out_of_reach_does_not_consume(self):
        self.record.combat_mode = 'PASSIVE'
        self.strike()
        self.record.combat_mode = 'ASSIST'
        self.view.entities.move(self.actor.ref.uid, 0, self.target.x + 5, self.target.y)
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (0, 100))

    def install_pc_effects(self):
        self.view.combat.pcs[1].status_fields.update({12: 0, 13: 100})
        writer = object()
        self.ctx._world_pcs = {id(writer): (writer, 1)}
        self.ctx.realm = NS(service=lambda _: NS(snapshot=lambda: NS(uid=1)))
        base = world_stats.CharacterStats(1, 3, world_stats.Attributes(13, 13, 13, 13, 13, 13))
        worn = (world_stats.EquippedItem(self.view.data.items[342], enchant=12),)
        self.ctx._world_stats_for = lambda position, level: (world_stats.calculate_stats(base, worn), worn, {})
        self.ctx.fold_sync_hooks = lambda name, value, *args: value
        self.ctx.has_hooks = lambda name: False

    def test_pc_absorption_enqueues_vitals_and_roundtrips_existing_vitals_store(self):
        from tools.local_original_session import world_bridge
        from tools.local_original_session.world_progress import ProgressStore
        from tools.local_original_session.world_persist import WorldPersist
        self.install_pc_effects()
        profile = Path(self.fixture.temp.name).resolve() / 'characters.json'
        progress = ProgressStore(profile)
        saved = []
        def save(key, value):
            self.assertEqual(key, ('vitals', 1))
            progress.save_vitals(key[1], value)
            saved.append(value)
        persist = WorldPersist(self.view.runtime.scheduler, save)
        self.addCleanup(persist.shutdown)
        broker = NS(_world_persist=persist, _world=self.view,
                    _world_progress=progress, _world_vital_snapshots={})
        world_bridge._capture_persist(broker)
        self.assertTrue(persist.flush_all().ok)
        self.assertEqual(ProgressStore(profile).vitals(1), (100, 0))
        with patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 1)), patch.object(self.view.combat.rng, 'randint', return_value=3):
            self.view.pc_attack(1, self.target.uid)
        world_bridge._capture_persist(broker)
        self.assertEqual(persist.pending_keys, (('vitals', 1),))
        self.assertEqual(persist.snapshot(('vitals', 1)), (100, 3))
        self.assertTrue(persist.flush_all().ok)
        self.assertEqual(ProgressStore(profile).vitals(1), (100, 3))
        self.assertEqual(saved, [(100, 0), (100, 3)])

    def test_zero_mp_npc_never_credits_pc_or_member(self):
        self.group.monster = replace(self.group.monster, mp=0)
        self.install_pc_effects()
        with patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 1)):
            self.view.pc_attack(1, self.target.uid)
        self.strike()
        self.assertEqual((self.view.combat.pcs[1].mp, self.record.mp, self.remaining()), (0, 0, 0))

    def test_pc_member_and_npc_spell_spending_share_target_balance_and_life_cap(self):
        self.install_pc_effects()
        with patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 1)), patch.object(self.view.combat.rng, 'randint', return_value=15):
            self.view.pc_attack(1, self.target.uid)
        self.assertEqual(self.remaining(), 91)
        self.equip(enchant=12)
        for _ in range(4):
            self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (31, 60))
        self.assertTrue(self.resources.spend_mana(self.target.ref, 100, 10))
        self.strike()
        self.assertEqual((self.record.mp, self.remaining()), (31, 50))

    def test_failed_atomic_save_keeps_previous_file_pending_gain_and_no_hit_replay(self):
        store = self.ctx._companion_store
        before = store.path.read_bytes()
        with patch('tools.local_original_session.world_companion.replace_file', side_effect=OSError('MANA_SAVE_FAILURE')):
            with self.assertLogs('tools.local_original_session.world_companion_runtime', level='ERROR'):
                self.strike()
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual((self.record.mp, self.remaining(), self.slot.hp), (3, 97, 9999))
        self.assertEqual(next(row['mp'] for row in store.pending['records'] if row['character_id'] == 2), 3)
        self.assertIn('MANA_SAVE_FAILURE', self.view.companion_save_errors[-1])
        self.view._save_companion(1)
        self.assertEqual((self.saved_mp(), self.remaining(), self.slot.hp), (3, 97, 9999))
        self.assertIsNone(store.pending)


class FollowerWithoutWeaponEffectsTests(unittest.TestCase):
    def test_optional_feature_absence_preserves_basic_damage_without_absorption(self):
        fixture = CompanionManaTests()
        fixture.setUp(weapon_effects=False)
        self.addCleanup(fixture.doCleanups)
        self.assertNotIn(npc_mp.EXTENSION_KEY, fixture.view.extensions)
        fixture.strike()
        self.assertEqual((fixture.record.mp, fixture.saved_mp(), fixture.slot.hp), (0, 0, 9999))


if __name__ == '__main__':
    unittest.main()
