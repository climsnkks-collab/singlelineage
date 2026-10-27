"""Short fake-clock checks for monster AI and world melee combat, plus one broker loopback run."""
import asyncio
import random
import time
import unittest

from tools.local_entry_server import protobuf as pb
from tools.local_game_session import session
from tools.local_native_login_self_actor_hook import hook as actor_hook
from tools.local_original_session import npc_ai, world_combat as wc, world_interest_spawn as wis
from tools.local_original_session import broker as b, world_spawn_tests as wst, world_visibility as wv
from tools.local_original_session.broker_tests import c2s
from tools.local_original_session.world_entities import Kind
from tools.local_movement_session_route.route import authority

NEAR_ORC = (0, 32590, 32880)  # inside the orc/goblin rectangles
PC = 1


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class GridTerrain:
    """Stand-in terrain: a tile is walkable unless ``blocked(x, y)``."""

    def __init__(self, blocked=lambda x, y: False):
        self.blocked = blocked

    def can_step(self, map_id, x, y, heading):
        dx, dy = npc_ai.DELTAS[heading]
        return not self.blocked(x + dx, y + dy)

    def passable(self, map_id, x, y):
        return not self.blocked(x, y)


def status_hp(wire):
    """4E38 f10 current HP; kill-reward 4E38 also carries the f26 double (wire1)."""
    body, i = wire[4:-2], 0
    while i < len(body):
        key = shift = 0
        while True:
            byte = body[i]; i += 1
            key |= (byte & 0x7f) << shift; shift += 7
            if byte < 0x80:
                break
        if key & 7 == 1:
            i += 8
            continue
        value = shift = 0
        while True:
            byte = body[i]; i += 1
            value |= (byte & 0x7f) << shift; shift += 7
            if byte < 0x80:
                break
        if key & 7 == 2:
            i += value
        elif key >> 3 == 10:
            return value
    return None


def varints(wire):
    """Flat varint protobuf body -> {field: value} (every frame used here is flat)."""
    body, out, i = wire[4:-2], {}, 0
    while i < len(body):
        key = shift = 0
        while True:
            byte = body[i]; i += 1
            key |= (byte & 0x7f) << shift; shift += 7
            if byte < 0x80:
                break
        value = shift = 0
        while True:
            byte = body[i]; i += 1
            value |= (byte & 0x7f) << shift; shift += 7
            if byte < 0x80:
                break
        out[key >> 3] = value
    return out


def opcode(wire):
    return int.from_bytes(wire[2:4], 'little')


def status_hp(wire):
    """SC4E38 f10; kill statuses also carry the f26 EXP double (wire1) the codecs reject."""
    from tools.local_original_session.world_m1_reward_tests import status_values
    return status_values(wire)[10]


def status_fields(hp):
    fields = dict(actor_hook.profiles()[0].fields)
    fields[10] = fields[11] = hp
    return fields


class AiTests(unittest.TestCase):
    def make(self, terrain, seed=3, hp=500):
        self.clock = FakeClock()
        self.view = wv.WorldView.create(terrain=terrain, clock=self.clock, rng=random.Random(seed))
        self.view.bind_pc(PC, wc.PcProfile(level=1, character_class=1, gender=0, strength=13,
                                           dexterity=13, weapon=wc.ATHAME), status_fields(hp))
        self.frames = []
        self.view.update_pc(PC, *NEAR_ORC, reset=True)

    def advance(self, seconds, each=None):
        end = self.clock.now + seconds
        while self.clock.now < end:
            self.clock.now += 0.15
            self.view.runtime.scheduler.run_due(self.clock.now)
            self.view.tick(self.clock.now)
            self.frames += [(self.clock.now, w) for w in self.view.drain(PC)]
            if each is not None and each():
                return True
        return False

    def orc(self):
        group = next(g for g in self.view.spawner.groups if g.spec.group_id == 'm1_orc')
        return self.view.entities.get(group.slots[0].uid), group.slots[0]

    def place_pc(self, x, y):
        self.frames += [(self.clock.now, w) for w in self.view.update_pc_and_drain(PC, 0, x, y)]

    def next_to(self, entity):
        for dx, dy in npc_ai.DELTAS:
            x, y = entity.x + dx, entity.y + dy
            if not self.view.entities.near(0, x, y, 0) and self.view.terrain.passable(0, x, y):
                return x, y
        self.fail('no free tile next to the monster')

    def test_wander_uses_walkable_tiles_only(self):
        blocked = lambda x, y: x % 4 == 0  # every fourth column is a wall
        self.make(GridTerrain(blocked))
        homes = {b.uid: b.home for b in self.view.ai.brains.values()}
        self.assertTrue(homes)
        self.advance(90)
        moves = [varints(w) for _, w in self.frames if opcode(w) == 0x4e2c]
        self.assertGreater(len(moves), 5)
        for move in moves:  # SC4E2C reports the pre-step grid + heading
            x, y = authority.unpack_grid(move[2])
            dx, dy = npc_ai.DELTAS[move[3]]
            self.assertFalse(blocked(x + dx, y + dy))
        for entity in self.view.entities:
            if entity.kind is Kind.NPC:
                self.assertFalse(blocked(entity.x, entity.y))
                self.assertLessEqual(npc_ai.distance(entity.x, entity.y, *homes[entity.uid]),
                                     npc_ai.WANDER_RADIUS)
        self.assertEqual(len({(e.x, e.y) for e in self.view.entities}), len(list(self.view.entities)))

    def test_hit_then_chase_and_attack_on_interval(self):
        self.make(GridTerrain())
        orc, _ = self.orc()
        self.place_pc(*self.next_to(orc))
        frames = self.view.pc_attack(PC, orc.uid)
        self.assertEqual(opcode(frames[0]), 0x4e31)
        self.assertEqual(self.view.ai.brains[orc.uid].state, npc_ai.State.CHASE)
        self.place_pc(orc.x + 4, orc.y)  # step back: the monster has to walk
        self.advance(12)
        brain = self.view.ai.brains[orc.uid]
        self.assertEqual(brain.state, npc_ai.State.ATTACK)
        self.assertLessEqual(npc_ai.distance(orc.x, orc.y, *self.view.pcs[PC][1:]), 1)
        self.assertTrue(any(opcode(w) == 0x4e2c and varints(w)[1] == orc.uid for _, w in self.frames))
        swings = [t for t, w in self.frames if opcode(w) == 0x4e31 and varints(w)[2] == orc.uid]
        self.assertGreaterEqual(len(swings), 3)
        interval = self.view.spawner.monster_for(orc.uid).attack_interval_ms / 1000
        for a, b in zip(swings, swings[1:]):
            self.assertGreaterEqual(b - a + 1e-9, interval)
            self.assertLess(b - a, interval + 0.2)  # no skipped swings while adjacent
        hp = [session.world.decode_payload(0x4e38, w[4:-2])[10] for _, w in self.frames if opcode(w) == 0x4e38]
        self.assertTrue(hp and hp == sorted(hp, reverse=True) and hp[-1] < 500, hp)

    def test_pc_dies_at_zero_and_monster_returns(self):
        self.make(GridTerrain(), hp=6)
        orc, _ = self.orc()
        self.place_pc(*self.next_to(orc))
        self.view.pc_attack(PC, orc.uid)
        self.advance(30)
        self.assertEqual(self.view.combat.pcs[PC].hp, 0)  # HP1 stop policy replaced by death
        self.assertTrue(self.view.combat.is_dead(PC))
        self.assertNotEqual(self.view.ai.brains[orc.uid].target, PC)

    def test_leash_returns_home(self):
        self.make(GridTerrain())
        orc, _ = self.orc()
        self.place_pc(*self.next_to(orc))
        self.view.pc_attack(PC, orc.uid)
        brain = self.view.ai.brains[orc.uid]
        far = []

        def kite():  # keep the PC 6 tiles ahead (on screen) so the chase runs away from home
            if brain.state is npc_ai.State.RETURN:
                return True
            far.append(npc_ai.distance(orc.x, orc.y, *brain.home))
            self.place_pc(orc.x + 6, orc.y)
            return False

        self.assertTrue(self.advance(60, kite))
        self.assertEqual(max(far), self.view.spawner.monster_for(orc.uid).leash_range + 1)
        self.place_pc(orc.x + 6, orc.y)
        self.assertTrue(self.advance(40, lambda: brain.state is npc_ai.State.IDLE))
        self.assertLessEqual(npc_ai.distance(orc.x, orc.y, *brain.home), 1)
        self.assertIsNone(brain.target)

    def test_early_pc_attack_refused(self):
        self.make(GridTerrain())
        orc, _ = self.orc()
        self.place_pc(*self.next_to(orc))
        first = self.view.pc_attack(PC, orc.uid)
        self.assertEqual([opcode(w) for w in first if opcode(w) == 0x4e31], [0x4e31])
        self.clock.now += 0.5  # knight sword interval is 917ms
        self.assertFalse([w for w in self.view.pc_attack(PC, orc.uid) if opcode(w) == 0x4e31])
        self.clock.now += 0.45
        self.assertTrue([w for w in self.view.pc_attack(PC, orc.uid) if opcode(w) == 0x4e31
                         and varints(w)[2] == PC])

    def test_speed_potions_shorten_attack_interval_until_expiry(self):
        self.make(GridTerrain())
        items = self.view.data.items
        haste, brave = items[17].buff, items[296].buff
        speed = lambda percent: '0801120c0a04080010%02x0a04080110%02x' % (percent, percent)  # UID1, key0/key1
        orc, _ = self.orc()
        self.place_pc(*self.next_to(orc))
        first = self.view.apply_buff(PC, haste)
        self.assertEqual((opcode(first), first[4:-2].hex()), (wc.SPEED_OPCODE, speed(34)))  # 1/0.745 - 1
        self.view.pc_attack(PC, orc.uid)
        self.clock.now += 0.5  # unhasted knight would wait 917ms; 917 x 0.745 = 683ms
        self.assertFalse([w for w in self.view.pc_attack(PC, orc.uid) if opcode(w) == 0x4e31])
        self.clock.now += 0.2
        self.assertTrue([w for w in self.view.pc_attack(PC, orc.uid) if opcode(w) == 0x4e31
                         and varints(w)[2] == PC])
        start = self.clock.now
        self.assertEqual(self.view.apply_buff(PC, brave)[4:-2].hex(), speed(80))  # 0.745^2
        self.view.apply_buff(PC, haste)  # L1J Stacking: remaining + 300 (cap 1800)
        self.assertAlmostEqual(self.view.combat.pcs[PC].buffs['haste'][0] - start, 599.3, 1)
        self.frames.clear()
        self.advance(601)  # brave ends at +300 (haste left), haste at +599.3 (back to 0)
        self.assertEqual([w[4:-2].hex() for _, w in self.frames if opcode(w) == wc.SPEED_OPCODE],
                         [speed(34), speed(0)])
        self.assertEqual((self.view.combat.speed_factor(PC, self.clock.now), self.view.buffs), (1.0, {}))
        self.view.combat.set_profile(PC, wc.PcProfile(level=1, character_class=0, gender=0,
                                                      strength=13, dexterity=10))
        self.assertIsNone(self.view.apply_buff(PC, brave))  # non-knight: consumed without effect

    def test_kill_corpse_removal_and_respawn(self):
        self.make(GridTerrain(), seed=11)
        orc, slot = self.orc()
        group, _ = self.view.spawner.slot_for(orc.uid)
        old = orc.ref
        for _ in range(60):
            if npc_ai.distance(orc.x, orc.y, *self.view.pcs[PC][1:]) > 1:
                self.place_pc(*self.next_to(orc))
            self.frames += [(self.clock.now, w) for w in self.view.pc_attack(PC, orc.uid)]
            if not orc.alive:
                break
            self.advance(1.0)
        self.assertFalse(orc.alive)
        self.assertTrue(any(opcode(w) == 0x4e39 and varints(w)[1] == orc.uid for _, w in self.frames))
        self.assertEqual(slot.state, wis.SlotState.WAIT)
        self.assertNotIn(orc.uid, self.view.ai.brains)
        self.assertNotIn(orc.uid, self.view.runtime.scheduler._by_owner)
        self.assertFalse(self.view.entities.is_current(old))
        self.assertEqual(self.view.combat.kills[-1].npc_uid, orc.uid)
        self.frames.clear()
        self.advance(slot.corpse_at - self.clock.now + 0.2)
        removed = [varints(w)[1] for _, w in self.frames if opcode(w) == 0x4e40]
        self.assertIn(orc.uid, removed)
        self.assertIsNone(self.view.entities.get(orc.uid))
        self.advance(slot.respawn_at - self.clock.now + 0.2)
        self.assertEqual(slot.state, wis.SlotState.ALIVE)
        self.assertNotEqual(slot.uid, orc.uid)
        self.assertEqual(slot.hp, group.monster.hp)
        self.assertIn(slot.uid, self.view.ai.brains)


class BrokerCombatTests(wst.BrokerWorldTests):
    """Real PersistentBroker over loopback: wander frames unasked, swing, counterattack, death."""

    test_walk_north_shows_mobs_and_walk_back_removes_them = None  # runs in world_spawn_tests

    async def test_monster_moves_fights_back_and_dies(self):
        reader, writer = await self.selected()
        frames = []  # (monotonic, wire) of everything the client receives

        async def pump():
            while True:
                header = await reader.readexactly(2)
                frames.append((time.monotonic(), header + await reader.readexactly(
                    int.from_bytes(header, 'little') - 2)))

        task = asyncio.create_task(pump())
        broker = self.broker
        service = broker.realm.service(broker._claims[12000][-1]['writer'])

        async def request(*wires):
            alive = sum(w == b.ALIVE_FRAME for _, w in frames)
            for wire in wires + (c2s(b.ALIVE_REQUEST),):
                writer.write(wire)
            await writer.drain()
            for _ in range(300):
                if sum(w == b.ALIVE_FRAME for _, w in frames) > alive:
                    return
                await asyncio.sleep(.01)
            self.fail(('no alive reply', broker.report()['failure_code']))

        async def step(direction):
            start = service.snapshot()
            await request(c2s(0x4e2b, pb.encode_message([pb.encode_uint32(1, start.packed),
                                                          pb.encode_uint32(2, direction)])))

        def seen(op, fields):
            return [(t, varints(w)) for t, w in frames if opcode(w) == op
                    and all(varints(w).get(k) == v for k, v in fields.items())]

        try:
            for _ in range(26):  # into the orc/goblin rectangles
                await step(0)
            mark = len(frames)
            for _ in range(100):  # no requests: wandering must still reach the client
                if any(opcode(w) == 0x4e2c for _, w in frames[mark:]):
                    break
                await asyncio.sleep(.1)
            self.assertTrue(any(opcode(w) == 0x4e2c for _, w in frames[mark:]))
            world = broker._world
            pos = service.snapshot()
            shown = {varints(w)[2] for _, w in frames if opcode(w) == 0x4e96}
            target = min((world.entities.get(uid) for uid in shown
                          if world.entities.get(uid) is not None and world.entities.get(uid).alive),
                         key=lambda e: npc_ai.distance(e.x, e.y, pos.word0, pos.word1))
            uid = target.uid
            state = world.combat.pcs[1]  # PC can now die; keep it alive for the kill
            state.max_hp = state.hp = 500
            for _ in range(60):
                if not target.alive:
                    break
                pos = service.snapshot()
                if npc_ai.distance(target.x, target.y, pos.word0, pos.word1) > 1:
                    await step(npc_ai.heading_to(pos.word0, pos.word1, target.x, target.y))
                    continue
                await request(c2s(b.ATTACK_REQUEST, pb.encode_message([pb.encode_uint32(1, uid)])))
                await asyncio.sleep(1.05)  # royal fist swing interval 1000ms
            self.assertTrue(seen(0x4e31, {2: 1, 3: uid}), 'own swing')
            self.assertTrue(seen(0x4e39, {1: uid}), 'monster death')
            self.assertTrue(seen(0x4e31, {2: uid, 3: 1}), 'counterattack')
            hp = [status_hp(w) for _, w in frames[mark:] if opcode(w) == 0x4e38]
            self.assertTrue(hp and min(hp) < 500, hp)
            self.assertFalse(broker.failure.is_set(), broker.report())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        result = await broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        counts = {}
        for _, w in frames:
            counts[hex(opcode(w))] = counts.get(hex(opcode(w)), 0) + 1
        print('\nloopback frames by opcode:', counts, 'pc hp:', hp)


class EquipmentCombatTests(unittest.TestCase):
    """Worn items.json weapon/armour feed combat; potion heal and HP survive leave/rebind."""

    def test_worn_weapon_armour_heal_and_vitals(self):
        from tools.local_original_session.game_data import load_m1
        data = load_m1()
        combat = wc.WorldCombat(data, random.Random(7))
        dagger = wc.weapon_from_item(data.items[41])
        self.assertEqual((dagger.small, dagger.large, dagger.hit), (4, 2, 2))
        profile = wc.PcProfile(level=1, character_class=0, gender=0, strength=13, dexterity=10,
                               ac=wc.DEFAULT_PC_AC + data.items[103].ac, weapon=dagger)
        self.assertEqual(profile.ac, 9)
        orc = data.monsters[0]
        damages = [wc.pc_hits_npc(profile, orc, combat.rng) for _ in range(400)]
        landed = [s.damage for s in damages if s.landed]
        bonus = wc.STR_DMG[13]
        self.assertTrue(landed and max(landed) <= 4 + bonus and min(landed) >= 1)
        combat.bind_pc(PC, profile, status_fields(30))
        combat.pcs[PC].hp = 5
        healed, frame = combat.heal(PC, data.items[14].heal_hp)
        self.assertEqual(opcode(frame), wc.STATUS_OPCODE)
        self.assertEqual(combat.hp_of(PC), min(30, 5 + healed))
        combat.set_profile(PC, wc.PcProfile(level=1, character_class=0, gender=0, strength=13, dexterity=10))
        self.assertEqual(combat.pcs[PC].profile.ac, wc.DEFAULT_PC_AC)
        combat.forget_pc(PC)
        self.assertEqual(combat.hp_of(PC), min(30, 5 + healed))
        fields = status_fields(30)
        fields[10] = combat.hp_of(PC)
        state = combat.bind_pc(PC, profile, fields)
        self.assertEqual(state.hp, min(30, 5 + healed))


class LifeTests(unittest.TestCase):
    """Fake clock: 1s HP/MP recovery to max, PC death (frames, monsters let go, no recovery), revive."""

    def make(self, hp, *, level=10, con=12, wis=15, seed=3):
        self.clock = FakeClock()
        self.view = wv.WorldView.create(terrain=GridTerrain(), clock=self.clock, rng=random.Random(seed))
        fields = status_fields(hp)
        fields[12], fields[13] = 2, 10  # MP 2/10
        self.view.bind_pc(PC, wc.PcProfile(level=level, character_class=1, gender=0, strength=13,
                                           dexterity=13, weapon=wc.ATHAME, con=con, wis=wis), fields)
        self.frames = []
        self.view.update_pc(PC, *NEAR_ORC, reset=True)
        self.regen = self.view.data.town.regen

    advance = AiTests.advance
    orc = AiTests.orc
    place_pc = AiTests.place_pc
    next_to = AiTests.next_to

    def statuses(self):
        return [(t, session.world.decode_payload(0x4e38, w[4:-2])) for t, w in self.frames
                if opcode(w) == 0x4e38]

    def test_regen_ticks_every_second_up_to_max(self):
        self.make(hp=30)
        state = self.view.combat.pcs[PC]
        state.hp = 20
        start = self.clock.now
        hp_every = self.regen.hp_threshold(10) / self.regen.idle_points  # Lv10: 12 / 4 = 3 ticks
        self.advance(hp_every * 4 + 0.5)
        hp = [(round(t - start), f[10]) for t, f in self.statuses()]
        step = self.regen.hp_amount(12)  # 1 + (CON12 - 10) = 3
        self.assertEqual([v for _, v in hp][:4], [23, 26, 29, 30])
        self.assertEqual([t for t, _ in hp][:3], [3, 6, 9])
        self.assertEqual(step, 3)
        self.frames.clear()
        self.advance(20)  # MP: every 16 idle ticks (64 / 4), WIS15 -> +2; HP stays max
        after = self.statuses()
        self.assertTrue(after and all(f[10] == 30 for _, f in after))
        self.assertEqual([round(t - start) for t, _ in after], [16, 32])
        self.assertEqual([f[12] for _, f in after], [4, 6])
        self.assertEqual(state.mp, 6)
        state.hp = 30
        self.view.combat.pcs[PC].status_fields[12] = 10
        self.frames.clear()
        self.advance(40)
        self.assertEqual(self.statuses(), [])  # nothing to recover, nothing sent
        self.assertIn(PC, self.view.regen)

    def test_moving_and_fighting_slow_recovery(self):
        self.make(hp=30)
        state = self.view.combat.pcs[PC]
        state.hp = 10
        x, y = self.view.pcs[PC][1:]
        for i in range(12):  # move every tick: 2 points per tick instead of 4
            self.place_pc(x + (i % 2), y)
            self.advance(1.0)
        self.assertEqual(state.hp, 10 + 2 * self.regen.hp_amount(12))

    def test_death_frames_release_monsters_and_stop_recovery(self):
        self.make(hp=6, level=1, con=10)
        orc, _ = self.orc()
        self.place_pc(*self.next_to(orc))
        self.view.pc_attack(PC, orc.uid)
        self.assertTrue(self.advance(60, lambda: self.view.combat.is_dead(PC)))
        brain = self.view.ai.brains[orc.uid]
        self.assertIsNone(brain.target)
        self.assertIn(brain.state, (npc_ai.State.RETURN, npc_ai.State.IDLE))
        ops = [(opcode(w), varints(w)) for _, w in self.frames]
        zero = next(i for i, (op, f) in enumerate(ops) if op == 0x4e38
                    and session.world.decode_payload(0x4e38, self.frames[i][1][4:-2])[10] == 0)
        self.assertEqual(ops[zero + 1], (0x4e39, {1: PC, 2: 8}))  # run102: HP0 status, then own death
        self.assertNotIn(PC, self.view.regen)
        self.assertEqual(self.view.combat.hp_of(PC), 0)
        self.frames.clear()
        self.advance(40)
        self.assertFalse([w for _, w in self.frames if opcode(w) == 0x4e38])  # no recovery, no hits
        self.assertFalse([w for _, w in self.frames if opcode(w) == 0x4e31 and varints(w).get(3) == PC])
        self.assertFalse([w for w in self.view.pc_attack(PC, orc.uid) if opcode(w) == 0x4e31])
        healed, frame = self.view.combat.heal(PC, 15)
        self.assertEqual((healed, session.world.decode_payload(0x4e38, frame[4:-2])[10]), (0, 0))
        self.assertTrue(self.view.leave_pc(PC))  # restart: leaves dead, revived at max HP
        self.assertEqual(self.view.combat.hp_of(PC), 6)
        self.assertEqual(self.view.combat.mp_of(PC), 2)
        self.assertNotIn(PC, self.view.regen)


class BrokerLifeTests(wst.BrokerWorldTests):
    """Real broker over loopback with Restart on: death -> 4EEC -> 4E3B -> reselect in town."""

    test_walk_north_shows_mobs_and_walk_back_removes_them = None

    async def asyncSetUp(self):
        from tools.local_original_session import restart
        import tempfile, uuid
        from pathlib import Path
        self.temp = tempfile.TemporaryDirectory()
        self.uuid = str(uuid.uuid4())

        async def owner(peer):
            return True

        self.broker = b.PersistentBroker(sockets=wst.reserve(), listener_ports=wst.test_ports.listener_ports(), retained_owner=object(),
            owner_handle=object(), owner_job=object(), owner_guard=owner,
            owner_liveness_guard=lambda: True, source_guard=lambda: None,
            conversation_factory=wst.FixtureConversation, expected_uuid=self.uuid,
            store_path=Path(self.temp.name) / 'characters.json',
            edge_passability=lambda *_: True, world_policy=wv.POLICY, restart_policy=restart.POLICY)
        self.broker._world.spawner.rng = random.Random(5)
        self.clients = []
        await self.broker.start()

    async def test_death_restart_reselect_in_town(self):
        from tools.local_original_session import restart
        reader, writer = await self.selected()
        broker, world = self.broker, self.broker._world
        frames = []

        async def pump():
            while True:
                header = await reader.readexactly(2)
                frames.append(header + await reader.readexactly(int.from_bytes(header, 'little') - 2))

        task = asyncio.create_task(pump())

        def service():
            return broker.realm.service(broker._claims[12000][-1]['writer'])

        async def until(check, label, seconds=30):
            for _ in range(int(seconds * 20)):
                if check():
                    return
                await asyncio.sleep(.05)
            self.fail((label, broker.report()['failure_code']))

        async def request(*wires):
            alive = frames.count(b.ALIVE_FRAME)
            for wire in wires + (c2s(b.ALIVE_REQUEST),):
                writer.write(wire)
            await writer.drain()
            await until(lambda: frames.count(b.ALIVE_FRAME) > alive, 'alive reply')

        async def step(direction):
            start = service().snapshot()
            await request(c2s(0x4e2b, pb.encode_message([pb.encode_uint32(1, start.packed),
                                                          pb.encode_uint32(2, direction)])))

        try:
            for _ in range(26):  # into the orc/goblin rectangles
                await step(0)
            pos = service().snapshot()
            target = min((e for e in world.entities.near(0, pos.word0, pos.word1, 13, kind=Kind.NPC)),
                         key=lambda e: npc_ai.distance(e.x, e.y, pos.word0, pos.word1))
            world.combat.pcs[PC].hp = 1  # test input: the next landed blow is lethal
            for _ in range(80):
                if world.combat.is_dead(PC):
                    break
                pos = service().snapshot()
                if npc_ai.distance(target.x, target.y, pos.word0, pos.word1) > 1:
                    await step(npc_ai.heading_to(pos.word0, pos.word1, target.x, target.y))
                    continue
                await request(c2s(b.ATTACK_REQUEST, pb.encode_message([pb.encode_uint32(1, target.uid)])))
                await asyncio.sleep(.5)
            await until(lambda: any(opcode(w) == 0x4e39 and varints(w).get(1) == PC for w in frames),
                        'own death frame')
            zero = [i for i, w in enumerate(frames) if opcode(w) == 0x4e38
                    and status_hp(w) == 0]
            self.assertTrue(zero)
            self.assertEqual(varints(frames[zero[-1] + 1]), {1: PC, 2: 8})
            self.assertFalse([brain for brain in world.ai.brains.values() if brain.target == PC])
            self.assertNotIn(PC, world.regen)
            mark = len(frames)
            writer.write(c2s(b.DEAD_RESTART_REQUEST))  # the dead Restart button (body0)
            await writer.drain()
            await until(lambda: any(opcode(w) == b.RESTART_ACK for w in frames[mark:]), 'restart ack')
            ack = next(w for w in frames[mark:] if opcode(w) == b.RESTART_ACK)
            self.assertTrue(restart.validate_ack(ack, policy=restart.POLICY))
            await until(lambda: PC not in world.pcs, 'world leave')
            self.assertEqual(world.combat.hp_of(PC), world.combat.vitals[PC])
            mark = len(frames)
            writer.write(c2s(0x4e28, pb.encode_message([pb.encode_bytes(1, b'SoloKnight'),
                                                         pb.encode_uint32(2, 0), pb.encode_uint32(3, 0)])))
            await writer.drain()
            await until(lambda: [opcode(w) for w in frames[mark:]][:4] == [0x4e29, 0x4e95, 0x4e38, 0x4e96],
                        'reselect world entry')
            entry = frames[mark:mark + 4]
            selfinfo = session.world.decode_payload(0x4e38, entry[2][4:-2])
            actor = session.world.decode_payload(0x4e96, entry[3][4:-2])
            town = world.data.town
            self.assertEqual(selfinfo[10], selfinfo[11])
            self.assertEqual(authority.unpack_grid(actor[1]), (town.respawn_x, town.respawn_y))
            self.assertEqual(service().snapshot().metadata()['grid'], [town.respawn_x, town.respawn_y])
            saved = broker.realm.positions.restore(service().snapshot())
            self.assertEqual((saved.word0, saved.word1), (town.respawn_x, town.respawn_y))
            await until(lambda: PC in world.pcs and PC in world.regen, 'rebound in town')
            self.assertEqual(world.pcs[PC], (town.map_id, town.respawn_x, town.respawn_y))
            self.assertFalse(world.combat.is_dead(PC))
            await step(0)  # the new life plays on
            self.assertFalse(broker.failure.is_set(), broker.report())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        result = await broker.close()
        self.assertTrue(result['cleanup_complete'], result)
        print('\nlife loopback opcodes:', sorted({hex(opcode(w)) for w in frames}))


if __name__ == '__main__':
    unittest.main()
