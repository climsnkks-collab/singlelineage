"""Bounded pure-module regressions for WORLD_CODE_REVIEW; no broker/game/socket.

Fake clock and in-memory commit callbacks check local behavior only, not native
LOS, durable disk transactions, packet round trips or formal gameplay PASS.
"""
from dataclasses import replace
import random
import unittest

from tools.local_original_session.game_data import load_m1
from tools.local_original_session import world_combat as wc
from tools.local_original_session.npc_ai import DELTAS, local_line_clear
from tools.local_original_session.world_entities import Kind
from tools.local_original_session.world_interest_spawn import Group, InterestSpawner, Slot, SlotState
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_visibility import WorldView

DATA = load_m1()
STACK = next(item.template_id for item in DATA.items.values() if item.stackable)


class Terrain:
    def __init__(self, edge=True):
        self.edge = edge

    def passable(self, *_):
        return True

    def can_step(self, *_):
        return self.edge


class WorldReviewFixTests(unittest.TestCase):
    def make(self, terrain=True, *, absent=False):
        self.now = 0.0
        data = replace(DATA, spawns=())
        runtime = WorldRuntime(clock=lambda: self.now)
        spawner = InterestSpawner(runtime.entities, data, passable=lambda *_: True)
        view = WorldView(runtime, spawner, None if absent else Terrain(terrain),
                         data=data, rng=random.Random(7))
        pc = view.entities.add(Kind.PC, 0, 100, 100, uid=1)
        view.pcs[1] = (0, 100, 100)
        view.bind_pc(1, wc.PcProfile(20, 1, 0, 13, 13, weapon=wc.ATHAME),
                     {10: 100, 11: 100})
        return view, pc

    def target(self, view):
        monster = DATA.monsters[DATA.spawns[0].template_id]
        entity = view.entities.add(Kind.NPC, 0, 101, 100, template_id=monster.template_id)
        slot = Slot(0, SlotState.ALIVE, entity.uid, 10000, (101, 100))
        group = Group(DATA.spawns[0], monster, [slot], True)
        view.spawner._slots[entity.uid] = (group, slot)
        return entity, slot

    def test_pc_blocked_unknown_and_absent_terrain_do_not_spend_swing(self):
        for edge in (False, None):
            with self.subTest(edge=edge):
                view, _ = self.make(edge)
                target, slot = self.target(view)
                rng = view.combat.rng.getstate()
                self.assertFalse(view.ai._line_clear(0, 100, 100, 101, 100))
                self.assertEqual(view.pc_attack(1, target.uid), [])
                self.assertEqual(slot.hp, 10000)
                self.assertEqual(view.combat.pcs[1].next_attack_at, 0)
                self.assertEqual(view.combat.rng.getstate(), rng)
                self.assertEqual(view.combat.kills, [])
        view, _ = self.make(absent=True)
        target, slot = self.target(view)
        self.assertEqual(view.pc_attack(1, target.uid), [])
        self.assertEqual((slot.hp, view.combat.pcs[1].next_attack_at), (10000, 0))

    def test_pc_clear_local_edges_allow_swing_in_each_direction(self):
        for dx, dy in DELTAS:
            with self.subTest(dx=dx, dy=dy):
                view, _ = self.make()
                target, slot = self.target(view)
                view.entities.move(target.uid, 0, 100 + dx, 100 + dy)
                self.assertTrue(local_line_clear(view.terrain, 0, 100, 100, target.x, target.y))
                frames = view.pc_attack(1, target.uid)
                self.assertEqual(len(frames), 1)
                self.assertEqual(int.from_bytes(frames[0][2:4], 'little'), wc.ATTACK_OPCODE)
                self.assertLess(slot.hp, 10000)
                self.assertGreater(view.combat.pcs[1].next_attack_at, self.now)

    def drop(self, view):
        npc = view.entities.add(Kind.NPC, 0, 100, 100)
        view.entities.kill(npc.uid)
        item, = view.ground.spawn_drops(npc.ref, [(STACK, 10)], owner_uid=1)
        return npc, item

    def test_pickup_commit_crossing_expiry_consumes_and_returns_frames(self):
        view, _ = self.make()
        _, item = self.drop(view)
        self.now = item.expires_at - .01
        saved = []

        def commit(row, count):
            saved.append((row.item_id, count))
            self.now = item.expires_at + .01
            return [b'inventory-change']

        self.assertEqual(view.pc_pickup(1, item.ref.uid, 10, commit), [b'inventory-change'])
        self.assertEqual(saved, [(STACK, 10)])
        self.assertIsNone(view.ground.get(item.ref))
        self.assertEqual(view.runtime.scheduler.run_due(self.now), 1)  # only PC regen remains

    def test_pickup_failed_commit_and_expired_request_preserve_ground(self):
        view, _ = self.make()
        _, item = self.drop(view)

        def fail(*_):
            raise ValueError('INSERT_FAILED')

        with self.assertRaisesRegex(ValueError, 'INSERT_FAILED'):
            view.pc_pickup(1, item.ref.uid, 10, fail)
        self.assertEqual(view.ground.get(item.ref), item)
        self.now = item.expires_at
        self.assertEqual(view.pc_pickup(1, item.ref.uid, 10, fail), [])
        self.assertEqual(view.ground.get(item.ref), item)

    def test_late_regen_waits_full_interval_before_next_points(self):
        view, _ = self.make()
        state = view.combat.pcs[1]
        self.now = 10.0
        self.assertEqual(view.runtime.scheduler.run_due(), 1)
        points = (state.hp_points, state.mp_points)
        self.assertEqual(view.runtime.scheduler.next_deadline(), 11.0)
        self.now = 10.15
        self.assertEqual(view.runtime.scheduler.run_due(), 0)
        self.assertEqual((state.hp_points, state.mp_points), points)
        self.now = 11.0
        self.assertEqual(view.runtime.scheduler.run_due(), 1)
        self.assertEqual(view.runtime.scheduler.next_deadline(), 12.0)

    def test_leave_reenter_invalidates_refs_and_releases_all_occupancy(self):
        view, pc = self.make()
        old = pc.ref
        npc = view.entities.add(Kind.NPC, 0, 99, 100)
        self.assertFalse(view.ai._can_move(npc, 99, 100, 2))
        self.assertTrue(view.spawner._occupied(0, 100, 100))
        view.leave_pc(1)
        self.assertFalse(pc.alive)
        self.assertIsNone(view.entities.resolve(old))
        self.assertEqual(view.entities.near(0, 100, 100, 0, alive_only=False), [])
        self.assertTrue(view.ai._can_move(npc, 99, 100, 2))
        self.assertFalse(view.spawner._occupied(0, 100, 100))
        inactive = pc.ref
        self.assertEqual(view.update_pc(1, 0, 105, 100, reset=True), [])
        self.assertTrue(pc.alive)
        self.assertGreater(pc.generation, inactive.generation)
        self.assertIsNone(view.entities.resolve(inactive))
        self.assertEqual([e.uid for e in view.entities.near(0, 105, 100, 0)], [1])
        view.entities.kill(1)
        dead_ref = pc.ref
        view.leave_pc(1)
        self.assertIsNone(view.entities.resolve(dead_ref))
        self.assertEqual(view.entities.near(0, 105, 100, 0, alive_only=False), [])
        view.entities.remove(npc.uid)
        with self.assertRaisesRegex(ValueError, 'WORLD_UID_ALREADY_USED'):
            view.entities.add(Kind.NPC, 0, 99, 100, uid=npc.uid)

    def test_removed_corpse_once_markers_are_bounded_current_guard_survives(self):
        view, pc = self.make()
        for _ in range(10):
            npc, item = self.drop(view)
            self.assertEqual(view.ground._spawned, {npc.ref})
            view.ground.pickup(pc.ref, item.ref, 10)
            with self.assertRaisesRegex(ValueError, 'ALREADY_DROPPED'):
                view.ground.spawn_drops(npc.ref, [(STACK, 10)], owner_uid=1)
            old = npc.ref
            view.entities.remove(npc.uid)
            with self.assertRaisesRegex(ValueError, 'CURRENT_DEAD_NPC'):
                view.ground.spawn_drops(old, [(STACK, 10)], owner_uid=1)
        view.ground.close()
        self.assertEqual(view.ground._spawned, set())
        self.assertEqual(len(view.ground), 0)


if __name__ == '__main__':
    unittest.main()
