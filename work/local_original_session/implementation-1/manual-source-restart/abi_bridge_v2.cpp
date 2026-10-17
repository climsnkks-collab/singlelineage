// ABI-compatible normal DLL successor. Frozen caller/producer are included,
// not edited. Root must configure and verify before installing any game hook.
#include "selected_diag.hpp"
#include "key_diag.hpp"
#include "caller.cpp"
#include "bridge_candidate_v2.hpp"
#include "bridge_own_authority_v2.hpp"
#include "binding.hpp"
#include "diagnostic.hpp"
#include "forward_layout.hpp"
#include <cstring>
#include <intrin.h>

#include <cstdio>
#include <type_traits>

using namespace local_native_own_login;
struct SourceProof {uint32_t size;uintptr_t innerImageBase;char programSha256[65];};
struct BridgeScope {
    Caller caller;Api api{};OriginalConnect connect=nullptr;OriginalInit init=nullptr;
    void(*close)(void*)=nullptr;
    std::atomic<bool> selectedReady{false};uintptr_t base=0;
};
static BridgeScope scope;
static SRWLOCK configurationLock=SRWLOCK_INIT;
struct ExclusiveConfiguration {ExclusiveConfiguration(){AcquireSRWLockExclusive(&configurationLock);}~ExclusiveConfiguration(){ReleaseSRWLockExclusive(&configurationLock);}};
struct TaskFrame {void* callable=nullptr;Pair socket{};};
static thread_local TaskFrame taskFrame;
static thread_local bool ownSelectedEnqueue=false;
static char configuredUuid[37]={},configuredTag[129]={};
static size_t configuredTagLength=0;
static std::atomic<bool> ownInputsReady{false};
static OriginalForwardBinding forwardBinding;
static bool PrepareOwnEligibility(selected_diagnostic::Eligibility* observed=nullptr) noexcept {
    if(scope.selectedReady.load()){if(observed)observed->cached=true;return true;}
    forward_diagnostic::Context context{};const bool confirmed=selected_diagnostic::valid_context(context);
    if(observed)observed->context=confirmed?selected_diagnostic::Pass:selected_diagnostic::Fail;
    if(!confirmed)return false;
    ExclusiveConfiguration only;if(scope.selectedReady.load()){if(observed)observed->cached=true;return true;}
    const auto b=forwardBinding.base.load();if(observed)observed->base=b?selected_diagnostic::Pass:selected_diagnostic::Fail;if(!b)return false;
    scope.base=b;scope.api=Api::Bind(b);scope.connect=reinterpret_cast<OriginalConnect>(forwardBinding.target(ForwardRole::Connect));
    scope.init=reinterpret_cast<OriginalInit>(forwardBinding.target(ForwardRole::Init));scope.close=reinterpret_cast<void(*)(void*)>(forwardBinding.target(ForwardRole::Close));
    scope.selectedReady.store(true);return true;
}
// Readiness for selected/getter/task/connect does not imply DTO code readiness.
static bool PrepareOwnDtoCodeDetailed(selected_diagnostic::QueryFn query=VirtualQuery,CopyFn copy=SafeCopy,CodeFn setterCode=Executable) noexcept {
    const DWORD before=GetLastError();selected_diagnostic::Eligibility detail;
    forward_diagnostic::Context context{};const bool confirmed=selected_diagnostic::valid_context(context);
    detail.context=confirmed?selected_diagnostic::Pass:selected_diagnostic::Fail;
    const auto b=forwardBinding.base.load();detail.base=b && scope.selectedReady.load() && scope.base==b?selected_diagnostic::Pass:selected_diagnostic::Fail;
    bool ready=false;
    if(confirmed && detail.base==selected_diagnostic::Pass){
        constexpr unsigned char create[]={0x48,0x89,0x5c,0x24,0x08,0x57,0x48,0x83,0xec,0x20};
        constexpr unsigned char setter[]={0x48,0x89,0x5c,0x24,0x10,0x48,0x89,0x6c,0x24,0x18};
        ready=selected_diagnostic::create_code_stage(b+0x799d00,create,sizeof(create),b,&detail,query,copy) &&
              selected_diagnostic::code_stage(b+0xdde430,setter,sizeof(setter),&detail.setter_exec,&detail.setter_copy,&detail.setter_match,setterCode,copy);
    }
    selected_diagnostic::dto(detail,ready);SetLastError(before);return ready;
}
static bool PrepareOwnDtoCode() noexcept {return PrepareOwnDtoCodeDetailed();}
extern "C" __declspec(dllexport) bool OwnLoginConfigureOriginalH(const SourceProof* supplied) noexcept {
    SourceProof proof{};return supplied && SafeCopy(&proof,supplied,sizeof(proof)) && proof.size==sizeof(proof) &&
        proof.innerImageBase==forwardBinding.base.load() && proof.innerImageBase && !memcmp(proof.programSha256,OWN_EXPECTED_PROGRAM_SHA,65) && PrepareOwnEligibility();
}
static thread_local uint32_t probeRecord=0;
struct BridgeCall;
static thread_local BridgeCall* activeCall=nullptr;
struct BridgeCall {
    ForwardRole role;DWORD before;BridgeCall* previous;
    bool hadOriginal=false;DWORD lastOriginal=0;
    explicit BridgeCall(ForwardRole r):role(r),before(GetLastError()),previous(activeCall){activeCall=this;}
    ~BridgeCall(){activeCall=previous;if(hadOriginal)SetLastError(lastOriginal);}
};
template<class F> static decltype(auto) ForwardCall(ForwardRole role,F function) {
    BridgeCall* frame=(activeCall && activeCall->role==role)?activeCall:nullptr;
    const DWORD entry=frame?frame->before:GetLastError();
    if(static_cast<unsigned>(role)<7)forward_diagnostic::once(forward_diagnostic::attempt,L"original-attempt.json","ORIGINAL_CALL_ATTEMPT",role,probeRecord,BindReason::Bound,true,false,scope.selectedReady.load()?"NONE":"OWN_NOT_READY");
    SetLastError(entry);
    try {
        if constexpr(std::is_void_v<decltype(function())>) {
            function();const DWORD after=GetLastError();if(frame){frame->hadOriginal=true;frame->lastOriginal=after;}
            if(static_cast<unsigned>(role)<7)forward_diagnostic::once(forward_diagnostic::returned,L"original-return.json","ORIGINAL_RETURN",role,probeRecord,BindReason::Bound,true,true,scope.selectedReady.load()?"NONE":"OWN_NOT_READY");
            SetLastError(after);return;
        } else {
            auto result=function();const DWORD after=GetLastError();if(frame){frame->hadOriginal=true;frame->lastOriginal=after;}
            if(static_cast<unsigned>(role)<7)forward_diagnostic::once(forward_diagnostic::returned,L"original-return.json","ORIGINAL_RETURN",role,probeRecord,BindReason::Bound,true,true,scope.selectedReady.load()?"NONE":"OWN_NOT_READY");
            SetLastError(after);return result;
        }
    } catch(...) {
        const DWORD after=GetLastError();if(frame){frame->hadOriginal=true;frame->lastOriginal=after;}if(static_cast<unsigned>(role)<7)forward_diagnostic::once(forward_diagnostic::returned,L"original-return.json","ORIGINAL_EXCEPTION",role,probeRecord,BindReason::Bound,true,false,"ORIGINAL_EXCEPTION");SetLastError(after);throw;
    }
}
static bool CallConnect(void* a,const char* b,uint16_t c,int d){return ForwardCall(ForwardRole::Connect,[&]{return reinterpret_cast<OriginalConnect>(forwardBinding.target(ForwardRole::Connect))(a,b,c,d);});}
static void CallInit(void* a,const void* b,int c){ForwardCall(ForwardRole::Init,[&]{reinterpret_cast<OriginalInit>(forwardBinding.target(ForwardRole::Init))(a,b,c);});}
// Actual own-qualified selection hook supplies the genuine3EC40 pair and own
// UUID. This explicit first hook is not installed by this DLL/build.
extern "C" __declspec(dllexport) bool OwnLoginBeginActualSelection(const Pair* held,const Inputs* own) noexcept {
    if(!scope.selectedReady.load() || !held || !own ||
       reinterpret_cast<uintptr_t>(_ReturnAddress())!=scope.base+0xadc1c3)return false;
    return BeginActualOwnSelected(scope.caller,*held,*own);
}
extern "C" __declspec(dllexport) bool OwnLoginOwnInitOnce(const void* actualSelectedDto,int timeout) {
    if(!PrepareOwnEligibility())return false;return OriginalOwnInitOnce(scope.caller,CallInit,actualSelectedDto,timeout);
}
extern "C" __declspec(dllexport) bool OwnLoginCaptureSelectedCallable(void* actualCallable,void* actualManager) noexcept {
    uintptr_t address=reinterpret_cast<uintptr_t>(_ReturnAddress());
    if(!scope.selectedReady.load() || address<scope.base+0x26dfa0 || address>=scope.base+0x26e134)return false;
    return AttachActualSelectedTask(scope.caller,actualCallable,actualManager);
}
// Original26F7E0 live frame: this callable and its retained stack20/28 pair.
// Capture only that original frame; neither config nor port selects this task.
extern "C" __declspec(dllexport) bool OwnLoginEnterSelectedTask(void* actualCallable,const Pair* retainedSocket) noexcept {
    taskFrame={}; // Rejecting another task must not leave an old borrowed frame.
    uintptr_t returnAddress=reinterpret_cast<uintptr_t>(_ReturnAddress());
    if(!scope.selectedReady.load() || !actualCallable || !retainedSocket ||
       returnAddress<scope.base+0x26f7e0 || returnAddress>=scope.base+0x26f900)return false;
    AcquireSRWLockShared(&scope.caller.lock);
    bool ok=actualCallable==scope.caller.selectedTask && retainedSocket->object && retainedSocket->control;
    ReleaseSRWLockShared(&scope.caller.lock);
    if(ok)taskFrame={actualCallable,*retainedSocket};return ok;
}
extern "C" __declspec(dllexport) void OwnLoginLeaveSelectedTask() noexcept {taskFrame={};}

static std::atomic<unsigned> connectDiagIndex{0};
static thread_local bool probeDuplicateBypass=false;
struct VerifiedSocketClaim {bool active=false;NativeProbeFrame frame{};BindingResult fresh;void* control=nullptr;};
static thread_local VerifiedSocketClaim probeFreshVerifiedSocket;

static bool ExactConnectedLocalPeer(void* socket) noexcept {
    const DWORD before=GetLastError();
    uintptr_t handle=0;unsigned char initialized=0;
    bool verified=false;
    if(socket && SafeCopy(&handle,static_cast<unsigned char*>(socket)+0x10,sizeof(handle))
       && SafeCopy(&initialized,static_cast<unsigned char*>(socket)+9,1)
       && handle && initialized==1) {
        HMODULE winsock=GetModuleHandleW(L"ws2_32.dll");
        auto peer=winsock?reinterpret_cast<int(WINAPI*)(uintptr_t,void*,int*)>(GetProcAddress(winsock,"getpeername")):nullptr;
        if(peer) {
            unsigned char address[128]{};int length=sizeof(address);
            if(peer(handle,address,&length)==0 && length>=8)
                verified=address[0]==2 && address[1]==0 && address[2]==0x36 && address[3]==0xce
                  && address[4]==127 && address[5]==0 && address[6]==0 && address[7]==1;
        }
        uintptr_t same=0;
        verified=verified && SafeCopy(&same,static_cast<unsigned char*>(socket)+0x10,sizeof(same)) && same==handle;
    }
    SetLastError(before);return verified;
}
using ConnectedPeerFn=bool(*)(void*) noexcept;
static bool BoundVerifiedSocketDuplicate(const NativeProbeFrame&,const BindingResult&,void*&,
    ConnectedPeerFn peer=ExactConnectedLocalPeer,void* expectedControl=nullptr) noexcept;
static void RecordConnect(uintptr_t returnAddress,unsigned index,unsigned phase,bool selectedTask,
                          bool duplicate,bool peerVerified,bool bypass,bool result,bool proofOverride,bool freshVerifiedDuplicate,
                          DWORD entryError,DWORD returnError) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context context{};
    if(index<8 && forward_diagnostic::context(context)) {
        const uintptr_t base=forwardBinding.base.load();
        const bool inImage=base && returnAddress>=base && returnAddress<base+OwnForwardLayout::ImageSize;
        const uintptr_t rva=inImage?returnAddress-base:0;
        FILETIME now{};GetSystemTimeAsFileTime(&now);
        const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
        wchar_t leaf[40]{};swprintf_s(leaf,L"connect-caller-%u.json",index);
        char text[896]{};
        const int n=sprintf_s(text,"{\"schema\":\"own-cp13-connect-caller-v2\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"filetime\":%llu,\"caller_in_image\":%s,\"caller_rva\":%llu,\"phase_before\":%u,\"selected_task_matches\":%s,\"duplicate_candidate\":%s,\"local_peer_verified\":%s,\"original_bypassed\":%s,\"returned_bool\":%s,\"source_mismatch_override\":%s,\"fresh_verified_duplicate\":%s,\"entry_last_error\":%lu,\"return_last_error\":%lu}\n",
            context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,index,
            static_cast<unsigned long long>(filetime),inImage?"true":"false",
            static_cast<unsigned long long>(rva),phase,selectedTask?"true":"false",
            duplicate?"true":"false",peerVerified?"true":"false",bypass?"true":"false",
            result?"true":"false",proofOverride?"true":"false",freshVerifiedDuplicate?"true":"false",entryError,returnError);
        if(n>0)selected_diagnostic::output(context,leaf,text,n);
    }
    SetLastError(before);
}
// Preserve the original connect for every call except a verified duplicate
// from the same selected task to the already connected local peer.
extern "C" __declspec(dllexport) bool OwnLoginConnectBridge(void* socket,const char* host,uint16_t port,int timeout) {
    BridgeCall call(ForwardRole::Connect);
    const auto verifiedClaim=probeFreshVerifiedSocket;probeFreshVerifiedSocket={};
    const bool freshVerifiedDuplicate=verifiedClaim.active;PrepareOwnEligibility();
    const bool proofOverride=probeDuplicateBypass;probeDuplicateBypass=false;
    TaskFrame active=taskFrame;taskFrame={}; // one call; also clear on exception
    uintptr_t caller=reinterpret_cast<uintptr_t>(_ReturnAddress());
    const bool selectedEdge=caller==scope.base+0x26f8bd && active.callable && active.socket.object==socket;
    bool selectedTask=false,duplicate=false;unsigned phase=0;
    AcquireSRWLockShared(&scope.caller.lock);
    phase=static_cast<unsigned>(scope.caller.phase.load());
    selectedTask=selectedEdge && active.callable==scope.caller.selectedTask
      && active.socket.control && active.socket.control==scope.caller.socket.control;
    duplicate=(selectedTask || proofOverride || freshVerifiedDuplicate) && phase==static_cast<unsigned>(Phase::Connected)
      && scope.caller.socket.object==socket && scope.caller.socket.control
      && scope.caller.connectAttempted && !scope.caller.ownLimitRefused;
    ReleaseSRWLockShared(&scope.caller.lock);
    void* recheckedControl=nullptr;
    const bool peerVerified=freshVerifiedDuplicate?
        duplicate && caller==verifiedClaim.frame.original_return &&
        reinterpret_cast<uintptr_t>(socket)==verifiedClaim.frame.rcx &&
        port==static_cast<uint16_t>(verifiedClaim.frame.r8) &&
        BoundVerifiedSocketDuplicate(verifiedClaim.frame,verifiedClaim.fresh,recheckedControl,
            ExactConnectedLocalPeer,verifiedClaim.control):
        duplicate && (port==14000 || port==14030) && ExactConnectedLocalPeer(socket);
    bool bypass=false;
    if(peerVerified) {
        AcquireSRWLockShared(&scope.caller.lock);
        const bool match=proofOverride?scope.caller.socket.object==socket && scope.caller.socket.control:
          freshVerifiedDuplicate?scope.caller.socket.object==socket && scope.caller.socket.control &&
          scope.caller.socket.control==verifiedClaim.control:
          active.callable==scope.caller.selectedTask && active.socket.object==scope.caller.socket.object
          && active.socket.control==scope.caller.socket.control;
        bypass=match && scope.caller.connectAttempted && !scope.caller.ownLimitRefused
          && scope.caller.phase.load()==Phase::Connected;
        ReleaseSRWLockShared(&scope.caller.lock);
    }
    bool result=false;
    if(freshVerifiedDuplicate && bypass)bypass=forwardBinding.same_source_proof(
        verifiedClaim.fresh.base,verifiedClaim.fresh.original,ForwardRole::Connect);
    if(bypass){result=true;SetLastError(0);}
    else if(proofOverride || freshVerifiedDuplicate){result=false;SetLastError(call.before);}
    else if(selectedEdge)result=OriginalConnectThenObserve(scope.caller,CallConnect,active.callable,active.socket,host,port,timeout);
    else result=CallConnect(socket,host,port,timeout);
    const DWORD after=GetLastError();
    RecordConnect(caller,connectDiagIndex.fetch_add(1,std::memory_order_relaxed),phase,selectedTask,
                  duplicate,peerVerified,bypass,result,proofOverride,freshVerifiedDuplicate,call.before,after);
    SetLastError(after);return result;
}
static std::atomic<unsigned> senderCountIndex{0};
static std::atomic<bool> dtoPageClaim{false};
static std::atomic<bool> factoryProbeClaim{false};
// Give the game's own exception handlers first chance to activate a protected
// generated method. Catch an unhandled fault at this leaf boundary only.
static bool TryFactoryProbe(Api::New factory,Message** value,DWORD* fault) noexcept {
    __try {*value=factory(nullptr,nullptr);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){*value=nullptr;*fault=GetExceptionCode();return false;}
}
static bool TrySetterProbe(Api::Set setter,uint64_t* field,const View* value,DWORD* fault) noexcept {
    __try {setter(field,value,nullptr);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){*fault=GetExceptionCode();return false;}
}
static bool TryDestroyProbe(Api::Delete destroy,Message* value,DWORD* fault) noexcept {
    __try {destroy(value,1);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){*fault=GetExceptionCode();return false;}
}
static void RecordFactoryProbe() noexcept {
    const DWORD before=GetLastError();bool expected=false;
    if(!factoryProbeClaim.compare_exchange_strong(expected,true))return;
    forward_diagnostic::Context context{};
    const uintptr_t base=forwardBinding.base.load(std::memory_order_acquire);
    if(forward_diagnostic::context(context) && scope.selectedReady.load() && base && scope.base==base &&
       reinterpret_cast<uintptr_t>(scope.api.create)==base+0x799d00 &&
       reinterpret_cast<uintptr_t>(scope.api.destroy)==base+0x799fd0) {
        MEMORY_BASIC_INFORMATION initial{},after{};
        const bool beforeQuery=VirtualQuery(reinterpret_cast<void*>(base+0x799d00),&initial,sizeof(initial))==sizeof(initial);
        const bool bounded=beforeQuery && initial.State==MEM_COMMIT && initial.Type==MEM_IMAGE &&
          initial.Protect==PAGE_NOACCESS && reinterpret_cast<uintptr_t>(initial.AllocationBase)==base;
        Message* value=nullptr;DWORD callFault=0,destroyFault=0;
        bool returned=false,nonnull=false,vtableMatch=false,arenaZero=false,destroyAttempted=false,destroyReturned=false;
        if(bounded) {
            returned=TryFactoryProbe(scope.api.create,&value,&callFault);
            nonnull=returned && value;
            if(nonnull) {
                void* vtable=nullptr;uint64_t arena=UINT64_MAX;
                vtableMatch=SafeCopy(&vtable,value,sizeof(vtable)) &&
                  reinterpret_cast<uintptr_t>(vtable)==scope.api.expectedMessageVtable;
                arenaZero=SafeCopy(&arena,&value->arena,sizeof(arena)) && arena==0;
                if(vtableMatch && arenaZero) {
                    // Generated setter may still be PAGE_NOACCESS at first
                    // COUNTS. Invoke it only on this disposable DTO so the
                    // game's own exception handler can activate its page.
                    MEMORY_BASIC_INFORMATION setterInfo{};
                    const bool setterBounded=
                      reinterpret_cast<uintptr_t>(scope.api.set)==base+0xdde430 &&
                      VirtualQuery(reinterpret_cast<void*>(base+0xdde430),&setterInfo,sizeof(setterInfo))==sizeof(setterInfo) &&
                      setterInfo.State==MEM_COMMIT && setterInfo.Type==MEM_IMAGE &&
                      setterInfo.Protect==PAGE_NOACCESS &&
                      reinterpret_cast<uintptr_t>(setterInfo.AllocationBase)==base;
                    if(setterBounded) {
                        constexpr char empty[]="";const View emptyView{empty,0};DWORD setterFault=0;
                        (void)TrySetterProbe(scope.api.set,&value->issuer,&emptyView,&setterFault);
                    }
                    destroyAttempted=true;
                    destroyReturned=TryDestroyProbe(scope.api.destroy,value,&destroyFault);
                }
            }
        }
        const bool afterQuery=VirtualQuery(reinterpret_cast<void*>(base+0x799d00),&after,sizeof(after))==sizeof(after);
        FILETIME now{};GetSystemTimeAsFileTime(&now);
        const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
        char text[900]{};
        const int n=sprintf_s(text,"{\"schema\":\"own-cp17-factory-probe-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"filetime\":%llu,\"bounded\":%s,\"before_protect\":%lu,\"call_returned\":%s,\"call_exception_code\":%lu,\"message_nonnull\":%s,\"vtable_match\":%s,\"arena_zero\":%s,\"destroy_attempted\":%s,\"destroy_returned\":%s,\"destroy_exception_code\":%lu,\"after_query_ok\":%s,\"after_protect\":%lu}\n",
          context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,
          static_cast<unsigned long long>(filetime),bounded?"true":"false",
          beforeQuery?initial.Protect:0,returned?"true":"false",callFault,
          nonnull?"true":"false",vtableMatch?"true":"false",arenaZero?"true":"false",
          destroyAttempted?"true":"false",destroyReturned?"true":"false",destroyFault,
          afterQuery?"true":"false",afterQuery?after.Protect:0);
        if(n>0)selected_diagnostic::output(context,L"factory-probe.json",text,n);
    }
    SetLastError(before);
}
static void RecordDtoPages() noexcept {
    const DWORD before=GetLastError();bool expected=false;
    if(!dtoPageClaim.compare_exchange_strong(expected,true))return;
    forward_diagnostic::Context context{};
    if(forward_diagnostic::context(context) && scope.base) {
        constexpr uint32_t rvas[]={0x799d00,0xdde430,0x79aa60,0x79a840,0x2424e0};
        constexpr const char* names[]={"factory","setter","clone","serializer","original_builder"};
        char items[1200]{};size_t used=0;bool good=true;
        for(unsigned i=0;i<5;++i) {
            MEMORY_BASIC_INFORMATION info{};
            const SIZE_T count=VirtualQuery(reinterpret_cast<void*>(scope.base+rvas[i]),&info,sizeof(info));
            const bool ok=count==sizeof(info);
            const bool same=ok && reinterpret_cast<uintptr_t>(info.AllocationBase)==scope.base;
            const int n=sprintf_s(items+used,sizeof(items)-used,
              "%s{\"name\":\"%s\",\"query_ok\":%s,\"state\":%lu,\"protect\":%lu,\"type\":%lu,\"same_image\":%s}",
              i?",":"",names[i],ok?"true":"false",ok?info.State:0,ok?info.Protect:0,
              ok?info.Type:0,same?"true":"false");
            if(n<=0){good=false;break;}used+=static_cast<size_t>(n);
        }
        if(good) {
            FILETIME now{};GetSystemTimeAsFileTime(&now);
            const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
            char text[1600]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-cp16-dto-pages-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"filetime\":%llu,\"pages\":[%s]}\n",
              context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,
              static_cast<unsigned long long>(filetime),items);
            if(n>0)selected_diagnostic::output(context,L"dto-pages.json",text,n);
        }
    }
    SetLastError(before);
}
static void RecordSenderCount(unsigned index,unsigned phase,bool selectedReady,bool networkMatch,
                              bool ownLimit,bool branch,int resultCode) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context context{};
    if(index<8 && forward_diagnostic::context(context)) {
        FILETIME now{};GetSystemTimeAsFileTime(&now);
        const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
        wchar_t leaf[40]{};swprintf_s(leaf,L"sender-count-%u.json",index);
        char text[650]{};
        const int n=sprintf_s(text,"{\"schema\":\"own-cp14-sender-count-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"filetime\":%llu,\"caller_rva\":%u,\"opcode\":%u,\"phase_before\":%u,\"selected_ready\":%s,\"network_matches_selected\":%s,\"own_limit_refused\":%s,\"original_called\":true,\"own_branch_entered\":%s,\"own_result_code\":%d}\n",
            context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,index,
            static_cast<unsigned long long>(filetime),0x2746ff,0x4f3d,phase,
            selectedReady?"true":"false",networkMatch?"true":"false",ownLimit?"true":"false",
            branch?"true":"false",resultCode);
        if(n>0)selected_diagnostic::output(context,leaf,text,n);
    }
    SetLastError(before);
}
// EXACT ORIGINAL 3-ARGUMENT ABI. Original opcode/message are passed through
// first, including when there is no own scope or this is another sender call.
#include "auto_ok.hpp"
extern "C" __declspec(dllexport) void OwnLoginSenderBridge(void* network,uint16_t opcode,Message* message) {
    BridgeCall call(ForwardRole::Sender);PrepareOwnEligibility();
    const bool countEdge=reinterpret_cast<uintptr_t>(_ReturnAddress())==scope.base+0x2746ff && opcode==0x4f3d;
    bool networkMatch=false,ownLimit=false;unsigned phase=0;
    if(countEdge) {
        AcquireSRWLockShared(&scope.caller.lock);
        phase=static_cast<unsigned>(scope.caller.phase.load());
        networkMatch=scope.caller.network.object==network;
        ownLimit=scope.caller.ownLimitRefused;
        ReleaseSRWLockShared(&scope.caller.lock);
    }
    ForwardCall(ForwardRole::Sender,[&]{reinterpret_cast<Api::Send>(forwardBinding.target(ForwardRole::Sender))(network,opcode,message);});
    const bool ready=scope.selectedReady.load();bool branch=false;int resultCode=-1;
    if(ready && countEdge && networkMatch){RecordDtoPages();RecordFactoryProbe();}
    if(ready && countEdge) {
        Pair held{};
        AcquireSRWLockShared(&scope.caller.lock);
        if(scope.caller.network.object==network){held=scope.caller.network;Retain(held);}
        ReleaseSRWLockShared(&scope.caller.lock);
        if(held.object) {
            Held guard{held};branch=true;
            resultCode=static_cast<int>(AfterOriginalVersionCounts(scope.caller,scope.api,held,PrepareOwnDtoCode).code);
        }
    }
    if(countEdge)RecordSenderCount(senderCountIndex.fetch_add(1,std::memory_order_relaxed),phase,
       ready,networkMatch,ownLimit,branch,resultCode);
    if(resultCode==0)InstallAutoOkHook();
}
static std::atomic<unsigned> closeDiagIndex{0};
static void RecordCloseCaller(void* socket,uintptr_t returnAddress,DWORD entryError) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context context{};
    if(forward_diagnostic::context(context)) {
        const unsigned index=closeDiagIndex.fetch_add(1,std::memory_order_relaxed);
        if(index<8) {
            const uintptr_t base=forwardBinding.base.load();
            const bool callerInImage=base && returnAddress>=base && returnAddress<base+OwnForwardLayout::ImageSize;
            const uintptr_t callerRva=callerInImage?returnAddress-base:0;
            void* frames[24]{};
            const USHORT captured=CaptureStackBackTrace(0,24,frames,nullptr);
            char gameStack[256]{};int used=0;unsigned gameCount=0;
            gameStack[used++]='[';
            for(USHORT frame=0;frame<captured && gameCount<8;++frame) {
                const uintptr_t address=reinterpret_cast<uintptr_t>(frames[frame]);
                if(!base || address<base || address>=base+OwnForwardLayout::ImageSize)continue;
                const int n=sprintf_s(gameStack+used,sizeof(gameStack)-used,"%s%llu",gameCount?",":"",
                    static_cast<unsigned long long>(address-base));
                if(n<=0 || used+n>=static_cast<int>(sizeof(gameStack))-2)break;
                used+=n;++gameCount;
            }
            gameStack[used++]=']';gameStack[used]=0;
            const char* route=callerRva==0x26cbc3?"WORKER_SEND_ERROR":
                callerRva==0x26c0b8?"ROLE0_CLOSE_TASK":
                callerRva==0x32f54b?"CONNECT_FAILURE":"OTHER_OR_UNKNOWN";
            bool selectedPair=false;
            AcquireSRWLockShared(&scope.caller.lock);
            selectedPair=scope.caller.socket.object && scope.caller.socket.object==socket;
            const unsigned phase=static_cast<unsigned>(scope.caller.phase.load());
            ReleaseSRWLockShared(&scope.caller.lock);
            unsigned char flags[2]{};uintptr_t handle=0;uint32_t sequence=0;
            const bool typed=socket && SafeCopy(flags,static_cast<unsigned char*>(socket)+8,2) &&
                SafeCopy(&handle,static_cast<unsigned char*>(socket)+0x10,sizeof(handle)) &&
                SafeCopy(&sequence,static_cast<unsigned char*>(socket)+0xa0060,sizeof(sequence)) &&
                flags[0]<=1 && flags[1]<=1;
            FILETIME now{};GetSystemTimeAsFileTime(&now);
            const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
            wchar_t wideLeaf[40]{};swprintf_s(wideLeaf,L"close-caller-%u.json",index);
            char text[900]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-cp10-close-stack-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"filetime\":%llu,\"caller_in_image\":%s,\"caller_rva\":%llu,\"route\":\"%s\",\"selected_socket_pair_matches\":%s,\"phase\":%u,\"entry_last_error\":%lu,\"socket_state_read\":%s,\"read_seen\":%s,\"initialized\":%s,\"handle_present\":%s,\"send_sequence\":%u,\"game_stack_rvas\":%s}\n",
                context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,index,
                static_cast<unsigned long long>(filetime),callerInImage?"true":"false",
                static_cast<unsigned long long>(callerRva),route,selectedPair?"true":"false",phase,
                entryError,typed?"true":"false",typed?(flags[0]?"true":"false"):"null",
                typed?(flags[1]?"true":"false"):"null",
                typed?(handle?"true":"false"):"null",typed?sequence:0,gameStack);
            if(n>0)selected_diagnostic::output(context,wideLeaf,text,n);
        }
    }
    SetLastError(before);
}
extern "C" __declspec(dllexport) void OwnLoginCloseBridge(void* socket) {
    BridgeCall call(ForwardRole::Close);
    RecordCloseCaller(socket,reinterpret_cast<uintptr_t>(_ReturnAddress()),call.before);
    if(PrepareOwnEligibility())CancelAtOriginalSocketClose(scope.caller,socket);
    ForwardCall(ForwardRole::Close,[&]{reinterpret_cast<void(*)(void*)>(forwardBinding.target(ForwardRole::Close))(socket);});
}
extern "C" __declspec(dllexport) void OwnLoginFinishAfterCallbacksJoined() noexcept {
    if(scope.selectedReady.load())FinishAfterOriginalCallbacksJoined(scope.caller);
}

extern "C" __declspec(dllexport) bool OwnLoginConfigureCandidate(uintptr_t innerBase) noexcept {
    SourceProof proof{};proof.size=sizeof(proof);proof.innerImageBase=innerBase;
    memcpy(proof.programSha256,OWN_EXPECTED_PROGRAM_SHA,65);
    return OwnLoginConfigureOriginalH(&proof);
}
extern "C" __declspec(dllexport) bool OwnLoginSetReviewedOwnInputs(const Inputs* in) noexcept {
    if(!scope.selectedReady.load() || !in || !Valid(*in))return false;
    ExclusiveConfiguration only;
    if(ownInputsReady.load())return false;
    memcpy(configuredUuid,in->uuid,36);configuredUuid[36]=0;
    configuredTagLength=in->tagLength;
    if(in->tagLength)memcpy(configuredTag,in->selectedTag,in->tagLength);
    ownInputsReady.store(true);return true;
}
using OriginalSelected=void(*)(void*,const void*,uintptr_t,int);
// Raw original27E4F0 ABI includes unusedR8 and timeoutR9. H's actual owned CALL
// is ADC1BE/returnADC1C3, while normal UI ADD4A1/returnADD4A6 is forwarded.
extern "C" __declspec(dllexport) void OwnLoginSelectedBridge(void* network,const void* dto,uintptr_t unusedR8,int timeoutR9) {
    BridgeCall call(ForwardRole::Selected);
    selected_diagnostic::Selected observed;observed.probe_bound=true;observed.cpp_entered=true;observed.reason=0;
    observed.qualified=reinterpret_cast<uintptr_t>(_ReturnAddress())==forwardBinding.base.load()+0xadc1c3?selected_diagnostic::Pass:selected_diagnostic::Fail;
    PrepareOwnEligibility(&observed.eligibility);
    auto capture=[&] {
        const DWORD before=GetLastError();AcquireSRWLockShared(&scope.caller.lock);
        observed.own_enqueue_attempted=scope.caller.enqueueAttempted;observed.selected_task_registered=scope.caller.selectedTask!=nullptr;observed.own_flags_observed=true;
        ReleaseSRWLockShared(&scope.caller.lock);selected_diagnostic::selected(observed);SetLastError(before);
    };
    auto original=[&](void* a,const void* b,uintptr_t c,int d){
        try{ForwardCall(ForwardRole::Selected,[&]{reinterpret_cast<OriginalSelected>(forwardBinding.target(ForwardRole::Selected))(a,b,c,d);});}
        catch(...){observed.original_exception_observed=true;capture();throw;}
        observed.original_return_confirmed=true;capture();
    };
    if(!scope.selectedReady.load()){original(network,dto,unusedR8,timeoutR9);return;}
    bool qualified=reinterpret_cast<uintptr_t>(_ReturnAddress())==scope.base+0xadc1c3;
    Pair pair{};
    if(qualified){
        if(!ownInputsReady.load()){
            constexpr char uuid[]=OWN_REVIEWED_UUID;
            Inputs reviewed{uuid,sizeof(uuid)-1,nullptr,0};
            if(!OwnLoginSetReviewedOwnInputs(&reviewed)){observed.own_inputs_ready=selected_diagnostic::Fail;original(network,dto,unusedR8,timeoutR9);return;}
        }
        observed.own_inputs_ready=selected_diagnostic::Pass;
        void* root=*reinterpret_cast<void**>(scope.base+0x1668790);
        if(root && static_cast<unsigned char*>(root)[0xd8])scope.api.network(root,&pair);
        Held getterPair{pair};
        Inputs in{configuredUuid,36,configuredTagLength?configuredTag:nullptr,configuredTagLength};
        observed.genuine_pair_matches_argument=pair.object==network?selected_diagnostic::Pass:selected_diagnostic::Fail;
        if(observed.genuine_pair_matches_argument==selected_diagnostic::Fail){original(network,dto,unusedR8,timeoutR9);return;}
        const bool begun=BeginActualOwnSelected(scope.caller,pair,in);observed.begin=begun?selected_diagnostic::Pass:selected_diagnostic::Fail;
        if(!begun){original(network,dto,unusedR8,timeoutR9);return;}
        struct EnqueueScope {EnqueueScope(){ownSelectedEnqueue=true;}~EnqueueScope(){ownSelectedEnqueue=false;}} selectScope;
        original(network,dto,unusedR8,timeoutR9);return;
    }
    original(network,dto,unusedR8,timeoutR9);
}
extern "C" __declspec(dllexport) void OwnLoginInitBridge(void* manager,const void* dto,int timeout) {
    BridgeCall call(ForwardRole::Init);PrepareOwnEligibility();
    if(scope.selectedReady.load() && ownSelectedEnqueue && reinterpret_cast<uintptr_t>(_ReturnAddress())==scope.base+0x27e538 && manager==scope.caller.manager){
        if(!OriginalOwnInitOnce(scope.caller,CallInit,dto,timeout))CallInit(manager,dto,timeout);return;
    }
    CallInit(manager,dto,timeout);
}
using OriginalConstructor=void*(*)(void*,void*);
extern "C" __declspec(dllexport) void* OwnLoginConstructorBridge(void* holder,void* captured) {
    BridgeCall call(ForwardRole::Constructor);
    void* returned=ForwardCall(ForwardRole::Constructor,[&]{return reinterpret_cast<OriginalConstructor>(forwardBinding.target(ForwardRole::Constructor))(holder,captured);});
    PrepareOwnEligibility();
    uintptr_t from=reinterpret_cast<uintptr_t>(_ReturnAddress());
    if(ownSelectedEnqueue && from>=scope.base+0x26dfa0 && from<scope.base+0x26e134){
        // Source26F2BC stores actual callable at holder+38; captured+0 manager.
        void* callable=*reinterpret_cast<void**>(static_cast<unsigned char*>(holder)+0x38);
        void* manager=*reinterpret_cast<void**>(captured);
        AttachActualSelectedTask(scope.caller,callable,manager);
    }
    return returned;
}
static Pair RetainOriginalRole0(void* manager) {
    using Mutex=void(*)(void*);auto lock=reinterpret_cast<Mutex>(scope.base+0xfa0624);
    auto unlock=reinterpret_cast<Mutex>(scope.base+0xfa0634);void* mutex=static_cast<unsigned char*>(manager)+0x58;
    lock(mutex);Pair result{};
    auto head=*reinterpret_cast<unsigned char**>(static_cast<unsigned char*>(manager)+0x48);
    auto node=*reinterpret_cast<unsigned char**>(head+8);auto best=head;
    while(!node[0x19]){if(*reinterpret_cast<int32_t*>(node+0x20)<0)node=*reinterpret_cast<unsigned char**>(node+0x10);
        else{best=node;node=*reinterpret_cast<unsigned char**>(node);}}
    if(best!=head && !best[0x19] && *reinterpret_cast<int32_t*>(best+0x20)==0){
        result={*reinterpret_cast<void**>(best+0x28),*reinterpret_cast<void**>(best+0x30)};Retain(result);
    }
    unlock(mutex);return result;
}
extern "C" __declspec(dllexport) void OwnLoginSelectedTaskBridge(void* callable) {
    BridgeCall call(ForwardRole::Task);
    auto original=[&](void* p){ForwardCall(ForwardRole::Task,[&]{reinterpret_cast<void(*)(void*)>(forwardBinding.target(ForwardRole::Task))(p);});};
    if(!PrepareOwnEligibility()){original(callable);return;}
    bool selected=false;void* manager=nullptr;
    AcquireSRWLockShared(&scope.caller.lock);
    if(callable==scope.caller.selectedTask && scope.caller.phase.load()==Phase::Selected){
        manager=*reinterpret_cast<void**>(static_cast<unsigned char*>(callable)+8);selected=manager==scope.caller.manager;}
    ReleaseSRWLockShared(&scope.caller.lock);
    Pair pair=selected?RetainOriginalRole0(manager):Pair{};
    Held guard{pair};taskFrame={selected?callable:nullptr,pair};
    struct Clear {~Clear(){taskFrame={};}} clear;
    original(callable); // original getter/lock/connect/cleanup remain intact
}

struct KeyExecution {void* manager=nullptr;bool recording=false;};
static thread_local KeyExecution keyExecution;
static bool MatchSelectedManager(void* manager) noexcept {
    if(!manager || !scope.selectedReady.load())return false;
    AcquireSRWLockShared(&scope.caller.lock);
    const bool match=scope.caller.network.object && scope.caller.network.control && scope.caller.manager==manager;
    ReleaseSRWLockShared(&scope.caller.lock);return match;
}
// Exact KEY holder's original ADD RCX,8 / JMP26E160 thunk remains the callee.
extern "C" void OwnKeyTaskBridge(void* holder) noexcept(false) {
    BridgeCall call(ForwardRole::KeyTask);void* manager=nullptr;
    const auto address=reinterpret_cast<uintptr_t>(holder);
    const bool readable=address && address<=UINTPTR_MAX-8 && SafeCopy(&manager,reinterpret_cast<void*>(address+8),sizeof(manager));
    key_diagnostic::Record record(false,readable && MatchSelectedManager(manager));
    struct Execution {
        KeyExecution previous;Execution(void* manager,bool recorded):previous(keyExecution){keyExecution={manager,recorded};}
        ~Execution(){keyExecution=previous;}
    } execution(manager,record.claimed);
    try{ForwardCall(ForwardRole::KeyTask,[&]{reinterpret_cast<void(*)(void*)>(forwardBinding.target(ForwardRole::KeyTask))(holder);});}
    catch(...){record.complete(true);throw;}
    record.complete(false);
}
#ifdef OWN_KEY_HOST_TEST
extern uintptr_t test_key_version_return;
static uintptr_t KeyVersionReturn() noexcept {return test_key_version_return;}
#endif
// Original26DA90 is four-register ABI. RDX is forwarded unchanged even though
// the exact original body replaces it before using manager+180 sender lookup.
extern "C" void OwnKeyVersionBridge(void* manager,uintptr_t unusedRdx,uint16_t opcode,void* message) noexcept(false) {
    BridgeCall call(ForwardRole::KeyVersion);
    const bool match=keyExecution.recording && keyExecution.manager==manager && MatchSelectedManager(manager) && opcode==0x4e34 &&
        
#ifdef OWN_KEY_HOST_TEST
        KeyVersionReturn()==forwardBinding.base.load()+0x26e8e5;
#else
        reinterpret_cast<uintptr_t>(_ReturnAddress())==forwardBinding.base.load()+0x26e8e5;
#endif
    key_diagnostic::Record record(true,match);
    try{ForwardCall(ForwardRole::KeyVersion,[&]{reinterpret_cast<void(*)(void*,uintptr_t,uint16_t,void*)>(forwardBinding.target(ForwardRole::KeyVersion))(manager,unusedRdx,opcode,message);});}
    catch(...){record.complete(true);throw;}
    record.complete(false);
}
#include "probe.cpp"
