#pragma once
// Original current-selector -> noncreating impl getter -> owned P/Q/X prefix.
// Actual whole Use function delegation; no listener timing or sender substitute.
namespace use_item { namespace owned_ui {
namespace shared=source_quit::binding;
enum Reason : unsigned {SlotStateLeaseUnknown=60,Prefix=61,Selector=62,SelectorType=63,
    VariantCall=64,VariantResult=65,ImplEntry=66,ImplCall=67,PcType=68,QOwner=69,
    ComponentCall=70,ComponentType=71,Cleanup=72,Changed=73,SlotPath=80,PathStorage=81,
    NodeLookup=82,NodeOutput=83,SlotTuple=84,UseEntry=85,DirectCodeBase=24000};
struct String32 {unsigned char storage[16]{};uint64_t length=0,capacity=0;};
struct Variant72 {String32 name{},resource{};uint32_t type=0,variant=0;};
struct Entry16 {uintptr_t link=0,entry=0;};
static_assert(sizeof(String32)==32 && sizeof(Variant72)==72 && sizeof(Entry16)==16,"accepted original storage ABI");
static constexpr original_move::Anchor directAnchors[]={
#include "owned_ui_code_anchors.inc"
#include "registered_selector_code_anchors.inc"
};
static constexpr original_move::Anchor dataAnchors[]={
#include "owned_ui_data_anchors.inc"
};
inline bool Span(uintptr_t at,size_t n) noexcept {
    return at>=0x10000 && at<=0x7fffffffffff && n && n-1<=0x7fffffffffff-at;
}
template<class T> inline bool Read(uintptr_t at,size_t offset,T& value) noexcept {
    return offset<=UINTPTR_MAX-at && Span(at+offset,sizeof(T)) &&
        SafeCopy(&value,reinterpret_cast<void*>(at+offset),sizeof(T));
}
inline bool Code(unsigned& reason,uint32_t target=0) noexcept {
    const auto base=scope.base;
    if(!base || !scope.selectedReady.load() || forwardBinding.base.load()!=base){reason=Prefix;return false;}
    uint32_t end=0;
    switch(target){
    case 0:break;
    case 0xa13b10:end=0xa13bfa;break;
    case 0xa0d5d0:end=0xa0d5ed;break;
    case 0xa08250:end=0xa0826d;break;
    case 0xb3a0b0:end=0xb3a17e;break;
    case 0xc52840:end=0xc52910;break;
    case 0x3c020:end=0x3c030;break; // accepted33 existing allocator prefix
    case 0xa56810:end=0xa56a82;break;
    case 0xa0c0b0:end=0xa0c1a4;break;
    default:reason=Prefix;return false;
    }
    uint32_t cursor=target;
    unsigned i=0;for(const auto& a:directAnchors){
        if(target && a.rva>=target && a.rva<end){
            if(a.rva!=cursor || a.size>end-cursor || !original_move::ExecutableAnchor(base,a)){
                reason=DirectCodeBase+i;return false;
            }
            cursor+=static_cast<uint32_t>(a.size);
        }
        ++i;
    }
    if(target && cursor!=end){reason=Prefix;return false;}
    for(const auto& a:dataAnchors)if(!binding::DataAnchor(base,a)){reason=DirectCodeBase+i;return false;}else ++i;
    return true;
}
inline bool CleanupCode() noexcept {
    uint32_t cursor=0x3be90;
    for(const auto& a:directAnchors)if(a.rva>=0x3be90 && a.rva<0x3bef1){
        if(a.rva!=cursor || a.size>0x3bef1-cursor || !original_move::ExecutableAnchor(scope.base,a))return false;
        cursor+=static_cast<uint32_t>(a.size);
    }
    return cursor==0x3bef1;
}
inline bool String(uintptr_t object,unsigned char* out,size_t max,size_t& length) noexcept {
    String32 s{};if(!Read(object,0,s) || s.length>max || s.capacity<s.length ||
        s.capacity>0x100000 || (s.capacity<16 && s.capacity!=15))return false;
    uintptr_t bytes=object;if(s.capacity>15)memcpy(&bytes,s.storage,sizeof(bytes));
    if(!Span(bytes,static_cast<size_t>(s.length)+1) ||
       !SafeCopy(out,reinterpret_cast<void*>(bytes),static_cast<size_t>(s.length)+1) || out[s.length])return false;
    length=static_cast<size_t>(s.length);return true;
}
inline bool Text(uintptr_t object,const char* wanted,size_t length) noexcept {
    unsigned char copy[129]{};size_t actual=0;
    return length<=128 && String(object,copy,128,actual) && actual==length && !memcmp(copy,wanted,length);
}
inline uint64_t Hash(const unsigned char* text,size_t n) noexcept {
    // accepted55 2B289..2B2C4 / accepted54 B5B37C..B5B3B4.
    uint64_t value=0xcbf29ce484222325ull;
    for(size_t i=0;i<n;++i)value=(value^text[i])*0x100000001b3ull;
    return value;
}
struct Map {uintptr_t sentinel=0,buckets=0,mask=0,first=0,last=0,entry=0;uint64_t hash=0;};
inline bool SameMap(const Map& a,const Map& b) noexcept {
    return a.sentinel==b.sentinel && a.buckets==b.buckets && a.mask==b.mask &&
        a.first==b.first && a.last==b.last && a.entry==b.entry && a.hash==b.hash;
}
// Exact read-only bucket walk from accepted55 2B26D..2B336. This is not a
// new owner: its original global/held-container UI-thread lifetime is required.
inline bool Find(uintptr_t sentinel,uintptr_t buckets,uintptr_t mask,
        const unsigned char* key,size_t length,Map& out) noexcept {
    out={};out.sentinel=sentinel;out.buckets=buckets;out.mask=mask;out.hash=Hash(key,length);
    if(!AutoOkCanonical(sentinel) || !AutoOkCanonical(buckets) || mask>0xfffff || (mask&(mask+1)))return false;
    const auto bucket=out.hash&mask;
    if(bucket>(UINTPTR_MAX-buckets)/16 || !Read(buckets+bucket*16,0,out.first) ||
       !Read(buckets+bucket*16,8,out.last))return false;
    if(out.last==sentinel)return true;
    if(!AutoOkCanonical(out.first))return false;
    auto at=out.last;
    for(unsigned visited=0;visited<128;++visited){
        if(!AutoOkCanonical(at) || at==sentinel)return false;
        unsigned char text[129]{};size_t size=0;
        if(!String(at+0x10,text,128,size))return false;
        if(size==length && !memcmp(text,key,length)){out.entry=at;return true;}
        if(at==out.first)return true;
        if(!Read(at,8,at))return false;
    }
    return false;
}
inline bool SelectorMap(Map& map) noexcept {
    uintptr_t sentinel=0,buckets=0,mask=0;const auto base=scope.base;
    return Read(base,0x1668868,sentinel) && Read(base,0x1668878,buckets) && Read(base,0x1668890,mask) &&
        Find(sentinel,buckets,mask,reinterpret_cast<const unsigned char*>("Inventory"),9,map);
}
inline bool ContainerMap(uintptr_t container,uintptr_t key,Map& map) noexcept {
    unsigned char text[129]{};size_t size=0;uintptr_t sentinel=0,buckets=0,mask=0;
    return String(key,text,128,size) && Read(container,8,sentinel) && Read(container,0x18,buckets) &&
        Read(container,0x30,mask) && Find(sentinel,buckets,mask,text,size,map);
}
inline bool ComponentMap(uintptr_t container,Map& map) noexcept {
    uintptr_t sentinel=0,buckets=0,mask=0;
    return Read(container,8,sentinel) && Read(container,0x18,buckets) && Read(container,0x30,mask) &&
        Find(sentinel,buckets,mask,reinterpret_cast<const unsigned char*>("UIDropSlotComponent"),19,map);
}
inline bool Typed(uintptr_t object,uint32_t table,uint32_t col,uint32_t td,size_t span) noexcept {
    uintptr_t actual=0;return Read(object,0,actual) && shared::Table(actual,table,col,td,span);
}
// Snapshot only values read by the existing SelectorFunction/Typed/Table chain.
// A failed stage never probes a later field, page or unknown callable.
struct SelectorTrace {
    unsigned step=0,observed=0;uintptr_t entry=0,active=0,table=0,col=0,invoke=0;uint32_t td=0;
};
struct SelectorSource {uint32_t table,col,td,target;};
inline constexpr SelectorSource pcSelector{0x1222a28,0x1349400,0x1771880,0xa0d5d0};
inline constexpr SelectorSource registeredSelector{0x1222140,0x1349008,0x1770c70,0xa08250};
inline const SelectorSource* SelectorFor(uintptr_t base,uintptr_t table) noexcept {
    if(table==base+pcSelector.table)return &pcSelector;
    if(table==base+registeredSelector.table)return &registeredSelector;
    return nullptr;
}
#ifdef OWN_SELECTED_HOST_TEST
inline bool(*testSelectorImage)(uintptr_t,size_t) noexcept=nullptr;
#endif
inline bool SelectorImage(uintptr_t at,size_t n) noexcept {
#ifdef OWN_SELECTED_HOST_TEST
    if(testSelectorImage)return testSelectorImage(at,n);
#endif
    return shared::Image(at,n);
}
inline bool SelectorFunction(const Map& map,uintptr_t& active,SelectorTrace* trace=nullptr,
        uint32_t* selected=nullptr) noexcept {
    SelectorTrace local{};auto& d=trace?*trace:local;d={};d.entry=map.entry;
    if(selected)*selected=0;
    d.step=1;if(!map.entry)return false;
    d.step=2;if(!Text(map.entry+0x10,"Inventory",9))return false;
    d.step=3;if(!Read(map.entry,0x68,active))return false;
    d.active=active;d.observed|=1;
    d.step=4;if(!Read(active,0,d.table))return false;d.observed|=2;
    d.step=5;const auto base=scope.base;const auto* source=SelectorFor(base,d.table);if(!source)return false;
    d.step=6;if(!SelectorImage(d.table-8,0x20))return false;
    d.step=7;d.col=*reinterpret_cast<uintptr_t*>(d.table-8);d.observed|=4;
    if(d.col!=base+source->col)return false;
    d.step=8;if(!SelectorImage(base+source->col,24))return false;
    d.step=9;d.td=*reinterpret_cast<uint32_t*>(base+source->col+12);d.observed|=8;
    if(d.td!=source->td)return false;
    d.step=10;if(!Read(scope.base,source->table+0x10,d.invoke))return false;d.observed|=16;
    d.step=11;if(d.invoke!=scope.base+source->target)return false;
    if(selected)*selected=source->target;
    d.step=12;return true;
}
inline void SelectorFailureBody(const Request& request,const SelectorTrace& d) noexcept {
    try {
    forward_diagnostic::Context context{};
    if(selected_diagnostic::valid_context(context)){
        char active[32]="null",table[32]="null",col[32]="null",td[32]="null",invoke[32]="null";
        if(d.observed&1)sprintf_s(active,"%llu",static_cast<unsigned long long>(d.active));
        if(d.observed&2)sprintf_s(table,"%llu",static_cast<unsigned long long>(d.table));
        if(d.observed&4)sprintf_s(col,"%llu",static_cast<unsigned long long>(d.col));
        if(d.observed&8)sprintf_s(td,"%u",d.td);
        if(d.observed&16)sprintf_s(invoke,"%llu",static_cast<unsigned long long>(d.invoke));
        char text[1024]{};
        const int n=sprintf_s(text,"{\"schema\":\"own-use-item-selector-source-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"reason\":63,\"invoked\":false,\"step\":%u,\"observed_mask\":%u,\"base\":%llu,\"entry\":%llu,\"active\":%s,\"vptr\":%s,\"col\":%s,\"td_rva\":%s,\"invoke\":%s}\n",
            context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,request.seq,
            d.step,d.observed,static_cast<unsigned long long>(scope.base),static_cast<unsigned long long>(d.entry),
            active,table,col,td,invoke);
        if(n>0)selected_diagnostic::output(context,L"use-item-selector-source-failure.json",text,n);
    }
    } catch(...) {}
}
inline void SelectorFailure(const Request& request,const SelectorTrace& d) noexcept {
    const DWORD before=GetLastError();
    __try {SelectorFailureBody(request,d);}
    __except(EXCEPTION_EXECUTE_HANDLER) {}
    SetLastError(before);
}
inline bool Pc(Pair p) noexcept {
    uintptr_t resource=0;
    return binding::Live(p) && Typed(reinterpret_cast<uintptr_t>(p.object),0x12228d8,0x1349c80,0x1771848,0x10) &&
        Typed(reinterpret_cast<uintptr_t>(p.control),0x1222a98,0x1349320,0x17717b0,0x10) &&
        Read(reinterpret_cast<uintptr_t>(p.control),0x10,resource) && resource==reinterpret_cast<uintptr_t>(p.object);
}
inline Variant72* Select(Variant72* out,const String32* key,uint32_t mode) {
    using Machine=Variant72*(__fastcall*)(Variant72*,const String32*,uint32_t);
    return reinterpret_cast<Machine>(scope.base+0xa13b10)(out,key,mode);
}
inline Pair* Existing(void* manager,Pair* out,const String32* key) {
    using Machine=Pair*(__fastcall*)(void*,Pair*,const String32*);
    return reinterpret_cast<Machine>(scope.base+0xb3a0b0)(manager,out,key);
}
inline Entry16* Component(void* container,Entry16* out,const String32* key,uint64_t hash) {
    using Machine=Entry16*(__fastcall*)(void*,Entry16*,const String32*,uint64_t);
    return reinterpret_cast<Machine>(scope.base+0xc52840)(container,out,key,hash);
}
inline void DestroyString(String32* value) {
    using Machine=void(__fastcall*)(String32*);reinterpret_cast<Machine>(scope.base+0x3be90)(value);
}
struct Flight {
    binding::Flight inventory{};binding::Lease pc{};Variant72 variant{};binding::Stage variantStage=binding::Stage::Empty;
    Map selector{},impl{},components{};uint32_t mode=0,selectorTarget=0;uintptr_t selectorActive=0,q=0,c=0,x=0;
    bool qHeld=false,xHeld=false,ambiguous=false;unsigned reason=Prefix;
    String32 path{};bool pathOwned=false;binding::Stage lookupStage=binding::Stage::Empty;
    void* input=nullptr;void* slot=nullptr;bool slotHeld=false,attempted=false;
    uintptr_t rawBegin=0,rawEnd=0,rawCapacity=0,candidate=0;
    std::array<uintptr_t,512> rawSlots{};size_t rawCount=0,pathLength=0;char pathText[256]{};
};
inline uintptr_t Manager(const Flight& f) noexcept {return reinterpret_cast<uintptr_t>(f.inventory.snapshot.world.ui.object);}
inline bool Current(const Request& r,Flight& f) noexcept {
    if(terminal.load() || !OwnedNow() || !binding::Current(r,f.inventory.snapshot,f.reason))return false;
    Map selector{};uintptr_t active=0;uint32_t mode=0,selectorTarget=0;
    if(!Read(Manager(f),0x328,mode) || mode!=f.mode || !SelectorMap(selector) || !SameMap(selector,f.selector) ||
       !SelectorFunction(selector,active,nullptr,&selectorTarget) || active!=f.selectorActive || selectorTarget!=f.selectorTarget)return false;
    if(f.pc.stage==binding::Stage::Returned){
        Map impl{};Pair pair{};uintptr_t q=0;
        if(!Pc(f.pc.pair) || !ContainerMap(Manager(f)+0x388,reinterpret_cast<uintptr_t>(&f.variant.name),impl) ||
           !SameMap(impl,f.impl) || !Read(impl.entry,0x30,pair) || !binding::Same(pair,f.pc.pair) ||
           !Read(reinterpret_cast<uintptr_t>(f.pc.pair.object),0x30,q) || (f.qHeld && q!=f.q))return false;
    }
    if(f.xHeld){
        Map components{};uintptr_t x=0,owner=0,c=0,table=0,target=0;uint32_t qCount=0,xCount=0;
        if(!shared::Node(reinterpret_cast<void*>(f.q),table) || !shared::Image(table,0x3e0) ||
           !Read(table,0x3d8,target) || target!=scope.base+0xb5b130 || !Read(f.q,8,qCount) || qCount<2 ||
           !Read(f.q,0x200,c) || c!=f.c || !Read(c,0x40,owner) || owner!=f.q ||
           !ComponentMap(c,components) || !SameMap(components,f.components) || !Read(components.entry,0x30,x) ||
           x!=f.x || !Typed(x,0x1217ab0,0x133bc98,0x16990e8,0x58) || !Read(x,0x10,owner) || owner!=f.q ||
           !Read(x,8,xCount) || xCount<2 || !Text(x+0x18,"UIDropSlotComponent",19))return false;
    }
    return true;
}
inline bool Variant(const Flight& f) noexcept {
    const bool alternative=f.mode==1;
    return f.variant.type==0x14 && f.variant.variant==(alternative?1u:0u) &&
        Text(reinterpret_cast<uintptr_t>(&f.variant.name),alternative?"Purple_InventoryLayout":"InventoryLayout",alternative?22:15) &&
        Text(reinterpret_cast<uintptr_t>(&f.variant.resource),alternative?"Purple_InventoryScene.csb":"InventoryScene.csb",alternative?25:18);
}
struct ModelTrace {
    unsigned step=0,observed=0;uintptr_t slot=0;Pair pair{};uint64_t uid=0;uint32_t kind=0;
};
struct UnsupportedPoint {
    unsigned step=0,check=0,observed=0,depth=0;uintptr_t node=0,at=0;uint64_t v0=0,v1=0,v2=0;
};
struct PathTrace {
    unsigned step=0,check=0,observed=0,depth=0,visited=0,matches=0;
    unsigned addressableMatches=0,unaddressableMatches=0;
    unsigned registered=0,modelRejected=0,empty=0,dotted=0,duplicate=0,bounded=0,unsupported=0;
    uintptr_t base=0,node=0,at=0;uint64_t v0=0,v1=0,v2=0;ModelTrace lastModel{};UnsupportedPoint firstUnsupported{};
};
inline void PathPoint(PathTrace& d,unsigned step,uintptr_t node=0,uintptr_t at=0,unsigned depth=0) noexcept {
    d.step=step;d.check=0;d.observed=0;d.node=node;d.at=at;d.depth=depth;d.v0=d.v1=d.v2=0;
}
#ifdef OWN_SELECTED_HOST_TEST
inline bool(*testPassiveTable)(uintptr_t,size_t) noexcept=nullptr;
#endif
inline bool PassiveTable(uintptr_t table) noexcept {
#ifdef OWN_SELECTED_HOST_TEST
    if(testPassiveTable)return testPassiveTable(table,0x200);
#endif
    return shared::Image(table,0x200);
}
// Path/Walk read the known Node* prefix; they call neither dtor nor child code.
// Authority is still the source-owned Q hierarchy/UI-thread borrow, not count.
inline bool PassiveNode(uintptr_t node,uintptr_t& table) noexcept {
    uint32_t count=0;
    return AutoOkCanonical(node) && Read(node,8,count) && count && Read(node,0,table) && PassiveTable(table);
}
// Range discovery uses exact 1F8. The read 1E0 target independently decides
// whether children have a source-supported named path from this parent.
inline bool ChildRoles(uintptr_t node,bool& named,PathTrace* trace=nullptr,unsigned step=2,unsigned depth=0) noexcept {
    named=false;PathTrace local{};auto& d=trace?*trace:local;PathPoint(d,step,node,0,depth);
    uintptr_t table=0,target=0;
    d.check=1;if(!PassiveNode(node,table))return false;
    d.v0=table;d.observed|=1;
    d.check=2;if(!Read(table,0x1e0,target))return false;d.v1=target;d.observed|=2;
    d.check=3;const bool knownLookup=target==scope.base+0xb58430;
    d.check=4;if(!Read(table,0x1f8,target))return false;d.v2=target;d.observed|=4;
    d.check=5;if(target!=scope.base+0x1498e0)return false;
    named=knownLookup;return true;
}
inline void RememberUnsupported(PathTrace& d) noexcept {
    if(!d.firstUnsupported.step)d.firstUnsupported={d.step,d.check,d.observed,d.depth,d.node,d.at,d.v0,d.v1,d.v2};
}
inline bool Registered(const Flight& f,uintptr_t node) noexcept {
    for(size_t i=0;i<f.rawCount;++i)if(f.rawSlots[i]==node)return true;
    return false;
}
inline bool AppendName(char* text,size_t used,const unsigned char* name,size_t length,size_t& next) noexcept {
    if(used>255 || !length || length>128 || memchr(name,'.',length) || used+length+(used?1:0)>255)return false;
    next=used+length+(used?1:0);
    if(used)text[used]='.';memcpy(text+used+(used?1:0),name,length);text[next]=0;return true;
}
inline bool UniqueName(uintptr_t begin,uintptr_t end,uintptr_t selected,
        const unsigned char* name,size_t length,bool& unique,PathTrace* trace=nullptr) noexcept {
    PathTrace local{};auto& d=trace?*trace:local;
    unique=true;
    for(auto other=begin;other<end;other+=8)if(other!=selected){
        uintptr_t sibling=0;unsigned char text[129]{};size_t size=0;
        d.at=other;d.observed=0;d.v0=d.v1=d.v2=0;
        d.check=1;if(!Read(other,0,sibling))return false;d.v0=sibling;d.observed|=1;
        d.check=2;if(!AutoOkCanonical(sibling))return false;
        d.check=3;if(!String(sibling+0x1a8,text,128,size))return false;d.v1=size;d.observed|=2;
        if(size==length && !memcmp(text,name,length)){unique=false;return true;}
    }
    return true;
}
// This field consumer is reached only after Model's unchanged exact Typed check.
// Host tests exercise scalars here without creating a Native/current proof.
inline bool ModelFields(const Request& r,uintptr_t slot,ModelTrace& d) noexcept {
    Pair model{};uint64_t uid=0;uint32_t kind=0;
    d.step=2;if(!Read(slot,0x808,model))return false;d.pair=model;d.observed|=1;
    d.step=3;if(!binding::Live(model))return false;
    d.step=4;if(!Read(reinterpret_cast<uintptr_t>(model.object),0,uid))return false;d.uid=uid;d.observed|=2;
    d.step=5;if(uid!=r.item)return false;
    d.step=6;if(!Read(reinterpret_cast<uintptr_t>(model.object),0xb0,kind))return false;d.kind=kind;d.observed|=4;
    d.step=7;if(kind!=2)return false;
    d.step=8;return true;
}
inline bool Model(const Request& r,uintptr_t slot,ModelTrace* trace=nullptr) noexcept {
    ModelTrace local{};auto& d=trace?*trace:local;d={};d.slot=slot;
    d.step=1;if(!Typed(slot,0x1232f30,0x135ee60,0x16895c0,0x1e8))return false;
    return ModelFields(r,slot,d);
}
inline bool RawSlots(Flight& f,bool capture,PathTrace* trace=nullptr) noexcept {
    PathTrace local{};auto& d=trace?*trace:local;PathPoint(d,1,f.x);
    uintptr_t begin=0,end=0,capacity=0;
    d.check=1;if(!Read(f.x,0x158,begin))return false;d.v0=begin;d.observed|=1;
    d.check=2;if(!Read(f.x,0x160,end))return false;d.v1=end;d.observed|=2;
    d.check=3;if(!Read(f.x,0x168,capacity))return false;d.v2=capacity;d.observed|=4;
    d.check=4;if(!AutoOkCanonical(begin))return false;
    d.check=5;if(end<begin)return false;
    d.check=6;if(capacity<end)return false;
    d.check=7;if(capacity>0x7fffffffffff)return false;
    d.check=8;if((end-begin)%8)return false;
    d.check=9;if((capacity-begin)%8)return false;
    d.check=10;if((end-begin)/8>f.rawSlots.size())return false;
    const auto count=static_cast<size_t>((end-begin)/8);
    d.check=11;if(!count)return false;
    d.check=12;if(!capture && (begin!=f.rawBegin || end!=f.rawEnd || capacity!=f.rawCapacity || count!=f.rawCount))return false;
    for(size_t i=0;i<count;++i){uintptr_t slot=0;d.at=begin+i*8;d.node=0;
        d.check=13;if(!Read(begin,i*8,slot))return false;d.node=slot;
        d.check=14;if(!AutoOkCanonical(slot))return false;
        if(capture)f.rawSlots[i]=slot;else {d.check=15;if(f.rawSlots[i]!=slot)return false;}
    }
    if(capture){f.rawBegin=begin;f.rawEnd=end;f.rawCapacity=capacity;f.rawCount=count;}
    return true;
}
// Only a successful Model can reach this scalar match classification.
inline bool NoteMatch(Flight& f,PathTrace& d,uintptr_t child,const char* text,size_t length,
        bool addressable,unsigned& matches) noexcept {
    ++matches;d.matches=matches;
    if(addressable)++d.addressableMatches;else ++d.unaddressableMatches;
    d.check=1;if(matches>1)return false;
    if(addressable){f.candidate=child;f.pathLength=length;memcpy(f.pathText,text,length+1);}
    return true;
}
// Same source-owned Q/UI-thread hierarchy borrow. Discovery reads only the
// exact 1F8=1498E0 header; no getter invocation/retain or source-name skipping.
// Addressability may become false at a name barrier and never recovers below it.
inline bool Walk(const Request& r,Flight& f,uintptr_t parent,char* text,size_t used,
        unsigned depth,unsigned& visited,unsigned& matches,PathTrace* trace=nullptr,bool addressable=true) noexcept {
    PathTrace local{};auto& d=trace?*trace:local;PathPoint(d,3,parent,0,depth);
    d.visited=visited;d.matches=matches;
    d.check=1;if(depth>=16)return false;
    d.check=2;++visited;d.visited=visited;if(visited>2048)return false;
    bool parentLookup=false;
    if(!ChildRoles(parent,parentLookup,&d,4,depth)){++d.unsupported;RememberUnsupported(d);return parent!=f.q;}
    uintptr_t begin=0,end=0;PathPoint(d,5,parent,0,depth);
    d.check=1;if(!Read(parent,0x178,begin))return false;d.v0=begin;d.observed|=1;
    d.check=2;if(!Read(parent,0x180,end))return false;d.v1=end;d.observed|=2;
    d.check=3;if(end<begin)return false;
    d.check=4;if((end-begin)%8)return false;
    d.check=5;if((end-begin)/8>512)return false;
    d.check=6;if((begin!=end) && !AutoOkCanonical(begin))return false;
    for(auto at=begin;at<end;at+=8){
        uintptr_t child=0;unsigned char name[129]{};size_t length=0;uint64_t hash=0;
        PathPoint(d,6,parent,at,depth);
        d.check=1;if(!Read(at,0,child))return false;d.v0=child;d.observed|=1;
        d.check=2;if(!AutoOkCanonical(child))return false;
        PathPoint(d,7,child,at,depth);
        d.check=1;if(!String(child+0x1a8,name,128,length))return false;d.v0=length;d.observed|=1;
        bool childAddressable=addressable && parentLookup;size_t next=used;
        if(!length){++d.empty;childAddressable=false;}
        else if(memchr(name,'.',length)){++d.dotted;childAddressable=false;}
        else {
            PathPoint(d,8,child,at,depth);
            d.check=1;if(!Read(child,0x1c8,hash))return false;d.v0=hash;d.observed|=1;
            const auto expected=Hash(name,length);d.v1=expected;d.observed|=2;
            d.check=2;if(hash!=expected)return false;
            bool unique=false;PathPoint(d,9,child,at,depth);
            if(!UniqueName(begin,end,at,name,length,unique,&d))return false;
            if(!unique){++d.duplicate;childAddressable=false;}
            if(childAddressable && !AppendName(text,used,name,length,next)){++d.bounded;childAddressable=false;}
        }
        // Once false, no descendant appends/copies a shortened fictional path.
        if(Registered(f,child)){
            ++d.registered;ModelTrace observedModel{};
            if(Model(r,child,&observedModel)){
                PathPoint(d,12,child,at,depth);
                if(!NoteMatch(f,d,child,text,next,childAddressable,matches))return false;
            }else{++d.modelRejected;d.lastModel=observedModel;}
        }
        if(!Walk(r,f,child,text,next,depth+1,visited,matches,&d,childAddressable))return false;
        text[used]=0;
    }
    return true;
}
inline bool NamedResult(Flight& f,PathTrace& d,unsigned visited,unsigned matches) noexcept {
    // Final summary has no failed child; lastModel remains a separate rejection.
    PathPoint(d,13);d.visited=visited;d.matches=matches;
    d.v0=matches;d.v1=f.candidate;d.v2=f.pathLength;d.observed=7;
    d.check=1;if(matches!=1)return false;
    d.check=4;if(d.addressableMatches!=1 || d.unaddressableMatches)return false;
    d.check=2;if(f.candidate==f.q)return false;
    d.check=3;return f.pathLength!=0;
}
inline bool Path(const Request& r,Flight& f,PathTrace* trace=nullptr) noexcept {
    PathTrace local{};auto& d=trace?*trace:local;d={};d.base=scope.base;
    if(!RawSlots(f,true,&d))return false;
    bool rootLookup=false;if(!ChildRoles(f.q,rootLookup,&d)){RememberUnsupported(d);return false;}
    char text[256]{};unsigned visited=0,matches=0;
    return Walk(r,f,f.q,text,0,0,visited,matches,&d,rootLookup) && NamedResult(f,d,visited,matches);
}
inline bool MakePath(Flight& f) {
    if(!f.pathLength || f.pathLength>255 || !Code(f.reason,0x3c020))return false;
    // Same original string32/allocator contract as accepted33: heap capacity+1,
    // cap>15 and below1000h. No foreign std::string allocator or guessed prefix.
    const auto capacity=(f.pathLength|size_t{15})<31?size_t{31}:(f.pathLength|size_t{15});
    void* buffer=shared::Allocate(capacity+1);if(!buffer)return false;
    memcpy(buffer,f.pathText,f.pathLength+1);memcpy(f.path.storage,&buffer,sizeof(buffer));
    f.path.length=f.pathLength;f.path.capacity=capacity;f.pathOwned=true;return true;
}
inline bool Tuple(const Request& r,Flight& f,uintptr_t& function) noexcept {
    const auto slot=reinterpret_cast<uintptr_t>(f.slot);uintptr_t listener=0,table=0,state=0,node=0,invoke=0;
    return f.slotHeld && slot==f.candidate && Model(r,slot) && Read(slot,0x528,listener) &&
        Read(listener,0,table) && table==scope.base+0x1217508 && shared::Image(table,0x18) &&
        Read(table,0x10,invoke) && invoke==scope.base+0x953890 && Read(listener,8,state) &&
        Read(state,0x88,node) && node==slot && Read(state,0x80,function) &&
        Typed(function,0x1222788,0x13491b8,0x17723c0,0x18) &&
        Read(scope.base,0x1222798,invoke) && invoke==scope.base+0xa0c0b0;
}
inline void Use(uintptr_t function,void** nodeStorage) {
    using Machine=void(__fastcall*)(void*,void**);
    reinterpret_cast<Machine>(scope.base+0xa0c0b0)(reinterpret_cast<void*>(function),nodeStorage);
}
inline bool AcquiredNode(Flight& f,void** returned) noexcept {
    if(f.lookupStage!=binding::Stage::Calling || returned!=&f.slot || f.input){
        f.lookupStage=binding::Stage::Ambiguous;f.ambiguous=true;return false;
    }
    f.lookupStage=binding::Stage::Returned;f.slotHeld=f.slot!=nullptr;return true;
}
inline void PathFailureBody(const Request& request,const PathTrace& d) noexcept {
    try {
    forward_diagnostic::Context context{};
    if(selected_diagnostic::valid_context(context)){
        char v0[32]="null",v1[32]="null",v2[32]="null",object[32]="null",control[32]="null",uid[32]="null",kind[32]="null";
        if(d.observed&1)sprintf_s(v0,"%llu",static_cast<unsigned long long>(d.v0));
        if(d.observed&2)sprintf_s(v1,"%llu",static_cast<unsigned long long>(d.v1));
        if(d.observed&4)sprintf_s(v2,"%llu",static_cast<unsigned long long>(d.v2));
        const auto& m=d.lastModel;
        if(m.observed&1){sprintf_s(object,"%llu",static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(m.pair.object)));
            sprintf_s(control,"%llu",static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(m.pair.control)));}
        if(m.observed&2)sprintf_s(uid,"%llu",static_cast<unsigned long long>(m.uid));
        if(m.observed&4)sprintf_s(kind,"%u",m.kind);
        const auto& first=d.firstUnsupported;
        char first0[32]="null",first1[32]="null",first2[32]="null";
        if(first.observed&1)sprintf_s(first0,"%llu",static_cast<unsigned long long>(first.v0));
        if(first.observed&2)sprintf_s(first1,"%llu",static_cast<unsigned long long>(first.v1));
        if(first.observed&4)sprintf_s(first2,"%llu",static_cast<unsigned long long>(first.v2));
        char text[2048]{};
        const int n=sprintf_s(text,"{\"schema\":\"own-use-item-path-source-v1\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"seq\":%u,\"reason\":80,\"invoked\":false,\"base\":%llu,\"step\":%u,\"check\":%u,\"observed_mask\":%u,\"node\":%llu,\"at\":%llu,\"v0\":%s,\"v1\":%s,\"v2\":%s,\"depth\":%u,\"visited\":%u,\"matches\":%u,\"addressable_matches\":%u,\"unaddressable_matches\":%u,\"registered\":%u,\"model_rejected\":%u,\"empty_skipped\":%u,\"dot_skipped\":%u,\"duplicate_skipped\":%u,\"bound_skipped\":%u,\"unsupported_branches\":%u,\"last_model_rejection\":{\"step\":%u,\"observed_mask\":%u,\"slot\":%llu,\"object\":%s,\"control\":%s,\"uid\":%s,\"kind\":%s},\"first_unsupported\":{\"step\":%u,\"check\":%u,\"observed_mask\":%u,\"node\":%llu,\"at\":%llu,\"depth\":%u,\"v0\":%s,\"v1\":%s,\"v2\":%s}}\n",
            context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,request.seq,
            static_cast<unsigned long long>(d.base),d.step,d.check,d.observed,static_cast<unsigned long long>(d.node),static_cast<unsigned long long>(d.at),v0,v1,v2,
            d.depth,d.visited,d.matches,d.addressableMatches,d.unaddressableMatches,d.registered,d.modelRejected,d.empty,d.dotted,d.duplicate,d.bounded,d.unsupported,
            m.step,m.observed,static_cast<unsigned long long>(m.slot),object,control,uid,kind,
            first.step,first.check,first.observed,static_cast<unsigned long long>(first.node),
            static_cast<unsigned long long>(first.at),first.depth,first0,first1,first2);
        if(n>0)selected_diagnostic::output(context,L"use-item-path-source-failure.json",text,n);
    }
    }catch(...){}
}
inline void PathFailure(const Request& request,const PathTrace& d) noexcept {
    const DWORD before=GetLastError();
    __try {PathFailureBody(request,d);}
    __except(EXCEPTION_EXECUTE_HANDLER){}
    SetLastError(before);
}
inline Reply Boundary(const Request& r,Flight& f) {
    if(terminal.load() || !OwnedNow())return {"UNKNOWN",2,false};
    if(!Code(f.reason))return {"CODE_ANCHOR_BLOCKED",f.reason,false};
    if(!binding::Capture(r,f.inventory.snapshot,f.reason))return {"REFUSED",f.reason,false};
    f.reason=Selector;
    if(!Read(Manager(f),0x328,f.mode) || !SelectorMap(f.selector) || !f.selector.entry)return {"REFUSED",f.reason,false};
    f.reason=SelectorType;SelectorTrace selectorTrace{};
    if(!SelectorFunction(f.selector,f.selectorActive,&selectorTrace,&f.selectorTarget)){
        SelectorFailure(r,selectorTrace);return {"REFUSED",f.reason,false};
    }
    f.reason=Changed;
    if(!Current(r,f) || !Code(f.reason,0xa13b10) || !Code(f.reason,f.selectorTarget))return {"REFUSED",f.reason,false};
    f.reason=VariantCall;f.variantStage=binding::Stage::Calling;
    auto* returned=Select(&f.variant,reinterpret_cast<const String32*>(f.selector.entry+0x10),f.mode);
    f.reason=VariantResult;
    if(returned!=&f.variant){f.variantStage=binding::Stage::Ambiguous;f.ambiguous=true;return {"UNKNOWN",f.reason,false};}
    f.variantStage=binding::Stage::Returned;
    if(!Variant(f))return {"REFUSED",f.reason,false};
    f.reason=Changed;if(!Current(r,f))return {"REFUSED",f.reason,false};
    f.reason=ImplEntry;Pair registered{};
    if(!ContainerMap(Manager(f)+0x388,reinterpret_cast<uintptr_t>(&f.variant.name),f.impl) || !f.impl.entry ||
       !Read(f.impl.entry,0x30,registered) || !Pc(registered))return {"REFUSED",f.reason,false};
    if(!Code(f.reason,0xb3a0b0))return {"CODE_ANCHOR_BLOCKED",f.reason,false};
    f.reason=ImplCall;f.pc.stage=binding::Stage::Calling;
    Pair* pcResult=Existing(reinterpret_cast<void*>(Manager(f)),&f.pc.pair,&f.variant.name);
    f.reason=PcType;
    if(!binding::Acquired(f.pc,pcResult)){f.ambiguous=true;return {"UNKNOWN",f.reason,false};}
    if(!binding::Same(f.pc.pair,registered) || !Pc(f.pc.pair))return {"UNKNOWN",f.reason,false};
    f.reason=Changed;if(!Current(r,f))return {"UNKNOWN",f.reason,false};
    f.reason=QOwner;uintptr_t table=0,target=0;
    if(!Read(reinterpret_cast<uintptr_t>(f.pc.pair.object),0x30,f.q) || !shared::Node(reinterpret_cast<void*>(f.q),table) ||
       !shared::Image(table,0x3e0) || !Read(table,0x3d8,target) || target!=scope.base+0xb5b130 ||
       !shared::RetainNode(reinterpret_cast<void*>(f.q)))return {"REFUSED",f.reason,false};
    f.qHeld=true;
    f.reason=ComponentCall;uintptr_t owner=0;
    if(!Read(f.q,0x200,f.c) || !Read(f.c,0x40,owner) || owner!=f.q || !ComponentMap(f.c,f.components) ||
       !f.components.entry)return {"REFUSED",f.reason,false};
    if(!Code(f.reason,0xc52840))return {"CODE_ANCHOR_BLOCKED",f.reason,false};
    Entry16 found{};
    auto* componentResult=Component(reinterpret_cast<void*>(f.c),&found,
        reinterpret_cast<const String32*>(f.components.entry+0x10),f.components.hash);
    if(componentResult!=&found){f.ambiguous=true;return {"UNKNOWN",f.reason,false};}
    f.reason=ComponentType;
    if(found.entry!=f.components.entry || !Read(found.entry,0x30,f.x) ||
       !Typed(f.x,0x1217ab0,0x133bc98,0x16990e8,0x58) || !Read(f.x,0x10,owner) || owner!=f.q ||
       !Text(f.x+0x18,"UIDropSlotComponent",19) || !shared::RetainNode(reinterpret_cast<void*>(f.x)))return {"REFUSED",f.reason,false};
    f.xHeld=true;
    f.reason=Changed;if(!Current(r,f))return {"UNKNOWN",f.reason,false};
    f.reason=SlotPath;PathTrace pathTrace{};
    if(!Path(r,f,&pathTrace)){PathFailure(r,pathTrace);return {"BLOCKED_SOURCE_BINDING",f.reason,false};}
    f.reason=PathStorage;if(!MakePath(f))return {"BLOCKED_SOURCE_BINDING",f.reason,false};
    f.reason=Changed;if(!Current(r,f) || !RawSlots(f,false))return {"UNKNOWN",f.reason,false};
    if(!Code(f.reason,0xa56810))return {"CODE_ANCHOR_BLOCKED",f.reason,false};
    f.reason=NodeLookup;
    if(!shared::RetainNode(reinterpret_cast<void*>(f.q)))return {"REFUSED",f.reason,false};
    f.input=reinterpret_cast<void*>(f.q);f.lookupStage=binding::Stage::Calling;
    void** output=shared::Lookup(&f.slot,&f.input,reinterpret_cast<const shared::Path*>(&f.path));
    f.reason=NodeOutput;
    if(!AcquiredNode(f,output))return {"UNKNOWN",f.reason,false};
    if(!f.slotHeld || reinterpret_cast<uintptr_t>(f.slot)!=f.candidate || !Model(r,f.candidate))return {"BLOCKED_SOURCE_BINDING",f.reason,false};
    f.reason=Changed;if(!Current(r,f) || !RawSlots(f,false))return {"UNKNOWN",f.reason,false};
    if(!Code(f.reason,0xa0c0b0))return {"CODE_ANCHOR_BLOCKED",f.reason,false};
    // Finish X's additional reference BEFORE the final holder borrow. This
    // release cannot enter a dtor while its original container owner remains.
    uint32_t xCount=0;if(!Read(f.x,8,xCount) || xCount<2)return {"UNKNOWN",Changed,false};
    void* ownedX=reinterpret_cast<void*>(f.x);f.xHeld=false;f.x=0;shared::ReleaseNode(ownedX);
    // From this point through entry: no original mutating/reentrant helper.
    // Read only current owned/borrowed fields under the same original UI thread.
    f.reason=Changed;if(!Current(r,f))return {"UNKNOWN",f.reason,false};
    f.reason=SlotTuple;uintptr_t function=0;
    if(!Tuple(r,f,function) || !OwnedNow())return {"BLOCKED_SOURCE_BINDING",f.reason,false};
    f.reason=UseEntry;f.attempted=true;Use(function,&f.slot);
    // No borrowed X/listener/state/function access after the invocation. RAX/RET
    // is not an ItemUse success bool; only normal completion is reported.
    return {"RETURNED",0,true};
}
inline bool ReleaseNode(void*& value) {
    if(!value)return true;
    // The closed prefix still has its original P/container owner. A sole
    // reference is an unresolved owner change, not permission for a new dtor.
    uint32_t count=0;if(!Read(reinterpret_cast<uintptr_t>(value),8,count) || count<2)return false;
    void* owned=value;value=nullptr;shared::ReleaseNode(owned);return true;
}
inline bool Clean(Flight& f) {
    if(f.ambiguous || f.pc.stage==binding::Stage::Calling || f.pc.stage==binding::Stage::Ambiguous ||
       f.variantStage==binding::Stage::Calling || f.variantStage==binding::Stage::Ambiguous ||
       f.lookupStage==binding::Stage::Calling || f.lookupStage==binding::Stage::Ambiguous)return false;
    if(f.slotHeld){
        uint32_t count=0;
        if(!Read(reinterpret_cast<uintptr_t>(f.slot),8,count) || !count)return false;
        // A56810's owned output may be the sole remaining reference after Use.
        // Consume exactly its authority, then use the original Node dtor ABI.
        void* owned=f.slot;f.slot=nullptr;f.slotHeld=false;shared::ReleaseNode(owned);
    }
    if(f.xHeld){void* x=reinterpret_cast<void*>(f.x);f.xHeld=false;if(!ReleaseNode(x))return false;}
    if(f.qHeld){void* q=reinterpret_cast<void*>(f.q);f.qHeld=false;if(!ReleaseNode(q))return false;}
    if(f.pc.stage==binding::Stage::Returned){
        if(f.pc.pair.control){LONG count=0;
            if(!Read(reinterpret_cast<uintptr_t>(f.pc.pair.control),8,count) || count<2)return false;
            const Pair owned=f.pc.pair;f.pc.pair={};f.pc.stage=binding::Stage::Released;binding::ReleasePair(owned);
        }else if(f.pc.pair.object)return false;
    }
    if(f.pathOwned){
        if(!CleanupCode() || f.path.capacity<31 || f.path.capacity>255 || f.path.length>f.path.capacity)return false;
        f.pathOwned=false;DestroyString(&f.path);
    }
    if(f.variantStage==binding::Stage::Returned){
        // Original A045C0 output uses cap15 or cap31. Restrict this adapter to
        // those proven normal allocations; never infer cleanup from partial bits.
        if(!CleanupCode())return false;
        for(auto* s:{&f.variant.resource,&f.variant.name}){
            unsigned char copy[32]{};size_t size=0;
            if((s->capacity!=15 && s->capacity!=31) || !String(reinterpret_cast<uintptr_t>(s),copy,31,size))return false;
        }
        f.variantStage=binding::Stage::Releasing;
        for(auto* s:{&f.variant.resource,&f.variant.name}){
            DestroyString(s);
        }
        f.variantStage=binding::Stage::Released;
    }
    return binding::Cleanup(f.inventory,binding::Calls{});
}
inline Reply Cpp(const Request& r,Flight& f) noexcept {
    try{return Boundary(r,f);}catch(...){terminal.store(true);return {"UNKNOWN",f.reason,f.attempted};}
}
inline Reply Guarded(const Request& r,Flight& f) noexcept {
    __try{return Cpp(r,f);}__except(EXCEPTION_EXECUTE_HANDLER){terminal.store(true);return {"UNKNOWN",f.reason,f.attempted};}
}
inline bool CppClean(Flight& f) noexcept {
    try{return Clean(f);}catch(...){return false;}
}
inline bool GuardedClean(Flight& f) noexcept {
    __try{return CppClean(f);}__except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline Reply Native(const Request& r) noexcept {
    Flight f{};Reply reply=Guarded(r,f);
    if(terminal.load())return !strcmp(reply.status,"RETURNED")?Reply{"UNKNOWN",9,f.attempted}:reply;
    if(!GuardedClean(f)){terminal.store(true);return {"UNKNOWN",f.ambiguous?f.reason:Cleanup,f.attempted};}
    if(strcmp(reply.status,"RETURNED") || !reply.invoked)terminal.store(true);
    return reply;
}
} }
