"""Explicit private v3 owner of the EXISTING InventoryStore inventory.json.

One replace contains canonical assets, staged documents, reward markers and
transaction receipt. No wallet/HP/MP store and no cross-file atomic claim.
Caller holds its selected broker operation lock before entering this module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import inspect
import json
import os
from pathlib import Path
import threading
import uuid
import weakref
import sys
from types import CodeType, MethodType, MappingProxyType

from tools.local_original_session import inventory, inventory_store, item_custody, equipment_store

POLICY = 'EXPLICIT_CANONICAL_INVENTORY_PARTICIPANT_BATCH_V3'
MAX_BYTES = 524288
MAX_TRANSACTIONS = 256
_OWNERS = weakref.WeakValueDictionary()
_CONSUMED_USE_OWNERS = weakref.WeakKeyDictionary()
_CONSUMED_USE_SCOPES = weakref.WeakKeyDictionary()
_ZERO_EQUIPMENT_SOURCES = weakref.WeakKeyDictionary()
ZERO_EQUIPMENT_SOURCE_SHA256 = '87c93ec3eb27d8109eab3e70eaa5d215bcdf1c3bf07d9e0fe2a9efcf9d9422ed'


def need(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def request_digest(request):
    need(type(request) is bytes and 0 < len(request) <= 32768, 'BATCH_EXACT_REQUEST_BYTES')
    return hashlib.sha256(request).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'BATCH_DUPLICATE_JSON_KEY')
        result[key] = value
    return result


@dataclass(frozen=True)
class Binding:
    uid: int
    writer: object = field(repr=False)
    generation: object = field(repr=False)
    operation_lock: object = field(repr=False)
    generation_key: str
    owned_scope: object = field(repr=False)


class CanonicalProvider(ABC):
    """Trusted server capability, never issued from a client JSON path/bool.

    current MUST verify actual acquired scope token/current task+thread, not
    merely lock.locked(). A product implementation binds the original Store,
    selected UID/writer/generation/operation lock and authoritative catalog.
    Tests use an explicit private-profile provider, not a fabricated broker.
    """
    @property
    @abstractmethod
    def source_store(self): ...

    @abstractmethod
    def current(self, binding): ...

    @abstractmethod
    def catalog_current(self, binding, catalog_digest): ...

    def delivery_current(self,binding):
        raise ValueError('BATCH_EXPLICIT_DELIVERY_SELECTION_CAPABILITY_REQUIRED')

    def terminal_delivery_current(self,binding):
        raise ValueError('BATCH_EXPLICIT_TERMINAL_SELECTION_CAPABILITY_REQUIRED')

    def catalog_current_for(self,binding,catalog_digest,exact_names):
        # Existing explicit provider remains its trusted single catalog authority.
        return self.catalog_current(binding,catalog_digest)


class BrokerProvider(CanonicalProvider):
    """Structural actual-broker capability; does not seed a selection/receipt.

    catalog_owner is another explicit server capability exposing current_digest.
    The root must replace old restore/delivery consumers before enabling v3.
    """
    def __init__(self, broker, catalog_owner):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker, 'BATCH_ACTUAL_BROKER_REQUIRED')
        need(isinstance(catalog_owner, CatalogOwner) or type(catalog_owner) is ParticipantCatalogOwner,
             'BATCH_SERVER_CATALOG_CAPABILITY')
        self.broker, self.catalog = broker, catalog_owner
        self._catalog_owner=catalog_owner
        self._catalog_descriptor=(catalog_owner.descriptor() if type(catalog_owner) is ParticipantCatalogOwner
                                  else catalog_method(catalog_owner))
        self._source = broker._inventory_store
        self._scope = None
        self._bound = None
        need(type(self._source) in (inventory_store.InventoryStore,CanonicalInventorySource), 'BATCH_EXACT_CANONICAL_STORE')
        self._capture_zero_equipment_source()

    def _capture_zero_equipment_source(self):
        effect=getattr(self.broker,'_item_equipment_effect',None)
        if effect is None:return
        module=sys.modules.get('tools.local_original_session.item_equipment_effect')
        if module is None or not hasattr(module.ItemEquipmentEffect,'server_preparation_memory'):return
        path=Path(module.__file__).resolve(strict=True)
        need(type(effect) is module.ItemEquipmentEffect and effect.broker is self.broker
             and path.stat().st_size<=65536
             and hashlib.sha256(path.read_bytes()).hexdigest()==ZERO_EQUIPMENT_SOURCE_SHA256,
             'BATCH_ZERO_EQUIPMENT_EXACT_SOURCE_REQUIRED')
        names=('server_preparation_memory','prepare_restart_retirement','finish_restart_retirement')
        functions=[];codes=[]
        for name in names:
            method=getattr(effect,name)
            need(type(method) is MethodType and method.__self__ is effect
                 and method.__func__ is getattr(module.ItemEquipmentEffect,name)
                 and not inspect.iscoroutinefunction(method)
                 and Path(method.__func__.__code__.co_filename).resolve(strict=True)==path
                 and method.__func__.__globals__ is module.__dict__,
                 'BATCH_ZERO_EQUIPMENT_ORIGINAL_ACCESSOR_REQUIRED')
            functions.append(method.__func__)
            codes.append((method.__func__.__code__,method.__func__.__defaults__,
                          inventory._freeze_static(method.__func__.__kwdefaults__)))
        _ZERO_EQUIPMENT_SOURCES[self]=(module,path,ZERO_EQUIPMENT_SOURCE_SHA256,module.ItemEquipmentEffect,
            module.ServerPreparationMemory,module.RestartRetirementToken,tuple(functions),tuple(codes))

    def _zero_equipment_source_current(self,effect):
        witness=_ZERO_EQUIPMENT_SOURCES.get(self)
        need(type(witness) is tuple and len(witness)==8,'BATCH_ZERO_EQUIPMENT_COLD_SOURCE_REQUIRED')
        module,path,expected_sha,cls,memory_type,token_type,functions,codes=witness
        need(sys.modules.get('tools.local_original_session.item_equipment_effect') is module
             and module.ItemEquipmentEffect is cls and module.ServerPreparationMemory is memory_type
             and module.RestartRetirementToken is token_type
             and type(effect) is cls and effect.broker is self.broker and effect.realm is self.broker.realm
             and Path(module.__file__).resolve(strict=True)==path and expected_sha==ZERO_EQUIPMENT_SOURCE_SHA256
             and hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha
             and type(functions) is tuple and type(codes) is tuple and len(functions)==len(codes)==3,
             'BATCH_ZERO_EQUIPMENT_SOURCE_CHANGED')
        for name,function,binding in zip(('server_preparation_memory','prepare_restart_retirement',
                                         'finish_restart_retirement'),functions,codes):
            method=getattr(effect,name);code,defaults,kwdefaults=binding
            need(type(method) is MethodType and method.__self__ is effect and method.__func__ is function
                 and getattr(cls,name) is function and function.__code__ is code
                 and function.__globals__ is module.__dict__
                 and Path(function.__code__.co_filename).resolve(strict=True)==path
                 and function.__defaults__ is defaults and inventory._freeze_static(function.__kwdefaults__)==kwdefaults,
                 'BATCH_ZERO_EQUIPMENT_METHOD_CHANGED')
        return witness

    def prepare_zero_equipment_retirement(self,writer,row,generation,state):
        # Every fallible/source check happens before the broker's synchronous cleanup.
        if self not in _ZERO_EQUIPMENT_SOURCES:return None
        effect=self.broker._item_equipment_effect
        witness=BrokerProvider._zero_equipment_source_current(self,effect)
        token=witness[6][1](effect,writer,row,generation,state)
        need(BrokerProvider._zero_equipment_source_current(self,effect) is witness,
             'BATCH_ZERO_EQUIPMENT_RETIREMENT_SOURCE_CHANGED')
        if token is None:return None
        need(type(token) is witness[5],'BATCH_ZERO_EQUIPMENT_ISSUED_RETIREMENT_REQUIRED')
        return (witness[6][2],effect,token) # Held original function; no later dynamic callback lookup.

    def _zero_equipment_nonpending(self,binding,effect):
        witness=BrokerProvider._zero_equipment_source_current(self,effect)
        memory_type=witness[4];function=witness[6][0]
        record=function(effect,binding.writer) # Original pure issuer, never _context/_project/Store.
        need(BrokerProvider._zero_equipment_source_current(self,effect) is witness,
             'BATCH_ZERO_EQUIPMENT_SOURCE_CHANGED')
        b=self.broker;g=binding.generation;game=b.realm.registry.resolve(binding.writer)
        need(game is not None and game.selection is not None and b._inventory_generation is g
             and g.phase=='ACTIVE','BATCH_ZERO_EQUIPMENT_CURRENT_SELECTION_REQUIRED')
        expected=(binding.writer,g,game,game.selection,g.service,g.item_use_session,b.realm._actor_fields)
        need(type(record) is memory_type and record.writer is binding.writer and record.generation is g
             and type(record.identity) is tuple and len(record.identity)==len(expected)==7
             and all(a is z for a,z in zip(record.identity,expected))
             and type(record.state) is equipment_store.EquipmentState and record.state.weapon_uid==0
             and record.state.character_uid==binding.uid
             and type(record.state_values) is tuple and len(record.state_values)==5
             and record.state_values==tuple(getattr(record.state,n) for n in
                 ('character_uid','item_uid','template','weapon_uid','revision'))
             and type(record.frame) is bytes and record.status in ('RESTORED_EMPTY','RESTORED_UNEQUIPPED')
             and type(effect._last) is dict and record.status==effect._last.get('status') and effect._last.get('phase')=='NO_NOTIFICATIONS'
             and record.receipt_fields==inventory._freeze_static(effect._last)
             and effect.store.inventory_store is self._source
             and all(pending is None or type(pending) is dict and pending.get('phase')=='DRAINED'
                     for pending in (effect._operation,effect._collection_batch)),
             'BATCH_ZERO_EQUIPMENT_ISSUED_NONPENDING_REQUIRED')
        # This is historical source preparation, not current Eq/client/frame authority.
        # BatchStore._equipment still validates actual before/proposed persisted state.
        return True

    @property
    def source_store(self): return self._source

    def register_consumed_use_owner(self, owner, source_path, expected_sha256):
        """Cold registration of the exact source-issued book operation owner."""
        broker=self.broker
        need(self not in _CONSUMED_USE_OWNERS and self._scope is None and self._bound is None
             and not broker._started and not broker._closing and not broker.realm.registry._sessions,
             'BATCH_CONSUMED_USE_COLD_SINGLE_OWNER_REQUIRED')
        path=Path(source_path).resolve(strict=True)
        need(type(expected_sha256) is str and len(expected_sha256)==64
             and all(c in '0123456789abcdef' for c in expected_sha256)
             and path.stat().st_size<=65536 and hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha256,
             'BATCH_CONSUMED_USE_SOURCE_PIN_REQUIRED')
        cls=type(owner);module=sys.modules.get(cls.__module__)
        need(module is not None and cls is getattr(module,'BookBatch',None)
             and Path(module.__file__).resolve(strict=True)==path
             and Path(inspect.getsourcefile(cls)).resolve(strict=True)==path
             and owner.service.provider is self and owner.service.batch is sys.modules[__name__]
             and type(owner.service.store) is BatchStore and owner.service.store.provider is self
             and not owner.closed,'BATCH_CONSUMED_USE_EXACT_BOOK_OWNER_REQUIRED')
        method=owner.received_context
        need(type(method) is MethodType and method.__self__ is owner
             and method.__func__ is cls.received_context
             and not inspect.iscoroutinefunction(method)
             and Path(method.__func__.__code__.co_filename).resolve(strict=True)==path,
             'BATCH_CONSUMED_USE_ORIGINAL_ACCESSOR_REQUIRED')
        _CONSUMED_USE_OWNERS[self]=(owner,cls,module,path,expected_sha256,method.__func__,
                                   owner.service,owner.service.store)
        return owner

    def retire_consumed_use_owner(self, owner):
        registration=_CONSUMED_USE_OWNERS.get(self)
        need(type(registration) is tuple and len(registration)==8 and registration[0] is owner
             and owner.closed and self.broker._closing and not self.broker._tasks
             and self not in _CONSUMED_USE_SCOPES and self._scope is None,
             'BATCH_CONSUMED_USE_RETIRE_AFTER_OWNER_JOIN_REQUIRED')
        del _CONSUMED_USE_OWNERS[self]

    def abort_consumed_use_owner(self, owner):
        """Rollback only an unused cold registration, never a live lease."""
        registration=_CONSUMED_USE_OWNERS.get(self)
        if registration is None:
            need(not self.broker._started and not self.broker.realm.registry._sessions
                 and self._scope is None and self not in _CONSUMED_USE_SCOPES,
                 'BATCH_CONSUMED_USE_ABORT_UNUSED_COLD_OWNER_REQUIRED')
            return False
        need(type(registration) is tuple and len(registration)==8 and registration[0] is owner
             and not self.broker._started and not self.broker.realm.registry._sessions
             and self._scope is None and self not in _CONSUMED_USE_SCOPES
             and getattr(owner,'_received',None) is None and getattr(owner,'_delivery',None) is None,
             'BATCH_CONSUMED_USE_ABORT_UNUSED_COLD_OWNER_REQUIRED')
        from tools.local_original_session.item_use_session import ItemUseSession
        use=self.broker._item_use_session;service,store=registration[6:]
        need((owner.service is service or owner.closed and owner.service is None)
             and service.provider is self and service.store is store
             and store.provider is self and store.source is self._source
             and store.active is None and not store._delivery_caps
             and (use is None or type(use) is ItemUseSession and use.broker is self.broker
                  and self.broker.realm._item_use_session is use and use.accepted_count==0
                  and use._current is None and use._inflight_writer is None and not use._lock.locked()),
             'BATCH_CONSUMED_USE_ABORT_REQUIRES_UNUSED_ORIGINAL_RUNTIME')
        del _CONSUMED_USE_OWNERS[self]
        return True

    def _consumed_use_context(self, owner, parent):
        """Source-file pin plus pure issuer accessor; no current()/Store recursion."""
        registration=_CONSUMED_USE_OWNERS.get(self)
        need(type(registration) is tuple and len(registration)==8,
             'BATCH_CONSUMED_USE_REGISTERED_OWNER_REQUIRED')
        actual,cls,module,path,sha,function,service,store=registration
        method=getattr(owner,'received_context',None)
        need(owner is actual and type(owner) is cls and sys.modules.get(cls.__module__) is module
             and getattr(module,'BookBatch',None) is cls and cls.received_context is function
             and type(method) is MethodType and method.__self__ is owner and method.__func__ is function
             and owner.service is service and service.provider is self and service.store is store
             and service.batch is sys.modules[__name__] and not owner.closed
             and Path(module.__file__).resolve(strict=True)==path
             and path.stat().st_size<=65536 and hashlib.sha256(path.read_bytes()).hexdigest()==sha,
             'BATCH_CONSUMED_USE_OWNER_OR_ACCESSOR_CHANGED')
        value=function(owner,parent)
        need(type(value) is tuple and len(value)==8,'BATCH_CONSUMED_USE_EXACT_CONTEXT_REQUIRED')
        need(_CONSUMED_USE_OWNERS.get(self) is registration and owner.service is service
             and type(owner.received_context) is MethodType
             and owner.received_context.__self__ is owner and owner.received_context.__func__ is function
             and cls.received_context is function and not owner.closed
             and type(owner) is cls and sys.modules.get(cls.__module__) is module
             and getattr(module,'BookBatch',None) is cls and service.provider is self
             and service.store is store and service.batch is sys.modules[__name__],
             'BATCH_CONSUMED_USE_ACCESSOR_CALLBACK_CHANGED')
        return value

    def _consumed_use_current(self, use, *, owner=None, parent=None, expected=None,
                              terminal=False, binding=None):
        from tools.local_original_session.item_use_session import ItemUseSession,_Intent
        active=_CONSUMED_USE_SCOPES.get(self)
        if owner is None:
            need(type(active) is tuple and len(active)==4,'BATCH_CONSUMED_USE_SCOPE_REQUIRED')
            owner,parent,expected,scope=active
        else:scope=self._scope
        need(type(scope) is tuple and len(scope)==10 and self._scope is scope,
             'BATCH_CONSUMED_USE_CONNECTION_SCOPE_REQUIRED')
        task=asyncio.current_task()
        need(task is not None and (terminal or not task.cancelling()) and scope[0] is task,
             'BATCH_CONSUMED_USE_UNCANCELLED_TASK_REQUIRED')
        if terminal:
            delivery=owner._delivery
            registration=_CONSUMED_USE_OWNERS.get(self);store=registration[7]
            cap=None if delivery is None else delivery.cap
            record=None if type(cap) is not DeliveryCapability else store._delivery_caps.get(cap.token)
            need(delivery is not None and delivery.operation is parent
                 and delivery.phase=='FAILING' and isinstance(delivery._failure,BaseException)
                 and type(cap) is DeliveryCapability and cap.store is store and cap.binding is binding
                 and cap.parent is delivery and cap.task is task and cap.thread==threading.get_ident()
                 and type(record) is dict and record['cap'] is cap and not record['closed']
                 and record['phase']=='WRITING' and delivery.index==record['index'],
                 'BATCH_CONSUMED_USE_TERMINAL_EXACT_FAILED_ATTEMPT_REQUIRED')
            need(self._consumed_use_context(owner,delivery) is expected,
                 'BATCH_CONSUMED_USE_TERMINAL_SAME_OPERATION_REQUIRED')
        context=self._consumed_use_context(owner,parent)
        if expected is not None:
            need(context is expected,'BATCH_CONSUMED_USE_ISSUED_CONTEXT_CHANGED')
        actual,intent,ordinal,writer,row,g,frame,request=context
        self._connection(writer,row,scope=scope,terminal=terminal)
        need(actual is use and type(use) is ItemUseSession and type(intent) is _Intent
             and use.broker is self.broker and self.broker._item_use_session is g.item_use_session is use
             and (self._terminal_generation(writer) if terminal else
                  self.broker.inventory_selection_current(writer)) is g and g.phase=='ACTIVE'
             and g.row is row and g.writer is writer and g.lock is scope[4]
             and g.current_frame is frame and intent.frame is frame
             and intent.selection_binding is g.selection_binding and intent.writer is writer
             and type(ordinal) is int and ordinal>0 and use.accepted_count==intent.accepted_ordinal==ordinal
             and intent.request.raw_payload is request and type(request) is bytes
             and use._current is intent and not use.closed and not use._released
             and use._inflight_writer is None and not use._lock.locked(),
             'BATCH_CONSUMED_USE_EXACT_ACCEPTED_INTENT_REQUIRED')
        return context

    @contextmanager
    def consumed_use_operation(self, owner, operation):
        """Nest inside the original owned row operation; grants no new lock."""
        need(self not in _CONSUMED_USE_SCOPES,'BATCH_CONSUMED_USE_ALREADY_ACTIVE')
        context=self._consumed_use_context(owner,operation)
        self._consumed_use_current(context[0],owner=owner,parent=operation,expected=context)
        active=(owner,operation,context,self._scope)
        _CONSUMED_USE_SCOPES[self]=active
        try:
            yield context
        finally:
            # No owner callback during unwinding; preserve the primary failure.
            if _CONSUMED_USE_SCOPES.get(self) is active:
                del _CONSUMED_USE_SCOPES[self]

    def consumed_use_context(self, owner, parent):
        active=_CONSUMED_USE_SCOPES.get(self)
        need(type(active) is tuple and len(active)==4 and active[0] is owner
             and active[3] is self._scope,'BATCH_CONSUMED_USE_SCOPE_REQUIRED')
        value=self._consumed_use_context(owner,parent)
        need(value is active[2],'BATCH_CONSUMED_USE_SAME_ISSUED_OPERATION_REQUIRED')
        self._connection(value[3],value[4],scope=active[3])
        return value

    def _connection(self,writer,row,*,scope=None,terminal=False):
        from tools.local_original_session.broker import PersistentBroker,_TransportPolicy
        need(type(self.broker) is PersistentBroker and type(self.broker.policy) is _TransportPolicy and self.broker._inventory_store is self._source
             and type(self._source) in (inventory_store.InventoryStore,CanonicalInventorySource),
             'BATCH_EXACT_CONNECTION_BROKER_SOURCE')
        broker=self.broker
        if scope is not None:need(broker.policy is scope[8],'BATCH_CONNECTION_POLICY_IDENTITY_CHANGED')
        claims=[r for rows in broker._claims.values() for r in rows if r['writer'] is writer]
        need(type(row) is dict and len(claims)==1 and claims[0] is row and row['writer'] is writer
             and (terminal or (not broker._closing and not broker.failure.is_set() and row.get('failed') is False
             and not row.get('eof',False))) and row.get('joined') is False, 'BATCH_CURRENT_CONNECTION_ROW')
        if terminal:
            rows=[r for group in broker.policy.rows.values() for r in group if r.writer is writer]
            need(len(rows)==1,'BATCH_TERMINAL_EXACT_POLICY_ROW')
            admitted=rows[0]
        else:admitted=broker.policy._connection(writer)
        need(row['policy_row'] is admitted and admitted.writer is writer and (terminal or (not admitted.failed
             and not admitted.eof)) and not admitted.positive_close and not admitted.task_joined and not admitted.registry_removed,
             'BATCH_CURRENT_CONNECTION_POLICY')
        peer=row['peer'];lock=row['operation_lock']
        need(type(peer) is dict and type(peer.get('connection_id')) is int and peer['connection_id']>0
             and type(lock) is asyncio.Lock,'BATCH_CONNECTION_PEER_LOCK')
        if scope is not None:
            need(self._scope is scope and scope[0] is asyncio.current_task() and scope[1]==threading.get_ident()
                 and scope[2] is writer and scope[3] is row and scope[4] is lock and lock.locked()
                 and scope[5] is peer and inventory._freeze_static(peer)==scope[6] and scope[7] is admitted,
                 'BATCH_ACTUALLY_OWNED_CONNECTION_SCOPE_REQUIRED')
        return peer,lock,admitted

    @asynccontextmanager
    async def connection_operation(self,writer,exact_row):
        """Acquire the real preselection chunk row lock; never adopt a bool."""
        need(self._scope is None,'BATCH_OPERATION_SCOPE_ALREADY_ACTIVE')
        peer,acquired_lock,admitted=self._connection(writer,exact_row)
        need(not acquired_lock.locked(),'BATCH_PREHELD_LOCK_OWNER_ADAPTER_REQUIRED')
        expected_peer=inventory._freeze_static(peer)
        await acquired_lock.acquire()
        scope=(asyncio.current_task(),threading.get_ident(),writer,exact_row,
               acquired_lock,peer,expected_peer,admitted,self.broker.policy,object())
        self._scope=scope;self._bound=None
        try:
            self._connection(writer,exact_row,scope=scope)
            yield scope
        finally:
            if self._scope is scope:self._scope=None;self._bound=None
            acquired_lock.release()

    def bind_selected(self,writer):
        scope=self._scope
        need(scope is not None,'BATCH_ACTUALLY_OWNED_CONNECTION_SCOPE_REQUIRED')
        self._connection(writer,scope[3],scope=scope)
        g=self.broker.inventory_selection_current(writer)
        need(g is not None and g.row is scope[3] and g.lock is scope[4],
             'BATCH_CURRENT_GENERATION_REQUIRED')
        old=self._bound
        if old is not None and old.generation is g:
            self.current(old);return old
        if old is not None:
            previous=old.generation
            need(previous.phase=='RETIRED' and g.previous is previous and
                 g.restart_state is previous.restart_state and type(g.restart_state) is dict and
                 g.restart_state.get('phase')=='DRAINED' and g.restart_state.get('selection_cleared') is True,
                 'BATCH_GENERATION_REPLACEMENT_REQUIRES_DRAINED_RESTART')
        bound=Binding(g.mover.snapshot().uid,writer,g,scope[4],uuid.uuid4().hex,scope)
        self._bound=bound
        try:self.current(bound)
        except BaseException:self._bound=old;raise
        return bound

    def bind(self,writer):return self.bind_selected(writer)

    @asynccontextmanager
    async def selected_operation(self,writer):
        """Preselected specialization of the same actual connection scope."""
        g=self.broker.inventory_selection_current(writer)
        need(g is not None,'BATCH_CURRENT_GENERATION_REQUIRED')
        async with self.connection_operation(writer,g.row):
            binding=self.bind_selected(writer)
            need(binding.generation is g,'BATCH_SELECTED_GENERATION_CHANGED_BEFORE_ACQUIRE')
            yield binding

    def _selected_current(self, binding, *, terminal=False):
        need(type(binding) is Binding, 'BATCH_EXACT_BINDING')
        b, g = self.broker, binding.generation
        need(self._scope is binding.owned_scope and self._scope is not None and self._bound is binding,
             'BATCH_ACTUALLY_OWNED_OPERATION_SCOPE_REQUIRED')
        self._connection(binding.writer,self._scope[3],scope=self._scope,terminal=terminal)
        need(b._inventory_store is self._source and
             (self._terminal_generation(binding.writer) if terminal else
              b.inventory_selection_current(binding.writer)) is g and
             g.store is self._source and g.writer is binding.writer and
             g.lock is binding.operation_lock is g.row['operation_lock'] and
             g.lock.locked() and g.mover.snapshot().uid == binding.uid,
             'BATCH_CURRENT_CANONICAL_SELECTION_REQUIRED')
        transfer = g.transfer_session
        need(transfer is None or (transfer.pending is None and transfer.phase in
             ('READY', 'RETURNED', 'RESTORED_CUSTODY')), 'BATCH_PENDING_CUSTODY_REFUSED')
        from tools.local_original_session.item_use_session import ItemUseSession,ItemUseOutcome,OutcomeKind
        use=g.item_use_session
        quiescent=(use is None or (type(use) is ItemUseSession and not use.closed and not use._released and
                    use._current is None and use._inflight_writer is None and not use._lock.locked()))
        if not quiescent:
            need(self in _CONSUMED_USE_SCOPES,'BATCH_PENDING_OR_UNKNOWN_ITEM_USE_REFUSED')
            self._consumed_use_current(use,terminal=terminal,binding=binding)
        if use is not None and use.last_outcome is not None:
            need(type(use.last_outcome) is ItemUseOutcome and type(use.last_outcome.kind) is OutcomeKind
                 and use.last_outcome.kind in (OutcomeKind.DISABLED,OutcomeKind.ACCEPTED,OutcomeKind.REJECTED),
                 'BATCH_FAILED_ITEM_USE_REFUSED')
        need(not g.service._inflight and not g.service._closed,'BATCH_INVENTORY_DELIVERY_INFLIGHT_REFUSED')
        need(b._inventory_update_operation is None or (type(b._inventory_update_operation) is dict and
             b._inventory_update_operation.get('phase')=='DRAINED'), 'BATCH_PENDING_INVENTORY_UPDATE_REFUSED')
        effect=b._item_equipment_effect
        if effect is not None:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            need(type(effect) is ItemEquipmentEffect and effect.broker is b,'BATCH_UNKNOWN_EQUIPMENT_OWNER_REFUSED')
            need(type(effect._last) is dict,'BATCH_FAILED_EQUIPMENT_RECEIPT_REFUSED')
            outcome=(effect._last.get('status'),effect._last.get('phase'))
            if outcome in (('RESTORED_EMPTY','NO_NOTIFICATIONS'),('RESTORED_UNEQUIPPED','NO_NOTIFICATIONS')):
                self._zero_equipment_nonpending(binding,effect)
            else:
                need(outcome in (('NOT_PREPARED','EMPTY'),('SYNCHRONIZED','DRAINED'),('COMMITTED','DRAINED')),
                     'BATCH_FAILED_EQUIPMENT_RECEIPT_REFUSED')
            for pending in (effect._operation,effect._collection_batch):
                need(pending is None or (type(pending) is dict and pending.get('phase')=='DRAINED'),
                     'BATCH_PENDING_OR_FAILED_EQUIPMENT_REFUSED')
        restart=g.row.get('_restart')
        need(restart is None or (type(restart) is dict and restart.get('phase')=='DRAINED'),
             'BATCH_PENDING_RESTART_REFUSED')
        return True

    def current(self,binding):
        self._selected_current(binding)
        policy=binding.generation.row['policy_row']
        need(policy.pending_opcode is None and policy.pending_size==0 and policy.drain_started_ns is None,
             'BATCH_PENDING_TRANSPORT_REFUSED')
        return True

    def delivery_current(self,binding):
        return self._selected_current(binding)

    def _terminal_generation(self,writer):
        # Original structural current observer; only closing/failure flags differ.
        from tools.local_original_session.broker import (_InventoryGeneration,
            INVENTORY_RESELECTION_POLICY,INVENTORY_RESELECTION_DELIVERY)
        broker=self.broker
        """Structural current-generation observation only; no Store/native reads."""
        if getattr(broker, 'inventory_reselection_policy', None) is None:
            return None
        from tools.local_original_session import inventory
        generation = broker._inventory_generation
        need(type(generation) is _InventoryGeneration and generation.broker is broker,
             'INVENTORY_RESELECTION_REAL_GENERATION_REQUIRED')
        if generation.writer is None or generation.phase in ('RETIRED', 'PREPARING'):
            return None
        need(type(broker.inventory_reselection_policy) is str
             and broker.inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
             and type(broker.inventory_delivery_policy) is str
             and broker.inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
             and broker.restart_policy == 'EXPLICIT_LOCAL_SELECTED_RESTART'
             and broker.policy.restart_enabled is True
             and generation.phase == 'ACTIVE',
             'INVENTORY_RESELECTION_GENERATION_NOT_ACTIVE')
        row, game, service = generation.row, generation.game, generation.service
        claims = [r for rows in broker._claims.values() for r in rows if r['writer'] is writer]
        need(generation.writer is writer and len(claims) == 1 and claims[0] is row
             and row['writer'] is writer and generation.lock is row['operation_lock']
             and not row['joined']
             and broker.realm.registry.resolve(writer) is game
             and broker.realm._account_bound.get(id(writer)) is generation.account
             and game.selection is generation.selected
             and broker.realm.registry.selected.get(generation.selected.reference) is generation.selected
             and broker.realm.service(writer) is generation.mover
             and type(service) is inventory.InventoryService and service is broker._inventory_service
             and getattr(service, '_inventory_generation', None) is generation
             and not service._closed and generation.reader is broker._inventory_reader
             and service.reader is generation.reader and generation.store is broker._inventory_store
             and service.store is generation.store
             and broker.realm._item_use_session is generation.item_use_session,
             'INVENTORY_RESELECTION_CURRENT_SELECTION_REQUIRED')
        previous = generation.previous
        if previous is not None:
            need(type(previous) is _InventoryGeneration and previous.broker is broker
                 and previous.phase == 'RETIRED' and previous.service._closed
                 and previous.writer is writer and previous.game is game
                 and previous.selected is not generation.selected
                 and previous.reader is generation.reader and previous.store is generation.store
                 and generation.restart_state is previous.restart_state
                 and generation.restart_state['phase'] == 'DRAINED'
                 and generation.restart_state['selection_cleared'] is True,
                 'INVENTORY_RESELECTION_PREVIOUS_LIFETIME_REQUIRED')
        if generation.selection_binding is None:
            need(generation.frame is None and not generation.restored
                 and generation.current_frame is None and not generation.attempted,
                 'INVENTORY_RESELECTION_EMPTY_ROW_REQUIRED')
        else:
            broker._inventory_selection_frame_current(writer, row, generation.frame)
            need(generation.selection_binding[7] is generation.selected
                 and generation.selection_binding[8] is service,
                 'INVENTORY_RESELECTION_SAME_BINDING_REQUIRED')
        return generation

    def terminal_delivery_current(self,binding):
        return self._selected_current(binding,terminal=True)

    def catalog_current(self, binding, catalog_digest):
        # Scoped configuration does not imply asset-only or ambient feature authority.
        return self.catalog_current_for(binding,catalog_digest,())

    def _catalog_binding(self,exact_names):
        need(self.catalog is self._catalog_owner,'BATCH_CATALOG_BOOTSTRAP_OWNER_CHANGED')
        if type(self.catalog) is ParticipantCatalogOwner:
            self.catalog.check(self._catalog_descriptor)
            return self.catalog.resolve(exact_names)
        method=catalog_method(self.catalog)
        need(method.__self__ is self._catalog_descriptor.__self__ and
             method.__func__ is self._catalog_descriptor.__func__,'BATCH_CATALOG_OWNER_METHOD_CHANGED')
        return method

    def catalog_current_for(self,binding,catalog_digest,exact_names):
        catalog_names(exact_names)
        catalog_sha(catalog_digest)
        self.current(binding)
        method=self._catalog_binding(exact_names)
        owner,descriptor=self._catalog_owner,self._catalog_descriptor
        try:
            value=method(binding)
        finally:
            self.current(binding)
            need(self._catalog_owner is owner and self._catalog_descriptor is descriptor and self.catalog is owner,
                 'BATCH_CATALOG_BOOTSTRAP_BINDING_CHANGED')
            checked=self._catalog_binding(exact_names)
            need(checked.__self__ is method.__self__ and checked.__func__ is method.__func__,
                 'BATCH_CATALOG_OWNER_METHOD_CHANGED')
        if inspect.isawaitable(value):
            if inspect.iscoroutine(value):value.close()
            raise ValueError('BATCH_CATALOG_OWNER_AWAITABLE_REFUSED')
        catalog_sha(value)
        return value==catalog_digest


class CatalogOwner(ABC):
    @abstractmethod
    def current_digest(self, binding): ...


@dataclass(frozen=True,slots=True,init=False)
class ParticipantCatalogOwner:
    """Explicit bootstrap tuple scopes, no mutable active-feature state."""
    _mapping: object
    _bindings: tuple

    def __init__(self,entries):
        need(type(entries) is tuple and len(entries)>0,'BATCH_EXACT_CATALOG_SCOPE_ENTRIES')
        rows={};bindings=[]
        for entry in entries:
            need(type(entry) is tuple and len(entry)==2,'BATCH_EXACT_CATALOG_SCOPE_ENTRY')
            names,owner=entry;catalog_names(names)
            need(names not in rows,'BATCH_DUPLICATE_CATALOG_SCOPE')
            method=catalog_method(owner)
            rows[names]=owner;bindings.append((names,owner,method.__func__))
        object.__setattr__(self,'_mapping',MappingProxyType(rows))
        object.__setattr__(self,'_bindings',tuple(bindings))

    def descriptor(self):
        return self._mapping,self._bindings

    def check(self,descriptor):
        need(type(self._mapping) is MappingProxyType and self._mapping is descriptor[0] and
             self._bindings is descriptor[1] and len(self._mapping)==len(self._bindings),
             'BATCH_CATALOG_SCOPE_MAP_CHANGED')
        for names,owner,function in self._bindings:
            need(self._mapping.get(names) is owner,'BATCH_CATALOG_SCOPE_OWNER_CHANGED')
            method=catalog_method(owner)
            need(method.__func__ is function,'BATCH_CATALOG_OWNER_METHOD_CHANGED')

    def resolve(self,names):
        catalog_names(names)
        need(names in self._mapping,'BATCH_PARTICIPANT_CATALOG_SCOPE_NOT_REGISTERED')
        return catalog_method(self._mapping[names])


def catalog_method(owner):
    need(isinstance(owner,CatalogOwner),'BATCH_TRUSTED_CATALOG_OWNER_REQUIRED')
    method=owner.current_digest
    need(inspect.ismethod(method) and method.__self__ is owner and
         not inspect.iscoroutinefunction(method),'BATCH_SYNC_CATALOG_OWNER_REQUIRED')
    return method


def catalog_names(names):
    need(type(names) is tuple and all(type(n) is str and n in
         ('RESOURCE','SKILL','SHOP-QUEST') for n in names) and
         len(set(names))==len(names) and names==tuple(sorted(names)),
         'BATCH_EXACT_PARTICIPANT_CATALOG_NAMES')
    return names


def catalog_sha(value):
    need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),
         'BATCH_EXACT_CATALOG_DIGEST')


class DeliveryOwner(ABC):
    """One bootstrap dispatcher. No parent.current/store recursion is allowed."""
    @abstractmethod
    def validate_operation(self,parent,binding,*,txid,request,receipt,participant,index,wire,phase): ...

    def validate_projection_read(self,parent,binding,*,participants,index,wire,phase):
        raise ValueError('BATCH_EXPLICIT_WORLD_PROJECTION_OWNER_REQUIRED')


@dataclass(frozen=True,slots=True,init=False)
class DeliveryCapability:
    store: object
    binding: Binding
    owner: object
    parent: object
    txid: str
    request: bytes
    receipt_raw: bytes
    frames: tuple
    transport: object
    task: object
    thread: int
    token: object

    def __new__(cls):raise ValueError('BATCH_DELIVERY_CAPABILITY_PRIVATE_ISSUANCE')


@dataclass(frozen=True)
class QuantityChange:
    item_uid: int
    debit: int = 0
    credit: int = 0
    # Required only for a new credited UID: a COMPLETE canonical singleton.
    credit_frame: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ParticipantChange:
    name: str
    expected_revision: int
    expected_digest: str
    document: dict = field(repr=False)
    reward_markers: tuple[str, ...] = ()


class DocumentCapability:
    """Explicit participant validator supplied by its owning server feature."""
    def __init__(self, name, validate, *, scope, validate_change, validate_authority=None):
        need(name in ('SHOP-QUEST', 'SKILL', 'RESOURCE') and callable(validate) and callable(validate_change)
             and scope == ('account' if name=='SKILL' else 'character'), 'BATCH_DOCUMENT_CAPABILITY')
        self.name,self.validate,self.scope,self.validate_change = name,validate,scope,validate_change
        need((name=='RESOURCE' and callable(validate_authority) and not inspect.iscoroutinefunction(validate_authority))
             or (name!='RESOURCE' and validate_authority is None), 'BATCH_RESOURCE_SYNC_AUTHORITY_REQUIRED')
        self.validate_authority=validate_authority

    def check(self, document):
        # Serializability/bounds are checked before feature-specific validation.
        need(type(document) is dict and len(encoded(document)) <= 131072, 'BATCH_DOCUMENT_BOUND')
        if self.name == 'SKILL':
            need(set(document) == {'schema','policy','account','rules','characters'},
                 'BATCH_SKILL_DOCUMENT_SHAPE')
            need(type(document['characters']) is dict, 'BATCH_SKILL_CHARACTERS')
            for row in document['characters'].values():
                need(type(row) is dict and set(row) ==
                     {'learned','cooldowns','buffs','revision','clock'},
                     'BATCH_SKILL_RESOURCE_DUPLICATION_REFUSED')
        elif self.name == 'SHOP-QUEST':
            need(set(document)=={'version','policy','catalog_sha','states','events'} and
                 type(document['version']) is int and (document['version'],document['policy']) in
                 ((1,'EXPLICIT_LOCAL_SHOP_QUEST_PARTICIPANT_V1'),
                  (2,'EXPLICIT_LOCAL_SHOP_QUEST_PARTICIPANT_V2')) and
                 type(document['states']) is list and type(document['events']) is list,
                 'BATCH_SHOP_DOCUMENT_SHAPE')
            seen=set()
            for row in document['states']:
                keys={'quest','count','rewarded'} if document['version']==1 else {'quest','count','rewarded','cursor'}
                need(type(row) is dict and set(row)==keys and
                     type(row['quest']) is str and row['quest'] not in seen and
                     type(row['count']) is int and row['count']>=0 and type(row['rewarded']) is bool,
                     'BATCH_SHOP_QUEST_ROW')
                if document['version']==2:
                    cursor=row['cursor']
                    need(type(cursor) is dict and set(cursor)=={'issuer_nonce','accepted_ordinal'} and
                         type(cursor['issuer_nonce']) is str and len(cursor['issuer_nonce'])==32 and
                         all(c in '0123456789abcdef' for c in cursor['issuer_nonce']) and
                         type(cursor['accepted_ordinal']) is int and 0<=cursor['accepted_ordinal']<1<<64,
                         'BATCH_SHOP_QUEST_CURSOR')
                seen.add(row['quest'])
        self.validate(deepcopy(document))

    def key(self,uid):
        return self.name+(':'+str(uid) if self.scope=='character' else '')

    def authority(self,binding,before,after,phase):
        if self.name!='RESOURCE':return
        need(type(binding) is Binding and phase in ('SEED','PREPARE','COMMIT'),
             'BATCH_RESOURCE_AUTHORITY_PHASE')
        value=self.validate_authority(binding,deepcopy(before),deepcopy(after),phase)
        if inspect.isawaitable(value):
            if inspect.iscoroutine(value):value.close()
            raise ValueError('BATCH_RESOURCE_AUTHORITY_AWAITABLE_REFUSED')
        need(value is True,'BATCH_RESOURCE_AUTHORITY_REFUSED')

    def change(self,before,after,uid):
        self.check(after)
        if self.scope=='account' and before is not None:
            need(all(before[k]==after[k] for k in before if k!='characters'), 'BATCH_ACCOUNT_BINDING_CHANGED')
            old,new=before['characters'],after['characters']
            need({k:v for k,v in old.items() if k!=str(uid)} ==
                 {k:v for k,v in new.items() if k!=str(uid)}, 'BATCH_OTHER_CHARACTER_MUTATION_REFUSED')
        # Server feature owns the semantic transition/event authorization.
        need(self.validate_change(deepcopy(before),deepcopy(after),uid) is True,
             'BATCH_PARTICIPANT_CHANGE_AUTHORITY_REFUSED')


@dataclass(frozen=True)
class Reservation:
    operation_id: str
    uid: int
    request_sha: str
    binding: Binding = field(repr=False)
    token: object = field(repr=False)


class BatchStore:
    """Private canonical-owner candidate. No implicit migration or old fallback.

    Lock order: owned operation scope -> shared participant/inventory RLock ->
    optional coordinator lock -> reentrant same inventory RLock -> realm._lock.
    No waits/async calls/callback writes happen inside the atomic replacement.
    One process writer only. v3 makes original readers/mutators refuse schema.
    """
    def __init__(self, provider, *, capabilities):
        need(isinstance(provider, CanonicalProvider), 'BATCH_CANONICAL_CAPABILITY_REQUIRED')
        source = provider.source_store
        need(type(source) in (inventory_store.InventoryStore,CanonicalInventorySource) and
             source._collection_policy == inventory_store.COLLECTION_STORE_POLICY,
             'BATCH_EXACT_CANONICAL_COLLECTION_STORE')
        self.provider, self.source = provider, source
        self.path, self.profile = source.path, source.profile
        self._paths = (self.path, self.profile)
        self.lock = inventory_store._lock
        need(type(capabilities) is tuple and all(type(c) is DocumentCapability for c in capabilities),
             'BATCH_EXPLICIT_DOCUMENT_CAPABILITIES')
        self.capabilities = {c.name:c for c in capabilities}
        need(len(self.capabilities) == len(capabilities), 'BATCH_DUPLICATE_DOCUMENT_CAPABILITY')
        self.failed = self.closed = False
        self.active = None
        self._delivery_owner=self._delivery_owner_method=self._projection_owner_method=None
        self._delivery_validating=False
        self._delivery_caps={}
        self._delivery_issuance={}
        self._catalog_validating=False
        self._catalog_write_refused=False
        self._original_update_owner=None
        self._original_update_validating=False
        self._original_update_write_refused=False
        self._original_update_commit=None
        with self.lock:
            key = str(self.path.resolve())
            prior = _OWNERS.get(key)
            need(prior is None or prior.closed or prior.failed, 'BATCH_CANONICAL_OWNER_ALREADY_OPEN')
            _OWNERS[key] = self
            self._key = key
            self._raw, self.data = self._read()

    def _path_check(self):
        need((self.path,self.profile) == self._paths and self.source.path == self.path and
             self.source.profile == self.profile and self.provider.source_store is self.source,
             'BATCH_CANONICAL_PATH_CHANGED')
        self.source._path_check()

    def _read(self):
        self._path_check()
        with self.path.open('rb') as stream: raw = stream.read(MAX_BYTES+1)
        need(len(raw) <= MAX_BYTES, 'BATCH_STORE_SIZE')
        doc = json.loads(raw, object_pairs_hook=unique)
        self._validate(doc, raw)
        return raw,doc

    def _validate_canonical(self, doc):
        # Preserve original strict canonical validators and roster bindings.
        known = {r['uid'] for r in inventory_store._characters(self.profile)['characters']}
        need(type(doc) is dict and type(doc.get('version')) is int, 'BATCH_CANONICAL_SCHEMA')
        if doc['version'] == 2:
            need(self.source.custody_policy == item_custody.CUSTODY_POLICY, 'BATCH_CUSTODY_OPT_IN')
            snap = item_custody.decode(doc, encoded(doc), known, str(self.profile))
            return {snap.character_uid:item_custody.owned_frame(snap)}
        need(doc['version'] == 1 and set(doc) == {'version','inventories'} and
             type(doc['inventories']) is list and len(doc['inventories']) <= 3,
             'BATCH_CANONICAL_LEGACY_SHAPE')
        rows = {}
        for row in doc['inventories']:
            need(type(row) is dict and set(row) == {'uid','frame'} and
                 type(row['uid']) is int and row['uid'] in known and row['uid'] not in rows,
                 'BATCH_CANONICAL_ROSTER_UID')
            wire = bytes.fromhex(row['frame'])
            need(wire.hex() == row['frame'], 'BATCH_CANONICAL_HEX')
            inventory.validate_current_collection_frame(wire, policy=inventory.COLLECTION_POLICY)
            rows[row['uid']] = wire
        return rows

    def _validate(self, doc, raw):
        need(type(doc) is dict and type(doc.get('version')) is int, 'BATCH_STORE_OBJECT_VERSION')
        if doc.get('version') != 3:
            return self._validate_canonical(doc)
        need(set(doc) == {'version','policy','canonical','revisions','participants','markers','transactions','pending'}
             and doc['policy'] == POLICY, 'BATCH_V3_SCHEMA')
        rows = self._validate_canonical(doc['canonical'])
        need(type(doc['revisions']) is dict and set(doc['revisions']) == {str(u) for u in rows}
             and all(type(v) is int and 0 < v < 1 << 63 for v in doc['revisions'].values()),
             'BATCH_REVISION_SCHEMA')
        need(type(doc['participants']) is dict,
             'BATCH_PARTICIPANT_CAPABILITY_MISSING')
        for key,row in doc['participants'].items():
            name=key.split(':',1)[0]
            need(name in self.capabilities,'BATCH_PARTICIPANT_CAPABILITY_MISSING')
            cap=self.capabilities[name]
            if cap.scope=='character':
                need(any(key==cap.key(u) for u in rows),'BATCH_PARTICIPANT_CHARACTER_SCOPE')
            else:need(key==name,'BATCH_PARTICIPANT_ACCOUNT_SCOPE')
            need(type(row) is dict and set(row) == {'revision','digest','document'} and
                 type(row['revision']) is int and row['revision'] >= 0 and
                 row['digest'] == digest(row['document']), 'BATCH_PARTICIPANT_SCHEMA')
            cap.check(row['document'])
        need(type(doc['transactions']) is dict and len(doc['transactions']) <= MAX_TRANSACTIONS and
             type(doc['markers']) is dict and set(doc['markers']) <= set(doc['participants']),
             'BATCH_RECEIPT_BOUND')
        pending = []
        for txid,tx in doc['transactions'].items():
            need(type(txid) is str and 1 <= len(txid) <= 128 and type(tx) is dict and
                 set(tx) == {'uid','request_sha','batch_sha','catalog','generation','plan_sha','phase','asset_revision','participants','delivery'}
                 and type(tx['uid']) is int and tx['uid'] in rows and
                 tx['phase'] in ('PREPARED','COMMITTED','ABORTED') and
                 tx['delivery'] in ('UNATTEMPTED','WRITE_ATTEMPTED','DRAINED','UNKNOWN'), 'BATCH_RECEIPT_SCHEMA')
            for key in ('request_sha','batch_sha','catalog','plan_sha'):
                need(type(tx[key]) is str and len(tx[key]) == 64 and
                     all(c in '0123456789abcdef' for c in tx[key]), 'BATCH_RECEIPT_DIGEST')
            need(type(tx['generation']) is str and 0 < len(tx['generation']) <= 128 and
                 type(tx['asset_revision']) is int and tx['asset_revision'] > 0 and
                 type(tx['participants']) is dict, 'BATCH_RECEIPT_VALUES')
            if tx['phase'] == 'PREPARED': pending.append(txid)
        need(pending == ([] if doc['pending'] is None else [doc['pending']]), 'BATCH_SINGLE_PENDING_REQUIRED')
        for name,markers in doc['markers'].items():
            need(type(markers) is dict and all(type(k) is str and type(v) is str and
                 v in doc['transactions'] and doc['transactions'][v]['phase'] == 'COMMITTED'
                 for k,v in markers.items()), 'BATCH_REWARD_MARKER_RECEIPT')

    def _current(self, binding):
        need(not self.failed and not self.closed and type(binding) is Binding and
             self.provider.current(binding) is True, 'BATCH_CURRENT_AUTHORITY_REQUIRED')
        need(_OWNERS.get(self._key) is self, 'BATCH_CANONICAL_OWNER_REPLACED')
        raw,doc = self._read()
        need(raw == self._raw and doc == self.data, 'BATCH_STALE_CANONICAL_INSTANCE')
        return doc

    def _resource_authority(self,binding,cap,before,after,phase,*,reservation=None):
        # Authority callbacks are read-only. Reentrant reads are allowed;
        # reentrant writes/active-plan mutation cannot replace our preimage.
        expected_raw=self._raw
        before_sha,after_sha=digest(before),digest(after)
        active=self.active
        active_sha=None if active is None else digest(active[1])
        try:
            cap.authority(binding,before,after,phase)
        finally:
            self._current(binding)
            if self._raw!=expected_raw:
                self.failed=True
                raise ValueError('BATCH_RESOURCE_CALLBACK_PREIMAGE_CHANGED')
            need(digest(before)==before_sha and digest(after)==after_sha,
                 'BATCH_RESOURCE_CALLBACK_STAGED_DOCUMENT_CHANGED')
            need(self.active is active and (active is None or digest(active[1])==active_sha),
                 'BATCH_RESOURCE_CALLBACK_RESERVATION_PLAN_CHANGED')
            if reservation is not None:self._reservation(binding,reservation)

    def _replace(self, data):
        if self._catalog_validating:
            self._catalog_write_refused=True
            raise ValueError('BATCH_CATALOG_CALLBACK_WRITE_REFUSED')
        if self._original_update_validating:
            self._original_update_write_refused=True
            raise ValueError('BATCH_ORIGINAL_UPDATE_CALLBACK_WRITE_REFUSED')
        if self._original_update_commit is None:
            self._validate(data, encoded(data))
        else:
            self._original_update_owner._guard_call(self._validate,data,encoded(data))
        raw = encoded(data)+b'\n'
        need(len(raw) <= MAX_BYTES, 'BATCH_STORE_SIZE')
        temporary = self.path.with_name('.inventory-batch-'+uuid.uuid4().hex+'.tmp')
        self.failed = True  # Any attempted write/replace/readback is ambiguous on error.
        try:
            self._path_check()
            with temporary.open('xb') as stream:
                need(stream.write(raw) == len(raw), 'BATCH_PARTIAL_WRITE')
                stream.flush(); os.fsync(stream.fileno())
            self._path_check()
            with self.path.open('rb') as stream:preimage=stream.read(MAX_BYTES+1)
            need(len(preimage)<=MAX_BYTES and preimage == self._raw, 'BATCH_PREIMAGE_CHANGED')
            os.replace(temporary,self.path)
            actual,restored = (self._read() if self._original_update_commit is None else
                              self._original_update_owner._guard_call(self._read))
            need(actual == raw and restored == data, 'BATCH_EXACT_READBACK_REQUIRED')
            self._raw,self.data = actual,restored
            self.failed = False
        finally:
            temporary.unlink(missing_ok=True)

    def replace_original_update_locked(self, capability):
        """Consume only a pinned actual original update, preserving its receipt.

        No catalog/txid/Binding/participant mutation or generic current waiver.
        The source caller owns CLAIMED -> PERSISTING -> PERSISTED -> original
        _send/drain. Its exact operation remains the only update receipt.
        """
        if self._catalog_validating:
            self._catalog_write_refused=True
            raise ValueError('BATCH_ORIGINAL_UPDATE_CATALOG_CALLBACK_REFUSED')
        if self._original_update_validating:
            self._original_update_write_refused=True
            raise ValueError('BATCH_ORIGINAL_UPDATE_CALLBACK_WRITE_REFUSED')
        with self.lock, inventory_store.realm._lock:
            owner=self._original_update_owner
            need(type(owner) is OriginalUpdateOwner and owner.store is self,
                 'BATCH_ORIGINAL_UPDATE_OWNER_REQUIRED')
            record=owner._record(capability)
            need(not record['used'],'BATCH_ORIGINAL_UPDATE_ONCE_REQUIRED')
            owner._check_record(record,phase='PERSISTING')
            doc=owner._checked(record['writer'],record['state'],record['request'])
            need(self._raw==record['raw'] and encoded(doc)==record['document'],
                 'BATCH_ORIGINAL_UPDATE_STALE_PREIMAGE')
            owner._guard_call(owner._replacement,record,doc)
            value=deepcopy(doc)
            row=next(r for r in value['canonical']['inventories'] if r['uid']==record['uid'])
            row['frame']=record['new'].hex()
            revision=value['revisions'][str(record['uid'])]
            need(revision<(1<<63)-1,'BATCH_ORIGINAL_UPDATE_REVISION_OVERFLOW')
            value['revisions'][str(record['uid'])]=revision+1
            plan=encoded(value)
            owner._check_record(record,phase='PERSISTING')
            record['used']=True  # Once BEFORE any durable IO or validation callback.
            self._original_update_commit=capability
            try:
                self._replace(value)
                need(encoded(value)==plan and encoded(self.data)==plan,
                     'BATCH_ORIGINAL_UPDATE_PLAN_CHANGED')
                record['committed']=True
                return True
            except BaseException:
                self.failed=True  # Persist was attempted; ambiguous outcomes are terminal.
                raise
            finally:
                self._original_update_commit=None

    def migrate(self, binding, *, expected_sha256, participants):
        """Explicit same-file private migration; no source/character edits."""
        with self.lock, inventory_store.realm._lock:
            current = self._current(binding)
            need(current['version'] in (1,2) and hashlib.sha256(self._raw).hexdigest() == expected_sha256,
                 'BATCH_EXACT_LEGACY_MIGRATION_REQUIRED')
            rows = self._validate_canonical(current)
            need(binding.uid in rows and type(participants) is dict and
                 set(participants) <= set(self.capabilities), 'BATCH_MIGRATION_PARTICIPANT_CAPABILITY')
            participants=deepcopy(participants)  # Only validated detached seed inputs survive callbacks.
            revisions = {str(u):1 for u in rows}
            if current['version'] == 2:
                row, = current['collections']
                need(row['owner'] == 'PLAYER' and row['phase'] in ('READY','RETURNED'),
                     'BATCH_GROUND_OR_PENDING_CUSTODY_MIGRATION_REFUSED')
                revisions[str(row['character_uid'])] = row['revision']
            docs = {}
            for name,document in participants.items():
                self.capabilities[name].check(document)
                self.capabilities[name].change(None,document,binding.uid)
                if name=='RESOURCE':
                    self._resource_authority(binding,self.capabilities[name],None,document,'SEED')
                if name=='SHOP-QUEST':need(not any(r['rewarded'] for r in document['states']),
                                         'BATCH_SETUP_CANNOT_MINT_REWARD')
                key=self.capabilities[name].key(binding.uid)
                docs[key] = dict(revision=0,digest=digest(document),document=deepcopy(document))
            for key,row in docs.items():
                if key.startswith('RESOURCE:'):
                    self._resource_authority(binding,self.capabilities['RESOURCE'],None,row['document'],'COMMIT')
            self._replace(dict(version=3,policy=POLICY,canonical=deepcopy(current),revisions=revisions,
                               participants=docs,markers={},transactions={},pending=None))

    def restore(self, binding):
        with self.lock, inventory_store.realm._lock:
            doc = self._current(binding)
            need(doc['version'] == 3, 'BATCH_EXPLICIT_MIGRATION_REQUIRED')
            rows = self._validate_canonical(doc['canonical'])
            need(binding.uid in rows, 'BATCH_CANONICAL_CHARACTER_MISSING')
            return rows[binding.uid],doc['revisions'][str(binding.uid)]

    def participant(self, binding, name):
        with self.lock:
            doc = self._current(binding)
            need(name in self.capabilities,'BATCH_PARTICIPANT_CAPABILITY_MISSING')
            key=self.capabilities[name].key(binding.uid)
            need(doc['version'] == 3 and key in doc['participants'], 'BATCH_PARTICIPANT_NOT_INSTALLED')
            return deepcopy(doc['participants'][key])

    def _apply(self, canonical, uid, changes):
        rows = self._validate_canonical(canonical)
        need(uid in rows and type(changes) is tuple and len(changes) <= 8 and
             all(type(c) is QuantityChange for c in changes), 'BATCH_EXPLICIT_ASSET_CHANGES')
        items = inventory.validate_current_collection_frame(rows[uid],policy=inventory.COLLECTION_POLICY)
        old = {i.identifier:i for i in items}; new = dict(old)
        seen = set()
        _,keys,_ = inventory._source()
        for c in changes:
            need(type(c.item_uid) is int and 0 < c.item_uid <= 0xffffffff and c.item_uid not in seen
                 and type(c.debit) is type(c.credit) is int and min(c.debit,c.credit) >= 0
                 and c.debit+c.credit > 0, 'BATCH_UNIQUE_POSITIVE_DEBIT_CREDIT')
            seen.add(c.item_uid)
            item = old.get(c.item_uid)
            if item is None:
                need(c.debit == 0 and c.credit > 0 and type(c.credit_frame) is bytes,
                     'BATCH_NEW_CREDIT_CANONICAL_ITEM_REQUIRED')
                item = inventory.validate_frame(c.credit_frame)
                need(item.identifier == c.item_uid and dict(item.raw_fields)[4] == c.credit,
                     'BATCH_CREDIT_ID_QUANTITY_MISMATCH')
                # Global UID collision check covers every stored character.
                for other in rows.values():
                    need(all(i.identifier != c.item_uid for i in inventory.validate_current_collection_frame(
                         other,policy=inventory.COLLECTION_POLICY)), 'BATCH_CREDIT_UID_COLLISION')
                new[c.item_uid] = item
                continue
            need(c.credit_frame is None, 'BATCH_EXISTING_OPAQUE_REPLACEMENT_REFUSED')
            fields = dict(item.raw_fields); q = fields[4]
            need(c.debit <= q and 0 <= q-c.debit+c.credit < 1 << 64, 'BATCH_INSUFFICIENT_OR_OVERFLOW')
            fields[4] = q-c.debit+c.credit
            if fields[4] == 0: new.pop(c.item_uid)
            else: new[c.item_uid] = inventory._values(fields,keys)
        # Storage/current projection may be empty after an exact final debit.
        frame = inventory.build_current_collection(tuple(new.values()),policy=inventory.COLLECTION_POLICY)
        result = deepcopy(canonical)
        if result['version'] == 2:
            row, = result['collections']
            need(row['character_uid'] == uid and row['owner'] == 'PLAYER' and
                 row['phase'] in ('READY','RETURNED'), 'BATCH_CURRENT_PLAYER_CUSTODY_REQUIRED')
            row['frame_ab'] = frame.hex();row['revision'] += 1
        else:
            for row in result['inventories']:
                if row['uid'] == uid: row['frame'] = frame.hex()
        self._validate_canonical(result)
        return result

    def _equipment(self,canonical,uid):
        """Read the existing equipment authority; never seed/copy it into v3."""
        rows=self._validate_canonical(canonical)
        path=self.profile.with_name('equipment.json')
        need(path.is_file(),'BATCH_EQUIPMENT_AUTHORITY_MISSING')
        # Reuse original path/reparse validation using a read-only typed view
        # of canonical frames, rather than invoking old InventoryStore._read(v3).
        for target in (path,*path.parents):
            if not os.path.lexists(target):continue
            info=target.lstat()
            import stat
            need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,
                 'BATCH_EQUIPMENT_REPARSE')
            if target==path:need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'BATCH_EQUIPMENT_REGULAR')
        limit=equipment_store.EquipmentStore.MAX_BYTES
        with path.open('rb') as stream:
            need(os.fstat(stream.fileno()).st_size<=limit,'BATCH_EQUIPMENT_SIZE')
            raw=stream.read(limit+1)
        need(len(raw)<=limit,'BATCH_EQUIPMENT_SIZE')
        doc=json.loads(raw,object_pairs_hook=unique)
        need(type(doc) is dict and set(doc)=={'version','policy','equipment'} and
             type(doc['version']) is int and doc['version']==1 and doc['policy']==equipment_store.POLICY and
             type(doc['equipment']) is list and len(doc['equipment'])<=3,'BATCH_EQUIPMENT_SCHEMA')
        known={r['uid'] for r in inventory_store._characters(self.profile)['characters']}
        states={}
        for row in doc['equipment']:
            value=equipment_store.EquipmentStore._state(row,known,rows,collection_policy=equipment_store.COLLECTION_POLICY)
            need(value.character_uid not in states,'BATCH_EQUIPMENT_DUPLICATE')
            states[value.character_uid]=value
        need(uid in states,'BATCH_EQUIPMENT_AUTHORITY_MISSING')
        return hashlib.sha256(raw).hexdigest(),states[uid]

    def prepare(self, binding, *, txid, request, catalog_digest, expected_revision,
                changes, participants=()):
        with self.lock, inventory_store.realm._lock:
            doc = self._current(binding)
            need(not any(r['phase'] not in ('DONE','UNKNOWN') for r in self._delivery_caps.values()),
                 'BATCH_ACTIVE_DELIVERY_ASSET_PREPARE_REFUSED')
            need(doc['version'] == 3, 'BATCH_EXPLICIT_MIGRATION_REQUIRED')
            need(type(txid) is str and 1 <= len(txid) <= 128, 'BATCH_TXID_REQUIRED')
            sha = request_digest(request)
            need(type(changes) is tuple and all(type(c) is QuantityChange for c in changes)
                 and type(participants) is tuple and all(type(p) is ParticipantChange for p in participants),
                 'BATCH_TYPED_PLAN_REQUIRED')
            participants=tuple(ParticipantChange(p.name,p.expected_revision,p.expected_digest,
                               deepcopy(p.document),deepcopy(p.reward_markers)) for p in participants)
            need(all(type(p.name) is str for p in participants) and
                 len({p.name for p in participants})==len(participants), 'BATCH_EXACT_PARTICIPANT_CHANGES')
            names=catalog_names(tuple(sorted(p.name for p in participants)))
            # Exact request digest is not the complete server-authorized batch.
            # Bind opaque metadata, debit/credit, participant CAS/docs/markers,
            # expected revision, catalog and selected UID independently.
            batch_sha=digest(dict(uid=binding.uid,request_sha=sha,catalog=catalog_digest,
                expected_revision=expected_revision,
                changes=[dict(uid=c.item_uid,debit=c.debit,credit=c.credit,
                    credit_frame=None if c.credit_frame is None else c.credit_frame.hex()) for c in changes],
                participants=[dict(name=p.name,expected_revision=p.expected_revision,
                    expected_digest=p.expected_digest,document=p.document,markers=p.reward_markers) for p in participants]))
            previous = doc['transactions'].get(txid)
            if previous is not None:
                need(previous['uid'] == binding.uid and previous['request_sha'] == sha,
                     'BATCH_TXID_REQUEST_COLLISION')
                need(previous['batch_sha']==batch_sha,'BATCH_TXID_COMPLETE_BATCH_COLLISION')
                return deepcopy(previous)  # Receipt only; NEVER another reservation/send.
            need(doc['pending'] is None and len(doc['transactions']) < MAX_TRANSACTIONS,
                 'BATCH_PENDING_OR_RECEIPT_BOUND')
            need(type(expected_revision) is int and doc['revisions'].get(str(binding.uid)) == expected_revision,
                 'BATCH_INVENTORY_REVISION_CHANGED')
            self._catalog_authority(binding,catalog_digest,names)
            canonical = self._apply(doc['canonical'],binding.uid,changes)
            equipment_sha=None
            if changes:
                equipment_sha,equipment=self._equipment(doc['canonical'],binding.uid)
                need(all(c.debit==0 or c.item_uid!=equipment.weapon_uid for c in changes),
                     'BATCH_EQUIPPED_ITEM_DEBIT_REFUSED')
                # Existing anchor and equipped UID must still validate after
                # the complete proposed frame; no automatic equipment rewrite.
                next_sha,next_equipment=self._equipment(canonical,binding.uid)
                need(next_sha==equipment_sha and next_equipment==equipment,'BATCH_EQUIPMENT_CHANGED')
            need(type(participants) is tuple and all(type(p) is ParticipantChange for p in participants)
                 and len({p.name for p in participants}) == len(participants), 'BATCH_EXACT_PARTICIPANT_CHANGES')
            nextdocs,markers = {},deepcopy(doc['markers'])
            for p in participants:
                need(p.name in self.capabilities, 'BATCH_PARTICIPANT_CAPABILITY_MISSING')
                cap=self.capabilities[p.name];key=cap.key(binding.uid)
                before = doc['participants'].get(key)
                if before is None:
                    need(p.expected_revision == -1 and p.expected_digest == digest(None) and not changes,
                         'BATCH_EXPLICIT_PARTICIPANT_SETUP_REQUIRED')
                    before=dict(revision=-1,digest=digest(None),document=None)
                need(before['revision'] == p.expected_revision and before['digest'] == p.expected_digest,
                     'BATCH_PARTICIPANT_REVISION_DIGEST_CHANGED')
                cap.change(before['document'],p.document,binding.uid)
                if p.name=='RESOURCE':
                    self._resource_authority(binding,cap,before['document'],p.document,
                                             'SEED' if before['document'] is None else 'PREPARE')
                if p.name=='SHOP-QUEST':
                    need(p.document['catalog_sha']==catalog_digest,'BATCH_PARTICIPANT_CATALOG_CHANGED')
                    prior={} if before['document'] is None else {r['quest']:r['rewarded'] for r in before['document']['states']}
                    required={r['quest'] for r in p.document['states'] if r['rewarded'] and not prior.get(r['quest'],False)}
                    need(set(p.reward_markers)==required,'BATCH_REWARD_MARKER_TRANSITION_REQUIRED')
                    need(before['document'] is not None or not required,'BATCH_SETUP_CANNOT_MINT_REWARD')
                need(type(p.reward_markers) is tuple and all(type(k) is str and 0 < len(k) <= 128 for k in p.reward_markers)
                     and len(set(p.reward_markers)) == len(p.reward_markers), 'BATCH_EXACT_REWARD_MARKERS')
                for marker in p.reward_markers:
                    markerkey = str(binding.uid)+':'+marker
                    need(markerkey not in markers.setdefault(key,{}), 'BATCH_REWARD_ALREADY_COMMITTED')
                    markers[key][markerkey] = txid
                nextdocs[key] = dict(revision=before['revision']+1,digest=digest(p.document),document=deepcopy(p.document))
            plan = dict(canonical=canonical,participants=nextdocs,markers=markers,equipment_sha=equipment_sha)
            tx = dict(uid=binding.uid,request_sha=sha,batch_sha=batch_sha,catalog=catalog_digest,generation=binding.generation_key,
                      plan_sha=digest(plan),phase='PREPARED',asset_revision=expected_revision+1,
                      participants={k:v['digest'] for k,v in nextdocs.items()},delivery='UNATTEMPTED')
            nextvalue=deepcopy(doc);nextvalue['transactions'][txid]=tx;nextvalue['pending']=txid
            self._replace(nextvalue)
            reservation=Reservation(txid,binding.uid,sha,binding,object())
            self.active=(reservation,plan)
            return reservation

    def _reservation(self, binding, reservation):
        doc = self._current(binding)
        need(type(reservation) is Reservation and self.active is not None and
             self.active[0] is reservation and reservation.binding is binding and
             reservation.uid == binding.uid and doc['pending'] == reservation.operation_id,
             'BATCH_EXACT_LIVE_RESERVATION_REQUIRED')
        tx=doc['transactions'][reservation.operation_id]
        need(tx['phase'] == 'PREPARED' and tx['request_sha'] == reservation.request_sha and
             tx['generation'] == binding.generation_key and tx['plan_sha'] == digest(self.active[1]),
             'BATCH_PREPARED_OPERATION_CHANGED')
        self._catalog_authority(binding,tx['catalog'],self._plan_catalog_names(binding,self.active[1],tx))
        return doc,tx

    def commit(self, binding, reservation):
        with self.lock, inventory_store.realm._lock:
            doc,tx=self._reservation(binding,reservation);plan=self.active[1]
            if plan['equipment_sha'] is not None:
                current_sha,_=self._equipment(doc['canonical'],binding.uid)
                need(current_sha==plan['equipment_sha'],'BATCH_EQUIPMENT_CHANGED')
            for key,row in plan['participants'].items():
                if key.startswith('RESOURCE:'):
                    before=doc['participants'].get(key)
                    self._resource_authority(binding,self.capabilities['RESOURCE'],
                        None if before is None else before['document'],row['document'],'COMMIT',
                        reservation=reservation)
            # The resource owner/equipment path may run other synchronous
            # validators. Reconfirm this same catalog/plan at the final write boundary.
            doc,tx=self._reservation(binding,reservation)
            need(self.active[1] is plan,'BATCH_EXACT_LIVE_CATALOG_PLAN_REQUIRED')
            nextvalue=deepcopy(doc)
            nextvalue['canonical']=plan['canonical']
            nextvalue['participants'].update(plan['participants']);nextvalue['markers']=plan['markers']
            nextvalue['revisions'][str(binding.uid)]=tx['asset_revision']
            nextvalue['transactions'][reservation.operation_id]['phase']='COMMITTED'
            nextvalue['pending']=None
            self._replace(nextvalue)  # Assets/docs/markers/receipt ONE durable replacement.
            self.active=None
            return deepcopy(self.data['transactions'][reservation.operation_id])

    def transact(self,binding,**batch):
        """Synchronous caller path within the SAME acquired operation scope."""
        prepared=self.prepare(binding,**batch)
        if type(prepared) is Reservation:return self.commit(binding,prepared)
        need(type(prepared) is dict and prepared['phase']=='COMMITTED','BATCH_EXISTING_OUTCOME_REQUIRES_RECOVERY')
        return prepared  # Historical receipt only, never another delivery.

    def abort(self, binding, reservation):
        with self.lock, inventory_store.realm._lock:
            doc,_=self._reservation(binding,reservation)
            self._abort_record(doc,reservation.operation_id);self.active=None

    def _abort_record(self, doc, txid):
        value=deepcopy(doc);value['transactions'][txid]['phase']='ABORTED';value['pending']=None
        self._replace(value)

    def recover(self, binding, *, txid, request):
        """Read durable outcome under fresh selection; no re-debit or send."""
        with self.lock:
            doc=self._current(binding);tx=doc['transactions'].get(txid)
            need(tx is not None and tx['uid']==binding.uid and tx['request_sha']==request_digest(request),
                 'BATCH_RECOVERY_RECEIPT_MISMATCH')
            return deepcopy(tx)

    def lookup(self,binding,*,txid,request_sha):
        """Read-only lookup before consumer replanning; never executes a batch."""
        with self.lock:
            doc=self._current(binding)
            need(doc['version']==3,'BATCH_EXPLICIT_MIGRATION_REQUIRED')
            tx=doc['transactions'].get(txid)
            if tx is None:return None
            need(tx['uid']==binding.uid and tx['request_sha']==request_sha,'BATCH_TXID_REQUEST_COLLISION')
            return deepcopy(tx)

    def abort_recovered_prepared(self,binding,*,txid,request):
        with self.lock, inventory_store.realm._lock:
            tx=self.recover(binding,txid=txid,request=request)
            need(self.active is None and tx['phase']=='PREPARED' and self.data['pending']==txid,
                 'BATCH_RECOVERY_ABORT_PRECOMMIT_ONLY')
            self._abort_record(self.data,txid)

    def delivery(self,binding,*,txid,request,state):
        """Caller-owned send lifecycle. Never sends or retries client packets."""
        with self.lock, inventory_store.realm._lock:
            tx=self.recover(binding,txid=txid,request=request)
            transitions={'UNATTEMPTED':('WRITE_ATTEMPTED',),'WRITE_ATTEMPTED':('DRAINED','UNKNOWN')}
            need(tx['phase']=='COMMITTED' and state in transitions.get(tx['delivery'],()),
                 'BATCH_DELIVERY_ONCE_TRANSITION_REQUIRED')
            value=deepcopy(self.data);value['transactions'][txid]['delivery']=state;self._replace(value)

    def close(self):
        # PREPARED is retained for explicit fresh-owner abort; COMMITTED never
        # rolled back, delivery UNKNOWN never converted to a successful drain.
        with self.lock:
            if self._original_update_owner is not None:self._original_update_owner.close()
            self.closed=True;self.active=None
            for record in tuple(self._delivery_caps.values()):self.retire_delivery(record['cap'])
            self._delivery_caps.clear();self._delivery_issuance.clear()
            self._delivery_owner=self._delivery_owner_method=self._projection_owner_method=None
            if _OWNERS.get(self._key) is self: _OWNERS.pop(self._key,None)

    def _issuance(self,binding):
        """Identity-indexed weak Binding tombstone, no strong parent/generation refs."""
        key=id(binding);row=self._delivery_issuance.get(key)
        if row is not None:
            need(row['binding']() is binding,'BATCH_ISSUANCE_BINDING_IDENTITY')
            return row
        owner=weakref.ref(self)
        def expired(reference):
            store=owner()
            if store is not None:
                with store.lock:
                    current=store._delivery_issuance.get(key)
                    if current is not None and current['binding'] is reference:
                        store._delivery_issuance.pop(key,None)
        row=dict(binding=weakref.ref(binding,expired),txids=set(),world=False)
        self._delivery_issuance[key]=row
        return row

    def retire_delivery(self,cap):
        """Revoke issued delivery or projection cap; no current scope or receipt IO."""
        with self.lock:
            need(type(cap) is DeliveryCapability and cap.store is self and
                 cap.token in self._delivery_caps and self._delivery_caps[cap.token]['cap'] is cap,
                 'BATCH_ISSUED_DELIVERY_CAPABILITY_REQUIRED')
            record=self._delivery_caps.pop(cap.token);record['closed']=True
            # The caller may retain a revoked opaque handle. It must not retain
            # the original generation, source parent, operations or wire images.
            for name in ('store','binding','owner','parent','transport','task','token'):
                object.__setattr__(cap,name,None)
            object.__setattr__(cap,'frames',())
            object.__setattr__(cap,'receipt_raw',b'')
            object.__setattr__(cap,'request',b'')
            object.__setattr__(cap,'txid',None)

    def register_delivery_owner(self,owner):
        with self.lock:
            need(not self.failed and not self.closed and self._delivery_owner is None
                 and isinstance(owner,DeliveryOwner),'BATCH_SINGLE_BOOTSTRAP_DELIVERY_OWNER_REQUIRED')
            method=owner.validate_operation
            need(inspect.ismethod(method) and method.__self__ is owner and
                 not inspect.iscoroutinefunction(method),'BATCH_SYNC_DELIVERY_OWNER_REQUIRED')
            projection=owner.validate_projection_read
            need(inspect.ismethod(projection) and projection.__self__ is owner and
                 not inspect.iscoroutinefunction(projection),'BATCH_SYNC_PROJECTION_OWNER_REQUIRED')
            self._delivery_owner,self._delivery_owner_method=owner,method.__func__
            self._projection_owner_method=projection.__func__

    def _delivery_owner_check(self,cap,participant,index,wire,phase):
        record=self._delivery_caps[cap.token]
        projection=record.get('kind')=='PROJECTION'
        method=(self._delivery_owner.validate_projection_read if projection else
                self._delivery_owner.validate_operation)
        need(cap.owner is self._delivery_owner and inspect.ismethod(method) and
             method.__self__ is cap.owner and method.__func__ is
             (record['owner_method'] if projection else self._delivery_owner_method),
             'BATCH_REGISTERED_DELIVERY_OWNER_CHANGED')
        need(not self._delivery_validating,'BATCH_REENTRANT_DELIVERY_OWNER_CALLBACK_REFUSED')
        raw=self._raw;active=self.active
        fields=('index','phase','drain','sent','closed','raw')
        state=tuple(record[k] for k in fields)
        self._delivery_validating=True
        try:
            if projection:
                need(participant is cap.parent,'BATCH_EXACT_WORLD_OPERATION_REQUIRED')
                value=method(cap.parent,cap.binding,participants=json.loads(cap.receipt_raw),
                             index=index,wire=wire,phase=phase)
            else:
                value=method(cap.parent,cap.binding,txid=cap.txid,request=cap.request,
                    receipt=json.loads(cap.receipt_raw),participant=participant,index=index,wire=wire,phase=phase)
        finally:
            self._delivery_validating=False
            if self._raw!=raw:
                self.failed=True
                raise ValueError('BATCH_DELIVERY_OWNER_PREIMAGE_CHANGED')
            need(self.active is active and tuple(record[k] for k in fields)==state,
                 'BATCH_DELIVERY_OWNER_MUTATION_REFUSED')
            actual,doc=self._read()
            need(actual==raw and doc==self.data,'BATCH_DELIVERY_OWNER_PREIMAGE_CHANGED')
        if inspect.isawaitable(value):
            if inspect.iscoroutine(value):value.close()
            raise ValueError('BATCH_DELIVERY_OWNER_AWAITABLE_REFUSED')
        need(value is True,'BATCH_DELIVERY_OWNER_OPERATION_REFUSED')

    def open_delivery(self,binding,owner,parent,*,txid,request,receipt,frames):
        with self.lock,inventory_store.realm._lock:
            doc=self._current(binding)
            need(owner is self._delivery_owner and owner is not None and parent is not None,
                 'BATCH_REGISTERED_DELIVERY_OWNER_REQUIRED')
            need(doc['version']==3 and doc['pending'] is None and self.active is None,
                 'BATCH_QUIESCENT_COMMITTED_DELIVERY_REQUIRED')
            tx=doc['transactions'].get(txid)
            need(type(receipt) is dict and tx==receipt and tx is not None and tx['phase']=='COMMITTED'
                 and tx['delivery']=='UNATTEMPTED' and tx['uid']==binding.uid
                 and tx['request_sha']==request_digest(request) and tx['generation']==binding.generation_key,
                 'BATCH_SAME_OWNED_OPERATION_COMMIT_RECEIPT_REQUIRED')
            issuance=self._issuance(binding)
            need(txid not in issuance['txids'],'BATCH_DELIVERY_TX_ALREADY_ISSUED')
            need(type(frames) is tuple and 1<=len(frames)<=5 and all(type(w) is bytes and
                 6<=len(w)<=65535 and int.from_bytes(w[:2],'little')==len(w) for w in frames),
                 'BATCH_EXACT_BOUNDED_DELIVERY_FRAME_TUPLE')
            self._delivery_digests(doc,tx,binding)
            policy=binding.generation.row['policy_row']
            need(type(policy.sent) is int and policy.sent>=0,'BATCH_DELIVERY_SENT_BASE')
            cap=object.__new__(DeliveryCapability)
            for name,value in dict(store=self,binding=binding,owner=owner,parent=parent,txid=txid,
                request=request,receipt_raw=encoded(receipt),frames=frames,transport=binding.writer.transport,
                task=asyncio.current_task(),thread=threading.get_ident(),token=object()).items():
                object.__setattr__(cap,name,value)
            issuance['txids'].add(txid)
            record=dict(cap=cap,kind='DELIVERY',index=0,phase='OPEN',drain=None,sent=policy.sent,closed=False,raw=self._raw)
            self._delivery_caps[cap.token]=record
            try:
                self._delivery_current(cap,None,0,frames[0],'BEFORE_RESERVE')
            except BaseException:
                self.retire_delivery(cap)
                raise
            return cap

    def _delivery_digests(self,doc,tx,binding):
        need(tx['uid']==binding.uid and tx['phase']=='COMMITTED','BATCH_DELIVERY_CURRENT_COMMITTED_UID')
        for key,expected in tx['participants'].items():
            row=doc['participants'].get(key)
            need(row is not None and row['digest']==expected==digest(row['document']),
                 'BATCH_DELIVERY_PARTICIPANT_DIGEST_CHANGED')

    def _delivery_current(self,cap,participant,index,wire,phase):
        self._delivery_validate(cap,participant,index,wire,phase)
        self._delivery_owner_check(cap,participant,index,wire,phase)
        return self._delivery_validate(cap,participant,index,wire,phase)

    def inventory_for_delivery(self,cap,*,participant,index,wire,phase):
        """Exact committed delivery's CURRENT selected asset projection only.

        This is not a new persistence/selection/delivery capability. WORLD
        projections and historical receipts from an older asset revision cannot
        read another transaction's canonical frame.
        """
        with self.lock, inventory_store.realm._lock:
            record,doc,tx=self._delivery_current(cap,participant,index,wire,phase)
            need(record.get('kind')=='DELIVERY' and tx is not None,
                 'BATCH_DELIVERY_INVENTORY_TRANSACTION_ONLY')
            uid=cap.binding.uid
            need(tx['uid']==uid,'BATCH_DELIVERY_INVENTORY_SELECTED_UID')
            revision=doc['revisions'].get(str(uid))
            need(revision==tx['asset_revision'],
                 'BATCH_DELIVERY_INVENTORY_ASSET_REVISION_CHANGED')
            frames=self._validate_canonical(doc['canonical'])
            need(uid in frames and type(frames[uid]) is bytes,
                 'BATCH_DELIVERY_INVENTORY_CANONICAL_FRAME_REQUIRED')
            return frames[uid],revision

    def _delivery_validate(self,cap,participant,index,wire,phase,*,terminal=False):
        need(type(cap) is DeliveryCapability and cap.store is self and cap.token in self._delivery_caps,
             'BATCH_ISSUED_DELIVERY_CAPABILITY_REQUIRED')
        record=self._delivery_caps[cap.token]
        need(record['cap'] is cap and not record['closed'] and not self.failed and not self.closed
             and _OWNERS.get(self._key) is self and cap.task is asyncio.current_task()
             and cap.thread==threading.get_ident(),'BATCH_CURRENT_DELIVERY_SCOPE_REQUIRED')
        if cap.task is not None and cap.task.cancelling() and not (terminal and phase=='UNKNOWN'):
            raise asyncio.CancelledError()
        guard=(self.provider.terminal_delivery_current if terminal else self.provider.delivery_current)
        need(guard(cap.binding) is True,'BATCH_DELIVERY_SELECTED_SCOPE_REQUIRED')
        need(self.active is None,'BATCH_DELIVERY_ASSET_RESERVATION_REFUSED')
        need(type(index) is int and 0<=index<len(cap.frames) and wire is cap.frames[index]
             and phase in ('BEFORE_RESERVE','BEFORE_WRITE_CHECKPOINT','BEGIN_WRITE','DRAIN_PENDING','AFTER_DRAIN','UNKNOWN'),
             'BATCH_EXACT_DELIVERY_INDEX_WIRE_PHASE')
        allowed=index==record['index'] or (phase=='AFTER_DRAIN' and index==record['index']-1
                                         and record['phase'] in ('BETWEEN','DONE'))
        need(allowed,'BATCH_DELIVERY_FRAME_ORDER_REQUIRED')
        writer=cap.binding.writer;row=cap.binding.generation.row;policy=row['policy_row']
        need(writer.transport is cap.transport,'BATCH_DELIVERY_TRANSPORT_CHANGED')
        need(type(policy.sent) is int and type(policy.pending_size) is int and
             (policy.pending_opcode is None or type(policy.pending_opcode) is int) and
             (policy.drain_started_ns is None or type(policy.drain_started_ns) is int),
             'BATCH_EXACT_TRANSPORT_COUNTER_TYPES')
        queued=writer.transport.get_write_buffer_size()
        need(type(queued) is int and queued>=0,'BATCH_DELIVERY_QUEUE_REQUIRED')
        opcode=int.from_bytes(wire[2:4],'little');sent=record['sent']+index
        if phase in ('BEFORE_RESERVE','BEFORE_WRITE_CHECKPOINT'):
            need(record['phase'] in ('OPEN','BETWEEN') and policy.pending_opcode is None and
                 policy.pending_size==0 and policy.drain_started_ns is None and policy.sent==sent,
                 'BATCH_DELIVERY_QUIESCENT_FRAME_PHASE')
        elif phase in ('BEGIN_WRITE','DRAIN_PENDING'):
            need(policy.pending_opcode==opcode and policy.pending_size==len(wire) and
                 policy.drain_started_ns is not None and policy.sent==sent,
                 'BATCH_DELIVERY_EXACT_PENDING_FRAME_PHASE')
            if phase=='DRAIN_PENDING':
                need(record['phase']=='WRITING' and policy.drain_started_ns==record['drain'],
                     'BATCH_DELIVERY_SAME_DRAIN_RESERVATION')
        elif phase=='AFTER_DRAIN':
            need(record['phase'] in ('WRITING','BETWEEN','DONE') and queued==0 and policy.pending_opcode is None
                 and policy.pending_size==0 and policy.drain_started_ns is None and policy.sent==sent+1,
                 'BATCH_DELIVERY_EXACT_AFTER_DRAIN_PHASE')
        else:
            same_pending=(policy.pending_opcode==opcode and policy.pending_size==len(wire) and
                          policy.drain_started_ns==record['drain'] and policy.sent==sent)
            after_drain=(queued==0 and policy.pending_opcode is None and policy.pending_size==0 and
                         policy.drain_started_ns is None and policy.sent==sent+1)
            need(record['phase']=='WRITING' and (same_pending or after_drain),
                 'BATCH_DELIVERY_UNKNOWN_REQUIRES_EXACT_ATTEMPT')
        raw,doc=self._read()
        need(raw==self._raw==record['raw'] and doc==self.data and doc['pending'] is None,
             'BATCH_DELIVERY_PREIMAGE_CHANGED')
        if record.get('kind')=='PROJECTION':
            need(phase!='UNKNOWN','BATCH_PROJECTION_HAS_NO_RECEIPT_TRANSITION')
            expected=json.loads(cap.receipt_raw)
            for name,row in expected.items():
                key=self.capabilities[name].key(cap.binding.uid)
                need(doc['participants'].get(key)==row and row['digest']==digest(row['document']),
                     'BATCH_PROJECTION_PARTICIPANT_CHANGED')
            return record,doc,None
        tx=doc['transactions'].get(cap.txid);original=json.loads(cap.receipt_raw)
        need(type(tx) is dict and {k:v for k,v in tx.items() if k!='delivery'}==
             {k:v for k,v in original.items() if k!='delivery'},'BATCH_DELIVERY_RECEIPT_CHANGED')
        self._delivery_digests(doc,tx,cap.binding)
        expected=('DRAINED' if record['phase']=='DONE' else 'UNATTEMPTED' if
                  record['phase']=='OPEN' and record['index']==0 else 'WRITE_ATTEMPTED')
        need(tx['delivery']==expected,'BATCH_DELIVERY_RECEIPT_STATE_CHANGED')
        return record,doc,tx

    def participant_for_delivery(self,cap,name,*,participant,index,wire,phase):
        with self.lock,inventory_store.realm._lock:
            _,doc,tx=self._delivery_current(cap,participant,index,wire,phase)
            need(tx is not None,'BATCH_RECEIPT_DELIVERY_CAPABILITY_REQUIRED')
            need(name in self.capabilities,'BATCH_DELIVERY_PARTICIPANT_CAPABILITY')
            key=self.capabilities[name].key(cap.binding.uid)
            need(key in tx['participants'],'BATCH_DELIVERY_RECEIPT_PARTICIPANT_REQUIRED')
            return deepcopy(doc['participants'][key])

    def receipt_for_delivery(self,cap,*,participant,index,wire,phase):
        with self.lock,inventory_store.realm._lock:
            _,_,tx=self._delivery_current(cap,participant,index,wire,phase)
            need(tx is not None,'BATCH_RECEIPT_DELIVERY_CAPABILITY_REQUIRED')
            return deepcopy(tx)

    def mark_delivery(self,cap,*,participant,index,wire,phase,state):
        with self.lock,inventory_store.realm._lock:
            record,doc,tx=self._delivery_current(cap,participant,index,wire,phase)
            need(tx is not None,'BATCH_RECEIPT_DELIVERY_CAPABILITY_REQUIRED')
            need((phase,state) in (('BEGIN_WRITE','WRITE_ATTEMPTED'),('AFTER_DRAIN','DRAINED'),('UNKNOWN','UNKNOWN')),
                 'BATCH_DELIVERY_MARK_PHASE_STATE')
            value=deepcopy(doc)
            if state=='WRITE_ATTEMPTED':
                need(index==record['index'] and record['phase'] in ('OPEN','BETWEEN'),
                     'BATCH_DELIVERY_SINGLE_FRAME_ATTEMPT')
                if index==0:
                    need(tx['delivery']=='UNATTEMPTED','BATCH_DELIVERY_FIRST_ATTEMPT_ONLY')
                    value['transactions'][cap.txid]['delivery']='WRITE_ATTEMPTED';self._replace(value)
                    record['raw']=self._raw
                else:need(tx['delivery']=='WRITE_ATTEMPTED','BATCH_DELIVERY_BATCH_ALREADY_ATTEMPTED')
                record['phase']='WRITING';record['drain']=cap.binding.generation.row['policy_row'].drain_started_ns
            elif state=='DRAINED':
                need(record['phase']=='WRITING' and index==record['index'] and tx['delivery']=='WRITE_ATTEMPTED',
                     'BATCH_DELIVERY_SINGLE_FRAME_DRAIN')
                if index==len(cap.frames)-1:
                    value['transactions'][cap.txid]['delivery']='DRAINED';self._replace(value)
                    record['raw']=self._raw;record['phase']='DONE'
                else:record['phase']='BETWEEN'
                record['index']+=1;record['drain']=None
            else:
                need(tx['delivery']=='WRITE_ATTEMPTED','BATCH_DELIVERY_UNKNOWN_NO_NEW_ATTEMPT')
                value['transactions'][cap.txid]['delivery']='UNKNOWN';self._replace(value)
                record['raw']=self._raw
                record['phase']='UNKNOWN';record['closed']=True

    def terminal_unknown(self,cap,index,wire,*,participant=None):
        """Failure-only monotonic metadata transition, never a read/send admission."""
        with self.lock,inventory_store.realm._lock:
            record,doc,tx=self._delivery_validate(cap,participant,index,wire,'UNKNOWN',terminal=True)
            need(record.get('kind')=='DELIVERY' and tx is not None and
                 tx['delivery']=='WRITE_ATTEMPTED','BATCH_TERMINAL_EXACT_WRITE_ATTEMPT_REQUIRED')
            self._delivery_owner_check(cap,participant,index,wire,'UNKNOWN')
            record,doc,tx=self._delivery_validate(cap,participant,index,wire,'UNKNOWN',terminal=True)
            value=deepcopy(doc);value['transactions'][cap.txid]['delivery']='UNKNOWN'
            self._replace(value);record['raw']=self._raw;record['phase']='UNKNOWN';record['closed']=True

    def open_projection_read(self,binding,owner,parent,participants,frames):
        """Existing WORLD RESOURCE, optionally sealed with canonical SKILL; no seed."""
        with self.lock,inventory_store.realm._lock:
            doc=self._current(binding)
            need(doc['version']==3,'BATCH_PROJECTION_RESOURCE_MIGRATION_REQUIRED')
            need(owner is self._delivery_owner and owner is not None and parent is not None and
                 type(participants) is tuple and participants in (('RESOURCE',),('RESOURCE','SKILL')),
                 'BATCH_EXISTING_RESOURCE_PROJECTION_ONLY')
            need(self.active is None and doc['pending'] is None,'BATCH_QUIESCENT_PROJECTION_REQUIRED')
            issuance=self._issuance(binding)
            need(not issuance['world'],'BATCH_WORLD_PROJECTION_ALREADY_ISSUED')
            need(type(frames) is tuple and 1<=len(frames)<=5 and all(type(w) is bytes and
                 6<=len(w)<=65535 and int.from_bytes(w[:2],'little')==len(w) for w in frames),
                 'BATCH_EXACT_BOUNDED_WORLD_FRAME_TUPLE')
            method=owner.validate_projection_read
            need(inspect.ismethod(method) and method.__self__ is owner and
                 not inspect.iscoroutinefunction(method) and method.__func__ is self._projection_owner_method,
                 'BATCH_REGISTERED_PROJECTION_OWNER_CHANGED')
            need('RESOURCE' in self.capabilities,'BATCH_RESOURCE_PROJECTION_CAPABILITY_REQUIRED')
            key=self.capabilities['RESOURCE'].key(binding.uid);row=doc['participants'].get(key)
            need(row is not None,'BATCH_EXISTING_RESOURCE_PROJECTION_REQUIRED')
            sealed={'RESOURCE':row}
            if participants==('RESOURCE','SKILL'):
                need('SKILL' in self.capabilities,'BATCH_SKILL_PROJECTION_CAPABILITY_REQUIRED')
                skill=doc['participants'].get(self.capabilities['SKILL'].key(binding.uid))
                need(skill is not None,'BATCH_EXISTING_SKILL_PROJECTION_REQUIRED')
                sealed['SKILL']=skill
            policy=binding.generation.row['policy_row']
            need(type(policy.sent) is int and policy.sent>=0,'BATCH_PROJECTION_SENT_BASE')
            cap=object.__new__(DeliveryCapability)
            for name,value in dict(store=self,binding=binding,owner=owner,parent=parent,txid=None,
                request=b'',receipt_raw=encoded(sealed),frames=frames,
                transport=binding.writer.transport,task=asyncio.current_task(),
                thread=threading.get_ident(),token=object()).items():object.__setattr__(cap,name,value)
            self._delivery_caps[cap.token]=dict(cap=cap,kind='PROJECTION',owner_method=method.__func__,
                index=0,phase='OPEN',drain=None,sent=policy.sent,closed=False,raw=self._raw)
            issuance['world']=True
            try:self._delivery_current(cap,parent,0,frames[0],'BEFORE_RESERVE')
            except BaseException:self.retire_delivery(cap);raise
            return cap

    def participant_for_projection(self,cap,name,*,participant,index,wire,phase):
        with self.lock,inventory_store.realm._lock:
            record,doc,tx=self._delivery_current(cap,participant,index,wire,phase)
            need(record.get('kind')=='PROJECTION' and name in json.loads(cap.receipt_raw) and tx is None,
                 'BATCH_WORLD_PROJECTION_CAPABILITY_REQUIRED')
            if phase=='BEGIN_WRITE':
                if record['phase'] in ('OPEN','BETWEEN'):
                    record['phase']='WRITING';record['drain']=cap.binding.generation.row['policy_row'].drain_started_ns
                else:need(record['phase']=='WRITING' and record['drain']==
                          cap.binding.generation.row['policy_row'].drain_started_ns,'BATCH_PROJECTION_SAME_WRITE')
            elif phase=='AFTER_DRAIN' and record['phase']=='WRITING':
                record['phase']='DONE' if index==len(cap.frames)-1 else 'BETWEEN'
                record['index']+=1;record['drain']=None
            return deepcopy(doc['participants'][self.capabilities[name].key(cap.binding.uid)])

    def _catalog_authority(self,binding,catalog_digest,names):
        """Synchronous catalog callback cannot replace this preimage or plan."""
        if self._original_update_validating or self._original_update_commit is not None:
            self._original_update_write_refused=True
            raise ValueError('BATCH_ORIGINAL_UPDATE_CALLBACK_CATALOG_REFUSED')
        catalog_names(names);catalog_sha(catalog_digest)
        need(not self._catalog_validating,'BATCH_REENTRANT_CATALOG_CALLBACK_REFUSED')
        original_owner=self._original_update_owner
        need(original_owner is None or not original_owner._issued,
             'BATCH_CATALOG_ORIGINAL_UPDATE_CAPABILITY_ACTIVE')
        expected_raw=self._raw;active=self.active;provider=self.provider
        active_sha=None if active is None else digest(active[1])
        self._catalog_validating=True;self._catalog_write_refused=False
        try:
            value=provider.catalog_current_for(binding,catalog_digest,names)
        finally:
            self._catalog_validating=False
            if self._raw!=expected_raw:
                self.failed=True
                raise ValueError('BATCH_CATALOG_CALLBACK_PREIMAGE_CHANGED')
            need(self.provider is provider,'BATCH_CATALOG_CALLBACK_PROVIDER_CHANGED')
            self._current(binding)
            need(self.active is active and (active is None or digest(active[1])==active_sha),
                 'BATCH_CATALOG_CALLBACK_ACTIVE_PLAN_CHANGED')
            need(not self._catalog_write_refused,'BATCH_CATALOG_CALLBACK_WRITE_REFUSED')
            need(self._original_update_owner is original_owner and not self._original_update_validating
                 and self._original_update_commit is None and
                 (original_owner is None or not original_owner._issued),
                 'BATCH_CATALOG_ORIGINAL_UPDATE_STATE_CHANGED')
        if inspect.isawaitable(value):
            if inspect.iscoroutine(value):value.close()
            raise ValueError('BATCH_CATALOG_PROVIDER_AWAITABLE_REFUSED')
        need(value is True,'BATCH_SERVER_CATALOG_CHANGED')

    def _plan_catalog_names(self,binding,plan,tx):
        need(set(plan['participants'])==set(tx['participants']),'BATCH_CATALOG_PLAN_PARTICIPANTS_CHANGED')
        names=[]
        for key,row in plan['participants'].items():
            matches=[name for name,cap in self.capabilities.items() if cap.key(binding.uid)==key]
            need(len(matches)==1 and tx['participants'][key]==row['digest'],
                 'BATCH_CATALOG_PLAN_PARTICIPANTS_CHANGED')
            names.append(matches[0])
        return catalog_names(tuple(sorted(names)))


class CanonicalInventorySource(inventory_store.InventoryStore):
    """Explicit private v3 read/restore candidate, using the original ctor.

    super().__init__ performs original policy/path/roster/source checks and
    dispatches this v3 reader. No __new__, temporary downgrade or bypass.
    Existing exact-type public consumers need an explicit reviewed adapter;
    this subclass is accepted only by this private BatchStore/BrokerProvider.
    All inherited mutation funnels refuse v3, so it is not a second writer.
    """
    def __init__(self,profile,*,policy,custody_policy=None,capabilities):
        need(type(capabilities) is tuple and all(type(c) is DocumentCapability for c in capabilities),
             'BATCH_REOPEN_DOCUMENT_CAPABILITIES')
        self._batch_capabilities={c.name:c for c in capabilities}
        need(len(self._batch_capabilities)==len(capabilities),'BATCH_DUPLICATE_DOCUMENT_CAPABILITY')
        self._batch_v3=False
        super().__init__(profile,policy=policy,custody_policy=custody_policy)

    def _read(self,*,_collection_keys=None):
        self._path_check();inventory_store._source();self._custody_binding()
        if not self.path.exists(): return super()._read(_collection_keys=_collection_keys)
        with self.path.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
        need(len(raw)<=MAX_BYTES,'BATCH_STORE_SIZE')
        doc=json.loads(raw,object_pairs_hook=unique)
        if type(doc) is dict and doc.get('version')==3:
            need(type(doc['version']) is int,'BATCH_STORE_OBJECT_VERSION')
            # Explicit strict projection object, never a live/current capability.
            class Projection:
                _validate_canonical=BatchStore._validate_canonical
            check=Projection();check.source=self;check.profile=self.profile;check.capabilities=self._batch_capabilities
            BatchStore._validate(check,doc,raw)
            rows=check._validate_canonical(doc['canonical'])
            known={r['uid'] for r in inventory_store._characters(self.profile)['characters']}
            self._batch_v3=True
            return rows,known
        need(not self._batch_v3,'BATCH_CANONICAL_DOWNGRADE_REFUSED')
        return super()._read(_collection_keys=_collection_keys)

    def _write(self,rows):
        self._read()
        need(not self._batch_v3,'BATCH_LEGACY_MUTATOR_REFUSED')
        return super()._write(rows)

    def _custody_atomic_write(self,value):
        self._read()
        need(not self._batch_v3,'BATCH_LEGACY_MUTATOR_REFUSED')
        return super()._custody_atomic_write(value)

    def custody_snapshot(self,character_uid):
        with inventory_store._lock,inventory_store.realm._lock:
            self._read()
            if self._batch_v3:
                with self.path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
                need(len(raw)<=MAX_BYTES,'BATCH_STORE_SIZE')
                doc=json.loads(raw,object_pairs_hook=unique)
                known={r['uid'] for r in inventory_store._characters(self.profile)['characters']}
                need(doc['canonical']['version']==2,'BATCH_CANONICAL_CUSTODY_NOT_INSTALLED')
                value=item_custody.decode(doc['canonical'],raw,known,str(self.profile))
                need(value.character_uid==character_uid,'BATCH_CUSTODY_CHARACTER_CHANGED')
                return value  # Data projection only; no old transfer-operation authority.
            return super().custody_snapshot(character_uid)


@dataclass(frozen=True,slots=True,init=False)
class OriginalUpdateCapability:
    """Opaque issued one-shot token; retirement drops all operation references."""
    _owner_ref: object = field(repr=False)
    _token: object = field(repr=False)

    def __new__(cls):
        raise ValueError('BATCH_ORIGINAL_UPDATE_ISSUANCE_PRIVATE')


def _update_fingerprint(value):
    if type(value) in (str,bytes,int,bool,type(None)):
        return type(value),value
    if type(value) is tuple:
        return tuple,tuple(_update_fingerprint(v) for v in value)
    return type(value),id(value)


def _update_state_signature(state,*,transition=False):
    ignored={'last_ns'} | ({'phase','persist_attempted'} if transition else set())
    identities={'old','new','wire','changes','refs','authority','request','writer','row','lock','item_use'}
    return tuple((key,id(value) if key in identities else None,_update_fingerprint(value))
                 for key,value in sorted(state.items()) if key not in ignored)


class OriginalUpdateOwner:
    """Pinned original operation validator, never a generic current exception.

    The original server caller supplies only its ACTUAL registered state and
    request. Catalogs/txids/receipts/Binding/intent/selected flags are not issued.
    source_pins are reviewed local source hashes, not client/saved configuration.
    """
    def __init__(self,provider,store,*,source_pins):
        from tools.local_original_session import broker,inventory_update
        need(type(provider) is BrokerProvider and type(store) is BatchStore
             and store.provider is provider and store.source is provider.source_store
             and type(provider.broker) is broker.PersistentBroker
             and type(store.source) is inventory_store.InventoryStore,
             'BATCH_ORIGINAL_UPDATE_EXACT_RUNTIME')
        need(type(source_pins) is dict and set(source_pins)=={'broker','inventory_store','inventory_update'}
             and all(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v)
                     for v in source_pins.values()), 'BATCH_ORIGINAL_UPDATE_SOURCE_PINS')
        self.provider,self.store,self.broker=provider,store,provider.broker
        self._issued={};self.closed=False
        self._sources=[]
        specifications=((broker,'PersistentBroker',('_inventory_update_current','_inventory_update_time','_row_operation')),
                        (inventory_store,'InventoryStore',('restore','replace_existing','_read','_path_check')),
                        (inventory_update,None,('source_ready','validate_frame','build_update')))
        for module,class_name,names in specifications:
            path=inventory.observe.ordinary(Path(module.__file__))
            with path.open('rb') as stream:raw=stream.read(1048577)
            expected=source_pins[module.__name__.rsplit('.',1)[-1]]
            need(0<len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==expected,
                 'BATCH_ORIGINAL_UPDATE_SOURCE_CHANGED')
            code=compile(raw,str(path),'exec',dont_inherit=True)
            cls=getattr(module,class_name) if class_name is not None else module
            if class_name is not None:
                code=next(c for c in code.co_consts if type(c) is CodeType and c.co_name==class_name)
            methods=[]
            for name in names:
                fn=getattr(cls,name);unwrapped=inspect.unwrap(fn)
                original=next(c for c in code.co_consts if type(c) is CodeType and c.co_name==name)
                need(unwrapped.__code__==original and unwrapped.__globals__ is module.__dict__,
                     'BATCH_ORIGINAL_UPDATE_ORIGINAL_SOURCE_METHOD')
                methods.append((name,fn,unwrapped,unwrapped.__code__))
            self._sources.append((module,path,expected,class_name,cls,tuple(methods)))
        self._validator=broker.PersistentBroker._inventory_update_current
        self._update_module=inventory_update
        need(store._original_update_owner is None and not store.closed and not store.failed,
             'BATCH_ORIGINAL_UPDATE_SINGLE_OWNER')
        store._original_update_owner=self
        self._source_check()

    def _source_check(self):
        need(not self.closed and self.store._original_update_owner is self,
             'BATCH_ORIGINAL_UPDATE_OWNER_CLOSED')
        for module,path,expected,class_name,cls,methods in self._sources:
            need(sys.modules.get(module.__name__) is module and Path(module.__file__)==path
                 and (class_name is None or getattr(module,class_name) is cls),
                 'BATCH_ORIGINAL_UPDATE_SOURCE_CLASS_CHANGED')
            inventory.observe.ordinary(path)
            with path.open('rb') as stream:raw=stream.read(1048577)
            need(0<len(raw)<=1048576 and hashlib.sha256(raw).hexdigest()==expected,
                 'BATCH_ORIGINAL_UPDATE_SOURCE_CHANGED')
            for name,fn,unwrapped,code in methods:
                need(getattr(cls,name) is fn and inspect.unwrap(fn) is unwrapped
                     and unwrapped.__code__ is code and unwrapped.__globals__ is module.__dict__,
                     'BATCH_ORIGINAL_UPDATE_SOURCE_METHOD_CHANGED')
        method=self.broker._inventory_update_current
        need(type(method) is MethodType and method.__self__ is self.broker and method.__func__ is self._validator,
             'BATCH_ORIGINAL_UPDATE_BOUND_VALIDATOR_CHANGED')

    def _scope(self,writer,row):
        self._source_check()
        p,s,b=self.provider,self.store,self.broker
        need(type(p) is BrokerProvider and p.broker is b and b._canonical_provider is p
             and s.provider is p and s.source is p.source_store is b._inventory_store
             and type(s.source) is inventory_store.InventoryStore,
             'BATCH_ORIGINAL_UPDATE_RUNTIME_CHANGED')
        scope=p._scope
        need(scope is not None,'BATCH_ORIGINAL_UPDATE_OWNED_SCOPE_REQUIRED')
        p._connection(writer,row,scope=scope)
        generation=b.inventory_selection_current(writer)
        need(generation is b._inventory_generation and generation.writer is writer
             and generation.row is row and generation.lock is row['operation_lock']
             and generation.store is s.source and generation.phase=='ACTIVE',
             'BATCH_ORIGINAL_UPDATE_CURRENT_GENERATION')
        return scope,generation

    def _idle(self):
        s=self.store
        need(not s.failed and not s.closed and _OWNERS.get(s._key) is s
             and s.active is None and s.data.get('pending') is None
             and not s._delivery_validating and not s._catalog_validating
             and not any(r['phase'] not in ('DONE','UNKNOWN') for r in s._delivery_caps.values()),
             'BATCH_ORIGINAL_UPDATE_ACTIVE_OR_FAILED_STORE')

    def _issuance_signature(self):
        return tuple((token,id(record),tuple((k,_update_fingerprint(v)) for k,v in sorted(record.items())),
                      _update_state_signature(record['state']))
                     for token,record in self._issued.items())

    def _context_signature(self):
        b=self.broker
        names=('_canonical_provider','_inventory_store','_inventory_generation','_inventory_service',
               '_inventory_current_frame','_inventory_frame','_inventory_operation_frame',
               '_inventory_selection_binding','_inventory_delivery_authority','_inventory_restore_only',
               '_inventory_attempted','_inventory_write_attempted','_inventory_update_operation','_item_use_session')
        return tuple((name,id(getattr(b,name)),_update_fingerprint(getattr(b,name))) for name in names)

    def _store_signature(self):
        s=self.store
        delivery=tuple((token,id(record),tuple((k,_update_fingerprint(v)) for k,v in sorted(record.items())))
                       for token,record in s._delivery_caps.items())
        return (s.failed,s.closed,id(s.path),str(s.path),id(s.profile),str(s.profile),
                id(s.source),id(s.provider),id(s._original_update_owner),
                id(_OWNERS.get(s._key)),delivery,s._catalog_validating,s._catalog_write_refused,
                id(s.provider.catalog),id(s.provider._catalog_owner),id(s.provider._catalog_descriptor))

    def _guard_call(self,function,*args):
        s=self.store
        if s._catalog_validating:
            s._catalog_write_refused=True
            raise ValueError('BATCH_ORIGINAL_UPDATE_CATALOG_CALLBACK_REFUSED')
        need(not s._original_update_validating,'BATCH_ORIGINAL_UPDATE_CALLBACK_REENTRY')
        baseline=(s._raw,encoded(s.data),s.active,s._original_update_commit,
                  self._issuance_signature(),self._store_signature(),self._context_signature())
        plan=(encoded(args[0]) if getattr(function,'__func__',None) is BatchStore._validate else None)
        s._original_update_validating=True;s._original_update_write_refused=False
        try:
            return function(*args)
        finally:
            s._original_update_validating=False
            same=(s._raw==baseline[0] and encoded(s.data)==baseline[1] and s.active is baseline[2]
                  and s._original_update_commit is baseline[3] and self._issuance_signature()==baseline[4]
                  and self._store_signature()==baseline[5]
                  and self._context_signature()==baseline[6]
                  and not s._original_update_write_refused and (plan is None or encoded(args[0])==plan))
            if not same:
                s.failed=True
                raise ValueError('BATCH_ORIGINAL_UPDATE_CALLBACK_MUTATION')
            self._source_check()
            for record in self._issued.values():
                scope,generation=self._scope(record['writer'],record['row'])
                need(scope is record['scope'] and generation is record['generation'],
                     'BATCH_ORIGINAL_UPDATE_CALLBACK_SELECTION_CHANGED')
                # The original deadline/cancellation source remains authoritative,
                # including callbacks introduced by full aggregate schema reads.
                self.broker._inventory_update_time(record['state'])

    def _checked(self,writer,state,request):
        s,b=self.store,self.broker
        need(type(state) is dict and b._inventory_update_operation is state and type(request) is tuple
             and state.get('request') is request and state.get('writer') is writer
             and state.get('phase') in ('CLAIMED','PERSISTING'),
             'BATCH_ORIGINAL_UPDATE_ACTUAL_OPERATION_REQUIRED')
        row=state['row'];scope,generation=self._scope(writer,row);self._idle()
        signature=_update_state_signature(state)
        old_raw,old_data=s._raw,encoded(s.data)
        raw,doc=self._guard_call(s._read)
        need(raw==old_raw and encoded(doc)==old_data,'BATCH_ORIGINAL_UPDATE_STALE_PREIMAGE')
        self._guard_call(self._validator.__get__(b,type(b)),writer,row,state,request)
        need(_update_state_signature(state)==signature,'BATCH_ORIGINAL_UPDATE_CALLBACK_OPERATION_CHANGED')
        actual_scope,actual_generation=self._scope(writer,row);self._idle()
        need(actual_scope is scope and actual_generation is generation,
             'BATCH_ORIGINAL_UPDATE_CALLBACK_SELECTION_CHANGED')
        actual_raw,actual_doc=self._guard_call(s._read)
        need(actual_raw==old_raw and encoded(actual_doc)==old_data and s._raw==old_raw
             and encoded(s.data)==old_data,'BATCH_ORIGINAL_UPDATE_CALLBACK_PREIMAGE_CHANGED')
        return actual_doc

    def _replacement(self,record,document):
        state,request=record['state'],record['request']
        need(record['old'] is request[0] is state['old'] and record['new'] is request[1] is state['new']
             and record['wire'] is request[2] is state['wire'], 'BATCH_ORIGINAL_UPDATE_ORIGINAL_FRAMES')
        before=inventory.validate_frame(record['old']);after=inventory.validate_frame(record['new'])
        need(self._update_module.source_ready() is True,'BATCH_ORIGINAL_UPDATE_SOURCE_REQUIRED')
        a,z=dict(before.raw_fields),dict(after.raw_fields)
        changes={k for k in a if a[k]!=z[k]}
        need(before.identifier==after.identifier and bool(changes) and changes<={4,5,7,18}
             and tuple(sorted((k,z[k]) for k in changes))==state['changes'],
             'BATCH_ORIGINAL_UPDATE_WHITELIST_REQUIRED')
        self._update_module.validate_frame(record['wire'])
        need(self._update_module.build_update({1:before.identifier,**dict(state['changes'])})==record['wire'],
             'BATCH_ORIGINAL_UPDATE_EXACT_SOURCE_WIRE')
        need(document['version']==3 and document['canonical']['version']==1,
             'BATCH_ORIGINAL_UPDATE_SINGLETON_V1_ONLY')
        rows=self.store._validate_canonical(document['canonical'])
        need(rows.get(record['uid'])==record['old'],'BATCH_ORIGINAL_UPDATE_CANONICAL_OLD_CHANGED')
        inventory.validate_frame(rows[record['uid']])

    def issue_locked(self,writer,state,request):
        if self.store._catalog_validating:
            self.store._catalog_write_refused=True
            raise ValueError('BATCH_ORIGINAL_UPDATE_CATALOG_CALLBACK_REFUSED')
        need(not self.store._original_update_validating,'BATCH_ORIGINAL_UPDATE_CALLBACK_REENTRY')
        with self.store.lock,inventory_store.realm._lock:
            need(type(state) is dict and state.get('phase')=='CLAIMED'
                 and state.get('persist_attempted') is False and state.get('persisted') is False
                 and state.get('write_attempted') is False and state.get('drain_returned') is False
                 and not self._issued,'BATCH_ORIGINAL_UPDATE_CLAIMED_ONCE')
            doc=self._checked(writer,state,request)
            scope,generation=self._scope(writer,state['row'])
            need(type(state['authority']) is tuple,'BATCH_ORIGINAL_UPDATE_ORIGINAL_AUTHORITY')
            uid=state['authority'][0].uid
            record=dict(writer=writer,state=state,request=request,row=state['row'],scope=scope,
                generation=generation,selection_binding=state['refs'][9],uid=uid,
                invariant=_update_state_signature(state,transition=True),raw=self.store._raw,
                document=encoded(doc),old=state['old'],new=state['new'],wire=state['wire'],used=False,committed=False)
            self._guard_call(self._replacement,record,doc)
            # Codec/source validation above is rechecked against actual current
            # authority and the full aggregate before issuing the opaque token.
            checked=self._checked(writer,state,request)
            need(encoded(checked)==record['document'] and self.store._raw==record['raw'],
                 'BATCH_ORIGINAL_UPDATE_ISSUANCE_CHANGED')
            cap=object.__new__(OriginalUpdateCapability)
            object.__setattr__(cap,'_owner_ref',weakref.ref(self));object.__setattr__(cap,'_token',object())
            record['cap']=cap;self._issued[cap._token]=record
            return cap

    def _record(self,cap):
        need(type(cap) is OriginalUpdateCapability and cap._owner_ref is not None
             and cap._owner_ref() is self and cap._token in self._issued,
             'BATCH_ORIGINAL_UPDATE_ISSUED_CAPABILITY_REQUIRED')
        record=self._issued[cap._token]
        need(record['cap'] is cap,'BATCH_ORIGINAL_UPDATE_EXACT_CAPABILITY')
        return record

    def _check_record(self,record,*,phase):
        self._record(record['cap'])
        scope,generation=self._scope(record['writer'],record['row'])
        state=record['state']
        need(scope is record['scope'] and generation is record['generation']
             and self.broker._inventory_update_operation is state and state['request'] is record['request']
             and state['refs'][9] is record['selection_binding']
             and _update_state_signature(state,transition=True)==record['invariant']
             and state['phase']==phase and state['persist_attempted'] is True
             and state['persisted'] is False and record['new'] is state['new']
             and record['old'] is state['old'] and record['wire'] is state['wire'],
             'BATCH_ORIGINAL_UPDATE_CAPABILITY_OPERATION_CHANGED')

    def retire(self,cap):
        with self.store.lock:
            if type(cap) is not OriginalUpdateCapability:return
            if cap._owner_ref is None or cap._owner_ref() is not self:return
            record=self._issued.pop(cap._token,None)
            if record is not None:record.clear()
            object.__setattr__(cap,'_owner_ref',None);object.__setattr__(cap,'_token',None)

    @contextmanager
    def issued_locked(self,writer,state,request):
        cap=self.issue_locked(writer,state,request)
        try:yield cap
        finally:self.retire(cap)

    def close(self):
        with self.store.lock:
            for record in tuple(self._issued.values()):self.retire(record['cap'])
            self.closed=True
            if self.store._original_update_owner is self:self.store._original_update_owner=None


class SkillBundlePort:
    """Exact current SKILL consumer shape, intentionally missing HP/MP writer.

    Skills can stage a resource-free document in this canonical aggregate.
    Current hp_status is not a durable owner and MP authority is absent.
    Even a zero debit cannot invent the mandatory resource-owner capability.
    """
    atomic_bundle_available=False

    def __init__(self,store,binding):
        need(type(store) is BatchStore and type(binding) is Binding,'BATCH_SKILL_CANONICAL_PORT')
        self.store,self.binding=store,binding

    def commit_bundle(self,reservation,skill_document,resource_debit):
        self.store._current(self.binding)
        raise ValueError('BATCH_SKILL_EXTERNAL_DURABLE_HPMP_OWNER_UNAVAILABLE')

    def verify_bundle(self,reservation,receipt):
        return False


class ParticipantView:
    """Read-only canonical document consumer; no separate skill/quest file.

    SKILL owner must adapt its exact-type Store admission to this shared view.
    This candidate does not bypass that existing check or mutate its source.
    """
    def __init__(self,store,binding,name,validate):
        need(type(store) is BatchStore and name in store.capabilities,'BATCH_PARTICIPANT_VIEW_CAPABILITY')
        self.store,self.binding,self.name=store,binding,name
        self.lock=store.lock;self._validate=validate
        self.data=self._load();self.failed=False

    def _load(self): return self.store.participant(self.binding,self.name)['document']

    def _current(self):
        need(not self.failed and self._load()==self.data,'BATCH_PARTICIPANT_VIEW_STALE')

    def _save(self,document):
        raise ValueError('BATCH_PARTICIPANT_COORDINATED_COMMIT_REQUIRED')


@dataclass(frozen=True)
class Expected:
    uid: int
    asset_revision: int
    participant_revision: int
    participant_digest: str


class ParticipantPort:
    """Feature adapter input: opaque CAS token + canonical staged transaction.

    The feature maps its own selected lease to this module's owned Binding.
    Signed client deltas alone cannot create credit_frame/UIDs/authority.
    exact_request is mandatory; request digest and complete batch digest differ.
    """
    def __init__(self,store,name):
        need(type(store) is BatchStore and name in store.capabilities,'BATCH_PARTICIPANT_PORT')
        self.store,self.name=store,name

    def load(self,binding):
        _,revision=self.store.restore(binding);p=self.store.participant(binding,self.name)
        return Expected(binding.uid,revision,p['revision'],p['digest']),p['document']

    def lookup(self,binding,txid,request_sha):
        return self.store.lookup(binding,txid=txid,request_sha=request_sha)

    def transact(self,binding,*,txid,expected,exact_request,catalog_digest,changes,next_document,reward_markers=()):
        need(type(expected) is Expected and expected.uid==binding.uid,'BATCH_EXPECTED_SELECTED_UID')
        return self.store.transact(binding,txid=txid,request=exact_request,catalog_digest=catalog_digest,
            expected_revision=expected.asset_revision,changes=changes,participants=(ParticipantChange(self.name,
                expected.participant_revision,expected.participant_digest,next_document,reward_markers),))
