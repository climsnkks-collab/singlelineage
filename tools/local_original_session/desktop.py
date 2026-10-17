"""Owned non-input desktop and frozen-launch wrapper; no desktop switch."""
import ctypes as C
from ctypes import wintypes as W
import threading
import uuid
from contextlib import contextmanager

def need(value, code):
    if not value:
        raise ValueError(code)


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
        row = self.probe_thread(thread_id)
        need(row['status'] == 'OBSERVED' and row['matches_private'] is True,
             'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH')

    def probe_thread(self, thread_id):
        with self._lease():
            self.verify_non_input()
            handle = self.u.GetThreadDesktop(thread_id)
            if not handle:
                # A suspended thread may not have initialized User32 yet.
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


