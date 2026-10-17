"""Post one bounded click to an exact owned game window client coordinate."""
from __future__ import annotations

import argparse
import ctypes as C
import json
import time
from ctypes import wintypes as W

import capture_window

user = capture_window.user
user.GetClientRect.argtypes = (W.HWND, C.c_void_p)
user.GetClientRect.restype = W.BOOL
user.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
user.PostMessageW.restype = W.BOOL


def click(pid, birth, x, y):
    capture_window.identity(pid, birth)
    choices = capture_window.windows(pid)
    capture_window.need(choices, 'OWNED_WINDOW_NOT_VISIBLE')
    _, hwnd, _, _ = choices[0]
    rect = capture_window.RECT()
    capture_window.need(user.GetClientRect(hwnd, C.byref(rect)), 'OWNED_CLIENT_RECT_UNKNOWN')
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    capture_window.need(0 <= x < width and 0 <= y < height,
                        'CLICK_OUTSIDE_OWNED_CLIENT')
    lparam = (y << 16) | x
    capture_window.need(user.PostMessageW(hwnd, 0x201, 1, lparam),
                        'OWNED_CLICK_DOWN_FAILED')
    time.sleep(0.08)
    capture_window.need(user.PostMessageW(hwnd, 0x202, 0, lparam),
                        'OWNED_CLICK_UP_FAILED')
    return {'status': 'POSTED', 'pid': pid, 'client_size': [width, height],
            'client_point': [x, y], 'game_state_result': 'UNKNOWN'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--click', action='store_true')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--birth')
    parser.add_argument('--x', type=int)
    parser.add_argument('--y', type=int)
    args = parser.parse_args()
    if not args.click:
        print(json.dumps({'status': 'PLAN', 'exact_owned_window_only': True}))
        return 0
    capture_window.need(args.pid and args.birth and args.birth.isdecimal()
                        and args.x is not None and args.y is not None,
                        'EXACT_IDENTITY_AND_POINT_REQUIRED')
    print(json.dumps(click(args.pid, args.birth, args.x, args.y)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
