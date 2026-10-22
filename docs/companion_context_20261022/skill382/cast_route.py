"""Default-off4EE6 ingress with separate source and explicit local-self paths."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from tools.local_persistent_broker_policy.policy import MAX_COUNTER

OPCODE=0x4ee6
LOCAL_SELF_POLICY='LOCAL_BACKEND_SELF_CAST'
METADATA_SHA='b79b28435eccd5dc7cc093f197c94fe52314259cb0d99ae555fa7763db6a0454'

def need(value,code):
    if not value:raise ValueError(code)

def load_codec():
    path=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())/'work/local_original_session/implementation-3/skill-buff/cast_wire.py'
    need(hashlib.sha256(path.read_bytes()).hexdigest()=='afa29d98b66d2fbf7686e16799dc809b75ab8dcb824ba46042a65d6b249eb3ef','CAST_ROUTE_CODEC_PARENT_CHANGED')
    name='_skill_buff_cast_wire_v1'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
        sys.modules[name]=m;spec.loader.exec_module(m)
    return sys.modules[name]

wire=load_codec()

@dataclass(frozen=True)
class InputOperation:
    binding:object=field(repr=False)
    row:object=field(repr=False)
    policy:object=field(repr=False)
    payload:bytes=field(repr=False)
    wire_length:int
    received_ordinal:int
    txid:str

@dataclass(frozen=True)
class AdmittedCast:
    spell_id:int
    target_uid:int
    snapshot:object=field(repr=False)
    original_input_owner:object=field(repr=False)
    original_actor_owner:object=field(repr=False)
    source_epoch:object=field(repr=False)

class SourceCastAdmission(ABC):
    """Trusted server adapter, never supplied by client payload.

    admit/current must prove original normal input identity and current actor,
    targetvirtual8 role, live selected/receiver lifetime and same source epoch.
    Returning arbitrary UID/bool/empty-target-to-self is not an implementation.
    current raises or returns None; no currently delivered production adapter
    establishes this contract, so actual_cast_enabled remains false.
    """
    @abstractmethod
    def admit(self,operation,decoded):...
    @abstractmethod
    def current(self,operation,decoded,decision):...

class UnresolvedAdmission(SourceCastAdmission):
    def admit(self,operation,decoded):
        raise ValueError('CAST_ORIGINAL_INPUT_ACTOR_TARGET_LIFETIME_UNRESOLVED')
    def current(self,operation,decoded,decision):
        raise ValueError('CAST_ORIGINAL_INPUT_ACTOR_TARGET_LIFETIME_UNRESOLVED')

@dataclass(frozen=True)
class Selected:
    uid:int
    writer:object=field(repr=False)
    lock:object=field(repr=False)
    binding:object=field(repr=False)
    row:object=field(repr=False)
    game:object=field(repr=False)
    selection:object=field(repr=False)
    mover:object=field(repr=False)

class CanonicalSelectedBindings:
    """Read-only codec compatibility protocol, not legacy Bindings/Session.

    No Store, resource balance, actor/target semantics or persistent game state.
    HP is freshly checked on every call; normal canonical cost projection may
    advance its Snapshot without changing selected lifetime identity.
    """
    def __init__(self,broker,provider,status):
        need(provider.broker is broker and status.broker is broker,
             'CAST_SELECTED_SAME_RUNTIME_REQUIRED')
        self.broker,self.provider,self.status=broker,provider,status
        self.bound={};self.closed=False

    def _read(self,binding):
        need(not self.closed and self.broker._canonical_provider is self.provider
             and self.broker._hp_status is self.status,'CAST_SELECTED_CURRENT_RUNTIME_REQUIRED')
        self.provider.current(binding)
        b,w=self.broker,binding.writer
        row=binding.generation.row
        game=b.realm.registry.resolve(w);mover=b.realm.service(w);position=mover.snapshot()
        selected=game.selection
        need(row['writer'] is w and row['operation_lock'] is binding.operation_lock
             and binding.generation.writer is w and binding.generation.lock is binding.operation_lock
             and selected is not None and b.realm.registry.selected.get(position.name) is selected
             and selected.reference==position.name and binding.uid==position.uid
             and not mover.fatal and not b.realm._settings_failed and id(w) not in b.realm._quit,
             'CAST_SELECTED_EXACT_GENERATION_LIFETIME_REQUIRED')
        b.realm.bound_account(w,game)
        snapshot=self.status.current(w)
        need(snapshot.target_uid==binding.uid and id(w) not in self.status._world,
             'CAST_SELECTED_ORIGINAL_WORLD_DRAIN_REQUIRED')
        self.provider.current(binding)
        return row,game,selected,mover

    def selected_locked(self,binding):
        row,game,selected,mover=self._read(binding)
        old=self.bound.get(id(binding.writer))
        if old is not None and old[0].binding is binding:
            self.current(old[0]);return old[0]
        value=Selected(binding.uid,binding.writer,binding.operation_lock,binding,row,game,selected,mover)
        self.bound[id(binding.writer)]=(value,)
        self.current(value)
        return value

    def current(self,selected):
        need(type(selected) is Selected and self.bound.get(id(selected.writer),(None,))[0] is selected,
             'CAST_SELECTED_RETIRED_COMPAT_SELECTION')
        current=self._read(selected.binding)
        need(all(a is b for a,b in zip(current,(selected.row,selected.game,selected.selection,selected.mover))),
             'CAST_SELECTED_LIFETIME_CHANGED')
        return True # Existing codec's structural protocol only; no target admission.

    def retire_writer(self,writer):self.bound.pop(id(writer),None)
    def close(self):
        self.closed=True;self.bound.clear();self.broker=self.provider=self.status=None


@dataclass(frozen=True)
class LocalSelfDecision:
    """Explicit backend target selection, never original input/actor proof."""
    spell_id:int
    target_uid:int
    snapshot:object=field(repr=False)
    operation:InputOperation=field(repr=False)
    selected:Selected=field(repr=False)
    policy:str
    catalog_fingerprint:str


class LocalBackendSelfAdmission:
    """Approved local policy for source-pinned Light1/Shield2 SELF rows.

    Optional nested target absence or explicit0 are permitted representations;
    neither proves self. Other target values refuse. Target is selected solely
    from the current owned operation's selected UID under this named policy.
    Native input/actor owners are never manufactured or retained here.
    """
    def __init__(self,source_root,*,policy,allowlist,bindings,status,key_policy=None):
        need(policy==LOCAL_SELF_POLICY and type(allowlist) is tuple and allowlist
             and len(set(allowlist))==len(allowlist)
             and all(type(key)is int and (key in (1,2) if key_policy is None else 0<key<1<<31)for key in allowlist),
             'CAST_LOCAL_SELF_EXPLICIT_POLICY_ALLOWLIST_REQUIRED')
        need(type(bindings) is CanonicalSelectedBindings and status is bindings.status,
             'CAST_LOCAL_SELF_SAME_SELECTED_STATUS_REQUIRED')
        self.root=Path(source_root)
        need(self.root.is_absolute(),'CAST_LOCAL_SELF_ABSOLUTE_SOURCE_ROOT')
        self.policy,self.allowlist,self.bindings,self.status=policy,allowlist,bindings,status
        self.closed=False
        self._catalog_policy=self._catalog_identity=key_policy;self._catalog_state=None
        if key_policy is not None:
            from tools.local_original_session.buff_skill_document import InstancePolicy
            need(type(key_policy)is InstancePolicy and {p[0]for p in key_policy.entries}==set(allowlist),
                 'CAST_EXACT_COLD_CATALOG_POLICY_REQUIRED')
            self._catalog_state=(key_policy.name,key_policy.entries,key_policy.source_contract_sha256,
                key_policy.metadata_sources,key_policy.metadata_rows)
        for key in allowlist:self._metadata(key)

    def _metadata(self,key):
        need(not self.closed,'CAST_LOCAL_SELF_ADMISSION_CLOSED')
        p=self._catalog_policy
        need(p is self._catalog_identity,'CAST_EXACT_COLD_CATALOG_POLICY_CHANGED')
        if p is not None and p.name=='LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1':
            need((p.name,p.entries,p.source_contract_sha256,p.metadata_sources,p.metadata_rows)==self._catalog_state,
                 'CAST_EXACT_COLD_CATALOG_POLICY_CHANGED')
            rows=tuple(r for r in p.metadata_rows if r[0]==key)
            need(len(rows)==1 and rows[0][1]=='generic','CAST_LOCAL_SELF_EXACT_SOURCE_ROW_REQUIRED')
            return hashlib.sha256(json.dumps((rows[0],p.metadata_sources),separators=(',',':')).encode()).hexdigest()
        path=self.root/'work/local_original_session/implementation-3/skill-buff/spell_metadata.py'
        try:raw=path.read_bytes()
        except OSError:raise ValueError('CAST_LOCAL_SELF_METADATA_UNAVAILABLE') from None
        need(hashlib.sha256(raw).hexdigest()==METADATA_SHA,
             'CAST_LOCAL_SELF_METADATA_ADAPTER_CHANGED')
        # Consume this verified source, not a preloaded alias or mutable cached
        # class/method. No private Catalog object escapes this call.
        namespace={'__name__':'_skill_local_self_verified_metadata','__file__':str(path)}
        exec(compile(raw,str(path),'exec'),namespace)
        try:catalog=namespace['Catalog'](self.root)
        except OSError:raise ValueError('CAST_LOCAL_SELF_METADATA_SOURCE_UNAVAILABLE') from None
        metadata=catalog.describe(key)
        rows=metadata['ui_rows']
        need(len(rows)==1 and rows[0]['class']=='generic' and rows[0]['grade']==1
             and rows[0]['spell_id']==key and rows[0]['named_UI_configuration']['id']==key
             and rows[0]['named_UI_configuration'].get('required',{}).get('target')=='self'
             and 'catalyst' not in rows[0]['named_UI_configuration'],
             'CAST_LOCAL_SELF_EXACT_SOURCE_ROW_REQUIRED')
        return hashlib.sha256(json.dumps(metadata,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def _current(self,operation,decoded):
        need(not self.closed and self.policy==LOCAL_SELF_POLICY,'CAST_LOCAL_SELF_ADMISSION_CLOSED')
        need(type(operation) is InputOperation and decoded.selection.binding is operation.binding
             and decoded.selection.writer is operation.binding.writer
             and operation.row is operation.binding.generation.row
             and operation.row['policy_row'] is operation.policy
             and operation.policy.received==operation.received_ordinal,
             'CAST_LOCAL_SELF_EXACT_RECEIVED_OPERATION_REQUIRED')
        self.bindings.provider.current(operation.binding)
        self.bindings.current(decoded.selection)
        key=decoded.request.signed_lookup_key
        need(key in self.allowlist and (self._catalog_policy is not None or key in (1,2)),'CAST_LOCAL_SELF_CATALOG_NOT_ALLOWLISTED')
        target=None if decoded.request.params is None else decoded.request.params.target_result_i32
        need(target in (None,0),
             'CAST_LOCAL_SELF_DIRECTED_TARGET_UNSUPPORTED')
        fingerprint=self._metadata(key)
        snapshot=self.status.current(operation.binding.writer)
        need(snapshot.target_uid==operation.binding.uid
             and id(operation.binding.writer) not in self.status._world,
             'CAST_LOCAL_SELF_CURRENT_COMPLETED_WORLD_REQUIRED')
        self.bindings.provider.current(operation.binding)
        self.bindings.current(decoded.selection)
        return key,snapshot,fingerprint

    def admit(self,operation,decoded):
        key,snapshot,fingerprint=self._current(operation,decoded)
        return LocalSelfDecision(key,operation.binding.uid,snapshot,operation,decoded.selection,self.policy,fingerprint)

    def current(self,operation,decoded,decision):
        need(type(decision) is LocalSelfDecision and decision.operation is operation
             and decision.selected is decoded.selection and decision.policy==LOCAL_SELF_POLICY,
             'CAST_LOCAL_SELF_EXACT_DECISION_REQUIRED')
        key,snapshot,fingerprint=self._current(operation,decoded)
        need(decision.spell_id==key and decision.target_uid==operation.binding.uid
             and decision.snapshot is snapshot and decision.catalog_fingerprint==fingerprint,
             'CAST_LOCAL_SELF_DECISION_SOURCE_OR_SNAPSHOT_CHANGED')

    def close(self):
        self.closed=True;self.bindings=self.status=None
        self._catalog_policy=self._catalog_identity=self._catalog_state=None

class Feature:
    actual_cast_enabled=False # Cold source-ready local producer enables its instance; original actor proof remains separate.
    def __init__(self,broker,*,provider,legacy_bindings,admission,source_adapter,clock,source_root):
        need((isinstance(admission,SourceCastAdmission) or type(admission) is LocalBackendSelfAdmission)
             and callable(clock),'CAST_TRUSTED_SOURCE_ADMISSION_AND_CLOCK_REQUIRED')
        need(type(legacy_bindings) is CanonicalSelectedBindings
             and provider.broker is broker and legacy_bindings.broker is broker,
             'CAST_SAME_EXISTING_PROVIDER_BINDINGS_REQUIRED')
        if type(admission) is LocalBackendSelfAdmission:
            need(admission.bindings is legacy_bindings and admission.status is legacy_bindings.status
                 and admission.root==Path(source_root),'CAST_LOCAL_SELF_SAME_FEATURE_SOURCE_REQUIRED')
        self.broker,self.provider,self.legacy=broker,provider,legacy_bindings
        self.admission,self.source_adapter,self.clock=admission,source_adapter,clock
        self.codec=wire.Codec(source_root)
        self.attached=self.closed=False
        self.headers={};self.pending={}

    def attach(self):
        from tools.local_original_session.broker import PersistentBroker
        from tools.local_original_session.canonical_batch import BrokerProvider
        b=self.broker
        need(type(self) is Feature and type(b) is PersistentBroker and type(self.provider) is BrokerProvider
             and b._canonical_provider is self.provider and not b._started and not b._closing
             and not b.realm.registry._sessions and not self.attached and not self.closed
             and getattr(b,'_cast_feature',None) is None
             and getattr(b.policy,'_cast_feature',None) is None
             and getattr(b.realm,'_cast_feature',None) is None,'CAST_EXACT_UNSTARTED_RUNTIME_ATTACH_REQUIRED')
        self.codec.source_ready()
        b._cast_feature=b.realm._cast_feature=b.policy._cast_feature=self
        self.attached=True

    def _live(self):
        need(self.attached and not self.closed and self.broker._cast_feature is self
             and self.broker.policy._cast_feature is self and self.broker.realm._cast_feature is self,
             'CAST_CURRENT_ATTACHED_FEATURE_REQUIRED')

    def header_locked(self,writer,policy,opcode,size):
        self._live();self.codec.source_ready()
        need(type(opcode) is int and opcode==OPCODE and type(size) is int
             and 10<=size<=wire.MAX_FRAME,'CAST_NARROW_SOURCE_FRAME_BOUND')
        binding=self.provider.bind_selected(writer)
        row=binding.generation.row
        need(row['policy_row'] is policy and type(policy.received) is int
             and 0<=policy.received<MAX_COUNTER
             and id(writer) not in self.headers and id(writer) not in self.pending,
             'CAST_EXACT_QUIESCENT_INPUT_ORDINAL_REQUIRED')
        self.provider.current(binding)
        self.legacy.selected_locked(binding)
        self.headers[id(writer)]=(binding,policy,policy.received,size)

    def received_locked(self,writer,row,frame):
        self._live()
        from tools.local_entry_server.codecs import Frame
        header=self.headers.pop(id(writer),None)
        need(header is not None,'CAST_ORIGINAL_HEADER_REQUIRED')
        binding,policy,before,size=header
        self.provider.current(binding)
        need(type(frame) is Frame and frame.opcode==OPCODE and type(frame.payload) is bytes
             and frame.wire_length==size and len(frame.payload)<=wire.MAX_BODY
             and row is binding.generation.row and row['policy_row'] is policy
             and policy.received==before+1 and id(writer) not in self.pending,
             'CAST_EXACT_ACCEPTED_SOURCE_FRAME_REQUIRED')
        key='CAST:'+binding.generation_key+':'+str(policy.received)
        need(len(key)<=128,'CAST_EXISTING_GENERATION_ORDINAL_BOUND')
        self.pending[id(writer)]=InputOperation(binding,row,policy,frame.payload,frame.wire_length,policy.received,key)

    def _current(self,operation):
        self._live();binding=operation.binding
        need(self.pending.get(id(binding.writer)) is operation
             and operation.row is binding.generation.row
             and operation.row['policy_row'] is operation.policy
             and operation.policy.received==operation.received_ordinal,
             'CAST_CURRENT_ORIGINAL_INPUT_OPERATION_REQUIRED')
        self.provider.current(binding)

    def _decode_local_locked(self,writer,payload):
        # This explicit local policy accepts the source schema's optional child
        # and coordinate absence. Neither is original-input/self proof. Keep
        # original SourceCastAdmission's normal-source-shape decoder unchanged.
        bound=self.legacy.bound.get(id(writer))
        need(bound is not None and bound[0].writer is writer,'CAST_LOCAL_SELF_SELECTED_ROUTE_REQUIRED')
        selected=bound[0]
        self.legacy.current(selected)
        request=self.codec.parse_payload(payload)
        self.legacy.current(selected)
        return wire.ReceivedCast(selected,request)

    async def dispatch_locked(self,writer,payload):
        operation=self.pending.get(id(writer))
        need(operation is not None and payload is operation.payload,'CAST_ROUTE_EXACT_RECEIVED_PAYLOAD_REQUIRED')
        plan=None
        try:
            self._current(operation)
            if type(self.admission) is LocalBackendSelfAdmission:
                decoded=self._decode_local_locked(writer,payload)
            else:
                decoded=wire.decode_locked(self.legacy,writer,opcode=OPCODE,payload=payload,codec=self.codec)
            self._current(operation)
            decision=self.admission.admit(operation,decoded)
            self._current(operation)
            if isinstance(self.admission,SourceCastAdmission):
                need(type(decision) is AdmittedCast and all(v is not None for v in
                     (decision.original_input_owner,decision.original_actor_owner,decision.source_epoch)),
                     'CAST_SOURCE_ACTOR_INPUT_EPOCH_PROOF_REQUIRED')
            else:
                need(type(self.admission) is LocalBackendSelfAdmission and type(decision) is LocalSelfDecision,
                     'CAST_EXACT_LOCAL_SELF_DECISION_REQUIRED')
            need(self.admission.current(operation,decoded,decision) is None,
                 'CAST_SOURCE_CURRENT_MUST_RAISE_NOT_BOOLEAN' if type(decision) is AdmittedCast
                 else 'CAST_LOCAL_SELF_CURRENT_MUST_RAISE_NOT_BOOLEAN')
            need(type(decision.spell_id) is int and 0<decision.spell_id<(1<<31)
                 and decision.spell_id==decoded.request.signed_lookup_key,
                 'CAST_EXACT_POSITIVE_SOURCE_LOOKUP_KEY_REQUIRED')
            owner=self.broker._hp_resource_owner
            need(owner is not None and owner.provider is self.provider
                 and owner.status.current(writer) is decision.snapshot,'CAST_CURRENT_ACCEPTED_STATUS_REQUIRED')
            # One admitted operation samples its accepted clock exactly once.
            # Expiry, cooldown/cost plan and response use that SAME value.
            now=self.clock()
            need(type(now) is int and 0<=now<(1<<53),'CAST_SERVER_ACCEPTED_CLOCK_REQUIRED')
            self._current(operation)
            need(self.admission.current(operation,decoded,decision)is None,
                 'CAST_SOURCE_CURRENT_MUST_RAISE_NOT_BOOLEAN')
            need(owner.status.current(writer)is decision.snapshot,'CAST_ADMITTED_STATUS_CHANGED_AFTER_CLOCK')
            buffs=getattr(self.broker,'_buff_lifecycle',None)
            if buffs is not None:
                await buffs.lifecycle_locked(operation.binding,now_ms=now)
                self._current(operation)
                need(owner.status.current(writer)is decision.snapshot,'CAST_STATUS_CHANGED_DURING_BUFF_EXPIRY')
            self._current(operation)
            need(self.admission.current(operation,decoded,decision) is None,
                 'CAST_SOURCE_CURRENT_MUST_RAISE_NOT_BOOLEAN' if type(decision) is AdmittedCast
                 else 'CAST_LOCAL_SELF_CURRENT_MUST_RAISE_NOT_BOOLEAN')
            need(owner.status.current(writer) is decision.snapshot,
                 'CAST_ADMITTED_STATUS_CHANGED_AFTER_SOURCE_CALLBACK')
            plan=owner.plan_cast_locked(operation.binding,txid=operation.txid,request=payload,
                spell_id=decision.spell_id,target_uid=decision.target_uid,now_ms=now)
            # The semantic/response caller itself preflights BEFORE aggregate prepare.
            need(type(plan) is not dict,'CAST_HISTORICAL_RECEIPT_HAS_NO_NEW_SEND_AUTHORITY')
            need(plan.operation.snapshot is decision.snapshot, 'CAST_PLANNED_ADMITTED_STATUS_MISMATCH')
            receipt=await self.broker.cast_skill_locked(operation.binding,plan,
                source_adapter=self.source_adapter,legacy_bindings=self.legacy)
            observer=getattr(self.broker,'_spell_whole_observer',None)
            if observer is not None:
                try:observer.cast_result_locked(operation,receipt=receipt)
                except BaseException:pass # Observation cannot turn successful original cast into a new gate.
            return () # Existing sender owns all frames; no guessed ACK.
        except BaseException as error:
            observer=getattr(self.broker,'_spell_whole_observer',None)
            if observer is not None:
                try:observer.cast_result_locked(operation,error=error)
                except BaseException:pass # Preserve the original failure/cancellation object.
            buffs=getattr(self.broker,'_buff_lifecycle',None)
            if buffs is not None and plan is not None and type(plan)is not dict and plan.phase=='COMMITTED':
                buffs.blocked[id(writer)]=operation.binding.generation
            raise
        finally:
            if self.pending.get(id(writer)) is operation:self.pending.pop(id(writer))
            owner=getattr(self.broker,'_hp_resource_owner',None)
            if plan is not None and type(plan) is not dict and plan.phase=='PLANNED' and owner is not None \
                    and owner._prepared_operation is plan.operation:
                owner.discard_cast_plan(plan)

    def retire_writer(self,writer):
        self.headers.pop(id(writer),None);self.pending.pop(id(writer),None)
        self.legacy.retire_writer(writer)

    def close(self):
        if self.closed:return
        self.closed=True;self.attached=False;self.actual_cast_enabled=False
        self.headers.clear();self.pending.clear()
        b=self.broker
        for obj in (b,b.realm,b.policy):
            if getattr(obj,'_cast_feature',None) is self:obj._cast_feature=None
        self.legacy.close()
        if type(self.admission) is LocalBackendSelfAdmission:self.admission.close()
        self.broker=self.provider=self.legacy=self.admission=self.source_adapter=self.clock=None
