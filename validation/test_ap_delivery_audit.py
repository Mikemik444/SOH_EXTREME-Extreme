"""Production AP delivery/save functions with controlled engine/network services.

Run in a VS x64 developer terminal with --include-dir pointing to the directory
containing nlohmann/json.hpp. No live server or game is simulated by these tests.
"""
from pathlib import Path
import argparse, json, subprocess, sys
from run_native_tests import function
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent)
parser.add_argument('--include-dir',type=Path,required=True)
parser.add_argument('--output',type=Path,default=Path('work/ap-delivery-tests'))
a=parser.parse_args();root=a.source_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
ap=(root/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
save=(root/'soh/SaveManager.cpp').read_text(encoding='utf-8')
results=[]
def run(name,code):
 src=out/(name+'.cpp');exe=out/(name+'.exe');src.write_text(code,encoding='utf-8')
 c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(root),'/I',str(a.include_dir.resolve()),str(src),'/Fo'+str(out/(name+'.obj')),'/Fe'+str(exe)],capture_output=True,text=True)
 r=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
 passed=c.returncode==0 and r.returncode==0
 log=c.stdout+c.stderr+(r.stdout+r.stderr if r else '')
 (out/(name+'.log')).write_text(log)
 results.append(dict(name=name,passed=passed))
 print(('PASS ' if passed else 'FAIL ')+name,flush=True)
 if not passed:print(log[-5000:])
common=r'''
#include <cassert>
#include <atomic>
#include <algorithm>
#include <cstring>
#include <cstdint>
#include <deque>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <nlohmann/json.hpp>
#include "soh/Network/Archipelago/ArchipelagoSaveSnapshot.h"
#define SPDLOG_DEBUG(...) ((void)0)
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
#define CVAR_RANDOMIZER_SETTING(x) x
int CVarGetInteger(const char*,int){return 1;}
struct Notice{std::string prefix,message,suffix;float remainingTime;};
namespace Notification {void Emit(Notice){}}
namespace CheckTracker{void RecalculateAvailableChecks(){}}
constexpr int QUEST_RANDOMIZER=1;
struct SaveContext{struct {struct{int id=QUEST_RANDOMIZER;}quest;}ship;int inventory=0;}gSaveContext;
struct Play{int sceneNum=1;}play;Play*gPlayState=&play;
struct Actor{int id=0,params=0;struct{struct{int x=0,y=0,z=0;}pos;}home;};
bool Archipelago_IsManualSpeechActor(const Actor*){return true;}
uint64_t Archipelago_NpcSpeechIdentity(const Actor*a,int16_t){return a->id;}
constexpr int64_t AP_EXTREME_SPEECH_FALLBACK_BASE=1000,AP_EXTREME_SPEECH_FALLBACK_COUNT=3;
double clockValue=0;double FinderMirrorClock(){return clockValue;}
std::vector<int64_t>sent;std::vector<std::set<int64_t>>scoutPackets;
void AP_SendItem(int64_t id){sent.push_back(id);}int AP_GetPlayerID(){return 1;}
void AP_SendLocationScouts(std::set<int64_t> ids,bool){scoutPackets.push_back(ids);}
std::deque<int64_t> gDeferredLocationReports;
class ArchipelagoClient {public:
 static ArchipelagoClient&GetInstance(){static ArchipelagoClient instance;return instance;}
 bool currentSaveIsArchipelago=true,saveIdentityMismatch=false,authenticated=true,activeLocationsLoaded=true;
 std::atomic_bool enabled=true;
 bool IsAuthenticated()const{return authenticated;}
 uint64_t appliedItemCount=0;std::string saveServer="server",saveSlot="slot",cachedSlotSettingsJson="{}";
 std::vector<uint64_t>fallbackNpcSpeechHashes;std::unordered_set<uint64_t>fallbackNpcSpeechSeen;
 std::unordered_set<int64_t>activeLocations,reportedLocations,pendingLocationReports;
 struct Scout{int playerId=1;std::string itemName="Item",playerName="Player",locationName="NPC";};
 std::unordered_map<int64_t,Scout>scoutedLocations;
 std::unordered_map<int32_t,int64_t>rcToApLocation;
 bool scoutsRequested=false;size_t expectedScoutCount=0;double nextScoutRequest=0;
 int64_t ResolveApLocationForCheck(int32_t rc){auto it=rcToApLocation.find(rc);return it==rcToApLocation.end()?-1:it->second;}
 bool IsGameplaySessionActive()const;bool OwnsCheck(int32_t);bool OwnsCheckCached(int32_t)const;
 void QueueRemotePresentation(int64_t){} // Presentation lifecycle is covered by test_ap_presentation.py.
 void SendLocation(int64_t,bool=false);bool IsLocationSubmitted(int64_t)const;
 bool ReportNpcSpeechLocation(int64_t);bool ReportFallbackNpcSpeech(const Actor*);
 void LoadPendingLocations(const std::vector<int64_t>&);ArchipelagoSaveSnapshot CaptureSaveSnapshot()const;
 void RequestLocationScouts();
};
'''
methods='\n'.join(function(ap,sig) for sig in [
 'bool ArchipelagoClient::IsGameplaySessionActive()', 'bool ArchipelagoClient::OwnsCheck(',
 'bool ArchipelagoClient::OwnsCheckCached(', 'void ArchipelagoClient::SendLocation(',
 'bool ArchipelagoClient::IsLocationSubmitted(', 'bool ArchipelagoClient::ReportNpcSpeechLocation(',
 'bool ArchipelagoClient::ReportFallbackNpcSpeech(', 'void ArchipelagoClient::LoadPendingLocations(',
 'ArchipelagoSaveSnapshot ArchipelagoClient::CaptureSaveSnapshot()', 'void ArchipelagoClient::RequestLocationScouts()'])
run('location_delivery_and_isolation',common+methods+r'''
int main(){ArchipelagoClient c;c.activeLocations={10,1000,1001,1002};c.rcToApLocation={{1,10}};
 assert(c.OwnsCheck(1)&&c.OwnsCheckCached(1));
 // A connected AP client must neither steal nor send a local randomizer's checks.
 c.currentSaveIsArchipelago=false;assert(!c.OwnsCheck(1)&&!c.OwnsCheckCached(1));c.SendLocation(10);assert(sent.empty());
 c.currentSaveIsArchipelago=true;c.saveIdentityMismatch=true;c.SendLocation(10);assert(sent.empty());assert(!c.OwnsCheck(1));
 c.saveIdentityMismatch=false;c.authenticated=false;
 assert(c.ReportNpcSpeechLocation(10));assert(c.pendingLocationReports.contains(10));assert(sent.empty());
 assert(!c.ReportNpcSpeechLocation(10)); // accepted once without an ACK
 Actor first{1},second{2};assert(c.ReportFallbackNpcSpeech(&first));assert(!c.ReportFallbackNpcSpeech(&first));
 assert(c.ReportFallbackNpcSpeech(&second));assert(c.pendingLocationReports.contains(1000)&&c.pendingLocationReports.contains(1001));
 assert(c.fallbackNpcSpeechHashes.size()==2);
 auto saved=c.CaptureSaveSnapshot();ArchipelagoClient loaded;loaded.LoadPendingLocations(saved.pendingLocations);
 assert(loaded.IsLocationSubmitted(10)&&loaded.IsLocationSubmitted(1000)&&loaded.IsLocationSubmitted(1001));
 assert(loaded.reportedLocations.empty()); // queued is never a fabricated server ACK
 c.authenticated=true;auto retry=c.pendingLocationReports;c.pendingLocationReports.clear();
 for(auto id:retry)c.SendLocation(id);assert(sent.size()==3);
 c.reportedLocations.insert(10);c.pendingLocationReports.erase(10);c.SendLocation(10);assert(sent.size()==3);
 c.SendLocation(999999);assert(sent.size()==3);assert(!c.IsLocationSubmitted(999999));
 c.currentSaveIsArchipelago=false;c.LoadPendingLocations({1001});assert(c.pendingLocationReports.empty());
}
''')
run('partial_scout_recovery',common+methods+r'''
int main(){ArchipelagoClient c;for(int64_t id=1;id<=600;++id)c.activeLocations.insert(id);
 c.RequestLocationScouts();assert(c.expectedScoutCount==600&&scoutPackets.size()==3);
 for(const auto&p:scoutPackets)assert(p.size()<=256);
 for(int64_t id=1;id<=256;++id)c.scoutedLocations[id]={};
 clockValue=2;c.RequestLocationScouts();assert(scoutPackets.size()==3);
 clockValue=3;c.RequestLocationScouts();assert(scoutPackets.size()==5&&c.expectedScoutCount==600);
 size_t retryCount=0;for(size_t i=3;i<scoutPackets.size();++i)for(auto id:scoutPackets[i]){assert(id>256);++retryCount;}
 assert(retryCount==344);
 for(int64_t id=257;id<=600;++id)c.scoutedLocations[id]={};
 clockValue=6;c.RequestLocationScouts();assert(scoutPackets.size()==5&&c.expectedScoutCount==600);
 c.authenticated=false;c.scoutedLocations.clear();clockValue=12;c.RequestLocationScouts();assert(scoutPackets.size()==5);
 c.authenticated=true;c.scoutsRequested=false;c.RequestLocationScouts();assert(scoutPackets.size()==8);
}
''')
metadata=save[save.index('    SaveManager::Instance->SaveData("archipelagoMetadataVersion"'):save.index('    std::shared_ptr<Randomizer> randomizer',save.index('    SaveManager::Instance->SaveData("archipelagoMetadataVersion"'))]
run('save_snapshot_consistency',common+methods+r'''
struct Pool{std::deque<std::function<void()>>jobs;template<class F>void detach_task(F f){jobs.emplace_back(f);}}pool;
static thread_local const ArchipelagoSaveSnapshot*gSavingArchipelagoSnapshot=nullptr;
class SaveManager{public:static SaveManager*Instance;int sectionIndex=10;Pool*smThreadPool=&pool;
 nlohmann::json data;std::string arrayKey;bool inArray=false;std::vector<nlohmann::json>writes;
 template<class T>void SaveData(std::string key,T value){if(inArray)data[arrayKey].push_back(value);else data[key]=value;}
 template<class F>void SaveArray(std::string key,size_t size,F fn){data[key]=nlohmann::json::array();arrayKey=key;inArray=true;for(size_t i=0;i<size;++i)fn(i);inArray=false;}
 void SaveSection(int,int,bool);
 void SaveFileThreaded(int file,SaveContext*context,int,ArchipelagoSaveSnapshot snapshot){
 gSavingArchipelagoSnapshot=&snapshot;const bool lightweightArchipelagoSave=snapshot.active;data=nlohmann::json::object();
 data["inventory"]=context->inventory;data["file"]=file;
'''+metadata+r'''
 writes.push_back(data);delete context;gSavingArchipelagoSnapshot=nullptr;}
};SaveManager*SaveManager::Instance=nullptr;
'''+function(save,'void SaveManager::SaveSection(')+r'''
int main(){SaveManager writer;SaveManager::Instance=&writer;auto&c=ArchipelagoClient::GetInstance();
 c.appliedItemCount=1;c.pendingLocationReports={1000};c.fallbackNpcSpeechHashes={11};gSaveContext.inventory=1;
 writer.SaveSection(0,0,true);
 c.appliedItemCount=2;c.pendingLocationReports={1001};c.fallbackNpcSpeechHashes.push_back(22);gSaveContext.inventory=2;
 writer.SaveSection(0,0,true);
 // A different file can become live before either background save executes.
 c.currentSaveIsArchipelago=false;c.saveSlot="other";c.appliedItemCount=99;gSaveContext.inventory=99;
 while(!pool.jobs.empty()){auto job=pool.jobs.front();pool.jobs.pop_front();job();}
 assert(writer.writes.size()==2);
 for(size_t i=0;i<2;++i){const auto&w=writer.writes[i];assert(w["inventory"]==i+1);assert(w["archipelagoReceivedItemCount"]==i+1);
 assert(w["archipelagoSave"]==true&&w["archipelagoSlot"]=="slot");assert(w["archipelagoPendingLocations"][0]==1000+i);
 assert(w["archipelagoFallbackNpcSpeechCount"]==i+1);}
 writer.SaveSection(1,0,false);assert(writer.writes.back()["archipelagoSave"]==false);
 writer.SaveSection(0xff,0,true);assert(pool.jobs.empty());
}
''')

# Compile the production receipt gate separately from ability-specific engine flags.
major=function(ap,'void ArchipelagoClient::FinalizeMajorItemReceipt(')
major_gate=major[major.index('    if (!awaitingMajorItemReceipt)'):major.index('    // SOH-EXTREME 0.7.55:')]
run('major_receipt_identity',r'''
#include <cassert>
#include <cstdint>
#define SPDLOG_DEBUG(...) ((void)0)
constexpr int MOD_NONE=0,MOD_RANDOMIZER=1;
bool awaitingMajorItemReceipt=true;int awaitingMajorModIndex=MOD_NONE,awaitingMajorItemId=20,awaitingMajorGetItemId=45;
uint64_t awaitingMajorSequence=3;int64_t awaitingMajorApItemId=650;int commits=0;
void callback(int modIndex,int itemId,int getItemId){
'''+major_gate+r'''
 ++commits;awaitingMajorItemReceipt=false;}
int main(){callback(MOD_NONE,1,1);assert(commits==0); // incidental rupee/heart
 callback(MOD_RANDOMIZER,20,45);assert(commits==0); // different item namespace
 callback(MOD_NONE,20,99);assert(commits==1); // vanilla GetItemID alias
 callback(MOD_NONE,20,99);assert(commits==1); // callback only once
 awaitingMajorItemReceipt=true;awaitingMajorModIndex=MOD_RANDOMIZER;
 callback(MOD_RANDOMIZER,20,99);assert(commits==1);
 callback(MOD_RANDOMIZER,20,45);assert(commits==2); // capped/duplicate item is still received
}
''')

# These are integration boundaries: regression tests above would not detect a
# caller continuing to read live metadata or infer a grant from unrelated ammo.
save_body=function(save,'void SaveManager::SaveRandomizer(')
assert 'ArchipelagoClient::GetInstance()' not in save_body
assert 'if (saveContext->ship.quest.id == QUEST_RANDOMIZER)' in function(save,'void SaveManager::SaveFileThreaded(')
update=function(ap,'void ArchipelagoClient::Update()')
assert 'gAwaitingMajorStateDigestBefore' not in update
assert 'LoadPendingLocations(pendingLocations)' in save
for sig in ('void ArchipelagoClient::Enable()', 'void ArchipelagoClient::Disable()'):
 body=function(ap,sig)
 assert 'currentSaveIsArchipelago = false' not in body
 assert 'saveServer.clear()' not in body and 'saveSlot.clear()' not in body
enemy=(root/'soh/Enhancements/randomizer/MegaSouls.cpp').read_text(encoding='utf-8')
assert 'Archipelago_IsLocationActive(locationId), Archipelago_IsLocationSubmitted(locationId)' in enemy
results.append(dict(name='AP save/receipt/enemy integration boundaries',passed=True))
(out/'results.json').write_text(json.dumps(results,indent=2))
sys.exit(0 if all(r['passed'] for r in results) else 1)
