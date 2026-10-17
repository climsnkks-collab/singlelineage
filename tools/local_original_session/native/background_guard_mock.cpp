// Fake originals only. Compile here; execution belongs to the main session.
#define OWN_BACKGROUND_GUARD_MOCK
#include "background_guard.hpp"
#include <cstdio>
using namespace owned_background_guard;
static int original_calls=0, checks=0, failures=0;
static bool desktop_ok=false, window_ok=false;
static bool desktop() noexcept { return desktop_ok; }
static bool window(HWND) noexcept { return window_ok; }
static LONG WINAPI fake_change(DEVMODEW*,DWORD) { ++original_calls; return DISP_CHANGE_SUCCESSFUL; }
static LONG WINAPI fake_ex(LPCWSTR,DEVMODEW*,HWND,DWORD,LPVOID) { ++original_calls; return DISP_CHANGE_SUCCESSFUL; }
static BOOL WINAPI fake_cursor(int,int) { ++original_calls; return TRUE; }
static HWND WINAPI fake_create(DWORD,LPCWSTR,LPCWSTR,DWORD,int,int,int,int,HWND,HMENU,HINSTANCE,LPVOID) {
    ++original_calls; return reinterpret_cast<HWND>(42);
}
static BOOL WINAPI fake_show(HWND,int command) { ++original_calls; return command==SW_SHOWNOACTIVATE || command==SW_HIDE; }
static void check(bool value) { ++checks; if(!value) ++failures; }
static LONG begin_error=0, update_error=0, attach_error_index=-1, commit_error=0;
static unsigned attached=0, aborted=0, committed=0;
static LONG WINAPI begin() { return begin_error; }
static LONG WINAPI update(HANDLE) { return update_error; }
static LONG WINAPI add(PVOID*,PVOID) { return static_cast<LONG>(attached++)==attach_error_index ? ERROR_ACCESS_DENIED : NO_ERROR; }
static LONG WINAPI commit() { ++committed; return commit_error; }
static LONG WINAPI abort_transaction() { ++aborted; return NO_ERROR; }
int main() {
    mock_desktop=desktop; mock_window=window;
    real_ChangeDisplaySettingsW=fake_change; real_ChangeDisplaySettingsExW=fake_ex;
    real_CreateWindowExW=fake_create; real_ShowWindow=fake_show;
    DEVMODEW mode{};
    check(change_w(nullptr,0)==DISP_CHANGE_FAILED && original_calls==0);
    check(change_w(&mode,CDS_FULLSCREEN)==DISP_CHANGE_FAILED && original_calls==0);
    check(change_w(&mode,CDS_TEST|CDS_FULLSCREEN)==DISP_CHANGE_FAILED && original_calls==0);
    check(change_w(&mode,CDS_TEST)==DISP_CHANGE_SUCCESSFUL && original_calls==1);
    check(change_ex_w(L"unused",nullptr,nullptr,CDS_TEST,nullptr)==DISP_CHANGE_FAILED && original_calls==1);
    check(change_ex_w(L"unused",&mode,reinterpret_cast<HWND>(1),CDS_TEST,nullptr)==DISP_CHANGE_FAILED && original_calls==1);
    check(change_ex_w(L"unused",&mode,nullptr,CDS_TEST,reinterpret_cast<void*>(1))==DISP_CHANGE_FAILED && original_calls==1);
    check(change_ex_w(L"unused",&mode,nullptr,CDS_TEST,nullptr)==DISP_CHANGE_SUCCESSFUL && original_calls==2);
    check(!cursor(1,2) && !physical_cursor(1,2) && !clip(nullptr) && !foreground(nullptr));
    check(!active(nullptr) && !focus(nullptr) && !bring(nullptr) && !switch_desktop(nullptr));
    check(send_input(0,nullptr,0)==0); mouse(0,0,0,0,0); key(0,0,0,0);
    check(original_calls==2 && BackgroundGuardReadSnapshot().blocked_input_calls==11);
    check(!create_w(0,L"fake",L"fake",0,0,0,0,0,nullptr,nullptr,nullptr,nullptr) && original_calls==2);
    desktop_ok=true;
    check(create_w(0,L"fake",L"fake",0,0,0,0,0,nullptr,nullptr,nullptr,nullptr)==reinterpret_cast<HWND>(42) && original_calls==3);
    check(!show(reinterpret_cast<HWND>(42),SW_SHOW) && original_calls==3);
    window_ok=true;
    check(show(reinterpret_cast<HWND>(42),SW_SHOW) && original_calls==4);
    check(show(reinterpret_cast<HWND>(42),SW_HIDE) && original_calls==5);
    Entry rows[3]{}; int tokens[6]{};
    for(unsigned i=0;i<3;++i) { rows[i].target=&tokens[i]; rows[i].code=&tokens[i+3]; }
    check(distinct_targets(rows,3)); rows[2].code=rows[0].code; check(!distinct_targets(rows,3));
    rows[2].code=&tokens[5]; rows[2].target=rows[0].target; check(!distinct_targets(rows,3));
    TransactionApi api={begin,update,add,add,commit,abort_transaction};
    for(int index=0;index<3;++index) {
        attach_error_index=index; attached=aborted=committed=0;
        check(transact(api,rows,3,false)==ERROR_ACCESS_DENIED && aborted==1 && committed==0 && attached==static_cast<unsigned>(index+1));
    }
    attach_error_index=-1; update_error=ERROR_ACCESS_DENIED; attached=aborted=committed=0;
    check(transact(api,rows,3,false)==ERROR_ACCESS_DENIED && aborted==1 && attached==0);
    update_error=0; begin_error=ERROR_BUSY; aborted=0;
    check(transact(api,rows,3,false)==ERROR_BUSY && aborted==0);
    begin_error=0; attached=aborted=committed=0;
    check(transact(api,rows,3,false)==NO_ERROR && attached==3 && committed==1 && aborted==0);
    commit_error=ERROR_INVALID_BLOCK; attached=aborted=committed=0;
    check(transact(api,rows,3,false)==ERROR_INVALID_BLOCK && committed==1);
    check(BackgroundGuardReadSnapshot().blocked_display_calls==6);
    Entry captured[count]{},selected[count]{}; int alias_tokens[count*2]{};
    for(unsigned i=0;i<count;++i) {
        captured[i]=entries[i]; captured[i].target=&alias_tokens[i]; captured[i].code=&alias_tokens[count+i];
    }
    captured[5].code=captured[4].code;
    unsigned selected_count=0; bool coalesced=false;
    check(select_physical_entries(captured,count,selected,selected_count,coalesced)
        && selected_count==17 && coalesced && selected[4].original==captured[4].original
        && selected[5].original==captured[6].original);
    real_SetCursorPos=fake_cursor; real_SetPhysicalCursorPos=fake_cursor;
    const int original_before=original_calls;
    const auto selected_cursor=reinterpret_cast<decltype(&::SetCursorPos)>(selected[4].wrapper);
    check(!selected_cursor(1,2) && !physical_cursor(1,2) && original_calls==original_before);
    captured[6].code=captured[4].code;
    check(!select_physical_entries(captured,count,selected,selected_count,coalesced)
        && failed_entry_index==6 && alias_peer_index==4);
    captured[6].code=&alias_tokens[count+6]; captured[5].code=&alias_tokens[count+5];
    captured[5].target=captured[4].target;
    check(!select_physical_entries(captured,count,selected,selected_count,coalesced));
    std::printf("{\"checks\":%d,\"failures\":%d,\"real_user32_calls\":0}\n",checks,failures);
    return failures ? 1 : 0;
}
