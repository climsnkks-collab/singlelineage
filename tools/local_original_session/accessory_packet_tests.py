"""Owned 56 accessory socket coverage;614 native correspondence UNKNOWN.

Run via the prescribed run_fast.py accessory_packet_tests entry point. It reuses
the equip_all scenario once, including ordinary FIRST/login/select/world, real
0960 decoder/router and Quit/reconnect. Fresh supplies are explicitly fixtures.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import hunt_bot_play_matrix as matrix


class AccessoryPacketTests(unittest.IsolatedAsyncioTestCase):
    async def test_56_accessories_ring_slots_stats_and_reconnect(self):
        root = Path(__file__).resolve().parents[2] / 'work/local_original_session/runs'
        directory = Path(tempfile.mkdtemp(prefix='accessory-packets-', dir=root))
        args = matrix.parser().parse_args(['--scenario', 'equip_all'])
        scenario = matrix.Matrix(args, 'equip_all', directory)
        def displayed_rows(frame):
            # Include every registered send-time display hook, including the
            # ItemInfo f19 rows, in this packet fixture's expected inventory.
            from tools.local_original_session import inventory, world_bridge, world_core_kit
            projected = world_core_kit._display_rows(world_bridge.Context(scenario.broker), frame)
            result = {}
            for wire in inventory.display_kit_frames(projected):
                for raw in matrix.hb.fields(wire[4:-2]).get(1, ()):
                    fields = matrix.hb.fields(raw)
                    result[matrix.hb.scalar(fields, 1)] = {
                        key: matrix.hb.scalar(fields, key) for key in fields}
            return result
        with matrix.environment(SL_EXPERIMENT_MAP=0, SL_EXPERIMENT_SHOP=1,
                SL_EXPERIMENT_WAREHOUSE=1, SL_EXPERIMENT_ENCHANT=0,
                SL_EXPERIMENT_POLY='orc', SL_COMPANION=1, SL_COMPANION_PET_UI=1,
                SL_SPELL_EXP=0, SL_COMPANION_REVIVE_EXP=0), \
                patch.object(matrix.hb, 'displayed_rows', displayed_rows):
            result = await scenario.run_matrix()
        print('ACCESSORY_PACKET_RESULT=' + str(directory / 'result.json'), flush=True)
        self.assertEqual(result['status'], 'PASS',
            f"{directory / 'result.json'}: {result['failure']}; {result['failures']}")
        self.assertTrue(result['cleanup_complete'])
        checks = {row['check']: row for row in result['checks']}
        coverage = checks['accessory_56_all_classes_equip_and_unequip']
        self.assertEqual(len(coverage['templates']), 56)
        self.assertIn(614, coverage['templates'])
        self.assertEqual(coverage['native_unknown_templates'], [614])
        self.assertEqual(checks['accessory_614_native_inventory']['status'], 'UNKNOWN')
        for check in ('accessory_two_equal_template_rings_distinct_uids',
                'accessory_full_rings_replace_first_only',
                'accessory_second_ring_toggle_preserves_first',
                'accessory_first_free_ring_slot_reused', 'accessory_four_slots_coexist'):
            self.assertEqual(checks[check]['status'], 'PASS')
        self.assertEqual(sum(row['check'].startswith('accessory_save_reconnect_')
                             for row in result['checks']), len(scenario.accessory_characters))


def main(argv=None):
    result = unittest.main(module=__name__, argv=[__name__, *(argv or [])], exit=False)
    return 0 if result.result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
