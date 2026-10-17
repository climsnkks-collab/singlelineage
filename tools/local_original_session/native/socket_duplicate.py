"""Apply the existing owned-socket duplicate policy after full Connect verification."""


def overlay(probe, abi, replace_once):
    pc, ac = [], []
    anchor = 'static thread_local bool probeDuplicateBypass=false;'
    abi = replace_once(abi, anchor, anchor + '''
struct VerifiedSocketClaim {bool active=false;NativeProbeFrame frame{};BindingResult fresh;void* control=nullptr;};
static thread_local VerifiedSocketClaim probeFreshVerifiedSocket;
''', ac)
    signature = 'static void RecordConnect(uintptr_t returnAddress,unsigned index,unsigned phase,bool selectedTask,'
    abi = replace_once(abi, signature, '''using ConnectedPeerFn=bool(*)(void*) noexcept;
static bool BoundVerifiedSocketDuplicate(const NativeProbeFrame&,const BindingResult&,void*&,
    ConnectedPeerFn peer=ExactConnectedLocalPeer,void* expectedControl=nullptr) noexcept;
''' + signature, ac)
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
        '    const auto verifiedClaim=probeFreshVerifiedSocket;probeFreshVerifiedSocket={};\n'
        '    const bool freshVerifiedDuplicate=verifiedClaim.active;PrepareOwnEligibility();', ac)
    abi = replace_once(abi, '    duplicate=(selectedTask || proofOverride) &&',
        '    duplicate=(selectedTask || proofOverride || freshVerifiedDuplicate) &&', ac)
    abi = replace_once(abi,
        '    const bool peerVerified=duplicate && (port==14000 || port==14030) && ExactConnectedLocalPeer(socket);',
        '''    void* recheckedControl=nullptr;
    const bool peerVerified=freshVerifiedDuplicate?
        duplicate && caller==verifiedClaim.frame.original_return &&
        reinterpret_cast<uintptr_t>(socket)==verifiedClaim.frame.rcx &&
        port==static_cast<uint16_t>(verifiedClaim.frame.r8) &&
        BoundVerifiedSocketDuplicate(verifiedClaim.frame,verifiedClaim.fresh,recheckedControl,
            ExactConnectedLocalPeer,verifiedClaim.control):
        duplicate && (port==14000 || port==14030) && ExactConnectedLocalPeer(socket);''', ac)
    abi = replace_once(abi,
        '        const bool match=proofOverride?scope.caller.socket.object==socket && scope.caller.socket.control:',
        '''        const bool match=proofOverride?scope.caller.socket.object==socket && scope.caller.socket.control:
          freshVerifiedDuplicate?scope.caller.socket.object==socket && scope.caller.socket.control &&
          scope.caller.socket.control==verifiedClaim.control:''', ac)
    abi = replace_once(abi, '    if(bypass){result=true;SetLastError(0);}',
        '''    if(freshVerifiedDuplicate && bypass)bypass=forwardBinding.same_source_proof(
        verifiedClaim.fresh.base,verifiedClaim.fresh.original,ForwardRole::Connect);
    if(bypass){result=true;SetLastError(0);}''', ac)
    abi = replace_once(abi, '    else if(proofOverride){result=false;SetLastError(call.before);}',
        '    else if(proofOverride || freshVerifiedDuplicate){result=false;SetLastError(call.before);}', ac)
    abi = replace_once(abi,
        '                  duplicate,peerVerified,bypass,result,proofOverride,call.before,after);',
        '                  duplicate,peerVerified,bypass,result,proofOverride,freshVerifiedDuplicate,call.before,after);', ac)
    helper = '''// Same owned-connected socket predicate as legacy BoundConnectedDuplicate,
// additionally requiring a complete fresh Connect result and prior all9 proof.
// Original Task retains its own manager key0 pair across this exact call site;
// task object identity is not part of the pre-existing socket duplicate policy.
static bool BoundVerifiedSocketDuplicate(const NativeProbeFrame& frame,const BindingResult& fresh,
        void*& control,ConnectedPeerFn peer,void* expectedControl) noexcept {
    control=nullptr;
    if(!peer || fresh.wrapper!=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge) ||
       fresh.reason!=BindReason::Bound || !scope.selectedReady.load())return false;
    const auto base=fresh.base;const auto& record=OwnForwardLayout::Records[0];
    if(!base || scope.base!=base || fresh.original!=base+record.original_rva ||
       frame.original_return!=base+0x26f8bd || frame.actual_leaf!=base+record.leaf_rva ||
       frame.native_original_target!=fresh.original ||
       (static_cast<uint16_t>(frame.r8)!=14000 && static_cast<uint16_t>(frame.r8)!=14030) ||
       !forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect))return false;
    void* heldControl=nullptr;
    auto sameOwner=[&](bool capture) noexcept {
        AcquireSRWLockShared(&scope.caller.lock);
        const bool ok=scope.selectedReady.load() && scope.base==base &&
            scope.caller.socket.object==reinterpret_cast<void*>(frame.rcx) && scope.caller.socket.control &&
            (!expectedControl || scope.caller.socket.control==expectedControl) &&
            (capture || scope.caller.socket.control==heldControl) &&
            scope.caller.phase.load()==Phase::Connected && scope.caller.connectAttempted && !scope.caller.ownLimitRefused;
        if(ok && capture)heldControl=scope.caller.socket.control;
        ReleaseSRWLockShared(&scope.caller.lock);return ok;
    };
    if(!sameOwner(true) || !peer(reinterpret_cast<void*>(frame.rcx)))return false;
    if(!forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect) || !sameOwner(false))return false;
    control=heldControl;return true;
}
'''
    anchor = 'static bool BoundConnectedDuplicate(const NativeProbeFrame& frame,const BindingResult& result) noexcept {'
    probe = replace_once(probe, anchor, helper + anchor, pc)
    probe = replace_once(probe, '    if(record==0)boundCheckBits=0;',
        '    if(record==0){boundCheckBits=0;probeFreshVerifiedSocket={};}', pc)
    anchor = '    RecordSourceRetry(record,result,retryBudget);'
    probe = replace_once(probe, anchor, '''    void* duplicateControl=nullptr;
    if(record==0 && target && BoundVerifiedSocketDuplicate(frame,currentVerified,duplicateControl))
        probeFreshVerifiedSocket={true,frame,currentVerified,duplicateControl};
''' + anchor, pc)
    probe = replace_once(probe,
        r'\"connect_role_revalidated\":%s}\n',
        r'\"connect_role_revalidated\":%s,\"fresh_verified_duplicate\":%s}\n', pc)
    probe = replace_once(probe,
        'source_diagnostic::connect_role_revalidated?"true":"false");',
        'source_diagnostic::connect_role_revalidated?"true":"false",probeFreshVerifiedSocket.active?"true":"false");', pc)
    return probe, abi, pc, ac


def write_fixture(out, relative, write_new):
    fixture = r'''#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "OUTPUT/abi_bridge_v2.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
static bool peerOk=true;static unsigned peerCalls=0,mutation=0,originalCalls=0;
static bool Peer(void*) noexcept {++peerCalls;
    if(mutation==1)scope.caller.phase=Phase::Cancelled;
    if(mutation==2)forwardBinding.all_roles_verified_base=0;
    if(mutation==3)scope.caller.socket.control=reinterpret_cast<void*>(0x99);
    return peerOk;
}
static bool Original(void*,const char*,uint16_t,int){++originalCalls;return true;}
int main() {
    const uintptr_t base=0x100000;NativeProbeFrame frame{};BindingResult fresh;void* control=nullptr;
    auto reset=[&]() {
        frame={};frame.original_return=base+0x26f8bd;frame.actual_leaf=base+OwnForwardLayout::Records[0].leaf_rva;
        frame.native_original_target=base+OwnForwardLayout::Records[0].original_rva;frame.rcx=0x500000;frame.r8=14030;
        fresh={};fresh.wrapper=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge);fresh.base=base;
        fresh.original=frame.native_original_target;fresh.reason=BindReason::Bound;
        forwardBinding.base=base;forwardBinding.all_roles_verified_base=base;forwardBinding.originals[0]=fresh.original;
        scope.base=base;scope.selectedReady=true;scope.caller.phase=Phase::Connected;
        scope.caller.connectAttempted=true;scope.caller.ownLimitRefused=false;
        scope.caller.socket={reinterpret_cast<void*>(0x500000),reinterpret_cast<void*>(0x600000)};
        scope.caller.selectedTask=reinterpret_cast<void*>(0x700000);taskFrame={};
        peerOk=true;peerCalls=mutation=originalCalls=0;control=nullptr;
    };
    unsigned checks=0;reset();
    if(!BoundVerifiedSocketDuplicate(frame,fresh,control,Peer)||peerCalls!=1||control!=scope.caller.socket.control)return 1;++checks;
    for(unsigned which=0;which<17;++which){reset();switch(which){
        case 0:scope.caller.phase=Phase::Selected;break;
        case 1:scope.caller.socket.object=reinterpret_cast<void*>(0x51);break;
        case 2:scope.caller.socket.control=nullptr;break;case 3:scope.caller.ownLimitRefused=true;break;
        case 4:scope.caller.connectAttempted=false;break;case 5:frame.original_return++;break;
        case 6:frame.actual_leaf++;break;case 7:frame.native_original_target++;break;
        case 8:fresh.wrapper=0;break;case 9:fresh.reason=BindReason::OriginalSourceMismatch;break;
        case 10:forwardBinding.all_roles_verified_base=0;break;case 11:forwardBinding.originals[0]++;break;
        case 12:forwardBinding.base++;break;case 13:scope.base++;break;
        case 14:scope.selectedReady=false;break;case 15:frame.r8=15000;break;case 16:fresh.original++;break;}
        if(BoundVerifiedSocketDuplicate(frame,fresh,control,Peer)||peerCalls||control)return 10+static_cast<int>(which);++checks;
    }
    reset();peerOk=false;if(BoundVerifiedSocketDuplicate(frame,fresh,control,Peer)||peerCalls!=1||control)return 30;++checks;
    for(unsigned which=1;which<=3;++which){reset();mutation=which;
        if(BoundVerifiedSocketDuplicate(frame,fresh,control,Peer)||peerCalls!=1||control)return 31+static_cast<int>(which);++checks;}
    reset();if(BoundVerifiedSocketDuplicate(frame,fresh,control,Peer,reinterpret_cast<void*>(0x99))||peerCalls||control)return 35;++checks;
    reset();frame.r8=14000;if(!BoundVerifiedSocketDuplicate(frame,fresh,control,Peer)||peerCalls!=1)return 36;++checks;
    reset();scope.caller.selectedTask=reinterpret_cast<void*>(0x123);if(!BoundVerifiedSocketDuplicate(frame,fresh,control,Peer))return 37;++checks;
    reset();probeFreshVerifiedSocket={true,frame,fresh,scope.caller.socket.control};
    forwardBinding.originals[0]=reinterpret_cast<uintptr_t>(&Original);SetLastError(71);
    if(OwnLoginConnectBridge(reinterpret_cast<void*>(frame.rcx),"127.0.0.1",14030,2000)||originalCalls||GetLastError()!=71||probeFreshVerifiedSocket.active)return 38;++checks;
    reset();scope.caller.phase=Phase::Selected;probeFreshVerifiedSocket={};
    forwardBinding.originals[0]=reinterpret_cast<uintptr_t>(&Original);SetLastError(71);
    if(!OwnLoginConnectBridge(reinterpret_cast<void*>(frame.rcx),"127.0.0.1",14030,2000)||originalCalls!=1||probeFreshVerifiedSocket.active)return 39;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_access\":false}\n",checks);return 0;
}
'''.replace('OUTPUT', relative)
    write_new(out/'verified_socket_mock.cpp',fixture)
    recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /FIOUTPUT\\fixture-aliases.hpp /Fe:OUTPUT\\verified_socket_mock.exe /Fo:OUTPUT\\verified_socket_mock.obj OUTPUT\\verified_socket_mock.cpp OUTPUT\\guard.obj user32.lib
exit /b %errorlevel%
'''.replace('OUTPUT',relative.replace('/','\\'))
    write_new(out/'build-verified-socket-fixture.cmd',recipe)
