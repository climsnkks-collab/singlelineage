"""Real original ship-route S32 service checks; no client/server/gameplay PASS."""
import unittest

from tools.local_original_session import world_terrain as wt


class ShipTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terrain = wt.WorldTerrain.load(lazy_map_ids=wt.LAZY_MAP_IDS)

    def test_native_key4_interior_loads_original_map83(self):
        self.assertIs(self.terrain.can_stand(83, 32735, 32797), True)
        self.assertEqual(self.terrain.bounds(83), (32704, 32768, 32831, 32831))
        self.assertEqual(tuple(s for s in self.terrain.sources if s.startswith('83/')),
                         ('83/7fff8000.s32', '83/80008000.s32'))

    def test_native_key4_arrival_center_and_radius_have_real_terrain(self):
        self.assertIs(self.terrain.can_stand(70, 32937, 33042), True)
        candidates = [self.terrain.can_stand(70, x, y)
                      for y in range(33035, 33050) for x in range(32930, 32945)]
        self.assertEqual(candidates.count(True), 219)
        self.assertEqual(candidates.count(False), 6)
        self.assertNotIn(None, candidates)

    def test_native_key4_dock_and_return_coordinate(self):
        self.assertIs(self.terrain.can_stand(4, 33426, 33502), True)
        dock = [self.terrain.can_stand(4, x, y)
                for y in range(33496, 33506) for x in range(33417, 33431)]
        self.assertEqual(dock.count(True), 28)
        self.assertEqual(dock.count(False), 112)
        self.assertNotIn(None, dock)


if __name__ == '__main__':
    unittest.main()
