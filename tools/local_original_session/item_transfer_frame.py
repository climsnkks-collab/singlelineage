"""One pending entry claim using the exact supported original monotonic clock.

The supported CPython Windows backend is GetTickCount64; no alternate clock.
Native establishes each original consumer owner before claim. The word is not a Scene token.
Claimed cancellation is consumed and blocks later callbacks, without undoing one already begun.
"""
import ctypes as C
from ctypes import wintypes as W
import os
import hashlib
from pathlib import Path
import secrets
import time

PENDING, CLAIMED, CANCELLED, CLAIMED_CANCELLED = range(4)
MAGIC = 0x46524531
ATOMIC_SHA256 = '6fe7d38e7d1a4f017d7f6fd7055b98f90fe67cea0ce13608aa42280124369d90'


class Header(C.Structure):
    _fields_ = [('state', C.c_long), ('magic', W.DWORD), ('version', W.DWORD),
        ('size', W.DWORD), ('pid', W.DWORD), ('seq', W.DWORD),
        ('birth', C.c_uint64), ('player', C.c_uint64), ('anchor', C.c_uint64),
        ('payload', C.c_uint64), ('quantity', C.c_uint64), ('map', C.c_int32),
        ('kind', W.DWORD), ('host_pid', W.DWORD), ('clock_id', W.DWORD),
        ('host_birth', C.c_uint64), ('started', C.c_uint64), ('window', C.c_uint64),
        ('candidate', C.c_char * 65), ('token', C.c_char * 33)]


def _api():
    k = C.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateFileMappingW': ([W.HANDLE, C.c_void_p, W.DWORD, W.DWORD, W.DWORD, W.LPCWSTR], W.HANDLE),
        'MapViewOfFile': ([W.HANDLE, W.DWORD, W.DWORD, W.DWORD, C.c_size_t], C.c_void_p),
        'UnmapViewOfFile': ([C.c_void_p], W.BOOL),
        'CloseHandle': ([W.HANDLE], W.BOOL),
        'GetCurrentProcess': ([], W.HANDLE),
        'GetProcessTimes': ([W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)], W.BOOL),
    }
    for name, (args, result) in signatures.items():
        fn = getattr(k, name); fn.argtypes = args; fn.restype = result
    path = Path(__file__).with_name('entry-frame-atomic.dll')
    _need(hashlib.sha256(path.read_bytes()).hexdigest() == ATOMIC_SHA256, 'ENTRY_FRAME_ATOMIC_PIN')
    atomic = C.WinDLL(str(path.resolve()), use_last_error=True)
    cas = atomic.FrameCompareExchange
    cas.argtypes = [C.POINTER(C.c_long), C.c_long, C.c_long]; cas.restype = C.c_long
    k._frame_atomic = atomic; k.FrameCompareExchange = cas
    return k


def _need(value, name):
    if not value:
        raise ValueError(name)


def supported_clock(clock):
    info = time.get_clock_info('monotonic')
    _need(clock is time.monotonic_ns and info.implementation == 'GetTickCount64()'
          and info.monotonic is True and info.adjustable is False, 'ENTRY_FRAME_EXACT_ORIGINAL_CLOCK')


class FrameClaim:
    def __init__(self, row, started, window, clock):
        _need(type(started) is int and type(window) is int and started > 0 and window > 0,
              'ENTRY_FRAME_ORIGINAL_WINDOW')
        supported_clock(clock)
        _need(started % 1000000 == 0 and window % 1000000 == 0, 'ENTRY_FRAME_TICK_INTEGER')
        self.k = _api(); self.handles = []; self.address = None; self.header = None
        self.token = secrets.token_hex(16)
        self.prefix = 'Local\\LC-EntryFrame-v1-' + self.token
        try:
            self.mapping = self._new(self.k.CreateFileMappingW(C.c_void_p(-1), None,
                4, 0, C.sizeof(Header), self.prefix + '-map'))
            self.address = self.k.MapViewOfFile(self.mapping, 2 | 4, 0, 0, C.sizeof(Header))
            _need(self.address, 'ENTRY_FRAME_MAP')
            self.header = Header.from_address(self.address)
            _need(C.sizeof(C.c_long)==4 and self.address % C.alignment(C.c_long)==0,
                  'ENTRY_FRAME_WORD_ALIGNMENT')
            times = [W.FILETIME() for _ in range(4)]
            _need(self.k.GetProcessTimes(self.k.GetCurrentProcess(), *(C.byref(t) for t in times)),
                  'ENTRY_FRAME_HOST_BIRTH')
            h = self.header
            h.magic = MAGIC; h.version = 1; h.clock_id = 1; h.size = C.sizeof(Header)
            h.pid = row['pid']; h.seq = row['seq']; h.birth = row['birth']
            h.player = row['player_uid']; h.anchor = row['anchor_inventory_uid']
            h.payload = row['payload_uid']; h.quantity = row['quantity']
            h.map = row['map_id']; h.kind = row['kind']; h.host_pid = os.getpid()
            h.host_birth = times[0].dwLowDateTime | (times[0].dwHighDateTime << 32)
            h.started = started; h.window = window
            h.candidate = row['candidate_sha256'].encode('ascii'); h.token = self.token.encode('ascii')
        except BaseException:
            self.close()
            raise

    def _new(self, handle):
        error = C.get_last_error()
        if handle:
            self.handles.append(handle)
        _need(handle and error != 183, 'ENTRY_FRAME_CREATE_NEW')
        return handle

    def _cas(self, desired, expected):
        _need(self.header is not None, 'ENTRY_FRAME_CLOSED')
        word = C.cast(self.address, C.POINTER(C.c_long))
        return self.k.FrameCompareExchange(word, desired, expected)

    def state(self):
        return self._cas(PENDING, PENDING)

    def cancel(self):
        if self.header is None:
            return None
        while True:
            state = self.state()
            if state in (CANCELLED, CLAIMED_CANCELLED):
                break
            _need(state in (PENDING, CLAIMED), 'ENTRY_FRAME_STATE_UNKNOWN')
            desired = CANCELLED if state == PENDING else CLAIMED_CANCELLED
            if self._cas(desired, state) == state:
                state = desired
                break
        # Claimed cancellation remains consumed, never returns to Pending.
        # It can block a later callback in the same operation, not undo one begun.
        return state

    def close(self):
        if self.address:
            try:
                self.cancel()
            except BaseException:
                pass  # Cleanup cannot revive an uncertain/terminal pending claim.
            finally:
                self.header = None
                self.k.UnmapViewOfFile(self.address); self.address = None
        for handle in reversed(self.handles):
            self.k.CloseHandle(handle)
        self.handles.clear()
