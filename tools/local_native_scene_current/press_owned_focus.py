"""Automatic Return after attaching to the exact owned window's input queue."""
from __future__ import annotations

import ctypes as C
import time
from ctypes import wintypes as W

import capture_window

user = capture_window.user
kernel = capture_window.kernel
kernel.GetCurrentThreadId.argtypes = ()
kernel.GetCurrentThreadId.restype = W.DWORD
user.AttachThreadInput.argtypes = (W.DWORD, W.DWORD, W.BOOL)
user.AttachThreadInput.restype = W.BOOL
user.GetForegroundWindow.argtypes = ()
user.GetForegroundWindow.restype = W.HWND
user.SetForegroundWindow.argtypes = (W.HWND,)
user.SetForegroundWindow.restype = W.BOOL
user.BringWindowToTop.argtypes = (W.HWND,)
user.BringWindowToTop.restype = W.BOOL
user.ShowWindow.argtypes = (W.HWND, C.c_int)
user.ShowWindow.restype = W.BOOL
user.PeekMessageW.argtypes = (C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT)
user.PeekMessageW.restype = W.BOOL
user.keybd_event.argtypes = (C.c_ubyte, C.c_ubyte, W.DWORD, C.c_size_t)
user.keybd_event.restype = None


def enter(pid, birth):
    capture_window.identity(pid, birth)
    choices = capture_window.windows(pid)
    capture_window.need(choices, 'OWNED_WINDOW_NOT_VISIBLE')
    hwnd = choices[0][1]
    owner = W.DWORD()
    target_thread = user.GetWindowThreadProcessId(hwnd, C.byref(owner))
    capture_window.need(target_thread and owner.value == pid,
                        'OWNED_WINDOW_THREAD_CHANGED')
    current_thread = kernel.GetCurrentThreadId()
    msg = W.MSG()
    user.PeekMessageW(C.byref(msg), None, 0, 0, 0)
    attached = False
    try:
        if current_thread != target_thread:
            attached = bool(user.AttachThreadInput(current_thread, target_thread, True))
            capture_window.need(attached, 'OWNED_INPUT_QUEUE_ATTACH_FAILED')
        user.ShowWindow(hwnd, 9)
        user.BringWindowToTop(hwnd)
        user.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user.AttachThreadInput(current_thread, target_thread, False)
    time.sleep(0.05)
    capture_window.need(user.GetForegroundWindow() == hwnd,
                        'OWNED_WINDOW_NOT_FOREGROUND')
    user.keybd_event(0x0d, 0, 0, 0)
    time.sleep(0.08)
    user.keybd_event(0x0d, 0, 0x0002, 0)
    return {'status': 'FOCUSED_SENT', 'pid': pid, 'key': 'Return',
            'exact_owned_window': True, 'resulting_scene': 'UNKNOWN'}
