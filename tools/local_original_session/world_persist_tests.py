"""Pure write-behind tests; no broker, game, server, ports or filesystem writes."""
from copy import deepcopy
import logging
import unittest

from tools.local_original_session.world_persist import WorldPersist
from tools.local_original_session.world_scheduler import Scheduler


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class WorldPersistTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.scheduler = Scheduler(clock=self.clock)
        self.calls = []
        self.store = {}
        self.writer = self.save
        self.log = logging.getLogger(__name__ + '.quiet')
        self.old_disabled = self.log.disabled
        self.log.disabled = True
        self.addCleanup(setattr, self.log, 'disabled', self.old_disabled)
        self.persist = WorldPersist(self.scheduler, self.write, logger=self.log)

    def save(self, key, snapshot):
        self.store[key] = deepcopy(snapshot)

    def write(self, key, snapshot):
        self.calls.append((key, deepcopy(snapshot)))
        return self.writer(key, snapshot)

    def tick(self, now):
        self.clock.now = now
        return self.scheduler.run_due()

    def test_coalesce_per_key_without_io_or_postponing_deadline(self):
        self.persist.enqueue('one', {'q': 1})
        self.persist.enqueue('two', {'q': 8})
        for now in range(1, 300):
            self.clock.now = now
            self.persist.enqueue('one', {'q': now})
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.scheduler), 2)
        self.assertEqual(self.tick(299), 0)
        self.assertEqual(self.tick(300), 2)
        self.assertEqual(self.store, {'one': {'q': 299}, 'two': {'q': 8}})
        self.assertEqual(self.persist.pending_keys, ())
        self.assertEqual(len(self.scheduler), 0)

    def test_inventory_and_character_intervals_and_clean_requeue(self):
        self.persist.enqueue(('inv', 1), [1])
        self.persist.enqueue(('char', 1), {'hp': 10}, kind='character')
        self.tick(300)
        self.assertEqual(self.calls, [(('inv', 1), [1])])
        self.tick(1199)
        self.assertEqual(len(self.calls), 1)
        self.tick(1200)
        self.assertEqual(self.store[('char', 1)], {'hp': 10})
        self.persist.enqueue(('inv', 1), [2])
        self.assertEqual(self.scheduler.next_deadline(), 1500)
        self.tick(1500)
        self.assertEqual(self.store[('inv', 1)], [2])

    def test_immediate_flush_only_selected_key_and_cancels_old_timer(self):
        self.persist.enqueue('logout', {'hp': 1}, kind='character')
        self.persist.enqueue('other', [2])
        result = self.persist.flush('logout')
        self.assertTrue(result.ok)
        self.assertEqual(result.saved, ('logout',))
        self.assertEqual(self.persist.pending_keys, ('other',))
        self.tick(1200)
        self.assertEqual([key for key, _ in self.calls], ['logout', 'other'])
        self.assertTrue(self.persist.flush('absent').ok)

    def test_failure_auto_retry_keeps_latest_and_error_until_saved(self):
        error = OSError('disk full')

        def fail(key, snapshot):
            raise error

        self.writer = fail
        self.persist.enqueue('one', {'q': 1})
        self.tick(300)
        self.assertIs(self.persist.last_failures[0].error, error)
        self.assertEqual(self.persist.snapshot('one'), {'q': 1})
        self.assertEqual(self.scheduler.next_deadline(), 305)
        self.clock.now = 301
        self.persist.enqueue('one', {'q': 2})
        self.assertEqual(self.scheduler.next_deadline(), 305)
        self.tick(304)
        self.assertEqual(len(self.calls), 1)
        self.writer = self.save
        self.tick(305)
        self.assertEqual(self.store['one'], {'q': 2})
        self.assertEqual(self.persist.last_failures, ())
        self.assertEqual(self.persist.pending_keys, ())

    def test_caller_and_inspection_mutation_are_isolated(self):
        payload = {'items': [{'q': 1}]}
        self.persist.enqueue('one', payload)
        payload['items'][0]['q'] = 99
        self.persist.snapshot('one')['items'].clear()
        self.persist.flush('one')
        self.assertEqual(self.store['one'], {'items': [{'q': 1}]})

    def test_writer_mutation_then_failure_does_not_corrupt_retry(self):
        def fail(key, snapshot):
            snapshot['items'].clear()
            raise OSError('before replace')

        self.writer = fail
        self.persist.enqueue('one', {'items': [1, 2]})
        result = self.persist.flush('one')
        self.assertFalse(result.ok)
        self.assertEqual(result.failures[0].key, 'one')
        self.assertEqual(self.persist.snapshot('one'), {'items': [1, 2]})
        self.writer = self.save
        self.tick(5)
        self.assertEqual(self.store['one'], {'items': [1, 2]})

    def test_reentrant_latest_request_cannot_be_overwritten_by_nested_flush(self):
        nested = []

        def reenter(key, snapshot):
            self.persist.enqueue(key, {'q': 2})
            nested.append(self.persist.flush(key))
            self.save(key, snapshot)  # The old writer completes LAST.

        self.writer = reenter
        self.persist.enqueue('one', {'q': 1})
        result = self.persist.flush('one')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(nested[0].pending, ('one',))
        self.assertFalse(result.ok)
        self.assertEqual(self.persist.snapshot('one'), {'q': 2})
        self.assertEqual(self.store['one'], {'q': 1})
        self.writer = self.save
        self.tick(300)
        self.assertEqual(self.store['one'], {'q': 2})
        self.assertEqual(self.persist.pending_keys, ())

    def test_reentrant_update_survives_mutating_failed_writer(self):
        def reenter(key, snapshot):
            self.persist.enqueue(key, {'q': 2})
            snapshot['q'] = 99
            raise OSError('replace failed')

        self.writer = reenter
        self.persist.enqueue('one', {'q': 1})
        self.tick(300)
        self.assertEqual(self.persist.snapshot('one'), {'q': 2})
        self.writer = self.save
        self.tick(305)
        self.assertEqual(self.store['one'], {'q': 2})

    def test_replace_then_raise_retries_absolute_snapshot_idempotently(self):
        def ambiguous(key, snapshot):
            self.save(key, snapshot)
            raise OSError('error after replace')

        self.writer = ambiguous
        self.persist.enqueue('one', {'q': 4})
        self.assertFalse(self.persist.flush('one').ok)
        self.assertEqual(self.store['one'], {'q': 4})
        self.writer = self.save
        self.tick(5)
        self.assertEqual(self.store['one'], {'q': 4})
        self.assertEqual(len(self.calls), 2)

    def test_flush_all_continues_after_failure_and_reports_pending(self):
        def partial(key, snapshot):
            if key == 'bad':
                raise OSError('locked')
            self.save(key, snapshot)

        self.writer = partial
        self.persist.enqueue('bad', [1])
        self.persist.enqueue('good', [2])
        result = self.persist.flush_all()
        self.assertEqual(result.saved, ('good',))
        self.assertEqual(result.pending, ('bad',))
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(self.store, {'good': [2]})

    def test_shutdown_saves_all_keys_and_prevents_future_requests(self):
        self.persist.enqueue('inv', [1])
        self.persist.enqueue('char', {'hp': 5}, kind='character')
        result = self.persist.shutdown()
        self.assertTrue(result.ok)
        self.assertEqual(result.saved, ('inv', 'char'))
        self.assertTrue(self.persist.closed)
        self.assertEqual(len(self.scheduler), 0)
        self.tick(1200)
        self.assertEqual(len(self.calls), 2)
        with self.assertRaisesRegex(RuntimeError, 'PERSIST_CLOSED'):
            self.persist.enqueue('new', [])

    def test_shutdown_failure_is_bounded_preserved_and_manually_retryable(self):
        def fail(key, snapshot):
            raise OSError('unavailable')

        self.writer = fail
        self.persist.enqueue('one', [1])
        self.persist.enqueue('two', [2])
        result = self.persist.shutdown()
        self.assertFalse(result.ok)
        self.assertEqual(result.pending, ('one', 'two'))
        self.assertEqual(len(result.failures), 2)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.scheduler), 0)
        self.tick(10000)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.persist.snapshot('two'), [2])
        self.writer = self.save
        self.assertTrue(self.persist.flush_all().ok)

    def test_false_ack_and_async_writer_are_failures_not_success(self):
        self.writer = lambda key, snapshot: False
        self.persist.enqueue('one', [1])
        self.assertFalse(self.persist.flush('one').ok)

        async def async_writer(key, snapshot):
            self.fail('must never execute')

        self.writer = async_writer
        result = self.persist.flush('one')
        self.assertIsInstance(result.failures[0].error, TypeError)
        self.assertEqual(result.pending, ('one',))


if __name__ == '__main__':
    unittest.main()
