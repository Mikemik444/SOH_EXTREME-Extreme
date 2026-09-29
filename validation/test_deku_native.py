"""Compile production combat and AP finder methods with controlled engine/network services.
Run in an MSVC x64 developer terminal, then pass --native-exe to test_deku_logic.py.
"""
from pathlib import Path
from run_native_tests import function
import argparse, subprocess, json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent.parent)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); root=a.source_root.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
tracker=(root/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text()
client=(root/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text()
enums=tracker[tracker.index('enum EnemyFinderCombat'):tracker.index('// NPC Speech checks are separate AP locations.')]
combat='\n'.join(function(tracker,s) for s in ('static bool EnemyFinderMelee(', 'static bool EnemyFinderRanged(', 'static bool EnemyFinderCombatReachable('))
code=r'''
#include <cassert>
#include <cstdint>
#include <set>
#include <vector>
#include <mutex>
#include <fstream>
#include <iostream>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Network/Archipelago/TrackerMirror.h"
namespace Rando { struct Logic {
 std::set<RandomizerGet> usable;
 bool CanUse(RandomizerGet i){return usable.count(i)!=0;}
 bool HasExplosives(){return CanUse(RG_BOMB_BAG);}
 bool CanReflectNuts(){return CanUse(RG_DEKU_SHIELD);}
}; }
'''+enums+combat+r'''
// Match Inventory.equipment bit layout; equipped shield is deliberately absent.
constexpr int EQUIP_TYPE_SHIELD=1,EQUIP_INV_SHIELD_DEKU=0,EQUIP_INV_SHIELD_HYLIAN=1;
struct {struct {uint16_t equipment=0;} inventory;} gSaveContext;
#define CHECK_OWNED_EQUIP(equip,value) ((1u << ((equip)*4+(value))) & gSaveContext.inventory.equipment)
struct AP_Bounce {std::vector<std::string>*tags;std::string data;};
std::string sent;
void AP_SendBounce(const AP_Bounce& b){sent=b.data;}
int AP_GetPlayerID(){return 1;}
double FinderMirrorClock(){return 100;}
class ArchipelagoClient { public:
 bool currentSaveIsArchipelago=true,activeLocationsLoaded=true,finderWorkerStarted=true;
 bool IsAuthenticated(){return true;}
 std::mutex queueMutex;
 std::string pendingFinderPayload,pendingFinderNonce,finderMirrorError,finderWorkerError;
 uint64_t incomingItemOrdinal=0;double finderNextRequest=0;
 std::set<int64_t> activeLocations,reportedLocations;
 SohExtreme::TrackerMirrorState finderMirror;
 const SohExtreme::TrackerSnapshot* GetFinderSnapshot(std::string&);
};
'''+function(client,'const SohExtreme::TrackerSnapshot* ArchipelagoClient::GetFinderSnapshot(')+r'''
int main(int argc,char**argv){
 Rando::Logic logic;
 for(auto weapon:{RG_STICKS,RG_MEGATON_HAMMER,RG_FAIRY_SLINGSHOT,RG_FAIRY_BOW,RG_BOMB_BAG,RG_HOOKSHOT,RG_DINS_FIRE}){
  logic.usable={weapon};assert(!EnemyFinderCombatReachable(&logic,EFC_SWORD_OR_BOOMERANG));
 }
 for(auto weapon:{RG_KOKIRI_SWORD,RG_MASTER_SWORD,RG_BIGGORON_SWORD,RG_GIANTS_KNIFE,RG_BOOMERANG}){
  logic.usable={weapon};assert(EnemyFinderCombatReachable(&logic,EFC_SWORD_OR_BOOMERANG));
 }
 logic.usable={RG_STICKS};assert(EnemyFinderCombatReachable(&logic,EFC_MELEE));
 unsigned withered=0;
 for(const auto&e:kEnemyDefeatFinderEntries){
  if(e.actorId==199){++withered;assert(e.combat==EFC_SWORD_OR_BOOMERANG);}
  if(e.actorId==85)assert(e.combat==EFC_MELEE);
 }assert(withered==10);
 if(argc==1){std::cout<<"PASS native Baba combat and catalog\n";return 0;}
 assert(argc==3);unsigned owned=std::stoul(argv[2]);assert(owned<=3);
 std::ifstream file(argv[1]);std::string payload((std::istreambuf_iterator<char>(file)),{});
 auto snapshot=SohExtreme::DecodeTrackerSnapshot(payload);assert(snapshot.liveShields==owned);
 ArchipelagoClient c;c.finderMirror.Reset(snapshot.nonce);
 c.activeLocations=snapshot.active;c.reportedLocations=snapshot.checked;c.incomingItemOrdinal=snapshot.received;
 for(uint64_t i=0;i<snapshot.request;++i)c.finderMirror.NextRequest();
 c.pendingFinderPayload=payload;c.pendingFinderNonce=snapshot.nonce;std::string status;
 gSaveContext.inventory.equipment=owned<<4;
 assert(c.GetFinderSnapshot(status)!=nullptr);
 assert(sent.find("\"live_shields\":"+std::to_string(owned))!=std::string::npos);
 // Losing OR buying a shield invalidates the previous snapshot before a new
 // response arrives; unrelated sword/tunic equipment does not.
 gSaveContext.inventory.equipment^=0x10;
 assert(c.GetFinderSnapshot(status)==nullptr);
 gSaveContext.inventory.equipment^=0x10;
 gSaveContext.inventory.equipment|=0x101;
 assert(c.GetFinderSnapshot(status)!=nullptr);
 auto bad=snapshot;bad.version="0.11.22";bad.revision++;
 assert(!c.finderMirror.Accept(bad,1,100,status));
 c.incomingItemOrdinal++;assert(c.GetFinderSnapshot(status)==nullptr);
 c.incomingItemOrdinal--;c.currentSaveIsArchipelago=false;assert(c.GetFinderSnapshot(status)==nullptr);
 std::cout<<"PASS callback payload, live equipment request, stale shield/receipt/save/version guards\n";
}
'''
src=out/'deku_native.cpp'; exe=out/'deku_native.exe'; src.write_text(code)
build=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD','/I',str(root),str(src),
                      '/Fo'+str(out/'deku_native.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
log=build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
(out/'native.log').write_text(log)
passed=build.returncode==0 and run.returncode==0
(out/'native.json').write_text(json.dumps(dict(passed=passed,build_exit=build.returncode,run_exit=run.returncode if run else None,log=log),indent=2))
print(log[-4000:]);raise SystemExit(0 if passed else 1)
