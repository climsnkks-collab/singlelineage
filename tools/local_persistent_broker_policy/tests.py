"""Synthetic metadata only: no sockets, native runtime imports or game runs."""
import unittest
from policy import PersistentPolicy, Peer, OwnerSample, Refused, GAME_S2C, MAX_COUNTER


class Fixture:
    def __init__(self):
        self.owner, self.handle, self.job = object(), object(), object()
        self.sockets = {12000: object(), 14030: object()}
        self.p = PersistentPolicy(self.owner, self.handle, self.job, self.sockets)
        self.now = 0

    def sample(self, accepted_peer, **changes):
        data = dict(owner=self.owner, handle=self.handle, job=self.job, peer=accepted_peer,
                    observed_ns=self.now, exact_identity_and_tuple=True, alive=True)
        data.update(changes)
        return OwnerSample(**data)

    def connection(self, port=14030, client_port=45000, adopted=False):
        writer = object(); peer = Peer(port, client_port, self.now)
        row = self.p.admit(writer, peer, self.sample(peer), self.now, key_already_drained=adopted)
        return row

    def write(self, row, op, size=12):
        sample = self.sample(row.peer)
        self.p.begin_write(row.writer, sample, op, size, 0, self.now)
        self.p.drained(row.writer, sample, 0, self.now)

    def bootstrap(self, row):
        if row.tx_boot == 0:
            self.write(row, 0x4e20)
        for rx, tx in ((0x4e34, 0x4e35), (0x4f3d, 0x4f3e)):
            self.p.received_frame(row.writer, self.sample(row.peer), rx, 10, self.now)
            self.write(row, tx)

    def close(self, row):
        self.p.eof(row.writer, self.sample(row.peer), True, self.now)
        self.p.closed(row.writer, positive_close=True, registry_removed=True,
                      decoder_empty=True, task_joined=True)

    def game(self):
        first = self.connection(); self.bootstrap(first); self.close(first)
        second = self.connection(client_port=45001); self.bootstrap(second)
        return second


class PolicyTests(unittest.TestCase):
    def rejected(self, code, callback):
        with self.assertRaises(Refused) as raised:
            callback()
        self.assertEqual(str(raised.exception), code)

    def test_exact_literal_owner_handle_job_and_tuple(self):
        for change in ({'owner': object()}, {'handle': object()}, {'job': object()}):
            f = Fixture(); peer = Peer(14030, 45000, 0)
            self.rejected('EXACT_RETAINED_OWNER_REQUIRED', lambda: f.p.admit(object(), peer, f.sample(peer, **change), 0))
        for change in ({'alive': False}, {'exact_identity_and_tuple': False},
                       {'observed_ns': 1}, {'peer': Peer(14030, 45001, 0)}):
            f = Fixture(); peer = Peer(14030, 45000, 0)
            self.rejected('CURRENT_OWNER_REQUIRED', lambda: f.p.admit(object(), peer, f.sample(peer, **change), 0))

    def test_idle_hours_with_fresh_owner_and_no_total_quota(self):
        f = Fixture(); row = f.game()
        for second in (16, 121, 301, 3600, 43200):
            f.now = second * 1_000_000_000
            f.p.checkpoint(row.writer, f.sample(row.peer), f.now)
        self.assertEqual(f.p.state, 'OPEN')

    def test_many_events_fixed_log_and_saturating_counters(self):
        f = Fixture(); row = f.game()
        # Route recognition / accounting fixture, not valid repeated READ_NEWS.
        # Exact live dispatcher still enforces each route's schema/order/replay.
        for _ in range(8000):
            f.now += 1_000_000_000
            f.p.received_chunk(row.writer, f.sample(row.peer), 4096, 0, f.now)
            f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 10, f.now)
        self.assertEqual(len(f.p.log), 256)
        self.assertGreater(f.p.dropped, 7700)
        self.assertEqual(row.received, 8002)
        self.assertFalse(any(item is f.owner for record in f.p.log for item in record))
        f.p.events = f.p.dropped = row.received = MAX_COUNTER
        f.now += 1_000_000_000
        f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 10, f.now)
        self.assertEqual((f.p.events, f.p.dropped, row.received), (MAX_COUNTER,) * 3)

    def test_current_owner_freshness_not_old_exit_receipt(self):
        f = Fixture(); row = f.game(); old = f.sample(row.peer)
        f.now = f.p.FRESH_NS + 1
        self.rejected('CURRENT_OWNER_REQUIRED', lambda: f.p.checkpoint(row.writer, old, f.now))
        f.p.stop('owner_unknown')
        self.assertEqual(f.p.state, 'CLOSING')
        self.rejected('SESSION_STOPPED', lambda: f.p.checkpoint(row.writer, f.sample(row.peer), f.now))

    def test_key_adoption_preserves_fast_first_write_order(self):
        f = Fixture(); row = f.connection(adopted=True); f.bootstrap(row)
        self.assertEqual((row.rx_boot, row.tx_boot, row.sent), (2, 3, 3))

    def test_bootstrap_reply_order_and_predecessor(self):
        f = Fixture(); row = f.connection()
        self.rejected('BOOTSTRAP_REPLY_NOT_DRAINED', lambda: f.p.received_frame(row.writer, f.sample(row.peer), 0x4e34, 10, 0))
        self.rejected('BOOTSTRAP_REPLY_SEQUENCE', lambda: f.p.begin_write(row.writer, f.sample(row.peer), 0x4f3e, 6, 0, 0))
        self.rejected('BOOTSTRAP_PREDECESSOR_NOT_COMPLETE_CLOSED', lambda: f.connection(client_port=45001))

    def test_only_complete_eof_positive_close_promotes_no_queue(self):
        f = Fixture(); row = f.connection(); f.bootstrap(row)
        f.p.eof(row.writer, f.sample(row.peer), True, 0)
        self.rejected('BOOTSTRAP_PREDECESSOR_NOT_COMPLETE_CLOSED', lambda: f.connection(client_port=45001))
        f.p.closed(row.writer, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        self.rejected('ACCEPTED_TUPLE_REUSED', lambda: f.connection())
        f.connection(client_port=45001)

    def test_application_reconnect_unbound_even_after_positive_close(self):
        f = Fixture(); row = f.game(); f.close(row)
        self.rejected('APPLICATION_RECONNECT_UNBOUND', lambda: f.connection(client_port=45002))

    def test_unknown_opcode_no_guessed_ping_or_movement_reply(self):
        f = Fixture(); row = f.game()
        for opcode in (0, 0xffff, 0x4e23, 0x4e2b):
            self.rejected('GAME_OPCODE_UNBOUND', lambda: f.p.received_frame(row.writer, f.sample(row.peer), opcode, 10, f.now))
            self.rejected('SERVER_OPCODE_UNBOUND', lambda: f.p.begin_write(row.writer, f.sample(row.peer), opcode, 6, 0, f.now))
        self.assertIn(0x4e22, GAME_S2C)
        self.assertNotIn(0x4e23, GAME_S2C)

    def test_decoder_and_frame_sizes(self):
        for size in (0, 4097, True):
            f = Fixture(); row = f.game()
            self.rejected('READ_CHUNK_BOUND', lambda: f.p.received_chunk(row.writer, f.sample(row.peer), size, 0, 0))
        f = Fixture(); row = f.game()
        self.rejected('DECODER_BUFFER_BOUND', lambda: f.p.received_chunk(row.writer, f.sample(row.peer), 1, f.p.MAX_BUFFER + 1, 0))
        self.rejected('CLIENT_FRAME_BOUND', lambda: f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 65536, 0))
        self.rejected('SERVER_FRAME_BOUND', lambda: f.p.begin_write(row.writer, f.sample(row.peer), 0x264, 65536, 0, 0))

    def test_partial_timeout_absolute_no_byte_trickle_extension(self):
        f = Fixture(); row = f.game()
        f.p.received_chunk(row.writer, f.sample(row.peer), 1, 1, 0)
        f.now = 9_000_000_000
        f.p.received_chunk(row.writer, f.sample(row.peer), 1, 2, f.now)
        f.now = 10_000_000_000
        self.rejected('PARTIAL_FRAME_TIMEOUT', lambda: f.p.checkpoint(row.writer, f.sample(row.peer), f.now))

    def test_complete_frame_clears_partial_timer(self):
        f = Fixture(); row = f.game()
        f.p.received_chunk(row.writer, f.sample(row.peer), 1, 1, 0)
        f.now = 1_000_000_000
        f.p.received_chunk(row.writer, f.sample(row.peer), 9, 0, f.now)
        f.now = 100_000_000_000
        f.p.checkpoint(row.writer, f.sample(row.peer), f.now)
        self.assertIsNone(row.partial_started_ns)

    def test_new_partial_after_completed_frame_gets_own_deadline(self):
        f = Fixture(); row = f.game()
        f.p.received_chunk(row.writer, f.sample(row.peer), 1, 1, 0)
        f.now = 9_000_000_000
        f.p.received_chunk(row.writer, f.sample(row.peer), 10, 1, f.now, decoded_frames=1)
        f.now = 10_000_000_000
        f.p.checkpoint(row.writer, f.sample(row.peer), f.now)
        self.assertEqual(row.partial_started_ns, 9_000_000_000)

    def test_rate_bound_and_refill(self):
        f = Fixture(); row = f.game()
        # bootstrap consumed2; max burst128 allows126 more metadata frames.
        for _ in range(126):
            f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 10, 0)
        self.rejected('RATE_BOUND', lambda: f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 10, 0))
        f.now = 1_000_000_000
        f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 10, f.now)

    def test_byte_rate_bound_without_total_byte_quota(self):
        f = Fixture(); row = f.game()
        for _ in range(31):
            f.p.received_chunk(row.writer, f.sample(row.peer), 4096, 0, 0)
        self.rejected('RATE_BOUND', lambda: f.p.received_chunk(row.writer, f.sample(row.peer), 4096, 0, 0))
        f.now = 1_000_000_000
        f.p.received_chunk(row.writer, f.sample(row.peer), 4096, 0, f.now)

    def test_backpressure_blocks_reads_and_new_dispatch_until_drain(self):
        f = Fixture(); row = f.game()
        self.rejected('TRANSPORT_BACKPRESSURE_BOUND', lambda: f.p.begin_write(row.writer, f.sample(row.peer), 0x264, 8, f.p.WRITE_HIGH, 0))
        f.p.begin_write(row.writer, f.sample(row.peer), 0x264, 8, 0, 0)
        self.rejected('READ_PAUSED_UNTIL_DRAIN', lambda: f.p.received_chunk(row.writer, f.sample(row.peer), 1, 0, 0))
        self.rejected('DISPATCH_PAUSED_UNTIL_DRAIN', lambda: f.p.received_frame(row.writer, f.sample(row.peer), 0x267, 10, 0))
        self.rejected('ONE_WRITE_DRAIN_REQUIRED', lambda: f.p.begin_write(row.writer, f.sample(row.peer), 0x264, 8, 0, 0))
        self.rejected('POSITIVE_DRAIN_REQUIRED', lambda: f.p.drained(row.writer, f.sample(row.peer), f.p.WRITE_LOW + 1, 0))
        f.p.drained(row.writer, f.sample(row.peer), 0, 0)
        f.p.received_chunk(row.writer, f.sample(row.peer), 1, 0, 0)

    def test_drain_timeout_and_changed_owner_after_write(self):
        f = Fixture(); row = f.game()
        f.p.begin_write(row.writer, f.sample(row.peer), 0x264, 8, 0, 0)
        self.rejected('CURRENT_OWNER_REQUIRED', lambda: f.p.drained(row.writer, f.sample(row.peer, alive=False), 0, 0))
        f.now = f.p.DRAIN_NS
        self.rejected('DRAIN_TIMEOUT', lambda: f.p.checkpoint(row.writer, f.sample(row.peer), f.now))
        f.p.fail(row.writer)
        self.assertEqual(f.p.state, 'CLOSING')

    def test_partial_eof_refused(self):
        f = Fixture(); row = f.game()
        f.p.received_chunk(row.writer, f.sample(row.peer), 1, 1, 0)
        self.rejected('COMPLETE_EOF_REQUIRED', lambda: f.p.eof(row.writer, f.sample(row.peer), False, 0))

    def test_clock_regression_and_boot_timeout(self):
        f = Fixture(); row = f.connection()
        f.now = f.p.BOOT_NS
        self.rejected('BOOTSTRAP_TIMEOUT', lambda: f.p.checkpoint(row.writer, f.sample(row.peer), f.now))
        self.rejected('CLOCK_REGRESSION', lambda: f.p.checkpoint(row.writer, f.sample(row.peer), 0))

    def test_positive_exit_exact_handle_required_and_cleanup(self):
        f = Fixture(); row = f.game()
        self.rejected('POSITIVE_EXACT_OWNER_EXIT_REQUIRED', lambda: f.p.stop('positive_owner_exit', owner=f.owner, handle=object(), positive_exit=True))
        plan = f.p.stop('positive_owner_exit', owner=f.owner, handle=f.handle, positive_exit=True)
        self.assertEqual(plan[0], 'stop_accepts')
        self.rejected('POSITIVE_CONNECTION_CLEANUP_REQUIRED', lambda: f.p.closed(row.writer, positive_close=False, registry_removed=True, decoder_empty=True, task_joined=True))
        self.rejected('POSITIVE_BROKER_CLEANUP_REQUIRED', lambda: f.p.release(f.sockets, listeners_closed=True, tasks_joined=True))
        f.p.closed(row.writer, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        wrong = dict(f.sockets); wrong[12000] = object()
        self.rejected('SAME_RESERVATIONS_REQUIRED', lambda: f.p.release(wrong, listeners_closed=True, tasks_joined=True))
        f.p.release(f.sockets, listeners_closed=True, tasks_joined=True)
        self.assertEqual(f.p.state, 'CLOSED')
        self.assertEqual(f.p.reservations, {})
        self.assertIsNone(f.p.handle)

    def test_cancel_idempotent_stop_and_no_new_admission(self):
        f = Fixture()
        self.assertEqual(f.p.stop('cancelled'), f.p.stop('cancelled'))
        self.rejected('SESSION_STOPPED', lambda: f.connection())
        f.p.release(f.sockets, listeners_closed=True, tasks_joined=True)

    def test_endpoint_and_socket_identity_rejection(self):
        f = Fixture(); peer = Peer(14000, 45000, 0)
        self.rejected('ENDPOINT_REQUIRED', lambda: f.p.admit(object(), peer, f.sample(peer), 0))
        self.rejected('BOTH_RESERVATIONS_REQUIRED', lambda: PersistentPolicy(f.owner, f.handle, f.job, {12000: object()}))
        sock = object()
        self.rejected('DISTINCT_RESERVED_SOCKETS_REQUIRED', lambda: PersistentPolicy(f.owner, f.handle, f.job, {12000: sock, 14030: sock}))

    def test_two_ports_bounded_and_foreign_writer_rejected(self):
        f = Fixture(); a = f.connection(port=12000); b = f.connection()
        f.bootstrap(a); f.bootstrap(b)
        self.rejected('LITERAL_WRITER_REQUIRED', lambda: f.p.checkpoint(object(), f.sample(a.peer), 0))
        self.rejected('BOOTSTRAP_PREDECESSOR_NOT_COMPLETE_CLOSED', lambda: f.connection(port=12000, client_port=45001))
        self.assertEqual(sum(len(rows) for rows in f.p.rows.values()), 2)

    def test_failed_connection_cleanup_keeps_failure_and_prevents_promotion(self):
        f = Fixture(); row = f.connection(); f.bootstrap(row)
        f.p.fail(row.writer)
        f.p.closed(row.writer, positive_close=True, registry_removed=True, decoder_empty=True, task_joined=True)
        self.assertTrue(row.failed)
        self.rejected('SESSION_STOPPED', lambda: f.connection(client_port=45001))
        f.p.release(f.sockets, listeners_closed=True, tasks_joined=True)


if __name__ == '__main__':
    unittest.main(verbosity=1)
