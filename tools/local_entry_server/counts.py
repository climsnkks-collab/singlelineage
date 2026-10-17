"""Verified counts schema, fixed empty response, and bounded post-ACK observation."""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib, json, struct
from .handshake import InitialPlan, InitialSession, Stage, HandshakeError
from .protobuf import encode_uint32, encode_bool, encode_varint, encode_bytes, encode_message, parse_message, WireError

REQUEST=0x4f3d
ACK=0x4f3e
OUTBOUND=(0x4e20,0x4e35,ACK)
_APPROVAL=object()
HERE=Path(__file__).resolve().parent
CONTRACT_SHA='0bc5f9e55b22a71668816910ef140bb1b77891a3ecf31b508eefe28cc7eb9379'
PROOF_SHA='32cfd4c48b8f1acd6bcf66217962655810db072c9c6d3d2d4178382a249c8471'

@dataclass(frozen=True,slots=True)
class CountRow:
    field1:int
    field2:int
    field3:int
    field4:bool

def encode_row(row):
    if type(row) is not CountRow:raise WireError('counts_row_type')
    for value in (row.field2,row.field3):
        if type(value) is not int or not -(1<<31)<=value<(1<<31):raise WireError('counts_int32_range')
    return encode_message([encode_uint32(1,row.field1),
        encode_varint(2<<3)+encode_varint(row.field2&0xffffffffffffffff),
        encode_varint(3<<3)+encode_varint(row.field3&0xffffffffffffffff),encode_bool(4,row.field4)])

def encode_counts(rows=()):
    if type(rows) not in (tuple,list) or len(rows)>128:raise WireError('counts_row_limit')
    return encode_message([encode_bytes(1,encode_row(row)) for row in rows])

def counts_frame(rows=()):
    payload=encode_counts(rows)
    return struct.pack('<HH',len(payload)+6,ACK)+payload+b'\0\0'

def response_opcode_allowed(reply):
    if type(reply) is not bytes or not 6<=len(reply)<=65535:return False
    declared,opcode=struct.unpack_from('<HH',reply)
    return declared==len(reply) and opcode in OUTBOUND and reply[-2:]==b'\0\0' and (opcode!=ACK or reply==counts_frame())

def validate_counts_contract():
    raw=(HERE/'counts-contract.json').read_bytes()
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=CONTRACT_SHA:raise ValueError('counts_contract_binding')
    value=json.loads(raw)
    required={'schema':'lc-controlled-counts-response-v1','target_sha256':'9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af',
        'target_version':'26.09.29.2001','response_allowlist':list(OUTBOUND),
        'request':{'opcode':REQUEST,'fields':[],'required_fields':[],'ordering':'after_version_response','initializer':'0x778540 returns1'},
        'response':{'opcode':ACK,'outer_field1':'repeated_length_delimited','nested_fields':{'1':'uint32','2':'int32_sign_extended_varint','3':'int32_sign_extended_varint','4':'bool'},'required_nested_fields':[1,2,3,4],'default_rows':[],'initializer':'0x778870 -> 0x78d160 count0 initialized'},
        's2c_framing':'uint16_total_uint16_opcode_payload_ignored_zero_footer2',
        'post_ack':'bounded_c2s_opcode_length_metadata_only_no_reply','character_selection_proven':False,'authentication_proven':False,
        'source_evidence':['solo/spec/protocol.json downstream_count_stage','work/solo_character_entry_protocol/report.md','work/solo_character_entry_protocol/validation.json 75/75']}
    if value!=required:raise ValueError('counts_contract_changed')
    return value

@dataclass(frozen=True,slots=True)
class CountsPlan:
    base:InitialPlan
    _approval:object=field(default=None,repr=False)
    def __post_init__(self):
        if self._approval is not _APPROVAL or not self.base.version_response_allowed:raise ValueError('counts_plan_not_validated')
    @classmethod
    def from_contract(cls,base):
        validate_counts_contract()
        proof=(HERE/'counts-proof.json').read_bytes()
        if len(proof)>65536 or hashlib.sha256(proof).hexdigest()!=PROOF_SHA:raise ValueError('counts_proof_binding')
        evidence=json.loads(proof)
        if not (evidence['passed']==evidence['total']==75 and evidence['source_sha256']==base['source']['sha256'] and
                evidence['outer_schema']['fields']==[[16,0,0,0x426]] and
                evidence['nested_schema']['fields']==[[24,128,0,0x891],[28,129,0,0x1091],[32,130,0,0x1091],[36,131,0,0x11]]):
            raise ValueError('counts_schema_evidence_changed')
        downstream=base['downstream_count_stage']['CS_SERVER_CHAR_COUNTS_REQ']
        if downstream!={'opcode':REQUEST,'fields':[],'required_fields':[],'is_initialized':'0x778540 returns1'}:
            raise ValueError('counts_request_contract_changed')
        return cls(InitialPlan.from_contract(base),_APPROVAL)

class CountsSession(InitialSession):
    """Retains only session state; empty ACK never invents server/character rows."""
    def __init__(self,plan,session,log):
        if type(plan) is not CountsPlan:raise ValueError('counts_plan_required')
        super().__init__(plan.base,session,log)
        self.ack_prepared=False
    async def received(self,frame):
        if self.ack_prepared:
            if frame.opcode in (0x4e34,REQUEST):self._reject('duplicate_or_out_of_order_message')
            self.log.event('post_counts_c2s_observed',session=self.session.number,
                opcode=frame.opcode,wire_bytes=frame.wire_length,stage='post_counts_metadata_only')
            self._reject('unexpected_opcode')
        if self.stage==Stage.VERSION_REPLIED and frame.opcode==REQUEST:
            # Current request schema has no fields. No payload/value is copied.
            try:
                with parse_message(frame.payload,schema={}) as message:
                    self.log.event('protobuf_message',session=self.session.number,opcode=REQUEST,field_count=len(message.fields))
            except WireError:self._reject('malformed_counts_request')
            self.ack_prepared=True
            self._transition(Stage.COMPLETED,'counts_request_verified')
            self.log.event('session_transition',session=self.session.number,stage='counts_ack_prepared',reason='verified_empty_counts_response')
            return (counts_frame(),)
        return await super().received(frame)
