"""Fake owned-window input tests; no game, UI, process, attach or network."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.local_original_session import input as i


class Fn:
    def __init__(self, callback):
        self.callback = callback
    def __call__(self, *args):
        return self.callback(*args)


class FakeOwner:
    def __init__(self):
        self.closed, self.alive = False, True
        self.owner_handle, self.owner_job = 100, 200
        self.child = SimpleNamespace(process=100, job=200, pid=11,
                                     identity=dict(birth='22', image='pinned LC.guard.exe'))
        self.hwnds, self.posts = [300], []
        self.hidden, self.enumeration_complete = set(), True
        self.class_name, self.pid, self.rect = 'GLFW30', 11, (0, 0, 960, 640)
        self.thread_context, self.window_context, self.window_dpi = 1, 1, 96
        self.target_awareness, self.native_rect = 0, None
        self.context_changes, self.fail_native_rect, self.fail_restore = [], False, False
        self.scene = dict(status='OBSERVED', current='Login', pending='none', root_ready=True)
        self.after_post = lambda message: None
        self.foreground, self.focus_allowed, self.focus_observed = 300, True, True
        self.focus_calls, self.after_focus = [], lambda: None
        self.cursor, self.screen_origin = (10, 20), (480, 0)
        self.cursor_calls, self.conversion_contexts = [], []
        self.cursor_set_allowed, self.cursor_read_allowed, self.conversion_allowed = True, True, True
        self.clipped_cursor = None
        self.after_cursor_sync, self.after_conversion = lambda: None, lambda: None
        self.token = dict(elevated=False, integrity_rid=8192)
        def window_pid(hwnd, pointer):
            C.cast(pointer, C.POINTER(W.DWORD)).contents.value = self.pid
            return 44
        def class_name(hwnd, buffer, capacity):
            buffer.value = self.class_name
            return len(self.class_name)
        def client_rect(hwnd, pointer):
            if self.fail_native_rect and self.thread_context == self.window_context:
                return False
            rectangle = C.cast(pointer, C.POINTER(i.RECT)).contents
            area = self.native_rect if (self.native_rect is not None
                   and self.thread_context == self.window_context) else self.rect
            rectangle.left, rectangle.top, rectangle.right, rectangle.bottom = area
            return True
        def set_context(context):
            previous = self.thread_context
            self.context_changes.append((previous, context))
            if self.fail_restore and previous == 2 and context == 1:
                return 0
            self.thread_context = context
            return previous
        def post(hwnd, message, flags, packed):
            self.posts.append((hwnd, message, flags, packed))
            self.after_post(message)
            return True
        def enumerate_windows(callback, unused):
            for hwnd in self.hwnds:
                if not callback(hwnd, 0):
                    return False
            return self.enumeration_complete
        def foreground(hwnd):
            self.focus_calls.append(hwnd)
            if self.focus_allowed and self.focus_observed:
                self.foreground = hwnd
            self.after_focus()
            return self.focus_allowed
        def screen_point(hwnd, pointer):
            self.conversion_contexts.append(self.thread_context)
            point = C.cast(pointer, C.POINTER(i.POINT)).contents
            point.x += self.screen_origin[0]
            point.y += self.screen_origin[1]
            self.after_conversion()
            return self.conversion_allowed
        def physical_cursor(pointer):
            point = C.cast(pointer, C.POINTER(i.POINT)).contents
            point.x, point.y = self.cursor
            return self.cursor_read_allowed
        def set_cursor(x, y):
            self.cursor_calls.append((x, y))
            if self.cursor_set_allowed:
                self.cursor = self.clipped_cursor if self.clipped_cursor is not None else (x, y)
            self.after_cursor_sync()
            return self.cursor_set_allowed
        user = SimpleNamespace(IsWindow=Fn(lambda hwnd: hwnd in self.hwnds),
                               EnumWindows=Fn(enumerate_windows),
                               IsWindowVisible=Fn(lambda hwnd: hwnd not in self.hidden),
                               GetWindowThreadProcessId=Fn(window_pid),
                               GetClassNameW=Fn(class_name), GetClientRect=Fn(client_rect),
                               ClientToScreen=Fn(screen_point), GetPhysicalCursorPos=Fn(physical_cursor),
                               SetPhysicalCursorPos=Fn(set_cursor),
                               GetForegroundWindow=Fn(lambda: self.foreground),
                               SetForegroundWindow=Fn(foreground),
                               GetThreadDpiAwarenessContext=Fn(lambda: self.thread_context),
                               GetWindowDpiAwarenessContext=Fn(lambda hwnd: self.window_context),
                               GetAwarenessFromDpiAwarenessContext=Fn(lambda context: self.target_awareness),
                               GetDpiForWindow=Fn(lambda hwnd: self.window_dpi),
                               SetThreadDpiAwarenessContext=Fn(set_context),
                               AreDpiAwarenessContextsEqual=Fn(lambda a, b: a == b),
                               PostMessageW=Fn(post))
        self.native = SimpleNamespace(u=user, token=lambda process: self.token,
                                      windows=lambda child: [dict(hwnd=h) for h in self.hwnds])
    def validate(self, child):
        return self.alive and child is self.child
    def mouse(self):
        return i.OwnedMouse(self, observation_scene=lambda: self.scene)


class MouseTests(unittest.TestCase):
    def test_explicit_move_syncs_physical_point_once_in_target_dpi_context_without_restore(self):
        owner = self.dpi_owner()
        result = owner.mouse().mouse_move(1005, 699, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual(result['physical_cursor_before'], [10, 20])
        self.assertEqual(result['target_screen_point'], [2239, 1224])
        self.assertTrue(result['cursor_sync_attempted'])
        self.assertTrue(result['cursor_sync_succeeded'])
        self.assertEqual(owner.cursor_calls, [(2239, 1224)])
        self.assertEqual(owner.cursor, (2239, 1224))
        self.assertEqual(set(owner.conversion_contexts), {owner.window_context})
        self.assertEqual(owner.thread_context, 1)
        self.assertEqual([row[1] for row in owner.posts], [0x200])
    def test_cursor_conversion_read_set_clip_and_owner_loss_refuse_without_messages_or_retry(self):
        rows = ((lambda o: setattr(o, 'conversion_allowed', False), 'INPUT_CLIENT_TO_SCREEN_FAILED', 0),
                (lambda o: setattr(o, 'cursor_read_allowed', False), 'INPUT_PHYSICAL_CURSOR_UNKNOWN', 0),
                (lambda o: setattr(o, 'cursor_set_allowed', False), 'INPUT_PHYSICAL_CURSOR_SET_FAILED', 1),
                (lambda o: setattr(o, 'clipped_cursor', (1, 2)), 'INPUT_PHYSICAL_CURSOR_MISMATCH', 1),
                (lambda o: setattr(o, 'after_cursor_sync', lambda: setattr(o, 'alive', False)),
                 'INPUT_OWNER_LOST', 1),
                (lambda o: setattr(o, 'after_cursor_sync', lambda: o.scene.update(current='Land')),
                 'INPUT_SCENE_MISMATCH', 1))
        for changes, expected, calls in rows:
            with self.subTest(reason=expected):
                owner = FakeOwner(); changes(owner)
                result = owner.mouse().left_click(42, 57, 'Login')
                self.assertEqual(result['status'], 'REFUSED')
                self.assertEqual(result['reason'], expected)
                self.assertFalse(owner.posts)
                self.assertEqual(len(owner.cursor_calls), calls)
                self.assertEqual(owner.thread_context, 1)
    def test_cursor_or_screen_target_change_after_move_prevents_down_without_reposition(self):
        for field, value, expected in (('cursor', (1, 2), 'INPUT_PHYSICAL_CURSOR_CHANGED'),
                                       ('screen_origin', (700, 0), 'INPUT_SCREEN_POINT_CHANGED')):
            with self.subTest(field=field):
                owner = FakeOwner()
                owner.after_post = lambda message: setattr(owner, field, value)
                result = owner.mouse().left_click(42, 57, 'Login')
                self.assertEqual(result['status'], 'PARTIAL')
                self.assertEqual(result['reason'], expected)
                self.assertEqual([row[1] for row in owner.posts], [0x200])
                self.assertEqual(len(owner.cursor_calls), 1)
    def test_cursor_change_after_down_releases_same_window_without_cursor_restore(self):
        owner = FakeOwner()
        def change(message):
            if message == 0x201: owner.cursor = (7, 8)
        owner.after_post = change
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertTrue(result['release_posted'])
        self.assertEqual([row[1] for row in owner.posts], [0x200, 0x201, 0x202])
        self.assertEqual(len(owner.cursor_calls), 1)
        self.assertEqual(owner.cursor, (7, 8))
    def test_screen_conversion_restore_failure_poison_prevents_cursor_sync(self):
        owner = self.dpi_owner()
        owner.after_conversion = lambda: setattr(owner, 'fail_restore', True)
        mouse = owner.mouse()
        result = mouse.mouse_move(1005, 699, 'Login')
        self.assertEqual(result['reason'], 'INPUT_DPI_CONTEXT_RESTORE_FAILED')
        self.assertFalse(result['dpi_context_restored'])
        self.assertEqual(mouse.mouse_move(1005, 699, 'Login')['reason'], 'INPUT_DPI_CONTEXT_UNRECOVERED')
        self.assertFalse(owner.cursor_calls)
        self.assertFalse(owner.posts)
    def test_signed_screen_point_on_negative_monitor_is_not_wrapped_or_clamped(self):
        owner = FakeOwner(); owner.screen_origin = (-480, -300)
        result = owner.mouse().mouse_move(42, 57, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual(result['target_screen_point'], [-438, -243])
        self.assertEqual(owner.cursor_calls, [(-438, -243)])
    def test_already_foreground_never_requests_activation(self):
        owner = FakeOwner()
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertTrue(result['foreground_before'])
        self.assertFalse(result['focus_attempted'])
        self.assertTrue(result['focus_succeeded'])
        self.assertFalse(owner.focus_calls)
    def test_explicit_click_activates_only_owned_window_and_preserves_dpi_mapping(self):
        owner = self.dpi_owner(); owner.foreground = 999
        result = owner.mouse().left_click(1005, 699, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertFalse(result['foreground_before'])
        self.assertTrue(result['focus_attempted'])
        self.assertTrue(result['focus_succeeded'])
        self.assertEqual(owner.focus_calls, [300])
        self.assertEqual(result['native_point'], [1759, 1224])
        self.assertTrue(result['dpi_context_restored'])
        self.assertEqual(owner.thread_context, 1)
    def test_os_refusal_or_foreground_mismatch_still_posts_only_owned_click(self):
        for allowed, observed in ((False, False), (True, False)):
            with self.subTest(allowed=allowed, observed=observed):
                owner = FakeOwner(); owner.foreground = 999
                owner.focus_allowed, owner.focus_observed = allowed, observed
                result = owner.mouse().left_click(42, 57, 'Login')
                self.assertEqual(result['status'], 'POSTED')
                self.assertTrue(result['focus_attempted'])
                self.assertFalse(result['focus_succeeded'])
                self.assertEqual(owner.focus_calls, [300])
                self.assertEqual(owner.foreground, 999)
                self.assertEqual([row[0] for row in owner.posts], [300, 300, 300])
                self.assertEqual([row[1] for row in owner.posts], [0x200, 0x201, 0x202])
    def test_activation_rechecks_owner_scene_and_geometry_before_messages(self):
        for changes, reason in ((lambda o: setattr(o, 'alive', False), 'INPUT_OWNER_LOST'),
                                (lambda o: o.scene.update(current='Land'), 'INPUT_SCENE_MISMATCH'),
                                (lambda o: setattr(o, 'rect', (0, 0, 800, 600)), 'INPUT_WINDOW_CHANGED'),
                                (lambda o: setattr(o, 'window_dpi', 120), 'INPUT_WINDOW_CHANGED')):
            with self.subTest(reason=reason):
                owner = FakeOwner(); owner.foreground = 999
                owner.after_focus = lambda: changes(owner)
                result = owner.mouse().left_click(42, 57, 'Login')
                self.assertEqual(result['reason'], reason)
                self.assertFalse(owner.posts)
                self.assertEqual(owner.focus_calls, [300])
    def test_unverified_scene_never_requests_foreground(self):
        owner = FakeOwner(); owner.foreground = 999
        result = owner.mouse().left_click(42, 57, 'Land')
        self.assertEqual(result['reason'], 'INPUT_SCENE_MISMATCH')
        self.assertFalse(owner.focus_calls)
        self.assertFalse(owner.posts)
    def test_focus_loss_after_move_does_not_add_foreground_gate_or_reactivation(self):
        owner = FakeOwner()
        owner.after_post = lambda message: setattr(owner, 'foreground', 999)
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual([row[1] for row in owner.posts], [0x200, 0x201, 0x202])
        self.assertFalse(owner.focus_calls)
    def test_focus_loss_after_down_still_releases_only_same_owned_window(self):
        owner = FakeOwner()
        def lose_focus(message):
            if message == 0x201: owner.foreground = 999
        owner.after_post = lose_focus
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual([row[1] for row in owner.posts], [0x200, 0x201, 0x202])
        self.assertFalse(owner.focus_calls)
    def dpi_owner(self):
        owner = FakeOwner()
        owner.rect = (0, 0, 2194, 1234)
        owner.native_rect = (0, 0, 3840, 2160)
        owner.window_context, owner.window_dpi, owner.target_awareness = 2, 168, 2
        return owner
    def test_move_only_posts_one_wm200_with_dpi_mapping_and_no_button_release(self):
        owner = self.dpi_owner(); owner.foreground, owner.focus_allowed = 999, False
        result = owner.mouse().mouse_move(1005, 699, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual(result['queued_messages'], 1)
        self.assertFalse(result['release_posted'])
        self.assertFalse(result['focus_succeeded'])
        self.assertEqual(owner.foreground, 999)
        self.assertEqual(owner.focus_calls, [300])
        self.assertEqual(owner.posts, [(300, 0x200, 0, (1224 << 16) | 1759)])
        self.assertTrue(result['dpi_context_restored'])
        self.assertEqual(owner.thread_context, 1)
    def test_move_only_refuses_other_owner_scene_or_unstable_dpi(self):
        for change in (lambda o: setattr(o, 'pid', 999),
                       lambda o: o.scene.update(current='Land'),
                       lambda o: setattr(o, 'window_dpi', 0)):
            owner = FakeOwner(); change(owner)
            result = owner.mouse().mouse_move(42, 57, 'Login')
            self.assertEqual(result['status'], 'REFUSED')
            self.assertFalse(owner.posts)
            self.assertFalse(owner.focus_calls)
    def test_dpi_175_percent_maps_explicit_point_and_restores_own_thread(self):
        owner = self.dpi_owner()
        result = owner.mouse().left_click(1005, 699, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual(result['client_size'], [2194, 1234])
        self.assertEqual(result['native_client_size'], [3840, 2160])
        self.assertEqual(result['native_point'], [1759, 1224])
        self.assertEqual(result['window_dpi'], 168)
        self.assertEqual([p[3] for p in owner.posts], [(1224 << 16) | 1759] * 3)
        self.assertEqual(owner.thread_context, 1)
        self.assertEqual(owner.context_changes, [(1, 2), (2, 1)] * (len(owner.context_changes) // 2))
    def test_dpi_unaware_100_percent_point_unchanged(self):
        owner = FakeOwner()
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['native_point'], [42, 57])
        self.assertEqual(result['client_size'], result['native_client_size'])
        self.assertEqual(owner.thread_context, 1)
    def test_dpi_or_native_rect_change_after_move_refuses_down(self):
        for field, value in (('window_dpi', 192), ('native_rect', (0, 0, 4000, 2160)),
                             ('window_context', 3)):
            owner = self.dpi_owner()
            owner.after_post = lambda message: setattr(owner, field, value)
            result = owner.mouse().left_click(1005, 699, 'Login')
            self.assertEqual(result['status'], 'PARTIAL')
            self.assertEqual(result['reason'], 'INPUT_WINDOW_CHANGED')
            self.assertEqual([p[1] for p in owner.posts], [0x200])
            self.assertEqual(owner.thread_context, 1)
    def test_unknown_dpi_refuses_without_unscaled_fallback(self):
        owner = self.dpi_owner()
        owner.window_dpi = 0
        result = owner.mouse().left_click(1005, 699, 'Login')
        self.assertEqual(result['reason'], 'INPUT_DPI_UNKNOWN')
        self.assertFalse(owner.posts)
    def test_dpi_native_rect_failure_restores_thread_without_fallback(self):
        owner = self.dpi_owner()
        owner.fail_native_rect = True
        result = owner.mouse().left_click(1005, 699, 'Login')
        self.assertEqual(result['reason'], 'INPUT_NATIVE_CLIENT_RECT_UNKNOWN')
        self.assertEqual(owner.context_changes, [(1, 2), (2, 1)])
        self.assertEqual(owner.thread_context, 1)
        self.assertFalse(owner.posts)
    def test_dpi_restore_failure_refuses_and_poison_prevents_new_input(self):
        owner = self.dpi_owner()
        owner.fail_restore = True
        mouse = owner.mouse()
        self.assertEqual(mouse.left_click(1005, 699, 'Login')['reason'], 'INPUT_DPI_CONTEXT_RESTORE_FAILED')
        self.assertEqual(mouse.left_click(1005, 699, 'Login')['reason'], 'INPUT_DPI_CONTEXT_UNRECOVERED')
        self.assertFalse(owner.posts)
    def test_dpi_scene_change_after_down_releases_same_transformed_point(self):
        owner = self.dpi_owner()
        def transition(message):
            if message == 0x201:
                owner.scene.update(current='Land')
        owner.after_post = transition
        result = owner.mouse().left_click(1005, 699, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertTrue(result['release_posted'])
        self.assertEqual(len(set(p[3] for p in owner.posts)), 1)
        self.assertEqual(owner.thread_context, 1)
    def test_hidden_eight_windows_do_not_truncate_single_glfw_inventory(self):
        owner = FakeOwner()
        owner.hwnds = list(range(300, 309))
        owner.hidden = set(range(300, 308))
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual([p[0] for p in owner.posts], [308, 308, 308])
    def test_second_visible_glfw_refused(self):
        owner = FakeOwner()
        owner.hwnds = [300, 301]
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(result['reason'], 'INPUT_EXACT_SINGLE_WINDOW_REQUIRED')
        self.assertFalse(owner.posts)
    def test_truncated_or_overflow_inventory_refused(self):
        owner = FakeOwner()
        owner.enumeration_complete = False
        self.assertEqual(owner.mouse().left_click(1, 2, 'Login')['reason'],
                         'INPUT_WINDOW_INVENTORY_INCOMPLETE')
        self.assertFalse(owner.posts)
        owner = FakeOwner()
        owner.hwnds = list(range(300, 4397))
        owner.hidden = set(owner.hwnds[:-1])
        self.assertEqual(owner.mouse().left_click(1, 2, 'Login')['reason'],
                         'INPUT_WINDOW_INVENTORY_OVERFLOW')
        self.assertFalse(owner.posts)
    def test_callback_error_refused_without_input(self):
        owner = FakeOwner()
        owner.native.u.GetClassNameW.callback = lambda *args: 0
        self.assertEqual(owner.mouse().left_click(1, 2, 'Login')['reason'],
                         'INPUT_WINDOW_CLASS_UNKNOWN')
        self.assertFalse(owner.posts)
    def test_pending_or_unready_scene_refused_without_input(self):
        for changes in (dict(pending='Land'), dict(root_ready=False), dict(root_ready=1)):
            owner = FakeOwner()
            owner.scene.update(changes)
            result = owner.mouse().left_click(1, 2, 'Login')
            self.assertEqual(result['reason'], 'INPUT_SCENE_MISMATCH')
            self.assertFalse(owner.posts)
    def test_point_uses_original_mousemove_then_down_up(self):
        owner = FakeOwner()
        result = owner.mouse().left_click(42, 57, 'Login')
        self.assertEqual(owner.posts, [(300, 0x200, 0, (57 << 16) | 42),
                                     (300, 0x201, 1, (57 << 16) | 42),
                                     (300, 0x202, 0, (57 << 16) | 42)])
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual(result['ui_result'], 'UNKNOWN')
        self.assertTrue(result['release_posted'])
    def test_ambiguous_or_wrong_class_or_wrong_owner_never_posts(self):
        for change in (lambda o: setattr(o, 'hwnds', [300, 301]),
                       lambda o: setattr(o, 'hwnds', list(range(300, 308))),
                       lambda o: setattr(o, 'class_name', 'other'),
                       lambda o: setattr(o, 'pid', 999),
                       lambda o: setattr(o, 'owner_handle', 999),
                       lambda o: setattr(o, 'token', dict(elevated=False, integrity_rid=4096))):
            owner = FakeOwner(); change(owner)
            self.assertEqual(owner.mouse().left_click(1, 2, 'Login')['status'], 'REFUSED')
            self.assertFalse(owner.posts)
    def test_coordinates_are_client_integer_and_signed_message_range(self):
        for point in ((True, 1), (-1, 1), (960, 1), (1, 640), (32768, 1), (1.0, 1)):
            owner = FakeOwner()
            self.assertEqual(owner.mouse().left_click(*point, 'Login')['status'], 'REFUSED')
            self.assertFalse(owner.posts)
    def test_scene_mismatch_prevents_any_input(self):
        owner = FakeOwner()
        self.assertEqual(owner.mouse().left_click(1, 2, 'Land')['status'], 'REFUSED')
        self.assertFalse(owner.posts)
    def test_scene_change_after_move_prevents_down(self):
        owner = FakeOwner()
        owner.after_post = lambda message: owner.scene.update(current='Land')
        result = owner.mouse().left_click(1, 2, 'Login')
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual([p[1] for p in owner.posts], [0x200])
    def test_scene_change_after_down_still_releases_same_window(self):
        owner = FakeOwner()
        def transition(message):
            if message == 0x201:
                owner.scene.update(current='Land')
        owner.after_post = transition
        result = owner.mouse().left_click(1, 2, 'Login')
        self.assertEqual(result['status'], 'POSTED')
        self.assertEqual([p[1] for p in owner.posts], [0x200, 0x201, 0x202])
    def test_owner_loss_after_down_never_releases_to_lost_owner(self):
        owner = FakeOwner()
        def lose(message):
            if message == 0x201:
                owner.alive = False
        owner.after_post = lose
        result = owner.mouse().left_click(1, 2, 'Login')
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertFalse(result['release_posted'])
        self.assertEqual(result['release_reason'], 'INPUT_OWNER_LOST')
        self.assertEqual([p[1] for p in owner.posts], [0x200, 0x201])
    def test_rectangle_change_refuses_further_messages(self):
        owner = FakeOwner()
        owner.after_post = lambda message: setattr(owner, 'rect', (0, 0, 800, 600))
        result = owner.mouse().left_click(1, 2, 'Login')
        self.assertEqual(result['reason'], 'INPUT_WINDOW_CHANGED')
        self.assertEqual(len(owner.posts), 1)


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.owner = FakeOwner()
        self.handler = i.InputRequests(self.directory, self.owner.mouse())
    def tearDown(self):
        self.temp.cleanup()
    def test_refused_foreground_posted_click_cannot_repeat_on_poll_or_handler_reload(self):
        self.owner.foreground, self.owner.focus_allowed = 999, False
        self.request()
        result = self.handler.poll()
        self.assertEqual(result['status'], 'POSTED')
        self.assertFalse(result['focus_succeeded'])
        self.assertIsNone(self.handler.poll())
        second = i.InputRequests(self.directory, self.owner.mouse())
        self.assertIsNone(second.poll())
        self.assertEqual(self.owner.focus_calls, [300])
        self.assertEqual(len(self.owner.posts), 3)
        self.assertEqual(self.owner.foreground, 999)
    def test_move_only_strict_request_and_monotonic_replay_protection(self):
        self.request(action='mouse_move')
        self.assertEqual(self.handler.poll()['status'], 'POSTED')
        self.assertEqual([row[1] for row in self.owner.posts], [0x200])
        self.assertIsNone(self.handler.poll())
        second = i.InputRequests(self.directory, self.owner.mouse())
        self.assertIsNone(second.poll())
        self.request(action='mouse_move', x=2)
        self.assertEqual(second.poll()['reason'], 'INPUT_SEQUENCE_ALREADY_CONSUMED')
        self.assertEqual(len(self.owner.posts), 1)
        self.request(action='mouse_move', sequence=2, x=2)
        self.assertEqual(second.poll()['status'], 'POSTED')
        self.assertEqual([row[1] for row in self.owner.posts], [0x200, 0x200])
        self.request(action='mouse_move', sequence=3, extra=True)
        self.assertEqual(second.poll()['reason'], 'INPUT_REQUEST_SCHEMA_REQUIRED')
        self.assertEqual(len(self.owner.posts), 2)
    def request(self, **changes):
        row = dict(schema=i.REQUEST_SCHEMA, action='left_click', x=1, y=2,
                   expected_scene='Login', sequence=1)
        row.update(changes)
        self.handler.request.write_text(json.dumps(row), encoding='utf-8')
    def test_duplicate_and_reloaded_handler_cannot_repeat_click(self):
        self.request()
        self.assertEqual(self.handler.poll()['status'], 'POSTED')
        self.assertIsNone(self.handler.poll())
        second = i.InputRequests(self.directory, self.owner.mouse())
        self.assertIsNone(second.poll())
        self.request(x=3)
        self.assertEqual(second.poll()['reason'], 'INPUT_SEQUENCE_ALREADY_CONSUMED')
        self.assertEqual(len(self.owner.posts), 3)
    def test_malformed_or_oversize_is_one_refusal_without_click(self):
        for raw in ('{', 'x' * 1025, '{"sequence":1,"sequence":2}', '[1,2]'):
            self.handler.request.write_text(raw, encoding='utf-8')
            self.assertEqual(self.handler.poll()['status'], 'REFUSED')
            self.assertIsNone(self.handler.poll())
        self.assertFalse(self.owner.posts)
    def test_unknown_action_or_extra_field_consumes_sequence(self):
        self.request(action='call_engine')
        self.assertEqual(self.handler.poll()['reason'], 'INPUT_REQUEST_SCHEMA_REQUIRED')
        self.request()
        self.assertEqual(self.handler.poll()['reason'], 'INPUT_SEQUENCE_ALREADY_CONSUMED')
        self.request(sequence=2, extra=True)
        self.assertEqual(self.handler.poll()['reason'], 'INPUT_REQUEST_SCHEMA_REQUIRED')
        self.assertFalse(self.owner.posts)
    def test_claim_is_written_before_input_and_restart_never_retries_partial(self):
        observed = []
        def post(message):
            prior = json.loads(self.handler.result.read_bytes())
            observed.append(prior['reason'])
            if message == 0x201:
                self.owner.alive = False
        self.owner.after_post = post
        self.request()
        self.assertEqual(self.handler.poll()['status'], 'PARTIAL')
        self.assertEqual(observed, ['INPUT_CLAIMED_NO_RETRY'] * 2)
        second = i.InputRequests(self.directory, self.owner.mouse())
        self.assertIsNone(second.poll())
        self.assertEqual(len(self.owner.posts), 2)
    def test_result_write_failure_never_posts_and_disables_handler(self):
        self.request()
        with patch.object(self.handler, '_write', side_effect=OSError('write failed')):
            self.assertEqual(self.handler.poll()['status'], 'REFUSED')
        self.assertTrue(self.handler.disabled)
        self.assertFalse(self.owner.posts)
    def test_reparse_attribute_refused_before_read(self):
        actual = Path.lstat
        target = self.handler.request
        self.request()
        def replaced(path):
            info = actual(path)
            if path == target:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        with patch.object(Path, 'lstat', replaced):
            self.assertEqual(self.handler.poll()['reason'], 'INPUT_REPARSE_REFUSED')
        self.assertFalse(self.owner.posts)


if __name__ == '__main__':
    unittest.main()
