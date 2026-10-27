"""Development-only host adapter tests; real codecs/kit DTOs, no game or port."""
import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, world_handlers as h
from tools.local_original_session.game_data import load_items
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_town import TownConfig, TownNpcs, load_town


class MemoryKitStore:
    def __init__(self, frame):
        self.frame, self.calls, self.fail = frame, [], False

    def replace_kit(self, uid, old, new, *, append):
        if self.fail:
            raise OSError('TEST_SAVE_FAILURE')
        assert append is True and self.frame == old
        self.calls.append((uid, old, new, append))
        self.frame = new
        return True


class ResourceFixture:
    """Explicit development resource producer, not a Classic NPC correspondence."""
    def __init__(self, uid, reply):
        self.policy = SimpleNamespace(spawn=SimpleNamespace(uid=uid),
            response_fields=((1, uid), (2, b'pixel')), command=b'buy',
            replies=(SimpleNamespace(source=SimpleNamespace(value=reply)),),
            listing=SimpleNamespace(reply_index=0))

    def current(self, *, cold=False):
        return True


class HostAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.entities = EntityRegistry()
        self.town = TownNpcs(self.entities, load_town(), TownConfig(candidate_npc_ids={70014}))
        self.town.register()
        self.npc = next(e for e in self.entities if self.town.npc_for(e.uid).npc_id == 70014)
        self.entities.add(Kind.PC, self.npc.map_id, self.npc.x, self.npc.y, uid=1)
        self.bindings = h.prepare_host_bindings(self.town)
        self.wire = self.bindings.wire
        self.offer = next(o for o in self.town.data.shops.offers.values()
                          if o.key[0] == 70014 and o.classic_item_id == 14)
        rows = []
        for uid, template, quantity in ((101, 7, 1000), (102, 1, 1)):
            fields = dict(self.bindings.item_policies[template].grant_fields)
            fields.update({1: uid, 4: quantity})
            rows.append(fields)
        initial = inventory.build_kit_frame(rows)
        self.writer = object()
        self.lock = asyncio.Lock()
        await self.lock.acquire()
        self.row = {'writer': self.writer, 'operation_lock': self.lock}
        self.store = MemoryKitStore(initial)
        self.position = SimpleNamespace(uid=1)
        definitions = load_items()
        equipment = SimpleNamespace(weapon_uid=102, slots=())
        effect = SimpleNamespace(_defs=definitions,
            store=SimpleNamespace(restore=lambda uid, frame: equipment))
        self.broker = SimpleNamespace(_world=SimpleNamespace(entities=self.entities),
            _world_warehouse_trade=lambda *_: False,
            _world_pcs={id(self.writer): (self.writer, 1)},
            _world_handler_bindings=self.bindings, _inventory_current_frame=initial,
            _inventory_store=self.store, _item_equipment_effect=effect,
            realm=SimpleNamespace(service=lambda writer: SimpleNamespace(snapshot=lambda: self.position)),
            _world_pc_profile=lambda writer, pos: SimpleNamespace(strength=13, con=10))

    async def asyncTearDown(self):
        self.lock.release()

    def context(self):
        return h.HostContext(self.broker, self.writer, self.row, object(), self.lock)

    def bind_resource(self, *, sell=False, sell_uid=103):
        lists = self.wire.lists
        if sell:
            self.resource = ResourceFixture(self.npc.uid, lists.Value(lists.SELL, (
                (1, self.npc.uid), (2, 0),
                (3, (lists.Value('SellListItem', ((1, 77), (2, 3))),)))))
            self.resource.policy.command = b'sell'
            keys = {77: sell_uid}
        else:
            member = lists.Value('BuyListItem', ((1, 77), (2, 14),
                (3, self.offer.icon_id), (4, self.offer.selling_price),
                (5, self.offer.name_token.encode()), (6, 0), (7, 0), (8, 0)))
            self.resource = ResourceFixture(self.npc.uid, lists.Value(lists.BUY,
                ((1, self.npc.uid), (2, 0), (3, (member,)))))
            keys = {77: self.offer.key}
        source = h.HostNpcSource.from_resource(self.resource, self.town.npc_for(self.npc.uid).key, keys)
        self.broker._world_handler_bindings = replace(self.bindings, sources={source.placement_key: source})

    async def open_list(self, *, delivered=True):
        ctx = self.context()
        await h.dispatch(ctx, h.CLICK, self.wire.click.encode_request(self.npc.uid))
        self.assertEqual(int.from_bytes(ctx.frames[0][2:4], 'little'), h.HYPERTEXT)
        ctx.mark_delivered()
        ctx = self.context()
        payload = self.wire.dialogue.encode_haction_normal(self.npc.uid,
                    self.resource.policy.command, None, (0, 0))
        await h.dispatch(ctx, h.HACTION, payload)
        if delivered:
            ctx.mark_delivered()
        return ctx

    def trade(self, mode, quantity):
        codec = self.wire.trade
        return codec.encode_normal(codec.Request(self.npc.uid, mode,
                                                  (codec.Item(77, quantity),), 0, 0))

    async def test_default_unmapped_dialogue_refuses(self):
        ctx = self.context()
        with self.assertRaisesRegex(h.HandlerError, 'CLASSIC_MENU_SOURCE_UNAVAILABLE'):
            await h.dispatch(ctx, h.CLICK, self.wire.click.encode_request(self.npc.uid))
        self.assertEqual(ctx.frames, [])

    async def test_buy_and_sell_save_before_exact_inventory_replies(self):
        self.bind_resource()
        await self.open_list()
        ctx = self.context()
        # Startup warmed actual codec sources; no source reads during dispatch.
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('request source IO')):
            await h.dispatch(ctx, h.TRADE, self.trade(h.BUY, 3))
        self.assertEqual(len(self.store.calls), 1)
        self.assertEqual(self.broker._inventory_current_frame, self.store.frame)
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in ctx.frames], [0x0965, 0x0964])
        values = {i.template_bits: dict(i.raw_fields) for i in inventory.validate_kit_frame(self.store.frame)}
        self.assertEqual(values[14][4], 3)
        self.assertEqual(values[7][4], 1000 - 3 * self.offer.selling_price)
        self.bind_resource(sell=True)
        await self.open_list()
        ctx = self.context()
        await h.dispatch(ctx, h.TRADE, self.trade(h.SELL, 3))
        self.assertEqual(len(self.store.calls), 2)
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in ctx.frames], [0x0965, 0x0978])
        self.assertNotIn(14, {i.template_bits for i in inventory.validate_kit_frame(self.store.frame)})

    async def test_list_must_drain_and_save_failure_cannot_replay(self):
        self.bind_resource()
        list_ctx = await self.open_list(delivered=False)
        ctx = self.context()
        with self.assertRaisesRegex(h.HandlerError, 'DRAINED_CURRENT_SHOP_LIST_REQUIRED'):
            await h.dispatch(ctx, h.TRADE, self.trade(h.BUY, 1))
        self.assertEqual(self.store.calls, [])
        list_ctx.mark_delivered()
        ctx = self.context()
        self.assertFalse(ctx.commit_attempted)
        self.store.fail = True
        with self.assertRaisesRegex(OSError, 'TEST_SAVE_FAILURE'):
            await h.dispatch(ctx, h.TRADE, self.trade(h.BUY, 1))
        self.assertTrue(ctx.commit_attempted)
        self.assertEqual(ctx.frames, [])
        with self.assertRaisesRegex(h.HandlerError, 'CURRENT_SHOP_WINDOW_REQUIRED'):
            await h.dispatch(self.context(), h.TRADE, self.trade(h.BUY, 1))

    async def test_snapshot_change_refuses(self):
        self.bind_resource()
        await self.open_list()
        self.broker._inventory_current_frame = bytes(bytearray(self.store.frame))
        with self.assertRaisesRegex(h.HandlerError, 'CURRENT_SHOP_INVENTORY_CHANGED'):
            await h.dispatch(self.context(), h.TRADE, self.trade(h.BUY, 1))
        self.assertEqual(self.store.calls, [])

    async def test_equipped_sale_refuses_and_stack_purchase_updates(self):
        self.bind_resource(sell=True, sell_uid=102)
        await self.open_list()
        with self.assertRaisesRegex(ValueError, 'ITEM_NOT_PURCHASEABLE'):
            await h.dispatch(self.context(), h.TRADE, self.trade(h.SELL, 1))
        self.assertEqual(self.store.calls, [])
        self.bind_resource()
        await self.open_list()
        await h.dispatch(self.context(), h.TRADE, self.trade(h.BUY, 1))
        await self.open_list()
        ctx = self.context()
        await h.dispatch(ctx, h.TRADE, self.trade(h.BUY, 2))
        self.assertEqual([int.from_bytes(f[2:4], 'little') for f in ctx.frames], [0x0965, 0x0965])
        rows = inventory.validate_kit_frame(self.store.frame)
        potion, = [row for row in rows if row.template_bits == 14]
        self.assertEqual((potion.identifier, dict(potion.raw_fields)[4]), (103, 3))

    async def test_movement_delegates_to_original_host(self):
        calls = []
        def move(writer, row, game, payload, now, context):
            self.assertIs(context, ctx)
            calls.append((writer, row, payload))
            return h.MovementResult(False, ())
        self.broker._world_move_for_handler = move
        ctx = self.context()
        await h.dispatch(ctx, h.MOVE, b'host-decoder-body')
        self.assertEqual(calls, [(self.writer, self.row, b'host-decoder-body')])
        self.assertEqual(ctx.frames, [])

    async def test_unsupported_click_clears_source_list_and_keeps_row_lifecycle(self):
        self.bind_resource()
        pending_list = await self.open_list(delivered=False)
        slot = self.row['_world_handler_state']
        ctx = self.context()
        with self.assertRaisesRegex(ValueError, 'TOWN_TARGET_NOT_CURRENT'):
            await h.dispatch(ctx, h.CLICK, self.wire.click.encode_request(self.npc.uid + 9999))
        self.assertIs(self.row['_world_handler_state'], slot)
        self.assertIs(ctx.sources, slot[2])
        self.assertEqual(ctx.sources, [])
        self.assertIsNone(ctx.state.menu)
        self.assertEqual(ctx.frames, [])
        with self.assertRaisesRegex(h.HandlerError, 'DRAINED_SOURCE_CHANGED'):
            pending_list.mark_delivered()


if __name__ == '__main__':
    unittest.main()
