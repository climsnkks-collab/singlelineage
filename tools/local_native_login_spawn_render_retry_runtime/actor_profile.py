"""Pure explicit local Actor review DTO. No runtime, socket or frame emitter."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import hashlib, importlib.util, json, re
from collections.abc import Mapping

ROOT = Path(__file__).resolve().parents[2]
LEDGER = Path(__file__).with_name('actor-profile.json')
LEDGER_SHA = '6dce388c1a49e70a5b255f4072f1973cab6c833d6284d728e5eed5a0c75a0b18'
SELF_INFO_PATH = ROOT / 'tools/local_self_info_profile/model.py'
SELF_INFO_SHA = 'aeccbd4d3f0384b173c51c8e8f0bc8dfe33a3823761359a8ef3ad6dd5b2d580f'
SELF_INFO_SOURCE_PATH = ROOT / 'tools/local_self_info_profile/source.py'
SELF_INFO_SOURCE_SHA = '17a1aa41c8547477b2f5e538d3b94679aab27309c30f2fba539e5a1eb398c8a6'
POLICY = 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73'
REQUIRED = frozenset(range(1,25)) | {27,28}

class Refused(ValueError):
    """Constant reasons only; no payload, pointer or private source data."""

def need(ok,reason):
    if not ok: raise Refused(reason)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def ledger():
    raw=LEDGER.read_bytes();need(sha(raw)==LEDGER_SHA,'FIXED_ACTOR_LEDGER_CHANGED')
    row=json.loads(raw)
    need(row['schema']=='own-local-self-actor-explicit-profile-v1' and row['policy']==POLICY,
         'EXPLICIT_LOCAL_POLICY_REQUIRED')
    need({r['field'] for r in row['rows']}==REQUIRED and len(row['rows'])==26,
         'ALL_26_REQUIRED_EXPLICIT')
    for name,digest in row['source_pins'].items():
        path=ROOT/name
        need(path.is_file() and sha(path.read_bytes())==digest,'FIXED_ACTOR_SOURCE_CHANGED')
    return row

def _load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return m

def model():
    row=ledger()
    return _load(ROOT/'tools/local_world_protocol/model.py','_explicit_local_actor_world')

def candidate():
    """Return the explicit approved ledger; no absent fields get defaults."""
    row=ledger()
    return ({r['field']:r['value'] for r in row['rows']},
            {r['field']:r['provenance'] for r in row['rows']})

def require_sprite_key(text,key):
    need(type(key)is int and -0x80000000<=key<=0x7fffffff,'SPRITE_KEY_I32_REQUIRED')
    # Only a real # block's first decimal token is a catalog key.
    need(any(int(m.group(1))==key for m in re.finditer(r'^#(\d+)\s',text,re.MULTILINE)),
         'SPRITE_KEY_ABSENT')
    return True

def _source_schema(m,row):
    specs=m.schema(0x4e96)
    need({n for n,r in specs.items() if r['required']}==REQUIRED,'WORLD_REQUIRED_SET_CHANGED')
    for r in row['rows']:
        spec=specs[r['field']]
        need(spec['raw_offset']==r['raw_proto_offset'],'SOURCE_FIELD_OFFSET_CHANGED')
        need(m.CARD_TYPES[int(r['type_card'],16)]==spec['kind'],'SOURCE_FIELD_TYPE_CHANGED')
        if spec['kind']!='string':
            width=8 if spec['kind']=='uint64' else 1 if spec['kind']=='bool' else 4
            wrapper_offset=spec['raw_offset']+8
            need(0x60<=wrapper_offset and wrapper_offset+width<=0x133,
                 'FACTORY_ZERO_SPAN_DOES_NOT_COVER_SCALAR')

def _self_fields(self_info):
    fields=getattr(self_info,'fields',self_info)
    need(isinstance(fields,Mapping),'COMPLETE_SELF_INFO_REQUIRED')
    return fields

def validate_profile(actor,provenance,self_info):
    row=ledger();m=_load(ROOT/'tools/local_world_protocol/model.py','_explicit_local_actor_world')
    _source_schema(m,row)
    # Width/type/missing checks precede comparison with the explicit local policy.
    m.validate_input(0x4e96,actor)
    need(set(actor)==REQUIRED,'ONLY_REQUIRED_ACTOR_FIELDS_ALLOWED')
    need(isinstance(provenance,Mapping) and set(provenance)==REQUIRED,
         'EVERY_FIELD_PROVENANCE_REQUIRED')
    own=json.loads((ROOT/'work/standalone_boot/owned-local-profile/characters.json').read_text())
    need(own['schema']=='lc-owned-character-store-v1' and len(own['characters'])==1,
         'EXACT_OWNED_STORE_REQUIRED')
    character=own['characters'][0]
    need(character['uid']==1 and character['class']==0 and character['gender']==0,
         'EXACT_LOCAL_CHARACTER_POLICY_REQUIRED')
    need(actor[2]==character['uid'] and actor[9]==character['name'],'OWN_UID_AND_NAME_REQUIRED')
    need(actor[16]is True,'SELF_PLAYER_BRANCH_REQUIRED')
    need(0<=actor[5]<=7,'ACTOR5_UNSIGNED_DIRECTION_RANGE')
    require_sprite_key((ROOT/'work/local_resource_provider/assets/data/list.spr').read_text(encoding='utf-8-sig'),actor[3])
    for r in row['rows']:
        n=r['field']
        need(type(actor[n])is type(r['value']) and actor[n]==r['value'],
             'ACTOR_VALUE_OUTSIDE_EXPLICIT_LOCAL_BASELINE')
        need(provenance[n]==r['provenance'],'EXACT_PER_FIELD_SOURCE_PROVENANCE_REQUIRED')
    self_fields=_self_fields(self_info)
    m.validate_self_spawn(self_fields,actor,this_is_self=True)
    # The independently source-bound SelfInfo module additionally checks its local
    # starter/timestamp policy. No process observation or UID-consumption is inferred.
    integrated=False
    if SELF_INFO_SHA is not None:
        need(SELF_INFO_PATH.is_file() and sha(SELF_INFO_PATH.read_bytes())==SELF_INFO_SHA,
             'FIXED_SELF_INFO_PROFILE_CHANGED')
        need(SELF_INFO_SOURCE_PATH.is_file() and sha(SELF_INFO_SOURCE_PATH.read_bytes())==SELF_INFO_SOURCE_SHA,
             'FIXED_SELF_INFO_PROFILE_SOURCE_CHANGED')
        peer=_load(SELF_INFO_PATH,'_actor_explicit_self_info_profile')
        expected=peer.build_profile(utc_seconds=self_fields[15])
        peer.validate_profile(expected)
        need(dict(self_fields)==dict(expected.fields),'SELF_INFO_LOCAL_POLICY_MISMATCH')
        peer.validate_self_actor(self_fields,actor)
        integrated=True
    return {'schema':'own-local-self-actor-validation-v1','policy':POLICY,
            'required_field_count':26,'self_UID_equal_without_truncation':True,
            'Actor16_Player_branch_true':True,'SelfInfo_profile_policy_checked':integrated,
            'prior_SelfInfo_UID_consumption_required':True,
            'required_order':['MapNotify4E95','SelfInfo4E38','ActorNotify4E96'],
            'per_field_provenance_checked':True,
            'unknown_downstream_fields':row['unknown_downstream_fields'],
            'sprite_key_in_source_asset':True,'runtime_sprite_loader_complete':False,
            'class_or_gender_sprite_mapping_proven':False,
            'normal_server_values_claim':False,'world_success_claim':False,
            'gameplay_claim':False,'actual_server_emit':False}

def encode_for_review(actor,provenance,self_info):
    """Pure protobuf bytes with hidden repr; emits no frame and sends nothing."""
    receipt=validate_profile(actor,provenance,self_info)
    m=model()
    encoded=m.encode_with_provenance(0x4e96,actor,
                                    {n:p['category'] for n,p in provenance.items()})
    decoded=m.decode_payload(0x4e96,encoded.payload)
    need(decoded==actor,'ACTOR_ENCODE_DECODE_MISMATCH')
    return m.EncodedGameDTO(encoded.payload,{**encoded.receipt,**receipt,
          'encoded_length':len(encoded.payload),'encoded_sha256':sha(encoded.payload)})
