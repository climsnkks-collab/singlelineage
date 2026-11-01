"""Knight interior startup/terrain contracts; no sockets or native game.

Authenticated extracted S32 may be supplied explicitly for development tests.
The product loader never falls back to that test output. These checks do not
prove normal access to map237: its current map13 key approach remains OPEN.
"""
from collections import deque
from pathlib import Path
from types import MethodType, SimpleNamespace
import json
import unittest
from unittest.mock import patch

from tools.local_original_session import world_feature_dungeons as dungeons
from tools.local_original_session import world_maps as maps
from tools.local_original_session import world_terrain as terrain_module
from tools.local_original_session.world_core_life import _world_set_relocation
from tools.local_original_session.world_core_maps import realm_serves_map
from tools.local_original_session.world_item_effects import ItemEffectResult
from tools.local_original_session.world_registry import build_registry


ROOT = Path(__file__).resolve().parents[2]
EXTRACTED_MAP_ROOT = ROOT / '_work/knight-maps/assets/map'
DOCUMENT = Path(__file__).resolve().parent / 'data/m6/knight_maps.json'


def reachable(terrain, map_id, start, *, blocked=(), stop=None):
    seen, pending = {start}, deque([start])
    while pending:
        x, y = pending.popleft()
        if (x, y) == stop:
            return seen
        for heading, (dx, dy) in enumerate(terrain_module.DELTAS):
            point = x + dx, y + dy
            if (point not in seen and point not in blocked
                    and terrain.can_step(map_id, x, y, heading) is True):
                seen.add(point)
                pending.append(point)
    return seen


class KnightMapsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(DOCUMENT.read_text(encoding='utf-8'))
        # Use canonical assets after materialization; otherwise explicitly use
        # the authenticated extraction for these static development checks.
        cls.knight_root = terrain_module.DEFAULT_MAP_ROOT
        if not all(any((cls.knight_root / str(mid)).glob('*.s32')) for mid in (3, 237)):
            cls.knight_root = EXTRACTED_MAP_ROOT
        cls.terrain = terrain_module.WorldTerrain.load(map_ids=(0, 4, 13))
        extra = terrain_module.WorldTerrain.load(cls.knight_root, map_ids=(3, 237))
        cls.terrain._chunks.update(extra._chunks)
        with patch.object(terrain_module, 'DEFAULT_MAP_ROOT', cls.knight_root):
            cls.policy = maps.load_dungeon_policy()

    def test_startup_admits_each_map_only_with_canonical_s32_and_no_dangling_link(self):
        missing = ROOT / '_work/knight-maps/not-materialized'
        for available in (set(), {3}, {237}, {3, 237}):
            class SelectedRoot:
                def __truediv__(self, name):
                    return self.knight_root / name if int(name) in available else missing / name
            selected = SelectedRoot()
            selected.knight_root = self.knight_root
            with self.subTest(available=available), patch.object(
                    terrain_module, 'DEFAULT_MAP_ROOT', selected):
                policy = maps.load_dungeon_policy()
                self.assertEqual(set(policy.maps) & {3, 237}, available)
                self.assertEqual(set(policy.returns) & {3, 237}, available)
                links = [(origin, transition) for origin, transition in policy.transitions.items()
                         if {origin[0], transition.destination.map_id} & {3, 237}]
                self.assertEqual(len(links), len(available) * 2)
                for origin, transition in links:
                    self.assertIn(transition.destination.map_id, {0, *policy.maps})
                    self.assertIn(origin[0], {0, *policy.maps})

    def test_existing_registry_and_transition_hooks_consume_prepared_policy(self):
        context = SimpleNamespace(world=object(), _world_dungeon_policy=self.policy)
        realm = SimpleNamespace(_world_map_exp=2, _world_context=context,
                                _world_registry=build_registry((dungeons,)))
        for mid in (3, 237):
            self.assertTrue(realm_serves_map(realm, mid))
        for row in self.document['transitions']:
            self.assertEqual(dungeons._world_dungeons_transition(context, None, *row['origin']),
                             maps.MapDestination(*row['destination']))
        context._world_dungeon_policy = None
        for mid in (3, 237):
            self.assertFalse(realm_serves_map(realm, mid))
        self.assertIsNone(dungeons._world_dungeons_transition(context, None, 0, 32510, 32863))

    def test_lazy_terrain_reuses_current_chunks_and_all_selected_points_are_standable(self):
        lazy = terrain_module.WorldTerrain.load(self.knight_root, map_ids=(),
                                                lazy_map_ids=terrain_module.LAZY_MAP_IDS)
        for row in self.document['maps']:
            mid = row['map_id']['value']
            self.assertEqual(lazy.bounds(mid), tuple(row['terrain_bounds']))
            self.assertEqual(sum(s.startswith(f'{mid}/') for s in lazy.sources), row['chunks'])
        count = len(lazy.sources)
        lazy.bounds(3)
        lazy.bounds(237)
        self.assertEqual(len(lazy.sources), count)
        for row in self.document['transitions']:
            self.assertEqual(row['origin'], row['reference_origin'])
            self.assertEqual(row['destination'], row['reference_destination'])
            self.assertEqual(row['native_trigger_status'], 'UNKNOWN')
            self.assertIs(self.terrain.can_stand(*row['origin']), True)
            self.assertIs(self.terrain.can_stand(*row['destination'][:3]), True)
        for row in self.document['returns']:
            self.assertIs(self.terrain.can_stand(*row['destination'][:3]), True)

    def test_map3_town_approach_gunter_and_exit_are_connected(self):
        entrance = (32510, 32863)
        other_stairs = {origin[1:] for origin in self.policy.transitions if origin[0] == 0
                        and origin[1:] != entrance}
        self.assertIn(entrance, reachable(self.terrain, 0, (32574, 32941),
                                         blocked=other_stairs, stop=entrance))
        self.assertIn((32669, 32788), reachable(self.terrain, 3, (32675, 32814),
                                               blocked={(32675, 32815)}))
        self.assertIn((32675, 32815), reachable(self.terrain, 3, (32669, 32788)))

    def test_map237_landing_reaches_jim_and_return_stair(self):
        self.assertIn((32746, 32807), reachable(self.terrain, 237, (32736, 32807)))
        self.assertIn((32736, 32807), reachable(self.terrain, 237, (32746, 32807)))

    def test_map13_key_approach_is_unconnected_and_remains_open(self):
        entry = next(transition.destination for origin, transition in self.policy.transitions.items()
                     if origin[0] != 13 and transition.destination.map_id == 13
                     and origin[0] != 237)
        seen = reachable(self.terrain, 13, (entry.x, entry.y))
        self.assertNotIn((32813, 32810), seen)
        self.assertNotIn((32815, 32810), seen)
        key = self.document['key_reference']
        x1, y1, x2, y2 = key['reference_rectangle']
        self.assertFalse(any((x, y) in seen for x in range(x1, x2 + 1)
                             for y in range(y1, y2 + 1)))
        self.assertIn((32813, 32810), reachable(self.terrain, 13, (32815, 32810)))
        self.assertEqual((key['fixed_item_id'], key['l1j_item_id'], key['shared_name_token']),
                         (707, 40555, '$2022'))
        self.assertEqual(self.document['normal_access_status']['237'],
                         'OPEN_MAP13_KEY_USE_APPROACH_UNREACHABLE')

    def test_return_hook_preserves_scroll_cost_and_death_only_queues_relocation(self):
        result = ItemEffectResult(162, 'return_town', 'destination_proposed', consume_count=1,
                                 destination=maps.MapDestination(0, 32578, 32946, 5))
        for mid in (3, 237):
            actor = SimpleNamespace(map_id=mid, x=32746, y=32807)
            context = SimpleNamespace(_world_dungeon_policy=self.policy,
                _world_relocations={}, world=SimpleNamespace(entities={19: actor}))
            context._world_set_relocation = MethodType(_world_set_relocation, context)
            position = maps.MapDestination(mid, actor.x, actor.y, 0)
            proposed = dungeons._world_dungeons_destination(context, result, position)
            self.assertEqual(proposed.destination, self.policy.return_for(mid))
            self.assertEqual(proposed.consume_count, 1)
            before = (actor.map_id, actor.x, actor.y)
            dungeons._world_dungeons_death(context, 19)
            self.assertEqual(context._world_relocations[19], self.policy.return_for(mid))
            self.assertEqual((actor.map_id, actor.x, actor.y), before)


if __name__ == '__main__':
    unittest.main()
