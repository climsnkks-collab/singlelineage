"""Existing real Native.read fixture; no attach/process/native initialization."""
import struct
import unittest
from unittest.mock import patch

from tools.local_original_session import attack_action_observe as a
from tools.local_original_session import attack_tests, npc_observe, npc_observe_tests
from tools.local_original_session import move_state, observe
from tools.local_native_scene_current import watch


def full_retained_reader(case):
    """Extend the existing Native.read memory with the already proved move fields."""
    m, reader = case.memory, case.reader
    layout = move_state.MoveState()
    actor, transform, action = m.player, 0x470000, case.action_component
    controller, navigation, character = 0x580000, 0x590000, 0x600000
    m.put(0x210000 + m.c['layout']['GI_end'], '<Q', 0x220000 + 64)
    m.put(0x220000 + 48, '<QQ', character, 0x250000)
    m.put(character, '<Q', m.base + layout.tables['CharacterDataSubsystem']['rva'])
    m.put(character + 0x10, '<B', 1)
    m.put(character + 0x6d8, '<Q', case.realm.profile_uid)
    m.put(character + 0x558, '<B', 0)
    m.put(m.actors + 0x10, '<B', 1)
    m.put(actor + 0x20, '<QQ', 0x460000, 0x460000 + 64)
    for index, (obj, role) in enumerate(((transform, 'TransformComponent'), (action, 'ActionComponent'),
                                       (controller, 'ActorControllerComponent'), (navigation, 'NavigationComponent'))):
        m.put(0x460000 + index * 16, '<QQ', obj, 0x250000)
        m.put(obj, '<QQ', m.base + layout.tables[role]['rva'], actor)
        m.put(obj + 0x30, '<B', 1)
    position = case.realm.service(case.writer).snapshot()
    coordinate = struct.pack('<iiii', (position.word0 >> 6) + 0x7e00, (position.word1 >> 6) + 0x7e00,
                             position.word0, position.word1) + bytes(24)
    m.put(transform + 0x38, '<80s', coordinate + coordinate)
    m.put(navigation + 0x1c0, '<60s', coordinate + bytes(20))
    m.put(controller + 0x58, '<Qi', 0, 0)
    m.put(action + 0x44, '<12s', bytes(12))
    m.put(action + 0xc0, '<Q', 0)
    m.put(action + 0xa0, '<QQQQ', 0, 0, 0, 0)
    position_source = case.observer.proof.position_source
    m.put(0x340000 + position_source['scene']['scene_object_pointer'], '<Q', 0)
    m.put(0x340000 + position_source['scene']['land_game_layer_pointer'], '<Q', 0)
    reader.watch, reader.world, reader.move_state = watch, case.observer.proof.world, layout
    reader.input_state = None
    reader.__dict__.pop('sample', None)


class AttackActionObservationTests(unittest.IsolatedAsyncioTestCase):
    metrics = {}

    async def asyncSetUp(self):
        await attack_tests.TargetTests.asyncSetUp(self)
        self.observer = npc_observe.NpcObserver(self.producer, self.reader)
        self.memory = npc_observe_tests.Memory(self)
        self.leaf = a.AttackActionObserver(self.producer, self.reader)
        self.now = 0
        self.action_component, self.target_component = 0x510000, 0x520000
        self.attack_action, self.damaged_action = 0x530000, 0x540000
        m, tables = self.memory, self.leaf.layout.tables
        # Retain each actor's existing Transform pair and add one Action pair.
        for actor, vector, component, action in (
                (m.player, 0x460000, self.action_component, self.attack_action),
                (m.npc, 0x480000, self.target_component, self.damaged_action)):
            m.put(actor + 0x20, '<QQ', vector, vector + 32)
            m.put(vector + 16, '<QQ', component, 0x570000)
            m.put(component, '<QQ', m.base + tables['ActionComponent']['rva'], actor)
            m.put(component + 0xa0, '<QQQQ', 0, 0, 0, 0)
            m.put(component + 0xc0, '<Q', action)
            m.put(action + 8, '<Q', component)
            m.put(action + 0x18, '<i', 3)
            m.put(action + 0x20, '<IB', 2, 0)
        m.put(self.attack_action, '<Q', m.base + 0x1180b78)
        m.put(0x570008, '<i', 4)
        m.put(self.damaged_action, '<Q', m.base + 0x1180bc0)
        m.put(self.attack_action + 0x80, '<QQi', self.realm.profile_uid, self.mover.state.uid, 7)
        self.scene = dict(status='OBSERVED', current='Land', pending='none', root_ready=True)
        self.world = dict(status='OBSERVED', stable_double_read=True,
            my_player_uid=self.realm.profile_uid, map_resolved_i32=self.mover.state.map_id)

    async def prepare(self):
        self.now += a.MIN_INTERVAL_NS
        await self.leaf.prepare(self.writer, self.mover.state.uid, now_ns=self.now)

    def collect(self, *, previous_total=0, cache=None):
        s = self.memory.s
        s.total, s.bytes, s.read_limit = previous_total, 0, 8192
        # Capture exactly the existing retained query's route and scene proof.
        route = s.route()
        scene, raw = s.scene(0x320000)
        proof = dict(route=route, state=0x320000, scene=scene, raw=raw)
        if callable(cache):
            cache = cache(proof)
        previous_bytes = s.bytes
        start = len(self.memory.calls)
        row = self.leaf.collect(self.scene, self.world, proof, cache)
        self.assertEqual(row['typed_bytes_requested'], sum(n for _, n in self.memory.calls[start:]))
        self.assertLessEqual(row['combined_typed_bytes_requested'], a.BYTE_LIMIT)
        self.writer.write.assert_not_called()
        self.assertEqual(self.writer.drain.await_count, 0)
        self.assertEqual((s.bytes, s.read_limit), (previous_bytes, 8192))
        return row

    async def test_actual_native_source_owner_and_typed_action_positive(self):
        await self.prepare()
        row = self.collect()
        self.assertEqual(row['status'], 'OBSERVED', row)
        self.assertTrue(row['stable_double_read'] and row['source_contract_valid'])
        self.assertEqual(row['attacker']['current']['kind'], 'AttackAction')
        self.assertEqual(row['attacker']['current']['raw_effect_i32'], 7)
        self.assertTrue(row['attacker']['current']['selected_pair_matches'])
        self.assertEqual(row['target']['current']['kind'], 'DamagedAction')
        self.assertFalse(row['start_observed'] or row['hp_claimed'] or row['rendered_claimed'])
        type(self).metrics['positive'] = {k: row[k] for k in (
            'status', 'typed_bytes_requested', 'combined_typed_bytes_requested', 'typed_byte_limit')}

    async def test_one_use_no_additional_sample_or_cadence(self):
        await self.prepare()
        self.assertEqual(self.collect()['status'], 'OBSERVED')
        self.assertEqual(self.collect()['reason'], 'ATTACK_OBSERVE_PREPARE_REQUIRED')
        with self.assertRaisesRegex(ValueError, 'ATTACK_OBSERVE_CADENCE'):
            await self.leaf.prepare(self.writer, self.mover.state.uid, now_ns=self.now + 1)

    async def test_current_queue_and_pair_mismatch_remain_raw(self):
        m = self.memory
        m.put(self.action_component + 0xc0, '<Q', 0)
        m.put(self.action_component + 0xa0, '<QQQQ', 0x550000, 8, 0, 1)
        m.put(0x550000, '<Q', 0x560000)
        m.put(0x560000, '<Q', self.attack_action)
        m.put(self.attack_action + 0x80, '<QQi', self.realm.profile_uid + 1, self.mover.state.uid, -2)
        await self.prepare()
        row = self.collect()
        self.assertEqual(row['status'], 'OBSERVED', row)
        self.assertFalse(row['attacker']['current']['present'])
        self.assertEqual(row['attacker']['queue_count'], 1)
        self.assertFalse(row['attacker']['queue_head']['selected_pair_matches'])
        self.assertEqual(row['attacker']['queue_head']['raw_effect_i32'], -2)

    async def test_owner_pair_table_uid_map_and_source_refusals(self):
        for kind in ('component_owner', 'action_owner', 'pair', 'type_table', 'uid', 'map', 'source'):
            with self.subTest(kind=kind):
                await self.asyncSetUp()
                m = self.memory
                await self.prepare()
                if kind == 'component_owner': m.put(self.target_component + 8, '<Q', m.player)
                if kind == 'action_owner': m.put(self.attack_action + 8, '<Q', self.target_component)
                if kind == 'pair': m.put(0x570008, '<i', 0)
                if kind == 'type_table': m.put(m.base + 0x1180b78, '<Q', m.base + 1)
                if kind == 'uid': self.world['my_player_uid'] += 1
                if kind == 'map': self.world['map_resolved_i32'] += 1
                if kind == 'source':
                    pins = dict(a.PINS); pins[next(iter(pins))] = '0' * 64
                    with patch.object(a, 'PINS', pins): row = self.collect()
                else:
                    row = self.collect()
                self.assertEqual(row['status'], 'UNKNOWN', row)
                self.assertIsNone(row['attacker'])
                self.assertFalse(row['stable_double_read'])

    async def test_prepared_writer_or_selected_snapshot_replaced_is_refused(self):
        for kind in ('writer', 'selected'):
            with self.subTest(kind=kind):
                await self.asyncSetUp()
                await self.prepare()
                if kind == 'writer':
                    self.row['writer'] = object()
                else:
                    self.realm.service(self.writer)._connection = object()
                row = self.collect()
                self.assertEqual(row['status'], 'UNKNOWN', row)
                self.assertEqual(row['typed_bytes_requested'], 0)
                self.assertIsNone(row['attacker'])

    async def test_final_typed_readback_and_source_after_reject_changes(self):
        for kind in ('typed', 'root', 'authority', 'source_after', 'code_after', 'positive_count_drift'):
            with self.subTest(kind=kind):
                await self.asyncSetUp()
                await self.prepare()
                hits = [0]
                at_target = self.attack_action + 0x80
                code_target = self.memory.base + npc_observe._source()[2][0]['rva']
                def fault(at, size, raw):
                    if kind == 'code_after':
                        if at == code_target:
                            hits[0] += 1
                            if hits[0] == 2: return bytes([raw[0] ^ 1]) + raw[1:]
                    if kind == 'positive_count_drift' and at == 0x570008:
                        hits[0] += 1
                        if hits[0] == 2: return struct.pack('<i', 5)
                    if at == at_target and kind in ('typed', 'root', 'authority'):
                        hits[0] += 1
                        if hits[0] == 2:
                            if kind == 'typed': return bytes([raw[0] ^ 1]) + raw[1:]
                            if kind == 'root': self.memory.put(0x200000 + self.memory.c['layout']['Root_phase'], '<I', 6)
                            if kind == 'authority': self.row['failed'] = True
                    return raw
                self.memory.fault = fault
                if kind == 'source_after':
                    original = a._source
                    calls = [0]
                    def changed_source():
                        calls[0] += 1
                        if calls[0] == 2: raise ValueError('ATTACK_OBSERVE_SOURCE_CHANGED')
                        return original()
                    with patch.object(a, '_source', changed_source): row = self.collect()
                else:
                    row = self.collect()
                self.assertEqual(row['status'], 'UNKNOWN', row)
                self.assertIsNone(row['attacker'])

    async def test_same_query_world_cache_still_receives_physical_readback(self):
        m = self.memory
        key = (m.player + 0x18, 8, False)
        cache = {key: struct.pack('<Q', self.realm.profile_uid)}
        await self.prepare()
        row = self.collect(cache=cache)
        self.assertEqual(row['status'], 'OBSERVED', row)
        cached_bytes = row['typed_bytes_requested']
        await self.prepare()
        plain = self.collect()
        self.assertEqual(plain['typed_bytes_requested'] - cached_bytes, 8)
        cache[key] = struct.pack('<Q', self.realm.profile_uid + 1)
        await self.prepare()
        self.assertEqual(self.collect(cache=cache)['status'], 'UNKNOWN')

    async def test_real_retained_scene_world_move_action_one_query_budget(self):
        # Supply the existing world tile fixture rather than a synthetic world DTO.
        from tools.local_original_session.manual_move_commands_tests import ManualAttackTests
        self.service = self.realm.service(self.writer)
        ManualAttackTests.tiles(self)
        full_retained_reader(self)
        await self.prepare()
        start = len(self.memory.calls)
        row, count = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        self.assertEqual(row['status'], 'OBSERVED', row)
        self.assertEqual(row['world']['status'], 'OBSERVED', row['world'])
        self.assertEqual(row['move_state']['status'], 'OBSERVED', row['move_state'])
        self.assertEqual(row['attack_action']['status'], 'OBSERVED', row['attack_action'])
        self.assertEqual(count, sum(n for _, n in self.memory.calls[start:]))
        self.assertLessEqual(count, a.BYTE_LIMIT)
        self.assertTrue(all(n <= 4096 for _, n in self.memory.calls[start:]))
        type(self).metrics['full_retained'] = dict(combined=count,
            action=row['attack_action']['typed_bytes_requested'], move=row['move_state']['typed_bytes_requested'])

    async def test_move_same_query_cache_saves_initial_reads_without_removing_readback(self):
        from tools.local_original_session.manual_move_commands_tests import ManualAttackTests
        self.service = self.realm.service(self.writer)
        ManualAttackTests.tiles(self)
        full_retained_reader(self)
        await self.prepare()
        row, current = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        self.assertEqual(row['attack_action']['status'], 'OBSERVED', row['attack_action'])
        await self.prepare()
        with patch.object(a.SameQueryCache, 'get', lambda cache, key: cache.roles['WORLD'].get(key)):
            old, baseline = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        self.assertEqual(old['attack_action']['status'], 'OBSERVED', old['attack_action'])
        self.assertEqual(row['move_state'], old['move_state'])
        self.assertEqual(row['world'], old['world'])
        self.assertGreater(baseline, current)
        type(self).metrics['move_cache_delta'] = dict(world_only=baseline, world_and_move=current,
            saved=baseline-current, move_physical_unchanged=row['move_state']['typed_bytes_requested'])

    async def test_source_complete_unsupported_move_field_keeps_independent_attack_snapshot(self):
        from tools.local_original_session.manual_move_commands_tests import ManualAttackTests
        self.service = self.realm.service(self.writer)
        ManualAttackTests.tiles(self)
        full_retained_reader(self)
        self.memory.put(0x580000, '<Q', self.memory.base)
        await self.prepare()
        row, count = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        self.assertEqual(row['move_state']['status'], 'OBSERVED_PARTIAL', row['move_state'])
        self.assertTrue(row['move_state']['source_contract_valid'] and row['move_state']['stable_double_read'])
        self.assertEqual(row['move_state']['controller']['status'], 'UNKNOWN')
        self.assertEqual(row['attack_action']['status'], 'OBSERVED', row['attack_action'])
        self.assertLessEqual(count, a.BYTE_LIMIT)
        self.memory.put(0x580000, '<Q', self.memory.base + self.leaf.layout.tables['ActorControllerComponent']['rva'])
        hits = [0]
        def changed_move_only(at, size, raw):
            if at == 0x580058:
                hits[0] += 1
                if hits[0] == 2:
                    return bytes([raw[0] ^ 1]) + raw[1:]
            return raw
        self.memory.fault = changed_move_only
        await self.prepare()
        row, count = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        self.assertEqual(row['move_state']['reason'], 'MOVE_TYPED_READ_CHANGED', row['move_state'])
        self.assertFalse(row['move_state']['stable_double_read'])
        self.assertEqual(row['attack_action']['status'], 'OBSERVED', row['attack_action'])
        self.assertLessEqual(count, a.BYTE_LIMIT)

    async def test_query_cache_role_stale_query_conflict_and_final_change_refuse(self):
        for kind in ('role', 'query', 'sampler', 'conflict', 'stale', 'cross_role'):
            with self.subTest(kind=kind):
                await self.asyncSetUp()
                def make_cache(proof):
                    cache = a.SameQueryCache(self.reader, self.memory.s, proof, {})
                    if kind == 'role': cache.roles['UNVERIFIED'] = {}
                    if kind == 'query': cache.proof = dict(proof)
                    if kind == 'sampler': cache.sampler = object()
                    at = self.attack_action + 0x80
                    raw = struct.pack('<QQi', self.realm.profile_uid, self.mover.state.uid, 7)
                    cache.capture('MOVE', at, 20, False, raw)
                    if kind == 'cross_role': cache.roles['WORLD'][(at, 20, False)] = bytes(20)
                    if kind == 'conflict':
                        cache.capture('MOVE', at, 20, False, bytes(20))
                    cache.finish_move(dict(status='OBSERVED', source_contract_valid=True, stable_double_read=True))
                    if kind == 'stale':
                        self.memory.put(at, '<QQi', self.realm.profile_uid, self.mover.state.uid, 8)
                    return cache
                await self.prepare()
                row = self.collect(cache=make_cache)
                self.assertEqual(row['status'], 'UNKNOWN', row)
                self.assertIsNone(row['attacker'])

    async def test_original_16160_pre_hook_completes_source_readback_inside_attack_only_24k(self):
        from tools.local_original_session.manual_move_commands_tests import ManualAttackTests
        self.service = self.realm.service(self.writer)
        ManualAttackTests.tiles(self)
        full_retained_reader(self)
        _, prehook = self.reader.sample(include_input_state=False)
        self.assertEqual(prehook, 4199)
        original = self.reader.watch
        # Preserve the existing costly-shape test's independent padding. It is
        # never cache-shareable typed data, and no read/check is removed.
        class PaddedWatch:
            @staticmethod
            def sample(native, sampler):
                row = original.sample(native, sampler)
                for size in (4096, 1904):
                    sampler.read(self.memory.base + 0x10000, size, image=True)
                if extra_scene[0]:
                    sampler.read(self.memory.base + 0x30000, extra_scene[0], image=True)
                return row
        self.reader.watch = PaddedWatch
        from types import SimpleNamespace
        original_world = self.reader.world
        extra_scene = [0]
        def padded_world(native, sampler):
            row = original_world.inspect_attached(native, sampler)
            for size in (4096, 1865):
                sampler.read(self.memory.base + 0x20000, size, image=True)
            return row
        self.reader.world = SimpleNamespace(empty_result=original_world.empty_result, inspect_attached=padded_world)
        await self.prepare()
        row, count = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        attack_row = row['attack_action']
        self.assertEqual(attack_row['status'], 'OBSERVED', attack_row)
        self.assertTrue(attack_row['stable_double_read'] and attack_row['source_contract_valid'])
        self.assertEqual(row['move_state']['status'], 'OBSERVED', row['move_state'])
        self.assertEqual(count - attack_row['typed_bytes_requested'], 16160)
        self.assertLessEqual(count, a.BYTE_LIMIT)
        self.assertEqual(self.reader.sample_byte_limit, 16384)
        self.assertLessEqual(attack_row['typed_bytes_requested'], 8192)
        self.assertGreater(count, 16384)
        type(self).metrics['large_shape'] = {key: attack_row[key] for key in (
            'status','reason','combined_typed_bytes_requested','typed_bytes_requested',
            'refused_read_bytes','shortfall_at_refused_read')}
        # The larger aggregate cannot rescue a MoveState that did not finish
        # inside its unchanged 16-KiB preceding aggregate.
        extra_scene[0] = 512
        await self.prepare()
        failed, used = self.reader.sample(include_input_state=False, attack_action_observer=self.leaf)
        self.assertEqual(failed['move_state']['status'], 'UNKNOWN', failed['move_state'])
        self.assertIn(failed['move_state']['reason'], ('MOVE_COMBINED_BYTE_BOUND', 'RETAINED_SAMPLE_BYTE_BUDGET'))
        self.assertEqual(failed['attack_action']['reason'], 'ATTACK_OBSERVE_MOVE_PROOF_REQUIRED')
        self.assertEqual(failed['attack_action']['typed_bytes_requested'], 0)
        self.assertLessEqual(used, 16384)
        type(self).metrics['move_16k_refusal'] = dict(combined=used, reason=failed['move_state']['reason'],
            attack_reason=failed['attack_action']['reason'], attack_bytes=failed['attack_action']['typed_bytes_requested'])

    async def test_shared_total_ceiling_reports_exact_first_gap(self):
        await self.prepare()
        row = self.collect(previous_total=a.BYTE_LIMIT - 884)
        self.assertEqual(row['status'], 'UNKNOWN', row)
        self.assertEqual(row['reason'], 'ATTACK_OBSERVE_COMBINED_BYTE_BOUND')
        self.assertGreater(row['refused_read_bytes'], 0)
        self.assertEqual(row['shortfall_at_refused_read'],
            row['combined_typed_bytes_requested'] + row['refused_read_bytes'] - a.BYTE_LIMIT)
        type(self).metrics['budget_refusal'] = {k: row[k] for k in (
            'reason', 'combined_typed_bytes_requested', 'refused_read_bytes', 'shortfall_at_refused_read')}


if __name__ == '__main__':
    unittest.main()
