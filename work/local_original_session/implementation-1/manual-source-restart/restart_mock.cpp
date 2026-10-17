#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
#include <stdexcept>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace restart_fixture {
namespace r=source_restart;namespace b=r::binding;
using manual_move::terminal;using manual_move::busy;using manual_move::lastSequence;
struct alignas(16) Node {uint8_t bytes[0x600]{};};
static Node root{},button{},other{},network{},otherNetwork{};static char heap[2][32]{};static uint64_t tags[2]{};
static unsigned mode=0,epoch=1,allocs=0,deletes=0,lookups=0,releases=0,pins=0,commands=0,codes=0,contexts=0,reads=0,outputs=0;
static bool bad=false,afterCall=false;static Pair selectedNetwork{};
static r::Request request{};static r::Reply result{};
uint32_t& Count(void* node){return *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(node)+8);}
void Reset(unsigned change=0) {
    root={};button={};other={};network={};otherNetwork={};
    Count(root.bytes)=Count(button.bytes)=Count(other.bytes)=Count(network.bytes)=Count(otherNetwork.bytes)=1;
    mode=change;epoch=1;allocs=deletes=lookups=releases=pins=commands=codes=contexts=reads=outputs=0;
    bad=afterCall=false;terminal.store(false);busy.store(false);lastSequence.store(0);r::restartClaimed=false;
    selectedNetwork={network.bytes+16,network.bytes};
    manual_move::owner={};manual_move::owner.pid=123;manual_move::owner.birth=456;
    wcscpy_s(manual_move::owner.directory,L"synthetic-source-restart");manual_move::ownerBound=true;
    request={};request.pid=123;request.birth=456;request.seq=1;request.phase=r::Phase::LandRestart;
    strcpy_s(request.hash,OWN_EXPECTED_PROGRAM_SHA);result={};
}
bool Owned() noexcept {if(afterCall)bad=true;return true;}
bool Code(unsigned kind) noexcept {if(afterCall)bad=true;++codes;return kind==5 && mode!=14 && !(mode==15&&codes==8);}
bool Start(b::Proof& p,unsigned kind) {
    if(afterCall || kind!=5)bad=true;
    p.ui.kind=5;p.ui.base=0x10000;p.ui.root=epoch;p.ui.node=root.bytes;p.ui.nodeTable=0x20000;
    p.network=selectedNetwork;++Count(p.network.control);return true;
}
bool Current(const b::Proof& p,bool bound) {
    if(afterCall)bad=true;
    if(mode==9 || p.ui.root!=epoch || p.ui.node!=root.bytes || !b::shared::SamePair(p.network,selectedNetwork))return false;
    if(!bound)return true;
    return p.ui.button && p.ui.callable==&tags[mode==11&&lookups==2?1:0];
}
bool Button(b::shared::Proof& p) noexcept {
    if(afterCall)bad=true;if(mode==8)return false;
    p.buttonTable=0x30000;p.callable=&tags[mode==11&&lookups==2?1:0];return true;
}
bool Retain(void* node){if(afterCall)bad=true;++Count(node);return true;}
void Release(void* node) {
    if(afterCall)bad=true;++releases;
    if(mode==18)throw std::runtime_error("release");
    if(!Count(node))bad=true;else --Count(node);
}
void* Allocate(size_t size) {
    if(afterCall || size!=32 || allocs>=2)bad=true;
    if(mode==1)return nullptr;return heap[allocs++];
}
void Delete(void* pointer,size_t size) {
    if(afterCall || size!=32 || (pointer!=heap[0]&&pointer!=heap[1]))bad=true;
    ++deletes;if(mode==19)throw std::runtime_error("delete");
}
void** Lookup(void** out,void** input,const b::Path* path) {
    ++lookups;
    if(afterCall || out==input || *out || *input!=root.bytes || Count(root.bytes)!=3 ||
       path->length!=19 || path->capacity!=31 || path->unused || !path->buffer ||
       memcmp(path->buffer,"Root.Button_Restart",20))bad=true;
    if(mode==3)throw std::runtime_error("lookup before publish");
    *out=mode==10&&lookups==2?other.bytes:button.bytes;++Count(*out);
    if(mode==4)throw std::runtime_error("lookup partial publish");
    if(mode!=6){--Count(*input);*input=nullptr;}
    if(mode==13)++epoch;
    if(mode==21)terminal.store(true);
    return mode==5?nullptr:out;
}
void* Cast(void* node){if(afterCall)bad=true;return mode==7?nullptr:node;}
void Pins(const b::Proof& p) {
    if(afterCall)bad=true;++pins;
    if(mode==20)throw std::runtime_error("pins");
    if(p.network.control)--Count(p.network.control);
    if(mode==12&&pins==1)selectedNetwork={otherNetwork.bytes+16,otherNetwork.bytes};
}
void Command(const b::Proof& p) {
    ++commands;
    if(allocs!=2 || deletes!=2 || lookups!=2 || pins!=2 || Count(root.bytes)!=1 || Count(button.bytes)!=1 ||
       Count(network.bytes)!=1 || p.ui.callable!=&tags[0] || !b::shared::SamePair(p.network,selectedNetwork))bad=true;
    afterCall=true;
    if(mode==16)throw std::runtime_error("whole callback");
    if(mode==17)RaiseException(0xe0424242,0,0,nullptr);
    if(mode==22)terminal.store(true);
}
b::Calls Calls() noexcept {return {Owned,Code,Start,Current,Button,Retain,Release,Allocate,Delete,Lookup,Cast,Pins,Command};}
r::Reply Execute(const r::Request&) noexcept {return b::GuardedUsing(Calls());}
bool Context(forward_diagnostic::Context& c) noexcept {
    ++contexts;c=manual_move::owner;if(mode==30)return false;
    if(mode==31&&contexts==2)++c.birth;return true;
}
bool Thread(const forward_diagnostic::Context&) noexcept {return mode!=32;}
bool Read(const forward_diagnostic::Context&,r::Request& out) noexcept {
    ++reads;out=request;if(mode==33)return false;if(mode==34)++out.seq;return true;
}
bool Output(const forward_diagnostic::Context&,const r::Request& out,const r::Reply& reply) noexcept {
    ++outputs;if(out.seq!=request.seq)bad=true;result=reply;return mode!=35;
}
r::Io Io() noexcept {return {Context,Thread,Read,Execute,Output};}
int Check(unsigned& checks) {
    Reset();char text[513]{};r::Request parsed{};
    sprintf_s(text,"{\"schema\":\"own-source-restart-request-v1\",\"pid\":123,\"birth\":456,\"candidate_sha256\":\"%s\",\"seq\":1,\"command\":\"SourceRestart\",\"phase\":\"LandRestart\"}\r\n",OWN_EXPECTED_PROGRAM_SHA);
    if(!r::Parse(text,parsed) || parsed.phase!=r::Phase::LandRestart || r::Authorize(parsed,1,manual_move::owner,true,0,false))return 1;++checks;
    if(r::Parse("{}",parsed))return 2;++checks;
    char* phase=strstr(text,"LandRestart");if(!phase)return 3;phase[0]='Q';if(r::Parse(text,parsed))return 4;phase[0]='L';++checks;
    const auto n=strlen(text);text[n-2]=' ';if(r::Parse(text,parsed))return 5;++checks;
    Reset();r::Process(1,true,Io());
    if(strcmp(result.status,"RETURNED") || result.reason || !result.invoked || commands!=1 || !r::restartClaimed ||
       bad || terminal.load() || busy.load() || outputs!=1 || Count(root.bytes)!=1 || Count(button.bytes)!=1 || Count(network.bytes)!=1)return 6;++checks;
    r::Process(1,true,Io());if(commands!=1 || outputs!=1 || reads!=1)return 7;++checks;
    request.seq=2;r::Process(2,true,Io());
    if(commands!=1 || outputs!=2 || strcmp(result.status,"UNKNOWN") || result.reason!=9 || result.invoked || !terminal.load())return 8;++checks;
    for(unsigned m=1;m<=22;++m){
        if(m==2)continue;Reset(m);r::Process(1,true,Io());
        const bool invoked=m==16 || m==17 || m==22;
        const char* status=m==14?"CODE_ANCHOR_BLOCKED":"UNKNOWN";
        const unsigned reason=m==14?12:m==3||m==4||m==16||m==17||m==18||m==19||m==20?7:m==22?9:6;
        if(strcmp(result.status,status) || result.reason!=reason || result.invoked!=invoked || !terminal.load() || busy.load() ||
           outputs!=1 || bad || commands!=(invoked?1u:0u))return 100+static_cast<int>(m);
        const auto oldCalls=commands,oldOutputs=outputs;request.seq=2;r::Process(2,true,Io());
        if(commands!=oldCalls || outputs!=oldOutputs)return 130+static_cast<int>(m);++checks;
    }
    for(unsigned m=30;m<=35;++m){Reset(m);r::Process(1,true,Io());
        if(!terminal.load() || busy.load() || bad || ((m==30||m==32||m==33||m==34)&&commands) || (m==31&&outputs))return 170+static_cast<int>(m);++checks;}
    Reset();lastSequence.store(5);r::Process(4,true,Io());if(reads || outputs || commands || terminal.load())return 210;++checks;
    Reset();lastSequence.store(5);request.seq=6;r::Process(6,true,Io());if(commands!=1 || lastSequence.load()!=6 || terminal.load() || bad)return 211;++checks;
    Reset();busy.store(true);r::Process(1,true,Io());if(reads || outputs || commands || !terminal.load())return 212;++checks;
    Reset();request.birth=999;r::Process(1,true,Io());if(commands || !terminal.load() || result.reason!=2)return 213;++checks;
    Reset();auto io=Io();io.execute=nullptr;r::Process(1,true,io);
    if(strcmp(result.status,"BLOCKED_SOURCE_BINDING") || result.reason!=11 || result.invoked || !terminal.load() || !r::restartClaimed)return 214;++checks;
    if(r::Io{}.execute!=b::Native || b::Calls{}.start!=b::Start || b::Calls{}.current!=b::Current ||
       b::Calls{}.button!=b::Button || b::Calls{}.command!=b::Command)return 215;++checks;
    // Real current-caller comparator touches only protected Pair fields, never
    // these intentionally non-dereferenceable target values.
    const Pair synthetic{reinterpret_cast<void*>(uintptr_t(1)),reinterpret_cast<void*>(uintptr_t(2))};
    AcquireSRWLockExclusive(&scope.caller.lock);const Pair saved=scope.caller.network;scope.caller.network=synthetic;
    ReleaseSRWLockExclusive(&scope.caller.lock);
    const bool same=b::CallerNetwork(synthetic);
    const bool changed=b::CallerNetwork({synthetic.object,reinterpret_cast<void*>(uintptr_t(3))});
    AcquireSRWLockExclusive(&scope.caller.lock);scope.caller.network=saved;ReleaseSRWLockExclusive(&scope.caller.lock);
    if(!same || changed)return 217;++checks;
    Reset();forward_diagnostic::Context c=manual_move::owner;
    wcscpy_s(c.directory,L"work\\local_original_session\\implementation-1\\manual-source-restart\\fixture-output");
    request.seq=GetCurrentProcessId();
    if(!r::Output(c,request,{"UNKNOWN",7,false}) || r::Output(c,request,{"RETURNED",0,true}))return 216;++checks;
    return 0;
}
}
namespace attributes_fixture {
namespace u=use_item;namespace b=u::binding;
static unsigned invalidMask=0,queries=0,compares=0,visits=0;
static bool bad=false;
static constexpr uintptr_t base=0x10000;
SIZE_T Query(const void* at,MEMORY_BASIC_INFORMATION* out,size_t size) noexcept {
    ++queries;const auto expected=base+b::codeAnchors[0].rva;
    if(reinterpret_cast<uintptr_t>(at)!=expected || size!=sizeof(*out))bad=true;
    *out={};out->BaseAddress=reinterpret_cast<void*>(expected);out->AllocationBase=reinterpret_cast<void*>(base);
    out->State=MEM_COMMIT;out->Type=MEM_IMAGE;out->Protect=PAGE_EXECUTE_READ;out->RegionSize=0x1000;
    if(invalidMask&1)out->State=MEM_RESERVE;
    if(invalidMask&2)out->Type=MEM_PRIVATE;
    if(invalidMask&4)out->AllocationBase=reinterpret_cast<void*>(base+8);
    if(invalidMask&16)out->Protect=PAGE_NOACCESS;
    if(invalidMask&8)out->Protect|=PAGE_GUARD;
    return sizeof(*out);
}
int Compare(const void*,const void*,size_t) noexcept {++compares;return 0;}
bool Verify(uintptr_t actual,const original_move::Anchor& anchor,unsigned& failure) noexcept {
    ++visits;if(actual!=base || &anchor!=&b::codeAnchors[0])bad=true;
    return original_move::ExecutableAnchorWith(actual,anchor,&failure,Query,Compare);
}
int Check(unsigned& checks) {
    static_assert(u::FirstAnchorAttributeBase==2112 && u::FirstAnchorAttributeBase+4==2116 &&
        u::FirstAnchorStageBase==2048 && b::CodeLiteralLast==1173,"fixed disjoint attribute reasons");
    const unsigned masks[]={1,2,4,8,16,31,30,28,24};
    const unsigned expected[]={2112,2113,2114,2115,2116,2112,2113,2114,2115};
    for(unsigned i=0;i<9;++i){
        invalidMask=masks[i];queries=compares=visits=0;bad=false;unsigned failure=0;
        if(original_move::ExecutableAnchorWith(base,b::codeAnchors[0],&failure,Query,Compare) ||
           failure!=6+expected[i]-2112 || queries!=1 || compares || bad)return 230;
        queries=compares=0;
        if(original_move::ExecutableAnchorWith(base,b::codeAnchors[0],nullptr,Query,Compare) ||
           queries!=1 || compares || bad)return 231;
        queries=compares=visits=0;unsigned reason=21;
        if(b::CodeLiteralReady(base,reason,Verify) || reason!=expected[i] || queries!=1 || compares || visits!=1 || bad)return 232;
        ++checks;
    }
    return 0;
}
}
int main(int argc,char** argv){unsigned checks=0;const bool attributes=argc==2 && !strcmp(argv[1],"attributes-only");
    const int code=attributes?attributes_fixture::Check(checks):restart_fixture::Check(checks);
    std::printf("{\"status\":\"%s\",\"checks\":%u,\"case\":%d,\"scope\":\"SourceRestart once/current typed path/owned Node8B and whole-call boundary\",\"original_game_calls\":0,\"windows_threads_listeners_created\":0}\n",code?"FAIL":"PASS",checks,code);return code;}
