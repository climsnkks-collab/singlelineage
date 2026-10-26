"""Pure fake-clock AI checks; no broker import, server, socket or game startup.

Uses real M1 definitions, spawn ownership, entity generations and scheduler.
View callbacks record actions instead of producing client packets; these checks
establish backend behavior only, not projectile rendering or formal game PASS.
"""
from array import array
from dataclasses import replace
import random
from types import SimpleNamespace
import unittest

from tools.local_original_session import npc_ai as ai
from tools.local_original_session.game_data import Rect, load_m1
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import InterestSpawner
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_terrain import FLAG_COUNT, WorldTerrain

DATA = load_m1()


class Terrain:
    def __init__(self, rule=lambda map_id, x, y, heading: True):
        self.rule = rule

    def can_step(self, map_id, x, y, heading):
        return self.rule(map_id, x, y, heading)


class AiRangeTests(unittest.TestCase):
    def make(self, template=1, *, terrain=None, **changes):
        self.now = 100.0
        monster = replace(DATA.monsters[template], **changes)
        spec = replace(DATA.spawns[0], template_id=template, rect=Rect(100, 100, 100, 100),
                       target_count=1)
        data = replace(DATA, monsters={template: monster}, spawns=(spec,))
        runtime = WorldRuntime(clock=lambda: self.now)
        entities = runtime.entities
        spawner = InterestSpawner(entities, data, passable=lambda *_: True, rng=random.Random(7))
        self.allowed = {1}
        self.steps, self.attacks = [], []
        self.pc = entities.add(Kind.PC, 0, 106, 100, uid=1)
        view = SimpleNamespace(runtime=runtime, entities=entities, spawner=spawner,
                               terrain=terrain if terrain is not None else Terrain(),
                               pcs={1: (0, 106, 100)},
                               combat=SimpleNamespace(can_be_attacked=lambda uid: uid in self.allowed))

        def step(entity, x, y, heading):
            self.steps.append((self.now, entity.uid, x, y))
            entities.move(entity.uid, entity.map_id, x, y, heading)

        def attack(entity, monster, pc_uid, now):
            self.attacks.append((now, entity.uid, pc_uid))

        view.npc_step, view.npc_attack = step, attack
        self.view = view
        self.ai = ai.NpcAi(view, random.Random(3))
        spawner.update_interest(view.pcs.values(), self.now)
        self.ai.sync(self.now)
        self.mob = entities.get(spawner.groups[0].slots[0].uid)
        self.brain = self.ai.brains[self.mob.uid]

    def move_pc(self, x, y, *, map_id=0):
        self.view.entities.move(1, map_id, x, y)
        self.view.pcs[1] = (map_id, x, y)

    def run_due(self, at=None):
        if at is not None:
            self.now = at
        self.view.runtime.scheduler.run_due(self.now)

    def hit(self):
        self.ai.on_hit(self.mob.uid, 1, self.now)
        self.run_due()

    def test_ranged_holds_position_at_limit_and_repeats_on_interval(self):
        self.make()
        self.move_pc(100 + self.brain.monster.attack_range, 100)
        self.hit()
        self.assertEqual(self.brain.state, ai.State.ATTACK)
        self.assertEqual((len(self.attacks), self.steps), (1, []))
        due = self.now + self.brain.monster.attack_interval_ms / 1000
        self.run_due(due - 0.001)
        self.assertEqual(len(self.attacks), 1)
        self.run_due(due)
        self.assertEqual(len(self.attacks), 2)
        self.run_due(due + 20)  # a late tick attacks once, never replays every missed swing
        self.assertEqual((len(self.attacks), self.steps), (3, []))

    def test_ranged_still_attacks_point_blank_and_when_pc_moves_closer(self):
        self.make()
        self.hit()
        self.move_pc(101, 100)
        self.run_due(self.brain.next_attack_at)
        self.assertEqual((len(self.attacks), self.steps), (2, []))
        self.assertEqual(self.brain.state, ai.State.ATTACK)

    def test_outside_range_chases_then_holds_first_clear_attack_position(self):
        self.make()
        self.move_pc(111, 100)
        self.hit()
        self.assertEqual((len(self.attacks), len(self.steps)), (0, 1))
        self.assertEqual(self.brain.state, ai.State.CHASE)
        position = self.mob.x, self.mob.y
        self.run_due(self.brain.next_move_at)
        self.assertEqual((len(self.attacks), len(self.steps)), (1, 1))
        self.assertEqual((self.mob.x, self.mob.y), position)

    def test_static_s32_blocked_edge_prevents_shot_and_chase_seeks_clear_ray(self):
        flags = array('H', [0]) * FLAG_COUNT
        # Heading east probes (x=103,y=100,half=1). Both cells remain standable.
        flags[(((100 & 63) << 6) | (103 & 63)) * 2 + 1] = 1
        terrain = WorldTerrain({0: {(1, 1): flags}})
        self.make(terrain=terrain)
        self.assertFalse(self.ai._line_clear(0, 100, 100, 106, 100))
        self.hit()
        self.assertEqual(self.attacks, [])
        self.assertEqual(len(self.steps), 1)
        self.assertEqual(self.brain.state, ai.State.CHASE)
        self.run_due(self.brain.next_move_at)
        self.assertEqual(len(self.attacks), 1)

    def test_los_checks_intermediate_edges_in_every_octant_and_unknown_blocks(self):
        self.make()
        for tx, ty in ((106, 100), (106, 103), (103, 106), (100, 106), (97, 106),
                       (94, 103), (94, 100), (94, 97), (97, 94), (100, 94), (103, 94), (106, 97)):
            with self.subTest(target=(tx, ty)):
                calls = []
                self.view.terrain = Terrain(lambda m, x, y, h: calls.append((x, y, h)) or True)
                self.assertTrue(self.ai._line_clear(0, 100, 100, tx, ty))
                self.assertEqual(len(calls), ai.distance(100, 100, tx, ty))
                blocked = calls[len(calls) // 2]
                for result in (False, None):
                    self.view.terrain = Terrain(lambda m, x, y, h: result if (x, y, h) == blocked else True)
                    self.assertFalse(self.ai._line_clear(0, 100, 100, tx, ty))
        self.view.terrain = Terrain(lambda *_: None)
        self.hit()
        self.assertEqual((self.attacks, self.steps), ([], []))
        self.assertEqual(self.brain.state, ai.State.CHASE)

    def test_entity_occupancy_does_not_become_projectile_wall(self):
        self.make()
        self.view.entities.add(Kind.NPC, 0, 103, 100)
        self.hit()
        self.assertEqual((len(self.attacks), self.steps), (1, []))

    def test_current_four_definitions_stay_non_aggressive(self):
        self.assertEqual(len(DATA.monsters), 4)
        for template, monster in DATA.monsters.items():
            with self.subTest(template=template):
                self.assertFalse(monster.aggressive)
                self.make(template)
                self.move_pc(101, 100)
                self.ai.sync(self.now)
                self.run_due(self.brain.handle.at)
                self.assertIsNone(self.brain.target)
                self.assertEqual(self.attacks, [])

    def test_aggressive_recognizes_on_sync_without_waiting_for_idle(self):
        self.make(aggressive=True)
        self.assertEqual((self.brain.state, self.brain.target), (ai.State.CHASE, 1))
        self.assertEqual(self.brain.handle.at, self.now)
        self.run_due()
        self.assertEqual(len(self.attacks), 1)

    def test_perception_filters_range_map_life_binding_and_attackability(self):
        for case in ('range', 'map', 'entity_dead', 'unbound', 'cannot_attack'):
            with self.subTest(case=case):
                self.make(perception_range=4)
                self.brain.monster = replace(self.brain.monster, aggressive=True)
                self.move_pc(104, 100)
                if case == 'range':
                    self.move_pc(105, 100)
                elif case == 'map':
                    self.move_pc(104, 100, map_id=1)
                elif case == 'entity_dead':
                    self.view.entities.kill(1)
                elif case == 'unbound':
                    self.view.pcs.clear()
                else:
                    self.allowed.clear()
                self.ai.sync(self.now)
                self.assertIsNone(self.brain.target)
        self.make(perception_range=4)
        self.brain.monster = replace(self.brain.monster, aggressive=True)
        self.move_pc(104, 100)
        self.ai.sync(self.now)
        self.assertEqual(self.brain.target, 1)  # inclusive perception boundary

    def test_perception_from_wander_selects_nearest_then_uid(self):
        self.make()
        self.brain.monster = replace(self.brain.monster, aggressive=True)
        self.brain.state = ai.State.WANDER
        for uid, x in ((3, 103), (2, 103)):
            self.view.entities.add(Kind.PC, 0, x, 100 + uid % 2, uid=uid)
            self.view.pcs[uid] = (0, x, 100 + uid % 2)
            self.allowed.add(uid)
        self.ai.sync(self.now)
        self.assertEqual((self.brain.state, self.brain.target), (ai.State.CHASE, 2))

    def test_return_is_not_interrupted_and_pc_death_release_keeps_return_schedule(self):
        self.make(aggressive=True)
        self.view.entities.move(self.mob.uid, 0, 104, 100)
        self.move_pc(105, 100)
        self.brain.next_move_at = self.now + 0.4

        def lethal(entity, monster, target, now):
            self.allowed.remove(target)
            self.ai.release_target(target, now)

        self.view.npc_attack = lethal
        self.run_due()
        self.assertEqual((self.brain.target, self.brain.state), (None, ai.State.RETURN))
        self.assertEqual(self.brain.handle.at, self.brain.next_move_at)
        self.allowed.add(1)  # another live PC could be recognized, but RETURN stays owned
        self.ai.sync(self.now)
        self.assertIsNone(self.brain.target)
        self.run_due(self.brain.next_move_at)
        self.assertLess(ai.distance(self.mob.x, self.mob.y, 100, 100), 4)

    def test_only_zero_attack_positive_move_flees_with_move_cooldown(self):
        self.make(attack_interval_ms=0)
        self.move_pc(101, 100)
        self.hit()
        self.assertEqual(self.brain.state, ai.State.FLEE)
        self.assertGreater(ai.distance(self.mob.x, self.mob.y, self.pc.x, self.pc.y), 1)
        self.assertEqual((self.attacks, len(self.steps)), ([], 1))
        due = self.brain.next_move_at
        self.run_due(due - 0.001)
        self.assertEqual(len(self.steps), 1)
        self.run_due(due)
        self.assertEqual(len(self.steps), 2)
        self.make(0)  # low-HP normal attacker is not a flee condition
        self.move_pc(101, 100)
        self.hit()
        self.assertEqual((self.brain.state, len(self.attacks)), (ai.State.ATTACK, 1))

    def test_flee_obeys_terrain_occupancy_and_target_release(self):
        self.make(attack_interval_ms=0, terrain=Terrain(lambda m, x, y, h: h == 6))
        self.move_pc(101, 100)
        self.view.entities.add(Kind.NPC, 0, 99, 100)
        self.hit()
        self.assertEqual((self.brain.state, self.steps, self.attacks), (ai.State.FLEE, [], []))
        self.ai.release_target(1, self.now)
        self.assertEqual((self.brain.state, self.brain.target), (ai.State.RETURN, None))

    def test_zero_move_never_flees_or_steps_and_zero_attack_never_swings(self):
        self.make(attack_interval_ms=0, move_interval_ms=0)
        self.hit()
        self.run_due(self.brain.handle.at)
        self.assertEqual((self.steps, self.attacks), ([], []))
        self.assertEqual(self.brain.state, ai.State.IDLE)
        self.make(move_interval_ms=0)
        self.hit()
        self.assertEqual((self.steps, len(self.attacks)), ([], 1))
        self.make(0, move_interval_ms=0)
        self.hit()  # outside melee range; no movement and no attack
        self.assertEqual((self.steps, self.attacks), ([], []))

    def test_leash_and_lost_target_return_then_idle_at_home(self):
        for reason in ('leash', 'logout', 'map', 'dead'):
            with self.subTest(reason=reason):
                self.make()
                self.ai.on_hit(self.mob.uid, 1, self.now)
                if reason == 'leash':
                    x = 101 + self.brain.monster.leash_range
                    self.view.entities.move(self.mob.uid, 0, x, 100)
                    self.move_pc(x + 1, 100)
                elif reason == 'logout':
                    self.view.pcs.clear()
                elif reason == 'map':
                    self.move_pc(106, 100, map_id=1)
                else:
                    self.allowed.clear()
                self.run_due()
                self.assertIsNone(self.brain.target)
                self.assertIn(self.brain.state, (ai.State.RETURN, ai.State.IDLE))
                self.assertEqual(self.attacks, [])

    def test_death_dormancy_and_respawn_cancel_old_generation(self):
        self.make()
        old = self.mob.ref
        self.ai.on_hit(self.mob.uid, 1, self.now)
        slot = self.view.spawner.mark_dead(self.mob.uid, self.now)
        self.ai.sync(self.now)
        self.assertNotIn(self.mob.uid, self.ai.brains)
        self.run_due(self.now + 1)
        self.assertEqual((self.steps, self.attacks), ([], []))
        self.assertFalse(self.view.entities.is_current(old))
        self.now = slot.respawn_at
        self.view.spawner.tick(self.now)
        self.ai.sync(self.now)
        self.assertNotEqual(slot.uid, old.uid)
        self.assertIn(slot.uid, self.ai.brains)
        self.view.spawner.update_interest([], self.now)
        self.ai.sync(self.now)
        self.assertEqual(self.ai.brains, {})
        self.assertEqual(len(self.view.runtime.scheduler), 0)


if __name__ == '__main__':
    unittest.main()
