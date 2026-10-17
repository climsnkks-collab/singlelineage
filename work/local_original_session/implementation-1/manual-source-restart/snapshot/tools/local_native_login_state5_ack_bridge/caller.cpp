// Successor to frozen producer.cpp: real original-call wrappers, no loader.
#include "producer.cpp"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <atomic>

namespace local_native_own_login {
enum class Phase:uint32_t { Idle,Selected,Connected,Dispatching,SenderReturned,Cancelled };
struct Caller {
    SRWLOCK lock=SRWLOCK_INIT;
    std::atomic<Phase> phase{Phase::Idle};
    Pair network{},socket{};
    void* manager=nullptr;void* selectedTask=nullptr;
    char uuid[37]={},tag[129]={};size_t tagLength=0;
    bool enqueueAttempted=false,connectAttempted=false,ownLimitRefused=false;
    State once{};
    // Caller storage lives until original callback/task cancellation and join.
    // Cancellation never frees storage that a worker may still borrow.
};
void Retain(const Pair& p) noexcept {
    if(p.control)_InterlockedIncrement(reinterpret_cast<volatile long*>(static_cast<unsigned char*>(p.control)+8));
}
// Only the actual OwnGuest-qualified selected entry calls this, before its
// original27E4F0. Neither catalog/port/config nor Root+D8 is this predicate.
bool BeginActualOwnSelected(Caller& c,const Pair& genuineNetwork,const Inputs& own) noexcept {
    if(!Valid(own)||!genuineNetwork.object||!genuineNetwork.control)return false;
    AcquireSRWLockExclusive(&c.lock);
    if(c.phase.load()!=Phase::Idle){ReleaseSRWLockExclusive(&c.lock);return false;}
    Retain(genuineNetwork);c.network=genuineNetwork;
    c.manager=*reinterpret_cast<void**>(static_cast<unsigned char*>(genuineNetwork.object)+0x198);
    memcpy(c.uuid,own.uuid,36);c.uuid[36]=0;c.tagLength=own.tagLength;
    if(own.tagLength)memcpy(c.tag,own.selectedTag,own.tagLength);
    c.phase.store(Phase::Selected);ReleaseSRWLockExclusive(&c.lock);return true;
}
using OriginalInit=void(*)(void*,const void*,int);
// Own-qualified27E533 ->26DFA0 call-through. Initial/vendor callers keep their
// original path. A re-selection/reconnect under this own caller is refused.
bool OriginalOwnInitOnce(Caller& c,OriginalInit original,const void* selectedDto,int timeout) {
    AcquireSRWLockExclusive(&c.lock);
    if(c.phase.load()!=Phase::Selected || c.enqueueAttempted){c.ownLimitRefused=true;
        ReleaseSRWLockExclusive(&c.lock);return false;}
    c.enqueueAttempted=true;void* manager=c.manager;ReleaseSRWLockExclusive(&c.lock);
    try{original(manager,selectedDto,timeout);return true;}
    catch(...){AcquireSRWLockExclusive(&c.lock);c.phase.store(Phase::Cancelled);
        ReleaseSRWLockExclusive(&c.lock);throw;}
}
// Capture the actual constructed callable while the qualified selected enqueue
// is synchronous. Original26F1F0 constructor is not duplicated or replaced here.
bool AttachActualSelectedTask(Caller& c,void* actualCallable,void* actualManager) noexcept {
    AcquireSRWLockExclusive(&c.lock);
    bool ok=c.phase.load()==Phase::Selected && c.enqueueAttempted && !c.selectedTask && actualCallable && actualManager==c.manager;
    if(ok)c.selectedTask=actualCallable;
    ReleaseSRWLockExclusive(&c.lock);return ok;
}
using OriginalConnect=bool(*)(void*,const char*,uint16_t,int);
// Source-level call-through for26F8B8 CALL32F2B0. Additional context arguments
// require an ABI adapter before byte integration; this is not a direct hook.
bool OriginalConnectThenObserve(Caller& c,OriginalConnect original,void* actualTask,
                               const Pair& retainedSocket,const char* host,uint16_t port,int timeout) {
    AcquireSRWLockExclusive(&c.lock);
    bool mine=actualTask && c.selectedTask==actualTask &&
        *reinterpret_cast<void**>(static_cast<unsigned char*>(actualTask)+8)==c.manager &&
        retainedSocket.object && retainedSocket.control;
    const bool actualOwnCapture=mine;
    if(mine && (c.phase.load()!=Phase::Selected || c.connectAttempted)){
        c.ownLimitRefused=true;mine=false;
        // Own observation is disabled. The ordinary original still runs once.
    }
    if(mine){Retain(retainedSocket);c.socket=retainedSocket;c.connectAttempted=true;}
    ReleaseSRWLockExclusive(&c.lock);
    bool result;
    try {result=original(retainedSocket.object,host,port,timeout);}
    catch(...){AcquireSRWLockExclusive(&c.lock);if(mine)c.phase.store(Phase::Cancelled);
        ReleaseSRWLockExclusive(&c.lock);throw;}
    AcquireSRWLockExclusive(&c.lock);
    if(mine && c.phase.load()==Phase::Selected && c.selectedTask==actualTask)
        c.phase.store(result?Phase::Connected:Phase::Cancelled);
    ReleaseSRWLockExclusive(&c.lock);if(actualOwnCapture)selected_diagnostic::connect(result);return result; // original allowed-attempt return
}
void CancelAtOriginalSocketClose(Caller& c,void* actualSocket) noexcept {
    AcquireSRWLockExclusive(&c.lock);
    if(c.socket.object && c.socket.object==actualSocket)c.phase.store(Phase::Cancelled);
    ReleaseSRWLockExclusive(&c.lock);
    // Original241990 close always runs; this helper touches only own phase.
}
Result AfterOriginalVersionCounts(Caller& c,const Api& api,const Pair& handlerHeldNetwork,bool(*prepareDto)() noexcept) noexcept {
    Pair retained{};Inputs own{};
    AcquireSRWLockExclusive(&c.lock);
    bool eligible=!c.ownLimitRefused && c.phase.load()==Phase::Connected && handlerHeldNetwork.object==c.network.object &&
                  handlerHeldNetwork.control==c.network.control && !c.once.attempted;
    if(eligible){c.phase.store(Phase::Dispatching);retained=c.network;Retain(retained);
        own={c.uuid,36,c.tagLength?c.tag:nullptr,c.tagLength};}
    ReleaseSRWLockExclusive(&c.lock);
    if(!eligible)return {Result::AlreadyAttempted,0};
    Held guard{retained};
    // Close can cancel before the original producer call. A concurrent close
    // during original send is handled by original queue/socket semantics; no
    // stronger completion-atomic guarantee is invented.
    if(c.phase.load()==Phase::Cancelled)return {Result::NoNetwork,0};
    // Only the actual eligible own handler reaches this check. Failure disables
    // this own generation without consuming producer once or retrying COUNTS.
    if(!prepareDto || !prepareDto()) {
        AcquireSRWLockExclusive(&c.lock);c.ownLimitRefused=true;c.phase.store(Phase::Cancelled);ReleaseSRWLockExclusive(&c.lock);
        return {Result::OwnCodeNotReady,0};
    }
    if(c.phase.load()!=Phase::Dispatching)return {Result::NoNetwork,0};
    Result r=SendOwnLoginHeld(api,retained,own,c.once);
    Phase expected=Phase::Dispatching;
    c.phase.compare_exchange_strong(expected,Phase::SenderReturned);
    return r;
}
// Compiled context-bearing ready callee: original COUNTS API first, then own
// producer. Not the original three-argument27D620 ABI: adapter still required.
// Only original4E35 consumer2746FA/2746FF may invoke it.
Result OriginalCountsThenOwn(Caller& c,const Api& api,const Pair& handlerHeldNetwork,Message* originalCounts,bool(*prepareDto)() noexcept) {
    api.send(handlerHeldNetwork.object,0x4f3d,originalCounts);
    return AfterOriginalVersionCounts(c,api,handlerHeldNetwork,prepareDto);
}
// No reset/reselection/reconnect API. Caller keeps storage valid until all
// borrowed hooks are unregistered and original tasks/callbacks have joined.
void FinishAfterOriginalCallbacksJoined(Caller& c) noexcept {
    Pair n{},s{};AcquireSRWLockExclusive(&c.lock);c.phase.store(Phase::Cancelled);
    n=c.network;s=c.socket;c.network={};c.socket={};ReleaseSRWLockExclusive(&c.lock);
    Release(s.control);Release(n.control);
}
}
