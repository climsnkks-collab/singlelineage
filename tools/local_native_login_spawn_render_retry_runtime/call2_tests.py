"""Injected original identity/Samples fixtures; no Native process or slot actions."""
import ast
import copy
import ctypes as C
import importlib.util
import json
import sys
import tempfile
import types
from ctypes import wintypes as W
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name):
    path = HERE / (name + '.py')
    spec = importlib.util.spec_from_file_location('_cp53_fixture_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def run_checks():
    d = load('call2_identity')
    checks = []
    windows = types.ModuleType('_cp53_fixture_original_windows')
    previous = sys.modules.get('core')
    sys.modules['core'] = types.SimpleNamespace(EXE='fixture', EXE_SHA='0' * 64, BUILD=(),
                                              CLONE='fixture', require=need, PROFILES={})
    try:
        exec(compile(d.base.WINDOWS.read_bytes(), str(d.base.WINDOWS), 'exec'), windows.__dict__)
    finally:
        if previous is None:
            sys.modules.pop('core', None)
        else:
            sys.modules['core'] = previous

    class Times:
        argtypes = (W.HANDLE, *([C.POINTER(windows.FT)] * 4))

        def __init__(self, kernel):
            self.kernel = kernel

        def __call__(self, handle, *pointers):
            self.kernel.calls.append(('GetProcessTimes', handle))
            pointers[0]._obj.low = self.kernel.birth
            pointers[0]._obj.high = 0
            C.set_last_error(44)
            return 1

    class Kernel:
        def __init__(self):
            self.calls = []
            self.wait = 258
            self.code = 1
            self.birth = 12345
            self.GetProcessTimes = Times(self)

        def QueryFullProcessImageNameW(self, handle, *args):
            self.calls.append(('QueryFullProcessImageNameW', handle))
            C.set_last_error(5)
            return 0

        def WaitForSingleObject(self, handle, delay):
            need(delay == 0, 'NO_BOUNDED_WAIT_POLICY_CHANGE')
            self.calls.append(('WaitForSingleObject', handle))
            return self.wait

        def GetExitCodeProcess(self, handle, pointer):
            self.calls.append(('GetExitCodeProcess', handle))
            pointer._obj.value = self.code
            return 1

        def IsProcessInJob(self, handle, job, pointer):
            self.calls.append(('IsProcessInJob', handle))
            pointer._obj.value = 1
            return 1

        def OpenProcess(self, *args):
            raise AssertionError('NEW_PID_OPEN_FORBIDDEN')

        def ReadProcessMemory(self, *args):
            raise AssertionError('VM_READ_FORBIDDEN')

    def scenario(work):
        owner = windows.Native.__new__(windows.Native)
        owner.k = Kernel()
        member = types.SimpleNamespace(process=object(), pid=123,
                                       identity={'pid': 123, 'birth': '12345', 'image': 'fixture', 'parent_pid': 1})
        main = types.SimpleNamespace(pid=1, job=object(), members={123: member}, refused_members=[])
        recorder = d.Recorder(work)
        recorder.bind(owner, lambda: main)
        return owner, member, main, recorder

    def fail(owner, member, handle=None):
        try:
            owner.identity(member.process if handle is None else handle, member.pid, 1, include_token=False)
        except ValueError as error:
            need(str(error) == 'native_image_required' and C.get_last_error() == 5,
                 'ORIGINAL_IMAGE_REFUSAL_AND_LASTERROR_PRESERVED')
            return error
        raise AssertionError('ORIGINAL_IMAGE_REFUSAL_REQUIRED')

    def fallback_count(kernel):
        return sum(name in {'WaitForSingleObject', 'GetExitCodeProcess', 'IsProcessInJob'}
                   for name, handle in kernel.calls)

    def sample_result(error, member, main):
        cls = next(node for node in ast.parse(d.base.TRIAL.read_bytes()).body
                   if isinstance(node, ast.ClassDef) and node.name == 'Samples')
        module = types.ModuleType('_cp53_existing_sample_fixture')
        module.__dict__.update(p=types.SimpleNamespace(need=need),
                               time=types.SimpleNamespace(monotonic=lambda: 0, monotonic_ns=lambda: 1),
                               asyncio=types.SimpleNamespace(sleep=lambda: None), native_backend=lambda: None)
        exec(compile(ast.Module(body=[cls], type_ignores=[]), str(d.base.TRIAL), 'exec'), module.__dict__)
        exec('def make(raw_fn):\n async def bound(*args,**kwargs):\n  return await raw_fn(*args,**kwargs)\n return bound', module.__dict__)
        async def raw_fn(*args, **kwargs):
            pass
        module.run_in_context = module.make(raw_fn)
        d.base.patch_samples(module)
        sample = module.Samples.__new__(module.Samples)
        sample.main = main
        sample.owner = types.SimpleNamespace(exit_code=lambda obj: None)
        sample.total = sample.bytes = 0
        sample.report = {'samples': []}
        sample.clock = lambda: 0
        events = []
        sample.event = lambda *args, **kwargs: events.append((args, kwargs))
        def throw():
            raise error
        item = {'member': member, 'reader': types.SimpleNamespace(snapshot=throw), 'count': 0, 'exited': False}
        try:
            sample.sample(item)
        except ValueError as caught:
            need(caught is error, 'ORIGINAL_SAMPLE_EXCEPTION_PRESERVED')
            return 'REFUSED', item, events
        return 'NATURAL_EXIT_SKIP', item, events

    with tempfile.TemporaryDirectory(prefix='cp53-identity-fixtures-') as temporary:
        work = Path(temporary) / 'signaled'
        owner, member, main, recorder = scenario(work)
        first = fail(owner, member)
        frozen_first = copy.deepcopy(recorder.record)
        need(first.identity_failure_reference['call_id'] == 1
             and recorder.record['known_exit'] is False
             and first.identity_failure_exited_member is None, 'FIRST_WAIT258_EXIT1_UNKNOWN')
        need(sample_result(first, member, main)[0] == 'REFUSED', 'FIRST_SAMPLE_REFUSES')
        owner.k.wait = 0
        second = fail(owner, member)
        need(recorder.record == frozen_first and recorder.followup['known_exit'] is True
             and second.identity_failure_reference['call_id'] == 2
             and second.identity_failure_reference['same_call_as_public_record'] is False
             and second.identity_failure_exited_member is member
             and second.identity_failure_exit_code == 1, 'SECOND_EXISTING_KNOWN_EXIT_PREDICATE')
        result, item, events = sample_result(second, member, main)
        need(result == 'NATURAL_EXIT_SKIP' and item['exited']
             and events[0][0][0] == 'natural_exit', 'ORIGINAL_EXISTING_SAMPLE_EXIT_BRANCH')
        checks.append('call1_wait258_unknown_call2_signaled_same_birth_non259_existing_skip')
        before = fallback_count(owner.k)
        third = fail(owner, member)
        need(third.identity_failure_reference['call_id'] == 3
             and third.identity_failure_exited_member is None
             and fallback_count(owner.k) == before
             and recorder.record == frozen_first, 'NO_THIRD_DIAGNOSTIC_OR_SKIP')
        checks.append('call3_original_refusal_no_additional_native_diagnostic_calls')
        need(all(handle is member.process for name, handle in owner.k.calls), 'SAME_HANDLE_ONLY')
        checks.append('all_mock_queries_exact_original_retained_handle_no_PID_open_no_VM')
        recorder.finish({'fatal_identity_failure_reference': third.identity_failure_reference})
        first_file = json.loads((work / 'identity-failure.json').read_bytes())
        followup = json.loads((work / 'identity-failure-followup.json').read_bytes())
        need(all(first_file[key] == value for key, value in frozen_first.items()), 'FIRST_RECORD_PRESERVED')
        need(d.validate_public(followup) == (work / 'identity-failure-followup.json').read_bytes()
             and (work / 'identity-failure-followup.json').stat().st_size <= d.PUBLIC_LIMIT,
             'PUBLIC_SCHEMA_AND_SIZE_BOUND')
        checks.append('first_record_preserved_followup_public_schema_CREATE_NEW_16384_bound')
        try:
            recorder.finish({})
            raise AssertionError('EXISTING_OUTPUT_OVERWRITTEN')
        except FileExistsError:
            pass
        checks.append('existing_public_output_never_overwritten')
        for label, change in (('wrong_schema', lambda row: row.update(schema='foreign')),
                              ('raw_handle_key', lambda row: row.update(raw_handle=123)),
                              ('oversize', lambda row: row['diagnostic'].update(secondary_diagnostic_error='x' * 20000))):
            bad = copy.deepcopy(followup)
            change(bad)
            try:
                d.validate_public(bad)
                raise AssertionError('INVALID_PUBLIC_RECORD_ACCEPTED')
            except ValueError:
                pass
            checks.append('public_validation_refuses_' + label)
        for label, mutate in (('wait258_exit1', lambda owner: None),
                              ('birth_changed', lambda owner: setattr(owner.k, 'birth', 54321)),
                              ('still_active259', lambda owner: (setattr(owner.k, 'wait', 0), setattr(owner.k, 'code', 259)))):
            owner, member, main, recorder = scenario(Path(temporary) / label)
            fail(owner, member)
            mutate(owner)
            second = fail(owner, member)
            need(recorder.followup['known_exit'] is False and second.identity_failure_exited_member is None
                 and sample_result(second, member, main)[0] == 'REFUSED', label)
            checks.append('second_failure_' + label + '_no_skip')
        owner, member, main, recorder = scenario(Path(temporary) / 'other_handle')
        fail(owner, member)
        before = fallback_count(owner.k)
        second = fail(owner, member, object())
        need(recorder.followup is None and fallback_count(owner.k) == before
             and second.identity_failure_exited_member is None, 'OTHER_HANDLE_NEVER_DIAGNOSED')
        fail(owner, member)
        need(recorder.followup is None and fallback_count(owner.k) == before, 'NO_THIRD_AFTER_OTHER_HANDLE')
        checks.append('different_handle_call2_and_later_call3_no_followup')
        owner, member, main, recorder = scenario(Path(temporary) / 'other_job')
        fail(owner, member)
        main.job = object()
        before = fallback_count(owner.k)
        fail(owner, member)
        need(recorder.followup is None and fallback_count(owner.k) == before, 'ROOT_JOB_CHANGED_NO_FOLLOWUP')
        checks.append('changed_root_Job_never_gets_followup_or_skip')
    return checks


if __name__ == '__main__':
    rows = run_checks()
    print(json.dumps({'status': 'PASS_INJECTED_IDENTITY_ONLY', 'checks': rows,
                      'Native_process_API_calls': 0, 'game_slot_uac_actions': 0}))
