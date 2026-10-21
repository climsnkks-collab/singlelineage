#pragma once
#include <cstdint>
#include <cstring>
namespace shop_wndproc_input {
enum class HoverState : unsigned {NotAttempted=0,Observed,Unknown};
struct HoverObservation {HoverState state=HoverState::NotAttempted;uint64_t uid=0;};
inline const char* HoverName(HoverState state) noexcept {
    switch(state){
    case HoverState::NotAttempted:return "NOT_ATTEMPTED";
    case HoverState::Observed:return "OBSERVED";
    case HoverState::Unknown:return "UNKNOWN";
    default:return nullptr;
    }
}
inline bool ValidHover(const HoverObservation& observation,unsigned attempted,unsigned returned,const char* status) noexcept {
    if(!HoverName(observation.state))return false;
    if(observation.state!=HoverState::Observed&&observation.uid)return false;
    if(observation.state!=HoverState::NotAttempted&&(!(attempted&1u)||!(returned&1u)))return false;
    return strcmp(status,"RETURNED")||observation.state!=HoverState::NotAttempted;
}
enum class BodyState : unsigned {NotAttempted=0,Observed,Unknown};
struct BodyObservation {BodyState state=BodyState::NotAttempted;int32_t raw[4]{},query[4]{};};
inline const char* BodyName(BodyState state) noexcept {
    switch(state){case BodyState::NotAttempted:return "NOT_ATTEMPTED";case BodyState::Observed:return "OBSERVED";
    case BodyState::Unknown:return "UNKNOWN";default:return nullptr;}
}
inline bool ValidBody(const BodyObservation& body,unsigned attempted,unsigned returned) noexcept {
    if(!BodyName(body.state))return false;
    if(body.state==BodyState::Observed||body.state==BodyState::Unknown){if(!(attempted&1u)||!(returned&1u))return false;}
    if(body.state!=BodyState::Observed)for(unsigned i=0;i<4;++i)if(body.raw[i]||body.query[i])return false;
    // BODY is additive and optional while role binder is unresolved. Neither
    // UNKNOWN nor NOT_ATTEMPTED changes the original sequence RETURNED policy.
    return true;
}
enum class PointState : unsigned {NotAttempted=0,Ready,Unknown};
enum class PointFailure : unsigned {None=0,GOwner,Key4Profile,SceneOwner,ChildMembership,BodyCache,ViewMapping,PointProjection,CurrentChanged};
struct PointObservation {PointState state=PointState::NotAttempted;PointFailure failure=PointFailure::None;int32_t x=0,y=0;bool body=false;int32_t query[4]{};};
inline const char* PointName(PointState s) noexcept {switch(s){case PointState::NotAttempted:return "NOT_ATTEMPTED";case PointState::Ready:return "READY";case PointState::Unknown:return "UNKNOWN";default:return nullptr;}}
inline const char* PointFailureName(PointFailure s) noexcept {switch(s){case PointFailure::None:return "NONE";case PointFailure::GOwner:return "G_OWNER";case PointFailure::Key4Profile:return "KEY4_PROFILE";case PointFailure::SceneOwner:return "SCENE_OWNER";case PointFailure::ChildMembership:return "CHILD_MEMBERSHIP";case PointFailure::BodyCache:return "BODY_CACHE";case PointFailure::ViewMapping:return "VIEW_MAPPING";case PointFailure::PointProjection:return "POINT_PROJECTION";case PointFailure::CurrentChanged:return "CURRENT_CHANGED";default:return nullptr;}}
inline bool ValidPoint(const PointObservation& p) noexcept {
    if(!PointName(p.state)||!PointFailureName(p.failure))return false;
    if(p.state==PointState::Unknown){if(p.failure==PointFailure::None)return false;}else if(p.failure!=PointFailure::None)return false;
    if(p.state==PointState::Ready){return p.x>=-32768&&p.x<=32767&&p.y>=-32768&&p.y<=32767&&(!p.body||(p.query[0]<p.query[2]&&p.query[1]<p.query[3]));}
    if(p.x||p.y||p.body)return false;for(auto v:p.query)if(v)return false;return true;
}
struct Outcome {
    const char* status="REFUSED";unsigned reason=62001;
    unsigned attempted=0,returned=0;bool cleanupUp=false,cleanupError=false;
    uint32_t exception=0;
    unsigned faultArea=0,boundaryRva=0;bool unwindProved=false;
    uint64_t exceptionAddress=0,exceptionAccess=0,exceptionOperation=0;
    unsigned registrationStage=0;
    HoverObservation hover{};
    BodyObservation body{};
    PointObservation point{};
    bool gatewayActive=false; // Adapter cleanup filter only; never a success bit.
};
// Only explicit pre-invocation refusals close SHOP without poisoning shared input.
inline bool CleanRefusal(const Outcome& o) noexcept {
    const bool reason=o.reason==62004 || o.reason==62005 || o.reason==7 || o.reason==8;
    const bool boundary=(o.reason==7 || o.reason==8)?
        (o.boundaryRva==0xef5480 || o.boundaryRva==0xef4647):o.boundaryRva==0;
    return !strcmp(o.status,"REFUSED") && reason && boundary && !o.attempted && !o.returned &&
        !o.cleanupUp && !o.cleanupError && !o.exception && !o.faultArea && !o.unwindProved &&
        !o.exceptionAddress && !o.exceptionAccess && !o.exceptionOperation && !o.registrationStage && !o.gatewayActive &&
        o.hover.state==HoverState::NotAttempted && !o.hover.uid &&
        o.body.state==BodyState::NotAttempted && ValidBody(o.body,0,0);
}
struct CallResult {
    unsigned reason=0;bool attempted=false,returned=false,post_current=false;
    uint32_t exception_code=0;bool current_return=false;
    unsigned fault_area=0,boundary_rva=0;bool unwind_proved=false;
    uint64_t exception_address=0,exception_access_address=0,exception_operation=0;
    unsigned registration_stage=0;
};
// Control-flow seam only. Production Env invokes the exact Daybreak whole
// WndProc gateway; tests supply scripted return metadata, never authority.
template<class Env>inline void Sequence(Env& env,Outcome& out) noexcept {
    out={};
    bool downSafe=false;
    for(unsigned index=0;index<3;++index){
        const auto call=env.Dispatch(index,false);
        if(call.attempted)out.attempted|=1u<<index;
        if(call.returned)out.returned|=1u<<index;
        if(!call.current_return||!call.returned||!call.post_current||call.reason||call.exception_code||call.fault_area||call.boundary_rva||call.registration_stage){
            out.status=out.attempted?"UNKNOWN":"REFUSED";
            out.reason=static_cast<unsigned>(call.reason);if(!out.reason)out.reason=62001;
            out.exception=call.exception_code;out.registrationStage=call.registration_stage;
            out.faultArea=call.fault_area;out.boundaryRva=call.boundary_rva;out.unwindProved=call.unwind_proved;
            out.exceptionAddress=call.exception_address;out.exceptionAccess=call.exception_access_address;
            out.exceptionOperation=call.exception_operation;
            // Never infer safe unwind from an attempted fault. Normal DOWN
            // return may require one UP when the primary stop was cancellation.
            // Env rechecks the original owner/scene/host/protection for cleanup.
            const bool needUp=downSafe && !call.attempted && !(out.attempted&4u) && !call.exception_code;
            if(needUp){
                const auto cleanup=env.Dispatch(2,true);
                out.cleanupUp=cleanup.attempted;
                if(cleanup.attempted)out.attempted|=4u;
                if(cleanup.returned)out.returned|=4u;
                out.cleanupError=!cleanup.current_return||!cleanup.returned||!cleanup.post_current||cleanup.exception_code||cleanup.registration_stage;
                if(!out.registrationStage)out.registrationStage=cleanup.registration_stage;
                // Preserve the first reason/exception, even if cleanup faults.
            }
            return;
        }
        if(index==1)downSafe=true;
    }
    out.status="RETURNED";out.reason=0;
}
}
