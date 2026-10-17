"""Injected CP73 integration fixtures: no live process, game, capture or slot."""
import copy
import asyncio
import contextlib
import importlib.util
import json
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def run_checks():
    spec = importlib.util.spec_from_file_location('_cp73_fixture_helper', ROOT/'tools/local_native_login_spawn_candidate_runtime/auto_enter_tile_render.py')
    h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    checks = []
    baseline = json.loads((ROOT/'work/local_native_login_world_dormant_runtime/world-read-stability.json').read_bytes())
    cp62_actual = json.loads((ROOT/'work/local_native_login_tile_render_runtime/world-read-stability.json').read_bytes())
    for fixture in (baseline, cp62_actual):
        fixture['expected_local_actor_grid_words'] = [32571,32950]
        for sample in fixture['samples']:
            if sample['observation'].get('grid_words') == [32571,32951]:
                sample['observation']['grid_words'] = [32571,32950]
    assert h.stable_world(cp62_actual, cp62_actual['identity'])
    checks.append('synthetic_shift_of_CP62_shape_first_partial_then_four_complete_samples_without_live_API')
    identity = dict(baseline['identity'])
    class Native:
        def __init__(self): self.handle=object(); self.expected=dict(identity); self.validations=0
        def validate(self): self.validations+=1
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp); events=[]; n=Native(); sampler=object()
        fixture_tile={'status':'OBSERVED','reason':None,'directions':[
            {'direction':v,'tile_passability':'PASSABLE','full_navigation_passability':'UNKNOWN'} for v in range(8)]}
        def tile(native, actual, *, expected_uid):
            assert native is n and actual is sampler and expected_uid==1
            events.append('tile'); return copy.deepcopy(fixture_tile)
        def identity_check(pid,birth):
            assert (pid,birth)==(identity['pid'],identity['birth']); events.append('identity')
        choices=[(1024,777,32,32)]
        def windows(pid):
            assert pid==identity['pid']; events.append('windows'); return list(choices)
        mode='success'
        def capture(pid,birth,*,hwnd,output,timeout):
            assert (pid,birth)==(identity['pid'],identity['birth']) and hwnd==777 and timeout==6.0
            events.append('wgc')
            if mode=='capture_exception': raise RuntimeError('hidden HWND=777 text')
            if mode=='owner_changed': n.expected=dict(identity,pid=999)
            if mode=='handle_changed': n.handle=object()
            return {'status':'UNKNOWN' if mode=='timeout' else 'PIXELS_OBSERVED_CONTENT_UNVERIFIED',
                    'report':str(output/'fixture-attempt.json'), 'image':None,
                    'world_visibility_verified':False}
        t=types.SimpleNamespace(inspect_all_attached=tile)
        w=types.SimpleNamespace(identity=identity_check,windows=windows)
        r=types.SimpleNamespace(capture=capture)
        def loader(path,name):
            return {h.TILE:t,h.WINDOW:w,h.RENDER:r}[path]
        def attempt(name,world=None):
            output=d/name; output.mkdir()
            (output/'world-read-stability.json').write_text(json.dumps(baseline if world is None else world),'utf-8')
            h.post_stability(n,sampler,output/'result.json',loader)
            return output,json.loads((output/'tile-passability.json').read_bytes()),json.loads((output/'render-capture.json').read_bytes())
        output,tile_row,render=attempt('success')
        assert events==['tile','identity','windows','wgc'] and tile_row['read_attempts']==1 and render['capture_attempts']==1
        assert tile_row['status']=='OBSERVED' and len(tile_row['observation']['directions'])==8
        assert render['status']=='PIXELS_OBSERVED_CONTENT_UNVERIFIED'
        assert not render['world_visibility_verified'] and not render['focus_attempted']
        assert not tile_row['actual_gameplay_proven'] and not tile_row['world_ready_claim']
        assert '777' not in (output/'render-capture.json').read_text('utf-8')
        checks.append('five_actual_shape_samples_gate_one_same_handle_tile8_then_exact_owned_WGC_without_HWND_output')
        transient = copy.deepcopy(baseline)
        transient['samples'][0]['observation'] = copy.deepcopy(cp62_actual['samples'][0]['observation'])
        for leading in (1, 2):
            accepted = copy.deepcopy(transient)
            if leading == 2:
                accepted['samples'][1]['observation'] = copy.deepcopy(accepted['samples'][0]['observation'])
            events.clear(); _, tr, rr = attempt('leading_' + str(leading), accepted)
            assert events == ['tile','identity','windows','wgc']
            assert tr['status'] == 'OBSERVED' and len(tr['observation']['directions']) == 8
            assert rr['capture_attempts'] == 1 and not rr['world_visibility_verified']
            checks.append('leading_' + str(leading) + '_transients_then_terminal_complete_tail_gate_tile8_WGC_once')
        for name, index, world in [('intermittent_regression', 1, baseline),
                                   ('three_leading_partial', 2, accepted),
                                   ('last_sample_partial', 4, transient)]:
            bad = copy.deepcopy(world)
            bad['samples'][index]['observation'] = copy.deepcopy(transient['samples'][0]['observation'])
            events.clear(); _, tr, rr = attempt(name, bad)
            assert not events and tr['read_attempts'] == rr['capture_attempts'] == 0
            checks.append('refuse_' + name + '_even_if_other_samples_complete')
        for field, value in [('my_player_uid', 2), ('map_requested_i32', 1),
                              ('map_resolved_i32', 1), ('map_context_header_i32', 1),
                              ('grid_words', [32572,32951]), ('pending', 'loading'),
                              ('status', 'UNKNOWN'), ('stable_double_read', False),
                              ('my_player_count', 2), ('expected_uid_match', False)]:
            bad = copy.deepcopy(transient); bad['samples'][0]['observation'][field] = value
            events.clear(); _, tr, rr = attempt('contradictory_initial_' + field, bad)
            assert not events and tr['read_attempts'] == rr['capture_attempts'] == 0
            checks.append('initial_partial_contradiction_or_unknown_refused:' + field)
        for field,value in [('status','UNKNOWN'),('my_player_uid',2),('grid_words',[32572,32951]),
                            ('map_resolved_i32',1),('stable_double_read',False),('pending','loading'),
                            ('scene','Login'),('my_player_count',0),('expected_uid_match',False),
                            ('segment_key_words',[32765,32770]),('source_segment_grid_relation_match',False),
                            ('expected_grid_words_match',False),('map_requested_i32',1),
                            ('map_context_header_i32',1),('map_context_present',False),
                            ('coordinate_tile_entry_present',False),('coordinate_tile_resource_present',False),
                            ('land_game_layer_present',False),('diagnostic',{'stage':'UNKNOWN'})]:
            bad=copy.deepcopy(baseline);bad['samples'][2]['observation'][field]=value
            events.clear();_,tr,rr=attempt('bad_'+field,bad)
            assert not events and tr['read_attempts']==0 and rr['capture_attempts']==0
            checks.append('refuse_partial_or_changed_stability:'+field)
        for name,mutate in [('sample_count',lambda b:b['samples'].pop()),
                            ('connection',lambda b:b['samples'][4]['emission'].update(connection_id=999)),
                            ('top_connection',lambda b:b['emission'].update(connection_id=999)),
                            ('leading_connection',lambda b:b['samples'][0]['emission'].update(connection_id=999)),
                            ('retained_handle_flag',lambda b:b.update(same_retained_native_handle=False)),
                            ('identity',lambda b:b['identity'].update(pid=999))]:
            bad=copy.deepcopy(baseline);mutate(bad);events.clear();_,tr,rr=attempt('bad_'+name,bad)
            assert not events and tr['status']==rr['status']=='UNKNOWN'
            checks.append('refuse_stability_'+name)
        for mode in ('timeout','capture_exception'):
            events.clear();_,tr,rr=attempt(mode)
            assert events==['tile','identity','windows','wgc'] and tr['status']=='OBSERVED' and rr['status']=='UNKNOWN'
            assert rr['capture_attempts']==1 and '777' not in json.dumps(rr)
            checks.append('WGC_'+mode+'_isolated_UNKNOWN_preserves_tile_evidence')
        mode='success'
        for name,selected in [('absent',[]),('ambiguous',[(10,777,32,32),(10,778,32,32)])]:
            choices=selected;events.clear();_,tr,rr=attempt(name)
            assert events==['tile','identity','windows'] and tr['status']=='OBSERVED' and rr['capture_attempts']==0
            checks.append('WGC_'+name+'_no_largest_window_selection_or_fallback')
        choices=[(1024,777,32,32)]
        def failed_identity(*a):raise ValueError('EXACT_OWNED_LC_REQUIRED')
        w.identity=failed_identity;events.clear();_,tr,rr=attempt('foreign_identity')
        assert events==['tile'] and rr['capture_attempts']==0 and rr['status']=='UNKNOWN'
        checks.append('foreign_capture_identity_refused_before_HWND_selection')
        w.identity=identity_check
        def failed_tile(*a,**kw):raise RuntimeError('secret-pointer')
        t.inspect_all_attached=failed_tile;events.clear();_,tr,rr=attempt('tile_exception')
        assert events==['identity','windows','wgc'] and tr['status']=='UNKNOWN' and rr['capture_attempts']==1
        checks.append('tile_exception_isolated_UNKNOWN_WGC_can_still_observe_pixels')
        t.inspect_all_attached=tile
        for mode in ('owner_changed','handle_changed'):
            n=Native()
            try:attempt(mode)
            except ValueError as error:assert str(error)=='EXACT_RETAINED_CP73_OBSERVATION_OWNER'
            else:raise AssertionError('OWNER_REFUSAL_REQUIRED')
            assert not (d/mode/'render-capture.json').exists()
            checks.append('exact_retained_'+mode+'_refused_after_WGC')
        n=Native();mode='success'
        try:h.post_stability(n,sampler,output/'result.json',loader)
        except ValueError as error:assert str(error)=='CREATE_NEW_CP73_OBSERVATIONS_REQUIRED'
        else:raise AssertionError('OVERWRITE_REFUSAL_REQUIRED')
        checks.append('exclusive_metadata_output_overwrite_refused')
        skipped=h.skipped_first_capture(n,lambda *a:(_ for _ in ()).throw(AssertionError('NO_CAPTURE')))
        assert skipped['status']=='SKIPPED' and not skipped['focus_attempted'] and not skipped['desktop_pixels_captured']
        checks.append('first_Land_desktop_capture_suppressed_without_loading_any_pixel_API')
    saved_run=h.prior.run; saved_world=h.prior.observe_world; saved_capture=h.prior.capture_land_screen
    calls=[]
    def trial_fixture(*args):
        assert h.prior.capture_land_screen is h.skipped_first_capture
        assert h.prior.observe_world is not saved_world
        calls.append('patched_frozen_helper');return 'fixture_return'
    h.prior.run=trial_fixture
    try:
        assert h.run(None,None,None,None,None)=='fixture_return'
        assert h.prior.observe_world is saved_world and h.prior.capture_land_screen is saved_capture
        def failure(*args):trial_fixture(*args);raise RuntimeError('fixture')
        h.prior.run=failure
        try:h.run(None,None,None,None,None)
        except RuntimeError:pass
        else:raise AssertionError('FAILURE_REQUIRED')
        assert h.prior.observe_world is saved_world and h.prior.capture_land_screen is saved_capture
    finally:h.prior.run=saved_run
    checks.append('helper_overlay_function_restoration_on_return_and_exception')
    # Execute the real CP73 trial function with file-only providers. Its nested
    # finally must restore even when observation/helper cleanup raises.
    root_spec=importlib.util.spec_from_file_location('_cp73_injected_root',HERE/'root-control.py')
    root=importlib.util.module_from_spec(root_spec);root_spec.loader.exec_module(root)
    with tempfile.TemporaryDirectory() as tmp:
        trace=[];d=Path(tmp)
        fake_slot=types.SimpleNamespace(fixed_backend=lambda:contextlib.nullcontext(object()))
        def execute(action,backend):
            assert action=='PrepareEndpoint';trace.append('prepare')
            journal=root.WORK/'slot/transactions.json';journal.parent.mkdir()
            journal.write_text(json.dumps({'events':[{'phase':'PENDING'}]}),'utf-8')
        fake_slot.execute=execute
        fake_api=types.SimpleNamespace(module=lambda:fake_slot)
        fake_helper=types.SimpleNamespace(returncode=0)
        async def communicate():return b'',b''
        fake_helper.communicate=communicate
        async def create_helper(*args,**kwargs):trace.append('create_helper');return fake_helper
        async def actual():
            nonlocal n
            trace.append('owned_cleanup')
            if trial_mode=='actual_exception':raise RuntimeError('fixture_actual')
            n=Native();events.clear()
            (root.WORK/'world-read-stability.json').write_text(json.dumps(baseline),'utf-8')
            h.post_stability(n,sampler,root.WORK/'auto-ok-result.json',loader)
            assert json.loads((root.WORK/'tile-passability.json').read_bytes())['status']=='OBSERVED'
            assert json.loads((root.WORK/'render-capture.json').read_bytes())['status']=='UNKNOWN'
            return {'restoration_safe_after_owned_cleanup':True,'stop_reason':'FIXTURE_CLEANUP'}
        runtime=types.SimpleNamespace(B=types.SimpleNamespace(RUN_ID='fixture',CANDIDATE=Path('fixture.bin'),CANDIDATE_SHA='fixture'),
                                      OBSERVER=types.SimpleNamespace(FORWARD_ROOT=d),
                                      slot_api=lambda:fake_api,
                                      runtime_api=lambda:types.SimpleNamespace(actual=actual))
        root.runtime=lambda:runtime
        root.verify_review=lambda r:None
        root.installed_reviews=lambda r:trace.append('installed_review')
        def restore(r):trace.append('CONTROL_restore_attempt')
        root.restore_control=restore
        async def stop(helper):
            trace.append('helper_stop')
            if trial_mode=='stop_exception':raise RuntimeError('fixture_stop')
        root.stop_helper=stop
        original_create=root.asyncio.create_subprocess_exec
        root.asyncio.create_subprocess_exec=create_helper
        try:
            for trial_mode in ('timeout','stop_exception','actual_exception'):
                root.WORK=d/trial_mode;root.WORK.mkdir();trace.clear();mode='timeout'
                try:code=asyncio.run(root.trial())
                except RuntimeError:assert trial_mode!='timeout'
                else:assert trial_mode=='timeout' and code==0
                assert trace.count('owned_cleanup')==1 and trace.count('helper_stop')==1
                assert trace[-1]=='CONTROL_restore_attempt'
                checks.append('real_root_trial_injected_'+trial_mode+'_owned_cleanup_and_nested_finally_restore')
        finally:root.asyncio.create_subprocess_exec=original_create
    return checks

if __name__=='__main__':
    print(json.dumps({'status':'PASS_CP73_TILE_RENDER_FIXTURES','checks':run_checks(),'Native':0}))
