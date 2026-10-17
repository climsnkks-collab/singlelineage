"""Default file-only Plan. --run requires reviewed, installed, fresh clone gate."""
import argparse
import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import ctypes as C
from ctypes import wintypes as W
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core import EXE, EXE_SHA, CLONE, BUILD, VARIANTS, PROFILES, require, observe
from windows import Native

ROOT=Path(r'C:\Users\Chansol\Documents\ChatGPT\싱글리니지')
HERE=ROOT/'tools/clone_observer'
ADMIN=ROOT/'tools/admin_runtime'
STATE=ADMIN/'state-handoff-live'
PLAN=ROOT/'work/clone-isolation-plan.json'
INSTALLED=ROOT/'work/clone-isolation-installed.json'
REVIEW=HERE/'root-review.json'
ONLINE_REVIEW=HERE/'root-online-analysis-review.json'
CONFIG_REVIEW=HERE/'root-online-config-analysis-review.json'
CONFIG_PREFLIGHT=ROOT/'work/standalone_boot/startup-policy-trials-preflight.json'
CONFIG_CANDIDATES={
    'admin-off':ROOT/'work/standalone_boot/current-systemmanager-admin-false.candidate.bin',
    'admin-launcher-off':ROOT/'work/standalone_boot/current-systemmanager-admin-and-launcher-false.candidate.bin'}
C_REVIEW=HERE/'root-C-review.json'
C_PREFLIGHT=ROOT/'work/standalone_boot/sdk-multiclient-preflight.json'
C_CANDIDATES={'sdk-multiclient':ROOT/'work/standalone_boot/current-sdk-multiclient.candidate.bin'}
ROUTE_REVIEW=HERE/'root-route-B-review.json'
ROUTE_PREFLIGHT=ROOT/'work/local-route-static-trial.json'
ROUTE_PREFLIGHT_SHA='7b7326c21d708b5d335944e0b419eff968c72b431099905d4629226893de1718'
ROUTE_PRODUCER=ROOT/'work/local-route-static-trial.py'
ROUTE_PRODUCER_SHA='22f8c15bdd908544b093a8abe356a79333b083ea993a4da92e4e5efed8395f01'
ROUTE_CANDIDATES={'route-b':ROOT/'work/local-route-static-trial.candidate.bin'}
ROUTE_WORK=ROOT/'work/route_startup_trial'
ROUTE_TRANSACTIONS=ROUTE_WORK/'transactions.json'
ROUTE_PROVENANCE=ROUTE_WORK/'control.provenance.json'
ROUTE_SNAPSHOT=ROUTE_WORK/'control.snapshot.bin'
ROUTE_FAMILY='ROUTE_B_LOCAL_SOCKET'
MOUNT_REVIEW=HERE/'root-mount-review.json'
MOUNT_TOOL=ROOT/'tools/root_mount_startup_trial'
MOUNT_WORK=ROOT/'work/root_mount_resume'
MOUNT_PREFLIGHT=ROOT/'work/local-mode-adapter-trial.json'
MOUNT_PREFLIGHT_SHA='52dcf828a3be383e0438c688d229a420b5f9d419e2f71ed0473168c74d04aed8'
MOUNT_PRODUCER=ROOT/'work/local-mode-adapter-trial.py'
MOUNT_PRODUCER_SHA='75e80e7404abf7a65052f7059e86e6079297d5b374cafcc430c29cc9187dcb5d'
MOUNT_CANDIDATE=ROOT/'work/local-mode-adapter-trial.candidate.bin'
MOUNT_SNAPSHOT=MOUNT_WORK/'control.snapshot.bin'
MOUNT_FAMILY='ROOT_MOUNT_ROUTE_B_LOCAL_SOCKET'
MOUNT_STATE_TOOL=ROOT/'tools/root_mount_public_state'
CURRENT_REVIEW=HERE/'root-current-resource-review.json'
CURRENT_TOOL=ROOT/'tools/current_resource_trial'
CURRENT_WORK=ROOT/'work/current_resource_trial'
CURRENT_SNAPSHOT=CURRENT_WORK/'control.snapshot.bin'
CURRENT_FAMILY='CURRENT_PRESERVED_RESOURCE_ROOT_MOUNT'
ONLINE_SOURCE='3cebc7134275c20142da90482cbd9bad118599949835c42fe9c3d1f5444e32d8'
FORMER_SOURCE='d09bb08e5cb0c8e4c2e9495c5a2f6f93ac520e213b82c35f32b77564d939fff1'
FORMER_HOST={'pid':12460,'birth':'134355830290220367'}
FORMER_OWNER={'pid':40940,'birth':'134355829987543068'}
POWERSHELL=r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
OBSERVER_SOURCES=('core.py','windows.py','observer.py','tests.py')
ONLINE_STATE_FILES=('status.json','baseline.json','clone-baseline.json','clone-status.json','launcher-status.json')
CODEC_REVIEW=HERE/'root-codec-diagnostic-review.json'
PHYSICAL_AUDIT=ROOT/'work/clone-native-current-audit.json'
CODEC_SOURCE='f06ab41b7b1e3e2f1240eaf812de7705af6f40635275329d132fb0e72af06bbc'
CODEC_PRODUCER={'pid':38688,'birth':'134355790844375964'}
FAILED_ARM='6982de69aa544cefacb01ebff03e2fc3'
PYTHON=Path(r'C:\Users\Chansol\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')


def plain(path):
    require(path.is_absolute() and path.resolve(strict=False)==path,'fixed_canonical_path_required')
    for part in (path,*path.parents):
        if part.exists():
            require(not part.is_symlink() and not getattr(part.stat(),'st_file_attributes',0)&0x400,'reparse_path_refused')


def load(path):
    plain(path);raw=path.read_bytes();require(len(raw)<=32768,'metadata_bound')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def admin_digest():
    raw=(ADMIN/'entry.py').read_bytes()
    tree=ast.parse(raw.decode('utf-8-sig'))
    assignments=[node for node in tree.body if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='SOURCES' for target in node.targets)]
    require(len(assignments)==1,'admin_literal_SOURCES_required')
    names=ast.literal_eval(assignments[0].value)
    require(type(names) in (tuple,list) and len(names)==14
        and len(set(names))==14 and all(type(name)is str and '/' not in name and '\\' not in name for name in names),
        'reviewed_admin_fourteen_sources_required')
    digest=hashlib.sha256()
    for name in names:
        path=ADMIN/name;plain(path)
        digest.update(name.encode());digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def clone_policy():
    """Reviewed admin module's pure scope validator; no adapter instantiation."""
    path=ADMIN/'clone_isolation.py';plain(path)
    spec=importlib.util.spec_from_file_location('_observer_reviewed_clone_scope',path)
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(ADMIN))
    try:spec.loader.exec_module(module)
    finally:sys.path.remove(str(ADMIN))
    require(str(module.PROGRAM)==EXE and module.ACCEPTED_HASHES==
        {VARIANTS[key][1]:VARIANTS[key][0] for key in ('control','candidate')},
        'reviewed_clone_policy_program_family_required')
    return module


def native_audit_proof(row,source,variant,expected_sha,live_names):
    policy=clone_policy()
    require(row.get('schema')=='lc-fixed-clone-native-inspect-v1'
        and row.get('mutation_performed')is False and row.get('source_sha256')==source
        and row.get('program_variant')==variant and row.get('actualprogram_sha256')==expected_sha,
        'fresh_native_clone_source_variant_required')
    # CloneInspect deliberately does not invent lifecycle ARMED state. Its
    # pure full audit supplies both raw stores and firewall profile facts.
    values=policy.validate_audit(row.get('audit'))
    require(tuple(live_names)==tuple(policy.NAMES)
        and values==dict.fromkeys(policy.NAMES,True)
        and row['audit']['profiles_enabled']is True,'fresh_full_both_store_rule_audit_required')
    return {'rule_count':len(policy.NAMES),'profiles_enabled':True,'both_stores_enabled':True}


class Gate:
    def __init__(self, native, variant='control',profile='single'):
        require(variant in ('control','candidate'),'fixed_control_or_candidate_variant_required')
        self.native=native
        self.variant,self.expected_sha=VARIANTS[variant]
        require(profile in ('single','startup-analysis'),'fixed_isolated_gate_profile_required');self.profile=profile

    def check(self):
        review,_=load(REVIEW)
        require(review.get('schema')=='lc-clone-observer-root-review-v1' and review.get('reviewed')is True
            and review.get('program')==EXE and review.get('program_sha256')==self.expected_sha
            and review.get('program_variant')==self.variant,
            'root_code_review_record_required')
        if self.profile=='startup-analysis':
            require(self.variant=='CONTROL' and review.get('profile')=='startup-analysis'
                and review.get('analysis_only')is True and review.get('SDK_descendant_online_analysis_allowed')is True
                and review.get('job_active_process_limit')==16 and review.get('cleanup_scope')=='owned_job_members',
                'explicit_startup_analysis_scope_review_required')
        plan,plan_sha=load(PLAN);installed,installed_sha=load(INSTALLED)
        require(review.get('plan_sha256')==plan_sha and review.get('installed_sha256')==installed_sha,
            'reviewed_plan_and_actual_receipt_digest_required')
        source=admin_digest();require(source==review.get('admin_source_sha256'),'current_admin_sources_required')
        status,_=load(STATE/'status.json')
        require(status.get('schema')=='lc-fixed-runtime-status-v1' and status.get('closed')is False
            and 'error' in status and status['error']is None and status.get('status_error')is None
            and status.get('source_sha256')==source,'live_error_free_admin_status_required')
        producer=review.get('producer',{})
        require((status.get('pid'),status.get('birth'))==(producer.get('pid'),producer.get('birth')),
            'original_install_producer_claim_required')
        require(installed.get('actual_admin_operation')is True and installed.get('verified')is True
            and installed.get('program')==EXE and installed.get('program_sha256')==self.expected_sha
            and installed.get('program_variant')==self.variant
            and installed.get('source_sha256')==source
            and installed.get('producer')==producer,'actual_fixed_clone_install_receipt_required')
        native_producer=self.native.producer(producer['pid'],producer['birth'],str(PYTHON))
        state=status.get('clone_isolation',{})
        require(state.get('schema')=='lc-fixed-clone-status-v1' and state.get('phase')=='ARMED'
            and state.get('verified')is True and state.get('program')==EXE
            and state.get('program_sha256')==self.expected_sha and state.get('program_variant')==self.variant,
            'armed_live_clone_gate_required')
        result=subprocess.run([str(PYTHON),'-I','-B',str(ADMIN/'entry.py'),'CloneInspect'],
            capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        require(result.returncode==0 and len(result.stdout)<=32768,'fresh_native_clone_audit_required')
        audit=native_audit_proof(json.loads(result.stdout.decode('utf-8-sig')),source,
            self.variant,self.expected_sha,state.get('rules',[]))
        return {'verified':True,'scope':'fixed_clone_direct_program_rules_only','producer':native_producer,
            'source_sha256':source,'plan_sha256':plan_sha,'installed_sha256':installed_sha,
            'native_audit':audit,
            'whole_app_isolation_proven':False}


def observer_hashes():
    hashes={}
    for name in OBSERVER_SOURCES:
        path=HERE/name;plain(path)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def closed_online_state(rows,policy):
    """Validate actual CLOSED records, not a replacement for live ARMED."""
    status=rows['status.json'];clone=rows['clone-status.json'];launcher=rows['launcher-status.json']
    require(status.get('schema')=='lc-fixed-runtime-status-v1' and status.get('phase')=='CLOSED'
        and status.get('closed')is True and 'error' in status and status['error']is None
        and status.get('status_error')is None
        and (status.get('pid'),status.get('birth'))==(FORMER_HOST['pid'],FORMER_HOST['birth'])
        and status.get('source_sha256')==FORMER_SOURCE,'closed_former_runtime_required')
    require(clone.get('schema')=='lc-fixed-clone-status-v1' and clone.get('phase')=='RESTORED'
        and clone.get('closed')is True and 'error' in clone and clone['error']is None
        and clone.get('program')==EXE and clone.get('actualprogram_sha256')==EXE_SHA
        and clone.get('program_sha256')==EXE_SHA and clone.get('program_variant')=='CONTROL'
        and (clone.get('pid'),clone.get('birth'))==(FORMER_HOST['pid'],FORMER_HOST['birth'])
        and clone.get('source_sha256')==FORMER_SOURCE,'closed_restored_CONTROL_record_required')
    require(launcher.get('schema')=='lc-fixed-launcher-status-v1' and launcher.get('phase')=='HOST_EXITED'
        and launcher.get('backend')=='windows' and launcher.get('host_retained')is False
        and launcher.get('host')==FORMER_HOST and launcher.get('owner')==FORMER_OWNER
        and launcher.get('source_sha256')==FORMER_SOURCE,'former_launcher_closed_record_required')
    baseline=rows['baseline.json']
    # The original legacy gate baseline was both enabled; this is not a claim
    # that those original-path rules provide normal online connectivity.
    fingerprints={
        'CodexSoloLC-c7b05daa-e47b-4800-a00d-561bdc562056-12000':
            'a1b94609d23fef365e6d84e7b6195103b6d6d5885dd74a58c85873d57bdcd89a',
        'CodexSoloLC-c7b05daa-e47b-4800-a00d-561bdc562056-14000':
            '92252be853e7ba77936b7077db0a85f4346f43b565093f90eec8b24b2c374554'}
    values=dict.fromkeys(fingerprints,True)
    require(set(baseline)=={'schema','backend','baseline_enabled','baseline_sha256','scope_fingerprints','closed','phase'}
        and baseline['schema']=='lc-fixed-baseline-ledger-v1' and baseline['backend']=='windows'
        and baseline['closed']is True and baseline['phase']=='CLOSED'
        and baseline['scope_fingerprints']==fingerprints
        and baseline['baseline_enabled']==values
        and all(type(value)is bool for value in baseline['baseline_enabled'].values())
        and baseline['baseline_sha256']==hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest(),
        'strict_closed_legacy_baseline_required')
    ledger=rows['clone-baseline.json']
    require(policy.validate_ledger(ledger,'windows')==dict.fromkeys(policy.NAMES,None)
        and ledger['closed']is True and ledger['phase']=='RESTORED','strict_closed_absent_clone_baseline_required')
    require(clone.get('scope_sha256')==policy.scope_hashes()
        and tuple(clone.get('rules',[]))==tuple(policy.NAMES),'closed_clone_scope_identity_required')


def online_audit_proof(row,policy):
    require(row.get('schema')=='lc-fixed-clone-native-inspect-v1'
        and row.get('source_sha256')==ONLINE_SOURCE and row.get('mutation_performed')is False
        and row.get('program_variant')=='CONTROL' and row.get('actualprogram_sha256')==EXE_SHA,
        'online_fresh_CONTROL_native_source_required')
    require(policy.validate_audit(row.get('audit'))==dict.fromkeys(policy.NAMES,None),
        'online_clone_rule_both_stores_absent_required')
    return {'rule_count':len(policy.NAMES),'both_stores_absent':True,
        'profiles_enabled':row['audit']['profiles_enabled'],'network_isolation_verified':False}


class OnlineAnalysisGate:
    """Already-authorized ordinary CONTROL online analysis, manager absent."""
    def __init__(self,native):self.native=native

    def check(self):
        review,review_sha=load(ONLINE_REVIEW)
        require(review.get('schema')=='lc-clone-online-analysis-review-v1'
            and review.get('reviewed')is True and review.get('profile')=='online-startup-analysis'
            and review.get('normal_online_analysis_authorized')is True
            and review.get('network_isolation_required')is False and review.get('analysis_only')is True
            and review.get('SDK_descendant_online_analysis_allowed')is True
            and review.get('no_concurrent_manager_launch')is True
            and review.get('stock_signature_verified')is True
            and review.get('allow_verified_stock_high_relaunch')is True
            and review.get('program')==EXE and review.get('program_sha256')==EXE_SHA
            and review.get('program_variant')=='CONTROL' and review.get('build')==list(BUILD)
            and review.get('job_active_process_limit')==16 and review.get('cleanup_scope')=='owned_job_members'
            and review.get('former_host')==FORMER_HOST and review.get('former_owner')==FORMER_OWNER,
            'explicit_authorized_online_CONTROL_review_required')
        require(admin_digest()==ONLINE_SOURCE and review.get('admin_source_sha256')==ONLINE_SOURCE,
            'current_3ce_online_analysis_source_required')
        require(review.get('observer_source_sha256')==observer_hashes(),'reviewed_current_observer_sources_required')
        policy=clone_policy();rows={};hashes={}
        for name in ONLINE_STATE_FILES:rows[name],hashes[name]=load(STATE/name)
        require(review.get('closed_state_sha256')==hashes,'reviewed_closed_state_bytes_required')
        closed_online_state(rows,policy)
        absent=[self.native.inactive_fixed_process(FORMER_HOST['pid'],FORMER_HOST['birth'],str(PYTHON)),
            self.native.inactive_fixed_process(FORMER_OWNER['pid'],FORMER_OWNER['birth'],POWERSHELL)]
        require(all(row.get('inactive')is True for row in absent),'former_manager_native_inactive_required')
        run=subprocess.run([str(PYTHON),'-I','-B',str(ADMIN/'entry.py'),'CloneInspect'],
            capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        require(run.returncode==0 and len(run.stdout)<=32768,'online_fresh_readonly_clone_audit_required')
        audit=online_audit_proof(json.loads(run.stdout.decode('utf-8-sig')),policy)
        require(admin_digest()==ONLINE_SOURCE and review.get('observer_source_sha256')==observer_hashes(),
            'online_sources_changed_during_audit')
        require(load(ONLINE_REVIEW)[1]==review_sha
            and {name:load(STATE/name)[1] for name in ONLINE_STATE_FILES}==hashes,
            'online_closed_state_or_review_changed_during_audit')
        require(all(self.native.inactive_fixed_process(row['pid'],row['birth'],image).get('inactive')is True
            for row,image in ((FORMER_HOST,str(PYTHON)),(FORMER_OWNER,POWERSHELL))),
            'former_manager_became_live_during_audit')
        self.native.online_stock_high_relaunch_authorized=True
        return {'verified':True,'condition':'AUTHORIZED_CONTROL_ONLINE_ANALYSIS',
            'analysis_only':True,'normal_online_analysis_authorized':True,'network_isolation_required':False,
            'network_isolation_verified':False,'whole_app_isolation_proven':False,'standalone_play_verified':False,
            'manager_present':False,'manager_ARMED':False,'former_manager_native':absent,
            'source_sha256':ONLINE_SOURCE,'review_sha256':review_sha,'closed_state_sha256':hashes,'native_audit':audit}


def config_preflight_proof(row,variant):
    require(variant in CONFIG_CANDIDATES,'fixed_A_or_B_config_variant_required')
    anchor='0ba7f4ff2c19fad5542f3724598dd380790df5e5d512922a60e3f89ade0655a6'
    require(row.get('schema')=='lc-startup-policy-trials-preflight-v1' and row.get('source_sha256')==EXE_SHA
        and row.get('source_size')==39144728 and row.get('original_plaintext_sha256')==anchor
        and row.get('build')=='26.09.29.2001' and row.get('source_unchanged_after')is True
        and row.get('actual_slot_swap_or_execution')is False and row.get('original_or_archive_or_C1_mutation')is False
        and row.get('fake_auth_ready_key_or_token')is False,'fixed_current_source_preflight_required')
    require(row.get('original_policy')=={'SystemManager.run-as-admin':True,'LauncherChecker.switch':True,
        'LauncherChecker.action':'suicide'}, 'source_admin_policy_true_required')
    trials=row.get('trials',[])
    require(type(trials)is list and len(trials)==2 and {trial.get('role') for trial in trials}=={'A','B'},
        'fixed_A_B_preflight_rows_required')
    trial=next(trial for trial in trials if trial['role']==('A' if variant=='admin-off' else 'B'))
    fields=['SystemManager.run-as-admin: true -> false']
    if variant=='admin-launcher-off':fields.append('LauncherChecker.switch: true -> false')
    checks={'semantic_exact_deepcompare','same_plaintext_length','recompressed_roundtrip','padded_payload_roundtrip',
        'payload_only_same_header_trailer','PE_headers_layout_dirs_length_same','certificate_table_bytes_same',
        'original_content_digest_matches','candidate_content_digest_mismatch','candidate_full_readback_hash'}
    require(trial.get('path')==str(CONFIG_CANDIDATES[variant]) and trial.get('sha256')==VARIANTS[variant][1]
        and trial.get('size')==39144728 and trial.get('source_sha256')==EXE_SHA
        and trial.get('original_plaintext_sha256')==anchor and trial.get('changed_semantic_fields')==fields
        and trial.get('changed_semantic_count')==len(fields) and trial.get('SystemManager_run_as_admin')is False
        and trial.get('LauncherChecker_switch')is (variant=='admin-off')
        and set(trial.get('checks',{}))==checks and all(value is True for value in trial['checks'].values())
        and trial.get('publisher_signature_valid')is False and trial.get('operational_adoption')is False
        and trial.get('actual_execution')is False and trial.get('no_fake_auth_ready_key_or_token')is True,
        'exact_candidate_roundtrip_semantics_and_signature_mismatch_required')
    return {'candidate_role':trial['role'],'changed_semantic_fields':fields,'roundtrip_checks_passed':10,
        'publisher_signature_valid':False,'configuration_consumed_at_runtime_proven':False}


def fixed_candidate_slot_proof(variant):
    require(variant in CONFIG_CANDIDATES,'fixed_candidate_slot_variant_required')
    for path in (CONFIG_CANDIDATES[variant],Path(EXE)):
        plain(path)
        require(path.stat().st_size==39144728 and hashlib.sha256(path.read_bytes()).hexdigest()==VARIANTS[variant][1],
            'exact_fixed_candidate_and_installed_slot_bytes_required')


class OnlineConfigAnalysisGate:
    """Unsigned exact A/B file-only config trial; all processes stay medium."""
    review_path=CONFIG_REVIEW
    preflight_path=CONFIG_PREFLIGHT
    review_schema='lc-clone-online-config-analysis-review-v1'
    candidate_paths=CONFIG_CANDIDATES
    preflight_proof=staticmethod(config_preflight_proof)
    slot_proof=staticmethod(fixed_candidate_slot_proof)
    def __init__(self,native,variant,public_review=False):
        require(variant in self.candidate_paths,'fixed_config_trial_variant_required')
        require(type(public_review)is bool and (not public_review or variant=='admin-launcher-off'),
            'public_review_B_only_required')
        self.native=native;self.variant=variant;self.role,self.sha=VARIANTS[variant];self.public_review=public_review

    def check(self):
        review,review_sha=load(self.review_path)
        require(review.get('schema')==self.review_schema and review.get('reviewed')is True
            and review.get('profile')=='online-config-analysis' and review.get('normal_online_analysis_authorized')is True
            and review.get('network_isolation_required')is False and review.get('analysis_only')is True
            and review.get('SDK_descendant_online_analysis_allowed')is True and review.get('no_concurrent_manager_launch')is True
            and review.get('candidate_code_reviewed')is True and review.get('roundtrip_preflight_verified')is True
            and review.get('stock_signature_verified')is False and review.get('publisher_signature_content_mismatch')is True
            and review.get('allow_verified_stock_high_relaunch')is False and review.get('operational_adoption')is False
            and review.get('program')==EXE and review.get('program_sha256')==self.sha
            and review.get('program_variant')==self.role and review.get('build')==list(BUILD)
            and review.get('candidate_path')==str(self.candidate_paths[self.variant])
            and review.get('job_active_process_limit')==16 and review.get('cleanup_scope')=='owned_job_members'
            and review.get('former_host')==FORMER_HOST and review.get('former_owner')==FORMER_OWNER,
            'explicit_unsigned_medium_only_config_trial_review_required')
        if self.public_review:
            require(review.get('public_UI_review_requested')is True and review.get('max_observation_seconds')==900,
                'explicit_public_UI_review_900_record_required')
        require(admin_digest()==ONLINE_SOURCE and review.get('admin_source_sha256')==ONLINE_SOURCE
            and review.get('observer_source_sha256')==observer_hashes(),'current_config_trial_sources_required')
        preflight,preflight_sha=load(self.preflight_path)
        require(review.get('candidate_preflight_sha256')==preflight_sha,'reviewed_fixed_candidate_preflight_bytes_required')
        proof=self.preflight_proof(preflight,self.variant)
        self.slot_proof(self.variant)
        policy=clone_policy();rows={};hashes={}
        for name in ONLINE_STATE_FILES:rows[name],hashes[name]=load(STATE/name)
        require(review.get('closed_state_sha256')==hashes,'reviewed_closed_config_state_bytes_required')
        closed_online_state(rows,policy)
        absent=[self.native.inactive_fixed_process(row['pid'],row['birth'],image)
            for row,image in ((FORMER_HOST,str(PYTHON)),(FORMER_OWNER,POWERSHELL))]
        require(all(row.get('inactive')is True for row in absent),'config_former_manager_native_inactive_required')
        # Admin14 ImagePin accepts only its original CONTROL/CANDIDATE family.
        # Inspect the fixed physical rule without inventing a successful A/B
        # CloneInspect wrapper or changing admin source/accepted image hashes.
        command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); & '"+str(ADMIN/'clone_firewall.ps1')+"' -Operation Inspect"
        run=subprocess.run([POWERSHELL,'-NoLogo','-NoProfile','-NonInteractive','-Command',command],
            capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        require(run.returncode==0 and len(run.stdout)<=32768,'config_fresh_readonly_physical_audit_required')
        audit=json.loads(run.stdout.decode('utf-8-sig'))
        require(policy.validate_audit(audit)==dict.fromkeys(policy.NAMES,None),'config_clone_rule_both_stores_absent_required')
        require(admin_digest()==ONLINE_SOURCE and review.get('observer_source_sha256')==observer_hashes()
            and load(self.review_path)[1]==review_sha and load(self.preflight_path)[1]==preflight_sha
            and {name:load(STATE/name)[1] for name in ONLINE_STATE_FILES}==hashes,
            'config_trial_sources_or_closed_proof_changed_during_audit')
        require(all(self.native.inactive_fixed_process(row['pid'],row['birth'],image).get('inactive')is True
            for row,image in ((FORMER_HOST,str(PYTHON)),(FORMER_OWNER,POWERSHELL))),
            'config_former_manager_became_live_during_audit')
        self.slot_proof(self.variant)
        self.native.online_stock_high_relaunch_authorized=False
        return {'verified':True,'condition':'AUTHORIZED_UNSIGNED_CONFIG_ONLINE_ANALYSIS','analysis_only':True,
            'network_isolation_required':False,'network_isolation_verified':False,'whole_app_isolation_proven':False,
            'standalone_play_verified':False,'manager_present':False,'manager_ARMED':False,
            'stock_signature_verified':False,'publisher_signature_content_mismatch':True,'operational_adoption':False,
            'high_descendants_allowed':False,'program_variant':self.role,'program_sha256':self.sha,
            'candidate_preflight_sha256':preflight_sha,'candidate_preflight':proof,'source_sha256':ONLINE_SOURCE,
            'review_sha256':review_sha,'closed_state_sha256':hashes,'former_manager_native':absent,
            'native_audit':{'interface':'literal_fixed_readonly_Inspect','both_stores_absent':True,
                'profiles_enabled':audit['profiles_enabled'],'mutation_performed':False},
            'admin_CloneInspect_A_B_supported':False}


def C_preflight_proof(row,variant):
    require(variant=='sdk-multiclient','fixed_C_sdk_multiclient_required')
    anchor='0ba7f4ff2c19fad5542f3724598dd380790df5e5d512922a60e3f89ade0655a6'
    require(row.get('schema')=='lc-sdk-multiclient-trial-preflight-v1' and row.get('source_sha256')==EXE_SHA
        and row.get('source_size')==39144728 and row.get('original_plaintext_sha256')==anchor
        and row.get('source_path')==str(ROOT/'work/config_startup_trial/control.snapshot.bin')
        and row.get('build')=='26.09.29.2001' and row.get('source_unchanged_after')is True
        and row.get('frozen_B_unchanged_after')is True and row.get('actual_slot_swap_or_execution')is False
        and row.get('original_or_archive_or_AB_mutation')is False and row.get('fake_auth_ready_key_or_token')is False,
        'fixed_CONTROL_C_preflight_and_B_unchanged_required')
    baseline=row.get('baseline_B',{})
    require(baseline.get('path')==str(CONFIG_CANDIDATES['admin-launcher-off'])
        and baseline.get('sha256')==VARIANTS['admin-launcher-off'][1]
        and baseline.get('policy')=={'SystemManager.run-as-admin':False,'LauncherChecker.switch':False,
            'SystemManager.enable-multi-client-mode':False},'fixed_B_comparison_baseline_required')
    trials=row.get('trials',[])
    require(type(trials)is list and len(trials)==1 and trials[0].get('role')=='C','one_fixed_C_row_required')
    trial=trials[0]
    fields=['SystemManager.run-as-admin: true -> false','LauncherChecker.switch: true -> false',
        'SystemManager.enable-multi-client-mode: false -> true']
    checks={'semantic_exact_deepcompare','same_plaintext_length','exact_B_plaintext_reproduction',
        'only_one_semantic_change_from_B','recompressed_roundtrip','padded_payload_roundtrip',
        'payload_only_same_header_trailer','PE_headers_layout_dirs_length_same','certificate_table_bytes_same',
        'original_content_digest_matches','candidate_content_digest_mismatch','candidate_full_readback_hash'}
    require(trial.get('path')==str(C_CANDIDATES[variant]) and trial.get('sha256')==VARIANTS[variant][1]
        and trial.get('size')==39144728 and trial.get('source_sha256')==EXE_SHA
        and trial.get('original_plaintext_sha256')==anchor and trial.get('changed_semantic_fields')==fields
        and trial.get('changed_semantic_count')==3 and trial.get('SystemManager_run_as_admin')is False
        and trial.get('LauncherChecker_switch')is False and trial.get('SystemManager_enable_multi_client_mode')is True
        and set(trial.get('checks',{}))==checks and all(value is True for value in trial['checks'].values())
        and trial.get('publisher_signature_valid')is False and trial.get('operational_adoption')is False
        and trial.get('actual_execution')is False and trial.get('no_fake_auth_ready_key_or_token')is True,
        'exact_C_three_fields_roundtrip_B_relation_and_signature_mismatch_required')
    return {'candidate_role':'C','changed_semantic_fields':fields,'roundtrip_checks_passed':12,
        'publisher_signature_valid':False,'configuration_consumed_at_runtime_proven':False}


def C_slot_proof(variant):
    require(variant=='sdk-multiclient','fixed_C_slot_variant_required')
    for path in (C_CANDIDATES[variant],Path(EXE)):
        plain(path)
        require(path.stat().st_size==39144728 and hashlib.sha256(path.read_bytes()).hexdigest()==VARIANTS[variant][1],
            'exact_fixed_C_candidate_and_installed_slot_bytes_required')


class OnlineCAnalysisGate(OnlineConfigAnalysisGate):
    """Separate C artifact/review family; A/B and B public-review stay fixed."""
    review_path=C_REVIEW
    preflight_path=C_PREFLIGHT
    review_schema='lc-clone-online-C-review-v1'
    candidate_paths=C_CANDIDATES
    preflight_proof=staticmethod(C_preflight_proof)
    slot_proof=staticmethod(C_slot_proof)

    def check(self):
        review,_=load(C_REVIEW)
        require(review.get('public_UI_review_requested')is False and review.get('max_observation_seconds')==120,
            'C_no_public_review_max120_record_required')
        proof=super().check()
        proof['condition']='AUTHORIZED_UNSIGNED_C_CONFIG_ONLINE_ANALYSIS'
        proof['admin_CloneInspect_C_supported']=False
        proof['public_review_allowed']=False
        return proof


def route_preflight_proof(row,variant):
    require(variant=='route-b','fixed_ROUTE_B_required')
    require(row.get('schema')=='lc-local-route-static-trial-v1' and row.get('status')=='REVIEW_ONLY_NOT_EXECUTED'
        and row.get('build')=='26.09.29.2001' and row.get('variant')=='ROUTE_B'
        and row.get('source_sha256')==EXE_SHA and row.get('B_sha256')==VARIANTS['admin-launcher-off'][1]
        and row.get('producer_sha256')==ROUTE_PRODUCER_SHA
        and row.get('candidate')=={'path':str(ROUTE_CANDIDATES[variant]),'size':39144728,'sha256':VARIANTS[variant][1]},
        'fixed_ROUTE_B_source_candidate_and_producer_required')
    checks={'seven_source_hashes_verified','seven_whole_candidate_records_roundtrip','code_only_host_and_port',
        'fixed_frame_header_lengths_trailer_layout_unchanged','all_other_records_code_and_raw_bytes_unchanged',
        'PE_headers_sections_directories_certificate_bytes_unchanged','original_publisher_content_digest_matches',
        'candidate_publisher_content_digest_mismatch','readback_hash_matches','original_and_B_unchanged'}
    require(set(row.get('checks',{}))==checks and all(v is True for v in row['checks'].values()),'route_ten_full_source_checks_required')
    frames=row.get('frames',[])
    require(type(frames)is list and len(frames)==7 and [f.get('number') for f in frames]==list(range(7))
        and all(f.get('candidate_sha256')==f.get('original_sha256') for f in frames if f['number']!=1)
        and frames[1].get('candidate_sha256')=='4d15d75a1b99e1430fc2fe0345b7a93324cac5256b0a9b281a7f2666e04f1545',
        'route_seven_records_only_code_record_changed_required')
    patch=row.get('code_patch',{})
    require(patch.get('host_code_RVA')==['0x32f3c4','0x32f3eb'] and patch.get('port_code_RVA')==['0x32f407','0x32f40b']
        and patch.get('host_input')=='127.0.0.1' and patch.get('host_port')==12000
        and patch.get('literal_NUL_exact')is True and patch.get('external_direct_incoming_branch_candidates')==0
        and patch.get('prolog_and_RDI_save_unchanged')is True
        and patch.get('inet_pton_call_failure_timeout_cipher_and_connect_suffix_unchanged')is True,
        'route_only_fixed_43_byte_ranges_localhost12000_required')
    require(row.get('configuration')=={'semantic_changes':2,'SystemManager.run-as-admin':False,'LauncherChecker.switch':False,
        'SystemManager.enable-multi-client-mode':False,'B_payload_byteexact':True,
        'B_plaintext_sha256':'2086de0cc0260f1c3fadbf9ced5ff7afde063881ffb6a096868e25c2b79951f5'},
        'route_exact_B_configuration_only_required')
    limits=row.get('limits',{})
    require(all(limits.get(k)is False for k in ('native_execution','network','SDK_auth_ready_patch','game_entry_proven',
        'first_socket_observed','resource_master_provider_available')),'route_no_fake_auth_ready_or_entry_claim_required')
    return {'candidate_role':'ROUTE_B','roundtrip_checks_passed':10,'whole_frames_verified':7,
        'code_patch_range_bytes':43,'route':{'ipv4':'127.0.0.1','port':12000},'configuration_semantic_changes':2,
        'B_payload_byteexact':True,'SDK_auth_ready_patch':False,'publisher_signature_valid':False,
        'runtime_loader_acceptance_proven':False,'first_socket_observed':False,'resource_master_provider_available':False}


def route_transaction_proof(document,provenance,review,provenance_sha):
    expected={'schema':'lc-fixed-config-trial-transactions-v1','trial_family':ROUTE_FAMILY,
        'slot_file_id':review.get('slot_file_id'),'control_sha256':EXE_SHA,
        'candidate_sha256':{'PrepareRouteB':VARIANTS['route-b'][1]},'length':39144728,
        'admin_source_sha256':ONLINE_SOURCE,'closed_state_sha256':review.get('closed_state_sha256'),
        'snapshot_provenance_sha256':provenance_sha,'preflight_sha256':ROUTE_PREFLIGHT_SHA,'producer_sha256':ROUTE_PRODUCER_SHA}
    require(type(document)is dict and set(document)==set(expected)|{'events'}
        and all(document[k]==v for k,v in expected.items()),'route_new_slot_history_binding_required')
    require(type(review.get('slot_file_id'))is str and len(review['slot_file_id'])==25 and review['slot_file_id'][8]==':'
        and all(c in '0123456789abcdef' for c in review['slot_file_id'].replace(':',''))
        and review['slot_file_id'].count(':')==1,'route_native_file_id_required')
    require(type(provenance)is dict and set(provenance)=={'schema','trial_family','program','slot_file_id','snapshot_file_id',
        'length','control_sha256','admin_source_sha256','closed_state_sha256','preflight_sha256','producer_sha256'}
        and provenance.get('schema')=='lc-fixed-config-trial-control-snapshot-v1' and provenance.get('trial_family')==ROUTE_FAMILY
        and provenance.get('program')==EXE and provenance.get('slot_file_id')==review['slot_file_id']
        and type(provenance.get('snapshot_file_id'))is str and provenance.get('length')==39144728
        and provenance.get('control_sha256')==EXE_SHA and provenance.get('admin_source_sha256')==ONLINE_SOURCE
        and provenance.get('preflight_sha256')==ROUTE_PREFLIGHT_SHA and provenance.get('producer_sha256')==ROUTE_PRODUCER_SHA
        and provenance.get('closed_state_sha256')==review.get('closed_state_sha256'),'route_new_snapshot_provenance_required')
    events=document['events']; require(type(events)is list and 2<=len(events)<=64,'route_history_bound')
    previous='0'*64; prior=None
    for index,event in enumerate(events):
        require(type(event)is dict and set(event)=={'index','action','phase','before','after','previous_sha256','sha256'}
            and event['index']==index and event['action']in ('PrepareRouteB','RestoreControl')
            and event['phase']in ('INTENT','COMPLETE') and event['previous_sha256']==previous,'route_event_chain_schema')
        clean={k:v for k,v in event.items() if k!='sha256'}
        encoded=(json.dumps(clean,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
        require(event['sha256']==hashlib.sha256(encoded).hexdigest(),'route_event_hash')
        target=EXE_SHA if event['action']=='RestoreControl' else VARIANTS['route-b'][1]
        require(event['after']==target,'route_target_not_fixed')
        if event['phase']=='INTENT':
            require(prior is None or prior['phase']=='COMPLETE','route_unfinished_intent')
            if event['action']=='PrepareRouteB':
                require(event['before']==EXE_SHA and (prior is None or prior['after']==EXE_SHA),'route_prepare_requires_control')
            else:
                require(prior is not None and prior['action']=='PrepareRouteB' and event['before']==VARIANTS['route-b'][1],
                    'route_restore_requires_own_prepare')
        else:
            require(prior is not None and prior['phase']=='INTENT'
                and all(event[k]==prior[k] for k in ('action','before','after')),'route_complete_without_intent')
        prior=event;previous=event['sha256']
    require(prior['phase']=='COMPLETE' and prior['action']=='PrepareRouteB' and prior['after']==VARIANTS['route-b'][1],
        'route_current_prepare_completion_required')
    return {'trial_family':ROUTE_FAMILY,'active_action':'PrepareRouteB','events':len(events),
        'slot_file_id':review['slot_file_id'],'installed_sha256':VARIANTS['route-b'][1],'completion_sha256':prior['sha256']}


def route_native_file_id(path):
    require(path in (Path(EXE),ROUTE_SNAPSHOT,MOUNT_SNAPSHOT,CURRENT_SNAPSHOT),'fixed_route_identity_paths_required');plain(path)
    k=C.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=(W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,C.c_void_p);k.CreateFileW.restype=W.HANDLE
    k.GetFileInformationByHandle.argtypes=(W.HANDLE,C.c_void_p)
    k.GetFinalPathNameByHandleW.argtypes=(W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD)
    k.CloseHandle.argtypes=(W.HANDLE,)
    handle=k.CreateFileW(str(path),0x80000000,1,None,3,0x80,None)
    require(handle!=C.c_void_p(-1).value,'route_readonly_native_file_handle_required')
    try:
        info=C.create_string_buffer(52);require(k.GetFileInformationByHandle(handle,info),'route_native_file_information_unknown')
        require(int.from_bytes(info.raw[28:32],'little')!=0 and int.from_bytes(info.raw[40:44],'little')==1
            and not int.from_bytes(info.raw[:4],'little')&0x400,'route_native_file_reparse_or_hardlink_refused')
        final=C.create_unicode_buffer(32768);length=k.GetFinalPathNameByHandleW(handle,final,32768,0)
        require(0<length<32768 and final.value.removeprefix('\\\\?\\').casefold()==str(path).casefold(),
            'route_native_final_path_mismatch')
        return info.raw[28:32].hex()+':'+info.raw[44:52].hex()
    finally:k.CloseHandle(handle)


def route_slot_proof(variant):
    require(variant=='route-b','fixed_route_slot_variant_required')
    review,_=load(ROUTE_REVIEW);document,history_sha=load(ROUTE_TRANSACTIONS);provenance,provenance_sha=load(ROUTE_PROVENANCE)
    require(review.get('slot_trial_family')==ROUTE_FAMILY and review.get('slot_transaction_sha256')==history_sha
        and review.get('slot_provenance_sha256')==provenance_sha,'reviewed_new_route_slot_raw_bytes_required')
    proof=route_transaction_proof(document,provenance,review,provenance_sha)
    for path,expected in ((ROUTE_CANDIDATES[variant],VARIANTS[variant][1]),(Path(EXE),VARIANTS[variant][1]),(ROUTE_SNAPSHOT,EXE_SHA)):
        plain(path); require(path.stat().st_size==39144728 and hashlib.sha256(path.read_bytes()).hexdigest()==expected,
            'exact_route_candidate_installed_and_own_snapshot_required')
    require(route_native_file_id(Path(EXE))==review['slot_file_id']
        and route_native_file_id(ROUTE_SNAPSHOT)==provenance['snapshot_file_id'],'route_same_native_slot_snapshot_file_id_required')
    require(load(ROUTE_TRANSACTIONS)[1]==history_sha and load(ROUTE_PROVENANCE)[1]==provenance_sha,'route_history_changed_during_slot_read')
    return proof


class OnlineRouteBAnalysisGate(OnlineConfigAnalysisGate):
    review_path=ROUTE_REVIEW
    preflight_path=ROUTE_PREFLIGHT
    review_schema='lc-clone-online-route-B-review-v1'
    candidate_paths=ROUTE_CANDIDATES
    preflight_proof=staticmethod(route_preflight_proof)
    slot_proof=staticmethod(route_slot_proof)

    def check(self):
        review,review_sha=load(ROUTE_REVIEW)
        require(review.get('public_UI_review_requested')is False and review.get('max_observation_seconds')==120
            and review.get('route_candidate_reviewed')is True and review.get('whole_app_isolation_proven')is False
            and review.get('SDK_auth_ready_patch')is False and review.get('route')=={'ipv4':'127.0.0.1','port':12000}
            and review.get('candidate_preflight_sha256')==ROUTE_PREFLIGHT_SHA
            and review.get('candidate_producer_sha256')==ROUTE_PRODUCER_SHA,'route_only_review_max120_and_no_auth_patch_required')
        plain(ROUTE_PRODUCER);require(hashlib.sha256(ROUTE_PRODUCER.read_bytes()).hexdigest()==ROUTE_PRODUCER_SHA
            and load(ROUTE_PREFLIGHT)[1]==ROUTE_PREFLIGHT_SHA,'route_frozen_producer_and_preflight_required')
        proof=super().check()
        require(load(ROUTE_REVIEW)[1]==review_sha and load(ROUTE_PREFLIGHT)[1]==ROUTE_PREFLIGHT_SHA
            and hashlib.sha256(ROUTE_PRODUCER.read_bytes()).hexdigest()==ROUTE_PRODUCER_SHA,'route_static_evidence_changed_during_audit')
        proof.update({'condition':'AUTHORIZED_UNSIGNED_ROUTE_B_ONLINE_ANALYSIS','public_review_allowed':False,
            'route':{'ipv4':'127.0.0.1','port':12000},'SDK_auth_ready_patch':False,'admin_CloneInspect_ROUTE_B_supported':False})
        return proof


def mount_slot_module(review,scope=None):
    scope=scope or RootMountAnalysisGate
    names=('slot.py','tests.py')
    require(review.get('slot_source_sha256')=={name:hashlib.sha256((scope.slot_tool/name).read_bytes()).hexdigest() for name in names},
        'reviewed_fixed_mount_slot_sources_required')
    spec=importlib.util.spec_from_file_location('_observer_fixed_'+scope.profile_name,scope.slot_tool/'slot.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(module.CANDIDATES=={scope.prepare_action:(MOUNT_CANDIDATE,VARIANTS[scope.variant_name][1])}
        and module.SOURCE_SHA==ONLINE_SOURCE and module.PREFLIGHT_SHA==MOUNT_PREFLIGHT_SHA
        and module.PRODUCER_SHA==MOUNT_PRODUCER_SHA,'fixed_mount_slot_role_family_required')
    manifest,_=load(scope.slot_tool/'manifest.json')
    require(manifest==module.expected_manifest()
        and load(scope.slot_tool/'manifest.json')[1]==review.get('slot_manifest_sha256')
        and load(scope.slot_tool/'profile.json')[1]==review.get('slot_profile_sha256'),'fixed_mount_manifest_profile_required')
    require(module.WORK==scope.slot_work and module.BACKUP==scope.slot_snapshot,'fixed_mount_slot_work_agreement_required')
    return module


def mount_preflight_proof(module,row):
    module.validate_route_preflight(row)
    require(row.get('producer_sha256')==MOUNT_PRODUCER_SHA and row.get('CONTROL_sha256')==EXE_SHA
        and row.get('ROUTE_B_sha256')==VARIANTS['route-b'][1], 'mount_source_control_route_parent_required')
    return {'role':'ROOT_MOUNT_ROUTE_B','six_fixed_mount_spans':True,'route':{'ipv4':'127.0.0.1','port':12000},
        'B_configuration_preserved':True,'SDK_auth_ready_patch':False,'publisher_signature_content_mismatch':True}


def mount_slot_proof(module,review,scope=None):
    scope=scope or RootMountAnalysisGate
    document,history_sha=load(scope.slot_work/'transactions.json')
    provenance,provenance_sha=load(scope.slot_work/'control.provenance.json')
    require(review.get('slot_trial_family')==scope.family_name and review.get('slot_transaction_sha256')==history_sha
        and review.get('slot_provenance_sha256')==provenance_sha,'mount_slot_fresh_raw_proof_required')
    file_id=review.get('slot_file_id')
    require(type(file_id)is str and len(file_id)==25 and file_id[8]==':'
        and all(c in '0123456789abcdef' for c in file_id.replace(':','')),'mount_native_file_id_required')
    expected={'schema':'lc-fixed-config-trial-control-snapshot-v1','trial_family':scope.family_name,'program':EXE,
        'slot_file_id':file_id,'snapshot_file_id':provenance.get('snapshot_file_id'),'length':39144728,
        'control_sha256':EXE_SHA,'admin_source_sha256':ONLINE_SOURCE,'closed_state_sha256':module.CLOSED_HASHES,
        'preflight_sha256':MOUNT_PREFLIGHT_SHA,'producer_sha256':MOUNT_PRODUCER_SHA}
    require(provenance==expected and type(provenance['snapshot_file_id'])is str,'mount_exact_provenance_required')
    backend=SimpleNamespace(slot=SimpleNamespace(file_id=file_id),control_sha=EXE_SHA,size=39144728,
        candidate_shas={scope.prepare_action:VARIANTS[scope.variant_name][1]},provenance_sha=provenance_sha)
    last=module.validate_proof(document,backend)
    require(last['phase']=='COMPLETE' and last['action']==scope.prepare_action
        and last['after']==VARIANTS[scope.variant_name][1],'mount_active_completed_prepare_required')
    for path,expected_sha in ((MOUNT_CANDIDATE,VARIANTS[scope.variant_name][1]),
        (Path(EXE),VARIANTS[scope.variant_name][1]),(scope.slot_snapshot,EXE_SHA)):
        plain(path);require(path.stat().st_size==39144728 and hashlib.sha256(path.read_bytes()).hexdigest()==expected_sha,
            'mount_exact_candidate_slot_control_snapshot_required')
    require(route_native_file_id(Path(EXE))==file_id
        and route_native_file_id(scope.slot_snapshot)==provenance['snapshot_file_id'],'mount_native_slot_snapshot_identity_required')
    return {'active_action':last['action'],'completion_sha256':last['sha256'],'slot_file_id':file_id}


class RootMountAnalysisGate:
    """Separate current closed-family binding; existing profile contracts stay fixed."""
    profile_name='root-mount-analysis';variant_name='root-mount-route-b';review_schema='lc-clone-root-mount-review-v1'
    review_path=MOUNT_REVIEW;slot_tool=MOUNT_TOOL;slot_work=MOUNT_WORK;slot_snapshot=MOUNT_SNAPSHOT
    prepare_action='PrepareRootMount';family_name=MOUNT_FAMILY
    def __init__(self,native):self.native=native;self.pinned=False;self.child_created=False
    def owned_child_created(self,identity):
        require(identity.get('image')==EXE and identity.get('elevated')is False,'mount_owned_medium_child_required')
        self.child_created=True
    def check(self):
        review,review_sha=load(self.review_path)
        fixed={'schema':self.review_schema,'reviewed':True,'profile':self.profile_name,
            'normal_online_analysis_authorized':True,'analysis_only':True,'network_isolation_required':False,
            'whole_app_isolation_proven':False,'program':EXE,'program_variant':VARIANTS[self.variant_name][0],
            'program_sha256':VARIANTS[self.variant_name][1],'build':list(BUILD),'candidate_path':str(MOUNT_CANDIDATE),
            'candidate_code_reviewed':True,'roundtrip_preflight_verified':True,'stock_signature_verified':False,
            'publisher_signature_content_mismatch':True,'operational_adoption':False,'SDK_auth_ready_patch':False,
            'allow_verified_stock_high_relaunch':False,'job_active_process_limit':16,'cleanup_scope':'owned_job_members',
            'public_UI_review_requested':False,'max_observation_seconds':120,'no_concurrent_manager_launch':True,
            'candidate_preflight_sha256':MOUNT_PREFLIGHT_SHA,'candidate_producer_sha256':MOUNT_PRODUCER_SHA,
            'admin_source_sha256':ONLINE_SOURCE,'observer_source_sha256':observer_hashes()}
        require(all(type(review.get(k))is type(v) and review.get(k)==v for k,v in fixed.items()),'explicit_fixed_root_mount_review_required')
        require(type(review.get('require_PURPLE_absent'))is bool,'explicit_mount_cold_or_warm_scope_required')
        require(admin_digest()==ONLINE_SOURCE,'mount_admin_source_required')
        module=mount_slot_module(review,self)
        preflight,preflight_sha=load(MOUNT_PREFLIGHT)
        require(preflight_sha==MOUNT_PREFLIGHT_SHA and hashlib.sha256(MOUNT_PRODUCER.read_bytes()).hexdigest()==MOUNT_PRODUCER_SHA,
            'mount_producer_preflight_raw_pins_required')
        proof=mount_preflight_proof(module,preflight)
        rows={};hashes={}
        for name in module.CLOSED_HASHES:
            path=module.NORMAL_STATE/'status.json' if name=='normal-status.json' else STATE/name
            rows[name],hashes[name]=load(path)
        require(hashes==module.CLOSED_HASHES and review.get('closed_state_sha256')==hashes,'mount_today_closed_six_raw_hashes_required')
        module.validate_closed_rows(rows)
        identities=((module.FORMER_HOST,str(PYTHON)),(module.LEGACY_HOST,str(PYTHON)),
            (module.NORMAL_HOST,str(PYTHON)),(module.NORMAL_OWNER,POWERSHELL),(module.FORMER_OWNER,POWERSHELL))
        require(all(self.native.inactive_fixed_process(x['pid'],x['birth'],image).get('inactive')is True for x,image in identities),
            'mount_all_fixed_previous_owners_inactive_required')
        inventory=self.native.inventory()
        require(inventory['lc_count']==(1 if self.child_created else 0),'mount_no_foreign_LC_required')
        cold_processes=inventory.get('purple_apps') if self.profile_name=='current-resource-analysis' else inventory.get('purple')
        require(not review['require_PURPLE_absent'] or cold_processes==[],'mount_cold_trial_requires_PURPLE_absent')
        slot=mount_slot_proof(module,review,self)
        raw=(module.PROVIDER_META).read_bytes();require(len(raw)<=1048576,'mount_fixed_asset_catalog_bound')
        assets=module.fixed_assets(raw)
        require(len(assets)==67 and len({a['path'] for a in assets})==67,'mount_fixed_67_unique_assets_required')
        asset_paths=[]
        for asset in assets:
            path=Path(CLONE)/asset['path'];plain(path)
            require(path.stat().st_size==asset['size'] and hashlib.sha256(path.read_bytes()).hexdigest()==asset['sha256'],
                'mount_fixed_materialized_asset_hash_required')
            asset_paths.append(path)
        state_paths=[]
        state_review=review.get('public_state_diagnostic',{'enabled':False})
        require(type(state_review)is dict and type(state_review.get('enabled'))is bool,'explicit_mount_public_state_opt_in_required')
        if state_review['enabled']:
            state_names=('__init__.py','backend.py','sampler.py','tests.py')
            require(state_review.get('source_sha256')=={n:hashlib.sha256((MOUNT_STATE_TOOL/n).read_bytes()).hexdigest() for n in state_names}
                and state_review.get('contract_sha256')==hashlib.sha256((MOUNT_STATE_TOOL/'source-contract.json').read_bytes()).hexdigest(),
                'mount_public_state_sources_before_import_required')
            if not getattr(self,'state_pinned',False):
                self.native.pin_evidence([MOUNT_STATE_TOOL/n for n in state_names]+[MOUNT_STATE_TOOL/'source-contract.json',Path(CLONE)/'ncplatformsdk-cpp.dll'])
                self.state_pinned=True
            spec=importlib.util.spec_from_file_location('_fixed_root_mount_public_state',MOUNT_STATE_TOOL/'__init__.py',
                submodule_search_locations=[str(MOUNT_STATE_TOOL)])
            states=importlib.util.module_from_spec(spec);sys.modules[spec.name]=states;spec.loader.exec_module(states)
            state_contract,state_paths=states.approved(state_review)
            self.native.root_mount_public_state_factory=lambda owner,child:states.Reader(owner,child,state_contract)
        else:
            require(state_review=={'enabled':False},'disabled_mount_memory_has_no_other_fields')
            self.native.root_mount_public_state_factory=None
        if not self.pinned:
            paths=[HERE/name for name in OBSERVER_SOURCES]+[self.slot_tool/name for name in ('slot.py','tests.py','manifest.json','profile.json')]
            paths += [self.review_path,MOUNT_PREFLIGHT,MOUNT_PRODUCER,MOUNT_CANDIDATE,self.slot_snapshot,
                self.slot_work/'transactions.json',self.slot_work/'control.provenance.json',module.PROVIDER_META]+asset_paths
            paths += [module.NORMAL_STATE/'status.json' if name=='normal-status.json' else STATE/name for name in hashes]
            paths += [ADMIN/name for name in module.SOURCES]
            paths += state_paths
            self.native.pin_evidence(paths);self.pinned=True
            # Revalidate all fixed evidence after pins close the open/hash boundary.
            return self.check()
        policy=clone_policy()
        command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); & '"+str(ADMIN/'clone_firewall.ps1')+"' -Operation Inspect"
        run=subprocess.run([POWERSHELL,'-NoLogo','-NoProfile','-NonInteractive','-Command',command],
            capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        require(run.returncode==0 and len(run.stdout)<=32768,'mount_fresh_readonly_audit_required')
        audit=json.loads(run.stdout.decode('utf-8-sig'))
        require(policy.validate_audit(audit)==dict.fromkeys(policy.NAMES,None),'mount_clone_rule_both_stores_absent_required')
        require(load(self.review_path)[1]==review_sha and observer_hashes()==review['observer_source_sha256']
            and admin_digest()==ONLINE_SOURCE,'mount_sources_changed_during_audit')
        inventory=self.native.inventory()
        require(inventory['lc_count']==(1 if self.child_created else 0),'mount_foreign_LC_during_audit')
        cold_processes=inventory.get('purple_apps') if self.profile_name=='current-resource-analysis' else inventory.get('purple')
        require(not review['require_PURPLE_absent'] or cold_processes==[],'mount_PURPLE_became_present_during_audit')
        self.native.online_stock_high_relaunch_authorized=False
        return {'verified':True,'condition':'ROOT_MOUNT_ROUTE_B_SOURCE_BOUND_ANALYSIS','analysis_only':True,
            'network_isolation_verified':False,'whole_app_isolation_proven':False,'standalone_play_verified':False,
            'manager_present':False,'manager_ARMED':False,'high_descendants_allowed':False,'slot':slot,'preflight':proof,
            'closed_state_sha256':hashes,'materialized_fixed_assets':len(assets),'public_review_allowed':False,
            'public_state_diagnostic_enabled':state_review['enabled'],
            'PURPLE_absent':inventory.get('purple')==[],'PURPLE_app_absent':inventory.get('purple_apps')==[],
            'PURPLE_companions_observed':inventory.get('purple_companions',[]),'whole_official_runtime_absent':False,
            'cold_PURPLE_independence_verified':False,'memory_state_sampler_enabled':state_review['enabled']}


class CurrentResourceAnalysisGate(RootMountAnalysisGate):
    profile_name='current-resource-analysis';variant_name='current-resource-root-mount'
    review_schema='lc-clone-current-resource-review-v1';review_path=CURRENT_REVIEW
    slot_tool=CURRENT_TOOL;slot_work=CURRENT_WORK;slot_snapshot=CURRENT_SNAPSHOT
    prepare_action='PrepareCurrentResource';family_name=CURRENT_FAMILY


class CodecDiagnosticGate:
    """One frozen known decoder fault; physical rule proof, never fake ARMED."""
    def __init__(self,native):
        self.native=native;self.child_created=False

    def owned_child_created(self,identity):
        require(identity.get('image')==EXE and identity.get('elevated')is False,
            'codec_diagnostic_own_control_child_required')
        self.child_created=True

    def check(self):
        review,_=load(CODEC_REVIEW)
        require(review.get('schema')=='lc-clone-codec-diagnostic-review-v1'
            and review.get('reviewed')is True and review.get('no_admin_repair_during_observation')is True
            and review.get('program')==EXE and review.get('program_sha256')==EXE_SHA
            and review.get('program_variant')=='CONTROL' and review.get('admin_source_sha256')==CODEC_SOURCE
            and review.get('producer')==CODEC_PRODUCER and review.get('failed_arm_request_id')==FAILED_ARM,
            'frozen_control_codec_review_required')
        require(admin_digest()==CODEC_SOURCE,'frozen_f06_source_required')
        result,result_sha=load(STATE/'results'/(FAILED_ARM+'.json'))
        request,_=load(STATE/'commands'/(FAILED_ARM+'.json'))
        session,_=load(STATE/'session.json')
        require(review.get('failed_arm_result_sha256')==result_sha
            and request.get('schema')=='lc-fixed-command-v1' and request.get('action')=='ArmCloneIsolation'
            and request.get('id')==FAILED_ARM and request.get('source_sha256')==CODEC_SOURCE
            and request.get('nonce')==session.get('nonce')
            and (session.get('pid'),session.get('birth'))==(CODEC_PRODUCER['pid'],CODEC_PRODUCER['birth'])
            and session.get('source_sha256')==CODEC_SOURCE,'original_failed_arm_current_epoch_required')
        nonce_sha=hashlib.sha256(bytes.fromhex(session['nonce'])).hexdigest()
        old=result.get('runtime',{});old_clone=old.get('clone_isolation',{})
        require(result.get('status')=='FAILED' and result.get('pid')==CODEC_PRODUCER['pid']
            and result.get('birth')==CODEC_PRODUCER['birth'] and result.get('source_sha256')==CODEC_SOURCE
            and result.get('nonce_sha256')==nonce_sha and old.get('phase')=='RECOVERY_REQUIRED'
            and old.get('error')=='UnicodeDecodeError' and old.get('closed')is False
            and old_clone.get('phase')=='CLEANUP_PENDING' and old_clone.get('error')=='ArmFailed'
            and old_clone.get('verified')is False and old_clone.get('program')==EXE
            and old_clone.get('program_sha256')==EXE_SHA and old_clone.get('program_variant')=='CONTROL',
            'specific_original_failed_arm_proof_required')
        status,_=load(STATE/'status.json');state=status.get('clone_isolation',{})
        known_fault=(status.get('error')=='UnicodeDecodeError' and state.get('error')=='ArmFailed')
        known_hold=(self.child_created and status.get('error')=='ValueError' and state.get('error')=='CloneStillLive')
        require(status.get('schema')=='lc-fixed-runtime-status-v1' and status.get('phase')=='RECOVERY_REQUIRED'
            and status.get('closed')is False and status.get('status_error')is None
            and status.get('source_sha256')==CODEC_SOURCE and status.get('pid')==CODEC_PRODUCER['pid']
            and status.get('birth')==CODEC_PRODUCER['birth'] and status.get('nonce_sha256')==nonce_sha
            and state.get('schema')=='lc-fixed-clone-status-v1' and state.get('phase')=='CLEANUP_PENDING'
            and state.get('verified')is False and state.get('program')==EXE
            and state.get('program_sha256')==EXE_SHA and state.get('program_variant')=='CONTROL'
            and (known_fault or known_hold),'known_codec_fault_or_own_clone_hold_required')
        producer=self.native.producer(CODEC_PRODUCER['pid'],CODEC_PRODUCER['birth'],str(PYTHON))
        policy=clone_policy();cached,cached_sha=load(PHYSICAL_AUDIT)
        require(review.get('physical_audit_sha256')==cached_sha
            and policy.validate_audit(cached)==dict.fromkeys(policy.NAMES,True)
            and cached['profiles_enabled']is True,'bound_physical_gate_audit_required')
        # Literal read-only pinned script; set UTF8 in this ordinary child only.
        # No operation selector from input, no normal-source patch or RPC.
        command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); & '"+str(ADMIN/'clone_firewall.ps1')+"' -Operation Inspect"
        run=subprocess.run([r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
            '-NoLogo','-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=60,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        require(run.returncode==0 and len(run.stdout)<=32768,'forced_UTF8_readonly_physical_audit_required')
        fresh=json.loads(run.stdout.decode('utf-8-sig'))
        require(policy.validate_audit(fresh)==dict.fromkeys(policy.NAMES,True)
            and fresh['profiles_enabled']is True and tuple(state.get('rules',[]))==tuple(policy.NAMES),
            'fresh_physical_gate_fullscope_required')
        return {'condition':'RULE_VERIFIED_HOST_CODEC_FAULT','physical_rules_verified':True,
            'manager_operation_succeeded':False,'manager_ARMED':False,'manager_error':status['error'],
            'manager_clone_error':state['error'],'program_variant':'CONTROL','program_sha256':EXE_SHA,
            'producer':producer,'source_sha256':CODEC_SOURCE,'failed_arm_request_id':FAILED_ARM,
            'failed_arm_result_sha256':result_sha,'physical_audit_sha256':cached_sha,
            'fresh_physical_audit_sha256':hashlib.sha256(run.stdout).hexdigest(),
            'whole_app_isolation_proven':False,'encoding_repair_concurrent':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true')
    parser.add_argument('--mode',choices=('normal','codec-diagnostic'),default='normal')
    parser.add_argument('--seconds',type=int)
    parser.add_argument('--public-review',action='store_true')
    parser.add_argument('--profile',choices=tuple(PROFILES),default='single')
    parser.add_argument('--variant',choices=tuple(VARIANTS),default='control');args=parser.parse_args()
    require(Path(__file__).resolve()==HERE/'observer.py','fixed_observer_location_required')
    if args.public_review:
        require(args.profile=='online-config-analysis' and args.variant=='admin-launcher-off' and args.mode=='normal'
            and args.seconds is None,'public_review_B_normal_only_no_seconds_override')
        args.seconds=900
    else:
        args.seconds=(120 if args.profile in ('root-mount-analysis','current-resource-analysis') else 25) if args.seconds is None else args.seconds
        require(20<=args.seconds<=120,'observation_bound_20_to_120_seconds')
    require(args.profile not in ('root-mount-analysis','current-resource-analysis') or args.seconds==120,'fixed_root_mount_120_seconds_required')
    require(args.mode!='codec-diagnostic' or args.variant=='control','codec_diagnostic_CONTROL_only')
    require((args.profile=='online-config-analysis' and args.variant in (*CONFIG_CANDIDATES,*C_CANDIDATES,*ROUTE_CANDIDATES) and args.mode=='normal')
        or (args.profile=='root-mount-analysis' and args.variant=='root-mount-route-b' and args.mode=='normal')
        or (args.profile=='current-resource-analysis' and args.variant=='current-resource-root-mount' and args.mode=='normal')
        or (args.profile not in ('online-config-analysis','root-mount-analysis','current-resource-analysis') and args.variant in ('control','candidate')
            and (PROFILES[args.profile]!=16 or (args.variant=='control' and args.mode=='normal'))),
        'startup_analysis_normal_CONTROL_only')
    if not args.run:
        role,expected_sha=VARIANTS[args.variant]
        print(json.dumps({'status':'PLAN','program':EXE,'program_sha256':expected_sha,'program_variant':role,
            'mode':args.mode,
            'profile':args.profile,'analysis_only':PROFILES[args.profile]==16,
            'public_UI_review_requested':args.public_review,
            'publisher_signature_content_mismatch':args.variant!='control','operational_adoption':False,
            'working_directory':CLONE,'arguments':[],'controller':'ordinary_hidden_console',
            'public_game_window':'visible only for first-gate launcher notice','observer_seconds':args.seconds,
            'suspended_job_attach_before_resume':True,'active_process_limit':PROFILES[args.profile],'breakaway':False,
            'actual_game_started':False,'root_review_path':str(CURRENT_REVIEW if args.profile=='current-resource-analysis' else
                MOUNT_REVIEW if args.profile=='root-mount-analysis' else
                ROUTE_REVIEW if args.variant in ROUTE_CANDIDATES else
                C_REVIEW if args.variant in C_CANDIDATES else
                CONFIG_REVIEW if args.profile=='online-config-analysis' else
                ONLINE_REVIEW if args.profile=='online-startup-analysis' else REVIEW),
            'network_isolation_required':args.profile not in ('online-startup-analysis','online-config-analysis','root-mount-analysis','current-resource-analysis'),
            'actual_gate_receipt_required':args.profile not in ('online-startup-analysis','online-config-analysis','root-mount-analysis','current-resource-analysis'),
            'screenshot_available':False},ensure_ascii=False))
        return 0
    native=Native(args.profile)
    gate=(CurrentResourceAnalysisGate(native) if args.profile=='current-resource-analysis' else
        RootMountAnalysisGate(native) if args.profile=='root-mount-analysis' else
        OnlineRouteBAnalysisGate(native,args.variant,args.public_review) if args.variant in ROUTE_CANDIDATES else
        OnlineCAnalysisGate(native,args.variant,args.public_review) if args.variant in C_CANDIDATES else
        OnlineConfigAnalysisGate(native,args.variant,args.public_review) if args.profile=='online-config-analysis' else
        OnlineAnalysisGate(native) if args.profile=='online-startup-analysis' else
        CodecDiagnosticGate(native) if args.mode=='codec-diagnostic' else Gate(native,args.variant,args.profile))
    report=observe(native,gate,seconds=args.seconds,variant=args.variant,profile=args.profile,public_review=args.public_review)
    report['mode']=args.mode
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    output_dir=ROOT/'work/current_resource_trial/observer-proof' if args.profile=='current-resource-analysis' else ROOT/'work/root_mount_resume/observer-proof' if args.profile=='root-mount-analysis' else HERE
    output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/'last-run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 현재 원본 복사본 첫 기동 관찰','',
        f"- launched: {report['launched']}",f"- stop reason: {report['stop_reason']}",
        f"- program variant: {report['program_variant']}",
        f"- publisher signature content mismatch: {report['publisher_signature_content_mismatch']}",
        '- operational adoption: False',
        f"- natural observed exit: {report['observed_exit']}",f"- forced exit: {report['forced_exit']}",
        f"- exit code: {report.get('exit_code')}",'',
        ('서명 content mismatch가 있는 고정 설정 후보의 온라인 분석이다. medium만 허용하며 configuration 소비·네트워크 격리·단독 게임 진입은 입증하지 않았다.'
            if args.profile in ('online-config-analysis','root-mount-analysis','current-resource-analysis') else
            '승인된 정상 CONTROL 온라인 분석이다. 관리자 부재·clone 차단 규칙 부재를 확인하며 네트워크 격리·단독 게임 진입은 입증하지 않았다.'
            if args.profile in ('online-startup-analysis','online-config-analysis') else '고정 clone의 직접 네트워크 차단만 검사한다. 기존 PURPLE/broker 영향과 앱 전체 격리는 입증하지 않았다.'),
        ('startup-analysis: Job active16/noBreakaway의 소유 SDK descendants 공식 분석만 허용하며 앱 전체 격리·offline play는 증명하지 않는다.'
            if PROFILES[args.profile]==16 else '활성 프로세스 1개 Job은 SDK child 생성 자체를 제한하므로 정상 온라인 초기화와 동일한 실험 조건이 아니다.'),
        '전역 화면·개인정보·전체 argv·메모리를 수집하지 않았다. UI 도구 초기화 실패 환경에서 자기 창의 bounded public text만 사용했다.']
    if args.mode=='codec-diagnostic':
        lines.extend(['','condition: RULE_VERIFIED_HOST_CODEC_FAULT',
            'manager operation succeeded: False; manager ARMED: False',
            'CONTROL의 현재 물리 규칙만 검증했다. 관리자 codec 복구와 gate cleanup은 여전히 별도 미완료다.'])
    report_path=output_dir/'observer-report.md' if args.profile in ('root-mount-analysis','current-resource-analysis') else ROOT/'work/clone-observer-report.md'
    report_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({key:report.get(key) for key in ('launched','stop_reason','observed_exit','forced_exit','exit_code',
        'whole_app_network_isolation_verified')},ensure_ascii=False))
    return 0 if report['observed_exit'] and report['stop_reason']=='natural_exit' else 2


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','exception_type':type(error).__name__,'game_launch_retried':False}))
        sys.exit(2)
