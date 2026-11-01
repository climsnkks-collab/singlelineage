"""Stage10 development checks; independent saves, no game or hunt_bot."""
import asyncio
from dataclasses import replace
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tools.local_original_session import inventory, world_magic as rules
from tools.local_original_session import world_feature_magic as feature, world_core_stats as core
from tools.local_original_session import world_stats, world_item_effects as items
from tools.local_original_session.world_status_frames import effect_frame
from tools.local_original_session import world_magic_stage6_tests as fixtures


class Stage10Tests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.Stage6Tests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.ctx, self.world, self.magic = self.f.ctx, self.f.world, self.f.magic
        self.pc, self.clock = self.f.pc, self.f.clock
        self.pc.profile = replace(self.pc.profile, level=60)

    def cast(self, key, target=1):
        return self.f.cast(key, target)

    def enemy(self, x=103, y=100, hp=10000):
        entity = self.f.owner.enemy()
        group, slot = self.world.spawner.slot_for(entity.uid)
        group.monster = replace(group.monster, hp=hp); slot.hp = hp
        self.world.entities.move(entity.uid, 0, x, y); self.world._refresh(1)
        return entity, slot

    def resources(self, hp=1003, mp=1504):
        self.pc.max_hp = hp; self.pc.status_fields.update({11: hp, 12: mp, 13: mp})
        self.pc = core._resource_state(self.pc)
        self.world.combat.pcs[1] = self.pc
        self.f.pc = self.f.owner.state = self.pc
        calculated = world_stats.calculate_stats(world_stats.CharacterStats(60, 3,
            world_stats.Attributes(12, 12, 18, 18, 8, 25)), ())
        self.f.owner.use_core_stats(calculated, {5: 0, 18: 0})
        for fn in (core._world_recalculate_uid, core._world_pc_profile, core._world_fields_for):
            setattr(self.ctx, fn.__name__, MethodType(fn, self.ctx))
        self.ctx._world_recalculate_uid(1)

    def test_official_costs_level_and_source_priority(self):
        for key, book, mp, duration in ((73,225,60,0),(78,1491,20,1200)):
            spell = rules.PlayerMagic(rules.load_catalog()).spells[key]
            self.assertEqual((spell.book,spell.mp,spell.duration,spell.classes), (book,mp,duration,{3:40}))
            self.assertEqual((spell.raw['hp_cost']['value'],spell.raw['materials']['value']), (0,[]))
            self.assertEqual(self.magic.learn(99,spell,3,40),{key})
            for cls,level,error in ((3,39,'LEVEL_TOO_LOW'),(2,99,'CLASS_NOT_ALLOWED')):
                with self.assertRaisesRegex(ValueError,error):self.magic.learn(99,spell,cls,level)
            self.assertIsNone(spell.raw['cooldown_ms']['value'])
            self.assertIn('LOCAL',spell.raw['player_policy']['learning_place_condition']['runtime_policy'])
        self.assertEqual(self.magic.spells[73].raw['formula']['parameters']['damage_dice_count'],8)

    def test_each_book_real_handler_cas_save_available_and_duplicate_no_consumption(self):
        from tools.local_original_session.spellbook_learning_tests import LearningHandlerTests
        helper=LearningHandlerTests();self.addCleanup(helper.doCleanups)
        for key in (73,78):
            case=helper.fixture(self.magic.spells[key].book)
            self.assertTrue(asyncio.run(case.use()));self.assertEqual(case.engine.state(1).learned,{key})
            after=case.store.restore(1)
            self.assertEqual(next(dict(i.raw_fields)[4] for i in inventory.validate_kit_frame(after) if i.identifier==11),1)
            self.assertTrue(any(int.from_bytes(w[2:4],'little')==0x4e60 for w in case.sent))
            self.assertTrue(asyncio.run(case.use()));self.assertEqual(case.store.restore(1),after)
            self.assertIn('MAGIC_ALREADY_LEARNED',case.ctx._world_magic_errors)

    def test_meteor_actual_target_center_radius_cost_and_damage(self):
        target,a=self.enemy(x=110);near,b=self.enemy(x=113);far,c=self.enemy(x=114)
        hp=self.pc.hp;bag=self.ctx.inventory_frame
        frames=self.cast(73,target.uid)
        self.assertLess(a.hp,10000);self.assertLess(b.hp,10000);self.assertEqual(c.hp,10000)
        self.assertEqual(self.ctx._world_magic_events[-1]['amount'],20000-a.hp-b.hp)
        self.assertEqual(self.pc.hp,hp);self.assertEqual(self.ctx.inventory_frame,bag)
        self.assertIn(effect_frame(target.uid,762),frames)
        self.assertFalse(any(int.from_bytes(w[2:4],'little')==0x4e91 for w in frames))

    def test_meteor_no_target_self_far_and_stale_refuse_without_cost(self):
        for target in (None,1,0xdeadbeef):
            before=self.pc.mp
            with self.assertRaises(ValueError):self.cast(73,target)
            self.assertEqual(self.pc.mp,before)
        target,_=self.enemy(x=111);before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'OUT_OF_RANGE'):self.cast(73,target.uid)
        self.assertEqual(self.pc.mp,before)

    def test_meteor_counter_consumed_per_actual_victim(self):
        target,a=self.enemy();other,b=self.enemy(x=104)
        self.magic.apply_status(target.uid,'counter_magic',self.clock.now,30,spell=30,target_ref=target.ref)
        self.cast(73,target.uid)
        self.assertEqual(a.hp,10000);self.assertLess(b.hp,10000)
        self.assertIsNone(self.magic.status(target.uid,'counter_magic',self.clock.now))

    def test_reuse_and_insufficient_mp_preserve_resources(self):
        target,_=self.enemy();self.cast(73,target.uid);before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'REUSE'):self.ctx._world_magic_cast(1,73,target.uid,self.clock.now)
        self.assertEqual(self.pc.mp,before)
        self.pc.status_fields[12]=19;self.clock.now+=2
        with self.assertRaisesRegex(ValueError,'MP'):self.ctx._world_magic_cast(1,78,1,self.clock.now)
        self.assertNotIn(78,self.magic.state(1).buffs)

    def test_advance_real_caps_floor_and_no_current_refill_or_compounding(self):
        self.resources();hp,mp=self.pc.hp,self.pc.mp
        frames=self.cast(78)
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1203,1804))
        self.assertEqual((self.pc.hp,self.pc.mp),(hp,mp-20))
        self.assertIn(items.buff_icon_frame(78,1607,10),frames)
        self.assertIn(effect_frame(1,3935),frames)
        for _ in range(3):self.ctx._world_recalculate_uid(1)
        self.cast(78)
        self.assertEqual((self.pc.base_max_hp,self.pc.base_max_mp),(1003,1504))
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1203,1804))

    def test_advance_excludes_equipment_and_tracks_base_growth(self):
        self.resources();self.cast(78)
        growth=replace(self.world.progress.snapshot(1),max_hp=1013,max_mp=1514)
        self.world.progress.adopt(1,growth);self.ctx._world_recalculate_uid(1)
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1215,1816))
        from tools.local_original_session.world_magic_stage10 import resource_bonuses
        self.pc.equipment_hp_bonus+=100;self.pc.equipment_mp_bonus+=70
        self.assertEqual(resource_bonuses(self.ctx,(100,70),1,base=(1013,1514)),(302,372))

    def test_direct_reward_base_writes_update_both_percentages_in_the_same_refresh(self):
        self.resources();self.cast(78)
        self.pc.max_hp=1033;self.pc.status_fields.update({11:1033,13:1534})
        self.ctx._world_recalculate_uid(1)
        self.assertEqual((self.pc.base_max_hp,self.pc.base_max_mp),(1033,1534))
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1239,1840))

    def test_advance_self_only_before_cost(self):
        target,_=self.enemy();before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'OUT_OF_RANGE|SELF_TARGET_REQUIRED'):self.cast(78,target.uid)
        self.assertEqual(self.pc.mp,before);self.assertFalse(self.magic.state(1).buffs)

    def test_expiry_clamps_effective_resources_removes_icon_and_preserves_bases(self):
        self.resources();self.cast(78);self.pc.hp=1203;self.pc.status_fields[12]=1804
        self.clock.now+=11;self.ctx._world_magic_tick(self.clock.now)
        self.assertEqual((self.pc.max_hp,self.pc.max_mp,self.pc.hp,self.pc.mp),(1003,1504,1003,1504))
        self.assertIn(items.buff_icon_frame(78,1607,0,remove=True),self.world.drain(1))
        self.assertEqual((self.pc.base_max_hp,self.pc.base_max_mp),(1003,1504))

    def test_save_offline_elapsed_and_teleport_replay_keep_deadline_and_caps(self):
        self.resources();self.cast(78);deadline=self.magic.state(1).buffs[78]
        saved=self.magic.snapshot(1,self.clock.now,wall=1000)
        cold=rules.PlayerMagic(rules.load_catalog());cold.restore(1,saved,500,wall=1003)
        self.assertEqual(cold.state(1).buffs[78],507)
        frames=self.ctx._world_magic_after_relocate(1,{})
        self.assertIn(items.buff_icon_frame(78,1607,10),frames)
        self.assertEqual(self.magic.state(1).buffs[78],deadline)
        self.magic.restore(1,saved,self.clock.now,wall=1003);self.ctx._world_recalculate_uid(1)
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1203,1804))

    def test_real_saved_enter_republishes_remaining_hud_and_recalculates_caps(self):
        self.resources();self.cast(78)
        self.ctx._world_magic_writers[id(self.f.owner.writer)]=1
        self.ctx._world_magic_detach(self.f.owner.writer)
        self.clock.now+=3
        self.ctx._world_send=AsyncMock()
        asyncio.run(self.ctx._world_magic_enter(self.f.owner.writer,{},None,None))
        frames=self.ctx._world_send.await_args.args[2]
        self.assertIn(items.buff_icon_frame(78,1607,7),frames)
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1203,1804))

    def test_cold_initial_selfinfo_preserves_saved_current_above_base_without_base_drift(self):
        from tools.local_original_session.world_magic_stage10 import realm_status
        self.resources();self.cast(78)
        saved=self.magic.snapshot(1,self.clock.now)
        self.magic.states.pop(1);self.ctx._world_magic_store.rows[1]=saved
        self.world.combat.pcs.pop(1)
        self.ctx.realm._world_context=self.ctx
        self.ctx.realm._world_hp=lambda uid:1199
        self.ctx.realm._world_mp=lambda uid:1788
        # The core's early base clamp has happened; the registered projection
        # restores real saved current values before the effective-cap clamp.
        fields={**self.pc.status_fields,10:1003,11:1003,12:1504,13:1504}
        position=NS(uid=1,name='MagicMage')
        restored=realm_status(self.ctx.realm,fields,position,True)
        projected=self.ctx._world_fields_for(position,restored)
        self.assertEqual((projected[10],projected[11],projected[12],projected[13]),(1199,1203,1788,1804))
        self.assertEqual(self.ctx._world_equipment_pending[1][:2],(1003,1504))
        self.assertTrue(self.magic.active(1,'advance_spirit',self.clock.now))

    def test_actual_teleport_spell_keeps_advance_deadline_and_resource_bases(self):
        self.resources();self.cast(78);deadline=self.magic.state(1).buffs[78]
        self.magic.state(1).learned.add(4)
        row={'operation_lock':NS(locked=lambda:True)};game=object()
        self.ctx.realm.registry=NS(resolve=lambda writer:game)
        self.ctx.realm.serves_map=lambda map_id:True
        self.ctx._world_relocate_locked=Mock(return_value=())
        destination=items.MapDestination(0,110,110,0);self.clock.now+=2
        with patch.object(items,'random_destination',return_value=destination):
            self.ctx._world_magic_cast(1,4,None,self.clock.now,row=row,game=game)
        self.ctx._world_relocate_locked.assert_called_once()
        self.assertEqual(self.magic.state(1).buffs[78],deadline)
        self.assertEqual((self.pc.base_max_hp,self.pc.base_max_mp),(1003,1504))

    def test_death_clears_caps_and_player_cancel_preserves_named_exemption(self):
        self.resources();self.cast(78)
        self.ctx._world_magic_player_cancel(1,self.clock.now)
        self.assertIn(78,self.magic.state(1).buffs)
        self.ctx._world_magic_died(1);self.ctx._world_recalculate_uid(1)
        self.assertNotIn(78,self.magic.state(1).buffs)
        self.assertEqual((self.pc.max_hp,self.pc.max_mp),(1003,1504))

    def test_native_display_still_published_with_spell_experiment_off(self):
        target,_=self.enemy()
        with patch.dict('os.environ',{'SL_SPELL_EXP':'0'}):
            self.cast(73,target.uid);self.cast(78)


if __name__=='__main__':unittest.main()
