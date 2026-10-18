// Compile the actual hint provenance, snapshot decoder and client methods.
// Game lifecycle, socket output and native RC lookup are isolated at the boundary.
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "soh/Network/Archipelago/ArchipelagoHintData.h"
#include "soh/Network/Archipelago/SaveConnectionIdentity.h"

using Json = nlohmann::json;
namespace SohExtreme { constexpr const char* kTrackerProtocol = "SOHExtremeFinder1"; }
static double now = 10;
static double FinderMirrorClock() { return now; }
static int AP_GetPlayerID() { return 1; }
struct AP_Bounce { std::vector<std::string>* tags = nullptr; std::string data; };
static std::vector<Json> sent;
static void AP_SendBounce(const AP_Bounce& bounce) { sent.push_back(Json::parse(bounce.data)); }
static uint64_t gAwaitingMajorFrames = 0;
static std::vector<int64_t> gDeferredLocationReports;
static struct {
    struct { struct { struct { struct { int triforcePiecesCollected = 0; } randomizer; } data; } quest; } ship;
} gSaveContext;
static std::map<std::string, int> cvars;
static void CVarSetInteger(const char* key, int value) { cvars[key] = value; }
#define SPDLOG_INFO(...)

class ArchipelagoClient {
  public:
    struct ScoutedLocation {
        int64_t itemId = 0;
        int playerId = 0, flags = 0;
        std::string itemName, playerName, locationName, itemGame;
    };
    struct HintInfo { std::string item, location, finder, recipient, entrance; bool found = false; };
    struct Mirror { std::string Nonce() const { return "native-session"; } } finderMirror;
    static ArchipelagoClient& GetInstance() { static ArchipelagoClient client; return client; }
    bool IsGameplaySessionActive() const { return gameplay; }
    bool IsAuthenticated() const { return authenticated; }
    bool IsLocationActive(int64_t id) const { return activeLocations.contains(id); }
    int64_t ResolveApLocationForCheck(int32_t rc) { return rc == 7 ? 11200000 : -1; }
    SohExtreme::HintTarget MakeHintTarget(int64_t id) const;
    std::vector<SohExtreme::HintTarget> GetHintItemTargets(int32_t rc);
    std::vector<SohExtreme::HintTarget> GetInGameHintTargets(const std::string& key, int32_t stone = -1);
    void RecordRevealedHintTargets(const std::vector<SohExtreme::HintTarget>& targets);
    void RebuildHints();
    std::string GetRevealedHintTargetsJson() const;
    bool LoadRevealedHintTargetsJson(const std::string& raw);
    void ServiceHintBridge();
    void PrimeNewSaveMetadata();
    std::string GetReceivedCountCVar() const { return "gNetwork.Archipelago.TestReceiveCount"; }
    bool gameplay = true, authenticated = true, currentSaveIsArchipelago = true, finderWorkerStarted = true;
    bool scoutsRequested = true, hintSnapshotLoaded = false;
    bool awaitingMajorItemReceipt = false, newSaveReplayPending = false, saveMetadataLoaded = false;
    bool saveIdentityMismatch = false;
    uint64_t appliedItemCount = 0, awaitingMajorSequence = 0;
    int64_t awaitingMajorApItemId = 0;
    size_t expectedScoutCount = 1;
    SohExtreme::SaveConnectionIdentity saveConnectionIdentity{"seed-one", 0, 1};
    SohExtreme::SaveConnectionIdentity connectedIdentity{"seed-one", 0, 1};
    std::string saveSlot = "Local Player";
    std::string saveServer = "old-server", connectedServer = "old-server", connectedSlot = "Local Player";
    mutable std::mutex hintJournalMutex;
    std::mutex queueMutex;
    std::unordered_map<int64_t, ScoutedLocation> scoutedLocations;
    std::unordered_set<int64_t> activeLocations, reportedLocations;
    std::unordered_set<int64_t> pendingLocationReports;
    std::vector<int64_t> pendingItems, receivedItemSnapshot;
    std::map<std::pair<int, int64_t>, SohExtreme::HintTarget> revealedHintTargets;
    SohExtreme::InGameHintData inGameHints;
    std::vector<SohExtreme::ServerHintRecord> serverHintRows;
    std::vector<HintInfo> hints;
    std::string pendingHintPayload, hintProducer, hintSyncStatus;
    uint64_t hintRequest = 0, hintRevision = 0;
    double nextHintRequest = 0, nextHintPublish = 0;
};

#include "soh/Network/Archipelago/ArchipelagoHintClient.inc"
#include "captured_prime_metadata.inc"

static void Require(bool condition, const char* description) {
    if (!condition) throw std::runtime_error(description);
}

static SohExtreme::HintTarget Target(int finder = 1, int64_t location = 11200000, int flags = 1) {
    SohExtreme::HintTarget target;
    target.locationId = location; target.itemId = 777; target.finderId = finder; target.recipientId = 2;
    target.flags = flags; target.item = "Actual Advancement"; target.location = "Actual Location";
    target.finder = "Local Player"; target.recipient = "Other Player"; target.game = "SOH-EXTREME";
    target.seed = "seed-one"; target.team = 0; target.slot = 1;
    return target;
}

static Json Snapshot(const std::vector<SohExtreme::HintTarget>& targets, uint64_t revision = 1) {
    Json rows = Json::array();
    for (const auto& target : targets) {
        auto row = HintTargetJson(target);
        row["found"] = false;
        rows.push_back(row);
    }
    return {{"soh_extreme_tracker", "SOHExtremeFinder1"}, {"kind", "hint_snapshot"}, {"nonce", "native-session"},
            {"producer", "worker-one"}, {"slot", 1}, {"request", 1}, {"revision", revision}, {"rows", rows}};
}

int main(int argc, char** argv) {
    Json report = {{"status", "passed"}, {"cases", Json::array()}};
    auto run = [&](const char* name, auto test) { sent.clear(); test(); report["cases"].push_back(name); };
    run("classification_bits_not_item_spelling", [] {
        for (int flags = -1; flags < 8; ++flags)
            Require(Target(1, 1, flags).IsProgression() == (flags == 1 || flags == 3), "Wrong AP classification filter");
        for (int flags : {9, 17, 33}) {
            Require(Target(1, 1, flags).IsProgression(), "Higher progression variant was discarded");
            Require(SohExtreme::ReadHintTarget(HintTargetJson(Target(1, 1, flags))).flags == flags,
                    "Progression variant did not survive typed metadata");
        }
        auto junk = Target(1, 1, 0); junk.item = "Progressive Junk";
        Require(!junk.IsProgression(), "Item spelling was treated as progression");
    });
    run("area_and_starting_hints_have_no_item_provenance", [] {
        SohExtreme::InGameHintData data;
        auto starting = HintTargetJson(Target()); starting["starting"] = true;
        Json raw = {{"hero", {{{"type", "woth"}, {"area", "Lift Room"}, {"finder", "Player"}}}},
                    {"barren", {{{"type", "barren"}, {"area", "Empty Room"}, {"finder", "Player"}}}},
                    {"starting", {starting}}};
        Require(data.Load(raw.dump()), "Typed hint snapshot failed");
        Require(data.Get("hero").find("way of the hero") != std::string::npos, "WOTH text missing");
        Require(data.Get("barren").find("barren of progression") != std::string::npos, "Barren text missing");
        Require(data.Targets("hero").empty() && data.Targets("barren").empty() && data.Targets("starting").empty(),
                "Area or starting inventory became a network item target");
    });
    run("unread_builders_never_record_or_send", [] {
        ArchipelagoClient client;
        client.activeLocations.insert(11200000);
        client.scoutedLocations[11200000] = {777, 2, 1, "Actual Advancement", "Other Player", "Actual Location", "Other Game"};
        auto targets = client.GetHintItemTargets(7);
        Require(targets.size() == 1 && targets[0].locationId == 11200000, "Native target not resolved");
        Require(client.hints.empty() && client.revealedHintTargets.empty() && sent.empty(), "Building disclosed an unread hint");
        Require(client.GetHintItemTargets(8).empty(), "Vanilla/non-network check became a target");
    });
    run("frozen_target_survives_later_seed_snapshot", [] {
        ArchipelagoClient client;
        auto old = HintTargetJson(Target());
        Require(client.inGameHints.Load(Json{{"stone", {old}}}.dump()), "First snapshot failed");
        auto frozen = client.GetInGameHintTargets("stone", 1);
        auto newer = old; newer["location_id"] = 11200001; newer["location"] = "Unread New Target";
        Require(client.inGameHints.Load(Json{{"stone", {newer}}}.dump()), "Second snapshot failed");
        client.RecordRevealedHintTargets(frozen);
        Require(client.hints.size() == 1 && client.hints[0].location == "Actual Location", "Late snapshot changed a shown hint");
    });
    run("completion_records_only_progression_and_deduplicates", [] {
        ArchipelagoClient client;
        client.RecordRevealedHintTargets({Target(), Target(), Target(1, 2, 0), Target(1, 3, 2), Target(1, 4, 4), Target(1, 5, 5)});
        Require(client.hints.size() == 1 && client.revealedHintTargets.size() == 1, "Junk/trap/duplicate hint entered list");
    });
    run("stale_save_and_starting_target_rejected", [] {
        ArchipelagoClient client;
        auto oldSeed = Target(); oldSeed.seed = "another-seed";
        auto oldSlot = Target(); oldSlot.slot = 3;
        auto oldTeam = Target(); oldTeam.team = 1;
        auto starting = Target(); starting.starting = true;
        client.RecordRevealedHintTargets({oldSeed, oldSlot, oldTeam, starting});
        Require(client.hints.empty(), "A different save/room or starting item was published");
    });
    run("actual_new_file_priming_clears_old_journal_and_roundtrips_only_new_identity", [] {
        for (bool sameRoom : {false, true}) {
            ArchipelagoClient client;
            const auto old = Target();
            client.RecordRevealedHintTargets({old});
            Require(client.hints.size() == 1 && client.revealedHintTargets.size() == 1,
                    "Missing old-file completed hint in reproduction");
            client.appliedItemCount = 3;
            client.receivedItemSnapshot = {1, 2, 3};
            client.pendingItems = {4};
            client.pendingLocationReports.insert(5);
            client.awaitingMajorItemReceipt = true;
            client.awaitingMajorSequence = 9;
            client.awaitingMajorApItemId = 10;
            gAwaitingMajorFrames = 11;
            gDeferredLocationReports = {12};
            gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected = 13;
            client.nextHintPublish = 100;
            if (!sameRoom) {
                client.connectedIdentity = {"seed-two", 2, 3};
                client.connectedServer = "new-server";
                client.connectedSlot = "New Player";
            }
            client.PrimeNewSaveMetadata();
            Require(client.revealedHintTargets.empty() && client.hints.empty() &&
                    client.GetRevealedHintTargetsJson() == "[]" && client.nextHintPublish == 0,
                    "Actual AP file creation inherited the previous file's completed hint journal");
            Require(client.saveConnectionIdentity.seed == client.connectedIdentity.seed &&
                    client.saveConnectionIdentity.team == client.connectedIdentity.team &&
                    client.saveConnectionIdentity.slot == client.connectedIdentity.slot &&
                    client.saveServer == client.connectedServer && client.saveSlot == client.connectedSlot,
                    "Actual priming did not stamp the new save's identity");
            Require(client.appliedItemCount == 0 && client.pendingItems.empty() &&
                    client.receivedItemSnapshot == std::vector<int64_t>({1, 2, 3}) &&
                    client.pendingLocationReports.empty() && gDeferredLocationReports.empty() &&
                    !client.awaitingMajorItemReceipt && client.awaitingMajorSequence == 0 &&
                    client.awaitingMajorApItemId == 0 && gAwaitingMajorFrames == 0 &&
                    client.newSaveReplayPending && client.saveMetadataLoaded &&
                    client.currentSaveIsArchipelago && !client.saveIdentityMismatch &&
                    gSaveContext.ship.quest.data.randomizer.triforcePiecesCollected == 0 &&
                    cvars.at(client.GetReceivedCountCVar()) == 0 && client.finderWorkerStarted,
                    "Hint reset changed the deferred inventory replay or managed-worker boundary");
            auto fresh = Target(client.saveConnectionIdentity.slot, 11200002);
            fresh.seed = client.saveConnectionIdentity.seed;
            fresh.team = client.saveConnectionIdentity.team;
            fresh.slot = client.saveConnectionIdentity.slot;
            fresh.finder = client.saveSlot;
            client.RecordRevealedHintTargets({fresh});
            if (!sameRoom) client.RecordRevealedHintTargets({old});
            const auto saved = client.GetRevealedHintTargetsJson();
            Require(Json::parse(saved).size() == 1 && Json::parse(saved)[0]["seed"] == fresh.seed,
                    "The first new-file snapshot mixed old and new save identities");
            ArchipelagoClient loaded;
            loaded.saveConnectionIdentity = client.saveConnectionIdentity;
            loaded.saveSlot = client.saveSlot;
            Require(loaded.LoadRevealedHintTargetsJson(saved) && loaded.revealedHintTargets.size() == 1 &&
                    loaded.GetRevealedHintTargetsJson() == saved,
                    "A correctly revealed new-file hint failed durable journal reload");
        }
    });
    run("reconnect_retry_stops_after_authoritative_confirmation", [] {
        ArchipelagoClient client;
        client.RecordRevealedHintTargets({Target()});
        client.authenticated = false;
        client.ServiceHintBridge();
        Require(sent.empty() && client.hints.size() == 1, "Disconnected reveal sent or was forgotten");
        client.authenticated = true;
        client.ServiceHintBridge();
        Require(sent.size() == 2 && sent[1]["kind"] == "hint_reveal" && sent[1]["targets"].size() == 1,
                "Targeted publication was not queued");
        client.pendingHintPayload = Snapshot({Target()}).dump();
        now += 4;
        sent.clear();
        client.ServiceHintBridge();
        Require(client.hintSnapshotLoaded && client.hints.size() == 1, "Server confirmation was not merged");
        for (const auto& packet : sent) Require(packet["kind"] != "hint_reveal", "Confirmed hint was republished");
    });
    run("fresh_monotonic_progression_snapshot_only", [] {
        ArchipelagoClient client;
        auto packet = Snapshot({Target(), Target(1, 2, 0), Target(1, 3, 2), Target(1, 4, 4)}, 2);
        client.pendingHintPayload = packet.dump(); client.ServiceHintBridge();
        Require(client.hints.size() == 1 && client.hintRevision == 2, "Nonprogression server hint visible");
        packet["revision"] = 1; packet["rows"] = Json::array();
        client.pendingHintPayload = packet.dump(); client.ServiceHintBridge();
        Require(client.hints.size() == 1, "Stale revision replaced current hints");
        packet["revision"] = 3; packet["nonce"] = "another-session";
        client.pendingHintPayload = packet.dump(); client.ServiceHintBridge();
        Require(client.hints.size() == 1, "Foreign nonce replaced current hints");
    });
    run("local_found_state_and_shared_remote_identity", [] {
        ArchipelagoClient client;
        client.RecordRevealedHintTargets({Target(), Target(3, 11200000)});
        Require(client.hints.size() == 2, "Equal numeric IDs from different worlds collided");
        client.reportedLocations.insert(11200000); client.RebuildHints();
        Require(std::count_if(client.hints.begin(), client.hints.end(), [](const auto& hint) { return hint.found; }) == 1,
                "Local check incorrectly marked a foreign hint found");
    });
    run("durable_full_text_journal_is_atomic_and_seed_scoped", [] {
        ArchipelagoClient client;
        auto target = Target(); target.item += std::string(12000, 'X');
        client.RecordRevealedHintTargets({target});
        auto saved = client.GetRevealedHintTargetsJson();
        client.RecordRevealedHintTargets({Target(1, 11200001)});
        Require(client.LoadRevealedHintTargetsJson(saved) && client.hints.size() == 2,
                "Older same-save snapshot erased a newly completed hint");
        ArchipelagoClient loaded;
        Require(loaded.LoadRevealedHintTargetsJson(saved), "Saved journal failed to reload");
        Require(loaded.hints.size() == 1 && loaded.hints[0].item == target.item, "Saved full item text was shortened");
        Require(!loaded.LoadRevealedHintTargetsJson("{bad") && loaded.hints.size() == 1, "Malformed journal replaced valid state");
        Require(!loaded.LoadRevealedHintTargetsJson(std::string(8 * 1024 * 1024 + 1, ' ')), "Oversized journal accepted");
        auto wrong = Json::parse(saved); wrong[0]["seed"] = "other-seed";
        Require(!loaded.LoadRevealedHintTargetsJson(wrong.dump()) && loaded.hints[0].item == target.item,
                "Wrong-save journal was accepted");
    });
    run("legacy_local_exact_scout_match_only", [] {
        ArchipelagoClient client;
        client.activeLocations.insert(11200000);
        client.scoutedLocations[11200000] = {777, 2, 1, "Actual Advancement", "Other Player", "Actual Location", "Other Game"};
        auto legacy = HintTargetJson(Target());
        for (const auto* field : {"item_id", "location_id", "finding_player", "receiving_player", "item_flags"}) legacy.erase(field);
        Require(client.inGameHints.Load(Json{{"stone", {legacy}}}.dump()), "Legacy hint failed");
        Require(client.GetInGameHintTargets("stone").size() == 1, "Exact legacy local item not resolved");
        legacy["finder"] = "Other World";
        Require(client.inGameHints.Load(Json{{"stone", {legacy}}}.dump()), "Foreign legacy hint failed");
        Require(client.GetInGameHintTargets("stone").empty(), "Unknown foreign item flags were guessed");
    });
    run("snapshot_invalid_row_and_boundaries_are_atomic", [] {
        SohExtreme::ServerHintSnapshot snapshot;
        auto packet = Snapshot({Target()});
        Require(SohExtreme::ReadServerHintSnapshot(packet.dump(), snapshot), "Valid snapshot failed");
        packet["rows"][0]["item_flags"] = true;
        Require(!SohExtreme::ReadServerHintSnapshot(packet.dump(), snapshot) && snapshot.rows.size() == 1,
                "Invalid flag type partially replaced a snapshot");
        packet = Snapshot({Target()}); packet["rows"][0]["location_id"] = uint64_t(-1);
        Require(!SohExtreme::ReadServerHintSnapshot(packet.dump(), snapshot), "Out-of-range location ID accepted");
        Require(!SohExtreme::ReadServerHintSnapshot(std::string(8 * 1024 * 1024 + 1, ' '), snapshot), "Oversized snapshot accepted");
    });
    if (argc > 1) run("actual_python_bridge_wire_contract", [&] {
        std::ifstream file(argv[1]);
        Require(file.good(), "Missing Python bridge fixture");
        std::string raw((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        SohExtreme::ServerHintSnapshot snapshot;
        Require(SohExtreme::ReadServerHintSnapshot(raw, snapshot), "Actual Python bridge output rejected");
        Require(snapshot.rows.size() == 2 && snapshot.rows[0].target.IsProgression() && snapshot.rows[1].target.IsProgression(),
                "Actual bridge lost progression hint targets");
    });
    report["case_count"] = report["cases"].size();
    std::cout << report.dump(2) << '\n';
}
