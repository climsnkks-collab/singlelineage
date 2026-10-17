"""Injected memory plus real realm/send/source helpers; no native initializer.

Live instruction/table bytes are synthetic as in edge_tests.Fixture. These tests
exercise the pinned helpers, not runtime CONTROL parity or an atomic snapshot.
"""
from dataclasses import replace
import hashlib
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import (attack_tests, edge, edge_tests, movement, npc_edge,
    npc_motion_tests, npc_observe, npc_observe_tests)


class NpcEdgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Reuse the existing real LocalRealm/PersistentPolicy/write+drain setup;
        # NpcMotion source_ready and NPC source pins are never patched.
        await npc_motion_tests.ConnectedMotionTests.asyncSetUp(self)
        self.f = edge_tests.Fixture()
        self.adapter = npc_edge.NpcEdgeAdapter(self.f.adapter.reader, current=self.binding)
        # Preserve actual helpers loaded and pinned by the constructor; inject
        # only the same synthetic retained-memory proof used by edge_tests.
        self.assertEqual(self.adapter._proof.checks, edge.EdgeAdapter(self.f.adapter.reader).checks)
        self.adapter._proof = self.f.adapter
        self.policy.handle, self.policy.job = 0x123456, 0x234567
        member = SimpleNamespace(process=self.policy.handle, job=self.policy.job)
        retained = SimpleNamespace(child=member, owner_handle=self.policy.handle,
                                   owner_job=self.policy.job, closed=False)
        self.f.adapter.reader.owner, self.f.adapter.reader.member = retained, member
        self.policy.owner = retained
        selected = self.realm.service(self.writer).snapshot()
        self.f.put(self.f.player + 24, '<Q', selected.uid)
        self.f.put(self.f.map + 0x718, '<ii', 0, 0)
        self.f.put(self.f.context, '<i', 0)
        # The historical single-direction fixture overlaps store0's bucket0
        # with store1's sentinel. Separate them for actual eight-key queries.
        self.buckets = (0x660000, 0x670000)
        for index, buckets in enumerate(self.buckets):
            head = 0x600000 + index * 0x10000
            self.f.put(self.f.actor + 0x798 + index * 64, '<fI7Q', 1.0, 0, head, 0,
                       buckets, buckets + 128, buckets + 128, 7, 8)
            self.f.put(head, '<QQ', head, head)
            for bucket in range(8):
                self.f.put(buckets + bucket * 16, '<QQ', head, head)
        self.f.grid = tuple(movement.authority.unpack_grid(self.initial.packed))
        segment = tuple((n >> 6) + 0x7e00 for n in self.f.grid)
        self.f.put(0x1a0000 + 32, '<I', (segment[0] << 16) | segment[1])
        for direction in range(8):
            for _, (x, y) in self.f.adapter.tile.probe_cells(self.f.grid, direction):
                row = 0x400000 + y * 0x1000
                self.f.put(0x300000 + y * 24, '<QQQ', row, row + 128 * 8, row + 128 * 8)
                self.f.put(row + x * 8, '<IHH', 0, 0, 0)
        self.realm.npc_edge_passability = self.adapter

    def binding(self):
        return npc_edge.NpcEdgeBinding(self.writer, self.producer)

    def call(self, direction=2, **changes):
        delta = movement.authority.DELTAS[direction if type(direction) is int and 0 <= direction < 8 else 2]
        target = tuple(a + b for a, b in zip(self.f.grid, delta))
        request = dict(uid=self.initial.uid, map_id=0, start=self.initial.packed,
                       direction=direction, destination=movement.authority.pack_grid(*target))
        request.update(changes)
        return self.adapter(**request)

    async def test_real_broker_send_and_all_eight_actual_helper_queries(self):
        proof = self.adapter._proof
        with patch.object(proof.tile, 'probe_cells', wraps=proof.tile.probe_cells) as probes, \
             patch.object(proof.nav, 'empty_store', wraps=proof.nav.empty_store) as stores:
            for direction in range(8):
                self.assertIs(self.call(direction), True, self.adapter.last_result)
            self.assertEqual(probes.call_count, 8)
            self.assertEqual(stores.call_count, 16)
        with patch.object(edge, '_world', wraps=edge._world) as world:
            state = await self.producer.step_npc(
                self.writer, goal=(self.x + 1, self.y), direction=2, now_ns=1000)
            # The selected UID remains the actual MyPlayer UID (not NPC UID).
            self.assertEqual(world.call_args.args[5], self.realm.profile_uid)
        self.assertEqual(state.packed, movement.authority.pack_grid(self.x + 1, self.y))
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertEqual(self.writer.drain.await_count, 1)
        self.assertEqual(self.adapter.last_result['occupancy'], 'BOTH_COMPLETE_TARGETS_EMPTY')
        self.assertEqual(self.adapter.last_result['official_navigation_equivalence'], 'UNKNOWN')
        self.assertEqual((self.f.s.bytes, self.f.s.read_limit, self.f.s.total), (77, 8192, 900))

    async def test_terrain_mask_one_blocks_eight_directions_without_occupancy_claim(self):
        for direction in range(8):
            cells = self.f.adapter.tile.probe_cells(self.f.grid, direction)
            addresses = [0x400000 + y * 0x1000 + x * 8 + 4 for _, (x, y) in cells]
            for at in addresses:
                self.f.put(at, '<H', 1)
            self.assertIs(self.call(direction), False, self.adapter.last_result)
            self.assertEqual(self.adapter.last_result['occupancy'], 'UNKNOWN')
            for at in addresses:
                self.f.put(at, '<H', 0)
        self.writer.write.assert_not_called()

    async def test_empty_query_rebound_handle_value_is_not_same_admission(self):
        original = self.f.native.read
        changed = []
        retained, member = self.f.adapter.reader.owner, self.f.adapter.reader.member
        def read(address, size, image=None):
            raw = original(address, size, image)
            if address == self.f.player + 24 and not changed:
                changed.append(True)
                member.process += 0x10000
                self.policy.handle = retained.owner_handle = member.process
            return raw
        self.f.native.read = read
        self.assertIsNone(self.call(), self.adapter.last_result)
        self.assertEqual(changed, [True])
        self.assertEqual(self.adapter.last_result['reason'], 'NPC_EDGE_AUTHORITY_CHANGED')
        self.writer.write.assert_not_called()

    async def test_nonempty_self_npc_player_and_foreign_pointers_remain_unknown(self):
        # This older synthetic fixture has no Monster source/read proof.
        # Labels such as "self NPC" cannot bypass the new exact source guards.
        original_data = dict(self.f.data)
        for pointer in (0x125000, self.f.player, 0x126000):
            for store in (0, 1):
                self.f.data = dict(original_data)
                target = tuple(self.f.adapter.tile.map_step(self.f.grid, 2)['grid_target'])
                head, buckets = 0x600000 + store * 0x10000, self.buckets[store]
                node, vector = 0x700000 + store * 0x10000, 0x740000 + store * 0x10000
                self.f.put(self.f.actor + 0x798 + store * 64 + 16, '<Q', 1)
                self.f.put(head, '<QQ', node, node)
                self.f.put(node, '<QQiiQQQ', head, head, *target, vector, vector + 8, vector + 8)
                self.f.put(vector, '<Q', pointer)
                self.f.put(buckets + (self.f.adapter.nav.destination_hash(target) & 7) * 16,
                           '<QQ', node, node)
                self.assertIsNone(self.call())
                self.assertEqual(self.adapter.last_result['reason'], 'SYNTHETIC_CELL_UNREADABLE')
                self.assertEqual(self.adapter.last_result['nonempty_self_npc'], 'UNKNOWN')

    async def test_malformed_or_incomplete_store_never_mints_clear(self):
        # Second-store corruption must invalidate a clean first store.
        self.f.put(self.f.actor + 0x798 + 0x40 + 16, '<Q', 1)
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['reason'], 'SPATIAL_SENTINEL_SIZE_INCONSISTENT')
        self.writer.write.assert_not_called()

    async def test_uid_map_start_destination_direction_and_constructed_binding_refuse(self):
        for change in (dict(uid=93), dict(uid=True), dict(map_id=7), dict(start=self.initial.packed + 1),
                       dict(destination=self.initial.packed), dict(direction=True), dict(direction=8)):
            self.assertIsNone(self.call(**change), (change, self.adapter.last_result))
        self.adapter.current = lambda: True
        self.assertIsNone(self.call())
        self.adapter.current = lambda: npc_edge.NpcEdgeBinding(self.writer, object())
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['reason'], 'NPC_EDGE_REAL_BROKER_REQUIRED')

    async def test_incomplete_read_and_changed_tile_recheck_remain_unknown(self):
        original = self.f.native.read
        segment, (x, y) = self.f.adapter.tile.probe_cells(self.f.grid, 2)[0]
        at = 0x400000 + y * 0x1000 + x * 8
        for partial in (True, False):
            count = [0]
            def read(address, size, image=None):
                raw = original(address, size, image)
                if address == at and size == 8:
                    count[0] += 1
                    if partial:
                        return raw[:-1]
                    if count[0] == 2:
                        return raw[:4] + b'\x01\0' + raw[6:]
                return raw
            self.f.native.read = read
            self.assertIsNone(self.call())
            self.assertEqual(self.adapter.last_result['reason'],
                             'EDGE_PARTIAL_TYPED_READ' if partial else 'EDGE_TYPED_READ_CHANGED')
        self.assertEqual((self.f.s.bytes, self.f.s.read_limit, self.f.s.total), (77, 8192, 900))

    async def test_owner_selection_reader_and_mover_lifetime_changes_are_unknown(self):
        original, initial_state = self.f.native.read, self.mover.state
        saved_selected = dict(self.realm.registry.selected)
        service = self.realm.service(self.writer)
        selected_position = service.snapshot()
        reader_owner = self.f.adapter.reader.owner
        mutations = (
            lambda: self.realm.registry.selected.clear(),
            lambda: setattr(self.mover, 'closed', True),
            lambda: setattr(self.mover, 'fatal', True),
            lambda: setattr(self.mover, 'spawn_drained', False),
            lambda: setattr(self.mover, 'state', replace(initial_state)),
            lambda: setattr(self.mover, 'state', replace(initial_state, uid=999)),
            lambda: setattr(self.mover, 'state', replace(initial_state, map_id=7)),
            lambda: setattr(service, '_position', replace(selected_position)),
            lambda: setattr(self.f.adapter.reader, 'owner', object()),
            lambda: setattr(self.adapter, 'current', lambda: npc_edge.NpcEdgeBinding(object(), self.producer)),
        )
        for mutate in mutations:
            count = [0]
            def read(address, size, image=None):
                raw = original(address, size, image)
                if address == self.f.player + 24:
                    count[0] += 1
                    if count[0] == 2:
                        mutate()
                return raw
            self.f.native.read = read
            self.assertIsNone(self.call(), self.adapter.last_result)
            self.realm.registry.selected.update(saved_selected)
            self.mover.closed = self.mover.fatal = False
            self.mover.spawn_drained, self.mover.state = True, initial_state
            service._position = selected_position
            self.f.adapter.reader.owner = reader_owner
            self.adapter.current = self.binding

    async def test_other_real_broker_same_uid_map_and_retained_bindings_refuse(self):
        other = NpcEdgeTests('test_real_broker_send_and_all_eight_actual_helper_queries')
        await other.asyncSetUp()
        self.addCleanup(other.temp.cleanup)
        self.assertEqual(other.mover.state, self.mover.state)
        self.adapter.current = other.binding
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['reason'], 'NPC_EDGE_SAME_RETAINED_BROKER_REQUIRED')
        self.adapter.current = self.binding
        retained, member = self.f.adapter.reader.owner, self.f.adapter.reader.member
        before = (retained.owner_handle, retained.owner_job, retained.child, member.process, member.job)
        mutations = (
            lambda: setattr(self.policy, 'owner', SimpleNamespace(**vars(retained))),
            lambda: setattr(retained, 'owner_handle', object()),
            lambda: setattr(retained, 'owner_job', object()),
            lambda: setattr(retained, 'child', SimpleNamespace(**vars(member))),
            lambda: setattr(member, 'process', object()),
            lambda: setattr(member, 'job', object()),
        )
        for mutate in mutations:
            mutate()
            self.assertIsNone(self.call())
            self.assertEqual(self.adapter.last_result['reason'], 'NPC_EDGE_SAME_RETAINED_BROKER_REQUIRED')
            self.policy.owner = retained
            retained.owner_handle, retained.owner_job, retained.child, member.process, member.job = before

    async def test_admission_and_broker_loss_before_or_during_read_refuse(self):
        original_read, policy_row = self.f.native.read, self.row['policy_row']
        claims = {port: list(rows) for port, rows in self.producer._claims.items()}
        retained, member = self.f.adapter.reader.owner, self.f.adapter.reader.member
        mutations = (
            lambda: setattr(self.producer, '_closing', True),
            self.producer.failure.set,
            lambda: self.producer._claims[14030].clear(),
            lambda: self.row.update(failed=True),
            lambda: self.row.update(joined=True),
            lambda: self.row.update(policy_row=object()),
            lambda: setattr(policy_row, 'failed', True),
            lambda: setattr(policy_row, 'eof', True),
            lambda: setattr(policy_row, 'stage', 0),
            lambda: setattr(self.policy, 'state', 'STOPPED'),
            lambda: setattr(retained, 'closed', True),
            lambda: setattr(retained, 'child', SimpleNamespace(**vars(member))),
        )
        for during_read in (False, True):
            for mutate in mutations:
                count = [0]
                def read(address, size, image=None):
                    raw = original_read(address, size, image)
                    if address == self.f.player + 24:
                        count[0] += 1
                        if count[0] == 2:
                            mutate()
                    return raw
                self.f.native.read = read if during_read else original_read
                if not during_read:
                    mutate()
                self.assertIsNone(self.call(), self.adapter.last_result)
                self.producer._closing = False
                self.producer.failure.clear()
                self.producer._claims = {port: list(rows) for port, rows in claims.items()}
                self.row.update(failed=False, joined=False, policy_row=policy_row)
                policy_row.failed, policy_row.eof, policy_row.stage = False, False, 1
                self.policy.state = 'OPEN'
                retained.closed, retained.child = False, member

    async def test_real_selected_player_uid_and_map_are_separate_reader_anchors(self):
        uid_at = self.f.player + self.f.adapter.public['Player']['ActorID']
        self.f.put(uid_at, '<Q', self.initial.uid)
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['reason'], 'EDGE_CURRENT_UID_MAP_MISMATCH')
        self.f.put(uid_at, '<Q', self.realm.profile_uid)
        self.f.put(self.f.context, '<i', 7)
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['reason'], 'EDGE_CURRENT_UID_MAP_MISMATCH')

    async def test_source_and_world_route_changes_refuse(self):
        proof = self.f.adapter
        self.f.put(self.f.base + 0x500, '4s', b'CODE')
        proof.checks = [dict(rva=0x500, length=4, sha256=hashlib.sha256(b'CODE').hexdigest())]
        self.assertIs(self.call(), True)
        original, seen = self.f.native.read, [0]
        def changed_source(at, size, image=None):
            raw = original(at, size, image)
            if at == self.f.base + 0x500:
                seen[0] += 1
                if seen[0] == 2:
                    return b'FAIL'
            return raw
        self.f.native.read = changed_source
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['phase'], 'SOURCE_AFTER')
        self.f.native.read = original
        route, count = self.f.route, [0]
        def changed_route():
            count[0] += 1
            return route if count[0] == 1 else (*route[:-1], {'GameState': [0x150001]})
        self.f.s.route = changed_route
        self.assertIsNone(self.call())
        self.assertEqual(self.adapter.last_result['reason'], 'EDGE_WORLD_OWNER_CHANGED')


class BindingTests(unittest.TestCase):
    def test_constructor_is_read_free_and_real_retained_binding_rejects_tamper(self):
        # __new__ avoids every Native constructor/process API. The existing
        # injected identity/job functions exercise only the retained validator.
        proof, reader, native = edge_tests.Tests().retained_binding()
        adapter = npc_edge.NpcEdgeAdapter(reader, current=lambda: None)
        self.assertEqual(adapter._proof._binding(), (native, reader.sampler))
        native.read = lambda *_: b''
        with self.assertRaisesRegex(ValueError, 'EXACT_RETAINED_EDGE_NATIVE_READ_METHOD_REQUIRED'):
            adapter._proof._binding()


class NpcSelfEdgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await npc_observe_tests.NpcObservationTests.asyncSetUp(self)
        self.adapter = npc_edge.NpcEdgeAdapter(self.reader,
            current=lambda: npc_edge.NpcEdgeBinding(self.writer, self.producer))
        self.realm.npc_edge_passability = self.adapter
        self.f = self.memory
        self.grid = tuple(movement.authority.unpack_grid(self.initial.packed))
        # Same source-bound observer memory and exact Native/Sampler methods.
        # Add only the existing tile/spatial-store fixture structures.
        context, head, node, resource = 0x330000, 0x610000, 0x620000, 0x630000
        self.f.put(context + 8, '<QQ', head, 1)
        self.f.put(head, '<QQQBB', node, node, node, 1, 1)
        segment = tuple((v >> 6) + 0x7e00 for v in self.grid)
        self.f.put(node, '<QQQBB6xI4xQQ', head, head, head, 1, 0,
                   (segment[0] << 16) | segment[1], resource, 0x250000)
        self.f.put(resource, '<QQQ', 0x640000, 0x640000 + 64 * 24, 0x640000 + 64 * 24)
        self.f.put(resource + 24, '<QQ', 0x650000, 0)
        self.f.put(0x650000, '<QQQBB', 0x650000, 0x650000, 0x650000, 1, 1)
        for direction in range(8):
            for _, (x, y) in self.adapter._proof.tile.probe_cells(self.grid, direction):
                row = 0x700000 + y * 0x1000
                self.f.put(0x640000 + y * 24, '<QQQ', row, row + 128 * 8, row + 128 * 8)
                self.f.put(row + x * 8, '<IHH', 0, 0, 0)
        self.target = tuple(self.adapter._proof.tile.map_step(self.grid, 2)['grid_target'])
        self.spatial(0, [self.f.npc])
        self.spatial(1, [self.f.npc])

    def spatial(self, store, pointers):
        head, buckets = 0x800000 + store * 0x20000, 0x810000 + store * 0x20000
        node, vector = 0x900000 + store * 0x10000, 0x940000 + store * 0x10000
        self.f.put(self.f.actors + 0x798 + store * 64, '<fI7Q', 1.0, 0, head, int(bool(pointers)),
                   buckets, buckets + 128, buckets + 128, 7, 8)
        self.f.put(head, '<QQ', node if pointers else head, node if pointers else head)
        for bucket in range(8):
            self.f.put(buckets + bucket * 16, '<QQ', head, head)
        if pointers:
            self.f.put(node, '<QQiiQQQ', head, head, *self.target,
                       vector, vector + 8 * len(pointers), vector + 8 * len(pointers))
            self.f.put(vector, '<' + 'Q' * len(pointers), *pointers)
            index = self.adapter._proof.nav.destination_hash(self.target) & 7
            self.f.put(buckets + index * 16, '<QQ', node, node)
        return node, vector

    def call(self):
        result = self.adapter(self.initial.uid, 0, self.initial.packed, 2,
                              movement.authority.pack_grid(*self.target))
        self.assertEqual((self.f.s.bytes, self.f.s.read_limit, self.f.s.total), (77, 8192, 900))
        self.assertNotIn('read', self.f.s.__dict__)
        self.assertLessEqual(self.adapter.last_result['typed_bytes_requested'], 32768)
        return result

    async def test_same_query_actual_source_self_subset_and_real_send_once_commit(self):
        self.assertIs(self.call(), True, self.adapter.last_result)
        row = self.adapter.last_result
        self.assertEqual(row['status'], 'CLEAR_EXACT_SELF_NPC_SUBSET')
        self.assertEqual(row['nonempty_self_npc'], 'EXACT_CURRENT_MOVING_MONSTER')
        self.assertEqual(row['raw_candidates_by_store'], [1, 1])
        self.assertEqual(row['self_npc_candidates'], 2)
        self.assertEqual(row['observed_npc_grid'], list(self.grid))
        self.assertEqual(row['typed_bytes_requested'], sum(size for _, size in self.f.calls))
        type(self).positive_metrics = dict(typed_bytes_requested=row['typed_bytes_requested'],
            typed_byte_limit=32768, native_read_count=len(self.f.calls),
            self_npc_candidates=2, source_ready_mock=False, snapshot_atomic=False,
            official_navigation_equivalence='UNKNOWN', game_runs=0, process_API_calls=0)
        self.writer.write.assert_not_called()
        before = self.mover.state
        moved = await self.producer.step_npc(self.writer, goal=self.target, direction=2, now_ns=1000)
        self.assertEqual(moved.packed, movement.authority.pack_grid(*self.target))
        self.assertIs(self.mover.state, moved)
        self.assertIsNot(moved, before)
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertEqual(self.writer.drain.await_count, 1)
        self.assertEqual(self.policy.log[-1][2], 0x4e2c)
        with self.assertRaises(ValueError):
            self.mover.commit(moved)
        self.assertEqual(self.writer.write.call_count, 1)

    async def test_large_ctypes_primary_same_handle_value_keeps_exact_self_positive(self):
        member = attack_tests.TargetTests.ctypes_primary(self)
        self.assertEqual(member.process, member.process)
        self.assertIsNot(member.process, member.process)
        self.assertIs(self.call(), True, self.adapter.last_result)
        self.assertEqual(self.adapter.last_result['nonempty_self_npc'], 'EXACT_CURRENT_MOVING_MONSTER')
        self.writer.write.assert_not_called()

    async def test_duplicate_handle_value_change_after_real_monster_resolve_refuses(self):
        original = npc_observe._resolve_monster
        resolved = []
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            resolved.append(result)
            # Only the scalar changes. Real Monster/source/root/read helpers
            # execute before/after, and retained validation remains installed.
            self.native.handle += 0x10000
            return result
        with patch.object(npc_observe, '_resolve_monster', changed):
            self.assertIsNone(self.call(), self.adapter.last_result)
        self.assertEqual(resolved, [(self.f.npc, list(self.grid))])
        self.assertEqual(self.adapter.last_result['reason'], 'NPC_EDGE_EXACT_AUTHORITY_CHANGED')
        self.writer.write.assert_not_called()

    async def test_foreign_same_uid_other_monster_ptr_duplicate_first_match_and_mixed_vectors_refuse(self):
        original = dict(self.f.data)
        monster, _, _ = npc_observe._source()
        other = 0x510000
        self.f.put(other, '<QQ', self.f.base + monster['rva'], other)
        self.f.put(other + 24, '<Q', self.initial.uid)
        with_other = dict(self.f.data)
        for pointers in ([self.f.player], [other], [self.f.npc, other], [self.f.npc, self.f.player]):
            self.f.data = dict(with_other)
            self.spatial(1, pointers)
            self.assertIsNone(self.call(), self.adapter.last_result)
            self.assertEqual(self.adapter.last_result['reason'], 'SPATIAL_TARGET_FOREIGN_OR_UNKNOWN_CANDIDATE')
        # First UID match is another actual Monster, but a different pointer.
        self.f.data = dict(with_other)
        p = self.adapter._proof.public['Position']
        self.f.put(other + p['component_begin'], '<QQ', 0x520000, 0x520010)
        self.f.put(0x520000, '<QQ', 0x530000, 0x250000)
        self.f.put(0x530000, '<Q', self.f.base + p['Transform']['rva'])
        self.f.put(0x530000 + p['borrowed_Actor'], '<Q', other)
        self.f.grid(0x530000, self.grid)
        self.f.put(self.f.vector + 16, '<QQQQ', other, 0x250000, self.f.npc, 0x250000)
        self.f.put(self.f.actors + self.adapter._proof.public['Player']['vector_end'], '<Q', self.f.vector + 48)
        self.assertIsNone(self.call(), self.adapter.last_result)
        self.assertEqual(self.adapter.last_result['reason'], 'SPATIAL_TARGET_FOREIGN_OR_UNKNOWN_CANDIDATE')
        # First match of a different primary subtype is never skipped either.
        self.f.put(other, '<Q', self.f.base + monster['rva'] + 56)
        self.assertIsNone(self.call(), self.adapter.last_result)
        self.f.data = dict(original)
        self.spatial(0, [self.f.npc, self.f.npc])
        self.assertIs(self.call(), True, self.adapter.last_result)
        self.assertEqual(self.adapter.last_result['raw_candidates_by_store'], [2, 1])
        self.writer.write.assert_not_called()

    async def test_wrong_uid_borrowed_transform_start_and_incomplete_store_are_unknown(self):
        original = dict(self.f.data)
        changes = [lambda: self.f.put(self.f.npc + 24, '<Q', 999),
            lambda: self.f.put(self.f.transform + self.adapter._proof.public['Position']['borrowed_Actor'], '<Q', self.f.player),
            lambda: self.f.grid(self.f.transform, [self.grid[0] + 1, self.grid[1]]),
            lambda: self.f.put(self.f.actors + 0x798 + 64 + 16, '<Q', 2)]
        for change in changes:
            self.f.data = dict(original)
            change()
            self.assertIsNone(self.call(), self.adapter.last_result)
        self.writer.write.assert_not_called()

    async def test_source_typed_and_current_authority_mutations_restore_and_refuse(self):
        original_data, selected, claims = dict(self.f.data), dict(self.realm.registry.selected), dict(self.producer._claims)
        owner, initial = self.reader.owner, self.mover.state
        original_validate = owner.validate
        grid_at = self.f.transform + self.adapter._proof.position_source['coordinates']['transform_grid_offset']
        _, _, checks = npc_observe._source()
        code_at = self.f.base + checks[0]['rva']
        mutations = [(code_at, 2, lambda: self.f.put(code_at, '<B', self.f.read(code_at, 1)[0] ^ 1)),
            (grid_at, 2, lambda: self.f.grid(self.f.transform, [self.grid[0] + 1, self.grid[1]])),
            (self.f.npc + 24, 1, self.realm.registry.selected.clear),
            (self.f.npc + 24, 1, self.producer._claims.clear),
            (self.f.npc + 24, 1, lambda: setattr(owner, 'validate', lambda _: False)),
            (self.f.npc + 24, 1, lambda: setattr(self.mover, 'state', replace(initial)))]
        for target, occurrence, mutate in mutations:
            hits = [0]
            def fault(at, size, raw):
                if at == target:
                    hits[0] += 1
                    if hits[0] == occurrence:
                        mutate()
                        return self.f.read(at, size)
                return raw
            self.f.fault = fault
            self.assertIsNone(self.call(), self.adapter.last_result)
            self.f.data = dict(original_data)
            self.realm.registry.selected.update(selected)
            self.producer._claims.update(claims)
            owner.validate, self.mover.state = original_validate, initial
        self.f.fault = None
        self.writer.write.assert_not_called()

    async def test_blocked_and_empty_preserve_existing_subset_without_monster_proof(self):
        self.f.put(self.f.npc, '<Q', 0x10000)
        for _, (x, y) in self.adapter._proof.tile.probe_cells(self.grid, 2):
            self.f.put(0x700000 + y * 0x1000 + x * 8 + 4, '<H', 1)
        self.assertIs(self.call(), False, self.adapter.last_result)
        self.assertEqual(self.adapter.last_result['status'], 'BLOCKED_MASK1')
        for _, (x, y) in self.adapter._proof.tile.probe_cells(self.grid, 2):
            self.f.put(0x700000 + y * 0x1000 + x * 8 + 4, '<H', 0)
        self.spatial(0, [])
        self.spatial(1, [])
        self.assertIs(self.call(), True, self.adapter.last_result)
        self.assertEqual(self.adapter.last_result['status'], 'CLEAR_EMPTY_SUBSET')
        self.assertEqual(self.adapter.last_result['nonempty_self_npc'], 'NOT_REQUIRED')
        self.writer.write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
