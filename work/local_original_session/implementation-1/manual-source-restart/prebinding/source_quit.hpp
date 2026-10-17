#pragma once
// Explicit manual ingress only. Original UI binding remains blocked pending
// the saved-source contract identified in CONTRACT_GAP.md. No guard is copied,
// disabled or replaced; no new callback ABI or speculative lookup is called.
namespace source_quit {
using manual_move::busy;
using manual_move::terminal;
using manual_move::lastSequence;
using manual_move::SameOwner;
using manual_move::CorrectThread;
using manual_move::Literal;
using manual_move::Number;
using Reply=manual_move::Reply;
enum class Phase : unsigned {None=0,FirstLandQuit=1,Quit6Approval=2};
struct Request {uint32_t pid=0,seq=0;uint64_t birth=0;char hash[65]{};Phase phase=Phase::None;};
static bool firstClaimed=false,firstReturned=false,lateClaimed=false;
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0;
    if(!Literal(p,"{\"schema\":\"own-manual-source-quit-request-v1\",\"pid\":") || !Number(p,UINT32_MAX,pid) ||
       !Literal(p,",\"birth\":") || !Number(p,UINT64_MAX,r.birth) ||
       !Literal(p,",\"candidate_sha256\":\""))return false;
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!Literal(p,"\",\"seq\":") || !Number(p,2147483647,seq) || !seq ||
       !Literal(p,",\"command\":\"SourceQuit\",\"phase\":\""))return false;
    if(!strncmp(p,"FirstLandQuit\"}",15)){p+=15;r.phase=Phase::FirstLandQuit;}
    else if(!strncmp(p,"Quit6Approval\"}",15)){p+=15;r.phase=Phase::Quit6Approval;}
    else return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);return true;
}
inline unsigned Authorize(const Request& r,unsigned posted,const forward_diagnostic::Context& c,
        bool correctThread,unsigned previous,bool occupied) noexcept {
    if(r.pid!=c.pid || r.birth!=c.birth || strcmp(r.hash,OWN_EXPECTED_PROGRAM_SHA))return 2;
    if(!r.seq || r.seq!=posted || r.seq<=previous)return 3;
    if(!correctThread)return 4;if(occupied)return 9;
    if(r.phase!=Phase::FirstLandQuit && r.phase!=Phase::Quit6Approval)return 1;
    return 0;
}
inline bool Read(const forward_diagnostic::Context& c,Request& r) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\source-quit-request.json",c.directory);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,r);
}
inline const char* Name(Phase phase) noexcept {
    return phase==Phase::FirstLandQuit?"FirstLandQuit":phase==Phase::Quit6Approval?"Quit6Approval":"UNKNOWN";
}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {
    char text[768]{};wchar_t path[600]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-manual-source-quit-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":\"SourceQuit\",\"phase\":\"%s\",\"status\":\"%s\",\"reason\":%u,\"invoked\":%s}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,Name(r.phase),reply.status,reply.reason,reply.invoked?"true":"false");
    if(n<=0 || n>=768)return false;
    swprintf_s(path,L"%s\\source-quit-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr) && written==static_cast<DWORD>(n) && FlushFileBuffers(file);
    const BOOL closed=CloseHandle(file);return ok && closed;
}
struct Io {
    bool(*context)(forward_diagnostic::Context&) noexcept=forward_diagnostic::context;
    bool(*thread)(const forward_diagnostic::Context&) noexcept=CorrectThread;
    bool(*read)(const forward_diagnostic::Context&,Request&) noexcept=Read;
    // Deliberate absence of a production provider, never a successful stub.
    // Future provider must prove current typed UI/source/lifetime twice, release
    // bridge-owned leases BEFORE its final borrowed proof, then dispatch once.
    // Late approval additionally requires actual host source-drain evidence and
    // current Quit6 proof. A request field/first RETURNED cannot prove the drain.
    Reply(*execute)(const Request&) noexcept=nullptr;
    bool(*output)(const forward_diagnostic::Context&,const Request&,const Reply&) noexcept=Output;
};
inline Reply Dispatch(const Request& r,const Io& io) noexcept {
    if(terminal.load())return {"UNKNOWN",9,false};
    if(!io.execute)return {"BLOCKED_SOURCE_BINDING",11,false};
    if(r.phase==Phase::FirstLandQuit){
        if(firstClaimed)return {"UNKNOWN",3,false};
        firstClaimed=true; // Consume before provider; no rearm on fault/refusal.
    } else {
        if(!firstReturned || lateClaimed)return {"UNKNOWN",3,false};
        lateClaimed=true;
    }
    const Reply reply=io.execute(r);
    if(r.phase==Phase::FirstLandQuit && !strcmp(reply.status,"RETURNED") && reply.invoked && !terminal.load())firstReturned=true;
    return reply;
}
inline Reply GuardedDispatch(const Request& r,const Io& io) noexcept {
    // Any provider/lease fault has ambiguous invocation; terminal UNKNOWN. No
    // speculative cleanup, callback retry, rollback, module unload or game read.
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
    if(terminal.load())reply={"UNKNOWN",9,reply.invoked};
    if(strcmp(reply.status,"RETURNED") || !reply.invoked)terminal.store(true);
    if(!io.output(c,r,reply))terminal.store(true);
}
inline bool Handle(int code,WPARAM remove,LPARAM raw) noexcept {
    if(code<0 || remove!=PM_REMOVE || !raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);const UINT id=RegisterWindowMessageW(L"LC-Owned-Manual-SourceQuit-v1");
    if(!manual_move::Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const auto posted=msg->wParam;const bool payload=msg->lParam==0 && posted>0 && posted<=2147483647;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD before=GetLastError();Process(payload?static_cast<unsigned>(posted):0,payload);SetLastError(before);return true;
}
}
