#pragma once
// One-shot original Login OK callback on the owned game window's UI thread.
// Included after BridgeScope and source bindings are defined.
static std::atomic<bool> autoOkInstallAttempted{false},autoOkClaimed{false};
static std::atomic<bool> autoCreateClaimed{false};
static std::atomic<bool> autoCreateSucceeded{false},autoSelectOkClaimed{false};
static std::atomic<bool> autoSelectOkSucceeded{false},autoCreateSubmitClaimed{false};
static std::atomic<HWND> autoOkWindow{nullptr};
static std::atomic<UINT> autoOkMessage{0};
static std::atomic<UINT> autoCreateMessage{0};
static std::atomic<UINT> autoSelectOkMessage{0};
static std::atomic<UINT> autoCreateSubmitMessage{0};
static std::atomic<HHOOK> autoOkHook{nullptr};
struct AutoOkWindow {HWND hwnd=nullptr;DWORD thread=0;LONG area=0;};

static BOOL CALLBACK FindAutoOkWindow(HWND hwnd,LPARAM raw) {
    auto* choice=reinterpret_cast<AutoOkWindow*>(raw);DWORD pid=0;
    const DWORD thread=GetWindowThreadProcessId(hwnd,&pid);
    if(pid!=GetCurrentProcessId() || !thread || !IsWindowVisible(hwnd))return TRUE;
    RECT rect{};if(!GetClientRect(hwnd,&rect))return TRUE;
    const LONG width=rect.right-rect.left,height=rect.bottom-rect.top;
    if(width<320 || width>7680 || height<200 || height>4320)return TRUE;
    const LONG area=width*height;
    if(area>choice->area){choice->hwnd=hwnd;choice->thread=thread;choice->area=area;}
    return TRUE;
}

static void AutoOkDiagnostic(const wchar_t* leaf,const char* event,bool success,DWORD error,unsigned reason) noexcept {
    const DWORD before=GetLastError();forward_diagnostic::Context context{};
    if(forward_diagnostic::context(context)) {
        char value[512]{};
        const int length=sprintf_s(value,"{\"schema\":\"own-cp34-auto-ok-v1\",\"event\":\"%s\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"success\":%s,\"native_error\":%lu,\"reason\":%u}\n",
          event,context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,
          success?"true":"false",error,reason);
        wchar_t path[600]{};swprintf_s(path,L"%s\\%s",context.directory,leaf);
        HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file!=INVALID_HANDLE_VALUE){DWORD written=0;if(length>0)WriteFile(file,value,static_cast<DWORD>(length),&written,nullptr);CloseHandle(file);}
    }
    SetLastError(before);
}

static bool AutoOkCanonical(uintptr_t value) noexcept {
    return value>=0x10000 && value<=0x7fffffffffff && (value&7)==0;
}

static bool AutoOkValidated(void* layout,void* button,unsigned& reason) noexcept {
    reason=1;
    const uintptr_t base=scope.base;
    if(!base || !scope.selectedReady.load() || !AutoOkCanonical(reinterpret_cast<uintptr_t>(layout))
       || !AutoOkCanonical(reinterpret_cast<uintptr_t>(button)))return false;
    forward_diagnostic::Context context{};
    if(!forward_diagnostic::context(context)){reason=2;return false;}
    __try {
        auto* root=*reinterpret_cast<uint8_t**>(base+0x1668790);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) || !root[0xd8]){reason=3;return false;}
        auto* gi=*reinterpret_cast<uint8_t**>(root+0xd0);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(gi))){reason=3;return false;}
        const uintptr_t begin=*reinterpret_cast<uintptr_t*>(gi+0x180);
        const uintptr_t end=*reinterpret_cast<uintptr_t*>(gi+0x188);
        if(!AutoOkCanonical(begin) || end<begin || (end-begin)%16 || (end-begin)/16>128){reason=3;return false;}
        uint8_t *ui=nullptr,*gameState=nullptr;
        for(uintptr_t at=begin;at<end;at+=16) {
            auto* object=*reinterpret_cast<uint8_t**>(at);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(object)))continue;
            const uintptr_t vft=*reinterpret_cast<uintptr_t*>(object);
            if(vft==base+0x1182c50){if(ui){reason=4;return false;}ui=object;}
            if(vft==base+0x1182e30){if(gameState){reason=4;return false;}gameState=object;}
        }
        if(!ui || !gameState){reason=4;return false;}
        auto* loginScene=*reinterpret_cast<uint8_t**>(gameState+0x360);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(loginScene))
           || *reinterpret_cast<uintptr_t*>(loginScene)!=base+0x1187f48
           || *reinterpret_cast<uint32_t*>(loginScene+0x10)!=3
           || *reinterpret_cast<uint32_t*>(gameState+0x380)!=3){reason=5;return false;}
        const uintptr_t head=*reinterpret_cast<uintptr_t*>(ui+0x350);
        const uintptr_t count=*reinterpret_cast<uintptr_t*>(ui+0x358);
        if(!AutoOkCanonical(head) || !count || count>64){reason=6;return false;}
        uintptr_t node=*reinterpret_cast<uintptr_t*>(head);unsigned matches=0;
        for(uintptr_t index=0;index<count;++index) {
            if(!AutoOkCanonical(node) || node==head){reason=6;return false;}
            auto* object=*reinterpret_cast<uint8_t**>(node+0x30);
            if(object==layout)++matches;
            node=*reinterpret_cast<uintptr_t*>(node);
        }
        if(node!=head || matches!=1){reason=6;return false;}
        auto* l=reinterpret_cast<uint8_t*>(layout);
        auto* b=reinterpret_cast<uint8_t*>(button);
        const uintptr_t buttonVft=*reinterpret_cast<uintptr_t*>(b);
        if(*reinterpret_cast<uintptr_t*>(l)!=base+0x1230558
           || *reinterpret_cast<void**>(l+0xe0)!=button
           || buttonVft<base || buttonVft>=base+OwnForwardLayout::ImageSize
           || *reinterpret_cast<uintptr_t*>(b+0x4f0)!=base+0x1230760
           || *reinterpret_cast<void**>(b+0x4f8)!=layout){reason=7;return false;}
        reason=0;return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){reason=8;return false;}
}

static bool AutoOkInvoke(void* button) noexcept {
    __try {
        void* pair[2]={button,nullptr};
        using OriginalOk=void(__fastcall*)(void*,void*);
        reinterpret_cast<OriginalOk>(scope.base+0xad9ca0)(reinterpret_cast<uint8_t*>(button)+0x4f0,pair);
        return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}

static bool AutoCreateValidated(void* layout,void* button,unsigned& reason) noexcept {
    reason=1;
    const uintptr_t base=scope.base;
    if(!base || !scope.selectedReady.load() || !autoOkClaimed.load()
       || !AutoOkCanonical(reinterpret_cast<uintptr_t>(layout))
       || !AutoOkCanonical(reinterpret_cast<uintptr_t>(button)))return false;
    forward_diagnostic::Context context{};
    if(!forward_diagnostic::context(context)){reason=2;return false;}
    __try {
        auto* root=*reinterpret_cast<uint8_t**>(base+0x1668790);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) || !root[0xd8]){reason=3;return false;}
        auto* gi=*reinterpret_cast<uint8_t**>(root+0xd0);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(gi))){reason=3;return false;}
        const uintptr_t begin=*reinterpret_cast<uintptr_t*>(gi+0x180);
        const uintptr_t end=*reinterpret_cast<uintptr_t*>(gi+0x188);
        if(!AutoOkCanonical(begin) || end<begin || (end-begin)%16 || (end-begin)/16>128){reason=3;return false;}
        uint8_t *ui=nullptr,*gameState=nullptr;
        for(uintptr_t at=begin;at<end;at+=16) {
            auto* object=*reinterpret_cast<uint8_t**>(at);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(object)))continue;
            const uintptr_t vft=*reinterpret_cast<uintptr_t*>(object);
            if(vft==base+0x1182c50){if(ui){reason=4;return false;}ui=object;}
            if(vft==base+0x1182e30){if(gameState){reason=4;return false;}gameState=object;}
        }
        if(!ui || !gameState){reason=4;return false;}
        auto* scene=*reinterpret_cast<uint8_t**>(gameState+0x360);
        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(scene))
           || *reinterpret_cast<uintptr_t*>(scene)!=base+0x1187778
           || *reinterpret_cast<uint32_t*>(scene+0x10)!=4
           || *reinterpret_cast<uint32_t*>(gameState+0x380)!=4){reason=5;return false;}
        const uintptr_t head=*reinterpret_cast<uintptr_t*>(ui+0x350);
        const uintptr_t count=*reinterpret_cast<uintptr_t*>(ui+0x358);
        if(!AutoOkCanonical(head) || !count || count>64){reason=6;return false;}
        uintptr_t node=*reinterpret_cast<uintptr_t*>(head);unsigned matches=0;
        for(uintptr_t index=0;index<count;++index) {
            if(!AutoOkCanonical(node) || node==head){reason=6;return false;}
            if(*reinterpret_cast<void**>(node+0x30)==layout)++matches;
            node=*reinterpret_cast<uintptr_t*>(node);
        }
        if(node!=head || matches!=1){reason=6;return false;}
        auto* l=reinterpret_cast<uint8_t*>(layout);
        auto* b=reinterpret_cast<uint8_t*>(button);
        const uintptr_t buttonVft=*reinterpret_cast<uintptr_t*>(b);
        auto* bundle=*reinterpret_cast<uint8_t**>(b+0x4f8);
        if(*reinterpret_cast<uintptr_t*>(l)!=base+0x1214f58
           || *reinterpret_cast<void**>(l+0xc0)!=button
           || l[0xb8]!=0
           || buttonVft<base || buttonVft>=base+OwnForwardLayout::ImageSize
           || *reinterpret_cast<uintptr_t*>(b+0x4f0)!=base+0x1217508
           || !AutoOkCanonical(reinterpret_cast<uintptr_t>(bundle))
           || *reinterpret_cast<void**>(bundle+0x88)!=button
           || *reinterpret_cast<uintptr_t*>(bundle+8)!=base+0x1214eb0
           || *reinterpret_cast<uintptr_t*>(bundle+0x48)!=base+0x1214e78
           || *reinterpret_cast<void**>(bundle+0x10)!=layout
           || *reinterpret_cast<int32_t*>(bundle+0x18)!=0){reason=7;return false;}
        reason=0;return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){reason=8;return false;}
}

static bool AutoCreateInvoke(void* button) noexcept {
    __try {
        auto* bundle=*reinterpret_cast<uint8_t**>(reinterpret_cast<uint8_t*>(button)+0x4f8);
        void* node=button;
        using OriginalSlot=void(__fastcall*)(void*,void**);
        reinterpret_cast<OriginalSlot>(scope.base+0x93a290)(bundle+8,&node);
        return true;
    } __except(EXCEPTION_EXECUTE_HANDLER){return false;}
}

struct AutoSmallPath {char text[16];size_t length;size_t capacity;};
static_assert(sizeof(AutoSmallPath)==32,"MSVC small-string layout required");

// The original 8F1B10 path lookup consumes one intrusive Node reference and
// returns one to the caller. Match the caller at 9349A3..934A38.
static void AutoReleaseUiNode(void* node) noexcept {
    if(!node)return;
    __try {
        auto* count=reinterpret_cast<volatile LONG*>(reinterpret_cast<uint8_t*>(node)+8);
        if(InterlockedDecrement(count)==0) {
            using Destroy=void(__fastcall*)(void*,int);
            auto* vft=*reinterpret_cast<void***>(node);
            reinterpret_cast<Destroy>(vft[0])(node,1);
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {}
}

static bool AutoSelectOkInvoke(void* layout,unsigned& reason) noexcept {
    reason=1;
    if(!autoCreateSucceeded.load() || !AutoOkCanonical(reinterpret_cast<uintptr_t>(layout)))return false;
    auto* l=reinterpret_cast<uint8_t*>(layout);
    void* input=nullptr;void* button=nullptr;bool invoked=false;
    __try {
        auto* first=*reinterpret_cast<uint8_t**>(l+0xc0);
        if(!AutoCreateValidated(layout,first,reason)){
            // The current CharacterSelect scene and first slot must still be bound.
        } else if(*reinterpret_cast<int32_t*>(l+0x180)!=0){reason=7;
        } else {
            auto* root=*reinterpret_cast<uint8_t**>(l+0x30);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) ||
               *reinterpret_cast<uintptr_t*>(root)<scope.base ||
               *reinterpret_cast<uintptr_t*>(root)>=scope.base+OwnForwardLayout::ImageSize){reason=7;
            } else {
                AutoSmallPath path{};
                memcpy(path.text,"Root.Bt_Ok",11);path.length=10;path.capacity=15;
                input=root;
                InterlockedIncrement(reinterpret_cast<volatile LONG*>(root+8));
                using FindNode=void*(__fastcall*)(void**,void**,const AutoSmallPath*);
                reinterpret_cast<FindNode>(scope.base+0x8f1b10)(&button,&input,&path);
                auto* b=reinterpret_cast<uint8_t*>(button);
                if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(button)) ||
                   *reinterpret_cast<uintptr_t*>(b)<scope.base ||
                   *reinterpret_cast<uintptr_t*>(b)>=scope.base+OwnForwardLayout::ImageSize ||
                   *reinterpret_cast<uintptr_t*>(b+0x4f0)!=scope.base+0x1214ee8 ||
                   *reinterpret_cast<void**>(b+0x4f8)!=layout){reason=8;
                } else {
                    void* pair[2]={button,nullptr};
                    using OriginalSelectOk=void(__fastcall*)(void*,void*);
                    reinterpret_cast<OriginalSelectOk>(scope.base+0x9398f0)(b+0x4f0,pair);
                    invoked=true;reason=0;
                }
            }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){reason=9;}
    AutoReleaseUiNode(button);
    if(reason!=9)AutoReleaseUiNode(input);
    return invoked;
}

static bool AutoCreateSubmitInvoke(void* layout,unsigned& reason) noexcept {
    reason=1;
    if(!autoSelectOkSucceeded.load() || !AutoOkCanonical(reinterpret_cast<uintptr_t>(layout)))return false;
    void* input=nullptr;void* button=nullptr;bool invoked=false;
    __try {
        const uintptr_t base=scope.base;
        auto* root=*reinterpret_cast<uint8_t**>(base+0x1668790);
        if(!base || !scope.selectedReady.load() ||
           !AutoOkCanonical(reinterpret_cast<uintptr_t>(root)) || !root[0xd8]){reason=2;
        } else {
            auto* gi=*reinterpret_cast<uint8_t**>(root+0xd0);
            auto* l=reinterpret_cast<uint8_t*>(layout);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(gi)) ||
               *reinterpret_cast<uintptr_t*>(l)!=base+0x1214c70){reason=3;
            } else {
                uint8_t* ui=nullptr;uint8_t* state=nullptr;
                const uintptr_t begin=*reinterpret_cast<uintptr_t*>(gi+0x180);
                const uintptr_t end=*reinterpret_cast<uintptr_t*>(gi+0x188);
                if(!AutoOkCanonical(begin) || end<begin || (end-begin)%16 || (end-begin)/16>128){reason=3;
                } else {
                    for(uintptr_t at=begin;at<end;at+=16) {
                        auto* object=*reinterpret_cast<uint8_t**>(at);
                        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(object)))continue;
                        const uintptr_t vft=*reinterpret_cast<uintptr_t*>(object);
                        if(vft==base+0x1182c50){if(ui){reason=4;break;}ui=object;}
                        if(vft==base+0x1182e30){if(state){reason=4;break;}state=object;}
                    }
                    if(reason!=4 && (!ui || !state)){reason=4;}
                    if(reason!=4) {
                        auto* scene=*reinterpret_cast<uint8_t**>(state+0x360);
                        if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(scene)) ||
                           *reinterpret_cast<uintptr_t*>(scene)!=base+0x1187778 ||
                           *reinterpret_cast<uint32_t*>(scene+0x10)!=4 ||
                           *reinterpret_cast<uint32_t*>(state+0x380)!=4){reason=5;
                        } else {
                            const uintptr_t head=*reinterpret_cast<uintptr_t*>(ui+0x350);
                            const uintptr_t count=*reinterpret_cast<uintptr_t*>(ui+0x358);
                            if(!AutoOkCanonical(head) || !count || count>64){reason=6;
                            } else {
                                uintptr_t node=*reinterpret_cast<uintptr_t*>(head);unsigned matches=0;
                                for(uintptr_t index=0;index<count;++index) {
                                    if(!AutoOkCanonical(node) || node==head){reason=6;break;}
                                    if(*reinterpret_cast<void**>(node+0x30)==layout)++matches;
                                    node=*reinterpret_cast<uintptr_t*>(node);
                                }
                                if(reason!=6 && (node!=head || matches!=1))reason=6;
                                if(reason!=6)reason=0;
                            }
                        }
                    }
                }
            }
        }
        if(reason==0) {
            auto* l=reinterpret_cast<uint8_t*>(layout);
            auto* field=*reinterpret_cast<uint8_t**>(l+0xd0);
            auto* rootNode=*reinterpret_cast<uint8_t**>(l+0x30);
            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(field)) ||
               !AutoOkCanonical(reinterpret_cast<uintptr_t>(rootNode)) ||
               *reinterpret_cast<uintptr_t*>(field)<base ||
               *reinterpret_cast<uintptr_t*>(field)>=base+OwnForwardLayout::ImageSize){reason=7;
            } else {
                auto* inner=*reinterpret_cast<uint8_t**>(field+0x700);
                if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(inner))){reason=7;
                } else {
                    auto* property=inner+0x340;
                    const uintptr_t vft=*reinterpret_cast<uintptr_t*>(property);
                    if(vft<base || vft>=base+OwnForwardLayout::ImageSize){reason=7;
                    } else {
                        const uintptr_t setter=*reinterpret_cast<uintptr_t*>(vft+8);
                        const uintptr_t getter=*reinterpret_cast<uintptr_t*>(vft+0x10);
                        if(setter<base || setter>=base+OwnForwardLayout::ImageSize ||
                           getter<base || getter>=base+OwnForwardLayout::ImageSize){reason=7;
                        } else {
                            AutoSmallPath name{};
                            memcpy(name.text,"SoloKnight",11);name.length=10;name.capacity=15;
                            using SetName=void(__fastcall*)(void*,const AutoSmallPath*);
                            using GetName=const AutoSmallPath*(__fastcall*)(void*);
                            reinterpret_cast<SetName>(setter)(property,&name);
                            const auto* got=reinterpret_cast<GetName>(getter)(property);
                            if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(got)) ||
                               got->length!=10 || got->capacity<10 || got->capacity>4096){reason=8;
                            } else {
                                const char* actual=got->capacity>15 ?
                                   *reinterpret_cast<char* const*>(got->text) : got->text;
                                if(!actual || memcmp(actual,"SoloKnight",10)!=0){reason=8;
                                } else {
                                    AutoSmallPath path{};
                                    memcpy(path.text,"Root.Bt_Ok",11);path.length=10;path.capacity=15;
                                    input=rootNode;
                                    InterlockedIncrement(reinterpret_cast<volatile LONG*>(rootNode+8));
                                    using FindNode=void*(__fastcall*)(void**,void**,const AutoSmallPath*);
                                    reinterpret_cast<FindNode>(base+0x8f1b10)(&button,&input,&path);
                                    auto* b=reinterpret_cast<uint8_t*>(button);
                                    if(!AutoOkCanonical(reinterpret_cast<uintptr_t>(button)) ||
                                       *reinterpret_cast<uintptr_t*>(b)<base ||
                                       *reinterpret_cast<uintptr_t*>(b)>=base+OwnForwardLayout::ImageSize ||
                                       *reinterpret_cast<uintptr_t*>(b+0x4f0)!=base+0x1214c00 ||
                                       *reinterpret_cast<void**>(b+0x4f8)!=layout){reason=8;
                                    } else {
                                        void* pair[2]={button,nullptr};
                                        using OriginalCreate=void(__fastcall*)(void*,void*);
                                        reinterpret_cast<OriginalCreate>(base+0x9327c0)(b+0x4f0,pair);
                                        invoked=true;reason=0;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){reason=9;}
    AutoReleaseUiNode(button);
    if(reason!=9)AutoReleaseUiNode(input);
    return invoked;
}

#include "manual_move.hpp"
#include "attack_target.hpp"
#include "source_quit.hpp"
#include "use_item.hpp"
#include "source_restart.hpp"
#include "source_reselect.hpp"

static LRESULT CALLBACK AutoOkGetMessage(int code,WPARAM remove,LPARAM raw) {
    HHOOK hook=autoOkHook.load();
    if(manual_move::Handle(code,remove,raw)){
        return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
    }
    if(attack_target::Handle(code,remove,raw)){
        return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
    }
    if(source_quit::Handle(code,remove,raw)){
        return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
    }
    if(use_item::Handle(code,remove,raw)){
        return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
    }
    if(source_restart::Handle(code,remove,raw)){
        return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
    }
    if(source_reselect::Handle(code,remove,raw)){
        return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
    }
    manual_move::ObserveEnd(code,remove,reinterpret_cast<const MSG*>(raw),autoOkWindow.load());
    if(code>=0 && remove==PM_REMOVE && raw) {
        auto* message=reinterpret_cast<MSG*>(raw);
        if(message->hwnd==autoOkWindow.load() && message->message==autoOkMessage.load()) {
            message->message=WM_NULL;
            if(!autoOkClaimed.exchange(true)) {
                unsigned reason=0;
                const bool valid=AutoOkValidated(reinterpret_cast<void*>(message->wParam),
                                                 reinterpret_cast<void*>(message->lParam),reason);
                const bool invoked=valid && AutoOkInvoke(reinterpret_cast<void*>(message->lParam));
                AutoOkDiagnostic(L"auto-ok-invoke.json",invoked?"ORIGINAL_OK_RETURNED":"ORIGINAL_OK_REFUSED",
                                 invoked,0,valid?(invoked?0:9):reason);
            }
        } else if(message->hwnd==autoOkWindow.load() && autoCreateMessage.load()!=0
                  && message->message==autoCreateMessage.load()) {
            message->message=WM_NULL;
            if(!autoCreateClaimed.exchange(true)) {
                unsigned reason=0;
                const bool valid=AutoCreateValidated(reinterpret_cast<void*>(message->wParam),
                                                     reinterpret_cast<void*>(message->lParam),reason);
                const bool invoked=valid && AutoCreateInvoke(reinterpret_cast<void*>(message->lParam));
                autoCreateSucceeded.store(invoked);
                AutoOkDiagnostic(L"auto-create-invoke.json",invoked?"ORIGINAL_SLOT_SELECTED":"ORIGINAL_SLOT_REFUSED",
                                 invoked,0,valid?(invoked?0:9):reason);
                if(!invoked && hook)manual_move::terminal.store(true);
            }
        } else if(message->hwnd==autoOkWindow.load() && autoSelectOkMessage.load()!=0
                  && message->message==autoSelectOkMessage.load()) {
            message->message=WM_NULL;
            if(!autoSelectOkClaimed.exchange(true)) {
                unsigned reason=0;
                const bool invoked=AutoSelectOkInvoke(reinterpret_cast<void*>(message->wParam),reason);
                autoSelectOkSucceeded.store(invoked);
                AutoOkDiagnostic(L"auto-select-ok-invoke.json",invoked?"ORIGINAL_SELECT_OK_RETURNED":"ORIGINAL_SELECT_OK_REFUSED",
                                 invoked,0,reason);
                if(!invoked && hook)manual_move::terminal.store(true);
            }
        } else if(message->hwnd==autoOkWindow.load() && autoCreateSubmitMessage.load()!=0
                  && message->message==autoCreateSubmitMessage.load()) {
            message->message=WM_NULL;
            if(!autoCreateSubmitClaimed.exchange(true)) {
                unsigned reason=0;
                const bool invoked=AutoCreateSubmitInvoke(reinterpret_cast<void*>(message->wParam),reason);
                AutoOkDiagnostic(L"auto-create-submit.json",invoked?"ORIGINAL_CREATE_RETURNED":"ORIGINAL_CREATE_REFUSED",
                                 invoked,0,reason);
                if(hook)manual_move::terminal.store(true);
            }
        }
    }
    return manual_move::Forward(hook,code,remove,raw,UnhookWindowsHookEx,CallNextHookEx);
}

static void InstallAutoOkHook() noexcept {
    if(autoOkInstallAttempted.exchange(true))return;
    AutoOkWindow choice{};EnumWindows(FindAutoOkWindow,reinterpret_cast<LPARAM>(&choice));
    if(!choice.hwnd){AutoOkDiagnostic(L"auto-ok-install.json","HOOK_NOT_INSTALLED",false,GetLastError(),1);return;}
    const UINT message=RegisterWindowMessageW(L"LC-Owned-Auto-OK-CP34");
    if(message<0xc000){AutoOkDiagnostic(L"auto-ok-install.json","HOOK_NOT_INSTALLED",false,GetLastError(),2);return;}
    const UINT createMessage=RegisterWindowMessageW(L"LC-Owned-Select-Empty-CP44");
    const UINT selectOkMessage=RegisterWindowMessageW(L"LC-Owned-Character-OK-CP46");
    const UINT createSubmitMessage=RegisterWindowMessageW(L"LC-Owned-Create-Submit-CP47");
    manual_move::uiThread.store(choice.thread);
    manual_move::BindOwner();
    autoOkWindow.store(choice.hwnd);autoOkMessage.store(message);
    if(createMessage>=0xc000)autoCreateMessage.store(createMessage);
    if(selectOkMessage>=0xc000)autoSelectOkMessage.store(selectOkMessage);
    if(createSubmitMessage>=0xc000)autoCreateSubmitMessage.store(createSubmitMessage);
    HHOOK hook=SetWindowsHookExW(WH_GETMESSAGE,AutoOkGetMessage,nullptr,choice.thread);
    const DWORD error=GetLastError();autoOkHook.store(hook);
    AutoOkDiagnostic(L"auto-ok-install.json",hook?"HOOK_INSTALLED":"HOOK_NOT_INSTALLED",hook!=nullptr,error,hook?0:3);
}
