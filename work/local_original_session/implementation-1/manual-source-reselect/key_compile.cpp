#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
#include <map>
#include <string>
#include <stdexcept>
#define CHECK(x) do{if(!(x))throw std::runtime_error(#x);}while(false)
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
static std::map<std::string,std::string> output;static bool dropSink=false;
static bool Context(forward_diagnostic::Context& c) noexcept {c.pid=100;c.birth=200;return true;}
static void Output(const char* leaf,const char* text,int n) noexcept {try{if(!dropSink)output[leaf]=std::string(text,static_cast<size_t>(n));}catch(...){}SetLastError(99);}
static unsigned keyCalls=0,versionCalls=0;static bool throwing=false,wrongOpcode=false,nesting=false,throwVersion=false;static unsigned nestedDepth=0;static void* expectedHolder=nullptr;static void* expectedManager=nullptr;static void* expectedMessage=reinterpret_cast<void*>(3);
static void Version(void* manager,uintptr_t unused,uint16_t opcode,void* message) {CHECK(manager==expectedManager&&unused==0x12345678&&opcode==(wrongOpcode?0x4f3d:0x4e34)&&message==expectedMessage&&GetLastError()==41);++versionCalls;if(throwVersion){SetLastError(78);throw std::runtime_error("original-version");}SetLastError(77);}
static void Key(void* holder) {CHECK(holder==expectedHolder&&GetLastError()==41);++keyCalls;if(nesting && !nestedDepth){++nestedDepth;OwnKeyTaskBridge(holder);--nestedDepth;CHECK(keyExecution.recording);SetLastError(41);}OwnKeyVersionBridge(expectedManager,0x12345678,wrongOpcode?0x4f3d:0x4e34,expectedMessage);if(throwing){SetLastError(76);throw std::runtime_error("original-key");}SetLastError(74);}
static void Reset(){output.clear();keyCalls=versionCalls=0;key_diagnostic::invoke_claim=false;key_diagnostic::version_claim=false;key_diagnostic::order=0;forward_diagnostic::attempt=false;forward_diagnostic::returned=false;throwing=wrongOpcode=nesting=dropSink=throwVersion=false;}
static void Save(const char* leaf,const wchar_t* path){FILE* f=nullptr;CHECK(!_wfopen_s(&f,path,L"wbx")&&f);const auto& text=output.at(leaf);CHECK(text.size()<4096&&fwrite(text.data(),1,text.size(),f)==text.size());CHECK(!fclose(f));}
static void NewTwoUnwind(){
    const uintptr_t functions[]={reinterpret_cast<uintptr_t>(&OwnForwardKeyTaskShim),reinterpret_cast<uintptr_t>(&OwnForwardKeyVersionShim)};
    const uintptr_t ends[]={reinterpret_cast<uintptr_t>(&OwnForwardKeyTaskShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardKeyVersionShimEnd)};
    for(unsigned i=0;i<2;++i){uintptr_t image=0;RUNTIME_FUNCTION rf{};CHECK(Lookup(functions[i],image,rf));CHECK(image+rf.BeginAddress==functions[i]&&image+rf.EndAddress==ends[i]);
        unsigned char info[16]{};CHECK(SafeCopy(info,reinterpret_cast<void*>(image+rf.UnwindData),16)&&!memcmp(info,ShimUnwind,16));
        alignas(16) uint64_t stack[128]{};const auto origin=reinterpret_cast<uintptr_t>(stack+64);stack[64]=0x123456;*reinterpret_cast<uint64_t*>(origin-8)=0x112233;
        CONTEXT c{};c.Rsp=origin-0xf8;c.Rbp=origin-8;c.Rip=image+rf.BeginAddress+32;PVOID handler=nullptr;DWORD64 establisher=0;
        RtlVirtualUnwind(UNW_FLAG_NHANDLER,image,c.Rip,&rf,&c,&handler,&establisher,nullptr);CHECK(c.Rip==0x123456&&c.Rsp==origin+8&&c.Rbp==0x112233);
    }
}
int KeyFixtureCompileOnly(){try{
 selected_diagnostic::test_context=Context;key_diagnostic::test_output=Output;
 void* holder[4]={nullptr,reinterpret_cast<void*>(0x55)};expectedHolder=holder;expectedManager=holder[1];scope.selectedReady=true;scope.caller.manager=expectedManager;scope.caller.network={reinterpret_cast<void*>(1),reinterpret_cast<void*>(2)};
 forwardBinding.base=0x1000;forwardBinding.originals[7]=reinterpret_cast<uintptr_t>(&Key);forwardBinding.originals[8]=reinterpret_cast<uintptr_t>(&Version);test_key_version_return=0x1000+0x26e8e5;
 Reset();SetLastError(41);OwnKeyTaskBridge(holder);CHECK(GetLastError()==74&&keyCalls==1&&versionCalls==1&&output.size()==2&&!forward_diagnostic::attempt&&!forward_diagnostic::returned);
 CHECK(output.at("key-task-invoke.json").find("\"return_state\":1")!=std::string::npos&&output.at("key-task-invoke.json").find("\"return_order\":4")!=std::string::npos);
 CHECK(output.at("key-version-send.json").find("\"opcode\":20020")!=std::string::npos&&output.at("key-version-send.json").find("\"entry_order\":2")!=std::string::npos&&output.at("key-version-send.json").find("\"return_order\":3")!=std::string::npos);
 Save("key-task-invoke.json",L"work/local_original_session/implementation-1/manual-source-reselect/fixture-key/sample-key-normal.json");Save("key-version-send.json",L"work/local_original_session/implementation-1/manual-source-reselect/fixture-key/sample-version-normal.json");
 Reset();throwing=true;SetLastError(41);bool caught=false;try{OwnKeyTaskBridge(holder);}catch(const std::runtime_error& e){caught=std::string(e.what())=="original-key";}
 CHECK(caught&&GetLastError()==76&&keyCalls==1&&versionCalls==1&&!keyExecution.recording&&output.at("key-task-invoke.json").find("\"return_state\":2")!=std::string::npos);
 Save("key-task-invoke.json",L"work/local_original_session/implementation-1/manual-source-reselect/fixture-key/sample-key-exception.json");
 Reset();scope.caller.manager=reinterpret_cast<void*>(0x66);SetLastError(41);OwnKeyTaskBridge(holder);CHECK(keyCalls==1&&versionCalls==1&&output.empty()&&GetLastError()==74);
 Reset();scope.caller.manager=expectedManager;wrongOpcode=true;SetLastError(41);OwnKeyTaskBridge(holder);CHECK(keyCalls==1&&versionCalls==1&&output.size()==1);
 Reset();scope.selectedReady=false;SetLastError(41);OwnKeyTaskBridge(holder);CHECK(keyCalls==1&&versionCalls==1&&output.empty()&&GetLastError()==74);
 Reset();scope.selectedReady=true;scope.caller.manager=expectedManager;nesting=true;SetLastError(41);OwnKeyTaskBridge(holder);CHECK(keyCalls==2&&versionCalls==2&&output.size()==2&&!keyExecution.recording&&GetLastError()==74);
 Reset();dropSink=true;SetLastError(41);OwnKeyTaskBridge(holder);CHECK(keyCalls==1&&versionCalls==1&&output.empty()&&GetLastError()==74&&!forward_diagnostic::attempt&&!forward_diagnostic::returned);
 Reset();throwVersion=true;SetLastError(41);bool versionCaught=false;try{OwnKeyTaskBridge(holder);}catch(const std::runtime_error& e){versionCaught=std::string(e.what())=="original-version";}
 CHECK(versionCaught&&GetLastError()==78&&keyCalls==1&&versionCalls==1&&output.at("key-version-send.json").find("\"return_state\":2")!=std::string::npos&&!keyExecution.recording);
 Save("key-version-send.json",L"work/local_original_session/implementation-1/manual-source-reselect/fixture-key/sample-version-exception.json");
 Reset();{key_diagnostic::Record entry(false,true);CHECK(output.at("key-task-invoke.json").find("\"return_state\":0")!=std::string::npos&&output.at("key-task-invoke.json").find("\"return_order\":null")!=std::string::npos);Save("key-task-invoke.json",L"work/local_original_session/implementation-1/manual-source-reselect/fixture-key/sample-key-entry-only.json");}
 NewTwoUnwind();
 puts("2 focused KEY/version production-wrapper/emitter fixture PASS: exact args/once/return/EH/LastError/foreign/old counters/order; Native/game 0; fake binding is contract-only");return 0;
 }catch(const std::exception& e){printf("key mock FAIL %.150s\n",e.what());return 1;}}



