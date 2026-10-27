"""Short fake-clock checks for world entities, scheduler and runtime."""
import asyncio
import unittest

from tools.local_original_session import world_entities as we, world_runtime as wr, world_scheduler as ws


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


class EntityTests(unittest.TestCase):
    def test_uid_generation_and_near(self):
        reg = we.EntityRegistry(allocate_uid=we.UidAllocator(start=1000))
        pc = reg.add(we.Kind.PC, 0, 50, 50, uid=1)
        npc = reg.add(we.Kind.NPC, 0, 53, 48, template_id=45)
        far = reg.add(we.Kind.NPC, 0, 90, 50, template_id=45)
        other_map = reg.add(we.Kind.ITEM, 4, 50, 50)
        self.assertEqual((npc.uid, far.uid, other_map.uid), (1000, 1001, 1002))
        self.assertEqual([e.uid for e in reg.near(0, 50, 50, 5)], [1, 1000])
        self.assertEqual([e.uid for e in reg.near(0, 50, 50, 5, kind=we.Kind.NPC)], [1000])
        reg.move(far.uid, 0, 47, 49, heading=3)
        self.assertEqual([e.uid for e in reg.near(0, 50, 50, 5)], [1, 1000, 1001])
        old = npc.ref
        reg.kill(npc.uid)
        self.assertFalse(reg.is_current(old))
        self.assertEqual([e.uid for e in reg.near(0, 50, 50, 5)], [1, 1001])
        reg.remove(npc.uid)
        self.assertIsNone(reg.get(npc.uid))
        with self.assertRaises(ValueError):
            reg.add(we.Kind.NPC, 0, 1, 1, uid=npc.uid)
        self.assertEqual(reg.add(we.Kind.NPC, 0, 1, 1).uid, 1003)
        self.assertTrue(reg.is_current(pc.ref))


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.reg = we.EntityRegistry()
        self.sched = ws.Scheduler(clock=self.clock, is_current=self.reg.is_current)
        self.log = []

    def note(self, label):
        return lambda now: self.log.append((label, now))

    def test_order_cancel_and_due_only(self):
        self.sched.schedule(103, None, 'c', self.note('c'))
        self.sched.schedule(101, None, 'a', self.note('a'))
        self.sched.schedule(101, None, 'b', self.note('b'))
        dropped = self.sched.schedule(102, None, 'x', self.note('x'))
        self.sched.schedule(200, None, 'later', self.note('later'))
        self.sched.cancel(dropped)
        self.assertEqual(self.sched.run_due(103), 3)
        self.assertEqual([label for label, _ in self.log], ['a', 'b', 'c'])
        self.assertEqual(self.sched.next_deadline(), 200)

    def test_generation_and_cancel_owner(self):
        mob = self.reg.add(we.Kind.NPC, 0, 1, 1, template_id=1)
        other = self.reg.add(we.Kind.NPC, 0, 2, 2, template_id=1)
        self.sched.schedule(101, mob.ref, 'ai', self.note('stale'))
        self.sched.schedule(101, other.ref, 'ai', self.note('dormant'))
        self.sched.schedule(102, other.ref, 'regen', self.note('dormant2'))
        self.reg.kill(mob.uid)
        self.assertEqual(self.sched.cancel_owner(other.ref), 2)
        self.assertEqual(self.sched.run_due(110), 0)
        self.assertEqual(self.log, [])

    def test_late_tick_does_not_replay_repeats(self):
        def attack(now):
            self.log.append(now)
            self.sched.schedule(now + 1.0, None, 'attack', attack)
        self.sched.schedule(101, None, 'attack', attack)
        self.sched.run_due(150)
        self.assertEqual(self.log, [150])
        self.sched.run_due(150.5)
        self.assertEqual(self.log, [150])
        self.sched.run_due(151)
        self.assertEqual(self.log, [150, 151])

    def test_callback_error_is_logged_and_others_run(self):
        def boom(now):
            raise RuntimeError('boom')
        self.sched.schedule(101, None, 'boom', boom)
        self.sched.schedule(101, None, 'ok', self.note('ok'))
        with self.assertLogs(ws.LOG, 'ERROR'):
            self.sched.run_due(101)
        self.assertEqual(self.log, [('ok', 101)])


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_stop_hooks_and_dispatch(self):
        clock = FakeClock()
        runtime = wr.WorldRuntime(clock=clock, tick_interval=0.1)
        ticked = asyncio.Event()
        seen = []
        calls = 0

        def hook(now):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('first tick fails')
            ticked.set()

        runtime.add_tick_hook(hook)
        runtime.scheduler.schedule(100, None, 'due', seen.append)
        with self.assertLogs(wr.LOG, 'ERROR'):
            runtime.start(asyncio.get_running_loop())
            await asyncio.wait_for(ticked.wait(), 2)
        self.assertTrue(runtime.running)
        self.assertEqual(seen, [100.0])

        async def request(value):
            self.assertTrue(runtime.lock.locked())
            return value * 2
        self.assertEqual(await runtime.dispatch_now(request, 21), 42)
        self.assertEqual(await runtime.dispatch_now(lambda: 'sync'), 'sync')
        await runtime.stop()
        self.assertFalse(runtime.running)
        self.assertFalse(runtime.lock.locked())
        with self.assertRaises(ValueError):
            wr.WorldRuntime(tick_interval=0.25)


if __name__ == '__main__':
    unittest.main()
