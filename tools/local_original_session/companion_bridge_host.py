"""Server -> companion bridge DLL publication over the owned run directory.

Contract: companion-bridge/SIGNALS.md "Host -> DLL" and "3차". A request is a
literal ``companion-request-<seq>.json`` (fixed field order, no spaces) and a
model is ``companion-model-<seq>.bin`` (LCMPMD2); each is announced to the
game's UI thread with the registered message ``LC-Owned-Companion-v1`` /
``LC-Owned-CompanionModel-v2`` and wParam=seq. The process identity comes from
the launcher's own ``context.json`` in that directory. ``ats-edit-apply``
(companion4) may add ``label_hex``; map may add ``name_hex``. LOCAL host; whether the
DLL consumed a file is only known from its ``companion-result-<seq>.json``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

REQUEST_MESSAGE = 'LC-Owned-Companion-v1'
MODEL_MESSAGE = 'LC-Owned-CompanionModel-v2'
DRAIN_MESSAGE = 'LC-Owned-CompanionDrain-v1'
REQUEST_FIELDS = ('command', 'actor_uid', 'actor_generation', 'owner_uid', 'member_id', 'hold',
                  'lawful_known', 'lawful', 'event_seq', 'ats_epoch')
COMMANDS = frozenset(('install', 'map', 'unmap', 'disable', 'ats-apply', 'ats-cancel', 'ats-edit-apply',
                      'ats-window-view', 'ats-window-result'))
LABEL_BYTES = 120
MAX_SEQUENCE = 2147483647
_SEQ = re.compile(r'-(\d+)\.(json|bin)$')


def request_text(identity, seq, values) -> str:
    """The exact literal own-companion-request-v1 line the DLL parser accepts."""
    if values['command'] not in COMMANDS:
        raise ValueError('COMPANION_HOST_COMMAND')
    if not 1 <= seq <= MAX_SEQUENCE:
        raise ValueError('COMPANION_HOST_SEQUENCE')
    sha = identity['candidate_sha256']
    if not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('COMPANION_HOST_IDENTITY')
    parts = ['"schema":"own-companion-request-v1"', f'"pid":{int(identity["pid"])}',
             f'"birth":{int(identity["birth"])}', f'"candidate_sha256":"{sha}"', f'"seq":{seq}',
             f'"command":"{values["command"]}"']
    for name in REQUEST_FIELDS[1:]:
        value = int(values.get(name, 0))
        if name == 'lawful':
            if not -(1 << 31) <= value < 1 << 31:
                raise ValueError('COMPANION_HOST_LAWFUL')
        elif name in ('hold', 'lawful_known'):
            if value not in (0, 1):
                raise ValueError('COMPANION_HOST_FLAG')
        elif not 0 <= value < 1 << 64:
            raise ValueError('COMPANION_HOST_FIELD')
        parts.append(f'"{name}":{value}')
    for name, error in (('label_hex', 'COMPANION_HOST_LABEL'), ('name_hex', 'COMPANION_HOST_NAME')):
        value = values.get(name)
        if value is not None:  # optional UTF-8 text as lowercase hex, at most 120 bytes
            if not re.fullmatch('(?:[0-9a-f]{2}){0,%d}' % LABEL_BYTES, value):
                raise ValueError(error)
            parts.append(f'"{name}":"{value}"')
    for command, name, prefix in (('ats-window-view', 'view_file', 'view'),
                                  ('ats-window-result', 'result_file', 'result')):
        value = values.get(name)
        if values['command'] == command:
            epoch = r'(?:0|[1-9][0-9]*)' if command == 'ats-window-result' else r'[1-9][0-9]*'
            if not isinstance(value, str) or re.fullmatch(
                    rf'companion-ats-{prefix}-{epoch}-[1-9][0-9]*\.json', value) is None:
                raise ValueError('COMPANION_HOST_' + name.upper())
            parts.append(f'"{name}":"{value}"')
        elif value is not None:
            raise ValueError('COMPANION_HOST_' + name.upper())
    text = '{' + ','.join(parts) + '}\n'
    if len(text.encode('ascii')) > 1024:
        raise ValueError('COMPANION_HOST_REQUEST_SIZE')
    return text


class DirectoryHost:
    """Owned run directory + UI-thread post; one sequence space per directory."""

    def __init__(self, directory, poster=None):
        self.directory = Path(directory)
        context = json.loads((self.directory / 'context.json').read_text(encoding='utf-8'))
        self.identity = dict(pid=int(context['pid']), birth=int(context['birth']),
                             candidate_sha256=str(context['candidate_sha256']))
        used = [int(m.group(1)) for path in self.directory.iterdir()
                if (m := _SEQ.search(path.name))
                and not path.name.startswith(('companion-signal-', 'companion-ats-'))]
        self.sequence = max(used, default=0)
        self.poster = poster if poster is not None else _window_poster(self.identity['pid'])
        self.installed = False
        self._models = set()

    def next_sequence(self) -> int:
        if self.sequence >= MAX_SEQUENCE:
            raise ValueError('COMPANION_HOST_SEQUENCE_EXHAUSTED')
        self.sequence += 1
        return self.sequence

    def _create(self, path, data: bytes):
        with open(path, 'xb') as stream:  # CREATE_NEW, like the DLL's own files
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def publish_request(self, values) -> tuple[int, bool]:
        seq = self.next_sequence()
        self._create(self.directory / f'companion-request-{seq}.json',
                     request_text(self.identity, seq, values).encode('ascii'))
        return seq, bool(self.poster(REQUEST_MESSAGE, seq))

    def publish_model(self, frame: bytes) -> tuple[int, bool]:
        seq = self.next_sequence()
        self._create(self.directory / f'companion-model-{seq}.bin', frame)
        posted = bool(self.poster(MODEL_MESSAGE, seq))
        if posted:
            self._models.add(seq)
        return seq, posted

    def read_model_failures(self):
        """Read matching DLL results once; retain files and retry partial writes."""
        failed = []
        for seq in tuple(self._models):
            try:
                result = json.loads((self.directory / f'companion-result-{seq}.json').read_text(
                    encoding='utf-8'))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if (not isinstance(result, dict) or result.get('schema') != 'own-companion-result-v1'
                    or result.get('seq') != seq or result.get('command') != 'model-apply'
                    or any(result.get(key) != value for key, value in self.identity.items())):
                continue
            self._models.remove(seq)
            status = str(result.get('status', '')).upper()
            window = str(result.get('window_state', '')).upper()
            if ('FAILED' in window or 'FAILED' in status or status.startswith(('REFUSED', 'ERROR'))
                    or status.startswith('MODEL_') and status not in
                    ('MODEL_APPLIED', 'MODEL_APPLIED_NATIVE_UNBOUND')):
                failed.append(seq)
        return failed


def _window_poster(pid):
    """PostMessageW to the visible top-level window of the game process."""
    def post(message_name, seq):
        import ctypes as C
        from ctypes import wintypes as W
        user = C.WinDLL('user32', use_last_error=True)
        user.RegisterWindowMessageW.argtypes, user.RegisterWindowMessageW.restype = (W.LPCWSTR,), W.UINT
        user.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        user.PostMessageW.restype = W.BOOL
        user.GetWindowThreadProcessId.argtypes = (W.HWND, C.POINTER(W.DWORD))
        user.IsWindowVisible.argtypes = (W.HWND,)
        message = user.RegisterWindowMessageW(message_name)
        if not 0xC000 <= message <= 0xFFFF:
            return False
        found = []
        callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        def each(hwnd, _):
            owner = W.DWORD()
            user.GetWindowThreadProcessId(hwnd, C.byref(owner))
            if owner.value == pid and user.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True
        user.EnumWindows(callback(each), 0)
        return bool(found) and bool(user.PostMessageW(found[0], message, seq, 0))
    return post
