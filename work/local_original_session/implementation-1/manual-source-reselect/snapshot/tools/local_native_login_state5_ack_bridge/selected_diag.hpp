#pragma once
#include "diagnostic.hpp"
namespace selected_diagnostic {
enum Check:int {NotObserved=0,Fail=1,Pass=2};
enum ExecReason:int {ExecNotObserved=0,SpanInvalid=1,QueryFailed=2,NotCommitted=3,Guard=4,NoAccess=5,RegionRange=6,Protection=7,ExecPass=8};
struct CreateQuery {
    bool observed=false,region_observed=false,span_in_region=false,allocation_matches=false;
    int reason=0;SIZE_T returned=0;DWORD error=0,state=0,protect=0,type=0;
};
using QueryFn=SIZE_T(WINAPI*)(LPCVOID,PMEMORY_BASIC_INFORMATION,SIZE_T);
inline bool create_executable(uintptr_t p,size_t n,uintptr_t verified_base,CreateQuery& q,QueryFn query=VirtualQuery) noexcept {
    const DWORD before=GetLastError();bool result=false;
    if(!n || p>UINTPTR_MAX-n){q.reason=SpanInvalid;SetLastError(before);return false;}
    MEMORY_BASIC_INFORMATION m{};q.observed=true;
    SetLastError(before);q.returned=query(reinterpret_cast<void*>(p),&m,sizeof(m));
    if(!q.returned){q.error=GetLastError();q.reason=QueryFailed;SetLastError(before);return false;}
    q.region_observed=true;q.state=m.State;q.protect=m.Protect;q.type=m.Type;
    const auto start=reinterpret_cast<uintptr_t>(m.BaseAddress);
    q.span_in_region=start<=UINTPTR_MAX-m.RegionSize && p+n<=start+m.RegionSize;
    q.allocation_matches=reinterpret_cast<uintptr_t>(m.AllocationBase)==verified_base;
    if(m.State!=MEM_COMMIT)q.reason=NotCommitted;
    else if(m.Protect&PAGE_GUARD)q.reason=Guard;
    else if(m.Protect&PAGE_NOACCESS)q.reason=NoAccess;
    else if(!q.span_in_region)q.reason=RegionRange;
    else {const DWORD protect=m.Protect&0xff;result=protect==PAGE_EXECUTE_READ || protect==PAGE_EXECUTE_READWRITE || protect==PAGE_EXECUTE_WRITECOPY;q.reason=result?ExecPass:Protection;}
    SetLastError(before);return result;
}
struct Eligibility {
    CreateQuery create_query;bool cached=false;int context=0,base=0,create_exec=0,create_copy=0,create_match=0,setter_exec=0,setter_copy=0,setter_match=0;
};
struct Selected {
    bool probe_bound=false,cpp_entered=false,original_return_confirmed=false,original_exception_observed=false;
    bool own_enqueue_attempted=false,selected_task_registered=false,own_flags_observed=false;
    uint32_t reason=1,stage=0;int failed_record=-1,qualified=0,begin=0,own_inputs_ready=0,genuine_pair_matches_argument=0;Eligibility eligibility;
};
inline std::atomic<bool> selected_claim{false},connect_claim{false};
using ContextFn=bool(*)(forward_diagnostic::Context&) noexcept;
using OutputFn=void(*)(const wchar_t*,const char*,int) noexcept;
#ifdef OWN_SELECTED_HOST_TEST
extern ContextFn test_context;extern OutputFn test_output;
inline bool valid_context(forward_diagnostic::Context& c) noexcept {return test_context(c);}
#else
inline bool valid_context(forward_diagnostic::Context& c) noexcept {return forward_diagnostic::context(c);}
#endif
inline void output(const forward_diagnostic::Context& c,const wchar_t* leaf,const char* text,int size) noexcept {
#ifdef OWN_SELECTED_HOST_TEST
    (void)c;test_output(leaf,text,size);
#else
    wchar_t path[600]{};swprintf_s(path,L"%s\\%s",c.directory,leaf);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file!=INVALID_HANDLE_VALUE){DWORD n=0;if(size>0)WriteFile(file,text,static_cast<DWORD>(size),&n,nullptr);CloseHandle(file);}
#endif
}
// These two claims are independent of all five CP04 first-Close counters.
inline void selected(const Selected& s) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context c{};
    if(valid_context(c)) {
        bool expected=false;if(selected_claim.compare_exchange_strong(expected,true)) {
            char text[4096]{};const auto& e=s.eligibility;const auto& q=e.create_query;
            char returned[32]="null",error[32]="null",state[32]="null",protect[32]="null",type[32]="null";
            if(q.observed)sprintf_s(returned,"%llu",static_cast<unsigned long long>(q.returned));
            if(q.observed && !q.returned)sprintf_s(error,"%lu",q.error);
            if(q.region_observed){sprintf_s(state,"%lu",q.state);sprintf_s(protect,"%lu",q.protect);sprintf_s(type,"%lu",q.type);}
            const int size=sprintf_s(text,"{\"schema\":\"own-selected-boundary-v2\",\"event\":\"SELECTED_BOUNDARY\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"record_id\":2,\"probe_bound\":%s,\"cpp_entered\":%s,\"binding_reason\":%u,\"binding_stage\":%u,\"failed_record_id\":%d,\"eligibility_cached_ready\":%s,\"context\":%d,\"base\":%d,\"create_exec\":%d,\"create_copy\":%d,\"create_match\":%d,\"setter_exec\":%d,\"setter_copy\":%d,\"setter_match\":%d,\"qualified\":%d,\"begin\":%d,\"own_inputs_ready\":%d,\"genuine_pair_matches_argument\":%d,\"original_return_confirmed\":%s,\"original_exception_observed\":%s,\"own_enqueue_attempted\":%s,\"selected_task_registered\":%s,\"create_query_observed\":%s,\"create_exec_reason\":%d,\"create_query_returned_size\":%s,\"create_query_failure_error\":%s,\"create_memory_state\":%s,\"create_memory_protect\":%s,\"create_memory_type\":%s,\"create_span_in_region\":%s,\"create_allocation_base_matches_verified_base\":%s}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,s.probe_bound?"true":"false",s.cpp_entered?"true":"false",s.reason,s.stage,s.failed_record,e.cached?"true":"false",e.context,e.base,e.create_exec,e.create_copy,e.create_match,e.setter_exec,e.setter_copy,e.setter_match,s.qualified,s.begin,s.own_inputs_ready,s.genuine_pair_matches_argument,s.original_return_confirmed?"true":"false",s.original_exception_observed?"true":"false",s.own_flags_observed?(s.own_enqueue_attempted?"true":"false"):"null",s.own_flags_observed?(s.selected_task_registered?"true":"false"):"null",q.observed?"true":"false",q.reason,returned,error,state,protect,type,q.region_observed?(q.span_in_region?"true":"false"):"null",q.region_observed?(q.allocation_matches?"true":"false"):"null");
            output(c,L"selected-boundary.json",text,size);
        }
    }
    SetLastError(before);
}
inline void connect(bool original) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context c{};
    if(valid_context(c)) {
        bool expected=false;if(connect_claim.compare_exchange_strong(expected,true)) {
            char text[512]{};const int size=sprintf_s(text,"{\"schema\":\"own-selected-connect-v1\",\"event\":\"OWN_SELECTED_CONNECT_RETURN\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"record_id\":0,\"original_bool\":%s,\"actual_own_capture_confirmed\":true}\n",c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,original?"true":"false");
            output(c,L"own-connect-result.json",text,size);
        }
    }
    SetLastError(before);
}
inline void probe_refused(uint32_t record,BindReason reason,uint32_t stage,int failed) noexcept {
    if(record!=2)return;Selected s;s.reason=static_cast<unsigned>(reason);s.stage=stage;s.failed_record=failed;selected(s);
}
inline bool code_stage(uintptr_t p,const unsigned char* expected,size_t n,int* executable,int* copied,int* matched,CodeFn code=Executable,CopyFn copy=SafeCopy) noexcept {
    unsigned char bytes[32]{};if(n>32)return false;
    const bool e=code(p,n);if(executable)*executable=e?Pass:Fail;if(!e)return false;
    const bool c=copy(bytes,reinterpret_cast<void*>(p),n);if(copied)*copied=c?Pass:Fail;if(!c)return false;
    const bool m=!memcmp(bytes,expected,n);if(matched)*matched=m?Pass:Fail;return m;
}
inline bool create_code_stage(uintptr_t p,const unsigned char* expected,size_t n,uintptr_t base,Eligibility* observed,QueryFn query=VirtualQuery,CopyFn copy=SafeCopy) noexcept {
    if(!observed)return code_stage(p,expected,n,nullptr,nullptr,nullptr);
    unsigned char bytes[32]{};if(n>32)return false;
    const bool e=create_executable(p,n,base,observed->create_query,query);observed->create_exec=e?Pass:Fail;if(!e)return false;
    const bool c=copy(bytes,reinterpret_cast<void*>(p),n);observed->create_copy=c?Pass:Fail;if(!c)return false;
    const bool m=!memcmp(bytes,expected,n);observed->create_match=m?Pass:Fail;return m;
}

inline std::atomic<bool> dto_claim{false};
inline void dto(const Eligibility& e,bool ready) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context c{};
    if(valid_context(c)) {
        bool expected=false;if(dto_claim.compare_exchange_strong(expected,true)) {
            const auto& q=e.create_query;char text[2048]{};
            char returned[32]="null",error[32]="null",state[32]="null",protect[32]="null",type[32]="null";
            if(q.observed)sprintf_s(returned,"%llu",static_cast<unsigned long long>(q.returned));
            if(q.observed && !q.returned)sprintf_s(error,"%lu",q.error);
            if(q.region_observed){sprintf_s(state,"%lu",q.state);sprintf_s(protect,"%lu",q.protect);sprintf_s(type,"%lu",q.type);}
            const int size=sprintf_s(text,"{\"schema\":\"own-dto-code-v1\",\"event\":\"OWN_DTO_CODE_CHECK\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"context\":%d,\"base\":%d,\"create_exec\":%d,\"create_copy\":%d,\"create_match\":%d,\"setter_exec\":%d,\"setter_copy\":%d,\"setter_match\":%d,\"dto_code_ready\":%s,\"create_query_observed\":%s,\"create_exec_reason\":%d,\"create_query_returned_size\":%s,\"create_query_failure_error\":%s,\"create_memory_state\":%s,\"create_memory_protect\":%s,\"create_memory_type\":%s,\"create_span_in_region\":%s,\"create_allocation_base_matches_verified_base\":%s}\n",c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,e.context,e.base,e.create_exec,e.create_copy,e.create_match,e.setter_exec,e.setter_copy,e.setter_match,ready?"true":"false",q.observed?"true":"false",q.reason,returned,error,state,protect,type,q.region_observed?(q.span_in_region?"true":"false"):"null",q.region_observed?(q.allocation_matches?"true":"false"):"null");
            output(c,L"dto-readiness.json",text,size);
        }
    }
    SetLastError(before);
}

}
