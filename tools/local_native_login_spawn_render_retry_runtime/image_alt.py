"""Add bounded alternate query diagnostics; preserve CP68 first/call2 refusal."""
import ast,ctypes as C,hashlib,importlib.util,json,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location('_cp73_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name]=module;spec.loader.exec_module(module);return module
parent=load('call2_identity');policy=load('diagnostic');adapter=load('queries')

class Recorder(parent.Recorder):
    def __init__(self,work):
        super().__init__(work);self.bindings={};self.alternate=None;self.alternate_attempted=False

    def capture_binding(self,owner,main,member):
        # Source-bound insert after the sole successful capture assignment,
        # before its callbacks. Capture/refused handles cannot create a binding.
        saved=C.get_last_error()
        try:
            b=policy.Binding(owner,main,member,member.process,main.job,member.pid,
                policy.identity_tuple(member),owner.pinned_program_sha256,getattr(owner,'_pinned_program_handle',None))
            if policy.unchanged(b):self.bindings[id(member)]=b
        except BaseException:
            self.secondary.append('CP73_CAPTURE_BINDING_UNKNOWN')
        finally:C.set_last_error(saved)

    def bind(self,owner,main_provider):
        super().bind(owner,main_provider)
        raw=parent.base.WINDOWS.read_bytes()
        parent.need(hashlib.sha256(raw).hexdigest()==parent.base.WINDOWS_SHA,'EXACT_CP73_ORIGINAL_NATIVE_SOURCE')
        cls=next(n for n in ast.parse(raw,str(parent.base.WINDOWS)).body if isinstance(n,ast.ClassDef) and n.name=='Native')
        source=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='source')
        ns=dict(owner.source.__func__.__globals__)
        original_module=compile(raw,str(parent.base.WINDOWS),'exec')
        original_class=next(c for c in original_module.co_consts if isinstance(c,types.CodeType) and c.co_name=='Native')
        expected=next(c for c in original_class.co_consts if isinstance(c,types.CodeType) and c.co_name=='source')
        actual=owner.source.__func__.__code__
        parent.need(Path(actual.co_filename)==parent.base.WINDOWS and actual.co_code==expected.co_code and actual.co_consts==expected.co_consts,
                    'EXACT_CP73_PROGRAM_PIN_SOURCE_REQUIRED')
        anchor=next(i for i,n in enumerate(source.body) if isinstance(n,ast.Expr) and ast.unparse(n)=='self.handles.append(handle)')
        source.body.insert(anchor+1,ast.parse('self._pinned_program_handle=handle').body[0])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[source],type_ignores=[])),str(parent.base.WINDOWS),'exec'),ns)
        owner.source=types.MethodType(ns['source'],owner)
        capture=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='capture_member')
        trial=next(n for n in ast.walk(capture) if isinstance(n,ast.Try))
        at=next(i for i,n in enumerate(trial.body) if isinstance(n,ast.Assign) and ast.unparse(n)=='identity = self.identity(handle, pid, include_token=False)')
        trial.body[at:at+1]=ast.parse("""_previous_capture=getattr(self,'_identity_failure_capture',None)
self._identity_failure_capture=(handle,pid,child)
try:
    identity=self.identity(handle,pid,include_token=False)
finally:
    self._identity_failure_capture=_previous_capture
""").body
        at=next(i for i,n in enumerate(trial.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and ast.unparse(t)=='child.members[pid]' for t in n.targets))
        trial.body.insert(at+1,ast.parse('_image_alt_capture(self,child,child.members[pid])').body[0])
        ns=dict(owner.identity.__func__.__globals__);ns['_image_alt_capture']=self.capture_binding
        exec(compile(ast.fix_missing_locations(ast.Module(body=[capture],type_ignores=[])),str(parent.base.WINDOWS),'exec'),ns)
        owner.capture_member=types.MethodType(ns['capture_member'],owner)
        return owner

    def failure(self,owner,handle,pid,times,winerror,started,finished):
        try:
            returned=super().failure(owner,handle,pid,times,winerror,started,finished)
            if not self.alternate_attempted and winerror==5:
                main,member,role=self.match(owner,handle,pid)
                b=self.bindings.get(id(member))
                if b is not None and b.owner is owner and b.main is main and b.member is member and b.process==handle and b.pid==pid and role=='PREVIOUSLY_RETAINED_MEMBER':
                    self.alternate_attempted=True
                    self.alternate=policy.Diagnostic(b,adapter.Queries(owner)).run(winerror)
                    self.alternate['original_call_id']=returned[0]['call_id']
            return returned
        except BaseException as error:
            # The base identity wrapper already isolates diagnostic errors;
            # preserve its return even if only alternate diagnostics fail.
            if 'returned' not in locals():raise
            self.secondary.append('CP73_ALTERNATE_DIAGNOSTIC_FAILED')
            return returned
        finally:C.set_last_error(winerror)

    def finish(self,report):
        super().finish(report)
        if self.alternate is not None:
            raw=(json.dumps(self.alternate,indent=2)+'\n').encode('utf-8')
            parent.need(len(raw)<=16384,'CP73_ALTERNATE_PUBLIC_BOUND')
            with (self.work/'identity-image-alternate.json').open('xb') as stream:stream.write(raw)
            report['identity_image_alternate_public_record']=self.alternate

def install_runtime_factory(core):
    original=core.identity.Recorder
    parent.need(Path(original.failure.__code__.co_filename)==parent.PARENT
        and original.failure.__code__.co_code==parent.base.Recorder.failure.__code__.co_code,'EXACT_FROZEN_RUNTIME_IDENTITY_RECORDER')
    core.identity.Recorder=Recorder
    return original
