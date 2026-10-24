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
        if getattr(self.provider,'_packet_port',None) is not None:
            current=self.provider.packet_current(binding)
            need(current.row is row and current.game is game and current.selection is selected
                 and current.mover is mover and current.position is position,
                 'CAST_SELECTED_SAME_PACKET_CURRENT_REQUIRED')
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
            key_policy.__post_init__() # Exact selected profile once at cold admission.
            self._catalog_state=(key_policy.name,key_policy.entries,key_policy.source_contract_sha256,
                key_policy.metadata_sources,key_policy.metadata_rows,key_policy.catalyst_recipes)
        for key in allowlist:self._metadata(key)

    def _metadata(self,key):
        need(not self.closed,'CAST_LOCAL_SELF_ADMISSION_CLOSED')
        p=self._catalog_policy
        need(p is self._catalog_identity,'CAST_EXACT_COLD_CATALOG_POLICY_CHANGED')
        if p is not None and p.name=='LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1':
            need((p.name,p.entries,p.source_contract_sha256,p.metadata_sources,p.metadata_rows,p.catalyst_recipes)==self._catalog_state,
                 'CAST_EXACT_COLD_CATALOG_POLICY_CHANGED')
            rows=tuple(r for r in p.metadata_rows if r[0]==key)
            need(len(rows)==1 and rows[0][1]in ('generic','elf'),'CAST_LOCAL_SELF_EXACT_SOURCE_ROW_REQUIRED')
            return hashlib.sha256(json.dumps((rows[0],p.metadata_sources,dict(p.catalyst_recipes).get(key)),separators=(',',':')).encode()).hexdigest()
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

LOCAL_PACKET_NPC_POLICY='EXPLICIT_LOCAL_PACKET_ISSUED_NPC_CAST_V1'

@dataclass(frozen=True)
class LocalPacketNpcDecision:
    """Local packet authority only; contains no original actor/input proof."""
    spell_id:int
    target_uid:int
    snapshot:object=field(repr=False)
    operation:InputOperation=field(repr=False)
    decoded:object=field(repr=False)
    bound:object=field(repr=False)
    packet_current:object=field(repr=False)
    namespace:object=field(repr=False)
    issuer:object=field(repr=False)
    spawn:object=field(repr=False)
    policy:str

class LocalPacketNpcAdmission:
    """Opt-in finite direct-spell target selection from THIS received 4EE6 body.

    Reuse AttackTargets.authorize/revalidate and the account NPC issuer lease.
    No AttackIntent, physical acceptance, native object or synthetic epoch.
    The configured issuer domain is below 2^31: signed target == issued UID.
    No generic low32 search, truncation or absent-target fallback is permitted.
    """
    def __init__(self,*,policy,targets,bindings,status,enabled=False,allowlist=(3,),visibility=None):
        from tools.local_original_session import attack
        need(policy==LOCAL_PACKET_NPC_POLICY and type(enabled)is bool,
             'CAST_LOCAL_PACKET_EXPLICIT_POLICY_REQUIRED')
        need(type(targets)is attack.AttackTargets and targets.packet_server is not None
             and type(bindings)is CanonicalSelectedBindings
             and targets.broker is bindings.broker and status is bindings.status
             and not targets.broker._started,
             'CAST_LOCAL_PACKET_COLD_SAME_TARGETS_SELECTED_STATUS_REQUIRED')
        from tools.local_original_session import offensive_direct_policy
        need(type(allowlist)is tuple and allowlist
             and all(type(key)is int and key in (3,5,6,9,14,15,27,33,37,44,45) for key in allowlist)
             and len(set(allowlist))==len(allowlist),
             'CAST_LOCAL_PACKET_FINITE_DIRECT_ALLOWLIST_REQUIRED')
        from tools.local_original_session.local_visibility import VisibilityGuard
        self.visibility=VisibilityGuard(visibility)
        self.allowlist=allowlist
        self._direct=offensive_direct_policy
        self.policy,self.enabled=policy,enabled
        self.targets,self.bindings,self.status=targets,bindings,status
        self.closed=False

    def _current(self,operation,decoded):
        from tools.local_original_session import attack
        need(not self.closed and self.enabled and self.policy==LOCAL_PACKET_NPC_POLICY,
             'CAST_LOCAL_PACKET_ADMISSION_DISABLED')
        need(type(operation)is InputOperation and type(decoded)is wire.ReceivedCast
             and type(decoded.request)is wire.Request and decoded.request.original_payload is operation.payload
             and decoded.selection.binding is operation.binding
             and decoded.selection.writer is operation.binding.writer
             and operation.row is operation.binding.generation.row
             and operation.row['policy_row'] is operation.policy
             and operation.policy.received==operation.received_ordinal
             and operation.row['operation_lock'] is operation.binding.operation_lock
             and operation.binding.operation_lock.locked(),
             'CAST_LOCAL_PACKET_SAME_RECEIVED_OPERATION_REQUIRED')
        self.bindings.provider.current(operation.binding)
        self.bindings.current(decoded.selection)
        decoded.request.require_normal_source_shape()
        target=decoded.request.params.target_result_i32
        need(type(decoded.request.signed_lookup_key)is int
             and decoded.request.signed_lookup_key in self.allowlist and type(target)is int
             and 0x20000000<=target<=0x2000ffff and target!=operation.binding.uid,
             'CAST_LOCAL_PACKET_DIRECT_EXPLICIT_ISSUED_TARGET_REQUIRED')
        broker=self.bindings.broker
        need(type(self.targets)is attack.AttackTargets and self.targets.broker is broker
             and broker._attack_session.targets is self.targets,
             'CAST_LOCAL_PACKET_SAME_ATTACK_TARGETS_REQUIRED')
        context=self.targets._packet_current(operation.binding.writer)
        need(context.row is operation.row and context.policy_row is operation.policy
             and context.selection is decoded.selection.selection
             and context.game is decoded.selection.game and context.mover is decoded.selection.mover
             and context.position.uid==operation.binding.uid,
             'CAST_LOCAL_PACKET_SAME_ISSUED_CURRENT_REQUIRED')
        spawn=attack.npc_recipe(broker.realm,target)
        namespace=broker.realm.uid_namespace_owner
        need(namespace is not None and namespace.setup.npc_issuer is not None
             and namespace.npc_issued_current(spawn)is True and spawn.fields[2]==target,
             'CAST_LOCAL_PACKET_CURRENT_ACCOUNT_NPC_LEASE_REQUIRED')
        snapshot=self.status.current(operation.binding.writer)
        need(snapshot.target_uid==operation.binding.uid
             and id(operation.binding.writer)not in self.status._world,
             'CAST_LOCAL_PACKET_COMPLETED_WORLD_STATUS_REQUIRED')
        return target,context,namespace,namespace.setup.npc_issuer,spawn,snapshot

    async def admit(self,operation,decoded):
        from tools.local_original_session import attack
        before=self._current(operation,decoded)
        # This creates only the shared resolver's comparison request, never a
        # received 4E30 or a physical AttackIntent/acceptance event.
        bound=await self.targets.authorize(operation.binding.writer,attack.AttackRequest(before[0]))
        after=self._current(operation,decoded)
        need(before[0]==after[0] and all(a is b for a,b in zip(before[1:],after[1:])),
             'CAST_LOCAL_PACKET_AUTHORITY_CHANGED_ACROSS_AUTHORIZE')
        target,context,namespace,issuer,spawn,snapshot=after
        decision=LocalPacketNpcDecision(decoded.request.signed_lookup_key,target,snapshot,operation,decoded,bound,
            context,namespace,issuer,spawn,self.policy)
        self.current(operation,decoded,decision)
        return decision

    def current(self,operation,decoded,decision):
        from tools.local_original_session import attack
        need(type(decision)is LocalPacketNpcDecision and decision.operation is operation
             and decision.decoded is decoded and decision.policy==LOCAL_PACKET_NPC_POLICY,
             'CAST_LOCAL_PACKET_EXACT_DECISION_REQUIRED')
        target,context,namespace,issuer,spawn,snapshot=self._current(operation,decoded)
        need(decision.spell_id==decoded.request.signed_lookup_key and decision.target_uid==target
             and decision.packet_current is context and decision.namespace is namespace
             and decision.issuer is issuer and decision.spawn is spawn and decision.snapshot is snapshot
             and type(decision.bound)is attack.BoundTarget
             and decision.bound._writer is operation.binding.writer
             and decision.bound.attacker is context.position and decision.bound.target_uid==target
             and self.targets.revalidate(decision.bound)is operation.row,
             'CAST_LOCAL_PACKET_DECISION_CURRENT_OR_BOUND_CHANGED')
        # Explicit reference single-NPC range; no LOS/status/AoE authority.
        # Current positions still come from exact shared target revalidation.
        spec=self._direct.describe(decision.spell_id)
        bound=decision.bound;position=bound.attacker
        need(bound.map_id==position.map_id
             and max(abs(bound.target_x-position.word0),abs(bound.target_y-position.word1))<=spec.ranged,
             'CAST_LOCAL_PACKET_DIRECT_RANGE_REQUIRED')
        # Exact local-visibility-v1 guard; no reference map/range substitutes.
        self.visibility.verify(operation,decoded,decision.bound,context,namespace,issuer,spawn,snapshot)
        after=self._current(operation,decoded)
        need(all(a is b for a,b in zip(after[1:],(context,namespace,issuer,spawn,snapshot)))
             and after[0]==target and self.targets.revalidate(decision.bound)is operation.row,
             'CAST_LOCAL_VISIBILITY_CURRENT_CHANGED')

    def target_bound(self,operation,decoded,decision):
        self.current(operation,decoded,decision)
        return decision.bound

    def close(self):
        self.closed=True;self.enabled=False
        self.visibility.close()
        self.targets=self.bindings=self.status=None


class Feature:
    actual_cast_enabled=False # Cold source-ready local producer enables its instance; original actor proof remains separate.
    def __init__(self,broker,*,provider,legacy_bindings,admission,source_adapter,clock,source_root):
        need((isinstance(admission,SourceCastAdmission) or type(admission) in (LocalBackendSelfAdmission,LocalPacketNpcAdmission))
             and callable(clock),'CAST_TRUSTED_SOURCE_ADMISSION_AND_CLOCK_REQUIRED')
        need(type(legacy_bindings) is CanonicalSelectedBindings
             and provider.broker is broker and legacy_bindings.broker is broker,
             'CAST_SAME_EXISTING_PROVIDER_BINDINGS_REQUIRED')
        if type(admission) is LocalBackendSelfAdmission:
            need(admission.bindings is legacy_bindings and admission.status is legacy_bindings.status
                 and admission.root==Path(source_root),'CAST_LOCAL_SELF_SAME_FEATURE_SOURCE_REQUIRED')
        if type(admission)is LocalPacketNpcAdmission:
            need(admission.bindings is legacy_bindings and admission.status is legacy_bindings.status,
                 'CAST_LOCAL_PACKET_SAME_FEATURE_SOURCE_REQUIRED')
        self.broker,self.provider,self.legacy=broker,provider,legacy_bindings
        self.admission,self.source_adapter,self.clock=admission,source_adapter,clock
        self.codec=wire.Codec(source_root)
        self.attached=self.closed=False
        self.headers={};self.pending={}
        self.hostile_admission=self._hostile_attachment=None
        self._poison_attachment=None

    def attach(self):
        from tools.local_original_session.broker import PersistentBroker
        from tools.local_original_session.canonical_batch import BrokerProvider
        b=self.broker
        need(type(self) is Feature and type(b) is PersistentBroker and type(self.provider) is BrokerProvider
             and b._canonical_provider is self.provider and not b._closing
             and ((not b._started and not b.realm.registry._sessions) or _scope_construction_current(b))
             and not self.attached and not self.closed
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

    def _decline_unimplemented_local(self,operation,decoded,buffs):
        # This is a no-effect LOCAL declaration, never target admission.
        if type(self.admission)is not LocalBackendSelfAdmission or buffs is None:return False
        schema=buffs.schema;key=decoded.request.signed_lookup_key
        if type(key)is not int or key in schema.rules or key not in schema.learnable_ids:return False
        catalog=schema.catalog_current()
        if catalog is None:return False
        need(not self.admission.closed and self.admission.policy==LOCAL_SELF_POLICY
             and self.admission.bindings is self.legacy,
             'CAST_UNIMPLEMENTED_ADMISSION_CURRENT_REQUIRED')
        catalog.metadata(key) # Exact cold catalog logical namespace only.
        self._current(operation);self.legacy.current(decoded.selection)
        need(decoded.selection.binding is operation.binding
             and decoded.selection.writer is operation.binding.writer
             and buffs.provider is self.provider,'CAST_UNIMPLEMENTED_SELECTED_SCOPE_REQUIRED')
        owner=self.broker._hp_resource_owner
        need(owner is not None and owner.provider is self.provider
             and buffs.owner is owner and schema is owner.skill_schema and buffs.store is owner.store
             and self.admission.status is owner.status,'CAST_UNIMPLEMENTED_STATUS_OWNER_REQUIRED')
        snapshot=owner.status.current(operation.binding.writer)
        need(snapshot.target_uid==operation.binding.uid
             and id(operation.binding.writer)not in owner.status._world,
             'CAST_UNIMPLEMENTED_COMPLETED_WORLD_REQUIRED')
        data=buffs.read_locked(operation.binding)
        row=data['characters'].get(str(operation.binding.uid))
        need(row is not None,'CAST_UNIMPLEMENTED_LEARNED_DOCUMENT_REQUIRED')
        learned=key in row['learned']
        self._current(operation);self.legacy.current(decoded.selection)
        need(owner.status.current(operation.binding.writer)is snapshot
             and owner._prepared_operation is None and owner._delivery_active is None
             and owner._catalyst_prepared is None,
             'CAST_UNIMPLEMENTED_PREPARATION_REQUIRED')
        error=ValueError('SKILL_CAST_NOT_IMPLEMENTED'if learned else 'SKILL_NOT_LEARNED')
        observer=getattr(self.broker,'_spell_whole_observer',None)
        if observer is not None:
            try:observer.cast_result_locked(operation,error=error)
            except BaseException:pass # Observation cannot authorize the refusal.
        return True

    async def _cancel_meditation_selfcast_locked(self,operation,decoded,buffs,now):
        """LOCAL learned SELF input cancels31 before its cast plan, not regen."""
        if type(self.admission)is not LocalBackendSelfAdmission or buffs is None:return False
        # This validates the original LOCAL metadata/target/current without
        # issuing a decision. Admission is issued once, AFTER the remove await.
        key,_,_=self.admission._current(operation,decoded)
        owner=self.broker._hp_resource_owner
        need(owner is not None and buffs.provider is self.provider and buffs.owner is owner
             and owner.skill_schema is buffs.schema and owner.store is buffs.store,
             'MEDITATION_SELFCAST_SAME_BUFF_OWNER_REQUIRED')
        data=buffs.read_locked(operation.binding)
        row=data['characters'].get(str(operation.binding.uid))
        need(row is not None,'MEDITATION_SELFCAST_CURRENT_CHARACTER_REQUIRED')
        if key not in row['learned']:return False # Original mastery-before-cancel boundary.
        expiry=row['buffs'].get('31')
        if expiry is None or expiry<=now:return False # Expiry remains the preceding routine's job.
        need(now>=row['clock'],'MEDITATION_SELFCAST_CLOCK_REVERSED')
        txid='BUFF:'+operation.binding.generation_key+':'+str(row['revision'])+':cast31'
        need(len(txid)<=128,'BUFF_EXISTING_OPERATION_ID_BOUND')
        # Lifecycle prelude is not the cast transaction: keep the original
        # request fingerprint as evidence, but never duplicate its request SHA.
        request=json.dumps(dict(policy='LOCAL_LEARNED_SELF_CAST_CANCELS_MEDITATION_V1',
            generation=operation.binding.generation_key,uid=operation.binding.uid,
            revision=row['revision'],now_ms=now,command='remove',spell_id=31,
            cast_request_sha=buffs.batch.request_digest(operation.payload),
            cast_txid=operation.txid),sort_keys=True,separators=(',',':')).encode()
        await buffs.execute_locked(operation.binding,command='remove',spell_id=31,
            txid=txid,request=request,now_ms=now)
        return True

    async def dispatch_locked(self,writer,payload):
        operation=self.pending.get(id(writer))
        need(operation is not None and payload is operation.payload,'CAST_ROUTE_EXACT_RECEIVED_PAYLOAD_REQUIRED')
        plan=None
        try:
            self._current(operation)
            if type(self.admission) in (LocalBackendSelfAdmission,LocalPacketNpcAdmission):
                decoded=self._decode_local_locked(writer,payload)
            else:
                decoded=wire.decode_locked(self.legacy,writer,opcode=OPCODE,payload=payload,codec=self.codec)
            self._current(operation)
            self.legacy.current(decoded.selection)
            # One decoded operation samples its accepted clock exactly once.
            # Expiry may install a new status Snapshot in the SAME selection.
            now=self.clock()
            need(type(now) is int and 0<=now<(1<<53),'CAST_SERVER_ACCEPTED_CLOCK_REQUIRED')
            self._current(operation)
            self.legacy.current(decoded.selection)
            buffs=getattr(self.broker,'_buff_lifecycle',None)
            if buffs is not None:
                await buffs.lifecycle_locked(operation.binding,now_ms=now)
            self._current(operation)
            self.legacy.current(decoded.selection)
            # A second explicitly selected LOCAL admission shares THIS Feature.
            # Only exact configured direct keys select it; self Buff remains intact.
            admission=self.admission
            if (self.hostile_admission is not None
                    and decoded.request.signed_lookup_key in self.hostile_admission.allowlist):
                need(type(admission)is LocalBackendSelfAdmission
                     and type(self.hostile_admission)is LocalPacketNpcAdmission,
                     'CAST_EXACT_SELF_AND_LOCAL_NPC_ADMISSIONS_REQUIRED')
                admission=self.hostile_admission
            if self._decline_unimplemented_local(operation,decoded,buffs):return ()
            if type(self.admission)is LocalBackendSelfAdmission:
                # Normal action is stricter than a positive pending life Snapshot.
                # Check once before31 removal OR any ordinary cast plan/CAS.
                life=getattr(self.broker,'_player_life',None)
                if life is not None:
                    from tools.local_original_session import player_life
                    need(type(life)is player_life.Service and life.broker is self.broker
                         and not life.closed,'CAST_LOCAL_SELF_EXACT_PLAYER_LIFE_REQUIRED')
                    life.check_normal_locked(writer)
            if self._poison_attachment is not None and decoded.request.signed_lookup_key==10:
                # The same actual decoder/operation/life check precedes this
                # default-OFF seam. Missing eligibility cannot fall through
                # into self cast, a fabricated context, cost or reply.
                await self._poison_attachment.received(operation,decoded,accepted_now_ms=now)
                raise ValueError('POISON10_RECEIVED_HANDLER_RETURNED_WITHOUT_ADMISSION')
            if admission is self.admission and await self._cancel_meditation_selfcast_locked(operation,decoded,buffs,now):
                self._current(operation)
                self.legacy.current(decoded.selection)
            decision=(await admission.admit(operation,decoded) if type(admission)is LocalPacketNpcAdmission
                      else admission.admit(operation,decoded))
            self._current(operation)
            if isinstance(admission,SourceCastAdmission):
                need(type(decision) is AdmittedCast and all(v is not None for v in
                     (decision.original_input_owner,decision.original_actor_owner,decision.source_epoch)),
                     'CAST_SOURCE_ACTOR_INPUT_EPOCH_PROOF_REQUIRED')
            elif type(admission)is LocalPacketNpcAdmission:
                need(type(decision)is LocalPacketNpcDecision,'CAST_EXACT_LOCAL_PACKET_NPC_DECISION_REQUIRED')
            else:
                need(type(admission) is LocalBackendSelfAdmission and type(decision) is LocalSelfDecision,
                     'CAST_EXACT_LOCAL_SELF_DECISION_REQUIRED')
            need(admission.current(operation,decoded,decision) is None,
                 'CAST_SOURCE_CURRENT_MUST_RAISE_NOT_BOOLEAN' if type(decision) is AdmittedCast
                 else ('CAST_LOCAL_PACKET_CURRENT_MUST_RAISE_NOT_BOOLEAN' if type(decision)is LocalPacketNpcDecision
                       else 'CAST_LOCAL_SELF_CURRENT_MUST_RAISE_NOT_BOOLEAN'))
            need(type(decision.spell_id) is int and 0<decision.spell_id<(1<<31)
                 and decision.spell_id==decoded.request.signed_lookup_key,
                 'CAST_EXACT_POSITIVE_SOURCE_LOOKUP_KEY_REQUIRED')
            owner=self.broker._hp_resource_owner
            need(owner is not None and owner.provider is self.provider
                 and owner.status.current(writer) is decision.snapshot,'CAST_CURRENT_ACCEPTED_STATUS_REQUIRED')
            self._current(operation)
            need(admission.current(operation,decoded,decision) is None,
                 'CAST_SOURCE_CURRENT_MUST_RAISE_NOT_BOOLEAN' if type(decision) is AdmittedCast
                 else ('CAST_LOCAL_PACKET_CURRENT_MUST_RAISE_NOT_BOOLEAN' if type(decision)is LocalPacketNpcDecision
                       else 'CAST_LOCAL_SELF_CURRENT_MUST_RAISE_NOT_BOOLEAN'))
            need(owner.status.current(writer) is decision.snapshot,
                 'CAST_ADMITTED_STATUS_CHANGED_AFTER_SOURCE_CALLBACK')
            try:
                hostile=getattr(owner,'_combat_hostile',None)
                if type(admission)is LocalPacketNpcAdmission:
                    need(hostile is not None and decision.spell_id in hostile.rules,
                         'CAST_LOCAL_PACKET_HOSTILE_RULE_REQUIRED')
                if hostile is not None and decision.spell_id in hostile.rules:
                    from tools.local_original_session.combat_hostile_cast import HostileCastContext,SourceNpcCastAdmission
                    need(isinstance(admission,SourceNpcCastAdmission) or type(admission)is LocalPacketNpcAdmission,
                         'HOSTILE_CAST_SOURCE_OR_EXPLICIT_LOCAL_NPC_PRODUCER_REQUIRED')
                    bound=admission.target_bound(operation,decoded,decision)
                    context=HostileCastContext(self,operation,decoded,decision,admission,bound)
                    context.current()
                    plan=owner.plan_hostile_magic_locked(context,txid=operation.txid,request=payload,now_ms=now)
                else:
                    plan=owner.plan_cast_locked(operation.binding,txid=operation.txid,request=payload,
                        spell_id=decision.spell_id,target_uid=decision.target_uid,now_ms=now)
            except ValueError as decline:
                # Explicit LOCAL behavior only: these conditions reject before
                # a computed resource operation, reservation or reply exists.
                if (type(admission)is not LocalBackendSelfAdmission or type(decline)is not ValueError
                        or decline.args not in (('SKILL_NOT_LEARNED',),('SKILL_HP_OR_DEAD',),
                            ('SKILL_MP_INSUFFICIENT',),('SKILL_COOLDOWN',),('CATALYST_INSUFFICIENT_QUANTITY',))):
                    raise
                self._current(operation)
                need(admission.current(operation,decoded,decision)is None,
                     'CAST_LOCAL_SELF_CURRENT_MUST_RAISE_NOT_BOOLEAN')
                need(self.broker._hp_resource_owner is owner and owner.provider is self.provider
                     and owner._prepared_operation is None and owner._catalyst_prepared is None
                     and owner.status.current(writer)is decision.snapshot,
                     'CAST_LOCAL_REFUSAL_UNSTAGED_CURRENT_REQUIRED')
                observer=getattr(self.broker,'_spell_whole_observer',None)
                if observer is not None:
                    try:observer.cast_result_locked(operation,error=decline)
                    except BaseException:pass # Observation is not rejection authority.
                return () # No invented refusal wire/receipt/charge/refund.
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
        if self._poison_attachment is not None:self._poison_attachment.close()
        if self._hostile_attachment is not None:self._hostile_attachment.close()
        b=self.broker
        for obj in (b,b.realm,b.policy):
            if getattr(obj,'_cast_feature',None) is self:obj._cast_feature=None
        self.legacy.close()
        if type(self.admission) in (LocalBackendSelfAdmission,LocalPacketNpcAdmission):self.admission.close()
        self.broker=self.provider=self.legacy=self.admission=self.source_adapter=self.clock=None


def _scope_construction_current(broker):
    # Source/module selection and the actual live token belong to root.
    import sys,types
    scope=sys.modules.get('character_scope')
    need(type(scope) is types.ModuleType,'SCOPE_CONSTRUCTION_SELECTED_SOURCE_REQUIRED')
    method=getattr(scope,'scope_construction_current',None)
    need(type(method) is types.FunctionType and method.__globals__ is vars(scope),
         'SCOPE_CONSTRUCTION_EXACT_SOURCE_FUNCTION_REQUIRED')
    result=method(broker)
    need(type(result) is bool,'SCOPE_CONSTRUCTION_EXACT_CURRENT_RESULT_REQUIRED')
    return result


class HostileAttachment:
    """Own only the additional hostile admission; the self Feature stays owned."""
    def __init__(self,feature,policy,admission):
        self.feature,self.policy,self.admission=feature,policy,admission
        self.closed=False

    def close(self):
        if self.closed:return
        self.closed=True
        f,p,a=self.feature,self.policy,self.admission
        if f._hostile_attachment is self:
            f._hostile_attachment=None
            if f.hostile_admission is a:f.hostile_admission=None
        if getattr(p.owner,'_combat_hostile',None)is p:p.owner._combat_hostile=None
        a.close()
        self.feature=self.policy=self.admission=None


def attach_hostile_disabled(self_feature,*,policy,admission,clock,source_adapter):
    """Cold opt-in, same Feature/selected bindings, no replacement or enabling.

    HostilePolicy must already be bound to the exact ResourceOwner. Failure
    leaves self route untouched; caller owns cleanup of its unbound inputs.
    The returned handle retires only this added admission and exact policy.
    """
    from tools.local_original_session.combat_hostile_cast import HostilePolicy
    f=self_feature
    need(type(f)is Feature and not f.closed and f.attached,
         'CAST_HOSTILE_EXISTING_SELF_FEATURE_REQUIRED')
    f._live()
    b=f.broker
    need(type(admission)is LocalPacketNpcAdmission,'CAST_HOSTILE_EXACT_PACKET_ADMISSION_REQUIRED')
    need(not b._started and not b._closing and not b.realm.registry._sessions
         and not f.headers and not f.pending
         and type(f.admission)is LocalBackendSelfAdmission
         and not f.admission.closed and f.admission.bindings is f.legacy
         and f.admission.status is f.legacy.status
         and not set(admission.allowlist).intersection(f.admission.allowlist)
         and f.hostile_admission is None and f._hostile_attachment is None,
         'CAST_HOSTILE_COLD_QUIESCENT_SELF_FEATURE_REQUIRED')
    need(type(policy)is HostilePolicy and policy.owner is b._hp_resource_owner
         and policy.owner.provider is f.provider and not policy.owner.active
         and policy.owner.status is f.legacy.status
         and getattr(policy.owner,'_combat_hostile',None)is policy
         and set(policy.rules)==set(admission.allowlist),'CAST_HOSTILE_SAME_BOUND_DIRECT_POLICY_REQUIRED')
    need(type(admission)is LocalPacketNpcAdmission and not admission.closed
         and admission.enabled is False and admission.bindings is f.legacy
         and admission.status is f.legacy.status
         and admission.targets is b._attack_session.targets
         and admission.targets.broker is b
         and clock is f.clock and source_adapter is f.source_adapter,
         'CAST_HOSTILE_DISABLED_SAME_FEATURE_ADMISSION_REQUIRED')
    from tools.local_original_session import offensive_direct_policy,combat_magic
    need(admission._direct is offensive_direct_policy,'CAST_HOSTILE_SAME_DIRECT_MODULE_REQUIRED')
    for rule in policy.rules.values():
        offensive_direct_policy.validate_hostile_rule(rule,combat_magic=combat_magic,
            core=policy.owner.core,skill_schema=policy.owner.skill_schema)
    handle=HostileAttachment(f,policy,admission)
    f.hostile_admission=admission
    f._hostile_attachment=handle
    return handle
