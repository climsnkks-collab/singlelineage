#pragma once
// Separate AttackTarget ingress. No A3640 call ABI is manufactured here.
// Owner/one-pending/terminal/sequence are shared with the frozen manual MoveGoal
// session, so crossing command kinds cannot bypass reentrancy or replay limits.
namespace attack_target {
using manual_move::busy;
using manual_move::terminal;
using manual_move::lastSequence;
using manual_move::SameOwner;
using manual_move::CorrectThread;
using manual_move::OwnedNow;
using manual_move::Literal;
using manual_move::Number;
struct Request {
    uint32_t pid=0,seq=0;uint64_t birth=0,player=0,target=0;int32_t map=0;char hash[65]{};
};
using Reply=manual_move::Reply;
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0,map=0;
    if(!Literal(p,"{\"schema\":\"own-attack-target-request-v1\",\"pid\":") || !Number(p,UINT32_MAX,pid) ||
       !Literal(p,",\"birth\":") || !Number(p,UINT64_MAX,r.birth) || !Literal(p,",\"candidate_sha256\":\""))return false;
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!Literal(p,"\",\"seq\":") || !Number(p,2147483647,seq) || !seq ||
       !Literal(p,",\"command\":\"AttackTarget\",\"player_uid\":") || !Number(p,UINT64_MAX,r.player) ||
       !Literal(p,",\"target_uid\":") || !Number(p,UINT32_MAX,r.target) ||
       !Literal(p,",\"map_id\":") || !Number(p,2147483647,map) || !Literal(p,"}"))return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);r.map=static_cast<int32_t>(map);return true;
}
inline unsigned Authorize(const Request& r,unsigned posted,const forward_diagnostic::Context& c,
        bool correctThread,unsigned previous,bool occupied) noexcept {
    if(r.pid!=c.pid || r.birth!=c.birth || strcmp(r.hash,OWN_EXPECTED_PROGRAM_SHA))return 2;
    if(!r.seq || r.seq!=posted || r.seq<=previous)return 3;
    if(!correctThread)return 4;if(occupied)return 9;
    if(!r.player || !r.target || r.target>UINT32_MAX || r.player==r.target || r.map<0)return 1;
    return 0;
}
inline bool Read(const forward_diagnostic::Context& c,Request& r) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\attack-target-request.json",c.directory);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[513]{};DWORD n=0;
    const bool ok=ReadFile(file,text,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(file);
    return ok && closed && !memchr(text,0,n) && Parse(text,r);
}
struct Snapshot {
    manual_move::Pins world{};manual_move::ActorPins player{};
    Pair target{},map{},character{};void* mapContext=nullptr;int32_t mapId=-1;
};
struct Retained {
    const Snapshot& s;
    ~Retained(){
        Release(s.character.control);Release(s.map.control);Release(s.target.control);
        Release(s.player.controller.control);Release(s.player.transform.control);Release(s.player.actor.control);
        Release(s.world.actors.control);Release(s.world.layout.control);Release(s.world.scene.control);
        Release(s.world.state.control);Release(s.world.ui.control);
    }
};
inline bool Same(Pair a,Pair b) noexcept {return a.object==b.object && a.control==b.control;}
inline bool Same(const Snapshot& a,const Snapshot& b) noexcept {
    return Same(a.world.state,b.world.state) && Same(a.world.scene,b.world.scene) && Same(a.world.actors,b.world.actors) &&
        Same(a.player.actor,b.player.actor) && Same(a.player.transform,b.player.transform) &&
        Same(a.player.controller,b.player.controller) && Same(a.target,b.target) && Same(a.map,b.map) &&
        Same(a.character,b.character) && a.mapContext==b.mapContext && a.mapId==b.mapId &&
        a.player.uid==b.player.uid && a.player.x==b.player.x && a.player.y==b.player.y;
}
inline bool ImageSlot(uintptr_t table) noexcept {
    MEMORY_BASIC_INFORMATION region{};const auto b=scope.base;
    if(table<b || table>b+OwnForwardLayout::ImageSize-16 ||
       VirtualQuery(reinterpret_cast<void*>(table),&region,sizeof(region))!=sizeof(region) ||
       region.State!=MEM_COMMIT || region.Type!=MEM_IMAGE || reinterpret_cast<uintptr_t>(region.AllocationBase)!=b ||
       (region.Protect&PAGE_GUARD) || (region.Protect&0xff)==PAGE_NOACCESS)return false;
    const auto low=reinterpret_cast<uintptr_t>(region.BaseAddress);
    return table>=low && region.RegionSize>=16 && table-low<=region.RegionSize-16 &&
        *reinterpret_cast<uintptr_t*>(table+8)==b+0x40c00;
}
// Read-only equivalent of 627B0's first UID match in its three ordered vectors.
// Unknown UID getter in any preceding entry blocks the lookup. No virtual call.
inline bool Lookup(Pair actors,uint64_t uid,Pair& out,bool(*verifySlot)(uintptr_t) noexcept=ImageSlot) noexcept {
    for(const uintptr_t offset:{uintptr_t(0x8a8),uintptr_t(0x8c0),uintptr_t(0x8d8)}){
        uintptr_t begin=0;size_t count=0;
        if(!original_move::Vector(reinterpret_cast<uintptr_t>(actors.object)+offset,512,begin,count))return false;
        for(size_t i=0;i<count;++i){const Pair p=*reinterpret_cast<Pair*>(begin+i*16);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)) || !AutoOkCanonical(reinterpret_cast<uintptr_t>(p.control)) ||
               *reinterpret_cast<volatile LONG*>(static_cast<uint8_t*>(p.control)+8)<=0)return false;
            const auto table=*reinterpret_cast<uintptr_t*>(p.object);
            if(!verifySlot(table))return false;
            // Getter40C00 is closed source: mov rax,[rcx+18]; ret.
            if(*reinterpret_cast<uint64_t*>(static_cast<uint8_t*>(p.object)+0x18)==uid){out=p;return true;}
        }
    }
    return false;
}
inline bool Observe(const Request& r,Snapshot& s) noexcept {
    __try {
        unsigned reason=0;if(!manual_move::Find(s.world,5,reason) || !manual_move::Stable(s.world,5) ||
            !manual_move::ObserveMove(s.world,r.player,s.player))return false;
        const auto b=scope.base;Pair own{},target{};
        if(!Lookup(s.world.actors,r.player,own) || !Same(own,s.player.actor) ||
           !Lookup(s.world.actors,r.target,target) || *reinterpret_cast<uintptr_t*>(target.object)!=b+0x11818a8 ||
           !manual_move::Hold(target,s.target))return false;
        auto* root=*reinterpret_cast<uint8_t**>(b+0x1668790);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) || !root[0xd8])return false;
        auto* gi=*reinterpret_cast<uint8_t**>(root+0xd0);if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(gi)))return false;
        uintptr_t begin=0;size_t count=0;if(!original_move::Vector(reinterpret_cast<uintptr_t>(gi)+0x180,128,begin,count))return false;
        Pair map{},character{};bool actors=false,state=false;
        for(size_t i=0;i<count;++i){const Pair p=*reinterpret_cast<Pair*>(begin+i*16);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)))return false;
            const auto v=*reinterpret_cast<uintptr_t*>(p.object);
            if(v==b+0x117ead8){if(actors || !Same(p,s.world.actors))return false;actors=true;}
            if(v==b+0x1182e30){if(state || !Same(p,s.world.state))return false;state=true;}
            if(v==b+0x11c7df0){if(map.object)return false;map=p;}
            if(v==b+0x1185340){if(character.object)return false;character=p;}
        }
        if(!actors || !state || !manual_move::Hold(map,s.map) || !manual_move::Hold(character,s.character) ||
           *reinterpret_cast<uint64_t*>(static_cast<uint8_t*>(character.object)+0x6d8)!=r.player)return false;
        auto* m=static_cast<uint8_t*>(map.object);s.mapContext=*reinterpret_cast<void**>(m+0x6e0);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(s.mapContext)) || *reinterpret_cast<int32_t*>(m+0x718)!=r.map ||
           *reinterpret_cast<int32_t*>(m+0x71c)!=r.map || *reinterpret_cast<int32_t*>(s.mapContext)!=r.map)return false;
        s.mapId=r.map;return manual_move::Stable(s.world,5);
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
}
#include "attack_abi.hpp"
namespace attack_target {
struct Ops {
    bool(*owned)() noexcept=OwnedNow;
    bool(*observe)(const Request&,Snapshot&) noexcept=Observe;
    Reply(*submit)(const Request&,const Snapshot&,bool&) noexcept=native_call::Submit;
};
inline Reply Execute(const Request& r,const Ops& ops,bool& attempted) noexcept {
    if(terminal.load() || !ops.owned())return {"UNKNOWN",2,false};
    Snapshot first{};Retained firstOwner{first};
    if(!ops.observe(r,first))return {"UNKNOWN",6,false};
    Snapshot last{};Retained lastOwner{last};
    if(!ops.observe(r,last) || !Same(first,last))return {"UNKNOWN",6,false};
    if(terminal.load() || !ops.owned())return {"UNKNOWN",2,false};
    if(!ops.submit)return {"ABI_BLOCKED",11,false};
    return ops.submit(r,last,attempted);
}
inline Reply Guarded(const Request& r,const Ops& ops) noexcept {
    bool attempted=false;
    __try {return Execute(r,ops,attempted);}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,attempted};}
}
inline Reply ExecuteGuarded(const Request& r) noexcept {return Guarded(r,Ops{});}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Reply& reply) noexcept {
    char text[768]{};wchar_t path[600]{};
    const int n=sprintf_s(text,"{\"schema\":\"own-attack-target-result-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"command\":\"AttackTarget\",\"player_uid\":%llu,\"target_uid\":%llu,\"map_id\":%d,\"status\":\"%s\",\"reason\":%u,\"invoked\":%s}\n",
        c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,r.seq,
        static_cast<unsigned long long>(r.player),static_cast<unsigned long long>(r.target),r.map,reply.status,reply.reason,reply.invoked?"true":"false");
    if(n<=0 || n>=768)return false;
    swprintf_s(path,L"%s\\attack-target-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr) && written==static_cast<DWORD>(n) && FlushFileBuffers(file);
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
    bool free=false;if(!busy.compare_exchange_strong(free,true)){terminal.store(true);return;}
    struct BusyScope {~BusyScope(){busy.store(false);}} inFlight;
    forward_diagnostic::Context c{};
    if(!payload || !io.context(c) || !SameOwner(c) || !io.thread(c)){terminal.store(true);return;}
    const unsigned previous=lastSequence.load();if(posted<=previous)return;
    lastSequence.store(posted);Request r{};r.seq=posted;Reply reply{"UNKNOWN",6,false};
    if(io.read(c,r)){
        const unsigned reason=Authorize(r,posted,c,true,previous,false);
        reply=reason?Reply{"UNKNOWN",reason,false}:io.execute(r);
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
    auto* msg=reinterpret_cast<MSG*>(raw);const UINT id=RegisterWindowMessageW(L"LC-Owned-Manual-AttackTarget-v1");
    if(!manual_move::Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const WPARAM posted=msg->wParam;const bool payload=msg->lParam==0 && posted>0 && posted<=2147483647;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD before=GetLastError();Process(payload?static_cast<unsigned>(posted):0,payload);SetLastError(before);return true;
}
}
