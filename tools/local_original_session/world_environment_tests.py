"""Underwater scheduler/lifetime checks; no game, ports or user saves."""
from types import SimpleNamespace
import random
import unittest

from tools.local_original_session import world_combat as wc
from tools.local_original_session.world_feature_environment import (
    WorldEnvironment, load_policy, _environment_started)
from tools.local_original_session.world_item_effects import (
    WorldItemEffects, _world_consumable_breathing, _world_consumable_died)
from tools.local_original_session.world_visibility import WorldView

PC = 65537


class EnvironmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 100.0
        self.view = WorldView.create(clock=lambda: self.now, rng=random.Random(7))
        fields = {1: PC, 2: 10, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
                  10: 200, 11: 200, 12: 100, 13: 100, 14: -10, 15: 1793000000,
                  16: 200, 17: 7, 18: -123, 20: 9}
        self.view.bind_pc(PC, wc.PcProfile(10, 3, 0, 13, 13), fields)
        self.view.pcs[PC] = (63, 32700, 32800)
        self.pc = self.view.combat.pcs[PC]
        self.effects = WorldItemEffects(self.view.combat)
        self.ctx = SimpleNamespace(_world_item_effects=self.effects, world=self.view)
        self.worn = ()
        self.owner = WorldEnvironment(self.view, load_policy(),
            equipped=lambda uid: self.worn,
            breathing=lambda uid, now: _world_consumable_breathing(self.ctx, uid, now))
        self.owner.start()
        self.deaths = []
        def died(uid):
            self.deaths.append(uid)
            _world_consumable_died(self.ctx, uid)
        self.view.on_pc_death = died

    async def asyncTearDown(self):
        self.view.close()
        self.owner.close()

    async def advance(self, count, activity=None):
        for _ in range(count):
            if activity is not None:
                self.view.combat.note_activity(PC, activity)
            self.now += 1
            await self.view.runtime.tick_once(self.now)

    async def test_underwater_enter_full_hp_then_real_activity_threshold(self):
        await self.advance(2)
        self.assertEqual(self.pc.hp, 200)
        await self.advance(1)
        self.assertEqual(self.pc.hp, 180)  # LOCAL damage after the existing cap
        await self.advance(5, self.view.combat.regen.move_points)
        self.assertEqual(self.pc.hp, 180)
        await self.advance(1, self.view.combat.regen.move_points)
        self.assertEqual(self.pc.hp, 161)  # base CON10 recovery1, damage20
        frames = self.view.drain(PC)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames], [0x4e38, 0x4e38])
        self.assertEqual(len(self.view.regen), 1)

    async def test_both_real_breath_items_prevent_damage_and_expiry_resumes(self):
        for template in (417, 418):
            self.pc.hp = 200
            result = self.effects.use(PC, template, self.now)
            self.assertEqual(result.outcome, 'applied')
            await self.advance(3)
            self.assertEqual(self.pc.hp, 200)
            # Use the actual item deadline, not a second expiry timer.
            self.now = self.effects.state(PC).breath_until
            await self.advance(3)
            self.assertEqual(self.pc.hp, 180)

    async def test_owned_equipped_boots_only_and_removal_resumes(self):
        self.worn = (551,)
        await self.advance(3)
        self.assertEqual(self.pc.hp, 200)
        self.worn = ()  # inventory may still contain the boots
        await self.advance(3)
        self.assertEqual(self.pc.hp, 180)

    async def test_map_exit_no_residual_damage_or_extra_timer_and_fafurion_enabled(self):
        await self.advance(3)
        self.view.pcs[PC] = (62, 32700, 32800)
        await self.advance(9)
        self.assertEqual(self.pc.hp, 183)
        self.view.pcs[PC] = (65, 32700, 32800)
        await self.advance(3)
        self.assertEqual(self.pc.hp, 164)
        self.view.leave_pc(PC)
        self.assertNotIn(PC, self.view.regen)
        await self.advance(30)
        self.assertNotIn(PC, self.view.combat.pcs)
        self.assertNotIn(PC, self.view.outbox)

    async def test_death_once_status_before_death_cancels_recovery_and_clears_breath(self):
        self.pc.hp = 1
        self.effects.state(PC).breath_until = self.now + .5
        self.effects.state(PC).wisdom_until = self.now + 100
        await self.advance(3)
        self.assertEqual((self.pc.hp, self.pc.dead, self.deaths), (0, True, [PC]))
        self.assertNotIn(PC, self.view.regen)
        self.assertEqual((self.effects.state(PC).breath_until,
                          self.effects.state(PC).wisdom_until), (0, 0))
        frames = self.view.drain(PC)
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames], [0x4e38, 0x4e39])
        await self.advance(100)
        self.assertEqual(self.deaths, [PC])
        self.assertEqual(self.view.drain(PC), [])

    async def test_runtime_close_removes_wrappers_and_feature_can_be_absent(self):
        self.owner.close()
        await self.advance(3)
        self.assertEqual(self.pc.hp, 200)
        self.assertNotIn('environment_companion_hp_recovery',
            {key for key, entries in self.view.events._callbacks.items() if entries})

    async def test_default_registry_context_starts_environment_and_queries_real_breath_hook(self):
        from types import MethodType
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_handlers import feature_registry
        self.owner.close()
        registry = feature_registry()
        host = SimpleNamespace(_world=self.view, _world_registry=registry,
                               _world_item_effects=self.effects)
        ctx = Context(host)
        for name in ('_environment_initialize', '_environment_started',
                     '_environment_stopped', '_world_consumable_breathing'):
            setattr(host, name, MethodType(registry.methods[name], ctx))
        ctx._environment_initialize()
        ctx._environment_started()
        self.owner = ctx._world_environment
        self.effects.use(PC, 418, self.now)
        self.assertTrue(ctx.chain_sync_hooks('environment_breathing', PC, self.now))
        await self.advance(3)
        self.assertEqual(self.pc.hp, 200)
        ctx._environment_stopped()
        self.assertFalse(self.owner.handles)

    async def test_equipment_provider_rejects_bag_only_and_zero_quantity(self):
        from tools.local_original_session import inventory
        self.owner.close()
        fields = {1: 9, 2: 551, 3: 0, 4: 1, 5: 0, 7: 704, 9: 0, 10: 0,
                  13: 0, 14: 0, 16: 0, 17: 0, 18: b'boots', 22: 0,
                  24: False, 25: 0, 26: False}
        frame = inventory.build_kit_frame([fields])
        state = SimpleNamespace(weapon_uid=0, slots=())
        store = SimpleNamespace(peek=lambda uid: (state, frame))
        ctx = SimpleNamespace(world=self.view, _world_environment_policy=load_policy(),
            _item_equipment_effect=SimpleNamespace(store=store),
            chain_sync_hooks=lambda *args: False)
        _environment_started(ctx)
        self.owner = ctx._world_environment
        await self.advance(3)
        self.assertEqual(self.pc.hp, 180)
        state.slots = ((7, 9),)
        self.assertEqual(self.owner.equipped(PC), (551,))
        fields[4] = 0
        frame = inventory.build_kit_frame([fields])
        self.assertEqual(self.owner.equipped(PC), ())


class CompanionEnvironmentTests(unittest.TestCase):
    def setUp(self):
        from tools.local_original_session.world_companion import CompanionRecord, WorldCompanions
        from tools.local_original_session.world_entities import EntityRegistry, Kind
        from tools.local_original_session.world_scheduler import Scheduler
        from tools.local_original_session.world_extensions import WorldEvents
        self.entities = EntityRegistry()
        self.scheduler = Scheduler(clock=lambda: 100, is_current=self.entities.is_current)
        self.followers = WorldCompanions(self.entities, self.scheduler)
        owner = self.entities.add(Kind.PC, 63, 10, 10, uid=PC)
        record = CompanionRecord(character_id=22, owner_character_id=11,
            account_id='a', hp=40, max_hp=40, mp=20, max_mp=20, exp=0,
            equipment={}, learned_spells=())
        self.followers.register(record, roster={11: {'account_id': 'a', 'class_id': 0},
            22: {'account_id': 'a', 'class_id': 3}})
        self.actor = self.followers.summon(22, owner.uid, 63, 11, 10)
        self.frames = []
        self.view = SimpleNamespace(entities=self.entities, closed=False,
            extensions={'followers': SimpleNamespace(companions=self.followers)},
            events=WorldEvents(), _watchers=lambda entity: [PC],
            _queue=lambda uid, frame: self.frames.append(frame))
        self.environment = WorldEnvironment(self.view, load_policy())

    def test_shared_breath_gear_exit_and_lethal_cancellation(self):
        self.assertEqual(self.environment.companion_recovery(self.actor, 100, breathing=True), 0)
        self.assertEqual(self.environment.companion_recovery(self.actor, 100, worn=(551,)), 0)
        self.entities.move(self.actor.ref.uid, 62, 11, 10)
        self.assertEqual(self.environment.companion_recovery(self.actor, 100), 0)
        self.entities.move(self.actor.ref.uid, 63, 11, 10)
        self.assertEqual(self.environment.companion_recovery(self.actor, 100), 20)
        called = []
        self.scheduler.schedule(101, self.actor.ref, 'companion-ai', called.append)
        self.assertEqual(self.environment.companion_recovery(self.actor, 100), 20)
        self.assertFalse(self.actor.record.alive)
        self.assertEqual(self.scheduler.run_due(101), 0)
        self.assertEqual(called, [])
        self.assertEqual(len(self.frames), 1)
        self.assertEqual(self.environment.companion_recovery(self.actor, 101), 0)
        self.assertEqual(len(self.frames), 1)

    def test_dismissed_lifetime_and_unmapped_reference_ids_get_no_authority(self):
        policy = load_policy()
        self.assertEqual(policy.maps, {63, 65})
        self.assertEqual(policy.damage_for(63, worn=(20207, 21048, 21049, 21050)), 20)
        self.assertEqual(policy.damage_for(63, exempt=True), 0)
        self.followers.dismiss(22, 100)
        self.assertEqual(self.environment.companion_recovery(self.actor, 100), 0)


if __name__ == '__main__':
    unittest.main()
