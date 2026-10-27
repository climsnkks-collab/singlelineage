"""Explicit goals through actual edge helpers and broker; no process/native UI.

Pinned helper/source checks and the existing synthetic retained-memory fixture
are reused. No source_ready patch or mocked-clear positive authorizes a move.
"""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_original_session import broker as b, edge, movement, npc_edge_tests
from tools.local_original_session import npc_motion, npc_session as ns
from tools.local_original_session.npc_tests import spawn


class ConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_off_never_constructs_reader_or_source_and_configuration_is_explicit(self):
        from tools.local_original_session.npc_session import EXPLICIT_LOCAL_AXIS_SIGN_GOAL
        self.assertEqual(EXPLICIT_LOCAL_AXIS_SIGN_GOAL, 'EXPLICIT_LOCAL_AXIS_SIGN_GOAL')
        self.assertIs(EXPLICIT_LOCAL_AXIS_SIGN_GOAL, ns.AXIS_SIGN_GOAL)
        with patch.object(ns.npc_edge, 'NpcEdgeAdapter', side_effect=AssertionError('unused')):
            factory = ns.NpcSessionFactory(None)
            self.assertEqual(factory.broker_options(), {})
            self.assertIsNone(factory.current_binding())
        for options in (dict(spawns=[spawn()]), dict(interval_ns=100),
                        dict(spawns=(spawn(),)),
                        dict(spawns=(spawn(),), interval_ns=True, policy=npc_motion.LOCAL_PRE_STEP,
                             goal_policy=ns.AXIS_SIGN_GOAL),
                        dict(spawns=(spawn(),), interval_ns=100, policy='UNKNOWN',
                             goal_policy=ns.AXIS_SIGN_GOAL),
                        dict(spawns=(spawn(),), interval_ns=100, policy=npc_motion.LOCAL_PRE_STEP,
                             goal_policy='ORIGINAL_AI')):
            with self.subTest(options=options), self.assertRaises(ValueError):
                ns.NpcSessionConfig(**options)


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await npc_edge_tests.NpcEdgeTests.asyncSetUp(self)
        candidate, _ = self.realm._npc_spawns[0]
        self.config = ns.NpcSessionConfig(spawns=(candidate,), interval_ns=100,
            policy=npc_motion.LOCAL_PRE_STEP, goal_policy=ns.AXIS_SIGN_GOAL)
        self.factory = ns.NpcSessionFactory(self.f.adapter.reader, config=self.config)
        self.assertIsNone(self.factory.current_binding())
        self.assertTrue(self.factory.adapter._proof.checks)  # Real pinned-source constructor.
        self.factory.adapter._proof = self.f.adapter
        # Existing fixture covers the initial eight edges. Add the actual cell
        # for the second eastward edge used by the two-step consumer checks.
        for _, (x, y) in self.f.adapter.tile.probe_cells((self.x + 1, self.y), 2):
            row = 0x400000 + y * 0x1000
            self.f.put(0x300000 + y * 24, '<QQQ', row, row + 128 * 8, row + 128 * 8)
            self.f.put(row + x * 8, '<IHH', 0, 0, 0)
        options = self.factory.broker_options()
        self.assertIs(options['npc_spawns'][0], candidate)
        self.assertEqual(options['npc_motion_interval_ns'], 100)
        self.assertEqual(options['npc_motion_policy'], npc_motion.LOCAL_PRE_STEP)
        self.realm.npc_edge_passability = options['npc_edge_passability']
        self.controller = self.factory.bind(self.producer)

    def binding(self):
        # Required only by the reused fixture's initial adapter constructor.
        return ns.npc_edge.NpcEdgeBinding(self.writer, self.producer)

    async def test_goal_actual_edge_real_policy_write_drain_once_commit_and_current_start(self):
        goal = (self.x + 2, self.y)
        with patch.object(edge, '_world', wraps=edge._world) as world, \
             patch.object(self.factory.adapter._proof.nav, 'empty_store',
                          wraps=self.factory.adapter._proof.nav.empty_store) as stores:
            result = await self.controller.approach(goal=goal, now_ns=1000)
            self.assertEqual(result.status, 'MOVED')
            self.assertEqual(world.call_args.args[5], self.realm.profile_uid)
            self.assertEqual(stores.call_count, 2)
        self.assertIs(result.state, self.mover.state)
        self.assertEqual(result.state.packed, movement.authority.pack_grid(self.x + 1, self.y))
        self.assertEqual((self.writer.write.call_count, self.writer.drain.await_count), (1, 1))
        self.assertEqual(self.policy.log[-1][2], 0x4e2c)
        with movement.pb.parse_message(self.writer.write.call_args.args[0][4:-2],
                                       schema={1: 0, 2: 0, 3: 0}) as parsed:
            self.assertEqual([(f.number, f.value) for f in parsed.fields],
                             [(1, self.initial.uid), (2, self.initial.packed), (3, 2)])
        self.assertIsNone(self.mover.pending)
        self.assertEqual((await self.controller.approach(goal=goal, now_ns=1000)).status, 'CADENCE')
        self.assertEqual((await self.controller.approach(goal=goal, now_ns=1099)).status, 'CADENCE')
        second = await self.controller.approach(goal=goal, now_ns=1100)
        self.assertEqual(second.status, 'MOVED', self.factory.adapter.last_result)
        self.assertEqual(movement.authority.unpack_grid(second.state.packed), goal)
        self.assertEqual((await self.controller.approach(goal=goal, now_ns=1100)).status, 'AT_GOAL')
        self.assertEqual(self.writer.write.call_count, 2)
        self.assertEqual(self.mover.state.last_step_ns, 1100)

    async def test_axis_sign_all_directions_is_local_and_no_implicit_goal_or_clock(self):
        for direction, delta in enumerate(movement.authority.DELTAS):
            with self.subTest(direction=direction):
                goal = tuple(a + d * 4 for a, d in zip((self.x, self.y), delta))
                before = self.mover.state
                self.assertEqual((await self.controller.approach(goal=goal, now_ns=1000)).status, 'MOVED')
                self.assertEqual(self.mover.state.direction, direction)
                self.mover.state = before  # Independent explicit directions, no fake clear edge.
        for goal, now in ((None, 1100), ([self.x, self.y], 1100), ((self.x, self.y), True),
                          ((self.x, self.y), -1), ((self.x, self.y), 999)):
            with self.subTest(goal=goal, now=now), self.assertRaises(ValueError):
                await self.controller.approach(goal=goal, now_ns=now)

    async def test_blocked_and_nonempty_unknown_preserve_state_without_alternative_route(self):
        goal = (self.x + 1, self.y)
        cells = self.f.adapter.tile.probe_cells(self.f.grid, 2)
        addresses = [0x400000 + y * 0x1000 + x * 8 + 4 for _, (x, y) in cells]
        for at in addresses:
            self.f.put(at, '<H', 1)
        with patch.object(self.factory.adapter._proof.tile, 'probe_cells',
                          wraps=self.factory.adapter._proof.tile.probe_cells) as probes:
            result = await self.controller.approach(goal=goal, now_ns=1000)
            self.assertEqual(result.status, 'BLOCKED')
            self.assertEqual({call.args[1] for call in probes.call_args_list}, {2})
        for at in addresses:
            self.f.put(at, '<H', 0)
        # This synthetic fixture lacks Monster source/typed proof. A nonempty
        # target stays UNKNOWN; a raw NPC label cannot authorize movement.
        target = (self.x + 1, self.y)
        head, buckets, node, vector = 0x600000, self.buckets[0], 0x700000, 0x740000
        self.f.put(self.f.actor + 0x798 + 16, '<Q', 1)
        self.f.put(head, '<QQ', node, node)
        self.f.put(node, '<QQiiQQQ', head, head, *target, vector, vector + 8, vector + 8)
        self.f.put(vector, '<Q', 0x125000)
        self.f.put(buckets + (self.f.adapter.nav.destination_hash(target) & 7) * 16,
                   '<QQ', node, node)
        result = await self.controller.approach(goal=goal, now_ns=1000)
        self.assertEqual((result.status, result.reason),
                         ('UNKNOWN', 'SYNTHETIC_CELL_UNREADABLE'))
        self.assertIs(self.mover.state, self.initial)
        self.writer.write.assert_not_called()

    async def test_current_registry_claim_reselection_ambiguity_configuration_and_close_refuse(self):
        selection = dict(self.realm.registry.selected)
        service = self.realm.service(self.writer)
        position = service.snapshot()
        self.assertIs(self.controller.current_binding().owner, self.writer)
        mutations = (
            self.realm.registry.selected.clear,
            lambda: self.realm.registry.selected.update({key: object() for key in selection}),
            lambda: self.producer._claims[14030].append(self.row),
            lambda: self.row.update(failed=True),
            lambda: setattr(self.mover, 'spawn_drained', False),
            lambda: setattr(self.mover, 'interval_ns', 101),
            lambda: setattr(self.mover, 'policy', 'UNKNOWN'),
            lambda: setattr(self.realm, '_npc_motion_interval_ns', 101),
            lambda: setattr(self.f.adapter.reader.owner, 'closed', True),
        )
        for mutate in mutations:
            mutate()
            self.assertIsNone(self.controller.current_binding())
            self.assertEqual((await self.controller.approach(
                goal=(self.x + 1, self.y), now_ns=1000)).status, 'UNKNOWN')
            self.realm.registry.selected.clear(); self.realm.registry.selected.update(selection)
            self.producer._claims[14030] = [self.row]
            self.row['failed'] = False
            self.mover.spawn_drained, self.mover.interval_ns, self.mover.policy = True, 100, self.config.policy
            self.realm._npc_motion_interval_ns = 100
            self.f.adapter.reader.owner.closed = False
            self.assertIs(service.snapshot(), position)
        with self.assertRaisesRegex(ValueError, 'ALREADY_BOUND'):
            self.factory.bind(self.producer)
        stale = ns.NpcSessionFactory(self.f.adapter.reader, config=replace(self.config, interval_ns=101))
        with self.assertRaisesRegex(ValueError, 'SAME_MOTION_CONFIGURATION'):
            stale.bind(self.producer)
        self.controller.close()
        self.assertIsNone(self.factory.current_binding())
        self.assertEqual((await self.controller.approach(
            goal=(self.x + 1, self.y), now_ns=1000)).status, 'CLOSED')
        self.writer.write.assert_not_called()

    async def test_concurrent_duplicate_goals_serialize_and_cancel_preserves_broker_failure(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def drain():
            entered.set()
            await release.wait()
        self.writer.drain.side_effect = drain
        goal = (self.x + 2, self.y)
        first = asyncio.create_task(self.controller.approach(goal=goal, now_ns=1000))
        await asyncio.wait_for(entered.wait(), 2)
        second = asyncio.create_task(self.controller.approach(goal=goal, now_ns=1000))
        await asyncio.sleep(0)
        self.assertEqual(self.writer.write.call_count, 1)
        release.set()
        results = await asyncio.gather(first, second)
        self.assertEqual([result.status for result in results], ['MOVED', 'CADENCE'])
        entered.clear(); release.clear()
        moving = asyncio.create_task(self.controller.approach(goal=goal, now_ns=1100))
        await asyncio.wait_for(entered.wait(), 2)
        moving.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await moving
        self.assertTrue(self.mover.fatal and self.producer.failure.is_set())
        self.assertIsNone(self.mover.pending)
        self.assertFalse(self.row['operation_lock'].locked())
        self.assertEqual((await self.controller.approach(goal=goal, now_ns=1200)).status, 'UNKNOWN')
        self.assertEqual(self.writer.write.call_count, 2)

    async def test_submit_tick_goal_replacement_at_goal_and_factory_close(self):
        self.assertEqual((await self.controller.tick(now_ns=1000)).status, 'IDLE')
        self.controller.submit_goal(goal=(self.x, self.y))
        self.assertEqual((await self.controller.tick(now_ns=1000)).status, 'AT_GOAL')
        self.assertEqual((await self.controller.tick(now_ns=1000)).status, 'AT_GOAL')
        entered, release = asyncio.Event(), asyncio.Event()
        async def drain():
            entered.set()
            await release.wait()
        self.writer.drain.side_effect = drain
        self.controller.submit_goal(goal=(self.x + 2, self.y))
        moving = asyncio.create_task(self.controller.tick(now_ns=1000))
        await asyncio.wait_for(entered.wait(), 2)
        self.controller.submit_goal(goal=(self.x + 1, self.y))
        release.set()
        self.assertEqual((await moving).status, 'MOVED')
        self.assertEqual((await self.controller.tick(now_ns=1100)).status, 'AT_GOAL')
        self.assertEqual(self.writer.write.call_count, 1)
        self.factory.close()
        self.assertIsNone(self.factory.current_binding())
        self.assertIsNone(self.controller._goal)
        self.assertEqual((await self.controller.tick(now_ns=1200)).status, 'CLOSED')
        with self.assertRaisesRegex(ValueError, 'CLOSED'):
            self.controller.submit_goal(goal=(self.x + 2, self.y))
        with self.assertRaisesRegex(ValueError, 'CLOSED'):
            self.factory.bind(self.producer)
        self.assertFalse(self.mover.closed)  # Caller still owns broker/reader close.


if __name__ == '__main__':
    unittest.main()
