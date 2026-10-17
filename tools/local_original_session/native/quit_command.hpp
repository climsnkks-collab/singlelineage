#pragma once
// Included inside internal_command after the existing Pair/Held helpers.
#include "tools/local_original_session/native/quit_source_anchors.hpp"
namespace quit_detail {
struct Proof {
    uintptr_t base=0,root=0,gi=0,application=0,head=0,count=0,callable=0;
    Pair ui{},state{},scene{},layout{};unsigned sceneKind=0;
};
inline unsigned Route(unsigned scene) noexcept {
    return scene==3||scene==4?1u:scene==5?2u:scene==6?3u:0u;
}
inline bool SamePair(Pair a,Pair b) noexcept {return a.object==b.object && a.control==b.control;}
inline bool Same(const Proof& a,const Proof& b) noexcept {
    return a.base==b.base && a.root==b.root && a.gi==b.gi && a.application==b.application &&
        a.head==b.head && a.count==b.count && a.callable==b.callable && a.sceneKind==b.sceneKind &&
        SamePair(a.ui,b.ui) && SamePair(a.state,b.state) && SamePair(a.scene,b.scene) && SamePair(a.layout,b.layout);
}
inline bool Alive(Pair p) noexcept {
    return AutoOkCanonical(reinterpret_cast<uintptr_t>(p.object)) &&
        AutoOkCanonical(reinterpret_cast<uintptr_t>(p.control)) &&
        *reinterpret_cast<volatile LONG*>(static_cast<uint8_t*>(p.control)+8)>0;
}
inline bool Read(Proof& p) noexcept {
    p={};const uintptr_t b=scope.base;
    if(!b || forwardBinding.base.load()!=b || !scope.selectedReady.load() ||
       GetCurrentThreadId()!=uiThread.load() || !BackgroundGuardCurrentDesktop())return false;
    __try {
        p.base=b;p.root=*reinterpret_cast<uintptr_t*>(b+0x1668790);
        if(!AutoOkCanonical(p.root) || !*reinterpret_cast<uint8_t*>(p.root+0xd8))return false;
        p.gi=*reinterpret_cast<uintptr_t*>(p.root+0xd0);if(!AutoOkCanonical(p.gi))return false;
        const auto begin=*reinterpret_cast<uintptr_t*>(p.gi+0x180),end=*reinterpret_cast<uintptr_t*>(p.gi+0x188);
        if(!AutoOkCanonical(begin)||end<begin||(end-begin)%16||(end-begin)/16>128)return false;
        for(auto at=begin;at<end;at+=16){const auto pair=*reinterpret_cast<Pair*>(at);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
            const auto v=*reinterpret_cast<uintptr_t*>(pair.object);
            if(v==b+0x1182c50){if(p.ui.object)return false;p.ui=pair;}
            if(v==b+0x1182e30){if(p.state.object)return false;p.state=pair;}}
        if(!Alive(p.ui)||!Alive(p.state))return false;
        auto* state=static_cast<uint8_t*>(p.state.object);p.scene=*reinterpret_cast<Pair*>(state+0x360);
        p.sceneKind=*reinterpret_cast<unsigned*>(state+0x380);
        if(!Route(p.sceneKind) || *reinterpret_cast<uintptr_t*>(state+0x370) ||
           *reinterpret_cast<uintptr_t*>(state+0x378) || !Alive(p.scene))return false;
        const uintptr_t v=p.sceneKind==3?0x1187f48:p.sceneKind==4?0x1187778:p.sceneKind==5?0x1186f18:0x1188110;
        if(*reinterpret_cast<uintptr_t*>(p.scene.object)!=b+v ||
           *reinterpret_cast<unsigned*>(static_cast<uint8_t*>(p.scene.object)+0x10)!=p.sceneKind)return false;
        p.application=*reinterpret_cast<uintptr_t*>(b+0x17f0cf8);
        if(!AutoOkCanonical(p.application) || *reinterpret_cast<uintptr_t*>(p.application)!=b+0x1181f78 ||
           *reinterpret_cast<uintptr_t*>(p.application+0x68)!=p.application ||
           *reinterpret_cast<uint8_t*>(p.application+0x60)!=0)return false;
        auto* ui=static_cast<uint8_t*>(p.ui.object);p.head=*reinterpret_cast<uintptr_t*>(ui+0x350);p.count=*reinterpret_cast<uintptr_t*>(ui+0x358);
        if(!AutoOkCanonical(p.head)||!p.count||p.count>64)return false;
        auto node=*reinterpret_cast<uintptr_t*>(p.head);
        for(uintptr_t i=0;i<p.count;++i){if(!AutoOkCanonical(node)||node==p.head)return false;
            const auto pair=*reinterpret_cast<Pair*>(node+0x30);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(pair.object)))return false;
            if(p.sceneKind==6 && *reinterpret_cast<uintptr_t*>(pair.object)==b+0x122f4d8){
                if(p.layout.object || !Alive(pair))return false;p.layout=pair;}
            node=*reinterpret_cast<uintptr_t*>(node);}
        if(node!=p.head)return false;
        if(p.sceneKind==6){
            if(!p.layout.object || *reinterpret_cast<uintptr_t*>(b+0x122f4d8+0x98)!=b+0xacacf0)return false;
            const auto layout=reinterpret_cast<uintptr_t>(p.layout.object);
            p.callable=*reinterpret_cast<uintptr_t*>(layout+0xf0);
            if(p.callable!=layout+0xb8 || *reinterpret_cast<uintptr_t*>(p.callable)!=b+0x122f590 ||
               *reinterpret_cast<uintptr_t*>(b+0x122f590+0x10)!=b+0xacb2a0)return false;
        }
        return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
template<class Code,class Copy> inline bool SourceProof(const Proof& p,Code code,Copy copy) noexcept {
    const unsigned route=Route(p.sceneKind);if(!route)return false;
    unsigned char bytes[32]{};
    for(const auto& a:internal_quit_source::anchors)if(a.route==route){
        const uintptr_t address=p.base+a.rva;
        if(!code(address,a.size)||!copy(bytes,reinterpret_cast<void*>(address),a.size)||memcmp(bytes,a.bytes,a.size))return false;
    }
    return true;
}
inline bool Source(const Proof& p) noexcept {return SourceProof(p,Executable,SafeCopy);}
inline bool Prepare(Proof& p) noexcept {
    if(!Read(p))return false;
    Pair u{},s{},c{},l{};
    const bool held=Hold(p.ui,u)&&Hold(p.state,s)&&Hold(p.scene,c)&&(!p.layout.object||Hold(p.layout,l));
    Held ui{u},state{s},scene{c},layout{l};
    Proof current;
    return held && Read(current) && Same(p,current) && Source(current);
    // All bridge-owned strong references release before the final borrowed proof.
}
inline bool Fresh(Proof& p) noexcept {
    if(!Read(p)||!Source(p))return false;Proof last;
    return Read(last)&&Same(p,last);
}
inline bool Invoke(const Proof& p) noexcept {
    // Formal original callback ABIs. Whole verified bodies do not consume the
    // nullptr arguments in routes1/2; this is a documented machine-ABI inference.
    // Route3 supplies the actual live bool-true QuitCredit callable as RCX.
    __try {
        if(Route(p.sceneKind)==2){using Callback=void(__fastcall*)(void*,void*);
            reinterpret_cast<Callback>(p.base+0xacbda0)(nullptr,nullptr);}
        else {using Callback=void(__fastcall*)(void*);
            reinterpret_cast<Callback>(p.base+(p.sceneKind==6?0xacb2a0:0x944b80))(
                p.sceneKind==6?reinterpret_cast<void*>(p.callable):nullptr);}
        return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
template<class PrepareFn,class FreshFn,class InvokeFn>
inline Reply Run(PrepareFn prepare,FreshFn fresh,InvokeFn invoke) noexcept {
    Proof before,current;
    if(!prepare(before) || !Route(before.sceneKind) || !fresh(current) || !Same(before,current))return {"REFUSED",6,false};
    const bool returned=invoke(current);
    // No game-object read, cached pointer use or Held release after invocation.
    return {returned?"RETURNED":"REFUSED",returned?0u:7u,returned};
}
inline Reply Execute() noexcept {return Run(Prepare,Fresh,Invoke);}
}
