#pragma once
// Process-local known Win32 protection; official Detours v4.0.1 only.
// DllMain: loaded-module lookup + one transaction, no User32 invocation,
// LoadLibrary, new threads or original-game body modification. Desktop queries
// happen only in wrappers / command dispatch outside loader callbacks.
// https://github.com/microsoft/Detours/wiki/Using-Detours
#include <windows.h>
#include <detours.h>
#include <type_traits>

namespace owned_background_guard {
enum class Admission : LONG { NotChecked=0, Installed=10, BadEnvironment=11,
    MissingExport=12, DuplicateTarget=13, PinFailed=14, TransactionFailed=15,
    ProtectionMismatch=16, InvalidRegion=17 };
static volatile LONG admission=0, last_error=0;
// Diagnostics only: these are populated by the existing attach checks. No
// additional target inspection, address output or policy decision is added.
enum class Stage : LONG { None=0, Environment=1, Module=2, Export=3,
    Resolve=4, Region=5, Alias=6, Pin=7, Begin=8, UpdateThread=9,
    AttachEntry=10, DetachEntry=11, Abort=12, Commit=13, Protection=14, Ready=15 };
static volatile LONG failed_stage=0, failed_entry_index=-1, alias_peer_index=-1, region_index=-1;
static volatile LONG query_available=0;
static volatile DWORD query_state=0, query_protect=0, query_type=0;
static volatile LONG64 calls[18]{};
static volatile LONG64 blocked_display=0;
static bool installed=false;
static HMODULE pinned_self=nullptr;
inline bool same_text(const char* a,const char* b) noexcept {
    if (!a || !b) return false;
    for (unsigned i=0;i<128;++i) { if(a[i]!=b[i]) return false; if(!a[i]) return true; }
    return false;
}
inline bool expected_desktop(wchar_t (&name)[96]) noexcept {
    wchar_t mode[4]{};
    if(GetEnvironmentVariableW(L"OWN_INTERNAL_COMMAND_MODE",mode,4)!=1 || mode[0]!=L'1') return false;
    constexpr wchar_t prefix[]=L"LC-Owned-Internal-";
    constexpr DWORD prefix_size=static_cast<DWORD>(sizeof(prefix)/sizeof(wchar_t)-1);
    constexpr DWORD size=prefix_size+32;
    if(GetEnvironmentVariableW(L"OWN_INTERNAL_COMMAND_DESKTOP",name,96)!=size) return false;
    for(DWORD i=0;i<prefix_size;++i) if(name[i]!=prefix[i]) return false;
    for(DWORD i=prefix_size;i<size;++i)
        if(!((name[i]>=L'0'&&name[i]<=L'9')||(name[i]>=L'a'&&name[i]<=L'f'))) return false;
    return name[size]==0;
}
inline bool desktop_name(HDESK desktop,const wchar_t (&expected)[96]) noexcept {
    wchar_t actual[96]{}; DWORD needed=0;
    if(!desktop || !GetUserObjectInformationW(desktop,UOI_NAME,actual,sizeof(actual),&needed)
       || !needed || needed>sizeof(actual)) return false;
    for(unsigned i=0;i<96;++i) {
        if(actual[i]!=expected[i]) return false;
        if(!actual[i]) return true;
    }
    return false;
}
inline bool current_desktop() noexcept {
    wchar_t expected[96]{};
    return expected_desktop(expected) && desktop_name(GetThreadDesktop(GetCurrentThreadId()),expected);
}
#ifdef OWN_BACKGROUND_GUARD_MOCK
static bool (*mock_desktop)() noexcept=nullptr;
static bool (*mock_window)(HWND) noexcept=nullptr;
#endif
inline bool permitted_desktop() noexcept {
#ifdef OWN_BACKGROUND_GUARD_MOCK
    if(mock_desktop) return mock_desktop();
#endif
    return current_desktop();
}
inline bool private_window(HWND window) noexcept {
#ifdef OWN_BACKGROUND_GUARD_MOCK
    if(mock_window) return mock_window(window);
#endif
    DWORD pid=0; const DWORD tid=GetWindowThreadProcessId(window,&pid);
    wchar_t expected[96]{};
    return tid && pid==GetCurrentProcessId() && expected_desktop(expected)
        && desktop_name(GetThreadDesktop(tid),expected);
}
inline void hit(unsigned index) noexcept { InterlockedIncrement64(&calls[index]); }
inline BOOL denied() noexcept { SetLastError(ERROR_ACCESS_DENIED); return FALSE; }
#define OWN_GUARD_REAL(name) static decltype(&::name) real_##name=nullptr
OWN_GUARD_REAL(ChangeDisplaySettingsA); OWN_GUARD_REAL(ChangeDisplaySettingsW);
OWN_GUARD_REAL(ChangeDisplaySettingsExA); OWN_GUARD_REAL(ChangeDisplaySettingsExW);
OWN_GUARD_REAL(SetCursorPos); OWN_GUARD_REAL(SetPhysicalCursorPos); OWN_GUARD_REAL(ClipCursor);
OWN_GUARD_REAL(SetForegroundWindow); OWN_GUARD_REAL(SetActiveWindow); OWN_GUARD_REAL(SetFocus);
OWN_GUARD_REAL(BringWindowToTop); OWN_GUARD_REAL(SwitchDesktop);
OWN_GUARD_REAL(CreateWindowExA); OWN_GUARD_REAL(CreateWindowExW); OWN_GUARD_REAL(ShowWindow);
OWN_GUARD_REAL(SendInput); OWN_GUARD_REAL(mouse_event); OWN_GUARD_REAL(keybd_event);
#undef OWN_GUARD_REAL
inline LONG WINAPI change_a(DEVMODEA* mode,DWORD flags) {
    hit(0); if(mode && flags==CDS_TEST && real_ChangeDisplaySettingsA) return real_ChangeDisplaySettingsA(mode,flags);
    InterlockedIncrement64(&blocked_display); denied(); return DISP_CHANGE_FAILED;
}
inline LONG WINAPI change_w(DEVMODEW* mode,DWORD flags) {
    hit(1); if(mode && flags==CDS_TEST && real_ChangeDisplaySettingsW) return real_ChangeDisplaySettingsW(mode,flags);
    InterlockedIncrement64(&blocked_display); denied(); return DISP_CHANGE_FAILED;
}
inline LONG WINAPI change_ex_a(LPCSTR device,DEVMODEA* mode,HWND window,DWORD flags,LPVOID reserved) {
    hit(2); if(mode && !window && !reserved && flags==CDS_TEST && real_ChangeDisplaySettingsExA)
        return real_ChangeDisplaySettingsExA(device,mode,window,flags,reserved);
    InterlockedIncrement64(&blocked_display); denied(); return DISP_CHANGE_FAILED;
}
inline LONG WINAPI change_ex_w(LPCWSTR device,DEVMODEW* mode,HWND window,DWORD flags,LPVOID reserved) {
    hit(3); if(mode && !window && !reserved && flags==CDS_TEST && real_ChangeDisplaySettingsExW)
        return real_ChangeDisplaySettingsExW(device,mode,window,flags,reserved);
    InterlockedIncrement64(&blocked_display); denied(); return DISP_CHANGE_FAILED;
}
inline BOOL WINAPI cursor(int,int) { hit(4); return denied(); }
inline BOOL WINAPI physical_cursor(int,int) { hit(5); return denied(); }
inline BOOL WINAPI clip(const RECT*) { hit(6); return denied(); }
inline BOOL WINAPI foreground(HWND) { hit(7); return denied(); }
inline HWND WINAPI active(HWND) { hit(8); denied(); return nullptr; }
inline HWND WINAPI focus(HWND) { hit(9); denied(); return nullptr; }
inline BOOL WINAPI bring(HWND) { hit(10); return denied(); }
inline BOOL WINAPI switch_desktop(HDESK) { hit(11); return denied(); }
inline HWND WINAPI create_a(DWORD ex,LPCSTR klass,LPCSTR name,DWORD style,int x,int y,int w,int h,
                           HWND parent,HMENU menu,HINSTANCE instance,LPVOID param) {
    hit(12); if(!permitted_desktop() || !real_CreateWindowExA) { denied(); return nullptr; }
    return real_CreateWindowExA(ex,klass,name,style,x,y,w,h,parent,menu,instance,param);
}
inline HWND WINAPI create_w(DWORD ex,LPCWSTR klass,LPCWSTR name,DWORD style,int x,int y,int w,int h,
                           HWND parent,HMENU menu,HINSTANCE instance,LPVOID param) {
    hit(13); if(!permitted_desktop() || !real_CreateWindowExW) { denied(); return nullptr; }
    return real_CreateWindowExW(ex,klass,name,style,x,y,w,h,parent,menu,instance,param);
}
inline BOOL WINAPI show(HWND window,int command) {
    hit(14); if(!permitted_desktop() || !private_window(window) || !real_ShowWindow) return denied();
    // Never activate even an owned private window. Preserve normal visibility.
    return real_ShowWindow(window,command==SW_HIDE ? SW_HIDE : SW_SHOWNOACTIVATE);
}
inline UINT WINAPI send_input(UINT,LPINPUT,int) { hit(15); denied(); return 0; }
inline void WINAPI mouse(DWORD,DWORD,DWORD,DWORD,ULONG_PTR) { hit(16); denied(); }
inline void WINAPI key(BYTE,BYTE,DWORD,ULONG_PTR) { hit(17); denied(); }
#define OWN_GUARD_ABI(wrapper,name) static_assert(std::is_same<decltype(&wrapper),decltype(&::name)>::value,"Win32 ABI " #name)
OWN_GUARD_ABI(change_a,ChangeDisplaySettingsA); OWN_GUARD_ABI(change_w,ChangeDisplaySettingsW);
OWN_GUARD_ABI(change_ex_a,ChangeDisplaySettingsExA); OWN_GUARD_ABI(change_ex_w,ChangeDisplaySettingsExW);
OWN_GUARD_ABI(cursor,SetCursorPos); OWN_GUARD_ABI(physical_cursor,SetPhysicalCursorPos);
OWN_GUARD_ABI(clip,ClipCursor); OWN_GUARD_ABI(foreground,SetForegroundWindow);
OWN_GUARD_ABI(active,SetActiveWindow); OWN_GUARD_ABI(focus,SetFocus); OWN_GUARD_ABI(bring,BringWindowToTop);
OWN_GUARD_ABI(switch_desktop,SwitchDesktop); OWN_GUARD_ABI(create_a,CreateWindowExA);
OWN_GUARD_ABI(create_w,CreateWindowExW); OWN_GUARD_ABI(show,ShowWindow);
OWN_GUARD_ABI(send_input,SendInput); OWN_GUARD_ABI(mouse,mouse_event); OWN_GUARD_ABI(key,keybd_event);
#undef OWN_GUARD_ABI
struct Region { PVOID address; PVOID allocation; DWORD protection; };
struct Entry { const char* name; PVOID* original; PVOID wrapper; PVOID target; PVOID code; Region regions[4]; };
#define OWN_GUARD_ENTRY(name,wrapper) {#name,reinterpret_cast<PVOID*>(&real_##name),reinterpret_cast<PVOID>(&wrapper),nullptr,nullptr,{}}
static Entry entries[]={
    OWN_GUARD_ENTRY(ChangeDisplaySettingsA,change_a), OWN_GUARD_ENTRY(ChangeDisplaySettingsW,change_w),
    OWN_GUARD_ENTRY(ChangeDisplaySettingsExA,change_ex_a), OWN_GUARD_ENTRY(ChangeDisplaySettingsExW,change_ex_w),
    OWN_GUARD_ENTRY(SetCursorPos,cursor), OWN_GUARD_ENTRY(SetPhysicalCursorPos,physical_cursor),
    OWN_GUARD_ENTRY(ClipCursor,clip), OWN_GUARD_ENTRY(SetForegroundWindow,foreground),
    OWN_GUARD_ENTRY(SetActiveWindow,active), OWN_GUARD_ENTRY(SetFocus,focus), OWN_GUARD_ENTRY(BringWindowToTop,bring),
    OWN_GUARD_ENTRY(SwitchDesktop,switch_desktop), OWN_GUARD_ENTRY(CreateWindowExA,create_a),
    OWN_GUARD_ENTRY(CreateWindowExW,create_w), OWN_GUARD_ENTRY(ShowWindow,show),
    OWN_GUARD_ENTRY(SendInput,send_input), OWN_GUARD_ENTRY(mouse_event,mouse), OWN_GUARD_ENTRY(keybd_event,key)};
#undef OWN_GUARD_ENTRY
constexpr unsigned count=static_cast<unsigned>(sizeof(entries)/sizeof(entries[0]));
static_assert(count==18,"counter inventory");
static_assert(std::is_same<decltype(real_SetCursorPos),decltype(real_SetPhysicalCursorPos)>::value,
              "coalesced deny pair must have identical documented ABI");
static Entry physical_entries[count]{};
static unsigned physical_count=0;
static bool cursor_pair_coalesced=false;
struct TransactionApi {
    decltype(&DetourTransactionBegin) begin;
    decltype(&DetourUpdateThread) update;
    decltype(&DetourAttach) attach;
    decltype(&DetourDetach) detach;
    decltype(&DetourTransactionCommit) commit;
    decltype(&DetourTransactionAbort) abort;
};
inline LONG transact(const TransactionApi& api,Entry* list,unsigned size,bool remove) noexcept {
    failed_stage=static_cast<LONG>(Stage::Begin); failed_entry_index=-1;
    LONG result=api.begin(); if(result!=NO_ERROR) return result;
    failed_stage=static_cast<LONG>(Stage::UpdateThread);
    result=api.update(GetCurrentThread());
    for(unsigned i=0;result==NO_ERROR && i<size;++i) {
        failed_stage=static_cast<LONG>(remove ? Stage::DetachEntry : Stage::AttachEntry);
        failed_entry_index=static_cast<LONG>(i);
        // The selected transaction list may omit the physical-cursor alias;
        // diagnostics still identify the original public-export inventory.
        for(unsigned j=0;j<count;++j) if(list[i].original==entries[j].original) {
            failed_entry_index=static_cast<LONG>(j); break;
        }
        result=remove ? api.detach(list[i].original,list[i].wrapper) : api.attach(list[i].original,list[i].wrapper);
    }
    if(result!=NO_ERROR) {
        const LONG rollback=api.abort();
        if(rollback!=NO_ERROR) failed_stage=static_cast<LONG>(Stage::Abort);
        return rollback==NO_ERROR ? result : rollback;
    }
    // Official CommitEx aborts all pending operations if any pending error exists.
    failed_stage=static_cast<LONG>(Stage::Commit); failed_entry_index=-1;
    return api.commit();
}
inline bool distinct_targets(const Entry* list,unsigned size) noexcept {
    for(unsigned i=0;i<size;++i) for(unsigned j=0;j<i;++j)
        if(list[i].target==list[j].target || list[i].code==list[j].code
           || list[i].target==list[j].code || list[i].code==list[j].target) {
            failed_entry_index=static_cast<LONG>(i); alias_peer_index=static_cast<LONG>(j); return false;
        }
    return true;
}
inline bool select_physical_entries(const Entry* list,unsigned size,Entry* selected,
                                    unsigned& selected_count,bool& coalesced) noexcept {
    selected_count=0; coalesced=false;
    if(size!=count) return false;
    for(unsigned i=0;i<size;++i) {
        bool omit=false;
        for(unsigned j=0;j<i;++j) {
            const bool overlaps=list[i].target==list[j].target || list[i].code==list[j].code
                || list[i].target==list[j].code || list[i].code==list[j].target;
            if(!overlaps) continue;
            // The actual host proved this one resolved-code alias. Both
            // wrappers unconditionally deny the same BOOL(int,int) ABI and
            // never call either original. Every other overlap still fails.
            const bool known_pair=j==4 && i==5 && list[i].code==list[j].code
                && same_text(list[j].name,"SetCursorPos") && same_text(list[i].name,"SetPhysicalCursorPos")
                && list[j].wrapper==reinterpret_cast<PVOID>(&cursor)
                && list[i].wrapper==reinterpret_cast<PVOID>(&physical_cursor)
                && list[j].original==reinterpret_cast<PVOID*>(&real_SetCursorPos)
                && list[i].original==reinterpret_cast<PVOID*>(&real_SetPhysicalCursorPos);
            if(!known_pair) {
                failed_entry_index=static_cast<LONG>(i); alias_peer_index=static_cast<LONG>(j); return false;
            }
            omit=true; coalesced=true;
        }
        if(!omit) selected[selected_count++]=list[i];
    }
    return selected_count==count-(coalesced ? 1u : 0u);
}
inline bool capture_region(PVOID address,Region& region) noexcept {
    MEMORY_BASIC_INFORMATION info{};
    const SIZE_T queried=VirtualQuery(address,&info,sizeof(info));
    query_available=queried==sizeof(info) ? 1 : 0;
    query_state=info.State; query_protect=info.Protect; query_type=info.Type;
    if(queried!=sizeof(info) || info.State!=MEM_COMMIT
       || info.Type!=MEM_IMAGE || (info.Protect&PAGE_GUARD)) return false;
    const DWORD p=info.Protect&0xff;
    if(p!=PAGE_EXECUTE && p!=PAGE_EXECUTE_READ && p!=PAGE_EXECUTE_READWRITE && p!=PAGE_EXECUTE_WRITECOPY) return false;
    region={address,info.AllocationBase,info.Protect}; return true;
}
inline bool protections_restored() noexcept {
    for(unsigned i=0;i<count;++i) for(unsigned j=0;j<4;++j) {
        failed_entry_index=static_cast<LONG>(i); region_index=static_cast<LONG>(j);
        const auto& before=entries[i].regions[j];
        Region after{}; if(!capture_region(before.address,after) || after.allocation!=before.allocation
            || after.protection!=before.protection) return false;
    }
    return true;
}
inline bool fail(Admission status,LONG error) noexcept {
    InterlockedExchange(&last_error,error); InterlockedExchange(&admission,static_cast<LONG>(status)); return false;
}
inline bool attach() noexcept {
    if(installed) return true;
    failed_stage=static_cast<LONG>(Stage::Environment);
    wchar_t expected[96]{};
    if(!expected_desktop(expected)) return fail(Admission::BadEnvironment,ERROR_INVALID_ENVIRONMENT);
    failed_stage=static_cast<LONG>(Stage::Module);
    const HMODULE user=GetModuleHandleW(L"user32.dll");
    if(!user) return fail(Admission::MissingExport,ERROR_MOD_NOT_FOUND);
    for(unsigned index=0;index<count;++index) {
        auto& entry=entries[index]; failed_entry_index=static_cast<LONG>(index);
        failed_stage=static_cast<LONG>(Stage::Export);
        entry.target=reinterpret_cast<PVOID>(GetProcAddress(user,entry.name));
        if(!entry.target) return fail(Admission::MissingExport,ERROR_PROC_NOT_FOUND);
        // Only official Detours resolves public-export indirections; no custom decoder.
        failed_stage=static_cast<LONG>(Stage::Resolve);
        entry.code=DetourCodeFromPointer(entry.target,nullptr);
        if(!entry.code) return fail(Admission::InvalidRegion,ERROR_INVALID_ADDRESS);
        PVOID addresses[]={entry.target,reinterpret_cast<BYTE*>(entry.target)+63,
                           entry.code,reinterpret_cast<BYTE*>(entry.code)+63};
        failed_stage=static_cast<LONG>(Stage::Region);
        for(unsigned i=0;i<4;++i) {
            region_index=static_cast<LONG>(i);
            if(!capture_region(addresses[i],entry.regions[i])) return fail(Admission::InvalidRegion,ERROR_INVALID_ADDRESS);
        }
        *entry.original=entry.target;
    }
    failed_stage=static_cast<LONG>(Stage::Alias); failed_entry_index=-1;
    if(!select_physical_entries(entries,count,physical_entries,physical_count,cursor_pair_coalesced))
        return fail(Admission::DuplicateTarget,ERROR_DUP_NAME);
    // No runtime unload: the trampolines/wrappers must outlive every caller,
    // including the short-lived LC child. No primary-command-PID exemption.
    failed_stage=static_cast<LONG>(Stage::Pin); failed_entry_index=-1;
    if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCWSTR>(&current_desktop),&pinned_self)) return fail(Admission::PinFailed,GetLastError());
    const TransactionApi api={DetourTransactionBegin,DetourUpdateThread,DetourAttach,DetourDetach,
                              DetourTransactionCommit,DetourTransactionAbort};
    const LONG result=transact(api,physical_entries,physical_count,false);
    if(result!=NO_ERROR) return fail(Admission::TransactionFailed,result);
    failed_stage=static_cast<LONG>(Stage::Protection);
    if(!protections_restored()) {
        const LONG saved_entry=failed_entry_index, saved_region=region_index;
        const LONG rollback=transact(api,physical_entries,physical_count,true);
        failed_stage=static_cast<LONG>(Stage::Protection); failed_entry_index=saved_entry; region_index=saved_region;
        return fail(Admission::ProtectionMismatch,rollback==NO_ERROR ? ERROR_INVALID_ACCESS : rollback);
    }
    installed=true; failed_stage=static_cast<LONG>(Stage::Ready); failed_entry_index=-1;
    InterlockedExchange(&admission,static_cast<LONG>(Admission::Installed)); return true;
}
} // namespace owned_background_guard
inline bool BackgroundGuardCurrentDesktop() noexcept { return owned_background_guard::current_desktop(); }
inline bool BackgroundGuardProcessAttach() noexcept { return owned_background_guard::attach(); }
inline bool BackgroundGuardInstalled() noexcept { return owned_background_guard::installed; }
inline LONG BackgroundGuardAdmission() noexcept { return owned_background_guard::admission; }
inline LONG BackgroundGuardError() noexcept { return owned_background_guard::last_error; }
struct BackgroundGuardDiagnostics {
    LONG stage, entry_index, alias_peer_index, region_index, query_available;
    DWORD query_state, query_protect, query_type;
};
inline BackgroundGuardDiagnostics BackgroundGuardReadDiagnostics() noexcept {
    using namespace owned_background_guard;
    return {failed_stage,failed_entry_index,alias_peer_index,region_index,query_available,
            query_state,query_protect,query_type};
}
inline LONG64 BackgroundGuardCallCount(const char* name) noexcept {
    using namespace owned_background_guard;
    for(unsigned i=0;i<count;++i) if(same_text(name,entries[i].name)) {
        // One physical wrapper cannot attribute which aliased export was used.
        if(cursor_pair_coalesced && (i==4 || i==5)) return -1;
        return InterlockedCompareExchange64(&calls[i],0,0);
    }
    return -1;
}
struct BackgroundGuardSnapshot {
    BOOL installed;
    DWORD hooks_count;
    DWORD protected_exports;
    LONG64 blocked_display_calls;
    LONG64 blocked_input_calls;
    LONG admission;
    LONG error;
};
inline BackgroundGuardSnapshot BackgroundGuardReadSnapshot() noexcept {
    using namespace owned_background_guard;
    LONG64 inputs=0;
    for(unsigned i=4;i<=11;++i) inputs+=InterlockedCompareExchange64(&calls[i],0,0);
    for(unsigned i=15;i<=17;++i) inputs+=InterlockedCompareExchange64(&calls[i],0,0);
    return {installed ? TRUE : FALSE,installed ? physical_count : 0,installed ? count : 0,
            InterlockedCompareExchange64(&blocked_display,0,0),inputs,admission,last_error};
}
inline void BackgroundGuardDetach(bool processTermination) noexcept {
    // Pinned for process lifetime. OS reclaims the process; no User32 calls,
    // transaction work, or user display/cursor/focus restoration under loader lock.
    (void)processTermination;
}
