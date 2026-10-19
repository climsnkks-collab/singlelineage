"""Passive selected local-character HP snapshot; not NPC HP or server authority."""
from __future__ import annotations
import hashlib
from contextlib import contextmanager
import json
import struct
from pathlib import Path

from tools.local_original_session import attack, edge, movement, observe

ROOT = observe.ROOT
BYTE_LIMIT = 16384
PAGE_NOACCESS = 1
MIN_INTERVAL_NS = 500_000_000
need = observe.need
SOURCE_PINS = {'work/source_hp_binding/source.json': 'a38fa51fca4c2b7f6ede8ac2855cc246a73e88234bdf3191710ac9d438094773', 'work/source_npc_binding/source-contract.json': 'fae01d10913218ff1ab6e85dab3d87c743e4c906e08fb88bf5e4c2de6c68094f', 'tools/source_npc_binding/npc_binding.cpp': '523f285a6747a6d7d326b1d0ecc2c6411cd48528ff015542fe0fc54b0c8d850d', 'work/local_server_rea_20261016/run5_move_update/nav_source.json': 'eed92e6eda3b30173210ad0e1590fd6ca5671679f333c21e7899d417534db85a'}


def _source():
    docs = {}
    for name, expected in SOURCE_PINS.items():
        raw = (ROOT/name).read_bytes()
        need(0 < len(raw) <= 2*1024*1024 and hashlib.sha256(raw).hexdigest() == expected,
             'STATUS_HP_SOURCE_CHANGED')
        if name.endswith('.json'): docs[name] = json.loads(raw)
    hp = docs['work/source_hp_binding/source.json']
    npc = docs['work/source_npc_binding/source-contract.json']
    nav = docs['work/local_server_rea_20261016/run5_move_update/nav_source.json']
    table, = nav['types']['CharacterDataSubsystem']['tables']
    need(table['vptr_rva'] == '0x1185340' and len(table['methods']) == 5,
         'STATUS_HP_CHARACTER_TABLE_SOURCE_REQUIRED')
    checks = [dict(rva=int(w['start'],16),length=int(w['end'],16)-int(w['start'],16),sha256=w['sha256'])
              for w in hp['windows']]
    window, = [w for w in npc['windows'] if w['name']=='HP_HUD_public_integer_pair']
    checks.append(dict(rva=int(window['start'],16),length=int(window['end'],16)-int(window['start'],16),sha256=window['sha256']))
    rows = hp['functions'][3]['instructions']
    for at in ('0x113d98','0x113ea0','0x113ec1'):
        i, = [i for i,r in enumerate(rows) if r['rva']==at]
        row=rows[i]
        checks.append(dict(rva=int(at,16),length=int(rows[i+1]['rva'],16)-int(at,16),sha256=row['sha256']))
    return table, checks


def decode(raw):
    """Exact accepted public-integer inverse, with wrapping32 and integrity."""
    need(type(raw) is bytes and len(raw)==12, 'STATUS_HP_TRIPLE_REQUIRED')
    a,b,c=struct.unpack('<III',raw)
    intermediate=a^b
    need(intermediate == (((~c)&0xffffffff)^((a+0x2f8b1064)&0xffffffff)),
         'STATUS_HP_TRIPLE_INTEGRITY')
    value=(intermediate-(((a*0x7f4a7c15)&0xffffffff)^0x2f8b1064))&0xffffffff
    return value if value<0x80000000 else value-0x100000000


class _Budget(edge._Budget):
    """Original strict comparisons; failed-span labels confer no authority."""
    def __init__(self,native,sampler):
        super().__init__(native,sampler)
        self._role=None;self._count_context=None;self._roles={}
        self._typed_read_changed=None
        self._first_read_failure=None
        self._cold_allowed=None
        self._cold_used=set()

    @contextmanager
    def cold_code(self,accepted):
        need(self._cold_allowed is None and type(accepted) is dict,'STATUS_HUD_COLD_SCOPE')
        self._cold_allowed=accepted
        try:yield
        finally:self._cold_allowed=None

    def _cold_read(self,error,key,image_base):
        if self._cold_allowed is None or self.retain or not key[2] or key not in self._cold_allowed:
            return None
        region=getattr(error,'region',None)
        if (observe.reason(error)!='region_not_readable' or type(region) is not dict or
            type(region.get('state')) is not int or region['state']!=0x1000 or
            type(region.get('type')) is not int or region['type']!=0x1000000 or
            type(region.get('protection')) is not int or region['protection']!=PAGE_NOACCESS or
            region.get('guard') is not False or region.get('length_fits') is not True or
            region.get('image_allocation_matches') is not True or
            type(region.get('requested_bytes')) is not int or region['requested_bytes']!=key[1] or
            image_base!=self.sampler.g['base']):
            return None
        raw=self._cold_allowed[key]
        need(type(raw) is bytes and len(raw)==key[1],'STATUS_HUD_COLD_BYTES')
        self._cold_used.add(key)
        return raw

    @contextmanager
    def field(self,role):
        previous=self._role;self._role=role
        try:yield
        finally:self._role=previous

    def _unchanged(self,unchanged,key,origin):
        if not unchanged:
            roles=self._roles.get(key,set())
            self._typed_read_changed=dict(
                typed_read_changed_field=(next(iter(roles)) if len(roles)==1
                                          else 'UNCLASSIFIED_TYPED_SPAN'),
                typed_read_changed_origin=origin,typed_read_changed_stage='typed_compare')
        need(unchanged,'EDGE_TYPED_READ_CHANGED')

    def read(self,at,size,image=False):
        need(type(size) is int and self.spent+size<=BYTE_LIMIT,'STATUS_HP_BYTE_BUDGET')
        need(type(at) is int and type(size) is int and 0 < size <= 4096 and
             0x10000 <= at <= 0x7fffffffffff - size,'EDGE_TYPED_READ_BOUND')
        need(self.spent+size<=edge.LIMIT,'EDGE_REQUEST_BYTE_BOUND')
        self.spent+=size
        key=(at,size,image)
        role=('SHARED_CONTROL_COUNT' if key==self._count_context else
              'IMAGE_TYPED_SPAN' if image else self._role or 'UNCLASSIFIED_TYPED_SPAN')
        image_base=self.sampler.g['base'] if image else None
        try:
            raw=self.native.read(at,size,image_base)
            need(type(raw) is bytes and len(raw)==size,'EDGE_PARTIAL_TYPED_READ')
        except Exception as error:
            cold=self._cold_read(error,key,image_base)
            if cold is not None:return cold
            if self._first_read_failure is None:
                fields={'state':int,'protection':int,'type':int,'guard':bool,'length_fits':bool,
                        'image_allocation_matches':bool,'requested_bytes':int}
                region=dict(status='UNAVAILABLE',**{name:None for name in fields},
                    base_address=None,allocation_base=None,allocation_protection=None,region_size=None,
                    geometry_status='UNAVAILABLE_IN_EXCEPTION')
                metadata=getattr(error,'region',None)
                if type(metadata) is dict:
                    available=0
                    for name,kind in fields.items():
                        value=metadata.get(name)
                        if name in metadata and ((type(value) is kind and (kind is bool or 0<=value<=0xffffffff))
                                or name=='image_allocation_matches' and value is None and not image):
                            region[name]=value;available+=1
                    if available:region['status']='EXCEPTION_METADATA' if available==len(fields) else 'PARTIAL_EXCEPTION_METADATA'
                native_error=getattr(error,'native_error',None)
                self._first_read_failure=dict(status='UNVERIFIED_FAILURE_VALUES',address=at,length=size,
                    image=image,image_base=image_base,field=role,reason=observe.reason(error),region=region,
                    native_error=native_error if type(native_error) is int and 0<=native_error<=0xffffffff else None)
            raise
        if self.retain:
            self._roles.setdefault(key,set()).add(role)
            expected=self._retained.get(key)
            if expected is None:
                self._retained[key]=raw
                self.records.append((at,raw,image))
            else:self._unchanged(raw==expected,key,'INITIAL_DUPLICATE')
        return raw

    @contextmanager
    def installed(self):
        sampler=self.sampler
        original={name:(name in sampler.__dict__,getattr(sampler,name)) for name in ('route','strong_pair')}
        def route():
            with self.field('ROOT_GI_ROUTE_TYPED_SPAN'):return original['route'][1]()
        def strong_pair(raw):
            previous=self._count_context
            self._count_context=((struct.unpack('<QQ',raw)[1]+8,4,False)
                if type(raw) is bytes and len(raw)==16 else None)
            try:return original['strong_pair'][1](raw)
            finally:self._count_context=previous
        sampler.route=route;sampler.strong_pair=strong_pair
        try:
            with super().installed():yield
        finally:
            for name,(present,value) in original.items():
                if present:setattr(sampler,name,value)
                else:sampler.__dict__.pop(name,None)

    def verify(self):
        self.retain=False
        try:
            for at,raw,image in self.records:
                self._unchanged(self.read(at,len(raw),image)==raw,
                    (at,len(raw),image),'FINAL_READBACK')
        finally:self.retain=True


class StatusHpObserver:
    def __init__(self,broker,reader):
        _source()
        self.targets=attack.AttackTargets(broker,reader)
        self.proof=edge.EdgeAdapter(reader)
        self._last_ns=None
        self._inflight=False

    def _current(self,writer):
        """Existing selected-world prefix; no NPC presence/HP/intent grant."""
        from tools.local_original_session.broker import LocalRealm,_TransportPolicy
        targets=self.targets;broker=targets.broker;reader=targets.reader
        native=targets._reader_binding();policy=broker.policy;owner=reader.owner;member=reader.member
        need(type(policy) is _TransportPolicy and owner is not None and member is not None
             and not reader.closed and not owner.closed and policy.owner is owner and owner.child is member
             and attack._handle_value(policy.handle)==attack._handle_value(owner.owner_handle)
             and attack._handle_value(policy.job)==attack._handle_value(owner.owner_job)
             and member.process==owner.owner_handle and member.job==owner.owner_job,
             'STATUS_HP_RETAINED_OWNER_REQUIRED')
        need(not broker._closing and not broker.failure.is_set() and policy.state=='OPEN',
             'STATUS_HP_CURRENT_BROKER_REQUIRED')
        rows=[r for values in broker._claims.values() for r in values if r['writer'] is writer]
        need(len(rows)==1,'STATUS_HP_UNIQUE_CURRENT_ROW_REQUIRED')
        row,=rows;admitted=policy._connection(writer)
        need(row['policy_row'] is admitted and admitted.writer is writer and admitted.stage==1
             and admitted.rx_boot==2 and admitted.tx_boot==3
             and not any((row['failed'],row['joined'],admitted.failed,admitted.eof,
                          admitted.task_joined,admitted.registry_removed)) and row['operation_lock'].locked(),
             'STATUS_HP_CURRENT_LOCKED_ROW_REQUIRED')
        realm=broker.realm
        need(type(realm) is LocalRealm,'STATUS_HP_REAL_REALM_REQUIRED')
        game=realm.registry.resolve(writer);service=realm.service(writer);position=service.snapshot()
        need(type(service) is movement.MovementService and type(position) is movement.Position
             and service._connection is writer and service._store is realm.positions,
             'STATUS_HP_CURRENT_SELECTED_SERVICE_REQUIRED')
        refs=(self,targets,broker,reader,self.proof,native,policy,owner,member,member.identity,
              broker.failure,row,row['peer'],row['operation_lock'],admitted,admitted.peer,
              realm,realm.registry,realm.store,realm.positions,game,game.selection,service,position)
        values=tuple(attack._handle_value(v) for v in (policy.handle,policy.job,owner.owner_handle,
            owner.owner_job,member.process,member.job,native.handle))
        values+=tuple(attack._typed_value(v) for v in (member.pid,
            *(member.identity.get(k) for k in ('pid','birth','image','parent_pid')),
            admitted.peer.port,admitted.peer.client_port,admitted.peer.accepted_ns,
            *row['peer'].keys(),*row['peer'].values()))
        return row,position,refs,values

    def _selection(self,writer):
        before=self._current(writer)
        self.targets.reader.validate()
        after=self._current(writer)
        need(attack._same_binding(after[2],after[3],before[2],before[3]),'STATUS_HP_SELECTION_CHANGED')
        return after

    async def sample(self,writer,*,now_ns):
        result=dict(status='UNKNOWN',reason='NOT_SAMPLED',uid=None,map_id=None,current_hp=None,max_hp=None,
            sample_monotonic_ns=now_ns,
            observation_scope='PASSIVE_READONLY_SNAPSHOT',value_scope='LOCAL_CHARACTER_CURRENT_MAX_HP',
            original_owning_getter_invoked=False,owning_lease_proven=False,source_contract_valid=False,
            source_owner_revalidated=False,stable_double_read=False,snapshot_atomic=False,
            typed_bytes_requested=0,typed_byte_limit=BYTE_LIMIT,max_samples_per_second=2,
            screen='UNKNOWN',server_authority=False)
        budget=None;entered=False
        try:
            need(not self._inflight,'STATUS_HP_INFLIGHT')
            need(type(now_ns) is int and 0<=now_ns<(1<<63),'STATUS_HP_CLOCK_REQUIRED')
            need(self._last_ns is None or now_ns-self._last_ns>=MIN_INTERVAL_NS,'STATUS_HP_CADENCE')
            self._last_ns=now_ns;self._inflight=True;entered=True
            initial=self._selection(writer)
            broker=self.targets.broker;reader=self.targets.reader;proof=self.proof
            for _ in range(2):
                need(await broker._movement_owner(writer,initial[0],initial[1]) is True,
                     'STATUS_HP_CURRENT_NATIVE_OWNER_REQUIRED')
                after=self._selection(writer)
                need(attack._same_binding(after[2],after[3],initial[2],initial[3]),'STATUS_HP_SELECTION_CHANGED')
            table,checks=_source()
            native,sampler=proof._binding()
            retained=(reader.owner,reader.member,reader.backend,reader.sampler)
            budget=_Budget(native,sampler)
            with budget.installed():
                proof._code(sampler,budget,checks+proof.public['Position']['source_checks'])
                pos=initial[1]
                reads,_,_,route,state,scene_raw,_=edge._world(native,sampler,proof.public,proof.world,
                    proof.position_source,pos.uid,pos.map_id,(pos.word0,pos.word1),require_current_start=False)
                objects=[reads.pair(pair)[0] for pair,vp in route[-2]
                         if vp==sampler.g['base']+int(table['vptr_rva'],16)]
                need(len(objects)==1,'STATUS_HP_UNIQUE_CHARACTER_DATA_REQUIRED')
                obj,=objects
                need(reads.pointer(obj)==sampler.g['base']+int(table['vptr_rva'],16),
                     'STATUS_HP_CHARACTER_DATA_TYPE_CHANGED')
                expected=struct.pack('<5Q',*(sampler.g['base']+int(v,16) for v in table['methods']))
                need(sampler.read(sampler.g['base']+int(table['vptr_rva'],16),40,image=True)==expected,
                     'STATUS_HP_CHARACTER_DATA_TABLE_CHANGED')
                with budget.field('CHARACTER_UID'):
                    need(struct.unpack('<Q',reads.read(obj+0x6d8,8))[0]==pos.uid,'STATUS_HP_CURRENT_UID_MISMATCH')
                with budget.field('HP_PUBLIC_INTEGER_PAIR'):
                    raw=reads.read(obj+0x750,24)
                current,maximum=decode(raw[:12]),decode(raw[12:])
                budget.verify()
                budget.retain=False
                try:
                    need(sampler.read(state+0x360,36)==scene_raw and sampler.route()==route,
                         'STATUS_HP_ROOT_OR_SCENE_CHANGED')
                finally:budget.retain=True
                proof._code(sampler,budget,checks+proof.public['Position']['source_checks'])
            need(self.proof is proof and self.targets.reader is reader and proof.reader is reader
                 and proof._binding()==(native,sampler)
                 and all(a is b for a,b in zip(retained,(reader.owner,reader.member,reader.backend,reader.sampler))),
                 'STATUS_HP_RETAINED_QUERY_CHANGED')
            after=self._selection(writer)
            need(attack._same_binding(after[2],after[3],initial[2],initial[3]),'STATUS_HP_SELECTION_CHANGED')
            need(_source()==(table,checks),'STATUS_HP_SOURCE_CHANGED')
            result.update(status='OBSERVED',reason=None,uid=pos.uid,map_id=pos.map_id,current_hp=current,max_hp=maximum,
                          source_contract_valid=True,source_owner_revalidated=True,stable_double_read=True)
        except Exception as error:
            result['reason']=observe.reason(error)
            if (result['reason']=='EDGE_TYPED_READ_CHANGED' and budget is not None
                    and budget._typed_read_changed is not None):
                result.update(budget._typed_read_changed)
        finally:
            if entered:self._inflight=False
            result['typed_bytes_requested']=0 if budget is None else budget.spent
        return result


    async def sample_hud_bar(self, writer, *, now_ns):
        return await _sample_hud_bar(self, writer, now_ns=now_ns)


SAMPLE_METHOD=StatusHpObserver.sample
HUD_SAMPLE_METHOD=StatusHpObserver.sample_hud_bar

# Accepted saved contracts only. No binary extraction, getter, retain or setter.
_HUD_BASE='work/local_server_rea_20261016/'
HUD_SOURCE_PINS={
    _HUD_BASE+'run92_hp_hud_connection/source-evidence.json':'7e6b84ae856778a7d205ddcb2accfdec76a1c6e37eabe6a32c9dc610ef09187c',
    _HUD_BASE+'run92_hp_hud_connection/worker/source-evidence.json':'4c15c12348c5bf60fa60e3764c9c272bfce956caba34812687d8523e2249bb46',
    _HUD_BASE+'run91_hp_hud_actual_selector/source-evidence.json':'211bacb028fd47d1d34220e052e00775f666cbf33797ff5c6c9e2736fd504219',
    _HUD_BASE+'run91_hp_hud_actual_selector/worker/source-evidence.json':'26979a66ec31cfd7e2e161caa2b3c3680d6c72335a648824b75e94dfccb5e801',
    _HUD_BASE+'run87_current_hp_hud_owner/findings.md':'ae2d207cac2652b300d7bdbaf725b12a3f7c7e37e237a4f3852a01ed2e7541ae',
    _HUD_BASE+'run87_current_hp_hud_owner/source-evidence.json':'9f701365a19a4dc27cb61688c8ca0f36e3f12a2c0e2596dd752b579ab9d3859a',
    _HUD_BASE+'run87_current_hp_hud_owner/main-review.json':'4809a9a8d3d35fa03174c95c119e0f4698cc5c7690115e6f05647e0ac335bc2f',
    _HUD_BASE+'run87_current_hp_hud_owner/worker/source-evidence.json':'fe59d23b88d550fbf13ffa6dbed9f9d21ab1525e1d0a099c5d2bdb82976d5f19',
    _HUD_BASE+'run85_hp_hud_signal_contract/worker/source-evidence.json':'8fa379ddf55f06361bb589b6fec652ce6eb2ee30afd5fb99b48600103bfdbe39',
    _HUD_BASE+'run86_hp_hud_value_storage/worker/source-evidence.json':'ab7c742516f6be3141bc7485d488985464c4b4038f13b743c550ff6c890a174a',
    _HUD_BASE+'run84_player_hp_death_contract/worker/source-evidence.json':'56923abdb9c65ccfbd4ea52a17d653aa3b9dfed335147d59a43809cb82cf34ce',
    _HUD_BASE+'run55_current_pc_receiver/source-input/A13B10-chained-file-decode.json':'4e769e9dbd91cb3e54774c7c88b05f922eb39b1d025163ca2eff7a935f8cdeb8',
    _HUD_BASE+'run55_current_pc_receiver/source-input/B3A0B0-file-decode.json':'85a844791a924242da2bb0c9204b9035155bf422633c741d63cddf967d536902',
    _HUD_BASE+'run55_current_pc_receiver/source-input/5B510-file-decode.json':'f0abd20e6799edcdfe12c07dc05b2cd148944d3273a7966f15c8e97b00882d69',
    'work/local_original_session/implementation-1/source-use-ui-child-role-split/owned_ui_binding.hpp':'676cf45a1523ceaa176dce73712a59487b67aa079095b6fb121c5c7ee5a521f8',
    'tools/local_original_session/native/command_bridge.hpp':'2d341306836f31d567cee31542b1ccb92efb966fa80914801b6ff7a6f2dede71'}


def _hud_source():
    docs={}
    for name, expected in HUD_SOURCE_PINS.items():
        raw=observe.ordinary(ROOT/name).read_bytes()
        need(0<len(raw)<=2*1024*1024 and hashlib.sha256(raw).hexdigest()==expected,'STATUS_HUD_SOURCE_CHANGED')
        if name.endswith('.json'):docs[name]=json.loads(raw)
    checks=[]
    def add(row):
        checks.append(dict(rva=int(row['rva'],16),length=row['length'],sha256=row['sha256']))
    owner=docs[_HUD_BASE+'run87_current_hp_hud_owner/worker/source-evidence.json']
    for row in owner['selected_source']:
        if row['id'] in ('S5','S6'):add(row)
    signal=docs[_HUD_BASE+'run85_hp_hud_signal_contract/worker/source-evidence.json']
    for function in signal['new_functions']:
        if int(function['rva'],16)==0x5ac90:
            for inst in function['instructions']:
                if int(inst['rva'],16)<0x5ad16:
                    checks.append(dict(rva=int(inst['rva'],16),length=inst['size'],sha256=inst['sha256']))
    for row in signal['selected_source']:
        if int(row['rva'],16) in (0x9ba0db,0x9ba392,0x9bb4f0,0x9bb554,0x45010,
                                  0x5ad16,0x5b0da,0x9bf4b0,0x9bcfb0,0x9bd13c):add(row)
        if int(row['rva'],16)==0x11a8f0:
            # Only the accepted unsigned generation/callable field consumer.
            for inst in row['instructions']:
                if 0x11a95c<=int(inst['rva'],16)<0x11a992:
                    checks.append(dict(rva=int(inst['rva'],16),length=inst['size'],sha256=inst['sha256']))
    storage=docs[_HUD_BASE+'run86_hp_hud_value_storage/worker/source-evidence.json']
    for row in storage['selected_source']:
        if row['id'] in ('S2','S3','S4'):add(row)
    hp=docs[_HUD_BASE+'run84_player_hp_death_contract/worker/source-evidence.json']
    for row in hp['reused_selected_source']:
        if int(row['start'],16)==0x9bdc98:
            rows=row['instructions']
            for index,inst in enumerate(rows):
                start=int(inst['rva'],16)
                end=int(rows[index+1]['rva'],16) if index+1<len(rows) else int(row['end_exclusive'],16)
                need(0<end-start<=15,'STATUS_HUD_SOURCE_INSTRUCTION_BOUND')
                checks.append(dict(rva=start,length=end-start,sha256=inst['sha256']))
    for name in ('A13B10-chained-file-decode.json','B3A0B0-file-decode.json','5B510-file-decode.json'):
        add(docs[_HUD_BASE+'run55_current_pc_receiver/source-input/'+name]['source'])
    selector=docs[_HUD_BASE+'run91_hp_hud_actual_selector/worker/source-evidence.json']
    row,=[row for row in selector['selected_source'] if row['id']=='S1']
    add(row) # Exact 29-byte 9BCC70 invoke10; same accepted 9BB560 producer.
    return checks


_COLD_SOURCE='work/local_server_rea_20261016/daybreak_page_noaccess_handoff/designated-01a14ed2/hud-code-span-235/cold-code-spans.json'
_COLD_SHA='650aa3f1f20720659911aa1c233c30dcaa1d46cc4becff87396ef84f5a9ede0e'
_PHYSICAL_SHA='8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
_CARRIER_SHA='c822838351d774a2022af434829a36dbd9bee030bf22182b834ca4e8659701a9'


def _cold_code_source(checks,reader,sampler):
    """Exact frozen decoded bytes only for protected CODE reads, never data."""
    image=ROOT/'work/standalone_boot/current-unmodified-clone/LC.guard.exe'
    need(reader.image==image and reader.owner is not None
         and reader.owner.image==image and reader.owner.child is reader.member
         and reader.owner.image_sha==_PHYSICAL_SHA
         and reader.backend.contract['original_program']==str(image)
         and Path(reader.member.identity.get('image',''))==image
         and reader.backend.expected==dict(pid=reader.member.pid,birth=reader.member.identity['birth'])
         and sampler.g['size']==reader.backend.contract['image_size'],
         'STATUS_HUD_COLD_IMAGE_IDENTITY')
    raw=observe.ordinary(ROOT/_COLD_SOURCE).read_bytes()
    need(0<len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==_COLD_SHA,
         'STATUS_HUD_COLD_SOURCE_CHANGED')
    document=json.loads(raw)
    need(type(document) is dict and set(document)=={'schema','physical_image_sha256',
         'derived_carrier_sha256','checks'} and document['schema']=='hud-cold-code-source-v1'
         and document['physical_image_sha256']==_PHYSICAL_SHA
         and document['derived_carrier_sha256']==_CARRIER_SHA
         and type(document['checks']) is list and len(document['checks'])==len(checks)==103,
         'STATUS_HUD_COLD_SOURCE_CONTRACT')
    accepted={}
    for actual,expected in zip(document['checks'],checks):
        need(type(actual) is dict and set(actual)=={'rva','length','sha256','bytes_hex'}
             and type(actual['rva']) is int and type(actual['length']) is int
             and type(actual['sha256']) is str and type(actual['bytes_hex']) is str
             and (actual['rva'],actual['length'],actual['sha256'])==
                 (expected['rva'],expected['length'],expected['sha256']),
             'STATUS_HUD_COLD_CHECK_CHANGED')
        span=bytes.fromhex(actual['bytes_hex'])
        need(len(span)==expected['length'] and hashlib.sha256(span).hexdigest()==expected['sha256'],
             'STATUS_HUD_COLD_BYTES_CHANGED')
        key=(sampler.g['base']+expected['rva'],expected['length'],True)
        need(key not in accepted or accepted[key]==span,'STATUS_HUD_COLD_DUPLICATE_CONFLICT')
        accepted[key]=span
    return accepted


def _hud_hash(raw):
    value=0xcbf29ce484222325
    for byte in raw:value=((value^byte)*0x100000001b3)&0xffffffffffffffff
    return value


class _HudRead:
    """Exact-key bounded lookup, never listener/child discovery or an owner."""
    def __init__(self,sampler):self.s,self.base=sampler,sampler.g['base']
    def read(self,at,size,image=False):return self.s.read(at,size,image=image)
    def ptr(self,at,nullable=False,*,context=None,callback_context=None):
        value=struct.unpack('<Q',self.read(at,8))[0]
        if callback_context is not None:callback_context.update(callback_address=value,callback_status='READ')
        if context is not None:
            context.update(actual_table_address=value,actual_table_status='READ',
                actual_table_rva=value-self.base if self.base<=value<self.base+self.s.g['size'] else None)
        need((nullable and value==0) or 0x10000<=value<=0x7fffffffffff and value%8==0,'STATUS_HUD_POINTER_BOUND')
        return value
    def failure(self,obj,role,index=None,*,table=None,offset=None,target=None):
        return dict(status='UNVERIFIED_FAILURE_VALUES',object_address=obj,role=role,vector_index=index,
            field='TYPE',expected_table_rva=table,slot_offset=offset,expected_target_rva=target,
            actual_table_address=None,actual_table_rva=None,actual_table_status='NOT_READ',
            actual_target_address=None,actual_target_rva=None,actual_target_status='NOT_READ')
    def typed(self,obj,expected,reason,context):
        try:
            table=self.ptr(obj,context=context)
            need(table==self.base+expected,reason)
            return table
        except Exception as error:
            if not hasattr(error,'hud_typed_failure'):error.hud_typed_failure=context
            raise
    def u32(self,at):return struct.unpack('<I',self.read(at,4))[0]
    def same_string(self,at,wanted):
        raw=self.read(at,32);length,capacity=struct.unpack_from('<QQ',raw,16)
        need(length<=capacity<=0x100000 and (capacity>=16 or capacity==15),'STATUS_HUD_STRING_HEADER')
        if length!=len(wanted):return False
        if capacity<=15:return raw[:length]==wanted
        return self.read(struct.unpack_from('<Q',raw)[0],length)==wanted
    def find(self,container,key,*,integer=False):
        sentinel,buckets=self.ptr(container+8),self.ptr(container+0x18)
        mask=struct.unpack('<Q',self.read(container+0x30,8))[0]
        need(mask<=0xfffff and mask&(mask+1)==0,'STATUS_HUD_MAP_MASK')
        first,last=struct.unpack('<QQ',self.read(buckets+(_hud_hash(key)&mask)*16,16))
        if last==sentinel:return None
        seen=set();at=last
        for _ in range(128): # Existing Find tool bound; not a game map-size rule.
            need(at not in seen and at!=sentinel and 0x10000<=at<=0x7fffffffffff and at%8==0,
                 'STATUS_HUD_MAP_CHAIN')
            seen.add(at)
            equal=(self.read(at+0x10,8)==key if integer else self.same_string(at+0x10,key))
            if equal:return at
            if at==first:return None
            at=self.ptr(at+8)
        raise ValueError('STATUS_HUD_MAP_QUERY_BOUND')
    def slot(self,obj,offset,target,diagnostic=None,*,context=None,role=None):
        if role is not None:context=self.failure(obj,role,offset=offset,target=target)
        if context is not None:context.update(field='ACTUAL_SLOT',slot_offset=offset,expected_target_rva=target)
        try:
            table=self.ptr(obj,context=context)
            if diagnostic is not None:
                diagnostic.update(field='SELECTOR_ACTUAL_SLOT_10',actual_table_address=table,
                    actual_table_rva=table-self.base if self.base<=table<self.base+self.s.g['size'] else None)
            need(self.base<=table and table+offset+8<=self.base+self.s.g['size'],'STATUS_HUD_TABLE_IMAGE_BOUND')
            actual=struct.unpack('<Q',self.read(table+offset,8,True))[0]
            if diagnostic is not None:
                diagnostic.update(actual_target_address=actual,
                    actual_target_rva=actual-self.base if self.base<=actual<self.base+self.s.g['size'] else None,
                    actual_target_status='READ')
            if context is not None:
                context.update(actual_target_address=actual,
                    actual_target_rva=actual-self.base if self.base<=actual<self.base+self.s.g['size'] else None,
                    actual_target_status='READ')
            need(actual==self.base+target,'STATUS_HUD_ACTUAL_SLOT_CHANGED')
            return table
        except Exception as error:
            if context is not None and not hasattr(error,'hud_typed_failure'):error.hud_typed_failure=context
            raise


def bar_expected(current,maximum,flip_x,flip_y):
    """cvtsi2ss/divss and optional mulss(-1), with no clamp or tolerance."""
    need(type(current) is type(maximum) is int and 0<current<=maximum<=0x7fffffff,
         'STATUS_HUD_EXPECTED_HP_PAIR')
    f=lambda value:struct.unpack('<f',struct.pack('<f',value))[0]
    x=f(f(current)/f(maximum))
    return (f(x*(-1.0 if flip_x else 1.0)),-1.0 if flip_y else 1.0)


def _hud_collect(sampler,route,character,budget):
    import math
    r=_HudRead(sampler);b=r.base
    manager=sampler.unique(route[-1],'UI')
    need(r.ptr(manager)==b+0x1182c50,'STATUS_HUD_CURRENT_MANAGER_TYPE')
    # Source-evaluate the exact known selector, without invoking it or claiming
    # a runtime LayoutVariant72 receipt. Registry key != mode != UIType18.
    selector=r.find(b+0x1668860,b'HudHpMpLayout')
    need(selector is not None,'STATUS_HUD_SELECTOR_ENTRY_REQUIRED')
    active=r.ptr(selector+0x68)
    selector_targets={0x121dfe0:0x9bf440,0x121dc80:0x9bcc70}
    diagnostic=dict(status='UNVERIFIED_FAILURE_VALUES',field='SELECTOR_CALLABLE_TYPE',
        entry_address=selector,active_field_offset=0x68,active_address=active,
        expected_selector_pairs=[dict(table_rva=table,target_rva=target)
                                 for table,target in selector_targets.items()],
        expected_table_rva=None,expected_target_rva=None,
        actual_table_address=None,actual_table_rva=None,
        actual_target_address=None,actual_target_rva=None,actual_target_status='NOT_READ')
    try:
        selector_table=r.ptr(active)
        diagnostic.update(actual_table_address=selector_table,
            actual_table_rva=selector_table-b if b<=selector_table<b+sampler.g['size'] else None)
        selector_rva=diagnostic['actual_table_rva']
        need(selector_rva in selector_targets,'STATUS_HUD_SELECTOR_TYPE')
        diagnostic.update(expected_table_rva=selector_rva,expected_target_rva=selector_targets[selector_rva])
        r.slot(active,0x10,selector_targets[selector_rva],diagnostic)
    except Exception as error:
        error.hud_selector_failure=diagnostic
        raise
    mode=r.u32(manager+0x328)
    ordinary=r.read(b+0x117e2a8,14,True);alternative=r.read(b+0x121dac8,21,True)
    need(ordinary==b'HudHpMpLayout\0' and alternative==b'Purple_HudHpMpLayout\0','STATUS_HUD_SELECTOR_LITERAL_CHANGED')
    variant=1 if mode==1 and alternative[0] else 0
    key=alternative[:-1] if variant else ordinary[:-1]
    # The accepted PC factory registration is ordinary only.
    need(variant==0,'STATUS_HUD_VARIANT_FACTORY_SOURCE_UNSUPPORTED')
    entry=r.find(manager+0x388,key)
    need(entry is not None,'STATUS_HUD_IMPL_ENTRY_REQUIRED')
    h,control=sampler.strong_pair(r.read(entry+0x30,16))
    need(r.ptr(control)==b+0x121e050 and r.ptr(control+0x10)==h
         and r.read(h+8,16)==struct.pack('<QQ',h,control),
         'STATUS_HUD_RESOURCE_PAIR_CHANGED')
    need(r.ptr(h)==b+0x121de28,'STATUS_HUD_CURRENT_H_TYPE')
    r.slot(h,8,0x9bcfb0) # Current initializer slot identity, never an init receipt.
    r.slot(h,0xb0,0x9bdb30)
    # Only the exact H-key vector. A weak node is never retained or promoted.
    connection_entry=r.find(b+0x17b0000,struct.pack('<Q',h),integer=True)
    need(connection_entry is not None,'STATUS_HUD_CONNECTION_ENTRY_REQUIRED')
    begin,end,capacity=struct.unpack('<QQQ',r.read(connection_entry+0x18,24))
    need(0x10000<=begin<=end<=capacity<=0x7fffffffffff and (end-begin)%8==0
         and (begin|end|capacity)%8==0 and 0<end-begin<=4096,'STATUS_HUD_CONNECTION_VECTOR')
    pointers=struct.unpack('<'+'Q'*((end-begin)//8),r.read(begin,end-begin))
    signal=character+0xd8;matches=0
    for index,connection in enumerate(pointers):
        connection_context=r.failure(connection,'HUD_CONNECTION',index)
        connection_context['expected_table_rvas']=[0x118b110,0x11812e0,0x1222f48]
        try:
            connection_table=r.ptr(connection,context=connection_context)
            need(connection_table in (b+0x118b110,b+0x11812e0,b+0x1222f48),'STATUS_HUD_CONNECTION_TYPE')
            s,node,ctrl=struct.unpack('<QQQ',r.read(connection+8,24))
            if s!=signal:continue
            connection_context.update(field='HP_SIGNAL_CONNECTION_TYPE',expected_table_rva=0x118b110,
                signal_address=s,expected_signal_address=signal)
            need(connection_table==b+0x118b110,'STATUS_HUD_CONNECTION_TYPE')
        except Exception as error:
            if not hasattr(error,'hud_typed_failure'):error.hud_typed_failure=connection_context
            raise
        node_context=r.failure(node,'HUD_HP_NODE',index)
        node_context.update(field='NODE_BOUND',connection_address=connection,control_address=ctrl,
            signal_address=s,strong=None,weak=None,count_status='NOT_READ',generation=None,snapshot=None,
            generation_status='NOT_READ',snapshot_status='NOT_READ',callback_address=None,callback_status='NOT_READ')
        try:
            need(0x10000<=node<=0x7fffffffffff and 0x10000<=ctrl<=0x7fffffffffff,
                 'STATUS_HUD_CONNECTION_NODE_BOUND')
            node_context['field']='WEAK_COUNTS'
            strong,weak=struct.unpack('<ii',r.read(ctrl+8,8))
            node_context.update(strong=strong,weak=weak,count_status='READ')
            need(strong>0 and weak>0,'STATUS_HUD_WEAK_NODE_NOT_CURRENT')
            node_context['field']='GENERATION'
            generation=r.u32(node+0x60)
            node_context.update(generation=generation,generation_status='READ')
            snapshot=r.u32(signal+0x78)
            node_context.update(snapshot=snapshot,snapshot_status='READ')
            need(0<generation<=snapshot,'STATUS_HUD_CONNECTION_GENERATION')
            node_context['field']='CALLBACK_POINTER'
            callback=r.ptr(node+0x58,callback_context=node_context)
        except Exception as error:
            if not hasattr(error,'hud_typed_failure'):error.hud_typed_failure=node_context
            raise
        callable_context=r.failure(callback,'HUD_CALLABLE',index,table=0x121d988)
        try:
            r.typed(callback,0x121d988,'STATUS_HUD_CALLABLE_TYPE',callable_context)
            r.slot(callback,0x10,0x9bb4f0,context=callable_context)
            callable_context.update(field='CAPTURE',expected_capture_address=h,expected_member_rva=0x9bb554,
                captured_address=None,member_address=None,adjustment=None,expected_adjustment=0)
            captured,member=struct.unpack('<QQ',r.read(callback+8,16))
            callable_context.update(captured_address=captured,member_address=member)
            adjustment=struct.unpack('<i',r.read(callback+0x18,4))[0]
            callable_context['adjustment']=adjustment
            need(captured==h and member==b+0x9bb554 and adjustment==0,'STATUS_HUD_CALLABLE_CAPTURE')
        except Exception as error:
            if not hasattr(error,'hud_typed_failure'):error.hud_typed_failure=callable_context
            raise
        matches+=1
    need(matches==1,'STATUS_HUD_SELECTED_CONNECTION_REQUIRED')
    text,bar=struct.unpack('<QQ',r.read(h+0x138,16))
    try:need(bar!=0,'STATUS_HUD_BAR_CHILD_REQUIRED')
    except Exception as error:
        if not hasattr(error,'hud_typed_failure'):
            context=r.failure(h,'HUD_BAR_CHILD')
            context.update(field='BAR_CHILD_POINTER',child_offset=0x140,child_address=bar,text_address=text)
            error.hud_typed_failure=context
        raise
    bar_table=r.slot(bar,0x68,0xbf8720,role='HUD_BAR')
    r.slot(bar,0x38,0xbf8660,role='HUD_BAR');r.slot(bar,0x48,0xbf86a0,role='HUD_BAR')
    need(r.read(b+0x126ee68,4,True)==struct.pack('<f',-1.0)
         and r.read(b+0x126eab4,4,True)==struct.pack('<f',1.0),'STATUS_HUD_FLOAT_LITERAL_CHANGED')
    with budget.field('HUD_BAR_SCALE'):x,y=struct.unpack('<ff',r.read(bar+0x30,8))
    with budget.field('HUD_BAR_FLIP'):flip_x,flip_y=r.read(bar+0x450,2)
    need(math.isfinite(x) and math.isfinite(y),'STATUS_HUD_BAR_NONFINITE')
    text_slots=dict(status='UNKNOWN',renderer_table_rva=None,setter_rva=None,getter_rva=None,
                    content='UNKNOWN',encoding='UNKNOWN',readmax='UNKNOWN')
    if text:
        text_context=r.failure(None,'HUD_TEXT_INTERFACE')
        text_context.update(field='INTERFACE_TABLE_IMAGE',text_address=text,slot_offsets=[8,0x10])
        try:
            renderer=r.ptr(text+0x740);interface=renderer+0x340
            text_context.update(renderer_address=renderer,object_address=interface)
            renderer_table=r.ptr(interface,context=text_context)
            need(b<=renderer_table and renderer_table+0x18<=b+sampler.g['size'],'STATUS_HUD_TEXT_INTERFACE_IMAGE_UNKNOWN')
            setter,getter=struct.unpack('<QQ',r.read(renderer_table+8,16,True))
            text_slots.update(renderer_table_rva=renderer_table-b,
                setter_rva=setter-b if b<=setter<b+sampler.g['size'] else None,
                getter_rva=getter-b if b<=getter<b+sampler.g['size'] else None)
        except Exception as error:
            if not hasattr(error,'hud_typed_failure'):error.hud_typed_failure=text_context
            reason=observe.reason(error)
            if reason in ('STATUS_HP_BYTE_BUDGET','EDGE_REQUEST_BYTE_BOUND','EDGE_TYPED_READ_CHANGED'):raise
            text_slots['reason']=reason
            text_slots['typed_failure']=error.hud_typed_failure
    return dict(status='OBSERVED',manager_type_rva=0x1182c50,mode=mode,ui_type=0x12,variant=variant,
        variant_scope='SOURCE_EVALUATED_CURRENT_MODE_LITERALS',selector_invoked=False,
        first_name='HudHpMpLayout',h_type_rva=0x121de28,h_b0_rva=0x9bdb30,
        selected_connection_matches=matches,bar_table_rva=bar_table-b,
        bar_68_rva=0xbf8720,bar_38_rva=0xbf8660,bar_48_rva=0xbf86a0,
        scale_x=x,scale_y=y,flip_x_u8=flip_x,flip_y_u8=flip_y,text_present=text!=0,text_slots=text_slots,
        text='UNKNOWN',callback='UNKNOWN',render='UNKNOWN',pixels='UNKNOWN',
        cpp_lease_proven=False,snapshot_atomic=False)


async def _sample_hud_bar(self,writer,*,now_ns):
    result=dict(status='UNKNOWN',reason='NOT_SAMPLED',uid=None,map_id=None,sample_monotonic_ns=now_ns,
        observation_scope='PASSIVE_READONLY_SNAPSHOT',value_scope='LOCAL_HP_HUD_BAR_MODEL_ONLY',
        source_contract_valid=False,source_owner_revalidated=False,stable_double_read=False,
        snapshot_atomic=False,owning_lease_proven=False,original_owning_getter_invoked=False,
        server_authority=False,screen='UNKNOWN',text='UNKNOWN',callback='UNKNOWN',pixels='UNKNOWN',
        bar=None,typed_bytes_requested=0,typed_byte_limit=BYTE_LIMIT,max_samples_per_second=2,
        code_validation_scope='UNKNOWN',live_code_bytes_verified=False,
        cold_code_anchor_count=0,first_cold_code_rva=None)
    budget=None;entered=False
    try:
        need(not self._inflight,'STATUS_HP_INFLIGHT')
        need(type(now_ns) is int and 0<=now_ns<(1<<63) and
             (self._last_ns is None or now_ns-self._last_ns>=MIN_INTERVAL_NS),'STATUS_HP_CADENCE')
        self._last_ns=now_ns;self._inflight=True;entered=True
        initial=self._selection(writer);broker=self.targets.broker;reader=self.targets.reader;proof=self.proof
        for _ in range(2):
            need(await broker._movement_owner(writer,initial[0],initial[1]) is True,'STATUS_HP_CURRENT_NATIVE_OWNER_REQUIRED')
            after=self._selection(writer)
            need(attack._same_binding(after[2],after[3],initial[2],initial[3]),'STATUS_HP_SELECTION_CHANGED')
        table,checks=_source();hud_checks=_hud_source()
        native,sampler=proof._binding();retained=(reader.owner,reader.member,reader.backend,reader.sampler)
        budget=_Budget(native,sampler)
        with budget.installed():
            code=checks+proof.public['Position']['source_checks']+hud_checks
            cold=_cold_code_source(code,reader,sampler)
            with budget.cold_code(cold):proof._code(sampler,budget,code)
            route=sampler.route();need(route[1] is True,'STATUS_HP_ROOT_OR_SCENE_CHANGED')
            state=sampler.unique(route[-1],'GameState');scene,scene_raw=sampler.scene(state)
            need(scene['current']['kind']=='Land' and scene['pending']['kind']=='none','STATUS_HP_ROOT_OR_SCENE_CHANGED')
            objects=[sampler.strong_pair(pair)[0] for pair,vp in route[-2]
                     if vp==sampler.g['base']+int(table['vptr_rva'],16)]
            need(len(objects)==1,'STATUS_HP_UNIQUE_CHARACTER_DATA_REQUIRED');character,=objects
            need(sampler.pointer(character)==sampler.g['base']+int(table['vptr_rva'],16),
                 'STATUS_HP_CHARACTER_DATA_TYPE_CHANGED')
            expected=struct.pack('<5Q',*(sampler.g['base']+int(v,16) for v in table['methods']))
            need(sampler.read(sampler.g['base']+int(table['vptr_rva'],16),40,image=True)==expected,
                 'STATUS_HP_CHARACTER_DATA_TABLE_CHANGED')
            with budget.field('CHARACTER_UID'):
                need(struct.unpack('<Q',sampler.read(character+0x6d8,8))[0]==initial[1].uid,'STATUS_HP_CURRENT_UID_MISMATCH')
            bar=_hud_collect(sampler,route,character,budget)
            budget.verify();budget.retain=False
            try:need(sampler.read(state+0x360,36)==scene_raw and sampler.route()==route,'STATUS_HP_ROOT_OR_SCENE_CHANGED')
            finally:budget.retain=True
            with budget.cold_code(cold):proof._code(sampler,budget,code)
        need(self.proof is proof and self.targets.reader is reader and proof.reader is reader
             and proof._binding()==(native,sampler)
             and all(a is b for a,b in zip(retained,(reader.owner,reader.member,reader.backend,reader.sampler))),
             'STATUS_HP_RETAINED_QUERY_CHANGED')
        after=self._selection(writer)
        need(attack._same_binding(after[2],after[3],initial[2],initial[3]),'STATUS_HP_SELECTION_CHANGED')
        need(_source()==(table,checks) and _hud_source()==hud_checks
             and _cold_code_source(code,reader,sampler)==cold,'STATUS_HUD_SOURCE_CHANGED')
        result.update(status='OBSERVED',reason=None,uid=initial[1].uid,map_id=initial[1].map_id,bar=bar,
            source_contract_valid=True,source_owner_revalidated=True,stable_double_read=True,
            code_validation_scope=('PINNED_COLD_CODE_WITH_CURRENT_IMAGE_VQ' if budget._cold_used
                                   else 'LIVE_CODE_HASHES'),
            live_code_bytes_verified=not budget._cold_used)
    except Exception as error:
        result['reason']=observe.reason(error)
        if hasattr(error,'hud_selector_failure'):result['selector_failure']=error.hud_selector_failure
        if hasattr(error,'hud_typed_failure'):result['typed_failure']=error.hud_typed_failure
        if budget is not None and budget._first_read_failure is not None:
            result['read_failure']=budget._first_read_failure
    finally:
        if entered:self._inflight=False
        if budget is not None and budget._cold_used:
            result['cold_code_anchor_count']=len(budget._cold_used)
            result['first_cold_code_rva']=min(at-budget.sampler.g['base'] for at,_,_ in budget._cold_used)
        result['typed_bytes_requested']=0 if budget is None else budget.spent
    return result
