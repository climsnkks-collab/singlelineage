"""LOCAL weakness data -> existing spell/proc HP consumers; no socket/client."""
from dataclasses import replace
import json
from pathlib import Path
import random
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import game_data, world_combat as combat
from tools.local_original_session import world_feature_weapon_effects as weapon_effects
from tools.local_original_session import world_magic_tests, world_weapon_proc_effects_tests


class WeaknessTests(unittest.TestCase):
    def test_loaded_sourced_weakness_and_missing_or_explicit_priority(self):
        data = game_data.load_m1()
        self.assertEqual(data.monsters[216].weak_attr, 2)
        self.assertEqual(data.monsters[216].sources['l1j_weak_attr'].kind, 'local_policy')
        path = Path(game_data.__file__).with_name('data') / 'm1/monsters.json'
        row = json.loads(path.read_text(encoding='utf-8'))['monsters'][0]
        template = row['template_id']['value']
        row['weak_attr'] = dict(value=4, source='official', ref='TEST explicit priority only')
        row['l1j_weak_attr'] = dict(value=2, source='local_policy', ref='TEST fallback')
        self.assertEqual(game_data._monsters(dict(monsters=[row]))[template].weak_attr, 4)
        del row['weak_attr']
        self.assertEqual(game_data._monsters(dict(monsters=[row]))[template].weak_attr, 2)
        del row['l1j_weak_attr']
        self.assertEqual(game_data._monsters(dict(monsters=[row]))[template].weak_attr, 0)

    def test_four_exact_elements_only_and_existing_spell_rounding(self):
        for attr in (1, 2, 4, 8):
            params = dict(damage_value=100, damage_dice=1, damage_dice_count=0,
                          element_attr_raw=attr, skill_level=7)
            bare = combat.magic_damage(params, 12, random.Random(1))
            weak = combat.magic_damage(params, 12, random.Random(1), weak_attr=attr)
            self.assertEqual((bare, weak), (109, 130))
            self.assertEqual(combat.magic_damage(params, 12, random.Random(1),
                                                weak_attr=attr ^ 3), bare)
            self.assertEqual(combat.magic_damage(params, 12, random.Random(1),
                                                weak_attr=attr, mr=100), 65)
        for attr in (0, 3, 15, 16, -1, 99):
            self.assertEqual(combat.elemental_weakness_multiplier(attr, attr), 1.)

    def magic_fixture(self):
        fixture = world_magic_tests.WorldConsumerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.prepare_new_tiers()
        return fixture

    def test_single_and_area_cast_real_hp_each_target_weakness(self):
        for key, attr in ((14, 2), (24, 2)):
            observed = []
            for weakness in (0, attr, 8):
                fixture = self.magic_fixture()
                target = fixture.enemy()
                group, slot = fixture.view.spawner.slot_for(target.uid)
                group.monster = replace(group.monster, weak_attr=weakness, hp=10000)
                fixture.view.spawner.set_hp(target.uid, 10000)
                fixture.view.combat.rng.seed(123)
                before_mp = fixture.state.mp
                with patch.object(combat, 'magic_damage', wraps=combat.magic_damage) as calculate:
                    fixture.ctx._world_magic_cast(1, key, target.uid, fixture.fixture.now + 2)
                calls = [c for c in calculate.call_args_list if c.kwargs.get('weak_attr') == weakness]
                self.assertTrue(calls)
                self.assertEqual(fixture.state.mp, before_mp-fixture.magic.spells[key].mp)
                observed.append(10000-slot.hp)
            self.assertGreater(observed[1], observed[0])
            self.assertEqual(observed[2], observed[0])

    def proc_fixture(self):
        fixture = world_weapon_proc_effects_tests.WeaponProcTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        return fixture

    def test_equipped_weapon_proc_hp_weakness_and_unrelated_physical_unchanged(self):
        fixture = self.proc_fixture()
        fixture.template = 1094  # Actual loaded Maillot Frost/cone_of_cold producer.
        group, slot = fixture.world.spawner.slot_for(fixture.target.uid)
        values = []
        for weakness in (0, 4, 2, 12):
            group.monster = replace(group.monster, weak_attr=weakness)
            fixture.now += 10
            fixture.world.spawner.set_hp(fixture.target.uid, 10000)
            fixture.attack(damage=7, roll=1)
            proc = fixture.events()[-1]
            self.assertEqual(10000-slot.hp, 7+proc['damage'])
            expected = weapon_effects.reduce_proc_damage(96*(1.2 if weakness == 4 else 1),
                dict(mr=group.monster.mr, resistance=0))
            self.assertEqual(proc['damage'], expected)
            values.append(proc['damage'])
        self.assertGreater(values[1], values[0])
        self.assertEqual(values[2:], [values[0], values[0]])
        fixture.template = 11  # Ordinary physical bow: no magic proc.
        for weakness in (0, 4):
            group.monster = replace(group.monster, weak_attr=weakness)
            fixture.now += 10
            fixture.world.spawner.set_hp(fixture.target.uid, 10000)
            fixture.attack(damage=7, roll=1)
            self.assertEqual(10000-slot.hp, 7)

    def test_magic_feature_absent_proc_still_uses_weakness_and_core_physical_same(self):
        fixture = self.proc_fixture()  # Installs weapon effects only, no magic feature.
        fixture.template = 3020
        group, slot = fixture.world.spawner.slot_for(fixture.target.uid)
        base = group.monster
        normal = combat.pc_hits_npc(combat.PcProfile(30, 3, 0, 13, 13), base, random.Random(2))
        group.monster = replace(base, weak_attr=8)
        self.assertEqual(combat.pc_hits_npc(combat.PcProfile(30, 3, 0, 13, 13),
                                         group.monster, random.Random(2)), normal)
        fixture.attack(damage=1, roll=1)
        proc = fixture.events()[-1]
        self.assertEqual(proc['damage'], weapon_effects.reduce_proc_damage(
            proc['rolled']*1.2, dict(mr=base.mr, resistance=0)))


if __name__ == '__main__':
    unittest.main()
