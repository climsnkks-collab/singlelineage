"""CP73 diagnostic-only frozen creation binding. A success cannot admit a peer."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Binding:
    owner:object
    main:object
    member:object
    process:object
    job:object
    pid:int
    identity:tuple
    program_sha256:str
    program_file:object

def identity_tuple(member):
    return tuple(member.identity.get(k) for k in ('pid','birth','image','parent_pid','elevated','integrity_rid'))

def unchanged(b):
    return bool(b.process and b.job and b.main.members.get(b.pid) is b.member and b.member is not b.main
        and b.member.process==b.process and b.member.pid==b.pid and b.main.job==b.job
        and b.owner._identity_failure_main() is b.main and identity_tuple(b.member)==b.identity
        and getattr(b.member,'retained_by_job',False) is True and getattr(b.member,'exact_fixed_path',False) is True
        and b.identity[4] is False and type(b.identity[5]) is int and b.identity[5]<=8192
        and b.owner.pinned_program_sha256==b.program_sha256)

def path_form(name):
    if name is None:return 'UNAVAILABLE'
    if not isinstance(name,str) or not name or '\x00' in name:return 'MALFORMED'
    if name.startswith('\\Device\\'):return 'NATIVE_DEVICE'
    if name.startswith('\\\\') or (len(name)>1 and name[1]==':'):return 'DOS_OR_UNC'
    return 'OTHER'

def native_path(name):
    if path_form(name)!='NATIVE_DEVICE' or len(name)>=32768 or '/' in name:return False
    parts=name[1:].split('\\')
    return (len(parts)>=3 and parts[0]=='Device' and parts[1].startswith('HarddiskVolume')
        and parts[1][len('HarddiskVolume'):].isdigit() and int(parts[1][len('HarddiskVolume'):])>0
        and all(p not in ('','.','..') for p in parts))

def public_query(q):
    return {'BOOL':q['BOOL'],'winerror':q['winerror'],'complete':q['complete'],'returned_path_form':path_form(q['name'])}

class Diagnostic:
    def __init__(self,binding,queries):self.b=binding;self.q=queries;self.attempted=False
    def run(self,original_error):
        row={'schema':'retained-native-image-alternate-diagnostic-v2','status':'UNKNOWN','reason':'UNASSESSED',
             'original_winerror':original_error,'attempts':[],'query_used_for_admission':False,'cache_used_for_admission':False,
             'new_PID_open':False,'VM_RPM':False,'privilege_change':False,'raw_image_paths_saved':False,
             'same_exact_retained_binding_before':False,'same_exact_retained_binding_after':False,
             'pinned_program_file_bound':False,'exact_native_file_path_equality':None}
        if self.attempted:row['reason']='SINGLE_DIAGNOSTIC_ALREADY_SPENT';return row
        self.attempted=True
        b,q=self.b,self.q
        try:
            row['same_exact_retained_binding_before']=unchanged(b)
            if original_error!=5 or not row['same_exact_retained_binding_before']:
                row['reason']='EXACT_ACTIVE_CAPTURED_BINDING_REQUIRED';return row
            required={'pid':b.pid,'birth':b.identity[1],'wait':258,'job_member':True}
            before=q.state(b.process,b.job);row['before']=before
            if any(before.get(k)!=v for k,v in required.items()):
                row['reason']='ACTIVE_BIRTH_PID_JOB_BEFORE_REQUIRED';return row
            bound=bool(b.program_file and getattr(b.owner,'_pinned_program_handle',None)==b.program_file and b.program_file in b.owner.handles)
            row['pinned_program_file_bound']=bound
            expected=None
            if bound:
                file_before=q.file_native_path(b.program_file);row['file_before']=public_query(file_before)
                if file_before['BOOL'] and file_before['complete'] and native_path(file_before['name']):expected=file_before['name']
            observed=None
            for method in ('flags1','k32'):
                result=q.image_native(b.process,method)
                row['attempts'].append(dict(method=method,**public_query(result)))
                if result['BOOL']:
                    observed=result['name'] if result['complete'] and native_path(result['name']) else None
                    break  # A success with malformed/mismatched output never falls through.
            after=q.state(b.process,b.job);row['after']=after
            row['same_exact_retained_binding_after']=unchanged(b)
            file_unchanged=False
            if bound and getattr(b.owner,'_pinned_program_handle',None)==b.program_file and b.program_file in b.owner.handles:
                file_after=q.file_native_path(b.program_file);row['file_after']=public_query(file_after)
                file_unchanged=bool(expected is not None and file_after['BOOL'] and file_after['complete'] and file_after['name']==expected)
            if any(after.get(k)!=v for k,v in required.items()) or not row['same_exact_retained_binding_after']:
                row['reason']='ACTIVE_BIRTH_PID_JOB_AFTER_REQUIRED'
            elif expected is None or not file_unchanged:row['reason']='PINNED_PROGRAM_NATIVE_PATH_UNKNOWN_OR_CHANGED'
            elif observed is None:row['reason']='ALTERNATE_IMAGE_QUERY_UNKNOWN'
            else:
                row['exact_native_file_path_equality']=observed==expected
                row['reason']='EXACT_NATIVE_FILE_PATH_SAME_RETAINED_ACTIVE_HANDLE' if observed==expected else 'ALTERNATE_IMAGE_PATH_MISMATCH'
                if observed==expected:row['status']='OBSERVED_CURRENT_NATIVE_IMAGE_ALT'
        except BaseException as error:
            row['reason']='DIAGNOSTIC_OPERATION_FAILED';row['exception_type']=type(error).__name__[:128]
        return row
