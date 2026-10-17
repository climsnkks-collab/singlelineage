"""Source-bound Restart wire subset; no selected-session or save policy.

The original request parser can preserve unknown fields. This local subset
accepts only the fresh producer's empty body. The original ACK bool is optional
and defaults false; local replies always carry an explicit bool. True triggers
original cleanup/state4, but proves neither receipt nor runtime transition.
Official acceptance/save/unselect ordering remains UNKNOWN. Callers own the
current selected owner, write/drain and subsequent lifecycle decisions.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct

from tools.local_entry_server import protobuf as pb
from tools.local_entry_server.codecs import ServerPlaintextDecoder

ROOT = Path(__file__).resolve().parents[2]
REQUEST_OPCODE = 0x4e33
ACK_OPCODE = 0x4e3b
POLICY = 'EXPLICIT_LOCAL_SELECTED_RESTART'
MAX_SOURCE = 1 << 20
MAX_FRAME = 8
LIMITS = pb.WireLimits(max_body=2, max_fields=1, max_field_bytes=2)
RUN34 = 'work/local_server_rea_20261016/run34_cs4e33/'
INDEX = RUN34 + 'source-evidence.json'
DETAIL = RUN34 + 'worker/source-evidence.json'
CONTROL = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
SOURCE_PINS = {
    RUN34 + 'findings.md': '331b8a7d9e4278021464a4552971e50497707348cd564b43382994dec55e1fbd',
    INDEX: 'e031a9f501ef809c41c9b76d3486d7fe7c689f71f28eabd85a21bce34cae1bb5',
    DETAIL: 'cb550c12dcfc127edf4c4b16a8b2152b00c3ab6b0a07e54470247277c52afe03',
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _source_contract(documents):
    index, detail = documents[INDEX], documents[DETAIL]
    need(index['CONTROL_sha256'] == detail['CONTROL_sha256'] == CONTROL,
         'RESTART_SOURCE_CONTROL')
    contract = index['source_contract']
    need(contract == detail['direct_contract']
         and contract['C2S_opcode'] == REQUEST_OPCODE
         and contract['request_declared_fields'] == contract['request_required_fields'] == 0
         and contract['fresh_producer_body_bytes'] == 0
         and contract['S2C_opcode'] == ACK_OPCODE and contract['S2C_type'] == 'SC_RESTART_ACK'
         and contract['response_fields'] == [dict(number=1, wire=0, type='bool',
                                                 presence='optional', default=False)]
         and contract['success_body_hex'] == '08 01', 'RESTART_SOURCE_SCHEMA')
    request, ack = detail['CS_RESTART_REQ_descriptor'], detail['SC_RESTART_ACK_descriptor']
    need(request['rva'] == '0x15eec00' and request['field_count'] == 0 and request['entries'] == []
         and ack['rva'] == '0x15ef3d8' and ack['field_count'] == 1
         and ack['entries'] == [[24, 128, 0, 17]], 'RESTART_SOURCE_DESCRIPTOR')
    anchors = {row['rva']: (row['mnemonic'], row['operand']) for row in detail['semantic_anchors']}
    need(anchors.get('0x13be64') == ('mov', 'edx, 0x4e33')
         and anchors.get('0x294ae4') == ('mov', 'edx, 0x4e3b')
         and anchors.get('0x760754') == ('mov', 'byte ptr [rbx], 8')
         and anchors.get('0x13dddf') == ('mov', 'edx, 4'), 'RESTART_SOURCE_LINKAGE')


def source_ready():
    """Read only bounded, pinned ordinary text; invoke no producer or binary."""
    documents = {}
    try:
        for relative, expected in SOURCE_PINS.items():
            path = (ROOT / relative).absolute()
            need(path.resolve(strict=True) == path and path.is_file(), 'RESTART_SOURCE_PATH')
            for part in (path, *path.parents):
                info = part.lstat()
                need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                     'RESTART_SOURCE_REPARSE')
            with path.open('rb') as stream:
                info = os.fstat(stream.fileno())
                need(info.st_nlink == 1 and 0 < info.st_size <= MAX_SOURCE, 'RESTART_SOURCE_BOUND')
                raw = stream.read(MAX_SOURCE + 1)
            need(len(raw) <= MAX_SOURCE, 'RESTART_SOURCE_BOUND')
            need(hashlib.sha256(raw).hexdigest() == expected, 'RESTART_SOURCE_CHANGED')
            if relative.endswith('.json'):
                documents[relative] = json.loads(raw)
        _source_contract(documents)
    except (OSError, KeyError, TypeError, UnicodeError) as error:
        raise ValueError('RESTART_SOURCE_UNAVAILABLE') from error


def _policy(policy):
    need(type(policy) is str and policy == POLICY, 'RESTART_EXPLICIT_POLICY_REQUIRED')


def parse_request(payload):
    """Validate decoder payload only; it carries no UID, position or success."""
    need(type(payload) is bytes and payload == b'', 'RESTART_EMPTY_SOURCE_BODY_REQUIRED')


def validate_ack(wire, *, policy=None):
    """Return explicit success bool from the exact local canonical frame."""
    _policy(policy)
    source_ready()
    need(type(wire) is bytes and len(wire) == MAX_FRAME, 'RESTART_ACK_FRAME_BYTES_BOUND')
    decoder = ServerPlaintextDecoder(max_frame=MAX_FRAME, max_buffer=MAX_FRAME)
    frames = decoder.feed(wire)
    decoder.finish()
    need(len(frames) == 1 and frames[0].opcode == ACK_OPCODE and wire[-2:] == b'\0\0',
         'RESTART_ACK_FRAME_HEADER_TAIL')
    with pb.parse_message(frames[0].payload, schema={1: 0}, limits=LIMITS) as message:
        need(len(message.fields) == 1 and message.fields[0].value in (0, 1),
             'RESTART_ACK_EXPLICIT_BOOL_REQUIRED')
        success = bool(message.fields[0].value)
    need(frames[0].payload == pb.encode_bool(1, success), 'RESTART_ACK_CANONICAL_REQUIRED')
    return success


def build_ack(*, success, policy=None):
    """Build bytes only; explicit local policy does not authorize a send."""
    _policy(policy)
    need(type(success) is bool, 'RESTART_ACK_EXPLICIT_BOOL_REQUIRED')
    source_ready()
    body = pb.encode_bool(1, success)
    return struct.pack('<HH', len(body) + 6, ACK_OPCODE) + body + b'\0\0'
