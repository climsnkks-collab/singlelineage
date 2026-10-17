// In-process static-library prototype. Root must bind verified H inner CODE
// base and invoke from the real selected handler. No DLL/injection/candidate.
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <intrin.h>
#include <utility>

namespace local_native_own_login {
struct Pair {void* object;void* control;};
struct View {const char* data;uint64_t length;};
struct Message {
    void** vtable;uint64_t arena;uint32_t hasbits,cache;
    uint64_t issuer,uuid,optional;uint32_t address,pad;
};
static_assert(sizeof(Message)==0x38 && offsetof(Message,issuer)==0x18 &&
              offsetof(Message,address)==0x30 && sizeof(Pair)==16 && sizeof(View)==16,"original ABI");
struct Inputs {const char* uuid;size_t uuidLength;const char* selectedTag;size_t tagLength;};
struct Result {enum Code:uint32_t { OriginalSenderReturned=0,InvalidInput=1,AlreadyAttempted=2,NoNetwork=3,WrongMessageABI=4,OriginalException=5,OwnCodeNotReady=6 } code;uint32_t socketAddress;};
// Owned local-session latch. One caller-owned instance per own UUID; it must
// remain alive through the handler call. It does not model a socket generation.
struct State {bool attempted=false;char ownUuid[37]={};};
struct Api {
    using New=Message*(*)(void*,void*);
    using Set=void(*)(uint64_t*,const View*,void*);
    using Address=uint32_t(*)(void*);
    using Send=void(*)(void*,uint16_t,Message*);
    using Delete=void*(*)(Message*,uint32_t);
    using GetNetwork=Pair*(*)(void*,Pair*);
    New create;Set set;Address address;Send send;Delete destroy;GetNetwork network;
    uintptr_t expectedMessageVtable;
    // Code-base binding is consumed only inside the game after Root's source
    // identity review. Never call these pointers from a controller process.
    static Api Bind(uintptr_t base) noexcept {
        return {reinterpret_cast<New>(base+0x799d00),reinterpret_cast<Set>(base+0xdde430),
            reinterpret_cast<Address>(base+0x27ee30),reinterpret_cast<Send>(base+0x27d620),
            reinterpret_cast<Delete>(base+0x799fd0),reinterpret_cast<GetNetwork>(base+0x3ec40),
            base+0x11f09d0};
    }
};
bool Valid(const Inputs& in) noexcept {
    if(!in.uuid||in.uuidLength!=36)return false;
    for(size_t n=0;n<36;++n){char c=in.uuid[n];
        if(n==8||n==13||n==18||n==23){if(c!='-')return false;}
        else if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
    }
    if(in.uuid[14]!='4'||!strchr("89ab",in.uuid[19]))return false;
    if(in.tagLength>128 || (in.tagLength && !in.selectedTag))return false;
    for(size_t n=0;n<in.tagLength;++n)if(static_cast<unsigned char>(in.selectedTag[n])<32)return false;
    return true;
}
void Release(void* control) noexcept {
    if(!control)return;
    auto bytes=static_cast<unsigned char*>(control);
    if(_InterlockedExchangeAdd(reinterpret_cast<volatile long*>(bytes+8),-1)==1){
        auto table=*reinterpret_cast<void***>(control);
        reinterpret_cast<void(*)(void*)>(table[0])(control);
        if(_InterlockedExchangeAdd(reinterpret_cast<volatile long*>(bytes+12),-1)==1)
            reinterpret_cast<void(*)(void*)>(table[1])(control);
    }
}
struct Held {Pair pair;~Held(){Release(pair.control);}};
struct Temporary {const Api& api;Message* value;~Temporary(){if(value)api.destroy(value,1);}};

// Input pair is the genuine original3EC40 result retained by the selected
// handler. Retain locally, query actual27EE30, copy own strings with the game's
// allocator, enqueue via original deep clone, destroy then release in that order.
Result SendOwnLoginHeld(const Api& api,const Pair& callerPair,const Inputs& in,State& state) noexcept {
    if(!Valid(in))return {Result::InvalidInput,0};
    if(state.attempted)return {Result::AlreadyAttempted,0};
    if(!callerPair.object||!callerPair.control)return {Result::NoNetwork,0};
    _InterlockedIncrement(reinterpret_cast<volatile long*>(static_cast<unsigned char*>(callerPair.control)+8));
    Held held{callerPair};
    // Consumed before an enqueue attempt: an exception after partial queue work
    // must not trigger a speculative retry. No acknowledgement is synthesized.
    state.attempted=true;memcpy(state.ownUuid,in.uuid,36);state.ownUuid[36]=0;
    uint32_t actual=0;
    try {
        Temporary message{api,api.create(nullptr,nullptr)}; // original New(arena0); RCX unused
        if(!message.value || reinterpret_cast<uintptr_t>(message.value->vtable)!=api.expectedMessageVtable || message.value->arena)
            return {Result::WrongMessageABI,0};
        actual=api.address(held.pair.object); // use exact original return, including its semantics
        message.value->address=actual;message.value->hasbits|=9;
        constexpr char issuer[]="standalone.local";
        View ownIssuer{issuer,sizeof(issuer)-1},ownUuid{state.ownUuid,36};
        api.set(&message.value->issuer,&ownIssuer,nullptr);
        message.value->hasbits|=2;api.set(&message.value->uuid,&ownUuid,nullptr);
        if(in.tagLength){View tag{in.selectedTag,in.tagLength};message.value->hasbits|=4;api.set(&message.value->optional,&tag,nullptr);}
        api.send(held.pair.object,0x0263,message.value);
        // Original26DA90 clones when its role0 sender exists; it can otherwise
        // return silently. Return0 proves this call returned, not an enqueue,
        // socket delivery, SDK success or server login.
        return {Result::OriginalSenderReturned,actual};
    }catch(...){return {Result::OriginalException,actual};}
}
// Optional same original2424E0 accessor sequence; publishedRoot must be a
// legitimate caller-held Root with its original +D8 publication gate true.
Result SendOwnLoginPublished(const Api& api,void* publishedRoot,const Inputs& in,State& state) noexcept {
    if(!publishedRoot || !static_cast<const unsigned char*>(publishedRoot)[0xd8])return {Result::NoNetwork,0};
    Pair pair{};
    try {api.network(publishedRoot,&pair);}
    catch(...){return {Result::OriginalException,0};}
    Held normalGetterPair{pair};
    return SendOwnLoginHeld(api,pair,in,state);
}
}
