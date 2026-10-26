"""Explicit one-roundtrip UI owner; Native return never grants backend custody.

Only the original entry/popup adapters publish Native requests. The backend
continues to accept its own authenticated CS4E3F/CS4E3E independently.
"""
from types import MethodType
import threading
import time

from tools.local_original_session import item_custody, item_transfer_session, inventory_observe, inventory, observe
from tools.local_original_session.broker import PersistentBroker, _InventoryGeneration
from tools.local_original_session.manual_move_commands import ManualMoveCommands, WAIT_NS
from tools.local_original_session.item_quantity_popup import PopupHost, CAPABILITY as POPUP_CAPABILITY
from tools.local_original_session.item_transfer_entry import EntryHost, CAPABILITY as ENTRY_CAPABILITY

PROFILE = item_transfer_session.PROFILE
_CURRENT = ManualMoveCommands._current
_TERMINAL = ManualMoveCommands._terminal
_CLOCK = ManualMoveCommands._clock
_GENERATION = PersistentBroker.inventory_selection_current
_PREPARE = PersistentBroker.prepare_item_equipment
_CONTEXT = item_transfer_session.ItemTransferSession.context_locked
_RETURN_SAMPLE = inventory_observe.InventoryObserver.sample_transfer_return
_DROP_SAMPLE = inventory_observe.InventoryObserver.sample_transfer_drop
_RETURN_OBSERVER_SHA = '86ef4acf4ac49644fd9d260e62d657e193b1bed65b6d0c76b6426f7a0795b747'


def need(value, code):
    if not value:
        raise ValueError(code)


def configured(factory):
    """Exact new mode; none of the old saved-B/Swap flags are aliases."""
    from tools.local_original_session import launcher, item_use_session, item_equipment_effect
    need(type(factory) is launcher.ProductFeatureFactory, 'TRANSFER_UI_EXACT_FACTORY_REQUIRED')
    c, spec, context = factory.config, factory._transfer_ui_spec, factory._transfer_ui_context
    item_transfer_session.configuration(c)
    return (factory.item_transfer_ui is factory._item_transfer_ui_bound is True
        and factory.product == context[0] == PROFILE and c is context[1] and context[2] == 'manual'
        and launcher.PRODUCTS.get(PROFILE) is spec and spec.get('item_transfer_ui') is True
        and spec.get('item_quantity_popup') == POPUP_CAPABILITY
        and spec.get('item_transfer_entry') == ENTRY_CAPABILITY
        and type(launcher.ITEM_TRANSFER_UI_DLL_SHA) is str
        and spec['bridges'].get('own-login-bridge-dg49.dll') == launcher.ITEM_TRANSFER_UI_DLL_SHA
        and factory.swap_saved_b_tail is factory._swap_saved_b_tail_bound is False
        and factory.zero_use_reselect is factory._zero_use_reselect_bound is False
        and not factory.swap_reselect and not factory.reselect_equipment_restore
        and factory.inventory and factory.item_use_enabled and factory.allow_use_item
        and factory.use_item_current_entry and not factory.use_item_already_open
        and factory.allow_inventory_ui_open and not factory.allow_equipment_ui_observe
        and factory.allow_source_restart and factory.allow_source_reselect
        and not factory.normal_open_use_current_ui and not factory.mark_on_current_indicator
        and not factory.allow_selected_slot_lookup_role and not factory.manual and not factory.allow_attack
        and not factory.allow_attack_replacement and not factory.allow_inventory_update
        and c.item_use_policy == item_use_session.POLICY
        and c.item_equipment_policy == item_equipment_effect.POLICY
        and all(getattr(c, name) is None for name in
            ('interval_ns','motion_policy','goal_policy','goal','attack_policy','attack_feedback',
             'attack_hp_provider','npc_death_policy','npc_remove_policy','npc_respawn_policy','npc_respawn_spawn',
             'hp_status_policy','hp_status_input')))


class ItemTransferUI:
    def __init__(self, runtime, broker):
        from tools.local_original_session.launcher import ProductFeatures, ManualMoveRequests
        need(type(runtime) is ProductFeatures and type(runtime.manual) is ManualMoveRequests
             and type(broker) is PersistentBroker and runtime.manual.inventory_broker is broker,
             'TRANSFER_UI_ACTUAL_RUNTIME_BROKER_REQUIRED')
        self.runtime, self.broker, self.manual = runtime, broker, runtime.manual
        self.consumer = self.manual.consumer
        self._clock_provider = self.consumer.clock_ns
        need(type(self.consumer) is ManualMoveCommands and self.manual.allow_use_item is False
             and self.consumer.allow_use_item is True and self.consumer.use_item_current_entry is True,
             'TRANSFER_UI_EXPLICIT_PREPARATION_CONSUMER_REQUIRED')
        self.entry = EntryHost(self.consumer, capability=ENTRY_CAPABILITY)
        self.popup = PopupHost(self.consumer, capability=POPUP_CAPABILITY)
        self._thread = threading.get_ident()
        self._refs = None
        self._post_ret_runtime = None
        self._claimed = self.started = self.closed = False
        self.phase = 'IDLE'
        self._phase_started = None
        self._prepare_use = False
        self._use_before = self._use_sequence = None
        self._use_pending = self._use_request = None
        self._accepted = None
        self._anchor = self._other = self._quantity = None
        self._initial_snapshot = self._equipment = None
        self._preparation_clock = self._preparation_backend_progress = None
        self._initial_prepare_attempted = False
        self._return_observer = self._return_binding = self._return_observation = None
        self._return_started_ns = self._return_nonce = self._return_sequence = None
        self._drop_observer = self._drop_binding = self._drop_observation = None
        self._drop_started_ns = self._drop_nonce = self._drop_sequence = None
        self._diagnostic_site = "CONSTRUCTOR"
        self._context_origin = None
        self._stage_clock = self._backend_context = None
        self.initial_receipt = None
        self.last = dict(status='IDLE', phase=self.phase, backend_effect='UNKNOWN', automatic_retry=False)

    def request(self, *, prepare_use=False):
        need(type(prepare_use) is bool, 'TRANSFER_UI_EXACT_PREPARATION_BOOL_REQUIRED')
        if self._claimed or self.closed:
            return False
        need(threading.get_ident() == self._thread and not self.runtime._closed,
             'TRANSFER_UI_CURRENT_THREAD_RUNTIME_REQUIRED')
        self._claimed = self.started = True
        self._prepare_use = prepare_use
        self._phase('INITIAL')
        return True

    def _phase(self, value, *, original_started=None):
        self.phase = value
        self._phase_started = self.consumer._clock() if original_started is None else original_started

    def _original(self):
        need(not self.closed and not self.runtime._closed and threading.get_ident() == self._thread
             and self.runtime.manual is self.manual and self.manual.consumer is self.consumer
             and self.manual.inventory_broker is self.broker and self.runtime.item_transfer_ui is self,
             'TRANSFER_UI_RUNTIME_LIFETIME_CHANGED')
        method = self.consumer._current
        need(type(self.consumer) is ManualMoveCommands and type(method) is MethodType
             and method.__self__ is self.consumer and method.__func__ is _CURRENT
             and type(self.consumer)._current is _CURRENT,
             'TRANSFER_UI_ORIGINAL_CONSUMER_REQUIRED')
        clock = self.consumer._clock
        need(type(clock) is MethodType and clock.__self__ is self.consumer and clock.__func__ is _CLOCK
             and self.consumer.clock_ns is self._clock_provider, 'TRANSFER_UI_ORIGINAL_CLOCK_CHANGED')
        # 10초는 Native 결과 대기 예산이며 완료 후 관측의 게임 규약이 아니다.
        post_ret = self._quantity == 1 and self.phase in (
            'DROP_BACKEND', 'DROP_CLIENT', 'RETURN_BACKEND', 'RETURN_CLIENT', 'DONE')
        if post_ret:
            from tools.local_original_session.item_transfer_runner import Runtime, POST_RET_CURRENT_METHOD
            runtime = self._post_ret_runtime
            method = getattr(runtime, 'require_post_ret_current', None)
            need(type(runtime) is Runtime and type(method) is MethodType
                 and method.__self__ is runtime and method.__func__ is POST_RET_CURRENT_METHOD
                 and Runtime.require_post_ret_current is POST_RET_CURRENT_METHOD,
                 'TRANSFER_UI_POST_RET_ORIGINAL_RUNTIME_REQUIRED')
            method(self)
        now = self.consumer._clock()  # 원 clock/단조 검사는 pending과 관측 모두 보존한다.
        if post_ret:
            current_method = runtime.require_post_ret_current
            need(runtime is self._post_ret_runtime and type(current_method) is MethodType
                 and current_method.__self__ is runtime and current_method.__func__ is POST_RET_CURRENT_METHOD
                 and Runtime.require_post_ret_current is POST_RET_CURRENT_METHOD,
                 'TRANSFER_UI_POST_RET_ORIGINAL_RUNTIME_REQUIRED')
            current_method(self)  # clock 호출 사이 취소/수명/메서드 교체도 승인하지 않는다.
        age = now - self._phase_started
        allowed = 0 <= age < WAIT_NS
        self._stage_clock = dict(caller=self._diagnostic_site, context_origin=self._context_origin, phase=self.phase,
            original_started_ns=self._phase_started, checked_ns=now, elapsed_ns=age,
            wait_ns=WAIT_NS, within_original_window=allowed,
            scope='LAST_ORIGINAL_CLOCK_CHECK_ONLY',
            budget_scope='POST_RET_LIFETIME_AND_FRESH_CONTEXT' if post_ret else 'NATIVE_OR_PREPARATION_TOOL_WAIT')
        if self.phase in ('PREPARE_USE', 'PREPARE_USE_BACKEND'):
            self._preparation_clock = dict(phase=self.phase, original_started_ns=self._phase_started,
                checked_ns=now, elapsed_ns=age, wait_ns=WAIT_NS, within_original_window=allowed)
        need(0 <= age and (post_ret or allowed), 'TRANSFER_UI_ORIGINAL_STAGE_DEADLINE')

    async def _context(self):
        self._context_origin = self._diagnostic_site
        self._diagnostic_site = "CONTEXT_BEFORE_ROW_LOCK"
        self._original()
        current = _CURRENT(self.consumer)
        writer, row = current[0].writer, current[1]
        need(current[0].broker is self.broker and type(self.broker).inventory_selection_current is _GENERATION,
             'TRANSFER_UI_SAME_ACTUAL_BROKER_REQUIRED')
        generation = _GENERATION(self.broker, writer)
        need(type(generation) is _InventoryGeneration and generation.phase == 'ACTIVE'
             and generation.writer is writer and generation.row is row,
             'TRANSFER_UI_CURRENT_GENERATION_REQUIRED')
        session = generation.transfer_session
        method = session.context_locked
        need(type(session) is item_transfer_session.ItemTransferSession and type(method) is MethodType
             and method.__self__ is session and method.__func__ is _CONTEXT,
             'TRANSFER_UI_ORIGINAL_TRANSFER_SESSION_REQUIRED')
        self._diagnostic_site = 'CONTEXT_ROW_LOCK_WAIT'
        async with row['operation_lock']:
            self._diagnostic_site = 'CONTEXT_ROW_LOCK_ACQUIRED'
            context = _CONTEXT(session, writer)
        refs = (self.broker, writer, row, generation, generation.selected,
                context.selection_binding, context.initial_frame, context.delivery,
                context.store, session, context.position)
        if self._refs is None:
            self._refs = refs
        else:
            need(all(a is b for a, b in zip(refs, self._refs)),
                 'TRANSFER_UI_GENERATION_SELECTION_OR_POSITION_CHANGED')
        count = context.item_use_session.accepted_count
        if self._accepted is not None:
            if self.phase in ('PREPARE_USE', 'PREPARE_USE_BACKEND'):
                need(type(count) is int and self._use_before <= count <= self._use_before + 1,
                     'TRANSFER_UI_UNEXPECTED_PREPARATION_COUNTER')
            else:
                need(type(count) is int and count == self._accepted,
                     'TRANSFER_UI_UNEXPECTED_RECEIVED_USE')
        self._backend_context = dict(scope='LAST_VALIDATED_CONTEXT_ONLY_NOT_CURRENT_AT_FAILURE',
            ui_phase=self.phase, snapshot_phase=context.snapshot.phase,
            snapshot_owner=context.snapshot.owner, snapshot_revision=context.snapshot.revision,
            session_phase=session.phase, membership_phase=context.membership.phase,
            pending=session.pending is not None, send_index=session._send_index,
            wire_phase=session._wire_phase)
        self._diagnostic_site = 'CONTEXT_VALIDATED'
        return context

    def _diagnostic_report(self):
        return dict(last_clock=None if self._stage_clock is None else dict(self._stage_clock),
                    last_context=None if self._backend_context is None else dict(self._backend_context),
                    last_caller=self._diagnostic_site,
                    context_origin=self._context_origin,
                    scope='CACHED_DIAGNOSTIC_ONLY_NO_COMPLETION_AUTHORITY')

    async def _prepare_initial(self, context):
        """Backend sync only. No raw PC equipment observer/proof is minted."""
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        from tools.local_original_session.equipment_store import EquipmentStore
        effect = self.broker._item_equipment_effect
        need(not self._initial_prepare_attempted and type(effect) is ItemEquipmentEffect
             and effect.broker is self.broker and effect.first_enable is False
             and type(effect.store) is EquipmentStore and effect.store.inventory_store is context.store
             and effect.prepare_locked.__func__ is ItemEquipmentEffect.prepare_locked
             and type(self.broker).prepare_item_equipment is _PREPARE,
             'TRANSFER_UI_ORIGINAL_INITIAL_EFFECT_REQUIRED')
        self._initial_prepare_attempted = True  # Spend before the original await.
        receipt = await _PREPARE(self.broker, context.writer, policy=effect.policy, first_enable=effect.first_enable)
        after = await self._context()
        need(self.broker._item_equipment_effect is effect and after.snapshot == context.snapshot
             and after.equipment == context.equipment and after.item_use_session.accepted_count == 0
             and type(receipt) is dict and receipt.get('operation') == 'INITIAL_SYNC'
             and receipt.get('accepted_ordinal') is None and receipt.get('status') == 'SYNCHRONIZED'
             and receipt.get('phase') == 'DRAINED'
             and receipt.get('initialization_source') == 'RESTORED_EQUIPMENT_SIDECAR'
             and receipt.get('persist_attempted') is receipt.get('persisted') is False
             and receipt.get('before_weapon_uid') == receipt.get('after_weapon_uid') == after.equipment.weapon_uid
             and receipt.get('before_revision') == receipt.get('after_revision') == after.equipment.revision
             and all(receipt.get(k) is True for k in
                     ('writer_bound','generation_bound','write_attempted','drain_returned','post_owner_verified')),
             'TRANSFER_UI_ACTUAL_RESTORED_INITIAL_SYNC_REQUIRED')
        count, records = receipt.get('notification_count'), receipt.get('notification_records')
        need(type(count) is int and 1 <= count <= 2 and receipt.get('notifications_drained') == count
             and type(records) is list and len(records) == count and all(type(row) is dict
                 and row.get('status') == 'DRAINED' and row.get('phase') == 'DRAINED'
                 and all(row.get(k) is True for k in ('write_attempted','drain_returned','post_owner_verified'))
                 for row in records), 'TRANSFER_UI_INITIAL_NOTIFICATION_DRAINS_REQUIRED')
        self.initial_receipt = receipt  # Actual history/report only, not an authority provider.
        return after

    def _preparation_backend(self, context):
        """Consume cached real effect progress; never prepare/send/replay it."""
        target, count = self._use_before + 1, context.item_use_session.accepted_count
        need(type(count) is int and self._use_before <= count <= target,
             'TRANSFER_UI_UNEXPECTED_PREPARATION_COUNTER')
        receipt = self.broker.item_equipment_observation(context.writer, accepted_ordinal=target)
        # Output only: existing returned receipt and current Python identities.
        # No Store/native query, clock call, replay or completion authority.
        effect, generation = self.broker._item_equipment_effect, self.broker._inventory_generation
        use, service = generation.item_use_session, generation.service
        fields = ('status','reason','phase','accepted_ordinal','operation','item_uid',
                  'before_weapon_uid','after_weapon_uid','writer_bound','generation_bound',
                  'persisted','write_attempted','drain_returned','post_owner_verified')
        progress = dict(target=target, count=count, before_count=self._use_before,
            classification='RECEIPT_CHECK', receipt_type=type(receipt).__name__,
            receipt={key: receipt.get(key) for key in fields} if type(receipt) is dict else None,
            effect_writer_matches=effect._writer is context.writer,
            effect_generation_matches=effect._generation is generation,
            generation_phase=generation.phase, use_session_present=use is not None,
            use_session_closed=None if use is None else use.closed,
            use_session_matches_context=use is context.item_use_session,
            service_present=service is not None, service_closed=None if service is None else service._closed,
            effect_last_ordinal=effect._last.get('accepted_ordinal'),
            clock_basis='LAST_EXISTING_ORIGINAL_CHECK_BEFORE_POSSIBLE_CONTEXT_LOCK_WAIT',
            original_check=None if self._preparation_clock is None else dict(self._preparation_clock))
        self._preparation_backend_progress = progress
        need(type(receipt) is dict and receipt.get('status') not in ('UNKNOWN', 'BLOCKED'),
             'TRANSFER_UI_PREPARATION_EFFECT_TERMINAL')
        if count == self._use_before or receipt.get('status') in ('NO_MATCH', 'NOT_PREPARED'):
            progress['classification'] = ('COUNT_NOT_ACCEPTED' if count == self._use_before
                                          else 'RECEIPT_' + receipt['status'])
            return False
        progress['classification'] = 'EFFECT_IDENTITY_CHECK'
        need(type(receipt.get('accepted_ordinal')) is int and receipt['accepted_ordinal'] == target
             and receipt.get('operation') == 'ITEM_USE_EFFECT' and receipt.get('item_uid') == self._other,
             'TRANSFER_UI_PREPARATION_EFFECT_IDENTITY_CHANGED')
        if receipt.get('status') != 'COMMITTED':
            progress['classification'] = 'EFFECT_IN_PROGRESS'
            return False
        progress['classification'] = 'UNEQUIP_CHECK'
        need(receipt.get('before_weapon_uid') == self._other and receipt.get('after_weapon_uid') == 0,
             'TRANSFER_UI_ACTUAL_UNEQUIP_PREPARATION_REQUIRED')
        if not all(receipt.get(k) is True for k in
                   ('writer_bound','generation_bound','persisted','write_attempted','drain_returned','post_owner_verified')):
            progress['classification'] = 'EFFECT_FLAGS_INCOMPLETE'
            return False
        progress['classification'] = 'EFFECT_DRAIN_CHECK'
        need(receipt.get('phase') == 'DRAINED' and context.equipment.weapon_uid == 0,
             'TRANSFER_UI_PREPARATION_EFFECT_DRAIN_REQUIRED')
        self._accepted, self._equipment = target, context.equipment
        progress['classification'] = 'COMMITTED_CONSUMED'
        return True

    def _capture_preparation_publication(self, value):
        """Result projection only; current/session authority stays in original M."""
        pending = self._use_pending
        committed = value.get('status') == 'COMMITTED'
        need(type(pending) is dict and pending.get('kind') == 'UseItem'
             and self.consumer.pending is (None if committed else pending),
             'TRANSFER_UI_PREPARATION_PENDING_CHANGED')
        request = pending.get('request')
        if request is None:
            need(value.get('status') == 'PENDING' and pending.get('phase') == 'ADMISSION'
                 and pending.get('native_attempted') is False
                 and self._use_request is self._use_sequence is None,
                 'TRANSFER_UI_PREPARATION_PUBLICATION_MISSING')
            return
        initial = pending['initial']
        need(type(request) is dict and pending.get('phase') == 'NATIVE_WAIT'
             and pending.get('native_attempted') is True
             and request.get('schema') == 'own-use-item-current-entry-request-v1'
             and request.get('command') == 'UseItemCurrentEntry'
             and type(request.get('seq')) is int and request['seq'] > 0
             and request['seq'] == self.consumer.sequence == self.consumer._action_sequence
             and type(request.get('item_identifier')) is int and request['item_identifier'] == self._other
             and type(request.get('player_uid')) is int and request['player_uid'] == initial.uid
             and type(request.get('map_id')) is int and request['map_id'] == initial.map_id,
             'TRANSFER_UI_PREPARATION_ORIGINAL_PUBLICATION_CHANGED')
        if self._use_request is None:
            need(self._use_sequence is None and value.get('status') == 'PENDING',
                 'TRANSFER_UI_PREPARATION_PUBLICATION_NOT_CAPTURED')
            self._use_request, self._use_sequence = request, request['seq']
        else:
            need(request is self._use_request and request['seq'] == self._use_sequence,
                 'TRANSFER_UI_PREPARATION_PUBLICATION_REPLACED')

    async def _poll_manual(self, monitor, *, preparation=False):
        # Keep the launcher's existing serial typed-query slot accounting when
        # this explicit owner temporarily bypasses ordinary public ingress.
        if monitor is not None and time.monotonic() < monitor.next_memory:
            return None
        before = self.manual.last_sample_monotonic_ns
        try:
            return (await self.consumer.poll_async() if preparation
                    else await self.manual.poll_async(monitor=monitor))
        finally:
            sampled = self.manual.last_sample_monotonic_ns
            if monitor is not None and sampled is not None and sampled != before:
                monitor.next_memory = max(monitor.next_memory, sampled / 1e9 + .5)

    @staticmethod
    def _returned(value, scope):
        need(type(value) is dict and value.get('status') == 'RETURNED'
             and value.get('invoked') is True and type(value.get('reason')) is int
             and value['reason'] == 0 and value.get('proof_scope') == scope
             and value.get('backend_effect') == 'UNKNOWN', 'TRANSFER_UI_NATIVE_ENTRY_UNKNOWN')

    def _preparation_report(self):
        clock, backend = self._preparation_clock, self._preparation_backend_progress
        result = dict(latest_original=None if clock is None else dict(clock),
                      last_backend=None if backend is None else dict(backend))
        if backend is not None and type(backend.get('receipt')) is dict:
            result['last_backend']['receipt'] = dict(backend['receipt'])
        if backend is not None and type(backend.get('original_check')) is dict:
            result['last_backend']['original_check'] = dict(backend['original_check'])
        return result

    async def _begin_drop_client(self, context):
        self._diagnostic_site = "BEGIN_DROP_CLIENT"
        need(self._drop_observer is None and self._drop_binding is None,
             'TRANSFER_UI_RETURN_OBSERVATION_ONCE_REQUIRED')
        after=await self._context()
        item_transfer_session.ItemTransferSession._same(context,after)
        need(after.snapshot.phase=='DROPPED' and after.snapshot.owner=='GROUND'
             and after.session.phase=='DROPPED' and after.session.pending is None
             and after.membership.phase=='DRAINED', 'TRANSFER_UI_ACTUAL_RETURN_DRAIN_REQUIRED')
        self._drop_binding=after
        self._drop_started_ns=time.monotonic_ns()
        self._drop_nonce=object();self._drop_sequence=self.consumer.sequence
        self._drop_observer=inventory_observe.InventoryObserver(self.broker,self.consumer.reader,
            collection_policy=inventory.COLLECTION_POLICY)

    async def _poll_drop_client(self, context, monitor):
        self._original()
        observer=self._drop_observer
        manual=self.manual;cls=manual._inventory_observer_type;engine=manual._inventory_observer_sample
        need(type(observer) is inventory_observe.InventoryObserver
             and cls is inventory_observe.InventoryObserver and type(observer) is cls
             and cls.sample is engine and observer.sample.__func__ is engine
             and observer.sample.__self__ is observer
             and engine.__globals__.get('InventoryObserver') is cls
             and engine.__qualname__=='InventoryObserver.sample'
             and observe.Path(engine.__code__.co_filename).resolve()==observe.Path(inventory_observe.__file__).resolve()
             and observer._authority.reader is self.consumer.reader
             and observer._authority.broker is self.broker
             and observer.sample_transfer_drop.__func__ is _DROP_SAMPLE
             and inventory_observe.InventoryObserver.sample_transfer_drop is _DROP_SAMPLE
             and observe.digest(observe.ordinary(observe.Path(inventory_observe.__file__))) == _RETURN_OBSERVER_SHA,
             'TRANSFER_UI_ORIGINAL_RETURN_OBSERVER_REQUIRED')
        need(self.consumer.sequence==self._drop_sequence and self._drop_nonce is not None,
             'TRANSFER_UI_RETURN_REQUEST_CHANGED')
        item_transfer_session.ItemTransferSession._same(self._drop_binding,context)
        now=time.monotonic_ns()
        sampled=[value for value in (observer.last_sample_monotonic_ns,self.manual.last_sample_monotonic_ns) if value is not None]
        last=max(sampled) if sampled else None
        if (monitor is not None and time.monotonic()<monitor.next_memory
                or last is not None and now-last<inventory.MIN_INTERVAL_NS):return False
        nonce=self._drop_nonce;sequence=self._drop_sequence;before=observer.last_result
        try:
            result=await _DROP_SAMPLE(observer,context.writer,now_ns=now,session=context.session)
        finally:
            queried=observer.last_sample_monotonic_ns
            if type(queried) is int:
                previous=manual._inventory_previous_sample_ns
                manual._inventory_previous_sample_ns=max(n for n in (previous,queried) if n is not None)
                if monitor is not None:monitor.next_memory=max(monitor.next_memory,queried/1e9+.5)
        after=await self._context()
        item_transfer_session.ItemTransferSession._same(self._drop_binding,after)
        need(self._drop_observer is observer and self._drop_nonce is nonce
             and self.consumer.sequence==sequence==self._drop_sequence
             and self.manual is manual and manual._inventory_observer_type is cls
             and manual._inventory_observer_sample is engine and cls.sample is engine
             and observer.sample.__func__ is engine and observer.sample.__self__ is observer
             and observer.sample_transfer_drop.__func__ is _DROP_SAMPLE
             and inventory_observe.InventoryObserver.sample_transfer_drop is _DROP_SAMPLE
             and result is observer.last_result and result is not before,
             'TRANSFER_UI_RETURN_QUERY_REPLACED')
        queried=observer.last_sample_monotonic_ns
        if monitor is not None and queried is not None:
            monitor.next_memory=max(monitor.next_memory,queried/1e9+.5)
        need(type(queried) is int and self._drop_started_ns<=now<=queried
             and result.get('query_started_monotonic_ns')==queried,
             'TRANSFER_UI_FRESH_RETURN_QUERY_REQUIRED')
        if (result.get('status')=='PENDING' and result.get('reason')=='INVENTORY_OBSERVE_DROP_ROWS_PENDING'
                and result.get('source_contract_valid') is True and result.get('stable_double_read') is True
                and result.get('source_owner_revalidated') is True and result.get('read_consistency')=='STRICT_STABLE'):
            return False
        if (result.get('status')=='UNKNOWN' and result.get('reason')=='EDGE_TYPED_READ_CHANGED'
                and result.get('read_consistency') in ('RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE','RECHECKED_SHARED_COUNT_FINAL_READBACK','RECHECKED_SHARED_COUNT_BOTH')
                and result.get('source_owner_revalidated') is True
                and result.get('source_contract_valid') is False and result.get('stable_double_read') is False
                and result.get('rows')==[] and result.get('entry_count') is None
                and type(result.get('typed_bytes_requested')) is int and 0<result['typed_bytes_requested']<=inventory_observe.BYTE_LIMIT):
            return False
        need(result.get('status')=='OBSERVED' and result.get('reason') is None
             and result.get('source_contract_valid') is True and result.get('stable_double_read') is True
             and result.get('source_owner_revalidated') is True and result.get('read_consistency')=='STRICT_STABLE'
             and type(queried) is int and self._drop_started_ns<=now<=queried
             and result.get('query_started_monotonic_ns')==queried
             and result.get('selected_uid')==context.position.uid and result.get('map_id')==context.position.map_id,
             'TRANSFER_UI_FRESH_RETURN_QUERY_REQUIRED')
        expected=[inventory_observe.InventoryObserver._row(item) for item in
            inventory.validate_collection_frame(context.current_frame,policy=inventory.COLLECTION_POLICY)]
        _,other=item_custody._members(context.snapshot.frame_ab)
        need(result.get('entry_count')==1 and result.get('rows')==expected
             and all(row['id_u64']!=other.identifier for row in result['rows']),
             'TRANSFER_UI_RETURN_CLIENT_B_SCALARS_REQUIRED')
        self._drop_observation=dict(query_started_monotonic_ns=queried,
            client_inventory='POST_DROP_A_ONLY_5_SCALARS_MATCHED',item_count=1,
            proof_scope='FRESH_POST_DROP_CLIENT_ROW_SCALARS_ONLY',render='UNKNOWN',ack='UNKNOWN')
        observer.close()
        return True

    async def _begin_return_client(self, context):
        self._diagnostic_site = "BEGIN_RETURN_CLIENT"
        need(self._return_observer is None and self._return_binding is None,
             'TRANSFER_UI_RETURN_OBSERVATION_ONCE_REQUIRED')
        after=await self._context()
        item_transfer_session.ItemTransferSession._same(context,after)
        need(after.snapshot.phase=='RETURNED' and after.snapshot.owner=='PLAYER'
             and after.session.phase=='RETURNED' and after.session.pending is None
             and after.membership.phase=='DRAINED', 'TRANSFER_UI_ACTUAL_RETURN_DRAIN_REQUIRED')
        self._return_binding=after
        self._return_started_ns=time.monotonic_ns()
        self._return_nonce=object();self._return_sequence=self.consumer.sequence
        self._return_observer=inventory_observe.InventoryObserver(self.broker,self.consumer.reader,
            collection_policy=inventory.COLLECTION_POLICY)

    async def _poll_return_client(self, context, monitor):
        self._original()
        observer=self._return_observer
        manual=self.manual;cls=manual._inventory_observer_type;engine=manual._inventory_observer_sample
        need(type(observer) is inventory_observe.InventoryObserver
             and cls is inventory_observe.InventoryObserver and type(observer) is cls
             and cls.sample is engine and observer.sample.__func__ is engine
             and observer.sample.__self__ is observer
             and engine.__globals__.get('InventoryObserver') is cls
             and engine.__qualname__=='InventoryObserver.sample'
             and observe.Path(engine.__code__.co_filename).resolve()==observe.Path(inventory_observe.__file__).resolve()
             and observer._authority.reader is self.consumer.reader
             and observer._authority.broker is self.broker
             and observer.sample_transfer_return.__func__ is _RETURN_SAMPLE
             and inventory_observe.InventoryObserver.sample_transfer_return is _RETURN_SAMPLE
             and observe.digest(observe.ordinary(observe.Path(inventory_observe.__file__))) == _RETURN_OBSERVER_SHA,
             'TRANSFER_UI_ORIGINAL_RETURN_OBSERVER_REQUIRED')
        need(self.consumer.sequence==self._return_sequence and self._return_nonce is not None,
             'TRANSFER_UI_RETURN_REQUEST_CHANGED')
        item_transfer_session.ItemTransferSession._same(self._return_binding,context)
        now=time.monotonic_ns()
        sampled=[value for value in (observer.last_sample_monotonic_ns,self.manual.last_sample_monotonic_ns) if value is not None]
        last=max(sampled) if sampled else None
        if (monitor is not None and time.monotonic()<monitor.next_memory
                or last is not None and now-last<inventory.MIN_INTERVAL_NS):return False
        nonce=self._return_nonce;sequence=self._return_sequence;before=observer.last_result
        try:
            result=await _RETURN_SAMPLE(observer,context.writer,now_ns=now,session=context.session)
        finally:
            queried=observer.last_sample_monotonic_ns
            if type(queried) is int:
                previous=manual._inventory_previous_sample_ns
                manual._inventory_previous_sample_ns=max(n for n in (previous,queried) if n is not None)
                if monitor is not None:monitor.next_memory=max(monitor.next_memory,queried/1e9+.5)
        after=await self._context()
        item_transfer_session.ItemTransferSession._same(self._return_binding,after)
        need(self._return_observer is observer and self._return_nonce is nonce
             and self.consumer.sequence==sequence==self._return_sequence
             and self.manual is manual and manual._inventory_observer_type is cls
             and manual._inventory_observer_sample is engine and cls.sample is engine
             and observer.sample.__func__ is engine and observer.sample.__self__ is observer
             and observer.sample_transfer_return.__func__ is _RETURN_SAMPLE
             and inventory_observe.InventoryObserver.sample_transfer_return is _RETURN_SAMPLE
             and result is observer.last_result and result is not before,
             'TRANSFER_UI_RETURN_QUERY_REPLACED')
        queried=observer.last_sample_monotonic_ns
        if monitor is not None and queried is not None:
            monitor.next_memory=max(monitor.next_memory,queried/1e9+.5)
        need(type(queried) is int and self._return_started_ns<=now<=queried
             and result.get('query_started_monotonic_ns')==queried,
             'TRANSFER_UI_FRESH_RETURN_QUERY_REQUIRED')
        if (result.get('status')=='PENDING' and result.get('reason')=='INVENTORY_OBSERVE_RETURN_ROWS_PENDING'
                and result.get('source_contract_valid') is True and result.get('stable_double_read') is True
                and result.get('source_owner_revalidated') is True and result.get('read_consistency')=='STRICT_STABLE'):
            return False
        if (result.get('status')=='UNKNOWN' and result.get('reason')=='EDGE_TYPED_READ_CHANGED'
                and result.get('read_consistency') in ('RECHECKED_SHARED_COUNT_INITIAL_DUPLICATE','RECHECKED_SHARED_COUNT_FINAL_READBACK','RECHECKED_SHARED_COUNT_BOTH')
                and result.get('source_owner_revalidated') is True
                and result.get('source_contract_valid') is False and result.get('stable_double_read') is False
                and result.get('rows')==[] and result.get('entry_count') is None
                and type(result.get('typed_bytes_requested')) is int and 0<result['typed_bytes_requested']<=inventory_observe.BYTE_LIMIT):
            return False
        need(result.get('status')=='OBSERVED' and result.get('reason') is None
             and result.get('source_contract_valid') is True and result.get('stable_double_read') is True
             and result.get('source_owner_revalidated') is True and result.get('read_consistency')=='STRICT_STABLE'
             and type(queried) is int and self._return_started_ns<=now<=queried
             and result.get('query_started_monotonic_ns')==queried
             and result.get('selected_uid')==context.position.uid and result.get('map_id')==context.position.map_id,
             'TRANSFER_UI_FRESH_RETURN_QUERY_REQUIRED')
        expected=[inventory_observe.InventoryObserver._row(item) for item in
            inventory.validate_collection_frame(context.current_frame,policy=inventory.COLLECTION_POLICY)]
        _,other=item_custody._members(context.snapshot.frame_ab)
        need(result.get('entry_count')==2 and result.get('rows')==expected
             and any(row['id_u64']==other.identifier and row['field28_i64']==dict(other.raw_fields)[4] for row in result['rows']),
             'TRANSFER_UI_RETURN_CLIENT_B_SCALARS_REQUIRED')
        self._return_observation=dict(query_started_monotonic_ns=queried,
            client_inventory='POST_RETURN_ROWS_5_SCALARS_MATCHED',item_count=2,
            proof_scope='FRESH_POST_RETURN_CLIENT_ROW_SCALARS_ONLY',render='UNKNOWN',ack='UNKNOWN')
        observer.close()
        return True

    def _report(self):
        self.last = dict(status='COMPLETE' if self.phase == 'DONE' else 'PENDING', phase=self.phase,
                         automatic_retry=False, backend_effect='ROUNDTRIP_DRAINED' if self.phase == 'DONE' else 'UNKNOWN',
                         proof_scope='SOURCE_BOUND_LOCAL_BACKEND_AND_NATIVE_RETURNS',
                         native_runtime='UNVERIFIED_BY_BACKEND', render='UNKNOWN')
        self.last['backend_progress'] = self._diagnostic_report()
        if self._return_observation is not None:self.last['client_return']=dict(self._return_observation)
        if self._drop_observation is not None:self.last['client_drop']=dict(self._drop_observation)
        if self._preparation_clock is not None or self._preparation_backend_progress is not None:
            self.last['preparation_progress'] = self._preparation_report()
        return dict(self.last)

    async def poll(self, monitor=None):
        # Q1의 이 두 전환만 외부 poll을 생략한다. 세 번째 pass는
        # DROP_CLIENT를 한 번 소비하고 Get/WAITING/PENDING에서 끝낸다.
        direct_edges = (('DROP_ENTRY_WAIT', 'DROP_BACKEND'),
                        ('DROP_BACKEND', 'DROP_CLIENT'))
        for direct_pass in range(3):
            entered = self.phase
            result = await self._poll_once(monitor)
            if self._quantity != 1 or (entered, self.phase) not in direct_edges:
                return result
        return result

    async def _poll_once(self, monitor=None):
        self._diagnostic_site = "POLL_ENTRY"
        self._context_origin = None
        if not self.started or self.phase == 'DONE':
            return dict(self.last)
        try:
            self._original()
            if self.phase == 'INITIAL':
                # Reuse the original actual Add/client confirmation, never seed
                # its tuple/result or invent a ready generation.
                await self._poll_manual(monitor)
                binding = self.manual.consumer.current()
                generation = None if binding is None else _GENERATION(self.broker, binding.writer)
                if generation is None or not self.runtime._equipment_initial_client_ready(
                        self.broker, binding.writer, generation):
                    return self._report()
                context = await self._context()
                item_custody._validate(context.snapshot)
                need(context.snapshot.phase == 'READY' and context.snapshot.owner == 'PLAYER'
                     and context.item_use_session.accepted_count == 0
                     and context.item_use_session._current is None,
                     'TRANSFER_UI_FRESH_READY_SELECTION_REQUIRED')
                a, b = item_custody._members(context.snapshot.frame_ab)
                self._anchor, self._other = a.identifier, b.identifier
                self._quantity = dict(b.raw_fields)[4]
                need(type(self._quantity) is int and 0 < self._quantity <= 0x7fffffff,
                     'TRANSFER_UI_WHOLE_QUANTITY_REQUIRED')
                self._initial_snapshot, self._equipment = context.snapshot, context.equipment
                self._accepted = context.item_use_session.accepted_count
                self._phase('INITIAL_SYNC')
                return self._report()
            context = await self._context()
            if self._quantity == 1 and self.phase in ('DROP_ENTRY_WAIT', 'DROP_BACKEND', 'DROP_CLIENT'):
                self._original()  # row lock await 뒤 같은 원clock을 재검사한다.
            if self.phase == 'INITIAL_SYNC':
                need(context.snapshot == self._initial_snapshot and context.equipment == self._equipment,
                     'TRANSFER_UI_INITIAL_STATE_CHANGED')
                await self._prepare_initial(context)
                need(self.runtime.request_inventory_ui_open() is True, 'TRANSFER_UI_ORIGINAL_OPEN_REQUIRED')
                self._phase('OPEN')
                return self._report()
            if self.phase == 'OPEN':
                opener = self.runtime.inventory_ui_opener
                value = opener.collect()
                if opener._requested:
                    due = monitor is None or time.monotonic() >= monitor.next_memory
                    if due:
                        await self.runtime._poll_equipment_slot(monitor)
                    value = opener.collect()
                if opener._pending is not None or opener._requested:
                    return self._report()
                need(type(value) is dict and value.get('status') == 'RETURNED'
                     and type(value.get('reason')) is int and value['reason'] == 0
                     and value.get('invoked') is value.get('opened') is True,
                     'TRANSFER_UI_ORIGINAL_OPEN_UNKNOWN')
                # No later collect of this now historical life after membership
                # changes. No new opener/rearm is created after transfer.
                opener.close()
                context = await self._context()
                if context.equipment.weapon_uid == self._other:
                    need(self._prepare_use is True, 'TRANSFER_UI_EXPLICIT_UNEQUIP_PREPARATION_REQUIRED')
                    self._use_before = context.item_use_session.accepted_count
                    need(self.consumer.pending is None, 'TRANSFER_UI_PREPARATION_PENDING_EXISTS')
                    value = self.consumer.submit_use_item(context.position.uid, self._other, context.position.map_id)
                    need(value.get('status') != 'UNKNOWN', 'TRANSFER_UI_PREPARATION_ADMISSION_UNKNOWN')
                    self._use_pending = self.consumer.pending
                    need(type(self._use_pending) is dict and self._use_pending.get('kind') == 'UseItem'
                         and self._use_pending.get('phase') == 'ADMISSION'
                         and self._use_pending.get('request') is None
                         and self._use_sequence is self._use_request is None,
                         'TRANSFER_UI_PREPARATION_ORIGINAL_ADMISSION_REQUIRED')
                    self._phase('PREPARE_USE', original_started=self._use_pending['started'])
                else:
                    self._phase('DROP_ENTRY')
                return self._report()
            if self.phase == 'PREPARE_USE':
                need(self.consumer.pending is self._use_pending,
                     'TRANSFER_UI_PREPARATION_PENDING_CHANGED')
                value = await self._poll_manual(monitor, preparation=True)
                if value is None:
                    return self._report()
                need(value.get('status') != 'UNKNOWN', 'TRANSFER_UI_PREPARATION_NATIVE_UNKNOWN')
                self._capture_preparation_publication(value)
                if value.get('status') != 'COMMITTED':
                    return self._report()
                need(type(value.get('sequence')) is int and value['sequence'] == self._use_sequence and value.get('command') == 'UseItem'
                     and value.get('proof_scope') == 'VALIDATED_ITEM_USE_INTENT_ONLY',
                     'TRANSFER_UI_PREPARATION_INTENT_RESULT_CHANGED')
                # This is not effect completion. Keep the SAME original Use
                # start/deadline while waiting for actual persist/notify/drain.
                self.phase = 'PREPARE_USE_BACKEND'
                return self._report()
            if self.phase == 'PREPARE_USE_BACKEND':
                if not self._preparation_backend(context):
                    return self._report()
                self._phase('DROP_ENTRY')
                return self._report()
            if self.phase == 'DROP_ENTRY':
                need(context.snapshot == self._initial_snapshot and context.equipment.weapon_uid != self._other,
                     'TRANSFER_UI_CURRENT_UNEQUIPPED_READY_B_REQUIRED')
                self.entry.submit_drop(anchor_inventory_uid=self._anchor, item_uid=self._other,
                                       whole_quantity=self._quantity)
                self._phase('DROP_ENTRY_WAIT')
            elif self.phase == 'DROP_ENTRY_WAIT':
                value = self.entry.collect()
                if value.get('status') == 'WAITING':
                    return self._report()
                self._returned(value, 'CURRENT_REGISTERED_DROP_CALLBACK_RETURN_ONLY')
                if self._quantity == 1:
                    # Original single-item Drop sends directly; keep the same
                    # Entry stage deadline while actual backend delivery settles.
                    self._phase('DROP_BACKEND', original_started=self._phase_started)
                else:
                    self.popup.submit(anchor_inventory_uid=self._anchor, action=1, kind=1,
                                      payload_uid=self._other, quantity=self._quantity)
                    self._phase('DROP_POPUP_WAIT')
            elif self.phase == 'DROP_POPUP_WAIT':
                value = self.popup.collect()
                if value.get('status') == 'WAITING':
                    return self._report()
                self._returned(value, 'ORIGINAL_POPUP_ENTRY_RETURN_ONLY')
                self._phase('DROP_BACKEND')
            elif self.phase == 'DROP_BACKEND':
                if context.snapshot.phase != 'DROPPED' or context.session.phase != 'DROPPED':
                    return self._report()
                need(context.snapshot.owner == 'GROUND' and context.membership.phase == 'DRAINED'
                     and context.session.pending is None and context.equipment == self._equipment,
                     'TRANSFER_UI_ACTUAL_DROP_DRAIN_REQUIRED')
                await self._begin_drop_client(context)
                if self._quantity == 1:
                    self._original()  # callee의 fresh current/_same 검사는 그대로 사용한다.
                self._phase('DROP_CLIENT',original_started=self._phase_started)
            elif self.phase == 'DROP_CLIENT':
                observed = await self._poll_drop_client(context,monitor)
                if self._quantity == 1:
                    self._original()  # 새 Get 단계를 시작하기 전에 원 Drop clock을 보존한다.
                if not observed:return self._report()
                self.entry.submit_get(anchor_inventory_uid=self._anchor, ground_uid=self._other,
                                      whole_quantity=self._quantity)
                self._phase('GET_ENTRY_WAIT')
            elif self.phase == 'GET_ENTRY_WAIT':
                value = self.entry.collect()
                if value.get('status') == 'WAITING':
                    return self._report()
                self._returned(value, 'CURRENT_TYPED_INTERACTION_CALLBACK_RETURN_ONLY')
                if self._quantity == 1:
                    # The separate original Get quantity branch also sends
                    # directly; keep its Entry deadline until real backend return.
                    self._phase('RETURN_BACKEND', original_started=self._phase_started)
                else:
                    self.popup.submit(anchor_inventory_uid=self._anchor, action=1, kind=2,
                                      payload_uid=self._other, quantity=self._quantity)
                    self._phase('GET_POPUP_WAIT')
            elif self.phase == 'GET_POPUP_WAIT':
                value = self.popup.collect()
                if value.get('status') == 'WAITING':
                    return self._report()
                self._returned(value, 'ORIGINAL_POPUP_ENTRY_RETURN_ONLY')
                self._phase('RETURN_BACKEND')
            elif self.phase == 'RETURN_BACKEND':
                if context.snapshot.phase != 'RETURNED' or context.session.phase != 'RETURNED':
                    return self._report()
                need(context.snapshot.owner == 'PLAYER' and context.membership.phase == 'DRAINED'
                     and context.session.pending is None and context.equipment == self._equipment
                     and context.current_frame == self._initial_snapshot.frame_ab
                     and context.snapshot.revision == self._initial_snapshot.revision + 2,
                     'TRANSFER_UI_ACTUAL_RETURN_DRAIN_REQUIRED')
                await self._begin_return_client(context)
                self._phase('RETURN_CLIENT',original_started=self._phase_started)
            elif self.phase == 'RETURN_CLIENT':
                if not await self._poll_return_client(context,monitor):return self._report()
                self._phase('DONE',original_started=self._phase_started)
            else:
                raise ValueError('TRANSFER_UI_PHASE_UNKNOWN')
            return self._report()
        except BaseException:
            self.close()
            self.last = dict(status='UNKNOWN', phase=self.phase, automatic_retry=False,
                             backend_effect='UNKNOWN', cleanup_required=True)
            self.last['backend_progress'] = self._diagnostic_report()
            refusal = self.entry.native_refusal()
            if refusal is not None:
                self.last['native_entry_refusal'] = refusal  # Output only; UNKNOWN stays terminal.
            refusal = self.popup.native_refusal()
            if refusal is not None:
                self.last['native_popup_refusal'] = refusal  # Earlier textbox effects are not rolled back.
            if self._preparation_clock is not None or self._preparation_backend_progress is not None:
                self.last['preparation_progress'] = self._preparation_report()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self._return_observer is not None:self._return_observer.close()
        self._return_nonce=None
        if self._drop_observer is not None:self._drop_observer.close()
        self._drop_nonce=None
        self.entry.cancel()
        self.popup.cancel()
        if self.started and self.phase != 'DONE':
            _TERMINAL(self.consumer, 'TRANSFER_UI_CLOSED_OR_UNKNOWN')
        # Never discard adapter.pending, clear busy, reset sequence, unlink
        # claims, roll back custody, or synthesize a ground retirement packet.
