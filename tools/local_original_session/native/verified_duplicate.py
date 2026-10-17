"""Fresh-verified same-owner duplicate Connect overlay; no exported ABI changes."""


def overlay(probe, abi, replace_once):
    pc, ac = [], []
    abi = replace_once(abi, 'static thread_local TaskFrame taskFrame;', '''static thread_local TaskFrame taskFrame;
struct TaskFrameClear {~TaskFrameClear(){taskFrame={};}};
struct VerifiedTaskFrame {TaskFrame held;void* manager=nullptr;};
static thread_local VerifiedTaskFrame verifiedTaskFrame;
struct VerifiedTaskScope {
    VerifiedTaskFrame previous;bool active=true;
    VerifiedTaskScope():previous(verifiedTaskFrame){verifiedTaskFrame={};}
    void restore() noexcept {if(active){verifiedTaskFrame=previous;active=false;}}
    ~VerifiedTaskScope(){restore();}
};
struct VerifiedDuplicateClaim {bool active=false;NativeProbeFrame frame{};BindingResult fresh;};
static thread_local VerifiedDuplicateClaim probeFreshVerifiedDuplicate;''', ac)
    anchor = 'static void RecordConnect(uintptr_t returnAddress,unsigned index,unsigned phase,bool selectedTask,'
    abi = replace_once(abi, anchor, '''using ConnectedPeerFn=bool(*)(void*) noexcept;
static bool BoundVerifiedConnectedDuplicate(const NativeProbeFrame&,const BindingResult&,
    ConnectedPeerFn peer=ExactConnectedLocalPeer) noexcept;
''' + anchor, ac)
    abi = replace_once(abi,
        'bool duplicate,bool peerVerified,bool bypass,bool result,bool proofOverride,',
        'bool duplicate,bool peerVerified,bool bypass,bool result,bool proofOverride,bool freshVerifiedDuplicate,', ac)
    abi = replace_once(abi, 'char text[800]{};', 'char text[896]{};', ac)
    abi = replace_once(abi,
        r'\"source_mismatch_override\":%s,\"entry_last_error\":%lu',
        r'\"source_mismatch_override\":%s,\"fresh_verified_duplicate\":%s,\"entry_last_error\":%lu', ac)
    abi = replace_once(abi,
        'result?"true":"false",proofOverride?"true":"false",entryError,returnError);',
        'result?"true":"false",proofOverride?"true":"false",freshVerifiedDuplicate?"true":"false",entryError,returnError);', ac)
    abi = replace_once(abi,
        '    BridgeCall call(ForwardRole::Connect);PrepareOwnEligibility();',
        '    BridgeCall call(ForwardRole::Connect);\n'
        '    const auto verifiedClaim=probeFreshVerifiedDuplicate;probeFreshVerifiedDuplicate={};\n'
        '    const bool freshVerifiedDuplicate=verifiedClaim.active;PrepareOwnEligibility();', ac)
    abi = replace_once(abi, '    duplicate=(selectedTask || proofOverride) &&',
        '    duplicate=(selectedTask || proofOverride || freshVerifiedDuplicate) &&', ac)
    abi = replace_once(abi,
        '    const bool peerVerified=duplicate && (port==14000 || port==14030) && ExactConnectedLocalPeer(socket);',
        '''    const bool peerVerified=freshVerifiedDuplicate?
        duplicate && caller==verifiedClaim.frame.original_return &&
        reinterpret_cast<uintptr_t>(socket)==verifiedClaim.frame.rcx && port==14030 &&
        BoundVerifiedConnectedDuplicate(verifiedClaim.frame,verifiedClaim.fresh):
        duplicate && (port==14000 || port==14030) && ExactConnectedLocalPeer(socket);''', ac)
    abi = replace_once(abi,
        '        const bool match=proofOverride?scope.caller.socket.object==socket && scope.caller.socket.control:',
        '        const bool match=(proofOverride || freshVerifiedDuplicate)?scope.caller.socket.object==socket && scope.caller.socket.control:', ac)
    abi = replace_once(abi,
        '    if(bypass){result=true;SetLastError(0);}',
        '''    if(freshVerifiedDuplicate && bypass)bypass=forwardBinding.same_source_proof(
        verifiedClaim.fresh.base,verifiedClaim.fresh.original,ForwardRole::Connect);
    if(bypass){result=true;SetLastError(0);}''', ac)
    abi = replace_once(abi, '    else if(proofOverride){result=false;SetLastError(call.before);}',
        '    else if(proofOverride || freshVerifiedDuplicate){result=false;SetLastError(call.before);}', ac)
    abi = replace_once(abi,
        '                  duplicate,peerVerified,bypass,result,proofOverride,call.before,after);',
        '                  duplicate,peerVerified,bypass,result,proofOverride,freshVerifiedDuplicate,call.before,after);', ac)
    abi = replace_once(abi,
        '    BridgeCall call(ForwardRole::Task);',
        '    BridgeCall call(ForwardRole::Task);VerifiedTaskScope verifiedScope;', ac)
    task_signature = 'extern "C" __declspec(dllexport) void OwnLoginSelectedTaskBridge(void* callable) {'
    borrowed = '''// Additional borrowed scope; original one-shot taskFrame semantics stay intact.
static Pair RetainVerifiedTaskSocket(void* callable,void*& manager,Pair(*retain)(void*)=RetainOriginalRole0) {
    manager=nullptr;bool known=false;
    AcquireSRWLockShared(&scope.caller.lock);
    const auto phase=scope.caller.phase.load();
    known=callable && callable==scope.caller.selectedTask && (phase==Phase::Selected || phase==Phase::Connected);
    ReleaseSRWLockShared(&scope.caller.lock);
    const auto address=reinterpret_cast<uintptr_t>(callable);void* actualManager=nullptr;
    if(!known || !retain || address>UINTPTR_MAX-16 || !SafeCopy(&actualManager,reinterpret_cast<void*>(address+8),sizeof(actualManager)))return {};
    auto sameOwner=[&](const Pair* held) noexcept {
        AcquireSRWLockShared(&scope.caller.lock);const auto current=scope.caller.phase.load();
        const bool ok=callable==scope.caller.selectedTask && actualManager && actualManager==scope.caller.manager &&
            (current==Phase::Selected || current==Phase::Connected) &&
            (!held || (held->object && held->control && (current!=Phase::Connected ||
                (held->object==scope.caller.socket.object && held->control==scope.caller.socket.control))));
        ReleaseSRWLockShared(&scope.caller.lock);return ok;
    };
    if(!sameOwner(nullptr))return {};
    Pair held=retain(actualManager);Held guard{held};
    if(!sameOwner(&held))return {};
    guard.pair={};manager=actualManager;return held;
}
'''
    abi = replace_once(abi, task_signature, borrowed + task_signature, ac)
    abi = replace_once(abi,
        '    Held guard{pair};taskFrame={selected?callable:nullptr,pair};\n    struct Clear {~Clear(){taskFrame={};}} clear;',
        '    Held guard{pair};taskFrame={selected?callable:nullptr,pair};\n'
        '    TaskFrameClear taskClear;\n'
        '    void* duplicateManager=nullptr;Pair duplicatePair=RetainVerifiedTaskSocket(callable,duplicateManager);\n'
        '    Held duplicateGuard{duplicatePair};\n'
        '    verifiedTaskFrame={{duplicateManager?callable:nullptr,duplicatePair},duplicateManager};\n'
        '    struct Clear {VerifiedTaskScope& scope;~Clear(){scope.restore();}} clear{verifiedScope};', ac)
    helper = '''// Full current Connect verification and the still-live selected task scope.
// First Connect remains original. Only its already-connected same socket qualifies.
static bool BoundVerifiedConnectedDuplicate(const NativeProbeFrame& frame,const BindingResult& fresh,
        ConnectedPeerFn peer) noexcept {
    if(!peer || fresh.wrapper!=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge) ||
       fresh.reason!=BindReason::Bound || !scope.selectedReady.load())return false;
    const auto base=fresh.base;const auto& record=OwnForwardLayout::Records[0];
    if(!base || scope.base!=base || fresh.original!=base+record.original_rva ||
       frame.original_return!=base+0x26f8bd || frame.actual_leaf!=base+record.leaf_rva ||
       frame.native_original_target!=fresh.original || static_cast<uint16_t>(frame.r8)!=14030 ||
       !forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect))return false;
    auto sameOwner=[&]() noexcept {
        AcquireSRWLockShared(&scope.caller.lock);
        const bool ok=scope.selectedReady.load() && scope.base==base &&
            verifiedTaskFrame.held.callable && verifiedTaskFrame.held.callable==scope.caller.selectedTask &&
            verifiedTaskFrame.manager && verifiedTaskFrame.manager==scope.caller.manager &&
            verifiedTaskFrame.held.socket.object==reinterpret_cast<void*>(frame.rcx) &&
            verifiedTaskFrame.held.socket.object==scope.caller.socket.object &&
            verifiedTaskFrame.held.socket.control && verifiedTaskFrame.held.socket.control==scope.caller.socket.control &&
            scope.caller.phase.load()==Phase::Connected && scope.caller.connectAttempted && !scope.caller.ownLimitRefused;
        ReleaseSRWLockShared(&scope.caller.lock);return ok;
    };
    if(!sameOwner() || !peer(reinterpret_cast<void*>(frame.rcx)))return false;
    return forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect) && sameOwner();
}
'''
    anchor = 'static bool BoundConnectedDuplicate(const NativeProbeFrame& frame,const BindingResult& result) noexcept {'
    probe = replace_once(probe, anchor, helper + anchor, pc)
    probe = replace_once(probe, '    if(record==0)boundCheckBits=0;',
        '    if(record==0){boundCheckBits=0;probeFreshVerifiedDuplicate={};}', pc)
    anchor = '    RecordSourceRetry(record,result,retryBudget);'
    probe = replace_once(probe, anchor, '''    if(record==0 && target && BoundVerifiedConnectedDuplicate(frame,currentVerified))
        probeFreshVerifiedDuplicate={true,frame,currentVerified};
''' + anchor, pc)
    # Make the distinct claim visible before entering the bridge as well.
    probe = replace_once(probe,
        r'\"connect_role_revalidated\":%s}\n',
        r'\"connect_role_revalidated\":%s,\"fresh_verified_duplicate\":%s}\n', pc)
    probe = replace_once(probe,
        'source_diagnostic::connect_role_revalidated?"true":"false");',
        'source_diagnostic::connect_role_revalidated?"true":"false",probeFreshVerifiedDuplicate.active?"true":"false");', pc)
    return probe, abi, pc, ac


def write_fixture(out, relative, write_new):
    fixture = r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
#include <stdexcept>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
static bool peerOk=true;static unsigned peerCalls=0,mutation=0;
static unsigned originalCalls=0,retainCalls=0;static Pair retained;static bool foreignPair=false;
static bool Original(void*,const char*,uint16_t,int){++originalCalls;return true;}
static Pair RetainPair(void*){++retainCalls;Retain(retained);auto p=retained;if(foreignPair)p.object=reinterpret_cast<void*>(0xdead);return p;}
static bool Peer(void*) noexcept {++peerCalls;
    if(mutation==1)scope.caller.phase=Phase::Cancelled;
    if(mutation==2)forwardBinding.all_roles_verified_base=0;
    if(mutation==3)scope.caller.socket.control=reinterpret_cast<void*>(0x99);
    return peerOk;
}
int main() {
    const uintptr_t base=0x100000;NativeProbeFrame frame{};BindingResult fresh;
    auto reset=[&]() {
        frame={};frame.original_return=base+0x26f8bd;frame.actual_leaf=base+OwnForwardLayout::Records[0].leaf_rva;
        frame.native_original_target=base+OwnForwardLayout::Records[0].original_rva;frame.rcx=0x500000;frame.r8=14030;
        fresh={};fresh.wrapper=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge);fresh.base=base;
        fresh.original=frame.native_original_target;fresh.reason=BindReason::Bound;
        forwardBinding.base=base;forwardBinding.all_roles_verified_base=base;forwardBinding.originals[0]=fresh.original;
        scope.base=base;scope.selectedReady=true;scope.caller.phase=Phase::Connected;scope.caller.connectAttempted=true;scope.caller.ownLimitRefused=false;
        scope.caller.socket={reinterpret_cast<void*>(0x500000),reinterpret_cast<void*>(0x600000)};
        scope.caller.selectedTask=reinterpret_cast<void*>(0x700000);scope.caller.manager=reinterpret_cast<void*>(0x800000);
        verifiedTaskFrame={{scope.caller.selectedTask,scope.caller.socket},scope.caller.manager};taskFrame={};
        peerOk=true;peerCalls=mutation=0;
    };
    unsigned checks=0;reset();
    if(!BoundVerifiedConnectedDuplicate(frame,fresh,Peer)||peerCalls!=1)return 1;++checks;
    for(unsigned which=0;which<16;++which){reset();switch(which){
        case 0:fresh.reason=BindReason::OriginalSourceMismatch;break;case 1:fresh.wrapper=0;break;
        case 2:frame.original_return++;break;case 3:frame.actual_leaf++;break;case 4:frame.native_original_target++;break;
        case 5:forwardBinding.all_roles_verified_base=0;break;case 6:forwardBinding.base++;break;
        case 7:forwardBinding.originals[0]++;break;case 8:frame.r8=14000;break;
        case 9:scope.caller.phase=Phase::Selected;break;case 10:scope.caller.connectAttempted=false;break;
        case 11:scope.caller.ownLimitRefused=true;break;case 12:verifiedTaskFrame.held.callable=reinterpret_cast<void*>(0x70);break;
        case 13:verifiedTaskFrame.held.socket.control=reinterpret_cast<void*>(0x60);break;
        case 14:verifiedTaskFrame.manager=reinterpret_cast<void*>(0x80);break;case 15:verifiedTaskFrame={};break;}
        if(BoundVerifiedConnectedDuplicate(frame,fresh,Peer)||peerCalls)return 10+static_cast<int>(which);++checks;
    }
    reset();peerOk=false;if(BoundVerifiedConnectedDuplicate(frame,fresh,Peer)||peerCalls!=1)return 30;++checks;
    for(unsigned which=1;which<=3;++which){reset();mutation=which;
        if(BoundVerifiedConnectedDuplicate(frame,fresh,Peer)||peerCalls!=1)return 31+static_cast<int>(which);++checks;}
    reset();const auto outer=verifiedTaskFrame;
    {VerifiedTaskScope scopeGuard;if(verifiedTaskFrame.held.callable)return 40;
        verifiedTaskFrame={{reinterpret_cast<void*>(0x123),{}},reinterpret_cast<void*>(0x456)};
        {VerifiedTaskScope inner;if(verifiedTaskFrame.held.callable)return 41;}
        if(verifiedTaskFrame.held.callable!=reinterpret_cast<void*>(0x123))return 42;
    }
    if(verifiedTaskFrame.held.callable!=outer.held.callable)return 43;++checks;
    try{VerifiedTaskScope throwing;throw std::runtime_error("scope");}catch(const std::runtime_error&){}
    if(verifiedTaskFrame.held.callable!=outer.held.callable)return 44;++checks;
    reset();probeFreshVerifiedDuplicate={true,frame,fresh};
    forwardBinding.originals[0]=reinterpret_cast<uintptr_t>(&Original);SetLastError(71);
    if(OwnLoginConnectBridge(reinterpret_cast<void*>(frame.rcx),"127.0.0.1",14030,2000)||originalCalls||GetLastError()!=71||probeFreshVerifiedDuplicate.active)return 45;++checks;
    reset();void* liveCallable[2]={nullptr,scope.caller.manager};alignas(8) long control[8]{};control[2]=10;control[3]=10;
    scope.caller.selectedTask=liveCallable;scope.caller.socket.control=control;retained=scope.caller.socket;
    void* manager=nullptr;retainCalls=0;
    {const Pair p=RetainVerifiedTaskSocket(liveCallable,manager,RetainPair);Held h{p};
        if(p.object!=retained.object||p.control!=control||manager!=scope.caller.manager||retainCalls!=1)return 46;}
    if(control[2]!=10)return 47;++checks;
    foreignPair=true;manager=nullptr;retainCalls=0;
    if(RetainVerifiedTaskSocket(liveCallable,manager,RetainPair).object||manager||retainCalls!=1||control[2]!=10)return 48;++checks;
    foreignPair=false;liveCallable[1]=reinterpret_cast<void*>(0x90);retainCalls=0;
    if(RetainVerifiedTaskSocket(liveCallable,manager,RetainPair).object||retainCalls)return 49;++checks;
    liveCallable[1]=scope.caller.manager;scope.caller.phase=Phase::Cancelled;retainCalls=0;
    if(RetainVerifiedTaskSocket(liveCallable,manager,RetainPair).object||retainCalls)return 50;++checks;
    taskFrame={reinterpret_cast<void*>(0x77),{}};
    try{TaskFrameClear earlyClear;throw std::runtime_error("getter");}catch(const std::runtime_error&){}
    if(taskFrame.callable)return 51;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_access\":false}\n",checks);return 0;
}
'''.replace('OUTPUT', relative)
    write_new(out/'verified_duplicate_mock.cpp', fixture)
    recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\verified_duplicate_mock.exe /Fo:OUTPUT\\verified_duplicate_mock.obj OUTPUT\\verified_duplicate_mock.cpp OUTPUT\\guard.obj user32.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-verified-duplicate-fixture.cmd',recipe)
