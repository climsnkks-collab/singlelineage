"""CP73 focused automatic Login OK retry, unchanged Native guard/lease/cleanup path."""

import ast,asyncio,hashlib,importlib.util,json,sys,types

from pathlib import Path

sys.dont_write_bytecode=True

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];WORK=ROOT/'work/local_native_login_spawn_render_retry_runtime'

PARENT=ROOT/'tools/local_native_login_create_exec_runtime'

FROZEN={'fix.py':'8d0757be9c46c330dc9c5641e5b3a7bc84963ebbc9053de1c654628020ababa5',

 'slot.py':'4af8ab28236bab3aaa37ccc7d7ca67e8fa9aa194dd6399c50ea934ea0a97f75c',

 'binding.py':'eebea14aeab082605f031a664bc3fc4deaafdf6ad9ccefb10fd438a21284a281',

 'observer.py':'2d012d357aed5d5ded00096fbefe15e491b718c56edc5895284058bdb84b8851'}

def sha(raw):return hashlib.sha256(raw).hexdigest()

def load(path,name):

    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def local(name):return load(HERE/(name+'.py'),'_key_invoke_'+name)

for name,digest in FROZEN.items():

    if sha((PARENT/name).read_bytes())!=digest:raise ValueError('FROZEN_CP06_RUNTIME')

CURRENT=load(PARENT/'fix.py','_key_invoke_current');B=local('binding');OBSERVER=local('observer');CORE=CURRENT.CORE;RUN_CORE=CURRENT.RUN_CORE

ACK_SHA='00f0e37db805a1398077ce798657a46f36a3b2ec657e6b6030e31f048459bf07'

ACK_PATH=HERE/'spawn_hook.py'

if sha(ACK_PATH.read_bytes())!=ACK_SHA:raise ValueError('EXACT_LOCAL_ACK_HOOK_REQUIRED')

ACK=load(ACK_PATH,'_cp73_local_create_wait_overlay')

for module in(CURRENT,CURRENT.CURRENT,CURRENT.SELECTED,CURRENT.SELECTED.PROCESS,CORE):

    module.HERE=HERE;module.WORK=WORK;module.B=B;module.OBSERVER=OBSERVER

CORE.observer=OBSERVER;CORE.parent.observer=OBSERVER;CORE.parent.WORK=WORK

RUN_CORE.HERE=HERE;RUN_CORE.WORK=WORK;RUN_CORE.__file__=__file__;RUN_CORE.B=B;RUN_CORE.observer=OBSERVER

fn=CORE._normal_product_binding;old='e4c627ce91cc05b5ed74cdeb175e827629fda25eb190166e8c208eeb8575f13f';new='b6233b321074a914cb4bb8d52e02fbe07c09e6c06711927bf40d4e6e865c0883'

if fn.__code__.co_consts.count(old)!=1:raise ValueError('ONE_CP07_DIRECT_PARENT')

tree=ast.parse((ROOT/'tools/local_native_login_creation_runtime/runtime.py').read_bytes())

product_fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='product_binding')

parent_changed=0;contract_changed=0

for node in ast.walk(product_fn):

    if isinstance(node,ast.Constant)and node.value=='df8a21dceaf9d9744886388737691af9498804f7735759190912f107a0dae731':node.value=new;parent_changed+=1

for index,node in enumerate(product_fn.body):

    if isinstance(node,ast.Expr)and any(isinstance(c,ast.Constant)and c.value=='EXACT_SELECTOR1_IMPORT_CALL_SOURCE'for c in ast.walk(node)):

        product_fn.body[index]=ast.parse("need(q['status']=='PASS_FILE_ONLY_COMPILED' and q['changed_encrypted_records_roundtrip']==[1,2] and q['all_undeclared_parent_ranges_identical']is True and q['selector1_raw_byte_identical']is True and q['exception_pdata_compact_header_relocation_IAT12_preserved']is True and q['old9_leaf_and_shim_IAT_bytes_preserved']is True and q['new2_stackless_leaf_algebra_verified']is True and q['original_call_return_address_preserved']is True and q['original_key_vft_DIR64_preserved']is True and q['Native_actions']==0 and q['executable_admission']is False,'EXACT_KEY_INVOKE_DECLARED_SUCCESSOR')").body[0];contract_changed+=1

if(parent_changed,contract_changed)!=(1,1):raise ValueError('ONE_CP07_PARENT_PREFLIGHT_SUCCESSOR')

product_fn.name='_key_invoke_normal_product_binding'

exec(compile(ast.fix_missing_locations(ast.Module(body=[product_fn],type_ignores=[])),__file__,'exec'),fn.__globals__)

CORE._normal_product_binding=fn.__globals__[product_fn.name]

original_source_api=CURRENT.source_api

def source_api():

    api=original_source_api();g=api.approved.__globals__

    g['SOURCES']=('fix.py','slot.py','binding.py','observer.py','root-control.py',
                 'identity_adapter.py','recover_control.py','cp49-baseline-pins.json',
                 'call2_identity.py','runtime-evidence-pins.json','world_pins.py','world-reader-pins.json','auto_enter_tile_render.py','cp57-frozen-pins.json','cp58-frozen-pins.json','cp59-frozen-pins.json','cp62-frozen-pins.json','cp63-frozen-pins.json','historical-artifacts.json','tile_render_pins.py','tile-render-pins.json','helper_failure_tail.py','helper-error-catalogue.json','image_alt.py','queries.py','diagnostic.py','spawn_hook.py','spawn-profile-pins.json','actor_profile.py','actor-profile.json','inspect_tile.py');api.SOURCES=g['SOURCES']

    g['_PINS']=dict(g['_PINS'],**{'tools/local_native_login_create_exec_runtime/'+n:h for n,h in FROZEN.items()});api._PINS=g['_PINS']

    original=g['expected_review']

    def expected(proof,config_sha256):

        row=original(proof,config_sha256);row.update(schema='native-local-auto-invoke-review-v1',

          existing_thirty_five_siblings_preserved=True,slot_creation_policy='fresh_cp74_journal_exact_cp49_owned_producer_reuse',
          fresh_one_producer_CREATE_NEW=False,owned_one_producer_exact_reuse=True,
          sibling_create_delete_rename_rewrite=False,cp49_outputs_written=False,
          spawn_experiment_policy='EXPLICIT_LOCAL_SOURCE_SPAWN_EXPERIMENT_CP73',spawn_map_id=0,spawn_uid=1,spawn_grid_words=[32571,32950],persistent_character_store_changed=False,spawn_occupancy='UNKNOWN',spawn_tile_passability_actual='UNKNOWN',tile_only_move_authority=False,
          land_probe_read_only=True,self_actor_reply_sequence='ACK_MAP_SELF_ACTOR',post_emit_sample_count=5,post_emit_capture=True,initial_transient_sample_maximum=2,terminal_consecutive_complete_sample_minimum=3,intermittent_world_regression_refused=True,first_land_capture_focus=False,first_land_capture_skipped=True,tile_passability_read_only=True,tile_passability_direction_count=8,tile_probe_count=1,wgc_capture_count_maximum=3,wgc_capture_delays_seconds=[0.0,2.0,2.0],wgc_sequence_same_retained_handle=True,wgc_sequence_world_visibility_verified=False,wgc_exact_owned_hwnd=True,wgc_ambiguous_window_refused=True,wgc_fallback=False,wgc_focus=False,world_probe_read_only=True,tile_render_claim=False,historical_snapshot_live_pins=False,historical_snapshot_review_streaming_chunk_maximum=1048576,dormant_code_execution_proven=False,source_anchor_dormancy_diagnostic_only=True,source_anchor_dormancy_policy='EXACT_COMMITTED_IMAGE_ALLOCATION_NOACCESS_SPAN',normal_server_success_proven=False,land_probe_never_proves_visible_ui_or_gameplay=True,
          first_image_failure_record_only=False,first_image_failure_record_preserved=True,
          identity_image_failure_diagnostics_maximum=2,same_retained_handle_followups_maximum=1,
          identity_followup_public_file='identity-failure-followup.json',
          existing_known_exit_predicate_unchanged=True,registry_or_guard_contract_relaxed=False,
          first_context_wait_seconds=240,other_helper_waits_and_one_second_delay_unchanged=True,
          module_readiness_wait_seconds=35,module_readiness_attempt_limit=351,
          module_readiness_diagnostic='constant_reason_native_error_aggregate_no_additional_query',

          KEY_manager_match_is_socket_epoch_or_parse_proof=False,KEY_entry_or_return_is_parse_success=False,

          forward_public_file_limit=57,forward_total_file_limit_with_context=58,

          new_KEY_VERSION_public_files=2,new_close_caller_public_files=8,

          new_connect_caller_public_files=8,new_connect_probe_public_files=8,

          close_game_stack_rvas_max=8,same_socket_OS_peer_guard=True,

          sender_probe_public_files=8,sender_count_public_files=8,

          bounded_selected_counts_sender_override=True,fixed_dto_page_public_files=1,

          bounded_factory_probe_public_files=1,local_only_ACK0_saved_roster_create=True,

          image_alternate_diagnostic_only=True,image_alternate_public_file='identity-image-alternate.json',image_alternate_query_flags1_maximum=1,image_alternate_query_k32_maximum=1,image_alternate_no_admission=True,image_alternate_original_abort_preserved=True,kernel_trace='NOT_REQUESTED')

        return row

    g['_PINS']['tools/local_native_login_local_ack_hook/ack_enter_world.py']=ACK.ACK_SHA
    g['_PINS']['tools/local_native_login_map_notify_hook/hook.py']='7cc69763edc8926c35e2a58412a6bf72282c52db9ff0c947467e8cdf219ece43'
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/spawn_hook.py']=ACK_SHA
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/spawn-profile-pins.json']=ACK.PINS_SHA
    g['_PINS'].update(ACK.pins())
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/cp57-frozen-pins.json']='418521ec28f7686ecc4945776dc03dacabd0c4927877597e8088ecb97a4b0dfe'
    g['_PINS'].update(json.loads((HERE/'cp57-frozen-pins.json').read_bytes()))
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/auto_enter_tile_render.py']='936077d13d8bf2d4e5c742f1f58aafa886299849261631a911bf96bd123acc5e'
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/cp58-frozen-pins.json']='5adf344b5c97b974f3f86c84dfbcc8605436939e80e22bab21986db1d1f4f68e'
    g['_PINS'].update(json.loads((HERE/'cp58-frozen-pins.json').read_bytes()))
    g['_PINS'].update(local('world_pins').pins())
    g['_PINS'].update(local('tile_render_pins').pins())
    g['_PINS']['tools/local_native_login_map_notify_hook/baseline.json']=ACK.BINDING_SHA
    g['_PINS']['tools/local_world_protocol/model.py']=ACK.WORLD_SHA
    g['_PINS'].update(ACK.baseline()[0]['evidence_pins'])

    g['_PINS']['tools/local_character_creation/realm.py']=ACK.REALM_SHA

    g['_PINS']['tools/local_native_auto_login/auto_click.py']='d11c4a927d4b3840e264c074d76e2cf411d33f5ad27ba6a4bbe9bb0dd1bce580'

    g['_PINS']['tools/local_native_auto_login/auto_enter_state5.py']='402c48ba628979fb00cb931a209dde809de40fc0a4d00a9c411b850425aa3312'
    g['_PINS']['tools/local_native_auto_login/auto_enter_land_probe.py']='f6a3281c6cb1ad8f6d7a76d51b51f7a4833910cbce91469c80be4fc74694a0c4'
    g['_PINS']['tools/local_native_auto_login/auto_enter_land_probe_context_wait.py']='7938b575a1a296253534c93b660eab9785c6b395800f436aefb31b3321d64551'
    g['_PINS']['tools/local_native_auto_login/auto_enter_land_probe_modules.py']='41594e5a34c815fac08748126af0d021738a8a6042aedbefd2c80d51919ef330'
    g['_PINS']['tools/local_native_auto_login/auto_enter_land_probe_map.py']='d746c692707d31a70e4c8ace4923f7bd834c9e864f2ca43edba2d11be327b405'
    g['_PINS']['tools/local_native_scene_current/inspect_land_map.py']='b60111c168560cfc2020b59d0e9f7f0880d5d70e38db38560dcd960cee80b63c'
    g['_PINS']['tools/local_native_scene_current/inspect_land.py']='2ed3e2c3caaf3508dbf50f356783710dac638c9a275d858cf45c2d007fea9273'
    g['_PINS']['tools/local_native_scene_current/capture_visible.py']='9dcdec308aa5cef67bbdf093d898368f078ea824b6a11f7a60aa7a9fb3660490'
    g['_PINS']['work/online_public_session-v4/source-contract.json']='5150ac7b24a0497210615876fb6d1560b21ed5e809809434999bbf26f6a2d222'
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/cp49-baseline-pins.json']='3e9c3b0f8a82b2047cf0d5c974f34da981bb91ec51187abd25a297c7320242bf'
    g['_PINS'].update(json.loads((HERE/'cp49-baseline-pins.json').read_bytes()))
    g['_PINS']['tools/local_native_login_spawn_render_retry_runtime/runtime-evidence-pins.json']='49d29ae968ce4c8678f147e1156fdf4f0f81dc17a32768c05ccd845fd9e1fc30'
    g['_PINS'].update(json.loads((HERE/'runtime-evidence-pins.json').read_bytes()))
    g['_PINS']['tools/local_native_scene_current/inspect_character_select.py']='77115a58a1aaf35c065ff5deeb3ec1ab815753b6136bf5f567ad379e3163bdf1'

    g['_PINS']['tools/local_native_scene_current/capture_window.py']='0ca22e5772277c58b43973266d3a61efa198b9632151fa7325c7fc73f00a4047'

    g['_PINS']['tools/local_native_scene_current/inspect_login_button.py']='92c4b35a8b6cecaa5493cd6c6b1a97d2a827da188718c1045c7bb825f1535692'

    g['_PINS']['tools/local_native_scene_current/click_owned.py']='d795561510ba95875758dd138172b80f5abee514d1ff7a13a3f73655f7ac856b'

    g['_PINS']['tools/local_character_creation_source/parse_login_csb.py']='d547c07b35d2a14da27fb58e23ff6501a628c12c4d497a057ca21e8751295e2c'

    g['_PINS']['tools/local_native_scene_current/watch.py']='a748265c8e0f155e4722e0771e54de73e2c4e7aed830ef821ca36031b10c24a6'

    original_hook=g['game_hook']

    def game_hook():return ACK.wrap(original_hook())

    g['game_hook']=game_hook;api.game_hook=game_hook

    g['expected_review']=expected;api.expected_review=expected;return api

RUN_CORE.source_api=source_api

def slot_api():return local('slot').api(source_api(),lambda:RUN_CORE.ACTIVE,RUN_CORE.base_slot)

RUN_CORE.slot_api=slot_api

def runtime_api():
    successor=local('image_alt')
    original=successor.install_runtime_factory(CORE)
    try:
        runtime=CURRENT.runtime_api()
        if not isinstance(runtime.identity_recorder,successor.Recorder):
            raise ValueError('EXACT_CP73_RUNTIME_RECORDER_REQUIRED')
        return runtime
    finally:
        CORE.identity.Recorder=original

def main():

    import argparse

    p=argparse.ArgumentParser();p.add_argument('action',choices=('Plan','PrintSlotReview','PrepareEndpoint','Run','RestoreControl'),nargs='?',default='Plan');p.add_argument('--run',action='store_true');a=p.parse_args()

    if a.action=='PrintSlotReview':print(json.dumps(slot_api().expected_review(),indent=2));return 0

    if not a.run or a.action=='Plan':print(json.dumps({'status':'PLAN_CP73_MAIN_REVIEW_REQUIRED','Native':0,'kernel_trace':'NOT_REQUESTED'}));return 0

    if a.action=='Run':

        report=asyncio.run(runtime_api().actual());return 0 if report.get('restoration_safe_after_owned_cleanup')else 2

    return slot_api().main()

if __name__=='__main__':raise SystemExit(main())

