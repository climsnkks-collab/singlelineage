"""Owned-clone, one aligned 4-byte write watch. Import performs no Win32 calls.

Reuses the existing observer's aligned CONTEXT and DebugAPI bindings only;
its original-client run/source/anchors are never invoked. No code writes/hooks.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
import threading
import time
import types

ROOT = Path(__file__).resolve().parents[2]
OBSERVER_SHA = '57c9568b2ea38a018d27afe92b4f4ed88183a4d0a67d86395f9f94b658ca85ec'
IMAGE_SHA = '8b9e2628286c295adf71bf3c0cb0882164aeaa7d63b97f50c46114b53650b684'
API = 'ChangeDisplaySettingsA'
CONTINUE, NOT_HANDLED = 0x10002, 0x80010001
DR_OFFSETS = (72, 80, 88, 96, 104, 112)
MAX_HITS, MAX_THREADS, MAX_EVENTS = 8, 256, 16384
READY_PHASES = ('ATTACH_REPLAY_DRAINED_WAITING_TARGET', 'ATTACH_REPLAY_DRAINED_ARMED')
STORE_CANDIDATE_SHA = 'fd213053ddd497bdd3c5052b1d47866b1b1aa386920c4b61ba5126f462d3c90b'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def observer_parts():
    path = ROOT / 'tools/local_public_login_debug_observer/win32.py'
    need(hashlib.sha256(path.read_bytes()).hexdigest() == OBSERVER_SHA,
         'ENTRY_WATCH_OBSERVER_CHANGED')
    spec = importlib.util.spec_from_file_location('_owned_entry_watch_parts', path)
    module = importlib.util.module_from_spec(spec)
    # win32.py imports source but only Collector's unused original-client
    # methods consume it. Do not import/run that original-client contract.
    previous = sys.modules.get('source')
    sys.modules['source'] = types.SimpleNamespace(need=need)
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop('source', None)
        else:
            sys.modules['source'] = previous
    return module


PARTS = observer_parts()
Context = PARTS.Context


def saved_dr(context):
    return tuple(context.get64(offset) for offset in DR_OFFSETS)


def arm_context(context, address):
    need(type(address) is int and 0x10000 <= address < 0x7fffffffffff and address % 4 == 0,
         'ENTRY_WATCH_ALIGNED_4B_REQUIRED')
    saved = saved_dr(context)
    # Refuse disabled-but-populated registers too. DR7 bit10 is fixed/reserved;
    # DR6 reserved bits are preserved, active breakpoint/BD/BS/BT bits refused.
    need(not any(saved[:4]) and saved[4] & 0xe00f == 0 and saved[5] & ~0x400 == 0,
         'ENTRY_WATCH_EXISTING_DR_REFUSED')
    context.put64(72, address)
    context.put64(112, saved[5] | 0xd0001)  # L0=1, RW0=01(write), LEN0=11(4B)
    context.put32(48, 0x100010)
    return saved


def owned_context(context, address, saved):
    need(context.get64(72) == address and
         tuple(context.get64(p) for p in (80, 88, 96)) == saved[1:4] and
         (context.get64(112) ^ (saved[5] | 0xd0001)) & ~0x400 == 0,
         'ENTRY_WATCH_OWNED_DR_CHANGED')


def parse_pe(raw, wanted=()):
    """Bounded PE64 export lookup from the debug event's retained file handle."""
    def u16(offset): return struct.unpack_from('<H', raw, offset)[0]
    def u32(offset): return struct.unpack_from('<I', raw, offset)[0]
    need(64 <= len(raw) <= 64 * 1024 * 1024 and raw[:2] == b'MZ', 'ENTRY_WATCH_PE_UNKNOWN')
    nt = u32(60)
    need(64 <= nt <= 4096 and nt + 264 <= len(raw) and raw[nt:nt+4] == b'PE\0\0'
         and u16(nt+4) == 0x8664 and u16(nt+24) == 0x20b, 'ENTRY_WATCH_PE64_REQUIRED')
    count, optional = u16(nt+6), u16(nt+20)
    need(0 < count <= 96 and optional >= 240, 'ENTRY_WATCH_PE_SECTION_BOUND')
    size, headers = u32(nt+80), u32(nt+84)
    need(4096 <= size <= 0x40000000 and headers <= len(raw), 'ENTRY_WATCH_PE_SIZE_UNKNOWN')
    sections = []
    for index in range(count):
        at = nt + 24 + optional + 40 * index
        need(at+40 <= len(raw), 'ENTRY_WATCH_PE_SECTIONS_SHORT')
        sections.append((u32(at+12), u32(at+8), u32(at+20), u32(at+16)))
    def off(rva, length):
        if rva < headers:
            need(rva+length <= headers, 'ENTRY_WATCH_PE_HEADER_SPAN')
            return rva
        for va, virtual, disk, length_disk in sections:
            if va <= rva and rva+length <= va + length_disk:
                result = disk+rva-va
                need(result+length <= len(raw), 'ENTRY_WATCH_PE_FILE_SPAN')
                return result
        raise ValueError('ENTRY_WATCH_PE_RVA_UNKNOWN')
    result = dict(size=size, headers=((0, raw[:64]), (nt, raw[nt:nt+264])), exports={})
    if not wanted:
        return result
    export_rva, export_size = u32(nt+136), u32(nt+140)
    export = off(export_rva, 40)
    functions, names = u32(export+20), u32(export+24)
    need(0 < functions <= 65536 and names <= 65536, 'ENTRY_WATCH_PE_EXPORT_BOUND')
    function_rva, name_rva, ordinal_rva = u32(export+28), u32(export+32), u32(export+36)
    for index in range(names):
        name_entry = name_rva + 4*index
        rva = u32(off(name_entry, 4))
        start = off(rva, 1)
        end = raw.find(b'\0', start, min(start+128, len(raw)))
        if end < 0:
            continue
        name = raw[start:end].decode('ascii', errors='replace')
        if name not in wanted:
            continue
        ordinal_entry = ordinal_rva + 2*index
        ordinal = u16(off(ordinal_entry, 2))
        need(ordinal < functions, 'ENTRY_WATCH_PE_ORDINAL_UNKNOWN')
        function_entry = function_rva + 4*ordinal
        target = u32(off(function_entry, 4))
        need(0 < target < size and not export_rva <= target < export_rva+export_size,
             'ENTRY_WATCH_FORWARDED_EXPORT_REFUSED')
        checks = [(export_rva, raw[export:export+40]),
                  (name_entry, raw[off(name_entry, 4):off(name_entry, 4)+4]),
                  (rva, raw[start:end+1]),
                  (ordinal_entry, raw[off(ordinal_entry, 2):off(ordinal_entry, 2)+2]),
                  (function_entry, raw[off(function_entry, 4):off(function_entry, 4)+4])]
        result['exports'][name] = (target, checks)
    need(set(wanted) <= result['exports'].keys(), 'ENTRY_WATCH_EXPORT_ABSENT')
    return result


def loaded_header_equal(expected, observed, allocation_base, *, nt_header=False):
    """Exact bytes, or exactly the loader's fresh PE64 ImageBase relocation.

    NT signature(4)+COFF(20)+PE32+ ImageBase offset(24) = offset48.
    This is an alternative complete-header comparison, not a masked compare.
    """
    if observed == expected:
        return True
    if not nt_header or len(expected) != 264 or len(observed) != 264:
        return False
    if expected[:4] != b'PE\0\0' or struct.unpack_from('<H', expected, 24)[0] != 0x20b:
        return False
    if type(allocation_base) is not int or not 0x10000 <= allocation_base < 0x7fffffffffff:
        return False
    relocated = bytearray(expected)
    struct.pack_into('<Q', relocated, 48, allocation_base)
    return observed == bytes(relocated)


class MBI(C.Structure):
    _fields_ = [('base', C.c_void_p), ('allocation', C.c_void_p),
                ('allocation_protect', W.DWORD), ('partition', W.WORD), ('padding', W.WORD),
                ('size', C.c_size_t), ('state', W.DWORD), ('protect', W.DWORD), ('type', W.DWORD)]


class Win32Backend(PARTS.Collector):
    """DebugAPI methods stay on one attaching/debugging thread."""
    def __init__(self, owner):
        self.owner = owner
        self.expected = dict(pid=owner.child.pid, birth=str(owner.child.identity['birth']),
                             image_sha256=owner.image_sha)
        native = types.SimpleNamespace(k=owner.native.k, expected=self.expected)
        super().__init__(native)
        self.process = owner.owner_handle
        self.requested = 0
        bindings = {
            'ReadProcessMemory': ((W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)), W.BOOL),
            'VirtualQueryEx': ((W.HANDLE, C.c_void_p, C.POINTER(MBI), C.c_size_t), C.c_size_t),
            'GetExitCodeThread': ((W.HANDLE, C.POINTER(W.DWORD)), W.BOOL),
            'GetFileInformationByHandle': ((W.HANDLE, C.c_void_p), W.BOOL),
            'GetFileSizeEx': ((W.HANDLE, C.POINTER(C.c_longlong)), W.BOOL),
            'SetFilePointerEx': ((W.HANDLE, C.c_longlong, C.c_void_p, W.DWORD), W.BOOL),
            'ReadFile': ((W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p), W.BOOL),
            'GetFinalPathNameByHandleW': ((W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD), W.DWORD),
            'K32GetMappedFileNameW': ((W.HANDLE, C.c_void_p, W.LPWSTR, W.DWORD), W.DWORD),
        }
        for name, (args, result) in bindings.items():
            fn = getattr(self.k, name); fn.argtypes = args; fn.restype = result

    def validate(self, expected):
        owner, child = self.owner, self.owner.child
        need(not owner.closed and child is not None and owner.owner_handle == child.process
             and owner.owner_job == child.job and owner.owner_job and owner.key_guard(),
             'ENTRY_WATCH_RETAINED_OWNER_REQUIRED')
        owner.verify_sources()
        need(self.k.GetProcessId(child.process) == expected['pid'] == child.pid
             and owner.image_sha == expected['image_sha256'] == IMAGE_SHA,
             'ENTRY_WATCH_FRESH_PID_IMAGE_MISMATCH')
        times = [owner._filetime_type() for _ in range(4)]
        self.call('GetProcessTimes', child.process, *(C.byref(x) for x in times))
        birth = str(times[0].high << 32 | times[0].low)
        need(birth == expected['birth'] == str(child.identity['birth']),
             'ENTRY_WATCH_FRESH_BIRTH_MISMATCH')

    def attach(self):
        self.call('DebugActiveProcess', self.pid)

    def no_kill(self): self.call('DebugSetProcessKillOnExit', False)
    def detach(self): self.call('DebugActiveProcessStop', self.pid)

    def wait(self):
        event = C.create_string_buffer(176)
        C.set_last_error(0)
        if not self.k.WaitForDebugEventEx(event, 50):
            need(C.get_last_error() == 121, 'ENTRY_WATCH_WAIT_FAILED')
            return None
        raw = event.raw
        code, pid, tid = struct.unpack_from('<III', raw)
        row = dict(code=code, pid=pid, tid=tid)
        if code == 3:
            row.update(file=struct.unpack_from('<Q', raw, 16)[0],
                       thread=struct.unpack_from('<Q', raw, 32)[0], base=struct.unpack_from('<Q', raw, 40)[0])
        elif code == 2: row['thread'] = struct.unpack_from('<Q', raw, 16)[0]
        elif code == 6:
            row.update(file=struct.unpack_from('<Q', raw, 16)[0], base=struct.unpack_from('<Q', raw, 24)[0])
        elif code == 7: row['base'] = struct.unpack_from('<Q', raw, 16)[0]
        elif code == 1:
            row.update(exception=struct.unpack_from('<I', raw, 16)[0],
                       address=struct.unpack_from('<Q', raw, 32)[0],
                       first_chance=bool(struct.unpack_from('<I', raw, 168)[0]))
        return row

    def continue_event(self, event, status):
        self.call('ContinueDebugEvent', event['pid'], event['tid'], status)

    def duplicate_thread(self, handle):
        need(self.k.GetProcessIdOfThread(handle) == self.pid, 'ENTRY_WATCH_THREAD_OWNER_MISMATCH')
        result = W.HANDLE(); current = self.k.GetCurrentProcess()
        self.call('DuplicateHandle', current, handle, current, C.byref(result), 0x10005a, False, 0)
        return result

    def close_handle(self, handle): self.call('CloseHandle', handle)
    def context(self, handle):
        result = Context(); self.call('GetThreadContext', handle, result.ptr()); return result
    def set_context(self, handle, context): self.call('SetThreadContext', handle, context.ptr())
    def thread_alive(self, handle):
        code = W.DWORD(); self.call('GetExitCodeThread', handle, C.byref(code)); return code.value == 259
    def suspend(self, handle):
        need(self.k.SuspendThread(handle) != 0xffffffff, 'ENTRY_WATCH_SUSPEND_FAILED')
    def resume_thread(self, handle):
        need(self.k.ResumeThread(handle) != 0xffffffff, 'ENTRY_WATCH_RESTORE_RESUME_FAILED')

    def region(self, address, length=1):
        info = MBI()
        need(0x10000 <= address < 0x7fffffffffff and 0 < length <= 4096,
             'ENTRY_WATCH_READ_BOUND')
        need(self.k.VirtualQueryEx(self.process, address, C.byref(info), C.sizeof(info)) == C.sizeof(info)
             and info.base <= address and address+length <= info.base+info.size,
             'ENTRY_WATCH_REGION_UNKNOWN')
        return info

    def read(self, address, length):
        need(self.requested+length <= 4*1024*1024, 'ENTRY_WATCH_READ_QUOTA')
        self.requested += length
        info = self.region(address, length)
        need(info.state == 0x1000 and not info.protect & 0x100
             and info.protect & 0xff in (2, 4, 8, 0x20, 0x40, 0x80), 'ENTRY_WATCH_READ_UNAVAILABLE')
        data = C.create_string_buffer(length); received = C.c_size_t()
        self.call('ReadProcessMemory', self.process, address, data, length, C.byref(received))
        need(received.value == length, 'ENTRY_WATCH_READ_SHORT')
        return data.raw

    def module(self, event):
        base, handle = event['base'], event['file']
        required = False
        initial_required = getattr(self, 'initial_break', True)
        target_base = getattr(self, 'target_base', None)
        user32_required = target_base is None or base == target_base
        try:
            mapped = C.create_unicode_buffer(32768)
            length = self.k.K32GetMappedFileNameW(self.process, base, mapped, len(mapped))
            name = Path(mapped.value).name.lower() if 0 < length < len(mapped) else None
            required = (name == 'user32.dll' and user32_required) or (name == 'ntdll.dll' and initial_required)
            if not handle:
                need(not required, 'ENTRY_WATCH_SYSTEM_FILE_IDENTITY_UNKNOWN')
                return None
            final = C.create_unicode_buffer(32768)
            length = self.k.GetFinalPathNameByHandleW(handle, final, len(final), 2)  # VOLUME_NAME_NT
            need(0 < length < len(final), 'ENTRY_WATCH_MODULE_FILE_UNKNOWN')
            filename = Path(final.value).name.lower()
            # Either observed name selects the strict boundary. A mismatch may
            # not downgrade a required system module to optional classification.
            required = required or (filename == 'user32.dll' and user32_required) or (filename == 'ntdll.dll' and initial_required)
            need(mapped.value.casefold() == final.value.casefold() and name == filename
                 and re.fullmatch(r'[a-z0-9_.-]{1,80}', filename),
                 'ENTRY_WATCH_MAPPED_FILE_MISMATCH')
            before = C.create_string_buffer(52)
            self.call('GetFileInformationByHandle', handle, before)
            size = C.c_longlong(); self.call('GetFileSizeEx', handle, C.byref(size))
            need(64 <= size.value and (not required or size.value <= 64*1024*1024),
                 'ENTRY_WATCH_MODULE_FILE_BOUND')

            def file_read(offset, length):
                need(0 <= offset and offset+length <= size.value, 'ENTRY_WATCH_MODULE_FILE_SHORT')
                self.call('SetFilePointerEx', handle, offset, None, 0)
                buffer = C.create_string_buffer(length); count = W.DWORD()
                self.call('ReadFile', handle, buffer, length, C.byref(count), None)
                need(count.value == length, 'ENTRY_WATCH_MODULE_FILE_SHORT')
                return buffer.raw

            if required:
                chunks = bytearray()
                while len(chunks) < size.value:
                    chunks.extend(file_read(len(chunks), min(1048576, size.value-len(chunks))))
                wanted = (API,) if filename == 'user32.dll' else ('DbgBreakPoint',)
                pe = parse_pe(bytes(chunks), wanted)
            else:
                # Optional writer classification reads exactly 64+264 file
                # bytes, even for large graphics/SDK images. No full-file hash,
                # section bodies, export table or 64MiB size refusal is needed.
                dos = file_read(0, 64)
                need(dos[:2] == b'MZ', 'ENTRY_WATCH_OPTIONAL_PE_UNKNOWN')
                nt = struct.unpack_from('<I', dos, 60)[0]
                need(64 <= nt <= 4096, 'ENTRY_WATCH_OPTIONAL_PE_UNKNOWN')
                header = file_read(nt, 264)
                need(header[:4] == b'PE\0\0' and struct.unpack_from('<H', header, 4)[0] == 0x8664
                     and struct.unpack_from('<H', header, 20)[0] >= 240
                     and struct.unpack_from('<H', header, 24)[0] == 0x20b,
                     'ENTRY_WATCH_OPTIONAL_PE_UNKNOWN')
                image_size = struct.unpack_from('<I', header, 80)[0]
                need(4096 <= image_size <= 0x40000000, 'ENTRY_WATCH_OPTIONAL_PE_UNKNOWN')
                pe = dict(size=image_size, headers=((0, dos), (nt, header)), exports={})

            after = C.create_string_buffer(52); self.call('GetFileInformationByHandle', handle, after)
            # Access time can change through reads; file object identity may not.
            identity = lambda b: b[:12]+b[20:]
            need(identity(before.raw) == identity(after.raw), 'ENTRY_WATCH_MODULE_FILE_CHANGED')
            info = self.region(base)
            need(info.type == 0x1000000 and info.allocation == base, 'ENTRY_WATCH_MODULE_ALLOCATION_UNKNOWN')
            # Required exports and optional headers are compared to this loaded
            # allocation, never a local module address or historical RVA.
            for rva, expected in pe['headers']:
                if not loaded_header_equal(expected, self.read(base+rva, len(expected)), base, nt_header=rva != 0):
                    self.header_failure = dict(role='TARGET_USER32' if filename == 'user32.dll' and required else
                        'INITIAL_NTDLL' if required else 'OPTIONAL', stage='NT' if rva else 'DOS',
                        existing_target_allocation=(base == target_base) if target_base is not None else None)
                    raise ValueError('ENTRY_WATCH_LOADED_HEADER_MISMATCH')
            exports = {}
            for symbol, (rva, checks) in pe['exports'].items():
                for at, expected in checks:
                    need(self.read(base+at, len(expected)) == expected, 'ENTRY_WATCH_LOADED_EXPORT_MISMATCH')
                entry = self.region(base+rva, 4)
                need(entry.type == 0x1000000 and entry.allocation == base and entry.state == 0x1000
                     and entry.protect & 0xff in (0x10, 0x20, 0x40, 0x80)
                     and not entry.protect & 0x100, 'ENTRY_WATCH_EXECUTABLE_ENTRY_REQUIRED')
                exports[symbol] = rva
            result = dict(base=base, size=pe['size'], name=filename, exports=exports,
                          file_identity_sha256=hashlib.sha256(identity(after.raw)).hexdigest())
            if required:
                result['file_sha256'] = hashlib.sha256(chunks).hexdigest()
            return result
        except Exception:
            if required:
                raise
            # Unsupported/unavailable optional images remain UNKNOWN when an
            # address is classified; they cannot stop the one-entry watch.
            return None

    def classify(self, address, modules):
        try:
            info = self.region(address)
            kind = {0x1000000: 'MEM_IMAGE', 0x20000: 'MEM_PRIVATE', 0x40000: 'MEM_MAPPED'}.get(info.type, 'UNKNOWN')
            if kind == 'MEM_IMAGE' and info.state == 0x1000 and not info.protect & 0x100 and info.protect & 0xff in (0x10, 0x20, 0x40, 0x80):
                for module in modules.values():
                    if module['base'] == info.allocation and module['base'] <= address < module['base']+module['size']:
                        return dict(type=kind, module=module['name'], rva=address-module['base'])
            return dict(type=kind, module='UNKNOWN', rva=None)
        except Exception:
            return dict(type='UNKNOWN', module='UNKNOWN', rva=None)


class Watch:
    def __init__(self, backend, expected, directory):
        self.b, self.expected, self.directory = backend, dict(expected), Path(directory)
        self.threads, self.modules, self.rows = {}, {}, []
        self.address = None
        self.initial_break = True
        self.created = False
        self.attached = False
        self.exited = False
        self.pending = None
        self.events = 0
        self.ready, self.stop, self.done = threading.Event(), threading.Event(), threading.Event()
        self.ready_phase = 'NOT_ATTACHED'
        self.target_armed_at_ready = False
        self.dr_mismatch_metadata_attempted = False
        self.writer_fragment_attempted = False
        self.watch_bind_entry4 = None
        self.failure = None
        self.cleanup = dict(restored=False, detached=False, handles_closed=False, errors=[])
        self.thread = None
        self.stream = None

    def start(self):
        self.thread = threading.Thread(target=self.run, name='owned-entry-write-watch', daemon=False)
        self.thread.start()
        need(self.ready.wait(10), 'ENTRY_WATCH_ATTACH_TIMEOUT')
        need(self.attached and self.failure is None, 'ENTRY_WATCH_ATTACH_FAILED')
        need(self.ready_phase in READY_PHASES and not self.done.is_set(),
             'ENTRY_WATCH_DRAINED_READY_REQUIRED')
        # Does not wait for the initial breakpoint: primary is still suspended.

    def ready_after_idle(self):
        """Only an idle Wait result after replay continuation opens resume."""
        if self.ready.is_set() or self.stop.is_set():
            return
        ntdll = [module for module in self.modules.values() if module['name'] == 'ntdll.dll']
        if (self.pending is not None or not self.created or not self.threads
                or (self.initial_break and (len(ntdll) != 1 or 'DbgBreakPoint' not in ntdll[0]['exports']))):
            return
        if self.address is None:
            if any(record['saved'] is not None for record in self.threads.values()):
                return
            phase = 'ATTACH_REPLAY_DRAINED_WAITING_TARGET'
        else:
            if not all(record['saved'] is not None for record in self.threads.values()):
                return
            phase = 'ATTACH_REPLAY_DRAINED_ARMED'
        self.b.validate(self.expected)
        self.target_armed_at_ready = self.address is not None
        self.ready_phase = phase
        self.ready.set()

    def finish(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(10)
            need(not self.thread.is_alive(), 'ENTRY_WATCH_CLEANUP_TIMEOUT')
        need(not self.cleanup['errors'], 'ENTRY_WATCH_CLEANUP_UNKNOWN')

    def emit(self, row):
        raw = json.dumps(row, separators=(',', ':'), ensure_ascii=True)
        need(len(raw) <= 4096 and self.stream.tell()+len(raw)+1 <= 49152,
             'ENTRY_WATCH_METADATA_BOUND')
        self.stream.write(raw+'\n'); self.stream.flush()

    def arm(self, record):
        if self.address is None or record['saved'] is not None:
            return
        context = self.b.context(record['handle'])
        saved = arm_context(context, self.address)
        # Mark before SetThreadContext: even a failing call may partially alter
        # state; cleanup verifies the actual context before restoring anything.
        record['saved'] = saved
        self.b.set_context(record['handle'], context)

    def writer_fragment(self, ip, row, stack_pointer=None):
        if self.writer_fragment_attempted: return None
        self.writer_fragment_attempted = True
        meta = dict(status='UNKNOWN', source_basename='UNKNOWN', byte_count=0, sha256='UNKNOWN',
                    post_ip_offset=None, allocation_offset=None, prefix_count=0, prefix_status='UNKNOWN', readsEqual=None,
                    scope='MEMORY_SNAPSHOT_NOT_PE_RVA_OR_EXECUTION_BYTES_OR_STORE_PROOF')
        meta.update(name_query_success=False, name_stable=False, backing_name_sha256='UNKNOWN',
                    phase='PREVIOUS_PAGE_FOR_KNOWN_DIRECT_EDGE')
        def mapped_name():
            try:
                buffer = C.create_unicode_buffer(32768)
                count = self.b.k.K32GetMappedFileNameW(self.b.process, ip, buffer, len(buffer))
                return buffer.value if 0 < count < len(buffer) else None
            except Exception: return None
        path, created = self.directory/'writer-source-01.bin', False
        try:
            event = self.pending[0] if self.pending else {}
            need(event.get('code') == 1 and event.get('exception') == 0x80000004
                 and event.get('pid') == self.expected['pid'] and event.get('tid') == row['thread_id'],
                 'ENTRY_WATCH_FRAGMENT_EVENT_REQUIRED')
            self.b.validate(self.expected)
            name_before = mapped_name()
            page = ip & ~4095; allocation = self.b.region(ip, 1).allocation
            need(type(allocation) is int and 0 < allocation <= page-4096, 'ENTRY_WATCH_FRAGMENT_ALLOCATION_UNKNOWN')
            def checked(address, length):
                region = self.b.region(address, length)
                need(region.type == 0x40000 and region.state == 0x1000 and region.allocation == allocation
                     and not region.protect & 0x100 and region.protect & 0xff in (0x10, 0x20, 0x40, 0x80),
                     'ENTRY_WATCH_FRAGMENT_REGION_UNKNOWN')
            checked(ip, 1); checked(page, 4096); checked(page-4096, 4096)
            first, second = self.b.read(page, 4096), self.b.read(page, 4096)
            meta['readsEqual'] = first == second
            need(meta['readsEqual'], 'ENTRY_WATCH_FRAGMENT_CHANGED')
            prefix, repeated = self.b.read(page-4096, 4096), self.b.read(page-4096, 4096)
            meta['readsEqual'] = prefix == repeated
            need(meta['readsEqual'], 'ENTRY_WATCH_FRAGMENT_PREFIX_CHANGED')
            checked(ip, 1); checked(page, 4096); checked(page-4096, 4096)
            meta['prefix_status'] = 'COMPLETE'
            name_after = mapped_name()
            stable = bool(name_before and name_after and name_before.casefold() == name_after.casefold())
            meta.update(name_query_success=bool(name_before and name_after), name_stable=stable)
            if stable:
                basename = Path(name_before).name
                meta.update(source_basename=basename if re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', basename) else 'UNKNOWN',
                            backing_name_sha256=hashlib.sha256(name_before.casefold().encode('utf-16le', 'surrogatepass')).hexdigest())
            self.b.validate(self.expected)
            data = prefix+first
            with path.open('xb') as stream:
                created = True
                need(stream.write(data) == len(data), 'ENTRY_WATCH_FRAGMENT_WRITE_SHORT')
            meta.update(status='SNAPSHOT', file_basename=path.name, byte_count=len(data),
                        sha256=hashlib.sha256(data).hexdigest(), post_ip_offset=len(prefix)+ip-page,
                        allocation_offset=page-len(prefix)-allocation, prefix_count=len(prefix))
        except Exception:
            if created:
                try: path.unlink()
                except Exception: pass
        if meta['status'] == 'SNAPSHOT':
            row['writer_targets'] = self.writer_targets(page-4096, allocation, row, meta['sha256'], stack_pointer)
        return meta

    def writer_targets(self, start, allocation, row, source_sha, stack_pointer=None):
        result = dict(status='UNKNOWN', file_basename='UNKNOWN', byte_count=0, sha256='UNKNOWN')
        source_known = source_sha == '4e25546ed10c6e41cf751835fbfe6f0f8dcad20f1828e1d77df30ba7e988e22f'
        document = dict(source_carrier_sha256=source_sha, pid=self.expected['pid'], birth=self.expected['birth'],
                        thread_id=row['thread_id'], hit=row['hit'], monotonic_ns=row['monotonic_ns'], targets=[])
        def checked(page, regions=True):
            self.b.validate(self.expected)
            event = self.pending[0] if self.pending else {}
            need(event.get('code') == 1 and event.get('exception') == 0x80000004
                 and event.get('pid') == self.expected['pid'] and event.get('tid') == row['thread_id'], 'ENTRY_WATCH_TARGET_EVENT_UNKNOWN')
            if not regions: return
            for address, length in ((start, 1), (page, 4096)):
                region = self.b.region(address, length)
                need(region.type == 0x40000 and region.state == 0x1000 and region.allocation == allocation
                     and allocation > 0 and not region.protect & 0x100
                     and region.protect & 0xff in (0x10, 0x20, 0x40, 0x80), 'ENTRY_WATCH_TARGET_REGION_UNKNOWN')
        def write_closed(path, data):
            created = False
            try:
                with path.open('xb') as stream:
                    created = True
                    need(stream.write(data) == len(data), 'ENTRY_WATCH_TARGET_WRITE_SHORT')
            except Exception:
                if created:
                    try: path.unlink()
                    except Exception: pass
                raise
        try:
            for label, offset, name in (('POTENTIAL_CALLEE', 82464, 'writer-target-call-01.bin'),
                                        ('NORMAL_RETURN_ASSUMED_CONTINUATION', 9462682, 'writer-target-continuation-02.bin')):
                target = dict(label=label, status='UNKNOWN' if source_known else 'UNKNOWN_SOURCE_LAYOUT',
                              file_basename='UNKNOWN', byte_count=0, sha256='UNKNOWN',
                              allocation_page_offset=None, target_file_offset=None, type='UNKNOWN', module='UNKNOWN', rva=None)
                document['targets'].append(target)  # One attempt per fixed target, including failures.
                if not source_known: continue
                try:
                    address = start+offset; page = address & ~4095
                    checked(page, False)
                    try:
                        kind = self.b.classify(address, self.modules)
                        target.update(type=kind['type'], module=kind['module'] if re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', kind['module']) else 'UNKNOWN', rva=kind['rva'])
                    except Exception: pass
                    need(0 < allocation <= page <= (1 << 64)-4096, 'ENTRY_WATCH_TARGET_RANGE_UNKNOWN')
                    checked(page)
                    data, repeated = self.b.read(page, 4096), self.b.read(page, 4096)
                    need(len(data) == 4096 and data == repeated, 'ENTRY_WATCH_TARGET_CHANGED')
                    checked(page)
                    write_closed(self.directory/name, data)
                    target.update(status='SNAPSHOT', file_basename=name, byte_count=len(data),
                                  sha256=hashlib.sha256(data).hexdigest(), allocation_page_offset=page-allocation,
                                  target_file_offset=address-page)
                except Exception: pass
            frame = dict(status='UNKNOWN', scope='CONDITIONAL_FRAME_CLASSIFICATION_NOT_UNWIND_OR_PROVEN_RETURN', byte_count=0, slot_count=0, slots=[])
            document['frame'] = frame
            if source_known and stack_pointer is not None:
                try:
                    checked(start)
                    before = self.b.region(stack_pointer, 1)
                    def stack_ok(region):
                        return region.type == 0x20000 and region.state == 0x1000 and region.allocation > 0 and not region.protect & 0x100 and region.protect & 0xff in (2, 4, 8, 0x20, 0x40, 0x80)
                    length = min(1024, before.base+before.size-stack_pointer) & ~7
                    need(stack_ok(before) and before.base <= stack_pointer and length >= 360, 'ENTRY_WATCH_FRAME_REGION_UNKNOWN')
                    raw, repeated = self.b.read(stack_pointer, length), self.b.read(stack_pointer, length)
                    after = self.b.region(stack_pointer, length)
                    need(len(raw) == length and raw == repeated and stack_ok(after) and after.allocation == before.allocation
                         and after.base == before.base and after.size == before.size, 'ENTRY_WATCH_FRAME_CHANGED')
                    checked(start)
                    for index in range(length//8):
                        slot = dict(slot_index=index, stack_byte_offset=index*8, type='UNKNOWN', module='UNKNOWN', rva=None, allocation_relative_offset=None)
                        try:
                            value = struct.unpack_from('<Q', raw, index*8)[0]; kind = self.b.classify(value, self.modules)
                            slot.update(type=kind['type'], module=kind['module'] if re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', kind['module']) else 'UNKNOWN', rva=kind['rva'])
                            if kind['type'] == 'MEM_MAPPED':
                                region = self.b.region(value, 1)
                                if region.type == 0x40000 and region.state == 0x1000 and region.allocation == allocation and value >= allocation: slot['allocation_relative_offset'] = value-allocation
                        except Exception: pass
                        frame['slots'].append(slot)
                    frame.update(status='CLASSIFIED', byte_count=length, slot_count=length//8)
                except Exception: pass
            data = json.dumps(document, separators=(',', ':'), ensure_ascii=True).encode('ascii')
            need(len(data) <= 32768, 'ENTRY_WATCH_TARGET_METADATA_BOUND')
            path = self.directory/'writer-targets.json'
            write_closed(path, data)
            result.update(status='METADATA_SAVED' if source_known else 'UNKNOWN_SOURCE_LAYOUT',
                          file_basename=path.name, byte_count=len(data), sha256=hashlib.sha256(data).hexdigest())
        except Exception: pass
        return result

    def post_context_effect(self, context):
        meta = dict(scope='CONDITIONAL_POST_CONTEXT_OPERAND_EFFECT_NOT_EXECUTION_BOUNDARY_PROOF',
                    baseline_phase='FIRST_STRICT_TARGET_BIND_BEFORE_ARM', target_read='UNKNOWN',
                    target_entry4_sha256='UNKNOWN', equals_watch_bind_entry4=None, source_candidate_hash_match=None,
                    source_binding='UNKNOWN', operand_in_watch=None, watch_offset=None, al_equals_current_byte=None)
        try:
            target = self.b.region(self.address, 4)
            need(target.type == 0x1000000 and target.state == 0x1000 and target.allocation == self.target_base,
                 'ENTRY_WATCH_EFFECT_TARGET_UNKNOWN')
            current = self.b.read(self.address, 4)
            meta.update(target_read='OBSERVED', target_entry4_sha256=hashlib.sha256(current).hexdigest(),
                        equals_watch_bind_entry4=(current == self.watch_bind_entry4) if self.watch_bind_entry4 is not None else None)
            ip = context.get64(248); source, code = self.b.region(ip, 1), self.b.region(ip-3, 3)
            need(source.allocation and source.allocation == code.allocation and all(
                 r.type == 0x40000 and r.state == 0x1000 and not r.protect & 0x100
                 and r.protect & 0xff in (0x10, 0x20, 0x40, 0x80) for r in (source, code)), 'ENTRY_WATCH_EFFECT_SOURCE_UNKNOWN')
            meta['source_binding'] = 'SAME_PENDING_EVENT_SAME_FRESH_MEM_MAPPED_ALLOCATION'
            meta['source_candidate_hash_match'] = hashlib.sha256(self.b.read(ip-3, 3)).hexdigest() == STORE_CANDIDATE_SHA
            if meta['source_candidate_hash_match']:
                operand = (context.get64(136)+context.get64(128)) & ((1 << 64)-1)
                meta['operand_in_watch'] = self.address <= operand < self.address+4
                if meta['operand_in_watch']:
                    offset = operand-self.address
                    meta.update(watch_offset=offset, al_equals_current_byte=(context.get64(120) & 255) == current[offset])
        except Exception: pass
        return meta

    def add_thread(self, event):
        tid = event['tid']
        need(tid not in self.threads and len(self.threads) < MAX_THREADS, 'ENTRY_WATCH_THREAD_BOUND')
        handle = self.b.duplicate_thread(event['thread'])
        record = dict(handle=handle, saved=None)
        self.threads[tid] = record
        self.arm(record)

    def exception(self, event):
        code = event['exception']
        if code == 0x80000003 and self.initial_break and self.created and event['first_chance']:
            ntdll = [m for m in self.modules.values() if m['name'] == 'ntdll.dll']
            if len(ntdll) == 1 and event['address'] == ntdll[0]['base']+ntdll[0]['exports']['DbgBreakPoint']:
                self.initial_break = False
                return CONTINUE
        record = self.threads.get(event['tid'])
        if code != 0x80000004 or record is None or record['saved'] is None:
            return NOT_HANDLED
        context = self.b.context(record['handle'])
        status = context.get64(104)
        if not status & 1:
            return NOT_HANDLED
        try:
            owned_context(context, self.address, record['saved'])
        except ValueError:
            if not self.dr_mismatch_metadata_attempted:
                self.dr_mismatch_metadata_attempted = True
                try:
                    self.b.validate(self.expected)
                    expected_dr = (self.address, *record['saved'][1:4])
                    self.emit(dict(schema='owned-entry-dr-mismatch-v1', pid=self.expected['pid'],
                        birth=self.expected['birth'], image_sha256=self.expected['image_sha256'],
                        thread_id=event['tid'], monotonic_ns=time.monotonic_ns(),
                        Dr0_3_equal=[context.get64(off) == value for off, value in zip(DR_OFFSETS[:4], expected_dr)],
                        Dr7Xor=context.get64(112) ^ (record['saved'][5] | 0xd0001),
                        activeDr6CauseBits=status & 0xe00f, phase='OWNED_CONTEXT_CHECK', ready_phase=self.ready_phase))
                except Exception:
                    pass  # Keep the original ownership failure if identity/output is unavailable.
            raise
        # Only after register ownership is verified may an owned continuation
        # survive a later metadata failure. Other causes remain unhandled.
        continuation = NOT_HANDLED if status & 0xe00e else CONTINUE
        self.pending = (event, continuation)
        self.b.validate(self.expected)
        module = self.modules[self.target_base]
        row = dict(schema='owned-entry-write-hit-v1', pid=self.expected['pid'],
                   birth=self.expected['birth'], image_sha256=self.expected['image_sha256'],
                   thread_id=event['tid'], monotonic_ns=time.monotonic_ns(), utc_ns=time.time_ns(),
                   api=API, watch_module=module['name'], watch_rva=self.address-self.target_base,
                   watch_size=4, watch_file_sha256=module['file_sha256'],
                   watch_file_identity_sha256=module['file_identity_sha256'],
                   hit=len(self.rows)+1, trap_position='AFTER_WRITE_NOT_WRITING_INSTRUCTION',
                   ready_phase=self.ready_phase,
                   ready_scope='DEBUG_ATTACH_REPLAY_ONLY_NOT_TARGET_COVERAGE',
                   target_armed_at_ready=self.target_armed_at_ready,
                   trap=self.b.classify(context.get64(248), self.modules),
                   stack_candidates=[], stack_scope='UP_TO_64B_SCAN_NOT_UNWIND_OR_PROVEN_CALLER')
        first_mapped = row['trap']['type'] == 'MEM_MAPPED' and not self.writer_fragment_attempted
        if row['trap']['type'] == 'MEM_MAPPED':
            row['post_context_effect'] = self.post_context_effect(context)
            fragment = self.writer_fragment(context.get64(248), row, context.get64(152))
            if fragment is not None: row['writer_fragment'] = fragment
        stack, classified = None, {}
        try:
            stack = self.b.read(context.get64(152), 64)
            for index in range(8):
                candidate = self.b.classify(struct.unpack_from('<Q', stack, index*8)[0], self.modules)
                classified[index] = candidate
                if candidate['type'] == 'MEM_IMAGE' and candidate['module'] != 'UNKNOWN' and candidate not in row['stack_candidates']:
                    row['stack_candidates'].append(candidate)
                if len(row['stack_candidates']) == 3:
                    break
        except Exception:
            row['stack_status'] = 'UNKNOWN'
        if first_mapped:
            row['stack_slots'] = []
            row['stack_slots_scope'] = 'CLASSIFIED_WORDS_NOT_UNWIND_OR_PROVEN_RETURN'
            source = None
            try:
                source = self.b.region(context.get64(248), 1)
                need(source.type == 0x40000 and source.state == 0x1000 and source.allocation > 0
                     and not source.protect & 0x100 and source.protect & 0xff in (0x10, 0x20, 0x40, 0x80), 'ENTRY_WATCH_STACK_SOURCE_UNKNOWN')
            except Exception: source = None
            for index in range(8):
                slot = dict(slot_index=index, stack_byte_offset=index*8, type='UNKNOWN', module='UNKNOWN', rva=None)
                try:
                    value = struct.unpack_from('<Q', stack, index*8)[0]
                    candidate = classified[index] if index in classified else self.b.classify(value, self.modules)
                    slot.update(type=candidate['type'], module=candidate['module'] if re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', candidate['module']) else 'UNKNOWN', rva=candidate['rva'])
                    if slot['type'] == 'MEM_MAPPED':
                        slot.update(same_source_allocation=None, allocation_relative_offset=None)
                        region = self.b.region(value, 1)
                        same = (region.allocation == source.allocation and value >= source.allocation) if source is not None and region.type == 0x40000 and region.state == 0x1000 and region.allocation > 0 else None
                        slot.update(same_source_allocation=same, allocation_relative_offset=value-source.allocation if same else None)
                except Exception: pass
                row['stack_slots'].append(slot)
        self.rows.append(row); self.emit(row)
        context.put64(104, status & ~1)  # Clear only our slot. No RF for data BP.
        context.put32(48, 0x100010)
        self.b.set_context(record['handle'], context)
        return continuation

    def event(self, event):
        try:
            return self._event(event)
        finally:
            if event['code'] in (3, 6) and event.get('file'):
                handle, event['file'] = event['file'], 0
                self.b.close_handle(handle)

    def _event(self, event):
        need(event['pid'] == self.expected['pid'], 'ENTRY_WATCH_FOREIGN_PID')
        code = event['code']
        if code in (2, 3):
            self.add_thread(event)
            if code == 3:
                need(not self.created, 'ENTRY_WATCH_DUPLICATE_PROCESS_EVENT')
                self.created = True
        if code in (3, 6):
            self.b.initial_break = self.initial_break
            self.b.target_base = getattr(self, 'target_base', None)
            module = self.b.module(event)
            if module:
                need(len(self.modules) < 512 and module['base'] not in self.modules,
                     'ENTRY_WATCH_MODULE_BOUND')
                self.modules[module['base']] = module
                if module['name'] == 'user32.dll' and (self.address is None or module['base'] == self.target_base):
                    need(self.address is None, 'ENTRY_WATCH_DUPLICATE_USER32')
                    self.target_base = module['base']
                    self.address = module['base']+module['exports'][API]
                    need(self.address % 4 == 0, 'ENTRY_WATCH_ALIGNED_4B_REQUIRED')
                    try: self.watch_bind_entry4 = self.b.read(self.address, 4)
                    except Exception: pass  # First-bind failure stays UNKNOWN; no backfill.
                    for record in self.threads.values(): self.arm(record)
        elif code == 7:
            need(event['base'] != getattr(self, 'target_base', None), 'ENTRY_WATCH_USER32_UNLOADED')
            self.modules.pop(event['base'], None)
        elif code == 4:
            record = self.threads.pop(event['tid'], None)
            if record: self.b.close_handle(record['handle'])
        elif code == 5: self.exited = True
        elif code == 1: return self.exception(event)
        return CONTINUE

    def restore(self):
        errors = []
        for record in self.threads.values():
            saved = record['saved']
            if saved is None:
                continue
            suspended = False
            try:
                if self.exited or not self.b.thread_alive(record['handle']):
                    record['saved'] = None
                    continue
                if self.pending is None:
                    self.b.suspend(record['handle']); suspended = True
                context = self.b.context(record['handle'])
                current = saved_dr(context)
                if current == saved:  # Failed arm left it unchanged.
                    record['saved'] = None
                    continue
                owned_context(context, self.address, saved)
                for offset, value in zip(DR_OFFSETS, saved):
                    # Preserve newly observed foreign DR6 causes, including a
                    # mixed trap which must still reach the debuggee.
                    context.put64(offset, (context.get64(104) & ~1) | (value & 1)
                                  if offset == 104 else value)
                context.put32(48, 0x100010)
                self.b.set_context(record['handle'], context)
                record['saved'] = None
            except Exception:
                errors.append('DR_RESTORE_UNKNOWN')
            finally:
                if suspended:
                    try: self.b.resume_thread(record['handle'])
                    except Exception: errors.append('RESTORE_RESUME_UNKNOWN')
        self.cleanup['restored'] = not errors
        self.cleanup['errors'].extend(errors)

    def run(self):
        try:
            self.stream = (self.directory / 'entry-write-watch.jsonl').open('x', encoding='utf-8')
            self.b.validate(self.expected)
            self.b.attach(); self.attached = True
            self.b.no_kill()
            self.b.validate(self.expected)
            self.ready_phase = 'ATTACH_REPLAY_PENDING'
            while not self.stop.is_set() and not self.exited and len(self.rows) < MAX_HITS:
                event = self.b.wait()
                if event is None:
                    self.ready_after_idle()
                    continue
                self.pending = (event, NOT_HANDLED if event['code'] == 1 else CONTINUE)
                self.events += 1
                need(self.events <= MAX_EVENTS, 'ENTRY_WATCH_EVENT_BOUND')
                continuation = self.event(event)
                self.pending = (event, continuation)
                if self.exited or len(self.rows) == MAX_HITS:
                    self.restore()
                self.b.continue_event(event, continuation); self.pending = None
        except Exception as error:
            self.failure = type(error).__name__
            if isinstance(error, ValueError) and len(error.args) == 1 and re.fullmatch(r'ENTRY_WATCH_[A-Z0-9_]+', str(error.args[0])):
                self.failure = error.args[0]
        finally:
            if self.pending:
                event = self.pending[0]
                if event['code'] in (3, 6) and event.get('file'):
                    handle, event['file'] = event['file'], 0
                    try: self.b.close_handle(handle)
                    except Exception: self.cleanup['errors'].append('EVENT_FILE_CLOSE_UNKNOWN')
            self.restore()
            if self.pending:
                try: self.b.continue_event(*self.pending); self.pending = None
                except Exception: self.cleanup['errors'].append('CONTINUE_UNKNOWN')
            if self.attached:
                try:
                    self.b.detach(); self.cleanup['detached'] = True; self.attached = False
                except Exception: self.cleanup['errors'].append('DETACH_UNKNOWN')
            for record in self.threads.values():
                try: self.b.close_handle(record['handle'])
                except Exception: self.cleanup['errors'].append('HANDLE_CLOSE_UNKNOWN')
            self.threads.clear()
            self.cleanup['handles_closed'] = not any(x == 'HANDLE_CLOSE_UNKNOWN' for x in self.cleanup['errors'])
            if self.stream:
                try:
                    self.emit(dict(schema='owned-entry-write-summary-v1', hit_count=len(self.rows),
                                   api=API, bound=MAX_HITS, initial_system_break_consumed=not self.initial_break,
                                   fresh_target_bound=self.address is not None, failure=self.failure,
                                   ready_phase=self.ready_phase,
                                   ready_scope='DEBUG_ATTACH_REPLAY_ONLY_NOT_TARGET_COVERAGE',
                                   target_armed_at_ready=self.target_armed_at_ready,
                                   header_failure=getattr(self.b, 'header_failure', None),
                                   cleanup=self.cleanup, single_writer_proven=False,
                                   limitations=['only_one_aligned_4B', 'external_process_or_kernel_write_may_be_missed',
                                                'thread_or_address_coverage_gaps_possible', 'debugger_affects_timing',
                                                'self_Detours_writes_not_filtered', 'trap_is_after_write']))
                except Exception: self.cleanup['errors'].append('SUMMARY_WRITE_UNKNOWN')
                try: self.stream.close()
                except Exception: self.cleanup['errors'].append('OUTPUT_CLOSE_UNKNOWN')
            self.ready.set(); self.done.set()


@contextmanager
def installed(launcher, directory, factory=Win32Backend):
    """Narrow lifecycle wrapper; tick forwards an ended observer's failure only."""
    original_resume, original_close = launcher.NativeOwner.resume, launcher.NativeOwner.close
    original_tick = launcher.NativeOwner.tick
    watches = {}

    def resume(owner):
        need(owner.internal and owner.product in known_products(launcher)
             and owner.image_sha == IMAGE_SHA, 'ENTRY_WATCH_EXACT_INTERNAL_PRODUCT_REQUIRED')
        need(owner not in watches, 'ENTRY_WATCH_SINGLE_RESUME_REQUIRED')
        expected = dict(pid=owner.child.pid, birth=str(owner.child.identity['birth']), image_sha256=owner.image_sha)
        watch = Watch(factory(owner), expected, directory)
        watches[owner] = watch
        watch.start()
        return original_resume(owner)

    def close(owner):
        error = None
        try:
            if owner in watches:
                try: watches.pop(owner).finish()
                except Exception as failure: error = failure
        finally:
            result = original_close(owner)
        if error: raise error
        return result

    def tick(owner):
        alive = original_tick(owner)
        watch = watches.get(owner)
        if alive and watch is not None and watch.done.is_set():
            need(watch.failure is None and not watch.cleanup['errors'], 'ENTRY_WATCH_RUNTIME_FAILURE')
        return alive

    launcher.NativeOwner.resume, launcher.NativeOwner.close = resume, close
    launcher.NativeOwner.tick = tick
    try:
        yield
    finally:
        try:
            for owner in tuple(watches): close(owner)
        finally:
            launcher.NativeOwner.resume, launcher.NativeOwner.close = original_resume, original_close
            launcher.NativeOwner.tick = original_tick


def known_products(launcher):
    """Only pre-existing registered, pinned internal health/desktop profiles."""
    return tuple(name for name, spec in launcher.PRODUCTS.items()
                 if spec.get('internal_only') is True and spec.get('require_lifecycle_health') is True
                 and spec.get('background_display_guard') is True and spec.get('image_sha256') == IMAGE_SHA)
