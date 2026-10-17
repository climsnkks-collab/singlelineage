"""Same exact session alias; two bounded KEY/VERSION invocation records."""
import hashlib,importlib.util,json,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PATH=ROOT/'tools/local_native_login_create_exec_runtime/observer.py'
if hashlib.sha256(PATH.read_bytes()).hexdigest()!='2d012d357aed5d5ded00096fbefe15e491b718c56edc5895284058bdb84b8851':raise ValueError('FROZEN_CP06_OBSERVER')
s=importlib.util.spec_from_file_location('_key_invoke_observer_parent',PATH);parent=importlib.util.module_from_spec(s);s.loader.exec_module(parent)
_session_globals=parent._session_globals
if _session_globals is not parent.Observation.__init__.__globals__:raise ValueError('EXACT_KEY_INVOKE_SESSION_GLOBALS')
_session_globals.update(FORWARD_ROOT=ROOT/'work/local_native_login_key_invoke_boundary/runs',FORWARD_ENV='OWN_KEY_INVOKE_BOUNDARY_DIR',
 FORWARD_RUN_ID='cp74-render-20261009-01',WORK=ROOT/'work/local_native_login_spawn_render_retry_runtime')
for name in('RUN_ROOT','ENV','CLONE','SCHEMA','SHA'):globals()[name]=getattr(parent,name)
FORWARD_ROOT=_session_globals['FORWARD_ROOT'];FORWARD_ENV=_session_globals['FORWARD_ENV'];FORWARD_RUN_ID=_session_globals['FORWARD_RUN_ID'];WORK=_session_globals['WORK']
environment=parent.environment;forward_directory=parent.forward_directory;QUERY_KEYS=parent.QUERY_KEYS;DTO_KEYS=parent.DTO_KEYS
def __getattr__(name):
    if name=='LAST_SESSION':return _session_globals['LAST_SESSION']
    raise AttributeError(name)
def need(value,reason):
    if not value:raise ValueError(reason)
KEY_PUBLIC_KEYS={'schema','event','pid','birth','candidate_sha256','key_call_id','manager_matches_selected',
 'originating_socket_epoch_proven','entry_observed','entry_thread_id','entry_filetime','entry_order',
 'return_state','return_thread_id','return_filetime','return_order','opcode'}
def public_record(path,row,context):
    if path.name in {'auto-ok-install.json','auto-ok-invoke.json','auto-create-invoke.json','auto-select-ok-invoke.json','auto-create-submit.json'}:
        keys={'schema','event','pid','birth','candidate_sha256','success','native_error','reason'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp34-auto-ok-v1',
             'EXACT_CP34_AUTO_OK_SCHEMA')
        parent.parent.parent.identity(row,context)
        need(type(row['success'])is bool and type(row['native_error'])is int
             and 0<=row['native_error']<=0xffffffff and type(row['reason'])is int
             and 0<=row['reason']<=9,'EXACT_CP34_AUTO_OK_FIELDS')
        if path.name=='auto-ok-install.json':
            need((row['event'],row['success'],row['reason']) in
                 {('HOOK_INSTALLED',True,0),('HOOK_NOT_INSTALLED',False,1),
                  ('HOOK_NOT_INSTALLED',False,2),('HOOK_NOT_INSTALLED',False,3)},
                 'EXACT_CP34_HOOK_INSTALL_EVENT')
        elif path.name=='auto-ok-invoke.json':
            need((row['event']=='ORIGINAL_OK_RETURNED' and row['success'] is True
                  and row['reason']==0) or
                 (row['event']=='ORIGINAL_OK_REFUSED' and row['success'] is False
                  and 1<=row['reason']<=9),'EXACT_CP34_HOOK_INVOKE_EVENT')
        elif path.name=='auto-create-invoke.json':
            need((row['event']=='ORIGINAL_SLOT_SELECTED' and row['success'] is True
                  and row['reason']==0) or
                 (row['event']=='ORIGINAL_SLOT_REFUSED' and row['success'] is False
                  and 1<=row['reason']<=9),'EXACT_CP42_SLOT_INVOKE_EVENT')
        elif path.name=='auto-select-ok-invoke.json':
            need((row['event']=='ORIGINAL_SELECT_OK_RETURNED' and row['success'] is True
                  and row['reason']==0) or
                 (row['event']=='ORIGINAL_SELECT_OK_REFUSED' and row['success'] is False
                  and 1<=row['reason']<=9),'EXACT_CP73_SELECT_OK_EVENT')
        else:
            need((row['event']=='ORIGINAL_CREATE_RETURNED' and row['success'] is True
                  and row['reason']==0) or
                 (row['event']=='ORIGINAL_CREATE_REFUSED' and row['success'] is False
                  and 1<=row['reason']<=9),'EXACT_CP73_CREATE_SUBMIT_EVENT')
        return row
    if path.name=='factory-probe.json':
        keys={'schema','pid','birth','candidate_sha256','filetime','bounded','before_protect',
          'call_returned','call_exception_code','message_nonnull','vtable_match','arena_zero',
          'destroy_attempted','destroy_returned','destroy_exception_code','after_query_ok','after_protect'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp17-factory-probe-v1',
          'EXACT_CP17_FACTORY_PROBE_SCHEMA')
        parent.parent.parent.identity(row,context)
        need(type(row['filetime'])is int and 0<row['filetime']<1<<64
          and all(type(row[k])is bool for k in ('bounded','call_returned','message_nonnull',
            'vtable_match','arena_zero','destroy_attempted','destroy_returned','after_query_ok'))
          and all(type(row[k])is int and 0<=row[k]<=0xffffffff
            for k in ('before_protect','call_exception_code','destroy_exception_code','after_protect'))
          and (not row['bounded'] or row['before_protect']==1)
          and (row['bounded'] or not row['call_returned'])
          and (not row['message_nonnull'] or row['call_returned'])
          and (not row['destroy_attempted'] or
            (row['message_nonnull'] and row['vtable_match'] and row['arena_zero']))
          and (not row['destroy_returned'] or row['destroy_attempted'])
          and (row['after_query_ok'] or row['after_protect']==0),
          'EXACT_CP17_FACTORY_PROBE_FIELDS')
        return row
    if path.name=='dto-pages.json':
        keys={'schema','pid','birth','candidate_sha256','filetime','pages'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp16-dto-pages-v1',
          'EXACT_CP16_DTO_PAGES_SCHEMA')
        parent.parent.parent.identity(row,context)
        need(type(row['filetime'])is int and 0<row['filetime']<1<<64
          and type(row['pages'])is list and len(row['pages'])==5,
          'EXACT_CP16_DTO_PAGES_COUNT')
        names=['factory','setter','clone','serializer','original_builder']
        fields={'name','query_ok','state','protect','type','same_image'}
        for index,page in enumerate(row['pages']):
            need(type(page)is dict and set(page)==fields and page['name']==names[index]
              and type(page['query_ok'])is bool and type(page['same_image'])is bool
              and all(type(page[k])is int and 0<=page[k]<=0xffffffff
                for k in ('state','protect','type'))
              and (page['query_ok'] or
                (not page['same_image'] and page['state']==0 and page['protect']==0 and page['type']==0)),
              'EXACT_CP16_DTO_PAGE_FIELDS')
        return row
    if path.name.startswith('sender-probe-') and path.name.endswith('.json'):
        keys={'schema','pid','birth','candidate_sha256','index','filetime','thread_id',
          'phase','caller_rva','opcode','binding_reason','wrapper_selected',
          'original_fallback','selected_ready','network_matches_selected','source_mismatch_override'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp15-sender-probe-v1',
          'EXACT_CP15_SENDER_PROBE_SCHEMA')
        parent.parent.parent.identity(row,context)
        index=int(path.stem.removeprefix('sender-probe-'))
        need(type(row['index'])is int and row['index']==index and 0<=index<8
          and type(row['filetime'])is int and 0<row['filetime']<1<<64
          and type(row['thread_id'])is int and 0<row['thread_id']<=0xffffffff
          and type(row['phase'])is int and 0<=row['phase']<=5
          and type(row['caller_rva'])is int and row['caller_rva']==0x2746ff
          and type(row['opcode'])is int and row['opcode']==0x4f3d
          and type(row['binding_reason'])is int and 0<=row['binding_reason']<=12
          and all(type(row[k])is bool for k in ('wrapper_selected','original_fallback',
            'selected_ready','network_matches_selected','source_mismatch_override'))
          and row['wrapper_selected']!=row['original_fallback']
          and (not row['source_mismatch_override'] or
            (row['wrapper_selected'] and row['binding_reason']==9 and
             row['selected_ready'] and row['network_matches_selected'] and row['phase']==2)),
          'EXACT_CP15_SENDER_PROBE_FIELDS')
        return row
    if path.name.startswith('sender-count-') and path.name.endswith('.json'):
        keys={'schema','pid','birth','candidate_sha256','index','filetime','caller_rva',
          'opcode','phase_before','selected_ready','network_matches_selected',
          'own_limit_refused','original_called','own_branch_entered','own_result_code'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp14-sender-count-v1',
          'EXACT_CP14_SENDER_COUNT_SCHEMA')
        parent.parent.parent.identity(row,context)
        index=int(path.stem.removeprefix('sender-count-'))
        need(type(row['index'])is int and row['index']==index and 0<=index<8
          and type(row['filetime'])is int and 0<row['filetime']<1<<64
          and type(row['caller_rva'])is int and row['caller_rva']==0x2746ff
          and type(row['opcode'])is int and row['opcode']==0x4f3d
          and type(row['phase_before'])is int and 0<=row['phase_before']<=5
          and all(type(row[k])is bool for k in ('selected_ready','network_matches_selected',
            'own_limit_refused','original_called','own_branch_entered'))
          and row['original_called'] is True
          and type(row['own_result_code'])is int and -1<=row['own_result_code']<=6,
          'EXACT_CP14_SENDER_COUNT_FIELDS')
        return row
    if path.name.startswith('connect-probe-') and path.name.endswith('.json'):
        keys={'schema','pid','birth','candidate_sha256','index','filetime','thread_id','phase',
          'caller_in_image','caller_rva','binding_reason','wrapper_selected','original_fallback',
          'binding_stage','failed_record_id','bound_check_bits'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp13-connect-probe-v1',
          'EXACT_CP13_CONNECT_PROBE_SCHEMA')
        parent.parent.parent.identity(row,context)
        index=int(path.stem.removeprefix('connect-probe-'))
        need(type(row['index'])is int and row['index']==index and 0<=index<8
          and type(row['filetime'])is int and 0<row['filetime']<1<<64
          and type(row['thread_id'])is int and 0<row['thread_id']<=0xffffffff
          and type(row['phase'])is int and 1<=row['phase']<=2,
          'EXACT_CP11_PROBE_INDEX_TIME_PHASE')
        need(type(row['caller_in_image'])is bool and type(row['caller_rva'])is int
          and 0<=row['caller_rva']<0x3e97000 and (row['caller_rva']==0 or row['caller_in_image'])
          and type(row['binding_reason'])is int and 0<=row['binding_reason']<=12
          and type(row['wrapper_selected'])is bool and type(row['original_fallback'])is bool
          and row['wrapper_selected']!=row['original_fallback']
          and type(row['binding_stage'])is int and 0<=row['binding_stage']<=3
          and type(row['failed_record_id'])is int and -1<=row['failed_record_id']<=10
          and type(row['bound_check_bits'])is int and 0<=row['bound_check_bits']<=16383,
          'EXACT_CP13_PROBE_PUBLIC_FIELDS')
        return row
    if path.name.startswith('connect-caller-') and path.name.endswith('.json'):
        keys={'schema','pid','birth','candidate_sha256','index','filetime','caller_in_image',
          'caller_rva','phase_before','selected_task_matches','duplicate_candidate',
          'local_peer_verified','original_bypassed','returned_bool','entry_last_error',
          'return_last_error','source_mismatch_override'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp13-connect-caller-v2',
          'EXACT_CP13_CONNECT_PUBLIC_SCHEMA')
        parent.parent.parent.identity(row,context)
        index=int(path.stem.removeprefix('connect-caller-'))
        need(type(row['index'])is int and row['index']==index and 0<=index<8
          and type(row['filetime'])is int and 0<row['filetime']<1<<64
          and type(row['caller_in_image'])is bool and type(row['caller_rva'])is int
          and 0<=row['caller_rva']<0x3e97000
          and (row['caller_rva']==0 or row['caller_in_image']),
          'EXACT_CP09_CONNECT_INDEX_AND_CALLER')
        need(type(row['phase_before'])is int and 0<=row['phase_before']<=5
          and all(type(row[key])is bool for key in ('selected_task_matches','duplicate_candidate',
            'local_peer_verified','original_bypassed','returned_bool','source_mismatch_override'))
          and type(row['entry_last_error'])is int and 0<=row['entry_last_error']<=0xffffffff
          and type(row['return_last_error'])is int and 0<=row['return_last_error']<=0xffffffff,
          'EXACT_CP09_CONNECT_PUBLIC_FIELDS')
        need(not row['selected_task_matches'] or row['caller_rva']==0x26f8bd,
          'EXACT_CP09_SELECTED_EDGE')
        need(not row['duplicate_candidate'] or((row['selected_task_matches'] or row['source_mismatch_override'])
          and row['phase_before']==2),'EXACT_CP13_DUPLICATE_SCOPE')
        need(not row['source_mismatch_override'] or row['caller_rva']==0x26f8bd,
          'EXACT_CP13_OVERRIDE_CALLER')
        need(not row['local_peer_verified'] or row['duplicate_candidate'],
          'EXACT_CP09_PEER_SCOPE')
        need(not row['original_bypassed'] or(row['local_peer_verified'] and row['returned_bool']
          and row['return_last_error']==0),'EXACT_CP09_BYPASS_SCOPE')
        return row
    if path.name.startswith('close-caller-') and path.name.endswith('.json'):
        keys={'schema','pid','birth','candidate_sha256','index','filetime','caller_in_image','caller_rva',
          'route','selected_socket_pair_matches','phase','entry_last_error','socket_state_read',
          'read_seen','initialized','handle_present','send_sequence','game_stack_rvas'}
        need(type(row)is dict and set(row)==keys and row['schema']=='own-cp10-close-stack-v1',
          'EXACT_CP10_CLOSE_PUBLIC_SCHEMA')
        parent.parent.parent.identity(row,context)
        index=int(path.stem.removeprefix('close-caller-'))
        need(type(row['index'])is int and row['index']==index and 0<=index<8,
          'EXACT_CP08_CLOSE_INDEX')
        need(type(row['filetime'])is int and 0<row['filetime']<1<<64
          and type(row['caller_in_image'])is bool and type(row['caller_rva'])is int
          and 0<=row['caller_rva']<0x3e97000,'EXACT_CP08_CLOSE_CALLER')
        route={0x26cbc3:'WORKER_SEND_ERROR',0x26c0b8:'ROLE0_CLOSE_TASK',
          0x32f54b:'CONNECT_FAILURE'}.get(row['caller_rva'],'OTHER_OR_UNKNOWN')
        need(row['route']==route and (row['caller_rva']==0 or row['caller_in_image'])
          and type(row['selected_socket_pair_matches'])is bool
          and type(row['phase'])is int and 0<=row['phase']<=5
          and type(row['entry_last_error'])is int and 0<=row['entry_last_error']<=0xffffffff,
          'EXACT_CP08_CLOSE_METADATA')
        need(type(row['socket_state_read'])is bool and type(row['send_sequence'])is int
          and 0<=row['send_sequence']<=0xffffffff,'EXACT_CP08_CLOSE_SOCKET_STATE')
        need(type(row['game_stack_rvas'])is list and len(row['game_stack_rvas'])<=8
          and all(type(rva)is int and 0<=rva<0x3e97000 for rva in row['game_stack_rvas']),
          'EXACT_CP10_BOUNDED_GAME_STACK_RVAS')
        if row['socket_state_read']:
            need(all(type(row[key])is bool for key in ('read_seen','initialized','handle_present')),
              'EXACT_CP08_CLOSE_TYPED_FLAGS')
        else:
            need(all(row[key]is None for key in ('read_seen','initialized','handle_present'))
              and row['send_sequence']==0,'EXACT_CP08_CLOSE_UNKNOWN_FLAGS')
        return row
    if path.name not in {'key-task-invoke.json','key-version-send.json'}:return parent.public_record(path,row,context)
    need(type(row)is dict and set(row)==KEY_PUBLIC_KEYS and row['schema']=='own-key-invoke-v1','EXACT_KEY_PUBLIC_SCHEMA')
    identity=parent.parent.parent.identity
    identity(row,context)
    expected='KEY_TASK_INVOKE'if path.name=='key-task-invoke.json'else'KEY_VERSION_SEND'
    need(row['event']==expected and type(row['key_call_id'])is int and row['key_call_id']==1,'ONE_KEY_INVOCATION_CORRELATION')
    need(row['manager_matches_selected']is True and row['originating_socket_epoch_proven']is False
      and row['entry_observed']is True,'KEY_ENTRY_MANAGER_MATCH_ONLY_NOT_EPOCH_OR_PARSE_PROOF')
    need(type(row['entry_thread_id'])is int and 0<row['entry_thread_id']<=0xffffffff
      and type(row['entry_filetime'])is int and 0<row['entry_filetime']<1<<64
      and type(row['entry_order'])is int and 1<=row['entry_order']<=4,'KEY_PUBLIC_ENTRY_FIELDS')
    need(type(row['return_state'])is int and 0<=row['return_state']<=2,'KEY_PUBLIC_RETURN_STATE')
    if row['return_state']==0:
        need(all(row[k]is None for k in('return_thread_id','return_filetime','return_order')),'KEY_RETURN_UNCONFIRMED_NULL')
    else:
        need(type(row['return_thread_id'])is int and 0<row['return_thread_id']<=0xffffffff
          and type(row['return_filetime'])is int and 0<row['return_filetime']<1<<64
          and type(row['return_order'])is int and row['entry_order']<row['return_order']<=4,'KEY_PUBLIC_RETURN_FIELDS')
    need(row['opcode']is None if expected=='KEY_TASK_INVOKE'else type(row['opcode'])is int and row['opcode']==20020,'KEY_VERSION_ORIGINAL_OPCODE_ONLY')
    return row
class Observation(parent.Observation):
    def _forward_records(self):
        result=[];names={'context.json',*parent.parent.parent.parent.EVENTS,'selected-boundary.json','own-connect-result.json',
          'dto-readiness.json','dto-pages.json','factory-probe.json','key-task-invoke.json','key-version-send.json',
          'auto-ok-install.json','auto-ok-invoke.json','auto-create-invoke.json','auto-select-ok-invoke.json','auto-create-submit.json'}
        names.update(f'close-caller-{i}.json'for i in range(8))
        names.update(f'connect-caller-{i}.json'for i in range(8))
        names.update(f'connect-probe-{i}.json'for i in range(8))
        names.update(f'sender-probe-{i}.json'for i in range(8))
        names.update(f'sender-count-{i}.json'for i in range(8))
        files=list(self.forward_path.iterdir());need(len(files)<=58 and all(p.name in names for p in files),'BOUNDED_CP73_DIAGNOSTIC_FILES')
        for path in sorted(files):
            if path.name=='context.json':continue
            stat=path.lstat();need(path.is_file()and not path.is_symlink()and not getattr(stat,'st_file_attributes',0)&0x400
              and stat.st_nlink==1 and 0<stat.st_size<=4096,'PLAIN_BOUNDED_KEY_INVOKE_DIAGNOSTIC')
            result.append({'file':path.name,'public':public_record(path,json.loads(path.read_bytes()),self.forward_context)})
        return result
method=parent.Observation.bind_owner;constants=list(method.__code__.co_consts);changed=0
for index,code in enumerate(constants):
    if isinstance(code,types.CodeType)and code.co_name=='created':
        if code.co_consts.count('own-create-exec-primary-v1')!=1:raise ValueError('ONE_KEY_INVOKE_PRIMARY_CONTEXT_LITERAL')
        constants[index]=code.replace(co_consts=tuple('own-key-invoke-primary-v1'if c=='own-create-exec-primary-v1'else c for c in code.co_consts));changed+=1
if changed!=1:raise ValueError('ONE_KEY_INVOKE_CREATOR')
Observation.bind_owner=types.FunctionType(method.__code__.replace(co_consts=tuple(constants)),method.__globals__,method.__name__,method.__defaults__,method.__closure__)
