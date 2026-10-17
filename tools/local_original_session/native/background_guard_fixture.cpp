// Main-owned runtime fixture: never run on the input desktop. Only invalid
// display/device + invalid SwitchDesktop probes; no cursor/clip/activation API.
#include "background_guard.hpp"
// One bounded, CREATE_NEW diagnostic write. DLL failure path uses Kernel32
// only and consumes solely metadata already produced by the guard checks.
namespace guard_fixture_diagnostic {
struct Json {
    char bytes[1024]{}; DWORD size=0; bool valid=true;
    void text(const char* value) noexcept {
        for(unsigned i=0;value[i];++i) {
            if(size>=sizeof(bytes)-1) { valid=false; return; }
            bytes[size++]=value[i];
        }
    }
    void number(LONGLONG value) noexcept {
        if(value<0) { text("-"); value=-value; }
        char digits[24]{}; unsigned count=0;
        do { digits[count++]=static_cast<char>('0'+value%10); value/=10; } while(value && count<24);
        while(count) { char one[2]={digits[--count],0}; text(one); }
    }
};
inline void write(const wchar_t* path,const Json& json) noexcept {
    if(!json.valid || !json.size) return;
    const HANDLE file=CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if(file==INVALID_HANDLE_VALUE) return;
    DWORD written=0; WriteFile(file,json.bytes,json.size,&written,nullptr); CloseHandle(file);
}
inline void attach_failure() noexcept {
    const DWORD previous=GetLastError();
    wchar_t path[1024]{};
    const DWORD length=GetEnvironmentVariableW(L"OWN_BACKGROUND_GUARD_DIAGNOSTIC_FILE",path,1024);
    if(length && length<1024) {
        const auto d=BackgroundGuardReadDiagnostics(); Json j;
        j.text("{\"status\":\"GUARD_ATTACH_FAILED\",\"admission\":"); j.number(BackgroundGuardAdmission());
        j.text(",\"error\":"); j.number(BackgroundGuardError());
        j.text(",\"stage\":"); j.number(d.stage); j.text(",\"entry_index\":"); j.number(d.entry_index);
        j.text(",\"alias_peer_index\":"); j.number(d.alias_peer_index);
        j.text(",\"region_index\":"); j.number(d.region_index);
        j.text(",\"query_available\":"); j.number(d.query_available);
        j.text(",\"query_state\":"); j.number(d.query_state);
        j.text(",\"query_protect\":"); j.number(d.query_protect);
        j.text(",\"query_type\":"); j.number(d.query_type);
        if(d.entry_index>=0 && static_cast<unsigned>(d.entry_index)<owned_background_guard::count) {
            j.text(",\"entry_name\":\""); j.text(owned_background_guard::entries[d.entry_index].name); j.text("\"");
        }
        if(d.alias_peer_index>=0 && static_cast<unsigned>(d.alias_peer_index)<owned_background_guard::count) {
            j.text(",\"alias_peer_name\":\""); j.text(owned_background_guard::entries[d.alias_peer_index].name); j.text("\"");
        }
        j.text("}\n"); write(path,j);
    }
    SetLastError(previous);
}
inline void load_failure(const wchar_t* path,DWORD error) noexcept {
    Json j; j.text("{\"status\":\"LOAD_LIBRARY_FAILED\",\"load_library_error\":");
    j.number(error); j.text("}\n"); write(path,j);
}
} // namespace guard_fixture_diagnostic
#ifdef OWN_BACKGROUND_GUARD_FIXTURE_DLL
extern "C" __declspec(dllexport) BOOL WINAPI OwnedGuardReadSnapshot(BackgroundGuardSnapshot* output) {
    if(!output) return FALSE; *output=BackgroundGuardReadSnapshot(); return TRUE;
}
BOOL WINAPI DllMain(HINSTANCE,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH) {
        if(BackgroundGuardProcessAttach()) return TRUE;
        guard_fixture_diagnostic::attach_failure(); return FALSE;
    }
    if(reason==DLL_PROCESS_DETACH) BackgroundGuardDetach(reserved!=nullptr);
    return TRUE;
}
#else
#include <cstdio>
#include <cstdint>
using SnapshotReader=BOOL (WINAPI*)(BackgroundGuardSnapshot*);
static SnapshotReader read_snapshot=nullptr;
static const wchar_t* result_path=nullptr;
static bool received=false;
static UINT marker_message=0;
static bool report(const char* status,HWND window) {
    BackgroundGuardSnapshot state{};
    if(!read_snapshot || !read_snapshot(&state)) return false;
    FILE* output=nullptr;
    if(_wfopen_s(&output,result_path,L"wb")!=0 || !output) return false;
    const int written=std::fprintf(output,
        "{\"status\":\"%s\",\"installed\":%s,\"hooks_count\":%lu,\"protected_exports\":%lu,\"blocked_display_calls\":%lld,"
        "\"blocked_input_calls\":%lld,\"private_desktop\":true,\"hwnd\":%llu,\"thread_id\":%lu,"
        "\"marker_message\":%u,\"marker_received\":%s}\n",status,state.installed ? "true":"false",
        state.hooks_count,state.protected_exports,state.blocked_display_calls,state.blocked_input_calls,
        static_cast<unsigned long long>(reinterpret_cast<uintptr_t>(window)),GetCurrentThreadId(),
        marker_message,received ? "true":"false");
    const int closed=std::fclose(output); return written>0 && closed==0;
}
static LRESULT CALLBACK procedure(HWND window,UINT message,WPARAM wparam,LPARAM lparam) {
    if(marker_message>=0xc000 && message==marker_message && wparam==1 && lparam==0) {
        received=true; const bool wrote=report("RECEIVED",window);
        DestroyWindow(window); PostQuitMessage(wrote ? 0 : 8); return 0;
    }
    if(message==WM_TIMER) {
        report("TIMEOUT",window); DestroyWindow(window); PostQuitMessage(7); return 0;
    }
    return DefWindowProcW(window,message,wparam,lparam);
}
int wmain(int argc,wchar_t** argv) {
    if(argc!=3 || !BackgroundGuardCurrentDesktop()) return 2;
    marker_message=RegisterWindowMessageW(L"LC-Owned-Internal-Command-v1");
    if(marker_message<0xc000) return 2;
    result_path=argv[2];
    // Load occurs outside loader callbacks; original test calls below are made
    // only after the actual DLL reports all exports installed successfully.
    const HMODULE library=LoadLibraryW(argv[1]);
    if(!library) { const DWORD error=GetLastError(); guard_fixture_diagnostic::load_failure(result_path,error); return 3; }
    read_snapshot=reinterpret_cast<SnapshotReader>(GetProcAddress(library,"OwnedGuardReadSnapshot"));
    BackgroundGuardSnapshot before{},after{};
    if(!read_snapshot || !read_snapshot(&before) || !before.installed || before.protected_exports!=18
        || (before.hooks_count!=17 && before.hooks_count!=18)) return 4;
    constexpr wchar_t device_prefix[]=L"LC-Owned-NoSuchDisplay-";
    wchar_t desktop[96]{},device[96]=L"LC-Owned-NoSuchDisplay-";
    if(!owned_background_guard::expected_desktop(desktop)) return 4;
    constexpr unsigned prefix=static_cast<unsigned>(sizeof(device_prefix)/sizeof(wchar_t)-1);
    for(unsigned i=0;i<32;++i) device[prefix+i]=desktop[18+i];
    device[prefix+32]=0;
    // Even without hooks: nonexistent display name and invalid desktop handle.
    const LONG display=ChangeDisplaySettingsExW(device,nullptr,nullptr,CDS_FULLSCREEN,nullptr);
    const BOOL switched=SwitchDesktop(nullptr);
    if(!read_snapshot(&after) || display!=DISP_CHANGE_FAILED || switched!=FALSE
        || after.blocked_display_calls!=before.blocked_display_calls+1
        || after.blocked_input_calls!=before.blocked_input_calls+1) return 5;
    const HINSTANCE instance=GetModuleHandleW(nullptr);
    WNDCLASSEXW klass{}; klass.cbSize=sizeof(klass); klass.lpfnWndProc=procedure;
    klass.hInstance=instance; klass.lpszClassName=L"LC-Owned-Guard-Hidden-Fixture";
    if(!RegisterClassExW(&klass)) return 6;
    const HWND window=CreateWindowExW(WS_EX_NOACTIVATE,klass.lpszClassName,L"",WS_OVERLAPPED,
        0,0,16,16,nullptr,nullptr,instance,nullptr);
    if(!window) return 6;
    DWORD pid=0; const DWORD tid=GetWindowThreadProcessId(window,&pid);
    if(pid!=GetCurrentProcessId() || tid!=GetCurrentThreadId() || IsWindowVisible(window)
        || !BackgroundGuardCurrentDesktop() || !SetTimer(window,1,15000,nullptr)) {
        DestroyWindow(window); return 6;
    }
    if(!report("READY",window)) { DestroyWindow(window); return 8; }
    MSG message{}; int result=0;
    while((result=GetMessageW(&message,nullptr,0,0))>0) { TranslateMessage(&message); DispatchMessageW(&message); }
    return result<0 ? 9 : static_cast<int>(message.wParam);
}
#endif
