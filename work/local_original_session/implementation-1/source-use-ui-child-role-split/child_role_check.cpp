#define OWN_SELECTED_HOST_TEST
#define OWN_KEY_HOST_TEST
#include "diagnostic.cpp"
#include <cstdio>
namespace selected_diagnostic {ContextFn test_context=nullptr;OutputFn test_output=nullptr;}
namespace key_diagnostic {void(*test_output)(const char*,const char*,int) noexcept=nullptr;}
uintptr_t test_key_version_return=0;
namespace fixture {
namespace ui=use_item::owned_ui;
static uintptr_t known[0x200/8]{},lookupOther[0x200/8]{},getterOther[0x200/8]{},getterOther2[0x200/8]{};
static unsigned queries=0;static bool deny=false,allowZero=false;
static bool Table(uintptr_t at,size_t n) noexcept {
    ++queries;return !deny && n==0x200 && ((allowZero && !at) || at==reinterpret_cast<uintptr_t>(known) ||
        at==reinterpret_cast<uintptr_t>(lookupOther) || at==reinterpret_cast<uintptr_t>(getterOther) || at==reinterpret_cast<uintptr_t>(getterOther2));
}
struct alignas(8) Node {unsigned char bytes[0x818]{};};
template<class T> void Put(uintptr_t at,T value){memcpy(reinterpret_cast<void*>(at),&value,sizeof(value));}
static uintptr_t Ptr(Node& n){return reinterpret_cast<uintptr_t>(n.bytes);}
static void Init(Node& n,const char* name,uintptr_t* table=known){
    n={};Put(Ptr(n),reinterpret_cast<uintptr_t>(table));Put(Ptr(n)+8,uint32_t{1});
    ui::String32 s{};s.length=strlen(name);s.capacity=15;memcpy(s.storage,name,s.length+1);Put(Ptr(n)+0x1a8,s);
    Put(Ptr(n)+0x1c8,ui::Hash(reinterpret_cast<const unsigned char*>(name),s.length));
}
static void Children(Node& n,uintptr_t* list,size_t count){Put(Ptr(n)+0x178,reinterpret_cast<uintptr_t>(list));Put(Ptr(n)+0x180,reinterpret_cast<uintptr_t>(list)+count*8);}
static char saved[2048]{};static bool outputFault=false;
static bool Context(forward_diagnostic::Context& c) noexcept {c.pid=71;c.birth=89;return true;}
static void Output(const wchar_t* leaf,const char* text,int n) noexcept {
    if(wcscmp(leaf,L"use-item-path-source-failure.json") || n<=0 || n>=2048)return;
    if(outputFault)RaiseException(0xe0424242,0,0,nullptr);
    memcpy(saved,text,static_cast<size_t>(n));saved[n]=0;SetLastError(19);
}
}
int main(){
    using namespace fixture;unsigned cases=0;const auto prior=scope.base;scope.base=0x140000000;
    for(auto* t:{known,lookupOther,getterOther,getterOther2}){t[0]=0;t[0x1e0/8]=scope.base+0xb58430;t[0x1f8/8]=scope.base+0x1498e0;}
    lookupOther[0x1e0/8]++;getterOther[0x1f8/8]++;getterOther2[0x1f8/8]+=2;ui::testPassiveTable=Table;
    auto check=[&](bool ok,const char* name){++cases;if(!ok)printf("FAIL %s\n",name);return ok;};
    Node node{};Init(node,"Parent",lookupOther);ui::PathTrace d{};bool named=true;queries=0;
    if(!check(ui::ChildRoles(Ptr(node),named,&d) && !named && d.observed==7 && d.v2==scope.base+0x1498e0 && queries==1,
        "1E0 mismatch preserves exact1F8 discovery only"))return 1;
    Init(node,"Parent",getterOther);named=true;
    if(!check(!ui::ChildRoles(Ptr(node),named,&d) && !named && d.check==5 && d.observed==7,"1F8 mismatch remains hard refusal"))return 2;
    Put(Ptr(node)+8,uint32_t{0});queries=0;
    if(!check(!ui::ChildRoles(Ptr(node),named,&d) && d.check==1 && !d.observed && !queries,"required Node prefix remains strict"))return 3;
    Put(Ptr(node)+8,uint32_t{1});deny=true;queries=0;
    if(!check(!ui::ChildRoles(Ptr(node),named,&d) && d.check==1 && !d.observed && queries==1,"table image/readspan failure remains strict"))return 4;
    deny=false;allowZero=true;Put(Ptr(node),uintptr_t{0});
    // Force only the query precondition in the host seam: the real Read rejects
    // subcanonical table+1E0, proving read failure is not a named-role mismatch.
    if(!check(!ui::ChildRoles(Ptr(node),named,&d) && d.check==2 && d.observed==1 && !d.v1 && !d.v2,"1E0 read failure is a hard refusal"))return 5;
    allowZero=false;
    Node root{},parent{},leaf{};Init(root,"Q");Init(parent,"Parent",lookupOther);Init(leaf,"Slot");
    uintptr_t rootList[]={Ptr(parent)},parentList[]={Ptr(leaf)};Children(root,rootList,1);Children(parent,parentList,1);
    ui::Flight f{};f.q=Ptr(root);f.rawCount=1;f.rawSlots[0]=Ptr(leaf);char text[256]{};unsigned visited=0,matches=0;d={};d.base=scope.base;use_item::Request request{};
    if(!check(ui::Walk(request,f,f.q,text,0,0,visited,matches,&d) && d.visited==3 && d.registered==1 && d.modelRejected==1 && !d.unsupported,
        "lookup-other parent still discovers registered descendant; real Typed rejects fixture"))return 6;
    // Only post-Model scalar gates, never Native/Current/Lookup proof or input.
    f={};f.q=Ptr(root);matches=0;d={};
    if(!ui::NoteMatch(f,d,Ptr(parent),"Parent",6,true,matches))return 7;
    if(!check(ui::ChildRoles(Ptr(parent),named,&d) && !named && f.candidate==Ptr(parent) && d.addressableMatches==1 &&
        ui::NamedResult(f,d,2,matches),"parent outgoing lookup mismatch does not revoke its incoming self path"))return 7;
    f={};f.q=Ptr(root);matches=0;d={};
    if(!check(ui::NoteMatch(f,d,Ptr(leaf),"",0,false,matches) && !ui::NamedResult(f,d,3,matches) && d.check==4 &&
        d.unaddressableMatches==1 && !f.candidate,"descendant unaddressable match retains explicit refusal"))return 8;
    Node bad1{},bad2{};Init(bad1,"bad1",getterOther);Init(bad2,"bad2",getterOther2);uintptr_t badList[]={Ptr(bad1),Ptr(bad2)};Children(root,badList,2);
    f={};f.q=Ptr(root);visited=matches=0;d={};d.base=scope.base;text[0]=0;
    const bool walked=ui::Walk(request,f,f.q,text,0,0,visited,matches,&d);
    const auto first=d.firstUnsupported;
    if(!check(walked && d.unsupported==2 && !ui::NamedResult(f,d,visited,matches) && d.step==13 && !d.node &&
        first.step==4 && first.check==5 && first.observed==7 && first.node==Ptr(bad1) && first.v2==0x1401498e1 &&
        d.firstUnsupported.node==Ptr(bad1) && d.firstUnsupported.v2==first.v2,"first unsupported freezes before later branch and final summary"))return 9;
    selected_diagnostic::test_context=Context;selected_diagnostic::test_output=Output;
    scope.base=0x180000000;SetLastError(123);ui::PathFailure(request,d);
    const bool normal=GetLastError()==123 && strstr(saved,"\"base\":5368709120") &&
        strstr(saved,"\"first_unsupported\":{\"step\":4,\"check\":5,\"observed_mask\":7") && strstr(saved,"\"step\":13,\"check\":1");
    outputFault=true;SetLastError(456);ui::PathFailure(request,d);
    if(!check(normal && GetLastError()==456,"logger uses captured base/first snapshot and isolates fault/LastError"))return 10;
    ui::testPassiveTable=nullptr;scope.base=prior;
    printf("PASS child role split delta %u cases; getter/Native/current-proof/Lookup/original-callback0\n",cases);return 0;
}
