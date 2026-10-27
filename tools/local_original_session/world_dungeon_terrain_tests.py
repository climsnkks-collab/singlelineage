"""Current-client dungeon/ship S32 cells and chunk boundaries (no client/server)."""
import unittest

from tools.local_original_session import world_terrain as wt

# Real extracted current S32 observations: chunks, walkable cell, eastward
# chunk-crossing step. These are static mask1 checks, not native gameplay PASS.
CASES = {
    5: (2, (32723, 32794), None),
    6: (2, (32750, 32792), None),
    7: (12, (32730, 32721), (32767, 32724)),
    8: (12, (32762, 32721), (32767, 32722)),
    9: (12, (32740, 32722), (32767, 32729)),
    10: (7, (32734, 32721), (32767, 32731)),
    11: (12, (32727, 32721), (32767, 32731)),
    12: (12, (32722, 32721), (32767, 32722)),
    13: (12, (32721, 32721), (32767, 32724)),
    19: (12, (32727, 32722), (32767, 32721)),
    20: (12, (32754, 32723), (32767, 32722)),
    21: (12, (32724, 32723), (32767, 32731)),
    43: (12, (32738, 32726), (32767, 32735)),
    44: (12, (32756, 32725), (32767, 32727)),
    45: (12, (32762, 32725), (32767, 32724)),
    46: (12, (32739, 32724), (32767, 32726)),
    47: (12, (32750, 32725), (32767, 32733)),
    48: (12, (32728, 32728), (32767, 32733)),
    49: (11, (32745, 32725), (32767, 32728)),
    50: (12, (32746, 32726), (32767, 32736)),
    51: (18, (32676, 32730), (32703, 32736)),
}
BOUNDS = {
    5: (32640, 32768, 32767, 32831),
    6: (32704, 32768, 32831, 32831),
    10: (32640, 32640, 32831, 32895),
    51: (32576, 32704, 32895, 32959),
}


class DungeonTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = wt.WorldTerrain.load(map_ids=tuple(CASES))

    def test_all_requested_chunks_and_bounds(self):
        for map_id, (count, _, _) in CASES.items():
            with self.subTest(map_id=map_id):
                self.assertEqual(sum(s.startswith(f'{map_id}/') for s in self.terrain.sources), count)
                self.assertEqual(self.terrain.bounds(map_id),
                                 BOUNDS.get(map_id, (32640, 32640, 32895, 32895)))

    def test_walkable_and_blocked_real_cells(self):
        for map_id, (_, walk, _) in CASES.items():
            blocked = {5: (32641, 32769), 6: (32705, 32769),
                       51: (32577, 32705)}.get(map_id, (32641, 32705))
            with self.subTest(map_id=map_id):
                self.assertIs(self.terrain.can_stand(map_id, *walk), True)
                self.assertIs(self.terrain.can_stand(map_id, *blocked), False)

    def test_dungeon_steps_cross_real_chunk_boundaries(self):
        for map_id, (_, _, seam) in CASES.items():
            if seam is None:  # Ship floors have no walkable east/west chunk seam.
                continue
            with self.subTest(map_id=map_id):
                self.assertEqual(seam[0] % wt.CHUNK, wt.CHUNK - 1)
                self.assertIs(self.terrain.can_step(map_id, *seam, 2), True)

    def test_missing_terrain_stays_unknown(self):
        for map_id in CASES:
            x1, y1, x2, y2 = self.terrain.bounds(map_id)
            with self.subTest(map_id=map_id):
                for x, y in ((x1 - 1, y1), (x1, y1 - 1), (x2 + 1, y2), (x2, y2 + 1)):
                    self.assertIsNone(self.terrain.can_stand(map_id, x, y))
                    self.assertIsNone(self.terrain.can_step(map_id, x, y, 2))
        self.assertIsNone(self.terrain.bounds(77))

    def test_lazy_ship_and_dungeon_keep_map0_and_reuse_chunks(self):
        terrain = wt.WorldTerrain.load(lazy_map_ids=wt.LAZY_MAP_IDS)
        before = terrain.half_flags(0, 32571, 32950)
        self.assertEqual(len(terrain.sources), 66)
        for map_id in (5, 7, 19, 43, 51):
            self.assertIs(terrain.can_stand(map_id, *CASES[map_id][1]), True)
        count = len(terrain.sources)
        self.assertEqual(count, 66 + sum(CASES[i][0] for i in (5, 7, 19, 43, 51)))
        for map_id in (5, 7, 19, 43, 51):
            terrain.bounds(map_id)
        self.assertEqual(len(terrain.sources), count)
        self.assertEqual(terrain.half_flags(0, 32571, 32950), before)


if __name__ == '__main__':
    unittest.main()
