#pragma once
// Included once after source_reselect.hpp by the existing AutoOkGetMessage TU.
// Root supplies the separately owned exact Daybreak header/include path.
#include "shop_wndproc_dispatch.hpp"
#include "shop_wndproc_protocol.hpp"
#include "shop_wndproc_sequence.hpp"
#include "shop_wndproc_hover.hpp"
#include "shop_wndproc_body_cache.hpp"
#include "body_point.hpp"
namespace shop_wndproc_input {
namespace ui=use_item::owned_ui;
static_assert(static_cast<unsigned>(shop_wndproc_dispatch::Reason::RegistrationChanged)==5 &&
    static_cast<unsigned>(shop_wndproc_dispatch::Reason::SourcePageRefused)==7 &&
    static_cast<unsigned>(shop_wndproc_dispatch::Reason::SourceBytesChanged)==8 &&
    static_cast<unsigned>(shop_wndproc_dispatch::Reason::PostCallChanged)==12,"strict reason wire mapping");
static_assert(static_cast<unsigned>(shop_wndproc_dispatch::RegistrationStage::None)==0 &&
    static_cast<unsigned>(shop_wndproc_dispatch::RegistrationStage::ClassInfo)==9,"strict registration stage wire range");
struct CurrentContext {
    const Request* request=nullptr;forward_diagnostic::Context owner{};
    ui::HostBorrow host{};manual_move::Pins pins{};Pair player{};
    bool cleaning=false;
};
inline unsigned Cancellation(const CurrentContext& context) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\shop-wndproc-cancel-%u.json",context.owner.directory,context.request->seq);
    const DWORD attributes=GetFileAttributesW(path);
    if(attributes!=INVALID_FILE_ATTRIBUTES)return 1;
    const DWORD error=GetLastError();return error==ERROR_FILE_NOT_FOUND||error==ERROR_PATH_NOT_FOUND?0:2;
}
inline bool Player(const manual_move::Pins& pins,uint64_t uid,Pair& result) noexcept {
    result={};uintptr_t begin=0;size_t count=0;
    if(!original_move::Vector(reinterpret_cast<uintptr_t>(pins.actors.object)+0x8a8,512,begin,count))return false;
    for(size_t i=0;i<count;++i){Pair p{};uintptr_t table=0;uint64_t actual=0;
        if(!ui::Read(begin,i*16,p)||!ui::Read(reinterpret_cast<uintptr_t>(p.object),0,table))return false;
        if(table==scope.base+0x11819f0){
            if(result.object||!ui::Read(reinterpret_cast<uintptr_t>(p.object),0x18,actual)||actual!=uid)return false;
            result=p;
        }
    }
    return result.object&&result.control;
}
inline bool SamePair(Pair a,Pair b) noexcept {return a.object==b.object&&a.control==b.control;}
inline bool CurrentBody(CurrentContext& c,const shop_wndproc_dispatch::Proof& proof) {
    const auto& r=*c.request;
    if(manual_move::terminal.load()||manual_move::sourceQuitTerminal.load()||!manual_move::OwnedNow()||
       !manual_move::busy.load()||scope.base!=proof.image_base||proof.image_size!=OwnForwardLayout::ImageSize||
       proof.process_birth!=c.owner.birth||proof.pid!=c.owner.pid||proof.hwnd!=reinterpret_cast<HWND>(r.hwnd)||
       proof.ui_thread_id!=r.uiThread||autoOkWindow.load()!=proof.hwnd||
       proof.host!=c.host.host||proof.view!=c.host.view||manual_move::lastSequence.load()!=r.seq)return false;
    forward_diagnostic::Context now{};ui::HostBorrow host{};
    if(!forward_diagnostic::context(now)||!manual_move::SameOwner(now)||now.birth!=c.owner.birth||now.pid!=c.owner.pid||
       !manual_move::CorrectThread(now)||!ui::AcquireHost(host)||host.window!=c.host.window||
       host.host!=c.host.host||host.view!=c.host.view)return false;
    RECT rect{};
    if(!GetClientRect(proof.hwnd,&rect)||rect.left!=r.rect[0]||rect.top!=r.rect[1]||
       rect.right!=r.rect[2]||rect.bottom!=r.rect[3]||GetDpiForWindow(proof.hwnd)!=r.dpi||
       r.x<rect.left||r.x>=rect.right||r.y<rect.top||r.y>=rect.bottom)return false;
    manual_move::Pins current{};unsigned reason=0;const bool found=manual_move::Find(current,5,reason);
    Held ownUi{current.ui},state{current.state},scene{current.scene},layout{current.layout},actors{current.actors};
    if(!found||!manual_move::Stable(c.pins,5)||!manual_move::Stable(current,5)||
       !SamePair(c.pins.ui,current.ui)||!SamePair(c.pins.state,current.state)||
       !SamePair(c.pins.scene,current.scene)||!SamePair(c.pins.actors,current.actors))return false;
    Pair player{};return Player(current,r.player,player)&&SamePair(player,c.player)&&
        !manual_move::terminal.load()&&!manual_move::sourceQuitTerminal.load()&&manual_move::OwnedNow();
}
inline bool Current(void* raw,const shop_wndproc_dispatch::Proof& proof) noexcept {
    __try {return raw&&CurrentBody(*static_cast<CurrentContext*>(raw),proof);}
    __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
struct HoverReader {
    template<class T>bool Read(uintptr_t at,size_t offset,T& value) noexcept {return ui::Read(at,offset,value);}
};
inline HoverObservation ObserveCurrentHover(CurrentContext& context,const shop_wndproc_dispatch::Proof& proof) noexcept {
    const HoverObservation unknown{HoverState::Unknown,0};
    if(!Current(&context,proof))return unknown;
    HoverReader reader{};
    const auto observation=ReadCurrentKey0(reinterpret_cast<uintptr_t>(context.pins.actors.object),reader);
    if(!Current(&context,proof))return unknown;
    return observation;
}
// REA205 passive post-MOVE excerpt; all owning pairs are local to this call.
// Concrete profiles only, first match; no RTTI/derived or install-success claim.
template<class S>inline ParticipationObservation ReadCurrentParticipation(S& s,Pair player) noexcept {
    auto out=UnknownParticipation();uintptr_t root=0,gi=0,begin=0;size_t count=0;unsigned char ready=0;
    if(!body::Read(s,s.ImageBase(),0x1668790,root)||!body::Read(s,root,0xd8,ready)||!ready||
       !body::Read(s,root,0xd0,gi)||!body::Vector(s,gi,0x180,0x188,16,begin,count)||count>128)return out;
    body::Pair selected{};
    for(size_t i=0;i<count;++i){body::Pair p{};uintptr_t table=0;
        if(!body::Read(s,begin,i*16,p)||!body::Read(s,p.object,0,table))return out;
        if(table==s.ImageBase()+0x1182d40){selected=p;break;}}
    Pair manager{};
    if(!manual_move::Hold({reinterpret_cast<void*>(selected.object),reinterpret_cast<void*>(selected.control)},manager))return out;
    Held managerHeld{manager};const auto m=reinterpret_cast<uintptr_t>(manager.object);
    unsigned char marker=0;uintptr_t listener=0,dispatcher=0;
    if(body::Read(s,m,0x10,marker)&&body::Read(s,m,0x1b0,listener)&&body::Read(s,m,0x1c8,dispatcher)){
        out.marker=marker;out.listener=listener!=0;out.dispatcher=dispatcher!=0;
        out.fields=marker==1&&listener&&dispatcher?ParticipationFields::Present:ParticipationFields::Incomplete;}
    const auto o=reinterpret_cast<uintptr_t>(player.object);selected={};
    if(!body::Vector(s,o,0x20,0x28,16,begin,count))return out;
    for(size_t i=0;i<count;++i){body::Pair p{};uintptr_t table=0,secondary=0,owner=0;
        if(!body::Read(s,begin,i*16,p)||!body::Read(s,p.object,0,table))return out;
        if(table!=s.ImageBase()+0x11811f0)continue;
        if(!body::Read(s,p.object,0x38,secondary)||secondary!=s.ImageBase()+0x1181188||
           !body::Read(s,p.object,8,owner)||owner!=o)return out;
        selected=p;break;}
    Pair component{};
    if(!manual_move::Hold({reinterpret_cast<void*>(selected.object),reinterpret_cast<void*>(selected.control)},component))return out;
    Held componentHeld{component};const auto p=reinterpret_cast<uintptr_t>(component.object),cp=reinterpret_cast<uintptr_t>(component.control);
    if(!body::Span(p,0x38,1))return out;
    const auto secondary=p+0x38;uintptr_t head=0,node=0;
    if(!body::Read(s,m,0x1d8,head)||!body::Read(s,head,8,node))return out;
    uintptr_t visited[512]{};unsigned used=0;
    for(unsigned hops=0;hops<512;++hops){
        for(unsigned i=0;i<used;++i)if(visited[i]==node)return out;visited[used++]=node;
        unsigned char nil=0;if(!body::Read(s,node,0x19,nil))return out;
        if(nil){if(node==head)out.pair=ParticipationPair::NotFound;return out;}
        int32_t key=0;if(!body::Read(s,node,0x20,key))return out;
        if(key!=2){if(!body::Read(s,node,key<2?0x10:0,node))return out;continue;}
        if(!body::Vector(s,node,0x28,0x30,16,begin,count))return out;
        for(size_t i=0;i<count;++i){body::Pair pair{};if(!body::Read(s,begin,i*16,pair))return out;
            if(pair.object==secondary&&pair.control==cp){out.pair=ParticipationPair::Found;return out;}}
        out.pair=ParticipationPair::NotFound;return out;
    }return out;
}
// End REA205 passive excerpt.
// REA212 same-HostBorrow current snapshots. No branch replay or callback claim.
template<class S>inline WindowMouseRoute ReadWindowMouseRoute(S& s,uintptr_t window) noexcept {
    uint32_t mode=0;if(!body::Read(s,window,0x8c,mode))return WindowMouseRoute::Unknown;
    if(mode!=0x34003)return WindowMouseRoute::Ordinary;
    uintptr_t selected=0;uint32_t condition=0;
    if(!body::Read(s,s.ImageBase(),0x17a8c28,selected))return WindowMouseRoute::Unknown;
    if(selected!=window)return WindowMouseRoute::DisabledSkipped;
    if(!body::Read(s,window,0x208,condition))return WindowMouseRoute::Unknown;
    return !condition?WindowMouseRoute::DisabledEligible:WindowMouseRoute::DisabledSkipped;
}
template<class S>inline ViewMouseAdmission ReadViewMouseAdmission(S& s,uintptr_t view) noexcept {
    float epsilon=0;uint32_t mask[4]{};
    // Original VMOVDQU loads 16B; scalar VCOMISS consumes only the low F32 lane.
    if(!body::Read(s,s.ImageBase(),0x126e920,epsilon)||!std::isfinite(epsilon)||
       !body::Read(s,s.ImageBase(),0x126f700,mask))return ViewMouseAdmission::Unknown;
    float rect[4]{};unsigned loaded=0;bool fast=true;
    for(unsigned i=0;i<4;++i){float initial=0;
        if(!body::Read(s,view,0x20+4*i,rect[i])||!std::isfinite(rect[i])||
           !body::Read(s,s.ImageBase(),0x1809820+4*i,initial)||!std::isfinite(initial))return ViewMouseAdmission::Unknown;
        loaded=i+1;const float difference=body::Minus(rect[i],initial);uint32_t bits=0;memcpy(&bits,&difference,4);bits&=mask[0];
        float absolute=0;memcpy(&absolute,&bits,4);if(!std::isfinite(difference)||!std::isfinite(absolute))return ViewMouseAdmission::Unknown;
        if(!(absolute<epsilon)){fast=false;break;}
    }
    if(fast)return ViewMouseAdmission::FastDefault;
    for(unsigned i=loaded;i<4;++i)if(!body::Read(s,view,0x20+4*i,rect[i])||!std::isfinite(rect[i]))return ViewMouseAdmission::Unknown;
    float x=0,y=0;if(!body::Read(s,view,0xb0,x)||!body::Read(s,view,0xb4,y)||!std::isfinite(x)||!std::isfinite(y))return ViewMouseAdmission::Unknown;
    const float right=body::Plus(rect[0],rect[2]),bottom=body::Plus(rect[1],rect[3]);
    if(!std::isfinite(right)||!std::isfinite(bottom))return ViewMouseAdmission::Unknown;
    return x>=rect[0]&&x<=right&&y>=rect[1]&&y<=bottom?ViewMouseAdmission::Contains:ViewMouseAdmission::Rejected;
}
// End REA212 snapshot excerpt.
// REA215 current selector, same HostBorrow/View call scope; raw pointers never escape.
// ZERO/NONZERO describe one U8 snapshot, not a dispatch/enable/install witness.
template<class S>inline CurrentDispatcherGate ReadCurrentDispatcherGate(S& s,uintptr_t hostView) noexcept {
    uintptr_t director=0,view=0,currentD=0;unsigned char gate=0;
    if(!body::Read(s,s.ImageBase(),0x1807fd8,director)||!director||!s.QualifiedPrimary(director,0x1237f90)||
       !body::Read(s,director,0x100,view)||view!=hostView||
       !body::Read(s,director,0xa0,currentD)||!currentD||!body::Read(s,currentD,0x194,gate))return CurrentDispatcherGate::Unknown;
    return gate?CurrentDispatcherGate::Nonzero:CurrentDispatcherGate::Zero;
}
// End REA215 current dispatcher snapshot excerpt.
#include "shop_wndproc_body_binding.hpp"
#include "shop_wndproc_point_binding.hpp"
struct Environment {
    CurrentContext* context=nullptr;Outcome* outcome=nullptr;PointObservation point{};shop_wndproc_dispatch::Proof proof{};
    CallResult Dispatch(unsigned index,bool cleanup) noexcept {
        const LPARAM packedPoint=static_cast<LPARAM>((static_cast<uint32_t>(this->point.x)&0xffffu)|
                         ((static_cast<uint32_t>(this->point.y)&0xffffu)<<16));
        const shop_wndproc_dispatch::Message message{static_cast<UINT>(index==0?WM_MOUSEMOVE:index==1?WM_LBUTTONDOWN:WM_LBUTTONUP),
                                                     static_cast<WPARAM>(index==1?MK_LBUTTON:0),packedPoint};
        if(!cleanup){
            const unsigned cancellation=Cancellation(*context);
            if(cancellation){
                CallResult cancelled{};cancelled.reason=cancellation==1?62004:62006;return cancelled;
            }
        }
        context->cleaning=cleanup;
        outcome->gatewayActive=true;
        const auto result=shop_wndproc_dispatch::Dispatch(proof,message,Current,context);
        outcome->gatewayActive=false;
        context->cleaning=false;
        if(!cleanup&&index==0&&result.status==shop_wndproc_dispatch::Status::ReturnedCurrent){
            outcome->hover=ObserveCurrentHover(*context,proof);
            outcome->body=ObserveCurrentBody(*context,proof,context->request->expectedNpcUid,&outcome->participation,&outcome->mouseAdmission);
        }
        return {static_cast<unsigned>(result.reason),result.attempted,result.returned,result.post_current,
            result.exception_code,result.status==shop_wndproc_dispatch::Status::ReturnedCurrent,
            static_cast<unsigned>(result.fault_area),result.boundary_rva,result.unwind_proved,
            result.exception_address,result.exception_access_address,result.exception_operation,
            static_cast<unsigned>(result.registration_stage)};
    }
};
inline bool CancelBeforePoint(CurrentContext& current,const shop_wndproc_dispatch::Proof& proof,Outcome& out) noexcept {
    const unsigned cancellation=Cancellation(current);if(!cancellation)return false;
    out.reason=cancellation==1?62004:62006;
    if(cancellation==1&&!Current(&current,proof)){out.status="UNKNOWN";out.reason=62006;}
    return true;
}
inline void Execute(const Request& r,const forward_diagnostic::Context& owner,Outcome& out) {
    if(manual_move::terminal.load()||manual_move::sourceQuitTerminal.load()||!manual_move::OwnedNow())return;
    CurrentContext current{};current.request=&r;current.owner=owner;
    unsigned reason=0;const bool found=manual_move::Find(current.pins,5,reason);
    Held ownUi{current.pins.ui},state{current.pins.state},scene{current.pins.scene},layout{current.pins.layout},actors{current.pins.actors};
    if(!found||!manual_move::Stable(current.pins,5)||!ui::AcquireHost(current.host)||
       current.host.window!=reinterpret_cast<HWND>(r.hwnd))return;
    Pair player{};if(!Player(current.pins,r.player,player)||!manual_move::Hold(player,current.player))return;
    Held playerOwner{current.player};
    Environment env{};env.context=&current;env.outcome=&out;
    env.proof.image_base=scope.base;env.proof.image_size=OwnForwardLayout::ImageSize;
    env.proof.process_birth=owner.birth;env.proof.pid=owner.pid;env.proof.ui_thread_id=r.uiThread;
    env.proof.hwnd=current.host.window;env.proof.host=current.host.host;env.proof.view=current.host.view;
    env.proof.registered_proc=GetWindowLongPtrW(current.host.window,GWLP_WNDPROC);
    if(!Current(&current,env.proof))return;
    if(CancelBeforePoint(current,env.proof,out))return;
    if(r.bodyPoint){BodyReadSection section{&current,&env.proof};env.point=DeriveBodyPoint(section,reinterpret_cast<uintptr_t>(current.pins.scene.object),current.host.host,current.host.view,r.expectedNpcUid,r.rect);}
    else {env.point.state=PointState::Ready;env.point.x=r.x;env.point.y=r.y;}
    if(env.point.state!=PointState::Ready){out.status="UNKNOWN";out.reason=62007;out.point=env.point;return;}
    Sequence(env,out);
    out.point=env.point; // Sequence resets Outcome; preserve pre-MOVE POD only.
    if(CleanRefusal(out)&&!Current(&current,env.proof)){out.status="UNKNOWN";out.reason=62006;}
}
inline void GuardedExecute(const Request& r,const forward_diagnostic::Context& owner,Outcome& out) noexcept {
    __try {Execute(r,owner,out);}
    __except(out.gatewayActive?EXCEPTION_CONTINUE_SEARCH:EXCEPTION_EXECUTE_HANDLER){
        out.status="UNKNOWN";if(!out.exception)out.exception=GetExceptionCode();
        if(!out.reason)out.reason=62002;out.cleanupError=true;
    }
}
inline bool Read(const forward_diagnostic::Context& c,unsigned posted,Request& r) noexcept {
    wchar_t path[600]{};swprintf_s(path,L"%s\\shop-wndproc-request-%u.json",c.directory,posted);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;char text[1025]{};DWORD count=0;
    const bool read=ReadFile(file,text,1024,&count,nullptr)&&count&&count<1024;const BOOL closed=CloseHandle(file);
    return read&&closed&&!memchr(text,0,count)&&Parse(text,r);
}
inline bool Output(const forward_diagnostic::Context& c,const Request& r,const Outcome& out) noexcept {
    wchar_t path[600]{};char text[2048]{};char inputMarker[8]="null";char hoverUid[32]="null",bodyRaw[64]="null",bodyQuery[64]="null",effective[40]="null",preQuery[64]="null";
    if((out.attempted&&out.point.state!=PointState::Ready)||(!strcmp(out.status,"RETURNED")&&out.point.state!=PointState::Ready))return false;
    if(!ValidPoint(out.point)||!ValidHover(out.hover,out.attempted,out.returned,out.status)||!ValidBody(out.body,out.attempted,out.returned)||!ValidParticipation(out.participation,out.attempted,out.returned)||!ValidMouseAdmission(out.mouseAdmission,out.attempted,out.returned))return false;
    if(out.point.state==PointState::Ready){
        if(out.point.body!=r.bodyPoint||out.point.x<r.rect[0]||out.point.x>=r.rect[2]||out.point.y<r.rect[1]||out.point.y>=r.rect[3]||
           (!r.bodyPoint&&(out.point.x!=r.x||out.point.y!=r.y))||sprintf_s(effective,"[%d,%d]",out.point.x,out.point.y)<=0)return false;
        if(out.point.body&&sprintf_s(preQuery,"[%d,%d,%d,%d]",out.point.query[0],out.point.query[1],out.point.query[2],out.point.query[3])<=0)return false;
    }
    if(out.body.state==BodyState::Observed){
        if(sprintf_s(bodyRaw,"[%d,%d,%d,%d]",out.body.raw[0],out.body.raw[1],out.body.raw[2],out.body.raw[3])<=0||
           sprintf_s(bodyQuery,"[%d,%d,%d,%d]",out.body.query[0],out.body.query[1],out.body.query[2],out.body.query[3])<=0)return false;
    }
    if(out.hover.state==HoverState::Observed&&sprintf_s(hoverUid,"%llu",static_cast<unsigned long long>(out.hover.uid))<=0)return false;
    const bool fieldsKnown=out.participation.fields==ParticipationFields::Present||out.participation.fields==ParticipationFields::Incomplete;
    if(fieldsKnown&&sprintf_s(inputMarker,"%u",out.participation.marker)<=0)return false;
    const int n=sprintf_s(text,"{\"schema\":\"own-shop-whole-wndproc-result-v1\",\"pid\":%u,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"hwnd\":%llu,\"ui_thread\":%u,\"x\":%d,\"y\":%d,\"client_rect\":[%d,%d,%d,%d],\"window_dpi\":%u,\"player_uid\":%llu,\"expected_npc_uid\":%llu,\"point_source\":\"%s\",\"status\":\"%s\",\"reason\":%u,\"attempted_mask\":%u,\"returned_mask\":%u,\"cleanup_up\":%s,\"cleanup_error\":%s,\"exception_code\":%lu,\"fault_area\":%u,\"boundary_rva\":%u,\"unwind_proved\":%s,\"exception_address\":%llu,\"exception_access_address\":%llu,\"exception_operation\":%llu,\"registration_stage\":%u,\"hover_key0_state\":\"%s\",\"hover_key0_uid\":%s,\"body_state\":\"%s\",\"body_raw_rect\":%s,\"body_query_rect\":%s,\"point_state\":\"%s\",\"point_failure\":\"%s\",\"point_body_failure\":\"%s\",\"effective_point\":%s,\"pre_move_body_query\":%s,\"input_fields_state\":\"%s\",\"input_entry_marker\":%s,\"input_mouse_listener_present\":%s,\"input_dispatcher_present\":%s,\"input_pair_state\":\"%s\",\"window_mouse_route_snapshot\":\"%s\",\"view_mouse_admission_snapshot\":\"%s\",\"current_dispatcher_gate_snapshot\":\"%s\"}\n",
        r.pid,static_cast<unsigned long long>(r.birth),r.hash,r.seq,static_cast<unsigned long long>(r.hwnd),r.uiThread,r.x,r.y,
        r.rect[0],r.rect[1],r.rect[2],r.rect[3],r.dpi,static_cast<unsigned long long>(r.player),static_cast<unsigned long long>(r.expectedNpcUid),r.bodyPoint?"BODY":"EXPLICIT",out.status,out.reason,
        out.attempted,out.returned,out.cleanupUp?"true":"false",out.cleanupError?"true":"false",static_cast<unsigned long>(out.exception),
        out.faultArea,out.boundaryRva,out.unwindProved?"true":"false",static_cast<unsigned long long>(out.exceptionAddress),
        static_cast<unsigned long long>(out.exceptionAccess),static_cast<unsigned long long>(out.exceptionOperation),out.registrationStage,HoverName(out.hover.state),hoverUid,BodyName(out.body.state),bodyRaw,bodyQuery,PointName(out.point.state),PointFailureName(out.point.failure),BodyFailureName(out.point.bodyFailure),effective,preQuery,ParticipationFieldsName(out.participation.fields),inputMarker,
        fieldsKnown?(out.participation.listener?"true":"false"):"null",fieldsKnown?(out.participation.dispatcher?"true":"false"):"null",ParticipationPairName(out.participation.pair),
        WindowMouseRouteName(out.mouseAdmission.route),ViewMouseAdmissionName(out.mouseAdmission.viewport),CurrentDispatcherGateName(out.mouseAdmission.dispatcher));
    if(n<=0||n>=static_cast<int>(sizeof(text)))return false;
    swprintf_s(path,L"%s\\shop-wndproc-result-%u.json",c.directory,r.seq);
    HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;DWORD written=0;
    const bool ok=WriteFile(file,text,static_cast<DWORD>(n),&written,nullptr)&&written==static_cast<DWORD>(n)&&FlushFileBuffers(file);
    const BOOL closed=CloseHandle(file);return ok&&closed;
}
inline std::atomic<bool> closed{false}; // SHOP lifetime only; never an Exit/Quit authority.
struct ProcessIo {
    bool context(forward_diagnostic::Context& c) noexcept {return forward_diagnostic::context(c);}
    bool read(const forward_diagnostic::Context& c,unsigned seq,Request& r) noexcept {return Read(c,seq,r);}
    void execute(const Request& r,const forward_diagnostic::Context& c,Outcome& out) noexcept {GuardedExecute(r,c,out);}
    bool output(const forward_diagnostic::Context& c,const Request& r,const Outcome& out) noexcept {return Output(c,r,out);}
};
// Production Process uses this same control flow; test IO cannot confer runtime authority.
template<class Io>inline void ProcessWith(unsigned posted,bool payload,Io& io) noexcept {
    if(manual_move::terminal.load()||manual_move::sourceQuitTerminal.load())return;
    bool free=false;if(!manual_move::busy.compare_exchange_strong(free,true)){manual_move::terminal.store(true);return;}
    struct BusyScope{~BusyScope(){manual_move::busy.store(false);}} inFlight;
    forward_diagnostic::Context c{};
    if(!payload||!io.context(c)||!manual_move::SameOwner(c)||!manual_move::CorrectThread(c)){
        manual_move::terminal.store(true);return;
    }
    const unsigned previous=manual_move::lastSequence.load();if(posted<=previous)return;
    manual_move::lastSequence.store(posted);Request r{};Outcome out{};
    if(io.read(c,posted,r)&&Identity(r,c.pid,c.birth,OWN_EXPECTED_PROGRAM_SHA,posted,previous)){
        if(closed.load()){out.reason=62005;} // Valid new sequence consumed; no second execution.
        else io.execute(r,c,out);
    }
    else {manual_move::terminal.store(true);return;}
    forward_diagnostic::Context after{};
    if(!io.context(after)||!manual_move::SameOwner(after)||!manual_move::CorrectThread(after)){
        manual_move::terminal.store(true);return;
    }
    if(manual_move::terminal.load()){out.status="UNKNOWN";if(!out.reason)out.reason=62003;}
    if(CleanRefusal(out))closed.store(true);
    else if(strcmp(out.status,"RETURNED"))manual_move::terminal.store(true);
    if(!io.output(c,r,out))manual_move::terminal.store(true);
}
inline void Process(unsigned posted,bool payload) noexcept {ProcessIo io;ProcessWith(posted,payload,io);}
inline bool Handle(int code,WPARAM remove,LPARAM raw) noexcept {
    if(code<0||remove!=PM_REMOVE||!raw)return false;
    auto* msg=reinterpret_cast<MSG*>(raw);
    const UINT id=RegisterWindowMessageW(L"LC-Owned-ShopWholeWndProc-v1");
    if(!manual_move::Matches(code,remove,msg,id,autoOkWindow.load()))return false;
    const auto posted=msg->wParam;const bool payload=posted>0&&posted<=INT32_MAX&&msg->lParam==0;
    msg->message=WM_NULL;msg->wParam=0;msg->lParam=0;
    const DWORD error=GetLastError();Process(payload?static_cast<unsigned>(posted):0,payload);SetLastError(error);return true;
}
}
