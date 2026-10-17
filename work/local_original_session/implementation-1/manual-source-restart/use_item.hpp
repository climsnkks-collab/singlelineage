#pragma once
// Explicit original UseItem ingress. No params or sender are built here.
namespace use_item {
using manual_move::busy;using manual_move::terminal;using manual_move::lastSequence;
using manual_move::SameOwner;using manual_move::CorrectThread;using manual_move::OwnedNow;
using manual_move::Literal;using manual_move::Number;using Reply=manual_move::Reply;
// Finite refusal/fault classifications in the existing u32 reason field.
// Ingress1..12 stays unchanged; no new output field, read or retry path.
enum Reason : unsigned {
    CodeContext=20,CodeLiteral=21,CodeData=22,CodeTable=23,
    CaptureWorld=30,CapturePlayer=31,RegistryOwner=32,RegistryMap=33,RegistryRows=34,
    RegistryItemType=35,RegistryItemUid=36,RegistryRawKey=37,RegistryChanged=38,RegistryLand=39,
    CurrentPolicy=40,OwnerCall=50,OwnerResult=51,ItemCall=52,ItemResult=53,
    FinalLeases=54,OriginalCommand=55,CleanupFailure=56,CodeLiteralBase=1024,FirstAnchorStageBase=2048,
    FirstAnchorAttributeBase=2112
};
static_assert(CodeLiteralBase==1024 && CodeLiteralBase>CleanupFailure,"literal reasons do not overlap existing1..56");
static_assert(FirstAnchorStageBase==2048 && FirstAnchorStageBase>1173,"first-anchor stages do not overlap literal reasons");
static_assert(FirstAnchorAttributeBase==2112 && FirstAnchorAttributeBase>2052,"first-anchor attribute reasons stay disjoint");
struct Request {uint32_t pid=0,seq=0;uint64_t birth=0,player=0,item=0;int32_t map=0;char hash[65]{};};
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0,map=0;
    if(!Literal(p,"{\"schema\":\"own-use-item-request-v1\",\"pid\":") || !Number(p,UINT32_MAX,pid) ||
       !Literal(p,",\"birth\":") || !Number(p,UINT64_MAX,r.birth) || !Literal(p,",\"candidate_sha256\":\""))return false;
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!Literal(p,"\",\"seq\":") || !Number(p,2147483647,seq) || !seq ||
       !Literal(p,",\"command\":\"UseItem\",\"player_uid\":") || !Number(p,UINT64_MAX,r.player) ||
       !Literal(p,",\"item_identifier\":") || !Number(p,UINT64_MAX,r.item) ||
       !Literal(p,",\"map_id\":") || !Number(p,2147483647,map) || !Literal(p,"}"))return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);r.map=static_cast<int32_t>(map);return true;
}
inline unsigned Authorize(const Request& r,unsigned posted,const forward_diagnostic::Context& c,
        bool correctThread,unsigned previous,bool occupied) noexcept {
    if(r.pid!=c.pid || r.birth!=c.birth || strcmp(r.hash,OWN_EXPECTED_PROGRAM_SHA))return 2;
    if(!r.seq || r.seq!=posted || r.seq<=previous)return 3;
    if(!correctThread)return 4;if(occupied)return 9;
    // Player and item identifiers are different domains; equal numeric values are legal.
    if(!r.player || !r.item || r.map<0)return 1;
    return 0;
}
inline bool Read(const forward_diagnostic::Context& c,Request& r) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\use-item-request.json",c.directory);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,r);
}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {
    char text[768]{};wchar_t path[600]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-use-item-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":\"UseItem\",\"player_uid\":%llu,\"item_identifier\":%llu,\"map_id\":%d,\"status\":\"%s\",\"reason\":%u,\"invoked\":%s}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,
        static_cast<unsigned long long>(r.player),static_cast<unsigned long long>(r.item),r.map,
        reply.status,reply.reason,reply.invoked?"true":"false");
    if(n<=0 || n>=768)return false;
    swprintf_s(path,L"%s\\use-item-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr) && written==static_cast<DWORD>(n) && FlushFileBuffers(file);
    const BOOL closed=CloseHandle(file);return ok && closed;
}
}
#include "use_item_binding.hpp"
namespace use_item {
struct Io {
    bool(*context)(forward_diagnostic::Context&) noexcept=forward_diagnostic::context;
    bool(*thread)(const forward_diagnostic::Context&) noexcept=CorrectThread;
    bool(*read)(const forward_diagnostic::Context&,Request&) noexcept=Read;
    Reply(*execute)(const Request&) noexcept=binding::Native;
    bool(*output)(const forward_diagnostic::Context&,const Request&,const Reply&) noexcept=Output;
};
inline Reply Dispatch(const Request& r,const Io& io) noexcept {
    if(terminal.load())return {"UNKNOWN",9,false};
    if(!io.execute)return {"BLOCKED_SOURCE_BINDING",11,false};
    return io.execute(r);
}
inline Reply GuardedDispatch(const Request& r,const Io& io) noexcept {
    __try {return Dispatch(r,io);}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,true};}
}
inline void Process(unsigned posted,bool payload,const Io& io=Io{}) noexcept {
    if(terminal.load())return;
    bool free=false;if(!busy.compare_exchange_strong(free,true)){terminal.store(true);return;}
    struct BusyScope {~BusyScope(){busy.store(false);}} inFlight;
    forward_diagnostic::Context c{};
    if(!payload || !io.context(c) || !SameOwner(c) || !io.thread(c)){terminal.store(true);return;}
    const unsigned previous=lastSequence.load();if(posted<=previous)return;
    lastSequence.store(posted);Request r{};r.seq=posted;Reply reply{"UNKNOWN",6,false};
    if(io.read(c,r)){
        const unsigned reason=Authorize(r,posted,c,true,previous,false);
        reply=reason?Reply{"UNKNOWN",reason,false}:GuardedDispatch(r,io);
    }
    forward_diagnostic::Context after{};
    if(!io.context(after) || !SameOwner(after) || !io.thread(after)){terminal.store(true);return;}
    r.seq=posted;
    // A native refusal already makes the session terminal. Keep that original
    // explicit cause. Only a nominal RETURNED interrupted by terminal is UNKNOWN9.
    if(terminal.load() && !strcmp(reply.status,"RETURNED"))reply={"UNKNOWN",9,reply.invoked};
    if(strcmp(reply.status,"RETURNED") || !reply.invoked)terminal.store(true);
    if(!io.output(c,r,reply))terminal.store(true);
}
inline bool Handle(int code,WPARAM remove,LPARAM raw) noexcept {
    if(code<0 || remove!=PM_REMOVE || !raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);const UINT id=RegisterWindowMessageW(L"LC-Owned-Manual-UseItem-v1");
    if(!manual_move::Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const auto posted=msg->wParam;const bool payload=msg->lParam==0 && posted>0 && posted<=2147483647;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD before=GetLastError();Process(payload?static_cast<unsigned>(posted):0,payload);SetLastError(before);return true;
}
}
