"""Virtual-clock fixtures for the one source-bound context wait change."""
import ast
import copy
import importlib.util
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HELPER = ROOT / 'tools/local_native_auto_login/auto_enter_land_probe_context_wait.py'


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def run_checks():
    paths = sys.path[:]
    try:
        sys.path.insert(0, str(HELPER.parent))
        spec = importlib.util.spec_from_file_location('_cp54_context_wait_fixture_helper', HELPER)
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
    finally:
        sys.path[:] = paths
    checks = []
    original = ast.parse(helper.BASE.read_bytes(), str(helper.BASE))
    original_run = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
    variant_run = helper.context_wait_tree().body[0]
    original_context = next(node for node in original_run.body if isinstance(node, ast.Assign)
                            and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'context')
    variant_context = next(node for node in variant_run.body if isinstance(node, ast.Assign)
                           and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'context')
    need(original_context.value.args[1].value == 110 and variant_context.value.args[1].value == 240,
         'FIRST_CONTEXT_WAIT_EXACT_110_TO240')
    restored = copy.deepcopy(variant_run)
    context = next(node for node in restored.body if isinstance(node, ast.Assign)
                   and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'context')
    context.value.args[1].value = 110
    need(ast.dump(restored, include_attributes=False) == ast.dump(original_run, include_attributes=False),
         'ONLY_CONTEXT_LITERAL_CHANGED')
    checks.append('whole_frozen_run_AST_identical_except_first_context_110_to240')
    original_waits = [ast.unparse(node) for node in ast.walk(original_run)
                      if isinstance(node, ast.Call) and ast.unparse(node.func) == 'parent.wait']
    restored_waits = [ast.unparse(node) for node in ast.walk(restored)
                      if isinstance(node, ast.Call) and ast.unparse(node.func) == 'parent.wait']
    need(original_waits == restored_waits, 'ALL_READINESS_AND_SELECTION_WAITS_UNCHANGED')
    need(sum(isinstance(node, ast.Call) and ast.unparse(node) == 'time.sleep(1)'
             for node in ast.walk(variant_run)) == 1, 'ONE_SECOND_AUTOMATIC_DELAY_UNCHANGED')
    checks.append('all_later_waits_and_Login_ACK_then_one_second_action_unchanged')

    class Clock:
        def __init__(self):
            self.elapsed = 0.0

        def monotonic(self):
            return self.elapsed

        def sleep(self, seconds):
            need(seconds == 0.1, 'ORIGINAL_POLL_INTERVAL_UNCHANGED')
            self.elapsed += seconds

    def wait_context(run, delay):
        clock = Clock()
        wait = types.FunctionType(helper.parent.wait.__code__, {'time': clock}, 'wait')
        context_value = {'candidate_sha256': 'fixture', 'pid': 123, 'birth': '12345'}
        path = types.SimpleNamespace(is_file=lambda: clock.elapsed >= delay,
                                     read_bytes=lambda: b'fixture')
        watch = types.SimpleNamespace(contract_for=lambda *args, **kwargs: {})
        parent = types.SimpleNamespace(need=need, WATCH=object(), load=lambda *args: watch, wait=wait)
        function = copy.deepcopy(run)
        index = next(index for index, node in enumerate(function.body)
                     if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                     and node.targets[0].id == 'context')
        function.body = function.body[:index + 1] + [ast.Return(value=ast.Name(id='context', ctx=ast.Load()))]
        namespace = {'parent': parent, 'json': types.SimpleNamespace(loads=lambda raw: context_value)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     'cp54_first_context_fixture', 'exec'), namespace)
        try:
            result = namespace['run'](None, 'fixture', path, None,
                                      types.SimpleNamespace(exists=lambda: False))
            return result, clock.elapsed
        except ValueError as error:
            need(str(error) == 'AUTO_OK_TRIGGER_TIMEOUT', 'ORIGINAL_CONTEXT_TIMEOUT_CODE')
            return None, clock.elapsed

    old, elapsed = wait_context(original_run, 125)
    need(old is None and elapsed < 111, 'OLD110_TIMEOUT_REPRODUCED')
    checks.append('virtual_context_delay125_old110_expires')
    for delay in (125, 239):
        result, elapsed = wait_context(variant_run, delay)
        need(result is not None and delay <= elapsed < delay + .2, 'CONTEXT_WITHIN240_ACCEPTED')
        checks.append('virtual_context_delay' + str(delay) + '_accepted_by240')
    result, elapsed = wait_context(variant_run, 250)
    need(result is None and 240 <= elapsed < 240.2, 'CONTEXT240_FINITE_BOUND')
    checks.append('virtual_context_delay250_refused_at240_no_unbounded_wait')
    original_load = helper.parent.load
    base_module = types.ModuleType('_cp54_fixture_frozen_base')
    fixture_land = types.SimpleNamespace(parent=helper.parent)

    def source_load(path, name):
        return fixture_land if Path(path) == helper.LAND else base_module

    def failed_run(*args):
        module = fixture_land.parent.load(helper.BASE, 'fixture')
        need(module is base_module and 240 in module.run.__code__.co_consts
             and 110 not in module.run.__code__.co_consts, 'ACTUAL_LOADER_CONTEXT_VARIANT')
        raise ValueError('fixture_failure')

    fixture_land.run = failed_run
    helper.parent.load = source_load
    try:
        try:
            helper.run(None, 'fixture', None, None, None)
            raise AssertionError('FIXTURE_FAILURE_NOT_PROPAGATED')
        except ValueError as error:
            need(str(error) == 'fixture_failure', 'ORIGINAL_FAILURE_PROPAGATED')
        need(helper.parent.load is source_load, 'LOADER_RESTORED_AFTER_FAILURE')
    finally:
        helper.parent.load = original_load
    checks.append('actual_source_loader_targets_only_frozen_base_and_finally_restores')
    return checks


if __name__ == '__main__':
    import json
    rows = run_checks()
    print(json.dumps({'status': 'PASS_VIRTUAL_CLOCK_SOURCE_FIXTURES', 'checks': rows,
                      'game_slot_Native_uac_actions': 0}))
