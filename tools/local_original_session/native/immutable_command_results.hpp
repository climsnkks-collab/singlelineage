#pragma once
// Opt-in only. Caller retains the trusted owned boundary and sole producer.
// A false return means publication was not confirmed, not that bytes are absent.
#include <windows.h>
#include <cstdint>
#include <cstring>
namespace immutable_command_results {
constexpr size_t PathChars=600;
constexpr int PayloadBound=1024;
inline bool Path(const wchar_t* directory,uint32_t sequence,wchar_t (&path)[PathChars]) noexcept {
    if(!directory||!sequence||sequence>2147483647u)return false;
    size_t length=0;while(length<PathChars&&directory[length])++length;
    if(length<3||length>=PathChars)return false;
    const wchar_t drive=directory[0];
    if(!((drive>=L'A'&&drive<=L'Z')||(drive>=L'a'&&drive<=L'z'))||directory[1]!=L':'||directory[2]!=L'\\')return false;
    wchar_t reverse[10]{};unsigned digits=0;uint32_t value=sequence;
    do{reverse[digits++]=static_cast<wchar_t>(L'0'+value%10);value/=10;}while(value);
    const bool separator=directory[length-1]!=L'\\';
    constexpr wchar_t prefix[]=L"command-result-",suffix[]=L".json";
    constexpr size_t prefixSize=sizeof(prefix)/sizeof(wchar_t)-1,suffixSize=sizeof(suffix)/sizeof(wchar_t)-1;
    if(length+(separator?1u:0u)+prefixSize+digits+suffixSize>=PathChars)return false;
    memcpy(path,directory,length*sizeof(wchar_t));size_t cursor=length;
    if(separator)path[cursor++]=L'\\';
    memcpy(path+cursor,prefix,prefixSize*sizeof(wchar_t));cursor+=prefixSize;
    while(digits)path[cursor++]=reverse[--digits];
    memcpy(path+cursor,suffix,sizeof(suffix));return true;
}
struct Win32Ops {
    DWORD Error() const noexcept {return GetLastError();}
    void Error(DWORD error) const noexcept {SetLastError(error);}
    HANDLE Open(const wchar_t* path) const noexcept {
        return CreateFileW(path,GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    }
    bool Write(HANDLE file,const char* text,DWORD size,DWORD& written) const noexcept {
        return WriteFile(file,text,size,&written,nullptr)!=FALSE;
    }
    bool Close(HANDLE file) const noexcept {return CloseHandle(file)!=FALSE;}
};
template<class Ops> inline bool Publish(Ops& op,const wchar_t* directory,uint32_t sequence,const char* text,int size) noexcept {
    if(!text||size<1||size>PayloadBound||!sequence||sequence>2147483647u){op.Error(ERROR_INVALID_PARAMETER);return false;}
    wchar_t path[PathChars]{};if(!Path(directory,sequence,path)){op.Error(ERROR_INVALID_NAME);return false;}
    const HANDLE file=op.Open(path);if(file==INVALID_HANDLE_VALUE)return false;
    DWORD written=0;const bool wrote=op.Write(file,text,static_cast<DWORD>(size),written);
    const DWORD writeError=wrote?ERROR_WRITE_FAULT:op.Error();
    const bool closed=op.Close(file);const DWORD closeError=closed?ERROR_SUCCESS:op.Error();
    if(!wrote||written!=static_cast<DWORD>(size)){op.Error(writeError);return false;}
    if(!closed){op.Error(closeError);return false;}
    return true;
}
} // namespace immutable_command_results
