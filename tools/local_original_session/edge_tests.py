"""Synthetic edge callback tests; no image, process, game, UI or network access."""
import hashlib
import copy
from collections import Counter
import importlib.util
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import edge, observe
from tools.online_intro_capture_20261006.sampler import Sampler


class Fixture:
    def __init__(self):
        self.adapter = edge.EdgeAdapter(observe.RetainedSceneReader.__new__(observe.RetainedSceneReader))
        self.data, self.calls = {}, []
        self.grid = (32571, 32950)
        self.base, self.actor, self.map, self.player = 0x140000000, 0x100000, 0x110000, 0x120000
        self.context, self.resource = 0x180000, 0x200000
        self.c = {'checks': [], 'bounds': {'typed_byte_limit': 8192, 'total_typed_byte_limit': 4194304}}
        self.native = SimpleNamespace(contract=self.c, read=self.read)
        self.s = Sampler(self.native, self.c, {'base': self.base, 'size': 0x4000000})
        self.s.bytes, self.s.read_limit, self.s.total = 77, 8192, 900
        self.adapter.reader.backend, self.adapter.reader.sampler = self.native, self.s
        self.adapter.reader.validate = Mock()
        self.adapter._binding = lambda: (self.native, self.s)
        # Synthetic metadata avoids reading CONTROL or executing source producers.
        self.adapter.checks, self.adapter.tables = [], []
        def table(obj, rva):
            self.put(obj, '<Q', self.base + rva)
            self.put(self.base + rva, '<Q', self.base + 0x1000)
            return dict(rva=rva, prefix_bytes=8,
                        normalized_sha256=hashlib.sha256(struct.pack('<Q', 0x1000)).hexdigest())
        actor_table, map_table, player_table = (table(self.actor, 0x100), table(self.map, 0x200),
                                               table(self.player, 0x300))
        self.transform = 0x160000
        position = dict(self.adapter.public['Position'], Transform=table(self.transform, 0x400))
        self.adapter.public = {'Player': {'ActorSubsystem': actor_table, 'MyPlayer': player_table,
            'vector_begin': 0x8a8, 'vector_end': 0x8b0, 'max_actor_elements': 16, 'ActorID': 24},
            'Position': position,
            'Map': {'table': map_table, 'context_pointer': 0x6e0, 'field718': 0x718}}
        self.put(0x140008, '<i', 3)
        def pair(obj): return struct.pack('<QQ', obj, 0x140000)
        self.pair = pair
        self.put(self.actor + 0x8a8, '<QQ', 0x130000, 0x130010)
        self.data.update({0x130000 + i: b for i, b in enumerate(pair(self.player))})
        self.put(self.player + 24, '<Q', 93)
        self.put(self.player + position['component_begin'], '<QQ', 0x170000, 0x170010)
        self.data.update({0x170000 + i: b for i, b in enumerate(pair(self.transform))})
        self.put(self.transform + position['borrowed_Actor'], '<Q', self.player)
        self.put(self.transform + position['pair_offset'], '<ii', *((n >> 6) + 0x7e00 for n in self.grid))
        self.put(self.transform + self.adapter.position_source['coordinates']['transform_grid_offset'],
                 '<ii', *self.grid)
        self.put(self.map + 0x6e0, '<Q', self.context)
        self.put(self.map + 0x718, '<ii', 7, 7)
        self.put(self.context, '<i', 7)
        self.route = (None, True, None, None, None, None,
                      ((pair(self.actor), self.base + 0x100), (pair(self.map), self.base + 0x200)),
                      {'GameState': [0x150000]})
        self.s.route = lambda: self.route
        self.s.scene = lambda _: ({'current': {'kind': 'Land'}, 'pending': {'kind': 'none'}}, bytes(36))
        self.put(0x150360, '36s', bytes(36))
        segment = tuple((n >> 6) + 0x7e00 for n in self.grid)
        self.put(self.context + 8, '<QQ', 0x190000, 1)
        self.put(0x190000, '<QQQBB', 0x1a0000, 0x1a0000, 0x1a0000, 1, 1)
        self.put(0x1a0000, '<QQQBB6xI4xQQ', 0x190000, 0x190000, 0x190000,
                 1, 0, (segment[0] << 16) | segment[1], self.resource, 0x140000)
        self.put(self.resource, '<QQQ', 0x300000, 0x300000 + 64 * 24, 0x300000 + 64 * 24)
        self.put(self.resource + 24, '<QQ', 0x210000, 0)
        self.put(0x210000, '<QQQBB', 0x210000, 0x210000, 0x210000, 1, 1)
        for direction in range(8):
            for _, (x, y) in self.adapter.tile.probe_cells(self.grid, direction):
                row = 0x400000 + y * 0x1000
                self.put(0x300000 + y * 24, '<QQQ', row, row + 128 * 8, row + 128 * 8)
                self.put(row + x * 8, '<IHH', 0, 0, 0)
        for index in range(2):
            head, buckets = 0x600000 + index * 0x10000, 0x610000 + index * 0x10000
            self.put(self.actor + 0x798 + index * 64, '<fI7Q', 1.0, 0, head, 0,
                     buckets, buckets + 128, buckets + 128, 7, 8)
            self.put(head, '<QQ', head, head)
            for bucket in range(8): self.put(buckets + bucket * 16, '<QQ', head, head)

    def put(self, at, fmt, *values):
        self.data.update((at + i, b) for i, b in enumerate(struct.pack(fmt, *values)))

    def read(self, at, size, image=None):
        self.calls.append(size)
        try: return bytes(self.data[at + i] for i in range(size))
        except KeyError: raise ValueError('SYNTHETIC_CELL_UNREADABLE')

    def call(self, direction=2, uid=93):
        target = self.adapter.tile.map_step(self.grid, direction)['grid_target']
        return self.adapter(uid, 7, self.grid[0] | self.grid[1] << 16,
                            direction, target[0] | target[1] << 16)

    def nonempty(self, store, pointers, target=None):
        self.lookup_fixture()
        target = tuple(self.adapter.tile.map_step(self.grid, 2)['grid_target']) if target is None else target
        head, buckets = 0x600000 + store * 0x10000, 0x610000 + store * 0x10000
        node, vector = 0x700000 + store * 0x10000, 0x740000 + store * 0x10000
        self.put(self.actor + 0x798 + store * 64 + 16, '<Q', 1)
        self.put(head, '<QQ', node, node)
        self.put(node, '<QQiiQQQ', head, head, *target, vector, vector + len(pointers) * 8, vector + len(pointers) * 8)
        if pointers:
            self.put(vector, '<' + 'Q' * len(pointers), *pointers)
        self.put(buckets + (self.adapter.nav.destination_hash(target) & 7) * 16, '<QQ', node, node)
        return node, vector

    def lookup_fixture(self):
        if hasattr(self, 'character'):
            return
        self.character = 0x1b0000
        contract = copy.deepcopy(self.adapter.lookup_contract)
        player = contract['player']
        player.update(self.adapter.public['Player']['MyPlayer'])
        targets = [0x1000, contract['getter_rva'], 0x2000, 0x3000, 0x4000]
        player.update(prefix_bytes=40,
            normalized_sha256=hashlib.sha256(struct.pack('<5Q', *targets)).hexdigest())
        self.put(self.base + player['rva'], '<5Q', *(self.base + v for v in targets))
        self.adapter.public['Player']['MyPlayer'] = dict(player)
        self.put(self.base + player['rva'] - 8, '<Q', self.base + player['COL_rva'])
        col = b'C' * 24
        self.put(self.base + player['COL_rva'], '24s', col)
        player['COL_sha256'] = hashlib.sha256(col).hexdigest()
        literal = player['literal'].encode('ascii') + b'\0'
        self.put(self.base + player['descriptor_rva'] + 16, str(len(literal)) + 's', literal)
        for anchor in player['RTTI_graph_anchors']:
            raw = bytes([anchor['rva'] & 255]) * anchor['length']
            self.put(self.base + anchor['rva'], str(len(raw)) + 's', raw)
            anchor['sha256'] = hashlib.sha256(raw).hexdigest()
        # The descriptor literal is itself one retained graph anchor.
        for anchor in player['RTTI_graph_anchors']:
            if anchor['rva'] == player['descriptor_rva'] + 16:
                self.put(self.base + anchor['rva'], str(len(literal)) + 's', literal)
                anchor['sha256'] = hashlib.sha256(literal).hexdigest()
        for check in contract['code_checks']:
            raw = b'G' * check['length']
            self.put(self.base + check['rva'], str(len(raw)) + 's', raw)
            check['sha256'] = hashlib.sha256(raw).hexdigest()
        character_table = contract['character']
        self.put(self.character, '<Q', self.base + character_table['rva'])
        self.put(self.character + 0x6d8, '<Q', 93)
        targets = [0x10ff40, 0x6cfc0, 0x6cfb0, 0x110c10, 0x111240]
        self.put(self.base + character_table['rva'], '<5Q', *(self.base + v for v in targets))
        self.route = (*self.route[:-2],
            (*self.route[-2], (self.pair(self.character), self.base + character_table['rva'])), self.route[-1])
        self.adapter.lookup_contract = contract

    def prefix(self, uids):
        self.nonempty(0, [self.player])
        self.nonempty(1, [self.player])
        actors = []
        for index, uid in enumerate(uids):
            actor, control, vptr = 0x900000 + index * 0x1000, 0xa00000 + index * 0x100, self.base + 0x9000
            self.put(actor, '<Q', vptr)
            self.put(actor + 24, '<Q', uid)
            self.put(control + 8, '<i', 3)
            self.put(0x130000 + index * 16, '<QQ', actor, control)
            actors.append((actor, control, vptr))
        self.put(self.base + 0x9008, '<Q', self.base + self.adapter.lookup_contract['getter_rva'])
        self.put(0x130000 + len(uids) * 16, '16s', self.pair(self.player))
        self.put(self.actor + 0x8b0, '<Q', 0x130000 + (len(uids) + 1) * 16)
        return actors


class BudgetDedupTests(unittest.TestCase):
    @staticmethod
    def baseline():
        path = observe.ROOT / 'work/local_original_session/implementation-2/budget-dedup-candidate/baseline/edge.py'
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == '1894b8fa6cdabaf1688cbd95cdf435317117b87003eab2f229aae0eb41ce1eae'
        spec = importlib.util.spec_from_file_location('_budget_dedup_baseline_edge', path)
        module = importlib.util.module_from_spec(spec)
        exec(compile(raw, str(path), 'exec'), module.__dict__)
        return module

    @staticmethod
    def budget():
        calls, data = [], bytearray(b'ABCDEFGH')
        def read(at, size, image=None):
            calls.append((at, size, image))
            return bytes(data[at - 0x20000:at - 0x20000 + size])
        sampler = SimpleNamespace(g=dict(base=0x140000000))
        return edge._Budget(SimpleNamespace(read=read), sampler), calls, data

    def test_budget_unique_records_keep_all_initial_native_reads_and_distinct_span_image(self):
        budget, calls, data = self.budget()
        spans = [(0x20000, 4, False), (0x20000, 4, False), (0x20000, 4, True),
                 (0x20000, 2, False), (0x20002, 2, False)]
        expected = [(at, size, budget.sampler.g['base'] if image else None) for at, size, image in spans]
        for at, size, image in spans: budget.read(at, size, image)
        self.assertEqual(calls, expected)
        self.assertEqual(budget.spent, sum(size for _, size, _ in spans))
        self.assertEqual(len(budget.records), 4)
        budget.verify()
        self.assertEqual(Counter(calls[len(spans):]), Counter(set(expected)))
        self.assertEqual(budget.spent, sum(size for _, size, _ in calls))

    def test_budget_duplicate_initial_change_or_native_failure_is_not_cached(self):
        budget, calls, data = self.budget()
        budget.read(0x20000, 4)
        data[0] ^= 1
        with self.assertRaisesRegex(ValueError, 'EDGE_TYPED_READ_CHANGED'):
            budget.read(0x20000, 4)
        self.assertEqual((len(calls), budget.spent, len(budget.records)), (2, 8, 1))
        budget, calls, data = self.budget()
        budget.read(0x20000, 4, True)
        with patch.object(budget.native, 'read', side_effect=ValueError('module_allocation_mismatch')) as read:
            with self.assertRaisesRegex(ValueError, 'module_allocation_mismatch'):
                budget.read(0x20000, 4, True)
        read.assert_called_once_with(0x20000, 4, budget.sampler.g['base'])
        self.assertEqual(budget.spent, 8)

    def test_budget_identical_initial_duplicates_then_footer_change_is_unknown(self):
        budget, calls, data = self.budget()
        budget.read(0x20000, 4)
        budget.read(0x20000, 4)
        data[0] ^= 1
        with self.assertRaisesRegex(ValueError, 'EDGE_TYPED_READ_CHANGED'):
            budget.verify()
        self.assertEqual((len(calls), budget.spent, len(budget.records)), (3, 12, 1))
        self.assertTrue(budget.retain)

    @staticmethod
    def edge_trace(module, limit=None):
        f = Fixture(); f.prefix([94, 95, 96])
        f.adapter.__class__ = module.EdgeAdapter
        code = b'CODE'; f.put(f.base + 0x500, '4s', code)
        f.adapter.checks = [dict(rva=0x500, length=4, sha256=hashlib.sha256(code).hexdigest())]
        calls, capture = [], {}
        original_read, original_verify = f.native.read, module._Budget.verify
        def read(at, size, image=None):
            calls.append((at, size, image))
            return original_read(at, size, image)
        def verify(budget):
            capture['initial'] = list(calls)
            capture['records'] = [(at, len(raw), f.base if image else None) for at, raw, image in budget.records]
            try:
                return original_verify(budget)
            finally:
                capture['final'] = calls[len(capture['initial']):]
                capture['footer_start'] = len(calls)
        f.native.read = read
        with patch.object(module._Budget, 'verify', verify), patch.object(module, 'LIMIT', module.LIMIT if limit is None else limit):
            accepted = f.call()
        capture.update(accepted=accepted, result=dict(f.adapter.last_result), calls=calls,
                       footer=calls[capture.get('footer_start', len(calls)):],
                       restored=(f.s.bytes, f.s.read_limit, f.s.total), validate_calls=f.adapter.reader.validate.call_count)
        return capture

    def test_budget_same_edge_proof_keeps_initial_source_world_reads_and_counter_restore(self):
        original, candidate = self.edge_trace(self.baseline()), self.edge_trace(edge)
        self.assertIs(original['accepted'], True, original['result'])
        self.assertIs(candidate['accepted'], True, candidate['result'])
        self.assertEqual(candidate['initial'], original['initial'])
        self.assertEqual(candidate['footer'], original['footer'])
        self.assertEqual(set(candidate['records']), set(original['records']))
        self.assertEqual(Counter(candidate['final']), Counter(set(original['records'])))
        self.assertGreater(len(original['final']), len(candidate['final']))
        for key in ('status', 'own_self_candidates', 'raw_candidates_by_store', 'self_uid_lookup',
                    'uid_lookup_prefix_count', 'official_navigation_equivalence', 'source_code_bytes_requested'):
            self.assertEqual(candidate['result'][key], original['result'][key])
        self.assertEqual(candidate['result']['source_code_bytes_requested'], 932)
        for trace in (original, candidate):
            self.assertEqual(trace['restored'], (77, 8192, 900))
            self.assertEqual(trace['validate_calls'], 1)
            self.assertEqual(trace['result']['typed_bytes_requested'], sum(size for _, size, _ in trace['calls']))
        self.assertEqual(candidate['validate_calls'], original['validate_calls'])

    def test_budget_decisive_same_dto_baseline_shortfall_candidate_complete_at_fixed_cap(self):
        baseline = self.baseline()
        original, candidate = self.edge_trace(baseline), self.edge_trace(edge)
        original_bytes, candidate_bytes = original['result']['typed_bytes_requested'], candidate['result']['typed_bytes_requested']
        self.assertGreater(original_bytes, candidate_bytes)
        refused, accepted = self.edge_trace(baseline, candidate_bytes), self.edge_trace(edge, candidate_bytes)
        self.assertIsNone(refused['accepted'])
        self.assertIs(accepted['accepted'], True, accepted['result'])
        self.assertEqual(refused['result']['reason'], 'EDGE_REQUEST_BYTE_BOUND')
        self.assertEqual(refused['result']['phase'], 'SOURCE_AFTER')
        self.assertEqual(refused['result']['required_total_bytes'], original_bytes)
        self.assertEqual(refused['result']['total_shortfall_bytes'], original_bytes - candidate_bytes)
        self.assertEqual(refused['restored'], accepted['restored'])
        self.assertEqual(accepted['result']['official_navigation_equivalence'], 'UNKNOWN')


class Tests(unittest.TestCase):
    def test_uid_prefix_zero_or_known_getter_different_uids_resolves_exact_self(self):
        for uids in ([], [94], [94, 95, 0]):
            with self.subTest(uids=uids):
                f = Fixture(); f.prefix(uids)
                self.assertIs(f.call(), True, f.adapter.last_result)
                result = f.adapter.last_result
                self.assertEqual(result['uid_lookup_prefix_count'], len(uids))
                self.assertEqual(result['self_uid_lookup'],
                    'EXACT_SELF_AFTER_TYPED_UID_PREFIX' if uids else 'EXACT_FIRST_REGISTERED_SELF')
                self.assertEqual(result['own_self_candidates'], 2)
                self.assertEqual(result['lookup_code_bytes_requested'], 924)
                self.assertEqual(result['official_navigation_equivalence'], 'UNKNOWN')

    def test_uid_prefix_earlier_match_unsupported_vptr_getter_control_or_reads_are_unknown(self):
        cases = {'duplicate_uid': 'EDGE_UID_LOOKUP_EARLIER_MATCH',
                 'unsupported_getter': 'EDGE_UID_PREFIX_GETTER_UNSUPPORTED',
                 'external_vptr': 'EDGE_UID_PREFIX_VTABLE_IMAGE_BOUNDS',
                 'control': 'shared_owner_not_positive',
                 'uid_read': 'SYNTHETIC_CELL_UNREADABLE',
                 'slot_read': 'SYNTHETIC_CELL_UNREADABLE',
                 'getter_code': 'EDGE_LOOKUP_CODE_CHANGED'}
        for failure, expected in cases.items():
            with self.subTest(failure=failure):
                f = Fixture(); (actor, control, vptr), = f.prefix([93 if failure == 'duplicate_uid' else 94])
                if failure == 'unsupported_getter': f.put(vptr + 8, '<Q', f.base + 0x7777)
                if failure == 'external_vptr': f.put(actor, '<Q', 0xb00000)
                if failure == 'control': f.put(control + 8, '<i', 0)
                if failure == 'uid_read': del f.data[actor + 24]
                if failure == 'slot_read': del f.data[vptr + 8]
                if failure == 'getter_code': f.data[f.base + f.adapter.lookup_contract['getter_rva']] ^= 1
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'], expected)
                self.assertNotIn(f.adapter.last_result['self_uid_lookup'],
                    ('EXACT_FIRST_REGISTERED_SELF', 'EXACT_SELF_AFTER_TYPED_UID_PREFIX'))

    def test_uid_prefix_pair_control_vptr_slot_and_uid_reread_changes_are_unknown(self):
        for changed in ('pair', 'control', 'vptr', 'slot', 'uid'):
            with self.subTest(changed=changed):
                f = Fixture(); (actor, control, vptr), = f.prefix([94])
                original, armed = f.native.read, [False]
                addresses = {'pair': 0x130000, 'control': control + 8,
                             'vptr': actor, 'slot': vptr + 8, 'uid': actor + 24}
                at_changed = addresses[changed]
                def read(at, size, image=None):
                    if at == f.character + 0x6d8: armed[0] = True
                    if armed[0] and at == at_changed:
                        f.data[at] ^= 1
                    return original(at, size, image)
                f.native.read = read
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'], 'EDGE_TYPED_READ_CHANGED')
                self.assertEqual(f.adapter.last_result['self_uid_lookup'], 'UNKNOWN')
                self.assertIsNone(f.adapter.last_result['uid_lookup_prefix_count'])
                self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))

    def test_uid_prefix_image_allocation_recheck_and_footer_budget_shortfall(self):
        for allocation_failure in (None, 1, 2):
            with self.subTest(allocation_failure=allocation_failure):
                f = Fixture(); (_, _, vptr), = f.prefix([94])
                original, calls = f.native.read, [0]
                def read(at, size, image=None):
                    if at == vptr + 8:
                        calls[0] += 1
                        self.assertEqual((size, image), (8, f.base))
                        if calls[0] == allocation_failure:
                            raise ValueError('module_allocation_mismatch')
                    return original(at, size, image)
                f.native.read = read
                if allocation_failure is not None:
                    self.assertIsNone(f.call())
                    self.assertEqual(f.adapter.last_result['reason'], 'module_allocation_mismatch')
                else:
                    self.assertIs(f.call(), True, f.adapter.last_result)
                    self.assertEqual(calls[0], 2)
                    complete = f.adapter.last_result['typed_bytes_requested']
                    with patch.object(edge, 'LIMIT', complete - 1):
                        self.assertIsNone(f.call())
                    result = f.adapter.last_result
                    self.assertEqual(result['phase'], 'SOURCE_AFTER')
                    self.assertEqual(result['reason'], 'EDGE_REQUEST_BYTE_BOUND')
                    self.assertEqual(result['required_total_bytes'], complete)
                    self.assertEqual(result['total_shortfall_bytes'], 1)
                    self.assertEqual(result['self_uid_lookup'], 'UNKNOWN')
                    self.assertIsNone(result['uid_lookup_prefix_count'])

    def test_neighbors_share_tiles_return_all_eight_mask1_only_and_leave_edge_result_unchanged(self):
        f = Fixture()
        for direction in range(8):
            for _, (x, y) in f.adapter.tile.probe_cells(f.grid, direction):
                f.put(0x400000 + y * 0x1000 + x * 8 + 4, '<H', 0x4000)
        for direction in (0, 4):
            _, (x, y) = f.adapter.tile.probe_cells(f.grid, direction)[0]
            f.put(0x400000 + y * 0x1000 + x * 8 + 4, '<H', 1)
        previous, original_read = f.adapter.last_result, f.s.read
        header_reads = [0]
        native_read = f.native.read
        def tracked(at, size, image=None):
            if at == f.resource + 24 and size == 16:
                header_reads[0] += 1
            return native_read(at, size, image)
        f.native.read = tracked
        with patch.object(f.adapter.tile, 'lookup_resource', wraps=f.adapter.tile.lookup_resource) as resources:
            with patch.object(f.adapter.tile, 'cell', wraps=f.adapter.tile.cell) as cells:
                result = f.adapter.tile_neighbors(93, 7, f.grid[0] | f.grid[1] << 16)
                self.assertEqual(resources.call_count, 1)
                self.assertEqual(cells.call_count, result['unique_cells_read'])
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertEqual([row['direction'] for row in result['directions']], list(range(8)))
        self.assertTrue(result['directions'][0]['blocked'])
        self.assertTrue(result['directions'][4]['blocked'])
        self.assertIs(result['directions'][2]['blocked'], False)
        self.assertEqual(result['directions'][2]['flags_u16'], [0x4000])
        self.assertTrue(result['stable_double_read'])
        self.assertEqual(result['occupancy'], 'NOT_READ')
        self.assertEqual(result['full_passability'], 'UNKNOWN')
        self.assertEqual(result['client_direction_selection'], 'UNKNOWN')
        self.assertEqual(header_reads[0], 2)  # One initial and one fresh verification.
        self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))
        self.assertEqual(f.s.read, original_read)
        self.assertIs(f.adapter.last_result, previous)

    def test_neighbors_stale_uid_or_cell_invalidates_every_clear_outcome(self):
        for stale in ('uid', 'cell'):
            with self.subTest(stale=stale):
                f = Fixture(); original = f.native.read; seen = [False]
                if stale == 'uid':
                    changed_at, fmt, values = f.player + 24, '<Q', (94,)
                else:
                    _, (x, y) = f.adapter.tile.probe_cells(f.grid, 0)[0]
                    changed_at, fmt, values = 0x400000 + y * 0x1000 + x * 8, '<IHH', (0, 1, 0)
                def read(at, size, image=None):
                    if at == changed_at:
                        if seen[0]: f.put(at, fmt, *values)
                        seen[0] = True
                    return original(at, size, image)
                f.native.read = read
                previous = f.adapter.last_result
                result = f.adapter.tile_neighbors(93, 7, f.grid[0] | f.grid[1] << 16)
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertEqual(result['reason'], 'EDGE_TYPED_READ_CHANGED')
                self.assertFalse(result['stable_double_read'])
                self.assertTrue(all(row['status'] == 'UNKNOWN' and row['blocked'] is None
                                    for row in result['directions']))
                self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))
                self.assertIs(f.adapter.last_result, previous)

    def test_neighbors_source_proof_twice_and_exact_footer_budget_shortfall(self):
        f = Fixture(); code_at = f.base + 0x500
        f.put(code_at, '4s', b'CODE')
        f.adapter.checks = [dict(rva=0x500, length=4, sha256=hashlib.sha256(b'CODE').hexdigest())]
        with patch.object(f.adapter, '_code', wraps=f.adapter._code) as code:
            complete = f.adapter.tile_neighbors(93, 7, f.grid[0] | f.grid[1] << 16)
            self.assertEqual(code.call_count, 2)
        self.assertEqual(complete['source_code_bytes_requested'], 8)
        self.assertEqual(complete['source_code_bytes_planned'], 8)
        cap = complete['typed_bytes_requested'] - 2
        previous = f.adapter.last_result
        with patch.object(edge, 'LIMIT', cap):
            refused = f.adapter.tile_neighbors(93, 7, f.grid[0] | f.grid[1] << 16)
        self.assertEqual(refused['reason'], 'EDGE_REQUEST_BYTE_BOUND')
        self.assertEqual(refused['required_total_bytes'], complete['typed_bytes_requested'])
        self.assertEqual(refused['total_shortfall_bytes'], 2)
        self.assertEqual(refused['refused_read_bytes'], 4)
        self.assertLessEqual(refused['typed_bytes_requested'], cap)
        self.assertTrue(all(row['blocked'] is None for row in refused['directions']))
        self.assertIs(f.adapter.last_result, previous)
        self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))

    def test_all_directions_dynamic_uid_map_and_counter_restoration(self):
        f = Fixture()
        original_read = f.s.read
        for direction in range(8):
            self.assertIs(f.call(direction), True, f.adapter.last_result)
            self.assertLessEqual(f.adapter.last_result['typed_bytes_requested'], edge.LIMIT)
        self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))
        self.assertEqual(f.s.read, original_read)

    def test_mask1_blocked_is_false(self):
        f = Fixture()
        _, (x, y) = f.adapter.tile.probe_cells(f.grid, 2)[0]
        f.put(0x400000 + y * 0x1000 + x * 8 + 4, '<H', 1)
        self.assertIs(f.call(), False)
        self.assertEqual(f.adapter.last_result['status'], 'BLOCKED_MASK1')

    def test_uid_identity_missing_cell_and_budget_fail_closed(self):
        for failure in ('uid', 'owner', 'cell', 'budget'):
            with self.subTest(failure=failure):
                f = Fixture()
                if failure == 'owner':
                    f.adapter.reader.validate.side_effect = ValueError('READONLY_DUPLICATE_IDENTITY_CHANGED')
                if failure == 'cell':
                    _, (x, y) = f.adapter.tile.probe_cells(f.grid, 2)[0]
                    del f.data[0x400000 + y * 0x1000 + x * 8 + 4]
                with patch.object(edge, 'LIMIT', 100 if failure == 'budget' else 32768):
                    self.assertIsNone(f.call(uid=94 if failure == 'uid' else 93))
                self.assertEqual(f.adapter.last_result['status'], 'UNKNOWN')
                self.assertEqual((f.s.bytes, f.s.total), (77, 900))
                if failure == 'budget':
                    self.assertEqual(f.adapter.last_result['reason'], 'EDGE_REQUEST_BYTE_BOUND')
                    self.assertLessEqual(sum(f.calls), 100)

    def test_foreign_candidate_is_unknown_and_never_dereferenced(self):
        f = Fixture()
        foreign = 0xdead0000
        f.nonempty(0, [f.player]); f.nonempty(1, [f.player, foreign])
        original = f.native.read
        def read(at, size, image=None):
            self.assertFalse(foreign <= at < foreign + 0x1000)
            return original(at, size, image)
        f.native.read = read
        self.assertIsNone(f.call())
        self.assertEqual(f.adapter.last_result['reason'], 'SPATIAL_TARGET_FOREIGN_OR_UNKNOWN_CANDIDATE')

    def test_exact_current_self_in_both_complete_stores_is_a_distinct_local_subset(self):
        f = Fixture()
        f.nonempty(0, [f.player]); f.nonempty(1, [f.player, f.player])
        self.assertIs(f.call(), True, f.adapter.last_result)
        self.assertEqual(f.adapter.last_result['status'], 'CLEAR_OWN_SELF_SUBSET')
        self.assertEqual(f.adapter.last_result['raw_candidates_by_store'], [1, 2])
        self.assertEqual(f.adapter.last_result['own_self_candidates'], 3)
        self.assertEqual(f.adapter.last_result['self_uid_lookup'], 'EXACT_FIRST_REGISTERED_SELF')
        self.assertEqual(f.adapter.last_result['lookup_code_bytes_requested'], 924)
        self.assertEqual(f.adapter.last_result['official_navigation_equivalence'], 'UNKNOWN')
        self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))

    def test_self_subset_uid_or_player_pair_changed_at_recheck_is_unknown(self):
        for changed in ('uid', 'player_pair'):
            with self.subTest(changed=changed):
                f = Fixture(); f.nonempty(0, [f.player]); f.nonempty(1, [f.player])
                original, seen = f.native.read, [False]
                at = f.player + 24 if changed == 'uid' else 0x130000
                def read(address, size, image=None):
                    if address == at:
                        if seen[0]:
                            if changed == 'uid': f.put(at, '<Q', 94)
                            else: f.put(at, '<QQ', f.player + 8, 0x140000)
                        seen[0] = True
                    return original(address, size, image)
                f.native.read = read
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'], 'EDGE_TYPED_READ_CHANGED')

    def test_self_subset_preserves_vector_bound_and_audit_query_failure(self):
        for failure in ('bound', 'audit_nonempty', 'bucket_range'):
            with self.subTest(failure=failure):
                f = Fixture()
                if failure == 'audit_nonempty':
                    actual_node, _ = f.nonempty(0, [f.player])
                    audit_key, audit_node, audit_vector = (-0x80000000, -0x80000000), 0x720000, 0x760000
                    f.put(f.actor + 0x798 + 16, '<Q', 2)
                    f.put(0x600000, '<QQ', actual_node, audit_node)
                    f.put(actual_node, '<Q', audit_node)
                    f.put(audit_node, '<QQiiQQQ', 0x600000, actual_node, *audit_key,
                          audit_vector, audit_vector + 8, audit_vector + 8)
                    f.put(audit_vector, '<Q', f.player)
                    bucket = f.adapter.nav.destination_hash(audit_key) & 7
                    f.put(0x610000 + bucket * 16, '<QQ', audit_node, audit_node)
                    expected = 'EDGE_SPATIAL_AUDIT_QUERY_NONEMPTY'
                else:
                    node, vector = f.nonempty(0, [f.player])
                    if failure == 'bound':
                        f.put(node + 40, '<Q', vector + (f.adapter.nav.CAPACITY_LIMIT + 1) * 8)
                        expected = 'SPATIAL_CANDIDATE_VECTOR_BOUND'
                    else:
                        target = tuple(f.adapter.tile.map_step(f.grid, 2)['grid_target'])
                        f.put(0x610000 + (f.adapter.nav.destination_hash(target) & 7) * 16, '<QQ', 0x600000, 0x600000)
                        expected = 'SPATIAL_BUCKET_COMPLETE_RANGE_MISMATCH'
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'], expected)

    def test_self_subset_footer_budget_refuses_with_exact_total_shortfall(self):
        f = Fixture(); f.nonempty(0, [f.player]); f.nonempty(1, [f.player])
        f.put(f.base + 0x500, '4s', b'CODE')
        f.adapter.checks = [dict(rva=0x500, length=4, sha256=hashlib.sha256(b'CODE').hexdigest())]
        self.assertIs(f.call(), True)
        complete = f.adapter.last_result['typed_bytes_requested']
        with patch.object(edge, 'LIMIT', complete - 2):
            self.assertIsNone(f.call())
        result = f.adapter.last_result
        self.assertEqual(result['phase'], 'SOURCE_AFTER')
        self.assertEqual(result['source_code_bytes_planned'], 932)
        self.assertEqual(result['required_total_bytes'], complete)
        self.assertEqual(result['total_shortfall_bytes'], 2)
        self.assertLessEqual(result['typed_bytes_requested'], complete - 2)
        self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))

    def test_self_lookup_foreign_prefix_even_with_duplicate_uid_is_unknown(self):
        for preceding_uid in (93, 94):
            with self.subTest(preceding_uid=preceding_uid):
                f = Fixture(); f.nonempty(0, [f.player])
                foreign = 0x125000
                f.put(foreign, '<Q', f.base + 0x500)
                f.put(f.base + 0x508, '<Q', f.base + 0x1000)
                f.put(foreign + 24, '<Q', preceding_uid)
                f.put(f.actor + 0x8b0, '<Q', 0x130020)
                f.put(0x130000, '16s', f.pair(foreign))
                f.put(0x130010, '16s', f.pair(f.player))
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'], 'EDGE_UID_PREFIX_GETTER_UNSUPPORTED')
                self.assertEqual(f.adapter.last_result['self_uid_lookup'], 'UNKNOWN')

    def test_self_lookup_requires_current_character_own_uid_and_readable_code(self):
        for failure in ('own_uid', 'character_missing', 'character_type', 'own_read', 'getter_read'):
            with self.subTest(failure=failure):
                f = Fixture(); f.nonempty(0, [f.player])
                if failure == 'own_uid':
                    f.put(f.character + 0x6d8, '<Q', 94)
                    expected = 'EDGE_UID_LOOKUP_OWN_UID_MISMATCH'
                elif failure == 'character_missing':
                    f.route = (*f.route[:-2], f.route[-2][:-1], f.route[-1])
                    expected = 'EDGE_UNIQUE_CHARACTER_DATA_REQUIRED'
                elif failure == 'character_type':
                    f.put(f.character, '<Q', f.base + 0x500)
                    expected = 'EDGE_CHARACTER_DATA_TYPE_CHANGED'
                else:
                    missing = (f.character + 0x6d8 if failure == 'own_read'
                               else f.base + f.adapter.lookup_contract['getter_rva'])
                    del f.data[missing]
                    expected = 'SYNTHETIC_CELL_UNREADABLE'
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'], expected)
                self.assertEqual(f.adapter.last_result['self_uid_lookup'], 'UNKNOWN')

    def test_self_lookup_control_slot_own_uid_rtti_and_code_changes_are_unknown(self):
        for changed in ('control', 'slot', 'own_uid', 'rtti', 'getter'):
            with self.subTest(changed=changed):
                f = Fixture(); f.nonempty(0, [f.player])
                original, armed, seen = f.native.read, [False], [0]
                player = f.adapter.lookup_contract['player']
                own_at = f.character + 0x6d8
                def read(at, size, image=None):
                    if at == own_at:
                        armed[0] = True
                        if changed == 'own_uid':
                            seen[0] += 1
                            if seen[0] == 2: f.put(own_at, '<Q', 94)
                    if armed[0]:
                        if changed == 'control' and at == 0x140008:
                            f.put(at, '<i', 0)
                        elif changed == 'slot' and at == f.base + player['rva']:
                            f.put(at + 8, '<Q', f.base + 0x500)
                        elif changed == 'rtti' and at == f.base + player['RTTI_graph_anchors'][0]['rva']:
                            f.data[at] ^= 1
                        elif changed == 'getter' and at == f.base + f.adapter.lookup_contract['getter_rva']:
                            f.data[at] ^= 1
                    return original(at, size, image)
                f.native.read = read
                self.assertIsNone(f.call())
                self.assertEqual(f.adapter.last_result['reason'],
                    'EDGE_LOOKUP_CODE_CHANGED' if changed == 'getter' else 'EDGE_TYPED_READ_CHANGED')
                self.assertEqual(f.adapter.last_result['self_uid_lookup'], 'UNKNOWN')
                self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))

    def test_empty_store_never_uses_lookup_or_character_data(self):
        f = Fixture()
        with patch.object(edge, '_exact_first_self_lookup', side_effect=AssertionError('unexpected lookup')):
            self.assertIs(f.call(), True)
        self.assertEqual(f.adapter.last_result['self_uid_lookup'], 'NOT_REQUIRED')
        self.assertEqual(f.adapter.last_result['lookup_code_bytes_requested'], 0)
        self.assertEqual(f.adapter.last_result['source_code_bytes_planned'], 0)

    def test_changed_typed_uid_recheck_invalidates_clear_candidate(self):
        f = Fixture()
        original, seen = f.native.read, [False]
        def read(at, size, image=None):
            if at == f.player + 24:
                if seen[0]: f.put(at, '<Q', 94)
                seen[0] = True
            return original(at, size, image)
        f.native.read = read
        self.assertIsNone(f.call())
        self.assertEqual(f.adapter.last_result['reason'], 'EDGE_TYPED_READ_CHANGED')

    def test_neighbors_current_start_mismatch_or_changed_grid_remains_unknown(self):
        for stale in (False, True):
            f = Fixture()
            at = f.transform + f.adapter.position_source['coordinates']['transform_grid_offset']
            if not stale:
                f.put(at, '<ii', f.grid[0] + 1, f.grid[1])
            else:
                original, seen = f.native.read, [False]
                def read(address, size, image=None):
                    if address == at:
                        if seen[0]: f.put(at, '<ii', f.grid[0] + 1, f.grid[1])
                        seen[0] = True
                    return original(address, size, image)
                f.native.read = read
            result = f.adapter.tile_neighbors(93, 7, f.grid[0] | f.grid[1] << 16)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertEqual(result['reason'],
                             'EDGE_TYPED_READ_CHANGED' if stale else 'EDGE_CURRENT_START_GRID_MISMATCH')
            self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))

    def test_server_callback_uses_authoritative_query_even_when_client_grid_has_advanced(self):
        for observed in ((32572, 32950), (32569, 32949), (32576, 32960)):
            with self.subTest(observed_client_grid=observed):
                f = Fixture(); position = f.adapter.public['Position']
                f.put(f.transform + f.adapter.position_source['coordinates']['transform_grid_offset'], '<ii', *observed)
                f.put(f.transform + position['pair_offset'], '<ii', *((n >> 6) + 0x7e00 for n in observed))
                with patch.object(f.adapter.tile, 'probe_cells', wraps=f.adapter.tile.probe_cells) as probes:
                    self.assertIs(f.call(), True, f.adapter.last_result)
                    probes.assert_called_once_with(f.grid, 2)
                result = f.adapter.last_result
                self.assertEqual(result['status'], 'CLEAR_EMPTY_SUBSET')
                self.assertEqual(result['observed_client_grid'], list(observed))
                self.assertEqual(result['authoritative_start_grid'], list(f.grid))
                self.assertIs(result['client_grid_used_as_authority'], False)
                self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))
        for corrupt in ('range', 'segment_relation'):
            with self.subTest(invalid_client_position=corrupt):
                f = Fixture()
                if corrupt == 'range':
                    f.put(f.transform + f.adapter.position_source['coordinates']['transform_grid_offset'],
                          '<ii', -1, f.grid[1])
                else:
                    f.put(f.transform + f.adapter.public['Position']['pair_offset'], '<ii', 0, 0)
                with patch.object(f.adapter.tile, 'probe_cells', wraps=f.adapter.tile.probe_cells) as probes:
                    self.assertIsNone(f.call())
                    probes.assert_not_called()
                self.assertEqual(f.adapter.last_result['reason'], 'EDGE_CLIENT_POSITION_INVALID')

    def test_binding_rejects_custom_duplicate_validator(self):
        reader = observe.RetainedSceneReader.__new__(observe.RetainedSceneReader)
        adapter = edge.EdgeAdapter(reader)
        reader.contract = {}
        reader.backend = SimpleNamespace(contract=reader.contract, validate=lambda: None)
        reader.sampler = SimpleNamespace(b=reader.backend, c=reader.contract)
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_EDGE_NATIVE_VALIDATE_METHOD_REQUIRED'):
            adapter._binding()

    def test_binding_accepts_original_methods_with_exact_retained_validator(self):
        adapter, reader, native = self.retained_binding()
        self.assertEqual(adapter._binding(), (native, reader.sampler))
        # marshal's reference flags can differ for unchanged code when a tuple
        # is retained by a source checker/debugger. Code identity is unchanged.
        held_constants = native.read.__func__.__code__.co_consts
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_READER_METHOD_REQUIRED'):
            adapter.nav._same_method(native, 'read', adapter.nm.Native.read)
        self.assertEqual(adapter._binding(), (native, reader.sampler))
        self.assertIs(held_constants, native.read.__func__.__code__.co_consts)
        native.read = lambda *args: bytes(1)
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_EDGE_NATIVE_READ_METHOD_REQUIRED'):
            adapter._binding()

    def retained_binding(self):
        reader = observe.RetainedSceneReader.__new__(observe.RetainedSceneReader)
        adapter = edge.EdgeAdapter(reader)
        reader.contract = {'checks': [], 'bounds': {'typed_byte_limit': 8192}}
        # The real observer loads these separately from CP73's _bindings().
        native_module = observe.load('tools/normal_online_memory/native.py', '_edge_test_current_native')
        reader.sampler_module = observe.load('tools/online_intro_capture_20261006/sampler.py',
                                            '_edge_test_current_sampler')
        native = native_module.Native.__new__(native_module.Native)
        native.contract, native.handle = reader.contract, 71
        native.validate = reader.validate
        reader.backend = native
        reader.sampler = reader.sampler_module.Sampler(native, reader.contract, {})
        reader.closed = False
        reader.member = SimpleNamespace(pid=9, identity=dict(pid=9, birth='12',
            image='C:/fixture.exe', parent_pid=1))
        def in_job(handle, job, result):
            result._obj.value = True
            return True
        reader.owner = SimpleNamespace(validate=lambda _: True, owner_job=7,
            native=SimpleNamespace(identity=lambda *args, **kw: dict(reader.member.identity),
                                   k=SimpleNamespace(IsProcessInJob=in_job)))
        return adapter, reader, native

    def test_current_reader_method_global_and_owner_proof_tamper_fail_closed(self):
        for change in ('sampler_read', 'sampler_route', 'global', 'identity', 'job', 'owner', 'validator'):
            with self.subTest(change=change):
                adapter, reader, native = self.retained_binding()
                if change == 'sampler_read': reader.sampler.read = lambda *args: bytes(1)
                if change == 'sampler_route': reader.sampler.route = lambda: ()
                if change == 'identity':
                    reader.owner.native.identity = lambda *args, **kwargs: dict(reader.member.identity, birth='13')
                if change == 'job':
                    reader.owner.native.k.IsProcessInJob = lambda *args: False
                if change == 'owner': reader.owner.validate = lambda _: False
                if change == 'validator': native.validate = lambda: True
                if change == 'global':
                    with patch.dict(native.read.__func__.__globals__, require=lambda *args: None):
                        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_EDGE_NATIVE_READ_GLOBAL_REQUIRED'):
                            adapter._binding()
                else:
                    with self.assertRaises(ValueError): adapter._binding()


class ManualMovementBudgetTests(unittest.IsolatedAsyncioTestCase):
    """Saved source guards + real retained Native, injected local world only.

    Seven subsystems, two actors and retained spatial-history nodes model the
    direct-play shape. The exact historical runtime nodes were not recorded;
    this is a source/layout-realistic budget counterexample, not a RAM replay.
    """
    async def fixture(self, prefix=False):
        # Import only after edge_tests is initialized: these existing fixtures
        # import this module, and execute no Native initializer or producer main.
        from tools.local_original_session import npc_edge_tests
        case = npc_edge_tests.NpcSelfEdgeTests(
            'test_same_query_actual_source_self_subset_and_real_send_once_commit')
        self.addCleanup(case.doCleanups)
        # Its inherited synthetic fixture bypasses PersistentBroker.__init__.
        # Supply only that constructor's optional respawn default, including the
        # inherited setup's initial _send; keep the real constructor untouched.
        from tools.local_original_session.broker import PersistentBroker
        respawn_default = patch.object(PersistentBroker, '_npc_respawn', None, create=True)
        respawn_default.start()
        self.addCleanup(respawn_default.stop)
        await case.asyncSetUp()
        self.addCleanup(case.temp.cleanup)
        proof, f = case.adapter._proof, case.f
        p, c = proof.public, f.c
        objects = [(0x300000, p['Player']['ActorSubsystem']['rva']),
                   (0x310000, p['Map']['table']['rva']),
                   (0x320000, c['tables']['GameState'][0]['rva']),
                   (0x350000, proof.lookup_contract['character']['rva'])]
        objects += [(0x360000 + i * 0x10000, c['tables'][role][0]['rva'])
                    for i, role in enumerate(('NP', 'UI', 'Scheduler'))]
        for index, (obj, vp) in enumerate(objects):
            f.put(obj, '<Q', f.base + vp)
            f.put(0x220000 + index * 16, '<QQ', obj, 0x250000)
        f.put(0x210000 + c['layout']['GI_begin'], '<QQ', 0x220000, 0x220000 + len(objects) * 16)
        f.put(0x350000 + 0x6d8, '<Q', case.realm.profile_uid)
        if prefix:
            f.put(f.vector, '<QQQQ', f.npc, 0x250000, f.player, 0x250000)
        for store in (0, 1):
            self.history(case, store, 28)
        return case

    @staticmethod
    def history(case, store, count):
        proof, f = case.adapter._proof, case.f
        head, buckets = 0x800000 + store * 0x20000, 0x810000 + store * 0x20000
        keys = [case.target] + [(case.grid[0] - i - 1, case.grid[1]) for i in range(count - 1)]
        keys.sort(key=lambda key: proof.nav.destination_hash(key) & 63)
        nodes = [0xa00000 + store * 0x10000 + index * 64 for index in range(count)]
        f.put(f.actors + 0x798 + store * 64, '<fI7Q', 1.0, 0, head, count,
              buckets, buckets + 1024, buckets + 1024, 63, 64)
        f.put(head, '<QQ', nodes[0], nodes[-1])
        groups = {}
        for index, (key, node) in enumerate(zip(keys, nodes)):
            groups.setdefault(proof.nav.destination_hash(key) & 63, []).append(node)
            own = store == 1 and key == case.target
            vector = 0x940000 + store * 0x10000 if own else 0
            f.put(node, '<QQiiQQQ', nodes[index + 1] if index + 1 < count else head,
                  nodes[index - 1] if index else head, *key, vector, vector + 8 if own else 0,
                  vector + 8 if own else 0)
            if own:
                f.put(vector, '<Q', f.player)
        for bucket in range(64):
            group = groups.get(bucket)
            f.put(buckets + bucket * 16, '<QQ', *((group[0], group[-1]) if group else (head, head)))

    @staticmethod
    def move(case):
        start = case.grid[0] | case.grid[1] << 16
        target = case.target[0] | case.target[1] << 16
        return case.adapter._proof(case.realm.profile_uid, 0, start, 2, target)

    async def test_actual_source_shape_old_cap_refuses_new_cap_preserves_every_read_and_hash(self):
        metrics = {}
        for prefix in (False, True):
            case = await self.fixture(prefix)
            proof, f = case.adapter._proof, case.f
            traces = []
            for limit in (32768, edge.LIMIT, edge.LIMIT):
                f.calls.clear()
                with patch.object(edge, 'LIMIT', limit):
                    accepted = self.move(case)
                result = dict(proof.last_result)
                trace = [(at, size, hashlib.sha256(f.read(at, size)).hexdigest()) for at, size in f.calls]
                traces.append(trace)
                self.assertEqual(result['typed_bytes_requested'], sum(size for _, size in f.calls))
                self.assertLessEqual(result['typed_bytes_requested'], limit)
                self.assertTrue(all(0 < size <= 4096 for _, size in f.calls))
                self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))
                self.assertNotIn('read', f.s.__dict__)
                if limit == 32768:
                    self.assertIsNone(accepted)
                    self.assertEqual((result['reason'], result['phase']),
                                     ('EDGE_REQUEST_BYTE_BOUND', 'SOURCE_AFTER'))
                else:
                    self.assertIs(accepted, True, result)
                    self.assertEqual(result['status'], 'CLEAR_OWN_SELF_SUBSET')
                    self.assertEqual(result['raw_candidates_by_store'], [0, 1])
                    self.assertEqual(result['uid_lookup_prefix_count'], int(prefix))
                    self.assertEqual(result['source_code_bytes_requested'], 22614)
                    self.assertEqual(result['source_code_bytes_requested'], result['source_code_bytes_planned'])
                    self.assertEqual(result['lookup_code_bytes_requested'], 924)
                    self.assertEqual(result['official_navigation_equivalence'], 'UNKNOWN')
                metrics[f'prefix{int(prefix)}_limit{limit}'] = result
            self.assertEqual(traces[0], traces[1][:len(traces[0])])
            self.assertEqual(traces[1], traces[2])  # Fresh per-call budget, same physical reads.
            self.assertEqual(metrics[f'prefix{int(prefix)}_limit32768']['required_total_bytes'],
                             metrics[f'prefix{int(prefix)}_limit{edge.LIMIT}']['typed_bytes_requested'])
        type(self).metrics = metrics

    async def test_full_shape_source_before_footer_partial_image_and_typed_changes_fail_closed(self):
        for fault, after in (('source', False), ('source', True), ('lookup', False), ('lookup', True),
                             ('partial', False), ('partial', True), ('image', False), ('image', True),
                             ('typed', True), ('owner', True)):
            with self.subTest(fault=fault, after=after):
                case = await self.fixture(True)
                proof, f = case.adapter._proof, case.f
                check = (proof.lookup_contract['code_checks'][0] if fault == 'lookup' else proof.checks[0])
                target = f.base + check['rva']
                if fault == 'typed':
                    target = f.player + 24
                hits = [0]
                def mutate(at, size, raw):
                    if at == target:
                        hits[0] += 1
                        if hits[0] == (2 if after else 1):
                            if fault == 'partial': return raw[:-1]
                            if fault in ('source', 'lookup', 'typed'): return bytes([raw[0] ^ 1]) + raw[1:]
                    return raw
                f.fault = mutate
                original_query = f.query
                image_hits = [0]
                def query(handle, at, info, size):
                    result = original_query(handle, at, info, size)
                    if at == target:
                        image_hits[0] += 1
                        if image_hits[0] == (2 if after else 1):
                            info._obj.allocation_base = f.base + 0x1000
                    return result
                if fault == 'image':
                    f.native.k.VirtualQueryEx = query
                if fault == 'owner':
                    original_validate = proof.reader.owner.validate
                    def invalidate(at, size, raw):
                        if at == f.player + 24:
                            proof.reader.owner.validate = lambda _: False
                        return raw
                    f.fault = invalidate
                    self.addCleanup(setattr, proof.reader.owner, 'validate', original_validate)
                self.assertIsNone(self.move(case))
                reason = proof.last_result['reason']
                expected = {'source': 'WORLD_RUNTIME_SOURCE_CHANGED', 'lookup': 'EDGE_LOOKUP_CODE_CHANGED',
                            'partial': 'RPM_failed_or_partial', 'image': 'module_allocation_mismatch',
                            'typed': 'EDGE_TYPED_READ_CHANGED', 'owner': 'RETAINED_PRIMARY_NOT_LIVE'}
                self.assertEqual(reason, expected[fault], proof.last_result)
                self.assertEqual(proof.last_result['status'], 'UNKNOWN')
                self.assertEqual((f.s.bytes, f.s.read_limit, f.s.total), (77, 8192, 900))
                self.assertNotIn('read', f.s.__dict__)

    async def test_actor_geometry_bound_and_request_budget_still_refuse(self):
        case = await self.fixture()
        proof, f = case.adapter._proof, case.f
        f.put(f.actors + proof.public['Player']['vector_end'], '<Q',
              f.vector + (proof.public['Player']['max_actor_elements'] + 1) * 16)
        self.assertIsNone(self.move(case))
        self.assertEqual(proof.last_result['reason'], 'WORLD_VECTOR_COUNT_BOUND')
        budget, calls, _ = BudgetDedupTests.budget()
        # A valid 4096-byte read is exercised by a bounded injected Native.
        budget.native.read = lambda at, size, image=None: calls.append((at, size, image)) or bytes(size)
        for _ in range(edge.LIMIT // 4096): budget.read(0x20000, 4096)
        self.assertEqual(budget.spent, edge.LIMIT)
        count = len(calls)
        with self.assertRaisesRegex(ValueError, 'EDGE_REQUEST_BYTE_BOUND'):
            budget.read(0x20000, 1)
        with self.assertRaisesRegex(ValueError, 'EDGE_TYPED_READ_BOUND'):
            budget.read(0x20000, 4097)
        self.assertEqual((budget.spent, len(calls)), (edge.LIMIT, count))


if __name__ == '__main__': unittest.main()
