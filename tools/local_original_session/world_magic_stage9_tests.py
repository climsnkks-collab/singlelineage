"""Stage9 real-owner unit checks; fixture values do not touch user profiles."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import world_magic as rules, world_magic_status as status
from tools.local_original_session import world_feature_magic as feature, world_combat as combat
from tools.local_original_session import world_item_effects as items, inventory
from tools.local_original_session import world_magic_stage8_tests as fixtures

KEYS=(64,65,67,68,69,70)


class Stage9Tests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Stage8Tests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.ctx,self.world,self.magic=self.f.ctx,self.f.world,self.f.magic
        self.pc,self.clock=self.f.pc,self.f.clock

    def cast(self,key,target=1):return self.f.cast(key,target)
    def enemy(self,**kwargs):return self.f.enemy(**kwargs)

    def test_official_costs_30percent_immunity_and_variable_durations(self):
        engine=rules.PlayerMagic(rules.load_catalog())
        expected={64:(48,0,0),65:(40,1,8),67:(30,2,32),68:(60,0,0),69:(48,0,0),70:(20,2,16)}
        for key,(mp,stones,duration) in expected.items():
            s=engine.spells[key]
            self.assertEqual((s.mp,sum(m['count'] for m in s.raw['materials']['value']),s.duration),(mp,stones,duration))
            self.assertEqual(s.raw['hp_cost']['value'],0);self.assertEqual(s.classes,{3:36})
            self.assertEqual(engine.learn(1,s,3,36),{key})
            with self.assertRaisesRegex(ValueError,'LEVEL_TOO_LOW'):engine.learn(1,s,3,35)
        self.assertEqual(engine.spells[67].raw['player_policy']['damage_multiplier'],.7)

    def test_each_stage9_book_real_handler_commits_learning_and_preserves_duplicate(self):
        from tools.local_original_session.spellbook_learning_tests import LearningHandlerTests
        helper=LearningHandlerTests();self.addCleanup(helper.doCleanups)
        for key in KEYS:
            case=helper.fixture(self.magic.spells[key].book)
            with self.subTest(key=key):
                self.assertTrue(asyncio.run(case.use()));self.assertEqual(case.engine.state(1).learned,{key})
                after=case.store.restore(1)
                self.assertEqual(next(dict(i.raw_fields)[4] for i in inventory.validate_kit_frame(after) if i.identifier==11),1)
                self.assertTrue(asyncio.run(case.use()));self.assertEqual(case.store.restore(1),after)

    def test_lightning_storm_radius_is_centered_on_real_target_not_caster(self):
        target,_,a=self.enemy(x=106);near,_,b=self.enemy(x=109);far,_,c=self.enemy(x=110)
        self.cast(64,target.uid)
        self.assertLess(a.hp,10000);self.assertLess(b.hp,10000);self.assertEqual(c.hp,10000)

    def test_fire_storm_hits_nearby_current_monsters_without_selected_target(self):
        near,_,a=self.enemy(x=103);far,_,b=self.enemy(x=104)
        self.cast(69,None)
        self.assertLess(a.hp,10000);self.assertEqual(b.hp,10000)

    def test_fog_sleep_single_target_official_range_and_random_duration(self):
        target,group,slot=self.enemy();neighbor,_,_=self.enemy(x=102)
        with patch.object(status,'probability',return_value=True):self.cast(65,target.uid)
        effect=self.magic.status(target.uid,'sleep',self.clock.now)
        self.assertTrue(1<=effect['until']-self.clock.now<=8)
        self.assertIsNone(self.magic.status(neighbor.uid,'sleep',self.clock.now))
        self.assertTrue(status.ai_status(self.magic.effects(target.uid,target_ref=target.ref),self.clock.now)['blocked'])

    def test_sleep_ends_on_positive_npc_damage_and_releases_pc_block_hud_on_expiry(self):
        target,group,slot=self.enemy()
        with patch.object(status,'probability',return_value=True):self.cast(65,target.uid)
        self.world._apply_monster_swing(1,1,target,group.monster,slot.hp,combat.Swing(True,1),self.clock.now)
        self.assertIsNone(self.magic.status(target.uid,'sleep',self.clock.now))
        self.magic.apply_status(1,'sleep',self.clock.now,1,spell=65)
        frames=self.ctx._world_magic_after_relocate(1,{})
        self.assertIn(items.buff_icon_frame(65,1560,1),frames)
        with self.assertRaisesRegex(ValueError,'CASTER_PARALYZED'):
            self.magic.admit_cast(1,67,3,60,1000,True,self.clock.now)
        self.clock.now+=1;self.magic.expire(self.clock.now)
        self.assertFalse(status.ai_status(self.magic.effects(1),self.clock.now)['blocked'])

    def test_sleep_wakes_from_current_pc_hit_event_without_poison_or_miss_waking(self):
        feature._world_magic_consumers(self.ctx);self.addCleanup(self.ctx._world_magic_stopped)
        self.magic.apply_status(1,'sleep',self.clock.now,8,spell=65)
        self.world.events.emit('pc_hit',self.world.entities.get(1).ref,None,self.clock.now)
        self.assertIsNone(self.magic.status(1,'sleep',self.clock.now))

    def test_fog_failure_and_counter_do_not_apply_or_extend_sleep(self):
        target,_,_=self.enemy()
        with patch.object(status,'probability',return_value=False):self.cast(65,target.uid)
        self.assertIsNone(self.magic.status(target.uid,'sleep',self.clock.now))
        self.magic.apply_status(target.uid,'counter_magic',self.clock.now,30,spell=30,target_ref=target.ref)
        with patch.object(status,'probability',return_value=True):self.cast(65,target.uid)
        self.assertIsNone(self.magic.status(target.uid,'sleep',self.clock.now))

    def test_immune_real_physical_damage_is_reduced_before_hp_debit_and_does_not_heal_back_dead(self):
        feature._world_magic_consumers(self.ctx);self.addCleanup(self.ctx._world_magic_stopped)
        self.cast(67)
        target,group,_=self.enemy();self.pc.hp=80
        with patch.object(combat,'npc_hits_pc',return_value=combat.Swing(True,100)):
            swing,wire=self.world.combat.npc_swing(group.monster,1)
        self.assertEqual(swing.damage,70);self.assertEqual(self.pc.hp,10);self.assertFalse(self.pc.dead)
        self.assertEqual(self.magic.received_damage(1,90,self.clock.now),63)
        self.assertIsNotNone(wire)

    def test_immune_real_magic_and_poison_reduction_with_healing_unchanged(self):
        feature._world_magic_consumers(self.ctx);self.addCleanup(self.ctx._world_magic_stopped)
        self.cast(67);target,group,_=self.enemy();self.pc.hp=100
        attack=NS()
        with patch.object(combat,'npc_hits_pc',return_value=combat.Swing(True,20)):
            swing,_=self.world.combat.npc_magic_swing(group.monster,1,attack)
        self.assertEqual((swing.damage,self.pc.hp),(14,86))
        self.ctx._world_magic_apply_poison(1,target.uid,self.clock.now,duration=10,tick_seconds=1,damage=10)
        self.clock.now+=1;self.ctx._world_magic_poison_tick(self.clock.now)
        self.assertEqual(self.pc.hp,79)
        self.assertEqual(self.magic.healing_amount(1,100,self.clock.now),100)

    def test_immune_monster_special_physical_uses_the_same_pc_hp_once(self):
        from tools.local_original_session.monster_skills_tests import MonsterSkillsTests
        f=MonsterSkillsTests();f.setUp();self.addCleanup(f.tearDown)
        row=next(r for rows in f.owner.attacks.values() for r in rows if r['kind']=='physical')
        monster,target=f.configure(row);pc=f.view.combat.pcs[1]
        f.magic.apply_status(1,'immune_to_harm',f.clock(),32,spell=67,params={'reduction_percent':30})
        before=pc.hp
        with patch.object(combat,'npc_hits_pc',return_value=combat.Swing(True,100)):
            removed=f.owner._physical(f.entity,monster,target,f.clock())
        self.assertEqual(removed,70);self.assertEqual(pc.hp,before-70)

    def test_immune_clan_target_requires_explicit_membership_and_preserves_self(self):
        self.world.bind_pc(2,self.pc.profile,{**self.pc.status_fields,1:2})
        self.world.update_pc(2,0,102,100)
        self.world.pc_known.setdefault(1,set()).add(2)  # current PC fixture publication
        before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'CLAN_RECIPIENT_REQUIRED'):self.cast(67,2)
        self.assertEqual(self.pc.mp,before)
        collect=self.ctx.collect_sync_hooks
        self.ctx.collect_sync_hooks=lambda name,*a,**kw:((1,2),) if name=='clan_members' else collect(name,*a,**kw)
        self.cast(67,2)
        self.assertIsNone(self.magic.status(1,'immune_to_harm',self.clock.now))
        self.assertEqual(self.magic.received_damage(2,100,self.clock.now),70)

    def test_mass_teleport_uses_existing_relocate_and_keeps_other_magic_deadlines(self):
        self.cast(67);until=self.magic.status(1,'immune_to_harm',self.clock.now)['until']
        row={'operation_lock':NS(locked=lambda:True)};game=object()
        self.ctx.realm.registry=NS(resolve=lambda writer:game);self.ctx.realm.serves_map=lambda m:True
        destination=items.MapDestination(0,110,110,0)
        self.ctx._world_relocate_locked=Mock(return_value=())
        self.clock.now+=2
        with patch.object(items,'random_destination',return_value=destination):
            self.ctx._world_magic_cast(1,68,None,self.clock.now,row=row,game=game)
        self.ctx._world_relocate_locked.assert_called_once()
        self.assertEqual(self.ctx._world_magic_events[-1]['outcome'],'mass_teleported')
        self.assertEqual(self.magic.status(1,'immune_to_harm',self.clock.now)['until'],until)

    def test_mass_teleport_current_registered_group_member_and_no_fake_nearby_party(self):
        from tools.local_original_session.world_magic_stage89 import group_relocations
        self.world.bind_pc(2,self.pc.profile,{**self.pc.status_fields,1:2})
        self.world.update_pc(2,0,102,100);action=Mock();collect=self.ctx.collect_sync_hooks
        owner=self.world.entities.get(1);destination=items.MapDestination(0,110,110,0)
        self.assertEqual(group_relocations(self.ctx,1,owner,destination,2),[])
        self.ctx.collect_sync_hooks=lambda name,*a:((1,2),) if name=='party_members' else (action,) if name=='mass_teleport_recipient' else collect(name,*a)
        actions=group_relocations(self.ctx,1,owner,destination,2);self.assertEqual(actions,[action])
        actions[0](self.clock.now);action.assert_called_once()

    def test_decay_pc_only_range_duration_and_real_hud(self):
        target,_,_=self.enemy();before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'PC_TARGET_REQUIRED'):self.cast(70,target.uid)
        self.assertEqual(self.pc.mp,before)
        with patch.object(status,'probability',return_value=True):frames=self.cast(70)
        effect=self.magic.status(1,'decay_potion',self.clock.now);remaining=effect['until']-self.clock.now
        self.assertTrue(4<=remaining<=16);self.assertIn(items.buff_icon_frame(70,754,remaining),frames)

    def test_decay_rejects_potion_kinds_but_keeps_food_scrolls_and_spell_healing(self):
        with patch.object(status,'probability',return_value=True):self.cast(70)
        for kind in ('heal','speed','mana_regen','cure_poison','wisdom','underwater_breath'):
            with self.assertRaisesRegex(ValueError,'DECAY_POTION_ACTIVE'):
                self.ctx._world_magic_item_admit(1,14,kind,self.clock.now)
        for kind in ('food','identify','return_town','random_teleport','remove_curse'):
            self.ctx._world_magic_item_admit(1,14,kind,self.clock.now)
        self.pc.hp=1;self.cast(56);self.assertGreater(self.pc.hp,1)

    def test_decay_legacy_kit_potion_refuses_before_any_quantity_save(self):
        from tools.local_original_session import item_equipment_effect as gear
        with patch.object(status,'probability',return_value=True):self.cast(70)
        broker=NS(_world_bound=lambda w:True,_world=self.world,_world_pcs={1:(None,1)},
            chain_sync_hooks=lambda name,uid,template,now:self.ctx._world_magic_potion_blocked(uid,template,now))
        writer=object();broker._world_pcs={id(writer):(writer,1)}
        effect=object.__new__(gear.ItemEquipmentEffect);effect.broker=broker
        effect._blocked=lambda receipt,reason:dict(status='BLOCKED',reason=reason)
        context={'item':NS(template_bits=14),'frame':b'not read when refused'}
        result=asyncio.run(effect._consume_potion(writer,context,{},NS()))
        self.assertEqual(result,dict(status='BLOCKED',reason='MAGIC_DECAY_POTION_ACTIVE'))

    def test_all_new_timed_statuses_save_elapsed_teleport_hud_and_expiry(self):
        for key,kind in ((65,'sleep'),(67,'immune_to_harm'),(70,'decay_potion')):
            self.magic.apply_status(1,kind,self.clock.now,8,spell=key,params={'reduction_percent':30} if key==67 else {})
        saved=self.magic.snapshot(1,self.clock.now,wall=1000)
        cold=rules.PlayerMagic(rules.load_catalog());cold.restore(1,saved,500,wall=1003)
        for key,kind,icon in ((65,'sleep',1560),(67,'immune_to_harm',1562),(70,'decay_potion',754)):
            self.assertEqual(cold.status(1,kind,500)['until'],505)
            self.assertIn(items.buff_icon_frame(key,icon,8),self.ctx._world_magic_after_relocate(1,{}))
        cold.expire(505);self.assertFalse(cold.effects(1))

    def test_cancellation_removes_new_magic_but_keeps_learned_keys_and_real_cost(self):
        self.cast(67)
        self.magic.apply_status(1,'decay_potion',self.clock.now,16,spell=70)
        learned=set(self.magic.state(1).learned);self.cast(43)
        self.assertFalse(self.magic.effects(1));self.assertEqual(self.magic.state(1).learned,learned)


if __name__=='__main__':unittest.main()
