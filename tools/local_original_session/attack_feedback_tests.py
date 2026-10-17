"""Pure canonical-wire checks and the existing non-native bound-target fixture."""
from dataclasses import FrozenInstanceError, replace
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import attack as a, attack_feedback as f, attack_tests


def field(number, value):
    # Independent fixture assembly, not a second product builder.
    return a.pb.encode_varint(number << 3) + a.pb.encode_varint(value & a.U64_MAX)


def frame(body, opcode=f.OPCODE):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def fields(**changes):
    values = dict(kind=1, attacker_uid=1, target_uid=2, raw_effect=0, direction=8, self_action=1)
    values.update(changes)
    return [field(n, v) for n, v in zip((1, 2, 3, 4, 5, 13), values.values())]


class WireTests(unittest.TestCase):
    def parse(self, wire):
        return f.validate_frame(wire, policy=f.POLICY)

    def test_full_uint64_signed_raw_effect_and_explicit_bool_roundtrip(self):
        for uid in (0, 1, (1 << 32), (1 << 63), a.U64_MAX):
            for raw in (-(1 << 31), -1, 0, 1, (1 << 31) - 1):
                for flag in (0, 1):
                    wire = frame(b''.join(fields(attacker_uid=uid, target_uid=uid,
                                                  raw_effect=raw, self_action=flag)))
                    self.assertEqual(self.parse(wire), f.Feedback(1, uid, uid, raw, 8, bool(flag)))
        maximum = frame(b''.join(fields(attacker_uid=a.U64_MAX, target_uid=a.U64_MAX, raw_effect=-1)))
        self.assertEqual(len(maximum), f.MAX_FRAME)
        for direction in range(9):
            self.assertEqual(self.parse(frame(b''.join(fields(direction=direction)))).direction, direction)
        self.assertIn(b'\x20' + b'\xff' * 9 + b'\x01', maximum)

    def test_default_off_and_immutable_view_is_never_send_authority(self):
        wire = frame(b''.join(fields()))
        for policy in (None, False, 1, '', 'OTHER'):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, 'EXPLICIT_POLICY'):
                f.validate_frame(wire, policy=policy)
        original = wire
        first = self.parse(wire)
        self.assertIs(wire, original)
        self.assertEqual(first, self.parse(wire))  # Parsing is not dedup/once-send.
        self.assertIsNot(first, self.parse(wire))
        with self.assertRaises(FrozenInstanceError):
            first.raw_effect = 1
        for value in (bytearray(wire), memoryview(wire), None, 'wire', bytes(46)):
            with self.assertRaises(ValueError): self.parse(value)
        class BytesSubclass(bytes): pass
        with self.assertRaises(ValueError): self.parse(BytesSubclass(wire))

    def test_exact_six_fields_no_missing_unknown_duplicate_or_reorder(self):
        rows = fields()
        bad = [b''.join(rows[:i] + rows[i + 1:]) for i in range(6)]
        bad += [b''.join(rows[:i] + [rows[i]] + rows[i:]) for i in range(6)]
        bad += [b''.join(rows[:-1] + [field(n, 0)] + rows[-1:]) for n in range(6, 13)]
        bad += [b''.join(rows) + field(14, 0), b''.join(rows) + field(15, 0)]
        for i in range(5):
            shuffled = list(rows); shuffled[i], shuffled[i + 1] = shuffled[i + 1], shuffled[i]
            bad.append(b''.join(shuffled))
        for body in bad:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError): self.parse(frame(body))

    def test_wrong_wire_types_nonminimal_values_tags_and_truncation(self):
        rows = fields()
        bad = []
        for index, number in enumerate((1, 2, 3, 4, 5, 13)):
            for replacement in (a.pb.encode_varint((number << 3) | 2) + b'\x01\x00',
                    bytes([(number << 3) | 0x80, 0]) + rows[index][1:],
                    rows[index][:1] + rows[index][1:-1] + bytes([rows[index][-1] | 0x80, 0]),
                    rows[index][:1] + b'\x80',
                    rows[index][:1] + b'\xff' * 9 + b'\x02',
                    rows[index][:1] + b'\x80' * 10 + b'\x00'):
                bad.append(b''.join(rows[:index] + [replacement] + rows[index + 1:]))
        for body in bad:
            with self.subTest(body=body.hex()), self.assertRaises(ValueError): self.parse(frame(body))
        valid = frame(b''.join(rows))
        for i in range(len(valid)):
            with self.assertRaises(ValueError): self.parse(valid[:i])

    def test_sign_overflow_kind_direction_bool_and_framing_refuse(self):
        for raw in ((1 << 31), 0xffffffff, 0xffffffff7fffffff):
            with self.assertRaises(ValueError): self.parse(frame(b''.join(fields(raw_effect=raw))))
        for key, values in [('kind', (0, 2, -1, (1 << 31))),
                            ('direction', (-1, 9, (1 << 31))), ('self_action', (2, 128))]:
            for value in values:
                with self.assertRaises(ValueError): self.parse(frame(b''.join(fields(**{key: value}))))
        wire = frame(b''.join(fields()))
        for broken in (frame(wire[4:-2], 0x4e30), wire[:-1] + b'\x01',
                       wire + b'\0', b'\x00\x00' + wire[2:],
                       wire[:4] + b'\0' * 40 + wire[-2:]):
            with self.assertRaises(ValueError): self.parse(broken)

    def test_source_pins_required_for_build_and_validation(self):
        pins = dict(f.SOURCE_PINS)
        for name in pins:
            changed = dict(pins); changed[name] = '0' * 64
            with patch.object(f, 'SOURCE_PINS', changed), self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                self.parse(frame(b''.join(fields())))
        with tempfile.TemporaryDirectory() as directory, patch.object(f, 'ROOT', Path(directory)):
            with self.assertRaisesRegex(ValueError, 'SOURCE_UNAVAILABLE'): f.source_ready()
        # Oversized ordinary file is rejected before a read or hash.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'oversized'; path.write_bytes(b'x' * (f.MAX_SOURCE + 1))
            with patch.object(f, 'ROOT', Path(directory)), patch.object(f, 'SOURCE_PINS', {'oversized': '0' * 64}):
                with self.assertRaisesRegex(ValueError, 'SOURCE_BOUND'): f.source_ready()

    def test_source_full_schema_control_required_and_rva_linkage(self):
        documents = {name: json.loads((f.ROOT / name).read_bytes())
                     for name in f.SOURCE_PINS if name.endswith('.json')}
        f._source_contract(documents)
        for index in range(14):
            bad = copy.deepcopy(documents)
            bad[f.RUN24]['schemas'][1]['decoded_fields'][index]['required'] = False if index < 5 else True
            with self.assertRaises(ValueError): f._source_contract(bad)
        for name, key, value in ((f.RUN25, 'CONTROL_sha256', '0' * 64),
                                 (f.RUN24, 'schemas', [])):
            bad = copy.deepcopy(documents); bad[name][key] = value
            with self.assertRaises(ValueError): f._source_contract(bad)
        bad = copy.deepcopy(documents)
        bad[f.RUN24]['source_spans'][8]['instructions'][2]['instruction'] = 'mov edx, 0x4e30'
        with self.assertRaises(ValueError): f._source_contract(bad)


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    # Reuse only the setup; no inherited/repeated authority test suite.
    asyncSetUp = attack_tests.TargetTests.asyncSetUp
    request = attack_tests.TargetTests.request

    async def test_existing_builder_direction8_and_f13_compatibility_same_bytes(self):
        bound = await self.targets.authorize(self.writer, self.request())
        original = a.AttackTargets.action_frame
        produced = []
        def record(targets, exact_bound, **options):
            self.assertIs(targets, self.targets); self.assertIs(exact_bound, bound)
            wire = original(targets, exact_bound, **options); produced.append(wire)
            return wire
        for raw in (-(1 << 31), -1, 0, 1, (1 << 31) - 1):
            for flag in (False, True):
                with patch.object(a.AttackTargets, 'action_frame', record):
                    wire = f.build_feedback(self.targets, bound, policy=f.POLICY,
                                           raw_effect=raw, direction=8, self_action=flag)
                self.assertIs(wire, produced[-1])
                self.assertEqual(f.validate_frame(wire, policy=f.POLICY),
                    f.Feedback(1, bound.attacker.uid, bound.target_uid, raw, 8, flag))
        omitted = original(self.targets, bound, raw_effect=0, direction=8, self_action=None)
        with self.assertRaises(ValueError): f.validate_frame(omitted, policy=f.POLICY)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()

    async def test_policy_and_each_explicit_input_refused_before_builder(self):
        bound = await self.targets.authorize(self.writer, self.request())
        defaults = dict(policy=f.POLICY, raw_effect=0, direction=8, self_action=True)
        for change in (dict(policy=None), dict(policy='OTHER'), dict(self_action=None), dict(self_action=1),
                       dict(raw_effect=True), dict(raw_effect=1 << 31), dict(raw_effect=-(1 << 31) - 1),
                       dict(direction=True), dict(direction=-1), dict(direction=9)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                f.build_feedback(self.targets, bound, **(defaults | change))
        for missing in ('raw_effect', 'direction', 'self_action'):
            options = dict(defaults); del options[missing]
            with self.assertRaises(TypeError): f.build_feedback(self.targets, bound, **options)
        with self.assertRaises(ValueError): f.build_feedback(object(), bound, **defaults)
        with self.assertRaises(ValueError): f.build_feedback(self.targets, object(), **defaults)
        self.writer.write.assert_not_called()

    async def test_original_pre_and_post_revalidation_remain_effective(self):
        bound = await self.targets.authorize(self.writer, a.AttackRequest(self.mover.state.uid))
        options = dict(policy=f.POLICY, raw_effect=0, direction=8, self_action=True)
        self.mover.state = replace(self.mover.state, packed=self.mover.state.packed + 1)
        with self.assertRaisesRegex(ValueError, 'BOUND_TARGET_STALE'):
            f.build_feedback(self.targets, bound, **options)
        self.mover.state = self.initial
        original = a.pb.encode_message
        def mutate(rows):
            body = original(rows)
            self.mover.state = replace(self.mover.state, packed=self.mover.state.packed + 1)
            return body
        with patch.object(a.pb, 'encode_message', mutate), self.assertRaisesRegex(ValueError, 'BOUND_TARGET_STALE'):
            f.build_feedback(self.targets, bound, **options)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
