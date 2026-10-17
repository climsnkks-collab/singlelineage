"""Opt-in canonical SC4E31 view over the existing bound-target frame builder.

This local policy supplies no writer/session authority, receipt, once-send,
deduplication, resend guarantee, combat result or HP mutation. The broker must
retain the original immutable bytes and check AttackSession.current and fresh
authority at the actual send boundary; a Feedback value is only a parsed view.

Original f1..5 are required; f13 is optional in the source schema, but explicit
bool is mandatory here. Local kind1 selects AttackAction subject to common
admission. Own attacker plus f13=False skips action creation after bookkeeping;
True can enter common admission and does not prove an echo safe. Raw f4 is full
int32: its positive gate admits later effect handling, not damage/HP/health.
Source f5 is int32; this existing builder's local subset is 0..8, with 8 reusing
current Transform+88. Coordinates never become a direction here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct

from tools.local_original_session import attack

ROOT = Path(__file__).resolve().parents[2]
OPCODE = 0x4e31
POLICY = 'EXPLICIT_LOCAL_KIND1_ATTACK_FEEDBACK'
U64_MAX = (1 << 64) - 1
MAX_FRAME = 45  # 6 tags + 1 kind + 20 UIDs + 10 raw + 1 dir + 1 bool + 6 framing.
MAX_SOURCE = 1 << 20
RUN24 = 'work/local_server_rea_20261016/run24_normal_attack/source-evidence.json'
RUN25 = 'work/local_server_rea_20261016/run25_attack_self_action/source-evidence.json'
RUN27 = 'work/local_server_rea_20261016/run27_attack_effect/source-evidence.json'
PROOF = 'work/source_npc_binding/source-contract.json'
CONTROL = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
SOURCE_PINS = {
    PROOF: 'fae01d10913218ff1ab6e85dab3d87c743e4c906e08fb88bf5e4c2de6c68094f',
    RUN24: 'ee7ae07d4c3928a02c8d91db0fa642f64106901c35ff90c654ff8c01b724a6aa',
    RUN24.replace('source-evidence.json', 'findings.md'):
        '6efc85b1a8da53dc4fdcf40c7ca88da2e098568b0e95ef8ba3341e11329d7ebc',
    RUN25: 'fd57e2fe4e5cde4899a1650c5c6d6fa57f6fced0c977f1988f93f3cbda69fa9a',
    RUN25.replace('source-evidence.json', 'findings.md'):
        'ddf8029b06fa570dccbaf04386439b92f5927e20435405d8c228fe633fd78b33',
    RUN25.replace('source-evidence.json', 'commit/source-evidence.json'):
        '2484f2052f413e56ca5d86102776d87afa5f731c0c0c3148ebe512834836e897',
    RUN25.replace('source-evidence.json', 'commit/findings.md'):
        '1ed2b53a45b40f4d39850842ab91679174e8174757067c7b98f15b90cbd0cc4c',
    RUN25.replace('source-evidence.json', 'start/source-evidence.json'):
        '908f3bc46b579a0c92581ee3fb898884768b867e58296b279bf58a7e3a1b567b',
    RUN25.replace('source-evidence.json', 'start/findings.md'):
        'd58f6d832ce983cc977cc0249a8697037613ceb57905e851c4b2d94b4161337a',
    RUN27: 'b1d5c7504192e21fabd99a8d9a2208cf2f996fed2a1d15fad00dfe53e225a9d4',
    RUN27.replace('source-evidence.json', 'findings.md'):
        'f2e99ab37f1ca0fb6fa5306b8e898a3de07d873e8a07feae232c8c7e18ed4c4f',
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _source_contract(documents):
    """Check all 14 source descriptors, although local wire contains only six."""
    normal, own, effect = (documents[p] for p in (RUN24, RUN25, RUN27))
    need(all(documents[p]['CONTROL_sha256'] == CONTROL for p in (
        RUN24, RUN25, RUN27, RUN25.replace('source-evidence.json', 'commit/source-evidence.json'),
        RUN25.replace('source-evidence.json', 'start/source-evidence.json'))),
        'ATTACK_FEEDBACK_SOURCE_CONTROL')
    schema, = [row for row in normal['schemas'] if row['schema'] == '0x15eee90']
    proof = documents[PROOF]['AttackNotify_schema']
    offsets = (32, 24, 40, 36, *range(48, 88, 4))
    bits = (129, 128, 131, 130, *range(132, 142))
    cards = (0x1091, 0x8d1, 0x8d1, *(0x1091 for _ in range(9)), 0x11, 0x1e91)
    need(schema['vptr'] == '0x11e4188' and schema['parse'] == '0x75e130'
         and schema['header'] == [16, 14, 19923064, 4294950912, 308, 65550]
         and proof['name'] == '.?AVSC_ATTACK_NOTI@LIN@@'
         and proof['schema_rva'] == schema['schema'] and proof['maximum'] == 14,
         'ATTACK_FEEDBACK_SOURCE_SCHEMA')
    expected = [[o, b, 0, c] for o, b, c in zip(offsets, bits, cards)]
    need(schema['fields'] == expected and len(schema['decoded_fields']) == 14
         and len(proof['fields']) == 14, 'ATTACK_FEEDBACK_SOURCE_FIELDS')
    for number, (offset, bit, _, card) in enumerate(expected, 1):
        need(schema['decoded_fields'][number - 1] == dict(field=number,
            object_offset=offset, presence_bit=bit, type_card=hex(card), required=number <= 5)
            and proof['fields'][number - 1] == dict(field=number, raw_offset=offset,
            presence_bit=bit, aux=0, type_card=hex(card)), 'ATTACK_FEEDBACK_SOURCE_FIELDS')
    spans = {row['label']: row for row in normal['source_spans']}
    need(any(row == dict(rva='0x294a30', instruction='mov edx, 0x4e31')
             for row in spans['S9']['instructions'])
         and spans['S10']['function_rva'] == '0x307450'
         and spans['S11']['function_rva'] == '0x5f990'
         and spans['S12']['function_rva'] == spans['S13']['function_rva'] == '0x4c440'
         and spans['S18']['function_rva'] == '0x9a0c0'
         and spans['S19']['function_rva'] == '0x917d0'
         and spans['S20']['function_rva'] == '0x907f0'
         and any(row['rva'] == '0x75e705' and row['instruction'] == 'test al, 0x1f'
                 for row in spans['S21']['instructions']), 'ATTACK_FEEDBACK_SOURCE_LINKAGE')
    need(own['commit']['dispatch'] == ['0xa29f0', '0xa11a0', '0xa17b0']
         and own['commit']['separate_attack_enqueue_direct_in_reviewed_boundary'] is False
         and own['start']['thunk'] == '0x91870' and own['start']['body'] == '0x8f9a0'
         and own['self_policy']['f13_true_echo_safety'] == 'UNKNOWN'
         and effect['first_direct_consumer_function']['start'] == '0x4d6590'
         and effect['unknown_boundary']['address'] == '4D6C09 call [record_object.vptr+8]',
         'ATTACK_FEEDBACK_SOURCE_LIMITS')


def source_ready():
    """Bounded ordinary frozen text only; never invoke a producer or binary."""
    documents = {}
    try:
        for relative, digest in SOURCE_PINS.items():
            path = (ROOT / relative).absolute()
            need(path.resolve(strict=True) == path and path.is_file(), 'ATTACK_FEEDBACK_SOURCE_PATH')
            for part in (path, *path.parents):
                info = part.lstat()
                need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                     'ATTACK_FEEDBACK_SOURCE_REPARSE')
            with path.open('rb') as stream:
                info = os.fstat(stream.fileno())
                need(info.st_nlink == 1 and 0 < info.st_size <= MAX_SOURCE, 'ATTACK_FEEDBACK_SOURCE_BOUND')
                raw = stream.read(MAX_SOURCE + 1)
            need(len(raw) <= MAX_SOURCE, 'ATTACK_FEEDBACK_SOURCE_BOUND')
            need(hashlib.sha256(raw).hexdigest() == digest, 'ATTACK_FEEDBACK_SOURCE_CHANGED')
            if relative.endswith('.json'):
                documents[relative] = json.loads(raw)
        _source_contract(documents)
    except (OSError, KeyError, TypeError, UnicodeError) as error:
        raise ValueError('ATTACK_FEEDBACK_SOURCE_UNAVAILABLE') from error


def _policy(policy):
    need(type(policy) is str and policy == POLICY, 'ATTACK_FEEDBACK_EXPLICIT_POLICY_REQUIRED')


@dataclass(frozen=True, slots=True)
class Feedback:
    """Wire values only; constructing/holding this view authorizes no send."""
    kind: int
    attacker_uid: int
    target_uid: int
    raw_effect: int
    direction: int
    self_action: bool


def _read_u64(body, offset):
    start, value = offset, 0
    for index in range(10):
        need(offset < len(body), 'ATTACK_FEEDBACK_TRUNCATED')
        byte = body[offset]
        offset += 1
        need(index < 9 or byte <= 1, 'ATTACK_FEEDBACK_VARINT_OVERFLOW')
        value |= (byte & 0x7f) << (index * 7)
        if byte < 0x80:
            need(index == 0 or byte != 0, 'ATTACK_FEEDBACK_NONMINIMAL_VARINT')
            return value, offset
    raise ValueError('ATTACK_FEEDBACK_VARINT_OVERFLOW')


def validate_frame(wire, *, policy=None):
    """Parse exact immutable canonical bytes; retain the input for actual send.

    Unknown/duplicate/out-of-order fields and alternate protobuf encodings are
    local refusals, not claims about the original parser's acceptance domain.
    UID range is the schema range; selection/target authorization is upstream.
    """
    _policy(policy)
    source_ready()
    need(type(wire) is bytes and 18 <= len(wire) <= MAX_FRAME, 'ATTACK_FEEDBACK_FRAME_BYTES_BOUND')
    length, opcode = struct.unpack('<HH', wire[:4])
    need(length == len(wire) and opcode == OPCODE and wire[-2:] == b'\0\0',
         'ATTACK_FEEDBACK_FRAME_HEADER_TAIL')
    body, offset, values = wire[4:-2], 0, []
    for number in (1, 2, 3, 4, 5, 13):
        need(offset < len(body) and body[offset] == number << 3, 'ATTACK_FEEDBACK_EXACT_FIELD_ORDER')
        value, offset = _read_u64(body, offset + 1)
        if number in (1, 4, 5):
            value = attack._signed(value)
        values.append(value)
    need(offset == len(body), 'ATTACK_FEEDBACK_EXTRA_FIELDS')
    kind, attacker_uid, target_uid, raw_effect, direction, self_action = values
    need(kind == 1 and 0 <= direction <= 8 and self_action in (0, 1),
         'ATTACK_FEEDBACK_LOCAL_KIND_DIRECTION_BOOL')
    return Feedback(kind, attacker_uid, target_uid, raw_effect, direction, bool(self_action))


def build_feedback(targets, bound, *, policy=None, raw_effect, direction, self_action):
    """Use the original builder and its actual bound UID/pre/post revalidation.

    All local policy inputs are required; no inferred effect, direction or echo.
    Existing action_frame remains compatible with optional f13=None, but this
    adapter requires the explicit bool and validates the returned original bytes.
    """
    _policy(policy)
    source_ready()
    need(type(targets) is attack.AttackTargets and type(bound) is attack.BoundTarget,
         'ATTACK_FEEDBACK_ACTUAL_BOUND_TARGET_REQUIRED')
    need(type(self_action) is bool, 'ATTACK_FEEDBACK_EXPLICIT_BOOL_REQUIRED')
    wire = attack.AttackTargets.action_frame(targets, bound, raw_effect=raw_effect,
                                             direction=direction, self_action=self_action)
    validate_frame(wire, policy=policy)
    return wire
