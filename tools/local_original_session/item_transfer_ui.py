"""Explicit one-roundtrip UI owner; Native return never grants backend custody.

Only the original entry/popup adapters publish Native requests. The backend
continues to accept its own authenticated CS4E3F/CS4E3E independently.
"""
from types import MethodType
import threading
import time

from tools.local_original_session import item_custody, item_transfer_session
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
        self._claimed = self.started = self.closed = False
        self.phase = 'IDLE'
        self._phase_started = None
        self._prepare_use = False
        self._use_before = self._use_sequence = None
        self._use_pending = self._use_request = None
        self._accepted = None
        self._anchor = self._other = self._quantity = None
        self._initial_snapshot = self._equipment = None
        self._initial_prepare_attempted = False
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
        need(0 <= self.consumer._clock() - self._phase_started < WAIT_NS,
             'TRANSFER_UI_ORIGINAL_STAGE_DEADLINE')

    async def _context(self):
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
        async with row['operation_lock']:
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
        return context

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
        need(type(receipt) is dict and receipt.get('status') not in ('UNKNOWN', 'BLOCKED'),
             'TRANSFER_UI_PREPARATION_EFFECT_TERMINAL')
        if count == self._use_before or receipt.get('status') in ('NO_MATCH', 'NOT_PREPARED'):
            return False
        need(type(receipt.get('accepted_ordinal')) is int and receipt['accepted_ordinal'] == target
             and receipt.get('operation') == 'ITEM_USE_EFFECT' and receipt.get('item_uid') == self._other,
             'TRANSFER_UI_PREPARATION_EFFECT_IDENTITY_CHANGED')
        if receipt.get('status') != 'COMMITTED':
            return False
        need(receipt.get('before_weapon_uid') == self._other and receipt.get('after_weapon_uid') == 0,
             'TRANSFER_UI_ACTUAL_UNEQUIP_PREPARATION_REQUIRED')
        if not all(receipt.get(k) is True for k in
                   ('writer_bound','generation_bound','persisted','write_attempted','drain_returned','post_owner_verified')):
            return False
        need(receipt.get('phase') == 'DRAINED' and context.equipment.weapon_uid == 0,
             'TRANSFER_UI_PREPARATION_EFFECT_DRAIN_REQUIRED')
        self._accepted, self._equipment = target, context.equipment
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

    def _report(self):
        self.last = dict(status='COMPLETE' if self.phase == 'DONE' else 'PENDING', phase=self.phase,
                         automatic_retry=False, backend_effect='ROUNDTRIP_DRAINED' if self.phase == 'DONE' else 'UNKNOWN',
                         proof_scope='SOURCE_BOUND_LOCAL_BACKEND_AND_NATIVE_RETURNS',
                         native_runtime='UNVERIFIED_BY_BACKEND', render='UNKNOWN')
        return dict(self.last)

    async def poll(self, monitor=None):
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
                self.entry.submit_get(anchor_inventory_uid=self._anchor, ground_uid=self._other,
                                      whole_quantity=self._quantity)
                self._phase('GET_ENTRY_WAIT')
            elif self.phase == 'GET_ENTRY_WAIT':
                value = self.entry.collect()
                if value.get('status') == 'WAITING':
                    return self._report()
                self._returned(value, 'CURRENT_TYPED_INTERACTION_CALLBACK_RETURN_ONLY')
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
                self._phase('DONE')
            else:
                raise ValueError('TRANSFER_UI_PHASE_UNKNOWN')
            return self._report()
        except BaseException:
            self.close()
            self.last = dict(status='UNKNOWN', phase=self.phase, automatic_retry=False,
                             backend_effect='UNKNOWN', cleanup_required=True)
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.started and self.phase != 'DONE':
            _TERMINAL(self.consumer, 'TRANSFER_UI_CLOSED_OR_UNKNOWN')
        # Never discard adapter.pending, clear busy, reset sequence, unlink
        # claims, roll back custody, or synthesize a ground retirement packet.
