"""Pure saved-source and protobuf fixture tests; no runtime or transport."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import item_use as use

pb = use.pb


def scalar(n, value):
    return pb.encode_varint(n << 3) + pb.encode_varint(value & use.U64_MAX)


def blob(n, raw):
    return pb.encode_varint(n << 3 | 2) + pb.encode_varint(len(raw)) + raw


def body(params=b'', identifier=0):
    # Fixtures are explicit wire bytes, never a product params builder.
    return scalar(1, identifier) + blob(2, params)


def frame(payload, mode='null', opcode=use.OPCODE):
    total = 10 + len(payload)
    if mode == 'present_disabled':
        total = ((total + 1) & ~3) + 2
    return (struct.pack('<HIHH', total - 2 if mode == 'null' else total,
                        0xfedcba98, opcode, len(payload)) + payload
            + bytes(total - 10 - len(payload)))


class ItemUseTests(unittest.TestCase):
    def test_exact_source_pins_control_and_opcode(self):
        use.source_ready()
        self.assertEqual(use.OPCODE, 2400)
        with patch.object(use, 'CONTROL_SHA256', '0' * 64):
            with self.assertRaisesRegex(use.ItemUseSourceError, 'CONTRACT_CHANGED'):
                use.source_ready()

    def test_missing_and_changed_source_each_pin(self):
        for relative in use.SOURCE_PINS:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name in use.SOURCE_PINS:
                    dest = root / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes((use.ROOT / name).read_bytes())
                target = root / relative
                original = target.read_bytes()
                target.unlink()
                with patch.object(use, 'ROOT', root):
                    with self.assertRaisesRegex(use.ItemUseSourceError, 'UNAVAILABLE'):
                        use.parse_payload(body())
                    target.write_bytes(original + b' ')
                    with self.assertRaisesRegex(use.ItemUseSourceError, 'CHANGED'):
                        use.parse_payload(body())

    def test_full_uint64_identifier_and_zero(self):
        for uid in (0, 0xffffffff, 0x100000000, 0xfedcba9876543210, use.U64_MAX):
            with self.subTest(uid=uid):
                request = use.parse_payload(body(identifier=uid))
                self.assertEqual(request.identifier, uid)
                self.assertEqual(request.raw_payload, body(identifier=uid))

    def test_required_presence_not_nonzero_or_nonempty(self):
        request = use.parse_payload(body())
        self.assertEqual(request.params.raw, b'')
        self.assertEqual(request.params.fields, ())
        self.assertFalse(request.params.has_f15_f16_presence)
        for raw in (b'', scalar(1, 0), blob(2, b'')):
            with self.subTest(raw=raw):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(raw)

    def test_parent_order_and_exact_raw_bytes_overlong_varint(self):
        raw = blob(2, b'') + b'\x08\x80\x00'
        request = use.parse_payload(raw)
        self.assertEqual(request.identifier, 0)
        self.assertEqual(request.raw_payload, raw)

    def test_parent_duplicates_wires_unknown_and_overflow(self):
        malformed = [body() + scalar(1, 1), body() + blob(2, b''),
                     blob(1, b'') + blob(2, b''), scalar(1, 0) + scalar(2, 0),
                     b'\x08' + b'\xff' * 9 + b'\x02' + blob(2, b''),
                     b'\x08\x80', scalar(1, 0) + b'\x12\x02\x08',
                     scalar(1, 0) + b'\x12\xff' * 10]
        for raw in malformed:
            with self.subTest(raw=raw):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(raw)
        with self.assertRaises(use.UnsupportedItemUse):
            use.parse_payload(scalar(3, 0) + blob(2, b''))

    def test_no_handler_presence_normalization(self):
        absent = use.parse_payload(body())
        one = use.parse_payload(body(scalar(15, 0)))
        both_raw = scalar(16, -7) + scalar(15, 0)
        both = use.parse_payload(body(both_raw))
        self.assertEqual(absent.params.present_fields, frozenset())
        self.assertEqual(one.params.present_fields, frozenset({15}))
        self.assertFalse(one.params.has_f15_f16_presence)
        self.assertTrue(both.params.has_f15_f16_presence)
        self.assertEqual(both.params.raw, both_raw)
        self.assertEqual([(r.number, r.value) for r in both.params.fields], [(16, -7), (15, 0)])

    def test_all_supported_scalar_types_and_boundaries(self):
        values = {1: -(1 << 31), 2: -(1 << 63), 3: (1 << 31) - 1,
                  4: 0, 5: -1, 6: 1, 8: 0, 9: 17, 10: -8,
                  12: 0xffffffff, 13: 0, 14: 1, 15: 0, 16: -1}
        raw = b''.join(scalar(n, value) for n, value in values.items())
        actual = use.parse_payload(body(raw)).params.fields
        self.assertEqual({r.number: r.value for r in actual}, values)
        self.assertIs(next(r.value for r in actual if r.number == 14), True)
        self.assertEqual(use.parse_payload(body(scalar(2, use.U64_MAX))).params.fields[0].value, -1)
        self.assertEqual(use.parse_payload(body(scalar(2, (1 << 63) - 1))).params.fields[0].value,
                         (1 << 63) - 1)

    def test_signed_uint32_bool_width_refusal(self):
        for raw in (scalar(1, 1 << 31), scalar(1, 0xffffffff), scalar(1, 1 << 32),
                    scalar(12, 1 << 32), scalar(14, 2), scalar(18, 0xffffffff)):
            with self.subTest(raw=raw):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(body(raw))

    def test_string_storage_is_opaque_bytes_and_empty_presence(self):
        for raw in (b'', b'\xff\xfe\x00A'):
            params = use.parse_payload(body(blob(7, raw))).params
            self.assertEqual(params.fields[0].value, raw)
            self.assertEqual(params.fields[0].kind, 'string_bytes')
            self.assertEqual(params.present_fields, frozenset({7}))

    def test_repeated_unpacked_int32_order_and_zero_occurrence(self):
        raw = scalar(18, 0) + scalar(1, 5) + scalar(18, -1) + scalar(18, 9)
        params = use.parse_payload(body(raw)).params
        self.assertEqual([(r.number, r.value) for r in params.fields],
                         [(18, 0), (1, 5), (18, -1), (18, 9)])
        self.assertEqual(params.raw, raw)
        self.assertNotIn(18, use.parse_payload(body()).params.present_fields)
        self.assertIn(18, use.parse_payload(body(scalar(18, 0))).params.present_fields)

    def test_unsupported_nested_enum_packed_and_unknown(self):
        for raw in (blob(11, b''), blob(11, scalar(1, 0)), scalar(17, 0),
                    scalar(17, use.U64_MAX), blob(18, b'\x00'), scalar(19, 0)):
            with self.subTest(raw=raw):
                with self.assertRaises(use.UnsupportedItemUse):
                    use.parse_payload(body(raw))

    def test_enum17_known_one_preserves_uid_child_presence_and_raw_order(self):
        raw = (scalar(17, 1) + scalar(1, 1) + scalar(4, 0)
               + scalar(18, 0) + scalar(18, -1))
        for uid in (0, 0x100000001, use.U64_MAX):
            with self.subTest(uid=uid):
                request = use.parse_payload(body(raw, uid))
                self.assertEqual(request.identifier, uid)
                self.assertEqual(request.raw_payload, body(raw, uid))
                self.assertEqual(request.params.raw, raw)
                self.assertEqual([(r.number, r.kind, r.value) for r in request.params.fields],
                    [(17, 'closed_enum_int32', 1), (1, 'int32', 1), (4, 'int32', 0),
                     (18, 'repeated_int32', 0), (18, 'repeated_int32', -1)])
                self.assertFalse(request.params.has_f15_f16_presence)
                self.assertNotIn(14, request.params.present_fields)
        # A received supported enum does not require or invent a UI branch's
        # other fields. Child f1 may be absent or explicitly zero on the wire.
        for child in (scalar(17, 1), scalar(1, 0) + scalar(17, 1),
                      scalar(17, 1) + scalar(15, 0) + scalar(16, 0)):
            result = use.parse_payload(body(child)).params
            self.assertEqual(result.raw, child)
        self.assertNotIn(1, use.parse_payload(body(scalar(17, 1))).params.present_fields)
        self.assertEqual(use.parse_payload(body(scalar(1, 0) + scalar(17, 1))).params.fields[0].value, 0)

    def test_enum17_other_values_absence_do_not_consume_new_source(self):
        with patch.object(use, '_enum17_one_source_ready', side_effect=AssertionError('unused')) as guard:
            self.assertEqual(use.parse_payload(body()).params.present_fields, frozenset())
            self.assertEqual(use.parse_payload(body(scalar(1, 0))).params.fields[0].value, 0)
            for value in (0, 2, -1, -(1 << 31), (1 << 31) - 1):
                with self.subTest(value=value):
                    with self.assertRaises(use.UnsupportedItemUse):
                        use.parse_payload(body(scalar(17, value)))
            guard.assert_not_called()

    def test_enum17_wrong_wire_width_overflow_and_duplicate(self):
        malformed = (blob(17, b'\x01'), scalar(17, 1 << 31), scalar(17, 0xffffffff),
                     scalar(17, 1 << 32), pb.encode_varint(17 << 3) + b'\xff' * 9 + b'\x02',
                     scalar(17, 1) + scalar(17, 1))
        for raw in malformed:
            with self.subTest(raw=raw):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(body(raw))

    def test_enum17_source_missing_changed_conditional_and_bounded(self):
        for relative in use.ENUM17_SOURCE_PINS:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name in (*use.SOURCE_PINS, *use.ENUM17_SOURCE_PINS):
                    dest = root / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes((use.ROOT / name).read_bytes())
                target = root / relative
                original = target.read_bytes()
                target.unlink()
                with patch.object(use, 'ROOT', root):
                    # Existing non-enum branch still needs only original pins.
                    self.assertEqual(use.parse_payload(body()).params.raw, b'')
                    with self.assertRaisesRegex(use.ItemUseSourceError, 'ENUM17_SOURCE_UNAVAILABLE'):
                        use.parse_payload(body(scalar(17, 1)))
                    target.write_bytes(original + b' ')
                    self.assertEqual(use.parse_payload(body()).params.raw, b'')
                    with self.assertRaisesRegex(use.ItemUseSourceError, 'ENUM17_SOURCE_CHANGED'):
                        use.parse_payload(body(scalar(17, 1)))
                    target.write_bytes(b'A' * 1048577)
                    with self.assertRaisesRegex(use.ItemUseSourceError, 'ENUM17_SOURCE_BOUND'):
                        use.parse_payload(body(scalar(17, 1)))

    def test_enum17_conditional_control_and_exact_branch_contract(self):
        original_loads = use.json.loads

        def changed_json(raw, kind):
            result = original_loads(raw)
            if result.get('schema') == 'i1-029-pc-item-ui-root-evidence-index-v1':
                if kind == 'CONTROL':
                    result['CONTROL_reference_sha256'] = '0' * 64
                elif kind == 'branch':
                    result['selected_branch_table']['selected_key_values'] = [143]
                else:
                    result['claims']['params_initialization'] = 'UNKNOWN'
            return result

        for kind in ('CONTROL', 'branch', 'raw1'):
            with self.subTest(kind=kind), patch.object(use.json, 'loads',
                    side_effect=lambda raw: changed_json(raw, kind)):
                with self.assertRaisesRegex(use.ItemUseSourceError, 'ENUM17_SOURCE_CONTRACT_CHANGED'):
                    use.parse_payload(body(scalar(17, 1)))

    def test_enum17_known_one_in_both_explicit_frames(self):
        raw = body(scalar(1, 1) + scalar(17, 1), 0xfedcba9876543210)
        for mode in ('null', 'present_disabled'):
            with self.subTest(mode=mode):
                self.assertEqual(use.parse_frame(frame(raw, mode), cipher_pointer=mode),
                                 use.parse_payload(raw))

    def test_malformed_child_and_duplicate_singletons(self):
        for raw in (b'\x00', b'\x08\x80', b'\x3a\x03a',
                    b'\x0d\0\0\0\0', blob(1, b''), scalar(7, 0),
                    scalar(15, 0) + scalar(15, 0), blob(7, b'') + blob(7, b'')):
            with self.subTest(raw=raw):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(body(raw))

    def test_local_bounds_and_exact_string_repeat_limits(self):
        use.parse_payload(body(blob(7, b'A' * use.MAX_STRING_BYTES)))
        use.parse_payload(body(scalar(18, 0) * use.MAX_REPEATED))
        for raw in (blob(7, b'A' * (use.MAX_STRING_BYTES + 1)),
                    scalar(18, 0) * (use.MAX_REPEATED + 1),
                    b'\x08\x00' * (use.MAX_PARAMS + 1)):
            with self.subTest(length=len(raw)):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(body(raw))
        with self.assertRaises(use.MalformedItemUse):
            use.parse_payload(b'A' * (use.MAX_PAYLOAD + 1))

    def test_complete_frame_both_explicit_layouts(self):
        raw = body(scalar(15, 0) + scalar(16, 0), 0x100000001)
        for mode in ('null', 'present_disabled'):
            with self.subTest(mode=mode):
                self.assertEqual(use.parse_frame(frame(raw, mode), cipher_pointer=mode),
                                 use.parse_payload(raw))

    def test_cipher_layout_requires_exact_string_type(self):
        class NonStringMode:
            def __eq__(self, other):
                return True

        class StringSubclass(str):
            pass

        for mode in (NonStringMode(), StringSubclass('null')):
            with self.subTest(kind=type(mode).__name__):
                with self.assertRaisesRegex(use.UnsupportedItemUse, 'EXPLICIT_CIPHER_LAYOUT_REQUIRED'):
                    use.parse_frame(frame(body()), cipher_pointer=mode)

    def test_frame_exact_one_truncation_lengths_layout_opcode(self):
        wire = frame(body())
        bad = [b'', wire[:-1], wire + b'\0', wire + wire,
               b'\x01\x00' + wire[2:], b'\xff\xff' + wire[2:],
               wire[:8] + b'\xff\xff' + wire[10:]]
        for raw in bad:
            with self.subTest(length=len(raw)):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_frame(raw, cipher_pointer='null')
        with self.assertRaises(use.UnsupportedItemUse):
            use.parse_frame(frame(body(), opcode=0x0964), cipher_pointer='null')
        with self.assertRaises(use.UnsupportedItemUse):
            use.parse_frame(wire, cipher_pointer='auto')
        with self.assertRaises(TypeError):
            use.parse_frame(wire)
        with self.assertRaises(use.MalformedItemUse):
            use.parse_frame(wire, cipher_pointer='present_disabled')

    def test_immutable_input_result_and_no_live_authority_claim(self):
        for raw in (bytearray(body()), memoryview(body()), None, 'abc'):
            with self.subTest(kind=type(raw).__name__):
                with self.assertRaises(use.MalformedItemUse):
                    use.parse_payload(raw)
        result = use.parse_payload(body(blob(7, b'sensitive')))
        with self.assertRaises(FrozenInstanceError):
            result.identifier = 5
        with self.assertRaises(FrozenInstanceError):
            result.params.raw = b''
        self.assertNotIn('sensitive', repr(result))
        self.assertNotIn('sensitive', repr(result.params.fields))
        self.assertFalse(hasattr(use, 'build_payload'))


if __name__ == '__main__':
    unittest.main()
