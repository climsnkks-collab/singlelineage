"""File-only CP74 successor: fresh namespace and frozen observation.sequence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / 'tools/local_native_login_spawn_candidate_runtime'
ADAPTER = ROOT / 'tools/local_native_login_spawn_render_runtime'
RUN_ID = 'cp74-render-20261009-01'
OLD_RUN_ID = 'cp73-spawn-20261009-01'
POLICY = 'EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def jsonbytes(row):
    return (json.dumps(row, indent=2, ensure_ascii=False) + '\n').encode('utf-8')

def write(name, raw):
    with (HERE / name).open('xb') as stream:
        stream.write(raw)

def namespace(raw):
    return raw.replace(PRIOR.name.encode(), HERE.name.encode()).replace(
        OLD_RUN_ID.encode(), RUN_ID.encode()).replace(
        b"FAMILY='LOCAL_NATIVE_LOGIN_LAND_PROBE_CP73'",
        b"FAMILY='LOCAL_NATIVE_LOGIN_LAND_PROBE_CP74'").replace(
        b"slot_creation_policy='fresh_cp73_journal_exact_cp49_owned_producer_reuse'",
        b"slot_creation_policy='fresh_cp74_journal_exact_cp49_owned_producer_reuse'")

def declared(name, replacements):
    raw = namespace((PRIOR / name).read_bytes())
    if name == 'probe_tests.py':
        raw = raw.replace(b"HERE/'auto_enter_tile_render.py'", b"ROOT/'tools/local_native_login_spawn_candidate_runtime/auto_enter_tile_render.py'")
    if name == 'auto_enter_tile_render.py':
        old = b"            captured = loader(RENDER, '_cp73_exact_owned_wgc').capture("
        new = b"            captured = loader(ADAPTER, '_cp74_frozen_observation_sequence').sequence(\n                native, loader(RENDER, '_cp73_exact_owned_wgc'),"
        if raw.count(old) != 1:
            raise ValueError('ONE_POST_STABILITY_CAPTURE_BOUNDARY_REQUIRED')
        raw = raw.replace(old, new)
        raw = raw.replace(b"TIMEOUT = 6.0", b"ADAPTER = ROOT / 'tools/local_native_login_spawn_render_runtime/observation.py'\nADAPTER_SHA = '" + sha(ADAPTER / 'observation.py').encode() + b"'\nTIMEOUT = 6.0")
        raw = raw.replace(b"prior = load(PRIOR, '_cp73_frozen_cp59_helper')", b"need(hashlib.sha256(ADAPTER.read_bytes()).hexdigest() == ADAPTER_SHA, 'FROZEN_CP74_RENDER_SEQUENCE')\nprior = load(PRIOR, '_cp73_frozen_cp59_helper')")
    if name == 'fix.py':
        raw = raw.replace(b'wgc_capture_count_maximum=1,', b'wgc_capture_count_maximum=3,wgc_capture_delays_seconds=[0.0,2.0,2.0],wgc_sequence_same_retained_handle=True,wgc_sequence_world_visibility_verified=False,')
    if name in ('fix.py', 'root-control.py', 'tile_render_pins.py', 'spawn_hook.py'):
        for old, new in replacements.items():
            raw = raw.replace(old.encode(), new.encode())
    return raw

def verify_freeze(directory):
    row = json.loads((directory / 'source-freeze.json').read_bytes())
    for name, digest in row['files_sha256'].items():
        if sha(directory / name) != digest:
            raise ValueError('IMMUTABLE_FREEZE_CHANGED:' + directory.name + '/' + name)
    return row

def main():
    frozen = verify_freeze(PRIOR)
    adapter = verify_freeze(ADAPTER)
    names = [n for n in frozen['files_sha256'] if n.endswith('.py') and n not in ('create_successor.py', 'static_check.py')]
    copies = [n for n in frozen['files_sha256'] if n.endswith('.json') and n != 'namespace-pin-transform.json']
    for name in names:
        write(name, declared(name, {}))
    for name in copies:
        write(name, (PRIOR / name).read_bytes())
    spawn_pins = json.loads((HERE / 'spawn-profile-pins.json').read_bytes())
    for name in ('actor_profile.py', 'actor-profile.json'):
        spawn_pins[(HERE / name).relative_to(ROOT).as_posix()] = sha(HERE / name)
    (HERE / 'spawn-profile-pins.json').write_bytes(jsonbytes(spawn_pins))
    hook_replacement = {sha(PRIOR / 'spawn-profile-pins.json'): sha(HERE / 'spawn-profile-pins.json')}
    (HERE / 'spawn_hook.py').write_bytes(declared('spawn_hook.py', hook_replacement))
    evidence = json.loads((HERE / 'runtime-evidence-pins.json').read_bytes())
    old_evidence = dict(evidence)
    for directory, freeze in ((PRIOR, frozen), (ADAPTER, adapter)):
        evidence.update({(directory / n).relative_to(ROOT).as_posix(): v for n, v in freeze['files_sha256'].items()})
        evidence[(directory / 'source-freeze.json').relative_to(ROOT).as_posix()] = sha(directory / 'source-freeze.json')
    evidence.update(json.loads((ADAPTER / 'dependency-pins.json').read_bytes()))
    for name in ('image_alt.py', 'queries.py', 'diagnostic.py', 'actor_profile.py', 'actor-profile.json', 'spawn_hook.py', 'spawn-profile-pins.json', 'inspect_tile.py'):
        evidence[(HERE / name).relative_to(ROOT).as_posix()] = sha(HERE / name)
    (HERE / 'runtime-evidence-pins.json').write_bytes(jsonbytes(evidence))
    replacements = {sha(PRIOR / name): sha(HERE / name) for name in names + copies if name not in ('fix.py', 'root-control.py', 'tile_render_pins.py')}
    for name in ('fix.py', 'root-control.py', 'tile_render_pins.py'):
        (HERE / name).write_bytes(declared(name, replacements))
    write('namespace-pin-transform.json', jsonbytes({
        'schema': 'cp74-exact-cp73-render-sequence-delta-v1', 'run_id': RUN_ID,
        'prior_freeze_sha256': sha(PRIOR / 'source-freeze.json'),
        'prior_files_sha256': frozen['files_sha256'],
        'adapter_freeze_sha256': sha(ADAPTER / 'source-freeze.json'),
        'adapter_files_sha256': adapter['files_sha256'],
        'copied_python': names, 'copied_pinsets': copies,
        'sha_literal_replacements': replacements,
        'runtime_evidence_added_paths': sorted(set(evidence) - set(old_evidence)),
        'preserved_spawn_policy': POLICY, 'spawn_grid': [32571, 32950],
        'spawn_uid': 1, 'map_id': 0, 'persistent_store_changed': False,
        'capture_delays_seconds': [0.0, 2.0, 2.0], 'world_visibility_verified': False,
        'game_slot_uac_actions': 0,
    }))
    print(json.dumps({'status': 'CREATED_FILES_ONLY', 'run_id': RUN_ID, 'game_slot_uac_actions': 0}))

if __name__ == '__main__':
    main()
