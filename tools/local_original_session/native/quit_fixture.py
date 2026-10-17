"""Targeted production Quit proof/lifetime orchestration checks; compile only."""


def write_fixture(out, relative, write_new):
    source = r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
int main(){
    using namespace internal_command;using namespace quit_detail;unsigned checks=0,calls=0,reads=0;
    for(unsigned scene=0;scene<8;++scene){const unsigned expected=scene==3||scene==4?1:scene==5?2:scene==6?3:0;
        if(Route(scene)!=expected)return 1;++checks;}
    Proof proof;proof.sceneKind=5;proof.base=0x100000;proof.root=1;proof.gi=2;proof.application=3;proof.head=4;proof.count=5;
    proof.ui={reinterpret_cast<void*>(6),reinterpret_cast<void*>(7)};
    proof.state={reinterpret_cast<void*>(8),reinterpret_cast<void*>(9)};
    proof.scene={reinterpret_cast<void*>(10),reinterpret_cast<void*>(11)};
    proof.layout={reinterpret_cast<void*>(12),reinterpret_cast<void*>(13)};proof.callable=14;
    bool released=false,calledBeforeRelease=false;
    const auto prepare=[&](Proof& p)noexcept{p=proof;released=true;return true;};
    const auto fresh=[&](Proof& p)noexcept{++reads;p=proof;return released;};
    const auto invoke=[&](const Proof&)noexcept{++calls;calledBeforeRelease=!released;return true;};
    auto reply=Run(prepare,fresh,invoke);
    if(strcmp(reply.status,"RETURNED")||!reply.invoked||reply.reason||calls!=1||reads!=1||calledBeforeRelease)return 2;++checks;
    calls=reads=0;reply=Run([](Proof&)noexcept{return false;},fresh,invoke);
    if(reply.invoked||reply.reason!=6||calls||reads)return 3;++checks;
    calls=reads=0;reply=Run(prepare,[](Proof&)noexcept{return false;},invoke);
    if(reply.invoked||reply.reason!=6||calls)return 4;++checks;
    for(unsigned field=0;field<16;++field){calls=0;
        reply=Run(prepare,[&](Proof& p)noexcept{p=proof;switch(field){
          case 0:++p.base;break;case 1:++p.root;break;case 2:++p.gi;break;case 3:++p.application;break;
          case 4:++p.head;break;case 5:++p.count;break;case 6:++p.callable;break;case 7:p.sceneKind=6;break;
          case 8:p.ui.object=nullptr;break;case 9:p.ui.control=nullptr;break;case 10:p.state.object=nullptr;break;
          case 11:p.state.control=nullptr;break;case 12:p.scene.object=nullptr;break;case 13:p.scene.control=nullptr;break;
          case 14:p.layout.object=nullptr;break;case 15:p.layout.control=nullptr;break;}return true;},invoke);
        if(reply.invoked||reply.reason!=6||calls)return 10+static_cast<int>(field);++checks;}
    for(unsigned scene:{3u,4u,5u,6u}){proof.sceneKind=scene;calls=0;reply=Run(prepare,fresh,invoke);
        if(!reply.invoked||reply.reason||calls!=1)return 30;++checks;}
    proof.sceneKind=2;calls=reads=0;reply=Run(prepare,fresh,invoke);
    if(reply.invoked||calls||reads)return 31;++checks;
    proof.sceneKind=6;calls=0;reply=Run(prepare,fresh,[&](const Proof&)noexcept{++calls;return false;});
    if(reply.invoked||reply.reason!=7||calls!=1)return 32;++checks;
    unsigned copies=0,codes=0;bool copiedMismatch=false;
    const auto code=[&](uintptr_t,size_t)noexcept{++codes;return true;};
    const auto copy=[&](void* dst,const void* from,size_t size)noexcept{++copies;
        for(const auto& a:internal_quit_source::anchors)if(proof.base+a.rva==reinterpret_cast<uintptr_t>(from)&&a.size==size){
            memcpy(dst,a.bytes,size);if(copiedMismatch)*static_cast<unsigned char*>(dst)^=1;return true;}return false;};
    for(unsigned scene:{3u,5u,6u}){proof.sceneKind=scene;copies=codes=0;
        if(!quit_detail::SourceProof(proof,code,copy)||!copies||copies!=codes)return 33;++checks;}
    copies=codes=0;if(quit_detail::SourceProof(proof,[](uintptr_t,size_t)noexcept{return false;},copy)||copies)return 34;++checks;
    copies=codes=0;if(quit_detail::SourceProof(proof,code,[](void*,const void*,size_t)noexcept{return false;})||codes!=1)return 35;++checks;
    copies=codes=0;copiedMismatch=true;if(quit_detail::SourceProof(proof,code,copy)||codes!=1||copies!=1)return 36;++checks;
    Request quit;quit.command=3;reply=internal_command::Execute(quit);
    if(reply.invoked||reply.reason!=6||strcmp(reply.status,"REFUSED"))return 37;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_or_desktop_operations\":false}\n",checks);return 0;
}
'''.replace('OUTPUT', relative)
    write_new(out/'quit_mock.cpp', source)
    recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Itools\\local_original_session\\native\\vendor\\detours\\src /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\quit_mock.exe /Fo:OUTPUT\\quit_mock.obj OUTPUT\\quit_mock.cpp OUTPUT\\guard.obj user32.lib tools\\local_original_session\\native\\vendor\\detours\\lib.X64\\detours.lib
exit /b %errorlevel%
'''.replace('OUTPUT', relative.replace('/', '\\'))
    write_new(out/'build-quit-fixture.cmd', recipe)
