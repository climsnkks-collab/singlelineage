"""Candidate byte tests only; no broker, game, server, transport or saved writes."""
import os
import unittest
from unittest.mock import patch

from tools.local_entry_server import protobuf as wire
from tools.local_original_session.world_hpbar_experiment import build_hpbar_experiment_frames


class HpbarExperimentTests(unittest.TestCase):
    def decoded(self, uid, step):
        frames = build_hpbar_experiment_frames(uid, step=step)
        self.assertIs(type(frames), list)
        self.assertEqual(len(frames), 1)
        frame = frames[0]
        self.assertIs(type(frame), bytes)
        self.assertEqual(int.from_bytes(frame[:2], 'little'), len(frame))
        self.assertEqual(frame[-2:], b'\0\0')
        opcode = int.from_bytes(frame[2:4], 'little')
        # The world model's contract lacks 4F1A/4EC8. Reuse its underlying pure
        # wire parser, retaining field order/types and checking exact field sets.
        with wire.parse_message(frame[4:-2]) as parsed:
            self.assertTrue(all(field.wire_type == 0 for field in parsed.fields))
            fields = {field.number: field.value for field in parsed.fields}
            self.assertEqual(len(fields), len(parsed.fields))
            self.assertEqual(list(fields), sorted(fields))
        return opcode, fields

    def test_default_and_other_environment_values_are_noop(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(build_hpbar_experiment_frames(None, step=None), [])
        for mode in ('', '0', '4', 'A', 'true', '01', ' 1', '1 '):
            with self.subTest(mode=mode), patch.dict(os.environ, SL_EXPERIMENT_HPBAR=mode):
                self.assertEqual(build_hpbar_experiment_frames(None, step=None), [])

    def test_a_varies_only_f4_and_omits_f6_f7(self):
        with patch.dict(os.environ, SL_EXPERIMENT_HPBAR='1'):
            for step, value in enumerate((100, 50, 1)):
                self.assertEqual(self.decoded(65537, step),
                                 (0x4F1A, {1: 65537, 2: 100, 3: 0, 4: value, 5: 100}))
            self.assertEqual(build_hpbar_experiment_frames(65537),
                             build_hpbar_experiment_frames(65537, step=0))

    def test_b_varies_only_f2(self):
        with patch.dict(os.environ, SL_EXPERIMENT_HPBAR='2'):
            for step, value in enumerate((100, 50, 1)):
                self.assertEqual(self.decoded(65537, step),
                                 (0x4F1A, {1: 65537, 2: value, 3: 0, 4: 50, 5: 100}))

    def test_c_exact_sequence_and_bool_toggle(self):
        with patch.dict(os.environ, SL_EXPERIMENT_HPBAR='3'):
            for step, (shown, value) in enumerate(((1, 100), (1, 50), (1, 1), (1, 50), (0, 50))):
                self.assertEqual(self.decoded(65537, step),
                                 (0x4EC8, {1: 65537, 2: shown, 3: value}))

    def test_uid_boundaries_are_preserved_without_truncation(self):
        for mode, maximum in (('1', 0xFFFFFFFF), ('2', 0xFFFFFFFF), ('3', 0x7FFFFFFF)):
            with self.subTest(mode=mode), patch.dict(os.environ, SL_EXPERIMENT_HPBAR=mode):
                for uid in (1, maximum):
                    self.assertEqual(self.decoded(uid, 0)[1][1], uid)
                for uid in (0, -1, maximum + 1, (1 << 64) + 1, True, 1.0, '1', None):
                    with self.subTest(uid=uid), self.assertRaises(ValueError):
                        build_hpbar_experiment_frames(uid)

    def test_step_is_explicit_and_bounded(self):
        for mode, count in (('1', 3), ('2', 3), ('3', 5)):
            with patch.dict(os.environ, SL_EXPERIMENT_HPBAR=mode):
                for step in (-1, count, True, 0.0, '0', None):
                    with self.subTest(mode=mode, step=step), self.assertRaises(ValueError):
                        build_hpbar_experiment_frames(1, step=step)

    def test_calls_have_no_sequence_state_and_read_environment_each_time(self):
        with patch.dict(os.environ, SL_EXPERIMENT_HPBAR='1'):
            before = build_hpbar_experiment_frames(65537, step=1)
            build_hpbar_experiment_frames(65538, step=2)
            self.assertEqual(before, build_hpbar_experiment_frames(65537, step=1))
            before.clear()
            self.assertEqual(len(build_hpbar_experiment_frames(65537, step=1)), 1)
            os.environ['SL_EXPERIMENT_HPBAR'] = '3'
            self.assertEqual(self.decoded(65537, 4), (0x4EC8, {1: 65537, 2: 0, 3: 50}))
            os.environ['SL_EXPERIMENT_HPBAR'] = 'off'
            self.assertEqual(build_hpbar_experiment_frames(65537, step=4), [])

    def test_build_performs_no_file_io(self):
        with patch.dict(os.environ, SL_EXPERIMENT_HPBAR='1'), \
                patch('builtins.open', side_effect=AssertionError('file I/O')):
            self.assertEqual(len(build_hpbar_experiment_frames(65537)), 1)


if __name__ == '__main__':
    unittest.main()
