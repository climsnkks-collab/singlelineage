"""Remembered places: official Classic limits, explicit LOCAL persistence model.

Official guide: https://lineageclassic.plaync.com/ko-kr/guidebook/view?title=기억
Basic capacity is 50; names permit 16 Korean / 32 English or numeric characters.
The native protocol field meanings are documented separately by the feature;
these storage keys are LOCAL backend names, not recovered protobuf field names.
"""
from __future__ import annotations

from copy import deepcopy
import struct

from tools.local_entry_server import protobuf as pb

BASE_CAPACITY = 50
ADD, UPDATE, DELETE, EXTEND, TELEPORT = 0x4E4A, 0x4E4B, 0x4E4C, 0x4F5F, 0x4E41
ADD_NOTI, STORE_NOTI, EXTEND_ACK = 0x4E4D, 0xC371, 0x4F60
CRYSTAL_TEMPLATE = 12458

# LOCAL backend policy copied from l1j-en-classic/db/l1jdb_m10.sql:
# mapids columns markable/teleportable/escapable (DDL lines1471..1473),
# rows19191..19293. Only maps used by the current local world plus map70's
# explicit no-escape reference are covered. These are not native Classic flags.
# Keep markability separate from escape: e.g. map2 cannot be remembered, but
# a saved destination may be reached FROM map2 despite random teleport=False.
_OVERWORLD = frozenset((0, 4))
_DUNGEON_ESCAPE = frozenset((1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13,
    19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36,
    43, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56, 72, 73,
    75, 76, 77, 78, 79, 80, 81, 82, 101, 102, 103, 104, 105))
_NO_ESCAPE = frozenset((37, 70))


def location_allowed(map_id, *, remembering=False):
    """Explicit LOCAL markable/escapable lookup; absent maps stay UNKNOWN.

    Siege-area runtime and house ownership are not present in this backend.
    This lookup does not imply that all points on overworld maps are markable.
    """
    need(type(map_id) is int and map_id in _OVERWORLD | _DUNGEON_ESCAPE | _NO_ESCAPE,
         'BOOKMARK_LOCATION_POLICY_UNKNOWN')
    return map_id in _OVERWORLD if remembering else map_id not in _NO_ESCAPE


def need(value, code):
    if not value:
        raise ValueError(code)


def valid_name(name):
    if type(name) is not str or not name or name != name.strip():
        return False
    # LOCAL mixed-string interpretation of official Korean16 / ASCII32 limits:
    # count ASCII as one unit and other characters as two display-width units.
    return (sum(1 if ord(ch) < 128 else 2 for ch in name) <= 32
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in name))


def empty():
    return dict(next_id=1, capacity=BASE_CAPACITY, entries=[])


def validate(value):
    need(type(value) is dict and set(value) == {'next_id', 'capacity', 'entries'},
         'BOOKMARK_STORE_SCHEMA')
    need(type(value['next_id']) is int and 1 <= value['next_id'] <= 1 << 31
         and type(value['capacity']) is int and value['capacity'] == BASE_CAPACITY
         and type(value['entries']) is list and len(value['entries']) <= value['capacity'],
         'BOOKMARK_STORE_VALUES')
    ids, names = set(), set()
    for row in value['entries']:
        need(type(row) is dict and set(row) == {'id', 'name', 'map_id', 'x', 'y'},
             'BOOKMARK_STORE_ROW')
        need(type(row['id']) is int and 0 < row['id'] < value['next_id']
             and valid_name(row['name']) and type(row['map_id']) is int
             and 0 <= row['map_id'] < 1 << 31
             and all(type(row[key]) is int and 0 <= row[key] < 1 << 16 for key in ('x', 'y')),
             'BOOKMARK_STORE_ROW_VALUES')
        need(row['id'] not in ids and row['name'] not in names, 'BOOKMARK_STORE_DUPLICATE')
        ids.add(row['id'])
        names.add(row['name'])
    return deepcopy(value)


def add(value, name, map_id, x, y):
    result = validate(value)
    need(valid_name(name), 'BOOKMARK_NAME_REQUIRED')
    need(len(result['entries']) < result['capacity'], 'BOOKMARK_CAPACITY_FULL')
    need(all(row['name'] != name for row in result['entries']), 'BOOKMARK_NAME_EXISTS')
    need(result['next_id'] < 1 << 31, 'BOOKMARK_ID_EXHAUSTED')
    row = dict(id=result['next_id'], name=name, map_id=map_id, x=x, y=y)
    result['entries'].append(row)
    result['next_id'] += 1
    return validate(result)


def rename(value, identifier, name):
    result = validate(value)
    need(valid_name(name), 'BOOKMARK_NAME_REQUIRED')
    need(all(row['id'] == identifier or row['name'] != name for row in result['entries']),
         'BOOKMARK_NAME_EXISTS')
    row = find(result, identifier)
    row['name'] = name
    return validate(result)


def delete(value, identifier, name):
    result = validate(value)
    row = find(result, identifier)
    need(row['name'] == name, 'BOOKMARK_CURRENT_NAME_REQUIRED')
    result['entries'].remove(row)
    return result


def find(value, identifier):
    need(type(identifier) is int and identifier > 0, 'BOOKMARK_ID_REQUIRED')
    row = next((row for row in value['entries'] if row['id'] == identifier), None)
    need(row is not None, 'BOOKMARK_CURRENT_ENTRY_REQUIRED')
    return row


def parse_request(opcode, payload):
    """Exact preserved compiled C2S shapes, no inferred field names.

    REQUEST_COVERAGE_MAP.json: ADD TD1742680, UPDATE1741E28,
    DELETE1741500, EXT1742908, TELEPORT1741D58. Field semantics are supplied by
    the feature's documented consumer policy, not the descriptor alone.
    """
    schemas = {ADD: {1: 2}, UPDATE: {1: 2, 2: 0}, DELETE: {1: 2, 2: 0},
               EXTEND: {}, TELEPORT: {1: 0, 2: 0, 3: 0}}
    schema = schemas[opcode]
    with pb.parse_message(payload, schema=schema, limits=pb.WireLimits(
            max_body=512, max_fields=3, max_field_bytes=128)) as parsed:
        need(len(parsed.fields) == len(schema) and
             all(len(parsed.occurrences(number)) == 1 for number in schema),
             'BOOKMARK_REQUEST_FIELDS')
        values = {field.number: bytes(field.value) if field.wire_type == 2 else field.value
                  for field in parsed.fields}
    if opcode in (ADD, UPDATE, DELETE):
        values[1] = values[1].decode('utf-8', 'strict')
        need(valid_name(values[1]), 'BOOKMARK_NAME_REQUIRED')
    if opcode == TELEPORT:
        need(values[1] <= 0x7fffffff or 0xffffffff80000000 <= values[1] <= 0xffffffffffffffff,
             'BOOKMARK_TELEPORT_INT32_REQUIRED')
        need(values[2] <= 0xffffffff and values[3] <= 0xffffffff,
             'BOOKMARK_TELEPORT_UINT32_REQUIRED')
    return values


def varint(number, value):
    return pb.encode_varint(number << 3) + pb.encode_varint(value & 0xffffffffffffffff)


def frame(opcode, body):
    return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'


def opaque_triple(row):
    """LOCAL field production order, not recovered original coordinate names.

    The client copies these three words unchanged to 0960 params f8/9/10.
    Only an exact saved-row match selects a destination; they never authorize
    client-chosen coordinates. The authoritative destination stays in storage.
    """
    return row['map_id'], row['x'], row['y']


def row_body(row):
    return (varint(1, row['id']) + pb.encode_bytes(2, row['name'].encode('utf-8'))
            + b''.join(varint(n, value) for n, value in zip((3, 4, 5), opaque_triple(row))))


def list_frame(value, *, store=False):
    value = validate(value)
    body = b'' if store else varint(1, value['capacity'])
    body += b''.join(pb.encode_bytes(1 if store else 2, row_body(row))
                     for row in value['entries'])
    return frame(STORE_NOTI if store else ADD_NOTI, body)


def parse_item_use(payload):
    with pb.parse_message(payload, schema={1: 0, 2: 2}, limits=pb.WireLimits(
            max_body=1024, max_fields=2, max_field_bytes=512)) as parsed:
        need(len(parsed.fields) == 2 and all(len(parsed.occurrences(n)) == 1 for n in (1, 2)),
             'BOOKMARK_ITEM_PARENT_FIELDS')
        identifier = parsed.occurrences(1)[0].value
        params = bytes(parsed.occurrences(2)[0].value)
    with pb.parse_message(params, schema={1: 0, 8: 0, 9: 0, 10: 0, 15: 0, 16: 0},
            limits=pb.WireLimits(max_body=512, max_fields=6, max_field_bytes=128)) as parsed:
        values = {field.number: field.value for field in parsed.fields}
        need(len(values) == len(parsed.fields), 'BOOKMARK_ITEM_DUPLICATE_FIELDS')
        if values == {1: 1, 15: 0, 16: 0}:
            return identifier, None
        need(set(values) in ({1, 8, 9, 10}, {1, 8, 9, 10, 15, 16})
             and values[1] == 1 and values.get(15, 0) == values.get(16, 0) == 0,
             'BOOKMARK_SELECTED_PARAMS_REQUIRED')
        return identifier, tuple(values[n] for n in (8, 9, 10))
