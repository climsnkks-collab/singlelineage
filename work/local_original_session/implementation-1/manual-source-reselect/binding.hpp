#pragma once
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <intrin.h>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include "probe_abi.hpp"
struct ForwardRecord {
    ForwardRole role;
    uint32_t original_rva,leaf_rva,leaf_end,shim_iat_rva;
    uint32_t table_rva,slot_offset;
    uint8_t anchor_size;unsigned char anchor[32];
};
struct DirectSite { uint32_t call_rva,return_rva,record_id; };
struct ForwardLayoutView {
    const ForwardRecord* records;std::size_t record_count;const DirectSite* direct;std::size_t direct_count;
    uint32_t image_size;const unsigned char* unwind_bytes;std::size_t unwind_size;
};
// Diagnostic step: 0=not checked/invalid anchor, 1=Executable, 2=SafeCopy, 3=memcmp.
// passed is true only after all three existing checks completed successfully.
namespace source_diagnostic {inline thread_local unsigned step=0;inline thread_local bool passed=false;
inline thread_local bool current_original_verified=false,prior_all_roles_verified=false,connect_role_revalidated=false;
// Failure: 0=not observed, 1=empty span, 2=span overflow, 3=query failed,
// 4=not committed, 5=guard, 6=noaccess, 7=region overflow, 8=outside region,
// 9=protection excluded, 10=pass. Private TLS query coordinates are never output.
struct Query {bool observed=false,region_observed=false,range_checked=false,span_in_region=false;
    unsigned category=0;SIZE_T returned=0,span=0,region_size=0;DWORD error=0,state=0,protect=0,type=0;uintptr_t region_start=0,allocation_base=0;};
inline thread_local Query query{};
inline thread_local bool current_prefix_verified=false;
struct RetryBudget {
    std::array<uintptr_t,9> spans{};unsigned attempted=0,verified=0;
    bool attempted_read=false,full_verified=false;
};
struct RetryAttempt {bool read_returned=false;};
}
enum class BindReason:uint32_t { Bound=0,FrameUnreadable,RoleUnknown,OriginUnknown,VptrUnreadable,
    MappingMismatch,CallerMismatch,LeafMismatch,IatMismatch,OriginalSourceMismatch,UnwindMissing,UnwindMismatch,GenerationConflict };
struct BindingResult {uintptr_t wrapper=0,base=0,original=0;BindReason reason=BindReason::FrameUnreadable;};
using CopyFn=bool(*)(void*,const void*,std::size_t) noexcept;
using CodeFn=bool(*)(uintptr_t,std::size_t) noexcept;
using UnwindFn=bool(*)(uintptr_t,uintptr_t&,RUNTIME_FUNCTION&) noexcept;
struct BindingApi {CopyFn copy;CodeFn code;UnwindFn unwind;const uintptr_t* wrappers;const uintptr_t* shims;const uintptr_t* shim_ends;};
// Current-clone self-verification only. No host RPM/OpenProcess, SDK range or
// scan. AV is caught at the narrow copy and lookup boundaries, not /EHsc alone.
inline bool SafeCopy(void* out,const void* source,std::size_t n) noexcept {
    __try {memcpy(out,source,n);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline bool Executable(uintptr_t p,std::size_t n) noexcept {
    auto& q=source_diagnostic::query;q={};q.span=n;
    MEMORY_BASIC_INFORMATION m{};
    if(!n){q.category=1;return false;}
    if(p>UINTPTR_MAX-n){q.category=2;return false;}
    q.observed=true;q.returned=VirtualQuery(reinterpret_cast<void*>(p),&m,sizeof(m));
    if(!q.returned){q.error=GetLastError();q.category=3;return false;}
    q.region_observed=true;q.state=m.State;q.protect=m.Protect;q.type=m.Type;q.region_size=m.RegionSize;
    q.region_start=reinterpret_cast<uintptr_t>(m.BaseAddress);q.allocation_base=reinterpret_cast<uintptr_t>(m.AllocationBase);
    if(m.State!=MEM_COMMIT){q.category=4;return false;}
    if(m.Protect&(PAGE_GUARD|PAGE_NOACCESS)){q.category=(m.Protect&PAGE_GUARD)?5u:6u;return false;}
    const auto start=reinterpret_cast<uintptr_t>(m.BaseAddress);
    q.range_checked=true;
    if(start>UINTPTR_MAX-m.RegionSize){q.category=7;return false;}
    if(p+n>start+m.RegionSize){q.category=8;return false;}
    q.span_in_region=true;
    const DWORD protection=m.Protect&0xff;
    const bool result=protection==PAGE_EXECUTE_READ || protection==PAGE_EXECUTE_READWRITE || protection==PAGE_EXECUTE_WRITECOPY;
    q.category=result?10u:9u;return result;
}
inline bool Lookup(uintptr_t pc,uintptr_t& base,RUNTIME_FUNCTION& value) noexcept {
    __try {DWORD64 image=0;const auto entry=RtlLookupFunctionEntry(pc,&image,nullptr);
        if(!entry)return false;value=*entry;base=static_cast<uintptr_t>(image);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline BindingResult VerifyOriginal(const NativeProbeFrame& f,uint32_t record_id,const ForwardLayoutView& layout,const BindingApi& api) noexcept {
    BindingResult out;source_diagnostic::current_prefix_verified=false;
    if(record_id>=layout.record_count){out.reason=BindReason::RoleUnknown;return out;}
    const auto& r=layout.records[record_id];const auto role=r.role;const auto index=static_cast<uint32_t>(role);uintptr_t base=0;
    if(index>=static_cast<uint32_t>(ForwardRole::Count)){out.reason=BindReason::RoleUnknown;return out;}
    if(role==ForwardRole::Task || role==ForwardRole::Close || role==ForwardRole::KeyTask) {
        uintptr_t vptr=0;
        if(!f.rcx || !api.copy(&vptr,reinterpret_cast<void*>(f.rcx),sizeof(vptr))){out.reason=BindReason::VptrUnreadable;return out;}
        if(!r.table_rva || vptr<r.table_rva){out.reason=BindReason::OriginUnknown;return out;}
        base=vptr-r.table_rva;uintptr_t slot=0;
        if(vptr>UINTPTR_MAX-r.slot_offset || !api.copy(&slot,reinterpret_cast<void*>(vptr+r.slot_offset),8) || slot!=f.actual_leaf) {out.reason=BindReason::LeafMismatch;return out;}
    }else {
        bool found=false;
        for(std::size_t n=0;n<layout.direct_count;++n) {
            const auto& site=layout.direct[n];if(site.record_id!=record_id || f.original_return<site.return_rva)continue;
            const uintptr_t candidate=f.original_return-site.return_rva;
            if(candidate<=UINTPTR_MAX-r.leaf_rva && candidate+r.leaf_rva==f.actual_leaf) {
                unsigned char call[5]{};
                if(!api.copy(call,reinterpret_cast<void*>(candidate+site.call_rva),5) || call[0]!=0xe8){out.reason=BindReason::CallerMismatch;return out;}
                int32_t displacement=0;memcpy(&displacement,call+1,4);
                const int64_t expected=static_cast<int64_t>(r.leaf_rva)-site.return_rva;
                if(displacement!=expected){out.reason=BindReason::CallerMismatch;return out;}
                base=candidate;found=true;break;
            }
        }
        if(!found){out.reason=BindReason::OriginUnknown;return out;}
    }
    if(!base || base>UINTPTR_MAX-layout.image_size || r.leaf_rva>=r.leaf_end || r.leaf_end>layout.image_size ||
       r.original_rva>=layout.image_size || !r.anchor_size || r.anchor_size>32 || r.original_rva>layout.image_size-r.anchor_size ||
       base+r.leaf_rva!=f.actual_leaf || base+r.original_rva!=f.native_original_target) {out.reason=BindReason::MappingMismatch;return out;}
    RUNTIME_FUNCTION runtime{};uintptr_t registered=0;
    if(!api.unwind(api.shims[record_id],registered,runtime)){out.reason=BindReason::UnwindMissing;return out;}
    if(registered+runtime.BeginAddress!=api.shims[record_id] || registered+runtime.EndAddress!=api.shim_ends[record_id]) {out.reason=BindReason::UnwindMismatch;return out;}
    unsigned char unwind[32]{};
    if(layout.unwind_size>sizeof(unwind) || !api.copy(unwind,reinterpret_cast<void*>(registered+runtime.UnwindData),layout.unwind_size) ||
       memcmp(unwind,layout.unwind_bytes,layout.unwind_size)){out.reason=BindReason::UnwindMismatch;return out;}
    unsigned char leaf[20]{};uintptr_t shim=0;
    if(r.leaf_end-r.leaf_rva!=20 || !api.copy(leaf,reinterpret_cast<void*>(f.actual_leaf),20) ||
       leaf[0]!=0x4c || leaf[1]!=0x8d || leaf[2]!=0x15 || leaf[7]!=0x4c || leaf[8]!=0x8d || leaf[9]!=0x1d || leaf[14]!=0xff || leaf[15]!=0x25) {out.reason=BindReason::LeafMismatch;return out;}
    int32_t relative=0;memcpy(&relative,leaf+3,4);
    if(static_cast<int64_t>(r.leaf_rva+7)+relative!=r.original_rva){out.reason=BindReason::LeafMismatch;return out;}
    memcpy(&relative,leaf+10,4);
    if(static_cast<int64_t>(r.leaf_rva+14)+relative!=r.leaf_rva){out.reason=BindReason::LeafMismatch;return out;}
    memcpy(&relative,leaf+16,4);
    if(static_cast<int64_t>(r.leaf_rva+20)+relative!=r.shim_iat_rva ||
       !api.copy(&shim,reinterpret_cast<void*>(base+r.shim_iat_rva),8) || shim!=api.shims[record_id]) {out.reason=BindReason::IatMismatch;return out;}
    // Metadata only: wrapper remains zero until complete fresh verification.
    out.base=base;out.original=f.native_original_target;source_diagnostic::current_prefix_verified=true;
    unsigned char original[32]{};
    source_diagnostic::passed=false;source_diagnostic::query={};
    if((source_diagnostic::step=1,!api.code(f.native_original_target,r.anchor_size)) ||
       (source_diagnostic::step=2,!api.copy(original,reinterpret_cast<void*>(f.native_original_target),r.anchor_size)) ||
       (source_diagnostic::step=3,memcmp(original,r.anchor,r.anchor_size))){out.reason=BindReason::OriginalSourceMismatch;return out;}
    source_diagnostic::passed=true;
    out.base=base;out.original=f.native_original_target;out.wrapper=api.wrappers[index];out.reason=BindReason::Bound;return out;
}
struct OriginalForwardBinding {
    SRWLOCK lock=SRWLOCK_INIT;std::atomic<uintptr_t> base{0};std::array<std::atomic<uintptr_t>,9> originals{};
    // Set only after the existing complete all9 check and seven-target publication.
    std::atomic<uintptr_t> all_roles_verified_base{0};
    BindingResult publish(BindingResult result,ForwardRole role) noexcept {
        if(!result.wrapper)return result;
        AcquireSRWLockExclusive(&lock);const auto current=base.load(std::memory_order_relaxed);
        if(current && current!=result.base){result.wrapper=0;result.reason=BindReason::GenerationConflict;}
        else {base.store(result.base,std::memory_order_release);originals[static_cast<unsigned>(role)].store(result.original,std::memory_order_release);}
        ReleaseSRWLockExclusive(&lock);return result;
    }
    bool allow_current_connect(const BindingResult& fresh,const BindingResult& failed,
                               uint32_t record,uint32_t stage,int failed_record) noexcept {
        if(record!=0 || !fresh.wrapper || fresh.reason!=BindReason::Bound || !fresh.base || !fresh.original ||
           failed.wrapper || failed.reason!=BindReason::OriginalSourceMismatch || stage!=2 ||
           failed_record<=0 || failed_record>=9)return false;
        AcquireSRWLockShared(&lock);
        const auto proof=all_roles_verified_base.load(std::memory_order_acquire);
        const bool allowed=proof && proof==fresh.base && base.load(std::memory_order_acquire)==fresh.base &&
            originals[static_cast<unsigned>(ForwardRole::Connect)].load(std::memory_order_acquire)==fresh.original;
        ReleaseSRWLockShared(&lock);return allowed;
    }
    bool same_source_proof(uintptr_t image,uintptr_t original,ForwardRole role) noexcept {
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
    uintptr_t target(ForwardRole role) const noexcept {return originals[static_cast<unsigned>(role)].load(std::memory_order_acquire);}
};
