"""Stage8 current-owner development checks, independent of user saves/ports."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import world_magic as rules, world_magic_status as status
from tools.local_original_session import world_feature_magic as feature, world_combat as combat
from tools.local_original_session import world_item_effects as items, inventory
from tools.local_original_session import world_magic_stage6_tests as fixtures

KEYS = (56,58,59,60,61,63)


class Stage8Tests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.Stage6Tests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.ctx,self.world,self.magic=self.f.ctx,self.f.world,self.f.magic
        self.pc,self.clock=self.f.pc,self.f.clock
        self.pc.profile=replace(self.pc.profile,level=60)
        self.world.on_npc_hit=self.ctx._world_magic_npc_hit

    def cast(self,key,target=1):return self.f.cast(key,target)

    def enemy(self,*,hp=10000,x=101,y=100):
        target=self.f.owner.enemy();group,slot=self.world.spawner.slot_for(target.uid)
        group.monster=replace(group.monster,hp=hp);slot.hp=hp
        self.world.entities.move(target.uid,0,x,y);self.world._refresh(1)
        return target,group,slot

    def test_official_values_learning_and_no_invented_upkeep(self):
        engine=rules.PlayerMagic(rules.load_catalog())
        expected={56:(30,0,0,0),58:(60,0,0,0),59:(45,25,1,0),60:(50,0,0,0),61:(40,0,0,0),63:(30,0,2,16)}
        for key,(mp,hp,stones,duration) in expected.items():
            s=engine.spells[key]
            with self.subTest(key=key):
                self.assertEqual((s.mp,s.raw['hp_cost']['value'],sum(m['count'] for m in s.raw['materials']['value']),s.duration),(mp,hp,stones,duration))
                self.assertEqual(s.classes,{3:32});self.assertEqual(engine.learn(1,s,3,32),{key})
                with self.assertRaisesRegex(ValueError,'LEVEL_TOO_LOW'):engine.learn(1,s,3,31)
                with self.assertRaisesRegex(ValueError,'CLASS_NOT_ALLOWED'):engine.learn(1,s,2,99)
        p=engine.spells[59].raw['player_policy']
        self.assertIsNone(p['upkeep_mp']);self.assertIsNone(p['upkeep_seconds'])

    def test_each_book_real_learning_handler_persists_once_and_duplicate_spends_nothing(self):
        from tools.local_original_session.spellbook_learning_tests import LearningHandlerTests
        helper=LearningHandlerTests();self.addCleanup(helper.doCleanups)
        for key in KEYS:
            case=helper.fixture(self.magic.spells[key].book)
            with self.subTest(key=key):
                self.assertTrue(asyncio.run(case.use()));self.assertEqual(case.engine.state(1).learned,{key})
                after=case.store.restore(1)
                self.assertEqual(next(dict(i.raw_fields)[4] for i in inventory.validate_kit_frame(after) if i.identifier==11),1)
                self.assertTrue(asyncio.run(case.use()));self.assertEqual(case.store.restore(1),after)
                self.assertIn('MAGIC_ALREADY_LEARNED',case.ctx._world_magic_errors)

    def test_full_heal_uses_real_hp_clamp_and_cost(self):
        self.pc.hp=1;before=self.pc.hp
        self.cast(56)
        self.assertGreater(self.pc.hp,before);self.assertLessEqual(self.pc.hp,self.pc.max_hp)
        self.assertEqual(self.ctx._world_magic_events[-1]['amount'],self.pc.hp-before)

    def test_full_heal_normal_npc_and_undead_semantics(self):
        for undead in (0,1,3):
            target,group,slot=self.enemy(hp=10000)
            group.monster=replace(group.monster,undead=undead);slot.hp=5000
            self.cast(56,target.uid)
            self.assertEqual(self.ctx._world_magic_events[-1]['outcome'],{0:'healed',1:'undead_damage',3:'undead_immune'}[undead])
            self.assertTrue(slot.hp>5000 if undead==0 else slot.hp<5000 if undead==1 else slot.hp==5000)

    def test_blizzard_and_earthquake_use_distinct_official_caster_radii(self):
        for key,radius in ((58,10),(61,3)):
            near,_,a=self.enemy(x=100+radius);far,_,b=self.enemy(x=101+radius)
            before_a,before_b=a.hp,b.hp
            self.cast(key,None)
            self.assertLess(a.hp,before_a);self.assertEqual(b.hp,before_b)

    def test_invisibility_debits_exact_hp_stone_and_uses_existing_wire_without_fake_hud(self):
        hp=self.pc.hp;before=self.ctx.inventory_frame
        frames=self.cast(59)
        self.assertEqual(self.pc.hp,hp-25);self.assertTrue(self.magic.is_invisible(1,self.clock.now))
        self.assertNotEqual(self.ctx.inventory_frame,before)
        self.assertIn(feature.invisible_frame(1,True),frames)
        self.assertFalse(any(int.from_bytes(w[2:4],'little')==0x4e91 for w in frames))
        self.assertIsNone(self.magic.status(1,'invisibility',self.clock.now)['until'])

    def test_invisibility_zero_mp_ends_and_detection_clears_persistent_marker(self):
        self.cast(59);self.pc.status_fields[12]=0
        self.ctx._world_magic_tick(self.clock.now)
        self.assertFalse(self.magic.is_invisible(1,self.clock.now))
        self.pc.status_fields[12]=1000;self.cast(59)
        self.cast(12)
        self.assertFalse(self.magic.is_invisible(1,self.clock.now))
        self.assertNotIn('invisibility',self.magic.state(1).effects)

    def test_invisibility_roundtrip_and_teleport_replay_preserve_state(self):
        self.cast(59);saved=self.magic.snapshot(1,self.clock.now,wall=1000)
        cold=rules.PlayerMagic(rules.load_catalog());cold.restore(1,saved,500,wall=2000)
        self.assertTrue(cold.is_invisible(1,500))
        self.assertIn(feature.invisible_frame(1,True),self.ctx._world_magic_after_relocate(1,{}))

    def test_invisible_player_cannot_attack_or_cast_offensive_magic_but_can_move(self):
        feature._world_magic_consumers(self.ctx);self.addCleanup(self.ctx._world_magic_stopped)
        target,group,slot=self.enemy();self.cast(59)
        self.world.pc_attack(1,target.uid);self.assertEqual(slot.hp,10000)
        self.assertFalse(status.ai_status(self.magic.effects(1),self.clock.now)['blocked'])
        before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'INVISIBLE_ACTION_RESTRICTED'):self.cast(61)
        self.assertEqual(self.pc.mp,before)

    def test_resurrection_current_npc_corpse_hp_lifetime_and_reward_once(self):
        target,group,slot=self.enemy(hp=100)
        old=target.ref
        self.world._apply_monster_swing(1,1,target,group.monster,slot.hp,combat.Swing(True,slot.hp),self.clock.now)
        corpse=target.ref;earned=len(self.world.combat.kills)
        self.assertNotEqual(corpse,old);self.assertFalse(target.alive)
        self.world.drain(1)
        frames=self.cast(60,target.uid)
        opcodes=[int.from_bytes(w[2:4],'little') for w in frames]
        self.assertLess(opcodes.index(0x4e96),opcodes.index(0x4ed8))
        self.assertTrue(target.alive);self.assertEqual(slot.hp,25)
        self.assertIsNone(self.world.entities.resolve(corpse));self.assertIsNone(slot.corpse_at)
        self.world._apply_monster_swing(1,1,target,group.monster,slot.hp,combat.Swing(True,slot.hp),self.clock.now)
        self.assertEqual(len(self.world.combat.kills),earned)

    def test_resurrection_rejects_living_removed_and_unsupported_pc_before_cost(self):
        target,_,_=self.enemy();before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'DEAD_TARGET_REQUIRED'):self.cast(60,target.uid)
        self.assertEqual(self.pc.mp,before)
        self.world.bind_pc(2,self.pc.profile,{**self.pc.status_fields,1:2,10:0})
        self.world.update_pc(2,0,102,100);self.world.entities.kill(2)
        self.world.pc_known.setdefault(1,set()).add(2)  # current PC fixture publication
        with self.assertRaisesRegex(ValueError,'PC_ACCEPTANCE_OR_NPC_OWNER_UNAVAILABLE'):self.cast(60,2)
        self.assertEqual(self.pc.mp,before)

    def test_resurrection_registered_companion_reuses_existing_saved_revive(self):
        from tools.local_original_session.world_companion_revive_tests import CompanionReviveTests
        from tools.local_original_session.world_feature_companion import _companion_magic_resurrection
        f=CompanionReviveTests();f.setUp();self.addCleanup(f.doCleanups)
        f.ctx._companion_enabled=True;f.die()
        action=_companion_magic_resurrection(f.ctx,1,f.actor.ref.uid)
        self.assertEqual(action(f.fixture.now),max(1,f.record.max_hp//4))
        self.assertTrue(f.record.alive);self.assertTrue(f.store.payload['records'][0]['alive'])

    def test_silence_self_receiver_hud_expiry_and_cast_block_without_monster_feature(self):
        with patch.object(status,'probability',return_value=True):frames=self.cast(63)
        self.assertIn(items.buff_icon_frame(63,824,10),frames)
        before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'CASTER_SILENCED'):self.cast(56)
        self.assertEqual(self.pc.mp,before)
        self.clock.now+=11;self.magic.expire(self.clock.now);self.cast(56)

    def test_silence_failure_still_pays_once_and_counter_absorbs(self):
        target,group,slot=self.enemy()
        with patch.object(status,'probability',return_value=False):self.cast(63,target.uid)
        self.assertIsNone(self.magic.status(target.uid,'silence',self.clock.now))
        self.assertEqual(self.ctx._world_magic_events[-1]['outcome'],'failed')
        self.magic.apply_status(target.uid,'counter_magic',self.clock.now,30,spell=30,target_ref=target.ref)
        with patch.object(status,'probability',return_value=True):self.cast(63,target.uid)
        self.assertIsNone(self.magic.status(target.uid,'silence',self.clock.now))
        self.assertIsNone(self.magic.status(target.uid,'counter_magic',self.clock.now))

    def test_silence_restore_and_teleport_replay_keep_deadline(self):
        with patch.object(status,'probability',return_value=True):self.cast(63)
        row=self.magic.snapshot(1,self.clock.now,wall=1000)
        cold=rules.PlayerMagic(rules.load_catalog());cold.restore(1,row,500,wall=1003)
        self.assertEqual(cold.status(1,'silence',500)['until'],507)
        self.assertIn(items.buff_icon_frame(63,824,10),self.ctx._world_magic_after_relocate(1,{}))

    def test_silence_blocks_both_actual_npc_spell_selectors_before_mp_spend(self):
        target,group,_=self.enemy()
        self.ctx._world_magic_npc_spells={group.monster.l1j_npcid:(object(),)}
        self.magic.apply_status(target.uid,'silence',self.clock.now,16,spell=63,target_ref=target.ref)
        mana=self.ctx._world_magic_npc_resources.mana_of(target.ref,group.monster.mp)
        self.assertIsNone(self.ctx._world_magic_npc_swing(group.monster,1,target.ref,self.clock.now))
        self.assertEqual(self.ctx._world_magic_npc_resources.mana_of(target.ref,group.monster.mp),mana)
        from tools.local_original_session.monster_skills_tests import MonsterSkillsTests
        f=MonsterSkillsTests();f.setUp();self.addCleanup(f.tearDown)
        row=next(r for rows in f.owner.attacks.values() for r in rows if r['kind']=='magic')
        monster,pc=f.configure(row)
        f.magic.apply_status(f.entity.uid,'silence',f.clock(),16,spell=63,target_ref=f.entity.ref)
        mana=f.owner.resources.mana_of(f.entity.ref,monster.mp)
        self.assertFalse(f.owner.cast(f.entity,monster,pc,row,f.clock()))
        self.assertEqual(f.owner.resources.mana_of(f.entity.ref,monster.mp),mana)


if __name__=='__main__':unittest.main()
