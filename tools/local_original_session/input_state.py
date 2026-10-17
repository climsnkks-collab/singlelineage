"""Read-only retained input callback state from existing pinned source evidence.

Source/layout and live pointer/slot agreement are reported separately from
execution: changing cursor fields does not prove which input produced a change.
No new attachment, function invocation, input, image capture or memory write.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
CONTROL_SHA = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
SOURCES = {
    'work/local_server_rea_20261016/input_evidence/callback_dispatch_followup.json':
        'ae13446780700e7e28263eaf3fc3a42f4d3b41ba1cc2182358d4c953f4f5a8eb',
    'work/local_native_move_input_source/source.json':
        '1f804ae48c8cc3cae307b652f9c81b295b829b9ed1f635d993a920d5db16df9b',
}
SCENES = ('Intro', 'Lobby', 'Login', 'CharacterSelect', 'Land')


def need(value, reason):
    if not value:
        raise ValueError(reason)


def empty(reason='NOT_SAMPLED', requested=0):
    return dict(status='UNKNOWN', reason=reason, source_contract_valid=False,
                cursor_xy=None, origin_xy=None, scale_xy=None,
                window_flag62_nonzero=None, window_mode64_i32=None,
                host_cursor_mode_i32=None, host_mode208_i32=None,
                stable_double_read=False, snapshot_atomic=False,
                typed_bytes_requested=requested)


def public(row):
    """Known scalar fields only; no raw pointer, HWND, bytes or UI text."""
    if type(row) is not dict or row.get('status') != 'OBSERVED':
        requested = row.get('typed_bytes_requested', 0) if type(row) is dict else 0
        if type(requested) is not int or not 0 <= requested <= 8192:
            requested = 0
        return empty(row.get('reason', 'NOT_SAMPLED') if type(row) is dict else 'NOT_SAMPLED', requested)
    result = empty()
    for key in result:
        if key in row:
            result[key] = row[key]
    result['status'] = 'OBSERVED'
    return result


class InputState:
    def __init__(self):
        documents = []
        for relative, expected in SOURCES.items():
            path = ROOT / relative
            need(0 < path.stat().st_size <= 4 * 1024 * 1024, 'INPUT_SOURCE_BYTE_BOUND')
            raw = path.read_bytes()
            need(hashlib.sha256(raw).hexdigest() == expected, 'INPUT_SOURCE_CHANGED')
            document = json.loads(raw)
            need(document['CONTROL_sha256'] == CONTROL_SHA, 'INPUT_SOURCE_CONTROL_CHANGED')
            documents.append(document)
        callbacks, host = documents
        need(callbacks['global'] == '0x17f0d18' and callbacks['window_vtable'] == '0x123a7d8'
             and callbacks['window_slots']['0x50'] == '0xb88fd0'
             and callbacks['window_slots']['0xd8'] == '0xb86fd0', 'INPUT_CALLBACK_SOURCE_CHANGED')
        functions = {f['rva']: {i['rva']: i['instruction'] for i in f['instructions']}
                     for f in callbacks['functions']}
        checks = {
            '0xb8ac40': {'0xb8ac67': 'mov rbx, qword ptr [rip + 0xc660aa]',
                        '0xb8ac77': 'lea rdi, [rbx + 0xb0]',
                        '0xb8ac86': 'lea rsi, [rbx + 0xb4]',
                        '0xb8acbf': 'cmp byte ptr [rbx + 0x62], 0',
                        '0xb8acc5': 'cmp dword ptr [rbx + 0x64], 1'},
            '0xb88570': {'0xb887f0': 'mov rcx, qword ptr [rbx + 0x80]',
                        '0xb887f7': 'call 0xef15d0',
                        '0xb88803': 'mov rcx, qword ptr [rbx + 0x80]',
                        '0xb8880a': 'call 0xef12d0'},
            '0xb8b1f0': {'0xb8b204': 'mov rbx, qword ptr [rip + 0xc65b0d]',
                        '0xb8b2f3': 'mov rcx, rbx',
                        '0xb8b2f6': 'call qword ptr [rax + 0xd8]'},
            '0xb86fd0': {'0xb8700c': 'mov rsi, rcx',
                        '0xb8711d': 'vsubss xmm0, xmm7, dword ptr [rsi + 0x24]',
                        '0xb87122': 'vdivss xmm3, xmm0, dword ptr [rsi + 0x54]',
                        '0xb87127': 'vsubss xmm1, xmm6, dword ptr [rsi + 0x20]',
                        '0xb8712c': 'vdivss xmm2, xmm1, dword ptr [rsi + 0x50]'},
            '0xef15d0': {'0xef15f7': 'mov qword ptr [rcx + 0x320], rdx'},
            '0xef12d0': {'0xef12f7': 'mov qword ptr [rcx + 0x328], rdx'},
        }
        for function, rows in checks.items():
            need(all(functions[function].get(at) == text for at, text in rows.items()),
                 'INPUT_FIELD_SOURCE_CHANGED')
        host_functions = {f['rva']: {i['rva']: i['instruction'] for i in f['instructions']}
                          for f in host['functions']}
        need(host_functions['0xef5480']['0xef5f95'] == 'cmp dword ptr [rsi + 0x8c], 0x34003'
             and host_functions['0xef5480']['0xef5fae'] == 'cmp dword ptr [rsi + 0x208], 0'
             and host_functions['0xef4c10']['0xef4c42'] == 'mov rcx, qword ptr [rbx + 0x368]',
             'INPUT_HOST_SOURCE_CHANGED')

    def sample(self, reader, scene_row, proof):
        sampler = reader.sampler
        started = sampler.total
        previous_bytes = sampler.bytes
        sampler.bytes = 0  # Independent frozen leaf allowance; total is never reset.
        limit = getattr(reader, 'sample_byte_limit', 8192)
        try:
            need(type(limit) is int and 8192 <= limit <= 16384, 'INPUT_COMBINED_LIMIT_REQUIRED')
            need(sampler.b is reader.backend and sampler.c is reader.contract,
                 'INPUT_EXACT_RETAINED_SAMPLER_REQUIRED')
            need(scene_row.get('status') == 'OBSERVED' and scene_row.get('current') in SCENES
                 and scene_row.get('pending') == 'none' and scene_row.get('root_ready') is True,
                 'INPUT_STABLE_SCENE_REQUIRED')
            reader.validate()
            base, size = sampler.g['base'], sampler.g['size']
            need(type(base) is int and base % 65536 == 0 and type(size) is int
                 and 0x17f0d20 <= size == reader.contract['image_size'], 'INPUT_IMAGE_BOUNDS_REQUIRED')
            route, state = proof.get('route'), proof.get('state')
            scene, scene_raw = proof.get('scene'), proof.get('raw')
            need(type(route) is tuple and route[1] is True and type(state) is int
                 and type(scene) is dict and type(scene_raw) is bytes and len(scene_raw) == 36,
                 'INPUT_CURRENT_SCENE_PROOF_REQUIRED')
            need(scene['current']['kind'] == scene_row['current']
                 and scene['pending']['kind'] == 'none', 'INPUT_SCENE_CHANGED')
            records = []
            def read(at, length, image=False):
                need(type(length) is int and 0 < length <= 4096
                     and sampler.total + length <= limit, 'INPUT_COMBINED_BYTE_BOUND')
                raw = sampler.read(at, length, image=image)
                need(type(raw) is bytes and len(raw) == length, 'INPUT_PARTIAL_READ')
                records.append((at, raw, image))
                return raw
            def pointer(at, image=False):
                value = struct.unpack('<Q', read(at, 8, image))[0]
                need(0x10000 <= value <= 0x7fffffffffff and value % 8 == 0,
                     'INPUT_POINTER_NONCANONICAL')
                return value
            window = pointer(base + 0x17f0d18, True)
            need(pointer(window) == base + 0x123a7d8, 'INPUT_WINDOW_TYPE_CHANGED')
            for offset, target in ((0x50, 0xb88fd0), (0xd8, 0xb86fd0)):
                need(pointer(base + 0x123a7d8 + offset, True) == base + target,
                     'INPUT_WINDOW_SLOT_CHANGED')
            host = pointer(window + 0x80)
            need(pointer(host + 0x320) == base + 0xb8b1f0
                 and pointer(host + 0x328) == base + 0xb8ac40, 'INPUT_HOST_CALLBACK_CHANGED')
            hwnd = struct.unpack('<Q', read(host + 0x368, 8))[0]
            need(hwnd and reader.owner.child is reader.member
                 and reader.owner.native.owned_hwnd(reader.member, hwnd), 'INPUT_WINDOW_OWNER_LOST')
            cursor = list(struct.unpack('<ff', read(window + 0xb0, 8)))
            origin = list(struct.unpack('<ff', read(window + 0x20, 8)))
            scale = list(struct.unpack('<ff', read(window + 0x50, 8)))
            need(all(math.isfinite(n) for n in cursor + origin + scale), 'INPUT_NONFINITE_FIELD')
            flag62 = read(window + 0x62, 1) != b'\0'
            mode64 = struct.unpack('<i', read(window + 0x64, 4))[0]
            cursor_mode = struct.unpack('<i', read(host + 0x8c, 4))[0]
            mode208 = struct.unpack('<i', read(host + 0x208, 4))[0]
            # Recheck every object/global/table byte privately; no addresses leave.
            for at, expected, image in records:
                need(sampler.total + len(expected) <= limit, 'INPUT_COMBINED_BYTE_BOUND')
                need(sampler.read(at, len(expected), image=image) == expected, 'INPUT_TYPED_READ_CHANGED')
            need(sampler.read(state + 0x360, 36) == scene_raw and sampler.route() == route,
                 'INPUT_ROOT_OR_SCENE_CHANGED')
            need(reader.owner.child is reader.member
                 and reader.owner.native.owned_hwnd(reader.member, hwnd), 'INPUT_WINDOW_OWNER_LOST')
            reader.validate()
            result = empty(None, sampler.total - started)
            result.update(status='OBSERVED', source_contract_valid=True, cursor_xy=cursor,
                          origin_xy=origin, scale_xy=scale, window_flag62_nonzero=flag62,
                          window_mode64_i32=mode64, host_cursor_mode_i32=cursor_mode,
                          host_mode208_i32=mode208,
                          stable_double_read=True)
            return result
        except Exception as error:
            value = getattr(error, 'reason', error.args[0] if len(error.args) == 1 else None)
            safe = value if type(value) is str and value.replace('_', '').isalnum() and len(value) <= 127 else 'INPUT_STATE_READ_FAILED'
            return empty(safe, max(0, sampler.total - started))
        finally:
            sampler.bytes = previous_bytes
