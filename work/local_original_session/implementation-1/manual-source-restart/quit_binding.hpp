#pragma once
// Only the explicit manual owner/UI-thread path calls this adapter. Internal
// quit_detail::Read and its desktop guard are neither copied nor bypassed.
#include "quit_source_anchors.hpp"
namespace source_quit { namespace binding {
#include "quit_lookup_anchors.hpp"
struct Path {void* buffer=nullptr;uint64_t unused=0,length=16,capacity=31;};
static_assert(sizeof(Path)==32,"run33 borrowed heap-string storage32B");
struct Proof {
    manual_move::Pins world{};
    uintptr_t base=0,root=0,gi=0,application=0,head=0,count=0;
    void* node=nullptr;void* button=nullptr;void* callable=nullptr;
    uintptr_t nodeTable=0,buttonTable=0;unsigned kind=0;
};
inline bool SamePair(Pair a,Pair b) noexcept {return a.object==b.object&&a.control==b.control;}
inline bool Same(const Proof& a,const Proof& b) noexcept {
    return a.kind==b.kind&&a.base==b.base&&a.root==b.root&&a.gi==b.gi&&a.application==b.application&&a.head==b.head&&a.count==b.count&&
        SamePair(a.world.ui,b.world.ui)&&SamePair(a.world.state,b.world.state)&&SamePair(a.world.scene,b.world.scene)&&
        SamePair(a.world.layout,b.world.layout)&&SamePair(a.world.actors,b.world.actors)&&
        a.node==b.node&&a.nodeTable==b.nodeTable&&a.button==b.button&&a.buttonTable==b.buttonTable&&a.callable==b.callable;
}
inline bool Image(uintptr_t at,size_t n,bool executable=false) noexcept {
    const auto b=scope.base;MEMORY_BASIC_INFORMATION m{};
    if(!b||at<b||n>OwnForwardLayout::ImageSize||at-b>OwnForwardLayout::ImageSize-n||
       VirtualQuery(reinterpret_cast<void*>(at),&m,sizeof(m))!=sizeof(m)||m.State!=MEM_COMMIT||m.Type!=MEM_IMAGE||
       reinterpret_cast<uintptr_t>(m.AllocationBase)!=b||(m.Protect&PAGE_GUARD)||(m.Protect&0xff)==PAGE_NOACCESS)return false;
    const auto low=reinterpret_cast<uintptr_t>(m.BaseAddress);const DWORD protection=m.Protect&0xff;
    return at>=low&&n<=m.RegionSize&&at-low<=m.RegionSize-n&&(!executable||
        protection==PAGE_EXECUTE_READ||protection==PAGE_EXECUTE_READWRITE||protection==PAGE_EXECUTE_WRITECOPY);
}
inline bool Table(uintptr_t table,uint32_t rva,uint32_t col,uint32_t td,size_t span) noexcept {
    const auto b=scope.base;
    return table==b+rva&&Image(table-8,span+8)&&*reinterpret_cast<uintptr_t*>(table-8)==b+col&&
        Image(b+col,24)&&*reinterpret_cast<uint32_t*>(b+col+12)==td;
}
template<class Query> inline bool ExecutableSourceAnchorWith(uintptr_t base,const internal_quit_source::Anchor& a,Query query) noexcept {
    if(!base||!a.size||a.size>sizeof(a.bytes)||a.rva>UINTPTR_MAX-base)return false;
    const auto at=base+a.rva;MEMORY_BASIC_INFORMATION region{};
    if(query(reinterpret_cast<void*>(at),&region,sizeof(region))!=sizeof(region)||
       region.State!=MEM_COMMIT||region.Type!=MEM_IMAGE||reinterpret_cast<uintptr_t>(region.AllocationBase)!=base||
       (region.Protect&PAGE_GUARD)||(region.Protect&0xff)==PAGE_NOACCESS)return false;
    const DWORD protection=region.Protect&0xff;
    if(protection!=PAGE_EXECUTE_READ&&protection!=PAGE_EXECUTE_READWRITE&&protection!=PAGE_EXECUTE_WRITECOPY)return false;
    const auto low=reinterpret_cast<uintptr_t>(region.BaseAddress);
    if(at<low||a.size>region.RegionSize||at-low>region.RegionSize-a.size)return false;
    return memcmp(reinterpret_cast<void*>(at),a.bytes,a.size)==0;
}
inline bool ExecutableSourceAnchor(uintptr_t base,const internal_quit_source::Anchor& a) noexcept {
    return ExecutableSourceAnchorWith(base,a,[](const void* at,MEMORY_BASIC_INFORMATION* region,size_t size) noexcept {
        return VirtualQuery(at,region,size);
    });
}
template<class LookupVerify,class SourceVerify> inline bool CodeGate(uintptr_t base,bool selected,uintptr_t forwardBase,unsigned kind,LookupVerify lookupVerify,SourceVerify sourceVerify) noexcept {
    if(!base||!selected||base!=forwardBase||(kind!=5&&kind!=6))return false;
    if(kind==5)for(const auto& a:lookupAnchors)if(!lookupVerify(base,a))return false;
    unsigned sourceCount=0;
    for(const auto& a:internal_quit_source::anchors)if(a.route==(kind==5?2u:3u)){
        ++sourceCount;
        if(!sourceVerify(base,a))return false;
    }
    return sourceCount!=0;
}
inline bool Code(unsigned kind) noexcept {
    return CodeGate(scope.base,scope.selectedReady.load(),forwardBinding.base.load(),kind,
        original_move::ExecutableAnchor,ExecutableSourceAnchor);
}
inline bool Alive(Pair p) noexcept {
    return AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object))&&AutoOkCanonical(reinterpret_cast<uintptr_t>(p.control))&&
        *reinterpret_cast<volatile LONG*>(static_cast<uint8_t*>(p.control)+8)>0;
}
inline bool Node(void* node,uintptr_t& table) noexcept {
    if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(node))||!*reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(node)+8))return false;
    table=*reinterpret_cast<uintptr_t*>(node);
    // Layout's source-owned Node may have a derived table; no guessed Node map.
    return Image(table,0x1e8)&&Image(*reinterpret_cast<uintptr_t*>(table),1,true)&&
        Image(*reinterpret_cast<uintptr_t*>(table+0x1e0),1,true);
}
inline bool Button(Proof& p) noexcept {
    const auto b=p.base;uintptr_t table=0;
    if(!Node(p.button,table)||!Table(table,0x1248740,0x136d6e8,0x1686de0,0x1e8))return false;
    p.buttonTable=table;p.callable=*reinterpret_cast<void**>(static_cast<uint8_t*>(p.button)+0x528);
    return AutoOkCanonical(reinterpret_cast<uintptr_t>(p.callable))&&
        Table(*reinterpret_cast<uintptr_t*>(p.callable),0x122f708,0x1359c20,0x17856d0,0x18)&&
        *reinterpret_cast<uintptr_t*>(b+0x122f708+0x10)==b+0xacbda0;
}
inline bool Layout(void* layout,unsigned kind) noexcept {
    const auto b=scope.base;const auto table=*reinterpret_cast<uintptr_t*>(layout);
    if(kind==6)return table==b+0x122f4d8&&Image(table,0xa0)&&*reinterpret_cast<uintptr_t*>(table+0x98)==b+0xacacf0;
    return Table(table,0x122f9a0,0x135a108,0x1785b98,0xa0)&&
        *reinterpret_cast<uintptr_t*>(table+0x98)==b+0xa11810&&
        *reinterpret_cast<uintptr_t*>(table+0x70)==b+0xacbb60&&*reinterpret_cast<uintptr_t*>(table+0x68)==b+0xa10b90;
}
inline bool Start(Proof& p,unsigned kind) {
    p.kind=kind;unsigned reason=0;if(!manual_move::OwnedNow())return false;
    if(kind==5&&!manual_move::Find(p.world,5,reason))return false;
    if(kind!=5&&kind!=6)return false;
    p.base=scope.base;p.root=*reinterpret_cast<uintptr_t*>(p.base+0x1668790);
    if(!AutoOkCanonical(p.root)||!*reinterpret_cast<uint8_t*>(p.root+0xd8))return false;
    p.gi=*reinterpret_cast<uintptr_t*>(p.root+0xd0);p.application=*reinterpret_cast<uintptr_t*>(p.base+0x17f0cf8);
    if(kind==6){
        uintptr_t begin=0;size_t count=0;if(!AutoOkCanonical(p.gi)||!original_move::Vector(p.gi+0x180,128,begin,count))return false;
        Pair ui{},state{};
        for(size_t i=0;i<count;++i){const Pair pair=*reinterpret_cast<Pair*>(begin+16*i);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
            const auto table=*reinterpret_cast<uintptr_t*>(pair.object);
            if(table==p.base+0x1182c50){if(ui.object)return false;ui=pair;}
            if(table==p.base+0x1182e30){if(state.object)return false;state=pair;}
        }
        if(!manual_move::Hold(ui,p.world.ui)||!manual_move::Hold(state,p.world.state))return false;
        const Pair scene=*reinterpret_cast<Pair*>(static_cast<uint8_t*>(state.object)+0x360);
        if(!manual_move::Hold(scene,p.world.scene)||!manual_move::Stable(p.world,6)||
           *reinterpret_cast<uintptr_t*>(scene.object)!=p.base+0x1188110||
           *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(scene.object)+0x10)!=6)return false;
    }
    auto* ui=static_cast<uint8_t*>(p.world.ui.object);p.head=*reinterpret_cast<uintptr_t*>(ui+0x350);p.count=*reinterpret_cast<uintptr_t*>(ui+0x358);
    if(!AutoOkCanonical(p.head)||!p.count||p.count>64)return false;
    auto at=*reinterpret_cast<uintptr_t*>(p.head);Pair found{};
    for(uintptr_t i=0;i<p.count;++i){if(!AutoOkCanonical(at)||at==p.head)return false;
        const Pair pair=*reinterpret_cast<Pair*>(at+0x30);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
        if(*reinterpret_cast<uintptr_t*>(pair.object)==p.base+(kind==5?0x122f9a0:0x122f4d8)){if(found.object)return false;found=pair;}
        at=*reinterpret_cast<uintptr_t*>(at);
    }
    if(at!=p.head||!manual_move::Hold(found,p.world.layout)||!Layout(found.object,kind))return false;
    if(kind==6){p.callable=*reinterpret_cast<void**>(static_cast<uint8_t*>(found.object)+0xf0);return true;}
    p.node=*reinterpret_cast<void**>(static_cast<uint8_t*>(found.object)+0x30);
    return Node(p.node,p.nodeTable);
}
inline bool Current(const Proof& p,bool bound) {
    const auto b=p.base;
    if(!manual_move::OwnedNow()||!b||b!=scope.base||forwardBinding.base.load()!=b||!scope.selectedReady.load()||
       *reinterpret_cast<uintptr_t*>(b+0x1668790)!=p.root||!*reinterpret_cast<uint8_t*>(p.root+0xd8)||
       *reinterpret_cast<uintptr_t*>(p.root+0xd0)!=p.gi||!manual_move::Stable(p.world,p.kind)||
       !Alive(p.world.ui)||!Alive(p.world.state)||!Alive(p.world.scene)||!Alive(p.world.layout))return false;
    if(*reinterpret_cast<uintptr_t*>(b+0x17f0cf8)!=p.application||!AutoOkCanonical(p.application)||
       *reinterpret_cast<uintptr_t*>(p.application)!=b+0x1181f78||
       *reinterpret_cast<uintptr_t*>(p.application+0x68)!=p.application||*reinterpret_cast<uint8_t*>(p.application+0x60))return false;
    // Rebind current subsystem pairs to this exact root registry, not just a held scene.
    uintptr_t begin=0;size_t size=0;if(!original_move::Vector(p.gi+0x180,128,begin,size))return false;
    unsigned uiMatches=0,stateMatches=0;
    for(size_t i=0;i<size;++i){const Pair pair=*reinterpret_cast<Pair*>(begin+16*i);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
        const auto table=*reinterpret_cast<uintptr_t*>(pair.object);
        if(table==b+0x1182c50){if(!SamePair(pair,p.world.ui))return false;++uiMatches;}
        if(table==b+0x1182e30){if(!SamePair(pair,p.world.state))return false;++stateMatches;}
    }
    if(uiMatches!=1||stateMatches!=1||*reinterpret_cast<uintptr_t*>(p.world.scene.object)!=b+(p.kind==5?0x1186f18:0x1188110)||
       *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(p.world.scene.object)+0x10)!=p.kind)return false;
    auto* ui=static_cast<uint8_t*>(p.world.ui.object);
    if(*reinterpret_cast<uintptr_t*>(ui+0x350)!=p.head||*reinterpret_cast<uintptr_t*>(ui+0x358)!=p.count)return false;
    auto at=*reinterpret_cast<uintptr_t*>(p.head);unsigned layouts=0;
    for(uintptr_t i=0;i<p.count;++i){if(!AutoOkCanonical(at)||at==p.head)return false;
        const Pair pair=*reinterpret_cast<Pair*>(at+0x30);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
        if(*reinterpret_cast<uintptr_t*>(pair.object)==b+(p.kind==5?0x122f9a0:0x122f4d8)){if(!SamePair(pair,p.world.layout))return false;++layouts;}
        at=*reinterpret_cast<uintptr_t*>(at);
    }
    uintptr_t nodeTable=0;
    if(at!=p.head||layouts!=1||!Layout(p.world.layout.object,p.kind))return false;
    if(p.kind==6){const auto layout=reinterpret_cast<uintptr_t>(p.world.layout.object);
        return p.callable==reinterpret_cast<void*>(layout+0xb8)&&*reinterpret_cast<void**>(layout+0xf0)==p.callable&&
            Image(b+0x122f590,0x18)&&*reinterpret_cast<uintptr_t*>(p.callable)==b+0x122f590&&
            *reinterpret_cast<uintptr_t*>(b+0x122f590+0x10)==b+0xacb2a0;
    }
    if(
       *reinterpret_cast<void**>(static_cast<uint8_t*>(p.world.layout.object)+0x30)!=p.node||
       !Node(p.node,nodeTable)||nodeTable!=p.nodeTable)return false;
    if(!bound)return true;
    Proof last=p;return Button(last)&&last.buttonTable==p.buttonTable&&last.callable==p.callable;
}
inline bool RetainNode(void* node) {
    auto& count=*reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(node)+8);
    if(!count||count==UINT32_MAX)return false;++count;return true;
}
inline void ReleaseNode(void* node) {
    if(!node)return;auto& count=*reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(node)+8);
    if(!count)RaiseException(0xe0510001,0,0,nullptr);
    if(--count==0){const auto table=*reinterpret_cast<uintptr_t*>(node);const auto target=*reinterpret_cast<uintptr_t*>(table);
        if(!Image(table,8)||!Image(target,1,true))RaiseException(0xe0510002,0,0,nullptr);
        using Destroy=void(__fastcall*)(void*,uint32_t);reinterpret_cast<Destroy>(target)(node,1);}
}
inline void* Allocate(size_t size) {using Call=void*(__fastcall*)(size_t);return reinterpret_cast<Call>(scope.base+0x3c020)(size);}
inline void Delete(void* pointer,size_t size) {using Call=void(__fastcall*)(void*,size_t);reinterpret_cast<Call>(scope.base+0xfa0d04)(pointer,size);}
inline void** Lookup(void** out,void** input,const Path* path) {
    using Call=void**(__fastcall*)(void**,void**,const Path*);return reinterpret_cast<Call>(scope.base+0xa56810)(out,input,path);
}
inline void* Cast(void* node) {
    using Call=void*(__fastcall*)(void*,int,void*,void*,int);
    return reinterpret_cast<Call>(scope.base+0xfa1ad3)(node,0,reinterpret_cast<void*>(scope.base+0x166ec80),reinterpret_cast<void*>(scope.base+0x1686de0),0);
}
inline void ReleasePins(const Proof& p) {
    Release(p.world.actors.control);Release(p.world.layout.control);Release(p.world.scene.control);Release(p.world.state.control);Release(p.world.ui.control);
}
inline void Command(const Proof& p) {
    // Existing stateless ACBDA0 whole-body machine ABI inference, not a new
    // formal C++ declaration. Actual bound callable selects this exact body.
    if(p.kind==5){using Call=void(__fastcall*)(void*,void*);reinterpret_cast<Call>(p.base+0xacbda0)(nullptr,nullptr);}
    else {using Call=void(__fastcall*)(void*);reinterpret_cast<Call>(p.base+0xacb2a0)(p.callable);}
}
struct Calls {
    bool(*owned)() noexcept=manual_move::OwnedNow;
    bool(*code)(unsigned) noexcept=Code;
    bool(*start)(Proof&,unsigned)=Start;
    bool(*current)(const Proof&,bool)=Current;
    bool(*button)(Proof&) noexcept=Button;
    bool(*retain)(void*)=RetainNode;
    void(*release)(void*)=ReleaseNode;
    void*(*allocate)(size_t)=Allocate;
    void(*deallocate)(void*,size_t)=Delete;
    void**(*lookup)(void**,void**,const Path*)=Lookup;
    void*(*cast)(void*)=Cast;
    void(*pins)(const Proof&)=ReleasePins;
    void(*command)(const Proof&)=Command;
};
struct Cells {void* root=nullptr;void* input=nullptr;void* output=nullptr;void* button=nullptr;Path path{};};
inline void ReleaseCell(void*& cell,const Calls& calls) {if(cell){calls.release(cell);cell=nullptr;}}
inline void Finish(Cells& cells,const Proof& p,const Calls& calls) {
    ReleaseCell(cells.output,calls);ReleaseCell(cells.input,calls);ReleaseCell(cells.root,calls);
    if(cells.path.buffer){calls.deallocate(cells.path.buffer,32);cells.path.buffer=nullptr;}
    ReleaseCell(cells.button,calls);calls.pins(p);
}
inline bool Capture(Proof& p,unsigned kind,const Calls& calls) {
    Cells cells{};const bool started=calls.start(p,kind);
    if(!started||terminal.load()||!calls.current(p,false)||!calls.owned()||!calls.code(kind)||terminal.load()){
        calls.pins(p);return false;
    }
    if(kind==6){calls.pins(p);return !terminal.load()&&calls.current(p,true);}
    cells.path.buffer=calls.allocate(32);
    if(!cells.path.buffer){calls.pins(p);return false;}
    memcpy(cells.path.buffer,"Root.Button_Quit",16);static_cast<char*>(cells.path.buffer)[16]=0;
    if(!calls.retain(p.node)){Finish(cells,p,calls);return false;}cells.root=p.node;
    if(!calls.retain(p.node)){Finish(cells,p,calls);return false;}cells.input=p.node;
    if(terminal.load()||!calls.current(p,false)||!calls.owned()||!calls.code(kind)||terminal.load()){
        Finish(cells,p,calls);return false;
    }
    void** const returned=calls.lookup(&cells.output,&cells.input,&cells.path);
    // A helper fault/contract mismatch is ambiguous: do not guess input/out
    // cleanup or apply caller EH metadata to this new adapter.
    if(returned!=&cells.output||cells.input)return false;
    if(terminal.load()||!calls.current(p,false)||!calls.owned()||!calls.code(kind)||terminal.load()){
        Finish(cells,p,calls);return false;
    }
    if(cells.output){
        cells.button=calls.cast(cells.output);
        if(cells.button&&!calls.retain(cells.button))return false;
        ReleaseCell(cells.output,calls);
    }
    ReleaseCell(cells.root,calls);
    calls.deallocate(cells.path.buffer,32);cells.path.buffer=nullptr;
    p.button=cells.button;
    // A borrowed final proof requires a source owner to remain when our typed
    // lease ends. A sole adapter-owned Button is released, never reused.
    const bool bound=p.button&&*reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(p.button)+8)>1&&calls.button(p)&&calls.current(p,true);
    Finish(cells,p,calls); // All adapter Node/strong leases end BEFORE final proof.
    return bound&&!terminal.load()&&calls.current(p,true);
}
inline Reply Boundary(unsigned kind,const Calls& calls,bool& attempted) {
    if(!calls.owned()||terminal.load())return {"UNKNOWN",2,false};
    if(!calls.code(kind))return {"CODE_ANCHOR_BLOCKED",12,false};
    Proof first{},last{};
    if(!Capture(first,kind,calls)||!Capture(last,kind,calls)||!Same(first,last))return {"UNKNOWN",6,false};
    if(!calls.current(last,true)||!calls.owned()||!calls.code(kind)||terminal.load())return {"UNKNOWN",6,false};
    attempted=true;calls.command(last);
    return {"RETURNED",0,true}; // No game object touch or lease release after call.
}
inline Reply Using(unsigned kind,const Calls& calls,bool& attempted) noexcept {
    try{return Boundary(kind,calls,attempted);}catch(...){return {"UNKNOWN",7,attempted};}
}
inline Reply GuardedUsing(unsigned kind,const Calls& calls) noexcept {
    bool attempted=false;
    __try{return Using(kind,calls,attempted);}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,attempted};}
}
inline Reply Native(const Request& r) noexcept {
    // Host MUST observe same-writer source Quit response drain before posting
    // Quit6Approval. This is a host contract, not native observation/evidence.
    const unsigned kind=r.phase==Phase::FirstLandQuit?5u:r.phase==Phase::Quit6Approval?6u:0u;
    return GuardedUsing(kind,Calls{});
}
} }
