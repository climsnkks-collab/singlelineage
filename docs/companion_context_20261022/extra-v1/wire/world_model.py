"""Pure current-world protobuf payload validation. No sockets or frame crypto."""
from __future__ import annotations
import sys,json,hashlib,importlib.util
from pathlib import Path
from dataclasses import dataclass,field
from collections.abc import Mapping
sys.dont_write_bytecode=True
ROOT=Path(__file__).absolute().parents[2]
CONTRACT=ROOT/'work/online_world_packet_source/world-notify-contract.json'
CONTRACT_SHA='fa1c30e094b1e750e74d6a3379afcfcb334a4df30e4aa8a9791ed9a1f0df1f7b'
WIRE_SHA='c6d00262da031fb03a138c34b6a86dfc88f03e8ead2d6e71ae9bb21cd45de389'
CHARACTER_MODEL_SHA='84eea27f4719da20c524fd9f1c5ad00f303debf4b7aae59b846e7c58e509ae6d'
sha=lambda b:hashlib.sha256(b).hexdigest()

class ContractError(ValueError):
    """Constant codes only: never include DTO values or packet bodies."""

def _wire_module():
    p=ROOT/'tools/local_entry_server/protobuf.py'
    if sha(p.read_bytes())!=WIRE_SHA:raise ContractError('PURE_WIRE_SOURCE_CHANGED')
    s=importlib.util.spec_from_file_location('_world_pure_protobuf',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
wire=_wire_module()

def contract():
    raw=CONTRACT.read_bytes()
    if sha(raw)!=CONTRACT_SHA:raise ContractError('WORLD_SOURCE_CONTRACT_CHANGED')
    if sha((ROOT/'tools/local_character_protocol/model.py').read_bytes())!=CHARACTER_MODEL_SHA:raise ContractError('CHARACTER_SOURCE_CHANGED')
    return json.loads(raw)

# Compiled scalar representation, no product labels or enum semantics.
CARD_TYPES={0x891:'uint32',0x8d1:'uint64',0x1091:'int32',0x10d1:'int64',0x11:'bool',0x815:'string',
            0x416:'unsupported_message',0x426:'unsupported_repeated_message',0x1e91:'unsupported_enum',
            0x10a1:'unsupported_repeated_scalar',0x18d3:'unsupported_fixed_scalar'}
PROVENANCE=frozenset(('source_literal','actual_public_game_dto','local_game_configuration','synthetic_fixture'))
MAX_STRING_BYTES=4096

def schema(opcode):
    if type(opcode)is not int:raise ContractError('UNSUPPORTED_OPCODE')
    row=next((r for r in contract()['tables']if r['opcode']==opcode),None)
    if row is None:raise ContractError('UNSUPPORTED_OPCODE')
    specs={}
    for f in row['fields']:
        kind=CARD_TYPES.get(int(f['type_card'],16))
        if kind is None:raise ContractError('UNSUPPORTED_SOURCE_TYPE_CARD')
        specs[f['field_number']]={'kind':kind,'required':f['required_by_IsInitialized'],'raw_offset':f['raw_offset']}
    return specs

def _typed(kind,value):
    if kind.startswith('unsupported'):
        code='UNSUPPORTED_NESTED_SCHEMA' if 'message'in kind else 'UNSUPPORTED_ENUM_DOMAIN' if kind=='unsupported_enum' else 'UNSUPPORTED_SOURCE_SCALAR_LAYOUT'
        raise ContractError(code)
    if kind=='bool':
        if type(value)is not bool:raise ContractError('BOOLEAN_TYPE_REQUIRED')
        return int(value)
    if kind=='string':
        if type(value)is not str:raise ContractError('UTF8_STRING_REQUIRED')
        try:raw=value.encode('utf-8','strict')
        except UnicodeError:raise ContractError('INVALID_UTF8')from None
        if len(raw)>MAX_STRING_BYTES:raise ContractError('STRING_POLICY_LIMIT')
        return raw
    if type(value)is not int:raise ContractError('INTEGER_TYPE_REQUIRED')
    bits=32 if kind.endswith('32') else 64
    lower=0 if kind.startswith('u')else-(1<<(bits-1));upper=(1<<bits)-1 if kind.startswith('u')else(1<<(bits-1))-1
    if not lower<=value<=upper:raise ContractError('SCALAR_RANGE')
    return value&0xffffffffffffffff

def _fields(opcode,values):
    if not isinstance(values,Mapping):raise ContractError('FIELD_MAPPING_REQUIRED')
    specs=schema(opcode)
    for n in values:
        if type(n)is not int or n not in specs:raise ContractError('UNKNOWN_FIELD')
    if any(f['required']and n not in values for n,f in specs.items()):raise ContractError('MISSING_REQUIRED_FIELD')
    return specs

def validate_input(opcode,values):
    specs=_fields(opcode,values)
    for n,value in values.items():_typed(specs[n]['kind'],value)
    return True

def encode_payload(opcode,values):
    """Explicit values only; no defaults, guessed semantics, or ordering."""
    specs=_fields(opcode,values);encoded=[]
    for n in sorted(values):
        kind=specs[n]['kind'];v=_typed(kind,values[n])
        if kind=='string':encoded.append(wire.encode_bytes(n,v))
        else:encoded.append(wire.encode_varint(n<<3)+wire.encode_varint(v))
    return wire.encode_message(encoded)

def decode_payload(opcode,body):
    """Strict fixture policy: duplicate/unknown/noncanonical values refused."""
    specs=schema(opcode);allowed={n:2 if f['kind']=='string' or 'message'in f['kind'] else 0 for n,f in specs.items()}
    values={}
    with wire.parse_message(body,schema=allowed)as parsed:
        for f in parsed.fields:
            if f.number in values:raise ContractError('DUPLICATE_FIELD')
            kind=specs[f.number]['kind']
            if kind.startswith('unsupported'):_typed(kind,None)
            if kind=='string':
                try:value=bytes(f.value).decode('utf-8','strict')
                except UnicodeError:raise ContractError('INVALID_UTF8')from None
            elif kind=='bool':
                if f.value not in(0,1):raise ContractError('NONCANONICAL_BOOLEAN')
                value=bool(f.value)
            elif kind=='int32':
                if f.value<=0x7fffffff:value=f.value
                elif 0xffffffff80000000<=f.value<=0xffffffffffffffff:value=f.value-(1<<64)
                else:raise ContractError('NON_SIGNEXTENDED_INT32')
            elif kind=='int64':value=f.value if f.value<(1<<63)else f.value-(1<<64)
            else:value=f.value
            _typed(kind,value);values[f.number]=value
    _fields(opcode,values)
    # The preserved pure varint parser accepts redundant encodings; this fixture
    # contract requires canonical field order/encoding without changing game IO.
    if encode_payload(opcode,values)!=bytes(body):raise ContractError('NONCANONICAL_PAYLOAD')
    return values

@dataclass(frozen=True)
class EncodedGameDTO:
    payload:bytes=field(repr=False)
    receipt:dict=field(repr=False)
    def metadata(self):return dict(self.receipt)

def encode_with_provenance(opcode,values,provenance):
    _fields(opcode,values)
    if not isinstance(provenance,Mapping)or set(provenance)!=set(values):raise ContractError('EXPLICIT_PROVENANCE_REQUIRED')
    if any(type(v)is not str or v not in PROVENANCE for v in provenance.values()):raise ContractError('UNKNOWN_PROVENANCE_CATEGORY')
    payload=encode_payload(opcode,values)
    return EncodedGameDTO(payload,{'schema':'source-bound-world-payload-metadata-v1','opcode':opcode,
      'payload_length':len(payload),'payload_sha256':sha(payload),'fields':sorted(values),
      'provenance_categories':{n:provenance[n]for n in sorted(values)},'source_contract_sha256':CONTRACT_SHA,
      'actual_server_emit':False,'game_world_ready_claim':False})

def validate_self_spawn(self_info,actor_notify,*,this_is_self):
    """Optional public UID necessary-condition check, never world readiness."""
    if type(this_is_self)is not bool:raise ContractError('EXPLICIT_SELF_ROLE_REQUIRED')
    validate_input(0x4e38,self_info);validate_input(0x4e96,actor_notify)
    if this_is_self and self_info[1]!=actor_notify[2]:raise ContractError('SELF_UID_MISMATCH')
    return {'self_role_check_applied':this_is_self,'UID_widths':'SelfInfo1 u64; ActorNotify2 u32 zeroextended, nevertruncateSelfInfo',
      'resource_subtype_verified':False,'game_world_ready_claim':False}

def plan():
    return {'schema':'local-world-wire-plan-v1','opcodes':[r['opcode']for r in contract()['tables']],
      'status':'PURE_PAYLOAD_ONLY','nested44_51_present':'UNSUPPORTED_NESTED_SCHEMA; requiredness/type closure not yet frozen',
      'unknown_enum_present':'UNSUPPORTED_ENUM_DOMAIN','no_default_fields':True,'server_or_game_actions':0,
      'source_contract_sha256':CONTRACT_SHA,'NUMINFO_ACK':'unchanged tools/local_character_protocol model; not synthesized here'}
