#pragma once
// Additive source-only CP47-style intra-process WH_GETMESSAGE bridge.
// Include from a reviewed host DLL after arming against its exact process.
// It has no DllMain, injection, process-open, socket, focus or launcher path.
#include <windows.h>
#include <cstddef>
#include "move_plan.hpp"
#include "../local_native_move_input_source/source_anchors.hpp"
namespace original_move {
using TileVerifier=TileGate(*)(const Plan&,const Observed&) noexcept;
using SourceVerifier=bool(*)(uintptr_t) noexcept;
using Report=void(*)(Result) noexcept;
struct Host {Plan plan;TileVerifier tile=nullptr;SourceVerifier source=nullptr;Report report=nullptr;};
static Host host{};
static OneMove attempt;
static std::atomic<bool> installationAttempted{false};
static std::atomic<HHOOK> hook{nullptr};
static std::atomic<UINT> messageId{0};
inline bool Canonical(uintptr_t p) noexcept {return p>=0x10000 && p<=0x7fffffffffff && (p&7)==0;}
inline uintptr_t Ptr(uintptr_t at) noexcept {return *reinterpret_cast<uintptr_t*>(at);}
inline bool Pair(uintptr_t at,uintptr_t& object) noexcept {
    object=Ptr(at);const auto control=Ptr(at+8);
    return Canonical(object) && Canonical(control) && *reinterpret_cast<int32_t*>(control+8)>0;
}
inline bool Vector(uintptr_t at,size_t limit,uintptr_t& start,size_t& count) noexcept {
    start=Ptr(at);const auto end=Ptr(at+8);
    if(start==0 && end==0){count=0;return true;}
    if(!Canonical(start) || end<start || end>0x7fffffffffff || (end-start)%16)return false;
    count=(end-start)/16;return count<=limit;
}
inline bool Component(uintptr_t actor,uintptr_t vft,uintptr_t& out) noexcept {
    uintptr_t begin=0;size_t count=0;out=0;
    if(!Vector(actor+0x20,128,begin,count))return false;
    for(size_t i=0;i<count;++i){uintptr_t object=0;if(!Pair(begin+i*16,object))return false;
        if(Ptr(object)==vft){if(out)return false;out=object;}}
    return out && Ptr(out+8)==actor;
}
enum AnchorFailure : unsigned {AnchorQuery=1,AnchorAttributes=2,AnchorProtection=3,AnchorSpan=4,AnchorBytes=5,
    AnchorState=6,AnchorType=7,AnchorAllocationBase=8,AnchorGuard=9,AnchorNoAccess=10};
template<class Query,class Compare>
inline bool ExecutableAnchorWith(uintptr_t base,const Anchor& a,unsigned* failure,Query query,Compare compare) noexcept {
    MEMORY_BASIC_INFORMATION region{};const auto at=base+a.rva;
    if(query(reinterpret_cast<void*>(at),&region,sizeof(region))!=sizeof(region)){
        if(failure)*failure=AnchorQuery;return false;}
    if(region.State!=MEM_COMMIT){if(failure)*failure=AnchorState;return false;}
    if(region.Type!=MEM_IMAGE){if(failure)*failure=AnchorType;return false;}
    if(reinterpret_cast<uintptr_t>(region.AllocationBase)!=base){if(failure)*failure=AnchorAllocationBase;return false;}
    if(region.Protect&PAGE_GUARD){if(failure)*failure=AnchorGuard;return false;}
    if((region.Protect&0xff)==PAGE_NOACCESS){if(failure)*failure=AnchorNoAccess;return false;}
    const DWORD protection=region.Protect&0xff;
    if(protection!=PAGE_EXECUTE_READ && protection!=PAGE_EXECUTE_READWRITE && protection!=PAGE_EXECUTE_WRITECOPY){
        if(failure)*failure=AnchorProtection;return false;}
    const auto low=reinterpret_cast<uintptr_t>(region.BaseAddress);
    if(at<low || a.size>region.RegionSize || at-low>region.RegionSize-a.size){
        if(failure)*failure=AnchorSpan;return false;}
    if(compare(reinterpret_cast<void*>(at),a.bytes,a.size)!=0){
        if(failure)*failure=AnchorBytes;return false;}
    return true;
}
inline bool ExecutableAnchorObserved(uintptr_t base,const Anchor& a,unsigned& failure) noexcept {
    return ExecutableAnchorWith(base,a,&failure,VirtualQuery,memcmp);
}
inline bool ExecutableAnchor(uintptr_t base,const Anchor& a) noexcept {
    return ExecutableAnchorWith(base,a,nullptr,VirtualQuery,memcmp);
}
inline bool IdentityNow(Identity& result) noexcept {
    const auto& wanted=host.plan.owner;DWORD pid=0;
    const DWORD thread=GetWindowThreadProcessId(reinterpret_cast<HWND>(wanted.hwnd),&pid);
    FILETIME create{},exit{},kernel{},user{};
    if(!IsWindow(reinterpret_cast<HWND>(wanted.hwnd)) || pid!=GetCurrentProcessId() || pid!=wanted.pid ||
       thread!=wanted.thread || GetCurrentThreadId()!=wanted.thread ||
       !GetProcessTimes(GetCurrentProcess(),&create,&exit,&kernel,&user))return false;
    result={pid,thread,(static_cast<uint64_t>(create.dwHighDateTime)<<32)|create.dwLowDateTime,wanted.hwnd,wanted.base};
    return Same(result,wanted);
}
struct Engine {
    bool Observe(Observed& o) noexcept {
        __try {
            if(!IdentityNow(o.owner) || !host.source || !host.source(o.owner.base))return false;
            for(const auto& a:anchors)if(!ExecutableAnchor(o.owner.base,a))return false;
            o.sourceVerified=true;const auto b=o.owner.base;
            const auto root=Ptr(b+0x1668790);
            if(!Canonical(root) || !*reinterpret_cast<uint8_t*>(root+0xd8))return false;
            const auto gi=Ptr(root+0xd0);uintptr_t begin=0;size_t count=0;
            if(!Canonical(gi) || !Vector(gi+0x180,128,begin,count))return false;
            uintptr_t state=0,actors=0;
            for(size_t i=0;i<count;++i){uintptr_t obj=0;if(!Pair(begin+i*16,obj))return false;
                const auto vft=Ptr(obj);
                if(vft==b+0x1182e30){if(state)return false;state=obj;}
                if(vft==b+0x117ead8){if(actors)return false;actors=obj;}}
            if(!state || !actors || *reinterpret_cast<uint32_t*>(state+0x380)!=5 || Ptr(state+0x370))return false;
            uintptr_t land=0;
            if(!Pair(state+0x360,land) || Ptr(land)!=b+0x1186f18 || *reinterpret_cast<uint32_t*>(land+0x10)!=5)return false;
            o.land=true;
            if(!Vector(actors+0x8a8,512,begin,count))return false;
            for(size_t i=0;i<count;++i){uintptr_t obj=0;if(!Pair(begin+i*16,obj))return false;
                if(Ptr(obj)==b+0x11819f0){if(o.actor)return false;o.actor=obj;}}
            if(!o.actor || !Component(o.actor,b+0x1181738,o.transform) || !Component(o.actor,b+0x1181010,o.controller))return false;
            o.uid=*reinterpret_cast<uint64_t*>(o.actor+0x18);
            o.grid0=*reinterpret_cast<int32_t*>(o.transform+0x40);o.grid1=*reinterpret_cast<int32_t*>(o.transform+0x44);
            o.idle=Ptr(o.controller+0x58)==0 && *reinterpret_cast<uint32_t*>(o.controller+0x60)==0;
            return WorldValid(host.plan,o);
        } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
    }
    // ClearCandidate is source-bound tile-only eligibility for a command test.
    // BA890/BA9F0 retains the complete original branch and movement decision.
    TileGate TileEvidenceFor(const Plan& p,const Observed& o) noexcept {
        __try {return host.tile?host.tile(p,o):TileGate::Unknown;}
        __except(EXCEPTION_EXECUTE_HANDLER){return TileGate::Unknown;}
    }
    bool ConstructOriginal(Coordinate& out,uint64_t packed,uint32_t type) noexcept {
        __try {using Ctor=void(__fastcall*)(Coordinate*,uint64_t,uint32_t);
            reinterpret_cast<Ctor>(host.plan.owner.base+0x52f320)(&out,packed,type);return true;
        } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
    }
    bool InvokeOriginal(uintptr_t controller,const Coordinate& out) noexcept {
        __try {using Command=void(__fastcall*)(void*,const Coordinate*);
            reinterpret_cast<Command>(host.plan.owner.base+0xa2c50)(reinterpret_cast<void*>(controller),&out);return true;
        } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
    }
};
static LRESULT CALLBACK GetMessage(int code,WPARAM remove,LPARAM raw) {
    const auto held=hook.load();
    if(code>=0 && remove==PM_REMOVE && raw){auto* msg=reinterpret_cast<MSG*>(raw);
        if(msg->hwnd==reinterpret_cast<HWND>(host.plan.owner.hwnd) && msg->message==messageId.load()){
            const bool validPayload=msg->wParam==0 && msg->lParam==0;msg->message=WM_NULL;
            Engine engine;const auto result=attempt.Run(host.plan,validPayload,engine);
            __try {if(host.report)host.report(result);}
            __except(EXCEPTION_EXECUTE_HANDLER) {}
            if(held){UnhookWindowsHookEx(held);hook.store(nullptr);}
        }}
    return CallNextHookEx(held,code,remove,raw);
}
// Preferred root integration: consume the new message inside its already
// reviewed CP47 WH_GETMESSAGE callback, kept alive through Land. No new hook.
// Root still owns its existing CallNextHookEx and final unhook/cleanup.
inline bool HandleExistingMessage(int code,WPARAM remove,LPARAM raw,const Host& supplied) noexcept {
    if(code<0 || remove!=PM_REMOVE || !raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);
    const auto id=RegisterWindowMessageW(L"LC-Owned-One-Move-Command-CP61");
    if(id<0xc000 || id>0xffff || msg->message!=id || msg->hwnd!=reinterpret_cast<HWND>(supplied.plan.owner.hwnd))return false;
    const bool validPayload=msg->wParam==0 && msg->lParam==0;msg->message=WM_NULL;
    Result result=Result::InvalidPlan;
    if(installationAttempted.exchange(true)){result=Result::Replay;}
    else if(PlanValid(supplied.plan) && supplied.tile && supplied.source && supplied.report){
        host=supplied;Engine engine;result=attempt.Run(host.plan,validPayload,engine);
    }
    __try {if(supplied.report)supplied.report(result);}
    __except(EXCEPTION_EXECUTE_HANDLER) {}
    return true;
}
inline bool Install(const Host& supplied) noexcept {
    if(installationAttempted.exchange(true) || !PlanValid(supplied.plan) || !supplied.tile || !supplied.source || !supplied.report)return false;
    host=supplied;Identity same{};
    if(!IdentityNow(same))return false;
    Engine engine;Observed before{};
    if(!engine.Observe(before))return false;
    const auto id=RegisterWindowMessageW(L"LC-Owned-One-Move-Command-CP61");
    if(id<0xc000 || id>0xffff)return false;
    messageId.store(id);
    const auto installed=SetWindowsHookExW(WH_GETMESSAGE,GetMessage,nullptr,supplied.plan.owner.thread);
    hook.store(installed);return installed!=nullptr;
}
inline void Cleanup() noexcept {const auto held=hook.exchange(nullptr);if(held)UnhookWindowsHookEx(held);}
}
