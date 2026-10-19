"""REQ92/run98 strict local DROP/GET/Inventory-remove wire subset.

DROP's original repeated f1 is deliberately limited to exactly one child here;
GET requires its singular f1. Coordinates are canonical signed int32, UID/Q
are full uint64, and required present-zero is preserved. Payloads must use
canonical varints and field order; unknown/duplicate fields are refused.

Zero UID/Q and negative coordinates remain representable wire values. Positive
count, current ownership/quantity, INT32 DROP-popup admission, cancellation,
epoch/once, transport and durable effects belong to a separate local policy.
In particular invalid/empty original popup input is NOT a cancel/no-op here.
No popup emulator, sender, ground appearance/packet or UID mapping is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

from tools.local_entry_server import codecs, protobuf as pb

def _module_root(path):
    """Only the assigned private product and canonical tools layouts."""
    names = tuple(parent.name for parent in path.parents)
    if names[:2] == ('local_original_session', 'tools'):
        return path.parents[2]
    if names[:6] == ('product', 'drop-pickup', 'item-equipment-product',
                     'implementation-1', 'local_original_session', 'work'):
        return path.parents[6]
    raise ImportError('TRANSFER_MODULE_LAYOUT_REQUIRED')


ROOT = _module_root(Path(__file__).resolve())
EVIDENCE = 'work/local_server_rea_20261016/run98_item_drop_pickup_contract/'
CONTROL_SHA256 = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
DROP_OPCODE, GET_OPCODE, REMOVE_OPCODE = 0x4E3F, 0x4E3E, 0x0978
I32_MIN, I32_MAX, U64_MAX = -(1 << 31), (1 << 31) - 1, (1 << 64) - 1
MAX_PAYLOAD, MAX_REQUEST_FRAME, MAX_REMOVE_FRAME = 64, 80, 32
SOURCE_PINS = MappingProxyType({
    EVIDENCE + 'findings.md': '39de7bae69e54d9fd35d3d6b43cd5ac4a31ada3d26201fd43760b028bf3bb098',
    EVIDENCE + 'implementation-conditions.md': 'c83fbf9c1ad6192c83148652084a2646743ef1bbb9949d626c23fbec4354dc01',
    EVIDENCE + 'main-review.json': 'cb261065f0cd944758924e5a82e412d957df29e3b618177069bf67fd9613b65c',
    EVIDENCE + 'source-evidence.json': 'cbd1d676d0f3536fc4c6772e40c885a126fb214430d25bc9f517d1ed81cef02c',
    EVIDENCE + 'worker/source-evidence.json': '4159a5fb87749ebc91a79849b68240551cfe9e50bcb0f64b6b20c55890ec65af',
})


class TransferProtocolError(ValueError):
    """Fixed codes only; never attach wire bytes, UID or coordinates."""


def _need(condition, reason):
    if not condition:
        raise TransferProtocolError(reason)


def _source_contract(index, worker, review):
    """Validate only the already accepted selected schema/registration facts."""
    try:
        _need(index['schema'] == 'req92-source-index/v1' and
              index['status'] == 'STATIC_DROP_GET_AND_ADJACENT_CONSUMERS_CLOSED_TEMPLATE1_GROUND_INPUT_AND_CAUSAL_MAPPING_UNKNOWN' and
              index['source_authority']['CONTROL_sha256'] == CONTROL_SHA256 and
              worker['schema'] == 'req92-drop-pickup-source-v1' and
              worker['CONTROL_sha256'] == CONTROL_SHA256 and
              review['schema'] == 'req92-main-nonauthor-risk-review/v1' and review['passed'] is True,
              'TRANSFER_SOURCE_IDENTITY_CHANGED')
        refs = {row['path']: row for row in index['artifacts']}
        for name in ('worker/source-evidence.json', 'main-review.json'):
            _need(refs[EVIDENCE + name]['sha256'] == SOURCE_PINS[EVIDENCE + name],
                  'TRANSFER_SOURCE_REFERENCE_CHANGED')
        _need(review['primary_worker']['path'] == EVIDENCE + 'worker/source-evidence.json' and
              review['primary_worker']['sha256'] == SOURCE_PINS[EVIDENCE + 'worker/source-evidence.json'],
              'TRANSFER_SOURCE_REVIEW_BINDING_CHANGED')
        schemas = worker['schemas']
        _need(len(schemas) == 4, 'TRANSFER_SOURCE_SCHEMA_CHANGED')
        expected = (
            ('CS_DROP_ITEM_REQ', '0x15ef1d0', [(1, None, '0x426', True)]),
            ('CS_DROP_ITEM_REQ repeated child', '0x15ef290',
             [(1, 0, '0x1091', False), (2, 1, '0x1091', False),
              (3, 2, '0x8d1', False), (4, 3, '0x8d1', False)]),
            ('CS_GET_ITEM_REQ', '0x15ef230', [(1, 0, '0x416', False)]),
            ('SC_REMOVE_INVENTORY_NOTI', '0x1604ea8', [(1, 0, '0x8d1', False)]),
        )
        for schema, (label, rva, fields) in zip(schemas, expected):
            _need(schema['label'] == label and schema['rva'] == rva and
                  [(r['field'], r['presence_bit'], r['type_card'], r['repeated']) for r in schema['fields']] == fields,
                  'TRANSFER_SOURCE_SCHEMA_CHANGED')
        _need(schemas[0]['auxiliary_slots'][0]['target'] == schemas[2]['auxiliary_slots'][0]['target'] == '0x15ef290',
              'TRANSFER_SOURCE_CHILD_BINDING_CHANGED')
        contract = worker['contracts']
        drop, get, remove = contract['DROP'], contract['GET'], contract['ROW_REMOVE']
        _need(drop['opcode'] == '0x4e3f' and drop['sender'] == '0x3cf00' and
              get['opcode'] == '0x4e3e' and get['sender'] == '0x3cd90' and
              drop['child_schema'] == get['child_schema'] == '0x15ef290' and
              [(r['field'], r['type'], r['wire'], r['required']) for r in drop['child_fields']] ==
              [(1, 'int32', 0, True), (2, 'int32', 0, True), (3, 'uint64', 0, True), (4, 'uint64', 0, True)] and
              remove['opcode'] == '0x0978' and remove['event'] == '0x17fa300' and
              remove['consumer'] == '0x4f6920 saved' and
              remove['register'] == '2945A9..2945CD ->11AA8B8+10=30A250',
              'TRANSFER_SOURCE_CONSUMER_CHANGED')
    except (KeyError, TypeError, IndexError):
        raise TransferProtocolError('TRANSFER_SOURCE_CONTRACT_CHANGED') from None
    return True


def source_ready():
    """Five bounded saved documents; no original reread/decode or 35-ref audit."""
    documents = {}
    for name, expected in SOURCE_PINS.items():
        try:
            with (ROOT / name).open('rb') as stream:
                raw = stream.read(1_048_577)
        except OSError:
            raise TransferProtocolError('TRANSFER_SOURCE_UNAVAILABLE') from None
        _need(0 < len(raw) <= 1_048_576, 'TRANSFER_SOURCE_BOUND')
        _need(hashlib.sha256(raw).hexdigest() == expected, 'TRANSFER_SOURCE_CHANGED')
        if name.endswith('.json'):
            try:
                documents[name] = json.loads(raw)
            except (ValueError, UnicodeError):
                raise TransferProtocolError('TRANSFER_SOURCE_JSON_INVALID') from None
    return _source_contract(documents[EVIDENCE + 'source-evidence.json'],
                            documents[EVIDENCE + 'worker/source-evidence.json'],
                            documents[EVIDENCE + 'main-review.json'])


def _fields(value):
    _need(type(value.x) is int and I32_MIN <= value.x <= I32_MAX and
          type(value.y) is int and I32_MIN <= value.y <= I32_MAX and
          type(value.uid) is int and 0 <= value.uid <= U64_MAX and
          type(value.quantity) is int and 0 <= value.quantity <= U64_MAX,
          'TRANSFER_EXACT_FIELD_RANGES_REQUIRED')


@dataclass(frozen=True, slots=True, repr=False)
class DropRequest:
    x: int
    y: int
    uid: int
    quantity: int

    def __post_init__(self):
        _fields(self)


@dataclass(frozen=True, slots=True, repr=False)
class GetRequest:
    x: int
    y: int
    uid: int
    quantity: int

    def __post_init__(self):
        _fields(self)


@dataclass(frozen=True, slots=True, repr=False)
class RemoveInventory:
    uid: int

    def __post_init__(self):
        _need(type(self.uid) is int and 0 <= self.uid <= U64_MAX, 'TRANSFER_UINT64_UID_REQUIRED')


def _child(value):
    return b''.join(pb.encode_varint(n << 3) + pb.encode_varint(v & U64_MAX)
                    for n, v in enumerate((value.x, value.y, value.uid, value.quantity), 1))


def _payload(value):
    return pb.encode_bytes(1, _child(value))


def build_drop_payload(request):
    source_ready()
    _need(type(request) is DropRequest, 'TRANSFER_DROP_REQUEST_REQUIRED')
    _fields(request)
    return _payload(request)


def build_get_payload(request):
    source_ready()
    _need(type(request) is GetRequest, 'TRANSFER_GET_REQUEST_REQUIRED')
    _fields(request)
    return _payload(request)


def _int32(value):
    if value <= I32_MAX:
        return value
    _need(value >= 0xFFFFFFFF80000000, 'TRANSFER_CANONICAL_INT32_REQUIRED')
    return value - (1 << 64)


def _parse_payload(payload, kind):
    source_ready()
    _need(type(payload) is bytes and len(payload) <= MAX_PAYLOAD, 'TRANSFER_IMMUTABLE_BOUNDED_PAYLOAD_REQUIRED')
    try:
        with pb.parse_message(payload, schema={1: 2},
                              limits=pb.WireLimits(max_body=MAX_PAYLOAD, max_fields=1, max_field_bytes=48)) as parent:
            _need(len(parent.fields) == 1, 'TRANSFER_ONE_REQUIRED_CHILD')
            child = bytes(parent.occurrences(1)[0].value)
            with pb.parse_message(child, schema={1: 0, 2: 0, 3: 0, 4: 0},
                                  limits=pb.WireLimits(max_body=48, max_fields=4, max_field_bytes=0)) as fields:
                _need(len(fields.fields) == 4 and all(len(fields.occurrences(n)) == 1 for n in range(1, 5)),
                      'TRANSFER_REQUIRED_UNIQUE_FIELDS')
                values = [fields.occurrences(n)[0].value for n in range(1, 5)]
                request = kind(_int32(values[0]), _int32(values[1]), values[2], values[3])
        _need(_payload(request) == payload, 'TRANSFER_CANONICAL_PAYLOAD_REQUIRED')
        return request
    except pb.WireError:
        raise TransferProtocolError('TRANSFER_MALFORMED_PAYLOAD') from None


def parse_drop_payload(payload):
    """Local exactly-one subset of original repeated outer f1, not all DROP."""
    return _parse_payload(payload, DropRequest)


def parse_get_payload(payload):
    return _parse_payload(payload, GetRequest)


def _parse_frame(wire, cipher_pointer, opcode, parser):
    _need(type(wire) is bytes and len(wire) <= MAX_REQUEST_FRAME, 'TRANSFER_IMMUTABLE_BOUNDED_FRAME_REQUIRED')
    _need(type(cipher_pointer) is str and cipher_pointer in ('null', 'present_disabled'),
          'TRANSFER_EXPLICIT_CIPHER_LAYOUT_REQUIRED')
    try:
        decoder = codecs.ClientPlaintextDecoder(cipher_pointer=cipher_pointer,
                    max_frame=MAX_REQUEST_FRAME, max_buffer=MAX_REQUEST_FRAME)
        frames = decoder.feed(wire)
        decoder.finish()
        _need(len(frames) == 1 and frames[0].opcode == opcode, 'TRANSFER_ONE_EXPECTED_FRAME_REQUIRED')
        return parser(frames[0].payload)
    except codecs.FrameError:
        raise TransferProtocolError('TRANSFER_MALFORMED_FRAME') from None


def parse_drop_frame(wire, *, cipher_pointer):
    """Sequence/padding layout only, never send/receipt/current authority."""
    return _parse_frame(wire, cipher_pointer, DROP_OPCODE, parse_drop_payload)


def parse_get_frame(wire, *, cipher_pointer):
    return _parse_frame(wire, cipher_pointer, GET_OPCODE, parse_get_payload)


def _remove_frame(value):
    body = pb.encode_varint(8) + pb.encode_varint(value.uid)
    return struct.pack('<HH', len(body) + 6, REMOVE_OPCODE) + body + b'\0\0'


def build_remove(*, uid):
    """SC0978 only; no ground-remove4E40 or custody/UID mapping construction."""
    source_ready()
    return _remove_frame(RemoveInventory(uid))


def parse_remove_frame(wire):
    """Canonical local S2C envelope uses original product's zero final2 bytes."""
    source_ready()
    _need(type(wire) is bytes and 6 <= len(wire) <= MAX_REMOVE_FRAME and
          int.from_bytes(wire[:2], 'little') == len(wire) and
          int.from_bytes(wire[2:4], 'little') == REMOVE_OPCODE,
          'TRANSFER_REMOVE_FRAME_REQUIRED')
    try:
        with pb.parse_message(wire[4:-2], schema={1: 0},
                              limits=pb.WireLimits(max_body=MAX_REMOVE_FRAME, max_fields=1, max_field_bytes=0)) as fields:
            _need(len(fields.fields) == 1, 'TRANSFER_REMOVE_REQUIRED_UID')
            value = RemoveInventory(fields.occurrences(1)[0].value)
        _need(_remove_frame(value) == wire, 'TRANSFER_CANONICAL_REMOVE_FRAME_REQUIRED')
        return value
    except pb.WireError:
        raise TransferProtocolError('TRANSFER_MALFORMED_REMOVE_FRAME') from None
