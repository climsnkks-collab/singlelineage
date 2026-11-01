"""LOCAL default town handlers with real temporary saves; no socket or client.

These are development calls through dispatch/HostContext. mark_delivered is a
fixture boundary, not a real network drain or a native UI PASS.
"""
import asyncio
from pathlib import Path
import tempfile
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import inventory, inventory_store
from tools.local_original_session import world_bridge, world_feature_town as town
from tools.local_original_session import world_handlers as h, world_core_kit
from tools.local_original_session.game_data import load_items
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_original_session.world_extensions import RuntimeExtensions, WorldEvents
from tools.local_original_session.world_state_services import InventoryTransactions


class DefaultTownAssetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict('os.environ', {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.profile = Path(self.temp.name) / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('TownAssets', 0, 0, (13,) * 6))
        self.store = self.fresh_store()
        self.writer, self.lock = object(), asyncio.Lock()
        await self.lock.acquire()
        self.addCleanup(self.lock.release)
        self.row = dict(writer=self.writer, operation_lock=self.lock)
        self.position = SimpleNamespace(uid=1)
        world = SimpleNamespace(entities=EntityRegistry(), extensions={}, events=WorldEvents(),
            runtime_extensions=RuntimeExtensions(), data=SimpleNamespace(items=load_items()),
            combat=SimpleNamespace(pcs={1: SimpleNamespace(profile=SimpleNamespace(level=5))},
                                   regen_tick=lambda uid: None), drain=lambda uid: ())
        self.broker = SimpleNamespace(_world=world,
            _world_registry=h.build_registry((town,)),
            _world_options={'world_handler_sources': ()},
            _world_handler_bindings=h.empty_host_bindings(),
            _world_pcs={id(self.writer): (self.writer, 1)},
            _inventory_store=self.store, _world_inventory_transactions=InventoryTransactions(self.store),
            _item_equipment_effect=None, INVENTORY_STARTER_FIELDS=h._starter_fields(),
            realm=SimpleNamespace(service=lambda writer: SimpleNamespace(snapshot=lambda: self.position)),
            _world_pc_profile=lambda writer, pos: SimpleNamespace(strength=13, con=13),
            _world_stats_for=lambda pos, **kw: (SimpleNamespace(max_weight=10000), (), {}))
        extension = world_bridge.Context(self.broker)
        for function in town.METHODS:
            setattr(self.broker, function.__name__, MethodType(function, extension))
        self.broker._world_replace_kit = MethodType(world_core_kit._world_replace_kit, extension)
        # Actual town initializer, with both env settings absent.
        self.broker._world_town_initialize()
        self.addCleanup(world.events.emit, 'close')
        self.addCleanup(self.broker._world_inn_runtime_stopped)
        self.entities = world.entities
        self.entities.add(Kind.PC, 0, 32577, 32946, uid=1)
        initial = self.kit((101, 7, 1000), (102, 14, 10), (103, 15, 5))
        self.store.grant(1, initial)
        self.broker._inventory_current_frame = initial

    def fresh_store(self):
        return inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                               kit_policy=inventory.KIT_POLICY)

    def kit(self, *rows):
        policies = self.broker._world_handler_bindings.item_policies
        return inventory.build_kit_frame([{**policies[t].grant_fields, 1: u, 4: q}
                                           for u, t, q in rows])

    def context(self):
        return h.HostContext(self.broker, self.writer, self.row, True, self.lock)

    def saved(self):
        return {r.template_bits: dict(r.raw_fields)
                for r in inventory.validate_kit_frame(self.store.restore(1))}

    async def open(self, npc_id, action):
        npc = next(e for e in self.entities if self.broker._world.town.npc_for(e.uid)
                   and self.broker._world.town.npc_for(e.uid).npc_id == npc_id)
        self.entities.move(1, npc.map_id, npc.x, npc.y)
        ctx = self.context()
        await h.dispatch(ctx, h.CLICK, ctx.wire.click.encode_request(npc.uid))
        ctx.mark_delivered()
        ctx = self.context()
        await h.dispatch(ctx, h.HACTION, ctx.wire.dialogue.encode_haction_normal(
            npc.uid, action.encode(), None, (0, 0)))
        ctx.mark_delivered()
        return ctx

    async def close(self):
        ctx = self.context()
        await h.dispatch(ctx, 0x097B, b'')
        self.assertNotIn('_world_warehouse_window', self.row)

    async def bank_trade(self, selections):
        window = self.row['_world_warehouse_window']
        pb = inventory.pb
        field = lambda n, v: pb.encode_varint(n << 3) + pb.encode_varint(v)
        body = field(1, window['context']) + field(2, window['mode'])
        for key, count in selections:
            body += pb.encode_bytes(3, field(1, key) + field(2, count))
        ctx = self.context()
        await h.dispatch(ctx, h.TRADE, body + field(4, 0) + field(5, 0))
        return ctx

    def scalar_fields(self, frame):
        with inventory.pb.parse_message(frame[4:-2]) as parsed:
            return {f.number: f.value for f in parsed.fields if f.wire_type == 0}

    async def test_default_shop_buy_sell_and_fresh_restore(self):
        ctx = await self.open(70014, 'buy')
        window = ctx.state.window
        self.assertEqual(dict(window.value.fields)[2], 7)
        for child in dict(window.value.fields)[3]:
            values = dict(child.fields)
            self.assertEqual([values[n] for n in (6, 7, 8)], [0, 0, 0])
        key = next(k for k, offer in window.rows.items()
                   if self.broker._world.town.data.shops.offers[offer].classic_item_id == 14)
        codec = ctx.wire.trade
        await h.dispatch(self.context(), h.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 5, (codec.Item(key, 2),), 0, 0)))
        self.assertEqual((self.saved()[7][4], self.saved()[14][4]), (926, 12))
        await self.close()
        ctx = await self.open(70014, 'sell')
        window = ctx.state.window
        key = next(k for k, uid in window.rows.items() if uid == 102)
        await h.dispatch(self.context(), h.TRADE, codec.encode_normal(codec.Request(
            dict(window.value.fields)[1], 6, (codec.Item(key, 2),), 0, 0)))
        self.assertEqual((self.saved()[7][4], self.saved()[14][4]), (964, 10))
        fresh = self.fresh_store()
        self.assertEqual(fresh.restore(1), self.store.restore(1))
        self.assertIsNone(InventoryTransactions(fresh).restore_warehouse(1))

    async def test_default_warehouse_dynamic_count_two_rows_fee_and_fresh_restore(self):
        ctx = await self.open(60001, 'deposit')
        self.assertEqual(self.scalar_fields(ctx.frames[-1]), {1: 0, 2: 1, 3: 150, 4: 1})
        await self.bank_trade(((102, 4), (103, 3)))
        await self.close()
        ctx = await self.open(60001, 'deposit')
        self.assertEqual(self.scalar_fields(ctx.frames[-1])[1], 2)
        await self.close()
        ctx = await self.open(60001, 'retrieve')
        values = self.scalar_fields(ctx.frames[-1])
        self.assertEqual(tuple(values[n] for n in (2, 3, 4, 5, 6)), (2, 1, 7, 30, 150))
        bank = InventoryTransactions(self.fresh_store()).restore_warehouse(1)
        self.assertEqual(len(inventory.validate_kit_frame(bank)), 2)
        await self.bank_trade(((0, 2), (1, 1)))
        self.assertEqual((self.saved()[7][4], self.saved()[14][4], self.saved()[15][4]),
                         (940, 8, 3))
        await self.close()
        ctx = await self.open(60001, 'retrieve')
        self.assertEqual(self.scalar_fields(ctx.frames[-1])[2], 2)
        await self.bank_trade(((0, 2), (1, 2)))
        fresh = self.fresh_store()
        self.assertEqual(fresh.restore(1), self.store.restore(1))
        self.assertIsNone(InventoryTransactions(fresh).restore_warehouse(1))
        await self.close()
        ctx = await self.open(60001, 'retrieve')
        self.assertEqual(self.scalar_fields(ctx.frames[-1])[2], 0)

    async def test_withdraw_exact_fee_and_insufficient_balance_preserves_both_saves(self):
        await self.open(60001, 'deposit')
        await self.bank_trade(((102, 4), (103, 3)))
        await self.close()
        before = self.store.restore(1)
        rows = [dict(r.raw_fields) for r in inventory.validate_kit_frame(before)]
        rows[0][4] = 59
        low = inventory.build_kit_frame(rows)
        self.broker._world_inventory_transactions.commit_inventory(1, before, low)
        self.broker._inventory_current_frame = low
        await self.open(60001, 'retrieve')
        bank_before = self.broker._world_inventory_transactions.restore_warehouse(1)
        with self.assertRaisesRegex(ValueError, '^INSUFFICIENT_ADENA$'):
            await self.bank_trade(((0, 1), (1, 1)))
        self.assertEqual(self.store.restore(1), low)
        self.assertEqual(InventoryTransactions(self.fresh_store()).restore_warehouse(1), bank_before)
        await self.close()
        rows[0][4] = 60
        exact = inventory.build_kit_frame(rows)
        self.broker._world_inventory_transactions.commit_inventory(1, low, exact)
        self.broker._inventory_current_frame = exact
        await self.open(60001, 'retrieve')
        await self.bank_trade(((0, 1), (1, 1)))
        self.assertNotIn(7, self.saved())
        self.assertEqual(self.fresh_store().restore(1), self.store.restore(1))


class ConfigurationTests(unittest.TestCase):
    def test_warehouse_default_blank_disabled_and_feature_send_registration(self):
        for value in (None, '', '  ', '1', '0', 'off', 'OFF'):
            with self.subTest(value=value), patch.dict('os.environ', {}, clear=True):
                if value is not None:
                    import os
                    os.environ['SL_EXPERIMENT_WAREHOUSE'] = value
                ctx = SimpleNamespace()
                town.setup_warehouse(ctx)
                if value in ('0', 'off', 'OFF'):
                    self.assertFalse(ctx._world_warehouse_exp)
                else:
                    self.assertEqual(ctx._world_warehouse_exp, (1, 0, 150, 0, 7, 30, 150))
        with patch.dict('os.environ', {}, clear=True):
            for opcode in (0x4ED2, 0x0971):
                self.assertIn(opcode, world_bridge.outgoing_extensions(
                    SimpleNamespace(world=True), (), opcode, 10, 'menu'))


if __name__ == '__main__':
    unittest.main()
