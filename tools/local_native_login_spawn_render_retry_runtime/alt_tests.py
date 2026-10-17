"""Injected refusal policy plus real self APIs only; no LC, slot, UAC, PID open."""
import copy,ctypes as C,importlib.util,json,os,sys,tempfile,types
from ctypes import wintypes as W
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location('_cp73_fixture_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
def need(ok,reason):
    if not ok:raise AssertionError(reason)

def run_checks():
    d=load('diagnostic');a=load('image_alt');checks=[]
    name='\\Device\\HarddiskVolume5\\fixture.exe'
    def query(name=name,okay=True,error=0):return {'BOOL':okay,'complete':okay,'winerror':error,'name':name if okay else None}
    class Q:
        def __init__(self):self.calls=[];self.before={'pid':10,'birth':'20','wait':258,'job_member':True};self.after=dict(self.before);self.file=[query(),query()];self.images={'flags1':query(),'k32':query()}
        def state(self,p,j):self.calls.append('state');return self.before if self.calls.count('state')==1 else self.after
        def file_native_path(self,p):self.calls.append('file');return self.file[self.calls.count('file')-1]
        def image_native(self,p,m):self.calls.append(m);return self.images[m]
    def setup():
        member=types.SimpleNamespace(process=30,pid=10,identity=dict(pid=10,birth='20',image='fixture',parent_pid=None,elevated=False,integrity_rid=8192),retained_by_job=True,exact_fixed_path=True)
        main=types.SimpleNamespace(job=40,members={10:member})
        owner=types.SimpleNamespace(pinned_program_sha256='a'*64,_pinned_program_handle=50,handles=[50],_identity_failure_main=lambda:main)
        b=d.Binding(owner,main,member,30,40,10,d.identity_tuple(member),'a'*64,50)
        return b,Q()
    b,q=setup();diag=d.Diagnostic(b,q);row=diag.run(5)
    need(row['status']=='OBSERVED_CURRENT_NATIVE_IMAGE_ALT' and q.calls==['state','file','flags1','state','file'],'FLAGS1_EXACT_ORDER')
    need(diag.run(5)['reason']=='SINGLE_DIAGNOSTIC_ALREADY_SPENT' and q.calls.count('flags1')==1,'ONCE_ONLY')
    checks.extend(['flags1_success_exact_native_file_equality_diagnostic_only','alternate_once_limit'])
    b,q=setup();q.images['flags1']=query(okay=False,error=5);row=d.Diagnostic(b,q).run(5)
    need(row['status']=='OBSERVED_CURRENT_NATIVE_IMAGE_ALT' and q.calls.count('k32')==1,'K32_AFTER_FLAGS1_REFUSAL')
    checks.append('flags1_refusal_then_k32_once')
    b,q=setup();q.images['flags1']=query(okay=False,error=5);q.images['k32']=query(okay=False,error=31)
    need(d.Diagnostic(b,q).run(5)['status']=='UNKNOWN','BOTH_REFUSALS');checks.append('both_refusals_UNKNOWN')
    for bad in ('\\Device\\HarddiskVolume5\\other.exe','C:\\fixture.exe','\\Device\\HarddiskVolume5\\..\\fixture.exe',None):
        b,q=setup();q.images['flags1']=query(bad)
        row=d.Diagnostic(b,q).run(5);need(row['status']=='UNKNOWN' and 'k32' not in q.calls,'SUCCESS_MISMATCH_NO_FALLBACK')
        checks.append('successful_mismatch_or_malformed_no_k32')
    for field,value in [('pid',11),('birth','21'),('wait',0),('wait',0xffffffff),('job_member',False),('job_member',None)]:
        for side in ('before','after'):
            b,q=setup();getattr(q,side)[field]=value;row=d.Diagnostic(b,q).run(5)
            need(row['status']=='UNKNOWN' and (side=='after' or 'flags1' not in q.calls),'ACTIVE_STATE_REFUSAL')
            checks.append('refuse_'+side+'_'+field)
    for change in ('member','handle','job','identity','source','token','capture','main'):
        b,q=setup()
        if change=='member':b.main.members[10]=copy.copy(b.member)
        if change=='handle':b.member.process=31
        if change=='job':b.main.job=41
        if change=='identity':b.member.identity['birth']='21'
        if change=='source':b.owner.pinned_program_sha256='b'*64
        if change=='token':b.member.identity['elevated']=True
        if change=='capture':b.member.retained_by_job=False
        if change=='main':b.owner._identity_failure_main=lambda:None
        row=d.Diagnostic(b,q).run(5);need(row['status']=='UNKNOWN' and not q.calls,'FROZEN_BINDING_REFUSAL');checks.append('frozen_'+change+'_refused')
    b,q=setup();b.owner.handles=[];row=d.Diagnostic(b,q).run(5)
    need(row['status']=='UNKNOWN' and row['attempts'][0]['BOOL'] and row['exact_native_file_path_equality'] is None,'UNBOUND_FILE_SUCCESS_UNKNOWN')
    checks.append('unbound_file_alt_success_no_equality_UNKNOWN')
    b,q=setup();q.file[1]=query('\\Device\\HarddiskVolume5\\other.exe')
    need(d.Diagnostic(b,q).run(5)['status']=='UNKNOWN','FILE_CHANGED_UNKNOWN');checks.append('file_path_changed_UNKNOWN')
    b,q=setup();q.images['flags1']=query(okay=True);q.images['flags1']['complete']=False
    row=d.Diagnostic(b,q).run(5);need(row['status']=='UNKNOWN' and 'k32' not in q.calls,'INCOMPLETE_SUCCESS_NO_K32');checks.append('incomplete_success_no_k32')
    b,q=setup();row=d.Diagnostic(b,q).run(31);need(not q.calls and row['status']=='UNKNOWN','OTHER_ERROR_NO_API');checks.append('other_original_winerror_no_api')
    rec=a.Recorder(Path(tempfile.gettempdir())/'unused_cp73')
    C.set_last_error(91)
    rec.capture_binding(types.SimpleNamespace(),types.SimpleNamespace(),types.SimpleNamespace())
    need(not rec.bindings and rec.secondary==['CP73_CAPTURE_BINDING_UNKNOWN'] and C.get_last_error()==91,'CAPTURE_DIAGNOSTIC_EXCEPTION_ISOLATED')
    checks.append('capture_binding_exception_isolated_LastError_preserved')
    for field in ('process','birth','job','pin'):
        b,q=setup();original=q.image_native
        def changed(p,m,b=b,field=field,original=original):
            result=original(p,m)
            if field=='process':b.member.process=31
            if field=='birth':b.member.identity['birth']='21'
            if field=='job':b.main.job=41
            if field=='pin':b.owner._pinned_program_handle=51
            return result
        q.image_native=changed
        need(d.Diagnostic(b,q).run(5)['status']=='UNKNOWN','AFTER_BINDING_CHANGE_REFUSED');checks.append('after_'+field+'_binding_change_refused')
    # Real self-process is represented as an injected retained child. Only Job
    # membership and original flags0 Win5 are injected; alternate APIs/times/
    # wait/PID/source file pin/close operate on this controller, never the game.
    previous=sys.modules.get('core');windows=types.ModuleType('_cp73_self_original_windows')
    sys.modules['core']=types.SimpleNamespace(EXE=sys.executable,EXE_SHA='0'*64,BUILD=(),CLONE='fixture',require=a.parent.need,PROFILES={})
    try:exec(compile(a.parent.base.WINDOWS.read_bytes(),str(a.parent.base.WINDOWS),'exec'),windows.__dict__)
    finally:
        if previous is None:sys.modules.pop('core',None)
        else:sys.modules['core']=previous
    k=C.WinDLL('kernel32',use_last_error=True)
    signatures={'GetCurrentProcess':((),W.HANDLE),'GetProcessTimes':((W.HANDLE,*([C.POINTER(windows.FT)]*4)),W.BOOL),
        'QueryFullProcessImageNameW':((W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)),W.BOOL),
        'WaitForSingleObject':((W.HANDLE,W.DWORD),W.DWORD),'GetExitCodeProcess':((W.HANDLE,C.POINTER(W.DWORD)),W.BOOL),
        'CreateFileW':((W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE),W.HANDLE),
        'CloseHandle':((W.HANDLE,),W.BOOL),'GetProcessHandleCount':((W.HANDLE,C.POINTER(W.DWORD)),W.BOOL)}
    for method,(args,result) in signatures.items():getattr(k,method).argtypes=args;getattr(k,method).restype=result
    self_handle=k.GetCurrentProcess()
    def count():
        value=W.DWORD();need(k.GetProcessHandleCount(self_handle,C.byref(value)),'SELF_HANDLE_COUNT');return value.value
    class Proxy:
        def __init__(self,force):self.force=force;self.calls=[];self.closed=[];self.opened=[];self.original_failure=True;self.injected_opens=[]
        def __getattr__(self,name):
            need(name not in ('OpenProcess','ReadProcessMemory','DuplicateHandle','TerminateProcess','TerminateJobObject'),'NO_EXTRA_SELF_ACTION');return getattr(k,name)
        def CreateFileW(self,*args):
            h=k.CreateFileW(*args);self.opened.append(h);return h
        def CloseHandle(self,h):self.closed.append(h);return k.CloseHandle(h)
        def OpenProcess(self,rights,inherit,pid):
            need(rights==0x101000 and inherit is False and pid==os.getpid(),'INJECTED_INITIAL_CAPTURE_ONLY')
            self.injected_opens.append((rights,inherit,pid));return self_handle
        def IsProcessInJob(self,h,job,pointer):need(h==self_handle,'SELF_JOB_HANDLE');pointer._obj.value=1;return 1
        def QueryFullProcessImageNameW(self,h,flags,buffer,size):
            need(h==self_handle,'SELF_IMAGE_HANDLE');self.calls.append(flags)
            if (flags==0 and self.original_failure) or (flags==1 and self.force):C.set_last_error(5);return 0
            return k.QueryFullProcessImageNameW(h,flags,buffer,size)
    for force in (False,True):
        with tempfile.TemporaryDirectory() as work:
            initial=count();owner=windows.Native.__new__(windows.Native);owner.k=Proxy(force);owner.handles=[]
            main=types.SimpleNamespace(pid=1,job=123,members={},member_events=[],identity={'birth':'0'});rec=a.Recorder(work);rec.bind(owner,lambda:main)
            source=owner.source()
            need(len(owner.k.opened)==1 and owner.handles==owner.k.opened and owner._pinned_program_handle==owner.handles[0],'EXACT_EXISTING_FILE_PIN_NO_EXTRA_OPEN')
            times=[windows.FT() for _ in range(4)];need(k.GetProcessTimes(self_handle,*(C.byref(t) for t in times)),'SELF_BIRTH')
            owner.k.original_failure=False;owner.profile='current-resource-analysis';owner.token=lambda h:{'elevated':False,'integrity_rid':8192}
            owner.capture_member(main,os.getpid());member=main.members[os.getpid()]
            need(len(rec.bindings)==1 and rec.bindings[id(member)].member is member and rec.alternate is None,'ACTUAL_SUCCESS_CAPTURE_FREEZES_BINDING_ONLY')
            owner.k.original_failure=True
            try:owner.identity(self_handle,member.pid,include_token=False)
            except ValueError as error:
                need(str(error)=='native_image_required' and C.get_last_error()==5,'ORIGINAL_FAILURE_LASTERROR')
                need(getattr(error,'identity_failure_exited_member',None) is None,'NO_EXIT_PROMOTION')
                need(error.identity_failure_reference['original_winerror']==5 and error.identity_failure_reference['call_id']==1,'ORIGINAL_EXCEPTION_REFERENCE_ATTACHED')
            else:raise AssertionError('ORIGINAL_REFUSAL_MUST_ABORT')
            row=rec.alternate
            need(row is not None and row['status']=='OBSERVED_CURRENT_NATIVE_IMAGE_ALT' and row['exact_native_file_path_equality'] is True,'SELF_ALTERNATE_REAL_API_EQUALITY')
            need([x['method'] for x in row['attempts']]==(['flags1','k32'] if force else ['flags1']),'SELF_QUERY_ORDER')
            need(not row['query_used_for_admission'] and not row['cache_used_for_admission'] and not rec.record['known_exit'],'NO_GUARD_PROMOTION')
            report={};rec.finish(report)
            raw=(Path(work)/'identity-image-alternate.json').read_text()
            need(sys.executable not in raw and name not in raw and len(raw)<16384,'NO_RAW_PATH_PUBLIC_BOUND')
            opened=list(owner.handles);owner.close()
            need(owner.k.closed==opened and not owner.handles and count()==initial,'EXISTING_FILE_PIN_CLOSE_NO_HANDLE_LEAK')
            checks.extend(['self_real_'+('K32' if force else 'flags1')+'_API_exact_file_equality','original_Win5_ValueError_attachment_LastError_known_exit_preserved','self_source_one_existing_pin_closed_once_no_leak','original_success_capture_assignment_frozen_binding_before_callback'])
    return checks
if __name__=='__main__':print(json.dumps({'checks':len(run_checks()),'game_slot_uac_actions':0,'self_process_real_API_fixture':True}))
