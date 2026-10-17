#pragma once
// Optional diagnostic successor only. No command lines, tokens, target arguments
// or raw addresses are persisted. Included after forward_diagnostic is defined.
#include <intrin.h>
#include <cstdio>
#include <cwchar>
namespace owned_lifecycle {
static decltype(&CreateProcessW) real_CreateProcessW=nullptr;
static decltype(&CreateProcessA) real_CreateProcessA=nullptr;
static decltype(&ExitProcess) real_ExitProcess=nullptr;
static volatile LONG installed=0,launch_claims=0,exit_claim=0;
static unsigned physical_count=3;
#ifdef OWN_LIFECYCLE_INTEGRITY
static decltype(&CreateProcessW) real_KB_CreateProcessW=nullptr;
static decltype(&CreateProcessA) real_KB_CreateProcessA=nullptr;
static decltype(&ExitProcess) real_KB_ExitProcess=nullptr;
static decltype(&TerminateProcess) real_TerminateProcess=nullptr,real_KB_TerminateProcess=nullptr;
static volatile LONG64 entered[8]{},statistics[7]{};
static unsigned coalesced_mask=0;
#ifdef OWN_LIFECYCLE_DETAILS
static HMODULE known_kernel32=nullptr,known_kernelbase=nullptr,known_user32=nullptr;
inline void RememberUserModule(HMODULE module) noexcept {known_user32=module;}
#endif
#define OWN_LIFE_ENTER(index) InterlockedIncrement64(&entered[index])
#define OWN_LIFE_STAT(index) InterlockedIncrement64(&statistics[index])
#else
#define OWN_LIFE_ENTER(index) ((void)0)
#define OWN_LIFE_STAT(index) ((void)0)
#endif
static thread_local bool writing=false;
struct Caller {bool known=false;uint64_t rva=0;char module[129]{};};
struct Event {unsigned kind=0;const void* caller=nullptr;Caller caller_info{};DWORD flags=0,exit_code=0,error=0;BOOL result=FALSE;DWORD child_pid=0;uint64_t child_birth=0,filetime=0;bool before_call=false,target_known=false,target_current=false;};
inline int Claim(unsigned kind) noexcept {
    if(kind==3)return InterlockedCompareExchange(&exit_claim,1,0)==0?15:-1;
    LONG n=InterlockedCompareExchange(&launch_claims,0,0);
    while(n<15){const LONG observed=InterlockedCompareExchange(&launch_claims,n+1,n);if(observed==n)return static_cast<int>(n);n=observed;}
    return -1;
}
inline uint64_t Time() noexcept {FILETIME t{};GetSystemTimeAsFileTime(&t);return (uint64_t(t.dwHighDateTime)<<32)|t.dwLowDateTime;}
inline void Basename(const wchar_t* path,char (&out)[129]) noexcept {
    const wchar_t* name=path;for(const wchar_t* p=path;*p;++p)if(*p==L'\\'||*p==L'/')name=p+1;
    unsigned n=0;for(;*name&&n<128;++name,++n){const wchar_t c=*name;
        out[n]=(c>=L'a'&&c<=L'z')||(c>=L'A'&&c<=L'Z')||(c>=L'0'&&c<=L'9')||c==L'.'||c==L'_'||c==L'-'?static_cast<char>(c):'_';}
    out[n]=0;
}
inline Caller CallerOf(const void* address) noexcept {
    Caller out;MEMORY_BASIC_INFORMATION info{};
    if(VirtualQuery(address,&info,sizeof(info))!=sizeof(info)||info.Type!=MEM_IMAGE||info.State!=MEM_COMMIT||
       !info.AllocationBase||reinterpret_cast<uintptr_t>(address)<reinterpret_cast<uintptr_t>(info.AllocationBase))return out;
    wchar_t path[1024]{};const DWORD n=GetModuleFileNameW(static_cast<HMODULE>(info.AllocationBase),path,1024);
    if(!n||n>=1024)return out;Basename(path,out.module);if(!out.module[0])return out;
    out.known=true;out.rva=reinterpret_cast<uintptr_t>(address)-reinterpret_cast<uintptr_t>(info.AllocationBase);return out;
}
inline void Child(Event& event,const PROCESS_INFORMATION* result) noexcept {
    if(!event.result||!result)return;
    __try {event.child_pid=result->dwProcessId;FILETIME birth{},end{},kernel{},user{};
        if(result->hProcess && GetProcessTimes(result->hProcess,&birth,&end,&kernel,&user))
            event.child_birth=(uint64_t(birth.dwHighDateTime)<<32)|birth.dwLowDateTime;
    } __except(EXCEPTION_EXECUTE_HANDLER){event.child_pid=0;event.child_birth=0;}
}
inline void Write(const Event& event) noexcept {
    OWN_LIFE_STAT(0);if(writing){OWN_LIFE_STAT(1);return;}writing=true;
    forward_diagnostic::Context context{};
    if(forward_diagnostic::context(context)){
        const int slot=Claim(event.kind==3||event.kind==6||(event.kind>=7&&event.before_call)?3u:1u);
        if(slot>=0){const auto& caller=event.caller_info;char text[1152]{};wchar_t path[600]{};
            swprintf_s(path,L"%s\\lifecycle-%02d.json",context.directory,slot);
            const char* api=event.kind==1||event.kind==4?"CreateProcessW":event.kind==2||event.kind==5?"CreateProcessA":event.kind>=7?"TerminateProcess":"ExitProcess";
            char extra[256]{};
#ifdef OWN_LIFECYCLE_INTEGRITY
            const unsigned index=event.kind-1;
            const bool aliased=(index==0&&(coalesced_mask&(1u<<3)))||(index==1&&(coalesced_mask&(1u<<4)))||
                (index==2&&(coalesced_mask&(1u<<5)))||(index==6&&(coalesced_mask&(1u<<7)));
            const char* family=aliased?"shared_alias":index>=3&&index<=5||index==7?"kernelbase":"kernel32";
            sprintf_s(extra,",\"api_export_family\":\"%s\",\"return_observed\":%s,\"target_is_current\":%s",family,
                event.before_call?"false":"true",event.target_known?(event.target_current?"true":"false"):"null");
#endif
            const int length=sprintf_s(text,"{\"schema\":\"own-lifecycle-diagnostic-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"slot\":%d,\"api\":\"%s\",\"filetime\":%llu,\"thread_id\":%lu,\"caller_image_known\":%s,\"caller_module\":\"%s\",\"caller_rva\":%llu,\"result\":%s,\"last_error\":%lu,\"exit_code\":%lu,\"creation_flags\":%lu,\"creator_pid\":%lu,\"created_pid\":%lu,\"created_birth\":%llu,\"lifecycle_installed\":%s,\"lifecycle_hooks_count\":%u%s}\n",
                context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,slot,api,
                static_cast<unsigned long long>(event.filetime),GetCurrentThreadId(),caller.known?"true":"false",caller.module,
                static_cast<unsigned long long>(caller.rva),event.result?"true":"false",event.error,event.exit_code,event.flags,
                context.pid,event.child_pid,static_cast<unsigned long long>(event.child_birth),installed?"true":"false",physical_count,extra);
            const HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(file!=INVALID_HANDLE_VALUE){DWORD written=0;
                bool complete=false;if(length>0&&WriteFile(file,text,static_cast<DWORD>(length),&written,nullptr)&&written==static_cast<DWORD>(length))complete=FlushFileBuffers(file)!=FALSE;
                const BOOL closed=CloseHandle(file);if(complete&&closed){OWN_LIFE_STAT(4);}else{OWN_LIFE_STAT(5);}}
            else{OWN_LIFE_STAT(5);}
        }else{OWN_LIFE_STAT(3);}
    }else{OWN_LIFE_STAT(2);}
    writing=false;
}
using Sink=void(*)(const Event&) noexcept;
static Sink sink=Write;
inline void Emit(const Event& event) noexcept {
    __try {sink(event);} __except(EXCEPTION_EXECUTE_HANDLER){OWN_LIFE_STAT(6);writing=false;}
}
__declspec(noinline) inline BOOL WINAPI create_w(LPCWSTR app,LPWSTR command,LPSECURITY_ATTRIBUTES process,LPSECURITY_ATTRIBUTES thread,
        BOOL inherit,DWORD flags,LPVOID environment,LPCWSTR directory,LPSTARTUPINFOW startup,LPPROCESS_INFORMATION output) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(0);Event event;event.kind=1;event.caller=_ReturnAddress();event.caller_info=CallerOf(event.caller);event.flags=flags;event.filetime=Time();
    SetLastError(before);const BOOL result=real_CreateProcessW(app,command,process,thread,inherit,flags,environment,directory,startup,output);
    const DWORD error=GetLastError();event.result=result;event.error=error;Child(event,output);Emit(event);SetLastError(error);return result;
}
__declspec(noinline) inline BOOL WINAPI create_a(LPCSTR app,LPSTR command,LPSECURITY_ATTRIBUTES process,LPSECURITY_ATTRIBUTES thread,
        BOOL inherit,DWORD flags,LPVOID environment,LPCSTR directory,LPSTARTUPINFOA startup,LPPROCESS_INFORMATION output) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(1);Event event;event.kind=2;event.caller=_ReturnAddress();event.caller_info=CallerOf(event.caller);event.flags=flags;event.filetime=Time();
    SetLastError(before);const BOOL result=real_CreateProcessA(app,command,process,thread,inherit,flags,environment,directory,startup,output);
    const DWORD error=GetLastError();event.result=result;event.error=error;Child(event,output);Emit(event);SetLastError(error);return result;
}
__declspec(noinline) inline VOID WINAPI exit_process(UINT code) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(2);Event event;event.kind=3;event.caller=_ReturnAddress();event.caller_info=CallerOf(event.caller);event.exit_code=code;event.filetime=Time();event.error=before;event.before_call=true;event.target_known=event.target_current=true;
    Emit(event);SetLastError(before);real_ExitProcess(code);
}
static_assert(std::is_same<decltype(real_CreateProcessW),decltype(&create_w)>::value,"CreateProcessW documented ABI");
static_assert(std::is_same<decltype(real_CreateProcessA),decltype(&create_a)>::value,"CreateProcessA documented ABI");
static_assert(std::is_same<decltype(real_ExitProcess),decltype(&exit_process)>::value,"ExitProcess documented ABI");
#ifdef OWN_LIFECYCLE_INTEGRITY
__declspec(noinline) inline BOOL WINAPI kb_create_w(LPCWSTR app,LPWSTR command,LPSECURITY_ATTRIBUTES process,LPSECURITY_ATTRIBUTES thread,
        BOOL inherit,DWORD flags,LPVOID environment,LPCWSTR directory,LPSTARTUPINFOW startup,LPPROCESS_INFORMATION output) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(3);Event event;event.kind=4;event.caller=_ReturnAddress();event.caller_info=CallerOf(event.caller);event.flags=flags;event.filetime=Time();
    SetLastError(before);const BOOL result=real_KB_CreateProcessW(app,command,process,thread,inherit,flags,environment,directory,startup,output);
    const DWORD error=GetLastError();event.result=result;event.error=error;Child(event,output);Emit(event);SetLastError(error);return result;
}
__declspec(noinline) inline BOOL WINAPI kb_create_a(LPCSTR app,LPSTR command,LPSECURITY_ATTRIBUTES process,LPSECURITY_ATTRIBUTES thread,
        BOOL inherit,DWORD flags,LPVOID environment,LPCSTR directory,LPSTARTUPINFOA startup,LPPROCESS_INFORMATION output) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(4);Event event;event.kind=5;event.caller=_ReturnAddress();event.caller_info=CallerOf(event.caller);event.flags=flags;event.filetime=Time();
    SetLastError(before);const BOOL result=real_KB_CreateProcessA(app,command,process,thread,inherit,flags,environment,directory,startup,output);
    const DWORD error=GetLastError();event.result=result;event.error=error;Child(event,output);Emit(event);SetLastError(error);return result;
}
__declspec(noinline) inline VOID WINAPI kb_exit_process(UINT code) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(5);Event event;event.kind=6;event.caller=_ReturnAddress();event.caller_info=CallerOf(event.caller);event.exit_code=code;event.filetime=Time();event.error=before;event.before_call=true;event.target_known=event.target_current=true;
    Emit(event);SetLastError(before);real_KB_ExitProcess(code);
}
inline BOOL Terminate(decltype(&TerminateProcess) original,unsigned kind,const void* caller,HANDLE process,UINT code,DWORD before) {
    Event event;event.kind=kind;event.caller=caller;event.caller_info=CallerOf(caller);event.exit_code=code;event.filetime=Time();event.error=before;
    const DWORD target=GetProcessId(process);event.target_known=target!=0;event.target_current=target==GetCurrentProcessId();
    if(!event.target_known||event.target_current){event.before_call=true;Emit(event);}
    SetLastError(before);const BOOL result=original(process,code);const DWORD error=GetLastError();
    event.before_call=false;event.result=result;event.error=error;Emit(event);SetLastError(error);return result;
}
__declspec(noinline) inline BOOL WINAPI terminate_process(HANDLE process,UINT code) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(6);return Terminate(real_TerminateProcess,7,_ReturnAddress(),process,code,before);
}
__declspec(noinline) inline BOOL WINAPI kb_terminate_process(HANDLE process,UINT code) {
    const DWORD before=GetLastError();OWN_LIFE_ENTER(7);return Terminate(real_KB_TerminateProcess,8,_ReturnAddress(),process,code,before);
}
static_assert(std::is_same<decltype(real_KB_CreateProcessW),decltype(&kb_create_w)>::value,"KernelBase CreateProcessW ABI");
static_assert(std::is_same<decltype(real_KB_CreateProcessA),decltype(&kb_create_a)>::value,"KernelBase CreateProcessA ABI");
static_assert(std::is_same<decltype(real_KB_ExitProcess),decltype(&kb_exit_process)>::value,"KernelBase ExitProcess ABI");
static_assert(std::is_same<decltype(real_TerminateProcess),decltype(&terminate_process)>::value,"TerminateProcess ABI");
static_assert(std::is_same<decltype(real_KB_TerminateProcess),decltype(&kb_terminate_process)>::value,"KernelBase TerminateProcess ABI");
#endif
struct Region {PVOID address=nullptr,allocation=nullptr;DWORD protection=0;};
struct Entry {const char* name;PVOID* original;PVOID wrapper;PVOID target=nullptr,code=nullptr;Region regions[4]{};};
static Entry entries[]={
    {"CreateProcessW",reinterpret_cast<PVOID*>(&real_CreateProcessW),reinterpret_cast<PVOID>(&create_w)},
    {"CreateProcessA",reinterpret_cast<PVOID*>(&real_CreateProcessA),reinterpret_cast<PVOID>(&create_a)},
    {"ExitProcess",reinterpret_cast<PVOID*>(&real_ExitProcess),reinterpret_cast<PVOID>(&exit_process)}
#ifdef OWN_LIFECYCLE_INTEGRITY
    ,{"CreateProcessW",reinterpret_cast<PVOID*>(&real_KB_CreateProcessW),reinterpret_cast<PVOID>(&kb_create_w)},
    {"CreateProcessA",reinterpret_cast<PVOID*>(&real_KB_CreateProcessA),reinterpret_cast<PVOID>(&kb_create_a)},
    {"ExitProcess",reinterpret_cast<PVOID*>(&real_KB_ExitProcess),reinterpret_cast<PVOID>(&kb_exit_process)},
    {"TerminateProcess",reinterpret_cast<PVOID*>(&real_TerminateProcess),reinterpret_cast<PVOID>(&terminate_process)},
    {"TerminateProcess",reinterpret_cast<PVOID*>(&real_KB_TerminateProcess),reinterpret_cast<PVOID>(&kb_terminate_process)}
#endif
};
constexpr unsigned count=static_cast<unsigned>(sizeof(entries)/sizeof(entries[0]));
#ifdef OWN_LIFECYCLE_INTEGRITY
static Entry physical_entries[8]{};
inline bool SelectPhysical(const Entry* list,unsigned size,Entry* selected,unsigned& selectedCount,unsigned& aliases) noexcept {
    selectedCount=aliases=0;if(size!=8)return false;
    for(unsigned i=0;i<size;++i){bool omit=false;for(unsigned j=0;j<i;++j){
        const bool overlaps=list[i].target==list[j].target||list[i].target==list[j].code||list[i].code==list[j].target||list[i].code==list[j].code;
        if(!overlaps)continue;
        const bool pair=(j==0&&i==3)||(j==1&&i==4)||(j==2&&i==5)||(j==6&&i==7);
        if(!pair||list[i].code!=list[j].code||list[i].original!=entries[i].original||list[j].original!=entries[j].original||
           list[i].wrapper!=entries[i].wrapper||list[j].wrapper!=entries[j].wrapper)return false;
        omit=true;aliases|=1u<<i;}
        if(!omit)selected[selectedCount++]=list[i];}
    return selectedCount>=4&&selectedCount<=8;
}
#endif
inline bool Capture(PVOID address,Region& region) noexcept {
    MEMORY_BASIC_INFORMATION info{};
    if(VirtualQuery(address,&info,sizeof(info))!=sizeof(info)||info.State!=MEM_COMMIT||info.Type!=MEM_IMAGE||(info.Protect&PAGE_GUARD))return false;
    const DWORD p=info.Protect&0xff;
    if(p!=PAGE_EXECUTE&&p!=PAGE_EXECUTE_READ&&p!=PAGE_EXECUTE_READWRITE&&p!=PAGE_EXECUTE_WRITECOPY)return false;
    region={address,info.AllocationBase,info.Protect};return true;
}
template<class GuardEntry> inline bool Prepare(const GuardEntry* guards,unsigned guardCount) noexcept {
    const HMODULE module=GetModuleHandleW(L"kernel32.dll");if(!module)return false;
#ifdef OWN_LIFECYCLE_INTEGRITY
    const HMODULE kernelbase=GetModuleHandleW(L"kernelbase.dll");if(!kernelbase)return false;
#ifdef OWN_LIFECYCLE_DETAILS
    known_kernel32=module;known_kernelbase=kernelbase;
#endif
#endif
    for(unsigned i=0;i<count;++i){auto& e=entries[i];HMODULE source=module;
#ifdef OWN_LIFECYCLE_INTEGRITY
        if((i>=3&&i<=5)||i==7)source=kernelbase;
#endif
        e.target=reinterpret_cast<PVOID>(GetProcAddress(source,e.name));
        if(!e.target||!(e.code=DetourCodeFromPointer(e.target,nullptr)))return false;
#ifndef OWN_LIFECYCLE_INTEGRITY
        for(unsigned j=0;j<i;++j)if(e.target==entries[j].target||e.target==entries[j].code||e.code==entries[j].target||e.code==entries[j].code)return false;
#endif
        for(unsigned j=0;j<guardCount;++j)if(e.target==guards[j].target||e.target==guards[j].code||e.code==guards[j].target||e.code==guards[j].code)return false;
        PVOID addresses[]={e.target,static_cast<BYTE*>(e.target)+63,e.code,static_cast<BYTE*>(e.code)+63};
        for(unsigned j=0;j<4;++j)if(!Capture(addresses[j],e.regions[j]))return false;
        *e.original=e.target;
    }
#ifdef OWN_LIFECYCLE_INTEGRITY
    if(!SelectPhysical(entries,count,physical_entries,physical_count,coalesced_mask))return false;
#endif
    return true;
}
template<class Attach,class Detach> inline LONG Enlist(bool remove,Attach attach,Detach detach) noexcept {
#ifdef OWN_LIFECYCLE_INTEGRITY
    for(unsigned i=0;i<physical_count;++i){auto& e=physical_entries[i];const LONG result=remove?detach(e.original,e.wrapper):attach(e.original,e.wrapper);if(result!=NO_ERROR)return result;}
#else
    for(auto& e:entries){const LONG result=remove?detach(e.original,e.wrapper):attach(e.original,e.wrapper);if(result!=NO_ERROR)return result;}
#endif
    return NO_ERROR;
}
inline bool ProtectionsRestored() noexcept {
    for(const auto& e:entries)for(const auto& before:e.regions){Region after;
        if(!Capture(before.address,after)||before.allocation!=after.allocation||before.protection!=after.protection)return false;}
    return true;
}
#ifdef OWN_LIFECYCLE_INTEGRITY
struct Signature {PVOID address=nullptr;unsigned char bytes[16]{};bool known=false;
#ifdef OWN_LIFECYCLE_DETAILS
    PVOID allocation=nullptr;const char* name="UNKNOWN";const char* module="UNKNOWN";uint64_t rva=0;
#endif
};
#ifdef OWN_LIFECYCLE_DETAILS
inline const char* KnownModule(PVOID allocation) noexcept {
    if(allocation&&allocation==known_kernel32)return "kernel32.dll";
    if(allocation&&allocation==known_kernelbase)return "kernelbase.dll";
    if(allocation&&allocation==known_user32)return "user32.dll";
    return "UNKNOWN";
}
template<class EntryType> inline void BaselineIdentity(Signature& s,const EntryType& entry) noexcept {
    // Reuse pre-commit Capture metadata; no loader-time module query or new read.
    s.allocation=entry.regions[2].allocation;s.name=entry.name;s.module=KnownModule(s.allocation);
    const auto address=reinterpret_cast<uintptr_t>(s.address),allocation=reinterpret_cast<uintptr_t>(s.allocation);
    if(s.allocation&&address>=allocation)s.rva=address-allocation;
}
#endif
struct Baseline {Signature guard[18]{},lifecycle[8]{};unsigned guards=0,lifecycles=0;volatile LONG claimed=0,captured=0;};
static Baseline baseline;
#ifdef OWN_LIFECYCLE_PRE_SELF
static Baseline pre_self;
#endif
inline bool Read16(PVOID address,unsigned char* bytes) noexcept {
    __try {for(unsigned i=0;i<16;++i)bytes[i]=static_cast<const volatile unsigned char*>(address)[i];return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
template<class GuardEntry,class LifeEntry,class Read>
inline bool RecordBaseline(Baseline& state,const GuardEntry* guards,unsigned guardCount,const LifeEntry* life,unsigned lifeCount,Read read) noexcept {
    if(guardCount>18||lifeCount>8)return false;
    if(InterlockedCompareExchange(&state.claimed,1,0)!=0)return state.captured!=0;
    state.guards=guardCount;state.lifecycles=lifeCount;
    for(unsigned i=0;i<guardCount;++i){auto& s=state.guard[i];s.address=guards[i].code;s.known=read(s.address,s.bytes);}
    for(unsigned i=0;i<lifeCount;++i){auto& s=state.lifecycle[i];s.address=life[i].code;s.known=read(s.address,s.bytes);}
#ifdef OWN_LIFECYCLE_DETAILS
    for(unsigned i=0;i<guardCount;++i)BaselineIdentity(state.guard[i],guards[i]);
    for(unsigned i=0;i<lifeCount;++i)BaselineIdentity(state.lifecycle[i],life[i]);
#endif
    InterlockedExchange(&state.captured,1);return true;
}
template<class GuardEntry> inline void CaptureAfterCommit(const GuardEntry* guards,unsigned size) noexcept {
    RecordBaseline(baseline,guards,size,physical_entries,physical_count,Read16);
}
#ifdef OWN_LIFECYCLE_PRE_SELF
template<class GuardEntry> inline void CaptureBeforeInstall(const GuardEntry* guards,unsigned size) noexcept {
    // Called after all Prepare/Capture/pin validation, before transaction begin.
    // The once-claim also prevents rollback or later sampling from backfilling.
    RecordBaseline(pre_self,guards,size,physical_entries,physical_count,Read16);
}
#endif
struct Totals {unsigned matched=0,mismatched=0,unknown=0;};
template<class Read> inline Totals Compare(const Signature* list,unsigned size,Read read) noexcept {
    Totals out;for(unsigned i=0;i<size;++i){unsigned char bytes[16]{};
        if(!list[i].known||!read(list[i].address,bytes)){++out.unknown;continue;}
        if(!memcmp(bytes,list[i].bytes,16))++out.matched;else ++out.mismatched;}
    return out;
}
struct HealthClock {volatile LONG claim=0,started=0,late=0;ULONGLONG ready=0;};
static HealthClock health_clock;
static volatile LONG64 health_success=0,health_failed=0;
inline bool Due(HealthClock& clock,ULONGLONG now) noexcept {
    return InterlockedCompareExchange(&clock.started,0,0)!=0&&now-clock.ready>=10000&&
        InterlockedCompareExchange(&clock.late,1,0)==0;
}
#ifdef OWN_LIFECYCLE_DETAILS
// These observations are sequential samples, not an atomic mapping snapshot or
// evidence of the writer. No raw address or captured instruction byte is output.
inline bool DetailSpan(const MEMORY_BASIC_INFORMATION& info,uintptr_t address,size_t size,bool image,bool readable=true) noexcept {
    const auto start=reinterpret_cast<uintptr_t>(info.BaseAddress);
    if(!size||info.State!=MEM_COMMIT||(image&&info.Type!=MEM_IMAGE)||!info.AllocationBase||
       (readable&&((info.Protect&(PAGE_GUARD|PAGE_NOACCESS))||!info.Protect))||address<start||
       info.RegionSize>UINTPTR_MAX-start||size>UINTPTR_MAX-address)return false;
    return address+size<=start+info.RegionSize;
}
inline unsigned DifferenceMask(const unsigned char* before,const unsigned char* after) noexcept {
    unsigned mask=0;for(unsigned i=0;i<16;++i)if(before[i]!=after[i])mask|=1u<<i;return mask;
}
#ifdef OWN_LIFECYCLE_PRE_SELF
struct PreComparison {bool known=false,identity_known=false,identity_same=false,compared=false;unsigned mask=0;};
inline PreComparison ComparePreSelf(const Signature* pre,PVOID address,PVOID allocation,const unsigned char* bytes,bool read) noexcept {
    PreComparison out;if(!pre)return out;out.known=pre->known;
    out.identity_known=pre->address&&address&&pre->allocation&&allocation;
    out.identity_same=out.identity_known&&pre->address==address&&pre->allocation==allocation;
    out.compared=out.known&&out.identity_same&&read;
    if(out.compared)out.mask=DifferenceMask(pre->bytes,bytes);return out;
}
#endif
inline bool RelativeTarget(uintptr_t address,unsigned length,int64_t displacement,uintptr_t& result) noexcept {
    if(length>UINTPTR_MAX-address)return false;const auto next=address+length;
    if(displacement>=0){const auto add=static_cast<uint64_t>(displacement);if(add>UINTPTR_MAX-next)return false;result=next+static_cast<uintptr_t>(add);}
    else {const auto subtract=static_cast<uint64_t>(-(displacement+1))+1;if(subtract>next)return false;result=next-static_cast<uintptr_t>(subtract);}
    return true;
}
struct Branch {unsigned kind=0;bool known=false;uintptr_t target=0;};
inline Branch FirstBranch(uintptr_t address,const unsigned char* bytes) noexcept {
    Branch out;
    if(bytes[0]==0xe9){int32_t offset=0;memcpy(&offset,bytes+1,4);out.kind=1;out.known=RelativeTarget(address,5,offset,out.target);}
    else if(bytes[0]==0xeb){int8_t offset=0;memcpy(&offset,bytes+1,1);out.kind=2;out.known=RelativeTarget(address,2,offset,out.target);}
    else if(bytes[0]==0xff&&bytes[1]==0x25){
        out.kind=3;int32_t offset=0;memcpy(&offset,bytes+2,4);uintptr_t slot=0;
        if(RelativeTarget(address,6,offset,slot)&&slot>=address&&slot-address<=16-sizeof(uintptr_t)){
            memcpy(&out.target,bytes+static_cast<size_t>(slot-address),sizeof(out.target));out.known=true;}}
    return out;
}
inline Caller ImageIdentity(const MEMORY_BASIC_INFORMATION& info,uintptr_t address) noexcept {
    Caller out;const auto allocation=reinterpret_cast<uintptr_t>(info.AllocationBase);
    if(info.Type!=MEM_IMAGE||info.State!=MEM_COMMIT||!allocation||address<allocation)return out;
    wchar_t path[512]{};const DWORD length=GetModuleFileNameW(static_cast<HMODULE>(info.AllocationBase),path,512);
    if(!length||length>=512)return out;Basename(path,out.module);if(!out.module[0])return out;
    out.rva=address-allocation;out.known=true;return out;
}
struct Detail {bool read=false,allocation_known=false,allocation_same=false;unsigned mask=0;
    DWORD state=0,protect=0,type=0,destination_type=0;Caller current{},destination{};Branch branch{};
#ifdef OWN_LIFECYCLE_PRE_SELF
    PreComparison pre{};
#endif
};
inline Detail SampleDetail(const Signature& signature
#ifdef OWN_LIFECYCLE_PRE_SELF
    ,const Signature* pre=nullptr
#endif
    ) noexcept {
    Detail out;MEMORY_BASIC_INFORMATION info{};const auto address=reinterpret_cast<uintptr_t>(signature.address);
#ifdef OWN_LIFECYCLE_PRE_SELF
    out.pre=ComparePreSelf(pre,signature.address,nullptr,nullptr,false);
#endif
    if(VirtualQuery(signature.address,&info,sizeof(info))!=sizeof(info))return out;
    out.state=info.State;out.protect=info.Protect;out.type=info.Type;
    if(!DetailSpan(info,address,16,true))return out;
    out.current=ImageIdentity(info,address);out.allocation_known=signature.allocation!=nullptr;
    out.allocation_same=out.allocation_known&&signature.allocation==info.AllocationBase;
#ifdef OWN_LIFECYCLE_PRE_SELF
    out.pre=ComparePreSelf(pre,signature.address,info.AllocationBase,nullptr,false);
#endif
    unsigned char current[16]{};if(!Read16(signature.address,current))return out;
    out.read=true;if(signature.known)out.mask=DifferenceMask(signature.bytes,current);
#ifdef OWN_LIFECYCLE_PRE_SELF
    out.pre=ComparePreSelf(pre,signature.address,info.AllocationBase,current,true);
#endif
    out.branch=FirstBranch(address,current);
    if(out.branch.known){MEMORY_BASIC_INFORMATION destination{};
        if(VirtualQuery(reinterpret_cast<PVOID>(out.branch.target),&destination,sizeof(destination))==sizeof(destination)){
            out.destination_type=destination.Type;
            if(DetailSpan(destination,out.branch.target,1,true,false))out.destination=ImageIdentity(destination,out.branch.target);}}
    return out;
}
inline const char* Tri(bool known,bool value) noexcept {return known?(value?"true":"false"):"null";}
inline bool SameDetailContext(const forward_diagnostic::Context& a,const forward_diagnostic::Context& b) noexcept {
    return a.pid==b.pid&&a.birth==b.birth&&!wcscmp(a.directory,b.directory);
}
inline bool AppendDetail(char* text,size_t capacity,size_t& used,const char* row,size_t size) noexcept {
    // Keep a fixed footer reserve; never publish a partial row.
    if(size>capacity||used>capacity-size||used+size>capacity-128)return false;
    memcpy(text+used,row,size);used+=size;return true;
}
inline void DetailsWrite(const forward_diagnostic::Context& c,bool late,uint64_t time) noexcept {
#ifdef OWN_LIFECYCLE_PRE_SELF
    char text[16384]{},row[2048]{};size_t used=0;unsigned rows=0;
#else
    char text[12288]{},row[2048]{};size_t used=0;unsigned rows=0;
#endif
    const int header=sprintf_s(text,"{\"schema\":\"own-lifecycle-details-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"phase\":\"%s\",\"filetime\":%llu,\"atomic_snapshot\":false,\"rows\":[",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,late?"late":"ready",static_cast<unsigned long long>(time));
    if(header<=0)return;used=static_cast<size_t>(header);
    const unsigned total=baseline.guards+baseline.lifecycles;
    for(unsigned i=0;i<total&&rows<25;++i){const bool guard=i<baseline.guards;const unsigned index=guard?i:i-baseline.guards;
        const auto& signature=guard?baseline.guard[index]:baseline.lifecycle[index];const auto sample=SampleDetail(signature
#ifdef OWN_LIFECYCLE_PRE_SELF
            ,!pre_self.captured?nullptr:guard?(index<pre_self.guards?&pre_self.guard[index]:nullptr):(index<pre_self.lifecycles?&pre_self.lifecycle[index]:nullptr)
#endif
            );
        char preFields[192]{};
#ifdef OWN_LIFECYCLE_PRE_SELF
        char mask[16]{};if(sample.pre.compared)sprintf_s(mask,"%u",sample.pre.mask);else strcpy_s(mask,"null");
        sprintf_s(preFields,",\"pre_self_known\":%s,\"ready_vs_pre_self_install_mask16\":%s,\"pre_self_identity_same\":%s",
            sample.pre.known?"true":"false",mask,Tri(sample.pre.identity_known,sample.pre.identity_same));
#endif
        const bool compared=signature.known&&sample.read;
        const int n=sprintf_s(row,"%s{\"group\":\"%s\",\"index\":%u,\"api\":\"%.128s\",\"baseline_module\":\"%.128s\",\"baseline_rva\":%llu,\"current_module\":\"%.128s\",\"current_rva\":%llu,\"state\":%lu,\"protect\":%lu,\"type\":%lu,\"read\":%s,\"changed_mask\":%d,\"first5_equal\":%s,\"allocation_identity_same\":%s,\"branch_kind\":%u,\"destination_type\":%lu,\"destination_module\":\"%.128s\",\"destination_rva\":%llu%s}",
            rows?",":"",guard?"guard":"lifecycle",index,signature.name,signature.module,static_cast<unsigned long long>(signature.rva),
            sample.current.known?sample.current.module:"UNKNOWN",static_cast<unsigned long long>(sample.current.rva),sample.state,sample.protect,sample.type,sample.read?"true":"false",
            compared?static_cast<int>(sample.mask):-1,Tri(compared,(sample.mask&31)==0),Tri(sample.allocation_known,sample.allocation_same),sample.branch.kind,sample.destination_type,
            sample.destination.known?sample.destination.module:"UNKNOWN",static_cast<unsigned long long>(sample.destination.rva),preFields);
        if(n<=0||!AppendDetail(text,sizeof(text),used,row,static_cast<size_t>(n)))break;++rows;}
    const int footer=sprintf_s(text+used,sizeof(text)-used,"],\"row_count\":%u,\"omitted_rows\":%u}\n",rows,total-rows);
    if(footer<=0)return;used+=static_cast<size_t>(footer);
    forward_diagnostic::Context fresh{};if(!forward_diagnostic::context(fresh)||!SameDetailContext(c,fresh))return;
    wchar_t path[600]{};swprintf_s(path,L"%s\\%s",c.directory,late?L"lifecycle-details-late.json":L"lifecycle-details-ready.json");
    const HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file!=INVALID_HANDLE_VALUE){DWORD written=0;if(WriteFile(file,text,static_cast<DWORD>(used),&written,nullptr)&&written==used)FlushFileBuffers(file);CloseHandle(file);}
}
inline void GuardedDetails(const forward_diagnostic::Context& c,bool late,uint64_t time) noexcept {
    // Detail failure must not skip or alter the existing aggregate publication.
    __try {DetailsWrite(c,late,time);} __except(EXCEPTION_EXECUTE_HANDLER){}
}
#endif
inline void HealthWrite(bool late) noexcept {
    forward_diagnostic::Context c{};
    if(!forward_diagnostic::context(c)){InterlockedIncrement64(&health_failed);return;}
    const auto guard=Compare(baseline.guard,baseline.guards,Read16),life=Compare(baseline.lifecycle,baseline.lifecycles,Read16);
    LONG64 e[8]{},s[7]{};for(unsigned i=0;i<8;++i)e[i]=InterlockedCompareExchange64(&entered[i],0,0);
    for(unsigned i=0;i<7;++i)s[i]=InterlockedCompareExchange64(&statistics[i],0,0);
#ifdef OWN_LIFECYCLE_DETAILS
    const uint64_t healthTime=Time();
    GuardedDetails(c,late,healthTime); // Flush/close before counts can trigger owned cleanup.
#endif
    char text[2048]{};wchar_t path[600]{};
    swprintf_s(path,L"%s\\%s",c.directory,late?L"lifecycle-health-late.json":L"lifecycle-health-ready.json");
    const int n=sprintf_s(text,"{\"schema\":\"own-lifecycle-integrity-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"phase\":\"%s\",\"filetime\":%llu,\"baseline_after_commit\":%s,\"guard_physical\":%u,\"guard_signature_matched\":%u,\"guard_signature_mismatched\":%u,\"guard_signature_unknown\":%u,\"lifecycle_logical\":8,\"lifecycle_physical\":%u,\"coalesced_mask\":%u,\"lifecycle_signature_matched\":%u,\"lifecycle_signature_mismatched\":%u,\"lifecycle_signature_unknown\":%u,\"entered_k32_w_a_exit_kb_w_a_exit_k32_kb_terminate\":[%lld,%lld,%lld,%lld,%lld,%lld,%lld,%lld],\"logger_calls\":%lld,\"logger_reentry_refused\":%lld,\"logger_context_refused\":%lld,\"logger_limit_refused\":%lld,\"logger_io_success\":%lld,\"logger_io_failed\":%lld,\"logger_faults\":%lld,\"health_prior_success\":%lld,\"health_prior_failed\":%lld}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,late?"late":"ready",static_cast<unsigned long long>(
#ifdef OWN_LIFECYCLE_DETAILS
        healthTime
#else
        Time()
#endif
        ),baseline.captured?"true":"false",
        baseline.guards,guard.matched,guard.mismatched,guard.unknown,physical_count,coalesced_mask,life.matched,life.mismatched,life.unknown,
        e[0],e[1],e[2],e[3],e[4],e[5],e[6],e[7],s[0],s[1],s[2],s[3],s[4],s[5],s[6],
        InterlockedCompareExchange64(&health_success,0,0),InterlockedCompareExchange64(&health_failed,0,0));
    const HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    bool complete=false;
    if(file!=INVALID_HANDLE_VALUE){DWORD written=0;
        if(n>0&&WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr)&&written==static_cast<DWORD>(n))complete=FlushFileBuffers(file)!=FALSE;
        if(!CloseHandle(file))complete=false;}
    InterlockedIncrement64(complete?&health_success:&health_failed);
}
inline void GuardedHealth(bool late) noexcept {
    const DWORD before=GetLastError();
    __try {HealthWrite(late);} __except(EXCEPTION_EXECUTE_HANDLER){InterlockedIncrement64(&health_failed);}
    SetLastError(before);
}
inline void StartHealth() noexcept {
    const DWORD before=GetLastError();
    if(InterlockedCompareExchange(&health_clock.claim,1,0)==0){health_clock.ready=GetTickCount64();
        InterlockedExchange(&health_clock.started,1);GuardedHealth(false);}
    SetLastError(before);
}
inline void MaybeHealth() noexcept {
    if(InterlockedCompareExchange(&health_clock.started,0,0)==0||InterlockedCompareExchange(&health_clock.late,0,0)!=0)return;
    const DWORD before=GetLastError();if(Due(health_clock,GetTickCount64()))GuardedHealth(true);SetLastError(before);
}
#endif
inline void Installed() noexcept {InterlockedExchange(&installed,1);}
} // namespace owned_lifecycle
