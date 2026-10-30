"""Offline ordinary NPC physical skill integration; no sockets/client/profile."""
from dataclasses import replace
import json
from pathlib import Path
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, world_combat as combat
from tools.local_original_session import world_feature_knight_skills as knight
from tools.local_original_session import world_feature_magic as feature
from tools.local_original_session import world_magic as magic, world_registry
from tools.local_original_session import world_enchant_inventory
from tools.local_original_session import world_magic_tests as existing_tests

fields = existing_tests.fields


class KnightRulesTests(unittest.TestCase):
    def test_official_costs_levels_durations_and_optional_support(self):
        enabled = magic.PlayerMagic(magic.load_catalog(), runtime_policies=knight.POLICIES)
        disabled = magic.PlayerMagic(magic.load_catalog())
        for key, minimum, mp, hp, duration in ((89,40,5,30,180),(90,50,10,100,64)):
            spell = enabled.spells[key]
            self.assertEqual((spell.classes,spell.mp,spell.raw['hp_cost']['value'],spell.duration),
                             ({1:minimum},mp,hp,duration))
            self.assertEqual(spell.raw['player_policy']['book_raw_weight']['value'],7000)
            self.assertTrue(spell.raw['player_policy']['uncancelable'])
            self.assertEqual(disabled.spells[key].kind,'unsupported')
            disabled.state(1).learned.add(key)
            with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):
                disabled.admit_cast(1,key,1,99,100,True,100)
            with self.assertRaisesRegex(ValueError,'LEVEL_TOO_LOW'):
                enabled.learn(1,spell,1,minimum-1)
            with self.assertRaisesRegex(ValueError,'CLASS_NOT_ALLOWED'):
                enabled.learn(1,spell,3,99)

    def test_official_solid_level_boundaries(self):
        self.assertEqual([knight.solid_bonus(level) for level in (40,49,50,51,55,80)],
                         [15,15,20,21,25,25])
        self.assertEqual(knight.knight_er(50,16,16),19)
        self.assertEqual(knight.knight_er(50,7,12),12) # Java -1/2 ->0

    def test_local_counter_probability_original_int_and_damage(self):
        self.assertEqual(knight.counter_chance(50,2),20)
        self.assertEqual(knight.counter_chance(68,60,10),24)
        self.assertEqual(knight.counter_chance(68,68,12),24)
        from tools.local_original_session.game_data import load_m1
        weapon = next(item for item in load_m1().items.values() if item.weapon_type=='twohand')
        self.assertEqual(knight.counter_damage(weapon,5),(weapon.dmg_large+weapon.dmg_bonus+5)*2)

    def test_disabled_saved_effect_is_inert_preserved_and_resumes_deadline(self):
        enabled = magic.PlayerMagic(magic.load_catalog(),runtime_policies=knight.POLICIES)
        enabled.state(1).learned={89,90}
        enabled.committed(1,enabled.spells[90],100)
        enabled.state(1).weapon_uids[90]=77
        row=enabled.snapshot(1,110,wall=1000)
        disabled=magic.PlayerMagic(magic.load_catalog())
        disabled.restore(1,row,300,wall=1005)
        self.assertFalse(disabled.active(1,'counter_barrier',300))
        row=disabled.snapshot(1,310,wall=1015)
        resumed=magic.PlayerMagic(magic.load_catalog(),runtime_policies=knight.POLICIES)
        resumed.restore(1,row,500,wall=1020)
        self.assertEqual(resumed.state(1).buffs[90],534)
        self.assertEqual(resumed.state(1).weapon_uids[90],77)
        self.assertTrue(resumed.active(1,'counter_barrier',533.9))
        resumed.expire(534)
        self.assertFalse(resumed.active(1,'counter_barrier',534))

    def test_registry_disable_removes_policy_admission_and_events(self):
        from tools.local_original_session.world_handlers import feature_registry
        enabled=feature_registry()
        with patch.dict('os.environ', {'SL_DISABLE_FEATURES':'world_feature_knight_skills'}):
            feature_registry.cache_clear()
            disabled=feature_registry()
        feature_registry.cache_clear()
        self.assertIn('_knight_magic_policies',enabled.hooks['magic_runtime_policies'])
        self.assertNotIn('magic_runtime_policies',disabled.hooks)

    def test_metadata_covers_registered_monster_catalogs(self):
        from tools.local_original_session import game_data
        root=Path(__file__).resolve().parents[2]
        table=json.loads((Path(__file__).parent/'data/m1/knight_skills.json').read_text(encoding='utf-8'))
        for filename in table['source_catalogs']:
            path=root/filename
            for npc in game_data._monsters(game_data._read(path.parent,path.name)).values():
                with self.subTest(catalog=filename,npc=npc.l1j_npcid):
                    self.assertIn(str(npc.l1j_npcid),table['npcs'])
        self.assertGreater(table['npcs']['45019']['bow_action'],0) # Orc Archer


class KnightWorldTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture=existing_tests.WorldConsumerTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ctx,self.world=self.fixture.ctx,self.fixture.view
        self.world.dismiss_companions(1) # Knight-only reward scenario; normal lifecycle API.
        self.assertFalse(getattr(self.ctx,'_world_magic_adapters',None))
        self.engine=magic.PlayerMagic(magic.load_catalog(),runtime_policies=knight.POLICIES)
        self.fixture.magic=self.engine
        self.ctx._world_magic=self.engine
        self.ctx._world_registry=world_registry.build_registry((feature,knight))
        for fn in knight.METHODS:
            setattr(self.ctx,fn.__name__,MethodType(fn,self.ctx))
        self.state=self.world.combat.pcs[1]
        self.state.profile=replace(self.state.profile,level=50,character_class=1,dexterity=16)
        self.world.exp[1]=self.world.data.exp_for_level(50)
        self.state.hp=self.state.max_hp=600
        self.state.status_fields[10]=self.state.status_fields[11]=600
        self.state.status_fields[12]=self.state.status_fields[13]=100
        self.engine.state(1).learned={89,90}
        self.ctx.realm.store=NS(select=lambda name:(None,{12:16,16:8}))
        self.weapon=next(item for item in self.world.data.items.values() if item.weapon_type=='twohand')
        self.selected=NS(weapon_uid=77,slots=())
        self.enchant=5
        self.kit=self.make_kit()
        self.ctx._item_equipment_effect=NS(store=NS(peek=lambda uid:(self.selected,self.kit)))
        self.ctx._world_magic_npc_spells={}
        self.ctx._world_magic_buff_ui=True
        feature._world_magic_consumers(self.ctx)
        knight._knight_initialize(self.ctx)
        self.addCleanup(knight._knight_stopped,self.ctx)
        self.target,self.monster=self.fixture.fixture.monster(0)
        self.world._refresh(1)
        self.world.drain(1)

    def make_kit(self):
        row=fields(77,self.weapon.template_id)
        row[18]=world_enchant_inventory.enchanted_name(self.weapon,self.enchant)
        return inventory.build_kit_frame([row])

    def cast(self,key,at=None):
        if at is not None:
            self.fixture.fixture.now=at
        self.ctx._world_magic_cast(1,key,1,self.fixture.fixture.now if at is None else at)

    def incoming(self,roll=1,swing=combat.Swing(True,20),monster=None):
        with patch.object(combat,'npc_hits_pc',return_value=swing), patch.object(self.world.combat.rng,'randint',return_value=roll):
            self.world.npc_attack(self.target,self.monster if monster is None else monster,1,self.fixture.fixture.now)

    def test_actual_cast_debits_once_and_normal_icons_display(self):
        self.cast(90)
        self.assertEqual((self.state.hp,self.state.mp),(500,90))
        self.assertEqual(self.engine.state(1).weapon_uids[90],77)
        self.assertEqual(self.ctx._world_magic_icons[(1,90)],20479)
        wires=self.world.drain(1)
        self.assertTrue({0x4e91,0x4e31,0x4ed8}<={int.from_bytes(w[2:4],'little') for w in wires})
        self.assertTrue(self.fixture.saved)

    def test_solid_cast_has_no_old_l1j_shield_requirement(self):
        self.selected.weapon_uid=0
        self.cast(89)
        self.assertEqual((self.state.hp,self.state.mp),(570,95))
        self.assertEqual(self.ctx._world_magic_icons[(1,89)],20161)

    def test_wrong_weapon_missing_equipment_and_hp_refuse_without_cost(self):
        original=self.kit
        sword=next(item for item in self.world.data.items.values() if item.weapon_type=='sword')
        self.kit=inventory.build_kit_frame([fields(77,sword.template_id)])
        for selected in (77,0):
            self.selected.weapon_uid=selected
            with self.assertRaisesRegex(ValueError,'TWO_HANDED'):
                self.cast(90)
            self.assertEqual((self.state.hp,self.state.mp),(600,100))
            self.assertFalse(self.engine.state(1).buffs)
        self.kit=original
        self.selected.weapon_uid=77
        self.state.hp=100
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_HP'):
            self.cast(90)
        self.assertEqual((self.state.hp,self.state.mp),(100,100))

    def test_counter_avoids_hit_and_normal_npc_hp_owner_once(self):
        self.cast(90)
        group,slot=self.world.spawner.slot_for(self.target.uid)
        slot.hp=1000
        before=self.state.hp
        self.incoming()
        self.assertEqual(self.state.hp,before)
        self.assertEqual(slot.hp,1000-knight.counter_damage(self.weapon,5))
        self.assertEqual(len(self.ctx._knight_events),1)

    def test_lethal_counter_rewards_once_and_stale_ref_cannot_repeat(self):
        self.cast(90)
        before=len(self.world.combat.kills)
        experience=self.world.exp[1]
        with patch.object(self.world,'_reward',wraps=self.world._reward) as rewards:
            self.incoming()
            self.assertEqual(rewards.call_count,1)
            self.incoming()
            self.assertEqual(rewards.call_count,1)
        self.assertEqual(len(self.world.combat.kills),before+1)
        self.assertEqual(self.world.exp[1]-experience,self.monster.kill_exp)

    def test_failed_counter_preserves_ordinary_incoming_hit(self):
        self.cast(90)
        self.incoming(roll=100)
        self.assertEqual(self.state.hp,480)

    def test_ranged_at_two_tiles_never_counters_but_adjacent_does(self):
        self.cast(90)
        archer=self.world.data.monsters[1]
        self.world.entities.move(self.target.uid,0,102,100,0)
        self.incoming(roll=20,monster=archer)
        self.assertEqual(self.state.hp,480)
        self.assertFalse([e for e in self.ctx._knight_events if e['kind']=='counter'])
        self.world.entities.move(self.target.uid,0,101,100,0)
        self.incoming(monster=archer)
        self.assertEqual(self.state.hp,480)
        self.assertTrue([e for e in self.ctx._knight_events if e['kind']=='counter'])

    def test_reach_two_melee_is_counterable(self):
        self.cast(90)
        self.world.entities.move(self.target.uid,0,102,100,0)
        self.incoming(monster=replace(self.monster,attack_range=2))
        self.assertEqual(self.state.hp,500)

    def test_solid_adds_exact_bonus_to_baseline_er_and_does_not_affect_melee(self):
        archer=self.world.data.monsters[1]
        self.world.entities.move(self.target.uid,0,102,100,0)
        self.incoming(roll=20,monster=archer) # base ER19: lands
        self.assertEqual(self.state.hp,580)
        self.assertEqual(self.ctx._knight_events[-1]['er'],19)
        self.cast(89)
        self.incoming(roll=20,monster=archer) # ER39: avoided
        self.assertEqual(self.state.hp,550)
        self.assertEqual(self.ctx._knight_events[-1]['er'],39)
        self.incoming(roll=20) # nonarcher melee/reach bypass ER
        self.assertEqual(self.state.hp,530)

    def test_reduction_combines_with_er_and_does_not_reduce_counter_damage(self):
        self.engine.state(1).learned.add(87)
        self.engine.committed(1,self.engine.spells[87],10)
        self.cast(89,at=13)
        archer=self.world.data.monsters[1]
        self.world.entities.move(self.target.uid,0,102,100,0)
        self.incoming(roll=100,monster=archer)
        self.assertEqual(self.state.hp,551) # HP600-cost30-hit20+reduction1
        self.fixture.fixture.now=16
        self.cast(90,at=16)
        self.world.entities.move(self.target.uid,0,101,100,0)
        slot=self.world.spawner.slot_for(self.target.uid)[1]
        slot.hp=1000
        self.incoming(roll=1)
        self.assertEqual(self.state.hp,451)
        self.assertEqual(slot.hp,1000-knight.counter_damage(self.weapon,5))

    def test_selected_npc_magic_bypasses_counter_and_er(self):
        self.cast(90)
        with patch.object(self.ctx,'_world_magic_npc_swing',return_value=(combat.Swing(True,0),None)):
            self.incoming()
        self.assertEqual(self.state.hp,500)
        self.assertFalse(self.ctx._knight_events)

    def test_expiry_death_and_weapon_replacement_remove_and_publish(self):
        self.cast(90)
        self.selected.weapon_uid=78
        knight._knight_equipment_changed(self.ctx,1)
        self.assertNotIn(90,self.engine.state(1).buffs)
        self.assertNotIn((1,90),self.ctx._world_magic_icons)
        self.selected.weapon_uid=77
        self.cast(90,at=12)
        feature._world_magic_died(self.ctx,1)
        self.assertFalse(self.engine.state(1).buffs)
        self.cast(89,at=14)
        self.fixture.fixture.now=194
        feature._world_magic_tick(self.ctx,194)
        self.assertFalse(self.engine.state(1).buffs)
        self.assertNotIn((1,89),self.ctx._world_magic_icons)

    def test_disabled_service_suppresses_optional_icons_and_runtime_stop_removes_callbacks(self):
        self.cast(90)
        row=self.engine.snapshot(1,10,wall=1000)
        self.ctx._world_magic=magic.PlayerMagic(magic.load_catalog())
        self.ctx._world_magic.restore(1,row,10,wall=1000)
        self.ctx._world_magic_icons={}
        feature._world_magic_sync_icons(self.ctx,1,10)
        self.assertEqual(self.ctx._world_magic_icons,{})
        knight._knight_stopped(self.ctx)
        self.assertFalse(self.world.events._callbacks['npc_physical_swing'])
        knight._knight_started(self.ctx)
        self.assertEqual(len(self.world.events._callbacks['npc_physical_swing']),1)

    def test_special_monster_physical_uses_counter_then_falls_back(self):
        from tools.local_original_session.world_monster_skills import MonsterSkills,load_attacks
        self.cast(90)
        owner=MonsterSkills(self.world,load_attacks(),provider=(self.engine,lambda uid,now:None))
        slot=self.world.spawner.slot_for(self.target.uid)[1]
        slot.hp=1000
        with patch.object(combat,'npc_hits_pc',return_value=combat.Swing(True,20)) as hits, \
                patch.object(self.world.combat.rng,'randint',return_value=1):
            owner._physical(self.target,self.monster,self.world.entities.get(1),10)
        self.assertEqual(self.state.hp,500)
        self.assertEqual(slot.hp,1000-knight.counter_damage(self.weapon,5))
        self.assertEqual([e['kind'] for e in self.ctx._knight_events],['counter'])
        hits.assert_not_called()
        with patch.object(combat,'npc_hits_pc',return_value=combat.Swing(True,20)) as hits, \
                patch.object(self.world.combat.rng,'randint',return_value=100):
            owner._physical(self.target,self.monster,self.world.entities.get(1),10)
        self.assertEqual(self.state.hp,480)
        hits.assert_called_once()
        self.assertEqual([e['kind'] for e in self.ctx._knight_events],['counter'])


if __name__=='__main__':
    unittest.main()
