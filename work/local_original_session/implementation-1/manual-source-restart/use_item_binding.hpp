#pragma once
namespace use_item { namespace binding {
static constexpr original_move::Anchor codeAnchors[]={
#include "use_item_code_anchors.inc"
};
static constexpr unsigned CodeLiteralCount=static_cast<unsigned>(sizeof(codeAnchors)/sizeof(codeAnchors[0]));
static constexpr unsigned CodeLiteralLast=CodeLiteralBase+CodeLiteralCount-1;
static_assert(CodeLiteralCount==150 && CodeLiteralLast==1173 && CodeLiteralLast<=UINT32_MAX,"fixed literal index range");
template<class Verify>
inline bool CodeLiteralReady(uintptr_t base,unsigned& reason,Verify verify) noexcept {
    unsigned index=0;
    for(const auto& anchor:codeAnchors){
        unsigned failure=0;
        if(!verify(base,anchor,failure)){
            if(index==0 && failure>=original_move::AnchorState && failure<=original_move::AnchorNoAccess)
                reason=FirstAnchorAttributeBase+failure-original_move::AnchorState;
            else reason=index==0 && failure>=original_move::AnchorQuery && failure<=original_move::AnchorBytes?
                    FirstAnchorStageBase+failure-1:CodeLiteralBase+index;
            return false;
        }
        ++index;
    }
    return true;
}
inline bool VerifyCodeAnchor(uintptr_t base,const original_move::Anchor& anchor,unsigned& failure) noexcept {
    if(&anchor==&codeAnchors[0])return original_move::ExecutableAnchorObserved(base,anchor,failure);
    return original_move::ExecutableAnchor(base,anchor);
}
static constexpr original_move::Anchor dataAnchors[]={
#include "use_item_data_anchors.inc"
};
struct TableAnchor {uint32_t rva,count;uintptr_t slots[3];};
static constexpr TableAnchor tableAnchors[]={
#include "use_item_table_anchors.inc"
};
inline bool DataAnchor(uintptr_t base,const original_move::Anchor& a) noexcept {
    MEMORY_BASIC_INFORMATION m{};const auto at=base+a.rva;
    if(!a.size || a.size>sizeof(a.bytes) || at<base ||
       VirtualQuery(reinterpret_cast<void*>(at),&m,sizeof(m))!=sizeof(m) ||
       m.State!=MEM_COMMIT || m.Type!=MEM_IMAGE || reinterpret_cast<uintptr_t>(m.AllocationBase)!=base ||
       (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
    const auto low=reinterpret_cast<uintptr_t>(m.BaseAddress);
    return at>=low && a.size<=m.RegionSize && at-low<=m.RegionSize-a.size &&
        !memcmp(reinterpret_cast<void*>(at),a.bytes,a.size);
}
inline bool CodeReady(unsigned& reason) noexcept {
    reason=CodeContext;
    const auto base=scope.base;
    if(!base || !scope.selectedReady.load() || forwardBinding.base.load()!=base)return false;
    reason=CodeLiteral;if(!CodeLiteralReady(base,reason,VerifyCodeAnchor))return false;
    reason=CodeData;for(const auto& a:dataAnchors)if(!DataAnchor(base,a))return false;
    reason=CodeTable;
    for(const auto& a:tableAnchors){
        MEMORY_BASIC_INFORMATION m{};const auto at=base+a.rva;const size_t bytes=a.count*8;
        if(!a.count || a.count>3 || at<base ||
           VirtualQuery(reinterpret_cast<void*>(at),&m,sizeof(m))!=sizeof(m) ||
           m.State!=MEM_COMMIT || m.Type!=MEM_IMAGE || reinterpret_cast<uintptr_t>(m.AllocationBase)!=base ||
           (m.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
        const auto low=reinterpret_cast<uintptr_t>(m.BaseAddress);
        if(at<low || bytes>m.RegionSize || at-low>m.RegionSize-bytes)return false;
        for(unsigned i=0;i<a.count;++i)
            if(*reinterpret_cast<uintptr_t*>(at+i*8)!=base+a.slots[i])return false;
    }
    return true;
}
// Narrow machine-call views of accepted caller/callee contracts. No success bool.
inline Pair* Owner(Pair* out) {
    using Machine=Pair*(__fastcall*)(Pair*);
    return reinterpret_cast<Machine>(scope.base+0x77340)(out);
}
inline Pair* Item(void* owner,Pair* out,uint64_t identifier) {
    using Machine=Pair*(__fastcall*)(void*,Pair*,uint64_t);
    return reinterpret_cast<Machine>(scope.base+0x4ff8e0)(owner,out,identifier);
}
inline void Command(void* owner,uint64_t identifier) {
    using Machine=void(__fastcall*)(void*,uint64_t);
    reinterpret_cast<Machine>(scope.base+0x4fd260)(owner,identifier);
}
inline void ReleasePair(Pair pair) {Release(pair.control);}
inline bool Same(Pair a,Pair b) noexcept {return a.object==b.object && a.control==b.control;}
inline bool Live(Pair pair) noexcept {
    return AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)) &&
        AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.control)) &&
        *reinterpret_cast<volatile LONG*>(static_cast<uint8_t*>(pair.control)+8)>0;
}
struct Snapshot {
    manual_move::Pins world{};manual_move::ActorPins player{};Pair map{},character{};
    uintptr_t root=0,gi=0,begin=0,end=0;Pair registeredOwner{},registeredItem{};
    uintptr_t rows=0,rowsEnd=0,capacity=0;void* mapContext=nullptr;
};
// This only reads the existing current registry. Actual owner/item strong leases
// are obtained from the original getter/lookup below, never borrowed from this scan.
inline bool Registry(const Request& r,Snapshot& s,bool capture,unsigned* reason=nullptr) noexcept {
    if(reason)*reason=RegistryOwner;
    const auto base=scope.base;auto* root=*reinterpret_cast<uint8_t**>(base+0x1668790);
    if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) || !root[0xd8])return false;
    auto* gi=*reinterpret_cast<uint8_t**>(root+0xd0);if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(gi)))return false;
    uintptr_t begin=0;size_t count=0;
    if(!original_move::Vector(reinterpret_cast<uintptr_t>(gi)+0x180,128,begin,count))return false;
    const auto end=begin+count*16;
    if(!capture && (s.root!=reinterpret_cast<uintptr_t>(root) || s.gi!=reinterpret_cast<uintptr_t>(gi) ||
       s.begin!=begin || s.end!=end))return false;
    Pair inventory{},map{},character{};bool actors=false,state=false,ui=false;
    for(size_t i=0;i<count;++i){const Pair p=*reinterpret_cast<Pair*>(begin+i*16);
        if(!Live(p))return false;const auto table=*reinterpret_cast<uintptr_t*>(p.object);
        if(table==base+0x117ead8){if(actors || !Same(p,s.world.actors))return false;actors=true;}
        if(table==base+0x1182e30){if(state || !Same(p,s.world.state))return false;state=true;}
        if(table==base+0x1182c50){if(ui || !Same(p,s.world.ui))return false;ui=true;}
        if(table==base+0x11c6878){if(inventory.object)return false;inventory=p;}
        if(table==base+0x11c7df0){if(map.object)return false;map=p;}
        if(table==base+0x1185340){if(character.object)return false;character=p;}
    }
    if(!actors || !state || !ui || !Live(inventory) || !Live(map) || !Live(character))return false;
    if(capture){
        if(!manual_move::Hold(map,s.map) || !manual_move::Hold(character,s.character))return false;
        s.root=reinterpret_cast<uintptr_t>(root);s.gi=reinterpret_cast<uintptr_t>(gi);s.begin=begin;s.end=end;
        s.registeredOwner=inventory;
    } else if(!Same(inventory,s.registeredOwner) || !Same(map,s.map) || !Same(character,s.character))return false;
    if(reason)*reason=RegistryMap;
    if(*reinterpret_cast<uint64_t*>(static_cast<uint8_t*>(character.object)+0x6d8)!=r.player)return false;
    auto* m=static_cast<uint8_t*>(map.object);void* context=*reinterpret_cast<void**>(m+0x6e0);
    if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(context)) ||
       *reinterpret_cast<int32_t*>(m+0x718)!=r.map || *reinterpret_cast<int32_t*>(m+0x71c)!=r.map ||
       *reinterpret_cast<int32_t*>(context)!=r.map)return false;
    if(capture)s.mapContext=context;else if(s.mapContext!=context)return false;
    if(reason)*reason=RegistryRows;
    auto* owner=static_cast<uint8_t*>(inventory.object);
    const auto rows=*reinterpret_cast<uintptr_t*>(owner+0x3d8),rowsEnd=*reinterpret_cast<uintptr_t*>(owner+0x3e0),
        capacity=*reinterpret_cast<uintptr_t*>(owner+0x3e8);
    if(!AutoOkCanonical(rows) || rowsEnd<rows || capacity<rowsEnd || capacity>0x7fffffffffff ||
       (rowsEnd-rows)%16 || (capacity-rows)%16 || (rowsEnd-rows)/16>128)return false;
    Pair item{};
    for(auto at=rows;at<rowsEnd;at+=16){const Pair p=*reinterpret_cast<Pair*>(at);
        if(reason)*reason=RegistryItemType;
        if(!Live(p) || reinterpret_cast<uintptr_t>(p.control)>UINTPTR_MAX-16 ||
           static_cast<uint8_t*>(p.object)!=static_cast<uint8_t*>(p.control)+16 ||
           *reinterpret_cast<uintptr_t*>(p.control)!=base+0x11c66e8 ||
           *reinterpret_cast<void**>(p.object)!=p.object)return false;
        if(*reinterpret_cast<uint64_t*>(static_cast<uint8_t*>(p.object)+8)==r.item){
            if(item.object)return false;item=p;
        }
    }
    if(reason)*reason=RegistryItemUid;
    if(!item.object)return false;
    if(reason)*reason=RegistryRawKey;
    if(*reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(item.object)+0x50)!=0)return false;
    if(reason)*reason=RegistryChanged;
    if(capture){s.rows=rows;s.rowsEnd=rowsEnd;s.capacity=capacity;s.registeredItem=item;}
    else if(s.rows!=rows || s.rowsEnd!=rowsEnd || s.capacity!=capacity || !Same(item,s.registeredItem))return false;
    if(reason)*reason=RegistryLand;
    return manual_move::Stable(s.world,5);
}
inline bool Capture(const Request& r,Snapshot& s,unsigned& reason) noexcept {
    unsigned findReason=0;reason=CaptureWorld;
    if(!manual_move::Find(s.world,5,findReason))return false;
    reason=CapturePlayer;if(!manual_move::ObserveMove(s.world,r.player,s.player))return false;
    return Registry(r,s,true,&reason);
}
inline bool Current(const Request& r,Snapshot& s,unsigned& reason) noexcept {
    reason=CurrentPolicy;
    return manual_move::FinalPolicy(s.world,s.player,move_command_policy::Strict) && Registry(r,s,false,&reason);
}
enum class Stage {Empty,Calling,Returned,Ambiguous,Releasing,Released};
struct Lease {Pair pair{};Stage stage=Stage::Empty;};
struct Calls {
    bool(*code)(unsigned&) noexcept=CodeReady;
    bool(*owned)() noexcept=OwnedNow;
    bool(*capture)(const Request&,Snapshot&,unsigned&) noexcept=Capture;
    bool(*current)(const Request&,Snapshot&,unsigned&) noexcept=Current;
    Pair*(*owner)(Pair*)=Owner;
    Pair*(*item)(void*,Pair*,uint64_t)=Item;
    void(*command)(void*,uint64_t)=Command;
    void(*release)(Pair)=ReleasePair;
};
struct Flight {Snapshot snapshot{};Lease owner{},item{};bool attempted=false;unsigned reason=7;};
inline bool CheckedPair(Pair p) noexcept {return Live(p);}
inline bool Acquired(Lease& lease,Pair* returned) noexcept {
    // The callee returned normally before this is called. A mismatched storage
    // contract is ambiguous; even nonzero partial bits are not cleanup authority.
    if(returned!=&lease.pair){lease.stage=Stage::Ambiguous;return false;}
    lease.stage=Stage::Returned;
    return (!lease.pair.object && !lease.pair.control) || CheckedPair(lease.pair);
}
inline Reply Boundary(const Request& r,Flight& f,const Calls& calls) {
    if(terminal.load() || !calls.owned())return {"UNKNOWN",2,false};
    if(!calls.code(f.reason))return {"CODE_ANCHOR_BLOCKED",f.reason,false};
    if(!calls.capture(r,f.snapshot,f.reason) || !calls.current(r,f.snapshot,f.reason))return {"REFUSED",f.reason,false};
    f.reason=OwnerCall;
    f.owner.stage=Stage::Calling;
    Pair* ownerResult=calls.owner(&f.owner.pair);
    f.reason=OwnerResult;
    if(!Acquired(f.owner,ownerResult))return {"UNKNOWN",f.reason,false};
    if(!f.owner.pair.object || !Same(f.owner.pair,f.snapshot.registeredOwner))return {"UNKNOWN",f.reason,false};
    if(terminal.load())return {"UNKNOWN",9,false};
    if(!calls.code(f.reason))return {"UNKNOWN",f.reason,false};
    if(!calls.owned())return {"UNKNOWN",2,false};
    if(!calls.current(r,f.snapshot,f.reason))return {"UNKNOWN",f.reason,false};
    f.reason=ItemCall;
    f.item.stage=Stage::Calling;
    Pair* itemResult=calls.item(f.owner.pair.object,&f.item.pair,r.item);
    f.reason=ItemResult;
    if(!Acquired(f.item,itemResult))return {"UNKNOWN",f.reason,false};
    if(!f.item.pair.object || !Same(f.item.pair,f.snapshot.registeredItem))return {"UNKNOWN",f.reason,false};
    if(terminal.load())return {"UNKNOWN",9,false};
    if(!calls.code(f.reason))return {"UNKNOWN",f.reason,false};
    if(!calls.owned())return {"UNKNOWN",2,false};
    if(!calls.current(r,f.snapshot,f.reason))return {"UNKNOWN",f.reason,false};
    f.reason=FinalLeases;
    if(!Live(f.owner.pair) || !Live(f.item.pair))return {"UNKNOWN",f.reason,false};
    if(terminal.load())return {"UNKNOWN",9,false};
    f.reason=OriginalCommand;f.attempted=true;
    calls.command(f.owner.pair.object,r.item);
    return {"RETURNED",0,true}; // Original call only. No sender/ACK/effect claim.
}
inline Reply CppBoundary(const Request& r,Flight& f,const Calls& calls) noexcept {
    try {return Boundary(r,f,calls);}
    catch(...) {terminal.store(true);return {"UNKNOWN",f.reason,f.attempted};}
}
inline Reply GuardedBoundary(const Request& r,Flight& f,const Calls& calls) noexcept {
    __try {return CppBoundary(r,f,calls);}
    __except(EXCEPTION_EXECUTE_HANDLER){terminal.store(true);return {"UNKNOWN",f.reason,f.attempted};}
}
inline bool ReleaseOne(Pair& p,const Calls& calls) {
    if(!p.control){p={};return true;}
    if(!Live(p))return false;
    const Pair owned=p;p={}; // Consume cleanup authority BEFORE the release call.
    calls.release(owned);return true;
}
inline bool Cleanup(Flight& f,const Calls& calls) {
    for(Lease* lease:{&f.item,&f.owner}){
        if(lease->stage==Stage::Calling || lease->stage==Stage::Ambiguous)return false;
        if(lease->stage==Stage::Returned){
            lease->stage=Stage::Releasing;
            if(!ReleaseOne(lease->pair,calls))return false;
            lease->stage=Stage::Released;
        }
    }
    auto& s=f.snapshot;
    for(Pair* p:{&s.character,&s.map,&s.player.controller,&s.player.transform,&s.player.actor,
                &s.world.actors,&s.world.layout,&s.world.scene,&s.world.state,&s.world.ui})
        if(!ReleaseOne(*p,calls))return false;
    return true;
}
inline bool CppCleanup(Flight& f,const Calls& calls) noexcept {
    try {return Cleanup(f,calls);}catch(...){return false;}
}
inline bool GuardedCleanup(Flight& f,const Calls& calls) noexcept {
    __try{return CppCleanup(f,calls);}__except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline Reply Using(const Request& r,const Calls& calls=Calls{}) noexcept {
    Flight f{};Reply reply=GuardedBoundary(r,f,calls);
    // A fault or partial publication never authorizes guessed cleanup or retry.
    if(terminal.load())return !strcmp(reply.status,"RETURNED")?Reply{"UNKNOWN",9,f.attempted}:reply;
    if(!GuardedCleanup(f,calls)){
        terminal.store(true);
        // Preserve the known returned-storage refusal if the unchanged cleanup
        // stopped at that Ambiguous stage. An actual release/check fault remains56.
        const bool ambiguous=f.owner.stage==Stage::Ambiguous || f.item.stage==Stage::Ambiguous;
        return {"UNKNOWN",ambiguous?reply.reason:CleanupFailure,f.attempted};
    }
    if(strcmp(reply.status,"RETURNED") || !reply.invoked)terminal.store(true);
    return reply;
}
inline Reply Native(const Request& r) noexcept {return Using(r);}
} }
