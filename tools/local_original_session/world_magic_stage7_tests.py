"""Stage7 development checks using current cast/effect/save owners; no game/ports."""
import asyncio
from dataclasses import replace
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_magic as rules, world_magic_status as status
from tools.local_original_session import world_feature_magic as feature, world_combat as combat
from tools.local_original_session import world_item_effects as items, inventory
from tools.local_original_session import world_magic_stage6_tests as stage6


class Stage7Tests(unittest.TestCase):
    def setUp(self):
        self.f=stage6.Stage6Tests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.ctx,self.world,self.magic=self.f.ctx,self.f.world,self.f.magic
        self.pc,self.clock=self.f.pc,self.f.clock

    def cast(self,key,target=1):return self.f.cast(key,target)

    def test_official_costs_durations_and_mage_only_learning(self):
        real=rules.PlayerMagic(rules.load_catalog())
        expected={48:(35,0),49:(30,0),50:(50,3600),51:(15,64),52:(45,0),53:(60,2400),54:(30,1200),55:(30,30)}
        for key,(mp,duration) in expected.items():
            s=real.spells[key]
            self.assertEqual((s.mp,s.duration,s.classes),(mp,duration,{3:28}))
            self.assertEqual(s.raw['hp_cost']['value'],0)
            if key==50:
                with self.assertRaisesRegex(ValueError,'EFFECT_UNSUPPORTED'):real.learn(1,s,3,28)
            else:
                self.assertEqual(real.learn(1,s,3,28),{key})
                with self.assertRaisesRegex(ValueError,'LEVEL_TOO_LOW'):real.learn(1,s,3,27)
                with self.assertRaisesRegex(ValueError,'CLASS_NOT_ALLOWED'):real.learn(1,s,2,99)

    def test_greater_haste_book_uses_existing_handler_without_place_gate(self):
        from tools.local_original_session.spellbook_learning_tests import LearningHandlerTests
        helper=LearningHandlerTests();self.addCleanup(helper.doCleanups)
        case=helper.fixture(523)
        self.assertTrue(asyncio.run(case.use()))
        self.assertFalse(case.ctx._world_magic_errors)
        self.assertEqual(case.engine.state(1).learned,{53})
        self.assertEqual(next(dict(i.raw_fields)[4] for i in inventory.validate_kit_frame(case.store.restore(1)) if i.identifier==11),1)
        self.assertTrue(any(int.from_bytes(w[2:4],'little')==0x4e60 for w in case.sent))

    def test_solo_heal_all_excludes_caster_and_records_no_party_instead_of_fake_group(self):
        self.pc.hp=1
        self.cast(48)
        self.assertEqual(self.pc.hp,1)
        self.assertEqual(self.ctx._world_magic_events[-1]['outcome'],'no_party_members')

    def test_heal_all_registered_current_party_heals_actual_hp_once_excluding_caster(self):
        self.world.bind_pc(2,self.pc.profile,{**self.pc.status_fields,1:2,10:1,11:100})
        self.world.update_pc(2,0,101,100)
        other=self.world.combat.pcs[2];other.hp=1;self.pc.hp=1
        collect=self.ctx.collect_sync_hooks
        self.ctx.collect_sync_hooks=lambda name,*a,**kw:((1,2,2),) if name=='party_members' else collect(name,*a,**kw)
        self.cast(48)
        self.assertEqual(self.pc.hp,1)
        self.assertGreater(other.hp,1)
        self.assertEqual(self.ctx._world_magic_events[-1]['amount'],other.hp-1)

    def sturdy_enemy(self):
        target=self.f.owner.enemy();group,slot=self.world.spawner.slot_for(target.uid)
        group.monster=replace(group.monster,hp=10000);slot.hp=10000
        return target,group,slot

    def test_ice_lance_real_damage_then_sourced_freeze_and_expiry(self):
        target,group,slot=self.sturdy_enemy();before=slot.hp
        with patch.object(status,'probability',return_value=True):self.cast(49,target.uid)
        self.assertLess(slot.hp,before)
        effect=self.magic.status(target.uid,'frozen',self.clock.now)
        self.assertEqual(effect['until'],self.clock.now+8)
        self.assertTrue(status.ai_status(self.magic.npc_statuses[target.uid]['effects'],self.clock.now)['blocked'])
        self.clock.now+=8;feature._world_magic_status_tick(self.ctx,self.clock.now)
        self.assertIsNone(self.magic.status(target.uid,'frozen',self.clock.now))

    def test_counter_magic_absorbs_ice_damage_and_freeze_after_real_cost(self):
        target,group,slot=self.sturdy_enemy();before=slot.hp
        self.magic.apply_status(target.uid,'counter_magic',self.clock.now,30,spell=30,target_ref=target.ref)
        self.cast(49,target.uid)
        self.assertEqual(slot.hp,before)
        self.assertIsNone(self.magic.status(target.uid,'counter_magic',self.clock.now))
        self.assertIsNone(self.magic.status(target.uid,'frozen',self.clock.now))

    def test_ice_lance_freeze_uses_this_attempt_erase_mr_before_marker_consumption(self):
        target,group,slot=self.sturdy_enemy()
        group.monster=replace(group.monster,mr=80)
        self.magic.apply_status(target.uid,'erase_magic',self.clock.now,30,spell=152,target_ref=target.ref)
        with patch.object(status,'probability',return_value=True) as probability:
            self.cast(49,target.uid)
        self.assertEqual(probability.call_args.args[4],40)
        self.assertIsNone(self.magic.status(target.uid,'erase_magic',self.clock.now))

    def test_holy_walk_only_changes_move_axis_and_preserves_deadline_across_restore(self):
        self.magic.spells[51]=replace(self.magic.spells[51],duration=64)
        self.cast(51)
        factor=self.ctx._world_magic_speed_factors((.745,.745),1,self.clock.now)
        self.assertEqual(factor,(.745*.745,.745))
        until=self.magic.status(1,'holy_walk',self.clock.now)['until']
        frames=self.ctx._world_magic_after_relocate(1,{})
        self.assertIn(items.buff_icon_frame(51,1561,64),frames)
        saved=self.magic.snapshot(1,self.clock.now,wall=1000)
        self.magic.restore(1,saved,self.clock.now+20,wall=1003)
        self.assertEqual(self.magic.status(1,'holy_walk',self.clock.now+20)['until'],until+17)

    def test_tornado_around_caster_hits_current_near_monsters_without_a_selected_target(self):
        near,_,a=self.sturdy_enemy();far,_,b=self.sturdy_enemy()
        self.world.entities.move(near.uid,0,101,100);self.world.entities.move(far.uid,0,104,100)
        self.world._refresh(1)
        before_a,before_b=a.hp,b.hp
        self.cast(52,None)
        self.assertLess(a.hp,before_a);self.assertEqual(b.hp,before_b)

    def test_greater_haste_real_2400_seconds_saved_and_rebound_without_1800_truncation(self):
        self.magic.spells[53]=replace(self.magic.spells[53],duration=2400)
        self.cast(53)
        self.assertEqual(self.pc.buffs['haste'][0],self.clock.now+2400)
        saved=items.consumable_snapshot(1,self.f.effects.state(1),self.clock.now,wall=1000)
        cold=items.WorldItemEffects(self.world.combat);cold.world=self.world
        cold.states[1]=items.consumable_restore(saved,self.clock.now+100,wall=2000)
        self.pc.buffs.clear();cold.restore_potions(1,self.clock.now)
        self.assertEqual(self.pc.buffs['haste'][0],self.clock.now+2400)
        self.assertEqual(self.world.combat.speed_factor(1,self.clock.now),self.world.data.items[17].buff.rate)

    def test_berserkers_official_ac_melee_bonus_and_hp_regen_block_preserves_mp(self):
        feature._world_magic_consumers(self.ctx);self.addCleanup(self.ctx._world_magic_stopped)
        self.f.effects.magic=self.magic
        self.cast(54)
        self.assertEqual(self.magic.ac_bonus(1,self.clock.now),10)
        boosted=self.ctx._world_magic_combat_profile(1,self.pc.profile,self.clock.now)
        self.assertEqual(boosted.weapon.damage,self.pc.profile.weapon.damage+5)
        ranged=self.ctx._world_magic_combat_profile(1,self.pc.profile,self.clock.now,ranged=True)
        self.assertEqual(ranged.weapon.damage,self.pc.profile.weapon.damage)
        self.pc.hp=1;self.pc.status_fields[12]=1
        self.pc.hp_points=self.world.combat.regen.hp_threshold(30)
        self.pc.mp_points=self.world.combat.regen.mp_threshold
        self.world.combat.regen_tick(1)
        self.assertEqual(self.pc.hp,1);self.assertGreater(self.pc.mp,1)
        self.clock.now+=11;self.magic.expire(self.clock.now)
        self.pc.hp_points=self.world.combat.regen.hp_threshold(30)
        self.world.combat.regen_tick(1);self.assertGreater(self.pc.hp,1)

    def test_disease_official_pc_ac_hit_hud_save_and_remove_curse(self):
        with patch.object(status,'probability',return_value=True):frames=self.cast(55)
        self.assertEqual(self.magic.ac_bonus(1,self.clock.now),8)
        profile=self.ctx._world_magic_combat_profile(1,self.pc.profile,self.clock.now)
        self.assertEqual(profile.weapon.hit,self.pc.profile.weapon.hit-4)
        self.assertEqual(profile.weapon.damage,self.pc.profile.weapon.damage)
        self.assertIn(items.buff_icon_frame(55,760,10),frames)
        row=self.magic.snapshot(1,self.clock.now,wall=1000)
        fresh=rules.PlayerMagic(rules.load_catalog());fresh.restore(1,row,500,wall=1003)
        self.assertEqual(fresh.status(1,'disease',500)['until'],507)
        self.cast(36);self.assertEqual(self.magic.ac_bonus(1,self.clock.now),0)

    def test_disease_real_npc_attack_hit_and_player_attack_defense_use_current_ref(self):
        target,group,slot=self.sturdy_enemy()
        self.world.entities.move(target.uid,0,101,100)
        with patch.object(status,'probability',return_value=True):self.cast(55,target.uid)
        disease=self.magic.status(target.uid,'disease',self.clock.now)
        changed=status.physical_monster(group.monster,None,disease)
        self.assertEqual(changed.level,group.monster.level-4)
        self.assertEqual(changed.damage,group.monster.damage)
        feature._world_magic_consumers(self.ctx);self.addCleanup(self.ctx._world_magic_stopped)
        with patch.object(combat,'pc_hits_npc',return_value=combat.Swing(False,0)) as hit:
            self.world.pc_attack(1,target.uid)
            self.assertEqual(hit.call_args.args[1].ac,group.monster.ac+8)
        self.assertIsNone(self.magic._defending_npc)

    def test_buff_description_refs_come_from_fixed_commonspell_not_icon_id(self):
        from tools.local_original_session.world_buff_frames import BUFF_DESCRIPTION_REFS
        self.assertEqual({k:BUFF_DESCRIPTION_REFS[k] for k in (41,46,47,51,53,54,55)},
                         {41:854,46:988,47:857,51:817,53:849,54:965,55:695})


if __name__=='__main__':unittest.main()
