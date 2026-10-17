"""Meaningful injected process/UI/gate failures. Never launches LC or UI."""
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import EXE,EXE_SHA,BUILD,VARIANTS,observe,public_window,PUBLIC_LAUNCHER_MESSAGES
from windows import Native,STARTUP,PROCESS,BASIC_LIMIT,LIMIT,RECT,MODULE,ACCOUNTING
import time
import ctypes
import copy
import json
import hashlib
import io
from types import SimpleNamespace
from unittest.mock import patch
import observer


def historical_closed_fixture():
    """Legacy profile's explicit historical model; today's actual state is separate."""
    rows={name:observer.load(observer.STATE/name)[0] for name in observer.ONLINE_STATE_FILES}
    for name in ('status.json','clone-status.json'):
        rows[name].update(observer.FORMER_HOST,source_sha256=observer.FORMER_SOURCE)
    rows['clone-status.json'].update(program_sha256=EXE_SHA,actualprogram_sha256=EXE_SHA,program_variant='CONTROL')
    return rows

def historical_mount_fixture(module):
    rows={name:observer.load(module.NORMAL_STATE/'status.json' if name=='normal-status.json' else observer.STATE/name)[0]
        for name in module.CLOSED_HASHES}
    for name in ('status.json','clone-status.json'):
        rows[name].update(module.FORMER_HOST,source_sha256=module.SOURCE_SHA)
    return rows


class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class Gate:
    def __init__(self,fail_at=0):self.calls=0;self.fail_at=fail_at
    def check(self):
        self.calls+=1
        if self.calls==self.fail_at:raise ValueError('fresh_isolation_changed')
        return {'verified':True,'scope':'fixed_clone_only'}


class Child:
    identity={'pid':222,'birth':'333','image':EXE,'parent_pid':111,'elevated':False,'integrity_rid':8192}


class Backend:
    def __init__(self,clock,exits=True):
        self.clock=clock;self.exits=exits;self.created=0;self.resumed=0;self.cleaned=[]
        self.assign_failed=False;self.elevated=False;self.foreign_lc=False;self.events=[]
    def controller(self):return {'pid':111,'birth':'11','elevated':self.elevated,'integrity_rid':8192}
    def inventory(self):return {'lc_count':int(self.foreign_lc),'purple':[{'pid':7956,'birth':'77'}]}
    def source(self):return {'path':EXE,'sha256':EXE_SHA,'build':BUILD}
    def create_suspended(self):self.created+=1;return Child()
    def attach_single_process_job(self,child):
        if self.assign_failed:raise ValueError('owned_job_assignment_failed_before_resume')
    def resume(self,child):self.resumed+=1
    def exit_code(self,child):return 7 if self.exits and self.clock.now>=.3 else None
    def child_token(self,child):return {'elevated':False,'integrity_rid':8192}
    def job_events(self,child):return self.events
    def windows(self,child):return [{'title':'Lineage Classic','children':[
        {'class':'Static','text':'리니지 클래식 실행은 게임 런처를 통해 실행 부탁드립니다.'},
        {'class':'Edit','text':'password-secret'},
        {'class':'Static','text':'email@example.com'}]}]
    def cleanup_owned(self,child):
        self.cleaned.append(child.identity)
        forced=self.exit_code(child)is None
        return {'forced_exit':forced,'positive_exit':True,'exit_code':1 if forced else 7,
            'method':'retained_exact_creation_handle'}
    def close(self):pass


class ObserverTests(unittest.TestCase):
    def run_case(self,backend,gate=None):
        return observe(backend,gate or Gate(),20,backend.clock,backend.clock.sleep)
    def test_natural_exit_and_public_notice_not_forced_or_playable(self):
        clock=Clock();backend=Backend(clock);gate=Gate()
        row=self.run_case(backend,gate)
        self.assertTrue(row['observed_exit']);self.assertFalse(row['forced_exit'])
        self.assertEqual(row['exit_code'],7);self.assertEqual(gate.calls,2)
        self.assertEqual(backend.created,1);self.assertEqual(backend.resumed,1)
        self.assertFalse(row['standalone_play_verified'])
        self.assertFalse(row['whole_app_network_isolation_verified'])
        self.assertIn('게임 런처',row['windows'][0]['public_launcher_text'][0])
        self.assertNotIn('password-secret',str(row));self.assertNotIn('email@example.com',str(row))
    def test_prelaunch_gate_failure_starts_nothing(self):
        backend=Backend(Clock());row=self.run_case(backend,Gate(1))
        self.assertFalse(row['launched']);self.assertEqual(backend.created,0)
    def test_gate_change_suspended_child_never_resumes(self):
        backend=Backend(Clock());row=self.run_case(backend,Gate(2))
        self.assertTrue(row['launched']);self.assertEqual(backend.resumed,0)
        self.assertEqual(len(backend.cleaned),1);self.assertTrue(row['forced_exit'])
    def test_job_assignment_failure_never_resumes_or_releases_untracked(self):
        backend=Backend(Clock());backend.assign_failed=True;row=self.run_case(backend)
        self.assertEqual(backend.resumed,0);self.assertEqual(len(backend.cleaned),1)
        self.assertTrue(row['forced_exit'])
    def test_existing_LC_blocks_without_touching_foreign_process(self):
        backend=Backend(Clock());backend.foreign_lc=True;row=self.run_case(backend)
        self.assertEqual(row['stop_reason'],'no_LC_prelaunch_required')
        self.assertEqual(backend.created,0);self.assertEqual(backend.cleaned,[])
    def test_elevated_controller_refused(self):
        backend=Backend(Clock());backend.elevated=True;row=self.run_case(backend)
        self.assertEqual(backend.created,0);self.assertFalse(row['UAC_requested'])
    def test_timeout_classifies_owned_forced_cleanup(self):
        backend=Backend(Clock(),exits=False);row=self.run_case(backend)
        self.assertEqual(row['stop_reason'],'observation_timeout')
        self.assertTrue(row['forced_exit']);self.assertFalse(row['observed_exit'])
        self.assertEqual(backend.cleaned,[Child.identity])
    def test_child_creation_limit_event_stops_owned_main_only(self):
        backend=Backend(Clock());backend.events=[{'event':'active_process_limit','new_child_runnable':False}]
        row=self.run_case(backend)
        self.assertEqual(row['stop_reason'],'SDK_child_blocked_or_job_constraint')
        self.assertEqual(backend.cleaned,[Child.identity]);self.assertTrue(row['forced_exit'])
    def test_unknown_caption_and_credentials_have_only_hash_length(self):
        row=public_window({'title':'user@example.com','children':[
            {'class':'Static','text':'PURPLE token '+'x'*50},
            {'class':'ComboBox','text':'private-account'}]})
        self.assertNotIn('user@example.com',str(row));self.assertNotIn('private-account',str(row))
        self.assertEqual(row['public_launcher_text'],[])
        self.assertEqual(len(row['unknown_static_text']),1)
    def test_default_IME_requires_actual_class_and_visibility_metadata(self):
        title='Default IME'
        self.assertEqual(hashlib.sha256(title.encode()).hexdigest(),
            'c104eb78ff3e7817dd138ea9ed95f07837e4adbbf7d90cbbd026f7b9703028e8')
        old=public_window({'title':title,'children':[]})
        self.assertNotIn('public_caption',old);self.assertNotIn('window_role',old)
        actual=public_window({'title':title,'class':'IME','visible':False,'geometry':{'width':0,'height':0},
            'owner_relation':'none','parent_relation':'outside_owned_process','children':[]})
        self.assertEqual(actual['window_role'],'Windows_default_IME_infrastructure')
        self.assertFalse(actual['game_UI_evidence']);self.assertFalse(actual['visible'])
    def test_unknown_class_private_controls_and_unapproved_notice_remain_opaque(self):
        row=public_window({'title':'private-account','class':'private-user-class','visible':True,'children':[
            {'class':'Edit','text':'secret-input'},{'class':'ComboBox','text':'private-selection'},
            {'class':'private-user-child','text':'do-not-read'},
            {'class':'Static','text':'PURPLE unknown public claim'}]})
        self.assertNotIn('private-user-class',str(row));self.assertNotIn('private-user-child',str(row))
        self.assertNotIn('secret-input',str(row));self.assertEqual(row['public_launcher_text'],[])
        self.assertEqual(row['child_class_counts']['Edit'],1)
    def test_longer_bound_has_fixed_cap_and_own_metadata_samples(self):
        class Metrics(Backend):
            def process_metrics(self,child):return {'own_thread_count':3,'cpu_total_seconds':self.clock.now,
                'SDK_initialized_proven':False,'modules':[{'basename':'LC.exe','image_bytes':39144728}]}
        backend=Metrics(Clock(),exits=False)
        row=observe(backend,Gate(),120,backend.clock,backend.clock.sleep)
        self.assertEqual(row['observation_bound_seconds'],120)
        self.assertTrue(20<=len(row['process_metadata_samples'])<=25)
        self.assertTrue(row['forced_exit']);self.assertFalse(row['standalone_play_verified'])
        with self.assertRaises(ValueError):observe(backend,Gate(),121,backend.clock,backend.clock.sleep)
    def test_startup_analysis_has_sixteen_bound_and_preserves_main_natural_exit(self):
        class Tree(Backend):
            def active_job_count(self,child):return 1 if self.clock.now<1 else 0
            def member_summary(self,child):return [{'pid':222,'birth':'333','image_basename':'LC.exe','job_membership_verified':True}]
            def job_windows(self,child):return self.windows(child)
        backend=Tree(Clock())
        row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,profile='startup-analysis')
        self.assertTrue(row['analysis_only']);self.assertEqual(row['job_active_process_limit'],16)
        self.assertTrue(row['main_natural_exit_with_owned_descendants'])
        self.assertTrue(row['observed_exit']);self.assertFalse(row['forced_exit'])
        self.assertFalse(row['whole_app_network_isolation_verified'])
        with self.assertRaises(ValueError):observe(backend,Gate(),20,backend.clock,backend.clock.sleep,
            variant='candidate',profile='startup-analysis')
    def test_high_member_metrics_continue_after_main_exit(self):
        class Tree(Backend):
            next_high=0
            def active_job_count(self,child):return int(self.clock.now<7)
            def member_summary(self,child):return []
            def job_windows(self,child):return []
            def job_metrics(self,child):
                if self.clock.now<self.next_high:return []
                self.next_high=self.clock.now+5
                return [{'owned_member':{'pid':999,'birth':'444','image_basename':'LC.exe'},
                    'sample_monotonic_seconds':self.clock.now,'cpu_total_seconds':.1}]
        backend=Tree(Clock())
        report=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,profile='online-startup-analysis')
        self.assertTrue(report['main_natural_exit_with_owned_descendants'])
        self.assertTrue(report['observed_exit']);self.assertEqual(len(report['process_metadata_samples']),2)
        self.assertGreater(report['process_metadata_samples'][1]['sample_monotonic_seconds'],.3)
    def test_cleanup_failure_reports_unknown_not_fake_success(self):
        class Broken(Backend):
            def cleanup_owned(self,child):raise ValueError('native_wait_unknown')
        row=self.run_case(Broken(Clock()))
        self.assertFalse(row['cleanup']['positive_exit']);self.assertEqual(row['cleanup']['outcome'],'unknown')
    def test_online_profile_is_CONTROL_tree_analysis_without_offline_claim(self):
        class Tree(Backend):
            def active_job_count(self,child):return 0
            def member_summary(self,child):return []
            def job_windows(self,child):return self.windows(child)
        backend=Tree(Clock());row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,
            profile='online-startup-analysis')
        self.assertTrue(row['observed_exit']);self.assertTrue(row['analysis_only'])
        self.assertFalse(row['network_isolation_required']);self.assertEqual(row['job_active_process_limit'],16)
        self.assertFalse(row['standalone_play_verified']);self.assertFalse(row['whole_app_network_isolation_verified'])
        with self.assertRaises(ValueError):observe(backend,Gate(),20,backend.clock,backend.clock.sleep,
            profile='online-startup-analysis',variant='candidate')
        with self.assertRaises(ValueError):observer.Gate(object(),'control','online-startup-analysis')
    def test_config_profile_is_unsigned_fixed_A_B_medium_only_analysis(self):
        class Trial(Backend):
            def active_job_count(self,child):return 0
            def member_summary(self,child):return []
            def job_windows(self,child):return []
        for variant in ('admin-off','admin-launcher-off'):
            backend=Trial(Clock());backend.source=lambda:{'path':EXE,'sha256':VARIANTS[variant][1],'build':BUILD}
            row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,profile='online-config-analysis',variant=variant)
            self.assertTrue(row['launched']);self.assertTrue(row['publisher_signature_content_mismatch'])
            self.assertFalse(row['stock_signature_verified']);self.assertFalse(row['operational_adoption'])
            self.assertFalse(row['standalone_play_verified']);self.assertFalse(row['network_isolation_required'])
            with self.assertRaises(ValueError):observer.Gate(object(),variant)
            with self.assertRaises(ValueError):observe(backend,Gate(),20,backend.clock,backend.clock.sleep,variant=variant)
        for variant in ('control','candidate'):
            with self.assertRaises(ValueError):observe(Trial(Clock()),Gate(),profile='online-config-analysis',variant=variant)
    def test_config_preflight_actual_shape_roundtrip_signature_and_semantics(self):
        actual=observer.load(observer.CONFIG_PREFLIGHT)[0]
        for variant in ('admin-off','admin-launcher-off'):
            proof=observer.config_preflight_proof(actual,variant)
            self.assertEqual(proof['roundtrip_checks_passed'],10);self.assertFalse(proof['publisher_signature_valid'])
            for key,value in (('SystemManager_run_as_admin',True),('publisher_signature_valid',True),
                    ('operational_adoption',True),('sha256','0'*64),('changed_semantic_count',99)):
                changed=copy.deepcopy(actual)
                trial=next(row for row in changed['trials'] if row['role']==proof['candidate_role'])
                trial[key]=value
                with self.assertRaises(ValueError):observer.config_preflight_proof(changed,variant)
            changed=copy.deepcopy(actual)
            next(row for row in changed['trials'] if row['role']==proof['candidate_role'])['checks']['recompressed_roundtrip']=False
            with self.assertRaises(ValueError):observer.config_preflight_proof(changed,variant)
        with patch.object(Path,'read_bytes',lambda path:b'wrong-candidate-bytes'):
            with self.assertRaises(ValueError):observer.fixed_candidate_slot_proof('admin-off')
    def test_C_preflight_separate_source_three_fields_twelve_checks_and_B_relation(self):
        actual=observer.load(observer.C_PREFLIGHT)[0]
        proof=observer.C_preflight_proof(actual,'sdk-multiclient')
        self.assertEqual(proof['roundtrip_checks_passed'],12);self.assertEqual(len(proof['changed_semantic_fields']),3)
        self.assertFalse(proof['publisher_signature_valid'])
        for key,value in (('SystemManager_enable_multi_client_mode',False),('publisher_signature_valid',True),
                ('sha256',VARIANTS['admin-launcher-off'][1]),('changed_semantic_count',2),
                ('no_fake_auth_ready_key_or_token',False)):
            changed=copy.deepcopy(actual);changed['trials'][0][key]=value
            with self.assertRaises(ValueError):observer.C_preflight_proof(changed,'sdk-multiclient')
        changed=copy.deepcopy(actual);changed['trials'][0]['checks']['only_one_semantic_change_from_B']=False
        with self.assertRaises(ValueError):observer.C_preflight_proof(changed,'sdk-multiclient')
        changed=copy.deepcopy(actual);changed['baseline_B']['policy']['SystemManager.enable-multi-client-mode']=True
        with self.assertRaises(ValueError):observer.C_preflight_proof(changed,'sdk-multiclient')
        with self.assertRaises(ValueError):observer.config_preflight_proof(actual,'sdk-multiclient')
        with self.assertRaises(ValueError):observer.OnlineConfigAnalysisGate(object(),'sdk-multiclient')
        with self.assertRaises(ValueError):observer.OnlineCAnalysisGate(object(),'sdk-multiclient',True)
    def test_C_medium_profile_has_fixed_hash_and_no_900_public_review(self):
        class Trial(Backend):
            def source(self):return {'path':EXE,'sha256':VARIANTS['sdk-multiclient'][1],'build':BUILD}
            def active_job_count(self,child):return 0
            def member_summary(self,child):return []
            def job_windows(self,child):return []
        backend=Trial(Clock());row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,
            profile='online-config-analysis',variant='sdk-multiclient')
        self.assertTrue(row['launched']);self.assertEqual(row['program_variant'],'SDK_MULTICLIENT')
        self.assertFalse(row['public_UI_review_requested']);self.assertTrue(row['publisher_signature_content_mismatch'])
        self.assertFalse(row['standalone_play_verified']);self.assertFalse(row['stock_signature_verified'])
        for seconds,public in ((121,False),(900,True)):
            with self.assertRaises(ValueError):observe(backend,Gate(),seconds,backend.clock,backend.clock.sleep,
                profile='online-config-analysis',variant='sdk-multiclient',public_review=public)
        args=[str(observer.HERE/'observer.py'),'--profile','online-config-analysis','--variant','sdk-multiclient']
        with patch.object(sys,'argv',args),patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(observer.main(),0)
            self.assertEqual(json.loads(output.getvalue())['root_review_path'],str(observer.C_REVIEW))
        with patch.object(sys,'argv',args+['--public-review']):
            with self.assertRaises(ValueError):observer.main()
    def test_C_gate_separate_review_and_same_readonly_absence_medium_guards(self):
        policy=observer.clone_policy();preflight,preflight_sha=observer.load(observer.C_PREFLIGHT)
        rows=historical_closed_fixture()
        hashes=dict.fromkeys(observer.ONLINE_STATE_FILES,'b'*64)
        review={'schema':'lc-clone-online-C-review-v1','reviewed':True,'profile':'online-config-analysis',
            'normal_online_analysis_authorized':True,'network_isolation_required':False,'analysis_only':True,
            'SDK_descendant_online_analysis_allowed':True,'no_concurrent_manager_launch':True,
            'candidate_code_reviewed':True,'roundtrip_preflight_verified':True,'stock_signature_verified':False,
            'publisher_signature_content_mismatch':True,'allow_verified_stock_high_relaunch':False,'operational_adoption':False,
            'program':EXE,'program_sha256':VARIANTS['sdk-multiclient'][1],'program_variant':'SDK_MULTICLIENT',
            'candidate_path':str(observer.C_CANDIDATES['sdk-multiclient']),'build':list(BUILD),
            'job_active_process_limit':16,'cleanup_scope':'owned_job_members',
            'former_host':observer.FORMER_HOST,'former_owner':observer.FORMER_OWNER,
            'admin_source_sha256':observer.ONLINE_SOURCE,'observer_source_sha256':{'mock':'a'*64},
            'closed_state_sha256':hashes,'candidate_preflight_sha256':preflight_sha,
            'public_UI_review_requested':False,'max_observation_seconds':120}
        audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()
        class Closed:
            def inactive_fixed_process(self,pid,birth,image):return {'pid':pid,'birth':birth,'inactive':True}
        def loaded(path):
            if path==observer.C_REVIEW:return review,'c'*64
            if path==observer.C_PREFLIGHT:return preflight,preflight_sha
            return rows[path.name],hashes[path.name]
        with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:observer.ONLINE_SOURCE),\
                patch.object(observer,'observer_hashes',lambda:{'mock':'a'*64}),\
                patch.object(observer.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(audit).encode())),\
                patch.object(observer.OnlineCAnalysisGate,'slot_proof',staticmethod(lambda variant:None)):
            proof=observer.OnlineCAnalysisGate(Closed(),'sdk-multiclient').check()
            self.assertTrue(proof['verified']);self.assertFalse(proof['public_review_allowed'])
            self.assertFalse(proof['high_descendants_allowed']);self.assertFalse(proof['admin_CloneInspect_C_supported'])
            for key,value in (('schema','lc-clone-online-config-analysis-review-v1'),
                    ('max_observation_seconds',900),('public_UI_review_requested',True),
                    ('program_sha256',VARIANTS['admin-launcher-off'][1]),('stock_signature_verified',True)):
                old=review[key];review[key]=value
                with self.assertRaises(ValueError):observer.OnlineCAnalysisGate(Closed(),'sdk-multiclient').check()
                review[key]=old
            audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,True)).inspect()
            with self.assertRaises(ValueError):observer.OnlineCAnalysisGate(Closed(),'sdk-multiclient').check()
    def test_config_gate_uses_real_readonly_audit_and_refuses_signature_lie_high_or_rules(self):
        policy=observer.clone_policy();preflight,preflight_sha=observer.load(observer.CONFIG_PREFLIGHT)
        rows=historical_closed_fixture()
        hashes=dict.fromkeys(observer.ONLINE_STATE_FILES,'b'*64)
        review={'schema':'lc-clone-online-config-analysis-review-v1','reviewed':True,'profile':'online-config-analysis',
            'normal_online_analysis_authorized':True,'network_isolation_required':False,'analysis_only':True,
            'SDK_descendant_online_analysis_allowed':True,'no_concurrent_manager_launch':True,
            'candidate_code_reviewed':True,'roundtrip_preflight_verified':True,'stock_signature_verified':False,
            'publisher_signature_content_mismatch':True,'allow_verified_stock_high_relaunch':False,'operational_adoption':False,
            'program':EXE,'build':list(BUILD),'job_active_process_limit':16,'cleanup_scope':'owned_job_members',
            'former_host':observer.FORMER_HOST,'former_owner':observer.FORMER_OWNER,
            'admin_source_sha256':observer.ONLINE_SOURCE,'observer_source_sha256':{'mock':'a'*64},
            'closed_state_sha256':hashes,'candidate_preflight_sha256':preflight_sha}
        audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()
        class Closed:
            def inactive_fixed_process(self,pid,birth,image):return {'pid':pid,'birth':birth,'inactive':True}
        def loaded(path):
            if path==observer.CONFIG_REVIEW:return review,'c'*64
            if path==observer.CONFIG_PREFLIGHT:return preflight,preflight_sha
            return rows[path.name],hashes[path.name]
        def run(*args,**kwargs):
            self.assertEqual(args[0][0],observer.POWERSHELL)
            self.assertTrue(args[0][-1].endswith("' -Operation Inspect"));self.assertNotIn('RunAs',args[0][-1])
            return SimpleNamespace(returncode=0,stdout=json.dumps(audit).encode())
        with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:observer.ONLINE_SOURCE),\
                patch.object(observer,'observer_hashes',lambda:{'mock':'a'*64}),patch.object(observer.subprocess,'run',run),\
                patch.object(observer.OnlineConfigAnalysisGate,'slot_proof',staticmethod(lambda variant:None)):
            for variant in ('admin-off','admin-launcher-off'):
                review.update({'program_variant':VARIANTS[variant][0],'program_sha256':VARIANTS[variant][1],
                    'candidate_path':str(observer.CONFIG_CANDIDATES[variant])})
                native=Closed();proof=observer.OnlineConfigAnalysisGate(native,variant).check()
                self.assertFalse(proof['high_descendants_allowed']);self.assertFalse(native.online_stock_high_relaunch_authorized)
                self.assertFalse(proof['admin_CloneInspect_A_B_supported']);self.assertTrue(proof['native_audit']['both_stores_absent'])
                if variant=='admin-launcher-off':
                    with self.assertRaises(ValueError):observer.OnlineConfigAnalysisGate(native,variant,True).check()
                    review.update({'public_UI_review_requested':True,'max_observation_seconds':900})
                    self.assertTrue(observer.OnlineConfigAnalysisGate(native,variant,True).check()['verified'])
                    review['max_observation_seconds']=120
                    with self.assertRaises(ValueError):observer.OnlineConfigAnalysisGate(native,variant,True).check()
                    review['max_observation_seconds']=900
                for key,value in (('stock_signature_verified',True),('allow_verified_stock_high_relaunch',True),
                        ('publisher_signature_content_mismatch',False),('candidate_preflight_sha256','0'*64)):
                    old=review[key];review[key]=value
                    with self.assertRaises(ValueError):observer.OnlineConfigAnalysisGate(native,variant).check()
                    review[key]=old
            audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,False)).inspect()
            with self.assertRaises(ValueError):observer.OnlineConfigAnalysisGate(Closed(),'admin-launcher-off').check()
    def test_public_review_CLI_is_only_B_normal_fixed900_no_seconds_override(self):
        base=[str(observer.HERE/'observer.py'),'--profile','online-config-analysis','--variant','admin-launcher-off']
        with patch.object(sys,'argv',base+['--public-review']),patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(observer.main(),0)
            plan=json.loads(output.getvalue());self.assertEqual(plan['observer_seconds'],900)
            self.assertTrue(plan['public_UI_review_requested']);self.assertFalse(plan['actual_game_started'])
        for args in (base+['--public-review','--seconds','900'],base+['--public-review','--seconds','120'],
                base+['--seconds','900'],base+['--public-review','--mode','codec-diagnostic'],
                [base[0],'--profile','online-startup-analysis','--variant','control','--public-review'],
                [base[0],'--profile','online-config-analysis','--variant','admin-off','--public-review']):
            with patch.object(sys,'argv',args):
                with self.assertRaises(ValueError):observer.main()
    def test_public_review_fake900_keeps400_metadata32_windows_and_owned_cleanup(self):
        class Review(Backend):
            count=0
            def source(self):return {'path':EXE,'sha256':VARIANTS['admin-launcher-off'][1],'build':BUILD}
            def active_job_count(self,child):return 1
            def member_summary(self,child):return []
            def job_windows(self,child):return [{'class':'GLFW30','title':'private-account',
                'visible':True,'geometry':{'width':int(self.clock.now),'height':81}}]
            def job_metrics(self,child):
                if self.count>=25:return []
                self.count+=1;return [{'member_sample_number':self.count} for _ in range(16)]
        backend=Review(Clock(),exits=False)
        row=observe(backend,Gate(),900,backend.clock,backend.clock.sleep,variant='admin-launcher-off',
            profile='online-config-analysis',public_review=True)
        self.assertTrue(900<=backend.clock.now<901);self.assertEqual(row['observation_bound_seconds'],900)
        self.assertEqual(len(row['process_metadata_samples']),400);self.assertEqual(len(row['windows']),32)
        self.assertTrue(row['forced_exit']);self.assertEqual(backend.cleaned,[Child.identity])
        self.assertFalse(row['standalone_play_verified']);self.assertNotIn('private-account',str(row))
        for kwargs in ({'seconds':899,'variant':'admin-launcher-off','profile':'online-config-analysis','public_review':True},
                {'seconds':900,'variant':'admin-off','profile':'online-config-analysis','public_review':True},
                {'seconds':900,'variant':'control','profile':'online-startup-analysis','public_review':True}):
            with self.assertRaises(ValueError):observe(Backend(Clock()),Gate(),**kwargs)
    def test_public_review_interrupt_still_cleans_exact_owned_child(self):
        class Interrupted(Backend):
            closed=False
            def job_events(self,child):raise KeyboardInterrupt()
            def close(self):self.closed=True
        backend=Interrupted(Clock(),exits=False)
        with self.assertRaises(KeyboardInterrupt):observe(backend,Gate(),20,backend.clock,backend.clock.sleep)
        self.assertEqual(backend.cleaned,[Child.identity]);self.assertTrue(backend.closed)
        window=public_window({'class':'GLFW30','visible':True})
        self.assertEqual(window['class_sha256'],'ccbfc78b6de79b018134e144ddc26e8be4005efef5aa0869ebe5345dd03189de')
        self.assertEqual(window['public_class'],'GLFW30');self.assertNotEqual(window.get('game_UI_evidence'),True)
    def test_online_gate_requires_current_review_closed_state_native_absence_and_no_clone_rules(self):
        policy=observer.clone_policy()
        rows=historical_closed_fixture()
        hashes=dict.fromkeys(observer.ONLINE_STATE_FILES,'b'*64)
        review={'schema':'lc-clone-online-analysis-review-v1','reviewed':True,'profile':'online-startup-analysis',
            'normal_online_analysis_authorized':True,'network_isolation_required':False,'analysis_only':True,
            'SDK_descendant_online_analysis_allowed':True,'no_concurrent_manager_launch':True,
            'stock_signature_verified':True,'program':EXE,'program_sha256':EXE_SHA,'program_variant':'CONTROL',
            'allow_verified_stock_high_relaunch':True,
            'build':list(BUILD),'job_active_process_limit':16,'cleanup_scope':'owned_job_members',
            'former_host':observer.FORMER_HOST,'former_owner':observer.FORMER_OWNER,
            'admin_source_sha256':observer.ONLINE_SOURCE,'observer_source_sha256':{'mock':'a'*64},
            'closed_state_sha256':hashes}
        audit={'schema':'lc-fixed-clone-native-inspect-v1','source_sha256':observer.ONLINE_SOURCE,
            'mutation_performed':False,'program_variant':'CONTROL','actualprogram_sha256':EXE_SHA,
            'audit':policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()}
        class Closed:
            active=False
            def inactive_fixed_process(self,pid,birth,image):
                if self.active:raise ValueError('former_manager_or_owner_still_live')
                return {'pid':pid,'birth':birth,'inactive':True}
        native=Closed()
        def loaded(path):
            return (review,'c'*64) if path==observer.ONLINE_REVIEW else (rows[path.name],hashes[path.name])
        def run(*args,**kwargs):
            self.assertEqual(args[0][-1],'CloneInspect');self.assertEqual(kwargs['timeout'],60)
            return SimpleNamespace(returncode=0,stdout=json.dumps(audit).encode())
        with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:observer.ONLINE_SOURCE),\
                patch.object(observer,'observer_hashes',lambda:{'mock':'a'*64}),patch.object(observer.subprocess,'run',run):
            proof=observer.OnlineAnalysisGate(native).check()
            self.assertFalse(proof['manager_present']);self.assertFalse(proof['manager_ARMED'])
            self.assertTrue(proof['native_audit']['both_stores_absent'])
            self.assertFalse(proof['network_isolation_verified'])
            for key,bad in (('normal_online_analysis_authorized',False),('network_isolation_required',True),
                    ('program_variant','CANDIDATE'),('program_sha256',VARIANTS['candidate'][1]),
                    ('observer_source_sha256',{}),('stock_signature_verified',False),
                    ('allow_verified_stock_high_relaunch',False)):
                old=review[key];review[key]=bad
                with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
                review[key]=old
            native.active=True
            with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
            native.active=False
            rows['baseline.json']['closed']=False
            with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
            rows['baseline.json']['closed']=True
            rows['clone-baseline.json']['phase']='ARMED'
            with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
            rows['clone-baseline.json']['phase']='RESTORED'
            for value in (True,False):
                audit['audit']=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,value)).inspect()
                with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
            audit['audit']=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()
            audit['program_variant']='CANDIDATE'
            with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
            audit['program_variant']='CONTROL';audit['source_sha256']='0'*64
            with self.assertRaises(ValueError):observer.OnlineAnalysisGate(native).check()
    def test_native_inactive_query_never_kills_or_accepts_live_exact_identity(self):
        class Kernel:
            wait=258;closed=[]
            def OpenProcess(self,access,inherit,pid):
                self.access=access;return 55
            def WaitForSingleObject(self,handle,timeout):return self.wait
            def CloseHandle(self,handle):self.closed.append(handle)
        native=object.__new__(Native);native.k=Kernel()
        native.identity=lambda *a,**kw:{'birth':'777','image':'fixed'}
        with self.assertRaises(ValueError):native.inactive_fixed_process(123,'777','fixed')
        self.assertEqual(native.k.access,0x101000);self.assertEqual(native.k.closed,[55])
        native.k.wait=0
        self.assertTrue(native.inactive_fixed_process(123,'777','fixed')['inactive'])
        native.k.wait=258
        self.assertEqual(native.inactive_fixed_process(123,'888','fixed')['proof'],'native_birth_reused')
        native.k.OpenProcess=lambda *a:0
        with patch.object(ctypes,'get_last_error',lambda:5):
            with self.assertRaises(ValueError):native.inactive_fixed_process(123,'777','fixed')
        with patch.object(ctypes,'get_last_error',lambda:87):
            self.assertTrue(native.inactive_fixed_process(123,'777','fixed')['inactive'])
    def test_candidate_same_path_fixed_hash_and_signature_flag(self):
        class Candidate(Backend):
            def source(self):return {'path':EXE,'sha256':VARIANTS['candidate'][1],'build':BUILD}
        backend=Candidate(Clock())
        row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,variant='candidate')
        self.assertTrue(row['observed_exit']);self.assertEqual(row['program_variant'],'CANDIDATE')
        self.assertTrue(row['publisher_signature_content_mismatch']);self.assertFalse(row['operational_adoption'])
        backend=Backend(Clock())
        wrong=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,variant='candidate')
        self.assertFalse(wrong['launched']);self.assertEqual(backend.created,0)
    def test_receipt_role_and_current_native_audit_hash_must_match_variant(self):
        producer={'pid':123,'birth':'456'};source='a'*64
        class Producer:
            def producer(self,*args):return {'live':True,'elevated':True}
        for variant in ('control','candidate'):
            role,expected=VARIANTS[variant]
            policy=observer.clone_policy()
            state={'schema':'lc-fixed-clone-status-v1','phase':'ARMED','verified':True,
                'program':EXE,'program_sha256':expected,'program_variant':role,'rules':list(policy.NAMES)}
            review={'schema':'lc-clone-observer-root-review-v1','reviewed':True,'program':EXE,
                'program_sha256':expected,'program_variant':role,'plan_sha256':'b'*64,
                'installed_sha256':'c'*64,'admin_source_sha256':source,'producer':producer}
            installed={'actual_admin_operation':True,'verified':True,'program':EXE,
                'program_sha256':expected,'program_variant':role,'source_sha256':source,'producer':producer}
            status={'schema':'lc-fixed-runtime-status-v1','closed':False,'error':None,'status_error':None,
                'source_sha256':source,'pid':123,'birth':'456','clone_isolation':state}
            def loaded(path):
                if path==observer.REVIEW:return review,'d'*64
                if path==observer.PLAN:return {},'b'*64
                if path==observer.INSTALLED:return installed,'c'*64
                return status,'e'*64
            def audit(*args,**kwargs):
                row={'schema':'lc-fixed-clone-native-inspect-v1','source_sha256':source,
                    'mutation_performed':False,'program_variant':role,
                    'actualprogram_sha256':state['program_sha256'],
                    'audit':policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,True)).inspect()}
                return SimpleNamespace(returncode=0,stdout=json.dumps(row).encode())
            with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:source),patch.object(observer.subprocess,'run',audit):
                self.assertTrue(observer.Gate(Producer(),variant).check()['verified'])
                if variant=='control':
                    with self.assertRaises(ValueError):observer.Gate(Producer(),variant,'startup-analysis').check()
                    review.update({'profile':'startup-analysis','analysis_only':True,
                        'SDK_descendant_online_analysis_allowed':True,'job_active_process_limit':16,
                        'cleanup_scope':'owned_job_members'})
                    self.assertTrue(observer.Gate(Producer(),variant,'startup-analysis').check()['verified'])
                installed['program_variant']='CONTROL' if role=='CANDIDATE' else 'CANDIDATE'
                with self.assertRaises(ValueError):observer.Gate(Producer(),variant).check()
                installed['program_variant']=role;state['program_sha256']='0'*64
                with self.assertRaises(ValueError):observer.Gate(Producer(),variant).check()
    def test_real_native_wrapper_absent_foreign_profile_false_are_refused(self):
        path=Path(__file__).resolve().parent/'fixtures/native-inspect-readonly.json'
        recorded=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(recorded['schema'],'lc-fixed-clone-native-inspect-v1')
        policy=observer.clone_policy();source=recorded['source_sha256']
        absent=copy.deepcopy(recorded)
        absent['audit']['rules']={name:{'persistent':None,'active':None} for name in policy.NAMES}
        with self.assertRaises(ValueError):observer.native_audit_proof(absent,source,'CONTROL',EXE_SHA,policy.NAMES)
        present=copy.deepcopy(recorded)
        present['audit']=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,True)).inspect()
        self.assertTrue(observer.native_audit_proof(present,source,'CONTROL',EXE_SHA,policy.NAMES)['both_stores_enabled'])
        foreign=copy.deepcopy(present)
        foreign['audit']['rules'][policy.NAMES[0]]['active']['scope']['program']='foreign.exe'
        with self.assertRaises(ValueError):observer.native_audit_proof(foreign,source,'CONTROL',EXE_SHA,policy.NAMES)
        disabled=copy.deepcopy(present);disabled['audit']['profiles_enabled']=False
        with self.assertRaises(ValueError):observer.native_audit_proof(disabled,source,'CONTROL',EXE_SHA,policy.NAMES)
        wrong_names=copy.deepcopy(present)
        with self.assertRaises(ValueError):observer.native_audit_proof(wrong_names,source,'CONTROL',EXE_SHA,['foreign'])


@unittest.skipUnless(os.name=='nt','Windows native ABI/self-token query only')
class NativeOwnQueryTests(unittest.TestCase):
    def test_64bit_job_process_structures_match_documented_ABI(self):
        if ctypes.sizeof(ctypes.c_void_p)!=8:self.skipTest('64-bit fixture')
        self.assertEqual(ctypes.sizeof(STARTUP),104)
        self.assertEqual(ctypes.sizeof(PROCESS),24)
        self.assertEqual(ctypes.sizeof(BASIC_LIMIT),64)
        self.assertEqual(ctypes.sizeof(LIMIT),144)
        self.assertEqual(ctypes.sizeof(RECT),16)
        self.assertEqual(ctypes.sizeof(MODULE),1080)
        self.assertEqual(ctypes.sizeof(ACCOUNTING),48)
    def test_current_controller_native_birth_image_integrity_query_only(self):
        backend=Native()
        try:
            identity=backend.controller()
            self.assertEqual(identity['pid'],os.getpid())
            self.assertTrue(identity['birth'].isdigit())
            # Windows Store aliases can report a different executable path than
            # sys.executable. Native image is independently queried for own PID.
            self.assertTrue(Path(identity['image']).is_absolute())
            self.assertEqual(Path(identity['image']).suffix.casefold(),'.exe')
            self.assertIsInstance(identity['elevated'],bool)
            self.assertIsInstance(identity['integrity_rid'],int)
        finally:backend.close()
    def test_current_process_module_CPU_thread_metadata_only(self):
        backend=Native()
        try:
            child=SimpleNamespace(process=backend.k.GetCurrentProcess(),pid=os.getpid(),
                identity=backend.controller(),create_return_clock=time.monotonic())
            row=backend.process_metrics(child)
            self.assertGreaterEqual(row['kernel_cpu_seconds'],0)
            self.assertGreaterEqual(row['user_cpu_seconds'],0)
            self.assertGreaterEqual(row['own_thread_count'],1)
            self.assertGreater(len(row['modules']),0)
            self.assertFalse(row['SDK_initialized_proven'])
            self.assertTrue(row['module_observation_complete'])
            self.assertTrue(all(set(item)=={'basename','image_bytes','file_version'} for item in row['modules']))
            self.assertNotIn('base',row);self.assertNotIn('path',row)
        finally:backend.close()
    def test_denied_module_query_is_incomplete_not_SDK_absence(self):
        native=Native.__new__(Native);native.retained_alive=lambda child:True
        def times(handle,creation,ended,kernel,user):creation._obj.low=123;return True
        native.k=SimpleNamespace(GetProcessTimes=times,
            CreateToolhelp32Snapshot=lambda flags,pid:ctypes.c_void_p(-1).value)
        child=SimpleNamespace(process=17,pid=222,identity={'birth':'123'},create_return_clock=time.monotonic())
        with patch.object(ctypes,'get_last_error',lambda:5):row=native.process_metrics(child)
        self.assertFalse(row['module_observation_complete']);self.assertEqual(row['module_query_error'],5)
        self.assertEqual(row['thread_query_error'],5);self.assertEqual(row['SDK_images_present'],[])
        self.assertFalse(row['SDK_initialized_proven'])
    def test_foreign_HWND_and_changed_birth_refused_before_metadata(self):
        backend=Native.__new__(Native)
        backend.retained_alive=lambda child:True
        def pid(hwnd,pointer):pointer._obj.value=999;return 8
        backend.u=SimpleNamespace(IsWindow=lambda hwnd:True,GetWindowThreadProcessId=pid)
        self.assertFalse(backend.owned_hwnd(SimpleNamespace(pid=222),10))
        backend.k=SimpleNamespace(WaitForSingleObject=lambda *args:258)
        backend.identity=lambda *args,**kwargs:{'pid':222,'birth':'changed','image':EXE,'parent_pid':111}
        child=SimpleNamespace(pid=222,process=17,identity=Child.identity)
        del backend.retained_alive
        with self.assertRaises(ValueError):backend.retained_alive(child)
    def test_foreign_admin_token_denial_does_not_invent_verified_elevation(self):
        backend=Native.__new__(Native);closed=[]
        backend.k=SimpleNamespace(OpenProcess=lambda *args:17,WaitForSingleObject=lambda *args:258,
            CloseHandle=lambda handle:closed.append(handle))
        def identity(handle,pid,parent_pid=None,include_token=True):
            self.assertFalse(include_token)
            return {'birth':'456','image':'fixed-python.exe'}
        def denied(handle):raise ValueError('token_query_failed')
        backend.identity=identity;backend.token=denied
        proof=backend.producer(123,'456','fixed-python.exe')
        self.assertTrue(proof['live']);self.assertFalse(proof['elevation_token_verified'])
        self.assertNotIn('elevated',proof);self.assertEqual(closed,[17])
    def test_new_member_must_belong_exact_job_and_tree_bound(self):
        native=Native.__new__(Native);closed=[]
        native.k=SimpleNamespace(OpenProcess=lambda *args:19,
            IsProcessInJob=lambda handle,job,pointer:True,CloseHandle=lambda handle:closed.append(handle))
        child=SimpleNamespace(job=20,members={222:SimpleNamespace()},member_events=[],identity={'birth':'333'})
        with self.assertRaises(ValueError):native.capture_member(child,999)
        self.assertEqual(closed,[19])
        child.members=dict.fromkeys(range(16),SimpleNamespace())
        with self.assertRaises(ValueError):native.capture_member(child,999)
    def test_job_cleanup_uses_retained_job_only_and_no_PID_termination(self):
        native=Native.__new__(Native);calls=[]
        native.profile='startup-analysis';native.exit_code=lambda child:None if not calls else 1
        native.active_job_count=lambda child:1 if not calls else 0
        def membership(handle,job,pointer):pointer._obj.value=True;return True
        native.k=SimpleNamespace(WaitForSingleObject=lambda handle,timeout:0 if calls else 258,IsProcessInJob=membership,
            TerminateJobObject=lambda job,code:calls.append(('job',job)) or True,
            GetProcessTimes=lambda *args:False,
            CloseHandle=lambda handle:None)
        child=SimpleNamespace(pid=222,process=17,thread=18,job=20,port=21,members={})
        child.members[222]=child
        outcome=native.cleanup_owned_job(child)
        self.assertEqual(calls,[('job',20)]);self.assertTrue(outcome['owned_job_empty'])
        self.assertTrue(outcome['forced_exit'])
    def test_refused_member_metadata_is_bounded_and_criteria_remain_enforced(self):
        native=Native.__new__(Native);closed=[]
        def membership(handle,job,pointer):pointer._obj.value=True;return True
        native.k=SimpleNamespace(OpenProcess=lambda *args:19,IsProcessInJob=membership,
            CloseHandle=lambda handle:closed.append(handle))
        native.identity=lambda *args,**kwargs:{'pid':999,'birth':'222','image':r'C:\Program Files\PublicSDK\SDK.exe'}
        native.token=lambda handle:{'elevated':True,'integrity_rid':12288}
        child=SimpleNamespace(job=20,members={},member_events=[],identity={'birth':'333'})
        with self.assertRaises(ValueError) as refusal:native.capture_member(child,999)
        row=refusal.exception.owned_member_refusal
        self.assertEqual(row['failed_criteria'],['birth_before_owned_main','elevated_token','integrity_above_medium'])
        self.assertEqual(row['image_basename'],'SDK.exe');self.assertEqual(row['birth'],'222')
        self.assertTrue(row['job_membership_verified']);self.assertTrue(row['elevated'])
        self.assertEqual(row['integrity_rid'],12288);self.assertNotIn('Program Files',str(row))
        self.assertEqual(child.members,{});self.assertEqual(child.refused_members[0].process,19)
        self.assertEqual(closed,[])
        class Refused(Backend):
            def job_events(self,child):raise refusal.exception
        backend=Refused(Clock())
        report=self.run_mock_refusal(backend)
        self.assertEqual(report['owned_member_refusal']['image_basename'],'SDK.exe')
        self.assertNotIn('Program Files',str(report));self.assertTrue(report['forced_exit'])
    def run_mock_refusal(self,backend):
        return observe(backend,Gate(),20,backend.clock,backend.clock.sleep)
    def test_job_empty_before_native_signal_waits_exact_handles_and_rechecks_exit(self):
        native=Native.__new__(Native);calls=[];signaled=set();terminated=[]
        native.exit_code=lambda child:1 if child.process in signaled else None
        native.active_job_count=lambda child:0 if terminated else 2
        def membership(handle,job,pointer):pointer._obj.value=True;return True
        def wait(handle,timeout):
            calls.append((handle,timeout))
            if timeout:signaled.add(handle)
            return 0 if handle in signaled else 258
        native.k=SimpleNamespace(WaitForSingleObject=wait,IsProcessInJob=membership,
            TerminateJobObject=lambda job,code:terminated.append(job) or True,GetProcessTimes=lambda *args:False,
            CloseHandle=lambda handle:None)
        child=SimpleNamespace(pid=222,process=17,thread=18,job=20,port=21,members={})
        child.members[222]=child;child.refused_members=[SimpleNamespace(process=19,pid=999)]
        outcome=native.cleanup_owned_job(child)
        self.assertTrue(outcome['positive_exit']);self.assertTrue(outcome['retained_members_signaled'])
        self.assertEqual(outcome['exit_code'],1);self.assertEqual(terminated,[20])
        self.assertEqual(signaled,{17,19});self.assertTrue(all(0<=timeout<=5000 for _,timeout in calls))
        self.assertTrue(outcome['forced_exit']);self.assertEqual(outcome['retained_member_count'],2)
    def test_only_online_verified_exact_CONTROL_high_relaunch_is_allowed(self):
        def scenario(profile,image=EXE,sha=EXE_SHA,authorized=True,rid=12288,elevated=True,birth='444'):
            native=Native.__new__(Native);native.profile=profile;native.pinned_control_sha256=sha
            native.online_stock_high_relaunch_authorized=authorized
            def membership(handle,job,pointer):pointer._obj.value=True;return True
            native.k=SimpleNamespace(OpenProcess=lambda *args:19,IsProcessInJob=membership,CloseHandle=lambda handle:None)
            native.identity=lambda *args,**kwargs:{'pid':999,'birth':birth,'image':image,'parent_pid':None}
            native.token=lambda handle:{'elevated':elevated,'integrity_rid':rid}
            child=SimpleNamespace(job=20,members={},member_events=[],identity={'birth':'333'})
            return native,child
        native,child=scenario('online-startup-analysis');native.capture_member(child,999)
        member=child.members[999]
        self.assertTrue(member.high_as_actual_normal_app_relaunch);self.assertTrue(member.identity['elevated'])
        self.assertEqual(member.identity['integrity_rid'],12288);self.assertTrue(member.exact_fixed_path)
        failures=[scenario('single'),scenario('startup-analysis'),scenario('online-config-analysis'),
            scenario('online-startup-analysis',image=r'D:\Lineage Classic\LC.exe'),
            scenario('online-startup-analysis',image=r'C:\Unreviewed\LC.exe'),
            scenario('online-startup-analysis',sha=VARIANTS['candidate'][1]),
            scenario('online-startup-analysis',authorized=False),
            scenario('online-startup-analysis',rid=16384),
            scenario('online-startup-analysis',elevated=False),
            scenario('online-startup-analysis',birth='333'),
            scenario('online-startup-analysis',birth='222')]
        for native,child in failures:
            with self.assertRaises(ValueError) as refusal:native.capture_member(child,999)
            self.assertEqual(child.members,{})
            row=refusal.exception.owned_member_refusal
            self.assertIn('exact_fixed_path',row);self.assertNotIn('C:\\Unreviewed',str(row))
            if row['known_original_program']:self.assertFalse(row['exact_fixed_path'])
    def test_public_window_access_denial_is_metadata_error_not_privilege_retry(self):
        native=Native.__new__(Native);native.owned_hwnd=lambda child,hwnd:True
        def denied(*args):ctypes.set_last_error(5);return 0
        native.u=SimpleNamespace(GetClassNameW=denied,GetWindowRect=denied,IsWindowVisible=lambda hwnd:False,
            GetWindow=lambda *args:0,GetAncestor=lambda *args:0)
        row=native.window_meta(SimpleNamespace(),10)
        self.assertEqual(row['public_metadata_errors'],[{'operation':'class','winerror':5},
            {'operation':'geometry','winerror':5}])
        public=public_window(row)
        self.assertEqual(public['public_metadata_errors'],row['public_metadata_errors'])
        self.assertNotIn('hwnd',public)
    def test_final_all_member_native_codes_lifetimes_and_natural_exit_are_distinct(self):
        native=Native.__new__(Native);native.active_job_count=lambda child:0;closed=[]
        def exitcode(handle,pointer):pointer._obj.value={17:1,19:3}[handle];return True
        def times(handle,creation,ended,kernel,user):
            creation._obj.low={17:111,19:222}[handle]
            ended._obj.low=creation._obj.low+10000000
            return True
        native.k=SimpleNamespace(WaitForSingleObject=lambda handle,timeout:0,GetExitCodeProcess=exitcode,
            GetProcessTimes=times,CloseHandle=lambda handle:closed.append(handle))
        main=SimpleNamespace(pid=222,process=17,thread=18,job=20,port=21,members={},
            identity={'birth':'111','image':EXE,'elevated':False,'integrity_rid':8192},first_capture_clock=1.0)
        high=SimpleNamespace(pid=333,process=19,identity={'birth':'222','image':EXE,'elevated':True,'integrity_rid':12288},
            first_capture_clock=2.0,high_as_actual_normal_app_relaunch=True)
        main.members={222:main,333:high}
        result=native.cleanup_owned_job(main)
        self.assertEqual([row['exit_code'] for row in result['final_owned_members']],[1,3])
        self.assertTrue(all(row['native_lifetime_seconds']==1.0 for row in result['final_owned_members']))
        self.assertTrue(all(row['exit_classification']=='natural_exit_no_force_requested' for row in result['final_owned_members']))
        self.assertTrue(result['final_owned_members'][1]['high_as_actual_normal_app_relaunch'])
        self.assertFalse(result['job_members_forced_cleanup']);self.assertEqual(closed.count(19),1)
    def test_job_metrics_immediate_new_member_bound_and_optional_CPU_denial(self):
        native=Native.__new__(Native);native.retained_alive=lambda member:True
        def membership(handle,job,pointer):pointer._obj.value=True;return True
        native.k=SimpleNamespace(WaitForSingleObject=lambda handle,timeout:258,IsProcessInJob=membership)
        main=SimpleNamespace(pid=222,process=17,identity={'birth':'111','image':EXE,'elevated':False,'integrity_rid':8192},
            first_capture_clock=0,create_return_clock=0)
        child=SimpleNamespace(job=20,members={222:main})
        native.process_metrics=lambda member:{'cpu_total_seconds':1,'modules':[],'SDK_initialized_proven':False}
        with patch.object(time,'monotonic',lambda:1):self.assertEqual(len(native.job_metrics(child)),1)
        with patch.object(time,'monotonic',lambda:2):self.assertEqual(native.job_metrics(child),[])
        high=SimpleNamespace(pid=333,process=19,identity={'birth':'222','image':EXE,'elevated':True,'integrity_rid':12288},
            first_capture_clock=2,create_return_clock=2,high_as_actual_normal_app_relaunch=True)
        child.members[333]=high
        with patch.object(time,'monotonic',lambda:2):
            immediate=native.job_metrics(child);self.assertEqual(len(immediate),1)
            self.assertTrue(immediate[0]['owned_member']['high_as_actual_normal_app_relaunch'])
        high.metadata_sample_count=25
        def denied(member):raise ValueError('own_CPU_time_query_failed')
        native.process_metrics=denied
        with patch.object(time,'monotonic',lambda:7),patch.object(ctypes,'get_last_error',lambda:5):
            rows=native.job_metrics(child);self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['public_metadata_errors'],[{'operation':'CPU','winerror':5}])
        main.metadata_sample_count=25
        with patch.object(time,'monotonic',lambda:999):self.assertEqual(native.job_metrics(child),[])
    def test_job_policy_readback_16_no_breakaway_before_resume(self):
        native=Native.__new__(Native);native.process_limit=16;seen=[]
        def set_info(job,kind,pointer,size):
            if kind==9:
                limits=pointer._obj;seen.append((limits.basic.active_limit,limits.basic.flags))
            return True
        def query(job,kind,pointer,size,length):
            pointer._obj.basic.active_limit=16;pointer._obj.basic.flags=0x2008;return True
        def membership(process,job,pointer):pointer._obj.value=True;return True
        native.k=SimpleNamespace(CreateJobObjectW=lambda *args:20,SetInformationJobObject=set_info,
            QueryInformationJobObject=query,CreateIoCompletionPort=lambda *args:21,
            AssignProcessToJobObject=lambda *args:True,IsProcessInJob=membership)
        child=SimpleNamespace(pid=222,process=17,members={},job_assigned=False)
        native.attach_single_process_job(child)
        self.assertEqual(seen,[(16,0x2008)]);self.assertTrue(child.job_assigned)
        self.assertEqual(set(child.members),{222})


class RouteBTests(unittest.TestCase):
    def fixture(self):
        preflight,preflight_sha=observer.load(observer.ROUTE_PREFLIGHT)
        rows=historical_closed_fixture()
        hashes={name:observer.load(observer.STATE/name)[1] for name in observer.ONLINE_STATE_FILES}
        review={'schema':'lc-clone-online-route-B-review-v1','reviewed':True,'profile':'online-config-analysis',
            'normal_online_analysis_authorized':True,'network_isolation_required':False,'analysis_only':True,
            'SDK_descendant_online_analysis_allowed':True,'no_concurrent_manager_launch':True,
            'candidate_code_reviewed':True,'roundtrip_preflight_verified':True,'stock_signature_verified':False,
            'publisher_signature_content_mismatch':True,'allow_verified_stock_high_relaunch':False,'operational_adoption':False,
            'program':EXE,'program_sha256':VARIANTS['route-b'][1],'program_variant':'ROUTE_B',
            'candidate_path':str(observer.ROUTE_CANDIDATES['route-b']),'build':list(BUILD),
            'job_active_process_limit':16,'cleanup_scope':'owned_job_members',
            'former_host':observer.FORMER_HOST,'former_owner':observer.FORMER_OWNER,
            'admin_source_sha256':observer.ONLINE_SOURCE,'observer_source_sha256':{'mock':'a'*64},
            'closed_state_sha256':hashes,'candidate_preflight_sha256':preflight_sha,
            'candidate_producer_sha256':observer.ROUTE_PRODUCER_SHA,'public_UI_review_requested':False,
            'max_observation_seconds':120,'route_candidate_reviewed':True,'whole_app_isolation_proven':False,
            'SDK_auth_ready_patch':False,'route':{'ipv4':'127.0.0.1','port':12000},
            'slot_file_id':'c98478ce:0000c600e8b60600','slot_trial_family':observer.ROUTE_FAMILY,
            'slot_transaction_sha256':'d'*64,'slot_provenance_sha256':'e'*64}
        return preflight,review,rows,hashes

    def history(self,review):
        provenance={'schema':'lc-fixed-config-trial-control-snapshot-v1','trial_family':observer.ROUTE_FAMILY,
            'program':EXE,'slot_file_id':review['slot_file_id'],'snapshot_file_id':'c98478ce:1111c600e8b60600',
            'length':39144728,'control_sha256':EXE_SHA,'admin_source_sha256':observer.ONLINE_SOURCE,
            'closed_state_sha256':review['closed_state_sha256'],'preflight_sha256':observer.ROUTE_PREFLIGHT_SHA,
            'producer_sha256':observer.ROUTE_PRODUCER_SHA}
        document={'schema':'lc-fixed-config-trial-transactions-v1','trial_family':observer.ROUTE_FAMILY,
            'slot_file_id':review['slot_file_id'],'control_sha256':EXE_SHA,'candidate_sha256':{'PrepareRouteB':VARIANTS['route-b'][1]},
            'length':39144728,'admin_source_sha256':observer.ONLINE_SOURCE,'closed_state_sha256':review['closed_state_sha256'],
            'snapshot_provenance_sha256':'e'*64,'preflight_sha256':observer.ROUTE_PREFLIGHT_SHA,
            'producer_sha256':observer.ROUTE_PRODUCER_SHA,'events':[]}
        for phase in ('INTENT','COMPLETE'):
            event={'index':len(document['events']),'action':'PrepareRouteB','phase':phase,'before':EXE_SHA,
                'after':VARIANTS['route-b'][1],'previous_sha256':document['events'][-1]['sha256'] if document['events'] else '0'*64}
            event['sha256']=hashlib.sha256((json.dumps(event,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
            document['events'].append(event)
        return document,provenance

    def test_route_actual_fixed_preflight_43B_and_two_B_values_only(self):
        actual,review,rows,hashes=self.fixture()
        proof=observer.route_preflight_proof(actual,'route-b')
        self.assertEqual(proof['whole_frames_verified'],7);self.assertEqual(proof['code_patch_range_bytes'],43)
        self.assertFalse(proof['publisher_signature_valid']);self.assertFalse(proof['SDK_auth_ready_patch'])
        bads=[('producer_sha256','0'*64),('source_sha256','0'*64),('variant','ADMIN_LAUNCHER_OFF')]
        for key,value in bads:
            changed=copy.deepcopy(actual);changed[key]=value
            with self.assertRaises(ValueError):observer.route_preflight_proof(changed,'route-b')
        for role,key,value in (('code_patch','host_port',14000),('code_patch','host_code_RVA',['0x32f3c0','0x32f3eb']),
            ('configuration','SystemManager.enable-multi-client-mode',True),('configuration','B_payload_byteexact',False),
            ('limits','SDK_auth_ready_patch',True),('checks','seven_whole_candidate_records_roundtrip',False)):
            changed=copy.deepcopy(actual);changed[role][key]=value
            with self.assertRaises(ValueError):observer.route_preflight_proof(changed,'route-b')
        with self.assertRaises(ValueError):observer.route_preflight_proof(actual,'sdk-multiclient')

    def test_route_own_transaction_chain_rejects_AB_foreign_incomplete_or_restored(self):
        _,review,_,_=self.fixture();document,provenance=self.history(review)
        proof=observer.route_transaction_proof(document,provenance,review,'e'*64)
        self.assertEqual(proof['active_action'],'PrepareRouteB')
        for key,value in (('trial_family','C_SDK_HELPER'),('candidate_sha256',{'PrepareB':VARIANTS['admin-launcher-off'][1]}),
            ('slot_file_id','c98478ce:2222c600e8b60600'),('producer_sha256','0'*64)):
            changed=copy.deepcopy(document);changed[key]=value
            with self.assertRaises(ValueError):observer.route_transaction_proof(changed,provenance,review,'e'*64)
        for change in ('incomplete','hash','before','action'):
            changed=copy.deepcopy(document)
            if change=='incomplete':changed['events'].pop()
            elif change=='hash':changed['events'][0]['sha256']='0'*64
            elif change=='before':changed['events'][0]['before']=VARIANTS['admin-launcher-off'][1]
            else:changed['events'][1]['action']='RestoreControl'
            with self.assertRaises(ValueError):observer.route_transaction_proof(changed,provenance,review,'e'*64)
        provenance['trial_family']='AB_STARTUP_POLICY'
        with self.assertRaises(ValueError):observer.route_transaction_proof(document,provenance,review,'e'*64)

    def test_route_gate_reuses_native_absence_closed_state_and_rule_absence(self):
        preflight,review,rows,hashes=self.fixture();policy=observer.clone_policy();slots=[]
        audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()
        class Closed:
            active=False
            def inactive_fixed_process(self,pid,birth,image):return {'pid':pid,'birth':birth,'inactive':not self.active}
        def loaded(path):
            if path==observer.ROUTE_REVIEW:return review,'c'*64
            if path==observer.ROUTE_PREFLIGHT:return preflight,observer.ROUTE_PREFLIGHT_SHA
            return rows[path.name],hashes[path.name]
        with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:observer.ONLINE_SOURCE),\
                patch.object(observer,'observer_hashes',lambda:{'mock':'a'*64}),\
                patch.object(observer.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(audit).encode())),\
                patch.object(observer.OnlineRouteBAnalysisGate,'slot_proof',staticmethod(lambda variant:slots.append(variant))):
            native=Closed();gate=observer.OnlineRouteBAnalysisGate(native,'route-b');proof=gate.check()
            self.assertEqual(slots,['route-b','route-b']);self.assertFalse(proof['public_review_allowed'])
            self.assertFalse(native.online_stock_high_relaunch_authorized);self.assertFalse(proof['whole_app_isolation_proven'])
            self.assertEqual(proof['route']['port'],12000)
            for key,value in (('schema','lc-clone-online-C-review-v1'),('max_observation_seconds',900),
                ('public_UI_review_requested',True),('candidate_preflight_sha256','0'*64),('SDK_auth_ready_patch',True),
                ('stock_signature_verified',True),('allow_verified_stock_high_relaunch',True)):
                old=review[key];review[key]=value
                with self.assertRaises(ValueError):gate.check()
                review[key]=old
            native.active=True
            with self.assertRaises(ValueError):gate.check()
            native.active=False;audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,False)).inspect()
            with self.assertRaises(ValueError):gate.check()
            audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect();rows['status.json']['closed']=False
            with self.assertRaises(ValueError):gate.check()

    def test_route_default_plan_fixed120_and_public_review_rejected(self):
        base=[str(observer.HERE/'observer.py'),'--profile','online-config-analysis','--variant','route-b']
        with patch.object(sys,'argv',base),patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(observer.main(),0);plan=json.loads(output.getvalue())
            self.assertEqual(plan['root_review_path'],str(observer.ROUTE_REVIEW));self.assertFalse(plan['actual_game_started'])
            self.assertEqual(plan['active_process_limit'],16);self.assertFalse(plan['breakaway'])
        for args in (base+['--public-review'],base+['--seconds','900'],base+['--mode','codec-diagnostic'],
            [base[0],'--variant','route-b']):
            with patch.object(sys,'argv',args):
                with self.assertRaises(ValueError):observer.main()

    def test_route_actual_mock_timeout_owned_cleanup_and_no_high_or_foreign_hash(self):
        class Trial(Backend):
            def source(self):return {'path':EXE,'sha256':VARIANTS['route-b'][1],'build':BUILD}
            def active_job_count(self,child):return 1
            def member_summary(self,child):return []
            def job_windows(self,child):return []
        backend=Trial(Clock(),exits=False)
        row=observe(backend,Gate(),120,backend.clock,backend.clock.sleep,variant='route-b',profile='online-config-analysis')
        self.assertTrue(row['forced_exit']);self.assertEqual(backend.cleaned,[Child.identity])
        self.assertEqual(row['program_variant'],'ROUTE_B');self.assertFalse(row['standalone_play_verified'])
        self.assertFalse(row['whole_app_network_isolation_verified'])
        backend=Trial(Clock(),exits=False)
        backend.create_suspended=lambda:SimpleNamespace(identity={**Child.identity,'elevated':True,'integrity_rid':12288})
        row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,variant='route-b',profile='online-config-analysis')
        self.assertEqual(backend.resumed,0);self.assertTrue(row['forced_exit'])
        backend=Trial(Clock());backend.source=lambda:{'path':EXE,'sha256':VARIANTS['admin-launcher-off'][1],'build':BUILD}
        row=observe(backend,Gate(),20,backend.clock,backend.clock.sleep,variant='route-b',profile='online-config-analysis')
        self.assertFalse(row['launched']);self.assertEqual(backend.created,0)


class RootMountTests(unittest.TestCase):
    def module(self):
        names=('slot.py','tests.py')
        review={'slot_source_sha256':{n:hashlib.sha256((observer.MOUNT_TOOL/n).read_bytes()).hexdigest() for n in names},
            'slot_manifest_sha256':observer.load(observer.MOUNT_TOOL/'manifest.json')[1],
            'slot_profile_sha256':observer.load(observer.MOUNT_TOOL/'profile.json')[1]}
        return observer.mount_slot_module(review),review
    def test_fixed_root_mount_source_preflight_and_today_closed_family(self):
        module,_=self.module()
        self.assertEqual(observer.MOUNT_WORK,module.WORK)
        self.assertEqual(observer.MOUNT_SNAPSHOT,module.BACKUP)
        preflight,sha=observer.load(observer.MOUNT_PREFLIGHT)
        self.assertEqual(sha,observer.MOUNT_PREFLIGHT_SHA)
        self.assertFalse(observer.mount_preflight_proof(module,preflight)['SDK_auth_ready_patch'])
        rows=historical_mount_fixture(module)
        self.assertTrue(module.validate_closed_rows(rows))
        bad=copy.deepcopy(rows);bad['normal-status.json']['core_alive']=True
        with self.assertRaises(ValueError):module.validate_closed_rows(bad)
        for mutate in ('ready','span','role'):
            bad=copy.deepcopy(preflight)
            if mutate=='ready':bad['limits']['provider_ready_or_UI_completion_forced']=True
            elif mutate=='span':bad['patches'][0]['span']=7
            else:bad['variant']='ROUTE_B'
            with self.assertRaises(ValueError):observer.mount_preflight_proof(module,bad)
    def test_fixed_support_manifest_source_drift_refused(self):
        _,review=self.module()
        for key in ('slot_manifest_sha256','slot_profile_sha256'):
            bad=copy.deepcopy(review);bad[key]='0'*64
            with self.assertRaises(ValueError):observer.mount_slot_module(bad)
        bad=copy.deepcopy(review);bad['slot_source_sha256']['slot.py']='0'*64
        with self.assertRaises(ValueError):observer.mount_slot_module(bad)
    def test_mount_prepare_chain_partial_wrong_family_and_restored_history_refused(self):
        module,_=self.module()
        backend=SimpleNamespace(slot=SimpleNamespace(file_id='00000000:0000000000000000'),control_sha=EXE_SHA,
            candidate_shas={'PrepareRootMount':VARIANTS['root-mount-route-b'][1]},size=39144728,provenance_sha='a'*64)
        doc={**module.proof_header(backend),'events':[]}
        module.append_event(doc,'PrepareRootMount','INTENT',EXE_SHA,VARIANTS['root-mount-route-b'][1])
        self.assertEqual(module.validate_proof(doc,backend)['phase'],'INTENT')
        module.append_event(doc,'PrepareRootMount','COMPLETE',EXE_SHA,VARIANTS['root-mount-route-b'][1])
        self.assertEqual(module.validate_proof(doc,backend)['phase'],'COMPLETE')
        bad=copy.deepcopy(doc);bad['trial_family']=observer.ROUTE_FAMILY
        with self.assertRaises(ValueError):module.validate_proof(bad,backend)
        bad=copy.deepcopy(doc);bad['closed_state_sha256']={}
        with self.assertRaises(ValueError):module.validate_proof(bad,backend)
        bad=copy.deepcopy(doc);bad['events'][1]['sha256']='0'*64
        with self.assertRaises(ValueError):module.validate_proof(bad,backend)
    def test_root_mount_plan_only_fixed_profile_variant_normal120(self):
        base=[str(observer.HERE/'observer.py'),'--profile','root-mount-analysis','--variant','root-mount-route-b']
        with patch.object(sys,'argv',base),patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(observer.main(),0);row=json.loads(output.getvalue())
        self.assertEqual(row['observer_seconds'],120);self.assertEqual(row['active_process_limit'],16)
        self.assertEqual(row['root_review_path'],str(observer.MOUNT_REVIEW))
        self.assertFalse(row['actual_game_started']);self.assertFalse(row['network_isolation_required'])
        for args in (base+['--public-review'],base+['--seconds','25'],base+['--mode','codec-diagnostic'],
            [base[0],'--profile','online-config-analysis','--variant','root-mount-route-b'],
            [base[0],'--profile','root-mount-analysis','--variant','route-b']):
            with patch.object(sys,'argv',args):
                with self.assertRaises(ValueError):observer.main()
    def test_root_mount_mock_owned_job_timeout_source_and_medium_only(self):
        class Trial(Backend):
            def source(self):return {'path':EXE,'sha256':VARIANTS['root-mount-route-b'][1],'build':BUILD}
            def active_job_count(self,child):return 1
            def member_summary(self,child):return []
            def job_windows(self,child):return []
        backend=Trial(Clock(),exits=False)
        row=observe(backend,Gate(),120,backend.clock,backend.clock.sleep,variant='root-mount-route-b',profile='root-mount-analysis')
        self.assertTrue(row['forced_exit']);self.assertEqual(backend.cleaned,[Child.identity])
        self.assertFalse(row['PURPLE_absent_at_start']);self.assertFalse(row['cold_PURPLE_independence_verified'])
        self.assertFalse(row['memory_state_sampler_enabled']);self.assertFalse(row['standalone_play_verified'])
        backend=Trial(Clock());backend.source=lambda:{'path':EXE,'sha256':VARIANTS['route-b'][1],'build':BUILD}
        row=observe(backend,Gate(),120,backend.clock,backend.clock.sleep,variant='root-mount-route-b',profile='root-mount-analysis')
        self.assertFalse(row['launched'])
        backend=Trial(Clock());backend.create_suspended=lambda:SimpleNamespace(identity={**Child.identity,'elevated':True,'integrity_rid':12288})
        row=observe(backend,Gate(),120,backend.clock,backend.clock.sleep,variant='root-mount-route-b',profile='root-mount-analysis')
        self.assertEqual(backend.resumed,0);self.assertTrue(row['forced_exit'])
    def test_root_mount_full_gate_requires_today_closed_scope_and_cold_choice(self):
        module,support=self.module();real_load=observer.load
        review={**support,'schema':'lc-clone-root-mount-review-v1','reviewed':True,'profile':'root-mount-analysis',
            'normal_online_analysis_authorized':True,'analysis_only':True,'network_isolation_required':False,
            'whole_app_isolation_proven':False,'program':EXE,'program_variant':'ROOT_MOUNT_ROUTE_B',
            'program_sha256':VARIANTS['root-mount-route-b'][1],'build':list(BUILD),'candidate_path':str(observer.MOUNT_CANDIDATE),
            'candidate_code_reviewed':True,'roundtrip_preflight_verified':True,'stock_signature_verified':False,
            'publisher_signature_content_mismatch':True,'operational_adoption':False,'SDK_auth_ready_patch':False,
            'allow_verified_stock_high_relaunch':False,'job_active_process_limit':16,'cleanup_scope':'owned_job_members',
            'public_UI_review_requested':False,'max_observation_seconds':120,'no_concurrent_manager_launch':True,
            'candidate_preflight_sha256':observer.MOUNT_PREFLIGHT_SHA,'candidate_producer_sha256':observer.MOUNT_PRODUCER_SHA,
            'admin_source_sha256':observer.ONLINE_SOURCE,'observer_source_sha256':observer.observer_hashes(),
            'closed_state_sha256':dict(module.CLOSED_HASHES),'require_PURPLE_absent':False}
        class N:
            active=False;foreign=False;purple=True;pins=[]
            def inactive_fixed_process(self,*args):return {'inactive':not self.active}
            def inventory(self):return {'lc_count':int(self.foreign),'purple':[{'pid':77}] if self.purple else []}
            def pin_evidence(self,paths):self.pins.extend(paths)
        native=N();policy=observer.clone_policy()
        audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()
        historical=historical_mount_fixture(module)
        def loaded(path):
            if path==observer.MOUNT_REVIEW:return review,'a'*64
            for name in module.CLOSED_HASHES:
                p=module.NORMAL_STATE/'status.json' if name=='normal-status.json' else observer.STATE/name
                if path==p:return historical[name],module.CLOSED_HASHES[name]
            return real_load(path)
        assets=[{'path':'data/mock-'+str(i)+'.txt','size':1,'sha256':hashlib.sha256(b'x').hexdigest()} for i in range(67)]
        paths={Path(observer.CLONE)/a['path'] for a in assets}
        original_bytes=Path.read_bytes;original_stat=Path.stat
        def bytes_(path):return b'x' if path in paths else original_bytes(path)
        def stat_(path,*args,**kwargs):return SimpleNamespace(st_size=1) if path in paths else original_stat(path,*args,**kwargs)
        with patch.object(observer,'load',loaded),patch.object(observer,'mount_slot_module',return_value=module),\
            patch.object(observer,'mount_slot_proof',return_value={'active_action':'PrepareRootMount'}),\
            patch.object(module,'fixed_assets',return_value=assets),patch.object(observer,'plain',lambda p:None),\
            patch.object(Path,'read_bytes',bytes_),patch.object(Path,'stat',stat_),\
            patch.object(observer.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(audit).encode())):
            gate=observer.RootMountAnalysisGate(native);proof=gate.check()
            self.assertEqual(proof['materialized_fixed_assets'],67);self.assertFalse(proof['PURPLE_absent'])
            self.assertFalse(proof['cold_PURPLE_independence_verified']);self.assertFalse(native.online_stock_high_relaunch_authorized)
            self.assertTrue(native.pins)
            review['require_PURPLE_absent']=True
            with self.assertRaises(ValueError):gate.check()
            native.purple=False;self.assertTrue(gate.check()['PURPLE_absent'])
            native.active=True
            with self.assertRaises(ValueError):gate.check()
            native.active=False;native.foreign=True
            with self.assertRaises(ValueError):gate.check()
            native.foreign=False;audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,False)).inspect()
            with self.assertRaises(ValueError):gate.check()
            audit=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,None)).inspect()
            review['closed_state_sha256']={}
            with self.assertRaises(ValueError):gate.check()


class CurrentResourceTests(unittest.TestCase):
    def module(self):
        t=observer.CURRENT_TOOL
        review={'slot_source_sha256':{n:hashlib.sha256((t/n).read_bytes()).hexdigest()for n in ('slot.py','tests.py')},
            'slot_manifest_sha256':observer.load(t/'manifest.json')[1],'slot_profile_sha256':observer.load(t/'profile.json')[1]}
        return observer.mount_slot_module(review,observer.CurrentResourceAnalysisGate),review
    def test_frozen_current_slot_V2_closed_and_actual_prepare_proof_readonly(self):
        module,review=self.module()
        self.assertEqual(module.WORK,observer.CURRENT_WORK);self.assertEqual(module.BACKUP,observer.CURRENT_SNAPSHOT)
        rows={n:observer.load(module.NORMAL_STATE/'status.json'if n=='normal-status.json'else observer.STATE/n)[0]for n in module.CLOSED_HASHES}
        self.assertTrue(module.validate_closed_rows(rows))
        self.assertEqual(rows['normal-status.json']['family'],'ORIGINAL_NORMAL_ONLINE_RESOURCE_PROOF_V2')
        review.update(slot_trial_family=observer.CURRENT_FAMILY,closed_state_sha256=module.CLOSED_HASHES,
            slot_file_id=observer.load(module.PROVENANCE)[0]['slot_file_id'],
            slot_transaction_sha256=observer.load(module.TRANSACTIONS)[1],slot_provenance_sha256=observer.load(module.PROVENANCE)[1])
        self.assertEqual(observer.mount_slot_proof(module,review,observer.CurrentResourceAnalysisGate)['active_action'],'PrepareCurrentResource')
        review['slot_trial_family']=observer.MOUNT_FAMILY
        with self.assertRaises(ValueError):observer.mount_slot_proof(module,review,observer.CurrentResourceAnalysisGate)
    def test_current_plan_exact_profile_variant120_no900_no_codec(self):
        base=[str(observer.HERE/'observer.py'),'--profile','current-resource-analysis','--variant','current-resource-root-mount']
        with patch.object(sys,'argv',base),patch('sys.stdout',new_callable=io.StringIO)as output:
            self.assertEqual(observer.main(),0);plan=json.loads(output.getvalue())
        self.assertEqual(plan['root_review_path'],str(observer.CURRENT_REVIEW));self.assertEqual(plan['observer_seconds'],120)
        self.assertEqual(plan['active_process_limit'],16);self.assertFalse(plan['actual_game_started'])
        for args in(base+['--public-review'],base+['--seconds','20'],base+['--mode','codec-diagnostic'],
            [base[0],'--profile','root-mount-analysis','--variant','current-resource-root-mount']):
            with patch.object(sys,'argv',args):
                with self.assertRaises(ValueError):observer.main()
    def test_current_mock_typical_companion_is_not_whole_runtime_absence(self):
        class B(Backend):
            def source(self):return {'path':EXE,'sha256':VARIANTS['current-resource-root-mount'][1],'build':BUILD}
            def inventory(self):return {'lc_count':0,'purple':[{'image_basename':'purpleon.exe'}],
                'purple_apps':[],'purple_companions':[{'image_basename':'purpleon.exe','app_or_service_classification':'unknown'}]}
            def active_job_count(self,c):return 1
            def member_summary(self,c):return []
            def job_windows(self,c):return []
        b=B(Clock(),exits=False)
        r=observe(b,Gate(),120,b.clock,b.clock.sleep,variant='current-resource-root-mount',profile='current-resource-analysis')
        self.assertTrue(r['PURPLE_app_absent_at_start']);self.assertFalse(r['PURPLE_absent_at_start'])
        self.assertFalse(r['cold_PURPLE_independence_verified']);self.assertTrue(r['forced_exit'])


class CodecDiagnosticTests(unittest.TestCase):
    def fixture(self):
        policy=observer.clone_policy();physical=policy.MockCloneAdapter(dict.fromkeys(policy.NAMES,True)).inspect()
        nonce='1'*32;nonce_sha=hashlib.sha256(bytes.fromhex(nonce)).hexdigest()
        state={'schema':'lc-fixed-clone-status-v1','phase':'CLEANUP_PENDING','error':'ArmFailed','verified':False,
            'program':EXE,'program_sha256':EXE_SHA,'program_variant':'CONTROL','rules':list(policy.NAMES)}
        runtime={'schema':'lc-fixed-runtime-status-v1','phase':'RECOVERY_REQUIRED','error':'UnicodeDecodeError',
            'closed':False,'status_error':None,'clone_isolation':state}
        response={'status':'FAILED','pid':observer.CODEC_PRODUCER['pid'],'birth':observer.CODEC_PRODUCER['birth'],
            'source_sha256':observer.CODEC_SOURCE,'nonce_sha256':nonce_sha,'runtime':copy.deepcopy(runtime)}
        current={**runtime,**observer.CODEC_PRODUCER,'source_sha256':observer.CODEC_SOURCE,'nonce_sha256':nonce_sha}
        review={'schema':'lc-clone-codec-diagnostic-review-v1','reviewed':True,'no_admin_repair_during_observation':True,
            'program':EXE,'program_sha256':EXE_SHA,'program_variant':'CONTROL','admin_source_sha256':observer.CODEC_SOURCE,
            'producer':observer.CODEC_PRODUCER,'failed_arm_request_id':observer.FAILED_ARM,
            'failed_arm_result_sha256':'b'*64,'physical_audit_sha256':'c'*64}
        request={'schema':'lc-fixed-command-v1','action':'ArmCloneIsolation','id':observer.FAILED_ARM,
            'source_sha256':observer.CODEC_SOURCE,'nonce':nonce}
        session={**observer.CODEC_PRODUCER,'source_sha256':observer.CODEC_SOURCE,'nonce':nonce}
        def loaded(path):
            if path==observer.CODEC_REVIEW:return review,'a'*64
            if path==observer.PHYSICAL_AUDIT:return physical,'c'*64
            if path==observer.STATE/'session.json':return session,'d'*64
            if path==observer.STATE/'status.json':return current,'e'*64
            if path.parent.name=='results':return response,'b'*64
            return request,'f'*64
        class Producer:
            def producer(self,*args):return {'live':True,'image_verified':True,'elevation_token_verified':False}
        return Producer(),loaded,current,physical

    def test_specific_codec_fault_physical_true_and_known_clone_hold(self):
        producer,loaded,current,physical=self.fixture()
        def inspect(*args,**kwargs):return SimpleNamespace(returncode=0,stdout=json.dumps(physical).encode())
        with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:observer.CODEC_SOURCE),patch.object(observer.subprocess,'run',inspect):
            gate=observer.CodecDiagnosticGate(producer);proof=gate.check()
            self.assertEqual(proof['condition'],'RULE_VERIFIED_HOST_CODEC_FAULT')
            self.assertFalse(proof['manager_ARMED']);self.assertFalse(proof['manager_operation_succeeded'])
            current['error']='ValueError';current['clone_isolation']['error']='CloneStillLive'
            with self.assertRaises(ValueError):gate.check()
            gate.owned_child_created(Child.identity)
            self.assertEqual(gate.check()['manager_clone_error'],'CloneStillLive')

    def test_missing_scope_profile_false_unknown_fault_and_candidate_refused(self):
        producer,loaded,current,physical=self.fixture()
        def inspect(*args,**kwargs):return SimpleNamespace(returncode=0,stdout=json.dumps(physical).encode())
        with patch.object(observer,'load',loaded),patch.object(observer,'admin_digest',lambda:observer.CODEC_SOURCE),patch.object(observer.subprocess,'run',inspect):
            gate=observer.CodecDiagnosticGate(producer)
            current['error']='PermissionError'
            with self.assertRaises(ValueError):gate.check()
            current['error']='UnicodeDecodeError';physical['profiles_enabled']=False
            with self.assertRaises(ValueError):gate.check()
            physical['profiles_enabled']=True
            name=next(iter(physical['rules']));physical['rules'][name]['active']=None
            with self.assertRaises(ValueError):gate.check()
        with patch.object(sys,'argv',['observer.py','--mode','codec-diagnostic','--variant','candidate']):
            with self.assertRaises(ValueError):observer.main()


if __name__=='__main__':unittest.main(verbosity=2)
