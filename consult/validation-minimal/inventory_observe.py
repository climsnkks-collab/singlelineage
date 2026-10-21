"""Current Inventory observation, explicit ordered collection opt-in only.

Caller schedules this instead of another retained memory sample, <=2 Hz.
The observer acquires the actual broker row lock. Call it outside that lock.
The last owner-check await precedes one synchronous 16-KiB typed query.
"""
from __future__ import annotations

import asyncio
import struct
import inspect
import sys
from time import monotonic_ns

from tools.local_original_session import edge, inventory, npc_observe, observe

INVENTORY_SOURCE_SHA = '51787127e681eee95b315cab7471828cdb43b6deb75cdfe4da0966bb660c0da7'
COUNT_BUDGET_SOURCE_SHA = 'd436d4c9a12d09d83115f9add1ee256aecf17c04541e8a66449f94b4f01741d3'
BYTE_LIMIT = observe.RETAINED_SAMPLE_LIMIT
MIN_INTERVAL_NS = inventory.MIN_INTERVAL_NS
need = inventory.need


def _source():
    need(observe.digest(observe.ordinary(observe.Path(inventory.__file__)))
         == INVENTORY_SOURCE_SHA, 'INVENTORY_OBSERVE_PARENT_SOURCE_CHANGED')
    need(observe.digest(observe.ordinary(observe.ROOT / 'tools/local_original_session/npc_observe.py'))
         == COUNT_BUDGET_SOURCE_SHA, 'INVENTORY_OBSERVE_COUNT_BUDGET_SOURCE_CHANGED')
    return inventory._source()


def _empty(reason):
    return dict(status='UNKNOWN', reason=reason, selected_uid=None, map_id=None,
        entry_count=None, empty=None, rows=[], source_contract_valid=False,
        stable_double_read=False, snapshot_atomic=False, visible_screen_claimed=False,
        wire_presence_proven=False, all_17_wire_fields_proven=False,
        wire_field18_bytes_observed=False, catalog_live_materialization_proven=False,
        equipped_or_durable_state_proven=False, typed_bytes_requested=0,
        identifier_wire_width_relation='UNKNOWN', query_started_monotonic_ns=None,
        typed_byte_limit=BYTE_LIMIT, max_samples_per_second=2,
        read_consistency='NOT_CLASSIFIED', source_owner_revalidated=False)


class _ObservationBudget(npc_observe._ObservationBudget):
    """Reuse the pinned positive count-only provenance; no extra reads."""
    def read(self, at, size, image=False):
        need(type(size) is int and self.spent + size <= BYTE_LIMIT, 'INVENTORY_OBSERVE_BYTE_BUDGET')
        return super().read(at, size, image)


class InventoryObserver:
    """NPC-independent observation through the real selected broker/reader.

    The private service reuses current authority/source helpers only. Its
    write gate is never called and its one-ADD admission is never consumed.
    Expected frames/values are deliberately absent from this read API.
    """
    def __init__(self, broker, reader, *, collection_policy=None):
        _source()
        need(collection_policy is None or type(collection_policy) is str
             and collection_policy == inventory.COLLECTION_POLICY,
             'INVENTORY_OBSERVE_COLLECTION_EXPLICIT_POLICY_REQUIRED')
        self.collection_policy = collection_policy
        self._collection_current(broker)
        self._authority = inventory.InventoryService(broker, reader, policy=inventory.POLICY)
        self._last_ns, self._inflight, self._closed = None, False, False
        self.last_sample_monotonic_ns = None
        self.last_result = _empty('NOT_SAMPLED')

    def _collection_current(self, broker):
        actual = getattr(broker, '_inventory_collection_policy', None)
        need((self.collection_policy is None and actual is None)
             or (type(self.collection_policy) is str and type(actual) is str
                 and self.collection_policy == actual == inventory.COLLECTION_POLICY),
             'INVENTORY_OBSERVE_COLLECTION_POLICY_CHANGED')

    @staticmethod
    def _row(item):
        fields = dict(item.raw_fields)
        return dict(id_u64=fields[1], template_id_u32=fields[2] & 0xffffffff,
            field18_u64=fields[3],
            field28_i64=fields[4] - (1 << 64) if fields[4] >= 1 << 63 else fields[4],
            field30_bool=fields[24])

    def close(self):
        self._closed = True
        self._authority.close()  # Only the private helper's state; no resource close.

    async def sample_transfer_return(self, writer, *, now_ns, session):
        return await InventoryObserver.sample(self, writer, now_ns=now_ns, transfer_return=session)

    async def sample_transfer_drop(self, writer, *, now_ns, session):
        return await InventoryObserver.sample(self, writer, now_ns=now_ns, transfer_drop=session)

    async def sample_shop_adoption(self, writer, *, now_ns, adoption):
        need(adoption is not None, 'INVENTORY_OBSERVE_EXPLICIT_SHOP_ADOPTION_REQUIRED')
        return await InventoryObserver.sample(self, writer, now_ns=now_ns, shop_adoption=adoption)

    def _shop_adoption_current(self, writer, row, frame, adoption):
        import trade_delivery
        import server_owned_menu as menus
        broker = self._authority.broker
        service = getattr(broker, '_shop_trade_delivery', None)
        need(sys.modules.get('trade_delivery') is trade_delivery
             and observe.digest(observe.ordinary(observe.Path(trade_delivery.__file__)))
                 == 'afcebef885c4d7e6b2ada83df340dfb5dbe0c16a28d95c247a1363ae1b274cf3'
             and type(service) is trade_delivery.Service
             and type(adoption) is trade_delivery.ProjectionAdoption,
             'INVENTORY_OBSERVE_ORIGINAL_SHOP_SERVICE_REQUIRED')
        for name in ('adoption_memory_record', 'validate_adoption'):
            method = getattr(service, name)
            need(inspect.ismethod(method) and method.__self__ is service
                 and method.__func__ is getattr(trade_delivery.Service, name),
                 'INVENTORY_OBSERVE_ORIGINAL_SHOP_METHOD_REQUIRED')
        owner = menus.get_server_menu(broker)
        need(type(owner) is menus.ServerMenuOwner and owner.broker is broker
             and owner.trade.feature is service.feature and owner.provider is broker._canonical_provider
             and service.store.provider is owner.provider and service.feature.broker is broker,
             'INVENTORY_OBSERVE_SHOP_NAMESPACE_REQUIRED')
        binding = owner.provider.bind_selected(writer)
        generation = broker.inventory_selection_current(writer)
        need(binding.writer is writer and binding.generation is generation
             and generation is broker._inventory_generation and generation.phase == 'ACTIVE'
             and generation.writer is writer and generation.row is row
             and row['writer'] is writer and binding.operation_lock is row['operation_lock']
             and generation.lock is binding.operation_lock and generation.lock.locked()
             and generation.game.selection is generation.selected
             and adoption.generation_ref() is generation and adoption.uid == binding.uid
             and adoption.frame is generation.current_frame is frame
             and service.last_adoption is adoption,
             'INVENTORY_OBSERVE_EXACT_SHOP_ADOPTION_REQUIRED')
        # Original menu binding scope owns Store source callbacks. No borrowed
        # binding, source scope or operation survives this synchronous check.
        with owner.binding_scope(binding):
            need(service.adoption_memory_record(adoption) is adoption,
                 'INVENTORY_OBSERVE_ISSUED_SHOP_ADOPTION_REQUIRED')
            need(service.validate_adoption(binding, adoption) is True,
                 'INVENTORY_OBSERVE_CURRENT_SHOP_ADOPTION_REQUIRED')
        need(broker._inventory_generation is generation and generation.current_frame is frame
             and generation.row is row and service.last_adoption is adoption,
             'INVENTORY_OBSERVE_SHOP_ADOPTION_CHANGED')

    async def sample(self, writer, *, now_ns, transfer_return=None, transfer_drop=None, shop_adoption=None):
        transfer_session=transfer_return if transfer_return is not None else transfer_drop
        result = _empty('NOT_SAMPLED')
        budget, entered = None, False
        try:
            need(not self._closed, 'INVENTORY_OBSERVE_CLOSED')
            need(not self._inflight, 'INVENTORY_OBSERVE_INFLIGHT')
            need(type(now_ns) is int and 0 <= now_ns < (1 << 63)
                 and (self._last_ns is None or now_ns - self._last_ns >= MIN_INTERVAL_NS),
                 'INVENTORY_OBSERVE_CALLER_CADENCE_REQUIRED')
            self._last_ns, self._inflight, entered = now_ns, True, True
            authority = self._authority
            authority._cancelled()
            broker = authority.broker
            delivery_service = getattr(broker, '_inventory_service', None)
            delivery = getattr(broker, '_inventory_delivery_authority', None)
            delivery_frame = getattr(broker, '_inventory_frame', None)
            operation_frame = getattr(broker, '_inventory_operation_frame', None)
            selection_binding = getattr(broker, '_inventory_selection_binding', None)
            current_frame = getattr(broker, '_inventory_current_frame', None)
            update_operation = getattr(broker, '_inventory_update_operation', None)
            restore_mode = getattr(broker, '_inventory_restore_only', None)
            collection = self.collection_policy is not None
            self._collection_current(broker)
            generation = getattr(broker, '_inventory_generation', None)
            need(not (transfer_return is not None and transfer_drop is not None),
                 'INVENTORY_OBSERVE_ONE_TRANSFER_PURPOSE_REQUIRED')
            need(transfer_session is None or collection and update_operation is None,
                 'INVENTORY_OBSERVE_RETURN_COLLECTION_NO_UPDATE_REQUIRED')
            need(shop_adoption is None or collection and transfer_session is None and update_operation is None,
                 'INVENTORY_OBSERVE_ONE_SHOP_PURPOSE_REQUIRED')
            expected_rows = None
            if collection:
                need(delivery_service is not None and delivery is not None and type(current_frame) is bytes,
                     'INVENTORY_OBSERVE_COLLECTION_DELIVERY_REQUIRED')
                need(update_operation is None, 'INVENTORY_OBSERVE_COLLECTION_UPDATE_UNSUPPORTED')
                expected_rows = [self._row(item) for item in inventory.validate_current_collection_frame(
                    current_frame, policy=self.collection_policy)]
            return_context = [None]
            def same_delivery(current):
                self._collection_current(broker)
                if collection:
                    from types import MethodType
                    from tools.local_original_session.broker import PersistentBroker
                    method = broker.inventory_selection_current
                    need(type(method) is MethodType and method.__self__ is broker
                         and method.__func__ is PersistentBroker.inventory_selection_current,
                         'INVENTORY_OBSERVE_COLLECTION_ORIGINAL_GENERATION_REQUIRED')
                    need(generation is not None and broker._inventory_generation is generation
                         and method(writer) is generation
                         and generation.phase == 'ACTIVE' and generation.writer is writer
                         and generation.selected is generation.game.selection
                         and generation.service is delivery_service
                         and generation.current_frame is current_frame
                         and generation.frame is delivery_frame
                         and generation.operation_frame is operation_frame
                         and generation.delivery_authority is delivery
                         and generation.selection_binding is selection_binding,
                         'INVENTORY_OBSERVE_COLLECTION_GENERATION_CHANGED')
                if delivery_service is not None:
                    need(broker._inventory_service is delivery_service and not delivery_service._closed
                         and delivery_service._claimed is True
                         and delivery is not None
                         and broker._inventory_delivery_authority is delivery
                         and getattr(broker, '_inventory_selection_binding', None) is selection_binding
                         and type(delivery_frame) is bytes and delivery_frame is operation_frame
                         and getattr(broker, '_inventory_frame', None) is delivery_frame
                         and getattr(broker, '_inventory_operation_frame', None) is operation_frame
                         and type(current_frame) is bytes
                         and getattr(broker, '_inventory_current_frame', None) is current_frame
                         and getattr(broker, '_inventory_update_operation', None) is update_operation
                         and type(restore_mode) is bool
                         and broker._inventory_restore_only is restore_mode,
                         'INVENTORY_OBSERVE_DELIVERY_AUTHORITY_REQUIRED')
                    # The delivered selection/owner stays fixed while normal
                    # movement may replace Position between separate samples.
                    # Within this sample, _same(before, after) stays strict.
                    need(len(delivery[1]) == len(current[1]) == 24
                         and delivery[0] is delivery[1][14]
                         and type(delivery[0]) is inventory.movement.Position
                         and (delivery[0].uid, delivery[0].name, delivery[0].map_id)
                             == (current[0].uid, current[0].name, current[0].map_id)
                         and all(a is b for index, (a, b) in enumerate(zip(delivery[1], current[1]))
                                 if index != 14)
                         and delivery[2] == current[2], 'INVENTORY_AUTHORITY_CHANGED')
                    broker._inventory_selection_frame_current(writer, row, delivery_frame)
                    if update_operation is None:
                        if shop_adoption is not None:
                            InventoryObserver._shop_adoption_current(self, writer, row, current_frame, shop_adoption)
                        elif transfer_session is None:
                            need(current_frame is delivery_frame, 'INVENTORY_OBSERVE_CURRENT_FRAME_UNPROVEN')
                        else:
                            from types import MethodType
                            from tools.local_original_session import item_transfer_session as transfer
                            method=transfer_session.context_locked
                            need(collection and type(transfer_session) is transfer.ItemTransferSession
                                 and generation.transfer_session is transfer_session
                                 and type(method) is MethodType and method.__self__ is transfer_session
                                 and method.__func__ is transfer.ItemTransferSession.context_locked
                                 and observe.digest(observe.ordinary(observe.Path(transfer.__file__))) == 'e1f2ca7ceddaf27e3358b47c9e894385a85dc75951c945bc8b7386aa39a87ce3',
                                 'INVENTORY_OBSERVE_ORIGINAL_RETURN_SESSION_REQUIRED')
                            returned=method(writer)
                            need(transfer_session.phase==('DROPPED' if transfer_drop is not None else 'RETURNED') and transfer_session.pending is None
                                 and not transfer_session.closed and returned.generation is generation
                                 and returned.row is row and returned.store is broker._inventory_store
                                 and returned.current_frame is current_frame and returned.initial_frame is delivery_frame
                                 and ((transfer_drop is None and returned.snapshot.phase=='RETURNED'
                                       and returned.snapshot.owner=='PLAYER' and returned.snapshot.frame_ab==current_frame)
                                      or (transfer_drop is not None and returned.snapshot.phase=='DROPPED'
                                          and returned.snapshot.owner=='GROUND'))
                                 and returned.membership is transfer_session.membership
                                 and returned.membership.phase=='DRAINED',
                                 'INVENTORY_OBSERVE_ACTUAL_RETURN_DRAIN_REQUIRED')
                            if return_context[0] is None:return_context[0]=returned
                            else:transfer.ItemTransferSession._same(return_context[0],returned)
                    else:
                        op = update_operation
                        need(type(op) is dict and type(op['phase']) is str and op['phase'] == 'DRAINED'
                             and op['writer'] is writer and op['row'] is row
                             and op['lock'] is operation_lock and op['new'] is current_frame
                             and type(op['old']) is bytes and type(op['wire']) is bytes
                             and type(op['changes']) is tuple
                             and all(op[key] is True for key in ('persist_attempted', 'persisted',
                                 'write_attempted', 'drain_returned', 'post_owner_verified'))
                             and type(op['sent_before']) is int and 0 <= op['sent_before'] < (1 << 64) - 1
                             and type(op['sent_after']) is int and op['sent_after'] == op['sent_before'] + 1
                             and type(row['policy_row'].sent) is int
                             and row['policy_row'].sent >= op['sent_after'],
                             'INVENTORY_OBSERVE_CURRENT_FRAME_UNPROVEN')
                        expected_refs = (current[1][10], current[1][11], current[1][12], current[1][13],
                            None, current[1][15], delivery_service, authority.reader,
                            getattr(broker, '_inventory_store', None), selection_binding,
                            delivery, delivery_frame, restore_mode)
                        refs, op_authority = op['refs'], op['authority']
                        need(type(refs) is tuple and len(refs) == 13
                             and all(a is b for index, (a, b) in enumerate(zip(refs, expected_refs)) if index != 4)
                             and len(op_authority[1]) == 24
                             and op_authority[0] is op_authority[1][14] is refs[4]
                             and type(refs[4]) is inventory.movement.Position
                             and (refs[4].uid, refs[4].name, refs[4].map_id)
                                 == (current[0].uid, current[0].name, current[0].map_id)
                             and all(a is b for index, (a, b) in enumerate(zip(op_authority[1], current[1]))
                                     if index != 14)
                             and op_authority[2] == current[2], 'INVENTORY_OBSERVE_CURRENT_FRAME_UNPROVEN')
            claims = [r for rows in broker._claims.values() for r in rows if r['writer'] is writer]
            need(len(claims) == 1, 'INVENTORY_OBSERVE_CURRENT_CLAIM_REQUIRED')
            row, = claims
            # Caller does not hold this lock; avoid a second independent lock.
            operation_lock = row['operation_lock']
            # SHOP consumes the actual canonical connection scope; ordinary
            # inventory/transfer/update samples retain their original lock API.
            scope = operation_lock if shop_adoption is None else broker._row_operation(writer, row)
            async with scope:
                need(row['operation_lock'] is operation_lock, 'INVENTORY_OBSERVE_ROW_LOCK_CHANGED')
                before = authority._current(writer, row)
                same_delivery(before)
                need(await broker._movement_owner(writer, row, before[0]) is True,
                     'INVENTORY_OBSERVE_NATIVE_OWNER_REQUIRED')
                # No await from here through authority/source/rechecks/result.
                authority._cancelled()
                after = authority._current(writer, row)
                authority._same(before, after)
                same_delivery(after)
                need(not self._closed, 'INVENTORY_OBSERVE_CLOSED')
                contract, _, core_checks = _source()
                reader, proof = authority.reader, authority.proof
                need(proof.reader is reader, 'INVENTORY_OBSERVE_SAME_READER_REQUIRED')
                native, sampler = proof._binding()
                need(native is reader.backend and sampler is reader.sampler,
                     'INVENTORY_OBSERVE_SAME_BACKEND_REQUIRED')
                after = authority._current(writer, row)
                authority._same(before, after)
                same_delivery(after)
                retained = (native, sampler, native.handle)
                authority._checks(sampler, contract, core_checks)
                budget = _ObservationBudget(native, sampler)
                rows = []
                # Caller now_ns is this host's monotonic_ns call timestamp.
                # Lock/checkpoint waits may delay it; cadence belongs to actual
                # memory query start, not the earlier request timestamp.
                query_ns = monotonic_ns()
                need(type(query_ns) is int and 0 <= now_ns <= query_ns < (1 << 63),
                     'INVENTORY_OBSERVE_CLOCK_DOMAIN_REQUIRED')
                need(self.last_sample_monotonic_ns is None
                     or query_ns - self.last_sample_monotonic_ns >= MIN_INTERVAL_NS,
                     'INVENTORY_OBSERVE_ACTUAL_QUERY_CADENCE_REQUIRED')
                self.last_sample_monotonic_ns = query_ns
                result['query_started_monotonic_ns'] = query_ns
                with budget.installed():
                    position = before[0]
                    reads, _, _, route, state, scene_raw, _ = edge._world(native, sampler,
                        proof.public, proof.world, proof.position_source, position.uid, position.map_id,
                        (position.word0, position.word1), require_current_start=False)
                    table = contract['owners']['Inventory']
                    owners = [reads.pair(pair)[0] for pair, vft in route[-2]
                              if vft == sampler.g['base'] + table['rva']]
                    need(len(owners) == 1, 'INVENTORY_OBSERVE_UNIQUE_OWNER_REQUIRED')
                    owner, = owners
                    need(reads.pointer(owner) == sampler.g['base'] + table['rva'],
                         'INVENTORY_OBSERVE_OWNER_TYPE_CHANGED')
                    proof.world.table(sampler, table)
                    layout = contract['inventory']
                    begin, end, capacity = struct.unpack('<QQQ', reads.read(owner + layout['begin'], 24))
                    need(begin == end == capacity == 0 or
                         (0x10000 <= begin <= end <= capacity <= 0x7fffffffffff
                          and (begin | end | capacity) % 8 == 0
                          and (end - begin) % layout['stride'] == 0
                          and (capacity - begin) % layout['stride'] == 0),
                         'INVENTORY_OBSERVE_CANONICAL_VECTOR_REQUIRED')
                    count = (end - begin) // layout['stride']
                    need(count in ((0, 1, 2) if collection else (0, 1)),
                         'INVENTORY_OBSERVE_EMPTY_OR_TWO_SUBSET' if collection else 'INVENTORY_OBSERVE_EMPTY_OR_ONE_SUBSET')
                    for index in range(count):
                        # A drained ADD does not prove that a row exists. Empty
                        # CLIENT_WAIT reads no cold ItemEntity storage guards.
                        # Full pinned source/layout checks run on both sides;
                        # this query never invokes a native row constructor.
                        item, control = reads.pair(reads.read(begin + index * layout['stride'], layout['stride']))
                        need(item == control + layout['row_equals_control_plus'],
                             'INVENTORY_OBSERVE_ITEM_SHARED_LAYOUT')
                        control_table = contract['inventory_control']
                        need(reads.pointer(control) == sampler.g['base'] + control_table['rva']
                             and reads.pointer(item + layout['row_self_pointer']) == item,
                             'INVENTORY_OBSERVE_ITEM_CONTROL_OR_SELF')
                        proof.world.table(sampler, control_table)
                        fields = (('id_u64', 'row_id_u64', '<Q', 8),
                                  ('template_id_u32', 'row_template_id_u32', '<I', 4),
                                  ('field18_u64', 'row_field18_u64', '<Q', 8),
                                  ('field28_i64', 'row_quantity_i64', '<q', 8),
                                  ('field30_bool', 'row_field30_bool', '<B', 1))
                        values = {name: struct.unpack(fmt, reads.read(item + layout[key], width))[0]
                                  for name, key, fmt, width in fields}
                        need(values['id_u64'] <= 0xffffffff,
                             'INVENTORY_OBSERVE_IDENTIFIER_ZERO_EXTENSION_CONTRADICTION')
                        need(values['field30_bool'] in (0, 1), 'INVENTORY_OBSERVE_NONCANONICAL_BOOL')
                        values['field30_bool'] = bool(values['field30_bool'])
                        # All names retain host storage meaning. In particular
                        # field18_u64 is Row+18 / wire f3, not wire f18 bytes.
                        rows.append(values)
                    if collection:
                        need(len({row['id_u64'] for row in rows}) == count,
                             'INVENTORY_OBSERVE_COLLECTION_DUPLICATE_UID')
                        if transfer_session is None and shop_adoption is None:
                            need(count == len(expected_rows), 'INVENTORY_OBSERVE_COLLECTION_INCOMPLETE')
                            need(rows == expected_rows, 'INVENTORY_OBSERVE_COLLECTION_ITEM_MISMATCH')
                    reads.verify()
                    budget.verify()
                    budget.retain = False
                    try:
                        need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                             'INVENTORY_OBSERVE_WORLD_OWNER_CHANGED')
                    finally:
                        budget.retain = True
                need(self._authority is authority and authority.broker is broker
                     and authority.reader is reader and authority.proof is proof,
                     'INVENTORY_OBSERVE_PRODUCER_CHANGED')
                need(proof._binding() == retained[:2] and native.handle == retained[2],
                     'INVENTORY_OBSERVE_RETAINED_CHANGED')
                after = authority._current(writer, row)
                authority._same(before, after)
                same_delivery(after)
                if budget.instability_origins:
                    # Only the actual drained broker operation supplies the
                    # expected row. A count marker cannot hide a value mismatch.
                    need(delivery_service is not None and delivery is not None
                         and type(current_frame) is bytes,
                         'EDGE_TYPED_READ_CHANGED')
                    if collection:
                        need(rows == expected_rows, 'FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH')
                    else:
                        fields = dict(inventory.validate_frame(current_frame).raw_fields)
                        expected = dict(id_u64=fields[1], template_id_u32=fields[2] & 0xffffffff,
                            field18_u64=fields[3],
                            field28_i64=fields[4] - (1 << 64) if fields[4] >= 1 << 63 else fields[4],
                            field30_bool=fields[24])
                        need(count == 0 or rows == [expected], 'FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH')
                contract, _, core_checks = _source()
                authority._checks(sampler, contract, core_checks)
                authority._cancelled()
                need(not self._closed, 'INVENTORY_OBSERVE_CLOSED')
                if budget.instability_origins:
                    origin = ('BOTH' if len(budget.instability_origins) == 2
                              else next(iter(budget.instability_origins)))
                    result.update(reason='EDGE_TYPED_READ_CHANGED', source_owner_revalidated=True,
                        read_consistency='RECHECKED_SHARED_COUNT_' + origin)
                    return result
                if shop_adoption is not None and rows != expected_rows:
                    # DRAINED is transport history. Only this strict current
                    # native read can decide whether the client consumed it.
                    result.update(status='PENDING', reason='INVENTORY_OBSERVE_SHOP_ROWS_PENDING',
                        selected_uid=before[0].uid, map_id=before[0].map_id, entry_count=count,
                        empty=count==0, rows=rows, source_contract_valid=True,
                        stable_double_read=True, source_owner_revalidated=True,
                        read_consistency='STRICT_STABLE')
                    return result
                if transfer_session is not None and rows != expected_rows:
                    result.update(status='PENDING',reason='INVENTORY_OBSERVE_DROP_ROWS_PENDING' if transfer_drop is not None else 'INVENTORY_OBSERVE_RETURN_ROWS_PENDING',
                        selected_uid=before[0].uid,map_id=before[0].map_id,entry_count=count,empty=count==0,rows=rows,
                        source_contract_valid=True,stable_double_read=True,source_owner_revalidated=True,
                        read_consistency='STRICT_STABLE')
                    return result
                pending_reason = None
                if delivery_service is not None and update_operation is not None and count == 1:
                    old_fields = dict(inventory.validate_frame(update_operation['old']).raw_fields)
                    new_fields = dict(inventory.validate_frame(current_frame).raw_fields)
                    if (update_operation['changes'] == ((4, new_fields[4]),)
                            and old_fields[1] == new_fields[1]
                            and {key for key in old_fields if old_fields[key] != new_fields[key]} == {4}):
                        previous = dict(id_u64=old_fields[1], template_id_u32=old_fields[2] & 0xffffffff,
                            field18_u64=old_fields[3], field28_i64=old_fields[4] - (1 << 64)
                                if old_fields[4] >= 1 << 63 else old_fields[4], field30_bool=old_fields[24])
                        if rows == [previous]:
                            pending_reason = 'INVENTORY_OBSERVE_PREVIOUS_FIELD4_PENDING'
                result.update(status='OBSERVED', reason=pending_reason, selected_uid=before[0].uid,
                    map_id=before[0].map_id, entry_count=count, empty=count == 0, rows=rows,
                    source_contract_valid=True, stable_double_read=True,
                    read_consistency='STRICT_STABLE', source_owner_revalidated=True,
                    identifier_wire_width_relation='U32_ZERO_EXTENDED_QWORD_STORE' if count else 'NOT_APPLICABLE_EMPTY')
        except asyncio.CancelledError:
            result['reason'] = 'INVENTORY_OBSERVE_CALLER_CANCELLED'
            self.close()
            raise
        except Exception as error:
            result['reason'] = observe.reason(error)
        finally:
            if entered:
                self._inflight = False
            result['typed_bytes_requested'] = 0 if budget is None else budget.spent
            self.last_result = result
        return result
