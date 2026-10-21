"""Read-only design excerpt from our Python controller. Not a standalone program.
No binary/original-client source, private logs, identities, addresses or credentials.
Unshown helpers/owners are existing production validators, not True-return stubs.
User32 is created with ctypes.WinDLL("user32", use_last_error=True).
GetThreadDesktop argument DWORD, return HANDLE; pointer-width setup is existing.
"""
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import threading

class ReviewedPrivateDesktopExcerpt:
    def verify_non_input(self):
        need(not self.closed, 'PRIVATE_DESKTOP_CLOSED')
        current = self.u.OpenInputDesktop(0, False, 1)
        need(current, 'PRIVATE_INPUT_DESKTOP_UNKNOWN')
        try:
            need(self._name(current).casefold() != self.name.casefold(), 'PRIVATE_DESKTOP_IS_INPUT')
        finally:
            need(self.u.CloseDesktop(current), 'PRIVATE_INPUT_DESKTOP_CLOSE_FAILED')


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


    def post_client_click(self, owner, identity, hwnd, ui_thread, x, y):
        """Queue explicit client XY on the retained non-input desktop only.

        QUEUED proves PostMessage acceptance, never original Touch/ActorInput.
        A failure raises the original exception with client_click_result attached.
        No cursor/focus/capture manipulation: original WndProc owns those effects.
        """
        need(type(x) is int and type(y) is int and -32768 <= x <= 32767
             and -32768 <= y <= 32767, 'CLIENT_CLICK_SIGNED16_REQUIRED')
        need(type(hwnd) is int and hwnd > 0 and type(ui_thread) is int and ui_thread > 0,
             'CLIENT_CLICK_WINDOW_REQUIRED')
        identity = dict(identity)
        need(type(identity.get('pid')) is int and identity['pid'] > 0
             and type(identity.get('birth')) is int and identity['birth'] > 0
             and type(identity.get('candidate_sha256')) is str,
             'CLIENT_CLICK_IDENTITY_REQUIRED')
        child, process, job, native = owner.child, owner.owner_handle, owner.owner_job, owner.native
        queued, attempted, failures, cleanup_errors = [], [], [], []
        cleanup_up = [False]
        packed = (x & 0xffff) | ((y & 0xffff) << 16)
        self.u.GetClientRect.argtypes, self.u.GetClientRect.restype = (W.HWND, C.POINTER(W.RECT)), W.BOOL

        def current(*, geometry=True):
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
                self.verify_thread(ui_thread)
            except ValueError as error:
                try:
                    if str(error) == 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH':
                        error.desktop_thread_stage = 'TARGET_UI_THREAD'
                except BaseException:
                    pass
                raise
            if geometry:
                rect = W.RECT()
                need(self.u.GetClientRect(hwnd, C.byref(rect)) and rect.left <= x < rect.right
                     and rect.top <= y < rect.bottom, 'CLIENT_CLICK_OUTSIDE_CLIENT_RECT')
            # The OS/owner queries above must not leave a changed retained owner.
            need(owner.private_desktop is self and owner.child is child and owner.native is native
                 and not owner.closed and owner.owner_handle == process == child.process
                 and owner.owner_job == job == child.job and child.pid == identity['pid']
                 and int(child.identity['birth']) == identity['birth']
                 and owner.image_sha == identity['candidate_sha256']
                 and owner.validate(child) is True, 'CLIENT_CLICK_OWNER_LOST')

        def post(message, keys):
            current()
            attempted.append(message)
            need(self.u.PostMessageW(hwnd, message, keys, packed), 'CLIENT_CLICK_POST_FAILED')
            queued.append(message)
            current()

        def body():
            try:
                post(0x200, 0)
                post(0x201, 1)  # MK_LBUTTON; original button callback reads stored move position.
                post(0x202, 0)
            except BaseException as primary:
                failures.append(primary)
                # A failed PostMessage is not assumed to be an unattempted down.
                # Never release against a replaced/dead/foreign owner.
                if 0x201 in attempted and 0x202 not in queued:
                    try:
                        # Button-up consumes stored cursor position, not this lParam.
                        # Resize must not strand same-window down/capture.
                        current(geometry=False)
                        attempted.append(0x202)
                        need(self.u.PostMessageW(hwnd, 0x202, 0, packed),
                             'CLIENT_CLICK_CLEANUP_UP_FAILED')
                        cleanup_up[0] = True
                        queued.append(0x202)
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
        desktop_thread_check = None
        try:
            for failure in failures:
                probe = getattr(failure, 'desktop_thread_probe', None)
                stage = getattr(failure, 'desktop_thread_stage', None)
                if (type(probe) is dict and type(stage) is str
                        and stage in ('CLICK_HELPER_JOIN', 'TARGET_UI_THREAD')):
                    desktop_thread_check = dict(stage=stage, status=probe.get('status'),
                        reason=probe.get('reason'), matches_private=probe.get('matches_private'),
                        get_thread_desktop_last_error=probe.get('get_thread_desktop_last_error'))
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
