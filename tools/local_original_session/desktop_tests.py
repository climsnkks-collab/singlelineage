"""Fake-only private desktop/startup checks; no native desktop or process."""
import ctypes as C
import threading
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.local_original_session import desktop as d, launcher as l


class Fn:
    def __init__(self, callback): self.callback = callback
    def __call__(self, *args): return self.callback(*args)


class DesktopTests(unittest.TestCase):
    def fake_native(self, *, collision=False, restore=True):
        state = dict(names={11: 'Default', 12: 'Default'}, threads={}, closed=[], creates=[], enum=[], posts=[],
                     join_allowed=True, restore_allowed=restore, on_join=lambda: None)
        def name(handle, index, buffer, capacity, size):
            if handle not in state['names']: return False
            buffer.value = state['names'][handle]
            size._obj.value = (len(buffer.value) + 1) * C.sizeof(C.c_wchar)
            return True
        def opening(*args):
            C.set_last_error(0 if collision else 2)
            return 44 if collision else None
        def create(name, device, mode, flags, rights, security):
            state['creates'].append((name, device, mode, flags, rights, security, threading.get_ident()))
            state['names'][55] = name
            state['threads'][threading.get_ident()] = 55
            return 55
        def set_thread(handle):
            if not state['restore_allowed']: return False
            if handle == 55 and not state['join_allowed']: return False
            state['threads'][threading.get_ident()] = handle
            if handle == 55: state['on_join']()
            return True
        def enumeration(handle, callback, parameter):
            state['enum'].append(handle)
            return callback(500, parameter)
        user = SimpleNamespace(CreateDesktopW=Fn(create), OpenDesktopW=Fn(opening),
            OpenInputDesktop=Fn(lambda *args: 12), CloseDesktop=Fn(lambda handle: state['closed'].append(handle) or True),
            GetThreadDesktop=Fn(lambda tid: state['threads'].get(tid, 11)), SetThreadDesktop=Fn(set_thread),
            GetUserObjectInformationW=Fn(name), EnumDesktopWindows=Fn(enumeration))
        return SimpleNamespace(u=user, k=SimpleNamespace(GetCurrentThreadId=Fn(threading.get_ident))), state

    def command_owner(self, desktop, native, state):
        child = SimpleNamespace(pid=7, process=101, job=202, identity=dict(birth='303'))
        owner = SimpleNamespace(private_desktop=desktop, closed=False, child=child,
            owner_handle=101, owner_job=202, image_sha='a' * 64, validate=lambda child: True, native=native)
        native.owned_hwnd = lambda child, hwnd: hwnd == 500
        native.u.IsWindow = Fn(lambda hwnd: hwnd == 500)
        def window_thread(hwnd, pointer):
            pointer._obj.value = child.pid
            return 44
        def post(*args):
            state['posts'].append((threading.get_ident(), state['threads'].get(threading.get_ident(), 11), args))
            return True
        native.u.GetWindowThreadProcessId, native.u.PostMessageW = Fn(window_thread), Fn(post)
        return owner, dict(pid=7, birth=303, candidate_sha256='a' * 64)

    def test_command_posts_only_from_joined_private_thread_then_restores(self):
        native, state = self.fake_native()
        desktop = d.PrivateDesktop(native)
        self.addCleanup(desktop.close)
        owner, identity = self.command_owner(desktop, native, state)
        self.assertTrue(desktop.post_command(owner, identity, 500, 44, 0xc123, 1))
        posting_thread, posting_desktop, args = state['posts'][0]
        self.assertNotEqual(posting_thread, threading.get_ident())
        self.assertEqual(posting_desktop, 55)
        self.assertEqual(args, (500, 0xc123, 1, 0))
        self.assertEqual(state['threads'][posting_thread], 11)
        self.assertEqual(desktop._users, 0)

    def test_command_join_owner_ui_thread_and_closed_desktop_fail_without_post(self):
        for mode in ('join', 'owner', 'ui_thread', 'closed'):
            with self.subTest(mode=mode):
                native, state = self.fake_native()
                desktop = d.PrivateDesktop(native)
                owner, identity = self.command_owner(desktop, native, state)
                if mode == 'join': state['join_allowed'] = False
                if mode == 'owner': state['on_join'] = lambda: setattr(owner, 'closed', True)
                if mode == 'closed': desktop.close()
                with self.assertRaises(ValueError):
                    desktop.post_command(owner, identity, 500, 99 if mode == 'ui_thread' else 44, 0xc123, 1)
                self.assertFalse(state['posts'])
                self.assertEqual(desktop._users, 0)
                desktop.close()

    def test_close_waits_for_dispatch_thread_restore_before_closing_hdesk(self):
        native, state = self.fake_native()
        desktop = d.PrivateDesktop(native)
        owner, identity = self.command_owner(desktop, native, state)
        entered, release = threading.Event(), threading.Event()
        original_post = native.u.PostMessageW
        def post(*args):
            answer = original_post(*args)
            entered.set()
            if not release.wait(2): raise AssertionError('fixture release missing')
            return answer
        native.u.PostMessageW = Fn(post)
        errors = []
        def dispatch():
            try: desktop.post_command(owner, identity, 500, 44, 0xc123, 1)
            except BaseException as error: errors.append(error)
        sending = threading.Thread(target=dispatch)
        sending.start()
        self.assertTrue(entered.wait(1))
        closing = threading.Thread(target=desktop.close)
        closing.start()
        with desktop._condition:
            self.assertTrue(desktop._condition.wait_for(lambda: desktop._closing, timeout=1))
            self.assertNotIn(55, state['closed'])
        release.set()
        sending.join(2); closing.join(2)
        self.assertFalse(sending.is_alive() or closing.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(state['closed'].count(55), 1)
        self.assertTrue(all(value == 11 for value in state['threads'].values()))

    def test_dispatch_restore_failure_is_reported_after_single_post_without_replay(self):
        native, state = self.fake_native()
        desktop = d.PrivateDesktop(native)
        owner, identity = self.command_owner(desktop, native, state)
        original_post = native.u.PostMessageW
        def post(*args):
            answer = original_post(*args)
            state['restore_allowed'] = False
            return answer
        native.u.PostMessageW = Fn(post)
        with self.assertRaisesRegex(ValueError, 'PRIVATE_DESKTOP_THREAD_RESTORE_FAILED'):
            desktop.post_command(owner, identity, 500, 44, 0xc123, 1)
        self.assertEqual(len(state['posts']), 1)
        self.assertEqual(desktop._users, 0)
        desktop.close()

    def test_pre_user32_unknown_does_not_prevent_resume_but_known_mismatch_does(self):
        owner = l.NativeOwner.__new__(l.NativeOwner)
        rows, events = [dict(status='UNKNOWN', reason='THREAD_DESKTOP_UNAVAILABLE')], []
        owner.child = SimpleNamespace(tid=99, members={})
        owner.private_desktop = SimpleNamespace(probe_thread=lambda tid: rows[0])
        owner.key_guard = lambda: True
        owner.native = SimpleNamespace(resume=lambda child: events.append('resume'),
            job_events=lambda child: [], active_job_count=lambda child: 1)
        owner.resume()
        self.assertEqual(events, ['resume'])
        self.assertEqual(owner.desktop_status['status'], 'UNKNOWN')
        rows[0] = dict(status='OBSERVED', matches_private=True)
        self.assertTrue(owner.tick())
        self.assertTrue(owner.desktop_status['matches_private'])
        rows[0] = dict(status='OBSERVED', matches_private=False)
        with self.assertRaisesRegex(ValueError, 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH'): owner.resume()
        self.assertEqual(events, ['resume'])

    def test_fresh_non_input_desktop_on_helper_thread_restored_and_closed_once(self):
        native, state = self.fake_native()
        main_thread = threading.get_ident()
        desktop = d.PrivateDesktop(native)
        self.assertNotEqual(state['creates'][0][-1], main_thread)
        self.assertEqual(state['creates'][0][1:4], (None, None, 0))
        self.assertIsNone(state['creates'][0][5])  # Inherited security, no DACL expansion.
        self.assertFalse(state['creates'][0][4] & 0x100)  # No switch-desktop access.
        self.assertEqual(state['threads'][state['creates'][0][-1]], 11)
        self.assertTrue(desktop.contains(500))
        self.assertEqual(state['enum'], [55])
        self.assertFalse(desktop.contains(501))
        desktop.close(); desktop.close()
        self.assertEqual(state['closed'].count(55), 1)

    def test_collision_restore_failure_and_input_desktop_match_fail_closed(self):
        native, state = self.fake_native(collision=True)
        with self.assertRaisesRegex(ValueError, 'PRIVATE_DESKTOP_NAME_ALREADY_EXISTS'):
            d.PrivateDesktop(native)
        self.assertFalse(state['creates'])
        self.assertIn(44, state['closed'])
        native, state = self.fake_native(restore=False)
        with self.assertRaisesRegex(ValueError, 'PRIVATE_DESKTOP_THREAD_RESTORE_FAILED'):
            d.PrivateDesktop(native)
        self.assertIn(55, state['closed'])
        native, state = self.fake_native()
        desktop = d.PrivateDesktop(native)
        state['names'][12] = desktop.name
        with self.assertRaisesRegex(ValueError, 'PRIVATE_DESKTOP_IS_INPUT'): desktop.verify_non_input()
        desktop.close()

    def test_suspended_thread_desktop_is_verified_without_switch(self):
        native, state = self.fake_native()
        desktop = d.PrivateDesktop(native)
        self.addCleanup(desktop.close)
        state['threads'][99] = 55
        desktop.verify_thread(99)
        state['threads'][99] = 11
        with self.assertRaisesRegex(ValueError, 'PRIVATE_CREATED_THREAD_DESKTOP_MISMATCH'):
            desktop.verify_thread(99)
        state['threads'][99] = None
        self.assertEqual(desktop.probe_thread(99), dict(status='UNKNOWN', reason='THREAD_DESKTOP_UNAVAILABLE'))

    def test_frozen_creation_wrapper_only_changes_desktop_hide_and_always_restores_api(self):
        module = l.native_module(Path('C:/fixture/LC.guard.exe'))
        seen = []
        original = Fn(lambda *args: seen.append((args[4], args[5], args[8]._obj.flags,
                                                args[8]._obj.show, args[8]._obj.desktop)) or 77)
        native = SimpleNamespace(k=SimpleNamespace(CreateProcessW=original))
        desktop = SimpleNamespace(name='LC-Owned-Internal-' + 'a' * 32, verify_non_input=lambda: None)
        def parent():
            startup = module.STARTUP(); startup.cb = C.sizeof(startup)
            startup.flags, startup.show = 1, 1
            return native.k.CreateProcessW('fixture', None, None, None, False, 4, None,
                                          'fixture-cwd', C.byref(startup), None)
        self.assertEqual(d.hidden_desktop_launch(native, parent, module.STARTUP, desktop), 77)
        self.assertEqual(seen, [(False, 4, 1, 0, desktop.name)])
        self.assertIs(native.k.CreateProcessW, original)
        def fail(): raise OSError('fixture')
        with self.assertRaises(OSError): d.hidden_desktop_launch(native, fail, module.STARTUP, desktop)
        self.assertIs(native.k.CreateProcessW, original)
