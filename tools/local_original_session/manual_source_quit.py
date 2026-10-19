"""Explicit first/late source Quit IPC; RETURNED never proves drain or exit.

The launcher owns WM_CLOSE, its original grace, EOF/exit/Job classification and
cleanup. This adapter creates no process, thread, desktop, packet or observer.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from types import MethodType

from tools.local_original_session import commands, manual_move_commands as manual
from tools.local_original_session.broker import PersistentBroker

need = manual.need
_PHASES = ('FirstLandQuit', 'Quit6Approval')
_LAUNCHER = Path(__file__).with_name('launcher.py').resolve()
_DESKTOP = Path(__file__).with_name('desktop.py').resolve()


def _actual_export(value, export, path):
    cls = type(value)
    function = getattr(cls, '__init__', None)
    return (getattr(function, '__globals__', {}).get(export) is cls
            and getattr(function, '__qualname__', None) == export + '.__init__'
            and Path(function.__code__.co_filename).resolve() == path)


@dataclass(frozen=True, slots=True)
class _Completion:
    first: tuple
    late: tuple
    drain: tuple
    snapshot: tuple


class SourceQuitRequests:
    def __init__(self, owner, requests, broker, directory):
        # Factory construction can precede NativeOwner.prepare/bind.
        need(_actual_export(requests, 'ManualMoveRequests', _LAUNCHER)
             and type(requests.consumer) is manual.ManualMoveCommands
             and type(broker) is PersistentBroker, 'SOURCE_QUIT_REAL_REQUESTS_REQUIRED')
        self.owner, self.requests, self.broker = owner, requests, broker
        self.consumer, self.directory = requests.consumer, Path(directory).absolute()
        self._busy = self._started = self._closed = False
        self._pending = self._desktop = self._initial = self._hwnd = None
        self._claimed, self._returned, self._requests = set(), {}, {}
        self._drain_evidence = self._completion = None
        self._state = dict(status='NOT_REQUESTED', reason=None, cleanup_required=False)

    def report(self):
        if type(self._completion) is _Completion:
            return dict(self._completion.snapshot)
        state = self._state
        if state.get('status') == 'RETURNED':
            state = dict(status='UNKNOWN', reason='SOURCE_QUIT_COMPLETION_EVIDENCE_REQUIRED', cleanup_required=True)
        return dict(state, command='SourceQuit', automatic_retry=False,
                    first_claimed=_PHASES[0] in self._claimed, late_claimed=_PHASES[1] in self._claimed,
                    first_returned=_PHASES[0] in self._returned, late_returned=_PHASES[1] in self._returned,
                    sequence=self.consumer.sequence, normal_exit_verified=False,
                    native_attempted=(self._pending is not None and self._pending['native_attempted']))

    def _fail(self, reason):
        self._state = dict(status='UNKNOWN', reason=reason, cleanup_required=True)
        terminal = self.consumer._terminal(reason)
        if 'window_observation' in terminal:
            self._state['window_observation'] = dict(terminal['window_observation'])
        return self.report()

    def _wrapper(self, *, quiesced):
        requests = self.requests
        need(_actual_export(requests, 'ManualMoveRequests', _LAUNCHER)
             and requests.consumer is self.consumer
             and Path(requests.directory).absolute() == self.directory,
             'SOURCE_QUIT_REQUESTS_CHANGED')
        if quiesced:
            need(requests.closed is True and requests._polling is False and requests.pending is False
                 and requests._inventory_request is None and requests._inventory_wait is None,
                 'SOURCE_QUIT_INGRESS_NOT_QUIESCED')
        need(not self._closed and self._state['status'] != 'UNKNOWN', 'SOURCE_QUIT_TERMINAL')
        need(self._state['status'] in ('NOT_REQUESTED', 'PENDING'),
             'SOURCE_QUIT_COMPLETION_EVIDENCE_REQUIRED')

    def _fresh(self):
        self._wrapper(quiesced=True)
        manual._source_quit_cancel_check()
        need(self.consumer.pending is self._pending and self._pending is not None
             and self._pending['kind'] == 'SourceQuit', 'SOURCE_QUIT_PENDING_CHANGED')
        current = self.consumer._admission_current()
        owner, reader = self.owner, self.consumer.reader
        need(current[0].broker is self.broker and reader.owner is owner
             and owner.private_desktop is self._desktop and owner.child is reader.member
             and _actual_export(self._desktop, 'PrivateDesktop', _DESKTOP), 'SOURCE_QUIT_OWNER_CHANGED')
        need(current[3] is self._initial and current[5] == self._boundary,
             'SOURCE_QUIT_AUTHORITY_CHANGED')
        need(self.consumer._window(current) == self._hwnd, 'SOURCE_QUIT_WINDOW_CHANGED')
        need(self.consumer._clock() - self._pending['started'] < manual.WAIT_NS,
             'SOURCE_QUIT_ORIGINAL_DEADLINE')
        current = self.consumer._admission_current()
        manual._source_quit_cancel_check()
        need(not self._closed and self._state['status'] != 'UNKNOWN'
             and self.consumer.state['status'] != 'UNKNOWN', 'SOURCE_QUIT_TERMINAL')
        return current

    def _publish(self, phase):
        need(phase in _PHASES and phase not in self._claimed, 'SOURCE_QUIT_PHASE_ALREADY_CLAIMED')
        current = self._fresh()
        self._claimed.add(phase)  # No rearm after claim/publication/provider ambiguity.
        self._pending.update(source_phase=phase, phase='ADMISSION', native_attempted=False,
                             native=None, result_identity=None)
        self.consumer._publish(current, self._hwnd)
        self._requests[phase] = dict(self._pending['request'])
        self._fresh()
        self._state = dict(status='PENDING', reason=None, cleanup_required=False, phase=phase,
                           native_attempted=self._pending['native_attempted'])

    def _native_settled(self):
        if self.consumer.pending is not None:
            return False
        if self.consumer.state['status'] in ('READY', 'COMMITTED'):
            return True
        if self.consumer.state['status'] != 'PREPARED':
            return False
        settled = self.requests.lethal_preparation_settled
        need(type(settled) is MethodType and settled.__self__ is self.requests
             and settled.__func__ is type(self.requests).__dict__.get('lethal_preparation_settled')
             and settled.__func__.__globals__.get('ManualMoveRequests') is type(self.requests)
             and Path(settled.__func__.__code__.co_filename).resolve() == _LAUNCHER,
             'SOURCE_QUIT_REAL_PREPARATION_REQUIRED')
        proof = settled()
        return (proof is not None and proof is self.requests._lethal_preparation_proof
                and proof is self.consumer._lethal_preparation_completed)

    def start(self, windows_requested):
        if type(self._completion) is _Completion:
            return self.report()
        if self._busy:
            return self._fail('SOURCE_QUIT_REENTRANT')
        if self._started or self._closed or self._state['status'] == 'UNKNOWN':
            return self.report()
        entered = False
        try:
            need(not self._busy, 'SOURCE_QUIT_REENTRANT')
            self._busy = True
            self.consumer._enter()
            entered = True
            self._started = True
            need(type(windows_requested) is int and windows_requested > 0, 'SOURCE_QUIT_OWNED_CLOSE_REQUIRED')
            self._wrapper(quiesced=False)
            need(self._native_settled(),
                 'SOURCE_QUIT_NATIVE_OUTCOME_UNRESOLVED')
            # Obtain real binding before invoking the launcher's quiesce policy.
            current = self.consumer._current()
            need(current[0].broker is self.broker and self.consumer.reader.owner is self.owner,
                 'SOURCE_QUIT_OWNER_CHANGED')
            quiesce = self.requests.quiesce_for_source_quit
            need(type(quiesce) is MethodType and quiesce.__self__ is self.requests
                 and quiesce.__func__ is type(self.requests).__dict__.get('quiesce_for_source_quit')
                 and quiesce.__func__.__globals__.get('ManualMoveRequests') is type(self.requests)
                 and Path(quiesce.__func__.__code__.co_filename).resolve() == _LAUNCHER,
                 'SOURCE_QUIT_REAL_QUIESCE_REQUIRED')
            need(quiesce() is True, 'SOURCE_QUIT_QUIESCE_REFUSED')
            self._wrapper(quiesced=True)
            need(self._native_settled(),
                 'SOURCE_QUIT_NATIVE_OUTCOME_UNRESOLVED')
            now = self.consumer._clock()
            current = self.consumer._current()
            owner = self.owner
            need(self.consumer.reader.owner is owner and owner.child is self.consumer.reader.member
                 and _actual_export(owner.private_desktop, 'PrivateDesktop', _DESKTOP),
                 'SOURCE_QUIT_PRIVATE_DESKTOP_REQUIRED')
            self._desktop, self._initial, self._boundary = owner.private_desktop, current[3], current[5]
            self._hwnd = self.consumer._window(current)
            self._pending = dict(kind='SourceQuit', phase='ADMISSION', native_attempted=False,
                initial=current[3], before=current[7], started=now, request=None,
                native=None, result_identity=None, source_owner=owner, source_desktop=self._desktop)
            self.consumer.pending = self._pending
            self._publish(_PHASES[0])
        except asyncio.CancelledError:
            self._fail('SOURCE_QUIT_CANCELLED')
            raise
        except BaseException as error:
            self._fail(self.consumer._reason(error))
        finally:
            if entered:
                self.consumer._busy = False
            self._busy = False
        return self.report()

    def _result(self, phase, sequence):
        path = self._boundary / ('source-quit-result-' + str(sequence) + '.json')
        try:
            row = commands._closed_health_json(path)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeError):
            row = None
        old = self._returned.get(phase)
        if row is None:
            need(old is None, 'SOURCE_QUIT_IMMUTABLE_RESULT_DISAPPEARED')
            return False
        request = self._requests[phase]
        expected = dict(request, schema='own-manual-source-quit-result-v1')
        need(set(row) == set(expected) | {'status', 'reason', 'invoked'}
             and all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items())
             and type(row['reason']) is int and type(row['invoked']) is bool,
             'SOURCE_QUIT_RESULT_SCHEMA_OR_IDENTITY')
        need(row['status'] == 'RETURNED' and row['reason'] == 0 and row['invoked'] is True,
             'SOURCE_QUIT_NATIVE_NOT_RETURNED')
        stat = commands._ordinary(path).stat()
        identity = stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
        need(old is None or old == (row, identity), 'SOURCE_QUIT_IMMUTABLE_RESULT_CHANGED')
        self._returned[phase] = dict(row), identity
        return True

    def _drained(self, current):
        realm, writer = self.broker.realm, current[0].writer
        state = realm._quit.get(id(writer))
        if state is None:
            return False
        need(state['writer'] is writer
             and state['selected'] is realm.registry.resolve(writer).selection
             and state['position'] is self._initial and state['uid'] == self._initial.uid
             and type(state['source_connection_id']) is int
             and state['source_connection_id'] == current[1]['peer']['connection_id'],
             'SOURCE_QUIT_SAME_WRITER_DRAIN_REQUIRED')
        keys = ('request_verified', 'response_drain_returned', 'response_queue_empty', 'response_drained')
        need(all(type(state[key]) is bool for key in keys), 'SOURCE_QUIT_DRAIN_UNKNOWN')
        drained = (all(state[key] is True for key in keys) and realm.quit_state(writer) is state
                   and self.broker.policy._quit_drained.get(id(writer)) is writer)
        if drained:
            self._drain_evidence = (writer, current[1], realm, state, state['source_connection_id'])
        return drained

    def _seal(self, current):
        # Both immutable native results were just collected. Do not query a
        # disappearing process/window again to reinterpret those past returns.
        need(self.consumer._clock() - self._pending['started'] < manual.WAIT_NS,
             'SOURCE_QUIT_ORIGINAL_DEADLINE')
        manual._source_quit_cancel_check()
        need(self._busy and self.consumer._busy and not self._closed
             and self._state['status'] != 'UNKNOWN' and self.consumer.state['status'] != 'UNKNOWN'
             and self.consumer.pending is self._pending and self._pending['kind'] == 'SourceQuit'
             and self._pending['source_phase'] == _PHASES[1] and self._pending['native_attempted'] is True,
             'SOURCE_QUIT_TERMINAL')
        need(self._claimed == set(_PHASES) and set(self._returned) == set(_PHASES)
             and type(self._drain_evidence) is tuple and len(self._drain_evidence) == 5
             and self._drain_evidence[0] is current[0].writer
             and self._drain_evidence[1] is current[1]
             and self._drain_evidence[2] is self.broker.realm
             and self._drain_evidence[4] == current[1]['peer']['connection_id']
             and self.consumer.sequence == self._requests[_PHASES[1]]['seq']
             and self._pending['request'] == self._requests[_PHASES[1]],
             'SOURCE_QUIT_COMPLETION_EVIDENCE_REQUIRED')
        first, late = (self._returned[phase] for phase in _PHASES)
        snapshot = dict(status='RETURNED', reason='SOURCE_QUIT_EXIT_UNVERIFIED', cleanup_required=False,
            phase=_PHASES[1], command='SourceQuit', automatic_retry=False,
            first_claimed=True, late_claimed=True, first_returned=True, late_returned=True,
            sequence=self.consumer.sequence, normal_exit_verified=False, native_attempted=True)
        self._completion = _Completion((tuple(first[0].items()), first[1]),
            (tuple(late[0].items()), late[1]), self._drain_evidence, tuple(snapshot.items()))

    def poll(self):
        if type(self._completion) is _Completion:
            return self.report()
        if not self._started or self._closed or self._state['status'] == 'UNKNOWN':
            return self.report()
        entered = False
        try:
            need(not self._busy, 'SOURCE_QUIT_REENTRANT')
            self._busy = True
            self.consumer._enter()
            entered = True
            current = self._fresh()
            phase = self._pending['source_phase']
            for previous in tuple(self._returned):
                self._result(previous, self._requests[previous]['seq'])
            returned = self._result(phase, self._requests[phase]['seq'])
            if returned and phase == _PHASES[1]:
                self._seal(current)
            else:
                current = self._fresh()
                if returned and phase == _PHASES[0]:
                    if self._drained(current):
                        self._fresh()
                        self._publish(_PHASES[1])
                    else:
                        self._state.update(status='PENDING', reason='SOURCE_QUIT_SAME_WRITER_DRAIN_PENDING')
                self._fresh()
        except asyncio.CancelledError:
            self._fail('SOURCE_QUIT_CANCELLED')
            raise
        except BaseException as error:
            self._fail(self.consumer._reason(error))
        finally:
            if entered:
                self.consumer._busy = False
            self._busy = False
        return self.report()

    def close(self):
        if type(self._completion) is _Completion:
            self._closed = True
            return self.report()
        self._closed = True
        if self._started and self._state['status'] != 'UNKNOWN':
            self._fail('SOURCE_QUIT_CLOSED')
        return self.report()
