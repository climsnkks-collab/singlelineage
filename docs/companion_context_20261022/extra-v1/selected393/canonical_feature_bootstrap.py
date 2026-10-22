"""Trusted, explicit fixture bootstrap for the original exact broker classes.

JSON/client input cannot construct this capability. No migration, default
resource values, prices, participant seed or wire response is supplied here.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import ModuleType
import sys
import threading
from contextvars import ContextVar
import asyncio

_NAMESPACE_LOCK = threading.RLock()
_NAMESPACE_USERS = set()
_NAMESPACE_MODULE = None
_NAMESPACE_OWNED = False
_ATTRIBUTE_MISSING = object()
_NAMESPACE_PRIOR_ATTRIBUTE = _ATTRIBUTE_MISSING


def _acquire_namespace(owner, api):
    import tools.local_original_session as package
    global _NAMESPACE_MODULE, _NAMESPACE_OWNED, _NAMESPACE_PRIOR_ATTRIBUTE
    name = 'tools.local_original_session.canonical_batch'
    with _NAMESPACE_LOCK:
        module = sys.modules.get(name)
        attribute = getattr(package, 'canonical_batch', _ATTRIBUTE_MISSING)
        need(module is None or module is api, 'CANONICAL_CORE_NAMESPACE_CONFLICT')
        need(attribute is _ATTRIBUTE_MISSING or attribute is api,
             'CANONICAL_CORE_NAMESPACE_CONFLICT')
        need(not _NAMESPACE_USERS or _NAMESPACE_MODULE is api,
             'CANONICAL_CORE_NAMESPACE_CONFLICT')
        if not _NAMESPACE_USERS:
            _NAMESPACE_MODULE = api
            _NAMESPACE_OWNED = module is None
            _NAMESPACE_PRIOR_ATTRIBUTE = attribute
        sys.modules[name] = api
        package.canonical_batch = api
        _NAMESPACE_USERS.add(owner)


def _release_namespace(owner):
    import tools.local_original_session as package
    global _NAMESPACE_MODULE, _NAMESPACE_OWNED, _NAMESPACE_PRIOR_ATTRIBUTE
    name = 'tools.local_original_session.canonical_batch'
    with _NAMESPACE_LOCK:
        if owner not in _NAMESPACE_USERS:
            return
        _NAMESPACE_USERS.discard(owner)
        if _NAMESPACE_USERS:
            return
        if _NAMESPACE_OWNED and sys.modules.get(name) is _NAMESPACE_MODULE:
            sys.modules.pop(name)
        if getattr(package, 'canonical_batch', None) is _NAMESPACE_MODULE:
            if _NAMESPACE_PRIOR_ATTRIBUTE is _ATTRIBUTE_MISSING:
                del package.canonical_batch
            else:
                package.canonical_batch = _NAMESPACE_PRIOR_ATTRIBUTE
        _NAMESPACE_MODULE = None
        _NAMESPACE_OWNED = False
        _NAMESPACE_PRIOR_ATTRIBUTE = _ATTRIBUTE_MISSING


def need(value, code):
    if not value:
        raise ValueError(code)


def _cleanup_steps(steps, primary=None):
    """Attempt every owned cleanup; never replace the first BaseException."""
    first = primary
    for label, action in steps:
        try:
            action()
        except BaseException as error:
            if first is None:
                first = error
            elif error is not first:
                # Diagnostic only; formatting a secondary exception is itself
                # untrusted and must not become a third cleanup failure.
                try:
                    BaseException.add_note(first, 'cleanup '+label+' raised '+type(error).__name__)
                except BaseException:
                    pass
    return first


@dataclass(frozen=True)
class SourceModule:
    module: object
    path: Path
    sha256: str

    def check(self):
        need(type(self.module) is ModuleType and isinstance(self.path, Path)
             and self.path.is_absolute() and Path(self.module.__file__).resolve() == self.path.resolve()
             and type(self.sha256) is str and len(self.sha256) == 64
             and hashlib.sha256(self.path.read_bytes()).hexdigest() == self.sha256,
             'CANONICAL_BOOTSTRAP_OWNER_SOURCE_REQUIRED')
        return self.module


def _export_bindings(module):
    result = []
    for name, value in vars(module).items():
        if callable(value):
            result.append((name, value))
        if isinstance(value, type) and value.__module__ == module.__name__:
            result.extend(((name, key), item) for key, item in vars(value).items()
                          if callable(item) or isinstance(item, (property, staticmethod, classmethod)))
    return tuple(result)


class CanonicalFeatureBootstrap:
    """One broker lifetime and one shared canonical module/class/owner space.

Owner modules and participant/catalog factories are trusted server setup,
never serialized data. The caller supplies all reviewed policy objects.
"""
    def __init__(self, *, profile, fixture_root, core_path, core_sha256,
                 aggregate_source, resource_document_source, resource_owner_source,
                 status_source, skill_core_source, skill_schema_source,
                 catalog_owner_factory, participant_capability_factory,
                 skill_schema_factory, runtime_capability_factory,
                 catalog_digest, setup_uid=None, shop=None, inventory_observer_source=None,
                 original_update_sources=None, delivery_sources=None, trade=None,
                 hp_consumer_sources=None, resource_only=False, legacy_initializer=None, legacy_initializer_source=None, buff=None, full_buff_initializer=None, full_buff_initializer_source=None):
        need(isinstance(profile, Path) and profile.is_absolute()
             and isinstance(fixture_root, Path) and fixture_root.is_absolute()
             and profile.resolve().is_relative_to(fixture_root.resolve())
             and profile.is_file(), 'CANONICAL_EXPLICIT_EXISTING_FIXTURE_PROFILE_REQUIRED')
        need(type(resource_only) is bool, 'CANONICAL_RESOURCE_ONLY_EXACT_BOOL_REQUIRED')
        need(not resource_only or shop is None and trade is None
             and participant_capability_factory is None and skill_schema_factory is None
             and runtime_capability_factory is None, 'CANONICAL_RESOURCE_ONLY_NO_UNUSED_FEATURES_REQUIRED')
        need(legacy_initializer is None or resource_only, 'CANONICAL_REPEAT_INITIALIZER_ONLY_REQUIRED')
        self.resource_only = resource_only
        need(inventory_observer_source is None or type(inventory_observer_source)is SourceModule,
             'CANONICAL_EXACT_INVENTORY_OBSERVER_SOURCE_REQUIRED')
        self._inventory_observer_source=inventory_observer_source
        need(full_buff_initializer is None or (buff is not None and not resource_only and legacy_initializer is None),
             'CANONICAL_FULL_BUFF_INITIALIZER_PAIRED_ONLY_REQUIRED')
        self._full_buff_initializer = full_buff_initializer
        self._legacy_initializer = legacy_initializer
        self.profile = profile.resolve()
        self.sources = (aggregate_source, resource_document_source, resource_owner_source,
                        status_source, skill_core_source, skill_schema_source)
        need(all(type(pin) is SourceModule for pin in self.sources),
             'CANONICAL_EXACT_OWNER_SOURCE_PINS_REQUIRED')
        modules = tuple(pin.check() for pin in self.sources)
        self.aggregate, self.documents, self.owners, self.status, self.core, self.skill_schema = modules
        # Explicit source dependencies, never a serialized feature switch.
        need(original_update_sources is None or
             (type(original_update_sources) is tuple and len(original_update_sources) == 3
              and all(type(pin) is SourceModule for pin in original_update_sources)),
             'CANONICAL_EXACT_ORIGINAL_UPDATE_SOURCE_PINS_REQUIRED')
        self._original_update_sources = original_update_sources
        if original_update_sources is not None:
            modules += tuple(pin.check() for pin in original_update_sources)
            self.sources += original_update_sources
        need(delivery_sources is None or (type(delivery_sources) is tuple
             and len(delivery_sources) == 2
             and all(type(pin) is SourceModule for pin in delivery_sources)),
             'CANONICAL_EXACT_DELIVERY_SOURCE_PINS_REQUIRED')
        self._delivery_sources = delivery_sources
        if delivery_sources is not None:
            modules += tuple(pin.check() for pin in delivery_sources)
            self.sources += delivery_sources
        need(hp_consumer_sources is None or (type(hp_consumer_sources) is tuple
             and len(hp_consumer_sources) == 3
             and all(type(pin) is SourceModule for pin in hp_consumer_sources)),
             'CANONICAL_EXACT_HP_CONSUMER_SOURCE_PINS_REQUIRED')
        self._hp_consumer_sources = hp_consumer_sources
        if hp_consumer_sources is not None:
            modules += tuple(pin.check() for pin in hp_consumer_sources)
            self.sources += hp_consumer_sources
        need((legacy_initializer is None) is (legacy_initializer_source is None), 'CANONICAL_INITIALIZER_EXACT_SOURCE_REQUIRED')
        if legacy_initializer is not None:
            need(type(legacy_initializer_source) is SourceModule and resource_only
                 and type(legacy_initializer) is legacy_initializer_source.check().CanonicalLegacyInitializer,
                 'CANONICAL_INITIALIZER_EXACT_SOURCE_REQUIRED')
            modules += (legacy_initializer_source.check(),)
            self.sources += (legacy_initializer_source,)
        need((full_buff_initializer is None) is (full_buff_initializer_source is None),
             'CANONICAL_FULL_BUFF_INITIALIZER_EXACT_SOURCE_REQUIRED')
        if full_buff_initializer is not None:
            need(type(full_buff_initializer_source) is SourceModule
                 and type(full_buff_initializer) is full_buff_initializer_source.check().FullBuffInitializer,
                 'CANONICAL_FULL_BUFF_INITIALIZER_EXACT_SOURCE_REQUIRED')
            modules += (full_buff_initializer_source.check(),)
            self.sources += (full_buff_initializer_source,)
        self._exports = tuple(_export_bindings(m) for m in modules)
        need(callable(catalog_owner_factory) and (resource_only or all(callable(c) for c in (participant_capability_factory,
             skill_schema_factory, runtime_capability_factory))),
             'CANONICAL_EXPLICIT_SERVER_FACTORIES_REQUIRED')
        self._catalog_factory = catalog_owner_factory
        self._participant_factory = participant_capability_factory
        self._skill_schema_factory = skill_schema_factory
        self._runtime_capability_factory = runtime_capability_factory
        self.catalog_digest, self.setup_uid = catalog_digest, setup_uid
        need(shop is None or type(shop) is ShopProgressBootstrap,
             'CANONICAL_EXACT_SHOP_BOOTSTRAP_REQUIRED')
        self.shop = shop
        need(trade is None or (type(trade) is ShopTradeBootstrap
             and trade.shop is shop and shop is not None and delivery_sources is not None),
             'CANONICAL_EXACT_SHOP_TRADE_BOOTSTRAP_REQUIRED')
        self.trade = trade
        if buff is not None:
            from tools.local_original_session.buff_bootstrap import BuffBootstrap
            need(type(buff)is BuffBootstrap,'BUFF_EXACT_BOOTSTRAP_REQUIRED')
        self.buff=buff
        self._spell_configuration=self._spell_source=None
        self._broker = self._batch = self._document = self._owner = None
        self._composite = self._composite_close = None
        self._retired = False
        self._lifetime_lock = threading.Lock()
        self._lifetime_state = 'INITIALIZING'
        self._factory = self._config = None
        if self.shop is not None:
            self.shop.claim(self)
        try:
            self.capability = self.aggregate.AggregateReadCapability.load(
                core_path, expected_sha256=core_sha256, capability_factory=self._capabilities)
            self.api = self.capability.canonical_module
            self._read_skill = None if self.resource_only else self._skill_capability(self.capability.capabilities)
            self._lifetime_state = 'READY'
        except BaseException:
            if self.shop is not None:
                self.shop.detach()
            self._retired, self._lifetime_state = True, 'RETIRED'
            raise

    def _skill_capability(self, capabilities, schema=None):
        rows = [c for c in capabilities if c.name == 'SKILL']
        need(len(rows) == 1, 'CANONICAL_EXACT_SKILL_CAPABILITY_REQUIRED')
        cap = rows[0]
        target = getattr(cap.validate, '__self__', None)
        need(type(target) is self.skill_schema.SkillDocument
             and getattr(cap.validate, '__func__', None) is self.skill_schema.SkillDocument.validate
             and getattr(cap.validate_change, '__self__', None) is target
             and getattr(cap.validate_change, '__func__', None) is self.skill_schema.SkillDocument.validate_change
             and cap.scope == 'account' and (schema is None or target is schema),
             'CANONICAL_EXACT_SKILL_CAPABILITY_REQUIRED')
        return target

    def _capabilities(self, api):
        # Aggregate reads are schema-only. They cannot grant live write authority.
        resource = api.DocumentCapability('RESOURCE', self.documents.validate_document,
            scope='character', validate_change=self._read_only,
            validate_authority=self._read_only)
        others = () if self.resource_only else self._participant_factory(api)
        need(type(others) is tuple and all(type(c) is api.DocumentCapability for c in others)
             and all(c.name != 'RESOURCE' for c in others),
             'CANONICAL_EXACT_PARTICIPANT_CAPABILITIES_REQUIRED')
        if self.shop is not None:
            need(all(c.name != 'SHOP-QUEST' for c in others),
                 'CANONICAL_SHOP_CAPABILITY_MUST_SHARE_EARLY_OWNER')
            others += (self.shop.capability(api),)
        return (resource,) + others

    @staticmethod
    def _read_only(*args):
        raise ValueError('CANONICAL_READ_CAPABILITY_NO_WRITE_AUTHORITY')

    def _sources_current(self):
        for pin, exports in zip(self.sources, self._exports):
            module = pin.check()
            need(_export_bindings(module) == exports,
                 'CANONICAL_BOOTSTRAP_OWNER_EXPORT_CHANGED')
        need(self.capability.check() is self.api,
             'CANONICAL_BOOTSTRAP_SHARED_CLASS_SPACE_REQUIRED')
        if self.shop is not None:
            self.shop.check()
        if self.trade is not None:
            self.trade.check()

    async def append_rules_cold(self, options, *, append_source, new_buff,
                                expected_sha256, expected_participant_keys):
        """One copied-store append before any owner/Feature/listener is created.
        This old-rule plan is consumed and retired; root then records the new
        packet preimages and reopens through a fresh new-rule plan.
        """
        from tools.local_original_session.broker import PersistentBroker
        from tools.local_original_session.buff_bootstrap import BuffBootstrap
        need(type(append_source)is SourceModule and type(new_buff)is BuffBootstrap
             and new_buff is not self.buff and self.buff is not None
             and self.shop is None and self.trade is None,
             'CANONICAL_EXACT_COLD_RULE_APPEND_REQUIRED')
        if self._factory is not None:
            self.factory_current(self._factory)
            owner=options.get('retained_owner') if type(options)is dict else None
            child=None if owner is None else owner.child
            need(self._factory.reader.owner is owner and child is not None
                 and child.resumed is False and not owner.closed
                 and options.get('owner_handle')==owner.owner_handle==child.process
                 and options.get('owner_job')==owner.owner_job==child.job
                 and child.members.get(child.pid)is child and owner.key_guard() is True,
                 'CANONICAL_COLD_FACTORY_SAME_PAUSED_OWNER_REQUIRED')
        module=append_source.check()
        need(callable(getattr(module,'append_skill_rules_cold',None)),
             'CANONICAL_RULE_APPEND_SOURCE_REQUIRED')
        with self._lifetime_lock:
            need(self._lifetime_state=='READY' and self._broker is None and not self._retired,
                 'CANONICAL_BOOTSTRAP_ONE_LIFETIME_REQUIRED')
            self._lifetime_state='CREATING'
        broker=batch=None
        primary=None
        try:
            need(type(options)is dict and Path(options['store_path']).resolve()==self.profile
                 and 'inventory_aggregate_capability'not in options,
                 'CANONICAL_BOOTSTRAP_EXACT_PROFILE_REQUIRED')
            self._sources_current();_acquire_namespace(self,self.api)
            broker=PersistentBroker(**options,inventory_aggregate_capability=self.capability)
            need(type(broker)is PersistentBroker and not broker._started and not broker._closing,
                 'CANONICAL_EXACT_UNSTARTED_BROKER_REQUIRED')
            catalog=self._catalog_factory(self.api)
            provider=self.api.BrokerProvider(broker,catalog)
            resource=self.documents.ResourceDocument(provider,broker._hp_status,self.status)
            old=self._skill_schema_factory(self.api,self.core,provider)
            need(type(old)is self.skill_schema.SkillDocument and old.rules==self._read_skill.rules
                 and old.rule_hash==self._read_skill.rule_hash,
                 'CANONICAL_SAME_READ_LIVE_PARTICIPANT_SCHEMAS_REQUIRED')
            caps=self._runtime_capability_factory(self.api,provider,old)
            batch=self.api.BatchStore(provider,capabilities=(resource.capability(self.api),)+caps)
            new=new_buff.skill_schema_factory(self.api,self.core,provider)
            need(type(new)is self.skill_schema.SkillDocument,'CANONICAL_EXACT_RUNTIME_SKILL_SCHEMA_REQUIRED')
            return module.append_skill_rules_cold(batch,expected_sha256=expected_sha256,
                expected_participant_keys=expected_participant_keys,old_schema=old,new_schema=new)
        except BaseException as error:
            primary=error;raise
        finally:
            # No live/current/issued owner was installed. Attempt every original
            # cleanup even if the append or broker cleanup is ambiguous.
            try:
                if broker is not None:await broker.close()
            except BaseException as error:
                if primary is None:primary=error
                else:
                    try:primary.add_note('Cold append broker cleanup raised '+type(error).__name__)
                    except BaseException:pass
            error=_cleanup_steps((('batch.close',lambda:batch.close()if batch is not None else None),
                ('buff.close',self.buff.close),('new_buff.close',new_buff.close),
                ('npc_factory.close',self._close_npc_factory),
                ('namespace.release',lambda:_release_namespace(self)),('plan.retire',self._retire_refs)),primary)
            if primary is not None and sys.exception()is None:raise primary
            if primary is None and error is not None:raise error

    def create_broker(self, options):
        from tools.local_original_session.broker import PersistentBroker
        # Reserve this Plan once before invoking any owner/server callable or
        # constructing original resources. The short lock is never held across
        # those calls. Reentry/concurrent callers cannot own cleanup below.
        with self._lifetime_lock:
            need(self._lifetime_state == 'READY',
                 'CANONICAL_BOOTSTRAP_ONE_LIFETIME_REQUIRED')
            self._lifetime_state = 'CREATING'
        broker = batch = update_owner = composite = composite_close = None
        try:
            need(type(options) is dict and self._broker is None and not self._retired,
                 'CANONICAL_BOOTSTRAP_ONE_LIFETIME_REQUIRED')
            need(Path(options['store_path']).resolve() == self.profile
                 and 'inventory_aggregate_capability' not in options,
                 'CANONICAL_BOOTSTRAP_EXACT_PROFILE_REQUIRED')
            self._sources_current()
            _acquire_namespace(self, self.api)
            if self._config is not None and self._config.item_equipment_policy is not None:
                need(type(options.get('item_equipment_policy')) is str
                     and options['item_equipment_policy'] == self._config.item_equipment_policy
                     and type(options.get('item_equipment_first_enable')) is bool
                     and options['item_equipment_first_enable'] is self._config.item_equipment_first_enable,
                     'CANONICAL_EXACT_ORIGINAL_EQUIPMENT_CTOR_OPTIONS_REQUIRED')
            broker = PersistentBroker(**options, inventory_aggregate_capability=self.capability)
            need(type(broker) is PersistentBroker and not broker._started and not broker._closing
                 and type(broker._hp_status) is self.status.Service
                 and broker._hp_status.broker is broker,
                 'CANONICAL_EXACT_UNSTARTED_BROKER_REQUIRED')
            catalog = self._catalog_factory(self.api)
            if self.shop is not None:
                need(type(catalog) is getattr(self.api, 'ParticipantCatalogOwner', None),
                     'CANONICAL_SHOP_EXPLICIT_PARTICIPANT_CATALOG_REQUIRED')
            if self.trade is not None:
                need(catalog.resolve(('SHOP-QUEST',)).__self__ is self.trade.catalog,
                     'CANONICAL_TRADE_SAME_GUARDED_CATALOG_REQUIRED')
            provider = self.api.BrokerProvider(broker, catalog)
            document = self.documents.ResourceDocument(provider, broker._hp_status, self.status)
            skill_schema = None if self.resource_only else self._skill_schema_factory(self.api, self.core, provider)
            need(self.resource_only or type(skill_schema) is self.skill_schema.SkillDocument,
                 'CANONICAL_EXACT_RUNTIME_SKILL_SCHEMA_REQUIRED')
            others = () if self.resource_only else self._runtime_capability_factory(self.api, provider, skill_schema)
            if self.shop is not None:
                need(type(others) is tuple and all(c.name != 'SHOP-QUEST' for c in others),
                     'CANONICAL_SHOP_CAPABILITY_MUST_SHARE_EARLY_OWNER')
                others += (self.shop.capability(self.api),)
            need(type(others) is tuple and all(type(c) is self.api.DocumentCapability for c in others)
                 and all(c.name != 'RESOURCE' for c in others),
                 'CANONICAL_EXACT_LIVE_PARTICIPANT_CAPABILITIES_REQUIRED')
            if not self.resource_only:
                self._skill_capability(others, skill_schema)
            need(self.resource_only and others == () or skill_schema.account == self._read_skill.account
                 and skill_schema.rules == self._read_skill.rules
                 and skill_schema.rule_hash == self._read_skill.rule_hash
                 and {c.name for c in others} == {c.name for c in self.capability.capabilities if c.name != 'RESOURCE'},
                 'CANONICAL_SAME_READ_LIVE_PARTICIPANT_SCHEMAS_REQUIRED')
            batch = self.api.BatchStore(provider,
                capabilities=(document.capability(self.api),) + others)
            owner = self.owners.ResourceOwner(broker._hp_status, self.status, self.api,
                batch, document, core=self.core, skill_schema=skill_schema,
                catalog_digest=self.catalog_digest, setup_uid=self.setup_uid)
            broker.bind_canonical_runtime(provider)
            if self._original_update_sources is not None:
                broker_pin, store_pin, codec_pin = self._original_update_sources
                need(broker_pin.check() is sys.modules.get(PersistentBroker.__module__)
                     and broker_pin.module.PersistentBroker is PersistentBroker
                     and store_pin.check().InventoryStore is type(broker._inventory_store)
                     and codec_pin.check() is sys.modules.get('tools.local_original_session.inventory_update'),
                     'CANONICAL_ORIGINAL_UPDATE_ACTUAL_SOURCE_MODULES_REQUIRED')
                update_owner = self.api.OriginalUpdateOwner(provider, batch,
                    source_pins={'broker': broker_pin.sha256,
                                 'inventory_store': store_pin.sha256,
                                 'inventory_update': codec_pin.sha256})
                broker.bind_original_update_runtime(update_owner)
                need(broker._inventory_update_owner is update_owner
                     and batch._original_update_owner is update_owner,
                     'CANONICAL_ORIGINAL_UPDATE_SAME_OWNER_ATTACHMENT_REQUIRED')
            broker.bind_resource_runtime(owner)
            if self._delivery_sources is not None:
                composite_pin, cost_pin = self._delivery_sources
                need(cost_pin.check() is sys.modules.get('tools.local_original_session.skill_cost_delivery'),
                     'CANONICAL_DELIVERY_ACTUAL_COST_MODULE_REQUIRED')
                if self.buff is None:
                    composite = composite_pin.module.create_composite(
                        self.api,batch,provider,owner,cost_pin.module,
                        None if self.trade is None else self.trade.delivery,resource_module=self.owners)
                else:
                    self.buff.source_ready()
                    composite = composite_pin.module.create_composite(
                        self.api,batch,provider,owner,cost_pin.module,
                        None if self.trade is None else self.trade.delivery,
                        resource_module=self.owners,buff_module=self.buff.modules[0],
                        book_module=(None if getattr(self.buff,'book_policy',None) is None
                                     else self.buff.book_delivery_source.check()))
                composite_close = composite.close
                need(owner.bind_delivery_dispatcher(composite) is composite,
                     'CANONICAL_DELIVERY_EXACT_COLD_ATTACHMENT_REQUIRED')
            if self.shop is not None:
                self.shop.attach(broker, self.api, batch)
            if self.trade is not None:
                self.trade.attach(broker,self.api,batch,composite)
            if self._factory is not None and self._factory.npc_factory is not None:
                self._factory.npc_factory.bind(broker)
            need(broker._canonical_provider is provider and broker._hp_resource_owner is owner
                 and provider.source_store is broker._inventory_store
                 and owner.store is batch and batch.provider is provider
                 and batch.lock is self.api.inventory_store._lock,
                 'CANONICAL_BOOTSTRAP_SAME_OWNER_ATTACHMENT_REQUIRED')
            if self._legacy_initializer is not None:
                self._legacy_initializer.attach(self,broker,batch,skill_schema)
            if self._full_buff_initializer is not None:
                self._full_buff_initializer.attach(self,broker,batch,skill_schema)
            if self.buff is not None:self.buff.attach(broker,self.api,batch,owner,skill_schema)
            self._sources_current()
            with self._lifetime_lock:
                self._broker, self._batch = broker, batch
                self._document, self._owner = document, owner
                self._composite, self._composite_close = composite, composite_close
                self._lifetime_state = 'BOUND'
            return broker
        except BaseException as primary:
            # The caller has not received broker yet. No listener/task exists;
            # release only this owner, preserving pending and durable receipts.
            def clear_update_field():
                if (broker is not None and update_owner is not None
                        and broker._inventory_update_owner is update_owner):
                    broker._inventory_update_owner = None
            _cleanup_steps((
                ('broker.fail',lambda: broker._fail('CANONICAL_BOOTSTRAP_ATTACH_FAILED') if broker is not None else None),
                ('update_owner.close',lambda: update_owner.close() if update_owner is not None else None),
                ('update_owner.detach',clear_update_field),
                ('buff.close',lambda: self.buff.close() if self.buff is not None else None),
                ('batch.close',lambda: batch.close() if batch is not None else None),
                ('composite.close',lambda: composite_close() if composite_close is not None else None),
                ('trade.close',lambda: self.trade.close() if self.trade is not None else None),
                ('shop.detach',lambda: self.shop.detach() if self.shop is not None else None),
                ('npc_factory.close',self._close_npc_factory),
                ('namespace.release',lambda: _release_namespace(self)),
                ('plan.retire',self._retire_refs)),primary)
            raise

    def _retire_refs(self):
        if self._full_buff_initializer is not None:
            self._full_buff_initializer.detach()
        if self._legacy_initializer is not None:
            self._legacy_initializer.detach()
        with self._lifetime_lock:
            self._broker = self._document = self._owner = self._batch = None
            self._composite = self._composite_close = None
            self._factory = self._config = None
            self._spell_configuration=self._spell_source=None
            self._retired = True
            self._lifetime_state = 'RETIRED'

    def _close_npc_factory(self):
        if self._factory is not None and self._factory.npc_factory is not None:
            self._factory.npc_factory.close()

    def close(self, broker):
        with self._lifetime_lock:
            if self._lifetime_state == 'RETIRED':
                return
            need(self._lifetime_state == 'BOUND' and broker is self._broker and broker is not None
                 and broker.cleanup_complete and not broker._tasks,
                 'CANONICAL_BOOTSTRAP_JOINED_BROKER_REQUIRED')
            self._lifetime_state = 'RETIRING'
            batch = self._batch
            composite_close = self._composite_close
        incoming = sys.exception()
        error = _cleanup_steps((
            ('buff.close',lambda: self.buff.close() if self.buff is not None else None),
            ('batch.close',batch.close),
            ('composite.close',lambda: composite_close() if composite_close is not None else None),
            ('trade.close',lambda: self.trade.close() if self.trade is not None else None),
            ('shop.detach',lambda: self.shop.detach() if self.shop is not None else None),
            ('npc_factory.close',self._close_npc_factory),
            ('namespace.release',lambda: _release_namespace(self)),
            ('plan.retire',self._retire_refs)),incoming)
        if incoming is None and error is not None:
            raise error

    def factory_current(self, factory):
        need(factory is self._factory and factory.config is self._config
             and factory.config.canonical_bootstrap is self and not self._retired,
             'CANONICAL_EXACT_FACTORY_SELECTION_CHANGED')

    def bind_spell_whole(self,configuration,source):
        need(self._lifetime_state=='READY' and self._factory is None and self._broker is None
             and self._spell_configuration is None and self.buff is not None
             and not self.resource_only and self.shop is None and self.trade is None,
             'SPELL_EXACT_COLD_BUFF_SELECTION_REQUIRED')
        need(type(source)is SourceModule,'SPELL_EXACT_RUNTIME_SOURCE_REQUIRED')
        module=source.check()
        need(type(configuration)is module.Configuration,'SPELL_EXACT_CONFIGURATION_REQUIRED')
        host=configuration.validate(SourceModule,self.status.observe.ROOT)
        self._spell_configuration,self._spell_source=configuration,source
        self.sources+=(source,configuration.host_source)
        self._exports+=(_export_bindings(module),_export_bindings(host))
    def runtime_profile(self):
        return SPELL_RUNTIME_PROFILE if self._spell_configuration is not None else BUFF_RUNTIME_PROFILE

    def full_buff_configured(self,factory):
        self.factory_current(factory)
        from tools.local_original_session import launcher
        from tools.local_original_session.buff_bootstrap import BuffBootstrap
        spec=launcher.PRODUCTS.get(self.runtime_profile())
        book_use_policy = None
        if _book_use_selected(self.buff):
            from tools.local_original_session.item_use_session import POLICY as book_use_policy
        need(factory.product==self.runtime_profile() and type(self.buff)is BuffBootstrap
             and not self.resource_only and self.shop is None and self.trade is None
             and self._config.item_use_policy == book_use_policy
             and (self._config.item_equipment_policy is None
                  or _equipment_options_selected(self.buff, self.trade, self._config))
             and not self._config.spawns and type(spec)is dict and spec.get('skill_buff_runtime')is True
             and spec.get('native_spell_input_enabled')is (self._spell_configuration is not None)
             and all(spec.get(k)is False for k in ('continuous_manual_move','continuous_manual_attack',
                 'manual_attack_move_replacement','manual_use_item','item_transfer_ui','player_life_repeat')),
             'CANONICAL_FULL_BUFF_RUNTIME_CONFIGURATION_CHANGED')
        if self._spell_configuration is not None:
            module=self._spell_source.check()
            need(spec['bridges'].get('own-login-bridge-dg49.dll')==module.DLL_SHA
                 and spec.get('bridge_artifact')==self.status.observe.ROOT/module.DLL_REL,
                 'SPELL_EXACT_NATIVE_DESCRIPTOR_REQUIRED')
        self.buff.source_ready()
        expected=((1,4,0,7200000),(2,2,0,1200000))
        if self.buff.allowlist in ((1,2,31,51,53),(1,2,31,51,53,128,147,149,150,162,165,167)):
            expected+=((31,10,40,600000),(51,15,0,64000),(53,60,0,2400000))
        if self.buff.allowlist==(1,2,31,51,53,128,147,149,150,162,165,167):
            expected+=((128,10,0,1200000),(147,20,0,1200000),(149,20,0,1200000),
                       (150,15,0,1200000),(162,30,0,1200000),(165,30,0,1200000),(167,30,0,1200000))
        need(self.buff.allowlist==tuple(r[0]for r in expected) and type(self.buff.rules)is tuple
             and all(type(r)is self.core.Rule for r in self.buff.rules)
             and tuple((r.spell_id,r.mp_cost,r.hp_cost,r.duration_ms)for r in self.buff.rules)==expected,
             'CANONICAL_PRODUCTION_BUFF_RULES_REQUIRED')
        return True

    def factory_options(self, factory):
        self.factory_current(factory)
        c = self._config
        result = dict(inventory_policy=c.inventory_policy, inventory_frame=c.inventory_frame,
            inventory_reader=factory.reader, inventory_store_policy=c.inventory_store_policy,
            inventory_collection_policy=c.inventory_collection_policy,
            inventory_collection_grant=c.inventory_collection_grant,
            inventory_reselection_policy=c.inventory_reselection_policy,
            inventory_delivery_policy=c.inventory_delivery_policy,
            inventory_custody_policy=c.inventory_custody_policy,
            restart_policy=c.restart_policy, hp_status_policy=c.hp_status_policy)
        if self._original_update_sources is not None:
            result['inventory_update_policy'] = c.inventory_update_policy
        if self.trade is not None or _book_use_selected(self.buff):
            result['item_use_policy'] = c.item_use_policy
        if _equipment_options_selected(self.buff, self.trade, c):
            result.update(item_equipment_policy=c.item_equipment_policy,
                          item_equipment_first_enable=c.item_equipment_first_enable)
        if self.shop is not None or self.resource_only:
            result.update(npc_spawns=c.spawns, attack_policy=c.attack_policy,
                attack_reader=factory.reader, attack_hp_provider=c.attack_hp_provider,
                attack_feedback=c.attack_feedback, npc_death_policy=c.npc_death_policy,
                npc_remove_policy=c.npc_remove_policy)
        if factory.npc_factory is not None:
            result.update(factory.npc_factory.broker_options())
            result['npc_player_hit_repeated_policy'] = c.npc_player_hit_repeated_policy
            result['player_life_policy'] = c.player_life_policy
        return result


class ShopProgressBootstrap:
    """Source-pinned official progress composition, no transaction/dialogue wire."""
    dialogue_enabled = False

    def __init__(self, *, core_source, port_source, bindings_source, events_source,
                 composer_source, kill_source, catalog, objectives, max_writers):
        self.sources = (core_source, port_source, bindings_source, events_source, composer_source, kill_source)
        need(all(type(pin) is SourceModule for pin in self.sources), 'SHOP_EXACT_SOURCE_PINS_REQUIRED')
        self.core, self.ports, self.bindings, self.events, self.composer, self.kill = tuple(p.check() for p in self.sources)
        self._exports = tuple(_export_bindings(p.module) for p in self.sources)
        need(self.ports.core is self.core and self.bindings.core is self.core
             and self.events.core is self.core and self.composer.core is self.core
             and self.composer.canonical_port is self.ports
             and self.composer.shop_quest_binding is self.bindings
             and self.composer.server_death_event is self.events
             and type(catalog) is self.core.Catalog and type(objectives) is tuple
             and all(type(o) is self.events.Objective for o in objectives),
             'SHOP_SINGLE_NOMINAL_SOURCE_CLASS_SPACE_REQUIRED')
        self.catalog, self.objectives, self.max_writers = catalog, objectives, max_writers
        self.owner = self.ports.ParticipantOwner(catalog)
        self._api = self._capability = self._runtime = self._broker = None
        self._plan_lock = threading.Lock()
        self._plan = None
        self._plan_state = 'READY'
        self._active = ContextVar('canonical_shop_current_binding', default=None)

    def claim(self, plan):
        with self._plan_lock:
            need(type(plan) is CanonicalFeatureBootstrap and self._plan_state == 'READY',
                 'SHOP_EARLY_OWNER_ONE_PLAN_REQUIRED')
            self._plan, self._plan_state = plan, 'CLAIMED'

    def check(self):
        for pin, exports in zip(self.sources, self._exports):
            need(_export_bindings(pin.check()) == exports, 'SHOP_BOOTSTRAP_SOURCE_CHANGED')
        need(self.owner.catalog is self.catalog, 'SHOP_BOOTSTRAP_CATALOG_IDENTITY_CHANGED')

    def capability(self, api):
        self.check()
        if self._capability is None:
            self._api, self._capability = api, self.owner.capability(api)
        need(self._api is api and type(self._capability) is api.DocumentCapability
             and getattr(self._capability.validate_change, '__self__', None) is self.owner
             and getattr(self._capability.validate_change, '__func__', None) is self.ports.ParticipantOwner.validate_change,
             'SHOP_SAME_EARLY_PARTICIPANT_CAPABILITY_REQUIRED')
        return self._capability

    def active_binding(self, selection):
        current = self._active.get()
        need(type(current) is tuple and len(current) == 3
             and current[1] == threading.get_ident() and current[2] is asyncio.current_task(),
             'SHOP_EXACT_OPERATION_BINDING_REQUIRED')
        binding = current[0]
        need(type(binding) is self._api.Binding and binding.writer is selection.writer,
             'SHOP_EXACT_OPERATION_BINDING_REQUIRED')
        # The consumer validates current/pending authority. This getter never
        # rebinds, adopts a lock or upgrades a captured Binding.
        return binding

    def attach(self, broker, api, batch):
        self.check()
        need(self._runtime is None and self._broker is None
             and batch.capabilities.get('SHOP-QUEST') is self.capability(api)
             and not broker._started and not broker._closing,
             'SHOP_COLD_SAME_BATCH_ATTACHMENT_REQUIRED')
        runtime = self.composer.build_progress_runtime(broker, self.catalog, api,
            batch, self.owner, self._capability, active_binding=self.active_binding,
            objectives=self.objectives, max_writers=self.max_writers, kill_api=self.kill)
        endpoints = dict(_shop_quest_selected_locked=self.selected_locked,
            _shop_quest_after_attack_locked=self.after_attack_locked,
            _shop_quest_retire_writer=self.retire, _shop_quest_close=self.close)
        need(all(getattr(broker.realm, name, None) is None for name in endpoints),
             'SHOP_EXISTING_HOOK_OWNER_REFUSED')
        self._broker, self._runtime = broker, runtime
        for name, endpoint in endpoints.items():
            setattr(broker.realm, name, endpoint)

    def selected_locked(self, binding):
        self._runtime.store.provider.current(binding)
        token = self._active.set((binding, threading.get_ident(), asyncio.current_task()))
        try:
            return self._runtime.bindings.selected_locked(binding)
        finally:
            self._active.reset(token)

    async def after_attack_locked(self, binding, service, accepted_before):
        self._runtime.store.provider.current(binding)
        token = self._active.set((binding, threading.get_ident(), asyncio.current_task()))
        try:
            return await self._runtime.bindings.after_attack_locked(binding, service, accepted_before)
        finally:
            self._active.reset(token)

    def retire(self, writer):
        self._runtime.bindings.retire(writer)

    def close(self):
        if self._runtime is not None:
            self._runtime.bindings.close()

    def detach(self):
        try:
            self.close()
        finally:
            if self._broker is not None:
                for name in ('_shop_quest_selected_locked', '_shop_quest_after_attack_locked',
                             '_shop_quest_retire_writer', '_shop_quest_close'):
                    if getattr(getattr(self._broker.realm, name, None), '__self__', None) is self:
                        setattr(self._broker.realm, name, None)
            self._runtime = self._broker = None
            with self._plan_lock:
                self._plan = None
                self._plan_state = 'RETIRED'


class ShopTradeBootstrap:
    """Explicit source listing/terms, original received route and typed delivery."""
    def __init__(self, *, shop, ingress_source, delivery_source, projection_source,
                 wire_source, current_listing, current_terms, current_source_memory,
                 broker_source):
        need(type(shop) is ShopProgressBootstrap
             and all(type(p) is SourceModule for p in (ingress_source,delivery_source,
                 projection_source,wire_source,broker_source))
             and all(callable(c) and not asyncio.iscoroutinefunction(c) for c in
                 (current_listing,current_terms,current_source_memory)),
             'SHOP_TRADE_EXPLICIT_SOURCE_DEPENDENCIES_REQUIRED')
        self.shop = shop
        self.sources = (ingress_source,delivery_source,projection_source,wire_source,broker_source)
        self.ingress,self.delivery,self.projection,self.wire,self.broker_module = tuple(p.check() for p in self.sources)
        self._exports = tuple(_export_bindings(p.module) for p in self.sources)
        need(self.ingress.core is shop.core and self.ingress.canonical_port is shop.ports
             and self.ingress.trade_delivery is self.delivery and self.delivery.projection is self.projection
             and self.ingress.wire is self.wire,
             'SHOP_TRADE_SINGLE_NOMINAL_SOURCE_MODULES_REQUIRED')
        self.current_listing,self.current_terms,self.current_source_memory = (
            current_listing,current_terms,current_source_memory)
        self.registry = self.ingress.RuntimeRegistry()
        self.catalog = self.feature = self.service = None
        self.closed = False

    def check(self):
        need(not self.closed, 'SHOP_TRADE_BOOTSTRAP_RETIRED')
        for pin,exports in zip(self.sources,self._exports):
            need(_export_bindings(pin.check()) == exports,'SHOP_TRADE_BOOTSTRAP_SOURCE_CHANGED')
        self.shop.check()

    def catalog_owner(self,api,base):
        self.check()
        need(self.catalog is None and isinstance(base,api.CatalogOwner),
             'SHOP_TRADE_SINGLE_GUARDED_CATALOG_REQUIRED')
        self.catalog = self.ingress.guarded_catalog_owner(api,base,self.registry)
        return self.catalog

    def attach(self,broker,api,store,composite):
        self.check()
        need(type(broker) is self.broker_module.PersistentBroker and self.feature is None
             and self.catalog is not None and self.shop._runtime is not None,
             'SHOP_TRADE_EXACT_COLD_FACTORY_RUNTIME_REQUIRED')
        runtime = self.shop._runtime
        self.feature = self.ingress.Feature(broker,runtime.bindings,api,store,self.shop.owner,
            current_listing=self.current_listing,current_terms=self.current_terms,
            registry=self.registry,stock_policy=self.ingress.STOCK,
            reuse_policy=self.ingress.LIST_REUSE,max_writers=self.shop.max_writers)
        self.service = self.delivery.Service(api,store,self.feature,composite,
            current_source_memory=self.current_source_memory,send=broker._send,
            broker_source_sha=self.sources[-1].sha256)
        self.service.attach()
        self.feature.bind_delivery(self.service)
        self.feature.attach()

    def publish_locked(self,binding,**listing):
        need(not self.closed and self.feature is not None and self.feature.attached
             and type(binding) is self.shop._api.Binding
             and self.shop._active.get() is None,
             'SHOP_TRADE_EXACT_OWNED_PUBLICATION_REQUIRED')
        provider = self.feature.store.provider
        provider.current(binding)
        token = self.shop._active.set((binding,threading.get_ident(),asyncio.current_task()))
        try:
            result = self.feature.publish_locked(binding.writer,**listing)
            provider.current(binding)
            return result
        finally:
            self.shop._active.reset(token)

    def close(self):
        if self.closed:
            return
        feature,service = self.feature,self.service
        def retire_refs():
            self.closed = True
            self.feature = self.service = self.catalog = self.registry = self.shop = None
            self.current_listing = self.current_terms = self.current_source_memory = None
        incoming = sys.exception()
        error = _cleanup_steps((
            ('feature.close',lambda: feature.close() if feature is not None else None),
            ('service.close',lambda: service.close() if service is not None else None),
            ('trade.retire',retire_refs)),incoming)
        if incoming is None and error is not None:
            raise error


def _book_use_selected(buff):
    if buff is None:
        return False
    from tools.local_original_session.buff_bootstrap import BuffBootstrap
    if type(buff) is not BuffBootstrap or buff.book_policy is None:
        return False
    buff.source_ready()
    for source, name in ((buff.book_source, 'spell_book_learning'),
                         (buff.book_delivery_source, 'spell_book_delivery')):
        need(type(source) is SourceModule
             and source.check() is sys.modules.get('tools.local_original_session.' + name),
             'BOOK_SINGLE_CANONICAL_SOURCE_GRAPH_REQUIRED')
    return True


def _equipment_options_selected(buff, trade, config):
    if config.item_equipment_policy is None:
        return False
    from tools.local_original_session.item_equipment_effect import POLICY
    allowed = trade is not None
    if not allowed and _book_use_selected(buff):
        from tools.local_original_session.item_use_session import POLICY as USE_POLICY
        allowed = type(config.item_use_policy) is str and config.item_use_policy == USE_POLICY
    need(allowed and type(config.item_equipment_policy) is str
         and config.item_equipment_policy == POLICY
         and type(config.item_equipment_first_enable) is bool,
         'CANONICAL_EXPLICIT_ORIGINAL_EQUIPMENT_OPTIONS_REQUIRED')
    return True


PROFILE = 'canonical-selected-features-v1'
BUFF_RUNTIME_PROFILE = 'sibling-background-skill-buff-spawn'
SPELL_RUNTIME_PROFILE = 'sibling-background-skill-buff-whole-entry-spawn'
BUFF_RUNTIME_PROFILES=(BUFF_RUNTIME_PROFILE,SPELL_RUNTIME_PROFILE)


def configure_factory(factory, *, reader, product, control_mode, directory, config, flags, paired_repeat=False):
    from dataclasses import fields
    from tools.local_original_session import feature_config, inventory, inventory_store, hp_status, restart
    need(type(paired_repeat) is bool,'CANONICAL_PAIRED_EXPLICIT_BOOL_REQUIRED')
    if paired_repeat:
        from tools.local_original_session.repeated_player_life_focused import configuration
        configuration(config)
    full_buff_runtime = product in BUFF_RUNTIME_PROFILES
    need(type(config) is feature_config.Features
         and type(config.canonical_bootstrap) is CanonicalFeatureBootstrap
         and product == ('sibling-background-repeated-player-life-spawn' if paired_repeat else product if full_buff_runtime else PROFILE) and control_mode == 'manual'
         and all(type(flag) is bool and flag is False for flag in flags),
         'CANONICAL_EXPLICIT_TRUSTED_FIXTURE_CONFIGURATION_REQUIRED')
    selected = config.canonical_bootstrap
    if full_buff_runtime:
        from tools.local_original_session.buff_bootstrap import BuffBootstrap
        need(not paired_repeat and not selected.resource_only and type(selected.buff) is BuffBootstrap
             and selected.shop is None and selected.trade is None, 'CANONICAL_FULL_BUFF_RUNTIME_ONLY')
        selected.buff.source_ready()
    need(not selected.resource_only or paired_repeat, 'CANONICAL_RESOURCE_ONLY_REPEAT_PROFILE_REQUIRED')
    need(selected._factory is None and not selected._retired,
         'CANONICAL_SINGLE_FACTORY_LIFETIME_REQUIRED')
    required = dict(inventory_policy=inventory.POLICY,
        inventory_store_policy=inventory_store.COLLECTION_STORE_POLICY,
        inventory_collection_policy=inventory.COLLECTION_POLICY,
        inventory_collection_grant=(inventory_store.SECOND_INSTANCE_POLICY, frozenset()),
        inventory_reselection_policy=feature_config.LOCAL_SAVED_ROW_ON_RESELECTION,
        inventory_delivery_policy=feature_config.LOCAL_WORLD_READY_ONCE,
        restart_policy=restart.POLICY, hp_status_policy=hp_status.POLICY)
    if selected._original_update_sources is not None:
        from tools.local_original_session.broker import INVENTORY_UPDATE_POLICY
        required['inventory_update_policy'] = INVENTORY_UPDATE_POLICY
    if selected.trade is not None or _book_use_selected(selected.buff):
        from tools.local_original_session.item_use_session import POLICY as ITEM_USE_POLICY
        required['item_use_policy'] = ITEM_USE_POLICY
    if _equipment_options_selected(selected.buff, selected.trade, config):
        required.update(item_equipment_policy=config.item_equipment_policy,
                        item_equipment_first_enable=config.item_equipment_first_enable)
    if selected.shop is not None:
        from tools.local_original_session import npc, npc_hp, attack_session
        need(type(config.spawns) is tuple and len(config.spawns) == 1
             and type(config.spawns[0]) is npc.NpcSpawn
             and config.attack_policy == feature_config.ATTACK_INTENT_POLICY
             and type(config.attack_hp_provider) is npc_hp.ExplicitInputs,
             'SHOP_EXPLICIT_ORIGINAL_NPC_ATTACK_HP_REQUIRED')
        spawn = config.spawns[0]
        target = npc_hp.Target(spawn.uid, spawn.map_id, spawn.fields[3], spawn.fields[39])
        need(selected.shop.objectives and all(o.target == target for o in selected.shop.objectives),
             'SHOP_OBJECTIVES_MUST_MATCH_EXPLICIT_NPC_SOURCE')
        required.update(spawns=config.spawns, attack_policy=config.attack_policy,
            attack_hp_provider=config.attack_hp_provider, attack_feedback=config.attack_feedback,
            npc_death_policy=config.npc_death_policy, npc_remove_policy=config.npc_remove_policy)
    defaults = feature_config.Features()
    if config.npc_player_hit_repeated_policy is not None:
        from tools.local_original_session import npc_player_hit,npc_motion,npc_session,player_life
        need((selected.shop is not None or paired_repeat and selected.resource_only)
             and selected._hp_consumer_sources is not None
             and tuple(pin.check() for pin in selected._hp_consumer_sources)
                 == (npc_player_hit,player_life,npc_session)
             and config.npc_player_hit_repeated_policy == npc_player_hit.REPEATED_POLICY
             and type(config.interval_ns) is int and config.interval_ns > 0
             and config.motion_policy == npc_motion.LOCAL_PRE_STEP
             and config.goal_policy == npc_session.AXIS_SIGN_GOAL
             and type(config.player_life_policy) is player_life.Policy
             and type(selected.owners.HPEffectDelivery) is type
             and type(selected.owners.HPProducerRead) is type,
             'CANONICAL_EXACT_HP_PRODUCER_DEPENDENCIES_REQUIRED')
        required.update(npc_player_hit_repeated_policy=config.npc_player_hit_repeated_policy,
            interval_ns=config.interval_ns,motion_policy=config.motion_policy,
            goal_policy=config.goal_policy,player_life_policy=config.player_life_policy)
    if paired_repeat:
        if selected.resource_only:
            need(selected.shop is None and selected.trade is None and config.item_use_policy is None
                 and config.item_equipment_policy is None, 'CANONICAL_REPEAT_UNUSED_FEATURES_DISABLED_REQUIRED')
            required.update(spawns=config.spawns,attack_policy=config.attack_policy,
                attack_hp_provider=config.attack_hp_provider,attack_feedback=config.attack_feedback,
                npc_death_policy=config.npc_death_policy,npc_remove_policy=config.npc_remove_policy)
        required['npc_player_lethal_recovery_input']=config.npc_player_lethal_recovery_input
    for field in fields(config):
        if field.name in ('canonical_bootstrap', 'inventory_frame', 'inventory_custody_policy'):
            continue
        need(getattr(config, field.name) == required.get(field.name, getattr(defaults, field.name)),
             'CANONICAL_FIXTURE_EXACT_FEATURE_OPTIONS_REQUIRED')
    need(type(config.inventory_frame) is bytes and reader is not None,
         'CANONICAL_EXISTING_FRAME_READER_REQUIRED')
    inventory.validate_frame(config.inventory_frame)
    # Constructor retains the original custody validator. No new custody policy
    # is inferred here; the explicit fixture selects the existing policy/None.
    factory.reader, factory.directory = reader, directory
    factory.config, factory.product = config, product
    factory.manual, factory.inventory, factory.npc_factory = paired_repeat or full_buff_runtime, True, None
    if config.npc_player_hit_repeated_policy is not None:
        factory.npc_factory = npc_session.NpcSessionFactory(reader,
            config=npc_session.NpcSessionConfig(spawns=config.spawns,interval_ns=config.interval_ns,
                policy=config.motion_policy,goal_policy=config.goal_policy))
    selected._factory, selected._config = factory, config
    selected.factory_current(factory)
    if full_buff_runtime:selected.full_buff_configured(factory)


class CanonicalFeatures:
    manual = None

    def __init__(self, selection, broker):
        need(type(selection) is CanonicalFeatureBootstrap and selection._broker is broker
             and broker._started and not broker._closing,
             'CANONICAL_STARTED_EXACT_RUNTIME_REQUIRED')
        self.selection, self.broker, self.closed = selection, broker, False
        self.manual=None;self.spell=None
        self.original_screenshot=None
        self.original_screenshot_observation=None
        self._screenshot_requested=False
        self._screenshot_finished=False
        self._book_equipment_enabled=False
        self._book_equipment_generation=None;self._book_equipment_attempted=False
        self.book_equipment_initial=None
        factory=selection._factory
        if factory.product in BUFF_RUNTIME_PROFILES:
            selection.full_buff_configured(factory)
            from tools.local_original_session.launcher import ManualMoveRequests,current_manual_binding
            from tools.local_original_session.manual_move_commands import ManualMoveCommands
            book_use = _book_use_selected(selection.buff)
            if book_use:
                from tools.local_original_session.item_use_session import POLICY, ItemUseSession
                use = broker._item_use_session
                need(factory.config.item_use_policy == POLICY
                     and broker._inventory_item_use_policy == POLICY
                     and type(use) is ItemUseSession and use.broker is broker
                     and broker.realm._item_use_session is use,
                     'BOOK_NATIVE_EXACT_USE_SESSION_REQUIRED')
            self._book_equipment_enabled = (book_use and
                _equipment_options_selected(selection.buff, selection.trade, factory.config))
            consumer=ManualMoveCommands(factory.reader,current=lambda:current_manual_binding(broker),
                allow_use_item=book_use)
            try:
                self.manual=ManualMoveRequests(factory.directory,consumer,allow_move=False,allow_attack=False,
                    allow_use_item=book_use,inventory_broker=broker,
                    inventory_delivery_policy=factory.config.inventory_delivery_policy,
                    inventory_reselection_policy=factory.config.inventory_reselection_policy,
                    inventory_observer_source=selection._inventory_observer_source)
                if selection._spell_configuration is not None:
                    module=selection._spell_source.check()
                    self.spell=module.Runtime(self,selection._spell_configuration,SourceModule,selection.status.observe.ROOT)
            except BaseException as primary:
                _cleanup_steps((('spell.close',lambda:self.spell.close()if self.spell is not None else None),
                    ('manual.close',lambda:self.manual.close()if self.manual is not None else consumer.close())),primary)
                self.spell=self.manual=None
                raise

    def request_original_screenshot(self):
        """One explicit post-success UI question; reuse the original capture owner."""
        if self._screenshot_requested:return False
        need(not self.closed and self.manual is not None and self.spell is not None,
             'CANONICAL_SCREENSHOT_CURRENT_RUNTIME_REQUIRED')
        self._screenshot_requested=True
        try:
            from tools.local_original_session.original_screenshot import OriginalScreenshotObserver
            self.original_screenshot=OriginalScreenshotObserver(self.manual,
                collection_policy=getattr(self.broker,'_inventory_collection_policy',None))
            queued=self.original_screenshot.request()
            self.original_screenshot_observation=self.original_screenshot.observation()
            self._screenshot_finished=not queued
        except Exception as error:
            self.original_screenshot_observation=dict(status='UNKNOWN',
                reason=type(error).__name__+':'+str(error)[:160])
            self._screenshot_finished=True
        return not self._screenshot_finished

    def original_screenshot_finished(self):
        return self._screenshot_requested and self._screenshot_finished

    async def _prepare_book_equipment(self):
        if not self._book_equipment_enabled or self.manual.pending or self.manual.consumer._busy:
            return None
        from tools.local_original_session import launcher, item_equipment_effect
        from tools.local_original_session.broker import PersistentBroker
        broker = self.broker
        binding = launcher.current_manual_binding(broker)
        generation = None if binding is None else self.manual._inventory_reselection_current(binding.writer)
        if generation is not self._book_equipment_generation:
            self._book_equipment_generation = generation
            self._book_equipment_attempted = False
            self.book_equipment_initial = None
        if generation is None or not launcher.ProductFeatures._equipment_delivery_complete(self, broker, generation):
            return None
        if self._book_equipment_attempted:
            return self.book_equipment_initial
        effect = broker._item_equipment_effect
        need(type(broker) is PersistentBroker
             and type(effect) is item_equipment_effect.ItemEquipmentEffect
             and effect.broker is broker and broker.realm._item_equipment_effect is effect
             and effect.policy == self.selection._config.item_equipment_policy
             and effect.first_enable is self.selection._config.item_equipment_first_enable
             and broker.prepare_item_equipment.__self__ is broker
             and broker.prepare_item_equipment.__func__ is PersistentBroker.prepare_item_equipment,
             'BOOK_ORIGINAL_EQUIPMENT_PREPARATION_REQUIRED')
        self._book_equipment_attempted = True # Same-generation failure is not retried.
        receipt = await broker.prepare_item_equipment(binding.writer,
            policy=effect.policy, first_enable=effect.first_enable)
        current = launcher.current_manual_binding(broker)
        need(current is not None and current.writer is binding.writer
             and self.manual._inventory_reselection_current(binding.writer) is generation,
             'BOOK_EQUIPMENT_PREPARATION_SELECTION_CHANGED')
        self.book_equipment_initial = receipt
        return receipt

    async def poll(self, monitor=None):
        need(not self.closed and not self.broker.failure.is_set(),
             'CANONICAL_RUNTIME_CLOSED_OR_FAILED')
        self.selection.factory_current(self.selection._factory)
        result=dict(canonical=dict(attached=True, resource_active=self.selection._owner.active))
        spell_pending=self.spell is not None and self.spell.phase=='PENDING'
        if self._book_equipment_enabled and not spell_pending:
            result['item_equipment_initial'] = await self._prepare_book_equipment()
        if spell_pending:
            result['spell_whole']=await self.spell.poll()
            result['manual_move']=dict(self.manual.last_result)
        if self.manual is not None and not spell_pending:
            self.selection.full_buff_configured(self.selection._factory)
            before=self.manual.last_sample_monotonic_ns
            try:result['manual_move']=await self.manual.poll_async(monitor=monitor)
            finally:
                sampled=self.manual.last_sample_monotonic_ns
                if monitor is not None and sampled is not None and sampled!=before:
                    monitor.next_memory=max(monitor.next_memory,sampled/1e9+.5)
        if self.spell is not None and not spell_pending:
            result['spell_whole']=self.spell.report() if self.spell.closed else await self.spell.poll()
        screenshot=self.original_screenshot
        if screenshot is not None and not self._screenshot_finished:
            screenshot.collect()
            await screenshot.sample()
            self.original_screenshot_observation=screenshot.observation()
            self._screenshot_finished=(screenshot._terminal or
                not screenshot._requested and screenshot._pending is None)
        if self._screenshot_requested:
            result['original_screenshot']=self.original_screenshot_observation
        return result

    def close(self):
        if self.closed:return
        self.closed=True
        manual=self.manual;spell=self.spell;screenshot=self.original_screenshot
        try:
            error=_cleanup_steps((('spell.close',lambda:spell.close()if spell is not None else None),
                ('screenshot.close',lambda:screenshot.close()if screenshot is not None else None),
                ('manual.close',lambda:manual.close()if manual is not None else None)))
            if error is not None:raise error
        finally:
            self.spell=self.manual=self.selection=self.broker=None
            self.original_screenshot=None
            self._book_equipment_generation=self.book_equipment_initial=None
            self._book_equipment_enabled=False


def create_broker(selection, options):
    """Original default path imports no aggregate/RESOURCE owner modules."""
    from tools.local_original_session.broker import PersistentBroker
    if selection is None:
        return PersistentBroker(**options)
    need(type(selection) is CanonicalFeatureBootstrap,
         'CANONICAL_EXACT_BOOTSTRAP_SELECTION_REQUIRED')
    return selection.create_broker(options)
