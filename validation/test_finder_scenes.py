"""Compile the real finder scene resolvers/grouping with catalogued engine data.

Uses MSVC cl and the checked-in native scene, check, NPC, and enemy catalogues.
Engine lookups are stubbed; this is not a full game build or a playthrough.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("finder_generator", ROOT / "tools/generate_finder_scenes.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    for name, content in generator.generate().items():
        assert (generator.OUTPUT / name).read_text(encoding="utf-8") == content, name
    _, _, checks, _ = generator.catalogues()
    scenes = dict(re.findall(r'/\* (0x\w+) \*/.*?\b(SCENE_\w+)',
                           (ROOT / "include/tables/scene_table.h").read_text(encoding="utf-8")))
    constants = "\n".join(f"constexpr int {name} = {number};" for number, name in scenes.items())
    constants += "\nconstexpr int SCENE_ID_MAX = 0x6E;\n"
    areas = {}
    for path in sorted(generator.NATIVE.glob("*.cpp")):
        for rc, body in re.findall(r'locationTable\[(RC_\w+)\]\s*=\s*(.*?);', path.read_text(encoding="utf-8"), re.S):
            area = re.search(r'\bRCAREA_\w+', body)
            if area:
                areas[rc] = area[0]
    location_data = "\n".join(f"{{{rc}, {{{scene}, {areas.get(rc, 'GetAreaFromScene(' + scene + ')')}}}}},"
                              for rc, scene in sorted(checks.items()))
    source = (generator.NATIVE / "randomizer_check_tracker.cpp").read_text(encoding="utf-8")
    functions = source[source.index("static SohExtreme::TrackerScene FinderScene("):
                       source.index("static void DrawUniversalFinderMirror()")]
    enemies = source[source.index("enum EnemyFinderCombat"):source.index("// NPC Speech checks are separate AP locations.")]
    location_source = (generator.NATIVE / "location.cpp").read_text(encoding="utf-8")
    area_function = location_source[location_source.index("RandomizerCheckArea GetAreaFromScene("):]
    area_function = area_function[:area_function.index("\n}\n") + 3]
    cpp = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Network/Archipelago/TrackerScenes.h"
''' + constants + area_function + r'''
constexpr int ENTRANCE_GROTTO_EXIT_START = 0x800;
namespace SohUtils {
std::string GetSceneName(int id) { return "Scene " + std::to_string(id); }
}
namespace RandomizerCheckObjects {
std::string GetRCAreaName(RandomizerCheckArea area) { return "Area " + std::to_string(area); }
}
namespace EntranceTracker {
struct Entrance { std::string source; };
const Entrance* GetEntranceData(int id) {
    static std::map<int, Entrance> values;
    return &values.try_emplace(id, Entrance{"Grotto " + std::to_string(id - 0x800)}).first->second;
}
}
namespace Rando::StaticData {
struct Location {
    int scene;
    RandomizerCheckArea area;
    int GetScene() const { return scene; }
    RandomizerCheckArea GetArea() const { return area; }
};
const std::map<RandomizerCheck, Location> locations = {
''' + location_data + r'''
};
const Location* GetLocation(RandomizerCheck rc) {
    auto found = locations.find(rc);
    return found == locations.end() ? nullptr : &found->second;
}
}
struct ArchipelagoClient {
    std::map<int64_t, int32_t> mapping;
    int32_t GetFinderNativeCheck(int64_t id) const {
        auto found = mapping.find(id);
        return found == mapping.end() ? -1 : found->second;
    }
};
struct NpcSpeechFinderEntry { int32_t rc; int64_t locationId; RandomizerGet languageItem; };
const NpcSpeechFinderEntry kNpcSpeechFinderEntries[] = {
#include "soh/Network/Archipelago/ArchipelagoSpeechFinderMap.inc"
};
''' + enemies + functions + r'''
using namespace SohExtreme;
int assertions = 0;
#define CK(test) do { ++assertions; if (!(test)) { std::cerr << "Failed line " << __LINE__ << ": " << #test << '\n'; return 1; } } while (false)
int main() {
    ArchipelagoClient client;
    const auto mido = FinderScene(SCENE_MIDOS_HOUSE, RCAREA_KOKIRI_FOREST);
    const auto forest = FinderScene(SCENE_KOKIRI_FOREST, RCAREA_KOKIRI_FOREST);
    const auto woods = FinderScene(SCENE_LOST_WOODS, RCAREA_LOST_WOODS);
    const auto kak = FinderScene(SCENE_KAKARIKO_VILLAGE, RCAREA_KAKARIKO_VILLAGE);
    const auto impa = FinderScene(SCENE_IMPAS_HOUSE, RCAREA_KAKARIKO_VILLAGE);
    const auto marketBazaar = FinderScene(SCENE_BAZAAR, RCAREA_MARKET);
    const auto kakBazaar = FinderScene(SCENE_BAZAAR, RCAREA_KAKARIKO_VILLAGE);
    const auto openGrotto = FinderScene(SCENE_GROTTOS, RCAREA_HYRULE_FIELD, GROTTO_HF_OPEN_OFFSET);
    const auto marketGrotto = FinderScene(SCENE_GROTTOS, RCAREA_HYRULE_FIELD, GROTTO_HF_NEAR_MARKET_OFFSET);
    const TrackerScene unknown;
    CK(!unknown.Matches(unknown));
    CK(!mido.Matches(forest));
    CK(!woods.Matches(kak));
    CK(!kakBazaar.Matches(marketBazaar));
    CK(!openGrotto.Matches(marketGrotto));
    CK(!FinderScene(SCENE_GROTTOS, RCAREA_HYRULE_FIELD).Matches(openGrotto));
    CK(FinderNativeScene(RC_KF_MIDOS_TOP_LEFT_CHEST).Matches(mido));
    CK(FinderNativeScene(RC_KF_MIDOS_TOP_RIGHT_CHEST).Matches(mido));
    CK(FinderNativeScene(RC_KF_MIDOS_BOTTOM_LEFT_CHEST).Matches(mido));
    CK(FinderNativeScene(RC_KF_MIDOS_BOTTOM_RIGHT_CHEST).Matches(mido));
    CK(FinderNativeScene(RC_KF_KOKIRI_SWORD_CHEST).Matches(forest));
    CK(FinderNativeScene(RC_MARKET_BAZAAR_ITEM_1).Matches(marketBazaar));
    CK(FinderNativeScene(RC_KAK_BAZAAR_ITEM_1).Matches(kakBazaar));
    CK(FinderNativeScene(RC_HF_OPEN_GROTTO_CHEST).Matches(openGrotto));
    CK(FinderNativeScene(RC_HF_NEAR_MARKET_GROTTO_CHEST).Matches(marketGrotto));
    CK(FinderNativeScene(RC_HF_OPEN_GROTTO_GRASS_1).Matches(openGrotto));
    CK(FinderNativeScene(RC_HF_FAIRY_GROTTO_FAIRY_1).Matches(
        FinderScene(SCENE_FAIRYS_FOUNTAIN, RCAREA_HYRULE_FIELD, GROTTO_HF_FAIRY_OFFSET)));
    // Moving NPCs must not make their AP parent or their other-age scene current.
    CK(FinderRowScene(10000053, client, woods, 0, 1).Matches(kak)); // Grog, child
    CK(FinderRowScene(10000053, client, kak, 1, 0).Matches(woods)); // Grog, adult
    CK(FinderRowScene(10000094, client, woods, 0, 0).Matches(forest)); // Mido, child
    CK(FinderRowScene(10000094, client, forest, 1, 0).Matches(woods)); // Mido, adult
    CK(FinderRowScene(10000000, client, impa, 0, 0).Matches(kak)); // Anju, day
    CK(FinderRowScene(10000000, client, kak, 0, 1).Matches(impa)); // Anju, night
    CK(FinderRowScene(10000066, client, mido, 1, 0).Matches(mido)); // Kokiri, adult
    CK(FinderRowScene(10000066, client, mido, 0, 0).Matches(forest)); // Kokiri, child
    CK(FinderRowScene(10000109, client, kakBazaar, 0, 0).Matches(marketBazaar));
    CK(FinderRowScene(10000109, client, marketBazaar, 1, 0).Matches(kakBazaar));
    CK(FinderRowScene(-999, client, woods, 0, 0).scene == -1);

    TrackerSnapshot snapshot;
    int64_t id = 20000000;
    for (const auto& [rc, location] : Rando::StaticData::locations) {
        client.mapping.emplace(++id, rc);
        snapshot.rows.push_back({id, uint8_t(id % 2 + 1), "Check " + std::to_string(id), "Shared AP parent"});
        const auto actual = FinderRowScene(id, client, mido, 0, 0);
        if (location.scene < SCENE_ID_MAX) CK(actual.scene == (location.scene == SCENE_TEST01 ? SCENE_BAZAAR : location.scene));
        if (location.scene == SCENE_GROTTOS || location.scene == SCENE_FAIRYS_FOUNTAIN)
            CK(actual.instance > 0 && actual.instance <= GROTTO_OFFSET_MAX);
        if (location.scene == SCENE_BAZAAR || location.scene == SCENE_SHOOTING_GALLERY ||
            location.scene == SCENE_GREAT_FAIRYS_FOUNTAIN_MAGIC || location.scene == SCENE_GREAT_FAIRYS_FOUNTAIN_SPELLS)
            CK(actual.instance > 0);
    }
    for (const auto& enemy : kEnemyDefeatFinderEntries) {
        snapshot.rows.push_back({enemy.locationId, 1, enemy.name, "Shared AP parent"});
        const auto actual = FinderRowScene(enemy.locationId, client, mido, 0, 0);
        CK(actual.scene == enemy.scene);
        if (enemy.scene == SCENE_GROTTOS) CK(actual.instance == enemy.grottoId + 1);
    }
    for (const auto& speech : kNpcSpeechFinderEntries) {
        snapshot.rows.push_back({speech.locationId, 2, "Legacy speech", "Shared AP parent"});
        CK(FinderRowScene(speech.locationId, client, woods, 0, 0).Key() == FinderNativeScene(static_cast<RandomizerCheck>(speech.rc)).Key());
    }
    const int64_t conversations[] = {
''' + ",".join(str(e["id"]) for e in json.loads((ROOT / "archipelago/soh_extreme/NpcSpeechCatalog.json").read_text(encoding="utf-8"))) + r'''
    };
    for (auto conversation : conversations) {
        snapshot.rows.push_back({conversation, 1, "Speech", "Market"});
        for (int age : {0, 1}) for (int time : {0, 1}) {
            const auto actual = FinderRowScene(conversation, client, woods, age, time);
            CK(actual.scene >= 0);
            CK(actual.instance >= 0);
        }
    }
    snapshot.rows.push_back({-999, 2, "Unknown mapping", "Lost Woods"});
    for (auto current : {mido, forest, woods, kak, marketBazaar, kakBazaar, openGrotto, marketGrotto, unknown})
    for (bool first : {false, true}) for (bool only : {false, true}) for (bool normal : {false, true}) {
        int resolutions = 0;
        auto resolver = [&](int64_t rowId) { ++resolutions; return FinderRowScene(rowId, client, current, 0, 0); };
        auto groups = GroupTrackerRowsByScene(snapshot, current, first, only, resolver,
            [&](const TrackerRow& row, const TrackerScene&) { return !normal || row.state == 1; });
        CK(resolutions == snapshot.rows.size());
        std::set<int64_t> seen;
        bool passedCurrent = false;
        for (const auto& group : groups) {
            if (!group.currentScene) passedCurrent = true;
            if (group.currentScene && first) CK(!passedCurrent);
            int inLogic = 0, glitched = 0;
            const TrackerRow* previous = nullptr;
            for (const auto* row : group.rows) {
                CK(seen.insert(row->id).second);
                const auto expected = FinderRowScene(row->id, client, current, 0, 0);
                CK(expected.Key() == group.scene.Key());
                CK(group.currentScene == expected.Matches(current));
                if (only) CK(group.currentScene);
                if (normal) CK(row->state == 1);
                if (row->state == 1) ++inLogic; else ++glitched;
                if (previous) CK(previous->state < row->state || (previous->state == row->state &&
                    (previous->name < row->name || (previous->name == row->name && previous->id < row->id))));
                previous = row;
            }
            CK(inLogic == group.normal && glitched == group.glitched);
        }
        for (const auto& row : snapshot.rows) {
            const bool expected = (!normal || row.state == 1) &&
                (!only || FinderRowScene(row.id, client, current, 0, 0).Matches(current));
            CK(bool(seen.count(row.id)) == expected);
        }
    }
    // Search can match the physical scene label even if the AP parent differs.
    auto result = GroupTrackerRowsByScene(snapshot, mido, true, false,
        [&](int64_t rowId) { return FinderRowScene(rowId, client, mido, 0, 0); },
        [&](const TrackerRow&, const TrackerScene& scene) { return scene.name == mido.name; });
    CK(result.size() == 1 && result[0].currentScene && result[0].rows.size() >= 4);
    std::cout << assertions << " assertions; " << snapshot.rows.size() << " catalogue rows passed\n";
}
'''
    file = output / "finder_scenes.cpp"
    file.write_text(cpp, encoding="utf-8")
    exe = output / "finder_scenes.exe"
    compiled = subprocess.run(["cl", "/nologo", "/EHsc", "/std:c++20", "/Zc:preprocessor", "/I" + str(ROOT), str(file),
                               "/Fo" + str(output / "finder_scenes.obj"), "/Fe" + str(exe)], capture_output=True, text=True)
    tested = subprocess.run([str(exe)], capture_output=True, text=True) if compiled.returncode == 0 else None
    report = dict(passed=compiled.returncode == 0 and tested.returncode == 0,
                  native_checks=len(checks), generated_tables_current=True,
                  output=compiled.stdout + compiled.stderr + (tested.stdout + tested.stderr if tested else ""),
                  scope=__doc__)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report["output"][:8000])
    raise SystemExit(not report["passed"])


if __name__ == "__main__":
    main()
