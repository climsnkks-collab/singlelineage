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
    def __init__(self,reader,*,stage="first-land"):
        source_ready()
        observe.need(stage in ('first-land','npc-hp-feedback-drained'),'HP4EC8_STAGE_REQUIRED')
        self.reader=reader
        self.stage=stage
        self.trigger=None
        self.result=None
        self._query=None
        self.waiting=dict(status='WAITING_VALID_EXISTING_QUERY',bytes=0,attempted=False,
            query_bytes=None,remaining_bytes=None,required_bytes=MAX_BYTES,scope='LOCAL_PENDING_REQUEST')
        if stage=='npc-hp-feedback-drained':self.waiting['status']='WAITING_NPC_HP_FEEDBACK_DRAINED'

    def record_npc_stage(self,consumer,pending,current,intent,*,at_ns):
        """Historical local stage only; failure cannot veto the original attack."""
        if self.stage!='npc-hp-feedback-drained' or self.trigger is not None or self.result is not None:return
        try:
            from tools.local_original_session import attack_session,npc_hp,manual_move_commands as manual
            need=observe.need
            need(type(consumer) is manual.ManualMoveCommands and consumer.reader is self.reader
                 and consumer._action_sample.__func__ is manual.HP4EC8_STAGE_PRODUCER
                 and consumer._attack_current.__func__ is manual.HP4EC8_STAGE_CURRENT
                 and consumer.pending is pending and consumer.observe_attack_feedback is True
                 and type(current[0]) is manual.ManualMoveBinding,
                 'HP4EC8_STAGE_CANONICAL_PRODUCER_REQUIRED')
            checked=consumer._attack_current()
            writer,broker,row=current[0].writer,current[0].broker,current[1]
            session=pending['attack_session']
            need(type(checked[0]) is manual.ManualMoveBinding
                 and checked[0].writer is writer and checked[0].broker is broker
                 and checked[1] is row and checked[3] is current[3]
                 and row['operation_lock'].locked() and type(session) is attack_session.AttackSession
                 and session is current[0].broker._attack_session
                 and type(intent) is attack_session.AttackIntent and session._current is intent
                 and session.current_intent() is intent and intent._bound._writer is writer
                 and intent._bound._authority is session.targets
                 and intent._bound.attacker is current[3]
                 and (intent._bound.target_uid,intent._bound.map_id)==(pending['target_uid'],current[3].map_id)
                 and intent.accepted_ordinal==session.accepted_count==pending['attack_before']+1,
                 'HP4EC8_STAGE_CURRENT_INTENT_REQUIRED')
            need(session.feedback_drained==pending['feedback_before']+1
                 and session.validate_feedback(writer,session._feedback_frame,state='DRAINED') is intent,
                 'HP4EC8_STAGE_DRAIN_REQUIRED')
            authority=session._hp
            need(type(authority) is npc_hp.Authority,'HP4EC8_STAGE_HP_AUTHORITY_REQUIRED')
            entry=authority._entries.get((id(writer),pending['target_uid']))
            result=session.last_hp_result
            lifetime,target=session._hp_binding(writer,row,pending['target_uid'])
            need(type(entry) is npc_hp._Entry and type(result) is npc_hp.Result
                 and entry.writer is writer and entry.row is row and entry.lock is row['operation_lock']
                 and entry.lock.locked() and entry.intent is intent and entry.hp is result.after
                 and entry.target==result.target==target
                 and len(entry.lifetime)==len(lifetime)
                 and all(a is b for a,b in zip(entry.lifetime,lifetime))
                 and (result.target.uid,result.target.map_id)==(pending['target_uid'],current[3].map_id)
                 and result.accepted_ordinal==intent.accepted_ordinal,
                 'HP4EC8_STAGE_COMMITTED_HP_REQUIRED')
            final=consumer._attack_current()
            need(type(final[0]) is manual.ManualMoveBinding
                 and final[0].writer is writer and final[0].broker is broker
                 and final[1] is row and final[3] is current[3]
                 and consumer.pending is pending and session._current is intent
                 and session.last_hp_result is result
                 and authority._entries.get((id(writer),pending['target_uid'])) is entry
                 and row['operation_lock'].locked() and session._feedback_state=='DRAINED'
                 and type(at_ns) is int and at_ns>=0,'HP4EC8_STAGE_CHANGED')
            self.trigger=dict(scope='HISTORICAL_LOCAL_HP_COMMIT_AND_FEEDBACK_DRAIN',at_ns=at_ns,
                target_uid=result.target.uid,ordinal=result.accepted_ordinal,
                hp=[result.before.current,result.after.current,result.after.maximum],
                hit=result.hit.landed,damage=result.hit.damage)
            self.waiting['status']='WAITING_FIT'
            self.waiting.update(stage=self.stage,trigger=dict(self.trigger))
        except Exception as error:
            self.result=dict(status='STAGE_PROOF_UNKNOWN',bytes=0,attempted=False,
                stage=self.stage,reason=observe.reason(error),scope='LOCAL_DIAGNOSTIC_FAILURE',
                query_complete=False,owner='NOT_ESTABLISHED')

    def collect(self,sampler,*,total_limit,query):
        if self.result is not None:return self.result
        if self.stage=='npc-hp-feedback-drained' and self.trigger is None:return None
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
        if self.trigger is not None:result.update(stage=self.stage,trigger=dict(self.trigger))
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
