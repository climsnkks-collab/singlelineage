"""Injected original absence gate and handle-race fixtures. Native API calls 0."""
import ctypes as C
import importlib.util
import sys
from ctypes import wintypes as W
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run_checks():
    adapter = load(HERE/'identity_adapter.py', '_cp73_pidreuse_adapter_fixture')
    prior_policy = sys.modules.get('policy')
    sys.modules['policy'] = load(ROOT/'tools/local_ready_entry_gate/policy.py', '_cp73_policy_fixture')
    try:
        original = load(ROOT/'tools/local_ready_entry_gate/native.py', '_cp73_native_fixture').Native.absent
    finally:
        if prior_policy is None: sys.modules.pop('policy', None)
        else: sys.modules['policy'] = prior_policy
    p = original.__globals__['p']
    checks = []

    class Kernel:
        def __init__(self, ident, births=None, wait=0, open_error=None, time_fail=None,
                     image_ok=True, image=None, close_ok=True):
            self.ident, self.births, self.wait = ident, births or [ident['birth']]*3, wait
            self.open_error, self.time_fail = open_error, time_fail
            self.image_ok, self.image, self.close_ok = image_ok, image or ident['image'], close_ok
            self.opens = self.closes = self.times = self.images = self.waits = 0
            self.handles = []
        def OpenProcess(self, rights, inherit, pid):
            assert rights == 0x101000 and inherit is False and pid == self.ident['pid']
            self.opens += 1
            if self.open_error is not None:
                C.set_last_error(self.open_error)
                return 0
            # A reopened PID could refer to another occupant. Tests require this
            # API to be invoked once; the original must receive the retained 701.
            return 701 if self.opens == 1 else 702
        def GetProcessTimes(self, handle, *times):
            self.handles.append(handle)
            self.times += 1
            if self.time_fail == self.times: return False
            birth = int(self.births[min(self.times-1, len(self.births)-1)])
            target = C.cast(times[0], C.POINTER(W.FILETIME)).contents
            target.dwHighDateTime, target.dwLowDateTime = birth >> 32, birth & 0xffffffff
            return True
        def QueryFullProcessImageNameW(self, handle, flags, name, length):
            self.handles.append(handle); self.images += 1
            if not self.image_ok: return False
            name.value = self.image
            return True
        def WaitForSingleObject(self, handle, timeout):
            self.handles.append(handle); self.waits += 1
            assert timeout == 0
            return self.wait
        def CloseHandle(self, handle):
            self.handles.append(handle); self.closes += 1
            assert handle == 701
            return self.close_ok

    def exercise(label, ident, reason=None, **options):
        k = Kernel(ident, **options)
        try:
            result = adapter.verified_absent(SimpleNamespace(k=k), ident, original)
            assert reason is None and result is None, (label, 'unexpected success')
        except p.Refusal as error:
            assert reason == str(error), (label, reason, str(error))
        assert k.opens == 1
        assert k.closes == (0 if options.get('open_error') is not None else 1)
        assert all(h == 701 for h in k.handles), (label, 'handle continuity')
        checks.append(label)
        return k

    for ident in adapter.HISTORICAL_IDENTITIES:
        tag = str(ident['pid'])
        k = exercise('same_birth_exited_original_acceptance:'+tag, ident)
        assert (k.times, k.images, k.waits) == (3, 1, 1)
        exercise('same_birth_active_original_refusal:'+tag, ident, 'PRIOR_HELPER_LIVE', wait=258)
        exercise('same_birth_wait_failure_original_refusal:'+tag, ident, 'PRIOR_HELPER_LIVE', wait=0xffffffff)
        exercise('same_birth_image_unknown_original_refusal:'+tag, ident, 'PRIOR_IMAGE_UNKNOWN', image_ok=False)
        exercise('same_birth_image_changed_original_refusal:'+tag, ident, 'PRIOR_IMAGE_CHANGED', image='C:/different.exe')
        birth = str(int(ident['birth'])+123)
        k = exercise('declared_mismatched_birth_acceptance_no_occupant_queries:'+tag, ident, births=[birth]*2,
                     image_ok=False, wait=258)
        assert (k.times, k.images, k.waits) == (2, 0, 0)
        exercise('open87_declared_absent:'+tag, ident, open_error=87)
        exercise('open5_unknown_refusal:'+tag, ident, 'PRIOR_IDENTITY_UNKNOWN', open_error=5)
        exercise('open0_unknown_refusal:'+tag, ident, 'PRIOR_IDENTITY_UNKNOWN', open_error=0)
        exercise('first_birth_query_failure:'+tag, ident, 'PRIOR_BIRTH_UNKNOWN', time_fail=1)
        exercise('second_birth_query_failure:'+tag, ident, 'PRIOR_BIRTH_UNKNOWN', time_fail=2)
        exercise('retained_birth_change_refusal:'+tag, ident, 'PRIOR_RETAINED_BIRTH_CHANGED', births=[birth, ident['birth']])
        exercise('original_third_birth_change_refusal:'+tag, ident, 'PRIOR_PID_REUSED', births=[ident['birth']]*2+[birth])
        exercise('mismatch_close_failure_unknown:'+tag, ident, 'PRIOR_HANDLE_CLOSE_UNKNOWN', births=[birth]*2, close_ok=False)
        k = exercise('PID_reuse_during_original_gate_keeps_first_handle:'+tag, ident)
        assert k.opens == k.closes == 1
    foreign = dict(adapter.HISTORICAL_IDENTITIES[0], pid=12345)
    k = exercise('undeclared_PID_mismatch_original_refusal', foreign, 'PRIOR_PID_REUSED', births=['1'])
    assert k.times == 1
    foreign = dict(adapter.HISTORICAL_IDENTITIES[0], image='C:/other.exe')
    k = exercise('undeclared_image_mismatch_original_refusal', foreign, 'PRIOR_PID_REUSED', births=['1'])
    assert k.times == 1
    foreign = dict(adapter.HISTORICAL_IDENTITIES[0], birth='1')
    exercise('undeclared_birth_mismatch_original_refusal', foreign, 'PRIOR_PID_REUSED', births=['2'])
    saved = p.IDENTITIES
    p.IDENTITIES = (saved[0],)
    k = Kernel(saved[0])
    try:
        adapter.verified_absent(SimpleNamespace(k=k), saved[0], original)
        raise AssertionError('mutated declaration accepted')
    except p.Refusal as error:
        assert str(error) == 'EXACT_HISTORICAL_IDENTITIES_REQUIRED' and k.opens == 0
    finally: p.IDENTITIES = saved
    checks.append('changed_declared_identity_policy_refused_before_open')
    assert not any(name in adapter.__dict__ for name in ('NEW_IMAGE', 'NEW_BIRTH'))
    checks.append('no_current_occupant_image_birth_allowlist')
    return checks

if __name__ == '__main__':
    import json
    print(json.dumps({'status':'PASS', 'checks_count':len(run_checks()), 'Native':0}))
