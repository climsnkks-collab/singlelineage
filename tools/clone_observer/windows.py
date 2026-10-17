"""Query native identity/public owned-window text; one fixed suspended child Job.

No debugger/injection/memory reads, elevation, UI clicks, or global screenshots.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import time
from types import SimpleNamespace
from core import EXE, EXE_SHA, BUILD, CLONE, require, PROFILES


class FT(C.Structure):
    _fields_ = [('low', W.DWORD), ('high', W.DWORD)]


class STARTUP(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR), ('title', W.LPWSTR),
        ('x', W.DWORD), ('y', W.DWORD), ('width', W.DWORD), ('height', W.DWORD),
        ('charsx', W.DWORD), ('charsy', W.DWORD), ('fill', W.DWORD), ('flags', W.DWORD),
        ('show', W.WORD), ('reserved2size', W.WORD), ('reserved2', C.c_void_p),
        ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class PROCESS(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class ENTRY(C.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD), ('heap', C.c_size_t),
        ('module', W.DWORD), ('threads', W.DWORD), ('parent', W.DWORD), ('priority', W.LONG),
        ('flags', W.DWORD), ('name', W.WCHAR * 260)]


class BASIC_LIMIT(C.Structure):
    _fields_ = [('process_time', C.c_longlong), ('job_time', C.c_longlong), ('flags', W.DWORD),
        ('min_working', C.c_size_t), ('max_working', C.c_size_t), ('active_limit', W.DWORD),
        ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]


class IO(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]


class LIMIT(C.Structure):
    _fields_ = [('basic', BASIC_LIMIT), ('io', IO), ('process_memory', C.c_size_t),
        ('job_memory', C.c_size_t), ('peak_process', C.c_size_t), ('peak_job', C.c_size_t)]


class ASSOCIATE(C.Structure):
    _fields_ = [('key', C.c_void_p), ('port', W.HANDLE)]


class RECT(C.Structure):
    _fields_=[(name,W.LONG) for name in ('left','top','right','bottom')]


class MODULE(C.Structure):
    _fields_=[('size',W.DWORD),('module_id',W.DWORD),('pid',W.DWORD),('global_usage',W.DWORD),
        ('process_usage',W.DWORD),('base',C.c_void_p),('image_size',W.DWORD),('handle',W.HMODULE),
        ('basename',W.WCHAR*256),('path',W.WCHAR*260)]


class ACCOUNTING(C.Structure):
    _fields_=[('user',C.c_longlong),('kernel',C.c_longlong),('period_user',C.c_longlong),
        ('period_kernel',C.c_longlong),('page_faults',W.DWORD),('total',W.DWORD),
        ('active',W.DWORD),('terminated',W.DWORD)]


class Native:
    def __init__(self,profile='single'):
        require(profile in PROFILES,'fixed_native_profile_required')
        self.profile=profile;self.process_limit=PROFILES[profile]
        require(os.name == 'nt', 'Windows_required')
        self.k, self.u, self.a = (C.WinDLL(name, use_last_error=True) for name in ('kernel32','user32','advapi32'))
        signatures = {
            'CloseHandle': ((W.HANDLE,), W.BOOL), 'GetCurrentProcess': ((), W.HANDLE),
            'OpenProcess': ((W.DWORD,W.BOOL,W.DWORD),W.HANDLE),
            'GetProcessTimes': ((W.HANDLE,*([C.POINTER(FT)]*4)),W.BOOL),
            'QueryFullProcessImageNameW': ((W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)),W.BOOL),
            'CreateToolhelp32Snapshot': ((W.DWORD,W.DWORD),W.HANDLE),
            'Process32FirstW': ((W.HANDLE,C.POINTER(ENTRY)),W.BOOL),
            'Process32NextW': ((W.HANDLE,C.POINTER(ENTRY)),W.BOOL),
            'Module32FirstW': ((W.HANDLE,C.POINTER(MODULE)),W.BOOL),
            'Module32NextW': ((W.HANDLE,C.POINTER(MODULE)),W.BOOL),
            'WaitForSingleObject': ((W.HANDLE,W.DWORD),W.DWORD),
            'GetExitCodeProcess': ((W.HANDLE,C.POINTER(W.DWORD)),W.BOOL),
            'TerminateProcess': ((W.HANDLE,W.UINT),W.BOOL),
            'TerminateJobObject': ((W.HANDLE,W.UINT),W.BOOL),
            'CreateFileW': ((W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE),W.HANDLE),
            'CreateProcessW': ((W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(STARTUP),C.POINTER(PROCESS)),W.BOOL),
            'CreateJobObjectW': ((C.c_void_p,W.LPCWSTR),W.HANDLE),
            'SetInformationJobObject': ((W.HANDLE,C.c_int,C.c_void_p,W.DWORD),W.BOOL),
            'AssignProcessToJobObject': ((W.HANDLE,W.HANDLE),W.BOOL),
            'QueryInformationJobObject': ((W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)),W.BOOL),
            'IsProcessInJob': ((W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)),W.BOOL),
            'ResumeThread': ((W.HANDLE,),W.DWORD),
            'CreateIoCompletionPort': ((W.HANDLE,W.HANDLE,C.c_size_t,W.DWORD),W.HANDLE),
            'GetQueuedCompletionStatus': ((W.HANDLE,C.POINTER(W.DWORD),C.POINTER(C.c_size_t),C.POINTER(C.c_void_p),W.DWORD),W.BOOL),
        }
        for name,(args,result) in signatures.items():
            fn = getattr(self.k,name);fn.argtypes,fn.restype=args,result
        self.a.OpenProcessToken.argtypes=(W.HANDLE,W.DWORD,C.POINTER(W.HANDLE));self.a.OpenProcessToken.restype=W.BOOL
        self.a.GetTokenInformation.argtypes=(W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD));self.a.GetTokenInformation.restype=W.BOOL
        self.a.GetSidSubAuthorityCount.argtypes=(C.c_void_p,);self.a.GetSidSubAuthorityCount.restype=C.POINTER(C.c_ubyte)
        self.a.GetSidSubAuthority.argtypes=(C.c_void_p,W.DWORD);self.a.GetSidSubAuthority.restype=C.POINTER(W.DWORD)
        self.u.GetWindowThreadProcessId.argtypes=(W.HWND,C.POINTER(W.DWORD))
        self.u.GetWindowTextW.argtypes=(W.HWND,W.LPWSTR,C.c_int)
        self.u.GetClassNameW.argtypes=(W.HWND,W.LPWSTR,C.c_int)
        self.u.IsWindow.argtypes=(W.HWND,);self.u.IsWindow.restype=W.BOOL
        self.u.IsWindowVisible.argtypes=(W.HWND,);self.u.IsWindowVisible.restype=W.BOOL
        self.u.GetWindowRect.argtypes=(W.HWND,C.POINTER(RECT));self.u.GetWindowRect.restype=W.BOOL
        self.u.GetWindow.argtypes=(W.HWND,W.UINT);self.u.GetWindow.restype=W.HWND
        self.u.GetAncestor.argtypes=(W.HWND,W.UINT);self.u.GetAncestor.restype=W.HWND
        self.callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        self.u.EnumWindows.argtypes=(self.callback,W.LPARAM)
        self.u.EnumChildWindows.argtypes=(W.HWND,self.callback,W.LPARAM)
        self.handles=[]
        self.version_cache={}

    def token(self, process):
        token=W.HANDLE();require(self.a.OpenProcessToken(process,8,C.byref(token)), 'token_query_failed')
        try:
            size=W.DWORD();elev=W.DWORD()
            require(self.a.GetTokenInformation(token,20,C.byref(elev),4,C.byref(size)), 'elevation_query_failed')
            self.a.GetTokenInformation(token,25,None,0,C.byref(size))
            require(0 < size.value <= 4096,'integrity_token_bound')
            data=C.create_string_buffer(size.value)
            require(self.a.GetTokenInformation(token,25,data,size.value,C.byref(size)),'integrity_query_failed')
            sid=C.c_void_p.from_buffer(data).value
            count=self.a.GetSidSubAuthorityCount(sid)[0]
            require(1<=count<=15,'integrity_SID_bound')
            rid=self.a.GetSidSubAuthority(sid,count-1)[0]
            return {'elevated':bool(elev.value),'integrity_rid':rid}
        finally:self.k.CloseHandle(token)

    def identity(self, handle, pid, parent_pid=None, include_token=True):
        times=[FT() for _ in range(4)]
        require(self.k.GetProcessTimes(handle,*(C.byref(value) for value in times)), 'native_birth_required')
        image=C.create_unicode_buffer(32768);size=W.DWORD(32768)
        require(self.k.QueryFullProcessImageNameW(handle,0,image,C.byref(size)),'native_image_required')
        return {'pid':pid,'birth':str(times[0].high<<32|times[0].low),'image':image.value,
            'parent_pid':parent_pid,**(self.token(handle) if include_token else {})}

    def controller(self):
        return self.identity(self.k.GetCurrentProcess(),os.getpid())

    def inventory(self):
        snapshot=self.k.CreateToolhelp32Snapshot(2,0)
        require(snapshot != C.c_void_p(-1).value,'process_snapshot_failed')
        rows=[];entry=ENTRY();entry.size=C.sizeof(entry)
        try:
            ok=self.k.Process32FirstW(snapshot,C.byref(entry))
            while ok:
                require(len(rows)<4096,'process_snapshot_bound')
                rows.append({'pid':entry.pid,'parent':entry.parent,'name':entry.name})
                ok=self.k.Process32NextW(snapshot,C.byref(entry))
            require(C.get_last_error()==18,'complete_process_snapshot_required')
        finally:self.k.CloseHandle(snapshot)
        purple=[];companions=[]
        for row in rows:
            if row['name'].casefold()in('purple.exe','purpleon.exe'):
                target=purple if row['name'].casefold()=='purple.exe' else companions
                handle=self.k.OpenProcess(0x101000,False,row['pid'])
                if handle:
                    try:
                        info=self.identity(handle,row['pid'],row['parent'],include_token=False)
                        if target is purple:target.append({key:info[key] for key in ('pid','birth','image')})
                        else:target.append({'pid':info['pid'],'birth':info['birth'],'image_basename':Path(info['image']).name,
                            'native_image_verified':True,'app_or_service_classification':'unknown'})
                    except Exception:target.append({'pid':row['pid'],'identity':'unreadable','app_or_service_classification':'unknown'})
                    finally:self.k.CloseHandle(handle)
                else:target.append({'pid':row['pid'],'identity':'unreadable','native_error':C.get_last_error(),'app_or_service_classification':'unknown'})
        return {'lc_count':sum(row['name'].casefold()=='lc.exe' for row in rows),'purple':purple+companions,'purple_apps':purple,
            'purple_app_count':sum(row['name'].casefold()=='purple.exe' for row in rows),'purple_companions':companions,
            'PURPLE_scope':'exact_PURPLE.exe_app_name; companions_separate; not_whole_official_runtime'}

    def source(self):
        path=Path(EXE)
        for part in (path,*path.parents):
            require(not part.is_symlink() and not getattr(part.stat(),'st_file_attributes',0)&0x400,'clone_reparse_refused')
        handle=self.k.CreateFileW(EXE,0x80000000,1,None,3,0x80,None)
        require(handle != C.c_void_p(-1).value,'clone_source_pin_failed');self.handles.append(handle)
        version=C.WinDLL('version',use_last_error=True)
        version.GetFileVersionInfoSizeW.argtypes=(W.LPCWSTR,C.POINTER(W.DWORD));version.GetFileVersionInfoSizeW.restype=W.DWORD
        version.GetFileVersionInfoW.argtypes=(W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p)
        version.VerQueryValueW.argtypes=(C.c_void_p,W.LPCWSTR,C.POINTER(C.c_void_p),C.POINTER(W.UINT))
        unused=W.DWORD();size=version.GetFileVersionInfoSizeW(EXE,C.byref(unused))
        require(0<size<=1048576,'file_version_bound')
        buffer=C.create_string_buffer(size)
        require(version.GetFileVersionInfoW(EXE,0,size,buffer),'file_version_read_failed')
        pointer=C.c_void_p();length=W.UINT()
        require(version.VerQueryValueW(buffer,'\\',C.byref(pointer),C.byref(length)) and length.value>=52,'file_version_root_failed')
        values=C.cast(pointer,C.POINTER(W.DWORD));ms,ls=values[2],values[3]
        row={'path':EXE,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'build':[ms>>16,ms&65535,ls>>16,ls&65535]}
        self.pinned_program_sha256=row['sha256']
        self.pinned_control_sha256=row['sha256'] if row['sha256']==EXE_SHA and tuple(row['build'])==BUILD else None
        return row

    def pin_evidence(self,paths):
        """Internal fixed-gate file set, retained read-share until own Job cleanup."""
        require(type(paths)in(tuple,list) and 0<len(paths)<=112,'fixed_evidence_file_count_bound')
        self.k.GetFileInformationByHandle.argtypes=(W.HANDLE,C.c_void_p)
        for path in paths:
            path=Path(path)
            require(path.is_absolute() and path.resolve(strict=True)==path,'fixed_evidence_canonical_path')
            for part in (path,*path.parents):
                require(not part.is_symlink() and not getattr(part.stat(),'st_file_attributes',0)&0x400,'fixed_evidence_reparse_refused')
            handle=self.k.CreateFileW(str(path),0x80000000,1,None,3,0x200080,None)
            require(handle!=C.c_void_p(-1).value,'fixed_evidence_read_pin_failed')
            self.handles.append(handle)
            info=C.create_string_buffer(52)
            require(self.k.GetFileInformationByHandle(handle,info) and not int.from_bytes(info.raw[:4],'little')&0x400,
                'fixed_evidence_native_reparse_refused')

    def create_suspended(self):
        startup=STARTUP();startup.cb=C.sizeof(startup);startup.flags=1;startup.show=1
        child=PROCESS();command=C.create_unicode_buffer('"'+EXE+'"')
        require(self.k.CreateProcessW(EXE,command,None,None,False,4,None,CLONE,C.byref(startup),C.byref(child)),
            'ordinary_fixed_CreateProcess_failed_no_elevation_retry')
        # Retain creation handles immediately; cleanup does not reopen any PID.
        child.identity={'pid':child.pid,'birth':None,'image':EXE,'parent_pid':os.getpid()}
        child.resumed=False;child.job=None;child.port=None
        child.job_assigned=False
        child.members={};child.member_events=[]
        child.create_return_clock=time.monotonic()
        child.first_capture_clock=child.create_return_clock
        try:child.identity=self.identity(child.process,child.pid,os.getpid())
        except Exception as error:
            forced=bool(self.k.TerminateProcess(child.process,1))
            positive=self.k.WaitForSingleObject(child.process,5000)==0
            self.k.CloseHandle(child.thread);self.k.CloseHandle(child.process)
            error.created_suspended=True
            error.creation_cleanup={'forced_exit':forced,'positive_exit':positive,
                'method':'own_CreateProcess_returned_handle_before_resume'}
            raise
        return child

    def attach_single_process_job(self, child):
        child.job=self.k.CreateJobObjectW(None,None);require(child.job,'owned_job_create_failed')
        limits=LIMIT();limits.basic.flags=0x2008;limits.basic.active_limit=self.process_limit
        require(self.k.SetInformationJobObject(child.job,9,C.byref(limits),C.sizeof(limits)), 'owned_job_limit_failed')
        observed=LIMIT();size=W.DWORD()
        require(self.k.QueryInformationJobObject(child.job,9,C.byref(observed),C.sizeof(observed),C.byref(size))
            and observed.basic.active_limit==self.process_limit and observed.basic.flags==0x2008,
            'owned_job_limits_readback_required')
        child.port=self.k.CreateIoCompletionPort(C.c_void_p(-1),None,0,1);require(child.port,'owned_job_port_failed')
        association=ASSOCIATE(1,child.port)
        require(self.k.SetInformationJobObject(child.job,7,C.byref(association),C.sizeof(association)), 'owned_job_port_association_failed')
        require(self.k.AssignProcessToJobObject(child.job,child.process),'owned_job_assignment_failed_before_resume')
        child.job_assigned=True;child.members[child.pid]=child
        member=W.BOOL()
        require(self.k.IsProcessInJob(child.process,child.job,C.byref(member)) and member.value,
            'owned_child_job_membership_required')

    def resume(self, child):
        require(child.job and self.identity(child.process,child.pid,os.getpid())==child.identity,'resume_exact_owned_identity_required')
        require(self.k.ResumeThread(child.thread)==1,'single_primary_thread_resume_required')
        child.resumed=True

    def exit_code(self, child):
        wait=self.k.WaitForSingleObject(child.process,0)
        require(wait in (0,258),'owned_child_wait_unknown')
        if wait==258:return None
        code=W.DWORD();require(self.k.GetExitCodeProcess(child.process,C.byref(code)),'owned_exit_code_failed')
        return code.value

    def child_token(self, child):
        return self.token(child.process)

    def job_events(self, child):
        events=[]
        if not child.port:return events
        for _ in range(32):
            code=W.DWORD();key=C.c_size_t();pointer=C.c_void_p()
            ok=self.k.GetQueuedCompletionStatus(child.port,C.byref(code),C.byref(key),C.byref(pointer),0)
            if not ok:
                require(C.get_last_error()==258,'owned_job_queue_failed')
                break
            if code.value==3:events.append({'event':'active_process_limit','new_child_runnable':False})
            elif code.value==6 and pointer.value!=child.pid:
                if self.profile=='single':events.append({'event':'unexpected_job_child','new_child_runnable':'unknown'})
                else:self.capture_member(child,pointer.value)
        return events

    def capture_member(self,child,pid):
        require(type(pid)is int and 0<pid<=0xffffffff,'owned_job_PID_notification_required')
        require(not getattr(child,'refused_members',[]),'prior_refused_member_no_new_capture')
        if pid in child.members:return
        require(len(child.members)+len(child.member_events)<16,'owned_job_total_tree_bound_16')
        handle=self.k.OpenProcess(0x101000,False,pid)
        if not handle:
            require(C.get_last_error()==87,'owned_job_member_capture_unknown')
            child.member_events.append({'event':'member_exited_before_identity_capture','native_identity_captured':False})
            require(len(child.member_events)<=16,'owned_job_event_bound')
            return
        public={'pid':pid,'native_identity_captured':False,'job_membership_verified':False,
            'elevated':None,'integrity_rid':None,'token_verified':False}
        stage='job_membership_query'
        try:
            member=W.BOOL()
            require(self.k.IsProcessInJob(handle,child.job,C.byref(member)) and member.value,
                'foreign_process_not_owned_job_member')
            public['job_membership_verified']=True;stage='native_identity_query'
            identity=self.identity(handle,pid,include_token=False)
            exact_path=(identity['image']==EXE and Path(EXE).resolve(strict=True)==Path(EXE))
            public.update({'native_identity_captured':True,'birth':identity['birth'],
                'image_basename':Path(identity['image']).name[:128],'exact_fixed_path':exact_path,
                'known_original_program':identity['image']==r'D:\Lineage Classic\LC.exe',
                'file_version':list(BUILD) if exact_path and getattr(self,'pinned_control_sha256',None)==EXE_SHA else None})
            stage='token_query';token=self.token(handle);identity.update(token)
            public.update({'token_verified':True,'elevated':token['elevated'],'integrity_rid':token['integrity_rid']})
            criteria=[]
            if int(identity['birth'])<int(child.identity['birth']):criteria.append('birth_before_owned_main')
            high_relaunch=(getattr(self,'profile',None)=='online-startup-analysis' and exact_path
                and getattr(self,'pinned_control_sha256',None)==EXE_SHA
                and getattr(self,'online_stock_high_relaunch_authorized',False)is True
                and int(identity['birth'])>int(child.identity['birth'])
                and identity['elevated']is True and identity['integrity_rid']==12288)
            public['high_as_actual_normal_app_relaunch']=high_relaunch and not criteria
            if not high_relaunch:
                if identity['elevated']is not False:criteria.append('elevated_token')
                if identity['integrity_rid']>8192:criteria.append('integrity_above_medium')
            stage='identity_or_elevation_criteria';public['failed_criteria']=criteria
            require(not criteria,'owned_SDK_identity_or_elevation_refused')
            captured_at=time.monotonic()
            child.members[pid]=SimpleNamespace(process=handle,pid=pid,identity=identity,
                create_return_clock=captured_at,first_capture_clock=captured_at,retained_by_job=True,
                high_as_actual_normal_app_relaunch=public['high_as_actual_normal_app_relaunch'],
                exact_fixed_path=exact_path)
        except Exception as error:
            if not public.get('failed_criteria'):public['failed_criteria']=[stage]
            if public['job_membership_verified']:
                # Refusal never makes this member eligible for observation.
                # Retain its read-only handle solely for exact Job exit proof.
                child.refused_members=[SimpleNamespace(process=handle,pid=pid,
                    identity=locals().get('identity'),first_capture_clock=time.monotonic())]
                public['handle_retained_for_owned_cleanup']=True
            else:self.k.CloseHandle(handle)
            error.owned_member_refusal=public
            raise

    def active_job_count(self,child):
        info=ACCOUNTING();size=W.DWORD()
        require(self.k.QueryInformationJobObject(child.job,1,C.byref(info),C.sizeof(info),C.byref(size))
            and info.active<=self.process_limit,'owned_job_accounting_required')
        return info.active

    def member_summary(self,child):
        result=[]
        for member in child.members.values():
            wait=self.k.WaitForSingleObject(member.process,0)
            require(wait in (0,258),'owned_member_wait_unknown')
            result.append({'pid':member.pid,'birth':member.identity['birth'],
                'image_basename':Path(member.identity['image']).name,
                'file_version':self.file_version(member.identity['image']),
                'elevated':member.identity['elevated'],'integrity_rid':member.identity['integrity_rid'],
                'exact_fixed_path':getattr(member,'exact_fixed_path',member.identity['image']==EXE),
                'high_as_actual_normal_app_relaunch':getattr(member,'high_as_actual_normal_app_relaunch',False),
                'first_capture_monotonic_seconds':getattr(member,'first_capture_clock',member.create_return_clock),
                'job_membership_verified':True,'currently_alive':wait==258})
        return result

    def job_metrics(self,child):
        """At most 25 samples per exact fixed LC; first capture is immediate."""
        require(len(child.members)<=16,'owned_metadata_member_bound_16')
        result=[];now=time.monotonic()
        for member in child.members.values():
            if member.identity['image']!=EXE:continue
            wait=self.k.WaitForSingleObject(member.process,0)
            require(wait in (0,258),'owned_metadata_wait_unknown')
            if wait==0:continue
            membership=W.BOOL()
            require(self.k.IsProcessInJob(member.process,child.job,C.byref(membership)) and membership.value,
                'owned_metadata_job_binding_required')
            if getattr(member,'metadata_sample_count',0)>=25 or now<getattr(member,'next_metadata_clock',0):continue
            if not self.retained_alive(member):continue
            try:metrics=self.process_metrics(member)
            except ValueError as error:
                if error.args!=('own_CPU_time_query_failed',):raise
                metrics={'public_metadata_errors':[{'operation':'CPU','winerror':C.get_last_error()}],
                    'module_observation_complete':False}
            member.metadata_sample_count=getattr(member,'metadata_sample_count',0)+1
            member.next_metadata_clock=now+5
            result.append({'owned_member':{'pid':member.pid,'birth':member.identity['birth'],
                'image_basename':'LC.exe','elevated':member.identity['elevated'],
                'integrity_rid':member.identity['integrity_rid'],
                'high_as_actual_normal_app_relaunch':getattr(member,'high_as_actual_normal_app_relaunch',False)},
                'first_capture_monotonic_seconds':getattr(member,'first_capture_clock',member.create_return_clock),
                'sample_monotonic_seconds':now,'member_sample_number':member.metadata_sample_count,**metrics})
            if (getattr(self,'profile',None)in('root-mount-analysis','current-resource-analysis') and member.process==child.process
                    and getattr(self,'root_mount_public_state_factory',None)is not None):
                if not hasattr(child,'root_mount_public_state_reader'):
                    child.root_mount_public_state_reader=self.root_mount_public_state_factory(self,child)
                result[-1]['public_states']=child.root_mount_public_state_reader.sample()
        return result

    def job_windows(self,child):
        result=[]
        for member in child.members.values():
            if self.k.WaitForSingleObject(member.process,0)!=258:continue
            membership=W.BOOL()
            require(self.k.IsProcessInJob(member.process,child.job,C.byref(membership)) and membership.value,
                'owned_window_member_job_binding_required')
            for row in self.windows(member):
                row['owned_member']={'pid':member.pid,'birth':member.identity['birth'],
                    'image_basename':Path(member.identity['image']).name}
                result.append(row)
                if len(result)>=32:return result
        return result

    def retained_alive(self,child):
        if self.k.WaitForSingleObject(child.process,0)==0:return False
        require(self.k.WaitForSingleObject(child.process,0)==258,'retained_owned_wait_unknown')
        current=self.identity(child.process,child.pid,child.identity.get('parent_pid'),include_token=False)
        require(all(current[key]==child.identity[key] for key in ('pid','birth','image','parent_pid')),
            'retained_owned_birth_image_required')
        return True

    def owned_hwnd(self,child,hwnd):
        if not self.retained_alive(child) or not self.u.IsWindow(hwnd):return False
        pid=W.DWORD();thread=self.u.GetWindowThreadProcessId(hwnd,C.byref(pid))
        return bool(thread and pid.value==child.pid)

    def window_relation(self,child,hwnd):
        if not hwnd:return 'none'
        if not self.u.IsWindow(hwnd):return 'closed_or_unknown'
        pid=W.DWORD();thread=self.u.GetWindowThreadProcessId(hwnd,C.byref(pid))
        return 'same_owned_process' if thread and pid.value==child.pid else 'outside_owned_process'

    def window_meta(self,child,hwnd):
        if not self.owned_hwnd(child,hwnd):return None
        errors=[];name=C.create_unicode_buffer(65);C.set_last_error(0)
        if not self.u.GetClassNameW(hwnd,name,65) and C.get_last_error():
            errors.append({'operation':'class','winerror':C.get_last_error()})
        if not self.owned_hwnd(child,hwnd):return None
        visible=bool(self.u.IsWindowVisible(hwnd))
        if not self.owned_hwnd(child,hwnd):return None
        rect=RECT();geometry=None;C.set_last_error(0)
        if self.u.GetWindowRect(hwnd,C.byref(rect)):
            values=[rect.left,rect.top,rect.right,rect.bottom]
            if all(abs(value)<=1000000 for value in values) and rect.right>=rect.left and rect.bottom>=rect.top:
                geometry={'left':rect.left,'top':rect.top,'width':rect.right-rect.left,'height':rect.bottom-rect.top}
        elif C.get_last_error():errors.append({'operation':'geometry','winerror':C.get_last_error()})
        if not self.owned_hwnd(child,hwnd):return None
        owner=self.window_relation(child,self.u.GetWindow(hwnd,4))  # GW_OWNER
        if not self.owned_hwnd(child,hwnd):return None
        parent=self.window_relation(child,self.u.GetAncestor(hwnd,1)) # GA_PARENT, not popup owner
        if not self.owned_hwnd(child,hwnd):return None
        return {'class':name.value,'visible':visible,'geometry':geometry,
            'owner_relation':owner,'parent_relation':parent,'public_metadata_errors':errors}

    def windows(self, child):
        rows=[];errors=[]
        def capture(hwnd,_):
            try:
                pid=W.DWORD();self.u.GetWindowThreadProcessId(hwnd,C.byref(pid))
                if pid.value!=child.pid or len(rows)>=8:return True
                meta=self.window_meta(child,hwnd)
                if meta is None:return True
                title=C.create_unicode_buffer(241)
                if not self.owned_hwnd(child,hwnd):return True
                C.set_last_error(0)
                if not self.u.GetWindowTextW(hwnd,title,241) and C.get_last_error():
                    meta['public_metadata_errors'].append({'operation':'caption','winerror':C.get_last_error()})
                if not self.owned_hwnd(child,hwnd):return True
                row={'hwnd':int(hwnd),'title':title.value,**meta,'children':[],
                    'same_process_child_count':0,'foreign_child_count':0,'child_enumeration_truncated':False}
                def controls(control,_):
                    try:
                        if row['same_process_child_count']+row['foreign_child_count']>=64:
                            row['child_enumeration_truncated']=True;return False
                        if not self.owned_hwnd(child,hwnd):return False
                        if not self.owned_hwnd(child,control):row['foreign_child_count']+=1;return True
                        metadata=self.window_meta(child,control)
                        if metadata is None:return True
                        row['same_process_child_count']+=1
                        item=metadata
                        if metadata['class']=='Static' and self.owned_hwnd(child,control):
                            text=C.create_unicode_buffer(481);self.u.GetWindowTextW(control,text,481)
                            if self.owned_hwnd(child,control):item['text']=text.value
                        row['children'].append(item)
                        return True
                    except Exception as error:errors.append(error);return False
                self.u.EnumChildWindows(hwnd,self.callback(controls),0)
                if self.owned_hwnd(child,hwnd):rows.append(row)
                return True
            except Exception as error:errors.append(error);return False
        self.u.EnumWindows(self.callback(capture),0)
        if errors:raise errors[0]
        return rows

    def file_version(self,path):
        if path in self.version_cache:return self.version_cache[path]
        result=None
        try:
            version=C.WinDLL('version',use_last_error=True)
            version.GetFileVersionInfoSizeW.argtypes=(W.LPCWSTR,C.POINTER(W.DWORD));version.GetFileVersionInfoSizeW.restype=W.DWORD
            version.GetFileVersionInfoW.argtypes=(W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p)
            version.VerQueryValueW.argtypes=(C.c_void_p,W.LPCWSTR,C.POINTER(C.c_void_p),C.POINTER(W.UINT))
            unused=W.DWORD();size=version.GetFileVersionInfoSizeW(path,C.byref(unused))
            if 0<size<=1048576:
                buffer=C.create_string_buffer(size);pointer=C.c_void_p();length=W.UINT()
                if version.GetFileVersionInfoW(path,0,size,buffer) and version.VerQueryValueW(buffer,'\\',C.byref(pointer),C.byref(length)) and length.value>=52:
                    values=C.cast(pointer,C.POINTER(W.DWORD));ms,ls=values[2],values[3]
                    result=[ms>>16,ms&65535,ls>>16,ls&65535]
        except Exception:pass
        self.version_cache[path]=result
        return result

    def process_metrics(self,child):
        if not self.retained_alive(child):return {'process_exited_during_query':True,'module_observation_complete':False}
        times=[FT() for _ in range(4)]
        require(self.k.GetProcessTimes(child.process,*(C.byref(value) for value in times)),'own_CPU_time_query_failed')
        creation=times[0].high<<32|times[0].low
        require(str(creation)==child.identity['birth'],'owned_CPU_birth_required')
        kernel=(times[2].high<<32|times[2].low)/10000000
        user=(times[3].high<<32|times[3].low)/10000000
        result={'elapsed_since_create_return_seconds':round(time.monotonic()-child.create_return_clock,3),
            'native_creation_filetime':str(creation),
            'kernel_cpu_seconds':round(kernel,6),'user_cpu_seconds':round(user,6),'cpu_total_seconds':round(kernel+user,6)}
        # Snapshot scans one transient structure for own PID only. It exports
        # no other process names/PIDs/argv or thread handles.
        snapshot=self.k.CreateToolhelp32Snapshot(2,0);count=None
        if snapshot==C.c_void_p(-1).value:result['thread_query_error']=C.get_last_error()
        else:
            try:
                entry=ENTRY();entry.size=C.sizeof(entry);ok=self.k.Process32FirstW(snapshot,C.byref(entry));visited=0
                while ok and visited<4096:
                    visited+=1
                    if entry.pid==child.pid:count=entry.threads;break
                    ok=self.k.Process32NextW(snapshot,C.byref(entry))
                if count is None and C.get_last_error()!=18:result['thread_query_error']=C.get_last_error()
            finally:self.k.CloseHandle(snapshot)
        result['own_thread_count']=count
        if not self.retained_alive(child):return {'process_exited_during_query':True,'module_observation_complete':False}
        result['module_observation_complete']=False
        modules=[];snapshot=self.k.CreateToolhelp32Snapshot(0x18,child.pid)
        if snapshot==C.c_void_p(-1).value:
            result['module_query_error']=C.get_last_error()
        else:
            try:
                entry=MODULE();entry.size=C.sizeof(entry);ok=self.k.Module32FirstW(snapshot,C.byref(entry))
                while ok and len(modules)<256:
                    require(entry.pid==child.pid,'own_module_snapshot_PID_required')
                    modules.append({'basename':entry.basename[:128],'image_bytes':entry.image_size,
                        'file_version':self.file_version(entry.path)})
                    ok=self.k.Module32NextW(snapshot,C.byref(entry))
                result['modules_truncated']=bool(ok)
                if not ok and C.get_last_error()!=18:result['module_query_error']=C.get_last_error()
                result['module_observation_complete']=not ok and C.get_last_error()==18
            finally:self.k.CloseHandle(snapshot)
        if not self.retained_alive(child):return {'process_exited_during_query':True,'module_observation_complete':False}
        result['modules']=modules
        result['SDK_images_present']=[row['basename'] for row in modules if row['basename'].casefold() in
            {'ncplatformsdk-cpp.dll','purplecommunitysdk.dll','yetiloaderdll.dll','ncgpa.dll','ncdevice.dll','webview2loader.dll'}]
        result['SDK_initialized_proven']=False
        return result

    def cleanup_owned(self, child):
        if self.process_limit==16 and getattr(child,'job_assigned',False):return self.cleanup_owned_job(child)
        forced=False
        try:
            code=self.exit_code(child)
            if code is None:
                current=self.identity(child.process,child.pid,os.getpid(),include_token=False)
                require(all(current[key]==child.identity[key] for key in ('pid','birth','image','parent_pid')),
                    'cleanup_exact_retained_identity_required')
                # No UI input/message. Final OS exit check precedes an exact
                # retained creation-handle forced cleanup on bounded timeout.
                code=self.exit_code(child)
                if code is None:
                    require(self.k.TerminateProcess(child.process,1),'owned_child_cleanup_failed')
                    forced=True;require(self.k.WaitForSingleObject(child.process,5000)==0,'owned_positive_exit_required')
                    code=self.exit_code(child)
            return {'UI_close_requested':False,'forced_exit':forced,'positive_exit':True,
                'exit_code':code,'method':'retained_exact_creation_handle'}
        finally:
            for handle in (child.thread,child.process,child.job,child.port):
                if handle:self.k.CloseHandle(handle)

    def cleanup_owned_job(self,child):
        main_code=self.exit_code(child);forced_main=False;job_forced=False
        deadline=time.monotonic()+5
        captured=[*child.members.values(),*getattr(child,'refused_members',[])]
        before_exit={}
        try:
            active=self.active_job_count(child)
            for member in captured:
                wait=self.k.WaitForSingleObject(member.process,0)
                require(wait in (0,258),'owned_member_cleanup_wait_unknown')
                before_exit[member.process]=wait==0
                if wait==258:
                    membership=W.BOOL()
                    require(self.k.IsProcessInJob(member.process,child.job,C.byref(membership)) and membership.value,
                        'cleanup_owned_job_membership_required')
            if active:
                # Kernel job handle is the retained ownership capability. No PID
                # is reopened for termination and no unrelated process is touched.
                require(self.k.TerminateJobObject(child.job,1),'owned_job_cleanup_failed')
                job_forced=True;forced_main=main_code is None
                while self.active_job_count(child) and time.monotonic()<deadline:time.sleep(.02)
                require(self.active_job_count(child)==0,'owned_job_positive_empty_required')
            # Job accounting can reach zero before process objects signal. Use
            # the retained exact handles and one shared five-second deadline.
            members=[child,*[member for member in captured if member is not child]]
            for member in members:
                remaining=max(0,min(5000,int((deadline-time.monotonic())*1000)))
                require(self.k.WaitForSingleObject(member.process,remaining)==0,
                    'owned_retained_member_positive_exit_required')
            main_code=self.exit_code(child)
            require(main_code is not None,'owned_main_exit_code_required')
            final_members=[]
            for member in members:
                code=self.exit_code(member)
                require(code is not None,'owned_member_final_exit_code_required')
                was_exited=before_exit.get(member.process,False)
                forced_requested=job_forced and not was_exited
                identity=getattr(member,'identity',None) or {}
                first_capture=getattr(member,'first_capture_clock',getattr(member,'create_return_clock',None))
                row={'pid':member.pid,'birth':identity.get('birth'),'image_basename':Path(identity['image']).name
                    if identity.get('image') else None,'exit_code':code,'retained_handle_signaled':True,
                    'natural_exit_observed_before_cleanup':was_exited,
                    'forced_cleanup_requested_while_active':forced_requested,
                    'exit_classification':'forced_cleanup_requested' if forced_requested else 'natural_exit_no_force_requested',
                    'first_capture_monotonic_seconds':first_capture,
                    'elapsed_since_first_capture_seconds':round(time.monotonic()-first_capture,6)
                        if first_capture is not None else None,
                    'elevated':identity.get('elevated'),'integrity_rid':identity.get('integrity_rid'),
                    'high_as_actual_normal_app_relaunch':getattr(member,'high_as_actual_normal_app_relaunch',False)}
                times=[FT() for _ in range(4)]
                if self.k.GetProcessTimes(member.process,*(C.byref(value) for value in times)):
                    creation=times[0].high<<32|times[0].low;exit_time=times[1].high<<32|times[1].low
                    require(identity.get('birth')is None or str(creation)==identity['birth'],
                        'final_retained_member_birth_required')
                    row.update({'native_creation_filetime':str(creation),'native_exit_filetime':str(exit_time),
                        'native_lifetime_seconds':round((exit_time-creation)/10000000,6)
                            if exit_time>=creation and exit_time>0 else None})
                else:row['public_metadata_errors']=[{'operation':'final_times','winerror':C.get_last_error()}]
                final_members.append(row)
            return {'UI_close_requested':False,'forced_exit':forced_main,'job_members_forced_cleanup':job_forced,
                'positive_exit':True,'retained_members_signaled':True,'owned_job_empty':True,'exit_code':main_code,
                'method':'retained_exact_owned_job_handle','retained_member_count':len(captured),
                'final_owned_members':final_members}
        finally:
            for member in captured:
                if member is not child:self.k.CloseHandle(member.process)
            for handle in (child.thread,child.process,child.job,child.port):
                if handle:self.k.CloseHandle(handle)

    def inactive_fixed_process(self,pid,birth,image):
        """Read-only native closure proof; no token query or PID cleanup."""
        handle=self.k.OpenProcess(0x101000,False,pid)
        if not handle:
            require(C.get_last_error()==87,'former_manager_native_absence_unknown')
            return {'pid':pid,'birth':birth,'inactive':True,'proof':'native_PID_absent'}
        try:
            info=self.identity(handle,pid,include_token=False)
            if info['birth']!=birth:
                return {'pid':pid,'birth':birth,'inactive':True,'proof':'native_birth_reused'}
            require(info['image']==image and self.k.WaitForSingleObject(handle,0)==0,
                'former_manager_or_owner_still_live')
            return {'pid':pid,'birth':birth,'inactive':True,'proof':'native_exact_identity_signaled'}
        finally:self.k.CloseHandle(handle)

    def producer(self, pid, birth, image):
        handle=self.k.OpenProcess(0x101000,False,pid);require(handle,'admin_producer_query_failed')
        try:
            info=self.identity(handle,pid,include_token=False)
            require(info['birth']==birth and info['image']==image
                and self.k.WaitForSingleObject(handle,0)==258,'current_admin_producer_identity_required')
            proof={'pid':pid,'birth':birth,'live':True,'image_verified':True,
                'elevation_token_verified':False,'privilege_proof':'bound_actual_Arm_receipt_and_fresh_full_policy'}
            try:
                token=self.token(handle)
                require(token['elevated'] is True,'actual_arm_producer_elevation_disagrees')
                proof.update({'elevation_token_verified':True,'elevated':True})
            except OSError:pass
            except ValueError as error:
                if error.args==('actual_arm_producer_elevation_disagrees',):raise
                # Limited query may identify an elevated host while its token
                # DACL denies a medium observer; do not request higher privilege.
                proof['elevation_token_error']=error.args[0]
            return proof
        finally:self.k.CloseHandle(handle)

    def close(self):
        for handle in self.handles:self.k.CloseHandle(handle)
        self.handles=[]
