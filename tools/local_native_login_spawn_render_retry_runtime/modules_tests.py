"""Virtual-clock/source module readiness fixtures; no actual Native or game."""
import ast
import copy
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUTO = ROOT / 'tools/local_native_auto_login/auto_enter_land_probe_modules.py'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def run_checks():
    paths = sys.path[:]
    try:
        sys.path.insert(0, str(AUTO.parent))
        spec = importlib.util.spec_from_file_location('_cp55_modules_fixture', AUTO)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        context = helper.parent.load(helper.CONTEXT, '_cp55_frozen_context_fixture')
    finally:
        sys.path[:] = paths
    checks = []
    before = context.context_wait_tree()
    after = helper.module_wait_tree(context)
    module_assignment = next(node for node in ast.walk(after.body[0]) if isinstance(node, ast.Assign)
                             and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'modules')
    need(module_assignment.value.args[1].value == 35, 'MODULE_WAIT35')
    restored = copy.deepcopy(after)
    statement = next(node for node in ast.walk(restored.body[0]) if isinstance(node, ast.Assign)
                     and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'modules')
    statement.value.args[1].value = 20
    need(ast.dump(restored, include_attributes=False) == ast.dump(before, include_attributes=False),
         'ONLY_MODULE_WAIT20_TO35_CHANGED')
    checks.append('whole_CP54_run_AST_identical_except_module_wait20_to35')
    ctx = next(node for node in after.body[0].body if isinstance(node, ast.Assign)
               and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'context')
    need(ctx.value.args[1].value == 240
         and sum(isinstance(node, ast.Call) and ast.unparse(node) == 'time.sleep(1)'
                 for node in ast.walk(after)) == 1, 'CONTEXT240_AND_AUTOMATIC_ONE_SECOND_UNCHANGED')
    checks.append('context240_and_all_other_Login_ACK_selection_readiness_waits_unchanged')

    class Failure(Exception):
        def __init__(self, reason, code=None):
            self.reason = reason
            self.native_error = code
            self.region = {'raw_address': 0x7abcdef, 'path': 'PRIVATE_PATH'}

    class Native:
        def __init__(self):
            self.handle = object()
            self.expected = {'pid': 123, 'birth': '12345'}
            self.calls = 0
            self.error = None

        def modules(self):
            self.calls += 1
            if self.error is not None:
                raise self.error
            return {'LC': {'base': 0x7abcdef, 'size': 1000}}

        def validate(self):
            raise AssertionError('NO_EXTRA_VALIDATE_QUERY')

        def OpenProcess(self, *args):
            raise AssertionError('NO_NEW_PID_OPEN')

    native = Native()
    diagnostic = helper.Diagnostic('0' * 64)
    attempt = helper.diagnostic_try_modules(diagnostic)
    native.error = Failure('module_query_denied', 299)
    need(attempt(native) is None, 'ORIGINAL_299_SWALLOWED')
    native.error = Failure('original_image_layout_unknown')
    need(attempt(native) is None, 'ORIGINAL_LAYOUT_UNKNOWN_SWALLOWED')
    native.error = None
    result = attempt(native)
    row = diagnostic.public()
    need(native.calls == diagnostic.attempts == 3 and row['module_snapshot_ever_succeeded'] is True
         and row['failure_counts'] == [
             {'reason': 'module_query_denied', 'native_error': 299, 'count': 1},
             {'reason': 'original_image_layout_unknown', 'native_error': None, 'count': 1}]
         and result['LC']['base'] == 0x7abcdef, 'SINGLE_EXISTING_QUERY_AND_CONSTANT_FAILURE_METADATA')
    checks.append('one_existing_modules_query_per_attempt_original_swallowed_cases_preserved')
    public = helper.validate_public(row).decode('utf-8')
    need('PRIVATE_PATH' not in public and '128683503' not in public
         and '"base"' not in public and '"region"' not in public and '"handle"' not in public,
         'NO_RAW_MODULE_PATH_POINTER_HANDLE_OR_REGION')
    checks.append('public_failure_aggregate_has_no_raw_module_paths_pointers_handles_or_bytes')
    for reason, code in (('module_query_denied', 5), ('unknown PRIVATE_PATH pointer0x7abcdef', 7)):
        native = Native()
        native.error = Failure(reason, code)
        diagnostic = helper.Diagnostic('0' * 64)
        try:
            helper.diagnostic_try_modules(diagnostic)(native)
            raise AssertionError('ORIGINAL_ERROR_SWALLOWED')
        except Failure as error:
            need(error is native.error and native.calls == diagnostic.attempts == 1,
                 'EXACT_ORIGINAL_ERROR_PROPAGATED')
        need(diagnostic.public()['failure_counts'][0]['reason'] in {'module_query_denied', 'OTHER'},
             'CONSTANT_REASON_ONLY')
        checks.append('non_swallowed_failure_original_exception_propagates:' + str(code))
    native = Native()
    diagnostic = helper.Diagnostic('0' * 64)
    attempt = helper.diagnostic_try_modules(diagnostic)
    attempt(native)
    native.handle = object()
    try:
        attempt(native)
        raise AssertionError('HANDLE_RETARGETED')
    except ValueError as error:
        need(str(error) == 'EXACT_RETAINED_MODULE_NATIVE_REQUIRED' and native.calls == 1,
             'HANDLE_CHANGED_BEFORE_NEW_QUERY_REFUSED')
    checks.append('changed_retained_handle_refused_before_query')

    class Clock:
        def __init__(self):
            self.elapsed = 0.0

        def monotonic(self):
            return self.elapsed

        def sleep(self, seconds):
            need(seconds == .1, 'ORIGINAL_POLL_INTERVAL')
            self.elapsed += seconds

    def wait_fixture(seconds, ready_at):
        clock = Clock()
        native = Native()
        diagnostic = helper.Diagnostic('0' * 64)
        original_modules = native.modules
        def modules():
            native.error = Failure('original_image_layout_unknown') if clock.elapsed < ready_at else None
            return original_modules()
        native.modules = modules
        attempt = helper.diagnostic_try_modules(diagnostic)
        wait = types.FunctionType(helper.parent.wait.__code__, {'time': clock}, 'wait')
        try:
            result = wait(lambda: attempt(native), seconds)
        except ValueError as error:
            need(str(error) == 'AUTO_OK_TRIGGER_TIMEOUT', 'ORIGINAL_WAIT_TIMEOUT')
            result = None
        return result, clock.elapsed, diagnostic, native

    result, elapsed, diagnostic, native = wait_fixture(20, 25)
    need(result is None and elapsed < 20.2 and diagnostic.succeeded is False, 'CP54_MODULE20_TIMEOUT')
    checks.append('virtual_module_ready25_old20_expires')
    result, elapsed, diagnostic, native = wait_fixture(35, 25)
    need(result is not None and 25 <= elapsed < 25.2 and diagnostic.succeeded is True
         and native.calls == diagnostic.attempts, 'MODULE25_READY_WITHIN35')
    checks.append('virtual_module_ready25_new35_accepts_no_extra_query')
    result, elapsed, diagnostic, native = wait_fixture(35, 40)
    need(result is None and 35 <= elapsed < 35.2 and diagnostic.succeeded is False
         and native.calls == diagnostic.attempts <= 351, 'FINITE35_NO_FALSE_SUCCESS')
    checks.append('virtual_module_unavailable40_timeout35_bounded_attempts_no_success_claim')
    native = Native()
    native.error = Failure('original_image_layout_unknown')
    diagnostic = helper.Diagnostic('0' * 64)
    attempt = helper.diagnostic_try_modules(diagnostic)
    for _ in range(helper.MAX_ATTEMPTS):
        attempt(native)
    try:
        attempt(native)
        raise AssertionError('ATTEMPT_BOUND_IGNORED')
    except ValueError as error:
        need(str(error) == 'BOUNDED_MODULE_ATTEMPTS_REQUIRED' and native.calls == 351,
             'NO_QUERY_AFTER_ATTEMPT_BOUND')
    checks.append('absolute351_attempt_limit_before_query')
    invalid = diagnostic.public()
    invalid['failure_counts'][0]['reason'] = 'PRIVATE_PATH'
    try:
        helper.validate_public(invalid)
        raise AssertionError('RAW_REASON_ALLOWED')
    except ValueError:
        pass
    checks.append('public_schema_rejects_nonconstant_reason')
    with tempfile.TemporaryDirectory(prefix='cp55-module-fixture-') as directory:
        original_load, original_try = helper.parent.load, helper.parent.try_modules
        land = types.SimpleNamespace(parent=helper.parent)
        base = types.ModuleType('_cp55_fixture_base')
        native = Native()
        native.error = Failure('module_query_denied', 5)
        def load(path, name):
            return context if Path(path) == helper.CONTEXT else land if Path(path) == helper.LAND else base
        def failure(*args):
            module = land.parent.load(helper.BASE, 'fixture')
            need(module is base and 240 in module.run.__code__.co_consts
                 and 35 in module.run.__code__.co_consts, 'ACTUAL_MODULE_WAIT_VARIANT_LOADER')
            land.parent.try_modules(native)
        land.run = failure
        helper.parent.load = load
        output = Path(directory) / 'auto-ok-result.json'
        try:
            try:
                helper.run(None, '0' * 64, None, None, output)
                raise AssertionError('ORIGINAL_FAILURE_NOT_PROPAGATED')
            except Failure as error:
                need(error is native.error, 'ORIGINAL_MODULE_FAILURE_PRESERVED')
            need(helper.parent.load is load and helper.parent.try_modules is original_try,
                 'ORIGINAL_LOADER_AND_TRY_MODULES_RESTORED')
            path = output.with_name('module-readiness-diagnostic.json')
            row = json.loads(path.read_bytes())
            need(row['attempt_count'] == 1 and row['module_snapshot_ever_succeeded'] is False
                 and row['helper_completed'] is False and path.stat().st_size <= helper.PUBLIC_LIMIT,
                 'BOUNDED_FAILURE_FILE_WRITTEN')
            checks.append('failure_finally_restores_loader_try_modules_and_writes_bounded_diagnostic')
            before = native.calls
            try:
                helper.run(None, '0' * 64, None, None, output)
                raise AssertionError('DIAGNOSTIC_OVERWRITTEN')
            except ValueError as error:
                need(str(error) == 'CREATE_NEW_MODULE_DIAGNOSTIC_REQUIRED'
                     and native.calls == before, 'CREATE_NEW_BEFORE_QUERY')
            checks.append('existing_diagnostic_refused_before_native_query')
        finally:
            helper.parent.load, helper.parent.try_modules = original_load, original_try
    return checks


if __name__ == '__main__':
    rows = run_checks()
    print(json.dumps({'status': 'PASS_MODULE_SOURCE_AND_VIRTUAL_CLOCK_FIXTURES',
                      'checks': rows, 'actual_Native_game_slot_uac_actions': 0}))
