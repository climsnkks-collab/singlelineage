#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace fixture {
namespace ui=use_item::owned_ui;
struct alignas(8) Entry {unsigned char bytes[0x90]{};};
static Entry sentinel{},a{},b{};static uintptr_t bucket[2]{};
template<class T> void Put(uintptr_t at,size_t offset,T value){memcpy(reinterpret_cast<void*>(at+offset),&value,sizeof(value));}
static uintptr_t Ptr(Entry& e){return reinterpret_cast<uintptr_t>(e.bytes);}
static void Key(Entry& e,const char* name){
    ui::String32 key{};key.length=strlen(name);key.capacity=15;memcpy(key.storage,name,key.length+1);
    Put(Ptr(e),0x10,key);
}
static void Reset(){
    sentinel={};a={};b={};Key(a,"Other");Key(b,"Inventory");Put(Ptr(b),8,Ptr(a));
    bucket[0]=Ptr(a);bucket[1]=Ptr(b);
}
static bool Find(const char* name,ui::Map& found){return ui::Find(Ptr(sentinel),reinterpret_cast<uintptr_t>(bucket),0,
    reinterpret_cast<const unsigned char*>(name),strlen(name),found);}
static unsigned destructs=0;static uint32_t deleting=0;static bool dtorFault=false;
static void __fastcall Dtor(void*,uint32_t value){++destructs;deleting=value;if(dtorFault)RaiseException(0xe0424242,0,0,nullptr);}
static void Child(){ }
static uintptr_t nodeTable[0x1e8/8]{};
static bool CleanupCases(unsigned& checks){
    auto check=[&](bool pass,const char* name){++checks;if(!pass){printf("FAIL %s\n",name);return false;}return true;};
    scope.base=reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    nodeTable[0]=reinterpret_cast<uintptr_t>(&Dtor);nodeTable[0x1e0/8]=0;
    Reset();Put(Ptr(a),0,reinterpret_cast<uintptr_t>(nodeTable));Put(Ptr(a),8,uint32_t{2});
    ui::Flight f{};f.slot=a.bytes;f.slotHeld=true;f.lookupStage=use_item::binding::Stage::Returned;
    destructs=0;deleting=0;dtorFault=false;
    if(!check(ui::GuardedClean(f) && !f.slotHeld && !f.slot && destructs==0 &&
        *reinterpret_cast<uint32_t*>(a.bytes+8)==1,"owned output release ignores unused child target"))return false;
    nodeTable[0x1e0/8]=reinterpret_cast<uintptr_t>(&Child);
    Reset();Put(Ptr(a),0,reinterpret_cast<uintptr_t>(nodeTable));Put(Ptr(a),8,uint32_t{1});
    f={};f.slot=a.bytes;f.slotHeld=true;f.lookupStage=use_item::binding::Stage::Returned;
    if(!check(ui::GuardedClean(f) && !f.slotHeld && !f.slot && destructs==1 && deleting==1,
        "formal owned Slot output may release sole reference after RET"))return false;
    Reset();Put(Ptr(a),0,reinterpret_cast<uintptr_t>(nodeTable));Put(Ptr(a),8,uint32_t{1});dtorFault=true;
    f={};f.slot=a.bytes;f.slotHeld=true;f.lookupStage=use_item::binding::Stage::Returned;
    return check(!ui::GuardedClean(f) && !f.slotHeld && !f.slot && destructs==2,
        "owned Slot cleanup authority consumed before destructor fault");
}
}
int main(int argc,char** argv){
    using namespace fixture;unsigned checks=0;
    if(argc==2 && !strcmp(argv[1],"cleanup-only")){
        if(!CleanupCases(checks))return 1;
        printf("PASS owned-ui cleanup delta %u checks; original game/callback invocation0\n",checks);return 0;
    }
    auto check=[&](bool pass,const char* name){++checks;if(!pass){printf("FAIL %s\n",name);return false;}return true;};
    ui::Map found{};Reset();
    if(!check(Find("Inventory",found) && found.entry==Ptr(b),"actual bucket/key selection"))return 1;
    if(!check(Find("Other",found) && found.entry==Ptr(a),"reverse chain to first"))return 1;
    if(!check(Find("Inventor",found) && !found.entry,"length mismatch is miss"))return 1;
    if(!check(Find("InventoryX",found) && !found.entry,"longer key is miss"))return 1;
    bucket[1]=Ptr(sentinel);if(!check(Find("Inventory",found) && !found.entry,"source sentinel miss"))return 1;
    Reset();bucket[0]=0;if(!check(!Find("Inventory",found),"malformed first even on last match"))return 1;
    Reset();Put(Ptr(b),8,Ptr(b));if(!check(!Find("Absent",found),"finite cycle refusal"))return 1;
    Reset();Put(Ptr(b),0x20,uint64_t{129});if(!check(!Find("Inventory",found),"bounded key length"))return 1;
    Reset();Put(Ptr(b),0x28,uint64_t{14});if(!check(!Find("Inventory",found),"invalid SSO capacity"))return 1;
    Reset();Put(Ptr(b),0x19,static_cast<unsigned char>('x'));if(!check(!Find("Inventory",found),"key terminal zero required"))return 1;
    Reset();
    if(!check(!ui::Find(Ptr(sentinel),reinterpret_cast<uintptr_t>(bucket),2,
        reinterpret_cast<const unsigned char*>("Inventory"),9,found),"invalid bounded mask"))return 1;
    if(!check(!ui::Span(0x7fffffffffff,2) && !ui::Span(0xffff,1),"canonical byte span bounds"))return 1;
    unsigned char buffer[10]="Inventory";ui::String32 heap{};uintptr_t address=reinterpret_cast<uintptr_t>(buffer);
    memcpy(heap.storage,&address,sizeof(address));heap.length=9;heap.capacity=31;
    const auto before=heap;
    if(!check(ui::Text(reinterpret_cast<uintptr_t>(&heap),"Inventory",9) && !memcmp(&heap,&before,sizeof(heap)),"borrowed heap string stays unchanged"))return 1;
    ui::Flight f{};f.variantStage=use_item::binding::Stage::Calling;
    if(!check(!ui::Clean(f),"partial variant has no cleanup authority"))return 1;
    f={};f.pc.stage=use_item::binding::Stage::Ambiguous;
    if(!check(!ui::Clean(f),"mismatched impl storage has no cleanup authority"))return 1;
    Reset();Put(Ptr(a),8,uint32_t{1});void* node=a.bytes;
    if(!check(!ui::ReleaseNode(node) && node==a.bytes,"sole Node reference is unresolved owner"))return 1;
    Put(Ptr(a),8,uint32_t{2});
    if(!check(ui::ReleaseNode(node) && !node && *reinterpret_cast<uint32_t*>(a.bytes+8)==1,"known owned Node reference consumed once"))return 1;
    if(!check(use_item::Io{}.execute==ui::Native,"UseItem routes to owned prefix Native"))return 1;
    char path[256]{};size_t next=0;
    if(!check(ui::AppendName(path,0,reinterpret_cast<const unsigned char*>("Panel"),5,next) && next==5 &&
        !strcmp(path,"Panel"),"actual first child without Root prefix"))return 1;
    if(!check(ui::AppendName(path,next,reinterpret_cast<const unsigned char*>("Slot"),4,next) &&
        !strcmp(path,"Panel.Slot"),"full relative child sequence"))return 1;
    if(!check(!ui::AppendName(path,0,reinterpret_cast<const unsigned char*>(""),0,next),"empty path token refusal"))return 1;
    if(!check(!ui::AppendName(path,0,reinterpret_cast<const unsigned char*>("A.B"),3,next),"dot token is not escaped or normalized"))return 1;
    if(!check(!ui::AppendName(path,255,reinterpret_cast<const unsigned char*>("X"),1,next),"bounded full path"))return 1;
    f={};f.lookupStage=use_item::binding::Stage::Calling;f.slot=a.bytes;
    if(!check(!ui::AcquiredNode(f,nullptr) && f.ambiguous && !f.slotHeld,"mismatched Node output storage grants no authority"))return 1;
    f={};f.lookupStage=use_item::binding::Stage::Calling;f.input=a.bytes;f.slot=b.bytes;
    if(!check(!ui::AcquiredNode(f,&f.slot) && f.ambiguous && !f.slotHeld,"unconsumed input is ambiguous"))return 1;
    f={};f.lookupStage=use_item::binding::Stage::Calling;
    if(!check(ui::AcquiredNode(f,&f.slot) && !f.slotHeld,"normal null lookup is not an owning Node"))return 1;
    alignas(8) unsigned char left[0x1d0]{},right[0x1d0]{};uintptr_t children[]={reinterpret_cast<uintptr_t>(left),reinterpret_cast<uintptr_t>(right)};
    ui::String32 childName{};childName.length=4;childName.capacity=15;memcpy(childName.storage,"Slot",5);
    Put(children[0],0x1a8,childName);Put(children[1],0x1a8,childName);bool unique=false;
    if(!check(ui::UniqueName(reinterpret_cast<uintptr_t>(children),reinterpret_cast<uintptr_t>(children)+16,
        reinterpret_cast<uintptr_t>(children),reinterpret_cast<const unsigned char*>("Slot"),4,unique) && !unique,"duplicate sibling path is ambiguous"))return 1;
    childName.storage[0]='X';Put(children[1],0x1a8,childName);
    if(!check(ui::UniqueName(reinterpret_cast<uintptr_t>(children),reinterpret_cast<uintptr_t>(children)+16,
        reinterpret_cast<uintptr_t>(children),reinterpret_cast<const unsigned char*>("Slot"),4,unique) && unique,"unique actual sibling name"))return 1;
    // Local deleting-Node ABI fixtures; never Native/current proof/Use inputs.
    if(!CleanupCases(checks))return 1;
    printf("PASS owned-ui delta %u checks; original game/callback invocation0\n",checks);return 0;
}
