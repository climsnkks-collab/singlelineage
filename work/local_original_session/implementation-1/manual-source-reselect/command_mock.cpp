#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
#include <stdexcept>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace fixture {
namespace q=source_quit;
using manual_move::terminal;using manual_move::busy;using manual_move::lastSequence;
static unsigned reads=0,calls=0,outputs=0,contexts=0,mode=0;
static q::Request request{};static q::Reply result{};
bool Context(forward_diagnostic::Context& c) noexcept {
    ++contexts;c=manual_move::owner;
    if(mode==1)return false;if(mode==2&&contexts==2)++c.birth;return true;
}
bool Thread(const forward_diagnostic::Context&) noexcept {return mode!=3;}
bool Read(const forward_diagnostic::Context&,q::Request& r) noexcept {
    ++reads;r=request;if(mode==4)return false;if(mode==5)++r.seq;
    if(mode==6)terminal.store(true);return true;
}
bool Output(const forward_diagnostic::Context&,const q::Request&,const q::Reply& reply) noexcept {
    ++outputs;result=reply;return mode!=7;
}
q::Reply Execute(const q::Request&) noexcept {
    ++calls;
    if(mode==8)q::Process(99,true); // Shared busy: terminal, no nested read.
    if(mode==9)RaiseException(0xe0424242,0,0,nullptr);
    if(mode==10)return {"UNKNOWN",7,true};
    if(mode==11)return {"REFUSED",6,false};
    return {"RETURNED",0,true}; // Injected seam only, original game calls0.
}
q::Io Io() noexcept {return {Context,Thread,Read,Execute,Output};}
void Reset(q::Phase phase=q::Phase::FirstLandQuit,unsigned seq=1) noexcept {
    reads=calls=outputs=contexts=mode=0;result={};terminal.store(false);busy.store(false);lastSequence.store(0);
    q::firstClaimed=q::firstReturned=q::lateClaimed=false;
    auto& owner=manual_move::owner;owner={};owner.pid=123;owner.birth=456;
    wcscpy_s(owner.directory,L"synthetic-source-quit");manual_move::ownerBound=true;
    request={};request.pid=owner.pid;request.birth=owner.birth;request.seq=seq;request.phase=phase;
    strcpy_s(request.hash,OWN_EXPECTED_PROGRAM_SHA);
}
int Check(unsigned& checks) noexcept {
    char text[513]{};q::Request parsed{};
    for(const auto phase:{q::Phase::FirstLandQuit,q::Phase::Quit6Approval}){
        sprintf_s(text,"{\"schema\":\"own-manual-source-quit-request-v1\",\"pid\":123,\"birth\":456,\"candidate_sha256\":\"%s\",\"seq\":8,\"command\":\"SourceQuit\",\"phase\":\"%s\"}\n",OWN_EXPECTED_PROGRAM_SHA,q::Name(phase));
        if(!q::Parse(text,parsed)||parsed.phase!=phase||parsed.seq!=8)return 1;++checks;
    }
    if(q::Parse("{}",parsed))return 2;++checks;
    Reset();auto io=Io();q::Process(1,true,io);
    if(calls!=1||outputs!=1||!q::firstClaimed||!q::firstReturned||terminal.load()||busy.load())return 3;++checks;
    q::Process(1,true,io);if(calls!=1||outputs!=1||reads!=1)return 4;++checks;
    request.phase=q::Phase::Quit6Approval;request.seq=3;q::Process(3,true,io);
    if(calls!=2||outputs!=2||!q::lateClaimed||terminal.load()||lastSequence.load()!=3)return 5;++checks;
    request.seq=4;q::Process(4,true,io);if(calls!=2||outputs!=3||!terminal.load())return 6;++checks;
    Reset(q::Phase::Quit6Approval);q::Process(1,true,Io());if(calls||!terminal.load()||q::lateClaimed)return 7;++checks;
    Reset();q::Process(1,true,Io());request.seq=2;q::Process(2,true,Io());
    if(calls!=1||outputs!=2||!terminal.load())return 8;++checks;
    Reset();auto blocked=Io();blocked.execute=nullptr;q::Process(1,true,blocked);
    if(calls||!terminal.load()||strcmp(result.status,"BLOCKED_SOURCE_BINDING")||result.invoked||q::firstClaimed)return 9;++checks;
    for(unsigned m=1;m<=11;++m){Reset();mode=m;q::Process(1,true,Io());
        if(!terminal.load()||busy.load()||(!strcmp(result.status,"RETURNED")&&outputs&&m!=7))return 10+static_cast<int>(m);
        if(((m==1||m==3||m==4||m==5||m==6)&&calls)||(m==2&&(calls!=1||outputs))||
           (m==8&&reads!=1)||(m==9&&!result.invoked))return 30+static_cast<int>(m);
        const unsigned oldCalls=calls,oldOutputs=outputs;q::Process(2,true,Io());
        if(calls!=oldCalls||outputs!=oldOutputs)return 50+static_cast<int>(m);++checks;}
    Reset();busy.store(true);q::Process(1,true,Io());if(!terminal.load()||reads||outputs||calls)return 62;++checks;
    Reset();lastSequence.store(5);q::Process(4,true,Io());if(reads||outputs||calls||terminal.load())return 63;++checks;
    Reset();lastSequence.store(5);request.seq=6;q::Process(6,true,Io());
    if(calls!=1||lastSequence.load()!=6||terminal.load())return 64;++checks;
    Reset();q::Process(1,false,Io());if(reads||calls||outputs||!terminal.load())return 65;++checks;
    Reset();request.birth=457;q::Process(1,true,Io());if(calls||!terminal.load()||lastSequence.load()!=1)return 66;++checks;
    if(q::Io{}.execute!=q::binding::Native)return 67;++checks;
    // Real CREATE_NEW/flush output seam, only in this owned fixture directory.
    forward_diagnostic::Context c=manual_move::owner;
    wcscpy_s(c.directory,L"work\\local_original_session\\implementation-1\\manual-use-item\\fixture-output");
    q::Request durable=request;durable.seq=GetCurrentProcessId();durable.phase=q::Phase::FirstLandQuit;
    if(!q::Output(c,durable,{"BLOCKED_SOURCE_BINDING",11,false}) || q::Output(c,durable,{"RETURNED",0,true}))return 68;++checks;
    wchar_t path[600]{};swprintf_s(path,L"%s\\source-quit-result-%u.json",c.directory,durable.seq);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return 69;char data[768]{};DWORD n=0;
    const bool read=ReadFile(file,data,767,&n,nullptr)!=FALSE;const BOOL closed=CloseHandle(file);
    if(!read||!closed||!n||!strstr(data,"BLOCKED_SOURCE_BINDING")||strstr(data,"RETURNED"))return 70;++checks;
    return 0;
}
}
namespace binding_fixture {
namespace b=source_quit::binding;using manual_move::terminal;
struct alignas(16) Node {uint8_t data[0x600]{};};
static Node root{},button{},otherButton{};static char heap[2][32]{};
static unsigned mode=0,epoch=1,allocs=0,deletes=0,lookups=0,casts=0,releases=0,pins=0,commands=0,codes=0,owns=0,reads=0;
static bool afterCall=false,badArguments=false;
uint32_t& Count(void* node) {return *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(node)+8);}
void Reset(unsigned change=0) {
    root={};button={};otherButton={};Count(root.data)=Count(button.data)=Count(otherButton.data)=1;
    mode=change;epoch=1;allocs=deletes=lookups=casts=releases=pins=commands=codes=owns=reads=0;
    afterCall=badArguments=false;terminal.store(false);
}
bool Owned() noexcept {++owns;return true;}
bool Code(unsigned kind) noexcept {
    ++codes;if(mode==1)return false;if(codes==8&&mode==10)return false;
    if(codes==8&&mode==12)terminal.store(true);return kind==5||kind==6;
}
bool Start(b::Proof& p,unsigned kind) {
    p.base=0x10000;p.kind=kind;p.root=epoch;p.node=root.data;p.nodeTable=0x20000;
    if(kind==6)p.callable=button.data;return true;
}
bool Current(const b::Proof& p,bool bound) {
    ++reads;if(afterCall)badArguments=true;
    if(p.root!=epoch||p.node!=root.data)return false;
    if(mode==13&&pins==2)return false;
    if(p.kind==6)return p.callable==button.data;
    return !bound||(p.button==button.data&&p.callable==button.data);
}
bool Button(b::Proof& p) noexcept {
    if(mode==9)return false;p.buttonTable=0x30000;p.callable=p.button;return true;
}
bool Retain(void* node) {++Count(node);return true;}
void Release(void* node) {
    ++releases;if(afterCall)badArguments=true;
    if(mode==19)throw std::runtime_error("release");
    if(!Count(node))badArguments=true;else --Count(node);
    if(mode==16&&releases==3)++epoch;
}
void* Allocate(size_t n) {
    if(n!=32||allocs>=2)badArguments=true;if(mode==2)return nullptr;
    return heap[allocs++];
}
void Deallocate(void* pointer,size_t n) {
    if(n!=32||(pointer!=heap[0]&&pointer!=heap[1]))badArguments=true;
    ++deletes;if(mode==20)throw std::runtime_error("free");
}
void** Lookup(void** out,void** input,const b::Path* path) {
    ++lookups;
    if(out==input||*out||*input!=root.data||path->length!=16||path->capacity!=31||path->unused||
       !path->buffer||memcmp(path->buffer,"Root.Button_Quit",17)||Count(root.data)!=3)badArguments=true;
    if(mode==3)throw std::runtime_error("lookup-before-consume");
    *out=mode==14&&lookups==2?otherButton.data:button.data;++Count(*out);
    if(mode==4)throw std::runtime_error("lookup-after-out");
    --Count(*input);if(mode!=6)*input=nullptr;
    if(mode==15)++epoch;
    return mode==5?input:out;
}
void* Cast(void* node) {
    ++casts;if(mode==8)throw std::runtime_error("cast");return mode==7?nullptr:node;
}
void Pins(const b::Proof&) {++pins;if(afterCall)badArguments=true;}
void Command(const b::Proof& p) {
    if((p.kind!=5&&p.kind!=6)||pins!=2||Count(root.data)!=1||Count(button.data)!=1||
       (p.kind==5&&(allocs!=2||deletes!=2)))badArguments=true;
    ++commands;afterCall=true;
    if(mode==17)throw std::runtime_error("command");
    if(mode==18)RaiseException(0xe0424243,0,0,nullptr);
}
b::Calls Calls() {return {Owned,Code,Start,Current,Button,Retain,Release,Allocate,Deallocate,Lookup,Cast,Pins,Command};}
source_quit::Reply Execute(const source_quit::Request& r) noexcept {
    return b::GuardedUsing(r.phase==source_quit::Phase::FirstLandQuit?5u:6u,Calls());
}
int Check(unsigned& checks) {
    Reset();auto reply=b::GuardedUsing(5,Calls());
    if(strcmp(reply.status,"RETURNED")||!reply.invoked||commands!=1||lookups!=2||casts!=2||
       releases!=6||pins!=2||allocs!=2||deletes!=2||badArguments)return 100;++checks;
    for(unsigned m:{1u,2u,3u,4u,5u,6u,7u,8u,9u,10u,12u,13u,14u,15u,16u,17u,18u,19u,20u}){
        Reset(m);reply=b::GuardedUsing(5,Calls());
        if(!strcmp(reply.status,"RETURNED")||badArguments||((m==17||m==18)?(!reply.invoked||commands!=1):(reply.invoked||commands)))return 100+static_cast<int>(m);
        if((m==3||m==4||m==5||m==6||m==8)&&(deletes||pins))return 130+static_cast<int>(m);
        if((m==7||m==9||m==13||m==14||m==15||m==16)&&(Count(root.data)!=1||Count(button.data)!=1||Count(otherButton.data)!=1))return 160+static_cast<int>(m);
        ++checks;
    }
    Reset();reply=b::GuardedUsing(6,Calls());
    if(strcmp(reply.status,"RETURNED")||!reply.invoked||commands!=1||lookups||casts||allocs||deletes||releases||pins!=2||badArguments)return 200;++checks;
    Reset(13);reply=b::GuardedUsing(6,Calls());if(commands||reply.invoked||!strcmp(reply.status,"RETURNED"))return 201;++checks;
    for(unsigned bad=0;bad<4;++bad){unsigned index=0;
        if(b::CodeGate(0x10000,true,0x10000,5,[&](uintptr_t,const original_move::Anchor&) noexcept {return index++!=bad;},
            [](uintptr_t,const internal_quit_source::Anchor&) noexcept {return true;}))return 202;++checks;
    }
    if(b::CodeGate(0x10000,true,0,5,[](uintptr_t,const original_move::Anchor&) noexcept {return true;},
            [](uintptr_t,const internal_quit_source::Anchor&) noexcept {return true;})||
       b::CodeGate(0x10000,true,0x10000,0,[](uintptr_t,const original_move::Anchor&) noexcept {return true;},
            [](uintptr_t,const internal_quit_source::Anchor&) noexcept {return true;}))return 203;++checks;
    if(source_quit::Io{}.execute!=b::Native||sizeof(b::Path)!=32)return 204;++checks;
    unsigned lookupCount=0,route2Count=0;
    if(!b::CodeGate(0x10000,true,0x10000,5,
        [&](uintptr_t,const original_move::Anchor& a) noexcept {++lookupCount;return a.size&&a.size<=sizeof(a.bytes);},
        [&](uintptr_t,const internal_quit_source::Anchor& a) noexcept {++route2Count;return a.size&&a.size<=sizeof(a.bytes);})||
       lookupCount!=4||route2Count!=37)return 207;++checks;
    unsigned route3Count=0;
    if(!b::CodeGate(0x10000,true,0x10000,6,
        [](uintptr_t,const original_move::Anchor&) noexcept {return false;},
        [&](uintptr_t,const internal_quit_source::Anchor& a) noexcept {++route3Count;return a.route==3&&a.size==12;})||route3Count!=1)return 208;++checks;
    const auto* route2=static_cast<const internal_quit_source::Anchor*>(nullptr);
    for(const auto& a:internal_quit_source::anchors)if(a.route==2){route2=&a;break;}
    if(!route2||route2->size<17)return 209;
    alignas(16) unsigned char image[96]{};internal_quit_source::Anchor source=*route2;
    source.rva=16;memcpy(image+source.rva,source.bytes,source.size);const uintptr_t imageBase=reinterpret_cast<uintptr_t>(image);
    auto region=[&](const void*,MEMORY_BASIC_INFORMATION* out,size_t) noexcept -> SIZE_T {
        *out={};out->BaseAddress=image;out->AllocationBase=image;out->AllocationProtect=PAGE_EXECUTE_READ;
        out->RegionSize=sizeof(image);out->State=MEM_COMMIT;out->Protect=PAGE_EXECUTE_READ;out->Type=MEM_IMAGE;
        return sizeof(*out);
    };
    if(!b::ExecutableSourceAnchorWith(imageBase,source,region))return 210;++checks;
    image[source.rva+source.size-1]^=1;
    if(b::ExecutableSourceAnchorWith(imageBase,source,region))return 211;++checks;
    image[source.rva+source.size-1]^=1;
    auto cross=[&](const void* at,MEMORY_BASIC_INFORMATION* out,size_t size) noexcept -> SIZE_T {
        const auto result=region(at,out,size);out->RegionSize=source.rva+source.size-1;return result;
    };
    if(b::ExecutableSourceAnchorWith(imageBase,source,cross))return 212;++checks;
    auto otherBase=[&](const void* at,MEMORY_BASIC_INFORMATION* out,size_t size) noexcept -> SIZE_T {
        const auto result=region(at,out,size);out->AllocationBase=image+8;return result;
    };
    if(b::ExecutableSourceAnchorWith(imageBase,source,otherBase))return 213;++checks;
    auto nonExecutable=[&](const void* at,MEMORY_BASIC_INFORMATION* out,size_t size) noexcept -> SIZE_T {
        const auto result=region(at,out,size);out->Protect=PAGE_READONLY;return result;
    };
    if(b::ExecutableSourceAnchorWith(imageBase,source,nonExecutable))return 217;++checks;
    auto privateType=[&](const void* at,MEMORY_BASIC_INFORMATION* out,size_t size) noexcept -> SIZE_T {
        const auto result=region(at,out,size);out->Type=MEM_PRIVATE;return result;
    };
    if(b::ExecutableSourceAnchorWith(imageBase,source,privateType))return 218;++checks;
    auto invalid=source;invalid.size=0;
    if(b::ExecutableSourceAnchorWith(imageBase,invalid,region))return 214;
    invalid.size=sizeof(invalid.bytes)+1;
    if(b::ExecutableSourceAnchorWith(imageBase,invalid,region))return 215;++checks;
    fixture::Reset();Reset();auto io=fixture::Io();io.execute=Execute;
    source_quit::Process(1,true,io);
    if(commands!=1||!source_quit::firstReturned||terminal.load()||badArguments)return 205;++checks;
    Reset();fixture::request.seq=2;fixture::request.phase=source_quit::Phase::Quit6Approval;
    source_quit::Process(2,true,io);
    if(commands!=1||lookups||!source_quit::lateClaimed||terminal.load()||badArguments)return 206;++checks;
    return 0;
}
}
int main(){unsigned checks=0;const int code=binding_fixture::Check(checks);
    std::printf("{\"status\":\"%s\",\"checks\":%u,\"case\":%d,\"scope\":\"CodeGate 32B source bounds/full literal/single executable region and existing source binding target checks\",\"original_game_calls\":0,\"windows_threads_listeners_created\":0}\n",code?"FAIL":"PASS",checks,code);return code;}
