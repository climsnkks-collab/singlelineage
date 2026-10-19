"""Explicit InstallMarkOnCaller action. Original queue reservation, no Use/effect authority.
The historical _readonly_pending field is an opaque shared Native reservation.
No engine pointer/callback construction or cached UI pointers cross this call.
"""
from __future__ import annotations
import asyncio
import ctypes as C
import threading
import time
from types import MethodType

from tools.local_original_session import commands, inventory, manual_move_commands as m, observe

MESSAGE = 'LC-Owned-InstallMarkOnCaller-v1'
REQUEST = 'own-install-mark-on-caller-request-v1'
RESULT = 'own-install-mark-on-caller-result-v1'
COMMAND = 'InstallMarkOnCaller'
need = observe.need


def clock_pair():
    ticks, frequency = C.c_longlong(), C.c_longlong()
    kernel = C.WinDLL('kernel32', use_last_error=True)
    need(kernel.QueryPerformanceCounter(C.byref(ticks)) and kernel.QueryPerformanceFrequency(C.byref(frequency))
         and ticks.value > 0 and frequency.value > 0, 'MARK_ON_QPC_UNAVAILABLE')
    return ticks.value, frequency.value
_CURRENT, _WINDOW = m.ManualMoveCommands._current, m.ManualMoveCommands._window


def _empty(reason):
    return dict(status='UNKNOWN', reason=reason, invoked=None, installed=None, native_sequence=None,
                source_pid=None, source_birth=None, source_image_sha256=None,
                player_uid=None, item_identifier=None, map_id=None,
                query_started_monotonic_ns=None, cleanup_required=False)


class InstallMarkOnCaller:
    def __init__(self, manual):
        from tools.local_original_session.launcher import ManualMoveRequests
        need(type(manual) is ManualMoveRequests and type(manual.consumer) is m.ManualMoveCommands,
             'MARK_ON_INSTALL_ORIGINAL_MANUAL_REQUIRED')
        self.manual, self.consumer = manual, manual.consumer
        self._pending = None
        self._closed = self._terminal = False
        self._thread = threading.get_ident()
        self._life = None
        self._requested = False
        self._request_life = None
        self._claimed = False
        self._invoke_observed = None
        self.last_sample_monotonic_ns = None
        self.dispatch_qpc = self.dispatch_qpc_frequency = None
        self.last_result = _empty('NOT_SAMPLED')

    def request(self):
        """Queue one explicit action; no query/seq until the serial slot admits it."""
        if self._closed or self._terminal:
            return False
        if self._pending is not None or self._requested:
            return True  # Existing request only; never reset or promote cache.
        if self._claimed:
            return False
        try:
            _, self._request_life = self._current()
            self._requested = True
            self.last_result = _empty('MARK_ON_INSTALL_REQUESTED')
            self._life = self._request_life  # Tag null cache only, never a Native lease.
            return True
        except Exception as error:
            self._unknown(observe.reason(error))
            return False

    def _current(self):
        manual, consumer = self.manual, self.consumer
        need(not self._closed and not manual.closed and not manual._resources_closed
             and threading.get_ident() == self._thread and manual.consumer is consumer
             and manual._actual_manual_producer(asynchronous=True) is consumer,
             'MARK_ON_INSTALL_CURRENT_CONSUMER_REQUIRED')
        for name, original in (('_current', _CURRENT), ('_window', _WINDOW)):
            method = getattr(consumer, name)
            need(type(method) is MethodType and method.__self__ is consumer
                 and method.__func__ is original and getattr(type(consumer), name) is original,
                 'MARK_ON_INSTALL_ORIGINAL_METHOD_REQUIRED')
        current = _CURRENT(consumer)
        broker, writer = current[0].broker, current[0].writer
        need(broker is manual.inventory_broker, 'MARK_ON_INSTALL_SAME_BROKER_REQUIRED')
        generation = manual._inventory_reselection_current(writer)
        need(generation is not None and generation.phase == 'ACTIVE'
             and not generation.service._closed and generation.current_frame is broker._inventory_current_frame
             and type(generation.current_frame) is bytes and generation.delivery_authority is not None
             and generation.write_attempted is True and generation.attempted is True,
             'MARK_ON_INSTALL_DELIVERED_CURRENT_GENERATION_REQUIRED')
        info = inventory.validate_frame(generation.current_frame)
        need(current[6]['candidate_sha256'] == m.USE_ITEM_IMAGE_SHA,
             'MARK_ON_INSTALL_PROGRAM_IMAGE_REQUIRED')
        # Exact selected lifetime + canonical current row, not a new generation,
        # admission receipt or public Intent. Frame identity change invalidates it.
        life = (writer, generation, generation.selected, generation.service,
                generation.current_frame, current[1], info.identifier, current[3].uid, current[3].map_id)
        return current, life

    @staticmethod
    def _same(left, right):
        return (all(a is b for a, b in zip(left[:6], right[:6])) and left[6:] == right[6:])

    def _unknown(self, reason, *, terminal=False):
        self._terminal |= terminal
        if self._terminal:
            self._requested = False
        self.last_result = _empty(reason)
        self.last_result['invoked'] = self._invoke_observed
        self.last_result['cleanup_required'] = self._terminal
        return dict(self.last_result)

    def observation(self):
        if self._closed:
            return self._unknown('MARK_ON_INSTALL_CLOSED')
        try:
            _, life = self._current()
            if self._life is not None and not self._same(self._life, life):
                return self._unknown('MARK_ON_INSTALL_SELECTION_CHANGED')
        except Exception:
            return self._unknown('MARK_ON_INSTALL_NO_CURRENT_SELECTION')
        return dict(self.last_result)

    def collect(self):
        """File-only completion; exact Native reply, never a new action attempt."""
        pending = self._pending
        if pending is None:
            return self.observation()
        request, path, life, started = pending
        try:
            try:
                row = commands._json(path, 2048)
            except ValueError as error:
                metadata = getattr(error, 'input_read_metadata', None)
                waiting = False
                if (type(error) is ValueError and type(metadata) is dict
                        and set(metadata) == {'stage', 'winerror', 'same_file'}
                        and type(metadata['stage']) is str):
                    waiting = (error.args == ('INPUT_REQUEST_OPEN_FAILED',)
                        and metadata['stage'] == 'OPEN' and type(metadata['winerror']) is int
                        and metadata['winerror'] in (32, 33) and metadata['same_file'] is False
                        or error.args == ('INPUT_REQUEST_CHANGED',)
                        and metadata['stage'] == 'FINAL_SIZE_OR_MTIME'
                        and metadata['winerror'] is None and metadata['same_file'] is True)
                if not waiting:
                    raise
                need(time.monotonic_ns() - started < m.WAIT_NS, 'MARK_ON_INSTALL_REPLY_DEADLINE')
                return dict(self.last_result)
            expected = dict(request, schema=RESULT)
            need(set(row) == set(expected) | {'status', 'reason', 'invoked', 'installed'}
                 and all(type(row[k]) is type(v) and row[k] == v for k, v in expected.items()),
                 'MARK_ON_INSTALL_REPLY_IDENTITY_REQUIRED')
            need(type(row['status']) is str and row['status'] in ('RETURNED', 'REFUSED', 'UNKNOWN')
                 and type(row['reason']) is int and 0 <= row['reason'] <= 0xffffffff
                 and type(row['invoked']) is bool, 'MARK_ON_INSTALL_REPLY_TYPES_REQUIRED')
            need((row['status'] == 'RETURNED' and row['reason'] == 0 and row['invoked'] is True
                  and row['installed'] is True)
                 or (row['status'] != 'RETURNED' and row['installed'] is None),
                 'MARK_ON_INSTALL_REPLY_PRIMITIVES_REQUIRED')
            actual_invoked = row['invoked']
            self._invoke_observed = actual_invoked
            if row['status'] == 'UNKNOWN':
                self._terminal = True
                self.last_result = _empty('MARK_ON_INSTALL_NATIVE_UNKNOWN')
                self.last_result.update(reason=row['reason'], invoked=actual_invoked, cleanup_required=True)
                return dict(self.last_result)  # Native completion/cleanup ambiguous; reservation stays.
            current, actual = self._current()
            need(self._same(life, actual), 'MARK_ON_INSTALL_SELECTION_CHANGED')
            need(time.monotonic_ns() - started < m.WAIT_NS, 'MARK_ON_INSTALL_REPLY_DEADLINE')
            need(self.consumer._readonly_pending is self, 'MARK_ON_INSTALL_RESERVATION_CHANGED')
            self._pending = None
            self._requested = False
            self._request_life = None
            self.consumer._readonly_pending = None
            completed = time.monotonic_ns()
            self.last_sample_monotonic_ns = completed
            self.consumer.last_sample_ns = completed
            if self._closed or self._terminal:
                return self._unknown('MARK_ON_INSTALL_CLOSED_OR_TERMINAL', terminal=True)
            self._life = life
            self.last_result = dict(status=row['status'], reason=row['reason'], invoked=actual_invoked,
                installed=row['installed'],
                native_sequence=request['seq'], source_pid=request['pid'], source_birth=request['birth'],
                source_image_sha256=request['candidate_sha256'], player_uid=current[3].uid,
                item_identifier=life[6], map_id=current[3].map_id,
                query_started_monotonic_ns=started, cleanup_required=False)
            return dict(self.last_result)
        except FileNotFoundError:
            if time.monotonic_ns() - started >= m.WAIT_NS:
                return self._unknown('MARK_ON_INSTALL_REPLY_DEADLINE', terminal=True)
            return dict(self.last_result)
        except Exception as error:
            return self._unknown(observe.reason(error), terminal=self._pending is not None)

    async def sample(self):
        """Use one serial sample slot; pending action/busy always has priority."""
        consumer, manual = self.consumer, self.manual
        if (not self._requested or self._claimed or self._closed or self._terminal or self._pending is not None or manual.closed
                or manual.pending or manual._polling or manual._inventory_request is not None
                or manual._inventory_wait is not None or consumer.pending is not None
                or consumer._busy or consumer._readonly_pending is not None):
            return False
        now = time.monotonic_ns()
        previous = max((n for n in (self.last_sample_monotonic_ns,
            manual.last_sample_monotonic_ns) if n is not None), default=None)
        if previous is not None and now - previous < m.SAMPLE_NS:
            return False
        entered = False
        try:
            current, life = self._current()
            if self._request_life is not None and not self._same(self._request_life, life):
                self._requested = False
                self._unknown('MARK_ON_INSTALL_SELECTION_CHANGED')
                return False
            row, writer = current[1], current[0].writer
            async with row['operation_lock']:
                need(not self._closed and not consumer._busy and consumer.pending is None
                     and consumer._readonly_pending is None and not self._claimed,
                     'MARK_ON_INSTALL_PENDING_CHANGED')
                consumer._busy, entered = True, True
                broker = current[0].broker
                need(await broker._movement_owner(writer, row, current[3]) is True,
                     'MARK_ON_INSTALL_NATIVE_OWNER_REQUIRED')
                current, after = self._current()
                need(self._same(life, after), 'MARK_ON_INSTALL_SELECTION_CHANGED')
                hwnd = _WINDOW(consumer, current)
                need(consumer.sequence < m.MAX_SEQUENCE, 'MARK_ON_INSTALL_SEQUENCE_EXHAUSTED')
                self.dispatch_qpc, self.dispatch_qpc_frequency = clock_pair()
                self._claimed = True  # One explicit action; no rearm after publication ambiguity.
                consumer.sequence += 1  # Shared original consumer; public action cache untouched.
                seq, boundary, identity = consumer.sequence, current[5], current[6]
                request = dict(schema=REQUEST, **identity, seq=seq, command=COMMAND)
                path = boundary / ('install-mark-on-caller-result-' + str(seq) + '.json')
                commands._ordinary(path, absent=True)
                m._create_once(boundary / ('install-mark-on-caller-request-' + str(seq) + '.json'), request)
                user = consumer.reader.owner.native.u
                message = int(user.RegisterWindowMessageW(MESSAGE))
                need(0xc000 <= message <= 0xffff, 'MARK_ON_INSTALL_MESSAGE_REQUIRED')
                final, final_life = self._current()
                need(self._same(life, final_life) and _WINDOW(consumer, final) == hwnd,
                     'MARK_ON_INSTALL_PREPOST_CHANGED')
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError()
                self._pending = (request, path, life, now)
                consumer._readonly_pending = self
                self._life = life
                self.last_sample_monotonic_ns = now
                consumer.last_sample_ns = now
                self.last_result = _empty('MARK_ON_INSTALL_PENDING')
                owner = consumer.reader.owner
                desktop = getattr(owner, 'private_desktop', None)
                if desktop is not None:
                    need(desktop.post_command(owner, identity, hwnd, owner.child.tid, message, seq)
                         is True, 'MARK_ON_INSTALL_POST_UNKNOWN')
                else:
                    need(user.PostMessageW(hwnd, message, seq, 0), 'MARK_ON_INSTALL_POST_UNKNOWN')
                final, final_life = self._current()
                need(self._same(life, final_life) and _WINDOW(consumer, final) == hwnd,
                     'MARK_ON_INSTALL_POST_CHANGED')
            self.collect()
            return True
        except asyncio.CancelledError:
            self._unknown('MARK_ON_INSTALL_CANCELLED', terminal=True)
            raise
        except Exception as error:
            self._unknown(observe.reason(error), terminal=True)
            return self.last_sample_monotonic_ns == now
        finally:
            if entered:
                consumer._busy = False

    def close(self):
        self._closed = True
        self._requested = False
        self.last_result = _empty('MARK_ON_INSTALL_CLOSED')
        # Preserve unresolved queue ownership. No guessed cleanup or new action.
        if self._pending is not None:
            self.collect()
