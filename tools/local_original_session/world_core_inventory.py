"""Selected inventory lifetime, durable admission and delivery for the broker.

The broker still owns sockets and locks. These methods operate on that same
owner, preserving dynamic overrides, save CAS and once-only consumption.
"""
from __future__ import annotations
import asyncio
import inspect
import re
import time
from tools.local_original_session import world_bridge
from tools.local_persistent_broker_policy.policy import OwnerSample, Peer


def need(value, code):
    if not value:
        raise ValueError(code)

INVENTORY_UPDATE_POLICY = 'EXPLICIT_LOCAL_OPAQUE_CURRENT_ITEM_UPDATE'

INVENTORY_RESELECTION_POLICY = 'LOCAL_SAVED_ROW_ON_RESELECTION'

INVENTORY_RESELECTION_DELIVERY = 'LOCAL_WORLD_READY_ONCE'

INVENTORY_MISSING_ROW_POLICY = 'EXPLICIT_LOCAL_CONFIGURED_STARTER_IF_MISSING'

INVENTORY_STARTER_FIELDS = {1: 65537, 2: 1, 3: 0, 4: 1, 5: 0, 7: 0,
    9: 0, 10: 0, 13: 0, 14: 0, 16: 0, 17: 0, 18: b'', 22: 0,
    24: False, 25: 0, 26: False}


class _InventoryGeneration:
    """One actual selection's mutable inventory lifetime; retired instances stay closed."""
    def __init__(self, broker, *, previous=None, restart_state=None):
        self.broker, self.previous, self.restart_state = broker, previous, restart_state
        self.writer = self.row = self.lock = self.game = self.selected = self.mover = None
        self.reader = self.store = self.account = None
        self.phase = 'ACTIVE'
        self.service = self.item_use_session = None
        self.frame = self.selection_binding = self.delivery_authority = self.current_frame = None
        self.update_operation = self.prewrite_refusal = self.operation_frame = None
        self.restored = self.attempted = self.restore_only = self.write_attempted = False
        self.deadline_ns = self.admission_clock_ns = self.sample_monotonic_ns = None
        self.admission_expired = False
        self.mode = None  # Actual restore provenance, never an inferred saved row.
        self.collection_grant = None  # Actual same-life durable grant; never a send capability.
        self.transfer_session = None


def _inventory_property(name):
    # Only the fixed declarations below use this facade. No attribute magic,
    # registry, copied receipt or caller-selected storage key is accepted.
    def get(broker):
        return getattr(broker._inventory_generation, name)
    def set_(broker, value):
        if '_inventory_generation' not in broker.__dict__:
            broker._inventory_generation = _InventoryGeneration(broker)
        setattr(broker._inventory_generation, name, value)
    return property(get, set_)



class InventoryCore:
    """Inventory operations on the owning broker, using its selected lifetime."""
    _inventory_service = _inventory_property('service')

    _item_use_session = _inventory_property('item_use_session')

    _inventory_frame = _inventory_property('frame')

    _inventory_selection_binding = _inventory_property('selection_binding')

    _inventory_restored = _inventory_property('restored')

    _inventory_attempted = _inventory_property('attempted')

    _inventory_restore_only = _inventory_property('restore_only')

    _inventory_delivery_authority = _inventory_property('delivery_authority')

    _inventory_current_frame = _inventory_property('current_frame')

    _inventory_update_operation = _inventory_property('update_operation')

    _inventory_prewrite_refusal = _inventory_property('prewrite_refusal')

    _inventory_write_attempted = _inventory_property('write_attempted')

    _inventory_operation_frame = _inventory_property('operation_frame')

    _inventory_deadline_ns = _inventory_property('deadline_ns')

    _inventory_admission_clock_ns = _inventory_property('admission_clock_ns')

    _inventory_admission_expired = _inventory_property('admission_expired')

    inventory_sample_monotonic_ns = _inventory_property('sample_monotonic_ns')


    def _inventory_owner_checkpoint_sync(self, writer, row, service, authority, wire, mode, operation_lock, *, item_transfer_operation=None):
        """A new exact owner query after the claimed leaf; never restamp old evidence."""
        guard = self._inventory_owner_guard
        policy, peer, policy_row = self.policy, row['peer'], row['policy_row']
        source_guard = self.source_guard
        owner, handle, job = policy.owner, policy.handle, policy.job
        peer_values = tuple(sorted(peer.items()))
        def current(*, authority_check=True):
            need(row['writer'] is writer and row['peer'] is peer
                 and tuple(sorted(peer.items())) == peer_values
                 and row['policy_row'] is policy_row and policy_row.writer is writer
                 and policy._connection(writer) is policy_row
                 and row['operation_lock'] is operation_lock and operation_lock.locked()
                 and not row['failed'] and not row['joined']
                 and not self._closing and not self.failure.is_set()
                 and policy.state == 'OPEN' and not policy_row.eof and not policy_row.failed
                 and policy_row.drain_started_ns is None and policy_row.pending_opcode is None
                 and policy_row.pending_size == 0,
                 'INVENTORY_SYNC_CURRENT_UNRESERVED_LOCK_REQUIRED')
            need(service is self._inventory_service and service._claimed is True
                 and service._inflight is False and not service._closed
                 and mode is True and self._inventory_collection_policy is not None,
                 'INVENTORY_SYNC_CLAIMED_RESTORE_REQUIRED')
            if item_transfer_operation is None:
                self._inventory_operation_mode_current(mode, writer, row, wire)
            if authority_check:
                service._same(authority, service._current(writer, row))
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        current()
        result = guard(dict(peer))
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            result = None  # Never await or retry this synchronous authority boundary.
        if result is not True:
            self._owner_failure(row, 'CALLBACK_FALSE' if result is False else 'CALLBACK_UNKNOWN')
        need(result is True, 'CURRENT_OWNER_REQUIRED')
        source_guard()
        current()
        sample = OwnerSample(owner, handle, job,
            Peer(peer['server_port'], peer['client_port'], peer['accepted_monotonic_ns']),
            time.monotonic_ns(), True, True)
        self._policy_sample(row, policy.checkpoint, writer, sample, time.monotonic_ns())
        # The policy callback must not replace authority or cancel before reservation.
        current(authority_check=False)
        return sample


    def _inventory_items(self, frame):
        from tools.local_original_session import inventory
        policy = self._inventory_collection_policy
        if policy is None:
            kit = world_bridge.inventory_items(self, frame)
            if kit is not None:
                return kit
            return (inventory.validate_frame(frame),)
        return inventory.validate_collection_frame(frame, policy=policy)


    def _inventory_collection_before_write_locked(self, writer, row, service, frame, items):
        """Called only from the original leaf AFTER its real empty-vector read.

        Synchronous same-row adoption before first write. No independent empty
        authority, re-lock, query, timer, send, rollback or retry is produced.
        """
        from tools.local_original_session import inventory_store
        generation = self.inventory_selection_current(writer)
        need(generation is self._inventory_generation and generation.row is row
             and row['operation_lock'].locked() and generation.phase == 'ACTIVE'
             and generation.mode == 'RESTORED_EXISTING' and generation.restored is True
             and generation.attempted is True and generation.write_attempted is False
             and generation.delivery_authority is None and generation.current_frame is None
             and self._inventory_restore_only is True
             and frame is generation.frame and frame is generation.operation_frame,
             'INVENTORY_COLLECTION_BEFORE_FIRST_DELIVERY_REQUIRED')
        self._inventory_selection_frame_current(writer, row, frame)
        if self.item_transfer_policy is not None:
            from tools.local_original_session import item_custody
            snapshot = self._inventory_store.custody_snapshot(self.realm.service(writer).snapshot().uid)
            need(self._inventory_collection_grant is None and
                 frame == item_custody.owned_frame(snapshot), 'ITEM_TRANSFER_EXACT_READONLY_CUSTODY_REQUIRED')
            return frame  # A-only is a real custody projection, NEVER a second grant.
        if len(items) == 2:
            return frame  # Existing saved2: no grant, only strict read-only verification.
        options = self._inventory_collection_grant
        need(type(options) is tuple and len(options) == 2 and
             options[0] == inventory_store.SECOND_INSTANCE_POLICY and type(options[1]) is frozenset
             and generation.collection_grant is None,
             'INVENTORY_COLLECTION_EXACT_GRANT_OPTIONS_REQUIRED')
        store = self._inventory_store
        # Revalidate the actual selection/source/cancel boundary before durable IO.
        service._cancelled()
        self._inventory_admission_time()
        authority = service._current(writer, row)
        bound = self._inventory_selection_binding
        grant = inventory_store.InventoryStore.grant_second_instance(
            store, authority[0].uid, expected_frame=frame, prototype_uid=items[0].identifier,
                       policy=options[0], reserved_uids=options[1])
        service._same(authority, service._current(writer, row))
        after = grant.after_frame
        # The exact original Store method validated the generated collection.
        # The leaf next parses that same after frame and verifies disk equality;
        # repeating source IO/codec here supplies no additional native authority.
        # Exactly one initial literal is now adopted. The old frame1/binding is
        # not accepted by _send, policy reservation or post-drain publication.
        generation.collection_grant = grant
        self._inventory_frame = self._inventory_operation_frame = after
        self._inventory_selection_binding = bound[:10] + (after,)
        return after


    def _inventory_selection_frame_current(self, writer, row, frame):
        """Keep the selected generation's one adopted literal, not restore-read identity."""
        store = getattr(self, '_inventory_store', None)
        if store is None:
            return
        service = self._inventory_service
        bound = self._inventory_selection_binding
        need(bound is not None and len(bound) == 11 and all(a is b for a, b in zip(bound,
            (writer, row, row['operation_lock'], self.realm, self.realm.registry,
             self.realm.registry.resolve(writer), self.realm.service(writer),
             self.realm.registry.resolve(writer).selection, service, store, frame)))
             and frame is self._inventory_frame and service._persistence_store() is store,
             'INVENTORY_SELECTED_STORE_FRAME_CHANGED')


    def inventory_selection_current(self, writer):
        """Structural current-generation observation only; no Store/native reads."""
        if getattr(self, 'inventory_reselection_policy', None) is None:
            return None
        generation = self._inventory_generation
        if generation.writer is None or generation.phase in ('RETIRED', 'PREPARING'):
            return None
        if generation.writer is writer and (generation.row.get('joined') is True
                                            or self.realm.registry._sessions.get(id(writer)) is None):
            return None  # The selected connection ended (Quit/EOF); no current selection remains.
        need(generation.phase == 'ACTIVE' and not self._closing and not self.failure.is_set(),
             'INVENTORY_RESELECTION_GENERATION_NOT_ACTIVE')
        return generation


    def _inventory_selection_start(self, writer, row):
        """Create one fresh lifetime at the actual selected callback, never reset old once."""
        from tools.local_original_session import inventory
        previous = self._inventory_generation
        game = self.realm.registry.resolve(writer)
        selected, mover = game.selection, self.realm.service(writer)
        account = self.realm._account_bound.get(id(writer))
        need(type(self.inventory_reselection_policy) is str
             and self.inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
             and type(self.inventory_delivery_policy) is str
             and self.inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
             and self.restart_policy == 'EXPLICIT_LOCAL_SELECTED_RESTART'
             and self.policy.restart_enabled is True
             and selected is not None and account is not None and row['writer'] is writer
             and row['operation_lock'].locked(), 'INVENTORY_RESELECTION_SELECTED_LOCK_REQUIRED')
        if previous.writer is None:
            generation = previous
        elif previous.phase == 'RETIRED':
            restart_state = row.get('_restart')
            need(previous.writer is writer and previous.game is game and previous.account is account
                 and previous.selected is not selected and previous.service._closed
                 and previous.reader is self._inventory_reader and previous.store is self._inventory_store
                 and restart_state is previous.restart_state and restart_state['phase'] == 'DRAINED'
                 and restart_state['selection_cleared'] is True,
                 'INVENTORY_RESELECTION_DRAINED_NEW_SELECTION_REQUIRED')
            generation = _InventoryGeneration(self, previous=previous, restart_state=restart_state)
            generation.phase = 'PREPARING'
            self._inventory_generation = generation
        else:
            need(previous.phase == 'ACTIVE' and previous.writer is writer
                 and previous.game is game and previous.selected is selected,
                 'INVENTORY_RESELECTION_NEW_GENERATION_REQUIRED')
            return previous
        generation.writer, generation.row, generation.lock = writer, row, row['operation_lock']
        generation.game, generation.selected, generation.mover = game, selected, mover
        generation.account, generation.reader, generation.store = account, self._inventory_reader, self._inventory_store
        generation.phase = 'PREPARING'
        try:
            if generation.previous is not None:
                generation.service = inventory.InventoryService(self, generation.reader,
                    policy=inventory.POLICY, store=generation.store, collection_policy=self._inventory_collection_policy)
                generation.service._inventory_generation = generation
                if self._inventory_item_use_policy is not None:
                    from tools.local_original_session.item_use_session import ItemUseSession
                    old = previous.item_use_session
                    generation.item_use_session = ItemUseSession(self, policy=self._inventory_item_use_policy)
                    self.realm._replace_item_use_selection(self, writer, old, generation.item_use_session)
                else:
                    need(self.realm._item_use_session is None, 'ITEM_USE_RESELECTION_DISABLED_REQUIRED')
            return generation
        except BaseException:
            generation.phase = 'TERMINAL'
            if generation.service is not None:
                generation.service.close()
            if generation.item_use_session is not None:
                generation.item_use_session.close()
            raise


    async def _restore_inventory_selection(self, writer):
        """Select-time read only. No grant, memory query, automatic delivery or retry."""
        from tools.local_original_session.inventory_store import InventoryStore
        generation = None
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
            need(len(rows) == 1, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
            generation = self._inventory_selection_start(writer, rows[0])
        service, store = self._inventory_service, self._inventory_store
        fallback_config = self._inventory_config_frame
        missing_policy = getattr(self, 'inventory_missing_row_policy', None)
        need(service is not None and type(store) is InventoryStore
             and service._persistence_store() is store, 'INVENTORY_EXACT_SELECTED_STORE_REQUIRED')
        # This broker's original once/closed/delivery state is never reset by
        # game Restart/reselect. Redelivery in that lifetime is not supported.
        if self._inventory_attempted:
            return
        rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
        need(len(rows) == 1, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
        row, = rows
        lock = row['operation_lock']
        try:
            before = service._current(writer, row)
            game, selected = self.realm.registry.resolve(writer), self.realm.registry.resolve(writer).selection
            mover = self.realm.service(writer)
            restored = InventoryStore.restore(store, before[0].uid)
            if self.item_transfer_policy is not None:
                from tools.local_original_session.item_transfer_session import restore_owned_custody
                _, custody_frame = restore_owned_custody(store,before[0].uid)
                need(custody_frame == restored, 'ITEM_TRANSFER_READONLY_RESTORE_CHANGED')
            if restored is not None:
                from tools.local_original_session import inventory
                self._inventory_items(restored)
            await self._checkpoint(writer, row)  # After file IO: current native tuple/source.
            self.source_guard()
            self.key_guard()
            service.reader.validate()
            need(lock.locked() and not self._inventory_attempted,
                 'INVENTORY_SELECTED_RESTORE_BINDING_CHANGED')
            service._same(before, service._current(writer, row))
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            mode = 'RESTORED_EXISTING' if restored is not None else None
            frame = None if generation is not None and restored is None else (fallback_config if restored is None else restored)
            if generation is not None and restored is None and missing_policy is not None:
                from tools.local_original_session import inventory
                athame = getattr(self, '_inventory_athame_config_frame', fallback_config)
                need(before[0].uid == self.realm.profile_uid
                     and (before[0].uid == 1 or self._inventory_kit_policy == inventory.KIT_POLICY)
                     and dict(inventory.validate_frame(athame).raw_fields) == INVENTORY_STARTER_FIELDS,
                     'INVENTORY_MISSING_ROW_CURRENT_ATHAME_STARTER_REQUIRED')
                frame, mode = fallback_config, 'FIRST_GRANT'
                frame = world_bridge.starter_frame(self, before[0].name, fallback_config)
            self._inventory_frame = frame  # Adopt this object exactly once for this selection.
            self._inventory_selection_binding = (None if frame is None else
                (writer, row, lock, self.realm, self.realm.registry, game, mover, selected, service, store, frame))
            self._inventory_restored = restored is not None
            if generation is not None:
                generation.mode = mode
                generation.phase = 'ACTIVE'
                if self.item_transfer_policy is not None:
                    from tools.local_original_session.item_transfer_session import ItemTransferSession
                    need(generation.transfer_session is None, 'ITEM_TRANSFER_FRESH_SESSION_REQUIRED')
                    generation.transfer_session = ItemTransferSession(self, generation)
        except BaseException:
            if generation is not None:
                generation.phase = 'TERMINAL'
                if generation.item_use_session is not None:
                    generation.item_use_session.close()
            service.close()  # Failed IO/authority/cancel grants no later send in this broker.
            raise


    def _inventory_operation_mode_current(self, mode, writer, row, frame):
        need(type(mode) is bool and self._inventory_restore_only is mode,
             'INVENTORY_RESTORE_MODE_CHANGED')
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            generation = self._inventory_generation
            need(self.inventory_selection_current(writer) is generation
                 and generation.phase == 'ACTIVE' and generation.row is row,
                 'INVENTORY_CURRENT_DELIVERY_GENERATION_REQUIRED')
            if generation.mode == 'FIRST_GRANT':
                from tools.local_original_session import inventory
                need(mode is False and generation.restored is False
                     and getattr(self, 'inventory_missing_row_policy', None) == INVENTORY_MISSING_ROW_POLICY
                     and frame is self._inventory_config_frame
                     and world_bridge.first_grant_valid(self, frame),
                     'INVENTORY_FIRST_GRANT_MODE_REQUIRED')
            else:
                need(generation.mode == 'RESTORED_EXISTING' and mode is True
                     and generation.restored is True, 'INVENTORY_RESTORED_EXISTING_MODE_REQUIRED')
        if mode:
            need(self._inventory_store is not None and self._inventory_restored is True,
                 'INVENTORY_RESTORE_SELECTED_STORE_REQUIRED')
            self._inventory_selection_frame_current(writer, row, frame)


    def _inventory_refusal_current(self, error):
        """Recheck the actual refused send lifetime without reopening its service."""
        evidence = self._inventory_prewrite_refusal
        need(evidence is not None and evidence[0] is error
             and len(evidence) == 5 and evidence[2] is self._inventory_service
             and type(evidence[3]) is bool and self._inventory_restore_only is evidence[3],
             'INVENTORY_PRE_WRITE_PROOF_REQUIRED')
        self.source_guard()
        need(self.key_guard() is True, 'INVENTORY_REFUSAL_OWNER_UNKNOWN')
        authority = evidence[1]
        need(not self._inventory_write_attempted
             and self._inventory_frame is evidence[4]
             and self._inventory_operation_frame is evidence[4],
             'INVENTORY_PRE_WRITE_PROOF_REQUIRED')
        (broker, reader, backend, owner, member, policy, handle, job, owner_handle,
         owner_job, realm, registry, game, movement, position, selected, row,
         admitted, lock, peer, failure, store, positions, movement_row) = authority[1]
        need(registry.resolve(row['writer']) is game and game.selection is selected
             and not self._closing and not failure.is_set() and policy.state == 'OPEN'
             and not any((row['failed'], row['joined'], admitted.failed, admitted.eof,
                          admitted.task_joined, admitted.registry_removed))
             and admitted.drain_started_ns is None and not movement.fatal and not realm._settings_failed
             and id(row['writer']) not in realm._quit, 'INVENTORY_REFUSAL_OWNER_CHANGED')
        self._inventory_operation_mode_current(evidence[3], row['writer'], row, evidence[4])
        realm.bound_account(row['writer'], game)
        saved_uid, _ = store.select(selected.reference)
        need(saved_uid == position.uid and positions.restore(position) == position,
             'INVENTORY_REFUSAL_STORAGE_CHANGED')
        from tools.local_original_session import inventory
        if type(error) is inventory.ReadOnlyPreWriteRefusal:
            need(type(self._inventory_admission_expired) is bool, 'INVENTORY_ADMISSION_EXPIRY_REQUIRED')
            need(inventory.InventoryService.validate_readonly_refusal(
                evidence[2], error, row['writer'], row, evidence[4],
                admission=False if self._inventory_admission_expired is True else True) is True,
                'INVENTORY_READONLY_REFUSAL_UNPROVEN')
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return True


    def _inventory_admission_time(self):
        now = time.monotonic_ns()
        self._inventory_admission_clock_ns = now
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        if self._inventory_deadline_ns is not None and now >= self._inventory_deadline_ns:
            evidence = self._inventory_prewrite_refusal
            if evidence is not None:
                self._inventory_refusal_current(evidence[0])
                self._inventory_admission_expired = True
                self._inventory_service.close()
                raise evidence[0]
            raise ValueError('INVENTORY_ADMISSION_DEADLINE')
        return now


    async def add_inventory(self, writer, *, deadline_ns=None, restore_only=False):
        """One explicit configured ADD; no trigger, timer or delivery retry."""
        from tools.local_original_session import inventory
        need(type(restore_only) is bool, 'INVENTORY_RESTORE_MODE_REQUIRED')
        generation = self._inventory_generation
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            need(generation.phase == 'ACTIVE' and self.inventory_selection_current(writer) is generation
                 and type(generation.frame) is bytes and generation.selection_binding is not None,
                 'INVENTORY_RESELECTION_SAVED_ROW_RESTORE_ONLY_REQUIRED')
            if generation.mode == 'FIRST_GRANT':
                need(restore_only is False and generation.restored is False
                     and getattr(self, 'inventory_missing_row_policy', None) == INVENTORY_MISSING_ROW_POLICY
                     and generation.frame is self._inventory_config_frame,
                     'INVENTORY_FIRST_GRANT_MODE_REQUIRED')
            else:
                need(generation.mode == 'RESTORED_EXISTING' and restore_only is True
                     and generation.restored is True,
                     'INVENTORY_RESELECTION_SAVED_ROW_RESTORE_ONLY_REQUIRED')
        service = self._inventory_service
        previous = self._inventory_prewrite_refusal
        continuation = (self._inventory_attempted and previous is not None
                        and self._inventory_deadline_ns is not None)
        need(service is not None and not self._inventory_write_attempted
             and (not self._inventory_attempted
                  or continuation and not service._closed and not service._claimed),
             'INVENTORY_EXPLICIT_ONCE_OPERATION_REQUIRED')
        if not self._inventory_attempted:
            self._inventory_attempted = True  # One command, before any await/cancellation.
            self._inventory_operation_frame = self._inventory_frame
            self._inventory_restore_only = restore_only
            self._inventory_deadline_ns = deadline_ns
        operation_frame = self._inventory_operation_frame if previous is None else None
        row = None
        try:
            need(deadline_ns is None or type(deadline_ns) is int and 0 <= deadline_ns < (1 << 63),
                 'INVENTORY_ADMISSION_DEADLINE_REQUIRED')
            need(deadline_ns == self._inventory_deadline_ns, 'INVENTORY_ORIGINAL_DEADLINE_REQUIRED')
            need(self._inventory_restore_only is restore_only, 'INVENTORY_RESTORE_MODE_CHANGED')
            if continuation:
                row = previous[1][1][16]
                operation_frame = previous[4]
                self._inventory_refusal_current(previous[0])
                need(row['writer'] is writer, 'INVENTORY_ORIGINAL_WRITER_REQUIRED')
            self._inventory_admission_time()
            rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
            need(len(rows) == 1, 'INVENTORY_CURRENT_CLAIM_REQUIRED')
            row, = rows
            operation_lock = row['operation_lock']
            # Capture real authority before waiting; never switch to a new selection.
            game = self.realm.registry.resolve(writer)
            registry, selected = self.realm.registry, game.selection
            movement = self.realm.service(writer)
            position = movement.snapshot()
            async with operation_lock:
                need(row['operation_lock'] is operation_lock, 'INVENTORY_OPERATION_LOCK_CHANGED')
                need(self.realm.registry is registry and registry.resolve(writer) is game
                     and game.selection is selected and self.realm.service(writer) is movement
                     and movement.snapshot() is position, 'INVENTORY_AUTHORITY_CHANGED')
                self._inventory_operation_mode_current(restore_only, writer, row, operation_frame)
                authority = service._current(writer, row)
                if previous is not None:
                    service._same(previous[1], authority)
                self._inventory_admission_time()
                await self._send(writer, row, (operation_frame,), game=True,
                                 inventory_service=service, inventory_authority=authority,
                                 inventory_restore_only=restore_only, operation_lock=operation_lock)
                if self._inventory_collection_policy is not None:
                    operation_frame = self._inventory_operation_frame
                service._same(authority, service._current(writer, row))
                self._inventory_operation_mode_current(restore_only, writer, row, operation_frame)
                self._inventory_delivery_authority = authority
                need(self._inventory_current_frame is None, 'INVENTORY_INITIAL_CURRENT_ALREADY_SET')
                self._inventory_current_frame = operation_frame
                self._inventory_prewrite_refusal = None
            return dict(status='COMMITTED', command='AddInventory',
                        proof_scope='TRANSPORT_DRAIN_ONLY', client_inventory='UNKNOWN', invoked=True)
        except BaseException as error:
            evidence = self._inventory_prewrite_refusal
            if evidence is not None and evidence[0] is error:
                try:
                    self._inventory_refusal_current(error)
                except BaseException:
                    self._inventory_prewrite_refusal = None
                    service.close()
                    if row is not None:
                        row['failed'] = True
                        self._fail('INVENTORY_SEND_OUTCOME_UNKNOWN')
                    raise  # Preserve cancellation/fresh-authority failure from this checkpoint.
                else:
                    if (self._inventory_deadline_ns is not None
                            and not service._closed and not service._claimed
                            and not self._inventory_admission_expired
                            and (type(error) is inventory.ReadOnlyPreWriteRefusal
                                 or type(error) is inventory.PreWriteReadRefusal
                                 and re.fullmatch(r'CODE_GUARD_BEFORE_[0-9]{4}', error.stage))):
                        return dict(status='PENDING', command='AddInventory', phase='ADMISSION',
                            reason=('INVENTORY_READONLY_ADMISSION_WAIT'
                                    if type(error) is inventory.ReadOnlyPreWriteRefusal
                                    else 'INVENTORY_CODE_PAGE_ADMISSION_WAIT'), refusal_reason=error.reason,
                            stage=error.stage, invoked=False, write_attempted=False,
                            client_inventory='UNKNOWN')
                    service.close()
                    raise
            service.close()  # Includes pre-write refusal; this explicit operation never retries.
            if row is not None:
                row['failed'] = True
                self._fail('INVENTORY_SEND_OUTCOME_UNKNOWN')
            raise


    async def prepare_item_equipment(self, writer, *, policy, first_enable):
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        effect = self._item_equipment_effect
        need(type(effect) is ItemEquipmentEffect and type(policy) is str and policy == effect.policy and
             type(first_enable) is bool and first_enable is effect.first_enable,
             'EQUIPMENT_SAME_CONFIGURED_EFFECT_REQUIRED')
        rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
        need(len(rows) == 1, 'EQUIPMENT_CURRENT_CLAIM_REQUIRED')
        async with rows[0]['operation_lock']:
            return await effect.prepare_locked(writer)


    def item_equipment_observation(self, writer, *, accepted_ordinal=None):
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        effect = self._item_equipment_effect
        need(type(effect) is ItemEquipmentEffect,
             'EQUIPMENT_ORIGINAL_OBSERVATION_REQUIRED')
        return effect.observation(writer, accepted_ordinal=accepted_ordinal)


    def _validate_inventory_update_reply(self, writer, wire):
        state = self._inventory_update_operation
        need(state is not None and wire is state['wire'] and state['writer'] is writer,
             'INVENTORY_UPDATE_EXACT_WIRE_REQUIRED')
        self._inventory_update_current(writer, state['row'], state)


    def _inventory_update_time(self, state):
        now = time.monotonic_ns()
        need(type(now) is int and state['last_ns'] <= now < state['deadline_ns'],
             'INVENTORY_UPDATE_OPERATION_DEADLINE')
        state['last_ns'] = now
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        return now


    def _inventory_update_current(self, writer, row, state, request=None):
        from tools.local_original_session import inventory, inventory_update, observe
        from tools.local_original_session.inventory_store import InventoryStore
        self._inventory_update_time(state)
        need(state is self._inventory_update_operation and state['writer'] is writer
             and state['row'] is row and state['lock'] is row['operation_lock'] and state['lock'].locked()
             and state['phase'] not in ('TERMINAL', 'DRAINED')
             and self.inventory_update_policy == INVENTORY_UPDATE_POLICY
             and self.policy.inventory_update is True, 'INVENTORY_UPDATE_CURRENT_OPERATION_REQUIRED')
        (realm, registry, game, mover, position, selected, service, reader, store,
         binding, delivery, initial, mode) = state['refs']
        need(self._inventory_current_frame is state['old']
             and self._inventory_attempted is True and self._inventory_write_attempted is True
             and self._inventory_prewrite_refusal is None and self._inventory_admission_expired is False
             and service._claimed is True and not service._closed and not service._inflight,
             'INVENTORY_UPDATE_DELIVERED_SELECTION_REQUIRED')
        admitted = row['policy_row']
        if state['phase'] in ('RESERVING', 'WRITE_ATTEMPTED') and admitted.drain_started_ns is not None:
            need(admitted.pending_opcode == 0x0965 and admitted.pending_size == len(state['wire']),
                 'INVENTORY_UPDATE_CURRENT_RESERVATION_REQUIRED')
        else:
            need(admitted.drain_started_ns is None and admitted.pending_opcode is None
                 and admitted.pending_size == 0, 'INVENTORY_UPDATE_UNRESERVED_POLICY_REQUIRED')
        self._inventory_operation_mode_current(mode, writer, row, initial)
        self.source_guard()
        need(self.key_guard() is True, 'INVENTORY_UPDATE_RETAINED_OWNER_REQUIRED')
        observe.RetainedSceneReader.validate(reader)
        authority = inventory.InventoryService._current(service, writer, row)
        if state['authority'] is not None:
            inventory.InventoryService._same(state['authority'], authority)
        expected = state['new'] if state['persisted'] else state['old']
        need(InventoryStore.restore(store, position.uid) == expected,
             'INVENTORY_UPDATE_STORED_FRAME_CHANGED')
        inventory.validate_frame(state['old'])
        if state['new'] is not None:
            inventory.validate_frame(state['new'])
            inventory_update.validate_frame(state['wire'])
        self.source_guard()
        inventory.InventoryService._same(authority, inventory.InventoryService._current(service, writer, row))
        self._inventory_update_time(state)
        return authority


    async def update_inventory(self, writer, *, item_identifier, changes, policy, deadline_ns=None):
        """One explicit local opaque update; persistence precedes its one transport attempt."""
        from tools.local_original_session import inventory, inventory_update
        from tools.local_original_session.inventory_store import InventoryStore
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            need(self.inventory_selection_current(writer) is self._inventory_generation
                 and self._inventory_generation.phase == 'ACTIVE',
                 'INVENTORY_RESELECTION_UPDATE_ACTIVE_REQUIRED')
        need(type(policy) is str and policy == INVENTORY_UPDATE_POLICY
             and self.inventory_update_policy == policy and self.policy.inventory_update is True,
             'INVENTORY_UPDATE_EXPLICIT_POLICY_REQUIRED')
        need(type(changes) is dict and changes and all(type(k) is int for k in changes)
             and changes.keys() <= {4, 5, 7, 18}, 'INVENTORY_UPDATE_EXPLICIT_CHANGES_REQUIRED')
        frozen_changes = tuple(sorted(changes.items()))  # Scalars/bytes validated before the first await.
        old = self._inventory_current_frame
        old_item = inventory.validate_frame(old)
        need(type(item_identifier) is int and item_identifier == old_item.identifier,
             'INVENTORY_UPDATE_SAME_ITEM_REQUIRED')
        fields = dict(old_item.raw_fields)
        need(all(fields[k] != value for k, value in frozen_changes), 'INVENTORY_UPDATE_ACTUAL_CHANGE_REQUIRED')
        updated = dict(fields); updated.update(frozen_changes)
        new = inventory.build_add(updated)
        wire_fields = {1: item_identifier, **dict(frozen_changes)}
        wire = inventory_update.build_update(wire_fields)
        inventory_update.validate_frame(wire)
        need(new != old, 'INVENTORY_UPDATE_ACTUAL_CHANGE_REQUIRED')
        previous = self._inventory_update_operation
        need(previous is None or previous['phase'] == 'DRAINED', 'INVENTORY_UPDATE_OPERATION_PENDING_OR_TERMINAL')
        rows = [r for claims in self._claims.values() for r in claims if r['writer'] is writer]
        need(len(rows) == 1, 'INVENTORY_UPDATE_CURRENT_CLAIM_REQUIRED')
        row, = rows
        lock = row['operation_lock']
        game, mover = self.realm.registry.resolve(writer), self.realm.service(writer)
        service = self._inventory_service
        now = time.monotonic_ns()
        need(type(now) is int and 0 <= now < (1 << 63)
             and (deadline_ns is None or type(deadline_ns) is int and now < deadline_ns <= now + 10_000_000_000),
             'INVENTORY_UPDATE_ORIGINAL_DEADLINE_REQUIRED')
        state = dict(writer=writer, row=row, lock=lock, old=old, new=new, wire=wire,
            changes=frozen_changes, policy=policy, phase='CLAIMED', persisted=False,
            persist_attempted=False, write_attempted=False, drain_returned=False, post_owner_verified=False,
            item_use=self._item_use_session,
            sent_after=None, authority=None, sent_before=None, deadline_ns=now + 10_000_000_000 if deadline_ns is None else deadline_ns, last_ns=now,
            refs=(self.realm, self.realm.registry, game, mover, mover.snapshot(), game.selection,
                  service, service.reader, self._inventory_store, self._inventory_selection_binding,
                  self._inventory_delivery_authority, self._inventory_frame, self._inventory_restore_only))
        request = state['request'] = (old, new, wire, frozen_changes, state['refs'], policy, state['deadline_ns'], state['item_use'])
        self._inventory_update_operation = state
        try:
            async with lock:
                state['authority'] = self._inventory_update_current(writer, row, state, request)
                state['sent_before'] = row['policy_row'].sent
                await self._checkpoint(writer, row)
                self._inventory_update_current(writer, row, state, request)
                self._inventory_update_time(state)
                state['phase'], state['persist_attempted'] = 'PERSISTING', True
                need(InventoryStore.replace_existing(state['refs'][8], state['authority'][0].uid, old, new) is True,
                     'INVENTORY_UPDATE_PERSISTED_CHANGE_REQUIRED')
                state['persisted'], state['phase'] = True, 'PERSISTED'
                self._inventory_update_current(writer, row, state, request)
                await self._send(writer, row, (wire,), game=True, operation_lock=lock,
                                 inventory_update_operation=state, inventory_update_request=request)
                self._inventory_update_current(writer, row, state, request)
                need(state['phase'] == 'WRITE_ATTEMPTED' and state['drain_returned'] is True
                     and state['post_owner_verified'] is True
                     and state['sent_after'] == state['sent_before'] + 1,
                     'INVENTORY_UPDATE_EXACT_DRAIN_REQUIRED')
                if state['item_use'] is not None:
                    from tools.local_original_session.item_use_session import ItemUseSession
                    ItemUseSession.release(state['item_use'], writer)
                self._inventory_update_time(state)
                self._inventory_current_frame = new
                state['phase'] = 'DRAINED'
            return dict(status='COMMITTED', command='UpdateInventory', proof_scope='TRANSPORT_DRAIN_ONLY',
                        storage='LOCAL_OPAQUE_FRAME_REPLACED', client_inventory='UNKNOWN', invoked=True)
        except BaseException:
            state['phase'] = 'TERMINAL'
            if state['persist_attempted']:
                self._fail('INVENTORY_UPDATE_OUTCOME_UNKNOWN')
                row['failed'] = True
            else:
                self._inventory_update_operation = previous  # No write/IO attempt; ordinary refusal only.
            raise


    def _configure_inventory(self, *,
            inventory_policy, inventory_frame, inventory_reader, inventory_store_policy,
            item_use_policy, inventory_update_policy, item_equipment_policy, item_equipment_first_enable,
            inventory_reselection_policy, inventory_delivery_policy, inventory_missing_row_policy, inventory_collection_policy,
            inventory_collection_grant, inventory_owner_guard, retained_owner, restart_policy,
            world_policy, item_transfer_policy,
    ):
        inventory_enabled = any(v is not None for v in (inventory_policy, inventory_frame, inventory_reader))
        if inventory_enabled:
            from tools.local_original_session import inventory
            need(type(inventory_policy) is str and inventory_policy == inventory.POLICY
                 and type(inventory_frame) is bytes and inventory_reader is not None,
                 'INVENTORY_EXPLICIT_POLICY_FRAME_READER_REQUIRED')
            inventory.validate_frame(inventory_frame)
        if inventory_store_policy is not None:
            from tools.local_original_session import inventory_store
            need(inventory_enabled and type(inventory_store_policy) is str
                 and inventory_store_policy in (inventory_store.POLICY, inventory_store.COLLECTION_STORE_POLICY),
                 'INVENTORY_STORE_REQUIRES_EXPLICIT_INVENTORY_POLICY')
        if item_use_policy is not None:
            from tools.local_original_session import item_use_session
            need(type(item_use_policy) is str and item_use_policy == item_use_session.POLICY,
                 'EXPLICIT_ITEM_USE_INTENT_POLICY_REQUIRED')
            need(inventory_enabled and inventory_store_policy is not None,
                 'ITEM_USE_REQUIRES_STORED_INVENTORY')
        if inventory_update_policy is not None:
            from tools.local_original_session import inventory_update
            need(type(inventory_update_policy) is str and inventory_update_policy == INVENTORY_UPDATE_POLICY,
                 'EXPLICIT_INVENTORY_UPDATE_POLICY_REQUIRED')
            need(inventory_enabled and inventory_store_policy is not None,
                 'INVENTORY_UPDATE_REQUIRES_STORED_INVENTORY')
            inventory_update.source_ready()
        self.inventory_update_policy = inventory_update_policy
        if item_equipment_policy is not None:
            from tools.local_original_session.item_equipment_effect import POLICY as EQUIPMENT_POLICY
            need(type(item_equipment_policy) is str and item_equipment_policy == EQUIPMENT_POLICY and
                 item_use_policy is not None and inventory_store_policy is not None and
                 type(item_equipment_first_enable) is bool, 'EQUIPMENT_EXPLICIT_POLICY_REQUIRED')
        else:
            need(item_equipment_first_enable is False, 'EQUIPMENT_FIRST_ENABLE_REQUIRES_POLICY')
        self.item_equipment_policy = item_equipment_policy
        self.item_equipment_first_enable = item_equipment_first_enable
        if inventory_reselection_policy is not None:
            need(type(inventory_reselection_policy) is str
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and type(inventory_delivery_policy) is str
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and restart_policy is not None and inventory_enabled
                 and inventory_store_policy is not None,
                 'INVENTORY_RESELECTION_EXPLICIT_STORED_RESTART_DELIVERY_REQUIRED')
        if inventory_missing_row_policy is not None:
            need(type(inventory_missing_row_policy) is str
                 and inventory_missing_row_policy == INVENTORY_MISSING_ROW_POLICY
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and inventory_store_policy is not None and inventory_enabled,
                 'INVENTORY_MISSING_ROW_EXPLICIT_POLICY_REQUIRED')
            need(dict(inventory.validate_frame(inventory_frame).raw_fields) == INVENTORY_STARTER_FIELDS,
                 'INVENTORY_MISSING_ROW_EXACT_ATHAME_STARTER_REQUIRED')
        if inventory_collection_policy is not None:
            need(type(inventory_collection_policy) is str and inventory_collection_policy == inventory.COLLECTION_POLICY
                 and inventory_store_policy == inventory_store.COLLECTION_STORE_POLICY
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and inventory_missing_row_policy is None,
                 'INVENTORY_COLLECTION_EXPLICIT_RESTORE_ONLY_REQUIRED')
            if item_transfer_policy is not None:
                need(inventory_collection_grant is None, 'ITEM_TRANSFER_READONLY_NO_GRANT_REQUIRED')
            else:
                need(type(inventory_collection_grant) is tuple and len(inventory_collection_grant) == 2
                     and type(inventory_collection_grant[0]) is str
                     and inventory_collection_grant[0] == inventory_store.SECOND_INSTANCE_POLICY
                     and type(inventory_collection_grant[1]) is frozenset
                     and len(inventory_collection_grant[1]) <= 4096
                     and all(type(uid) is int and 0 <= uid <= 0xffffffff for uid in inventory_collection_grant[1]),
                     'INVENTORY_COLLECTION_EXPLICIT_GRANT_OPTIONS_REQUIRED')
        else:
            need(inventory_collection_grant is None and
                 (inventory_store_policy is None or inventory_store_policy == inventory_store.POLICY),
                 'INVENTORY_COLLECTION_POLICY_REQUIRED')
        if inventory_owner_guard is not None:
            from tools.local_original_session.launcher import NativeOwner
            need(inventory_collection_policy == inventory.COLLECTION_POLICY
                 and inventory_reselection_policy == INVENTORY_RESELECTION_POLICY
                 and inventory_delivery_policy == INVENTORY_RESELECTION_DELIVERY
                 and inventory_missing_row_policy is None,
                 'INVENTORY_SYNC_OWNER_EXPLICIT_COLLECTION_REQUIRED')
            need(type(retained_owner) is NativeOwner
                 and getattr(inventory_owner_guard, '__self__', None) is retained_owner
                 and getattr(inventory_owner_guard, '__func__', None) is NativeOwner.guard_exact_sync
                 and not inspect.iscoroutinefunction(inventory_owner_guard),
                 'INVENTORY_SYNC_ORIGINAL_OWNER_GUARD_REQUIRED')
        self._inventory_owner_guard = inventory_owner_guard
        self._inventory_owner_guard_binding = (inventory_owner_guard.__self__, inventory_owner_guard.__func__) \
            if inventory_owner_guard is not None else None
        self._inventory_collection_policy = inventory_collection_policy
        self._inventory_collection_grant = inventory_collection_grant
        self.inventory_missing_row_policy = inventory_missing_row_policy
        self.inventory_reselection_policy = inventory_reselection_policy
        self.inventory_delivery_policy = inventory_delivery_policy
        self._inventory_reader = inventory_reader
        self._inventory_item_use_policy = item_use_policy
        self._inventory_generation = _InventoryGeneration(self)
        self._inventory_kit_policy = world_bridge.kit_policy(world_policy,
            inventory_missing_row_policy, inventory_collection_policy,
            item_transfer_policy, inventory_store_policy)
        return inventory_enabled

    def _initialize_inventory(self, *,
            inventory_enabled, inventory_frame, inventory_reader, inventory_policy,
            inventory_store_policy, inventory_custody_policy, inventory_reselection_policy, inventory_update_policy,
            world_policy, item_use_policy, item_equipment_policy, item_equipment_first_enable,
            item_transfer_policy,
    ):
        self._item_use_session = None
        self._inventory_service = None
        self._inventory_frame = inventory_frame
        self._inventory_config_frame = inventory_frame
        self._inventory_athame_config_frame = inventory_frame  # Kit mode may replace the config frame.
        self._inventory_store = None
        self._inventory_selection_binding = None
        self._inventory_restored = False
        self._inventory_attempted = False
        self._inventory_restore_only = False
        self._inventory_delivery_authority = None
        self._inventory_current_frame = None
        self._inventory_update_operation = None
        self._inventory_prewrite_refusal = None
        self._inventory_write_attempted = False
        self._inventory_operation_frame = None
        self._inventory_deadline_ns = None
        self._inventory_admission_clock_ns = None
        self._inventory_admission_expired = False
        self.inventory_sample_monotonic_ns = None
        if inventory_enabled:
            from tools.local_original_session import inventory, inventory_store
            if inventory_store_policy is not None:
                self._inventory_store = inventory_store.InventoryStore(self.realm.store.path,
                    policy=inventory_store_policy, custody_policy=inventory_custody_policy,
                    kit_policy=self._inventory_kit_policy)
            self._inventory_service = inventory.InventoryService(self, inventory_reader, policy=inventory_policy,
                                                               store=self._inventory_store, collection_policy=self._inventory_collection_policy)
            self._inventory_generation.reader = inventory_reader
            self._inventory_generation.store = self._inventory_store
            if inventory_reselection_policy is not None:
                self._inventory_service._inventory_generation = self._inventory_generation
            if self._inventory_store is not None:
                self.realm._inventory_broker = self
        if inventory_update_policy is not None:
            self.realm._inventory_update_broker = self
        world_bridge.prepare_inventory(self, world_policy)
        if item_use_policy is not None:
            from tools.local_original_session import item_use_session
            self._item_use_session = item_use_session.ItemUseSession(self, policy=item_use_policy)
            self.realm.bind_item_use_session(self._item_use_session)
        self._item_equipment_effect = None
        self.realm._item_equipment_effect = None
        if item_equipment_policy is not None:
            from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
            self._item_equipment_effect = ItemEquipmentEffect(self, policy=item_equipment_policy,
                                                            first_enable=item_equipment_first_enable)
            self.realm._item_equipment_effect = self._item_equipment_effect
        if item_transfer_policy is not None:
            from tools.local_original_session.item_ground import GroundRegistry
            self._item_ground_registry = GroundRegistry(self)
            self.realm._item_transfer_broker = self

    async def _inventory_before_send(self, writer, row, wire, service, authority, restore_only):
        from tools.local_original_session import inventory
        self._inventory_operation_mode_current(restore_only, writer, row, wire)
        service._same(authority, service._current(writer, row))
        self.inventory_sample_monotonic_ns = self._inventory_admission_time()
        try:
            prepared_wire = service.validate_pre_write_locked(writer, row, wire,
                now_ns=self.inventory_sample_monotonic_ns)
            if self._inventory_collection_policy is not None:
                need(type(prepared_wire) is bytes and prepared_wire is self._inventory_frame
                     and prepared_wire is self._inventory_operation_frame
                     and service._claimed is True
                     and service.last_result.get('status') == 'OBSERVED',
                     'INVENTORY_COLLECTION_EXACT_INITIAL_WIRE_REQUIRED')
                wire = prepared_wire
                self._inventory_selection_frame_current(writer, row, wire)
        except (inventory.PreWriteReadRefusal, inventory.ReadOnlyPreWriteRefusal) as error:
            # Only the original leaf's exact refusal precedes reservation/write.
            readonly = type(error) is inventory.ReadOnlyPreWriteRefusal
            if readonly:
                need(inventory.InventoryService.validate_readonly_refusal(
                    service, error, writer, row, wire) is True,
                    'INVENTORY_READONLY_REFUSAL_UNPROVEN')
            else:
                need(type(error) is inventory.PreWriteReadRefusal
                     and error.reason == 'region_not_readable'
                     and error.stage == service.last_pre_write_stage,
                     'INVENTORY_PRE_WRITE_REFUSAL_UNPROVEN')
            need(row['policy_row'].drain_started_ns is None,
                 'INVENTORY_PRE_WRITE_REFUSAL_UNPROVEN')
            service._same(authority, service._current(writer, row))
            await self._checkpoint(writer, row)
            service._same(authority, service._current(writer, row))
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            self._inventory_operation_mode_current(restore_only, writer, row, wire)
            self._inventory_prewrite_refusal = (error, authority, service,
                                               restore_only, wire)
            self._inventory_admission_time()
            raise
        self._inventory_operation_mode_current(restore_only, writer, row, wire)
        self._inventory_prewrite_refusal = None  # A successful leaf consumes admission.
        self._inventory_admission_time()
        return wire

    def _inventory_send_attempt(self, writer, row, wire, inventory_wire, service, authority,
                                restore_only, update_state, update_request):
        if update_state is not None:
            self._inventory_update_current(writer, row, update_state, update_request)
            need(update_state['phase'] == 'RESERVING' and not update_state['write_attempted']
                 and wire is update_state['wire']
                 and row['policy_row'].pending_opcode == 0x0965
                 and row['policy_row'].pending_size == len(wire)
                 and row['policy_row'].drain_started_ns is not None,
                 'INVENTORY_UPDATE_SINGLE_WRITE_REQUIRED')
            self._inventory_update_time(update_state)
            update_state['phase'], update_state['write_attempted'] = 'WRITE_ATTEMPTED', True
        if inventory_wire:
            # Synchronous policy/source callbacks may cancel without yielding.
            self._inventory_operation_mode_current(restore_only, writer, row, wire)
            service._same(authority, service._current(writer, row))
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        if inventory_wire:
            self._inventory_admission_time()
            self._inventory_write_attempted = True


class RealmInventoryCore:
    """Inventory/session routes on the realm; transport closures only delegate."""
    def bind_item_use_session(self, service):
        from tools.local_original_session.item_use_session import ItemUseSession, POLICY
        need(type(service) is ItemUseSession and service.policy == POLICY
             and service.broker.realm is self and service.broker._item_use_session is service
             and self._item_use_session is None and not self.registry._sessions,
             'ITEM_USE_SAME_REAL_BROKER_SESSION_REQUIRED')
        self._item_use_session = service


    def _replace_item_use_selection(self, broker, writer, old, new):
        """Opt-in same-account/new-selection replacement; ordinary bind stays strict."""
        self._item_use_session = new


    async def _inventory_use_intent(self, writer, payload):
        self.registry.resolve(writer)
        service = self._item_use_session
        need(service is not None and service.broker.realm is self
             and service.broker._item_use_session is service,
             'ITEM_USE_SAME_REAL_BROKER_SESSION_REQUIRED')
        accepted_before = service.accepted_count
        replies = await service.handle(writer, payload)  # Existing _serve row lock, same immutable payload.
        effect = getattr(service.broker, '_item_equipment_effect', None)
        if effect is not None and service.accepted_count == accepted_before + 1:
            ordinal, intent = service.accepted_count, service._current
            # The received request already owns the real row lock. Initial
            # sync may not have reached the feature poll yet; finish it here
            # before consuming this same accepted intent, without re-locking.
            life = getattr(effect, '_selection', None)
            if world_bridge.defer_equipment_prepare(service.broker, life):
                pass
            else:
                initial = await effect.prepare_locked(writer)
                if initial['status'] == 'SYNCHRONIZED':
                    await effect.consume_locked(writer, accepted_ordinal=ordinal, expected_intent=intent)
        need(type(replies) is tuple and replies == (), 'ITEM_USE_INTENT_REPLY_FORBIDDEN')
        return replies

    async def _inventory_transfer(self, writer, payload, *, kind):
        broker = self._item_transfer_broker
        need(broker is not None and broker.realm is self, 'ITEM_TRANSFER_REAL_BROKER_REQUIRED')
        service = broker._inventory_generation.transfer_session
        need(service is not None, 'ITEM_TRANSFER_CURRENT_SELECTED_SESSION_REQUIRED')
        return await service.handle(writer, payload, kind=kind)
