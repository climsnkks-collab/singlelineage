"""Rental inventory/recovery/lifetime/threshold tests; no clients or ports."""
import asyncio
import json
from pathlib import Path
import tempfile
import textwrap
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tools.local_original_session import inventory, world_feature_town as town, world_inn as inn
from tools.local_original_session.world_handlers import _starter_fields
from tools.local_original_session.world_scheduler import Scheduler


DEFINITION = inn.definitions(Path(__file__).parent / 'data/m2')[70012]


def kit(*items):
    rows = []
    for uid, template, count in items:
        row = _starter_fields()
        row.update({1: uid, 2: template, 4: count})
        rows.append(row)
    return inventory.build_kit_frame(rows)


def rent(frame=None, *, kind='room', wall=100):
    return inn.rent_plan(frame or kit((1, 7, 1000)), DEFINITION, uid=3, kind=kind,
        key_uid=2, prototype=_starter_fields(), placement=(61122, 0, 32596, 32929), wall=wall)


class Transactions:
    def __init__(self, folder, frame):
        self.inventory = self
        self.profile = Path(folder) / 'characters.json'
        self.frame = frame
        self.commits = 0

    def restore(self, uid):
        return self.frame

    def commit_inventory(self, uid, before, after, **kwargs):
        if before != self.frame:
            raise ValueError('CAS_CHANGED')
        self.frame = after
        self.commits += 1
        return True


class RentalTests(unittest.TestCase):
    def test_room_and_hall_use_client_key_name_and_duration(self):
        for kind, template, name in (('room', 10100, DEFINITION.room_name),
                                     ('hall', 10101, DEFINITION.hall_name)):
            after, lease = rent(kind=kind)
            coins, key = inventory.validate_kit_frame(after)
            self.assertEqual(dict(coins.raw_fields)[4], 900)
            self.assertEqual((key.template_bits, dict(key.raw_fields)[18]),
                             (template, name.encode('utf-8')))
            self.assertEqual(lease['expires_at'], 14500)
            self.assertEqual(lease['key_uid'], key.identifier)

    def test_exact_fee_keeps_zero_anchor_and_key(self):
        after, _ = rent(kit((1, 7, 100)))
        self.assertEqual([dict(r.raw_fields)[4] for r in inventory.validate_kit_frame(after)], [0, 1])

    def test_insufficient_fee_does_not_change_inventory(self):
        frame = kit((1, 7, 99))
        with self.assertRaisesRegex(ValueError, 'INN_INSUFFICIENT_ADENA'):
            rent(frame)
        self.assertEqual(dict(inventory.validate_kit_frame(frame)[0].raw_fields)[4], 99)

    def test_timely_return_removes_only_issued_key_and_refunds_once(self):
        after, lease = rent()
        closed, amount = inn.close_plan(after, lease, DEFINITION, refund=True, wall=101)
        self.assertEqual(amount, 10)
        self.assertEqual([(r.identifier, dict(r.raw_fields)[4])
                         for r in inventory.validate_kit_frame(closed)], [(1, 910)])
        with self.assertRaisesRegex(ValueError, 'INN_OWNED_KEY_REQUIRED'):
            inn.close_plan(closed, lease, DEFINITION, refund=True, wall=102)

    def test_expired_return_has_no_refund(self):
        after, lease = rent()
        closed, amount = inn.close_plan(after, lease, DEFINITION, refund=True, wall=lease['expires_at'])
        self.assertEqual(amount, 0)
        self.assertEqual(dict(inventory.validate_kit_frame(closed)[0].raw_fields)[4], 900)

    def test_missing_coin_uses_existing_owner_allocator(self):
        after, lease = rent()
        key = dict(inventory.validate_kit_frame(after)[1].raw_fields)
        frame = inventory.build_kit_frame([key])
        allocate = Mock(return_value=100)
        closed, _ = inn.close_plan(frame, lease, DEFINITION, refund=True, wall=101, allocate_uid=allocate)
        allocate.assert_called_once_with()
        coin, = inventory.validate_kit_frame(closed)
        self.assertEqual((coin.identifier, coin.template_bits, dict(coin.raw_fields)[4]), (100, 7, 10))

    def test_recovery_requires_key_place_and_valid_time(self):
        after, lease = rent()
        position = SimpleNamespace(map_id=0, x=32596, y=32929)
        self.assertTrue(inn.eligible(lease, DEFINITION, after, position, wall=101))
        for frame, place, wall in ((kit((1, 7, 900)), position, 101),
            (after, SimpleNamespace(map_id=4, x=32596, y=32929), 101),
            (after, SimpleNamespace(map_id=0, x=32600, y=32929), 101),
            (after, position, lease['expires_at'])):
            self.assertFalse(inn.eligible(lease, DEFINITION, frame, place, wall=wall))

    def test_all_town_keys_are_client_named(self):
        definitions = {}
        for name in ('m2', 'm4', 'm5'):
            definitions.update(inn.definitions(Path(__file__).parent / 'data' / name))
        self.assertEqual(set(definitions), {70012, 70019, 70070, 70031, 70065, 70084})
        self.assertEqual({d.room_key for d in definitions.values()}, {10100,10104,10106,10108,10110,10114})

    def test_m5_builder_preserves_emitted_rental_policies_and_korean_names(self):
        root = Path(__file__).parent / 'data'
        baseline = json.loads((root / 'm2/town_services.json').read_text(encoding='utf-8'))
        current = json.loads((root / 'm5/town_services.json').read_text(encoding='utf-8'))['inns']
        rows = [dict(l1j_npc_id=r['l1j_npc_id'], l1j_name=r['name'],
                     l1j_npc_ref=r['source_ref'], classification='inn_menu_candidate') for r in current]
        source = (root / 'm5/build_data.py').read_text(encoding='utf-8')
        # Execute the actual isolated builder block without running its unrelated
        # dataset writes, terrain loads or rebuild operations.
        block = '    inn_keys=' + source.split('    inn_keys=', 1)[1].split('    banks=', 1)[0]
        scope = dict(baseline=baseline, rows=rows)
        exec(compile(textwrap.dedent(block), 'm5/build_data.py inn block', 'exec'), scope)
        self.assertEqual({r['l1j_npc_id']: r['rental_policy'] for r in scope['inns']},
                         {r['l1j_npc_id']: r['rental_policy'] for r in current})
        for row in scope['inns']:
            self.assertNotIn('?', row['rental_policy']['room_name'])


class StoreTests(unittest.TestCase):
    def test_commit_reopen_and_return_persist_canonical_inventory(self):
        before = kit((1, 7, 1000))
        after, lease = rent(before)
        with tempfile.TemporaryDirectory() as directory:
            tx = Transactions(directory, before)
            store = inn.InnStore(tx)
            store.commit(3, before, after, lease)
            reopened = inn.InnStore(tx)
            self.assertEqual(reopened.rows[3], lease)
            self.assertEqual(tx.commits, 1)
            final, _ = inn.close_plan(after, lease, DEFINITION, refund=True, wall=101)
            reopened.commit(3, after, final, None)
            self.assertEqual(inn.InnStore(tx).rows, {})
            self.assertFalse(store.intent.exists())

    def test_crash_after_inventory_before_metadata_finishes_without_recharge(self):
        before = kit((1, 7, 1000))
        after, lease = rent(before)
        with tempfile.TemporaryDirectory() as directory:
            tx = Transactions(directory, before)
            store = inn.InnStore(tx)
            write = store._write
            def interrupted(path, value):
                if path == store.path:
                    raise OSError('metadata write interrupted')
                return write(path, value)
            with patch.object(store, '_write', interrupted):
                with self.assertRaisesRegex(OSError, 'metadata write interrupted'):
                    store.commit(3, before, after, lease)
            self.assertEqual(tx.frame, after)
            self.assertTrue(store.intent.exists())
            with self.assertRaisesRegex(ValueError, 'INN_RECOVERY_REQUIRED'):
                store.commit(3, after, after, lease)
            recovered = inn.InnStore(tx)
            self.assertEqual(recovered.rows[3], lease)
            self.assertEqual(tx.commits, 1)
            self.assertFalse(recovered.intent.exists())

    def test_crash_before_inventory_recovers_original_expiry_and_single_debit(self):
        before = kit((1, 7, 1000))
        after, lease = rent(before)
        with tempfile.TemporaryDirectory() as directory:
            tx = Transactions(directory, before)
            store = inn.InnStore(tx)
            with patch.object(tx, 'commit_inventory', side_effect=OSError('CAS interrupted')):
                # Store captured the original bound method; inject the failing owner callback.
                store.replace_kit = tx.commit_inventory
                with self.assertRaisesRegex(OSError, 'CAS interrupted'):
                    store.commit(3, before, after, lease)
            self.assertEqual(tx.frame, before)
            recovered = inn.InnStore(tx)
            self.assertEqual(tx.frame, after)
            self.assertEqual(recovered.rows[3]['expires_at'], 14500)
            self.assertEqual(tx.commits, 1)

    def test_conflicting_inventory_is_preserved(self):
        before = kit((1, 7, 1000))
        after, lease = rent(before)
        with tempfile.TemporaryDirectory() as directory:
            tx = Transactions(directory, before)
            store = inn.InnStore(tx)
            store.replace_kit = Mock(side_effect=OSError('stop'))
            with self.assertRaises(OSError):
                store.commit(3, before, after, lease)
            tx.frame = kit((1, 7, 999))
            with self.assertRaisesRegex(ValueError, 'INN_INVENTORY_CONFLICT'):
                inn.InnStore(tx)
            self.assertTrue(store.intent.exists())
            self.assertEqual(dict(inventory.validate_kit_frame(tx.frame)[0].raw_fields)[4], 999)


class RegenTests(unittest.TestCase):
    def fixture(self):
        from tools.local_original_session.world_combat import PcState
        frame, lease = rent()
        state = PcState(SimpleNamespace(level=1), {12: 1, 13: 200}, 1, 200,
                        regen_state=4, hp_points=6, mp_points=6)
        policy = SimpleNamespace(hp_threshold=lambda level: 10, mp_threshold=10)
        combat = SimpleNamespace(pcs={3: state}, regen=policy)
        entity = SimpleNamespace(map_id=0, x=32596, y=32929)
        ctx = SimpleNamespace(world=SimpleNamespace(combat=combat, entities={3:entity}),
            inventory_frame=frame, _world_inn_store=SimpleNamespace(rows={3:lease}),
            _world_inn_definitions={70012:DEFINITION})
        def base(uid):
            hp_due = state.hp_points + state.regen_state >= 10
            mp_due = state.mp_points + state.regen_state >= 10
            state.hp_points = 0 if hp_due else state.hp_points + state.regen_state
            state.mp_points = 0 if mp_due else state.mp_points + state.regen_state
            if hp_due: state.hp += 2
            if mp_due: state.status_fields[12] += 1
            return b'base'
        return ctx, state, entity, inn.regen_wrapper(ctx)(base)

    def test_bonus_only_on_natural_resource_threshold(self):
        ctx, state, entity, tick = self.fixture()
        with patch('tools.local_original_session.world_inn.time.time', return_value=101), \
             patch('tools.local_original_session.world_combat.status_frame', return_value=b'new'):
            self.assertEqual(tick(3), b'new')
            self.assertEqual((state.hp, state.mp), (8, 5))
            state.hp_points, state.mp_points = 0, 0
            self.assertEqual(tick(3), b'base')
            self.assertEqual((state.hp, state.mp), (8, 5))

    def test_no_bonus_for_expiry_missing_key_far_away_or_dead(self):
        for condition in ('expiry', 'key', 'range', 'dead'):
            ctx, state, entity, tick = self.fixture()
            wall = 14500 if condition == 'expiry' else 101
            if condition == 'key': ctx.inventory_frame = kit((1,7,900))
            if condition == 'range': entity.x += 4
            if condition == 'dead': state.dead = True
            with patch('tools.local_original_session.world_inn.time.time', return_value=wall):
                self.assertEqual(tick(3), b'base')
                self.assertEqual((state.hp,state.mp), (3,2))


class LifetimeTests(unittest.TestCase):
    def fixture(self, directory):
        before = kit((1,7,1000))
        after, lease = rent(before)
        tx = Transactions(directory, before)
        store = inn.InnStore(tx)
        store.commit(3,before,after,lease)
        scheduler = Scheduler(clock=lambda: 10)
        queue = Mock()
        ctx = SimpleNamespace(_world_inn_store=store, _world_inn_definitions={70012:DEFINITION},
            inventory_frame=after, _world_inn_timers={}, _world_bound=lambda writer:True,
            world=SimpleNamespace(runtime=SimpleNamespace(scheduler=scheduler,clock=lambda:10), _queue=queue))
        ctx._world_inn_expire = MethodType(town._world_inn_expire, ctx)
        ctx._world_inn_schedule = MethodType(town._world_inn_schedule, ctx)
        return ctx, scheduler, queue

    def test_online_timer_expires_key_and_releases_rental(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx,scheduler,queue = self.fixture(directory)
            with patch('tools.local_original_session.world_inn.time.time', return_value=14499):
                ctx._world_inn_schedule(object(),3)
            with patch('tools.local_original_session.world_inn.time.time', return_value=14500):
                scheduler.run_due(11)
            self.assertEqual(ctx._world_inn_store.rows,{})
            self.assertEqual(ctx._world_inn_timers,{})
            self.assertEqual([r.template_bits for r in inventory.validate_kit_frame(ctx.inventory_frame)],[7])
            queue.assert_called_once()

    def test_disconnect_cancels_timer_and_reentry_expires_offline_key(self):
        with tempfile.TemporaryDirectory() as directory:
            ctx,scheduler,queue = self.fixture(directory)
            writer=object()
            with patch('tools.local_original_session.world_inn.time.time', return_value=14499):
                ctx._world_inn_schedule(writer,3)
            town._world_inn_before_leave(ctx,writer,3)
            self.assertEqual(len(scheduler),0)
            self.assertIn(3,ctx._world_inn_store.rows)
            async def dispatch(fn,*args): return fn(*args)
            ctx.world.runtime.dispatch_now=dispatch
            ctx.realm=SimpleNamespace(service=lambda writer:SimpleNamespace(snapshot=lambda:SimpleNamespace(uid=3)))
            ctx._world_send=AsyncMock()
            with patch('tools.local_original_session.world_inn.time.time', return_value=14501):
                asyncio.run(town._world_inn_after_enter(ctx,writer,{},True,object()))
            self.assertEqual(ctx._world_inn_store.rows,{})
            ctx._world_send.assert_awaited_once()
            self.assertEqual(len(scheduler),0)


if __name__ == '__main__':
    unittest.main()
