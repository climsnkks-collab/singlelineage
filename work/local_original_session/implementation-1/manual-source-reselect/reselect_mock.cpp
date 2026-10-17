#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
#include <stdexcept>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace fixture {
namespace r=source_reselect;namespace b=r::binding;
static unsigned mode=0,captures=0,finishes=0,held=0,commands=0,codes=0,contexts=0,outputs=0,reads=0;
static bool after=false,bad=false;static r::Request request{};static r::Reply reply{};
void Reset(unsigned change=0){mode=change;captures=finishes=held=commands=codes=contexts=outputs=reads=0;after=bad=false;
    manual_move::terminal.store(false);manual_move::busy.store(false);manual_move::lastSequence.store(0);
    source_restart::restartClaimed=true;r::firstClaimed=r::firstReturned=r::lateClaimed=false;r::firstRequest={};
    b::firstIdentity={};b::firstIdentityValid=false;manual_move::owner={};manual_move::owner.pid=123;manual_move::owner.birth=456;
    wcscpy_s(manual_move::owner.directory,L"synthetic-reselect");manual_move::ownerBound=true;
    request={};request.pid=123;request.birth=456;request.seq=1;request.saved=UINT64_MAX;request.phase=r::Phase::SelectSlot;
    strcpy_s(request.hash,OWN_EXPECTED_PROGRAM_SHA);strcpy_s(request.referenceHex,"536f6c6f4b6e69676874");
    memcpy(request.reference,"SoloKnight",10);request.referenceLength=10;reply={};}
void CheckTarget(){if(after)bad=true;}
bool Owned() noexcept {CheckTarget();return mode!=1;}
bool Code(unsigned& reason) noexcept {CheckTarget();++codes;if(mode==2){reason=12;return false;}return true;}
bool Capture(const r::Request& req,b::Flight& f){
    CheckTarget();++captures;f.reason=6;if(mode==3)return false;
    auto pair=[](uintptr_t value){return Pair{reinterpret_cast<void*>(value),reinterpret_cast<void*>(value+8)};};
    auto& p=f.proof;p.root=0x10000;p.gi=0x11000;p.registryBegin=0x12000;p.registryEnd=0x12040;
    p.world.ui=pair(0x13000);p.world.state=pair(0x14000);p.world.scene=pair(0x15000);p.world.layout=pair(0x16000);
    p.character=pair(0x17000);p.row=pair(0x18000);p.network=pair(0x19000);p.rows=0x20000;p.rowsEnd=0x20010;
    p.node=reinterpret_cast<void*>(0x21000);p.slot=reinterpret_cast<void*>(0x22000);p.bundle=reinterpret_cast<void*>(0x23000);
    p.head=0x24000;p.count=3;p.ok=req.phase==r::Phase::SelectOK?reinterpret_cast<void*>(uintptr_t(mode==15 && captures==2?0x25008:0x25000)):nullptr;
    ++held;f.owner.stage=b::Stage::Returned;
    if(mode==4 && captures==2)++p.root;
    if(mode==5){f.reason=51;f.owner.stage=b::Stage::Ambiguous;f.ambiguous=true;return false;}
    if(mode==6){f.lookupCalling=true;throw std::runtime_error("partial lookup");}
    if(mode==7)throw std::runtime_error("getter before normal return");
    if(mode==8){f.reason=56;f.ambiguous=true;return false;}
    if(mode==9 && req.phase==r::Phase::SelectOK)++p.rows;
    return true;
}
bool Current(const r::Request&,b::Proof&) noexcept {CheckTarget();return mode!=10;}
void Finish(b::Flight& f){CheckTarget();++finishes;if(mode==11)throw std::runtime_error("release");
    if(f.proof.world.ui.object){if(!held)bad=true;else --held;f.proof.world.ui={};}f.owner.stage=b::Stage::Released;}
void Command(const r::Request&,const b::Proof&){CheckTarget();if(held || captures!=2)bad=true;++commands;after=true;
    if(mode==12)throw std::runtime_error("callback");if(mode==13)RaiseException(0xe0424242,0,0,nullptr);
    if(mode==14)manual_move::terminal.store(true);}
b::Calls Calls(){return {Owned,Code,Capture,Current,Finish,Command};}
r::Reply Execute(const r::Request& req) noexcept {return b::Using(req,Calls());}
bool Context(forward_diagnostic::Context& out) noexcept {++contexts;out=manual_move::owner;if(mode==20)return false;
    if(mode==21 && contexts==2)++out.birth;return true;}
bool Thread(const forward_diagnostic::Context&) noexcept {return mode!=22;}
bool Read(const forward_diagnostic::Context&,r::Request& out) noexcept {++reads;out=request;return mode!=23;}
bool Output(const forward_diagnostic::Context&,const r::Request& req,const r::Reply& value) noexcept {
    if(req.seq!=request.seq)bad=true;++outputs;reply=value;return mode!=24;}
r::Io Io(){return {Context,Thread,Read,Execute,Output};}
void Text(char(&text)[513],const char* phase="SelectSlot",const char* hex="536f6c6f4b6e69676874"){
    sprintf_s(text,"{\"schema\":\"own-source-reselect-request-v1\",\"pid\":123,\"birth\":456,\"candidate_sha256\":\"%s\",\"seq\":1,\"command\":\"SourceReselect\",\"phase\":\"%s\",\"saved_character_uid\":18446744073709551615,\"canonical_reference_utf8_hex\":\"%s\"}",OWN_EXPECTED_PROGRAM_SHA,phase,hex);}
Pair* GoodOwner(uintptr_t root,Pair* out){if(root!=0x10000)bad=true;*out={};return out;}
Pair* WrongOwner(uintptr_t,Pair* out){*out={reinterpret_cast<void*>(0x10000),nullptr};return nullptr;}
Pair* ThrowOwner(uintptr_t,Pair* out){*out={reinterpret_cast<void*>(0x10000),nullptr};throw std::runtime_error("partial pair");}
int Check(unsigned& checks){
    Reset();char text[513]{};r::Request parsed{};Text(text);
    if(!r::Parse(text,parsed) || parsed.saved!=UINT64_MAX || parsed.referenceLength!=10 || strcmp(parsed.referenceHex,request.referenceHex) ||
       r::Authorize(parsed,1,manual_move::owner,true,0,false))return 1;++checks;
    Text(text,"SelectOK");if(!r::Parse(text,parsed) || parsed.phase!=r::Phase::SelectOK)return 2;++checks;
    for(const char* hex:{"","0","00","1f","7f","A0","c080","eda080","f4908080","e282","80","f5808080"}){
        Text(text,"SelectSlot",hex);if(r::Parse(text,parsed))return 3;++checks;}
    for(const char* hex:{"41","eab080","f09f9880","e282ac"}){Text(text,"SelectSlot",hex);if(!r::Parse(text,parsed))return 4;++checks;}
    char maxhex[67]{};memset(maxhex,'4',64);Text(text,"SelectSlot",maxhex);if(!r::Parse(text,parsed) || parsed.referenceLength!=32)return 5;++checks;
    maxhex[64]='4';maxhex[65]='4';Text(text,"SelectSlot",maxhex);if(r::Parse(text,parsed))return 6;++checks;
    Text(text,"SelectSaved");if(r::Parse(text,parsed))return 7;++checks;
    Text(text);strcat_s(text," ");if(r::Parse(text,parsed))return 8;++checks;
    Reset();r::Process(1,true,Io());
    if(strcmp(reply.status,"RETURNED") || reply.reason || !reply.invoked || commands!=1 || held || bad || !r::firstReturned || r::lateClaimed || manual_move::terminal.load())return 9;++checks;
    r::Process(1,true,Io());if(outputs!=1 || commands!=1 || reads!=1)return 10;++checks;
    // Simulate next host poll; no target pointer is retained or dereferenced by the protocol state.
    after=false;captures=0;request.seq=2;request.phase=r::Phase::SelectOK;r::Process(2,true,Io());
    if(strcmp(reply.status,"RETURNED") || reply.reason || !reply.invoked || commands!=2 || held || bad || !r::lateClaimed || manual_move::terminal.load())return 11;++checks;
    after=false;request.seq=3;r::Process(3,true,Io());if(reply.reason!=9 || reply.invoked || commands!=2 || !manual_move::terminal.load())return 12;++checks;
    Reset();request.phase=r::Phase::SelectOK;r::Process(1,true,Io());if(reply.reason!=9 || commands || !manual_move::terminal.load())return 13;++checks;
    Reset();source_restart::restartClaimed=false;r::Process(1,true,Io());if(strcmp(reply.status,"BLOCKED_SOURCE_BINDING") || reply.reason!=10 || commands)return 14;++checks;
    Reset();r::Process(1,true,Io());after=false;request.seq=2;request.phase=r::Phase::SelectOK;--request.saved;r::Process(2,true,Io());
    if(reply.reason!=1 || reply.invoked || commands!=1 || !r::lateClaimed)return 15;++checks;
    Reset();r::Process(1,true,Io());after=false;request.seq=2;request.phase=r::Phase::SelectOK;request.referenceHex[0]='4';r::Process(2,true,Io());
    if(reply.reason!=1 || reply.invoked || commands!=1)return 16;++checks;
    Reset();r::Process(1,true,Io());after=false;captures=0;mode=9;request.seq=2;request.phase=r::Phase::SelectOK;r::Process(2,true,Io());
    if(reply.reason!=63 || reply.invoked || commands!=1 || held || bad)return 17;++checks;
    for(unsigned m=1;m<=14;++m){Reset(m);r::Process(1,true,Io());const bool invoked=m>=12;
        const unsigned reason=m==1?2:m==2?12:m==5?51:m==6||m==7||m==11||m==12||m==13?7:m==8?56:m==14?9:6;
        const char* status=m==2?"CODE_ANCHOR_BLOCKED":m==9?"RETURNED":"UNKNOWN";
        if(m==9){if(strcmp(reply.status,status) || !reply.invoked || held || bad)return 18;}
        else if(strcmp(reply.status,status) || reply.reason!=reason || reply.invoked!=invoked || !manual_move::terminal.load() || bad || commands!=(invoked?1u:0u))return 100+static_cast<int>(m);
        if(m==4 && held)return 19; // Normal refusal cleans both known captures.
        if((m==5||m==6||m==7||m==8||m==11) && !held)return 20; // Ambiguous/fault debt remains; no guessed cleanup.
        ++checks;
    }
    for(unsigned m=20;m<=24;++m){Reset(m);r::Process(1,true,Io());
        if(!manual_move::terminal.load() || manual_move::busy.load() || bad || ((m==20||m==22||m==23)&&commands) || (m==21&&outputs))return 140+static_cast<int>(m);++checks;}
    Reset();manual_move::lastSequence.store(5);r::Process(4,true,Io());if(reads || commands || outputs)return 150;++checks;
    Reset();manual_move::busy.store(true);r::Process(1,true,Io());if(reads || commands || !manual_move::terminal.load())return 151;++checks;
    Reset();request.birth=1;r::Process(1,true,Io());if(reply.reason!=2 || commands)return 152;++checks;
    Reset();auto io=Io();io.execute=nullptr;r::Process(1,true,io);if(strcmp(reply.status,"BLOCKED_SOURCE_BINDING") || reply.reason!=11 || reply.invoked)return 153;++checks;
    // Normal owner getter output was returned to its own cell. Empty is valid ABI but not a usable owner.
    Reset();b::Flight owner{};owner.proof.root=0x10000;
    if(b::GetOwner(owner,GoodOwner) || owner.owner.stage!=b::Stage::Returned || owner.reason!=51 || bad)return 154;++checks;
    owner={};owner.proof.root=0x10000;if(b::GetOwner(owner,WrongOwner) || owner.owner.stage!=b::Stage::Ambiguous || !owner.ambiguous || owner.reason!=51)return 155;++checks;
    owner={};owner.proof.root=0x10000;bool threw=false;try{b::GetOwner(owner,ThrowOwner);}catch(...){threw=true;}
    if(!threw || owner.owner.stage!=b::Stage::Calling || owner.reason!=50)return 156;++checks;
    // Exact source row MSVC string, SSO and heap, no UID field/truncation.
    alignas(16) unsigned char row[32]{};memcpy(row,"SoloKnight",10);*reinterpret_cast<size_t*>(row+16)=10;*reinterpret_cast<size_t*>(row+24)=15;
    if(!b::RowReference(request,row))return 157;++checks;row[0]='X';if(b::RowReference(request,row))return 158;++checks;
    alignas(8) char heap[33]="SoloKnight";*reinterpret_cast<char**>(row)=heap;*reinterpret_cast<size_t*>(row+24)=31;
    if(!b::RowReference(request,row))return 159;++checks;heap[10]='X';if(b::RowReference(request,row))return 160;++checks;
    // Source Rows/current vector and exact slot0 uniqueness without original calls.
    Reset();alignas(16) unsigned char character[0x580]{};alignas(16) LONG controls[3][4]{};
    for(auto& control:controls)control[2]=2;
    alignas(16) unsigned char names[2][32]{};
    for(auto& name:names){memcpy(name,"SoloKnight",10);*reinterpret_cast<size_t*>(name+16)=10;*reinterpret_cast<size_t*>(name+24)=15;}
    Pair vector[2]={{names[0],controls[1]},{names[1],controls[2]}};b::Proof proof{};
    proof.character={character,controls[0]};proof.row=vector[0];proof.rows=reinterpret_cast<uintptr_t>(vector);proof.rowsEnd=proof.rows+16;
    *reinterpret_cast<uintptr_t*>(character+0x570)=proof.rows;*reinterpret_cast<uintptr_t*>(character+0x578)=proof.rowsEnd;
    if(!b::Rows(request,proof,false))return 163;++checks;
    proof.rowsEnd+=16;*reinterpret_cast<uintptr_t*>(character+0x578)=proof.rowsEnd;
    if(b::Rows(request,proof,false))return 164;++checks; // Same reference duplicated.
    names[0][0]='X';if(b::Rows(request,proof,false))return 165;++checks; // Exact target exists only in slot1.
    names[0][0]='S';names[1][0]='X';if(!b::Rows(request,proof,false))return 166;++checks;
    *reinterpret_cast<size_t*>(names[1]+24)=1;if(b::Rows(request,proof,false))return 169;++checks;
    *reinterpret_cast<size_t*>(names[1]+24)=15;
    ++proof.rowsEnd;if(b::Rows(request,proof,false))return 167;++checks;
    proof.rowsEnd-=1;controls[1][2]=0;if(b::Rows(request,proof,false))return 168;++checks;
    if(r::Io{}.execute!=b::Native || b::Calls{}.capture!=b::Capture || b::Calls{}.current!=b::Current || b::Calls{}.command!=b::Command || b::Calls{}.finish!=b::Finish)return 161;++checks;
    Reset();forward_diagnostic::Context c=manual_move::owner;
    CreateDirectoryW(L"work\\local_original_session\\implementation-1\\manual-source-reselect\\fixture-output",nullptr);
    wcscpy_s(c.directory,L"work\\local_original_session\\implementation-1\\manual-source-reselect\\fixture-output");request.seq=GetCurrentProcessId();
    if(!r::Output(c,request,{"UNKNOWN",7,false}) || r::Output(c,request,{"RETURNED",0,true}))return 162;++checks;
    return 0;
}
int OkIdentityCheck(unsigned& checks){
    for(unsigned change:{0u,15u}){
        Reset();r::Process(1,true,Io());if(strcmp(reply.status,"RETURNED") || commands!=1 || held || bad)return 170;
        after=false;captures=0;mode=change;request.seq=2;request.phase=r::Phase::SelectOK;r::Process(2,true,Io());
        if(change){if(strcmp(reply.status,"UNKNOWN") || reply.reason!=6 || reply.invoked || commands!=1 ||
            !manual_move::terminal.load() || held || bad || captures!=2)return 171;}
        else if(strcmp(reply.status,"RETURNED") || reply.reason || !reply.invoked || commands!=2 ||
            manual_move::terminal.load() || held || bad || captures!=2)return 172;
        ++checks;
    }
    return 0;
}
static unsigned invokeChecks=0;static bool invokeMatches=true;
bool VerifyInvoke(uintptr_t table) noexcept {++invokeChecks;if(table!=0x10000+0x1214ee8)bad=true;return invokeMatches;}
int OkActiveCheck(unsigned& checks){
    alignas(16) unsigned char button[0x600]{};void* const layout=reinterpret_cast<void*>(0x40000);
    for(unsigned change=0;change<7;++change){
        memset(button,0,sizeof(button));invokeChecks=0;invokeMatches=true;bad=false;
        *reinterpret_cast<void**>(button+0x528)=button+0x4f0;
        *reinterpret_cast<uintptr_t*>(button+0x4f0)=0x10000+0x1214ee8;
        *reinterpret_cast<void**>(button+0x4f8)=layout;
        if(change==1)*reinterpret_cast<void**>(button+0x528)=nullptr;
        if(change==2)*reinterpret_cast<void**>(button+0x528)=reinterpret_cast<void*>(1);
        if(change==3)*reinterpret_cast<void**>(button+0x528)=button+0x4f8;
        if(change==4)*reinterpret_cast<uintptr_t*>(button+0x4f0)+=8;
        if(change==5)invokeMatches=false;
        if(change==6)*reinterpret_cast<void**>(button+0x4f8)=reinterpret_cast<void*>(0x40008);
        if(b::InlineOk(button,0x10000,layout,VerifyInvoke)!=(change==0) || bad ||
           invokeChecks!=(change>=1&&change<=4?0u:1u))return 180;
        ++checks;
    }
    return 0;
}

bool VerifySlotInvoke(uintptr_t table) noexcept {++invokeChecks;if(table!=0x10000+0x1217508)bad=true;return invokeMatches;}
int SlotActiveCheck(unsigned& checks){
    alignas(16) unsigned char button[0x600]{},bundle[0x90]{};void* const layout=reinterpret_cast<void*>(0x40000);
    for(unsigned change=0;change<14;++change){
        memset(button,0,sizeof(button));memset(bundle,0,sizeof(bundle));invokeChecks=0;invokeMatches=true;bad=false;
        *reinterpret_cast<void**>(button+0x528)=button+0x4f0;
        *reinterpret_cast<uintptr_t*>(button+0x4f0)=0x10000+0x1217508;
        *reinterpret_cast<void**>(button+0x4f8)=bundle;
        *reinterpret_cast<void**>(bundle+0x88)=button;*reinterpret_cast<void**>(bundle+0x40)=bundle+8;
        *reinterpret_cast<uintptr_t*>(bundle+8)=0x10000+0x1214eb0;
        *reinterpret_cast<uintptr_t*>(bundle+0x48)=0x10000+0x1214e78;
        *reinterpret_cast<void**>(bundle+0x10)=layout;
        void* supplied=bundle;
        if(change==1)*reinterpret_cast<void**>(button+0x528)=nullptr;
        if(change==2)*reinterpret_cast<void**>(button+0x528)=reinterpret_cast<void*>(1);
        if(change==3)*reinterpret_cast<uintptr_t*>(button+0x4f0)+=8;
        if(change==4)invokeMatches=false;
        if(change==5)*reinterpret_cast<void**>(button+0x4f8)=bundle+8;
        if(change==6)*reinterpret_cast<void**>(bundle+0x88)=button+8;
        if(change==7)*reinterpret_cast<void**>(bundle+0x40)=nullptr;
        if(change==8)*reinterpret_cast<void**>(bundle+0x40)=reinterpret_cast<void*>(1);
        if(change==9)*reinterpret_cast<uintptr_t*>(bundle+8)+=8;
        if(change==10)*reinterpret_cast<uintptr_t*>(bundle+0x48)+=8;
        if(change==11)*reinterpret_cast<void**>(bundle+0x10)=reinterpret_cast<void*>(0x40008);
        if(change==12)*reinterpret_cast<int32_t*>(bundle+0x18)=1;
        if(change==13){supplied=reinterpret_cast<void*>(1);*reinterpret_cast<void**>(button+0x4f8)=supplied;}
        if(b::InlineSlot(button,supplied,0x10000,layout,VerifySlotInvoke)!=(change==0) || bad ||
           invokeChecks!=(change>=1&&change<=3?0u:1u))return 181;
        ++checks;
    }
    return 0;
}

}
int main(int argc,char** argv){unsigned checks=0;
    const bool ok=argc==2 && !strcmp(argv[1],"ok-identity-only");
    const bool active=argc==2 && !strcmp(argv[1],"ok-active-only");
    const bool slot=argc==2 && !strcmp(argv[1],"slot-active-only");
    const int result=slot?fixture::SlotActiveCheck(checks):active?fixture::OkActiveCheck(checks):ok?fixture::OkIdentityCheck(checks):fixture::Check(checks);
    std::printf("{\"status\":\"%s\",\"checks\":%u,\"case\":%d,\"scope\":\"%s\",\"original_game_calls\":0,\"windows_threads_listeners_created\":0}\n",result?"FAIL":"PASS",checks,result,
        slot?"SourceReselect strict current Slot outer/first active and captures":active?"SourceReselect strict current inline OK active/vptr/invoke/capture":ok?"SourceReselect same-phase OK numeric identity negative and positive":"SourceReselect two explicit phases/UTF8/once/current/lease/exception");return result;}
