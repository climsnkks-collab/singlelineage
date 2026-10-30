"""Development unit checks only; these are not native-client/UI PASS claims."""
from dataclasses import replace
import json
from pathlib import Path
import struct
from types import MethodType, SimpleNamespace, MappingProxyType
import unittest
from unittest.mock import patch

from tools.local_original_session import game_data, inventory
from tools.local_original_session import world_feature_talkscroll as feature
from tools.local_original_session import world_talkscroll as scroll
from tools.local_original_session.world_terrain import WorldTerrain


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = scroll.load_catalog()
        self.selection = scroll.Selection(1, 65590, 12273, (0, 32578, 32946), 'lucas1', True)

    def select(self, action, **changes):
        values = dict(pc_uid=1, target_uid=65590, action=action, origin=(0, 32578, 32946),
                      owned_template=12273, owned_count=20)
        values.update(changes)
        return scroll.select(self.catalog, self.selection, **values)

    def test_native_item_identity_and_prepared_points(self):
        self.assertEqual(set(self.catalog.items), {12086, 12163, 12183, 12273, 12280,
            12366, 12367, 12368, 12369, 12370, 12416, 12454, 15396})
        self.assertEqual(self.catalog.items[12273]['icon'], 20256)
        terrain = WorldTerrain.load()
        point = self.catalog.destinations['island-dungeon']
        self.assertIs(terrain.can_stand(point.map_id, point.x, point.y), True)
        self.assertNotIn('native:0', self.catalog.destinations)  # heading is not a target
        self.assertEqual(self.catalog.destinations['native:8'].x, 32525)

    def test_groups_preserve_complete_original_rows_and_do_not_share_ordinals(self):
        raw = json.loads(scroll.TABLE.read_text(encoding='utf-8'))
        original = json.loads(Path(raw['native_source']).read_text(encoding='utf-8'))
        self.assertEqual(raw['native_destinations'], original)
        for group, count in ((6, 7), (8, 258), (9, 55), (10, 95), (11, 3)):
            rows = [row for row in raw['native_destinations'] if row['group_id'] == group]
            self.assertEqual(rows, [row for row in original if row['group_id'] == group])
            self.assertEqual(len(rows), count)
        self.assertIsNone(self.catalog.destination_for_native(12273, 0))
        self.assertEqual(self.catalog.destination_for_native(12163, 0).x, 32573)
        self.assertIsNone(self.catalog.destination_for_native(12163, 12))
        self.assertIsNone(self.catalog.destination_for_native(12163, 999))
        self.assertIsNone(self.catalog.destination_for_native(1, 0))

    def test_current_menu_link_and_destination(self):
        self.assertEqual(self.select('teleportURL'), ('lucas2', None))
        self.selection.page = 'lucas2'
        page, point = self.select('island-dungeon')
        self.assertIsNone(page)
        self.assertEqual((point.map_id, point.x, point.y), (0, 32477, 32853))

    def test_bad_selection_or_cancel_never_mutates_policy(self):
        before = replace(self.selection)
        for action in ('cancel', 'close'):
            self.assertEqual(self.select(action), (None, None))
        for values in ({'target_uid': 1}, {'pc_uid': 2}, {'owned_count': 0},
                       {'owned_template': 12366}, {'origin': (0, 1, 1)}):
            with self.assertRaises(ValueError):
                self.select('teleportURL', **values)
        with self.assertRaisesRegex(ValueError, 'NOT_LISTED'):
            self.select('arbitrary-destination')
        self.selection.delivered = False
        with self.assertRaises(ValueError):
            self.select('teleportURL')
        self.selection.delivered = True
        self.assertEqual(before, self.selection)


class KitTests(unittest.TestCase):
    def test_supply_preserves_old_rows_and_only_applies_named_knight(self):
        from tools.local_original_session.world_core_kit import _inventory_kit_frame
        from tools.local_original_session.world_bridge import Context
        from tools.local_original_session.world_extensions import WorldEvents
        from tools.local_original_session.world_registry import build_registry
        from tools.local_original_session.world_visibility import WorldView
        from tools.local_original_session.world_handlers import _starter_fields
        data = game_data.load_m1()
        world = SimpleNamespace(data=data, combat=SimpleNamespace(data=data),
            ground=SimpleNamespace(data=data), events=WorldEvents())
        world.replace_data = MethodType(WorldView.replace_data, world)
        host = SimpleNamespace(_world=world,
            _world_handler_bindings=SimpleNamespace(item_policies=MappingProxyType({})),
            _world_starter_kit='test_knight', INVENTORY_STARTER_FIELDS=_starter_fields(),
            _world_registry=build_registry((feature,)))
        plain = SimpleNamespace(_world_starter_kit='test_knight',
            starter_fields=host.INVENTORY_STARTER_FIELDS,
            fold_sync_hooks=lambda name, value, *args: value)
        ctx = Context(host)
        host._talkscroll_kit_frame = MethodType(feature._talkscroll_kit_frame, ctx)
        # The real host bindings dataclass is required by replace; use its normal factory.
        from tools.local_original_session.world_handlers import HostBindings
        host._world_handler_bindings = HostBindings(None, object(), MappingProxyType({}),
                                                   MappingProxyType({}), 0, None, None)
        feature._talkscroll_initialize(ctx)
        old = inventory.validate_kit_frame(_inventory_kit_frame(plain, 1))
        new = inventory.validate_kit_frame(_inventory_kit_frame(ctx, 1))
        self.assertEqual(new[:-1], old)
        self.assertEqual((new[-1].template_bits, dict(new[-1].raw_fields)[4],
                          dict(new[-1].raw_fields)[7]), (12163, 1, 20018))
        self.assertEqual(dict(new[-1].raw_fields)[5], 133)
        mage_before = inventory.validate_kit_frame(_inventory_kit_frame(plain, 3))
        mage_after = inventory.validate_kit_frame(_inventory_kit_frame(ctx, 3))
        self.assertEqual([(item.template_bits, dict(item.raw_fields)[4]) for item in mage_after],
                         [(item.template_bits, dict(item.raw_fields)[4]) for item in mage_before])
        self.assertEqual([(item.template_bits, dict(item.raw_fields)[4]) for item in mage_after
                          if item.template_bits in ctx._talkscroll_catalog.items], [(12273, 1)])
        self.assertEqual(_inventory_kit_frame(ctx, 0), _inventory_kit_frame(plain, 0))
        host._world_starter_kit = plain._world_starter_kit = None
        self.assertEqual(_inventory_kit_frame(ctx, 1), _inventory_kit_frame(plain, 1))


class NativeRequestTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from tools.local_original_session.world_handlers import _starter_fields
        from tools.local_original_session import attack
        self.field = attack._field
        fields = _starter_fields()
        fields.update({1: 65590, 2: 12273, 4: 20, 5: 133, 7: 20256})
        self.before = inventory.build_kit_frame([fields])
        self.position = SimpleNamespace(map_id=0, word0=32578, word1=32946)
        self.relocations, self.sent, self.drains = [], [], []

        def drain(uid):
            self.drains.append(uid)
            return ()

        async def dispatch(function):
            return function()

        async def send(writer, row, frames, operation_lock):
            self.sent.extend(frames)

        self.host = SimpleNamespace(inventory_frame=self.before,
            _talkscroll_catalog=scroll.load_catalog(), _talkscroll_native=True,
            _world_handler_errors=[], _world_map_exp=0,
            _world=SimpleNamespace(combat=SimpleNamespace(is_dead=lambda uid: False),
                terrain=WorldTerrain.load(lazy_map_ids=(7, 10, 11, 19)), drain=drain,
                runtime=SimpleNamespace(dispatch_now=dispatch)),
            realm=SimpleNamespace(service=lambda writer: SimpleNamespace(snapshot=lambda: self.position),
                                  serves_map=lambda map_id: map_id == 0),
            _world_send=send)
        self.host.broker = self.host

        def relocate(writer, row, game, point, **kwargs):
            self.assertNotIn('same_map_correction', kwargs)
            kwargs['context'].commit_attempted = True
            self.relocations.append(point)
            self.position.map_id, self.position.word0, self.position.word1 = point.map_id, point.x, point.y
            return (b'map-refresh',)

        self.host._world_relocate_locked = relocate

        def context(*args):
            result = SimpleNamespace(pc_uid=1, commit_attempted=False, frames=[],
                                     state=SimpleNamespace(clear=lambda: None))
            result.send_frame = result.frames.append
            return result

        self.context_patch = patch('tools.local_original_session.world_handlers.HostContext', context)
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)

    def frame(self, ordinal, *, extras=(), uid=65590):
        params = b''.join(self.field(key, value) for key, value in
                         ((1, 1), (13, ordinal), (15, 0), (16, 0), *extras))
        # The ordinary existing protobuf envelope (not a fake codec).
        return SimpleNamespace(opcode=0x0960,
            payload=self.field(1, uid) + b'\x12' + bytes((len(params),)) + params)

    async def request(self, ordinal, **kwargs):
        return await feature._talkscroll_request(self.host, object(), {}, object(),
                                                 self.frame(ordinal, **kwargs), object())

    async def test_native_local_list_selection_reuses_same_owned_scroll(self):
        # No preceding 0960/list packet: original UI owns the local group10 list.
        self.assertIn(0x4ed8, feature.OUTGOING_OPCODES)
        self.assertTrue(await self.request(8))
        self.assertTrue(await self.request(7))
        self.assertEqual([(p.map_id, p.x, p.y) for p in self.relocations],
                         [(0, 32525, 32832), (0, 32632, 32962)])
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(dict(inventory.validate_kit_frame(self.before)[0].raw_fields)[4], 20)
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        self.assertEqual(self.sent, [teleport_effect_frame(1), b'map-refresh',
                                     teleport_effect_frame(1), b'map-refresh'])

    async def test_unowned_heading_unknown_or_unsupported_map_do_not_move(self):
        self.assertFalse(await self.request(8, uid=1))
        for ordinal in (0, 9, 999, 11):  # group10 row11 is map4, not a TI hunt target.
            self.assertTrue(await self.request(ordinal))
        self.assertTrue(await self.request(8, extras=((13, 8),)))
        self.assertEqual(self.relocations, [])
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(len(self.sent), 4)
        self.assert_notices()
        self.assertEqual(self.drains, [])
        self.assertTrue(self.host._world_handler_errors)

    def use_hunting_scroll(self):
        fields = dict(inventory.validate_kit_frame(self.before)[0].raw_fields)
        fields.update({2: 12163, 4: 1, 7: 20018})
        self.before = self.host.inventory_frame = inventory.build_kit_frame([fields])

    def assert_notices(self):
        from tools.local_entry_server import protobuf as pb
        self.assertIn(0x4eea, feature.OUTGOING_OPCODES)
        for wire in self.sent:
            self.assertEqual(struct.unpack('<HH', wire[:4]), (len(wire), 0x4eea))
            self.assertEqual(wire[-2:], b'\0\0')
            with pb.parse_message(wire[4:-2]) as parsed:
                self.assertEqual(len(parsed.fields), 2)
                self.assertEqual(parsed.occurrences(1)[0].value, 12066)
                self.assertIn('지원하지 않는 목적지',
                              bytes(parsed.occurrences(2)[0].value).decode('utf-8'))

    async def test_hunting_fields_and_dungeon_entrance_use_exact_original_coordinates(self):
        self.use_hunting_scroll()
        for ordinal in (166, 167, 168, 165):
            self.assertTrue(await self.request(ordinal))
        self.assertEqual([(p.map_id, p.x, p.y) for p in self.relocations],
                         [(0, 32662, 32846), (0, 32412, 33020),
                          (0, 32574, 33100), (0, 32477, 32853)])
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(dict(inventory.validate_kit_frame(self.before)[0].raw_fields)[4], 1)

    async def test_native_same_ordinal_is_resolved_by_current_owned_template(self):
        self.assertTrue(await self.request(0))  # group10 heading: refused
        self.assertEqual(self.relocations, [])
        self.assert_notices()
        self.sent.clear()
        self.use_hunting_scroll()
        self.assertTrue(await self.request(0))  # group8 village: valid
        self.assertEqual([(p.map_id, p.x, p.y) for p in self.relocations], [(0, 32573, 32946)])

    async def test_hunting_scroll_repeats_dungeon_destination_on_same_map_with_effect(self):
        from tools.local_original_session.world_item_effects import teleport_effect_frame
        self.use_hunting_scroll()
        self.host._world_map_exp = 2
        self.host._world.terrain = WorldTerrain.load(map_ids=(0, 1))
        self.host.realm.serves_map = lambda map_id: map_id in (0, 1)
        self.assertTrue(await self.request(13))
        self.assertTrue(await self.request(13))
        self.assertEqual([(p.map_id, p.x, p.y) for p in self.relocations],
                         [(1, 32669, 32811)] * 2)
        self.assertEqual(self.sent, [teleport_effect_frame(1), b'map-refresh'] * 2)

    async def test_map_exp2_activation_reuses_served_map_and_terrain(self):
        self.use_hunting_scroll()
        self.host.realm.serves_map = lambda map_id: map_id in (0, 7, 19)
        for expansion in (0, 1, 3):
            self.host._world_map_exp = expansion
            self.assertTrue(await self.request(19))
        self.assertEqual(self.relocations, [])
        self.assertEqual(self.drains, [])
        self.assert_notices()
        self.sent.clear()
        self.host._world_map_exp = 2
        self.assertTrue(await self.request(19))
        self.assertTrue(await self.request(32))
        self.assertEqual([(p.map_id, p.x, p.y) for p in self.relocations],
                         [(7, 32802, 32727), (19, 32767, 32767)])
        self.assertIs(self.host.inventory_frame, self.before)

    async def test_unsupported_heading_unknown_and_blocked_original_points_only_notify(self):
        self.use_hunting_scroll()
        self.host._world_map_exp = 2
        self.host.realm.serves_map = lambda map_id: map_id in (0, 10, 11)
        for ordinal in (12, 999, 30, 22, 23):
            self.assertTrue(await self.request(ordinal))
        self.assertEqual(self.relocations, [])
        self.assertEqual(self.drains, [])
        self.assertEqual((self.position.map_id, self.position.word0, self.position.word1),
                         (0, 32578, 32946))
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(len(self.sent), 5)
        self.assert_notices()

    async def test_relocation_save_failure_propagates_without_spending_stack(self):
        self.use_hunting_scroll()
        def fail(writer, row, game, destination, **kwargs):
            kwargs['context'].commit_attempted = True
            raise OSError('position save failed')
        self.host._world_relocate_locked = fail
        with self.assertRaises(OSError):
            await self.request(166)
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(self.sent, [])


if __name__ == '__main__':
    unittest.main()
