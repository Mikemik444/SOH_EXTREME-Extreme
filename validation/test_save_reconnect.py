"""Exercise production save loading, connection reconciliation and settings delivery.

Engine/network services are controlled adapters; the functions under test are
extracted unchanged from ArchipelagoClient.cpp. Run in a VS x64 developer shell.
"""
from pathlib import Path
import argparse,json,subprocess
from run_native_tests import function
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent)
p.add_argument('--include-dir',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();r=a.source_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
ap=(r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
code=r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <climits>
#include <cstdint>
#include <deque>
#include <iostream>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <nlohmann/json.hpp>
#include "soh/Network/Archipelago/ArchipelagoSaveSnapshot.h"
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_ERROR(...) ((void)0)
#define SPDLOG_WARN(...) ((void)0)
#define SPDLOG_DEBUG(...) ((void)0)
#define CVAR_REMOTE_ARCHIPELAGO(x) x
std::unordered_map<std::string,std::string> config;
const char* CVarGetString(const char* name,const char*) {return config[name].c_str();}
struct {struct {struct {struct {struct {int triforcePiecesCollected=0;}randomizer;}data;}quest;}ship;int fileNum=0;}gSaveContext;
int saves=0;void Save_SaveFile(){++saves;}
std::deque<int64_t>gDeferredLocationReports;
size_t gNewSaveReplayTargetCount=0;int gNewSaveReplayGraceFrames=0,gAwaitingMajorFrames=0;
const int RO_FISHSANITY_POND=1,RO_FISHSANITY_BOTH=3;
class ArchipelagoClient {public:
 std::mutex queueMutex;std::atomic_bool enabled=true,slotSettingsPendingApply=false;
 bool authenticated=true,currentSaveIsArchipelago=true,saveIdentityMismatch=false,saveRuntimeSynchronized=false;
 bool newSaveReplayPending=false,awaitingMajorItemReceipt=false,saveMetadataLoaded=false,goalReported=false;
 bool slotSettingsLoaded=false,wasAuthenticated=false,gameplay=true;
 uint64_t appliedItemCount=0,awaitingMajorSequence=0;int64_t awaitingMajorApItemId=0;
 std::string saveServer,saveSlot,cachedSlotSettingsJson,connectedServer,connectedSlot,connectedPassword,connectedSettingsJson;
 std::string saveConnectionStatus;
 SohExtreme::SaveConnectionIdentity saveConnectionIdentity,connectedIdentity;
 SohExtreme::SaveConnectionDecision saveConnectionDecision=SohExtreme::SaveConnectionDecision::Waiting;
 std::unordered_map<std::string,std::string>pendingSlotData;
 std::unordered_map<std::string,int>slotSettings;
 std::unordered_set<int64_t>pendingLocationReports,reportedLocations;
 std::vector<uint64_t>fallbackNpcSpeechHashes;
 std::vector<int64_t>receivedItemSnapshot;
 struct Item{int64_t id;bool notify;uint64_t sequence;};std::deque<Item>pendingItems;
 bool deathLinkEnabled=false,trapLinkEnabled=false,kakarikoGateOpen=false;
 int resets=0,applies=0;std::unordered_map<std::string,int>appliedSettings;
 bool IsAuthenticated()const{return authenticated;}
 bool IsGameplaySessionActive()const{return gameplay&&currentSaveIsArchipelago&&!saveIdentityMismatch;}
 void ResetFinderMirror(){++resets;}
 void ResetRemotePresentations(){}
 void ApplySlotSettings(){++applies;appliedSettings=slotSettings;}
 void SetShopPricesFromJson(const std::string&){}
 void SetActiveLocationsFromJson(const std::string&){}
 void SetLocationNameMapFromJson(const std::string&){}
 bool ConnectionSettingsChanged()const;
 void SetConnectionIdentityFromJson(const std::string&);
 void ReconcileSaveConnection(bool confirmLegacy=false);
 bool CanConfirmLegacyReconnect()const;void ConfirmLegacyReconnect();std::string GetReconnectTarget()const;
 void SetSlotSettingsFromJson(const std::string&);void DrainSlotData();
 void LoadSaveMetadata(bool,uint64_t,const std::string&,const std::string&,const std::string&,const SohExtreme::SaveConnectionIdentity& identity={});
 ArchipelagoSaveSnapshot CaptureSaveSnapshot()const;
};
'''
for sig in ['static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& out) {', 'bool ArchipelagoClient::ConnectionSettingsChanged()',
 'void ArchipelagoClient::SetConnectionIdentityFromJson(', 'void ArchipelagoClient::ReconcileSaveConnection(',
 'bool ArchipelagoClient::CanConfirmLegacyReconnect()', 'std::string ArchipelagoClient::GetReconnectTarget()',
 'void ArchipelagoClient::ConfirmLegacyReconnect()', 'void ArchipelagoClient::SetSlotSettingsFromJson(',
 'void ArchipelagoClient::DrainSlotData()', 'void ArchipelagoClient::LoadSaveMetadata(',
 'ArchipelagoSaveSnapshot ArchipelagoClient::CaptureSaveSnapshot()']:
 code+='\n'+function(ap,sig)
code+=r'''
int assertions=0;
#define CHECK(x) do{++assertions;if(!(x)){std::cerr<<"Failed line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
int main(){
 using Identity=SohExtreme::SaveConnectionIdentity;
 using D=SohExtreme::SaveConnectionDecision;
 const Identity saved{"original-seed",2,3};
 // Addresses, schemes and drives are not a generated game's identity.
 for(const auto&address: {"archipelago.gg:58419","wss://archipelago.gg:60000","new.example:1234","localhost:38281"}){
  CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old:53286",saved,"Player",address,true)==D::Ready);
 }
 CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old",{"different",2,3},"Player","old",true)==D::WrongSeed);
 CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old",{"original-seed",0,3},"Player","new",true)==D::WrongSlot);
 CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old",{"original-seed",2,4},"Player","new",true)==D::WrongSlot);
 CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old",saved,"Other","new",true)==D::WrongSlot);
 CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old",{},"Player","new",true)==D::Waiting);
 CHECK(SohExtreme::CompareSaveConnection(saved,"Player","old",saved,"Player","new",false)==D::Waiting);
 CHECK(SohExtreme::CompareSaveConnection({},"Player","old",saved,"Player","new",true)==D::ConfirmLegacy);
 CHECK(SohExtreme::CompareSaveConnection({},"Player","old",saved,"Player","old",true)==D::Ready);
 // Loading online preserves the cursor and queues only unseen receipts.
 ArchipelagoClient c;c.connectedIdentity=saved;c.connectedServer="new:58419";c.connectedSlot="Player";
 c.connectedSettingsJson=R"({"Climb":1,"FlowOfTime":0})";c.receivedItemSnapshot={101,102,103,104};
 c.LoadSaveMetadata(true,2,"old:53286","Player",R"({"Climb":0,"FlowOfTime":0})",saved);
 CHECK(!c.saveIdentityMismatch&&c.saveServer=="new:58419");
 CHECK(c.appliedItemCount==2&&c.pendingItems.size()==2&&c.pendingItems.front().sequence==2);
 CHECK(c.applies==1&&c.appliedSettings.at("Climb")==1&&c.appliedSettings.at("FlowOfTime")==0);
 auto snap=c.CaptureSaveSnapshot();CHECK(snap.identity.seed==saved.seed&&snap.identity.team==2&&snap.identity.slot==3);
 CHECK(snap.server=="new:58419"&&snap.receivedItemCount==2);
 int resets=c.resets;c.ReconcileSaveConnection();CHECK(c.resets==resets);
 // Offline load must restore its own settings and receipt cursor immediately.
 c.authenticated=false;c.connectedSettingsJson=R"({"Climb":99})";
 c.LoadSaveMetadata(true,3,"old:53286","Player",R"({"Climb":0,"FlowOfTime":1})",saved);
 CHECK(c.saveIdentityMismatch&&c.appliedItemCount==3&&c.pendingItems.size()==1);
 CHECK(c.appliedSettings.at("Climb")==0&&c.appliedSettings.at("FlowOfTime")==1);
 CHECK(c.CaptureSaveSnapshot().settingsJson==R"({"Climb":0,"FlowOfTime":1})");
 // Wrong-room metadata cannot overwrite a loaded save's settings or identity.
 c.authenticated=true;c.connectedIdentity={"wrong-seed",2,3};
 c.pendingSlotData["extreme_soh_cvars"]=R"({"Climb":99,"FlowOfTime":99})";c.DrainSlotData();
 CHECK(c.saveIdentityMismatch&&c.saveConnectionDecision==D::WrongSeed);
 CHECK(c.slotSettings.at("Climb")==0&&c.CaptureSaveSnapshot().identity.seed==saved.seed);
 CHECK(c.CaptureSaveSnapshot().settingsJson==R"({"Climb":0,"FlowOfTime":1})");
 CHECK(!c.CanConfirmLegacyReconnect());c.ConfirmLegacyReconnect();CHECK(saves==0&&c.appliedItemCount==3);
 // Loading with wrong live data already present still applies the saved rules.
 c.LoadSaveMetadata(true,2,"old:53286","Player",R"({"Climb":0,"FlowOfTime":1})",saved);
 CHECK(c.saveIdentityMismatch&&c.appliedSettings.at("Climb")==0&&c.applies==3);
 // An old file moved to another endpoint requires one explicit confirmation.
 c.connectedIdentity=saved;c.connectedSettingsJson=R"({"Climb":1,"FlowOfTime":0})";
 c.LoadSaveMetadata(true,3,"old:53286","Player",R"({"Climb":0,"FlowOfTime":1})");
 CHECK(c.CanConfirmLegacyReconnect()&&c.appliedSettings.at("Climb")==0);
 c.pendingLocationReports={41,42};c.fallbackNpcSpeechHashes={55};c.ConfirmLegacyReconnect();
 CHECK(!c.saveIdentityMismatch&&saves==1&&c.appliedItemCount==3&&c.pendingItems.size()==1);
 CHECK(c.pendingLocationReports.size()==2&&c.fallbackNpcSpeechHashes.size()==1);
 CHECK(c.saveConnectionIdentity.Valid()&&c.saveConnectionIdentity.seed==saved.seed);
 CHECK(c.saveServer==c.connectedServer&&c.cachedSlotSettingsJson==c.connectedSettingsJson);
 c.ConfirmLegacyReconnect();CHECK(saves==1); // once; cannot override a future mismatch
 // Next move is automatic, including after saving and reloading the identity.
 snap=c.CaptureSaveSnapshot();c.connectedServer="another-host:60000";
 c.LoadSaveMetadata(true,snap.receivedItemCount,snap.server,snap.slot,snap.settingsJson,snap.identity);
 CHECK(!c.saveIdentityMismatch&&c.saveServer=="another-host:60000"&&c.appliedItemCount==3);
 // Callback ordering: identity is handled before settings regardless of map order.
 c.pendingSlotData["extreme_soh_cvars"]=R"({"Climb":7})";
 c.pendingSlotData["_soh_connection_identity"]=R"({"name":"Player","seed":"wrong-seed","slot":3,"team":2})";
 c.DrainSlotData();CHECK(c.saveIdentityMismatch&&c.slotSettings.at("Climb")==1);
 CHECK(c.appliedItemCount==3&&c.CaptureSaveSnapshot().identity.seed==saved.seed);
 c.pendingSlotData["_soh_connection_identity"]=R"({"name":"Player","seed":"original-seed","slot":3,"team":2})";
 c.pendingSlotData["extreme_soh_cvars"]=R"({"Climb":2})";c.DrainSlotData();
 CHECK(!c.saveIdentityMismatch&&c.slotSettings.at("Climb")==2&&c.appliedItemCount==3);
 CHECK(!c.wasAuthenticated&&!c.saveRuntimeSynchronized); // services resync after automatic handshake
 // Pre-ID saves at their existing endpoint upgrade without a confirmation.
 c.LoadSaveMetadata(true,3,c.connectedServer,"Player",R"({"Climb":0})");
 CHECK(!c.saveIdentityMismatch&&c.saveConnectionIdentity.Valid());
 // A local randomizer file is never adopted as an AP file by authentication.
 c.LoadSaveMetadata(false,0,"","","{}");c.ReconcileSaveConnection();
 CHECK(!c.currentSaveIsArchipelago&&!c.CaptureSaveSnapshot().active);
 // Invalid metadata must wait, not throw or adopt a guessed identity.
 for(auto raw:{"null","{}",R"({"name":7})",R"({"name":"Player","seed":"x","slot":0,"team":0})"}){
  c.SetConnectionIdentityFromJson(raw);CHECK(!c.connectedIdentity.Valid());
 }
 // UI editing changes the reconnect action, not the live worker's credentials.
 c.connectedServer="old:1";c.connectedSlot="Player";c.connectedPassword="secret";
 config={{"ServerAddress","old:1"},{"SlotName","Player"},{"Password","secret"}};
 CHECK(!c.ConnectionSettingsChanged());config["ServerAddress"]="new:2";CHECK(c.ConnectionSettingsChanged());
 CHECK(c.connectedServer=="old:1"&&c.connectedPassword=="secret");
 std::cout<<assertions<<" production reconnect assertions passed\n";
}
'''
src=out/'save_reconnect.cpp';src.write_text(code,encoding='utf-8')
exe=out/'save_reconnect.exe'
build=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(r),'/I',str(r/'soh/Network/Archipelago'),'/I',str(a.include_dir.resolve()),str(src),'/Fo'+str(out/'save_reconnect.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
(out/'native.log').write_text(log)
passed=build.returncode==0 and run.returncode==0
report={'passed':passed,'build_exit':build.returncode,'test_exit':run.returncode if run else None,'output':run.stdout if run else '',
 'scope':'Production functions with controlled engine/network services; no live gameplay test.'}
# Verify production call sites keep verification ahead of all gameplay services.
update=function(ap,'void ArchipelagoClient::Update()')
assert update.index('ReconcileSaveConnection();')<update.index('ServiceFinderWorker();')<update.index('if (!currentSaveIsArchipelago || saveIdentityMismatch)')
finder=function(ap,'const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot(')
assert finder.index('if (saveIdentityMismatch)')<finder.index('finderMirror.Current(')
worker=function(ap,'void ArchipelagoClient::ServiceFinderWorker()')
assert 'connectedServer.c_str()' in worker and 'connectedPassword.c_str()' in worker
(out/'native.json').write_text(json.dumps(report,indent=2))
print(log[-6500:]);raise SystemExit(0 if passed else 1)
