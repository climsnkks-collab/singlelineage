#pragma once
// Explicit once-per-DLL two-phase saved-character reselect; boot claims remain unchanged.
namespace source_reselect {
using manual_move::busy;using manual_move::terminal;using manual_move::lastSequence;
using manual_move::SameOwner;using manual_move::CorrectThread;
using manual_move::Literal;using manual_move::Number;using Reply=manual_move::Reply;
enum class Phase : unsigned {None=0,SelectSlot=1,SelectOK=2};
struct Request {uint32_t pid=0,seq=0;uint64_t birth=0;char hash[65]{};Phase phase=Phase::None;uint64_t saved=0;char referenceHex[65]{};unsigned char reference[33]{};unsigned referenceLength=0;};
static bool firstClaimed=false,firstReturned=false,lateClaimed=false;
static Request firstRequest{};
inline bool Reference(const unsigned char* bytes,unsigned n) noexcept {
    if(!n || n>32)return false;
    for(unsigned i=0;i<n;){const unsigned c=bytes[i++];if(c<32 || c==127)return false;if(c<128)continue;
        unsigned count=0,value=0,minimum=0;
        if(c>=0xc2 && c<=0xdf){count=1;value=c&31;minimum=0x80;}
        else if(c>=0xe0 && c<=0xef){count=2;value=c&15;minimum=0x800;}
        else if(c>=0xf0 && c<=0xf4){count=3;value=c&7;minimum=0x10000;}else return false;
        if(count>n-i)return false;for(unsigned j=0;j<count;++j){const unsigned part=bytes[i++];if((part&0xc0)!=0x80)return false;value=(value<<6)|(part&63);}
        if(value<minimum || value>0x10ffff || (value>=0xd800 && value<=0xdfff))return false;
    }return true;
}
inline const char* PhaseName(Phase phase) noexcept {return phase==Phase::SelectSlot?"SelectSlot":phase==Phase::SelectOK?"SelectOK":"UNKNOWN";}
inline int Hex(char c) noexcept {return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0;
    if(!Literal(p,"{\"schema\":\"own-source-reselect-request-v1\",\"pid\":") || !Number(p,UINT32_MAX,pid) ||
       !Literal(p,",\"birth\":") || !Number(p,UINT64_MAX,r.birth) || !Literal(p,",\"candidate_sha256\":\""))return false;
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!Literal(p,"\",\"seq\":") || !Number(p,2147483647,seq) || !seq ||
       !Literal(p,",\"command\":\"SourceReselect\",\"phase\":\""))return false;
    if(Literal(p,"SelectSlot\""))r.phase=Phase::SelectSlot;
    else if(Literal(p,"SelectOK\""))r.phase=Phase::SelectOK;else return false;
    if(!Literal(p,",\"saved_character_uid\":") || !Number(p,UINT64_MAX,r.saved) || !r.saved ||
       !Literal(p,",\"canonical_reference_utf8_hex\":\""))return false;
    unsigned count=0;
    while(*p!='\"'){if(count>=64 || Hex(*p)<0)return false;r.referenceHex[count++]=*p++;}
    if(!count || count%2)return false;
    r.referenceLength=count/2;for(unsigned i=0;i<r.referenceLength;++i)r.reference[i]=static_cast<unsigned char>((Hex(r.referenceHex[i*2])<<4)|Hex(r.referenceHex[i*2+1]));
    if(!Reference(r.reference,r.referenceLength) || !Literal(p,"\"}"))return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);return true;
}

inline unsigned Authorize(const Request& r,unsigned posted,const forward_diagnostic::Context& c,
        bool correctThread,unsigned previous,bool occupied) noexcept {
    if(r.pid!=c.pid || r.birth!=c.birth || strcmp(r.hash,OWN_EXPECTED_PROGRAM_SHA))return 2;
    if(!r.seq || r.seq!=posted || r.seq<=previous)return 3;
    if(!correctThread)return 4;if(occupied)return 9;
    return (r.phase==Phase::SelectSlot || r.phase==Phase::SelectOK) && r.saved && Reference(r.reference,r.referenceLength)?0u:1u;
}
inline bool Read(const forward_diagnostic::Context& c,Request& r) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\source-reselect-request.json",c.directory);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,r);
}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {
    char text[768]{};wchar_t path[600]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-source-reselect-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":\"SourceReselect\",\"phase\":\"%s\",\"saved_character_uid\":%llu,\"canonical_reference_utf8_hex\":\"%s\",\"status\":\"%s\",\"reason\":%u,\"invoked\":%s}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,PhaseName(r.phase),static_cast<unsigned long long>(r.saved),r.referenceHex,reply.status,reply.reason,reply.invoked?"true":"false");
    if(n<=0 || n>=768)return false;swprintf_s(path,L"%s\\source-reselect-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr) && written==static_cast<DWORD>(n) && FlushFileBuffers(file);
    const BOOL closed=CloseHandle(file);return ok && closed;
}
}
#include "reselect_binding.hpp"
namespace source_reselect {
struct Io {
    bool(*context)(forward_diagnostic::Context&) noexcept=forward_diagnostic::context;
    bool(*thread)(const forward_diagnostic::Context&) noexcept=CorrectThread;
    bool(*read)(const forward_diagnostic::Context&,Request&) noexcept=Read;
    Reply(*execute)(const Request&) noexcept=binding::Native;
    bool(*output)(const forward_diagnostic::Context&,const Request&,const Reply&) noexcept=Output;
};
inline Reply Dispatch(const Request& r,const Io& io) noexcept {
    if(terminal.load())return {"UNKNOWN",9,false};
    if(!source_restart::restartClaimed)return {"BLOCKED_SOURCE_BINDING",10,false};
    if(r.phase==Phase::SelectSlot){
        if(firstClaimed)return {"UNKNOWN",9,false};firstClaimed=true;firstRequest=r;
    }else if(r.phase==Phase::SelectOK){
        if(!firstReturned || lateClaimed)return {"UNKNOWN",9,false};lateClaimed=true;
        if(r.saved!=firstRequest.saved || strcmp(r.referenceHex,firstRequest.referenceHex))return {"UNKNOWN",1,false};
    }else return {"UNKNOWN",1,false};
    const Reply reply=io.execute?io.execute(r):Reply{"BLOCKED_SOURCE_BINDING",11,false};
    if(r.phase==Phase::SelectSlot && !strcmp(reply.status,"RETURNED") && !reply.reason && reply.invoked && !terminal.load())firstReturned=true;
    return reply;
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
    if(io.read(c,r)){const unsigned reason=Authorize(r,posted,c,true,previous,false);
        reply=reason?Reply{"UNKNOWN",reason,false}:GuardedDispatch(r,io);}
    forward_diagnostic::Context after{};
    if(!io.context(after) || !SameOwner(after) || !io.thread(after)){terminal.store(true);return;}
    r.seq=posted;
    if(terminal.load() && !strcmp(reply.status,"RETURNED"))reply={"UNKNOWN",9,reply.invoked};
    if(strcmp(reply.status,"RETURNED") || !reply.invoked)terminal.store(true);
    if(!io.output(c,r,reply))terminal.store(true);
}
inline bool Handle(int code,WPARAM remove,LPARAM raw) noexcept {
    if(code<0 || remove!=PM_REMOVE || !raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);const UINT id=RegisterWindowMessageW(L"LC-Owned-Manual-SourceReselect-v1");
    if(!manual_move::Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const auto posted=msg->wParam;const bool payload=msg->lParam==0 && posted>0 && posted<=2147483647;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD before=GetLastError();Process(payload?static_cast<unsigned>(posted):0,payload);SetLastError(before);return true;
}
}
