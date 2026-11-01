"""Pure ground-item rules; no game, server, sockets, packets or durable writes."""
from collections import Counter
from dataclasses import replace
import random
import unittest

from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_entities import EntityRef, EntityRegistry, Kind, UidAllocator
from tools.local_original_session.world_ground_items import GroundItems, MAX_COUNT
from tools.local_original_session.world_combat import PcProfile, PcState
from tools.local_original_session.world_reward import KillReward, RewardPcState, on_kill
from tools.local_original_session.world_scheduler import Scheduler

DATA = load_m1()
STACK = next(item.template_id for item in DATA.items.values() if item.stackable)
SINGLE = next(item.template_id for item in DATA.items.values() if not item.stackable)


class GroundItemsTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.entities = EntityRegistry()
        self.scheduler = Scheduler(clock=lambda: self.now, is_current=self.entities.is_current)
        self.pc = self.entities.add(Kind.PC, 0, 100, 100, uid=1)
        self.other = self.entities.add(Kind.PC, 0, 100, 100, uid=2)
        self.npc = self.entities.add(Kind.NPC, 0, 100, 100, template_id=next(iter(DATA.monsters)))
        self.old_npc_ref = self.npc.ref
        self.entities.kill(self.npc.uid)
        self.ground = GroundItems(self.entities, self.scheduler, DATA, passable=lambda *_: True)

    def spawn(self, drops=None, **kwargs):
        return self.ground.spawn_drops(self.npc.ref, [(STACK, 10)] if drops is None else drops,
                                       owner_uid=self.pc.uid, **kwargs)

    def state(self):
        return (tuple((e.uid, e.generation, e.alive, e.map_id, e.x, e.y) for e in self.entities),
                dict(self.ground._items), dict(self.ground._expiry), len(self.scheduler))

    def test_dead_generation_placement_once_and_grade(self):
        with self.assertRaisesRegex(ValueError, 'CURRENT_DEAD_NPC'):
            self.ground.spawn_drops(self.old_npc_ref, [(STACK, 10)], owner_uid=1)
        row = next(row for rows in DATA.drops.values() for row in rows)
        row = replace(row, item_id=STACK, grade=2)
        reward = KillReward(0, 0, 1, 1, 0, 20, 10, [(STACK, 10)], (row,))
        items = self.ground.spawn_reward(self.npc.ref, reward, owner_uid=1)
        item = items[0]
        self.assertEqual((item.map_id, item.x, item.y, item.grade), (0, 100, 99, 2))
        self.assertEqual(self.entities.resolve(item.ref).kind, Kind.ITEM)
        self.assertEqual((item.owner_until, item.expires_at), (110.0, 700.0))
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'ALREADY_DROPPED'):
            self.spawn()
        self.assertEqual(self.state(), before)

    def test_only_true_cells_used_unknown_and_blocked_retry(self):
        for verdict in (False, None, 1):
            self.ground.passable = lambda *_, result=verdict: result
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'NO_PASSABLE_TILE'):
                self.spawn()
            self.assertEqual(self.state(), before)
        self.ground.passable = lambda m, x, y: (x, y) == (101, 101)
        items = self.spawn([(STACK, 1), (SINGLE, 2)])
        self.assertEqual(len(items), 3)
        self.assertEqual({(i.x, i.y) for i in items}, {(101, 101)})
        self.assertEqual([i.count for i in items], [1, 1, 1])
        self.assertEqual(len({i.ref.uid for i in items}), 3)

    def test_partial_and_final_pickup_keep_then_cancel_timer(self):
        item, = self.spawn()
        timer = self.ground._expiry[item.ref.uid]
        self.assertEqual(self.ground.pickup(self.pc.ref, item.ref, 3), (STACK, 3))
        remaining = self.ground.get(item.ref)
        self.assertEqual(remaining.count, 7)
        self.assertEqual((remaining.owner_until, remaining.expires_at), (110, 700))
        self.assertIs(self.ground._expiry[item.ref.uid], timer)
        self.assertEqual(self.ground.pickup(self.pc.ref, item.ref, 7), (STACK, 7))
        self.assertTrue(timer.cancelled)
        self.assertIsNone(self.entities.resolve(item.ref))
        self.assertIsNone(self.ground.get(item.ref))
        with self.assertRaisesRegex(ValueError, 'ITEM_NOT_FOUND'):
            self.ground.pickup(self.pc.ref, item.ref, 1)
        self.now = 700
        self.assertEqual(self.scheduler.run_due(), 0)

    def test_owner_priority_exact_boundary(self):
        item, = self.spawn()
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'OWNER_PRIORITY'):
            self.ground.pickup(self.other.ref, item.ref, 1, now=109.999)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.ground.pickup(self.other.ref, item.ref, 1, now=110), (STACK, 1))

    def test_expiry_boundary_without_tick_and_scheduled_cleanup(self):
        item, = self.spawn()
        self.assertEqual(self.ground.pickup(self.pc.ref, item.ref, 1, now=699.999), (STACK, 1))
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'ITEM_EXPIRED'):
            self.ground.pickup(self.pc.ref, item.ref, 1, now=700)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.scheduler.run_due(699.999), 0)
        self.assertEqual(self.scheduler.run_due(700), 1)
        self.assertEqual(len(self.ground), 0)
        self.assertIsNone(self.entities.get(item.ref.uid))
        self.assertEqual(self.scheduler.run_due(701), 0)

    def test_distance_map_and_stale_dead_pc_rejections(self):
        item, = self.spawn()
        self.entities.move(self.pc.uid, 0, item.x + 3, item.y + 3)
        self.assertEqual(self.ground.pickup(self.pc.ref, item.ref, 1), (STACK, 1))
        for map_id, x, y in ((0, item.x + 4, item.y), (1, item.x, item.y)):
            self.entities.move(self.pc.uid, map_id, x, y)
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'TOO_FAR'):
                self.ground.pickup(self.pc.ref, item.ref, 1)
            self.assertEqual(self.state(), before)
        old_pc_ref = self.pc.ref
        self.entities.kill(self.pc.uid)
        for ref in (old_pc_ref, self.pc.ref, self.npc.ref):
            with self.assertRaisesRegex(ValueError, 'CURRENT_ALIVE_PC'):
                self.ground.pickup(ref, item.ref, 1)

    def test_bad_pickup_counts_and_refs_preserve_state(self):
        item, = self.spawn()
        for count in (0, -1, True, 1.0, '1', 11, MAX_COUNT + 1):
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'COUNT_INVALID'):
                self.ground.pickup(self.pc.ref, item.ref, count)
            self.assertEqual(self.state(), before)
        for ref in (None, EntityRef(item.ref.uid, item.ref.generation + 1), self.npc.ref):
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'ITEM_NOT_FOUND'):
                self.ground.pickup(self.pc.ref, ref, 1)
            self.assertEqual(self.state(), before)

    def test_nonstackable_count_one_only(self):
        first, second = self.spawn([(SINGLE, 2)])
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'COUNT_INVALID'):
            self.ground.pickup(self.pc.ref, first.ref, 2)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.ground.pickup(self.pc.ref, first.ref, 1), (SINGLE, 1))
        self.assertIsNotNone(self.ground.get(second.ref))

    def test_invalid_drop_batch_is_atomic(self):
        bad_rows = [(STACK, 0), (STACK, True), (STACK, MAX_COUNT + 1), (99999999, 1), (STACK,)]
        for row in bad_rows:
            before = self.state()
            with self.assertRaises(ValueError):
                self.spawn([(STACK, 1), row])
            self.assertEqual(self.state(), before)
        definition = next(row for rows in DATA.drops.values() for row in rows)
        for rolled in ([], [replace(definition, item_id=99999999)],
                       [replace(definition, item_id=STACK, grade=3)]):
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'ROLLED_ROWS_MISMATCH'):
                self.spawn(rolled_rows=rolled)
            self.assertEqual(self.state(), before)
        for now in (-1, float('nan'), float('inf'), True):
            with self.assertRaisesRegex(ValueError, 'TIME_INVALID'):
                self.spawn(now=now)

    def test_all_current_resolved_drop_rows_place_and_keep_grade(self):
        for rows in DATA.drops.values():
            npc = self.entities.add(Kind.NPC, 0, 100, 100)
            self.entities.kill(npc.uid)
            drops = [(row.item_id, max(1, row.min_count)) for row in rows]
            items = self.ground.spawn_drops(npc.ref, drops, rolled_rows=rows, owner_uid=1)
            for row, (_, count) in zip(rows, drops):
                matching = [i for i in items if i.item_id == row.item_id and i.grade == row.grade]
                self.assertGreaterEqual(sum(i.count for i in matching), count)
        self.ground.close()
        self.assertEqual((len(self.ground), len(self.scheduler)), (0, 0))

    def test_actual_kill_reward_to_ground_and_pickup(self):
        profile = PcProfile(DATA.level_for_exp(0), 0, 0, 13, 10, con=10, wis=10)
        state = PcState(profile, {1: 65537, 2: profile.level, 10: 8, 11: 20,
                                  12: 3, 13: 10}, 8, 20)
        reward = on_kill(RewardPcState.from_combat(state, exp=0),
                         DATA.monsters[self.npc.template_id], random.Random(7), data=DATA)
        self.assertTrue(reward.drops)
        expected = Counter()
        for (item_id, count), row in zip(reward.drops, reward.rolled_rows):
            expected[item_id, row.grade] += count
        items = self.ground.spawn_reward(self.npc.ref, reward, owner_uid=self.pc.uid)
        picked = Counter()
        for item in items:
            snapshot = self.ground.get(item.ref)
            item_id, count = self.ground.pickup(self.pc.ref, item.ref, item.count)
            picked[item_id, snapshot.grade] += count
        self.assertEqual(picked, expected)
        self.assertEqual((len(self.ground), len(self.scheduler)), (0, 0))

    def test_separate_owner_grade_and_close_preserves_other_entities(self):
        row = next(row for rows in DATA.drops.values() for row in rows)
        self.ground.passable = lambda m, x, y: (x, y) == (100, 99)
        first, = self.spawn([(STACK, 3)], rolled_rows=[replace(row, item_id=STACK, grade=0)])
        npc = self.entities.add(Kind.NPC, 0, 100, 100)
        self.entities.kill(npc.uid)
        second, = self.ground.spawn_drops(npc.ref, [(STACK, 4)], owner_uid=2,
                                          rolled_rows=[replace(row, item_id=STACK, grade=2)])
        self.assertNotEqual(first.ref, second.ref)
        self.assertEqual((first.owner_uid, first.grade, second.owner_uid, second.grade), (1, 0, 2, 2))
        self.ground.close()
        self.ground.close()
        self.assertIsNotNone(self.entities.get(self.pc.uid))
        self.assertIsNotNone(self.entities.get(self.npc.uid))
        self.assertEqual((len(self.ground), len(self.scheduler)), (0, 0))

    def test_allocation_failure_releases_partial_creation(self):
        registry = EntityRegistry(allocate_uid=UidAllocator(start=10, stop=12))
        pc = registry.add(Kind.PC, 0, 100, 100, uid=1)
        npc = registry.add(Kind.NPC, 0, 100, 100, uid=2)
        registry.kill(npc.uid)
        scheduler = Scheduler(clock=lambda: self.now, is_current=registry.is_current)
        ground = GroundItems(registry, scheduler, DATA, passable=lambda *_: True)
        with self.assertRaisesRegex(ValueError, 'UID_EXHAUSTED'):
            ground.spawn_drops(npc.ref, [(SINGLE, 3)], owner_uid=pc.uid)
        self.assertEqual((len(registry), len(ground), len(scheduler)), (2, 0, 0))
        self.assertNotIn(npc.ref, ground._spawned)
        # Already allocated UIDs stay burned, never reused by retry.
        with self.assertRaisesRegex(ValueError, 'UID_EXHAUSTED'):
            registry.add(Kind.ITEM, 0, 100, 100)


if __name__ == '__main__':
    unittest.main()
