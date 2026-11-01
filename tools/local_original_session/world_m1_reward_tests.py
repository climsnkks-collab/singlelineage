"""M1 step 4 wiring: kill -> EXP/level SC4E38(f26), drops -> ground 4E96, pickup 4E3E
-> ground 4E40 + pickup action 4E39 + kit inventory 0964/0965.

Pure WorldView checks and real PersistentBroker loopback checks (same fixture as
world_spawn_tests.BrokerWorldTests). ``enable_world_kit`` is the loopback stand-in
for the launcher's native-observed kit delivery: it grants the class starter kit
row and adopts it as the current inventory frame, which is what the kit potion
and pickup paths read. It is a test harness, not a product configuration.
"""
import asyncio
import json
import random
import struct
import unittest
from unittest import mock

from tools.local_entry_server import protobuf as pb
from tools.local_original_session import broker as b, inventory, inventory_store, inventory_update
from tools.local_original_session import world_combat as wc, world_spawn_tests as wst, world_visibility as wv
from tools.local_original_session.broker_tests import c2s, response
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_progress import Progress, ProgressStore, exp_percent

ADENA = 7


def _varint(body, i):
    value = shift = 0
    while True:
        byte = body[i]
        i += 1
        value |= (byte & 0x7f) << shift
        shift += 7
        if byte < 0x80:
            return value, i


def status_values(wire):
    """Flat protobuf body -> {field: last value}; wire1 is read as the f26 double."""
    body, out, i = wire[4:-2], {}, 0
    while i < len(body):
        key, i = _varint(body, i)
        number, kind = key >> 3, key & 7
        if kind == 0:
            value, i = _varint(body, i)
        elif kind == 1:
            value = struct.unpack_from('<d', body, i)[0]
            i += 8
        elif kind == 2:
            size, i = _varint(body, i)
            value = bytes(body[i:i + size])
            i += size
        elif kind == 5:
            value = struct.unpack_from('<I', body, i)[0]
            i += 4
        else:
            raise ValueError('wire type')
        out[number] = value
    return out


def opcode(wire):
    return int.from_bytes(wire[2:4], 'little')


def ground_notices(frames, world):
    """Match received ground actors to the world's actual item identities."""
    values = [status_values(w) for w in frames if opcode(w) == 0x4e96]
    return [fields for fields in values if fields.get(39) == 0
            and (entity := world.entities.get(fields[2])) is not None
            and entity.kind is Kind.ITEM]


def get_payload(x, y, uid, quantity):
    child = b''.join(pb.encode_varint(n << 3) + pb.encode_varint(v & ((1 << 64) - 1))
                     for n, v in ((1, x), (2, y), (3, uid), (4, quantity)))
    return pb.encode_bytes(1, child)


def enable_world_kit(broker, character_class, uid=1, *, without=()):
    """Grant the class starter kit row and make it the current kit frame (harness)."""
    store = inventory_store.InventoryStore(broker.realm.store.path, policy=inventory_store.POLICY,
                                           kit_policy=inventory.KIT_POLICY)
    frame = broker._inventory_kit_frame(character_class)
    if without:
        frame = inventory.build_kit_frame([dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)
                                           if dict(item.raw_fields)[2] & 0xffffffff not in without])
    store.grant(uid, frame)
    broker._inventory_store = store
    broker._inventory_kit_policy = inventory.KIT_POLICY
    broker._inventory_current_frame = frame
    broker.policy.inventory_add = True
    broker.policy.item_kit = True
    return store, frame


def kit_items(frame):
    return {dict(item.raw_fields)[2] & 0xffffffff: dict(item.raw_fields) for item in inventory.validate_kit_frame(frame)}


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class WorldRewardTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.view = wv.WorldView.create(passable=lambda *_: True, clock=self.clock, rng=random.Random(4))
        self.view.ground.passable = lambda *_: True
        from tools.local_native_login_self_actor_hook import hook as actor_hook
        fields = self.fields = dict(actor_hook.profiles()[0].fields)
        profile = wc.PcProfile(level=1, character_class=1, gender=0, strength=18, dexterity=12, con=16, wis=9)
        self.assertIsNone(self.view.bind_pc(1, profile, fields))  # fresh EXP 0: no extra status
        self.view.update_pc(1, 0, 32590, 32880)
        # Exercise the original guaranteed Adena rows, independently of added
        # non-reward population occupying the same field.
        self.target = next(e for e in self.view.entities.near(0, 32590, 32880, 40, kind=Kind.NPC)
                           if e.template_id in (0, 245))
        self.view.ai.drop(self.target.uid)
        self.view.entities.move(self.target.uid, 0, 32590, 32879)
        self.view.update_pc(1, 0, 32590, 32880)  # the client now shows the moved monster
        self.view.drain(1)

    def kill(self):
        state = self.view.combat.pcs[1]
        state.next_attack_at = 0
        with mock.patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 999)):
            return self.view.pc_attack(1, self.target.uid)

    def test_kill_sends_exp_status_and_drops_adena_on_the_ground(self):
        frames = self.kill()
        statuses = [status_values(w) for w in frames if opcode(w) == 0x4e38]
        self.assertEqual(len(statuses), 1)
        monster = self.view.spawner.monster_for(self.target.uid)
        self.assertEqual(self.view.exp[1], monster.kill_exp)
        self.assertEqual(statuses[0][2], 1)
        self.assertAlmostEqual(statuses[0][26], exp_percent(self.view.data, monster.kill_exp, 1))
        self.assertEqual(self.view.progress_dirty[1].exp, monster.kill_exp)
        # f9 now carries the real client item name. The actual item UID also
        # distinguishes ground actors from orcs, whose template f39 is zero.
        items = ground_notices(frames, self.view)
        self.assertTrue(items)  # orc/goblin adena row has chance 1,000,000
        adena = [v for v in items if v[3] == wv.item_gfx()[ADENA][1]]
        self.assertEqual(len(adena), 1)
        self.assertTrue(10 <= adena[0][7] <= 30)
        self.assertEqual(len(self.view.ground), len(items))
        # Monster death comes before the reward status.
        order = [opcode(w) for w in frames]
        self.assertLess(order.index(0x4e39), order.index(0x4e38))

    def test_level_up_raises_level_and_max_hp_once(self):
        self.view.exp[1] = self.view.data.pc_exp[1] - 1  # one EXP short of level 2
        before = self.view.combat.pcs[1].max_hp
        frames = self.kill()
        status, = [status_values(w) for w in frames if opcode(w) == 0x4e38]
        self.assertEqual(status[2], 2)
        self.assertGreater(status[11], before)
        self.assertEqual(self.view.combat.pcs[1].profile.level, 2)
        self.assertEqual(self.view.progress_dirty[1].level, 2)
        self.assertEqual(status[10], self.view.combat.pcs[1].hp)  # no refill policy

    def test_pickup_commits_before_consuming_and_removes_from_screen(self):
        frames = self.kill()
        uid = next(values[2] for values in ground_notices(frames, self.view))
        item = self.view.ground.get(self.view.entities.get(uid).ref)
        calls = []

        def fail(item, count):
            raise ValueError('WORLD_PICKUP_INVENTORY_FULL')
        with self.assertRaises(ValueError):
            self.view.pc_pickup(1, uid, item.count, fail)
        self.assertIsNotNone(self.view.ground.get(item.ref))  # stays on the ground

        def commit(item, count):
            calls.append((item.item_id, count))
            return [b'INVENTORY']
        out = self.view.pc_pickup(1, uid, item.count, commit)
        self.assertEqual(calls, [(item.item_id, item.count)])
        self.assertEqual(out[-1], b'INVENTORY')
        self.assertIn(wv.remove_frame(uid), out)
        self.assertLess(out.index(wv.remove_frame(uid)), out.index(b'INVENTORY'))
        self.assertIsNone(self.view.ground.get(item.ref))
        self.assertIsNone(self.view.pc_pickup(1, 0x7ffffff0, 1, commit))  # not a world item

    def test_other_pc_owner_priority_and_expiry_removal(self):
        frames = self.kill()
        uid = next(values[2] for values in ground_notices(frames, self.view))
        profile = wc.PcProfile(level=1, character_class=0, gender=0, strength=13, dexterity=10)
        self.view.bind_pc(2, profile, self.fields)
        self.view.update_pc(2, 0, 32590, 32881)
        self.view.drain(2)
        out = self.view.pc_pickup(2, uid, 1, lambda *_: self.fail('no commit inside owner priority'))
        self.assertNotIn(wv.remove_frame(uid), out)
        self.clock.now += 601
        asyncio.run(self.view.runtime.tick_once())
        self.assertIn(wv.remove_frame(uid), self.view.drain(1))
        self.assertIn(wv.remove_frame(uid), self.view.drain(2))
        self.assertEqual(len(self.view.ground), 0)

    def test_ground_items_do_not_block_monster_steps_or_spawns(self):
        self.kill()
        item = next(iter(self.view.ground._items.values()))
        self.assertTrue(self.view.ai._free(item.map_id, item.x, item.y, 0))
        self.assertFalse(self.view.spawner._occupied(item.map_id, item.x, item.y))


class ProgressStoreTests(unittest.TestCase):
    def test_round_trip_and_baseline(self):
        import tempfile
        from pathlib import Path
        from tools.local_original_session.world_progress import Progress
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'characters.json'
            store = ProgressStore(path)
            self.assertEqual(store.get(1), Progress(0, 1))
            for value in (Progress(130, 2, 35, 12), Progress(810016, 30, 550, 100),
                          Progress(55810962, 50, 900, 150),
                          Progress(1823000470, 99, 1750, 200)):
                with self.subTest(level=value.level):
                    store.commit(1, value)
                    self.assertEqual(ProgressStore(path).get(1), value)


class PotionDeadTests(unittest.TestCase):
    def test_dead_world_pc_potion_is_blocked_before_any_store_change(self):
        from tools.local_original_session.item_equipment_effect import ItemEquipmentEffect
        effect = object.__new__(ItemEquipmentEffect)
        writer = object()

        class Combat:
            def is_dead(self, uid):
                return True

        class Broker:
            _world_pcs = {id(writer): (writer, 1)}
            _world = type('W', (), {'combat': Combat()})()

            def _world_bound(self, w):
                return w is writer

            @property
            def _inventory_store(self):
                raise AssertionError('store touched')
        effect.broker = Broker()
        receipt = dict(persist_attempted=False, write_attempted=False)
        result = asyncio.run(effect._consume_potion(writer, dict(item=None, frame=None, row=None), receipt, None))
        self.assertEqual((result['status'], result['reason']), ('BLOCKED', 'ITEM_USE_POTION_PLAYER_DEAD'))


class BrokerRewardTests(wst.BrokerWorldTests):
    test_walk_north_shows_mobs_and_walk_back_removes_them = None
    test_quit_ack_then_late_alive_closes_normally = None

    async def until_alive(self, reader, writer, *wires):
        for wire in wires + (c2s(b.ALIVE_REQUEST),):
            writer.write(wire)
        await writer.drain()
        frames = []
        while True:
            wire = await response(reader)
            if wire == b.ALIVE_FRAME:
                return frames
            frames.append(wire)

    async def read_item_descriptions(self, reader, items):
        """Complete the known kit changes published after the Alive response."""
        from tools.local_original_session.world_feature_iteminfo import backend_descriptions
        for item in items:
            fields = dict(item.raw_fields)
            name = fields[18] or wv.item_names()[item.template_bits]
            count = fields[4]
            display = name + (b' (' + str(count).encode('ascii') + b')' if count > 1 else b'')
            descriptions = backend_descriptions(item, self.broker._world.data.items.get(item.template_bits))
            wire = await response(reader)
            self.assertEqual(opcode(wire), 0x0977)
            with pb.parse_message(wire[4:-2]) as message:
                self.assertEqual([field.number for field in message.fields],
                                 [1, 2, *([3] * len(descriptions)), 4])
                self.assertEqual(message.occurrences(1)[0].value, item.identifier)
                self.assertEqual(bytes(message.occurrences(2)[0].value), display)
                self.assertEqual(message.occurrences(4)[0].value, count)
                received = []
                for field in message.occurrences(3):
                    with pb.parse_message(bytes(field.value)) as child:
                        self.assertEqual([field.number for field in child.fields], [1, 2])
                        received.append((child.occurrences(1)[0].value,
                                         bytes(child.occurrences(2)[0].value)))
                self.assertEqual(tuple(received), descriptions)

    async def kill_adjacent(self, reader, writer):
        world = self.broker._world
        world.ground.passable = lambda *_: True
        service = self.broker.realm.service(self.broker._claims[12000][-1]['writer'])
        pos = service.snapshot()

        def place():
            # A spawner-owned monster; registered town NPCs are NPC entities too.
            target = next(e for e in world.entities.near(0, pos.word0, pos.word1, 60, kind=Kind.NPC)
                          if e.template_id in (0, 245) and world.town.npc_for(e.uid) is None)
            world.ai.drop(target.uid)
            world.runtime.scheduler.cancel_owner(target.ref)
            world.entities.move(target.uid, 0, pos.word0, pos.word1 - 1)
            world.combat.pcs[1].next_attack_at = 0
            # Screen refresh for the teleported monster, delivered with the swing.
            world.outbox.setdefault(1, []).extend(world.update_pc(1, 0, pos.word0, pos.word1))
            return target.uid
        uid = await world.runtime.dispatch_now(place)  # groups near the start point are active
        with mock.patch.object(wc, 'pc_hits_npc', return_value=wc.Swing(True, 999)):
            frames = await self.until_alive(reader, writer,
                                            c2s(b.ATTACK_REQUEST, pb.encode_message([pb.encode_uint32(1, uid)])))
        return uid, frames

    async def test_kill_drop_pickup_into_kit_inventory_and_saved_progress(self):
        reader, writer = await self.selected()
        store, kit = enable_world_kit(self.broker, 0, without=(ADENA,))
        self.assertNotIn(ADENA, kit_items(kit))
        uid, frames = await self.kill_adjacent(reader, writer)
        # This harness installs the initial kit after selection. The following
        # Alive ACK precedes iteminfo's after_request publication, so finish its
        # exact three owned descriptions before sending the pickup request.
        await self.read_item_descriptions(reader, inventory.validate_kit_frame(kit))
        ops = [opcode(w) for w in frames]
        self.assertIn(0x4e39, ops)
        status = status_values(next(w for w in frames if opcode(w) == 0x4e38))
        self.assertGreater(status[26], 0)
        # Ordinary kill EXP is immediately authoritative in memory, with its
        # latest absolute snapshot pending until the normal save boundary.
        persist = self.broker._world_persist
        self.assertEqual(self.broker._world_progress.get(1).exp, self.broker._world.exp[1])
        self.assertEqual(persist.snapshot(('progress', 1)).exp, self.broker._world.exp[1])
        self.assertEqual(ProgressStore(self.broker.realm.store.path).get(1).exp, 0)
        ground = ground_notices(frames, self.broker._world)
        adena = next(v for v in ground if v[3] == wv.item_gfx()[ADENA][1])
        x, y = adena[1] & 0xffff, adena[1] >> 16
        got = await self.until_alive(reader, writer, c2s(0x4e3e, get_payload(x, y, adena[2], adena[7])))
        self.assertEqual([opcode(w) for w in got], [0x4e40, 0x4e39, 0x0964], got)
        self.assertEqual(status_values(got[0])[1], adena[2])
        self.assertEqual(status_values(got[1]), {1: 1, 2: 15})
        held = kit_items(store.restore(1))[ADENA]
        self.assertEqual(held[4], adena[7])
        await self.read_item_descriptions(reader, tuple(item for item in
            inventory.validate_kit_frame(store.restore(1)) if item.template_bits == ADENA))
        # Creating the first Adena instance is an immediate boundary, including
        # settlement of the preceding kill's pending character snapshot.
        self.assertEqual(ProgressStore(self.broker.realm.store.path).get(1).exp,
                         self.broker._world.exp[1])
        self.assertIs(self.broker._inventory_current_frame, self.broker._inventory_current_frame)
        self.assertEqual(kit_items(self.broker._inventory_current_frame)[ADENA][4], adena[7])
        # Second kill: the adena stack grows with SC0965 (absolute count).
        uid2, frames2 = await self.kill_adjacent(reader, writer)
        ground2 = ground_notices(frames2, self.broker._world)
        adena2 = next(v for v in ground2 if v[3] == wv.item_gfx()[ADENA][1])
        got2 = await self.until_alive(reader, writer, c2s(0x4e3e, get_payload(
            adena2[1] & 0xffff, adena2[1] >> 16, adena2[2], adena2[7])))
        self.assertEqual([opcode(w) for w in got2], [0x4e40, 0x4e39, 0x0965], got2)
        self.assertEqual(status_values(got2[0])[1], adena2[2])
        self.assertEqual(status_values(got2[1]), {1: 1, 2: 15})
        await self.read_item_descriptions(reader, tuple(item for item in
            inventory.validate_kit_frame(store.restore(1)) if item.template_bits == ADENA))
        update = inventory_update.validate_frame(got2[2])
        self.assertEqual(dict(update.raw_fields)[4], adena[7] + adena2[7])
        self.assertEqual(kit_items(store.restore(1))[ADENA][4], adena[7] + adena2[7])
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        report = self.broker.report()['world']
        self.assertEqual((report['kills'], report['pickups']), (2, 2))
        final_exp = self.broker._world.exp[1]
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        self.assertEqual(ProgressStore(self.broker.realm.store.path).get(1).exp,
                         final_exp)
        self.assertEqual(persist.pending_keys, ())

    async def test_saved_exp_is_shown_on_the_next_selection(self):
        # This broker has already loaded its profile. Seed through that same
        # owner rather than mutate the file behind its in-memory authority.
        self.broker._world_progress.commit(1, Progress(200, 2, 31, 12))
        reader, writer = await self.selected()
        # selected() consumed ACK/map/SelfInfo/actor; the saved f26 status follows.
        wire = await response(reader)
        values = status_values(wire)
        self.assertEqual((opcode(wire), values[2], values[11]), (0x4e38, 2, 31))
        self.assertAlmostEqual(values[26], exp_percent(self.broker._world.data, 200, 2))
        self.assertEqual(self.broker._world.combat.pcs[1].profile.level, 2)
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)

    async def test_potion_sends_older_queued_frames_first(self):
        reader, writer = await self.selected()
        await self.until_alive(reader, writer)  # town NPC entry frames queued at selection
        enable_world_kit(self.broker, 0)
        world = self.broker._world
        row = self.broker._claims[12000][-1]
        state = world.combat.pcs[1]
        state.hp = 5
        older = wc.status_frame(state.status_fields, 5)
        world.outbox.setdefault(1, []).append(older)
        wire = inventory_update._encode(inventory_update._values({1: 77, 4: 3}))
        with mock.patch.object(self.broker._world_item_effects.rng, 'randint', return_value=6) as roll, \
                mock.patch.object(world.combat, 'heal', side_effect=AssertionError('legacy potion path')):
            async with row['operation_lock']:
                result = await self.broker._world_potion_locked(row['writer'], row, wire, 14)
        roll.assert_called_once_with(6, 27)
        got = [await response(reader) for _ in range(4)]
        self.assertEqual(got[0], older)
        self.assertEqual(got[1], wire)
        # Leading 4ED8 use effect (S_SkillSound) precedes the status frame.
        self.assertEqual(opcode(got[2]), 0x4ed8)
        self.assertEqual(opcode(got[3]), 0x4e38)
        expected = min(state.max_hp, 11)
        self.assertEqual(status_values(got[3])[10], expected)
        self.assertEqual(result, dict(healed_hp=expected - 5, hp_after=expected))
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)

    async def test_dead_pc_move_is_ignored_and_not_saved(self):
        reader, writer = await self.selected()
        world = self.broker._world
        service = self.broker.realm.service(self.broker._claims[12000][-1]['writer'])
        start = service.snapshot()
        state = world.combat.pcs[1]
        state.hp, state.dead = 0, True
        frames = await self.until_alive(reader, writer, c2s(0x4e2b, pb.encode_message(
            [pb.encode_uint32(1, start.packed), pb.encode_uint32(2, 0)])))
        self.assertNotIn(0x4ee0, [opcode(w) for w in frames])
        self.assertEqual(service.snapshot(), start)
        self.assertEqual(self.broker.realm.positions.restore(start), start)
        self.assertFalse(self.broker.failure.is_set(), self.broker.report())
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)

    async def test_failed_town_save_keeps_the_pending_return(self):
        broker = self.broker
        broker.realm.store.create(b.ack.realm.Creation('SoloKnight', 0, 0, (13,) * 6))
        x, y = b.movement.authority.unpack_grid(broker.realm._actor_fields[1])
        broker.realm.positions.commit(b.movement.Position(1, 'SoloKnight', 0, x, y),
                                      b.movement.Position(1, 'SoloKnight', 0, 32595, 32906))
        broker._world_respawn[1] = 'SoloKnight'
        with mock.patch.object(broker.realm.positions, 'commit', side_effect=OSError('locked')):
            self.assertFalse(broker._world_commit_respawn(1))
            self.assertIn(1, broker._world_respawn)
            with self.assertRaises(OSError):
                broker._world_commit_respawn(1, strict=True)
            self.assertIn(1, broker._world_respawn)
        self.assertTrue(broker._world_commit_respawn(1))
        self.assertNotIn(1, broker._world_respawn)
        town = broker._world.data.town
        saved = broker.realm.positions.restore(b.movement.Position(1, 'SoloKnight', 0, 1, 1))
        self.assertEqual((saved.word0, saved.word1), (town.respawn_x, town.respawn_y))


class KitCapacityTests(wst.BrokerWorldTests):
    """Bag = L1J 180 kinds; a saved kit row above one 0964 frame goes out split."""
    test_walk_north_shows_mobs_and_walk_back_removes_them = None
    test_quit_ack_then_late_alive_closes_normally = None

    def item(self, item_id, stackable=False):
        from types import SimpleNamespace
        return SimpleNamespace(item_id=item_id, stackable=stackable)

    async def test_pickup_keeps_rolled_grade_and_separates_scroll_stacks(self):
        from types import SimpleNamespace
        from tools.local_original_session import inventory, world_enchant_inventory as enchant
        await self.selected()
        store, _ = enable_world_kit(self.broker, 1)
        server = self.broker._claims[12000][-1]['writer']
        for grade in (0, 1, 2, 2):
            self.broker._world_pickup_commit(server,
                SimpleNamespace(item_id=25, stackable=True, grade=grade), 1)
        scrolls = [item for item in inventory.validate_kit_frame(store.restore(1))
                   if item.template_bits == 25]
        counts = {grade: sum(dict(item.raw_fields)[4] for item in scrolls
                            if enchant.scroll_grade(item) == grade) for grade in (0, 1, 2)}
        self.assertEqual(counts, {0: 1, 1: 1, 2: 2})
        for grade in (0, 1, 2):
            self.broker._world_pickup_commit(server,
                SimpleNamespace(item_id=40, stackable=False, grade=grade), 1)
        equipment = [item for item in inventory.validate_kit_frame(store.restore(1))
                     if item.template_bits == 40]
        self.assertEqual([item.bless for item in equipment], [0, 1, 2])
        self.assertTrue(all(enchant.enchant_level(item, self.broker._world.data.items[40]) == 0
                            for item in equipment))

    async def test_twenty_plus_new_drop_kinds_fit_and_go_out_as_split_0964_frames(self):
        await self.selected()
        store, kit = enable_world_kit(self.broker, 1)
        server = self.broker._claims[12000][-1]['writer']
        held = list(kit_items(kit))
        # Keep this M1 split-frame fixture on its original table. Optional gfx
        # extensions now contain more templates than the real 180-slot bag.
        base_gfx = json.loads(wv.ITEM_GFX_PATH.read_text(encoding='utf-8'))['items']
        ids = [int(i) for i in base_gfx if int(i) not in held]
        self.assertGreaterEqual(len(ids), 20)
        for item_id in ids:
            frames = self.broker._world_pickup_commit(server, self.item(item_id), 1)
            self.assertEqual([opcode(w) for w in frames], [0x0964])
        current = self.broker._inventory_current_frame
        self.assertEqual(store.restore(1), current)
        self.assertEqual(inventory_store.InventoryStore(self.broker.realm.store.path, policy=inventory_store.POLICY,
                                                        kit_policy=inventory.KIT_POLICY).restore(1), current)
        items = inventory.validate_kit_frame(current)
        self.assertEqual([dict(i.raw_fields)[2] for i in items], held + ids)
        self.assertGreater(len(current), inventory.MAX_FRAME)
        wires = inventory.kit_wire_frames(current)
        self.assertGreater(len(wires), 1)
        self.assertTrue(all(len(w) <= inventory.MAX_FRAME and opcode(w) == 0x0964 for w in wires))
        self.assertEqual([i for w in wires for i in inventory.validate_kit_frame(w)], list(items))
        self.assertEqual(inventory.kit_wire_frames(kit), (kit,))  # a row that fits is unchanged
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)

    async def test_bag_holds_l1j_180_kinds_then_keeps_new_kinds_on_the_ground(self):
        await self.selected()
        _, keys, _ = inventory._source()
        templates = sorted(k for k in keys if k != ADENA and k < (1 << 31) and k not in wv.item_gfx())
        rows = [{**b.INVENTORY_STARTER_FIELDS, 1: 1000 + i, 2: t}
                for i, t in enumerate(templates[:inventory.KIT_MAX_ITEMS - 1])]
        # Stack compatibility preserves opaque properties, including the icon.
        # Use the real Adena icon rather than the starter weapon's icon.
        rows.append({**b.INVENTORY_STARTER_FIELDS, 1: 5000, 2: ADENA, 4: 10,
                     7: self.broker._world.data.items[ADENA].icon})
        frame = inventory.build_kit_frame(rows)
        store = inventory_store.InventoryStore(self.broker.realm.store.path, policy=inventory_store.POLICY,
                                               kit_policy=inventory.KIT_POLICY)
        store.grant(1, frame)
        self.broker._inventory_store, self.broker._inventory_kit_policy = store, inventory.KIT_POLICY
        self.broker._inventory_current_frame = frame
        server = self.broker._claims[12000][-1]['writer']
        new_kind = next(i for i in wv.item_gfx() if i != ADENA)
        with self.assertRaisesRegex(ValueError, 'WORLD_PICKUP_INVENTORY_FULL'):
            self.broker._world_pickup_commit(server, self.item(new_kind), 1)
        self.assertEqual(store.restore(1), frame)
        frames = self.broker._world_pickup_commit(server, self.item(ADENA, stackable=True), 5)
        self.assertEqual([opcode(w) for w in frames], [0x0965])
        self.assertEqual(kit_items(store.restore(1))[ADENA], {**rows[-1], 4: 15})
        self.assertEqual(len(inventory.validate_kit_frame(store.restore(1))), inventory.KIT_MAX_ITEMS)
        result = await self.broker.close()
        self.assertTrue(result['cleanup_complete'], result)


if __name__ == '__main__':
    unittest.main()
