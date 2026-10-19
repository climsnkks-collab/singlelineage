"""Explicit client mouse input for the runner's retained primary only.

Queued WindowProc messages prove POSTED only; resulting UI/movement is UNKNOWN.
No attach, engine call, packet sender or global button input. An explicit mouse
action may request foreground once and synchronize the physical cursor once to
the validated retained window's client point; neither operation is retried.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import stat

REQUEST_SCHEMA = 'local-original-input-request-v1'
RESULT_SCHEMA = 'local-original-input-result-v1'
MAX_SEQUENCE = (1 << 53) - 1


def need(value, reason):
    if not value:
        raise ValueError(reason)


def reason(error):
    text = error.args[0] if len(error.args) == 1 else None
    return text if isinstance(text, str) and text.startswith('INPUT_') else 'INPUT_OPERATION_FAILED'


class RECT(C.Structure):
    _fields_ = [('left', W.LONG), ('top', W.LONG), ('right', W.LONG), ('bottom', W.LONG)]


class POINT(C.Structure):
    _fields_ = [('x', W.LONG), ('y', W.LONG)]


class OwnedMouse:
    def __init__(self, owner, *, observation_scene):
        need(callable(observation_scene), 'INPUT_SCENE_CALLBACK_REQUIRED')
        self.owner, self.observation_scene = owner, observation_scene
        self.u = owner.native.u
        self.dpi_failed = False
        for name, args, result in (
            ('EnumWindows', (C.c_void_p, W.LPARAM), W.BOOL),
            ('IsWindow', (W.HWND,), W.BOOL),
            ('IsWindowVisible', (W.HWND,), W.BOOL),
            ('GetWindowThreadProcessId', (W.HWND, C.POINTER(W.DWORD)), W.DWORD),
            ('GetClassNameW', (W.HWND, W.LPWSTR, C.c_int), C.c_int),
            ('GetClientRect', (W.HWND, C.POINTER(RECT)), W.BOOL),
            ('ClientToScreen', (W.HWND, C.POINTER(POINT)), W.BOOL),
            ('GetPhysicalCursorPos', (C.POINTER(POINT),), W.BOOL),
            ('SetPhysicalCursorPos', (C.c_int, C.c_int), W.BOOL),
            ('GetForegroundWindow', (), W.HWND),
            ('SetForegroundWindow', (W.HWND,), W.BOOL),
            ('GetThreadDpiAwarenessContext', (), W.HANDLE),
            ('GetWindowDpiAwarenessContext', (W.HWND,), W.HANDLE),
            ('GetAwarenessFromDpiAwarenessContext', (W.HANDLE,), C.c_int),
            ('GetDpiForWindow', (W.HWND,), W.UINT),
            ('SetThreadDpiAwarenessContext', (W.HANDLE,), W.HANDLE),
            ('AreDpiAwarenessContextsEqual', (W.HANDLE, W.HANDLE), W.BOOL),
            ('PostMessageW', (W.HWND, W.UINT, W.WPARAM, W.LPARAM), W.BOOL),
        ):
            function = getattr(self.u, name)
            function.argtypes, function.restype = args, result

    def _owner_key(self):
        owner, child = self.owner, self.owner.child
        need(not owner.closed and child is not None and owner.owner_handle == child.process
             and owner.owner_job == child.job and child.process and child.job,
             'INPUT_RETAINED_PRIMARY_REQUIRED')
        need(owner.validate(child) is True, 'INPUT_OWNER_LOST')
        token = owner.native.token(child.process)
        need(token.get('elevated') is False and type(token.get('integrity_rid')) is int
             and token['integrity_rid'] == 8192, 'INPUT_MEDIUM_PRIMARY_REQUIRED')
        return (id(child), child.process, child.job, child.pid,
                child.identity['birth'], child.identity['image'])

    def _rect(self, hwnd, code):
        rect = RECT()
        need(self.u.GetClientRect(hwnd, C.byref(rect)), code)
        area = (rect.left, rect.top, rect.right, rect.bottom)
        need(area[0:2] == (0, 0) and 0 < area[2] <= 32768 and 0 < area[3] <= 32768,
             'INPUT_CLIENT_RECT_BOUND')
        return area

    def _dpi_rectangles(self, hwnd):
        # Only this runner thread changes context, synchronously and without
        # message pumping/await. The target process and OS settings are untouched.
        # API: learn.microsoft.com/windows/win32/api/winuser/
        # nf-winuser-setthreaddpiawarenesscontext (old context restores the thread).
        need(not self.dpi_failed, 'INPUT_DPI_CONTEXT_UNRECOVERED')
        source_context = self.u.GetThreadDpiAwarenessContext()
        target_context = self.u.GetWindowDpiAwarenessContext(hwnd)
        dpi = self.u.GetDpiForWindow(hwnd)
        need(source_context and target_context and 48 <= dpi <= 1536, 'INPUT_DPI_UNKNOWN')
        awareness = self.u.GetAwarenessFromDpiAwarenessContext(target_context)
        need(awareness in (0, 1, 2), 'INPUT_DPI_UNKNOWN')
        source_rect = self._rect(hwnd, 'INPUT_CLIENT_RECT_UNKNOWN')
        previous = self.u.SetThreadDpiAwarenessContext(target_context)
        need(previous, 'INPUT_DPI_CONTEXT_SWITCH_FAILED')
        try:
            need(self.u.AreDpiAwarenessContextsEqual(previous, source_context),
                 'INPUT_DPI_SOURCE_CONTEXT_CHANGED')
            need(self.u.AreDpiAwarenessContextsEqual(self.u.GetThreadDpiAwarenessContext(), target_context),
                 'INPUT_DPI_CONTEXT_SWITCH_FAILED')
            native_rect = self._rect(hwnd, 'INPUT_NATIVE_CLIENT_RECT_UNKNOWN')
        finally:
            replaced = self.u.SetThreadDpiAwarenessContext(previous)
            restored = (replaced and self.u.AreDpiAwarenessContextsEqual(replaced, target_context)
                        and self.u.AreDpiAwarenessContextsEqual(self.u.GetThreadDpiAwarenessContext(), source_context))
            self.dpi_failed = not restored
            need(restored, 'INPUT_DPI_CONTEXT_RESTORE_FAILED')
        need(self.u.AreDpiAwarenessContextsEqual(self.u.GetWindowDpiAwarenessContext(hwnd), target_context)
             and self.u.GetDpiForWindow(hwnd) == dpi
             and self._rect(hwnd, 'INPUT_CLIENT_RECT_UNKNOWN') == source_rect,
             'INPUT_DPI_OR_RECT_CHANGED')
        need(awareness != 0 or native_rect == source_rect, 'INPUT_UNAWARE_CLIENT_MISMATCH')
        return source_rect, native_rect, dpi, source_context, target_context

    def _snapshot(self, expected=None):
        key = self._owner_key()
        choices = []
        counts, errors = [0, 0], []
        def visit(hwnd, unused):
            try:
                counts[0] += 1
                need(counts[0] <= 4096, 'INPUT_WINDOW_INVENTORY_OVERFLOW')
                if not self.u.IsWindowVisible(hwnd):
                    return True
                pid = W.DWORD()
                thread = self.u.GetWindowThreadProcessId(hwnd, C.byref(pid))
                need(thread, 'INPUT_WINDOW_OWNER_UNKNOWN')
                if pid.value != key[3]:
                    return True
                counts[1] += 1
                need(counts[1] <= 64, 'INPUT_WINDOW_INVENTORY_OVERFLOW')
                need(self.u.IsWindow(hwnd), 'INPUT_WINDOW_LOST')
                name = C.create_unicode_buffer(128)
                length = self.u.GetClassNameW(hwnd, name, len(name))
                need(0 < length < len(name) - 1, 'INPUT_WINDOW_CLASS_UNKNOWN')
                if name.value == 'GLFW30':
                    choices.append((int(hwnd), thread))
                return True
            except Exception as error:
                errors.append(error)
                return False
        callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)(visit)
        complete = self.u.EnumWindows(callback, 0)
        if errors:
            raise errors[0]
        need(complete, 'INPUT_WINDOW_INVENTORY_INCOMPLETE')
        need(len(choices) == 1, 'INPUT_EXACT_SINGLE_WINDOW_REQUIRED')
        hwnd, thread = choices[0]
        need(self.u.IsWindow(hwnd) and self.u.IsWindowVisible(hwnd), 'INPUT_WINDOW_LOST')
        pid = W.DWORD()
        need(self.u.GetWindowThreadProcessId(hwnd, C.byref(pid)) == thread
             and pid.value == key[3], 'INPUT_WINDOW_OWNER_MISMATCH')
        name = C.create_unicode_buffer(128)
        need(self.u.GetClassNameW(hwnd, name, len(name)) == 6 and name.value == 'GLFW30',
             'INPUT_WINDOW_CLASS_CHANGED')
        snapshot = (key, hwnd, thread, *self._dpi_rectangles(hwnd))
        need(self._owner_key() == key, 'INPUT_OWNER_CHANGED')
        need(expected is None or (snapshot[:6] == expected[:6]
             and self.u.AreDpiAwarenessContextsEqual(snapshot[6], expected[6])
             and self.u.AreDpiAwarenessContextsEqual(snapshot[7], expected[7])), 'INPUT_WINDOW_CHANGED')
        return snapshot

    def _scene(self, expected):
        scene = self.observation_scene()
        need(type(scene) is dict and scene.get('status') == 'OBSERVED'
             and scene.get('current') == expected and scene.get('pending') == 'none'
             and scene.get('root_ready') is True, 'INPUT_SCENE_MISMATCH')

    def _screen_point(self, snapshot, x, y):
        """Convert in the target's DPI context, restoring only this own thread."""
        # learn.microsoft.com/windows/win32/api/winuser/nf-winuser-clienttoscreen
        source_context, target_context = snapshot[6:8]
        need(not self.dpi_failed, 'INPUT_DPI_CONTEXT_UNRECOVERED')
        need(self.u.AreDpiAwarenessContextsEqual(self.u.GetThreadDpiAwarenessContext(), source_context)
             and self.u.AreDpiAwarenessContextsEqual(self.u.GetWindowDpiAwarenessContext(snapshot[1]),
                                                    target_context), 'INPUT_DPI_OR_RECT_CHANGED')
        previous = self.u.SetThreadDpiAwarenessContext(target_context)
        need(previous, 'INPUT_DPI_CONTEXT_SWITCH_FAILED')
        try:
            need(self.u.AreDpiAwarenessContextsEqual(previous, source_context)
                 and self.u.AreDpiAwarenessContextsEqual(self.u.GetThreadDpiAwarenessContext(), target_context),
                 'INPUT_DPI_CONTEXT_SWITCH_FAILED')
            point = POINT(x, y)
            need(self.u.ClientToScreen(snapshot[1], C.byref(point)), 'INPUT_CLIENT_TO_SCREEN_FAILED')
            answer = (int(point.x), int(point.y))
        finally:
            replaced = self.u.SetThreadDpiAwarenessContext(previous)
            restored = (replaced and self.u.AreDpiAwarenessContextsEqual(replaced, target_context)
                        and self.u.AreDpiAwarenessContextsEqual(self.u.GetThreadDpiAwarenessContext(), source_context))
            self.dpi_failed = not restored
            need(restored, 'INPUT_DPI_CONTEXT_RESTORE_FAILED')
        return answer

    def _physical_cursor(self):
        # learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getphysicalcursorpos
        point = POINT()
        need(self.u.GetPhysicalCursorPos(C.byref(point)), 'INPUT_PHYSICAL_CURSOR_UNKNOWN')
        return (int(point.x), int(point.y))

    def left_click(self, x, y, expected_scene):
        return self._post_mouse(x, y, expected_scene, click=True)

    def mouse_move(self, x, y, expected_scene):
        """Synchronize the cursor and post WM_MOUSEMOVE once; no button input."""
        return self._post_mouse(x, y, expected_scene, click=False)

    def _post_mouse(self, x, y, expected_scene, *, click):
        """One explicit point. Caller supplies a fresh same-owner scene callback.

        Scene is required until DOWN. After DOWN, release uses only retained
        owner/window/rectangle checks so a scene transition cannot leave DOWN.
        A lost owner/window prevents release; never redirect it to another HWND.
        """
        queued, snapshot = [], None
        result = dict(status='REFUSED', ui_result='UNKNOWN', queued_messages=0,
                      release_posted=False, automatic_retry=False,
                      foreground_before=False, focus_attempted=False, focus_succeeded=False,
                      physical_cursor_before=None, target_screen_point=None,
                      cursor_sync_attempted=False, cursor_sync_succeeded=False)
        try:
            need(type(x) is int and type(y) is int and 0 <= x <= 32767 and 0 <= y <= 32767,
                 'INPUT_POINT_BOUND')
            need(type(expected_scene) is str
                 and expected_scene in ('Intro', 'Lobby', 'Login', 'CharacterSelect', 'Land'),
                 'INPUT_EXPECTED_SCENE_REQUIRED')
            snapshot = self._snapshot()
            need(x < snapshot[3][2] and y < snapshot[3][3], 'INPUT_POINT_OUTSIDE_CLIENT')
            source_width, source_height = snapshot[3][2:]
            native_width, native_height = snapshot[4][2:]
            native_x = (x * native_width + source_width // 2) // source_width
            native_y = (y * native_height + source_height // 2) // source_height
            need(0 <= native_x < native_width and 0 <= native_y < native_height
                 and native_x <= 32767 and native_y <= 32767, 'INPUT_NATIVE_POINT_BOUND')
            packed = (native_y << 16) | native_x
            result.update(hwnd=snapshot[1], ui_thread=snapshot[2], client_point=[x, y],
                          client_size=[source_width, source_height],
                          native_point=[native_x, native_y], native_client_size=[native_width, native_height],
                          window_dpi=snapshot[5], expected_scene=expected_scene)
            self._snapshot(snapshot)
            self._scene(expected_scene)
            result['foreground_before'] = self.u.GetForegroundWindow() == snapshot[1]
            if not result['foreground_before']:
                # Best effort metadata only. OS policy may refuse activation;
                # owned-window messages do not require foreground success.
                # Never bypass the policy or retry this foreground request.
                # learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setforegroundwindow
                # learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getforegroundwindow
                result['focus_attempted'] = True
                accepted = bool(self.u.SetForegroundWindow(snapshot[1]))
                result['focus_succeeded'] = accepted and self.u.GetForegroundWindow() == snapshot[1]
            else:
                result['focus_succeeded'] = True
            self._snapshot(snapshot)
            self._scene(expected_scene)
            target = self._screen_point(snapshot, native_x, native_y)
            result['target_screen_point'] = list(target)
            result['physical_cursor_before'] = list(self._physical_cursor())
            self._snapshot(snapshot)
            self._scene(expected_scene)
            need(self._screen_point(snapshot, native_x, native_y) == target, 'INPUT_SCREEN_POINT_CHANGED')
            # learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setphysicalcursorpos
            # No cursor restore: a queued original callback may poll it later.
            result['cursor_sync_attempted'] = True
            need(self.u.SetPhysicalCursorPos(*target), 'INPUT_PHYSICAL_CURSOR_SET_FAILED')
            need(self._physical_cursor() == target, 'INPUT_PHYSICAL_CURSOR_MISMATCH')
            result['cursor_sync_succeeded'] = True
            messages = ((0x200, 0), (0x201, 1), (0x202, 0)) if click else ((0x200, 0),)
            for message, flags in messages:
                self._snapshot(snapshot)
                if message != 0x202:
                    self._scene(expected_scene)
                    need(self._screen_point(snapshot, native_x, native_y) == target,
                         'INPUT_SCREEN_POINT_CHANGED')
                    need(self._physical_cursor() == target, 'INPUT_PHYSICAL_CURSOR_CHANGED')
                need(self.u.PostMessageW(snapshot[1], message, flags, packed), 'INPUT_POST_FAILED')
                queued.append(message)
                self._snapshot(snapshot)
            result['status'] = 'POSTED'
        except Exception as error:
            result['reason'] = reason(error)
            if 0x201 in queued and 0x202 not in queued:
                try:
                    self._snapshot(snapshot)
                    need(self.u.PostMessageW(snapshot[1], 0x202, 0, packed), 'INPUT_RELEASE_FAILED')
                    queued.append(0x202)
                    self._snapshot(snapshot)
                except Exception as release_error:
                    result['release_reason'] = reason(release_error)
            if queued:
                result['status'] = 'PARTIAL'
        result.update(queued_messages=len(queued), release_posted=0x202 in queued,
                      dpi_context_restored=not self.dpi_failed)
        return result


def _ordinary(path, *, directory=False, absent=False):
    """Reject reparse/symlink ancestors and multiple-linked request/result files."""
    path = Path(path).absolute()
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if part == path and absent:
                return path
            raise
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400, 'INPUT_REPARSE_REFUSED')
        if part != path or directory:
            need(stat.S_ISDIR(info.st_mode), 'INPUT_DIRECTORY_REQUIRED')
        else:
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'INPUT_REGULAR_SINGLE_FILE_REQUIRED')
    return path


def _read(path, limit):
    _ordinary(path)
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    if os.name == 'nt':
        # OPEN_REPARSE_POINT inspects the named file itself, including a link
        # introduced after lstat. Deny write/delete while consuming its bytes.
        import msvcrt
        kernel = C.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE)
        create.restype = W.HANDLE
        kernel.GetFileInformationByHandle.argtypes = (W.HANDLE, C.c_void_p)
        kernel.GetFileInformationByHandle.restype = W.BOOL
        kernel.CloseHandle.argtypes = (W.HANDLE,)
        kernel.CloseHandle.restype = W.BOOL
        handle = create(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
        if not (handle and handle != C.c_void_p(-1).value):
            winerror = C.get_last_error()  # First ctypes operation after failed CreateFileW.
            error = ValueError('INPUT_REQUEST_OPEN_FAILED')
            error.input_read_metadata = dict(stage='OPEN', winerror=winerror, same_file=False)
            raise error
        try:
            info = C.create_string_buffer(52)
            need(kernel.GetFileInformationByHandle(handle, info), 'INPUT_REQUEST_INFO_UNKNOWN')
            need(not int.from_bytes(info.raw[:4], 'little') & 0x400, 'INPUT_REPARSE_REFUSED')
            descriptor = msvcrt.open_osfhandle(handle, flags)
            handle = None  # descriptor now owns it
        finally:
            if handle:
                kernel.CloseHandle(handle)
    else:
        descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        need((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino)
             and not getattr(opened, 'st_file_attributes', 0) & 0x400,
             'INPUT_REQUEST_CHANGED')
        need(0 <= opened.st_size <= limit, 'INPUT_REQUEST_BYTE_BOUND')
        raw = os.read(descriptor, limit + 1)
        after = _ordinary(path).lstat()
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
            error = ValueError('INPUT_REQUEST_CHANGED')
            # Both ordinary checks and the opened identity/reparse check passed.
            # Identity changes remain unclassified; no permission/read is added.
            if (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino):
                error.input_read_metadata = dict(stage='FINAL_SIZE_OR_MTIME', winerror=None, same_file=True)
            raise error
        need(len(raw) == opened.st_size and len(raw) <= limit, 'INPUT_REQUEST_BYTE_BOUND')
        return raw
    finally:
        os.close(descriptor)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'INPUT_DUPLICATE_JSON_KEY')
        result[key] = value
    return result


class InputRequests:
    """One fixed request/result pair; monotonically increasing sequence, no retry.

    A durable refusal claims a sequence before input, so reloading the handler
    after partial posting cannot repeat the click. No request is a no-op.
    """
    def __init__(self, directory, mouse):
        self.directory = _ordinary(Path(directory).absolute(), directory=True)
        self.request = self.directory / 'input.request.json'
        self.result = self.directory / 'input.result.json'
        self.temporary = self.directory / 'input.result.tmp'
        self.mouse = mouse
        self.last_sequence, self.fingerprint, self.last_result = 0, None, None
        self.disabled = False
        try:
            prior = json.loads(_read(self.result, 2048), object_pairs_hook=_unique_object)
            need(type(prior) is dict and prior.get('schema') == RESULT_SCHEMA
                 and type(prior.get('last_sequence')) is int
                 and 0 <= prior['last_sequence'] <= MAX_SEQUENCE, 'INPUT_PRIOR_RESULT_INVALID')
            self.last_sequence = prior['last_sequence']
            self.fingerprint = prior.get('request_sha256')
            self.last_result = prior
        except FileNotFoundError:
            pass
        except Exception:
            self.disabled = True  # Unknown previous claim must never permit replay.

    def _write(self, row):
        _ordinary(self.directory, directory=True)
        _ordinary(self.result, absent=True)
        _ordinary(self.temporary, absent=True)
        raw = json.dumps(row, separators=(',', ':'), ensure_ascii=True).encode('ascii')
        need(len(raw) <= 2048, 'INPUT_RESULT_BYTE_BOUND')
        with self.temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _ordinary(self.result, absent=True)
        os.replace(self.temporary, self.result)

    def poll(self):
        if self.disabled:
            return dict(status='REFUSED', reason='INPUT_HANDLER_DISABLED', ui_result='UNKNOWN')
        sequence, fingerprint = None, None
        try:
            raw = _read(self.request, 1024)
            fingerprint = hashlib.sha256(raw).hexdigest()
            if fingerprint == self.fingerprint:
                return None
            self.fingerprint = fingerprint
            request = json.loads(raw, object_pairs_hook=_unique_object)
            need(type(request) is dict, 'INPUT_REQUEST_OBJECT_REQUIRED')
            candidate = request.get('sequence')
            if type(candidate) is int and 1 <= candidate <= MAX_SEQUENCE:
                sequence = candidate
            need(sequence is not None, 'INPUT_SEQUENCE_REQUIRED')
            need(sequence > self.last_sequence, 'INPUT_SEQUENCE_ALREADY_CONSUMED')
            self.last_sequence = sequence
            need(set(request) == {'schema', 'action', 'x', 'y', 'expected_scene', 'sequence'}
                 and request['schema'] == REQUEST_SCHEMA
                 and request['action'] in ('left_click', 'mouse_move'),
                 'INPUT_REQUEST_SCHEMA_REQUIRED')
            row = dict(schema=RESULT_SCHEMA, sequence=sequence, last_sequence=self.last_sequence,
                       request_sha256=fingerprint, status='REFUSED', reason='INPUT_CLAIMED_NO_RETRY',
                       ui_result='UNKNOWN', automatic_retry=False)
            self._write(row)
            action = self.mouse.left_click if request['action'] == 'left_click' else self.mouse.mouse_move
            outcome = action(request['x'], request['y'], request['expected_scene'])
            row.update(outcome)
            if outcome['status'] == 'POSTED':
                row.pop('reason', None)
        except FileNotFoundError:
            return None
        except Exception as error:
            row = dict(schema=RESULT_SCHEMA, sequence=sequence, last_sequence=self.last_sequence,
                       request_sha256=fingerprint, status='REFUSED', reason=reason(error),
                       ui_result='UNKNOWN', automatic_retry=False)
        if row == self.last_result:
            return None
        try:
            self._write(row)
        except Exception:
            self.disabled = True
            row['result_write_failed'] = True
        self.last_result = row
        return row
