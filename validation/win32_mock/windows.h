#pragma once
// Controlled Win32 declarations for compiling and exercising the production
// process-owner branch on Linux. NOT a Windows SDK or ABI validation.
#include <cstdint>
#include <cwchar>
#include <map>
#include <string>
#include <vector>
using DWORD=uint32_t; using BOOL=int; using HANDLE=void*; using HKEY=void*; using BYTE=unsigned char;
using REGSAM=uint32_t; using LSTATUS=long; using SIZE_T=size_t; using WCHAR=wchar_t;
constexpr DWORD ERROR_SUCCESS=0,ERROR_NO_MORE_ITEMS=259,CP_UTF8=65001,MB_ERR_INVALID_CHARS=8;
constexpr REGSAM KEY_READ=1,KEY_WOW64_64KEY=0x100,KEY_WOW64_32KEY=0x200;
constexpr DWORD REG_SZ=1,REG_EXPAND_SZ=2,HANDLE_FLAG_INHERIT=1,GENERIC_WRITE=0x40000000,
 FILE_SHARE_READ=1,FILE_SHARE_WRITE=2,OPEN_EXISTING=3,JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE=0x2000,
 STARTF_USESTDHANDLES=0x100,STARTF_USESHOWWINDOW=1,SW_HIDE=0,CREATE_NO_WINDOW=0x8000000,
 CREATE_SUSPENDED=4,EXTENDED_STARTUPINFO_PRESENT=0x80000,STILL_ACTIVE=259;
constexpr BOOL TRUE=1;
#define HKEY_CURRENT_USER ((HKEY)(uintptr_t)1)
#define HKEY_LOCAL_MACHINE ((HKEY)(uintptr_t)2)
#define INVALID_HANDLE_VALUE ((HANDLE)(intptr_t)-1)
constexpr int JobObjectExtendedLimitInformation=9,PROC_THREAD_ATTRIBUTE_HANDLE_LIST=2;
struct SECURITY_ATTRIBUTES{DWORD nLength;void* lpSecurityDescriptor;BOOL bInheritHandle;};
struct LIMIT{DWORD LimitFlags;};
struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION{LIMIT BasicLimitInformation;};
struct ATTR{char b[128];}; using LPPROC_THREAD_ATTRIBUTE_LIST=ATTR*;
struct STARTUPINFOW{DWORD cb=0,dwFlags=0;uint16_t wShowWindow=0;HANDLE hStdInput=nullptr,hStdOutput=nullptr,hStdError=nullptr;};
struct STARTUPINFOEXW{STARTUPINFOW StartupInfo;LPPROC_THREAD_ATTRIBUTE_LIST lpAttributeList;};
struct PROCESS_INFORMATION{HANDLE hProcess;HANDLE hThread;DWORD dwProcessId,dwThreadId;};
namespace Mock {
struct Resource{int type;bool open=true;DWORD exit=STILL_ACTIVE;Resource* child=nullptr;};
inline std::vector<Resource*> handles;
inline DWORD error=5,flags=0;
inline bool assignOK=true,createOK=true,resumeOK=true;
inline int creates=0,terminations=0;
inline std::wstring application,command;
inline std::string pipe;
inline std::vector<HANDLE> inherited;
inline Resource* New(int type){auto* p=new Resource{type};handles.push_back(p);return p;}
inline Resource* lastProcess=nullptr;
}
inline DWORD GetLastError(){return Mock::error;}
inline BOOL CloseHandle(HANDLE h){auto* p=static_cast<Mock::Resource*>(h);if(!p->open)return 0;p->open=false;if(p->type==4&&p->child)p->child->exit=1;return 1;}
inline int MultiByteToWideChar(unsigned,DWORD,const char* s,int len,wchar_t* dst,int){if(dst)for(int i=0;i<len;i++)dst[i]=(unsigned char)s[i];return len;}
inline int WideCharToMultiByte(unsigned,DWORD,const wchar_t* s,int len,char* dst,int,const char*,BOOL*){if(dst)for(int i=0;i<len;i++)dst[i]=(char)s[i];return len;}
inline DWORD GetEnvironmentVariableW(const wchar_t*,wchar_t*,DWORD){return 0;}
inline LSTATUS RegOpenKeyExW(HKEY,const wchar_t*,DWORD,REGSAM,HKEY*){return 2;}
inline LSTATUS RegQueryValueExW(HKEY,const wchar_t*,DWORD*,DWORD*,BYTE*,DWORD*){return 2;}
inline LSTATUS RegCloseKey(HKEY){return 0;}
inline LSTATUS RegEnumKeyExW(HKEY,DWORD,wchar_t*,DWORD*,DWORD*,wchar_t*,DWORD*,void*){return ERROR_NO_MORE_ITEMS;}
inline DWORD ExpandEnvironmentStringsW(const wchar_t*,wchar_t*,DWORD){return 0;}
inline DWORD GetModuleFileNameW(HANDLE,wchar_t*,DWORD){return 0;}
inline BOOL CreatePipe(HANDLE* r,HANDLE* w,SECURITY_ATTRIBUTES*,DWORD n){if(n!=65536)return 0;*r=Mock::New(1);*w=Mock::New(2);return 1;}
inline BOOL SetHandleInformation(HANDLE,DWORD,DWORD){return 1;}
inline HANDLE CreateFileW(const wchar_t*,DWORD,DWORD,SECURITY_ATTRIBUTES*,DWORD,DWORD,HANDLE){return Mock::New(3);}
inline HANDLE CreateJobObjectW(SECURITY_ATTRIBUTES*,const wchar_t*){return Mock::New(4);}
inline BOOL SetInformationJobObject(HANDLE,int,void* ptr,DWORD){return static_cast<JOBOBJECT_EXTENDED_LIMIT_INFORMATION*>(ptr)->BasicLimitInformation.LimitFlags==JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;}
inline BOOL InitializeProcThreadAttributeList(LPPROC_THREAD_ATTRIBUTE_LIST p,DWORD,DWORD,SIZE_T* bytes){*bytes=sizeof(ATTR);return p!=nullptr;}
inline void DeleteProcThreadAttributeList(LPPROC_THREAD_ATTRIBUTE_LIST){}
inline BOOL UpdateProcThreadAttribute(LPPROC_THREAD_ATTRIBUTE_LIST,DWORD,size_t,void* ptr,SIZE_T bytes,void*,void*){auto* handles=static_cast<HANDLE*>(ptr);Mock::inherited.assign(handles,handles+bytes/sizeof(HANDLE));return 1;}
inline BOOL CreateProcessW(const wchar_t* app,wchar_t* cmd,SECURITY_ATTRIBUTES*,SECURITY_ATTRIBUTES*,BOOL,DWORD flags,void*,const wchar_t*,STARTUPINFOW* start,PROCESS_INFORMATION* process){
 ++Mock::creates;Mock::application=app;Mock::command=cmd;Mock::flags=flags;
 if(!Mock::createOK)return 0;
 if(start->wShowWindow!=SW_HIDE||Mock::inherited.size()!=2)return 0;
 process->hProcess=Mock::lastProcess=Mock::New(5);process->hThread=Mock::New(6);return 1;
}
inline BOOL AssignProcessToJobObject(HANDLE job,HANDLE process){if(Mock::assignOK)static_cast<Mock::Resource*>(job)->child=static_cast<Mock::Resource*>(process);return Mock::assignOK;}
inline BOOL TerminateProcess(HANDLE process,unsigned code){++Mock::terminations;static_cast<Mock::Resource*>(process)->exit=code;return 1;}
inline BOOL WriteFile(HANDLE,const void* buffer,DWORD len,DWORD* written,void*){Mock::pipe.assign(static_cast<const char*>(buffer),len);*written=len;return 1;}
inline DWORD ResumeThread(HANDLE){return Mock::resumeOK?0:DWORD(-1);}
inline BOOL GetExitCodeProcess(HANDLE process,DWORD* code){*code=static_cast<Mock::Resource*>(process)->exit;return 1;}
