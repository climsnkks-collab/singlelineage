"""One main-owned, hidden private-desktop integration check; no game startup."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
import uuid

from tools.local_original_session.launcher import native_module, digest
from tools.local_original_session.desktop import PrivateDesktop, hidden_desktop_launch

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'work/local_original_session/background-guard-compile'
EXE = BUILD / 'background_guard_fixture.exe'
DLL = BUILD / 'background_guard_fixture.dll'
OUT = ROOT / 'work/local_original_session/desktop-probes' / ('guard-' + uuid.uuid4().hex[:16])
OUT.mkdir(parents=True, exist_ok=False)
report = dict(schema='private-background-guard-check-v1', game_executed=False)
pins = {str(p): digest(p) for p in (EXE, DLL)}
module = native_module(EXE, BUILD)
native = module.Native('single')
native.k.GetProcessId.argtypes, native.k.GetProcessId.restype = (W.HANDLE,), W.DWORD
native.u.PostMessageW.argtypes = (W.HWND, W.UINT, W.WPARAM, W.LPARAM)
native.u.PostMessageW.restype = W.BOOL
desktop = PrivateDesktop(native)
child = None
owner = None
original_create = native.k.CreateProcessW
previous = {k: os.environ.get(k) for k in ('OWN_INTERNAL_COMMAND_MODE', 'OWN_INTERNAL_COMMAND_DESKTOP',
                                         'OWN_BACKGROUND_GUARD_DIAGNOSTIC_FILE')}

try:
    report['parent_desktop_before'] = desktop._name(native.u.GetThreadDesktop(native.k.GetCurrentThreadId()))
    args = subprocess.list2cmdline([str(EXE), str(DLL), str(OUT / 'host.json')])

    def with_arguments(*parameters):
        values = list(parameters)
        values[1] = C.create_unicode_buffer(args)
        return original_create(*values)

    native.k.CreateProcessW = with_arguments
    os.environ.update(OWN_INTERNAL_COMMAND_MODE='1', OWN_INTERNAL_COMMAND_DESKTOP=desktop.name,
                      OWN_BACKGROUND_GUARD_DIAGNOSTIC_FILE=str(OUT / 'failure.json'))
    try:
        child = hidden_desktop_launch(native, native.create_suspended, module.STARTUP, desktop)
    finally:
        native.k.CreateProcessW = original_create
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    native.attach_single_process_job(child)
    report['primary_pid'], report['primary_tid'] = int(child.pid), int(child.tid)
    owner = SimpleNamespace(child=child, owner_handle=child.process, owner_job=child.job,
                            image_sha=pins[str(EXE)], private_desktop=desktop,
                            native=native, closed=False)

    def validate(member):
        inside = W.BOOL()
        return (member is child and native.k.GetProcessId(child.process) == child.pid
                and native.retained_alive(child)
                and native.k.IsProcessInJob(child.process, child.job, C.byref(inside))
                and bool(inside.value))

    owner.validate = validate
    report['suspended_desktop'] = desktop.probe_thread(child.tid)
    native.resume(child)
    deadline = time.monotonic() + 12
    host = None
    while time.monotonic() < deadline:
        if (OUT / 'host.json').exists():
            try:
                host = json.loads((OUT / 'host.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                host = None
            if host and host.get('status') == 'READY':
                break
        if native.exit_code(child) is not None:
            raise RuntimeError('GUARD_HOST_EXITED_BEFORE_READY:' + str(native.exit_code(child)))
        time.sleep(.05)
    if not host or host.get('status') != 'READY':
        raise RuntimeError('GUARD_HOST_READY_TIMEOUT')
    if not (host.get('installed') is True and host.get('hooks_count') in (17, 18)
            and host.get('protected_exports') == 18
            and host.get('blocked_display_calls') == 1 and host.get('blocked_input_calls') == 1):
        raise RuntimeError('GUARD_HOST_PROTECTION_UNVERIFIED')
    report['phase'] = 'HOST_READY_VERIFY_THREAD'
    report['created_thread_desktop'] = desktop.probe_thread(child.tid)
    C.set_last_error(0)
    queried = native.u.GetThreadDesktop(child.tid)
    report['foreign_desktop_query_error'] = C.get_last_error() if not queried else 0
    if (report['created_thread_desktop'].get('status') == 'OBSERVED'
            and report['created_thread_desktop'].get('matches_private') is not True):
        raise RuntimeError('GUARD_HOST_KNOWN_DESKTOP_MISMATCH')
    if not desktop.contains(host['hwnd']) or host['thread_id'] != child.tid:
        raise RuntimeError('GUARD_HOST_OWNED_DESKTOP_WINDOW_MISMATCH')
    identity = dict(pid=int(child.pid), birth=int(child.identity['birth']),
                    candidate_sha256=owner.image_sha)
    report['phase'] = 'POST_FROM_PRIVATE_HELPER'
    report['posted'] = desktop.post_command(owner, identity, host['hwnd'], host['thread_id'],
                                            host['marker_message'], 1)
    if native.k.WaitForSingleObject(child.process, 5000) != 0:
        raise RuntimeError('GUARD_HOST_EXIT_TIMEOUT')
    report['exit_code'] = native.exit_code(child)
    report['phase'] = 'HOST_EXITED'
    report['host'] = json.loads((OUT / 'host.json').read_text(encoding='utf-8'))
    report['passed'] = (report['posted'] is True and report['exit_code'] == 0
                        and report['host'].get('status') == 'RECEIVED'
                        and report['host'].get('marker_received') is True)
except Exception as error:
    report.update(passed=False, error_type=type(error).__name__, error=str(error)[:180])
finally:
    native.k.CreateProcessW = original_create
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    if child is not None:
        report['job_active_before_cleanup'] = native.active_job_count(child)
        report['cleanup'] = native.cleanup_owned(child)
    if owner is not None:
        owner.closed = True
    for leaf in ('failure.json', 'host.json'):
        path = OUT / leaf
        if path.exists() and path.stat().st_size <= 2048:
            try:
                report[leaf] = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pass
    report['parent_desktop_after'] = desktop._name(native.u.GetThreadDesktop(native.k.GetCurrentThreadId()))
    desktop.close()
    native.close()
    report['desktop_closed'] = desktop.closed
    report['files_unchanged'] = all(digest(Path(p)) == sha for p, sha in pins.items())
    report['files'] = pins
    (OUT / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(dict(path=str(OUT / 'result.json'), **report)))
raise SystemExit(0 if report.get('passed') is True else 1)
