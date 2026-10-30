"""Pure route-choice tests; no listener, broker, game or save initialization."""
from collections import deque
from types import SimpleNamespace
from pathlib import Path
import unittest

from tools.local_original_session import hunt_bot_dungeons as bot


def edge(map_id):
    return SimpleNamespace(destination=SimpleNamespace(map_id=map_id))


class RouteTests(unittest.TestCase):
    def test_cli_can_construct_reused_matrix_without_opening_it(self):
        transitions = {(4, 10, 10): edge(43)}
        transitions.update({(m, 21, 21): edge(m+1) for m in range(43, 51)})
        scenario = bot.DungeonScenario(bot.parser().parse_args([]), 'ant_cave', Path('.'),
                                       transitions, SimpleNamespace())
        self.assertEqual(scenario.family, 'ant_cave')
        self.assertIsNone(scenario.broker)

    def test_all_floors_follow_existing_branch_edges_with_revisits(self):
        from tools.local_original_session import world_maps
        transitions = dict(world_maps.TRANSITIONS) | dict(world_maps.load_dungeon_policy().transitions)
        for family, maps in bot.FAMILIES.items():
            route = bot.floor_route(family, transitions)
            current, visited = maps[0], {maps[0]}
            for origin, row in route:
                self.assertEqual(origin[0], current)
                self.assertIs(transitions[origin], row)
                current = row.destination.map_id
                visited.add(current)
            self.assertEqual(visited, set(maps))
            self.assertEqual(current, maps[-1])
            if family == 'ant_cave':
                self.assertGreater(len(route), len(maps)-1)

    def test_same_map_maze_route_cache_survives_parent_preflight_query(self):
        scenario = bot.DungeonScenario.__new__(bot.DungeonScenario)
        calls = []
        def can_step(map_id, x, y, heading):
            calls.append((x, y, heading))
            return (x, y, heading) in ((0, 0, 2), (10, 0, 2))
        scenario.bot = SimpleNamespace(map_id=7, position=(0, 0), self_uid=1, blocked_edges={})
        scenario.broker = SimpleNamespace(_world=SimpleNamespace(
            terrain=SimpleNamespace(can_step=can_step),
            entities=SimpleNamespace(near=lambda *args, **kwargs: ())))
        scenario.transitions = {(7, 1, 0): SimpleNamespace(
            destination=SimpleNamespace(map_id=7, x=10, y=0))}
        scenario._planned_key, scenario._planned_steps = None, deque()
        self.assertEqual(scenario.travel_heading((11, 0), 0, require_reached=True), 2)
        count = len(calls)
        self.assertEqual(scenario.travel_heading((11, 0), 0), 2)
        self.assertEqual(len(calls), count)
        scenario.bot.position = (10, 0)  # position supplied by the actual stair reply in a live run
        self.assertEqual(scenario.travel_heading((11, 0), 0), 2)
        self.assertEqual(len(calls), count)

    def test_family_route_requires_external_entry_and_forward_floor(self):
        transitions = {(4, 10, 10): edge(43), (43, 20, 20): edge(4),
                       (43, 21, 21): edge(47), (47, 30, 30): edge(43)}
        entry, floor = bot.family_route('ant_cave', transitions)
        self.assertEqual(entry[0], (4, 10, 10))
        self.assertEqual(floor[0], (43, 21, 21))
        with self.assertRaises(bot.matrix.MissingFeature):
            bot.family_route('ant_cave', {(47, 30, 30): edge(43), (43, 21, 21): edge(47)})

    def test_entrance_fixture_is_nonportal_and_has_actual_inbound_edge(self):
        class Terrain:
            def can_stand(self, map_id, x, y):
                return True

            def can_step(self, map_id, x, y, heading):
                return (x, y, heading) in ((10, 11, 0), (9, 11, 1))
        # The north-step neighbour is itself a portal, so choose the next valid
        # neighbour. Standability alone must not count as inbound reachability.
        transitions = {(4, 10, 10): edge(7), (4, 10, 11): edge(19)}
        self.assertEqual(bot.entrance_start(Terrain(), (4, 10, 10), transitions), (4, 9, 11))

    def test_unknown_edges_do_not_make_a_start_fixture(self):
        terrain = SimpleNamespace(can_stand=lambda *args: True, can_step=lambda *args: None)
        with self.assertRaises(bot.matrix.MissingFeature):
            bot.entrance_start(terrain, (4, 10, 10), {})


if __name__ == '__main__':
    unittest.main()
