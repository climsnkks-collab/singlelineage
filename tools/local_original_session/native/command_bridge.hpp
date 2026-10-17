#pragma once
// Included after the frozen AutoOk helpers. No external pointer/function input.
#pragma warning(push)
#pragma warning(disable:4505)
#include "tools/local_native_land_move_hook/move_bridge.hpp"
#pragma warning(pop)

namespace internal_command {
struct Request {uint32_t pid=0,seq=0,command=0;uint64_t birth=0,uid=0;int32_t x=0,y=0;char hash[65]{};};
struct Reply {const char* status="REFUSED";unsigned reason=6;bool invoked=false;};
static std::atomic<unsigned> lastSequence{0};
static std::atomic<bool> busy{false};
static std::atomic<DWORD> uiThread{0};
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
    if(r.command<1 || r.command>4 || (r.command!=4 && (r.uid || r.x || r.y)) || (r.command==4 && !r.uid))return 1;
    return 0;
}
inline bool Read(const forward_diagnostic::Context& c,Request& request) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\command-request.json",c.directory);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,request);
}
inline bool AtomicOutput(const forward_diagnostic::Context& c,const wchar_t* leaf,const char* text,int size) noexcept {
    if(size<=0 || size>2048)return false;wchar_t path[600]{},temporary[600]{};
    swprintf_s(path,L"%s\\%s",c.directory,leaf);swprintf_s(temporary,L"%s\\%s.tmp",c.directory,leaf);
    HANDLE file=CreateFileW(temporary,GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(size),&written,nullptr) && written==static_cast<DWORD>(size);
    const BOOL closed=CloseHandle(file);
    return ok && closed && MoveFileExW(temporary,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
}
inline void Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {
    char text[768]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-internal-command-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":%u,\"status\":\"%s\",\"reason\":%u,\"invoked\":%s}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,r.command,reply.status,reply.reason,reply.invoked?"true":"false");
    AtomicOutput(c,L"command-result.json",text,n);
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
#include "tools/local_original_session/native/quit_command.hpp"
struct ActorPins {Pair actor{},transform{},controller{};uint64_t uid=0;int32_t x=0,y=0;};
inline bool ObserveMove(const Pins& pins,uint64_t uid,ActorPins& out) noexcept {
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
           *reinterpret_cast<uintptr_t*>(c+0x58) || *reinterpret_cast<uint32_t*>(c+0x60))return false;
        out.uid=uid;out.x=*reinterpret_cast<int32_t*>(t+0x40);out.y=*reinterpret_cast<int32_t*>(t+0x44);return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
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
inline Reply Execute(const Request& request) noexcept {
    if(request.command==3)return quit_detail::Execute();
    if(request.command==4 && (request.x<0||request.x>65535||request.y<0||request.y>65535))return {"REFUSED",1,false};
    const unsigned scene=request.command==1?3:request.command==2?4:5;Pins pins;unsigned reason=0;
    const bool found=Find(pins,scene,reason);
    Held ui{pins.ui},state{pins.state},sceneOwner{pins.scene},layout{pins.layout},actors{pins.actors};
    if(!found || !Stable(pins,scene))return {"REFUSED",reason?reason:5,false};
    if(request.command==1){
        const bool valid=AutoOkValidated(pins.layout.object,pins.button,reason);
        const bool invoked=valid&&AutoOkInvoke(pins.button);
        return {invoked?"RETURNED":"REFUSED",invoked?0u:valid?7u:6u,invoked};
    }
    if(request.command==2){
        if(!CharacterSlotValidated(pins.layout.object,pins.button,reason))return {"REFUSED",6,false};
        if(!CharacterSlotInvoke(pins.button))return {"REFUSED",7,false};
        if(!Stable(pins,4))return {"REFUSED",5,true};
        const bool invoked=CharacterSelectOkInvoke(pins.layout.object,reason,true);
        return {invoked?"RETURNED":"REFUSED",invoked?0u:7u,true};
    }
    ActorPins first;const bool observed=ObserveMove(pins,request.uid,first);
    Held actor{first.actor},transform{first.transform},controller{first.controller};
    if(!observed || (first.x==request.x&&first.y==request.y))return {"REFUSED",6,false};
    original_move::Coordinate goal{};
    if(!Construct(goal,request.x,request.y)||goal.grid0!=request.x||goal.grid1!=request.y||
       goal.segment0!=(request.x>>6)+0x7e00||goal.segment1!=(request.y>>6)+0x7e00)return {"REFUSED",7,false};
    Pins current;unsigned currentReason=0;const bool currentFound=Find(current,5,currentReason);
    Held uiAgain{current.ui},stateAgain{current.state},sceneAgain{current.scene},layoutAgain{current.layout},actorsAgain{current.actors};
    if(!currentFound || current.state.object!=pins.state.object || current.state.control!=pins.state.control ||
       current.scene.object!=pins.scene.object || current.scene.control!=pins.scene.control ||
       current.actors.object!=pins.actors.object || current.actors.control!=pins.actors.control)return {"REFUSED",5,false};
    ActorPins last;const bool rechecked=ObserveMove(current,request.uid,last);
    Held actorAgain{last.actor},transformAgain{last.transform},controllerAgain{last.controller};
    if(!rechecked || first.actor.object!=last.actor.object || first.actor.control!=last.actor.control ||
       first.transform.object!=last.transform.object || first.transform.control!=last.transform.control ||
       first.controller.object!=last.controller.object || first.controller.control!=last.controller.control ||
       first.x!=last.x || first.y!=last.y)return {"REFUSED",6,false};
    const bool invoked=Move(last.controller.object,goal);
    return {invoked?"RETURNED":"REFUSED",invoked?0u:7u,invoked};
}
template<class Run> inline Reply Dispatch(const Request& request,unsigned posted,const forward_diagnostic::Context& context,
        bool correctThread,bool payload,Run run) noexcept {
    unsigned reason=Authorize(request,posted,context,correctThread,lastSequence.load(),busy.load());
    if(!payload)reason=1;
    if(reason)return {"REFUSED",reason,false};
    lastSequence=request.seq;busy=true;const auto reply=run(request);busy=false;return reply;
}
inline void Handle(unsigned posted,bool payload) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context context{};
    if(!forward_diagnostic::context(context)){SetLastError(before);return;}
    Request request;
    if(!Read(context,request)){request.seq=posted;Output(context,request,{"REFUSED",1,false});SetLastError(before);return;}
    const bool correct=GetCurrentThreadId()==uiThread.load() && BackgroundGuardCurrentDesktop();
    const auto reply=Dispatch(request,posted,context,correct,payload,Execute);
    Output(context,request,reply);SetLastError(before);
}
static LRESULT CALLBACK GetMessage(int code,WPARAM remove,LPARAM raw) {
    const auto hook=autoOkHook.load();
    if(code>=0&&remove==PM_REMOVE&&raw){auto* message=reinterpret_cast<MSG*>(raw);
        if(message->hwnd==autoOkWindow.load() && message->message==autoOkMessage.load()){
            const auto seq=message->wParam;const bool payload=message->lParam==0 && seq>0 && seq<=2147483647;
            message->message=WM_NULL;message->wParam=0;message->lParam=0;
            if(seq>0&&seq<=2147483647)Handle(static_cast<unsigned>(seq),payload);
        }}
    return CallNextHookEx(hook,code,remove,raw);
}
struct WindowChoice {HWND hwnd=nullptr;DWORD thread=0;unsigned count=0;};
inline HWND KnownWindow() noexcept {
    const uintptr_t b=scope.base;uintptr_t window=0,vft=0,host=0,slot=0;HWND hwnd=nullptr;
    if(!b || forwardBinding.base.load()!=b || !scope.selectedReady.load() ||
       !SafeCopy(&window,reinterpret_cast<void*>(b+0x17f0d18),8) || !AutoOkCanonical(window) ||
       !SafeCopy(&vft,reinterpret_cast<void*>(window),8) || vft!=b+0x123a7d8 ||
       !SafeCopy(&slot,reinterpret_cast<void*>(vft+0x50),8) || slot!=b+0xb88fd0 ||
       !SafeCopy(&slot,reinterpret_cast<void*>(vft+0xd8),8) || slot!=b+0xb86fd0 ||
       !SafeCopy(&host,reinterpret_cast<void*>(window+0x80),8) || !AutoOkCanonical(host) ||
       !SafeCopy(&slot,reinterpret_cast<void*>(host+0x320),8) || slot!=b+0xb8b1f0 ||
       !SafeCopy(&slot,reinterpret_cast<void*>(host+0x328),8) || slot!=b+0xb8ac40 ||
       !SafeCopy(&hwnd,reinterpret_cast<void*>(host+0x368),sizeof(hwnd)))return nullptr;
    return hwnd;
}
static BOOL CALLBACK FindWindow(HWND hwnd,LPARAM raw) {
    auto* choice=reinterpret_cast<WindowChoice*>(raw);DWORD pid=0;
    const DWORD thread=GetWindowThreadProcessId(hwnd,&pid);wchar_t name[32]{};
    if(pid!=GetCurrentProcessId() || !thread || GetClassNameW(hwnd,name,32)<=0 || wcscmp(name,L"GLFW30"))return TRUE;
    RECT rectangle{};if(!GetClientRect(hwnd,&rectangle))return TRUE;
    const LONG width=rectangle.right-rectangle.left,height=rectangle.bottom-rectangle.top;
    if(width<320||width>7680||height<200||height>4320)return TRUE;
    ++choice->count;choice->hwnd=hwnd;choice->thread=thread;return TRUE;
}
inline void Install() noexcept {
    const DWORD before=GetLastError();if(autoOkInstallAttempted.exchange(true)){SetLastError(before);return;}
    forward_diagnostic::Context context{};
    if(!forward_diagnostic::context(context)||!BackgroundGuardCurrentDesktop()){SetLastError(before);return;}
    const auto guard=BackgroundGuardReadSnapshot();
    const bool protectedExports=guard.installed && guard.protected_exports==18 &&
        (guard.hooks_count==17 || guard.hooks_count==18);
    WindowChoice choice{};const auto desktop=GetThreadDesktop(GetCurrentThreadId());
    const HWND known=protectedExports?KnownWindow():nullptr;
    const bool enumerated=protectedExports && desktop && EnumDesktopWindows(desktop,FindWindow,reinterpret_cast<LPARAM>(&choice));
    DWORD pid=0;const DWORD thread=choice.hwnd?GetWindowThreadProcessId(choice.hwnd,&pid):0;
    const bool window=protectedExports && enumerated && choice.count==1 && known && known==choice.hwnd &&
        KnownWindow()==known && pid==GetCurrentProcessId() && thread==choice.thread && BackgroundGuardCurrentDesktop();
    const UINT message=window?RegisterWindowMessageW(L"LC-Owned-Internal-Command-v1"):0;
    if(window && message>=0xc000){autoOkWindow=choice.hwnd;autoOkMessage=message;uiThread=choice.thread;
        autoOkHook=SetWindowsHookExW(WH_GETMESSAGE,GetMessage,nullptr,choice.thread);}
    char text[896]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-internal-command-bridge-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"ready\":%s,\"message\":%u,\"window\":%llu,\"thread_id\":%lu,\"supported_commands\":[1,2,3,4],\"background_guard_installed\":%s,\"hooks_count\":%lu,\"protected_exports\":%lu,\"blocked_display_calls\":%lld,\"blocked_input_calls\":%lld}\n",
        context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,autoOkHook.load()?"true":"false",message,
        static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(choice.hwnd)),choice.thread,
        guard.installed?"true":"false",guard.hooks_count,guard.protected_exports,guard.blocked_display_calls,guard.blocked_input_calls);
    AtomicOutput(context,L"command-bridge.json",text,n);SetLastError(before);
}
}
static void InstallAutoOkHook() noexcept {internal_command::Install();}
