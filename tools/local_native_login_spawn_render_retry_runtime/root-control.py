"""One CP73 Land observation with fresh outputs and guaranteed restore attempt."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORK = ROOT / 'work/local_native_login_spawn_render_retry_runtime'
FILE_REVIEW = ROOT / 'work/local_native_login_state5_ack_candidate/file-review-v2.json'
INPUT = ROOT / 'work/local_native_login_saved_select_runtime/own-input.json'
INPUT_SHA = '286d6f647ba0f8f29d3660e52d4e8a94b51628e29fa7018265c85e78032afec7'
IDENTITY_SHA = '7e0260cbfe4a3e3c91b468cada6b1efe3a7d0643cb7c0262f3b59bfb69872e59'
AUTO = HERE / 'auto_enter_tile_render.py'
AUTO_SHA = '936077d13d8bf2d4e5c742f1f58aafa886299849261631a911bf96bd123acc5e'
TAIL_SHA = '07298209efc5ef97194830af109225f2875ece0f581a8390172a97075a8cfc02'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def save(path, row):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(row, stream, indent=2)
        stream.write('\n')


def runtime():
    spec = importlib.util.spec_from_file_location('_cp73_root_runtime', HERE / 'fix.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    identity_path = HERE / 'identity_adapter.py'
    need(sha(identity_path) == IDENTITY_SHA, 'EXACT_RECYCLED_PID_READER_REQUIRED')
    spec = importlib.util.spec_from_file_location('_cp73_exact_old_pid', identity_path)
    identity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(identity)
    original_slot_api = module.slot_api

    def slot_api():
        return identity.patch_provider(original_slot_api())

    module.slot_api = slot_api
    module.RUN_CORE.slot_api = slot_api
    return module


def source_review():
    need(not WORK.exists(), 'FRESH_CP73_WORK_DIRECTORY_REQUIRED')
    need(not (HERE / 'root-slot-review.json').exists(), 'CP73_SOURCE_REVIEW_ALREADY_CONSUMED')
    r = runtime()
    need(sha(AUTO) == AUTO_SHA, 'EXACT_LAND_HELPER_REQUIRED')
    need(r.B.FINALIZED and sha(r.B.CANDIDATE) == r.B.CANDIDATE_SHA, 'EXACT_CP49_REUSED_CANDIDATE')
    file_review = json.loads(FILE_REVIEW.read_bytes())
    need(file_review['status'] == 'FILE_ONLY_REVIEWED'
         and file_review['candidate_sha256'] == r.B.CANDIDATE_SHA
         and file_review['new_dll_sha256'] == r.B.DLL_SHA, 'CP49_FILE_COMPARISON_REQUIRED')
    need(sha(INPUT) == INPUT_SHA, 'IMMUTABLE_OWN_INPUT_REQUIRED')
    old_own = json.loads(INPUT.read_bytes())
    need(set(old_own) == {'candidate_sha256', 'expected_own_uuid'}
         and old_own['candidate_sha256'] == 'e5290ff31aa8dd068f9af413634e5dedd076f508d83851cb6fe272aac2f8503d'
         and old_own['expected_own_uuid'] == 'a1416ea8-d0e1-4b93-b622-c27752ef6b51',
         'EXACT_ORIGINAL_OWN_INPUT_REQUIRED')
    api = r.source_api()
    api.verify_files()
    historical = r.local('tile_render_pins').verify_history()
    prior_receipt_path = ROOT / 'work/local_native_login_tile_render_stable_runtime/slot/receipt.json'
    prior_receipt = json.loads(prior_receipt_path.read_bytes())
    need(sha(prior_receipt_path) == api.pins()[prior_receipt_path.relative_to(ROOT).as_posix()]
         and prior_receipt['status'] == 'VERIFIED' and prior_receipt['phase'] == 'RESTORED'
         and prior_receipt['restoration_required'] is False and prior_receipt['outcome_unconfirmed'] is False
         and prior_receipt['current_sha256'] == '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
         and prior_receipt['slot_file_id'] == 'ce7884c9:00c600000006b6e8', 'EXACT_CP63_RESTORED_CONTROL_RECEIPT')
    product, preflight = api.product_binding()
    need(product['candidate']['sha256'] == r.B.CANDIDATE_SHA
         and product['producer_DLL']['sha256'] == r.B.DLL_SHA
         and preflight['status'] == 'PASS_FILE_ONLY_COMPILED', 'EXACT_CP49_PRODUCT_BINDING')
    run_directory = r.RUN_CORE.run_directory()
    forward = r.OBSERVER.FORWARD_ROOT / r.B.RUN_ID
    need(not run_directory.exists() and not forward.exists(), 'FRESH_CP73_OBSERVER_DIRECTORIES_REQUIRED')
    WORK.mkdir(exist_ok=False)
    save(WORK / 'own-input.json', dict(old_own, candidate_sha256=r.B.CANDIDATE_SHA))
    binding = api.local_binding()
    api.game_hook().identity(binding)
    save(HERE / 'root-slot-review.json', r.slot_api().expected_review())
    run_directory.parent.mkdir(parents=True, exist_ok=True)
    run_directory.mkdir(exist_ok=False)
    forward.parent.mkdir(parents=True, exist_ok=True)
    forward.mkdir(exist_ok=False)
    save(WORK / 'root-source-review.json', {
        'schema': 'cp73-land-probe-source-review-v1', 'status': 'SOURCE_REVIEWED_NO_GAME',
        'candidate_sha256': r.B.CANDIDATE_SHA, 'dll_sha256': r.B.DLL_SHA,
        'file_review_sha256': sha(FILE_REVIEW), 'manifest_sha256': r.B.MANIFEST_SHA,
        'preflight_sha256': r.B.PREFLIGHT_SHA, 'source_pins_sha256': r.B.PRODUCT_PINS_SHA,
        'runtime_source_sha256': api.own_hashes(), 'dependency_pins': api.pins(),
        'historical_artifacts': historical,
        'identity_adapter_sha256': IDENTITY_SHA, 'auto_land_helper_sha256': AUTO_SHA,
        'slot_review_sha256': sha(HERE / 'root-slot-review.json'),
        'old_own_input_sha256': INPUT_SHA, 'own_input_sha256': sha(WORK / 'own-input.json'),
        'run_id': r.B.RUN_ID, 'forward_public_file_limit': 57,
        'game_or_slot_action': False, 'cp49_outputs_written': False,
    })
    return {'status': 'SOURCE_REVIEWED', 'run_id': r.B.RUN_ID, 'work': str(WORK)}


def verify_review(r):
    row = json.loads((WORK / 'root-source-review.json').read_bytes())
    api = r.source_api()
    need(row['schema'] == 'cp73-land-probe-source-review-v1'
         and row['status'] == 'SOURCE_REVIEWED_NO_GAME' and row['run_id'] == r.B.RUN_ID
         and row['candidate_sha256'] == r.B.CANDIDATE_SHA and row['dll_sha256'] == r.B.DLL_SHA
         and row['runtime_source_sha256'] == api.own_hashes()
         and row['dependency_pins'] == api.pins()
         and row['auto_land_helper_sha256'] == AUTO_SHA == sha(AUTO)
         and row['slot_review_sha256'] == sha(HERE / 'root-slot-review.json')
         and row['own_input_sha256'] == sha(WORK / 'own-input.json')
         and row['file_review_sha256'] == sha(FILE_REVIEW)
         and row['manifest_sha256'] == sha(r.B.MANIFEST)
         and row['preflight_sha256'] == sha(r.B.PREFLIGHT)
         and row['source_pins_sha256'] == sha(r.B.PRODUCT_PINS), 'CP73_SOURCE_REVIEW_CHANGED')
    need(row['historical_artifacts'] == r.local('tile_render_pins').verify_history(),
         'CP73_REVIEWED_HISTORICAL_ARTIFACT_CHANGED')
    api.verify_files()
    for name, digest in row['dependency_pins'].items():
        need(sha(ROOT / name) == digest, 'CP73_REVIEWED_DEPENDENCY_CHANGED:' + name)
    return api


def installed_reviews(r):
    api = r.source_api()
    with r.slot_api().verified_installed_context() as context:
        context.verify_sources()
        raw = api.small(api.CONFIG, 65536)
        config = json.loads(raw)
        binding = api.local_binding()
        api.game_hook().identity(binding)
        save(api.REVIEW, api.expected_review(context.proof, api.sha(raw)))
        save(api.LOGIN_REVIEW, api.game_hook().expected_review(context.proof, binding, config))
        need(r.local('tile_render_pins').verify_history()
             == json.loads((WORK / 'root-source-review.json').read_bytes())['historical_artifacts'],
             'CP73_INSTALLED_PREFLIGHT_HISTORICAL_ARTIFACT_CHANGED')
        api.approved(context.proof)
        context.verify_sources()
        save(WORK / 'root-installed-review.json', {
            'status': 'EXACT_CP73_INSTALLED_CONTEXT_REVIEWED',
            'current_sha256': context.proof['current_sha256'],
            'slot_file_id': context.proof['slot_file_id'],
            'transaction_sha256': context.proof['transaction_sha256'],
            'runtime_review_sha256': sha(api.REVIEW), 'login_review_sha256': sha(api.LOGIN_REVIEW),
            'game_created': False,
        })


def helper_failure_tail(stderr, returncode, result_file_created):
    path = HERE / 'helper_failure_tail.py'
    need(sha(path) == TAIL_SHA, 'EXACT_CP73_HELPER_FAILURE_TAIL_REQUIRED')
    spec = importlib.util.spec_from_file_location('_cp73_helper_failure_tail', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.diagnostic(stderr, returncode, result_file_created, module.catalogue())


async def stop_helper(helper):
    if helper is not None and helper.returncode is None:
        helper.terminate()
        try:
            await asyncio.wait_for(helper.wait(), 5)
        except asyncio.TimeoutError:
            helper.kill()
            await helper.wait()


async def trial():
    r = runtime()
    verify_review(r)
    save(WORK / 'one-trial-intent.json', {'schema': 'cp73-one-trial-intent-v1', 'run_id': r.B.RUN_ID})
    slot_attempted = False
    helper = None
    try:
        slot = r.slot_api().module()
        slot_attempted = True
        with slot.fixed_backend() as backend:
            slot.execute('PrepareEndpoint', backend)
        installed_reviews(r)
        need(sha(AUTO) == AUTO_SHA, 'CP73_LAND_HELPER_CHANGED')
        helper = await asyncio.create_subprocess_exec(
            sys.executable, '-X', 'utf8', '-B', str(AUTO),
            '--candidate', str(r.B.CANDIDATE), '--sha', r.B.CANDIDATE_SHA,
            '--context', str(r.OBSERVER.FORWARD_ROOT / r.B.RUN_ID / 'context.json'),
            '--metadata', str(WORK / 'broker/packet-metadata.jsonl'),
            '--result', str(WORK / 'auto-ok-result.json'),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        report = await r.runtime_api().actual()
        try:
            stdout, stderr = await asyncio.wait_for(helper.communicate(), 15)
        except asyncio.TimeoutError:
            await stop_helper(helper)
            stdout, stderr = await helper.communicate()
        save(WORK / 'auto-helper-exit.json', {
            'schema': 'cp65-land-probe-helper-exit-v1', 'returncode': helper.returncode,
            'stdout': stdout.decode('utf-8', 'replace')[:1200],
            'stderr': stderr.decode('utf-8', 'replace')[:1200],
            'result_file_created': (WORK / 'auto-ok-result.json').is_file(),
        })
        if helper.returncode != 0:
            save(WORK / 'helper-failure-tail.json', helper_failure_tail(
                stderr, helper.returncode, (WORK / 'auto-ok-result.json').is_file()))
        auto = json.loads((WORK / 'auto-ok-result.json').read_bytes()) if (WORK / 'auto-ok-result.json').is_file() else None
        module_file = WORK / 'module-readiness-diagnostic.json'
        module_diagnostic = json.loads(module_file.read_bytes()) if module_file.is_file() else None
        save(WORK / 'root-trial-result.json', {
            'schema': 'cp73-land-probe-trial-v1', 'status': 'ACTUAL_TRIAL_RETURNED',
            'stop_reason': report.get('stop_reason'), 'reason': report.get('reason'),
            'restoration_safe_after_owned_cleanup': report.get('restoration_safe_after_owned_cleanup'),
            'automatic_one_second_result': auto is not None,
            'character_select_memory_seen': auto.get('character_select_memory_seen') if auto else None,
            'land_public_presence': auto.get('land_public_presence') if auto else None,
            'land_probe_file': auto.get('land_probe_file') if auto else None,
            'land_screen_capture': auto.get('land_screen_capture') if auto else None,
            'land_screen_capture_file': auto.get('land_screen_capture_file') if auto else None,
            'identity_followup_file_created': (WORK / 'identity-failure-followup.json').is_file(),
            'module_readiness_diagnostic_file': str(module_file) if module_diagnostic else None,
            'module_snapshot_ever_succeeded': module_diagnostic.get('module_snapshot_ever_succeeded') if module_diagnostic else None,
            'module_readiness_attempt_count': module_diagnostic.get('attempt_count') if module_diagnostic else None,
            'world_read_stability_file_created': (WORK/'world-read-stability.json').is_file(),
            'post_stability_capture_requested': True,
            'tile_passability_file_created': (WORK/'tile-passability.json').is_file(),
            'render_capture_file_created': (WORK/'render-capture.json').is_file(),
            'capture_content_requires_root_visual_review': True,
            'self_actor_configuration_policy': 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73',
            'normal_server_success_proven':False,
            'tile_state':'UNKNOWN',
            'dormant_code_execution_proven':False,
            'source_anchor_dormancy_diagnostic_only':True,
            'map_configuration_policy': 'EXPLICIT_LOCAL_SOURCE_BASELINE',
            'map_world_ready_claim': False, 'map_tileload_claim': False,
            'character_screen_proven': False, 'gameplay_proven': False,
        })
        return 0 if report.get('restoration_safe_after_owned_cleanup') is True and helper.returncode == 0 else 2
    finally:
        # Helper cleanup failure must never skip the slot restoration attempt.
        try:
            await stop_helper(helper)
        finally:
            if slot_attempted:
                journal_path = WORK / 'slot/transactions.json'
                # A Prepare refusal before durable intent needs no image write.
                # An unreadable existing journal cannot be assumed harmless.
                if journal_path.exists():
                    try:
                        journal = json.loads(journal_path.read_bytes())
                        restore_needed = bool(journal.get('events')) and journal['events'][-1]['phase'] != 'RESTORED'
                    except Exception:
                        restore_needed = True
                    if restore_needed:
                        restore_control(r)


def restore_control(r=None):
    r = runtime() if r is None else r
    slot = r.slot_api().module()
    with slot.fixed_backend() as backend:
        slot.execute('RestoreControl', backend)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('Plan', 'SourceReview', 'OneTrial', 'RestoreControl'),
                        nargs='?', default='Plan')
    args = parser.parse_args()
    if args.action == 'Plan':
        print(json.dumps({'status': 'PLAN_CP73_LAND_PROBE', 'run_id': 'cp74-render-20261009-01',
                          'work': str(WORK), 'game_started': False, 'uac_requested': False}))
        return 0
    if args.action == 'SourceReview':
        print(json.dumps(source_review()))
        return 0
    if args.action == 'RestoreControl':
        restore_control()
        return 0
    return asyncio.run(trial())


if __name__ == '__main__':
    raise SystemExit(main())
