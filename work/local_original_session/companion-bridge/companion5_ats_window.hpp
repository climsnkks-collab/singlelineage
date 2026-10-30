#pragma once
#include <new>
#include <set>
#include "companion5_ats_json.hpp"

// Independent companion ATS CSB widgets, generic CreatableLayout lifetime.
// Static source: frozen CONTROL 9ffc24fe...170b7af; selected bytes read through
// ats-evidence/native_inspect.py's existing View. This is not runtime evidence.
namespace companion5_ats {
using namespace companion_bridge;
using namespace companion3_native;
using Pair=companion3_native::Pair;
inline bool Enabled() noexcept {
    static const bool value=[](){wchar_t text[4]{};
        return GetEnvironmentVariableW(L"COMPANION_ATS_WINDOW",text,4)==1&&text[0]==L'1';}();
    return value;
}
struct State {
    Record window{};Pair owner{};void* root=nullptr;Mapping identity{};
    std::string caption{};bool creating=false,closePending=false,failed=false;
    const char* status="ATS_WINDOW_UNREQUESTED";
    AtsOpenDiagnostic diagnostic{};uintptr_t imageSize=0;bool titleTracing=false;
    companion5_json::Value baseline{},draft{};
    uint64_t editEpoch=0,openEvent=0,saveEvent=0;
    uint64_t renderedRevision=0,bagEvent=0,bagEpoch=0;
    unsigned unavailableItems=0;
    bool unsupportedReadOnly=false;
    bool loaded=false,saving=false,rendering=false;
    void* fields[2]{};void* slots[10]{};
    void* optionScan=nullptr;void* optionWeight=nullptr;void* optionList=nullptr;
    void* dropComponent=nullptr;void* inputComponent=nullptr;
    Pair knightOwner{};void* knightLayout=nullptr;
    // Original ATS has 24 virtual entries through vB8 (ui2_vtables.json).
    uintptr_t* knightNativeVtable=nullptr;uintptr_t knightLocalVtable[25]{};
    Show knightNativeShow=nullptr;
    std::string resultReason{};
    Record spellWindow{};Pair spellOwner{};void* spellRoot=nullptr;
    bool spellCreating=false,spellClosePending=false;size_t spellPage=0;
    void* spellDrop=nullptr;void* spellInput=nullptr;void* spellList=nullptr;
    size_t spellRequested=0,spellFilled=0;
    const char* spellPlacement="UNOBSERVED";
    const char* spellDiagnosticPhase="OPEN";
    UINT_PTR spellDiagnosticTimer=0,spellLayoutTimer=0,atsLayoutTimer=0;
    struct SpellSlot {void* node=nullptr;Pair metadata{};uint64_t row=0;
        uint16_t maskBefore=0,iconMaskBefore=0;};
    std::vector<SpellSlot> spellSlots;
    // DLL-owned spell drag (SLCompSpell -> SLCompATS), see SpellDragTick.
    bool spellPointerHeld=false,spellDragActive=false;size_t spellDragSource=SIZE_MAX;
    Vec2 spellDragStart{},spellDragOffset{};void* spellDragPreview=nullptr;
    struct AtsDragSource {unsigned kind=0;size_t index=0;void* slot=nullptr;};
    bool atsPointerHeld=false,atsDragActive=false;AtsDragSource atsDragSource{};
    Vec2 atsDragStart{},atsDragOffset{};void* atsDragPreview=nullptr;
    uint64_t spellDragSequence=0;
    std::vector<void*> buffRows,buffSlotNodes;
    void* battleSequence[8]{},*battleConditional[8]{};
    // Recovery tab: the Help page carries a second ATSLayout.csb Combat.02.
    // Rows 1-4 HP (10% pulldown), rows 5-6 status. All retained.
    void* healFragment=nullptr;void* healRows[6]{},*healSlots[6]{},*healTexts[6]{},*healMenus[4]{};
    int healOpen=-1;bool healAttempted=false,healReady=false;
    ULONGLONG openMs=0,widgetsMs=0,healLoadMs=0,healSetupMs=0;
};
// Like the existing bag/gear records, no native calls from CRT detach teardown.
inline State* state=nullptr;
inline uint64_t spellResultSequence=0;
inline uintptr_t __fastcall KnightShowWindow(void* layout,bool show);
inline bool Current() noexcept {
    if(!state||!state->window.layout||state->closePending||!enabled||!OnUi())return false;
    const Mapping* m=Find(state->identity.actor);
    return m&&m->generation==state->identity.generation&&m->owner==state->identity.owner&&m->member==state->identity.member;
}
inline void ClosePendingModelRequest() noexcept {
    if(!state||!state->bagEvent||!state->bagEpoch)return;
    const auto* mapping=Find(state->identity.actor);
    if(mapping&&mapping->generation==state->identity.generation&&mapping->owner==state->identity.owner&&mapping->member==state->identity.member){
        auto& model=ModelFor(*mapping);const auto& bag=model.view(companion_model::Window::Bag);
        if(bag.requested&&bag.epoch==state->bagEpoch)companion_model::CloseView(model,companion_model::Window::Bag);
    }
    state->bagEvent=0;state->bagEpoch=0;
}
inline void ModelRequestFlushed(uint64_t sequence) noexcept {
    // Flush's normal mapping/requested/epoch checks remain intact. Revoke our
    // view intent only after that exact queued event has been emitted/failed,
    // before an asynchronous ReadModel can invoke Changed and open a Bag UI.
    if(state&&state->bagEvent==sequence)ClosePendingModelRequest();
}
inline void BagMenuRequested(const Mapping& mapping) noexcept {
    // A real Bag-menu intent promotes the pending request to the ordinary Bag
    // lifetime; ATS must no longer close it when its model signal flushes.
    if(state&&state->bagEvent&&state->identity.actor==mapping.actor&&state->identity.generation==mapping.generation&&
        state->identity.owner==mapping.owner&&state->identity.member==mapping.member){state->bagEvent=0;state->bagEpoch=0;}
}
inline void Render();
inline void Save();
inline bool OpenSpell();
inline void RetireSpell();
inline void CancelAtsDrag();
inline void ReleaseWidgets() {
    if(!state)return;for(void*& field:state->fields){ReleaseNode(field);field=nullptr;}
    for(void*& slot:state->slots){ReleaseNode(slot);slot=nullptr;}
    ReleaseNode(state->optionScan);state->optionScan=nullptr;
    ReleaseNode(state->optionWeight);state->optionWeight=nullptr;
    ReleaseNode(state->optionList);state->optionList=nullptr;
}
inline void Step(const char* name) noexcept {
    if(!state||!atsOpenBoundary)return;auto& d=state->diagnostic;
    if(d.step<65535)++d.step;d.phase=name;d.name=name;
    d.nativeTarget=0;d.nativeRva=0;d.nativeInImage=false;d.virtualOffset=-1;
}
inline void NativeBoundary(uintptr_t target,int virtualOffset) noexcept {
    if(!state)return;auto& d=state->diagnostic;if(d.step<65535)++d.step;
    d.name=state->titleTracing?companion3_native::createStage:d.phase;
    d.nativeTarget=target;d.virtualOffset=virtualOffset;
    d.nativeInImage=target>=base&&target-base<state->imageSize;
    d.nativeRva=d.nativeInImage?target-base:0;
}
inline void CaptureBeforeRetire() noexcept {
    if(state){state->diagnostic.layout=reinterpret_cast<uintptr_t>(state->window.layout);
        state->diagnostic.root=reinterpret_cast<uintptr_t>(state->root);}
}
inline int CaptureOpenException(EXCEPTION_POINTERS* info) noexcept {
    if(info&&info->ExceptionRecord&&info->ExceptionRecord->ExceptionCode==0xe06d7363)return EXCEPTION_CONTINUE_SEARCH;
    // Record while the exception context and pre-cleanup window still exist.
    // No original calls, allocations, or target-memory reads in this filter.
    if(state&&info&&info->ExceptionRecord){auto& d=state->diagnostic;
        d.exceptionCode=info->ExceptionRecord->ExceptionCode;
        d.exceptionAddress=reinterpret_cast<uintptr_t>(info->ExceptionRecord->ExceptionAddress);
        d.exceptionInImage=d.exceptionAddress>=base&&d.exceptionAddress-base<state->imageSize;
        d.exceptionRva=d.exceptionInImage?d.exceptionAddress-base:0;CaptureBeforeRetire();}
    atsOpenBoundary=nullptr;return EXCEPTION_EXECUTE_HANDLER;
}
inline void ResetAny(void* value) {
    if(!value)return;
    // v+A0=FA1958 is _purecall (IAT10B7248 -> hint/name15BA5CC).
    // Concrete ATS8E6580 consumes RDX any64: 8E65E4..8E6605 destroys
    // small(tag2, inline) / big(tag1, +28) via +30 then zeros +38.
    // Inventory A02E20..A032CB confirms R8 is borrowed, RDX alone consumed.
    // Preserve that argument ownership while performing no model operation.
    const uintptr_t mode=At<uintptr_t>(value,0x38)&3;
    if(mode==1||mode==2){void* object=mode==1?At<void*>(value,0x28):value;
        using Destroy=void(__fastcall*)(void*);
        auto* table=At<uintptr_t*>(value,0x30);reinterpret_cast<Destroy>(table[0])(object);}
    At<uintptr_t>(value,0x38)=0;
}
inline void __fastcall ConsumeCommand(void*,void* value,const void*) {ResetAny(value);}
inline uintptr_t __fastcall ShowWindow(void* layout,bool show) {
    const auto original=companion3_native::originalShow?companion3_native::originalShow:reinterpret_cast<Show>(base+0xa10bb0);
    ObserveAtsOpenBoundary(reinterpret_cast<uintptr_t>(original));
    const uintptr_t result=original(layout,show);
    if(state&&state->window.layout==layout&&!show){state->closePending=true;
        PostMessageW(autoOkWindow.load(),DrainMessage(),0,0);}
    return result;
}
inline void DeleteLayout(void* object) noexcept {
    using Destroy=void(__fastcall*)(void*,unsigned);Vcall<Destroy>(object,0)(object,1);
}
inline void ReleaseTransientTitle(Record& r) {
    ReleaseNode(r.titleStyle);ReleaseNode(r.titleClose);ReleaseNode(r.titleName);
}
inline void RetireImpl() {
    if(!state)return;auto& s=*state;auto& r=s.window;
    if(s.atsLayoutTimer){KillTimer(nullptr,s.atsLayoutTimer);s.atsLayoutTimer=0;}
    CancelAtsDrag();
    RetireSpell();
    isolatedAtsRoute=nullptr;
    if(s.knightLayout&&s.knightNativeVtable&&At<uintptr_t*>(s.knightLayout,0)==s.knightLocalVtable+1)
        At<uintptr_t*>(s.knightLayout,0)=s.knightNativeVtable;
    Release(nullptr,s.knightOwner);s.knightLayout=nullptr;s.knightNativeVtable=nullptr;s.knightNativeShow=nullptr;
    ClosePendingModelRequest();s.creating=false;s.closePending=false;
    s.loaded=false;s.saving=false;s.editEpoch=0;s.openEvent=0;s.saveEvent=0;s.bagEvent=0;s.bagEpoch=0;s.renderedRevision=0;
    s.baseline={};s.draft={};s.dropComponent=nullptr;s.inputComponent=nullptr;ReleaseWidgets();
    for(void*& node:s.buffSlotNodes){ReleaseNode(node);node=nullptr;}
    for(void*& node:s.buffRows){ReleaseNode(node);node=nullptr;}
    s.buffSlotNodes.clear();s.buffRows.clear();
    for(void*& node:s.battleSequence){ReleaseNode(node);node=nullptr;}
    for(void*& node:s.battleConditional){ReleaseNode(node);node=nullptr;}
    for(void** group:{s.healRows,s.healSlots,s.healTexts})for(size_t i=0;i<6;++i){ReleaseNode(group[i]);group[i]=nullptr;}
    for(void*& node:s.healMenus){ReleaseNode(node);node=nullptr;}
    ReleaseNode(s.healFragment);s.healFragment=nullptr;s.healOpen=-1;s.healAttempted=false;s.healReady=false;
    RemoveTitle(r);ReleaseTransientTitle(r);
    UnregisterLayout(r);
    if(r.layout){
        // Hide before disconnect/remove so manager's focus/visibility event is
        // balanced while the shared weak owner and tree are still alive.
        if(At<uint8_t>(r.layout,0x70))ShowWindow(r.layout,false);
        s.closePending=false;Disconnect(r.layout,0x18);
        if(s.root){using Remove=void(__fastcall*)(void*);Vcall<Remove>(s.root,0x220)(s.root);}
        if(r.nativeVtable)At<uintptr_t*>(r.layout,0)=r.nativeVtable;
    }
    Release(nullptr,s.owner);s.root=nullptr;s.identity={};s.caption.clear();
    r.layout=nullptr;r.nativeVtable=nullptr;r.nativeShow=nullptr;
    r.registryName=nullptr;r.titleOverride=nullptr;r.titleStylePath=nullptr;
    r.titleRetry=false;r.creation={};r.log={};s.closePending=false;
}
inline bool RetireNative() {
    __try {RetireImpl();return true;}
    __except(GetExceptionCode()==0xe06d7363?EXCEPTION_CONTINUE_SEARCH:EXCEPTION_EXECUTE_HANDLER){
        ++adapterErrors;if(state)state->status="ATS_WINDOW_RETIRE_UNKNOWN";return false;}
}
inline void Retire() noexcept {try{(void)RetireNative();}catch(...){++adapterErrors;if(state)state->status="ATS_WINDOW_RETIRE_UNKNOWN";}}
inline void RetireMember(const Mapping& mapping) noexcept {
    if(state&&state->identity.actor==mapping.actor&&state->identity.generation==mapping.generation&&state->identity.member==mapping.member)Retire();
}
inline bool CloseVisibleKnightAts() {
    // The native ATS Close is A10570 -> v70(false)=8E6A80. Its false branch
    // hides through A10BB0 and returns without the Save invoke (8F6450).
    // Look up only the existing original instance; never create or toggle it.
    Pair manager{};using GetManager=Pair*(__fastcall*)(Pair*);
    Call<GetManager>(0x560f0)(&manager);
    struct Held {Pair& pair;~Held(){Release(nullptr,pair);}} heldManager{manager};
    if(!manager.object)return true;
    const String32 name=Borrow("ATSLayout");Pair knight{};
    using LookupLayout=Pair*(__fastcall*)(void*,Pair*,const String32*);
    Call<LookupLayout>(0xb3a0b0)(manager.object,&knight,&name);
    Held heldKnight{knight};
    if(!knight.object||knight.object==state->window.layout)return true;
    void* root=At<void*>(knight.object,0x30);if(!root)return true;
    using IsVisible=bool(__fastcall*)(void*);
    if(Vcall<IsVisible>(root,0x150)(root)){
        Step("KNIGHT_ATS_NATIVE_CLOSE");using Close=void(__fastcall*)(void*);
        Call<Close>(0xa10570)(knight.object);
        if(Vcall<IsVisible>(root,0x150)(root)){
            // A10570 can refuse if the layout's native close gate is disabled.
            // The same original ATS v70(false) hide branch has no Save call.
            Step("KNIGHT_ATS_NATIVE_HIDE");using ShowAts=uintptr_t(__fastcall*)(void*,bool);
            Vcall<ShowAts>(knight.object,0x70)(knight.object,false);
        }
    }
    if(Vcall<IsVisible>(root,0x150)(root))return false;
    // The no-code-patch DLL cannot detour 8E6A80. Interpose only this already
    // registered original ATS instance's v70 while the companion editor lives.
    auto& s=*state;s.knightOwner=knight;Retain(s.knightOwner);s.knightLayout=knight.object;
    s.knightNativeVtable=At<uintptr_t*>(knight.object,0);
    s.knightNativeShow=reinterpret_cast<Show>(s.knightNativeVtable[0x70/8]);
    std::memcpy(s.knightLocalVtable,s.knightNativeVtable-1,sizeof(s.knightLocalVtable));
    s.knightLocalVtable[1+0x70/8]=reinterpret_cast<uintptr_t>(&KnightShowWindow);
    At<uintptr_t*>(knight.object,0)=s.knightLocalVtable+1;
    return true;
}
inline void* Cast(void* node,uintptr_t target) {
    using DynamicCast=void*(__fastcall*)(void*,long,void*,void*,int);
    return Call<DynamicCast>(0xfa1ad3)(node,0,reinterpret_cast<void*>(base+0x166ec80),reinterpret_cast<void*>(base+target),0);
}
inline void Visible(void* node,bool value) {
    if(node){using Set=void(__fastcall*)(void*,bool);Vcall<Set>(node,0x148)(node,value);}
}
inline void* Typed(const char* path,uintptr_t target) {
    void* node=Lookup(state->window.layout,path,false);if(!node)return nullptr;
    void* typed=Cast(node,target);if(typed)++At<int32_t>(typed,8);ReleaseNode(node);return typed;
}
inline std::string FieldText(void* field) {
    if(!field)return {};void* renderer=At<void*>(field,0x700);if(!renderer)return {};
    // C021F0/C0220D..17: renderer+340 interface v10 returns String32.
    // CONTROL C56A20 returns interface+4F0 (renderer+830).
    void* textInterface=static_cast<char*>(renderer)+0x340;
    using Get=const String32*(__fastcall*)(void*);const auto* value=Vcall<Get>(textInterface,0x10)(textInterface);
    if(!value||value->size>128||value->capacity<value->size)return {};
    const char* bytes=value->capacity>15?value->pointer:value->inlineBytes;
    return bytes?std::string(bytes,value->size):std::string{};
}
inline void SetField(void* field,const std::string& text) {
    if(!field)return;const String32 value=Borrow(text.c_str());using Set=void(__fastcall*)(void*,const String32*);
    Call<Set>(0xc015b0)(field,&value);
    // Suppress CSB placeholder100/99 when absent. The native renderer alone is
    // hidden; TextField hit/input remains native and its event shows typed text.
    Visible(At<void*>(field,0x700),!text.empty());
}
inline bool Percent(const companion5_json::Value& v) {
    if(v.kind==companion5_json::Value::Null)return true;
    if(v.kind!=companion5_json::Value::Number)return false;char* end=nullptr;
    const double number=std::strtod(v.text.c_str(),&end);return end&&!*end&&std::isfinite(number)&&number>=0&&number<=100;
}
inline std::string PercentText(const companion5_json::Value& value) {
    if(value.kind!=companion5_json::Value::Number)return {};
    const double number=std::strtod(value.text.c_str(),nullptr);
    return std::isfinite(number)&&number>=0&&number<=100&&std::floor(number)==number?
        std::to_string(static_cast<unsigned>(number)):value.text;
}
inline bool SamePercent(const companion5_json::Value& a,const companion5_json::Value& b) {
    if(a.kind!=companion5_json::Value::Number||b.kind!=companion5_json::Value::Number)return a==b;
    return Percent(a)&&Percent(b)&&std::strtod(a.text.c_str(),nullptr)==std::strtod(b.text.c_str(),nullptr);
}
inline bool ValidView(const companion5_json::Value& view,uint64_t member,uint64_t epoch) {
    using J=companion5_json::Value;uint64_t m=0,e=0;
    if(view.kind!=J::Object||view.Get("schema").text!="companion-ats-view-v1"||
       !view.Get("member_id").UInt(m)||m!=member||!view.Get("edit_epoch").UInt(e)||e!=epoch||!epoch)return false;
    const char* keys[]={"hp_slots","mp_slots","function_slots"};const size_t counts[]={2,2,6};
    for(size_t k=0;k<3;++k){const auto& array=view.Get(keys[k]);if(array.kind!=J::Array||array.array.size()!=counts[k])return false;
        for(const auto& item:array.array)if(item.kind!=J::Null){uint64_t id=0;if(item.kind!=J::Object||!item.Get("template").UInt(id)||!id||id>INT_MAX)return false;}}
    const auto& learned=view.Get("learned_spells");
    if(learned.kind!=J::Array||learned.array.size()>80)return false;
    std::set<uint64_t> learnedRows;
    for(const auto& spell:learned.array){uint64_t row=0,icon=0;
        if(spell.kind!=J::Object||!spell.Get("spell_row").UInt(row)||row>INT_MAX||
           spell.Get("name").kind!=J::String||spell.Get("name").text.empty()||spell.Get("name").text.size()>512||
           !spell.Get("icon").UInt(icon)||icon>INT_MAX||!learnedRows.insert(row).second)return false;}
    const auto& buffs=view.Get("buff_slots");
    const auto& battle=view.Get("battle_slots");
    if(buffs.kind!=J::Array||buffs.array.size()>64||battle.kind!=J::Array||battle.array.size()>64)return false;
    for(const auto& slot:buffs.array){uint64_t row=0;
        if(slot.kind!=J::Null&&slot.kind!=J::Object)return false;
        if(slot.kind==J::Object&&slot.Get("spell_row").kind!=J::Null&&
           (!slot.Get("spell_row").UInt(row)||row>INT_MAX))return false;}
    for(const auto& entry:battle.array){
        if(entry.kind!=J::Object||entry.Get("kind").kind!=J::String||
           (entry.Get("kind").text!="sequence"&&entry.Get("kind").text!="conditional")||
           entry.Get("slot").kind!=J::Null&&entry.Get("slot").kind!=J::Object)return false;
        uint64_t index=0;if(!entry.Get("index").UInt(index)||index>64)return false;
    }
    // LOCAL companion_heal: rows 0-3 HP (10..90 in 10% steps), 4-5 status.
    const auto& heal=view.Get("heal_slots");
    if(heal.kind!=J::Array||heal.array.size()!=6)return false;
    for(size_t i=0;i<6;++i){const auto& entry=heal.array[i];uint64_t percent=0;
        if(entry.kind!=J::Object||entry.Get("kind").text!=(i<4?"hp":"status")||
           entry.Get("slot").kind!=J::Null&&entry.Get("slot").kind!=J::Object)return false;
        if(i<4&&(!entry.Get("percent").UInt(percent)||percent<10||percent>90||percent%10))return false;}
    return Percent(view.Get("hp_percent"))&&Percent(view.Get("mp_percent"));
}
inline const companion_model::Model* MemberModel() {
    if(!Current())return nullptr;const Mapping* m=Find(state->identity.actor);const auto& model=ModelFor(*m);
    return model.revision&&model.identity.actor==m->actor&&model.identity.generation==m->generation&&model.identity.owner==m->owner&&model.identity.member==m->member?&model:nullptr;
}
inline Pair ItemMetadata(uint64_t itemTemplate) {
    Pair metadata{};if(!itemTemplate||itemTemplate>INT_MAX)return metadata;
    const companion_model::Item* chosen=nullptr;if(const auto* model=MemberModel())for(const auto& row:model->items)
        if(row.second.itemTemplate>0&&static_cast<uint64_t>(row.second.itemTemplate)==itemTemplate&&row.second.quantity){chosen=&row.second;break;}
    companion_model::Bytes display;
    if(!chosen){
        // Native CommonItemInfo supplies the template's actual icon. It is the
        // same f5 -> ItemInfo.f7 producer documented by all_table_semantics,
        // not an invented UID/icon or a lookup in the owner's Inventory.
        using Catalog=void*(__fastcall*)();using LookupItem=Pair*(__fastcall*)(void*,Pair*,int32_t);
        Pair item{};struct Item {Pair& p;~Item(){Release(nullptr,p);}} held{item};
        void* catalog=Call<Catalog>(0x36d510)();if(!catalog)return metadata;
        if(Call<LookupItem>(0x36fe00)(catalog,&item,static_cast<int32_t>(itemTemplate))!=&item||
            !item.object||At<int32_t>(item.object,0xc0)!=static_cast<int32_t>(itemTemplate))return metadata;
        const uint32_t icon=At<uint32_t>(item.object,0xd0);if(!icon)return metadata;
        const auto scalar=[&display](uint8_t key,uint64_t value){display.push_back(key);
            do{display.push_back(static_cast<uint8_t>((value&127)|(value>=128?128:0)));value>>=7;}while(value);};
        // UID zero is a display-only sentinel. Never insert this row in the
        // model/projection or use it to authorize a drag, use, transfer or Save.
        scalar(0x08,0);scalar(0x10,itemTemplate);scalar(0x38,icon);
    }
    const auto& wire=chosen?chosen->wire:display;void* info=NewInfo(nullptr);if(!info)return metadata;
    struct Proto {void* p;~Proto(){DeleteInfo(nullptr,p);}} proto{info};
    if(wire.size()>INT_MAX||!ParseInfo(nullptr,info,wire.data(),static_cast<int>(wire.size())))return metadata;
    Pair entity{};struct Entity {Pair& p;~Entity(){Release(nullptr,p);}} held{entity};
    if(MakeEntity(nullptr,info,entity)&&entity.object)(void)MakeMetadata(nullptr,entity.object,metadata);
    // B03780 leaves B4=0 for display. B4=1 would hide the icon, not fade it.
    // The initial contract permits an icon-only absent-item presentation.
    return metadata;
}
inline Pair SpellMetadata(const companion5_json::Value& value) {
    Pair out{};uint64_t row=0,icon=0;
    if(value.kind!=companion5_json::Value::Object||!value.Get("spell_row").UInt(row)||row>INT_MAX||
       !value.Get("icon").UInt(icon)||icon>INT_MAX||value.Get("name").kind!=companion5_json::Value::String)return out;
    // B079B0's kind1 producer allocates this exact 0x100 shared SlotData
    // control and calls 439F00. Its learned branch writes row/+0, kind/+8,
    // icon/+C and name/+30. Do not call B079B0 or AE360: both read SELF.
    using New=void*(__fastcall*)(size_t);void* block=Call<New>(0xfa0a80)(0x100);
    if(!block)return out;std::memset(block,0,0x100);
    At<uintptr_t>(block,0)=base+0x11b9a40;At<LONG>(block,8)=1;At<LONG>(block,12)=1;
    void* data=static_cast<char*>(block)+0x10;
    using Construct=void(__fastcall*)(void*);Call<Construct>(0x439f00)(data);
    At<int64_t>(data,0)=static_cast<int64_t>(row);At<int32_t>(data,8)=1;
    At<int32_t>(data,0xc)=static_cast<int32_t>(icon);
    *reinterpret_cast<std::string*>(static_cast<char*>(data)+0x30)=value.Get("name").text;
    At<uint8_t>(data,0xb4)=0;
    out={data,block};return out;
}
inline bool SetSlotMetadata(void* slot,const companion5_json::Value& value) {
    if(!slot)return false;Pair metadata{};uint64_t item=0;
    if(value.Get("spell_row").kind!=companion5_json::Value::Null)metadata=SpellMetadata(value);
    else if(value.Get("template").UInt(item))metadata=ItemMetadata(item);
    const bool supplied=value.kind==companion5_json::Value::Null||metadata.object;
    const bool showSpell=metadata.object&&value.Get("spell_row").kind!=companion5_json::Value::Null;
    using Set=void(__fastcall*)(void*,const Pair*);
    Call<Set>(0xb042d0)(slot,&metadata);metadata={};
    // B043A1..C3 true fills ProgressTimer+898 to 100%; B04462..84 toggles
    // that overlay and +880 cooldown text. This is not the spell name.
    // Companion draft slots have no published live cooldown.
    if(showSpell){using Cooldown=void(__fastcall*)(void*,bool);Call<Cooldown>(0xb04350)(slot,false);}
    return supplied&&At<void*>(slot,0x830);
}
inline std::string NodeName(void* node) {
    if(!node)return {};using Get=const String32*(__fastcall*)(void*);
    const String32* name=Vcall<Get>(node,0x278)(node);
    if(!name||name->size>128||name->capacity<name->size)return {};
    const char* data=name->capacity>15?name->pointer:name->inlineBytes;
    return data?std::string(data,name->size):std::string{};
}
inline void* FindSlotNode(void* node,unsigned depth=0) {
    if(!node||depth>12)return nullptr;
    if(void* slot=Cast(node,0x16895c0))return slot;
    void** begin=At<void**>(node,0x178),**end=At<void**>(node,0x180);
    if(!begin||!end||end<begin||end-begin>128)return nullptr;
    for(void** p=begin;p!=end;++p)if(*p)if(void* slot=FindSlotNode(*p,depth+1))return slot;
    return nullptr;
}
inline void* ResourceSlot(const char* resourceName) {
    // Each slot CSB's Node table slot3 is custom class SlotNode; Panel_Slot
    // is its child, so searching down from that panel cannot find the slot.
    // Original ATS adapter 8E3A3E calls A56F30 and casts its returned root at
    // 8E3A85 before B042D0. A57053..56 returns one retained Node reference.
    const String32 resource=Borrow(resourceName);const ResourceFunction callback{};
    void* root=nullptr;
    using Load=void**(__fastcall*)(void**,const String32*,const ResourceFunction*);
    Call<Load>(0xa56f30)(&root,&resource,&callback);
    return root;
}
inline bool AttachPanel(void* panel,void* parent,float x,float y) {
    if(!panel||!parent)return false;
    using Remove=void(__fastcall*)(void*);using Add=void(__fastcall*)(void*,void*);
    if(At<void*>(panel,0x190))Vcall<Remove>(panel,0x220)(panel);
    Vcall<Add>(parent,0x1d0)(parent,panel);
    // ListView::addChild forwards to its inner container at +CE0 (C08F60).
    // The slot root is a Node, so it is not entered in the Widget item vector.
    if(At<void*>(panel,0x190)!=At<void*>(parent,0xce0))return false;
    using Position=void(__fastcall*)(void*,float,float);Vcall<Position>(panel,0x80)(panel,x,y);
    return true;
}
inline Vec2 BuffCell(size_t index) {
    // CONTROL ATSLayout.csb: ListView_Slot is 369x184; the authored
    // BehaviorSlot.csb panel is 62x62 inside its zero-size root.
    return {static_cast<float>(index%6)*61.5f,
            static_cast<float>(2-index/6)*61.0f};
}
inline void RestoreBuffGrid() {
    if(!state||!state->window.layout||state->closePending||!OnUi()||
       state->buffRows.empty())return;
    void* inner=At<void*>(state->buffRows.front(),0x190);if(!inner)return;
    using Position=void(__fastcall*)(void*,float,float);
    for(size_t i=0;i<state->buffRows.size();++i){
        void* row=state->buffRows[i];if(!row||At<void*>(row,0x190)!=inner)continue;
        const Vec2 expected=BuffCell(i),actual=At<Vec2>(row,0x3c);
        if(actual.x!=expected.x||actual.y!=expected.y)
            Vcall<Position>(row,0x80)(row,expected.x,expected.y);
    }
}
inline bool AttachSpellSlot(void* slot,void* list,size_t index) {
    if(!slot||!list)return false;
    // ListView's addChild forwards to its inner Layout. Keep that known-good
    // attachment path; its later layout pass can move zero-size slot roots.
    void* inner=At<void*>(list,0xce0);if(!inner)return false;
    using Remove=void(__fastcall*)(void*);using Add=void(__fastcall*)(void*,void*);
    if(At<void*>(slot,0x190))Vcall<Remove>(slot,0x220)(slot);
    Vcall<Add>(inner,0x1d0)(inner,slot);
    if(At<void*>(slot,0x190)!=inner)return false;
    const size_t cell=index%32;
    const Vec2 position{static_cast<float>(cell%4)*62.0f,
                        static_cast<float>(7-cell/4)*62.0f};
    using Position=void(__fastcall*)(void*,const Vec2*);
    Vcall<Position>(slot,0x88)(slot,&position);
    return true;
}
inline bool SetupSpellTargets() {
    auto& s=*state;if(!s.loaded){s.status="ATS_WINDOW_SPELL_VIEW_UNAVAILABLE";return false;}
    const auto& buffs=s.draft.Get("buff_slots");
    void* list=Lookup(s.window.layout,"Root.Buff.03.ListView_Slot",false);
    if(!list){s.status="ATS_WINDOW_SPELL_BUFF_LIST_UNAVAILABLE";return false;}
    struct Held {void*& node;~Held(){ReleaseNode(node);}} held{list};
    if(buffs.array.size()>18){s.status="ATS_WINDOW_SPELL_BUFF_CAPACITY_REFUSED";return false;}
    for(size_t i=s.buffRows.size();i<buffs.array.size();++i){
        void* row=ResourceSlot("Slot/BehaviorSlot.csb");
        if(!row){s.status="ATS_WINDOW_SPELL_BUFF_RESOURCE_UNAVAILABLE";return false;}
        void* slot=FindSlotNode(row);
        if(!slot){ReleaseNode(row);s.status="ATS_WINDOW_SPELL_BUFF_NODE_UNAVAILABLE";return false;}
        const Vec2 position=BuffCell(i);
        if(!AttachPanel(row,list,position.x,position.y)){
            ReleaseNode(row);s.status="ATS_WINDOW_SPELL_BUFF_ATTACH_UNAVAILABLE";return false;}
        s.buffRows.push_back(row);
        ++At<int32_t>(slot,8);s.buffSlotNodes.push_back(slot);
    }
    bool sequenceFound[8]{},conditionalFound[8]{};
    for(size_t i=0;i<8;++i){
        char path[100]{};
        if(!s.battleSequence[i]){
            sprintf_s(path,"Root.Combat.01.Slot01.Item_%u",static_cast<unsigned>(i));
            void* row=Lookup(s.window.layout,path,false);
            if(row){sequenceFound[i]=true;void* slot=FindSlotNode(row);
                if(slot){++At<int32_t>(slot,8);s.battleSequence[i]=slot;}
                ReleaseNode(row);}
        }
        if(!s.battleConditional[i]){
            sprintf_s(path,"Root.Combat.02.Slot_%02u.Slot.FileNode_1",static_cast<unsigned>(i+1));
            void* row=Lookup(s.window.layout,path,false);
            if(row){conditionalFound[i]=true;void* slot=FindSlotNode(row);
                if(slot){++At<int32_t>(slot,8);s.battleConditional[i]=slot;}
                ReleaseNode(row);}
        }
    }
    for(const auto& entry:s.draft.Get("battle_slots").array){uint64_t index=0;
        if(!entry.Get("index").UInt(index)||index>=8){s.status="ATS_WINDOW_SPELL_BATTLE_INDEX_REFUSED";return false;}
        if(entry.Get("kind").text=="sequence"){
            if(!s.battleSequence[index]){s.status=sequenceFound[index]?
                "ATS_WINDOW_SPELL_SEQUENCE_NODE_UNAVAILABLE":"ATS_WINDOW_SPELL_SEQUENCE_LOOKUP_UNAVAILABLE";return false;}
        }else if(!s.battleConditional[index]){s.status=conditionalFound[index]?
            "ATS_WINDOW_SPELL_CONDITIONAL_NODE_UNAVAILABLE":"ATS_WINDOW_SPELL_CONDITIONAL_LOOKUP_UNAVAILABLE";return false;}}
    if(s.buffSlotNodes.size()!=buffs.array.size()){s.status="ATS_WINDOW_SPELL_BUFF_COUNT_UNAVAILABLE";return false;}
    return true;
}
inline void OptionVisible(const char* suffix,bool visible) {
    std::string path="Root.Option.ListviewScroll.ListView.";path+=suffix;
    void* node=Lookup(state->window.layout,path.c_str(),false);
    if(node){Visible(node,visible);ReleaseNode(node);}
}
inline bool RenderReadOnlyOptions() {
    auto& s=*state;using J=companion5_json::Value;
    const auto& options=s.draft.Get("options");
    // Server policy names: codec.companion_policy maps OptionData f1/f7 to
    // scan_tiles/pickup_weight. CSB paths/text are in resource_trees.json.
    // Do not load the original ATS model or infer a 100 -> Release button.
    const auto& scan=options.Get("scan_tiles");const auto& weight=options.Get("pickup_weight");
    const bool hasScan=s.loaded&&scan.kind==J::Number,hasWeight=s.loaded&&weight.kind==J::Number;
    for(const char* row:{"Panel01.01.Tx_01","Panel01.01.Bg_Textfield01","Panel01.01.Tx_01_00"})
        OptionVisible(row,hasScan);
    OptionVisible("Panel01.01.Tx_Sub01",hasScan);
    OptionVisible("Panel02.02.Tx_Sub01",hasWeight);
    OptionVisible("Panel02.02.Weight Limit",hasWeight);
    if(s.optionScan)SetField(s.optionScan,hasScan?scan.text:std::string{});
    if(s.optionWeight){const std::string text=hasWeight?std::string(u8"획득 무게 제한: ")+weight.text:std::string{};
        SetText(s.optionWeight,text.c_str());
        // Authored label is left anchored, 143px inside a 324px list. Reserve
        // the row width for the exact value, including signed int32 values.
        const Vec2 size{324.0f,20.0f};using Size=void(__fastcall*)(void*,const Vec2*);
        Vcall<Size>(s.optionWeight,0x138)(s.optionWeight,&size);}
    if(options.kind!=J::Null&&options.kind!=J::Object)return false;
    bool complete=true;
    for(const auto& entry:options.object){
        if(entry.first=="scan_tiles")complete=complete&&hasScan&&s.optionScan&&s.optionList&&FieldText(s.optionScan)==scan.text;
        else if(entry.first=="pickup_weight")complete=complete&&hasWeight&&s.optionWeight&&s.optionList;
        else complete=false; // Preserve unknown keys; do not claim to show them.
    }
    return complete;
}
inline void Render() {
    if(!Current())return;auto& s=*state;s.rendering=true;
    struct End {bool& value;~End(){value=false;}} end{s.rendering};
    const auto* model=MemberModel();s.renderedRevision=model?model->revision:0;s.unavailableItems=0;
    s.unsupportedReadOnly=!RenderReadOnlyOptions()||
        s.buffSlotNodes.size()!=s.draft.Get("buff_slots").array.size();
    const char* keys[]={"hp_slots","mp_slots","function_slots"};size_t at=0;
    for(size_t group=0;group<3;++group){const auto& items=s.draft.Get(keys[group]);const size_t count=group==2?6:2;
        for(size_t i=0;i<count;++i,++at){Pair supplied{};uint64_t itemTemplate=0;
            if(s.loaded&&i<items.array.size())(void)items.array[i].Get("template").UInt(itemTemplate);
            supplied=ItemMetadata(itemTemplate);if(itemTemplate&&!supplied.object)++s.unavailableItems;
            if(s.slots[at]){using Set=void(__fastcall*)(void*,const Pair*);
                // B042D0 consumes the supplied shared reference (GearSlots).
                Call<Set>(0xb042d0)(s.slots[at],&supplied);supplied={};
                if(itemTemplate&&!At<void*>(s.slots[at],0x830))++s.unavailableItems;}
            else if(itemTemplate)++s.unavailableItems;
            Release(nullptr,supplied);
        }}
    const char* percents[]={"hp_percent","mp_percent"};for(size_t i=0;i<2;++i){const auto& value=s.draft.Get(percents[i]);
        SetField(s.fields[i],s.loaded?PercentText(value):std::string{});}
    const auto& buffs=s.draft.Get("buff_slots");
    for(size_t i=0;i<s.buffSlotNodes.size()&&i<buffs.array.size();++i)
        if(!SetSlotMetadata(s.buffSlotNodes[i],buffs.array[i]))s.unsupportedReadOnly=true;
    for(const auto& entry:s.draft.Get("battle_slots").array){uint64_t index=0;
        if(!entry.Get("index").UInt(index)||index>=8)continue;
        void* slot=entry.Get("kind").text=="sequence"?s.battleSequence[index]:s.battleConditional[index];
        if(!SetSlotMetadata(slot,entry.Get("slot")))s.unsupportedReadOnly=true;}
    const auto& heal=s.draft.Get("heal_slots");
    for(size_t i=0;i<6&&i<heal.array.size();++i){
        if(s.healSlots[i]&&!SetSlotMetadata(s.healSlots[i],heal.array[i].Get("slot")))s.unsupportedReadOnly=true;
        if(!s.healTexts[i])continue;char text[48]{};uint64_t percent=0;
        if(i<4){(void)heal.array[i].Get("percent").UInt(percent);sprintf_s(text,"HP %u%%",static_cast<unsigned>(percent));}
        else strcpy_s(text,u8"상태 이상");
        SetText(s.healTexts[i],text);}
    // B042D0 may create the Icon child lazily (B046F0 -> B05690).
    // Include those new nodes in the existing UI camera, after binding.
    using Mask=void(__fastcall*)(void*,uint32_t,bool);
    Vcall<Mask>(s.root,0x468)(s.root,2,true);
}
inline int SlotIndex(void* node) noexcept {
    if(!state)return -1;for(size_t i=0;i<10;++i)if(node==state->slots[i])return static_cast<int>(i);return -1;
}
inline int OwnSlotByWorldPoint(const Vec2& point);
inline void SetDraftSlot(size_t index,const companion_model::Item* item) {
    if(!Current()||!state->loaded||state->saving||index>=10)return;
    const char* key=index<2?"hp_slots":index<4?"mp_slots":"function_slots";
    const size_t offset=index<2?index:index<4?index-2:index-4;
    auto& array=state->draft.object[key];if(array.kind!=companion5_json::Value::Array||offset>=array.array.size())return;
    companion5_json::Value value;if(item){value.kind=companion5_json::Value::Object;
        value.object["template"]=companion5_json::Value::Integer(static_cast<uint64_t>(item->itemTemplate));
        // ItemInfo f18 is the existing bag row's display name. It is display
        // metadata only; ownership and the Save selection still use template.
        const auto* name=companion_model::Last(item->fields,18);
        if(name&&name->wire==2&&!name->bytes.empty()&&name->bytes.size()<=512)
            value.object["name"]=companion5_json::Value::Text(std::string(name->bytes.begin(),name->bytes.end()));}
    array.array[offset]=std::move(value);Render();state->status="ATS_WINDOW_DRAFT_CHANGED";
}
inline const companion_model::Item* SourceItem(Record& source,const Pair& incoming) {
    const auto* model=MemberModel();if(!model||!companion3_native::Current(source)||source.kind!=companion_model::Window::Bag||
        source.model!=model||source.projection.revision!=model->revision||!incoming.object||!incoming.control)return nullptr;
    for(const auto& row:source.projection.rows)if(row.metadata.object==incoming.object&&row.metadata.control==incoming.control){
        const auto found=model->items.find(row.uid);if(found!=model->items.end()&&found->second.quantity&&found->second.itemTemplate>0&&
            At<int32_t>(incoming.object,8)==2&&At<int32_t>(incoming.object,0x20)==found->second.itemTemplate)return &found->second;
        break;
    }return nullptr;
}
inline bool ApplyDrop(Record& source,void* node,const Pair& incoming) {
    const int index=SlotIndex(node);
    TraceDrop("ApplyDrop","ENTER",state?state->window.layout:nullptr,state?state->dropComponent:nullptr,node,&incoming,0,index);
    if(!Current()||!state->loaded||state->saving){EmitDrop("ApplyDrop","EDIT_UNAVAILABLE");return false;}
    if(index<0){EmitDrop("ApplyDrop","SLOT_NOT_OWNED");return false;}
    const auto* item=SourceItem(source,incoming);if(!item){state->status="ATS_WINDOW_DROP_SOURCE_REFUSED";EmitDrop("ApplyDrop","SOURCE_REFUSED");return false;}
    // B045F0 consumes only this retained argument; projection ownership stays intact.
    Pair check=incoming;Retain(check);using Accept=bool(__fastcall*)(void*,Pair*);
    if(!Call<Accept>(0xb045f0)(node,&check)){state->status="ATS_WINDOW_DROP_CLASS_REFUSED";EmitDrop("ApplyDrop","CLASS_REFUSED",item->uid,item->quantity);return false;}
    TraceDrop("ApplyDrop","SOURCE_MATCH_CLASS_ACCEPTED",state->window.layout,state->dropComponent,node,&incoming,0,index);
    SetDraftSlot(static_cast<size_t>(index),item);EmitDrop("ApplyDrop","DRAFT_APPLIED",item->uid,item->quantity);return true;
}
inline bool RouteDrop(Record& source,const Pair& incoming,uint64_t point) {
    TraceDrop("RouteDrop","ENTER",state?state->window.layout:nullptr,state?state->dropComponent:nullptr,nullptr,&incoming,point);
    if(!Enabled()||!Current()){TraceDrop("RouteDrop","WINDOW_UNAVAILABLE");return false;}
    if(activeDrop)activeDrop->worldPointBits=point;
    // Observe the exact native manager hit ABI without changing routing.
    Vec2 position{};std::memcpy(&position,&point,sizeof(position));
    using Camera=void*(__fastcall*)(void*,int);using RootHit=bool(__fastcall*)(void*,const Vec2*,void*,void*,bool);
    void* camera=Call<Camera>(0x1d3160)(*reinterpret_cast<void**>(base+0x1809d10),2);
    const bool nativeRootHit=Vcall<RootHit>(state->root,0x480)(state->root,&position,camera,nullptr,true);
    TraceDrop("RouteDrop",nativeRootHit?"NATIVE_ROOT_HIT_TRUE":"NATIVE_ROOT_HIT_FALSE",state->window.layout,state->dropComponent,nullptr,&incoming,point);
    const int owned=OwnSlotByWorldPoint(position);
    TraceDrop("OwnWorldSlot",owned>=0?"ITEM_SLOT_HIT":"NO_ITEM_SLOT_HIT",state->window.layout,state->dropComponent,
        owned>=0?state->slots[owned]:nullptr,&incoming,point,owned);
    // Only the ten editable item cells belong to this route. All other
    // releases continue through the existing bag/owner transfer dispatcher.
    if(owned<0)return false;
    TraceDrop("RouteDrop",Hit(state->window.layout,point)?"LAYOUT_HIT_TRUE":"LAYOUT_HIT_FALSE_BUT_OWN_CELL_HIT",
        state->window.layout,state->dropComponent,state->slots[owned],&incoming,point,owned);
    if(state->dropComponent){using FindSlot=void*(__fastcall*)(void*,uint64_t);
        void* slot=Call<FindSlot>(0x95e010)(state->dropComponent,point);
        TraceDrop("FindSlot",slot?"OWN_COMPONENT_FOUND":"OWN_COMPONENT_MISSING",state->window.layout,state->dropComponent,slot,&incoming,point,SlotIndex(slot));
        // The component also registers read-only/hidden ATS slots. Resolve
        // only our ten editable Panel_Slot bounds before applying the draft.
        (void)ApplyDrop(source,state->slots[owned],incoming);
    }else EmitDrop("FindSlot","COMPONENT_MISSING");
    return true;
}
inline bool TargetDrop(void* node,Pair& incoming) {
    TraceDrop("TargetDrop","108_INVOKED",state?state->window.layout:nullptr,state?state->dropComponent:nullptr,node,&incoming,0,SlotIndex(node));
    Pair held=incoming;incoming={};struct Held {Pair& p;~Held(){Release(nullptr,p);}} release{held};
    if(!Current()||!records||!held.object){EmitDrop("TargetDrop","CONTEXT_UNAVAILABLE");return false;}
    if(SlotIndex(node)<0){EmitDrop("TargetDrop","SLOT_NOT_OWNED");return false;}(void)ApplyDrop(records[0],node,held);return true;
}
// Called only by the existing injected mouse-up diagnostic. This is a snapshot,
// never a synthetic source callback or a manager traversal/target invocation.
inline void ObserveMouseUp(uint64_t point) noexcept {
    if(!Enabled())return;
    __try {
        if(records){auto& bag=records[0];Pair drag{};
            if(bag.dropComponent)drag={At<void*>(bag.dropComponent,0x170),At<void*>(bag.dropComponent,0x178)};
            TraceDrop("mouse-up-source","SNAPSHOT",bag.layout,bag.dropComponent,nullptr,&drag,point);
            TraceDrop("native-manager",bag.dropComponent&&!At<uint8_t>(bag.dropComponent,0x148)?"NOT_OBSERVED_SOURCE_ROUTE_DISABLED":"NOT_OBSERVED",bag.layout,bag.dropComponent);}
        if(state){TraceDrop("mouse-up-target","SNAPSHOT",state->window.layout,state->dropComponent,nullptr,nullptr,point);
            for(size_t i=0;i<10;++i)if(state->slots[i])TraceDrop("mouse-up-slot",At<void*>(state->slots[i],0x830)?"PANEL_SLOT_PRESENT":"PANEL_SLOT_MISSING",
                state->window.layout,state->dropComponent,state->slots[i],nullptr,point,static_cast<int>(i));}
    }__except(EXCEPTION_EXECUTE_HANDLER){TraceDrop("mouse-up","SNAPSHOT_SEH");}
}
inline void BindSlotInput(size_t index) {
    void* slot=state->slots[index];
    // 8E3830 consumes function64 into SlotNode+7C8 (callable at +800).
    using Predicate=std::function<bool(Pair&)>;static_assert(sizeof(Predicate)==64,"native predicate function64");Predicate predicate=[index](Pair& incoming){
        if(index<4){Pair owned=incoming;incoming={};using Test=bool(__fastcall*)(Pair*);
            return Call<Test>(index<2?0x8e6b90:0x8e6cf0)(&owned);}
        // 8F59A0 reads only capture+8, moves/zeros its Pair and delegates to
        // the original item-table classifier for function category index+3.
        struct Capture {uintptr_t unused;int32_t index;};Capture capture{0,static_cast<int32_t>(index-4)};
        using Test=bool(__fastcall*)(void*,Pair*);return Call<Test>(0x8f59a0)(&capture,&incoming);
    };
    using Set=void(__fastcall*)(void*,Predicate*);Call<Set>(0x8e3830)(slot,&predicate);
    // 95C4C0 binds the native slot's two button callbacks; first is empty,
    // second is right-click. Only our draft is cleared; never call 8FCD40.
    const Function empty{};Function clear=[index](void*){try{SetDraftSlot(index,nullptr);}catch(...){++adapterErrors;}};
    Call<Register>(0x95c4c0)(state->inputComponent,slot,&empty,&clear);
}
inline void FieldChanged(size_t index) {
    if(!Current()||!state->loaded||state->rendering||index>=2)return;
    if(state->saving){Render();return;}
    const std::string text=FieldText(state->fields[index]);Visible(At<void*>(state->fields[index],0x700),!text.empty());
    companion5_json::Value value;if(!companion5_json::Parse(text,value)||value.kind!=companion5_json::Value::Number||!Percent(value)){
        state->status="ATS_WINDOW_PERCENT_INVALID";return;}
    state->draft.object[index?"mp_percent":"hp_percent"]=std::move(value);state->status="ATS_WINDOW_DRAFT_CHANGED";
}
inline void BindButton(const char* path,const Function& callback) {
    void* node=Lookup(state->window.layout,path,false);if(!node)return;
    using Assign=void*(__fastcall*)(void*,const Function*);Call<Assign>(0xa5c1e0)(static_cast<char*>(node)+0x4f0,&callback);ReleaseNode(node);
}
inline void CloseHealMenu() {
    if(!state||state->healOpen<0)return;Visible(state->healMenus[state->healOpen],false);state->healOpen=-1;
}
inline bool SetupHealPage();
inline void SelectTab(size_t index) {
    if(!Current()||index>3)return;const char* pages[]={"Root.Buff","Root.Combat","Root.Option","Root.Help","Root.Report"};
    CloseHealMenu();
    if(index==3&&!state->healReady){
        if(state->healAttempted||!SetupHealPage())return;
        Render();
    }
    for(size_t i=0;i<5;++i){void* page=Lookup(state->window.layout,pages[i],false);if(page){Visible(page,i==index);ReleaseNode(page);}}
}
// Borrowed child by authored name (Node children vector +178/+180).
inline void* Child(void* node,const char* name) {
    if(!node)return nullptr;void** begin=At<void**>(node,0x178),**end=At<void**>(node,0x180);
    if(!begin||!end||end<begin||end-begin>256)return nullptr;
    for(void** p=begin;p!=end;++p)if(*p&&NodeName(*p)==name)return *p;
    return nullptr;
}
inline void* ChildPath(void* node,const char* path) {
    std::string rest=path;
    while(node&&!rest.empty()){const size_t dot=rest.find('.');
        node=Child(node,rest.substr(0,dot).c_str());rest=dot==std::string::npos?std::string{}:rest.substr(dot+1);}
    return node;
}
inline void* Retained(void* node) {if(node)++At<int32_t>(node,8);return node;}
inline void* CloneWidget(void* source) {
    if(!source)return nullptr;
    // Frozen CONTROL BF3D24..47 (CSB cached-widget clone): v4C0 creates an
    // autoreleased concrete widget, BF8150 copies properties (v618 includes
    // Button textures), v620 copies children. C22D18 calls autorelease B8EE70.
    using Create=void*(__fastcall*)(void*);using Copy=void(__fastcall*)(void*,void*);
    void* copy=Vcall<Create>(source,0x4c0)(source);if(!copy)return nullptr;
    Retained(copy);Call<Copy>(0xbf8150)(copy,source);Vcall<Copy>(copy,0x620)(copy,source);
    return copy;
}
inline void* CloneNodeTree(void* source) {
    if(!source)return nullptr;
    // ATSLayout.csb Root.Combat.02 is a SingleNode (resource_nodes.tsv:71),
    // not a Widget. Frozen CONTROL B57330 uses source v4C0 to create a Node,
    // copies Node properties, and source v4D0=B579B0 recursively clones its
    // children. B579B0 dispatches Widget children through BF8150/v620 and
    // non-Widgets back through B57330; BF3CD0's native tree clone takes the
    // same Widget branch at BF3D24..47. Retain its autoreleased result as
    // ResourceSlot formerly retained the separate CSB tree.
    using Clone=void*(__fastcall*)(void*);
    return Retained(Call<Clone>(0xb57330)(source));
}
inline bool BindNodeButton(void* node,const Function& callback) {
    void* button=node?Cast(node,0x1686de0):nullptr;if(!button)return false;
    using Assign=void*(__fastcall*)(void*,const Function*);Call<Assign>(0xa5c1e0)(static_cast<char*>(button)+0x4f0,&callback);return true;
}
inline bool SetupHealTabAndSpellButton();
inline bool EditableSpellSlot(const companion5_json::Value& slot);
inline void ResetDraft() {
    if(!Current()||!state->loaded||state->saving)return;
    using J=companion5_json::Value;auto& draft=state->draft;
    // Original Bt_Reset invoke 8F7710 tests the visible Buff/Combat/Option
    // page with v150 and resets only that page's model. Help in this DLL is
    // the LOCAL Recovery tab; its six slots and 50% HP default are local.
    auto shown=[&](const char* path){void* page=Lookup(state->window.layout,path,false);
        using IsVisible=bool(__fastcall*)(void*);const bool active=page&&Vcall<IsVisible>(page,0x150)(page);
        ReleaseNode(page);return active;};
    if(shown("Root.Buff")){
        // ATSLayout.csb help (resource_trees.json:23678) says Reset removes
        // registrations. Original Buff reset 42D880 recreates the empty item
        // and spell slots; 42D96D/42DA41 set HP/MP thresholds to float 80.
        for(const char* key:{"hp_slots","mp_slots","function_slots"})
            for(J& slot:draft.object[key].array)slot={};
        for(J& slot:draft.object["buff_slots"].array)if(EditableSpellSlot(slot))slot={};
        draft.object["hp_percent"]=J::Integer(80);
        draft.object["mp_percent"]=J::Integer(80);
    }else if(shown("Root.Combat")){
        for(J& entry:draft.object["battle_slots"].array)
            if(EditableSpellSlot(entry.Get("slot")))entry.object["slot"]={};
        // Original Combat reset 428BA0..428C37 zeros condition/value too.
        // ats_config_codec.py:_window_battle rejects condition changes, so
        // the companion draft retains them and clears only selections.
    }else if(shown("Root.Help")){
        for(J& entry:draft.object["heal_slots"].array){
            if(EditableSpellSlot(entry.Get("slot")))entry.object["slot"]={};
            if(entry.Get("kind").text=="hp")entry.object["percent"]=J::Integer(50);}
    }else if(shown("Root.Option")){
        // 8F780F/8F7817 set the original Option defaults 100/15; 8F7532..
        // 754A saves working +5D0/+5C0 as OptionData f7/f1 (42F065/42EFEE).
        // The server codec names these pickup_weight/scan_tiles. Preserve
        // opaque option fields, whose original bytes have no local meaning.
        J& options=draft.object["options"];options.kind=J::Object;
        options.object["scan_tiles"]=J::Integer(15);
        options.object["pickup_weight"]=J::Integer(100);
    }
    Render();state->status="ATS_WINDOW_RESET";
}
inline bool SetupWidgets() {
    auto& s=*state;
    // Same native root-owned components as ATS initialize, independently of
    // ATS globals/subscriptions. CONTROL95D57D->95E770 recursively discovers
    // SlotNodes, initializes B042D0/Panel_Slot and appends +158/+160;95D5BF
    // attaches via root v3D8. The manager uses RegisterLayout's name/parent,
    // not a separate target list.95E010 computes current transforms at drop.
    // Do not add duplicate registration or touch the original ATS model.
    using Create=void*(__fastcall*)(void*);Step("CREATE_SLOT_DROP_COMPONENT");
    s.dropComponent=Call<Create>(0x95cfa0)(s.root);
    Step("CREATE_SLOT_INPUT_COMPONENT");s.inputComponent=Call<Create>(0x95c250)(s.root);
    if(!s.dropComponent||!s.inputComponent){s.status="ATS_WINDOW_SLOT_COMPONENT_UNAVAILABLE";return false;}
    using Target=std::function<bool(void*,Pair&)>;static_assert(sizeof(Target)==64,"native target function64");
    Target target=[](void* node,Pair& incoming){try{return TargetDrop(node,incoming);}catch(...){++adapterErrors;return false;}};
    // 8F2300 swaps native function64 wrappers; local destroys the old value.
    using Swap=void(__fastcall*)(Target*,void*);Call<Swap>(0x8f2300)(&target,static_cast<char*>(s.dropComponent)+0x108);
    isolatedAtsRoute=&RouteDrop;
    const char* paths[]={"Root.Buff.01.Slot01.Item01","Root.Buff.01.Slot01.Item02","Root.Buff.01.Slot02.Item01","Root.Buff.01.Slot02.Item02",
        "Root.Buff.02.Slot01.Item_0","Root.Buff.02.Slot01.Item_1","Root.Buff.02.Slot01.Item_2","Root.Buff.02.Slot01.Item_3","Root.Buff.02.Slot01.Item_4","Root.Buff.02.Slot01.Item_5"};
    for(size_t i=0;i<10;++i)if(!(s.slots[i]=Typed(paths[i],0x16895c0))){s.status="ATS_WINDOW_SLOT_UNAVAILABLE";return false;}
    for(size_t i=0;i<10;++i)BindSlotInput(i);
    s.fields[0]=Typed("Root.Buff.01.HPTextField.TextField_23",0x1686e08);
    s.fields[1]=Typed("Root.Buff.01.MPTextField.TextField_23_0",0x1686e08);
    if(!s.fields[0]||!s.fields[1]){s.status="ATS_WINDOW_PERCENT_FIELD_UNAVAILABLE";return false;}
    for(size_t i=0;i<2;++i){using Event=std::function<void(void*,int)>;Event callback=[i](void*,int){try{FieldChanged(i);}catch(...){++adapterErrors;}};
        using Assign=void*(__fastcall*)(void*,const Event*);Call<Assign>(0xc03800)(static_cast<char*>(s.fields[i])+0x720,&callback);}
    s.optionScan=Typed("Root.Option.ListviewScroll.ListView.Panel01.01.Bg_Textfield01.TextField",0x1686e08);
    s.optionWeight=Lookup(s.window.layout,"Root.Option.ListviewScroll.ListView.Panel02.02.Weight Limit.Tx_Sub01",true);
    s.optionList=Lookup(s.window.layout,"Root.Option.ListviewScroll.ListView",false);
    // EmptyModelCallbacks already removed the native TextField callback.
    // Disable native text input too: these options are views, not draft edits.
    if(s.optionScan){using Touch=void(__fastcall*)(void*,bool);Vcall<Touch>(s.optionScan,0x530)(s.optionScan,false);}
    // The server does not publish these policies. Do not expose CSB sample
    // values/buttons as if they were the companion's saved settings.
    for(const char* row:{"Panel01.01.Tx_02","Panel01.01.Bg_Textfield02","Panel01.01.Tx_02_00",
        "Panel01.01.Item","Panel01.01.Manner","Panel01.01.Attack","Panel02.02.Loot Attempt",
        "Panel02.02.Weight Limit.Bt_Release","Panel02.02.Weight Limit.Bt_49","Panel02.02.Weight Limit.Bt_82","Panel03"})
        OptionVisible(row,false);
    if(s.optionList){using Refresh=void(__fastcall*)(void*);Vcall<Refresh>(s.optionList,0x650)(s.optionList);}
    BindButton("Root.Bottom.Bt_Save",[](void*){try{Save();}catch(...){++adapterErrors;if(state)state->status="ATS_WINDOW_SAVE_EXCEPTION";}});
    BindButton("Root.Bottom.Bt_Reset",[](void*){try{ResetDraft();}catch(...){++adapterErrors;if(state)state->status="ATS_WINDOW_RESET_EXCEPTION";}});
    const char* tabs[]={"Root.Tab.Bt_Buff","Root.Tab.Bt_Combat","Root.Tab.Bt_Option","Root.Tab.Bt_Help"};
    for(size_t i=0;i<4;++i)BindButton(tabs[i],[i](void*){SelectTab(i);});
    if(!SetupHealTabAndSpellButton())return false;
    const char* hidden[]={"Root.Bottom.Bt_Play","Root.Bottom.Bt_Quit","Root.Bottom.Tx_Time","Root.Report"};
    for(const char* path:hidden){void* node=Lookup(s.window.layout,path,false);if(node){Visible(node,false);ReleaseNode(node);}}
    // The CSB authors every condition pulldown list expanded; original ATS
    // initialization (not called) collapses them. Open lists cover Bt_Save.
    for(unsigned i=1;i<=8;++i){char path[64]{};
        sprintf_s(path,"Root.Combat.02.Slot_%02u.Pulldown_Menu.Sub_Menu",i);
        void* node=Lookup(s.window.layout,path,false);if(node){Visible(node,false);ReleaseNode(node);}}
    // The authored frame remains the target surface; existing server rows
    // are populated after the owned view arrives.
    for(const char* path:{"Root.Buff.03","Root.Buff.03.Slot01"}){
        void* node=Lookup(s.window.layout,path,false);if(node){Visible(node,true);ReleaseNode(node);}}
    Render();return true;
}
inline bool ReadJson(const char* filename,companion5_json::Value& value) {
    forward_diagnostic::Context c{};if(!forward_diagnostic::context(c)||!manual_move::SameOwner(c)||!manual_move::CorrectThread(c))return false;
    wchar_t path[600]{};swprintf_s(path,L"%s\\%hs",c.directory,filename);
    HANDLE file=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_DELETE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    LARGE_INTEGER size{};const bool bounded=GetFileSizeEx(file,&size)&&size.QuadPart>0&&size.QuadPart<=65536;
    std::string bytes;if(bounded)bytes.resize(static_cast<size_t>(size.QuadPart));DWORD count=0;
    const bool good=bounded&&ReadFile(file,bytes.data(),static_cast<DWORD>(bytes.size()),&count,nullptr)&&count==bytes.size();
    const bool closed=CloseHandle(file)!=FALSE;
    return good&&closed&&bytes.find('\0')==std::string::npos&&companion5_json::Parse(bytes,value);
}
inline const char* SupplyImpl(bool result,uint64_t member,uint64_t epoch,uint64_t event,const char* filename) {
    if(!Enabled()||!Current()||member!=state->identity.member)return "ATS_WINDOW_STALE";auto& s=*state;
    if(!companion5_json::Basename(filename,result?"companion-ats-result-":"companion-ats-view-"))return "ATS_WINDOW_BASENAME_REFUSED";
    if(result){if(event!=(s.saving?s.saveEvent:s.openEvent)||(s.loaded&&epoch!=s.editEpoch))return "ATS_WINDOW_STALE";}
    else if(s.loaded||event!=s.openEvent||!epoch)return "ATS_WINDOW_STALE";
    companion5_json::Value payload;if(!ReadJson(filename,payload))return "ATS_WINDOW_JSON_REFUSED";
    if(!result){if(!ValidView(payload,member,epoch))return "ATS_WINDOW_VIEW_REFUSED";RetireSpell();s.baseline=payload;s.draft=payload;s.editEpoch=epoch;s.loaded=true;
        const bool spellTargets=SetupSpellTargets();Render();
        if(!spellTargets)return s.status;
        s.status=s.unavailableItems?"ATS_WINDOW_VIEW_PARTIAL_ITEMS_UNAVAILABLE":s.unsupportedReadOnly?"ATS_WINDOW_VIEW_PARTIAL_READONLY_UNAVAILABLE":"ATS_WINDOW_ITEMS_PERCENT_APPLIED";return s.status;}
    uint64_t m=0,e=0;if(payload.Get("schema").text!="companion-ats-result-v1"||!payload.Get("member_id").UInt(m)||m!=member||!payload.Get("edit_epoch").UInt(e)||e!=epoch)return "ATS_WINDOW_RESULT_REFUSED";
    s.saving=false;s.resultReason=payload.Get("reason").text;
    if(payload.Get("status").text!="OK"){s.status="ATS_WINDOW_SERVER_REFUSED";return s.status;}
    const auto& view=payload.Get("view");if(!ValidView(view,member,epoch)){s.loaded=false;s.status="ATS_WINDOW_SAVED_VIEW_UNAVAILABLE";return s.status;}
    if(s.draft.Get("learned_spells")!=view.Get("learned_spells"))RetireSpell();
    s.baseline=view;s.draft=view;s.editEpoch=epoch;s.loaded=true;
    const bool spellTargets=SetupSpellTargets();Render();
    if(!spellTargets)return s.status;
    s.status=s.unavailableItems||s.unsupportedReadOnly?"ATS_WINDOW_SAVED_VIEW_PARTIAL":"ATS_WINDOW_SAVED_ITEMS_PERCENT_APPLIED";return s.status;
}
inline const char* SupplyTry(bool result,uint64_t member,uint64_t epoch,uint64_t event,const char* filename) {
    try{return SupplyImpl(result,member,epoch,event,filename);}catch(...){++adapterErrors;return "ATS_WINDOW_SUPPLY_EXCEPTION";}
}
inline const char* Supply(bool result,uint64_t member,uint64_t epoch,uint64_t event,const char* filename) noexcept {
    __try{return SupplyTry(result,member,epoch,event,filename);}
    __except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;if(state){state->rendering=false;state->status="ATS_WINDOW_SUPPLY_SEH";}return "ATS_WINDOW_SUPPLY_SEH";}
}
inline void Save() {
    if(!Current()||!state->loaded||state->saving)return;auto& s=*state;
    // Re-read actual native strings on Save, including an event still pending
    // in the native input queue; never serialize an invalid/blank new percent.
    const char* percents[]={"hp_percent","mp_percent"};for(size_t i=0;i<2;++i){const auto text=FieldText(s.fields[i]);
        if(text.empty()&&s.draft.Get(percents[i]).kind==companion5_json::Value::Null)continue;
        companion5_json::Value value;if(!companion5_json::Parse(text,value)||value.kind!=companion5_json::Value::Number||!Percent(value)){s.status="ATS_WINDOW_PERCENT_INVALID";return;}
        s.draft.object[percents[i]]=std::move(value);}
    using J=companion5_json::Value;J delta;delta.kind=J::Object;delta.object["member_id"]=J::Integer(s.identity.member);delta.object["edit_epoch"]=J::Integer(s.editEpoch);
    // Unknown option keys remain in baseline/draft but are never echoed to
    // the server. Only the two source-mapped Option Reset fields are editable.
    for(const char* key:{"hp_slots","mp_slots","function_slots"})
        if(s.draft.Get(key)!=s.baseline.Get(key))delta.object[key]=s.draft.Get(key);
    for(const char* key:{"hp_percent","mp_percent"})
        if(!SamePercent(s.draft.Get(key),s.baseline.Get(key)))delta.object[key]=s.draft.Get(key);
    for(const char* key:{"buff_slots","battle_slots"})
        if(s.draft.Get(key)!=s.baseline.Get(key))delta.object[key]=s.draft.Get(key);
    J options;options.kind=J::Object;
    for(const char* key:{"scan_tiles","pickup_weight"})
        if(s.draft.Get("options").Get(key)!=s.baseline.Get("options").Get(key))
            options.object[key]=s.draft.Get("options").Get(key);
    if(!options.object.empty())delta.object["options"]=std::move(options);
    if(s.draft.Get("heal_slots")!=s.baseline.Get("heal_slots")){J rows;rows.kind=J::Array;
        for(const auto& entry:s.draft.Get("heal_slots").array){J row;row.kind=J::Object;
            const auto& slot=entry.Get("slot");row.object["spell_row"]=slot.kind==J::Object?slot.Get("spell_row"):J{};
            if(entry.Get("kind").text=="hp")row.object["percent"]=entry.Get("percent");
            rows.array.push_back(std::move(row));}
        delta.object["heal_slots"]=std::move(rows);}
    if(delta.object.size()==2){s.status="ATS_WINDOW_NO_CHANGES";return;}
    const std::string bytes=companion5_json::Encode(delta);forward_diagnostic::Context c{};
    if(bytes.size()>65536||!forward_diagnostic::context(c)||!manual_move::SameOwner(c)||!manual_move::CorrectThread(c)){s.status="ATS_WINDOW_DELTA_CONTEXT_REFUSED";return;}
    static uint64_t sequence=[](){FILETIME now{};GetSystemTimeAsFileTime(&now);return (static_cast<uint64_t>(now.dwHighDateTime)<<32)|now.dwLowDateTime;}();
    char name[96]{};wchar_t path[600]{};bool wrote=false;
    for(unsigned attempt=0;attempt<64&&!wrote;++attempt){if(sequence==UINT64_MAX){s.status="ATS_WINDOW_DELTA_SEQUENCE_EXHAUSTED";return;}
        sprintf_s(name,"companion-ats-delta-%llu.json",static_cast<unsigned long long>(++sequence));swprintf_s(path,L"%s\\%hs",c.directory,name);
        wrote=WriteNew(path,bytes.data(),static_cast<DWORD>(bytes.size()));if(!wrote&&GetLastError()!=ERROR_FILE_EXISTS&&GetLastError()!=ERROR_ALREADY_EXISTS)break;}
    if(!wrote){s.status="ATS_WINDOW_DELTA_WRITE_FAILED";return;}
    s.saveEvent=EnqueueAtsWindow(s.identity,true,s.editEpoch,name);s.saving=s.saveEvent!=0;s.status=s.saving?"ATS_WINDOW_SAVE_QUEUED":"ATS_WINDOW_SAVE_ENQUEUE_REFUSED";
}
inline void EmptyModelCallbacks(void* node) {
    // Button/TextField RTTI descriptors from the same CONTROL strings:
    // 1686DE0+10=Button, 1686E08+10=TextField. No ATS Initialize is called.
    // Read function64's target at +38 first: a CSB-only widget can already
    // be empty. Authored tab Buttons follow this same recursive +4F0 path.
    Step("DISABLE_BUTTON_CAST");if(void* button=Cast(node,0x1686de0)){
        void* callback=static_cast<char*>(button)+0x4f0;
        Step("DISABLE_BUTTON_CALLBACK");if(At<void*>(callback,0x38)){
            const Function empty{};using Assign=void*(__fastcall*)(void*,const Function*);
            Call<Assign>(0xa5c1e0)(callback,&empty);
        }
    }
    Step("DISABLE_TEXTFIELD_CAST");if(void* field=Cast(node,0x1686e08)){
        // Original 8E450B/8E4519 and 8E9327/8E9332 pass field+720,
        // not the TextField itself. C0382E reads source+38; C03851 reads
        // destination+38; C0386B..78 destroys the replaced callable via v20.
        // C0387C returns the destination function object. Keep native copy/
        // swap/destruction for occupied slots, including inline callables.
        void* callback=static_cast<char*>(field)+0x720;
        Step("DISABLE_TEXTFIELD_CALLBACK");if(At<void*>(callback,0x38)){
            using Event=std::function<void(void*,int)>;const Event empty{};
            static_assert(sizeof(Event)==64,"native TextField event function64");
            using Assign=void*(__fastcall*)(void*,const Event*);Call<Assign>(0xc03800)(callback,&empty);
        }
        SetField(field,{});
    }
    // Every CSB example SlotNode starts empty. No ATS model population or
    // original ATS right-click/classification callable is installed here.
    if(void* slot=Cast(node,0x16895c0)){Pair empty{};using Set=void(__fastcall*)(void*,const Pair*);Call<Set>(0xb042d0)(slot,&empty);}
    // 9082B0 finds UIDropSlotComponent on this Node (B5B090 + RTTI).
    // Empty +C8 and disable its route, including authored nested components.
    using Find=void*(__fastcall*)(void*);Step("DISABLE_DROP_FIND");if(void* drop=Call<Find>(0x9082b0)(node)){
        void* callback=static_cast<char*>(drop)+0xc8;
        Step("DISABLE_DROP_CALLBACK");if(At<void*>(callback,0x38)){
            DropAction empty{};using Swap=void*(__fastcall*)(void*,DropAction*);
            Call<Swap>(0x9086d0)(callback,&empty);
        }
        At<uint8_t>(drop,0x148)=0;
    }
    // Node v1F8=1498E0 returns self+178; v200=B58000 reads end+180.
    // Component slot vectors at +158/+160 are a different native container.
    Step("DISABLE_CHILDREN");auto** begin=At<void**>(node,0x178);auto** end=At<void**>(node,0x180);
    for(auto** p=begin;p&&p!=end;++p)if(*p)EmptyModelCallbacks(*p);
}
inline void* SceneParent(void* manager,void* root) {
    // B3AF17..B3B01F: metadata95EB80+40 -> manager+3D8 map<int,Node*>.
    // Read the existing native tree; never insert a missing/null parent.
    Step("ATTACH_PARENT_METADATA");using Metadata=void*(__fastcall*)(void*);void* metadata=Call<Metadata>(0x95eb80)(root);
    if(!metadata)return nullptr;const int32_t key=At<int32_t>(metadata,0x40);
    void* head=At<void*>(manager,0x3d8);if(!head)return nullptr;
    void* current=At<void*>(head,8);void* found=head;
    while(!At<uint8_t>(current,0x19)){
        if(At<int32_t>(current,0x20)>=key){found=current;current=At<void*>(current,0);}
        else current=At<void*>(current,0x10);
    }
    return found!=head&&At<int32_t>(found,0x20)==key?At<void*>(found,0x28):nullptr;
}
inline void Construct(void* node) {
    auto& s=*state;auto& r=s.window;if(!node||!s.creating||r.layout)return;
    // Resource callbacks may receive other Ref types. Match the existing
    // B3F350 source Ref -> Node dynamic cast before reading Node's name slot.
    using DynamicCast=void*(__fastcall*)(void*,long,void*,void*,int);
    Step("RESOURCE_CALLBACK_CAST");void* typed=Call<DynamicCast>(0xfa1ad3)(node,0,reinterpret_cast<void*>(base+0x16d87a8),reinterpret_cast<void*>(base+0x166ec80),0);
    if(!typed)return;using Name=const String32*(__fastcall*)(void*);
    Step("RESOURCE_CALLBACK_NAME");const String32* name=Vcall<Name>(typed,0x278)(typed);if(!name)return;
    const char* text=name->capacity>15?name->pointer:name->inlineBytes;
    if(name->size!=9||!text||std::memcmp(text,"ATSLayout",9))return;
    s.status="ATS_WINDOW_GENERIC_CONSTRUCT";
    // 8E3330 returns CreatableLayout vptr120FA80 and retains Node+30.
    // 8E37D0 is its native deleting dtor and frees exactly B8 bytes.
    Step("LAYOUT_ALLOCATE");using New=void*(__fastcall*)(size_t);void* object=Call<New>(0xfa0a80)(0xb8);
    Step("CREATABLE_LAYOUT_CTOR");using Ctor=void*(__fastcall*)(void*,void*);Call<Ctor>(0x8e3330)(object,typed);
    Step("SHARED_OWNER_CONSTRUCT");
    const std::shared_ptr<void> owner(object,&DeleteLayout,GameAllocator<char>{});
    static_assert(sizeof(std::weak_ptr<void>)==16,"native MSVC weak owner Pair16");
    // A0D726..A0D7A6 (existing Inventory factory) binds shared_from_this:
    // {self+8=object,self+10=control}, strong+8, weak+C, releasing replaced weak.
    // The constructor zeroes these cells. MSVC weak_ptr performs exactly that
    // one weak retain on this same standard control ABI; native A0FF30..4B
    // decrements weak+C on destruction. A10D6C..9E upgrades strong+8 for show.
    Step("WEAK_OWNER_CONSTRUCT");new (static_cast<char*>(object)+8) std::weak_ptr<void>(owner);
    Step("SHARED_OWNER_RETAIN");std::memcpy(&s.owner,&owner,sizeof(s.owner));Retain(s.owner);
    r.layout=object;s.root=At<void*>(object,0x30);
    r.nativeVtable=At<uintptr_t*>(object,0);
    // 22 entries plus COL (120FA80..120FB30); retain generic Close/ESC.
    Step("GENERIC_VTABLE_INSTALL");std::memcpy(r.localVtable,r.nativeVtable-1,23*sizeof(uintptr_t));
    r.localVtable[1+0x70/8]=reinterpret_cast<uintptr_t>(&ShowWindow);
    r.localVtable[1+0xa0/8]=reinterpret_cast<uintptr_t>(&ConsumeCommand);
    At<uintptr_t*>(object,0)=r.localVtable+1;
    // A11D90 calls generic manager/input initialization A0FF60, without ATS
    // model/inventory subscriptions. Never call 8FCFE0/8E3E60/8FBFE0.
    Step("GENERIC_INITIALIZE");Call<Init>(0xa11d90)(object,4);At<uint8_t>(object,0x21)=1;
}
struct PlacementAffine {float a,b,c,d,tx,ty;};
struct PlacementRect {float left,bottom,right,top;};
inline void* PlacementScene(void* node) {
    for(unsigned depth=0;node&&depth<32;++depth){void* parent=At<void*>(node,0x190);if(!parent)return node;node=parent;}
    return nullptr;
}
inline bool PlacementTransform(void* node,void* scene,PlacementAffine& transform) {
    if(node==scene){transform={1,0,0,1,0,0};return true;}
    // The same native Node-to-ancestor affine used by OptionalTitle. Native
    // accumulation preserves authored anchor/scale and excludes the scene.
    using ToAncestor=PlacementAffine*(__fastcall*)(void*,PlacementAffine*,void*);
    Call<ToAncestor>(0xb5a1d0)(node,&transform,scene);
    return std::isfinite(transform.a)&&std::isfinite(transform.b)&&std::isfinite(transform.c)&&
        std::isfinite(transform.d)&&std::isfinite(transform.tx)&&std::isfinite(transform.ty);
}
inline bool PlacementBounds(void* node,void* scene,PlacementRect& rect) {
    const Vec2 size=At<Vec2>(node,0x6c);PlacementAffine t{};
    if(!std::isfinite(size.x)||!std::isfinite(size.y)||size.x<=0||size.y<=0||!PlacementTransform(node,scene,t))return false;
    const float x[]={t.tx,t.tx+t.a*size.x,t.tx+t.c*size.y,t.tx+t.a*size.x+t.c*size.y};
    const float y[]={t.ty,t.ty+t.b*size.x,t.ty+t.d*size.y,t.ty+t.b*size.x+t.d*size.y};
    rect={x[0],y[0],x[0],y[0]};
    for(unsigned i=0;i<4;++i){rect.left=(std::min)(rect.left,x[i]);rect.right=(std::max)(rect.right,x[i]);
        rect.bottom=(std::min)(rect.bottom,y[i]);rect.top=(std::max)(rect.top,y[i]);}
    return std::isfinite(rect.left)&&std::isfinite(rect.bottom)&&std::isfinite(rect.right)&&std::isfinite(rect.top)&&
        rect.right>rect.left&&rect.top>rect.bottom;
}
inline void HealPercent(size_t row,unsigned percent) {
    CloseHealMenu();if(!Current()||!state->loaded||state->saving||row>=4)return;
    auto& heal=state->draft.object["heal_slots"];if(heal.kind!=companion5_json::Value::Array||row>=heal.array.size())return;
    heal.array[row].object["percent"]=companion5_json::Value::Integer(percent);Render();state->status="ATS_WINDOW_DRAFT_CHANGED";
}
inline void ToggleHealMenu(size_t row) {
    if(!Current()||row>=4||!state->healMenus[row])return;auto& s=*state;
    if(s.healOpen==static_cast<int>(row)){CloseHealMenu();return;}
    CloseHealMenu();if(!s.loaded||s.saving)return;
    // Draw (and touch) the opened row above the rows its list covers.
    void* rowNode=s.healRows[row];void* parent=rowNode?At<void*>(rowNode,0x190):nullptr;
    if(parent){using Remove=void(__fastcall*)(void*);using Add=void(__fastcall*)(void*,void*);
        Vcall<Remove>(rowNode,0x220)(rowNode);Vcall<Add>(parent,0x1d0)(parent,rowNode);
        using Mask=void(__fastcall*)(void*,uint32_t,bool);Vcall<Mask>(rowNode,0x468)(rowNode,2,true);}
    Visible(s.healMenus[row],true);s.healOpen=static_cast<int>(row);
}
// Keep a resized node's top edge where the CSB authored it (anchor-agnostic).
inline void ResizeKeepTop(void* node,float height) {
    void* parent=node?At<void*>(node,0x190):nullptr;if(!parent)return;
    PlacementAffine before{},after{};const Vec2 old=At<Vec2>(node,0x6c);
    if(!PlacementTransform(node,parent,before))return;
    const Vec2 size{old.x,height};using Size=void(__fastcall*)(void*,const Vec2*);Vcall<Size>(node,0x138)(node,&size);
    if(!PlacementTransform(node,parent,after))return;
    const float shift=(before.ty+before.d*old.y)-(after.ty+after.d*height);
    const Vec2 position=At<Vec2>(node,0x3c);using Position=void(__fastcall*)(void*,float,float);
    Vcall<Position>(node,0x80)(node,position.x,position.y+shift);
}
inline bool SetupHealTabAndSpellButton() {
    auto& s=*state;
    // Tab label/order: reuse the Help tab (its button already selects Root.Help)
    // and swap Option/Help button positions -> Buff / Combat / Recovery / Option.
    if(void* label=Lookup(s.window.layout,"Root.Tab.Bt_Help.Tx_Help",true)){SetText(label,u8"회복");ReleaseNode(label);}
    void* option=Lookup(s.window.layout,"Root.Tab.Bt_Option",false),*help=Lookup(s.window.layout,"Root.Tab.Bt_Help",false);
    if(option&&help){const Vec2 a=At<Vec2>(option,0x3c),b=At<Vec2>(help,0x3c);using Position=void(__fastcall*)(void*,float,float);
        Vcall<Position>(option,0x80)(option,b.x,b.y);Vcall<Position>(help,0x80)(help,a.x,a.y);}
    ReleaseNode(option);ReleaseNode(help);
    void* page=Lookup(s.window.layout,"Root.Help",false);if(!page){s.status="ATS_WINDOW_HEAL_PAGE_UNAVAILABLE";return false;}
    struct PageHeld {void*& node;~PageHeld(){ReleaseNode(node);}} pageHeld{page};
    for(const char* name:{"Bg_Black","Main","General","Buffs","Combat","Options"})Visible(Child(page,name),false);
    // Clone just the original Buff button; do not parse/clone the entire
    // 242 KB ATS tree merely to show the bottom-bar button on initial open.
    void* source=Lookup(s.window.layout,"Root.Buff.02.Bt",false);
    void* spell=CloneWidget(source);ReleaseNode(source);
    void* bottom=Lookup(s.window.layout,"Root.Bottom",false);
    if(!bottom||!spell){ReleaseNode(bottom);ReleaseNode(spell);s.status="ATS_WINDOW_SPELL_BUTTON_UNAVAILABLE";return false;}
    EmptyModelCallbacks(spell);
    if(void* label=Child(spell,"Tx_Transform"))SetText(label,u8"마법창");
    void* root=At<void*>(bottom,0x190);if(!root){ReleaseNode(spell);ReleaseNode(bottom);s.status="ATS_WINDOW_SPELL_BUTTON_UNAVAILABLE";return false;}
    const Vec2 bar=At<Vec2>(bottom,0x3c);
    using Add=void(__fastcall*)(void*,void*);using Position=void(__fastcall*)(void*,float,float);
    Vcall<Add>(root,0x1d0)(root,spell);
    // glfw100: Button anchor near (0,0.1), Bottom at Root (0,-37).
    Vcall<Position>(spell,0x80)(spell,bar.x+162.0f,bar.y+49.5f);
    BindNodeButton(spell,[](void*){(void)OpenSpell();});
    ReleaseNode(spell);ReleaseNode(bottom);return true;
}
inline bool SetupHealPage() {
    auto& s=*state;s.healAttempted=true;
    const ULONGLONG started=GetTickCount64();
    struct Timed {ULONGLONG start;~Timed(){state->healSetupMs=GetTickCount64()-start;}} timed{started};
    void* page=Lookup(s.window.layout,"Root.Help",false);if(!page){s.status="ATS_WINDOW_HEAL_PAGE_UNAVAILABLE";return false;}
    struct PageHeld {void*& node;~PageHeld(){ReleaseNode(node);}} pageHeld{page};
    // Clone the already-loaded Combat.02; no second 242 KB ATSLayout.csb
    // parse. C0A1F0..C0A29B recreates each ListView _items Widget and adds
    // it to the clone's new +CE0 container; BF8150 copies owned callbacks.
    // EmptyModelCallbacks below removes the copied native model callbacks.
    // SlotNode v4C0 clears its dynamic +830 cache, then B042D0->B046F0
    // invokes B05690 on first metadata bind to locate its cloned Panel_Slot.
    void* source=Lookup(s.window.layout,"Root.Combat.02",false);
    void* fragment=CloneNodeTree(source);ReleaseNode(source);
    if(!fragment){s.status="ATS_WINDOW_HEAL_FRAGMENT_UNAVAILABLE";return false;}
    s.healFragment=fragment;
    using Remove=void(__fastcall*)(void*);using Add=void(__fastcall*)(void*,void*);using Position=void(__fastcall*)(void*,float,float);
    EmptyModelCallbacks(fragment);
    // Rows 7-8 lend three list panels to each HP row (6 authored + 3 = 10..90%).
    std::vector<void*> spare;
    for(unsigned row=5;row<=8;++row){char path[96]{};sprintf_s(path,"Slot_%02u.Pulldown_Menu.Sub_Menu.ListView",row);
        void* list=ChildPath(fragment,path);void* inner=list?At<void*>(list,0xce0):nullptr;
        for(const char* name:{"Panel","Panel_0","Panel_1","Panel_2","Panel_3","Panel_4"})if(void* panel=Child(inner,name))spare.push_back(Retained(panel));}
    if(spare.size()<12){for(void*& panel:spare)ReleaseNode(panel);s.status="ATS_WINDOW_HEAL_PANELS_UNAVAILABLE";return false;}
    size_t lent=0;
    for(size_t i=0;i<6;++i){char name[16]{};sprintf_s(name,"Slot_%02u",static_cast<unsigned>(i+1));
        void* row=Child(fragment,name);void* slot=row?FindSlotNode(ChildPath(row,"Slot.FileNode_1")):nullptr;
        void* text=row?ChildPath(row,"Pulldown_Menu.Text"):nullptr;
        if(!row||!slot||!text){for(void*& panel:spare)ReleaseNode(panel);s.status="ATS_WINDOW_HEAL_ROW_UNAVAILABLE";return false;}
        // B03F90 clones Combat's already-rendered children. B05690's first
        // bind creates a NEW Gen_OutlineIcon and caches only it at slot+820;
        // B05210 then clears that cache, leaving an inherited visible copy.
        // Live glfw132 confirmed the uncached duplicate after battle seeding.
        // Retire only inherited generated children, using native parent release.
        // Preserve an already-bound cache owner, if one exists.
        if(void* panel=Child(slot,"Panel_Slot")){
            std::vector<void*> inherited;
            auto** begin=At<void**>(panel,0x178);auto** end=At<void**>(panel,0x180);
            for(auto** child=begin;child&&child!=end;++child)if(*child&&
                *child!=At<void*>(slot,0x820)&&NodeName(*child)=="Gen_OutlineIcon")
                inherited.push_back(Retained(*child));
            for(void*& child:inherited){Vcall<Remove>(child,0x220)(child);ReleaseNode(child);}
        }
        s.healRows[i]=Retained(row);s.healSlots[i]=Retained(slot);s.healTexts[i]=Retained(text);
        Visible(Child(row,"Bg_TextField"),false);
        void* menu=ChildPath(row,"Pulldown_Menu.Sub_Menu");
        if(i>=4){Visible(ChildPath(row,"Pulldown_Menu.Bt_Pdn"),false);
            // Status rows have no list; dropping it also frees the lent panels' old ListView.
            if(menu)Vcall<Remove>(menu,0x220)(menu);continue;}
        s.healMenus[i]=Retained(menu);Visible(menu,false);
        void* list=ChildPath(menu,"ListView");void* inner=list?At<void*>(list,0xce0):nullptr;
        std::vector<void*> panels;
        for(const char* panel:{"Panel","Panel_0","Panel_1","Panel_2","Panel_3","Panel_4"})if(void* p=Child(inner,panel))panels.push_back(p);
        for(unsigned k=0;k<3;++k){void* panel=spare[lent++];
            Vcall<Remove>(panel,0x220)(panel);Vcall<Add>(list,0x1d0)(list,panel);panels.push_back(panel);}
        if(panels.size()!=9){for(void*& panel:spare)ReleaseNode(panel);s.status="ATS_WINDOW_HEAL_PANELS_UNAVAILABLE";return false;}
        for(size_t k=0;k<9;++k){const unsigned percent=static_cast<unsigned>(k+1)*10;char label[24]{};
            sprintf_s(label,u8"%u%% 이하",percent);
            if(void* caption=ChildPath(panels[k],"Button_225.Text_248_0"))SetText(caption,label);
            BindNodeButton(Child(panels[k],"Button_225"),[i,percent](void*){try{HealPercent(i,percent);}catch(...){++adapterErrors;}});}
        // CSB pitch is 23 per 22-high item: 6 rows=138, 9 rows=207.
        ResizeKeepTop(list,207.0f);ResizeKeepTop(Child(menu,"Sub_Bg"),210.0f);
        if(list){using Refresh=void(__fastcall*)(void*);Vcall<Refresh>(list,0x650)(list);}
        BindNodeButton(ChildPath(row,"Pulldown_Menu.Bt_Pdn"),[i](void*){try{ToggleHealMenu(i);}catch(...){++adapterErrors;}});
    }
    for(void*& panel:spare)ReleaseNode(panel);
    for(const char* name:{"Slot_07","Slot_08"})if(void* row=Child(fragment,name))Vcall<Remove>(row,0x220)(row);
    if(void* title=Child(fragment,"Tx_Sub01"))SetText(title,u8"회복 마법 (HP 이하일 때)");
    // Combat.02 sits at y98 in Combat (y531); Help is at y491. Lift it so its
    // title takes Combat.01's title line: 491+y-303 == 531+96-121.
    Vcall<Remove>(fragment,0x220)(fragment);Vcall<Add>(page,0x1d0)(page,fragment);
    Vcall<Position>(fragment,0x80)(fragment,94.9986f,318.0f);
    // This tree is attached after the initial root mask was applied.
    using Mask=void(__fastcall*)(void*,uint32_t,bool);Vcall<Mask>(fragment,0x468)(fragment,2,true);
    s.healReady=true;
    return true;
}
inline int OwnSlotByWorldPoint(const Vec2& point) {
    if(activeDrop&&std::isfinite(point.x)&&std::isfinite(point.y)){
        activeDrop->worldPointKnown=true;activeDrop->worldX=point.x;activeDrop->worldY=point.y;}
    if(!state||!std::isfinite(point.x)||!std::isfinite(point.y))return -1;
    void* scene=PlacementScene(state->root);if(!scene)return -1;
    using IsVisible=bool(__fastcall*)(void*);
    int selected=-1;
    for(size_t i=0;i<10;++i){
        void* slot=state->slots[i];auto* observed=activeDrop?&activeDrop->worldRects[i]:nullptr;
        if(observed)observed->slot=reinterpret_cast<uintptr_t>(slot);
        if(!slot)continue;
        // B05690 binds the authored Panel_Slot at +830; 95E010 uses that
        // panel's current size and live SlotNode transform at drop time.
        void* panel=At<void*>(slot,0x830);
        if(observed)observed->panel=reinterpret_cast<uintptr_t>(panel);
        if(!panel||PlacementScene(panel)!=scene)continue;
        void* node=slot;
        for(;node&&node!=scene;node=At<void*>(node,0x190))if(!Vcall<IsVisible>(node,0x150)(node))break;
        if(observed)observed->visible=node==scene;
        PlacementRect bounds{};PlacementAffine transform{};
        if(!PlacementBounds(panel,scene,bounds)||!PlacementTransform(panel,scene,transform))continue;
        const float determinant=transform.a*transform.d-transform.b*transform.c;
        if(!std::isfinite(determinant)||std::fabs(determinant)<0.000001f)continue;
        const float dx=point.x-transform.tx,dy=point.y-transform.ty;
        const float localX=(transform.d*dx-transform.c*dy)/determinant;
        const float localY=(-transform.b*dx+transform.a*dy)/determinant;
        if(!std::isfinite(localX)||!std::isfinite(localY))continue;
        const Vec2 size=At<Vec2>(panel,0x6c);
        if(observed){observed->left=bounds.left;observed->bottom=bounds.bottom;
            observed->right=bounds.right;observed->top=bounds.top;
            observed->localX=localX;observed->localY=localY;observed->boundsKnown=true;}
        if(node!=scene)continue;
        if(localX<0||localX>=size.x||localY<0||localY>=size.y)continue;
        if(selected>=0)return -1; // never choose between overlapping editable cells
        selected=static_cast<int>(i);
    }
    return selected;
}
inline bool PlaceWindowImpl() {
    auto& s=*state;void* scene=PlacementScene(s.root);void* parent=At<void*>(s.root,0x190);
    const Vec2 point=At<Vec2>(s.root,0x3c);
    using Position=void(__fastcall*)(void*,float,float);
    // Placement is optional. Every fallback leaves the untouched CSB default
    // in place; lack of room or geometry must never reject opening the editor.
    s.status="ATS_WINDOW_POSITION_DEFAULT";
    if(!scene||!parent)return true;
    const Vec2 canvas=At<Vec2>(scene,0x6c);PlacementRect current{};PlacementAffine rootTransform{},parentTransform{};
    if(!std::isfinite(canvas.x)||!std::isfinite(canvas.y)||canvas.x<=0||canvas.y<=0||
        !std::isfinite(point.x)||!std::isfinite(point.y)||!PlacementBounds(s.root,scene,current)||
        !PlacementTransform(s.root,scene,rootTransform)||!PlacementTransform(parent,scene,parentTransform))return true;
    const float width=current.right-current.left,height=current.top-current.bottom;
    const float gutterX=8.0f*(std::fabs(rootTransform.a)+std::fabs(rootTransform.c));
    const float gutterY=8.0f*(std::fabs(rootTransform.b)+std::fabs(rootTransform.d));
    std::vector<PlacementRect> occupied;
    const float determinant=parentTransform.a*parentTransform.d-parentTransform.b*parentTransform.c;
    auto moveTo=[&](float left,float bottom){
        if(!std::isfinite(left)||!std::isfinite(bottom)||left<0||bottom<0||
            left+width>canvas.x||bottom+height>canvas.y||
            !std::isfinite(determinant)||std::fabs(determinant)<0.000001f)return false;
        const float dx=left-current.left,dy=bottom-current.bottom;
        const float x=point.x+(parentTransform.d*dx-parentTransform.c*dy)/determinant;
        const float y=point.y+(-parentTransform.b*dx+parentTransform.a*dy)/determinant;
        if(!std::isfinite(x)||!std::isfinite(y))return false;
        Step("WINDOW_POSITION");Vcall<Position>(s.root,0x80)(s.root,x,y);return true;
    };
    auto visibleBounds=[&](void* layout,PlacementRect& rect){
        if(!layout||layout==s.window.layout)return false;
        void* root=At<void*>(layout,0x30);if(!root||PlacementScene(root)!=scene)return false;
        using IsVisible=bool(__fastcall*)(void*);
        for(void* node=root;node;node=At<void*>(node,0x190))if(!Vcall<IsVisible>(node,0x150)(node))return false;
        return PlacementBounds(root,scene,rect);
    };
    PlacementRect bag{};
    if(records&&visibleBounds(records[0].layout,bag))occupied.push_back(bag);
    for(const auto& view:views)if(view.layout&&view.actor==s.identity.actor){
        PlacementRect pet{};if(visibleBounds(view.layout,pet))occupied.push_back(pet);
    }
    // Keep the original ATS CSB position unless the current companion Bag or
    // Pet actually overlaps it. The knight ATS is not a placement obstacle.
    bool overlaps=false;for(const auto& rect:occupied)
        if(current.left<rect.right&&current.right>rect.left&&current.bottom<rect.top&&current.top>rect.bottom){overlaps=true;break;}
    if(!overlaps)return true;
    const float preferredX=current.left;
    const float preferredY=(std::max)(0.0f,(std::min)(current.bottom,canvas.y-height));
    std::vector<float> xs{(std::max)(0.0f,(std::min)(preferredX,canvas.x-width)),0.0f,canvas.x-width};
    std::vector<float> ys{preferredY,0.0f,canvas.y-height};
    for(const auto& rect:occupied){xs.push_back(rect.right+gutterX);xs.push_back(rect.left-width-gutterX);
        ys.push_back(rect.top+gutterY);ys.push_back(rect.bottom-height-gutterY);}
    bool found=false;float best=0,bestX=0,bestY=0;
    for(float x:xs)for(float y:ys){
        if(x<0||y<0||x+width>canvas.x||y+height>canvas.y)continue;
        bool clear=true;for(const auto& rect:occupied)if(x<rect.right+gutterX&&x+width>rect.left-gutterX&&
            y<rect.top+gutterY&&y+height>rect.bottom-gutterY){clear=false;break;}
        if(!clear)continue;const float dx=x-preferredX,dy=y-preferredY,distance=dx*dx+dy*dy;
        if(!found||distance<best){found=true;best=distance;bestX=x;bestY=y;}
    }
    if(found&&moveTo(bestX,bestY))return true;
    // No clear bounded gap: keep the resource default and still open.
    Step("WINDOW_POSITION_DEFAULT");return true;
}
inline void PlaceWindowTry() noexcept {
    try{(void)PlaceWindowImpl();}catch(...){++adapterErrors;Step("WINDOW_POSITION_DEFAULT_EXCEPTION");}
}
inline bool PlaceWindow() noexcept {
    __try{PlaceWindowTry();}
    __except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;Step("WINDOW_POSITION_DEFAULT_SEH");}
    return true;
}
inline void PlaceKnightAwayFromPetImpl(void* layout) {
    void* root=layout?At<void*>(layout,0x30):nullptr;
    void* scene=PlacementScene(root);void* parent=root?At<void*>(root,0x190):nullptr;
    if(!scene||!parent)return;
    const Vec2 canvas=At<Vec2>(scene,0x6c),point=At<Vec2>(root,0x3c);
    PlacementRect knight{};PlacementAffine parentTransform{};
    if(!std::isfinite(canvas.x)||canvas.x<=0||!std::isfinite(point.x)||!std::isfinite(point.y)||
        !PlacementBounds(root,scene,knight)||!PlacementTransform(parent,scene,parentTransform))return;
    const float determinant=parentTransform.a*parentTransform.d-parentTransform.b*parentTransform.c;
    if(!std::isfinite(determinant)||std::fabs(determinant)<0.000001f)return;
    using IsVisible=bool(__fastcall*)(void*);
    float targetLeft=knight.left;bool overlaps=false;
    for(const auto& view:views){
        if(!view.layout)continue;
        void* pet=At<void*>(view.layout,0x30);
        if(!pet||PlacementScene(pet)!=scene||!Vcall<IsVisible>(pet,0x150)(pet))continue;
        PlacementRect bounds{};if(!PlacementBounds(pet,scene,bounds))continue;
        if(knight.left<bounds.right&&knight.right>bounds.left&&
            knight.bottom<bounds.top&&knight.top>bounds.bottom){
            overlaps=true;targetLeft=(std::max)(targetLeft,bounds.right+8.0f);
        }
    }
    if(!overlaps||targetLeft+knight.right-knight.left>canvas.x)return;
    const float dx=targetLeft-knight.left;
    const float x=point.x+parentTransform.d*dx/determinant;
    const float y=point.y-parentTransform.b*dx/determinant;
    if(!std::isfinite(x)||!std::isfinite(y))return;
    using Position=void(__fastcall*)(void*,float,float);
    Vcall<Position>(root,0x80)(root,x,y);
}
inline void PlaceKnightAwayFromPetTry(void* layout) noexcept {
    try{PlaceKnightAwayFromPetImpl(layout);}catch(...){++adapterErrors;}
}
inline void PlaceKnightAwayFromPet(void* layout) noexcept {
    __try{PlaceKnightAwayFromPetTry(layout);}
    __except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;}
}
inline bool EditableSpellSlot(const companion5_json::Value& slot) {
    if(slot.kind==companion5_json::Value::Null)return true;
    if(slot.kind!=companion5_json::Value::Object||slot.Get("status").kind!=companion5_json::Value::Null)return false;
    uint64_t row=0;return slot.Get("spell_row").UInt(row)&&row<=INT_MAX;
}
// Recovery rows are battle-side entries HealEntry+0..5 (SpellDropTarget).
constexpr size_t HealEntry=1000;
inline bool DraftSpell(uint64_t row,bool buff,size_t index) {
    if(!Current()||!state->loaded||state->saving)return false;
    const auto& learned=state->draft.Get("learned_spells");
    const companion5_json::Value* selection=nullptr;
    for(const auto& spell:learned.array){uint64_t candidate=0;
        if(spell.Get("spell_row").UInt(candidate)&&candidate==row){selection=&spell;break;}}
    if(!selection)return false;
    // The learned catalog also carries heal_kind for the recovery kind gate.
    // It is not a persisted slot field: ats_config_codec.py:_window_validate_spell
    // admits only spell_row/name/icon for ordinary editable spell slots.
    companion5_json::Value saved;saved.kind=companion5_json::Value::Object;
    for(const char* key:{"spell_row","name","icon"})saved.object[key]=selection->Get(key);
    if(!buff&&index>=HealEntry){auto& heal=state->draft.object["heal_slots"].array;const size_t at=index-HealEntry;
        if(at>=heal.size()||!EditableSpellSlot(heal[at].Get("slot")))return false;
        // Server heal_kind: hp rows 0-3 take heal spells, status rows 4-5 cures.
        if(selection->Get("heal_kind").text!=(at<4?"hp":"status")){state->status="ATS_WINDOW_SPELL_KIND_REFUSED";return false;}
        heal[at].object["slot"]=saved;
    }else if(buff){auto& slots=state->draft.object["buff_slots"].array;
        if(index>=slots.size()||!EditableSpellSlot(slots[index]))return false;
        slots[index]=saved;
    }else {auto& entries=state->draft.object["battle_slots"].array;
        if(index>=entries.size()||!EditableSpellSlot(entries[index].Get("slot")))return false;
        entries[index].object["slot"]=saved;
    }
    Render();state->status="ATS_WINDOW_SPELL_DRAFT_CHANGED";return true;
}
inline bool SpellHitNode(void* slot,const Vec2& point) {
    if(!slot)return false;void* panel=At<void*>(slot,0x830);if(!panel)return false;
    void* scene=PlacementScene(panel);if(!scene)return false;
    using IsVisible=bool(__fastcall*)(void*);
    for(void* node=panel;node;node=At<void*>(node,0x190))
        if(!Vcall<IsVisible>(node,0x150)(node))return false;
    PlacementRect rect{};return PlacementBounds(panel,scene,rect)&&
        point.x>=rect.left&&point.x<rect.right&&point.y>=rect.bottom&&point.y<rect.top;
}
inline bool SpellDropTarget(const Vec2& point,bool& buff,size_t& entry) {
    if(!Current()||!state->loaded)return false;auto& s=*state;
    unsigned hits=0;
    for(size_t i=0;i<s.buffSlotNodes.size();++i)if(SpellHitNode(s.buffSlotNodes[i],point)){
        buff=true;entry=i;++hits;}
    const auto& battle=s.draft.Get("battle_slots").array;
    for(size_t i=0;i<battle.size();++i){uint64_t index=0;
        if(!battle[i].Get("index").UInt(index)||index>=8)continue;
        void* slot=battle[i].Get("kind").text=="sequence"?s.battleSequence[index]:s.battleConditional[index];
        if(SpellHitNode(slot,point)){buff=false;entry=i;++hits;}}
    for(size_t i=0;i<6;++i)if(SpellHitNode(s.healSlots[i],point)){buff=false;entry=HealEntry+i;++hits;}
    return hits==1;
}
inline void SpellSourceDrop(Pair& incoming,const Vec2& point) {
    Pair held=incoming;incoming={};struct Held {Pair& pair;~Held(){Release(nullptr,pair);}} release{held};
    uint64_t pointBits=0;std::memcpy(&pointBits,&point,sizeof(pointBits));
    TraceDrop("spell-source","ENTER",state?state->spellWindow.layout:nullptr,
        state?state->spellDrop:nullptr,nullptr,&held,pointBits);
    if(!Current()||!state->spellWindow.layout||state->spellClosePending||!held.object||!held.control)return;
    uint64_t row=UINT64_MAX;for(const auto& source:state->spellSlots)
        if(source.metadata.object==held.object&&source.metadata.control==held.control){row=source.row;break;}
    if(row==UINT64_MAX){state->status="ATS_WINDOW_SPELL_SOURCE_REFUSED";return;}
    if(Hit(state->spellWindow.layout,pointBits)){state->status="ATS_WINDOW_SPELL_SELF_DROP";return;}
    bool buff=false;size_t index=0;
    if(!SpellDropTarget(point,buff,index)){state->status="ATS_WINDOW_SPELL_TARGET_MISSING";return;}
    if(!DraftSpell(row,buff,index)&&std::strcmp(state->status,"ATS_WINDOW_SPELL_KIND_REFUSED"))state->status="ATS_WINDOW_SPELL_TARGET_READONLY";
}
// The original manager never starts a drag from these DLL-built spell slots
// (no source callback, drag Pair stays 0). Own press/move/release between our
// two windows instead: poll the GLFW host's left button (+90) and cursor
// (+1F8/+200) on the existing 15 ms spell timer. No input hook, no SendInput.
inline void* SpellPointerHost() noexcept {
    __try {void* window=*reinterpret_cast<void**>(base+0x17f0d18);
        void* host=window?At<void*>(window,0x80):nullptr;
        if(!host||At<HWND>(host,0x368)!=autoOkWindow.load())return nullptr;return host;
    }__except(EXCEPTION_EXECUTE_HANDLER){return nullptr;}
}
// Inverse of the aspect-fit presentation the harness node_to_capture uses:
// the scene canvas is centered in the GLFW client area at min(w/W,h/H).
inline bool SpellPointerScene(void* host,void* scene,Vec2& point) {
    RECT client{};if(!host||!scene||!GetClientRect(autoOkWindow.load(),&client))return false;
    const double width=client.right-client.left,height=client.bottom-client.top;
    const Vec2 canvas=At<Vec2>(scene,0x6c);
    if(width<=0||height<=0||!std::isfinite(canvas.x)||!std::isfinite(canvas.y)||canvas.x<=0||canvas.y<=0)return false;
    const double scale=(std::min)(width/canvas.x,height/canvas.y);
    const double x=(At<double>(host,0x1f8)-(width-canvas.x*scale)/2)/scale;
    const double y=canvas.y-(At<double>(host,0x200)-(height-canvas.y*scale)/2)/scale;
    point={static_cast<float>(x),static_cast<float>(y)};
    return std::isfinite(point.x)&&std::isfinite(point.y);
}
inline bool SceneToLocal(void* node,void* scene,const Vec2& point,Vec2& local) {
    PlacementAffine t{};if(!PlacementTransform(node,scene,t))return false;
    const float determinant=t.a*t.d-t.b*t.c;
    if(!std::isfinite(determinant)||std::fabs(determinant)<0.000001f)return false;
    const float dx=point.x-t.tx,dy=point.y-t.ty;
    local={(t.d*dx-t.c*dy)/determinant,(-t.b*dx+t.a*dy)/determinant};
    return std::isfinite(local.x)&&std::isfinite(local.y);
}
inline void DropSpellPreview() {
    if(!state||!state->spellDragPreview)return;
    void* preview=state->spellDragPreview;state->spellDragPreview=nullptr;
    using Remove=void(__fastcall*)(void*);if(At<void*>(preview,0x190))Vcall<Remove>(preview,0x220)(preview);
    ReleaseNode(preview);
}
inline void CancelSpellDrag() {
    if(!state)return;DropSpellPreview();
    state->spellPointerHeld=false;state->spellDragActive=false;state->spellDragSource=SIZE_MAX;
}
inline void MoveSpellPreview(const Vec2& point) {
    auto& s=*state;void* preview=s.spellDragPreview;if(!preview)return;
    void* parent=At<void*>(preview,0x190);Vec2 local{};
    if(!parent||!SceneToLocal(parent,PlacementScene(preview),point,local))return;
    using Position=void(__fastcall*)(void*,float,float);
    Vcall<Position>(preview,0x80)(preview,local.x+s.spellDragOffset.x,local.y+s.spellDragOffset.y);
}
inline void CreateSpellPreview(const Vec2& point) {
    auto& s=*state;if(s.spellDragPreview)return;
    const auto& learned=s.draft.Get("learned_spells").array;if(s.spellDragSource>=learned.size())return;
    void* parent=At<void*>(s.spellRoot,0x190),*scene=PlacementScene(s.spellRoot);if(!parent||!scene)return;
    // Same CSB slot and B042D0 icon bind as BuildSpellSlots.
    void* panel=ResourceSlot("Slot/SpellSlot.csb");if(!panel)return;
    void* slot=FindSlotNode(panel);Pair metadata=slot?SpellMetadata(learned[s.spellDragSource]):Pair{};
    if(!metadata.object){ReleaseNode(panel);return;}
    // ReportSpellOpenImpl and manual-evidence-20261030/bridge record manager
    // roots at local z14/10/4. Insertion order alone loses to local z0.
    // Frozen CONTROL Node v10=B576D0 uses v18=B57730 (+16C store) and
    // parent v258 to reorder; B59260(addChild) consumes the child's z via v20.
    int32_t top=0;void** first=At<void**>(parent,0x178),**last=At<void**>(parent,0x180);
    for(void** p=first;p!=last;++p)if(*p)top=(std::max)(top,At<int32_t>(*p,0x16c));
    using Z=void(__fastcall*)(void*,int32_t);Vcall<Z>(panel,0x10)(panel,top<INT_MAX?top+1:top);
    using Add=void(__fastcall*)(void*,void*);Vcall<Add>(parent,0x1d0)(parent,panel);
    if(At<void*>(panel,0x190)!=parent){Release(nullptr,metadata);ReleaseNode(panel);return;}
    s.spellDragPreview=panel;At<uint8_t>(slot,0x818)=1;
    using Set=void(__fastcall*)(void*,const Pair*);Call<Set>(0xb042d0)(slot,&metadata);metadata={};
    using Cooldown=void(__fastcall*)(void*,bool);Call<Cooldown>(0xb04350)(slot,false);
    using Mask=void(__fastcall*)(void*,uint32_t,bool);Vcall<Mask>(panel,0x468)(panel,2,true);
    // Center the 62x62 Panel_Slot (+830) on the cursor.
    s.spellDragOffset={};MoveSpellPreview(point);
    void* cell=At<void*>(slot,0x830);PlacementRect rect{};Vec2 center{},at{};
    if(cell&&PlacementBounds(cell,scene,rect)&&
       SceneToLocal(parent,scene,{(rect.left+rect.right)/2,(rect.bottom+rect.top)/2},center)&&
       SceneToLocal(parent,scene,point,at)){
        s.spellDragOffset={at.x-center.x,at.y-center.y};MoveSpellPreview(point);}
}
inline void ReportSpellDrag(uint64_t row,size_t source,const Vec2& point,bool buff,size_t index,bool targeted) {
    forward_diagnostic::Context c{};
    if(!forward_diagnostic::context(c)||!manual_move::SameOwner(c)||!manual_move::CorrectThread(c))return;
    auto& s=*state;using J=companion5_json::Value;
    auto number=[](double value){J out;out.kind=J::Number;out.text=std::to_string(value);return out;};
    J result;result.kind=J::Object;result.object["schema"]=J::Text("companion-spell-dll-drag-v1");
    result.object["sequence"]=J::Integer(++s.spellDragSequence);
    result.object["status"]=J::Text(s.status);
    result.object["spell_row"]=J::Integer(row);result.object["source_index"]=J::Integer(source);
    result.object["start_x"]=number(s.spellDragStart.x);result.object["start_y"]=number(s.spellDragStart.y);
    result.object["drop_x"]=number(point.x);result.object["drop_y"]=number(point.y);
    result.object["target"]=J::Text(!targeted?"NONE":buff?"BUFF":index>=HealEntry?"HEAL":"BATTLE");
    result.object["target_index"]=J::Integer(!targeted?0:index>=HealEntry?index-HealEntry:index);
    const std::string bytes=companion5_json::Encode(result);wchar_t path[600]{};
    swprintf_s(path,L"%s\\companion-spell-dll-drag-%llu.json",c.directory,static_cast<unsigned long long>(s.spellDragSequence));
    if(!WriteNew(path,bytes.data(),static_cast<DWORD>(bytes.size())))++signalErrors;
}
inline void SpellDragTickImpl() {
    if(!state)return;auto& s=*state;
    if(!Current()||!s.loaded||s.saving||!s.spellWindow.layout||!s.spellRoot||s.spellClosePending){CancelSpellDrag();return;}
    void* host=SpellPointerHost();Vec2 point{};
    if(!host||!SpellPointerScene(host,PlacementScene(s.spellRoot),point)){CancelSpellDrag();return;}
    const bool held=At<uint8_t>(host,0x90)!=0;
    if(held&&!s.spellPointerHeld){
        // A press starts a candidate only on a visible learned slot of the
        // current page; any other press (bag/potion drags, buttons) is ignored.
        s.spellPointerHeld=true;s.spellDragActive=false;s.spellDragSource=SIZE_MAX;s.spellDragStart=point;
        for(size_t i=0;i<s.spellSlots.size();++i)
            if(i/32==s.spellPage&&SpellHitNode(FindSlotNode(s.spellSlots[i].node),point)){s.spellDragSource=i;break;}
        return;
    }
    if(held){
        if(s.spellDragSource==SIZE_MAX)return;
        if(!s.spellDragActive){const float dx=point.x-s.spellDragStart.x,dy=point.y-s.spellDragStart.y;
            if(dx*dx+dy*dy<16)return;s.spellDragActive=true;CreateSpellPreview(point);}
        else MoveSpellPreview(point);
        return;
    }
    if(!s.spellPointerHeld)return;
    const bool active=s.spellDragActive;const size_t source=s.spellDragSource;
    CancelSpellDrag();
    if(!active||source>=s.spellSlots.size())return;
    const uint64_t row=s.spellSlots[source].row;
    uint64_t pointBits=0;std::memcpy(&pointBits,&point,sizeof(pointBits));
    bool buff=false,targeted=false;size_t index=0;
    if(Hit(s.spellWindow.layout,pointBits))s.status="ATS_WINDOW_SPELL_SELF_DROP";
    else if(!SpellDropTarget(point,buff,index))s.status="ATS_WINDOW_SPELL_TARGET_MISSING";
    else {targeted=true;if(!DraftSpell(row,buff,index)&&std::strcmp(s.status,"ATS_WINDOW_SPELL_KIND_REFUSED"))s.status="ATS_WINDOW_SPELL_TARGET_READONLY";}
    ReportSpellDrag(row,source,point,buff,index,targeted);
}
inline void SpellDragTickTry() noexcept {
    try{SpellDragTickImpl();}catch(...){++adapterErrors;}
}
inline void SpellDragTick() noexcept {
    __try{SpellDragTickTry();}__except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;}
}
inline const companion5_json::Value& AtsSelected(const State::AtsDragSource& source) {
    const auto& draft=state->draft;
    if(source.kind==1){const char* key=source.index<2?"hp_slots":source.index<4?"mp_slots":"function_slots";
        const size_t index=source.index<2?source.index:source.index<4?source.index-2:source.index-4;
        return draft.Get(key).array[index];}
    if(source.kind==2)return draft.Get("buff_slots").array[source.index];
    if(source.kind==3)return draft.Get("battle_slots").array[source.index].Get("slot");
    return draft.Get("heal_slots").array[source.index].Get("slot");
}
// 0=no ATS cell, 1=one cell, 2=overlap. A failed unique hit must not erase
// a source: the authored windows can overlap without changing their node rects.
inline unsigned AtsHitSlot(const Vec2& point,State::AtsDragSource& found) {
    auto& s=*state;unsigned hits=0;
    auto take=[&](void* slot,unsigned kind,size_t index){
        if(SpellHitNode(slot,point)){found={kind,index,slot};++hits;}};
    for(size_t i=0;i<10;++i)take(s.slots[i],1,i);
    for(size_t i=0;i<s.buffSlotNodes.size();++i)take(s.buffSlotNodes[i],2,i);
    const auto& battle=s.draft.Get("battle_slots").array;
    for(size_t i=0;i<battle.size();++i){uint64_t index=0;
        if(!battle[i].Get("index").UInt(index)||index>=8)continue;
        take(battle[i].Get("kind").text=="sequence"?s.battleSequence[index]:s.battleConditional[index],3,i);}
    for(size_t i=0;i<6;++i)take(s.healSlots[i],4,i);
    return hits>1?2:hits;
}
inline void DropAtsPreview() {
    if(!state||!state->atsDragPreview)return;void* preview=state->atsDragPreview;
    state->atsDragPreview=nullptr;using Remove=void(__fastcall*)(void*);
    if(At<void*>(preview,0x190))Vcall<Remove>(preview,0x220)(preview);
    ReleaseNode(preview);
}
inline void CancelAtsDrag() {
    if(!state)return;DropAtsPreview();state->atsPointerHeld=false;
    state->atsDragActive=false;state->atsDragSource={};
}
inline void MoveAtsPreview(const Vec2& point) {
    auto& s=*state;void* preview=s.atsDragPreview;if(!preview)return;
    void* parent=At<void*>(preview,0x190);Vec2 local{};
    if(!parent||!SceneToLocal(parent,PlacementScene(preview),point,local))return;
    using Position=void(__fastcall*)(void*,float,float);
    Vcall<Position>(preview,0x80)(preview,local.x+s.atsDragOffset.x,local.y+s.atsDragOffset.y);
}
inline void CreateAtsPreview(const Vec2& point) {
    auto& s=*state;const auto& source=s.atsDragSource;
    if(s.atsDragPreview||!source.slot)return;
    const auto& selected=AtsSelected(source);Pair metadata{};
    if(source.kind==1){uint64_t item=0;selected.Get("template").UInt(item);metadata=ItemMetadata(item);}
    else metadata=SpellMetadata(selected);
    if(!metadata.object)return;
    // Clone the live SlotNode via the same BF3D24..47 Widget path as the
    // bottom spell button. SlotNode v620=B03F90 clones its Panel_Slot child;
    // B042D0->B046F0->B05690 rebinds the clone's +830 dynamic cache.
    void* preview=CloneWidget(source.slot);
    if(!preview){Release(nullptr,metadata);return;}
    void* parent=At<void*>(s.root,0x190),*scene=PlacementScene(s.root);
    if(!parent||!scene){Release(nullptr,metadata);ReleaseNode(preview);return;}
    EmptyModelCallbacks(preview);
    using Touch=void(__fastcall*)(void*,bool);Vcall<Touch>(preview,0x530)(preview,false);
    // Native Node v10=B576D0 stores local z at +16C; manager roots are
    // above local z0, so put the cursor preview above its scene siblings.
    int32_t top=0;void** first=At<void**>(parent,0x178),**last=At<void**>(parent,0x180);
    for(void** p=first;p!=last;++p)if(*p)top=(std::max)(top,At<int32_t>(*p,0x16c));
    using Z=void(__fastcall*)(void*,int32_t);Vcall<Z>(preview,0x10)(preview,top<INT_MAX?top+1:top);
    using Add=void(__fastcall*)(void*,void*);Vcall<Add>(parent,0x1d0)(parent,preview);
    s.atsDragPreview=preview;void* slot=FindSlotNode(preview);
    if(source.kind!=1)At<uint8_t>(slot,0x818)=1;
    using Set=void(__fastcall*)(void*,const Pair*);Call<Set>(0xb042d0)(slot,&metadata);metadata={};
    if(source.kind!=1){using Cooldown=void(__fastcall*)(void*,bool);Call<Cooldown>(0xb04350)(slot,false);}
    using Mask=void(__fastcall*)(void*,uint32_t,bool);Vcall<Mask>(preview,0x468)(preview,2,true);
    s.atsDragOffset={};MoveAtsPreview(point);
    void* cell=At<void*>(slot,0x830);PlacementRect rect{};Vec2 center{},at{};
    if(cell&&PlacementBounds(cell,scene,rect)&&
       SceneToLocal(parent,scene,{(rect.left+rect.right)/2,(rect.bottom+rect.top)/2},center)&&
       SceneToLocal(parent,scene,point,at)){
        s.atsDragOffset={at.x-center.x,at.y-center.y};MoveAtsPreview(point);}
}
inline void ClearAtsSource(const State::AtsDragSource& source) {
    auto& s=*state;using J=companion5_json::Value;
    if(source.kind==1){SetDraftSlot(source.index,nullptr);return;}
    if(source.kind==2)s.draft.object["buff_slots"].array[source.index]=J{};
    else if(source.kind==3)s.draft.object["battle_slots"].array[source.index].object["slot"]=J{};
    else s.draft.object["heal_slots"].array[source.index].object["slot"]=J{};
    Render();s.status="ATS_WINDOW_SPELL_DRAFT_CHANGED";
}
inline void AtsDragTickImpl() {
    if(!state)return;auto& s=*state;
    if(!Current()||!s.loaded||s.saving){CancelAtsDrag();return;}
    void* host=SpellPointerHost();Vec2 point{};
    if(!host||!SpellPointerScene(host,PlacementScene(s.root),point)){CancelAtsDrag();return;}
    const bool held=At<uint8_t>(host,0x90)!=0;
    if(held&&!s.atsPointerHeld){
        s.atsPointerHeld=true;s.atsDragActive=false;s.atsDragSource={};s.atsDragStart=point;
        uint64_t bits=0;std::memcpy(&bits,&point,sizeof(bits));
        if(s.spellWindow.layout&&Hit(s.spellWindow.layout,bits))return;
        State::AtsDragSource source{};
        if(AtsHitSlot(point,source)!=1)return;
        const auto& selected=AtsSelected(source);
        if(selected.kind!=companion5_json::Value::Object||
           source.kind!=1&&!EditableSpellSlot(selected))return;
        s.atsDragSource=source;return;
    }
    if(held){
        if(!s.atsDragSource.kind)return;
        if(!s.atsDragActive){const float dx=point.x-s.atsDragStart.x,dy=point.y-s.atsDragStart.y;
            if(dx*dx+dy*dy<16)return;s.atsDragActive=true;CreateAtsPreview(point);}
        else MoveAtsPreview(point);
        return;
    }
    if(!s.atsPointerHeld)return;
    const bool active=s.atsDragActive;const auto source=s.atsDragSource;
    CancelAtsDrag();if(!active||!source.kind)return;
    State::AtsDragSource target{};const unsigned hits=AtsHitSlot(point,target);
    if(hits==0)ClearAtsSource(source);
    else if(hits==2)s.status="ATS_WINDOW_DRAG_TARGET_AMBIGUOUS";
    else if(target.kind!=source.kind||target.index!=source.index)
        // Original slot-to-slot move/swap condition was not established by
        // ui2_pc_drop_callbacks.json (8FCD40); preserve both drafts.
        s.status="ATS_WINDOW_DRAG_MOVE_UNCONFIRMED";
}
inline void AtsDragTickTry() noexcept {
    try{AtsDragTickImpl();}catch(...){++adapterErrors;}
}
inline void AtsDragTick() noexcept {
    __try{AtsDragTickTry();}__except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;}
}
inline void SpellPage(size_t page) {
    if(!state||!state->spellWindow.layout||page>=10)return;
    state->spellPage=page;
    for(size_t i=0;i<state->spellSlots.size();++i)
        Visible(state->spellSlots[i].node,i/32==page);
}
inline void RestoreSpellGrid() {
    if(!state||!state->spellWindow.layout||!state->spellList||
       state->spellClosePending||!Current()||!OnUi())return;
    void* inner=At<void*>(state->spellList,0xce0);if(!inner)return;
    using Position=void(__fastcall*)(void*,const Vec2*);
    for(size_t i=0;i<state->spellSlots.size();++i){
        void* node=state->spellSlots[i].node;
        if(!node||At<void*>(node,0x190)!=inner)continue;
        const size_t cell=i%32;
        const Vec2 expected{static_cast<float>(cell%4)*62.0f,
                            static_cast<float>(7-cell/4)*62.0f};
        const Vec2 actual=At<Vec2>(node,0x3c);
        if(actual.x!=expected.x||actual.y!=expected.y)
            Vcall<Position>(node,0x88)(node,&expected);
    }
}
inline uintptr_t __fastcall KnightShowWindow(void* layout,bool show) {
    const auto native=state&&state->knightLayout==layout&&state->knightNativeShow?
        state->knightNativeShow:reinterpret_cast<Show>(base+0x8e6a80);
    if(show&&state&&state->knightLayout==layout&&state->window.layout)Retire();
    const uintptr_t result=native(layout,show);
    // The original ATS is left of the Pet menu in the selected scene. Give
    // the menu row a real, unobstructed hit target for the next editor switch.
    if(show)PlaceKnightAwayFromPet(layout);
    return result;
}
inline uintptr_t __fastcall SpellShowWindow(void* layout,bool show) {
    const auto native=companion3_native::originalShow?companion3_native::originalShow:
        reinterpret_cast<Show>(base+0xa10bb0);
    const uintptr_t result=native(layout,show);
    if(state&&state->spellWindow.layout==layout&&!show){state->spellClosePending=true;
        PostMessageW(autoOkWindow.load(),DrainMessage(),0,0);}
    return result;
}
inline void RetireSpell() {
    if(!state)return;auto& s=*state;auto& r=s.spellWindow;
    CancelSpellDrag();
    if(s.spellLayoutTimer){KillTimer(nullptr,s.spellLayoutTimer);s.spellLayoutTimer=0;}
#if defined(COMPANION_NC_GLFW_INPUT)
    if(s.spellDiagnosticTimer){KillTimer(nullptr,s.spellDiagnosticTimer);s.spellDiagnosticTimer=0;}
#endif
    s.spellCreating=false;s.spellClosePending=false;
    if(r.layout){
        if(At<uint8_t>(r.layout,0x70)){
            const auto native=companion3_native::originalShow?companion3_native::originalShow:
                reinterpret_cast<Show>(base+0xa10bb0);
            native(r.layout,false);
        }
        Disconnect(r.layout,0x18);
        if(s.spellRoot){using Remove=void(__fastcall*)(void*);Vcall<Remove>(s.spellRoot,0x220)(s.spellRoot);}
        if(r.nativeVtable)At<uintptr_t*>(r.layout,0)=r.nativeVtable;
    }
    for(auto& slot:s.spellSlots){Release(nullptr,slot.metadata);ReleaseNode(slot.node);}
    s.spellSlots.clear();ReleaseNode(s.spellList);s.spellList=nullptr;
    s.spellDrop=nullptr;s.spellInput=nullptr;
    UnregisterLayout(r);Release(nullptr,s.spellOwner);
    s.spellRoot=nullptr;r.layout=nullptr;r.nativeVtable=nullptr;r.nativeShow=nullptr;
    r.registryName=nullptr;r.creation={};r.log={};
}
inline void ConstructSpell(void* node) {
    auto& s=*state;auto& r=s.spellWindow;if(!node||!s.spellCreating||r.layout)return;
    using DynamicCast=void*(__fastcall*)(void*,long,void*,void*,int);
    void* typed=Call<DynamicCast>(0xfa1ad3)(node,0,reinterpret_cast<void*>(base+0x16d87a8),
                                            reinterpret_cast<void*>(base+0x166ec80),0);
    if(!typed||NodeName(typed)!="SpellLayout")return;
    using New=void*(__fastcall*)(size_t);void* object=Call<New>(0xfa0a80)(0xb8);
    using Ctor=void*(__fastcall*)(void*,void*);Call<Ctor>(0x8e3330)(object,typed);
    const std::shared_ptr<void> owner(object,&DeleteLayout,GameAllocator<char>{});
    new (static_cast<char*>(object)+8) std::weak_ptr<void>(owner);
    std::memcpy(&s.spellOwner,&owner,sizeof(s.spellOwner));Retain(s.spellOwner);
    r.layout=object;s.spellRoot=At<void*>(object,0x30);r.nativeVtable=At<uintptr_t*>(object,0);
    std::memcpy(r.localVtable,r.nativeVtable-1,23*sizeof(uintptr_t));
    r.localVtable[1+0x70/8]=reinterpret_cast<uintptr_t>(&SpellShowWindow);
    r.localVtable[1+0xa0/8]=reinterpret_cast<uintptr_t>(&ConsumeCommand);
    At<uintptr_t*>(object,0)=r.localVtable+1;
    Call<Init>(0xa11d90)(object,4);At<uint8_t>(object,0x21)=1;
}
inline void PlaceSpell() {
    auto& s=*state;s.spellPlacement="GEOMETRY_UNKNOWN";if(!s.spellRoot||!s.root)return;
    void* scene=PlacementScene(s.spellRoot),*parent=At<void*>(s.spellRoot,0x190);
    if(!scene||!parent||PlacementScene(s.root)!=scene)return;
    void* spellBody=Lookup(s.spellWindow.layout,"Root.Background",false);
    void* atsBody=Lookup(s.window.layout,"Root.Background",false);
    struct Bodies {void*& spell;void*& ats;~Bodies(){ReleaseNode(spell);ReleaseNode(ats);}} bodies{spellBody,atsBody};
    if(!spellBody||!atsBody)return;
    PlacementRect spell{},ats{};PlacementAffine affine{};
    if(!PlacementBounds(spellBody,scene,spell)||!PlacementBounds(atsBody,scene,ats)||
       !PlacementTransform(parent,scene,affine))return;
    const Vec2 canvas=At<Vec2>(scene,0x6c),position=At<Vec2>(s.spellRoot,0x3c);
    const float determinant=affine.a*affine.d-affine.b*affine.c;
    if(!std::isfinite(canvas.x)||!std::isfinite(canvas.y)||canvas.x<=0||canvas.y<=0||
       !std::isfinite(determinant)||std::fabs(determinant)<0.000001f)return;
    const float width=spell.right-spell.left,height=spell.top-spell.bottom;
    std::vector<PlacementRect> occupied{ats};
    auto addLayout=[&](void* layout){
        if(!layout)return;void* root=At<void*>(layout,0x30);
        if(!root||PlacementScene(root)!=scene)return;
        using IsVisible=bool(__fastcall*)(void*);
        for(void* node=root;node&&node!=scene;node=At<void*>(node,0x190))
            if(!Vcall<IsVisible>(node,0x150)(node))return;
        // PetLayout's Node/Root are size zero; its authored Background owns
        // the actual 450x581 frame. Do not mistake that root for empty space.
        void* body=Lookup(layout,"Root.Background",false);PlacementRect rect{};
        if(PlacementBounds(body?body:root,scene,rect))occupied.push_back(rect);
        ReleaseNode(body);
    };
    if(records)addLayout(records[0].layout);
    for(const auto& view:views)if(view.actor==s.identity.actor)addLayout(view.layout);
    auto clear=[&](float x,float y){
        if(x<0||y<0||x+width>canvas.x||y+height>canvas.y)return false;
        for(const auto& rect:occupied)if(x<rect.right&&x+width>rect.left&&
            y<rect.top&&y+height>rect.bottom)return false;
        return true;
    };
    if(clear(spell.left,spell.bottom)){s.spellPlacement="DEFAULT_CLEAR";return;}
    const float preferredY=(std::max)(0.0f,(std::min)(ats.bottom,canvas.y-height));
    std::vector<float> xs{ats.right+8,canvas.x-width,0.0f},ys{preferredY,canvas.y-height,0.0f};
    for(const auto& rect:occupied){xs.push_back(rect.right+8);xs.push_back(rect.left-width-8);
        ys.push_back(rect.top+8);ys.push_back(rect.bottom-height-8);}
    bool found=false;float left=0,bottom=0,best=0;
    for(float x:xs)for(float y:ys)if(clear(x,y)){
        const float dx=x-(ats.right+8),dy=y-preferredY,distance=dx*dx+dy*dy;
        if(!found||distance<best){found=true;left=x;bottom=y;best=distance;}}
    if(!found){s.spellPlacement="NO_CLEAR_SPACE";return;}
    const float dx=left-spell.left,dy=bottom-spell.bottom;
    const float x=position.x+(affine.d*dx-affine.c*dy)/determinant;
    const float y=position.y+(-affine.b*dx+affine.a*dy)/determinant;
    if(std::isfinite(x)&&std::isfinite(y)){using Position=void(__fastcall*)(void*,float,float);
        Vcall<Position>(s.spellRoot,0x80)(s.spellRoot,x,y);s.spellPlacement="MOVED_CLEAR";}
}
inline bool BuildSpellSlots() {
    auto& s=*state;s.spellList=Lookup(s.spellWindow.layout,"Root.ListviewScroll.ListView_Slot",false);
    if(!s.spellList){s.status="ATS_WINDOW_SPELL_LIST_UNAVAILABLE";return false;}
    const auto& learned=s.draft.Get("learned_spells").array;
    s.spellRequested=learned.size();s.spellFilled=0;
    for(size_t i=0;i<learned.size();++i){uint64_t row=0;
        if(!learned[i].Get("spell_row").UInt(row))return false;
        void* panel=ResourceSlot("Slot/SpellSlot.csb");
        if(!panel){s.status="ATS_WINDOW_SPELL_SLOT_RESOURCE_UNAVAILABLE";return false;}
        if(!AttachSpellSlot(panel,s.spellList,i)){
            ReleaseNode(panel);s.status="ATS_WINDOW_SPELL_SLOT_ATTACH_UNAVAILABLE";return false;}
        void* slot=FindSlotNode(panel);if(!slot){ReleaseNode(panel);s.status="ATS_WINDOW_SPELL_SLOT_NODE_UNAVAILABLE";return false;}
        Pair metadata=SpellMetadata(learned[i]);if(!metadata.object){ReleaseNode(panel);s.status="ATS_WINDOW_SPELL_METADATA_UNAVAILABLE";return false;}
        Pair retained=metadata;Retain(retained);
        // Frozen CONTROL SpellAdapter B07310 creates the CSB root SlotNode
        // (primary vptr 1232F30, RTTI 16895C0); B075B0 binds its learned Pair
        // through B042D0. Panel_Slot is the +830 child, not the SlotNode.
        s.spellSlots.push_back({panel,retained,row});
        At<uint8_t>(slot,0x818)=1;
        // Frozen CONTROL SpellAdapter B0751E..41 enables Widget mouse events
        // and copies its stateless hover function64 to SlotNode+570. RTTI
        // TD178B840: void(Ref*,bool,EventMouse*), vptr1233998; B095D0 copies
        // only that vptr. B09320 consumes this slot's +808/+B4 and routes
        // enter/leave to the original tooltip B29010/B291F0; B09610 reads
        // metadata+30 for its name. No SELF-backed adapter is constructed.
        if(!At<void*>(slot,0x430)){using Mouse=void(__fastcall*)(void*,bool);Call<Mouse>(0xbf8a80)(slot,true);}
        uintptr_t hover[8]{};hover[0]=base+0x1233998;hover[7]=reinterpret_cast<uintptr_t>(hover);
        using AssignHover=void*(__fastcall*)(void*,const void*);
        Call<AssignHover>(0x9668d0)(static_cast<char*>(slot)+0x570,hover);
        At<uint8_t>(slot,0x6f0)=0; // Original B07546.
        using Set=void(__fastcall*)(void*,const Pair*);Call<Set>(0xb042d0)(slot,&metadata);metadata={};
        void* payload=At<void*>(slot,0x808),*icon=At<void*>(slot,0x820);
        uint64_t expectedIcon=0;learned[i].Get("icon").UInt(expectedIcon);
        if(!payload||!At<void*>(slot,0x830)||!icon||At<int32_t>(payload,8)!=1||
           At<int64_t>(payload,0)!=static_cast<int64_t>(row)||
           At<int32_t>(payload,0xc)!=static_cast<int32_t>(expectedIcon)){
            s.status="ATS_WINDOW_SPELL_SLOT_BIND_UNCONFIRMED";return false;}
        s.spellSlots.back().maskBefore=At<uint16_t>(slot,0x212);
        s.spellSlots.back().iconMaskBefore=At<uint16_t>(icon,0x212);
        ++s.spellFilled;
        using Predicate=std::function<bool(Pair&)>;Predicate predicate=[](Pair& incoming){
            Pair held=incoming;incoming={};Release(nullptr,held);return true;};
        using Bind=void(__fastcall*)(void*,Predicate*);Call<Bind>(0x8e3830)(slot,&predicate);
    }
    // Original SpellLayout B0B650 finds the root's existing drop component
    // before creating one; B0A0B0 then creates the slot input component.
    // Its derived layout+B8 is this ListView, copied to drop+180 and each
    // registered SlotNode+7C0 by 95D5A5..B6. Our base-only layout has no +B8.
    using Find=void*(__fastcall*)(void*);using Create=void*(__fastcall*)(void*);
    s.spellDrop=Call<Find>(0x9082b0)(s.spellRoot);
    if(!s.spellDrop)s.spellDrop=Call<Create>(0x95cfa0)(s.spellRoot);
    if(!s.spellDrop){s.status="ATS_WINDOW_SPELL_DRAG_COMPONENT_UNAVAILABLE";return false;}
    auto registered=[&](void* slot){
        auto** first=At<void**>(s.spellDrop,0x158),**last=At<void**>(s.spellDrop,0x160);
        if(!first||!last||last<first||last-first>512)return false;
        for(auto** p=first;p!=last;++p)if(*p==slot)return true;
        return false;
    };
    using Scan=void(__fastcall*)(void*,void*);
    for(const auto& entry:s.spellSlots){void* slot=FindSlotNode(entry.node);
        if(!slot){s.status="ATS_WINDOW_SPELL_DRAG_SLOT_UNAVAILABLE";return false;}
        if(!registered(slot))Call<Scan>(0x95e770)(s.spellDrop,slot);
        if(!registered(slot)){s.status="ATS_WINDOW_SPELL_DRAG_REGISTRATION_UNAVAILABLE";return false;}
    }
    At<void*>(s.spellDrop,0x180)=s.spellList;
    for(const auto& entry:s.spellSlots)if(void* slot=FindSlotNode(entry.node))
        At<void*>(slot,0x7c0)=s.spellList;
    DropAction source=[](Pair& incoming,const Vec2& point){try{SpellSourceDrop(incoming,point);}
        catch(...){++adapterErrors;}};
    using Assign=void*(__fastcall*)(void*,DropAction*);
    Call<Assign>(0x9086d0)(static_cast<char*>(s.spellDrop)+0xc8,&source);
    At<uint8_t>(s.spellDrop,0x148)=0;
    s.spellInput=Call<Create>(0x95c250)(s.spellRoot);
    if(!s.spellInput){s.status="ATS_WINDOW_SPELL_INPUT_COMPONENT_UNAVAILABLE";return false;}
    SpellPage(0);
    // OpenSpellImpl's earlier mask covered only the authored tree. The
    // newly attached SlotNodes and B05690-created Icon children must join it.
    // Node::setCameraMask B5BEE0 stores +212 and recursively visits children.
    using Mask=void(__fastcall*)(void*,uint32_t,bool);
    Vcall<Mask>(s.spellRoot,0x468)(s.spellRoot,2,true);
    return true;
}
inline bool ShowSpellSlots() {
    auto& s=*state;
    const auto& learned=s.draft.Get("learned_spells").array;
    s.spellFilled=0;
    if(s.spellSlots.size()!=learned.size())return false;
    for(size_t i=0;i<s.spellSlots.size();++i){
        const auto& source=s.spellSlots[i];void* slot=FindSlotNode(source.node);
        if(!slot||!source.metadata.object||!source.metadata.control){s.status="ATS_WINDOW_SPELL_SLOT_SHOW_UNAVAILABLE";return false;}
        // The original spell-list adapter B075B0 supplies its learned Pair to
        // B042D0 and then toggles B04350 using adapter+190>0 (B07684..92).
        // No live cooldown is published for this learned-list view. The earlier bind
        // passed before Show but the captured post-Show rows were defaults;
        // bind here too and check the actual post-Show payload.
        Pair supplied=source.metadata;Retain(supplied);
        using Set=void(__fastcall*)(void*,const Pair*);Call<Set>(0xb042d0)(slot,&supplied);supplied={};
        using Cooldown=void(__fastcall*)(void*,bool);Call<Cooldown>(0xb04350)(slot,false);
        void* payload=At<void*>(slot,0x808),*icon=At<void*>(slot,0x820);
        uint64_t expectedIcon=0;learned[i].Get("icon").UInt(expectedIcon);
        if(!payload||!icon||At<int32_t>(payload,8)!=1||
           At<int64_t>(payload,0)!=static_cast<int64_t>(source.row)||
           At<int32_t>(payload,0xc)!=static_cast<int32_t>(expectedIcon)){
            s.status="ATS_WINDOW_SPELL_SLOT_SHOW_UNCONFIRMED";return false;}
        ++s.spellFilled;
    }
    SpellPage(s.spellPage);
    return true;
}
inline bool OpenSpellImpl() {
    if(!Current()||!state->loaded||state->saving)return false;auto& s=*state;
    s.status="ATS_WINDOW_SPELL_OPENING";
    if(s.spellWindow.layout){RetireSpell();if(s.spellWindow.layout)return false;}
    s.spellRequested=s.draft.Get("learned_spells").array.size();s.spellFilled=0;
    s.spellPlacement="UNOBSERVED";
    s.spellWindow.registryName="SLCompSpell";s.spellCreating=true;s.spellClosePending=false;
    s.spellWindow.creation=[](void* node){ConstructSpell(node);};
    s.spellWindow.log=[](void*){++adapterErrors;};
    const String32 resource=Borrow("SpellScene.csb"),name=Borrow("SpellLayout");
    using Load=void*(__fastcall*)(const String32*,const String32*,const ResourceFunction*,const ResourceFunction*);
    void* loaded=Call<Load>(0xbe76e0)(&resource,&name,&s.spellWindow.creation,&s.spellWindow.log);
    s.spellCreating=false;
    if(!loaded||!s.spellWindow.layout||!s.spellRoot)return false;
    EmptyModelCallbacks(s.spellRoot);
    void* close=Lookup(s.spellWindow.layout,"Root.Bt_Close",false);if(!close)return false;
    Function callback=[layout=s.spellWindow.layout](void*){Call<One>(0xa10570)(layout);};
    using Assign=void*(__fastcall*)(void*,const Function*);
    Call<Assign>(0xa5c1e0)(static_cast<char*>(close)+0x4f0,&callback);ReleaseNode(close);
    companion3_ui::Lease lease{};lease.layout=s.spellWindow.layout;lease.control=s.spellOwner.control;lease.root=s.spellRoot;
    if(!RegisterLayout(s.spellWindow,lease))return false;
    void* parent=SceneParent(s.spellWindow.registryManager.object,s.spellRoot);if(!parent)return false;
    ++At<int32_t>(parent,8);using Remove=void(__fastcall*)(void*);using Add=void(__fastcall*)(void*,void*);
    Vcall<Remove>(s.spellRoot,0x220)(s.spellRoot);Vcall<Add>(parent,0x1d0)(parent,s.spellRoot);ReleaseNode(parent);
    void* borrowed=s.spellRoot;++At<int32_t>(borrowed,8);
    using Prepare=void(__fastcall*)(void**);Call<Prepare>(0xa576c0)(&borrowed);
    using Mask=void(__fastcall*)(void*,uint32_t,bool);Vcall<Mask>(s.spellRoot,0x468)(s.spellRoot,2,true);
    for(const char* path:{"Root.ElfSpellPanel","Root.PrinceSpellPanel","Root.KnightSpellPanel"}){
        void* node=Lookup(s.spellWindow.layout,path,false);if(node){Visible(node,false);ReleaseNode(node);}}
    if(!BuildSpellSlots())return false;
    for(size_t page=0;page<10;++page){char path[90]{};
        sprintf_s(path,"Root.NomalSpellPanel.Page_%u.Bt_%u",static_cast<unsigned>(page+1),static_cast<unsigned>(page+1));
        void* button=Lookup(s.spellWindow.layout,path,false);
        if(button){Function select=[page](void*){SpellPage(page);};
            Call<Assign>(0xa5c1e0)(static_cast<char*>(button)+0x4f0,&select);ReleaseNode(button);}}
    SpellShowWindow(s.spellWindow.layout,true);s.spellClosePending=false;
    if(!ShowSpellSlots())return false;
    PlaceSpell();
    s.status="ATS_WINDOW_COMPANION_SPELL_OPENED";return true;
}
inline bool OpenSpellNative() {
    __try{return OpenSpellImpl();}
    __except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;if(state)state->status="ATS_WINDOW_SPELL_OPEN_SEH";return false;}
}
inline void ReportSpellOpenImpl() {
    if(!state)return;auto& s=*state;using J=companion5_json::Value;
    forward_diagnostic::Context c{};
    if(!forward_diagnostic::context(c)||!manual_move::SameOwner(c)||!manual_move::CorrectThread(c))return;
    J result;result.kind=J::Object;
    auto integer=[&](const char* key,uint64_t value){result.object[key]=J::Integer(value);};
    auto text=[&](const char* key,const char* value){result.object[key]=J::Text(value);};
    auto boolean=[](bool value){J out;out.kind=J::Boolean;out.text=value?"true":"false";return out;};
    auto real=[](float value){J out;if(std::isfinite(value)){out.kind=J::Number;out.text=std::to_string(value);}return out;};
    auto shown=[&](void* node){using IsVisible=bool(__fastcall*)(void*);
        for(;node;node=At<void*>(node,0x190))if(!Vcall<IsVisible>(node,0x150)(node))return false;
        return true;};
    void* scene=s.spellRoot?PlacementScene(s.spellRoot):nullptr;
    auto bounds=[&](void* node){J out;PlacementRect rect{};
        if(scene&&node&&PlacementScene(node)==scene&&PlacementBounds(node,scene,rect)){
            out.kind=J::Object;out.object["left"]=real(rect.left);out.object["bottom"]=real(rect.bottom);
            out.object["right"]=real(rect.right);out.object["top"]=real(rect.top);
            out.object["visible"]=boolean(shown(node));}
        return out;};
    auto point=[&](const Vec2& value){J out;out.kind=J::Object;
        out.object["x"]=real(value.x);out.object["y"]=real(value.y);return out;};
    auto geometry=[&](void* node){J out;if(!node)return out;out.kind=J::Object;
        void* parent=At<void*>(node,0x190);
        const Vec2 anchor=At<Vec2>(node,0x64),size=At<Vec2>(node,0x6c);
        out.object["node"]=J::Integer(reinterpret_cast<uintptr_t>(node));
        out.object["position"]=point(At<Vec2>(node,0x3c));
        out.object["anchor"]=point(anchor);
        out.object["content_size"]=point(size);
        out.object["ignore_anchor_for_position"]=boolean(At<uint8_t>(node,0x1fa)!=0);
        out.object["parent"]=J::Integer(reinterpret_cast<uintptr_t>(parent));
        if(parent){out.object["parent_position"]=point(At<Vec2>(parent,0x3c));
            out.object["parent_anchor"]=point(At<Vec2>(parent,0x64));
            out.object["parent_content_size"]=point(At<Vec2>(parent,0x6c));}
        // B5A1D0 accumulates the native Node transform through all parents
        // when ancestor=null. tx/ty are convert-to-world of local (0,0).
        PlacementAffine world{};
        using ToWorld=PlacementAffine*(__fastcall*)(void*,PlacementAffine*,void*);
        Call<ToWorld>(0xb5a1d0)(node,&world,nullptr);
        out.object["world_origin"]=point({world.tx,world.ty});
        out.object["world_anchor"]=point({world.tx+world.a*size.x*anchor.x+world.c*size.y*anchor.y,
                                           world.ty+world.b*size.x*anchor.x+world.d*size.y*anchor.y});
        J affine;affine.kind=J::Object;
        affine.object["a"]=real(world.a);affine.object["b"]=real(world.b);
        affine.object["c"]=real(world.c);affine.object["d"]=real(world.d);
        affine.object["tx"]=real(world.tx);affine.object["ty"]=real(world.ty);
        out.object["world_affine"]=std::move(affine);
        out.object["scene_bounds"]=bounds(node);
        return out;};
    auto color=[&](void* node,size_t offset){J out;out.kind=J::Object;
        out.object["r"]=J::Integer(At<uint8_t>(node,offset));
        out.object["g"]=J::Integer(At<uint8_t>(node,offset+1));
        out.object["b"]=J::Integer(At<uint8_t>(node,offset+2));return out;};
    auto renderNode=[&](void* node){J out;if(!node)return out;out.kind=J::Object;
        out.object["node"]=J::Integer(reinterpret_cast<uintptr_t>(node));
        out.object["parent"]=J::Integer(reinterpret_cast<uintptr_t>(At<void*>(node,0x190)));
        out.object["vptr_rva"]=J::Integer(At<uintptr_t>(node,0)-base);
        out.object["visible_local"]=boolean(At<uint8_t>(node,0x1f9)!=0);
        out.object["running"]=boolean(At<uint8_t>(node,0x1f8)!=0);
        J localZ;localZ.kind=J::Number;localZ.text=std::to_string(At<int32_t>(node,0x16c));
        out.object["local_z_order"]=std::move(localZ);
        out.object["global_z_order"]=real(At<float>(node,0x170));
        out.object["camera_mask"]=J::Integer(At<uint16_t>(node,0x212));
        out.object["real_opacity"]=J::Integer(At<uint8_t>(node,0x209));
        out.object["displayed_opacity"]=J::Integer(At<uint8_t>(node,0x208));
        out.object["cascade_opacity"]=boolean(At<uint8_t>(node,0x211)!=0);
        out.object["real_color"]=color(node,0x20d);
        out.object["displayed_color"]=color(node,0x20a);
        out.object["cascade_color"]=boolean(At<uint8_t>(node,0x210)!=0);
        return out;};
    auto ancestors=[&](void* node){J out;out.kind=J::Array;
        for(unsigned depth=0;node&&depth<32;++depth,node=At<void*>(node,0x190))
            out.array.push_back(renderNode(node));
        return out;};
    auto iconSprite=[&](void* icon){J out;if(!icon)return out;out.kind=J::Object;
        void* renderer=At<void*>(icon,0x720);
        void* sprite=renderer?Cast(renderer,0x1686fd0):nullptr;
        out.object["renderer"]=J::Integer(reinterpret_cast<uintptr_t>(renderer));
        out.object["sprite"]=J::Integer(reinterpret_cast<uintptr_t>(sprite));
        out.object["renderer_state"]=renderNode(renderer);
        out.object["renderer_geometry"]=geometry(renderer);
        if(sprite){void* texture=At<void*>(sprite,0x3b8);
            out.object["texture"]=J::Integer(reinterpret_cast<uintptr_t>(texture));
            // BFDC60 Sprite::draw returns before queue submission when
            // texture+20 is zero. Sample that exact native draw guard.
            out.object["texture_draw_handle"]=J::Integer(texture?At<uintptr_t>(texture,0x20):0);
            out.object["sprite_cull_cache"]=boolean(At<uint8_t>(sprite,0x613)!=0);
            J rect;rect.kind=J::Object;
            rect.object["x"]=real(At<float>(sprite,0x504));rect.object["y"]=real(At<float>(sprite,0x508));
            rect.object["width"]=real(At<float>(sprite,0x50c));rect.object["height"]=real(At<float>(sprite,0x510));
            out.object["texture_rect"]=std::move(rect);}
        const String32& path=At<String32>(icon,0x738);
        if(path.size<=512&&path.capacity>=path.size){
            const char* bytes=path.capacity>15?path.pointer:path.inlineBytes;
            if(bytes)out.object["frame_path"]=J::Text(std::string(bytes,path.size));}
        return out;};
    auto clipping=[&](void* list){J out;if(!list)return out;out.kind=J::Object;
        out.object["enabled"]=boolean(At<uint8_t>(list,0x748)!=0);
        out.object["clip_node"]=J::Integer(reinterpret_cast<uintptr_t>(At<void*>(list,0x750)));
        out.object["viewport_scene_bounds"]=bounds(list);
        J raw;raw.kind=J::Object;
        raw.object["x"]=real(At<float>(list,0x778));raw.object["y"]=real(At<float>(list,0x77c));
        raw.object["width"]=real(At<float>(list,0x780));raw.object["height"]=real(At<float>(list,0x784));
        out.object["clip_rect_raw_778"]=std::move(raw);return out;};
    auto bodyBounds=[&](void* layout){J out;if(!layout)return out;
        void* body=Lookup(layout,"Root.Background",false);
        out=bounds(body?body:At<void*>(layout,0x30));ReleaseNode(body);return out;};
    const uint64_t sequence=++spellResultSequence;
    text("schema","companion-ats-spell-open-v1");integer("pid",c.pid);integer("birth",c.birth);
    text("candidate_sha256",OWN_EXPECTED_PROGRAM_SHA);integer("counter",sequence);
    text("status",s.status);integer("member_id",s.identity.member);integer("edit_epoch",s.editEpoch);
    integer("actor_uid",s.identity.actor);integer("layout",reinterpret_cast<uintptr_t>(s.spellWindow.layout));
    integer("root",reinterpret_cast<uintptr_t>(s.spellRoot));integer("requested_count",s.spellRequested);
    integer("filled_count",s.spellFilled);integer("page",s.spellPage);
    integer("ats_open_ms",s.openMs);integer("ats_widgets_ms",s.widgetsMs);
    integer("heal_resource_load_ms",s.healLoadMs);integer("heal_setup_ms",s.healSetupMs);
    result.object["heal_created"]=boolean(s.healReady);
    text("sample_phase",s.spellDiagnosticPhase);
    result.object["visible"]=boolean(s.spellRoot&&shown(s.spellRoot));
    result.object["spell_list_geometry"]=geometry(s.spellList);
    result.object["spell_list_inner_geometry"]=geometry(s.spellList?At<void*>(s.spellList,0xce0):nullptr);
    result.object["spell_list_render"]=renderNode(s.spellList);
    result.object["spell_list_clipping"]=clipping(s.spellList);
    result.object["spell_list_ancestors"]=ancestors(s.spellList);
    result.object["spell_inner_render"]=renderNode(s.spellList?At<void*>(s.spellList,0xce0):nullptr);
    result.object["spell_inner_clipping"]=clipping(s.spellList?At<void*>(s.spellList,0xce0):nullptr);
    if(s.spellList){void** begin=At<void**>(s.spellList,0xdd8),**end=At<void**>(s.spellList,0xde0);
        if(begin&&end&&end>=begin&&end-begin<=128)integer("list_item_count",static_cast<uint64_t>(end-begin));
        void* inner=At<void*>(s.spellList,0xce0);
        if(inner){begin=At<void**>(inner,0x178);end=At<void**>(inner,0x180);
            if(begin&&end&&end>=begin&&end-begin<=128)integer("inner_child_count",static_cast<uint64_t>(end-begin));}}
    void* spellBackground=Lookup(s.spellWindow.layout,"Root.Background",false);
    result.object["spell_background_render"]=renderNode(spellBackground);
    result.object["spell_background_geometry"]=geometry(spellBackground);
    ReleaseNode(spellBackground);
    void* slotFrame=Lookup(s.spellWindow.layout,"Root.SlotFrame",false);
    result.object["slot_frame_render"]=renderNode(slotFrame);
    result.object["slot_frame_geometry"]=geometry(slotFrame);
    ReleaseNode(slotFrame);
    using Camera=void*(__fastcall*)(void*,int);
    void* uiCamera=Call<Camera>(0x1d3160)(*reinterpret_cast<void**>(base+0x1809d10),2);
    result.object["ui_camera"]=J::Integer(reinterpret_cast<uintptr_t>(uiCamera));
    result.object["render_queue_observation"]=J::Text("NOT_OBSERVED; running, camera mask and sprite state are sampled");
    J rows;rows.kind=J::Array;size_t displayed=0;
    for(size_t i=0;i<s.spellSlots.size();++i){const auto& source=s.spellSlots[i];
        void* slot=FindSlotNode(source.node);if(!slot)continue;
        void* payload=At<void*>(slot,0x808),*panel=At<void*>(slot,0x830),*icon=At<void*>(slot,0x820);
        if(!payload)continue;J row;row.kind=J::Object;
        row.object["node"]=J::Integer(reinterpret_cast<uintptr_t>(slot));
        row.object["node_name"]=J::Text(NodeName(slot));
        row.object["vptr_rva"]=J::Integer(At<uintptr_t>(slot,0)-base);
        row.object["metadata"]=J::Integer(reinterpret_cast<uintptr_t>(payload));
        row.object["panel"]=J::Integer(reinterpret_cast<uintptr_t>(panel));
        row.object["icon_node"]=J::Integer(reinterpret_cast<uintptr_t>(icon));
        row.object["slot_geometry"]=geometry(slot);
        row.object["panel_geometry"]=geometry(panel);
        row.object["icon_geometry"]=geometry(icon);
        row.object["icon_sprite"]=iconSprite(icon);
        row.object["icon_ancestors"]=ancestors(icon);
        row.object["kind"]=J::Integer(static_cast<uint64_t>(At<int32_t>(payload,8)));
        row.object["spell_row"]=J::Integer(static_cast<uint64_t>(At<int64_t>(payload,0)));
        row.object["icon"]=J::Integer(static_cast<uint64_t>(At<int32_t>(payload,0xc)));
        row.object["name"]=J::Text(*reinterpret_cast<std::string*>(static_cast<char*>(payload)+0x30));
        row.object["page"]=J::Integer(i/32);
        const bool visible=shown(slot)&&icon&&shown(icon);
        row.object["visible"]=boolean(visible);if(visible)++displayed;
        row.object["camera_mask_before"]=J::Integer(source.maskBefore);
        row.object["icon_camera_mask_before"]=J::Integer(source.iconMaskBefore);
        row.object["camera_mask"]=J::Integer(At<uint16_t>(slot,0x212));
        if(icon)row.object["icon_camera_mask"]=J::Integer(At<uint16_t>(icon,0x212));
        rows.array.push_back(std::move(row));
    }
    result.object["native_spell_rows"]=std::move(rows);integer("displayed_count",displayed);
    J placement;placement.kind=J::Object;placement.object["status"]=J::Text(s.spellPlacement);
    placement.object["spell"]=bodyBounds(s.spellWindow.layout);
    placement.object["ats"]=bodyBounds(s.window.layout);
    if(records)placement.object["bag"]=bodyBounds(records[0].layout);
    J pets;pets.kind=J::Array;
    for(const auto& view:views)if(view.layout&&view.actor==s.identity.actor)pets.array.push_back(bodyBounds(view.layout));
    placement.object["pet"]=std::move(pets);result.object["placement"]=std::move(placement);
    // Passive original SpellLayout comparison only when its native instance
    // already exists. Never open it or populate its SELF-backed adapter here.
    J knight;knight.kind=J::Object;knight.object["status"]=J::Text("NOT_REGISTERED");
    Pair manager{},nativeSpell{};struct HeldPair {Pair& value;~HeldPair(){Release(nullptr,value);}};
    HeldPair heldManager{manager},heldSpell{nativeSpell};
    using GetManager=Pair*(__fastcall*)(Pair*);Call<GetManager>(0x560f0)(&manager);
    if(manager.object){const String32 name=Borrow("SpellLayout");
        using LookupLayout=Pair*(__fastcall*)(void*,Pair*,const String32*);
        Call<LookupLayout>(0xb3a0b0)(manager.object,&nativeSpell,&name);
        if(nativeSpell.object&&nativeSpell.object!=s.spellWindow.layout){
            knight.object["status"]=J::Text("REGISTERED_NO_GRID");
            knight.object["layout"]=J::Integer(reinterpret_cast<uintptr_t>(nativeSpell.object));
            void* grid=At<void*>(nativeSpell.object,0xb8);
            if(grid&&Cast(grid,0x1760fb8)){
                knight.object["status"]=J::Text("GRID_OBSERVED");
                knight.object["grid_render"]=renderNode(grid);
                knight.object["grid_clipping"]=clipping(grid);
                J nativeRows;nativeRows.kind=J::Array;
                void** begin=At<void**>(grid,0xec8),**end=At<void**>(grid,0xed0);
                if(begin&&end&&end>=begin&&end-begin<=128)
                    for(void** item=begin;item!=end&&nativeRows.array.size()<4;++item){
                        void* node=*item?FindSlotNode(*item):nullptr;if(!node)continue;
                        void* icon=At<void*>(node,0x820);J sample;sample.kind=J::Object;
                        sample.object["slot_geometry"]=geometry(node);
                        sample.object["slot_render"]=renderNode(node);
                        sample.object["icon_geometry"]=geometry(icon);
                        sample.object["icon_sprite"]=iconSprite(icon);
                        sample.object["icon_ancestors"]=ancestors(icon);
                        nativeRows.array.push_back(std::move(sample));}
                knight.object["rows"]=std::move(nativeRows);
            }
        }}
    result.object["knight_spell_comparison"]=std::move(knight);
    const std::string bytes=companion5_json::Encode(result);wchar_t path[600]{};
    swprintf_s(path,L"%s\\companion-ats-spell-open-%llu.json",c.directory,static_cast<unsigned long long>(sequence));
    if(!WriteNew(path,bytes.data(),static_cast<DWORD>(bytes.size())))++signalErrors;
}
inline void ReportSpellOpenTry() noexcept {
    try{ReportSpellOpenImpl();}catch(...){++adapterErrors;}
}
inline void ReportSpellOpen() noexcept {
    __try{ReportSpellOpenTry();}__except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;}
}
#if defined(COMPANION_NC_GLFW_INPUT)
inline void ReportSpellDragInputImpl(const char* phase,unsigned sequence,unsigned event,void* host) {
    if(!state||!host||!OnUi())return;
    forward_diagnostic::Context c{};
    if(!forward_diagnostic::context(c)||!manual_move::SameOwner(c)||!manual_move::CorrectThread(c))return;
    using J=companion5_json::Value;
    auto ptr=[](void* value){return J::Integer(reinterpret_cast<uintptr_t>(value));};
    auto number=[](double value){J out;out.kind=J::Number;out.text=std::to_string(value);return out;};
    auto boolean=[](bool value){J out;out.kind=J::Boolean;out.text=value?"true":"false";return out;};
    auto source=[&](void* layout,void* root,void* grid,void* input,void* knownDrop,void* slot){
        J row;row.kind=J::Object;
        row.object["layout"]=ptr(layout);row.object["root"]=ptr(root);
        row.object["grid"]=ptr(grid);row.object["input_component"]=ptr(input);
        if(grid)row.object["grid_vptr"]=ptr(At<void*>(grid,0));
        if(input){row.object["input_vptr"]=ptr(At<void*>(input,0));
            row.object["input_40"]=ptr(At<void*>(input,0x40));
            row.object["input_48"]=ptr(At<void*>(input,0x48));}
        using FindDrop=void*(__fastcall*)(void*);
        void* found=root?Call<FindDrop>(0x9082b0)(root):nullptr;
        void* drop=found?found:knownDrop;
        row.object["found_drop"]=ptr(found);row.object["known_drop"]=ptr(knownDrop);
        row.object["drop"]=ptr(drop);row.object["slot"]=ptr(slot);
        if(slot){
            row.object["slot_vptr"]=ptr(At<void*>(slot,0));
            row.object["slot_drag_owner_7c0"]=ptr(At<void*>(slot,0x7c0));
            row.object["slot_predicate_target_800"]=ptr(At<void*>(slot,0x800));
            row.object["slot_payload_808"]=ptr(At<void*>(slot,0x808));
            row.object["slot_panel_830"]=ptr(At<void*>(slot,0x830));
            row.object["slot_flag_818"]=J::Integer(At<uint8_t>(slot,0x818));
            void* payload=At<void*>(slot,0x808);
            if(payload){row.object["payload_kind"]=J::Integer(At<uint32_t>(payload,8));
                row.object["payload_row_or_uid"]=J::Integer(At<uint64_t>(payload,0));}
        }
        if(drop){
            row.object["drop_vptr"]=ptr(At<void*>(drop,0));
            // B0A0B0 registers the original SpellLayout drag start/update
            // function64 objects at +48/+88 before its +C8 release action.
            row.object["drag_start_48_vptr"]=ptr(At<void*>(drop,0x48));
            row.object["drag_update_88_vptr"]=ptr(At<void*>(drop,0x88));
            row.object["source_c8_vptr"]=ptr(At<void*>(drop,0xc8));
            row.object["target_108_vptr"]=ptr(At<void*>(drop,0x108));
            row.object["drag_start_48_target"]=ptr(At<void*>(drop,0x80));
            row.object["drag_update_88_target"]=ptr(At<void*>(drop,0xc0));
            row.object["source_c8_target"]=ptr(At<void*>(drop,0x100));
            row.object["target_108_target"]=ptr(At<void*>(drop,0x140));
            row.object["route_148"]=J::Integer(At<uint8_t>(drop,0x148));
            row.object["drag_pair_object_170"]=ptr(At<void*>(drop,0x170));
            row.object["drag_pair_control_178"]=ptr(At<void*>(drop,0x178));
            row.object["drop_grid_180"]=ptr(At<void*>(drop,0x180));
            auto** first=At<void**>(drop,0x158),**last=At<void**>(drop,0x160);
            if(first&&last&&last>=first&&last-first<=512){
                row.object["registered_count"]=J::Integer(static_cast<uint64_t>(last-first));
                bool foundSlot=false;for(auto** p=first;p!=last;++p)if(*p==slot)foundSlot=true;
                row.object["slot_registered"]=boolean(slot&&foundSlot);
            }
        }
        return row;
    };
    J result;result.kind=J::Object;result.object["schema"]=J::Text("companion-spell-drag-input-v1");
    result.object["phase"]=J::Text(phase);result.object["sequence"]=J::Integer(sequence);
    result.object["event"]=J::Integer(event);
    result.object["host_x"]=number(At<double>(host,0x1f8));
    result.object["host_y"]=number(At<double>(host,0x200));
    result.object["host_left_90"]=J::Integer(At<uint8_t>(host,0x90));
    J sources;sources.kind=J::Object;
    void* companionSlot=state->spellSlots.empty()?nullptr:FindSlotNode(state->spellSlots.front().node);
    sources.object["companion_spell"]=source(state->spellWindow.layout,state->spellRoot,
        state->spellList,state->spellInput,state->spellDrop,companionSlot);
    if(records&&records[0].layout){auto& bag=records[0];void* bagSlot=nullptr;
        if(bag.grid){void** first=At<void**>(bag.grid,0xec8),**last=At<void**>(bag.grid,0xed0);
            if(first&&last&&last>=first&&last-first<=512)
                for(void** p=first;p!=last&&!bagSlot;++p)if(*p)bagSlot=FindSlotNode(*p);}
        sources.object["companion_bag"]=source(bag.layout,At<void*>(bag.layout,0x30),
            bag.grid,nullptr,bag.dropComponent,bagSlot);
        sources.object["companion_bag"].object["input_installed"]=boolean(bag.inputInstalled);
        sources.object["companion_bag"].object["input_callback_count"]=J::Integer(bag.inputCallbackCount);
    }else {J missing;missing.kind=J::Object;missing.object["status"]=J::Text("NOT_OPEN");
        sources.object["companion_bag"]=std::move(missing);}
    // The SELF Bag lease can be retired independently of this ATS state.
    // Only the owned companion Bag above is needed for this item source probe.
    Pair manager{},knight{};struct Held {Pair& pair;~Held(){Release(nullptr,pair);}} heldManager{manager},heldKnight{knight};
    using GetManager=Pair*(__fastcall*)(Pair*);Call<GetManager>(0x560f0)(&manager);
    if(manager.object){const String32 name=Borrow("SpellLayout");
        using LookupLayout=Pair*(__fastcall*)(void*,Pair*,const String32*);
        Call<LookupLayout>(0xb3a0b0)(manager.object,&knight,&name);}
    if(knight.object&&knight.object!=state->spellWindow.layout){
        void* root=At<void*>(knight.object,0x30),*grid=At<void*>(knight.object,0xb8);
        void* knightSlot=nullptr;
        if(grid&&Cast(grid,0x1760fb8)){void** first=At<void**>(grid,0xec8),**last=At<void**>(grid,0xed0);
            if(first&&last&&last>=first&&last-first<=128)
                for(void** p=first;p!=last&&!knightSlot;++p)if(*p)knightSlot=FindSlotNode(*p);}
        void* input=At<uintptr_t>(knight.object,0)==base+0x12341c8?At<void*>(knight.object,0x100):nullptr;
        sources.object["knight_spell"]=source(knight.object,root,grid,input,nullptr,knightSlot);
    }else {J missing;missing.kind=J::Object;missing.object["status"]=J::Text("NOT_REGISTERED");
        sources.object["knight_spell"]=std::move(missing);}
    result.object["sources"]=std::move(sources);
    const std::string bytes=companion5_json::Encode(result);wchar_t path[600]{};
    swprintf_s(path,L"%s\\companion-spell-drag-input-%u-%u-%hs.json",c.directory,sequence,event,phase);
    if(!WriteNew(path,bytes.data(),static_cast<DWORD>(bytes.size())))++signalErrors;
}
inline void ReportSpellDragInputTry(const char* phase,unsigned sequence,unsigned event,void* host) noexcept {
    try{ReportSpellDragInputImpl(phase,sequence,event,host);}catch(...){++adapterErrors;}
}
inline void ReportSpellDragInput(const char* phase,unsigned sequence,unsigned event,void* host) noexcept {
    __try{ReportSpellDragInputTry(phase,sequence,event,host);}
    __except(EXCEPTION_EXECUTE_HANDLER){++adapterErrors;}
}
inline VOID CALLBACK SpellRenderSample(HWND,UINT,UINT_PTR id,DWORD) {
    KillTimer(nullptr,id);
    if(!state||state->spellDiagnosticTimer!=id)return;
    state->spellDiagnosticTimer=0;
    if(!Current()||!state->spellWindow.layout||state->spellClosePending)return;
    state->spellDiagnosticPhase="AFTER_1500MS";
    ReportSpellOpen();
}
#endif
inline VOID CALLBACK SpellLayoutTick(HWND,UINT,UINT_PTR id,DWORD) {
    if(!state||state->spellLayoutTimer!=id)return;
    try{RestoreSpellGrid();}catch(...){++adapterErrors;}
    SpellDragTick();
}
inline VOID CALLBACK BuffLayoutTick(HWND,UINT,UINT_PTR id,DWORD) {
    if(!state||state->atsLayoutTimer!=id)return;
    try{RestoreBuffGrid();}catch(...){++adapterErrors;}
    AtsDragTick();
}
inline bool OpenSpell() {
    bool opened=false;try{opened=OpenSpellNative();}catch(...){++adapterErrors;if(state)state->status="ATS_WINDOW_SPELL_OPEN_EXCEPTION";}
    if(opened&&state){state->spellLayoutTimer=SetTimer(nullptr,0,15,&SpellLayoutTick);
        if(!state->spellLayoutTimer){state->status="ATS_WINDOW_SPELL_LAYOUT_TIMER_UNAVAILABLE";opened=false;}}
    // The open button executes after ats-window-view's result was published.
    // Preserve the actual callback result (including partial fill/refusal)
    // in that same owned bridge directory before a failed window is retired.
    if(state)state->spellDiagnosticPhase="OPEN";
    ReportSpellOpen();
    if(!opened){const char* failure=state?state->status:"ATS_WINDOW_COMPANION_SPELL_UNAVAILABLE";
        RetireSpell();if(state)state->status=failure;}
#if defined(COMPANION_NC_GLFW_INPUT)
    else if(state)state->spellDiagnosticTimer=SetTimer(nullptr,0,1500,&SpellRenderSample);
#endif
    return opened;
}
inline bool OpenImpl(const Mapping& mapping) {
    if(!state)state=new State;
    auto& s=*state;s.diagnostic={};s.imageSize=0;s.titleTracing=false;
    s.openMs=0;s.widgetsMs=0;s.healLoadMs=0;s.healSetupMs=0;
    Step("ORIGINAL_IMAGE_BOUNDS");
    const auto* dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    const auto* nt=reinterpret_cast<const IMAGE_NT_HEADERS*>(base+dos->e_lfanew);
    s.imageSize=nt->OptionalHeader.SizeOfImage;
    if(s.window.layout){Step("PREVIOUS_WINDOW_RETIRE");RetireImpl();if(s.window.layout)return false;}
    Step("KNIGHT_ATS_VISIBILITY_READ");if(!CloseVisibleKnightAts()){
        s.status="ATS_WINDOW_KNIGHT_CLOSE_UNCONFIRMED";return false;}
    s.identity=mapping;s.failed=false;s.closePending=false;s.creating=true;
    s.window.registryName="SLCompATS";
    // User: remove the title entirely, without replacement text or lookup.
    s.caption.clear();s.window.titleOverride=nullptr;s.window.titleStylePath=nullptr;
    Step("RESOURCE_CALLBACKS_CONSTRUCT");
    s.window.creation=[](void* node){Construct(node);};s.window.log=[](void*){++adapterErrors;};
    const String32 resource=Borrow("ATSLayoutScene.csb"),name=Borrow("ATSLayout");
    using Load=void*(__fastcall*)(const String32*,const String32*,const ResourceFunction*,const ResourceFunction*);
    s.status="ATS_WINDOW_RESOURCE_LOAD";
    void* loaded=nullptr;
    Step("RESOURCE_LOAD");
    try{loaded=Call<Load>(0xbe76e0)(&resource,&name,&s.window.creation,&s.window.log);s.creating=false;}
    catch(...){s.creating=false;throw;}
    if(!loaded||!s.window.layout||!s.root){s.status="ATS_WINDOW_TREE_UNAVAILABLE";return false;}
    Step("DISABLE_MODEL_CALLBACKS");EmptyModelCallbacks(s.root);
    Step("BIND_WINDOW_WIDGETS");const ULONGLONG widgetsStarted=GetTickCount64();
    const bool widgetsReady=SetupWidgets();s.widgetsMs=GetTickCount64()-widgetsStarted;
    if(!widgetsReady)return false;
    Step("CLOSE_BUTTON_LOOKUP");void* button=Lookup(s.window.layout,"Root.Bt_Close",false);if(!button){s.status="ATS_WINDOW_CLOSE_UNAVAILABLE";return false;}
    Step("CLOSE_CALLBACK_CONSTRUCT");Function close=[layout=s.window.layout](void*){Call<One>(0xa10570)(layout);};
    using Assign=void*(__fastcall*)(void*,const Function*);Step("CLOSE_CALLBACK_ASSIGN");Call<Assign>(0xa5c1e0)(static_cast<char*>(button)+0x4f0,&close);
    Step("CLOSE_BUTTON_RELEASE");ReleaseNode(button);
    companion3_ui::Lease lease{};lease.layout=s.window.layout;lease.control=s.owner.control;lease.root=s.root;
    Step("REGISTER_LAYOUT");if(!RegisterLayout(s.window,lease)){s.status="ATS_WINDOW_REGISTRY_UNAVAILABLE";return false;}
    void* parent=SceneParent(s.window.registryManager.object,s.root);
    if(!parent){s.status="ATS_WINDOW_PARENT_UNAVAILABLE";return false;}
    ++At<int32_t>(parent,8);using Remove=void(__fastcall*)(void*);using Add=void(__fastcall*)(void*,void*);
    Step("ATTACH_REMOVE_ROOT");Vcall<Remove>(s.root,0x220)(s.root);
    Step("ATTACH_ADD_ROOT");Vcall<Add>(parent,0x1d0)(parent,s.root);
    Step("ATTACH_PARENT_RELEASE");ReleaseNode(parent);
    void* borrowed=s.root;++At<int32_t>(borrowed,8);using Prepare=void(__fastcall*)(void**);
    Step("ATTACH_PREPARE_ROOT");Call<Prepare>(0xa576c0)(&borrowed);
    using Mask=void(__fastcall*)(void*,uint32_t,bool);Step("ATTACH_ROOT_MASK");Vcall<Mask>(s.root,0x468)(s.root,2,true);
    // Begin on the first authored tab; isolated local tab callbacks only change
    // page visibility. They never call the original ATS tab/model methods.
    const char* pages[]={"Root.Buff","Root.Combat","Root.Option","Root.Help","Root.Report"};
    for(size_t i=0;i<5;++i){Step("PAGE_LOOKUP");void* page=Lookup(s.window.layout,pages[i],false);if(page){using Visible=void(__fastcall*)(void*,bool);
        Step("PAGE_VISIBILITY");Vcall<Visible>(page,0x148)(page,i==0);Step("PAGE_RELEASE");ReleaseNode(page);}}
    Step("SHOW_WINDOW");ShowWindow(s.window.layout,true);
    // One-time default placement only; native title dragging remains intact.
    Step("WINDOW_POSITION_READ");(void)PlaceWindow();
    // ATS view publication does not publish ItemInfo. Use the existing bag
    // model request without opening the separate Bag layout. Its normal model
    // publication is reconciled by Drain when the revision arrives.
    if(!MemberModel()){
        Step("QUEUE_ITEM_MODEL");const auto* current=Find(mapping.actor);
        if(current){auto& model=ModelFor(*current);
            // Keep the standard request live through Flush's existing guard.
            // ModelRequestFlushed revokes only this ATS-owned visual intent
            // before asynchronous model application; a user Bag is promoted.
            if(!model.view(companion_model::Window::Bag).requested){
                const auto epoch=companion_model::RequestView(model,companion_model::Window::Bag);
                s.bagEvent=Enqueue("bag-open-take",static_cast<uint32_t>(current->actor),nullptr,"QUEUED",current,epoch);
                if(s.bagEvent)s.bagEpoch=epoch;else companion_model::CloseView(model,companion_model::Window::Bag);
            }}
    }
    s.atsLayoutTimer=SetTimer(nullptr,0,15,&BuffLayoutTick);
    if(!s.atsLayoutTimer){s.status="ATS_WINDOW_BUFF_LAYOUT_TIMER_UNAVAILABLE";return false;}
    Step("QUEUE_WINDOW_OPEN");s.openEvent=EnqueueAtsWindow(mapping,false);
    s.status=s.openEvent?"ATS_WINDOW_OPENED":"ATS_WINDOW_OPEN_ENQUEUE_REFUSED";
    return s.openEvent!=0;
}
inline bool OpenNative(const Mapping* mapping) {
    __try{atsOpenBoundary=&NativeBoundary;const bool opened=OpenImpl(*mapping);atsOpenBoundary=nullptr;return opened;}
    __except(CaptureOpenException(GetExceptionInformation())){
        ++adapterErrors;if(state)state->status="ATS_WINDOW_OPEN_SEH_UNKNOWN";return false;}
}
inline bool Open(const Mapping& mapping) noexcept {
    if(!Enabled()||!enabled||!OnUi())return false;
    const ULONGLONG started=GetTickCount64();
    bool ok=false;try{ok=OpenNative(&mapping);}catch(...){atsOpenBoundary=nullptr;++adapterErrors;if(state)state->status="ATS_WINDOW_OPEN_EXCEPTION";}
    if(state)state->openMs=GetTickCount64()-started;
    atsOpenBoundary=nullptr;CaptureBeforeRetire();
    if(!ok){const char* failure=state?state->status:"ATS_WINDOW_UNAVAILABLE";Retire();if(state)state->status=failure;}
    return ok;
}
inline void Drain() noexcept {
    if(!state||!state->window.layout)return;
    if(state->spellClosePending){try{RetireSpell();}catch(...){++adapterErrors;state->status="ATS_WINDOW_SPELL_RETIRE_UNKNOWN";}}
    const Mapping* mapping=Find(state->identity.actor);
    if(state->closePending||!enabled||!mapping||mapping->generation!=state->identity.generation||mapping->owner!=state->identity.owner||mapping->member!=state->identity.member){Retire();return;}
    // Reconcile the existing companion model producer's real revision.
    // Do not replace a locally edited draft when bag metadata arrives.
    if(state->loaded&&!state->saving){const auto* model=MemberModel();if(model&&model->revision!=state->renderedRevision){
        try{Render();}catch(...){++adapterErrors;state->status="ATS_WINDOW_MODEL_REFRESH_EXCEPTION";}}}
}
}
