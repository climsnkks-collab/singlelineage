"""Equipment development checks; temporary stores only, no game/listener PASS."""
from dataclasses import replace
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace as NS, MappingProxyType
import unittest

from tools.local_original_session import world_core_stats as core, world_stats as stats
from tools.local_original_session import world_combat as combat, world_progress as progress, world_reward
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_extensions import RuntimeExtensions
from tools.local_original_session.world_ai_tests import status_fields


class EquipmentStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_m1()

    def setUp(self):
        self.base = stats.CharacterStats(1, 1, stats.Attributes(18, 12, 16, 10, 12, 8))
        self.calculated = stats.calculate_stats(self.base)
        self.combat = combat.WorldCombat(self.data, random.Random(7))
        self.world = NS(combat=self.combat, runtime_extensions=RuntimeExtensions(), exp={1: 0})
        self.ctx = NS(world=self.world)
        core._world_equipment_initialize(self.ctx)
        self.profile = combat.PcProfile(1, 1, 0, 18, 12, con=16, wis=10)
        fields = status_fields(50)
        fields.update({2: 1, 10: 40, 11: 50, 12: 15, 13: 20})
        self.state = self.combat.bind_pc(1, self.profile, fields)
        self.world.progress = progress.ProgressOwner(self.world)

    def wear(self, **options):
        item = replace(self.data.items[102], modifiers=MappingProxyType(options), set_bonuses=())
        calculated = stats.calculate_stats(self.base, (stats.EquippedItem(item),))
        core.project_resources(self.state, calculated)
        return calculated

    def test_catalog_options_and_all_classic_sets_add_once(self):
        item = replace(self.data.items[102], modifiers=dict(str=1, dex=2, con=3, wis=4,
            cha=5, int=6, hit_bonus=2, damage_bonus=3, hp_regen=4, mp_regen=5,
            max_hp=40, max_mp=20, mr=7), class_modifiers={}, set_bonuses=())
        value = stats.calculate_stats(self.base, (stats.EquippedItem(item),))
        self.assertEqual(value.attributes, stats.Attributes(19, 14, 19, 14, 17, 14))
        self.assertEqual((value.max_hp_bonus, value.max_mp_bonus, value.hp_regen_bonus,
            value.mp_regen_bonus, value.equipment_melee_hit, value.equipment_ranged_damage),
            (40, 20, 4, 5, 2, 3))
        sets = {bonus.set_id: bonus for item in self.data.items.values() for bonus in item.set_bonuses}
        self.assertEqual(len(sets), 14)
        for bonus in sets.values():
            with self.subTest(set_id=bonus.set_id):
                worn = tuple(stats.EquippedItem(self.data.items[key]) for key in bonus.members)
                matching = stats.catalog_modifiers(bonus.modifiers)
                self.assertIn(matching, stats.equipment_set_modifiers(worn))
                self.assertNotIn(matching, stats.equipment_set_modifiers(worn[:-1]))
                self.assertEqual(stats.equipment_set_modifiers(worn),
                                 stats.equipment_set_modifiers(worn + worn))

    def test_conditional_elf_options_use_saved_class(self):
        for template, field, amount in ((105, 'hpr', 1), (114, 'mr', 5)):
            item = self.data.items[template]
            self.assertEqual(getattr(stats.equipment_modifiers(item, 2), field),
                             getattr(stats.equipment_modifiers(item, 1), field) + amount)

    def test_equip_unequip_rewear_clamps_current_and_keeps_base(self):
        self.wear(max_hp=40, max_mp=20)
        self.assertEqual((self.state.max_hp, self.state.max_mp), (90, 40))
        combat.apply_heal(self.combat, 1, 1000)
        self.state.status_fields[12] = self.state.max_mp
        for _ in range(3):
            core.project_resources(self.state, self.calculated)
            self.assertEqual((self.state.hp, self.state.mp, self.state.max_hp, self.state.max_mp),
                             (50, 20, 50, 20))
            self.wear(max_hp=40, max_mp=20)
            self.assertEqual(progress.base_maxima(self.state), (50, 20))
            self.assertEqual((self.state.hp, self.state.mp), (50, 20))

    def test_kill_refresh_and_death_level_change_do_not_accumulate(self):
        value = self.wear(max_hp=5)
        for _ in range(3):
            self.state.status_fields.update({11: 50, 13: 20})  # ordinary kill writes BASE fields
            core.project_resources(self.state, value)
            self.assertEqual((self.state.max_hp, self.state.max_mp), (55, 20))
        self.state.profile = replace(self.state.profile, level=2)
        core.project_resources(self.state, value)  # death changes level only
        self.assertEqual(progress.base_maxima(self.state), (50, 20))

    def test_growth_equal_to_previous_effective_cap_and_mp_only(self):
        value = self.wear(max_hp=5, max_mp=2)
        self.state.profile = replace(self.state.profile, level=2)
        self.state.max_hp = 55  # new BASE equals old effective: explicit setter disambiguates
        self.state.status_fields.update({11: 55, 13: 22})
        core.project_resources(self.state, value)
        self.assertEqual(progress.base_maxima(self.state), (55, 22))
        self.assertEqual((self.state.max_hp, self.state.max_mp), (60, 24))
        core.project_resources(self.state, self.calculated)
        self.assertEqual((self.state.max_hp, self.state.max_mp), (55, 22))
        self.wear(max_mp=10)
        self.assertEqual((self.state.max_hp, self.state.max_mp), (55, 32))

    def test_save_reload_adopt_and_quest_reprojection_store_base_only(self):
        value = self.wear(max_hp=40, max_mp=20)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'characters.json'
            store = progress.ProgressStore(path)
            self.world.progress.attach_store(store)
            snapshot = self.world.progress.mark(1)
            store.commit(1, snapshot)
            self.assertEqual((snapshot.max_hp, snapshot.max_mp), (50, 20))
            saved = progress.ProgressStore(path).get(1)
            self.assertEqual(saved, snapshot)
            adopted = replace(saved, level=2, max_hp=60, max_mp=23)
            self.world.progress.adopt(1, adopted)
            self.assertEqual((self.state.max_hp, self.state.max_mp), (100, 43))
            self.state.max_hp = adopted.max_hp  # existing quest post-adopt base writer
            self.state.status_fields.update({11: 60, 13: 23})
            core.project_resources(self.state, value)
            self.assertEqual((self.state.max_hp, self.state.max_mp), (100, 43))
            self.combat.forget_pc(1)
            self.ctx._world_equipment_pending[1] = (60, 23, value, 16, 10)
            fields = status_fields(100)
            fields.update({2: 2, 10: 50, 11: 100, 12: 20, 13: 43})
            rebound = self.combat.bind_pc(1, replace(self.profile, level=2), fields)
            self.assertEqual(progress.base_maxima(rebound), (60, 23))
            self.assertEqual((rebound.max_hp, rebound.max_mp), (100, 43))

    def test_reward_uses_growth_base_stats_and_maxima(self):
        self.wear(max_hp=40, max_mp=20, con=10, wis=10)
        self.state.profile = replace(self.state.profile, con=26, wis=20)
        self.state.base_growth_con, self.state.base_growth_wis = 16, 10
        source = world_reward.RewardPcState.from_combat(self.state, exp=124)
        self.assertEqual((source.max_hp, source.max_mp, source.profile.con, source.profile.wis),
                         (50, 20, 16, 10))
        monster = replace(self.data.monsters[0], kill_exp=1)
        result = world_reward.on_kill(source, monster, random.Random(7), data=self.data)
        baseline = world_reward.on_kill(replace(source, profile=self.profile), monster,
                                       random.Random(7), data=self.data)
        self.assertEqual((result.max_hp, result.max_mp), (baseline.max_hp, baseline.max_mp))

    def test_actual_combat_profile_and_regen_consumers(self):
        value = self.wear(max_hp=40, max_mp=20, hit_bonus=3, damage_bonus=4, hp_regen=2, mp_regen=3)
        actual = self.combat.modify_profile(1, self.profile, 0, ranged=False)
        self.assertEqual((actual.weapon.hit, actual.weapon.damage),
                         (self.profile.weapon.hit + 3, self.profile.weapon.damage + 4))
        self.assertEqual(self.combat.modify_profile(1, self.profile, 0, ranged=True).weapon, actual.weapon)
        before_hp, before_mp = self.state.hp, self.state.mp
        self.state.hp_points = self.combat.regen.hp_threshold(1)
        self.state.mp_points = self.combat.regen.mp_threshold
        self.combat.regen_tick(1)
        self.assertEqual((self.state.hp, self.state.mp),
            (before_hp + self.combat.regen.hp_amount(16) + 2,
             before_mp + self.combat.regen.mp_amount(10) + 3))
        self.state.hp, self.state.status_fields[12] = self.state.max_hp - 1, self.state.max_mp - 1
        self.state.hp_points = self.combat.regen.hp_threshold(1)
        self.state.mp_points = self.combat.regen.mp_threshold
        self.combat.regen_tick(1)
        self.assertEqual((self.state.hp, self.state.mp), (90, 40))
        negative = replace(value, hp_regen_bonus=-1, mp_regen_bonus=-1)
        core.project_resources(self.state, negative)
        self.state.hp = 89
        self.state.hp_points = self.combat.regen.hp_threshold(1)
        self.combat.regen_tick(1)
        self.assertEqual(self.state.hp, min(90, 89 + self.combat.regen.hp_amount(16) - 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
