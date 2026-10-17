#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace fixture {
namespace ui=use_item::owned_ui;
static uintptr_t base=0;static ui::SelectorSource source{};static unsigned queries=0,failQuery=0;
static bool order=true;
static bool Image(uintptr_t at,size_t n) noexcept {
    ++queries;
    if(queries==1)order=order && at==base+source.table-8 && n==0x20;
    else if(queries==2)order=order && at==base+source.col && n==24;
    else order=false;
    return queries!=failQuery;
}
template<class T> void Put(uintptr_t at,T value){memcpy(reinterpret_cast<void*>(at),&value,sizeof(value));}
static void Install(uintptr_t active,const ui::SelectorSource& selected){
    source=selected;queries=0;failQuery=0;order=true;
    Put(active,base+source.table);Put(base+source.table-8,base+source.col);
    Put(base+source.col+12,source.td);Put(base+source.table+0x10,base+source.target);
}
}
int main(){
    using namespace fixture;unsigned cases=0;
    auto check=[&](bool ok,const char* name){++cases;if(!ok)printf("FAIL %s\n",name);return ok;};
    // Private fixture storage only; native same-allocation/Image guard is never replaced in product.
    auto* memory=VirtualAlloc(nullptr,0x134b000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);if(!memory)return 20;
    base=reinterpret_cast<uintptr_t>(memory);const auto priorBase=scope.base;scope.base=base;ui::testSelectorImage=Image;
    alignas(8) unsigned char entry[0x70]{};ui::String32 key{};key.length=9;key.capacity=15;
    memcpy(key.storage,"Inventory",10);memcpy(entry+0x10,&key,sizeof(key));
    uintptr_t activeStorage=0,actual=reinterpret_cast<uintptr_t>(&activeStorage),active=0;
    Put(reinterpret_cast<uintptr_t>(entry)+0x68,actual);ui::Map map{};map.entry=reinterpret_cast<uintptr_t>(entry);
    ui::SelectorTrace trace{};uint32_t target=0;
    auto run=[&](){return ui::SelectorFunction(map,active,&trace,&target);};
    Install(actual,ui::pcSelector);
    if(!check(run() && target==0xa0d5d0 && trace.step==12 && trace.observed==31 && queries==2 && order,"PC exact tuple"))return 1;
    Install(actual,ui::registeredSelector);
    if(!check(run() && target==0xa08250 && trace.step==12 && trace.observed==31 && queries==2 && order,"registered exact tuple"))return 2;
    Install(actual,ui::registeredSelector);Put(base+source.table-8,base+ui::pcSelector.col);
    if(!check(!run() && !target && trace.step==7 && trace.observed==7 && queries==1 && order,"mixed PC COL refused before TD"))return 3;
    Install(actual,ui::registeredSelector);Put(base+source.col+12,ui::pcSelector.td);
    if(!check(!run() && !target && trace.step==9 && trace.observed==15 && queries==2 && order,"mixed PC TD refused before invoke"))return 4;
    Install(actual,ui::registeredSelector);Put(base+source.table+0x10,base+ui::pcSelector.target);
    if(!check(!run() && !target && trace.step==11 && trace.observed==31 && queries==2 && order,"mixed PC invoke refused"))return 5;
    Install(actual,ui::registeredSelector);failQuery=1;
    if(!check(!run() && !target && trace.step==6 && trace.observed==3 && !trace.col && queries==1 && order,"table Image failure no COL read"))return 6;
    Install(actual,ui::registeredSelector);failQuery=2;
    if(!check(!run() && !target && trace.step==8 && trace.observed==7 && !trace.td && !trace.invoke && queries==2 && order,"COL Image failure no TD/invoke read"))return 7;
    Install(actual,ui::registeredSelector);Put(actual,base+source.table+1);
    if(!check(!run() && !target && trace.step==5 && trace.observed==3 && !queries,"unknown table before Image"))return 8;
    Install(actual,ui::pcSelector);if(!run())return 9;const auto firstActive=active;const auto firstTarget=target;
    Install(actual,ui::registeredSelector);
    if(!check(run() && active==firstActive && target!=firstTarget,"same active type switch changes Current compared target"))return 10;
    ui::testSelectorImage=nullptr;scope.base=priorBase;VirtualFree(memory,0,MEM_RELEASE);
    printf("PASS registered selector delta %u cases; Native/current-proof/original-callback0\n",cases);
    return 0;
}
