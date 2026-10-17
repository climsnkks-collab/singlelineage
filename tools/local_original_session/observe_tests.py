"""Retained scene/world integration fixtures; no attach, native or game execution."""
import json
import math
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.local_original_session import observe as obs
from tools.local_original_session import input_state
from tools.local_original_session import move_state
from tools.local_native_world_read_dormant import inspect_world as world
from tools.online_intro_capture_20261006.sampler import Sampler
from tools.local_native_scene_current import watch as frozen_watch


class MoveStateTests(unittest.TestCase):
    def fixture(self):
        probe = move_state.MoveState()
        base, state, actor_sub, character, actor = 0x140000000, 0x200000, 0x210000, 0x220000, 0x230000
        controller, nav, transform, action, command, moving = [0x240000 + i * 0x10000 for i in range(6)]
        cells, reads = {}, []
        def put(at, raw):
            cells.update((at + i, byte) for i, byte in enumerate(raw))
        def q(at, value):
            put(at, struct.pack('<Q', value))
        owner_index = [0]
        def pair(obj):
            control = 0x600000 + owner_index[0] * 0x100
            owner_index[0] += 1
            put(control + 8, struct.pack('<i', 1))
            return struct.pack('<QQ', obj, control)
        for row in probe.tables.values():
            put(base + row['rva'], struct.pack('<' + 'Q' * len(row['targets']), *(base + v for v in row['targets'])))
        actors, components = 0x400000, 0x410000
        for obj, role in ((actor_sub, 'ActorSubsystem'), (character, 'CharacterDataSubsystem'), (actor, 'MyPlayer'),
                          (controller, 'ActorControllerComponent'), (nav, 'NavigationComponent'),
                          (transform, 'TransformComponent'), (action, 'ActionComponent'), (command, 'MoveCommand')):
            q(obj, base + probe.tables[role]['rva'])
        put(actor_sub + 0x10, b'\1'); put(character + 0x10, b'\1')
        put(actor_sub + 0x8a8, struct.pack('<QQ', actors, actors + 16)); put(actors, pair(actor))
        put(actor + 0x20, struct.pack('<QQ', components, components + 64))
        for i, obj in enumerate((controller, nav, transform, action)):
            put(components + i * 16, pair(obj)); q(obj + 8, actor); put(obj + 0x30, b'\1')
        uid = 31337
        q(actor + 0x18, uid); q(character + 0x6d8, uid); put(character + 0x558, b'\0')
        put(controller + 0x58, struct.pack('<Qi', command, 3))
        put(command + 8, struct.pack('<i', 0)); q(command + 0x10, uid)
        coordinate = lambda x, y: struct.pack('<iiii', 321, 322, x, y) + bytes(24)
        put(command + 0x18, coordinate(4001, 5001))
        put(nav + 0x1c0, coordinate(4001, 5001) + struct.pack('<iBB2xiii', 2, 1, 0, 0, 0, 0))
        put(transform + 0x38, coordinate(4000, 5001) + coordinate(4001, 5001))
        put(action + 0x44, bytes([1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1]))
        put(action + 0xd0, struct.pack('<f', 0.25)); q(action + 0xc0, moving)
        q(moving, base + 0x1180ca8); q(base + 0x1180ca8 + 8, base + 0x94570); q(moving + 8, action)
        put(moving + 0x18, struct.pack('<i4xIB', 2, 17, 0))
        put(moving + 0x80, struct.pack('<I', 1) + coordinate(4000, 5001) + coordinate(4001, 5001))
        queue_map, queue_block = 0x430000, 0x440000
        put(action + 0xa0, struct.pack('<QQQQ', queue_map, 8, 0, 1))
        q(queue_map, queue_block); q(queue_block, moving)
        raw = pair(0x450000) + bytes(16) + struct.pack('<I', 5); put(state + 0x360, raw)
        route = (0x460000, True, 7, 0x470000, 0, 0,
                 ((pair(actor_sub), base + probe.tables['ActorSubsystem']['rva']),
                  (pair(character), base + probe.tables['CharacterDataSubsystem']['rva'])), {'GameState': [state]})
        def read(at, size, image):
            reads.append((at, size, image))
            return bytes(cells.get(at + i, 0) for i in range(size))
        contract = dict(image_size=65630208, bounds=dict(typed_byte_limit=8192, total_typed_byte_limit=4194304), checks=[])
        backend = SimpleNamespace(read=read)
        sampler = Sampler(backend, contract, dict(base=base, size=65630208)); sampler.bytes=0; sampler.read_limit=8192
        sampler.route = Mock(return_value=route)
        reader = SimpleNamespace(sampler=sampler, backend=backend, contract=contract,
                                 sample_byte_limit=16384, validate=Mock())
        scene = dict(status='OBSERVED', current='Land', pending='none', root_ready=True, root_phase=7)
        world_row = dict(status='OBSERVED', stable_double_read=True, my_player_uid=uid)
        proof = dict(route=route, state=state, raw=raw, scene=dict(current=dict(kind='Land'), pending=dict(kind='none')))
        return SimpleNamespace(probe=probe, reader=reader, scene=scene, world=world_row, proof=proof,
            put=put, q=q, cells=cells, reads=reads, controller=controller, nav=nav, action=action,
            actor=actor, command=command, uid=uid)

    def test_typed_fields_command_queue_and_owner_are_read_without_call_claim(self):
        f = self.fixture(); result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertEqual(result['actor_uid'], 31337)
        self.assertEqual(result['controller']['goal_grid'], [4001, 5001])
        self.assertEqual(result['navigation']['target_grid'], [4001, 5001])
        self.assertTrue(result['navigation']['active'])
        self.assertEqual(result['transform']['current_grid'], [4000, 5001])
        self.assertEqual(result['transform']['predicted_grid'], [4001, 5001])
        self.assertEqual(result['action']['current']['kind'], 'MovingAction')
        self.assertEqual(result['action']['queue_count'], 1)
        self.assertEqual(result['action']['queue_head']['token_u32'], 17)
        self.assertTrue(result['character_data']['own_uid_matches_actor'])
        self.assertTrue(result['stable_double_read'])
        self.assertFalse(result['snapshot_atomic'])
        self.assertTrue(all(size <= 4096 for _, size, _ in f.reads))
        self.assertNotIn('update_called', result)
        self.assertLess(result['typed_bytes_requested'], 8192)
        self.assertEqual((f.reader.sampler.bytes, f.reader.sampler.read_limit), (0, 8192))

    def test_type_owner_and_uid_mismatches_are_unknown_without_losing_other_fields(self):
        for mismatch in ('borrowed', 'type', 'command_uid', 'world_uid'):
            with self.subTest(mismatch=mismatch):
                f = self.fixture()
                if mismatch == 'borrowed': f.q(f.controller + 8, f.actor + 8)
                if mismatch == 'type': f.q(f.controller, 0x140000008)
                if mismatch == 'command_uid': f.q(f.command + 0x10, f.uid + 1)
                if mismatch == 'world_uid': f.world['my_player_uid'] += 1
                result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
                if mismatch == 'world_uid':
                    self.assertEqual(result['status'], 'UNKNOWN')
                else:
                    self.assertEqual(result['status'], 'OBSERVED_PARTIAL')
                    self.assertEqual(result['controller']['status'], 'UNKNOWN')
                    self.assertEqual(result['navigation']['status'], 'OBSERVED')

    def test_changed_typed_bytes_scene_or_retained_owner_refuses_freshness(self):
        for mismatch in ('typed', 'scene', 'owner'):
            with self.subTest(mismatch=mismatch):
                f = self.fixture()
                if mismatch == 'owner':
                    f.reader.validate.side_effect = [None, ValueError('RETAINED_PRIMARY_NOT_LIVE')]
                else:
                    original = f.reader.backend.read; count = [0]
                    target = f.nav + 0x1c0 if mismatch == 'typed' else f.proof['state'] + 0x360
                    def changed(at, size, image):
                        value = original(at, size, image)
                        if at == target:
                            count[0] += 1
                            if mismatch == 'scene' or count[0] == 2: return bytes([value[0] ^ 1]) + value[1:]
                        return value
                    f.reader.backend.read = changed
                result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertFalse(result['stable_double_read'])

    def test_same_tick_world_cache_and_combined_budget_are_bounded(self):
        f = self.fixture(); cache = {}
        first = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        for at, size, image in f.reads:
            cache[(at, size, image is not None)] = bytes(f.cells.get(at + i, 0) for i in range(size))
        f.reader.sampler.total, f.reader.sampler.bytes = 10270, 6073
        result = f.probe.sample(f.reader, f.scene, f.world, f.proof, cache)
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertLessEqual(f.reader.sampler.total, 16384)
        self.assertEqual(f.reader.sampler.bytes, 6073)
        self.assertLess(result['typed_bytes_requested'], first['typed_bytes_requested'])
        f.reader.sampler.total = 16383
        refused = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        self.assertEqual(refused['status'], 'UNKNOWN')
        self.assertLessEqual(f.reader.sampler.total, 16384)

    def test_unknown_current_action_or_queue_head_keeps_component_flags(self):
        f = self.fixture(); f.q(f.action + 0xc0, 0x480000); f.q(0x480000, 0x140000008)
        f.q(f.action + 0xa8, 3)
        result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        self.assertEqual(result['action']['status'], 'OBSERVED')
        self.assertEqual(result['action']['current']['status'], 'UNKNOWN')
        self.assertEqual(result['action']['queue_status'], 'UNKNOWN')
        self.assertEqual(result['action']['flag44_u8'], 1)
        self.assertNotIn('480000', json.dumps(result))

    def test_unknown_action_only_exposes_bounded_image_relative_table_hint(self):
        for vptr, expected in ((0x140005008, 0x5008), (0x80000000, None)):
            with self.subTest(vptr_inside_image=expected is not None):
                f = self.fixture()
                f.q(f.action + 0xc0, 0x480000); f.q(0x480000, vptr)
                f.q(0x440000, 0x480000)  # Same unknown type at the queue head.
                result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
                for field in ('current', 'queue_head'):
                    action = result['action'][field]
                    self.assertEqual(action['status'], 'UNKNOWN')
                    self.assertEqual(action['kind'], 'unknown')
                    self.assertEqual(action['type_table_rva'], expected)
                self.assertFalse(any(0x480008 <= at < 0x480100 for at, _, _ in f.reads))
                self.assertNotIn('vptr', json.dumps(result))

    def set_source_action(self, f, obj, kind, *, finished=False):
        for rva, row in f.probe.action_tables.items():
            if row['kind'] == kind:
                f.q(obj, 0x140000000 + rva)
                f.put(0x140000000 + rva, struct.pack('<8Q', *(0x140000000 + v for v in row['targets'])))
                f.put(obj + 0x24, bytes([int(finished)]))
                return rva
        raise AssertionError('missing fixture source type')

    def test_default_breath_and_null_current_have_source_eval_without_action_owner_reads(self):
        for kind, expected in (('DefaultAction', True), ('BreathAction', False), ('none', False)):
            with self.subTest(kind=kind):
                f = self.fixture(); obj = 0x480000
                if kind == 'none':
                    f.q(f.action + 0xc0, 0)
                else:
                    self.set_source_action(f, obj, kind)
                    f.q(f.action + 0xc0, obj)
                f.q(f.action + 0xa8, 3)  # Invalid head map does not affect short-circuit.
                result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
                action = result['action']
                self.assertEqual(action['current']['kind'], kind)
                self.assertEqual(action['busy_source_eval']['status'], 'EVALUATED')
                self.assertIs(action['busy_source_eval']['value'], expected)
                self.assertIs(action['busy_source_eval']['actual_call_observed'], False)
                self.assertFalse(any(at == obj + 8 for at, _, _ in f.reads))
                if kind == 'BreathAction':
                    self.assertIsNone(action['current']['finished'])
                    self.assertFalse(any(at == obj + 0x24 for at, _, _ in f.reads))

    def test_finished_default_evaluation_consumes_flags_count_and_qualified_head_conditionally(self):
        cases = ((1, 1, 'unknown', False), (0, 0, 'unknown', False), (0, 2, 'unknown', True),
                 (0, 1, 'BreathAction', False), (0, 1, 'DefaultAction', True), (0, 1, 'unknown', None))
        for flag4f, count, head_kind, expected in cases:
            with self.subTest(flag4f=flag4f, count=count, head_kind=head_kind):
                f = self.fixture(); current, head = 0x480000, 0x490000
                self.set_source_action(f, current, 'DefaultAction', finished=True)
                f.q(f.action + 0xc0, current); f.put(f.action + 0x4f, bytes([flag4f]))
                f.q(f.action + 0xb8, count); f.q(0x440000, head)
                if head_kind == 'unknown': f.q(head, 0x140005008)
                else: self.set_source_action(f, head, head_kind)
                result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
                evaluation = result['action']['busy_source_eval']
                self.assertIs(evaluation['value'], expected)
                self.assertEqual(evaluation['status'], 'UNKNOWN' if expected is None else 'EVALUATED')
                self.assertFalse(evaluation['actual_call_observed'])
                self.assertFalse(any(at in (current + 8, head + 8, head + 0x24) for at, _, _ in f.reads))

    def test_source_table_tail_and_finished_reread_change_refuse_qualification(self):
        for mismatch in ('table_tail', 'finished_changed'):
            with self.subTest(mismatch=mismatch):
                f = self.fixture(); obj = 0x480000
                rva = self.set_source_action(f, obj, 'DefaultAction')
                f.q(f.action + 0xc0, obj)
                if mismatch == 'table_tail':
                    f.q(0x140000000 + rva + 56, 0x140000008)
                else:
                    original = f.reader.backend.read; calls = [0]
                    def changed(at, size, image):
                        raw = original(at, size, image)
                        if at == obj + 0x24:
                            calls[0] += 1
                            if calls[0] == 2: return b'\1'
                        return raw
                    f.reader.backend.read = changed
                result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
                if mismatch == 'table_tail':
                    self.assertEqual(result['action']['status'], 'UNKNOWN')
                    self.assertEqual(result['action']['reason'], 'MOVE_ACTION_TYPE_TABLE_CHANGED')
                    self.assertEqual(result['action']['busy_source_eval']['status'], 'UNKNOWN')
                    self.assertIsNone(result['action']['busy_source_eval']['value'])
                else:
                    self.assertEqual(result['status'], 'UNKNOWN')
                    self.assertEqual(result['reason'], 'MOVE_TYPED_READ_CHANGED')

    def test_breath_static_eval_does_not_require_timer_or_unknown_current_guess(self):
        f = self.fixture(); obj = 0x480000
        self.set_source_action(f, obj, 'BreathAction'); f.q(f.action + 0xc0, obj)
        f.put(f.action + 0xd0, struct.pack('<f', float('nan')))
        result = f.probe.sample(f.reader, f.scene, f.world, f.proof)
        self.assertIs(result['action']['busy_source_eval']['value'], False)
        self.assertEqual(result['action']['current']['kind'], 'BreathAction')
        self.assertIsNone(result['action']['timer_f32'])
        unknown = move_state.busy_source_eval(dict(status='UNKNOWN', present=True, kind='unknown'), 1, 0)
        self.assertIsNone(unknown['value'])
        self.assertFalse(unknown['actual_call_observed'])


class QuitSceneTests(unittest.TestCase):
    def reader(self, *, pending=False, mismatch=None):
        base, state, scene, control = 0x140000000, 0x200000, 0x210000, 0x220000
        contract = obs.quit_scene_contract(dict(scenes=[], checks=[], bounds=dict(
            typed_byte_limit=8192, total_typed_byte_limit=4194304)))
        cells, reads = {}, []
        def put(at, raw):
            cells.update((at + index, value) for index, value in enumerate(raw))
        pair = struct.pack('<QQ', scene, control)
        put(state + 0x360, (bytes(16) + pair + struct.pack('<I', 0)) if pending
            else (pair + bytes(16) + struct.pack('<I', 6)))
        put(control + 8, struct.pack('<i', 0 if mismatch == 'strong_owner' else 1))
        row = contract['scenes'][0]
        put(base + row['rva'], struct.pack('<' + 'Q' * len(row['targets']),
            *(base + value for value in row['targets'])))
        if mismatch == 'table':
            put(base + row['rva'] + 16, struct.pack('<Q', base + 1))
        put(scene, struct.pack('<QQI', base + row['rva'] + (8 if mismatch == 'vptr' else 0),
                              0, 5 if mismatch == 'scene_enum' else 6))
        if mismatch == 'current_enum':
            put(state + 0x380, struct.pack('<I', 5))
        counts = dict(pair=0, owner=0, validate=0)
        def read(at, size, image):
            reads.append(size)
            raw = bytes(cells.get(at + index, 0) for index in range(size))
            if at == state + 0x360 and size == 36:
                counts['pair'] += 1
                if mismatch == 'pair_changed' and counts['pair'] == 2:
                    return bytes([raw[0] ^ 8]) + raw[1:]
            if at == scene and size == 20:
                counts['owner'] += 1
                if mismatch == 'owner_changed' and counts['owner'] == 2:
                    return raw[:-1] + bytes([raw[-1] ^ 1])
            return raw
        def validate():
            counts['validate'] += 1
            if mismatch == 'owner_lost' and counts['validate'] == 2:
                raise ValueError('RETAINED_PRIMARY_NOT_LIVE')
        backend = SimpleNamespace(read=read, validate=validate)
        reader = obs.RetainedSceneReader.__new__(obs.RetainedSceneReader)
        reader.contract, reader.backend = contract, backend
        reader.validate = Mock()
        reader.sampler = Sampler(backend, contract, dict(base=base))
        reader.sampler.route = lambda: (0x230000, True, 1, 0x240000, 0, 0, (), {'GameState': [state]})
        reader.watch = frozen_watch
        reader.world = SimpleNamespace(empty_result=world.empty_result, inspect_attached=Mock())
        return reader, reads

    def test_current_and_pending_quit_reuse_frozen_typed_sampler(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                reader, reads = self.reader(pending=pending)
                row, count = reader.sample()
                self.assertEqual(row['status'], 'OBSERVED')
                self.assertEqual((row['current'], row['pending']), ('none', 'Quit') if pending else ('Quit', 'none'))
                self.assertTrue(row['root_ready'])
                self.assertFalse(row['visible_ui_proven'])
                self.assertEqual(count, sum(reads))
                self.assertLessEqual(count, obs.RETAINED_SAMPLE_LIMIT)
                self.assertTrue(all(0 < size <= 4096 for size in reads))
                reader.world.inspect_attached.assert_not_called()
                self.assertNotIn('210000', json.dumps(row))

    def test_torn_or_wrong_type_enum_owner_and_table_are_unknown(self):
        for mismatch, expected in (
            ('strong_owner', 'shared_owner_not_positive'), ('vptr', 'scene_type_enum_disagree'),
            ('scene_enum', 'scene_type_enum_disagree'), ('current_enum', 'current_enum_disagree'),
            ('table', 'public_vtable_changed'), ('owner_changed', 'scene_owner_changed'),
            ('pair_changed', 'scene_pair_transition')):
            with self.subTest(mismatch=mismatch):
                reader, _ = self.reader(mismatch=mismatch)
                row, _ = reader.sample()
                self.assertEqual(row['status'], 'UNKNOWN')
                self.assertEqual(row['reason'], expected)
                self.assertEqual(row['current'], 'unknown')

    def test_retained_owner_loss_never_reports_quit_observed(self):
        reader, _ = self.reader(mismatch='owner_lost')
        row, _ = reader.sample()
        self.assertEqual(row['status'], 'UNKNOWN')
        self.assertEqual(row['current'], 'unknown')

    def test_local_extension_is_idempotent_and_frozen_contract_is_unchanged(self):
        original = dict(scenes=[])
        extended = obs.quit_scene_contract(original)
        self.assertEqual(original, dict(scenes=[]))
        self.assertEqual(extended['scenes'][0]['state_id'], 6)
        self.assertIs(obs.quit_scene_contract(extended), extended)

    def test_changed_saved_evidence_is_refused(self):
        digest = obs.digest
        with patch.object(obs, 'digest', side_effect=lambda path:
                '0' * 64 if Path(path).name == 'quit_type.json' else digest(path)):
            with self.assertRaisesRegex(ValueError, '^QUIT_SOURCE_CHANGED$'):
                obs.quit_scene_contract(dict(scenes=[]))


class InputCallbackTests(unittest.TestCase):
    def fixture(self):
        probe = input_state.InputState()
        base, window, host, state = 0x140000000, 0x200000, 0x210000, 0x220000
        cells = {}
        def put(at, raw):
            cells.update((at + n, value) for n, value in enumerate(raw))
        q = lambda at, value: put(at, struct.pack('<Q', value))
        q(base + 0x17f0d18, window)
        q(window, base + 0x123a7d8)
        q(base + 0x123a7d8 + 0x50, base + 0xb88fd0)
        q(base + 0x123a7d8 + 0xd8, base + 0xb86fd0)
        q(window + 0x80, host)
        q(host + 0x320, base + 0xb8b1f0)
        q(host + 0x328, base + 0xb8ac40)
        q(host + 0x368, 99)
        put(window + 0xb0, struct.pack('<ff', 100.0, 200.0))
        put(window + 0x20, struct.pack('<ff', 10.0, 20.0))
        put(window + 0x50, struct.pack('<ff', 1.0, 2.0))
        put(window + 0x62, b'\1')
        put(window + 0x64, struct.pack('<i', 1))
        put(host + 0x8c, struct.pack('<i', 0x34001))
        put(host + 0x208, struct.pack('<i', 0))
        scene_raw = bytes(36)
        put(state + 0x360, scene_raw)
        sampler = SimpleNamespace(total=0, bytes=0, g=dict(base=base, size=65630208))
        sampler.combined_limit = 8192
        def read(at, size, image=False):
            obs.need(sampler.total + size <= sampler.combined_limit, 'RETAINED_SAMPLE_BYTE_BUDGET')
            obs.need(sampler.bytes + size <= 8192, 'sample_byte_budget')
            sampler.total += size
            sampler.bytes += size
            return bytes(cells[at + n] for n in range(size))
        sampler.read = read
        route = (123, True, 4)
        sampler.route = lambda: route
        contract = dict(image_size=65630208)
        backend = SimpleNamespace(handle=77)
        sampler.b, sampler.c = backend, contract
        member = object()
        owner = SimpleNamespace(child=member, native=SimpleNamespace(owned_hwnd=Mock(return_value=True)))
        reader = SimpleNamespace(sampler=sampler, backend=backend, contract=contract,
                                 validate=Mock(), owner=owner, member=member)
        row = dict(status='OBSERVED', current='Login', pending='none', root_ready=True)
        proof = dict(route=route, state=state, scene={'current': {'kind': 'Login'},
                     'pending': {'kind': 'none'}}, raw=scene_raw)
        return probe, reader, row, proof, put, window, host

    def test_actual_fields_change_without_transform_or_raw_pointer_output(self):
        probe, reader, row, proof, put, window, _ = self.fixture()
        first = probe.sample(reader, row, proof)
        self.assertEqual(first['cursor_xy'], [100.0, 200.0])
        self.assertEqual(first['origin_xy'], [10.0, 20.0])
        self.assertEqual(first['scale_xy'], [1.0, 2.0])
        self.assertTrue(first['source_contract_valid'])
        self.assertTrue(first['stable_double_read'])
        put(window + 0xb0, struct.pack('<ff', 1759.0, 1224.0))
        second = probe.sample(reader, row, proof)
        self.assertEqual(second['cursor_xy'], [1759.0, 1224.0])
        self.assertEqual(second['window_mode64_i32'], 1)
        self.assertNotIn('0x', json.dumps(input_state.public(second)))
        self.assertNotIn('hwnd', json.dumps(input_state.public(second)))
        self.assertNotIn('window', {k for k in second if k in ('window', 'host', 'pointer')})
        self.assertLess(reader.sampler.total, 8192)
        self.assertEqual(reader.validate.call_count, 4)

    def test_nonfinite_slot_or_owner_or_typed_change_is_unknown(self):
        for boundary in ('nonfinite', 'slot', 'owner', 'typed_change'):
            probe, reader, row, proof, put, window, host = self.fixture()
            if boundary == 'nonfinite':
                put(window + 0xb0, struct.pack('<ff', math.nan, 2.0))
            elif boundary == 'slot':
                put(host + 0x328, struct.pack('<Q', reader.sampler.g['base'] + 1))
            elif boundary == 'owner':
                reader.owner.native.owned_hwnd.side_effect = [True, False]
            else:
                original = reader.sampler.read
                visits = [0]
                def changed(at, size, image=False):
                    if at == window + 0xb0:
                        visits[0] += 1
                        if visits[0] == 2:
                            put(at, struct.pack('<ff', 999.0, 2.0))
                    return original(at, size, image)
                reader.sampler.read = changed
            result = probe.sample(reader, row, proof)
            self.assertEqual(result['status'], 'UNKNOWN', boundary)
            self.assertFalse(result['source_contract_valid'])
            self.assertIsNone(result['cursor_xy'])

    def test_remaining_combined_budget_refuses_without_promotion(self):
        probe, reader, row, proof, _, _, _ = self.fixture()
        reader.sampler.total = 8190
        result = probe.sample(reader, row, proof)
        self.assertEqual(result['reason'], 'INPUT_COMBINED_BYTE_BOUND')
        self.assertEqual(reader.sampler.total, 8190)
        self.assertEqual(row['status'], 'OBSERVED')

    def test_input_leaf_does_not_add_world_bytes_to_frozen_leaf_allowance(self):
        probe, reader, row, proof, _, _, _ = self.fixture()
        reader.sample_byte_limit = reader.sampler.combined_limit = 16384
        reader.sampler.total, reader.sampler.bytes = 10270, 6073
        result = probe.sample(reader, row, proof)
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertGreater(reader.sampler.total, 10270)
        self.assertEqual(reader.sampler.bytes, 6073)
        self.assertLessEqual(reader.sampler.total, 16384)


class WindowHealthTests(unittest.TestCase):
    class Function:
        def __init__(self, callback):
            self.callback = callback
        def __call__(self, *args):
            return self.callback(*args)

    def fixture(self):
        state = dict(window_class='GLFW30', dpi=168, hung=0)
        def get_class(hwnd, buffer, capacity):
            buffer.value = state['window_class']
            return len(state['window_class'])
        user = SimpleNamespace(GetClassNameW=self.Function(get_class),
            GetDpiForWindow=self.Function(lambda hwnd: state['dpi']),
            IsHungAppWindow=self.Function(lambda hwnd: state['hung']))
        child = SimpleNamespace(pid=11, identity=dict(birth='22', image='C:/pinned/LC.guard.exe'))
        owner = SimpleNamespace(child=child, validate=Mock(return_value=True),
            native=SimpleNamespace(u=user, owned_hwnd=Mock(return_value=True)))
        row = dict(hwnd=333, **{'class': 'GLFW30'}, visible=True, title='PRIVATE_CAPTION',
            geometry=dict(left=0, top=0, width=2194, height=1234),
            children=[dict(**{'class': 'Edit'}, text='PRIVATE_TEXT')],
            owned_member=dict(pid=11, birth='22', image_basename='LC.guard.exe'))
        return owner, row, state

    def test_primary_readonly_health_and_foreign_member_is_unknown_redacted(self):
        owner, row, state = self.fixture()
        public = obs.public_windows([row], owner)[0]
        self.assertEqual(public['window_health'], dict(status='OBSERVED', is_hung=False,
                                                      dpi=168, render_verified=False))
        self.assertEqual(public['geometry']['width'], 2194)
        encoded = json.dumps(public)
        self.assertNotIn('PRIVATE_', encoded)
        self.assertNotIn('333', encoded)
        self.assertNotIn('owned_member', encoded)
        owner.validate.reset_mock()
        row['owned_member']['pid'] = 99
        foreign = obs.public_windows([row], owner)[0]['window_health']
        self.assertEqual(foreign['status'], 'UNKNOWN')
        self.assertIsNone(foreign['is_hung'])
        owner.validate.assert_not_called()

    def test_owner_or_class_change_clears_entire_health_observation(self):
        owner, row, state = self.fixture()
        owner.validate.side_effect = [True, False]
        health = obs.window_health(owner, row)
        self.assertEqual(health['reason'], 'CURRENT_WINDOW_OWNER_LOST')
        self.assertIsNone(health['dpi'])
        owner, row, state = self.fixture()
        def changed(hwnd):
            state['window_class'] = 'Button'
            return 1
        owner.native.u.IsHungAppWindow.callback = changed
        health = obs.window_health(owner, row)
        self.assertEqual(health['reason'], 'CURRENT_WINDOW_METADATA_CHANGED')
        self.assertIsNone(health['is_hung'])

    def test_hung_boolean_and_dpi_bounds_or_change_never_prove_rendering(self):
        for hung in (0, 1):
            owner, row, state = self.fixture()
            state['hung'] = hung
            health = obs.window_health(owner, row)
            self.assertEqual(health['is_hung'], bool(hung))
            self.assertFalse(health['render_verified'])
        for changes in (dict(dpi=0), dict(dpi=1537), dict(dpi=True), dict(hung=2)):
            owner, row, state = self.fixture()
            state.update(changes)
            health = obs.window_health(owner, row)
            self.assertEqual(health['status'], 'UNKNOWN')
            self.assertIsNone(health['is_hung'])
            self.assertIsNone(health['dpi'])
        owner, row, state = self.fixture()
        values = iter((168, 192))
        owner.native.u.GetDpiForWindow.callback = lambda hwnd: next(values)
        self.assertEqual(obs.window_health(owner, row)['reason'], 'CURRENT_WINDOW_METADATA_CHANGED')


class RetainedWorldTests(unittest.TestCase):
    def test_default_and_explicit_no_attack_keep_identical_16k_read_trace(self):
        reader, fixture = self.movement_reader()
        implicit, implicit_count = reader.sample(include_input_state=False)
        trace = list(fixture.reads)
        fixture.reads.clear()
        explicit, explicit_count = reader.sample(include_input_state=False, attack_action_observer=None)
        self.assertEqual(implicit, explicit)
        self.assertEqual(trace, fixture.reads)
        self.assertEqual((implicit_count, explicit_count, reader.sample_byte_limit), (16160, 16160, 16384))

    def test_attack_leaf_instance_or_class_override_refused_before_any_read(self):
        from tools.local_original_session import attack_action_observe as action_observe
        from types import MethodType
        for field in ('prepare', 'collect'):
            with self.subTest(field=field):
                reader, fixture = self.movement_reader()
                leaf = action_observe.AttackActionObserver.__new__(action_observe.AttackActionObserver)
                leaf.reader = reader
                setattr(leaf, field, MethodType(lambda self, *a, **k: {}, leaf))
                with self.assertRaisesRegex(ValueError, 'RETAINED_ATTACK_SAME_OBSERVER_REQUIRED'):
                    reader.sample(include_input_state=False, attack_action_observer=leaf)
                self.assertEqual(fixture.reads, [])
        reader, fixture = self.movement_reader()
        leaf = action_observe.AttackActionObserver.__new__(action_observe.AttackActionObserver)
        leaf.reader = reader
        with patch.object(action_observe.AttackActionObserver, 'collect', lambda *a: {}):
            with self.assertRaisesRegex(ValueError, 'RETAINED_ATTACK_SAME_OBSERVER_REQUIRED'):
                reader.sample(attack_action_observer=leaf)
        self.assertEqual(fixture.reads, [])

    def movement_reader(self):
        # Existing typed movement fixture, with the real input probe's verified
        # window/host fields at separate addresses. Scene/world consume a
        # bounded 14100 B, leaving movement's actual 2060 B within 16 KiB.
        f = MoveStateTests().fixture()
        reader = obs.RetainedSceneReader.__new__(obs.RetainedSceneReader)
        reader.backend, reader.contract, reader.sampler = f.reader.backend, f.reader.contract, f.reader.sampler
        reader.validate = f.reader.validate
        reader.sample_byte_limit = obs.RETAINED_SAMPLE_LIMIT
        window, host = 0x800000, 0x810000
        base = reader.sampler.g['base']
        for at, value in ((base + 0x17f0d18, window), (window, base + 0x123a7d8),
                          (base + 0x123a7d8 + 0x50, base + 0xb88fd0),
                          (base + 0x123a7d8 + 0xd8, base + 0xb86fd0),
                          (window + 0x80, host), (host + 0x320, base + 0xb8b1f0),
                          (host + 0x328, base + 0xb8ac40), (host + 0x368, 99)):
            f.q(at, value)
        for at, values in ((window + 0xb0, (100., 200.)), (window + 0x20, (10., 20.)),
                           (window + 0x50, (1., 2.))):
            f.put(at, struct.pack('<ff', *values))
        f.put(window + 0x62, b'\1')
        for at, value in ((window + 0x64, 1), (host + 0x8c, 0x34001), (host + 0x208, 0)):
            f.put(at, struct.pack('<i', value))
        reader.member = object()
        reader.owner = SimpleNamespace(internal=False, child=reader.member,
            native=SimpleNamespace(owned_hwnd=Mock(return_value=True)))
        reader.input_state, reader.move_state = input_state.InputState(), f.probe
        reader.sampler.scene = Mock(return_value=(f.proof['scene'], f.proof['raw']))
        def scene(native, sampler):
            sampler.bytes = 0
            sampler.read(0x10000, 4096)
            sampler.read(0x10000, 1904)
            sampler.route()
            sampler.scene(f.proof['state'])
            return dict(f.scene)
        def inspect(native, sampler):
            sampler.bytes = 0
            sampler.read(0x10000, 4096)
            sampler.read(0x10000, 4004)
            return dict(f.world)
        reader.watch = SimpleNamespace(sample=scene)
        reader.world = SimpleNamespace(empty_result=world.empty_result, inspect_attached=inspect)
        return reader, f

    def test_selective_input_skip_preserves_real_move_probe_within_same_16k(self):
        reader, f = self.movement_reader()
        original_read = reader.sampler.read
        full, full_bytes = reader.sample()
        self.assertEqual(full['world']['status'], 'OBSERVED')
        self.assertEqual(full['input_state']['status'], 'OBSERVED')
        self.assertEqual(full['move_state']['status'], 'UNKNOWN')
        self.assertEqual(full['move_state']['reason'], 'RETAINED_SAMPLE_BYTE_BUDGET')
        self.assertLessEqual(full_bytes, 16384)
        self.assertEqual(full_bytes, sum(size for _, size, _ in f.reads))
        f.reads.clear()
        selected, selected_bytes = reader.sample(include_input_state=False)
        self.assertEqual(selected['input_state']['reason'], 'MOVEMENT_INPUT_NOT_REQUIRED')
        self.assertEqual(selected['input_state']['status'], 'UNKNOWN')
        self.assertEqual(selected['input_state']['typed_bytes_requested'], 0)
        self.assertEqual(selected['world']['status'], 'OBSERVED')
        self.assertEqual(selected['move_state']['status'], 'OBSERVED')
        self.assertTrue(selected['move_state']['stable_double_read'])
        self.assertEqual(selected_bytes, 16160)
        self.assertLessEqual(selected_bytes, 16384)
        self.assertEqual(selected_bytes, sum(size for _, size, _ in f.reads))
        self.assertEqual(reader.sample_byte_limit, 16384)
        self.assertEqual(reader.contract['bounds']['typed_byte_limit'], 8192)
        self.assertTrue(all(size <= 4096 for _, size, _ in f.reads))
        self.assertEqual(reader.sampler.read, original_read)
        self.assertFalse(any(at == 0x800000 or at == 0x810000 for at, _, _ in f.reads))
        # Explicit True is the unchanged full/default order, including its
        # budget refusal; neither selection promotes UNKNOWN to idle/allowed.
        explicit, explicit_bytes = reader.sample(include_input_state=True)
        self.assertEqual(explicit['move_state']['reason'], full['move_state']['reason'])
        self.assertEqual(explicit_bytes, full_bytes)

    def test_input_selection_is_exact_bool_before_validation_or_read(self):
        reader, reads = self.reader()
        for value in (None, 0, 1, 'False', [], object()):
            with self.subTest(type=type(value).__name__), self.assertRaisesRegex(
                    ValueError, 'RETAINED_INPUT_SELECTION_BOOL_REQUIRED'):
                reader.sample(include_input_state=value)
        reader.validate.assert_not_called()
        self.assertEqual(reads, [])

    def reader(self, scene='Land', scene_bytes=128, leaf=None):
        reads = []
        contract = {'bounds': {'typed_byte_limit': 8192,
                              'total_typed_byte_limit': 4194304}, 'checks': []}
        backend = SimpleNamespace(contract=contract,
            read=lambda at, size, image: reads.append(size) or bytes(size))
        reader = obs.RetainedSceneReader.__new__(obs.RetainedSceneReader)
        reader.sample_byte_limit = 8192  # Legacy boundary fixtures also exercise a smaller aggregate.
        reader.backend, reader.contract = backend, contract
        reader.validate = Mock()
        backend.validate = reader.validate
        reader.sampler = Sampler(backend, contract, {'base': 0x140000000})
        def sample(native, sampler):
            self.assertIs(native, backend)
            sampler.bytes, sampler.read_limit = 0, 8192
            remaining = scene_bytes
            while remaining:
                size = min(4096, remaining)
                sampler.read(0x10000, size)
                remaining -= size
            return dict(status='OBSERVED', current=scene, pending='none')
        reader.watch = SimpleNamespace(sample=sample)
        reader.world = SimpleNamespace(empty_result=world.empty_result,
                                       inspect_attached=Mock(side_effect=leaf))
        return reader, reads

    def test_internal_move_leaf_reuses_world_cache_and_does_not_replace_scene_world(self):
        reader, _ = self.reader(leaf=lambda native, sampler: (sampler.read(0x10000, 32) and
            dict(status='OBSERVED', stable_double_read=True, my_player_uid=77)))
        reader.owner = SimpleNamespace(internal=True)
        reader.input_state = SimpleNamespace(sample=Mock(side_effect=AssertionError('manual input leaf')))
        def movement(current, scene, world_row, proof, cache):
            self.assertEqual(world_row['my_player_uid'], 77)
            self.assertEqual(cache[(0x10000, 32, False)], bytes(32))
            return move_state.empty('MOVE_COMBINED_BYTE_BOUND')
        reader.move_state = SimpleNamespace(sample=Mock(side_effect=movement))
        row, _ = reader.sample()
        self.assertEqual(row['current'], 'Land')
        self.assertEqual(row['world']['my_player_uid'], 77)
        self.assertEqual(row['move_state']['reason'], 'MOVE_COMBINED_BYTE_BOUND')
        self.assertEqual(row['input_state']['reason'], 'INTERNAL_COMMAND_INPUT_NOT_REQUIRED')
        reader.input_state.sample.assert_not_called()

    def test_finish_only_passes_exact_verified_normal_exit_report(self):
        monitor = obs.SessionMonitor.__new__(obs.SessionMonitor)
        monitor.last_row = dict(memory={'move_state': move_state.empty()}, broker={})
        monitor.publish = lambda row: row
        for verified, protocol, accepted in ((True, 'SOURCE_QUIT_DRAIN_EOF_EXIT0', True),
                                             (True, 'UNVERIFIED', False),
                                             (False, 'SOURCE_QUIT_DRAIN_EOF_EXIT0', False)):
            with self.subTest(verified=verified, protocol=protocol):
                result = monitor.finish(dict(normal_exit_verified=verified, game_logout_protocol=protocol))
                self.assertEqual(result['normal_exit_verified'], accepted)
                self.assertEqual(result['game_logout_protocol'], protocol if accepted else 'UNVERIFIED')

    def test_land_reuses_same_handle_and_sampler_and_whitelists_world(self):
        def inspect(native, sampler):
            self.assertIs(native, reader.backend)
            self.assertIs(sampler, reader.sampler)
            sampler.bytes, sampler.read_limit = 0, 20480
            sampler.read(0x10000, 100)
            return dict(status='OBSERVED', my_player_uid=12345, grid_words=[100, 200],
                        expected_uid_match=None, typed_bytes_requested=sampler.bytes,
                        raw_pointer='PRIVATE_ADDRESS', saved_body='PRIVATE_BODY')
        reader, reads = self.reader(leaf=inspect)
        original_read = reader.sampler.read
        scene, count = reader.sample()
        self.assertEqual(reader.sampler.read, original_read)
        self.assertEqual(count, 228)
        self.assertEqual(sum(reads), count)
        self.assertEqual(reader.validate.call_count, 2)
        reader.world.inspect_attached.assert_called_once_with(reader.backend, reader.sampler)
        self.assertEqual(scene['world']['grid_words'], [100, 200])
        self.assertIsNone(scene['world']['expected_uid_match'])
        self.assertNotIn('PRIVATE_', json.dumps(scene))

    def test_nonland_and_unknown_scene_do_not_inspect_world(self):
        for current, status in [('Login', 'OBSERVED'), ('Land', 'UNKNOWN')]:
            with self.subTest(current=current, status=status):
                reader, reads = self.reader(current)
                if status == 'UNKNOWN':
                    reader.watch.sample = lambda *_: dict(status=status, current=current)
                    reader.sampler.bytes = 0
                row, count = reader.sample()
                reader.world.inspect_attached.assert_not_called()
                self.assertEqual(row['world']['reason'], 'LAND_NOT_OBSERVED')
                self.assertEqual(count, sum(reads))

    def test_real_leaf_cannot_reset_combined_sample_budget(self):
        reader, reads = self.reader(scene_bytes=8190, leaf=world.inspect_attached)
        public, source = {}, dict(source_checks=[dict(rva=1, length=3, sha256='unused')],
                                 inherited_source_checks=[])
        reader.sampler.g['size'] = 100
        with patch.object(world, 'contracts', return_value=(public, source)):
            row, count = reader.sample()
        self.assertEqual(row['world']['status'], 'UNKNOWN')
        self.assertEqual(row['world']['reason'], 'RETAINED_SAMPLE_BYTE_BUDGET')
        self.assertEqual(row['world']['typed_bytes_requested'], 0)
        self.assertEqual(count, 8190)
        self.assertEqual(sum(reads), count)
        # Restoration and the next sample have independent bounded counters.
        reader.watch.sample = lambda *_: dict(status='OBSERVED', current='Login')
        reader.sampler.bytes = 0
        _, count = reader.sample()
        self.assertEqual(count, 0)

    def test_identity_loss_after_leaf_prevents_publishing_observed_world(self):
        reader, _ = self.reader(leaf=lambda *_: dict(status='OBSERVED', my_player_uid=12345))
        reader.validate.side_effect = [None, ValueError('READONLY_DUPLICATE_IDENTITY_CHANGED')]
        with self.assertRaisesRegex(ValueError, 'READONLY_DUPLICATE_IDENTITY_CHANGED'):
            reader.sample()

    def test_input_unknown_keeps_existing_world_and_scene_at_combined_budget(self):
        reader, reads = self.reader(scene_bytes=8190,
            leaf=lambda native, sampler: (sampler.read(0x10000, 2) and
                dict(status='OBSERVED', my_player_uid=12345)))
        def input_leaf(current, row, proof):
            try:
                current.sampler.read(0x10000, 1)
            except ValueError as error:
                return input_state.empty(error.args[0])
            self.fail('combined allowance escaped')
        reader.input_state = SimpleNamespace(sample=input_leaf)
        original_route, original_scene = reader.sampler.route, reader.sampler.scene
        result, count = reader.sample()
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertEqual(result['world']['status'], 'OBSERVED')
        self.assertEqual(result['world']['my_player_uid'], 12345)
        self.assertEqual(result['input_state']['status'], 'UNKNOWN')
        self.assertEqual(result['input_state']['reason'], 'RETAINED_SAMPLE_BYTE_BUDGET')
        self.assertEqual(count, 8192)
        self.assertEqual(sum(reads), 8192)
        self.assertEqual(reader.sampler.route, original_route)
        self.assertEqual(reader.sampler.scene, original_scene)

    def test_measured_scene_world_input_total_fits_16k_preserving_frozen_leaf_limits(self):
        def leaf(native, sampler):
            sampler.bytes = 0
            sampler.read(0x10000, 4096)
            sampler.read(0x10000, 1977)
            return dict(status='OBSERVED', my_player_uid=1, grid_words=[32571, 32951],
                        map_resolved_i32=0, typed_bytes_requested=sampler.bytes)
        reader, reads = self.reader(scene_bytes=4197, leaf=leaf)
        reader.sample_byte_limit = obs.RETAINED_SAMPLE_LIMIT
        def input_leaf(current, row, proof):
            old = current.sampler.bytes
            current.sampler.bytes = 0
            try:
                current.sampler.read(0x10000, 2244)
            finally:
                current.sampler.bytes = old
            return dict(input_state.empty(), status='OBSERVED', typed_bytes_requested=2244)
        reader.input_state = SimpleNamespace(sample=input_leaf)
        result, total = reader.sample()
        self.assertEqual(total, 12514)
        self.assertEqual(sum(reads), total)
        self.assertEqual(result['world']['my_player_uid'], 1)
        self.assertEqual(result['world']['grid_words'], [32571, 32951])
        self.assertEqual(result['input_state']['status'], 'OBSERVED')
        self.assertEqual(reader.contract['bounds']['typed_byte_limit'], 8192)
        self.assertTrue(all(n <= 4096 for n in reads))

    def test_input_reuses_current_watch_proof_and_restores_sampler_methods(self):
        reader, _ = self.reader(scene='Login')
        route, raw = (123, True, 4), bytes(36)
        scene = {'current': {'kind': 'Login'}, 'pending': {'kind': 'none'}}
        reader.sampler.route = Mock(return_value=route)
        reader.sampler.scene = Mock(return_value=(scene, raw))
        original_route, original_scene = reader.sampler.route, reader.sampler.scene
        def sample(native, sampler):
            self.assertEqual(sampler.route(), route)
            self.assertEqual(sampler.scene(999), (scene, raw))
            self.assertEqual(sampler.route(), route)
            sampler.bytes = 0
            return dict(status='OBSERVED', current='Login', pending='none', root_ready=True)
        reader.watch.sample = sample
        def input_leaf(current, row, proof):
            self.assertEqual(proof, dict(route=route, state=999, scene=scene, raw=raw))
            self.assertIs(current.sampler.route, original_route)
            self.assertIs(current.sampler.scene, original_scene)
            return input_state.empty('FIXTURE_ONLY')
        reader.input_state = SimpleNamespace(sample=input_leaf)
        result, _ = reader.sample()
        self.assertEqual(result['status'], 'OBSERVED')
        self.assertEqual(result['input_state']['reason'], 'FIXTURE_ONLY')
        self.assertEqual(original_route.call_count, 2)
        self.assertEqual(original_scene.call_count, 1)

    def test_monitor_publishes_world_then_invalidates_it_on_identity_loss(self):
        now = [0.0]
        reader, _ = self.reader(leaf=lambda *_: dict(status='OBSERVED', my_player_uid=12345,
                                                    raw_pointer='PRIVATE_ADDRESS'))
        reader.bind = Mock()
        owner = SimpleNamespace(child=object(), validate=lambda _: True,
                                native=SimpleNamespace(job_windows=lambda _: []))
        with tempfile.TemporaryDirectory() as folder:
            monitor = obs.SessionMonitor(Path('C:/fixture.exe'), folder,
                                         reader=reader, clock=lambda: now[0])
            monitor.bind(owner)
            first = monitor.tick()
            self.assertEqual(first['memory']['world']['my_player_uid'], 12345)
            self.assertNotIn('PRIVATE_', json.dumps(first))
            reader.validate.side_effect = ValueError('READONLY_DUPLICATE_JOB_CHANGED')
            now[0] = .75
            failed = monitor.tick()
            self.assertEqual(failed['memory']['scene']['status'], 'UNKNOWN')
            self.assertEqual(failed['memory']['world']['reason'], 'READONLY_DUPLICATE_JOB_CHANGED')
            self.assertIsNone(failed['memory']['world']['my_player_uid'])
            raw = (Path(folder) / 'status.json').read_bytes()
            self.assertLessEqual(len(raw), obs.STATUS_LIMIT)


class LiveMovementStatusTests(unittest.TestCase):
    def test_event_counters_preserve_zero_and_filter_unknown_values(self):
        for value in (0, 2, obs.MAX_COUNTER, None, True, -1, obs.MAX_COUNTER + 1, '2', 2.0):
            with self.subTest(value=value):
                source = dict(committed=0, active_services=1, sessions=[dict(
                    requests_received=value, corrections_prepared=value)])
                result = obs.public_movement(source)['sessions'][0]
                expected = value if type(value) is int and 0 <= value <= obs.MAX_COUNTER else None
                self.assertEqual(result['requests_received'], expected)
                self.assertEqual(result['corrections_prepared'], expected)

    def test_current_movement_and_edge_metadata_are_bounded_and_redacted(self):
        from tools.local_original_session import broker
        realm = broker.LocalRealm.__new__(broker.LocalRealm)
        realm.edge_passability = SimpleNamespace(last_result=dict(
            status='UNKNOWN', reason='SPATIAL_TARGET_NONEMPTY_UNCLASSIFIED',
            typed_bytes_requested=1234, raw_pointer='PRIVATE_ADDRESS', payload='PRIVATE_BODY'))
        edge_report = realm.edge_report()
        position = dict(uid=1, map_id=0, grid=[32571, 32951], name='PRIVATE_NAME')
        session = dict(connection_id=4, committed=0, authority=position, fatal=False, closed=False,
                       raw_pointer='PRIVATE_ADDRESS', last_result=dict(accepted=False, reason='EDGE_UNKNOWN',
                       unknown=True, fatal=False, authority=position, reply_count=1, own_SC4E2C_count=0,
                       payload='PRIVATE_BODY'))
        source = dict(state='OPEN', movement=dict(committed=0, active_services=1, sessions=[session] * 9),
                      edge_check=edge_report)
        result = obs.broker_status(SimpleNamespace(report=lambda: source))
        self.assertEqual(result['edge_check']['reason'], 'SPATIAL_TARGET_NONEMPTY_UNCLASSIFIED')
        self.assertEqual(result['edge_check']['typed_bytes_requested'], 1234)
        self.assertEqual(len(result['movement']['sessions']), 6)
        self.assertEqual(result['movement']['sessions'][0]['last_result']['reason'], 'EDGE_UNKNOWN')
        self.assertEqual(result['movement']['sessions'][0]['authority']['grid'], [32571, 32951])
        self.assertNotIn('PRIVATE_', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
