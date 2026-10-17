#pragma once
// Pure policy and call seam. Host binds only reviewed source and live ownership.
#include <atomic>
#include <cstdint>
#include <cstring>
namespace original_move {
struct Identity {uint32_t pid=0,thread=0;uint64_t birth=0;uintptr_t hwnd=0,base=0;};
inline bool Same(const Identity& a,const Identity& b) noexcept {
    return a.pid==b.pid && a.thread==b.thread && a.birth==b.birth && a.hwnd==b.hwnd && a.base==b.base;
}
struct Plan {Identity owner;uint64_t uid=1;int32_t grid0=32571,grid1=32950,target0=32572,target1=32950;uint32_t direction=2,coordinateType=5;};
struct Observed {Identity owner;uint64_t uid=0;int32_t grid0=0,grid1=0;uintptr_t actor=0,controller=0,transform=0;bool land=false,idle=false,sourceVerified=false;};
enum class TileGate {Unknown,Blocked,ClearCandidate};
enum class Result {WrongMessage,Replay,InvalidPlan,OwnerChanged,WorldUnknown,TileUnknown,Blocked,ConstructorRefused,ChangedBeforeCall,CallUnknown,Returned};
struct Coordinate {int32_t segment0,segment1,grid0,grid1,local0,local1;float pixel0,pixel1,draw0,draw1;};
static_assert(sizeof(Coordinate)==40,"Source Coordinate40B ABI");
inline bool PlanValid(const Plan& p) noexcept {
    return p.owner.pid && p.owner.thread && p.owner.birth && p.owner.hwnd && p.owner.base && p.uid==1 &&
      p.grid0==32571 && p.grid1==32950 && p.target0==32572 && p.target1==32950 &&
      p.direction==2 && p.coordinateType==5;
}
inline bool WorldValid(const Plan& p,const Observed& o) noexcept {
    return Same(p.owner,o.owner) && o.uid==p.uid && o.grid0==p.grid0 && o.grid1==p.grid1 &&
      o.actor && o.controller && o.transform && o.land && o.idle && o.sourceVerified;
}
inline bool SameWorld(const Observed& a,const Observed& b) noexcept {
    return Same(a.owner,b.owner) && a.uid==b.uid && a.grid0==b.grid0 && a.grid1==b.grid1 &&
      a.actor==b.actor && a.controller==b.controller && a.transform==b.transform &&
      a.land==b.land && a.idle==b.idle && a.sourceVerified==b.sourceVerified;
}
class OneMove {
    std::atomic<bool> claimed{false};
public:
    // Engine: Observe, TileEvidenceFor, ConstructOriginal, InvokeOriginal.
    // An exact matching trigger consumes the single attempt even on refusal.
    template<class Engine> Result Run(const Plan& p,bool exactMessage,Engine& e) noexcept {
        if(!exactMessage)return Result::WrongMessage;
        if(claimed.exchange(true))return Result::Replay;
        if(!PlanValid(p))return Result::InvalidPlan;
        Observed first{};
        if(!e.Observe(first))return Result::WorldUnknown;
        if(!Same(p.owner,first.owner))return Result::OwnerChanged;
        if(!WorldValid(p,first))return Result::WorldUnknown;
        const auto tile=e.TileEvidenceFor(p,first);
        if(tile==TileGate::Unknown)return Result::TileUnknown;
        if(tile!=TileGate::ClearCandidate)return Result::Blocked;
        Coordinate target{};
        const uint64_t packed=(static_cast<uint64_t>(static_cast<uint32_t>(p.target1))<<32)|static_cast<uint32_t>(p.target0);
        if(!e.ConstructOriginal(target,packed,p.coordinateType) || target.grid0!=p.target0 || target.grid1!=p.target1 ||
          target.segment0!=(p.target0>>6)+0x7e00 || target.segment1!=(p.target1>>6)+0x7e00)return Result::ConstructorRefused;
        Observed last{};
        if(!e.Observe(last) || !WorldValid(p,last) || !SameWorld(first,last))return Result::ChangedBeforeCall;
        return e.InvokeOriginal(last.controller,target)?Result::Returned:Result::CallUnknown;
    }
};
}
