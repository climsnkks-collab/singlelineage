"""Bounded parser-only CS_USE_ITEM_REQ (0960), from reviewed run37 evidence.

Results describe received bytes, never current Inventory selection, use authority,
an original UI params producer, transport receipt, equip success or server ACK.
No builder/default params/handler normalization or sender is provided. In
particular schema-empty f2 is valid wire but is not normal UI/sender provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from tools.local_entry_server import codecs, protobuf as pb

ROOT = Path(__file__).resolve().parents[2]
OPCODE = 0x0960
CONTROL_SHA256 = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
EVIDENCE_DIR = 'work/local_server_rea_20261016/run37_item_command_sender/'
SOURCE_PINS = {
    EVIDENCE_DIR + 'findings.md':
        '7a6554ee69e06080ff100fe80482753f7c5257a9c8cc708974173f7d7da11f3d',
    EVIDENCE_DIR + 'source-evidence.json':
        'dbaccb1063632163fefaa9ca0dfd046aff716d802ff15f8baf4639f703800ff2',
    EVIDENCE_DIR + 'worker/source-evidence.json':
        '9ae9425c6c5b322ee0577ad718424fc46e71ac456b316162482f6ff7b1792b7c',
}
ENUM17_EVIDENCE_DIR = 'work/local_server_rea_20261016/run39_item_ui_producer/'
ENUM17_SOURCE_PINS = {
    ENUM17_EVIDENCE_DIR + 'findings.md':
        'c467dbea5cf31bd7b6d04835e9c627bdfc2c67544371a65270e0431105cab44c',
    ENUM17_EVIDENCE_DIR + 'source-evidence.json':
        '9dbcc274e77a0b238079521c45e83b77559de746bee2dcc7ba9fce2493b9ccbc',
}
U64_MAX = (1 << 64) - 1
# Local supported subset limits, not inferred official protocol limits.
MAX_PAYLOAD = 4096
MAX_PARAMS = 2048
MAX_STRING_BYTES = 1024
MAX_REPEATED = 64
MAX_FRAME = MAX_PAYLOAD + 12
PARAM_TYPES = {1: 'int32', 2: 'int64', 3: 'int32', 4: 'int32',
               5: 'int32', 6: 'int32', 7: 'string_bytes', 8: 'int32',
               9: 'int32', 10: 'int32', 12: 'uint32', 13: 'int32',
               14: 'bool', 15: 'int32', 16: 'int32', 18: 'repeated_int32'}


class ItemUseError(ValueError):
    """Fixed codes only; subclasses distinguish source, malformed, unsupported."""


class ItemUseSourceError(ItemUseError):
    pass


class MalformedItemUse(ItemUseError):
    pass


class UnsupportedItemUse(ItemUseError):
    pass


def source_ready():
    """Read only pinned saved text/JSON; no executable/producer inspection."""
    documents = {}
    for relative, expected in SOURCE_PINS.items():
        try:
            with (ROOT / relative).open('rb') as stream:
                raw = stream.read(1048577)
        except OSError:
            raise ItemUseSourceError('ITEM_USE_SOURCE_UNAVAILABLE') from None
        if not 0 < len(raw) <= 1048576:
            raise ItemUseSourceError('ITEM_USE_SOURCE_BOUND')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ItemUseSourceError('ITEM_USE_SOURCE_CHANGED')
        if relative.endswith('.json'):
            documents[relative] = json.loads(raw)
    proof = documents[EVIDENCE_DIR + 'source-evidence.json']
    worker = documents[EVIDENCE_DIR + 'worker/source-evidence.json']
    parent, child = proof['message_schemas']
    catalog = proof['retained_nested_catalog']
    parent_shape = [(r['field'], r['required'], r['type_card'], r['presence_bit'])
                    for r in parent['fields']]
    types = {r['field']: r['storage_type'] for r in catalog['fields']}
    expected_types = dict(PARAM_TYPES)
    expected_types[7] = 'string'
    expected_types.update({11: 'message', 17: 'closed_enum_int32'})
    # The fixed full-file hashes also pin every physical descriptor/instruction
    # range, including Init753690 mask3 and child Init6C2780 optional recursion.
    if not (proof['CONTROL_reference_sha256'] == CONTROL_SHA256
            and proof['claims']['normal_opcode'] == OPCODE
            and proof['claims']['identifier_type'] == 'uint64'
            and parent['label'] == 'CS_USE_ITEM_REQ'
            and parent_shape == [(1, True, '0x8d1', 1), (2, True, '0x416', 0)]
            and child['label'] == 'UseItemReqParam' and len(child['fields']) == 18
            and all(r['required'] is False for r in child['fields'])
            and types == expected_types
            and worker['schemas'] == proof['message_schemas']):
        raise ItemUseSourceError('ITEM_USE_SOURCE_CONTRACT_CHANGED')


def _enum17_one_source_ready():
    """Only raw enum1 is source-known; no enum name/domain or live-item claim.

    Conditional guard: existing branches keep exactly their run37 dependencies.
    run39's one rawkey144 UI producer is evidence for this number, never a rule
    that the current item/fixture has that key or came from that UI branch.
    """
    proof = None
    for relative, expected in ENUM17_SOURCE_PINS.items():
        try:
            with (ROOT / relative).open('rb') as stream:
                raw = stream.read(1048577)
        except OSError:
            raise ItemUseSourceError('ITEM_USE_ENUM17_SOURCE_UNAVAILABLE') from None
        if not 0 < len(raw) <= 1048576:
            raise ItemUseSourceError('ITEM_USE_ENUM17_SOURCE_BOUND')
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ItemUseSourceError('ITEM_USE_ENUM17_SOURCE_CHANGED')
        if relative.endswith('.json'):
            proof = json.loads(raw)
    fields = {r['field']: r for r in proof['nested_fields_from_accepted_metadata']}
    enum = fields[17]
    if not (proof['CONTROL_reference_sha256'] == CONTROL_SHA256
            and proof['selected_branch_table']['selected_key_values'] == [144]
            and proof['selected_branch_table']['selected_target'] == '0x4fd8fe'
            and enum['storage_type'] == 'closed_enum_int32'
            and enum['wire_type'] == 0 and enum['object_offset'] == '0x6c'
            and enum['presence_bit'] == 14
            and proof['claims']['params_initialization'] ==
                'inline original UseItemReqParam stack object atRBP-30; storage initialized then ownhasbits=0xC000; f1int32=1/bit15 and f17closed_enum_int32=1/bit14; not empty'):
        raise ItemUseSourceError('ITEM_USE_ENUM17_SOURCE_CONTRACT_CHANGED')


@dataclass(frozen=True, slots=True)
class ParamField:
    number: int
    kind: str
    value: int | bool | bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class UseItemParams:
    """Immutable wire observation; ordered f18 repetitions and bytes retained.

    f7 has source string storage. Only opaque bytes are exposed here, without a
    UTF8-validity or application string claim. f11 remains unsupported. f17
    exposes only source-known raw enum1, without its business/enum name.
    """
    raw: bytes = field(repr=False)
    fields: tuple[ParamField, ...] = field(repr=False)

    @property
    def present_fields(self) -> frozenset[int]:
        # f18 has no protobuf presence bit; membership means wire occurrence(s).
        return frozenset(item.number for item in self.fields)

    @property
    def has_f15_f16_presence(self) -> bool:
        """Shape only, not evidence that the original handler produced bytes."""
        return {15, 16} <= self.present_fields


@dataclass(frozen=True, slots=True)
class ItemUseRequest:
    identifier: int = field(repr=False)
    params: UseItemParams = field(repr=False)
    raw_payload: bytes = field(repr=False)


def _signed(value, bits):
    if value < (1 << (bits - 1)):
        return value
    if value < (1 << 64) - (1 << (bits - 1)):
        raise MalformedItemUse('ITEM_USE_SIGNED_WIDTH')
    return value - (1 << 64)


def _params(raw):
    fields, seen, repeated = [], set(), 0
    limits = pb.WireLimits(max_body=MAX_PARAMS, max_fields=16 + MAX_REPEATED,
                           max_field_bytes=MAX_STRING_BYTES)
    with pb.parse_message(raw, limits=limits) as parsed:
        for item in parsed.fields:
            n = item.number
            if n == 11:
                # Do not treat an arbitrary empty nested graph as initialized.
                raise UnsupportedItemUse('ITEM_USE_UNSUPPORTED_NESTED_OR_ENUM')
            if n not in PARAM_TYPES and n != 17:
                raise UnsupportedItemUse('ITEM_USE_UNSUPPORTED_PARAM_FIELD')
            if n == 18 and item.wire_type == 2:
                raise UnsupportedItemUse('ITEM_USE_UNSUPPORTED_PACKED_INT32')
            if item.wire_type != (2 if n == 7 else 0):
                raise MalformedItemUse('ITEM_USE_PARAM_WIRE_TYPE')
            if n != 18 and n in seen:
                raise MalformedItemUse('ITEM_USE_DUPLICATE_PARAM_FIELD')
            seen.add(n)
            kind = 'closed_enum_int32' if n == 17 else PARAM_TYPES[n]
            value = item.value
            if kind in ('int32', 'repeated_int32', 'closed_enum_int32'):
                value = _signed(value, 32)
            elif kind == 'int64':
                value = _signed(value, 64)
            elif kind == 'uint32' and value > 0xffffffff:
                raise MalformedItemUse('ITEM_USE_UINT32_WIDTH')
            elif kind == 'bool':
                if value not in (0, 1):
                    raise MalformedItemUse('ITEM_USE_BOOL_WIDTH')
                value = bool(value)
            elif kind == 'string_bytes':
                value = bytes(value)
            if n == 17:
                if value != 1:
                    raise UnsupportedItemUse('ITEM_USE_UNSUPPORTED_ENUM17_VALUE')
                _enum17_one_source_ready()
            if n == 18:
                repeated += 1
                if repeated > MAX_REPEATED:
                    raise MalformedItemUse('ITEM_USE_REPEATED_BOUND')
            fields.append(ParamField(n, kind, value))
    return UseItemParams(raw, tuple(fields))


def parse_payload(payload: bytes) -> ItemUseRequest:
    """Validate an existing body; preserve absent vs explicit 0 and exact bytes.

    Required parent f1/f2 occur exactly once, even for identifier0/empty child.
    Child15/16 are never filled. Noncanonical negative int32, unknown fields,
    duplicate singleton fields and unsupported graph/enum/packed branches fail
    closed. Bounded overlong varints accepted by the shared helper are retained.
    """
    source_ready()
    if type(payload) is not bytes:
        raise MalformedItemUse('ITEM_USE_IMMUTABLE_BYTES_REQUIRED')
    try:
        limits = pb.WireLimits(max_body=MAX_PAYLOAD, max_fields=2,
                               max_field_bytes=MAX_PARAMS)
        with pb.parse_message(payload, limits=limits) as parsed:
            if any(item.number not in (1, 2) for item in parsed.fields):
                raise UnsupportedItemUse('ITEM_USE_UNSUPPORTED_PARENT_FIELD')
            if len(parsed.occurrences(1)) != 1 or len(parsed.occurrences(2)) != 1:
                raise MalformedItemUse('ITEM_USE_REQUIRED_UNIQUE_FIELDS')
            identifier, = parsed.occurrences(1)
            params, = parsed.occurrences(2)
            if identifier.wire_type != 0 or params.wire_type != 2:
                raise MalformedItemUse('ITEM_USE_PARENT_WIRE_TYPE')
            return ItemUseRequest(identifier.value, _params(bytes(params.value)), payload)
    except pb.WireError:
        raise MalformedItemUse('MALFORMED_ITEM_USE_PAYLOAD') from None


def parse_frame(wire: bytes, *, cipher_pointer: str) -> ItemUseRequest:
    """One complete existing C2S plaintext frame, with explicit codec layout.

    Sequence/padding are codec structure only; no sequence agreement or live
    cipher state is inferred. Frame decoding is not transport-receipt evidence.
    """
    source_ready()
    if type(wire) is not bytes or len(wire) > MAX_FRAME:
        raise MalformedItemUse('ITEM_USE_FRAME_BOUND_OR_TYPE')
    if type(cipher_pointer) is not str or cipher_pointer not in ('null', 'present_disabled'):
        raise UnsupportedItemUse('ITEM_USE_EXPLICIT_CIPHER_LAYOUT_REQUIRED')
    try:
        decoder = codecs.ClientPlaintextDecoder(cipher_pointer=cipher_pointer,
                max_frame=MAX_FRAME, max_buffer=MAX_FRAME)
        frames = decoder.feed(wire)
        decoder.finish()
        if len(frames) != 1:
            raise MalformedItemUse('ITEM_USE_ONE_FRAME_REQUIRED')
        frame, = frames
        if frame.opcode != OPCODE:
            raise UnsupportedItemUse('ITEM_USE_OPCODE_REQUIRED')
        return parse_payload(frame.payload)
    except codecs.FrameError:
        raise MalformedItemUse('MALFORMED_ITEM_USE_FRAME') from None
