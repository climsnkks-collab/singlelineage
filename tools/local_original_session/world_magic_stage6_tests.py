"""Stage6 development checks, with existing world/kit/timed-effect owners.

These invoke the real cast handler but use unit-fixture readiness; they are
not normal-login packets or evidence of native screen behavior.
"""
from types import SimpleNamespace, MethodType
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, world_magic as rules
from tools.local_original_session import world_magic_status as status
from tools.local_original_session import world_feature_magic as feature
from tools.local_original_session import world_item_effects as items
from tools.local_original_session import world_magic_tests as fixtures


class Stage6Tests(unittest.TestCase):
    def setUp(self):
        self.owner = fixtures.WorldConsumerTests()
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)
        self.owner.prepare_new_tiers()
        self.ctx, self.world, self.magic = self.owner.ctx, self.owner.view, self.owner.magic
        self.pc, self.clock = self.owner.state, self.owner.fixture
        self.ctx._world_magic_buff_ui = True
        self.effects = items.WorldItemEffects(self.world.combat)
        self.effects.world = self.world
        self.ctx._world_item_effects = self.effects
        self.ctx.inventory_frame = inventory.build_kit_frame([
            fixtures.fields(1000, 1, 1), fixtures.fields(1001, 166, 20)])
        self.ctx._inventory_kit_policy = inventory.KIT_POLICY
        self.ctx.broker = SimpleNamespace()
        self.commits = []
        def commit(uid, before, after):
            self.assertEqual(before, self.ctx.inventory_frame)
            self.commits.append((uid, before, after))
            return True
        self.ctx._world_replace_kit = commit
        collect, run = self.ctx.collect_sync_hooks, self.ctx.run_sync_hooks
        self.ctx.collect_sync_hooks = lambda name, *a, **kw: (
            (items._world_consumable_haste_target(self.ctx, *a),)
            if name == 'magic_haste_target' else collect(name, *a, **kw))
        def hooks(name, *args, **kwargs):
            if name == 'player_cancel_magic':
                items._world_consumable_cancel_magic(self.ctx, *args)
            return run(name, *args, **kwargs)
        self.ctx.run_sync_hooks = hooks
        self.ctx._world_magic_weapon_uid = lambda uid: 1000
        self.flush = patch('tools.local_original_session.world_bridge._flush_persist')
        self.immediate = patch('tools.local_original_session.world_bridge._immediate_inventory')
        self.flush.start(); self.immediate.start()
        self.addCleanup(self.flush.stop); self.addCleanup(self.immediate.stop)

    def cast(self, key, target=1):
        self.clock.now += 2
        before = self.pc.mp
        self.ctx._world_magic_cast(1, key, target, self.clock.now)
        self.assertEqual(before - self.pc.mp, self.magic.spells[key].mp)
        frames = self.world.drain(1)
        opcodes = {int.from_bytes(w[2:4], 'little') for w in frames}
        self.assertTrue({0x4e31, 0x4ed8} <= opcodes)
        return frames

    def test_official_stage6_costs_learning_and_zombie_remains_resource_safe(self):
        expected = {40:(35,2,3600),41:(40,0,1200),42:(40,0,1200),43:(40,2,0),
                    44:(25,0,0),45:(30,0,0),46:(25,1,30),47:(20,0,1200)}
        magic = rules.PlayerMagic(rules.load_catalog())
        for key,(mp,count,duration) in expected.items():
            spell=magic.spells[key]
            self.assertEqual((spell.mp, spell.duration), (mp,duration))
            self.assertEqual(spell.raw['hp_cost']['value'],0)
            self.assertEqual(sum(r['count'] for r in spell.raw['materials']['value']),count)
            self.assertEqual(spell.classes,{2:48,3:24})
            if key==40:
                with self.assertRaisesRegex(ValueError,'EFFECT_UNSUPPORTED'):
                    magic.learn(1,spell,3,24)
            else:
                self.assertEqual(magic.learn(1,spell,3,24),{key})
                with self.assertRaisesRegex(ValueError,'LEVEL_TOO_LOW'):
                    magic.learn(1,spell,3,23)
        self.assertFalse(magic.state(1).learned)

    def test_remove_curse_clears_pc_npc_poison_and_requested_debuffs_preserves_buff(self):
        target=self.owner.enemy()
        for uid,ref in ((1,None),(target.uid,target.ref)):
            for kind in ('blind','paralyze','darkness','slow','weakness','curse'):
                self.magic.apply_status(uid,kind,self.clock.now,30,spell=46 if kind=='weakness' else 28,
                    target_ref=ref,params={'melee_hit':-2,'melee_damage':-4})
            self.ctx._world_magic_apply_poison(uid,1,self.clock.now)
            if uid==1:
                # A second caster can remove paralysis; the self test starts
                # before its onset, then proves the scheduled row is removed.
                self.magic.effects(uid)['paralyze']['starts_at']=self.clock.now+5
                self.magic.committed(1,self.magic.spells[2],self.clock.now)
            self.cast(36,uid)
            self.assertFalse(self.magic.effects(uid))
            self.assertFalse(self.magic.is_poisoned(uid,self.clock.now))
        self.assertIn(2,self.magic.state(1).buffs)

    def test_mighty_real_stats_hud_relocation_restore_and_expiry(self):
        from tools.local_original_session import world_stats
        base=world_stats.calculate_stats(world_stats.CharacterStats(30,3,
            world_stats.Attributes(12,12,12,12,12,18)),())
        self.owner.use_core_stats(base)
        frames=self.cast(41)
        actual=self.ctx._world_stats_for(SimpleNamespace(uid=1,name='MagicMage'))[0]
        self.assertEqual(actual.attributes.strength,17)
        self.assertIn(items.buff_icon_frame(41,482,10),frames)
        until=self.magic.state(1).buffs[41]
        self.ctx._world_magic_after_relocate(1,{})
        self.assertEqual(self.magic.state(1).buffs[41],until)
        row=self.magic.snapshot(1,self.clock.now,wall=1000)
        self.magic.restore(1,row,self.clock.now,wall=1003)
        self.assertEqual(self.magic.strength_bonus(1,self.clock.now),5)
        self.clock.now+=8
        self.ctx._world_magic_tick(self.clock.now)
        self.assertEqual(self.magic.strength_bonus(1,self.clock.now),0)

    def test_haste_uses_potion_state_adds_duration_without_rate_stacking_and_slow_neutralizes(self):
        rate=self.world.data.items[17].buff.rate
        expiry=self.clock.now+100
        self.pc.buffs['haste']=(expiry,rate)
        frames=self.cast(42)
        self.assertEqual(self.pc.buffs['haste'],(expiry+10,rate))
        self.assertEqual(self.world.combat.speed_factor(1,self.clock.now),rate)
        remaining=self.pc.buffs['haste'][0]-self.clock.now
        self.assertIn(items.buff_icon_frame(223,481,remaining),frames)
        self.assertEqual(set(self.effects.state(1).potions),{17})
        saved=items.consumable_snapshot(1,self.effects.state(1),self.clock.now,wall=1000)
        restored=items.consumable_restore(saved,self.clock.now+50,wall=1003)
        # Existing potion owner pauses saved potion time while disconnected.
        self.assertAlmostEqual(restored.potions[17],remaining)
        self.magic.apply_status(1,'slow',self.clock.now,30,spell=28,
                                params={'interval_multiplier':2})
        self.cast(42)
        self.assertNotIn('haste',self.pc.buffs)
        self.assertIsNone(self.magic.status(1,'slow',self.clock.now))
        self.assertEqual(self.world.combat.speed_factor(1,self.clock.now),1)

    def test_haste_npc_generation_bound_and_cancelled(self):
        target=self.owner.enemy()
        self.cast(42,target.uid)
        self.assertEqual(status.ai_status(self.magic.npc_statuses[target.uid]['effects'],self.clock.now)['move_factor'],
                         self.world.data.items[17].buff.rate)
        with patch.object(status,'probability',return_value=True): self.cast(43,target.uid)
        self.assertFalse(self.magic.effects(target.uid))

    def test_cancel_self_clears_magic_and_consumable_owners_keeps_learning_reuse_weapon_damage(self):
        self.cast(41); self.cast(42); self.cast(47)
        self.magic.apply_status(1,'weapon_break',self.clock.now,None,spell=26,params={'weapon_uid':1000})
        self.magic.apply_status(1,'weakness',self.clock.now,30,spell=46,params={'melee_hit':-2,'melee_damage':-4})
        self.ctx._world_magic_apply_poison(1,1,self.clock.now)
        learned=set(self.magic.state(1).learned)
        self.cast(43)
        self.assertFalse(self.magic.state(1).buffs)
        self.assertEqual(set(self.magic.state(1).effects),{'weapon_break'})
        self.assertFalse(self.pc.buffs)
        self.assertFalse(self.effects.state(1).potions)
        self.assertEqual(self.magic.state(1).learned,learned)
        self.assertGreater(self.magic.state(1).next_cast_at,self.clock.now)
        self.assertEqual(len(self.commits),1)

    def test_eruption_sunburst_damage_hp_and_display_with_display_switch_off(self):
        for key in (44,45):
            target=self.owner.enemy()
            before=self.world.spawner.slot_for(target.uid)[1].hp
            with patch.dict('os.environ',SL_SPELL_EXP='0'):
                self.cast(key,target.uid)
            self.assertLess(self.world.spawner.slot_for(target.uid)[1].hp,before)

    def test_weakness_real_npc_physical_input_and_pc_melee_only_expiry(self):
        target=self.owner.enemy()
        self.world.entities.move(target.uid,0,101,100)
        with patch.object(status,'probability',return_value=True): self.cast(46,target.uid)
        effect=self.magic.status(target.uid,'weakness',self.clock.now)
        original=self.world.spawner.slot_for(target.uid)[0].monster
        adapted=status.physical_monster(original,effect)
        self.assertEqual(adapted.level,original.level-2)
        self.assertEqual(adapted.damage.min,original.damage.min-4)
        self.assertEqual(adapted.damage.max,original.damage.max-4)
        self.assertEqual(original,self.world.spawner.slot_for(target.uid)[0].monster)
        with patch.object(status,'probability',return_value=True): self.cast(46,1)
        profile=self.pc.profile
        melee=self.ctx._world_magic_combat_profile(1,profile,self.clock.now)
        ranged=self.ctx._world_magic_combat_profile(1,profile,self.clock.now,ranged=True)
        self.assertEqual(melee.weapon.hit,profile.weapon.hit-2)
        self.assertEqual(melee.weapon.damage,profile.weapon.damage-4)
        self.assertEqual(ranged,profile)
        self.assertIsNone(self.magic.status(1,'weakness',self.clock.now+11))

    def test_bless_weapon_uid_binding_melee_bonus_exclusivity_and_expiry(self):
        self.magic.apply_buff(1,self.magic.spells[7],self.clock.now,weapon_uid=1000)
        self.cast(47)
        self.assertNotIn(7,self.magic.state(1).buffs)
        base=self.pc.profile
        boosted=self.ctx._world_magic_combat_profile(1,base,self.clock.now)
        self.assertEqual((boosted.weapon.hit-base.weapon.hit,boosted.weapon.damage-base.weapon.damage),(2,2))
        self.assertEqual(self.ctx._world_magic_combat_profile(1,base,self.clock.now,ranged=True),base)
        self.ctx._world_magic_weapon_uid=lambda uid:1002
        self.assertEqual(self.ctx._world_magic_combat_profile(1,base,self.clock.now),base)

    def test_cancel_preserves_name_joined_uncancelable_buffs_and_shock_stun(self):
        state=self.magic.state(1)
        for key in (11,13,87,89,90):
            state.buffs[key]=self.clock.now+60
        state.weapon_uids[11]=1000
        state.armor_uids[13]=1002
        self.magic.apply_status(1,'stun',self.clock.now,30,spell=86,onset=20)
        self.cast(43)
        self.assertEqual(set(state.buffs),{11,13,87,89,90})
        self.assertIn('stun',state.effects)
        self.assertEqual(state.weapon_uids,{11:1000})
        self.assertEqual(state.armor_uids,{13:1002})

    def test_cancel_polymorph_restores_real_original_and_cancels_existing_timer(self):
        from tools.local_original_session import world_feature_items as item_feature
        from tools.local_original_session import world_polymorph as poly, world_combat
        base=world_combat.PC_SPRITES[(3,0)]
        form=poly.use_scroll(poly.initial_appearance(base),poly.load_polymorphs(),
            item_template_id=299,grade=1,form_key='orc',character_level=30,
            now_ms=int(self.clock.now*1000),weapon_type='sword')
        self.assertTrue(form.allowed)
        ctx=self.ctx
        ctx._world_polymorphs={1:form.state}
        timer=self.world.runtime.scheduler.schedule(self.clock.now+1800,None,'pc_polymorph',lambda now:None)
        ctx._world_poly_timers={1:timer}
        ctx._world_stance_for=lambda uid:0
        for fn in (item_feature._world_expire_polymorph,item_feature._world_polymorph_frame):
            setattr(ctx,fn.__name__,MethodType(fn,ctx))
        previous=ctx.run_sync_hooks
        def hooks(name,*args,**kwargs):
            if name=='player_cancel_magic': item_feature._world_items_cancel_magic(ctx,*args)
            return previous(name,*args,**kwargs)
        ctx.run_sync_hooks=hooks
        frames=self.cast(43)
        self.assertFalse(ctx._world_polymorphs)
        self.assertFalse(ctx._world_poly_timers)
        self.assertTrue(timer.cancelled)
        self.assertIn(ctx._world_polymorph_frame(1,base),frames)

    def test_bless_and_weakness_saved_deadlines_hud_replay_after_relocation(self):
        self.cast(47)
        with patch.object(status,'probability',return_value=True): self.cast(46,1)
        now=self.clock.now
        until=self.magic.state(1).buffs[47]
        frames=self.ctx._world_magic_after_relocate(1,{})
        self.assertIn(items.buff_icon_frame(47,728,until-now),frames)
        self.assertIn(items.buff_icon_frame(46,852,10),frames)
        saved=self.magic.snapshot(1,now,wall=1000)
        self.magic.restore(1,saved,now+50,wall=1003)
        self.assertEqual(self.magic.state(1).weapon_uids[47],1000)
        self.assertEqual(self.magic.status(1,'weakness',now+50)['until'],now+57)
        self.assertEqual(self.magic.state(1).buffs[47],until+47)

    def test_missing_catalyst_and_insufficient_mp_do_not_mutate_resources(self):
        self.ctx.inventory_frame=inventory.build_kit_frame([fixtures.fields(1000,1,1)])
        before=self.pc.mp
        with self.assertRaisesRegex(ValueError,'CURRENT_CATALYST_REQUIRED'): self.cast(43)
        self.assertEqual(self.pc.mp,before)
        self.assertFalse(self.commits)
        self.pc.status_fields[12]=1
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_MP'): self.cast(41)
        self.assertEqual(self.pc.mp,1)


if __name__=='__main__': unittest.main()
