// Included by the typed bridge translation unit; no independent framework.
extern "C" void OwnForwardConnectShim();extern "C" void OwnForwardConnectShimEnd();
extern "C" void OwnForwardSenderShim();extern "C" void OwnForwardSenderShimEnd();
extern "C" void OwnForwardSelectedShim();extern "C" void OwnForwardSelectedShimEnd();
extern "C" void OwnForwardInitShim();extern "C" void OwnForwardInitShimEnd();
extern "C" void OwnForwardConstructor0Shim();extern "C" void OwnForwardConstructor0ShimEnd();
extern "C" void OwnForwardConstructor1Shim();extern "C" void OwnForwardConstructor1ShimEnd();
extern "C" void OwnForwardConstructor2Shim();extern "C" void OwnForwardConstructor2ShimEnd();
extern "C" void OwnForwardTaskShim();extern "C" void OwnForwardTaskShimEnd();
extern "C" void OwnForwardCloseShim();extern "C" void OwnForwardCloseShimEnd();
// MASM frame: version1/flags0/prolog17/count5/FP RBP+F0; slots in reverse prolog order.
static constexpr unsigned char ShimUnwind[]={1,17,5,0xf5,17,0x53,9,1,29,0,2,2,1,0x50,0,0};
static std::atomic<unsigned> connectProbeIndex{0};
static std::atomic<unsigned> senderProbeIndex{0};
static thread_local uint32_t boundCheckBits=0;
static thread_local bool senderSourceOverride=false;
// Same owned-connected socket predicate as legacy BoundConnectedDuplicate,
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
static bool BoundConnectedDuplicate(const NativeProbeFrame& frame,const BindingResult& result) noexcept {
    boundCheckBits=0;
    if(result.reason!=BindReason::OriginalSourceMismatch)return false;
    boundCheckBits|=1;
    if(!scope.selectedReady.load())return false;
    boundCheckBits|=2;
    const uintptr_t base=forwardBinding.base.load();
    const auto& record=OwnForwardLayout::Records[0];
    if(!base)return false;
    boundCheckBits|=4;
    if(frame.original_return!=base+0x26f8bd)return false;
    boundCheckBits|=8;
    if(frame.actual_leaf!=base+record.leaf_rva)return false;
    boundCheckBits|=16;
    if(frame.native_original_target!=base+record.original_rva)return false;
    boundCheckBits|=32;
    if((frame.r8&0xffff)!=14000 && (frame.r8&0xffff)!=14030)return false;
    boundCheckBits|=1024;
    bool sameSocket=false,connected=false,attempted=false,limitClear=false,frameMatch=false;
    AcquireSRWLockShared(&scope.caller.lock);
    sameSocket=scope.caller.socket.object==reinterpret_cast<void*>(frame.rcx)
      && scope.caller.socket.control!=nullptr;
    connected=scope.caller.phase.load()==Phase::Connected;
    attempted=scope.caller.connectAttempted;
    limitClear=!scope.caller.ownLimitRefused;
    frameMatch=taskFrame.callable && taskFrame.callable==scope.caller.selectedTask
      && taskFrame.socket.object==scope.caller.socket.object
      && taskFrame.socket.control==scope.caller.socket.control;
    ReleaseSRWLockShared(&scope.caller.lock);
    if(sameSocket)boundCheckBits|=64;
    if(connected)boundCheckBits|=128;
    if(attempted)boundCheckBits|=256;
    if(limitClear)boundCheckBits|=512;
    if(frameMatch)boundCheckBits|=4096;
    if(!(sameSocket && connected && attempted && limitClear))return false;
    if(!ExactConnectedLocalPeer(reinterpret_cast<void*>(frame.rcx)))return false;
    boundCheckBits|=2048;
    AcquireSRWLockShared(&scope.caller.lock);
    const bool selected=scope.caller.socket.object==reinterpret_cast<void*>(frame.rcx)
      && scope.caller.socket.control!=nullptr && scope.caller.phase.load()==Phase::Connected
      && scope.caller.connectAttempted && !scope.caller.ownLimitRefused;
    ReleaseSRWLockShared(&scope.caller.lock);
    if(selected)boundCheckBits|=8192;
    return selected;
}
// The selected COUNTS direct edge can return after an earlier successful
// all-role binding even when the sender's original 32-byte source check now
// fails. The native fallback has already used this same original sender. Keep
// the original call in OwnLoginSenderBridge, and limit post-send own work to
// the previously bound selected network and connected local socket.
static bool BoundConnectedCountsSender(const NativeProbeFrame& frame,const BindingResult& result) noexcept {
    if(result.reason!=BindReason::OriginalSourceMismatch || !scope.selectedReady.load())return false;
    const uintptr_t base=forwardBinding.base.load(std::memory_order_acquire);
    const auto& record=OwnForwardLayout::Records[1];
    if(!base || scope.base!=base || frame.original_return!=base+0x2746ff ||
       frame.actual_leaf!=base+record.leaf_rva ||
       frame.native_original_target!=base+record.original_rva ||
       forwardBinding.target(ForwardRole::Sender)!=frame.native_original_target ||
       static_cast<uint16_t>(frame.rdx)!=0x4f3d ||
       !Executable(frame.native_original_target,1))return false;
    void* socket=nullptr;bool selected=false;
    AcquireSRWLockShared(&scope.caller.lock);
    selected=scope.caller.network.object==reinterpret_cast<void*>(frame.rcx) &&
      scope.caller.network.control && scope.caller.socket.object && scope.caller.socket.control &&
      scope.caller.selectedTask && scope.caller.phase.load()==Phase::Connected &&
      scope.caller.connectAttempted && !scope.caller.ownLimitRefused;
    if(selected)socket=scope.caller.socket.object;
    ReleaseSRWLockShared(&scope.caller.lock);
    if(!selected || !ExactConnectedLocalPeer(socket))return false;
    AcquireSRWLockShared(&scope.caller.lock);
    selected=scope.caller.network.object==reinterpret_cast<void*>(frame.rcx) &&
      scope.caller.network.control && scope.caller.socket.object==socket &&
      scope.caller.socket.control && scope.caller.selectedTask &&
      scope.caller.phase.load()==Phase::Connected && scope.caller.connectAttempted &&
      !scope.caller.ownLimitRefused;
    ReleaseSRWLockShared(&scope.caller.lock);
    return selected && forwardBinding.base.load(std::memory_order_acquire)==base;
}
static void RecordConnectProbe(const NativeProbeFrame& frame,const BindingResult& result,uintptr_t target) noexcept {
    const DWORD before=GetLastError();
    const unsigned phase=static_cast<unsigned>(scope.caller.phase.load());
    if(phase>=static_cast<unsigned>(Phase::Selected) && phase<=static_cast<unsigned>(Phase::Connected)) {
        const unsigned index=connectProbeIndex.fetch_add(1,std::memory_order_relaxed);
        forward_diagnostic::Context context{};
        if(index<8 && forward_diagnostic::context(context)) {
            const uintptr_t base=forwardBinding.base.load()?forwardBinding.base.load():result.base;
            const bool callerInImage=base && frame.original_return>=base
              && frame.original_return<base+OwnForwardLayout::ImageSize;
            const uintptr_t callerRva=callerInImage?frame.original_return-base:0;
            FILETIME now{};GetSystemTimeAsFileTime(&now);
            const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
            wchar_t leaf[40]{};swprintf_s(leaf,L"connect-probe-%u.json",index);
            char text[960]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-cp13-connect-probe-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"filetime\":%llu,\"thread_id\":%lu,\"phase\":%u,\"caller_in_image\":%s,\"caller_rva\":%llu,\"binding_reason\":%u,\"wrapper_selected\":%s,\"original_fallback\":%s,\"binding_stage\":%u,\"failed_record_id\":%d,\"bound_check_bits\":%u,\"source_check_step\":%u,\"source_check_passed\":%s,\"current_original_verified\":%s,\"prior_all_roles_verified\":%s,\"connect_role_revalidated\":%s,\"fresh_verified_duplicate\":%s}\n",
                context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,index,
                static_cast<unsigned long long>(filetime),GetCurrentThreadId(),phase,
                callerInImage?"true":"false",static_cast<unsigned long long>(callerRva),
                static_cast<unsigned>(result.reason),target?"true":"false",target?"false":"true",
                forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id,boundCheckBits,
                source_diagnostic::step,source_diagnostic::passed?"true":"false",
                source_diagnostic::current_original_verified?"true":"false",
                source_diagnostic::prior_all_roles_verified?"true":"false",
                source_diagnostic::connect_role_revalidated?"true":"false",probeFreshVerifiedSocket.active?"true":"false");
            if(n>0)selected_diagnostic::output(context,leaf,text,n);
        }
    }
    SetLastError(before);
}
static void RecordSenderProbe(const NativeProbeFrame& frame,const BindingResult& result,uintptr_t target,bool sourceOverride) noexcept {
    const DWORD before=GetLastError();
    const uintptr_t base=forwardBinding.base.load()?forwardBinding.base.load():result.base;
    const bool callerInImage=base && frame.original_return>=base
      && frame.original_return<base+OwnForwardLayout::ImageSize;
    const uintptr_t callerRva=callerInImage?frame.original_return-base:0;
    const uint16_t opcode=static_cast<uint16_t>(frame.rdx);
    if(callerRva==0x2746ff && opcode==0x4f3d) {
        const unsigned index=senderProbeIndex.fetch_add(1,std::memory_order_relaxed);
        forward_diagnostic::Context context{};
        if(index<8 && forward_diagnostic::context(context)) {
            unsigned phase=0;bool networkMatch=false;
            AcquireSRWLockShared(&scope.caller.lock);
            phase=static_cast<unsigned>(scope.caller.phase.load());
            networkMatch=scope.caller.network.object==reinterpret_cast<void*>(frame.rcx);
            ReleaseSRWLockShared(&scope.caller.lock);
            FILETIME now{};GetSystemTimeAsFileTime(&now);
            const uint64_t filetime=(uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime;
            wchar_t leaf[40]{};swprintf_s(leaf,L"sender-probe-%u.json",index);
            char text[800]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-cp15-sender-probe-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"index\":%u,\"filetime\":%llu,\"thread_id\":%lu,\"phase\":%u,\"caller_rva\":%llu,\"opcode\":%u,\"binding_reason\":%u,\"wrapper_selected\":%s,\"original_fallback\":%s,\"selected_ready\":%s,\"network_matches_selected\":%s,\"source_mismatch_override\":%s,\"source_check_step\":%u,\"source_check_passed\":%s}\n",
                context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,index,
                static_cast<unsigned long long>(filetime),GetCurrentThreadId(),phase,
                static_cast<unsigned long long>(callerRva),opcode,static_cast<unsigned>(result.reason),
                target?"true":"false",target?"false":"true",scope.selectedReady.load()?"true":"false",
                networkMatch?"true":"false",sourceOverride?"true":"false",
                source_diagnostic::step,source_diagnostic::passed?"true":"false");
            if(n>0)selected_diagnostic::output(context,leaf,text,n);
        }
    }
    SetLastError(before);
}
// Separate claims retain the current Selected refusal even after a constructor failure.
static std::atomic<bool> sourceFirstClaim{false},sourceSelectedClaim{false};
static void RecordSourceCheckFailure(uint32_t record,BindReason reason,uint32_t stage,int failed) noexcept {
    if(reason!=BindReason::OriginalSourceMismatch || (stage!=1 && stage!=2))return;
    const auto q=source_diagnostic::query;const unsigned step=source_diagnostic::step;
    const DWORD before=GetLastError();forward_diagnostic::Context c{};
    if(selected_diagnostic::valid_context(c)) {
        bool expected=false;const bool first=sourceFirstClaim.compare_exchange_strong(expected,true);
        expected=false;const bool selected=record==2 && sourceSelectedClaim.compare_exchange_strong(expected,true);
        if(first || selected) {
            FILETIME now{};GetSystemTimeAsFileTime(&now);
            const auto time=(static_cast<uint64_t>(now.dwHighDateTime)<<32)|now.dwLowDateTime;
            char returned[32]="null",error[32]="null",state[32]="null",protect[32]="null",type[32]="null",region[32]="null";
            if(q.observed)sprintf_s(returned,"%llu",static_cast<unsigned long long>(q.returned));
            if(q.observed && !q.returned)sprintf_s(error,"%lu",q.error);
            if(q.region_observed){sprintf_s(state,"%lu",q.state);sprintf_s(protect,"%lu",q.protect);sprintf_s(type,"%lu",q.type);sprintf_s(region,"%llu",static_cast<unsigned long long>(q.region_size));}
            char text[1536]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-source-check-query-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"filetime\":%llu,\"thread_id\":%lu,\"record_id\":%u,\"binding_reason\":%u,\"binding_stage\":%u,\"failed_record_id\":%d,\"source_check_step\":%u,\"source_check_passed\":false,\"query_observed\":%s,\"failure_category\":%u,\"query_returned_size\":%s,\"query_failure_error\":%s,\"memory_state\":%s,\"memory_protect\":%s,\"memory_type\":%s,\"span_bytes\":%llu,\"region_bytes\":%s,\"range_checked\":%s,\"span_in_region\":%s}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,static_cast<unsigned long long>(time),GetCurrentThreadId(),
                record,static_cast<unsigned>(reason),stage,failed,step,q.observed?"true":"false",q.category,returned,error,state,protect,type,
                static_cast<unsigned long long>(q.span),region,q.range_checked?"true":"false",q.range_checked?(q.span_in_region?"true":"false"):"null");
            if(n>0){if(first)selected_diagnostic::output(c,L"source-check-first-failure.json",text,n);
                if(selected)selected_diagnostic::output(c,L"selected-source-check-failure.json",text,n);}
        }
    }
    SetLastError(before);
}
static std::atomic<unsigned> sourceRetryClaims{0};
static void RecordSourceRetry(uint32_t record,const BindingResult& result,const source_diagnostic::RetryBudget& retry) noexcept {
    if(record>=9 || (!retry.attempted_read && record!=2))return;
    const DWORD before=GetLastError();forward_diagnostic::Context c{};
    if(selected_diagnostic::valid_context(c)) {
        const unsigned bit=1u<<record;
        if(!(sourceRetryClaims.fetch_or(bit)&bit)) {
            wchar_t leaf[64]{};swprintf_s(leaf,L"source-read-retry-record-%u.json",record);
            char text[896]{};
            const int n=sprintf_s(text,"{\"schema\":\"own-source-read-retry-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"record_id\":%u,\"retry_attempted\":%s,\"retry_full_verified\":%s,\"attempted_spans\":%u,\"verified_spans\":%u,\"guard_wrapper_selected\":%s,\"binding_reason\":%u,\"binding_stage\":%u,\"failed_record_id\":%d,\"source_check_step\":%u}\n",
                c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,record,
                retry.attempted_read?"true":"false",retry.full_verified?"true":"false",retry.attempted,retry.verified,result.wrapper?"true":"false",
                static_cast<unsigned>(result.reason),forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id,source_diagnostic::step);
            if(n>0)selected_diagnostic::output(c,leaf,text,n);
        }
    }
    SetLastError(before);
}
extern "C" uintptr_t OwnForwardProbe(const NativeProbeFrame* supplied,uint32_t record) noexcept {
    const DWORD before=GetLastError();uintptr_t target=0;
    if(record==0){boundCheckBits=0;probeFreshVerifiedSocket={};}
    if(record==1)senderSourceOverride=false;
    NativeProbeFrame frame{};BindingResult result,currentVerified;
    forward_diagnostic::binding_stage=0;forward_diagnostic::failed_record_id=-1;
    source_diagnostic::step=0;source_diagnostic::passed=false;
    source_diagnostic::current_original_verified=false;source_diagnostic::prior_all_roles_verified=false;
    source_diagnostic::connect_role_revalidated=false;
    source_diagnostic::current_prefix_verified=false;
    source_diagnostic::RetryBudget retryBudget{};
    try {
        const uintptr_t wrappers[]={reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge),reinterpret_cast<uintptr_t>(&OwnLoginSenderBridge),
            reinterpret_cast<uintptr_t>(&OwnLoginSelectedBridge),reinterpret_cast<uintptr_t>(&OwnLoginInitBridge),reinterpret_cast<uintptr_t>(&OwnLoginConstructorBridge),
            reinterpret_cast<uintptr_t>(&OwnLoginSelectedTaskBridge),reinterpret_cast<uintptr_t>(&OwnLoginCloseBridge),reinterpret_cast<uintptr_t>(&OwnKeyTaskBridge),reinterpret_cast<uintptr_t>(&OwnKeyVersionBridge)};
        const uintptr_t shims[]={reinterpret_cast<uintptr_t>(&OwnForwardConnectShim),reinterpret_cast<uintptr_t>(&OwnForwardSenderShim),reinterpret_cast<uintptr_t>(&OwnForwardSelectedShim),
            reinterpret_cast<uintptr_t>(&OwnForwardInitShim),reinterpret_cast<uintptr_t>(&OwnForwardConstructor0Shim),reinterpret_cast<uintptr_t>(&OwnForwardConstructor1Shim),
            reinterpret_cast<uintptr_t>(&OwnForwardConstructor2Shim),reinterpret_cast<uintptr_t>(&OwnForwardTaskShim),reinterpret_cast<uintptr_t>(&OwnForwardCloseShim),reinterpret_cast<uintptr_t>(&OwnForwardKeyTaskShim),reinterpret_cast<uintptr_t>(&OwnForwardKeyVersionShim)};
        const uintptr_t ends[]={reinterpret_cast<uintptr_t>(&OwnForwardConnectShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardSenderShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardSelectedShimEnd),
            reinterpret_cast<uintptr_t>(&OwnForwardInitShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardConstructor0ShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardConstructor1ShimEnd),
            reinterpret_cast<uintptr_t>(&OwnForwardConstructor2ShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardTaskShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardCloseShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardKeyTaskShimEnd),reinterpret_cast<uintptr_t>(&OwnForwardKeyVersionShimEnd)};
        const ForwardLayoutView layout{OwnForwardLayout::Records,9,OwnForwardLayout::Direct,7,OwnForwardLayout::ImageSize,ShimUnwind,sizeof(ShimUnwind)};
        const BindingApi api{SafeCopy,Executable,Lookup,wrappers,shims,ends};
        if(record>=9) {
            // Old9 view/all9 checks/first globals remain unchanged for old edges.
            const ForwardLayoutView extra{OwnForwardLayout::Records,11,OwnForwardLayout::Direct,8,OwnForwardLayout::ImageSize,ShimUnwind,sizeof(ShimUnwind)};
            if(record<11 && supplied && SafeCopy(&frame,supplied,sizeof(frame))) {
                result=VerifyOriginal(frame,record,extra,api);
                if(result.wrapper)result=forwardBinding.publish(result,extra.records[record].role);
                target=result.wrapper;
            }
            SetLastError(before);return target;
        }
        ForwardRole role=ForwardRole::Count;
        if(record<9)role=layout.records[record].role;
        forward_diagnostic::once(forward_diagnostic::entry,L"first-bridge.json","FIRST_BRIDGE",role,record,BindReason::FrameUnreadable,false,false,"OWN_NOT_READY");
        if(supplied && SafeCopy(&frame,supplied,sizeof(frame)))result=VerifyOriginal(frame,record,layout,api);
        if(record<9 && !result.wrapper && result.reason==BindReason::OriginalSourceMismatch &&
           source_diagnostic::current_prefix_verified && source_diagnostic::step==1) {
            const auto q=source_diagnostic::query;
            result=forwardBinding.retry_current_source(result,layout.records[record],layout.image_size,
                    q,retryBudget,api.copy,[&]() noexcept {return VerifyOriginal(frame,record,layout,api);});
        }
        currentVerified=result;source_diagnostic::current_original_verified=result.wrapper!=0;
        const auto priorAll=forwardBinding.all_roles_verified_base.load(std::memory_order_acquire);
        source_diagnostic::prior_all_roles_verified=priorAll && priorAll==forwardBinding.base.load(std::memory_order_acquire);
        if(!result.wrapper){forward_diagnostic::binding_stage=1;forward_diagnostic::failed_record_id=static_cast<int>(record);
            RecordSourceCheckFailure(record,result.reason,1,static_cast<int>(record));}
        if(result.wrapper) {
            // All seven exact original spans are independent of own DTO/inputs.
            // Failure changes only shim activation: native original edge still runs.
            std::array<uintptr_t,7> original{};
            for(std::size_t i=0;i<9;++i) {
                const auto& r=layout.records[i];const auto index=static_cast<unsigned>(r.role);
                const uintptr_t p=result.base+r.original_rva;unsigned char code[32]{};
                source_diagnostic::step=0;source_diagnostic::passed=false;source_diagnostic::query={};
                auto verifySource=[&]() noexcept {
                    return r.anchor_size && r.anchor_size<=32 &&
                        (source_diagnostic::step=1,Executable(p,r.anchor_size)) &&
                        (source_diagnostic::step=2,SafeCopy(code,reinterpret_cast<void*>(p),r.anchor_size)) &&
                        (source_diagnostic::step=3,!memcmp(code,r.anchor,r.anchor_size));
                };
                bool sourceOk=verifySource();
                if(!sourceOk && source_diagnostic::step==1) {
                    const auto q=source_diagnostic::query;
                    sourceOk=forwardBinding.retry_source_read(result.base,p,r,layout.image_size,q,
                        retryBudget,api.copy,verifySource);
                }
                if(!sourceOk) {
                    result.wrapper=0;result.reason=BindReason::OriginalSourceMismatch;forward_diagnostic::binding_stage=2;forward_diagnostic::failed_record_id=static_cast<int>(i);
                    RecordSourceCheckFailure(record,result.reason,2,static_cast<int>(i));break;
                }
                source_diagnostic::passed=true;
                original[index]=p;
            }
            if(result.wrapper) {
                AcquireSRWLockExclusive(&forwardBinding.lock);const auto previous=forwardBinding.base.load();
                if(previous && previous!=result.base){result.wrapper=0;result.reason=BindReason::GenerationConflict;forward_diagnostic::binding_stage=3;forward_diagnostic::failed_record_id=-1;}
                else {for(unsigned i=0;i<7;++i)forwardBinding.originals[i].store(original[i],std::memory_order_release);forwardBinding.base.store(result.base,std::memory_order_release);
                    forwardBinding.all_roles_verified_base.store(result.base,std::memory_order_release);}
                ReleaseSRWLockExclusive(&forwardBinding.lock);
            }
        }
        // Only a fresh valid current Connect can survive another role's all9 refusal.
        // Use the already published identical Connect; publish no new callable here.
        if(forwardBinding.allow_current_connect(currentVerified,result,record,
                forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id)) {
            result.wrapper=currentVerified.wrapper;source_diagnostic::connect_role_revalidated=true;
            source_diagnostic::prior_all_roles_verified=true;
        }
        if(result.wrapper) {
            probeRecord=record;target=result.wrapper;
            forward_diagnostic::once(forward_diagnostic::success,L"binding-success.json","BINDING_SUCCESS",role,record,BindReason::Bound,false,false,"OWN_NOT_READY");
        }else {selected_diagnostic::probe_refused(record,result.reason,forward_diagnostic::binding_stage,forward_diagnostic::failed_record_id);forward_diagnostic::once(forward_diagnostic::failure,L"binding-first-failure.json","BINDING_FIRST_FAILURE",role,record,result.reason,false,false,"NATIVE_ORIGINAL_EDGE_ONLY");}
    }catch(...){target=0;result.reason=BindReason::FrameUnreadable;selected_diagnostic::probe_refused(record,BindReason::FrameUnreadable,forward_diagnostic::binding_stage,-1);}
    void* duplicateControl=nullptr;
    if(record==0 && target && BoundVerifiedSocketDuplicate(frame,currentVerified,duplicateControl))
        probeFreshVerifiedSocket={true,frame,currentVerified,duplicateControl};
    RecordSourceRetry(record,result,retryBudget);
    if(record==0 && !target && BoundConnectedDuplicate(frame,result)) {
        probeDuplicateBypass=true;
        target=reinterpret_cast<uintptr_t>(&OwnLoginConnectBridge);
    }
    if(record==1 && !target && BoundConnectedCountsSender(frame,result)) {
        senderSourceOverride=true;
        target=reinterpret_cast<uintptr_t>(&OwnLoginSenderBridge);
    }
    if(record==0)RecordConnectProbe(frame,result,target);
    if(record==1)RecordSenderProbe(frame,result,target,senderSourceOverride);
    SetLastError(before);return target;
}
