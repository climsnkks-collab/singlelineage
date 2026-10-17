#pragma once
// run26/I1-016 machine ABI. RAX from A3640 is intentionally unused; the
// void machine-call view does not establish the original formal C++ return type.
namespace attack_target { namespace native_call {
static constexpr original_move::Anchor anchors[]={
#include "attack_prefix_anchors.inc"
};
static_assert(sizeof(anchors)/sizeof(anchors[0])==6,"run26 six fixed decoded CONTROL prefixes");
template<class Verify>
inline bool CodeGate(uintptr_t base,bool selected,uintptr_t forwardBase,Verify verify) noexcept {
    if(!base || !selected || forwardBase!=base)return false;
    for(const auto& anchor:anchors)if(!verify(base,anchor))return false;
    return true;
}
inline bool CodeReady() noexcept {
    // Decoded CONTROL literals, not candidate packed disk prefixes. Actual
    // runtime mapping/allocation/protection/bytes must pass the existing gate.
    return CodeGate(scope.base,scope.selectedReady.load(),forwardBinding.base.load(),original_move::ExecutableAnchor);
}
inline void Get(uint32_t rva,Pair* out,void* target) {
    using Machine=void(__fastcall*)(Pair*,void*); // Getter RAX is not an admission predicate.
    reinterpret_cast<Machine>(scope.base+rva)(out,target);
}
inline Pair* Copy(Pair* out,const Pair* source) {
    using Machine=Pair*(__fastcall*)(Pair*,const Pair*);
    return reinterpret_cast<Machine>(scope.base+0x66410)(out,source);
}
inline uint8_t Predicate(void* interaction) {
    using Machine=uint8_t(__fastcall*)(void*);
    return reinterpret_cast<Machine>(scope.base+0xb6db0)(interaction);
}
inline void Command(void* controller,Pair* argument) {
    using Machine=void(__fastcall*)(void*,Pair*,uint32_t);
    reinterpret_cast<Machine>(scope.base+0xa3640)(controller,argument,0);
}
inline void ReleasePair(Pair p) {Release(p.control);}
inline bool Fresh(const Request& r,const Snapshot& pinned) noexcept {
    Snapshot current{};Retained retain{current};
    return Observe(r,current) && Same(pinned,current);
}
struct Calls {
    bool(*code)() noexcept=CodeReady;
    bool(*owned)() noexcept=OwnedNow;
    bool(*fresh)(const Request&,const Snapshot&) noexcept=Fresh;
    void(*get)(uint32_t,Pair*,void*)=Get;
    Pair*(*copy)(Pair*,const Pair*)=Copy;
    uint8_t(*predicate)(void*)=Predicate;
    void(*command)(void*,Pair*)=Command;
    void(*release)(Pair)=ReleasePair;
};
struct Components {
    const Calls& calls;Pair pair[3]{};bool leased[3]{};
    ~Components() noexcept(false){for(unsigned i=3;i;--i)if(leased[i-1])calls.release(pair[i-1]);}
};
inline bool Acquire(Components& out,void* target) {
    constexpr uint32_t getters[]={0x3ed20,0x586e0,0x42ec0};
    for(unsigned i=0;i<3;++i){
        if(terminal.load())return false;
        out.calls.get(getters[i],&out.pair[i],target);
        out.leased[i]=true; // Getter retains only if control != null.
        if(terminal.load())return false;
    }
    return true; // Local cancellation result, never the getter's RAX.
}
inline bool Same(const Components& a,const Components& b) noexcept {
    for(unsigned i=0;i<3;++i)if(!attack_target::Same(a.pair[i],b.pair[i]))return false;
    return true;
}
inline bool Live(Pair p,bool required) noexcept {
    if(!p.object)return !required && !p.control;
    if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)))return false;
    // A null control is allowed by the original typed getter. Its current
    // membership is revalidated by the same-target getter while Actor is held.
    return !p.control || (AutoOkCanonical(reinterpret_cast<uintptr_t>(p.control)) &&
        *reinterpret_cast<volatile LONG*>(static_cast<uint8_t*>(p.control)+8)>0);
}
inline bool Live(const Components& c) noexcept {
    return Live(c.pair[0],true) && Live(c.pair[1],true) && Live(c.pair[2],false);
}
inline bool RawAdmission(const Components& c,bool predicate) noexcept {
    if(!Live(c) || !static_cast<uint8_t*>(c.pair[0].object)[0x46] ||
       static_cast<uint8_t*>(c.pair[1].object)[0x88])return false;
    return predicate || (c.pair[2].object && *reinterpret_cast<float*>(static_cast<uint8_t*>(c.pair[2].object)+0x84)>0.0f);
}
enum class ArgPhase {Empty,Copying,Copied,HandedOff,Consumed};
struct Argument {
    const Calls& calls;Pair pair{};ArgPhase phase=ArgPhase::Empty;
    ~Argument() noexcept(false){
        // Only a completed copy cancelled BEFORE handoff is ours to release.
        // Copy fault and post-handoff fault are ambiguous: no guessed cleanup.
        if(phase==ArgPhase::Copied)calls.release(pair);
    }
};
inline Reply Boundary(const Request& r,const Snapshot& s,const Calls& calls,bool& attempted) {
    if(!calls.code())return {"CODE_ANCHOR_BLOCKED",12,false};
    if(terminal.load() || !calls.owned())return {"UNKNOWN",2,false};
    Components first{calls};
    if(!Acquire(first,s.target.object) || !Live(first) || !calls.fresh(r,s))return {"UNKNOWN",6,false};
    Components again{calls};
    if(!Acquire(again,s.target.object) || !Same(first,again) || !Live(again))return {"UNKNOWN",6,false};
    // Early byte-only refusal; policy evaluation belongs to the final leases.
    if(!static_cast<uint8_t*>(first.pair[0].object)[0x46] || static_cast<uint8_t*>(first.pair[1].object)[0x88])return {"REFUSED",13,false};
    Argument argument{calls};argument.phase=ArgPhase::Copying;
    const Pair* const source=&s.target; // Retained source lease is never handed off.
    if(calls.copy(&argument.pair,source)!=&argument.pair || !attack_target::Same(argument.pair,*source))return {"UNKNOWN",7,false};
    argument.phase=ArgPhase::Copied;
    if(terminal.load() || !calls.code() || !calls.owned() || !calls.fresh(r,s) || !Live(first))return {"UNKNOWN",2,false};
    Components final{calls};
    if(!Acquire(final,s.target.object) || !Same(first,final) || !Live(final) ||
       !calls.fresh(r,s) || terminal.load())return {"UNKNOWN",6,false};
    if(!static_cast<uint8_t*>(final.pair[0].object)[0x46] || static_cast<uint8_t*>(final.pair[1].object)[0x88])return {"REFUSED",13,false};
    // Exactly one AL evaluation, after copy/fresh/final getter callbacks.
    const bool predicate=calls.predicate(final.pair[1].object)!=0;
    if(terminal.load())return {"UNKNOWN",9,false};
    if(!RawAdmission(final,predicate))return {"REFUSED",13,false};
    if(!calls.fresh(r,s) || !calls.owned() || !calls.code() || !Live(argument.pair,true))return {"UNKNOWN",6,false};
    // No callback may revive this attempt by setting terminal then returning true.
    if(terminal.load())return {"UNKNOWN",9,false};
    argument.phase=ArgPhase::HandedOff;attempted=true;
    calls.command(s.player.controller.object,&argument.pair);
    argument.phase=ArgPhase::Consumed; // Normal callee consumed parameter lease; bits remain.
    return {"RETURNED",0,true};
}
inline Reply SubmitUsing(const Request& r,const Snapshot& s,const Calls& calls,bool& attempted) noexcept {
    try {return Boundary(r,s,calls,attempted);}
    catch(...) {return {"UNKNOWN",7,attempted};} // C++ EH; outer Guarded handles hardware SEH.
}
inline Reply Submit(const Request& r,const Snapshot& s,bool& attempted) noexcept {return SubmitUsing(r,s,Calls{},attempted);}
} }
