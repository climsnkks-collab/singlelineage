"""Actual realm/retained methods with injected memory, no OS process API.

Image guard material is read unchanged from the existing pinned saved records.
No disassembly/producer main, source-ready bypass, game or native initializer.
"""
import ctypes as C
from dataclasses import replace
import importlib.util
import json
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import attack_tests, npc_observe as n, observe


class Memory:
    @classmethod
    def source(cls):
        if not hasattr(cls, '_saved'):
            path = observe.ROOT / 'tools/local_movement_contract/source.py'
            spec = importlib.util.spec_from_file_location('_npc_test_saved_records', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _, cls._saved = module.view()  # read only; no function decoding
        return cls._saved

    def __init__(self, case):
        self.reader, self.native = case.reader, case.native
        self.base, self.size, self.data = 0x140000000, 65622016, {}
        self.calls, self.fault = [], None
        self.npc, self.player, self.transform, self.vector = 0x410000, 0x400000, 0x490000, 0x420000
        path = observe.ROOT / 'work/online_intro_capture_20261006/source-contract.json'
        assert observe.digest(path) == '2c9af49767502c0b28f39a24dd24ffe44eb142ed9acf0cd2372dcc11bf87c7e5'
        self.c = json.loads(path.read_bytes())
        self.reader.contract = self.native.contract = self.c
        self.s = self.reader.sampler_module.Sampler(self.native, self.c, dict(base=self.base, size=self.size))
        self.s.bytes, self.s.read_limit, self.s.total = 77, 8192, 900
        self.reader.sampler = self.s
        self.native.rpm_attempts = self.native.rpm_successes = self.native.rpm_bytes = 0
        self.native.k = SimpleNamespace(VirtualQueryEx=self.query, ReadProcessMemory=self.rpm)
        self.proof = case.observer.proof
        p, layout = self.proof.public, self.c['layout']
        root, gi, subsystems, ctrl = 0x200000, 0x210000, 0x220000, 0x250000
        actors, maps, state, context, land = 0x300000, 0x310000, 0x320000, 0x330000, 0x340000
        self.put(ctrl + 8, '<i', 4)
        self.put(self.base + layout['Root_slot_rva'], '<Q', root)
        self.put(root + layout['Root_ready'], '<B', 1)
        self.put(root + layout['Root_phase'], '<I', 7)
        self.put(root + layout['GI_pointer'], '<Q', gi)
        self.put(gi + layout['GI_begin'], '<QQ', subsystems, subsystems + 48)
        gs, = self.c['tables']['GameState']
        for index, (obj, vp) in enumerate(((actors, p['Player']['ActorSubsystem']['rva']),
                                         (maps, p['Map']['table']['rva']), (state, gs['rva']))):
            self.put(obj, '<Q', self.base + vp)
            self.put(subsystems + index * 16, '<QQ', obj, ctrl)
        scene, = [s for s in self.c['scenes'] if s['kind'] == 'Land']
        self.put(land, '<QQI', self.base + scene['rva'], 0, 5)
        self.put(state + 0x360, '<QQQQI', land, ctrl, 0, 0, 5)
        self.put(maps + p['Map']['context_pointer'], '<Q', context)
        self.put(maps + p['Map']['field718'], '<ii', 0, 0)
        self.put(context, '<i', 0)
        self.actors = actors
        self.put(actors + p['Player']['vector_begin'], '<QQ', self.vector, self.vector + 32)
        self.put(self.vector, '<QQQQ', self.player, ctrl, self.npc, ctrl)
        monster, _, _ = n._source()
        for actor, vp, uid, transform, vector in (
                (self.player, p['Player']['MyPlayer']['rva'], case.realm.profile_uid, 0x470000, 0x460000),
                (self.npc, monster['rva'], case.mover.state.uid, self.transform, 0x480000)):
            self.put(actor, '<QQ', self.base + vp, actor)
            self.put(actor + 24, '<Q', uid)
            self.put(actor + p['Position']['component_begin'], '<QQ', vector, vector + 16)
            self.put(vector, '<QQ', transform, ctrl)
            self.put(transform, '<Q', self.base + p['Position']['Transform']['rva'])
            self.put(transform + p['Position']['borrowed_Actor'], '<Q', actor)
            self.grid(transform, [case.x, case.y])

    def put(self, at, fmt, *values):
        self.data.update((at + i, value) for i, value in enumerate(struct.pack(fmt, *values)))

    def grid(self, transform, grid):
        self.put(transform + self.proof.public['Position']['pair_offset'], '<ii',
                 *((v >> 6) + 0x7e00 for v in grid))
        self.put(transform + self.proof.position_source['coordinates']['transform_grid_offset'], '<ii', *grid)

    def read(self, at, size):
        if self.base <= at and at + size <= self.base + self.size:
            raw = bytearray(self.source().read(at - self.base, size))
            for i in range(size):
                if at + i in self.data:
                    raw[i] = self.data[at + i]
            return bytes(raw)
        return bytes(self.data[at + i] for i in range(size))

    def query(self, handle, at, info, size):
        image = self.base <= at < self.base + self.size
        row = info._obj
        row.base, row.region_size = (self.base, self.size) if image else (0x10000, 0x1000000)
        row.allocation_base, row.state, row.protect = (self.base if image else 0x10000), 0x1000, 4
        row.type = 0x1000000 if image else 0x20000
        return size

    def rpm(self, handle, at, data, size, received):
        self.calls.append((at, size))
        raw = self.read(at, size)
        if self.fault:
            raw = self.fault(at, size, raw)
        C.memmove(data, raw, len(raw))
        received._obj.value = len(raw)
        return True


class NpcObservationTests(unittest.IsolatedAsyncioTestCase):
    stage_metrics = {}

    async def asyncSetUp(self):
        await attack_tests.TargetTests.asyncSetUp(self)
        self.observer = n.NpcObserver(self.producer, self.reader)
        self.memory = Memory(self)
        self.now_ns = 0

    async def sample(self):
        self.now_ns += n.MIN_INTERVAL_NS
        result = await self.observer.sample(self.writer, self.mover.state.uid, now_ns=self.now_ns)
        self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
        self.assertNotIn('read', self.memory.s.__dict__)
        self.assertNotIn('strong_pair', self.memory.s.__dict__)
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)
        return result

    async def test_actual_source_guards_reader_and_realm_positive_with_separate_grid(self):
        state = self.mover.state
        row = await self.sample()
        self.assertEqual(row['status'], 'OBSERVED', row)
        self.assertEqual(row['observation_stage'], 'COMPLETE')
        type(self).stage_metrics['positive'] = {key: row[key] for key in (
            'status', 'reason', 'observation_stage', 'typed_bytes_requested', 'typed_byte_limit')}
        self.assertEqual(row['client_grid'], [self.x, self.y])
        self.assertEqual(row['server_grid'], [self.x, self.y])
        self.assertTrue(row['source_contract_valid'] and row['stable_double_read'])
        self.assertFalse(row['snapshot_atomic'] or row['visible_screen_claimed'])
        self.assertEqual(row['typed_bytes_requested'], sum(size for _, size in self.memory.calls))
        self.assertLessEqual(row['typed_bytes_requested'], 16384)
        self.positive_bytes = row['typed_bytes_requested']
        self.memory.grid(self.memory.transform, [self.x + 1, self.y])
        row = await self.sample()
        self.assertEqual(row['status'], 'OBSERVED', row)
        self.assertFalse(row['coordinates_match'])
        self.assertEqual(row['client_grid'], [self.x + 1, self.y])
        self.assertIs(self.mover.state, state)

    async def test_observation_stage_initial_duplicate_and_final_readback_preserve_unknown(self):
        layout = self.memory.c['layout']
        ready_at = 0x200000 + layout['Root_ready']
        grid_at = self.memory.transform + self.observer.proof.position_source['coordinates']['transform_grid_offset']
        for label, target, expected_stage in (
                ('initial_duplicate', ready_at, 'WORLD_TYPED'),
                ('final_readback', grid_at, 'FINAL_READBACK')):
            hits = [0]
            def fault(at, size, raw):
                if at == target:
                    hits[0] += 1
                    if hits[0] == 2:
                        return bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            self.memory.fault = fault
            start = len(self.memory.calls)
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertEqual(row['reason'], 'EDGE_TYPED_READ_CHANGED')
            self.assertEqual(row['observation_stage'], expected_stage)
            self.assertIsNone(row['client_grid'])
            self.assertFalse(row['source_contract_valid'] or row['stable_double_read'])
            self.assertEqual(row['typed_bytes_requested'], sum(size for _, size in self.memory.calls[start:]))
            self.assertLessEqual(row['typed_bytes_requested'], 16384)
            type(self).stage_metrics[label] = {key: row[key] for key in (
                'status', 'reason', 'observation_stage', 'typed_bytes_requested', 'typed_byte_limit')}
        self.memory.fault = None

    async def test_observation_stage_pre_read_authorize_and_cadence_are_not_completed_checks(self):
        before = len(self.memory.calls)
        row = await self.observer.sample(self.writer, 0, now_ns=0)
        self.assertEqual((row['status'], row['observation_stage'], row['typed_bytes_requested']),
                         ('UNKNOWN', 'AUTHORIZE', 0))
        self.assertEqual(row['reason'], 'ATTACK_LOCAL_ACTOR_TARGET_REQUIRED')
        row = await self.observer.sample(self.writer, self.mover.state.uid, now_ns=0)
        self.assertEqual((row['status'], row['reason'], row['observation_stage'], row['typed_bytes_requested']),
                         ('UNKNOWN', 'NPC_OBSERVE_CADENCE', 'REQUEST', 0))
        self.assertEqual(len(self.memory.calls), before)
        self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
        self.assertNotIn('read', self.memory.s.__dict__)

    async def test_positive_count_instability_is_incomplete_only_after_all_original_checks(self):
        count_at = 0x250000 + 8
        original_verify = n._ObservationBudget.verify
        type(self).instability_metrics = {}
        for label in ('INITIAL_DUPLICATE', 'FINAL_READBACK'):
            phase, hits = [False], [0]
            def verify(budget):
                phase[0] = True
                try:
                    return original_verify(budget)
                finally:
                    phase[0] = False
            def fault(at, size, raw):
                if at == count_at and size == 4:
                    hits[0] += 1
                    if ((label == 'INITIAL_DUPLICATE' and hits[0] == 2)
                            or (label == 'FINAL_READBACK' and phase[0])):
                        return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
                return raw
            self.memory.fault = fault
            before = len(self.memory.calls)
            with patch.object(n._ObservationBudget, 'verify', verify):
                row = await self.sample()
            self.assertEqual((row['status'], row['reason']), ('UNKNOWN', 'EDGE_TYPED_READ_CHANGED'))
            self.assertEqual(row['read_consistency'], 'RECHECKED_SHARED_COUNT_' + label)
            self.assertTrue(row['source_owner_revalidated'])
            self.assertEqual(row['observation_stage'], 'AUTHORITY_AFTER')
            self.assertFalse(row['stable_double_read'] or row['source_contract_valid'])
            self.assertIsNone(row['client_grid'])
            self.assertEqual(row['typed_bytes_requested'], sum(size for _, size in self.memory.calls[before:]))
            self.assertEqual(row['typed_bytes_requested'], 3565)
            type(self).instability_metrics[label] = {key: row[key] for key in (
                'status', 'reason', 'read_consistency', 'source_owner_revalidated',
                'stable_double_read', 'client_grid', 'typed_bytes_requested')}
        self.memory.fault = None
        row = await self.sample()
        self.assertEqual((row['status'], row['read_consistency']), ('OBSERVED', 'STRICT_STABLE'))
        self.assertTrue(row['source_owner_revalidated'])

    async def test_count_marker_never_survives_semantic_owner_source_or_physical_failures(self):
        saved, selected = dict(self.memory.data), dict(self.realm.registry.selected)
        owner_validate = self.reader.owner.validate
        initial = self.mover.state
        _, _, checks = n._source()
        code_at = self.memory.base + checks[0]['rva']
        mutations = (
            lambda: self.memory.put(self.memory.player + 24, '<Q', 999),
            lambda: self.memory.put(self.memory.npc + 24, '<Q', 999),
            lambda: self.memory.put(self.memory.transform + self.observer.proof.public['Position']['borrowed_Actor'], '<Q', self.memory.player),
            self.realm.registry.selected.clear,
            lambda: setattr(self.reader.owner, 'validate', lambda _: False),
            lambda: setattr(self.mover, 'state', replace(initial)),
            lambda: self.memory.put(code_at, '<B', self.memory.read(code_at, 1)[0] ^ 1))
        for mutate in mutations:
            hits = [0]
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == 2:
                        mutate()
                        return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
                return raw
            self.memory.fault = fault
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertEqual(row['read_consistency'], 'NOT_CLASSIFIED', row)
            self.assertFalse(row['source_owner_revalidated'])
            self.memory.data = dict(saved)
            self.realm.registry.selected.update(selected)
            self.reader.owner.validate, self.mover.state = owner_validate, initial
        for changed in (0, -1, None):
            hits = [0]
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == 2:
                        return raw[:-1] if changed is None else struct.pack('<i', changed)
                return raw
            self.memory.fault = fault
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN')
            self.assertEqual(row['read_consistency'], 'NOT_CLASSIFIED')
            self.assertFalse(row['source_owner_revalidated'])
        self.memory.fault = None

    async def test_count_only_provenance_collision_is_fail_closed_before_or_after_drift(self):
        raw_pair = struct.pack('<QQ', self.memory.npc, 0x250000)
        for drift_first in (False, True):
            budget = n._ObservationBudget(self.native, self.memory.s)
            hits = [0]
            def fault(at, size, raw):
                if at == 0x250008 and size == 4:
                    hits[0] += 1
                    if hits[0] == (2 if drift_first else 3):
                        return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
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
            self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
        self.memory.fault = None

    async def test_same_reader_proof_replacement_cannot_publish_rechecked_count_marker(self):
        original_proof = self.observer.proof
        count_hits, replaced = [0], [False]
        def fault(at, size, raw):
            if at == 0x250008 and size == 4:
                count_hits[0] += 1
                if count_hits[0] == 2:
                    return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
            if at == self.memory.npc + 24 and not replaced[0]:
                replaced[0] = True
                self.observer.proof = type(original_proof)(self.reader)
            return raw
        self.memory.fault = fault
        row = await self.sample()
        self.assertTrue(replaced[0])
        self.assertIsNot(self.observer.proof, original_proof)
        self.assertIs(self.observer.proof.reader, self.reader)
        self.assertEqual((row['status'], row['reason'], row['read_consistency']),
                         ('UNKNOWN', 'NPC_OBSERVE_PRODUCER_CHANGED', 'NOT_CLASSIFIED'))
        self.assertFalse(row['source_owner_revalidated'])
        self.assertIsNone(row['client_grid'])

    async def test_positive_count_with_stable_wrong_grid_never_marks_rechecked_incomplete(self):
        self.memory.grid(self.memory.transform, [self.x + 1, self.y])
        hits = [0]
        def fault(at, size, raw):
            if at == 0x250008 and size == 4:
                hits[0] += 1
                if hits[0] == 2:
                    return struct.pack('<i', struct.unpack('<i', raw)[0] + 1)
            return raw
        self.memory.fault = fault
        row = await self.sample()
        self.assertEqual((row['status'], row['reason'], row['read_consistency']),
                         ('UNKNOWN', 'NPC_OBSERVE_CURRENT_POSITION_MISMATCH', 'NOT_CLASSIFIED'))
        self.assertFalse(row['source_owner_revalidated'] or row['stable_double_read'])
        self.assertIsNone(row['client_grid'])
        self.memory.fault = None
        row = await self.sample()
        self.assertEqual((row['status'], row['read_consistency'], row['coordinates_match']),
                         ('OBSERVED', 'STRICT_STABLE', False))
        self.assertEqual(row['client_grid'], [self.x + 1, self.y])

    async def test_wrong_type_uid_getter_borrowed_actor_and_first_match_refuse(self):
        original = dict(self.memory.data)
        monster, _, _ = n._source()
        grid_offset = self.observer.proof.public['Position']['borrowed_Actor']
        changes = [lambda: self.memory.put(self.memory.npc, '<Q', self.memory.base + monster['rva'] + 56),
            lambda: self.memory.put(self.memory.base + monster['rva'] + 8, '<Q', self.memory.base + 1),
            lambda: self.memory.put(self.memory.npc + 24, '<Q', 999),
            lambda: self.memory.put(self.memory.transform + grid_offset, '<Q', self.memory.player)]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.memory.data = dict(original)
                change()
                row = await self.sample()
                self.assertEqual(row['status'], 'UNKNOWN', row)
                self.assertIsNone(row['client_grid'])
        self.memory.data = dict(original)
        # An earlier UID match of a different source-qualified Actor subtype
        # must not be skipped to find the later Monster.
        foreign = 0x510000
        self.memory.put(foreign, '<QQ', self.memory.base + monster['rva'] + 56, foreign)
        self.memory.put(foreign + 24, '<Q', self.mover.state.uid)
        self.memory.put(self.memory.vector + 16, '<QQQQ', foreign, 0x250000, self.memory.npc, 0x250000)
        self.memory.put(self.memory.actors + self.observer.proof.public['Player']['vector_end'],
                        '<Q', self.memory.vector + 48)
        self.assertEqual((await self.sample())['status'], 'UNKNOWN')

    async def test_source_and_data_recheck_mutations_or_partial_reads_are_unknown(self):
        grid_at = self.memory.transform + self.observer.proof.position_source['coordinates']['transform_grid_offset']
        _, _, checks = n._source()
        code_at = self.memory.base + checks[0]['rva']
        for target, on_read, partial in ((grid_at, 2, False), (code_at, 1, False),
                                         (code_at, 2, False), (grid_at, 1, True)):
            hits = [0]
            def fault(at, size, raw):
                if at == target:
                    hits[0] += 1
                    if hits[0] == on_read:
                        return raw[:-1] if partial else bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            self.memory.fault = fault
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertFalse(row['source_contract_valid'])
        self.memory.fault = None
        pins = dict(n.SOURCE_PINS)
        pins[n.TYPE_PATH] = '0' * 64
        with patch.object(n, 'SOURCE_PINS', pins):
            self.assertEqual((await self.sample())['reason'], 'NPC_OBSERVE_SOURCE_CHANGED')

    async def test_current_claim_selection_native_owner_loss_after_read_refuses(self):
        old_selected, old_claims = dict(self.realm.registry.selected), dict(self.producer._claims)
        owner = self.reader.owner
        original_validate = owner.validate
        mutations = (lambda: self.realm.registry.selected.clear(),
                     lambda: self.producer._claims.clear(),
                     lambda: setattr(owner, 'validate', lambda _: False),
                     lambda: setattr(self.mover, 'state', replace(self.mover.state)))
        initial = self.mover.state
        for mutation in mutations:
            done = [False]
            def fault(at, size, raw):
                if at == self.memory.npc + 24 and not done[0]:
                    done[0] = True
                    mutation()
                return raw
            self.memory.fault = fault
            row = await self.sample()
            self.assertEqual(row['status'], 'UNKNOWN', row)
            self.assertIsNone(row['client_grid'])
            self.realm.registry.selected.update(old_selected)
            self.producer._claims.update(old_claims)
            owner.validate, self.mover.state = original_validate, initial

    async def test_original_reader_method_substitution_limit_and_caller_cadence_refuse(self):
        await self.sample()
        calls = len(self.memory.calls)
        for now in (self.now_ns, self.now_ns - 1, True):
            row = await self.observer.sample(self.writer, self.mover.state.uid, now_ns=now)
            self.assertEqual(row['status'], 'UNKNOWN')
            self.assertEqual(row['typed_bytes_requested'], 0)
        self.assertEqual(len(self.memory.calls), calls)
        self.observer._inflight = True
        self.assertEqual((await self.sample())['reason'], 'NPC_OBSERVE_INFLIGHT')
        self.observer._inflight = False
        self.memory.s.route = lambda: ()
        row = await self.sample()
        self.assertEqual(row['status'], 'UNKNOWN')
        del self.memory.s.route
        with patch.object(n, 'BYTE_LIMIT', 100):
            row = await self.sample()
            self.assertEqual(row['reason'], 'NPC_OBSERVE_BYTE_BUDGET')
            self.assertLessEqual(row['typed_bytes_requested'], 100)


if __name__ == '__main__':
    unittest.main()
