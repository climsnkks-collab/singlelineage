"""Pure fake-Context tests using existing real codecs; no broker/native imports."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from tools.local_original_session import world_handlers as h
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_shop import InventoryItem, InventorySnapshot, Purchase
from tools.local_original_session.world_town import TownConfig, TownNpcs, load_town
from tools.local_world_protocol import model as world_wire

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'work/local_original_session/implementation-4/shop-quest/dialogue-contract'


def _load(name, path):
    # Reuse a single canonical instance: the existing modules use bare imports.
    existing = sys.modules.get(name)
    if existing is not None:
        if Path(existing.__file__).resolve() != path.resolve():
            raise RuntimeError('TEST_CODEC_MODULE_IDENTITY_MISMATCH')
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


click = _load('dialogue_route', CONTRACT / 'dialogue_route.py')
dialogue = _load('dialogue_wire_f4', CONTRACT / 'hypertext-field4/dialogue_wire_f4.py')
lists = _load('shop_list_wire', CONTRACT / 'shop-list-wire/shop_list_wire.py')
trade = _load('trade_request_wire', CONTRACT / 'trade-request-wire/trade_request_wire.py')
WIRES = h.WireBindings(click, dialogue, lists, trade)


def frame(opcode, body):
    return (len(body) + 6).to_bytes(2, 'little') + opcode.to_bytes(2, 'little') + body + b'\0\0'


class FakeStore:
    def __init__(self):
        self.value = h.TradeSnapshot(InventorySnapshot(1000, 2, 0, 1800, {14: 5}),
                                     (InventoryItem(101, 14, 5, 1),), object())
        self.commits = []
        self.reject = False
        # Opaque already-produced reply fixture. The store owner, not handlers,
        # chooses reply kinds. This asserts unchanged append order only.
        self.frames = (frame(0x4E95, world_wire.encode_payload(
            0x4E95, {1: 0, 2: 17, 3: False, 4: False})),)

    def snapshot(self, pc_uid, now):
        return self.value

    async def commit(self, pc_uid, snapshot, window, request, proposal, now):
        if self.reject:
            raise ValueError('FAKE_STORE_REVISION_CHANGED')
        if snapshot is not self.value:
            raise ValueError('FAKE_STORE_REVISION_CHANGED')
        self.commits.append((pc_uid, snapshot, window, request, proposal, now))
        self.value = replace(snapshot, inventory=replace(snapshot.inventory, adena=proposal.adena_after),
                             revision=object())
        return self.frames


class FakeContext:
    def __init__(self, data):
        entities = EntityRegistry()
        self.world = SimpleNamespace(entities=entities)
        self.town = TownNpcs(entities, data, TownConfig(candidate_npc_ids={70014, 70523}))
        self.town.register()
        self.npc = next(entity for entity in entities if self.town.npc_for(entity.uid).npc_id == 70014)
        self.pc_uid = 1
        entities.add(Kind.PC, self.npc.map_id, self.npc.x, self.npc.y, uid=self.pc_uid)
        self.store, self.wire, self.state = FakeStore(), WIRES, h.HandlerState()
        self.interaction_distance = 1
        self.frames, self.calls = [], []
        self.menu_source, self.list_source = object(), object()
        self.live_sources = {self.menu_source, self.list_source}
        self.mode = h.BUY
        self.accepted = True
        self.move_to = None
        self.move_frames = ()

    def now(self):
        return 123.5

    def send_frame(self, value):
        self.frames.append(value)

    def current_source(self, source):
        return source in self.live_sources

    def dialogue_for(self, interaction, now):
        self.calls.append(('dialogue', interaction, now))
        uid = interaction.ref.uid
        target = uid if uid < (1 << 31) else uid - (1 << 32)
        # Explicit resource-owner test fixture, not a Pandora resource mapping.
        return h.Dialogue({1: target, 2: b'pixel', 4: (-7, 9), 5: (b'fixture',)}, self.menu_source)

    def shop_action(self, interaction, menu, fields, now):
        self.calls.append(('action', interaction, menu, fields, now))
        if fields[2] != b'explicit-owner-fixture-action':
            raise ValueError('FAKE_UNKNOWN_MENU_ACTION')
        if self.mode == h.BUY:
            offer = next(o for o in interaction.shop_listing.offers if o.classic_item_id == 14)
            # Every unknown wire operand is explicit fixture content, not zero
            # supplied by handlers or an asserted original producer value.
            row = lists.Value('BuyListItem', (
                (1, -2147483647), (2, offer.classic_item_id), (3, offer.icon_id),
                (4, offer.selling_price), (5, offer.name_token.encode('ascii')),
                (6, 11), (7, 12), (8, -13)))
            value = lists.Value(lists.BUY, ((1, -2), (2, 23), (3, (row,))))
            return h.ShopWindow(h.BUY, value, {0x80000001: offer.key}, self.list_source)
        row = lists.Value('SellListItem', ((1, -10), (2, 19)))
        value = lists.Value(lists.SELL, ((1, -2), (2, 23), (3, (row,))))
        return h.ShopWindow(h.SELL, value, {0xfffffff6: 101}, self.list_source)

    async def move(self, payload, now):
        self.calls.append(('move', payload, now))
        if self.accepted and self.move_to is not None:
            self.world.entities.move(self.pc_uid, *self.move_to)
        return h.MovementResult(self.accepted, self.move_frames)

    async def transition(self, destination, now):
        self.calls.append(('transition', destination, now))
        self.world.entities.move(self.pc_uid, destination.map_id, destination.x,
                                 destination.y, destination.heading)
        # Actual existing world encoder, with all otherwise-unknown fixture
        # operands explicit. Production transition callback remains unimplemented.
        body = world_wire.encode_payload(0x4E95, {
            1: destination.map_id, 2: 17, 3: False, 4: False})
        return (frame(0x4E95, body),)


class WorldHandlersTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_town()

    def setUp(self):
        self.ctx = FakeContext(self.data)

    async def open_menu(self):
        target = self.ctx.npc.uid
        target = target if target < (1 << 31) else target - (1 << 32)
        self.assertTrue(await h.dispatch(self.ctx, h.CLICK, click.encode_request(target)))

    async def open_window(self, mode=h.BUY):
        await self.open_menu()
        self.ctx.mode = mode
        body = dialogue.encode_haction_normal(self.ctx.state.menu.fields[1],
                b'explicit-owner-fixture-action', None, (self.ctx.npc.x, self.ctx.npc.y))
        self.assertTrue(await h.dispatch(self.ctx, h.HACTION, body))

    def request(self, *, mode=None, context=0xfffffffe, key=None, count=2):
        mode = self.ctx.mode if mode is None else mode
        key = (0x80000001 if mode == h.BUY else 0xfffffff6) if key is None else key
        return trade.encode_normal(trade.Request(context, mode, (trade.Item(key, count),),
                                                self.ctx.npc.x, self.ctx.npc.y))

    async def test_registry_unknown_opcode_has_no_effect(self):
        self.assertEqual(set(h.HANDLERS), {0x4E2B, 0x4E43, 0x4ED4, 0x4ED1, 0x0960})
        self.assertFalse(await h.dispatch(self.ctx, 0x1234, b''))
        self.assertEqual((self.ctx.frames, self.ctx.calls), ([], []))

    async def test_click_only_emits_exact_real_dialogue_with_signed_f4(self):
        await self.open_menu()
        menu = self.ctx.state.menu
        expected = frame(h.HYPERTEXT, dialogue.encode(h.HYPERTEXT, dict(menu.fields)))
        self.assertEqual(self.ctx.frames, [expected])
        self.assertEqual(dialogue.decode(h.HYPERTEXT, expected[4:-2])[4], (-7, 9))
        self.assertIsNone(self.ctx.state.window)
        self.assertEqual([call[0] for call in self.ctx.calls], ['dialogue'])
        self.assertEqual(self.ctx.state.interaction.shop_listing.unavailable,
                         self.ctx.town.route_click(self.ctx.npc.uid,
                            player_map_id=0, player_x=self.ctx.npc.x,
                            player_y=self.ctx.npc.y, max_distance=1).shop_listing.unavailable)

    async def test_buy_action_emits_real_4e48_after_4e44(self):
        await self.open_window()
        window = self.ctx.state.window
        self.assertEqual(self.ctx.frames, [
            frame(h.HYPERTEXT, dialogue.encode(h.HYPERTEXT, dict(self.ctx.state.menu.fields))),
            frame(h.BUY_LIST, lists.encode(lists.BUY, window.value))])
        self.assertEqual(lists.decode(lists.BUY, h.BUY_LIST, self.ctx.frames[-1][4:-2]), window.value)
        self.assertEqual([call[0] for call in self.ctx.calls], ['dialogue', 'action'])

    async def test_buy_real_4ed1_uses_row_identity_and_committed_frames(self):
        await self.open_window()
        before = list(self.ctx.frames)
        await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual(self.ctx.frames, before + list(self.ctx.store.frames))
        commit = self.ctx.store.commits[0]
        self.assertEqual((commit[0], commit[-1]), (1, 123.5))
        self.assertIsInstance(commit[4], Purchase)
        self.assertEqual((commit[4].cost, commit[4].adena_after, commit[4].grants[0].count), (74, 926, 2))
        self.assertIsNone(self.ctx.state.window)
        with self.assertRaisesRegex(h.HandlerError, 'CURRENT_SHOP_WINDOW_REQUIRED'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual(len(self.ctx.store.commits), 1)

    async def test_sell_real_4ee7_and_4ed1_resolve_owned_uid(self):
        await self.open_window(h.SELL)
        window = self.ctx.state.window
        self.assertEqual(self.ctx.frames[-1], frame(h.SELL_LIST, lists.encode(lists.SELL, window.value)))
        before = list(self.ctx.frames)
        await h.dispatch(self.ctx, h.TRADE, self.request())
        proposal = self.ctx.store.commits[0][4]
        self.assertEqual((proposal.proceeds, proposal.adena_after, proposal.removals), (38, 1038, ((101, 2),)))
        self.assertEqual(self.ctx.frames, before + list(self.ctx.store.frames))

    async def test_action_and_trade_cannot_skip_menu_sequence(self):
        with self.assertRaisesRegex(h.HandlerError, 'CURRENT_MENU_REQUIRED'):
            await h.dispatch(self.ctx, h.HACTION, dialogue.encode_haction_normal(1, b'buy', None, None))
        await self.open_menu()
        before = list(self.ctx.frames)
        with self.assertRaisesRegex(h.HandlerError, 'CURRENT_SHOP_WINDOW_REQUIRED'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual(self.ctx.frames, before)

    async def test_mismatch_context_mode_unknown_row_and_stale_source_do_not_commit(self):
        await self.open_window()
        before = list(self.ctx.frames)
        for body, error in ((self.request(context=1), 'SHOP_LIST_CONTEXT_MISMATCH'),
                            (self.request(mode=h.SELL), 'SHOP_LIST_CONTEXT_MISMATCH'),
                            (self.request(key=999), 'UNKNOWN_SHOP_ROW')):
            with self.assertRaisesRegex(h.HandlerError, error):
                await h.dispatch(self.ctx, h.TRADE, body)
        self.ctx.live_sources.remove(self.ctx.list_source)
        with self.assertRaisesRegex(h.HandlerError, 'CURRENT_SHOP_LIST_SOURCE_REQUIRED'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual((self.ctx.frames, self.ctx.store.commits), (before, []))

    async def test_live_npc_generation_and_range_are_rechecked(self):
        await self.open_window()
        before = list(self.ctx.frames)
        self.ctx.world.entities.move(self.ctx.pc_uid, 0, 1, 1)
        with self.assertRaisesRegex(ValueError, 'TOWN_TARGET_OUT_OF_RANGE'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.ctx.world.entities.remove(self.ctx.npc.uid)
        with self.assertRaisesRegex(h.HandlerError, 'STALE_NPC_REFERENCE'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual((self.ctx.frames, self.ctx.store.commits), (before, []))

    async def test_calculation_or_commit_failure_does_not_emit_success(self):
        await self.open_window()
        before = list(self.ctx.frames)
        self.ctx.store.value = replace(self.ctx.store.value,
            inventory=replace(self.ctx.store.value.inventory, adena=1))
        with self.assertRaisesRegex(ValueError, 'INSUFFICIENT_ADENA'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual(self.ctx.store.commits, [])
        self.ctx.store.value = replace(self.ctx.store.value,
            inventory=replace(self.ctx.store.value.inventory, adena=1000))
        self.ctx.store.reject = True
        with self.assertRaisesRegex(ValueError, 'FAKE_STORE_REVISION_CHANGED'):
            await h.dispatch(self.ctx, h.TRADE, self.request())
        self.assertEqual(self.ctx.frames, before)

    async def test_rejected_move_cannot_trigger_stairs_even_on_trigger_cell(self):
        self.ctx.world.entities.move(1, 0, 32477, 32851)
        self.ctx.accepted = False
        await h.dispatch(self.ctx, h.MOVE, b'host-decoded-only')
        self.assertEqual([call[0] for call in self.ctx.calls], ['move'])
        self.assertEqual(self.ctx.frames, [])

    async def test_accepted_move_checks_live_destination_and_preserves_reply_order(self):
        await self.open_window()
        self.ctx.move_to = (0, 32477, 32851)
        self.ctx.move_frames = tuple(self.ctx.frames[:1])
        self.ctx.frames.clear()
        await h.dispatch(self.ctx, h.MOVE, b'host-decoded-only')
        destination = self.ctx.calls[-1][1]
        self.assertEqual((destination.map_id, destination.x, destination.y, destination.heading),
                         (1, 32669, 32802, 4))
        expected = frame(0x4E95, world_wire.encode_payload(0x4E95,
                         {1: 1, 2: 17, 3: False, 4: False}))
        self.assertEqual(self.ctx.frames, list(self.ctx.move_frames) + [expected])
        self.assertIsNone(self.ctx.state.menu)
        self.assertEqual(world_wire.decode_payload(0x4E95, expected[4:-2])[1], 1)

    async def test_accepted_move_outside_trigger_does_not_transition(self):
        self.ctx.move_to = (0, 32477, 32853)
        await h.dispatch(self.ctx, h.MOVE, b'host-decoded-only')
        self.assertEqual([call[0] for call in self.ctx.calls], ['move'])
        self.assertEqual(self.ctx.frames, [])


if __name__ == '__main__':
    unittest.main()
