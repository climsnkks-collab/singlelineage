"""Direct wire and saved-source negatives; no native/game/Store/transport."""
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory_update as u


def frame(body, opcode=u.OPCODE):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def child_frame(child):
    return frame(u.pb.encode_bytes(1, child))


class WireTests(unittest.TestCase):
    def test_minimal_exact_frame_and_immutable_presence(self):
        self.assertTrue(u.source_ready())
        wire = u.build_update({1: 0})
        self.assertEqual(wire, bytes.fromhex('0a0065090a0208000000'))
        result = u.validate_frame(wire)
        self.assertEqual(result.raw_frame, wire)
        self.assertEqual(result.raw_fields, ((1, 0),))
        self.assertEqual(result.identifier, 0)
        self.assertEqual(result.present_fields, frozenset({1}))
        with self.assertRaises(FrozenInstanceError):
            result.raw_fields = ()

    def test_optional_zero_and_empty_bytes_stay_distinct_from_absence(self):
        absent = u.validate_frame(u.build_update({1: 7}))
        explicit = u.validate_frame(u.build_update({1: 7, 4: 0, 5: 0, 7: 0, 18: b''}))
        self.assertEqual(absent.present_fields, frozenset({1}))
        self.assertEqual(explicit.present_fields, frozenset({1, 4, 5, 7, 18}))
        self.assertEqual(dict(explicit.raw_fields), {1: 7, 4: 0, 5: 0, 7: 0, 18: b''})
        self.assertNotEqual(absent.raw_frame, explicit.raw_frame)
        # Optional subsets are independent, never padded with other fields.
        for number, value in ((4, 0), (5, 0), (7, 0), (18, b'')):
            result = u.validate_frame(u.build_update({1: 7, number: value}))
            self.assertEqual(result.present_fields, frozenset({1, number}))

    def test_uint32_uint64_and_signed_int32_extremes(self):
        values = {1: 0xffffffff, 4: (1 << 64) - 1, 5: -(1 << 31), 7: (1 << 31) - 1}
        result = u.validate_frame(u.build_update(values))
        self.assertEqual(dict(result.raw_fields), values)
        values.update({4: 1 << 63, 5: -1, 7: -(1 << 31)})
        wire = u.build_update(values)
        self.assertEqual(dict(u.validate_frame(wire).raw_fields), values)
        with u.pb.parse_message(wire[4:-2]) as outer:
            with u.pb.parse_message(outer.fields[0].value) as inner:
                fields = {r.number: r.value for r in inner.fields}
                self.assertEqual(fields[5], (1 << 64) - 1)
                self.assertEqual(fields[7], 0xffffffff80000000)

    def test_opaque_bytes_and_local_bound(self):
        raw = b'\xff\0' * 128
        result = u.validate_frame(u.build_update({1: 1, 18: raw}))
        self.assertEqual(dict(result.raw_fields)[18], raw)
        self.assertLessEqual(len(result.raw_frame), u.MAX_FRAME)
        for value in (raw + b'x', bytearray(raw), 'name', None):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                u.build_update({1: 1, 18: value})
        self.assertMalformed(child_frame(b'\x08\x01' + u.pb.encode_bytes(18, raw + b'x')))

    def test_required_identifier_ranges_exact_types_and_unknown_fields(self):
        cases = [{}, {4: 0}, [], {True: 1}, {'1': 1}, {1: True}, {1: -1}, {1: 1 << 32}]
        for n, bads in ((4, (-1, 1 << 64, True)),
                        (5, (-(1 << 31) - 1, 1 << 31, True)),
                        (7, (-(1 << 31) - 1, 1 << 31, False))):
            cases.extend({1: 1, n: bad} for bad in bads)
        cases.extend({1: 1, n: 0} for n in (2, 3, 6, 19, 21, 36, 37))
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                u.build_update(fields)

    def assertMalformed(self, wire):
        with self.assertRaisesRegex(ValueError, '^MALFORMED_INVENTORY_UPDATE_SUBSET$'):
            u.validate_frame(wire)

    def test_outer_one_item_only_no_add_bool_and_frame_envelope(self):
        wire = u.build_update({1: 1})
        body = wire[4:-2]
        for invalid in (frame(body, 0x0964), frame(body, 0x0960), frame(b''),
                        frame(body * 2), frame(body + b'\x10\0'), frame(body + b'\x10\x01'),
                        frame(body + b'\x18\0'), frame(b'\x08\x01'),
                        wire[:-1], wire + b'\0', b'\0\0' + wire[2:], wire[:-2] + b'xx',
                        bytearray(wire), memoryview(wire), b'x' * (u.MAX_FRAME + 1)):
            with self.subTest(length=len(invalid)):
                self.assertMalformed(invalid)

    def test_missing_duplicate_unknown_and_wrong_wire_inner_fields(self):
        children = (b'', b'\x20\0', b'\x08\x01\x08\x01', b'\x08\x01\x10\0',
                    b'\x08\x01\xa8\x01\0', b'\x0a\0', b'\x08\x01\x22\0',
                    b'\x08\x01\x90\x01\0', b'\x08\x01\x92\x01\x02x',
                    b'\x08\x01\x20\0\x20\0')
        for child in children:
            with self.subTest(length=len(child)):
                self.assertMalformed(child_frame(child))

    def test_canonical_order_varints_signed_extension_and_wire_ranges(self):
        # Invalid uint32, truncated varint, and unsigned representations of
        # negative int32 must not be truncated/normalized into accepted values.
        children = [b'\x08' + u.pb.encode_varint(1 << 32), b'\x08\x80',
                    b'\x08\x81\0', b'\x20\0\x08\x01', b'\x08\x01\x20\x80\0']
        for n in (5, 7):
            children.extend(b'\x08\x01' + u.pb.encode_varint(n << 3) + u.pb.encode_varint(value)
                            for value in (1 << 31, 0xffffffff, 0xffffffff7fffffff))
        for child in children:
            with self.subTest(length=len(child)):
                self.assertMalformed(child_frame(child))
        # Equivalent but overlong outer length/key are outside canonical subset.
        self.assertMalformed(frame(b'\x0a\x82\0\x08\x01'))
        self.assertMalformed(frame(b'\x8a\0\x02\x08\x01'))


class SourceTests(unittest.TestCase):
    def test_each_real_source_pin_is_required_for_both_apis(self):
        wire = u.build_update({1: 1})
        for relative in u.SOURCE_PINS:
            pins = dict(u.SOURCE_PINS); pins[relative] = '0' * 64
            with self.subTest(source=relative), patch.object(u, 'SOURCE_PINS', pins):
                for call in (lambda: u.build_update({1: 1}), lambda: u.validate_frame(wire)):
                    with self.assertRaisesRegex(u.InventoryUpdateSourceError, 'SOURCE_CHANGED'):
                        call()

    def test_bounded_missing_and_oversized_saved_source(self):
        relative = next(iter(u.SOURCE_PINS))
        with tempfile.TemporaryDirectory() as directory, patch.object(u, 'ROOT', Path(directory)):
            with self.assertRaisesRegex(u.InventoryUpdateSourceError, 'SOURCE_UNAVAILABLE'):
                u.source_ready()
            path = Path(directory) / relative
            path.parent.mkdir(parents=True)
            for raw in (b'', b'x' * 1048577):
                path.write_bytes(raw)
                with self.assertRaisesRegex(u.InventoryUpdateSourceError, 'SOURCE_BOUND'):
                    u.source_ready()

    def test_control_registration_event_callback_and_descriptor_contract_negatives(self):
        original = u.ROOT
        relative = u.EVIDENCE_DIR + 'source-evidence.json'
        mutations = (
            lambda d: d.update(CONTROL_sha256='0' * 64),
            lambda d: d['binding'].update(numeric_opcode_decimal=0x0964),
            lambda d: d['binding'].update(registration='wrong'),
            lambda d: d['binding'].update(event_rva='0x17f9700'),
            lambda d: d['binding'].update(actual_invoke='wrong'),
            lambda d: d['outer_schema']['field_descriptor'].update(wire=0),
            lambda d: d['callback_fields'][0]['retained_descriptor'].update(required=False),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in u.SOURCE_PINS:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((original / name).read_bytes())
            for mutation in mutations:
                proof = json.loads((original / relative).read_bytes()); mutation(proof)
                raw = json.dumps(proof, ensure_ascii=False).encode('utf-8')
                (root / relative).write_bytes(raw)
                pins = dict(u.SOURCE_PINS); pins[relative] = hashlib.sha256(raw).hexdigest()
                with patch.object(u, 'ROOT', root), patch.object(u, 'SOURCE_PINS', pins):
                    with self.assertRaisesRegex(u.InventoryUpdateSourceError, 'SOURCE_CONTRACT_CHANGED'):
                        u.source_ready()


if __name__ == '__main__':
    unittest.main()
