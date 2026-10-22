#pragma once
#include "shop_wndproc_body_math.hpp"
namespace shop_wndproc_input {namespace body {
struct ClientPoint {bool available=false;int32_t x=0,y=0;};
// Pure derived convenience, NOT an original NPC center/selection/hit receipt.
// Inputs must already carry their source-qualified current roles. This file
// creates no roles; the source-bound NPC pre-MOVE caller supplies these inputs.
// Try exactly one midpoint and one signed truncation per coordinate; never
// search, clamp, retry, substitute another point, or issue input.
inline ClientPoint BodyClientPoint(const BodyObservation& observation,const MouseQueryInputs& mouse,
                                  const ViewInputs& view,const int32_t clientRect[4]) noexcept {
    const ClientPoint unknown{};
    if(observation.state!=BodyState::Observed||(mouse.role!=Type4Role::ProvenAbsent&&mouse.role!=Type4Role::QualifiedDirectB86C10&&mouse.role!=Type4Role::QualifiedCameraB57E20))return unknown;
    const auto* rect=observation.query;
    if(rect[0]>=rect[2]||rect[1]>=rect[3]||clientRect[0]>=clientRect[2]||clientRect[1]>=clientRect[3])return unknown;
    const float qx=Times(Plus(F(rect[0]),F(rect[2])),0.5f),qy=Times(Plus(F(rect[1]),F(rect[3])),0.5f);
    // F32 rounding can collapse a very narrow rectangle; no alternate seed.
    if(!std::isfinite(qx)||!std::isfinite(qy)||!(qx>F(rect[0])&&qx<F(rect[2])&&qy>F(rect[1])&&qy<F(rect[3])))return unknown;
    float mx=0,my=0,cx=0,cy=0;
    if(!QueryMouseCandidate(qx,qy,mouse,mx,my)||!NormalMouseClientCandidate(mx,my,view,cx,cy))return unknown;
    int32_t x=0,y=0;
    if(!Trunc(cx,x)||!Trunc(cy,y)||x< -32768||x>32767||y< -32768||y>32767||
       x<clientRect[0]||x>=clientRect[2]||y<clientRect[1]||y>=clientRect[3])return unknown;
    float actualX=0,actualY=0;
    if(!ClientToNormalMouse(x,y,view,mx,my)||!MouseToQuery(mx,my,mouse,actualX,actualY)||!Inside(rect,actualX,actualY))return unknown;
    return {true,x,y};
}
struct StoredMousePosition {double x=0,y=0;};
// Producer policy: preserve the verified midpoint unless the current Window's
// finite F64 pair is numerically equal in BOTH axes (including +/-0).
// Only then try clientX+1 once; no other seed/search/clamp or additional WM.
inline ClientPoint BodyClientPointChangedMove(const BodyObservation& observation,const MouseQueryInputs& mouse,
        const ViewInputs& view,const int32_t clientRect[4],const StoredMousePosition& stored) noexcept {
    const ClientPoint unknown{};
    if(!std::isfinite(stored.x)||!std::isfinite(stored.y))return unknown;
    const auto original=BodyClientPoint(observation,mouse,view,clientRect);
    if(!original.available||static_cast<double>(original.x)!=stored.x||static_cast<double>(original.y)!=stored.y)return original;
    if(original.x==32767)return unknown;
    const int32_t x=original.x+1,y=original.y;
    if(x<clientRect[0]||x>=clientRect[2]||y<clientRect[1]||y>=clientRect[3])return unknown;
    float mx=0,my=0,actualX=0,actualY=0;
    if(!ClientToNormalMouse(x,y,view,mx,my)||!MouseToQuery(mx,my,mouse,actualX,actualY)||
       !Inside(observation.query,actualX,actualY))return unknown;
    return {true,x,y};
}
}}
