"""Three current-client maps: development request/policy tests, no game or sockets."""
import json
from collections import deque
import os
from pathlib import Path
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory
from tools.local_original_session import world_feature_dungeons as dungeons
from tools.local_original_session import world_maps as maps
from tools.local_original_session.world_core_maps import realm_serves_map
from tools.local_original_session.world_core_life import _world_set_relocation
from tools.local_original_session.world_item_effects import WorldItemEffects
from tools.local_original_session.world_registry import build_registry
from tools.local_original_session.world_talkscroll import destination_status
from tools.local_original_session import world_talkscroll_tests as _request_fixture
from tools.local_original_session.world_terrain import WorldTerrain, LAZY_MAP_IDS, DELTAS
from tools.local_original_session.world_visibility import WorldView


CASES = ((102, 244, 32987, 32811, (4, 32750, 32435, 5)),
         (133, 777, 32554, 32952, (4, 34043, 32184, 5)),
         (134, 779, 32554, 32952, (4, 32608, 33178, 5)))


class DungeonTalkingMapTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the existing request envelope/owned-item fixture without changing
    # its source or running its inherited tests under a second test class.
    frame = _request_fixture.NativeRequestTests.frame
    request = _request_fixture.NativeRequestTests.request
    use_hunting_scroll = _request_fixture.NativeRequestTests.use_hunting_scroll

    def setUp(self):
        _request_fixture.NativeRequestTests.setUp(self)
        self.use_hunting_scroll()
        self.policy = dungeons.load_island_policy()
        self.terrain = WorldTerrain.load(lazy_map_ids=LAZY_MAP_IDS)
        self.host._world.terrain = self.terrain
        self.host._world_map_exp = 2
        realm = self.host.realm
        realm._world_map_exp = 2
        realm._world_registry = build_registry((dungeons,))
        realm._world_context = SimpleNamespace(world=self.host._world,
                                               _world_dungeon_policy=self.policy)
        # Actual registry-backed map admission, not an always-true test stub.
        realm.serves_map = MethodType(realm_serves_map, realm)

    async def test_three_original_selections_reach_relocation_without_consuming_scroll(self):
        for ordinal, map_id, x, y, _ in CASES:
            with self.subTest(map_id=map_id):
                row = next(row for row in self.host._talkscroll_catalog.rows
                           if row['group_id'] == 8 and row['ordinal'] == ordinal)
                self.assertEqual(destination_status(row, serves_map=self.host.realm.serves_map,
                                                    terrain=self.terrain), 'open')
                self.assertTrue(await self.request(ordinal))
                self.assertEqual((self.position.map_id, self.position.word0, self.position.word1),
                                 (map_id, x, y))
        self.assertEqual(len(self.relocations), 3)
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        self.assertEqual(self.sent, [teleport_effect_frame(1), b'map-refresh'] * 3)
        self.assertEqual(self.host._world_handler_errors, [])
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(dict(inventory.validate_kit_frame(self.before)[0].raw_fields)[4], 1)

    async def test_disabled_dungeons_refuse_all_three_before_relocation_or_drain(self):
        self.host.realm._world_context._world_dungeon_policy = None
        for ordinal, map_id, _, _, _ in CASES:
            self.assertFalse(self.host.realm.serves_map(map_id))
            self.assertTrue(await self.request(ordinal))
        self.assertEqual(self.relocations, [])
        self.assertEqual(self.drains, [])
        self.assertIs(self.host.inventory_frame, self.before)

    def test_return162_and_death_use_sourced_external_points(self):
        world = WorldView.create(terrain=self.terrain)
        self.addCleanup(world.close)
        from tools.local_original_session.world_combat import PcProfile
        world.combat.bind_pc(1, PcProfile(1, 1, 0, 13, 13),
                            {1: 1, 10: 1, 11: 200, 12: 3, 13: 10, 16: 200, 17: 7})
        effects = WorldItemEffects(world.combat, self.terrain)
        composed = dungeons.DungeonItemEffects(effects, self.policy)
        context = SimpleNamespace(world=world, _world_dungeon_policy=self.policy,
                                  _world_relocations={})
        context._world_set_relocation = MethodType(_world_set_relocation, context)
        from tools.local_original_session.world_entities import Kind
        for _, map_id, x, y, expected in CASES:
            with self.subTest(map_id=map_id):
                position = maps.MapDestination(map_id, x, y, 0)
                destination = maps.MapDestination(*expected)
                self.assertIs(self.terrain.can_stand(destination.map_id,
                                                    destination.x, destination.y), True)
                # Actual ordinary return effect and registered destination hook.
                original = effects.use(1, 162, 0, position=position)
                result = dungeons._world_dungeons_destination(context, original, position)
                self.assertEqual(result.destination, destination)
                self.assertEqual((result.kind, result.consume_count), ('return_town', 1))
                self.assertEqual(composed.use(1, 162, 0, position=position), result)
                actor = world.entities.add(Kind.PC, map_id, x, y)
                dungeons._world_dungeons_death(context, actor.uid)
                self.assertEqual(context._world_relocations[actor.uid], destination)
                self.assertEqual((actor.map_id, actor.x, actor.y), (map_id, x, y))

    def test_client_bounds_admissions_and_population_remain_separate(self):
        path = Path(__file__).resolve().parent / 'data/m6/talkscroll_maps.json'
        document = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(document['groups'], [])
        self.assertEqual(document['transitions'], [])
        for row in document['maps']:
            map_id = row['map_id']['value']
            self.assertIn(map_id, self.policy.maps)
            self.assertIn(map_id, LAZY_MAP_IDS)
            self.assertEqual(self.policy.maps.count(map_id), 1)
            self.assertEqual(self.terrain.bounds(map_id), tuple(row['terrain_bounds']))
            self.assertEqual(len(self.terrain._chunks[map_id]), row['chunks'])
            self.assertEqual(row['hunting'], map_id != 779)
            self.assertFalse(any(origin[0] == map_id for origin in self.policy.transitions))
        # The same L1J id describes a different coordinate region. It is not
        # imported as current-client terrain, stairs or spawn coordinates.
        row = next(row for row in document['maps'] if row['map_id']['value'] == 779)
        self.assertNotEqual(row['terrain_bounds'], row['reference_geometry']['bounds'])

    def test_population_uses_exact_npc_sql_rectangle_and_connected_current_s32(self):
        from tools.local_original_session import game_data as gd
        from tools.local_original_session.world_interest_spawn import with_dungeon_data
        directory = Path(__file__).resolve().parent / 'data'
        document = json.loads((directory / 'm6/map_expansion6.json').read_text(encoding='utf-8'))
        official = {row['official_id']: row for row in
                    json.loads((directory / 'official/monsters.json').read_text(encoding='utf-8'))['monsters']}
        with patch.dict(os.environ, {'SL_EXPERIMENT_MAP': '2'}):
            data = dungeons.load_dungeon_data(with_dungeon_data(gd.load_m1()))
        groups = [row for row in document['groups']
                  if row['group_id']['value'].startswith('m6_talkscroll_')]
        self.assertEqual(len(groups), 17)
        self.assertFalse(any(row.map_id == 779 for row in data.spawns))
        selected = {244: {2381, 2388, 2389, 2390, 2391, 2392, 2394, 2395,
                          2397, 2399, 2400, 2401}, 777: set(range(2782, 2787))}
        for _, mid, x, y, _ in CASES[:2]:
            seen, pending = {(x, y)}, deque([(x, y)])
            while pending:
                x, y = pending.popleft()
                for heading, (dx, dy) in enumerate(DELTAS):
                    point = x+dx, y+dy
                    if point not in seen and self.terrain.can_step(mid, x, y, heading) is True:
                        seen.add(point)
                        pending.append(point)
            rows = [row for row in groups if row['map_id']['value'] == mid]
            self.assertEqual({row['template_id']['value'] for row in rows}, selected[mid])
            for row in rows:
                tid = row['template_id']['value']
                reference, rect = row['l1j_spawn_reference'], row['rect']['value']
                raw = reference['raw']
                self.assertEqual((int(raw[16]), int(raw[3])), (mid, data.monsters[tid].l1j_npcid))
                self.assertEqual(official[tid]['client_id'], tid)
                self.assertTrue(set(row['official_region_names']['value'])
                                & set(official[tid]['official']['regionNames']))
                self.assertTrue(int(raw[9]) <= rect['x1'] <= rect['x2'] <= int(raw[11]))
                self.assertTrue(int(raw[10]) <= rect['y1'] <= rect['y2'] <= int(raw[12]))
                self.assertEqual((row['target_count']['value'], row['respawn_delay_ms']['value']),
                                 (1, {'min': 60000, 'max': 120000}))
                for x in range(rect['x1'], rect['x2']+1):
                    for y in range(rect['y1'], rect['y2']+1):
                        self.assertIn((x, y), seen)
                        self.assertIs(self.terrain.can_stand(mid, x, y), True)
                self.assertIn(row['group_id']['value'], {spec.group_id for spec in data.spawns})


if __name__ == '__main__':
    unittest.main()
