"""Pure fake-clock backend checks; no broker, socket, client or native PASS."""
from dataclasses import replace
import random
from types import SimpleNamespace
import unittest

from tools.local_original_session.companion_ai import AttackIntent, CompanionAI, State
from tools.local_original_session.game_data import Rect, load_m1
from tools.local_original_session.npc_ai import DELTAS, NpcAi, State as NpcState, distance
from tools.local_original_session.world_companion import CompanionRecord, WorldCompanions
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import InterestSpawner
from tools.local_original_session.world_runtime import WorldRuntime


DATA = load_m1()


class Terrain:
    def __init__(self, rule=lambda *_: True):
        self.rule = rule

    def can_step(self, *args):
        return self.rule(*args)


class CompanionAiTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.runtime = WorldRuntime(clock=lambda: self.now)
        self.entities = self.runtime.entities
        self.owner = self.entities.add(Kind.PC, 0, 100, 100, uid=1)
        spec = replace(DATA.spawns[0], rect=Rect(110, 100, 110, 100), target_count=1)
        spec2 = replace(spec, group_id='companion-test-second', rect=Rect(109, 101, 109, 101))
        data = replace(DATA, spawns=(spec, spec2))
        spawner = InterestSpawner(self.entities, data, passable=lambda *_: True,
                                  rng=random.Random(1))
        self.intents, self.moves, self.npc_attacks = [], [], []
        self.view = SimpleNamespace(
            runtime=self.runtime, entities=self.entities, spawner=spawner, terrain=Terrain(),
            pcs={1: (0, 100, 100)}, combat=SimpleNamespace(can_be_attacked=lambda uid: uid == 1))
        spawner.update_interest(self.view.pcs.values(), self.now)
        self.mob = self.entities.get(spawner.groups[0].slots[0].uid)
        self.second_mob = self.entities.get(spawner.groups[1].slots[0].uid)
        self.view.npc_step = self.move_npc
        self.view.npc_attack = lambda actor, monster, target_uid, now: self.npc_attacks.append(
            (actor.ref, target_uid, now))
        self.npc_ai = NpcAi(self.view, random.Random(4))
        self.view.ai = self.npc_ai
        self.npc_ai.sync(self.now)
        self.manager = WorldCompanions(self.entities, self.runtime.scheduler,
                                       release_target=self.npc_ai.release_target)
        self.view.companions = self.manager
        self.view.ai_target = self.manager.can_be_attacked
        self.record = CompanionRecord(2, 1, 'account', hp=20, max_hp=20, mp=10, max_mp=10)
        roster = {1: {'account_id': 'account', 'class_id': 0},
                  2: {'account_id': 'account', 'class_id': 3}}
        self.manager.register(self.record, roster=roster)
        self.companion = self.manager.summon(2, 1, 0, 95, 100)
        self.actor = self.entities.resolve(self.companion.ref)
        # These numbers are caller test inputs, not production speed claims.
        self.ai = CompanionAI(self.view, move_interval=0.5, attack_interval=1.25,
                              tick_interval=0.25, attack_consumer=self.intents.append,
                              move_consumer=self.move_companion)

    def move_companion(self, actor, x, y, heading):
        self.moves.append((self.now, actor.ref, x, y))
        self.entities.move(actor.uid, actor.map_id, x, y, heading)

    def move_npc(self, actor, x, y, heading):
        self.entities.move(actor.uid, actor.map_id, x, y, heading)

    def place(self, actor, x, y, map_id=0):
        self.entities.move(actor.uid, map_id, x, y)
        if actor.uid == 1:
            self.view.pcs[1] = (map_id, x, y)

    def run_due(self, at=None):
        if at is not None:
            self.now = at
        return self.runtime.scheduler.run_due(self.now)

    def commands(self, **changes):
        self.manager.set_commands(2, now=self.now, **changes)
        self.ai.command_changed(self.companion.ref, self.now)

    def test_summon_follow_hold_and_resume(self):
        self.ai.start(self.companion.ref, self.now)
        self.run_due()
        self.assertEqual(len(self.moves), 1)
        self.assertEqual(distance(self.actor.x, self.actor.y, self.owner.x, self.owner.y), 4)
        self.assertEqual(self.companion.action, State.FOLLOW.value)
        self.commands(movement_mode='HOLD')
        self.run_due(104)
        self.assertEqual((len(self.moves), self.companion.action), (1, 'HOLD'))
        self.commands(movement_mode='FOLLOW')
        self.run_due()
        self.assertEqual(len(self.moves), 2)

    def test_late_scheduler_moves_once_and_uses_own_interval(self):
        self.ai.start(self.companion.ref, self.now)
        self.run_due()
        self.run_due(100.25)
        self.assertEqual(len(self.moves), 1)
        self.run_due(120)
        self.assertEqual(len(self.moves), 2)
        self.assertEqual(self.companion.next_move_at, 120.5)
        self.assertEqual(self.companion.handle.owner, self.companion.ref)
        self.assertEqual(self.companion.handle.at, 120.25)

    def test_assist_intent_repeats_switches_target_and_never_changes_resources(self):
        self.place(self.actor, 109, 100)
        before = self.record.hp, self.record.mp
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.run_due()
        self.assertEqual(self.intents, [AttackIntent(self.actor.ref, self.mob.ref, 100)])
        self.assertEqual(self.companion.action, 'ATTACK')
        self.run_due(100.25)
        self.assertEqual(len(self.intents), 1)
        self.run_due(101.25)
        self.assertEqual(len(self.intents), 2)
        self.run_due(120)
        self.assertEqual(len(self.intents), 3)
        self.assertEqual(self.companion.next_attack_at, 121.25)
        self.assertEqual((self.record.hp, self.record.mp), before)

        # A second real spawned target replaces the first without haste reset.
        second = self.second_mob
        self.ai.owner_attacked(self.owner.ref, second.ref, self.now)
        self.run_due()
        self.assertEqual((self.companion.target, len(self.intents)), (second.ref, 3))
        self.run_due(121.25)
        self.assertEqual(self.intents[-1].target_ref, second.ref)

    def test_step_returns_intent_without_consumer(self):
        self.ai.attack_consumer = None
        self.place(self.actor, 109, 100)
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        intent = self.ai.step(self.actor.ref, self.now)
        self.assertEqual(intent, AttackIntent(self.actor.ref, self.mob.ref, self.now))
        self.assertEqual(self.intents, [])

    def test_defend_owner_and_self_events_only(self):
        self.commands(combat_mode='DEFEND')
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.assertIsNone(self.companion.target)
        self.ai.on_hit(self.owner.ref, self.mob.ref, self.now)
        self.assertEqual(self.companion.target, self.mob.ref)
        self.commands(combat_mode='DEFEND')
        self.ai.on_hit(self.actor.ref, self.mob.ref, self.now)
        self.assertEqual(self.companion.target, self.mob.ref)
        self.commands(combat_mode='PASSIVE')
        self.ai.on_hit(self.actor.ref, self.mob.ref, self.now)
        self.assertIsNone(self.companion.target)

    def test_hold_forbids_follow_and_chase_but_allows_in_range_intent(self):
        self.commands(movement_mode='HOLD')
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.run_due()
        self.run_due(102)
        self.assertEqual((self.moves, self.intents), ([], []))
        self.place(self.actor, 109, 100)
        self.run_due(102.25)
        self.assertEqual((len(self.intents), self.moves), (1, []))

    def test_command_change_clears_target_and_cancels_old_callback(self):
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        old_handle = self.companion.handle
        self.commands(movement_mode='HOLD')
        self.assertTrue(old_handle.cancelled)
        self.run_due()
        self.assertIsNone(self.companion.target)
        self.assertEqual((self.moves, self.intents), ([], []))

    def test_target_death_and_generation_invalid_stop_attack(self):
        self.place(self.actor, 109, 100)
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.run_due()
        self.entities.kill(self.mob.uid)
        self.run_due(102)
        self.assertIsNone(self.companion.target)
        self.assertEqual(len(self.intents), 1)

    def test_stale_target_ref_cannot_select_current_generation(self):
        old = self.mob.ref
        self.mob.generation += 1
        self.ai.owner_attacked(self.owner.ref, old, self.now)
        self.assertIsNone(self.companion.target)

    def test_non_hostile_and_ally_targets_are_refused(self):
        item = self.entities.add(Kind.ITEM, 0, 96, 100)
        town = self.entities.add(Kind.NPC, 0, 97, 100)
        for target in (self.owner, self.actor, item, town):
            with self.subTest(kind=target.kind, uid=target.uid):
                self.ai.owner_attacked(self.owner.ref, target.ref, self.now)
                self.assertIsNone(self.companion.target)
        self.view.spawner.groups[0].active = False
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.assertIsNone(self.companion.target)
        self.assertTrue(self.manager.are_allies(self.owner.uid, self.actor.uid))
        self.assertTrue(self.manager.are_allies(self.actor.uid, self.owner.uid))

    def test_owner_offline_map_death_or_generation_departure_dismisses(self):
        # Separate real manager/registry instances avoid reusing dead UIDs.
        for mode in ('offline', 'map', 'dead', 'combat_dead', 'generation'):
            with self.subTest(mode=mode):
                self.setUp()
                old = self.actor.ref
                self.ai.start(old, self.now)
                if mode == 'offline':
                    self.view.pcs.clear()
                elif mode == 'map':
                    self.place(self.owner, 100, 100, map_id=1)
                elif mode == 'dead':
                    self.entities.kill(self.owner.uid)
                elif mode == 'combat_dead':
                    # Existing WorldView._pc_died retains an alive registry PC.
                    self.view.combat.can_be_attacked = lambda uid: False
                else:
                    self.owner.generation += 1
                self.run_due()
                self.assertNotIn(2, self.manager.active)
                self.assertIsNone(self.entities.get(old.uid))
                self.assertEqual(self.intents, [])

    def test_invalid_actor_generation_is_cleaned_without_reviving(self):
        old = self.actor.ref
        self.actor.generation += 1
        self.ai.step(old, self.now)
        self.assertNotIn(2, self.manager.active)
        self.assertIsNone(self.entities.get(old.uid))
        self.assertTrue(self.record.alive)

    def test_dismiss_resummon_fresh_uid_does_not_run_old_callback(self):
        old = self.companion
        self.ai.start(old.ref, self.now)
        self.manager.dismiss(2, self.now)
        new = self.manager.summon(2, 1, 0, 94, 100)
        self.assertNotEqual(old.ref.uid, new.ref.uid)
        self.run_due(130)
        self.assertEqual((self.moves, self.intents), ([], []))
        self.ai.start(new.ref, self.now)
        self.run_due()
        self.assertEqual(len(self.moves), 1)

    def test_owner_leash_returns_one_step_without_teleport(self):
        self.place(self.actor, 80, 100)
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.run_due()
        self.assertEqual((self.companion.action, self.companion.target), ('RETURN', None))
        self.assertEqual(distance(80, 100, self.actor.x, self.actor.y), 1)

    def test_unknown_or_walled_terrain_blocks_motion_and_attack(self):
        for result in (None, False):
            with self.subTest(result=result):
                self.view.terrain = Terrain(lambda *_: result)
                self.ai.step(self.actor.ref, self.now)
                self.place(self.actor, 109, 100)
                self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
                self.ai.step(self.actor.ref, self.now)
                self.assertEqual((self.moves, self.intents), ([], []))

    def test_every_actor_and_corpse_blocks_path_but_items_do_not(self):
        for heading, (dx, dy) in enumerate(DELTAS):
            other = self.entities.add(Kind.PC if heading % 2 else Kind.NPC,
                                      0, self.actor.x + dx, self.actor.y + dy)
            if heading == 2:
                self.entities.kill(other.uid)
        self.ai.step(self.actor.ref, self.now)
        self.assertEqual(self.moves, [])
        # Remove the corpse east, replacing it with an item on that same tile.
        east = self.entities.near(0, 96, 100, 0, alive_only=False)[0]
        self.entities.remove(east.uid)
        self.entities.add(Kind.ITEM, 0, 96, 100)
        self.now += 0.5
        self.ai.step(self.actor.ref, self.now)
        self.assertEqual((self.actor.x, self.actor.y), (96, 100))

    def test_npc_retaliates_and_chases_companion_then_death_releases_immediately(self):
        self.view.combat.can_be_attacked = lambda uid: uid == 1  # PC predicate rejects companions
        self.place(self.actor, 105, 100)
        self.npc_ai.on_hit(self.mob.uid, self.actor.uid, self.now)
        brain = self.npc_ai.brains[self.mob.uid]
        self.assertEqual(brain.target_ref, self.actor.ref)
        self.run_due()
        self.assertIn(brain.state, (NpcState.CHASE, NpcState.ATTACK))
        self.place(self.actor, self.mob.x + 1, self.mob.y)
        self.run_due(max(self.now + 1, brain.next_move_at))
        self.assertEqual(self.npc_attacks[-1][1], self.actor.uid)
        self.ai.start(self.actor.ref, self.now)
        self.manager.die(2, self.now)
        self.assertEqual((brain.target, brain.target_ref, brain.state), (None, None, NpcState.RETURN))
        self.assertIsNotNone(brain.handle)
        self.assertIsNone(self.companion.handle)
        self.ai.step(self.companion.ref, self.now)
        self.assertEqual(self.companion.action, 'DEAD')
        self.ai.command_changed(self.companion.ref, self.now)
        self.assertEqual(self.companion.action, 'DEAD')
        self.assertIsNone(self.companion.handle)
        self.assertFalse(self.manager.can_be_attacked(self.actor.uid))
        with self.assertRaises(ValueError):
            self.manager.summon(2, 1, 0, 99, 100)

    def test_npc_perception_admits_only_registered_companions_and_pc(self):
        brain = self.npc_ai.brains[self.mob.uid]
        brain.monster = replace(brain.monster, aggressive=True)
        self.view.combat.can_be_attacked = lambda uid: False
        self.place(self.actor, 109, 100)
        town = self.entities.add(Kind.NPC, 0, 110, 101)
        item = self.entities.add(Kind.ITEM, 0, 110, 99)
        self.npc_ai.sync(self.now)
        self.assertEqual(brain.target, self.actor.uid)
        self.assertFalse(self.npc_ai._pc_ok(self.mob, town.uid))
        self.assertFalse(self.npc_ai._pc_ok(self.mob, item.uid))

    def test_npc_rejects_unregistered_actor_hit_and_stale_companion_generation(self):
        brain = self.npc_ai.brains[self.mob.uid]
        town = self.entities.add(Kind.NPC, 0, 109, 100)
        self.npc_ai.on_hit(self.mob.uid, town.uid, self.now)
        self.assertIsNone(brain.target)
        self.place(self.actor, 109, 100)
        self.npc_ai.on_hit(self.mob.uid, self.actor.uid, self.now)
        self.actor.generation += 1
        self.run_due()
        self.assertIsNone(brain.target)
        self.assertEqual(self.npc_attacks, [])

    def test_caller_intervals_must_be_positive_finite(self):
        for bad in (0, -1, float('nan'), float('inf'), True):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                CompanionAI(self.view, move_interval=bad, attack_interval=1, tick_interval=0.25)

    def test_sync_cleans_stale_generation_after_scheduler_skips_callback(self):
        old = self.actor.ref
        self.ai.start(old, self.now)
        self.actor.generation += 1
        self.run_due()  # scheduler correctly skips the obsolete ref
        self.assertIn(2, self.manager.active)
        self.ai.sync(self.now)
        self.assertNotIn(2, self.manager.active)
        self.assertIsNone(self.entities.get(old.uid))
        self.assertEqual((self.moves, self.intents), ([], []))

    def test_sync_wakes_missing_handle_once_preserves_dead_and_cleans_departure(self):
        self.ai.sync(self.now)
        handle = self.companion.handle
        self.ai.sync(self.now)
        self.assertIs(self.companion.handle, handle)
        self.run_due()
        self.assertEqual(len(self.moves), 1)
        self.manager.die(2, self.now)
        self.ai.sync(self.now)
        self.assertIn(2, self.manager.active)
        self.assertEqual(self.companion.action, 'DEAD')
        self.assertIsNone(self.companion.handle)
        self.setUp()
        self.view.pcs.clear()
        self.ai.sync(self.now)
        self.assertNotIn(2, self.manager.active)

    def test_command_and_event_spam_preserve_all_cooldowns(self):
        self.place(self.actor, 109, 100)
        self.ai.owner_attacked(self.owner.ref, self.mob.ref, self.now)
        self.run_due()
        self.companion.next_move_at = 100.5
        self.companion.next_cast_at = 107
        expected = (100.5, 101.25, 107)
        self.now = 100.25
        for _ in range(3):
            self.commands(movement_mode='HOLD', combat_mode='DEFEND')
            self.ai.on_hit(self.owner.ref, self.mob.ref, self.now)
            self.ai.on_hit(self.actor.ref, self.mob.ref, self.now)
            self.run_due()
            self.assertEqual((self.companion.next_move_at, self.companion.next_attack_at,
                              self.companion.next_cast_at), expected)
            self.assertEqual(len(self.intents), 1)
        self.run_due(101.25)
        self.assertEqual(len(self.intents), 2)

    def test_dead_corpse_stays_with_owner_then_departure_removes_without_reviving(self):
        for mode in ('offline', 'map', 'dead', 'combat_dead', 'generation'):
            with self.subTest(mode=mode):
                self.setUp()
                old = self.companion.ref
                self.manager.die(2, self.now)
                self.ai.sync(self.now)
                self.assertIn(2, self.manager.active)
                self.assertIs(self.entities.get(old.uid), self.actor)
                self.assertEqual(self.companion.action, 'DEAD')
                self.assertIsNone(self.companion.handle)
                if mode == 'offline':
                    self.view.pcs.clear()
                elif mode == 'map':
                    self.place(self.owner, 100, 100, map_id=1)
                elif mode == 'dead':
                    self.entities.kill(self.owner.uid)
                elif mode == 'combat_dead':
                    self.view.combat.can_be_attacked = lambda uid: False
                else:
                    self.owner.generation += 1
                self.ai.sync(self.now)
                self.assertNotIn(2, self.manager.active)
                self.assertIsNone(self.entities.get(old.uid))
                self.assertEqual((self.record.alive, self.record.hp), (False, 0))
                self.assertEqual(self.companion.action, 'DEAD')
                self.assertIsNone(self.companion.handle)


if __name__ == '__main__':
    unittest.main()
