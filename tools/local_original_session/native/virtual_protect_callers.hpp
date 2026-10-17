#pragma once
// Explicit diagnostic profile only; the parent DLL and trampolines stay pinned.
#include <atomic>
#include <type_traits>
namespace virtual_protect_callers {
using Fn=decltype(&::VirtualProtect);
static_assert(sizeof(void*)==8,"Pinned Detours x64 layout only");
static_assert(std::atomic<Fn>::is_always_lock_free,"Hook forward must be lock-free");
constexpr SIZE_T TrampolineBytes=96; // Pinned e4bfd6 x64 rbCode offset0, whole struct96.
struct Target {uintptr_t address=0;unsigned group=0,index=0;};
struct Record {volatile LONG state=0;unsigned group=0,index=0,offset=0,length=0,matches=0;
    uintptr_t caller=0;uint64_t claim=0,completed=0,tsc=0;BOOL result=FALSE;DWORD error=0,new_protect=0;};
struct State {Target targets[25]{};unsigned count=0;uintptr_t self=0,self_end=0;
    volatile LONG armed=0,active=0,published=0,attempted=0,install=0,error=0;
    volatile LONG64 claims=0,completions=0,invalid=0,dropped=0;Record records[4]{};};
static State state;
static std::atomic<Fn> prepared{nullptr};
static Fn original_slot=&::VirtualProtect; // Detours only; NEVER consumed by HookEntry.
__declspec(thread) static bool inside=false;
enum Install:LONG {NotAttempted=0,Installed=1,BadSetup=2,BeginFailed=3,UpdateFailed=4,
    AttachFailed=5,NullTrampoline=6,CacheFailed=7,CommitPrepatchFailed=8,AbortUnknown=9,InstallException=10};
inline bool Span(uintptr_t address,SIZE_T size) noexcept {
    constexpr uintptr_t high=0x00007fffffffffffULL;
    return address>=0x10000&&address<=high&&size&&size<=0x40000000ULL&&size-1<=high-address;
}
struct Match {bool valid=false;unsigned group=0,index=0,offset=0,length=0,count=0;};
inline Match Find(const State& s,uintptr_t address,SIZE_T size) noexcept {
    Match out;if(!Span(address,size))return out;out.valid=true;const auto end=address+size;
    for(unsigned i=0;i<s.count;++i){const auto& t=s.targets[i];const auto targetEnd=t.address+16;
        if(address>=targetEnd||end<=t.address)continue;
        if(!out.count){const auto begin=address>t.address?address:t.address,finish=end<targetEnd?end:targetEnd;
            out.group=t.group;out.index=t.index;out.offset=static_cast<unsigned>(begin-t.address);out.length=static_cast<unsigned>(finish-begin);}
        ++out.count;}return out;
}
inline int Claim(State& s,const Match& match,uintptr_t caller,DWORD protection) noexcept {
    for(unsigned i=0;i<4;++i)if(InterlockedCompareExchange(&s.records[i].state,1,0)==0){auto& r=s.records[i];
        r.group=match.group;r.index=match.index;r.offset=match.offset;r.length=match.length;r.matches=match.count;r.caller=caller;r.new_protect=protection;
        r.claim=static_cast<uint64_t>(InterlockedIncrement64(&s.claims));r.tsc=__rdtsc();return static_cast<int>(i);}
    InterlockedIncrement64(&s.dropped);return -1;
}
inline void Complete(State& s,int slot,BOOL result,DWORD error) noexcept {
    if(slot<0)return;auto& r=s.records[slot];r.result=result;r.error=error;
    r.completed=static_cast<uint64_t>(InterlockedIncrement64(&s.completions));InterlockedExchange(&r.state,2);
}
__declspec(noinline) static BOOL WINAPI HookEntry(LPVOID address,SIZE_T size,DWORD protection,PDWORD oldProtection) {
    const DWORD before=GetLastError();const uintptr_t caller=reinterpret_cast<uintptr_t>(_ReturnAddress());
    const bool owner=!inside;int slot=-1;
    if(owner){inside=true;InterlockedIncrement(&state.active);
        if(InterlockedCompareExchange(&state.armed,0,0)&&!(caller>=state.self&&caller<state.self_end)){
            const auto match=Find(state,reinterpret_cast<uintptr_t>(address),size);
            if(!match.valid)InterlockedIncrement64(&state.invalid);else if(match.count)slot=Claim(state,match,caller,protection);}}
    BOOL result=FALSE;DWORD after=before;bool returned=false;
    __try {SetLastError(before);const Fn forward=prepared.load(std::memory_order_acquire);
        // Nonnull is established BEFORE target patch. No original-slot fallback.
        result=forward(address,size,protection,oldProtection);after=GetLastError();returned=true;Complete(state,slot,result,after);}
    __finally {if(owner){InterlockedDecrement(&state.active);inside=false;}if(returned)SetLastError(after);}
    return result;
}
static_assert(std::is_same_v<decltype(&HookEntry),Fn>,"SDK VirtualProtect ABI");
template<class Ops> inline void InstallTransaction(Ops& op) {
    LONG status=op.Begin();if(status!=NO_ERROR){state.install=BeginFailed;state.error=status;return;}
    status=op.Update();PVOID trampoline=nullptr;
    if(status!=NO_ERROR)state.install=UpdateFailed;
    else {status=op.Attach(&trampoline);if(status!=NO_ERROR)state.install=AttachFailed;
        else if(!trampoline){status=ERROR_INVALID_ADDRESS;state.install=NullTrampoline;}
        else if(!op.Flush(trampoline,TrampolineBytes)){status=op.Error();state.install=CacheFailed;}}
    if(status!=NO_ERROR){state.error=status;if(op.Abort()!=NO_ERROR)state.install=AbortUnknown;return;}
    prepared.store(reinterpret_cast<Fn>(trampoline),std::memory_order_release);
    status=op.Commit();
    if(status!=NO_ERROR){
        // Pinned Commit error returns precede its patch loop. No target consumer
        // exists; pending-error path has already aborted/freed. No second abort.
        prepared.store(nullptr,std::memory_order_release);state.install=CommitPrepatchFailed;state.error=status;return;}
    state.install=Installed;InterlockedExchange(&state.armed,1);
}
struct NativeOps {
    LONG Begin()const{return DetourTransactionBegin();}
    LONG Update()const{return DetourUpdateThread(GetCurrentThread());}
    LONG Attach(PVOID* out)const{PDETOUR_TRAMPOLINE value=nullptr;
        PVOID target=nullptr;const LONG result=DetourAttachEx(reinterpret_cast<PVOID*>(&original_slot),reinterpret_cast<PVOID>(&HookEntry),&value,&target,nullptr);
        *out=value;if(result==NO_ERROR&&value&&(!Span(reinterpret_cast<uintptr_t>(target),16)||Find(state,reinterpret_cast<uintptr_t>(target),16).count))return ERROR_INVALID_ADDRESS;
        return result;}
    bool Flush(PVOID value,SIZE_T size)const{return FlushInstructionCache(GetCurrentProcess(),value,size)!=FALSE;}
    LONG Commit()const{return DetourTransactionCommit();}
    LONG Abort()const{return DetourTransactionAbort();}
    DWORD Error()const noexcept{return GetLastError();}
};
inline bool Configure(HMODULE self) noexcept {
    const auto& core=owned_lifecycle::baseline;
    if(!core.captured||core.guards!=17||core.lifecycles!=8||!self)return false;
    __try {const auto base=reinterpret_cast<uintptr_t>(self);const auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
        if(dos->e_magic!=IMAGE_DOS_SIGNATURE||dos->e_lfanew<0||dos->e_lfanew>0x100000)return false;
        const auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS64*>(base+dos->e_lfanew);
        if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64||
           nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC||nt->OptionalHeader.SizeOfImage<4096||nt->OptionalHeader.SizeOfImage>0x4000000)return false;
        state.self=base;state.self_end=base+nt->OptionalHeader.SizeOfImage;if(state.self_end<base)return false;
        for(unsigned i=0;i<25;++i){const bool guard=i<17;const unsigned index=guard?i:i-17;const auto& s=guard?core.guard[index]:core.lifecycle[index];
            if(!s.known||!s.allocation||!Span(reinterpret_cast<uintptr_t>(s.address),16))return false;
            state.targets[i]={reinterpret_cast<uintptr_t>(s.address),guard?0u:1u,index};}
        state.count=25;return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline void InstallBody(HMODULE self) {
    __try {if(!Configure(self))state.install=BadSetup;else {NativeOps op;InstallTransaction(op);}}
    __except(EXCEPTION_EXECUTE_HANDLER){state.install=InstallException;/* Never free uncertain prepared lifetime. */}
}
inline void InstallOptional(HMODULE self) noexcept {
    const DWORD before=GetLastError();if(InterlockedCompareExchange(&state.attempted,1,0)==0){
        try {InstallBody(self);}catch(...){state.install=InstallException;}}
    SetLastError(before);
}
inline void Disarm() noexcept {InterlockedExchange(&state.armed,0);}
inline void PublishReady(const forward_diagnostic::Context& c) noexcept {
    if(InterlockedCompareExchange(&state.published,1,0)!=0)return;
    char text[8192]{},row[1024]{};unsigned count=0,pending=0;size_t used=0;
    const int header=sprintf_s(text,"{\"schema\":\"own-virtual-protect-callers-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"install\":%ld,\"install_error\":%ld,\"coverage\":\"UNKNOWN\",\"span_basis\":\"INPUT_ARGUMENT_VALUES\",\"mapping_scope\":\"PUBLICATION_TIME_ONLY\",\"tsc_domain\":\"RDTSC_UNCALIBRATED_NOT_UTC_QPC\",\"inflight_unknown\":%ld,\"invalid_span_unknown\":%lld,\"capacity_dropped\":%lld,\"records\":[",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,state.install,state.error,
        InterlockedCompareExchange(&state.active,0,0),InterlockedCompareExchange64(&state.invalid,0,0),InterlockedCompareExchange64(&state.dropped,0,0));
    if(header<=0)return;used=static_cast<size_t>(header);
    for(unsigned i=0;i<4;++i){const auto ready=InterlockedCompareExchange(&state.records[i].state,0,0);if(ready==1){++pending;continue;}if(ready!=2)continue;
        const auto& r=state.records[i];const auto caller=owned_lifecycle::CallerOf(reinterpret_cast<PVOID>(r.caller));
        const int n=sprintf_s(row,"%s{\"group\":%u,\"index\":%u,\"offset\":%u,\"length\":%u,\"match_count\":%u,\"new_protect_uint32\":%lu,\"result\":%s,\"last_error\":%lu,\"claim_ordinal\":%llu,\"completion_ordinal\":%llu,\"claim_tsc\":%llu,\"caller_module\":\"%.128s\",\"caller_rva\":%llu}",
            count?",":"",r.group,r.index,r.offset,r.length,r.matches,r.new_protect,r.result?"true":"false",r.error,
            static_cast<unsigned long long>(r.claim),static_cast<unsigned long long>(r.completed),static_cast<unsigned long long>(r.tsc),caller.known?caller.module:"UNKNOWN",static_cast<unsigned long long>(caller.rva));
        if(n<=0||used+static_cast<size_t>(n)+128>=sizeof(text))return;memcpy(text+used,row,static_cast<size_t>(n));used+=static_cast<size_t>(n);++count;}
    const int footer=sprintf_s(text+used,sizeof(text)-used,"],\"complete_records\":%u,\"pending_unknown\":%u,\"actual_write_proven\":false}\n",count,pending);
    if(footer<=0)return;used+=static_cast<size_t>(footer);forward_diagnostic::Context fresh{};
    if(!forward_diagnostic::context(fresh)||!owned_lifecycle::SameDetailContext(c,fresh))return;
    wchar_t path[600]{};swprintf_s(path,L"%s\\virtual-protect-callers-ready.json",c.directory);
    const HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file!=INVALID_HANDLE_VALUE){DWORD written=0;if(WriteFile(file,text,static_cast<DWORD>(used),&written,nullptr)&&written==used)FlushFileBuffers(file);CloseHandle(file);}
}
inline void GuardedPublish(const forward_diagnostic::Context& c) noexcept {
    __try {PublishReady(c);} __except(EXCEPTION_EXECUTE_HANDLER){}
}
} // namespace virtual_protect_callers
