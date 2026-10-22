"""Concrete source-schema Buff response adapter; no sender or local timer.

Removal has no f3/time dependency. Active responses require a separately proven
ordinary clock contract; no guessed ms/seconds encoding or valid-proof flag.
"""
from abc import ABC,abstractmethod
from dataclasses import dataclass,field
import hashlib
import importlib.util
import marshal
import math
import struct
from pathlib import Path
import sys
import types
import weakref


def need(value,code):
    if not value:raise ValueError(code)


def load_optional():
    root=next(p for p in Path(__file__).resolve().parents if (p/'tools/local_original_session/launcher.py').is_file())
    path=root/'work/local_original_session/implementation-3/skill-buff/buff-wire/optional-enum-v3/optional_enum.py'
    need(hashlib.sha256(path.read_bytes()).hexdigest()==
         '9d3cc09e3d147161d713de7c8320611700045a5ff6969ed4f80298b7f3681a72','BUFF_RESPONSE_OPTIONAL_CODEC_CHANGED')
    name='_skill_buff_optional_enum_v3'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module;spec.loader.exec_module(module)
    return sys.modules[name]


optional=load_optional()
base=optional.base
delivery=optional.retirement.delivery
METADATA_SHA='b79b28435eccd5dc7cc093f197c94fe52314259cb0d99ae555fa7763db6a0454'
ACTIONS={'buff_add':1,'buff_refresh':2,'buff_restore':1,'buff_remove':3}
FACT_PINS={
    'work/local_server_rea_20261016/run115_buff_self_instance_time/main-review.json':
        '5bea52822854b59db0e64b4a5c14fbf1326b606abee10dd107889bd3005e4289',
    'work/local_server_rea_20261016/run115_buff_self_instance_time/worker/packet.json':
        'f0e226c401f4569b66db3bc4cb28d06935a39ea7f41b160d113298e5dd09d3d3',
    'work/local_server_rea_20261016/run118_buff_key_numeric_use/worker/packet.json':
        '9868951b28102e59ec0bf82d927983aac7afabb9f864a9113159acf10b2e846c',
}
TIME_PINS={
    'work/local_server_rea_20261016/run119_buff_delta_normal_caller/main-review.json':
        '47726e5ded68d67665827f587b452897c6e8a482d7a23d67aa80ba3e4c8eb54a',
    'work/local_server_rea_20261016/run119_buff_delta_normal_caller/worker/packet.json':
        'ca4e724a79a8e9779c98ba573fe50de6df741e15409d909ab16c12eff535a9d7',
}
LOCAL_SECONDS_POLICY='LOCAL_WALL_MS_TO_SIMULATION_SECONDS_CEIL_V1'


class OriginalClockContract(ABC):
    """Root-configured source capability, never a client or arbitrary callback.

    Only the concrete SimulationSecondsClock is admitted in this version.
    source_ready verifies the accepted ordinary frame/delta unit evidence;
    encode_remaining consumes only the frozen SourceEvent, samples no new clock;
    current is pure immutable provenance validation safe in pending transport.
    Returning None is interface convention, not a minted proof of source units.
    """
    @abstractmethod
    def source_ready(self):...
    @abstractmethod
    def encode_remaining(self,event):...
    @abstractmethod
    def current(self,event,signed_units):...


class UnknownOriginalClock(OriginalClockContract):
    def source_ready(self):raise ValueError('BUFF_ORDINARY_CLOCK_SOURCE_MAPPING_UNRESOLVED')
    def encode_remaining(self,event):raise ValueError('BUFF_ORDINARY_CLOCK_SOURCE_MAPPING_UNRESOLVED')
    def current(self,event,signed_units):raise ValueError('BUFF_ORDINARY_CLOCK_SOURCE_MAPPING_UNRESOLVED')


@dataclass(frozen=True)
class SimulationSecondsClock(OriginalClockContract):
    """Accepted original simsecond unit + explicit backend ceil conversion.

    This does not identify live IAT/DLL/timescale or assert walltime1:1. Server
    expiry remains a local wall-ms deadline followed by explicit removal3.
    """
    root:Path
    policy:str
    _pins:tuple=field(init=False,repr=False)

    def __post_init__(self):
        object.__setattr__(self,'root',Path(self.root))
        object.__setattr__(self,'_pins',tuple(sorted(TIME_PINS.items())))
        need(self.root.is_absolute()and self.policy==LOCAL_SECONDS_POLICY,'BUFF_RESPONSE_EXPLICIT_SIMSECOND_POLICY_REQUIRED')
        self.source_ready()

    def source_ready(self):
        need(self.policy==LOCAL_SECONDS_POLICY and self._pins==tuple(sorted(TIME_PINS.items())),
             'BUFF_RESPONSE_SIMSECOND_SOURCE_POLICY_CHANGED')
        for relative,sha in self._pins:
            try:
                with (self.root/relative).open('rb')as stream:raw=stream.read(1048577)
            except OSError:raise ValueError('BUFF_RESPONSE_SIMSECOND_SOURCE_UNAVAILABLE')from None
            need(0<len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==sha,
                 'BUFF_RESPONSE_SIMSECOND_SOURCE_CHANGED')

    @staticmethod
    def _units(event):
        need(all(type(v)is int and 0<=v<(1<<53)for v in (event.expires_ms,event.accepted_now_ms)),
             'BUFF_RESPONSE_LOCAL_EVENT_MS_REQUIRED')
        remaining=event.expires_ms-event.accepted_now_ms
        need(remaining>0,'BUFF_RESPONSE_ACTIVE_EVENT_EXPIRED')
        units=(remaining+999)//1000 # Explicit local policy, no new clock sample.
        need(0<units<=0x7fffffff,'BUFF_RESPONSE_SIMSECONDS_INT32_OVERFLOW')
        rounded=struct.unpack('<f',struct.pack('<f',float(units)))[0]
        # Conservative local encoder subset: do not silently alter the chosen
        # integer seconds at the original signed32→F32 consumer boundary.
        need(math.isfinite(rounded)and rounded>0 and rounded==units,
             'BUFF_RESPONSE_SIMSECONDS_FLOAT32_INEXACT')
        return units

    def encode_remaining(self,event):
        self.source_ready()
        return self._units(event)

    def current(self,event,signed_units):
        need(self.policy==LOCAL_SECONDS_POLICY and self._pins==tuple(sorted(TIME_PINS.items()))
             and type(signed_units)is int and signed_units==self._units(event),
             'BUFF_RESPONSE_SIMSECOND_IMMUTABLE_WITNESS_CHANGED')


def code_digest(code):
    constants=tuple(code_digest(c) if isinstance(c,types.CodeType) else c for c in code.co_consts)
    normalized=code.replace(co_filename='<pinned-source>',co_firstlineno=1,co_linetable=b'',co_consts=constants)
    return hashlib.sha256(marshal.dumps(normalized)).hexdigest()


@dataclass(frozen=True)
class Record:
    prepared_ref:object
    plan_ref:object
    request_sha:str
    event:object
    action:int
    fields:tuple
    signed_units:int|None
    methods:tuple
    payload:bytes
    clock:object


class SourceResponseAdapter(delivery.SourceResponseAdapter):
    """Actual issued-plan → source fields → canonical PreparedBuff capability.

    source_schema/source_module are the primary owner's exact pinned
    SkillDocument/SourceEvent, not a callback returning a fabricated descriptor.
    schema_sha256 is the root-reviewed primary checkpoint dependency, never
    request data. No store, schema, key allocation or canonical receipt writes.
    """
    def __init__(self,*,root,source_schema,source_module,schema_sha256,bindings,provider,
                 codec,allowlist,clock_contract=None,schema_source=None):
        self.root=Path(root)
        need(self.root.is_absolute(),'BUFF_RESPONSE_ABSOLUTE_ROOT_REQUIRED')
        need(type(schema_sha256)is str and len(schema_sha256)==64
             and all(c in '0123456789abcdef'for c in schema_sha256),'BUFF_RESPONSE_SCHEMA_PIN_REQUIRED')
        need(type(allowlist)is tuple and allowlist and len(set(allowlist))==len(allowlist)
             and all(type(k)is int and 0<k<1<<31 for k in allowlist),'BUFF_RESPONSE_EXPLICIT_SELF_CATALOG_REQUIRED')
        need(type(codec)is optional.OptionalCodec and (clock_contract is None or type(clock_contract)in(UnknownOriginalClock,SimulationSecondsClock)),
             'BUFF_RESPONSE_EXACT_CODEC_CLOCK_CAPABILITY_REQUIRED')
        self.schema,self.module,self.schema_sha=source_schema,source_module,schema_sha256
        self.bindings,self.provider,self.codec=bindings,provider,codec
        self.allowlist=allowlist;self.clock=clock_contract or UnknownOriginalClock()
        self._issued={};self.closed=False
        self._schema_source=schema_source;self._schema_methods=None
        self._schema_identity=(source_schema,source_module,schema_sha256,schema_source)
        self.source_ready()
        self._catalog_init()

    def source_ready(self):
        need(not self.closed,'BUFF_RESPONSE_ADAPTER_CLOSED')
        schema,module,sha,source=self._schema_identity
        need(self.schema is schema and self.module is module and self.schema_sha==sha
             and self._schema_source is source,'BUFF_RESPONSE_EXACT_SCHEMA_SOURCE_REQUIRED')
        self.codec.source_ready()
        need(type(self.schema)is self.module.SkillDocument
             and (self._schema_source is None or
                  sys.modules.get('tools.local_original_session.buff_skill_document')is self.module),
             'BUFF_RESPONSE_EXACT_SCHEMA_SOURCE_REQUIRED')
        if self._schema_methods is not None:
            self._methods_current(self._schema_methods)
            return self._schema_methods
        for relative,sha in FACT_PINS.items():
            try:raw=(self.root/relative).read_bytes()
            except OSError:raise ValueError('BUFF_RESPONSE_SOURCE_UNAVAILABLE')from None
            need(hashlib.sha256(raw).hexdigest()==sha,'BUFF_RESPONSE_SOURCE_CHANGED')
        if self._schema_source is None:
            path=self.root/'work/local_original_session/implementation-3/skill-buff/buff-lifecycle-v1/skill_document.py'
        else:
            from tools.local_original_session.canonical_feature_bootstrap import SourceModule
            source=self._schema_source
            need(type(source)is SourceModule and source.module is self.module
                 and isinstance(source.path,Path) and source.path.is_absolute()
                 and source.sha256==self.schema_sha
                 and sys.modules.get('tools.local_original_session.buff_skill_document')is self.module,
                 'BUFF_RESPONSE_EXACT_SCHEMA_SOURCE_REQUIRED')
            path=source.path
        try:raw=path.read_bytes()
        except OSError:raise ValueError('BUFF_RESPONSE_SCHEMA_SOURCE_UNAVAILABLE')from None
        need(Path(self.module.__file__).resolve()==path.resolve()
             and hashlib.sha256(raw).hexdigest()==self.schema_sha
             and type(self.schema)is self.module.SkillDocument,'BUFF_RESPONSE_EXACT_SCHEMA_SOURCE_REQUIRED')
        # Preserve actual issued-plan witness globals while checking the two
        # immediate capability methods against verified source, not a mutable
        # cached module alias or a user callback.
        compiled=compile(raw,str(path),'exec')
        cls=next(c for c in compiled.co_consts if isinstance(c,types.CodeType)and c.co_name=='SkillDocument')
        methods=[]
        for name in ('source_event','policy_current'):
            code=next(c for c in cls.co_consts if isinstance(c,types.CodeType)and c.co_name==name)
            method=getattr(self.schema,name)
            need(getattr(method,'__self__',None)is self.schema
                 and method.__func__ is getattr(self.module.SkillDocument,name)
                 and method.__func__.__globals__ is vars(self.module)
                 and code_digest(method.__func__.__code__)==code_digest(code),
                 'BUFF_RESPONSE_SOURCE_CAPABILITY_METHOD_CHANGED')
            methods.append((name,method.__func__,method.__func__.__code__))
        self._schema_methods=tuple(methods)
        return self._schema_methods

    def _methods_current(self,methods):
        for name,function,code in methods:
            method=getattr(self.schema,name)
            need(getattr(method,'__self__',None)is self.schema and method.__func__ is function
                 and function.__code__ is code and function.__globals__ is vars(self.module)
                 and getattr(self.module.SkillDocument,name)is function,
                 'BUFF_RESPONSE_SOURCE_CAPABILITY_METHOD_CHANGED')

    def _event(self,binding,plan,request,*,preparing):
        methods=self.source_ready() if preparing else None
        event=self.schema.source_event(binding,plan,request)
        need(type(event)is self.module.SourceEvent and type(event.kind)is str and event.kind in ACTIONS
             and type(event.spell_id)is int and event.spell_id in self.allowlist
             and type(event.instance_key)is int and 0<event.instance_key<=0x7fffffff
             and event.instance_key!=0x4e41,'BUFF_RESPONSE_ORDINARY_SOURCE_EVENT_REQUIRED')
        need(all(type(v)is int and 0<=v<(1<<53)for v in (event.expires_ms,event.accepted_now_ms))
             and (event.previous_expiry_ms is None or type(event.previous_expiry_ms)is int
                  and 0<=event.previous_expiry_ms<(1<<53)),'BUFF_RESPONSE_FROZEN_EVENT_CLOCK_REQUIRED')
        if preparing:need(event.spell_id in self._catalog_keys,'BUFF_RESPONSE_EXACT_SELF_CATALOG_REQUIRED')
        return event,methods

    def _catalog_init(self):
        policy=self.schema.key_policy
        self.schema.policy_current()
        if policy.name=='LOCAL_CATALOG_ICON_SELF_BUFF_KEYS_V1':
            # Already checked Catalog.configure metadata/provenance, frozen in
            # the exact selected schema policy. No second Catalog or file read.
            need(type(policy)is self.module.InstancePolicy and policy.metadata_sources
                 and {p[0]for p in policy.entries}==set(self.allowlist),
                 'BUFF_RESPONSE_EXACT_SELF_CATALOG_REQUIRED')
            self._catalog_keys=tuple(p[0]for p in policy.entries)
            return
        path=self.root/'work/local_original_session/implementation-3/skill-buff/spell_metadata.py'
        try:raw=path.read_bytes()
        except OSError:raise ValueError('BUFF_RESPONSE_METADATA_UNAVAILABLE')from None
        need(hashlib.sha256(raw).hexdigest()==METADATA_SHA,'BUFF_RESPONSE_METADATA_CHANGED')
        namespace={'__name__':'_buff_response_verified_metadata','__file__':str(path)}
        exec(compile(raw,str(path),'exec'),namespace)
        catalog=namespace['Catalog'](self.root)
        for key in self.allowlist:
            row=catalog.describe(key)['ui_rows']
            need(len(row)==1 and row[0]['class']=='generic'and row[0]['grade']==1
                 and row[0]['spell_id']==key and row[0]['named_UI_configuration']['id']==key
                 and row[0]['named_UI_configuration'].get('required',{}).get('target')=='self'
                 and 'catalyst'not in row[0]['named_UI_configuration'],'BUFF_RESPONSE_EXACT_SELF_CATALOG_REQUIRED')
        self._catalog_keys=self.allowlist

    def prepare_exact(self,binding,source_plan,request):
        need(type(request)is bytes and 0<len(request)<=32768,'BUFF_RESPONSE_EXACT_REQUEST_REQUIRED')
        event,methods=self._event(binding,source_plan,request,preparing=True)
        action=ACTIONS[event.kind];units=None
        fields=[(1,event.spell_id),(4,event.instance_key)]
        if action!=3:
            need(event.expires_ms>event.accepted_now_ms,'BUFF_RESPONSE_ACTIVE_EVENT_EXPIRED')
            need(type(self.clock)in(UnknownOriginalClock,SimulationSecondsClock),'BUFF_RESPONSE_EXACT_SOURCE_CLOCK_REQUIRED')
            need(self.clock.source_ready()is None,'BUFF_RESPONSE_CLOCK_MUST_RAISE_NOT_OVERRIDE')
            units=self.clock.encode_remaining(event)
            need(type(units)is int and 0<units<=0x7fffffff,'BUFF_RESPONSE_SOURCE_SIGNED_POSITIVE_UNITS_REQUIRED')
            need(self.clock.current(event,units)is None,'BUFF_RESPONSE_CLOCK_MUST_RAISE_NOT_OVERRIDE')
            fields.append((3,units))
        fields=tuple(sorted(fields))
        prepared=base.prepare_locked(self.bindings,binding.writer,base.Notification(action,base.Info(fields)),
            codec=self.codec,owned_provider=self.provider,operation_binding=binding)
        key=id(prepared);own=weakref.ref(self)
        def released(reference):
            adapter=own()
            if adapter is not None:
                record=adapter._issued.get(key)
                if record is not None and record.prepared_ref is reference:adapter._issued.pop(key,None)
        reference=weakref.ref(prepared,released)
        self._issued[key]=Record(reference,weakref.ref(source_plan),hashlib.sha256(request).hexdigest(),
                                 event,action,fields,units,methods,prepared.payload,self.clock if action!=3 else None)
        self.current(binding,prepared,source_plan,request)
        return prepared

    def current(self,binding,prepared,source_plan,request):
        need(not self.closed and type(prepared)is base.PreparedBuff
             and prepared.operation_binding is binding and prepared.owned_provider is self.provider,
             'BUFF_RESPONSE_EXACT_PREPARED_BINDING_REQUIRED')
        record=self._issued.get(id(prepared))
        need(record is not None and record.prepared_ref()is prepared and record.plan_ref()is source_plan
             and type(request)is bytes and hashlib.sha256(request).hexdigest()==record.request_sha,
             'BUFF_RESPONSE_EXACT_ISSUED_PREPARATION_REQUIRED')
        self._methods_current(record.methods)
        event,_=self._event(binding,source_plan,request,preparing=False)
        self._methods_current(record.methods)
        need(type(event)is type(record.event) and event==record.event
             and prepared.request==base.Notification(record.action,base.Info(record.fields))
             and prepared.payload==record.payload,'BUFF_RESPONSE_SOURCE_OR_WIRE_CHANGED')
        if record.action!=3:
            need(self.clock is record.clock and type(self.clock)is SimulationSecondsClock
                 and self.clock.current(event,record.signed_units)is None,
                 'BUFF_RESPONSE_CLOCK_MUST_RAISE_NOT_OVERRIDE')
        return None

    def close(self):
        if self.closed:return
        self.closed=True;self._issued.clear()
        self.schema=self.module=self.bindings=self.provider=self.codec=self.clock=None
        self._schema_source=self._schema_methods=self._schema_identity=self._catalog_keys=None
