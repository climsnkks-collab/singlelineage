"""CP74 namespace/capture delta + actual factory + static/injected/self API checks."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / 'tools/local_native_login_spawn_candidate_runtime'
ADAPTER = ROOT / 'tools/local_native_login_spawn_render_runtime'

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def suite(path, name, count):
    result = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromModule(load(path, name)))
    need(result.wasSuccessful() and result.testsRun == count, 'EXACT_INJECTED_SUITE:' + name)
    return result.testsRun

def main():
    checks = []
    transform = json.loads((HERE / 'namespace-pin-transform.json').read_bytes())
    builder = load(HERE / 'create_successor.py', '_cp74_declared_builder')
    for directory, prefix in ((PRIOR, 'prior'), (ADAPTER, 'adapter')):
        need(sha(directory / 'source-freeze.json') == transform[prefix + '_freeze_sha256'], 'IMMUTABLE_FREEZE:' + prefix)
        frozen = builder.verify_freeze(directory)
        need(frozen['files_sha256'] == transform[prefix + '_files_sha256'], 'EXACT_FROZEN_CONTENT:' + prefix)
        checks.append(prefix + '_entire_frozen_source_preserved')
    for path in sorted(HERE.glob('*.py')):
        compile(path.read_bytes(), str(path), 'exec'); checks.append('syntax:' + path.name)
    for name in transform['copied_python']:
        expected = builder.declared(name, transform['sha_literal_replacements'])
        actual = (HERE / name).read_bytes()
        need(actual == expected, 'WHOLE_CP73_DECLARED_DELTA_BYTES:' + name)
        need(ast.dump(ast.parse(actual), include_attributes=False) == ast.dump(ast.parse(expected), include_attributes=False), 'WHOLE_CP73_DECLARED_DELTA_AST:' + name)
        checks.extend(('CP73_declared_delta_bytes:' + name, 'CP73_declared_delta_AST:' + name))
    for name in transform['copied_pinsets']:
        if name not in ('runtime-evidence-pins.json', 'spawn-profile-pins.json'):
            need((HERE / name).read_bytes() == (PRIOR / name).read_bytes(), 'UNCHANGED_PINSET:' + name)
            checks.append('unchanged_pinset:' + name)
    for name in ('actor_profile.py', 'actor-profile.json', 'inspect_tile.py'):
        need((HERE / name).read_bytes() == (PRIOR / name).read_bytes(), 'EXACT_CP73_SPAWN_TILE:' + name)
        checks.append('CP73_byte_identical_spawn_tile:' + name)
    expected_spawn_pins = json.loads((PRIOR / 'spawn-profile-pins.json').read_bytes())
    for name in ('actor_profile.py', 'actor-profile.json'):
        expected_spawn_pins[(HERE / name).relative_to(ROOT).as_posix()] = sha(HERE / name)
    need(json.loads((HERE / 'spawn-profile-pins.json').read_bytes()) == expected_spawn_pins, 'EXACT_NAMESPACE_ACTOR_PROFILE_PIN_ADDITIONS')
    checks.append('CP73_hook_only_new_namespace_profile_pinset_SHA_rebind_all_original_guards_preserved')
    evidence = json.loads((HERE / 'runtime-evidence-pins.json').read_bytes())
    old_evidence = json.loads((PRIOR / 'runtime-evidence-pins.json').read_bytes())
    expected_evidence = dict(old_evidence)
    for directory, prefix in ((PRIOR, 'prior'), (ADAPTER, 'adapter')):
        expected_evidence.update({(directory / n).relative_to(ROOT).as_posix(): v for n, v in transform[prefix + '_files_sha256'].items()})
        expected_evidence[(directory / 'source-freeze.json').relative_to(ROOT).as_posix()] = sha(directory / 'source-freeze.json')
    expected_evidence.update(json.loads((ADAPTER / 'dependency-pins.json').read_bytes()))
    for name in ('image_alt.py', 'queries.py', 'diagnostic.py', 'actor_profile.py', 'actor-profile.json', 'spawn_hook.py', 'spawn-profile-pins.json', 'inspect_tile.py'):
        expected_evidence[(HERE / name).relative_to(ROOT).as_posix()] = sha(HERE / name)
    need(evidence == expected_evidence and set(evidence) - set(old_evidence) == set(transform['runtime_evidence_added_paths']), 'EXACT_ADDITIVE_RUNTIME_EVIDENCE')
    checks.append('exact_CP73_CP74_frozen_evidence_and_new_runtime_paths_no_prior_pin_changes')
    store = ROOT / 'work/standalone_boot/owned-local-profile/characters.json'
    store_sha = sha(store)
    need(store_sha == '563edcf5ecb9d878f8826151e334ff034d88dfe0a914c6a4b76c21de3005f395', 'IMMUTABLE_CHARACTER_STORE')
    factory = load(HERE / 'fix.py', '_cp74_static_factory')
    api = factory.source_api(); pins = api.pins()
    need(all((ROOT / k).is_file() and (ROOT / k).stat().st_nlink == 1 and (ROOT / k).stat().st_size <= 2097152 and sha(ROOT / k) == v for k, v in pins.items()), 'EXACT_SMALL_LIVE_PINS')
    api.verify_files()
    need(all(pins[k] == v for k, v in evidence.items()), 'ACTUAL_FACTORY_EVIDENCE_CLOSURE')
    checks.append('actual_CP74_source_api_pins_and_verify_files_PASS')
    root = load(HERE / 'root-control.py', '_cp74_static_root')
    helper = load(HERE / 'auto_enter_tile_render.py', '_cp74_static_helper')
    need(sha(root.AUTO) == root.AUTO_SHA and sha(HERE / 'identity_adapter.py') == root.IDENTITY_SHA and sha(HERE / 'helper_failure_tail.py') == root.TAIL_SHA, 'ROOT_HELPER_IDENTITY_TAIL_EXACT')
    need(helper.TILE == HERE / 'inspect_tile.py' and sha(helper.TILE) == helper.TILE_SHA and helper.ADAPTER == ADAPTER / 'observation.py' and sha(helper.ADAPTER) == helper.ADAPTER_SHA, 'EXACT_POST_STABILITY_TILE_AND_SEQUENCE')
    need(factory.ACK_PATH == HERE / 'spawn_hook.py' and sha(factory.ACK_PATH) == factory.ACK_SHA, 'EXACT_CP73_HOOK')
    need(factory.B.RUN_ID == builder.RUN_ID == factory.B.FORWARD_RUN_ID == factory.OBSERVER.FORWARD_RUN_ID and 1 <= len(builder.RUN_ID) <= 32 and re.fullmatch('[a-z0-9-]+', builder.RUN_ID), 'CP74_NATIVE_CONTEXT_GRAMMAR')
    need(factory.WORK == ROOT / ('work/' + HERE.name) and root.WORK == factory.WORK and factory.B.FAMILY == 'LOCAL_NATIVE_LOGIN_LAND_PROBE_CP74', 'FRESH_CP74_WORK_FAMILY')
    need(not factory.WORK.exists() and not (HERE / 'root-slot-review.json').exists() and not factory.RUN_CORE.run_directory().exists() and not (factory.OBSERVER.FORWARD_ROOT / builder.RUN_ID).exists(), 'FRESH_CP74_SOURCE_REVIEW_ONE_TRIAL_NAMESPACES')
    checks.extend(('root_helper_identity_tail_tile_adapter_pins_exact', 'fresh_CP74_work_family_native_context_source_review_one_trial_forward_namespaces'))
    need(sha(root.INPUT) == root.INPUT_SHA, 'ORIGINAL_OWN_INPUT')
    binding = json.loads(root.INPUT.read_bytes()); binding['candidate_sha256'] = factory.B.CANDIDATE_SHA
    hook = api.game_hook(); hook.identity(binding)
    need({HERE / n for n in ('actor_profile.py', 'actor-profile.json', 'spawn_hook.py', 'spawn-profile-pins.json')}.issubset(set(hook.input_paths())), 'OWN_HOOK_PROFILE_PATHS')
    checks.append('actual_hook_owned_input_identity_and_byte_preserved_profile_paths')
    prior_hook = load(PRIOR / 'spawn_hook.py', '_cp74_frozen_cp73_packet_fixture')
    # SelfInfo's original field15 is the current UTC second; compare identical
    # inputs under one synthetic clock, never alter runtime time behavior.
    with patch('time.time', return_value=1791500000):
        need(factory.ACK.frames() == prior_hook.frames(), 'BYTE_IDENTICAL_CP73_SELFINFO_ACTOR_FRAMES_SAME_CLOCK')
    actor = load(HERE / 'actor_profile.py', '_cp74_actor_candidate_fixture')
    old_actor = load(PRIOR / 'actor_profile.py', '_cp74_prior_actor_candidate_fixture')
    need(actor.candidate() == old_actor.candidate(), 'IDENTICAL_CP73_ACTOR_FIELDS_PROVENANCE')
    checks.append('actual_CP73_SelfInfo_Actor_frames_same_clock_byte_identical_and_actor_fields_provenance_identical')
    history = factory.local('tile_render_pins'); historical = history.verify_history()
    need(len(historical) == 2 and all(v['verified'] for v in historical.values()) and not set(history.HISTORICAL_PATHS).intersection(pins) and not set(ROOT / k for k in history.HISTORICAL_PATHS).intersection(api.input_paths()), 'HISTORICAL_PINFIX_PRESERVED')
    checks.append('historical_snapshots_stream_verified_excluded_live_pins')
    runtime = factory.runtime_api()
    need(Path(runtime.identity_recorder.failure.__code__.co_filename) == HERE / 'image_alt.py' and runtime.identity_recorder.followup is None and Path(factory.CORE.identity.Recorder.failure.__code__.co_filename) == ROOT / 'tools/local_native_login_creation_identity_failure/identity.py', 'ORIGINAL_RECORDER_FACTORY_RESTORED')
    provider = root.runtime().slot_api(); result = provider.module()
    backend = result.fixed_backend.__closure__[0].cell_contents.__globals__
    with backend['gate_module']() as gate:
        need(Path(gate.Native.absent.__code__.co_filename) == HERE / 'identity_adapter.py', 'ACTUAL_CP74_ABSENCE_ADAPTER')
        original_native = gate.Native.__bases__[0]
        need(Path(original_native.absent.__code__.co_filename) == ROOT / 'tools/local_ready_entry_gate/native.py', 'ORIGINAL_NATIVE_BASE')
    need(gate.Native is original_native, 'GATE_CLASS_RESTORED')
    context = provider.verified_installed_context.__closure__[0].cell_contents
    cells = dict(zip(context.__code__.co_freevars, context.__closure__ or ()))
    need(cells['module'].cell_contents is provider.module, 'INSTALLED_CONTEXT_SAME_PROVIDER')
    checks.extend(('diagnostic_only_image_alt_factory_restored', 'actual_slot_absence_gate_and_installed_context_closure_preserved'))
    context_static = load(ROOT / 'tools/local_native_login_tile_render_shortid_runtime/static_check.py', '_cp74_native_context_fixture')
    context_checks, context_report = context_static.context_checks(json.loads((ROOT / 'tools/local_native_login_tile_render_shortid_runtime/namespace-pin-transform.json').read_bytes()))
    checks.extend(context_checks)
    script = "import importlib.util,json; s=importlib.util.spec_from_file_location('_cp74_isolated_alt'," + repr(str(HERE / 'alt_tests.py')) + "); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.run_checks()))"
    isolated = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, timeout=30)
    need(isolated.returncode == 0 and len(isolated.stdout) <= 65536 and len(isolated.stderr) <= 65536, 'ISOLATED_SELF_API_FIXTURE_FAILED')
    alt_checks = json.loads(isolated.stdout)
    need(type(alt_checks) is list and len(alt_checks) == 45, 'EXACT_SELF_API_45_FIXTURE')
    checks.extend(alt_checks)
    for name in ('pidreuse_tests', 'call2_tests', 'modules_tests', 'context_wait_tests', 'helper_tail_tests', 'spawn_tests', 'spawn_hook_tests'):
        checks.extend(load(HERE / (name + '.py'), '_cp74_suite_' + name).run_checks())
    # CP73 baseline fixtures execute the frozen helper; they are not CP74 render evidence.
    checks.extend(load(HERE / 'probe_tests.py', '_cp74_original_cp73_fixtures').run_checks())
    for name in ('tests', 'probe_tests'):
        checks.extend(load(ROOT / 'tools/local_native_login_self_actor_hook' / (name + '.py'), '_cp74_hook_' + name).run_checks())
    checks.extend(load(ROOT / 'tools/local_native_login_world_dormant_runtime/probe_tests.py', '_cp74_CP59_fixtures').run_checks())
    counts = {'budget': suite(ROOT / 'tools/local_tile_passability_budget/tests.py', '_cp74_budget', 17),
              'adapter': suite(ADAPTER / 'tests.py', '_cp74_frozen_adapter_fixtures', 12),
              'integration': suite(HERE / 'integration_tests.py', '_cp74_post_stability_fixtures', 10)}
    checks.extend(('CP70_17_real_sampler_budget_fixtures_PASS', 'CP74_frozen_adapter_12_injected_fixtures_PASS', 'CP74_successor_10_post_stability_integration_fixtures_PASS'))
    need(sha(store) == store_sha, 'CHARACTER_STORE_AFTER_FIXTURES')
    for directory in (PRIOR, ADAPTER):
        builder.verify_freeze(directory)
    checks.append('character_store_and_CP73_CP74_frozen_sources_preserved_after_all_fixtures')
    report = {'status': 'PASS_STATIC_INJECTED_AND_SELF_IMAGE_ALT_DIAGNOSTIC', 'checks': checks,
              'checks_count': len(checks), 'fixture_counts': counts, 'runtime_dependency_count': len(pins),
              'run_id': builder.RUN_ID, 'context_grammar_fixture': context_report, 'historical_artifacts': historical,
              'spawn_policy': builder.POLICY, 'spawn_grid_words': [32571, 32950], 'spawn_uid': 1, 'map_id': 0,
              'wgc_capture_delays_seconds': [0.0, 2.0, 2.0], 'world_visibility_verified': False,
              'self_process_real_API_fixture': True, 'game_native_api_calls': 0, 'game_slot_online_uac_actions': 0,
              'worker_SourceReview_OneTrial_executed': False, 'movement_input_or_packet_sent': False,
              'persistent_store_changed': False, 'full_navigation_passability': 'UNKNOWN'}
    output = HERE / ('static-review-' + uuid.uuid4().hex + '.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    files = {p.name: sha(p) for p in HERE.iterdir() if p.is_file() and (p.suffix == '.py' or p.name == 'README.md' or p.name in (*transform['copied_pinsets'], 'namespace-pin-transform.json'))}
    freeze = {'schema': 'cp74-spawn-render-retry-worker-source-freeze-v1', 'status': 'STATIC_INJECTED_SELF_API_READY_ROOT_REVIEW_REQUIRED',
              'files_sha256': files, 'static_review': output.name, 'static_review_sha256': sha(output),
              'checks_count': len(checks), 'fixture_counts': counts, 'runtime_dependency_count': len(pins),
              'run_id': builder.RUN_ID, 'tile_inspector_sha256': sha(helper.TILE), 'tile_operation_byte_limit': 20480,
              'spawn_policy': builder.POLICY, 'spawn_grid_words': [32571, 32950], 'spawn_uid': 1, 'map_id': 0,
              'wgc_capture_delays_seconds': [0.0, 2.0, 2.0], 'world_visibility_verified': False,
              'worker_SourceReview_OneTrial_executed': False, 'game_slot_online_uac_actions': 0,
              'self_process_real_API_fixture': True, 'cached_identity_admission': False}
    path = HERE / 'source-freeze.json'
    if path.exists():
        existing = json.loads(path.read_bytes())
        need(existing['files_sha256'] == files and existing['checks_count'] == len(checks) and existing['runtime_dependency_count'] == len(pins) and sha(HERE / existing['static_review']) == existing['static_review_sha256'], 'EXISTING_CP74_FREEZE_CHANGED')
    else:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(freeze, stream, indent=2); stream.write('\n')
    print(json.dumps({'status': report['status'], 'checks_count': len(checks), 'fixture_counts': counts, 'runtime_dependency_count': len(pins), 'review': str(output), 'source_freeze': str(path), 'game_Native': 0, 'self_process_real_API_fixture': True}))

if __name__ == '__main__':
    main()
