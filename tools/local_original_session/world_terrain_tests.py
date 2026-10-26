"""Real map0 S32 terrain: town cells, spawn rectangles, live-observed blocked moves."""
import random
import unittest

from tools.local_original_session import world_terrain as wt, world_visibility as wv
from tools.local_original_session.game_data import load_m1

DATA = load_m1()
TERRAIN = wt.default_terrain()

# Live client tile memory, all 8 directions (work/local_native_login_*_runtime/
# tile-passability.json, lc-one-step-tile-read-v1, data_source MATRIX).
# (32571,32950): spawn_candidate/spawn_render_retry; (32571,32951): tile_budget/old_spawn.
LIVE = {
    (32571, 32950): ((4, 4), [True, True, True, True, False, True, True, True]),
    (32571, 32951): ((5, 5), [False] * 8),
}


class TerrainTests(unittest.TestCase):
    def test_town_cells_stand(self):
        for x, y in ((32578, 32946), (32577, 32946)):
            self.assertIs(TERRAIN.can_stand(0, x, y), True, (x, y))

    def test_live_observed_moves_match(self):
        for (x, y), (flags, steps) in LIVE.items():
            self.assertEqual(TERRAIN.half_flags(0, x, y), flags)
            self.assertEqual([TERRAIN.can_step(0, x, y, h) for h in range(8)], steps, (x, y))
        # Live BLOCKED: (32571,32950) heading 4 into (32571,32951).
        self.assertIs(TERRAIN.can_step(0, 32571, 32950, 4), False)
        self.assertIs(TERRAIN.can_stand(0, 32571, 32951), False)

    def test_spawn_rects_mixed(self):
        for spec in DATA.spawns:
            r = spec.rect
            counts = {True: 0, False: 0, None: 0}
            for x in range(r.x1, r.x2 + 1):
                for y in range(r.y1, r.y2 + 1):
                    counts[TERRAIN.can_stand(spec.map_id, x, y)] += 1
            total = sum(counts.values())
            self.assertEqual(counts[None], 0, spec.group_id)
            self.assertGreater(counts[True], total // 2, spec.group_id)
            self.assertGreater(counts[False], 0, spec.group_id)

    def test_unloaded_is_none(self):
        self.assertIsNone(TERRAIN.can_stand(0, 100, 100))
        self.assertIsNone(TERRAIN.can_step(0, 100, 100, 0))
        self.assertIsNone(TERRAIN.can_stand(4, 32578, 32946))
        self.assertIsNone(TERRAIN.can_step(0, 32578, 32946, 8))

    def test_view_spawns_on_standable_cells(self):
        view = wv.WorldView.create(rng=random.Random(5), clock=lambda: 100.0)
        self.assertIs(view.terrain, TERRAIN)
        view.update_pc(1, 0, 32600, 32870)
        npcs = [e for e in view.entities.near(0, 32600, 32870, 200) if e.uid != 1]
        self.assertTrue(npcs)
        for entity in npcs:
            self.assertIs(TERRAIN.can_stand(entity.map_id, entity.x, entity.y), True)


class Map1TerrainTests(unittest.TestCase):
    def test_real_map1_load_and_passable_cell(self):
        terrain = wt.WorldTerrain.load(map_ids=(1,))
        self.assertEqual(len(terrain.sources), 12)
        self.assertTrue(all(source.startswith('1/') for source in terrain.sources))
        self.assertIsNone(terrain.bounds(0))
        self.assertIsNotNone(terrain.half_flags(1, 32669, 32802))
        # Search the reference spawn area without asserting native full bounds.
        self.assertTrue(any(terrain.can_stand(1, x, y) is True
                            for y in range(32768, 32896)
                            for x in range(32640, 32768)))

    def test_map1_lazy_loading_preserves_map0(self):
        terrain = wt.WorldTerrain.load(lazy_map_ids=(1, 2))
        self.assertEqual(len(terrain.sources), 66)
        self.assertTrue(all(source.startswith('0/') for source in terrain.sources))
        before = terrain.half_flags(0, 32571, 32950)
        self.assertIsNotNone(terrain.half_flags(1, 32669, 32802))
        self.assertEqual(len(terrain.sources), 78)
        self.assertEqual(terrain.half_flags(0, 32571, 32950), before)
        self.assertIsNone(terrain.bounds(77))
        # A second query reuses map1; unqueried map2 adds no startup reads.
        self.assertIsNotNone(terrain.bounds(1))
        self.assertEqual(len(terrain.sources), 78)


if __name__ == '__main__':
    unittest.main()
