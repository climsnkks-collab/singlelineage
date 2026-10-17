#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
#include <cstring>
#include <stdexcept>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace use_fixture {
namespace u=use_item;namespace b=u::binding;
using manual_move::terminal;using manual_move::busy;using manual_move::lastSequence;
struct alignas(16) Node {unsigned char bytes[0x100]{};};
static Node ownerControl{},itemControl{},otherControl{};
static Pair owner{},item{},other{};
static unsigned mode=0,getters=0,lookups=0,commands=0,releases=0,codes=0,currents=0,reads=0,outputs=0,contexts=0;
static bool bad=false;
static unsigned indexedFailure=0,indexedVisits=0,indexedCaptures=0;
static bool indexedFault=false,indexedWrongOrder=false;
static u::Request request{};static u::Reply output{};
uint32_t& Count(Pair p){return *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(p.control)+8);}
void Reset(unsigned change=0) {
    ownerControl={};itemControl={};otherControl={};
    owner={ownerControl.bytes+16,ownerControl.bytes};item={itemControl.bytes+16,itemControl.bytes};
    other={otherControl.bytes+16,otherControl.bytes};Count(owner)=Count(item)=Count(other)=1;
    mode=change;getters=lookups=commands=releases=codes=currents=reads=outputs=contexts=0;bad=false;
    terminal.store(false);busy.store(false);lastSequence.store(0);
    manual_move::owner={};manual_move::owner.pid=123;manual_move::owner.birth=456;
    wcscpy_s(manual_move::owner.directory,L"use-item-synthetic");manual_move::ownerBound=true;
    request={};request.pid=123;request.birth=456;request.seq=1;request.player=1;request.item=1;request.map=4;
    strcpy_s(request.hash,OWN_EXPECTED_PROGRAM_SHA);output={};
}
bool Code(unsigned& reason) noexcept {++codes;reason=12;return mode!=1 && !(mode==2&&codes==3);}
bool Owned() noexcept {return mode!=3;}
bool Capture(const u::Request& r,b::Snapshot& s,unsigned& reason) noexcept {
    ++indexedCaptures;
    reason=u::CaptureWorld;
    if(r.player!=1 || r.item!=1 || r.map!=4)bad=true;
    s.registeredOwner=owner;s.registeredItem=item;
    if(mode==23 || mode==24){s.map=other;++Count(other);}
    return mode!=4;
}
bool Current(const u::Request&,b::Snapshot&,unsigned& reason) noexcept {
    reason=u::CurrentPolicy;
    ++currents;
    // Typed owner/Land/UID/raw0 refusals are injected at the real current seam.
    return !(mode==5&&currents==2) && !(mode==6&&currents==3);
}
Pair* Get(Pair* out) {
    ++getters;if(mode==7)throw std::runtime_error("owner before publish");
    *out=owner;++Count(owner);
    if(mode==8)throw std::runtime_error("owner partial publish");
    if(mode==9)RaiseException(0xe0424242,0,0,nullptr);
    if(mode==10)return nullptr;
    if(mode==11){--Count(owner);*out={};}
    if(mode==23){--Count(owner);out->control=nullptr;}
    return out;
}
Pair* Lookup(void* actual,Pair* out,uint64_t uid) {
    ++lookups;if(actual!=owner.object || uid!=request.item || Count(owner)!=2)bad=true;
    if(mode==12)throw std::runtime_error("item before publish");
    *out=item;++Count(item);
    if(mode==13)throw std::runtime_error("item partial publish");
    if(mode==14)RaiseException(0xe0424242,0,0,nullptr);
    if(mode==15)return nullptr;
    if(mode==16){--Count(item);*out={};}
    if(mode==17){--Count(item);*out=other;++Count(other);}
    if(mode==24){--Count(item);out->control=nullptr;}
    return out;
}
void Command(void* actual,uint64_t uid) {
    ++commands;
    if(actual!=owner.object || uid!=request.item || Count(owner)!=2 || Count(item)!=2)bad=true;
    if(mode==18)throw std::runtime_error("original partial mutation");
    if(mode==19)RaiseException(0xe0424242,0,0,nullptr);
    if(mode==20)terminal.store(true);
}
void Release(Pair p) {
    ++releases;
    if(mode==21)throw std::runtime_error("release");
    if(mode==22)RaiseException(0xe0424242,0,0,nullptr);
    if(!Count(p))bad=true;else --Count(p);
}
b::Calls Calls() noexcept {return {Code,Owned,Capture,Current,Get,Lookup,Command,Release};}
bool Context(forward_diagnostic::Context& c) noexcept {
    ++contexts;c=manual_move::owner;if(mode==30)return false;
    if(mode==31 && contexts==2)++c.birth;return true;
}
bool Thread(const forward_diagnostic::Context&) noexcept {return mode!=32;}
bool Read(const forward_diagnostic::Context&,u::Request& r) noexcept {
    ++reads;r=request;if(mode==33)return false;if(mode==34)++r.seq;return true;
}
bool Output(const forward_diagnostic::Context&,const u::Request& r,const u::Reply& reply) noexcept {
    ++outputs;output=reply;if(r.seq!=request.seq)bad=true;return mode!=35;
}
u::Reply Execute(const u::Request& r) noexcept {
    if(mode==36){u::Process(88,true);return {"RETURNED",0,true};}
    return b::Using(r,Calls());
}
u::Io Io() noexcept {return {Context,Thread,Read,Execute,Output};}
bool IndexedVerify(uintptr_t base,const original_move::Anchor& anchor,unsigned&) noexcept {
    const unsigned current=indexedVisits++;
    if(base!=0x10000 || current>=150 || &anchor!=&b::codeAnchors[current])indexedWrongOrder=true;
    if(indexedFault && current==indexedFailure)RaiseException(0xe0424242,0,0,nullptr);
    return current!=indexedFailure;
}
bool IndexedCode(unsigned& reason) noexcept {
    reason=u::CodeLiteral;
    return b::CodeLiteralReady(0x10000,reason,IndexedVerify);
}
u::Reply IndexedExecute(const u::Request& r) noexcept {
    auto calls=Calls();calls.code=IndexedCode;return b::Using(r,calls);
}
int CheckAnchorIndex(unsigned& checks) {
    // Hardcoded independent contract boundaries, not values inferred from the loop.
    static_assert(u::CodeLiteralBase==1024 && b::CodeLiteralCount==150 && b::CodeLiteralLast==1173 &&
        u::CodeLiteralBase>56 && b::CodeLiteralLast<=4294967295ull,"independent literal reason boundaries");++checks;
    for(unsigned failure=0;failure<150;++failure){
        Reset();indexedFailure=failure;indexedVisits=indexedCaptures=0;indexedFault=indexedWrongOrder=false;
        auto io=Io();io.execute=IndexedExecute;u::Process(1,true,io);
        if(strcmp(output.status,"CODE_ANCHOR_BLOCKED") || output.reason!=1024+failure || output.invoked ||
           indexedVisits!=failure+1 || indexedWrongOrder || indexedCaptures || getters || lookups || commands ||
           releases || outputs!=1 || !terminal.load() || busy.load())return 601;++checks;
        const auto visits=indexedVisits;request.seq=2;u::Process(2,true,io);
        if(indexedVisits!=visits || outputs!=1 || reads!=1)return 602;
    }
    Reset();indexedFailure=150;indexedVisits=indexedCaptures=0;indexedFault=indexedWrongOrder=false;
    unsigned reason=21;if(!b::CodeLiteralReady(0x10000,reason,IndexedVerify) || indexedVisits!=150 ||
       indexedWrongOrder || reason!=21 || commands || releases)return 603;++checks;
    // An exception is not a false predicate. Preserve old UNKNOWN21 and its debt.
    Reset();indexedFailure=73;indexedVisits=indexedCaptures=0;indexedFault=true;indexedWrongOrder=false;
    auto io=Io();io.execute=IndexedExecute;u::Process(1,true,io);
    if(strcmp(output.status,"UNKNOWN") || output.reason!=21 || output.invoked || indexedVisits!=74 ||
       indexedWrongOrder || indexedCaptures || getters || lookups || commands || releases ||
       outputs!=1 || !terminal.load() || busy.load())return 604;++checks;
    return 0;
}
static unsigned stageMode=0,stageQueries=0,stageCompares=0,stageVisits=0,stageLaterFailure=150;
static bool stageBad=false;
static constexpr uintptr_t stageBase=0x10000;
SIZE_T StageQuery(const void* at,MEMORY_BASIC_INFORMATION* out,size_t size) noexcept {
    ++stageQueries;const auto expected=stageBase+b::codeAnchors[0].rva;
    if(reinterpret_cast<uintptr_t>(at)!=expected || size!=sizeof(*out))stageBad=true;
    if(stageMode==15)RaiseException(0xe0424242,0,0,nullptr);
    if(stageMode==1)return 0;
    *out={};out->BaseAddress=reinterpret_cast<void*>(expected);out->AllocationBase=reinterpret_cast<void*>(stageBase);
    out->State=MEM_COMMIT;out->Type=MEM_IMAGE;out->Protect=PAGE_EXECUTE_READ;out->RegionSize=0x1000;
    if(stageMode==2)out->State=MEM_RESERVE;
    if(stageMode==3)out->Type=MEM_PRIVATE;
    if(stageMode==4)out->AllocationBase=reinterpret_cast<void*>(stageBase+8);
    if(stageMode==5)out->Protect|=PAGE_GUARD;
    if(stageMode==6)out->Protect=PAGE_NOACCESS;
    if(stageMode==7)out->Protect=PAGE_READONLY;
    if(stageMode==8)out->BaseAddress=reinterpret_cast<void*>(expected+8);
    if(stageMode==9)out->RegionSize=b::codeAnchors[0].size-1;
    if(stageMode==10){out->BaseAddress=reinterpret_cast<void*>(expected-8);out->RegionSize=b::codeAnchors[0].size;}
    if(stageMode==12)out->Protect=PAGE_EXECUTE_READWRITE;
    if(stageMode==13)out->Protect=PAGE_EXECUTE_WRITECOPY;
    if(stageMode==14)out->Protect|=PAGE_NOCACHE;
    return sizeof(*out);
}
int StageCompare(const void* at,const void* bytes,size_t size) noexcept {
    ++stageCompares;
    if(reinterpret_cast<uintptr_t>(at)!=stageBase+b::codeAnchors[0].rva ||
       bytes!=b::codeAnchors[0].bytes || size!=16)stageBad=true;
    if(stageMode==16)RaiseException(0xe0424242,0,0,nullptr);
    return stageMode==11?1:0;
}
bool StageVerify(uintptr_t base,const original_move::Anchor& anchor,unsigned& failure) noexcept {
    const unsigned index=stageVisits++;
    if(base!=stageBase || index>=150 || &anchor!=&b::codeAnchors[index])stageBad=true;
    if(index==0)return original_move::ExecutableAnchorWith(base,anchor,&failure,StageQuery,StageCompare);
    failure=original_move::AnchorBytes; // Must not classify later anchors as first-anchor stages.
    return index!=stageLaterFailure;
}
bool StageCode(unsigned& reason) noexcept {
    reason=u::CodeLiteral;return b::CodeLiteralReady(stageBase,reason,StageVerify);
}
u::Reply StageExecute(const u::Request& r) noexcept {
    auto calls=Calls();calls.code=StageCode;return b::Using(r,calls);
}
void StageReset(unsigned change) {
    Reset();stageMode=change;stageQueries=stageCompares=stageVisits=indexedCaptures=0;
    stageLaterFailure=150;stageBad=false;
}
int CheckAnchorStage(unsigned& checks) {
    using Legacy=bool(*)(uintptr_t,const original_move::Anchor&) noexcept;
    static_assert(std::is_same_v<decltype(&original_move::ExecutableAnchor),Legacy>,"legacy2arg function pointer preserved");
    static_assert(u::FirstAnchorStageBase==2048 && u::FirstAnchorStageBase+4==2052 &&
        u::FirstAnchorStageBase>1173 && b::CodeLiteralCount==150 && b::CodeLiteralLast==1173 &&
        u::CodeContext==20 && u::CodeLiteral==21 && u::CodeData==22 && u::CodeTable==23,"independent stage boundaries");++checks;
    for(unsigned m=0;m<=14;++m){
        StageReset(m);unsigned failure=99;
        const bool observed=original_move::ExecutableAnchorWith(stageBase,b::codeAnchors[0],&failure,StageQuery,StageCompare);
        const auto queryCount=stageQueries,compareCount=stageCompares;
        stageQueries=stageCompares=0;
        const bool plain=original_move::ExecutableAnchorWith(stageBase,b::codeAnchors[0],nullptr,StageQuery,StageCompare);
        const unsigned expected=m==1?1:m>=2&&m<=6?m+4:m==7?3:m>=8&&m<=10?4:m==11?5:99;
        const bool good=m==0 || m>=12;
        if(observed!=good || plain!=observed || failure!=expected || queryCount!=1 || stageQueries!=1 ||
           compareCount!=(good || m==11?1u:0u) || stageCompares!=compareCount || stageBad)return 650+static_cast<int>(m);++checks;
    }
    for(unsigned m:{1u,2u,7u,8u,11u}){
        StageReset(m);auto io=Io();io.execute=StageExecute;u::Process(1,true,io);
        const unsigned expected=m==1?2048:m==2?2112:m==7?2050:m==8?2051:2052;
        if(strcmp(output.status,"CODE_ANCHOR_BLOCKED") || output.reason!=expected || output.invoked ||
           stageQueries!=1 || stageCompares!=(m==11?1u:0u) || stageVisits!=1 || stageBad || indexedCaptures ||
           getters || lookups || commands || releases || outputs!=1 || !terminal.load() || busy.load())return 680+static_cast<int>(m);
        request.seq=2;u::Process(2,true,io);if(stageQueries!=1 || stageVisits!=1 || outputs!=1)return 699;++checks;
    }
    for(unsigned later:{73u,149u}){
        StageReset(0);stageLaterFailure=later;auto io=Io();io.execute=StageExecute;u::Process(1,true,io);
        if(strcmp(output.status,"CODE_ANCHOR_BLOCKED") || output.reason!=1024+later || output.invoked ||
           stageQueries!=1 || stageCompares!=1 || stageVisits!=later+1 || stageBad || indexedCaptures ||
           getters || lookups || commands || releases || outputs!=1 || !terminal.load() || busy.load())return 700;++checks;
    }
    for(unsigned m:{15u,16u}){
        StageReset(m);auto io=Io();io.execute=StageExecute;u::Process(1,true,io);
        if(strcmp(output.status,"UNKNOWN") || output.reason!=21 || output.invoked || stageQueries!=1 ||
           stageCompares!=(m==16?1u:0u) || stageVisits!=1 || stageBad || indexedCaptures || getters || lookups ||
           commands || releases || outputs!=1 || !terminal.load() || busy.load())return 701;++checks;
    }
    return 0;
}
int CheckCleanup(unsigned& checks) {
    for(unsigned m:{23u,24u,10u,15u,21u,22u}){
        Reset(m);u::Process(1,true,Io());
        const unsigned expectedReason=(m==23 || m==10)?u::OwnerResult:
            (m==24 || m==15)?u::ItemResult:u::CleanupFailure;
        if(!terminal.load() || busy.load() || bad || outputs!=1 || strcmp(output.status,"UNKNOWN") ||
           output.reason!=expectedReason || output.invoked!=(m==21 || m==22))return 520+static_cast<int>(m);
        if((m==23 && (releases!=1 || Count(other)!=1 || Count(owner)!=1)) ||
           (m==24 && (releases!=2 || Count(other)!=1 || Count(owner)!=1 || Count(item)!=1)))return 514;
        if((m==10 || m==15) && releases)return 515;
        ++checks;
    }
    return 0;
}
int Check(unsigned& checks) {
    Reset();char text[513]{};u::Request parsed{};
    sprintf_s(text,"{\"schema\":\"own-use-item-request-v1\",\"pid\":123,\"birth\":456,\"candidate_sha256\":\"%s\",\"seq\":1,\"command\":\"UseItem\",\"player_uid\":1,\"item_identifier\":1,\"map_id\":4}\n",OWN_EXPECTED_PROGRAM_SHA);
    if(!u::Parse(text,parsed) || parsed.player!=parsed.item || u::Authorize(parsed,1,manual_move::owner,true,0,false))return 1;++checks;
    if(u::Parse("{}",parsed) || u::Parse("{\"schema\":\"own-use-item-request-v1\",\"pid\":01}",parsed))return 2;++checks;
    const auto size=strlen(text);text[size-1]=' ';if(u::Parse(text,parsed))return 3;text[size-1]='\n';++checks;
    sprintf_s(text,"{\"schema\":\"own-use-item-request-v1\",\"pid\":4294967295,\"birth\":18446744073709551615,\"candidate_sha256\":\"%s\",\"seq\":2147483647,\"command\":\"UseItem\",\"player_uid\":18446744073709551615,\"item_identifier\":18446744073709551615,\"map_id\":2147483647}",OWN_EXPECTED_PROGRAM_SHA);
    if(!u::Parse(text,parsed) || parsed.item!=UINT64_MAX || parsed.player!=UINT64_MAX)return 7;++checks;
    char* digit=strstr(text,"4294967295");if(!digit)return 8;digit[9]='6';if(u::Parse(text,parsed))return 9;++checks;
    Reset();u::Process(1,true,Io());
    if(commands!=1 || getters!=1 || lookups!=1 || releases!=2 || outputs!=1 || terminal.load() || busy.load() ||
       strcmp(output.status,"RETURNED") || !output.invoked || Count(owner)!=1 || Count(item)!=1 || bad)return 4;++checks;
    u::Process(1,true,Io());if(reads!=1 || outputs!=1 || commands!=1)return 5;++checks;
    request.seq=2;u::Process(2,true,Io());
    if(commands!=2 || outputs!=2 || releases!=4 || terminal.load() || bad)return 6;++checks;
    for(unsigned m=1;m<=22;++m){
        Reset(m);u::Process(1,true,Io());
        if(!terminal.load() || busy.load() || outputs!=1 || !strcmp(output.status,"RETURNED") || bad)return 100+static_cast<int>(m);
        const unsigned expected[]={0,12,12,2,u::CaptureWorld,u::CurrentPolicy,u::CurrentPolicy,
            u::OwnerCall,u::OwnerCall,u::OwnerCall,u::OwnerResult,u::OwnerResult,
            u::ItemCall,u::ItemCall,u::ItemCall,u::ItemResult,u::ItemResult,u::ItemResult,
            u::OriginalCommand,u::OriginalCommand,9,u::CleanupFailure,u::CleanupFailure};
        if(output.reason!=expected[m])return 430+static_cast<int>(m);
        const char* const expectedStatus=m==1?"CODE_ANCHOR_BLOCKED":m==4?"REFUSED":"UNKNOWN";
        if(strcmp(output.status,expectedStatus) || output.invoked!=(m>=18))return 460+static_cast<int>(m);
        if(m<18 && commands)return 140+static_cast<int>(m);
        if((m==5 && releases!=1) || (m==6 && releases!=2))return 170+static_cast<int>(m);
        if(m>=7 && m<=10 && (lookups || releases))return 180+static_cast<int>(m);
        if((m==12 || m==13 || m==14 || m==15 || m==18 || m==19 || m==20) && releases)return 220+static_cast<int>(m);
        const auto old=commands,oldOutputs=outputs;request.seq=2;u::Process(2,true,Io());
        if(commands!=old || outputs!=oldOutputs)return 260+static_cast<int>(m);++checks;
    }
    for(unsigned m=30;m<=36;++m){Reset(m);u::Process(1,true,Io());
        if(!terminal.load() || busy.load() || bad)return 300+static_cast<int>(m);
        if((m==30 || m==32 || m==33 || m==34 || m==36) && commands)return 350+static_cast<int>(m);
        if(m==31 && outputs)return 390;++checks;}
    Reset();busy.store(true);u::Process(1,true,Io());if(reads || commands || outputs || !terminal.load())return 400;++checks;
    Reset();lastSequence.store(5);u::Process(4,true,Io());if(reads || commands || outputs || terminal.load())return 401;++checks;
    Reset();request.birth=457;u::Process(1,true,Io());if(commands || !terminal.load())return 402;++checks;
    Reset();request.item=0;u::Process(1,true,Io());if(commands || !terminal.load())return 403;++checks;
    if(u::Io{}.execute!=b::Native)return 404;++checks;
    // Sequential non-reentrant source refusal must preserve its original reply.
    Reset(1);u::Process(1,true,Io());
    if(strcmp(output.status,"CODE_ANCHOR_BLOCKED") || output.reason!=12 || output.invoked ||
       commands || getters || lookups || !terminal.load())return 408;++checks;
    forward_diagnostic::Context durable=manual_move::owner;
    wcscpy_s(durable.directory,L"work\\local_original_session\\implementation-1\\manual-source-restart\\fixture-output");
    request.seq=GetCurrentProcessId();request.player=request.item=UINT64_MAX;
    if(!u::Output(durable,request,{"UNKNOWN",7,false}) || u::Output(durable,request,{"RETURNED",0,true}))return 405;++checks;
    wchar_t path[600]{};swprintf_s(path,L"%s\\use-item-result-%u.json",durable.directory,request.seq);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return 406;char saved[768]{};DWORD n=0;
    const bool read=ReadFile(file,saved,767,&n,nullptr)!=FALSE;const BOOL closed=CloseHandle(file);
    if(!read || !closed || !n || n>767 || !strstr(saved,"\"status\":\"UNKNOWN\"") ||
       !strstr(saved,"\"item_identifier\":18446744073709551615") || strstr(saved,"RETURNED"))return 407;++checks;
    return 0;
}
}
namespace registry_fixture {
namespace u=use_item;namespace b=u::binding;
struct alignas(16) Node {unsigned char bytes[0x900]{};};
static Node nodes[12]{};static Pair registered[6]{},rows[2]{};static void* rootSlot=nullptr;
Pair Make(unsigned index) {return {nodes[index].bytes+16,nodes[index].bytes};}
void Store(void* object,size_t offset,uintptr_t value){*reinterpret_cast<uintptr_t*>(static_cast<uint8_t*>(object)+offset)=value;}
void Dword(void* object,size_t offset,uint32_t value){*reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(object)+offset)=value;}
int Check(unsigned& checks) {
    const auto oldBase=scope.base;
    struct Restore {uintptr_t base;~Restore(){scope.base=base;}} restore{oldBase};
    unsigned reason=0;scope.base=0;
    if(b::CodeReady(reason) || reason!=u::CodeContext)return 513;++checks;
    for(auto& n:nodes)n={};
    const auto base=reinterpret_cast<uintptr_t>(&rootSlot)-0x1668790;scope.base=base;
    for(unsigned i=0;i<12;++i)Dword(nodes[i].bytes,8,1);
    for(unsigned i=0;i<6;++i)registered[i]=Make(i);
    const uintptr_t vft[]={0x1182e30,0x11c6878,0x11c7df0,0x1185340,0x1182c50,0x117ead8};
    for(unsigned i=0;i<6;++i)Store(registered[i].object,0,base+vft[i]);
    Pair scene=Make(6);Store(registered[0].object,0x360,reinterpret_cast<uintptr_t>(scene.object));
    Store(registered[0].object,0x368,reinterpret_cast<uintptr_t>(scene.control));Dword(registered[0].object,0x380,5);
    Dword(registered[2].object,0x718,4);Dword(registered[2].object,0x71c,4);
    Store(registered[2].object,0x6e0,reinterpret_cast<uintptr_t>(nodes[8].bytes));Dword(nodes[8].bytes,0,4);
    Store(registered[3].object,0x6d8,1);
    rootSlot=nodes[9].bytes;nodes[9].bytes[0xd8]=1;Store(rootSlot,0xd0,reinterpret_cast<uintptr_t>(nodes[10].bytes));
    Store(nodes[10].bytes,0x180,reinterpret_cast<uintptr_t>(registered));
    Store(nodes[10].bytes,0x188,reinterpret_cast<uintptr_t>(registered+6));
    rows[0]=Make(7);Store(rows[0].control,0,base+0x11c66e8);Store(rows[0].object,0,reinterpret_cast<uintptr_t>(rows[0].object));
    Store(rows[0].object,8,1);Dword(rows[0].object,0x50,0);
    const auto begin=reinterpret_cast<uintptr_t>(rows);
    Store(registered[1].object,0x3d8,begin);Store(registered[1].object,0x3e0,begin+16);Store(registered[1].object,0x3e8,begin+32);
    b::Snapshot s{};s.world.state=registered[0];s.world.ui=registered[4];s.world.actors=registered[5];s.world.scene=scene;
    u::Request r{};r.player=r.item=1;r.map=4;
    if(!b::Registry(r,s,true) || !b::Registry(r,s,false))return 500;++checks;
    // Only map/character were retained by Registry; release these exact fixture leases.
    Release(s.character.control);Release(s.map.control);
    Dword(rows[0].object,0x50,144);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryRawKey)return 501;Dword(rows[0].object,0x50,0);++checks;
    Store(rows[0].object,8,2);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryItemUid)return 502;Store(rows[0].object,8,1);++checks;
    Store(rows[0].control,0,base+0x11c66f0);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryItemType)return 503;Store(rows[0].control,0,base+0x11c66e8);++checks;
    Store(rows[0].object,0,0);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryItemType)return 504;Store(rows[0].object,0,reinterpret_cast<uintptr_t>(rows[0].object));++checks;
    const Pair row=rows[0];rows[0].object=static_cast<uint8_t*>(rows[0].object)+8;
    if(b::Registry(r,s,false,&reason) || reason!=u::RegistryItemType)return 505;rows[0]=row;++checks;
    rows[1]=Make(11);Store(rows[1].control,0,base+0x11c66e8);Store(rows[1].object,0,reinterpret_cast<uintptr_t>(rows[1].object));Store(rows[1].object,8,1);
    Store(registered[1].object,0x3e0,begin+32);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryItemType)return 506;Store(registered[1].object,0x3e0,begin+16);++checks;
    Dword(registered[2].object,0x718,5);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryMap)return 507;Dword(registered[2].object,0x718,4);++checks;
    Dword(registered[0].object,0x380,4);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryLand)return 508;Dword(registered[0].object,0x380,5);++checks;
    Store(registered[3].object,0x6d8,2);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryMap)return 509;Store(registered[3].object,0x6d8,1);++checks;
    Store(registered[1].object,0,base+0x11c6870);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryOwner)return 510;Store(registered[1].object,0,base+0x11c6878);++checks;
    rootSlot=nodes[11].bytes;if(b::Registry(r,s,false,&reason) || reason!=u::RegistryOwner)return 511;rootSlot=nodes[9].bytes;++checks;
    Store(registered[1].object,0x3e8,begin+8);if(b::Registry(r,s,false,&reason) || reason!=u::RegistryRows)return 512;++checks;
    return 0;
}
}
int main(int argc,char** argv){unsigned checks=0;const bool cleanupOnly=argc==2 && !strcmp(argv[1],"cleanup-only");
    const bool anchorOnly=argc==2 && !strcmp(argv[1],"anchor-only");
    const bool stageOnly=argc==2 && !strcmp(argv[1],"stage-only");
    int code=stageOnly?use_fixture::CheckAnchorStage(checks):anchorOnly?use_fixture::CheckAnchorIndex(checks):cleanupOnly?use_fixture::CheckCleanup(checks):use_fixture::Check(checks);
    if(!code && !cleanupOnly && !anchorOnly && !stageOnly)code=registry_fixture::Check(checks);
    std::printf("{\"status\":\"%s\",\"checks\":%u,\"case\":%d,\"scope\":\"UseItem native owner/item stages, noRetry, cleanup and shared mailbox\",\"original_game_calls\":0,\"windows_threads_listeners_created\":0}\n",code?"FAIL":"PASS",checks,code);return code;}
