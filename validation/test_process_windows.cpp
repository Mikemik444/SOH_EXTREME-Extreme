// Load the host standard library before selecting the production Win32 branch.
// Operating-system calls are controlled; paths remain host paths for fixtures.
#include <algorithm>
#include <cwchar>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <vector>
#include <iostream>
#include <cassert>
#define _WIN32
#include "soh/Network/Archipelago/TrackerWorker.cpp"
int main(int argc,char** argv){
 assert(argc==2);
 std::filesystem::path base(argv[1]);std::filesystem::create_directories(base/"custom_worlds");
 std::ofstream(base/"ArchipelagoLauncherDebug.exe").put('x');
 SohExtreme::TrackerWorker w;std::string error;
 std::string path=(base/"ArchipelagoLauncherDebug.exe").string();
 std::string secret="{\"password\":\"Not in command line\"}";
 assert(!w.Start(path,secret,error));assert(Mock::creates==0); // old/missing world fails before Launcher GUI
 std::ofstream(base/"custom_worlds/soh_extreme.apworld")<<"zip filename test: soh_extreme/TrackerWorker.py";
 assert(w.Start(path,secret,error));assert(Mock::creates==1);assert(w.IsRunning(error));
 assert((Mock::flags&CREATE_NO_WINDOW)&&(Mock::flags&CREATE_SUSPENDED)&&(Mock::flags&EXTENDED_STARTUPINFO_PRESENT));
 assert(Mock::command.find(L"Not in command line")==std::wstring::npos);
 assert(Mock::command.find(L"--game-owned --nogui")!=std::wstring::npos);
 assert(Mock::pipe==secret+"\n");assert(Mock::inherited.size()==2);
 auto* first=Mock::lastProcess;w.Stop();assert(first->exit!=STILL_ACTIVE);assert(!first->open);
 auto* unrelated=Mock::New(5);assert(w.Start(path,secret,error));
 Mock::lastProcess->exit=22;assert(!w.IsRunning(error));assert(error.find("authenticate")!=std::string::npos);
 assert(unrelated->exit==STILL_ACTIVE);
 Mock::assignOK=false;assert(!w.Start(path,secret,error));assert(Mock::terminations==1);Mock::assignOK=true;
 Mock::resumeOK=false;assert(!w.Start(path,secret,error));assert(Mock::lastProcess->exit!=STILL_ACTIVE);Mock::resumeOK=true;
 Mock::createOK=false;assert(!w.Start(path,secret,error));Mock::createOK=true;
 assert(!w.Start(path,std::string(16001,'a'),error));
 assert(!w.Start(path,"{}\n{}",error));
 for(auto* p:Mock::handles){if(p!=unrelated)assert(!p->open);delete p;}
 std::cout<<"Production Windows process owner passed with controlled Win32 calls.\n";
 std::cout<<"No-window flags, private credential pipe, missing-world guard, job cleanup, failures, and unrelated-process isolation checked.\n";
}
