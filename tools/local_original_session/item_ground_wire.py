"""Strict saved SC4E96 candidate codec, not a live Item source capability.

Every required value is explicit. No field defaults, NPC recipe, Sprite14
compatibility assertion, ground UID mapping or registry admission is supplied.
The live Item recipe must additionally prove its original branch/resource
conditions. Optional44 is typed Item state, never a graphics/template pointer.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from types import MappingProxyType

from tools.local_entry_server import protobuf as pb


def _root(path):
    names = tuple(parent.name for parent in path.parents)
    if names[:2] == ('local_original_session', 'tools'):
        return path.parents[2]
    if names[:7] == ('ground', 'live', 'drop-pickup', 'item-equipment-product',
                     'implementation-1', 'local_original_session', 'work'):
        return path.parents[7]
    raise ImportError('GROUND_WIRE_MODULE_LAYOUT_REQUIRED')


ROOT = _root(Path(__file__).resolve())
CONTROL_SHA = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
WORLD = 'work/online_world_packet_source/world-notify-contract.json'
REQ94 = 'work/local_server_rea_20261016/run100_item1_ground_graphics_producer/'
REQ95 = 'work/local_server_rea_20261016/run101_item14_local_spawn_contract/'
SOURCE_PINS = MappingProxyType({
    WORLD: 'fa1c30e094b1e750e74d6a3379afcfcb334a4df30e4aa8a9791ed9a1f0df1f7b',
    REQ94 + 'source-evidence.json': 'bcb974890b406f65e12487b7e1a9d0634e4692b562d65c774898a455185c0aff',
    REQ94 + 'worker/source-evidence.json': '35655a1a6ee9d553c04eb15df6c2341b254846cef5ad24c99a9c98bd9336c917',
    REQ94 + 'main-review.json': '76ae836b64d8d522ce079fae9ffdeb5e139d77b2f36e1ee86ad07024840085bd',
    REQ95 + 'spawn_recipe/findings.md': '2e7a13aa87a00e4bd3d22b7d99b12f88a3644b90fe442bcb2cd5e46d4b1710ff',
    REQ95 + 'spawn_recipe/source-evidence.json': '4e67473fe6e2939a89a91301638d9b9276a729e87cdbda6c4d18a2cc1ffa8d84',
    REQ95 + 'spawn_recipe/reproducer.py': '7f06abe11368dfdf21fb508f8235305b9db1d06660648f7efe5a5636a8c21105',
    REQ95 + 'main-recipe-check.json': 'bdd5a0abfab5b80a2614599489588c3044f52aa7ae0f0bf2954acb0ede63c54e',
})
OPCODE, MAX_FRAME, MAX_BYTES, U64_MAX = 0x4E96, 2048, 256, (1 << 64) - 1
REQUIRED = frozenset(range(1, 25)) | {27, 28}
KINDS = MappingProxyType({
    1: 'u32', 2: 'u32', 3: 'i32', 4: 'i32', 5: 'i32', 6: 'i32',
    7: 'u64', 8: 'i32', 9: 'bytes', 10: 'bytes', 11: 'i32', 12: 'i32',
    13: 'i32', 14: 'bool', 15: 'bool', 16: 'bool', 17: 'bool', 18: 'bool',
    19: 'u64', 20: 'bytes', 21: 'bytes', 22: 'i32', 23: 'i32',
    24: 'i32', 27: 'i32', 28: 'i32', 39: 'i32', 44: 'nested44', 69: 'i32',
})
NESTED_KINDS = MappingProxyType({1: 'i64', 2: 'i32', 3: 'i32', 4: 'bool'})
CARDS = {'u32': '0x891', 'u64': '0x8d1', 'i32': '0x1091', 'i64': '0x10d1',
         'bool': '0x11', 'bytes': '0x815', 'nested44': '0x416'}


class GroundWireError(ValueError):
    """Fixed reason codes only."""


def _need(ok, reason):
    if not ok:
        raise GroundWireError(reason)


def _contract(world, index, worker, review):
    try:
        _need(world['schema'] == 'current-world-notify-proto-consumer-v1' and
              world['program_sha256'] == CONTROL_SHA and
              index['schema'] == 'req94-source-index/v1' and
              worker['schema'] == 'req94-Item-ground-graphics-producer-v1' and
              worker['CONTROL_sha256'] == CONTROL_SHA and review['passed'] is True,
              'GROUND_WIRE_SOURCE_IDENTITY_CHANGED')
        refs = {r['path']: r for r in index['artifacts']}
        _need(refs[REQ94 + 'worker/source-evidence.json']['sha256'] == SOURCE_PINS[REQ94 + 'worker/source-evidence.json'],
              'GROUND_WIRE_SOURCE_REFERENCE_CHANGED')
        table, = [row for row in world['tables'] if row['opcode'] == OPCODE]
        specs = {row['field_number']: row for row in table['fields']}
        _need(set(table['required_fields']) == REQUIRED and
              all(specs[n]['type_card'] == CARDS[kind] and
                  specs[n]['required_by_IsInitialized'] is (n in REQUIRED)
                  for n, kind in KINDS.items()), 'GROUND_WIRE_SCHEMA_CHANGED')
        nested = worker['nested44_schema']
        _need(nested['schema'] == '0x15f5538' and
              [(r['field'], r['storage_type'], r['wire_type'], r['required_by_IsInitialized']) for r in nested['fields']] ==
              [(1, 'int64', 0, True), (2, 'int32', 0, False), (3, 'int32', 0, False), (4, 'bool', 0, False)],
              'GROUND_WIRE_NESTED44_CHANGED')
        _need(worker['typed_flow'][0]['templateID'] is False and
              worker['typed_flow'][0]['destination'] == 'Actor+18 UID',
              'GROUND_WIRE_UID_DOMAIN_CHANGED')
    except (KeyError, TypeError, IndexError, ValueError) as error:
        if isinstance(error, GroundWireError):
            raise
        raise GroundWireError('GROUND_WIRE_SOURCE_CONTRACT_CHANGED') from None
    return True


def source_ready():
    """Static selected schema/consumer only; never a live-ground ready result."""
    docs = {}
    for name, digest in SOURCE_PINS.items():
        try:
            with (ROOT / name).open('rb') as stream:
                raw = stream.read(1_048_577)
        except OSError:
            raise GroundWireError('GROUND_WIRE_SOURCE_UNAVAILABLE') from None
        _need(0 < len(raw) <= 1_048_576 and hashlib.sha256(raw).hexdigest() == digest,
              'GROUND_WIRE_SOURCE_CHANGED')
        if name.endswith('.json'):
            try:
                docs[name] = json.loads(raw)
            except (ValueError, UnicodeError):
                raise GroundWireError('GROUND_WIRE_SOURCE_JSON_INVALID') from None
    _contract(docs[WORLD], docs[REQ94 + 'source-evidence.json'],
              docs[REQ94 + 'worker/source-evidence.json'], docs[REQ94 + 'main-review.json'])
    return _recipe_contract(docs[REQ95 + 'spawn_recipe/source-evidence.json'], docs[REQ95 + 'main-recipe-check.json'])


def _recipe_contract(recipe, check):
    """Accepted intermediate source facts; not Sprite14/current action proof."""
    try:
        _need(recipe['schema'] == 'REQ95-normal-local-Item-spawn-recipe-v1' and
              recipe['CONTROL_sha256'] == CONTROL_SHA and
              check['schema'] == 'req95-main-recipe-saved-check/v1' and check['passed'] is True and
              check['worker']['sha256'] == SOURCE_PINS[REQ95 + 'spawn_recipe/source-evidence.json'],
              'GROUND_RECIPE_SOURCE_IDENTITY_CHANGED')
        records = {row['id']: row['record'] for row in recipe['saved_records']}
        kinds = {row['field']: row['kind'] for row in records['M2']}
        _need(all(kinds[n] == 'bytes' for n in (9, 10, 20, 21)) and
              set(recipe['minimal_builder_conditions']['required_fields']) == REQUIRED,
              'GROUND_RECIPE_BYTES_OR_REQUIRED_CHANGED')
        normal = recipe['minimal_builder_conditions']['normal_Item']
        _need(normal['nonPlayer'] == 'required f16 bool explicitly present false' and
              normal['f21'] == 'required bytes present; empty is local subset choice, not Item admission gate',
              'GROUND_RECIPE_ITEM_BRANCH_CHANGED')
    except (KeyError, TypeError, IndexError):
        raise GroundWireError('GROUND_RECIPE_CONTRACT_CHANGED') from None
    return True


def _scalar(kind, value):
    if kind == 'bool':
        _need(type(value) is bool, 'GROUND_WIRE_BOOL_REQUIRED')
        return int(value)
    if kind == 'bytes':
        _need(type(value) is bytes and len(value) <= MAX_BYTES, 'GROUND_WIRE_IMMUTABLE_BYTES_BOUND')
        return value
    bits = 32 if kind.endswith('32') else 64
    low, high = (0, (1 << bits) - 1) if kind.startswith('u') else (-(1 << (bits - 1)), (1 << (bits - 1)) - 1)
    _need(type(value) is int and low <= value <= high, 'GROUND_WIRE_SCALAR_RANGE')
    return value & U64_MAX


def _pairs(fields, kinds, required):
    _need(type(fields) is tuple and all(type(pair) is tuple and len(pair) == 2 for pair in fields),
          'GROUND_WIRE_IMMUTABLE_FIELDS_REQUIRED')
    numbers = tuple(pair[0] for pair in fields)
    _need(all(type(n) is int and n in kinds for n in numbers) and
          tuple(sorted(set(numbers))) == numbers and required <= set(numbers),
          'GROUND_WIRE_EXPLICIT_UNIQUE_REQUIRED_FIELDS')
    for number, value in fields:
        if kinds[number] == 'nested44':
            _need(type(value) is Nested44, 'GROUND_WIRE_NESTED44_REQUIRED')
            _pairs(value.fields, NESTED_KINDS, {1})
        else:
            _scalar(kinds[number], value)


@dataclass(frozen=True, slots=True, repr=False)
class Nested44:
    fields: tuple

    def __post_init__(self):
        _pairs(self.fields, NESTED_KINDS, {1})


@dataclass(frozen=True, slots=True, repr=False)
class ActorNoticeCandidate:
    """Wire values only. Constructing this never claims an Item branch/owner."""
    fields: tuple

    def __post_init__(self):
        _pairs(self.fields, KINDS, REQUIRED)


LOCAL_POLICY = 'EXPLICIT_LOCAL_TEMPLATE1_ATHAME137_GROUND14_CANDIDATE'
PROFILE_FIELDS = REQUIRED - {1, 2, 3, 4, 5, 7, 16}
PROFILE_KINDS = MappingProxyType({n: KINDS[n] for n in PROFILE_FIELDS})


@dataclass(frozen=True, slots=True, repr=False)
class LocalItemProfile:
    """Explicit local parameters, not a current resource/action capability.

    All nineteen remaining required fields are supplied, including f6 and the
    four bytes fields. action is an explicit typed input, never defaulted to0.
    Runtime initialization/resource outcome remains the original path's result.
    """
    parameters: tuple
    action: int
    direction: int
    nonnegative_state: int

    def __post_init__(self):
        _pairs(self.parameters, PROFILE_KINDS, PROFILE_FIELDS)
        _scalar('i32', self.action)
        _need(type(self.direction) is int and 0 <= self.direction <= 7,
              'GROUND_LOCAL_DIRECTION_0_TO_7_REQUIRED')
        _need(type(self.nonnegative_state) is int and 0 <= self.nonnegative_state < 1 << 31,
              'GROUND_LOCAL_EXPLICIT_NONNEGATIVE_STATE_REQUIRED')


def local_candidate(profile, *, actor_uid, packed_position, quantity):
    """Root local14 recipe candidate only; no ready/provider/registry issuance.

    packed_position is an existing source-bound grid codec result, not new x/y
    interpretation. ActorUID is the chosen positive-u32 local B mapping. Actual
    same-owner/current-state/collision/conservation checks belong to registry.
    """
    source_ready()
    _need(type(profile) is LocalItemProfile, 'GROUND_LOCAL_EXACT_PROFILE_REQUIRED')
    _pairs(profile.parameters, PROFILE_KINDS, PROFILE_FIELDS)
    _need(type(actor_uid) is int and 0 < actor_uid < 1 << 32 and
          type(packed_position) is int and 0 <= packed_position < 1 << 32 and
          type(quantity) is int and 0 < quantity <= U64_MAX,
          'GROUND_LOCAL_POSITIVE_UID_Q_PACKED_POSITION_REQUIRED')
    # No unspecified required field is manufactured. These seven values have
    # their own explicit source/local-policy role; f39 is explicit optional.
    fields = profile.parameters + ((1, packed_position), (2, actor_uid), (3, 14),
        (4, profile.action), (5, profile.direction), (7, quantity), (16, False),
        (39, profile.nonnegative_state))
    return ActorNoticeCandidate(tuple(sorted(fields)))


def _payload(fields, kinds):
    result = []
    for number, value in fields:
        kind = kinds[number]
        if kind == 'nested44':
            result.append(pb.encode_bytes(number, _payload(value.fields, NESTED_KINDS)))
        elif kind == 'bytes':
            result.append(pb.encode_bytes(number, _scalar(kind, value)))
        else:
            result.append(pb.encode_varint(number << 3) + pb.encode_varint(_scalar(kind, value)))
    return b''.join(result)


def build_candidate(candidate):
    source_ready()
    _need(type(candidate) is ActorNoticeCandidate, 'GROUND_WIRE_CANDIDATE_REQUIRED')
    _pairs(candidate.fields, KINDS, REQUIRED)
    body = _payload(candidate.fields, KINDS)
    _need(len(body) + 6 <= MAX_FRAME, 'GROUND_WIRE_FRAME_BOUND')
    return struct.pack('<HH', len(body) + 6, OPCODE) + body + b'\0\0'


def _decode_scalar(kind, value):
    if kind == 'bytes':
        return bytes(value)
    if kind == 'bool':
        _need(value in (0, 1), 'GROUND_WIRE_CANONICAL_BOOL_REQUIRED')
        return bool(value)
    if kind in ('i32', 'i64'):
        bits = 32 if kind == 'i32' else 64
        if value >= 1 << (bits - 1):
            _need(value >= (1 << 64) - (1 << (bits - 1)), 'GROUND_WIRE_CANONICAL_SIGNED_REQUIRED')
            value -= 1 << 64
    _scalar(kind, value)
    return value


def _parse(body, kinds, required):
    schema = {n: 2 if kind in ('bytes', 'nested44') else 0 for n, kind in kinds.items()}
    try:
        with pb.parse_message(body, schema=schema,
              limits=pb.WireLimits(max_body=MAX_FRAME, max_fields=len(kinds), max_field_bytes=MAX_BYTES)) as parsed:
            _need(all(len(parsed.occurrences(n)) == 1 for n in required) and
                  len({f.number for f in parsed.fields}) == len(parsed.fields),
                  'GROUND_WIRE_REQUIRED_UNIQUE_FIELDS')
            fields = []
            for field in parsed.fields:
                kind = kinds[field.number]
                value = Nested44(_parse(bytes(field.value), NESTED_KINDS, {1})) if kind == 'nested44' else _decode_scalar(kind, field.value)
                fields.append((field.number, value))
        return tuple(fields)
    except pb.WireError:
        raise GroundWireError('GROUND_WIRE_MALFORMED_PAYLOAD') from None


def parse_candidate(wire):
    source_ready()
    _need(type(wire) is bytes and 6 <= len(wire) <= MAX_FRAME and
          int.from_bytes(wire[:2], 'little') == len(wire) and
          int.from_bytes(wire[2:4], 'little') == OPCODE, 'GROUND_WIRE_FRAME_REQUIRED')
    value = ActorNoticeCandidate(_parse(wire[4:-2], KINDS, REQUIRED))
    _need(struct.pack('<HH', len(wire), OPCODE) + _payload(value.fields, KINDS) + b'\0\0' == wire,
          'GROUND_WIRE_CANONICAL_FRAME_REQUIRED')
    return value
