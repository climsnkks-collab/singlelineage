"""Raw current Equipment map data through the owned retained reader.

Schedule instead of another retained sample, <=2 Hz. Call outside the broker
row lock: this observer acquires it. No sender, receipt, native call or UI graph.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import struct
from time import monotonic_ns

from tools.local_original_session import edge, inventory, observe

BYTE_LIMIT = observe.RETAINED_SAMPLE_LIMIT
MIN_INTERVAL_NS = inventory.MIN_INTERVAL_NS
need = inventory.need
SOURCE_PATH = 'work/online_equipment_buff_source/source-contract.json'
SOURCE_PINS = {
    SOURCE_PATH: 'cf2883e8f94e9c7d43ecf6b4a165e8304c56f009242a0b332c471dfb4437d1bb',
    'work/online_equipment_buff_source/row-types.json':
        'd93ef7f6497dd57c202e6554d01cc33c4408868702d2d43b710f76cabdb3a0ab',
    'tools/local_original_session/inventory.py':
        '4d7fd4a32ebe77cf70469c02a481b40f813f9947fdd7dc4015dbbfc53ffb2daf',
    'tools/local_original_session/edge.py':
        'e758a6eb692b44d8bf5742150592ddda8814abda8d58d418c3710d0c42447d28',
}


def _source():
    source = None
    for relative, expected in SOURCE_PINS.items():
        path = observe.ordinary(observe.Path(inventory.__file__) if relative == 'tools/local_original_session/inventory.py'
                                else observe.ROOT / relative)
        need(0 < path.stat().st_size <= 1048576, 'EQUIPMENT_OBSERVE_SOURCE_BOUND')
        raw = path.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == expected, 'EQUIPMENT_OBSERVE_SOURCE_CHANGED')
        if relative == SOURCE_PATH:
            source = json.loads(raw)
    need(source['CONTROL'] == '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
         and source['Equipment']['tree_head'] == 0x3d8
         and source['Equipment']['tree_count'] == 0x3e0
         and source['Equipment']['node_links'] == dict(left=0, parent=8, right=16, sentinel_bool=25)
         and source['Equipment']['record'] == dict(node_key_i32=32, node_value_u64=40, span_bytes=48)
         and source['Equipment']['node_limit'] == 128
         and source['owner_tables']['Equipment']['rva'] == 0x11c6450,
         'EQUIPMENT_OBSERVE_LAYOUT_SOURCE_CHANGED')
    return source, inventory._source()


def _empty(reason):
    return dict(status='UNKNOWN', reason=reason, selected_uid=None, map_id=None,
        entry_count=None, empty=None, rows=[], source_contract_valid=False,
        stable_double_read=False, source_owner_revalidated=False,
        read_consistency='NOT_CLASSIFIED', snapshot_atomic=False,
        equipped_state_proven=False, item_uid_equivalence_proven=False,
        slot_names_proven=False, visible_screen_claimed=False,
        typed_bytes_requested=0, typed_byte_limit=BYTE_LIMIT,
        max_samples_per_second=2, query_started_monotonic_ns=None)


class _ObservationBudget(edge._Budget):
    # Private query-local metadata only. No address or retained byte is output.
    _diagnostic_stage = 0
    _last_span = None

    def read(self, at, size, image=False):
        need(type(size) is int and self.spent + size <= BYTE_LIMIT,
             'EQUIPMENT_OBSERVE_BYTE_BUDGET')
        self._last_span = (at, size, image)
        return super().read(at, size, image)

    def read_failure(self):
        """Locate the last requested span in the ORIGINAL retained records."""
        if self._diagnostic_stage not in (1, 2, 3, 4, 5, 6) or self._last_span is None:
            return {}
        at, size, image = self._last_span
        if type(size) is not int or not 0 < size <= 4096 or type(image) is not bool:
            return {}
        for index, (record_at, raw, record_image) in enumerate(self.records):
            if at == record_at and size == len(raw) and image is record_image:
                return dict(read_stage=self._diagnostic_stage, read_record_index=index,
                    read_width=size, read_image=image)
        return {}


def _pointer(value):
    need(0x10000 <= value <= 0x7fffffffffff and value % 8 == 0,
         'EQUIPMENT_OBSERVE_NONCANONICAL_POINTER')
    return value


def _map(reads, owner, layout):
    """Private source-layout traversal; output contains primitive data only."""
    head, count = struct.unpack('<QQ', reads.read(owner + layout['tree_head'], 16))
    _pointer(head)
    need(count <= layout['node_limit'], 'EQUIPMENT_OBSERVE_NODE_LIMIT')
    leftmost, root, rightmost = struct.unpack('<QQQ', reads.read(head, 24))
    for at in (leftmost, root, rightmost):
        _pointer(at)
    need(reads.read(head + 25, 1) == b'\1', 'EQUIPMENT_OBSERVE_HEAD_SENTINEL')
    if count == 0:
        need(leftmost == root == rightmost == head, 'EQUIPMENT_OBSERVE_EMPTY_LINKS')
        return []
    need(head not in (leftmost, root, rightmost), 'EQUIPMENT_OBSERVE_NONEMPTY_LINKS')
    stack, seen, rows = [(root, head, None, None)], set(), []
    keyed = {}
    while stack:
        node, expected_parent, low, high = stack.pop()
        need(node != head and node not in seen and len(seen) < count,
             'EQUIPMENT_OBSERVE_CYCLE_OR_COUNT')
        seen.add(node)
        left, parent, right = struct.unpack('<QQQ', reads.read(node, 24))
        for at in (left, parent, right):
            _pointer(at)
        need(parent == expected_parent, 'EQUIPMENT_OBSERVE_PARENT_LINK')
        need(reads.read(node + 25, 1) == b'\0', 'EQUIPMENT_OBSERVE_NODE_SENTINEL')
        key = struct.unpack('<i', reads.read(node + 32, 4))[0]
        value = struct.unpack('<Q', reads.read(node + 40, 8))[0]
        need((low is None or low < key) and (high is None or key < high),
             'EQUIPMENT_OBSERVE_KEY_ORDER')
        keyed[node] = key
        rows.append(dict(rawkey_i32=key, value_u64=value))
        if right != head:
            stack.append((right, node, key, high))
        if left != head:
            stack.append((left, node, low, key))
    need(len(seen) == count and leftmost in keyed and rightmost in keyed,
         'EQUIPMENT_OBSERVE_COUNT_OR_EXTREMA')
    rows.sort(key=lambda row: row['rawkey_i32'])
    need(keyed[leftmost] == rows[0]['rawkey_i32']
         and keyed[rightmost] == rows[-1]['rawkey_i32'], 'EQUIPMENT_OBSERVE_EXTREMA')
    return rows


class EquipmentObserver:
    def __init__(self, broker, reader):
        _source()
        self._authority = inventory.InventoryService(broker, reader, policy=inventory.POLICY)
        self._last_ns, self._inflight, self._closed = None, False, False
        self.last_sample_monotonic_ns = None
        self.last_result = _empty('NOT_SAMPLED')

    def close(self):
        self._closed = True
        self._authority.close()

    def _generation(self, broker, reader, writer, row):
        from tools.local_original_session.broker import _InventoryGeneration, PersistentBroker
        generation = broker._inventory_generation
        service = broker._inventory_service
        game = broker.realm.registry.resolve(writer)
        need(type(generation) is _InventoryGeneration and generation.broker is broker
             and generation.phase == 'ACTIVE'
             and row['writer'] is writer and generation.writer is writer
             and generation.row is row and generation.lock is row['operation_lock']
             and generation.game is game and game.selection is not None
             and generation.selected is game.selection
             and type(service) is inventory.InventoryService and service is generation.service
             and not service._closed and service.reader is reader
             and generation.reader is reader and generation.store is broker._inventory_store,
             'EQUIPMENT_OBSERVE_CURRENT_GENERATION_REQUIRED')
        current = broker.inventory_selection_current
        need(getattr(current, '__self__', None) is broker
             and getattr(current, '__func__', None) is PersistentBroker.inventory_selection_current,
             'EQUIPMENT_OBSERVE_ORIGINAL_GENERATION_CHECK_REQUIRED')
        if broker.inventory_reselection_policy is not None:
            need(current(writer) is generation, 'EQUIPMENT_OBSERVE_SELECTED_GENERATION_REQUIRED')
        return generation, service

    async def sample(self, writer, *, now_ns):
        result, budget, entered = _empty('NOT_SAMPLED'), None, False
        try:
            need(not self._closed, 'EQUIPMENT_OBSERVE_CLOSED')
            need(not self._inflight, 'EQUIPMENT_OBSERVE_INFLIGHT')
            need(type(now_ns) is int and 0 <= now_ns < (1 << 63)
                 and (self._last_ns is None or now_ns - self._last_ns >= MIN_INTERVAL_NS),
                 'EQUIPMENT_OBSERVE_CALLER_CADENCE_REQUIRED')
            self._last_ns, self._inflight, entered = now_ns, True, True
            authority = self._authority
            authority._cancelled()
            broker, reader = authority.broker, authority.reader
            claims = [row for rows in broker._claims.values() for row in rows if row['writer'] is writer]
            need(len(claims) == 1, 'EQUIPMENT_OBSERVE_CURRENT_CLAIM_REQUIRED')
            row, = claims
            operation_lock = row['operation_lock']
            async with operation_lock:
                need(row['operation_lock'] is operation_lock, 'EQUIPMENT_OBSERVE_ROW_LOCK_CHANGED')
                generation, service = self._generation(broker, reader, writer, row)
                before = authority._current(writer, row)
                need(await broker._movement_owner(writer, row, before[0]) is True,
                     'EQUIPMENT_OBSERVE_NATIVE_OWNER_REQUIRED')
                # No await between this owner checkpoint and all final rechecks.
                def current():
                    authority._cancelled()
                    need(not self._closed and self._authority is authority
                         and authority.broker is broker and authority.reader is reader,
                         'EQUIPMENT_OBSERVE_PRODUCER_CHANGED')
                    actual_generation, actual_service = self._generation(broker, reader, writer, row)
                    need(actual_generation is generation and actual_service is service,
                         'EQUIPMENT_OBSERVE_GENERATION_CHANGED')
                    authority._same(before, authority._current(writer, row))
                current()
                source, (contract, _, checks) = _source()
                proof = authority.proof
                need(proof.reader is reader, 'EQUIPMENT_OBSERVE_SAME_READER_REQUIRED')
                native, sampler = proof._binding()
                need(native is reader.backend and sampler is reader.sampler,
                     'EQUIPMENT_OBSERVE_SAME_BACKEND_REQUIRED')
                retained = (native, sampler, native.handle)
                current()
                authority._checks(sampler, contract, checks)
                budget = _ObservationBudget(native, sampler)
                query_ns = monotonic_ns()
                need(type(query_ns) is int and 0 <= now_ns <= query_ns < (1 << 63),
                     'EQUIPMENT_OBSERVE_CLOCK_DOMAIN_REQUIRED')
                need(self.last_sample_monotonic_ns is None
                     or query_ns - self.last_sample_monotonic_ns >= MIN_INTERVAL_NS,
                     'EQUIPMENT_OBSERVE_ACTUAL_QUERY_CADENCE_REQUIRED')
                self.last_sample_monotonic_ns = query_ns
                result['query_started_monotonic_ns'] = query_ns
                with budget.installed():
                    budget._diagnostic_stage = 1  # Original world query.
                    position = before[0]
                    reads, _, _, route, state, scene_raw, _ = edge._world(native, sampler,
                        proof.public, proof.world, proof.position_source, position.uid, position.map_id,
                        (position.word0, position.word1), require_current_start=False)
                    budget._diagnostic_stage = 2  # Equipment owner/type/table.
                    table = source['owner_tables']['Equipment']
                    owners = [reads.pair(pair)[0] for pair, vft in route[-2]
                              if vft == sampler.g['base'] + table['rva']]
                    need(len(owners) == 1, 'EQUIPMENT_OBSERVE_UNIQUE_OWNER_REQUIRED')
                    owner, = owners
                    need(reads.pointer(owner) == sampler.g['base'] + table['rva'],
                         'EQUIPMENT_OBSERVE_OWNER_TYPE_CHANGED')
                    proof.world.table(sampler, table)
                    budget._diagnostic_stage = 3  # Original map traversal.
                    rows = _map(reads, owner, source['Equipment'])
                    budget._diagnostic_stage = 4  # Original world.Reads.verify.
                    reads.verify()
                    budget._diagnostic_stage = 5  # Original edge._Budget.verify.
                    budget.verify()
                    budget._diagnostic_stage = 6  # Original final scene/route.
                    budget.retain = False
                    try:
                        need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                             'EQUIPMENT_OBSERVE_WORLD_OWNER_CHANGED')
                    finally:
                        budget.retain = True
                budget._diagnostic_stage = 0  # Installed reads ended; no stale span attribution.
                need(authority.proof is proof and proof._binding() == retained[:2]
                     and native.handle == retained[2], 'EQUIPMENT_OBSERVE_RETAINED_CHANGED')
                current()
                final_source, (contract, _, checks) = _source()
                need(final_source == source, 'EQUIPMENT_OBSERVE_SOURCE_CHANGED')
                authority._checks(sampler, contract, checks)
                current()
                result.update(status='OBSERVED', reason=None, selected_uid=position.uid,
                    map_id=position.map_id, entry_count=len(rows), empty=not rows, rows=rows,
                    source_contract_valid=True, stable_double_read=True,
                    source_owner_revalidated=True, read_consistency='STRICT_STABLE')
        except asyncio.CancelledError:
            result['reason'] = 'EQUIPMENT_OBSERVE_CALLER_CANCELLED'
            self.close()
            raise
        except Exception as error:
            result['reason'] = observe.reason(error)
            if (type(error) is ValueError and error.args == ('EDGE_TYPED_READ_CHANGED',)
                    and budget is not None):
                result.update(budget.read_failure())
        finally:
            if entered:
                self._inflight = False
            result['typed_bytes_requested'] = 0 if budget is None else budget.spent
            self.last_result = result
        return result


SAMPLE_METHOD = EquipmentObserver.sample
CLOSE_METHOD = EquipmentObserver.close
