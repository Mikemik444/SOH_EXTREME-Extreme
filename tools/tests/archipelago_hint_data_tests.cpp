// Compile the production hint-data header and native hint/merchant methods.
// Only game/session IO is isolated; all text loading and rendering is real.
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "soh/Network/Archipelago/ArchipelagoHintData.h"

using Json = nlohmann::json;

enum RandomizerCheck { RC_TEST_HINT = 7 };
namespace Rando::StaticData {
struct ItemName { std::string english; };
struct Item {
    ItemName name;
    const ItemName& GetName() const { return name; }
};
struct Location { int GetVanillaItem() const { return 0; } };
static Item vanillaItem;
static Location vanillaLocation;
static Item& RetrieveItem(int) { return vanillaItem; }
static Location* GetLocation(RandomizerCheck check) {
    return check == RC_TEST_HINT ? &vanillaLocation : nullptr;
}
} // namespace Rando::StaticData

class ArchipelagoClient {
  public:
    struct Scout {
        std::string itemName, playerName, locationName;
        int playerId = 1;
        int flags = 1;
    };
    bool gameplayActive = true;
    bool activeLocationsLoaded = true;
    bool scoutsRequested = true;
    size_t expectedScoutCount = 1;
    int64_t resolvedLocation = 11200007;
    std::unordered_map<int64_t, Scout> scoutedLocations;
    SohExtreme::InGameHintData inGameHints;
    bool IsGameplaySessionActive() const { return gameplayActive; }
    bool IsAuthenticated() const { return gameplayActive; }
    int64_t ResolveApLocationForCheck(int32_t) const { return resolvedLocation; }
    std::string GetHintItemDescription(int32_t randomizerCheck);
    std::string GetInGameHint(const std::string& key, int32_t stoneIndex = -1);
    std::string GetRemoteItemDescription(int32_t randomizerCheck);
};

static int AP_GetPlayerID() { return 1; }

#include "captured_hint_methods.inc"

static void Require(bool condition, const char* description) {
    if (!condition) throw std::runtime_error(description);
}

static std::string LongName(const std::string& prefix, size_t count, const std::string& suffix) {
    std::string result = prefix;
    for (size_t i = 0; i < count; ++i) result += "Éclair ";
    return result + suffix;
}

static Json Row(size_t index) {
    const auto suffix = std::to_string(index);
    return {
        {"item", LongName("Item ", 24, "ITEM_END_" + suffix)},
        {"recipient", LongName("Recipient ", 10, "RECIPIENT_END_" + suffix)},
        {"location", LongName("Location ", 120, "LOCATION_END_" + suffix)},
        {"finder", LongName("Finder ", 10, "FINDER_END_" + suffix)},
        {"game", LongName("Game ", 12, "GAME_END_" + suffix)},
    };
}

static void RequireFullRow(const std::string& rendered, const Json& row) {
    for (const auto* field : {"item", "recipient", "location", "finder", "game"})
        Require(rendered.find(row.at(field).get<std::string>()) != std::string::npos,
                "A complete hint field or its distinguishing suffix was lost.");
}

int main() {
    Json report = {{"status", "passed"}, {"cases", Json::array()}};
    auto run = [&](const char* name, auto test) {
        test();
        report["cases"].push_back(name);
    };

    run("long_utf8_literal_preserved", [] {
        const auto name = LongName("Beginning ", 512, "DISTINGUISHING_END");
        Require(SohExtreme::HintLiteral(name) == name, "A long UTF-8 literal was shortened.");
    });

    run("textbox_markers_are_literal", [] {
        std::string input;
        for (int c = 0; c < 0x20; ++c) input += static_cast<char>(c);
        input += '\x7f';
        input += "%&^@#$[]";
        Require(SohExtreme::HintLiteral(input) == std::string(input.size(), ' '),
                "A textbox control marker, including $, survived literal sanitization.");
        const std::string normal = "Éclair's (West) -> Room 42: Key!";
        Require(SohExtreme::HintLiteral(normal) == normal, "Normal text or UTF-8 was changed.");
    });

    run("single_hint_exceeds_old_font_limit_without_truncation", [&] {
        const auto row = Row(0);
        SohExtreme::InGameHintData hints;
        Require(hints.Load(Json{{"hint", Json::array({row})}}.dump()), "Valid hint did not load.");
        const auto rendered = hints.Get("hint");
        RequireFullRow(rendered, row);
        Require(rendered.size() > 1280, "The fixture must exceed the old native buffer limit.");
        Require(rendered.find("...") == std::string::npos, "Hint text was abbreviated.");
        report["single_hint_bytes"] = rendered.size();
    });

    for (const size_t count : {8u, 12u}) {
        run(count == 8 ? "eight_rows_keep_complete_names" : "more_than_eight_rows_are_preserved", [&] {
            Json rows = Json::array();
            for (size_t i = 0; i < count; ++i) rows.push_back(Row(i));
            SohExtreme::InGameHintData hints;
            Require(hints.Load(Json{{"hint", rows}}.dump()), "Valid multi-target hint did not load.");
            const auto rendered = hints.Get("hint");
            size_t previous = 0;
            for (const auto& row : rows) {
                RequireFullRow(rendered, row);
                const auto position = rendered.find(row.at("item").get<std::string>(), previous);
                Require(position != std::string::npos, "Target order was changed or a target was dropped.");
                previous = position + 1;
            }
            Require(static_cast<size_t>(std::count(rendered.begin(), rendered.end(), '^')) == count - 1,
                    "Each complete target should retain its own native page separator.");
            Require(rendered.find("...") == std::string::npos, "A multi-target hint was abbreviated.");
            report[std::to_string(count) + "_row_hint_bytes"] = rendered.size();
        });
    }

    run("loaded_fields_cannot_inject_native_directives", [] {
        const auto unsafe = std::string("Name$0%r^&@#[[1]]") + '\x04';
        Json row = {{"item", unsafe}, {"recipient", unsafe}, {"location", unsafe},
                    {"finder", unsafe}, {"game", unsafe}};
        SohExtreme::InGameHintData hints;
        Require(hints.Load(Json{{"hint", Json::array({row})}}.dump()), "Literal fixture did not load.");
        const auto rendered = hints.Get("hint");
        Require(rendered.find_first_of("$%&^@#[]") == std::string::npos,
                "A field injected a native formatting marker.");
        Require(rendered.find('\x04') == std::string::npos, "A field injected a native page command.");
        Require(rendered.find(SohExtreme::HintLiteral(unsafe)) != std::string::npos,
                "Sanitized field content was lost.");
    });

    run("invalid_and_oversize_snapshots_preserve_previous_data", [] {
        SohExtreme::InGameHintData hints;
        Require(!hints.Load("{"), "Invalid JSON was accepted.");
        Require(!hints.IsLoaded(), "Invalid JSON marked an initial snapshot loaded.");
        Require(hints.Load(Json{{"hint", Json::array({Row(0)})}}.dump()), "Valid snapshot did not load.");
        const auto original = hints.Get("hint");
        for (const auto& invalid : {std::string("[1,2]"), std::string("null"),
                                   std::string("{"), std::string(8 * 1024 * 1024 + 1, ' ')}) {
            Require(!hints.Load(invalid), "An invalid or oversize snapshot was accepted.");
            Require(hints.IsLoaded() && hints.Get("hint") == original,
                    "Rejected data replaced the last valid hint snapshot.");
        }
    });

    run("legacy_labels_and_clear_behavior", [] {
        const auto key = LongName("Legacy hint ", 30, "LEGACY_KEY_END");
        SohExtreme::InGameHintData hints;
        const Json rows = Json::array({nullptr, 42, Json::object(),
                                      Json{{"location", 12}, {"finder", "Player"}},
                                      Json{{"location", "Original location"}, {"finder", "Player"},
                                           {"game", "SOH-EXTREME"}}});
        Require(hints.Load(Json{{key, rows}}.dump()), "A legacy hint did not load.");
        Require(hints.Get(key) == key + ": Original location in Player's world (SOH-EXTREME).",
                "A complete legacy label was lost or invalid rows were accepted.");
        Require(hints.Get("unknown").empty(), "An unknown hint returned another hint's content.");
        hints.Clear();
        Require(!hints.IsLoaded() && hints.Get(key).empty(), "Clear retained hint data.");
    });

    run("native_item_description_preserves_complete_item_and_recipient", [] {
        ArchipelagoClient client;
        const auto row = Row(0);
        auto& scout = client.scoutedLocations[client.resolvedLocation];
        scout.itemName = row.at("item");
        scout.playerName = row.at("recipient");
        Require(client.GetHintItemDescription(RC_TEST_HINT) == scout.itemName + " for " + scout.playerName,
                "The native item description shortened an item or recipient.");
        scout.playerName.clear();
        scout.playerId = 42;
        Require(client.GetHintItemDescription(RC_TEST_HINT) == scout.itemName + " for Player 42",
                "The existing player-ID fallback changed.");
        client.resolvedLocation = -1;
        Rando::StaticData::vanillaItem.name.english = LongName("Vanilla ", 40, "VANILLA_END");
        Require(client.GetHintItemDescription(RC_TEST_HINT) == Rando::StaticData::vanillaItem.name.english,
                "An unshuffled reward's full item name was lost.");
        client.gameplayActive = false;
        Require(client.GetHintItemDescription(RC_TEST_HINT).empty(), "Inactive gameplay exposed AP hints.");
    });

    run("native_supplied_hint_keeps_all_targets", [] {
        Json rows = Json::array();
        for (size_t i = 0; i < 12; ++i) rows.push_back(Row(i));
        ArchipelagoClient client;
        Require(client.inGameHints.Load(Json{{"hint", rows}}.dump()), "Supplied hints did not load.");
        const auto rendered = client.GetInGameHint("hint");
        for (const auto& row : rows) RequireFullRow(rendered, row);
    });

    run("native_older_seed_fallback_preserves_complete_fields", [] {
        ArchipelagoClient client;
        const auto row = Row(0);
        auto& scout = client.scoutedLocations[client.resolvedLocation];
        scout.itemName = row.at("item");
        scout.playerName = row.at("recipient");
        scout.locationName = row.at("location");
        const auto expected = scout.itemName + " for " + scout.playerName +
                              " can be found at " + scout.locationName + " in your world.";
        Require(client.GetInGameHint("gossip", 0) == expected,
                "An older-seed gossip fallback shortened its content.");
        Require(client.GetInGameHint("missing").empty(), "Unloaded static hint did not wait for its snapshot.");
        Require(client.inGameHints.Load("{}"), "An empty valid snapshot did not load.");
        Require(client.GetInGameHint("missing") ==
                    "This seed did not store this hint's target. Another lead:^" + expected,
                "The missing-target fallback shortened its lead.");
        scout.itemName = "$0Item^";
        scout.playerName = "%rPlayer@";
        scout.locationName = "Location&[[1]]";
        const auto safe = client.GetInGameHint("gossip", 0);
        Require(safe.find_first_of("$%&^@#[]") == std::string::npos,
                "An older-seed fallback injected formatting controls.");
        client.gameplayActive = false;
        Require(client.GetInGameHint("gossip", 0).empty(), "Inactive gameplay exposed a fallback hint.");
    });

    run("merchant_hints_and_remote_presentations_keep_complete_names", [] {
        ArchipelagoClient client;
        auto& scout = client.scoutedLocations[client.resolvedLocation];
        scout.itemName = LongName("Merchant item ", 70, "ITEM_END");
        scout.playerName = LongName("Recipient ", 60, "PLAYER_END");
        scout.playerId = 2;
        Require(client.GetRemoteItemDescription(RC_TEST_HINT) ==
                    scout.itemName + " for " + scout.playerName + "'s world",
                "A merchant hint still abbreviated the complete item/recipient name.");
        Require(ApMessageName(scout.itemName) == scout.itemName,
                "The shared remote presentation formatter shortened the name.");
        scout.itemName = "$0Item^[[1]]";
        scout.playerName = "%rPlayer@";
        Require(client.GetRemoteItemDescription(RC_TEST_HINT).find_first_of("$%&^@#[]") == std::string::npos,
                "A merchant name injected native formatting.");
        scout.playerId = AP_GetPlayerID();
        Require(client.GetRemoteItemDescription(RC_TEST_HINT).empty(), "A local item became a remote hint.");
    });

    report["case_count"] = report.at("cases").size();
    std::cout << report.dump() << '\n';
}
