"""Sourced forgotten-island placement checks; no sockets or native client."""
from collections import deque
import json
from pathlib import Path
import unittest

from tools.local_original_session import game_data as gd
from tools.local_original_session import world_feature_dungeons as feature
from tools.local_original_session.world_terrain import DELTAS, WorldTerrain


ROOT = Path(__file__).resolve().parents[2]


class ForgottenIslandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = gd._read(gd.M1_DATA_DIR.parent / 'm6', 'forgotten_island_spawns.json')
        cls.specs = gd._spawns(cls.document)
        cls.base = feature.load_dungeon_data(gd.load_m4(gd.load_m1()))
        cls.terrain = WorldTerrain.load(map_ids=(70,))

    def test_exact_official_region_and_selected_npc_source_rectangles(self):
        sql = Path('D:/SingleLineageRef/l1j-en-classic/db/l1jdb_m10.sql').read_text(
            encoding='utf-8').splitlines()
        self.assertEqual(len(self.specs), 23)
        self.assertEqual({row['template_id'] for row in self.document['pending']}, {753, 756, 766})
        for spec, row in zip(self.specs, self.document['groups']):
            monster = self.base.monsters[spec.template_id]
            official = json.loads((ROOT / 'work/official_data_refresh_20261028/raw/monster' /
                f'{spec.template_id}.json').read_text(encoding='utf-8'))
            self.assertIn('잊혀진 섬', official['regionNames'])
            reference = row['l1j_spawn_reference']
            raw = reference['raw']
            self.assertEqual((int(raw[3]), int(raw[16])), (monster.l1j_npcid, 70))
            line = int(reference['ref'].rsplit(':', 1)[1])
            self.assertIn("'" + "', '".join(raw) + "'", sql[line - 1])
            a, b, c, d = reference['rect']
            self.assertTrue(a <= spec.rect.x1 <= spec.rect.x2 <= c)
            self.assertTrue(b <= spec.rect.y1 <= spec.rect.y2 <= d)
            self.assertEqual((spec.target_count, spec.respawn_delay_min_ms,
                              spec.respawn_delay_max_ms), (1, 60000, 120000))
            self.assertTrue(all(self.terrain.can_stand(70, x, y) is True
                for x in range(spec.rect.x1, spec.rect.x2 + 1)
                for y in range(spec.rect.y1, spec.rect.y2 + 1)))

    def test_ship_arrival_reaches_all_source_rectangles_via_existing_named_links(self):
        links = {tuple(row['origin'][1:]): tuple(row['destination'][1:3])
                 for row in self.document['transitions']}
        start = self.document['arrival']
        origin = start['x'], start['y']
        self.assertIs(self.terrain.can_stand(70, *origin), True)
        seen, queue = {origin}, deque([origin])
        while queue:
            x, y = queue.popleft()
            for heading, (dx, dy) in enumerate(DELTAS):
                if self.terrain.can_step(70, x, y, heading) is not True:
                    continue
                point = links.get((x + dx, y + dy), (x + dx, y + dy))
                if point not in seen:
                    seen.add(point)
                    queue.append(point)
        for spec in self.specs:
            self.assertTrue(all((x, y) in seen
                for x in range(spec.rect.x1, spec.rect.x2 + 1)
                for y in range(spec.rect.y1, spec.rect.y2 + 1)), spec.group_id)

    def test_named_link_coordinates_are_original_bytes_without_external_walk_entry(self):
        self.assertEqual(len(self.document['transitions']), 4)
        for row in self.document['transitions']:
            self.assertEqual((row['origin'][0], row['destination'][0]), (70, 70))
            self.assertEqual(row['origin'], row['reference_origin'])
            self.assertEqual(row['destination'], row['reference_destination'])
            path, offset = row['ref'].split(':byte')
            self.assertEqual((ROOT / path).read_bytes()[int(offset):int(offset) + 8].hex(),
                             row['raw_hex'])
            self.assertIs(self.terrain.can_stand(*row['origin']), True)
            self.assertIs(self.terrain.can_stand(*row['destination'][:3]), True)
            self.assertEqual(row['native_trigger_status'], 'UNKNOWN')

    def test_startup_loader_registers_exact_island_groups_and_internal_links(self):
        policy = feature.load_island_policy()
        self.assertIn(70, policy.maps)
        self.assertIn(83, policy.maps)
        island = tuple(spec for spec in self.base.spawns
                       if spec.group_id.startswith('m6_forgotten_island_'))
        self.assertEqual({spec.group_id for spec in island},
                         {spec.group_id for spec in self.specs})
        self.assertEqual(len(island), 23)
        for row in self.document['transitions']:
            transition = policy.transitions[tuple(row['origin'])]
            self.assertEqual((transition.destination.map_id, transition.destination.x,
                              transition.destination.y, transition.destination.heading),
                             tuple(row['destination']))


if __name__ == '__main__':
    unittest.main()
