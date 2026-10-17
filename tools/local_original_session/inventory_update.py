"""Source-bound one-item SC_UPDATE_INVENTORY_NOTI (0965) wire subset only.

The original outer f1 is repeated ItemInfo, without ADD0964's outer bool. An
empty source list passes Init but is outside this local one-item subset; it
does not mean clear/remove/commit. Required f1 presence, including zero, is
wire validity only, never proof of a current matching Inventory row.

Source direct callback: f4 present calls the row+28 setter; its first write
occurs only when different (zero is not rejected). Absent skips that setter;
equal skips only its first write. Present f18 invokes copy to row+58, present
f7 copies to row+20, present f5 to row+50, in that order after f4. Missing UID
skips direct writes, with no direct create/append/remove. Omitted fields do
not imply universal unchanged state: setter/string/post-loop subeffects are
UNKNOWN. No sender, use ACK/0960 causality, quantity/equip policy or Store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import struct

from tools.local_entry_server import protobuf as pb

ROOT = Path(__file__).resolve().parents[2]
OPCODE = 0x0965
CONTROL_SHA256 = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
EVIDENCE_DIR = 'work/local_server_rea_20261016/run41_inventory_update/'
ITEM_EVIDENCE = 'work/local_server_rea_20261016/run30_inventory_first_wire/source-evidence.json'
SOURCE_PINS = {
    EVIDENCE_DIR + 'findings.md':
        '12cc8d0dc13650107dd09a7c73739bed9f8bba0ee31589d966a6cde9d7bb42a3',
    EVIDENCE_DIR + 'source-evidence.json':
        '053d771eb4191093488087477f4ccd6dedeecedcfda30d2f631a1c90b130d162',
    EVIDENCE_DIR + 'worker/source-evidence.json':
        'fbf4699e3855d3e263748958568db2ef32c2bbe101d359a47d36d67e3c37b37f',
    ITEM_EVIDENCE: '46d0d2aaaa49f2468ede8ec61383396aae81eda22f2174861a6e082ae3def5d7',
}
# Local supported subset bounds, not official protocol limits or field policy.
MAX_FRAME = 1024
MAX_BYTES = 256
U64_MAX = (1 << 64) - 1
FIELD_TYPES = {1: 'u32', 4: 'u64', 5: 'i32', 7: 'i32', 18: 'bytes'}


class InventoryUpdateSourceError(ValueError):
    pass


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def source_ready():
    """Bounded saved evidence only; no native code, producer or live authority."""
    documents = {}
    for relative, expected in SOURCE_PINS.items():
        try:
            with (ROOT / relative).open('rb') as stream:
                raw = stream.read(1048577)
        except OSError:
            raise InventoryUpdateSourceError('INVENTORY_UPDATE_SOURCE_UNAVAILABLE') from None
        if not 0 < len(raw) <= 1048576:
            raise InventoryUpdateSourceError('INVENTORY_UPDATE_SOURCE_BOUND')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise InventoryUpdateSourceError('INVENTORY_UPDATE_SOURCE_CHANGED')
        if relative.endswith('.json'):
            documents[relative] = json.loads(raw)
    try:
        proof = documents[EVIDENCE_DIR + 'source-evidence.json']
        worker = documents[EVIDENCE_DIR + 'worker/source-evidence.json']
        retained = documents[ITEM_EVIDENCE]
        binding, outer = proof['binding'], proof['outer_schema']
        schema, = [s for s in retained['schemas'] if s['label'] == 'ItemInfo']
        descriptors = {r['field']: r for r in schema['fields']}
        expected = {1: ('0x891', 0x70, 3, True), 4: ('0x8d1', 0x80, 6, False),
                    5: ('0x1091', 0x90, 8, False), 7: ('0x1091', 0x94, 9, False),
                    18: ('0x815', 0x58, 0, False)}
        descriptor = outer['field_descriptor']
        _need(all(d['CONTROL_sha256'] == CONTROL_SHA256 for d in (proof, worker, retained))
              and binding['numeric_opcode_hex'] == '0x965'
              and binding['numeric_opcode_decimal'] == OPCODE
              and binding['registration'] == '29438D table11AAB58 /294394 EDX0965 /2943AC→292F80'
              and binding['factory_actual_invoke'] == '11AAB58+10→30B7E0'
              and binding['event_rva'] == '0x17f97c0'
              and binding['register'] == '4FB848 R8=4F7670 /RDX=Inventoryowner RDI /4FB852 sameevent /4FB859→4F9300'
              and binding['actual_invoke'] == 'reused4F9300→4F9890 capture(owner,4F7670) clone4FA040→node+58→27714F vslot10=4FA010→captured function4F7670'
              and worker['binding'] == binding, 'binding')
        _need(outer == worker['outer_schema'] and outer['rva'] == '0x1601530'
              and outer['header_u32'] == ['0x0', '0x1', '0x400000', '0xfffffffe',
                                          '0x44', '0x10001', '0x50', '0x0']
              and (descriptor['field'], descriptor['wire'], descriptor['type_card'],
                   descriptor['object_offset'], descriptor['raw_presence_word']) ==
                  (1, 2, '0x426', '0x10', 0)
              and outer['aux_slot']['target'] == schema['schema_rva'] == '0x1603a28'
              and schema == worker['retained_ItemInfo_schema']
              and schema['field_count'] == len(descriptors) == len(schema['fields']) == 35
              and schema['missing_field_numbers'] == [21]
              and [r['field'] for r in schema['fields'] if r['required']] == [1]
              and all((descriptors[n]['type_card'], descriptors[n]['object_offset'],
                       descriptors[n]['presence_bit'], descriptors[n]['required']) == contract
                      and descriptors[n]['repeated'] is False for n, contract in expected.items()),
              'schema')
        fields = proof['callback_fields']
        _need(fields == worker['callback_fields']
              and [r['field'] for r in fields] == [1, 4, 18, 7, 5]
              and [(r['DTO_offset'], r['row_offset'], r['presence']) for r in fields] ==
                  [('0x70', '0x8', 'required'), ('0x80', '0x28', 'optional'),
                   ('0x58', '0x58', 'optional'), ('0x94', '0x20', 'optional'),
                   ('0x90', '0x50', 'optional')]
              and all(r['retained_descriptor'] == descriptors[r['field']] for r in fields),
              'selected_fields')
    except (KeyError, TypeError, ValueError):
        raise InventoryUpdateSourceError('INVENTORY_UPDATE_SOURCE_CONTRACT_CHANGED') from None
    return True


@dataclass(frozen=True, slots=True)
class InventoryUpdate:
    """Immutable exact canonical frame and present field values; no state claim."""
    raw_fields: tuple[tuple[int, int | bytes], ...] = field(repr=False)
    raw_frame: bytes = field(repr=False)

    @property
    def identifier(self) -> int:
        return dict(self.raw_fields)[1]

    @property
    def present_fields(self) -> frozenset[int]:
        return frozenset(n for n, _ in self.raw_fields)


def _values(fields):
    _need(type(fields) is dict and all(type(n) is int for n in fields)
          and 1 in fields and fields.keys() <= FIELD_TYPES.keys(),
          'INVENTORY_UPDATE_FIELDS_REQUIRED')
    for n, value in fields.items():
        kind = FIELD_TYPES[n]
        if kind == 'bytes':
            _need(type(value) is bytes and len(value) <= MAX_BYTES,
                  'INVENTORY_UPDATE_BYTES_BOUND')
        else:
            low, high = {'u32': (0, 1 << 32), 'u64': (0, 1 << 64),
                         'i32': (-(1 << 31), 1 << 31)}[kind]
            _need(type(value) is int and low <= value < high,
                  'INVENTORY_UPDATE_SCALAR_RANGE')
    return tuple(sorted(fields.items()))


def _encode(raw_fields):
    child = b''.join(pb.encode_bytes(n, value) if FIELD_TYPES[n] == 'bytes' else
                     pb.encode_varint(n << 3) + pb.encode_varint(value & U64_MAX)
                     for n, value in raw_fields)
    body = pb.encode_bytes(1, child)
    return struct.pack('<HH', len(body) + 6, OPCODE) + body + b'\0\0'


def build_update(fields: dict[int, int | bytes]) -> bytes:
    """Explicit raw choices only. Missing optionals stay absent; no defaults."""
    source_ready()
    return _encode(_values(fields))


def validate_frame(wire: bytes) -> InventoryUpdate:
    """Exactly one canonical ItemInfo with only f1/f4/f5/f7/f18 supported."""
    source_ready()
    try:
        _need(type(wire) is bytes and 6 <= len(wire) <= MAX_FRAME
              and int.from_bytes(wire[:2], 'little') == len(wire)
              and int.from_bytes(wire[2:4], 'little') == OPCODE and wire[-2:] == b'\0\0',
              'frame')
        limits = pb.WireLimits(max_body=MAX_FRAME, max_fields=6, max_field_bytes=512)
        with pb.parse_message(wire[4:-2], schema={1: 2}, limits=limits) as outer:
            _need(len(outer.fields) == 1, 'one_item')
            with pb.parse_message(outer.fields[0].value,
                    schema={n: 2 if kind == 'bytes' else 0 for n, kind in FIELD_TYPES.items()},
                    limits=limits) as inner:
                _need(len({r.number for r in inner.fields}) == len(inner.fields), 'unique_fields')
                fields = {}
                for row in inner.fields:
                    value = row.value
                    if FIELD_TYPES[row.number] == 'bytes':
                        value = bytes(value)
                    elif FIELD_TYPES[row.number] == 'i32' and value >= 1 << 31:
                        _need(value >= 0xffffffff80000000, 'signextended_i32')
                        value -= 1 << 64
                    fields[row.number] = value
                raw_fields = _values(fields)
        _need(_encode(raw_fields) == wire, 'canonical_frame')
        return InventoryUpdate(raw_fields, wire)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('MALFORMED_INVENTORY_UPDATE_SUBSET') from None
