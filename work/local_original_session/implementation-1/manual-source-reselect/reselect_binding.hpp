#pragma once
namespace source_reselect { namespace binding {
namespace shared=source_quit::binding;
using Stage=use_item::binding::Stage;using Lease=use_item::binding::Lease;
struct Proof {
    manual_move::Pins world{};Pair character{},row{},network{},registeredCharacter{};
    uintptr_t base=0,root=0,gi=0,registryBegin=0,registryEnd=0,rows=0,rowsEnd=0,head=0,count=0;
    void* node=nullptr;void* slot=nullptr;void* bundle=nullptr;void* ok=nullptr;
};
struct Identity {std::array<uintptr_t,26> values{};};
inline Identity Id(const Proof& p) noexcept {
    return {{{p.root,p.gi,p.registryBegin,p.registryEnd,
        reinterpret_cast<uintptr_t>(p.world.ui.object),reinterpret_cast<uintptr_t>(p.world.ui.control),
        reinterpret_cast<uintptr_t>(p.world.state.object),reinterpret_cast<uintptr_t>(p.world.state.control),
        reinterpret_cast<uintptr_t>(p.world.scene.object),reinterpret_cast<uintptr_t>(p.world.scene.control),
        reinterpret_cast<uintptr_t>(p.world.layout.object),reinterpret_cast<uintptr_t>(p.world.layout.control),
        reinterpret_cast<uintptr_t>(p.character.object),reinterpret_cast<uintptr_t>(p.character.control),
        reinterpret_cast<uintptr_t>(p.row.object),reinterpret_cast<uintptr_t>(p.row.control),p.rows,p.rowsEnd,
        reinterpret_cast<uintptr_t>(p.node),reinterpret_cast<uintptr_t>(p.slot),reinterpret_cast<uintptr_t>(p.bundle),
        reinterpret_cast<uintptr_t>(p.network.object),reinterpret_cast<uintptr_t>(p.network.control),p.head,p.count,p.base}}};
}
inline bool Same(const Identity& a,const Identity& b) noexcept {return a.values==b.values;}
static Identity firstIdentity{};static bool firstIdentityValid=false;
static constexpr original_move::Anchor anchors[]={
#include "reselect_code_anchors.inc"
};
inline bool Code(unsigned& reason) noexcept {
    const auto base=scope.base;
    if(!base || !scope.selectedReady.load() || forwardBinding.base.load()!=base){reason=12;return false;}
    for(const auto& a:anchors)if(!original_move::ExecutableAnchor(base,a)){reason=12;return false;}
    if(!source_restart::binding::NetworkTable()){reason=12;return false;}return true;
}
inline Pair* Owner(uintptr_t root,Pair* out) {
    using Machine=Pair*(__fastcall*)(void*,Pair*);
    return reinterpret_cast<Machine>(scope.base+0x3eb60)(reinterpret_cast<void*>(root),out);
}
struct Flight {Proof proof{};Lease owner{};void* node=nullptr;void* slot=nullptr;void* input=nullptr;void* output=nullptr;
    bool lookupCalling=false,ambiguous=false,attempted=false;unsigned reason=6;};
inline bool GetOwner(Flight& f,Pair*(*getter)(uintptr_t,Pair*)=Owner) {
    f.reason=50;f.owner.stage=Stage::Calling;Pair* returned=getter(f.proof.root,&f.owner.pair);
    f.reason=51;
    if(!use_item::binding::Acquired(f.owner,returned)){f.ambiguous=f.owner.stage==Stage::Ambiguous;return false;}
    f.proof.character=f.owner.pair;
    return shared::Alive(f.proof.character) && shared::SamePair(f.proof.character,f.proof.registeredCharacter);
}
inline bool CompareReference(const Request& r,void* row,bool& match) noexcept {
    match=false;const auto at=reinterpret_cast<uintptr_t>(row);if(!AutoOkCanonical(at))return false;
    const auto length=*reinterpret_cast<size_t*>(at+0x10),capacity=*reinterpret_cast<size_t*>(at+0x18);
    if(!length || length>32 || capacity<length || capacity>0x7fffffffffff || (capacity<16 && capacity!=15))return false;
    const auto bytes=capacity<16?at:*reinterpret_cast<uintptr_t*>(at);
    if(!AutoOkCanonical(bytes) || bytes>UINTPTR_MAX-length)return false;
    unsigned char copy[33]{};memcpy(copy,reinterpret_cast<void*>(bytes),length+1);
    if(copy[length] || !Reference(copy,static_cast<unsigned>(length)))return false;
    match=length==r.referenceLength && !memcmp(copy,r.reference,length);return true;
}
inline bool RowReference(const Request& r,void* row) noexcept {bool match=false;return CompareReference(r,row,match) && match;}
inline bool Registry(Proof& p,bool capture) noexcept {
    const auto base=scope.base;const auto root=*reinterpret_cast<uintptr_t*>(base+0x1668790);
    if(!AutoOkCanonical(root) || !*reinterpret_cast<uint8_t*>(root+0xd8))return false;
    const auto gi=*reinterpret_cast<uintptr_t*>(root+0xd0);uintptr_t begin=0;size_t count=0;
    if(!AutoOkCanonical(gi) || !original_move::Vector(gi+0x180,128,begin,count))return false;
    if(!capture && (base!=p.base || root!=p.root || gi!=p.gi || begin!=p.registryBegin || begin+count*16!=p.registryEnd))return false;
    Pair character{},network{};unsigned ui=0,state=0;
    for(size_t i=0;i<count;++i){const Pair pair=*reinterpret_cast<Pair*>(begin+i*16);
        if(!shared::Alive(pair))return false;const auto table=*reinterpret_cast<uintptr_t*>(pair.object);
        if(table==base+0x1182c50){if(!shared::SamePair(pair,p.world.ui))return false;++ui;}
        if(table==base+0x1182e30){if(!shared::SamePair(pair,p.world.state))return false;++state;}
        if(table==base+0x1185340){if(character.object)return false;character=pair;}
        if(table==base+0x1199d18){if(network.object)return false;network=pair;}
    }
    if(ui!=1 || state!=1 || !shared::Alive(character) || !shared::Alive(network))return false;
    if(capture){p.base=base;p.root=root;p.gi=gi;p.registryBegin=begin;p.registryEnd=begin+count*16;p.registeredCharacter=character;
        return manual_move::Hold(network,p.network) && source_restart::binding::CallerNetwork(p.network);}
    return shared::SamePair(character,p.character) && shared::SamePair(network,p.network) &&
        source_restart::binding::CallerNetwork(p.network);
}
inline bool Rows(const Request& r,Proof& p,bool capture) noexcept {
    if(!shared::Alive(p.character))return false;const auto owner=reinterpret_cast<uintptr_t>(p.character.object);
    const auto begin=*reinterpret_cast<uintptr_t*>(owner+0x570),end=*reinterpret_cast<uintptr_t*>(owner+0x578);
    if(!AutoOkCanonical(begin) || end<begin || (end-begin)%16 || !(end-begin) || (end-begin)/16>128)return false;
    if(!capture && (begin!=p.rows || end!=p.rowsEnd))return false;
    unsigned matches=0;Pair first{};bool firstMatches=false;
    for(uintptr_t at=begin;at<end;at+=16){const Pair pair=*reinterpret_cast<Pair*>(at);
        if(!shared::Alive(pair))return false;
        bool match=false;if(!CompareReference(r,pair.object,match))return false;
        if(at==begin){first=pair;firstMatches=match;}if(match)++matches;
    }
    if(matches!=1 || !firstMatches)return false;
    if(capture){p.rows=begin;p.rowsEnd=end;return manual_move::Hold(first,p.row);}
    return shared::SamePair(first,p.row) && shared::Alive(p.row);
}
inline bool SlotInvoke(uintptr_t table) noexcept {
    return shared::Image(table,0x18) && *reinterpret_cast<uintptr_t*>(table+0x10)==scope.base+0x953890;
}
template<class VerifyInvoke>
inline bool InlineSlot(void* button,void* bundle,uintptr_t base,void* layout,VerifyInvoke verify) noexcept {
    auto* b=static_cast<uint8_t*>(button);auto* state=static_cast<uint8_t*>(bundle);
    return *reinterpret_cast<void**>(b+0x528)==b+0x4f0 &&
        *reinterpret_cast<uintptr_t*>(b+0x4f0)==base+0x1217508 && verify(base+0x1217508) &&
        *reinterpret_cast<void**>(b+0x4f8)==bundle && AutoOkCanonical(reinterpret_cast<uintptr_t>(bundle)) &&
        *reinterpret_cast<void**>(state+0x88)==button && *reinterpret_cast<void**>(state+0x40)==state+8 &&
        *reinterpret_cast<uintptr_t*>(state+8)==base+0x1214eb0 &&
        *reinterpret_cast<uintptr_t*>(state+0x48)==base+0x1214e78 &&
        *reinterpret_cast<void**>(state+0x10)==layout && *reinterpret_cast<int32_t*>(state+0x18)==0;
}
inline bool Ui(const Request& r,Proof& p,bool capture) noexcept {
    const auto base=scope.base;
    if(!manual_move::Stable(p.world,4) || !shared::Alive(p.world.ui) || !shared::Alive(p.world.state) ||
       !shared::Alive(p.world.scene) || !shared::Alive(p.world.layout) ||
       *reinterpret_cast<uintptr_t*>(p.world.scene.object)!=base+0x1187778 ||
       *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(p.world.scene.object)+0x10)!=4)return false;
    const auto layout=reinterpret_cast<uintptr_t>(p.world.layout.object);
    if(*reinterpret_cast<uintptr_t*>(layout)!=base+0x1214f58 || *reinterpret_cast<uint8_t*>(layout+0xb8) ||
       (r.phase==Phase::SelectOK && *reinterpret_cast<int32_t*>(layout+0x180)!=0))return false;
    const auto head=*reinterpret_cast<uintptr_t*>(reinterpret_cast<uintptr_t>(p.world.ui.object)+0x350);
    const auto count=*reinterpret_cast<uintptr_t*>(reinterpret_cast<uintptr_t>(p.world.ui.object)+0x358);
    if(!AutoOkCanonical(head) || !count || count>64 || (!capture && (p.head!=head || p.count!=count)))return false;
    auto at=*reinterpret_cast<uintptr_t*>(head);unsigned found=0;
    for(uintptr_t i=0;i<count;++i){if(!AutoOkCanonical(at) || at==head)return false;
        const Pair pair=*reinterpret_cast<Pair*>(at+0x30);if(!shared::Alive(pair))return false;
        if(*reinterpret_cast<uintptr_t*>(pair.object)==base+0x1214f58){if(!shared::SamePair(pair,p.world.layout))return false;++found;}
        at=*reinterpret_cast<uintptr_t*>(at);}
    if(at!=head || found!=1)return false;
    void* node=*reinterpret_cast<void**>(layout+0x30);void* slot=*reinterpret_cast<void**>(layout+0xc0);uintptr_t table=0;
    if(!shared::Node(node,table) || !shared::Node(slot,table))return false;
    auto* button=static_cast<uint8_t*>(slot);void* bundle=*reinterpret_cast<void**>(button+0x4f8);
    if(!InlineSlot(slot,bundle,base,p.world.layout.object,SlotInvoke))return false;
    if(capture){p.head=head;p.count=count;p.node=node;p.slot=slot;p.bundle=bundle;return true;}
    return p.node==node && p.slot==slot && p.bundle==bundle;
}
inline bool OkInvoke(uintptr_t table) noexcept {
    return shared::Image(table,0x18) && *reinterpret_cast<uintptr_t*>(table+0x10)==scope.base+0x9398f0;
}
template<class VerifyInvoke>
inline bool InlineOk(void* button,uintptr_t base,void* layout,VerifyInvoke verify) noexcept {
    auto* b=static_cast<uint8_t*>(button);
    return *reinterpret_cast<void**>(b+0x528)==b+0x4f0 &&
        *reinterpret_cast<uintptr_t*>(b+0x4f0)==base+0x1214ee8 && verify(base+0x1214ee8) &&
        *reinterpret_cast<void**>(b+0x4f8)==layout;
}
inline bool Ok(const Proof& p) noexcept {
    uintptr_t table=0;return shared::Node(p.ok,table) && InlineOk(p.ok,scope.base,p.world.layout.object,OkInvoke);
}
inline bool Current(const Request& r,Proof& p) noexcept {
    return manual_move::OwnedNow() && scope.base && scope.base==p.base && scope.selectedReady.load() && forwardBinding.base.load()==scope.base &&
        Registry(p,false) && Ui(r,p,false) && Rows(r,p,false) && (r.phase!=Phase::SelectOK || Ok(p));
}
inline void** Lookup(void** out,void** input,const AutoSmallPath* path) {
    using Machine=void**(__fastcall*)(void**,void**,const AutoSmallPath*);
    return reinterpret_cast<Machine>(scope.base+0x8f1b10)(out,input,path);
}
inline bool Capture(const Request& r,Flight& f) {
    auto& p=f.proof;f.reason=6;
    if(!manual_move::Find(p.world,4,f.reason) || !Registry(p,true))return false;
    if(terminal.load() || !manual_move::OwnedNow() || !Code(f.reason) || !GetOwner(f))return false;
    f.reason=6;
    if(!Rows(r,p,true) || !Ui(r,p,true))return false;
    if(!shared::RetainNode(p.node))return false;f.node=p.node;
    if(!shared::RetainNode(p.slot))return false;f.slot=p.slot;
    if(r.phase==Phase::SelectOK){
        if(terminal.load() || !manual_move::OwnedNow() || !Registry(p,false) || !Ui(r,p,false) || !Rows(r,p,false) || !Code(f.reason))return false;
        if(!shared::RetainNode(p.node))return false;f.input=p.node;
        AutoSmallPath path{};memcpy(path.text,"Root.Bt_Ok",11);path.length=10;path.capacity=15;
        f.reason=55;f.lookupCalling=true;void** returned=Lookup(&f.output,&f.input,&path);f.lookupCalling=false;
        f.reason=56;if(returned!=&f.output || f.input){f.ambiguous=true;return false;}
        p.ok=f.output;if(!Ok(p))return false;
    }
    f.reason=6;
    for(void* node:{f.node,f.slot,f.output})if(node && *reinterpret_cast<uint32_t*>(static_cast<uint8_t*>(node)+8)<2)return false;
    return Current(r,p);
}
inline void ReleaseOwned(Pair& pair) {
    if(!pair.control){pair={};return;}
    if(!use_item::binding::Live(pair))RaiseException(0xe0520001,0,0,nullptr);
    const Pair owned=pair;pair={};Release(owned.control);
}
inline void Finish(Flight& f) {
    for(void** cell:{&f.output,&f.input,&f.slot,&f.node})if(*cell){void* owned=*cell;*cell=nullptr;shared::ReleaseNode(owned);}
    for(Pair* pair:{&f.proof.row,&f.proof.network,&f.proof.world.layout,&f.proof.world.scene,&f.proof.world.state,&f.proof.world.ui}){
        ReleaseOwned(*pair);}
    if(f.owner.stage==Stage::Returned){f.owner.stage=Stage::Releasing;ReleaseOwned(f.owner.pair);f.owner.stage=Stage::Released;}
}
inline void Command(const Request& r,const Proof& p) {
    if(r.phase==Phase::SelectSlot){void* node=p.slot;using Machine=void(__fastcall*)(void*,void**);
        reinterpret_cast<Machine>(scope.base+0x93a290)(static_cast<uint8_t*>(p.bundle)+8,&node);}
    else {void* node=p.ok;using Machine=void(__fastcall*)(void*,void**);
        reinterpret_cast<Machine>(scope.base+0x9398f0)(static_cast<uint8_t*>(p.ok)+0x4f0,&node);}
}
struct Calls {
    bool(*owned)() noexcept=manual_move::OwnedNow;
    bool(*code)(unsigned&) noexcept=Code;
    bool(*capture)(const Request&,Flight&)=Capture;
    bool(*current)(const Request&,Proof&) noexcept=Current;
    void(*finish)(Flight&)=Finish;
    void(*command)(const Request&,const Proof&)=Command;
};
inline Reply Boundary(const Request& r,Flight& first,Flight& last,const Calls& calls) {
    if(terminal.load() || !calls.owned())return {"UNKNOWN",2,false};
    if(!calls.code(first.reason))return {"CODE_ANCHOR_BLOCKED",first.reason,false};
    if(!calls.capture(r,first) || !calls.current(r,first.proof))return {"UNKNOWN",first.reason,false};
    const Identity initial=Id(first.proof);const auto firstOk=reinterpret_cast<uintptr_t>(first.proof.ok);calls.finish(first);
    if(!calls.capture(r,last) || !calls.current(r,last.proof) || !Same(initial,Id(last.proof)) ||
       (r.phase==Phase::SelectOK && firstOk!=reinterpret_cast<uintptr_t>(last.proof.ok)))return {"UNKNOWN",last.reason,false};
    if(r.phase==Phase::SelectOK && (!firstIdentityValid || !Same(firstIdentity,Id(last.proof))))return {"UNKNOWN",63,false};
    Proof borrowed=last.proof;calls.finish(last);
    if(!calls.owned() || !calls.code(last.reason) || terminal.load() || !calls.current(r,borrowed))return {"UNKNOWN",last.reason,false};
    if(r.phase==Phase::SelectSlot){firstIdentity=Id(borrowed);firstIdentityValid=true;}
    last.attempted=true;calls.command(r,borrowed);
    return {"RETURNED",0,true}; // No target read or release after the phase callback.
}
inline Reply CppBoundary(const Request& r,Flight& a,Flight& b,const Calls& calls) noexcept {
    try{return Boundary(r,a,b,calls);}catch(...){terminal.store(true);return {"UNKNOWN",7,b.attempted};}
}
inline Reply GuardedBoundary(const Request& r,Flight& a,Flight& b,const Calls& calls) noexcept {
    __try{return CppBoundary(r,a,b,calls);}__except(EXCEPTION_EXECUTE_HANDLER){terminal.store(true);return {"UNKNOWN",7,b.attempted};}
}
inline bool Cleanup(Flight& f,const Calls& calls) noexcept {
    if(f.ambiguous || f.lookupCalling || f.owner.stage==Stage::Calling || f.owner.stage==Stage::Ambiguous)return false;
    try{calls.finish(f);return true;}catch(...){return false;}
}
inline bool GuardedCleanup(Flight& f,const Calls& calls) noexcept {
    __try{return Cleanup(f,calls);}__except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline Reply Using(const Request& r,const Calls& calls=Calls{}) noexcept {
    Flight first{},last{};Reply reply=GuardedBoundary(r,first,last,calls);
    if(terminal.load())return !strcmp(reply.status,"RETURNED")?Reply{"UNKNOWN",9,last.attempted}:reply;
    if(strcmp(reply.status,"RETURNED")){
        if(!GuardedCleanup(last,calls) || !GuardedCleanup(first,calls)){
            terminal.store(true);return {"UNKNOWN",first.ambiguous || last.ambiguous?reply.reason:62,last.attempted};}
        terminal.store(true);
    }
    return reply;
}
inline Reply Native(const Request& r) noexcept {return Using(r);}
} }
