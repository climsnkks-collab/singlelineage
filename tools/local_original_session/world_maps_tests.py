"""Pure transition policy and real map1/2 S32 coverage; no game/server runs."""
from dataclasses import FrozenInstanceError
import unittest

from tools.local_original_session import world_maps as wm, world_terrain as wt


class TransitionTests(unittest.TestCase):
    def test_explicit_destinations(self):
        cases = (
            ((0, 32478, 32851), (1, 32669, 32802, 4)),
            ((1, 32669, 32802), (0, 32477, 32853, 4)),
            ((1, 32737, 32877), (2, 32665, 32789, 4)),
            ((2, 32665, 32788), (1, 32738, 32877, 2)),
        )
        self.assertEqual(len(wm.TRANSITIONS), len(cases))
        for origin, destination in cases:
            self.assertEqual(wm.resolve_transition(*origin), wm.MapDestination(*destination))

    def test_adjacent_cells_and_wrong_maps_do_not_trigger(self):
        for map_id, x, y in wm.TRANSITIONS:
            for dx, dy in wt.DELTAS:
                self.assertIsNone(wm.resolve_transition(map_id, x + dx, y + dy))
            self.assertIsNone(wm.resolve_transition(77, x, y))
        self.assertIsNone(wm.resolve_transition(False, 32477, 32851))

    def test_native_destinations_are_not_triggers(self):
        self.assertIsNone(wm.resolve_transition(0, 32477, 32853))
        self.assertIsNone(wm.resolve_transition(0, 32478, 32853))
        # L1J floor2 arrival is one cell south of its return trigger.
        self.assertIsNone(wm.resolve_transition(2, 32665, 32789))
        self.assertIsNone(wm.resolve_transition(1, 32738, 32877))

    def test_immutable_policy_preserves_evidence_status(self):
        row = wm.TRANSITIONS[(0, 32478, 32851)]
        self.assertEqual(row.source, 'local_policy/client_s32+l1j')
        self.assertEqual(row.reference_origin, (0, 32477, 32851))
        self.assertEqual(row.native_trigger_status, 'UNKNOWN')
        self.assertTrue(row.ref.endswith('l1jdb_m10.sql:14930'))
        with self.assertRaises(TypeError):
            wm.TRANSITIONS[(0, 1, 1)] = row
        with self.assertRaises(FrozenInstanceError):
            row.destination.x = 1


class DungeonTerrainTests(unittest.TestCase):
    def test_adjusted_entrance_is_reachable_from_native_destination_vicinity(self):
        terrain = wt.WorldTerrain.load(map_ids=(0,))
        self.assertIs(terrain.can_stand(0, 32477, 32851), False)
        self.assertIsNone(wm.resolve_transition(0, 32477, 32851))
        for y in (32853, 32852):
            self.assertIs(terrain.can_step(0, 32478, y, 0), True)
        self.assertIsNotNone(wm.resolve_transition(0, 32478, 32851))

    def test_real_maps_load_and_passable_cells(self):
        for map_id, count, arrival, x_end in (
                (1, 12, (32669, 32802), 32768),
                (2, 16, (32665, 32789), 32832)):
            with self.subTest(map_id=map_id):
                terrain = wt.WorldTerrain.load(map_ids=(map_id,))
                self.assertEqual(len(terrain.sources), count)
                self.assertTrue(all(source.startswith(f'{map_id}/') for source in terrain.sources))
                self.assertIsNone(terrain.bounds(0))
                self.assertIsNotNone(terrain.half_flags(map_id, *arrival))
                # Reference spawn rectangles are search areas, not native map bounds.
                self.assertTrue(any(terrain.can_stand(map_id, x, y) is True
                                    for y in range(32768, 32896)
                                    for x in range(32640, x_end)))


if __name__ == '__main__':
    unittest.main()
