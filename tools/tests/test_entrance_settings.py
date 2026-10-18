"""Compile native AP settings ingestion, readiness, and entrance status text.

Usage: python test_entrance_settings.py --dependencies PATH --report PATH
       child_cvars.json adult_cvars.json

The input JSON is exported by the actual APWorld. The production parser,
SetSlotSettingsFromJson, readiness/status methods, routing validator, and native
defaults are compiled unchanged. Network authentication and engine installation
are isolated; the separate slot bridge test covers the complete native runtime.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile


def between(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


HARNESS = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>
#include "json.hpp"
#include "soh/Network/Archipelago/EntranceRouting.h"
#include "captured_constants.h"
using Json = nlohmann::json;
static size_t errorLogs = 0;
template <class... Args> void ErrorLog(Args&&...) { ++errorLogs; }
template <class... Args> void IgnoreLog(Args&&...) {}
#define SPDLOG_ERROR(...) ErrorLog(__VA_ARGS__)
#define SPDLOG_INFO(...) IgnoreLog(__VA_ARGS__)
#define SPDLOG_DEBUG(...) IgnoreLog(__VA_ARGS__)
namespace SohExtreme::EntranceRuntime {
EntranceRouting routing;
bool slotMapLoaded = false;
#include "captured_validate.inc"
}
class ArchipelagoClient {
public:
    // IO boundary only: the production readiness method consumes this result.
    bool authenticated = true;
    bool IsAuthenticated() const { return authenticated; }
    void SetSlotSettingsFromJson(const std::string& raw);
    bool IsReadyForFileSelect() const;
    std::string GetEntranceStatusText() const;
#include "captured_fields.inc"
};
#include "captured_parser.inc"
#include "captured_set_slot_settings.inc"
#include "captured_readiness.inc"
#include "captured_status.inc"

static std::string Read(const char* path) {
    std::ifstream file(path);
    assert(file.good());
    return {std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
}
static void Prepare(ArchipelagoClient& client) {
    client.authenticated = true;
    client.activeLocationsLoaded = true;
    client.shopPricesLoaded = true;
}
static void InstallForStatus(const std::unordered_map<std::string, int>& settings) {
    // Installation itself is covered by test_entrance_slot_bridge. Here the
    // status method sees the same routing object that the runtime owns.
    SohExtreme::EntranceRouting next;
    std::string error;
    assert(SohExtreme::EntranceRuntime::Validate(settings, next, error));
    SohExtreme::EntranceRuntime::routing = std::move(next);
    SohExtreme::EntranceRuntime::slotMapLoaded = true;
}
static std::string DestinationName(int id) {
    const auto* endpoint = SohExtreme::EntranceEndpointById(id);
    assert(endpoint);
    std::string result = endpoint->name;
    const auto arrow = result.find(" -> ");
    return arrow == std::string::npos ? result : result.substr(arrow + 4);
}
static void AssertRejected(ArchipelagoClient& client, const std::string& raw) {
    const auto cached = client.cachedSlotSettingsJson;
    const auto settings = client.slotSettings;
    const bool loaded = client.slotSettingsLoaded;
    const bool pending = client.slotSettingsPendingApply.load();
    const auto installed = SohExtreme::EntranceRuntime::routing.Routes();
    const auto logsBefore = errorLogs;
    client.SetSlotSettingsFromJson(raw);
    assert(!client.IsReadyForFileSelect());
    assert(!client.slotSettingsError.empty());
    assert(client.GetEntranceStatusText().starts_with("Entrances: "));
    assert(client.GetEntranceStatusText().find("vanilla in") == std::string::npos);
    assert(client.cachedSlotSettingsJson == cached && client.slotSettings == settings);
    assert(client.slotSettingsLoaded == loaded);
    assert(client.slotSettingsPendingApply.load() == pending);
    assert(SohExtreme::EntranceRuntime::routing.Routes() == installed);
    assert(errorLogs == logsBefore + 1);
    const auto error = client.slotSettingsError;
    for (int frame = 0; frame < 120; ++frame) client.SetSlotSettingsFromJson(raw);
    assert(errorLogs == logsBefore + 1);
    assert(client.slotSettingsError == error);
    assert(client.cachedSlotSettingsJson == cached && client.slotSettings == settings);
}

int main(int argc, char** argv) {
    assert(argc >= 2);
    Json cases = Json::array();
    for (int argument = 1; argument < argc; ++argument) {
        const auto raw = Read(argv[argument]);
        const auto fixture = Json::parse(raw);
        ArchipelagoClient client;
        Prepare(client);
        SohExtreme::EntranceRuntime::routing.Reset();
        SohExtreme::EntranceRuntime::slotMapLoaded = false;
        assert(!client.IsReadyForFileSelect());
        assert(client.GetEntranceStatusText() == "Entrances: waiting for AP seed settings");
        client.SetSlotSettingsFromJson(raw);
        assert(client.IsReadyForFileSelect() && client.slotSettingsError.empty());
        assert(client.cachedSlotSettingsJson == raw && client.slotSettingsPendingApply.load());
        assert(client.slotSettings.at("EntranceRandomizerRevision") == 1);
        assert(client.slotSettings.at("ShuffleOverworldEntrances") == 1);
        assert(client.slotSettings.at("ShuffleOverworldSpawns") == 1);
        assert(!SohExtreme::EntranceRuntime::slotMapLoaded);
        assert(!SohExtreme::EntranceRuntime::routing.Active());
        assert(client.GetEntranceStatusText() == "Entrances: randomized map received; open this seed's Archipelago save");
        client.authenticated = false;
        assert(!client.IsReadyForFileSelect());
        client.authenticated = true;
        client.activeLocationsLoaded = false;
        assert(!client.IsReadyForFileSelect());
        client.activeLocationsLoaded = true;
        client.shopPricesLoaded = false;
        assert(!client.IsReadyForFileSelect());
        client.shopPricesLoaded = true;
        assert(client.IsReadyForFileSelect());
        client.currentSaveIsArchipelago = true;
        assert(client.GetEntranceStatusText() == "Entrances: waiting for this save's seed map");
        InstallForStatus(client.slotSettings);
        const auto installedRoutes = SohExtreme::EntranceRuntime::routing.Routes();
        const int child = fixture.at("EntranceMap.187");
        const int adult = fixture.at("EntranceMap.642");
        const auto installedText = client.GetEntranceStatusText();
        assert(installedText.find(std::to_string(installedRoutes.size()) + " routes loaded") != std::string::npos);
        assert(installedText.find("Child spawn: " + DestinationName(child)) != std::string::npos);
        assert(installedText.find("Adult spawn: " + DestinationName(adult)) != std::string::npos);
        // The installed save wins even over conflicting currently loaded settings.
        // No CVar functions are linked into this harness at all.
        const auto serverSettings = client.slotSettings;
        client.slotSettings.clear();
        client.slotSettings.emplace("EntranceRandomizerRevision", 0);
        assert(client.GetEntranceStatusText() == installedText);
        client.slotSettings = serverSettings;
        client.slotSettingsPendingApply.store(false);

        std::vector<std::pair<std::string, std::string>> invalid;
        Json bad = fixture;
        bad.erase("EntranceRandomizerRevision");
        invalid.emplace_back("missing revision with actual map", bad.dump());
        bad = fixture; bad["EntranceRandomizerRevision"] = 0;
        invalid.emplace_back("revision zero with actual map", bad.dump());
        bad = fixture; bad["EntranceRandomizerRevision"] = 2;
        invalid.emplace_back("unsupported revision", bad.dump());
        bad = fixture;
        for (auto it = bad.begin(); it != bad.end();) {
            if (it.key().starts_with("EntranceMap.")) it = bad.erase(it); else ++it;
        }
        invalid.emplace_back("versioned map missing every route", bad.dump());
        for (const char* key : {"ShuffleInteriorsEntrances", "ShuffleThievesHideoutEntrances",
                 "ShuffleDungeonsEntrances", "ShuffleGanonTowerEntrance", "ShuffleBossEntrances",
                 "ShuffleGrottosEntrances", "ShuffleOverworldEntrances", "ShuffleOwlDrops",
                 "ShuffleWarpSongs", "ShuffleOverworldSpawns", "ShuffleDungeonDoors"}) {
            bad = Json::object(); bad[key] = 1;
            invalid.emplace_back(std::string("unversioned request: ") + key, bad.dump());
        }
        bad = fixture; bad["EntranceMap.30000"] = child;
        invalid.emplace_back("unknown source", bad.dump());
        bad = fixture; bad["EntranceMap.187"] = 30000;
        invalid.emplace_back("unknown destination", bad.dump());
        bad = fixture; bad["EntranceMap.0187"] = child;
        invalid.emplace_back("duplicate numeric source alias", bad.dump());
        bad = fixture; bad["EntranceMap.187suffix"] = child;
        invalid.emplace_back("malformed numeric source", bad.dump());
        for (const auto& [source, target] : installedRoutes) {
            if (SohExtreme::EntranceEndpointById(source)->reverse < 0) continue;
            bad = fixture;
            bad.erase("EntranceMap." + std::to_string(SohExtreme::EntranceEndpointById(target)->reverse));
            invalid.emplace_back("missing paired return", bad.dump());
            break;
        }
        // A legacy coupled map can still break carried-Ruto progression.
        // Reject that semantic mismatch before making a new AP save ready.
        for (const auto& [source, target] : installedRoutes) {
            if (SohExtreme::EntranceEndpointById(source)->reverse < 0 ||
                SohExtreme::IsLocalCarrierDoor(source)) continue;
            constexpr int carrySource = 8456;
            const int carryTarget = installedRoutes.at(carrySource);
            assert(carryTarget == carrySource);
            bad = fixture;
            bad["EntranceMap." + std::to_string(carrySource)] = target;
            bad["EntranceMap." + std::to_string(source)] = carryTarget;
            bad["EntranceMap." + std::to_string(SohExtreme::EntranceEndpointById(target)->reverse)] =
                SohExtreme::EntranceEndpointById(carrySource)->reverse;
            bad["EntranceMap." + std::to_string(SohExtreme::EntranceEndpointById(carryTarget)->reverse)] =
                SohExtreme::EntranceEndpointById(source)->reverse;
            invalid.emplace_back("coupled legacy map breaks Ruto carry route", bad.dump());
            break;
        }
        bad = fixture; bad["StartingAge"] = true;
        invalid.emplace_back("boolean native setting", bad.dump());
        bad = fixture; bad["StartingAge"] = 1.5;
        invalid.emplace_back("floating point native setting", bad.dump());
        bad = fixture; bad["StartingAge"] = int64_t{2147483648};
        invalid.emplace_back("signed int overflow", bad.dump());
        bad = fixture; bad["StartingAge"] = int64_t{-2147483649};
        invalid.emplace_back("signed int underflow", bad.dump());
        bad = fixture; bad["StartingAge"] = std::numeric_limits<uint64_t>::max();
        invalid.emplace_back("unsigned int64 overflow", bad.dump());
        invalid.emplace_back("invalid JSON", "not-json");
        invalid.emplace_back("array instead of object", "[]");
        Json rejected = Json::array();
        for (const auto& [name, invalidRaw] : invalid) {
            ArchipelagoClient fresh;
            Prepare(fresh);
            AssertRejected(fresh, invalidRaw);
            assert(!fresh.slotSettingsLoaded && fresh.cachedSlotSettingsJson.empty() && fresh.slotSettings.empty());
            AssertRejected(client, invalidRaw);
            // Correcting to the original good snapshot clears rejection state
            // without needlessly marking the unchanged map for application.
            client.SetSlotSettingsFromJson(raw);
            assert(client.IsReadyForFileSelect() && client.slotSettingsError.empty());
            assert(client.rejectedSlotSettingsJson.empty() && client.cachedSlotSettingsJson == raw);
            assert(!client.slotSettingsPendingApply.load());
            assert(client.GetEntranceStatusText() == installedText);
            rejected.push_back(name);
        }

        // A corrected, genuinely new valid map is accepted and queued for apply.
        bad = fixture; bad["EntranceMap.187"] = adult;
        const auto corrected = bad.dump();
        client.SetSlotSettingsFromJson(corrected);
        assert(client.IsReadyForFileSelect() && client.slotSettingsPendingApply.load());
        assert(client.cachedSlotSettingsJson == corrected && client.slotSettings.at("EntranceMap.187") == adult);
        // Status must continue showing what is installed until the runtime applies it.
        assert(client.GetEntranceStatusText() == installedText);
        InstallForStatus(client.slotSettings);
        assert(client.GetEntranceStatusText().find("Child spawn: " + DestinationName(adult)) != std::string::npos);
        client.slotSettingsPendingApply.store(false);
        client.SetSlotSettingsFromJson(corrected);
        assert(!client.slotSettingsPendingApply.load());

        // Legacy all-off maps must not inherit menu flags or become rejected.
        ArchipelagoClient legacy;
        Prepare(legacy);
        for (const auto& legacyRaw : {std::string("{}"), std::string("{\"EntranceRandomizerRevision\":0,\"ShuffleOverworldEntrances\":0,\"ShuffleOverworldSpawns\":0}")}) {
            legacy.SetSlotSettingsFromJson(legacyRaw);
            assert(legacy.IsReadyForFileSelect() && legacy.slotSettingsError.empty());
            assert(legacy.GetEntranceStatusText() == "Entrances: vanilla in the connected server's seed");
            InstallForStatus(legacy.slotSettings);
            assert(!SohExtreme::EntranceRuntime::routing.Active());
            legacy.currentSaveIsArchipelago = true;
            assert(legacy.GetEntranceStatusText() == "Entrances: vanilla in this save's seed");
            legacy.currentSaveIsArchipelago = false;
        }
        // A mapped save that does not shuffle either spawn names their defaults.
        InstallForStatus({{"EntranceRandomizerRevision", 1}, {"EntranceMap.333", 333}, {"EntranceMap.441", 441}});
        client.currentSaveIsArchipelago = true;
        assert(client.GetEntranceStatusText().find("Child spawn: Link's House (not shuffled by this seed)") != std::string::npos);
        assert(client.GetEntranceStatusText().find("Adult spawn: Temple of Time (not shuffled by this seed)") != std::string::npos);
        cases.push_back({{"fixture", argv[argument]}, {"native_cvars", fixture.size()},
                         {"routes", installedRoutes.size()}, {"child_spawn", child}, {"adult_spawn", adult},
                         {"rejected_inputs", rejected}, {"rejection_memo_frames_per_input", 120},
                         {"valid_snapshot_readiness", true}, {"good_cache_preserved", true},
                         {"corrected_snapshot_recovery", true}, {"status_uses_installed_routes", true},
                         {"legacy_all_off_accepted", true}});
    }
    std::cout << cases.dump() << '\n';
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('fixtures', type=Path, nargs='+')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which('g++') or shutil.which('c++')
    if not compiler:
        raise SystemExit('A C++20 compiler is required.')
    dependency = args.dependencies / 'json.hpp'
    if not dependency.is_file():
        raise SystemExit(f'Missing public test dependency: {dependency}')
    names = (
        'soh/Network/Archipelago/ArchipelagoClient.cpp',
        'soh/Network/Archipelago/ArchipelagoClient.h',
        'soh/Network/Archipelago/EntranceRouting.h',
        'soh/Network/Archipelago/EntranceRuntime.inc',
        'soh/Network/Archipelago/EntranceRandomizerData.inc',
        'soh/Network/Archipelago/ArchipelagoNativeDefaults.inc',
        'soh/Enhancements/randomizer/randomizer_entrance.h',
        'soh/Enhancements/randomizer/randomizerEnums/RandomizerOptions.h',
        'soh/SohGui/SohMenuNetwork.cpp',
    )
    before = {name: digest(root / name) for name in names}
    client = (root / names[0]).read_text()
    header = (root / names[1]).read_text()
    runtime = (root / names[3]).read_text()
    entrance = (root / names[6]).read_text()
    options = (root / names[7]).read_text()
    menu = (root / names[8]).read_text()
    assert 'GetEntranceStatusText()' in menu
    assert '"SOH-EXTREME " SOH_EXTREME_VERSION' in menu
    catalog = json.loads((root / 'archipelago/soh_extreme/EntranceCatalog.json').read_text())
    constants = re.search(r'^#define ENTRANCE_OVERRIDES_MAX_COUNT\s+[^\r\n]+', entrance, re.MULTILINE).group(0)
    for index in ('ENTR_LINKS_HOUSE_CHILD_SPAWN', 'ENTR_HYRULE_FIELD_10'):
        row = next(row for row in catalog if row.get('index') == index)
        constants += f'\nconstexpr int {index} = {row["id"]};'
    fish = between(options, 'RANDO_ENUM_BEGIN(RandoOptionsFishsanity)', 'RANDO_ENUM_END(RandoOptionsFishsanity)')
    constants += '\n#define RANDO_ENUM_BEGIN(name) enum name {\n#define RANDO_ENUM_ITEM(name) name,\n'
    constants += fish + '};\n#undef RANDO_ENUM_BEGIN\n#undef RANDO_ENUM_ITEM\n'
    fields = []
    for field in ('queueMutex', 'slotSettings', 'cachedSlotSettingsJson', 'slotSettingsLoaded',
                  'slotSettingsError', 'rejectedSlotSettingsJson', 'slotSettingsPendingApply',
                  'activeLocationsLoaded', 'shopPricesLoaded', 'currentSaveIsArchipelago'):
        fields.append(re.search(r'^\s*(?![^\r\n]*\()[^\r\n;]*\b' + field + r'\b[^\r\n;]*;', header, re.MULTILINE).group(0))
    captures = {
        'captured_constants.h': constants,
        'captured_fields.inc': '\n'.join(fields),
        'captured_validate.inc': between(runtime, 'bool Validate(', 'bool Apply('),
        'captured_parser.inc': between(client, 'static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& out) {', 'static void RefreshArchipelagoRandomizerHooks()'),
        'captured_set_slot_settings.inc': between(client, 'void ArchipelagoClient::SetSlotSettingsFromJson(', 'void ArchipelagoClient::SetLocationNameMapFromJson('),
        'captured_readiness.inc': between(client, 'bool ArchipelagoClient::IsReadyForFileSelect() const {', 'void ArchipelagoClient::ApplyPostInitSlotState()'),
        'captured_status.inc': between(client, 'std::string ArchipelagoClient::GetEntranceStatusText() const {', 'bool ArchipelagoClient::ConnectionSettingsChanged() const'),
    }
    with tempfile.TemporaryDirectory(prefix='soh-entrance-settings-') as directory:
        work = Path(directory)
        for name, value in captures.items():
            (work / name).write_text(value + '\n')
        source = work / 'entrance_settings_tests.cpp'
        source.write_text(HARNESS)
        executable = work / 'entrance_settings_tests'
        command = [compiler, '-std=c++20', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', str(work),
                   '-I', str(args.dependencies.resolve()), '-I', str(root),
                   '-I', str(root / 'soh/Network/Archipelago'), str(source), '-o', str(executable)]
        subprocess.run(command, check=True)
        sanitizer_environment = os.environ.copy()
        # LeakSanitizer enumerates /proc tasks, which the isolated executor does
        # not expose. Address-access and undefined-behavior checks remain active.
        sanitizer_environment['ASAN_OPTIONS'] = sanitizer_environment.get('ASAN_OPTIONS', '') + ':detect_leaks=0'
        result = subprocess.run([str(executable), *(str(path.resolve()) for path in args.fixtures)],
                                text=True, capture_output=True, env=sanitizer_environment)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        cases = json.loads(result.stdout)
    after = {name: digest(root / name) for name in names}
    if before != after:
        raise SystemExit('Production source changed during settings verification; rerun after the edit is complete.')
    report = {
        'status': 'passed', 'cases': cases,
        'coverage': ['production JSON parser and SetSlotSettingsFromJson', 'actual generated adult/child fixtures',
                     'file-select readiness rejects invalid maps', 'cached good settings preserved atomically',
                     'repeated rejection is memoized', 'corrected snapshot recovery', 'legacy all-off accepted',
                     'actual installed route count and spawn names in status', 'network menu status binding'],
        'engine_io_isolated': True, 'native_windows_build': False, 'in_game_playthrough': False,
        'sanitizers': ['address', 'undefined'], 'source_sha256': before,
        'leak_sanitizer_enabled': False,
        'fixture_sha256': {str(path): digest(path) for path in args.fixtures},
        'dependency_sha256': {'json.hpp': digest(dependency)},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'passed', 'report': str(args.report), 'cases': cases}, indent=2))


if __name__ == '__main__':
    main()
