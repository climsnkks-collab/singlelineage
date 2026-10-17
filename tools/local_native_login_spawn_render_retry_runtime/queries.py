"""Bounded alternate image APIs on supplied existing handles; never opens one."""
import ctypes as C
from ctypes import wintypes as W

BOUND=32768

class Queries:
    def __init__(self, owner):
        self.owner=owner
        self.k=owner.k

    def function(self,name,args,result):
        fn=getattr(self.k,name)
        fn.argtypes=args;fn.restype=result
        return fn

    def state(self,process,job):
        getpid=self.function('GetProcessId',(W.HANDLE,),W.DWORD)
        C.set_last_error(0);pid=getpid(process);pid_error=C.get_last_error()
        FT=self.k.GetProcessTimes.argtypes[1]._type_
        times=[FT() for _ in range(4)]
        C.set_last_error(0);okay=bool(self.k.GetProcessTimes(process,*(C.byref(t) for t in times)));birth_error=C.get_last_error()
        birth=str(times[0].high<<32|times[0].low) if okay else None
        C.set_last_error(0);wait=self.k.WaitForSingleObject(process,0);wait_error=C.get_last_error()
        inside=W.BOOL()
        C.set_last_error(0);job_ok=bool(self.k.IsProcessInJob(process,job,C.byref(inside)));job_error=C.get_last_error()
        return {'pid':pid if pid else None,'birth':birth,'wait':wait,'job_member':bool(inside.value) if job_ok else None,
                'pid_succeeded':bool(pid),'birth_succeeded':okay,'job_succeeded':job_ok,
                'pid_winerror':pid_error,'birth_winerror':birth_error,'wait_winerror':wait_error,'job_winerror':job_error}

    @staticmethod
    def name_result(buffer,count,okay,error):
        valid=bool(okay and type(count) is int and 0<count<BOUND and buffer[count]=='\x00'
                   and all(buffer[i]!='\x00' for i in range(count)))
        return {'BOOL':bool(okay),'winerror':error,'complete':valid,'name':buffer[:count] if valid else None}

    def file_native_path(self,handle):
        fn=self.function('GetFinalPathNameByHandleW',(W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD),W.DWORD)
        buffer=C.create_unicode_buffer(BOUND)
        C.set_last_error(0);count=int(fn(handle,buffer,BOUND,2));error=C.get_last_error()
        return self.name_result(buffer,count,count>0,error)

    def image_native(self,handle,method):
        buffer=C.create_unicode_buffer(BOUND)
        if method=='flags1':
            size=W.DWORD(BOUND)
            C.set_last_error(0);okay=bool(self.k.QueryFullProcessImageNameW(handle,1,buffer,C.byref(size)));error=C.get_last_error()
            return self.name_result(buffer,int(size.value),okay,error)
        if method!='k32':raise ValueError('EXACT_ALTERNATE_METHOD_REQUIRED')
        fn=self.function('K32GetProcessImageFileNameW',(W.HANDLE,W.LPWSTR,W.DWORD),W.DWORD)
        C.set_last_error(0);count=int(fn(handle,buffer,BOUND));error=C.get_last_error()
        return self.name_result(buffer,count,count>0,error)
