"""Complete current NUM/INFO/ACK plaintext wire model only; no sockets/API."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib.util,hashlib,struct
from dataclasses import dataclass,field
ROOT=Path(__file__).absolute().parents[2]

def codec():
    p=ROOT/'tools/local_entry_server/protobuf.py'
    if hashlib.sha256(p.read_bytes()).hexdigest()!='c6d00262da031fb03a138c34b6a86dfc88f03e8ead2d6e71ae9bb21cd45de389':raise ValueError('fixed_wire_codec_pin')
    s=importlib.util.spec_from_file_location('_character_v2_codec',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m

pb=codec()
OPCODES={'NUM':0x4e21,'INFO':0x4e22,'ACK':0x4e29}
INFO_TYPES={1:'string',2:'string',3:'i32',4:'i64',**{n:'i32'for n in range(5,19)},19:'u32',20:'i32',21:'u64',22:'bool',23:'bool'}
TYPES={'NUM':{1:'i32',2:'i32'},'INFO':INFO_TYPES,'ACK':{2:'i32'}}
REQUIRED={'NUM':{1,2},'INFO':set(range(1,22)),'ACK':{2}}

def need(ok,why):
    if not ok:raise ValueError(why)

def row_i32_to_u32_bits(value):
    """Same four bytes reinterpretation; never reconstructs missing uint64 bits."""
    need(type(value)is int and -(1<<31)<=value<1<<31,'Row_i32_representation_required')
    return value&0xffffffff

def validate_fields(kind,values):
    need(kind in TYPES and type(values)is dict,'fixed_message_fields_required')
    need(all(type(n)is int and n in TYPES[kind]for n in values),'unknown_field')
    need(REQUIRED[kind]<=set(values),'required_field_missing')
    for n,value in values.items():
        typ=TYPES[kind][n]
        if typ=='string':
            need(type(value)is str,'UTF8_string_required')
            try:b=value.encode('utf-8')
            except UnicodeEncodeError:raise ValueError('UTF8_invalid')
            need(len(b)<=128,'game_UI_string_bound')
        elif typ=='bool':need(type(value)is bool,'bool_required')
        else:
            width=int(typ[1:]);lo=-(1<<(width-1))if typ[0]=='i'else 0;hi=(1<<(width-1))if typ[0]=='i'else 1<<width
            need(type(value)is int and lo<=value<hi,'typed_scalar_range')
    return dict(values)

def encode_payload(kind,values):
    values=validate_fields(kind,values);parts=[]
    for n in sorted(values):
        typ=TYPES[kind][n];value=values[n]
        if typ=='string':parts.append(pb.encode_bytes(n,value.encode('utf-8')))
        elif typ=='bool':parts.append(pb.encode_bool(n,value))
        else:parts.append(pb.encode_varint(n<<3)+pb.encode_varint(value&0xffffffffffffffff))
    return pb.encode_message(parts)

@dataclass(frozen=True,slots=True)
class Decoded:
    kind:str
    fields:dict=field(repr=False)
    def metadata(self):return {'kind':self.kind,'field_numbers':sorted(self.fields),'field_count':len(self.fields)}

def validate_payload(kind,body):
    need(kind in TYPES,'fixed_message_kind');schema={n:2 if t=='string'else 0 for n,t in TYPES[kind].items()};values={}
    with pb.parse_message(body,schema=schema,limits=pb.WireLimits(max_field_bytes=128))as msg:
        for row in msg.fields:
            typ=TYPES[kind][row.number];v=row.value
            if typ=='string':
                try:value=bytes(v).decode('utf-8')
                except UnicodeDecodeError:raise ValueError('UTF8_invalid')
            elif typ=='bool':need(v in(0,1),'canonical_bool_required');value=bool(v)
            elif typ[0]=='i':
                width=int(typ[1:])
                if v<(1<<(width-1)):value=v
                elif 0xffffffffffffffff-(1<<(width-1))+1<=v<=0xffffffffffffffff:value=v-(1<<64)
                else:raise ValueError('signed_scalar_not_signextended')
            else:
                need(v<1<<int(typ[1:]),'typed_scalar_range');value=v
            # Known scalar singular fields use protobuf last-value semantics.
            values[row.number]=value
    return Decoded(kind,validate_fields(kind,values))

def encode_frame(kind,values):
    body=encode_payload(kind,values);need(len(body)+6<=65535,'S2C_frame_bound')
    return struct.pack('<HH',len(body)+6,OPCODES[kind])+body+b'\0\0'

def validate_frame(raw):
    need(isinstance(raw,(bytes,bytearray,memoryview))and 6<=len(raw)<=65535,'S2C_frame_bound')
    size,op=struct.unpack_from('<HH',raw);need(size==len(raw),'S2C_frame_length')
    kind=next((k for k,n in OPCODES.items()if n==op),None);need(kind is not None,'unknown_character_opcode')
    # Current S2C consumer ignores final2; don't invent checksum semantics.
    return validate_payload(kind,memoryview(raw)[4:-2])

@dataclass(frozen=True,slots=True)
class LocalRoster:
    frames:tuple=field(repr=False)
    expected_count:int
    display_slots:int
    row_count:int
    transition:str
    def metadata(self):return {'realm':'owned-local','frames':len(self.frames),'expected_count':self.expected_count,'display_slots':self.display_slots,'row_count':self.row_count,'transition':self.transition,'actual_character_entry':False}

def build_local_roster(*,expected_count,display_slots,rows,existing_rows=(),mode,allow_expected_growth):
    """Explicit own policy, distinct from generic protobuf legality.

    Initial mode emits NUM then complete INFO rows, with unique nonempty game
    references and no accidental flag22 count changes. Update mode requires a
    real own existing reference for field23=True. No automatic ACK is emitted.
    """
    need(mode in('initial','update')and type(allow_expected_growth)is bool,'explicit_local_roster_policy')
    need(type(rows)in(list,tuple)and type(existing_rows)in(list,tuple)and len(rows)<=128 and len(existing_rows)<=128,'local_row_bound')
    validate_fields('NUM',{1:expected_count,2:display_slots})
    need(0<=expected_count<=128 and 0<=display_slots<=128,'local_count_policy')
    need(mode!='initial'or not existing_rows,'initial_existing_rows')
    state={}
    def reference(row):
        validate_fields('INFO',row);r=row[1];need(bool(r)and not any(ord(c)<32 for c in r),'local_character_reference_policy');return r
    for row in existing_rows:
        r=reference(row);need(r not in state,'local_duplicate_reference');state[r]=row
    wanted=expected_count;items=[];aux=0
    for row in rows:
        r=reference(row);upsert=row.get(23,False)
        if upsert:
            need(mode=='update'and r in state,'local_upsert_reference_missing');state[r]=row
        else:
            need(r not in state,'local_duplicate_reference');state[r]=row
            if len(state)!=wanted and row.get(22,False):
                need(allow_expected_growth,'local_unexpected_count_growth');wanted+=1;aux+=1
        items.append(encode_frame('INFO',row))
    need(len(state)==wanted,'local_count_completion_missing')
    if mode=='initial':items.insert(0,encode_frame('NUM',{1:expected_count,2:display_slots}))
    transition='normal_list_completion_event_requires_actual_Login3'if mode=='initial'else'normal_existing_reference_update_event'
    return LocalRoster(tuple(items),wanted,display_slots,len(state),transition)

def state5_request_ack(*,field2):
    """Generic known ACK scalar, not auth/game-entry success. Caller explicit."""
    return encode_frame('ACK',{2:field2})
