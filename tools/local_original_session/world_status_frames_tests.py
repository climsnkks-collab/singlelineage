"""SC_STATUS byte round trips only; no game, transport or saved writes."""
from dataclasses import replace
import struct
from types import MappingProxyType
import unittest

from tools.local_original_session.world_reward import KillReward
from tools.local_original_session.world_status_frames import build_status_frames
from tools.local_world_protocol import model as world


def decode_status(test, frame):
    test.assertIs(type(frame), bytes)
    test.assertEqual(int.from_bytes(frame[:2], 'little'), len(frame))
    test.assertEqual(frame[2:4], b'\x38\x4e')
    test.assertEqual(frame[-2:], b'\0\0')
    body = frame[4:-2]
    # f26 is last in canonical full-status order. Decode its actual wire1 key,
    # then let the unchanged existing decoder verify every remaining field.
    tag = world.wire.encode_varint((26 << 3) | 1)
    test.assertEqual(body[-10:-8], tag)
    fields = world.decode_payload(0x4E38, body[:-10])
    fields[26] = struct.unpack('<d', body[-8:])[0]
    return fields


class WorldStatusFramesTests(unittest.TestCase):
    def setUp(self):
        self.status = {1: 65537, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12,
                       8: 14, 9: 15, 10: 8, 11: 20, 12: 3, 13: 10,
                       14: -10, 15: 1793000000, 16: 200, 17: 7, 18: -123,
                       20: 9}
        self.reward = KillReward(1, 125, 1, 2, 1, 32, 12, [], ())

    def fields(self, reward=None, status=None, **kwargs):
        frames = build_status_frames(self.reward if reward is None else reward,
                                     self.status if status is None else status,
                                     **kwargs)
        self.assertIs(type(frames), list)
        self.assertEqual(len(frames), 1)
        return decode_status(self, frames[0])

    def test_level_up_updates_final_level_maxima_and_exp_only(self):
        actual = self.fields(exp_percent=0.125)
        expected = {**self.status, 2: 2, 11: 32, 13: 12, 26: 0.125}
        self.assertEqual(actual, expected)
        # Raw cumulative EXP125 is not substituted for the display percent.
        self.assertNotEqual(actual[26], self.reward.new_exp)

    def test_non_level_up_still_emits_exp_change(self):
        reward = replace(self.reward, new_exp=25, new_level=1, level_ups=0,
                         max_hp=20, max_mp=10)
        self.assertEqual(self.fields(reward, exp_percent=20.5),
                         {**self.status, 26: 20.5})

    def test_multi_level_gain_emits_one_final_snapshot(self):
        reward = replace(self.reward, exp_gained=750, new_exp=750,
                         new_level=5, level_ups=4, max_hp=67, max_mp=18)
        self.assertEqual(self.fields(reward, exp_percent=1.2345),
                         {**self.status, 2: 5, 11: 67, 13: 18, 26: 1.2345})

    def test_explicit_current_resources_stats_and_ac(self):
        updates = {4: 18, 5: 17, 6: 16, 7: 15, 8: 14, 9: 13,
                   10: 19, 12: 7, 14: -14}
        before = dict(self.status)
        actual = self.fields(status=MappingProxyType(self.status),
                             exp_percent=2.5, status_updates=MappingProxyType(updates))
        self.assertEqual(actual, {**before, **updates, 2: 2, 11: 32, 13: 12, 26: 2.5})
        self.assertEqual(self.status, before)
        self.assertEqual(updates[10], 19)

    def test_unknown_max_mp_preserves_existing_full_status_values(self):
        actual = self.fields(replace(self.reward, max_mp=None), exp_percent=3.0)
        self.assertEqual((actual[12], actual[13]), (3, 10))
        incomplete = {k: v for k, v in self.status.items() if k != 13}
        with self.assertRaisesRegex(world.ContractError, 'MISSING_REQUIRED_FIELD'):
            self.fields(replace(self.reward, max_mp=None), incomplete, exp_percent=3.0)

    def test_optional_fields_are_preserved_and_previous_f26_is_replaced_once(self):
        optional = {3: (1 << 62) + 17, 21: -1, 22: 2, 23: 3, 24: 4, 25: -5}
        status = {**self.status, **optional, 26: 98.7654}
        before = dict(status)
        actual = self.fields(status=status, exp_percent=12.3456789)
        self.assertEqual(actual, {**before, 2: 2, 11: 32, 13: 12, 26: 12.3456789})
        self.assertEqual(status, before)
        # Existing decoder above would reject any duplicate or leftover f26.

    def test_explicit_percent_is_required_and_not_clamped(self):
        with self.assertRaises(TypeError):
            build_status_frames(self.reward, {**self.status, 26: 90.0})
        for percent in (-0.25, 100.5):
            with self.subTest(percent=percent):
                self.assertEqual(self.fields(exp_percent=percent)[26], percent)

    def test_unsupported_optional_field_is_not_silently_discarded(self):
        with self.assertRaisesRegex(world.ContractError, 'UNSUPPORTED_SOURCE_SCALAR_LAYOUT'):
            self.fields(status={**self.status, 19: [1, 2]}, exp_percent=1.0)

    def test_updates_cannot_overwrite_reward_or_unrelated_status_fields(self):
        for number in (1, 2, 11, 13, 15, 26):
            with self.subTest(number=number), self.assertRaises(ValueError):
                self.fields(exp_percent=1.0, status_updates={number: 99})


if __name__ == '__main__':
    unittest.main()
