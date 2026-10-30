"""Companion worn-resource regression; copied profile, no game or sockets.

The saved character/equipment rows are input only. All mutations and saves use
TMP/TEMP copies. Direct clock/handler checks are development coverage.
"""
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import inventory, inventory_store, world_stats
from tools.local_original_session import world_companion_equipment_tests as fixture
from tools.local_original_session import world_feature_companion as feature
from tools.local_original_session import world_companion_ui as ui
from tools.local_original_session.world_companion import (
    CompanionRecord, CompanionStore, WorldCompanions, record_from_row)
from tools.local_original_session.world_companion_inventory import CompanionInventory
from tools.local_original_session.world_reward import RewardPcState

SOURCE = (Path(__file__).resolve().parents[2] / 'work' / 'local_original_session' /
          'validation-profiles' / 'manual-test-knight')


def values(body):
    with pb.parse_message(body) as message:
        return {f.number: bytes(f.value) if f.wire_type == 2 else f.value
                for f in message.fields}


class CompanionResourcesTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.CompanionEquipmentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ctx, self.view = self.fixture.ctx, self.fixture.ctx.world
        root = Path(self.fixture.temp.name) / 'copied-profile'
        root.mkdir()
        for source in SOURCE.iterdir():
            if source.is_file() and source.suffix in ('.json', '.bin'):
                shutil.copy2(source, root / source.name)
        self.profile = root / 'characters.json'
        self.ctx.inventory_store = inventory_store.InventoryStore(self.profile,
            policy=inventory_store.POLICY, kit_policy=inventory.KIT_POLICY)
        self.ctx._companion_rows = {r['uid']: r for r in
            json.loads(self.profile.read_text(encoding='utf-8'))['characters']}
        self.ctx.inventory_frame = self.ctx.inventory_store.restore(1)
        saved = json.loads((root / 'companion.json').read_text(encoding='utf-8'))
        self.record = record_from_row(next(r for r in saved['records'] if r['character_id'] == 2))
        self.actor = self.fixture.actor
        self.actor.record = self.record
        self.view.companions.records[2] = self.record
        self.bags = CompanionInventory(self.ctx, characters=self.ctx._companion_rows,
            policy=self.ctx._companion_policy, save=lambda uid: self.ctx._companion_save(uid),
            owned_actor=Mock(), report_error=Mock())
        self.bags.initialize(2)
        self.ctx._companion_inventory = self.bags
        self.view.companion_ai.inventory = self.bags
        self.ctx._companion_store = CompanionStore(self.profile)
        self.ctx._companion_windows, self.ctx._companion_pet_modes, self.ctx._companion_views = {}, {}, {}
        self.ctx._companion_party = feature.CompanionParty(self.ctx)
        self.ctx._companion_save = lambda uid, receipt=None: feature._companion_save(self.ctx, uid, receipt)
        self.view.companion_save = self.ctx._companion_save
        self.addCleanup(setattr, self.view, 'companion_save', None)

    def item_uid(self, template):
        return next(r.identifier for r in inventory.validate_kit_frame(self.bags.frames[2])
                    if r.template_bits == template)

    def add_belt(self):
        before = self.bags.frames[2]
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(before)]
        uid = max(r[1] for r in rows) + 1
        rows.append(fixture.item(uid, 505))  # actual catalog body belt: HP+50
        after = inventory.build_kit_frame(rows)
        self.bags.store.replace_kit(2, before, after, append=True)
        self.bags.frames[2] = after
        self.bags.set_equipped(2, uid, True)
        return uid

    def magic(self):
        root = Path(__file__).parent / 'data' / 'companion'
        read = lambda name: json.loads((root / (name + '.json')).read_text(encoding='utf-8'))
        magic = feature.CompanionMagic(self.view, read('mage_spells'), read('mage_growth'),
            read('ai_policy'), {2: self.ctx._companion_rows[2]['attributes']}, display=False)
        magic.policy_for = lambda _: None
        self.view.companion_ai.magic = magic
        return magic

    def test_real_worn_three_items_add_175_once_with_existing_int_and_mpr(self):
        calculated, worn = self.bags.calculated(2)
        bonuses = {row.item.template_id: row.item.modifiers.get('max_mp', 0) for row in worn}
        self.assertEqual({k: bonuses[k] for k in (978, 979, 15399)}, {978: 50, 979: 25, 15399: 100})
        self.assertEqual((self.record.max_mp, calculated.max_mp_bonus, self.record.effective_max_mp), (314, 175, 489))
        self.assertEqual(calculated.attributes.intelligence, self.ctx._companion_rows[2]['attributes'][5] + 1)
        self.assertEqual(calculated.mp_regen_bonus, 22)
        self.assertEqual((self.view.companion_profiles[2].ac, self.view.companion_profiles[2].mr),
                         (calculated.ac, calculated.mr))
        current = self.record.hp, self.record.mp
        for _ in range(3):
            self.bags.refresh(2, publish=False)
            self.assertEqual((self.record.hp, self.record.mp), current)
            self.assertEqual((self.record.max_mp, self.record.effective_max_mp), (314, 489))

    def test_equip_unequip_hp_mp_preserves_then_clamps_and_never_refills(self):
        self.record.mp = 489
        for template, cap in ((978, 439), (979, 414), (15399, 314)):
            self.bags.set_equipped(2, self.item_uid(template), False)
            self.assertEqual((self.record.mp, self.record.effective_max_mp, self.record.max_mp), (cap, cap, 314))
        for template in (978, 979, 15399):
            self.bags.set_equipped(2, self.item_uid(template), True)
            self.assertEqual(self.record.mp, 314)
        belt = self.add_belt()
        self.assertEqual((self.record.max_hp, self.record.effective_max_hp), (317, 367))
        self.record.hp = 367
        self.bags.set_equipped(2, belt, False)
        self.assertEqual((self.record.hp, self.record.effective_max_hp), (317, 317))
        self.bags.set_equipped(2, belt, True)
        self.assertEqual((self.record.hp, self.record.effective_max_hp), (317, 367))

    def test_recovery_party_pet_and_full_status_use_effective_caps(self):
        self.add_belt()
        self.record.hp, self.record.mp = 366, 488
        magic = self.magic()
        self.actor.regen_at = self.fixture.fixture.now
        self.actor.regen_points = self.view.combat.regen.mp_threshold
        magic.hp_regen_points[2] = (self.actor.ref, self.view.combat.regen.hp_threshold(30))
        magic.regen(self.actor, self.fixture.fixture.now)
        self.assertEqual((self.record.hp, self.record.mp), (367, 489))
        self.record.mp = 400
        self.view.drain(1)
        self.ctx._companion_party.reset(1)
        self.ctx._companion_party.sync()
        updates = [values(child) for wire in self.view.drain(1)
            if int.from_bytes(wire[2:4], 'little') == 0x08a3
            for child in self.message_children(wire)]
        self.assertEqual(next(r[4] for r in updates if r[1] == b'SoloMage'), 100 * 400 // 489)
        pet = values(feature._companion_status_frame(self.ctx, self.actor)[4:-2])
        resources = values(pet[3][:-9])  # strip fixed64 EXP tail
        self.assertEqual((resources[2], resources[3], resources[4], resources[5]), (367, 367, 489, 400))
        from tools.local_native_login_self_actor_hook import hook
        fields = ui.status_fields(hook.profiles()[0].fields, character_id=2, record=self.record,
            calculated=self.bags.calculated(2)[0], lawful=500, exp_percent=0)
        self.assertEqual(tuple(fields[n] for n in (10, 11, 12, 13)), (367, 367, 400, 489))

    @staticmethod
    def message_children(wire):
        with pb.parse_message(wire[4:-2]) as message:
            return tuple(bytes(child.value) for child in message.occurrences(1))

    def test_save_load_current_above_base_unchanged_schema_and_command_copy(self):
        self.add_belt()
        self.record.hp, self.record.mp = 360, 480
        self.view.companions.set_commands(2, combat_mode='PASSIVE')
        self.ctx._companion_save(1)
        saved = CompanionStore(self.profile)
        row = next(r for r in saved.payload['records'] if r['character_id'] == 2)
        self.assertEqual(set(row), set(CompanionRecord.__dataclass_fields__))
        self.assertEqual((row['max_hp'], row['max_mp'], row['hp'], row['mp']), (317, 314, 360, 480))
        restored = record_from_row(row)
        self.view.companions.records[2] = self.actor.record = restored
        self.bags.refresh(2, publish=False)
        restored.validate()
        self.assertEqual((restored.effective_max_hp, restored.effective_max_mp, restored.hp, restored.mp),
                         (367, 489, 360, 480))
        world = WorldCompanions(self.view.entities, self.view.runtime.scheduler)
        roster = {uid: dict(account_id='owned-local-test', class_id=r['class'])
                  for uid, r in self.ctx._companion_rows.items()}
        world.register(record_from_row(row), roster=roster)
        path = self.profile.parent / 'scoped-companion.json'
        self.view.companions.save(path, owner_character_id=1)
        loaded, = world.load(path, roster=roster)
        loaded.project_resources(self.bags.calculated(2)[0])
        self.assertEqual(json.loads(json.dumps(asdict(loaded))), row)

    def test_restore_rejects_actual_over_cap_and_bad_scalar_life_before_projection(self):
        row = asdict(self.record)
        for changes in ({'hp': -1}, {'mp': '480'}, {'hp': 0, 'alive': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                record_from_row(dict(row, **changes))
        for changes in ({'mp': 490}, {'hp': 318}):
            restored = record_from_row(dict(row, **changes))
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'RESOURCE_ABOVE_MAXIMUM'):
                restored.project_resources(self.bags.calculated(2)[0])

    def test_ats_percentages_and_potion_thresholds_use_effective_caps(self):
        from tools.local_original_session import ats_config_codec as codec
        self.add_belt()
        self.record.hp, self.record.mp = 200, 260
        # 54.49% HP and 53.16% MP effective; bases give 63.09% and 82.80%.
        self.assertTrue(codec.condition_matches(2, 55, self.record))
        self.assertFalse(codec.condition_matches(1, 55, self.record))
        self.assertTrue(codec.condition_matches(4, 55, self.record))
        self.assertFalse(codec.condition_matches(3, 55, self.record))
        plain = NS(hp=200, max_hp=317, mp=260, max_mp=314)
        self.assertFalse(codec.condition_matches(2, 55, plain))
        self.assertFalse(codec.condition_matches(4, 55, plain))
        # Reuse the exact saved native-loadable blue slot query from this bag.
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(self.bags.frames[2])]
        blue = next(r for r in rows if r[2] == 492 and r[4] > 0)
        wrapped = codec.wrap_blob(codec.build_ats(mp_templates=[{4: 492, 5: blue[22], 6: blue[3], 7: blue[18]}], mp_percent=55))
        self.bags.policy_for = lambda _: codec.companion_policy(wrapped, {})
        self.bags.blue_until[2] = 0
        self.assertTrue(self.bags.potion(self.actor, 10))
        self.assertEqual(self.record.mp, 260)  # blue is periodic, not an instant refill
        self.assertGreater(self.bags.blue_until[2], 10)

    def test_heal_admission_and_clamp_above_growth_base(self):
        from tools.local_original_session import ats_config_codec as codec
        self.add_belt()
        self.record.hp, self.record.mp = 350, 480
        magic = self.magic()
        policy = codec.companion_policy(codec.wrap_blob(codec.build_ats(sequence_spells=(0,))), {0: 'heal'})
        magic.policy_for = lambda _: policy
        entity = self.view.entities.resolve(self.actor.ref)
        self.assertTrue(magic.cast(self.actor, entity, entity, 'heal', 10))
        self.assertGreater(self.record.hp, 350)
        self.assertLessEqual(self.record.hp, 367)
        self.assertEqual(self.record.mp, 476)

    def test_staff_mana_drain_uses_effective_cap_and_saves_actual_current(self):
        from tools.local_original_session import world_companion_mana_tests as mana
        member = mana.CompanionManaTests()
        member.setUp()
        self.addCleanup(member.doCleanups)
        for template in (978, 979, 15399):
            member.equip(template)
        member.record.mp = 270
        member.strike()
        self.assertEqual((member.record.max_mp, member.record.effective_max_mp, member.record.mp), (100, 275, 273))
        member.strike()
        self.assertEqual((member.record.mp, member.saved_mp()), (275, 275))

    def test_selecting_member_seeds_growth_base_for_single_pc_projection(self):
        from tools.local_original_session import world_core_stats as core
        self.record.mp = 480
        realm = NS(_world_companion_record=lambda uid: self.record)
        fields = feature._companion_realm_status(realm, {}, NS(uid=2), True)
        self.assertEqual((fields[12], fields[13]), (480, 314))
        self.ctx._world = self.view
        self.ctx._world_stats_for = lambda position, level=None: (self.bags.calculated(2)[0], (),
            {13: self.ctx._companion_rows[2]['attributes'][2], 14: self.ctx._companion_rows[2]['attributes'][3]})
        fields[18] = 500
        projected = core._world_fields_for(self.ctx, NS(uid=2), fields)
        self.assertEqual((projected[12], projected[13]), (480, 489))

    def test_growth_and_revive_keep_permanent_base_separate(self):
        self.add_belt()
        source = RewardPcState.from_companion(self.record, self.view.companion_profiles[2],
            attributes=self.ctx._companion_rows[2]['attributes'])
        self.assertEqual((source.max_hp, source.max_mp), (317, 314))
        self.record.max_hp, self.record.max_mp = 327, 324
        self.bags.refresh(2, publish=False)
        self.assertEqual((self.record.effective_max_hp, self.record.effective_max_mp), (377, 499))
        self.record.mp = 490
        self.view.companions.die(2, 10)
        self.view.companions.revive(2, 10)
        self.assertEqual((self.record.hp, self.record.mp), (377, 490))
        self.record.validate()


if __name__ == '__main__':
    unittest.main(verbosity=2)
