"""Bounded file IPC to this runner's retained native UI command bridge.

No attach, remote memory write, engine pointer argument, cursor or focus API.
RETURNED describes the native callback's return, never game completion.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

from tools.local_original_session.input import _ordinary, _read, _unique_object

REQUEST_SCHEMA = 'local-original-command-request-v1'
RESULT_SCHEMA = 'local-original-command-result-v1'
MESSAGE = 'LC-Owned-Internal-Command-v1'
COMMANDS = {'LoginOK': 1, 'Select': 2, 'Quit': 3, 'MoveGoal': 4}
MAX_SEQUENCE = 2147483647
IMMUTABLE_RESULT_MODE = 'immutable-sequence-v1'
TOOL_RESULT_WAIT_NS = 10_000_000_000  # Tool supervision only; never a game rule.


class ResultPublicationFailure(ValueError):
    """The posted command's outcome is unknown; its sequence may not be replayed."""


class IntegrityFailure(ValueError):
    """A fixed health failure, never a native command result."""


def _closed_health_json(path):
    """The existing _read denies writes/deletes and verifies stable file identity."""
    try:
        return _json(path, 4096)
    except ValueError as error:
        if (error.args == ('INPUT_REQUEST_CHANGED',) or
                (error.args == ('INPUT_REQUEST_OPEN_FAILED',) and C.get_last_error() in (32, 33))):
            return None  # In-progress CREATE_NEW write or transition to its final size.
        raise


def lifecycle_health(owner, identity):
    boundary = _ordinary(owner.directory, directory=True)
    summaries = {}
    for phase in ('ready', 'late'):
        try:
            row = _closed_health_json(boundary / ('lifecycle-health-' + phase + '.json'))
        except FileNotFoundError:
            if phase == 'ready': return dict(status='WAIT', reason='COMMAND_INTEGRITY_HEALTH_ABSENT')
            continue
        except Exception:
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_MALFORMED') from None
        if row is None:
            return dict(status='WAIT', reason='COMMAND_INTEGRITY_HEALTH_WRITER_ACTIVE')
        if (row.get('schema') != 'own-lifecycle-integrity-v1' or row.get('phase') != phase
                or row.get('baseline_after_commit') is not True):
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_BASELINE_INVALID')
        if not all(type(row.get(key)) is type(value) and row[key] == value for key, value in identity.items()):
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_IDENTITY_MISMATCH')
        names = ('guard_physical', 'guard_signature_matched', 'guard_signature_mismatched',
                 'guard_signature_unknown', 'lifecycle_logical', 'lifecycle_physical',
                 'lifecycle_signature_matched', 'lifecycle_signature_mismatched', 'lifecycle_signature_unknown')
        if not all(type(row.get(key)) is int for key in names):
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_COUNT_TYPE')
        if not (row['guard_physical'] == row['guard_signature_matched'] == 17
                and row['guard_signature_mismatched'] == row['guard_signature_unknown'] == 0
                and row['lifecycle_logical'] == 8 and 4 <= row['lifecycle_physical'] <= 8
                and row['lifecycle_signature_matched'] == row['lifecycle_physical']
                and row['lifecycle_signature_mismatched'] == row['lifecycle_signature_unknown'] == 0):
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_COUNTS_FAILED')
        summaries[phase] = {key: row[key] for key in names}
    return dict(status='VERIFIED', baseline_after_commit=True, **summaries)


def need(value, code):
    if not value:
        raise ValueError(code)


def _code(error):
    value = error.args[0] if isinstance(error, ValueError) and len(error.args) == 1 else None
    return value if type(value) is str and re.fullmatch('COMMAND_[A-Z0-9_]{1,80}', value) else 'COMMAND_IO_REFUSED'


def _json(path, limit):
    row = json.loads(_read(path, limit), object_pairs_hook=_unique_object)
    need(type(row) is dict, 'COMMAND_OBJECT_REQUIRED')
    return row


def _atomic(path, row, limit, *, output_only=False):
    need(type(output_only) is bool, 'COMMAND_OUTPUT_ONLY_BOOL_REQUIRED')
    if output_only:
        return _atomic_observation(path, row, limit)
    _ordinary(path.parent, directory=True)
    _ordinary(path, absent=True)
    temporary = path.with_name(path.name + '.tmp')
    _ordinary(temporary, absent=True)
    raw = json.dumps(row, separators=(',', ':'), ensure_ascii=True).encode('ascii') + b'\n'
    need(len(raw) <= limit, 'COMMAND_BYTE_BOUND')
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _ordinary(path, absent=True)
    os.replace(temporary, path)


def _atomic_observation(path, row, limit):
    """One output save only; a sharing defer grants no command/game outcome."""
    _ordinary(path.parent, directory=True)
    _ordinary(path, absent=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    _ordinary(temporary, absent=True)
    raw = json.dumps(row, separators=(',', ':'), ensure_ascii=True).encode('ascii') + b'\n'
    need(len(raw) <= limit, 'COMMAND_BYTE_BOUND')
    owned = None
    try:
        stream = temporary.open('xb')
        try:
            info = os.fstat(stream.fileno())
            owned = info.st_dev, info.st_ino
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            try:
                stream.close()
            except BaseException:
                pass
            raise
        else:
            stream.close()
        _ordinary(path, absent=True)
        info = _ordinary(temporary).lstat()
        need((info.st_dev, info.st_ino) == owned, 'COMMAND_OUTPUT_TEMP_CHANGED')
        os.replace(temporary, path)
    except BaseException as error:
        cleanup_failed = False
        if owned is not None:
            try:
                info = temporary.lstat()
                if (info.st_dev, info.st_ino) != owned:
                    cleanup_failed = True  # Never unlink a replacement/foreign file.
                else:
                    temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                cleanup_failed = not (os.name == 'nt' and getattr(cleanup_error, 'winerror', None) in (32, 33))
            except BaseException:
                cleanup_failed = True
        # A still-shared own temp may remain, but its unique name cannot collide
        # with a later save. Other cleanup failures keep the original exception.
        if (not cleanup_failed and os.name == 'nt' and isinstance(error, OSError)
                and getattr(error, 'winerror', None) in (32, 33)):
            return False
        raise
    return True


class CommandRequests:
    """One pending native request, durable claim before posting, no replay."""
    def __init__(self, directory, owner):
        self.directory = _ordinary(Path(directory).absolute(), directory=True)
        self.owner = owner
        self.request = self.directory / 'command.request.json'
        self.result = self.directory / 'command.result.json'
        self.last_sequence, self.fingerprint, self.pending = 0, None, None
        self.disabled = False
        self.command_result_mode = getattr(owner, 'command_result_mode', None)
        need(self.command_result_mode in (None, IMMUTABLE_RESULT_MODE), 'COMMAND_RESULT_MODE_UNKNOWN')
        self.publication_failed = False
        self.u = owner.native.u
        for name, args, result in (
            ('RegisterWindowMessageW', (W.LPCWSTR,), W.UINT),
            ('IsWindow', (W.HWND,), W.BOOL),
            ('GetWindowThreadProcessId', (W.HWND, C.POINTER(W.DWORD)), W.DWORD),
            ('PostMessageW', (W.HWND, W.UINT, W.WPARAM, W.LPARAM), W.BOOL),
        ):
            function = getattr(self.u, name)
            function.argtypes, function.restype = args, result
        self.message = int(self.u.RegisterWindowMessageW(MESSAGE))
        need(0xc000 <= self.message <= 0xffff, 'COMMAND_MESSAGE_REGISTRATION_FAILED')
        try:
            prior = _json(self.result, 2048)
            need(prior.get('schema') == RESULT_SCHEMA
                 and type(prior.get('last_sequence')) is int
                 and 0 <= prior['last_sequence'] <= MAX_SEQUENCE, 'COMMAND_PRIOR_RESULT_INVALID')
            self.last_sequence = prior['last_sequence']
            self.fingerprint = prior.get('request_sha256')
            if prior.get('status') == 'QUEUED':
                self.pending = dict(prior)
            if self.command_result_mode == IMMUTABLE_RESULT_MODE and prior.get('status') == 'UNKNOWN':
                self.disabled = True
                self.publication_failed = True
        except FileNotFoundError:
            pass
        except Exception:
            self.disabled = True

    def _identity(self):
        owner, child = self.owner, self.owner.child
        need(not owner.closed and child is not None and owner.owner_handle == child.process
             and owner.owner_job == child.job and child.process and child.job,
             'COMMAND_RETAINED_PRIMARY_REQUIRED')
        need(owner.validate(child) is True, 'COMMAND_OWNER_LOST')
        need(type(owner.image_sha) is str and re.fullmatch('[0-9a-f]{64}', owner.image_sha),
             'COMMAND_IMAGE_REQUIRED')
        pid, birth = int(child.pid), int(child.identity['birth'])
        need(0 < pid <= 0xffffffff and 0 < birth <= 0xffffffffffffffff, 'COMMAND_IDENTITY_BOUND')
        return dict(pid=pid, birth=birth, candidate_sha256=owner.image_sha)

    def _ready(self, identity):
        boundary = _ordinary(self.owner.directory, directory=True)
        ready = _json(boundary / 'command-bridge.json', 1024)
        need(all(type(ready.get(key)) is type(value) and ready[key] == value
                 for key, value in identity.items()), 'COMMAND_BRIDGE_IDENTITY_MISMATCH')
        if self.command_result_mode == IMMUTABLE_RESULT_MODE:
            need(ready.get('command_result_mode') == IMMUTABLE_RESULT_MODE,
                 'COMMAND_RESULT_CAPABILITY_MISMATCH')
        need(ready.get('ready') is True and type(ready.get('message')) is int
             and ready['message'] == self.message, 'COMMAND_BRIDGE_NOT_READY')
        hwnd, thread = ready.get('window'), ready.get('thread_id')
        need(type(hwnd) is int and 0 < hwnd <= 0xffffffffffffffff
             and type(thread) is int and 0 < thread <= 0xffffffff, 'COMMAND_WINDOW_UNKNOWN')
        need(self.owner.private_desktop is not None and self.owner.private_desktop.contains(hwnd),
             'COMMAND_PRIVATE_DESKTOP_WINDOW_REQUIRED')
        need(self._identity() == identity, 'COMMAND_OWNER_CHANGED')
        return hwnd, thread

    def checked_health(self):
        if getattr(self.owner, 'require_lifecycle_health', False) is not True:
            return dict(status='NOT_REQUIRED')
        try:
            identity = self._identity()
            result = lifecycle_health(self.owner, identity)
            if self._identity() != identity:
                raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_OWNER_CHANGED')
            return result
        except IntegrityFailure:
            raise
        except Exception:
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_OWNER_UNKNOWN') from None

    def _record(self, row):
        try:
            _atomic(self.result, row, 2048)
        except Exception:
            self.disabled = True
            raise
        return row

    def _queued_age_ns(self):
        """The original durable tool claim bounds waiting, including reloads."""
        pending = self.pending
        if type(pending) is not dict:
            return None
        utc, mono = pending.get('tool_queued_utc_ns'), pending.get('tool_queued_monotonic_ns')
        now_utc, now_mono = time.time_ns(), time.monotonic_ns()
        if (pending.get('tool_session_id') != str(self.owner.directory.absolute())
                or type(utc) is not int or type(mono) is not int
                or not 0 < utc <= now_utc or not 0 < mono <= now_mono):
            return None
        # Wall-clock jumps cannot grant more time than the original monotonic
        # interval. A future/rolled-back clock is unknown, never a renewed claim.
        return max(now_utc - utc, now_mono - mono)

    def _publication_unknown(self, reason):
        self.disabled = True
        self.publication_failed = True
        row = dict(self.pending or {}, status='UNKNOWN', invoked=None,
                   invocation_uncertain=True, reason=reason,
                   native_ui_thread_conditional=False, ui_result='UNKNOWN', automatic_retry=False)
        try:
            self._record(row)
        except Exception:
            pass  # The earlier durable QUEUED claim still prevents replay.
        raise ResultPublicationFailure(reason)

    def check_result_wait(self):
        """Run before health admission too; WAIT cannot renew a posted claim."""
        if self.command_result_mode != IMMUTABLE_RESULT_MODE:
            return
        if self.publication_failed:
            raise ResultPublicationFailure('COMMAND_RESULT_PUBLICATION_UNKNOWN')
        if self.pending is not None:
            age = self._queued_age_ns()
            if age is None:
                self._publication_unknown('COMMAND_RESULT_ORIGINAL_CLAIM_UNKNOWN')
            if age >= TOOL_RESULT_WAIT_NS:
                self._publication_unknown('COMMAND_RESULT_TOOL_DEADLINE')

    def _collect_immutable(self):
        pending = self.pending
        age = self._queued_age_ns()
        if age is None:
            self._publication_unknown('COMMAND_RESULT_ORIGINAL_CLAIM_UNKNOWN')
        if age >= TOOL_RESULT_WAIT_NS:
            self._publication_unknown('COMMAND_RESULT_TOOL_DEADLINE')
        try:
            sequence, command = pending.get('sequence'), pending.get('native_command')
            need(type(sequence) is int and 1 <= sequence <= MAX_SEQUENCE
                 and type(command) is int and command in COMMANDS.values(), 'COMMAND_RESULT_SEQUENCE_UNKNOWN')
            identity = self._identity()
            # Single immutable basename derived only from the claimed integer.
            native = _json(self.owner.directory / ('command-result-' + str(sequence) + '.json'), 1024)
            need(native.get('schema') == 'own-internal-command-result-v1'
                 and all(type(native.get(key)) is type(value) and native[key] == value
                         for key, value in identity.items()), 'COMMAND_RESULT_IDENTITY_MISMATCH')
            need(type(native.get('seq')) is int and native['seq'] == sequence
                 and type(native.get('command')) is int and native['command'] == command,
                 'COMMAND_RESULT_SEQUENCE_MISMATCH')
            need(native.get('status') in ('RETURNED', 'REFUSED', 'UNSUPPORTED')
                 and type(native.get('reason')) is int and 0 <= native['reason'] <= 9
                 and type(native.get('invoked')) is bool, 'COMMAND_NATIVE_RESULT_INVALID')
            need(native['status'] != 'RETURNED' or (native['reason'] == 0 and native['invoked'] is True),
                 'COMMAND_NATIVE_RESULT_INVALID')
            need(self._identity() == identity, 'COMMAND_OWNER_CHANGED')
        except Exception:
            # Missing/open32/33, partial/invalid JSON, changed identity, and lost
            # owner are all UNKNOWN. None proves that the callback did not run.
            return None
        age = self._queued_age_ns()
        if age is None or age >= TOOL_RESULT_WAIT_NS:
            self._publication_unknown('COMMAND_RESULT_TOOL_DEADLINE')
        row = dict(pending, status=native['status'], native_reason=native['reason'],
                   invoked=native['invoked'], native_ui_thread_conditional=True)
        try:
            result = self._record(row)
        except Exception:
            self._publication_unknown('COMMAND_RESULT_LOCAL_RECORD_FAILED')
        self.pending = None
        return result


    def _collect(self):
        pending = self.pending
        if pending is None:
            return None
        if self.command_result_mode == IMMUTABLE_RESULT_MODE:
            return self._collect_immutable()
        identity = self._identity()
        try:
            native = _json(self.owner.directory / 'command-result.json', 1024)
        except FileNotFoundError:
            return None
        need(native.get('schema') == 'own-internal-command-result-v1'
             and all(type(native.get(key)) is type(value) and native[key] == value
                     for key, value in identity.items()), 'COMMAND_RESULT_IDENTITY_MISMATCH')
        need(type(native.get('seq')) is int and type(native.get('command')) is int,
             'COMMAND_RESULT_SEQUENCE_UNKNOWN')
        if native['seq'] < pending['sequence']:
            return None  # Previous completed result is not the current answer.
        need(native['seq'] == pending['sequence'] and native['command'] == pending['native_command'],
             'COMMAND_RESULT_SEQUENCE_MISMATCH')
        need(native.get('status') in ('RETURNED', 'REFUSED', 'UNSUPPORTED')
             and type(native.get('reason')) is int and 0 <= native['reason'] <= 9
             and type(native.get('invoked')) is bool, 'COMMAND_NATIVE_RESULT_INVALID')
        need(native['status'] != 'RETURNED' or (native['reason'] == 0 and native['invoked'] is True),
             'COMMAND_NATIVE_RESULT_INVALID')
        need(self._identity() == identity, 'COMMAND_OWNER_CHANGED')
        row = dict(pending, status=native['status'], native_reason=native['reason'],
                   invoked=native['invoked'], native_ui_thread_conditional=True)
        self.pending = None
        return self._record(row)

    def _submit(self, request, fingerprint):
        if self.checked_health()['status'] == 'WAIT':
            self.fingerprint = None  # No claim or post occurred; keep the explicit request pending.
            return None
        sequence = request.get('sequence')
        need(type(sequence) is int and 1 <= sequence <= MAX_SEQUENCE, 'COMMAND_SEQUENCE_REQUIRED')
        need(sequence > self.last_sequence, 'COMMAND_SEQUENCE_ALREADY_CONSUMED')
        self.last_sequence = sequence
        row = dict(schema=RESULT_SCHEMA, sequence=sequence, last_sequence=sequence,
                   request_sha256=fingerprint, status='REFUSED', reason='COMMAND_CLAIMED_NO_RETRY',
                   invoked=False, native_ui_thread_conditional=False,
                   ui_result='UNKNOWN', automatic_retry=False)
        self._record(row)  # Durable claim precedes every native side effect.
        need(set(request) == {'schema', 'sequence', 'command', 'uid', 'x', 'y'}
             and request['schema'] == REQUEST_SCHEMA and request['command'] in COMMANDS,
             'COMMAND_REQUEST_SCHEMA_REQUIRED')
        command, uid, x, y = COMMANDS[request['command']], request['uid'], request['x'], request['y']
        need(type(x) is int and type(y) is int and -(1 << 31) <= x < (1 << 31)
             and -(1 << 31) <= y < (1 << 31), 'COMMAND_COORDINATE_BOUND')
        need(type(uid) is int and 0 <= uid <= 0xffffffffffffffff, 'COMMAND_UID_REQUIRED')
        need((command == 4 and uid > 0) or (command != 4 and uid == 0 and x == 0 and y == 0),
             'COMMAND_UID_OR_UNUSED_ARGUMENT_REQUIRED')
        identity = self._identity()
        hwnd, thread = self._ready(identity)
        row.update(status='QUEUED', native_command=command, native_ui_thread=thread)
        row.pop('reason')
        if self.command_result_mode == IMMUTABLE_RESULT_MODE:
            row.update(tool_queued_utc_ns=time.time_ns(), tool_queued_monotonic_ns=time.monotonic_ns(),
                       tool_session_id=str(self.owner.directory.absolute()))
        self._record(row)  # A restart never re-posts a possibly queued command.
        self.pending = row
        native = dict(schema='own-internal-command-v1', **identity,
                      seq=sequence, command=command, uid=uid, x=x, y=y)
        _atomic(self.owner.directory / 'command-request.json', native, 512)
        need(self._identity() == identity and self._ready(identity) == (hwnd, thread), 'COMMAND_OWNER_CHANGED')
        if self.checked_health()['status'] == 'WAIT':
            raise IntegrityFailure('COMMAND_INTEGRITY_HEALTH_DISAPPEARED')
        need(self.owner.private_desktop.post_command(self.owner, identity, hwnd, thread, self.message, sequence)
             is True, 'COMMAND_POST_FAILED')
        return row

    def poll(self):
        if self.disabled:
            if self.command_result_mode == IMMUTABLE_RESULT_MODE and self.publication_failed:
                raise ResultPublicationFailure('COMMAND_RESULT_PUBLICATION_UNKNOWN')
            return None
        self.check_result_wait()
        try:
            if self.checked_health()['status'] == 'WAIT':
                return None
            answer = self._collect()
            if answer is not None or self.pending is not None:
                return answer
            try:
                raw = _read(self.request, 1024)
            except FileNotFoundError:
                return None
            fingerprint = hashlib.sha256(raw).hexdigest()
            if fingerprint == self.fingerprint:
                return None
            self.fingerprint = fingerprint
            request = json.loads(raw, object_pairs_hook=_unique_object)
            need(type(request) is dict, 'COMMAND_OBJECT_REQUIRED')
            return self._submit(request, fingerprint)
        except (IntegrityFailure, ResultPublicationFailure):
            raise
        except Exception as error:
            if self.command_result_mode == IMMUTABLE_RESULT_MODE and self.pending is not None:
                self._publication_unknown('COMMAND_RESULT_PENDING_EXCEPTION_UNKNOWN')
            self.pending = None
            row = dict(schema=RESULT_SCHEMA, sequence=self.last_sequence, last_sequence=self.last_sequence,
                       request_sha256=self.fingerprint, status='REFUSED', reason=_code(error),
                       invoked=False, native_ui_thread_conditional=False, ui_result='UNKNOWN', automatic_retry=False)
            return self._record(row)

    def request_quit(self):
        if self.disabled or self.pending is not None:
            return dict(status='REFUSED', reason='COMMAND_PENDING_OR_DISABLED', invoked=False)
        # close.request/Ctrl+C is an explicit request, not an automatic retry.
        request = dict(schema=REQUEST_SCHEMA, sequence=self.last_sequence + 1, command='Quit', uid=0, x=0, y=0)
        raw = json.dumps(request, separators=(',', ':')).encode('ascii')
        return self._submit(request, hashlib.sha256(raw).hexdigest())
