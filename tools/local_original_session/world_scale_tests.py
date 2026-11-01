"""Deterministic backend scale/instrumentation checks; no timing-noise assertions."""
import asyncio
from collections import Counter, deque
from dataclasses import replace
import random
import unittest

from tools.local_original_session import npc_ai
from tools.local_original_session import world_scale_bench as bench
from tools.local_original_session.game_data import Rect
from tools.local_original_session.world_entities import EntityRegistry, Kind


def uncached_heading(ai, entity, reached, goal):
    """Pre-optimization BFS: retain original order and individual occupancy checks."""
    start = entity.x, entity.y
    if reached(*start):
        return None
    first, depth, queue = {start: None}, {start: 0}, deque([start])
    best, best_key = None, (npc_ai.distance(*start, *goal), 0)
    while queue and len(first) < npc_ai.BFS_MAX_NODES:
        x, y = queue.popleft()
        for heading, (dx, dy) in enumerate(npc_ai.DELTAS):
            nxt = x+dx, y+dy
            if nxt in first or npc_ai.distance(*nxt, *start) > npc_ai.BFS_RADIUS:
                continue
            if not ai._can_move(entity, x, y, heading):
                continue
            first[nxt] = heading if (x, y) == start else first[x, y]
            depth[nxt] = depth[x, y]+1
            if reached(*nxt):
                return first[nxt]
            key = npc_ai.distance(*nxt, *goal), depth[nxt]
            if key < best_key:
                best, best_key = nxt, key
            queue.append(nxt)
    return None if best is None else first[best]


class CountingRegistry(EntityRegistry):
    def __init__(self):
        super().__init__()
        self.near_calls = Counter()

    def near(self, map_id, x, y, radius, **kwargs):
        self.near_calls[radius] += 1
        return super().near(map_id, x, y, radius, **kwargs)


class ScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.info = bench.load_catalog()

    def small_data(self, count=1):
        monster = self.data.monsters[0]
        group = replace(self.data.spawns[0], template_id=0, target_count=count,
                        rect=Rect(100, 100, 104, 104))
        return replace(self.data, monsters={0: monster}, spawns=(group,))

    def world(self, count=1, terrain=None):
        world = bench.BenchWorld(self.small_data(count), terrain or bench.OpenTerrain(),
                                 entities=CountingRegistry())
        world.update_pc(101, 101)
        entity = world.entities.get(next(iter(world.ai.brains)))
        # Keep the PC outside the search window for pure occupancy checks.
        world.entities.move(bench.PC, 0, 200, 200)
        world.entities.near_calls.clear()
        return world, entity

    def test_full_catalog_retains_254_slots_and_unresolved_local_ids(self):
        self.assertEqual((len(self.data.spawns), sum(s.target_count for s in self.data.spawns)), (90, 254))
        self.assertEqual((len(self.data.monsters), self.info['unresolved_slots']), (30, 50))
        unresolved = [m for m in self.data.monsters.values() if m.template_id < 0]
        self.assertEqual(len(unresolved), 7)
        for monster in unresolved:
            self.assertEqual(monster.template_id, -monster.l1j_npcid)
            self.assertIn('BENCH', monster.sources['identity'].note.upper())

    def test_rectangle_sweep_matches_exhaustive_integer_search(self):
        groups = (replace(self.data.spawns[0], rect=Rect(0, 0, 2, 2), target_count=2),
                  replace(self.data.spawns[1], rect=Rect(4, 1, 5, 3), target_count=7),
                  replace(self.data.spawns[2], rect=Rect(1, 5, 2, 5), target_count=3))
        for radius in (0, 1, 2):
            actual = bench.geometric_maxima(groups, radius)
            counts = [(sum(bench.rect_distance(g.rect, x, y) <= radius for g in groups),
                       sum(g.target_count for g in groups if bench.rect_distance(g.rect, x, y) <= radius))
                      for x in range(-3, 9) for y in range(-3, 9)]
            self.assertEqual(actual['groups']['value'], max(a for a, b in counts))
            self.assertEqual(actual['slots']['value'], max(b for a, b in counts))

    def test_static_route_and_retention_witness_keep_edges_and_hysteresis(self):
        data, terrain = self.small_data(2), bench.OpenTerrain()
        found = bench.geometric_maxima(data.spawns, bench.ROFF)['slots']
        route, info = bench.retention_walk(data, terrain, found)
        self.assertEqual(info['status'], 'CONSTRUCTED_STATIC_S32_WALK')
        world = bench.BenchWorld(data, terrain)
        for x, y in route:
            world.update_pc(x, y)
        self.assertEqual(world.snapshot()['active_slots'], 2)
        path = bench.static_path(terrain, (100, 100), (106, 103))
        self.assertEqual((path[0], path[-1]), ((100, 100), (106, 103)))
        self.assertTrue(all(npc_ai.distance(*a, *b) == 1 for a, b in zip(path, path[1:])))

    def test_hysteresis_last_activation_rules_out_off_overlap_without_a_ron_entry(self):
        groups = (replace(self.data.spawns[0], rect=Rect(0, 0, 0, 0)),
                  replace(self.data.spawns[1], rect=Rect(80, 0, 80, 0)))
        self.assertEqual(bench.geometric_maxima(groups, bench.ROFF)['groups']['value'], 2)
        bound = bench.reachable_group_bound(groups, observed_lower=1)
        self.assertEqual((bound['history_upper'], bound['exact']), (1, True))
        close = (groups[0], replace(groups[1], rect=Rect(60, 0, 60, 0)))
        self.assertEqual(bench.reachable_group_bound(close, observed_lower=1)['history_upper'], 2)

    def test_runtime_hook_order_and_callback_failures_are_not_swallowed(self):
        world, _ = self.world()
        order = []
        world.runtime.scheduler.schedule(world.clock.now, None, 'order', lambda now: order.append('due'))
        world.runtime.add_tick_hook(lambda now: order.append('hook'))
        asyncio.run(world.runtime.tick_once())
        self.assertEqual(order, ['due', 'hook'])
        def fail(now):
            raise ValueError('deliberate-test-error')
        world.runtime.scheduler.schedule(world.clock.now, None, 'error', fail)
        asyncio.run(world.runtime.tick_once())
        with self.assertRaisesRegex(RuntimeError, 'deliberate-test-error'):
            world.check()

    def test_worst_case_bfs_is_exercised_and_budget_reporting_is_deterministic(self):
        world, entity = self.world()
        meter = bench.BfsMeter(world)
        world.ai._path_step(entity, lambda x, y: False, (entity.x+50, entity.y))
        report = meter.report()
        self.assertEqual(report['calls'], 1)
        self.assertEqual(report['max_reached_probes_per_call'], (2*npc_ai.BFS_RADIUS+1)**2)
        self.assertGreater(report['can_move_checks'], 400)
        self.assertEqual(bench.timing_summary([1, 45, 46, 50])['over_45ms'], 2)
        burst = asyncio.run(bench.bfs_burst(self.small_data(2), (100, 100), instrument=True))
        self.assertEqual(burst['completed_bfs'], 2)
        self.assertEqual(burst['bfs']['calls'], 2)

    def test_maximum_load_intervals_report_cost_and_zero_bfs_without_raw_samples(self):
        data, terrain = self.small_data(2), bench.OpenTerrain()
        route = [(200, 200), (100, 100), (101, 100), (200, 200)]
        timed = asyncio.run(bench.replay(data, terrain, route, dwell_ticks=0))
        measured = asyncio.run(bench.replay(data, terrain, route, dwell_ticks=0,
                                           instrument=True, collect_timing=False))
        for key, count_key, expected in (('max_active_groups', 'active_groups', 1),
                                          ('max_active_slots', 'active_slots', 2)):
            summary = timed['maximum_load_intervals'][key]
            self.assertEqual((summary[count_key], summary['samples']), (expected, 2))
            self.assertEqual(summary['tick_wall']['samples'], 2)
            self.assertEqual(summary['move_plus_tick_wall']['samples'], 2)
            bfs = measured['maximum_load_intervals'][key]['bfs']
            self.assertEqual((bfs['calls'], bfs['reached_probes'], bfs['can_move_checks'],
                              bfs['instrumented_bfs_wall_ms']), (0, 0, 0, 0.0))
            self.assertFalse(any(isinstance(value, list) for value in summary.values()))
        world, entity = self.world()
        meter = bench.BfsMeter(world)
        world.ai._can_move(entity, entity.x, entity.y, 0)  # ordinary wander/step check
        self.assertEqual(meter.move_checks, 0)

    def test_cached_heading_equals_original_with_terrain_items_corpses_and_actors(self):
        rng = random.Random(17)
        for case in range(12):
            class Terrain(bench.OpenTerrain):
                def can_step(self, map_id, x, y, heading):
                    dx, dy = npc_ai.DELTAS[heading]
                    return (x+dx+y+dy+case) % 7 != 0
            world, entity = self.world(terrain=Terrain())
            for i in range(15):
                actor = world.entities.add(Kind.ITEM if i % 4 == 0 else Kind.NPC, 0,
                    entity.x+rng.randrange(-8, 9), entity.y+rng.randrange(-8, 9))
                if i % 5 == 0:
                    world.entities.kill(actor.uid)
            goal = entity.x+12, entity.y+3
            reached = lambda x, y: (x, y) == goal
            expected = uncached_heading(world.ai, entity, reached, goal)
            world.entities.near_calls.clear()
            actual = world.ai._path_step(entity, reached, goal)
            self.assertEqual(actual, expected)
            self.assertEqual(world.entities.near_calls, Counter({npc_ai.BFS_RADIUS: 1}))

    def test_occupancy_snapshot_refreshes_between_bfs_calls(self):
        world, entity = self.world()
        reached = lambda x, y: (x, y) == (entity.x+1, entity.y)
        goal = entity.x+1, entity.y
        self.assertEqual(world.ai._path_step(entity, reached, goal), 2)
        blocker = world.entities.add(Kind.NPC, 0, *goal)
        self.assertNotEqual(world.ai._path_step(entity, reached, goal), 2)
        world.entities.move(blocker.uid, 0, 200, 201)
        self.assertEqual(world.ai._path_step(entity, reached, goal), 2)
        world.entities.move(blocker.uid, 0, *goal)
        world.entities.remove(blocker.uid)
        self.assertEqual(world.ai._path_step(entity, reached, goal), 2)


if __name__ == '__main__':
    unittest.main()
