#pragma once
#include "selected_diag.hpp"
namespace key_diagnostic {
inline std::atomic<bool> invoke_claim{false},version_claim{false};
inline std::atomic<unsigned> order{0};
struct Stamp {DWORD thread=0;uint64_t filetime=0;unsigned order=0;};
inline Stamp stamp() noexcept {FILETIME f{};GetSystemTimePreciseAsFileTime(&f);return {GetCurrentThreadId(),(uint64_t(f.dwHighDateTime)<<32)|f.dwLowDateTime,order.fetch_add(1)+1};}
#ifdef OWN_KEY_HOST_TEST
extern void(*test_output)(const char*,const char*,int) noexcept;
#endif
// One CREATE_NEW owned handle per file; never reopen another pathname for return.
struct Record {
    HANDLE file=INVALID_HANDLE_VALUE;forward_diagnostic::Context context{};bool claimed=false,version=false;Stamp entry{},returned{};int state=0;
    explicit Record(bool isVersion,bool matched) noexcept:version(isVersion) {
        const DWORD before=GetLastError();
        if(matched && selected_diagnostic::valid_context(context)){
            bool expected=false;auto& claim=version?version_claim:invoke_claim;
            if(claim.compare_exchange_strong(expected,true)){
                claimed=true;entry=stamp();
#ifndef OWN_KEY_HOST_TEST
                wchar_t path[600]{};swprintf_s(path,L"%s\\%s",context.directory,version?L"key-version-send.json":L"key-task-invoke.json");
                file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
#endif
                write();
            }
        }
        SetLastError(before);
    }
    void write() noexcept {
        const DWORD before=GetLastError();char text[2048]{},returnThread[32]="null",returnTime[32]="null",returnOrder[32]="null";
        if(state){sprintf_s(returnThread,"%lu",returned.thread);sprintf_s(returnTime,"%llu",static_cast<unsigned long long>(returned.filetime));sprintf_s(returnOrder,"%u",returned.order);}
        const int n=sprintf_s(text,"{\"schema\":\"own-key-invoke-v1\",\"event\":\"%s\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"key_call_id\":1,\"manager_matches_selected\":true,\"originating_socket_epoch_proven\":false,\"entry_observed\":true,\"entry_thread_id\":%lu,\"entry_filetime\":%llu,\"entry_order\":%u,\"return_state\":%d,\"return_thread_id\":%s,\"return_filetime\":%s,\"return_order\":%s,\"opcode\":%s}\n",version?"KEY_VERSION_SEND":"KEY_TASK_INVOKE",context.pid,static_cast<unsigned long long>(context.birth),OWN_EXPECTED_PROGRAM_SHA,entry.thread,static_cast<unsigned long long>(entry.filetime),entry.order,state,returnThread,returnTime,returnOrder,version?"20020":"null");
#ifdef OWN_KEY_HOST_TEST
        test_output(version?"key-version-send.json":"key-task-invoke.json",text,n);
#else
        if(file!=INVALID_HANDLE_VALUE && n>0){LARGE_INTEGER zero{};DWORD count=0;if(SetFilePointerEx(file,zero,nullptr,FILE_BEGIN) && WriteFile(file,text,static_cast<DWORD>(n),&count,nullptr) && count==static_cast<DWORD>(n))SetEndOfFile(file);}
#endif
        SetLastError(before);
    }
    void complete(bool exception) noexcept {if(!claimed)return;const DWORD before=GetLastError();returned=stamp();state=exception?2:1;write();SetLastError(before);}
    ~Record(){const DWORD before=GetLastError();if(file!=INVALID_HANDLE_VALUE)CloseHandle(file);SetLastError(before);}
};
}
