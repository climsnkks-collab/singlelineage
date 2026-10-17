"""CP73: bounded initial transients, terminal stability, tile read and owned WGC."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIOR = ROOT / 'tools/local_native_login_world_dormant_runtime/auto_enter_world_dormant.py'
PRIOR_SHA = 'fd488f0cdf01812814c886f22f75d0590868239bcc10afac7081e389814f31b2'
TILE = HERE / 'inspect_tile.py'
TILE_SHA = '1a124864ec110b686ba37a0c873c525ffef073d5546889b1ee387fe6304733ea'
RENDER = ROOT / 'tools/local_native_render_proof/capture.py'
WINDOW = ROOT / 'tools/local_native_scene_current/capture_window.py'
ADAPTER = ROOT / 'tools/local_native_login_spawn_render_runtime/observation.py'
ADAPTER_SHA = 'bd21daca3938a59e5322d44715819cc1774ec807fb22ea6e75c2dec21b20d0e5'
TIMEOUT = 6.0
LIMIT = 131072


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


need(hashlib.sha256(PRIOR.read_bytes()).hexdigest() == PRIOR_SHA, 'FROZEN_CP59_HELPER')
need(hashlib.sha256(ADAPTER.read_bytes()).hexdigest() == ADAPTER_SHA, 'FROZEN_CP74_RENDER_SEQUENCE')
prior = load(PRIOR, '_cp73_frozen_cp59_helper')
pins_module = load(HERE / 'tile_render_pins.py', '_cp73_dependency_pins')
need(hashlib.sha256(TILE.read_bytes()).hexdigest() == TILE_SHA, 'EXACT_CP70_TILE_BUDGET_INSPECTOR_REQUIRED')


def save(path, row):
    raw = (json.dumps(row, indent=2) + '\n').encode('utf-8')
    need(len(raw) <= LIMIT, 'BOUNDED_CP73_OBSERVATION_OUTPUT')
    with path.open('xb') as stream:
        stream.write(raw)


def skipped_first_capture(native, loader):
    native.validate()
    return {'schema': 'lc-owned-land-capture-skipped-v1', 'status': 'SKIPPED',
            'reason': 'CP73_POST_STABILITY_WGC_ONLY', 'focus_attempted': False,
            'desktop_pixels_captured': False, 'visible_gameworld_verified': False,
            'actual_gameplay_proven': False}


def complete_world(observed):
    """Preserve every CP62 complete observation requirement."""
    return (observed.get('status') == 'OBSERVED'
            and observed.get('scene') == 'Land' and observed.get('pending') == 'none'
            and observed.get('my_player_count') == 1 and observed.get('my_player_uid') == 1
            and observed.get('expected_uid_match') is True
            and observed.get('grid_words') == [32571, 32950]
            and observed.get('segment_key_words') == [32764, 32770]
            and observed.get('source_segment_grid_relation_match') is True
            and observed.get('expected_grid_words_match') is True
            and observed.get('map_requested_i32') == 0
            and observed.get('map_resolved_i32') == 0
            and observed.get('map_context_header_i32') == 0
            and observed.get('map_context_present') is True
            and observed.get('coordinate_tile_entry_present') is True
            and observed.get('coordinate_tile_resource_present') is True
            and observed.get('land_game_layer_present') is True
            and observed.get('stable_double_read') is True
            and observed.get('diagnostic', {}).get('stage') == 'COMPLETE')


def initial_transient(observed):
    """Only a fully read Land sample with no contradictory local actor/map values."""
    if (observed.get('status') != 'OBSERVED_PARTIAL'
            or observed.get('reason') is not None
            or observed.get('scene') != 'Land' or observed.get('pending') != 'none'
            or observed.get('map_context_present') is not True
            or observed.get('stable_double_read') is not True
            or observed.get('diagnostic', {}).get('stage') != 'COMPLETE'
            or observed.get('map_requested_i32') != 0
            or observed.get('map_resolved_i32') not in (-1, 0)
            or observed.get('map_context_header_i32') not in (-1, 0)):
        return False
    count = observed.get('my_player_count')
    if type(count) is not int or count not in (0, 1):
        return False
    for field, expected in (('my_player_uid', 1), ('grid_words', [32571, 32950]),
                            ('segment_key_words', [32764, 32770])):
        value = observed.get(field)
        if value is not None and value != expected:
            return False
        if count == 0 and value is not None:
            return False
    if count == 1 and observed.get('my_player_uid') != 1:
        return False
    for field in ('expected_uid_match', 'expected_grid_words_match',
                  'source_segment_grid_relation_match'):
        value = observed.get(field)
        if value is not None and value is not True:
            return False
    return True


def stable_world(row, identity):
    """At most two leading transients, then >=3 exact uninterrupted complete reads."""
    if row.get('identity') != identity or row.get('sample_limit') != 5:
        return False
    samples = row.get('samples', [])
    if len(samples) != 5 or row.get('same_retained_native_handle') is not True:
        return False
    connections = []
    initial_count = 0
    complete_count = 0
    for index, sample in enumerate(samples):
        emitted = sample.get('emission', {})
        observed = sample.get('observation', {})
        if (sample.get('sample_index') != index
                or emitted.get('status') != 'EMITTED_METADATA'
                or emitted.get('sequence') != [0x4e29, 0x4e95, 0x4e38, 0x4e96]
                or type(emitted.get('connection_id')) is not int):
            return False
        if complete_world(observed):
            complete_count += 1
        elif complete_count == 0 and initial_count < 2 and initial_transient(observed):
            initial_count += 1
        else:
            return False
        connections.append(emitted['connection_id'])
    emitted = row.get('emission', {})
    return (complete_count >= 3 and len(set(connections)) == 1
            and emitted.get('status') == 'EMITTED_METADATA'
            and emitted.get('sequence') == [0x4e29, 0x4e95, 0x4e38, 0x4e96]
            and type(emitted.get('connection_id')) is int
            and emitted['connection_id'] == connections[0])


def post_stability(native, sampler, result_path, loader=load):
    pins_module.pins()
    held, handle, identity = native, native.handle, dict(native.expected)
    def owner():
        need(native is held and native.handle == handle and native.expected == identity,
             'EXACT_RETAINED_CP73_OBSERVATION_OWNER')
        native.validate()
    owner()
    tile_path = result_path.with_name('tile-passability.json')
    render_path = result_path.with_name('render-capture.json')
    need(not tile_path.exists() and not render_path.exists(), 'CREATE_NEW_CP73_OBSERVATIONS_REQUIRED')
    row_path = result_path.with_name('world-read-stability.json')
    need(row_path.stat().st_size <= LIMIT, 'BOUNDED_CP59_WORLD_OUTPUT_REQUIRED')
    world = json.loads(row_path.read_bytes())
    ready = stable_world(world, identity)
    tile = {'schema': 'lc-owned-cp73-tile-passability-v1', 'status': 'UNKNOWN',
            'reason': 'BOUNDED_INITIAL_TRANSIENT_THEN_THREE_STABLE_MAP0_MYPLAYER1_REQUIRED',
            'read_attempts': 0, 'same_retained_native_handle': True,
            'new_PID_open': False, 'full_navigation_passability': 'UNKNOWN',
            'movement_input_or_packet_sent': False, 'world_ready_claim': False,
            'actual_gameplay_proven': False}
    render = {'schema': 'lc-owned-cp73-render-capture-v1', 'status': 'UNKNOWN',
              'reason': 'BOUNDED_INITIAL_TRANSIENT_THEN_THREE_STABLE_MAP0_MYPLAYER1_REQUIRED',
              'capture_attempts': 0, 'method': 'Windows.Graphics.Capture.CreateForWindow',
              'focus_attempted': False, 'desktop_pixels_captured': False,
              'world_visibility_verified': False, 'actual_gameplay_proven': False}
    if ready:
        owner()
        tile['read_attempts'] = 1
        try:
            tile['observation'] = loader(TILE, '_cp73_exact_tile_only').inspect_all_attached(
                native, sampler, expected_uid=1)
            tile['status'] = tile['observation']['status']
            tile['reason'] = tile['observation'].get('reason')
        except Exception as error:
            # Exception text can contain addresses/identifiers; only a bounded type is public.
            tile['reason'] = 'TILE_READ_EXCEPTION:' + type(error).__name__[:64]
        owner()
        try:
            window = loader(WINDOW, '_cp73_exact_window_selection')
            window.identity(identity['pid'], str(identity['birth']))
            choices = window.windows(identity['pid'])
            need(len(choices) == 1, 'ONE_EXACT_OWNED_WINDOW_REQUIRED')
            _, hwnd, _, _ = choices[0]
            owner()
            render['capture_attempts'] = 1
            captured = loader(ADAPTER, '_cp74_frozen_observation_sequence').sequence(
                native, loader(RENDER, '_cp73_exact_owned_wgc'),
                identity['pid'], str(identity['birth']), hwnd=hwnd,
                output=result_path.parent / 'render', timeout=TIMEOUT)
            # Copy only the documented bounded path/status API, never raw HWND metadata.
            need(type(captured) is dict
                 and set(captured) == {'status', 'report', 'image', 'world_visibility_verified'}
                 and captured['world_visibility_verified'] is False, 'EXACT_WGC_RESULT_SCHEMA')
            need(captured['status'] in ('UNKNOWN', 'PIXELS_OBSERVED_CONTENT_UNVERIFIED'),
                 'EXACT_WGC_UNVERIFIED_STATUS')
            render.update(status=captured['status'], reason=None, capture=captured)
        except Exception as error:
            render['reason'] = 'WGC_CAPTURE_EXCEPTION:' + type(error).__name__[:64]
        owner()
    owner()
    save(tile_path, tile)
    save(render_path, render)


def run(candidate, expected_sha, context_path, metadata_path, result_path):
    pins_module.pins()
    original_expected_actor = prior.expected_actor
    profile = load(HERE / 'actor_profile.py', '_cp73_expected_spawn')
    fields, _ = profile.candidate()
    def expected_actor():
        return fields[2], (fields[1] & 0xffff, fields[1] >> 16)
    prior.expected_actor = expected_actor
    original_world = prior.observe_world
    original_capture = prior.capture_land_screen
    def observe(native, sampler, original_sample, metadata, result, loader):
        original_world(native, sampler, original_sample, metadata, result, loader)
        post_stability(native, sampler, result, loader)
    prior.observe_world = observe
    prior.capture_land_screen = skipped_first_capture
    try:
        return prior.run(candidate, expected_sha, context_path, metadata_path, result_path)
    finally:
        prior.expected_actor = original_expected_actor
        prior.observe_world = original_world
        prior.capture_land_screen = original_capture


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('candidate', 'context', 'metadata', 'result'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--sha', required=True)
    args = parser.parse_args()
    run(args.candidate.resolve(), args.sha, args.context.resolve(),
        args.metadata.resolve(), args.result.resolve())
