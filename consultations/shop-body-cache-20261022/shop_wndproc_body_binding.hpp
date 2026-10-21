#pragma once
// Included inside shop_wndproc_input after Current/ObserveCurrentHover.
// REA181: synchronous passive POD interval under Execute's existing Held
// UI/State/Scene/A and same-UI-thread Current boundary. No child retain/lock,
// original getter/virtual call, G/K role, or point authority is created here.
struct BodyReadSection {
    CurrentContext* context;const shop_wndproc_dispatch::Proof* proof;
    bool Current() noexcept {return shop_wndproc_input::Current(context,*proof);}
    uintptr_t ImageBase() noexcept {return proof->image_base;}
    uintptr_t Actors() noexcept {return reinterpret_cast<uintptr_t>(context->pins.actors.object);}
    template<class T>bool Read(uintptr_t at,size_t offset,T& value) noexcept {return ui::Read(at,offset,value);}
    bool QualifiedSlot(uintptr_t object,unsigned slot,uintptr_t rva) noexcept {
        uintptr_t table=0,entry=0;
        return rva<proof->image_size&&ui::Read(object,0,table)&&ui::Read(table,slot,entry)&&entry==ImageBase()+rva;
    }
    bool QualifiedPrimary(uintptr_t object,uintptr_t rva) noexcept {
        uintptr_t table=0;return rva<proof->image_size&&ui::Read(object,0,table)&&table==ImageBase()+rva;
    }
    bool SelectedComponents(uintptr_t actor,uintptr_t action,uintptr_t transform) noexcept {
        uintptr_t actionOwner=0,transformOwner=0;
        return QualifiedPrimary(action,0x1180df0)&&QualifiedPrimary(transform,0x117ed38)&&
            ui::Read(action,8,actionOwner)&&ui::Read(transform,8,transformOwner)&&
            actionOwner==actor&&transformOwner==actor;
    }
};
inline BodyObservation ObserveCurrentBody(CurrentContext& context,const shop_wndproc_dispatch::Proof& proof,uint64_t expectedUid) noexcept {
    BodyObservation unknown{};unknown.state=BodyState::Unknown;
    if(!Current(&context,proof))return unknown;
    BodyReadSection section{&context,&proof};
    const auto result=body::CachedBody(section,expectedUid);
    if(!Current(&context,proof))return unknown;
    return result;
}
