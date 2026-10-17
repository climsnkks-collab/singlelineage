"""Post Return only to an exact owned LC window, without foreground focus."""
from __future__ import annotations

import argparse
import ctypes as C
import json
import time
from ctypes import wintypes as W

import capture_window

user = capture_window.user
user.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
user.PostMessageW.restype = W.BOOL


def enter(pid, birth):
    capture_window.identity(pid, birth)
    choices = capture_window.windows(pid)
    capture_window.need(choices, 'OWNED_WINDOW_NOT_VISIBLE')
    hwnd = choices[0][1]
    capture_window.need(user.PostMessageW(hwnd, 0x100, 0x0d, 0x001c0001),
                        'OWNED_RETURN_DOWN_FAILED')
    capture_window.need(user.PostMessageW(hwnd, 0x102, 0x0d, 0x001c0001),
                        'OWNED_RETURN_CHAR_FAILED')
    time.sleep(0.08)
    capture_window.need(user.PostMessageW(hwnd, 0x101, 0x0d, 0xc01c0001),
                        'OWNED_RETURN_UP_FAILED')
    return {'status': 'POSTED', 'pid': pid, 'key': 'Return',
            'exact_owned_window': True, 'resulting_scene': 'UNKNOWN'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enter', action='store_true')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--birth')
    args = parser.parse_args()
    if not args.enter:
        print(json.dumps({'status': 'PLAN', 'exact_owned_window_required': True}))
        return 0
    capture_window.need(args.pid and args.birth and args.birth.isdecimal(),
                        'EXACT_IDENTITY_REQUIRED')
    print(json.dumps(enter(args.pid, args.birth)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
