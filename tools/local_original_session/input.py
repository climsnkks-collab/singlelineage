"""Explicit private message and opt-in native helper input for the retained primary.

Queued messages prove POSTED only; resulting UI/movement is UNKNOWN.
PrivateInput uses only the owned non-input desktop helper. OwnedMouse retains
its separate interactive-desktop cursor/focus behavior and is not used by it.
GLFW_CALLBACK_INJECTION awaits native input helpers; resulting UI stays UNKNOWN.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import asyncio
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import stat
import time

from .desktop import normalize_click_options

REQUEST_SCHEMA = 'local-original-input-request-v1'
RESULT_SCHEMA = 'local-original-input-result-v1'
MAX_SEQUENCE = (1 << 53) - 1
GLFW_INPUT_SCHEMA = 'companion-glfw-input-v1'
GLFW_INPUT_ROUTE = 'GLFW_CALLBACK_INJECTION'
GLFW_MAX_SEQUENCE = (1 << 31) - 1


def need(value, reason):
    if not value:
        raise ValueError(reason)


def reason(error):
    text = error.args[0] if len(error.args) == 1 else None
    return text if isinstance(text, str) and text.startswith('INPUT_') else 'INPUT_OPERATION_FAILED'


def capture_to_client(request, capture, current):
    """Convert top-left PNG pixels from a same-run GL crop; never DPI-scale.

    Capture must describe the read drawable in native client pixels. A nonzero
    FBO has no established presentation transform and is refused. Legacy v5
    host observations explicitly retain their inferred drawable relation.
    """
    need(type(capture) is dict and type(current) is dict, 'INPUT_CAPTURE_REQUIRED')
    for key in ('pid', 'birth', 'candidate_sha256', 'hwnd', 'ui_thread',
                'client_rect', 'window_dpi', 'window_awareness'):
        need(capture.get(key) is not None and capture[key] == current.get(key),
             'INPUT_CAPTURE_GEOMETRY_CHANGED')
    need(current.get('awareness_equal') is True and current['window_awareness'] == 2,
         'INPUT_CAPTURE_NATIVE_PIXELS_REQUIRED')
    need(capture.get('read_fbo') == 0 or (capture.get('read_fbo') is None
         and capture.get('relation') == 'INFERRED_DEFAULT_CLIENT_DRAWABLE_V5'),
         'INPUT_CAPTURE_FBO_RELATION_UNKNOWN')
    rect = capture['client_rect']
    need(rect[:2] == [0, 0] and capture.get('read_size') == rect[2:],
         'INPUT_CAPTURE_DRAWABLE_MISMATCH')
    cx, cy, width, height = capture['crop']
    need(all(type(n) is int for n in (cx, cy, width, height))
         and cx >= 0 and cy >= 0 and width > 0 and height > 0
         and cx + width <= rect[2] and cy + height <= rect[3]
         and capture.get('png_size') == [width, height], 'INPUT_CAPTURE_CROP_MISMATCH')
    offset = [cx, rect[3] - cy - height]
    def point(value):
        need(type(value) in (list, tuple) and len(value) == 2
             and all(type(n) is int for n in value)
             and 0 <= value[0] < width and 0 <= value[1] < height,
             'INPUT_CAPTURE_POINT_OUTSIDE_PNG')
        answer = [value[0] + offset[0], value[1] + offset[1]]
        need(all(0 <= n <= 32767 for n in answer), 'INPUT_CAPTURE_POINT_BOUND')
        return answer
    converted = dict(request)
    if request.get('action') == 'left_drag':
        need(type(request.get('points')) is list and len(request['points']) >= 2,
             'INPUT_CAPTURE_DRAG_POINTS_REQUIRED')
        converted['points'] = [point(p) for p in request['points']]
    elif request.get('action') in ('left_click', 'left_double_click', 'mouse_move', 'mouse_wheel'):
        converted['x'], converted['y'] = point([request.get('x'), request.get('y')])
    else:
        need(request.get('action') in ('key_press', 'type_text'), 'INPUT_ACTION_UNAVAILABLE')
    return converted, dict(scale=[1, 1], offset=offset, png_request=request,
                          client_request=converted, capture=capture)


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


class PrivateInput:
    """Message adapter for the retained private desktop; no global input.

    observation_target returns fresh {identity, hwnd, ui_thread}. Coordinates
    are native client pixels in the target window's DPI context. Scene reads
    remain observations and never directly invoke an original UI callback.
    click_options configure only click/double-click: activate posts focus
    messages, while move_settle_ms/down_hold_ms are wall-clock pacing only.
    """
    def __init__(self, owner, *, observation_scene, observation_target, click_options=None):
        need(callable(observation_scene) and callable(observation_target),
             'INPUT_OBSERVATION_CALLBACK_REQUIRED')
        self.owner = owner
        self.observation_scene = observation_scene
        self.observation_target = observation_target
        self.click_options = normalize_click_options(click_options)

    def _scene(self, expected):
        need(type(expected) is str
             and expected in ('Intro', 'Lobby', 'Login', 'CharacterSelect', 'Land'),
             'INPUT_EXPECTED_SCENE_REQUIRED')
        scene = self.observation_scene()
        need(type(scene) is dict and scene.get('status') == 'OBSERVED'
             and scene.get('current') == expected and scene.get('pending') == 'none'
             and scene.get('root_ready') is True, 'INPUT_SCENE_MISMATCH')

    def _post(self, action, expected_scene, **parameters):
        result = dict(status='REFUSED', ui_result='UNKNOWN', queued_messages=0,
                      release_posted=False, automatic_retry=False,
                      input_route='PRIVATE_DESKTOP_MESSAGES')
        native_result = None
        if action in ('left_click', 'left_double_click'):
            parameters['click_options'] = dict(self.click_options)
            result.update(click_options=dict(self.click_options),
                          click_timing='WALL_CLOCK_ONLY_NO_FRAME_PROOF')
        try:
            self._scene(expected_scene)
            target = self.observation_target()
            need(type(target) is dict, 'INPUT_TARGET_OBSERVATION_REQUIRED')
            desktop = self.owner.private_desktop
            need(desktop is not None, 'INPUT_PRIVATE_DESKTOP_REQUIRED')
            native_result = desktop.post_client_input(self.owner, target['identity'],
                target['hwnd'], target['ui_thread'], action,
                check_scene=lambda: self._scene(expected_scene),
                **({'expected_geometry': target['expected_geometry']}
                   if 'expected_geometry' in target else {}), **parameters)
            result.update(status='POSTED', hwnd=target['hwnd'], ui_thread=target['ui_thread'],
                          expected_scene=expected_scene)
        except Exception as error:
            result['reason'] = reason(error)
            if str(error).startswith(('CLIENT_', 'PRIVATE_')):
                result['native_reason'] = str(error)
            native_result = getattr(error, 'client_click_result', None)
            if native_result is not None and native_result.queued:
                result['status'] = 'PARTIAL'
        if native_result is not None:
            result.update(queued_messages=len(native_result.queued),
                          release_posted=bool(native_result.queued
                              and native_result.queued[-1] in (0x202, 0x101)),
                          cleanup_up=native_result.cleanup_up,
                          cleanup_errors=list(native_result.cleanup_errors))
            if native_result.desktop_thread_check is not None:
                result['desktop_thread_check'] = native_result.desktop_thread_check
        return result

    def left_click(self, x, y, expected_scene):
        return self._post('left_click', expected_scene, x=x, y=y)

    def mouse_move(self, x, y, expected_scene):
        return self._post('mouse_move', expected_scene, x=x, y=y)

    def left_double_click(self, x, y, expected_scene):
        return self._post('left_double_click', expected_scene, x=x, y=y)

    def left_drag(self, points, expected_scene):
        return self._post('left_drag', expected_scene, points=points)

    def mouse_wheel(self, x, y, delta, expected_scene):
        return self._post('mouse_wheel', expected_scene, x=x, y=y, delta=delta)

    def key_press(self, key, expected_scene):
        return self._post('key_press', expected_scene, key=key)


class GlfwCallbackInput(PrivateInput):
    """Opt-in diagnostic file transport; await native input helper completion.

    Uses the same owned private target and client-pixel geometry observations as
    PrivateInput. No OS input, focus, cursor or retry is performed. Full event
    evidence stays in glfw-input.result.json; helper completion is not UI proof.
    """
    def __init__(self, owner, directory, *, observation_scene, observation_target,
                 enabled=False, click_options=None, timeout=30):
        super().__init__(owner, observation_scene=observation_scene,
                         observation_target=observation_target, click_options=click_options)
        need(enabled is True, 'INPUT_GLFW_OPT_IN_REQUIRED')
        need(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 120,
             'INPUT_GLFW_TIMEOUT_REQUIRED')
        self.directory = _ordinary(Path(directory).absolute(), directory=True)
        self.request = self.directory / 'glfw-input.request.json'
        self.result = self.directory / 'glfw-input.result.json'
        self.temporary = self.directory / 'glfw-input.request.tmp'
        self.timeout = timeout
        self.inflight = False

    def _target(self):
        target = self.observation_target()
        need(type(target) is dict, 'INPUT_TARGET_OBSERVATION_REQUIRED')
        desktop = self.owner.private_desktop
        need(desktop is not None, 'INPUT_PRIVATE_DESKTOP_REQUIRED')
        geometry = desktop.observe_client_geometry(self.owner, target['identity'],
                                                   target['hwnd'], target['ui_thread'])
        need(type(geometry) is dict and geometry.get('status') == 'OBSERVED'
             and geometry.get('awareness_equal') is True
             and geometry.get('window_awareness') == 2, 'INPUT_CAPTURE_NATIVE_PIXELS_REQUIRED')
        expected = target.get('expected_geometry')
        keys = ('pid', 'birth', 'candidate_sha256', 'hwnd', 'ui_thread',
                'client_rect', 'window_dpi', 'window_awareness')
        if expected is not None:
            need(all(geometry.get(k) == expected.get(k) for k in keys),
                 'INPUT_CAPTURE_GEOMETRY_CHANGED')
        return target, {k: geometry[k] for k in keys}

    def _events(self, action, geometry, parameters):
        rect = geometry['client_rect']
        def point(xy):
            need(type(xy) in (list, tuple) and len(xy) == 2
                 and all(type(n) is int for n in xy)
                 and rect[0] <= xy[0] < rect[2] and rect[1] <= xy[1] < rect[3],
                 'INPUT_GLFW_POINT_OUTSIDE_CLIENT')
            return dict(type='cursor', x=xy[0], y=xy[1], delay_ms=0)
        def button(action, delay=0):
            return dict(type='button', button=0, action=action, mods=0, delay_ms=delay)
        if action in ('left_click', 'left_double_click'):
            need(not self.click_options['activate'], 'INPUT_GLFW_ACTIVATION_UNSUPPORTED')
            move_delay, hold_delay = (self.click_options[k] for k in ('move_settle_ms', 'down_hold_ms'))
            events = [point((parameters['x'], parameters['y'])), button(1, move_delay), button(0, hold_delay)]
            if action == 'left_double_click':
                events.extend((button(1), button(0, hold_delay)))
        elif action == 'mouse_move':
            events = [point((parameters['x'], parameters['y']))]
        elif action == 'left_drag':
            path = parameters['points']
            need(type(path) in (list, tuple) and 2 <= len(path) <= 254,
                 'INPUT_GLFW_DRAG_POINTS_REQUIRED')
            moves = [point(xy) for xy in path]
            events = [moves[0], button(1), *moves[1:], button(0)]
        elif action == 'mouse_wheel':
            delta = parameters['delta']
            need(type(delta) is int and -32768 <= delta <= 32767 and delta != 0,
                 'INPUT_GLFW_WHEEL_DELTA_REQUIRED')
            events = [point((parameters['x'], parameters['y'])),
                      dict(type='wheel', xoff=0, yoff=delta / 120, delay_ms=0)]
        elif action == 'key_press':
            key = parameters['key']
            keys = {'Enter': (257, 0x1c), 'Escape': (256, 0x01),
                    'Tab': (258, 0x0f), 'Backspace': (259, 0x0e),
                    'Delete': (261, 0x153), 'Left': (263, 0x14b), 'Right': (262, 0x14d)}
            keys.update({str(n): (48+n, 0x0b if n == 0 else n+1) for n in range(10)})
            need(type(key) is str and key in keys, 'INPUT_GLFW_KEY_REQUIRED')
            code, scan = keys[key]
            down = dict(type='key', key=code, scancode=scan, action=1, mods=0, delay_ms=0)
            events = [down]
            if key in '0123456789':
                # There is no TranslateMessage on this callback route.
                events.append(dict(type='char', codepoint=ord(key), mods=0, plain=1, delay_ms=0))
            events.append(dict(down, action=0))
        elif action == 'type_text':
            text = parameters['text']
            need(type(text) is str and 1 <= len(text) <= 256
                 and all(not 0xd800 <= ord(c) <= 0xdfff and ord(c) > 0 for c in text),
                 'INPUT_GLFW_TEXT_REQUIRED')
            events = [dict(type='char', codepoint=ord(c), mods=0, plain=1, delay_ms=0) for c in text]
        else:
            raise ValueError('INPUT_ACTION_UNAVAILABLE')
        need(1 <= len(events) <= 256, 'INPUT_GLFW_EVENT_BOUND')
        return events

    def _native_file(self, path):
        try:
            row = json.loads(_read(path, 196608 if path == self.result else 65536,
                                   shared_snapshot=path == self.result), object_pairs_hook=_unique_object)
        except FileNotFoundError:
            return None
        need(type(row) is dict and row.get('schema') == GLFW_INPUT_SCHEMA
             and type(row.get('sequence')) is int and 1 <= row['sequence'] <= GLFW_MAX_SEQUENCE,
             'INPUT_GLFW_PRIOR_FILE_INVALID')
        return row

    async def _post(self, action, expected_scene, **parameters):
        outcome = dict(status='REFUSED', ui_result='UNKNOWN', automatic_retry=False,
                       input_route=GLFW_INPUT_ROUTE, frame_count='UNKNOWN', completed_events=0)
        sequence = None
        claimed = False
        published = False
        try:
            need(not self.inflight, 'INPUT_GLFW_ALREADY_INFLIGHT')
            self.inflight = claimed = True
            self._scene(expected_scene)
            target, geometry = self._target()
            events = self._events(action, geometry, parameters)
            prior_request, prior_result = self._native_file(self.request), self._native_file(self.result)
            terminal = ('COMPLETED', 'FAILED', 'REFUSED')
            if prior_result is not None:
                need(prior_result.get('status') in terminal, 'INPUT_GLFW_REQUEST_PENDING')
            if prior_request is not None:
                need(prior_result is not None and prior_result['sequence'] >= prior_request['sequence'],
                     'INPUT_GLFW_REQUEST_PENDING')
            sequence = max((row['sequence'] for row in (prior_request, prior_result) if row), default=0) + 1
            need(sequence <= GLFW_MAX_SEQUENCE, 'INPUT_SEQUENCE_REQUIRED')
            raw = json.dumps(dict(schema=GLFW_INPUT_SCHEMA, sequence=sequence, events=events),
                             separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
            need(len(raw) <= 65536, 'INPUT_GLFW_REQUEST_BYTE_BOUND')
            self._scene(expected_scene)
            fresh_target, fresh_geometry = self._target()
            need(geometry == fresh_geometry and all(target[k] == fresh_target[k]
                 for k in ('identity', 'hwnd', 'ui_thread')), 'INPUT_CAPTURE_GEOMETRY_CHANGED')
            _ordinary(self.request, absent=True)
            _ordinary(self.temporary, absent=True)
            with self.temporary.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self.temporary, self.request)
            published = True
            outcome.update(native_sequence=sequence, native_result_path=str(self.result),
                           hwnd=target['hwnd'], ui_thread=target['ui_thread'],
                           expected_scene=expected_scene, event_count=len(events))
            deadline = time.monotonic() + self.timeout
            while True:
                result = self._native_file(self.result)
                if result is not None and result['sequence'] == sequence:
                    need(result.get('input_route') == GLFW_INPUT_ROUTE
                         and result.get('status') in ('RUNNING', *terminal), 'INPUT_GLFW_RESULT_INVALID')
                    count = result.get('completed_events')
                    need(type(count) is int and 0 <= count <= len(events), 'INPUT_GLFW_RESULT_INVALID')
                    outcome.update(native_status=result['status'], completed_events=count)
                    if result['status'] in terminal:
                        records = result.get('events')
                        need(type(records) is list and len(records) <= len(events)
                             and all(type(row) is dict for row in records), 'INPUT_GLFW_RESULT_INVALID')
                        outcome['native_event_count'] = len(records)
                        # Full records remain in the native result file (v1 outer result is bounded).
                        outcome['thread_ids'] = sorted({row['thread_id'] for row in records
                                                       if type(row.get('thread_id')) is int})[:8]
                        outcome['host_left_button_90'] = [row.get('host_left_button_90') for row in records[:8]]
                        failures = [row for row in records if row.get('exception_code')]
                        if failures:
                            outcome['exception_code'] = failures[0]['exception_code']
                        if result['status'] == 'COMPLETED':
                            need(count == len(events) and len(records) == len(events)
                                 and all(row.get('index') == index and row.get('type') == events[index]['type']
                                     and row.get('status') == 'RETURNED' and row.get('helper_returned') is True
                                     for index, row in enumerate(records)), 'INPUT_GLFW_RESULT_INCOMPLETE')
                            outcome['status'] = 'POSTED'
                            outcome['callback_invocation'] = 'NATIVE_HELPER_CONTROLS'
                        else:
                            outcome.update(status='PARTIAL' if count else result['status'],
                                           reason='INPUT_GLFW_NATIVE_' + result['status'])
                            if type(result.get('reason')) is str:
                                outcome['native_reason'] = result['reason'][:160]
                        return outcome
                if time.monotonic() >= deadline:
                    outcome.update(status='UNKNOWN', reason='INPUT_GLFW_COMPLETION_TIMEOUT',
                                   native_status=outcome.get('native_status', 'UNKNOWN'))
                    return outcome
                await asyncio.sleep(0.05)
        except Exception as error:
            outcome['reason'] = reason(error)
            if published:
                outcome['status'] = 'UNKNOWN'
            if str(error).startswith(('CLIENT_', 'PRIVATE_')):
                outcome['native_reason'] = str(error)
            return outcome
        finally:
            if claimed:
                self.inflight = False

    def type_text(self, text, expected_scene):
        return self._post('type_text', expected_scene, text=text)


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


def _read(path, limit, *, shared_snapshot=False):
    _ordinary(path)
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    if os.name == 'nt':
        # OPEN_REPARSE_POINT inspects the named file itself, including a link
        # introduced after lstat. Ordinary requests deny write/delete while read.
        # Native results are immutable snapshots replaced atomically; allow the
        # producer to rename the next snapshot while this handle reads the old.
        import msvcrt
        kernel = C.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE)
        create.restype = W.HANDLE
        kernel.GetFileInformationByHandle.argtypes = (W.HANDLE, C.c_void_p)
        kernel.GetFileInformationByHandle.restype = W.BOOL
        kernel.CloseHandle.argtypes = (W.HANDLE,)
        kernel.CloseHandle.restype = W.BOOL
        handle = create(str(path), 0x80000000, 5 if shared_snapshot else 1, None, 3, 0x00200000, None)
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
        need(stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1
             and (shared_snapshot or (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino))
             and not getattr(opened, 'st_file_attributes', 0) & 0x400,
             'INPUT_REQUEST_CHANGED')
        need(0 <= opened.st_size <= limit, 'INPUT_REQUEST_BYTE_BOUND')
        raw = os.read(descriptor, limit + 1)
        after = None if shared_snapshot else _ordinary(path).lstat()
        if not shared_snapshot and ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
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

    def _begin(self):
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
            fields = {
                'left_click': ('x', 'y'), 'mouse_move': ('x', 'y'),
                'left_double_click': ('x', 'y'), 'left_drag': ('points',),
                'mouse_wheel': ('x', 'y', 'delta'), 'key_press': ('key',),
                'type_text': ('text',),
            }
            action_name = request.get('action')
            need(type(action_name) is str and action_name in fields
                 and set(request) == {'schema', 'action', 'expected_scene', 'sequence',
                                      *fields.get(action_name, ())}
                 and request['schema'] == REQUEST_SCHEMA,
                 'INPUT_REQUEST_SCHEMA_REQUIRED')
            row = dict(schema=RESULT_SCHEMA, sequence=sequence, last_sequence=self.last_sequence,
                       request_sha256=fingerprint, status='REFUSED', reason='INPUT_CLAIMED_NO_RETRY',
                       ui_result='UNKNOWN', automatic_retry=False)
            self._write(row)
            action = getattr(self.mouse, action_name, None)
            need(callable(action), 'INPUT_ACTION_UNAVAILABLE')
            parameters = {field: request[field] for field in fields[action_name]}
            return row, action, parameters, request['expected_scene']
        except FileNotFoundError:
            return None
        except Exception as error:
            row = dict(schema=RESULT_SCHEMA, sequence=sequence, last_sequence=self.last_sequence,
                       request_sha256=fingerprint, status='REFUSED', reason=reason(error),
                       ui_result='UNKNOWN', automatic_retry=False)
        return row

    def _end(self, row):
        if row is None or self.disabled:
            return row
        if row == self.last_result:
            return None
        try:
            self._write(row)
        except Exception:
            self.disabled = True
            row['result_write_failed'] = True
        self.last_result = row
        return row

    def _outcome(self, row, outcome):
        row.update(outcome)
        if outcome['status'] == 'POSTED':
            row.pop('reason', None)

    def poll(self):
        work = self._begin()
        if type(work) is tuple:
            row, action, parameters, scene = work
            try:
                # Callback transport must use poll_async; never leave a coroutine
                # unawaited or claim POSTED before the diagnostic drain consumes it.
                if inspect.iscoroutinefunction(getattr(self.mouse, '_post', None)):
                    raise ValueError('INPUT_ASYNC_DISPATCH_REQUIRED')
                self._outcome(row, action(**parameters, expected_scene=scene))
            except Exception as error:
                row.update(status='REFUSED', reason=reason(error))
        else:
            row = work
        return self._end(row)

    async def poll_async(self):
        work = self._begin()
        if type(work) is tuple:
            row, action, parameters, scene = work
            try:
                outcome = action(**parameters, expected_scene=scene)
                if inspect.isawaitable(outcome):
                    outcome = await outcome
                self._outcome(row, outcome)
            except Exception as error:
                row.update(status='REFUSED', reason=reason(error))
        else:
            row = work
        return self._end(row)
