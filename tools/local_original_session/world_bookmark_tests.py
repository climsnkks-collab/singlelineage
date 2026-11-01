"""Remembered-place storage and unit contracts; no process, socket or port."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tools.local_character_creation import realm
from tools.local_original_session import world_bookmark as bookmark
from tools.local_original_session import world_feature_bookmark as feature


class BookmarkModelTests(unittest.TestCase):
    def test_request_parser_reuses_compiled_fields_and_rejects_duplicates(self):
        from tools.local_entry_server import protobuf as pb
        name = pb.encode_bytes(1, '마을'.encode('utf-8'))
        self.assertEqual(bookmark.parse_request(bookmark.ADD, name), {1: '마을'})
        self.assertEqual(bookmark.parse_request(bookmark.UPDATE,
            name + bookmark.varint(2, 4)), {1: '마을', 2: 4})
        self.assertEqual(bookmark.parse_request(bookmark.EXTEND, b''), {})
        for opcode, body in ((bookmark.ADD, name + name), (bookmark.DELETE, name),
                             (bookmark.EXTEND, bookmark.varint(1, 1)),
                             (bookmark.TELEPORT, bookmark.varint(1, 1))):
            with self.subTest(opcode=opcode), self.assertRaises(ValueError):
                bookmark.parse_request(opcode, body)

    def test_add_rename_delete_keep_monotonic_ids_and_enforce_official_capacity(self):
        state = bookmark.empty()
        for i in range(50):
            state = bookmark.add(state, '장소' + str(i), 0, 32700 + i, 32800)
        with self.assertRaisesRegex(ValueError, 'CAPACITY_FULL'):
            bookmark.add(state, '초과', 0, 32700, 32800)
        state = bookmark.rename(state, 1, '새이름')
        state = bookmark.delete(state, 1, '새이름')
        state = bookmark.add(state, '새장소', 0, 32700, 32800)
        self.assertEqual(state['entries'][-1]['id'], 51)
        self.assertEqual(state['next_id'], 52)

    def test_names_and_current_id_reject_without_mutating_previous_state(self):
        state = bookmark.add(bookmark.empty(), '한글' * 8, 0, 32700, 32800)
        self.assertTrue(bookmark.valid_name('a' * 32))
        for name in ('한' * 17, 'a' * 33, '', ' 장소', '장소\n'):
            self.assertFalse(bookmark.valid_name(name))
        with self.assertRaisesRegex(ValueError, 'CURRENT_NAME'):
            bookmark.delete(state, 1, '다른이름')
        with self.assertRaisesRegex(ValueError, 'CURRENT_ENTRY'):
            bookmark.rename(state, 999, '새이름')
        self.assertEqual(state['entries'][0]['name'], '한글' * 8)
        with self.assertRaisesRegex(ValueError, 'NAME_EXISTS'):
            bookmark.add(state, '한글' * 8, 0, 32700, 32800)


class BookmarkStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'characters.json'
        self.store = realm.CharacterStore(self.path)
        for name in ('기사', '법사'):
            self.store.create(realm.Creation(name, 1, 0, (16, 12, 14, 9, 10, 8)))

    def test_old_profile_read_does_not_write_and_only_selected_row_changes(self):
        before = self.path.read_bytes()
        self.assertEqual(self.store.bookmarks(1), bookmark.empty())
        self.assertEqual(before, self.path.read_bytes())
        state = self.store.update_bookmarks(1, lambda value:
            bookmark.add(value, '마을', 0, 32700, 32800))
        first = json.loads(before)
        after = json.loads(self.path.read_bytes())
        self.assertEqual(after['next_uid'], first['next_uid'])
        self.assertEqual(after['characters'][1], first['characters'][1])
        self.assertEqual({k: v for k, v in after['characters'][0].items() if k != 'bookmarks'},
                         first['characters'][0])
        self.assertEqual(realm.CharacterStore(self.path).bookmarks(1), state)
        self.assertEqual(self.store.select('기사')[0], 1)
        self.assertEqual(self.store.roster().row_count, 2)
        # A later character creation preserves both existing optional fields.
        self.store.create(realm.Creation('요정', 2, 1, (12, 12, 12, 12, 12, 12)))
        self.assertEqual(self.store.bookmarks(1), state)

    def test_failure_preserves_disk_and_no_implicit_success(self):
        before = self.path.read_bytes()
        with patch.object(self.store, '_write', side_effect=OSError('unit write failure')):
            with self.assertRaisesRegex(OSError, 'unit write failure'):
                self.store.update_bookmarks(1, lambda value:
                    bookmark.add(value, '마을', 0, 32700, 32800))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.bookmarks(1), bookmark.empty())

    def test_unknown_optional_and_malformed_bookmarks_still_reject(self):
        value = json.loads(self.path.read_bytes())
        value['characters'][0]['unrecognized_field'] = 1
        self.path.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CREATE_STORE_ROW'):
            self.store.bookmarks(1)
        del value['characters'][0]['unrecognized_field']
        value['characters'][0]['bookmarks'] = dict(next_id=1, capacity=50, entries=[{}])
        self.path.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'BOOKMARK_STORE_ROW'):
            self.store.bookmarks(1)


class BookmarkFeatureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from tools.local_original_session import inventory
        from tools.local_original_session.world_handlers import _starter_fields
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = realm.CharacterStore(Path(self.temp.name) / 'characters.json')
        self.store.create(realm.Creation('기사', 1, 0, (16, 12, 14, 9, 10, 8)))
        self.store.update_bookmarks(1, lambda value: bookmark.add(value, '마을', 0, 32700, 32800))
        self.writer, self.game = object(), object()
        self.position = SimpleNamespace(uid=1, map_id=0, word0=32701, word1=32801)
        self.sent, self.costs, self.moves = [], [], []
        fields = _starter_fields()
        fields.update({1: 65590, 2: 23, 4: 2, 7: 473,
                       18: '[축복] 순간이동 주문서'.encode('utf-8')})
        async def dispatch(function):
            return function()
        async def send(writer, row, frames, lock):
            self.sent.extend(frames)
        def consume(writer, uid):
            self.costs.append(uid)
            return b'cost'
        def relocate(writer, row, game, destination):
            self.moves.append(destination)
            return (b'relocation',)
        self.ctx = SimpleNamespace(_bookmark_errors=[], _world_map_exp=0,
            inventory_frame=inventory.build_kit_frame([fields]),
            _world_bound=lambda writer: True, _world_ready=lambda writer, game: True,
            selected_session=lambda writer: self.game, owner_current=lambda *args: True,
            _world_stats_for=lambda position: (None, (), None),
            realm=SimpleNamespace(store=self.store,
                service=lambda writer: SimpleNamespace(snapshot=lambda: self.position),
                serves_map=lambda map_id: map_id == 0),
            world=SimpleNamespace(combat=SimpleNamespace(is_dead=lambda uid: False),
                terrain=SimpleNamespace(can_stand=lambda *args: True),
                runtime=SimpleNamespace(dispatch_now=dispatch), drain=lambda uid: ()),
            _world_send=send, _world_consume_kit=consume, _world_relocate_locked=relocate)

    def use(self, triple=(0, 32700, 32800), *, uid=65590):
        from tools.local_entry_server import protobuf as pb
        fields = {1: 1, 15: 0, 16: 0} if triple is None else dict(zip((1, 8, 9, 10), (1, *triple)))
        child = b''.join(bookmark.varint(n, value) for n, value in fields.items())
        return SimpleNamespace(opcode=0x0960,
            payload=bookmark.varint(1, uid) + pb.encode_bytes(2, child))

    async def item(self, *args, **kwargs):
        return await feature._bookmark_item(self.ctx, self.writer, {}, self.game,
                                             self.use(*args, **kwargs), object())

    async def test_selected_native_opaque_echo_uses_saved_destination_and_one_existing_cost(self):
        self.assertTrue(await self.item())
        self.assertEqual(self.costs, [65590])
        self.assertEqual([(v.map_id, v.x, v.y) for v in self.moves], [(0, 32700, 32800)])
        self.assertEqual(self.sent, [b'cost', b'relocation'])

    async def test_unknown_place_normal_scroll_and_unavailable_map_keep_inventory(self):
        from tools.local_original_session import inventory
        self.assertTrue(await self.item((0, 111, 222)))
        self.assertFalse(await self.item(None))  # original random handler retains raw0
        self.assertFalse(await self.item(uid=999))
        rows = [dict(v.raw_fields) for v in inventory.validate_kit_frame(self.ctx.inventory_frame)]
        rows[0][18] = b''
        self.ctx.inventory_frame = inventory.build_kit_frame(rows)
        self.assertTrue(await self.item())  # normal scroll, no equipped control ring
        self.assertEqual(self.costs, [])
        self.assertEqual(self.moves, [])
        self.assertEqual(self.sent, [])

    async def test_position_failure_after_debit_is_propagated_without_success_reply(self):
        def fail(*args):
            raise ValueError('position unit save failed')
        self.ctx._world_relocate_locked = fail
        with self.assertRaisesRegex(ValueError, 'position unit save failed'):
            await self.item()
        self.assertEqual(self.costs, [65590])
        self.assertEqual(self.sent, [])

    async def test_rename_delete_no_fake_ack_and_extension_does_not_mutate(self):
        from tools.local_entry_server import protobuf as pb
        async def request(opcode, body):
            return await feature._bookmark_request(self.ctx, self.writer, {}, self.game,
                SimpleNamespace(opcode=opcode, payload=body), object())
        await request(bookmark.UPDATE, pb.encode_bytes(1, '새이름'.encode('utf-8')) + bookmark.varint(2, 1))
        self.assertEqual(self.store.bookmarks(1)['entries'][0]['name'], '새이름')
        await request(bookmark.DELETE, pb.encode_bytes(1, '새이름'.encode('utf-8')) + bookmark.varint(2, 1))
        self.assertEqual(self.store.bookmarks(1)['entries'], [])
        await request(bookmark.EXTEND, b'')
        self.assertEqual(self.store.bookmarks(1)['capacity'], 50)
        self.assertEqual(self.sent, [])
        self.assertIn('EXTENSION_COST', self.ctx._bookmark_errors[-1])

    async def test_phase2_departure_escape_and_markability_are_independent(self):
        self.position.map_id = 2  # L1J teleportable=0, escapable=1, markable=0.
        self.ctx._world_map_exp = 2
        before = self.store.bookmarks(1)
        await feature._bookmark_request(self.ctx, self.writer, {}, self.game,
            SimpleNamespace(opcode=bookmark.ADD,
                payload=bookmark.pb.encode_bytes(1, '던전'.encode('utf-8'))), object())
        self.assertEqual(self.store.bookmarks(1), before)
        self.assertEqual(self.ctx._bookmark_errors[-1], 'BOOKMARK_LOCATION_NOT_MARKABLE')
        self.assertTrue(await self.item())
        self.assertEqual(self.costs, [65590])
        self.assertEqual(len(self.moves), 1)

    async def test_phase2_non_escapable_and_unknown_departures_preserve_everything(self):
        before = self.store.bookmarks(1)
        self.ctx._world_map_exp = 2
        for map_id, reason in ((37, 'BOOKMARK_DEPARTURE_NOT_ESCAPABLE'),
                               (999999, 'BOOKMARK_LOCATION_POLICY_UNKNOWN')):
            self.position.map_id = map_id
            self.assertTrue(await self.item())
            self.assertEqual(self.ctx._bookmark_errors[-1], reason)
            self.assertEqual(self.store.bookmarks(1), before)
            self.assertEqual((self.costs, self.moves, self.sent), ([], [], []))

    async def test_phase2_coordinate_command_never_authorizes_arbitrary_movement(self):
        before = self.store.bookmarks(1)
        for first in (0, 0xffffffffffffffff):
            payload = b''.join(bookmark.varint(n, value) for n, value in
                ((1, first), (2, 32700), (3, 32800)))
            self.assertEqual(bookmark.parse_request(bookmark.TELEPORT, payload),
                             {1: first, 2: 32700, 3: 32800})
            await feature._bookmark_request(self.ctx, self.writer, {}, self.game,
                SimpleNamespace(opcode=bookmark.TELEPORT, payload=payload), object())
            self.assertEqual(self.ctx._bookmark_errors[-1], 'BOOKMARK_COORDINATE_COMMAND_UNSUPPORTED')
        self.assertEqual(self.store.bookmarks(1), before)
        self.assertEqual((self.costs, self.moves, self.sent), ([], [], []))

    async def test_phase2_owned_crystal_has_no_fabricated_store_notification_or_debit(self):
        from tools.local_original_session import inventory
        rows = [dict(v.raw_fields) for v in inventory.validate_kit_frame(self.ctx.inventory_frame)]
        rows[0][2] = bookmark.CRYSTAL_TEMPLATE
        self.ctx.inventory_frame = inventory.build_kit_frame(rows)
        before = self.ctx.inventory_frame, self.store.bookmarks(1)
        # No recovered initial/confirmation params are asserted by this test.
        self.assertTrue(await self.item(None))
        self.assertEqual(self.ctx._bookmark_errors[-1],
                         'BOOKMARK_CRYSTAL_STORAGE_AND_USE_CONTRACT_UNKNOWN')
        self.assertEqual((self.ctx.inventory_frame, self.store.bookmarks(1)), before)
        self.assertEqual((self.costs, self.moves, self.sent), ([], [], []))


class BookmarkPhase2ProtocolTests(unittest.TestCase):
    def test_crystal_list_encoding_is_separate_from_main_capacity_list(self):
        value = bookmark.add(bookmark.empty(), '마을', 0, 32700, 32800)
        main, crystal = bookmark.list_frame(value), bookmark.list_frame(value, store=True)
        self.assertEqual(int.from_bytes(main[2:4], 'little'), bookmark.ADD_NOTI)
        self.assertEqual(int.from_bytes(crystal[2:4], 'little'), bookmark.STORE_NOTI)
        with bookmark.pb.parse_message(main[4:-2]) as parsed:
            self.assertEqual(parsed.occurrences(1)[0].value, 50)
            main_row = bytes(parsed.occurrences(2)[0].value)
        with bookmark.pb.parse_message(crystal[4:-2]) as parsed:
            self.assertEqual(bytes(parsed.occurrences(1)[0].value), main_row)
            self.assertEqual(len(parsed.fields), 1)
        self.assertNotIn(bookmark.STORE_NOTI, feature.OUTGOING_OPCODES)
        self.assertNotIn(bookmark.EXTEND_ACK, feature.OUTGOING_OPCODES)

    def test_phase2_l1j_region_reference_and_unknown_boundary(self):
        for map_id in (0, 4):
            self.assertTrue(bookmark.location_allowed(map_id, remembering=True))
        for map_id in (2, 5, 37, 70, 101):
            self.assertFalse(bookmark.location_allowed(map_id, remembering=True))
        self.assertTrue(bookmark.location_allowed(2))
        for map_id in (37, 70):
            self.assertFalse(bookmark.location_allowed(map_id))
        with self.assertRaisesRegex(ValueError, 'POLICY_UNKNOWN'):
            bookmark.location_allowed(999999)


if __name__ == '__main__':
    unittest.main()
