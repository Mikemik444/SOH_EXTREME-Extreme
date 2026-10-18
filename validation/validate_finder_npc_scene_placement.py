"""Narrow compiled source-fragment proof for the final moving-NPC scene filter."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
TESTS = ROOT / "tests"
FINDER = "soh/Enhancements/randomizer/randomizer_check_tracker.cpp"
MIDO = "src/overlays/actors/ovl_En_Md/z_en_md.c"
TALON = "src/overlays/actors/ovl_En_Ta/z_en_ta.c"
SCENES = "soh/Network/Archipelago/NpcSpeechScenes.inc"
PRIORITY = "soh/Network/Archipelago/TrackerScenes.h"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def function(text, signature):
    start = text.index(signature)
    brace = text.index("{", start)
    while ";" in text[start:brace]:
        start = text.index(signature, start + len(signature))
        brace = text.index("{", start)
    depth = 0
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|[{}]')
    for token in tokens.finditer(text, brace):
        if token[0] == "{":
            depth += 1
        elif token[0] == "}":
            depth -= 1
            if depth == 0:
                return text[start:token.end()]
    raise AssertionError(signature)


finder = (SOURCE / FINDER).read_text()
mido = (SOURCE / MIDO).read_text()
talon = (SOURCE / TALON).read_text()
helper = function(finder, "static bool FinderNpcSpeechScenePresent(")
native_mido = function(mido, "u8 EnMd_ShouldSpawn(")
native_talon = function(talon, "void EnTa_Init(")
priority = function((SOURCE / PRIORITY).read_text(), "inline int TrackerSceneRoutePriority(")


def talon_guards(anchor, condition, next_branch):
    start = native_talon.index(condition, native_talon.index(anchor))
    end = native_talon.index(next_branch, start)
    return native_talon[start:end]


guards = {
    "SCENE_KAKARIKO_CENTER_GUEST_HOUSE": talon_guards(
        "case 1:", "if (Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_KAKARIKO))",
        " else if (Flags_GetEventChkInf(EVENTCHKINF_TALON_WOKEN_IN_KAKARIKO))"),
    "SCENE_HYRULE_CASTLE": talon_guards(
        "default:", "if (Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE))",
        " else if (Flags_GetEventChkInf(EVENTCHKINF_TALON_WOKEN_IN_CASTLE))"),
    "SCENE_LON_LON_BUILDINGS": talon_guards(
        "default:", "if (!Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE))",
        " else {"),
}
route_function = function(finder, "static SohExtreme::TrackerScene FinderRowScene(")
selection_start = route_function.index("        SohExtreme::TrackerScene best;")
selection_end = route_function.index("        return best;", selection_start) + len("        return best;")
selection = route_function[selection_start:selection_end]
rows = [line.strip() for line in (SOURCE / SCENES).read_text().splitlines()
        if re.search(r"\{ 10000(?:094|118)LL,", line)]
assert len(rows) == 6

cpp = r'''
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>
enum { SCENE_KOKIRI_FOREST, SCENE_MIDOS_HOUSE, SCENE_LOST_WOODS,
       SCENE_HYRULE_CASTLE, SCENE_LON_LON_BUILDINGS, SCENE_KAKARIKO_CENTER_GUEST_HOUSE };
enum { EVENTCHKINF_SPOKE_TO_MIDO_AFTER_DEKU_TREES_DEATH, EVENTCHKINF_OBTAINED_ZELDAS_LETTER,
       EVENTCHKINF_TALON_RETURNED_FROM_CASTLE, EVENTCHKINF_TALON_RETURNED_FROM_KAKARIKO,
       EVENTCHKINF_TALON_WOKEN_IN_CASTLE };
static int testAge = 0, testFlags = 0;
static bool Flags_GetEventChkInf(int flag) { return (testFlags & (1 << flag)) != 0; }
#define LINK_IS_ADULT (testAge == 1)
using u8 = unsigned char;
struct Actor { bool killed = false; };
struct EnMd {};
struct EnTa { Actor actor; };
struct PlayState { int sceneNum; };
static void Actor_Kill(Actor* actor) { actor->killed = true; }
namespace SohExtreme {
struct TrackerScene { int scene = -1; bool Matches(const TrackerScene& other) const {
    return scene >= 0 && scene == other.scene;
}};
'''
cpp += priority + "\n}\n" + helper + "\n"
cpp += re.sub(r"\bthis\b", "thisActor", native_mido) + "\n"
cpp += "static bool NativeTalonScenePresent(int scene) { EnTa actor; EnTa* thisActor = &actor;\n"
for scene, guard in guards.items():
    cpp += f"if (scene == {scene}) {{\n" + re.sub(r"\bthis\b", "thisActor", guard) + "\n}\n"
cpp += "return !actor.actor.killed; }\n"
cpp += r'''
constexpr int RC_UNKNOWN_CHECK = 0, RCAREA_INVALID = -1;
struct ConversationScene { int64_t location; int check, scene, area, grotto, age, time; };
static SohExtreme::TrackerScene FinderNativeScene(int) { return {}; }
static SohExtreme::TrackerScene FinderScene(int scene, int, int) { return {scene}; }
static SohExtreme::TrackerScene Select(int64_t id, int currentScene) {
    static const ConversationScene rows[] = {
'''
cpp += "\n".join(rows) + "\n};\n"
cpp += r'''
    std::map<int64_t, std::vector<ConversationScene>> conversations;
    for (const auto& row : rows) conversations[row.location].push_back(row);
    const auto conversation = conversations.find(id);
    const SohExtreme::TrackerScene current {currentScene};
    const int age = testAge, time = 0;
'''
cpp += selection + "\n}\n"
cpp += r'''
int main() {
    int comparisons = 0;
    for (testAge = 0; testAge < 2; ++testAge) {
        for (testFlags = 0; testFlags < 4; ++testFlags) {
            for (int scene : {SCENE_KOKIRI_FOREST, SCENE_MIDOS_HOUSE, SCENE_LOST_WOODS}) {
                PlayState play {scene};
                if (FinderNpcSpeechScenePresent(10000094, scene, testAge) != bool(EnMd_ShouldSpawn(nullptr, &play))) return 1;
                ++comparisons;
            }
        }
        for (int flags = 0; flags < 8; ++flags) {
            testFlags = flags << 2;
            for (int scene : {SCENE_HYRULE_CASTLE, SCENE_LON_LON_BUILDINGS, SCENE_KAKARIKO_CENTER_GUEST_HOUSE}) {
                if (FinderNpcSpeechScenePresent(10000118, scene, testAge) != NativeTalonScenePresent(scene)) return 2;
                ++comparisons;
            }
        }
    }
    struct Case { const char* name; int64_t id; int age, flags, current, expected; };
    const Case cases[] = {
        {"Mido before story flags in forest",10000094,0,0,SCENE_KOKIRI_FOREST,SCENE_KOKIRI_FOREST},
        {"Mido before story flags in empty house",10000094,0,0,SCENE_MIDOS_HOUSE,SCENE_KOKIRI_FOREST},
        {"Mido after Deku conversation in forest",10000094,0,1,SCENE_KOKIRI_FOREST,SCENE_MIDOS_HOUSE},
        {"Mido after letter in forest",10000094,0,2,SCENE_KOKIRI_FOREST,SCENE_MIDOS_HOUSE},
        {"Mido Skip Child Zelda in forest",10000094,0,22,SCENE_KOKIRI_FOREST,SCENE_MIDOS_HOUSE},
        {"Mido adult before flags",10000094,1,0,SCENE_KOKIRI_FOREST,SCENE_LOST_WOODS},
        {"Mido adult after flags",10000094,1,3,SCENE_MIDOS_HOUSE,SCENE_LOST_WOODS},
        {"Talon sleeping in castle",10000118,0,0,SCENE_HYRULE_CASTLE,SCENE_HYRULE_CASTLE},
        {"Talon sleeping in empty ranch",10000118,0,0,SCENE_LON_LON_BUILDINGS,SCENE_HYRULE_CASTLE},
        {"Talon awake but not departed",10000118,0,16,SCENE_HYRULE_CASTLE,SCENE_HYRULE_CASTLE},
        {"Talon departed while player visits castle",10000118,0,4,SCENE_HYRULE_CASTLE,SCENE_LON_LON_BUILDINGS},
        {"Talon departed while player visits ranch",10000118,0,4,SCENE_LON_LON_BUILDINGS,SCENE_LON_LON_BUILDINGS},
        {"Talon Skip Child Zelda in castle",10000118,0,22,SCENE_HYRULE_CASTLE,SCENE_LON_LON_BUILDINGS},
        {"Talon adult before Kakariko departure",10000118,1,4,SCENE_HYRULE_CASTLE,SCENE_KAKARIKO_CENTER_GUEST_HOUSE},
        {"Talon adult departed Kakariko",10000118,1,12,SCENE_KAKARIKO_CENTER_GUEST_HOUSE,-1},
    };
    for (const auto& row : cases) {
        testAge = row.age; testFlags = row.flags;
        const int actual = Select(row.id, row.current).scene;
        std::cout << row.name << '\t' << row.expected << '\t' << actual << '\n';
        if (actual != row.expected) return 3;
    }
    std::cout << "native_predicate_comparisons\t" << comparisons << '\n';
}
'''
fixture = TESTS / "finder_npc_scene_placement_fixture.cpp"
fixture.write_text(cpp)
binary = TESTS / "finder_npc_scene_placement_fixture"
compile_command = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Wno-unused-parameter", str(fixture), "-o", str(binary)]
subprocess.run(compile_command, check=True, capture_output=True, text=True)
run = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
table = []
for line in run.stdout.splitlines():
    columns = line.split("\t")
    if len(columns) == 3:
        table.append({"case": columns[0], "expected_scene": int(columns[1]), "actual_scene": int(columns[2])})
    else:
        assert columns[0] == "native_predicate_comparisons"
        comparisons = int(columns[1])
assert comparisons == 72 and len(table) == 15
assert 'cv("ShuffleWeirdEgg", 2)' in (SOURCE / "archipelago/soh_extreme/__init__.py").read_text()
assert 'cv("StartingZeldasLetter", 1)' in (SOURCE / "archipelago/soh_extreme/__init__.py").read_text()
save = (SOURCE / "soh/Enhancements/randomizer/savefile.cpp").read_text()
assert "Flags_SetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE);" in save
assert "Flags_SetEventChkInf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER);" in save
report = {
    "status": "passed",
    "scope": "Compiled final Finder presence helper and final route selection loop. Native Mido spawn function and exact Talon init kill-guard spans compiled with actor/flag/scene shims. No full native build or game UI run.",
    "native_predicate_comparisons": comparisons,
    "scene_selection_cases": table,
    "fixture_scene_enum": {name: index for index, name in enumerate(("Kokiri Forest", "Mido's House", "Lost Woods", "Hyrule Castle", "Lon Lon Buildings", "Kakariko Guest House"))},
    "skip_child_zelda_provenance": "Existing slot-data settings set StartingZeldasLetter=1 and ShuffleWeirdEgg=2; native save initialization sets Zelda-letter, Talon-woken and Talon-left-castle flags. Fixture flag set 22 represents those three flags.",
    "talon_after_adult_departure": "Native EnTa_IdleAwakeInKakariko sets the return flag only through an actual conversation, so the permanent first-speech identity has already been fulfilled. An out-of-date row no longer points to the departed Kakariko actor; no new AP route or rule is introduced.",
    "source_sha256": {name: sha((SOURCE / name).read_bytes()) for name in (FINDER, MIDO, TALON, SCENES, PRIORITY, "soh/Enhancements/randomizer/savefile.cpp", "archipelago/soh_extreme/__init__.py")},
    "fragment_sha256_lf": {"FinderNpcSpeechScenePresent": sha(helper.encode()), "FinderRowScene_selection": sha(selection.encode()), "EnMd_ShouldSpawn": sha(native_mido.encode()), **{name: sha(value.encode()) for name, value in guards.items()}},
    "fixture_sha256": sha(fixture.read_bytes()),
    "probe_sha256": sha(Path(__file__).read_bytes()),
    "compile_command": compile_command,
    "full_native_game_build": False,
    "live_imgui_run": False,
}
(TESTS / "finder_npc_scene_placement_validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"status": "passed", "native_predicate_comparisons": comparisons, "scene_selection_cases": len(table)}, indent=2))
