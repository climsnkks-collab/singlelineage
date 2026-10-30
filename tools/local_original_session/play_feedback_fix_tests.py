"""User play-test fixes: 0960 report, display projection, effects, 4ED7, 026B, movement."""
import asyncio
import random
import struct
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import (inventory, inventory_update, movement as m, settings,
                                          world_bridge, world_core_kit, world_feature_items,
                                          world_item_effects, world_visibility)
from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
from tools.local_original_session.world_status_frames import effect_frame

UID = 65537


def kit(*rows):
    result = []
    for index, (template, count, name) in enumerate(rows):
        fields = dict(INVENTORY_STARTER_FIELDS)
        fields.update({1: 1000 + index, 2: template, 4: count, 18: name})
        result.append(fields)
    return inventory.build_kit_frame(result)


class DisplayCtx:
    _inventory_kit_policy = inventory.KIT_POLICY
    _world = object()

    def fold_sync_hooks(self, name, value, *args):
        if name == 'inventory_display_fields':
            return world_feature_items._world_items_display_fields(self, value, *args)
        return value


class EffectFrameTests(unittest.TestCase):
    def test_core_builder_matches_former_feature_bytes(self):
        body = pb.encode_uint32(1, UID) + pb.encode_uint32(2, 744)
        self.assertEqual(effect_frame(UID, 744), struct.pack('<HH', len(body) + 6, 0x4ED8) + body + b'\0\0')
        with self.assertRaises(ValueError):
            effect_frame(0, 744)

    def test_use_gfx_loaded_and_led_for_consumed_use_only(self):
        definitions = world_item_effects.load_effects()
        extended = world_item_effects.load_effects(owner='consumables')
        expected = {14: 189, 15: 194, 130: 197, 17: 191, 296: 751, 492: 190, 126: 192}
        self.assertEqual({t: definitions[t].use_gfx for t in expected}, expected)
        self.assertEqual(extended[297].use_gfx, 750)
        effects = world_item_effects.WorldItemEffects(types.SimpleNamespace(rng=random.Random(1)))
        result = world_item_effects.ItemEffectResult
        self.assertEqual(effects.use_effect_frame(UID, 14, result(14, 'heal', 'no_effect', 1)),
                         effect_frame(UID, 189))
        self.assertIsNone(effects.use_effect_frame(UID, 296, result(296, 'speed', 'no_effect', 1)))
        self.assertIsNone(effects.use_effect_frame(UID, 14, result(14, 'heal', 'refused')))
        self.assertIsNone(effects.use_effect_frame(UID, 162))  # return scroll: no gfx
        status = b'\x08\0\x38\x4e\0\0'
        with mock.patch.object(effects, '_use', return_value=result(14, 'heal', 'applied', 1, (status,))):
            self.assertEqual(effects.use(UID, 14, 1.0).frames, (effect_frame(UID, 189), status))


class DisplayProjectionTests(unittest.TestCase):
    def test_stack_suffix_and_targeted_scroll_projection_keep_canonical_frame(self):
        canonical = kit((1, 1, '단검'.encode()), (40, 1500, '아데나'.encode()), (25, 3, b''))
        projected = world_core_kit.display_frame(DisplayCtx(), canonical)
        rows = [dict(item.raw_fields) for item in inventory.validate_kit_frame(projected)]
        self.assertEqual(rows[0][18], '단검'.encode())
        self.assertEqual(rows[1][18], '아데나 (1500)'.encode())
        self.assertEqual(rows[2][5], 7)
        name = world_visibility.item_names().get(25, b'')
        self.assertEqual(rows[2][18], (name + b' (3)') if name else b'')
        saved = [dict(item.raw_fields) for item in inventory.validate_kit_frame(canonical)]
        self.assertEqual((saved[1][18], saved[2][5]), ('아데나'.encode(), 0))
        # The projection is idempotent and never doubles a suffix.
        self.assertEqual(world_core_kit.display_frame(DisplayCtx(), projected), projected)
        self.assertEqual(world_core_kit.display_name(b'x (5)', 5), b'x (5)')
        self.assertEqual(world_core_kit.display_name(b'x', 1), b'x')

    def test_send_payload_projects_world_0964_and_splits_initial_delivery(self):
        ctx = DisplayCtx()
        wire = kit((40, 7, '아데나'.encode()))
        self.assertIn('아데나 (7)'.encode(), world_core_kit.inventory_payload(ctx, wire, False))
        other = inventory_update._encode(inventory_update._values({1: 1000, 4: 7}))
        self.assertIs(world_core_kit.inventory_payload(ctx, other, False), other)
        many = kit(*((40, 100 + i, ('물건%d' % i).encode()) for i in range(60)))
        payload = world_core_kit.inventory_payload(ctx, many, True)
        offset, frames = 0, []
        while offset < len(payload):
            size = int.from_bytes(payload[offset:offset + 2], 'little')
            frames.append(payload[offset:offset + size])
            offset += size
        self.assertTrue(len(frames) > 1 and all(len(f) <= inventory.MAX_FRAME for f in frames))
        names = [dict(i.raw_fields)[18] for f in frames for i in inventory.validate_kit_frame(f)]
        self.assertEqual(names[0], '물건0 (100)'.encode())

    def test_identified_label_carries_stack_suffix(self):
        state = world_item_effects.ConsumableState(identified={1000})
        frame, = world_item_effects.identified_projection(kit((14, 4, '빨간 물약'.encode())), state)
        self.assertIn('빨간 물약 [확인됨] (4)'.encode(), frame)

    def test_ground_name_shows_quantity_first(self):
        from tools.local_original_session.world_entities import EntityRef
        from tools.local_original_session.world_ground_items import GroundItem
        name = world_visibility.item_names()[1]
        for count, expected in ((100, b'100 ' + name), (1, name)):
            ground = GroundItem(EntityRef(500, 1), EntityRef(501, 2), 1, count, 1, True, 0, 100, 101, 0, 10, 600)
            with pb.parse_message(world_visibility.ground_frame(ground)[4:-2]) as parsed:
                self.assertEqual(bytes(parsed.occurrences(9)[0].value), expected)


class ItemUseProbeTests(unittest.IsolatedAsyncioTestCase):
    def broker(self, handlers):
        broker = types.SimpleNamespace(
            _inventory_kit_policy=inventory.KIT_POLICY, _world=object(),
            _inventory_current_frame=kit((25, 2, b''), (1, 1, b'')),
            _world_handler_errors=[], _world_item_use_log=[], _world_item_use_pending=None,
            _world_registry=types.SimpleNamespace(frames={0x0960: tuple(handlers)}),
            _item_use_session=types.SimpleNamespace(last_outcome=None))
        for name, value in handlers.items():
            setattr(broker, name, value)
        return broker

    async def test_handled_and_legacy_silent_refusal_are_recorded(self):
        params = (pb.encode_uint32(1, 1) + pb.encode_uint32(2, 1001) + pb.encode_uint32(3, 0)
                  + pb.encode_uint32(15, 0) + pb.encode_uint32(16, 0))
        frame = types.SimpleNamespace(opcode=0x0960, payload=pb.encode_uint32(1, 1000) + pb.encode_bytes(2, params))
        async def declines(*_):
            return False
        async def takes(*_):
            return True
        broker = self.broker({'_pet_frame': declines, '_world_dispatch': takes})
        self.assertTrue(await world_bridge.receive(broker, object(), {}, None, frame, None))
        record, = broker._world_item_use_log
        self.assertEqual((record['template'], record['target_template'], record['handler'], record['result']),
                         (25, 1, '_world_dispatch', 'handled'))
        self.assertEqual(record['params'], [(1, 0), (2, 0), (3, 0), (15, 0), (16, 0)])
        broker = self.broker({'_pet_frame': declines})
        writer = object()
        self.assertFalse(await world_bridge.receive(broker, writer, {}, None, frame, None))
        broker._item_use_session.last_outcome = types.SimpleNamespace(
            kind=types.SimpleNamespace(value='REJECTED'), reason='ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')
        world_bridge._item_use_settle(broker, id(writer), completed=True)
        self.assertEqual(broker._world_item_use_log[0]['result'],
                         'legacy_REJECTED:ITEM_USE_IDENTIFIER_NOT_CURRENT_ITEM')

    def test_pet_and_companion_report_their_errors(self):
        from tools.local_original_session import world_feature_companion as companion, world_feature_pet as pet
        result = {}
        pet._pet_report(types.SimpleNamespace(_pet_system=types.SimpleNamespace(errors=['PET_X'])), result)
        companion._companion_report(types.SimpleNamespace(_companion_errors=['COMPANION_Y']), result)
        self.assertEqual((result['pet_errors'], result['companion_errors']), (['PET_X'], ['COMPANION_Y']))
        self.assertIn('_pet_report', pet.HOOKS['report'])
        self.assertIn('_companion_report', companion.HOOKS['report'])

    def test_iteminfo_publishes_names_on_inventory_delivery(self):
        from tools.local_original_session import world_feature_iteminfo as iteminfo
        self.assertEqual(iteminfo.HOOKS['inventory_delivered'], ('_iteminfo_delivered',))


class SettingsAndLoginTests(unittest.TestCase):
    def test_noti_frame_pairs_saved_fields_or_omits(self):
        from tools.local_original_session import ats_config_codec as codec
        first, second = codec.wrap_blob(b'self-config'), codec.wrap_blob(b'ats-config')
        frame = settings.noti_frame(pb.encode_bytes(1, first) + pb.encode_bytes(2, second))
        self.assertEqual(int.from_bytes(frame[2:4], 'little'), 0x4ED7)
        with pb.parse_message(frame[4:-2]) as parsed:
            self.assertEqual(codec.read_noti_field(bytes(parsed.occurrences(1)[0].value)), first)
            self.assertEqual(codec.read_noti_field(bytes(parsed.occurrences(2)[0].value)), second)
        self.assertIsNone(settings.noti_frame(pb.encode_bytes(1, first)))
        self.assertIsNone(settings.noti_frame(pb.encode_bytes(1, b'bad') + pb.encode_bytes(2, second)))
        self.assertIsNone(settings.noti_frame(None))

    def test_login_auth_finish_is_empty_026b(self):
        from tools.local_original_session import broker as b
        self.assertEqual(b.LOGIN_AUTH_FINISH_FRAME, b'\x06\x00\x6b\x02\x00\x00')


class SettingsNotiLoopbackTests(unittest.IsolatedAsyncioTestCase):
    """Real route/_send: 4ED6 save -> restart -> reselect writes the same 4ED7."""
    async def asyncSetUp(self):
        from tools.local_original_session import broker_tests
        self.dispatch = types.MethodType(broker_tests.AttackIntentRouteTests.dispatch, self)
        await broker_tests.RestartRouteTests.asyncSetUp(self)

    async def test_saved_settings_return_as_4ed7_on_reselect(self):
        from tools.local_original_session import ats_config_codec as codec, broker_tests
        first, second = codec.wrap_blob(b'self-config-restart-key'), codec.wrap_blob(b'ats')
        position = self.realm.service(self.writer).snapshot()
        self.realm.positions.commit(position, position)
        await self.dispatch(broker_tests.c2s(settings.OPCODE, pb.encode_bytes(1, first) + pb.encode_bytes(2, second)))
        await self.dispatch(broker_tests.c2s(0x4e33))
        self.writer.write.reset_mock()
        selection = pb.encode_message([pb.encode_bytes(1, position.name.encode()),
                                       pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])
        # World play never sends the legacy trial NPC with the selection reply.
        with mock.patch.object(type(self.realm), '_trial_target_hidden', return_value=True):
            await self.dispatch(broker_tests.c2s(0x4e28, selection))
        written = [call.args[0] for call in self.writer.write.call_args_list]
        noti = [w for w in written if int.from_bytes(w[2:4], 'little') == 0x4ED7]
        self.assertEqual(len(noti), 1)
        with pb.parse_message(noti[0][4:-2]) as parsed:
            self.assertEqual(bytes(parsed.occurrences(1)[0].value), first.hex().encode())
            self.assertEqual(bytes(parsed.occurrences(2)[0].value), second.hex().encode())
        self.assertEqual(int.from_bytes(written[0][2:4], 'little'), 0x4E29)


class PublishedStartTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        profile = Path(self.folder.name) / 'characters.json'
        profile.write_bytes(b'{}\n')
        self.selected = m.Position(1, 'SoloKnight', 0, 32571, 32951)
        async def owner(*_):
            return True
        async def edge(*_):
            return True
        self.service = m.MovementService(self.selected, connection=object(), owner_guard=owner,
                                         edge_passability=edge, store=m.PositionStore(profile))

    @staticmethod
    def payload(position, direction=2):
        return m.pb.encode_message([m.pb.encode_uint32(1, position.packed),
                                    m.pb.encode_varint(2 << 3) + m.pb.encode_varint(direction)])

    async def test_move_from_resent_actor_cell_commits_without_correction(self):
        published = self.service.snapshot()
        self.service.actor_published()
        ahead = await self.service.handle_CS4E2B(self.payload(published))  # committed before the resend arrived
        self.assertTrue(ahead.accepted)
        replay = await self.service.handle_CS4E2B(self.payload(published, 4))
        self.assertEqual((replay.accepted, replay.replies), (True, ()))
        self.assertEqual(self.service.published_adopted, 1)
        # One-shot: the same stale start is corrected again.
        stale = await self.service.handle_CS4E2B(self.payload(published, 4))
        self.assertEqual(stale.reason, 'STALE_START')
        self.assertEqual(len(stale.replies), 1)

    async def test_other_cell_or_expired_publication_keeps_correction(self):
        start = self.service.snapshot()
        self.service.actor_published()
        await self.service.handle_CS4E2B(self.payload(start))
        other = m.Position(1, 'SoloKnight', 0, 32500, 32900)
        self.assertEqual((await self.service.handle_CS4E2B(self.payload(other))).reason, 'STALE_START')
        self.service.actor_published()
        moved = self.service.snapshot()
        await self.service.handle_CS4E2B(self.payload(moved))
        with mock.patch.object(m.time, 'monotonic', return_value=m.time.monotonic() + 60):
            self.assertEqual((await self.service.handle_CS4E2B(self.payload(moved))).reason, 'STALE_START')


class StanceRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_unchanged_appearance_skips_resend_and_change_sends(self):
        sent, stance = [], [0]
        position = types.SimpleNamespace(uid=UID)
        service = types.SimpleNamespace(snapshot=lambda: position, _actor_heading=None,
                                        actor_published=lambda *a: sent.append('published'))
        realm = types.SimpleNamespace(service=lambda writer: service, _world_frames={},
            _frames_for=lambda *_a, **_k: (None, None, bytes(4) + bytes([stance[0]]) + bytes(2)))
        async def send(writer, row, frames, lock):
            sent.extend(frames)
        dispatch = mock.AsyncMock()
        publish = mock.Mock()
        world = types.SimpleNamespace(runtime=types.SimpleNamespace(dispatch_now=dispatch),
                                      publish_pc_actor=publish)
        ctx = types.SimpleNamespace(realm=realm, _world=world,
                                    _world_bound=lambda writer: True, _world_send=send)
        fake = types.SimpleNamespace(world=types.SimpleNamespace(
            decode_payload=lambda op, raw: {2: UID, 3: 61, 4: raw[0]}))
        with mock.patch.object(world_core_kit, 'session', fake):
            world_core_kit.remember_self_actor(service, {3: 61, 4: 0})  # the select's 4E96
            self.assertEqual(await world_core_kit._world_refresh_stance_locked(ctx, object(), {'operation_lock': None}), 0)
            self.assertEqual(sent, [])  # INITIAL_SYNC / same-stance item use: no snap-back resend
            dispatch.assert_not_awaited()
            stance[0] = 4
            await world_core_kit._world_refresh_stance_locked(ctx, object(), {'operation_lock': None})
            self.assertEqual(sent, [bytes(4) + bytes([4]) + bytes(2), 'published'])
            dispatch.assert_awaited_once_with(publish, UID, {2: UID, 3: 61, 4: 4})
            await world_core_kit._world_refresh_stance_locked(ctx, object(), {'operation_lock': None})
            self.assertEqual(len(sent), 2)
            self.assertEqual(dispatch.await_count, 1)


if __name__ == '__main__':
    unittest.main()
