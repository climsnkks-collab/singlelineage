"""Development unit checks only; these are not native-client/UI PASS claims."""
from dataclasses import replace
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
        self.assertEqual(set(self.catalog.items), {12273, 12366, 12367, 12368, 12369, 12370, 12416})
        self.assertEqual(self.catalog.items[12273]['icon'], 20256)
        terrain = WorldTerrain.load()
        for point in self.catalog.destinations.values():
            if point.map_id == 0:
                self.assertIs(terrain.can_stand(point.map_id, point.x, point.y), True)
        self.assertNotIn('native:0', self.catalog.destinations)  # heading is not a target
        self.assertEqual(self.catalog.destinations['native:8'].x, 32525)

    def test_current_menu_link_and_destination(self):
        self.assertEqual(self.select('teleportURL'), ('lucas2', None))
        self.selection.page = 'lucas2'
        page, point = self.select('island-dungeon')
        self.assertIsNone(page)
        self.assertEqual((point.map_id, point.x, point.y), (0, 32478, 32853))

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
                          dict(new[-1].raw_fields)[7]), (12273, 1, 20256))
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
        self.relocations, self.sent = [], []

        async def dispatch(function):
            return function()

        async def send(writer, row, frames, operation_lock):
            self.sent.extend(frames)

        self.host = SimpleNamespace(inventory_frame=self.before,
            _talkscroll_catalog=scroll.load_catalog(), _talkscroll_native=True,
            _world_handler_errors=[], _world_map_exp=0,
            _world=SimpleNamespace(combat=SimpleNamespace(is_dead=lambda uid: False),
                terrain=WorldTerrain.load(), drain=lambda uid: (),
                runtime=SimpleNamespace(dispatch_now=dispatch)),
            realm=SimpleNamespace(service=lambda writer: SimpleNamespace(snapshot=lambda: self.position),
                                  serves_map=lambda map_id: map_id == 0),
            _world_send=send)
        self.host.broker = self.host

        def relocate(writer, row, game, point, **kwargs):
            self.assertIs(kwargs['same_map_correction'], True)
            kwargs['context'].commit_attempted = True
            self.relocations.append(point)
            self.position.map_id, self.position.word0, self.position.word1 = point.map_id, point.x, point.y
            return (b'correction',)

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
        self.assertTrue(await self.request(8))
        self.assertTrue(await self.request(7))
        self.assertEqual([(p.map_id, p.x, p.y) for p in self.relocations],
                         [(0, 32525, 32832), (0, 32632, 32962)])
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(dict(inventory.validate_kit_frame(self.before)[0].raw_fields)[4], 20)
        self.assertEqual(self.sent, [b'correction', b'correction'])

    async def test_unowned_heading_unknown_or_unsupported_map_do_not_move(self):
        self.assertFalse(await self.request(8, uid=1))
        for ordinal in (0, 9, 999, 11):  # group10 row11 is map4, not a TI hunt target.
            self.assertTrue(await self.request(ordinal))
        self.assertTrue(await self.request(8, extras=((13, 8),)))
        self.assertEqual(self.relocations, [])
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.host._world_handler_errors)

    async def test_relocation_save_failure_propagates_without_spending_stack(self):
        def fail(writer, row, game, destination, **kwargs):
            kwargs['context'].commit_attempted = True
            raise OSError('position save failed')
        self.host._world_relocate_locked = fail
        with self.assertRaises(OSError):
            await self.request(8)
        self.assertIs(self.host.inventory_frame, self.before)
        self.assertEqual(self.sent, [])


if __name__ == '__main__':
    unittest.main()
