"""One source-bound passive event tuple in an existing retained query.

No callback, code/RTTI read, retain, lock, memory write or HP field inference.
The saved result is dated observation data, never current actor authority.
"""
from datetime import datetime, timezone
import hashlib
import json
import struct
import time
from tools.local_original_session import observe

BASE='work/local_server_rea_20261016/run103_i2_005_hp4ec8_subscriber/observation_recipe/'
SOURCE_PINS={BASE+'findings.md':'1053bee122ebca4c40a6e82442edc11c82c95a395710b1f28845e41a505ef02d',
             BASE+'source-evidence.json':'1172693eb75491cc90b1314ba39a65c96ff52d544bdd8d9d6304bb90693f1e96'}
MAX_NODES=16
MAX_BYTES=744
DTO_LIMIT=4096
EVENT_RVA=0x17ffb80
COLUMNS=['N','incoming_control','generation','C','V','T','V_RVA','T_RVA','next_N','next_control','status']

def source_ready():
    for relative,expected in SOURCE_PINS.items():
        raw=observe.ordinary(observe.ROOT/relative).read_bytes()
        observe.need(0<len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==expected,
                     'HP4EC8_SAVED_RECIPE_CHANGED')

def pointer(value):return type(value) is int and 0<value<=0x7fffffffffff and value%8==0
def packed(result):return json.dumps(result,separators=(',',':'),ensure_ascii=True).encode('ascii')

class _Stop(Exception):pass

class Observation:
    def __init__(self,reader):
        source_ready()
        self.reader=reader
        self.result=None
        self._query=None
        self.waiting=dict(status='WAITING_VALID_EXISTING_QUERY',bytes=0,attempted=False,
            query_bytes=None,remaining_bytes=None,required_bytes=MAX_BYTES,scope='LOCAL_PENDING_REQUEST')

    def collect(self,sampler,*,total_limit,query):
        if self.result is not None:return self.result
        # Reserve a full recipe in an already-needed query before any read.
        # This local selection is not a game/authority gate or a retry.
        remaining=max(0,total_limit-sampler.total)
        if remaining<MAX_BYTES:
            self.waiting.update(status='WAITING_FIT',query_bytes=sampler.total,remaining_bytes=remaining)
            return None
        self._query=query
        game=sampler.g
        base,size=game.get('base'),game.get('size')
        member=self.reader.member
        result=self.result=dict(status='UNKNOWN',captured_utc=datetime.now(timezone.utc).isoformat(),
            query_complete=False,query_completed_ns=None,owner_validation='PENDING_FINAL_CHECK',pid=member.pid,birth=member.identity.get('birth'),
            module=[base,size,getattr(self.reader.owner,'image_sha',None)],
            source=list(SOURCE_PINS.values()),event=None,head=None,epoch=None,columns=COLUMNS,nodes=[],
            bytes=0,header_repeat=None,atomic=False,owner='NOT_ESTABLISHED',scope='DATED_PASSIVE_SNAPSHOT')
        if not (type(base) is int and base>0 and type(size) is int and size>EVENT_RVA+0x7c):
            result['status']='MODULE_BOUNDS_UNKNOWN'
            return result
        event=base+EVENT_RVA;result['event']=event
        available=max(0,min(MAX_BYTES,total_limit-sampler.total))
        old_bytes,old_limit=sampler.bytes,sampler.read_limit
        sampler.bytes=0;sampler.read_limit=min(8192,available)
        spent=0
        def read(at,length):
            nonlocal spent
            if spent+length>available:
                result['status']='BUDGET_PARTIAL_UNKNOWN'
                raise _Stop()
            spent+=length;result['bytes']=spent
            try:
                raw=sampler.read(at,length,image=False)
            except Exception as error:
                result['status']='READ_FAILED_UNKNOWN';result['failure']=[at,length,observe.reason(error)]
                raise _Stop() from None
            if type(raw) is not bytes or len(raw)!=length:
                result['status']='SHORT_READ_UNKNOWN';result['failure']=[at,length]
                raise _Stop()
            return raw
        def ptr(at):return struct.unpack('<Q',read(at,8))[0]
        def rva(value):return value-base if type(value) is int and base<=value<base+size else None
        complete=False
        try:
            head=struct.unpack('<QQ',read(event+8,16));epoch=struct.unpack('<I',read(event+0x78,4))[0]
            result['head']=list(head);result['epoch']=epoch
            node,control=head;seen=set()
            if node==0:result['status']='EMPTY_AT_READ';complete=True
            while node:
                if len(result['nodes'])==MAX_NODES:
                    result['status']='TRUNCATED_OR_UNKNOWN';break
                if node in seen:
                    result['status']='CYCLE_UNKNOWN';break
                row=[node,control,None,None,None,None,None,None,None,None,'UNKNOWN']
                result['nodes'].append(row)
                if not pointer(node):row[-1]=result['status']='BAD_NODE_POINTER_UNKNOWN';break
                seen.add(node)
                generation=struct.unpack('<I',read(node+0x60,4))[0];row[2]=generation
                if 0<generation<=epoch:
                    callable=ptr(node+0x58);row[3]=callable
                    if callable==0:row[-1]=result['status']='NULLCALLABLE_UNKNOWN';break
                    if not pointer(callable):row[-1]=result['status']='BAD_CALLABLE_POINTER_UNKNOWN';break
                    vptr=ptr(callable);row[4]=vptr;row[6]=rva(vptr)
                    if not pointer(vptr):row[-1]=result['status']='BAD_VPTR_UNKNOWN';break
                    target=ptr(vptr+0x10);row[5]=target;row[7]=rva(target)
                    row[-1]='RVA_CANDIDATE' if row[6] is not None and row[7] is not None else 'RAW_UNRESOLVED'
                else:row[-1]='INELIGIBLE_AT_READ'
                node,control=struct.unpack('<QQ',read(node+0x10,16));row[8:10]=[node,control]
                if node==0:result['status']='PATH_READ';complete=True
            # Optional same-query repeat only when this path ended normally.
            if complete and available-spent>=20:
                after=[*struct.unpack('<QQ',read(event+8,16)),struct.unpack('<I',read(event+0x78,4))[0]]
                result['header_repeat']=after
                if after!=[*head,epoch]:result['status']='UNSTABLE'
        except _Stop:
            if result['nodes'] and result['nodes'][-1][-1]=='UNKNOWN':result['nodes'][-1][-1]=result['status']
        finally:
            sampler.bytes,sampler.read_limit=old_bytes,old_limit
        # Keep the entire partial prefix within the existing leaf DTO bound.
        while len(packed(result))>DTO_LIMIT-32 and result['nodes']:
            result['nodes'].pop();result['status']='OUTPUT_TRUNCATED_UNKNOWN'
        observe.need(len(packed(result))<=DTO_LIMIT,'HP4EC8_DTO_BOUND')
        return result

    def finish(self,query):
        if self.result is not None and self._query is query and self.result['query_completed_ns'] is None:
            self.result['query_complete']=True
            self.result['owner_validation']='EXISTING_BEFORE_AFTER_VALIDATED'
            self.result['query_completed_ns']=time.monotonic_ns()
            observe.need(len(packed(self.result))<=DTO_LIMIT,'HP4EC8_DTO_BOUND')

    def failed_final_check(self,query):
        if self.result is not None and self._query is query:
            self.result['path_status']=self.result['status']
            self.result['status']='FINAL_OWNER_CHECK_UNKNOWN'
            self.result['owner_validation']='FINAL_CHECK_FAILED_UNKNOWN'
