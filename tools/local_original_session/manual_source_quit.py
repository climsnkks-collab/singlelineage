"""Explicit first/late source Quit IPC; RETURNED never proves drain or exit.

The launcher owns WM_CLOSE, its original grace, EOF/exit/Job classification and
cleanup. This adapter creates no process, thread, desktop, packet or observer.
"""
from __future__ import annotations

import asyncio
import copy
import threading
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
    def __init__(self, owner, requests, broker, directory, *, features=None):
        # Factory construction can precede NativeOwner.prepare/bind.
        need(_actual_export(requests, 'ManualMoveRequests', _LAUNCHER)
             and type(requests.consumer) is manual.ManualMoveCommands
             and type(broker) is PersistentBroker, 'SOURCE_QUIT_REAL_REQUESTS_REQUIRED')
        self._features = features
        self._exit_only = False
        self._exit_entry = self._failure_state = self._failure_data = self._failure_pending = None
        self._exit_popup = self._failure_domain = None
        self._failure_phase = self._failure_quantity = self._failure_refs = None
        self.owner, self.requests, self.broker = owner, requests, broker
        self.consumer, self.directory = requests.consumer, Path(directory).absolute()
        self._busy = self._started = self._closed = False
        self._pending = self._desktop = self._initial = self._hwnd = None
        self._claimed, self._returned, self._requests = set(), {}, {}
        self._drain_evidence = self._completion = None
        self._observations, self._observation_errors = {}, {}
        self._state = dict(status='NOT_REQUESTED', reason=None, cleanup_required=False)

    def report(self):
        if type(self._completion) is _Completion:
            return copy.deepcopy(dict(self._completion.snapshot))
        state = self._state
        if state.get('status') == 'RETURNED':
            state = dict(status='UNKNOWN', reason='SOURCE_QUIT_COMPLETION_EVIDENCE_REQUIRED', cleanup_required=True)
        return dict(state, command='SourceQuit', automatic_retry=False,
                    first_claimed=_PHASES[0] in self._claimed, late_claimed=_PHASES[1] in self._claimed,
                    first_returned=_PHASES[0] in self._returned, late_returned=_PHASES[1] in self._returned,
                    sequence=self.consumer.sequence, normal_exit_verified=False,
                    native_attempted=(self._pending is not None and self._pending['native_attempted']),
                    native_observation=self._observation_report())

    def _fail(self, reason):
        self._state = dict(status='UNKNOWN', reason=reason, cleanup_required=True)
        terminal = (self.consumer.state if self._exit_only or self._failure_domain == 'BACKEND'
                    and self.consumer.state['status'] == 'UNKNOWN' else self.consumer._terminal(reason))
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

    def _failure_current(self):
        from tools.local_original_session.item_transfer_ui import ItemTransferUI
        from tools.local_original_session.item_transfer_entry import EntryHost
        from tools.local_original_session.item_quantity_popup import PopupHost
        features = self._features
        need(self._exit_only and self._busy and self.consumer.state is self._failure_state
             and self.consumer.state == self._failure_data
             and self.consumer.state['status'] == 'UNKNOWN', 'SOURCE_QUIT_FAILURE_STATE_CHANGED')
        need(_actual_export(features, 'ProductFeatures', _LAUNCHER) and not features._closed
             and features.manual is self.requests and type(features.item_transfer_ui) is ItemTransferUI,
             'SOURCE_QUIT_ACTUAL_FAILED_FEATURE_REQUIRED')
        ui = features.item_transfer_ui
        need(ui.runtime is features and ui.manual is self.requests and ui.consumer is self.consumer
             and ui.broker is self.broker and ui.closed,
             'SOURCE_QUIT_FAILED_FEATURE_LIFETIME_CHANGED')
        if self._failure_domain == 'ENTRY':
            need(ui.phase in ('DROP_ENTRY_WAIT','GET_ENTRY_WAIT') and ui.entry is self._exit_entry
                 and type(ui.entry) is EntryHost and ui.popup.pending is None and ui.popup._frame is None,
                 'SOURCE_QUIT_FAILED_ENTRY_LIFETIME_CHANGED')
            adapter = ui.entry
        elif self._failure_domain == 'POPUP':
            need(ui.phase in ('DROP_POPUP_WAIT','GET_POPUP_WAIT') and ui.popup is self._exit_popup
                 and type(ui.popup) is PopupHost and type(ui.entry) is EntryHost
                 and ui.entry.manual is self.consumer and ui.entry.pending is None and ui.entry._frame is None
                 and ui.entry.terminal is False and ui.entry.native_refusal() is None,
                 'SOURCE_QUIT_FAILED_POPUP_LIFETIME_CHANGED')
            adapter = ui.popup
        elif self._failure_domain == 'BACKEND':
            need(ui.phase == self._failure_phase and ui.phase in ('DROP_BACKEND','RETURN_BACKEND')
                 and type(ui._quantity) is int and ui._quantity == self._failure_quantity
                 and type(ui.entry) is EntryHost and type(ui.popup) is PopupHost
                 and ui.entry.manual is ui.popup.manual is self.consumer
                 and ui.entry.pending is ui.popup.pending is None
                 and ui.entry._frame is ui.popup._frame is None
                 and not ui.entry.terminal and not ui.popup.terminal
                 and ui.entry.native_refusal() is ui.popup.native_refusal() is None
                 and ui._refs is self._failure_refs,
                 'SOURCE_QUIT_FAILED_BACKEND_LIFETIME_CHANGED')
            refs = ui._refs
            need(type(refs) is tuple and len(refs) == 11 and refs[0] is self.broker,
                 'SOURCE_QUIT_FAILED_BACKEND_SELECTION_CHANGED')
            binding = self.consumer.current()
            generation = PersistentBroker.inventory_selection_current(self.broker, binding.writer)
            from tools.local_original_session.broker import _InventoryGeneration
            from tools.local_original_session.item_transfer_session import ItemTransferSession
            need(type(generation) is _InventoryGeneration and generation is refs[3]
                 and generation.phase == 'ACTIVE' and generation.writer is binding.writer is refs[1]
                 and generation.row is refs[2] and generation.selected is refs[4]
                 and type(generation.transfer_session) is ItemTransferSession
                 and generation.transfer_session is refs[9] and refs[9].broker is self.broker,
                 'SOURCE_QUIT_FAILED_BACKEND_SELECTION_CHANGED')
            adapter = self._exit_entry if self._failure_quantity == 1 else self._exit_popup
            need(adapter is (ui.entry if self._failure_quantity == 1 else ui.popup)
                 and adapter.source_quit_return(self) is self._failure_pending,
                 'SOURCE_QUIT_FAILED_BACKEND_RETURN_CHANGED')
            request = self._failure_pending[0]
            need(request['kind'] == (1 if ui.phase == 'DROP_BACKEND' else 2)
                 and request['quantity'] == self._failure_quantity
                 and (self._failure_quantity == 1 or request['action'] == 1),
                 'SOURCE_QUIT_FAILED_BACKEND_REQUEST_CHANGED')
        else:
            raise ValueError('SOURCE_QUIT_FAILURE_DOMAIN_CHANGED')
        need(adapter.manual is self.consumer
             and (self._failure_domain == 'BACKEND' or adapter.source_quit_refusal() is self._failure_pending)
             and self.consumer._busy is (False if self._failure_domain == 'BACKEND' else True)
             and self.consumer.reader.owner is self.owner
             and self.consumer._readonly_pending is None
             and threading.get_ident() == self.consumer._thread,
             'SOURCE_QUIT_FAILURE_OWNER_OR_THREAD_CHANGED')
        need(self.consumer.pending is None if self._pending is None else self.consumer.pending is self._pending,
             'SOURCE_QUIT_PENDING_CHANGED')
        if self._pending is None:
            need(self.consumer.sequence == self._failure_pending[0]['seq'], 'SOURCE_QUIT_FAILURE_SEQUENCE_CHANGED')
        return True

    def _prepare_failure_exit(self):
        features = self._features
        if features is not None and not _actual_export(features, 'ProductFeatures', _LAUNCHER):
            from tools.local_original_session.item_transfer_runner import Runtime
            need(type(features) is Runtime and features.manual is self.requests
                 and features.broker is self.broker, 'SOURCE_QUIT_ACTUAL_FAILED_FEATURE_REQUIRED')
            features = features.original
        self._features = features
        need(_actual_export(features, 'ProductFeatures', _LAUNCHER),
             'SOURCE_QUIT_ACTUAL_FAILED_FEATURE_REQUIRED')
        ui = features.item_transfer_ui
        if ui.phase in ('DROP_ENTRY_WAIT','GET_ENTRY_WAIT'):
            self._failure_domain = 'ENTRY'
            self._exit_entry = ui.entry
            adapter = self._exit_entry
        elif ui.phase in ('DROP_POPUP_WAIT','GET_POPUP_WAIT'):
            self._failure_domain = 'POPUP'
            self._exit_popup = ui.popup
            adapter = self._exit_popup
        elif ui.phase in ('DROP_BACKEND','RETURN_BACKEND'):
            self._failure_domain = 'BACKEND'
            need(type(ui._quantity) is int and ui._quantity > 0,
                 'SOURCE_QUIT_FAILED_BACKEND_QUANTITY_REQUIRED')
            self._failure_phase, self._failure_quantity, self._failure_refs = ui.phase, ui._quantity, ui._refs
            if ui._quantity == 1:
                self._exit_entry = ui.entry
            else:
                self._exit_popup = ui.popup
            adapter = self._exit_entry if ui._quantity == 1 else self._exit_popup
        else:
            raise ValueError('SOURCE_QUIT_FAILED_FEATURE_PHASE_REQUIRED')
        self._failure_pending = (adapter.source_quit_return(self) if self._failure_domain == 'BACKEND'
                                 else adapter.source_quit_refusal())
        self._failure_state, self._failure_data = self.consumer.state, copy.deepcopy(self.consumer.state)
        self._exit_only = True
        self._failure_current()
        need(self.consumer._source_quit_owner is None, 'SOURCE_QUIT_ALREADY_OWNED')
        self.consumer._source_quit_owner = self  # One-way EXIT ownership, no busy/state reset.

    def _enter_consumer(self):
        if self._exit_only:
            self.consumer._source_quit_terminal_current(self)
        else:
            self.consumer._enter()

    def _current(self):
        return self.consumer._current(source_quit=self) if self._exit_only else self.consumer._current()

    def _consumer_live(self):
        return self._failure_current() if self._exit_only else self.consumer.state['status'] != 'UNKNOWN'

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
             and self._consumer_live(), 'SOURCE_QUIT_TERMINAL')
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
        if self._exit_only:
            return self._failure_current() and self.consumer.pending is None
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
            if self.consumer.state['status'] == 'UNKNOWN':
                self._prepare_failure_exit()
            self._enter_consumer()
            entered = True
            self._started = True
            need(type(windows_requested) is int and windows_requested > 0, 'SOURCE_QUIT_OWNED_CLOSE_REQUIRED')
            self._wrapper(quiesced=False)
            need(self._native_settled(),
                 'SOURCE_QUIT_NATIVE_OUTCOME_UNRESOLVED')
            # Obtain real binding before invoking the launcher's quiesce policy.
            current = self._current()
            need(current[0].broker is self.broker and self.consumer.reader.owner is self.owner,
                 'SOURCE_QUIT_OWNER_CHANGED')
            quiesce = self.requests.quiesce_for_source_quit
            need(type(quiesce) is MethodType and quiesce.__self__ is self.requests
                 and quiesce.__func__ is type(self.requests).__dict__.get('quiesce_for_source_quit')
                 and quiesce.__func__.__globals__.get('ManualMoveRequests') is type(self.requests)
                 and Path(quiesce.__func__.__code__.co_filename).resolve() == _LAUNCHER,
                 'SOURCE_QUIT_REAL_QUIESCE_REQUIRED')
            need((quiesce(source_quit=self) if self._exit_only else quiesce()) is True,
                 'SOURCE_QUIT_QUIESCE_REFUSED')
            self._wrapper(quiesced=True)
            need(self._native_settled(),
                 'SOURCE_QUIT_NATIVE_OUTCOME_UNRESOLVED')
            now = self.consumer._clock()
            current = self._current()
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
            if entered and not self._exit_only:
                self.consumer._busy = False
            self._busy = False
        return self.report()

    def _observation_report(self):
        # Diagnostic evidence cannot authorize dispatch, drain, late Quit or exit.
        rows = [value[0] for value in self._observations.values()]
        return dict(status='UNKNOWN' if self._observation_errors else 'OBSERVED' if rows else 'NOT_OBSERVED',
                    errors=list(self._observation_errors.values()), received=bool(rows),
                    original_call_boundary_reached=any(row['call_boundary_reached'] for row in rows),
                    original_call_returned=any(row['call_returned'] for row in rows),
                    first_false=next((row['first_false'] for row in rows
                                      if row['first_false'] != 'NONE'), None),
                    scope='OBSERVED_ONLY_NOT_COMPLETION_OR_EXIT')

    def _observe(self):
        for phase, request in self._requests.items():
            for boundary in ('received', 'before_call', 'complete'):
                key = (phase, boundary)
                path = self._boundary / ('source-quit-observation-' + str(request['seq'])
                                         + '-' + boundary + '.json')
                try:
                    self._observe_one(phase, request, boundary, key, path)
                except Exception as error:
                    # A diagnostic sidecar cannot gate authoritative result,
                    # drain, late approval or exit processing. Keep first error.
                    self._observation_errors.setdefault(key, self.consumer._reason(error))

    def _observe_one(self, phase, request, boundary, key, path):
        old = self._observations.get(key)
        try:
            row = commands._closed_health_json(path)
        except FileNotFoundError:
            need(old is None, 'SOURCE_QUIT_OBSERVATION_DISAPPEARED')
            return
        expected = dict(request, schema='own-manual-source-quit-observation-v1', boundary=boundary)
        need(set(row) == set(expected) | {'step', 'first_false', 'call_boundary_reached',
                                         'call_returned', 'output_ok'}
             and all(type(row.get(k)) is type(v) and row[k] == v for k, v in expected.items())
             and type(row['step']) is str and 0 < len(row['step']) <= 64
             and type(row['first_false']) is str and 0 < len(row['first_false']) <= 64
             and all(type(row[k]) is bool for k in ('call_boundary_reached', 'call_returned', 'output_ok'))
             and (not row['call_returned'] or row['call_boundary_reached']),
             'SOURCE_QUIT_OBSERVATION_SCHEMA_OR_IDENTITY')
        stat = commands._ordinary(path).stat()
        identity = stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
        need(old is None or old == (row, identity), 'SOURCE_QUIT_OBSERVATION_CHANGED')
        self._observations[key] = dict(row), identity


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
        need(self._busy and self.consumer._busy is (False if self._exit_only
             and self._failure_domain == 'BACKEND' else True) and not self._closed
             and self._state['status'] != 'UNKNOWN' and self._consumer_live()
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
            sequence=self.consumer.sequence, normal_exit_verified=False, native_attempted=True,
            native_observation=self._observation_report())
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
            self._enter_consumer()
            entered = True
            self._observe()
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
            if entered and not self._exit_only:
                self.consumer._busy = False
            self._busy = False
        return self.report()

    def close(self):
        if type(self._completion) is _Completion:
            self._closed = True
            return self.report()
        if self._started:
            self._observe()
        self._closed = True
        if self._started and self._state['status'] != 'UNKNOWN':
            self._fail('SOURCE_QUIT_CLOSED')
        return self.report()
