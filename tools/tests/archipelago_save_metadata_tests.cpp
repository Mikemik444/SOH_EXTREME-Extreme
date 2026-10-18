// The complete production LoadSaveMetadata method is compiled unchanged below.
// Engine scene initialization, worker IO, and settings delivery are isolated.
#include <atomic>
#include <cstdint>
#include <deque>
#include <iostream>
#include <limits>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <nlohmann/json.hpp>
#include "soh/Network/Archipelago/SaveConnectionIdentity.h"

using Json = nlohmann::json;
#define SPDLOG_ERROR(...)
#define SPDLOG_INFO(...)

namespace SohExtreme {
struct EntranceRouting {};
namespace EntranceRuntime {
static int resets = 0;
void Reset() { ++resets; }
bool Validate(const std::unordered_map<std::string, int>& settings, EntranceRouting&, std::string& error) {
    const auto revision = settings.find("EntranceRandomizerRevision");
    if (revision != settings.end() && revision->second > 1) { error = "invalid revision"; return false; }
    return true;
}
}
}
struct CrossingJournal { int resets = 0; void Reset() { ++resets; } } gCrossingJournal;
static int presentationResets = 0;
static void ResetRemotePresentations() { ++presentationResets; }
static std::deque<int64_t> gDeferredLocationReports;
static uint64_t gNewSaveReplayTargetCount = 0;
static int gNewSaveReplayGraceFrames = 0, gAwaitingMajorFrames = 0;
static struct {
    struct { struct { struct { struct { int triforcePiecesCollected = 0; } randomizer; } data; } quest; } ship;
} gSaveContext;
static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& result) {
    const auto parsed = Json::parse(raw, nullptr, false);
    if (!parsed.is_object()) return false;
    for (auto it = parsed.begin(); it != parsed.end(); ++it) {
        if (!it.value().is_number_integer()) return false;
        result[it.key()] = it.value().get<int64_t>();
    }
    return true;
}

class ArchipelagoClient {
  public:
    struct Worker {
        bool running = true;
        int checks = 0;
        bool IsRunning(std::string& status) { ++checks; status = running ? "running" : "stopped"; return running; }
    } finderWorker;
    struct PendingItem { int64_t id; bool notify; uint64_t sequence; };
    bool currentSaveIsArchipelago = true, saveIdentityMismatch = false, authenticated = true;
    bool finderWorkerStarted = true, slotSettingsLoaded = true;
    bool saveRuntimeSynchronized = true, newSaveReplayPending = true, awaitingMajorItemReceipt = true;
    bool saveMetadataLoaded = false, goalReported = true;
    uint64_t awaitingMajorSequence = 99, appliedItemCount = 99;
    int64_t awaitingMajorApItemId = 99;
    SohExtreme::SaveConnectionIdentity saveConnectionIdentity{"seed-one", 0, 1};
    SohExtreme::SaveConnectionIdentity connectedIdentity{"seed-one", 0, 1};
    SohExtreme::SaveConnectionDecision saveConnectionDecision = SohExtreme::SaveConnectionDecision::Ready;
    std::string saveSlot = "Link", connectedSlot = "Link", saveServer = "server:1234", connectedServer = "server:1234";
    std::string cachedSlotSettingsJson = "{\"EntranceRandomizerRevision\":0}";
    std::string connectedSettingsJson = "{\"EntranceRandomizerRevision\":0}";
    std::string saveConnectionStatus, slotSettingsError, rejectedSlotSettingsJson;
    double finderNextRequest = 44, nextHintRequest = 55;
    std::mutex hintJournalMutex, queueMutex;
    std::map<int, int> revealedHintTargets{{1, 1}};
    std::unordered_set<int64_t> pendingLocationReports{50};
    std::unordered_map<std::string, int> slotSettings{{"OldSetting", 2}};
    std::atomic<bool> slotSettingsPendingApply{true};
    std::deque<PendingItem> pendingItems{{99, true, 99}};
    std::vector<int64_t> receivedItemSnapshot{1000, 1001, 1002, 1003};
    int mirrorResets = 0, reconciliationCalls = 0, settingsApplies = 0, nonce = 5;
    bool IsAuthenticated() const { return authenticated; }
    void ResetFinderMirror() { ++mirrorResets; ++nonce; finderWorkerStarted = false; }
    void ReconcileSaveConnection() {
        ++reconciliationCalls;
        saveConnectionDecision = SohExtreme::CompareSaveConnection(
            saveConnectionIdentity, saveSlot, saveServer, connectedIdentity, connectedSlot, connectedServer,
            authenticated);
        saveIdentityMismatch = saveConnectionDecision != SohExtreme::SaveConnectionDecision::Ready;
    }
    void ApplySlotSettings() { ++settingsApplies; }
    void LoadSaveMetadata(bool isArchipelagoSave, uint64_t receivedItemCount,
                          const std::string& server, const std::string& slot,
                          const std::string& cachedSettingsJson,
                          const SohExtreme::SaveConnectionIdentity& identity);
};

#include "captured_save_metadata.inc"

static void Require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
static void Load(ArchipelagoClient& client, uint64_t cursor = 2) {
    client.LoadSaveMetadata(true, cursor, "server:1234", "Link", "{\"EntranceRandomizerRevision\":0}",
                            {"seed-one", 0, 1});
}

int main() {
    Json report = {{"status", "passed"}, {"cases", Json::array()}};
    auto run = [&](const char* name, auto test) { test(); report["cases"].push_back(name); };
    run("same_verified_save_keeps_worker_nonce_and_requests_fresh_snapshots", [] {
        ArchipelagoClient client;
        Load(client);
        Require(client.mirrorResets == 0 && client.nonce == 5 && client.finderWorkerStarted,
                "Same verified Return to Spawn restarted its managed worker");
        Require(client.finderWorker.checks == 1 && client.finderNextRequest == 0 && client.nextHintRequest == 0,
                "Return to Spawn did not verify host health or refresh its snapshots");
        Require(client.revealedHintTargets.size() == 1, "Pending completed hint was lost during spawn return");
    });
    run("preservation_still_reloads_receipts_inventory_settings_and_identity", [] {
        ArchipelagoClient client;
        gDeferredLocationReports.push_back(80); gNewSaveReplayTargetCount = 8; gNewSaveReplayGraceFrames = 9;
        gAwaitingMajorFrames = 8;
        const int entrances = SohExtreme::EntranceRuntime::resets, crossings = gCrossingJournal.resets;
        Load(client);
        Require(client.appliedItemCount == 2 && client.pendingItems.size() == 2 &&
                client.pendingItems.front().id == 1002 && client.pendingItems.front().sequence == 2,
                "Same-save preservation skipped receipt cursor restoration/replay");
        Require(client.pendingLocationReports.empty() && gDeferredLocationReports.empty() &&
                !client.saveRuntimeSynchronized && !client.newSaveReplayPending &&
                !client.awaitingMajorItemReceipt && client.awaitingMajorSequence == 0 &&
                client.awaitingMajorApItemId == 0 && gAwaitingMajorFrames == 0 &&
                gNewSaveReplayTargetCount == 0 && gNewSaveReplayGraceFrames == 0,
                "Old inventory/delivery state leaked through save reload");
        Require(client.reconciliationCalls == 1 && client.settingsApplies == 1 &&
                !client.saveIdentityMismatch && client.slotSettingsLoaded &&
                client.slotSettings.size() == 1 && client.slotSettings.at("EntranceRandomizerRevision") == 0 &&
                !client.slotSettingsPendingApply && client.saveMetadataLoaded && !client.goalReported &&
                SohExtreme::EntranceRuntime::resets == entrances + 1 && gCrossingJournal.resets == crossings + 1,
                "Ordinary settings, scene or identity reload did not run");
    });
    run("same_identity_pending_journal_survives_offline_or_stopped_worker", [] {
        for (int condition = 0; condition < 3; ++condition) {
            ArchipelagoClient client;
            if (condition == 0) client.authenticated = false;
            if (condition == 1) client.finderWorkerStarted = false;
            if (condition == 2) client.finderWorker.running = false;
            Load(client);
            Require(client.mirrorResets == 1, "An offline or dead worker incorrectly remained live");
            Require(client.revealedHintTargets.size() == 1, "Worker health erased a same-save completed hint");
        }
    });
    run("seed_team_slot_and_legacy_identity_changes_reset_worker_and_journal", [] {
        for (int condition = 0; condition < 4; ++condition) {
            ArchipelagoClient client;
            if (condition == 0) client.saveConnectionIdentity.seed = "other-seed";
            if (condition == 1) client.saveConnectionIdentity.team = 1;
            if (condition == 2) client.saveConnectionIdentity.slot = 2;
            if (condition == 3) client.saveConnectionIdentity = {};
            Load(client);
            Require(client.mirrorResets == 1 && client.revealedHintTargets.empty(),
                    "Changing file identity kept another seed's worker or completed hints");
        }
    });
    run("connection_alias_address_settings_and_verification_changes_reset_worker", [] {
        for (int condition = 0; condition < 10; ++condition) {
            ArchipelagoClient client;
            if (condition == 0) client.saveIdentityMismatch = true;
            if (condition == 1) client.connectedIdentity.seed = "different-live-seed";
            if (condition == 2) client.connectedIdentity.team = 2;
            if (condition == 3) client.connectedIdentity.slot = 2;
            if (condition == 4) client.connectedSlot = "Different Live Slot";
            if (condition == 5) client.saveSlot = "Different Saved Slot";
            if (condition == 6) client.connectedServer = "other-server:1234";
            if (condition == 7) client.saveServer = "other-server:1234";
            if (condition == 8) client.connectedSettingsJson = "{\"EntranceRandomizerRevision\":1}";
            if (condition == 9) client.cachedSlotSettingsJson = "{\"EntranceRandomizerRevision\":1}";
            Load(client);
            Require(client.mirrorResets == 1, "A different/unverified connection reused the old worker");
            Require(client.revealedHintTargets.size() == 1, "Same save lost its pending discoveries after connection change");
        }
    });
    run("unloaded_or_invalid_settings_retain_the_existing_validation_gate", [] {
        ArchipelagoClient unloaded;
        unloaded.slotSettingsLoaded = false;
        Load(unloaded);
        Require(unloaded.mirrorResets == 1, "Unverified prior settings preserved the host");
        for (const auto& settings : {std::string("invalid"), std::string("{\"EntranceRandomizerRevision\":99}"),
                                    std::string("{\"TooLarge\":2147483648}")}) {
            ArchipelagoClient client;
            client.LoadSaveMetadata(true, 1, "server:1234", "Link", settings, {"seed-one", 0, 1});
            Require(client.mirrorResets == 1 && !client.slotSettingsLoaded &&
                    client.settingsApplies == 0 && !client.slotSettingsError.empty(),
                    "Invalid saved settings bypassed normal rejection");
        }
    });
    run("vanilla_load_clears_ap_journal_and_host_without_applying_ap_settings", [] {
        ArchipelagoClient client;
        client.LoadSaveMetadata(false, 0, "", "", "", {});
        Require(client.mirrorResets == 1 && client.revealedHintTargets.empty() &&
                !client.currentSaveIsArchipelago && client.settingsApplies == 0 && client.appliedItemCount == 0,
                "Vanilla save inherited an AP worker or completed hint journal");
    });
    run("new_ap_save_never_inherits_current_worker_or_previous_hint_journal", [] {
        ArchipelagoClient client;
        client.currentSaveIsArchipelago = false;
        Load(client, 0);
        Require(client.mirrorResets == 1 && client.revealedHintTargets.empty() &&
                client.appliedItemCount == 0 && client.pendingItems.size() == 4,
                "New AP save inherited an old worker/journal or lost receipt replay");
    });
    std::cout << report.dump(2) << '\n';
}
