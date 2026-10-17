"""Preserve first image failure; assess one second failure on the same held member."""
import ctypes as C
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / 'tools/local_native_login_creation_identity_failure/identity.py'
PARENT_SHA = 'e09e6e4f03a8eda17eec946044c3cb36aefc8a273ed09590daaff3729a5daa9c'
PUBLIC_LIMIT = 16384


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


need(hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA, 'FROZEN_FIRST_IDENTITY_RECORDER')
spec = importlib.util.spec_from_file_location('_cp53_frozen_first_identity', PARENT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def validate_public(row):
    keys = {'schema', 'first_call_id', 'followup_call_id', 'maximum_additional_diagnostics',
            'same_exact_retained_handle', 'new_PID_open', 'VM_RPM', 'diagnostic',
            'final_exception_reference', 'original_guard_predicate_changed',
            'same_existing_known_exit_predicate'}
    need(type(row) is dict and set(row) == keys
         and row['schema'] == 'retained-identity-image-followup-v1'
         and row['first_call_id'] == 1 and row['followup_call_id'] == 2
         and row['maximum_additional_diagnostics'] == 1
         and row['same_exact_retained_handle'] is True
         and row['new_PID_open'] is False and row['VM_RPM'] is False
         and row['original_guard_predicate_changed'] is False
         and row['same_existing_known_exit_predicate'] is True, 'EXACT_CP53_FOLLOWUP_PUBLIC_SCHEMA')
    diagnostic = row['diagnostic']
    required = {'schema', 'call_reference', 'pid_argument', 'handle_classification',
                'exact_previously_retained_handle', 'expected_birth',
                'original_QueryFullProcessImageNameW', 'original_GetProcessTimes',
                'new_PID_Open', 'VM_RPM', 'query_used_for_admission', 'known_exit'}
    optional = {'wait_before', 'fallback_GetProcessTimes', 'GetExitCodeProcess',
                'retained_root_Job', 'wait_after', 'secondary_diagnostic_error'}
    need(type(diagnostic) is dict and required <= set(diagnostic)
         and set(diagnostic) <= required | optional
         and diagnostic['schema'] == 'retained-identity-image-failure-v1'
         and diagnostic['handle_classification'] == 'PREVIOUSLY_RETAINED_MEMBER'
         and diagnostic['exact_previously_retained_handle'] is True
         and diagnostic['new_PID_Open'] is False and diagnostic['VM_RPM'] is False
         and diagnostic['query_used_for_admission'] is False
         and type(diagnostic['pid_argument']) is int and 0 < diagnostic['pid_argument'] <= 0xffffffff
         and type(diagnostic['expected_birth']) is str
         and diagnostic['expected_birth'].isdigit() and len(diagnostic['expected_birth']) <= 20
         and type(diagnostic['known_exit']) is bool, 'EXACT_CP53_FOLLOWUP_DIAGNOSTIC')
    reference = diagnostic['call_reference']
    need(set(reference) == {'call_id', 'operation', 'caller_stage', 'same_call_as_public_record', 'original_winerror'}
         and reference['call_id'] == 2 and reference['operation'] == 'QueryFullProcessImageNameW'
         and reference['same_call_as_public_record'] is False
         and type(reference['original_winerror']) is int and 0 <= reference['original_winerror'] <= 0xffffffff
         and type(reference['caller_stage']) is list and len(reference['caller_stage']) <= 4,
         'EXACT_CP53_FOLLOWUP_REFERENCE')
    for stage in reference['caller_stage']:
        need(set(stage) == {'source', 'operation', 'line'}
             and type(stage['source']) is str and len(stage['source']) <= 256
             and type(stage['operation']) is str and len(stage['operation']) <= 128
             and type(stage['line']) is int and stage['line'] >= 0, 'BOUNDED_CP53_CALLER_STAGE')
    if diagnostic['known_exit']:
        expected = diagnostic['expected_birth']
        need(diagnostic.get('wait_after', {}).get('result') == 0
             and diagnostic['original_GetProcessTimes']['birth'] == expected
             and diagnostic.get('fallback_GetProcessTimes', {}).get('succeeded') is True
             and diagnostic['fallback_GetProcessTimes']['birth'] == expected
             and diagnostic.get('GetExitCodeProcess', {}).get('succeeded') is True
             and diagnostic['GetExitCodeProcess']['exit_code'] != 259, 'EXISTING_KNOWN_EXIT_PREDICATE_REQUIRED')
    raw = (json.dumps(row, indent=2) + '\n').encode('utf-8')
    need(len(raw) <= PUBLIC_LIMIT, 'CP53_FOLLOWUP_PUBLIC_SIZE_BOUND')
    return raw


class Recorder(base.Recorder):
    def __init__(self, work):
        super().__init__(work)
        self.followup = None
        self._first_attempted = False
        self._first_binding = None
        self._followup_attempted = False

    def _reference_only(self, winerror):
        self.sequence += 1
        reference = {'call_id': self.sequence, 'operation': 'QueryFullProcessImageNameW',
                     'caller_stage': base.caller_stage(), 'same_call_as_public_record': False,
                     'original_winerror': winerror}
        self.last_reference = reference
        return reference, None, None

    def _same_retained_member(self, owner, handle, pid):
        if self._first_binding is None:
            return False
        first_owner, first_handle, first_pid, first_main, first_member, first_job = self._first_binding
        if owner is not first_owner or handle != first_handle or pid != first_pid:
            return False
        main, member, role = self.match(owner, handle, pid)
        return (main is first_main and member is first_member and member is not None
                and role == 'PREVIOUSLY_RETAINED_MEMBER' and main.job == first_job
                and bool(first_job) and member.process == handle
                and member.identity.get('birth') == self.record['expected_birth'])

    def failure(self, owner, handle, pid, times, winerror, started, finished):
        if not self._first_attempted:
            self._first_attempted = True
            returned = super().failure(owner, handle, pid, times, winerror, started, finished)
            if self.record is not None and self.record['exact_previously_retained_handle'] is True:
                main, member, role = self.match(owner, handle, pid)
                if main is not None and member is not None and role == 'PREVIOUSLY_RETAINED_MEMBER':
                    self._first_binding = (owner, handle, pid, main, member, main.job)
            return returned
        if (self.sequence != 1 or self._followup_attempted
                or not self._same_retained_member(owner, handle, pid)):
            return self._reference_only(winerror)
        self._followup_attempted = True
        # Invoke the frozen diagnostic once in an isolated recorder. Its exact
        # birth/wait/non259 predicate and same-handle native calls are unchanged.
        # The original first row and the native image-query refusal are preserved.
        second = base.Recorder(self.work)
        second.sequence = self.sequence
        try:
            returned = second.failure(owner, handle, pid, times, winerror, started, finished)
            reference, member, exitcode = returned
            reference['same_call_as_public_record'] = False
            self.sequence = second.sequence
            self.last_reference = reference
            self.followup = second.record
            return reference, member, exitcode
        finally:
            self.sequence = second.sequence
            self.last_reference = second.last_reference
            C.set_last_error(winerror)

    def finish(self, report):
        super().finish(report)
        if self.followup is None:
            return
        row = {'schema': 'retained-identity-image-followup-v1', 'first_call_id': 1,
               'followup_call_id': 2, 'maximum_additional_diagnostics': 1,
               'same_exact_retained_handle': True, 'new_PID_open': False, 'VM_RPM': False,
               'diagnostic': self.followup,
               'final_exception_reference': report.get('fatal_identity_failure_reference'),
               'original_guard_predicate_changed': False, 'same_existing_known_exit_predicate': True}
        raw = validate_public(row)
        with (self.work / 'identity-failure-followup.json').open('xb') as stream:
            stream.write(raw)
        report['identity_followup_public_record'] = row


def install_runtime_factory(core):
    """Select this recorder only while the frozen runtime constructs its factory."""
    original = core.identity.Recorder
    need(Path(original.failure.__code__.co_filename) == PARENT
         and original.failure.__code__.co_code == base.Recorder.failure.__code__.co_code,
         'EXACT_FROZEN_RUNTIME_IDENTITY_RECORDER')
    core.identity.Recorder = Recorder
    return original
