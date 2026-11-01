"""Actual source guard/retained methods and NPC-free realm; no process API.

Saved original records are hydrated read-only without decoder/producer main.
Only identity, memory query and RPM results are injected. No source-ready or
catalog membership bypass is used, including the positive gate.
"""
import asyncio
import copy
import ctypes as C
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
import uuid

from tools.local_original_session import broker as b, edge_tests, inventory as i, inventory_store as stores, observe
from tools.local_own_login_request.codec import LocalLoginRequest


def explicit_fields():
    # Explicit fixture values, never installed as default or starter policy.
    return {1: 0xffffffff, 2: 1, 3: (1 << 64) - 1, 4: 1 << 63, 5: -1,
            7: -(1 << 31), 9: 1 << 63, 10: 7, 13: 0, 14: 0xffffffff,
            16: 1, 17: -2, 18: b'\xff\0raw', 22: -3, 24: False, 25: -4, 26: True}


class WireTests(unittest.TestCase):
    def test_exact_explicit_one_raw_row_false_branch_and_catalog_key(self):
        values = explicit_fields()
        wire = i.build_add(values)
        item = i.validate_frame(wire)
        self.assertEqual(dict(item.raw_fields), values)
        self.assertEqual(item.identifier, 0xffffffff)
        self.assertEqual(item.template_bits, 1)
        self.assertEqual(wire[2:4], b'\x64\x09')
        with i.pb.parse_message(wire[4:-2], schema={1: 2, 2: 0}) as outer:
            self.assertEqual([(r.number, r.wire_type) for r in outer.fields], [(1, 2), (2, 0)])
            self.assertEqual(outer.occurrences(2)[0].value, 0)
            with i.pb.parse_message(outer.occurrences(1)[0].value) as child:
                actual = {r.number: r.value for r in child.fields}
                self.assertEqual(actual[4], 1 << 63)  # wire u64, no guessed positive signed range
                self.assertEqual(actual[5], (1 << 64) - 1)
                self.assertNotIn(21, actual)
        # raw bytes are not interpreted as UTF8 or an invented product name.
        self.assertIn(b'\xff\0raw', wire)

    def test_explicit_optional_policy_domains_and_unsupported_fields_refuse(self):
        values = explicit_fields()
        variants = []
        for missing in values:
            row = dict(values); del row[missing]; variants.append(row)
        for n, value in ((1, True), (1, 0), (1, 1 << 32), (2, 0xffffffff),
                         (2, 500000), (4, -1), (4, True), (14, -1), (24, 0),
                         (18, 'text'), (18, b'a' * 257), (19, ()), (21, 0), (34, b'')):
            row = dict(values); row[n] = value; variants.append(row)
        for row in variants:
            with self.subTest(fields=len(row)), self.assertRaises(ValueError):
                i.build_add(row)

    def test_strict_frame_shape_duplicate_unknown_presence_and_wire_fail_closed(self):
        wire = i.build_add(explicit_fields())
        with i.pb.parse_message(wire[4:-2], schema={1: 2, 2: 0}) as outer:
            child = bytes(outer.occurrences(1)[0].value)
        def frame(body, opcode=i.OPCODE):
            return struct.pack('<HH', len(body) + 6, opcode) + body + b'\0\0'
        children = [child + b'\x08\x01', child + b'\xa8\x01\0', child + b'\x9a\x01\0',
                    child.replace(b'\xc0\x01\0', b'\xc0\x01\x02'), b'\x08\x01', child[:-1]]
        cases = [frame(i.pb.encode_bytes(1, c) + b'\x10\0') for c in children]
        cases += [frame(i.pb.encode_bytes(1, child)), frame(i.pb.encode_bytes(1, child) + b'\x10\x01'),
                  frame(i.pb.encode_bytes(1, child) * 2 + b'\x10\0'),
                  frame(i.pb.encode_bytes(1, child) + b'\x10\0\x18\0'), wire[:-1], bytearray(wire),
                  frame(i.pb.encode_bytes(1, child) + b'\x10\0', i.OPCODE + 1)]
        for value in cases:
            with self.subTest(length=len(value)), self.assertRaisesRegex(ValueError, 'MALFORMED_INVENTORY'):
                i.validate_frame(value)

    def test_fixed_wire_and_catalog_pins_are_required(self):
        pins = dict(i.SOURCE_PINS); pins[i.EVIDENCE] = '0' * 64
        with patch.object(i, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            i.build_add(explicit_fields())
        pins = dict(i.SOURCE_PINS); pins[i.CATALOG_NAMES] = '0' * 64
        with patch.object(i, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            i.validate_frame(i._encode(i.ItemInfo(tuple(sorted(explicit_fields().items())))))


class Memory:
    @classmethod
    def source(cls):
        if not hasattr(cls, '_saved'):
            path = observe.ROOT / 'tools/local_movement_contract/source.py'
            spec = importlib.util.spec_from_file_location('_inventory_saved_records', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _, cls._saved = module.view()  # hydration only, no disassembly/producer main
        return cls._saved

    def __init__(self, case):
        self.case, self.reader, self.native = case, case.reader, case.native
        self.base, self.data = 0x140000000, {}
        self.calls, self.fault = [], None
        path = observe.ROOT / 'work/online_intro_capture_20261006/source-contract.json'
        assert observe.digest(path) == '2c9af49767502c0b28f39a24dd24ffe44eb142ed9acf0cd2372dcc11bf87c7e5'
        self.c = i._reader_intro(self.reader, i._source_documents())
        self.size = self.c['image_size']
        self.reader.contract = self.native.contract = self.c
        self.s = self.reader.sampler_module.Sampler(self.native, self.c, dict(base=self.base, size=self.size))
        self.s.bytes, self.s.read_limit, self.s.total = 77, 8192, 900
        self.reader.sampler = self.s
        self.native.rpm_attempts = self.native.rpm_successes = self.native.rpm_bytes = 0
        self.native.k = SimpleNamespace(VirtualQueryEx=self.query, ReadProcessMemory=self.rpm)
        self.proof = case.service.proof
        # The exact source-declared H bootstrap slot is the one cloned vtable
        # byte; saved original records supply every other image-table value.
        self.put(self.base + 0x1182e50, '<Q', self.base + 0x6cfa3)
        p, layout = self.proof.public, self.c['layout']
        root, gi, subsystems, ctrl = 0x200000, 0x210000, 0x220000, 0x250000
        actors, maps, self.state, context, land = 0x300000, 0x310000, 0x320000, 0x330000, 0x340000
        self.inventory, self.subsystems, self.gi = 0x350000, subsystems, gi
        self.put(ctrl + 8, '<i', 4)
        self.put(self.base + layout['Root_slot_rva'], '<Q', root)
        self.put(root + layout['Root_ready'], '<B', 1)
        self.put(root + layout['Root_phase'], '<I', 7)
        self.put(root + layout['GI_pointer'], '<Q', gi)
        self.put(gi + layout['GI_begin'], '<QQ', subsystems, subsystems + 64)
        gs, = self.c['tables']['GameState']
        contract, _, _ = i._source()
        for index, (obj, vp) in enumerate(((actors, p['Player']['ActorSubsystem']['rva']),
                (maps, p['Map']['table']['rva']), (self.state, gs['rva']),
                (self.inventory, contract['owners']['Inventory']['rva']))):
            self.put(obj, '<Q', self.base + vp)
            self.put(subsystems + index * 16, '<QQ', obj, ctrl)
        scene, = [s for s in self.c['scenes'] if s['kind'] == 'Land']
        self.put(land, '<QQI', self.base + scene['rva'], 0, 5)
        self.put(self.state + 0x360, '<QQQQI', land, ctrl, 0, 0, 5)
        self.put(maps + p['Map']['context_pointer'], '<Q', context)
        self.put(maps + p['Map']['field718'], '<ii', 0, 0)
        self.put(context, '<i', 0)
        self.player, transform, vector = 0x400000, 0x470000, 0x460000
        self.put(actors + p['Player']['vector_begin'], '<QQ', 0x420000, 0x420010)
        self.put(0x420000, '<QQ', self.player, ctrl)
        self.put(self.player, '<QQ', self.base + p['Player']['MyPlayer']['rva'], self.player)
        self.put(self.player + 24, '<Q', case.realm.profile_uid)
        self.put(self.player + p['Position']['component_begin'], '<QQ', vector, vector + 16)
        self.put(vector, '<QQ', transform, ctrl)
        self.put(transform, '<Q', self.base + p['Position']['Transform']['rva'])
        self.put(transform + p['Position']['borrowed_Actor'], '<Q', self.player)
        position = case.realm.service(case.writer).snapshot()
        self.put(transform + p['Position']['pair_offset'], '<ii',
                 *((v >> 6) + 0x7e00 for v in (position.word0, position.word1)))
        self.put(transform + self.proof.position_source['coordinates']['transform_grid_offset'],
                 '<ii', position.word0 + 1, position.word1)
        self.header = self.inventory + contract['inventory']['begin']
        # Empty but previously allocated vector is admitted by original shape.
        self.put(self.header, '<QQQ', 0x500000, 0x500000, 0x500040)

    def put(self, at, fmt, *values):
        self.data.update((at + n, value) for n, value in enumerate(struct.pack(fmt, *values)))

    def read(self, at, size):
        if self.base <= at and at + size <= self.base + self.size:
            raw = bytearray(self.source().read(at - self.base, size))
            for n in range(size):
                if at + n in self.data:
                    raw[n] = self.data[at + n]
            return bytes(raw)
        return bytes(self.data[at + n] for n in range(size))

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


class GateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        async def owner(*_): return True
        # Initialize the real broker's optional services and inventory lifetime;
        # the opaque socket values are never started or bound by this fixture.
        self.producer = b.PersistentBroker(
            sockets={12000: object(), 14030: object()}, retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=owner,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=lambda *_: None, expected_uuid=str(uuid.uuid4()),
            store_path=Path(self.temp.name) / 'characters.json')
        self.realm = self.producer.realm
        self.writer = SimpleNamespace(transport=SimpleNamespace(get_write_buffer_size=lambda: 0),
                                      write=Mock(), drain=AsyncMock())
        self.realm.store.create(b.ack.realm.Creation(self.realm.profile_name, 0, 0, (13,) * 6))
        game = self.realm.grant(self.writer, movement_owner_guard=owner, connection_id=4)
        await game.received(SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', self.realm.expected_uuid).payload()))
        payload = i.pb.encode_bytes(1, self.realm.profile_name.encode()) + b'\x10\0\x18\0'
        await game.received(SimpleNamespace(opcode=0x4e28, payload=payload))
        self.policy = self.producer.policy
        def sample(peer):
            return b.OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                                 peer, time.monotonic_ns(), True, True)
        def boot(writer, peer):
            row = self.policy.admit(writer, peer, sample(peer), time.monotonic_ns())
            for opcode, size, request in ((0x4e20, 12, None), (0x4e35, 76, 0x4e34), (0x4f3e, 6, 0x4f3d)):
                if request is not None:
                    self.policy.received_frame(writer, sample(peer), request, 10, time.monotonic_ns())
                self.policy.begin_write(writer, sample(peer), opcode, size, 0, time.monotonic_ns())
                self.policy.drained(writer, sample(peer), 0, time.monotonic_ns())
            return row
        prior, peer = object(), b.Peer(14030, 41000, time.monotonic_ns())
        boot(prior, peer)
        self.policy.eof(prior, sample(peer), True, time.monotonic_ns())
        self.policy.closed(prior, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        peer = b.Peer(14030, 41001, time.monotonic_ns())
        policy_row = boot(self.writer, peer)
        self.row = dict(writer=self.writer, policy_row=policy_row, peer=dict(connection_id=4, endpoint_port=14030),
                        joined=False, failed=False, operation_lock=asyncio.Lock())
        self.producer._claims = {12000: [], 14030: [self.row]}
        _, self.reader, self.native = edge_tests.Tests.retained_binding(self)
        self.reader.image = observe.IMAGE.with_name('LC.guard.exe')
        self.reader.member.identity['image'] = str(self.reader.image)
        member, retained = self.reader.member, self.reader.owner
        member.process, member.job = self.policy.handle, self.policy.job
        retained.child, retained.closed = member, False
        retained.owner_handle, retained.owner_job = self.policy.handle, self.policy.job
        self.policy.owner = retained
        self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        self.memory = Memory(self)
        self.wire = i.build_add(explicit_fields())
        self.now_ns = 0

    async def check(self, wire=None):
        self.now_ns += i.MIN_INTERVAL_NS
        try:
            async with self.row['operation_lock']:
                value = self.service.validate_pre_write_locked(self.writer, self.row,
                    self.wire if wire is None else wire, now_ns=self.now_ns)
        finally:
            self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
            self.assertNotIn('read', self.memory.s.__dict__)
            self.writer.write.assert_not_called(); self.assertEqual(self.writer.drain.await_count, 0)
        return value

    async def test_real_source_guards_retained_and_npc_free_realm_positive_once(self):
        self.assertEqual(self.realm._npc_spawns, ())
        self.assertIsNone(await self.check())
        result = self.service.last_result
        self.assertEqual(result['status'], 'OBSERVED', result)
        self.assertTrue(result['source_contract_valid'] and result['stable_double_read'])
        self.assertTrue(result['inventory_empty'] and result['catalog_static_key_verified'])
        self.assertFalse(result['catalog_live_materialization_proven'] or result['visible_screen_claimed'])
        self.assertEqual(result['typed_bytes_requested'], sum(n for _, n in self.memory.calls))
        self.assertLessEqual(result['typed_bytes_requested'], 16384)
        print('inventory_positive_typed_bytes=' + str(result['typed_bytes_requested']))
        with self.assertRaisesRegex(ValueError, 'ONE_SEND_ONLY'):
            await self.check()

    async def test_passive_source_cache_is_exact_before_and_after_without_code_body_queries(self):
        contract, _, core = i._source()
        checks = self.service._checks(self.memory.s, contract, core)
        code = {r['rva'] for r in checks}
        self.assertEqual(len(code), 49)
        query, queried = self.native.k.VirtualQueryEx, []
        def unreadable_code(handle, at, info, size):
            result = query(handle, at, info, size)
            queried.append(at - self.memory.base)
            if at - self.memory.base in code: info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = unreadable_code
        self.assertIsNone(await self.check())
        self.assertFalse(code & set(queried))
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.native.k.VirtualQueryEx = query
        original_c = copy.deepcopy(self.memory.c)
        original_checks = list(self.memory.s.image_checks)
        class IntCopy(int): pass
        class DictCopy(dict): pass
        def mutate(mode):
            if mode == 'public_bool': self.service.proof.public['parent']['checks'][0]['passed'] = 1
            elif mode == 'public_subclass': self.service.proof.public = DictCopy(self.service.proof.public)
            elif mode == 'position_bool': self.service.proof.position_source['coordinates']['grid_axis_names_world_units_unknown'] = 1
            elif mode == 'intro_bool': self.memory.c['runtime_cause_proven'] = 0
            elif mode == 'layout_int_subclass': self.memory.c['layout']['Root_slot_rva'] = IntCopy(self.memory.c['layout']['Root_slot_rva'])
            elif mode == 'intro_list_tuple': self.memory.c['checks'] = tuple(self.memory.c['checks'])
            elif mode == 'checks_list_tuple': self.memory.s.image_checks = tuple(original_checks)
            else: self.memory.s.image_checks = [list(original_checks[0]), *original_checks[1:]]
        for phase in ('before', 'after'):
            for mode in ('public_bool', 'public_subclass', 'position_bool', 'intro_bool',
                         'layout_int_subclass', 'intro_list_tuple', 'checks_list_tuple', 'checks_pair_list'):
                self.memory.c.clear(); self.memory.c.update(copy.deepcopy(original_c))
                self.memory.s.image_checks = list(original_checks)
                self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
                calls = len(self.memory.calls)
                if phase == 'before': mutate(mode)
                else:
                    def during(at, size, raw):
                        if at == self.memory.header: mutate(mode)
                        return raw
                    self.memory.fault = during
                with self.subTest(phase=phase, mode=mode), self.assertRaisesRegex(ValueError, 'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED'):
                    await self.check()
                self.assertFalse(self.service._claimed)
                if phase == 'before': self.assertEqual(len(self.memory.calls), calls)
                else: self.assertEqual(self.service.last_pre_write_stage, 'SOURCE_AFTER')
                self.memory.fault = None
        self.memory.c.clear(); self.memory.c.update(original_c)
        self.memory.s.image_checks = original_checks
        self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        for source in (i.PUBLIC_PROOF, i.INTRO_PROOF, i.WORLD_PROOF, i.POSITION_PROOF):
            pins = dict(i.SOURCE_PINS); pins[source] = '0' * 64
            calls = len(self.memory.calls)
            with patch.object(i, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'INVENTORY_SOURCE_CHANGED'):
                await self.check()
            self.assertEqual(len(self.memory.calls), calls)
        print('passive_code49_queries=0; exact_cache_before_after=16; exact4_source_pins=STRICT; empty_bytes=1857')

    async def test_actual_preflight_clone_and_sibling_contracts_match_once_generated_expectation(self):
        # Execute original preflight/watch generation. Only Frames.read input is
        # hydrated from the existing pinned saved-table fixture; no decoder runs.
        original_load = observe.load
        watch = original_load('tools/local_native_scene_current/watch.py', '_inventory_actual_preflight_watch')
        saved = self.memory.source()
        class SavedTables:
            def __init__(self, raw): pass
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, rva, size):
                raw = bytearray(saved.read(rva, size))
                if rva <= 0x1182e50 and 0x1182e58 <= rva + size:
                    at = 0x1182e50 - rva
                    if struct.unpack_from('<Q', raw, at)[0] != 0x14006cfa0:
                        raise AssertionError('saved original H slot changed')
                    raw[at] = 0xa3  # Pinned original rebuild.py transformation.
                return bytes(raw)
        def frames(path, alias):
            self.assertEqual(path, watch.FRAMES)
            return SimpleNamespace(Frames=SavedTables)
        def load(relative, alias):
            return watch if relative == 'tools/local_native_scene_current/watch.py' else original_load(relative, alias)
        documents = i._source_documents()
        variants = ((observe.IMAGE, observe.CANDIDATE, documents[i.CLONE_PROOF]['candidate']['sha256']),
            (observe.IMAGE.with_name('LC.guard.exe'), Path(documents[i.SIBLING_PROOF]['candidate']['path']),
             documents[i.SIBLING_PROOF]['candidate']['sha256']))
        for image, candidate, digest in variants:
            with patch.object(observe, 'load', load), patch.object(watch, 'load', frames):
                image, _, contract, _, _, _, _ = observe.preflight(image, candidate, expected_sha=digest)
            self.reader.image = image
            self.reader.member.identity['image'] = str(image)
            self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
            self.memory.c.clear(); self.memory.c.update(contract)
            self.assertEqual(contract['original_sha256'], digest)
            self.assertEqual(contract['image_size'], 65630208)
            self.assertEqual(contract['tables']['GameState'][0]['targets'][4], 0x6cfa3)
            self.assertEqual([r['state_id'] for r in contract['scenes'] if r['kind'] == 'Quit'], [6])
            self.assertIs(type(self.service._intro_snapshot), tuple)
            # Query must use the frozen once-derived expectation, not hash or
            # regenerate the image again during either source/cache check.
            with patch.object(observe, 'digest', side_effect=AssertionError('per-query image digest')):
                self.assertIsNone(await self.check())
            self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        print('actual_preflight=CP69_and_sibling8b9; saved_table_input_only; new_decoder_binary_native_calls=0; per_query_image_digest=0')

    async def test_clone_augmentation_values_types_and_image_context_never_fallback(self):
        image = self.reader.image
        del self.reader.image
        with self.assertRaisesRegex(ValueError, 'INVENTORY_PREPARED_READER_IMAGE_REQUIRED'):
            i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        self.reader.image = image
        real_digest = observe.digest
        with patch.object(observe, 'digest', side_effect=lambda p: '0' * 64 if p == image else real_digest(p)):
            with self.assertRaisesRegex(ValueError, 'INVENTORY_EXACT_CLONE_SOURCE_REQUIRED'):
                i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        self.reader.image = Path(self.temp.name) / 'missing-image.exe'
        with self.assertRaises(OSError): i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        self.reader.image = image
        original = copy.deepcopy(self.memory.c)
        class IntCopy(int): pass
        modes = ('program', 'sdk', 'sha', 'size', 'size_type', 'target', 'target_type',
                 'quit_absent', 'quit_bool', 'quit_extra', 'scenes_tuple')
        def mutate(mode):
            c = self.memory.c
            if mode == 'program': c['original_program'] += '.wrong'
            elif mode == 'sdk': c['SDK_program'] += '.wrong'
            elif mode == 'sha': c['original_sha256'] = '0' * 64
            elif mode == 'size': c['image_size'] -= 1
            elif mode == 'size_type': c['image_size'] = IntCopy(c['image_size'])
            elif mode == 'target': c['tables']['GameState'][0]['targets'][4] += 1
            elif mode == 'target_type': c['tables']['GameState'][0]['targets'][4] = IntCopy(0x6cfa3)
            elif mode == 'quit_absent': c['scenes'] = [r for r in c['scenes'] if r['kind'] != 'Quit']
            elif mode == 'scenes_tuple': c['scenes'] = tuple(c['scenes'])
            else:
                quit_row, = [r for r in c['scenes'] if r['kind'] == 'Quit']
                if mode == 'quit_bool': quit_row['state_id'] = True
                else: quit_row['extra'] = 1
        for phase in ('before', 'after'):
            for mode in modes:
                self.memory.c.clear(); self.memory.c.update(copy.deepcopy(original))
                self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
                count = len(self.memory.calls)
                if phase == 'before': mutate(mode)
                else:
                    def during(at, size, raw):
                        if at == self.memory.header: mutate(mode)
                        return raw
                    self.memory.fault = during
                reason = ('public_vtable_changed' if phase == 'after' and mode == 'target'
                          else 'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED')
                with self.subTest(phase=phase, mode=mode), self.assertRaisesRegex(ValueError, reason):
                    await self.check()
                self.assertFalse(self.service._claimed)
                if phase == 'before': self.assertEqual(len(self.memory.calls), count)
                self.memory.fault = None
        self.memory.c.clear(); self.memory.c.update(original)
        print('clone_augmentation_exact_before_after=22; missing_or_bad_image=STRICT; same_size_digest_mismatch=STRICT; raw_fallback=0')

    async def test_passive_current_typed_table_vector_and_double_read_stay_strict(self):
        original_data = dict(self.memory.data)
        contract, _, _ = i._source()
        table = self.memory.base + contract['owners']['Inventory']['rva']
        query = self.native.k.VirtualQueryEx
        for mode in ('table_page', 'heap_page', 'table_bytes', 'uid', 'vector', 'readback'):
            self.memory.data = dict(original_data)
            self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
            if mode in ('table_page', 'heap_page'):
                target = table if mode == 'table_page' else self.memory.player + 24
                def unreadable(handle, at, info, size):
                    result = query(handle, at, info, size)
                    if at == target: info._obj.protect = 1
                    return result
                self.native.k.VirtualQueryEx = unreadable
            elif mode == 'table_bytes':
                self.memory.fault = lambda at, size, raw: bytes([raw[0] ^ 1]) + raw[1:] if at == table else raw
            elif mode == 'uid': self.memory.put(self.memory.player + 24, '<Q', 99)
            elif mode == 'vector': self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500010, 0x500040)
            else:
                hits = [0]
                def changed(at, size, raw):
                    if at == self.memory.header:
                        hits[0] += 1
                        if hits[0] == 2: return raw[:-1] + bytes([raw[-1] ^ 1])
                    return raw
                self.memory.fault = changed
            with self.subTest(mode=mode), self.assertRaises(ValueError) as caught:
                await self.check()
            if mode.endswith('page'):
                self.assertIs(type(caught.exception), i.PreWriteReadRefusal)
                self.assertEqual(caught.exception.refused_read['at'], target)
            self.assertFalse(self.service._claimed)
            self.native.k.VirtualQueryEx = query
            self.memory.fault = None
        self.memory.data = original_data
        print('passive_live_table_heap_pages=STRICT; table_bytes_uid_vector_readback=STRICT; write=0')

    async def test_empty_list_shape_duplicate_owner_pending_scene_and_selected_uid_refuse(self):
        original = dict(self.memory.data)
        mutations = [lambda: self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500010, 0x500040),
            lambda: self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500000, 0x500001),
            lambda: self.memory.put(self.memory.header, '<QQQ', 0, 0, 0x500000),
            lambda: self.memory.put(self.memory.gi + self.memory.c['layout']['GI_begin'], '<QQ',
                                    self.memory.subsystems, self.memory.subsystems + 48),
            lambda: self.memory.put(self.memory.state + 0x370, '<QQ', 0x340000, 0x250000),
            lambda: self.memory.put(self.memory.player + 24, '<Q', 99)]
        for mutate in mutations:
            self.memory.data = dict(original); mutate()
            with self.assertRaises(ValueError): await self.check()
        self.memory.data = dict(original)
        self.memory.put(self.memory.subsystems + 64, '<QQ', self.memory.inventory, 0x250000)
        self.memory.put(self.memory.gi + self.memory.c['layout']['GI_begin'], '<QQ',
                        self.memory.subsystems, self.memory.subsystems + 80)
        with self.assertRaisesRegex(ValueError, 'UNIQUE_REGISTERED_OWNER'): await self.check()
        self.memory.data = dict(original)
        self.memory.put(self.memory.header, '<QQQ', 0, 0, 0)
        self.assertIsNone(await self.check())

    async def test_source_header_races_partial_budget_and_method_tamper_refuse(self):
        contract, _, core = i._source()
        source_at = self.memory.base + contract['owners']['Inventory']['rva']
        for target, hit, partial in ((source_at, 1, False), (source_at, 2, False),
                (self.memory.header, 2, False), (self.memory.header, 1, True)):
            hits = [0]
            def fault(at, size, raw):
                if at == target:
                    hits[0] += 1
                    if hits[0] == hit:
                        return raw[:-1] if partial else bytes([raw[0] ^ 1]) + raw[1:]
                return raw
            self.memory.fault = fault
            with self.assertRaises(ValueError): await self.check()
        self.memory.fault = None
        with patch.object(i, 'BYTE_LIMIT', 100):
            with self.assertRaisesRegex(ValueError, 'BYTE_BUDGET'): await self.check()
        self.memory.s.route = lambda: ()
        with self.assertRaises(ValueError): await self.check()
        del self.memory.s.route
        self.assertIsNone(await self.check())

    async def test_selection_claim_peer_and_retained_owner_change_during_query_refuse(self):
        selected = dict(self.realm.registry.selected)
        claims = dict(self.producer._claims)
        initial_peer = dict(self.row['peer'])
        mutations = [lambda: self.realm.registry.selected.clear(), lambda: self.producer._claims.clear(),
            lambda: self.row['peer'].update(connection_id=5),
            lambda: setattr(self.reader.member, 'process', object())]
        for mutation in mutations:
            fired = [False]
            def fault(at, size, raw):
                if at == self.memory.header and not fired[0]:
                    fired[0] = True; mutation()
                return raw
            self.memory.fault = fault
            with self.assertRaises(ValueError): await self.check()
            self.realm.registry.selected.update(selected); self.producer._claims.update(claims)
            self.row['peer'].clear(); self.row['peer'].update(initial_peer)
            self.reader.member.process = self.policy.handle
        self.memory.fault = None
        self.reader.validate = lambda: True
        with self.assertRaises(ValueError): await self.check()
        del self.reader.validate
        self.assertIsNone(await self.check())

    async def test_same_session_selection_copied_into_other_real_registry_refuses(self):
        original = self.realm.registry
        replacement = type(original)()
        replacement._sessions = dict(original._sessions)
        replacement.selected = dict(original.selected)
        fired = [False]
        def fault(at, size, raw):
            if at == self.memory.header and not fired[0]:
                fired[0] = True
                self.realm.registry = replacement
            return raw
        self.memory.fault = fault
        with self.assertRaisesRegex(ValueError, 'SAME_REGISTERED_SESSION'):
            await self.check()
        self.assertFalse(self.service._claimed)
        self.assertTrue(fired[0])
        self.assertIs(replacement.resolve(self.writer), original.resolve(self.writer))
        self.assertIs(replacement.selected[self.realm.profile_name],
                      original.selected[self.realm.profile_name])

    async def test_explicit_optin_lock_cadence_close_and_source_pin_refuse(self):
        with self.assertRaises(TypeError): i.InventoryService(self.producer, self.reader)
        with self.assertRaises(ValueError): i.InventoryService(self.producer, self.reader, policy=None)
        with self.assertRaises(ValueError):
            self.service.validate_pre_write_locked(self.writer, self.row, self.wire, now_ns=0)
        for now in (True, 0, -1):
            with self.assertRaises(ValueError):
                self.service.validate_pre_write_locked(self.writer, self.row, self.wire, now_ns=now)
        pins = dict(i.SOURCE_PINS); pins[i.EVIDENCE] = '0' * 64
        with patch.object(i, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            await self.check()
        self.service.close()
        with self.assertRaisesRegex(ValueError, 'LIFETIME'): await self.check()

    async def test_cancel_requested_without_yield_by_read_refuses_before_admission(self):
        async def run():
            task = asyncio.current_task()
            def fault(at, size, raw):
                if at == self.memory.header: task.cancel()
                return raw
            self.memory.fault = fault
            try:
                await self.check()
            except asyncio.CancelledError:
                self.assertFalse(self.service._claimed)
                self.assertEqual(self.service.last_result['reason'], 'INVENTORY_CALLER_CANCELLED')
                raise
            self.fail('cancelled synchronous callback admitted an item')
        task = asyncio.create_task(run())
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(self.service._closed)
        self.assertEqual((self.memory.s.bytes, self.memory.s.read_limit, self.memory.s.total), (77, 8192, 900))
        self.writer.write.assert_not_called()


class QueryGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await GateTests.asyncSetUp(self)

    async def check(self):
        return await GateTests.check(self)

    async def test_passive_empty_query_omits_getters_and_preserves_typed_recheck(self):
        contract, _, core = i._source()
        checks = self.service._checks(self.memory.s, contract, core)
        all_inventory = set(rva for rows in i.INVENTORY_SOURCE_ROLES.values() for rva in rows)
        selected = set()
        self.assertTrue(set(i.INVENTORY_SOURCE_ROLES['registered_getter']) <= all_inventory)
        self.assertEqual(set(r['rva'] for r in checks) & all_inventory, selected)
        self.assertEqual(len(checks), 49)
        original_query = self.native.k.VirtualQueryEx
        self.addCleanup(setattr, self.native.k, 'VirtualQueryEx', original_query)
        requested = []
        def no_handler_pages(handle, at, info, size):
            result = original_query(handle, at, info, size)
            requested.append(at - self.memory.base)
            if at - self.memory.base in all_inventory - selected:
                info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = no_handler_pages
        self.assertIsNone(await self.check())
        self.assertTrue(self.service._claimed)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.assertEqual(sum(size for _, size in self.memory.calls), 1857)
        self.assertFalse(set(requested) & (all_inventory - selected))
        self.native.k.VirtualQueryEx = original_query
        def fresh():
            self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        counterexamples = 0
        # An unchanged required base guard remains strict on both sides.
        for rva in (contract['owners']['Inventory']['rva'],):
            for hit in (1, 2):
                for unreadable in (True, False):
                    fresh(); hits = [0]
                    if unreadable:
                        def query(handle, at, info, size):
                            result = original_query(handle, at, info, size)
                            if at == self.memory.base + rva:
                                hits[0] += 1
                                if hits[0] == hit: info._obj.protect = 1
                            return result
                        self.native.k.VirtualQueryEx = query
                    else:
                        def fault(at, size, raw):
                            if at == self.memory.base + rva:
                                hits[0] += 1
                                if hits[0] == hit: return bytes([raw[0] ^ 1]) + raw[1:]
                            return raw
                        self.memory.fault = fault
                    expected = ('region_not_readable' if unreadable else
                                'WORLD_VTABLE_SOURCE_CHANGED' if hit == 1 else 'EDGE_TYPED_READ_CHANGED')
                    with self.assertRaisesRegex(ValueError, expected):
                        await self.check()
                    self.assertFalse(self.service._claimed)
                    if unreadable:
                        self.assertEqual(self.service.last_pre_write_stage,
                                         'INVENTORY_TYPED' if hit == 1 else 'FINAL_READBACK')
                    counterexamples += 1
                    self.native.k.VirtualQueryEx = original_query
                    self.memory.fault = None
        original_data = dict(self.memory.data)
        for kind in ('capacity', 'nonempty', 'recheck'):
            fresh(); self.memory.data = dict(original_data)
            if kind == 'capacity': self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500000, 0x500001)
            elif kind == 'nonempty': self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500010, 0x500040)
            else:
                hits = [0]
                def changed(at, size, raw):
                    if at == self.memory.header:
                        hits[0] += 1
                        if hits[0] == 2: return raw[:-1] + bytes([raw[-1] ^ 1])
                    return raw
                self.memory.fault = changed
            with self.assertRaises(ValueError): await self.check()
            self.assertFalse(self.service._claimed)
            self.memory.fault = None
        self.memory.data = dict(original_data)
        fresh()
        self.memory.put(self.memory.inventory, '<Q', self.memory.base + 0x11819f0)
        with self.assertRaises(ValueError): await self.check()
        self.assertFalse(self.service._claimed)
        self.memory.data = dict(original_data)
        fresh()
        table_at = self.memory.base + contract['owners']['Inventory']['rva']
        self.memory.fault = lambda at, size, raw: bytes([raw[0] ^ 1]) + raw[1:] if at == table_at else raw
        with self.assertRaises(ValueError): await self.check()
        self.assertFalse(self.service._claimed)
        self.memory.fault = None
        fresh()
        pins = dict(i.SOURCE_PINS); pins[i.PROOF] = '0' * 64
        calls = len(self.memory.calls)
        with patch.object(i, 'SOURCE_PINS', pins), self.assertRaisesRegex(ValueError, 'INVENTORY_SOURCE_CHANGED'):
            await self.check()
        self.assertEqual(len(self.memory.calls), calls)
        self.assertFalse(self.service._claimed)
        print('inventory_source_descriptors=49; inventory_selected=0; getter_reads=0; positive_bytes=1857; required_base_refusals=' + str(counterexamples) + '; typed_vector_refusals=3; inventory_type_table_source_refusals=3')


class PlayerGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await GateTests.asyncSetUp(self)

    async def check(self):
        return await GateTests.check(self)

    async def test_static_init_split_keeps_current_code_type_uid_and_once_strict(self):
        contract, _, core = i._source()
        checks = self.service._checks(self.memory.s, contract, core)
        init = set(i.PLAYER_ALLOCATION_INIT_RVAS)
        current = set(i.PLAYER_CURRENT_CHECK_RVAS)
        self.assertEqual(init, {0xc26e6, 0xc26ec, 0xc26f3})
        self.assertEqual(len(current), 20)
        self.assertTrue(current <= set(r['rva'] for r in checks))
        self.assertFalse(init & set(r['rva'] for r in checks))
        self.assertEqual(len(checks), 49)
        original = self.native.k.VirtualQueryEx
        queried = []
        def no_init(handle, at, info, size):
            result = original(handle, at, info, size)
            queried.append(at - self.memory.base)
            if at - self.memory.base in init:
                info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = no_init
        self.assertIsNone(await self.check())
        self.assertFalse(init & set(queried))
        self.assertTrue(self.service._claimed)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        with self.assertRaisesRegex(ValueError, 'ONE_SEND_ONLY'):
            await self.check()
        self.native.k.VirtualQueryEx = original
        def fresh():
            self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        for rva in i.PLAYER_CURRENT_CHECK_RVAS:
            fresh()
            check, = [r for r in self.service.proof.public['Player']['source_checks'] if r['rva'] == rva]
            check['sha256'] = '0' * 64
            calls = len(self.memory.calls)
            with self.subTest(rva=hex(rva)), self.assertRaisesRegex(ValueError, 'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED'):
                await self.check()
            self.assertEqual(len(self.memory.calls), calls)
            self.assertFalse(self.service._claimed)
        saved = dict(self.memory.data)
        for at, value in ((self.memory.player, self.memory.base + 0x11819f8),
                          (self.memory.player + 24, 99)):
            fresh(); self.memory.data = dict(saved)
            self.memory.put(at, '<Q', value)
            with self.assertRaises(ValueError): await self.check()
            self.assertFalse(self.service._claimed)
        self.memory.data = saved
        print('player_init3_queries=0; current20_source_cache_refusals=20; current_type_uid_refusals=2; descriptors=49; bytes=1857; once=STRICT')


class MapGuardTests(unittest.IsolatedAsyncioTestCase):
    """Current Map proof selection with unchanged original typed/code reads."""
    async def asyncSetUp(self):
        await GateTests.asyncSetUp(self)

    async def check(self):
        return await GateTests.check(self)

    async def test_init_path_is_not_queried_but_current_code_and_typed_map_stay_strict(self):
        contract, _, core = i._source()
        checks = self.service._checks(self.memory.s, contract, core)
        original = self.memory.native.k.VirtualQueryEx
        queried = []
        def query(handle, at, info, size):
            result = original(handle, at, info, size)
            queried.append(at)
            # The original Native.read still rejects PAGE_NOACCESS. No code
            # path waives that refusal; this query never asks for init anchors.
            if at - self.memory.base in i.MAP_ALLOCATION_INIT_RVAS + i.MAP_CURRENT_CHECK_RVAS:
                info._obj.protect = 1
            return result
        self.native.k.VirtualQueryEx = query
        initial_data = dict(self.memory.data)
        map_rows = {r['rva']: r for r in core if r['rva'] in i.MAP_CURRENT_CHECK_RVAS}
        self.assertEqual(set(map_rows), set(i.MAP_CURRENT_CHECK_RVAS))
        self.assertFalse(set(r['rva'] for r in checks) & set(i.MAP_ALLOCATION_INIT_RVAS))
        self.assertEqual(len(checks), 49)
        self.assertIsNone(await self.check())
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.assertFalse(any(self.memory.base + 0x530000 <= at < self.memory.base + 0x532000 for at in queried))
        # Positive admission consumed only this fixture's service; current Map
        # source descriptors remain exact even though function bodies are cold.
        def fresh():
            self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        for rva in i.MAP_CURRENT_CHECK_RVAS:
            fresh()
            check, = [r for r in self.service.proof.public['Map']['source_checks'] if r['rva'] == rva]
            check['sha256'] = '0' * 64
            calls = len(self.memory.calls)
            with self.assertRaisesRegex(ValueError, 'INVENTORY_PASSIVE_SOURCE_CACHE_CHANGED'): await self.check()
            self.assertEqual(len(self.memory.calls), calls)
            self.assertFalse(self.service._claimed)
        # The live 718/71C/context0 values, unique typed owner/table and final
        # readbacks remain on the original _world path, not a static fallback.
        for at in (0x310000 + 0x718, 0x310000 + 0x71c, 0x330000):
            fresh(); self.memory.data = dict(initial_data)
            self.memory.put(at, '<i', 1)
            with self.assertRaisesRegex(ValueError, 'EDGE_CURRENT_UID_MAP_MISMATCH'): await self.check()
            self.assertFalse(self.service._claimed)
        self.memory.data = initial_data
        print('map_source_descriptors=49; code_queries=0; positive_typed_bytes=1857; current_map_cache_refusals=6; current_map_data_refusals=3')


class ReadabilityTests(unittest.IsolatedAsyncioTestCase):
    """Original Native.read page checks; only VirtualQueryEx page facts vary."""
    async def asyncSetUp(self):
        await GateTests.asyncSetUp(self)

    async def check(self):
        return await GateTests.check(self)

    async def test_physical_unreadable_pages_are_typed_and_keep_fixed_stage(self):
        contract, _, core = i._source()
        checks = self.service._checks(self.memory.s, contract, core)
        base = self.memory.base
        cases = [(base + contract['owners']['Inventory']['rva'], 1, 'INVENTORY_TYPED'),
                 (self.memory.player + 24, 1, 'WORLD_TYPED'),
                 (self.memory.header, 1, 'EMPTY_VECTOR'),
                 (self.memory.header, 2, 'FINAL_READBACK'),
                 (self.memory.state + 0x360, 4, 'ROOT_RECHECK'),
                 (base + contract['owners']['Inventory']['rva'], 2, 'FINAL_READBACK')]
        original_query = self.native.k.VirtualQueryEx
        evidence = []
        for target, hit, expected in cases:
            calls = [0]
            def query(handle, at, info, size):
                value = original_query(handle, at, info, size)
                if at == target:
                    calls[0] += 1
                    if calls[0] == hit:
                        info._obj.protect = 1  # Native.read itself raises its original Unknown.
                return value
            self.native.k.VirtualQueryEx = query
            with self.assertRaises(i.PreWriteReadRefusal) as caught:
                await self.check()
            error = caught.exception
            self.assertIsInstance(error, ValueError)
            self.assertEqual((error.reason, error.stage, error.args, str(error)),
                             ('region_not_readable', expected, ('region_not_readable',), 'region_not_readable'))
            self.assertEqual(observe.reason(error), 'region_not_readable')
            self.assertEqual(set(error.__dict__), {'reason', 'stage', '_refused_read'})
            self.assertIs(type(error._refused_read), tuple)
            self.assertEqual(self.service.last_pre_write_stage, expected)
            self.assertEqual(self.service.last_result['status'], 'UNKNOWN')
            self.assertEqual(self.service.last_result['reason'], 'region_not_readable')
            self.assertFalse(self.service._claimed)
            self.assertEqual(self.native.last_region['protection'], 1)
            evidence.append(dict(stage=error.stage, typed_bytes=self.service.last_result['typed_bytes_requested']))
        self.native.k.VirtualQueryEx = original_query
        print('physical_unreadable_stages=' + str(evidence))

    async def test_exact_physical_refusal_keeps_immutable_request_region_without_extra_reads(self):
        contract, _, core = i._source()
        checks = self.service._checks(self.memory.s, contract, core)
        unknown = self.native.read.__func__.__globals__['Unknown']
        original_init, original_query = unknown.__init__, self.native.k.VirtualQueryEx
        for target, expected_size, expected_base in (
                (self.memory.base + contract['owners']['Inventory']['rva'], 24, self.memory.base),
                (self.memory.player + 24, 8, None)):
            captured, queries = [], []
            def capture(error, *args, **kwargs):
                original_init(error, *args, **kwargs)
                captured.append(error)
            def unreadable(handle, at, info, size):
                result = original_query(handle, at, info, size)
                queries.append(at)
                if at == target: info._obj.protect = 1
                return result
            self.native.k.VirtualQueryEx = unreadable
            rpm_before = self.native.rpm_attempts
            with patch.object(unknown, '__init__', capture), self.assertRaises(i.PreWriteReadRefusal) as caught:
                await self.check()
            error = caught.exception
            self.assertEqual(len(captured), 1)
            self.assertIs(type(captured[0]), unknown)
            region = captured[0].region
            expected = dict(region, at=target, size=expected_size, image_base=expected_base)
            self.assertEqual(set(expected), {'state', 'protection', 'type', 'guard', 'length_fits',
                'image_allocation_matches', 'requested_bytes', 'at', 'size', 'image_base'})
            self.assertEqual((error.reason, error.args, str(error)),
                             ('region_not_readable', ('region_not_readable',), 'region_not_readable'))
            self.assertEqual(error.refused_read, expected)
            self.assertEqual(self.service.last_result['refused_read'], expected)
            self.assertIsNot(self.service.last_result['refused_read'], error.refused_read)
            self.assertIsNot(error.refused_read, error.refused_read)
            self.assertIs(type(error._refused_read), tuple)
            with self.assertRaises(TypeError): error._refused_read[0] = 0
            region['protection'] = 0x40
            captured[0].region = dict(region, state=0)
            self.native.last_region = dict(region, requested_bytes=4096)
            projection = error.refused_read
            projection['at'] = 0
            self.service.last_result['refused_read']['protection'] = 0
            self.assertEqual(error.refused_read, expected)
            self.assertEqual(len(queries), self.service.last_result['typed_read_requests'])
            self.assertEqual(self.native.rpm_attempts - rpm_before, len(queries) - 1)
            self.assertEqual(queries[-1], target)
            self.assertFalse(self.service._claimed or self.service._closed)
        self.native.k.VirtualQueryEx = original_query
        self.assertIsNone(i.PreWriteReadRefusal('region_not_readable', 'WORLD_TYPED').refused_read)
        print('refused_read_snapshot=image_and_heap; exact_unknown=2; immutable_projection=PASS; extra_native_reads=0')

    async def test_missing_or_malformed_region_preserves_original_refusal_and_exact_unknown_scope(self):
        contract, _, core = i._source()
        target = self.memory.base + contract['owners']['Inventory']['rva']
        unknown = self.native.read.__func__.__globals__['Unknown']
        original_init, original_query = unknown.__init__, self.native.k.VirtualQueryEx
        for mode in ('missing', 'none', 'list', 'extra', 'missing_key', 'bad_int',
                     'bad_bool', 'bad_nullable', 'wrong_width'):
            def capture(error, *args, **kwargs):
                original_init(error, *args, **kwargs)
                if mode == 'missing': del error.region
                elif mode == 'none': error.region = None
                elif mode == 'list': error.region = []
                elif mode == 'extra': error.region['extra'] = 1
                elif mode == 'missing_key': del error.region['state']
                elif mode == 'bad_int': error.region['state'] = True
                elif mode == 'bad_bool': error.region['guard'] = 0
                elif mode == 'bad_nullable': error.region['image_allocation_matches'] = None
                else: error.region['requested_bytes'] += 1
            def unreadable(handle, at, info, size):
                result = original_query(handle, at, info, size)
                if at == target: info._obj.protect = 1
                return result
            self.native.k.VirtualQueryEx = unreadable
            with self.subTest(mode=mode), patch.object(unknown, '__init__', capture), self.assertRaises(i.PreWriteReadRefusal) as caught:
                await self.check()
            error = caught.exception
            self.assertEqual((error.reason, error.stage, error.args),
                ('region_not_readable', 'INVENTORY_TYPED', ('region_not_readable',)))
            self.assertIsNone(error.refused_read)
            self.assertIsNone(self.service.last_result['refused_read'])
            self.assertFalse(self.service._claimed or self.service._closed)
        class OtherUnknown(unknown): pass
        original = OtherUnknown('region_not_readable')
        def subclass_error(handle, at, info, size):
            if at == target: raise original
            return original_query(handle, at, info, size)
        self.native.k.VirtualQueryEx = subclass_error
        with self.assertRaisesRegex(ValueError, 'region_not_readable') as caught:
            await self.check()
        self.assertIs(type(caught.exception), ValueError)
        self.assertIsNone(self.service.last_result['refused_read'])
        self.native.k.VirtualQueryEx = original_query
        print('refused_read_invalid_metadata=9; exact_unknown_subclass_not_promoted=PASS; original_reason_args_stage=PASS')

    async def test_other_physical_guard_refusals_and_same_reason_context_remain_plain(self):
        contract, _, core = i._source()
        first = self.memory.base + contract['owners']['Inventory']['rva']
        original_query = self.native.k.VirtualQueryEx
        for field, value, expected in (('state', 0x2000, 'region_not_committed_or_short'),
                                      ('type', 0x20000, 'module_allocation_mismatch')):
            def query(handle, at, info, size):
                result = original_query(handle, at, info, size)
                if at == first: setattr(info._obj, field, value)
                return result
            self.native.k.VirtualQueryEx = query
            with self.assertRaisesRegex(ValueError, expected) as caught:
                await self.check()
            self.assertIs(type(caught.exception), ValueError)
            self.assertFalse(self.service._claimed)
        self.native.k.VirtualQueryEx = original_query
        self.memory.fault = lambda at, size, raw: (bytes([raw[0] ^ 1]) + raw[1:]) if at == first else raw
        with self.assertRaisesRegex(ValueError, 'WORLD_VTABLE_SOURCE_CHANGED') as caught:
            await self.check()
        self.assertIs(type(caught.exception), ValueError)
        self.memory.fault = None
        with patch.object(i, 'BYTE_LIMIT', 100), self.assertRaisesRegex(ValueError, 'INVENTORY_BYTE_BUDGET') as caught:
            await self.check()
        self.assertIs(type(caught.exception), ValueError)
        # Identical reason from file/authority code must not become a physical
        # unreadability type, even when it is the Native Unknown class itself.
        unknown = self.native.read.__func__.__globals__['Unknown']
        for error in (ValueError('region_not_readable'), unknown('region_not_readable')):
            with patch.object(self.service, '_current', side_effect=error):
                with self.assertRaisesRegex(ValueError, 'region_not_readable') as caught:
                    await self.check()
                self.assertIs(type(caught.exception), ValueError)
                self.assertEqual(self.service.last_pre_write_stage, 'AUTHORITY_BEFORE')
        with patch.object(i, '_source', side_effect=ValueError('region_not_readable')):
            with self.assertRaisesRegex(ValueError, 'region_not_readable') as caught:
                await self.check()
            self.assertIs(type(caught.exception), ValueError)
            self.assertEqual(self.service.last_pre_write_stage, 'SOURCE_BEFORE')

    async def test_success_keeps_same_original_byte_budget_order_and_admission(self):
        self.assertIsNone(await self.check())
        result = self.service.last_result
        self.assertEqual(result['typed_bytes_requested'], 1857)
        self.assertEqual(result['typed_bytes_requested'], sum(size for _, size in self.memory.calls))
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertTrue(self.service._claimed)
        self.assertEqual(self.service.last_pre_write_stage, 'SOURCE_AFTER')
        print('readability_success_typed_bytes=' + str(result['typed_bytes_requested']))
        with self.assertRaisesRegex(ValueError, 'ONE_SEND_ONLY'):
            await self.check()


class PrewriteDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await GateTests.asyncSetUp(self)

    async def changed(self, at, hit, phase, stage):
        hits = []
        def fault(address, size, raw):
            if address == at:
                hits.append(1)
                if len(hits) == hit:
                    return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = fault
        with self.assertRaisesRegex(ValueError, '^EDGE_TYPED_READ_CHANGED$') as caught:
            await GateTests.check(self)
        self.assertIs(type(caught.exception), ValueError)
        result = self.service.last_result
        diagnostic = result['changed_read']
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual((diagnostic['comparison'], diagnostic['stage']), (phase, stage))
        self.assertEqual(set(diagnostic), {'stage', 'comparison', 'request_ordinal',
            'record_ordinal', 'record_count', 'requested_width', 'typed_bytes_requested', 'image'})
        self.assertTrue(1 <= diagnostic['record_ordinal'] <= diagnostic['record_count'])
        self.assertTrue(diagnostic['request_ordinal'] <= result['typed_read_requests'])
        self.assertEqual(diagnostic['typed_bytes_requested'], result['typed_bytes_requested'])
        self.assertEqual(result['typed_bytes_requested'], sum(size for _, size in self.memory.calls))
        self.assertFalse(self.service._claimed)
        self.assertNotIsInstance(caught.exception, i.PreWriteReadRefusal)

    async def test_initial_duplicate_keeps_strict_refusal_and_bounded_metadata(self):
        await self.changed(0x250008, 2, 'INITIAL', 'WORLD_TYPED')

    async def test_world_readback_keeps_strict_refusal_and_bounded_metadata(self):
        await self.changed(self.memory.header, 2, 'WORLD_READBACK', 'FINAL_READBACK')

    async def test_budget_readback_keeps_strict_refusal_and_bounded_metadata(self):
        at = self.memory.base + self.memory.c['layout']['Root_slot_rva']
        await self.changed(at, 2, 'BUDGET_READBACK', 'FINAL_READBACK')

    async def test_success_preserves_exact_original_read_trace(self):
        original = i._ReadBudget.read
        # Reference is the unchanged parent implementation plus original byte
        # budget/stage guards; no diagnostic comparison can add a native read.
        def reference(budget, at, size, image=False):
            i.need(type(size) is int and budget.spent + size <= i.BYTE_LIMIT, 'INVENTORY_BYTE_BUDGET')
            if budget._stage in ('CODE_GUARD_BEFORE', 'CODE_GUARD_AFTER'):
                budget._ordinal += 1
                budget._service.last_pre_write_stage = f'{budget._stage}_{budget._ordinal:04d}'
            return i.edge._Budget.read(budget, at, size, image)
        with patch.object(i._ReadBudget, 'read', reference):
            await GateTests.check(self)
        trace = list(self.memory.calls)
        self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY)
        self.memory.calls.clear()
        self.assertIs(i._ReadBudget.read, original)
        await GateTests.check(self)
        self.assertEqual(self.memory.calls, trace)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.assertEqual(self.service.last_result['typed_read_requests'], len(trace))
        self.assertIsNone(self.service.last_result['changed_read'])


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    """Canonical Service/real TempStore; no class or source-pin replacement."""
    async def asyncSetUp(self):
        await GateTests.asyncSetUp(self)
        self.store = stores.InventoryStore(self.realm.store.path, policy=stores.POLICY)

    async def test_default_none_original_contract_and_no_sidecar(self):
        self.assertIs(type(self.service), i.InventoryService)
        async with self.row['operation_lock']:
            before = self.service._current(self.writer, self.row)
        self.assertEqual(len(before[1]), 24)
        self.assertIs(before[1][16], self.row)
        self.assertIs(before[1][18], self.row['operation_lock'])
        await self.check()
        self.assertEqual(self.service.last_result['status'], 'OBSERVED')
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.assertTrue(self.service.last_result['source_contract_valid'])
        self.assertFalse(self.store.path.exists())
        print('canonical_default_none_current_positive=PASS; same_current_typed_trace_reused; codebody_queries=0; bytes=1857')

    def fresh(self, *, enabled=True, restore_only=False):
        self.service = i.InventoryService(self.producer, self.reader, policy=i.POLICY,
                                          store=self.store if enabled else None)
        self.producer._inventory_service = self.service
        self.producer._inventory_attempted = True
        self.producer._inventory_write_attempted = False
        self.producer._inventory_delivery_authority = None
        self.producer._inventory_frame = self.producer._inventory_operation_frame = self.wire
        self.producer._inventory_prewrite_refusal = None
        self.producer._inventory_deadline_ns = time.monotonic_ns() + 10_000_000_000
        self.producer._inventory_admission_clock_ns = None
        self.producer._inventory_restore_only = restore_only
        self.producer._inventory_restored = restore_only
        self.producer._inventory_store = self.store if enabled else None
        game = self.realm.registry.resolve(self.writer)
        self.producer._inventory_selection_binding = (self.writer, self.row,
            self.row['operation_lock'], self.realm, self.realm.registry, game,
            self.realm.service(self.writer), game.selection, self.service,
            self.producer._inventory_store, self.wire)

        self.assertIs(type(self.service), i.InventoryService)
        self.assertIs(type(self.producer), b.PersistentBroker)
        self.assertIs(self.producer._inventory_service, self.service)

    async def check(self, wire=None):
        return await GateTests.check(self, wire)


    def reset_temp_sidecar(self):
        # Each counterexample is an independent fixture operation, never a
        # product retry. Only this test-owned temporary file can be removed.
        self.assertEqual(self.store.path.parent, Path(self.temp.name))
        if self.store.path.exists(): self.store.path.unlink()


    async def assert_no_current_retry(self):
        self.assertTrue(self.service._closed)
        before = len(self.memory.calls)
        with self.assertRaises(ValueError): await self.check()
        self.assertEqual(len(self.memory.calls), before)
        self.writer.write.assert_not_called()


    async def test_real_durable_grant_reuses_original_suffix_and_reads(self):
        await self.check()
        baseline = list(self.memory.calls)
        self.memory.calls.clear(); self.fresh()
        real_sync = stores.os.fsync
        index = []
        def synced(fd):
            index.append(len(self.memory.calls))
            self.assertTrue(self.row['operation_lock'].locked() and self.service._inflight)
            self.assertFalse(self.service._claimed)
            self.assertEqual(self.memory.calls[-1], (self.memory.header, 24))
            real_sync(fd)
        with patch.object(stores.os, 'fsync', synced): await self.check()
        self.assertEqual(len(index), 1)
        self.assertTrue(self.memory.calls == baseline)
        self.assertTrue(0 < index[0] < len(baseline))
        self.assertTrue(self.store.restore(self.realm.profile_uid) == self.wire)
        self.assertNotEqual(self.realm.profile_uid, i.validate_frame(self.wire).identifier)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        self.assertTrue(self.service._claimed and not self.service._closed)
        with self.assertRaisesRegex(ValueError, 'ONE_SEND_ONLY'): await self.check()
        print('canonical_persistence_persisted_frame=PASS; grant_after_empty_before_original_suffix=PASS; extra_native_reads=0; bytes=1857')

    async def test_restore_only_existing_row_uses_real_grant_without_write_or_extra_reads(self):
        await self.check()
        baseline = list(self.memory.calls)
        self.store.grant(self.realm.profile_uid, self.wire)
        prior = self.store.path.read_bytes()
        self.memory.calls.clear(); self.fresh(restore_only=True)
        with patch.object(stores.InventoryStore, '_write', side_effect=AssertionError('unexpected write')):
            await self.check()
        self.assertEqual(self.memory.calls, baseline)
        self.assertEqual(self.store.path.read_bytes(), prior)
        self.assertTrue(self.service._claimed and not self.service._closed)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)

    async def test_restore_only_missing_and_deleted_selected_rows_never_recreated(self):
        for mode in ('missing', 'deleted_file', 'deleted_row'):
            self.reset_temp_sidecar()
            if mode != 'missing': self.store.grant(self.realm.profile_uid, self.wire)
            self.fresh(restore_only=True)
            fired = [False]
            def fault(at, size, raw):
                if mode != 'missing' and at == self.memory.header and not fired[0]:
                    fired[0] = True
                    if mode == 'deleted_file': self.store.path.unlink()
                    else: self.store.path.write_text('{"version":1,"inventories":[]}\n', encoding='ascii')
                return raw
            self.memory.fault = fault
            with self.subTest(mode=mode), patch.object(stores.InventoryStore, '_write',
                    side_effect=AssertionError('unexpected write')):
                with self.assertRaisesRegex(ValueError, 'EXISTING_ROW_REQUIRED'): await self.check()
            self.assertFalse(self.service._claimed)
            self.assertIsNone(self.store.restore(self.realm.profile_uid))
            await self.assert_no_current_retry()
        self.memory.fault = None

    async def test_restore_only_mode_selection_and_owner_swaps_refuse_before_grant(self):
        self.store.grant(self.realm.profile_uid, self.wire)
        prior = self.store.path.read_bytes()
        selected = dict(self.realm.registry.selected)
        member_process = self.reader.member.process
        for mode in ('mode', 'selection', 'owner', 'selection_binding', 'helper', 'restored', 'broker_store'):
            self.fresh(restore_only=True)
            fired = [False]
            def fault(at, size, raw):
                if at == self.memory.header and not fired[0]:
                    fired[0] = True
                    if mode == 'mode': self.producer._inventory_restore_only = False
                    elif mode == 'selection': self.realm.registry.selected.clear()
                    elif mode == 'owner': self.reader.member.process = object()
                    elif mode == 'selection_binding': self.producer._inventory_selection_binding = tuple(list(
                        self.producer._inventory_selection_binding[:-1]) + [bytes(bytearray(self.wire))])
                    elif mode == 'helper': self.producer._inventory_selection_frame_current = lambda *_: None
                    elif mode == 'restored': self.producer._inventory_restored = False
                    else: self.producer._inventory_store = None
                return raw
            self.memory.fault = fault
            try:
                with self.subTest(mode=mode), patch.object(stores.InventoryStore, '_write',
                        side_effect=AssertionError('unexpected write')):
                    with self.assertRaises(ValueError): await self.check()
                self.assertFalse(self.service._claimed)
                self.assertEqual(self.store.path.read_bytes(), prior)
            finally:
                self.realm.registry.selected.clear(); self.realm.registry.selected.update(selected)
                self.reader.member.process = member_process
                self.producer.__dict__.pop('_inventory_selection_frame_current', None)
        self.memory.fault = None

    async def test_restore_mode_literal_bool_missing_and_store_required(self):
        for mode in (None, 0, 1, 'true'):
            self.fresh(); self.producer._inventory_restore_only = mode
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'RESTORE_MODE_CHANGED'):
                await self.check()
            self.assertFalse(self.store.path.exists() or self.service._claimed)
        self.fresh()
        # The broker facade has no deleter; corrupt the actual selected
        # generation field to exercise the same missing-mode refusal.
        del self.producer._inventory_generation.restore_only
        with self.assertRaises(ValueError): await self.check()
        self.fresh(enabled=False, restore_only=True)
        with self.assertRaisesRegex(ValueError, 'RESTORE_STORE_REQUIRED'): await self.check()
        self.assertFalse(self.store.path.exists() or self.service._claimed)

    async def test_restore_only_mode_changed_with_selected_file_deletion_cannot_fallback_to_grant(self):
        self.store.grant(self.realm.profile_uid, self.wire)
        self.fresh(restore_only=True)
        fired, grants = [], []
        def fault(at, size, raw):
            if at == self.memory.header and not fired:
                fired.append(1)
                self.producer._inventory_restore_only = False
                self.store.path.unlink()
            return raw
        self.memory.fault = fault
        import sys
        original_code, previous = stores.InventoryStore.grant.__code__, sys.gettrace()
        def trace(frame, event, arg):
            if event == 'call' and frame.f_code is original_code: grants.append(1)
            return trace
        try:
            sys.settrace(trace)
            with patch.object(stores.InventoryStore, '_write', side_effect=AssertionError('unexpected write')):
                with self.assertRaisesRegex(ValueError, 'RESTORE_MODE_CHANGED'): await self.check()
        finally:
            sys.settrace(previous)
            self.memory.fault = None
        self.assertEqual(fired, [1])
        self.assertEqual(grants, [])
        self.assertFalse(self.store.path.exists() or self.service._claimed)

    async def test_restore_only_mode_swap_during_real_grant_and_after_final_source_refuses(self):
        self.store.grant(self.realm.profile_uid, self.wire)
        prior = self.store.path.read_bytes()
        for stage in ('grant', 'source_after'):
            self.fresh(restore_only=True)
            original_read, original_source = self.store._read, i._source
            read_hits, source_hits = [], []
            def read():
                result = original_read()
                read_hits.append(1)
                self.producer._inventory_restore_only = False
                return result
            def source():
                result = original_source()
                source_hits.append(self.service.last_pre_write_stage)
                if self.service.last_pre_write_stage == 'SOURCE_AFTER':
                    self.producer._inventory_restore_only = False
                return result
            mutation = patch.object(self.store, '_read', read) if stage == 'grant' else patch.object(i, '_source', source)
            with self.subTest(stage=stage), mutation, patch.object(stores.InventoryStore, '_write',
                    side_effect=AssertionError('unexpected write')):
                with self.assertRaisesRegex(ValueError, 'RESTORE_MODE_CHANGED'): await self.check()
            if stage == 'grant': self.assertEqual(read_hits, [1])
            else: self.assertEqual(source_hits[-1], 'SOURCE_AFTER')
            self.assertEqual(self.store.path.read_bytes(), prior)
            self.assertFalse(self.service._claimed)
            await self.assert_no_current_retry()

    async def test_default_false_preserves_original_two_positional_grant_call(self):
        self.fresh()
        import ast, inspect, textwrap
        tree = ast.parse(textwrap.dedent(inspect.getsource(i.InventoryService.validate_pre_write_locked)))
        calls_ast = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == 'grant']
        legacy, = [node for node in calls_ast if not node.keywords]
        self.assertEqual(len(legacy.args), 2)
        calls = []
        original = stores.InventoryStore.grant.__code__
        def traced(frame, event, arg):
            if event == 'call' and frame.f_code is original:
                calls.append((frame.f_locals['character_uid'], frame.f_locals['frame'],
                              frame.f_locals['existing_only']))
            return traced
        import sys
        previous = sys.gettrace()
        try:
            sys.settrace(traced)
            await self.check()
        finally: sys.settrace(previous)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1], self.wire)
        self.assertIs(calls[0][2], False)
        self.assertTrue(self.store.restore(self.realm.profile_uid) == self.wire)


    async def test_exact_store_paths_uid_writer_frame_and_once_reservation_refuse(self):
        with self.assertRaisesRegex(ValueError, 'EXACT_STORE'):
            i.InventoryService(self.producer, self.reader, policy=i.POLICY, store=object())
        self.fresh()
        saved_profile, saved_path = self.store.profile, self.store.path
        saved_uid, saved_writer = self.realm.profile_uid, self.row['writer']
        modes = ('store', 'profile', 'path', 'uid', 'writer', 'frame', 'operation_frame',
                 'attempt', 'written', 'service', 'delivery', 'grant_method')
        for mode in modes:
            self.fresh()
            if mode == 'store': self.service.store = stores.InventoryStore(saved_profile, policy=stores.POLICY)
            elif mode == 'profile': self.store.profile = Path(str(saved_profile))
            elif mode == 'path': self.store.path = Path(str(saved_path))
            elif mode == 'uid': self.realm.profile_uid += 1
            elif mode == 'writer': self.row['writer'] = object()
            elif mode == 'frame': self.producer._inventory_frame = bytes(bytearray(self.wire))
            elif mode == 'operation_frame': self.producer._inventory_operation_frame = bytes(bytearray(self.wire))
            elif mode == 'attempt': self.producer._inventory_attempted = False
            elif mode == 'written': self.producer._inventory_write_attempted = True
            elif mode == 'service': self.producer._inventory_service = object()
            elif mode == 'delivery': self.producer._inventory_delivery_authority = object()
            elif mode == 'grant_method': self.store.grant = lambda *_: True
            try:
                with self.subTest(mode=mode), self.assertRaises(ValueError): await self.check()
                self.assertFalse(saved_path.exists())
                self.assertFalse(self.service._claimed)
            finally:
                self.store.profile, self.store.path = saved_profile, saved_path
                self.realm.profile_uid, self.row['writer'] = saved_uid, saved_writer
                self.store.__dict__.pop('grant', None)
        # Different actual character profile is rejected before a leaf exists.
        other = saved_profile.with_name('other-characters.json')
        other.write_bytes(saved_profile.read_bytes())
        foreign = stores.InventoryStore(other, policy=stores.POLICY)
        with self.assertRaisesRegex(ValueError, 'STORE_BINDING'):
            i.InventoryService(self.producer, self.reader, policy=i.POLICY, store=foreign)
        self.fresh()
        with self.assertRaises(ValueError): await self.check(bytes(bytearray(self.wire)))
        self.assertFalse(saved_path.exists())
        print('canonical_persistence_pregrant_binding_refusals=15; durable_rows_created=0')


    async def test_real_fstat_fsync_replace_failures_close_without_current_retry(self):
        for operation in ('fstat', 'fsync', 'replace'):
            self.reset_temp_sidecar(); self.fresh()
            with patch.object(stores.os, operation, side_effect=OSError('fixture file failure')):
                with self.subTest(operation=operation), self.assertRaises(ValueError): await self.check()
            self.assertFalse(self.store.path.exists() or self.service._claimed)
            await self.assert_no_current_retry()
        self.assertEqual(list(Path(self.temp.name).glob('.inventory-*.tmp')), [])
        print('canonical_persistence_grant_file_failures_terminal=3; current_retries=0; orphan_tmp=0')


    async def test_grant_then_typed_root_source_authority_binding_failure_keeps_row_terminal(self):
        initial_data, selected = dict(self.memory.data), dict(self.realm.registry.selected)
        profile, path = self.store.profile, self.store.path
        pins = dict(i.SOURCE_PINS)
        real_sync = stores.os.fsync
        modes = ('header', 'root', 'source', 'authority', 'proof', 'frame', 'operation_frame',
                 'store', 'profile', 'path', 'store_bound', 'table_after_unreadable')
        for mode in modes:
            self.store.profile, self.store.path = profile, path
            self.reset_temp_sidecar(); self.fresh()
            original_query = self.native.k.VirtualQueryEx
            code_at = self.memory.base + i._source()[0]['owners']['Inventory']['rva']
            after_grant = [False]
            def query(handle, at, info, size):
                result = original_query(handle, at, info, size)
                if mode == 'table_after_unreadable' and after_grant[0] and at == code_at: info._obj.protect = 1
                return result
            def synced(fd):
                real_sync(fd); after_grant[0] = True
                if mode == 'header': self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500010, 0x500040)
                elif mode == 'root': self.memory.put(self.memory.state + 0x370, '<QQ', 0x340000, 0x250000)
                elif mode == 'source': i.SOURCE_PINS[i.EVIDENCE] = '0' * 64
                elif mode == 'authority': self.realm.registry.selected.clear()
                elif mode == 'proof': self.service.proof = type(self.service.proof)(self.reader)
                elif mode == 'frame': self.producer._inventory_frame = bytes(bytearray(self.wire))
                elif mode == 'operation_frame': self.producer._inventory_operation_frame = bytes(bytearray(self.wire))
                elif mode == 'store': self.service.store = stores.InventoryStore(profile, policy=stores.POLICY)
                elif mode == 'profile': self.store.profile = Path(str(profile))
                elif mode == 'path': self.store.path = Path(str(path))
                elif mode == 'store_bound': self.service._store_bound = tuple(list(self.service._store_bound))
            self.native.k.VirtualQueryEx = query
            try:
                with patch.object(stores.os, 'fsync', synced):
                    with self.subTest(mode=mode), self.assertRaises(ValueError): await self.check()
                self.assertTrue(path.exists())
                self.assertFalse(self.service._claimed)
                if mode == 'table_after_unreadable':
                    self.assertEqual(self.service.last_pre_write_stage, 'FINAL_READBACK')
                self.store.profile, self.store.path = profile, path
                await self.assert_no_current_retry()
            finally:
                self.native.k.VirtualQueryEx = original_query
                self.memory.data = dict(initial_data)
                self.realm.registry.selected.clear(); self.realm.registry.selected.update(selected)
                self.store.profile, self.store.path = profile, path
                i.SOURCE_PINS.clear(); i.SOURCE_PINS.update(pins)
            self.assertTrue(self.store.restore(self.realm.profile_uid) == self.wire)
        print('canonical_persistence_postgrant_hard_refusals=12; complete_durable_row_retained=12; current_retries=0')


    async def test_cancel_during_real_grant_persists_but_never_claims_or_retries(self):
        self.fresh()
        real_sync = stores.os.fsync
        async def cancelled_leaf():
            task = asyncio.current_task()
            def synced(fd): real_sync(fd); task.cancel()
            with patch.object(stores.os, 'fsync', synced): await self.check()
        with self.assertRaises(asyncio.CancelledError): await asyncio.create_task(cancelled_leaf())
        self.assertTrue(self.store.restore(self.realm.profile_uid) == self.wire)
        self.assertFalse(self.service._claimed)
        await self.assert_no_current_retry()
        print('canonical_persistence_cancel_after_grant=terminal; durable_row_retained=1; sender_calls=0')

    async def test_postgrant_changed_read_diagnostic_preserves_durable_terminal(self):
        self.fresh()
        real_sync = stores.os.fsync
        def synced(fd):
            real_sync(fd)
            self.memory.put(self.memory.header, '<QQQ', 0x500000, 0x500010, 0x500040)
        with patch.object(stores.os, 'fsync', synced):
            with self.assertRaisesRegex(ValueError, '^EDGE_TYPED_READ_CHANGED$'):
                await self.check()
        diagnostic = self.service.last_result['changed_read']
        self.assertEqual((diagnostic['stage'], diagnostic['comparison']),
                         ('FINAL_READBACK', 'WORLD_READBACK'))
        self.assertTrue(self.service._closed)
        self.assertFalse(self.service._claimed)
        self.assertEqual(self.store.restore(self.realm.profile_uid), self.wire)
        await self.assert_no_current_retry()


    async def test_root_deadline_or_policy_reservation_failure_after_leaf_is_not_delivery(self):
        for failure in ('deadline', 'policy'):
            self.reset_temp_sidecar(); self.fresh()
            await self.check()
            self.assertTrue(self.store.restore(self.realm.profile_uid) == self.wire)
            self.assertTrue(self.service._claimed)
            if failure == 'deadline':
                self.producer._inventory_deadline_ns = 0
                with self.assertRaises(ValueError): self.producer._inventory_admission_time()
            else:
                self.policy.inventory_add = True
                sample = b.OwnerSample(self.policy.owner, self.policy.handle, self.policy.job,
                    self.row['policy_row'].peer, time.monotonic_ns(), True, True)
                with self.assertRaisesRegex(ValueError, 'BACKPRESSURE'):
                    self.policy.begin_write(self.writer, sample, i.OPCODE, len(self.wire), self.policy.WRITE_HIGH, time.monotonic_ns())
            self.service.close()  # Root's existing terminal error contract.
            self.assertIsNone(self.producer._inventory_delivery_authority)
            await self.assert_no_current_retry()
        print('canonical_persistence_postleaf_root_deadline_policy_refusals=2; delivery_posted=0; actual_send_integration=UNVERIFIED')



class ReadonlyAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await PersistenceTests.asyncSetUp(self)
        self.store.grant(self.realm.profile_uid, self.wire)
        self.producer._inventory_admission_expired = False
        self.fresh()

    def fresh(self):
        PersistenceTests.fresh(self, restore_only=True)
        self.producer._inventory_admission_expired = False
        self.memory.fault = None
        self.memory.calls.clear()

    async def check(self):
        return await GateTests.check(self)

    def fault(self, target, hit=2, action=None, *, string_only=False):
        hits = []
        def changed(at, size, raw):
            if at == target:
                hits.append(1)
                if len(hits) == hit:
                    if action: action()
                    if string_only: raise ValueError('EDGE_TYPED_READ_CHANGED')
                    return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = changed

    async def refused(self, target=None):
        self.fault(self.memory.header if target is None else target)
        with self.assertRaises(i.ReadOnlyPreWriteRefusal) as caught:
            await self.check()
        error = caught.exception
        self.assertEqual(error.__dict__, dict(reason='EDGE_TYPED_READ_CHANGED',
                                              stage=self.service.last_pre_write_stage))
        self.assertEqual(self.service.last_result['status'], 'UNKNOWN')
        self.assertFalse(self.service._closed or self.service._claimed)
        count = len(self.memory.calls)
        self.assertTrue(self.service.validate_readonly_refusal(error, self.writer, self.row, self.wire))
        self.assertEqual(len(self.memory.calls), count)
        return error

    async def test_three_physical_phases_then_fresh_fullproof_first_claim_once(self):
        await self.check()
        baseline = list(self.memory.calls)
        self.assertEqual(self.service.last_result['typed_bytes_requested'], 1857)
        prior = self.store.path.read_bytes()
        root = self.memory.base + self.memory.c['layout']['Root_slot_rva']
        for target, phase in ((0x250008, 'INITIAL'), (self.memory.header, 'WORLD_READBACK'),
                              (root, 'BUDGET_READBACK')):
            self.fresh()
            with patch.object(stores.InventoryStore, '_write', side_effect=AssertionError('write')):
                old = await self.refused(target)
                self.assertEqual(self.service.last_result['changed_read']['comparison'], phase)
                self.memory.fault = None
                self.memory.calls.clear()
                await self.check()
                self.assertEqual(self.memory.calls, baseline)
                self.assertTrue(self.service._claimed)
                self.assertIsNone(self.service._readonly_refusal)
                with self.assertRaises(ValueError):
                    self.service.validate_readonly_refusal(old, self.writer, self.row, self.wire)
                with self.assertRaisesRegex(ValueError, 'ONE_SEND_ONLY'): await self.check()
            self.assertEqual(self.store.path.read_bytes(), prior)

    async def test_string_forged_subclass_wrong_attempt_and_result_are_not_proof(self):
        self.fault(0x250008, string_only=True)
        with self.assertRaisesRegex(ValueError, '^EDGE_TYPED_READ_CHANGED$') as caught:
            await self.check()
        self.assertIs(type(caught.exception), ValueError)
        self.assertIsNone(self.service._readonly_refusal)
        self.fresh()
        old = await self.refused()
        class Fake(i.ReadOnlyPreWriteRefusal): pass
        for forged in (ValueError('EDGE_TYPED_READ_CHANGED'),
                       i.ReadOnlyPreWriteRefusal(old.stage), Fake(old.stage)):
            with self.assertRaises(ValueError):
                self.service.validate_readonly_refusal(forged, self.writer, self.row, self.wire)
        class Equal:
            def __eq__(self, other): return True
        for field in ('reason', 'stage'):
            value = getattr(old, field)
            setattr(old, field, Equal())
            with self.assertRaises(ValueError):
                self.service.validate_readonly_refusal(old, self.writer, self.row, self.wire)
            setattr(old, field, value)
        for writer, row, frame in ((object(), self.row, self.wire),
                                    (self.writer, dict(self.row), self.wire),
                                    (self.writer, self.row, bytes(bytearray(self.wire)))):
            with self.assertRaises(ValueError):
                self.service.validate_readonly_refusal(old, writer, row, frame)
        actual = self.service.last_result
        self.service.last_result = dict(actual)
        with self.assertRaises(ValueError):
            self.service.validate_readonly_refusal(old, self.writer, self.row, self.wire)
        self.service.last_result = actual
        newer = await self.refused()
        self.assertIsNot(newer, old)
        with self.assertRaises(ValueError):
            self.service.validate_readonly_refusal(old, self.writer, self.row, self.wire)
        for mode in (0, 1, None, object()):
            with self.assertRaisesRegex(ValueError, 'MODE_REQUIRED'):
                self.service.validate_readonly_refusal(newer, self.writer, self.row, self.wire, admission=mode)

    async def test_closed_deadline_is_report_only_and_ordinary_current_stays_strict(self):
        error = await self.refused()
        with self.assertRaises(ValueError): self.service._current(self.writer, self.row)
        self.producer._inventory_admission_expired = True
        self.service.close()
        self.assertTrue(self.service.validate_readonly_refusal(error, self.writer, self.row,
                                                              self.wire, admission=False))
        with self.assertRaisesRegex(ValueError, 'TERMINAL'):
            self.service.validate_readonly_refusal(error, self.writer, self.row, self.wire)
        count = len(self.memory.calls)
        self.memory.fault = None
        with self.assertRaises(ValueError): await self.check()
        self.assertEqual(len(self.memory.calls), count)
        self.assertTrue(self.service._closed)

    async def test_equal_bytes_operation_frame_swap_refuses_both_proof_modes(self):
        error = await self.refused()
        self.producer._inventory_operation_frame = bytes(bytearray(self.wire))
        self.assertEqual(self.producer._inventory_operation_frame, self.wire)
        self.assertIsNot(self.producer._inventory_operation_frame, self.wire)
        count = len(self.memory.calls)
        for mode in (True, False):
            with self.assertRaisesRegex(ValueError, 'NOT_PREWRITE'):
                self.service.validate_readonly_refusal(error, self.writer, self.row,
                                                      self.wire, admission=mode)
        self.assertEqual(len(self.memory.calls), count)

    async def test_source_image_buffer_change_stays_plain_terminal(self):
        changed = []
        def fault(at, size, raw):
            budget = self.memory.s.read.__self__
            if (not changed and budget.read_phase == 'BUDGET_READBACK'
                    and any(saved_at == at and len(saved) == size and image is True
                            for saved_at, saved, image in budget.records)):
                changed.append(1)
                return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = fault
        with self.assertRaisesRegex(ValueError, '^EDGE_TYPED_READ_CHANGED$') as caught:
            await self.check()
        self.assertEqual(changed, [1])
        self.assertIs(type(caught.exception), ValueError)
        self.assertTrue(self.service._closed)
        self.assertFalse(self.service._claimed)
        self.assertIsNone(self.service._readonly_refusal)
        self.assertEqual(self.service.last_result['status'], 'UNKNOWN')
        self.assertIs(self.service.last_result['changed_read']['image'], True)
        self.assertEqual(self.service.last_result['changed_read']['comparison'], 'BUDGET_READBACK')
        count = len(self.memory.calls)
        self.memory.fault = None
        with self.assertRaises(ValueError): await self.check()
        self.assertEqual(len(self.memory.calls), count)

    async def test_observed_delete_disk_failure_and_conflict_are_terminal_on_next_proof(self):
        original = self.store.path.read_bytes()
        fields = explicit_fields(); fields[3] -= 1
        conflict = i.build_add(fields)
        for mode in ('delete', 'disk', 'conflict'):
            self.store.path.write_bytes(original)
            self.fresh()
            await self.refused(0x250008)  # Before original existing-only grant.
            self.memory.fault = None
            if mode == 'delete': self.store.path.unlink()
            elif mode == 'conflict': self.store._write({self.realm.profile_uid: conflict})
            mutation = (patch.object(self.store, '_read', side_effect=OSError('READ_FAILURE'))
                        if mode == 'disk' else patch.object(stores.InventoryStore, '_write',
                                                           side_effect=AssertionError('write')))
            with mutation, self.assertRaises(ValueError) as caught: await self.check()
            self.assertIs(type(caught.exception), ValueError)
            self.assertFalse(self.service._claimed)
            self.assertTrue(self.service._closed)
            self.assertIsNone(self.service._readonly_refusal)
            if mode == 'delete': self.assertFalse(self.store.path.exists())
            count = len(self.memory.calls)
            with self.assertRaises(ValueError): await self.check()
            self.assertEqual(len(self.memory.calls), count)

    async def test_source_owner_mode_claim_write_and_reservation_cannot_be_promoted(self):
        pins = dict(i.SOURCE_PINS)
        # No 'source' mode: inventory._source() verifies pins once per process and
        # request paths deliberately do not re-hash (inventory.py _source comment).
        for mode in ('owner', 'mode', 'claim', 'write', 'reservation'):
            self.fresh()
            def action():
                if mode == 'source': i.SOURCE_PINS[i.EVIDENCE] = '0' * 64
                elif mode == 'owner': self.reader.owner.closed = True
                elif mode == 'mode': self.producer._inventory_restore_only = False
                elif mode == 'claim': self.service._claimed = True
                elif mode == 'write': self.producer._inventory_write_attempted = True
                else: self.row['policy_row'].pending_opcode = i.OPCODE
            self.fault(self.memory.header, action=action)
            try:
                with self.assertRaises(ValueError) as caught: await self.check()
                self.assertIs(type(caught.exception), ValueError)
                self.assertTrue(self.service._closed)
                self.assertIsNone(self.service._readonly_refusal)
            finally:
                i.SOURCE_PINS.clear(); i.SOURCE_PINS.update(pins)
                self.reader.owner.closed = False
                self.row['policy_row'].pending_opcode = None

    async def test_cancel_during_changed_physical_read_is_terminal(self):
        async def attempt():
            task = asyncio.current_task()
            self.fault(self.memory.header, action=task.cancel)
            await self.check()
        with self.assertRaises(asyncio.CancelledError): await asyncio.create_task(attempt())
        self.assertTrue(self.service._closed)
        self.assertIsNone(self.service._readonly_refusal)
        self.assertFalse(self.service._claimed)


if __name__ == '__main__':
    unittest.main()
