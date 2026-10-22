// Non-buildable exact excerpts of our adapter glue. Original client code, fixed ABI addresses, memory-layout readers and private runtime data are excluded. External dependencies remain explicit and are described in BRIEF.

// EXACT OWN GLUE EXCERPT: popup_button_wm.hpp lines 7-82; source SHA256 427fe11df54900e87d234b10bf1a862b1cacd299d5f62a1b5ab3e3c13697cc76
namespace popup_button_wm {
namespace gateway=shop_wndproc_dispatch;
struct Point {
    gateway::Proof window{};int32_t x=0,y=0;RECT rect{};DWORD dpi=0;
};
inline bool Valid(const Point& p) noexcept {
    return p.x>=-32768&&p.x<=32767&&p.y>=-32768&&p.y<=32767&&p.dpi&&
        p.rect.left<=p.x&&p.x<p.rect.right&&p.rect.top<=p.y&&p.y<p.rect.bottom;
}
inline gateway::Message Message(const Point& p,unsigned index) noexcept {
    const LPARAM packed=static_cast<LPARAM>((static_cast<uint32_t>(p.x)&0xffffu)|
        ((static_cast<uint32_t>(p.y)&0xffffu)<<16));
    return {static_cast<UINT>(index==0?WM_MOUSEMOVE:index==1?WM_LBUTTONDOWN:WM_LBUTTONUP),
        static_cast<WPARAM>(index==1?MK_LBUTTON:0),packed};
}
// Before may inspect current helper/button/capture. After is deliberately a
// separate operation: whole original UP can retire all those borrowed objects.
template<class Owner>struct Call {
    Owner& owner;unsigned index=0;bool cleanup=false,invocationFinished=false;
    static bool Current(void* raw,const gateway::Proof& proof) noexcept {
        auto& c=*static_cast<Call*>(raw);
        return c.invocationFinished?c.owner.after(c.index,c.cleanup,proof):c.owner.before(c.index,c.cleanup,proof);
    }
    static void Invoke(void* raw,HWND hwnd,UINT id,WPARAM keys,LPARAM xy,
                       gateway::detail::Invocation& out) noexcept {
        auto& c=*static_cast<Call*>(raw);
        gateway::detail::WinInvoke(nullptr,hwnd,id,keys,xy,out);
        // Only phase bookkeeping. Original invoke result/exception is untouched.
        c.invocationFinished=true;
    }
    gateway::Result run(const Point& point) noexcept {
        if(index>2||!Valid(point))return {};
        const gateway::detail::Seams api{this,gateway::detail::WinIsWindow,gateway::detail::WinWindowThread,
            gateway::detail::WinCurrentPid,gateway::detail::WinCurrentTid,gateway::detail::WinWndProc,gateway::detail::WinClass,
            gateway::detail::WinHost,gateway::detail::WinQuery,gateway::detail::WinRead,Invoke};
        return gateway::detail::DispatchWithSeams(point.window,Message(point,index),Current,this,api);
    }
};
struct Outcome {
    TargetClaim targetClaim=TargetClaim::Unknown;
    popup_button_wm::TargetProfile targetProfile=popup_button_wm::TargetProfile::Unknown;
    popup_button_wm::TargetFlag target3ea=popup_button_wm::TargetFlag::Unknown,target41c=popup_button_wm::TargetFlag::Unknown;
    popup_button_wm::TargetFlag preDownD194=popup_button_wm::TargetFlag::Unknown;

    unsigned attempted=0,returned=0;bool complete=false,cleanupUp=false,cleanupFailed=false;
    gateway::Result firstFailure{},cleanupResult{};
};
inline bool Returned(const gateway::Result& r) noexcept {
    return r.status==gateway::Status::ReturnedCurrent&&r.reason==gateway::Reason::None&&
        r.attempted&&r.returned&&r.post_current&&!r.exception_code&&
        r.fault_area==gateway::FaultArea::None&&!r.boundary_rva;
}
template<class Environment>inline Outcome Sequence(Environment& env) noexcept {
    Outcome out{};bool downReturned=false;
    for(unsigned index=0;index<3;++index){
        const auto call=env.dispatch(index,false);
        if(call.attempted)out.attempted|=1u<<index;
        if(call.returned)out.returned|=1u<<index;
        if(!Returned(call)){
            out.firstFailure=call;
            // A normal DOWN plus a wholly unattempted UP may need one cleanup
            // release on the same owned HWND. Never continue after a fault or
            // ambiguous invocation, never generate another DOWN or retry.
            if(downReturned&&!call.attempted&&!(out.attempted&4u)&&!call.exception_code){
                const auto cleanup=env.dispatch(2,true);out.cleanupResult=cleanup;
                out.cleanupUp=cleanup.attempted;out.cleanupFailed=!Returned(cleanup);
                if(cleanup.attempted)out.attempted|=4u;
                if(cleanup.returned)out.returned|=4u;
            }
            return out;
        }
        if(index==1)downReturned=true;
    }
    out.complete=true;return out; // Original WM returns only; hit/Submit UNKNOWN.
}
} // namespace popup_button_wm


// EXACT OWN GLUE EXCERPT: popup_button_binding.hpp lines 60-165; source SHA256 d95ba6ff38696830f0e87e09a6c51b7c369b1ed3b3fa7c5162fbf0eea1aab190
template<class PointSource>struct Owner {
    const Request& request;Flight& flight;Button button{};ui::HostBorrow host{};
    popup_button_wm::Point point{};typename PointSource::State pointBinding{};uintptr_t touchIdentity=0;uint32_t touchIndex=UINT_MAX;
    bool touchBound=false,upReturned=false;
    popup_button_wm::TargetClaim targetClaim=popup_button_wm::TargetClaim::Unknown;
    popup_button_wm::TargetProfile targetProfile=popup_button_wm::TargetProfile::Unknown;
    popup_button_wm::TargetFlag target3ea=popup_button_wm::TargetFlag::Unknown,target41c=popup_button_wm::TargetFlag::Unknown;
    popup_button_wm::TargetFlag preDownD194=popup_button_wm::TargetFlag::Unknown;

    bool Window(bool geometry) noexcept {
        // This post-call graph has no Snapshot/modal PlayerCurrent/Actor read.
        // FrameCurrent reads Director/scene identity and host/view only.
        if(terminal.load()||manual_move::sourceQuitTerminal.load()||!manual_move::busy.load()||
           !manual_move::OwnedNow()||!item_transfer_entry::PopupFrameBorrowCurrent()||
           manual_move::lastSequence.load()!=request.core.seq||point.window.pid!=request.core.pid||
           point.window.process_birth!=request.core.birth||scope.base!=point.window.image_base)return false;
        forward_diagnostic::Context owner{};ui::HostBorrow now{};
        if(!forward_diagnostic::context(owner)||!manual_move::SameOwner(owner)||!manual_move::CorrectThread(owner)||
           owner.pid!=request.core.pid||owner.birth!=request.core.birth||!ui::AcquireHost(now)||
           now.window!=host.window||now.host!=host.host||now.view!=host.view||
           reinterpret_cast<HWND>(point.window.hwnd)!=now.window)return false;
        if(geometry){RECT rect{};
            if(!GetClientRect(now.window,&rect)||GetDpiForWindow(now.window)!=point.dpi||
               memcmp(&rect,&point.rect,sizeof(rect))||!popup_button_wm::Valid(point))return false;
        }
        return true;
    }
    bool Idle() noexcept {
        ui::ContactPoint input{};
        return ui::InputState(host,input)&&!input.down&&!input.present;
    }
    bool SameTouch() noexcept {
        if(!touchBound||upReturned||!touchIdentity||touchIndex>=15)return false;
        ui::ContactPoint input{};
        return ui::InputState(host,input)&&input.down&&input.present&&
            input.index==touchIndex&&input.touch==touchIdentity;
    }
    bool Prepare() {
        if(!NormalCheck(120,CurrentButton(request,flight,button,true),flight)||!NormalCheck(121,ui::AcquireHost(host),flight)||!NormalCheck(122,Idle(),flight))return false;
        // The implementation must derive this point for exactly button.widget
        // through the accepted normal Widget/scene/View geometry contract.
        if(!NormalCheck(123,PointSource::prepare(request,flight,button,host,point,pointBinding),flight)||
           !NormalCheck(124,CurrentButton(request,flight,button,false),flight))return false;
        point.window.image_base=scope.base;point.window.image_size=OwnForwardLayout::ImageSize;
        point.window.pid=request.core.pid;point.window.process_birth=request.core.birth;
        point.window.ui_thread_id=GetCurrentThreadId();point.window.hwnd=host.window;
        point.window.host=host.host;point.window.view=host.view;
        point.window.registered_proc=GetWindowLongPtrW(host.window,GWLP_WNDPROC);
        return NormalCheck(125,Window(true),flight)&&NormalCheck(126,Idle(),flight);
    }
    bool BeforeBody(unsigned index,bool cleanup,const popup_button_wm::gateway::Proof&) {
        if(index==1)preDownD194=popup_button_wm::TargetFlag::Unknown;
        if(!NormalCheck(130,Window(!cleanup),flight))return false;
        if(cleanup)return NormalCheck(131,index==2&&SameTouch(),flight); // No helper/capture/Actor/point getter here.
        if(!NormalCheck(132,item_popup_deadline::Executing(),flight)||!NormalCheck(133,CurrentButton(request,flight,button,false),flight)||
           !NormalCheck(134,PointSource::current(request,flight,button,host,point,pointBinding,popup_input352::ForMessage(index)),flight)||
           !NormalCheck(135,CurrentButton(request,flight,button,false),flight))return false;
        const bool current=NormalCheck(136,index<2?Idle():index==2&&SameTouch(),flight);
        if(current&&index==1)preDownD194=pointBinding.preDownD194;
        if(current&&index==2){targetClaim=ObserveTargetClaim(button.listener,touchIdentity);
            ObserveTargetState(button.widget,button.table,scope.base,targetProfile,target3ea,target41c);}
        return current; // Diagnostic UNKNOWN/NOT_CLAIMED cannot suppress original UP.
    }
    bool BeforeCpp(unsigned index,bool cleanup,const popup_button_wm::gateway::Proof& proof) noexcept {
        return CppCurrentWith(flight,[&](){return BeforeBody(index,cleanup,proof);});
    }
    bool before(unsigned index,bool cleanup,const popup_button_wm::gateway::Proof& proof) noexcept {
        __try{return BeforeCpp(index,cleanup,proof);}
        __except(EXCEPTION_EXECUTE_HANDLER){flight.ambiguous=true;flight.reason=Exception;return false;}
    }
    bool AfterBody(unsigned index,bool cleanup,const popup_button_wm::gateway::Proof&) noexcept {
        if(!Window(!cleanup))return false;
        ui::ContactPoint input{};if(!ui::InputState(host,input))return false;
        if(index==0)return !input.down&&!input.present;
        if(index==1){
            if(!input.down||!input.present||!input.touch||input.index>=15)return false;
            if(touchBound)return input.touch==touchIdentity&&input.index==touchIndex;
            touchBound=true;touchIdentity=input.touch;touchIndex=input.index;return true;
        }
        if(index!=2||input.down||input.present||!touchBound||touchIndex>=15||
           (input.mask&(uint32_t{1}<<touchIndex)))return false;
        // InputState reads fresh map/slot values only. Never dereference the
        // old Touch, helper/capture or Actor after original UP callback RET.
        touchBound=false;touchIdentity=0;touchIndex=UINT_MAX;upReturned=true;return true;
    }
    bool AfterCpp(unsigned index,bool cleanup,const popup_button_wm::gateway::Proof& proof) noexcept {
        return CppCurrentWith(flight,[&](){return AfterBody(index,cleanup,proof);});
    }
    bool after(unsigned index,bool cleanup,const popup_button_wm::gateway::Proof& proof) noexcept {
        __try{return AfterCpp(index,cleanup,proof);}
        __except(EXCEPTION_EXECUTE_HANDLER){flight.ambiguous=true;flight.reason=Exception;return false;}
    }
    popup_button_wm::gateway::Result dispatch(unsigned index,bool cleanup) noexcept {
        popup_button_wm::Call<Owner> call{*this,index,cleanup,false};
        return call.run(point);
    }
};
template<class PointSource>inline popup_button_wm::Outcome Execute(const Request& r,Flight& f) {
    Owner<PointSource> owner{r,f};
    if(!owner.Prepare()){popup_button_wm::Outcome out{};
        out.firstFailure.reason=popup_button_wm::gateway::Reason::CurrentRejected;return out;}
    auto out=popup_button_wm::Sequence(owner);out.targetClaim=owner.targetClaim;
    if(out.complete){out.targetProfile=owner.targetProfile;out.target3ea=owner.target3ea;out.target41c=owner.target41c;out.preDownD194=owner.preDownD194;}
    return out; // Failed final current/UP leaves snapshot fields UNKNOWN.
}
} // namespace normal_button


// EXACT OWN GLUE EXCERPT: popup_button_point.hpp lines 155-183; source SHA256 4fdefd0024387a07d01442f5e6badc26c945ed4bbe6723bb107e6f9aeea928a5
    static bool Produce(const Request& r,Flight& f,const Button& button,const ui::HostBorrow& host,
                        State& state,bool initial,bool derive,point_math::Candidate& candidate,popup_input352::Phase phase) {
        if(!NormalCheck(201,Registration(r,f,button,host,state,initial),f))return false;
        Producer producer{r,f,button,host,derive,candidate,phase};OriginalPort ops{r,f,button,host,state};
        popup_preinput176::Receipt receipt{};
        const bool produced=popup_preinput176::Run(ops,producer,receipt);
        if(receipt.ambiguous){f.ambiguous=true;f.reason=Exception;}
        if(!NormalCheck(202,produced,f))return false;
        candidate=producer.candidate;
        // No callback/camera/VP pointer is consulted after original RET/clear.
        return NormalCheck(203,Registration(r,f,button,host,state,false,
            !derive&&phase==popup_input352::Phase::BeforeDown),f);
    }
    static bool prepare(const Request& r,Flight& f,const Button& button,const ui::HostBorrow& host,
                        popup_button_wm::Point& point,State& state) {
        point_math::Candidate candidate{};
        if(!Produce(r,f,button,host,state,true,true,candidate,popup_input352::Phase::BeforeMove)||
           !NormalCheck(182,GetClientRect(host.window,&point.rect)!=FALSE,f)||
           !NormalCheck(183,(point.dpi=GetDpiForWindow(host.window))!=0,f))return false;
        point.x=candidate.x;point.y=candidate.y;return NormalCheck(184,popup_button_wm::Valid(point),f);
    }
    static bool current(const Request& r,Flight& f,const Button& button,const ui::HostBorrow& host,
                        const popup_button_wm::Point& point,State& state,popup_input352::Phase phase) {
        state.preDownD194=popup_button_wm::TargetFlag::Unknown;
        point_math::Candidate same{point.x,point.y};
        return Produce(r,f,button,host,state,false,false,same,phase);
    }
};
} // namespace normal_button


// EXACT OWN GLUE EXCERPT: popup_button_boundary.hpp lines 5-48; source SHA256 1d8e82d13bcc14964811910b9f9eab6adc8c32c59eb5d820964c2170f413889e
template<class PointSource,class Ops>inline Reply NormalButtonBoundaryWith(const Request& r,Flight& f,Ops& ops) {
    if(!Valid(r)||r.action!=Action::Submit)return {"REFUSED",Invalid,false};
    if(!NormalCheck(100,ops.acquire(r,f),f)||!NormalCheck(101,ops.current(r,f),f))return {"REFUSED",f.reason,false};
    ui::String32 text{};text.capacity=15;
    const int n=sprintf_s(reinterpret_cast<char*>(text.storage),sizeof(text.storage),"%llu",static_cast<unsigned long long>(r.quantity));
    if(n<=0||n>=16)return {"REFUSED",Text,false};text.length=static_cast<uint64_t>(n);
    if(!NormalCheck(102,item_popup_deadline::Begin(),f))return {"REFUSED",Changed,false};
    f.mutated=true;ops.set(r,f,text);
    if(!NormalCheck(103,ops.current(r,f),f)||!NormalCheck(104,ops.readback(r,f,text),f)||!NormalCheck(105,ops.current(r,f),f))return {"UNKNOWN",Changed,false};
    const auto out=normal_button::Execute<PointSource>(r,f);
    helperTrace.targetClaim=out.targetClaim; // Output only; original result/UP/cleanup stay unchanged.
    helperTrace.targetProfile=out.targetProfile;helperTrace.target3ea=out.target3ea;helperTrace.target41c=out.target41c;
    helperTrace.preDownD194=out.preDownD194;
    f.invoked=out.attempted!=0;
    NormalResult(106,out.complete,static_cast<unsigned>(out.firstFailure.reason));
    if(out.firstFailure.exception_code||
       (out.firstFailure.attempted&&!out.firstFailure.returned)||
       out.cleanupResult.exception_code||(out.cleanupResult.attempted&&!out.cleanupResult.returned))f.ambiguous=true;
    // A whole original WndProc triplet returning is input delivery only. Actual
    // hit/callable/scalar/send is decided by unchanged backend/client consumers.
    if(f.ambiguous)return {"UNKNOWN",Exception,f.invoked};
    return out.complete?Reply{"RETURNED",0,true}:Reply{"UNKNOWN",Changed,f.invoked};
}
template<class PointSource,class Ops>inline Reply CppNormalButtonWith(const Request& r,Flight& f,Ops& ops) noexcept {
    try{return NormalButtonBoundaryWith<PointSource>(r,f,ops);}
    catch(...){f.ambiguous=true;return {"UNKNOWN",Exception,f.invoked};}
}
template<class PointSource,class Ops>inline Reply GuardedNormalButtonWith(const Request& r,Flight& f,Ops& ops) noexcept {
    __try{return CppNormalButtonWith<PointSource>(r,f,ops);}
    __except(EXCEPTION_EXECUTE_HANDLER){f.ambiguous=true;return {"UNKNOWN",Exception,f.invoked};}
}
template<class PointSource,class Ops>inline Reply RunNormalButtonWith(const Request& r,Flight& f,Ops& ops) noexcept {
    if(terminal.load())return {"UNKNOWN",9,false};
    Reply result=GuardedNormalButtonWith<PointSource>(r,f,ops);
    if(f.ambiguous){terminal.store(true);return result;}
    const bool cleaned=CleanWith(f,ops);
    if(!cleaned){terminal.store(true);return {"UNKNOWN",Cleanup,f.invoked};}
    source_quit::PreparePopupRefusal(r,result,cleaned,f.ambiguous);
    // Preserve accepted333 domain3 only for its own exact Guard-fallback path;
    // normal WM/other UNKNOWN never masquerades as that settled witness.
    source_quit::PreparePopupGuardSettlement(r,result,cleaned,f.ambiguous,f.guardFallbackReturned,item_popup_deadline::active);
    if(strcmp(result.status,"RETURNED")||!result.invoked)terminal.store(true);
    return result;
}
