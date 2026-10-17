"""Real NPC-free broker/reader/source guards with saved-record memory only."""
import asyncio
from dataclasses import replace
import struct
import time
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_observe as n, inventory_tests, observe


class ObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_delivery_uses_original_authority_and_unconfigured_observation_is_unchanged(self):
        # Default standalone observation is still available without a sender.
        self.assertEqual((await self.sample())['status'], 'OBSERVED')
        self.producer._inventory_service = self.service
        self.producer._inventory_delivery_authority = None
        calls = len(self.memory.calls)
        self.assertEqual((await self.sample())['reason'], 'INVENTORY_OBSERVE_DELIVERY_AUTHORITY_REQUIRED')
        self.assertEqual(len(self.memory.calls), calls)
        await self.delivered(one=False)  # Synthetic read fixture, not a drain proof.
        self.assertEqual((await self.sample())['status'], 'OBSERVED')
        calls = len(self.memory.calls)
        movement = self.realm.service(self.writer)
        movement._position = replace(movement.snapshot())  # Same values, a new actual authority object.
        self.assertEqual((await self.sample())['status'], 'OBSERVED')
        self.assertGreater(len(self.memory.calls), calls)

    async def asyncSetUp(self):
        await inventory_tests.GateTests.asyncSetUp(self)
        self.observer = n.InventoryObserver(self.producer, self.reader)
        self.checkpoints = 0
        async def sample(row):
            self.checkpoints += 1
            self.assertTrue(row['operation_lock'].locked())
            return inventory_tests.b.OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                row['policy_row'].peer, time.monotonic_ns(), True, True)
        self.producer._sample = sample
        self.now_ns = 0
        self.query_ns = 0
        self.clock_patch = patch.object(n, 'monotonic_ns', lambda: self.query_ns)
        self.clock_patch.start(); self.addCleanup(self.clock_patch.stop)

    def one(self):
        layout, _, _ = inventory._source()
        layout = layout['inventory']
        self.item, self.control, self.vector = 0x510010, 0x510000, 0x500000
        contract, _, _ = inventory._source()
        self.memory.put(self.memory.header, '<QQQ', self.vector, self.vector + 16, self.vector + 64)
        self.memory.put(self.vector, '<QQ', self.item, self.control)
        self.memory.put(self.control, '<Q', self.memory.base + contract['inventory_control']['rva'])
        self.memory.put(self.control + 8, '<i', 4)
        self.memory.put(self.item, '<Q', self.item)
        for key, fmt, value in (('row_id_u64', '<Q', 0xffffffff),
                ('row_template_id_u32', '<I', 0x80000001), ('row_field18_u64', '<Q', (1 << 64) - 1),
                ('row_quantity_i64', '<q', -(1 << 63)), ('row_field30_bool', '<B', 1)):
            self.memory.put(self.item + layout[key], fmt, value)

    async def sample(self):
        self.now_ns += n.MIN_INTERVAL_NS
        self.query_ns += n.MIN_INTERVAL_NS
        claimed = self.service._claimed
        try:
            result = await self.observer.sample(self.writer, now_ns=self.now_ns)
        finally:
            self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
            self.assertNotIn('read', self.memory.s.__dict__)
            self.assertNotIn('strong_pair', self.memory.s.__dict__)
            self.assertFalse(self.row['operation_lock'].locked())
            self.assertIs(self.service._claimed, claimed)
            self.assertFalse(self.observer._authority._claimed)
            self.writer.write.assert_not_called(); self.assertEqual(self.writer.drain.await_count, 0)
        return result

    async def delivered(self, *, one=True):
        # Synthetic delivery bookkeeping used only by legacy read-counter
        # counterexamples. Real Add/drain coverage lives in CurrentFrameTests.
        self.producer._inventory_service = self.service
        self.producer._inventory_frame = self.wire
        self.producer._inventory_operation_frame = self.wire
        self.producer._inventory_current_frame = self.wire
        self.service._claimed = True
        async with self.row['operation_lock']:
            self.producer._inventory_delivery_authority = self.service._current(self.writer, self.row)
        if one:
            self.one()
            fields = dict(inventory.validate_frame(self.wire).raw_fields)
            self.memory.put(self.item + 0x10, '<I', fields[2] & 0xffffffff)
            self.memory.put(self.item + 0x30, '<B', fields[24])

    async def test_count_only_incomplete_requires_delivery_and_all_original_checks(self):
        original_verify = n._ObservationBudget.verify
        metrics = []
        for one in (False, True):
            await self.delivered(one=one)
            for origin in ('INITIAL_DUPLICATE', 'FINAL_READBACK'):
                phase, hits = [False], [0]
                def verify(budget):
                    phase[0] = True
                    try: return original_verify(budget)
                    finally: phase[0] = False
                def fault(at, size, raw):
                    if at == 0x250008 and size == 4:
                        hits[0] += 1
                        if (origin == 'INITIAL_DUPLICATE' and hits[0] == 2) or (origin == 'FINAL_READBACK' and phase[0]):
                            return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
                    return raw
                self.memory.fault = fault
                before = len(self.memory.calls)
                with patch.object(n._ObservationBudget, 'verify', verify): result = await self.sample()
                self.assertEqual((result['status'], result['reason'], result['read_consistency']),
                    ('UNKNOWN', 'EDGE_TYPED_READ_CHANGED', 'RECHECKED_SHARED_COUNT_' + origin), result)
                self.assertTrue(result['source_owner_revalidated'])
                self.assertFalse(result['source_contract_valid'] or result['stable_double_read'])
                self.assertEqual((result['entry_count'], result['empty'], result['rows']), (None, None, []))
                self.assertEqual(result['typed_bytes_requested'], 2084 if one else 1857)
                self.assertEqual(result['typed_bytes_requested'], sum(size for _, size in self.memory.calls[before:]))
                metrics.append((one, origin, result['typed_bytes_requested']))
        # Standalone strict observation survives; no delivery cannot authorize
        # a count-only wait marker, even when all memory reads complete.
        self.producer._inventory_service = None
        hits = [0]
        def drift(at, size, raw):
            if at == 0x250008 and size == 4:
                hits[0] += 1
                if hits[0] == 2: return struct.pack('<i', 5)
            return raw
        self.memory.fault = drift
        result = await self.sample()
        self.assertEqual((result['read_consistency'], result['source_owner_revalidated']), ('NOT_CLASSIFIED', False))
        self.memory.fault = None
        result = await self.sample()
        self.assertEqual((result['status'], result['read_consistency']), ('OBSERVED', 'STRICT_STABLE'))
        print('inventory_count_only_incomplete=' + str(metrics))

    async def test_count_drift_never_hides_five_stable_wrong_item_values(self):
        await self.delivered()
        saved = dict(self.memory.data)
        for offset, fmt, value in ((8, '<Q', 7), (0x10, '<I', 2), (0x18, '<Q', 3),
                                   (0x28, '<q', 4), (0x30, '<B', 1)):
            self.memory.data = dict(saved)
            self.memory.put(self.item + offset, fmt, value)
            hits = [0]
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == 2: return struct.pack('<i', 5)
                return raw
            self.memory.fault = fault
            result = await self.sample()
            self.assertEqual((result['status'], result['reason'], result['read_consistency']),
                ('UNKNOWN', 'FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH', 'NOT_CLASSIFIED'), result)
            self.assertFalse(result['source_owner_revalidated'] or result['stable_double_read'])
            self.assertEqual(result['rows'], [])
            # With no drift, raw observation remains visible for the original
            # launcher mismatch check; this reader does not require an expected row.
            self.memory.fault = None
            strict = await self.sample()
            self.assertEqual(strict['status'], 'OBSERVED')
            self.assertEqual(len(strict['rows']), 1)
        self.memory.data = saved
        print('inventory_count_drift_expected5_mismatches=5; strict_wrong5_raw_preserved=5')

    async def test_count_marker_is_discarded_on_semantic_source_owner_delivery_or_read_failure(self):
        await self.delivered()
        saved, selected = dict(self.memory.data), dict(self.realm.registry.selected)
        authority, proof = self.observer._authority, self.observer._authority.proof
        original_broker, original_process = authority.broker, self.reader.member.process
        original_frame, source_pin = self.producer._inventory_frame, n.COUNT_BUDGET_SOURCE_SHA
        contract, _, core = inventory._source()
        code_at = self.memory.base + contract['owners']['Inventory']['rva']
        cases = ('uid', 'pointer', 'image', 'selection', 'owner', 'frame', 'operation_frame',
                 'proof', 'authority', 'broker', 'source', 'scalar_drift', 'physical')
        for case in cases:
            hits, scalar_hits = [0], [0]
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == 2:
                        if case == 'uid': self.memory.put(self.memory.player + 24, '<Q', 999)
                        elif case == 'pointer': self.memory.put(self.vector, '<QQ', self.item + 8, self.control)
                        elif case == 'image': self.memory.put(code_at, '<B', self.memory.read(code_at, 1)[0] ^ 1)
                        elif case == 'selection': self.realm.registry.selected.clear()
                        elif case == 'owner': self.reader.member.process = object()
                        elif case == 'frame': self.producer._inventory_frame = bytes(bytearray(original_frame))
                        elif case == 'operation_frame': self.producer._inventory_operation_frame = bytes(bytearray(original_frame))
                        elif case == 'proof': authority.proof = type(proof)(self.reader)
                        elif case == 'authority': self.observer._authority = inventory.InventoryService(self.producer, self.reader, policy=inventory.POLICY)
                        elif case == 'broker': authority.broker = object()
                        elif case == 'source': n.COUNT_BUDGET_SOURCE_SHA = '0' * 64
                        return struct.pack('<i', 5)
                if case == 'scalar_drift' and at == self.item + 24:
                    scalar_hits[0] += 1
                    if scalar_hits[0] == 2: return bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            original_query = self.native.k.VirtualQueryEx
            def physical(handle, at, info, size):
                result = original_query(handle, at, info, size)
                if case == 'physical' and hits[0] >= 2 and at == self.item + 24: info._obj.protect = 1
                return result
            self.memory.fault, self.native.k.VirtualQueryEx = fault, physical
            try:
                result = await self.sample()
                self.assertEqual((result['status'], result['read_consistency'], result['rows']),
                                 ('UNKNOWN', 'NOT_CLASSIFIED', []), (case, result))
                self.assertFalse(result['source_owner_revalidated'] or result['source_contract_valid'])
            finally:
                self.native.k.VirtualQueryEx = original_query
                self.memory.data = dict(saved)
                self.realm.registry.selected.clear(); self.realm.registry.selected.update(selected)
                self.reader.member.process = original_process
                self.observer._authority, authority.proof, authority.broker = authority, proof, original_broker
                self.producer._inventory_frame = self.producer._inventory_operation_frame = original_frame
                n.COUNT_BUDGET_SOURCE_SHA = source_pin
                self.memory.fault = None
        for changed in (0, -1, None):
            hits = [0]
            def invalid_count(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == 2: return raw[:-1] if changed is None else struct.pack('<i', changed)
                return raw
            self.memory.fault = invalid_count
            result = await self.sample()
            self.assertEqual((result['read_consistency'], result['source_owner_revalidated']), ('NOT_CLASSIFIED', False))
            self.assertEqual(result['rows'], [])
        self.memory.fault = None
        print('inventory_count_marker_hard_refusals=' + str(len(cases) + 3))

    async def test_reused_budget_mixed_role_count_cannot_be_incomplete(self):
        raw_pair = struct.pack('<QQ', self.memory.player, 0x250000)
        for drift_first in (False, True):
            budget = n._ObservationBudget(self.native, self.memory.s)
            hits = [0]
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == (2 if drift_first else 3): return struct.pack('<i', 5)
                return raw
            self.memory.fault = fault
            with budget.installed():
                self.memory.s.strong_pair(raw_pair)
                if drift_first:
                    self.memory.s.strong_pair(raw_pair)
                    with self.assertRaisesRegex(ValueError, 'EDGE_TYPED_READ_CHANGED'):
                        self.memory.s.read(0x250008, 4)
                else:
                    self.memory.s.read(0x250008, 4)
                    with self.assertRaisesRegex(ValueError, 'EDGE_TYPED_READ_CHANGED'):
                        self.memory.s.strong_pair(raw_pair)
            self.assertNotIn('read', self.memory.s.__dict__)
            self.assertNotIn('strong_pair', self.memory.s.__dict__)
        self.memory.fault = None

    async def test_source_guard_empty_exact_one_host_bits_and_no_send_admission(self):
        first = await self.sample()
        self.assertEqual(first['status'], 'OBSERVED', first)
        self.assertEqual((first['entry_count'], first['empty'], first['rows']), (0, True, []))
        empty_bytes = first['typed_bytes_requested']
        self.memory.calls.clear()
        self.one()
        row = await self.sample()
        self.assertEqual(row['status'], 'OBSERVED', row)
        self.assertEqual((row['entry_count'], row['empty']), (1, False))
        self.assertEqual(row['rows'], [dict(id_u64=0xffffffff, template_id_u32=0x80000001,
            field18_u64=(1 << 64) - 1, field28_i64=-(1 << 63), field30_bool=True)])
        self.assertTrue(row['source_contract_valid'] and row['stable_double_read'])
        self.assertEqual(row['typed_bytes_requested'], sum(size for _, size in self.memory.calls))
        self.assertLessEqual(row['typed_bytes_requested'], 16384)
        self.assertEqual(self.checkpoints, 2)
        self.assertFalse(row['wire_presence_proven'] or row['all_17_wire_fields_proven']
                         or row['wire_field18_bytes_observed'] or row['visible_screen_claimed'])
        self.assertEqual(row['identifier_wire_width_relation'], 'U32_ZERO_EXTENDED_QWORD_STORE')
        print('inventory_observe_positive_bytes=' + str(dict(empty=empty_bytes, exact_one=row['typed_bytes_requested'])))
        # This observer reports host bits rather than applying the sender's
        # template membership/value policy to actual observed client memory.
        self.memory.put(self.item + 8, '<Q', 0)
        self.assertEqual((await self.sample())['rows'][0]['id_u64'], 0)

    async def test_passive_getter_unreadable_is_not_queried_for_empty_or_one(self):
        contract, _, core = inventory._source()
        checks = self.observer._authority._checks(self.memory.s, contract, core)
        getters = set(inventory.INVENTORY_SOURCE_ROLES['registered_getter'])
        self.assertFalse(getters & set(r['rva'] for r in checks))
        self.assertEqual(len(checks), 49)
        original_query = self.native.k.VirtualQueryEx
        self.addCleanup(setattr, self.native.k, 'VirtualQueryEx', original_query)
        requested = []
        def getter_pages_unreadable(handle, at, info, size):
            result = original_query(handle, at, info, size)
            requested.append(at - self.memory.base)
            if 0x77000 <= at - self.memory.base < 0x78000: info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = getter_pages_unreadable
        empty = await self.sample()
        self.assertEqual((empty['status'], empty['entry_count'], empty['typed_bytes_requested']), ('OBSERVED', 0, 1857))
        self.assertFalse(set(inventory.INVENTORY_SOURCE_ROLES['item_storage']) & set(requested))
        self.one(); self.memory.calls.clear()
        one = await self.sample()
        self.assertEqual((one['status'], one['entry_count'], one['typed_bytes_requested']), ('OBSERVED', 1, 2084))
        self.assertEqual(sum(size for _, size in self.memory.calls), 2084)
        self.assertFalse(getters & set(requested))
        self.assertEqual(one['identifier_wire_width_relation'], 'U32_ZERO_EXTENDED_QWORD_STORE')
        print('inventory_passive_source_descriptors=49+11; codebody_queries=0; getter_reads=0; empty_bytes=1857; exact_one_bytes=2084')

    async def test_query_guards_keep_item_storage_proof_and_exclude_other_handlers(self):
        contract, _, core = inventory._source()
        checks = self.observer._authority._checks(self.memory.s, contract, core)
        selected = set(inventory.INVENTORY_SOURCE_ROLES['item_storage'])
        all_inventory = set(rva for rows in inventory.INVENTORY_SOURCE_ROLES.values() for rva in rows)
        self.assertEqual(len(selected), 11)
        self.assertEqual(len(checks), 49)
        self.assertEqual(set(r['rva'] for r in checks) & all_inventory, set())
        self.assertTrue({0x509507, 0x50950a} <= selected)
        original_query = self.native.k.VirtualQueryEx
        self.addCleanup(setattr, self.native.k, 'VirtualQueryEx', original_query)
        requested = []
        def no_other_handlers(handle, at, info, size):
            result = original_query(handle, at, info, size)
            requested.append(at - self.memory.base)
            if at - self.memory.base in all_inventory - set(): info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = no_other_handlers
        empty = await self.sample()
        self.assertEqual((empty['status'], empty['entry_count'], empty['typed_bytes_requested']), ('OBSERVED', 0, 1857))
        self.assertFalse(set(requested) & (all_inventory - set()))
        code = all_inventory | {r['rva'] for r in checks}
        def no_unconsumed_handlers(handle, at, info, size):
            result = original_query(handle, at, info, size)
            requested.append(at - self.memory.base)
            if at - self.memory.base in code: info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = no_unconsumed_handlers
        self.one(); self.memory.calls.clear()
        one = await self.sample()
        self.assertEqual((one['status'], one['entry_count'], one['typed_bytes_requested']), ('OBSERVED', 1, 2084))
        self.assertEqual(one['typed_bytes_requested'], sum(size for _, size in self.memory.calls))
        self.assertFalse(set(requested) & code)
        self.native.k.VirtualQueryEx = original_query
        counterexamples = 0
        original_data = dict(self.memory.data)
        original_flag = self.memory.c['runtime_cause_proven']
        table = self.memory.base + contract['inventory_control']['rva']
        for mode in ('cache_before', 'cache_after', 'source', 'table_page', 'row_page', 'row_bool', 'row_readback'):
            self.memory.data = dict(original_data)
            if mode == 'cache_before': self.memory.c['runtime_cause_proven'] = 0
            elif mode == 'cache_after':
                def changed_cache(at, size, raw):
                    if at == self.item + 8: self.memory.c['runtime_cause_proven'] = 0
                    return raw
                self.memory.fault = changed_cache
            elif mode in ('table_page', 'row_page'):
                target = table if mode == 'table_page' else self.item + 8
                def unreadable(handle, at, info, size):
                    result = original_query(handle, at, info, size)
                    if at == target: info._obj.protect = 1
                    return result
                self.native.k.VirtualQueryEx = unreadable
            elif mode == 'row_bool': self.memory.put(self.item + 0x30, '<B', 2)
            elif mode == 'row_readback':
                hits = [0]
                def changed_row(at, size, raw):
                    if at == self.item + 8:
                        hits[0] += 1
                        if hits[0] == 2: return raw[:-1] + bytes([raw[-1] ^ 1])
                    return raw
                self.memory.fault = changed_row
            pins = dict(inventory.SOURCE_PINS)
            if mode == 'source': pins[inventory.PROOF] = '0' * 64
            with patch.object(inventory, 'SOURCE_PINS', pins): result = await self.sample()
            self.assertEqual((result['status'], result['rows']), ('UNKNOWN', []), result)
            if mode.startswith('cache'): self.assertEqual(result['reason'], 'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED')
            if mode.endswith('page'): self.assertEqual(result['reason'], 'region_not_readable')
            counterexamples += 1
            self.native.k.VirtualQueryEx = original_query
            self.memory.fault = None
            self.memory.c['runtime_cause_proven'] = original_flag
        self.memory.data = original_data
        print('inventory_source_descriptors=49+11; codebody_queries=0; empty_bytes=1857; exact_one_bytes=2084; source_cache_live_refusals=' + str(counterexamples))

    async def test_item_pair_type_self_strong_bool_width_and_multirow_refuse(self):
        self.one()
        original = dict(self.memory.data)
        mutations = [lambda: self.memory.put(self.vector, '<QQ', self.item + 8, self.control),
            lambda: self.memory.put(self.control, '<Q', self.memory.base + 0x11819f0),
            lambda: self.memory.put(self.item, '<Q', self.item + 16),
            lambda: self.memory.put(self.control + 8, '<i', 0),
            lambda: self.memory.put(self.item + 48, '<B', 2),
            lambda: self.memory.put(self.item + 8, '<Q', 1 << 32),
            lambda: self.memory.put(self.memory.header, '<QQQ', self.vector, self.vector + 32, self.vector + 64)]
        for mutation in mutations:
            self.memory.data = dict(original); mutation()
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertIsNone(row['entry_count']); self.assertIsNone(row['empty'])
            self.assertEqual(row['rows'], [])
        self.memory.data = dict(original)
        self.assertEqual((await self.sample())['status'], 'OBSERVED')

    async def test_source_scalar_header_partial_and_budget_recheck_refuse(self):
        self.one()
        contract, _, core = inventory._source()
        code_at = self.memory.base + contract['owners']['Inventory']['rva']
        for at_target, hit, partial in ((code_at, 1, False), (code_at, 2, False),
                (self.item + 24, 2, False), (self.memory.header, 2, False), (self.vector, 1, True)):
            hits = [0]
            def fault(at, size, raw):
                if at == at_target:
                    hits[0] += 1
                    if hits[0] == hit:
                        return raw[:-1] if partial else bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            self.memory.fault = fault
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertEqual(row['rows'], [])
            self.assertFalse(row['source_contract_valid'])
        self.memory.fault = None
        with patch.object(n, 'BYTE_LIMIT', 100):
            row = await self.sample()
            self.assertEqual(row['reason'], 'INVENTORY_OBSERVE_BYTE_BUDGET')
            self.assertLessEqual(row['typed_bytes_requested'], 100)
        self.assertEqual((await self.sample())['status'], 'OBSERVED')

    async def test_checkpoint_selection_identity_and_native_failure_before_reads(self):
        original_sample = self.producer._sample
        original_registry = self.realm.registry
        selection = dict(original_registry.selected)
        service = self.realm.service(self.writer)
        position = service.snapshot()
        mutations = [lambda: original_registry.selected.clear(),
                     lambda: setattr(service, '_position', replace(position))]
        for mutation in mutations:
            async def changed(row):
                result = await original_sample(row); mutation(); return result
            self.producer._sample = changed
            calls = len(self.memory.calls)
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertEqual(len(self.memory.calls), calls)
            original_registry.selected.update(selection); service._position = position
        async def refused(row):
            raise ValueError('CURRENT_OWNER_REQUIRED')
        self.producer._sample = refused
        self.assertEqual((await self.sample())['status'], 'UNKNOWN')
        self.producer._sample = original_sample
        self.assertEqual((await self.sample())['status'], 'OBSERVED')

    async def test_registry_member_source_and_original_method_loss_during_query_refuse(self):
        self.one()
        registry, member = self.realm.registry, self.reader.member
        replacement = type(registry)()
        replacement._sessions, replacement.selected = dict(registry._sessions), dict(registry.selected)
        for mutate in (lambda: setattr(self.realm, 'registry', replacement),
                       lambda: setattr(member, 'process', object())):
            fired = [False]
            def fault(at, size, raw):
                if at == self.item + 8 and not fired[0]: fired[0] = True; mutate()
                return raw
            self.memory.fault = fault
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertEqual(row['rows'], [])
            self.realm.registry, member.process = registry, self.policy.handle
        self.memory.fault = None
        self.memory.s.route = lambda: ()
        self.assertEqual((await self.sample())['status'], 'UNKNOWN')
        del self.memory.s.route
        with patch.object(n, 'INVENTORY_SOURCE_SHA', '0' * 64):
            self.assertEqual((await self.sample())['reason'], 'INVENTORY_OBSERVE_PARENT_SOURCE_CHANGED')
        self.assertEqual((await self.sample())['status'], 'OBSERVED')

    async def test_cadence_and_close_are_read_only_and_do_not_close_caller_resources(self):
        self.assertEqual((await self.sample())['status'], 'OBSERVED')
        calls = len(self.memory.calls)
        for now in (self.now_ns, self.now_ns - 1, True, -1):
            row = await self.observer.sample(self.writer, now_ns=now)
            self.assertEqual(row['status'], 'UNKNOWN')
            self.assertEqual(row['typed_bytes_requested'], 0)
        self.assertEqual(len(self.memory.calls), calls)
        self.observer.close()
        self.assertEqual((await self.sample())['reason'], 'INVENTORY_OBSERVE_CLOSED')
        self.assertFalse(self.reader.closed or self.reader.owner.closed)
        self.assertEqual(self.policy.state, 'OPEN')
        self.assertIs(self.producer.realm, self.realm)

    async def test_actual_query_cadence_after_checkpoint_delay_and_clock_domain(self):
        original_sample = self.producer._sample
        async def delayed(row):
            sample = await original_sample(row)
            self.query_ns = 2_000_000_000
            return sample
        self.producer._sample = delayed
        first = await self.sample()  # caller500ms, actual query starts2s
        self.assertEqual(first['status'], 'OBSERVED', first)
        self.assertEqual(self.observer.last_sample_monotonic_ns, 2_000_000_000)
        async def too_soon(row):
            sample = await original_sample(row)
            self.query_ns = 2_100_000_000
            return sample
        self.producer._sample = too_soon
        calls = len(self.memory.calls)
        second = await self.sample()  # caller1s, query only100ms after first
        self.assertEqual(second['reason'], 'INVENTORY_OBSERVE_ACTUAL_QUERY_CADENCE_REQUIRED')
        self.assertEqual(second['typed_bytes_requested'], 0)
        self.assertEqual(len(self.memory.calls), calls)
        self.assertEqual(self.observer.last_sample_monotonic_ns, 2_000_000_000)
        self.producer._sample = original_sample
        self.query_ns = 2_000_000_000
        self.assertEqual((await self.sample())['status'], 'OBSERVED')  # actual2.5s
        self.query_ns = 0
        bad_clock = await self.sample()
        self.assertEqual(bad_clock['reason'], 'INVENTORY_OBSERVE_CLOCK_DOMAIN_REQUIRED')
        self.assertEqual(bad_clock['typed_bytes_requested'], 0)

    async def test_row_lock_replaced_while_waiting_refuses_before_query_start(self):
        old_lock = self.row['operation_lock']
        replacement = asyncio.Lock()
        await old_lock.acquire()
        await replacement.acquire()
        task = asyncio.create_task(self.observer.sample(self.writer, now_ns=0))
        try:
            await asyncio.sleep(0)  # Only yield: sample is waiting on old_lock.
            self.assertFalse(task.done())
            self.row['operation_lock'] = replacement
            old_lock.release()
            result = await task
            self.assertEqual(result['reason'], 'INVENTORY_OBSERVE_ROW_LOCK_CHANGED')
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertEqual(result['typed_bytes_requested'], 0)
            self.assertEqual(self.memory.calls, [])
            self.assertIsNone(self.observer.last_sample_monotonic_ns)
            self.assertEqual(self.checkpoints, 0)
            self.assertFalse(old_lock.locked())
            self.assertTrue(replacement.locked())
            self.assertFalse(self.observer._authority._claimed)
            self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
            self.assertNotIn('read', self.memory.s.__dict__)
            self.writer.write.assert_not_called()
        finally:
            if not task.done(): task.cancel()
            if old_lock.locked(): old_lock.release()
            if replacement.locked(): replacement.release()
            self.row['operation_lock'] = old_lock
        self.assertFalse(old_lock.locked() or replacement.locked())

    async def test_cancel_without_yield_by_memory_callback_discards_complete_candidate(self):
        self.one()
        async def run():
            task = asyncio.current_task()
            def fault(at, size, raw):
                if at == self.item + 8: task.cancel()
                return raw
            self.memory.fault = fault
            await self.sample()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.create_task(run())
        self.assertEqual(self.observer.last_result['reason'], 'INVENTORY_OBSERVE_CALLER_CANCELLED')
        self.assertEqual(self.observer.last_result['rows'], [])
        self.assertIsNone(self.observer.last_result['entry_count'])
        self.assertFalse(self.reader.closed or self.reader.owner.closed)
        self.writer.write.assert_not_called()


class CurrentFrameTests(unittest.IsolatedAsyncioTestCase):
    """Real initial Add and explicit broker Update/Store/write/drain fixtures."""
    async def asyncSetUp(self):
        from tools.local_original_session.broker_tests import InventoryRestoreOnlyBrokerTests
        await InventoryRestoreOnlyBrokerTests.asyncSetUp(self)
        self.observer = n.InventoryObserver(self.producer, self.reader)
        self.wire = self.producer._inventory_frame
        self.assertIsNone(self.producer._inventory_current_frame)
        result = await self.producer.add_inventory(self.writer)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertIs(self.producer._inventory_current_frame, self.wire)
        self.initial = (self.producer._inventory_frame, self.producer._inventory_operation_frame,
                        self.producer._inventory_selection_binding,
                        self.producer._inventory_delivery_authority)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.materialize(self.wire)

    def materialize(self, frame):
        ObservationTests.one(self)
        fields = dict(inventory.validate_frame(frame).raw_fields)
        for offset, fmt, value in ((8, '<Q', fields[1]), (0x10, '<I', fields[2] & 0xffffffff),
                (0x18, '<Q', fields[3]), (0x28, '<q', fields[4] - (1 << 64)
                    if fields[4] >= 1 << 63 else fields[4]), (0x30, '<B', fields[24])):
            self.memory.put(self.item + offset, fmt, value)

    async def sample(self):
        self.product_ns += n.MIN_INTERVAL_NS
        before = len(self.memory.calls)
        result = await self.observer.sample(self.writer, now_ns=self.product_ns)
        self.assertEqual(result['typed_bytes_requested'], sum(size for _, size in self.memory.calls[before:]))
        self.assertTrue(self.service._claimed)
        self.assertFalse(self.observer._authority._claimed)
        self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
        return result

    def replacement(self):
        fields = dict(inventory.validate_frame(self.wire).raw_fields)
        fields.update({4: (1 << 63) + 17, 5: 3, 7: 2, 18: b'updated-wire-bytes'})
        return inventory.build_add(fields)

    async def update(self, changes=None):
        from tools.local_original_session import broker
        self.producer.inventory_update_policy = broker.INVENTORY_UPDATE_POLICY
        self.policy.inventory_update = True  # Explicit fixture policy, no production config edit.
        self.realm._inventory_update_broker = self.producer
        fields = dict(inventory.validate_frame(self.replacement()).raw_fields)
        if changes is None:
            changes = {key: fields[key] for key in (4, 5, 7, 18)}
        old = self.producer._inventory_current_frame
        drained = self.writer.drain.side_effect
        observed = []
        async def drain():
            op = self.producer._inventory_update_operation
            self.assertEqual(self.service.store.restore(self.realm.profile_uid), op['new'])
            self.assertIs(self.producer._inventory_current_frame, old)
            observed.append(1)
            if drained: return await drained()
        self.writer.drain.side_effect = drain
        try:
            result = await self.producer.update_inventory(self.writer,
                item_identifier=inventory.validate_frame(old).identifier,
                changes=changes, policy=broker.INVENTORY_UPDATE_POLICY)
        finally:
            self.writer.drain.side_effect = drained
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertEqual(observed, [1])
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        op = self.producer._inventory_update_operation
        self.assertIs(self.producer._inventory_current_frame, op['new'])
        self.assertEqual(op['phase'], 'DRAINED')
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        return op['new']

    def counter_drift(self):
        hits = []
        def drift(at, size, raw):
            if at == 0x250008 and size == 4:
                hits.append(1)
                if len(hits) == 2: return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
            return raw
        self.memory.fault = drift

    async def test_real_add_store_cas_different_current_then_move_observes_new_bits(self):
        initial = await self.sample()
        self.assertEqual((initial['status'], initial['typed_bytes_requested']), ('OBSERVED', 2084))
        replacement = await self.update()  # Drain hook proves CAS new/current old ordering.
        self.materialize(replacement)
        mover = self.realm.service(self.writer)
        mover._edge_passability = lambda *_: True
        from tools.local_original_session.movement_tests import payload
        moved = await mover.handle_CS4E2B(payload(mover.snapshot(), 2))
        self.assertTrue(moved.accepted)
        self.memory.fault = None
        result = await self.sample()
        self.assertEqual((result['status'], result['rows'][0]['field28_i64']), ('OBSERVED', -(1 << 63) + 17))
        self.assertEqual(result['rows'][0]['field18_u64'], (1 << 64) - 1)
        self.row['policy_row'].sent += 1  # Later unrelated successful TX counter fixture.
        self.assertEqual((await self.sample())['status'], 'OBSERVED')
        self.assertFalse(result['wire_field18_bytes_observed'] or result['equipped_or_durable_state_proven'])
        self.assertIsNot(self.realm.service(self.writer).snapshot(), self.initial[3][0])
        for current, original in zip((self.producer._inventory_frame, self.producer._inventory_operation_frame,
                self.producer._inventory_selection_binding, self.producer._inventory_delivery_authority), self.initial):
            self.assertIs(current, original)

    async def test_counter_only_uses_current_five_values_and_never_disk_or_initial(self):
        replacement = await self.update()
        self.counter_drift()
        wrong = await self.sample()  # Row still has initial f4.
        self.assertEqual((wrong['status'], wrong['reason'], wrong['rows']),
                         ('UNKNOWN', 'FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH', []))
        self.materialize(replacement)
        self.counter_drift()
        correct = await self.sample()
        self.assertEqual((correct['status'], correct['reason']), ('UNKNOWN', 'EDGE_TYPED_READ_CHANGED'))
        self.assertTrue(correct['source_owner_revalidated'])
        self.assertEqual(correct['typed_bytes_requested'], 2084)

    async def test_strict_previous_field4_pending_new_success_and_third_scalar_are_distinct(self):
        old = await self.sample()
        frame = await self.update({4: (1 << 63) + 17})
        self.assertEqual(self.producer._inventory_update_operation['changes'], ((4, (1 << 63) + 17),))
        previous = await self.sample()  # Real Update drained; row has not consumed f4 yet.
        self.assertEqual((previous['status'], previous['reason'], previous['rows']),
            ('OBSERVED', 'INVENTORY_OBSERVE_PREVIOUS_FIELD4_PENDING', old['rows']))
        self.assertTrue(previous['source_contract_valid'] and previous['stable_double_read'])
        self.materialize(frame)
        current = await self.sample()
        self.assertEqual((current['status'], current['reason'], current['rows'][0]['field28_i64']),
                         ('OBSERVED', None, -(1 << 63) + 17))
        self.memory.put(self.item + 0x28, '<q', -(1 << 63) + 1)
        third = await self.sample()
        self.assertIsNone(third['reason'])  # Raw strict mismatch stays available to the normal consumer.
        self.assertNotEqual(third['rows'], old['rows'])
        self.memory.put(self.item + 0x28, '<q', -(1 << 63))
        self.memory.put(self.item + 0x10, '<I', 2)
        other_scalar = await self.sample()
        self.assertIsNone(other_scalar['reason'])
        self.assertNotEqual(other_scalar['rows'], old['rows'])

    async def test_previous_field4_marker_never_covers_multifield_or_incomplete_read(self):
        await self.update()  # The real full17 difference includes 4/5/7/18.
        multi = await self.sample()  # The still-old visible five values are no general pending claim.
        self.assertEqual((multi['status'], multi['reason']), ('OBSERVED', None))
        self.counter_drift()
        incomplete = await self.sample()
        self.assertEqual((incomplete['status'], incomplete['reason']),
                         ('UNKNOWN', 'FEATURE_INVENTORY_CLIENT_ITEM_MISMATCH'))
        self.assertFalse(incomplete['source_contract_valid'] or incomplete['stable_double_read'])

    async def test_existing_store_restore_add_seeds_current_for_unchanged_observation(self):
        # A fresh real broker restores the already persisted canonical row.
        await self.rebuild()
        self.product_ns += n.MIN_INTERVAL_NS
        self.wire = self.producer._inventory_frame
        self.assertTrue(self.producer._inventory_restored)
        self.assertIsNone(self.producer._inventory_current_frame)
        result = await self.producer.add_inventory(self.writer, restore_only=True)
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertIs(self.producer._inventory_current_frame, self.producer._inventory_frame)
        self.observer = n.InventoryObserver(self.producer, self.reader)
        self.writer.write.reset_mock(); self.writer.drain.reset_mock()
        self.materialize(self.producer._inventory_current_frame)
        observed = await self.sample()
        self.assertEqual((observed['status'], observed['typed_bytes_requested']), ('OBSERVED', 2084))

    async def test_await_current_owner_selection_position_and_initial_cap_swaps_refuse(self):
        original = self.producer._sample
        mover = self.realm.service(self.writer)
        position = mover.snapshot()
        selection = dict(self.realm.registry.selected)
        process = self.reader.member.process
        current = self.producer._inventory_current_frame
        for mode in ('current_copy', 'current_new', 'current_none', 'owner', 'selection',
                     'position', 'delivery_copy', 'binding_copy', 'initial_copy', 'operation_copy'):
            async def changed(row):
                result = await original(row)
                if mode == 'current_copy': self.producer._inventory_current_frame = bytes(bytearray(current))
                elif mode == 'current_new': self.producer._inventory_current_frame = self.replacement()
                elif mode == 'current_none': self.producer._inventory_current_frame = None
                elif mode == 'owner': self.reader.member.process = object()
                elif mode == 'selection': self.realm.registry.selected.clear()
                elif mode == 'position': mover._position = replace(position)
                elif mode == 'delivery_copy': self.producer._inventory_delivery_authority = tuple(list(self.initial[3]))
                elif mode == 'binding_copy': self.producer._inventory_selection_binding = tuple(list(self.initial[2]))
                elif mode == 'initial_copy': self.producer._inventory_frame = bytes(bytearray(self.wire))
                else: self.producer._inventory_operation_frame = bytes(bytearray(self.wire))
                return result
            self.producer._sample = changed
            before = len(self.memory.calls)
            try:
                result = await self.sample()
                self.assertEqual((result['status'], result['rows']), ('UNKNOWN', []), (mode, result))
                self.assertEqual(len(self.memory.calls), before)
            finally:
                self.producer._inventory_current_frame = current
                self.reader.member.process = process
                self.realm.registry.selected.clear(); self.realm.registry.selected.update(selection)
                mover._position = position
                (self.producer._inventory_frame, self.producer._inventory_operation_frame,
                 self.producer._inventory_selection_binding, self.producer._inventory_delivery_authority) = self.initial
        self.producer._sample = original

    async def test_missing_current_or_missing_delivery_has_no_initial_fallback(self):
        current, delivery = self.producer._inventory_current_frame, self.producer._inventory_delivery_authority
        for mode in ('missing_current', 'missing_delivery', 'unclaimed', 'historical_position_none'):
            if mode == 'missing_current': self.producer._inventory_current_frame = None
            elif mode == 'missing_delivery': self.producer._inventory_delivery_authority = None
            elif mode == 'unclaimed': self.service._claimed = False
            else:
                identities = list(delivery[1]); identities[14] = None
                self.producer._inventory_delivery_authority = (None, tuple(identities), delivery[2])
            count = len(self.memory.calls)
            result = await self.observer.sample(self.writer, now_ns=self.product_ns + n.MIN_INTERVAL_NS)
            self.product_ns += n.MIN_INTERVAL_NS
            self.assertEqual(result['reason'], 'INVENTORY_AUTHORITY_CHANGED' if mode == 'historical_position_none'
                             else 'INVENTORY_OBSERVE_DELIVERY_AUTHORITY_REQUIRED')
            self.assertEqual(len(self.memory.calls), count)
            self.producer._inventory_current_frame, self.producer._inventory_delivery_authority = current, delivery
            self.service._claimed = True

    async def test_only_last_drained_operation_can_supply_noninitial_current(self):
        current = await self.update()
        self.materialize(current)
        op = self.producer._inventory_update_operation
        sent = self.row['policy_row'].sent
        for mode in ('current_copy', 'missing_op', 'active_with_initial', 'terminal_with_initial',
                     'no_drain', 'no_post_owner', 'wrong_sent', 'sent_not_reached', 'wrong_store_ref', 'position_none'):
            snapshot = dict(op)
            if mode == 'current_copy': self.producer._inventory_current_frame = bytes(bytearray(current))
            elif mode == 'missing_op': self.producer._inventory_update_operation = None
            elif mode in ('active_with_initial', 'terminal_with_initial'):
                op['phase'] = 'PERSISTED' if mode == 'active_with_initial' else 'TERMINAL'
                self.producer._inventory_current_frame = self.wire
            elif mode == 'no_drain': op['drain_returned'] = False
            elif mode == 'no_post_owner': op['post_owner_verified'] = False
            elif mode == 'wrong_sent': op['sent_after'] += 1
            elif mode == 'sent_not_reached': self.row['policy_row'].sent = op['sent_after'] - 1
            elif mode == 'wrong_store_ref':
                refs = list(op['refs']); refs[8] = object(); op['refs'] = tuple(refs)
            else:
                refs = list(op['refs']); refs[4] = None; op['refs'] = tuple(refs)
                values = list(op['authority'][1]); values[14] = None
                op['authority'] = (None, tuple(values), op['authority'][2])
            count = len(self.memory.calls)
            try:
                result = await self.sample()
                self.assertEqual((result['status'], result['rows']), ('UNKNOWN', []), (mode, result))
                self.assertEqual(len(self.memory.calls), count)
            finally:
                op.clear(); op.update(snapshot)
                self.producer._inventory_current_frame = current
                self.producer._inventory_update_operation = op
                self.row['policy_row'].sent = sent
        original = self.producer._sample
        async def swap(row):
            result = await original(row)
            self.producer._inventory_update_operation = dict(op)
            return result
        self.producer._sample = swap
        count = len(self.memory.calls)
        try:
            self.assertEqual((await self.sample())['status'], 'UNKNOWN')
            self.assertEqual(len(self.memory.calls), count)
        finally:
            self.producer._sample = original
            self.producer._inventory_update_operation = op


class ReselectionObservationTests(unittest.IsolatedAsyncioTestCase):
    from tools.local_original_session.broker_tests import InventoryReselectionTests as _Fixture
    asyncSetUp = _Fixture.asyncSetUp
    rebuild, dispatch, select = _Fixture.rebuild, _Fixture.dispatch, _Fixture.select
    add, reset_writes = _Fixture.add, _Fixture.reset_writes
    restart_reselect = _Fixture.restart_reselect

    async def test_actual_reselection_closed_old_observer_and_fresh_new_delivery(self):
        await self.add()
        old = self.producer.inventory_selection_current(self.writer)
        old_observer = n.InventoryObserver(self.producer, self.reader)
        CurrentFrameTests.materialize(self, old.current_frame)
        query_ns = 1_000_000_000
        with patch.object(n, 'monotonic_ns', lambda: query_ns):
            before = await old_observer.sample(self.writer, now_ns=query_ns)
            self.assertEqual((before['status'], before['entry_count']), ('OBSERVED', 1))
            stored = old.store.path.read_bytes()
            new = await self.restart_reselect()
            self.assertIs(new.previous, old)
            self.assertTrue(old.service._closed)
            # Lifecycle calls stay owned by the launcher; these original leaf
            # APIs test the resulting closed-old/fresh-new consumer boundary.
            old_observer.close()
            query_ns += n.MIN_INTERVAL_NS
            count = len(self.memory.calls)
            closed = await old_observer.sample(self.writer, now_ns=query_ns)
            self.assertEqual((closed['status'], closed['reason']), ('UNKNOWN', 'INVENTORY_OBSERVE_CLOSED'))
            self.assertEqual(len(self.memory.calls), count)
            self.assertFalse(self.reader.closed or self.reader.owner.closed)
            fresh = n.InventoryObserver(self.producer, self.reader)
            # Explicit injected snapshot of the new selection's empty client
            # vector, not a generation/once reset or a product-side mutation.
            self.memory.put(self.memory.header, '<QQQ', self.vector, self.vector, self.vector + 64)
            self.reset_writes()
            await self.add()
            self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
            self.assertEqual(new.store.path.read_bytes(), stored)
            self.assertIs(new.current_frame, new.frame)
            self.assertIsNot(new.delivery_authority, old.delivery_authority)
            CurrentFrameTests.materialize(self, new.current_frame)
            self.reset_writes()
            query_ns += n.MIN_INTERVAL_NS
            count = len(self.memory.calls)
            observed = await fresh.sample(self.writer, now_ns=query_ns)
            self.assertEqual((observed['status'], observed['reason'], observed['entry_count']), ('OBSERVED', None, 1))
            self.assertEqual(observed['typed_bytes_requested'], 2084)
            self.assertEqual(observed['typed_bytes_requested'], sum(size for _, size in self.memory.calls[count:]))
            self.assertFalse(fresh._authority._claimed)
            self.assertTrue(old.service._claimed and old.service._closed and new.service._claimed)
            self.writer.write.assert_not_called(); self.writer.drain.assert_not_awaited()
            self.assertIs(self.producer.inventory_selection_current(self.writer), new)


if __name__ == '__main__':
    unittest.main()
