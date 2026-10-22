"""Same canonical SKILL owner: bounded preflighted Buff lifecycle, no sidecar.
Exact source conversion is supplied by a source-backed ResponseAdapter. No
wire-key, time unit or gameplay formula is inferred by this state owner.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib,importlib.util,json,sys,weakref
from pathlib import Path

def need(value,code):
    if not value:raise ValueError(code)

def load(name,relative,sha):
    root=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
    path=root/'work/local_original_session/implementation-3/skill-buff'/relative
    need(hashlib.sha256(path.read_bytes()).hexdigest()==sha,'BUFF_LIFECYCLE_PARENT_CHANGED')
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
        sys.modules[name]=m;spec.loader.exec_module(m)
    return sys.modules[name]
canonical=load('_buff_lifecycle_canonical_parent','canonical_skill.py','c1ef77e41fba8cec73b81941cd8e03b7d42b7f601f7e149999ff932f2ef332ed')
# Same canonical DTO/module objects as the reviewed sender/cost caller.
cost=load('_buff_lifecycle_cost_parent','resource-owner/skill_cost_delivery.py','7b8d39951ce7e7bccbef7e5c25bc5f6167aafaefe176253e9efe9a434dfbbf58')
buff=cost.buff_delivery
optional=cost.optional_buff
spell_bridge=load('_buff_lifecycle_spell_bridge','spell-responses/retirement-v3/bridge.py','9b3d4424c42cf8a32f9090b409cdf3438f2d013f530848baaa8eabef728e965c')
responses=spell_bridge.responses

def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()

@dataclass(frozen=True)
class Event:
    kind:str
    spell_id:int
    expires_ms:int
    accepted_now_ms:int
    previous_expiry_ms:int|None

@dataclass(frozen=True,eq=False)
class Plan:
    binding:object
    txid:str
    request:bytes
    command:str
    accepted_now_ms:int
    before:dict
    after:dict
    events:tuple
    snapshot:object
    remaining:tuple

_PLANS=weakref.WeakKeyDictionary()

class Service(canonical.Service):
    """Plan before source preflight; commit same aggregate only after validation.

    Expiry/restore use at most five Buff frames per canonical operation. Every
    chunk is explicit and independently once-receipted; no limit truncation.
    Caller owns one genuine scope across chunks. Failure blocks that selection;
    new selection restores durable state without replaying attempted receipts.
    """
    def __init__(self,*args,resource_owner,legacy_bindings,source_adapter,source_root,roster_admission=None,initial_learned=(),**kwargs):
        super().__init__(*args,**kwargs)
        need(resource_owner.store is self.store and resource_owner.provider is self.provider
             and legacy_bindings.broker is self.provider.broker,'BUFF_SINGLE_CANONICAL_OWNER_REQUIRED')
        need(isinstance(source_adapter,buff.SourceResponseAdapter),'BUFF_SOURCE_RESPONSE_ADAPTER_REQUIRED')
        self.owner=resource_owner;self.legacy=legacy_bindings;self.adapter=source_adapter;self.root=Path(source_root)
        self.schema.policy_ready(self.root)
        need(type(initial_learned)is tuple and all(type(p)is tuple and len(p)==3
             and type(p[0])is int and 0<p[0]<=0xffffffff and type(p[1])is tuple
             and tuple(sorted(set(p[1])))==p[1] and set(p[1])<=set(self.schema.rules)
             and (p[2]is None or type(p[2])is str and len(p[2])==64)for p in initial_learned)
             and len({p[0]for p in initial_learned})==len(initial_learned),'BUFF_EXPLICIT_INITIAL_LEARNED_CONFIGURATION')
        self.initial_learned=initial_learned
        self.roster_admission=roster_admission
        if roster_admission is not None:
            from tools.local_original_session.cast_route import LocalBackendSelfAdmission
            need(type(roster_admission)is LocalBackendSelfAdmission and roster_admission.bindings is legacy_bindings
                 and roster_admission.status is resource_owner.status
                 and set(self.schema.rules)<=set(roster_admission.allowlist),'SPELL_CONFIGURED_ROSTER_ADMISSION_REQUIRED')
        self.pending={};self.blocked={};self.closed=False
        self.input_selector=None

    def roster_response_adapter(self):
        if self.input_selector is None:return RosterAdapter(self)
        from tools.local_original_session.spell_learned_input import InputSelector
        need(type(self.input_selector)is InputSelector and self.input_selector.service is self
             and not self.input_selector.closed,
             'SPELL_LEARNED_INPUT_EXACT_COLD_OWNER_REQUIRED')
        return self.input_selector.adapter

    def _roster_metadata(self):
        admission=self.roster_admission
        need(admission is not None and not admission.closed,'SPELL_SOURCE_ROSTER_ADMISSION_REQUIRED')
        return tuple((key,admission._metadata(key))for key in sorted(self.schema.rules))

    def _current(self,binding):
        need(not self.closed and id(binding.writer) not in self.blocked,'BUFF_SELECTION_REQUIRES_RESTORE')
        self.provider.current(binding)
        self.owner.require_hp_quiescent(binding.writer)
        return self.owner.status.current(binding.writer)

    def plan_locked(self,binding,*,command,txid,request,now_ms,spell_id=None,restore_ids=None):
        snapshot=self._current(binding)
        if command=='roster':self._roster_metadata()
        need(command in ('tick','restore','remove','roster','reconcile'),'BUFF_LIFECYCLE_COMMAND_REQUIRED')
        need(self.core.integer(now_ms) and type(request) is bytes and request and type(txid) is str,
             'BUFF_ACCEPTED_OPERATION_CLOCK_REQUIRED')
        previous=self.store.lookup(binding,txid=txid,request_sha=self.batch.request_digest(request))
        need(previous is None,'BUFF_RECEIPT_REPLAY_IS_NOT_SEND_AUTHORITY')
        need(id(binding.writer) not in self.pending,'BUFF_OPERATION_ALREADY_ACTIVE')
        before=self.store.participant(binding,'SKILL');self.schema.validate(before['document'])
        doc=deepcopy(before['document']);row=doc['characters'].get(str(binding.uid))
        need(row is not None and now_ms>=row['clock'],'BUFF_CURRENT_CHARACTER_CLOCK_REQUIRED')
        if command=='restore':self.owner.require_exclusive(binding,doc,now_ms=now_ms)
        events=[];remaining=[]
        limit=5-1-int(self.owner._light_policy is not None)
        # Stable expiry/spell ordering gives deterministic chunk ownership.
        expired=sorted((v,int(k)) for k,v in row['buffs'].items() if v<=now_ms)
        if command in ('tick','restore') and expired:
            for expiry,key in expired[:limit]:
                del row['buffs'][str(key)];events.append(Event('buff_remove',key,expiry,now_ms,expiry))
            remaining=[key for expiry,key in expired[limit:]]
        elif command=='remove':
            need(type(spell_id) is int and str(spell_id) in row['buffs'],'SKILL_BUFF_ABSENT')
            expiry=row['buffs'].pop(str(spell_id));events.append(Event('buff_remove',spell_id,expiry,now_ms,expiry))
        elif command=='reconcile':
            ids=tuple(sorted(set(self.schema.rules)-{int(k)for k in row['buffs']})) if restore_ids is None else restore_ids
            need(type(ids)is tuple and len(set(ids))==len(ids) and all(type(k)is int and k in self.schema.rules and str(k)not in row['buffs']for k in ids),
                 'BUFF_EXACT_INACTIVE_RECONCILIATION_REQUIRED')
            events=[Event('buff_remove',key,0,now_ms,None)for key in ids[:limit]];remaining=list(ids[limit:])
        elif command=='restore':
            ids=tuple(sorted(int(k) for k in row['buffs'])) if restore_ids is None else restore_ids
            need(type(ids) is tuple and len(set(ids))==len(ids) and all(type(k)is int and str(k)in row['buffs'] and row['buffs'][str(k)]>now_ms for k in ids),'BUFF_EXACT_ACTIVE_RESTORE_IDS')
            for key in ids[:limit]:events.append(Event('buff_restore',key,row['buffs'][str(key)],now_ms,None))
            remaining=list(ids[limit:])
        if not events and command!='roster':return None # Genuine no-op: no revision/receipt/write.
        row['cooldowns']={k:v for k,v in row['cooldowns'].items() if v>now_ms}
        need(row['revision']<self.core.MAX_TIME,'SKILL_REVISION_OVERFLOW')
        row['revision']+=1;row['clock']=now_ms;self.schema.validate(doc)
        plan=Plan(binding,txid,request,command,now_ms,deepcopy(before),doc,tuple(events),snapshot,tuple(remaining))
        _PLANS[plan]=(self,self.fingerprint(plan));self.pending[id(binding.writer)]=plan
        return plan

    def fingerprint(self,plan):
        return hashlib.sha256(encoded(dict(txid=plan.txid,request=plan.request.hex(),command=plan.command,
            now=plan.accepted_now_ms,before=plan.before,after=plan.after,
            events=[vars(e) for e in plan.events],remaining=plan.remaining))).hexdigest()

    def validate_plan(self,plan):
        witness=_PLANS.get(plan)
        need(type(plan)is Plan and witness is not None and witness[0]is self
             and witness[1]==self.fingerprint(plan) and self.pending.get(id(plan.binding.writer))is plan,
             'BUFF_EXACT_ISSUED_IMMUTABLE_PLAN_REQUIRED')
        need(self._current(plan.binding)is plan.snapshot,'BUFF_ACCEPTED_STATUS_CHANGED')
        need(self.store.participant(plan.binding,'SKILL')==plan.before,'BUFF_STAGED_DOCUMENT_CHANGED')
        return None

    def commit_locked(self,plan,parent):
        need(type(parent)is Delivery and parent.service is self and parent.plan is plan,
             'BUFF_EXACT_PREFLIGHT_PARENT_REQUIRED')
        self.validate_plan(plan);parent.validate_precommit(plan)
        reservation=None
        with self.store.lock:
            self.validate_plan(plan)
            _,revision=self.store.restore(plan.binding)
            change=self.batch.ParticipantChange('SKILL',plan.before['revision'],plan.before['digest'],deepcopy(plan.after))
            try:
                with self.schema.authorize_staged(plan.binding,plan.before['document'],plan.after):
                    reservation=self.store.prepare(plan.binding,txid=plan.txid,request=plan.request,
                        catalog_digest=self.catalog_digest,expected_revision=revision,changes=(),participants=(change,))
                need(type(reservation)is self.batch.Reservation,'BUFF_NEW_RESERVATION_REQUIRED')
                receipt=self.store.commit(plan.binding,reservation)
            except BaseException:
                if reservation is not None:
                    try:self.store.abort(plan.binding,reservation)
                    except BaseException:pass # Never undo ambiguous commit or issue a refund.
                raise
            actual=self.store.participant(plan.binding,'SKILL')
            need(receipt['phase']=='COMMITTED' and actual['document']==plan.after,'BUFF_COMMIT_READBACK_REQUIRED')
            return receipt

    def discard(self,plan):
        if self.pending.get(id(plan.binding.writer))is plan:self.pending.pop(id(plan.binding.writer))
        _PLANS.pop(plan,None)

    async def execute_locked(self,binding,*,command,txid,request,now_ms,spell_id=None,restore_ids=None):
        self._current(binding)
        self.legacy.selected_locked(binding) # Exact binding belongs to THIS owned scope.
        plan=self.plan_locked(binding,command=command,txid=txid,request=request,now_ms=now_ms,
                              spell_id=spell_id,restore_ids=restore_ids)
        if plan is None:return None
        parent=Delivery(self,plan)
        try:
            parent.preflight()
            receipt=self.commit_locked(plan,parent)
            parent.bind_committed(receipt)
            await self.provider.broker._send(binding.writer,binding.generation.row,parent.frames,
                game=True,operation_lock=binding.operation_lock,skill_operation=parent)
            return plan.remaining
        except BaseException as error:
            parent.failed(error);raise
        finally:self.discard(plan)

    def transition_locked(self,binding,*,txid,request,operation):
        """Only pure entitlement learning remains a direct document operation.
        Buff transitions MUST use execute_locked with before-write preflight.
        """
        self._current(binding)
        need(type(operation)is dict and set(operation)=={'command','spell_id'}
             and operation['command']=='learn','BUFF_TRANSITIONS_REQUIRE_SOURCE_PREFLIGHT')
        previous=self.store.lookup(binding,txid=txid,request_sha=self.batch.request_digest(request))
        if previous is not None:return canonical.Outcome(previous,None,True)
        before=self.store.participant(binding,'SKILL');now=self._now()
        row=before['document']['characters'][str(binding.uid)]
        need(not any(v<=now for v in row['buffs'].values()),'BUFF_EXPIRE_BEFORE_LEARN_REQUIRED')
        need(callable(self.entitlement)and self.core.Session._sync(self.entitlement,binding,operation['spell_id'])is True,
             'SKILL_PURE_ENTITLEMENT_REQUIRED')
        result,after=self.schema.plan_apply(before['document'],binding,command='learn',spell_id=operation['spell_id'],
            now_ms=now,expected_revision=row['revision'],learn_grant=True)
        return self._commit_document(binding,txid,request,before,after,result)

    def selection_locked(self,binding,selection_request):
        """Original selected hook; optional startup learned grant is explicit.

        An explicit grant None preimage admits ONLY an absent participant; an
        existing account missing this actor requires its exact configured digest.
        Existing selected documents are never overwritten by startup settings.
        """
        self.provider.current(binding)
        need(type(selection_request)is bytes and selection_request,'BUFF_ORIGINAL_SELECTED_REQUEST_REQUIRED')
        try:before=self.store.participant(binding,'SKILL')
        except ValueError as error:
            if error.args!=('BATCH_PARTICIPANT_NOT_INSTALLED',):raise
            before=dict(revision=-1,digest=self.batch.digest(None),document=None)
        old=before['document']
        if old is not None:
            self.schema.validate(old)
            blocked=self.blocked.get(id(binding.writer))
            if blocked is not None:
                need(blocked is not binding.generation and blocked.phase=='RETIRED'
                     and id(binding.writer)not in self.pending
                     and self.owner._delivery_active is None
                     and id(binding.writer)not in self.owner._deliveries
                     and id(binding.writer)not in self.owner.status._resource_deliveries
                     and not any(r['cap'].binding.generation is blocked for r in self.store._delivery_caps.values()),
                     'BUFF_OLD_SELECTION_RETIRE_REQUIRED')
                self.blocked.pop(id(binding.writer))
            if str(binding.uid)in old['characters']:return
        entry=next((p for p in self.initial_learned if p[0]==binding.uid),None)
        # Named local setup policy: a genuinely selected new actor starts EMPTY;
        # only a configured entry can grant learned spells. Exact CAS and actor
        # ownership still protect the current whole-account preimage.
        if entry is None:entry=(binding.uid,(),None if old is None else before['digest'])
        need(old is None and entry[2]is None or old is not None and entry[2]==before['digest'],
             'BUFF_EXPLICIT_STARTUP_LEARNED_PREIMAGE_REQUIRED')
        self._roster_metadata()
        now=self._now();initial=self.schema.initial_document(binding,now_ms=now)
        after=initial if old is None else deepcopy(old)
        after['characters'][str(binding.uid)]=initial['characters'][str(binding.uid)]
        after['characters'][str(binding.uid)]['learned']=list(entry[1])
        self.schema.validate(after)
        self._commit_document(binding,'BUFF_INIT:'+str(binding.uid),
            b'LOCAL_BUFF_STARTUP_V1'+selection_request+encoded(entry),before,after,dict(kind='configured_learned_setup'))

    async def lifecycle_locked(self,binding,*,restore=False,now_ms=None):
        """Original caller owns scope; complete ALL chunks, never silently truncate.

        Local operation identity is generation + canonical selected revision +
        command. Existing BatchStore once receipt owns retry; no nonce registry.
        Unknown failure requires selection cleanup before any subsequent poll.
        """
        self._current(binding)
        self.legacy.selected_locked(binding)
        now_ms=self._now() if now_ms is None else now_ms
        need(self.core.integer(now_ms),'BUFF_SERVER_CLOCK_REQUIRED')
        async def chunk(command,ids=None):
            self._current(binding)
            data=self.read_locked(binding);row=data['characters'][str(binding.uid)]
            txid='BUFF:'+binding.generation_key+':'+str(row['revision'])+':'+command
            need(len(txid)<=128,'BUFF_EXISTING_OPERATION_ID_BOUND')
            request=encoded(dict(policy='LOCAL_BUFF_LIFECYCLE_V1',generation=binding.generation_key,
                uid=binding.uid,revision=row['revision'],command=command,now_ms=now_ms,restore_ids=ids))
            return await self.execute_locked(binding,command=command,txid=txid,request=request,
                now_ms=now_ms,restore_ids=ids)
        expired_drained=set()
        while True:
            data=self.read_locked(binding);row=data['characters'][str(binding.uid)]
            if not any(v<=now_ms for v in row['buffs'].values()):break
            expired_drained.update(int(k)for k,v in row['buffs'].items()if v<=now_ms)
            await chunk('tick')
        if restore:
            active=self.read_locked(binding)['characters'][str(binding.uid)]['buffs']
            clear_ids=tuple(sorted(set(self.schema.rules)-{int(k)for k in active}-expired_drained))
            while clear_ids:clear_ids=await chunk('reconcile',clear_ids)
            await chunk('roster')
            ids=tuple(sorted(int(k) for k in self.read_locked(binding)['characters'][str(binding.uid)]['buffs']))
            while ids:
                ids=await chunk('restore',ids)
        return None

    def retire_writer(self,writer):
        if self.input_selector is not None:self.input_selector.retire_writer(writer)
        plan=self.pending.get(id(writer))
        if plan is not None:self.discard(plan)
        self.blocked.pop(id(writer),None)

    def close(self):
        if self.closed:return
        self.closed=True
        for plan in tuple(self.pending.values()):self.discard(plan)
        self.blocked.clear()
        adapter=self.adapter
        try:
            close=getattr(adapter,'close',None)
            if callable(close):close()
        finally:
            primary=sys.exception()
            try:
                if self.input_selector is not None:self.input_selector.close()
            except BaseException as secondary:
                if primary is None:raise
                try:primary.add_note('Learned input cleanup raised '+type(secondary).__name__)
                except BaseException:pass
            finally:
                self.input_selector=None
                if self.owner is not None:self.owner._light_policy=self.owner._light=None
                self.owner=self.adapter=self.legacy=self.roster_admission=None
                self.initial_learned=()
                self.store=self.provider=self.schema=self.core=self.batch=self.clock=self.entitlement=self.roster_grant=None

@dataclass(frozen=True)
class EventPlan:
    """One wire operation; all numbers/units still supplied by source adapter."""
    transition:Plan
    event:Event
    index:int

_DELIVERIES=weakref.WeakKeyDictionary()

class Delivery(optional.retirement.ParentLifetime):
    """One SKILL chunk, one receipt and original send lifecycle; no new sender."""
    def __init__(self,service,plan):
        super().__init__();service.validate_plan(plan)
        self.service=service;self.owner=service.owner;self.plan=plan;self.binding=plan.binding
        self.txid,self.request=plan.txid,plan.request
        self.frames=();self.preflights=();self.parts=[];self.consumer=None
        self.roster=plan.command=='roster'
        self.receipt=self.cap=None;self.index=0;self.phase='PREFLIGHTING'
        self.status_fields=self.status_wire=self.status_delivery=None
        self.light_wire=self.light_scalar=self.light_part=None
        self.projected_snapshot=plan.snapshot
        self.port_phase='BEFORE_RESERVE';self._failure=None;self._drain=False
        _DELIVERIES[self]=(service,plan,service.fingerprint(plan))

    def preflight(self):
        s=self.service
        try:
            self.status_fields=self.owner.shield_status_fields(self.binding,dict(self.plan.snapshot.fields),self.plan.after)
            if self.status_fields!=dict(self.plan.snapshot.fields):self.status_wire=self.owner.status_module.frame(self.status_fields)
            if self.roster:
                codec=responses.Codec(s.root)
                self.consumer=spell_bridge.ScopedBridge(parent=self,bindings=s.legacy,codec=codec,
                    owned_provider=s.provider,source_adapter=s.roster_response_adapter(),delivery_module=buff)
                prepared=[self.consumer.preflight(self.binding,request=self.request,source_plan=self.plan)]
                self.frames=(prepared[0].prepared.wire,)
            else:
                self.consumer=optional.OptionalScopedService(parent=self,root=s.root,broker=s.provider.broker,
                    store=s.store,owned_provider=s.provider,legacy_bindings=s.legacy,source_adapter=s.adapter)
                prepared=[]
                for index,event in enumerate(self.plan.events):
                    s.validate_plan(self.plan)
                    prepared.append(self.consumer.preflight(self.binding,request=self.request,
                        source_plan=EventPlan(self.plan,event,index)))
                    s.validate_plan(self.plan)
                self.frames=tuple(p.wire for p in prepared)
            self.preflights=tuple(prepared)
            if self.status_wire is not None:self.frames=(self.status_wire,)+self.frames
            if any(event.spell_id==1 for event in self.plan.events):
                light=self.owner.light_wire(self.binding,self.plan.after)
                if light is not None:
                    self.light_wire,self.light_scalar=light;self.frames+=(self.light_wire,)
            need(0<len(self.frames)<=5,'BUFF_EXPLICIT_CHUNK_REPLY_BOUND')
            self.parts=[None]*len(self.frames);self.phase='PREFLIGHTED'
            self.owner.register_delivery_dispatcher()
        except BaseException:
            self.phase='TERMINAL';self.retire();raise

    def validate_precommit(self,plan):
        need(self.phase=='PREFLIGHTED' and self.plan is plan,'BUFF_SOURCE_PREFLIGHT_REQUIRED')
        self.service.validate_plan(plan)
        if self.roster:self.service._roster_metadata()
        need(self.status_fields==self.owner.shield_status_fields(self.binding,dict(plan.snapshot.fields),plan.after)
             and (self.status_wire is None if self.status_fields==dict(plan.snapshot.fields) else self.status_wire==self.owner.status_module.frame(self.status_fields)),
             'SHIELD_LIFECYCLE_PREFLIGHT_CHANGED')
        light=(self.owner.light_wire(self.binding,plan.after)if any(e.spell_id==1 for e in plan.events)else None)
        need(light==(None if self.light_wire is None else (self.light_wire,self.light_scalar)),
             'LIGHT_SEALED_LIFECYCLE_PREFLIGHT_CHANGED')
        for p,wire in zip(self.preflights,self.frames[int(self.status_wire is not None):]):
            need(p.binding is self.binding and p.request==self.request and (p.prepared.wire if self.roster else p.wire)is wire
                 and self.consumer.codec.encode_frame(p.prepared.response if self.roster else p.prepared.request)==wire,'BUFF_PREFLIGHT_MUTATION')
            need(self.consumer.adapter.current(self.binding,p.prepared,p.source_plan,self.request)is None,
                 'BUFF_SOURCE_CURRENT_MUST_RAISE')
            self.service.validate_plan(plan)
        return None

    def bind_committed(self,receipt):
        need(self.phase=='PREFLIGHTED' and receipt['phase']=='COMMITTED'
             and receipt['delivery']=='UNATTEMPTED','BUFF_COMMITTED_ONCE_REQUIRED')
        self.receipt=deepcopy(receipt);self.phase='ATTACHING'
        offset=int(self.status_wire is not None)
        if offset:
            self.status_delivery=self.owner.project_buff_commit(self.service,self.plan,self,receipt,self.status_fields,self.status_wire)
            self.projected_snapshot=self.status_delivery.result.after
            self.parts[0]=self.status_delivery
        need(self.owner._delivery_active is None,'BUFF_SINGLE_PARENT_REQUIRED')
        self.owner._delivery_active=self
        for index,p in enumerate(self.preflights,offset):
            if self.roster:self.consumer.bind_committed(p,parent=self,index=index,txid=self.txid,receipt=self.receipt)
            else:self.consumer.bind_committed(p,parent=self,index=index,txid=self.txid)
        if self.light_wire is not None:
            self.light_part=self.owner._light.LightPart(self,self.light_wire,self.light_scalar,len(self.parts)-1)
            self.parts[-1]=self.light_part
        need(all(p is not None for p in self.parts),'BUFF_ALL_DECLARED_PARTS_REQUIRED')
        # The original status _Delivery is slots-only and already owned by
        # this same tuple. Keep its exact identity without inventing a lease.
        self.parts=tuple(self.parts);self._part_refs=tuple((lambda part=p:part)if p is self.status_delivery else weakref.ref(p)for p in self.parts);self._fixed_frames=self.frames
        self.phase='OPENING'
        self.cap=self.owner.store.open_delivery(self.binding,self.owner._delivery_dispatcher,self,
            txid=self.txid,request=self.request,receipt=self.receipt,frames=self.frames)
        self.phase='READY'

    def attach_active(self,part):
        need(self.phase=='ATTACHING' and type(part)is (responses.FrameParticipant if self.roster else buff.Operation) and part.parent is self
             and 0<=part.index<len(self.parts) and self.parts[part.index]is None
             and part.preflight is self.preflights[part.index-int(self.status_wire is not None)],'BUFF_EXACT_PART_REQUIRED')
        self.parts[part.index]=part

    def validate_memory(self,binding,*,txid,request,receipt,participant,index,wire,phase):
        w=_DELIVERIES.get(self)
        need(self.frames is self._fixed_frames and len(self.parts)==len(self._part_refs)
             and all(ref()is part for ref,part in zip(self._part_refs,self.parts)), 'BUFF_ORIGINAL_ISSUED_PARTS_REQUIRED')
        need(self.owner.status._states.get(id(binding.writer))is self.projected_snapshot,
             'BUFF_FIXED_RESOURCE_SNAPSHOT_REQUIRED')
        need(w is not None and w[0]is self.service and w[1]is self.plan
             and w[2]==self.service.fingerprint(self.plan) and self.owner._delivery_active is self
             and binding is self.binding and txid==self.txid and request==self.request
             and receipt==self.receipt and type(index)is int and index==self.index
             and wire is self.frames[index],'BUFF_FIXED_PARENT_MEMORY_REQUIRED')
        need(participant is self.parts[index] or participant is None and self.phase=='OPENING' and index==0,
             'BUFF_FIXED_PARTICIPANT_REQUIRED')
        if self.light_part is not None:self.light_part.validate()
        if phase=='UNKNOWN':need(self.phase=='FAILING' and isinstance(self._failure,BaseException),'BUFF_REAL_SEND_FAILURE_REQUIRED')
        else:need(phase in ('BEFORE_RESERVE','BEFORE_WRITE_CHECKPOINT','BEGIN_WRITE','DRAIN_PENDING','AFTER_DRAIN'),'BUFF_PHASE_REQUIRED')
        return True

    def _receipt(self):
        r=self.owner.store.receipt_for_delivery(self.cap,participant=self.parts[self.index],index=self.index,
            wire=self.frames[self.index],phase=self.port_phase)
        expected=deepcopy(self.receipt);expected['delivery']=r['delivery']
        need(r==expected,'BUFF_RECEIPT_PREIMAGE_CHANGED');return r

    def current_active(self,binding,*,txid,request,participant,index,wire,phase):
        need(binding is self.binding and txid==self.txid and request==self.request,'BUFF_EXACT_PARENT_CONTEXT')
        if self.phase=='ATTACHING':
            self.owner.provider.current(binding)
            need(0<=index<len(self.parts) and phase in ('PREPARING','PREPARED') and
                 (participant is None and wire is None or participant is self.parts[index] and wire is self.frames[index]),'BUFF_EXACT_ATTACH')
            need(self.owner.store.recover(binding,txid=txid,request=request)==self.receipt,'BUFF_RECEIPT_CHANGED_BEFORE_OPEN')
            return
        need(participant is self.parts[self.index] and index==self.index and wire is self.frames[index],
             'BUFF_EXACT_CURRENT_FRAME')
        self._receipt()

    def validate_projection(self,snapshot):
        # No RESOURCE effect exists in this operation. During pending delivery
        # the issued cap seals the ENTIRE aggregate preimage, not only SKILL.
        need(snapshot is self.projected_snapshot and self.owner.status._states.get(id(self.binding.writer))is snapshot
             and dict(snapshot.fields)==self.status_fields,
             'BUFF_FIXED_UNCHANGED_RESOURCE_SNAPSHOT')
        if self.cap is None:
            self.owner.provider.current(self.binding)
            resource=self.owner._participant(self.binding)['document']
            need({str(n):snapshot.fields[n]for n in (10,11,12,13)}==resource['values'],
                 'BUFF_CANONICAL_RESOURCE_PROJECTION_CHANGED')
        else:self._receipt()
        return True

    def validate_batch(self,writer,row,replies):
        need(self.phase=='READY' and self.index==0 and writer is self.binding.writer
             and row is self.binding.generation.row and type(replies)is tuple and len(replies)==len(self.frames)
             and all(a is b for a,b in zip(replies,self.frames)),'BUFF_EXACT_REPLY_BATCH')
        self._receipt()

    def reserve(self,writer,row,wire):
        self.port_phase='BEFORE_RESERVE';self._receipt()
        if self.status_wire is not None and self.index==0:
            need(self.status_delivery.phase=='PREPARED','SHIELD_STATUS_SINGLE_RESERVATION');self.status_delivery.phase='RESERVED'
        elif self.parts[self.index]is self.light_part:self.light_part.transition('PREPARED','RESERVED')
        elif self.roster:self.consumer.validate_parent(self.parts[self.index],phase='PREPARED')
        else:self.consumer.reserve(writer,row,wire,self.parts[self.index])
        self.phase='SENDING'
    def before_write_checkpoint(self,writer,row,wire):
        need(wire is self.frames[self.index],'BUFF_NEXT_WIRE_REQUIRED')
        self.port_phase='BEFORE_WRITE_CHECKPOINT';self._receipt()
    def attempt(self,writer,row,wire):
        self.port_phase='BEGIN_WRITE'
        self.owner.store.mark_delivery(self.cap,participant=self.parts[self.index],index=self.index,
            wire=wire,phase=self.port_phase,state='WRITE_ATTEMPTED')
        if self.status_wire is not None and self.index==0:
            need(self.status_delivery.phase=='RESERVED','SHIELD_STATUS_SINGLE_WRITE');self.status_delivery.phase='WRITE_ATTEMPTED'
        elif self.parts[self.index]is self.light_part:self.light_part.transition('RESERVED','WRITE_ATTEMPTED')
        elif self.roster:self.consumer.validate_parent(self.parts[self.index],phase='RESERVED')
        else:self.consumer.attempt(writer,row,wire,self.parts[self.index])
    def drain_returned(self,writer,row,wire):
        self.port_phase='DRAIN_PENDING';self._drain=True;self._receipt()
        if self.status_wire is not None and self.index==0 or self.parts[self.index]is self.light_part:pass
        elif self.roster:self.consumer.validate_parent(self.parts[self.index],phase='WRITE_ATTEMPTED')
        else:self.consumer.drain_returned(writer,row,wire,self.parts[self.index])
    def validate_pending_drain(self,writer,row,wire):
        need(self._drain,'BUFF_ORIGINAL_DRAIN_REQUIRED');self.port_phase='DRAIN_PENDING';self._receipt()
        if self.status_wire is not None and self.index==0 or self.parts[self.index]is self.light_part:pass
        elif self.roster:self.consumer.validate_parent(self.parts[self.index],phase='WRITE_ATTEMPTED')
        else:self.consumer.validate_pending_drain(writer,row,wire,self.parts[self.index])
    def drained(self,writer,row,wire,queued):
        need(self._drain and queued==0,'BUFF_ORIGINAL_ZERO_QUEUE_DRAIN_REQUIRED')
        self.port_phase='AFTER_DRAIN';self._receipt()
        if self.status_wire is not None and self.index==0:
            need(self.status_delivery.phase=='WRITE_ATTEMPTED','SHIELD_STATUS_EXACT_DRAIN');self.status_delivery.phase='DRAINED'
        elif self.parts[self.index]is self.light_part:self.light_part.transition('WRITE_ATTEMPTED','DRAINED')
        elif self.roster:self.consumer.validate_parent(self.parts[self.index],phase='WRITE_ATTEMPTED')
        else:self.consumer.drained(writer,row,wire,self.parts[self.index],queued)
        self.owner.store.mark_delivery(self.cap,participant=self.parts[self.index],index=self.index,
            wire=wire,phase=self.port_phase,state='DRAINED')
        self.index+=1;self._drain=False;self.port_phase='BEFORE_RESERVE'
        if self.index==len(self.frames):
            self.phase='DONE';self.retire()
        else:self.phase='READY'

    def failed(self,error):
        if self.phase in ('DONE','TERMINAL'):return
        self._failure=error;self.phase='FAILING'
        try:
            if self.cap is not None:
                try:self.owner.store.terminal_unknown(self.cap,index=self.index,wire=self.frames[self.index],participant=self.parts[self.index])
                except BaseException:pass
            if self.binding is not None:self.service.blocked[id(self.binding.writer)]=self.binding.generation
        finally:
            self.phase='TERMINAL'
            try:self.retire()
            except BaseException:pass
    def retirement_state(self):return 'DRAINED' if self.phase=='DONE' else 'TERMINAL' if self.phase=='TERMINAL' else None
    def release_parent_refs(self):
        owner,cap=self.owner,self.cap
        try:
            if cap is not None:owner.store.retire_delivery(cap)
        finally:
            if owner._delivery_active is self:owner._delivery_active=None
            if self.status_delivery is not None:
                for mapping in (owner._deliveries,owner.status._resource_deliveries):
                    if mapping.get(id(self.binding.writer))is self.status_delivery:mapping.pop(id(self.binding.writer))
                self.status_delivery.resource_context=None
                if self.status_delivery.phase!='DRAINED':self.status_delivery.phase='TERMINAL'
            if self.light_part is not None:self.light_part.retire()
            self.light_part=self.light_wire=self.light_scalar=None
            self.status_delivery=self.status_fields=self.status_wire=self.projected_snapshot=None
            _DELIVERIES.pop(self,None)
            self.frames=self.preflights=self.parts=self._part_refs=self._fixed_frames=()
            self.service=self.owner=self.plan=self.binding=self.consumer=self.receipt=self.cap=self.request=None
        return None

class RosterAdapter(buff.SourceResponseAdapter):
    """Exact learned truth from the issued v1 document, no learning grant/ACK."""
    def __init__(self,service):self.service=service
    def _response(self,binding,plan,request):
        witness=_PLANS.get(plan)
        need(witness is not None and witness[0]is self.service and witness[1]==self.service.fingerprint(plan)
             and plan.command=='roster' and plan.binding is binding and plan.request==request,
             'SPELL_EXACT_ISSUED_ROSTER_PLAN')
        learned=plan.before['document']['characters'][str(binding.uid)]['learned']
        return responses.Available(tuple(responses.SpellInfo(key,key in learned)for key in sorted(self.service.schema.rules)))
    def prepare_exact(self,binding,source_plan,request):
        response=self._response(binding,source_plan,request)
        return responses.prepare_locked(self.service.legacy,binding.writer,response,
            codec=responses.Codec(self.service.root),owned_provider=self.service.provider,operation_binding=binding)
    def current(self,binding,prepared,source_plan,request):
        need(type(prepared)is responses.PreparedResponse and prepared.operation_binding is binding
             and prepared.response==self._response(binding,source_plan,request), 'SPELL_ROSTER_SOURCE_CHANGED')
        return None
