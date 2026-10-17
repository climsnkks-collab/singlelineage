"""Offline fixtures for bounded diagnostics and the unchanged cleanup boundary."""
import ast
import asyncio
import contextlib
import importlib.util
import json
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('_cp73_tail_fixture_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def run_checks():
    checks = []
    module = load('helper_failure_tail')
    trusted = {
        'frames': {'auto_enter_tile_render.py': ['run', '<module>'], '게임.py': ['실행'],
                   'a.py': ['f']},
        'exception_types': ['ValueError', 'RuntimeError', 'TypeError'],
        'reason_constants': ['EXACT_OWNED_HANDLE_REQUIRED', 'region_not_readable'],
    }

    def fixture(text, code=1):
        return module.diagnostic(text if isinstance(text, bytes) else text.encode('utf-8'), code, False, trusted)

    long_traceback = ('Traceback (most recent call last):\n'
                      + '  File "C:\\ignored\\auto_enter_tile_render.py", line 226, in <module>\n'
                      + '    payload = "NEVER_KEEP_BODY"\n') * 40
    long_traceback += ('  File "C:\\project\\auto_enter_tile_render.py", line 213, in run\n'
                       '    dump(memory_bytes)\n'
                       'ValueError: EXACT_OWNED_HANDLE_REQUIRED\n')
    row = fixture(long_traceback)
    need(row['stderr_input_tail_truncated'] and row['exception_type'] == 'ValueError'
         and row['reason_constant'] == 'EXACT_OWNED_HANDLE_REQUIRED'
         and row['final_frame'] == {'file': 'auto_enter_tile_render.py', 'line': 213, 'function': 'run'}
         and len(row['stderr_tail']) <= 1600
         and all(s not in json.dumps(row) for s in ['NEVER_KEEP_BODY', 'memory_bytes', 'C:\\project']),
         'LONG_TRACEBACK_FINAL_EXCEPTION_STRUCTURAL_TAIL')
    checks.append('helper_tail_long_traceback_prefix_overflow_final_exception_exact')
    row = fixture(b'')
    need(row['reason_constant'] == 'NO_STDERR_OUTPUT' and row['exception_type'] == 'UNKNOWN'
         and row['stderr_tail'] == '' and row['final_frame'] is None,
         'EMPTY_STDERR_UNKNOWN_NOT_INVENTED')
    checks.append('helper_tail_no_output_unknown_no_invented_exception')
    row = fixture('가' * 1700 + '\n  File "C:\\프로젝트\\게임.py", line 9, in 실행\n'
                  'ValueError: region_not_readable\n')
    need(row['stderr_examined_tail_characters'] == 1600
         and row['stderr_total_bytes'] > row['stderr_total_decoded_characters']
         and row['final_frame'] == {'file': '게임.py', 'line': 9, 'function': '실행'}
         and row['reason_constant'] == 'region_not_readable'
         and len(row['stderr_tail']) <= 1600, 'UTF8_CHAR_BOUND_NOT_BYTE_SPLIT')
    checks.append('helper_tail_multibyte_utf8_character_bound_frame_basename')
    row = fixture(b'\xff\xfe\nValueError: region_not_readable\n')
    need(row['reason_constant'] == 'region_not_readable' and '\ufffd' not in row['stderr_tail'],
         'INVALID_UTF8_REPLACED_AND_NONSTRUCTURAL_DISCARDED')
    checks.append('helper_tail_invalid_utf8_nonstructural_discarded')
    row = fixture('ValueError: EXACT_OWNED_HANDLE_REQUIRED\n\n'
                  'During handling of the above exception, another exception occurred:\n\n'
                  'Traceback (most recent call last):\n'
                  '  File "auto_enter_tile_render.py", line 213, in run\n'
                  'RuntimeError: UNTRUSTED_PAYLOAD_SECRET_0x7ABC\n')
    need(row['exception_type'] == 'RuntimeError' and row['reason_constant'] == 'UNKNOWN_REASON_CONSTANT'
         and 'UNTRUSTED_PAYLOAD' not in json.dumps(row), 'CHAIN_FINAL_EXCEPTION_ONLY')
    checks.append('helper_tail_chained_final_exception_only_untrusted_reason_redacted')
    row = fixture('ValueError: region_not_readable\nUNTRUSTED_FINAL_LINE\n')
    need(row['exception_type'] == 'UNKNOWN' and not row['final_exception_parsed'],
         'NONEXCEPTION_FINAL_LINE_MUST_NOT_REUSE_EARLIER_EXCEPTION')
    checks.append('helper_tail_unknown_final_line_prior_exception_not_promoted')
    row = fixture('  File "PRIVATE_BODY.py", line 6, in raw_memory\n'
                  '    image_base64 = "DO_NOT_RECORD"\n'
                  'ValueError: region_not_readable:0xdeadbeef raw payload\n')
    need(row['final_frame'] is None and row['reason_constant'] == 'region_not_readable'
         and all(s not in json.dumps(row) for s in ['PRIVATE_BODY', 'DO_NOT_RECORD', '0xdeadbeef']),
         'ONLY_ALLOWLISTED_FRAME_AND_CONSTANT_NO_DETAILS')
    checks.append('helper_tail_source_payload_image_address_path_details_discarded')
    row = fixture('Traceback (most recent call last):\n'
                  + ''.join(f'  File "a.py", line {n}, in f\n' for n in range(30))
                  + 'TypeError: private message\n')
    need(row['frame_count_in_tail'] == 30 and row['frames_truncated']
         and len(row['frames']) == 6 and row['final_frame']['line'] == 29
         and row['exception_type'] == 'TypeError' and row['reason_constant'] == 'UNKNOWN_REASON_CONSTANT',
         'FRAME_BOUND_LAST_SIX_FINAL_FRAME')
    checks.append('helper_tail_last_six_frames_count_truncation_final_frame')
    row = fixture('ValueError: ' + 'A' * 10000 + '\n')
    need(row['exception_type'] == 'UNKNOWN' and len(row['stderr_tail']) <= 1600,
         'HUGE_FINAL_LINE_REFUSED_NOT_SCANNED_OUTSIDE_TAIL')
    checks.append('helper_tail_huge_arbitrary_final_message_unknown_bounded')
    actual_catalogue = module.catalogue()
    need('ValueError' in actual_catalogue['exception_types']
         and 'region_not_readable' in actual_catalogue['reason_constants']
         and 'auto_enter_tile_render.py' in actual_catalogue['frames'],
         'EXACT_FROZEN_SOURCE_CATALOGUE_AVAILABLE')
    checks.append('helper_tail_frozen_source_error_catalogue_SHA_verified')
    root = load('root-control')
    with tempfile.TemporaryDirectory(prefix='cp73-tail-fixture-') as directory:
        path = Path(directory) / 'helper-failure-tail.json'
        root.save(path, fixture('ValueError: region_not_readable\n'))
        try:
            root.save(path, {})
        except FileExistsError:
            pass
        else:
            raise ValueError('FAILURE_TAIL_CREATE_NEW_REQUIRED')
    checks.append('helper_tail_output_create_new_existing_file_never_overwritten')

    async def cleanup_fixture(actual_raises=False, stop_raises=False, diagnostic_raises=False):
        root = load('root-control')
        events = []
        helper = types.SimpleNamespace(returncode=1)

        async def communicate():
            events.append('communicate')
            return b'', b'ValueError: region_not_readable\n'

        helper.communicate = communicate

        async def create(*args, **kwargs):
            events.append('helper_already_exited')
            return helper

        async def actual():
            events.append('actual_owned_cleanup')
            if actual_raises:
                raise RuntimeError('INJECTED_ACTUAL_FAILURE')
            return {'restoration_safe_after_owned_cleanup': True}

        async def stop(p):
            events.append('stop_helper')
            if stop_raises:
                raise RuntimeError('INJECTED_STOP_FAILURE')

        def tail(stderr, rc, created):
            events.append('helper_failure_tail')
            if diagnostic_raises:
                raise RuntimeError('INJECTED_DIAGNOSTIC_FAILURE')
            return fixture(stderr, rc)

        @contextlib.contextmanager
        def backend():
            yield None

        slot = types.SimpleNamespace(fixed_backend=backend, execute=lambda action, b: events.append(action))
        runtime = types.SimpleNamespace(
            B=types.SimpleNamespace(RUN_ID='fixture', CANDIDATE=Path('fixture'), CANDIDATE_SHA='fixture'),
            OBSERVER=types.SimpleNamespace(FORWARD_ROOT=Path('fixture')),
            slot_api=lambda: types.SimpleNamespace(module=lambda: slot),
            runtime_api=lambda: types.SimpleNamespace(actual=actual))
        original_create = asyncio.create_subprocess_exec
        try:
            asyncio.create_subprocess_exec = create
            with tempfile.TemporaryDirectory(prefix='cp73-cleanup-fixture-') as directory:
                root.WORK = Path(directory)
                (root.WORK / 'slot').mkdir()
                (root.WORK / 'slot/transactions.json').write_text('{"events":[{"phase":"PREPARED"}]}', encoding='utf-8')
                root.runtime = lambda: runtime
                root.verify_review = lambda r: None
                root.installed_reviews = lambda r: events.append('installed_reviews')
                root.sha = lambda p: root.AUTO_SHA
                root.stop_helper = stop
                root.restore_control = lambda r: events.append('RestoreControl')
                root.helper_failure_tail = tail
                try:
                    result = await root.trial()
                    need(not actual_raises and not stop_raises and not diagnostic_raises and result == 2,
                         'FAILED_HELPER_RESULT_CODE')
                    need((root.WORK / 'helper-failure-tail.json').is_file()
                         and json.loads((root.WORK / 'auto-helper-exit.json').read_bytes())['schema']
                         == 'cp65-land-probe-helper-exit-v1', 'TAIL_AND_COMPATIBLE_PREFIX_CREATED')
                except RuntimeError as error:
                    expected_error = ('INJECTED_STOP_FAILURE' if stop_raises
                                      else 'INJECTED_DIAGNOSTIC_FAILURE' if diagnostic_raises
                                      else 'INJECTED_ACTUAL_FAILURE')
                    need(str(error) == expected_error,
                         'EXPECTED_INJECTED_CLEANUP_ERROR')
                need(events.index('helper_already_exited') < events.index('actual_owned_cleanup')
                     and events[-1] == 'RestoreControl', 'EARLY_HELPER_EXIT_MUST_NOT_SKIP_ACTUAL_OR_RESTORE')
        finally:
            asyncio.create_subprocess_exec = original_create
        return events

    asyncio.run(cleanup_fixture())
    checks.append('helper_exit_before_actual_preserves_actual_owned_cleanup_and_slot_restore')
    asyncio.run(cleanup_fixture(actual_raises=True))
    checks.append('actual_exception_preserves_stop_helper_then_slot_restore')
    asyncio.run(cleanup_fixture(stop_raises=True))
    checks.append('nested_finally_stop_helper_exception_cannot_skip_slot_restore')
    asyncio.run(cleanup_fixture(diagnostic_raises=True))
    checks.append('new_diagnostic_exception_cannot_skip_owned_cleanup_or_slot_restore')
    tree = ast.parse((HERE / 'root-control.py').read_bytes())
    trial = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'trial')
    outer = next(n for n in trial.body if isinstance(n, ast.Try))
    nested = outer.finalbody[0]
    need(isinstance(nested, ast.Try) and nested.finalbody, 'NESTED_FINALLY_PRESENT')
    checks.append('nested_finally_AST_preserved_for_root_owned_cleanup')
    return checks
