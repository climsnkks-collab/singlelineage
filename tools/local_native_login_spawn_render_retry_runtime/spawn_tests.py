"""CP73 pure candidate and synthetic typed-memory fixtures; no live game APIs."""
import copy
import importlib.util
import json
import struct
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def run_checks():
    checks = []
    actor = load(HERE / 'actor_profile.py', '_cp73_actor_test')
    old = load(ROOT / 'tools/local_self_actor_profile/profile.py', '_cp73_old_actor_test')
    fields, provenance = actor.candidate()
    original, original_provenance = old.candidate()
    assert fields[1] == 32571 | (32950 << 16)
    assert {k for k in fields if fields[k] != original[k]} == {1}
    assert {k for k in provenance if provenance[k] != original_provenance[k]} == {1}
    checks.append('pure_candidate_only_Actor1_value_and_provenance_changed_all_UID_name_stats_preserved')
    hook = load(HERE / 'spawn_hook.py', '_cp73_spawn_hook_test')
    baseline_hook = load(ROOT / 'tools/local_native_login_self_actor_hook/hook.py', '_cp73_original_hook_test')
    new_frames = hook.frames()
    old_frames = baseline_hook.frames()
    assert new_frames[0] == old_frames[0]
    model = actor.model()
    new_fields = model.decode_payload(0x4e96, new_frames[1][4:-2])
    old_fields = model.decode_payload(0x4e96, old_frames[1][4:-2])
    assert new_fields == fields and {k for k in new_fields if new_fields[k] != old_fields[k]} == {1}
    assert hook.profiles()[3].metadata()['policy'] == actor.POLICY
    checks.append('actual_hook_frames_SelfInfo_byte_identical_Actor_only_field1_new_explicit_experiment_policy')
    info = hook.profiles()[0]
    for field, value in ((1,original[1]), (2,2), (9,'ForeignName'), (16,False), (5,8)):
        bad = dict(fields); bad[field] = value
        try:
            actor.encode_for_review(bad,provenance,info.fields)
        except ValueError:
            pass
        else:
            raise AssertionError('UNDECLARED_ACTOR_DELTA_ACCEPTED')
        checks.append('refuse_undeclared_actor_field_' + str(field))
    for reference, selected in (('ForeignName',(1,())),('SoloKnight',(2,())),('SoloKnight',[1,()])):
        try:
            hook.validate_selected(reference, selected)
        except ValueError:
            pass
        else:
            raise AssertionError('OWN_STORE_SELECTION_REQUIRED')
    hook.validate_selected('SoloKnight',(1,()))
    checks.append('unchanged_exact_owned_store_UID_name_tuple_selection_guard')
    helper = load(HERE / 'auto_enter_tile_render.py', '_cp73_spawn_helper_test')
    actual = json.loads((ROOT / 'work/local_native_login_tile_budget_runtime/world-read-stability.json').read_bytes())
    assert not helper.stable_world(actual, actual['identity'])
    checks.append('immutable_CP71_actual_old_grid_refused_as_CP73_stability_proof')
    old_expected = helper.prior.expected_actor
    old_run = helper.prior.run
    def injected(*args):
        assert helper.prior.expected_actor() == (1,(32571,32950))
        raise RuntimeError('synthetic')
    helper.prior.run = injected
    try:
        try:
            helper.run(None,None,None,None,None)
        except RuntimeError:
            pass
        else:
            raise AssertionError('SYNTHETIC_EXCEPTION_REQUIRED')
        assert helper.prior.expected_actor is old_expected
    finally:
        helper.prior.run = old_run
    checks.append('scoped_new_expected_actor_restored_on_helper_exception')
    tests = load(ROOT / 'tools/local_tile_passability_budget/tests.py', '_cp73_cp70_fixture_source')
    tile = load(HERE / 'inspect_tile.py', '_cp73_new_grid_tile')
    fixture = tests.Tests()
    for flags in (0,1,4,5,0x4000):
        native, sampler = fixture.fixture(flags)
        sampler.put(sampler.transform+0x40,struct.pack('<ii',*tile.GRID))
        # Add candidate's northern row to original fixture, retaining the typed backend.
        y=53; cells=sampler.cells+(y-55)*2048
        sampler.put(sampler.rows+y*24,struct.pack('<QQQ',cells,cells+128*8,cells+128*8))
        for x in range(116,121):
            sampler.put(cells+x*8,struct.pack('<IHH',123,flags,0))
        original_read=sampler.read; original_limit=sampler.read_limit
        with patch.object(tile,'load_world',return_value=tests.world), \
             patch.object(tile,'contract',return_value={'source_checks':[],'tables':[]}), \
             patch.object(tests.world,'contracts',return_value=(sampler.public,sampler.source)):
            row=tile.inspect_all_attached(native,sampler,expected_uid=1)
        assert row['status']=='OBSERVED', row
        assert row['grid_start']==[32571,32950]
        assert len(row['directions'])==8
        assert row['directions'][2]['grid_target']==[32572,32950]
        assert [p[1] for p in tile.probe_cells(tile.GRID,2)]==[(119,54)]
        assert all(r['tile_passability']==('BLOCKED' if flags&1 else 'PASSABLE') for r in row['directions'])
        assert all(r['full_navigation_passability']=='UNKNOWN' for r in row['directions'])
        assert sampler.read==original_read and sampler.read_limit==original_limit and row['typed_bytes_requested']<=20480
        checks.append('new_grid_real_typed_sampler_all8_flags_' + str(flags) + '_full_navigation_UNKNOWN_and_budget_restore')
    return checks
