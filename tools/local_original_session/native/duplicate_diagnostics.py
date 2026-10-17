"""Bounded scalar diagnostics only for the fresh duplicate and task scope."""


def overlay(probe, abi, replace_once):
    pc, ac = [], []
    anchor = 'static thread_local VerifiedDuplicateClaim probeFreshVerifiedDuplicate;'
    abi = replace_once(abi, anchor, anchor + '''
struct FreshDuplicateEvidence {unsigned reason=99,owner_bits=0,port=0;bool scope_present=false;};
static thread_local FreshDuplicateEvidence freshDuplicateEvidence;
struct TaskBorrowEvidence {unsigned reason=99,phase=99;bool known=false,manager_copied=false,getter_called=false;};
''', ac)
    # Invocation-local evidence is passed through the actual borrowed-pair helper.
    abi = replace_once(abi,
        'static Pair RetainVerifiedTaskSocket(void* callable,void*& manager,Pair(*retain)(void*)=RetainOriginalRole0) {',
        'static Pair RetainVerifiedTaskSocket(void* callable,void*& manager,Pair(*retain)(void*)=RetainOriginalRole0,TaskBorrowEvidence* evidence=nullptr) {', ac)
    abi = replace_once(abi, '    manager=nullptr;bool known=false;',
        '    manager=nullptr;bool known=false;if(evidence)*evidence={};', ac)
    abi = replace_once(abi,
        '    known=callable && callable==scope.caller.selectedTask && (phase==Phase::Selected || phase==Phase::Connected);',
        '    known=callable && callable==scope.caller.selectedTask && (phase==Phase::Selected || phase==Phase::Connected);\n'
        '    if(evidence){evidence->phase=static_cast<unsigned>(phase);evidence->known=known;}', ac)
    abi = replace_once(abi,
        '    if(!known || !retain || address>UINTPTR_MAX-16 || !SafeCopy(&actualManager,reinterpret_cast<void*>(address+8),sizeof(actualManager)))return {};',
        '    if(!known || !retain || address>UINTPTR_MAX-16 || !SafeCopy(&actualManager,reinterpret_cast<void*>(address+8),sizeof(actualManager))){if(evidence)evidence->reason=1;return {};}\n'
        '    if(evidence)evidence->manager_copied=true;', ac)
    abi = replace_once(abi, '    if(!sameOwner(nullptr))return {};',
        '    if(!sameOwner(nullptr)){if(evidence)evidence->reason=2;return {};}', ac)
    abi = replace_once(abi, '    Pair held=retain(actualManager);Held guard{held};',
        '    if(evidence)evidence->getter_called=true;\n    Pair held=retain(actualManager);Held guard{held};', ac)
    abi = replace_once(abi, '    if(!sameOwner(&held))return {};\n    guard.pair={};manager=actualManager;return held;',
        '    if(!sameOwner(&held)){if(evidence)evidence->reason=3;return {};}\n'
        '    if(evidence)evidence->reason=0;\n    guard.pair={};manager=actualManager;return held;', ac)
    signature = 'extern "C" __declspec(dllexport) void OwnLoginSelectedTaskBridge(void* callable) {'
    emitter = r'''static std::atomic<unsigned> taskScopeEvidenceIndex{0},taskEntryEvidenceIndex{0};
static void RecordTaskEntry(void* callable) noexcept {
    const DWORD before=GetLastError();const unsigned index=taskEntryEvidenceIndex.fetch_add(1);
    if(index<8) {
        forward_diagnostic::Context c{};
        if(selected_diagnostic::valid_context(c)) {
            AcquireSRWLockShared(&scope.caller.lock);
            const unsigned phase=static_cast<unsigned>(scope.caller.phase.load());
            const bool known=callable && callable==scope.caller.selectedTask;
            ReleaseSRWLockShared(&scope.caller.lock);
            wchar_t leaf[64]{};swprintf_s(leaf,L"selected-task-entry-%u.json",index);char text[640]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-selected-task-entry-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"thread_id\":%lu,\"cpp_entered\":true,\"phase\":%u,\"known_task\":%s}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,index,GetCurrentThreadId(),phase,known?"true":"false");
            if(n>0)selected_diagnostic::output(c,leaf,text,n);
        }
    }
    SetLastError(before);
}
static void RecordTaskScope(const TaskBorrowEvidence& e,bool originalSelected) noexcept {
    const DWORD before=GetLastError();const unsigned index=taskScopeEvidenceIndex.fetch_add(1);
    if(index<8) {
        forward_diagnostic::Context c{};
        if(selected_diagnostic::valid_context(c)) {
            wchar_t leaf[64]{};swprintf_s(leaf,L"selected-task-scope-%u.json",index);
            char text[896]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-selected-task-scope-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"thread_id\":%lu,\"cpp_entered\":true,\"phase\":%u,\"borrow_reason\":%u,\"known_task\":%s,\"manager_copied\":%s,\"getter_called\":%s,\"original_selected_predicate\":%s,\"one_shot_frame_present\":%s,\"verified_scope_present\":%s}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,index,GetCurrentThreadId(),e.phase,e.reason,
                e.known?"true":"false",e.manager_copied?"true":"false",e.getter_called?"true":"false",originalSelected?"true":"false",
                taskFrame.callable?"true":"false",verifiedTaskFrame.held.callable?"true":"false");
            if(n>0)selected_diagnostic::output(c,leaf,text,n);
        }
    }
    SetLastError(before);
}
'''
    abi = replace_once(abi, signature, emitter + signature, ac)
    abi = replace_once(abi, '    BridgeCall call(ForwardRole::Task);VerifiedTaskScope verifiedScope;',
        '    BridgeCall call(ForwardRole::Task);VerifiedTaskScope verifiedScope;RecordTaskEntry(callable);', ac)
    abi = replace_once(abi,
        '    void* duplicateManager=nullptr;Pair duplicatePair=RetainVerifiedTaskSocket(callable,duplicateManager);',
        '    TaskBorrowEvidence borrowEvidence;\n'
        '    void* duplicateManager=nullptr;Pair duplicatePair=RetainVerifiedTaskSocket(callable,duplicateManager,RetainOriginalRole0,&borrowEvidence);', ac)
    abi = replace_once(abi, '    original(callable); // original getter/lock/connect/cleanup remain intact',
        '    RecordTaskScope(borrowEvidence,selected);\n'
        '    original(callable); // original getter/lock/connect/cleanup remain intact', ac)

    # Equivalent split prefix checks report the exact first failing group.
    old = '''    if(!peer || fresh.wrapper!=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge) ||
       fresh.reason!=BindReason::Bound || !scope.selectedReady.load())return false;
    const auto base=fresh.base;const auto& record=OwnForwardLayout::Records[0];
    if(!base || scope.base!=base || fresh.original!=base+record.original_rva ||
       frame.original_return!=base+0x26f8bd || frame.actual_leaf!=base+record.leaf_rva ||
       frame.native_original_target!=fresh.original || static_cast<uint16_t>(frame.r8)!=14030 ||
       !forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect))return false;'''
    new = '''    auto& evidence=freshDuplicateEvidence;evidence={};evidence.port=static_cast<uint16_t>(frame.r8);
    evidence.scope_present=verifiedTaskFrame.held.callable!=nullptr;
    if(!peer || fresh.wrapper!=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge) ||
       fresh.reason!=BindReason::Bound || !scope.selectedReady.load()){evidence.reason=1;return false;}
    const auto base=fresh.base;const auto& record=OwnForwardLayout::Records[0];
    if(!base || scope.base!=base){evidence.reason=2;return false;}
    if(fresh.original!=base+record.original_rva){evidence.reason=3;return false;}
    if(frame.original_return!=base+0x26f8bd){evidence.reason=4;return false;}
    if(frame.actual_leaf!=base+record.leaf_rva){evidence.reason=5;return false;}
    if(frame.native_original_target!=fresh.original){evidence.reason=6;return false;}
    if(static_cast<uint16_t>(frame.r8)!=14030){evidence.reason=7;return false;}
    if(!forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect)){evidence.reason=8;return false;}'''
    probe = replace_once(probe, old, new, pc)
    old = '''        const bool ok=scope.selectedReady.load() && scope.base==base &&
            verifiedTaskFrame.held.callable && verifiedTaskFrame.held.callable==scope.caller.selectedTask &&
            verifiedTaskFrame.manager && verifiedTaskFrame.manager==scope.caller.manager &&
            verifiedTaskFrame.held.socket.object==reinterpret_cast<void*>(frame.rcx) &&
            verifiedTaskFrame.held.socket.object==scope.caller.socket.object &&
            verifiedTaskFrame.held.socket.control && verifiedTaskFrame.held.socket.control==scope.caller.socket.control &&
            scope.caller.phase.load()==Phase::Connected && scope.caller.connectAttempted && !scope.caller.ownLimitRefused;'''
    new = '''        evidence.owner_bits=0;
        const bool ok=scope.selectedReady.load() && scope.base==base && (evidence.owner_bits|=1,true) &&
            verifiedTaskFrame.held.callable && verifiedTaskFrame.held.callable==scope.caller.selectedTask && (evidence.owner_bits|=2,true) &&
            verifiedTaskFrame.manager && verifiedTaskFrame.manager==scope.caller.manager && (evidence.owner_bits|=4,true) &&
            verifiedTaskFrame.held.socket.object==reinterpret_cast<void*>(frame.rcx) && (evidence.owner_bits|=8,true) &&
            verifiedTaskFrame.held.socket.object==scope.caller.socket.object && (evidence.owner_bits|=16,true) &&
            verifiedTaskFrame.held.socket.control && verifiedTaskFrame.held.socket.control==scope.caller.socket.control && (evidence.owner_bits|=32,true) &&
            scope.caller.phase.load()==Phase::Connected && (evidence.owner_bits|=64,true) &&
            scope.caller.connectAttempted && (evidence.owner_bits|=128,true) && !scope.caller.ownLimitRefused && (evidence.owner_bits|=256,true);'''
    probe = replace_once(probe, old, new, pc)
    probe = replace_once(probe,
        '    if(!sameOwner() || !peer(reinterpret_cast<void*>(frame.rcx)))return false;\n'
        '    return forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect) && sameOwner();',
        '''    if(!sameOwner()){evidence.reason=9;return false;}
    if(!peer(reinterpret_cast<void*>(frame.rcx))){evidence.reason=10;return false;}
    if(!forwardBinding.same_source_proof(base,fresh.original,ForwardRole::Connect)){evidence.reason=11;return false;}
    if(!sameOwner()){evidence.reason=12;return false;}
    evidence.reason=0;return true;''', pc)
    probe = replace_once(probe, '    if(record==0){boundCheckBits=0;probeFreshVerifiedDuplicate={};}',
        '    if(record==0){boundCheckBits=0;probeFreshVerifiedDuplicate={};freshDuplicateEvidence={};}', pc)
    probe = replace_once(probe, 'char text[960]{};', 'char text[1280]{};', pc)
    probe = replace_once(probe,
        r'\"fresh_verified_duplicate\":%s}\n',
        r'\"fresh_verified_duplicate\":%s,\"fresh_duplicate_reason\":%u,\"fresh_duplicate_owner_bits\":%u,\"fresh_duplicate_input_port\":%u,\"verified_task_scope_present\":%s}\n', pc)
    probe = replace_once(probe,
        'source_diagnostic::connect_role_revalidated?"true":"false",probeFreshVerifiedDuplicate.active?"true":"false");',
        'source_diagnostic::connect_role_revalidated?"true":"false",probeFreshVerifiedDuplicate.active?"true":"false",\n'
        '                freshDuplicateEvidence.reason,freshDuplicateEvidence.owner_bits,freshDuplicateEvidence.port,freshDuplicateEvidence.scope_present?"true":"false");', pc)
    task_probe = r'''static std::atomic<unsigned> taskProbeEvidenceIndex{0};
static void RecordTaskProbe(const BindingResult& result,uintptr_t target) noexcept {
    const DWORD before=GetLastError();const unsigned index=taskProbeEvidenceIndex.fetch_add(1);
    if(index<8) {
        forward_diagnostic::Context c{};
        if(selected_diagnostic::valid_context(c)) {
            wchar_t leaf[64]{};swprintf_s(leaf,L"selected-task-probe-%u.json",index);char text[768]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-selected-task-probe-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"thread_id\":%lu,\"record_id\":7,\"wrapper_selected\":%s,\"binding_reason\":%u,\"binding_stage\":%u,\"failed_record_id\":%d,\"source_check_step\":%u,\"current_original_verified\":%s}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,index,GetCurrentThreadId(),target?"true":"false",
                static_cast<unsigned>(result.reason),forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id,source_diagnostic::step,
                source_diagnostic::current_original_verified?"true":"false");
            if(n>0)selected_diagnostic::output(c,leaf,text,n);
        }
    }
    SetLastError(before);
}
'''
    signature = 'extern "C" uintptr_t OwnForwardProbe(const NativeProbeFrame* supplied,uint32_t record) noexcept {'
    probe = replace_once(probe, signature, task_probe + signature, pc)
    probe = replace_once(probe, '    if(record==0)RecordConnectProbe(frame,result,target);',
        '    if(record==7)RecordTaskProbe(result,target);\n    if(record==0)RecordConnectProbe(frame,result,target);', pc)
    return probe, abi, pc, ac
