"""Explicit, fail-closed source-read retry overlay over memory-query diagnostics."""


def overlay(binding, probe, replace_once):
    bc, pc = [], []
    binding = replace_once(binding,
        '// 9=protection excluded, 10=pass. No address or original bytes are retained.',
        '// 9=protection excluded, 10=pass. Private TLS query coordinates are never output.', bc)
    binding = replace_once(binding,
        'DWORD error=0,state=0,protect=0,type=0;};',
        'DWORD error=0,state=0,protect=0,type=0;uintptr_t region_start=0,allocation_base=0;};', bc)
    binding = replace_once(binding, 'inline thread_local Query query{};', '''inline thread_local Query query{};
inline thread_local bool current_prefix_verified=false;
struct RetryBudget {
    std::array<uintptr_t,9> spans{};unsigned attempted=0,verified=0;
    bool attempted_read=false,full_verified=false;
};
struct RetryAttempt {bool read_returned=false;};''', bc)
    binding = replace_once(binding,
        'q.region_observed=true;q.state=m.State;q.protect=m.Protect;q.type=m.Type;q.region_size=m.RegionSize;',
        'q.region_observed=true;q.state=m.State;q.protect=m.Protect;q.type=m.Type;q.region_size=m.RegionSize;\n'
        '    q.region_start=reinterpret_cast<uintptr_t>(m.BaseAddress);q.allocation_base=reinterpret_cast<uintptr_t>(m.AllocationBase);', bc)
    binding = replace_once(binding, '    BindingResult out;\n',
        '    BindingResult out;source_diagnostic::current_prefix_verified=false;\n', bc)
    binding = replace_once(binding, '    unsigned char original[32]{};\n',
        '    // Metadata only: wrapper remains zero until complete fresh verification.\n'
        '    out.base=base;out.original=f.native_original_target;source_diagnostic::current_prefix_verified=true;\n'
        '    unsigned char original[32]{};\n', bc)
    anchor = '    uintptr_t target(ForwardRole role) const noexcept'
    methods = '''    bool same_source_proof(uintptr_t image,uintptr_t original,ForwardRole role) noexcept {
        if(!image || !original || static_cast<unsigned>(role)>=7)return false;
        AcquireSRWLockShared(&lock);
        const bool ok=all_roles_verified_base.load(std::memory_order_acquire)==image &&
            base.load(std::memory_order_acquire)==image &&
            originals[static_cast<unsigned>(role)].load(std::memory_order_acquire)==original;
        ReleaseSRWLockShared(&lock);return ok;
    }
    template<class Verify> bool retry_source_read(uintptr_t image,uintptr_t original,const ForwardRecord& record,
            uint32_t image_size,const source_diagnostic::Query& q,source_diagnostic::RetryBudget& budget,
            CopyFn copy,Verify verify,source_diagnostic::RetryAttempt* observed=nullptr) noexcept {
        // A previous proof authorizes one bounded read, never an unverified call.
        const auto n=record.anchor_size;
        if(!copy || !n || n>32 || !image || image>UINTPTR_MAX-image_size ||
           n>image_size || record.original_rva>image_size-n ||
           original!=image+record.original_rva || !q.observed || !q.region_observed ||
           q.returned!=sizeof(MEMORY_BASIC_INFORMATION) || q.span!=n || q.category!=6 ||
           q.state!=MEM_COMMIT || q.type!=MEM_IMAGE || q.protect!=PAGE_NOACCESS ||
           q.allocation_base!=image || q.region_start>original ||
           q.region_start>UINTPTR_MAX-q.region_size || original>UINTPTR_MAX-n ||
           original+n>q.region_start+q.region_size || !same_source_proof(image,original,record.role))return false;
        for(unsigned i=0;i<budget.attempted;++i)if(budget.spans[i]==original)return false;
        if(budget.attempted>=budget.spans.size())return false;
        budget.spans[budget.attempted++]=original;budget.attempted_read=true;
        const DWORD before=GetLastError();unsigned char scratch[32]{};
        const bool read=copy(scratch,reinterpret_cast<void*>(original),n);
        if(observed)observed->read_returned=read;
        // Keep the complete copied span observable to the optimizer, privately.
        volatile unsigned char consumed=0;
        if(read)for(unsigned i=0;i<n;++i)consumed=static_cast<unsigned char>(consumed^scratch[i]);
        (void)consumed;
        const bool full=read && same_source_proof(image,original,record.role) && verify() &&
            same_source_proof(image,original,record.role);
        if(full)++budget.verified;
        budget.full_verified=budget.verified==budget.attempted;
        SetLastError(before);return full;
    }
    template<class Verify> BindingResult retry_current_source(BindingResult initial,const ForwardRecord& record,
            uint32_t image_size,const source_diagnostic::Query& q,source_diagnostic::RetryBudget& budget,
            CopyFn copy,Verify verify) noexcept {
        if(initial.wrapper || initial.reason!=BindReason::OriginalSourceMismatch)return initial;
        BindingResult latest;bool called=false;source_diagnostic::RetryAttempt attempt;
        const bool recovered=retry_source_read(initial.base,initial.original,record,image_size,q,budget,copy,
            [&]() noexcept {called=true;latest=verify();return latest.wrapper!=0;},&attempt);
        if(called){
            if(latest.wrapper && !recovered){latest.wrapper=0;latest.reason=BindReason::GenerationConflict;}
            return latest;
        }
        if(attempt.read_returned){initial.wrapper=0;initial.reason=BindReason::GenerationConflict;}
        return initial;
    }
'''
    binding = replace_once(binding, anchor, methods + anchor, bc)
    reset = '    source_diagnostic::connect_role_revalidated=false;'
    probe = replace_once(probe, reset,
        reset + '\n    source_diagnostic::current_prefix_verified=false;\n'
        '    source_diagnostic::RetryBudget retryBudget{};', pc)
    old = '        currentVerified=result;source_diagnostic::current_original_verified=result.wrapper!=0;'
    new = '''        if(record<9 && !result.wrapper && result.reason==BindReason::OriginalSourceMismatch &&
           source_diagnostic::current_prefix_verified && source_diagnostic::step==1) {
            const auto q=source_diagnostic::query;
            result=forwardBinding.retry_current_source(result,layout.records[record],layout.image_size,
                    q,retryBudget,api.copy,[&]() noexcept {return VerifyOriginal(frame,record,layout,api);});
        }
        currentVerified=result;source_diagnostic::current_original_verified=result.wrapper!=0;'''
    probe = replace_once(probe, old, new, pc)
    old = '''                if(!r.anchor_size || r.anchor_size>32 ||
                   (source_diagnostic::step=1,!Executable(p,r.anchor_size)) ||
                   (source_diagnostic::step=2,!SafeCopy(code,reinterpret_cast<void*>(p),r.anchor_size)) ||
                   (source_diagnostic::step=3,memcmp(code,r.anchor,r.anchor_size))) {'''
    new = '''                auto verifySource=[&]() noexcept {
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
                if(!sourceOk) {'''
    probe = replace_once(probe, old, new, pc)
    helper = r'''static std::atomic<unsigned> sourceRetryClaims{0};
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
'''
    signature = 'extern "C" uintptr_t OwnForwardProbe(const NativeProbeFrame* supplied,uint32_t record) noexcept {'
    probe = replace_once(probe, signature, helper + signature, pc)
    anchor = '    if(record==0 && !target && BoundConnectedDuplicate(frame,result)) {'
    probe = replace_once(probe, anchor, '    RecordSourceRetry(record,result,retryBudget);\n' + anchor, pc)
    return binding, probe, bc, pc


def write_fixture(out, relative, write_new):
    source = r'''#include "OUTPUT/binding.hpp"
#include <cstdio>
static unsigned reads=0,verifies=0;static bool readOk=true,verifyOk=true;
static OriginalForwardBinding* mutate=nullptr;
static bool Read(void* to,const void*,std::size_t n) noexcept {
    ++reads;if(mutate)mutate->base=0x300000;if(!readOk)return false;
    memset(to,0,n);return true;
}
int main() {
    OriginalForwardBinding b;ForwardRecord r{};r.role=ForwardRole::Selected;r.original_rva=0x4000;r.anchor_size=32;
    source_diagnostic::Query q;q.observed=true;q.region_observed=true;q.returned=sizeof(MEMORY_BASIC_INFORMATION);
    q.span=32;q.category=6;q.state=MEM_COMMIT;q.type=MEM_IMAGE;q.protect=PAGE_NOACCESS;
    q.allocation_base=0x100000;q.region_start=0x104000;q.region_size=0x1000;
    const auto initial=q;
    auto reset=[&]() {b.base=0x100000;b.all_roles_verified_base=0x100000;b.originals[2]=0x104000;
        q=initial;reads=verifies=0;readOk=verifyOk=true;mutate=nullptr;};
    auto run=[&](source_diagnostic::RetryBudget& budget) {
        return b.retry_source_read(0x100000,0x104000,r,0x10000,q,budget,Read,[&]() noexcept {++verifies;return verifyOk;});
    };
    unsigned checks=0;
    reset();source_diagnostic::RetryBudget success;
    if(!run(success)||reads!=1||verifies!=1||!success.full_verified)return 1;++checks;
    if(run(success)||reads!=1)return 2;++checks; // same original span once
    for(unsigned which=0;which<13;++which) {
        reset();source_diagnostic::RetryBudget denied;
        switch(which){case 0:b.all_roles_verified_base=0;break;case 1:b.base=0x200000;break;
        case 2:b.originals[2]=0x104001;break;case 3:q.allocation_base=0x200000;break;
        case 4:q.protect=PAGE_NOACCESS|PAGE_GUARD;break;case 5:q.returned=1;break;
        case 6:q.region_size=16;break;case 7:q.region_start=UINTPTR_MAX-15;q.region_size=32;break;
        case 8:q.state=MEM_RESERVE;break;case 9:q.type=MEM_PRIVATE;break;
        case 10:q.span=31;break;case 11:q.category=9;break;case 12:q.region_start=0x104001;break;}
        if(run(denied)||reads||verifies||denied.attempted)return 10+static_cast<int>(which);++checks;
    }
    reset();source_diagnostic::RetryBudget fault;readOk=false;
    if(run(fault)||reads!=1||verifies||fault.full_verified)return 30;++checks;
    reset();source_diagnostic::RetryBudget mismatch;verifyOk=false;
    if(run(mismatch)||reads!=1||verifies!=1||mismatch.full_verified)return 31;++checks;
    reset();source_diagnostic::RetryBudget changedDuringRead;mutate=&b;
    if(run(changedDuringRead)||reads!=1||verifies||changedDuringRead.full_verified)return 32;++checks;
    reset();source_diagnostic::RetryBudget changedDuringVerify;
    const bool changed=b.retry_source_read(0x100000,0x104000,r,0x10000,q,changedDuringVerify,Read,[&]() noexcept {b.base=0x200000;return true;});
    if(changed||changedDuringVerify.full_verified)return 33;++checks;
    reset();source_diagnostic::RetryBudget stillNoAccess;
    const bool notExecutable=b.retry_source_read(0x100000,0x104000,r,0x10000,q,stillNoAccess,Read,[]() noexcept {return false;});
    if(notExecutable||stillNoAccess.full_verified)return 34;++checks;
    // Constructor records4/5/6 share role4 and one original target: budget by span.
    reset();r.role=ForwardRole::Constructor;b.originals[4]=0x104000;source_diagnostic::RetryBudget aliases;
    if(!run(aliases)||run(aliases)||run(aliases)||reads!=1)return 35;++checks;
    reset();r.role=ForwardRole::Selected;source_diagnostic::RetryBudget prefixFailure;
    BindingResult failed;failed.base=0x100000;failed.original=0x104000;failed.reason=BindReason::OriginalSourceMismatch;
    const auto latest=b.retry_current_source(failed,r,0x10000,q,prefixFailure,Read,[]() noexcept {
        BindingResult f;f.reason=BindReason::IatMismatch;return f;
    });
    if(latest.wrapper||latest.reason!=BindReason::IatMismatch)return 36;++checks;
    reset();source_diagnostic::RetryBudget postConflict;
    const auto conflict=b.retry_current_source(failed,r,0x10000,q,postConflict,Read,[&]() noexcept {
        BindingResult f;f.wrapper=0x900000;f.reason=BindReason::Bound;b.base=0x200000;return f;
    });
    if(conflict.wrapper||conflict.reason!=BindReason::GenerationConflict)return 37;++checks;
    reset();source_diagnostic::RetryBudget outer;
    const bool nested=b.retry_source_read(0x100000,0x104000,r,0x10000,q,outer,Read,[&]() noexcept {
        source_diagnostic::RetryBudget inner;
        if(!run(inner)||inner.attempted!=1)return false;
        return outer.attempted==1;
    });
    if(!nested||outer.attempted!=1||outer.verified!=1||reads!=2||run(outer))return 38;++checks;
    std::printf("{\"status\":\"PASS\",\"checks\":%u,\"game_access\":false}\n",checks);return 0;
}
'''.replace('OUTPUT', relative)
    write_new(out / 'source_retry_mock.cpp', source)
    recipe = '''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /utf-8 /W4 /WX /EHsc /O2 /MD /I. /Itools\\local_native_login_state5_ack_bridge /Fe:OUTPUT\\source_retry_mock.exe /Fo:OUTPUT\\source_retry_mock.obj OUTPUT\\source_retry_mock.cpp
exit /b %errorlevel%
'''.replace('OUTPUT', relative.replace('/', '\\'))
    write_new(out / 'build-source-retry-fixture.cmd', recipe)
