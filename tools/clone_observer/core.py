"""First-gate observer policy: fixed unmodified clone, one owned process only."""
import hashlib
import re
import time

CLONE = r'C:\Users\Chansol\Documents\ChatGPT\싱글리니지\work\standalone_boot\current-unmodified-clone'
EXE = CLONE + r'\LC.exe'
EXE_SHA = '9ffc24fe304aacbb98642363f7b19fd4610b12d1fd0cb09a30c0c944f170b7af'
VARIANTS = {
    'control': ('CONTROL', EXE_SHA),
    'candidate': ('CANDIDATE', '7e66b52b18caf852c741d43abdef0398faf2894c9b989172a8123b16141f1d33'),
    'admin-off': ('ADMIN_OFF','f13cb8967ff800268af5b9190c75789cc0991ccb3a42fdf085e314d92e04e4f1'),
    'admin-launcher-off': ('ADMIN_LAUNCHER_OFF','94fa03e91eac3798c7f940cd9b30e6fe9862f577f226eb3a2fdf81314064e35c'),
    'sdk-multiclient':('SDK_MULTICLIENT','85497a9d4c5abfaff33d14766874e74eca93bda96f1745f5dc17f4ca74d150e7'),
    'route-b':('ROUTE_B','720d4f8bdc754f2f5ef2dd69cc9936f5edc7d9afc0473d7a885111cf64fc05e5'),
    'root-mount-route-b':('ROOT_MOUNT_ROUTE_B','374691bc3b302adae799398747788dac22d4d186a2c4042f596b013843c0f1c4'),
    'current-resource-root-mount':('CURRENT_RESOURCE_ROOT_MOUNT','374691bc3b302adae799398747788dac22d4d186a2c4042f596b013843c0f1c4'),
}
BUILD = (26, 9, 29, 2001)
PROFILES={'single':1,'startup-analysis':16,'online-startup-analysis':16,'online-config-analysis':16,'root-mount-analysis':16,'current-resource-analysis':16}
PUBLIC_TITLES = {'Lineage Classic', 'Lineage', '리니지 클래식', '리니지', 'NC', 'PURPLE', '알림', 'Notice', 'Error',
                 'Lineage Classic - 26.09.29.2001 [LIVE]'}
PUBLIC_CLASSES = {'#32770','GLFW30','Static','Button','Edit','ComboBox','ComboBoxEx32','ListBox',
    'SysListView32','SysTreeView32','SysTabControl32','SysLink','ToolbarWindow32',
    'msctls_progress32','msctls_statusbar32','tooltips_class32','IME','MSCTFIME UI',
    'Chrome_WidgetWin_0','Chrome_WidgetWin_1','Chrome_RenderWidgetHostHWND',
    'Intermediate D3D Window','ApplicationFrameWindow','Windows.UI.Core.CoreWindow'}
PUBLIC_LAUNCHER_MESSAGES = {'리니지 클래식 실행은 게임 런처를 통해 실행 부탁드립니다.'}


def public_class(name):
    name=name[:64]
    value={'class_chars':len(name),'class_sha256':hashlib.sha256(name.encode()).hexdigest()}
    if name in PUBLIC_CLASSES:value['public_class']=name
    return value


def require(value, reason):
    if not value:
        raise ValueError(reason)


def _public_child_class_counts(children):
    """Count bounded public class labels in first-seen order."""
    class_counts={}
    for child in children[:64]:
        label=public_class(child.get('class',''))
        key=label.get('public_class','unknown:'+label['class_sha256'])
        class_counts[key]=class_counts.get(key,0)+1
    return class_counts


def _public_static_texts(children):
    """Keep allowed Static text verbatim; expose only hashes for other text."""
    texts, unknown = [], []
    for child in children[:64]:
        if child.get('class') != 'Static':
            continue
        text = child.get('text', '')[:480]
        if text.strip() in PUBLIC_LAUNCHER_MESSAGES:
            texts.append(text)
        elif text:
            unknown.append({'chars': len(text), 'sha256': hashlib.sha256(text.encode()).hexdigest()})
    return texts, unknown


def public_window(row):
    """Never collect Edit/ComboBox text, credentials, or unknown UI plaintext."""
    title = row.get('title', '')[:240]
    result = {'title_chars': len(title), 'title_sha256': hashlib.sha256(title.encode()).hexdigest()}
    if title in PUBLIC_TITLES:
        result['public_caption'] = title
    result.update(public_class(row.get('class','')))
    for key in ('visible','geometry','owner_relation','parent_relation','same_process_child_count',
                'foreign_child_count','child_enumeration_truncated','public_metadata_errors'):
        if key in row:result[key]=row[key]
    result['child_class_counts'] = _public_child_class_counts(row.get('children', []))
    # A matching old digest alone is not a stage identity. Actual class and
    # visibility must have been read for this newly owned HWND observation.
    if title=='Default IME' and row.get('class')=='IME' and type(row.get('visible'))is bool:
        result.update({'public_caption':'Default IME','window_role':'Windows_default_IME_infrastructure',
            'game_UI_evidence':False})
    texts, unknown = _public_static_texts(row.get('children', []))
    result['public_launcher_text'] = texts
    result['exact_source_launcher_message_detected']=bool(texts)
    result['unknown_static_text'] = unknown
    if 'owned_member' in row:result['owned_member']=row['owned_member']
    return result


def observe(backend, gate, seconds=25, clock=time.monotonic, sleep=time.sleep, variant='control',profile='single',public_review=False):
    require(profile in PROFILES,'fixed_observer_profile_required')
    require((profile=='online-config-analysis' and variant in ('admin-off','admin-launcher-off','sdk-multiclient','route-b'))
        or (profile=='root-mount-analysis' and variant=='root-mount-route-b')
        or (profile=='current-resource-analysis' and variant=='current-resource-root-mount')
        or (profile not in ('online-config-analysis','root-mount-analysis','current-resource-analysis') and variant in ('control','candidate')
            and (PROFILES[profile]!=16 or variant=='control')),'fixed_profile_variant_required')
    require(variant in VARIANTS,'fixed_control_or_candidate_variant_required')
    require(profile not in ('root-mount-analysis','current-resource-analysis') or seconds==120,'fixed_root_mount_120_seconds_required')
    role,expected_sha=VARIANTS[variant]
    require(type(public_review)is bool,'explicit_public_review_flag_required')
    require((public_review and profile=='online-config-analysis' and variant=='admin-launcher-off' and seconds==900)
        or (not public_review and 20<=seconds<=120),'fixed_public_review_900_or_normal_20_to_120_required')
    report = {'schema': 'lc-owned-clone-first-gate-v1', 'launched': False,
        'standalone_play_verified': False, 'whole_app_network_isolation_verified': False,
        'single_process_job_restriction': profile=='single', 'screenshot_captured': False,
        'UAC_requested': False, 'observed_exit': False, 'forced_exit': False,
        'windows': [], 'stop_reason': None}
    report.update({'observation_bound_seconds':seconds,'process_metadata_samples':[]})
    report['public_UI_review_requested']=public_review
    report.update({'profile':profile,'job_active_process_limit':PROFILES[profile],
        'analysis_only':PROFILES[profile]==16,'SDK_descendant_online_analysis_allowed':PROFILES[profile]==16,
        'network_isolation_required':profile not in ('online-startup-analysis','online-config-analysis','root-mount-analysis','current-resource-analysis')})
    report.update({'program_variant':role,'expected_program_sha256':expected_sha,
        'publisher_signature_content_mismatch':variant!='control','operational_adoption':False})
    if profile in ('online-config-analysis','root-mount-analysis','current-resource-analysis'):report['stock_signature_verified']=False
    child = None
    try:
        controller = backend.controller()
        require(controller['elevated'] is False and controller['integrity_rid'] <= 8192,
            'ordinary_controller_required')
        report['controller'] = controller
        snapshot = backend.inventory()
        require(snapshot['lc_count'] == 0, 'no_LC_prelaunch_required')
        report['prelaunch'] = snapshot
        if profile in ('root-mount-analysis','current-resource-analysis'):
            report['PURPLE_absent_at_start']=snapshot.get('purple')==[]
            report['PURPLE_app_absent_at_start']=snapshot.get('purple_apps')==[]
            report['cold_PURPLE_independence_verified']=False
            report['memory_state_sampler_enabled']=False
        report['isolation_prelaunch'] = gate.check()
        if profile in ('root-mount-analysis','current-resource-analysis'):
            report['memory_state_sampler_enabled']=report['isolation_prelaunch'].get('public_state_diagnostic_enabled')is True
        source = backend.source()
        require(source['sha256'] == expected_sha and tuple(source['build']) == BUILD and source['path'] == EXE,
            'fixed_clone_source_build_required')
        report['source'] = source
        # Thread never runs before Job association, token/identity and a second
        # fresh full firewall audit. No debugger flag or memory API is used.
        child = backend.create_suspended()
        report['launched'] = True
        report['child'] = child.identity
        require(child.identity['image'] == EXE and child.identity['elevated'] is False
            and child.identity['integrity_rid'] <= 8192
            and child.identity['parent_pid'] == controller['pid'], 'owned_child_identity_or_token_required')
        backend.attach_single_process_job(child)
        if hasattr(gate,'owned_child_created'):
            gate.owned_child_created(child.identity)
        report['isolation_suspended_child'] = gate.check()
        backend.resume(child)
        report['primary_thread_resumed'] = True
        deadline = clock() + seconds
        next_metrics=clock()
        seen = set()
        while clock() < deadline:
            exit_code = backend.exit_code(child)
            constraint = backend.job_events(child)
            if PROFILES[profile]==16:report['owned_job_members']=backend.member_summary(child)
            if PROFILES[profile]==16 and hasattr(backend,'job_metrics'):
                samples=backend.job_metrics(child)
                require(len(samples)<=16,'owned_metadata_batch_bound_16')
                report['process_metadata_samples'].extend(samples[:400-len(report['process_metadata_samples'])])
            if exit_code is not None:
                report.update({'observed_exit': True, 'exit_code': exit_code, 'stop_reason': 'natural_exit'})
            if constraint:
                report['job_events'] = constraint
                report['stop_reason'] = 'SDK_child_blocked_or_job_constraint'
                break
            if exit_code is not None:
                if PROFILES[profile]!=16 or backend.active_job_count(child)==0:break
                report['main_natural_exit_with_owned_descendants']=True
            if exit_code is None:
                token = backend.child_token(child)
                require(token['elevated'] is False and token['integrity_rid'] <= 8192,
                    'unexpected_child_elevation_or_unknown_token')
            if exit_code is None and hasattr(backend,'process_metrics') and clock()>=next_metrics\
                    and not (PROFILES[profile]==16 and hasattr(backend,'job_metrics')):
                metrics=backend.process_metrics(child)
                if len(report['process_metadata_samples'])<25:
                    report['process_metadata_samples'].append(metrics)
                next_metrics=clock()+5
            windows=backend.job_windows(child) if PROFILES[profile]==16 else backend.windows(child)
            for window in windows:
                public = public_window(window)
                fingerprint = repr(public)
                if fingerprint not in seen and len(report['windows']) < 32:
                    seen.add(fingerprint)
                    report['windows'].append(public)
            sleep(.1)
        else:
            report['stop_reason'] = 'observation_timeout'
    except Exception as error:
        report['stop_reason'] = error.args[0] if type(error) is ValueError else type(error).__name__
        report['exception_type'] = type(error).__name__
        if hasattr(error,'owned_member_refusal'):
            report['owned_member_refusal']={key:value for key,value in error.owned_member_refusal.items()
                if key in ('pid','birth','image_basename','native_identity_captured','job_membership_verified',
                    'elevated','integrity_rid','token_verified','failed_criteria','handle_retained_for_owned_cleanup',
                    'exact_fixed_path','known_original_program','file_version','high_as_actual_normal_app_relaunch')}
        if getattr(error,'created_suspended',False):
            report['launched']=True
            report['creation_failure_cleanup']=getattr(error,'creation_cleanup',{'outcome':'unknown'})
            report['forced_exit']=report['creation_failure_cleanup'].get('forced_exit',False)
    finally:
        if child is not None:
            try:
                cleanup = backend.cleanup_owned(child)
            except Exception as error:
                cleanup = {'positive_exit':False,'outcome':'unknown','exception_type':type(error).__name__}
            report['cleanup'] = cleanup
            report['forced_exit'] = cleanup.get('forced_exit', False)
            if report['forced_exit']:
                report['observed_exit'] = False
            report['exit_code'] = cleanup.get('exit_code', report.get('exit_code'))
        backend.close()
    return report
