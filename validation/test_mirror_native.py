"""Compile new production C++ decoder, actual client class/methods and drawing
function. AP network and ImGui are controlled services, not a full game link."""
import argparse,subprocess,pathlib,json
p=argparse.ArgumentParser();p.add_argument('--source-root',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--compiler',default='clang++');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
def function(text,sig):
 start=text.index(sig);i=text.index('{',start);depth=0;mode='code';j=i
 while j<len(text):
  c=text[j];n=text[j:j+2]
  if mode=='line':
   if c=='\n':mode='code'
  elif mode=='block':
   if n=='*/':mode='code';j+=1
  elif mode in ('"',"'"):
   if c=='\\':j+=1
   elif c==mode:mode='code'
  elif n=='//':mode='line';j+=1
  elif n=='/*':mode='block';j+=1
  elif c in ('"',"'"):mode=c
  elif c=='{':depth+=1
  elif c=='}':
   depth-=1
   if depth==0:return text[start:j+1]
  j+=1
 raise ValueError(sig)
s=(a.source_root/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text()
funcs='\n'.join(function(s,sig) for sig in ('double FinderMirrorClock(', 'void ArchipelagoClient::ResetFinderMirror(', 'void ArchipelagoClient::RefreshFinderMirror(', 'const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot('))
draw=function((a.source_root/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text(),'static void DrawUniversalFinderMirror(')
cpp=r'''
#include <atomic>
#include <mutex>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <random>
#include <chrono>
#include <fstream>
#include <iostream>
#include <functional>
#include "soh/Network/Archipelago/TrackerMirror.h"
#define private public
#include "soh/Network/Archipelago/ArchipelagoClient.h"
#undef private
bool authenticated=true;
struct AP_Bounce { std::vector<std::string>* tags=nullptr;std::string data; };
std::vector<std::string> requests;
int playerId=1;int AP_GetPlayerID(){return playerId;}
void AP_SendBounce(const AP_Bounce& b){requests.push_back(b.data);}
bool ArchipelagoClient::IsAuthenticated()const{return authenticated;}
ArchipelagoClient& ArchipelagoClient::GetInstance(){static ArchipelagoClient c;return c;}
struct ImVec2 {float x,y;ImVec2(float a,float b):x(a),y(b){}};
namespace ImGui {
std::vector<std::string> rendered;
void TextWrapped(const char*,...){};void Text(const char*,...){};
void TextUnformatted(const char* s){rendered.emplace_back(s);}
bool Button(const char*){return false;}void Separator(){};
bool BeginChild(const char*,ImVec2,bool){return true;}void EndChild(){};
bool IsItemHovered(){return false;}void BeginTooltip(){};void EndTooltip(){};
}
''' + funcs + draw + r'''
int checks=0;
void ck(bool value,const char* name){++checks;if(!value){std::cerr<<"FAIL "<<name<<"\n";std::exit(1);}}
int main(int argc,char** argv){
 if(argc!=2)return 2;
 std::ifstream input(argv[1]);std::string payload((std::istreambuf_iterator<char>(input)),{});
 auto snapshot=SohExtreme::DecodeTrackerSnapshot(payload);
 using namespace SohExtreme;
 TrackerMirrorState store;store.Reset(snapshot.nonce);store.NextRequest();std::string status;
 auto valid=snapshot;valid.request=1;valid.revision=1;
 ck(store.Accept(valid,valid.slot,100,status),"initial snapshot");
 ck(store.Current(valid.slot,valid.received,valid.active,valid.checked,100,status)!=nullptr,"ready exact snapshot");
 ck(store.Current(valid.slot,valid.received+1,valid.active,valid.checked,100,status)==nullptr,"pending receipt rejected");
 auto extra=valid.active;extra.insert(999999999);
 ck(store.Current(valid.slot,valid.received,extra,valid.checked,100,status)==nullptr,"different active set rejected");
 extra=valid.checked;extra.insert(999999999);
 ck(store.Current(valid.slot,valid.received,valid.active,extra,100,status)==nullptr,"different checked set rejected");
 ck(store.Current(valid.slot,valid.received,valid.active,valid.checked,111,status)==nullptr,"expired snapshot hidden");
 ck(!store.Accept(valid,valid.slot,101,status),"duplicate revision rejected");
 auto bad=valid;bad.revision=2;bad.version="0.11.18";
 ck(!store.Accept(bad,valid.slot,101,status),"version mismatch rejected");
 bad=valid;bad.revision=2;bad.nonce=std::string(32,'e');
 ck(!store.Accept(bad,valid.slot,101,status),"nonce mismatch rejected");
 bad=valid;bad.revision=2;bad.slot++;
 ck(!store.Accept(bad,valid.slot,101,status),"slot mismatch rejected");
 bad=valid;bad.revision=2;bad.request=9;
 ck(!store.Accept(bad,valid.slot,101,status),"unsent request rejected");
 bad=valid;bad.revision=2;bad.producer="other";
 ck(!store.Accept(bad,valid.slot,101,status),"second producer pinned out");
 ck(store.Accept(bad,valid.slot,112,status),"tracker restart can recover after expiry");
 store.Reset(std::string(32,'d'));
 ck(store.Current(valid.slot,valid.received,valid.active,valid.checked,112,status)==nullptr,"save reset discards data");
 ck(!store.Accept(valid,valid.slot,112,status),"old save response rejected");
 for(const std::string invalid:{"", "=AAA", "A===", "AA=A", "AAAA=", "!!!!", "AB==", "AAB="}){
  bool failed=false;try{DecodeTrackerSnapshot(invalid);}catch(const std::exception&){failed=true;}
  ck(failed,"malformed payload rejected");
 }
 auto& client=ArchipelagoClient::GetInstance();client.ResetFinderMirror();
 client.finderMirror.Reset(snapshot.nonce);client.finderMirror.NextRequest();
 playerId=static_cast<int>(snapshot.slot);client.currentSaveIsArchipelago=true;client.activeLocationsLoaded=true;
 client.activeLocations.insert(snapshot.active.begin(),snapshot.active.end());
 client.reportedLocations.insert(snapshot.checked.begin(),snapshot.checked.end());
 client.incomingItemOrdinal=snapshot.received;client.appliedItemCount=snapshot.received;
 client.pendingFinderPayload=payload;
 ck(client.GetFinderSnapshot(status)!=nullptr,"actual client accepts matching payload");
 ck(!requests.empty()&&requests.back().find("SOHExtremeFinder1")!=std::string::npos,"actual client sends request");
 DrawUniversalFinderMirror();
 ck(ImGui::rendered.size()==snapshot.rows.size()||snapshot.rows.empty(),"actual view draws full list");
 if(!snapshot.rows.empty())for(size_t i=0;i<snapshot.rows.size();++i){
  const auto& row=snapshot.rows[i];
  const std::string expected=(row.state==2?"[Glitched] ":"")+row.region+" | "+row.name;
  ck(ImGui::rendered[i]==expected,"actual view matches received labels/state");
 }
 authenticated=false;ck(client.GetFinderSnapshot(status)==nullptr,"disconnected hides availability");
 std::cout<<"CHECKS\t"<<checks<<"\n";
 for(const auto& row:snapshot.rows)std::cout<<row.id<<"\t"<<unsigned(row.state)<<"\t"<<row.region<<" | "<<row.name<<"\n";
 return 0;
}
'''
(a.out/'mirror_native.cpp').write_text(cpp)
binary=a.out/'mirror_native'
cmd=[a.compiler,'-std=c++20','-Wall','-Wextra','-Werror','-O1','-I'+str(a.source_root.resolve()),str(a.out/'mirror_native.cpp'),'-o',str(binary)]
r=subprocess.run(cmd,text=True,capture_output=True);(a.out/'compile.log').write_text(r.stdout+r.stderr)
if r.returncode:print(r.stderr);raise SystemExit(r.returncode)
print(binary)
