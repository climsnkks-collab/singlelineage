#pragma once
// Manual 1d1f additive movement only. Existing pinned Pair/Held/MoveGoal contract.
#pragma warning(push)
#pragma warning(disable:4505)
#include "tools/local_native_land_move_hook/move_bridge.hpp"
#pragma warning(pop)
#include "move_command_policy.hpp"
namespace manual_move {
struct Request {uint32_t pid=0,seq=0,command=0;uint64_t birth=0,uid=0;int32_t x=0,y=0;char hash[65]{};};
struct Reply {const char* status="REFUSED";unsigned reason=6;bool invoked=false;};
static std::atomic<unsigned> lastSequence{0};
static std::atomic<bool> busy{false};
static std::atomic<bool> terminal{false};
static std::atomic<DWORD> uiThread{0};
// Written once before hook publication; no reset/rearm within a DLL lifetime.
static forward_diagnostic::Context owner{};
static bool ownerBound=false;
inline void BindOwner() noexcept {
    ownerBound=forward_diagnostic::context(owner);
    if(!ownerBound)terminal.store(true);
}
inline bool SameOwner(const forward_diagnostic::Context& c) noexcept {
    return ownerBound && c.pid==owner.pid && c.birth==owner.birth &&
        !wcscmp(c.directory,owner.directory);
}
inline bool CorrectThread(const forward_diagnostic::Context& c) noexcept {
    DWORD pid=0;const HWND window=autoOkWindow.load();
    const DWORD thread=GetWindowThreadProcessId(window,&pid);
    return IsWindow(window) && thread && thread==uiThread.load() &&
        thread==GetCurrentThreadId() && pid==c.pid;
}
inline bool OwnedNow() noexcept {
    forward_diagnostic::Context c{};
    return forward_diagnostic::context(c) && SameOwner(c) && CorrectThread(c);
}
inline bool Literal(const char*& p,const char* value) noexcept {
    const auto n=strlen(value);if(strncmp(p,value,n))return false;p+=n;return true;
}
inline bool Number(const char*& p,uint64_t limit,uint64_t& value) noexcept {
    if(*p<'0'||*p>'9')return false;const char* start=p;value=0;
    while(*p>='0'&&*p<='9'){const unsigned digit=static_cast<unsigned>(*p-'0');
        if(value>limit/10 || (value==limit/10 && digit>limit%10))return false;
        value=value*10+digit;++p;}
    return p-start==1 || *start!='0';
}
inline bool Signed(const char*& p,int32_t& out) noexcept {
    const bool negative=*p=='-';if(negative)++p;uint64_t value=0;
    if(!Number(p,negative?2147483648ull:2147483647ull,value) || (negative && !value))return false;
    out=negative?static_cast<int32_t>(-static_cast<int64_t>(value)):static_cast<int32_t>(value);return true;
}
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0,command=0;
    if(!Literal(p,"{\"schema\":\"own-internal-command-v1\",\"pid\":") || !Number(p,UINT32_MAX,pid) ||
       !Literal(p,",\"birth\":") || !Number(p,UINT64_MAX,r.birth) || !Literal(p,",\"candidate_sha256\":\""))return false;
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!Literal(p,"\",\"seq\":") || !Number(p,2147483647,seq) || !seq ||
       !Literal(p,",\"command\":") || !Number(p,4,command) || !command ||
       !Literal(p,",\"uid\":") || !Number(p,UINT64_MAX,r.uid) ||
       !Literal(p,",\"x\":") || !Signed(p,r.x) || !Literal(p,",\"y\":") || !Signed(p,r.y) ||
       !Literal(p,"}"))return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);r.command=static_cast<uint32_t>(command);return true;
}
inline unsigned Authorize(const Request& r,unsigned posted,const forward_diagnostic::Context& c,
        bool correctThread,unsigned previous,bool occupied) noexcept {
    if(r.pid!=c.pid || r.birth!=c.birth || strcmp(r.hash,OWN_EXPECTED_PROGRAM_SHA))return 2;
    if(!r.seq || r.seq!=posted || r.seq<=previous)return 3;
    if(!correctThread)return 4;if(occupied)return 9;
    if(r.command!=4 || !r.uid || r.x<0 || r.x>65535 || r.y<0 || r.y>65535)return 1;
    return 0;
}
inline bool Read(const forward_diagnostic::Context& c,Request& request) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\manual-move-request.json",c.directory);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,request);
}
struct Pins {Pair ui{},state{},scene{},layout{},actors{};void* button=nullptr;};
inline bool Hold(Pair p,Pair& out) noexcept {
    if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)) || !AutoOkCanonical(reinterpret_cast<uintptr_t>(p.control)))return false;
    __try {if(*reinterpret_cast<volatile LONG*>(static_cast<unsigned char*>(p.control)+8)<=0)return false;Retain(p);out=p;return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline bool Find(Pins& pins,unsigned expected,unsigned& reason) noexcept {
    reason=5;const auto b=scope.base;
    __try {
        if(!b || !scope.selectedReady.load() || forwardBinding.base.load()!=b)return false;
        auto* root=*reinterpret_cast<uint8_t**>(b+0x1668790);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) || !root[0xd8])return false;
        auto* gi=*reinterpret_cast<uint8_t**>(root+0xd0);if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(gi)))return false;
        const auto begin=*reinterpret_cast<uintptr_t*>(gi+0x180),end=*reinterpret_cast<uintptr_t*>(gi+0x188);
        if(!AutoOkCanonical(begin)||end<begin||(end-begin)%16||(end-begin)/16>128)return false;
        Pair ui{},state{},actors{};
        for(auto at=begin;at<end;at+=16){const auto p=*reinterpret_cast<Pair*>(at);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)))return false;
            const auto v=*reinterpret_cast<uintptr_t*>(p.object);
            if(v==b+0x1182c50){if(ui.object)return false;ui=p;}
            if(v==b+0x1182e30){if(state.object)return false;state=p;}
            if(v==b+0x117ead8){if(actors.object)return false;actors=p;}}
        if(!Hold(ui,pins.ui)||!Hold(state,pins.state))return false;
        auto* s=static_cast<uint8_t*>(state.object);const auto current=*reinterpret_cast<Pair*>(s+0x360);
        if(*reinterpret_cast<uintptr_t*>(s+0x370)||*reinterpret_cast<uintptr_t*>(s+0x378)||
           *reinterpret_cast<uint32_t*>(s+0x380)!=expected || !Hold(current,pins.scene))return false;
        const uintptr_t sceneVft=expected==3?0x1187f48:expected==4?0x1187778:0x1186f18;
        if(*reinterpret_cast<uintptr_t*>(current.object)!=b+sceneVft ||
           *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(current.object)+0x10)!=expected)return false;
        if(expected==5){if(!Hold(actors,pins.actors))return false;reason=0;return true;}
        reason=6;auto* u=static_cast<uint8_t*>(ui.object);
        const auto head=*reinterpret_cast<uintptr_t*>(u+0x350),count=*reinterpret_cast<uintptr_t*>(u+0x358);
        if(!AutoOkCanonical(head)||!count||count>64)return false;
        auto node=*reinterpret_cast<uintptr_t*>(head);Pair found{};
        const auto layoutVft=b+(expected==3?0x1230558:0x1214f58);
        for(uintptr_t i=0;i<count;++i){if(!AutoOkCanonical(node)||node==head)return false;
            const auto p=*reinterpret_cast<Pair*>(node+0x30);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)))return false;
            if(*reinterpret_cast<uintptr_t*>(p.object)==layoutVft){if(found.object)return false;found=p;}
            node=*reinterpret_cast<uintptr_t*>(node);}
        if(node!=head || !Hold(found,pins.layout))return false;
        pins.button=*reinterpret_cast<void**>(static_cast<uint8_t*>(found.object)+(expected==3?0xe0:0xc0));
        reason=0;return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){reason=6;return false;}
}
inline bool Stable(const Pins& pins,unsigned expected) noexcept {
    __try {auto* s=static_cast<uint8_t*>(pins.state.object);
        const auto current=*reinterpret_cast<Pair*>(s+0x360);
        return current.object==pins.scene.object && current.control==pins.scene.control &&
            !*reinterpret_cast<uintptr_t*>(s+0x370) && !*reinterpret_cast<uintptr_t*>(s+0x378) &&
            *reinterpret_cast<uint32_t*>(s+0x380)==expected;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
struct ActorPins {Pair actor{},transform{},controller{};uint64_t uid=0;int32_t x=0,y=0;move_command_policy::Pin command{};};
inline bool ObserveActor(const Pins& pins,uint64_t uid,ActorPins& out,
        bool(*command)(void*,uint64_t,move_command_policy::Pin&) noexcept) noexcept {
    __try {
        if(!Stable(pins,5))return false;const auto b=scope.base;
        for(const auto& anchor:original_move::anchors)
            if(((anchor.rva>=0x52f320&&anchor.rva<0x52f4b0)||(anchor.rva>=0xa2c50&&anchor.rva<0xa2d20)) &&
               !original_move::ExecutableAnchor(b,anchor))return false;
        uintptr_t begin=0;size_t count=0;
        if(!original_move::Vector(reinterpret_cast<uintptr_t>(pins.actors.object)+0x8a8,512,begin,count))return false;
        Pair actor{};
        for(size_t i=0;i<count;++i){const auto p=*reinterpret_cast<Pair*>(begin+i*16);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)))return false;
            if(*reinterpret_cast<uintptr_t*>(p.object)==b+0x11819f0){if(actor.object)return false;actor=p;}}
        if(!Hold(actor,out.actor)||*reinterpret_cast<uint64_t*>(static_cast<uint8_t*>(actor.object)+0x18)!=uid)return false;
        if(!original_move::Vector(reinterpret_cast<uintptr_t>(actor.object)+0x20,128,begin,count))return false;
        Pair transform{},controller{};
        for(size_t i=0;i<count;++i){const auto p=*reinterpret_cast<Pair*>(begin+i*16);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)))return false;
            const auto v=*reinterpret_cast<uintptr_t*>(p.object);
            if(v==b+0x1181738){if(transform.object)return false;transform=p;}
            if(v==b+0x1181010){if(controller.object)return false;controller=p;}}
        if(!Hold(transform,out.transform)||!Hold(controller,out.controller))return false;
        auto* t=static_cast<uint8_t*>(transform.object);auto* c=static_cast<uint8_t*>(controller.object);
        if(*reinterpret_cast<void**>(t+8)!=actor.object || *reinterpret_cast<void**>(c+8)!=actor.object ||
           !command(c,uid,out.command))return false;
        out.uid=uid;out.x=*reinterpret_cast<int32_t*>(t+0x40);out.y=*reinterpret_cast<int32_t*>(t+0x44);return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
// AttackTarget and its Fresh snapshots retain the original empty-only gate.
inline bool ObserveMove(const Pins& pins,uint64_t uid,ActorPins& out) noexcept {
    return ObserveActor(pins,uid,out,move_command_policy::Strict);
}
// Only the original MoveGoal setter is allowed to replace a typed AttackCommand.
inline bool ObserveMoveForSetter(const Pins& pins,uint64_t uid,ActorPins& out) noexcept {
    return ObserveActor(pins,uid,out,move_command_policy::Setter);
}
inline bool FinalPolicy(const Pins& pins,const ActorPins& actor,
        bool(*command)(void*,uint64_t,move_command_policy::Pin&) noexcept) noexcept {
    __try {
        const auto b=scope.base;move_command_policy::Pin current{};
        return b && scope.selectedReady.load() && forwardBinding.base.load()==b && Stable(pins,5) &&
            *reinterpret_cast<uintptr_t*>(actor.actor.object)==b+0x11819f0 &&
            *reinterpret_cast<uint64_t*>(static_cast<uint8_t*>(actor.actor.object)+0x18)==actor.uid &&
            *reinterpret_cast<void**>(static_cast<uint8_t*>(actor.controller.object)+8)==actor.actor.object &&
            *reinterpret_cast<void**>(static_cast<uint8_t*>(actor.transform.object)+8)==actor.actor.object &&
            *reinterpret_cast<int32_t*>(static_cast<uint8_t*>(actor.transform.object)+0x40)==actor.x &&
            *reinterpret_cast<int32_t*>(static_cast<uint8_t*>(actor.transform.object)+0x44)==actor.y &&
            command(actor.controller.object,actor.uid,current) && move_command_policy::Same(actor.command,current);
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline bool FinalMove(const Pins& pins,const ActorPins& actor) noexcept {
    return FinalPolicy(pins,actor,move_command_policy::Setter);
}
inline bool Construct(original_move::Coordinate& coordinate,int32_t x,int32_t y) noexcept {
    const uint64_t packed=(static_cast<uint64_t>(static_cast<uint32_t>(y))<<32)|static_cast<uint32_t>(x);
    __try {using Function=void(__fastcall*)(original_move::Coordinate*,uint64_t,uint32_t);
        reinterpret_cast<Function>(scope.base+0x52f320)(&coordinate,packed,5);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline bool Move(void* controller,const original_move::Coordinate& coordinate) noexcept {
    __try {using Function=void(__fastcall*)(void*,const original_move::Coordinate*);
        reinterpret_cast<Function>(scope.base+0xa2c50)(controller,&coordinate);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
// Pure substitution seam: production always supplies these same existing operations.
// Mock pins have null controls; no original engine call, window or thread is created.
struct EngineOps {
    bool(*owned)() noexcept=OwnedNow;
    bool(*find)(Pins&,unsigned,unsigned&) noexcept=Find;
    bool(*stable)(const Pins&,unsigned) noexcept=Stable;
    bool(*observe)(const Pins&,uint64_t,ActorPins&) noexcept=ObserveMoveForSetter;
    bool(*construct)(original_move::Coordinate&,int32_t,int32_t) noexcept=Construct;
    bool(*move)(void*,const original_move::Coordinate&) noexcept=Move;
    bool(*final)(const Pins&,const ActorPins&) noexcept=FinalMove;
};
inline Reply Execute(const Request& request,const EngineOps& ops=EngineOps{}) noexcept {
    if(terminal.load() || !ops.owned())return {"UNKNOWN",2,false};
    Pins pins;unsigned reason=0;const bool found=ops.find(pins,5,reason);
    Held ui{pins.ui},state{pins.state},sceneOwner{pins.scene},layout{pins.layout},actors{pins.actors};
    if(!found || !ops.stable(pins,5))return {"REFUSED",reason?reason:5,false};
    ActorPins first;const bool observed=ops.observe(pins,request.uid,first);
    Held actor{first.actor},transform{first.transform},controller{first.controller};
    if(!observed || (first.x==request.x&&first.y==request.y))return {"REFUSED",6,false};
    original_move::Coordinate goal{};
    if(!ops.construct(goal,request.x,request.y)||goal.grid0!=request.x||goal.grid1!=request.y||
       goal.segment0!=(request.x>>6)+0x7e00||goal.segment1!=(request.y>>6)+0x7e00)return {"REFUSED",7,false};
    Pins current;unsigned currentReason=0;const bool currentFound=ops.find(current,5,currentReason);
    Held uiAgain{current.ui},stateAgain{current.state},sceneAgain{current.scene},layoutAgain{current.layout},actorsAgain{current.actors};
    if(!currentFound || current.state.object!=pins.state.object || current.state.control!=pins.state.control ||
       current.scene.object!=pins.scene.object || current.scene.control!=pins.scene.control ||
       current.actors.object!=pins.actors.object || current.actors.control!=pins.actors.control)return {"REFUSED",5,false};
    ActorPins last;const bool rechecked=ops.observe(current,request.uid,last);
    Held actorAgain{last.actor},transformAgain{last.transform},controllerAgain{last.controller};
    if(!rechecked || first.actor.object!=last.actor.object || first.actor.control!=last.actor.control ||
       first.transform.object!=last.transform.object || first.transform.control!=last.transform.control ||
       first.controller.object!=last.controller.object || first.controller.control!=last.controller.control ||
       !move_command_policy::Same(first.command,last.command) ||
       first.x!=last.x || first.y!=last.y)return {"REFUSED",6,false};
    // Construct/observation can reenter the message loop. Revalidate ownership and
    // cancellation immediately before the only original MoveGoal invocation.
    if(terminal.load() || !ops.owned() || terminal.load() || !ops.final(current,last) || terminal.load())return {"UNKNOWN",2,false};
    const bool returned=ops.move(last.controller.object,goal);
    return {returned?"RETURNED":"UNKNOWN",returned?0u:7u,true};
}
inline Reply Guarded(const Request& request,const EngineOps& ops) noexcept {
    // Includes faults in legacy retained-pair release. Such a fault cannot prove
    // no invocation, or complete unwinding: terminal UNKNOWN, never retry/unload.
    __try {return Execute(request,ops);}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,true};}
}
inline Reply ExecuteGuarded(const Request& request) noexcept {return Guarded(request,EngineOps{});}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {
    char text[768]{};wchar_t path[600]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-manual-move-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":4,\"status\":\"%s\",\"reason\":%u,\"invoked\":%s}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,reply.status,reply.reason,reply.invoked?"true":"false");
    if(n<=0 || n>768)return false;
    swprintf_s(path,L"%s\\manual-move-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr) && written==static_cast<DWORD>(n);
    const BOOL closed=CloseHandle(file);return ok && closed;
}
struct Io {
    bool(*context)(forward_diagnostic::Context&) noexcept=forward_diagnostic::context;
    bool(*thread)(const forward_diagnostic::Context&) noexcept=CorrectThread;
    bool(*read)(const forward_diagnostic::Context&,Request&) noexcept=Read;
    Reply(*execute)(const Request&) noexcept=ExecuteGuarded;
    bool(*output)(const forward_diagnostic::Context&,const Request&,const Reply&) noexcept=Output;
};
inline void Process(unsigned posted,bool payload,const Io& io=Io{}) noexcept {
    if(terminal.load())return;
    bool free=false;
    if(!busy.compare_exchange_strong(free,true)){terminal.store(true);return;}
    struct BusyScope {~BusyScope(){busy.store(false);}} inFlight;
    forward_diagnostic::Context context{};
    if(!payload || !io.context(context) || !SameOwner(context) || !io.thread(context)){
        terminal.store(true);return; // No trusted current result identity: UNKNOWN externally.
    }
    const auto previous=lastSequence.load();
    if(posted<=previous)return; // Duplicate/stale: no read, invocation or immutable overwrite.
    lastSequence.store(posted); // Consume every new attempt BEFORE reading/invoking.
    Request request{};request.seq=posted;
    Reply reply{"UNKNOWN",6,false};
    if(io.read(context,request)){
        const unsigned reason=Authorize(request,posted,context,true,previous,false);
        if(!reason)reply=io.execute(request);
        else reply={"UNKNOWN",reason,false};
    }
    forward_diagnostic::Context after{};
    if(!io.context(after) || !SameOwner(after) || !io.thread(after)){
        terminal.store(true);return; // Invocation/result identity now UNKNOWN; no stale publication.
    }
    // A parser may have reset/partially filled request. Only the posted sequence
    // selects a result path; malformed/mismatched contents cannot claim another file.
    request.seq=posted;
    if(terminal.load())reply={"UNKNOWN",9,reply.invoked};
    if(strcmp(reply.status,"RETURNED") || !reply.invoked)terminal.store(true);
    if(!io.output(context,request,reply))terminal.store(true);
}
// Detach only at a quiescent callback boundary. Reentrant callbacks cannot clear
// the hook or release state while the outer original engine call is on stack.
template<class Unhook>
inline void DetachTerminal(std::atomic<HHOOK>& slot,Unhook unhook) noexcept {
    if(terminal.load() && !busy.load()){
        const HHOOK hook=slot.exchange(nullptr);
        if(hook)unhook(hook); // Failure stays terminal; no reinstall/retry.
    }
}
inline bool Matches(int code,WPARAM remove,const MSG* msg,UINT id,HWND window) noexcept {
    return code>=0 && remove==PM_REMOVE && msg && id>=0xc000 && id<=0xffff &&
        msg->message==id && msg->hwnd==window;
}
inline void ObserveEnd(int code,WPARAM remove,const MSG* msg,HWND window) noexcept {
    if(code>=0 && remove==PM_REMOVE && msg && (msg->message==WM_QUIT ||
       (msg->hwnd==window && (msg->message==WM_DESTROY || msg->message==WM_NCDESTROY))))terminal.store(true);
}
template<class Unhook,class Next>
inline LRESULT Forward(HHOOK captured,int code,WPARAM remove,LPARAM raw,
        Unhook unhook,Next next) noexcept {
    DetachTerminal(autoOkHook,unhook);
    // Unhook only removes future dispatch. The current callback and static DLL
    // storage remain resident; captured HHOOK follows the existing CallNext path.
    return next(captured,code,remove,raw);
}
inline bool Handle(int code,WPARAM remove,LPARAM raw) noexcept {
    if(code<0 || remove!=PM_REMOVE || !raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);const UINT id=RegisterWindowMessageW(L"LC-Owned-Manual-Move-v1");
    if(!Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const auto posted=msg->wParam;const bool payload=msg->lParam==0 && posted>0 && posted<=2147483647;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD before=GetLastError();
    Process(payload?static_cast<unsigned>(posted):0,payload);
    SetLastError(before);return true;
}
}
