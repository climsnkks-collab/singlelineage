"""Short checks for nearby spawn groups, dormant slots, visibility and the broker link."""
import asyncio
import random
import tempfile
import unittest
import uuid
from pathlib import Path

from tools.local_original_session import broker as b, movement as m, npc, npc_death
from tools.local_original_session import world_interest_spawn as wis, world_visibility as wv
from tools.local_original_session import test_ports
from tools.local_original_session.broker_tests import FixtureConversation, c2s, reserve, response
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_entities import EntityRegistry, Kind
from tools.local_entry_server import protobuf as pb
from tools.local_own_login_request.codec import LocalLoginRequest

DATA = load_m1()
TOWN = (0, 32578, 32946)
NEAR_ORC = (0, 32590, 32900)  # orc/goblin rect (y2=32886) at 14, archer (y2=32866) at 34


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


def decode(wire):
    opcode = int.from_bytes(wire[2:4], 'little')
    if opcode == 0x4e96:
        return opcode, b.session.world.decode_payload(0x4e96, wire[4:-2])
    return opcode, wire


class SpawnerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.entities = EntityRegistry()
        self.spawner = wis.InterestSpawner(self.entities, DATA, passable=lambda *_: True,
                                           rng=random.Random(7))

    def npcs(self):
        return [e for e in self.entities if e.kind is Kind.NPC and e.alive]

    def group(self, group_id):
        return next(g for g in self.spawner.groups if g.spec.group_id == group_id)

    def test_activate_dormant_and_same_mobs_return(self):
        self.assertFalse(self.spawner.update_interest([TOWN], self.clock()))
        self.assertEqual(self.npcs(), [])
        self.assertTrue(self.spawner.update_interest([NEAR_ORC], self.clock()))
        orc, goblin = self.group('m1_orc'), self.group('m1_goblin')
        self.assertTrue(orc.active and goblin.active)
        self.assertFalse(self.group('m1_orc_archer').active or self.group('m1_werewolf').active)
        npcs = self.npcs()
        self.assertEqual(len(npcs), orc.spec.target_count + goblin.spec.target_count)
        for entity in npcs:
            group, slot = self.spawner.slot_for(entity.uid)
            self.assertTrue(group.spec.rect.contains(entity.x, entity.y))
            self.assertEqual(entity.template_id, group.spec.template_id)
            self.assertEqual(slot.hp, group.monster.hp)
        self.assertEqual(len({(e.x, e.y) for e in npcs}), len(npcs))  # one per tile
        # Wounded mob, then walk away: dormant keeps entity/HP/position.
        wounded = npcs[0]
        self.spawner.set_hp(wounded.uid, 1)
        before = {e.uid: (e.x, e.y, e.generation) for e in npcs}
        self.assertFalse(self.spawner.update_interest([(0, 32590, 32920)], self.clock()))  # 34: still active
        self.assertTrue(orc.active)
        self.spawner.update_interest([TOWN], self.clock())  # 60 > ROFF
        self.assertFalse(orc.active or goblin.active)
        self.assertFalse(any(self.spawner.visible(uid) for uid in before))
        self.clock.now += 3600
        self.assertFalse(self.spawner.tick(self.clock()))  # dormant groups are not computed
        self.spawner.update_interest([NEAR_ORC], self.clock())
        after = {e.uid: (e.x, e.y, e.generation) for e in self.npcs()}
        self.assertEqual(after, before)
        self.assertEqual(self.spawner.slot_for(wounded.uid)[1].hp, 1)

    def test_dead_slot_refills_only_after_deadline_and_while_active(self):
        self.spawner.update_interest([NEAR_ORC], self.clock())
        victim = self.npcs()[0]
        group, slot = self.spawner.slot_for(victim.uid)
        self.spawner.mark_dead(victim.uid, self.clock())
        self.assertEqual(slot.state, wis.SlotState.WAIT)
        self.assertGreaterEqual(slot.respawn_at - slot.corpse_at, group.spec.respawn_delay_min_ms / 1000)
        self.clock.now = slot.corpse_at
        self.assertTrue(self.spawner.tick(self.clock()))  # corpse removed
        self.assertIsNone(self.entities.get(victim.uid))
        self.assertEqual(slot.state, wis.SlotState.WAIT)
        self.spawner.update_interest([TOWN], self.clock())
        self.clock.now = slot.respawn_at + 1
        self.assertFalse(self.spawner.tick(self.clock()))  # dormant: no refill
        self.assertEqual(slot.state, wis.SlotState.WAIT)
        self.spawner.update_interest([NEAR_ORC], self.clock())  # deadline passed: refill on entry
        self.assertEqual(slot.state, wis.SlotState.ALIVE)
        self.assertNotEqual(slot.uid, victim.uid)
        self.assertEqual(slot.hp, group.monster.hp)

    def test_blocked_tiles_keep_vacancy(self):
        spawner = wis.InterestSpawner(EntityRegistry(), DATA, passable=lambda *_: None,
                                      rng=random.Random(1))
        spawner.update_interest([NEAR_ORC], 10.0)
        slots = [s for g in spawner.groups if g.active for s in g.slots]
        self.assertTrue(slots)
        self.assertTrue(all(s.state is wis.SlotState.EMPTY and s.retry_at == 10.0 + wis.PLACE_RETRY_S
                            for s in slots))


class VisibilityTests(unittest.TestCase):
    def test_screen_rule(self):
        # L1J Point.isInScreen: <=13 always, >17 never, between: |x-(cx-15)|+|y-(cy-15)| in [17, 43].
        self.assertTrue(wv.in_screen(100, 100, 113, 87))
        self.assertFalse(wv.in_screen(100, 100, 118, 100))
        self.assertTrue(wv.in_screen(100, 100, 114, 86))   # 29+1
        self.assertTrue(wv.in_screen(100, 100, 86, 114))   # 1+29
        self.assertFalse(wv.in_screen(100, 100, 114, 100))  # 29+15
        self.assertFalse(wv.in_screen(100, 100, 86, 100))   # 1+15

    def test_known_set_enter_exit(self):
        reg = EntityRegistry()
        a = reg.add(Kind.NPC, 0, 105, 100)
        far = reg.add(Kind.NPC, 0, 140, 100)
        vis = wv.Visibility()
        enter, leave = vis.diff(1, [a, far], 100, 100)
        self.assertEqual(([e.uid for e in enter], leave), ([a.uid], []))
        self.assertEqual(vis.diff(1, [a, far], 100, 100), ([], []))
        enter, leave = vis.diff(1, [a, far], 130, 100)
        self.assertEqual(([e.uid for e in enter], leave), ([far.uid], [a.uid]))
        enter, leave = vis.diff(1, [a], 130, 100)  # removed from the world
        self.assertEqual((enter, leave), ([], [far.uid]))

    def test_view_frames_use_monster_sprites(self):
        clock = FakeClock()
        view = wv.WorldView.create(clock=clock, rng=random.Random(3))
        self.assertEqual(view.update_pc(1, *TOWN, reset=True), [])
        frames = view.update_pc(1, 0, 32600, 32880)
        decoded = [decode(w) for w in frames]
        self.assertTrue(decoded and all(op == 0x4e96 for op, _ in decoded))
        sprites = {f[3] for _, f in decoded}
        self.assertLessEqual(sprites, {56, 1022, 57})
        self.assertGreater(len(sprites), 1)
        for _, fields in decoded:
            self.assertEqual((fields[3], fields[39]) in npc.WORLD_MONSTERS, True)
            entity = view.entities.get(fields[2])
            self.assertEqual(fields[1], m.authority.pack_grid(entity.x, entity.y))
        shown = {f[2] for _, f in decoded}
        removed = view.update_pc(1, *TOWN)
        self.assertEqual({int.from_bytes(w[2:4], 'little') for w in removed}, {0x4e40})
        self.assertEqual({npc_death.validate_frame(w)[1] for w in removed}, shown)


class BrokerWorldTests(unittest.IsolatedAsyncioTestCase):
    """Real PersistentBroker over loopback TCP with the world option on."""

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.uuid = str(uuid.uuid4())

        async def owner(peer):
            return True

        self.broker = b.PersistentBroker(sockets=reserve(), listener_ports=test_ports.listener_ports(), retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=owner,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=FixtureConversation, expected_uuid=self.uuid,
            store_path=Path(self.temp.name) / 'characters.json',
            edge_passability=lambda *_: True, world_policy=wv.POLICY)
        self.broker._world.spawner.rng = random.Random(5)  # deterministic placement
        self.clients = []
        await self.broker.start()
        self.assertTrue(self.broker._world.runtime.running)  # same loop as the broker

    async def asyncTearDown(self):
        await self.broker.close()
        for _, writer in self.clients:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        self.temp.cleanup()

    async def bootstrap(self):
        reader, writer = await asyncio.open_connection('127.0.0.1', test_ports.port(12000))
        self.clients.append((reader, writer))
        self.assertEqual(await response(reader), b.KEY12)
        from tools.local_original_session.broker_tests import version_request
        writer.write(c2s(0x4e34, version_request()))
        await writer.drain()
        await response(reader)
        writer.write(c2s(0x4f3d))
        await writer.drain()
        self.assertEqual(await response(reader), b.EMPTY_COUNTS)
        return reader, writer

    async def selected(self):
        first_reader, first = await self.bootstrap()
        first.close()
        await first.wait_closed()
        for _ in range(200):
            if self.broker._claims[12000][0]['promotable']:
                break
            await asyncio.sleep(.005)
        realm = self.broker.realm
        realm.store.create(b.ack.realm.Creation('SoloKnight', 0, 0, (13,) * 6))
        x, y = m.authority.unpack_grid(realm._actor_fields[1])
        realm.positions.commit(m.Position(1, 'SoloKnight', 0, x, y), m.Position(1, 'SoloKnight', 0, 32595, 32906))
        reader, writer = await self.bootstrap()
        writer.write(c2s(0x263, LocalLoginRequest(0x0100007f, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        self.assertEqual(await response(reader), b.ack.ACK_FRAME)
        await response(reader)
        await response(reader)
        writer.write(c2s(0x4e28, pb.encode_message([pb.encode_bytes(1, b'SoloKnight'),
                                                     pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await writer.drain()
        frames = [await response(reader) for _ in range(4)]
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames], [0x4e29, 0x4e95, 0x4e38, 0x4e96])
        return reader, writer

    async def step(self, reader, writer, direction):
        """One move then Alive; collect frames up to the Alive reply."""
        service = self.broker.realm.service(self.broker._claims[12000][-1]['writer'])
        start = service.snapshot()
        writer.write(c2s(0x4e2b, pb.encode_message([pb.encode_uint32(1, start.packed),
                                                     pb.encode_uint32(2, direction)])))
        writer.write(c2s(b.ALIVE_REQUEST))
        await writer.drain()
        frames = []
        while True:
            wire = await response(reader)
            if wire == b.ALIVE_FRAME:
                return frames
            frames.append(decode(wire))

    async def test_quit_ack_then_late_alive_closes_normally(self):
        # Client order seen in manual play: 4E3C -> 4EEF, then one more 4E2A.
        reader, writer = await self.selected()
        writer.write(c2s(b.QUIT_REQUEST))
        await writer.drain()
        while await response(reader) != b.QUIT_SUCCESS_FRAME:
            pass
        writer.write(c2s(b.ALIVE_REQUEST))
        await writer.drain()
        with self.assertRaises(asyncio.TimeoutError):  # ignored: no reply
            while True:
                self.assertNotEqual(await asyncio.wait_for(response(reader), .5), b.ALIVE_FRAME)
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        writer.close()
        await writer.wait_closed()
        for _ in range(200):
            if self.broker.report()['registry_sessions'] == 0:
                break
            await asyncio.sleep(.01)
        report = self.broker.report()
        self.assertIsNone(report['failure_code'], report)
        self.assertTrue(report['quit']['sessions'][0]['request_verified'])
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        self.assertIsNone(result['failure_code'], result)

    async def test_need_failure_in_one_request_drops_it_and_broker_keeps_serving(self):
        # World safety net: a need(...) refusal while handling one request drops
        # that request (recorded), never the broker; the next request is normal.
        from unittest import mock
        from tools.local_original_session import world_bridge
        reader, writer = await self.selected()
        original = world_bridge.receive
        failed = []

        async def receive(broker, writer_, row, game, frame, lock):
            if frame.opcode == 0x4e2b and not failed:
                failed.append(frame.opcode)
                world_bridge.need(False, 'TEST_ONE_REQUEST_NEED_FAILURE')
            return await original(broker, writer_, row, game, frame, lock)
        service = self.broker.realm.service(self.broker._claims[12000][-1]['writer'])
        with mock.patch.object(world_bridge, 'receive', receive):
            start = service.snapshot()
            await self.step(reader, writer, 0)  # refused move, then a normal Alive reply
            self.assertEqual(failed, [0x4e2b])
            self.assertEqual(service.snapshot(), start)
            self.assertFalse(self.broker.failure.is_set(), self.broker.report())
            self.assertIn('TEST_ONE_REQUEST_NEED_FAILURE@0x4e2b', self.broker._world_handler_errors)
            await self.step(reader, writer, 0)  # the next move is handled normally
            self.assertNotEqual(service.snapshot(), start)
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        self.assertIsNone(self.broker.report()['failure_code'])

    async def test_saved_unserved_map_selection_enters_at_town(self):
        # Map experiment off: a character saved on map 4 enters at the town
        # respawn point instead of failing the selection (and the broker).
        first_reader, first = await self.bootstrap()
        first.close()
        await first.wait_closed()
        for _ in range(200):
            if self.broker._claims[12000][0]['promotable']:
                break
            await asyncio.sleep(.005)
        realm = self.broker.realm
        realm.store.create(b.ack.realm.Creation('SoloKnight', 0, 0, (13,) * 6))
        x, y = m.authority.unpack_grid(realm._actor_fields[1])
        realm.positions.commit(m.Position(1, 'SoloKnight', 0, x, y), m.Position(1, 'SoloKnight', 4, 32600, 32800),
                               transition=True)
        reader, writer = await self.bootstrap()
        writer.write(c2s(0x263, LocalLoginRequest(0x0100007f, 'standalone.local', self.uuid).payload()))
        await writer.drain()
        self.assertEqual(await response(reader), b.ack.ACK_FRAME)
        await response(reader)
        await response(reader)
        writer.write(c2s(0x4e28, pb.encode_message([pb.encode_bytes(1, b'SoloKnight'),
                                                     pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
        await writer.drain()
        frames = [await response(reader) for _ in range(4)]
        self.assertEqual([int.from_bytes(w[2:4], 'little') for w in frames], [0x4e29, 0x4e95, 0x4e38, 0x4e96])
        town = self.broker._world.data.town
        position = realm.service(self.broker._claims[12000][-1]['writer']).snapshot()
        self.assertEqual((position.map_id, position.word0, position.word1),
                         (town.map_id, town.respawn_x, town.respawn_y))
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())

    async def test_walk_north_shows_mobs_and_walk_back_removes_them(self):
        reader, writer = await self.selected()
        known, shown, removed = set(), {}, set()

        town = self.broker._world.town

        def apply(frames):
            for op, value in frames:
                if op == 0x4e2c:
                    continue  # monsters now wander on their own (npc_ai); screen enter/exit still checked
                # Registered fixed town NPCs near the start stay on screen; this checks spawned mobs.
                if op == 0x4e96 and town.npc_for(value[2]) is not None:
                    continue
                if op == 0x4e40 and town.npc_for(npc_death.validate_frame(value)[1]) is not None:
                    continue
                if op == 0x4e96:
                    self.assertNotIn(value[2], known)
                    known.add(value[2])
                    shown[value[2]] = value[3]
                else:
                    self.assertEqual(op, 0x4e40)
                    uid = npc_death.validate_frame(value)[1]
                    self.assertIn(uid, known)  # exit only for an NPC this client was shown
                    known.discard(uid)
                    removed.add(uid)

        # Narrowed rectangles put the seeded goblins farther north. Walk the
        # real route to y32874 so both original species enter the wire view.
        for _ in range(32):  # y32906 -> 32874; real seed5 placement, no forced spawn
            apply(await self.step(reader, writer, 0))
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        self.assertGreaterEqual(len(shown), 4)
        self.assertTrue(known)
        self.assertGreater(len(set(shown.values())), 1, shown)  # orc 56 and goblin 1022
        for _ in range(32):  # back south: everything leaves the screen
            apply(await self.step(reader, writer, 4))
        self.assertEqual(known, set())
        self.assertEqual(removed, set(shown))
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        self.assertFalse(self.broker._world.runtime.running)


if __name__ == '__main__':
    unittest.main()
