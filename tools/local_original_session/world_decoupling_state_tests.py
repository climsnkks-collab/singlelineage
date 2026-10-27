"""Executable contracts for decoupled state owners (no client/source fixtures)."""
from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from tools.local_original_session.world_extensions import RuntimeExtensions, WorldEvents
from tools.local_original_session.world_progress import Progress, ProgressOwner, ProgressStore
from tools.local_original_session.world_state_services import InventoryTransactions


class ExtensionContracts(unittest.TestCase):
    def test_empty_registration_keeps_defaults(self):
        events = WorldEvents()
        self.assertIsNone(events.emit('tick', 10))
        self.assertEqual(events.collect('visible_entities', 1, 0, 2, 3, ()), ())
        self.assertFalse(events.chain('can_be_attacked', 7))
        self.assertEqual(events.first('spawn_frame', object(), default=b'base'), b'base')
        self.assertEqual(events.fold('stats', 8, 1), 8)

    def test_optional_observer_failure_does_not_skip_other_owners(self):
        events, reached = WorldEvents(), []
        def fail(_):
            raise RuntimeError('observer')
        events.add('broken', 'report', fail, isolate=True)
        events.add('healthy', 'report', reached.append)
        with self.assertLogs('tools.local_original_session.world_extensions', level='ERROR'):
            events.emit('report', 42)
        self.assertEqual(reached, [42])
        self.assertEqual(events.errors, [('broken', 'report', 'RuntimeError')])

    def test_critical_transaction_failure_stays_fatal(self):
        events, reached = WorldEvents(), []
        def fail(_):
            raise OSError('durable write')
        events.add('store', 'commit', fail)
        events.add('publish', 'commit', reached.append)
        with self.assertRaises(OSError):
            events.emit('commit', 42)
        self.assertEqual(reached, [])

    def test_reducers_preserve_each_contribution(self):
        events = WorldEvents()
        events.add('one', 'stats', lambda value, amount: value + amount)
        events.add('two', 'stats', lambda value, amount: value * 2)
        self.assertEqual(events.fold('stats', 3, 4), 14)
        events.add('skip', 'item', lambda _: False)
        events.add('consume', 'item', lambda _: True)
        events.add('unreachable', 'item', lambda _: self.fail('already consumed'))
        self.assertTrue(events.chain('item', 1))

    def test_duplicate_callback_registration_is_explicit_error(self):
        events = WorldEvents()
        callback = lambda: None
        events.add('feature', 'tick', callback)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_WORLD_EVENT'):
            events.add('feature', 'tick', callback)

    def test_lifecycle_priority_preserves_order_independent_of_install_order(self):
        events, reached = WorldEvents(), []
        events.add('town', 'close', lambda: reached.append('town'))
        events.add('followers', 'close', lambda: reached.append('followers'), priority=10)
        tail = events.add('later', 'close', lambda: reached.append('later'))
        events.emit('close')
        self.assertEqual(reached, ['followers', 'town', 'later'])
        events.remove('close', tail)
        reached.clear()
        events.emit('close')
        self.assertEqual(reached, ['followers', 'town'])

    def test_wrappers_compose_and_remove_out_of_order(self):
        class Target:
            def value(self, x):
                return x + 1
        target, extensions = Target(), RuntimeExtensions()
        first = extensions.wrap('first', target, 'value',
            lambda base: lambda x: base(x) * 2)
        second = extensions.wrap('second', target, 'value',
            lambda base: lambda x: base(x) + 3)
        self.assertEqual(target.value(5), 15)
        first.close()
        self.assertEqual(target.value(5), 9)
        second.close()
        self.assertEqual(target.value(5), 6)
        self.assertNotIn('value', vars(target))
        first.close()  # One feature's cleanup is idempotent.

    def test_optional_provider_slot_restores_absence(self):
        target, extensions = SimpleNamespace(), RuntimeExtensions()
        handle = extensions.wrap('provider', target, 'query', lambda base: lambda: 7)
        self.assertEqual(target.query(), 7)
        handle.close()
        self.assertFalse(hasattr(target, 'query'))

    def test_duplicate_wrapper_does_not_replace_existing_owner(self):
        target, extensions = SimpleNamespace(value=lambda: 3), RuntimeExtensions()
        extensions.wrap('owner', target, 'value', lambda base: lambda: base() + 1)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_WORLD_WRAPPER'):
            extensions.wrap('owner', target, 'value', lambda base: lambda: 99)
        self.assertEqual(target.value(), 4)

    def test_reserved_wrapper_validates_early_and_captures_base_at_activation(self):
        target, extensions = SimpleNamespace(value=None), RuntimeExtensions()
        prepared = extensions.reserve('pet', target, 'value')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_WORLD_WRAPPER'):
            extensions.reserve('pet', target, 'value')
        self.assertIsNone(target.value)
        supplied_later = lambda x: x + 7
        target.value = supplied_later
        handle = prepared.install(lambda base: lambda x: base(x) * 2)
        self.assertEqual(target.value(3), 20)
        handle.close()
        self.assertIs(target.value, supplied_later)


@dataclass(frozen=True)
class Profile:
    level: int


class ProgressContracts(unittest.TestCase):
    def setUp(self):
        state = SimpleNamespace(profile=Profile(2), max_hp=30, max_mp=12, hp=7, mp=4,
                                status_fields={2: 2, 10: 7, 11: 30, 12: 4, 13: 12, 18: -70})
        self.world = SimpleNamespace(combat=SimpleNamespace(pcs={1: state}), exp={1: 120})
        self.owner = ProgressOwner(self.world)

    def test_lawful_has_one_live_authority_and_survives_pending_snapshot(self):
        self.owner.set_lawful(1, -13)
        pending = self.owner.mark(1)
        self.assertEqual(pending.lawful, -13)
        self.world.combat.pcs.clear()
        self.assertEqual(self.owner.lawful_of(1), -13)
        self.assertEqual(self.owner.snapshot(1), pending)

    def test_acknowledging_older_snapshot_preserves_newer_one(self):
        old = self.owner.mark(1)
        self.world.exp[1] = 150
        current = self.owner.mark(1)
        self.owner.ack(1, old)
        self.assertIs(self.owner.pending(1), current)
        with self.assertRaises(TypeError):
            self.owner.pending_view[1] = old
        self.owner.ack(1, current)
        self.assertEqual(self.owner.pending_items(), ())

    def test_adopt_does_not_refill_vitals_or_add_percent_field(self):
        state = self.world.combat.pcs[1]
        self.owner.adopt(1, Progress(500, 3, 42, 18, 123))
        self.assertEqual((state.hp, state.mp, state.status_fields[10], state.status_fields[12]),
                         (7, 4, 7, 4))
        self.assertEqual((state.profile.level, state.max_hp, state.status_fields[13],
                          state.status_fields[18]), (3, 42, 18, 123))
        self.assertNotIn(26, state.status_fields)

    def test_unbound_lawful_does_not_reopen_an_unreadable_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / 'characters.json'
            (profile.parent / 'progression.json').write_text('invalid')
            self.owner.attach_store(ProgressStore(profile))
            self.world.combat.pcs.clear()
            self.assertEqual(self.owner.lawful_of(1, 123), 123)

    def test_reward_can_preserve_pre_projection_maxima(self):
        pending = self.owner.mark(1, max_hp=28, max_mp=10)
        self.assertEqual((pending.max_hp, pending.max_mp, pending.lawful), (28, 10, -70))
        self.assertEqual(self.world.combat.pcs[1].max_hp, 30)

    def test_progression_json_old_lawful_and_fresh_defaults_stay_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / 'characters.json'
            (profile.parent / 'progression.json').write_text(json.dumps({
                'version': 1, 'rows': [dict(uid=1, exp=10, level=1, max_hp=30, max_mp=8)]}))
            store = ProgressStore(profile)
            self.assertEqual(store.get(1).lawful, 0)
            self.assertEqual(store.get(2).lawful, 500)
            value = Progress(100, 2, 36, 11, -33)
            store.commit(1, value)
            self.assertEqual(ProgressStore(profile).get(1), value)
            body = json.loads(store.path.read_text())
            self.assertEqual(body, {'version': 1, 'rows': [
                dict(uid=1, exp=100, level=2, max_hp=36, max_mp=11, lawful=-33)]})


class InventoryTransactionContracts(unittest.TestCase):
    def test_plain_cas_does_not_add_warehouse_work(self):
        calls = []
        service = InventoryTransactions.__new__(InventoryTransactions)
        service.inventory = SimpleNamespace(replace_kit=lambda *a, **k: calls.append((a, k)) or True)
        service._warehouse = SimpleNamespace(restore=lambda uid: self.fail('plain CAS opens warehouse'))
        self.assertTrue(service.commit_inventory(5, b'before', b'after', append=True))
        self.assertEqual(calls, [((5, b'before', b'after'), {'append': True})])

    def test_joint_inventory_uses_unchanged_warehouse_snapshot(self):
        calls, warehouse = [], b'warehouse'
        service = InventoryTransactions.__new__(InventoryTransactions)
        service.inventory = SimpleNamespace(replace_kit=lambda *a, **k: self.fail('joint CAS not atomic'))
        service._warehouse = SimpleNamespace(restore=lambda uid: warehouse,
            commit=lambda *a, **k: calls.append((a, k)) or True)
        self.assertTrue(service.commit_inventory(5, b'before', b'after', joint=True))
        self.assertEqual(calls, [((5, b'before', b'after', warehouse, warehouse), {})])


class JointProjectionContracts(unittest.TestCase):
    def test_reward_scope_restores_roster_order_and_actor_after_failure(self):
        from tools.local_original_session.world_companion import CompanionRecord, WorldCompanions
        from tools.local_original_session.world_entities import EntityRegistry, Kind
        from tools.local_original_session.world_scheduler import Scheduler
        entities = EntityRegistry()
        scheduler = Scheduler(clock=lambda: 0, is_current=entities.is_current)
        manager = WorldCompanions(entities, scheduler)
        owner = entities.add(Kind.PC, 0, 10, 10)
        roster = {1: {'account_id': 'fixture', 'class_id': 0},
                  2: {'account_id': 'fixture', 'class_id': 3},
                  3: {'account_id': 'fixture', 'class_id': 3}}
        for uid in (2, 3):
            manager.register(CompanionRecord(uid, 1, 'fixture'), roster=roster)
            manager.summon(uid, owner.uid, 0, 10 + uid, 10)
        actor = manager.active[2]
        with self.assertRaisesRegex(RuntimeError, 'reward failed'):
            with manager.without_reward_member(2):
                self.assertEqual(tuple(manager.active), (3,))
                self.assertIs(manager.get_actor(actor.ref.uid), actor)
                self.assertTrue(manager.can_be_attacked(actor.ref.uid))
                raise RuntimeError('reward failed')
        self.assertEqual(tuple(manager.active), (3, 2))
        self.assertIs(manager.active[2], actor)
        with self.assertRaises(TypeError):
            manager.active[2] = actor

    def test_feature_save_does_not_swap_or_mark_another_owners_projection(self):
        from tools.local_original_session.world_companion import CompanionRecord, CompanionStore
        one = CompanionRecord(2, 1, 'fixture', hp=12, max_hp=12, mp=8, max_mp=8)
        two = CompanionRecord(3, 1, 'fixture', hp=14, max_hp=14, mp=9, max_mp=9)
        records = {2: one, 3: two}
        first = dict(kill_id='first', member_character_id=2, durable=False)
        second = dict(kill_id='second', member_character_id=3, durable=False)
        receipts = [first, second]
        state = SimpleNamespace(profile=Profile(2), max_hp=30, max_mp=12, status_fields={18: -70})
        world = SimpleNamespace(companions=SimpleNamespace(records=records),
            combat=SimpleNamespace(pcs={1: state}), exp={1: 120},
            companion_owner_half={1: 1}, companion_reward_receipts=receipts)
        with tempfile.TemporaryDirectory() as directory:
            store = CompanionStore(Path(directory) / 'characters.json')
            store.commit(world, 1, records=(one,), reward_receipts=(first,))
            self.assertIs(world.companions.records, records)
            self.assertIs(world.companion_reward_receipts, receipts)
            self.assertEqual(set(records), {2, 3})
            self.assertEqual([row['character_id'] for row in store.payload['records']], [2])
            self.assertEqual([row['kill_id'] for row in store.payload['rewards']], ['first'])
            self.assertTrue(first['durable'])
            self.assertFalse(second['durable'])
            self.assertEqual(store.payload['owners']['1']['lawful'], -70)


if __name__ == '__main__':
    unittest.main()
