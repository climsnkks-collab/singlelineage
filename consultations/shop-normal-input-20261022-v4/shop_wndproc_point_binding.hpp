#pragma once
// Included inside shop_wndproc_input. REA183 no-call scoped projection only.
// Raw pointers below are local and discarded before any original WM dispatch.
struct PointProjection {
    uint64_t signature[48]{};unsigned used=0;
    body::MouseQueryInputs mouse{};body::ViewInputs view{};body::StoredMousePosition stored{};
    bool Add(uint64_t value) noexcept {if(used==48)return false;signature[used++]=value;return true;}
    bool Same(const PointProjection& b) const noexcept {
        return used==b.used&&!memcmp(signature,b.signature,used*sizeof(uint64_t));
    }
};
template<class S,class T>inline bool PointRead(S& s,PointProjection& p,uintptr_t at,size_t offset,T& value) noexcept {
    if(!body::Read(s,at,offset,value))return false;
    uint64_t bits=0;static_assert(sizeof(T)<=8,"projection POD");memcpy(&bits,&value,sizeof(T));return p.Add(bits);
}
template<class S>inline bool ChildMember(S& s,PointProjection& p,uintptr_t parent,uintptr_t child) noexcept {
    uintptr_t begin=0,end=0,cap=0,back=0;
    if(!PointRead(s,p,parent,0x178,begin)||!PointRead(s,p,parent,0x180,end)||!PointRead(s,p,parent,0x188,cap)||
       end<begin||cap<end||(end-begin)%8||(cap-begin)%8||(end-begin)/8>4096||
       (end!=begin&&!body::Span(begin,0,end-begin))||!PointRead(s,p,child,0x190,back)||back!=parent)return false;
    uintptr_t foundAt=0;
    for(auto at=begin;at<end;at+=8){uintptr_t node=0;if(!body::Read(s,at,0,node))return false;if(node==child){foundAt=at;break;}}
    return foundAt&&p.Add(foundAt);
}
template<class S>inline bool ProjectPointRoles(S& s,uintptr_t w,uintptr_t host,uintptr_t hostView,PointProjection& p,PointFailure& failure) noexcept {
    failure=PointFailure::CurrentChanged;if(!s.Current())return false;
    failure=PointFailure::GOwner;
    const auto base=s.ImageBase();uintptr_t root=0,gi=0,g=0,self=0,begin=0,end=0;unsigned char ready=0;
    if(!PointRead(s,p,base,0x1668790,root)||!PointRead(s,p,root,0xd8,ready)||!ready||
       !PointRead(s,p,root,0xd0,gi)||!PointRead(s,p,base,0x1809d10,g)||
       !s.QualifiedPrimary(g,0x118b540)||!PointRead(s,p,g,8,self)||self!=g||
       !PointRead(s,p,gi,0x180,begin)||!PointRead(s,p,gi,0x188,end)||end<begin||(end-begin)%16||(end-begin)/16>128||
       !body::Span(begin,0,end-begin?end-begin:1))return false;
    body::Pair owner{};uintptr_t ownerAt=0;
    for(auto at=begin;at<end;at+=16){body::Pair pair{};if(!body::Read(s,at,0,pair))return false;
        if(pair.object==g){owner=pair;ownerAt=at;break;}}
    int32_t strong=0;
    if(!ownerAt||!body::Read(s,owner.control,8,strong)||strong<=0||!p.Add(ownerAt)||!p.Add(owner.control))return false;
    failure=PointFailure::Key4Profile;
    uintptr_t sentinel=0,buckets=0,node=0,first=0,k=0;uint64_t mask=0;
    if(!PointRead(s,p,g,0x118,sentinel)||!PointRead(s,p,g,0x128,buckets)||!PointRead(s,p,g,0x140,mask))return false;
    uint64_t hash=0xcbf29ce484222325ull;
    for(unsigned i=0;i<4;++i)hash=(hash^((4u>>(8*i))&255u))*0x100000001b3ull;
    const auto index=hash&mask;if(index>SIZE_MAX/16)return false;
    if(!PointRead(s,p,buckets,static_cast<size_t>(index)*16,first)||!PointRead(s,p,buckets,static_cast<size_t>(index)*16+8,node)||node==sentinel)return false;
    uintptr_t visited[512]{};unsigned used=0;bool found=false;
    for(unsigned n=0;n<512;++n){
        for(unsigned i=0;i<used;++i)if(visited[i]==node)return false;visited[used++]=node;
        int32_t key=0;if(!body::Read(s,node,0x10,key))return false;
        if(key==4){if(!PointRead(s,p,node,0x18,k)||!p.Add(node))return false;found=true;break;}
        if(node==first||!body::Read(s,node,8,node)||node==sentinel)return false;
    }
    if(!found||!s.QualifiedPrimary(k,0x1237fb0)||!s.QualifiedSlot(k,0xa8,0xb57e20))return false;
    failure=PointFailure::SceneOwner;
    uintptr_t scene=0,parent=0;
    if(!s.QualifiedPrimary(w,0x1186f18)||!PointRead(s,p,w,8,scene)||!s.QualifiedPrimary(scene,0x123ac90)||
       !PointRead(s,p,k,0x190,parent))return false;
    failure=PointFailure::ChildMembership;
    if(parent==scene){if(!ChildMember(s,p,scene,k))return false;}
    else if(!s.QualifiedPrimary(parent,0x1186f48)||!ChildMember(s,p,scene,parent)||!ChildMember(s,p,parent,k))return false;
    p.mouse.role=body::Type4Role::QualifiedCameraB57E20; // math profile only: direct Float2 is qualified above.
    // Concrete Camera B57E20 returns K+3C; never reuse B86C10's K+18 fields.
    failure=PointFailure::ViewMapping;
    if(!PointRead(s,p,g,0xd8,p.mouse.scale)||!PointRead(s,p,k,0x3c,p.mouse.offsetX)||!PointRead(s,p,k,0x40,p.mouse.offsetY))return false;
    if(!PointRead(s,p,hostView,0x20,p.view.ox)||!PointRead(s,p,hostView,0x24,p.view.oy)||
       !PointRead(s,p,hostView,0x50,p.view.sx)||!PointRead(s,p,hostView,0x54,p.view.sy)||!PointRead(s,p,hostView,0x68,p.view.zoomX))return false;
    p.view.zoomY=p.view.zoomX;unsigned char doubled=0;uint32_t kind=0;
    if(!PointRead(s,p,hostView,0x62,doubled)||!PointRead(s,p,hostView,0x64,kind))return false;
    p.view.doubled=doubled&&kind==1;
    // Same qualified GLFW Window, not View+B0/B4. No persistent raw pointer.
    if(!PointRead(s,p,host,0x1f8,p.stored.x)||!PointRead(s,p,host,0x200,p.stored.y)||
       !std::isfinite(p.stored.x)||!std::isfinite(p.stored.y))return false;
    failure=PointFailure::CurrentChanged;return s.Current();
}
template<class S>inline PointObservation DeriveBodyPoint(S& s,uintptr_t sceneLand,uintptr_t host,uintptr_t hostView,uint64_t uid,const int32_t rect[4]) noexcept {
    PointObservation unknown{};unknown.state=PointState::Unknown;
    PointProjection before{},after{};
    if(!s.Current()){unknown.failure=PointFailure::CurrentChanged;return unknown;}
    if(!ProjectPointRoles(s,sceneLand,host,hostView,before,unknown.failure))return unknown;
    const auto geometry=body::CachedBody(s,uid,&unknown.bodyFailure);
    unknown.failure=PointFailure::BodyCache;if(geometry.state!=BodyState::Observed)return unknown;
    unknown.failure=PointFailure::PointProjection;
    const auto point=body::BodyClientPointChangedMove(geometry,before.mouse,before.view,rect,before.stored);
    if(!point.available)return unknown;
    if(!ProjectPointRoles(s,sceneLand,host,hostView,after,unknown.failure))return unknown;
    unknown.failure=PointFailure::CurrentChanged;if(!before.Same(after)||!s.Current())return unknown;
    PointObservation result{};result.state=PointState::Ready;result.x=point.x;result.y=point.y;result.body=true;
    memcpy(result.query,geometry.query,sizeof(result.query));return result;
}
