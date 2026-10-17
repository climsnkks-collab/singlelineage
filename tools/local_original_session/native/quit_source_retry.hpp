#pragma once
// Included inside quit_detail after the pinned source checker. Invocation-local
// page budget; no new callable, protection write or historical eligibility gate.
struct PageBudget {uintptr_t pages[2]{};unsigned used=0;bool full_guard=false,owner_set=false;Proof owner{};};
inline thread_local source_diagnostic::Query retry_query{};
inline thread_local uintptr_t retry_query_anchor=0;
inline thread_local unsigned retry_pages=0;
inline thread_local bool retry_attempted=false,retry_full_verified=false;
inline unsigned RoutePages(unsigned route,uintptr_t (&pages)[2]) noexcept {
    unsigned count=0;
    for(const auto& a:internal_quit_source::anchors)if(a.route==route){const uintptr_t page=a.rva&~uintptr_t(0xfff);
        bool seen=false;for(unsigned i=0;i<count;++i)if(pages[i]==page)seen=true;
        if(!seen){if(count==2)return 0;pages[count++]=page;}}
    return count;
}
inline bool Eligible(uintptr_t base,const internal_quit_source::Anchor& a,const source_diagnostic::Query& q) noexcept {
    constexpr uintptr_t imageSize=OwnForwardLayout::ImageSize;
    const auto n=a.size;
    if(!base||(base&0xfff)||base>UINTPTR_MAX-imageSize||!n||n>32||n>imageSize||a.rva>imageSize-n||
       !q.observed||!q.region_observed||q.returned!=sizeof(MEMORY_BASIC_INFORMATION)||q.span!=n||q.category!=6||
       q.state!=MEM_COMMIT||q.type!=MEM_IMAGE||q.protect!=PAGE_NOACCESS||q.allocation_base!=base)return false;
    const uintptr_t address=base+a.rva;
    return q.region_start<=address&&q.region_start<=UINTPTR_MAX-q.region_size&&address<=UINTPTR_MAX-n&&
        address+n<=q.region_start+q.region_size && (address&~uintptr_t(0xfff))==((address+n-1)&~uintptr_t(0xfff));
}
template<class Code,class Copy,class FreshProof>
inline bool VerifySourceRetry(const Proof& p,PageBudget& budget,Code code,Copy copy,FreshProof fresh) noexcept {
    if(!budget.owner_set){budget.owner=p;budget.owner_set=true;}
    else if(!Same(budget.owner,p)){diagnostic_phase=83;return false;}
    uintptr_t allowed[2]{};const unsigned pageCount=RoutePages(Route(p.sceneKind),allowed);
    if(!pageCount)return false;
    // Each failed page can cause one restart; the final pass must verify every
    // original anchor from the beginning. No repeated page/anchor attempt.
    for(unsigned pass=0;pass<=pageCount;++pass){
        if(SourceProof(p,code,copy))return true;
        if(diagnostic_step!=1)return false;
        const auto q=source_diagnostic::query;const uintptr_t rva=diagnostic_anchor;
        retry_query=q;retry_query_anchor=rva;
        const internal_quit_source::Anchor* anchor=nullptr;
        for(const auto& a:internal_quit_source::anchors)if(a.route==Route(p.sceneKind)&&a.rva==rva){anchor=&a;break;}
        if(!anchor||!Eligible(p.base,*anchor,q)||budget.used>=pageCount)return false;
        const uintptr_t page=rva&~uintptr_t(0xfff);bool known=false;
        for(unsigned i=0;i<pageCount;++i)if(allowed[i]==page)known=true;
        for(unsigned i=0;i<budget.used;++i)if(budget.pages[i]==page)return false;
        if(!known||!fresh(p))return false;
        budget.pages[budget.used++]=page;
        const DWORD before=GetLastError();unsigned char scratch[32]{};
        const bool read=copy(scratch,reinterpret_cast<void*>(p.base+rva),anchor->size);
        volatile unsigned char consumed=0;
        if(read)for(size_t i=0;i<anchor->size;++i)consumed=static_cast<unsigned char>(consumed^scratch[i]);
        (void)consumed;SetLastError(before);
        if(!read){diagnostic_phase=82;diagnostic_anchor=rva;diagnostic_step=2;return false;}
        if(!fresh(p))return false;
    }
    return false;
}
inline bool RetryFreshProof(const Proof& expected) noexcept {
    Proof current;if(!Read(current))return false;
    if(!Same(expected,current)){diagnostic_phase=83;return false;}return true;
}
inline bool Source(const Proof& p,PageBudget& budget) noexcept {
    return VerifySourceRetry(p,budget,Executable,SafeCopy,RetryFreshProof);
}
