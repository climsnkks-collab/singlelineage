#pragma once
#include "shop_wndproc_sequence.hpp"
#include <cmath>
#include <cstring>
#include <climits>
namespace shop_wndproc_input {namespace body {
inline int32_t I32(uint32_t bits) noexcept {int32_t value;memcpy(&value,&bits,4);return value;}
inline int32_t Add(int32_t a,int32_t b) noexcept {return I32(static_cast<uint32_t>(a)+static_cast<uint32_t>(b));}
inline int32_t Sub(int32_t a,int32_t b) noexcept {return I32(static_cast<uint32_t>(a)-static_cast<uint32_t>(b));}
inline int32_t Mul(int32_t a,int32_t b) noexcept {return I32(static_cast<uint32_t>(a)*static_cast<uint32_t>(b));}
inline int32_t Neg(int32_t a) noexcept {return Sub(0,a);}
// Each operation is a source single-precision rounding boundary. /fp:strict
// is required by the actual Native build; no algebraic folding/FMA replacement.
inline float F(int32_t a) noexcept {volatile float r=static_cast<float>(a);return r;}
inline float Plus(float a,float b) noexcept {volatile float r=a+b;return r;}
inline float Minus(float a,float b) noexcept {volatile float r=a-b;return r;}
inline float Times(float a,float b) noexcept {volatile float r=a*b;return r;}
inline float Divide(float a,float b) noexcept {volatile float r=a/b;return r;}
inline float SignFlip(float a) noexcept {uint32_t bits;memcpy(&bits,&a,4);bits^=0x80000000u;memcpy(&a,&bits,4);return a;}
inline bool Trunc(float a,int32_t& out) noexcept {
    if(!std::isfinite(a)||a< -2147483648.0f||a>=2147483648.0f)return false;
    out=static_cast<int32_t>(a);return true;
}
inline float Min(float a,float b) noexcept {return a<b?a:b;}
inline float Max(float a,float b) noexcept {return a>b?a:b;}
struct TileGeometry {int32_t width=0,height=0;float offsetX=0,offsetY=0,scaleX=0,scaleY=0;};
struct TileAccumulator {
    int32_t minX=0xffffff,minY=0xffffff,maxX=I32(0xff000001u),maxY=I32(0xff000001u);
    unsigned count=0;
    bool AddTile(int32_t a,int32_t b) noexcept {
        const int32_t q=a/2,r=a%2;if(a<0)b=Sub(b,r);
        const int32_t x=Mul(Add(Add(q,r),b),48),y=Mul(Sub(b,q),24);
        const float fx=F(x),fy=F(y);
        if(!Trunc(Min(F(minX),fx),minX)||!Trunc(Max(F(maxX),Plus(fx,48.0f)),maxX)||
           !Trunc(Min(F(minY),fy),minY)||!Trunc(Max(F(maxY),Plus(fy,48.0f)),maxY))return false;
        ++count;return true;
    }
    bool Finish(TileGeometry& result) const noexcept {
        if(!count)return false;
        const int32_t w0=Sub(maxX,minX),h0=Sub(maxY,minY),k=Sub(h0,1);
        const float u=Times(F(w0),0.5f),v=Times(F(k),0.5f);int32_t tu=0,tv=0;
        if(!Trunc(u,tu)||!Trunc(v,tv))return false;
        const int32_t width=Add(w0,0.0f<Minus(u,F(tu))?1:0),height=Add(k,0.0f<Minus(v,F(tv))?1:0);
        if(!width||!height)return false;
        TileGeometry g{};g.width=width;g.height=height;g.offsetX=F(Neg(minX));g.offsetY=F(Neg(minY));
        g.scaleX=Divide(Plus(48.0f,g.offsetX),F(width));g.scaleY=Divide(SignFlip(Plus(g.offsetY,24.0f)),F(height));
        if(!std::isfinite(g.scaleX)||!std::isfinite(g.scaleY))return false;result=g;return true;
    }
};
inline bool RawRect(const int32_t s[4],const int32_t q[4],int32_t mode,const TileGeometry& g,int32_t result[4],int32_t& by) noexcept {
    int32_t p[4]{};for(unsigned i=0;i<4;++i)p[i]=mode==0?s[i]:mode==1?Add(s[i],q[i]):q[i];
    int32_t bx=0;
    if(!Trunc(Minus(g.offsetX,Times(F(g.width),g.scaleX)),bx)||
       !Trunc(Minus(SignFlip(g.offsetY),Times(F(g.height),g.scaleY)),by))return false;
    result[0]=Add(p[0],bx);result[1]=Sub(by,p[3]);result[2]=Add(bx,p[2]);result[3]=Sub(by,p[1]);return true;
}
inline bool QueryRect(const int32_t raw[4],float tx,float ty,int32_t out[4]) noexcept {
    if(!std::isfinite(tx)||!std::isfinite(ty))return false;
    for(unsigned i=0;i<4;++i)if(!Trunc(Plus(F(raw[i]),i%2?ty:tx),out[i]))return false;return true;
}
inline bool Inside(const int32_t rect[4],float x,float y) noexcept {
    int32_t ix=0,iy=0;return Trunc(x,ix)&&Trunc(y,iy)&&ix>=rect[0]&&ix<=rect[2]&&iy>=rect[1]&&iy<=rect[3];
}
// Pure source math only. Actual G/type4/View roles are NOT manufactured here.
enum class Type4Role {Unknown,ProvenAbsent,QualifiedDirectB86C10,QualifiedCameraB57E20};
struct MouseQueryInputs {Type4Role role=Type4Role::Unknown;float scale=0,offsetX=0,offsetY=0;};
inline bool MouseToQuery(float mouseX,float mouseY,const MouseQueryInputs& in,float& x,float& y) noexcept {
    if(!std::isfinite(mouseX)||!std::isfinite(mouseY)||in.role==Type4Role::Unknown)return false;
    float a=mouseX,b=mouseY;
    if(in.role==Type4Role::QualifiedDirectB86C10||in.role==Type4Role::QualifiedCameraB57E20){
        if(!std::isfinite(in.scale)||!std::isfinite(in.offsetX)||!std::isfinite(in.offsetY))return false;
        a=Plus(Times(in.scale,mouseX),in.offsetX);b=Plus(Times(in.scale,mouseY),in.offsetY);
    }
    int32_t ix=0,iy=0;if(!Trunc(a,ix)||!Trunc(b,iy))return false;
    x=Minus(F(ix),48.0f);y=F(iy);return true;
}
// 168 normal View algebra only. No Widget/Touch-world/Camera inverse or Y flip.
struct ViewInputs {float ox=0,oy=0,sx=0,sy=0,zoomX=0,zoomY=0;bool doubled=false;};
inline bool ClientToNormalMouse(int32_t x,int32_t y,const ViewInputs& v,float& mx,float& my) noexcept {
    if(!std::isfinite(v.ox)||!std::isfinite(v.oy)||!std::isfinite(v.sx)||!std::isfinite(v.sy)||
       !std::isfinite(v.zoomX)||!std::isfinite(v.zoomY)||!v.sx||!v.sy||!v.zoomX||!v.zoomY)return false;
    float a=Divide(F(x),v.zoomX),b=Divide(F(y),v.zoomY);
    if(v.doubled){a=Times(a,2.0f);b=Times(b,2.0f);}
    mx=Divide(Minus(a,v.ox),v.sx);my=Divide(Minus(b,v.oy),v.sy);return std::isfinite(mx)&&std::isfinite(my);
}
inline bool NormalMouseClientCandidate(float mx,float my,const ViewInputs& v,float& x,float& y) noexcept {
    if(!std::isfinite(mx)||!std::isfinite(my)||!std::isfinite(v.ox)||!std::isfinite(v.oy)||
       !std::isfinite(v.sx)||!std::isfinite(v.sy)||!std::isfinite(v.zoomX)||!std::isfinite(v.zoomY)||
       !v.sx||!v.sy||!v.zoomX||!v.zoomY)return false;
    const float a=Plus(v.ox,Times(v.sx,mx)),b=Plus(v.oy,Times(v.sy,my));
    x=Divide(Times(a,v.zoomX),v.doubled?2.0f:1.0f);y=Divide(Times(b,v.zoomY),v.doubled?2.0f:1.0f);
    return std::isfinite(x)&&std::isfinite(y);
}
inline bool QueryMouseCandidate(float qx,float qy,const MouseQueryInputs& in,float& mx,float& my) noexcept {
    if(!std::isfinite(qx)||!std::isfinite(qy)||in.role==Type4Role::Unknown)return false;
    if(in.role==Type4Role::ProvenAbsent){mx=Plus(qx,48.0f);my=qy;}
    else {if(!std::isfinite(in.scale)||!in.scale||!std::isfinite(in.offsetX)||!std::isfinite(in.offsetY))return false;
        mx=Divide(Minus(Plus(qx,48.0f),in.offsetX),in.scale);my=Divide(Minus(qy,in.offsetY),in.scale);}
    return std::isfinite(mx)&&std::isfinite(my);
}
// A candidate from either inverse is NOT a selected/quantized client point.
// The caller must bind roles and re-run client->mouse->query->Inside with its
// one explicit signed16 integer pair. No point production/override lives here.
}}
