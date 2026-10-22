#pragma once
#include <cstdint>
#include <cstring>
#include <climits>
namespace shop_wndproc_input {
struct Request {
    uint32_t pid=0,seq=0,uiThread=0,dpi=0;
    uint64_t birth=0,hwnd=0,player=0,expectedNpcUid=0;
    int32_t x=0,y=0,rect[4]{};
    char hash[65]{};bool bodyPoint=false;
};
inline bool Literal(const char*& p,const char* wanted) noexcept {
    const auto n=std::strlen(wanted);if(std::strncmp(p,wanted,n))return false;p+=n;return true;
}
inline bool Number(const char*& p,uint64_t maximum,uint64_t& out) noexcept {
    if(*p<'0'||*p>'9')return false;const char* start=p;out=0;
    while(*p>='0'&&*p<='9'){
        const unsigned digit=static_cast<unsigned>(*p-'0');
        if(out>maximum/10||(out==maximum/10&&digit>maximum%10))return false;
        out=out*10+digit;++p;
    }
    return p-start==1||*start!='0';
}
inline bool Signed(const char*& p,int32_t& out) noexcept {
    const bool negative=*p=='-';if(negative)++p;uint64_t value=0;
    if(!Number(p,negative?2147483648ull:2147483647ull,value)||(negative&&!value))return false;
    out=negative?static_cast<int32_t>(-static_cast<int64_t>(value)):static_cast<int32_t>(value);return true;
}
inline bool Valid(const Request& r) noexcept {
    return r.pid&&r.birth&&r.seq&&r.seq<=INT32_MAX&&r.hwnd&&r.uiThread&&r.dpi&&r.player&&
        r.x>=-32768&&r.x<=32767&&r.y>=-32768&&r.y<=32767&&
        r.rect[0]<=r.x&&r.x<r.rect[2]&&r.rect[1]<=r.y&&r.y<r.rect[3];
}
inline bool Parse(const char* text,Request& r) noexcept {
    r={};const char* p=text;uint64_t pid=0,seq=0,tid=0,dpi=0;
    if(!Literal(p,"{\"schema\":\"own-shop-whole-wndproc-request-v1\",\"pid\":")||!Number(p,UINT32_MAX,pid)||
       !Literal(p,",\"birth\":")||!Number(p,UINT64_MAX,r.birth)||!Literal(p,",\"candidate_sha256\":\""))return false;
    // Bounded input is always NUL-terminated by the file reader. Reject early
    // terminators before advancing, including truncated SHA fields.
    for(unsigned i=0;i<64;++i){const char c=*p;if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;r.hash[i]=c;++p;}
    if(!Literal(p,"\",\"seq\":")||!Number(p,INT32_MAX,seq)||!Literal(p,",\"hwnd\":")||!Number(p,UINT64_MAX,r.hwnd)||
       !Literal(p,",\"ui_thread\":")||!Number(p,UINT32_MAX,tid)||!Literal(p,",\"x\":")||!Signed(p,r.x)||
       !Literal(p,",\"y\":")||!Signed(p,r.y)||!Literal(p,",\"client_rect\":["))return false;
    for(unsigned i=0;i<4;++i){if(i&&!Literal(p,","))return false;if(!Signed(p,r.rect[i]))return false;}
    if(!Literal(p,"],\"window_dpi\":")||!Number(p,UINT32_MAX,dpi)||!Literal(p,",\"player_uid\":")||!Number(p,UINT64_MAX,r.player)||
       !Literal(p,",\"expected_npc_uid\":")||!Number(p,UINT64_MAX,r.expectedNpcUid)||!Literal(p,",\"point_source\":\""))return false;
    if(Literal(p,"BODY\"}"))r.bodyPoint=true;else if(!Literal(p,"EXPLICIT\"}"))return false;
    if(*p=='\r')++p;if(*p=='\n')++p;if(*p)return false;
    r.pid=static_cast<uint32_t>(pid);r.seq=static_cast<uint32_t>(seq);
    r.uiThread=static_cast<uint32_t>(tid);r.dpi=static_cast<uint32_t>(dpi);return Valid(r);
}
inline bool Identity(const Request& r,uint32_t pid,uint64_t birth,const char* hash,unsigned posted,unsigned previous) noexcept {
    return Valid(r)&&r.pid==pid&&r.birth==birth&&!std::strcmp(r.hash,hash)&&r.seq==posted&&r.seq>previous;
}
}
