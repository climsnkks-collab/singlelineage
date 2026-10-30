"""Temporary profile regression: real item debit/save and registered reconnect hooks.

No sockets, game, native inputs or production profiles. This checks server
state and proposed outbound packets, not native rendering or a formal PASS.
"""
from pathlib import Path
import asyncio
import json
import os
import shutil
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import (
    broker, inventory, inventory_store, world_bridge, world_combat, world_item_effects,
    world_registry, world_visibility)
from tools.local_own_login_request.codec import LocalLoginRequest
from tools.local_original_session.world_handlers import _starter_fields, feature_registry


class ConsumableReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_root = (Path(__file__).resolve().parents[2] / '_work' / 'tmp').resolve()
        self.temp = self.temp_root / uuid4().hex
        os.makedirs(self.temp)
        self.addCleanup(self._remove_temp)
        previous = (os.environ.get('TEMP'), os.environ.get('TMP'), tempfile.tempdir)
        self.addCleanup(self._restore_temp, previous)
        os.environ['TEMP'] = os.environ['TMP'] = str(self.temp)
        tempfile.tempdir = str(self.temp)
        self.profile = self.temp / 'characters.json'
        roster = inventory_store.realm.CharacterStore(self.profile)
        roster.create(inventory_store.realm.Creation('PotionKnight', 1, 0, (13,) * 6))
        self.now = 100.0
        self.views = []
        self.registry = feature_registry()

    @staticmethod
    def _restore_temp(previous):
        for name, value in zip(('TEMP', 'TMP'), previous[:2]):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        tempfile.tempdir = previous[2]

    def _remove_temp(self):
        if self.temp.resolve().parent != self.temp_root:
            raise ValueError('TEST_TEMP_OUTSIDE_WORKSPACE')
        shutil.rmtree(self.temp)

    async def asyncTearDown(self):
        for view in self.views:
            view.close()

    def context(self):
        """Construct the real unstarted host; select and transport stay in memory."""
        host = broker.PersistentBroker(
            sockets={12000: object(), 14030: object()}, retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=lambda *_: True,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=lambda *_: None, expected_uuid=str(uuid4()),
            store_path=self.profile, edge_passability=lambda *_: True,
            world_policy=world_visibility.POLICY)
        self.assertIs(host._world_registry, self.registry)
        view = host._world
        view.runtime.clock = lambda: self.now
        self.views.append(view)
        store = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                kit_policy=inventory.KIT_POLICY)
        host._inventory_store = store
        host._inventory_kit_policy = inventory.KIT_POLICY
        host.policy.inventory_add = host.policy.item_kit = True
        writer, game = object(), object()
        position = SimpleNamespace(uid=1, name='PotionKnight', map_id=0, word0=100, word1=100)
        host._world_pcs[id(writer)] = (writer, 1)
        host.realm.service = lambda w: SimpleNamespace(snapshot=lambda: position)
        host.realm.registry.resolve = lambda w: game
        host._world_ready = lambda w, g: host.realm.service(w) if w is writer and g is game else None
        host._selected_owner_current = lambda w, r, p: w is writer and p is position
        host._send = AsyncMock()
        ctx = host.realm._world_context
        ctx.run_sync_hooks('runtime_started')
        return ctx, writer, game

    def bind(self, ctx):
        fields = {1: 1, 2: 1, 4: 13, 5: 10, 6: 11, 7: 12, 8: 14, 9: 15,
                  10: 200, 11: 200, 12: 100, 13: 100, 14: -10, 15: 1793000000,
                  16: 200, 17: 7, 18: -123, 20: 9}
        ctx.world.bind_pc(1, world_combat.PcProfile(1, 1, 0, 13, 13), fields)
        ctx.world.update_pc(1, 0, 100, 100, reset=True)

    async def enter(self, ctx, writer, game, hook='after_enter'):
        await world_registry.run_hooks(hook, ctx, writer, {}, game, object())

    async def test_actual_broker_selection_adopts_loaded_row_at_first_pc_entry(self):
        # The reconnect report had a loaded store row but an empty default
        # state when after_enter ran. Model that observed gap before the real
        # login/select/world_after_request route, then require store adoption.
        saved = world_item_effects.consumable_snapshot(1,
            world_item_effects.ConsumableState(
                potions={17: 243.422, 296: 240.844}, potions_paused=True),
            self.now, wall=time.time())
        self.profile.with_name('consumable-effects.json').write_text(
            json.dumps({'version': 1, 'rows': [saved]}), encoding='utf-8')
        host = broker.PersistentBroker(
            sockets={12000: object(), 14030: object()}, retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=lambda *_: True,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=lambda *_: None, expected_uuid=str(uuid4()),
            store_path=self.profile, edge_passability=lambda *_: True,
            world_policy=world_visibility.POLICY, world_starter_kit='test_knight')
        view = host._world
        view.runtime.clock = lambda: self.now
        self.views.append(view)
        store = inventory_store.InventoryStore(self.profile, policy=inventory_store.POLICY,
                                                kit_policy=inventory.KIT_POLICY)
        rows = []
        for uid, template in ((11, 17), (12, 296)):
            fields = _starter_fields()
            fields.update({1: uid, 2: template, 4: 2})
            rows.append(fields)
        store.grant(1, inventory.build_kit_frame(rows))
        host._inventory_store = store
        host._inventory_kit_policy = inventory.KIT_POLICY
        host.policy.inventory_add = host.policy.item_kit = True
        ctx = host.realm._world_context
        ctx.run_sync_hooks('runtime_started')
        effects = host._world_item_effects
        self.assertEqual(set(effects.states[1].potions), {17, 296})
        effects.states.pop(1)  # Exact empty-state boundary observed in reconnect JSON.
        writer = object()
        game = host.realm.grant(writer, movement_owner_guard=lambda *_: True)
        await game.received(SimpleNamespace(opcode=0x263,
            payload=LocalLoginRequest(0, 'standalone.local', host.realm.expected_uuid).payload()))
        await game.received(SimpleNamespace(opcode=0x4e28,
            payload=pb.encode_bytes(1, b'PotionKnight') + b'\x10\0\x18\0'))
        host._send = AsyncMock()
        host._world_send = AsyncMock()
        lock = asyncio.Lock()
        row = {'operation_lock': lock}
        await host._world_after_request(writer, row, game, 0x4e28, lock)
        entered = next(event for event in effects.restore_trace if event['phase'] == 'after_enter')
        bound = next(event for event in effects.restore_trace if event['phase'] == 'post_bind_pc')
        self.assertFalse(bound['owner']['state_paused'])
        self.assertEqual(entered['saved_templates_before'], [17, 296])
        self.assertEqual(entered['active_templates_after'], [17, 296])
        self.assertFalse(entered['inventory_frame_present'])
        self.assertEqual(set(view.combat.pcs[1].buffs), {'brave', 'haste'})
        host._inventory_current_frame = store.restore(1)
        before_delivery = len(host._send.await_args_list)
        await world_registry.run_hooks('inventory_delivered', ctx, writer, row, game, lock)
        delivered = tuple(wire for call in host._send.await_args_list[before_delivery:]
                          for wire in call.args[2])
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in delivered
                          if int.from_bytes(wire[2:4], 'little') in (0x4ed8, 0x4e5b, 0x4e91)],
                         [0x4ed8, 0x4e5b, 0x4e91] * 2)
        self.assertEqual(effects.restore_trace[-1]['status'], 'DRAINED')
        await world_bridge.stop(host)

    async def test_drink_broker_close_reconnect_replays_potion_frames(self):
        ctx, writer, game = self.context()
        rows = []
        for uid, template in ((11, 17), (12, 296)):
            fields = _starter_fields()
            fields.update({1: uid, 2: template, 4: 2})
            rows.append(fields)
        ctx.inventory_store.grant(1, inventory.build_kit_frame(rows))
        ctx.inventory_frame = ctx.inventory_store.restore(1)
        self.bind(ctx)
        await self.enter(ctx, writer, game)
        params = pb.encode_uint32(1, 1) + pb.encode_uint32(15, 0) + pb.encode_uint32(16, 0)
        for item_uid in (11, 12):
            frame = SimpleNamespace(payload=pb.encode_uint32(1, item_uid) + pb.encode_bytes(2, params))
            self.assertTrue(await ctx._world_use_item(writer, {}, game, frame, object()))
        magic = ctx._world_magic.state(1)
        magic.buffs[7] = self.now + 1200
        magic.buff_sources[7] = 2
        magic.weapon_uids[7] = 99

        # Broker.close cancels its serve task. Its finally runs world leave,
        # then _close stops the runtime and detaches the potion owner.
        host = ctx.broker
        for port in host.sockets:
            socket = SimpleNamespace(close=lambda: None)
            host.sockets[port] = host.policy.reservations[port] = socket
        entered = asyncio.Event()
        async def serve_lifetime():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                try:
                    await world_bridge.leave(host, writer)
                finally:
                    host._tasks.discard(asyncio.current_task())
        task = asyncio.create_task(serve_lifetime())
        host._tasks.add(task)
        await entered.wait()
        await host.close()
        saved = json.loads(self.profile.with_name('consumable-effects.json').read_text(
            encoding='utf-8'))['rows'][0]['potion_remaining']
        self.assertEqual(set(saved), {'17', '296'})
        self.assertGreater(saved['17'], 0)
        self.assertGreater(saved['296'], 0)
        self.assertEqual(ctx._world_item_effects.restore_trace[-1]['phase'], 'before_leave')
        self.assertEqual(ctx._world_item_effects.restore_trace[-1]['stage'], 'SAVED')
        magic_rows = json.loads(self.profile.with_name('magic.json').read_text(
            encoding='utf-8'))['rows']
        saved_magic = next(row for row in magic_rows if row['uid'] == 1)
        self.assertTrue(any(buff['spell'] == 7 and buff['remaining'] > 0
                            for buff in saved_magic['buffs']))

        fresh, writer2, game2 = self.context()
        self.bind(fresh)
        await self.enter(fresh, writer2, game2)
        self.assertFalse(fresh._world_item_effects.restore_trace[-1]['inventory_frame_present'])
        fresh.inventory_frame = fresh.inventory_store.restore(1)
        before_delivery = len(fresh.broker._send.await_args_list)
        await self.enter(fresh, writer2, game2, 'inventory_delivered')
        delivered = tuple(wire for call in fresh.broker._send.await_args_list[before_delivery:]
                          for wire in call.args[2])
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in delivered
                          if int.from_bytes(wire[2:4], 'little') in (0x4ed8, 0x4e5b, 0x4e91)],
                         [0x4ed8, 0x4e5b, 0x4e91] * 2)
        self.assertEqual(fresh._world_item_effects.restore_trace[-1]['status'], 'DRAINED')
        await world_bridge.stop(fresh.broker)

    async def test_consumed_knight_potions_restore_from_disk_through_registered_hooks(self):
        ctx, writer, game = self.context()
        rows = []
        for uid, template in ((11, 17), (12, 296)):
            fields = _starter_fields()
            fields.update({1: uid, 2: template, 4: 2})
            rows.append(fields)
        ctx.inventory_store.grant(1, inventory.build_kit_frame(rows))
        ctx.inventory_frame = ctx.inventory_store.restore(1)
        self.bind(ctx)
        await self.enter(ctx, writer, game)
        # Reproduce the separate received magic save without learning the
        # companion's spells on the knight. It must not own potion deadlines.
        for key in (7, 25):
            ctx._world_magic.state(1).buffs[key] = self.now + 1200
            ctx._world_magic.state(1).buff_sources[key] = 2
        ctx._world_magic.state(1).weapon_uids[7] = 99
        params = pb.encode_uint32(1, 1) + pb.encode_uint32(15, 0) + pb.encode_uint32(16, 0)
        used_packets = []
        for item_uid in (11, 12):
            frame = SimpleNamespace(payload=pb.encode_uint32(1, item_uid) + pb.encode_bytes(2, params))
            before_use = len(ctx.broker._send.await_args_list)
            self.assertTrue(await ctx._world_use_item(writer, {}, game, frame, object()))
            used_packets.append(tuple(wire for call in ctx.broker._send.await_args_list[before_use:]
                                      for wire in call.args[2]
                                      if int.from_bytes(wire[2:4], 'little') in (0x4ed8, 0x4e5b, 0x4e91)))
        self.assertEqual([[int.from_bytes(wire[2:4], 'little') for wire in group]
                          for group in used_packets], [[0x4ed8, 0x4e5b, 0x4e91]] * 2)
        consumed = ctx.inventory_store.restore(1)
        self.assertEqual([dict(item.raw_fields)[4] for item in inventory.validate_kit_frame(consumed)], [1, 1])
        self.now += 70.25
        await world_registry.run_hooks('before_leave', ctx, writer, 1)
        ctx.world.leave_pc(1)
        await world_registry.run_hooks('after_leave', ctx, writer)
        saved = ctx._world_item_effects.store.rows[1]['potion_remaining']
        self.assertEqual(saved, {'17': 229.75, '296': 229.75})
        await world_bridge.stop(ctx.broker)

        # New runtime/feature objects load actual files. Delay after startup
        # proves the paused potion state survives the character selection wait.
        self.now = 10000.0
        fresh, writer2, game2 = self.context()
        self.now += 5000
        self.bind(fresh)
        await self.enter(fresh, writer2, game2)
        pc = fresh.world.combat.pcs[1]
        self.assertEqual({kind: deadline - self.now for kind, (deadline, _) in pc.buffs.items()},
                         {'haste': 229.75, 'brave': 229.75})
        self.assertLess(fresh.world.combat.speed_factor(1, self.now), 1)
        sent = tuple(wire for call in fresh.broker._send.await_args_list for wire in call.args[2])
        self.assertNotIn(world_combat.speed_frame(1, fresh.world.combat.speed_factor(1, self.now)), sent)
        for template in (17, 296):
            catalog, image, _ = world_item_effects.CONSUMABLE_BUFF_ICONS[template]
            self.assertNotIn(world_item_effects.buff_icon_frame(catalog, image, 229.75), sent)
            self.assertNotIn(fresh._world_item_effects.use_effect_frame(1, template), sent)
        self.assertEqual(fresh._world_magic.state(1).buff_sources, {7: 2, 25: 2})
        self.assertEqual(fresh._world_magic.state(1).learned, set())

        deadlines = dict(pc.buffs)
        fresh.inventory_frame = fresh.inventory_store.restore(1)
        before_delivery = len(fresh.broker._send.await_args_list)
        await self.enter(fresh, writer2, game2, 'inventory_delivered')
        delivered = tuple(wire for call in fresh.broker._send.await_args_list[before_delivery:]
                          for wire in call.args[2])
        self.assertTrue(all(len(call.args[2]) <= fresh.broker.WORLD_SEND_CHUNK
                            for call in fresh.broker._send.await_args_list[before_delivery:]))
        replayed = tuple(wire for wire in delivered
                         if int.from_bytes(wire[2:4], 'little') in (0x4ed8, 0x4e5b, 0x4e91))
        self.assertEqual([int.from_bytes(wire[2:4], 'little') for wire in replayed],
                         [0x4ed8, 0x4e5b, 0x4e91] * 2)
        trace = fresh._world_item_effects.restore_trace
        self.assertEqual(trace[0]['loaded'][0]['potion_remaining'], saved)
        self.assertEqual(trace[1]['phase'], 'after_enter')
        self.assertFalse(trace[1]['inventory_frame_present'])
        self.assertEqual(trace[1]['proposed_opcodes'], [])
        self.assertEqual(trace[2]['phase'], 'inventory_delivered')
        self.assertEqual(trace[2]['proposed_opcodes'][:6], [0x4ed8, 0x4e5b, 0x4e91] * 2)
        self.assertEqual((trace[2]['status'], trace[2]['drained_chunks']), ('DRAINED', 2))
        report = {}
        fresh.run_sync_hooks('report', report)
        self.assertEqual(report['consumable_restore'], trace)
        self.assertEqual((replayed[0], replayed[3]),
                         (used_packets[0][0], used_packets[1][0]))
        self.assertEqual((replayed[1], replayed[4]), (used_packets[1][1],) * 2)
        self.assertIn(world_combat.speed_frame(1, fresh.world.combat.speed_factor(1, self.now)), delivered)
        for template in (17, 296):
            catalog, image, _ = world_item_effects.CONSUMABLE_BUFF_ICONS[template]
            self.assertIn(world_item_effects.buff_icon_frame(catalog, image, 229.75), delivered)
        for used, restored in zip((used_packets[0][2], used_packets[1][2]),
                                  (replayed[2], replayed[5])):
            with pb.parse_message(used[4:-2]) as outer_used, pb.parse_message(restored[4:-2]) as outer_restored:
                self.assertEqual(outer_used.occurrences(1)[0].value,
                                 outer_restored.occurrences(1)[0].value)
                with pb.parse_message(bytes(outer_used.occurrences(2)[0].value)) as child_used, \
                        pb.parse_message(bytes(outer_restored.occurrences(2)[0].value)) as child_restored:
                    self.assertEqual({n: child_used.occurrences(n)[0].value for n in (1, 2, 4)},
                                     {n: child_restored.occurrences(n)[0].value for n in (1, 2, 4)})
                    self.assertEqual(child_restored.occurrences(3)[0].value, 230)
        self.assertEqual(pc.buffs, deadlines)
        self.assertEqual(fresh.inventory_store.restore(1), consumed)
        await world_bridge.stop(fresh.broker)

    async def test_saved_knight_potions_survive_close_before_inventory_delivery(self):
        row = world_item_effects.consumable_snapshot(1,
            world_item_effects.ConsumableState(
                potions={17: 211.61, 296: 229.297}, potions_paused=True),
            self.now, wall=time.time())
        saved = self.profile.with_name('consumable-effects.json')
        saved.write_text(json.dumps({'version': 1, 'rows': [row]}), encoding='utf-8')
        ctx, writer, game = self.context()
        self.bind(ctx)
        await self.enter(ctx, writer, game)
        self.assertEqual(set(ctx.world.combat.pcs[1].buffs), {'haste', 'brave'})
        self.assertIsNone(ctx.inventory_frame)
        self.assertFalse(any(int.from_bytes(wire[2:4], 'little') in (0x0964, 0x4e5b, 0x4e91)
                             for call in ctx.broker._send.await_args_list for wire in call.args[2]))
        ctx.world.close()  # Broker.close precedes world_bridge.stop on failed send.
        await world_bridge.stop(ctx.broker)
        latest = json.loads(saved.read_text(encoding='utf-8'))['rows'][0]
        self.assertGreater(latest['potion_remaining']['17'], 200)
        self.assertGreater(latest['potion_remaining']['296'], 200)

        fresh, writer2, game2 = self.context()
        self.bind(fresh)
        await self.enter(fresh, writer2, game2)
        kit = inventory.build_kit_frame([_starter_fields()])
        fresh.inventory_store.grant(1, kit)
        fresh.inventory_frame = kit
        await self.enter(fresh, writer2, game2, 'inventory_delivered')
        frames = (wire for call in fresh.broker._send.await_args_list
                  for wire in call.args[2] if int.from_bytes(wire[2:4], 'little') == 0x4e91)
        durations = {}
        for wire in frames:
            with pb.parse_message(wire[4:-2]) as outer:
                with pb.parse_message(bytes(outer.occurrences(2)[0].value)) as child:
                    durations[child.occurrences(4)[0].value] = child.occurrences(3)[0].value
        self.assertEqual(durations, {481: 212, 486: 230})
        await world_bridge.stop(fresh.broker)


if __name__ == '__main__':
    unittest.main()
