"""Owned non-input desktop and frozen-launch wrapper; no desktop switch."""
import ctypes as C
from ctypes import wintypes as W
import threading
import time
import uuid
from dataclasses import dataclass

@dataclass(frozen=True)
class ClientClickResult:
    status: str
    queued: tuple
    attempted: tuple
    cleanup_up: bool
    cleanup_errors: tuple
    desktop_thread_check: dict | None = None

from contextlib import contextmanager

def need(value, code):
    if not value:
        raise ValueError(code)


def normalize_click_options(options):
    """Private click timing is opt-in wall-clock pacing, not frame proof."""
    defaults = dict(activate=False, move_settle_ms=0, down_hold_ms=0)
    need(options is None or (type(options) is dict and set(options) <= set(defaults)),
         'INPUT_CLICK_OPTIONS_REQUIRED')
    answer = dict(defaults, **(options or {}))
    need(type(answer['activate']) is bool and all(type(answer[key]) is int
         and 0 <= answer[key] <= 2000 for key in ('move_settle_ms', 'down_hold_ms')),
         'INPUT_CLICK_OPTIONS_REQUIRED')
    return answer


class PrivateDesktop:
    """Own one fresh non-input HDESK; never switch the user's desktop.

    CreateDesktop is confined to a new thread, whose original desktop is
    restored before it exits. No DACL, window-station or display-mode changes.
    """
    ACCESS = 0x0001 | 0x0002 | 0x0008 | 0x0040 | 0x0080

    def __init__(self, native):
        self.u, self.k = native.u, native.k
        self.handle, self.closed = None, False
        self._condition, self._users, self._lease_threads = threading.Condition(), 0, {}
        self._closing = False
        self.name = 'LC-Owned-Internal-' + uuid.uuid4().hex
        for name, args, result in (
            ('CreateDesktopW', (W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, W.DWORD, C.c_void_p), W.HANDLE),
            ('OpenDesktopW', (W.LPCWSTR, W.DWORD, W.BOOL, W.DWORD), W.HANDLE),
            ('OpenInputDesktop', (W.DWORD, W.BOOL, W.DWORD), W.HANDLE),
            ('CloseDesktop', (W.HANDLE,), W.BOOL),
            ('GetThreadDesktop', (W.DWORD,), W.HANDLE),
            ('SetThreadDesktop', (W.HANDLE,), W.BOOL),
            ('GetUserObjectInformationW', (W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)), W.BOOL),
            ('EnumDesktopWindows', (W.HANDLE, C.c_void_p, W.LPARAM), W.BOOL),
        ):
            function = getattr(self.u, name)
            function.argtypes, function.restype = args, result
        self.k.GetCurrentThreadId.argtypes, self.k.GetCurrentThreadId.restype = (), W.DWORD
        errors = []

        def create():
            original, original_name = None, None
            try:
                original = self.u.GetThreadDesktop(self.k.GetCurrentThreadId())
                original_name = self._name(original)
                self.verify_non_input()
                C.set_last_error(0)
                existing = self.u.OpenDesktopW(self.name, 0, False, self.ACCESS)
                if existing:
                    self.u.CloseDesktop(existing)
                    raise ValueError('PRIVATE_DESKTOP_NAME_ALREADY_EXISTS')
                need(C.get_last_error() == 2, 'PRIVATE_DESKTOP_ABSENCE_UNVERIFIED')
                C.set_last_error(0)
                self.handle = self.u.CreateDesktopW(self.name, None, None, 0, self.ACCESS, None)
                need(self.handle and C.get_last_error() != 183, 'PRIVATE_DESKTOP_CREATE_FAILED')
                need(self._name(self.handle).casefold() == self.name.casefold(), 'PRIVATE_DESKTOP_NAME_MISMATCH')
                self.verify_non_input()
            except BaseException as error:
                errors.append(error)
            finally:
                try:
                    if original_name is not None:
                        need(self.u.SetThreadDesktop(original)
                             and self._name(self.u.GetThreadDesktop(self.k.GetCurrentThreadId())) == original_name,
                             'PRIVATE_DESKTOP_THREAD_RESTORE_FAILED')
                except BaseException as error:
                    errors.append(error)

        # No runner UI thread is reassigned, and no SwitchDesktop API is used.
        thread = threading.Thread(target=create, name='local-session-desktop')
        thread.start(); thread.join()
        if errors:
            if self.handle:
                self.close()
            raise errors[0]

    def _name(self, handle):
        need(handle, 'PRIVATE_DESKTOP_HANDLE_REQUIRED')
        name, size = C.create_unicode_buffer(260), W.DWORD()
        need(self.u.GetUserObjectInformationW(handle, 2, name, C.sizeof(name), C.byref(size))
             and 0 < size.value <= C.sizeof(name) and bool(name.value), 'PRIVATE_DESKTOP_NAME_UNKNOWN')
        return name.value

    def verify_non_input(self):
        need(not self.closed, 'PRIVATE_DESKTOP_CLOSED')
        current = self.u.OpenInputDesktop(0, False, 1)
        need(current, 'PRIVATE_INPUT_DESKTOP_UNKNOWN')
        try:
            need(self._name(current).casefold() != self.name.casefold(), 'PRIVATE_DESKTOP_IS_INPUT')
        finally:
            need(self.u.CloseDesktop(current), 'PRIVATE_INPUT_DESKTOP_CLOSE_FAILED')

    def enum(self, callback, parameter):
        with self._lease() as handle:
            self.verify_non_input()
            return self.u.EnumDesktopWindows(handle, callback, parameter)

    def verify_thread(self, thread_id):
        winerror = []
        row = self.probe_thread(thread_id, winerror)
        try:
            need(row['status'] == 'OBSERVED' and row['matches_private'] is True,
                 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH')
        except ValueError as error:
            try:
                error.desktop_thread_probe = dict(status=row['status'],
                    reason=row.get('reason'), matches_private=row.get('matches_private'),
                    get_thread_desktop_last_error=winerror[0] if winerror else None)
            except BaseException:
                pass  # Diagnostic attributes never replace the original refusal.
            raise

    def verify_owned_window_thread(self, hwnd, thread_id, pid, native, child):
        """Prove the target via its window when foreign thread desktop read is denied.

        EnumDesktopWindows binds this exact HWND to our retained HDESK, while
        GetWindowThreadProcessId binds that HWND to the expected thread/process.
        A thread with a live window cannot move to another desktop. This path
        never applies to the fresh posting helper or to another Win32 error.
        """
        try:
            self.verify_thread(thread_id)
            return None
        except ValueError as original:
            try:
                probe = getattr(original, 'desktop_thread_probe', None)
                access_denied = (str(original) == 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH'
                    and type(probe) is dict and probe.get('status') == 'UNKNOWN'
                    and probe.get('reason') == 'THREAD_DESKTOP_UNAVAILABLE'
                    and probe.get('matches_private') is None
                    and probe.get('get_thread_desktop_last_error') == 5)
            except BaseException:
                access_denied = False
            if not access_denied:
                raise
            try:
                with self._lease() as handle:
                    self.verify_non_input()
                    need(self._name(handle).casefold() == self.name.casefold(),
                         'PRIVATE_TARGET_WINDOW_DESKTOP_NAME_CHANGED')
                    need(self.contains(hwnd) and self.u.IsWindow(hwnd),
                         'PRIVATE_TARGET_WINDOW_NOT_ON_OWNED_DESKTOP')
                    actual_pid = W.DWORD()
                    need(self.u.GetWindowThreadProcessId(hwnd, C.byref(actual_pid)) == thread_id
                         and actual_pid.value == pid and native.owned_hwnd(child, hwnd)
                         and self.handle == handle,
                         'PRIVATE_TARGET_WINDOW_OWNER_CHANGED')
            except Exception as proof_error:
                try:
                    bounded = ('PRIVATE_TARGET_WINDOW_DESKTOP_NAME_CHANGED',
                               'PRIVATE_TARGET_WINDOW_NOT_ON_OWNED_DESKTOP',
                               'PRIVATE_TARGET_WINDOW_OWNER_CHANGED',
                               'PRIVATE_DESKTOP_ENUM_INCOMPLETE',
                               'PRIVATE_DESKTOP_CLOSED',
                               'PRIVATE_DESKTOP_IS_INPUT',
                               'PRIVATE_INPUT_DESKTOP_UNKNOWN',
                               'PRIVATE_INPUT_DESKTOP_CLOSE_FAILED',
                               'PRIVATE_DESKTOP_NAME_UNKNOWN')
                    code = str(proof_error)
                    probe['owned_window_proof_failure'] = (code if type(proof_error) is ValueError
                        and code in bounded else type(proof_error).__name__)
                except BaseException:
                    pass
                try:
                    BaseException.add_note(original, 'owned window proof: '
                        + type(proof_error).__name__ + ': ' + str(proof_error))
                except BaseException:
                    pass
                raise original from None
            return dict(stage='TARGET_UI_THREAD', status='WINDOW_DERIVED',
                        reason='OWNED_WINDOW_ON_PRIVATE_DESKTOP', matches_private=True,
                        get_thread_desktop_last_error=5)

    def probe_thread(self, thread_id, winerror_out=None):
        with self._lease():
            self.verify_non_input()
            C.set_last_error(0)
            handle = self.u.GetThreadDesktop(thread_id)
            if not handle:
                # A suspended thread may not have initialized User32 yet.
                code = int(C.get_last_error())
                if type(winerror_out) is list and not winerror_out:
                    winerror_out.append(code)
                return dict(status='UNKNOWN', reason='THREAD_DESKTOP_UNAVAILABLE')
            return dict(status='OBSERVED', matches_private=self._name(handle).casefold() == self.name.casefold())

    def contains(self, hwnd):
        found, count = [], [0]
        def visit(current, unused):
            count[0] += 1
            if count[0] > 4096:
                return False
            if int(current) == hwnd:
                found.append(True)
            return True
        callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)(visit)
        need(self.enum(callback, 0) and count[0] <= 4096, 'PRIVATE_DESKTOP_ENUM_INCOMPLETE')
        return bool(found)

    @contextmanager
    def _lease(self):
        thread_id = threading.get_ident()
        with self._condition:
            need(not self.closed and not self._closing and self.handle, 'PRIVATE_DESKTOP_CLOSED')
            self._users += 1
            self._lease_threads[thread_id] = self._lease_threads.get(thread_id, 0) + 1
            handle = self.handle
        try:
            yield handle
        finally:
            with self._condition:
                self._users -= 1
                self._lease_threads[thread_id] -= 1
                if not self._lease_threads[thread_id]:
                    self._lease_threads.pop(thread_id)
                self._condition.notify_all()

    def post_command(self, owner, identity, hwnd, ui_thread, message, sequence):
        """Post only from a fresh thread joined to this retained non-input HDESK."""
        need(type(sequence) is int and 1 <= sequence <= 2147483647
             and type(message) is int and 0xc000 <= message <= 0xffff,
             'COMMAND_MESSAGE_BOUND')
        child, process, job = owner.child, owner.owner_handle, owner.owner_job
        identity = dict(identity)
        errors, posted = [], []

        def dispatch(handle):
            try:
                with self._lease():
                    with self._joined_thread(handle):
                        need(owner.private_desktop is self and not owner.closed and owner.child is child
                             and child is not None and process and job
                             and owner.owner_handle == process == child.process
                             and owner.owner_job == job == child.job
                             and child.pid == identity['pid']
                             and int(child.identity['birth']) == identity['birth']
                             and owner.image_sha == identity['candidate_sha256']
                             and owner.validate(child) is True, 'COMMAND_OWNER_CHANGED')
                        need(self.contains(hwnd) and self.u.IsWindow(hwnd), 'COMMAND_PRIVATE_DESKTOP_WINDOW_REQUIRED')
                        pid = W.DWORD()
                        need(self.u.GetWindowThreadProcessId(hwnd, C.byref(pid)) == ui_thread
                             and pid.value == identity['pid'] and owner.native.owned_hwnd(child, hwnd),
                             'COMMAND_WINDOW_OWNER_MISMATCH')
                        self.verify_non_input()
                        need(owner.validate(child) is True, 'COMMAND_OWNER_LOST')
                        need(self.u.PostMessageW(hwnd, message, sequence, 0), 'COMMAND_POST_FAILED')
                        posted.append(True)
            except BaseException as error:
                errors.append(error)

        # Keep the HDESK open until the helper is joined and restored/exited.
        # Never send cross-desktop messages from the runner's original thread.
        with self._lease() as handle:
            thread = threading.Thread(target=dispatch, args=(handle,), name='local-session-command')
            thread.start()
            thread.join()
        if errors:
            raise errors[0]
        return bool(posted)

    @contextmanager
    def _window_dpi_context(self, hwnd):
        """Change only this detached helper, restoring even on partial input."""
        for name, args, result in (
            ('GetWindowDpiAwarenessContext', (W.HWND,), C.c_void_p),
            ('GetThreadDpiAwarenessContext', (), C.c_void_p),
            ('SetThreadDpiAwarenessContext', (C.c_void_p,), C.c_void_p),
            ('AreDpiAwarenessContextsEqual', (C.c_void_p, C.c_void_p), W.BOOL),
        ):
            function = getattr(self.u, name)
            function.argtypes, function.restype = args, result
        context = self.u.GetWindowDpiAwarenessContext(hwnd)
        need(context, 'CLIENT_GEOMETRY_WINDOW_CONTEXT_UNKNOWN')
        previous = self.u.SetThreadDpiAwarenessContext(context)
        need(previous, 'CLIENT_GEOMETRY_CONTEXT_JOIN_FAILED')
        primary = None
        try:
            need(self.u.AreDpiAwarenessContextsEqual(context, self.u.GetThreadDpiAwarenessContext()),
                 'CLIENT_GEOMETRY_CONTEXT_MISMATCH')
            yield context
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                need(self.u.SetThreadDpiAwarenessContext(previous)
                     and self.u.AreDpiAwarenessContextsEqual(previous,
                         self.u.GetThreadDpiAwarenessContext()), 'CLIENT_GEOMETRY_CONTEXT_RESTORE_FAILED')
            except BaseException as cleanup:
                if primary is None:
                    raise
                try:
                    BaseException.add_note(primary, 'client geometry cleanup: ' + type(cleanup).__name__ + ': ' + str(cleanup))
                except BaseException:
                    pass


    def observe_client_geometry(self, owner, identity, hwnd, ui_thread):
        """Detached read in the retained HDESK, in the window's DPI context.

        No target thread/context is changed. Failed observation/restoration raises;
        callers must not treat it as coordinate authority or input acceptance.
        """
        import time
        identity = dict(identity)
        need(type(hwnd) is int and hwnd > 0 and type(ui_thread) is int and ui_thread > 0
             and type(identity.get('pid')) is int and identity['pid'] > 0
             and type(identity.get('birth')) is int and identity['birth'] > 0
             and type(identity.get('candidate_sha256')) is str,
             'CLIENT_GEOMETRY_IDENTITY_REQUIRED')
        for name, args, result in (
            ('IsWindow', (W.HWND,), W.BOOL),
            ('GetWindowThreadProcessId', (W.HWND, C.POINTER(W.DWORD)), W.DWORD),
            ('GetClientRect', (W.HWND, C.POINTER(W.RECT)), W.BOOL),
            ('GetDpiForWindow', (W.HWND,), W.UINT),
            ('GetWindowDpiAwarenessContext', (W.HWND,), C.c_void_p),
            ('GetThreadDpiAwarenessContext', (), C.c_void_p),
            ('SetThreadDpiAwarenessContext', (C.c_void_p,), C.c_void_p),
            ('GetAwarenessFromDpiAwarenessContext', (C.c_void_p,), C.c_int),
            ('AreDpiAwarenessContextsEqual', (C.c_void_p, C.c_void_p), W.BOOL),
        ):
            function = getattr(self.u, name)
            function.argtypes, function.restype = args, result
        child, process, job, native = owner.child, owner.owner_handle, owner.owner_job, owner.native
        errors, rows = [], []

        def current():
            need(owner.private_desktop is self and not owner.closed and owner.child is child
                 and child is not None and process and job and owner.native is native
                 and owner.owner_handle == process == child.process
                 and owner.owner_job == job == child.job and child.pid == identity['pid']
                 and int(child.identity['birth']) == identity['birth']
                 and owner.image_sha == identity['candidate_sha256'] and owner.validate(child) is True,
                 'CLIENT_GEOMETRY_OWNER_CHANGED')
            self.verify_non_input()
            need(self.contains(hwnd) and self.u.IsWindow(hwnd), 'CLIENT_GEOMETRY_PRIVATE_WINDOW_REQUIRED')
            pid = W.DWORD()
            need(self.u.GetWindowThreadProcessId(hwnd, C.byref(pid)) == ui_thread
                 and pid.value == identity['pid'] and native.owned_hwnd(child, hwnd),
                 'CLIENT_GEOMETRY_WINDOW_OWNER_MISMATCH')
            need(owner.private_desktop is self and not owner.closed and owner.child is child
                 and owner.native is native and owner.owner_handle == process == child.process
                 and owner.owner_job == job == child.job and child.pid == identity['pid']
                 and int(child.identity['birth']) == identity['birth']
                 and owner.image_sha == identity['candidate_sha256'] and owner.validate(child) is True,
                 'CLIENT_GEOMETRY_OWNER_LOST')

        def body():
            try:
                current()
                with self._window_dpi_context(hwnd) as context:
                    rect = W.RECT()
                    need(self.u.GetClientRect(hwnd, C.byref(rect)), 'CLIENT_GEOMETRY_RECT_UNKNOWN')
                    dpi = self.u.GetDpiForWindow(hwnd)
                    awareness = self.u.GetAwarenessFromDpiAwarenessContext(context)
                    need(dpi > 0 and awareness in (0, 1, 2) and rect.left == 0 and rect.top == 0
                         and rect.right > 0 and rect.bottom > 0, 'CLIENT_GEOMETRY_VALUES_UNKNOWN')
                    sampled = time.monotonic_ns()
                    current()
                    after = W.RECT()
                    need(self.u.GetClientRect(hwnd, C.byref(after)) and self.u.GetDpiForWindow(hwnd) == dpi
                         and (rect.left, rect.top, rect.right, rect.bottom) ==
                             (after.left, after.top, after.right, after.bottom), 'CLIENT_GEOMETRY_CHANGED')
                    need(self.u.AreDpiAwarenessContextsEqual(context,
                        self.u.GetWindowDpiAwarenessContext(hwnd)) and self.u.AreDpiAwarenessContextsEqual(
                        context, self.u.GetThreadDpiAwarenessContext()), 'CLIENT_GEOMETRY_CONTEXT_CHANGED')
                    rows.append(dict(status='OBSERVED', **identity, hwnd=hwnd, ui_thread=ui_thread,
                        client_rect=[rect.left, rect.top, rect.right, rect.bottom], window_dpi=int(dpi),
                        window_awareness=int(awareness), thread_awareness=int(awareness), awareness_equal=True,
                        sample_monotonic_ns=sampled, desktop_name=self.name))
            except BaseException as error:
                errors.append(error)

        def dispatch(handle):
            try:
                with self._lease():
                    with self._joined_thread(handle):
                        body()
            except BaseException as error:
                errors.append(error)

        with self._lease() as handle:
            thread = threading.Thread(target=dispatch, args=(handle,), name='local-session-client-geometry')
            thread.start()
            thread.join()
        if errors:
            primary = errors[0]
            for extra in errors[1:]:
                try:
                    BaseException.add_note(primary, 'client geometry cleanup: ' + type(extra).__name__ + ': ' + str(extra))
                except BaseException:
                    pass
            raise primary
        need(len(rows) == 1, 'CLIENT_GEOMETRY_UNKNOWN')
        return rows[0]


    def post_client_click(self, owner, identity, hwnd, ui_thread, x, y):
        return self.post_client_input(owner, identity, hwnd, ui_thread,
                                      'left_click', x=x, y=y)

    def post_client_input(self, owner, identity, hwnd, ui_thread, action,
                          *, x=None, y=None, points=None, delta=None, key=None,
                          check_scene=None, expected_geometry=None, click_options=None):
        """Queue explicit client XY on the retained non-input desktop only.

        QUEUED proves PostMessage acceptance, never original Touch/ActorInput.
        A failure raises the original exception with client_click_result attached.
        Optional activation only posts WM_ACTIVATE/WM_SETFOCUS to this HWND;
        no OS cursor/focus/capture API is invoked. Timing waits are wall-clock
        pacing only: no original render-frame consumption is established.
        """
        options = normalize_click_options(click_options)
        click = action in ('left_click', 'left_double_click')
        need(click or click_options is None, 'INPUT_CLICK_OPTIONS_ACTION_REQUIRED')
        def point(value):
            need(type(value) in (list, tuple) and len(value) == 2
                 and all(type(n) is int and -32768 <= n <= 32767 for n in value),
                 'CLIENT_CLICK_SIGNED16_REQUIRED')
            return tuple(value)

        # Each tuple is (message, wParam, client point or None, key lParam).
        # Original WindowProc receives normal input messages; no UI callback is
        # called here. Double click uses two ordinary button pairs; original
        # double-click recognition still requires runtime observation.
        if action in ('left_click', 'mouse_move', 'left_double_click', 'mouse_wheel'):
            xy = point((x, y))
        if action == 'left_drag':
            need(type(points) in (list, tuple) and len(points) >= 2,
                 'CLIENT_INPUT_DRAG_POINTS_REQUIRED')
            path = tuple(point(value) for value in points)
            events = [(0x200, 0, path[0], 0), (0x201, 1, path[0], 0)]
            events.extend((0x200, 1, xy, 0) for xy in path[1:])
            events.append((0x202, 0, path[-1], 0))
        elif action == 'mouse_move':
            events = [(0x200, 0, xy, 0)]
        elif action in ('left_click', 'left_double_click'):
            events = [(0x200, 0, xy, 0), (0x201, 1, xy, 0), (0x202, 0, xy, 0)]
            if action == 'left_double_click':
                events.extend(((0x201, 1, xy, 0), (0x202, 0, xy, 0)))
        elif action == 'mouse_wheel':
            need(type(delta) is int and -32768 <= delta <= 32767 and delta != 0,
                 'CLIENT_INPUT_WHEEL_DELTA_REQUIRED')
            events = [(0x200, 0, xy, 0), (0x20a, (delta & 0xffff) << 16, xy, 0)]
        elif action == 'key_press':
            need(type(key) is str and key in (*'0123456789', 'Enter'),
                 'CLIENT_INPUT_KEY_REQUIRED')
            vk = 13 if key == 'Enter' else ord(key)
            self.u.MapVirtualKeyW.argtypes, self.u.MapVirtualKeyW.restype = (W.UINT, W.UINT), W.UINT
            scan = int(self.u.MapVirtualKeyW(vk, 0))
            need(0 < scan <= 255, 'CLIENT_INPUT_KEY_SCAN_UNKNOWN')
            key_lparam = 1 | (scan << 16)
            # Original EF2CD0 loop calls TranslateMessage before DispatchMessageW
            # (WIN32_POLL_API_BINDINGS_V20): it generates WM_CHAR from KEYDOWN.
            # Posting a second WM_CHAR here would duplicate numeric input.
            events = [(0x100, vk, None, key_lparam),
                      (0x101, vk, None, key_lparam | 0xc0000000)]
        else:
            raise ValueError('CLIENT_INPUT_ACTION_REQUIRED')
        need(type(hwnd) is int and hwnd > 0 and type(ui_thread) is int and ui_thread > 0,
             'CLIENT_CLICK_WINDOW_REQUIRED')
        identity = dict(identity)
        need(type(identity.get('pid')) is int and identity['pid'] > 0
             and type(identity.get('birth')) is int and identity['birth'] > 0
             and type(identity.get('candidate_sha256')) is str,
             'CLIENT_CLICK_IDENTITY_REQUIRED')
        if expected_geometry is not None:
            self.u.GetDpiForWindow.argtypes, self.u.GetDpiForWindow.restype = (W.HWND,), W.UINT
        child, process, job, native = owner.child, owner.owner_handle, owner.owner_job, owner.native
        queued, attempted, failures, cleanup_errors = [], [], [], []
        cleanup_up = [False]
        target_window_proof = [None]
        pressed, last_packed = [None], [0]
        self.u.ClientToScreen.argtypes, self.u.ClientToScreen.restype = (W.HWND, C.POINTER(W.POINT)), W.BOOL
        self.u.GetClientRect.argtypes, self.u.GetClientRect.restype = (W.HWND, C.POINTER(W.RECT)), W.BOOL

        def current(*, xy=None, geometry=True):
            with self._condition:
                need(getattr(self, '_client_click_inflight', None) is claim,
                     'CLIENT_CLICK_CLAIM_LOST')
            need(owner.private_desktop is self and not owner.closed and owner.child is child
                 and child is not None and process and job and owner.native is native
                 and owner.owner_handle == process == child.process
                 and owner.owner_job == job == child.job and child.pid == identity['pid']
                 and int(child.identity['birth']) == identity['birth']
                 and owner.image_sha == identity['candidate_sha256']
                 and owner.validate(child) is True, 'CLIENT_CLICK_OWNER_CHANGED')
            self.verify_non_input()
            need(self.contains(hwnd) and self.u.IsWindow(hwnd), 'CLIENT_CLICK_PRIVATE_WINDOW_REQUIRED')
            pid = W.DWORD()
            need(self.u.GetWindowThreadProcessId(hwnd, C.byref(pid)) == ui_thread
                 and pid.value == identity['pid'] and native.owned_hwnd(child, hwnd),
                 'CLIENT_CLICK_WINDOW_OWNER_MISMATCH')
            try:
                proof = self.verify_owned_window_thread(hwnd, ui_thread, identity['pid'], native, child)
            except ValueError as error:
                try:
                    if str(error) == 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH':
                        error.desktop_thread_stage = 'TARGET_UI_THREAD'
                except BaseException:
                    pass
                raise
            if geometry and xy is not None:
                rect = W.RECT()
                need(self.u.GetClientRect(hwnd, C.byref(rect)) and rect.left <= xy[0] < rect.right
                     and rect.top <= xy[1] < rect.bottom, 'CLIENT_CLICK_OUTSIDE_CLIENT_RECT')
            if geometry and expected_geometry is not None:
                rect = W.RECT()
                need(self.u.GetClientRect(hwnd, C.byref(rect))
                     and [rect.left, rect.top, rect.right, rect.bottom] == expected_geometry['client_rect']
                     and self.u.GetDpiForWindow(hwnd) == expected_geometry['window_dpi'],
                     'CLIENT_INPUT_CAPTURE_GEOMETRY_CHANGED')
            # The OS/owner queries above must not leave a changed retained owner.
            need(owner.private_desktop is self and owner.child is child and owner.native is native
                 and not owner.closed and owner.owner_handle == process == child.process
                 and owner.owner_job == job == child.job and child.pid == identity['pid']
                 and int(child.identity['birth']) == identity['birth']
                 and owner.image_sha == identity['candidate_sha256']
                 and owner.validate(child) is True, 'CLIENT_CLICK_OWNER_LOST')
            if proof is not None:
                target_window_proof[0] = proof

        def post(message, keys, xy, key_lparam):
            release = message in (0x202, 0x101)
            current(xy=xy, geometry=not release)
            if not release and check_scene is not None:
                check_scene()
            packed = key_lparam
            if xy is not None:
                message_point = xy
                if message == 0x20a:
                    # WM_MOUSEWHEEL lParam is screen coordinates, even though
                    # requests use client coordinates like the other actions.
                    screen = W.POINT(*xy)
                    need(self.u.ClientToScreen(hwnd, C.byref(screen)),
                         'CLIENT_INPUT_CLIENT_TO_SCREEN_FAILED')
                    message_point = point((int(screen.x), int(screen.y)))
                packed = (message_point[0] & 0xffff) | ((message_point[1] & 0xffff) << 16)
                last_packed[0] = packed
            attempted.append(message)
            if message == 0x201:
                pressed[0] = (0x202, 0, packed)
            elif message == 0x100:
                pressed[0] = (0x101, keys, packed | 0xc0000000)
            need(self.u.PostMessageW(hwnd, message, keys, packed), 'CLIENT_CLICK_POST_FAILED')
            queued.append(message)
            if release:
                pressed[0] = None
            current(xy=xy, geometry=not release)

        def body():
            try:
                if click and options['activate']:
                    # Validate the point before any optional focus messages.
                    current(xy=xy)
                    # WM_ACTIVATE reaches DefWindowProc; WM_SETFOCUS reaches
                    # the original host focus callback. Neither proves focus.
                    post(0x6, 1, None, 0)
                    post(0x7, 0, None, 0)
                for event in events:
                    post(*event)
                    if click:
                        wait_ms = (options['move_settle_ms'] if event[0] == 0x200
                                   else options['down_hold_ms'] if event[0] == 0x201 else 0)
                        if wait_ms:
                            # Next post revalidates ownership/geometry/scene;
                            # UP intentionally ignores a successful scene change.
                            time.sleep(wait_ms / 1000)
            except BaseException as primary:
                failures.append(primary)
                # A failed PostMessage is not assumed to be an unattempted down.
                # Release stays on the retained window despite scene/size change.
                if pressed[0] is not None:
                    try:
                        current(geometry=False)
                        message, keys, packed = pressed[0]
                        if message == 0x202:
                            packed = last_packed[0]
                        attempted.append(message)
                        need(self.u.PostMessageW(hwnd, message, keys, packed),
                             'CLIENT_CLICK_CLEANUP_UP_FAILED')
                        cleanup_up[0] = True
                        queued.append(message)
                        pressed[0] = None
                        current(geometry=False)
                    except BaseException as cleanup:
                        cleanup_errors.append(cleanup)

        def dispatch(handle):
            helper_joined = False
            try:
                with self._lease():
                    # Catch the operation error inside the context so restore errors
                    # cannot replace it in the original _joined_thread finally.
                    with self._joined_thread(handle):
                        helper_joined = True
                        with self._window_dpi_context(hwnd):
                            body()
            except BaseException as error:
                if (str(error) == 'PRIVATE_DESKTOP_THREAD_RESTORE_FAILED'
                        and error.__context__ is not None):
                    prior = error.__context__
                    try:
                        if (not helper_joined and str(prior) == 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH'):
                            prior.desktop_thread_stage = 'CLICK_HELPER_JOIN'
                    except BaseException:
                        pass
                    failures.append(prior)
                try:
                    if (not helper_joined and str(error) == 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH'):
                        error.desktop_thread_stage = 'CLICK_HELPER_JOIN'
                except BaseException:
                    pass
                failures.append(error)

        claim = object()
        with self._condition:
            need(getattr(self, '_client_click_inflight', None) is None,
                 'CLIENT_CLICK_ALREADY_INFLIGHT')
            self._client_click_inflight = claim
        try:
            with self._lease() as handle:
                thread = threading.Thread(target=dispatch, args=(handle,), name='local-session-client-click')
                thread.start()
                thread.join()
        except BaseException as error:
            failures.append(error)
        finally:
            with self._condition:
                if getattr(self, '_client_click_inflight', None) is claim:
                    self._client_click_inflight = None
        desktop_thread_check = target_window_proof[0] if not failures else None
        try:
            for failure in failures:
                probe = getattr(failure, 'desktop_thread_probe', None)
                stage = getattr(failure, 'desktop_thread_stage', None)
                if (type(probe) is dict and type(stage) is str
                        and stage in ('CLICK_HELPER_JOIN', 'TARGET_UI_THREAD')):
                    desktop_thread_check = dict(stage=stage, status=probe.get('status'),
                        reason=probe.get('reason'), matches_private=probe.get('matches_private'),
                        get_thread_desktop_last_error=probe.get('get_thread_desktop_last_error'))
                    if 'owned_window_proof_failure' in probe:
                        desktop_thread_check['owned_window_proof_failure'] = probe['owned_window_proof_failure']
                    break
        except BaseException:
            desktop_thread_check = None  # Original click error and cleanup stay authoritative.
        result = ClientClickResult('UNKNOWN' if failures else 'QUEUED', tuple(queued),
                                   tuple(attempted), cleanup_up[0],
                                   tuple(type(e).__name__ + ':' + str(e) for e in cleanup_errors),
                                   desktop_thread_check)
        if failures:
            primary = failures[0]
            try:
                primary.client_click_result = result
            except BaseException:
                # Hostile/custom exception attribute hooks cannot replace primary.
                pass
            for extra in failures[1:] + cleanup_errors:
                try:
                    BaseException.add_note(primary, 'client click cleanup: ' + type(extra).__name__ + ': ' + str(extra))
                except BaseException:
                    pass
            raise primary
        return result

    @contextmanager
    def _joined_thread(self, handle):
        original = self.u.GetThreadDesktop(self.k.GetCurrentThreadId())
        original_name = self._name(original)
        try:
            need(self.u.SetThreadDesktop(handle), 'PRIVATE_COMMAND_THREAD_JOIN_FAILED')
            self.verify_thread(self.k.GetCurrentThreadId())
            yield
        finally:
            need(self.u.SetThreadDesktop(original)
                 and self._name(self.u.GetThreadDesktop(self.k.GetCurrentThreadId())) == original_name,
                 'PRIVATE_DESKTOP_THREAD_RESTORE_FAILED')

    def close(self):
        with self._condition:
            if self.closed:
                return
            need(not self._lease_threads.get(threading.get_ident()), 'PRIVATE_DESKTOP_CLOSE_DURING_USE')
            self._closing = True
            self._condition.notify_all()
            while self._users:
                self._condition.wait()
            if self.handle:
                need(self.u.CloseDesktop(self.handle), 'PRIVATE_DESKTOP_CLOSE_FAILED')
                self.handle = None
            self.closed = True


def hidden_desktop_launch(native, parent_create, startup_type, desktop):
    """Reuse frozen handle/Job creation, overriding only STARTUPINFO fields."""
    original = native.k.CreateProcessW
    def create(*args):
        need(len(args) == 10 and args[5] & 4 and not args[4], 'PRIVATE_SUSPENDED_LAUNCH_REQUIRED')
        desktop.verify_non_input()
        startup = C.cast(args[8], C.POINTER(startup_type)).contents
        need(startup.cb == C.sizeof(startup_type), 'PRIVATE_STARTUPINFO_REQUIRED')
        startup.flags |= 1  # STARTF_USESHOWWINDOW
        startup.show, startup.desktop = 0, desktop.name  # SW_HIDE; no interactive switch.
        return original(*args)
    native.k.CreateProcessW = create
    try:
        return parent_create()
    finally:
        native.k.CreateProcessW = original


