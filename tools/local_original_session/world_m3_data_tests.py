"""M3 table references and real S32 placement checks; no game/server/packets.

These are static LOCAL backend checks, not a native dungeon play PASS.
The LOCAL map0 entrance source uses the reachable S32 cell; the blocked L1J
source remains provenance in world_maps, never an expectedFailure or skip.
"""
from collections import Counter
from pathlib import Path
import unittest

from tools.local_original_session import game_data as gd
from tools.local_original_session.world_interest_spawn import (
    rect_distance, with_dungeon_data,
)
from tools.local_original_session.world_maps import TRANSITIONS
from tools.local_original_session.world_terrain import WorldTerrain


DIRECTORY = Path(__file__).resolve().parent / 'data' / 'm3'


def cells(rect):
    return ((x, y) for y in range(rect.y1, rect.y2 + 1)
            for x in range(rect.x1, rect.x2 + 1))


def stand_counts(terrain, map_id, rect):
    counts = Counter(terrain.can_stand(map_id, x, y) for x, y in cells(rect))
    return {'true': counts[True], 'false': counts[False],
            'unknown': counts[None], 'total': sum(counts.values())}


class M3DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exactly the same sourced readers used by with_dungeon_data.
        cls.raw_monsters = gd._read(DIRECTORY, 'monsters.json')
        cls.raw_spawns = gd._read(DIRECTORY, 'spawns.json')
        cls.raw_drops = gd._read(DIRECTORY, 'drops.json')
        cls.monsters = gd._monsters(cls.raw_monsters)
        cls.spawns = gd._spawns(cls.raw_spawns)
        cls.drops, cls.unresolved = gd._drops(cls.raw_drops)
        cls.policy = gd._Fields(cls.raw_spawns, 'spawns')('terrain_policy')
        # map0 is needed for both endpoints of the entrance/return transitions.
        cls.terrain = WorldTerrain.load(map_ids=(0, 1, 2))

    def rectangle_record(self, raw_groups, group):
        raw = raw_groups[group.group_id]
        rect = raw['rect']
        if (group.group_id.startswith('population_')
                and rect['source'] == 'local_policy'
                and rect.get('note', '').startswith(
                    'Reuse existing rectangle in the exact same map/field.')):
            # This row declares an existing rectangle, not a new terrain audit.
            # Check its actual geometry against that source and reuse only the
            # source rectangle's recorded provenance/counts below.
            owner = raw_groups[rect['ref'].split(' group=', 1)[1]]
            self.assertEqual(rect['value'], owner['rect']['value'])
            return owner
        return raw

    def test_table_references_and_sources(self):
        ids = set(self.monsters)
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(self.raw_monsters['monsters']))
        self.assertEqual(len(self.spawns), len({g.group_id for g in self.spawns}))
        self.assertEqual({g.template_id for g in self.spawns}, ids)
        self.assertEqual(set(self.drops), ids)
        self.assertEqual({g.map_id for g in self.spawns}, {1, 2})
        for g in self.spawns:
            with self.subTest(group=g.group_id):
                self.assertGreater(g.target_count, 0)
                self.assertGreaterEqual(g.respawn_delay_min_ms, 0)
                self.assertGreaterEqual(g.respawn_delay_max_ms, g.respawn_delay_min_ms)
        for template_id, rows in self.drops.items():
            with self.subTest(drops=template_id):
                pairs = [(d.item_id, d.grade) for d in rows]
                self.assertEqual(len(pairs), len(set(pairs)))
                for d in rows:
                    self.assertGreater(d.item_id, 0)
                    self.assertIn(d.grade, (0, 1, 2))
                    self.assertTrue(d.item_token)
                    self.assertTrue(d.item_name_ko)
                    self.assertGreaterEqual(d.chance, 0)
                    self.assertLessEqual(d.chance, gd.CHANCE_DENOMINATOR)
                    self.assertGreater(d.min_count, 0)
                    self.assertGreaterEqual(d.max_count, d.min_count)
        resolved = {(template_id, d.item_id, d.grade)
                    for template_id, rows in self.drops.items() for d in rows}
        unresolved = [(d.template_id, d.item_id, d.grade) for d in self.unresolved]
        self.assertEqual(len(unresolved), len(set(unresolved)))
        self.assertTrue(resolved.isdisjoint(unresolved))
        for d in self.unresolved:
            self.assertIn(d.template_id, ids)
            self.assertTrue(d.reason)
            self.assertTrue(d.ref)
            self.assertIn(d.grade, (0, 1, 2))

    def test_existing_opt_in_consumer_reads_same_three_tables(self):
        m1 = gd.load_m1()
        merged = with_dungeon_data(m1, DIRECTORY)
        self.assertEqual(merged.spawns, m1.spawns + self.spawns)
        for template_id, monster in self.monsters.items():
            self.assertEqual(merged.monsters[template_id], monster)
            self.assertEqual(merged.drops[template_id], self.drops[template_id])
        self.assertEqual(merged.drops_unresolved, m1.drops_unresolved + self.unresolved)
        self.assertIs(merged.items, m1.items)
        self.assertIs(merged.town, m1.town)

    def test_policy_thresholds_and_loaded_bounds(self):
        self.assertGreaterEqual(self.policy['min_standable_ratio'], 0.5)
        self.assertLessEqual(self.policy['min_standable_ratio'], 1)
        self.assertEqual(self.policy['max_unknown_cells'], 0)
        self.assertGreaterEqual(self.policy['min_stair_arrival_distance'], 8)
        self.assertGreaterEqual(self.policy['perception_margin'], 1)
        self.assertGreater(self.policy['center_radius'], 0)
        for row in self.raw_spawns['maps']:
            map_id = row['map_id']['value']
            with self.subTest(map_id=map_id):
                self.assertIsNone(row['classic_bounds']['value'])
                bounds = row['loaded_chunk_bounds']['value']
                self.assertEqual(tuple(bounds[k] for k in ('x1', 'y1', 'x2', 'y2')),
                                 self.terrain.bounds(map_id))

    def test_all_spawn_cells_bounds_ratio_and_recorded_counts(self):
        raw_groups = {g['group_id']['value']: g for g in self.raw_spawns['groups']}
        cache = {}
        for g in self.spawns:
            with self.subTest(group=g.group_id):
                r = g.rect
                bx1, by1, bx2, by2 = self.terrain.bounds(g.map_id)
                self.assertLessEqual(bx1, r.x1)
                self.assertLessEqual(by1, r.y1)
                self.assertLessEqual(r.x1, r.x2)
                self.assertLessEqual(r.y1, r.y2)
                self.assertLessEqual(r.x2, bx2)
                self.assertLessEqual(r.y2, by2)
                key = (g.map_id, r)
                if key not in cache:
                    cache[key] = stand_counts(self.terrain, g.map_id, r)
                counts = cache[key]
                self.assertEqual(counts['unknown'], self.policy['max_unknown_cells'])
                self.assertGreaterEqual(counts['true'] / counts['total'],
                                        self.policy['min_standable_ratio'])
                self.assertGreaterEqual(counts['true'], g.target_count)
                # Shared rectangles must also have room for their combined targets.
                total_target = sum(s.target_count for s in self.spawns
                                   if s.map_id == g.map_id and s.rect == r)
                self.assertGreaterEqual(counts['true'], total_target)
                raw = self.rectangle_record(raw_groups, g)
                self.assertEqual(raw['rect']['source'], 'local_policy')
                self.assertEqual(raw['l1j_reference_rect']['source'], 'l1j')
                origin = raw['l1j_reference_origin']['value']
                selection = raw.get('rect_selection')
                if selection is None:
                    # Original groups retain their documented +/-15 policy.
                    center, radius = origin, self.policy['center_radius']
                else:
                    self.assertEqual(selection['source'], 'local_policy')
                    chosen = selection['value']
                    center, radius = chosen['center'], chosen['radius']
                    self.assertGreater(radius, 0)
                    self.assertLessEqual(max(abs(center[k] - origin[k]) for k in ('x', 'y')),
                                         chosen['max_reference_center_offset'])
                self.assertEqual(r, gd.Rect(center['x'] - radius, center['y'] - radius,
                                            center['x'] + radius, center['y'] + radius))
                recorded = raw['terrain_check']['value']
                self.assertEqual(counts, recorded['after'])
                old_rect = gd._rect(raw['l1j_reference_rect']['value'])
                old_key = (g.map_id, old_rect)
                if old_key not in cache:
                    cache[old_key] = stand_counts(self.terrain, g.map_id, old_rect)
                self.assertEqual(cache[old_key], recorded['before'])

    def test_entire_spawn_rect_clears_every_stair_arrival(self):
        raw_groups = {g['group_id']['value']: g for g in self.raw_spawns['groups']}
        for g in self.spawns:
            # _place samples independent x/y across the entire inclusive rectangle.
            # Measure its nearest cell, not just accepted/standable samples.
            required = max(self.policy['min_stair_arrival_distance'],
                           self.monsters[g.template_id].perception_range
                           + self.policy['perception_margin'])
            distances = []
            for transition in TRANSITIONS.values():
                d = transition.destination
                if d.map_id == g.map_id:
                    with self.subTest(group=g.group_id, arrival=(d.map_id, d.x, d.y)):
                        distance = rect_distance(g.rect, d.x, d.y)
                        distances.append(distance)
                        self.assertGreaterEqual(distance, required)
            self.assertTrue(distances, g.group_id)
            self.assertEqual(min(distances),
                             self.rectangle_record(raw_groups, g)['terrain_check']['value']
                             ['min_stair_arrival_distance'])

    def test_every_stair_source_is_standable(self):
        self.assertTrue(TRANSITIONS)
        for origin in TRANSITIONS:
            with self.subTest(source=origin):
                self.assertIs(self.terrain.can_stand(*origin), True,
                              f'blocked/unknown existing stair source {origin}')

    def test_every_stair_arrival_is_standable(self):
        for transition in TRANSITIONS.values():
            d = transition.destination
            with self.subTest(arrival=(d.map_id, d.x, d.y)):
                self.assertIs(self.terrain.can_stand(d.map_id, d.x, d.y), True)


if __name__ == '__main__':
    unittest.main()
