"""Owned local character creation, durable roster, and exact client wire fields.

This module has no listener or game process control. The caller must bind it to
an admitted owned-local connection. Creation field names and result code are
local policy; the fixed client schema and opcodes are checked separately.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
WIRE = ROOT / 'tools/local_character_wire_v2/wire.py'
WIRE_SHA = '466d3db45f1765f2cb3ce3e5a25917615ebd07326c428f29b66b80512d372cfc'
if hashlib.sha256(WIRE.read_bytes()).hexdigest() != WIRE_SHA:
    raise ValueError('FIXED_CHARACTER_WIRE_CHANGED')
spec = importlib.util.spec_from_file_location('_local_creation_character_wire', WIRE)
wire = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wire
spec.loader.exec_module(wire)
pb = wire.pb

CREATE_OPCODE = 0x4e24
CREATE_ACK_OPCODE = 0x4e25
MAX_CHARACTERS = 3
SCHEMA = 'lc-owned-character-store-v1'
_lock = threading.RLock()


class Refused(ValueError):
    """Constant errors; never contain a player name or packet bytes."""


def need(condition, code):
    if not condition:
        raise Refused(code)


def _i32(value):
    if value <= 0x7fffffff:
        return value
    if 0xffffffff80000000 <= value <= 0xffffffffffffffff:
        return value - (1 << 64)
    raise Refused('CREATE_NON_SIGNEXTENDED_INT32')


def _i64(value):
    return value if value < (1 << 63) else value - (1 << 64)


def _valid_name(name):
    if type(name) is not str:
        return False
    try:
        encoded = name.encode('utf-8', 'strict')
    except UnicodeError:
        return False
    return (1 <= len(encoded) <= 32 and name == name.strip() and
            not any(ord(ch) < 32 or ord(ch) == 127 for ch in name))


@dataclass(frozen=True, slots=True)
class Creation:
    name: str = field(repr=False)
    character_class: int
    gender: int
    attributes: tuple[int, int, int, int, int, int] = field(repr=False)


def decode_creation(payload):
    """Client's 4E24 generated schema: 1..9 required, 10..12 optional."""
    need(isinstance(payload, (bytes, bytearray, memoryview)), 'CREATE_BODY_REQUIRED')
    schema = {1: 2, **{n: 0 for n in range(2, 13)}}
    with pb.parse_message(payload, schema=schema,
                          limits=pb.WireLimits(max_body=512, max_fields=12,
                                               max_field_bytes=64)) as parsed:
        need({f.number for f in parsed.fields} >= set(range(1, 10)),
             'CREATE_REQUIRED_FIELDS')
        need(len({f.number for f in parsed.fields}) == len(parsed.fields),
             'CREATE_DUPLICATE_FIELD')
        fields = {f.number: f.value for f in parsed.fields}
        try:
            name = bytes(fields[1]).decode('utf-8', 'strict')
        except UnicodeError:
            raise Refused('CREATE_NAME_UTF8') from None
        need(_valid_name(name), 'CREATE_NAME_POLICY')
        values = {n: _i32(fields[n]) for n in range(2, 12) if n in fields}
        if 12 in fields:
            _i64(fields[12])
        need(values[2] in range(4) and values[3] in (0, 1),
             'CREATE_CLASS_OR_GENDER')
        stats = tuple(values[n] for n in range(4, 10))
        need(all(0 <= n <= 127 for n in stats), 'CREATE_ATTRIBUTE_RANGE')
        return Creation(name, values[2], values[3], stats)


def create_ack(field1):
    """Encode the known 4E25 one-int32 schema; caller chooses local result."""
    need(type(field1) is int and -(1 << 31) <= field1 < (1 << 31),
         'CREATE_ACK_INT32_REQUIRED')
    body = pb.encode_varint(1 << 3) + pb.encode_varint(field1 & 0xffffffffffffffff)
    return struct.pack('<HH', len(body) + 6, CREATE_ACK_OPCODE) + body + b'\0\0'


def _record_info(record):
    """Explicit starter values in the owned realm; no online value is copied."""
    name, character_class, gender = (record[k] for k in ('name', 'class', 'gender'))
    stats = record['attributes']
    values = {1: name, 2: '', 3: character_class, 4: 0, 5: gender,
              6: 0, 7: 20, 8: 10, 9: 10, 10: 1,
              11: stats[0], 12: stats[1], 13: stats[2],
              14: stats[3], 15: stats[4], 16: stats[5],
              17: 0, 18: 0, 19: 0, 20: 0, 21: 0}
    return wire.validate_fields('INFO', values)


class CharacterStore:
    """One-process owned-local JSON store with atomic replacement."""

    def __init__(self, path):
        self.path = Path(path)

    def _read(self):
        if not self.path.exists():
            return {'schema': SCHEMA, 'next_uid': 1, 'characters': []}
        raw = self.path.read_bytes()
        need(len(raw) <= 65536, 'CREATE_STORE_SIZE')
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise Refused('CREATE_STORE_JSON') from None
        need(type(data) is dict and set(data) == {'schema', 'next_uid', 'characters'}
             and data['schema'] == SCHEMA and type(data['next_uid']) is int
             and 1 <= data['next_uid'] <= 1 << 32 and type(data['characters']) is list
             and len(data['characters']) <= MAX_CHARACTERS, 'CREATE_STORE_SCHEMA')
        names, uids = set(), set()
        for row in data['characters']:
            need(type(row) is dict and set(row) == {'uid', 'name', 'class', 'gender', 'attributes'},
                 'CREATE_STORE_ROW')
            need(type(row['uid']) is int and 1 <= row['uid'] < data['next_uid']
                 and _valid_name(row['name']) and type(row['class']) is int
                 and type(row['gender']) is int and type(row['attributes']) is list
                 and len(row['attributes']) == 6, 'CREATE_STORE_ROW_TYPE')
            need(row['uid'] not in uids and row['name'].casefold() not in names,
                 'CREATE_STORE_DUPLICATE')
            need(row['class'] in range(4) and row['gender'] in (0, 1)
                 and all(type(n) is int and 0 <= n <= 127 for n in row['attributes']),
                 'CREATE_STORE_ROW_VALUE')
            wire.validate_fields('INFO', _record_info(row))
            names.add(row['name'].casefold())
            uids.add(row['uid'])
        return data

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        raw = (json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        need(len(raw) <= 65536, 'CREATE_STORE_SIZE')
        try:
            with tmp.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink()

    def roster(self):
        with _lock:
            data = self._read()
            rows = [_record_info(r) for r in data['characters']]
            return wire.build_local_roster(expected_count=len(rows),
                    display_slots=MAX_CHARACTERS, rows=rows, existing_rows=(),
                    mode='initial', allow_expected_growth=False)

    def create(self, creation):
        need(isinstance(creation, Creation), 'CREATE_REQUEST_REQUIRED')
        need(_valid_name(creation.name) and type(creation.character_class) is int
             and creation.character_class in range(4) and type(creation.gender) is int
             and creation.gender in (0, 1) and len(creation.attributes) == 6
             and all(type(n) is int and 0 <= n <= 127 for n in creation.attributes),
             'CREATE_LOCAL_VALUES')
        with _lock:
            data = self._read()
            need(len(data['characters']) < MAX_CHARACTERS, 'CREATE_CHARACTER_LIMIT')
            need(all(r['name'].casefold() != creation.name.casefold()
                     for r in data['characters']), 'CREATE_NAME_EXISTS')
            uid = data['next_uid']
            need(uid < 1 << 32, 'CREATE_UID_EXHAUSTED')
            row = {'uid': uid, 'name': creation.name,
                   'class': creation.character_class, 'gender': creation.gender,
                   'attributes': list(creation.attributes)}
            _record_info(row)
            data['characters'].append(row)
            data['next_uid'] += 1
            self._write(data)
            return uid, _record_info(row), self.roster()

    def select(self, name):
        with _lock:
            data = self._read()
            row = next((r for r in data['characters'] if r['name'] == name), None)
            need(row is not None, 'SELECT_UNKNOWN_LOCAL_CHARACTER')
            return row['uid'], _record_info(row)

    def snapshot(self):
        with _lock:
            data = self._read()
            rows = [_record_info(r) for r in data['characters']]
            roster = wire.build_local_roster(expected_count=len(rows),
                    display_slots=MAX_CHARACTERS, rows=rows, existing_rows=(),
                    mode='initial', allow_expected_growth=False)
            return roster, frozenset(row[1] for row in rows)
