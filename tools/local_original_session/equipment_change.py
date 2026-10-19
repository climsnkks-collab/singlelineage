"""Accepted run74 SC097A schema and explicit local single-weapon position9.

Original Equipment UI key9 is named weapon independently of item template.
This is the declared local Athame policy position, not an official server
assignment rule or observed official Athame notification. No runtime evidence IO.
"""
from dataclasses import dataclass
import struct
from tools.local_entry_server import protobuf as pb

OPCODE=0x097A
MAX_FRAME=64
U64_MAX=(1<<64)-1
SCHEMA_STATUS='RUN74_WIRE_ACCEPTED_LOCAL_SINGLE_WEAPON_KEY9'
SOURCE_FINDINGS_SHA256='ef5582e7224d535b896d03113f829c70bc13b6dbdc089afcb145347a1e6eb1fd'
SOURCE_EVIDENCE_SHA256='04c34d95090e6d44ef36cd5fca33432de6608f7282bcaa11ad20b989942ce8f7'

@dataclass(frozen=True,slots=True)
class EquipmentChange:
    uid:int
    key:int
    equipped:bool

def _values(uid,key,equipped):
    if not (type(uid) is int and 0<=uid<=U64_MAX and type(key) is int and -(1<<31)<=key<1<<31 and type(equipped) is bool):
        raise ValueError('EQUIPMENT_CHANGE_EXACT_FIELDS_REQUIRED')
    return EquipmentChange(uid,key,equipped)

def _encode(value):
    payload=b''.join((pb.encode_varint(8)+pb.encode_varint(value.uid),
                      pb.encode_varint(16)+pb.encode_varint(value.key&U64_MAX),
                      pb.encode_varint(24)+pb.encode_varint(int(value.equipped))))
    return struct.pack('<HH',len(payload)+6,OPCODE)+payload+b'\0\0'

def build_change(*,uid,key,equipped):
    return _encode(_values(uid,key,equipped))

def validate_change(wire):
    if not(type(wire) is bytes and 6<=len(wire)<=MAX_FRAME and
           int.from_bytes(wire[:2],'little')==len(wire) and int.from_bytes(wire[2:4],'little')==OPCODE and wire[-2:]==b'\0\0'):
        raise ValueError('EQUIPMENT_CHANGE_FRAME_REQUIRED')
    with pb.parse_message(wire[4:-2],schema={1:0,2:0,3:0},limits=pb.WireLimits(max_body=MAX_FRAME,max_fields=3,max_field_bytes=0)) as message:
        if len(message.fields)!=3 or any(len(message.occurrences(n))!=1 for n in (1,2,3)):
            raise ValueError('EQUIPMENT_CHANGE_REQUIRED_UNIQUE_FIELDS')
        uid=message.occurrences(1)[0].value;key=message.occurrences(2)[0].value;flag=message.occurrences(3)[0].value
        if flag not in (0,1):raise ValueError('EQUIPMENT_CHANGE_BOOL_REQUIRED')
        if key>=1<<31:
            if key<0xffffffff80000000:raise ValueError('EQUIPMENT_CHANGE_SIGNEXTENDED_I32_REQUIRED')
            key-=1<<64
        value=_values(uid,key,bool(flag))
    if _encode(value)!=wire:raise ValueError('EQUIPMENT_CHANGE_CANONICAL_FRAME_REQUIRED')
    return value

# Accepted original UI naming: key9 -> category0/string.csv4194 weapon.
# Adopted only by the explicit local single-weapon Athame policy.
# These immutable provenance literals do not access work/ at runtime.
WEAPON_KEY_SOURCE_SHA256=(
    'cfc4d28045e675ae04abfdf81a8ab1b954ad4f034c694b9bd6d64de906b2fe3e',
    '94609a202541bfed3c7dc664bf422bd7d6877f2d3b140e5a38ce735e30353010',
    'a887c8ec943c1f2723fc5f5923c44717f0dee689407e8c5a275e2a104d466107',
    'be3cd9a825c05f69908de54934ad9dbbb24c35878cee7ac71632fddf91daf6b4',
)
WEAPON_KEY=9

def weapon_key_from_source():
    # No caller/config key and no fallback; only the adopted fixed position.
    if type(WEAPON_KEY) is not int or WEAPON_KEY!=9:
        raise ValueError('EQUIPMENT_WEAPON_KEY_SOURCE_NOT_ACCEPTED')
    return WEAPON_KEY
