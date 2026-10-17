"""Pure mocks only. Never instantiate Win32Backend or call a production API."""
import copy
import ctypes as C
import io
import json
from pathlib import Path
import struct
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from tools.local_original_session import entry_watch as e


EXPECTED = dict(pid=44, birth='123', image_sha256=e.IMAGE_SHA)
PRODUCTS = {'sibling-internal-lifecycle-details-spawn':
            dict(internal_only=True, require_lifecycle_health=True,
                 background_display_guard=True, image_sha256=e.IMAGE_SHA)}


def context():
    result = e.Context()
    result.put64(104, 0xffff0ff0)
    result.put64(112, 0x400)
    result.put64(248, 0x80100)
    result.put64(152, 0x90000)
    return result


def module(name='user32.dll', base=0x40000):
    exports = {e.API: 0x100} if name == 'user32.dll' else {'DbgBreakPoint': 0x200} if name == 'ntdll.dll' else {}
    return dict(name=name, base=base, size=0x10000, exports=exports,
                file_sha256='a'*64, file_identity_sha256='b'*64)


def event(code, tid=10, **extra):
    return dict(code=code, pid=44, tid=tid, **extra)


class Fake:
    def __init__(self, events=()):
        self.events = list(events)
        self.contexts = {10: context(), 11: context()}
        self.log = []
        self.identity = dict(EXPECTED)
        self.fail_attach = False
        self.fail_set = False
        self.fail_detach = False
        self.fail_restore = False
        self.w = None
    def validate(self, expected):
        e.need(expected == self.identity, 'ENTRY_WATCH_FRESH_BIRTH_MISMATCH')
        self.log.append('validate')
    def attach(self):
        self.log.append('attach')
        if self.fail_attach: raise ValueError('ENTRY_WATCH_ATTACH_FAILED')
    def no_kill(self): self.log.append('no_kill')
    def detach(self):
        self.log.append('detach')
        if self.fail_detach: raise RuntimeError('mock')
    def wait(self):
        if self.events: return self.events.pop(0)
        self.w.stop.set(); return None
    def continue_event(self, event, status): self.log.append(('continue', event['tid'], status))
    def duplicate_thread(self, handle): self.log.append(('duplicate', handle)); return handle
    def close_handle(self, handle): self.log.append(('close_handle', handle))
    def context(self, handle): return copy.deepcopy(self.contexts[handle])
    def set_context(self, handle, value):
        self.log.append(('set_context', handle, value.get64(112)))
        if self.fail_set: raise RuntimeError('mock')
        if self.fail_restore and value.get64(112) == 0x400: raise RuntimeError('mock')
        self.contexts[handle] = copy.deepcopy(value)
    def thread_alive(self, handle): return True
    def suspend(self, handle): self.log.append(('suspend', handle))
    def resume_thread(self, handle): self.log.append(('resume_thread', handle))
    def module(self, event): return module(**event.get('module', {}))
    def read(self, address, length):
        assert length <= 64
        return struct.pack('<8Q', *range(0x80100, 0x80140, 8))[:length]
    def classify(self, address, modules):
        return dict(type='MEM_IMAGE', module='writer.dll', rva=address-0x80000)


class PureWatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
    def watch(self, fake=None):
        fake = fake or Fake()
        result = e.Watch(fake, EXPECTED, self.directory)
        fake.w = result
        return result, fake
    def bound(self):
        watch, fake = self.watch()
        watch.stream = io.StringIO()
        watch.event(event(3, thread=10, file=71, base=0x40000))
        return watch, fake
    def run_watch(self, events, **flags):
        fake = Fake(events)
        for key, value in flags.items(): setattr(fake, key, value)
        watch, _ = self.watch(fake)
        watch.run()
        return watch, fake
    def test_context_aligned_x64(self):
        x = context()
        self.assertEqual(x.address % 16, 0)
        self.assertEqual(len(x.view), 1232)
    def test_write_four_byte_encoding_and_default_preserved(self):
        x = context(); before = e.saved_dr(x)
        self.assertEqual(e.arm_context(x, 0x40100), before)
        self.assertEqual(x.get64(112), 0xd0401)
        self.assertEqual((x.get64(112) >> 16) & 3, 1)  # RW write
        self.assertEqual((x.get64(112) >> 18) & 3, 3)  # LEN 4B, NOT 2 (=8B)
        self.assertEqual(x.get32(48), 0x100010)
        self.assertEqual(x.get64(248), 0x80100)
    def test_unaligned_refused(self):
        with self.assertRaisesRegex(ValueError, 'ALIGNED_4B'): e.arm_context(context(), 0x40101)
    def test_all_occupied_dr_refused(self):
        for offset, value in [(72, 3), (80, 4), (88, 5), (96, 6), (104, 0x2000), (112, 2), (112, 0x10000)]:
            with self.subTest(offset=offset, value=value):
                x = context(); x.put64(offset, x.get64(offset) | value)
                with self.assertRaisesRegex(ValueError, 'EXISTING_DR'): e.arm_context(x, 0x40100)
    def test_fresh_module_export_used_not_historical_rva(self):
        watch, fake = self.bound()
        self.assertEqual(watch.address, 0x40100)
        self.assertNotEqual(watch.address-0x40000, 0x4b220)
        self.assertEqual(fake.contexts[10].get64(72), 0x40100)
    def test_preexisting_and_created_thread_arming(self):
        watch, fake = self.watch()
        watch.event(event(2, tid=11, thread=11))
        self.assertEqual(fake.contexts[11].get64(72), 0)
        watch.event(event(3, thread=10, file=71, base=0x40000))
        self.assertEqual(fake.contexts[10].get64(72), 0x40100)
        self.assertEqual(fake.contexts[11].get64(72), 0x40100)
    def test_created_thread_after_load_arms(self):
        watch, fake = self.bound()
        watch.event(event(2, tid=11, thread=11))
        self.assertEqual(fake.contexts[11].get64(72), 0x40100)
    def test_foreign_pid_refused(self):
        watch, _ = self.watch()
        row = event(2, thread=11); row['pid'] = 45
        with self.assertRaisesRegex(ValueError, 'FOREIGN_PID'): watch.event(row)
    def test_foreign_exceptions_passthrough(self):
        watch, fake = self.bound()
        for code in (0xc0000005, 0x80000003, 0x80000004):
            self.assertEqual(watch.exception(event(1, exception=code, address=0x1000, first_chance=True)), e.NOT_HANDLED)
        self.assertEqual(watch.rows, [])
    def test_exact_initial_breakpoint_once_only(self):
        watch, _ = self.bound()
        watch.event(event(6, file=72, base=0x60000, module=dict(name='ntdll.dll', base=0x60000)))
        row = event(1, exception=0x80000003, address=0x60200, first_chance=False)
        self.assertEqual(watch.exception(row), e.NOT_HANDLED)
        row['first_chance'] = True
        self.assertEqual(watch.exception(row), e.CONTINUE)
        self.assertEqual(watch.exception(row), e.NOT_HANDLED)
    def test_own_dr6_clear_only_rip_flags_unchanged(self):
        watch, fake = self.bound()
        x = fake.contexts[10]; x.put64(104, x.get64(104) | 1); x.put32(68, 0x246)
        rip, flags = x.get64(248), x.get32(68)
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
        x = fake.contexts[10]
        self.assertEqual(x.get64(104), 0xffff0ff0)
        self.assertEqual((x.get64(248), x.get32(68)), (rip, flags))
        self.assertEqual(x.get32(48), 0x100010)
    def test_mixed_foreign_trap_passthrough_and_restore_preserves_foreign_bit(self):
        watch, fake = self.bound()
        fake.contexts[10].put64(104, 0xffff0ff3)
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.NOT_HANDLED)
        self.assertEqual(fake.contexts[10].get64(104), 0xffff0ff2)
        watch.restore()
        self.assertEqual(fake.contexts[10].get64(104), 0xffff0ff2)
        self.assertEqual(fake.contexts[10].get64(112), 0x400)
    def test_changed_owned_dr_not_claimed(self):
        watch, fake = self.bound()
        fake.contexts[10].put64(104, 0xffff0ff1)
        fake.contexts[10].put64(72, 0x40400)
        with self.assertRaisesRegex(ValueError, 'OWNED_DR_CHANGED'):
            watch.exception(event(1, exception=0x80000004))
        self.assertIsNone(watch.pending)
    def test_restores_all_threads_before_detach_then_handle_close(self):
        watch, fake = self.run_watch([event(3, thread=10, file=71, base=0x40000), event(2, tid=11, thread=11)])
        detach = fake.log.index('detach')
        for tid in (10, 11):
            self.assertLess(fake.log.index(('set_context', tid, 0x400)), detach)
            self.assertGreater(fake.log.index(('close_handle', tid)), detach)
        self.assertTrue(watch.cleanup['restored'])
        self.assertTrue(watch.cleanup['detached'])
    def test_initial_attach_failure_no_events_or_resume(self):
        watch, fake = self.watch()
        fake.fail_attach = True
        with self.assertRaisesRegex(ValueError, 'ATTACH_FAILED'): watch.start()
        watch.finish()
        self.assertNotIn('detach', fake.log)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == 'set_context' for x in fake.log))
    def test_fresh_birth_mismatch_prevents_attach(self):
        fake = Fake(); fake.identity['birth'] = '124'
        watch, _ = self.watch(fake); watch.run()
        self.assertEqual(watch.failure, 'ENTRY_WATCH_FRESH_BIRTH_MISMATCH')
        self.assertNotIn('attach', fake.log)
    def test_pid_mismatch_prevents_attach(self):
        fake = Fake(); fake.identity['pid'] = 99
        watch, _ = self.watch(fake); watch.run()
        self.assertNotIn('attach', fake.log)
    def test_created_thread_conflict_restores_previous_and_detaches(self):
        fake = Fake([event(3, thread=10, file=71, base=0x40000), event(2, tid=11, thread=11)])
        fake.contexts[11].put64(88, 0x50000)
        watch, _ = self.watch(fake); watch.run()
        self.assertEqual(watch.failure, 'ENTRY_WATCH_EXISTING_DR_REFUSED')
        self.assertEqual(fake.contexts[10].get64(112), 0x400)
        self.assertEqual(fake.contexts[11].get64(88), 0x50000)
        self.assertTrue(watch.cleanup['detached'])
    def test_max_eight_hits_bounded_metadata_no_addresses(self):
        fake = Fake([event(3, thread=10, file=71, base=0x40000)] + [event(1, exception=0x80000004)]*9)
        watch, _ = self.watch(fake)
        original_wait = fake.wait
        def wait():
            row = original_wait()
            if row and row['code'] == 1: fake.contexts[10].put64(104, 0xffff0ff1)
            return row
        fake.wait = wait
        watch.run()
        self.assertEqual(len(watch.rows), 8)
        self.assertEqual(len(fake.events), 1)
        raw = (self.directory / 'entry-write-watch.jsonl').read_text('utf-8')
        self.assertLess(len(raw), 49152)
        rows = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len(rows), 9)
        for row in rows[:-1]:
            self.assertEqual(len(row['stack_candidates']), 3)
            self.assertEqual(row['trap_position'], 'AFTER_WRITE_NOT_WRITING_INSTRUCTION')
            self.assertEqual(row['watch_rva'], 256)
            self.assertNotIn('address', row)
            self.assertNotIn('stack', row)
        self.assertNotIn('589824', raw)  # raw RSP
        self.assertFalse(rows[-1]['single_writer_proven'])
    def test_restore_failure_is_unknown_and_detach_still_attempted(self):
        watch, fake = self.run_watch([event(3, thread=10, file=71, base=0x40000)], fail_restore=True)
        self.assertIn('DR_RESTORE_UNKNOWN', watch.cleanup['errors'])
        self.assertIn('detach', fake.log)
    def test_detach_failure_unknown_and_handles_close_attempted(self):
        watch, fake = self.run_watch([event(3, thread=10, file=71, base=0x40000)], fail_detach=True)
        self.assertIn('DETACH_UNKNOWN', watch.cleanup['errors'])
        self.assertIn(('close_handle', 10), fake.log)
    def test_unload_target_refused(self):
        watch, _ = self.bound()
        with self.assertRaisesRegex(ValueError, 'USER32_UNLOADED'): watch.event(event(7, base=0x40000))


class Wrapper(unittest.TestCase):
    def test_attach_failure_never_calls_original_resume_and_close_runs(self):
        log = []
        class Owner:
            internal = True; product = 'sibling-internal-lifecycle-details-spawn'; image_sha = e.IMAGE_SHA
            child = types.SimpleNamespace(pid=44, identity=dict(birth='123'))
            def resume(self): log.append('original_resume')
            def close(self): log.append('owner_close'); return 42
            def tick(self): return True
        launcher = types.SimpleNamespace(NativeOwner=Owner, PRODUCTS=PRODUCTS)
        original_resume, original_close = Owner.resume, Owner.close
        class MockWatch:
            def __init__(self, *args): pass
            def start(self): log.append('attach'); raise ValueError('ENTRY_WATCH_ATTACH_FAILED')
            def finish(self): log.extend(['restore', 'detach', 'join'])
        with patch.object(e, 'Watch', MockWatch):
            with e.installed(launcher, '.', factory=lambda owner: None):
                owner = Owner()
                with self.assertRaises(ValueError): owner.resume()
                self.assertEqual(owner.close(), 42)
        self.assertEqual(log, ['attach', 'restore', 'detach', 'join', 'owner_close'])
        self.assertIs(Owner.resume, original_resume)
        self.assertIs(Owner.close, original_close)
    def test_success_ready_before_resume_no_initial_break_wait_and_exception_cleanup(self):
        log = []
        class Owner:
            internal = True; product = 'sibling-internal-lifecycle-details-spawn'; image_sha = e.IMAGE_SHA
            child = types.SimpleNamespace(pid=44, identity=dict(birth='123'))
            def resume(self): log.append('resume'); raise RuntimeError('resume failed')
            def close(self): log.append('close')
            def tick(self): return True
        class MockWatch:
            def __init__(self, *args): pass
            def start(self): log.append('attached_not_initial_break')
            def finish(self): log.extend(['restore', 'detach', 'join'])
        launcher = types.SimpleNamespace(NativeOwner=Owner, PRODUCTS=PRODUCTS)
        with patch.object(e, 'Watch', MockWatch):
            with self.assertRaises(RuntimeError):
                with e.installed(launcher, '.', factory=lambda owner: None): Owner().resume()
        self.assertEqual(log, ['attached_not_initial_break', 'resume', 'restore', 'detach', 'join', 'close'])
    def test_finish_failure_still_owner_close_and_patch_restore(self):
        log = []
        class Owner:
            internal = True; product = 'sibling-internal-lifecycle-details-spawn'; image_sha = e.IMAGE_SHA
            child = types.SimpleNamespace(pid=44, identity=dict(birth='123'))
            def resume(self): pass
            def close(self): log.append('close')
            def tick(self): return True
        class MockWatch:
            def __init__(self, *args): pass
            def start(self): pass
            def finish(self): log.append('finish'); raise ValueError('ENTRY_WATCH_CLEANUP_UNKNOWN')
        launcher = types.SimpleNamespace(NativeOwner=Owner, PRODUCTS=PRODUCTS)
        original = Owner.resume
        with patch.object(e, 'Watch', MockWatch):
            with self.assertRaisesRegex(ValueError, 'CLEANUP_UNKNOWN'):
                with e.installed(launcher, '.', factory=lambda owner: None): Owner().resume()
        self.assertEqual(log, ['finish', 'close'])
        self.assertIs(Owner.resume, original)
    def test_runtime_watch_failure_reaches_existing_session_cleanup(self):
        log = []
        class Owner:
            internal = True; product = 'sibling-internal-lifecycle-details-spawn'; image_sha = e.IMAGE_SHA
            child = types.SimpleNamespace(pid=44, identity=dict(birth='123'))
            def resume(self): log.append('resume')
            def close(self): log.append('close')
            alive = True
            def tick(self): log.append('tick'); return self.alive
        class MockWatch:
            def __init__(self, *args):
                self.done = threading.Event(); self.failure = None; self.cleanup = dict(errors=[])
            def start(self): self.done.set(); self.failure = 'ENTRY_WATCH_OWNED_DR_CHANGED'
            def finish(self): log.extend(['restore', 'detach', 'join'])
        launcher = types.SimpleNamespace(NativeOwner=Owner, PRODUCTS=PRODUCTS)
        original_tick = Owner.tick
        with patch.object(e, 'Watch', MockWatch):
            with e.installed(launcher, '.', factory=lambda owner: None):
                owner = Owner(); owner.resume()
                with self.assertRaisesRegex(ValueError, 'RUNTIME_FAILURE'): owner.tick()
                owner.alive = False
                self.assertFalse(owner.tick())  # Preserve existing native-exit meaning.
                owner.close()
        self.assertEqual(log, ['resume', 'tick', 'tick', 'restore', 'detach', 'join', 'close'])
        self.assertIs(Owner.tick, original_tick)


class NativeIdentityPure(unittest.TestCase):
    def make(self):
        class FT(C.Structure): _fields_ = [('low', C.c_uint32), ('high', C.c_uint32)]
        child = types.SimpleNamespace(pid=44, process=100, job=200, identity=dict(birth='123'))
        owner = types.SimpleNamespace(child=child, closed=False, owner_handle=100, owner_job=200,
                                      image_sha=e.IMAGE_SHA, _filetime_type=FT,
                                      key_guard=lambda: True, verify_sources=lambda: None)
        def call(name, handle, *times):
            self.assertEqual(name, 'GetProcessTimes')
            times[0]._obj.low = 123
        fake = types.SimpleNamespace(owner=owner, k=types.SimpleNamespace(GetProcessId=lambda handle: 44), call=call)
        return fake
    def test_retained_identity_validates(self):
        e.Win32Backend.validate(self.make(), EXPECTED)
    def test_current_pid_mismatch_refused(self):
        fake = self.make(); fake.k.GetProcessId = lambda handle: 45
        with self.assertRaisesRegex(ValueError, 'PID_IMAGE'): e.Win32Backend.validate(fake, EXPECTED)
    def test_current_birth_mismatch_refused(self):
        fake = self.make(); expected = dict(EXPECTED, birth='124')
        with self.assertRaisesRegex(ValueError, 'BIRTH_MISMATCH'): e.Win32Backend.validate(fake, expected)
    def test_owner_job_changed_refused(self):
        fake = self.make(); fake.owner.owner_job = 201
        with self.assertRaisesRegex(ValueError, 'RETAINED_OWNER'): e.Win32Backend.validate(fake, EXPECTED)


def tiny_pe():
    raw = bytearray(4096)
    raw[:2] = b'MZ'
    def put16(at, value): struct.pack_into('<H', raw, at, value)
    def put32(at, value): struct.pack_into('<I', raw, at, value)
    put32(60, 0x80); raw[0x80:0x84] = b'PE\0\0'
    put16(0x84, 0x8664); put16(0x86, 2); put16(0x94, 240); put16(0x98, 0x20b)
    put32(0xd0, 0x4000); put32(0xd4, 0x400)
    put32(0x108, 0x2000); put32(0x10c, 0x200)
    # .edata at RVA2000 -> file400, .text at RVA1000 -> fileA00.
    for at, va, disk in [(0x188, 0x2000, 0x400), (0x1b0, 0x1000, 0xa00)]:
        put32(at+8, 0x600); put32(at+12, va); put32(at+16, 0x600); put32(at+20, disk)
    put32(0x414, 1); put32(0x418, 1)
    put32(0x41c, 0x2050); put32(0x420, 0x2040); put32(0x424, 0x2060)
    put32(0x440, 0x2070); put32(0x450, 0x1000); put16(0x460, 0)
    name = (e.API+'\0').encode('ascii'); raw[0x470:0x470+len(name)] = name
    return bytes(raw)


class FreshModulePure(unittest.TestCase):
    def test_file_export_lookup_without_old_rva(self):
        pe = e.parse_pe(tiny_pe(), (e.API,))
        self.assertEqual(pe['exports'][e.API][0], 0x1000)
        self.assertEqual(pe['size'], 0x4000)
    def test_forwarded_export_refused(self):
        raw = bytearray(tiny_pe()); struct.pack_into('<I', raw, 0x450, 0x2080)
        with self.assertRaisesRegex(ValueError, 'FORWARDED_EXPORT'): e.parse_pe(raw, (e.API,))
    def test_missing_export_refused(self):
        with self.assertRaisesRegex(ValueError, 'EXPORT_ABSENT'): e.parse_pe(tiny_pe(), ('OtherAPI',))
    def make(self, filename='user32.dll', *, file_size=None, raw_override=None, mapped_filename=None):
        original = tiny_pe(); pe = e.parse_pe(original, (e.API,))
        raw = original if raw_override is None else raw_override
        path = '\\Device\\HarddiskVolume3\\Windows\\System32\\' + filename
        mapped_path = '\\Device\\HarddiskVolume3\\Windows\\System32\\' + (mapped_filename or filename)
        class Kernel:
            def K32GetMappedFileNameW(self, process, base, buffer, length):
                buffer.value = mapped_path; return len(mapped_path)
            def GetFinalPathNameByHandleW(self, handle, buffer, length, flags):
                assert flags == 2
                buffer.value = path; return len(path)
        memory = {}
        for rva, data in pe['headers'] + tuple(pe['exports'][e.API][1]):
            memory[0x40000+rva] = data
        state = dict(position=0)
        file_reads, memory_reads = [], []
        def call(name, *args):
            if name == 'GetFileSizeEx': args[1]._obj.value = len(raw) if file_size is None else file_size
            elif name == 'SetFilePointerEx': state['position'] = args[1]
            elif name == 'ReadFile':
                length = args[2]; start = state['position']
                data = raw[start:start+length]
                file_reads.append((start, length))
                C.memmove(args[1], data, len(data)); args[3]._obj.value = len(data)
                state['position'] += len(data)
            elif name == 'GetFileInformationByHandle':
                C.memmove(args[1], b'\0'*52, 52)
            else: raise AssertionError(name)
        def read(address, length):
            memory_reads.append(length)
            return memory[address]
        fake = types.SimpleNamespace(k=Kernel(), process=100, call=call,
                                     region=lambda address, length=1: types.SimpleNamespace(type=0x1000000, allocation=0x40000, state=0x1000, protect=0x20),
                                     read=read, memory=memory, file_reads=file_reads, memory_reads=memory_reads)
        return fake
    def test_fresh_file_memory_and_export_binding(self):
        module = e.Win32Backend.module(self.make(), event(6, file=71, base=0x40000))
        self.assertEqual(module['exports'][e.API], 0x1000)
        self.assertEqual(module['name'], 'user32.dll')
        self.assertEqual(len(module['file_identity_sha256']), 64)
    def test_loaded_export_mismatch_refused(self):
        fake = self.make(); fake.memory[0x42050] = b'\0'*4
        with self.assertRaisesRegex(ValueError, 'LOADED_EXPORT_MISMATCH'):
            e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
    def test_loaded_header_mismatch_refused(self):
        fake = self.make(); fake.memory[0x40000] = b'\0'*64
        with self.assertRaisesRegex(ValueError, 'LOADED_HEADER_MISMATCH'):
            e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
    def test_nonimage_entry_refused(self):
        fake = self.make()
        fake.region = lambda address, length=1: types.SimpleNamespace(type=0x20000, allocation=0x40000, state=0x1000, protect=0x20)
        with self.assertRaisesRegex(ValueError, 'MODULE_ALLOCATION_UNKNOWN'):
            e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
    def test_optional_large_file_reads_only_bounded_headers_without_full_hash(self):
        fake = self.make('graphics.dll', file_size=128*1024*1024)
        module = e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
        self.assertEqual(module['name'], 'graphics.dll')
        self.assertEqual(module['size'], 0x4000)
        self.assertEqual(module['exports'], {})
        self.assertNotIn('file_sha256', module)
        self.assertEqual(fake.file_reads, [(0, 64), (0x80, 264)])
        self.assertEqual(sum(fake.memory_reads), 328)
    def test_optional_unsupported_pe_is_unknown_not_watch_failure(self):
        raw = bytearray(tiny_pe()); struct.pack_into('<H', raw, 0x84, 0x14c)
        fake = self.make('graphics.dll', raw_override=bytes(raw))
        self.assertIsNone(e.Win32Backend.module(fake, event(6, file=71, base=0x40000)))
        self.assertEqual(sum(n for _, n in fake.file_reads), 328)
    def test_optional_unknown_file_identity_is_not_watch_failure(self):
        fake = self.make('graphics.dll', mapped_filename='different.dll')
        self.assertIsNone(e.Win32Backend.module(fake, event(6, file=71, base=0x40000)))
        self.assertEqual(fake.file_reads, [])
    def test_required_large_file_still_fail_closed(self):
        fake = self.make(file_size=128*1024*1024)
        with self.assertRaisesRegex(ValueError, 'MODULE_FILE_BOUND'):
            e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
        self.assertEqual(fake.file_reads, [])
    def test_required_name_cannot_downgrade_to_optional(self):
        for actual, mapped in [('graphics.dll', 'user32.dll'), ('ntdll.dll', 'graphics.dll')]:
            with self.subTest(actual=actual, mapped=mapped):
                fake = self.make(actual, mapped_filename=mapped)
                with self.assertRaisesRegex(ValueError, 'MAPPED_FILE_MISMATCH'):
                    e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
    def test_optional_unknown_still_closes_eventfile_and_continues(self):
        raw = bytearray(tiny_pe()); struct.pack_into('<H', raw, 0x84, 0x14c)
        native = self.make('graphics.dll', raw_override=bytes(raw))
        with tempfile.TemporaryDirectory() as directory:
            fake = Fake(); watch = e.Watch(fake, EXPECTED, directory)
            fake.module = lambda row: e.Win32Backend.module(native, row)
            self.assertEqual(watch.event(event(6, file=71, base=0x40000)), e.CONTINUE)
            self.assertEqual(watch.modules, {})
            self.assertIn(('close_handle', 71), fake.log)
    def test_eventfile_closed_if_thread_duplication_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Fake(); watch = e.Watch(fake, EXPECTED, directory)
            fake.duplicate_thread = lambda handle: (_ for _ in ()).throw(ValueError('ENTRY_WATCH_THREAD_OWNER_MISMATCH'))
            with self.assertRaises(ValueError): watch.event(event(3, thread=10, file=71, base=0x40000))
            self.assertIn(('close_handle', 71), fake.log)
    def test_only_known_registered_safe_profiles(self):
        specs = dict(PRODUCTS)
        specs['manual'] = dict(next(iter(PRODUCTS.values())), internal_only=False)
        specs['no_health'] = dict(next(iter(PRODUCTS.values())), require_lifecycle_health=False)
        specs['no_guard'] = dict(next(iter(PRODUCTS.values())), background_display_guard=False)
        specs['other_image'] = dict(next(iter(PRODUCTS.values())), image_sha256='0'*64)
        specs['new_reviewed'] = dict(next(iter(PRODUCTS.values())))
        actual = e.known_products(types.SimpleNamespace(PRODUCTS=specs))
        self.assertEqual(set(actual), {'sibling-internal-lifecycle-details-spawn', 'new_reviewed'})


class HeaderRelocationPure(unittest.TestCase):
    def header(self):
        raw = tiny_pe()
        return raw[0x80:0x80+264]
    def relocate(self, header, base):
        result = bytearray(header)
        struct.pack_into('<Q', result, 48, base)
        return bytes(result)
    def test_exact_file_header_still_allowed(self):
        header = self.header()
        self.assertTrue(e.loaded_header_equal(header, header, 0x40000, nt_header=True))
    def test_only_fresh_allocation_imagebase_allowed(self):
        header = self.header()
        self.assertTrue(e.loaded_header_equal(header, self.relocate(header, 0x40000),
                                              0x40000, nt_header=True))
    def test_other_imagebase_refused(self):
        header = self.header()
        self.assertFalse(e.loaded_header_equal(header, self.relocate(header, 0x50000),
                                               0x40000, nt_header=True))
    def test_every_other_header_byte_remains_exact(self):
        header = self.header()
        for offset in range(264):
            if 48 <= offset < 56:
                continue
            with self.subTest(offset=offset):
                changed = bytearray(self.relocate(header, 0x40000))
                changed[offset] ^= 1
                self.assertFalse(e.loaded_header_equal(header, bytes(changed), 0x40000, nt_header=True))
    def test_dos_header_has_no_relocation_alternative(self):
        header = tiny_pe()[:64]
        self.assertTrue(e.loaded_header_equal(header, header, 0x40000))
        self.assertFalse(e.loaded_header_equal(header, self.relocate(header, 0x40000), 0x40000))
    def test_required_and_optional_binding_accept_fresh_imagebase_only(self):
        for filename in ('user32.dll', 'graphics.dll'):
            with self.subTest(filename=filename):
                fake = FreshModulePure().make(filename)
                fake.memory[0x40080] = self.relocate(fake.memory[0x40080], 0x40000)
                module = e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
                self.assertEqual(module['name'], filename)
                self.assertEqual(module['base'], 0x40000)
    def test_required_wrong_imagebase_binding_refused(self):
        fake = FreshModulePure().make()
        fake.memory[0x40080] = self.relocate(fake.memory[0x40080], 0x50000)
        with self.assertRaisesRegex(ValueError, 'LOADED_HEADER_MISMATCH'):
            e.Win32Backend.module(fake, event(6, file=71, base=0x40000))
    def test_required_relocated_header_other_bit_binding_refused(self):
        fake = FreshModulePure().make()
        changed = bytearray(self.relocate(fake.memory[0x40080], 0x40000))
        changed[80] ^= 1  # SizeOfImage remains exact.
        fake.memory[0x40080] = bytes(changed)
        with self.assertRaisesRegex(ValueError, 'LOADED_HEADER_MISMATCH'):
            e.Win32Backend.module(fake, event(6, file=71, base=0x40000))


class NtdllRolePure(unittest.TestCase):
    def native(self, filename):
        if filename == 'user32.dll':
            return FreshModulePure().make()
        raw = bytearray(tiny_pe()); name = b'DbgBreakPoint\0'
        raw[0x470:0x470+len(name)] = name
        backend = FreshModulePure().make('ntdll.dll', raw_override=bytes(raw))
        pe = e.parse_pe(raw, ('DbgBreakPoint',))
        for rva, expected in pe['headers'] + tuple(pe['exports']['DbgBreakPoint'][1]):
            backend.memory[0x40000+rva] = expected
        return backend
    def test_initial_ntdll_strict_then_optional_and_user32_always_strict_with_header_role_stage(self):
        cases = [('ntdll.dll', True, 'INITIAL_NTDLL', 'DOS'),
                 ('ntdll.dll', False, 'OPTIONAL', 'DOS'),
                 ('user32.dll', True, 'TARGET_USER32', 'NT'),
                 ('user32.dll', False, 'TARGET_USER32', 'NT')]
        for filename, initial, role, stage in cases:
            with self.subTest(filename=filename, initial=initial):
                backend = self.native(filename); backend.initial_break = initial
                address = 0x40000 if stage == 'DOS' else 0x40080
                backend.memory[address] = b'\0'*len(backend.memory[address])
                if role == 'OPTIONAL':
                    self.assertIsNone(e.Win32Backend.module(backend, event(6, file=71, base=0x40000)))
                    self.assertEqual(backend.file_reads, [(0, 64), (0x80, 264)])
                else:
                    with self.assertRaisesRegex(ValueError, 'LOADED_HEADER_MISMATCH'):
                        e.Win32Backend.module(backend, event(6, file=71, base=0x40000))
                self.assertEqual(backend.header_failure, dict(role=role, stage=stage, existing_target_allocation=None))
    def test_only_exact_initial_closes_ntdll_ready_role_without_old_address_reuse_and_summary_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Fake(); watch = e.Watch(backend, EXPECTED, directory); backend.w = watch
            watch.event(event(3, thread=10, file=71, base=0x80000,
                              module=dict(name='lc.guard.exe', base=0x80000)))
            watch.ready_after_idle(); self.assertFalse(watch.ready.is_set())
            watch.event(event(6, file=72, base=0x60000, module=dict(name='ntdll.dll', base=0x60000)))
            self.assertTrue(backend.initial_break)
            wrong = event(1, exception=0x80000003, first_chance=True, address=0x60300)
            self.assertEqual(watch.exception(wrong), e.NOT_HANDLED)
            self.assertTrue(watch.initial_break)
            exact = dict(wrong, address=0x60200)
            self.assertEqual(watch.exception(exact), e.CONTINUE)
            self.assertFalse(watch.initial_break)
            watch.event(event(7, base=0x60000))  # No previous ntdll mapping remains.
            watch.ready_after_idle(); self.assertTrue(watch.ready.is_set())
            self.assertEqual(watch.ready_phase, 'ATTACH_REPLAY_DRAINED_WAITING_TARGET')
            def optional_mismatch(row):
                self.assertFalse(backend.initial_break)
                backend.header_failure = dict(role='OPTIONAL', stage='DOS')
                return None
            backend.module = optional_mismatch
            self.assertEqual(watch.event(event(6, file=73, base=0x70000)), e.CONTINUE)
            self.assertNotIn(0x60000, watch.modules)
            self.assertNotIn(0x70000, watch.modules)
            self.assertEqual(watch.exception(exact), e.NOT_HANDLED)  # No old address reuse.
            watch.run()
            raw = (Path(directory)/'entry-write-watch.jsonl').read_text('utf-8')
            self.assertLess(len(raw), 4096)
            summary = json.loads(raw)
            self.assertEqual(summary['header_failure'], dict(role='OPTIONAL', stage='DOS'))
            self.assertEqual(summary['hit_count'], 0)


class BackingNameEffectPure(unittest.TestCase):
    def make(self, mode='stable'):
        fragment = (e.ROOT/'work/local_original_session/runs/entry-write-watch-46/writer-source-01.bin').read_bytes()
        self.assertTrue(e.hashlib.sha256(fragment).hexdigest() == 'ada7f19a05ca315bc2479b856f8cde479bb7195ca784a5e2929589c2bf831786')
        candidate = fragment[15:18]
        self.assertTrue(e.hashlib.sha256(candidate).hexdigest() == e.STORE_CANDIDATE_SHA)
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        backend = Fake(); watch = e.Watch(backend, EXPECTED, temporary.name); watch.stream = io.StringIO()
        target = b'ABCD'; code = b'\0'*3 if mode == 'wrong_code' else candidate
        page = bytearray(b'p'*4096); page[15:18] = code
        calls, names = [], []
        path = r'\Device\Volume\CodeBacking.DLL'
        def name_query(process, address, buffer, length):
            names.append(1)
            if mode == 'name_failed': return 0
            value = path if mode != 'unsafe_name' else '\\Device\\Volume\\'+'x'*81
            buffer.value = value; return len(value)
        backend.k = types.SimpleNamespace(K32GetMappedFileNameW=name_query); backend.process = 101
        def region(address, length=1):
            if address == 0x40100 and length == 4:
                return types.SimpleNamespace(type=0x1000000, state=0x1000, allocation=0x40000, protect=0x20)
            allocation = 0x71000 if mode == 'other_source_allocation' and address == 0x8000f else 0x70000
            return types.SimpleNamespace(type=0x40000, state=0x1000, allocation=allocation, protect=0x20)
        def read(address, length):
            calls.append((address, length)); backend.log.append(('read', address, length))
            if address == 0x40100 and length == 4:
                number = sum(at == 0x40100 and n == 4 for at, n in calls)
                if mode == 'bind_failed' and number == 1: raise PermissionError('pure bind read failure')
                if mode == 'target_denied' and number > 1: raise PermissionError('pure target read failure')
                return target
            if address == 0x8000f and length == 3: return code
            if address in (0x7f000, 0x80000) and length == 4096: return bytes(page)
            if length == 64: return b'\0'*64
            raise ValueError('PURE_UNEXPECTED_READ')
        backend.region, backend.read = region, read
        backend.classify = lambda address, modules: dict(type='MEM_MAPPED', module='UNKNOWN', rva=None)
        watch.event(event(3, thread=10, file=71, base=0x1000000,
                          module=dict(name='lc.guard.exe', base=0x1000000)))
        watch.event(event(6, file=72, base=0x40000))
        ctx = backend.contexts[10]; ctx.put64(248, 0x80012); ctx.put64(104, 0xffff0ff1)
        ctx.put64(136, (1 << 64)-2); ctx.put64(128, 0x40106 if mode == 'outside' else 0x40104)
        ctx.put64(120, 68 if mode == 'al_differs' else 67)
        return watch, backend, calls, names, path, target
    def test_stable_safe_name_hash_and_wrapped_conditional_operand_match_bind_baseline(self):
        watch, backend, calls, names, path, target = self.make()
        self.assertLess(backend.log.index(('read', 0x40100, 4)),
                        next(i for i, row in enumerate(backend.log) if isinstance(row, tuple) and row[0] == 'set_context'))
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
        row = watch.rows[0]; fragment, effect = row['writer_fragment'], row['post_context_effect']
        self.assertEqual(fragment['source_basename'], 'CodeBacking.DLL')
        self.assertEqual(fragment['backing_name_sha256'], e.hashlib.sha256(path.casefold().encode('utf-16le')).hexdigest())
        self.assertTrue(fragment['name_stable'] and fragment['name_query_success'])
        self.assertEqual(len(names), 2)
        self.assertEqual(effect['baseline_phase'], 'FIRST_STRICT_TARGET_BIND_BEFORE_ARM')
        self.assertTrue(effect['equals_watch_bind_entry4'] and effect['source_candidate_hash_match'])
        self.assertEqual(effect['target_entry4_sha256'], e.hashlib.sha256(target).hexdigest())
        self.assertTrue(effect['operand_in_watch'] and effect['al_equals_current_byte'])
        self.assertEqual(effect['watch_offset'], 2)
        self.assertFalse(path in watch.stream.getvalue())
        self.assertEqual(backend.contexts[10].get64(104) & 1, 0)
    def test_name_fallback_and_operand_hash_allocation_range_read_or_bind_unknown_do_not_change_trap_flow(self):
        for mode in ('name_failed', 'unsafe_name', 'wrong_code', 'other_source_allocation',
                     'outside', 'al_differs', 'target_denied', 'bind_failed'):
            with self.subTest(mode=mode):
                watch, backend, calls, names, path, target = self.make(mode)
                self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
                fragment, effect = watch.rows[0]['writer_fragment'], watch.rows[0]['post_context_effect']
                self.assertEqual(fragment['status'], 'SNAPSHOT')
                if mode in ('name_failed', 'unsafe_name'): self.assertEqual(fragment['source_basename'], 'UNKNOWN')
                if mode == 'name_failed':
                    self.assertFalse(fragment['name_query_success']); self.assertEqual(fragment['backing_name_sha256'], 'UNKNOWN')
                if mode == 'wrong_code': self.assertFalse(effect['source_candidate_hash_match'])
                if mode == 'other_source_allocation': self.assertIsNone(effect['source_candidate_hash_match'])
                if mode in ('wrong_code', 'other_source_allocation', 'target_denied'):
                    self.assertIsNone(effect['operand_in_watch']); self.assertIsNone(effect['watch_offset'])
                if mode == 'outside':
                    self.assertFalse(effect['operand_in_watch']); self.assertIsNone(effect['al_equals_current_byte'])
                if mode == 'al_differs': self.assertFalse(effect['al_equals_current_byte'])
                if mode == 'target_denied': self.assertEqual(effect['target_read'], 'UNKNOWN')
                if mode == 'bind_failed':
                    self.assertIsNone(watch.watch_bind_entry4); self.assertIsNone(effect['equals_watch_bind_entry4'])
                self.assertFalse(path in watch.stream.getvalue())
                self.assertEqual(backend.contexts[10].get64(104) & 1, 0)


class WriterFragmentPure(unittest.TestCase):
    def make(self, mode='stable'):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name); backend = Fake(); watch = e.Watch(backend, EXPECTED, directory)
        watch.stream = io.StringIO(); watch.event(event(3, thread=10, file=71, base=0x40000))
        backend.contexts[10].put64(248, 0x80003)
        backend.contexts[10].put64(104, 0xffff0ff1)
        words = (0xa0100, 0xa0100, 0xa0200, 0xa0300, 0x7f123, 0xb0010, 0, 0xc0010)
        def classify(address, modules):
            if address == 0xc0010 and mode == 'unsafe_slot_name':
                return dict(type='MEM_IMAGE', module='\\Device\\Private\\'+'x'*81, rva=16)
            if address == 0xc0010 and mode == 'max_slot_name':
                return dict(type='MEM_IMAGE', module='x'*76+'.dll', rva=16)
            if address == 0xc0010: raise ValueError('PURE_CLASSIFICATION_UNKNOWN')
            if address in words[:4]: return dict(type='MEM_IMAGE', module='writer.dll', rva=address-0xa0000)
            return dict(type='MEM_MAPPED' if address else 'UNKNOWN', module='UNKNOWN', rva=None)
        backend.classify = classify
        calls, source_queries = [], []; page = bytes(range(256))*16; prefix = b'p'*4096
        def region(address, length=1):
            if address == 0x80003:
                source_queries.append(1)
                if mode == 'source_unknown' and len(source_queries) > 3: raise ValueError('PURE_SOURCE_UNKNOWN')
            if not address: raise ValueError('PURE_NULL_REGION')
            allocation = 0xb0000 if address == 0xb0010 else 0x70000
            if mode == 'other_allocation' and address == 0x7f000: allocation = 0x71000
            return types.SimpleNamespace(type=0x40000, state=0x1000, allocation=allocation, protect=0x20)
        def read(address, length):
            calls.append((address, length))
            if length == 4096:
                if mode == 'denied': raise PermissionError('pure read denied')
                data = page if address == 0x80000 else prefix
                count = sum(at == address and n == 4096 for at, n in calls)
                return b'x'+data[1:] if mode in ('changed', 'prefix_changed') and count == 2 and address == (0x80000 if mode == 'changed' else 0x7f000) else data
            self.assertEqual(length, 64); return struct.pack('<8Q', *words)
        backend.region, backend.read = region, read
        return watch, backend, directory, calls, prefix+page
    def test_stable_prefix_closed_binary_hash_offsets_and_one_attempt_preserve_own_traps(self):
        watch, backend, directory, calls, expected = self.make()
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
        artifact = directory/'writer-source-01.bin'; metadata = watch.rows[0]['writer_fragment']
        self.assertEqual(artifact.read_bytes(), expected)
        self.assertEqual(metadata['sha256'], e.hashlib.sha256(expected).hexdigest())
        self.assertEqual((metadata['status'], metadata['byte_count'], metadata['post_ip_offset'],
                          metadata['allocation_offset'], metadata['prefix_count']),
                         ('SNAPSHOT', 8192, 4099, 61440, 4096))
        self.assertEqual(metadata['phase'], 'PREVIOUS_PAGE_FOR_KNOWN_DIRECT_EDGE')
        self.assertTrue(0 <= 4096-53 < metadata['byte_count'])  # Requested known edge fits the carrier.
        self.assertEqual(metadata['prefix_status'], 'COMPLETE'); self.assertTrue(metadata['readsEqual'])
        row = watch.rows[0]; slots = row['stack_slots']
        self.assertEqual(len(slots), 8)
        self.assertEqual([(x['slot_index'], x['stack_byte_offset']) for x in slots], [(i, i*8) for i in range(8)])
        self.assertEqual([x['rva'] for x in row['stack_candidates']], [0x100, 0x200, 0x300])
        self.assertEqual(slots[0]['rva'], slots[1]['rva'])
        self.assertTrue(slots[4]['same_source_allocation'])
        self.assertEqual(slots[4]['allocation_relative_offset'], 0xf123)
        self.assertFalse(slots[5]['same_source_allocation']); self.assertIsNone(slots[5]['allocation_relative_offset'])
        self.assertEqual([slots[i]['type'] for i in (6, 7)], ['UNKNOWN', 'UNKNOWN'])
        raw = watch.stream.getvalue()
        self.assertLessEqual(len(raw.rstrip('\n')), 4096)
        self.assertTrue(all(str(value) not in raw for value in (0xa0100, 0xa0200, 0xa0300, 0x7f123, 0xb0010, 0xc0010)))
        moved = artifact.with_suffix('.closed'); artifact.rename(moved); moved.rename(artifact)
        backend.contexts[10].put64(104, 0xffff0ff1)
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
        self.assertNotIn('writer_fragment', watch.rows[1])
        self.assertNotIn('stack_slots', watch.rows[1])
        self.assertEqual([n for _, n in calls].count(4096), 4)
        self.assertEqual([n for _, n in calls].count(64), 2)
        self.assertEqual(len(list(directory.glob('*.bin'))), 1)
        self.assertEqual(backend.contexts[10].get64(104) & 1, 0)
        self.assertNotIn(str(directory), watch.stream.getvalue())
    def test_changed_read_foreign_prefix_allocation_or_denied_read_is_unknown_without_artifact_and_trap_continues(self):
        for mode in ('changed', 'prefix_changed', 'other_allocation', 'denied', 'unsafe_slot_name', 'max_slot_name', 'source_unknown'):
            with self.subTest(mode=mode):
                watch, backend, directory, calls, _ = self.make(mode)
                self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
                metadata = watch.rows[0]['writer_fragment']
                self.assertTrue(all(len(line) <= 4096 for line in watch.stream.getvalue().splitlines()))
                if mode in ('unsafe_slot_name', 'max_slot_name', 'source_unknown'):
                    self.assertEqual(metadata['status'], 'SNAPSHOT')
                    if mode == 'source_unknown':
                        slot = watch.rows[0]['stack_slots'][4]
                        self.assertIsNone(slot['same_source_allocation']); self.assertIsNone(slot['allocation_relative_offset'])
                        self.assertEqual(watch.pending[1], e.CONTINUE)
                        self.assertEqual(backend.contexts[10].get64(104) & 1, 0)
                        continue
                    name = watch.rows[0]['stack_slots'][7]['module']
                    self.assertEqual(name, 'UNKNOWN' if mode == 'unsafe_slot_name' else 'x'*76+'.dll')
                    self.assertNotIn('Device', watch.stream.getvalue())
                    continue
                self.assertEqual((metadata['status'], metadata['byte_count'], metadata['sha256']), ('UNKNOWN', 0, 'UNKNOWN'))
                self.assertNotIn('file_basename', metadata)
                self.assertFalse((directory/'writer-source-01.bin').exists())
                self.assertEqual(backend.contexts[10].get64(104) & 1, 0)
                self.assertEqual(watch.pending[1], e.CONTINUE)
                self.assertTrue(watch.writer_fragment_attempted)
                calls_before = len(calls)
                backend.contexts[10].put64(104, 0xffff0ff1)
                self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
                self.assertNotIn('writer_fragment', watch.rows[1]); self.assertNotIn('stack_slots', watch.rows[1])
                self.assertEqual(len(calls)-calls_before, 1)  # Existing stack64 only, no retry.
                if mode == 'other_allocation':
                    self.assertEqual(metadata['prefix_status'], 'UNKNOWN')
                    self.assertNotIn(4096, [n for _, n in calls])


class WriterTargetsPure(unittest.TestCase):
    def make(self, mode='stable'):
        watch, backend, directory, _, _ = WriterFragmentPure.make(self)
        carrier = (e.ROOT/'work/local_original_session/runs/entry-write-watch-48/writer-source-01.bin').read_bytes()
        self.assertEqual(e.hashlib.sha256(carrier).hexdigest(), '4e25546ed10c6e41cf751835fbfe6f0f8dcad20f1828e1d77df30ba7e988e22f')
        if mode == 'layout': carrier = bytes([carrier[0] ^ 1])+carrier[1:]
        start, allocation = 0x7f000, 0x70000
        targets = [start+offset for offset in (82464, 9462682)]
        pages = [address & ~4095 for address in targets]
        reads, checks, frame_checks = [], [], []
        words = [0]*128; words[43], words[44], words[48] = 0x7f123, 0xb0010, 0xa0200
        frame_data = struct.pack('<128Q', *words)
        old_read, old_region, old_validate, old_classify = backend.read, backend.region, backend.validate, backend.classify
        def read(address, length):
            reads.append((address, length))
            if address == 0x90000 and length in (512, 768, 1024):
                return b'x'+frame_data[1:length] if mode == 'frame_changed' and reads.count((address, length)) == 2 else frame_data[:length]
            if address in (start, start+4096) and length == 4096: return carrier[address-start:address-start+4096]
            if address in pages:
                self.assertEqual(length, 4096)
                count = reads.count((address, length))
                return (b'x' if mode == 'changed' and address == pages[0] and count == 2 else b't')*4096
            return old_read(address, length)
        def region(address, length=1):
            if address == 0x90000 and length in (1, 512, 768, 1024):
                frame_checks.append(1)
                return types.SimpleNamespace(type=0x20000, state=0x1000, protect=0x104 if mode == 'frame_denied' else 4,
                                             allocation=0x91000 if mode == 'frame_foreign' and len(frame_checks) > 1 else 0x90000,
                                             base=0x90000, size=515 if mode == 'frame_clip512' else 768 if mode == 'frame_clip768' else 352 if mode == 'frame_short' else 4096)
            if address in pages:
                checks.append(address)
                other = mode == 'other_allocation' and address == pages[0]
                return types.SimpleNamespace(type=0x1000000 if other else 0x40000, state=0x1000,
                                             allocation=0xb0000 if other else allocation, protect=0x20)
            return old_region(address, length)
        def validate(expected):
            if (directory/'writer-source-01.bin').exists():
                if mode == 'owner': raise ValueError('PURE_OWNER_CHANGED')
                if mode == 'event': watch.pending[0]['tid'] = 11
            return old_validate(expected)
        def classify(address, modules):
            if address in targets:
                return dict(type='MEM_IMAGE' if mode == 'other_allocation' else 'MEM_MAPPED',
                            module='LC.guard.exe' if mode == 'other_allocation' else 'UNKNOWN', rva=32 if mode == 'other_allocation' else None)
            return old_classify(address, modules)
        backend.read, backend.region, backend.validate, backend.classify = read, region, validate, classify
        return watch, backend, directory, reads, checks, pages, targets, allocation
    def test_exact_carrier_two_pages_offsets_closed_hash_sidecar_bounded_and_no_retry(self):
        watch, backend, directory, reads, checks, pages, targets, allocation = self.make()
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
        row = watch.rows[0]; meta = row['writer_targets']; path = directory/meta['file_basename']
        data = path.read_bytes(); sidecar = json.loads(data)
        self.assertEqual(meta['status'], 'METADATA_SAVED')
        self.assertEqual((meta['byte_count'], meta['sha256']), (len(data), e.hashlib.sha256(data).hexdigest()))
        self.assertEqual([sidecar[key] for key in ('pid', 'birth', 'thread_id', 'hit', 'monotonic_ns')],
                         [row[key] for key in ('pid', 'birth', 'thread_id', 'hit', 'monotonic_ns')])
        self.assertEqual(sidecar['source_carrier_sha256'], row['writer_fragment']['sha256'])
        frame = sidecar['frame']; self.assertEqual(frame['status'], 'CLASSIFIED')
        self.assertEqual((frame['byte_count'], frame['slot_count']), (1024, 128))
        self.assertEqual(len(frame['slots']), 128); self.assertEqual(reads.count((0x90000, 1024)), 2)
        self.assertEqual((frame['slots'][48]['stack_byte_offset'], frame['slots'][48]['type'], frame['slots'][48]['module'], frame['slots'][48]['rva']),
                         (384, 'MEM_IMAGE', 'writer.dll', 0x200))
        self.assertEqual(frame['slots'][43]['allocation_relative_offset'], 0xf123)
        self.assertIsNone(frame['slots'][44]['allocation_relative_offset'])
        self.assertLessEqual(len(data), 32768)
        self.assertTrue(all(str(value) not in data.decode('ascii') for value in (0x90000, 0x7f123, 0xb0010, 0xa0200)))
        for index, target in enumerate(sidecar['targets']):
            artifact = directory/target['file_basename']; saved = artifact.read_bytes()
            self.assertEqual((target['status'], target['byte_count'], target['sha256']), ('SNAPSHOT', 4096, e.hashlib.sha256(saved).hexdigest()))
            self.assertEqual((target['allocation_page_offset'], target['target_file_offset']), (pages[index]-allocation, targets[index]-pages[index]))
            self.assertEqual(reads.count((pages[index], 4096)), 2); self.assertEqual(checks.count(pages[index]), 2)
            moved = artifact.with_suffix('.closed'); artifact.rename(moved); moved.rename(artifact)
        moved = path.with_suffix('.closed'); path.rename(moved); moved.rename(path)
        self.assertEqual(len(list(directory.glob('writer-target*.bin'))), 2)
        self.assertLessEqual(len(watch.stream.getvalue().rstrip('\n')), 4096)
        self.assertTrue(all(str(address) not in data.decode('ascii') for address in targets+pages))
        before = len(reads); backend.contexts[10].put64(104, 0xffff0ff1)
        self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
        self.assertNotIn('writer_targets', watch.rows[1]); self.assertEqual(len(reads)-before, 1)
    def test_layout_identity_allocation_read_and_io_failures_stay_unknown_without_changing_trap(self):
        for mode in ('layout', 'owner', 'event', 'other_allocation', 'changed', 'target_io', 'sidecar_io', 'existing',
                     'frame_changed', 'frame_foreign', 'frame_denied', 'frame_clip512', 'frame_clip768', 'frame_short'):
            with self.subTest(mode=mode):
                watch, backend, directory, reads, checks, pages, targets, allocation = self.make(mode)
                original_open = Path.open
                existing = directory/'writer-target-call-01.bin'
                if mode == 'existing': existing.write_bytes(b'preserve')
                class FailingStream:
                    def __enter__(self): self.file = original_open(self.path, 'xb'); return self
                    def write(self, data): self.file.write(data[:1]); raise OSError('PURE_WRITE_FAILURE')
                    def __exit__(self, *unused): self.file.close()
                def opening(path, *args, **kwargs):
                    fail = (mode == 'target_io' and path.name == 'writer-target-call-01.bin') or (mode == 'sidecar_io' and path.name == 'writer-targets.json')
                    if fail and args == ('xb',):
                        stream = FailingStream(); stream.path = path; return stream
                    return original_open(path, *args, **kwargs)
                with patch.object(Path, 'open', opening):
                    self.assertEqual(watch.exception(event(1, exception=0x80000004)), e.CONTINUE)
                row = watch.rows[0]; meta = row['writer_targets']
                self.assertEqual(row['writer_fragment']['status'], 'SNAPSHOT')
                self.assertEqual(backend.contexts[10].get64(104) & 1, 0)
                self.assertEqual(watch.pending[1], e.CONTINUE)
                self.assertTrue(all(len(line) <= 4096 for line in watch.stream.getvalue().splitlines()))
                if mode == 'sidecar_io':
                    self.assertEqual(meta['status'], 'UNKNOWN'); self.assertFalse((directory/'writer-targets.json').exists())
                else:
                    sidecar = json.loads((directory/'writer-targets.json').read_bytes())
                    expected = 'UNKNOWN_SOURCE_LAYOUT' if mode == 'layout' else 'SNAPSHOT' if mode.startswith('frame_') else 'UNKNOWN'
                    self.assertEqual(sidecar['targets'][0]['status'], expected)
                    if mode.startswith('frame_'):
                        self.assertEqual(sidecar['targets'][1]['status'], 'SNAPSHOT')
                        if mode in ('frame_clip512', 'frame_clip768'):
                            size = 512 if mode == 'frame_clip512' else 768
                            self.assertEqual((sidecar['frame']['status'], sidecar['frame']['byte_count'], sidecar['frame']['slot_count']), ('CLASSIFIED', size, size//8))
                            self.assertEqual(len(sidecar['frame']['slots']), size//8)
                            self.assertEqual(sidecar['frame']['slots'][48]['module'], 'writer.dll')
                            self.assertEqual(reads.count((0x90000, size)), 2)
                        else:
                            self.assertEqual(sidecar['frame'], dict(status='UNKNOWN', scope='CONDITIONAL_FRAME_CLASSIFICATION_NOT_UNWIND_OR_PROVEN_RETURN', byte_count=0, slot_count=0, slots=[]))
                            self.assertEqual(reads.count((0x90000, 1024)), 0 if mode in ('frame_denied', 'frame_short') else 2)
                    if mode in ('layout', 'owner', 'event'):
                        self.assertFalse(any(address in pages for address, _ in reads))
                        self.assertEqual(reads.count((0x90000, 1024)), 0)
                    if mode == 'other_allocation':
                        self.assertEqual(sidecar['targets'][0]['module'], 'LC.guard.exe')
                        self.assertEqual((sidecar['targets'][0]['type'], sidecar['targets'][0]['rva']), ('MEM_IMAGE', 32))
                        self.assertFalse(any(address == pages[0] for address, _ in reads))
                    if mode == 'target_io': self.assertFalse(existing.exists())
                    if mode == 'existing': self.assertEqual(existing.read_bytes(), b'preserve')
                before = len(reads)
                self.assertIsNone(watch.writer_fragment(0x80003, row))
                self.assertEqual(len(reads), before)  # Failed targets/metadata never retry.


class User32TargetRolePure(unittest.TestCase):
    def test_first_and_same_allocation_stay_strict_other_mapping_can_be_unknown(self):
        for target_base, role, same in [(None, 'TARGET_USER32', None),
                                        (0x40000, 'TARGET_USER32', True),
                                        (0x50000, 'OPTIONAL', False)]:
            with self.subTest(target_base=target_base):
                backend = FreshModulePure().make(); backend.target_base = target_base
                backend.memory[0x40080] = b'\0'*264
                if role == 'OPTIONAL':
                    self.assertIsNone(e.Win32Backend.module(backend, event(6, file=71, base=0x40000)))
                else:
                    with self.assertRaisesRegex(ValueError, 'LOADED_HEADER_MISMATCH'):
                        e.Win32Backend.module(backend, event(6, file=71, base=0x40000))
                self.assertEqual(backend.header_failure,
                                 dict(role=role, stage='NT', existing_target_allocation=same))
    def test_later_other_mapping_never_retargets_or_arms_same_base_and_target_unload_still_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Fake(); watch = e.Watch(backend, EXPECTED, directory)
            watch.event(event(3, thread=10, file=71, base=0x80000,
                              module=dict(name='lc.guard.exe', base=0x80000)))
            watch.event(event(6, file=72, base=0x40000))
            original_module = watch.modules[0x40000]
            original_dr = e.saved_dr(backend.contexts[10])
            original_sets = [row for row in backend.log if isinstance(row, tuple) and row[0] == 'set_context']
            self.assertEqual(watch.event(event(6, file=73, base=0x70000,
                                              module=dict(base=0x70000))), e.CONTINUE)
            self.assertEqual(backend.target_base, 0x40000)
            self.assertIn(0x70000, watch.modules)  # Classification only, never target.
            original_binding = backend.module
            backend.module = lambda row: None
            self.assertEqual(watch.event(event(6, file=74, base=0x60000)), e.CONTINUE)
            self.assertNotIn(0x60000, watch.modules)
            backend.module = original_binding
            with self.assertRaisesRegex(ValueError, 'MODULE_BOUND'):
                watch.event(event(6, file=75, base=0x40000))
            with self.assertRaisesRegex(ValueError, 'USER32_UNLOADED'):
                watch.event(event(7, base=0x40000))
            self.assertEqual(watch.event(event(7, base=0x70000)), e.CONTINUE)
            self.assertIs(watch.modules[0x40000], original_module)
            self.assertEqual((watch.target_base, watch.address), (0x40000, 0x40100))
            self.assertEqual(e.saved_dr(backend.contexts[10]), original_dr)
            self.assertEqual([row for row in backend.log if isinstance(row, tuple) and row[0] == 'set_context'], original_sets)


class Dr7FixedBitPure(unittest.TestCase):
    def armed(self, default=0):
        value = context(); value.put64(112, default)
        saved = e.arm_context(value, 0x40100)
        return value, saved
    def test_actual42_fixed_bit_only_difference_accepted_without_context_mutation(self):
        for default in (0, 0x400):
            with self.subTest(default=default):
                value, saved = self.armed(default)
                value.put64(112, value.get64(112) ^ 0x400)
                value.put64(104, value.get64(104) | 1)  # Actual42 own B0 only.
                before = e.saved_dr(value)
                self.assertEqual(value.get64(112) ^ (saved[5] | 0xd0001), 1024)
                e.owned_context(value, 0x40100, saved)
                self.assertEqual(e.saved_dr(value), before)
    def test_all_other_63_dr7_bits_and_each_address_register_still_refused(self):
        for bit in range(64):
            if bit == 10:
                continue
            with self.subTest(dr7_bit=bit):
                value, saved = self.armed()
                value.put64(112, value.get64(112) ^ (1 << bit))
                with self.assertRaisesRegex(ValueError, 'OWNED_DR_CHANGED'):
                    e.owned_context(value, 0x40100, saved)
        for offset in e.DR_OFFSETS[:4]:
            with self.subTest(address_register_offset=offset):
                value, saved = self.armed()
                value.put64(offset, value.get64(offset) ^ 1)
                with self.assertRaisesRegex(ValueError, 'OWNED_DR_CHANGED'):
                    e.owned_context(value, 0x40100, saved)


class MismatchMetadataPure(unittest.TestCase):
    def make(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        backend = Fake(); watch = e.Watch(backend, EXPECTED, temporary.name)
        watch.stream = io.StringIO()
        watch.event(event(3, thread=10, file=71, base=0x40000))
        backend.contexts[10].put64(72, 0x40400)
        backend.contexts[10].put64(112, backend.contexts[10].get64(112) ^ 0x400)
        backend.contexts[10].put64(104, 0xffff0ff1)
        return watch, backend
    def test_owned_mismatch_one_bounded_row_without_hit_or_consumption(self):
        watch, backend = self.make()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'ENTRY_WATCH_OWNED_DR_CHANGED'):
                watch.exception(event(1, exception=0x80000004))
        raw = watch.stream.getvalue()
        self.assertEqual(len(raw.splitlines()), 1)
        self.assertLess(len(raw), 4096)
        row = json.loads(raw)
        self.assertEqual(row['schema'], 'owned-entry-dr-mismatch-v1')
        self.assertEqual((row['pid'], row['birth'], row['image_sha256'], row['thread_id']),
                         (44, '123', e.IMAGE_SHA, 10))
        self.assertEqual(row['Dr0_3_equal'], [False, True, True, True])
        self.assertEqual((row['Dr7Xor'], row['activeDr6CauseBits']), (0x400, 1))
        self.assertEqual(watch.rows, [])
        self.assertIsNone(watch.pending)
        self.assertNotIn('263168', raw)  # No raw current DR0.
    def test_metadata_identity_or_output_failure_preserves_original_ownership_error(self):
        for failed in ('identity', 'output'):
            with self.subTest(failed=failed):
                watch, backend = self.make()
                if failed == 'identity':
                    backend.identity['birth'] = '124'
                else:
                    watch.emit = lambda row: (_ for _ in ()).throw(OSError('pure sink failure'))
                with self.assertRaisesRegex(ValueError, 'ENTRY_WATCH_OWNED_DR_CHANGED'):
                    watch.exception(event(1, exception=0x80000004))
                self.assertEqual(watch.stream.getvalue(), '')
                self.assertEqual(watch.rows, [])
                self.assertIsNone(watch.pending)
                self.assertTrue(watch.dr_mismatch_metadata_attempted)


class ReadyDrainPure(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
    def watch(self, backend=None):
        backend = backend or Fake()
        watch = e.Watch(backend, EXPECTED, self.directory)
        backend.w = watch
        return watch, backend
    def replay(self, *, target=True, ntdll=True):
        rows = [event(3, thread=10, file=71, base=0x80000,
                      module=dict(name='lc.guard.exe', base=0x80000)),
                event(2, tid=11, thread=11)]
        if ntdll:
            rows.append(event(6, file=73, base=0x60000, module=dict(name='ntdll.dll', base=0x60000)))
        if target:
            rows.append(event(6, file=72, base=0x40000))
        return rows
    def test_start_only_returns_after_continued_replay_idle_all_threads_armed(self):
        watch, backend = self.watch(Fake(self.replay()))
        checks = []
        def wait():
            if backend.events:
                self.assertFalse(watch.ready.is_set())
                return backend.events.pop(0)
            if not checks:
                self.assertIsNone(watch.pending)
                self.assertEqual([x for x in backend.log if isinstance(x, tuple) and x[0] == 'continue'],
                                 [('continue', 10, e.CONTINUE), ('continue', 11, e.CONTINUE),
                                  ('continue', 10, e.CONTINUE), ('continue', 10, e.CONTINUE)])
                self.assertFalse(watch.ready.is_set())
                self.assertTrue(all(r['saved'] is not None for r in watch.threads.values()))
                self.assertEqual(backend.contexts[10].get64(72), 0x40100)
                self.assertEqual(backend.contexts[11].get64(72), 0x40100)
                checks.append('first_idle')
                return None
            watch.stop.wait(0.002)
            return None
        backend.wait = wait
        try:
            watch.start()
            self.assertEqual(checks, ['first_idle'])
            self.assertEqual(watch.ready_phase, 'ATTACH_REPLAY_DRAINED_ARMED')
            self.assertTrue(watch.initial_break)  # No initial-breakpoint wait.
            self.assertTrue(watch.attached)
        finally:
            watch.finish()
        rows = [json.loads(line) for line in (self.directory/'entry-write-watch.jsonl').read_text('utf-8').splitlines()]
        self.assertEqual(rows[-1]['ready_phase'], 'ATTACH_REPLAY_DRAINED_ARMED')
        self.assertFalse(rows[-1]['initial_system_break_consumed'])
    def test_target_present_requires_created_ntdll_threads_and_all_armed(self):
        watch, backend = self.watch()
        watch.attached = True
        watch.ready_phase = 'ATTACH_REPLAY_PENDING'
        watch.ready_after_idle(); self.assertFalse(watch.ready.is_set())
        watch.created = True
        watch.modules[0x60000] = module(name='ntdll.dll', base=0x60000)
        watch.ready_after_idle(); self.assertFalse(watch.ready.is_set())
        watch.address = 0x40100
        watch.ready_after_idle(); self.assertFalse(watch.ready.is_set())
        watch.threads[10] = dict(handle=10, saved=None)
        watch.ready_after_idle(); self.assertFalse(watch.ready.is_set())
        watch.threads[10]['saved'] = e.saved_dr(context())
        watch.ready_after_idle(); self.assertTrue(watch.ready.is_set())
    def test_ntdll_missing_blocks_ready_even_when_target_armed(self):
        watch, backend = self.watch()
        for row in self.replay(ntdll=False): watch.event(row)
        self.assertTrue(all(record['saved'] is not None for record in watch.threads.values()))
        watch.ready_after_idle()
        self.assertFalse(watch.ready.is_set())
    def test_target_absent_rejects_any_saved_arm_state(self):
        watch, backend = self.watch()
        for row in self.replay(target=False): watch.event(row)
        watch.threads[10]['saved'] = e.saved_dr(context())
        watch.ready_after_idle()
        self.assertFalse(watch.ready.is_set())
    def test_waiting_target_start_then_late_load_arms_all_before_continue_and_new_thread(self):
        watch, backend = self.watch(Fake(self.replay(target=False)))
        backend.contexts[12] = context()
        allow_load, late_complete = threading.Event(), threading.Event()
        later = [event(6, file=72, base=0x40000), event(2, tid=12, thread=12)]
        original_continue = backend.continue_event
        def wait():
            if backend.events:
                self.assertFalse(watch.ready.is_set())
                return backend.events.pop(0)
            if allow_load.is_set() and later:
                return later.pop(0)
            watch.stop.wait(0.002)
            return None
        def continue_event(row, status):
            if row['code'] == 6 and row['base'] == 0x40000:
                self.assertEqual(watch.address, 0x40100)
                for tid in (10, 11):
                    self.assertIsNotNone(watch.threads[tid]['saved'])
                    self.assertEqual(backend.contexts[tid].get64(72), 0x40100)
            if row['code'] == 2 and row['tid'] == 12:
                self.assertIsNotNone(watch.threads[12]['saved'])
                self.assertEqual(backend.contexts[12].get64(72), 0x40100)
                late_complete.set()
            return original_continue(row, status)
        backend.wait, backend.continue_event = wait, continue_event
        try:
            watch.start()
            self.assertEqual(watch.ready_phase, 'ATTACH_REPLAY_DRAINED_WAITING_TARGET')
            self.assertFalse(watch.target_armed_at_ready)
            self.assertIsNone(watch.address)
            self.assertTrue(all(record['saved'] is None for record in watch.threads.values()))
            self.assertTrue(watch.initial_break)
            allow_load.set()
            self.assertTrue(late_complete.wait(1))
            self.assertIsNone(watch.failure)
        finally:
            watch.finish()
        summary = json.loads((self.directory/'entry-write-watch.jsonl').read_text('utf-8').splitlines()[-1])
        self.assertEqual(summary['ready_phase'], 'ATTACH_REPLAY_DRAINED_WAITING_TARGET')
        self.assertEqual(summary['ready_scope'], 'DEBUG_ATTACH_REPLAY_ONLY_NOT_TARGET_COVERAGE')
        self.assertFalse(summary['target_armed_at_ready'])
        self.assertTrue(summary['fresh_target_bound'])
    def test_pending_event_prevents_ready_even_if_armed(self):
        watch, backend = self.watch()
        for row in self.replay(): watch.event(row)
        watch.pending = (event(6, file=0, base=0x40000), e.CONTINUE)
        watch.ready_after_idle()
        self.assertFalse(watch.ready.is_set())
        watch.pending = None
        watch.ready_after_idle()
        self.assertTrue(watch.ready.is_set())
    def test_fresh_identity_failure_at_idle_is_not_ready(self):
        watch, backend = self.watch()
        for row in self.replay(): watch.event(row)
        backend.identity['birth'] = '124'
        with self.assertRaisesRegex(ValueError, 'BIRTH_MISMATCH'): watch.ready_after_idle()
        self.assertFalse(watch.ready.is_set())
        self.assertNotEqual(watch.ready_phase, 'ATTACH_REPLAY_DRAINED_ARMED')
    def test_finally_signal_without_drained_ready_cannot_start_successfully(self):
        watch, backend = self.watch()
        with self.assertRaisesRegex(ValueError, 'ATTACH_FAILED'): watch.start()
        watch.finish()
        self.assertTrue(watch.ready.is_set())  # Wake on terminal failure/stop only.
        self.assertTrue(watch.done.is_set())
        self.assertEqual(watch.ready_phase, 'ATTACH_REPLAY_PENDING')
        self.assertFalse(watch.attached)
    def test_attach_only_signal_is_rejected_without_phase_and_cleanup_still_joins(self):
        watch, backend = self.watch()
        def attach_only():
            watch.attached = True
            watch.ready.set()
            watch.stop.wait(1)
            watch.done.set()
        watch.run = attach_only
        try:
            with self.assertRaisesRegex(ValueError, 'DRAINED_READY_REQUIRED'): watch.start()
        finally:
            watch.finish()
        self.assertFalse(watch.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
