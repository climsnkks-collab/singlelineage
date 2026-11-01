"""Committed-bag weight publication checks; no sockets, game or profile IO."""
from types import SimpleNamespace as NS
import unittest

from tools.local_original_session import inventory, world_core_stats as core
from tools.local_original_session.game_data import load_m1
from tools.local_original_session.world_ai_tests import status_fields
from tools.local_original_session.world_core_inventory import INVENTORY_STARTER_FIELDS
from tools.local_original_session.world_status_frames_tests import decode_status
from tools.local_original_session.world_core_kit import _world_consume_kit
from tools.local_original_session.world_extensions import WorldEvents
from tools.local_original_session.world_runtime import WorldRuntime
from tools.local_original_session.world_visibility import WorldView


class WeightProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_committed_bag_cost_capacity_change_and_no_duplicate_publication(self):
        data = load_m1()
        writer = object()
        position = NS(uid=1, name='DevelopmentWeight')
        info = {3: 1, 10: 1, 11: 18, 12: 12, 13: 16, 14: 10, 15: 12, 16: 8}
        current = [None]
        capacity_bonus = [0]

        def bag(count):
            fields = dict(INVENTORY_STARTER_FIELDS)
            fields.update({1: 42, 2: 14, 4: count})
            current[0] = inventory.build_kit_frame([fields])
            owner.inventory_frame = current[0]

        def fold(hook, value, *args, **kwargs):
            return value + capacity_bonus[0] if hook == 'weight_capacity' else value

        queued, announced = [], []
        state = NS(profile=NS(level=1), status_fields=status_fields(200))
        state.status_fields.update({17: 0, 12: 7, 13: 40, 26: 42.5})

        runtime = WorldRuntime()
        world = NS(data=data, combat=NS(pcs={1: state}),
                   runtime=runtime, events=WorldEvents(), closed=False,
                   spawner=NS(tick=lambda now: False), ai=None,
                   _queue=lambda uid, frame: queued.append((uid, frame)),
                   _announce=lambda: announced.append(True))
        runtime.add_tick_hook(lambda now: WorldView.tick(world, now))
        owner = NS(world=world, _world=world,
            realm=NS(store=NS(select=lambda name: (None, info)),
                     service=lambda writer: NS(snapshot=lambda: position)),
            _item_equipment_effect=NS(store=NS(peek=lambda uid: (None, current[0]))),
            _world_progress_for=lambda uid: None, fold_sync_hooks=fold,
            item_policies={}, _world_bound=lambda value: value is writer,
            _inventory_kit_policy=inventory.KIT_POLICY,
            _world_pcs={id(writer): (writer, 1)})
        owner._world_stats_for = lambda *args, **kwargs: core._world_stats_for(owner, *args, **kwargs)
        commits = []

        def replace_kit(uid, before, after):
            self.assertEqual((uid, before), (1, current[0]))
            commits.append((uid, before, after))
            current[0] = after
            return True

        owner.inventory_store = NS(replace_kit=replace_kit)
        core._world_weight_initialize(owner)

        async def publish():
            await runtime.tick_once(1.0)

        bag(300)
        initial, _, _ = owner._world_stats_for(position)
        self.assertGreater(initial.carried_weight, 0)
        self.assertEqual(initial.carried_weight, max(data.items[14].weight * 300 // 1000, 1))
        await publish()
        first_percent = state.status_fields[17]
        self.assertGreater(first_percent, 0)
        self.assertEqual(len(queued), 1)
        # A later request with the same saved bag sends no duplicate status.
        await publish()
        self.assertEqual(len(queued), 1)
        # Real kit-cost producer, including its CAS/frame assignment. No
        # after_request call: world-handled requests bypass that broker hook.
        await runtime.dispatch_now(_world_consume_kit, owner, writer, 42, 100)
        self.assertEqual(len(commits), 1)
        self.assertEqual(state.status_fields[17], first_percent)
        await publish()
        self.assertLess(state.status_fields[17], first_percent)
        # Capacity changes use the same burden; stale gauge240 is never reused.
        capacity_bonus[0] = initial.max_weight
        await publish()
        self.assertLess(state.status_fields[17], first_percent)
        latest = queued[-1][1]
        self.assertEqual(int.from_bytes(latest[2:4], 'little'), 0x4e38)
        values = decode_status(self, latest)
        self.assertEqual(values[17], state.status_fields[17])
        self.assertEqual((values[10], values[11], values[12], values[13]), (200, 200, 7, 40))
        self.assertEqual(values[26], 42.5)
        # Losing the final stack produces zero burden and a final full update.
        bag(0)
        await publish()
        self.assertEqual(state.status_fields[17], 0)
        self.assertGreaterEqual(len(announced), len(queued))
        # The existing world close event releases this tick consumer.
        world.events.emit('close')
        count_before_close = len(queued)
        bag(300)
        await publish()
        self.assertEqual(len(queued), count_before_close)


if __name__ == '__main__':
    unittest.main()
