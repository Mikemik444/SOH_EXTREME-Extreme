"""Compile the actual tracker metadata, sorting, and grouping with engine IO stubbed.

Native scene metadata is a small explicit fixture. AP endpoint definitions,
tracker enums/structures, and every tested function are read from this checkout.
Run with Python and an available C++20 compiler; no game assets are needed.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
s = (root / "soh/Enhancements/randomizer/randomizer_entrance_tracker.cpp").read_text(encoding="utf-8-sig")
h = (root / "soh/Enhancements/randomizer/randomizer_entrance_tracker.h").read_text(encoding="utf-8-sig")
entrance_header = (root / "soh/Enhancements/randomizer/randomizer_entrance.h").read_text(encoding="utf-8-sig")
capacity = re.search(r"^#define ENTRANCE_OVERRIDES_MAX_COUNT\s+\d+[^\r\n]*", entrance_header, re.MULTILINE)
if capacity is None:
    raise SystemExit("The production entrance capacity definition was not found.")
types=h[h.index('typedef enum {'):h.index('static std::map')]
def block(a,b): return s[s.index(a):s.index(b,s.index(a))]
source='''#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <vector>
#include "soh/Network/Archipelago/EntranceRouting.h"
using s16=int16_t; using u8=uint8_t;
#define ARRAY_COUNT(x) (sizeof(x)/sizeof((x)[0]))
#define SPDLOG_WARN(...) ((void)0)
'''+capacity.group(0)+'\n'+types+'''
struct EntranceOverride { uint16_t type; int16_t index,destination,override,overrideDestination; };
constexpr int RSK_SHUFFLE_ENTRANCES=0;
static const EntranceOverride emptyOverride={0};
EntranceOverride srcListSortedByArea[ENTRANCE_OVERRIDES_MAX_COUNT]{},destListSortedByArea[ENTRANCE_OVERRIDES_MAX_COUNT]{},srcListSortedByType[ENTRANCE_OVERRIDES_MAX_COUNT]{},destListSortedByType[ENTRANCE_OVERRIDES_MAX_COUNT]{};
EntranceTrackingData gEntranceTrackingData{};
struct Shuffler { std::array<EntranceOverride,ENTRANCE_OVERRIDES_MAX_COUNT> entranceOverrides{}; } nativeRoutes;
namespace Rando { struct Context { static Context* GetInstance() { static Context c; return &c; } Shuffler* GetEntranceShuffler() { return &nativeRoutes; } }; }
struct Randomizer { int GetRandoSettingValue(int) { return 1; } } randomizer;
struct Globals { Randomizer* gRandomizer=&randomizer; } globals;
struct OTRGlobals { static inline Globals* Instance=&globals; };
bool Archipelago_EntranceShuffleActive() { return true; }
int Entrance_EntranceIsNull(EntranceOverride* e) { return e->index==0 && e->destination==0 && e->override==0 && e->overrideDestination==0; }
// Small native metadata fixture. The production fallback and sorting functions
// below are extracted verbatim from the edited source.
const EntranceData entranceData[]={
 {187,-1,{{52,-1}},"Child Spawn","Link's House",ENTRANCE_GROUP_ONE_WAY,ENTRANCE_GROUP_ONE_WAY,ENTRANCE_TYPE_ONE_WAY,"",1},
 {642,-1,{{67,-1}},"Adult Spawn","Temple of Time",ENTRANCE_GROUP_ONE_WAY,ENTRANCE_GROUP_ONE_WAY,ENTRANCE_TYPE_ONE_WAY,"",1},
 {521,0,{{0,-1}},"Deku Tree","Kokiri Forest",ENTRANCE_GROUP_KOKIRI_FOREST,ENTRANCE_GROUP_KOKIRI_FOREST,ENTRANCE_TYPE_DUNGEON,"",1},
 {578,4,{{1,-1}},"Dodongos","DMT",ENTRANCE_GROUP_DEATH_MOUNTAIN_TRAIL,ENTRANCE_GROUP_DEATH_MOUNTAIN_TRAIL,ENTRANCE_TYPE_DUNGEON,"",1},
 {545,40,{{2,-1}},"Jabu","ZF",ENTRANCE_GROUP_ZORAS_FOUNTAIN,ENTRANCE_GROUP_ZORAS_FOUNTAIN,ENTRANCE_TYPE_DUNGEON,"",1},
 {533,361,{{3,-1}},"Forest","SFM",ENTRANCE_GROUP_SFM,ENTRANCE_GROUP_SFM,ENTRANCE_TYPE_DUNGEON,"",1},
 {586,357,{{4,-1}},"Fire","DMC",ENTRANCE_GROUP_DEATH_MOUNTAIN_CRATER,ENTRANCE_GROUP_DEATH_MOUNTAIN_CRATER,ENTRANCE_TYPE_DUNGEON,"",1},
 {541,16,{{5,-1}},"Water","LH",ENTRANCE_GROUP_LAKE_HYLIA,ENTRANCE_GROUP_LAKE_HYLIA,ENTRANCE_TYPE_DUNGEON,"",1},
 {481,130,{{6,-1}},"Spirit","Colossus",ENTRANCE_GROUP_DESERT_COLOSSUS,ENTRANCE_GROUP_DESERT_COLOSSUS,ENTRANCE_TYPE_DUNGEON,"",1},
 {517,55,{{7,-1}},"Shadow","GY",ENTRANCE_GROUP_GRAVEYARD,ENTRANCE_GROUP_GRAVEYARD,ENTRANCE_TYPE_DUNGEON,"",1},
 {678,152,{{8,-1}},"Well","Kak",ENTRANCE_GROUP_KAKARIKO,ENTRANCE_GROUP_KAKARIKO,ENTRANCE_TYPE_DUNGEON,"",1},
 {980,136,{{9,-1}},"Ice","ZF",ENTRANCE_GROUP_ZORAS_FOUNTAIN,ENTRANCE_GROUP_ZORAS_FOUNTAIN,ENTRANCE_TYPE_DUNGEON,"",1},
 {2000,2001,{{10,-1}},"Tower","Castle",ENTRANCE_GROUP_HYRULE_CASTLE,ENTRANCE_GROUP_HYRULE_CASTLE,ENTRANCE_TYPE_DUNGEON,"",1},
 {936,8,{{11,-1}},"GTG","GF",ENTRANCE_GROUP_GERUDO_FORTRESS,ENTRANCE_GROUP_GERUDO_FORTRESS,ENTRANCE_TYPE_DUNGEON,"",1},
 {561,1158,{{12,-1}},"Hideout","GF",ENTRANCE_GROUP_GERUDO_FORTRESS,ENTRANCE_GROUP_GERUDO_FORTRESS,ENTRANCE_TYPE_FORTRESS,"",1},
 {573,1127,{{13,-1}},"Inside Castle","Castle",ENTRANCE_GROUP_HYRULE_CASTLE,ENTRANCE_GROUP_HYRULE_CASTLE,ENTRANCE_TYPE_DUNGEON,"",1},
 {469,99,{{16,-1}},"TCG","Market",ENTRANCE_GROUP_MARKET,ENTRANCE_GROUP_MARKET,ENTRANCE_TYPE_INTERIOR,"",1}
};
'''+block('static const EntranceData* GetNativeEntranceData(', 'void LoadFromPreset(')+block('static size_t EntranceDisplayOrder(', 's16 GetLastEntranceOverride()')+block('void InitEntranceTrackingData()', 'void EntranceTrackerSettingsWindow::DrawElement()')+'''
int main() {
  size_t doors=0;
  std::vector<int16_t> targets;
  for(const auto& e:SohExtreme::kEntranceEndpoints) {
    const auto* data=GetEntranceData(e.id);
    assert(data && data->index==e.id && data->reverseIndex==e.reverse);
    assert(!data->source.empty() && !data->destination.empty());
    assert(data->srcGroup<SPOILER_ENTRANCE_GROUP_COUNT && data->dstGroup<SPOILER_ENTRANCE_GROUP_COUNT);
    assert(data->type<ENTRANCE_TYPE_COUNT);
    if(e.door>=0) {
      ++doors; targets.push_back(e.id);
      assert(data->type==ENTRANCE_TYPE_ROOM_DOOR);
      assert(data->source.find("(door ")!=std::string::npos);
      assert(data->destination.find("(door ")!=std::string::npos);
      assert(data->srcGroup!=ENTRANCE_GROUP_OTHER);
    }
  }
  assert(!GetEntranceData(32000));
  assert(doors==421);
  std::cout << "PASS: all 721 catalog endpoints resolve; all 421 door labels and area/type bounds validated.\\n";
  size_t routeCount=0;
  for(const auto& e:SohExtreme::kEntranceEndpoints) {
    if(e.door>=0) continue;
    assert(routeCount<nativeRoutes.entranceOverrides.size());
    const auto* target=SohExtreme::EntranceEndpointById(targets[routeCount%targets.size()]);
    nativeRoutes.entranceOverrides[routeCount++]={0,static_cast<int16_t>(e.id),static_cast<int16_t>(e.reverse),static_cast<int16_t>(target->id),static_cast<int16_t>(target->reverse)};
  }
  assert(routeCount==300 && routeCount<ENTRANCE_OVERRIDES_MAX_COUNT);
  // Both one-way spawns deliberately share the same synthetic destination.
  for(auto& route:nativeRoutes.entranceOverrides) {
    if(route.index==187 || route.index==642) { route.override=8961; route.overrideDestination=8960; }
  }
  InitEntranceTrackingData();
  assert(gEntranceTrackingData.EntranceCount==routeCount);
  std::set<std::pair<int16_t,int16_t>> expected;
  for(auto& e:nativeRoutes.entranceOverrides) {
    if(!Entrance_EntranceIsNull(&e)) expected.emplace(e.index,e.override);
  }
  assert(expected.size()==routeCount);
  EntranceOverride* lists[]={srcListSortedByArea,destListSortedByArea,srcListSortedByType,destListSortedByType};
  for(int k=0;k<4;++k) {
    const auto grouping=static_cast<TrackerEntranceGroupingType>(k);
    std::set<std::pair<int16_t,int16_t>> actual;
    for(size_t i=0;i<routeCount;++i) {
      actual.emplace(lists[k][i].index,lists[k][i].override);
      if(i) assert(EntranceGroup(lists[k][i-1],grouping)<=EntranceGroup(lists[k][i],grouping));
    }
    for(size_t i=routeCount;i<ENTRANCE_OVERRIDES_MAX_COUNT;++i)
      assert(Entrance_EntranceIsNull(&lists[k][i]));
    assert(expected==actual);
    size_t total=0;
    const size_t groups=k>=2?static_cast<size_t>(ENTRANCE_TYPE_COUNT):static_cast<size_t>(SPOILER_ENTRANCE_GROUP_COUNT);
    for(size_t g=0;g<groups;++g) {
      assert(gEntranceTrackingData.GroupOffsets[k][g]==total);
      for(size_t i=0;i<gEntranceTrackingData.GroupEntranceCounts[k][g];++i)
        assert(EntranceGroup(lists[k][total+i],grouping)==g);
      total+=gEntranceTrackingData.GroupEntranceCounts[k][g];
    }
    assert(total==routeCount);
  }
  std::cout << "PASS: all 300 indexed routes retained in all four groupings; duplicate one-way targets preserved; offsets and counts agree.\\n";
  nativeRoutes.entranceOverrides.fill({});
  nativeRoutes.entranceOverrides[0]={0,32000,32001,32002,32003};
  InitEntranceTrackingData();
  assert(gEntranceTrackingData.EntranceCount==0);
  std::cout << "PASS: unknown endpoints skipped safely; stale arrays cleared on rebuild.\\n";
}
'''
def main():
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler (g++ or c++) is required for this regression test.")
    with tempfile.TemporaryDirectory(prefix="soh-entrance-tracker-test-") as directory:
        work = Path(directory)
        translation_unit = work / "entrance_tracker_tests.cpp"
        translation_unit.write_text(source, encoding="utf-8")
        executable = work / "entrance_tracker_tests"
        subprocess.run([
            compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wno-missing-field-initializers", "-I", str(root),
            str(translation_unit), "-o", str(executable),
        ], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
