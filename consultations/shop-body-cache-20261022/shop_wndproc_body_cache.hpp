#pragma once
#include "shop_wndproc_body_math.hpp"
#include <cstddef>
namespace shop_wndproc_input {namespace body {
// ReadSection is an ALREADY-authorized nonmutating in-place borrow, not a
// source-issued boolean/lease. Required methods: Current/ImageBase/Actors,
// Read, QualifiedSlot, QualifiedPrimary, SelectedComponents. Production
// construction is deliberately absent until the original role binder is closed.
struct Pair {uintptr_t object=0,control=0;};
enum class Lookup {Unknown,Missing,Found};
inline bool Span(uintptr_t at,size_t offset,size_t n) noexcept {
    return at>=0x10000&&at<=0x7fffffffffff&&offset<=UINTPTR_MAX-at&&at+offset<=0x7fffffffffff&&n&&n-1<=0x7fffffffffff-(at+offset);
}
template<class S,class T>inline bool Read(S& s,uintptr_t at,size_t off,T& value) noexcept {return Span(at,off,sizeof(T))&&s.Read(at,off,value);}
template<class S>inline bool Vector(S& s,uintptr_t at,size_t bo,size_t eo,size_t stride,uintptr_t& begin,size_t& count) noexcept {
    uintptr_t end=0;if(!Read(s,at,bo,begin)||!Read(s,at,eo,end)||end<begin||(end-begin)%stride)return false;
    count=(end-begin)/stride;return count<=4096&&(!count||Span(begin,0,end-begin));
}
template<class S>inline bool Registry(S& s,uint64_t uid,Pair& actor) noexcept {
    const size_t offsets[3]={0x8a8,0x8c0,0x8d8};
    for(size_t offset:offsets){uintptr_t begin=0;size_t count=0;if(!Vector(s,s.Actors(),offset,offset+8,16,begin,count))return false;
        for(size_t i=0;i<count;++i){Pair p{};if(!Read(s,begin,i*16,p)||!p.object||!s.QualifiedSlot(p.object,8,0x40c00))return false;
            uint64_t actual=0;if(!Read(s,p.object,0x18,actual))return false;if(actual==uid){actor=p;return true;}}
    }return false;
}
template<class S>inline bool Components(S& s,uintptr_t actor,Pair& action,Pair& transform) noexcept {
    uintptr_t begin=0;size_t count=0;if(!Vector(s,actor,0x20,0x28,16,begin,count))return false;
    for(size_t i=0;i<count;++i){Pair p{};uintptr_t v=0;if(!Read(s,begin,i*16,p)||!Read(s,p.object,0,v))return false;
        if(v==s.ImageBase()+0x1180df0){if(action.object||!s.QualifiedPrimary(p.object,0x1180df0))return false;action=p;}
        if(v==s.ImageBase()+0x117ed38){if(transform.object||!s.QualifiedPrimary(p.object,0x117ed38))return false;transform=p;}
    }
    uintptr_t a=0,t=0;return action.object&&transform.object&&Read(s,action.object,8,a)&&Read(s,transform.object,8,t)&&a==actor&&t==actor&&
        s.SelectedComponents(actor,action.object,transform.object);
}
// Exact SPR only; original key460/fallback objects are outside this subset.
template<class S>inline Lookup Spr(S& s,int32_t key,uintptr_t& entry) noexcept {
    uintptr_t head=0,at=0;if(!Read(s,s.Actors(),0x908,head)||!Read(s,head,8,at))return Lookup::Unknown;
    uintptr_t candidate=head,visited[512]{};unsigned used=0;int32_t chosen=0;
    int64_t lower=static_cast<int64_t>(INT32_MIN)-1,upper=static_cast<int64_t>(INT32_MAX)+1;
    for(unsigned hops=0;hops<512;++hops){
        for(unsigned i=0;i<used;++i)if(visited[i]==at)return Lookup::Unknown;visited[used++]=at;
        unsigned char nil=0;if(!Read(s,at,0x19,nil))return Lookup::Unknown;
        if(nil){if(at!=head)return Lookup::Unknown;if(candidate==head)return Lookup::Missing;
            int32_t again=0;if(!Read(s,candidate,0x20,again)||again!=chosen)return Lookup::Unknown;
            if(again!=key)return Lookup::Missing;if(!Span(candidate,0x28,1))return Lookup::Unknown;entry=candidate+0x28;return Lookup::Found;}
        int32_t k=0;if(!Read(s,at,0x20,k)||k<=lower||k>=upper)return Lookup::Unknown;
        if(k<key){lower=k;if(!Read(s,at,0x10,at))return Lookup::Unknown;}
        else {upper=k;candidate=at;chosen=k;if(!Read(s,at,0,at))return Lookup::Unknown;}
    }return Lookup::Unknown;
}
template<class S>inline bool Action(S& s,uintptr_t spr,int32_t direction,int32_t subtype,uintptr_t& action) noexcept {
    uintptr_t begin=0;size_t count=0;const bool single=subtype==-1;
    if(!Vector(s,spr,single?0x10:0x28,single?0x18:0x30,0x28,begin,count))return false;
    for(size_t i=0;i<count;++i){const auto p=begin+i*0x28;int32_t d=0,t=0;if(!Read(s,p,0,d))return false;
        if(d!=direction)continue;if(!single){if(!Read(s,p,4,t))return false;if(t!=subtype)continue;}action=p;return true;}
    return false;
}
template<class S>inline bool Frame(S& s,uintptr_t owner,size_t bo,size_t eo,int32_t token,uintptr_t& frame) noexcept {
    uintptr_t begin=0;size_t count=0;if(!Vector(s,owner,bo,eo,48,begin,count)||token<0||static_cast<uint32_t>(token)>=count)return false;
    frame=begin+static_cast<size_t>(token)*48;return true;
}
inline uint64_t ResourceHash(int32_t k1,int32_t k2) noexcept {
    const uint32_t a=static_cast<uint32_t>(k1),b=static_cast<uint32_t>(k2);constexpr uint64_t seed=0xcbf29ce484222325ull,prime=0x100000001b3ull;
    uint64_t h1=seed,h2=seed;
    for(unsigned i=0;i<4;++i)h1=(h1^((a>>(8*i))&255u))*prime;
    for(unsigned i=0;i<3;++i)h2=(h2^((b>>(8*i))&255u))*prime;
    h2=(h2^((b>>24)&255u))*0x100000001b30000ull;return h1^h2;
}
template<class S>inline Lookup Cache(S& s,uintptr_t component,int32_t k1,int32_t k2,Pair& out) noexcept {
    const uintptr_t map=component+0x58;uintptr_t end=0,buckets=0;uint64_t mask=0;
    if(!Span(component,0x58,0x38)||!Read(s,map,8,end)||!Read(s,map,0x18,buckets)||!Read(s,map,0x30,mask))return Lookup::Unknown;
    const uint64_t index=ResourceHash(k1,k2)&mask;if(index>SIZE_MAX/16)return Lookup::Unknown;
    uintptr_t first=0,at=0;if(!Read(s,buckets,static_cast<size_t>(index)*16,first)||!Read(s,buckets,static_cast<size_t>(index)*16+8,at))return Lookup::Unknown;
    if(at==end)return Lookup::Missing;uintptr_t visited[512]{};unsigned used=0;
    for(unsigned hops=0;hops<512;++hops){
        for(unsigned i=0;i<used;++i)if(visited[i]==at)return Lookup::Unknown;visited[used++]=at;
        int32_t a=0,b=0;if(!Read(s,at,0x10,a)||!Read(s,at,0x14,b))return Lookup::Unknown;
        if(a==k1&&b==k2){if(!Read(s,at,0x18,out))return Lookup::Unknown;return Lookup::Found;}
        if(at==first)return Lookup::Missing;if(!Read(s,at,8,at)||at==end)return Lookup::Unknown;
    }return Lookup::Unknown;
}
template<class S>inline bool Child(S& s,uintptr_t resource,int32_t index,Pair& out) noexcept {
    uintptr_t begin=0;size_t count=0;if(!Vector(s,resource,0,8,16,begin,count))return false;
    if(!count){out={};return true;}
    const uint64_t unsignedIndex=static_cast<uint64_t>(static_cast<int64_t>(index));
    return Read(s,begin,(unsignedIndex<count?static_cast<size_t>(unsignedIndex):0)*16,out);
}
template<class S>inline bool Tiles(S& s,uintptr_t q,TileGeometry& out) noexcept {
    uintptr_t begin=0;size_t count=0;if(!Vector(s,q,0x10,0x18,16,begin,count)||!count)return false;
    TileAccumulator accumulator{};for(size_t i=0;i<count;++i){int32_t a=0,b=0;if(!Read(s,begin,i*16,a)||!Read(s,begin,i*16+4,b)||!accumulator.AddTile(a,b))return false;}
    return accumulator.Finish(out);
}
template<class S>inline BodyObservation CachedBody(S& s,uint64_t expectedUid) noexcept {
    BodyObservation unknown{};unknown.state=BodyState::Unknown;if(!s.Current())return unknown;
    Pair actor{},c{},transform{};if(!Registry(s,expectedUid,actor)||!Components(s,actor.object,c,transform))return unknown;
    uintptr_t d=0;if(!Read(s,c.object,0xc0,d)||!d||!s.QualifiedSlot(d,0x18,0x8f8f0))return unknown;
    int32_t d10=0,d14=0,d18=0,token=0,sprKey=0,c40=0;unsigned char c48=0,e1=0,over=0;
    if(!Read(s,d,0x10,d10)||!Read(s,d,0x14,d14)||!Read(s,d,0x18,d18)||!Read(s,d,0x20,token)||
       !Read(s,c.object,0x3c,sprKey)||!Read(s,c.object,0x40,c40)||!Read(s,c.object,0x48,c48)||!Read(s,c.object,0xe1,e1)||!Read(s,c.object,0x10c,over))return unknown;
    uintptr_t spr=0,action=0,frame=0,componentFrame=0;
    if(Spr(s,sprKey,spr)!=Lookup::Found||!Action(s,spr,d10,d14,action)||!Frame(s,action,0x10,0x18,token,frame)||!Frame(s,c.object,0xe8,0xf0,token,componentFrame))return unknown;
    int32_t childIndex=0,k1=0,k2=0,primary=0;
    if(!Read(s,frame,4,childIndex)||!Read(s,spr,0xc,k1)||!Read(s,spr,0,primary)||!Read(s,componentFrame,0,k2))return unknown;
    if(k1<=0)k1=primary;if(k2==-1)k2=c40;if(c48)k2=0;else if(e1)k2=Add(k2,d18);
    Pair resource{},q{};if(Cache(s,c.object,k1,k2,resource)!=Lookup::Found||!resource.object||!Child(s,resource.object,childIndex,q)||!q.object)return unknown;
    TileGeometry geometry{};if(!Tiles(s,q.object,geometry))return unknown;
    int32_t mode=0,shape[4]{},childRect[4]{};const uintptr_t source=over?c.object:spr;const size_t mo=over?0x110:0xe0,so=over?0x114:0xe4;
    if(!Read(s,source,mo,mode))return unknown;for(unsigned i=0;i<4;++i)if(!Read(s,source,so+4*i,shape[i])||!Read(s,q.object,4*i,childRect[i]))return unknown;
    BodyObservation result{};int32_t by=0;if(!RawRect(shape,childRect,mode,geometry,result.raw,by))return unknown;
    const int32_t diff=Sub(d10,c40);
    if(diff!=0&&diff<5){uintptr_t baseAction=0,firstFrame=0;int32_t firstKey=0;
        if(!Action(s,spr,c40,-1,baseAction)||!Frame(s,baseAction,0x10,0x18,0,firstFrame)||!Read(s,firstFrame,0,firstKey))return unknown;
        Pair correction{};const auto found=Cache(s,c.object,k1,Add(firstKey,d18),correction);
        if(found==Lookup::Unknown)return unknown;if(found==Lookup::Found&&correction.object){Pair child{};
            if(!Child(s,correction.object,0,child))return unknown;if(child.object){int32_t top=0;if(!Read(s,child.object,4,top))return unknown;
                const int32_t bottom=Add(Sub(by,top),5);if(result.raw[3]>bottom)result.raw[3]=bottom;}}
    }
    float tx=0,ty=0;if(!Read(s,transform.object,0x50,tx)||!Read(s,transform.object,0x54,ty)||!QueryRect(result.raw,tx,ty,result.query)||!s.Current())return unknown;
    uintptr_t sameD=0;int32_t sameToken=0;
    if(!Read(s,c.object,0xc0,sameD)||sameD!=d||!Read(s,d,0x20,sameToken)||sameToken!=token)return unknown;
    result.state=BodyState::Observed;return result;
}
// Conditional existing-key4 path only. G's role and K's raw child lifetime
// must be covered by the SAME caller-supplied ReadSection; no accessor/insertion.
template<class S>inline bool ExistingType4(S& s,uintptr_t g,MouseQueryInputs& out) noexcept {
    if(!s.Current()||!s.CurrentG(g))return false;
    uintptr_t end=0,buckets=0;uint64_t mask=0;
    if(!Read(s,g,0x118,end)||!Read(s,g,0x128,buckets)||!Read(s,g,0x140,mask))return false;
    uint64_t h=0xcbf29ce484222325ull;const uint32_t key=4;
    for(unsigned i=0;i<4;++i)h=(h^((key>>(8*i))&255u))*0x100000001b3ull;
    const uint64_t index=h&mask;if(index>SIZE_MAX/16)return false;
    uintptr_t first=0,atNode=0;if(!Read(s,buckets,static_cast<size_t>(index)*16,first)||!Read(s,buckets,static_cast<size_t>(index)*16+8,atNode))return false;
    bool found=false;uintptr_t k=0,visited[512]{};unsigned used=0;
    if(atNode!=end)for(unsigned hops=0;hops<512;++hops){
        for(unsigned i=0;i<used;++i)if(visited[i]==atNode)return false;visited[used++]=atNode;
        int32_t current=0;if(!Read(s,atNode,0x10,current))return false;
        if(current==4){if(!Read(s,atNode,0x18,k))return false;found=true;break;}
        if(atNode==first){found=true;k=0;break;}if(!Read(s,atNode,8,atNode)||atNode==end)return false;
    }
    else found=true;
    if(!found)return false;MouseQueryInputs result{};
    if(!k)result.role=Type4Role::ProvenAbsent;
    else {if(!s.QualifiedSlot(k,0xa8,0xb86c10)||!Read(s,g,0xd8,result.scale)||!Read(s,k,0x18,result.offsetX)||!Read(s,k,0x1c,result.offsetY))return false;
        if(!std::isfinite(result.scale)||!std::isfinite(result.offsetX)||!std::isfinite(result.offsetY))return false;result.role=Type4Role::QualifiedDirectB86C10;}
    if(!s.Current()||!s.CurrentG(g))return false;out=result;return true;
}
}}
