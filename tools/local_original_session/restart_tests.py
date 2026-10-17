"""Pure Restart source/wire checks; no broker, game, native, ports or saves."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.local_entry_server.codecs import ClientPlaintextDecoder, ServerPlaintextDecoder
from tools.local_original_session import restart as r


def frame(body=b'\x08\x01', opcode=r.ACK_OPCODE):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


class RestartTests(unittest.TestCase):
    def parse(self, wire):
        return r.validate_ack(wire, policy=r.POLICY)

    def test_empty_original_request_decoder_payload_and_strict_local_subset(self):
        decoder = ClientPlaintextDecoder(cipher_pointer='present_disabled')
        wire = struct.pack('<HIHH', 10, 0, r.REQUEST_OPCODE, 0)
        request, = decoder.feed(wire)
        decoder.finish()
        self.assertEqual(request.opcode, r.REQUEST_OPCODE)
        self.assertEqual(request.wire_length, 10)
        self.assertIsNone(r.parse_request(request.payload))
        class BytesSubclass(bytes): pass
        for payload in (None, '', [], bytearray(), memoryview(b''), BytesSubclass(),
                        b'\0', b'\x08\0', b'\x10\0', bytes(65525)):
            with self.subTest(kind=type(payload).__name__), self.assertRaises(ValueError):
                r.parse_request(payload)

    def test_explicit_true_and_false_are_canonical_source_bool_frames(self):
        for success in (False, True):
            wire = r.build_ack(success=success, policy=r.POLICY)
            self.assertEqual(wire, frame(bytes((8, int(success)))))
            self.assertIs(self.parse(wire), success)
            decoder = ServerPlaintextDecoder()
            decoded, = decoder.feed(wire)
            decoder.finish()
            self.assertEqual((decoded.opcode, decoded.payload), (r.ACK_OPCODE, bytes((8, int(success)))))
        # Neither an absent original optional bool nor a generic empty ACK is local success.
        with self.assertRaises(ValueError): self.parse(frame(b''))

    def test_policy_default_off_and_success_must_be_explicit_bool(self):
        for policy in (None, False, 1, '', 'OTHER'):
            with self.assertRaisesRegex(ValueError, 'EXPLICIT_POLICY'):
                r.build_ack(success=True, policy=policy)
            with self.assertRaisesRegex(ValueError, 'EXPLICIT_POLICY'):
                r.validate_ack(frame(), policy=policy)
        with self.assertRaises(TypeError): r.build_ack(policy=r.POLICY)
        for success in (None, 0, 1, 2, '', 'true', [], object()):
            with self.assertRaisesRegex(ValueError, 'EXPLICIT_BOOL'):
                r.build_ack(success=success, policy=r.POLICY)

    def test_wrong_opcode_framing_bool_schema_and_canonical_refuse(self):
        good = frame()
        bad = [frame(opcode=n) for n in (r.REQUEST_OPCODE, 0x4e34, 0x4e3c, 0x4eef)]
        bad += [good[:i] for i in range(len(good))]
        bad += [good + b'\0', b'\0\0' + good[2:], b'\x09\0' + good[2:],
                good[:-1] + b'\x01', frame(b'\x08\x02'), frame(b'\x08\x7f'),
                frame(b'\x10\x01'), frame(b'\x0a\0'), frame(b'\x08\x81\0'),
                frame(b'\x88\0\x01'), frame(b'\x08\0\x08\x01'),
                frame(b'\x08\x01\x10\0'), frame(b'\x08'), frame(b'\0\0')]
        class BytesSubclass(bytes): pass
        bad += [None, '', bytearray(good), memoryview(good), BytesSubclass(good)]
        for wire in bad:
            with self.subTest(kind=type(wire).__name__), self.assertRaises(ValueError): self.parse(wire)

    def test_frozen_sources_fail_closed_in_both_builder_and_validator(self):
        r.source_ready()
        for name in r.SOURCE_PINS:
            pins = dict(r.SOURCE_PINS); pins[name] = '0' * 64
            with patch.object(r, 'SOURCE_PINS', pins):
                with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                    r.build_ack(success=True, policy=r.POLICY)
                with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'): self.parse(frame())
        with tempfile.TemporaryDirectory() as directory, patch.object(r, 'ROOT', Path(directory)):
            with self.assertRaisesRegex(ValueError, 'SOURCE_UNAVAILABLE'): r.source_ready()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'oversized'; path.write_bytes(b'x' * (r.MAX_SOURCE + 1))
            with patch.object(r, 'ROOT', Path(directory)), patch.object(r, 'SOURCE_PINS', {'oversized': '0' * 64}):
                with self.assertRaisesRegex(ValueError, 'SOURCE_BOUND'): r.source_ready()

    def test_source_schema_descriptors_and_numeric_linkage_counterexamples(self):
        original = {name: json.loads((r.ROOT / name).read_bytes())
                    for name in r.SOURCE_PINS if name.endswith('.json')}
        r._source_contract(original)
        for key, value in (('C2S_opcode', 0x4e3c), ('S2C_opcode', 0x4e34),
                           ('request_declared_fields', 1), ('request_required_fields', 1),
                           ('fresh_producer_body_bytes', 2), ('success_body_hex', '08 00'),
                           ('response_fields', [dict(number=1, wire=0, type='bool', presence='required', default=False)])):
            changed = copy.deepcopy(original)
            changed[r.INDEX]['source_contract'][key] = value
            changed[r.DETAIL]['direct_contract'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'SOURCE_SCHEMA'):
                r._source_contract(changed)
        mutations = [lambda d: d[r.DETAIL].__setitem__('CONTROL_sha256', '0' * 64),
            lambda d: d[r.DETAIL]['CS_RESTART_REQ_descriptor'].__setitem__('field_count', 1),
            lambda d: d[r.DETAIL]['SC_RESTART_ACK_descriptor'].__setitem__('entries', [[24, 128, 0, 0x1091]]),
            lambda d: d[r.DETAIL]['semantic_anchors'][3].__setitem__('operand', 'edx, 0x4e34')]
        for mutate in mutations:
            changed = copy.deepcopy(original); mutate(changed)
            with self.assertRaises(ValueError): r._source_contract(changed)


if __name__ == '__main__':
    unittest.main()
