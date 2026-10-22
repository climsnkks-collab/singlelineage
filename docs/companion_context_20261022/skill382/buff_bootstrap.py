"""Concrete cold factory hooks; root retains one Store/Provider/Composite.
Module aliases are installed by the existing source-pinned startup loader. This
helper neither creates another store nor grants learned state or resources.
"""
from pathlib import Path
import hashlib,sys

def need(ok,code):
    if not ok:raise ValueError(code)

class BuffBootstrap:
    def __init__(self,*,root,account,rules,clock,allowlist,module_pins,clock_contract=None,initial_learned=(),key_policy=None):
        need(type(module_pins)is dict and set(module_pins)=={'buff_lifecycle','buff_skill_document','cast_route','buff_source_response'},
             'BUFF_EXPLICIT_STARTUP_MODULE_PINS_REQUIRED')
        from tools.local_original_session import buff_lifecycle,buff_skill_document,cast_route,buff_source_response
        self.modules=(buff_lifecycle,buff_skill_document,cast_route,buff_source_response)
        self.pins=dict(module_pins);self.root=Path(root);self.account=account;self.rules=rules
        self.clock=clock;self.allowlist=allowlist;self.clock_contract=clock_contract
        self.initial_learned=initial_learned
        need(type(rules)is tuple and rules and type(allowlist)is tuple and set(allowlist)=={r.spell_id for r in rules}
             and callable(clock),'BUFF_EXPLICIT_RULES_CLOCK_ALLOWLIST_REQUIRED')
        self.broker=self.service=self.feature=self.adapter=None;self.closed=False
        self.light_policy=self.light_source=self._light_binding=None
        self.learned_input_source=None
        self.book_source=self.book_delivery_source=self.book_policy=self.book_owner=None
        self.source_ready()
        doc=self.modules[1]
        self._key_policy=doc.local_self_policy(self.root,self.allowlist) if key_policy is None else key_policy
        need(type(self._key_policy)is doc.InstancePolicy
             and {p[0]for p in self._key_policy.entries}==set(self.allowlist),'BUFF_EXACT_RULESET_KEY_CONFIGURATION')
        self._key_policy_state=(self._key_policy,self._key_policy.name,self._key_policy.entries,
            self._key_policy.source_contract_sha256,self._key_policy.metadata_sources,self._key_policy.metadata_rows)
        from tools.local_original_session.canonical_feature_bootstrap import SourceModule
        self._schema_source=SourceModule(doc,Path(doc.__file__).resolve(),self.pins['buff_skill_document'])
    def bind_learned_input(self,source):
        from tools.local_original_session.canonical_feature_bootstrap import SourceModule
        need(type(source)is SourceModule and self.broker is None and self.service is None
             and not self.closed and self.learned_input_source is None,'LEARNED_EXACT_COLD_SOURCE_REQUIRED')
        module=source.check()
        need(source.path.resolve()==self.root/'work/local_original_session/integration-1/spell-host-binding-serial369-v1/learned_input.py'
             and source.sha256=='a4765d540f356823495e9ab6626f9985c8bf289b2b5c0c64de5f812b6cc4098d','LEARNED_EXACT_SOURCE_PIN_REQUIRED')
        self.learned_input_source=source
        return self
    def bind_light_policy(self,source,policy):
        from tools.local_original_session.canonical_feature_bootstrap import SourceModule
        need(type(source)is SourceModule and self.broker is None and self.service is None
             and not self.closed and self._light_binding is None,'LIGHT_COLD_SOURCE_REQUIRED')
        module=source.check()
        need(sys.modules.get('tools.local_original_session.light_state')is module
             and type(policy)is module.LightPolicy,'LIGHT_EXPLICIT_POLICY_REQUIRED')
        # Validate immutable configuration now. Original owner.bind_light_policy
        # performs policy source-file acceptance once during cold attach.
        policy.__post_init__()
        self._light_binding=(source,module,policy,module.LightPolicy,
            policy.name,policy.active_scalar,policy.provenance)
        self.light_source,self.light_policy=source,policy
        return self

    def bind_book_learning(self,source,delivery_source,*,policy=None):
        from tools.local_original_session.canonical_feature_bootstrap import SourceModule
        need(type(source)is SourceModule and type(delivery_source)is SourceModule
             and self.broker is None and self.service is None and not self.closed
             and self.book_source is None,'BOOK_EXACT_COLD_SOURCE_MODULES_REQUIRED')
        for selected,name,file in ((source,'spell_book_learning','book-empty-current-v8/book_batch.py'),
                                   (delivery_source,'spell_book_delivery','book-roster-consumer-v9/book_delivery.py')):
            module=selected.check()
            need(selected.path.resolve()==self.root/'work/local_original_session/implementation-3/skill-buff/spell-normal-learning-v1'/file
                 and sys.modules.get('tools.local_original_session.'+name)is module,
                 'BOOK_SINGLE_CANONICAL_SOURCE_GRAPH_REQUIRED')
        # None installs no learning owner, does not claim an item or grant.
        # A real source-policy object must be selected explicitly by root.
        self.book_source,self.book_delivery_source,self.book_policy=source,delivery_source,policy
        return self

    def source_ready(self):
        need(not self.closed,'BUFF_BOOTSTRAP_CLOSED')
        bound=self._light_binding
        if bound is None:
            need(self.light_source is None and self.light_policy is None,'LIGHT_COLD_POLICY_CHANGED')
        else:
            source,module,policy,cls,name,scalar,provenance=bound
            need(self.light_source is source and self.light_policy is policy
                 and source.module is module
                 and sys.modules.get('tools.local_original_session.light_state')is module
                 and module.LightPolicy is cls and type(policy)is cls
                 and (policy.name,policy.active_scalar,policy.provenance)==(name,scalar,provenance),
                 'LIGHT_COLD_POLICY_CHANGED')
            policy.__post_init__()
        if self.learned_input_source is not None:self.learned_input_source.check()
        if self.book_source is not None:
            self.book_source.check();self.book_delivery_source.check()
        for key,module in zip(('buff_lifecycle','buff_skill_document','cast_route','buff_source_response'),self.modules):
            need(sys.modules.get('tools.local_original_session.'+key)is module
                 and hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()==self.pins[key],
                 'BUFF_EXACT_STARTUP_SOURCE_GRAPH_REQUIRED')
    def skill_schema_factory(self,api,core,provider):
        self.source_ready();doc=self.modules[1]
        p=self._key_policy;bound=self._key_policy_state
        need(p is bound[0] and (p.name,p.entries,p.source_contract_sha256,p.metadata_sources,p.metadata_rows)==bound[1:],
             'BUFF_KEY_POLICY_OR_RULESET_CHANGED')
        need(all(type(r)is core.Rule for r in self.rules),'BUFF_CANONICAL_RULE_CLASS_REQUIRED')
        return doc.SkillDocument(api,core,provider,account=self.account,rules=self.rules,
            key_policy=self._key_policy)
    def participant_capability_factory(self,api):
        from tools.local_original_session import skill_buff
        return (self.skill_schema_factory(api,skill_buff,None).capability(),)
    def runtime_capability_factory(self,api,provider,schema):
        need(type(schema)is self.modules[1].SkillDocument and schema.provider is provider,'BUFF_EXACT_LIVE_DOCUMENT_REQUIRED')
        return (schema.capability(),)
    def attach(self,broker,api,store,owner,schema):
        self.source_ready()
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker)is PersistentBroker and type(store)is api.BatchStore
             and owner.store is store and store.provider is owner.provider is broker._canonical_provider
             and owner is broker._hp_resource_owner and type(schema)is self.modules[1].SkillDocument
             and schema is owner.skill_schema and self.broker is None
             and not broker._started and not broker._closing and not broker.realm.registry._sessions,
             'BUFF_EXACT_COLD_EXISTING_RUNTIME_REQUIRED')
        life,doc,route,response=self.modules
        legacy=route.CanonicalSelectedBindings(broker,owner.provider,owner.status)
        admission=route.LocalBackendSelfAdmission(self.root,policy=route.LOCAL_SELF_POLICY,
            allowlist=self.allowlist,bindings=legacy,status=owner.status,key_policy=self._key_policy)
        adapter=service=feature=book=None
        try:
            clock=self.clock_contract if self.clock_contract is not None else response.SimulationSecondsClock(root=self.root,policy=response.LOCAL_SECONDS_POLICY)
            clock.source_ready()
            adapter=response.SourceResponseAdapter(root=self.root,source_schema=schema,source_module=doc,
                schema_sha256=self.pins['buff_skill_document'],schema_source=self._schema_source,bindings=legacy,provider=owner.provider,
                codec=life.optional.OptionalCodec(self.root),allowlist=self.allowlist,clock_contract=clock)
            service=life.Service(api,owner.core,store,schema,clock=self.clock,catalog_digest=owner.catalog_digest,
                resource_owner=owner,legacy_bindings=legacy,source_adapter=adapter,source_root=self.root,
                roster_admission=admission,initial_learned=self.initial_learned)
            if self.learned_input_source is not None:
                selected=self.learned_input_source.check()
                selected.InputSelector(service) # Existing Service owns selector cleanup.
            if self._light_binding is not None:
                owner.bind_light_policy(self.light_policy,self._light_binding[1])
            broker.bind_buff_lifecycle_runtime(service)
            if self.book_source is not None and self.book_policy is not None:
                selected=self.book_source.check();self.book_delivery_source.check()
                book=selected.BookBatch(service,source_policy=self.book_policy)
                book.attach(source_path=self.book_source.path,expected_sha256=self.book_source.sha256,
                    delivery_source_path=self.book_delivery_source.path,delivery_sha256=self.book_delivery_source.sha256)
            feature=route.Feature(broker,provider=owner.provider,legacy_bindings=legacy,admission=admission,
                source_adapter=adapter,clock=self.clock,source_root=self.root)
            feature.attach()
            # Status is explicit local backend capability, never proof of the
            # unresolved original input/actor/target producer.
            feature.original_actor_target_proven=False
            try:adapter.clock.source_ready();feature.actual_cast_enabled=True
            except ValueError as error:
                if error.args!=('BUFF_ORDINARY_CLOCK_SOURCE_MAPPING_UNRESOLVED',):raise
                feature.actual_cast_enabled=False
            self.source_ready()
            self.broker,self.service,self.feature,self.adapter=broker,service,feature,adapter
            self.book_owner=book
            return service
        except BaseException as primary:
            # Every cleanup runs; never replace the original construction error.
            steps=(lambda:book.close()if book is not None else None,
                lambda:feature.close()if feature is not None else None,
                lambda:service.close()if service is not None else None,
                lambda:adapter.close()if adapter is not None else None,admission.close,legacy.close)
            for cleanup in steps:
                try:cleanup()
                except BaseException as secondary:
                    try:primary.add_note('Buff attach cleanup raised '+type(secondary).__name__)
                    except BaseException:pass
            for obj in (broker,broker.realm,broker.policy):
                try:
                    if getattr(obj,'_buff_lifecycle',None)is service:obj._buff_lifecycle=None
                    if getattr(obj,'_cast_feature',None)is feature:obj._cast_feature=None
                    if book is not None and getattr(obj,'_book_learning',None)is book:obj._book_learning=None
                except BaseException:pass
            raise
    def close(self):
        if self.closed:return
        self.closed=True
        broker,feature,service,adapter=self.broker,self.feature,self.service,self.adapter
        book=self.book_owner
        first=None
        try:
            for target in (book,feature,service,adapter):
                if target is not None:
                    try:target.close()
                    except BaseException as error:
                        if first is None:first=error
                        else:
                            try:first.add_note('Buff close cleanup raised '+type(error).__name__)
                            except BaseException:pass
        finally:
            if broker is not None:
                for obj in (broker,broker.realm,broker.policy):
                    if getattr(obj,'_buff_lifecycle',None)is service:obj._buff_lifecycle=None
                    if getattr(obj,'_cast_feature',None)is feature:obj._cast_feature=None
                    if book is not None and getattr(obj,'_book_learning',None)is book:obj._book_learning=None
            self.broker=self.feature=self.service=self.adapter=self.clock_contract=self.clock=None;self.learned_input_source=None
            self.rules=self.modules=();self.pins={};self.initial_learned=()
            self._key_policy=self._key_policy_state=self._schema_source=None
            if service is not None and service.owner is not None:
                service.owner._light_policy=service.owner._light=None
            self.light_policy=self.light_source=self._light_binding=None
            self.book_source=self.book_delivery_source=self.book_policy=self.book_owner=None
        if first is not None:raise first
