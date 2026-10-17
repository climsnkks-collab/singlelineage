#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
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
    if(q::Io{}.execute!=nullptr)return 67;++checks;
    // Real CREATE_NEW/flush output seam, only in this owned fixture directory.
    forward_diagnostic::Context c=manual_move::owner;
    wcscpy_s(c.directory,L"work\\local_original_session\\implementation-1\\manual-source-quit\\fixture-output");
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
int main(){unsigned checks=0;const int code=fixture::Check(checks);
    std::printf("{\"status\":\"%s\",\"checks\":%u,\"case\":%d,\"scope\":\"SourceQuit request/shared seq/busy/phase once/immutable result only; production binding blocked\",\"original_game_calls\":0,\"windows_threads_listeners_created\":0}\n",code?"FAIL":"PASS",checks,code);return code;}
