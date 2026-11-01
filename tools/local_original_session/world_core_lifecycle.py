"""Quit/EOF and restart lifetimes on the broker's retained connection.

No alternate reader or socket owner: terminal requests, cleanup and original
close deadlines keep using the broker row and the selected generation.
"""
from __future__ import annotations
import asyncio
import inspect
import time
from tools.local_entry_server.codecs import ClientPlaintextDecoder, Frame
from tools.local_original_session import movement, settings
from tools.local_persistent_broker_policy.policy import OwnerSample, MAX_COUNTER

QUIT_REQUEST = 0x4e3c
QUIT_SUCCESS_FRAME = b'\x08\0\xef\x4e\x08\x2d\0\0'


def need(value, code):
    if not value:
        raise ValueError(code)

class _ClosingQuitOwnerGuard:
    """The real accepted game row's no-effect duplicate Quit capability only."""
    __slots__ = ('broker', 'row', 'writer')

    def __init__(self, broker, row, writer):
        self.broker, self.row, self.writer = broker, row, writer

    async def __call__(self, writer, position):
        return await self.broker._quit_duplicate_owner(writer, self.row, position)


class _TerminalQuitReceipt:
    """One decoded empty Quit on the same retained read, never an OwnerSample."""
    __slots__ = ('broker', 'writer', 'row', 'peer', 'peer_values', 'policy_row',
                 'operation_lock', 'transport', 'read_task', 'decoder', 'frame')

    def __init__(self, broker, writer, row, read_task, decoder, frame):
        self.broker, self.writer, self.row = broker, writer, row
        self.peer, self.peer_values = row['peer'], tuple(sorted(row['peer'].items()))
        self.policy_row, self.operation_lock = row['policy_row'], row['operation_lock']
        self.transport, self.read_task = writer.transport, read_task
        self.decoder, self.frame = decoder, frame



class BrokerLifecycle:
    """Terminal/restart operations on the broker and its retained read task."""
    def bind_source_quit_closing(self, source_quit):
        """Bind the existing SourceQuit object before the primary is resumed.

        This is an owner receipt for one later no-effect duplicate Quit, never
        an owner sample for an ordinary frame or a transport policy change.
        """
        from tools.local_original_session.manual_source_quit import SourceQuitRequests
        need(type(source_quit) is SourceQuitRequests and source_quit.broker is self
             and source_quit.owner is self.policy.owner
             and source_quit.requests.consumer is source_quit.consumer
             and source_quit.consumer.reader.owner is self.policy.owner
             and source_quit._started is False and source_quit._closed is False
             and self._source_quit_closing is None and not self._closing
             and not self.failure.is_set(), 'QUIT_CLOSING_SOURCE_BINDING_REQUIRED')
        self._source_quit_closing = source_quit


    async def _quit_exit(self, writer, row):
        state = self.realm.quit_state(writer)
        need(row['writer'] is writer and row['policy_row'] is not None
             and row['policy_row'].writer is writer and not row['failed'] and not row['joined']
             and not self._closing and not self.failure.is_set()
             and state['response_drain_returned'] is True and state['response_queue_empty'] is True
             and not self.realm._settings_failed and callable(self.owner_exit_proof),
             'VERIFIED_QUIT_DRAIN_EXIT_REQUIRED')
        game = self.realm.registry.resolve(writer)
        self.realm.bound_account(writer, game)
        service = self.realm.service(writer)
        position, selected = service.snapshot(), game.selection
        need(selected is not None and not service.fatal and position.uid == state['uid']
             and selected.reference == position.name
             and self.realm.registry.selected.get(position.name) is selected,
             'QUIT_SAME_SELECTED_AUTHORITY_REQUIRED')
        proof = self.owner_exit_proof()
        if inspect.isawaitable(proof):
            proof = await asyncio.wait_for(proof, 1.5)
        self.source_guard()
        # Do not serialize this dict: owner/handle/Job bindings are private.
        self.policy._verified_exit(proof, time.monotonic_ns())
        return proof


    async def _complete_eof(self, writer, row, *, decoder_empty, _binding_check=None):
        alive = self.owner_liveness_guard()
        if inspect.isawaitable(alive):
            alive = await asyncio.wait_for(alive, 1.5)
        self.source_guard()
        if _binding_check is not None:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
        if alive is True or id(writer) not in self.realm._quit:
            # Ordinary EOF keeps the prior live-owner contract unchanged.
            self.policy.eof_retained(writer, retained_alive=alive, decoder_empty=decoder_empty,
                                     now=time.monotonic_ns())
        else:
            need(alive is False, 'CURRENT_RETAINED_OWNER_UNKNOWN')
            proof = await self._quit_exit(writer, row)
            need(self.realm.quit_state(writer)['response_drained'] is True,
                 'EXACT_DRAINED_QUIT_EOF_REQUIRED')
            self.policy.eof_after_quit_exit(writer, proof=proof, decoder_empty=decoder_empty,
                                           now=time.monotonic_ns())
            row['quit_terminal_exit'] = True
        row['eof'] = True
        row['boot_complete'] = row['policy_row'].rx_boot == 2 and row['policy_row'].tx_boot == 3


    async def _drained_quit_read_eof(self, writer, row, read_task, *, decoder,
                                     decoder_empty, quit_binding, binding_check, original_error):
        """Same retained read: actual EOF or one parsed no-effect duplicate Quit."""
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        try:
            raw = await asyncio.wait_for(asyncio.shield(read_task), self.policy.CLOSE_NS / 1e9)
        except asyncio.TimeoutError:
            raise original_error  # Same strict owner failure; no inferred EOF.
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        if raw:
            need(len(raw) == 10 and type(decoder) is ClientPlaintextDecoder
                 and decoder.cipher_pointer == 'present_disabled'
                 and decoder_empty is True and decoder.buffered_bytes == 0,
                 'QUIT_TERMINAL_EXACT_FRAME_REQUIRED')
            frames = decoder.feed(raw)  # The same original C2S parser, no invented frame.
            need(len(frames) == 1 and type(frames[0]) is Frame
                 and frames[0].opcode == QUIT_REQUEST and frames[0].wire_length == 10
                 and frames[0].payload == b'' and decoder.buffered_bytes == 0,
                 'QUIT_TERMINAL_EXACT_FRAME_REQUIRED')
            frame = frames[0]
            receipt = _TerminalQuitReceipt(self, writer, row, read_task, decoder, frame)
            row['_quit_frame_owner'] = receipt
            row['await_phase'] = 'TERMINAL_QUIT_DISPATCH'
            try:
                need(self._quit_closing_witness(writer, row, quit_binding[4]),
                     'QUIT_TERMINAL_SOURCE_WRITER_REQUIRED')
                from tools.local_original_session.launcher import NativeOwner
                owner = self.policy.owner
                callback = getattr(owner, 'quit_terminal_retained_sync', None)
                target = getattr(NativeOwner, 'quit_terminal_retained_sync', None)
                need(type(owner) is NativeOwner
                     and target is not None
                     and getattr(callback, '__self__', None) is owner
                     and getattr(callback, '__func__', None) is target
                     and callback(row['peer']) is True,
                     'QUIT_TERMINAL_RETAINED_PRIMARY_REQUIRED')
                self.source_guard()
                self.policy.received_drained_quit_terminal(writer, receipt,
                    raw_size=len(raw), now=time.monotonic_ns())
                replies = await quit_binding[2].received(frame)
                need(type(replies) is tuple and replies == (),
                     'QUIT_TERMINAL_NOEFFECT_REPLY_REQUIRED')
                current = binding_check()
                need(current is not None and len(current) == len(quit_binding)
                     and all(a is b for a, b in zip(quit_binding, current))
                     and self.realm.quit_state(writer)['duplicate_requests'] == 1,
                     'QUIT_TERMINAL_NOEFFECT_CHANGED')
            finally:
                row['_quit_frame_owner'] = None
                row['await_phase'] = 'READ_POLL_CHECKPOINT'
            return 'QUIT_DUPLICATE_CONTINUE'  # Continue ordinary read; EOF is still unproved.
        await self._complete_eof(writer, row, decoder_empty=decoder_empty)
        return True


    async def _poll_checkpoint(self, writer, row, read_task, *, decoder,
                               decoder_empty, operation_lock=None):
        from tools.local_original_session.broker import LocalRealm
        policy, policy_row = self.policy, row['policy_row']
        pending_bootstrap = (not read_task.done() and policy_row.stage == 0
                             and operation_lock is not None)
        peer, peer_values = row['peer'], tuple(sorted(row['peer'].items()))

        def first_bootstrap_eof():
            # Only an actual read that completed while the poll awaited its
            # owner can take the already-existing terminal EOF path.
            if (not pending_bootstrap or not read_task.done() or read_task.cancelled()
                    or read_task.exception() is not None):
                return False
            raw = read_task.result()
            claims = self._claims.get(peer.get('endpoint_port'), ())
            return (type(raw) is bytes and raw == b'' and decoder_empty is True
                    and len(claims) == 1 and claims[0] is row and row['writer'] is writer
                    and row['_read_task'] is read_task and row['policy_row'] is policy_row
                    and row['operation_lock'] is operation_lock and operation_lock.locked()
                    and row['peer'] is peer and tuple(sorted(peer.items())) == peer_values
                    and self.policy is policy and policy._connection(writer) is policy_row
                    and policy_row.stage == 0 and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
                    and policy_row.buffered == 0 and policy_row.drain_started_ns is None
                    and not row['failed'] and not row['joined'] and not self._closing
                    and not self.failure.is_set())

        bootstrap_peer, bootstrap_claims = policy_row.peer, self._claims.get(14030)
        bootstrap_refs = (policy.owner, policy.handle, policy.job, self.realm, self.failure,
                          self.source_guard, self.owner_liveness_guard, self.owner_guard)
        bootstrap_phase = row.get('await_phase')

        def late_bootstrap_binding(*, eof=False):
            claims = self._claims.get(14030)
            return (pending_bootstrap and claims is bootstrap_claims
                    and claims is not None and len(claims) == 1 and claims[0] is row
                    and row['writer'] is writer and row.get('_read_task') is read_task
                    and row['policy_row'] is policy_row and row['operation_lock'] is operation_lock
                    and operation_lock.locked() and row['peer'] is peer
                    and tuple(sorted(peer.items())) == peer_values and peer.get('endpoint_port') == 14030
                    and row.get('await_phase') == bootstrap_phase
                    and self.policy is policy and policy._connection(writer) is policy_row
                    and policy_row.writer is writer and policy_row.peer is bootstrap_peer
                    and (bootstrap_peer.port, bootstrap_peer.client_port, bootstrap_peer.accepted_ns)
                        == (peer.get('server_port'), peer.get('client_port'), peer.get('accepted_monotonic_ns'))
                    and all(a is b for a, b in zip(bootstrap_refs,
                        (policy.owner, policy.handle, policy.job, self.realm, self.failure,
                         self.source_guard, self.owner_liveness_guard, self.owner_guard)))
                    and policy.state == 'OPEN' and policy_row.stage == 0
                    and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
                    and decoder_empty is True and policy_row.buffered == 0
                    and policy_row.partial_started_ns is None and policy_row.drain_started_ns is None
                    and policy_row.pending_opcode is None and policy_row.pending_size == 0
                    and policy_row.eof is eof and row['eof'] is eof
                    and not any((policy_row.failed, policy_row.positive_close,
                                 row['failed'], row['joined'], self._closing, self.failure.is_set()))
                    and id(writer) not in self.realm.registry._sessions
                    and id(writer) not in self.realm._movement and id(writer) not in self.realm._quit
                    and row.get('_restart') is None)

        late_bootstrap_initial = late_bootstrap_binding()

        def late_bootstrap_eof():
            return (late_bootstrap_initial and late_bootstrap_binding()
                    and read_task.done() and not read_task.cancelled()
                    and read_task.exception() is None and type(read_task.result()) is bytes
                    and read_task.result() == b'')

        pending_quit = (not read_task.done() and policy_row.stage == 1
                        and operation_lock is not None)
        quit_policy_peer = policy_row.peer

        def drained_quit_binding(*, eof=False):
            if not pending_quit:
                return None
            try:
                claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
                realm = self.realm
                state = realm._quit.get(id(writer))
                if (len(claims) != 1 or claims[0] is not row or row['writer'] is not writer
                        or row['_read_task'] is not read_task or row['policy_row'] is not policy_row
                        or row['operation_lock'] is not operation_lock or not operation_lock.locked()
                        or row['peer'] is not peer or tuple(sorted(peer.items())) != peer_values
                        or self.policy is not policy or policy._connection(writer) is not policy_row
                        or policy_row.writer is not writer or policy_row.stage != 1
                        or policy_row.peer is not quit_policy_peer
                        or (quit_policy_peer.port, quit_policy_peer.client_port, quit_policy_peer.accepted_ns)
                           != (peer.get('server_port'), peer.get('client_port'), peer.get('accepted_monotonic_ns'))
                        or policy_row.rx_boot != 2 or policy_row.tx_boot != 3
                        or decoder_empty is not True or policy_row.buffered != 0
                        or policy_row.drain_started_ns is not None or policy_row.pending_size != 0
                        or policy_row.pending_opcode is not None or policy_row.eof is not eof
                        or row['eof'] is not eof or row['failed'] or row['joined']
                        or policy_row.task_joined or policy_row.registry_removed
                        or self._closing or self.failure.is_set() or policy.state != 'OPEN'
                        or type(realm) is not LocalRealm or realm._settings_failed
                        or state is None or state['writer'] is not writer
                        or not all(state[key] is True for key in ('request_verified',
                            'response_drain_returned', 'response_queue_empty', 'response_drained'))
                        or policy._quit_drained.get(id(writer)) is not writer
                        or type(state['source_connection_id']) is not int
                        or state['source_connection_id'] != peer.get('connection_id')):
                    return None
                registry = realm.registry
                game = registry.resolve(writer)
                realm.bound_account(writer, game)
                service = realm.service(writer)
                position, selected = service.snapshot(), game.selection
                if (selected is None or service.fatal or state['selected'] is not selected
                        or state['position'] is not position or position.uid != state['uid']
                        or selected.reference != position.name
                        or registry.selected.get(position.name) is not selected
                        or realm.store.select(selected.reference)[0] != position.uid
                        or realm.positions.restore(position) != position):
                    return None
                return (realm, registry, game, service, position, selected, state,
                        realm.store, realm.positions, policy.owner, policy.handle, policy.job,
                        self.owner_liveness_guard, self.source_guard)
            except (ValueError, KeyError, AttributeError):
                return None  # This handoff is off; the original exit-only refusal still applies.

        quit_binding = drained_quit_binding()

        def drained_quit_eof():
            if (quit_binding is None or not read_task.done() or read_task.cancelled()
                    or read_task.exception() is not None):
                return False
            raw = read_task.result()
            current = drained_quit_binding()
            return (type(raw) is bytes and raw == b'' and current is not None
                    and all(a is b for a, b in zip(quit_binding, current)))

        restart_state = row.get('_restart')
        restart_frame = None if restart_state is None else restart_state['frame']
        pending_restart = (not read_task.done() and operation_lock is not None
                           and restart_state is not None and restart_state['phase'] == 'DRAINED')

        def drained_restart_binding(*, eof=False):
            if not pending_restart:
                return None
            try:
                from tools.local_original_session import restart
                need(restart_state['frame'] is restart_frame
                     and restart.validate_ack(restart_frame, policy=self.restart_policy) is True
                     and row.get('_restart') is restart_state
                     and restart_state['lock'] is operation_lock
                     and row['operation_lock'] is operation_lock and operation_lock.locked()
                     and row.get('_read_task') is read_task and row['policy_row'] is policy_row
                     and self.policy is policy and row['peer'] is peer
                     and tuple(sorted(peer.items())) == peer_values
                     and policy_row.peer is quit_policy_peer
                     and decoder_empty is True and policy_row.buffered == 0
                     and policy_row.drain_started_ns is None and policy_row.pending_opcode is None
                     and policy_row.pending_size == 0 and restart_state['write_attempted'] is True
                     and restart_state['drain_returned'] is True
                     and restart_state['response_drained'] is True,
                     'RESTART_DRAINED_ACCOUNT_EOF_REQUIRED')
                current = self._restart_current(writer, row, state=restart_state, cleared=True, eof=eof)
                self._restart_same(restart_state['binding'], current)
                return current
            except (ValueError, KeyError, AttributeError):
                return None  # No new send/dispatch or inferred native-exit authority.

        restart_binding = drained_restart_binding()

        def drained_restart_eof():
            if (restart_binding is None or not read_task.done() or read_task.cancelled()
                    or read_task.exception() is not None):
                return False
            raw = read_task.result()
            current = drained_restart_binding()
            return (type(raw) is bytes and raw == b'' and current is not None
                    and len(current[0]) == len(restart_binding[0])
                    and all(a is b for a, b in zip(current[0], restart_binding[0]))
                    and current[1] == restart_binding[1])

        try:
            await self._checkpoint(writer, row)
            return False
        except ValueError as error:
            if error.args != ('CURRENT_OWNER_REQUIRED',):
                raise
            if first_bootstrap_eof():
                await self._complete_eof(writer, row, decoder_empty=decoder_empty)
                return True  # Ends this old stream; never dispatches or writes.
            if late_bootstrap_initial and not read_task.done() and late_bootstrap_binding():
                # The first bootstrap stream may finish its actual EOF one event-loop
                # turn after the failed tuple poll. Wait only for that retained read.
                alive = self.owner_liveness_guard()
                if inspect.isawaitable(alive):
                    alive = await asyncio.wait_for(alive, 1.5)
                self.source_guard()
                need(alive is True, 'CURRENT_RETAINED_OWNER_REQUIRED')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                try:
                    raw = await asyncio.wait_for(asyncio.shield(read_task), self.policy.CLOSE_NS / 1e9)
                except asyncio.TimeoutError:
                    raise error  # The same strict owner failure remains terminal; no inferred EOF.
                need(type(raw) is bytes and raw == b'' and late_bootstrap_eof(),
                     'BOOTSTRAP_TERMINAL_EOF_REQUIRED')
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                await self._complete_eof(writer, row, decoder_empty=decoder_empty,
                                         _binding_check=late_bootstrap_eof)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                return True  # Terminal old stream only; no live owner sample or dispatch.
            if drained_quit_eof():
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                await self._complete_eof(writer, row, decoder_empty=decoder_empty)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                return True  # EOF closes only this drained stream, not the native process.
            if drained_restart_eof():
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                await self._complete_eof(writer, row, decoder_empty=decoder_empty)
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                row['account_terminal_reason'] = 'DRAINED_RESTART_ACTUAL_EOF'
                return True
            state = self.realm._quit.get(id(writer))
            if (state is None or state['writer'] is not writer
                    or state['response_drained'] is not True):
                raise  # Ordinary polls retain the original strict-live refusal.
            # Only a fully drained source Quit can enter this terminal read.
            # No live OwnerSample, payload dispatch or write is permitted here.
            need(decoder_empty is True and row['policy_row'].buffered == 0,
                 'EXACT_DRAINED_QUIT_EOF_REQUIRED')
            return await self._drained_quit_read_eof(writer, row, read_task,
                decoder=decoder, decoder_empty=decoder_empty, quit_binding=quit_binding,
                binding_check=drained_quit_binding, original_error=error)


    async def join_quit_exit(self):
        """Give only proven terminal Quit tasks the existing close bound to join."""
        async def join():
            tasks = []
            for rows in self._claims.values():
                for row in rows:
                    task = row.get('task')
                    state = self.realm._quit.get(id(row['writer']))
                    if (task is not None and not task.done() and state is not None
                            and state['writer'] is row['writer']
                            and state['response_drained'] is True):
                        await self._quit_exit(row['writer'], row)
                        tasks.append(task)
            if tasks:
                await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            return dict(eligible=len(tasks), joined=sum(task.done() for task in tasks))
        try:
            return await asyncio.wait_for(join(), self.policy.CLOSE_NS / 1e9)
        except (ValueError, TimeoutError):
            return dict(status='UNKNOWN')


    def _quit_closing_witness(self, writer, row, position):
        """First-ACK drain and this exact frame's already-proved owner sample."""
        from tools.local_original_session.manual_source_quit import SourceQuitRequests
        source = self._source_quit_closing
        if type(source) is not SourceQuitRequests:
            return False
        try:
            policy, realm = self.policy, self.realm
            peer, policy_row = row['peer'], row['policy_row']
            state = realm._quit.get(id(writer))
            evidence = source._drain_evidence
            receipt = row['_quit_frame_owner']
            late = source._requests.get('Quit6Approval')
            first = source._requests.get('FirstLandQuit')
            first_returned = source._returned.get('FirstLandQuit')
            claims = [claim for rows in self._claims.values() for claim in rows
                      if claim['writer'] is writer]
            frame_receipt = type(receipt) is tuple and len(receipt) == 10
            terminal_receipt = type(receipt) is _TerminalQuitReceipt
            sample = receipt[7] if frame_receipt else None
            return (source.broker is self and source.owner is policy.owner
                    and source.consumer.reader.owner is policy.owner
                    and source.requests.consumer is source.consumer
                    and source._started is True and source._closed is False
                    and source._claimed == {'FirstLandQuit', 'Quit6Approval'}
                    and type(first) is dict and type(late) is dict
                    and type(first_returned) is tuple and len(first_returned) == 2
                    and first_returned[0]['status'] == 'RETURNED'
                    and type(first['seq']) is int and type(late['seq']) is int
                    and 0 < first['seq'] < late['seq'] == source.consumer.sequence
                    and type(evidence) is tuple and len(evidence) == 5
                    and evidence[0] is writer and evidence[1] is row
                    and evidence[2] is realm and evidence[3] is state
                    and evidence[4] == peer['connection_id'] == 4
                    and state is not None and state['writer'] is writer
                    and state['position'] is position
                    and state['source_connection_id'] == peer['connection_id']
                    and all(state[key] is True for key in ('request_verified',
                        'response_drain_returned', 'response_queue_empty', 'response_drained'))
                    and policy._quit_drained.get(id(writer)) is writer
                    and len(claims) == 1 and claims[0] is row
                    and row['writer'] is writer
                    and row['await_phase'] == ('FRAME_DISPATCH' if frame_receipt
                                                 else 'TERMINAL_QUIT_DISPATCH')
                    and row['operation_lock'].locked() and not row['failed']
                    and not row['joined'] and not row['eof']
                    and policy_row is policy._connection(writer)
                    and policy_row.writer is writer and policy_row.stage == 1
                    and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
                    and not policy_row.eof and policy_row.drain_started_ns is None
                    and policy_row.pending_opcode is None and policy_row.pending_size == 0
                    and policy_row.buffered == 0 and policy.state == 'OPEN'
                    and not self._closing and not self.failure.is_set()
                    and ((frame_receipt
                          and receipt[0] is writer and receipt[1] is row and receipt[2] is peer
                          and receipt[3] == tuple(sorted(peer.items()))
                          and receipt[4] is policy_row and receipt[5] is row['operation_lock']
                          and receipt[6] is writer.transport
                          and receipt[8] == QUIT_REQUEST and receipt[9] == 10
                          and type(sample) is OwnerSample and sample.owner is policy.owner
                          and sample.handle is policy.handle and sample.job is policy.job
                          and sample.exact_identity_and_tuple is True and sample.alive is True
                          and sample.peer.port == peer['server_port'] == peer['endpoint_port'] == 14030
                          and sample.peer.client_port == peer['client_port']
                          and sample.peer.accepted_ns == peer['accepted_monotonic_ns']
                          and type(sample.observed_ns) is int
                          and 0 < sample.observed_ns <= time.monotonic_ns())
                         or (terminal_receipt and receipt.broker is self
                             and receipt.writer is writer and receipt.row is row
                             and receipt.peer is peer and receipt.peer_values == tuple(sorted(peer.items()))
                             and receipt.policy_row is policy_row
                             and receipt.operation_lock is row['operation_lock']
                             and receipt.transport is writer.transport
                             and receipt.read_task is row['_read_task']
                             and receipt.read_task.done() and not receipt.read_task.cancelled()
                             and receipt.read_task.exception() is None
                             and type(receipt.read_task.result()) is bytes
                             and len(receipt.read_task.result()) == 10
                             and type(receipt.decoder) is ClientPlaintextDecoder
                             and receipt.decoder.buffered_bytes == 0
                             and type(receipt.frame) is Frame
                             and receipt.frame.opcode == QUIT_REQUEST
                             and receipt.frame.wire_length == 10
                             and receipt.frame.payload == b''
                             and state['duplicate_requests'] == 0)))
        except (AttributeError, KeyError, TypeError, ValueError):
            return False


    async def _quit_duplicate_owner(self, writer, row, position):
        """No-effect duplicate Quit using the strict sample from this frame."""
        if not self._selected_owner_current(writer, row, position):
            self._owner_failure(row, 'QUIT_SELECTED_CURRENT_FALSE')
            return False
        if self._source_quit_closing is None:
            return await self._movement_owner(writer, row, position)
        if not self._quit_closing_witness(writer, row, position):
            self._owner_failure(row, 'QUIT_SOURCE_FRAME_WITNESS_FALSE')
            return False
        from tools.local_original_session.launcher import NativeOwner
        owner = self.policy.owner
        receipt = row['_quit_frame_owner']
        terminal = type(receipt) is _TerminalQuitReceipt
        method = 'quit_terminal_retained_sync'
        target = getattr(NativeOwner, method, None)
        callback = getattr(owner, method, None)
        if (type(owner) is not NativeOwner or target is None
                or getattr(callback, '__self__', None) is not owner
                or getattr(callback, '__func__', None) is not target):
            self._owner_failure(row, 'QUIT_NATIVE_CALLBACK_BINDING_FALSE')
            return False
        current = callback(row['peer'])  # The broker witness bound either receipt.
        if current is not True:
            self._owner_failure(row, 'QUIT_RETAINED_PRIMARY_FALSE' if terminal
                                else 'QUIT_FRAME_RETAINED_FALSE')
            return False
        self.source_guard()
        current = (self._quit_closing_witness(writer, row, position)
                   and self._selected_owner_current(writer, row, position))
        if not current:
            self._owner_failure(row, 'QUIT_POST_CURRENT_FALSE')
        return current


    def _restart_current(self, writer, row, *, state=None, cleared=False, eof=False):
        """Actual current account/selection; no caller-supplied authorization."""
        from tools.local_original_session.broker import LocalRealm
        from tools.local_original_session import restart
        need(self.restart_policy == restart.POLICY and self.policy.restart_enabled is True
             and not self._closing and not self.failure.is_set() and self.policy.state == 'OPEN',
             'RESTART_CURRENT_BROKER_REQUIRED')
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        policy_row = self.policy._connection(writer)
        need(len(claims) == 1 and claims[0] is row and row['writer'] is writer
             and row['policy_row'] is policy_row and policy_row.writer is writer
             and policy_row.stage == 1 and policy_row.rx_boot == 2 and policy_row.tx_boot == 3
             and not any((row['failed'], row['joined'], policy_row.failed,
                          policy_row.task_joined, policy_row.registry_removed))
             and row['eof'] is eof and policy_row.eof is eof
             and row['operation_lock'].locked(), 'RESTART_CURRENT_ROW_REQUIRED')
        realm = self.realm
        need(type(realm) is LocalRealm and realm._restart_broker is self
             and not realm._settings_failed and id(writer) not in realm._quit,
             'RESTART_CURRENT_REALM_REQUIRED')
        game = realm.registry.resolve(writer)
        realm.bound_account(writer, game)
        if cleared:
            need(state is not None and row.get('_restart') is state and state['phase'] == 'DRAINED'
                 and state['selection_cleared'] is True, 'RESTART_DRAINED_STATE_REQUIRED')
            service, position, selected = state['binding'][0][8:11]
            need(game.selection is None and selected.reference not in realm.registry.selected
                 and all(id(writer) not in mapping for mapping in (
                     realm._movement, realm._world_frames, realm._npc_frames, realm._npc_motion)),
                 'RESTART_CLEARED_SELECTION_REQUIRED')
        else:
            service = realm.service(writer)
            position, selected = service.snapshot(), game.selection
            need(selected is not None and realm.registry.selected.get(position.name) is selected
                 and selected.reference == position.name, 'RESTART_CURRENT_SELECTION_REQUIRED')
        need(type(service) is movement.MovementService and service._connection is writer
             and not service.fatal and service.snapshot() is position
             and realm.store.select(selected.reference)[0] == position.uid
             and realm.positions.restore(position) == position, 'RESTART_COMMITTED_POSITION_REQUIRED')
        account = realm._account_bound[id(writer)]
        settings_store = realm.settings
        if settings_store is not None:
            need(type(settings_store) is settings.SettingsStore and not settings_store.failed,
                 'RESTART_CURRENT_SETTINGS_REQUIRED')
            record = settings_store._load()
            need((None if record is None else record.metadata()) == settings_store.last,
                 'RESTART_COMMITTED_SETTINGS_REQUIRED')
        objects = (self, self.policy, row, row['peer'], policy_row, policy_row.peer,
                   realm, game, service, position, selected, realm.registry, realm.store,
                   realm.positions, settings_store, account, game.roster, self.policy.owner,
                   self.source_guard, self.key_guard, self.owner_guard, self.owner_liveness_guard,
                   row['operation_lock'])
        values = tuple((type(v), v) for v in (self.policy.handle, self.policy.job,
            *row['peer'].keys(), *row['peer'].values(), policy_row.peer.port,
            policy_row.peer.client_port, policy_row.peer.accepted_ns,
            None if settings_store is None else settings_store.committed,
            *((settings_store.last or {}).keys() if settings_store is not None else ()),
            *((settings_store.last or {}).values() if settings_store is not None else ())))
        return objects, values


    @staticmethod
    def _restart_same(before, after):
        need(len(before[0]) == len(after[0]) and all(a is b for a, b in zip(before[0], after[0]))
             and before[1] == after[1], 'RESTART_AUTHORITY_CHANGED')


    def _validate_restart(self, writer, wire, *, phase):
        from tools.local_original_session import restart
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        need(len(claims) == 1, 'RESTART_CURRENT_ROW_REQUIRED')
        row = claims[0]
        state = row.get('_restart')
        need(state is not None and state['phase'] == phase and wire is state['frame']
             and type(wire) is bytes and row['operation_lock'] is state['lock'],
             'RESTART_CURRENT_FRAME_REQUIRED')
        self.source_guard()
        self.key_guard()
        self._restart_current(writer, row)
        return row, state


    async def _prepare_restart(self, writer, payload):
        from tools.local_original_session import restart
        restart.parse_request(payload)
        claims = [r for rows in self._claims.values() for r in rows if r['writer'] is writer]
        need(len(claims) == 1, 'RESTART_CURRENT_ROW_REQUIRED')
        row = claims[0]
        before = self._restart_current(writer, row)
        previous = row.get('_restart')
        need(previous is None or previous['phase'] == 'DRAINED', 'RESTART_PREVIOUS_OUTCOME_UNRESOLVED')
        frame = restart.build_ack(success=True, policy=self.restart_policy)
        state = dict(phase='PREPARING', frame=frame, binding=before,
                     lock=row['operation_lock'], write_attempted=False, drain_returned=False,
                     response_drained=False, selection_cleared=False)
        row['_restart'] = state
        try:
            need(row['policy_row'].drain_started_ns is None, 'RESTART_UNRESERVED_POLICY_REQUIRED')
            await self._checkpoint(writer, row)
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError()
            state['phase'] = 'PREPARED'
            return (frame,)
        except BaseException:
            state['phase'] = 'TERMINAL'
            raise


    def _restart_selection_drained(self, writer, row, state):
        realm, game, service, position, selected = state['binding'][0][6:11]
        metadata = realm._movement_metadata(realm._movement[id(writer)], closed=True)
        mover = realm._npc_motion.get(id(writer))
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError()
        inventory_generation = None
        if getattr(self, 'inventory_reselection_policy', None) is not None:
            inventory_generation = self.inventory_selection_current(writer)
            need(inventory_generation is not None and inventory_generation.row is row
                 and inventory_generation.lock.locked(), 'INVENTORY_RESELECTION_RETIRE_CURRENT_REQUIRED')
        if inventory_generation is not None and inventory_generation.transfer_session is not None:
            inventory_generation.transfer_session.release(writer)
        # All fallible authority/storage/source checks precede this synchronous
        # selection-only cleanup. The real registered game/account are retained.
        if realm._item_use_session is not None:
            realm._item_use_session.release(writer)
        if realm._attack_session is not None:
            realm._attack_session.release(writer)
        life = getattr(self,'_player_life',None)
        life_broker = getattr(self,'_player_life_broker',None)
        if life is None and life_broker is not None: life = life_broker._player_life
        if life is not None: life.release(writer)
        player_hit = getattr(self, '_npc_player_hit', None)
        if player_hit is not None:
            player_hit.release(writer)
        status = getattr(self, '_hp_status', None)
        if status is not None:
            status.release(writer)
        if mover is not None:
            mover[1].close()
        realm._npc_motion.pop(id(writer), None)
        realm._npc_frames.pop(id(writer), None)
        realm._world_frames.pop(id(writer), None)
        realm._movement.pop(id(writer))
        realm._movement_closed.append(metadata)
        realm.registry.selected.pop(selected.reference)
        game.selection = None
        state['phase'] = 'DRAINED'
        state['selection_cleared'] = True
        if inventory_generation is not None:
            inventory_generation.service.close()
            if inventory_generation.item_use_session is not None:
                inventory_generation.item_use_session.close()
            inventory_generation.restart_state = state
            inventory_generation.phase = 'RETIRED'



class RealmLifecycle:
    """Selected Quit routes and reporting on the existing realm."""
    def quit_state(self, writer):
        state = self._quit.get(id(writer))
        need(state is not None and state['writer'] is writer and state['request_verified'] is True,
             'VERIFIED_SELECTED_QUIT_REQUEST_REQUIRED')
        return state


    def quit_response_drained(self, writer, wire, queued_bytes):
        need(wire == QUIT_SUCCESS_FRAME, 'EXACT_QUIT_SUCCESS_RESPONSE_REQUIRED')
        state = self.quit_state(writer)
        state['response_drain_returned'] = True
        state['response_queue_empty'] = type(queued_bytes) is int and queued_bytes == 0


    @staticmethod
    def _quit_metadata(state):
        return {key: state[key] for key in ('uid', 'source_connection_id', 'request_verified', 'response_drain_returned',
                                           'response_queue_empty', 'response_drained', 'duplicate_requests')}


    def quit_report(self):
        sessions = [*list(self._quit_closed), *(self._quit_metadata(state) for state in self._quit.values())]
        return dict(active=len(self._quit), sessions=sessions, scope='SOURCE_QUIT_RESPONSE_DRAIN_ONLY',
                    source_quit_response_drained=any(all(row[key] is True for key in
                        ('request_verified', 'response_drain_returned', 'response_queue_empty', 'response_drained'))
                        for row in sessions),
                    duplicate_policy='LOCAL_DRAINED_EMPTY_QUIT_NO_EFFECT')


    async def _quit_game(self, writer, game, payload, movement_owner_guard, closing_quit_owner_guard=None, connection_id=None):
        self.bound_account(writer, game)
        need(type(payload) in (bytes, bytearray, memoryview) and len(payload) == 0,
             'QUIT_EMPTY_SOURCE_BODY_REQUIRED')
        need(game.selection is not None and callable(movement_owner_guard), 'QUIT_SELECTED_OWNER_REQUIRED')
        service = self.service(writer)
        position = service.snapshot()
        need(not service.fatal, 'QUIT_SELECTED_STORAGE_FATAL')
        state = dict(writer=writer, uid=position.uid, source_connection_id=connection_id,
                     selected=game.selection, position=position,
                     duplicate_requests=0, request_verified=False,
                     response_drain_returned=False, response_queue_empty=False, response_drained=False)
        self._quit[id(writer)] = state  # Block parallel requests until the first response drains.
        need(await movement_owner_guard(writer, position) is True, 'QUIT_CURRENT_SELECTED_OWNER_REQUIRED')
        self.bound_account(writer, game)
        need(service.snapshot() is position and not self._settings_failed,
             'QUIT_CURRENT_SELECTED_AUTHORITY_REQUIRED')
        state['request_verified'] = True
        return (QUIT_SUCCESS_FRAME,)

    async def _duplicate_quit(self, writer, game, payload, movement_owner_guard, closing_quit_owner_guard=None, connection_id=None):
        state = self._quit.get(id(writer))
        need(state is not None and state['writer'] is writer and state['request_verified'] is True
             and state['response_drain_returned'] is True and state['response_drained'] is True
             and state['response_queue_empty'] is True, 'QUIT_TERMINAL_SESSION')
        need(type(payload) in (bytes, bytearray, memoryview) and len(payload) == 0,
             'QUIT_EMPTY_SOURCE_BODY_REQUIRED')
        self.bound_account(writer, game)
        service = self.service(writer)
        position, selected = state['position'], state['selected']

        def exact():
            self.bound_account(writer, game)
            return (self._quit.get(id(writer)) is state and not self._settings_failed
                    and state['writer'] is writer and state['request_verified'] is True
                    and state['response_drain_returned'] is True
                    and state['response_drained'] is True and state['response_queue_empty'] is True
                    and not service.fatal and self.service(writer) is service
                    and service.snapshot() is position and position.uid == state['uid']
                    and game.selection is selected and selected is not None
                    and selected.reference == position.name
                    and self.registry.selected.get(position.name) is selected)

        need(exact() and callable(movement_owner_guard), 'QUIT_CURRENT_SELECTED_AUTHORITY_REQUIRED')
        duplicate_owner = closing_quit_owner_guard or movement_owner_guard
        need(await duplicate_owner(writer, position) is True, 'QUIT_CURRENT_SELECTED_OWNER_REQUIRED')
        # Explicit local idempotency: preserve the first terminal state and
        # its one ACK. This does not assert why the original retries Quit.
        state['duplicate_requests'] = min(MAX_COUNTER, state['duplicate_requests'] + 1)
        return ()

