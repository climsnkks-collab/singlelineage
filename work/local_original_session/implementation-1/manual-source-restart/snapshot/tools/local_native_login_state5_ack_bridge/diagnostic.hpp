#pragma once
#include "binding.hpp"
#include <cstdio>
#include <cwchar>
#include "bridge_candidate_v2.hpp"
namespace forward_diagnostic {
inline thread_local uint32_t binding_stage=0;inline thread_local int failed_record_id=-1;
struct Context {DWORD pid=0;uint64_t birth=0;wchar_t directory[512]{};};
inline bool context(Context& out) noexcept {
    const DWORD before=GetLastError();bool valid=false;
    __try {
        constexpr wchar_t prefix[]=L"C:\\Users\\Chansol\\Documents\\ChatGPT\\싱글리니지\\work\\local_native_login_key_invoke_boundary\\runs\\";
        const DWORD count=GetEnvironmentVariableW(L"OWN_KEY_INVOKE_BOUNDARY_DIR",out.directory,512);
        const std::size_t start=wcslen(prefix);
        if(count>start && count<512 && !wcsncmp(out.directory,prefix,start) && count-start<=32) {
            valid=true;for(std::size_t i=start;i<count;++i){const wchar_t c=out.directory[i];if(!((c>=L'a'&&c<=L'z')||(c>=L'0'&&c<=L'9')||c==L'-'))valid=false;}
        }
        if(valid) {
            wchar_t file[600]{};swprintf_s(file,L"%s\\context.json",out.directory);
            HANDLE handle=CreateFileW(file,GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
            valid=handle!=INVALID_HANDLE_VALUE;char bytes[513]{};DWORD n=0;
            if(valid){valid=ReadFile(handle,bytes,513,&n,nullptr) && n && n<=512;const BOOL closed=CloseHandle(handle);valid=valid && closed;}
            unsigned pid=0;unsigned long long birth=0;char hash[65]{};
            if(valid)valid=sscanf_s(bytes,"{\"schema\":\"own-key-invoke-primary-v1\",\"pid\":%u,\"birth\":%llu,\"candidate_sha256\":\"%64[0123456789abcdef]\"}",&pid,&birth,hash,65)==3;
            if(valid){while(n && (bytes[n-1]=='\r'||bytes[n-1]=='\n'))--n;bytes[n]=0;
                char canonical[512]{};sprintf_s(canonical,"{\"schema\":\"own-key-invoke-primary-v1\",\"pid\":%u,\"birth\":%llu,\"candidate_sha256\":\"%s\"}",pid,birth,hash);valid=!strcmp(canonical,bytes);}
            if(valid)valid=strlen(hash)==64 && !strcmp(hash,OWN_EXPECTED_PROGRAM_SHA) && pid==GetCurrentProcessId();
            FILETIME b{},e{},k{},u{};
            if(valid)valid=GetProcessTimes(GetCurrentProcess(),&b,&e,&k,&u) && ((uint64_t(b.dwHighDateTime)<<32)|b.dwLowDateTime)==birth;
            if(valid){out.pid=pid;out.birth=birth;}
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){valid=false;}
    SetLastError(before);return valid;
}
inline void emit(const wchar_t* leaf,const char* event,uint32_t role,uint32_t record,uint32_t reason,bool originalAttempt,bool originalReturned,const char* ownReason) noexcept {
    const DWORD before=GetLastError();Context c{};
    if(context(c)) {
        char text[1024]{};const int length=sprintf_s(text,"{\"schema\":\"own-forward-diagnostic-v2\",\"event\":\"%s\",\"pid\":%lu,\"birth\":%llu,\"candidate_sha256\":\"%s\",\"role\":%u,\"record_id\":%u,\"binding_reason\":%u,\"original_attempt\":%s,\"original_return_confirmed\":%s,\"own_disabled_reason\":\"%s\",\"native_edge_fallback_when_unbound\":true,\"binding_stage\":%u,\"failed_record_id\":%d}\n",event,c.pid,static_cast<unsigned long long>(c.birth),OWN_EXPECTED_PROGRAM_SHA,role,record,reason,originalAttempt?"true":"false",originalReturned?"true":"false",ownReason,binding_stage,failed_record_id);
        wchar_t path[600]{};swprintf_s(path,L"%s\\%s",c.directory,leaf);
        HANDLE file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(file!=INVALID_HANDLE_VALUE){DWORD n=0;if(length>0)WriteFile(file,text,static_cast<DWORD>(length),&n,nullptr);CloseHandle(file);}
    }
    SetLastError(before);
}
inline std::atomic<bool> entry{false},failure{false},success{false},attempt{false},returned{false};
inline void once(std::atomic<bool>& claim,const wchar_t* file,const char* event,ForwardRole role,uint32_t record,BindReason reason,bool attempted,bool complete,const char* why) noexcept {
    Context c{};if(!context(c))return;
    bool expected=false;if(claim.compare_exchange_strong(expected,true))emit(file,event,static_cast<unsigned>(role),record,static_cast<unsigned>(reason),attempted,complete,why);
}
}
