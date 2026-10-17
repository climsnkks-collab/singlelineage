"""Internal fixed-message facade overlay; no original frozen sources modified."""


def overlay(abi, automatic, replace_once):
    ac, uc = [], []
    abi = replace_once(abi, '#include <type_traits>',
        '#include <type_traits>\n#include "tools/local_original_session/native/background_guard.hpp"', ac)
    ending = '''
extern "C" BOOL WINAPI DllMain(HINSTANCE,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH)return BackgroundGuardProcessAttach()?TRUE:FALSE;
    if(reason==DLL_PROCESS_DETACH)BackgroundGuardDetach(reserved!=nullptr);
    return TRUE;
}
'''
    abi = replace_once(abi, '#include "probe.cpp"', '#include "probe.cpp"\n' + ending, ac)
    start = automatic.index('static LRESULT CALLBACK AutoOkGetMessage(')
    automatic = replace_once(automatic, automatic[start:],
        '#include "tools/local_original_session/native/command_bridge.hpp"\n#pragma warning(pop)\n', uc)
    # Keep only the slot selection and Select OK source callbacks. The original
    # create-submit/name-edit workflow is outside this command facade.
    start = automatic.index('static bool AutoCreateSubmitInvoke(')
    stop = automatic.index('#include "tools/local_original_session/native/command_bridge.hpp"', start)
    automatic = replace_once(automatic, automatic[start:stop],
        '// Internal commands exclude the original create-submit workflow.\n', uc)
    automatic = replace_once(automatic, 'static bool AutoCreateValidated(', 'static bool CharacterSlotValidated(', uc)
    automatic = replace_once(automatic, 'if(!AutoCreateValidated(layout,first,reason))', 'if(!CharacterSlotValidated(layout,first,reason))', uc)
    automatic = replace_once(automatic, 'static bool AutoCreateInvoke(', 'static bool CharacterSlotInvoke(', uc)
    automatic = replace_once(automatic, 'static bool AutoSelectOkInvoke(void* layout,unsigned& reason)',
        'static bool CharacterSelectOkInvoke(void* layout,unsigned& reason,bool slotSelected)', uc)
    automatic = replace_once(automatic, '!autoCreateSucceeded.load() || !AutoOkCanonical', '!slotSelected || !AutoOkCanonical', uc)
    automatic = replace_once(automatic, '!base || !scope.selectedReady.load() || !autoOkClaimed.load()\n       ||',
        '!base || !scope.selectedReady.load() || /* Current command, no historical Login latch. */', uc)
    automatic = replace_once(automatic,
        'static std::atomic<bool> autoOkInstallAttempted{false},autoOkClaimed{false};',
        'static std::atomic<bool> autoOkInstallAttempted{false};', uc)
    for index, line in enumerate((
        'static std::atomic<bool> autoCreateClaimed{false};\n',
        'static std::atomic<bool> autoCreateSucceeded{false},autoSelectOkClaimed{false};\n',
        'static std::atomic<bool> autoSelectOkSucceeded{false},autoCreateSubmitClaimed{false};\n',
        'static std::atomic<UINT> autoCreateMessage{0};\n',
        'static std::atomic<UINT> autoSelectOkMessage{0};\n',
        'static std::atomic<UINT> autoCreateSubmitMessage{0};\n',
    )):
        automatic = replace_once(automatic, line,
            f'// Historical automatic command state {index} excluded.\n', uc)
    automatic = replace_once(automatic, '#pragma once',
        '#pragma once\n#pragma warning(push)\n#pragma warning(disable:4505) // Frozen callback helpers retained as a source-bound subset.', uc)
    return abi, automatic, ac, uc


def write_fixture(out, relative, write_new):
    text = r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
#include <string>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
int main() {
    using namespace internal_command;unsigned checks=0,calls=0;
    char text[512]{};sprintf_s(text,"{\"schema\":\"own-internal-command-v1\",\"pid\":123,\"birth\":456,\"candidate_sha256\":\"%s\",\"seq\":1,\"command\":1,\"uid\":0,\"x\":0,\"y\":0}\n",OWN_EXPECTED_PROGRAM_SHA);
    const std::string canonical=text;Request request;
    if(!Parse(text,request)||request.seq!=1||request.command!=1)return 1;++checks;
    const char* invalid[]={"\"seq\":0","\"seq\":2147483648","\"pid\":4294967296","\"birth\":18446744073709551616",
        "\"uid\":18446744073709551616","\"x\":2147483648","\"y\":-2147483649","\"x\":-0","\"seq\":01","\"command\":5"};
    const char* originals[]={"\"seq\":1","\"seq\":1","\"pid\":123","\"birth\":456","\"uid\":0","\"x\":0","\"y\":0","\"x\":0","\"seq\":1","\"command\":1"};
    for(unsigned i=0;i<10;++i){auto bad=canonical;const auto at=bad.find(originals[i]);bad.replace(at,strlen(originals[i]),invalid[i]);
        if(Parse(bad.c_str(),request))return 10+static_cast<int>(i);++checks;}
    if(Parse((canonical+"{}").c_str(),request))return 21;++checks;
    Parse(canonical.c_str(),request);forward_diagnostic::Context c;c.pid=123;c.birth=456;
    if(Authorize(request,1,c,true,0,false))return 22;++checks;
    for(unsigned i=0;i<9;++i){auto r=request;auto identity=c;unsigned posted=1,previous=0;bool thread=true,occupied=false;
        switch(i){case 0:r.pid++;break;case 1:r.birth++;break;case 2:r.hash[0]=r.hash[0]=='a'?'b':'a';break;
        case 3:posted=2;break;case 4:previous=1;break;case 5:thread=false;break;case 6:occupied=true;break;
        case 7:r.uid=1;break;case 8:r.command=4;r.uid=0;break;}
        if(!Authorize(r,posted,identity,thread,previous,occupied))return 30+static_cast<int>(i);++checks;}
    lastSequence=0;busy=false;
    auto run=[&](const Request&) noexcept {++calls;return Reply{"RETURNED",0,true};};
    auto reply=Dispatch(request,1,c,true,true,run);
    if(strcmp(reply.status,"RETURNED")||calls!=1||lastSequence!=1||busy)return 40;++checks;
    reply=Dispatch(request,1,c,true,true,run);if(reply.reason!=3||calls!=1)return 41;++checks;
    request.seq=2;reply=Dispatch(request,2,c,true,false,run);if(reply.reason!=1||calls!=1||lastSequence!=1)return 42;++checks;
    reply=Dispatch(request,2,c,false,true,run);if(reply.reason!=4||calls!=1||lastSequence!=1)return 43;++checks;
    bool nestedBlocked=false;
    reply=Dispatch(request,2,c,true,true,[&](const Request&) noexcept {
        auto nested=request;nested.seq=3;const auto result=Dispatch(nested,3,c,true,true,run);
        nestedBlocked=result.reason==9 && !result.invoked;return Reply{"RETURNED",0,true};
    });
    if(!nestedBlocked||lastSequence!=2||busy||calls!=1||strcmp(reply.status,"RETURNED"))return 44;++checks;
    Request quit=request;quit.command=3;reply=Execute(quit);
    if(strcmp(reply.status,"UNSUPPORTED")||reply.reason!=8||reply.invoked)return 45;++checks;
    Request move=request;move.command=4;move.uid=1;move.x=-1;reply=Execute(move);
    if(reply.reason!=1||reply.invoked)return 46;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false}\n",checks);return 0;
}
'''.replace('OUTPUT', relative)
    write_new(out/'command_mock.cpp',text)
    recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\command_mock.exe /Fo:OUTPUT\\command_mock.obj OUTPUT\\command_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-command-fixture.cmd',recipe)
