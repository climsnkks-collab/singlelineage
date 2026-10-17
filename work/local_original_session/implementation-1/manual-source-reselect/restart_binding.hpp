#pragma once
namespace source_restart { namespace binding {
namespace shared=source_quit::binding;
using Path=shared::Path;
struct Proof {shared::Proof ui{};Pair network{};};
static constexpr original_move::Anchor anchors[]={
#include "restart_code_anchors.inc"
};
static constexpr uintptr_t networkMethods[]={
#include "restart_network_methods.inc"
};
static_assert(sizeof(networkMethods)/sizeof(networkMethods[0])==8,"accepted Network prefix64");
inline bool NetworkTable() noexcept {
    const auto base=scope.base;const auto table=base+0x1199d18;
    if(!shared::Image(table,64))return false;
    for(unsigned i=0;i<8;++i)if(*reinterpret_cast<uintptr_t*>(table+i*8)!=base+networkMethods[i])return false;
    return true;
}
enum CodeReason : unsigned {CodeContext=3072,CodeNetworkTable=3073,LookupBase=4096,SourceBase=8192,CodeStride=16};
static constexpr unsigned LookupCount=sizeof(shared::lookupAnchors)/sizeof(shared::lookupAnchors[0]);
static constexpr unsigned SourceCount=sizeof(anchors)/sizeof(anchors[0]);
static_assert(LookupCount==4 && SourceCount==116 && LookupBase+3*CodeStride+9==4153 &&
    SourceBase+115*CodeStride+9==10041 && CodeContext>2116 && SourceBase>4153,"fixed disjoint code reasons");
template<class Verify>
inline bool LiteralCode(uintptr_t base,unsigned& reason,Verify verify) noexcept {
    for(unsigned i=0;i<LookupCount;++i){unsigned clause=0;
        if(!verify(base,shared::lookupAnchors[i],clause)){reason=(clause==1 || (clause>=3 && clause<=10))?LookupBase+i*CodeStride+clause-1:12;return false;}}
    for(unsigned i=0;i<SourceCount;++i){unsigned clause=0;
        if(!verify(base,anchors[i],clause)){reason=(clause==1 || (clause>=3 && clause<=10))?SourceBase+i*CodeStride+clause-1:12;return false;}}
    return true;
}
inline bool Code(unsigned kind,unsigned& reason) noexcept {
    const auto base=scope.base;
    if(kind!=5 || !base || !scope.selectedReady.load() || forwardBinding.base.load()!=base){reason=CodeContext;return false;}
    if(!LiteralCode(base,reason,original_move::ExecutableAnchorObserved))return false;
    if(!NetworkTable()){reason=CodeNetworkTable;return false;}
    return true;
}
inline bool Same(const Proof& a,const Proof& b) noexcept {
    return shared::Same(a.ui,b.ui) && shared::SamePair(a.network,b.network);
}
inline bool CallerNetwork(Pair retained) noexcept {
    AcquireSRWLockShared(&scope.caller.lock);
    const bool same=shared::SamePair(scope.caller.network,retained);
    ReleaseSRWLockShared(&scope.caller.lock);
    return same; // Only pair fields are read under lock; no target read or call.
}
inline bool NetworkNow(const Proof& p,Pair& current) noexcept {
    if(!NetworkTable())return false;
    uintptr_t begin=0;size_t count=0;
    if(!original_move::Vector(p.ui.gi+0x180,128,begin,count))return false;
    for(size_t i=0;i<count;++i){const Pair pair=*reinterpret_cast<Pair*>(begin+i*16);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
        if(*reinterpret_cast<uintptr_t*>(pair.object)==p.ui.base+0x1199d18){
            if(current.object || !shared::Alive(pair))return false;current=pair;
        }
    }
    return current.object!=nullptr;
}
inline bool Button(shared::Proof& p) noexcept {
    uintptr_t table=0;const auto base=p.base;
    if(!shared::Node(p.button,table) || !shared::Table(table,0x1248740,0x136d6e8,0x1686de0,0x1e8))return false;
    p.buttonTable=table;p.callable=*reinterpret_cast<void**>(static_cast<uint8_t*>(p.button)+0x528);
    return AutoOkCanonical(reinterpret_cast<uintptr_t>(p.callable)) &&
        shared::Table(*reinterpret_cast<uintptr_t*>(p.callable),0x122f6d0,0x1359bf8,0x1785760,0x18) &&
        *reinterpret_cast<uintptr_t*>(base+0x122f6d0+0x10)==base+0xacbf10;
}
inline bool Start(Proof& p,unsigned kind) {
    if(kind!=5 || !shared::Start(p.ui,5))return false;
    Pair current{};
    return NetworkNow(p,current) && manual_move::Hold(current,p.network) && CallerNetwork(p.network);
}
inline bool Current(const Proof& p,bool bound) {
    if(!shared::Current(p.ui,false) || !shared::Alive(p.network))return false;
    Pair current{};
    if(!NetworkNow(p,current) || !shared::SamePair(current,p.network) || !CallerNetwork(p.network))return false;
    if(!bound)return true;
    shared::Proof last=p.ui;
    return source_restart::binding::Button(last) && last.buttonTable==p.ui.buttonTable && last.callable==p.ui.callable;
}
inline void Pins(const Proof& p) {Release(p.network.control);shared::ReleasePins(p.ui);}
inline void Command(const Proof& p) {
    // Accepted direct machine live-ins: neither incoming RCX nor RDX is read.
    // Bind the actual lambda2 first; preserve its whole original body/guards/leases.
    using Machine=void(__fastcall*)(void*,void*);
    reinterpret_cast<Machine>(p.ui.base+0xacbf10)(p.ui.callable,nullptr);
}
struct Calls {
    bool(*owned)() noexcept=manual_move::OwnedNow;
    bool(*code)(unsigned,unsigned&) noexcept=Code;
    bool(*start)(Proof&,unsigned)=Start;
    bool(*current)(const Proof&,bool)=Current;
    bool(*button)(shared::Proof&) noexcept=Button;
    bool(*retain)(void*)=shared::RetainNode;
    void(*release)(void*)=shared::ReleaseNode;
    void*(*allocate)(size_t)=shared::Allocate;
    void(*deallocate)(void*,size_t)=shared::Delete;
    void**(*lookup)(void**,void**,const Path*)=shared::Lookup;
    void*(*cast)(void*)=shared::Cast;
    void(*pins)(const Proof&)=Pins;
    void(*command)(const Proof&)=Command;
};
using Cells=shared::Cells;
inline void ReleaseCell(void*& cell,const Calls& calls) {if(cell){calls.release(cell);cell=nullptr;}}
inline void Finish(Cells& cells,const Proof& p,const Calls& calls) {
    ReleaseCell(cells.output,calls);ReleaseCell(cells.input,calls);ReleaseCell(cells.root,calls);
    if(cells.path.buffer){calls.deallocate(cells.path.buffer,32);cells.path.buffer=nullptr;}
    ReleaseCell(cells.button,calls);calls.pins(p);
}
inline bool Capture(Proof& p,const Calls& calls,unsigned& reason) {
    Cells cells{};cells.path.length=19;
    if(!calls.start(p,5) || terminal.load() || !calls.current(p,false) || !calls.owned() || !calls.code(5,reason) || terminal.load()){
        calls.pins(p);return false;
    }
    cells.path.buffer=calls.allocate(32);
    if(!cells.path.buffer){calls.pins(p);return false;}
    memcpy(cells.path.buffer,"Root.Button_Restart",19);static_cast<char*>(cells.path.buffer)[19]=0;
    if(!calls.retain(p.ui.node)){Finish(cells,p,calls);return false;}cells.root=p.ui.node;
    if(!calls.retain(p.ui.node)){Finish(cells,p,calls);return false;}cells.input=p.ui.node;
    if(terminal.load() || !calls.current(p,false) || !calls.owned() || !calls.code(5,reason) || terminal.load()){
        Finish(cells,p,calls);return false;
    }
    void** const returned=calls.lookup(&cells.output,&cells.input,&cells.path);
    // Same original Node8B input consume/zero and owned out contract as Quit.
    // Ambiguous helper fault/partial publication never authorizes guessed cleanup.
    if(returned!=&cells.output || cells.input)return false;
    if(terminal.load() || !calls.current(p,false) || !calls.owned() || !calls.code(5,reason) || terminal.load()){
        Finish(cells,p,calls);return false;
    }
    if(cells.output){
        cells.button=calls.cast(cells.output);
        if(cells.button && !calls.retain(cells.button))return false;
        ReleaseCell(cells.output,calls);
    }
    ReleaseCell(cells.root,calls);
    calls.deallocate(cells.path.buffer,32);cells.path.buffer=nullptr;
    p.ui.button=cells.button;
    const bool bound=p.ui.button && *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(p.ui.button)+8)>1 &&
        calls.button(p.ui) && calls.current(p,true);
    Finish(cells,p,calls); // All adapter leases end before the borrowed final proof.
    return bound && !terminal.load() && calls.current(p,true);
}
inline Reply Boundary(const Calls& calls,bool& attempted) {
    if(!calls.owned() || terminal.load())return {"UNKNOWN",2,false};
    unsigned reason=6;
    if(!calls.code(5,reason))return {"CODE_ANCHOR_BLOCKED",reason,false};
    Proof first{},last{};
    if(!Capture(first,calls,reason) || !Capture(last,calls,reason) || !Same(first,last))return {"UNKNOWN",reason,false};
    if(!calls.current(last,true) || !calls.owned() || !calls.code(5,reason) || terminal.load())return {"UNKNOWN",reason,false};
    attempted=true;calls.command(last);
    return {"RETURNED",0,true}; // No original object read/release after whole callback.
}
inline Reply Using(const Calls& calls,bool& attempted) noexcept {
    try{return Boundary(calls,attempted);}catch(...){return {"UNKNOWN",7,attempted};}
}
inline Reply GuardedUsing(const Calls& calls=Calls{}) noexcept {
    bool attempted=false;
    __try{return Using(calls,attempted);}
    __except(EXCEPTION_EXECUTE_HANDLER){return {"UNKNOWN",7,attempted};}
}
inline Reply Native(const Request& r) noexcept {
    return r.phase==Phase::LandRestart?GuardedUsing():Reply{"UNKNOWN",1,false};
}
} }
