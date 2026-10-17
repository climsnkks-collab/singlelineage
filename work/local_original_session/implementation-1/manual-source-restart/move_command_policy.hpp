#pragma once
namespace move_command_policy {
#include "run31_anchors.hpp"
struct Pin {
    uintptr_t object=0,table=0;uint64_t owner=0;uint32_t rawState=0,controllerState=0;
};
inline bool Same(const Pin& a,const Pin& b) noexcept {
    return a.object==b.object && a.table==b.table && a.owner==b.owner &&
        a.rawState==b.rawState && a.controllerState==b.controllerState;
}
inline bool TableTargets(uintptr_t base,const uintptr_t* table) noexcept {
    for(unsigned i=0;i<5;++i)if(table[i]!=base+attackTableRvas[i])return false;
    return true;
}
inline bool Source(uintptr_t table) noexcept {
    const auto b=scope.base;MEMORY_BASIC_INFORMATION region{};
    if(!b || !scope.selectedReady.load() || forwardBinding.base.load()!=b || table!=b+0x1181040)return false;
    const auto at=table-8;
    if(VirtualQuery(reinterpret_cast<void*>(at),&region,sizeof(region))!=sizeof(region) ||
       region.State!=MEM_COMMIT || region.Type!=MEM_IMAGE || reinterpret_cast<uintptr_t>(region.AllocationBase)!=b ||
       (region.Protect&PAGE_GUARD) || (region.Protect&0xff)==PAGE_NOACCESS)return false;
    const auto low=reinterpret_cast<uintptr_t>(region.BaseAddress);
    if(at<low || region.RegionSize<48 || at-low>region.RegionSize-48)return false;
    return *reinterpret_cast<uintptr_t*>(at)==b+0x127a398 &&
        TableTargets(b,reinterpret_cast<const uintptr_t*>(table)) &&
        original_move::ExecutableAnchor(b,attackDestructor);
}
inline bool Read(void* controller,uint64_t uid,Pin& out,bool allowAttack,
        bool(*source)(uintptr_t) noexcept=Source) noexcept {
    out={};
    __try {
        auto* c=static_cast<uint8_t*>(controller);out.object=*reinterpret_cast<uintptr_t*>(c+0x58);
        out.controllerState=*reinterpret_cast<uint32_t*>(c+0x60);
        if(!out.object)return out.controllerState==0; // Existing empty contract stays strict.
        if(!allowAttack || !uid || !AutoOkCanonical(out.object))return false;
        out.table=*reinterpret_cast<uintptr_t*>(out.object);
        if(out.table!=scope.base+0x1181040 || !source(out.table))return false;
        out.owner=*reinterpret_cast<uint64_t*>(out.object+0x10);
        out.rawState=*reinterpret_cast<uint32_t*>(out.object+8);
        // State values are observations, not invented success/permission enums.
        return out.owner==uid && *reinterpret_cast<uintptr_t*>(c+0x58)==out.object &&
            *reinterpret_cast<uint32_t*>(c+0x60)==out.controllerState;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}
inline bool Strict(void* controller,uint64_t uid,Pin& out) noexcept {return Read(controller,uid,out,false);}
inline bool Setter(void* controller,uint64_t uid,Pin& out) noexcept {return Read(controller,uid,out,true);}
}
