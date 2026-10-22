"""Opt-in current-inventory validation of CS0960; no use effect or reply.

The receiving broker owns the actual row operation_lock. This service performs
read-only canonical Store checks and the original native-owner checkpoint; it
never grants inventory, queries item memory, writes a frame or commits a Store.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import inspect
from pathlib import Path
import sys
import threading
import weakref
from types import MethodType

from tools.local_original_session import inventory, item_use, movement, observe
from tools.local_original_session.inventory_store import InventoryStore
from tools.local_original_session import inventory_store

POLICY = 'EXPLICIT_LOCAL_VALIDATED_ITEM_USE_INTENT'
U64_MAX = item_use.U64_MAX
need = inventory.need
_SHOP_RUNTIMES = weakref.WeakValueDictionary()
_BOOK_RUNTIMES = weakref.WeakKeyDictionary()
SHOP_ADOPTION_SOURCE_SHA256 = 'afcebef885c4d7e6b2ada83df340dfb5dbe0c16a28d95c247a1363ae1b274cf3'
BOOK_EMPTY_EQUIPMENT_SOURCE_SHA256 = '87c93ec3eb27d8109eab3e70eaa5d215bcdf1c3bf07d9e0fe2a9efcf9d9422ed'
MANUAL_NATIVE_SOURCE_SHA256 = 'efdd4b3c63b7ae20fd08e3ed39d916fd5cd60035020db0aa44ee33ea038c6125'


@dataclass(frozen=True, slots=True)
class _BookRuntime:
    owner: object
    owner_module: object
    delivery_module: object
    source_pins: tuple
    store: object
    provider: object
    readcap: object
    canonical: object
    methods: tuple
    paths: tuple
    equipment: object


@dataclass(frozen=True, slots=True)
class _BookEquipmentRuntime:
    module: object
    path: object
    sha256: str
    cls: object
    effect: object
    store: object
    methods: tuple
    code_bindings: tuple


def _book_equipment_current(broker, bound):
    effect=getattr(broker,'_item_equipment_effect',None)
    if bound is None:
        need(effect is None and broker.realm._item_equipment_effect is None
             and broker.policy.item_equipment_effect is False,
             'ITEM_USE_BOOK_EQUIPMENT_DISABLED_CHANGED')
        return None
    need(type(bound) is _BookEquipmentRuntime and effect is bound.effect
         and broker.realm._item_equipment_effect is effect and type(effect) is bound.cls
         and broker.policy.item_equipment_effect is True
         and sys.modules.get('tools.local_original_session.item_equipment_effect') is bound.module
         and bound.module.ItemEquipmentEffect is bound.cls
         and Path(bound.module.__file__).resolve(strict=True)==bound.path
         and hashlib.sha256(bound.path.read_bytes()).hexdigest()==bound.sha256
         and bound.sha256==BOOK_EMPTY_EQUIPMENT_SOURCE_SHA256
         and effect.broker is broker and effect.realm is broker.realm
         and effect.store is bound.store and bound.store.inventory_store is broker._inventory_store,
         'ITEM_USE_BOOK_EQUIPMENT_SOURCE_CHANGED')
    need(len(bound.methods)==len(bound.code_bindings)==7
         and bound.cls.__module__==bound.module.__name__ and bound.cls.__qualname__=='ItemEquipmentEffect',
         'ITEM_USE_BOOK_EQUIPMENT_CLASS_SOURCE_CHANGED')
    for (name,function),(code,defaults,kwdefaults) in zip(bound.methods,bound.code_bindings):
        need(getattr(bound.cls,name) is function and function.__globals__ is bound.module.__dict__
             and function.__qualname__=='ItemEquipmentEffect.'+name
             and Path(function.__code__.co_filename).resolve(strict=True)==bound.path
             and function.__code__ is code and function.__defaults__ is defaults
             and inventory._freeze_static(function.__kwdefaults__)==kwdefaults,
             'ITEM_USE_BOOK_EQUIPMENT_METHOD_CHANGED')
        _original(effect,name,function)
    return effect


def _capture_book_equipment(broker):
    effect=getattr(broker,'_item_equipment_effect',None)
    if effect is None:
        _book_equipment_current(broker,None)
        return None
    module=sys.modules.get('tools.local_original_session.item_equipment_effect')
    need(module is not None and type(effect) is module.ItemEquipmentEffect,
         'ITEM_USE_BOOK_EQUIPMENT_EXACT_CLASS_REQUIRED')
    path=Path(module.__file__).resolve(strict=True)
    need(path.stat().st_size<=65536,'ITEM_USE_BOOK_EQUIPMENT_SOURCE_BOUND')
    cls=module.ItemEquipmentEffect
    methods=tuple((name,getattr(cls,name)) for name in ('prepare_locked','_context','_same',
        '_begin','_collection_changes','_notify_selected','_notify_collection'))
    codes=tuple((function.__code__,function.__defaults__,inventory._freeze_static(function.__kwdefaults__))
                for _,function in methods)
    bound=_BookEquipmentRuntime(module,path,BOOK_EMPTY_EQUIPMENT_SOURCE_SHA256,cls,effect,effect.store,methods,codes)
    _book_equipment_current(broker,bound)
    return bound


def _book_methods(owner, module, delivery, store, provider, readcap):
    return (module.BookBatch.received_context,module.BookBatch.materialization,
        module.BookBatch.adoption_memory,delivery.BookDelivery.materialization,
        delivery.BookDelivery.validate_memory,type(provider).consumed_use_context,
        type(store)._read,type(store)._path_check,type(store.source)._path_check,
        type(readcap).check,type(readcap).project,ItemUseSession.release,
        ItemUseSession.adopt_book_drained,ItemUseSession._book_current,
        type(provider)._connection,type(provider.broker).inventory_selection_current,
        delivery.BookDelivery._receipt,type(store).receipt_for_delivery,type(store).inventory_for_delivery,
        ItemUseSession._prepare_book_native_completion,ItemUseSession.book_native_current,
        ItemUseSession.retire_book_native,ItemUseSession._book_native_context,
        ItemUseSession._complete_book_native_received,ItemUseSession._prepare_book_empty_equipment_received,
        ItemUseSession._project,ItemUseSession._same)


def bind_book_adoption_runtime(broker, owner, *, source_path, expected_sha256,
                               delivery_source_path, delivery_sha256):
    provider=owner.service.provider
    abort=type(provider).abort_consumed_use_owner
    rollback=broker not in _BOOK_RUNTIMES
    try:
        return _bind_book_adoption_runtime(broker,owner,source_path=source_path,
            expected_sha256=expected_sha256,delivery_source_path=delivery_source_path,
            delivery_sha256=delivery_sha256)
    except BaseException as error:
        # A failing cold bind must not strand the preceding registration.
        # Never overwrite its source/pin error with a secondary cleanup error.
        try:
            if rollback:abort(provider,owner)
        except BaseException as cleanup_error:
            error.add_note('ITEM book cold rollback: '+type(cleanup_error).__name__+': '+str(cleanup_error))
        raise


def _bind_book_adoption_runtime(broker, owner, *, source_path, expected_sha256,
                                delivery_source_path, delivery_sha256):
    """Explicit cold source cohort; no received intent or inventory grant."""
    need(not broker._started and not broker._closing and not broker.failure.is_set()
         and not broker.realm.registry._sessions and broker not in _BOOK_RUNTIMES,
         'ITEM_USE_BOOK_COLD_SINGLE_RUNTIME_REQUIRED')
    module=sys.modules.get(type(owner).__module__)
    need(module is not None and type(owner) is getattr(module,'BookBatch',None),
         'ITEM_USE_BOOK_EXACT_OWNER_REQUIRED')
    delivery=sys.modules.get('tools.local_original_session.spell_book_delivery')
    need(delivery is not None and getattr(delivery,'BookDelivery',None) is not None,
         'ITEM_USE_BOOK_EXACT_DELIVERY_MODULE_REQUIRED')
    pins=((Path(source_path).resolve(strict=True),expected_sha256,module),
          (Path(delivery_source_path).resolve(strict=True),delivery_sha256,delivery))
    for path,sha,loaded in pins:
        need(path.is_absolute() and type(sha) is str and len(sha)==64
             and all(c in '0123456789abcdef' for c in sha) and path.stat().st_size<=65536
             and Path(loaded.__file__).resolve(strict=True)==path
             and hashlib.sha256(path.read_bytes()).hexdigest()==sha,
             'ITEM_USE_BOOK_EXACT_SOURCE_PIN_REQUIRED')
    service=owner.service;store=service.store;provider=service.provider
    source=broker._inventory_store;readcap=source._aggregate_capability;m=readcap.check()
    need(type(store) is m.BatchStore and type(provider) is m.BrokerProvider
         and service.batch is m and provider.broker is broker and store.provider is provider
         and store.source is source and provider.source_store is source
         and source._aggregate_bound is readcap and not owner.closed
         and m._CONSUMED_USE_OWNERS.get(provider,(None,))[0] is owner,
         'ITEM_USE_BOOK_SINGLE_CANONICAL_RUNTIME_REQUIRED')
    store._path_check()
    runtime=_BookRuntime(owner,module,delivery,pins,store,provider,readcap,m,
        _book_methods(owner,module,delivery,store,provider,readcap),
        (store.path,store.profile,store._paths,source.path,source.profile,
         source._aggregate_paths,source._custody_paths),_capture_book_equipment(broker))
    _BOOK_RUNTIMES[broker]=runtime
    return runtime


def retire_book_adoption_runtime(broker):
    runtime=_BOOK_RUNTIMES.get(broker)
    if runtime is None:return
    need(runtime.owner.closed and not broker._tasks,
         'ITEM_USE_BOOK_RETIRE_AFTER_OWNER_CLOSE_REQUIRED')
    if broker._closing:
        runtime.provider.retire_consumed_use_owner(runtime.owner)
    elif not broker._started:
        need(not broker.realm.registry._sessions and runtime.provider._scope is None
             and runtime.provider.source_store is broker._inventory_store is runtime.store.source
             and runtime.store.active is None and not runtime.store._delivery_caps,
             'ITEM_USE_BOOK_RETIRE_UNUSED_COLD_RUNTIME_REQUIRED')
        runtime.provider.abort_consumed_use_owner(runtime.owner)
    else:
        raise ValueError('ITEM_USE_BOOK_RETIRE_LIVE_REQUIRES_CLOSE_JOIN')
    del _BOOK_RUNTIMES[broker]


@dataclass(frozen=True, slots=True, init=False)
class _BookNativeCompletion:
    source: object
    context: tuple
    binding: object
    after: bytes
    revision: int
    txid: str
    receipt_json: str
    def __init__(self,*args,**kwargs):
        raise TypeError('실제 Native source와 last DRAINED adoption에서만 발급')


@dataclass(frozen=True, slots=True, init=False)
class _NativeSourceRead:
    owner: object
    writer: object
    item_identifier: int
    context: tuple
    def __init__(self,*args,**kwargs):
        raise TypeError('실제 source caller의 같은 동기 호출에서만 발급')


@dataclass(frozen=True, slots=True, weakref_slot=True)
class _ShopRuntime:
    broker: object
    delivery: object
    module: object
    path: Path
    source_sha256: str
    store: object
    provider: object
    readcap: object
    methods: tuple
    paths: tuple
    identity: tuple
    resource: object = None


@dataclass(frozen=True,slots=True)
class _ResourceRead:
    owner: object
    status: object
    owner_module: object
    status_module: object
    owner_path: object
    status_path: object
    methods: tuple
    dispatcher: object

RESOURCE_OWNER_SOURCE_SHA256='256f4d884440c9428e82292d5e144143fa8bcd71ce5b9e06f14ed86530c9dbe3'
HP_STATUS_SOURCE_SHA256='5a2da3c39f21a58748ef51cbc15d8499f34bae46feb7bef5f5f279d61d2a8739'

def _bind_resource_read(broker,store,provider):
    owner=getattr(broker,'_hp_resource_owner',None)
    if owner is None:return None
    from tools.local_original_session import hp_resource_owner as resource,hp_status as hp
    owner_path=Path(resource.__file__).resolve();status_path=Path(hp.__file__).resolve()
    need(type(owner) is resource.ResourceOwner and type(broker._hp_status) is hp.Service
         and owner.status is broker._hp_status and owner.store is store and owner.provider is provider
         and hashlib.sha256(owner_path.read_bytes()).hexdigest()==RESOURCE_OWNER_SOURCE_SHA256
         and hashlib.sha256(status_path.read_bytes()).hexdigest()==HP_STATUS_SOURCE_SHA256,
         'ITEM_USE_RESOURCE_EXACT_COLD_RUNTIME_REQUIRED')
    return _ResourceRead(owner,owner.status,resource,hp,owner_path,status_path,
        (resource.ResourceOwner._issued_hp_delivery,hp.Service._resource_raw_current,
         ItemUseSession._resource_memory,ItemUseSession._same_resource_memory,ItemUseSession._resource_revision_current,
         ItemUseSession._resource_final),owner._delivery_dispatcher)

def _shop_methods(service, module, store, provider, readcap):
    return (module.Service.adoption_memory_record, module.Service.close,
            module.Service.record_adoption, type(provider)._connection,
            type(provider).source_store.fget, type(store)._read,
            type(readcap).check, type(readcap).project,
            type(store.source).restore, type(store.source)._read,
            type(store)._path_check, type(store.source)._path_check,
            module.Service.runtime_identity, module.Service.revoke_writer, module.ProjectionAdoption)


def bind_shop_adoption_runtime(broker, delivery, *, source_path, expected_sha256):
    """Cold trusted configuration only; does not grant a received Use intent."""
    from tools.local_original_session.broker import PersistentBroker
    path = Path(source_path)
    module = sys.modules.get(type(delivery).__module__)
    need(type(broker) is PersistentBroker and not broker._started and not broker._closing
         and not broker.failure.is_set() and not broker.realm.registry._sessions
         and getattr(broker, '_item_shop_adoption_runtime', None) is None,
         'ITEM_USE_SHOP_COLD_EXCLUSIVE_BINDING_REQUIRED')
    need(expected_sha256 == SHOP_ADOPTION_SOURCE_SHA256
         and path.is_absolute() and module is not None and type(delivery) is module.Service
         and Path(inspect.getsourcefile(module.Service)).resolve() == path.resolve()
         and hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256,
         'ITEM_USE_SHOP_EXACT_SOURCE_REQUIRED')
    store, provider = delivery.store, delivery.store.provider
    source = broker._inventory_store
    readcap = source._aggregate_capability
    m = readcap.check()
    need(type(store) is m.BatchStore and type(provider) is m.BrokerProvider
         and delivery.api is m and provider.broker is broker and provider.source_store is source
         and store.source is source and source._aggregate_bound is readcap
         and delivery.feature.broker is broker and delivery.attached and not delivery.closed
         and all(getattr(o, '_shop_trade_delivery', None) is delivery
                 for o in (broker, broker.realm, broker.policy)),
         'ITEM_USE_SHOP_SAME_CANONICAL_RUNTIME_REQUIRED')
    _original(delivery, 'adoption_memory_record', module.Service.adoption_memory_record)
    _original(delivery, 'runtime_identity', module.Service.runtime_identity)
    delivery.runtime_identity()
    store._path_check()
    runtime = _ShopRuntime(broker, delivery, module, path, expected_sha256, store, provider,
        readcap, _shop_methods(delivery, module, store, provider, readcap),
        (store.path, store.profile, store._paths, source.path, source.profile,
         source._aggregate_paths, source._custody_paths),
        (delivery.feature, delivery.owner, delivery.current_source_memory,
         delivery.send.__func__, delivery.identity), _bind_resource_read(broker,store,provider))
    _SHOP_RUNTIMES[id(runtime)] = runtime
    broker._item_shop_adoption_runtime = runtime
    return runtime


def retire_shop_adoption_runtime(broker):
    """After broker tasks joined and SHOP closed; never closes another owner."""
    runtime = getattr(broker, '_item_shop_adoption_runtime', None)
    if runtime is None:
        return
    need(type(runtime) is _ShopRuntime and _SHOP_RUNTIMES.get(id(runtime)) is runtime
         and runtime.broker is broker and broker._closing and runtime.delivery.closed
         and not runtime.delivery.parents and not broker._tasks,
         'ITEM_USE_SHOP_RETIRE_AFTER_OWNER_CLOSE_REQUIRED')
    broker._item_shop_adoption_runtime = None
    _SHOP_RUNTIMES.pop(id(runtime), None)
RAW0_SOURCE_PINS = {
    'work/local_server_rea_20261016/run40_item_raw0_branch/findings.md':
        '9d51db3062ed47934da2b9d5843f3c2111232a5f688e7447abad77b2cd71aec7',
    'work/local_server_rea_20261016/run40_item_raw0_branch/source-evidence.json':
        '0f9b83dc5ec9ac8f4d07cf0efc508ff521ef5a0ba1186be16a24a7afd19ee567',
}
_INVENTORY_SOURCE_ERRORS = frozenset({
    'INVENTORY_SOURCE_BOUND', 'INVENTORY_SOURCE_CHANGED', 'INVENTORY_SOURCE_CONTROL_CHANGED',
    'INVENTORY_EXACT_QUERY_SOURCE_REQUIRED', 'INVENTORY_REQUIRED_SOURCE_CHANGED',
    'INVENTORY_FIELD_SOURCE_CHANGED', 'INVENTORY_FIXED_CATALOG_CHANGED',
    'INVENTORY_EXACT_CURRENT_MAP_SOURCE_REQUIRED', 'INVENTORY_STORE_PARENT_SOURCE_CHANGED',
})


def _raw0_source_ready():
    # Existing run37 pins include the original sender's absent-f15/f16 ->
    # present-zero copy behavior. Run40 pins only the selected raw0 producer.
    item_use.source_ready()
    proof = None
    for relative, expected in RAW0_SOURCE_PINS.items():
        try:
            with (item_use.ROOT / relative).open('rb') as stream:
                raw = stream.read(1048577)
        except OSError:
            raise item_use.ItemUseSourceError('ITEM_USE_RAW0_SOURCE_UNAVAILABLE') from None
        if not 0 < len(raw) <= 1048576 or hashlib.sha256(raw).hexdigest() != expected:
            raise item_use.ItemUseSourceError('ITEM_USE_RAW0_SOURCE_CHANGED')
        if relative.endswith('.json'):
            proof = json.loads(raw)
    if not (proof['CONTROL_sha256'] == item_use.CONTROL_SHA256
            and proof['schema'] == 'run40-item-raw0-main-index-v1'
            and proof['raw0_table']['key'] == 0
            and proof['raw0_table']['target_rva'] == '0x4fe1fc'
            and proof['claims']['params'] == 'original inline UseItemReqParam stack object; '
                'ownhasbits8000; nestedf1 int32=1 only ownoptionalpresent; f17 absent; '
                'bool+74 raw1 but bit16 absent'):
        raise item_use.ItemUseSourceError('ITEM_USE_RAW0_SOURCE_CONTRACT_CHANGED')


class OutcomeKind(str, Enum):
    DISABLED = 'DISABLED'
    ACCEPTED = 'ACCEPTED'
    REJECTED = 'REJECTED'
    ERROR = 'ERROR'
    CANCELLED = 'CANCELLED'
    CLOSED = 'CLOSED'


@dataclass(frozen=True, slots=True)
class ItemUseOutcome:
    kind: OutcomeKind
    reason: str
    accepted_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class _Intent:
    # Private immutable received bytes/ordered typed params, never a capability
    # exported for later requests. Every frame is freshly validated.
    request: item_use.ItemUseRequest = field(repr=False)
    writer: object = field(repr=False)
    accepted_ordinal: int
    frame: bytes = field(repr=False)
    selection_binding: tuple = field(repr=False)
    adoption: object = field(default=None, repr=False)


def _original(owner, name, function):
    method = getattr(owner, name, None)
    need(type(method) is MethodType and method.__self__ is owner
         and method.__func__ is function, 'ITEM_USE_ORIGINAL_METHOD_REQUIRED')
    return method


def _category(error):
    if isinstance(error, item_use.ItemUseSourceError):
        return 'ITEM_USE_SOURCE_INVALID'
    if isinstance(error, item_use.MalformedItemUse):
        return 'MALFORMED_ITEM_USE_PAYLOAD'
    if isinstance(error, item_use.UnsupportedItemUse):
        return 'UNSUPPORTED_ITEM_USE_PAYLOAD'
    if isinstance(error, (ValueError, OSError)):
        return 'ITEM_USE_CURRENT_AUTHORITY_INVALID'
    return 'ITEM_USE_UNEXPECTED_ERROR'


_BACKEND_COMPLETIONS=weakref.WeakKeyDictionary()

@dataclass(frozen=True,slots=True,weakref_slot=True,eq=False,init=False)
class BackendCompletion:
    kind: str
    accepted_ordinal: int
    intent: object
    generation_ref: object
    effect_ref: object
    operation_id: int
    effect_snapshot: tuple
    def __init__(self,*args,**kwargs):raise TypeError('실제 backend end-consumer 전용 issuer')

class ItemUseSession:
    """One private intent and an exact uint64 accepted counter, default off."""
    def __init__(self, broker, *, policy=None):
        from tools.local_original_session.broker import PersistentBroker
        need(type(broker) is PersistentBroker, 'ITEM_USE_REAL_BROKER_REQUIRED')
        need(policy is None or type(policy) is str and policy == POLICY,
             'ITEM_USE_EXPLICIT_POLICY_REQUIRED')
        service = broker._inventory_service
        need(type(service) is inventory.InventoryService and service.broker is broker,
             'ITEM_USE_REAL_INVENTORY_SERVICE_REQUIRED')
        reader = service.reader
        need(type(reader) is observe.RetainedSceneReader,
             'ITEM_USE_REAL_RETAINED_READER_REQUIRED')
        self._collection_policy = getattr(broker, '_inventory_collection_policy', None)
        need(self._collection_policy is None or (type(self._collection_policy) is str
             and self._collection_policy == inventory.COLLECTION_POLICY),
             'ITEM_USE_EXPLICIT_COLLECTION_POLICY_REQUIRED')
        self.broker, self.policy = broker, policy
        self._service, self._reader, self._backend = service, reader, reader.backend
        self._store = service._persistence_store()
        self._store_bound = service._store_bound
        self._realm = broker.realm
        self.closed = False
        self.accepted_count = 0
        self.last_outcome = None
        self.last_invalidation = None
        self._current = None
        self._inflight_writer, self._released = None, False
        self._lock = asyncio.Lock()  # Never acquire the caller's row lock again.
        self._native_source_read = None
        self._native_pending_read = None
        self._book_native_completion = None
        self._book_native_preparation = None  # Existing metadata only; never read by authority guards.
        self._backend_completion = None

    def _clear(self, reason):
        self.retire_book_native()
        self._backend_completion = None
        self._current = None
        self.last_invalidation = reason

    def _outcome(self, kind, reason, ordinal=None):
        self.last_outcome = ItemUseOutcome(kind, reason, ordinal)
        return ()

    def _unavailable(self):
        if self.closed:
            return OutcomeKind.CLOSED, 'ITEM_USE_SESSION_CLOSED'
        need(self.policy is None or type(self.policy) is str and self.policy == POLICY,
             'ITEM_USE_EXPLICIT_POLICY_REQUIRED')
        if self.policy is None:
            return OutcomeKind.DISABLED, 'ITEM_USE_SESSION_DISABLED'
        if self._released:
            return OutcomeKind.REJECTED, 'ITEM_USE_WRITER_RELEASED'
        need(type(self.accepted_count) is int and 0 <= self.accepted_count <= U64_MAX,
             'ITEM_USE_UINT64_COUNTER_REQUIRED')
        if self.accepted_count == U64_MAX:
            return OutcomeKind.REJECTED, 'ITEM_USE_COUNTER_CAPACITY'
        return None

    def _native_source_context(self, source_owner, writer, item_identifier):
        from tools.local_original_session import manual_move_commands as commands
        need(type(source_owner) is commands.ManualMoveCommands
             and sys.modules.get(type(source_owner).__module__) is commands
             and hashlib.sha256(Path(commands.__file__).read_bytes()).hexdigest() == MANUAL_NATIVE_SOURCE_SHA256,
             'ITEM_USE_NATIVE_EXACT_SOURCE_CALLER_REQUIRED')
        _original(source_owner, '_use_item_current', commands.ManualMoveCommands._use_item_current)
        _original(source_owner, '_publish', commands.ManualMoveCommands._publish)
        _original(source_owner, '_clock', commands.ManualMoveCommands._clock)
        need(source_owner._busy is True and source_owner._thread == threading.get_ident()
             and source_owner.reader is self._reader
             and source_owner._item_use_type is type(self)
             and source_owner._item_use_native_project is ItemUseSession.project_native_source
             and not self.closed and not self._released,
             'ITEM_USE_NATIVE_ACTUAL_SOURCE_OWNER_REQUIRED')
        pending = source_owner.pending
        need(type(pending) is dict and pending.get('kind') == 'UseItem'
             and pending.get('phase') == 'NATIVE_WAIT' and pending.get('native_attempted') is False
             and pending.get('item_session') is self
             and type(item_identifier) is int and pending.get('item_identifier') == item_identifier
             and pending.get('native') is None and pending.get('result_identity') is None
             and type(pending.get('request')) is dict,
             'ITEM_USE_NATIVE_EXACT_PREPOST_REQUEST_REQUIRED')
        now = source_owner._clock()
        need(type(pending.get('started')) is int and now - pending['started'] < commands.WAIT_NS,
             'ITEM_USE_NATIVE_ORIGINAL_CLAIM_DEADLINE')
        current = source_owner._use_item_current(admission=True)
        row, request = current[1], pending['request']
        refs = pending.get('inventory_refs')
        actual_refs = (self.broker._inventory_service,self.broker._inventory_store,
            self.broker._inventory_frame,self.broker._inventory_selection_binding,
            self.broker._inventory_delivery_authority,self.broker._inventory_current_frame)
        need(type(refs) is tuple and len(refs) == 6 and len(actual_refs) == 6
             and all(refs[i] is actual_refs[i] for i in range(6)),
             'ITEM_USE_NATIVE_CURRENT_INVENTORY_REFS_REQUIRED')
        need(current[0].broker is self.broker and current[0].writer is writer
             and row['writer'] is writer and type(row['operation_lock']) is asyncio.Lock
             and row['operation_lock'].locked()
             and type(source_owner.sequence) is int and request.get('seq') == source_owner.sequence
             and request.get('player_uid') == current[3].uid
             and request.get('map_id') == current[3].map_id
             and request.get('item_identifier') == item_identifier
             and request.get('command') in ('UseItem','UseItemAlreadyOpen','UseItemCurrentEntry')
             and self.accepted_count == pending['item_before'],
             'ITEM_USE_NATIVE_CURRENT_SOURCE_ROW_REQUEST_REQUIRED')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        need(task is not None, 'ITEM_USE_NATIVE_SOURCE_TASK_REQUIRED')
        provider = getattr(self.broker, '_canonical_provider', None)
        scope = None if provider is None else provider._scope
        if provider is not None:
            need(type(scope) is tuple and len(scope) == 10 and scope[0] is task
                 and scope[1] == threading.get_ident() and scope[2] is writer
                 and scope[3] is row and scope[4] is row['operation_lock'],
                 'ITEM_USE_NATIVE_ACTUAL_CONNECTION_SCOPE_REQUIRED')
        identities = (source_owner,pending,request,writer,row,row['operation_lock'],
            current[0].broker,current[3],pending['inventory_refs'],source_owner._bound,task,scope)
        scalars = (source_owner.sequence,self.accepted_count,source_owner._busy,self.closed,self._released,
            pending['phase'],pending['native_attempted'],pending['started'],
            inventory._freeze_static(request),inventory._freeze_static(source_owner.state))
        return identities,scalars

    @staticmethod
    def _same_native_source(before, after):
        need(len(before[0]) == len(after[0])
             and all(a is z for a,z in zip(before[0],after[0])) and before[1] == after[1],
             'ITEM_USE_NATIVE_SOURCE_OPERATION_CHANGED')

    def project_native_source(self, writer, item_identifier, *, source_owner):
        """실제 final Post 직전 한 번의 동기 read; native/intent/ACK 권한을 발급하지 않는다."""
        need(self._native_source_read is None and not self._lock.locked()
             and self._inflight_writer is None and self._unavailable() is None,
             'ITEM_USE_NATIVE_SOURCE_REENTRY_OR_UNAVAILABLE')
        before = self._native_source_context(source_owner, writer, item_identifier)
        token = object.__new__(_NativeSourceRead)
        for name,value in dict(owner=source_owner,writer=writer,item_identifier=item_identifier,context=before).items():
            object.__setattr__(token,name,value)
        self._native_source_read = token
        self._inflight_writer,self._released = writer,False
        try:
            item_use.source_ready()
            projected = self._project(writer,item_identifier=item_identifier,native_source=token)
            self._same_native_source(before,self._native_source_context(source_owner,writer,item_identifier))
            need(self._native_source_read is token and not self._released and not self.closed,
                 'ITEM_USE_NATIVE_SOURCE_REVOKED')
            item_use.source_ready()
            need(self._native_pending_read is None and self._book_native_completion is None,
                 'ITEM_USE_NATIVE_PENDING_RELATION_ALREADY_EXISTS')
            self._native_pending_read = token
            return projected
        finally:
            self._native_source_read = None
            self._inflight_writer,self._released = None,False

    def _resource_memory(self, runtime, writer, row):
        rr=runtime.resource;b=self.broker;g=b._inventory_generation
        need(type(rr) is _ResourceRead and rr.owner is b._hp_resource_owner is b.realm._hp_resource_owner
             and rr.status is b._hp_status and rr.status._resource_owner is rr.owner
             and type(rr.owner) is rr.owner_module.ResourceOwner and type(rr.status) is rr.status_module.Service
             and rr.owner.status is rr.status and rr.owner.store is runtime.store
             and rr.owner.provider is runtime.provider and rr.owner.batch is runtime.delivery.api
             and rr.owner.document.owner is rr.owner and rr.owner.active
             and g.item_use_session is self and not self.closed and g.phase=='ACTIVE' and g.writer is writer and g.row is row
             and rr.owner._hp_effect is None and rr.owner._hp_read is None and rr.owner._operation is None
             and rr.owner._projection is None and rr.owner._prepared_operation is None and rr.owner._hp_producer is None,
             'ITEM_USE_RESOURCE_CURRENT_SOURCE_REQUIRED')
        need(hashlib.sha256(rr.owner_path.read_bytes()).hexdigest()==RESOURCE_OWNER_SOURCE_SHA256
             and hashlib.sha256(rr.status_path.read_bytes()).hexdigest()==HP_STATUS_SOURCE_SHA256,
             'ITEM_USE_RESOURCE_SOURCE_CHANGED')
        _original(rr.owner,'_issued_hp_delivery',rr.methods[0]);_original(rr.status,'_resource_raw_current',rr.methods[1])
        for name,function in (('_resource_memory',rr.methods[2]),('_resource_revision_current',rr.methods[4]),('_resource_final',rr.methods[5])):
            _original(self,name,function)
        need(type(self)._same_resource_memory is rr.methods[3] and self._same_resource_memory is rr.methods[3],
             'ITEM_USE_RESOURCE_ORIGINAL_COMPARE_REQUIRED')
        deliveries=tuple(rr.owner._hp_edges.get(id(writer),()))
        records=tuple(rr.methods[0](rr.owner,writer,d) for d in deliveries)
        snapshot=rr.methods[1](rr.status,writer)
        need(len(deliveries)==len(rr.owner._hp_edges.get(id(writer),()))
             and all(d is rr.owner._hp_edges[id(writer)][n] for n,d in enumerate(deliveries))
             and all(r.row is row and r.delivery is deliveries[n] and r.delivery.phase=='DRAINED' for n,r in enumerate(records)),
             'ITEM_USE_RESOURCE_ISSUED_HISTORY_CHANGED')
        values=tuple((r.txid,r.request,r.delivery.phase,r.before.revision,r.after.revision,
                      tuple(sorted(r.before.fields.items())),tuple(sorted(r.after.fields.items()))) for r in records)
        memory=(rr,snapshot,g,records,values)
        rr.methods[5](self,runtime,memory,writer,row)
        return memory

    @staticmethod
    def _same_resource_memory(before,after):
        need(all(before[n] is after[n] for n in (0,1,2)) and len(before[3])==len(after[3])
             and all(a is z for a,z in zip(before[3],after[3])) and before[4]==after[4],
             'ITEM_USE_RESOURCE_READ_SOURCE_CHANGED')

    def _resource_revision_current(self,runtime,writer,row,frame,adoption,document):
        # The latest full-schema canonical document is inventory authority.
        # The old SHOP adoption remains materialization history only.
        need(type(runtime.resource) is _ResourceRead,'ITEM_USE_RESOURCE_BOUND_RUNTIME_REQUIRED')
        rr=runtime.resource
        _original(self,'_resource_revision_current',rr.methods[4])
        memory=rr.methods[2](self,runtime,writer,row)
        rr,snapshot,g,records,values=memory;m=runtime.delivery.api
        revision=document['revisions'].get(str(adoption.uid));old=adoption.asset_revision
        need(type(revision) is int and revision>old and revision-old<=len(records),
             'ITEM_USE_RESOURCE_REVISION_BRIDGE_REQUIRED')
        key='RESOURCE:'+str(adoption.uid);selected=[]
        participant=document['participants'].get(key)
        need(type(participant) is dict,'ITEM_USE_RESOURCE_CURRENT_PARTICIPANT_REQUIRED')
        shop_tx=document['transactions'].get(adoption.txid)
        need(type(shop_tx) is dict,'ITEM_USE_RESOURCE_SHOP_HISTORY_REQUIRED')
        for record in records:
            tx=document['transactions'].get(record.txid)
            need(type(tx) is dict,'ITEM_USE_RESOURCE_ISSUED_RECEIPT_MISSING')
            if tx['asset_revision']<=old:continue
            expected_request=m.encoded(dict(kind='HP_EFFECT',uid=adoption.uid,revision=record.before.revision,
                before=record.after.current_hp+1,after=record.after.current_hp,generation=tx['generation']))
            expected_after=json.loads(m.encoded(participant['document']))
            expected_after['revision']=record.after.revision
            expected_after['values']={k:record.after.fields[int(k)] for k in expected_after['values']}
            need(old<tx['asset_revision']<=revision and tx['uid']==adoption.uid
                 and tx['request_sha']==m.request_digest(record.request)
                 and tx['phase']=='COMMITTED' and tx['delivery']=='DRAINED'
                 and set(tx['participants'])=={key} and record.request==expected_request
                 and record.after.revision==record.before.revision+1
                 and tx['participants'][key]==m.digest(expected_after),
                 'ITEM_USE_RESOURCE_EXACT_CONTINUATION_RECEIPT_REQUIRED')
            selected.append((tx['asset_revision'],record,expected_after))
        selected.sort(key=lambda part:part[0])
        need(len(selected)==revision-old and all(part[0]==old+1+n for n,part in enumerate(selected)),
             'ITEM_USE_RESOURCE_CONTIGUOUS_REVISION_REQUIRED')
        need(all(selected[n][1].before is selected[n-1][1].after for n in range(1,len(selected)))
             and selected[-1][1].after is snapshot,
             'ITEM_USE_RESOURCE_CURRENT_LINEAGE_REQUIRED')
        after=selected[-1][2];participant=document['participants'].get(key)
        need(type(participant) is dict and participant['document']==after
             and after['revision']==snapshot.revision
             and after['values']=={k:snapshot.fields[int(k)] for k in after['values']}
             and g.current_frame is frame and adoption.generation_ref() is g,
             'ITEM_USE_RESOURCE_CURRENT_DOCUMENT_REQUIRED')
        return memory

    def _resource_final(self,runtime,memory,writer,row):
        rr,snapshot,g,records,values=memory;o=rr.owner;s=rr.status;b=self.broker
        need(type(rr) is _ResourceRead and o is b._hp_resource_owner is b.realm._hp_resource_owner
             and s is b._hp_status and s._resource_owner is o and o.status is s
             and o.store is runtime.store and o.provider is runtime.provider and o.active
             and o._delivery_dispatcher is rr.dispatcher and rr.dispatcher.resource_owner is o
             and rr.dispatcher.store is runtime.store and rr.dispatcher.provider is runtime.provider
             and o._hp_effect is None and o._hp_read is None and o._operation is None and o._projection is None
             and o._prepared_operation is None and o._hp_producer is None
             and b._inventory_generation is g and g.item_use_session is self and not self.closed
             and g.phase=='ACTIVE' and g.writer is writer and g.row is row and g.lock.locked()
             and s._states.get(id(writer)) is snapshot
             and len(o._hp_edges.get(id(writer),()))==len(records)
             and all(o._hp_edges[id(writer)][n] is r.delivery and o._hp_receipts.get(id(r.delivery)) is r
                     for n,r in enumerate(records))
             and values==tuple((r.txid,r.request,r.delivery.phase,r.before.revision,r.after.revision,
                      tuple(sorted(r.before.fields.items())),tuple(sorted(r.after.fields.items()))) for r in records),
             'ITEM_USE_RESOURCE_POST_CALLBACK_OWNER_CHANGED')
        _original(o,'_issued_hp_delivery',rr.methods[0]);_original(s,'_resource_raw_current',rr.methods[1])
        for name,function in (('_resource_memory',rr.methods[2]),('_resource_revision_current',rr.methods[4]),('_resource_final',rr.methods[5])):
            _original(self,name,function)

    def _shop_current(self, writer, row, authority, frame, *, equipment_operation=None,
                      history_only=False, expected_context=None, native_source=None):
        """Actual Use/equipment row scope + current canonical read, never current()."""
        from tools.local_original_session.broker import PersistentBroker
        b = self.broker
        runtime = getattr(b, '_item_shop_adoption_runtime', None)
        if runtime is None:
            return None
        need(type(runtime) is _ShopRuntime and _SHOP_RUNTIMES.get(id(runtime)) is runtime
             and runtime.broker is b, 'ITEM_USE_SHOP_ISSUED_RUNTIME_REQUIRED')
        service, m, store, provider, readcap = (runtime.delivery, runtime.module,
            runtime.store, runtime.provider, runtime.readcap)
        value = service.last_adoption
        if value is None:
            return None
        need(type(value) is m.ProjectionAdoption, 'ITEM_USE_SHOP_TYPED_ADOPTION_REQUIRED')
        if value.frame is not frame:
            return None  # A later original UPDATE must prove its own old/new path.
        canonical = readcap.check()
        def current():
            if hashlib.sha256(runtime.path.read_bytes()).hexdigest() != runtime.source_sha256:
                raise item_use.ItemUseSourceError('ITEM_USE_SHOP_SOURCE_CHANGED')
            f = service.feature
            feature_identity = (b, store, provider, self._store, self._store, f.owner,
                                f.owner.catalog, f.bindings, f.current_listing, f.current_terms)
            need(getattr(b, '_item_shop_adoption_runtime', None) is runtime
                 and _shop_methods(service, m, store, provider, readcap) == runtime.methods
                 and type(service) is m.Service and type(store) is canonical.BatchStore
                 and type(provider) is canonical.BrokerProvider
                 and service.api is canonical and service.store is store and store.provider is provider
                 and service.feature is runtime.identity[0] and service.owner is runtime.identity[1]
                 and service.current_source_memory is service._source_callback is runtime.identity[2]
                 and service.send.__self__ is b and service.send.__func__ is runtime.identity[3]
                 and service.identity is runtime.identity[4] and type(service.identity) is tuple
                 and len(service.identity) == len(feature_identity)
                 and all(a is z for a,z in zip(service.identity, feature_identity))
                 and provider.broker is b and provider.source_store is self._store is store.source
                 and self._store._aggregate_capability is self._store._aggregate_bound is readcap
                 and readcap.check() is canonical and not store.closed and not store.failed
                 and canonical._OWNERS.get(store._key) is store
                 and not store._catalog_validating and not store._delivery_validating
                 and not store._original_update_validating and store.active is None
                 and not store._delivery_caps
                 and (store.path, store.profile, store._paths, self._store.path,
                      self._store.profile, self._store._aggregate_paths,
                      self._store._custody_paths) == runtime.paths,
                 'ITEM_USE_SHOP_CURRENT_RUNTIME_CHANGED')
            _original(provider, '_connection', canonical.BrokerProvider._connection)
            _original(b, 'inventory_selection_current', PersistentBroker.inventory_selection_current)
            _original(store, '_read', canonical.BatchStore._read)
            _original(store, '_path_check', runtime.methods[10])
            _original(self._store, '_path_check', runtime.methods[11])
            store._path_check()
            _original(service, 'adoption_memory_record', runtime.methods[0])
            _original(service, 'runtime_identity', runtime.methods[12])
            _original(readcap, 'check', runtime.methods[6])
            _original(readcap, 'project', runtime.methods[7])
            scope = provider._scope
            need(type(scope) is tuple and len(scope) == 10,
                 'ITEM_USE_SHOP_ACTUAL_CONNECTION_SCOPE_REQUIRED')
            provider._connection(writer, row, scope=scope)
            g = b.inventory_selection_current(writer)
            need(g is not None and g.item_use_session is self and g.store is self._store
                 and g.row is row and g.writer is writer and g.lock is row['operation_lock']
                 and g.current_frame is frame and value.generation_ref() is g
                 and g.mover.snapshot() is authority[0]
                 and value.uid == authority[0].uid and service.last_adoption is value
                 and service.adoption_memory_record(value) is value,
                 'ITEM_USE_SHOP_CURRENT_GENERATION_ADOPTION_REQUIRED')
            # Inflight validation and received/equipment consumption have
            # different legitimate states; neither clears the other's flags.
            inflight = self._lock.locked() and self._inflight_writer is writer
            intent = self._current
            received = (type(intent) is _Intent and intent.writer is writer
                        and intent.frame is frame and intent.selection_binding is g.selection_binding
                        and intent.adoption is value and intent.accepted_ordinal == self.accepted_count)
            effect = getattr(b, '_item_equipment_effect', None)
            if equipment_operation is not None:
                from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
                need(type(effect) is ItemEquipmentEffect and effect._operation is equipment_operation,
                     'ITEM_USE_SHOP_ACTUAL_EQUIPMENT_OPERATION_REQUIRED')
            native = native_source is not None
            if native:
                need(type(native_source) is _NativeSourceRead and self._native_source_read is native_source
                     and native_source.writer is writer and self._inflight_writer is writer,
                     'ITEM_USE_SHOP_ACTUAL_NATIVE_SOURCE_TOKEN_REQUIRED')
                self._same_native_source(native_source.context,self._native_source_context(
                    native_source.owner,writer,native_source.item_identifier))
            need(not self.closed and not self._released and (inflight or received
                 or equipment_operation is not None or native), 'ITEM_USE_SHOP_ACTUAL_SOURCE_OPERATION_REQUIRED')
            task = asyncio.current_task()
            need(task is not None and not task.cancelling()
                 and scope[0] is task and scope[1] == threading.get_ident(),
                 'ITEM_USE_SHOP_CURRENT_TASK_REQUIRED')
            return (scope, g, self._current, self._inflight_writer, self._released,
                    self.closed, self._lock.locked(), self.accepted_count,
                    b._inventory_update_operation, effect,
                    None if effect is None else effect._operation,
                    None if effect is None else effect._collection_batch,
                    self._service, self._reader, self._backend, self._store,
                    self._store_bound, self._realm, b._inventory_service,
                    b._inventory_frame, b._inventory_operation_frame,
                    b._inventory_selection_binding, b._inventory_delivery_authority,
                    b._inventory_restore_only, self.last_outcome, self.last_invalidation)
        with inventory_store._lock, inventory_store.realm._lock:
            before = current()
            def same_context(old, new):
                return len(old) == len(new) and all(a is z if n not in (4,5,6,7) else a == z
                    for n,(a,z) in enumerate(zip(old, new)))
            need(expected_context is None or same_context(expected_context, before),
                 'ITEM_USE_SHOP_RESTORE_SOURCE_OPERATION_CHANGED')
            if history_only:
                return value, before  # No intent/capability; same synchronous call only.
            old_raw, old_data = store._raw, canonical.encoded(store.data)
            raw, document = store._read()  # Full original schema/callback validation, no provider recursion.
            need(raw == old_raw and raw == store._raw and canonical.encoded(document) == old_data
                 and canonical.encoded(store.data) == old_data,
                 'ITEM_USE_SHOP_CURRENT_CANONICAL_PREIMAGE_CHANGED')
            # _read already used this exact readcap's canonical schema and
            # participant validators. Extract rows without a second callback pass.
            rows = canonical.BatchStore._validate_canonical(store, document['canonical'])
            tx = document['transactions'].get(value.txid)
            resource_memory=None
            if document['revisions'].get(str(value.uid)) != value.asset_revision:
                need(type(runtime.resource) is _ResourceRead,'ITEM_USE_RESOURCE_BOUND_RUNTIME_REQUIRED')
                resource_memory=runtime.resource.methods[4](self,runtime,writer,row,frame,value,document)
            need(rows.get(value.uid) == frame
                 and hashlib.sha256(frame).hexdigest() == value.frame_sha
                 and (document['revisions'].get(str(value.uid)) == value.asset_revision or resource_memory is not None)
                 and type(tx) is dict and tx['uid'] == value.uid
                 and tx['request_sha'] == canonical.request_digest(value.exact_request)
                 and tx['asset_revision'] == value.asset_revision
                 and tx['phase'] == 'COMMITTED' and tx['delivery'] == 'DRAINED'
                 and canonical.encoded(tx) == value.receipt_raw and document['pending'] is None,
                 'ITEM_USE_SHOP_CURRENT_REVISION_RECEIPT_REQUIRED')
            if resource_memory is not None:
                rr=runtime.resource
                rr.methods[3](resource_memory,rr.methods[2](self,runtime,writer,row))
            after = current()
            if resource_memory is not None:
                runtime.resource.methods[5](self,runtime,resource_memory,writer,row)
            # No callbacks after this raw read. A schema callback that writes
            # or swaps the canonical file cannot make its old read a success.
            with runtime.paths[0].open('rb') as stream:
                final_raw = stream.read(canonical.MAX_BYTES + 1)
            need(final_raw == old_raw and store._raw == old_raw
                 and canonical.encoded(store.data) == old_data,
                 'ITEM_USE_SHOP_POST_CALLBACK_CANONICAL_CHANGED')
            need(same_context(before, after),
                 'ITEM_USE_SHOP_POST_CALLBACK_SOURCE_OPERATION_CHANGED')
        return value

    def adopt_book_drained(self, owner, parent):
        """Consume the exact final book capability, then release and RAM CAS.

        Synchronous inside the original source row scope. DRAINED is backend
        delivery evidence, never client ACK or Native return evidence.
        """
        runtime=_BOOK_RUNTIMES.get(self.broker)
        need(type(runtime) is _BookRuntime and runtime.owner is owner,
             'ITEM_USE_BOOK_REGISTERED_RUNTIME_REQUIRED')
        provider,store,m=runtime.provider,runtime.store,runtime.canonical
        need(_book_methods(owner,runtime.owner_module,runtime.delivery_module,store,provider,
             runtime.readcap)==runtime.methods,'ITEM_USE_BOOK_ORIGINAL_METHODS_CHANGED')
        for path,sha,module in runtime.source_pins:
            need(sys.modules.get(module.__name__) is module and Path(module.__file__).resolve()==path
                 and hashlib.sha256(path.read_bytes()).hexdigest()==sha,
                 'ITEM_USE_BOOK_ADOPTION_SOURCE_CHANGED')
        scoped=_original(provider,'consumed_use_context',runtime.methods[5])
        context=scoped(owner,parent)
        use,intent,ordinal,writer,row,g,before,request=context
        need(use is self and type(parent) is runtime.delivery_module.BookDelivery
             and parent.batch is owner and parent.operation is owner._received
             and parent.phase=='DRAINED_ADOPTION' and parent.index==1
             and self._current is intent and self.accepted_count==ordinal
             and not self.closed and not self._released and self._inflight_writer is None
             and not self._lock.locked() and g.current_frame is before
             and g.selection_binding is intent.selection_binding,
             'ITEM_USE_BOOK_EXACT_DRAINED_SOURCE_OPERATION_REQUIRED')
        release=_original(self,'release',runtime.methods[11])
        materialize=_original(owner,'materialization',runtime.methods[1])
        _original(parent,'materialization',runtime.methods[3])
        _original(parent,'validate_memory',runtime.methods[4])
        _original(parent,'_receipt',runtime.methods[16])
        _original(store,'receipt_for_delivery',runtime.methods[17])
        _original(store,'inventory_for_delivery',runtime.methods[18])
        binding,old,after,revision=materialize(parent)
        need(type(binding) is m.Binding and binding is parent.binding and binding.generation is g
             and binding.writer is writer and binding.operation_lock is row['operation_lock']
             and old is before and type(after) is bytes and type(revision) is int and revision>0
             and parent.request is request and parent.staged.intent is intent
             and parent.staged.before_inventory is before and parent.staged.after_inventory==after,
             'ITEM_USE_BOOK_FINAL_MATERIALIZATION_REQUIRED')
        # Capture live received ordinal/request and final cap before release retires them.
        prepare_native=_original(self,'_prepare_book_native_completion',runtime.methods[19])
        native_completion=prepare_native(context,parent,binding,after,revision)
        # Last source callbacks run before release. Their original cap checks
        # bind both frames, durable receipt and the actual current held scope.
        check=scoped(owner,parent)
        need(check is context and self._current is intent and g.current_frame is before
             and not asyncio.current_task().cancelling()
             and _BOOK_RUNTIMES.get(self.broker) is runtime
             and _book_methods(owner,runtime.owner_module,runtime.delivery_module,store,provider,
                 runtime.readcap)==runtime.methods,
             'ITEM_USE_BOOK_PRE_RELEASE_CURRENT_CHANGED')
        _original(self,'release',runtime.methods[11])
        _original(owner,'materialization',runtime.methods[1])
        _original(parent,'materialization',runtime.methods[3])
        _original(parent,'_receipt',runtime.methods[16])
        _original(store,'receipt_for_delivery',runtime.methods[17])
        _original(store,'inventory_for_delivery',runtime.methods[18])
        _original(provider,'consumed_use_context',runtime.methods[5])
        _original(provider,'_connection',runtime.methods[14])
        release(writer)
        # The source accessor permits None only for this same live final drain.
        need(scoped(owner,parent) is context and self._current is None
             and self.accepted_count==ordinal and g.current_frame is before,
             'ITEM_USE_BOOK_RELEASE_POSTSTATE_CHANGED')
        binding2,old2,after2,revision2=materialize(parent)
        _original(self,'release',runtime.methods[11])
        _original(owner,'materialization',runtime.methods[1])
        _original(parent,'materialization',runtime.methods[3])
        _original(parent,'_receipt',runtime.methods[16])
        _original(store,'receipt_for_delivery',runtime.methods[17])
        _original(store,'inventory_for_delivery',runtime.methods[18])
        _original(provider,'consumed_use_context',runtime.methods[5])
        _original(provider,'_connection',runtime.methods[14])
        need(binding2 is binding and old2 is before and after2==after and revision2==revision
             and self._current is None and g.current_frame is before
             and self.broker._inventory_generation is g and g.item_use_session is self
             and row['operation_lock'] is g.lock and g.lock.locked()
             and provider._scope is binding.owned_scope
             and binding.owned_scope[0] is asyncio.current_task()
             and binding.owned_scope[1]==threading.get_ident()
             and not asyncio.current_task().cancelling()
             and _BOOK_RUNTIMES.get(self.broker) is runtime
             and _book_methods(owner,runtime.owner_module,runtime.delivery_module,store,provider,
                 runtime.readcap)==runtime.methods,
             'ITEM_USE_BOOK_POST_RELEASE_CAS_PREIMAGE_CHANGED')
        self.broker._inventory_current_frame=after
        need(g.current_frame is after and self._current is None,
             'ITEM_USE_BOOK_CURRENT_FRAME_CAS_FAILED')
        if native_completion is not None:
            need(self._native_pending_read is None and self._book_native_completion is None,
                 'ITEM_USE_BOOK_NATIVE_RELEASE_MUST_REVOKE_OLD_RELATION')
            self._native_pending_read=native_completion.source
            self._book_native_completion=native_completion
        return True

    def retire_book_native(self):
        """Revoke source relation and completion together; never replay or retry."""
        self._native_pending_read = None
        self._book_native_completion = None

    def _prepare_book_native_completion(self, context, parent, binding, after, revision):
        source = self._native_pending_read
        if source is None:
            self._book_native_preparation = dict(scope='LAST_PREPARATION_DECISION_ONLY_NOT_CURRENT_AUTHORITY', status='NO_SOURCE_RELATION',
                accepted_ordinal=context[2], native_sequence=None, started_ns=None,
                checked_ns=None, original_claim_expired=None)
            return None  # Ordinary received Use has no Native completion authority.
        need(type(source) is _NativeSourceRead and self._book_native_completion is None,
             'ITEM_USE_BOOK_NATIVE_ISSUED_SOURCE_REQUIRED')
        use,intent,ordinal,writer,row,g,before,raw = context
        runtime = _BOOK_RUNTIMES.get(self.broker)
        need(type(runtime) is _BookRuntime and use is self and self._current is intent
             and runtime.owner is parent.batch and parent.phase == 'DRAINED_ADOPTION'
             and parent.index == 1 and parent.operation is runtime.owner._received
             and runtime.provider.consumed_use_context(runtime.owner,parent) is context
             and runtime.owner.materialization(parent) == (binding,before,after,revision),
             'ITEM_USE_BOOK_NATIVE_LIVE_LAST_DRAIN_REQUIRED')
        from tools.local_original_session import manual_move_commands as commands
        owner=source.owner
        need(type(owner) is commands.ManualMoveCommands
             and sys.modules.get(type(owner).__module__) is commands
             and hashlib.sha256(Path(commands.__file__).read_bytes()).hexdigest()==MANUAL_NATIVE_SOURCE_SHA256,
             'ITEM_USE_BOOK_NATIVE_ISSUANCE_EXACT_SOURCE_REQUIRED')
        _original(owner,'_clock',commands.ManualMoveCommands._clock)
        _original(owner,'_use_item_current',commands.ManualMoveCommands._use_item_current)
        now=owner._clock()
        pending=owner.pending; identities,scalars=source.context
        need(type(pending) is dict and identities[0] is owner and identities[1] is pending
             and identities[2] is pending.get('request') and identities[3] is writer
             and identities[4] is row and identities[5] is row['operation_lock']
             and identities[6] is self.broker and identities[8] is pending.get('inventory_refs')
             and identities[9] is owner._bound and source.writer is writer
             and source.item_identifier == intent.request.identifier == pending.get('item_identifier')
             and pending.get('item_session') is self and pending.get('phase') == 'NATIVE_WAIT'
             and pending.get('native_attempted') is True and pending.get('item_before')+1 == ordinal
             and pending['inventory_refs'][5] is before and self.accepted_count == ordinal
             and owner.state.get('status')!='UNKNOWN' and type(now) is int
             and type(pending.get('started')) is int
             and scalars[0] == owner.sequence == pending['request'].get('seq')
             and scalars[1] == pending['item_before'] and scalars[7] == pending.get('started')
             and scalars[8] == inventory._freeze_static(pending['request'])
             and intent.request.raw_payload is raw and parent.request is raw
             and intent.frame is before and intent.selection_binding is g.selection_binding
             and g is self.broker._inventory_generation and g.current_frame is before,
             'ITEM_USE_BOOK_NATIVE_SAME_PREPOST_RECEIVED_RELATION_REQUIRED')
        # The optional tool-side collection budget does not govern a server
        # transaction that has really DRAINED. Revoke only Native continuation.
        if (type(pending) is dict and type(pending.get('started')) is int
                and type(now) is int and now-pending['started']>=commands.WAIT_NS):
            self._book_native_preparation = dict(scope='LAST_PREPARATION_DECISION_ONLY_NOT_CURRENT_AUTHORITY', status='ORIGINAL_CLAIM_EXPIRED',
                accepted_ordinal=ordinal, native_sequence=owner.sequence,
                started_ns=pending['started'], checked_ns=now, original_claim_expired=True)
            self.retire_book_native()
            return None
        receipt=parent._receipt()
        need(type(receipt) is dict and receipt['phase']=='COMMITTED' and receipt['delivery']=='DRAINED'
             and receipt['uid']==binding.uid and receipt['asset_revision']==revision
             and receipt['request_sha']==runtime.canonical.request_digest(raw)
             and type(parent.txid) is str,
             'ITEM_USE_BOOK_NATIVE_LAST_DRAIN_RECEIPT_REQUIRED')
        value=object.__new__(_BookNativeCompletion)
        for name,part in dict(source=source,context=context,binding=binding,after=after,
            revision=revision,txid=parent.txid,
            receipt_json=runtime.canonical.encoded(receipt).decode('ascii')).items():
            object.__setattr__(value,name,part)
        self._book_native_preparation = dict(scope='LAST_PREPARATION_DECISION_ONLY_NOT_CURRENT_AUTHORITY', status='ISSUED',
            accepted_ordinal=ordinal, native_sequence=owner.sequence,
            started_ns=pending['started'], checked_ns=now, original_claim_expired=False)
        return value

    def book_native_current(self, source_owner, current, *, admission=False):
        """Narrow issued before->after bridge; no Native or canonical verdict."""
        value=self._book_native_completion
        if value is None:return None
        retire=ItemUseSession.retire_book_native
        try:
            from tools.local_original_session import manual_move_commands as commands
            for name in ('book_native_current','retire_book_native','_book_native_context',
                         '_complete_book_native_received'):
                _original(self,name,getattr(ItemUseSession,name))
            need(not admission and type(value) is _BookNativeCompletion
                 and type(source_owner) is commands.ManualMoveCommands
                 and sys.modules.get(type(source_owner).__module__) is commands
                 and hashlib.sha256(Path(commands.__file__).read_bytes()).hexdigest()==MANUAL_NATIVE_SOURCE_SHA256,
                 'ITEM_USE_BOOK_NATIVE_EXACT_COMPLETION_CALLER_REQUIRED')
            now=source_owner._clock()
            source=value.source; use,intent,ordinal,writer,row,g,before,raw=value.context
            pending=source_owner.pending;ids,scalars=source.context
            refs=(self.broker._inventory_service,self.broker._inventory_store,self.broker._inventory_frame,
                self.broker._inventory_selection_binding,self.broker._inventory_delivery_authority,
                self.broker._inventory_current_frame)
            need(source_owner._busy is True and source_owner._thread==threading.get_ident()
                 and source_owner.reader is self._reader and source_owner._item_use_type is type(self)
                 and source_owner._item_use_complete is ItemUseSession.complete_received
                 and source_owner._item_use_book_current is ItemUseSession.book_native_current
                 and source_owner._item_use_book_retire is ItemUseSession.retire_book_native
                 and type(source) is _NativeSourceRead and source.owner is source_owner
                 and use is self and self._native_pending_read is source and self._current is None
                 and self._backend_completion is None and not self.closed and not self._released
                 and not self.broker._closing and not self.broker.failure.is_set()
                 and type(self.policy) is str and self.policy==POLICY
                 and type(self._collection_policy) is type(getattr(self.broker,'_inventory_collection_policy',None))
                 and self._collection_policy==getattr(self.broker,'_inventory_collection_policy',None)
                 and type(pending) is dict and pending is ids[1] and pending.get('kind')=='UseItem'
                 and pending.get('phase')=='NATIVE_WAIT' and pending.get('native_attempted') is True
                 and pending.get('request') is ids[2] and pending.get('inventory_refs') is ids[8]
                 and source_owner._bound is ids[9] and pending.get('item_session') is self
                 and pending.get('item_identifier')==source.item_identifier==intent.request.identifier
                 and source.writer is writer and current[0].writer is writer
                 and current[0].broker is self.broker and current[1] is row and row['writer'] is writer
                 and current[3] is pending['initial'] is ids[7] and current[7]==pending['before']
                 and current[3].uid==value.binding.uid and pending['request'].get('player_uid')==current[3].uid
                 and pending['request'].get('map_id')==current[3].map_id
                 and source_owner.sequence==scalars[0]==pending['request'].get('seq')
                 and pending['item_before']==scalars[1] and ordinal==scalars[1]+1==self.accepted_count
                 and scalars[7]==pending['started'] and scalars[8]==inventory._freeze_static(pending['request'])
                 and intent.request.raw_payload is raw and intent.frame is before
                 and self.last_invalidation=='ITEM_USE_WRITER_RELEASED'
                 and self.last_outcome.kind is OutcomeKind.ACCEPTED
                 and self.last_outcome.accepted_ordinal==ordinal
                 and all(refs[n] is pending['inventory_refs'][n] for n in range(5))
                 and pending['inventory_refs'][5] is before and refs[5] is value.after
                 and self.broker._inventory_generation is g and g.phase=='ACTIVE'
                 and g.writer is writer and g.row is row and g.lock is row['operation_lock']
                 and g.item_use_session is self and g.current_frame is value.after
                 and g.selection_binding is intent.selection_binding is refs[3]
                 and source_owner.state.get('status')!='UNKNOWN'
                 and type(now) is int and now-pending['started']<commands.WAIT_NS,
                 'ITEM_USE_BOOK_NATIVE_COMPLETION_RELATION_CHANGED')
            return value
        except BaseException:
            retire(self)
            raise

    def _book_native_context(self, writer, item_identifier, ordinal, source_owner):
        from tools.local_original_session import manual_move_commands as commands
        for name in ('_poll_use_item','_use_item_current','_use_item_result','_clock'):
            _original(source_owner,name,getattr(commands.ManualMoveCommands,name))
        current=source_owner._use_item_current()
        value=self.book_native_current(source_owner,current)
        need(type(value) is _BookNativeCompletion and value.context[3] is writer
             and value.context[2]==ordinal and value.source.item_identifier==item_identifier
             and self._lock.locked() and self._inflight_writer is writer
             and current[1]['operation_lock'].locked(),
             'ITEM_USE_BOOK_NATIVE_COMPLETION_LOCKED_SOURCE_REQUIRED')
        from tools.local_original_session.broker import PersistentBroker
        _original(self._service,'_current',inventory.InventoryService._current)
        _original(self._service,'_persistence_store',inventory.InventoryService._persistence_store)
        _original(self._reader,'validate',observe.RetainedSceneReader.validate)
        _original(self._store,'restore',InventoryStore.restore)
        _original(self.broker,'_checkpoint',PersistentBroker._checkpoint)
        need(self._service._persistence_store() is self._store
             and self._service.reader is self._reader and self._reader.backend is self._backend,
             'ITEM_USE_BOOK_NATIVE_CURRENT_SERVICE_REQUIRED')
        restart=current[1].get('_restart')
        need(restart is None or type(restart) is dict and restart.get('phase')=='DRAINED'
             and restart.get('selection_cleared') is True,'ITEM_USE_BOOK_NATIVE_NO_PENDING_RESTART_REQUIRED')
        admitted=current[1]['policy_row']
        need(admitted.drain_started_ns is None and admitted.pending_opcode is None and admitted.pending_size==0,
             'ITEM_USE_BOOK_NATIVE_NO_PENDING_DELIVERY_REQUIRED')
        if getattr(self.broker,'_item_transfer_policy_bound',None) is not None:
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            transfer=self.broker._inventory_generation.transfer_session
            need(type(transfer) is ItemTransferSession,'ITEM_USE_REAL_CUSTODY_SESSION_REQUIRED')
            transfer.validate_use_locked(writer,read_only_initialization=False)
        authority=self._service._current(writer,current[1])
        runtime=_BOOK_RUNTIMES.get(self.broker)
        need(type(runtime) is _BookRuntime,'ITEM_USE_BOOK_NATIVE_RUNTIME_REQUIRED')
        book_current=_original(self,'_book_current',runtime.methods[13])
        memory=book_current(writer,current[1],authority,value.after)
        need(memory is not None and memory.generation_ref() is value.context[5]
             and memory.frame is value.after and memory.uid==value.binding.uid
             and memory.revision==value.revision and memory.txid==value.txid
             and memory.request is value.context[7] and memory.receipt_json==value.receipt_json
             and self._store.restore(memory.uid)==value.after,
             'ITEM_USE_BOOK_NATIVE_ACTUAL_CANONICAL_LINEAGE_REQUIRED')
        self._reader.validate()
        source_owner._use_item_result(current)  # Original immutable result-file schema/identity.
        pending=source_owner.pending; policy=self.broker.policy
        offset=pending['event_start']-(policy.events-len(policy.log))
        need(0<=offset<=len(policy.log),'ITEM_USE_BOOK_NATIVE_RX_PROOF_DROPPED')
        received=[e for e in list(policy.log)[offset:] if e[0]=='rx'
            and e[1]==current[1]['peer']['endpoint_port'] and e[2]==0x0960]
        need(len(received)==1 and current[1]['policy_row'].received>pending['received_base']
             and type(pending['native']) is dict and pending['native'].get('status')=='RETURNED'
             and pending['native'].get('invoked') is True and pending['native'].get('reason')==0
             and type(pending['result_identity']) is tuple and len(pending['result_identity'])==4,
             'ITEM_USE_BOOK_NATIVE_ACTUAL_RETURN_AND_RECEIVED_REQUIRED')
        native_frozen=inventory._freeze_static(pending['native'])
        result_identity=pending['result_identity']
        book_current(writer,current[1],authority,value.after)
        need(inventory._freeze_static(pending['native'])==native_frozen
             and pending['result_identity']==result_identity,
             'ITEM_USE_BOOK_NATIVE_RESULT_CHANGED_AFTER_READ')
        need(self.book_native_current(source_owner,current) is value,
             'ITEM_USE_BOOK_NATIVE_POST_READ_CHANGED')
        task=asyncio.current_task()
        need(task is not None and not task.cancelling(),'ITEM_USE_BOOK_NATIVE_CURRENT_TASK_REQUIRED')
        return (value,pending,pending['request'],inventory._freeze_static(pending['request']),
            inventory._freeze_static(pending['native']),pending['result_identity'],authority,memory,
            source_owner._bound,source_owner.sequence,pending['started'],task,
            self.broker._canonical_provider._scope)

    async def _prepare_book_empty_equipment_received(self, writer, item_identifier, ordinal, source_owner, before):
        # 원 Native 완료의 살아 있는 row/scope/lock/witness에서만 서버 복원을 소비한다.
        runtime=_BOOK_RUNTIMES.get(self.broker)
        need(type(runtime) is _BookRuntime,'ITEM_USE_BOOK_REGISTERED_RUNTIME_REQUIRED')
        need(_book_methods(runtime.owner,runtime.owner_module,runtime.delivery_module,runtime.store,
             runtime.provider,runtime.readcap)==runtime.methods,'ITEM_USE_BOOK_ORIGINAL_METHODS_CHANGED')
        effect=_book_equipment_current(self.broker,runtime.equipment)
        if effect is None:return  # Eq-off의 기존 Native 완료는 바꾸지 않는다.
        value=before[0]
        items=inventory.validate_current_collection_frame(value.after,policy=inventory.COLLECTION_POLICY)
        if items and (any(item.template_bits==1 for item in items)
                      or not all(item.template_bits in (180,181) for item in items)):
            return  # 실 지원 무기가 있는 기존 경로와 다른 비책 상태는 불변이다.
        bound=runtime.equipment
        need(effect._collection_policy==inventory.COLLECTION_POLICY,
             'ITEM_USE_BOOK_EMPTY_EQUIPMENT_COLLECTION_REQUIRED')
        need(self._book_native_completion is value and self._lock.locked()
             and self._inflight_writer is writer and not self.closed and not self._released
             and runtime.provider._scope is before[12] and before[12][0] is asyncio.current_task()
             and before[12][1]==threading.get_ident()
             and value.context[4]['operation_lock'].locked(),
             'ITEM_USE_BOOK_EMPTY_EQUIPMENT_SOURCE_OPERATION_REQUIRED')
        methods=dict(bound.methods)
        context=methods['_context'](effect,writer)
        need(context['frame'] is value.after and context['generation'] is value.context[5]
             and context['row'] is value.context[4] and context['writer'] is writer
             and context['service'] is self and tuple(context['items'])==items,
             'ITEM_USE_BOOK_EMPTY_EQUIPMENT_CONTEXT_REQUIRED')
        previous=(effect._operation,effect._collection_batch)
        _book_equipment_current(self.broker,bound)
        receipt=await methods['prepare_locked'](effect,writer)  # row lock을 다시 얻지 않는다.
        _book_equipment_current(self.broker,bound)
        need(_book_methods(runtime.owner,runtime.owner_module,runtime.delivery_module,runtime.store,
             runtime.provider,runtime.readcap)==runtime.methods,'ITEM_USE_BOOK_ORIGINAL_METHODS_CHANGED')
        native_context=_original(self,'_book_native_context',runtime.methods[22])
        current=native_context(writer,item_identifier,ordinal,source_owner)
        need(all(before[n] is current[n] for n in (0,1,2,7,8,11,12))
             and before[3:6]==current[3:6] and before[9:11]==current[9:11],
             'ITEM_USE_BOOK_EMPTY_EQUIPMENT_NATIVE_CHANGED')
        inventory.InventoryService._same(before[6],current[6])
        after=methods['_context'](effect,writer)
        methods['_same'](effect,context,after)
        _book_equipment_current(self.broker,bound)
        life=effect._selection
        need(type(receipt) is dict and receipt==effect._last and type(life) is dict
             and life.get('server_ready') is True and life.get('synced') is False
             and life.get('frame') is value.after and life.get('sync_receipt')==receipt
             and life['state'].weapon_uid==0
             and effect._operation is previous[0] and effect._collection_batch is previous[1]
             and receipt.get('status')==('RESTORED_EMPTY' if not items else 'RESTORED_UNEQUIPPED')
             and receipt.get('phase')=='NO_NOTIFICATIONS' and receipt.get('operation')=='INITIAL_SYNC'
             and receipt.get('accepted_ordinal') is None and receipt.get('after_weapon_uid')==0
             and receipt.get('initialization_source')=='RESTORED_EQUIPMENT_SIDECAR'
             and all(receipt.get(k) is True for k in ('writer_bound','generation_bound','server_state_verified'))
             and all(receipt.get(k) is False for k in ('persist_attempted','persisted','write_attempted',
                 'drain_returned','post_owner_verified'))
             and all(type(receipt.get(k)) is int and receipt[k]==0 for k in
                 ('notification_count','notifications_attempted','notifications_drained'))
             and receipt.get('notification_records')==[]
             and all(receipt.get(k) is None for k in ('notification_opcode','notification_size','notification_sha256'))
             and receipt.get('client_state')=='UNKNOWN',
             'ITEM_USE_BOOK_EMPTY_EQUIPMENT_RESTORE_REQUIRED')

    async def _complete_book_native_received(self, writer, item_identifier, ordinal, source_owner):
        methods=tuple((name,getattr(ItemUseSession,name)) for name in
            ('_book_native_context','book_native_current','retire_book_native','_book_current',
             '_prepare_book_empty_equipment_received'))
        for name,function in methods:_original(self,name,function)
        async with self._lock:
            self._inflight_writer,self._released=writer,False
            try:
                before=self._book_native_context(writer,item_identifier,ordinal,source_owner)
                await self.broker._checkpoint(writer,before[0].context[4])
                for name,function in methods:_original(self,name,function)
                after=self._book_native_context(writer,item_identifier,ordinal,source_owner)
                need(all(before[n] is after[n] for n in (0,1,2,7,8,11,12))
                     and before[3:6]==after[3:6] and before[9:11]==after[9:11],
                     'ITEM_USE_BOOK_NATIVE_COMPLETION_CHANGED_DURING_CHECKPOINT')
                inventory.InventoryService._same(before[6],after[6])
                runtime=_BOOK_RUNTIMES.get(self.broker)
                need(type(runtime) is _BookRuntime,'ITEM_USE_BOOK_REGISTERED_RUNTIME_REQUIRED')
                prepare=_original(self,'_prepare_book_empty_equipment_received',runtime.methods[24])
                await prepare(writer,item_identifier,ordinal,source_owner,after)
                for name,function in methods:_original(self,name,function)
                need(self._current is None and self.accepted_count==ordinal,
                     'ITEM_USE_BOOK_NATIVE_RELEASE_POSTSTATE_REQUIRED')
                return True
            finally:
                methods[2][1](self)
                self._inflight_writer,self._released=None,False

    def _book_current(self, writer, row, authority, frame, *, equipment_operation=None,
                      history_only=False, expected_context=None, native_source=None):
        runtime=_BOOK_RUNTIMES.get(self.broker)
        if runtime is None:return None
        owner,m,store,provider,readcap=(runtime.owner,runtime.canonical,runtime.store,
                                     runtime.provider,runtime.readcap)
        _original(owner,'adoption_memory',runtime.methods[2])
        value=owner.adoption_memory(writer)
        if value is None:return None
        need(type(value) is runtime.owner_module.BookAdoptionMemory and value.frame is frame,
             'ITEM_USE_BOOK_CURRENT_ADOPTION_REQUIRED')
        b=self.broker
        def current():
            need(_BOOK_RUNTIMES.get(b) is runtime and not owner.closed
                 and _book_methods(owner,runtime.owner_module,runtime.delivery_module,store,provider,
                     readcap)==runtime.methods and readcap.check() is m
                 and type(store) is m.BatchStore and type(provider) is m.BrokerProvider
                 and store.provider is provider and provider.broker is b
                 and store.source is provider.source_store is self._store
                 and self._store._aggregate_capability is self._store._aggregate_bound is readcap
                 and m._OWNERS.get(store._key) is store and not store.closed and not store.failed
                 and not store._catalog_validating and not store._delivery_validating
                 and not store._original_update_validating and store.active is None and not store._delivery_caps
                 and (store.path,store.profile,store._paths,self._store.path,self._store.profile,
                      self._store._aggregate_paths,self._store._custody_paths)==runtime.paths,
                 'ITEM_USE_BOOK_CANONICAL_RUNTIME_CHANGED')
            for path,sha,module in runtime.source_pins:
                need(sys.modules.get(module.__name__) is module and Path(module.__file__).resolve()==path
                     and hashlib.sha256(path.read_bytes()).hexdigest()==sha,
                     'ITEM_USE_BOOK_SOURCE_CHANGED')
            _original(store,'_read',runtime.methods[6]);_original(store,'_path_check',runtime.methods[7])
            _original(self._store,'_path_check',runtime.methods[8]);store._path_check()
            _original(readcap,'check',runtime.methods[9]);_original(readcap,'project',runtime.methods[10])
            _original(owner,'adoption_memory',runtime.methods[2])
            connection=_original(provider,'_connection',runtime.methods[14])
            selection=_original(b,'inventory_selection_current',runtime.methods[15])
            scope=provider._scope
            need(type(scope) is tuple and len(scope)==10,'ITEM_USE_BOOK_REAL_SCOPE_REQUIRED')
            connection(writer,row,scope=scope)
            g=selection(writer);intent=self._current
            need(g is not None and g.item_use_session is self and g.row is row and g.writer is writer
                 and g.store is self._store and g.lock is row['operation_lock'] and g.current_frame is frame
                 and value.generation_ref() is g and value.uid==authority[0].uid
                 and owner.adoption_memory(writer) is value and not self.closed and not self._released,
                 'ITEM_USE_BOOK_SAME_CURRENT_GENERATION_REQUIRED')
            received=(type(intent) is _Intent and intent.writer is writer and intent.frame is frame
                      and intent.selection_binding is g.selection_binding and intent.adoption is value
                      and intent.accepted_ordinal==self.accepted_count)
            inflight=self._lock.locked() and self._inflight_writer is writer
            native=native_source is not None
            if native:
                need(type(native_source) is _NativeSourceRead and self._native_source_read is native_source
                     and native_source.writer is writer and self._inflight_writer is writer,
                     'ITEM_USE_BOOK_ACTUAL_NATIVE_SOURCE_REQUIRED')
                self._same_native_source(native_source.context,self._native_source_context(
                    native_source.owner,writer,native_source.item_identifier))
            if equipment_operation is not None:
                effect=b._item_equipment_effect
                need(effect is not None and effect._operation is equipment_operation,
                     'ITEM_USE_BOOK_ACTUAL_EQUIPMENT_OPERATION_REQUIRED')
            need(inflight or received or native or equipment_operation is not None,
                 'ITEM_USE_BOOK_ACTUAL_SOURCE_OPERATION_REQUIRED')
            task=asyncio.current_task()
            need(task is not None and not task.cancelling() and scope[0] is task
                 and scope[1]==threading.get_ident(),'ITEM_USE_BOOK_CURRENT_TASK_REQUIRED')
            return (scope,g,intent,self._inflight_writer,self._released,self.closed,
                self._lock.locked(),self.accepted_count,b._inventory_update_operation,
                b._inventory_frame,b._inventory_operation_frame,b._inventory_selection_binding,
                b._inventory_delivery_authority,self.last_outcome,self.last_invalidation,
                self._service,self._reader,self._backend,self._store,self._store_bound,self._realm,
                b._inventory_service,b.realm,b._item_use_session,b.realm._item_use_session,
                b._item_equipment_effect,None if b._item_equipment_effect is None else b._item_equipment_effect._operation,
                None if b._item_equipment_effect is None else b._item_equipment_effect._collection_batch)
        with inventory_store._lock,inventory_store.realm._lock:
            before=current()
            def same(old,new):
                return len(old)==len(new) and all(a==z if n in (4,5,6,7) else a is z
                    for n,(a,z) in enumerate(zip(old,new)))
            need(expected_context is None or same(expected_context,before),
                 'ITEM_USE_BOOK_RESTORE_SOURCE_CHANGED')
            if history_only:return value,before
            old_raw,old_data=store._raw,m.encoded(store.data)
            raw,document=store._read()
            need(raw==old_raw==store._raw and m.encoded(document)==old_data==m.encoded(store.data),
                 'ITEM_USE_BOOK_CANONICAL_PREIMAGE_CHANGED')
            rows=m.BatchStore._validate_canonical(store,document['canonical'])
            tx=document['transactions'].get(value.txid)
            need(rows.get(value.uid)==frame and document['revisions'].get(str(value.uid))==value.revision
                 and type(tx) is dict and tx['uid']==value.uid and tx['asset_revision']==value.revision
                 and tx['request_sha']==m.request_digest(value.request) and tx['phase']=='COMMITTED'
                 and tx['delivery']=='DRAINED' and m.encoded(tx).decode('ascii')==value.receipt_json
                 and document['pending'] is None,'ITEM_USE_BOOK_CURRENT_REVISION_RECEIPT_REQUIRED')
            after=current()
            with runtime.paths[0].open('rb') as stream:final_raw=stream.read(m.MAX_BYTES+1)
            need(final_raw==old_raw==store._raw and m.encoded(store.data)==old_data and same(before,after),
                 'ITEM_USE_BOOK_POST_CALLBACK_CHANGED')
        return value

    def _current_authority(self, writer, *, equipment_operation=None, item_identifier=None, native_source=None):
        from tools.local_original_session.broker import PersistentBroker
        broker, service, reader = self.broker, self._service, self._reader
        mode = getattr(broker, '_inventory_collection_policy', None)
        need(type(mode) is type(self._collection_policy) and mode == self._collection_policy,
             'ITEM_USE_COLLECTION_POLICY_CHANGED')
        need(type(broker) is PersistentBroker and broker.realm is self._realm
             and broker._item_use_session is self and broker.realm._item_use_session is self,
             'ITEM_USE_SAME_REGISTERED_SESSION_REQUIRED')
        need(broker._inventory_service is service and service.broker is broker
             and service.reader is reader and reader.backend is self._backend
             and service.policy == inventory.POLICY
             and getattr(broker.policy, 'item_use_intent', None) is True,
             'ITEM_USE_CURRENT_INVENTORY_SERVICE_REQUIRED')
        _original(service, '_current', inventory.InventoryService._current)
        _original(service, '_authority', inventory.InventoryService._authority)
        _original(service, '_persistence_store', inventory.InventoryService._persistence_store)
        _original(broker, '_inventory_selection_frame_current',
                  PersistentBroker._inventory_selection_frame_current)
        _original(broker, '_checkpoint', PersistentBroker._checkpoint)
        _original(reader, 'validate', observe.RetainedSceneReader.validate)
        validator = reader.backend.validate
        need(type(validator) is MethodType and validator.__self__ is reader
             and validator.__func__ is observe.RetainedSceneReader.validate,
             'ITEM_USE_ORIGINAL_RETAINED_VALIDATOR_REQUIRED')
        store = service._persistence_store()
        need(type(store) is InventoryStore and store is self._store
             and service._store_bound is self._store_bound
             and broker._inventory_store is store,
             'ITEM_USE_CURRENT_STORE_BINDING_REQUIRED')
        restore = _original(store, 'restore', InventoryStore.restore)
        rows = [row for claims in broker._claims.values() for row in claims if row['writer'] is writer]
        need(len(rows) == 1, 'ITEM_USE_CURRENT_CLAIM_REQUIRED')
        row, = rows
        restart = row.get('_restart')
        need(restart is None or type(restart) is dict and restart.get('phase') == 'DRAINED'
             and restart.get('selection_cleared') is True,
             'ITEM_USE_NO_PENDING_RESTART_REQUIRED')
        authority = service._current(writer, row)  # Current position, saved selection, lock/owner.
        transfer = getattr(broker._inventory_generation, 'transfer_session', None)
        if getattr(broker, '_item_transfer_policy_bound', None) is not None:
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            need(type(transfer) is ItemTransferSession, 'ITEM_USE_REAL_CUSTODY_SESSION_REQUIRED')
            # Admission follows validation of the actual equipment operation below.
        initial_frame = broker._inventory_frame
        need(type(initial_frame) is bytes and broker._inventory_operation_frame is initial_frame,
             'ITEM_USE_CURRENT_CANONICAL_FRAME_REQUIRED')
        broker._inventory_selection_frame_current(writer, row, initial_frame)  # Original 11 identities.
        need(type(broker._inventory_selection_binding) is tuple
             and len(broker._inventory_selection_binding) == 11,
             'ITEM_USE_ORIGINAL_SELECTION_BINDING_REQUIRED')
        delivered = broker._inventory_delivery_authority
        need(type(delivered) is tuple and len(delivered) == 3
             and type(delivered[1]) is tuple and len(delivered[1]) == 24
             and broker._inventory_attempted is True and broker._inventory_write_attempted is True
             and broker._inventory_prewrite_refusal is None
             and broker._inventory_admission_expired is False
             and service._claimed is True and service._inflight is False,
             'ITEM_USE_COMPLETED_INVENTORY_DELIVERY_REQUIRED')
        # Successful delivery proves this selection/owner/frame lifetime. Its
        # historical Position is not current movement authority: only identity
        # uid/name/map is retained across ordinary movement in the same selection.
        old_position = delivered[0]
        need(type(old_position) is movement.Position and delivered[1][14] is old_position
             and (old_position.uid, old_position.name, old_position.map_id)
                 == (authority[0].uid, authority[0].name, authority[0].map_id)
             and len(authority[1]) == len(delivered[1])
             and all(a is b for index, (a, b) in enumerate(zip(delivered[1], authority[1]))
                     if index != 14)
             and delivered[2] == authority[2], 'ITEM_USE_SAME_DELIVERED_SELECTION_REQUIRED')
        admitted = row['policy_row']
        if equipment_operation is None:
            need(admitted.drain_started_ns is None and admitted.pending_opcode is None
                 and admitted.pending_size == 0, 'ITEM_USE_NO_PENDING_INVENTORY_DELIVERY_REQUIRED')
        else:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            effect = getattr(broker, '_item_equipment_effect', None)
            need(type(effect) is ItemEquipmentEffect and effect.broker is broker and
                 effect is getattr(broker.realm, '_item_equipment_effect', None) and
                 effect.validate_pending.__func__ is ItemEquipmentEffect.validate_pending,
                 'ITEM_USE_EXACT_EQUIPMENT_CONSUMER_REQUIRED')
            effect.validate_pending(writer, row, equipment_operation, admitted)
        if getattr(broker, '_item_transfer_policy_bound', None) is not None:
            # A selected A identifier on the ORIGINAL INITIAL_SYNC notification
            # is not a received Use. validate_pending above proves exact owned
            # op/current generation/row/lock and no accepted intent or ordinal.
            initial_sync = (equipment_operation is not None and
                equipment_operation['receipt']['operation'] == 'INITIAL_SYNC')
            transfer.validate_use_locked(writer,
                read_only_initialization=item_identifier is None or initial_sync)
        # The initial ADD literal/once proof never becomes an UPDATE or current
        # value. Only the broker's post-drain canonical current frame is used.
        frame = broker._inventory_current_frame
        need(type(frame) is bytes, 'ITEM_USE_DRAINED_CURRENT_FRAME_REQUIRED')
        operation = broker._inventory_update_operation
        book_runtime=_BOOK_RUNTIMES.get(broker)
        book_current=_original(self,'_book_current',ItemUseSession._book_current if book_runtime is None
                               else book_runtime.methods[13])
        book_history = book_current(writer,row,authority,frame,
            equipment_operation=equipment_operation,history_only=True,native_source=native_source)
        adoption_history = book_history if book_history is not None else self._shop_current(writer, row, authority, frame,
                                      equipment_operation=equipment_operation, history_only=True,
                                      native_source=native_source)
        adoption, adoption_context = (None, None) if adoption_history is None else adoption_history
        if adoption is not None:
            need(operation is None or type(operation) is dict and operation.get('phase') == 'DRAINED',
                 'ITEM_USE_SHOP_PENDING_ORIGINAL_UPDATE_REFUSED')
        elif operation is None:
            need(frame is initial_frame, 'ITEM_USE_INITIAL_CURRENT_LITERAL_REQUIRED')
        else:
            need(type(operation) is dict and type(operation.get('phase')) is str
                 and operation.get('phase') == 'DRAINED'
                 and operation.get('writer') is writer and operation.get('row') is row
                 and operation.get('lock') is row['operation_lock'] and operation.get('new') is frame
                 and all(operation.get(key) is True for key in (
                     'persist_attempted', 'persisted', 'write_attempted', 'drain_returned',
                     'post_owner_verified')),
                 'ITEM_USE_DRAINED_UPDATE_LITERAL_REQUIRED')
            refs, updated = operation.get('refs'), operation.get('authority')
            current_refs = (broker.realm, broker.realm.registry, broker.realm.registry.resolve(writer),
                broker.realm.service(writer), authority[0], broker.realm.registry.resolve(writer).selection,
                service, reader, store, broker._inventory_selection_binding, delivered, initial_frame,
                broker._inventory_restore_only)
            need(type(refs) is tuple and len(refs) == 13
                 and all(a is b for index, (a, b) in enumerate(zip(refs, current_refs)) if index != 4)
                 and type(refs[4]) is movement.Position
                 and (refs[4].uid, refs[4].name, refs[4].map_id)
                     == (authority[0].uid, authority[0].name, authority[0].map_id)
                 and type(updated) is tuple and len(updated) == 3
                 and type(updated[1]) is tuple and len(updated[1]) == 24
                 and type(updated[0]) is movement.Position and updated[1][14] is updated[0]
                 and refs[4] is updated[0]
                 and (updated[0].uid, updated[0].name, updated[0].map_id)
                     == (authority[0].uid, authority[0].name, authority[0].map_id)
                 and all(a is b for index, (a, b) in enumerate(zip(updated[1], authority[1])) if index != 14)
                 and updated[2] == authority[2], 'ITEM_USE_SAME_DRAINED_UPDATE_SELECTION_REQUIRED')
            sent_before, sent_after = operation.get('sent_before'), operation.get('sent_after')
            need(type(sent_before) is int and type(sent_after) is int
                 and type(admitted.sent) is int
                 and 0 <= sent_before < sent_after <= U64_MAX and sent_after == sent_before + 1
                 and admitted.sent >= sent_after, 'ITEM_USE_DRAINED_UPDATE_COUNTER_REQUIRED')
        if self._collection_policy is None:
            item = inventory.validate_frame(frame)
            initial = inventory.validate_frame(initial_frame)
            initial_fields, current_fields = dict(initial.raw_fields), dict(item.raw_fields)
            need(adoption is not None or item.identifier == initial.identifier
                 and {n for n in initial_fields if initial_fields[n] != current_fields[n]} <= {4, 5, 7, 18},
                 'ITEM_USE_SAME_CURRENT_ITEM_FIELDS_REQUIRED')
        else:
            need(store._collection_policy == inventory_store.COLLECTION_STORE_POLICY,
                 'ITEM_USE_COLLECTION_STORE_POLICY_REQUIRED')
            current_items = inventory.validate_current_collection_frame(frame, policy=self._collection_policy)
            initial_items = inventory.validate_current_collection_frame(initial_frame, policy=self._collection_policy)
            need(adoption is not None or len(current_items) == len(initial_items) and all(
                 current.identifier == initial.identifier and
                 {n for n, value in initial.raw_fields if dict(current.raw_fields)[n] != value} <= {4, 5, 7, 18}
                 for current, initial in zip(current_items, initial_items)),
                 'ITEM_USE_SAME_CURRENT_COLLECTION_FIELDS_REQUIRED')
            if item_identifier is None:
                item = current_items[0] if current_items else None  # Empty current has no selected-use UID.
            else:
                need(type(item_identifier) is int and 0 < item_identifier < 1 << 32,
                     'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                members = tuple(item for item in current_items if item.identifier == item_identifier)
                need(len(members) == 1, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                item, = members
        restored = restore(authority[0].uid)  # Original bounded read, never grant/write.
        need(type(restored) is bytes and restored == frame,
             'ITEM_USE_CURRENT_STORED_FRAME_REQUIRED')
        if adoption is not None:
            adoption_current=book_current if book_history is not None else self._shop_current
            need(adoption_current(writer, row, authority, frame,
                 equipment_operation=equipment_operation, expected_context=adoption_context,
                 native_source=native_source) is adoption,
                 'ITEM_USE_SHOP_POST_RESTORE_ADOPTION_CHANGED')
        return row, authority, frame, delivered, broker._inventory_selection_binding, store, item, adoption

    def _project(self, writer, *, equipment_operation=None, item_identifier=None, native_source=None):
        operation = self.broker._inventory_update_operation
        before = self._current_authority(writer, equipment_operation=equipment_operation,
            item_identifier=item_identifier,native_source=native_source)
        self._reader.validate()  # Retained identity/Job, not an item-memory query.
        after = self._current_authority(writer, equipment_operation=equipment_operation,
            item_identifier=item_identifier,native_source=native_source)
        self._same(before, after)
        need(self.broker._inventory_update_operation is operation,
             'ITEM_USE_CURRENT_UPDATE_OPERATION_CHANGED')
        return after

    def _same(self, before, after):
        need(before[0] is after[0] and all(before[n] is after[n] for n in (2, 3, 4, 5)),
             'ITEM_USE_CURRENT_BINDING_CHANGED')
        inventory.InventoryService._same(before[1], after[1])  # Request-local position stays identical.
        need(before[6] == after[6], 'ITEM_USE_CURRENT_ITEM_CHANGED')
        need(before[7] is after[7], 'ITEM_USE_CURRENT_SHOP_ADOPTION_CHANGED')

    @staticmethod
    def _source(request):
        item_use.source_ready()
        if 17 in request.params.present_fields:
            item_use._enum17_one_source_ready()

    async def handle(self, writer, payload) -> tuple[bytes, ...]:
        """Validate this received request only, returning no ACK/effect frames.

        Identifier mismatch is a local REJECTED result. Parser/source/current
        owner/Store errors propagate unchanged after fixed-category reporting.
        """
        async with self._lock:
            self._released = False
            self._inflight_writer = writer
            try:
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                request = item_use.parse_payload(payload)
                operation = self.broker._inventory_update_operation
                try:
                    before = self._project(writer, item_identifier=request.identifier)
                except ValueError as error:
                    if str(error) != 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM':raise
                    self._clear('ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                    return self._outcome(OutcomeKind.REJECTED, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                if request.identifier != before[6].identifier:
                    self._clear('ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                    return self._outcome(OutcomeKind.REJECTED, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                await self.broker._checkpoint(writer, before[0])
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                self._source(request)
                after = self._project(writer, item_identifier=request.identifier)
                self._same(before, after)
                need(self.broker._inventory_update_operation is operation,
                     'ITEM_USE_CURRENT_UPDATE_OPERATION_CHANGED')
                unavailable = self._unavailable()
                if unavailable is not None:
                    self._clear(unavailable[1])
                    return self._outcome(*unavailable)
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                ordinal = self.accepted_count + 1
                self._current = _Intent(request, writer, ordinal, after[2], after[4], after[7])
                self.accepted_count = ordinal
                self.last_invalidation = None
                return self._outcome(OutcomeKind.ACCEPTED, 'VALIDATED_ITEM_USE_INTENT_ONLY', ordinal)
            except asyncio.CancelledError:
                self._clear('ITEM_USE_SESSION_CANCELLED')
                self._outcome(OutcomeKind.CANCELLED, 'ITEM_USE_SESSION_CANCELLED')
                raise
            except Exception as error:
                category = _category(error)
                self._clear(category)
                self._outcome(OutcomeKind.ERROR, category)
                raise
            finally:
                self._inflight_writer = None
                self._released = False

    async def validate_native_request(self, writer, item_identifier):
        """Current read-only admission before the caller's native request.

        Caller holds the real row lock. True is no request/params, send, native
        item query, received intent or transferable permission. Any refusal
        raises; original source/owner/Store/cancellation errors propagate. Only
        the existing transient in-flight state changes during this call.
        """
        async with self._lock:
            self._inflight_writer, self._released = writer, False
            try:
                need(self._unavailable() is None, 'ITEM_USE_NATIVE_VALIDATION_UNAVAILABLE')
                need(type(item_identifier) is int and 0 <= item_identifier <= U64_MAX,
                     'ITEM_USE_UINT64_IDENTIFIER_REQUIRED')
                item_use.source_ready()
                operation = self.broker._inventory_update_operation
                before = self._project(writer, item_identifier=item_identifier)
                need(item_identifier == before[6].identifier, 'ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
                await self.broker._checkpoint(writer, before[0])
                need(self._unavailable() is None, 'ITEM_USE_NATIVE_VALIDATION_UNAVAILABLE')
                item_use.source_ready()
                after = self._project(writer, item_identifier=item_identifier)
                self._same(before, after)
                need(self.broker._inventory_update_operation is operation,
                     'ITEM_USE_CURRENT_UPDATE_OPERATION_CHANGED')
                need(self._unavailable() is None, 'ITEM_USE_NATIVE_VALIDATION_UNAVAILABLE')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                return True
            finally:
                self._inflight_writer, self._released = None, False

    def matches_received(self, writer, item_identifier, accepted_ordinal):
        """Observe the current received raw0-shaped intent under caller row lock.

        Missing read authority or mismatched writer/id/ordinal/params returns
        False. Source and IO failures propagate unchanged; other unexpected
        errors also propagate. This never consumes a receipt or records a new
        acceptance: repeated True observes the same ordinal only.
        """
        current = self._current
        if (self.closed or type(self.policy) is not str or self.policy != POLICY
                or type(item_identifier) is not int or not 0 <= item_identifier <= U64_MAX
                or type(accepted_ordinal) is not int or not 1 <= accepted_ordinal <= U64_MAX
                or current is None or current.writer is not writer
                or current.request.identifier != item_identifier
                or current.accepted_ordinal != accepted_ordinal):
            return False
        params = current.request.params
        if params.present_fields != {1, 15, 16} or len(params.fields) != 3:
            return False
        expected = {1: 1, 15: 0, 16: 0}
        if any(part.kind != 'int32' or type(part.value) is not int
               or part.value != expected[part.number] for part in params.fields):
            return False
        _raw0_source_ready()
        try:
            current_authority = self._project(writer, item_identifier=item_identifier)
        except item_use.ItemUseSourceError:
            raise
        except ValueError as error:
            if str(error) in _INVENTORY_SOURCE_ERRORS:
                raise
            return False
        _raw0_source_ready()
        return (self._current is current and not self.closed
                and type(self.policy) is str and self.policy == POLICY
                and current_authority[2] is current.frame
                and current_authority[4] is current.selection_binding
                and current_authority[7] is current.adoption
                and current_authority[6].identifier == item_identifier)

    def _backend_completion_current(self,writer,item_identifier,accepted_ordinal):
        value=self._backend_completion
        witness=_BACKEND_COMPLETIONS.get(value) if type(value) is BackendCompletion else None
        g=self.broker._inventory_generation;effect=getattr(self.broker,'_item_equipment_effect',None)
        need(type(value) is BackendCompletion and type(witness) is tuple and len(witness)==6
             and witness[0]() is self and witness[1]() is g and witness[2]() is effect
             and id(value.intent)==witness[3] and value.operation_id==witness[4]
             and value.effect_snapshot==witness[5]
             and value.kind=='BACKEND_EQUIPMENT_LEASE_COMPLETED'
             and self._current is None and not self.closed and self.accepted_count==accepted_ordinal==value.accepted_ordinal
             and value.intent.writer is writer and value.intent.request.identifier==item_identifier
             and value.generation_ref() is g and value.effect_ref() is effect
             and g.phase=='ACTIVE' and g.item_use_session is self and g.writer is writer
             and g.current_frame is value.intent.frame and g.selection_binding is value.intent.selection_binding
             and effect is not None and id(effect._operation)==value.operation_id
             and inventory._freeze_static(effect._last)==value.effect_snapshot,
             'ITEM_USE_CURRENT_ISSUED_BACKEND_COMPLETION_REQUIRED')
        params=value.intent.request.params
        need(params.present_fields=={1,15,16} and len(params.fields)==3
             and all(part.kind=='int32' and type(part.value) is int and part.value=={1:1,15:0,16:0}[part.number]
                     for part in params.fields),'ITEM_USE_COMPLETION_RAW0_RECEIVED_REQUIRED')
        _raw0_source_ready()
        return value

    async def complete_backend_received(self,writer,accepted_ordinal,expected_intent,*,effect,source_owner):
        from tools.local_original_session.broker import PersistentBroker
        methods=(('_project',ItemUseSession._project),('_same',ItemUseSession._same),
                 ('release',ItemUseSession.release),('_effect_completion_current',ItemUseSession._effect_completion_current))
        for name,function in methods:_original(self,name,function)
        project,same,release,effect_current=(part[1] for part in methods)
        need(type(source_owner) is PersistentBroker and source_owner is self.broker
             and effect is source_owner._item_equipment_effect,'ITEM_USE_BACKEND_ACTUAL_SOURCE_REQUIRED')
        async with self._lock:
            self._inflight_writer,self._released=writer,False
            try:
                need(self._current is expected_intent and type(expected_intent) is _Intent
                     and expected_intent.writer is writer and expected_intent.accepted_ordinal==accepted_ordinal
                     and self.accepted_count==accepted_ordinal and self.last_invalidation is None,
                     'ITEM_USE_BACKEND_SAME_ISSUED_INTENT_REQUIRED')
                before=project(self,writer,item_identifier=expected_intent.request.identifier)
                await source_owner._checkpoint(writer,before[0])
                for name,function in methods:_original(self,name,function)
                after=project(self,writer,item_identifier=expected_intent.request.identifier);same(self,before,after)
                ec=effect_current(self,writer,expected_intent.request.identifier,expected_intent,row=after[0])
                need(ec is not None,'ITEM_USE_BACKEND_EQUIPMENT_REQUIRED')
                eq_path,eq_raw,eq_identity,eq_policy=ec[-4:]
                with eq_path.open('rb') as stream:final_raw=stream.read(effect.store.MAX_BYTES+1)
                need(final_raw==eq_raw,'ITEM_USE_BACKEND_FINAL_EQUIPMENT_PREIMAGE_CHANGED')
                need(all(eq_identity[n] is (effect.store.path,effect.store._path,effect.store.profile,
                         effect.store._profile,effect.store._inventory_path,effect.store.inventory_store)[n] for n in range(6))
                     and eq_policy==(effect.policy,effect._collection_policy,effect._form_policy,effect._switch_policy,
                         effect._limit_weapon_switching,effect._barrier_policy)
                     and effect._selection is ec[5] and effect._operation is ec[3] and effect._consumed is ec[1]
                     and effect._last is ec[2] and inventory._freeze_static(effect._last)==ec[6]
                     and ec[5]['state'] is ec[3]['state'],
                     'ITEM_USE_BACKEND_FINAL_EQUIPMENT_OWNER_CHANGED')

                task=asyncio.current_task();g=source_owner._inventory_generation;provider=source_owner._canonical_provider
                need(task is not None and not task.cancelling() and self._current is expected_intent
                     and g.phase=='ACTIVE' and g.item_use_session is self and g.writer is writer
                     and g.current_frame is expected_intent.frame and g.row is after[0] and g.lock.locked()
                     and provider._scope is not None and provider._scope[0] is task
                     and provider._scope[2] is writer and provider._scope[3] is g.row,
                     'ITEM_USE_BACKEND_FINAL_SOURCE_CHANGED')
                for name,function in methods:_original(self,name,function)
                value=object.__new__(BackendCompletion)
                for name,part in dict(kind='BACKEND_EQUIPMENT_LEASE_COMPLETED',accepted_ordinal=accepted_ordinal,
                    intent=expected_intent,generation_ref=weakref.ref(g),effect_ref=weakref.ref(effect),
                    operation_id=id(effect._operation),effect_snapshot=inventory._freeze_static(effect._last)).items():
                    object.__setattr__(value,name,part)
                release(self,writer)
                _BACKEND_COMPLETIONS[value]=(weakref.ref(self),weakref.ref(g),weakref.ref(effect),
                    id(expected_intent),value.operation_id,value.effect_snapshot)
                self._backend_completion=value
                return value
            finally:self._inflight_writer,self._released=None,False

    def _effect_completion_current(self, writer, item_identifier, intent, *, row):
        accepted_ordinal=intent.accepted_ordinal
        effect=getattr(self.broker,'_item_equipment_effect',None)
        effect_context=None
        if effect is not None:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            need(type(effect) is ItemEquipmentEffect and effect.broker is self.broker
                 and self._realm._item_equipment_effect is effect,'ITEM_USE_COMPLETION_REAL_EFFECT_REQUIRED')
            consumed=effect._consumed;receipt=effect._last;op=effect._operation;batch=effect._collection_batch
            need(type(consumed) is tuple and len(consumed)==3 and consumed[0] is self
                 and consumed[1]==accepted_ordinal and consumed[2] is receipt and type(receipt) is dict
                 and receipt.get('operation')=='ITEM_USE_EFFECT' and receipt.get('accepted_ordinal')==accepted_ordinal
                 and receipt.get('status')=='COMMITTED' and receipt.get('phase')=='DRAINED'
                 and all(receipt.get(k) is True for k in ('persisted','drain_returned','post_owner_verified'))
                 and type(op) is dict and op.get('phase')=='DRAINED' and op.get('intent') is intent
                 and op['context']['service'] is self and op['context']['writer'] is writer
                 and op['context']['row'] is row and op['context']['generation'] is self.broker._inventory_generation
                 and op['context']['frame'] is intent.frame and op['lock'] is row['operation_lock'],
                 'ITEM_USE_COMPLETION_SAME_DRAINED_EFFECT_REQUIRED')
            if batch is not None:
                records=receipt.get('notification_records')
                need(type(batch) is dict and batch.get('phase')=='DRAINED' and op.get('batch') is batch
                     and batch.get('receipt') is receipt and batch.get('context') is op['context']
                     and type(records) is list and len(records)==len(batch['changes'])==batch['next']
                     and len(records)>0 and receipt.get('notifications_drained')==len(records)
                     and records[-1] is op['receipt']
                     and all(type(r) is dict and r.get('phase')=='DRAINED' and all(r.get(k) is True
                         for k in ('write_attempted','drain_returned','post_owner_verified')) for r in records),
                     'ITEM_USE_COMPLETION_EXACT_COLLECTION_DRAIN_REQUIRED')
            from tools.local_original_session.equipment_store import EquipmentStore
            _original(effect,'_context',ItemEquipmentEffect._context)
            _original(effect,'_same',ItemEquipmentEffect._same)
            need(type(effect.store) is EquipmentStore and effect.store.inventory_store is self._store,
                 'ITEM_USE_COMPLETION_REAL_EQUIPMENT_STORE_REQUIRED')
            _original(effect.store,'restore',EquipmentStore.restore)
            effect_current=effect._context(writer,item_identifier=item_identifier)
            effect._same(op['context'],effect_current)
            life=effect._selection
            need(type(life) is dict and life.get('synced') is True and life.get('state') is op['state']
                 and type(life.get('identity')) is tuple and len(life['identity'])==7
                 and len(effect_current['identity'])==7
                 and all(life['identity'][n] is effect_current['identity'][n] for n in range(7)),
                 'ITEM_USE_COMPLETION_CURRENT_EQUIPMENT_LIFE_REQUIRED')
            eq_path=effect.store._path
            eq_identity=(effect.store.path,effect.store._path,effect.store.profile,effect.store._profile,
                         effect.store._inventory_path,effect.store.inventory_store)
            eq_policy=(effect.policy,effect._collection_policy,effect._form_policy,effect._switch_policy,
                       effect._limit_weapon_switching,effect._barrier_policy)
            with eq_path.open('rb') as stream:eq_raw=stream.read(effect.store.MAX_BYTES+1)
            need(len(eq_raw)<=EquipmentStore.MAX_BYTES,'ITEM_USE_COMPLETION_EQUIPMENT_FILE_BOUND')
            restored=effect.store.restore(effect_current['character_uid'],effect_current['frame'])
            effect_after=effect._context(writer,item_identifier=item_identifier)
            effect._same(effect_current,effect_after)
            need(restored==op['state']==life['state'] and effect._selection is life
                 and self.broker._inventory_generation is effect_after['generation']
                 and self.broker._inventory_current_frame is effect_after['frame']
                 and self.broker._item_equipment_effect is effect
                 and effect._operation is op and effect._consumed is consumed and effect._last is receipt,
                 'ITEM_USE_COMPLETION_CURRENT_SIDECAR_CHANGED')
            with eq_path.open('rb') as stream:eq_after_raw=stream.read(effect.store.MAX_BYTES+1)
            need(eq_after_raw==eq_raw,'ITEM_USE_COMPLETION_EQUIPMENT_PREIMAGE_CHANGED')
            effect_context=(effect,consumed,receipt,op,batch,effect._selection,
                            inventory._freeze_static(receipt),(op['state'].character_uid,op['state'].item_uid,
                                op['state'].template,op['state'].weapon_uid,op['state'].revision),
                            eq_path,eq_raw,eq_identity,eq_policy)
        return effect_context

    def _completion_context(self, writer, item_identifier, accepted_ordinal, source_owner, *, completion_methods):
        from tools.local_original_session import manual_move_commands as commands
        need(type(source_owner) is commands.ManualMoveCommands
             and sys.modules.get(type(source_owner).__module__) is commands
             and hashlib.sha256(Path(commands.__file__).read_bytes()).hexdigest() == MANUAL_NATIVE_SOURCE_SHA256,
             'ITEM_USE_COMPLETION_EXACT_SOURCE_REQUIRED')
        for name in ('_poll_use_item','_use_item_current','_use_item_result','_clock'):
            _original(source_owner,name,getattr(commands.ManualMoveCommands,name))
        need(source_owner._busy is True and source_owner._thread == threading.get_ident()
             and source_owner.reader is self._reader and source_owner._item_use_type is type(self)
             and source_owner._item_use_complete is ItemUseSession.complete_received
             and self._lock.locked() and self._inflight_writer is writer
             and not self.closed and not self._released,'ITEM_USE_COMPLETION_ACTUAL_OWNER_REQUIRED')
        pending=source_owner.pending
        need(type(pending) is dict and pending.get('kind')=='UseItem'
             and pending.get('phase')=='NATIVE_WAIT' and pending.get('native_attempted') is True
             and pending.get('item_session') is self and pending.get('item_identifier')==item_identifier
             and type(pending.get('item_before')) is int and pending['item_before']+1==accepted_ordinal
             and type(pending.get('request')) is dict and type(pending.get('native')) is dict
             and type(pending.get('result_identity')) is tuple and len(pending['result_identity'])==4,
             'ITEM_USE_COMPLETION_EXACT_PENDING_REQUIRED')
        source_before=(source_owner._bound,source_owner.sequence,pending['request'],
            inventory._freeze_static(pending['request']),inventory._freeze_static(pending['native']),
            pending['result_identity'],pending['started'],pending.get('inventory_refs'))
        now=source_owner._clock()
        need(type(pending.get('started')) is int and now-pending['started']<commands.WAIT_NS,
             'ITEM_USE_COMPLETION_ORIGINAL_DEADLINE')
        current=source_owner._use_item_current()
        row=current[1];request=pending['request']
        refs=pending.get('inventory_refs')
        actual=(self.broker._inventory_service,self.broker._inventory_store,self.broker._inventory_frame,
                self.broker._inventory_selection_binding,self.broker._inventory_delivery_authority,
                self.broker._inventory_current_frame)
        need(type(refs) is tuple and len(refs)==6 and all(refs[n] is actual[n] for n in range(6))
             and current[0].broker is self.broker and current[0].writer is writer
             and row['writer'] is writer and row['operation_lock'].locked()
             and request.get('seq')==source_owner.sequence and request.get('player_uid')==current[3].uid
             and request.get('map_id')==current[3].map_id and request.get('item_identifier')==item_identifier,
             'ITEM_USE_COMPLETION_CURRENT_SOURCE_REQUIRED')
        # Read the actual original result file again; no cached native bool is authority.
        source_owner._use_item_result(current)
        policy=self.broker.policy
        offset=pending['event_start']-(policy.events-len(policy.log))
        need(0<=offset<=len(policy.log),'ITEM_USE_COMPLETION_RX_PROOF_DROPPED')
        received=[e for e in list(policy.log)[offset:] if e[0]=='rx'
                  and e[1]==row['peer']['endpoint_port'] and e[2]==0x0960]
        need(len(received)==1 and row['policy_row'].received>pending['received_base'],
             'ITEM_USE_COMPLETION_EXACT_RECEIVED_REQUIRED')
        active_intent=self._current
        completed=None if active_intent is not None else completion_methods[4][1](self,writer,item_identifier,accepted_ordinal)
        intent=active_intent if completed is None else completed.intent
        need(type(intent) is _Intent and intent.writer is writer and intent.accepted_ordinal==accepted_ordinal
             and self.accepted_count==accepted_ordinal
             and self.last_invalidation==(None if completed is None else 'ITEM_USE_WRITER_RELEASED')
             and self.last_outcome.kind is OutcomeKind.ACCEPTED
             and self.last_outcome.accepted_ordinal==accepted_ordinal
             and (completed is not None or self.matches_received(writer,item_identifier,accepted_ordinal) is True),
             'ITEM_USE_COMPLETION_SAME_ACCEPTED_INTENT_REQUIRED')
        projection=self._project(writer,item_identifier=item_identifier)
        if completed is not None:
            need(type(self.policy) is str and self.policy==POLICY
                 and type(item_identifier) is int and 0<=item_identifier<=U64_MAX
                 and type(accepted_ordinal) is int and 1<=accepted_ordinal<=U64_MAX
                 and projection[2] is completed.intent.frame
                 and projection[4] is completed.intent.selection_binding
                 and projection[7] is completed.intent.adoption
                 and projection[6].identifier==item_identifier,
                 'ITEM_USE_MANUAL_COMPLETION_RECEIPT_READ_AUTHORITY_REQUIRED')
            _raw0_source_ready()

        effect_context=completion_methods[3][1](self,writer,item_identifier,intent,row=row)
        effect=getattr(self.broker,'_item_equipment_effect',None)
        if effect_context is not None:
            consumed,receipt,op,batch,life=effect_context[1:6]
        source_generation=self.broker._inventory_generation
        source_provider=getattr(self.broker,'_canonical_provider',None)
        source_scope=None if source_provider is None else source_provider._scope
        final_now=source_owner._clock()
        # No caller/schema/clock callback follows this bounded preimage read.
        if effect_context is not None:
            eq_path,eq_raw,eq_identity,eq_policy=effect_context[-4:]
            with eq_path.open('rb') as stream:final_eq_raw=stream.read(effect.store.MAX_BYTES+1)
            need(final_eq_raw==eq_raw,'ITEM_USE_COMPLETION_FINAL_EQUIPMENT_PREIMAGE_CHANGED')
            need(all(x is y for x,y in zip(eq_identity,(effect.store.path,effect.store._path,
                 effect.store.profile,effect.store._profile,effect.store._inventory_path,effect.store.inventory_store)))
                 and eq_policy==(effect.policy,effect._collection_policy,effect._form_policy,effect._switch_policy,
                     effect._limit_weapon_switching,effect._barrier_policy)
                 and effect._selection is life and life['state'] is op['state']
                 and effect._operation is op and effect._consumed is consumed and effect._last is receipt
                 and inventory._freeze_static(receipt)==effect_context[6],
                 'ITEM_USE_COMPLETION_FINAL_EQUIPMENT_OWNER_CHANGED')

        need(type(final_now) is int and final_now-pending['started']<commands.WAIT_NS
             and source_owner.pending is pending and source_owner._busy is True
             and source_owner._thread==threading.get_ident() and source_owner._bound is source_before[0]
             and source_owner.sequence==source_before[1] and pending['request'] is source_before[2]
             and inventory._freeze_static(pending['request'])==source_before[3]
             and inventory._freeze_static(pending['native'])==source_before[4]
             and pending['result_identity']==source_before[5] and pending['started']==source_before[6]
             and pending.get('inventory_refs') is source_before[7]
             and self._current is active_intent and self._backend_completion is completed
             and source_owner.state.get('status')!='UNKNOWN'
             and not self.closed and not self._released and not self.broker._closing
             and self.broker._inventory_generation is source_generation
             and getattr(self.broker,'_canonical_provider',None) is source_provider
             and (source_provider is None or source_provider._scope is source_scope)
             and all(refs[n] is (self.broker._inventory_service,self.broker._inventory_store,
                 self.broker._inventory_frame,self.broker._inventory_selection_binding,
                 self.broker._inventory_delivery_authority,self.broker._inventory_current_frame)[n] for n in range(6)),
             'ITEM_USE_COMPLETION_FINAL_SOURCE_CHANGED_OR_EXPIRED')
        # The last callback cannot replace any completion callee.
        for name,function in completion_methods:
            _original(self,name,function)
        task=asyncio.current_task()
        need(task is not None and not task.cancelling(),'ITEM_USE_COMPLETION_CURRENT_TASK_REQUIRED')
        return (pending,request,pending['native'],pending['result_identity'],intent,projection,
                source_owner._bound,task,effect_context,source_owner.sequence,pending['started'],completed)

    async def complete_received(self, writer, item_identifier, accepted_ordinal, *, source_owner):
        """원 manual 결과/received intent/Eq drain 소비 뒤에만 intent lifetime을 종료한다."""
        if self._book_native_completion is not None:
            complete=_original(self,'_complete_book_native_received',ItemUseSession._complete_book_native_received)
            return await complete(writer,item_identifier,accepted_ordinal,source_owner)
        methods=(('_completion_context',ItemUseSession._completion_context),
                 ('_same',ItemUseSession._same),('release',ItemUseSession.release),
                 ('_effect_completion_current',ItemUseSession._effect_completion_current),
                 ('_backend_completion_current',ItemUseSession._backend_completion_current))
        for name,function in methods:_original(self,name,function)
        context,same,release=(part[1] for part in methods[:3])
        async with self._lock:
            self._inflight_writer,self._released=writer,False
            try:
                for name,function in methods:_original(self,name,function)
                before=context(self,writer,item_identifier,accepted_ordinal,source_owner,completion_methods=methods)
                await self.broker._checkpoint(writer,before[5][0])
                for name,function in methods:_original(self,name,function)
                after=context(self,writer,item_identifier,accepted_ordinal,source_owner,completion_methods=methods)
                need(all(before[n] is after[n] for n in (0,1,4,6,7))
                     and before[2:4]==after[2:4] and before[8:]==after[8:],
                     'ITEM_USE_COMPLETION_SOURCE_CHANGED')
                for name,function in methods:_original(self,name,function)
                same(self,before[5],after[5])
                # The actual normal caller has consumed every required result.
                # This is lifetime cleanup, never Native/ACK/effect authority.
                if before[-1] is None:release(self,writer)
                need(self._current is None and self.accepted_count==accepted_ordinal,
                     'ITEM_USE_COMPLETION_RELEASE_POSTSTATE')
                return True
            finally:
                self._inflight_writer,self._released=None,False

    def release(self, writer):
        source=self._native_pending_read
        if source is not None and source.writer is writer:
            self.retire_book_native()
        if self._inflight_writer is writer:
            self._released = True
        if self._current is not None and self._current.writer is writer:
            self._clear('ITEM_USE_WRITER_RELEASED')

    def close(self):
        self.closed = True
        self._clear('ITEM_USE_SESSION_CLOSED')
        self._outcome(OutcomeKind.CLOSED, 'ITEM_USE_SESSION_CLOSED')

    def metadata(self):
        # Recent history only. Calling metadata never grants current authority,
        # reads Store/native data, exposes request values or requires a row lock.
        outcome = self.last_outcome
        enabled = type(self.policy) is str and self.policy == POLICY
        return dict(enabled=enabled, policy=POLICY if enabled else None, closed=self.closed,
            book_native_preparation=(None if self._book_native_preparation is None
                                     else dict(self._book_native_preparation)),
            accepted_count=self.accepted_count, intent_recorded=self._current is not None,
            last_invalidation=self.last_invalidation,
            last_outcome=None if outcome is None else dict(kind=outcome.kind.value,
                reason=outcome.reason, accepted_ordinal=outcome.accepted_ordinal),
            proof_scope='VALIDATED_ITEM_USE_INTENT_ONLY',
            response_policy='NO_ITEM_USE_REPLY_OR_EFFECT')
