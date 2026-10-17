"""Capture desktop pixels within one exact owned game window rectangle only."""
from __future__ import annotations

import argparse
import ctypes as C
import json
import uuid
from ctypes import wintypes as W
from pathlib import Path

from PIL import ImageGrab
import capture_window

OUTPUT = capture_window.OUTPUT
user = capture_window.user
user.ShowWindow.argtypes = (W.HWND, C.c_int)
user.ShowWindow.restype = W.BOOL
user.SetForegroundWindow.argtypes = (W.HWND,)
user.SetForegroundWindow.restype = W.BOOL


def capture(pid, birth, *, focus):
    capture_window.identity(pid, birth)
    choices = capture_window.windows(pid)
    capture_window.need(choices, 'OWNED_WINDOW_NOT_VISIBLE')
    _, hwnd, width, height = choices[0]
    if focus:
        user.ShowWindow(hwnd, 9)
        user.SetForegroundWindow(hwnd)
    rect = capture_window.RECT()
    capture_window.need(user.GetWindowRect(hwnd, C.byref(rect)), 'OWNED_RECT_UNKNOWN')
    capture_window.need(rect.right - rect.left == width and rect.bottom - rect.top == height,
                        'OWNED_WINDOW_RECT_CHANGED')
    image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom),
                           all_screens=True)
    OUTPUT.mkdir(exist_ok=True)
    token = uuid.uuid4().hex
    path = OUTPUT / ('visible-' + token + '.png')
    image.save(path)
    report = {'schema': 'lc-exact-owned-desktop-crop-v1', 'pid': pid, 'birth': birth,
              'window_size': [width, height], 'focus_attempted': focus,
              'crop_scope': 'exact_owned_window_rect', 'path': str(path),
              'character_screen_verified': False}
    metadata = OUTPUT / ('visible-' + token + '.json')
    with metadata.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return {'status': 'CAPTURED', 'image': str(path), 'report': str(metadata),
            'width': width, 'height': height}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--birth')
    parser.add_argument('--focus', action='store_true')
    args = parser.parse_args()
    if not args.capture:
        print(json.dumps({'status': 'PLAN', 'exact_owned_window_only': True}))
        return 0
    capture_window.need(args.pid and args.birth and args.birth.isdecimal(),
                        'EXACT_IDENTITY_REQUIRED')
    print(json.dumps(capture(args.pid, args.birth, focus=args.focus)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
