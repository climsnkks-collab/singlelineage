#pragma once
// Fixed original UI callbacks, dispatched by the retained owned UI thread.
// RETURNED means callback return only. Rendering and server effects stay UNKNOWN.
namespace ui_open_bridge {
inline constexpr uintptr_t MagicShortcutRva=0x15eaf0;
inline constexpr uintptr_t StatsShortcutRva=0x15ebf0;
inline constexpr uintptr_t HotbarSubsystemGetterRva=0x9dc8d0;
inline constexpr uintptr_t HotbarDispatchRva=0x59b630;
inline constexpr uintptr_t ActorLookupRva=0x627b0;
inline constexpr uintptr_t PetRequestRva=0xb8710;
inline constexpr unsigned HotbarSlotsPerPage=8;
enum class Command : unsigned { Magic=1, Stats=2, Pet=3, Hotbar=4 };
struct Request {uint32_t pid=0,seq=0,slot=0;uint64_t birth=0,target=0;char hash[65]{};Command command=Command::Magic;};
struct Result {const char* status="REFUSED";unsigned reason=6;bool invoked=false;const char* action="none";};
inline const char* Name(Command command) noexcept {
    switch(command){case Command::Magic:return "open_magic_window";case Command::Stats:return "open_stats_window";
    case Command::Pet:return "open_pet_window";case Command::Hotbar:return "hotbar_cast";}return "unknown";
}
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0,slot=0;
    if(!manual_move::Literal(p,"{\"schema\":\"own-ui-open-request-v1\",\"pid\":") || !manual_move::Number(p,UINT32_MAX,pid) ||
       !manual_move::Literal(p,",\"birth\":") || !manual_move::Number(p,UINT64_MAX,r.birth) ||
       !manual_move::Literal(p,",\"candidate_sha256\":\""))return false;
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!manual_move::Literal(p,"\",\"seq\":") || !manual_move::Number(p,2147483647,seq) || !seq ||
       !manual_move::Literal(p,",\"command\":\""))return false;
    bool matched=false;
    for(unsigned value=1;value<=4;++value){const auto command=static_cast<Command>(value);const char* next=p;
        if(manual_move::Literal(next,Name(command)) && manual_move::Literal(next,"\"")){r.command=command;p=next;matched=true;break;}}
    if(!matched || !manual_move::Literal(p,",\"slot\":") || !manual_move::Number(p,HotbarSlotsPerPage-1,slot) ||
       (r.command!=Command::Hotbar && slot) || !manual_move::Literal(p,",\"target_uid\":") ||
       !manual_move::Number(p,UINT64_MAX,r.target) || (r.command==Command::Pet?!r.target:r.target!=0) ||
       !manual_move::Literal(p,"}"))return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);r.slot=static_cast<uint32_t>(slot);return true;
}
inline bool Read(const forward_diagnostic::Context& c,unsigned seq,Request& r) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\ui-open-request-%u.json",c.directory,seq);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,r);
}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Result& result) noexcept {
    char text[896]{};const int n=sprintf_s(text,
        "{\"schema\":\"own-ui-open-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":\"%s\",\"slot\":%u,\"target_uid\":%llu,\"status\":\"%s\",\"reason\":%u,\"invoked\":%s,\"action\":\"%s\",\"window_state\":\"UNKNOWN\",\"effect\":\"UNKNOWN\"}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,Name(r.command),r.slot,static_cast<unsigned long long>(r.target),
        result.status,result.reason,result.invoked?"true":"false",result.action);
    if(n<=0 || n>=896)return false;wchar_t path[600]{};swprintf_s(path,L"%s\\ui-open-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr) && written==static_cast<DWORD>(n) && FlushFileBuffers(file);
    const BOOL closed=CloseHandle(file);return ok && closed;
}
inline Result InvokeToggle(uintptr_t entry) noexcept {
    // These whole original shortcut callbacks own manager/any lifetimes.
    // Both ignore incoming arguments and select original command2 (toggle).
    __try {using Callback=void(__fastcall*)();reinterpret_cast<Callback>(entry)();return {"RETURNED",0,true,"toggle"};}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,true,"toggle"};}
}
inline bool LookupActor(void* actors,uint64_t uid,Pair& pair) noexcept {
    // Existing spell-whole-entry/drop_reference.hpp uses this exact fullUID ABI.
    __try {using Lookup=Pair*(__fastcall*)(void*,Pair*,uint64_t);
        return reinterpret_cast<Lookup>(scope.base+ActorLookupRva)(actors,&pair,uid)==&pair;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline Result InvokePet(void* actor) noexcept {
    // Whole original interaction callee preserves its current/target guards and
    // reads the request's low32 actor ID itself. No packet or Actor is forged.
    __try {using RequestPet=void(__fastcall*)(void*);
        reinterpret_cast<RequestPet>(scope.base+PetRequestRva)(actor);return {"RETURNED",0,true,"pet_request"};}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,true,"pet_request"};}
}
inline Result Native(const Request& r) noexcept {
    // Original59B630 traps on a missing current-page slotkey. The real UI
    // caller supplies an existing SlotNode's metadata index, absent here.
    // Keep the discovered addresses as evidence; do not guess that precondition.
    if(r.command==Command::Hotbar)return {"UNSUPPORTED",8,false,"none"};
    manual_move::Pins pins{};unsigned reason=0;const bool found=manual_move::Find(pins,5,reason);
    Held ui{pins.ui},state{pins.state},scene{pins.scene},layout{pins.layout},actors{pins.actors};
    if(!found || !manual_move::Stable(pins,5))return {"REFUSED",reason?reason:5,false,"none"};
    if(r.command==Command::Pet){
        Pair target{};if(!LookupActor(pins.actors.object,r.target,target))return {"UNKNOWN",7,false,"none"};
        Held retained{target};
        if(!target.object || !target.control)return {"REFUSED",6,false,"none"};
        return InvokePet(target.object);
    }
    // Static original InitUIShortcut entries: lambda4=Magic, next=Stats.
    return InvokeToggle(scope.base+(r.command==Command::Magic?MagicShortcutRva:StatsShortcutRva));
}
inline unsigned Authorize(const Request& r,unsigned seq,const forward_diagnostic::Context& c,unsigned previous) noexcept {
    if(r.pid!=c.pid || r.birth!=c.birth || strcmp(r.hash,OWN_EXPECTED_PROGRAM_SHA))return 2;
    if(!r.seq || r.seq!=seq || r.seq<=previous)return 3;
    return 0;
}
inline void Process(unsigned seq,bool payload) noexcept {
    if(manual_move::terminal.load())return;
    if(!seq)return;
    bool free=false;if(!manual_move::busy.compare_exchange_strong(free,true)){manual_move::terminal.store(true);return;}
    struct BusyScope {~BusyScope(){manual_move::busy.store(false);}} inFlight;
    forward_diagnostic::Context c{};
    if(!forward_diagnostic::context(c) || !manual_move::SameOwner(c) || !manual_move::CorrectThread(c)){
        manual_move::terminal.store(true);return;}
    const unsigned previous=manual_move::lastSequence.load();if(seq<=previous)return;
    manual_move::lastSequence.store(seq);Request r{};r.seq=seq;Result result{"REFUSED",1,false,"none"};
    if(payload && Read(c,seq,r)){
        const unsigned reason=Authorize(r,seq,c,previous);result=reason?Result{"REFUSED",reason,false,"none"}:Native(r);
    }
    forward_diagnostic::Context after{};
    if(!forward_diagnostic::context(after) || !manual_move::SameOwner(after) || !manual_move::CorrectThread(after)){
        manual_move::terminal.store(true);return;}
    r.seq=seq;
    if(!strcmp(result.status,"UNKNOWN"))manual_move::terminal.store(true);
    if(!Output(c,r,result))manual_move::terminal.store(true);
}
inline bool Handle(int code,WPARAM remove,LPARAM raw) noexcept {
    if(code<0 || remove!=PM_REMOVE || !raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);const UINT id=RegisterWindowMessageW(L"LC-Owned-UIOpen-v1");
    if(!manual_move::Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const auto posted=msg->wParam;const bool payload=msg->lParam==0 && posted>0 && posted<=2147483647;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD before=GetLastError();Process(posted>0&&posted<=2147483647?static_cast<unsigned>(posted):0,payload);SetLastError(before);return true;
}
}
