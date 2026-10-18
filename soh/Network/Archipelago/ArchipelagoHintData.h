#pragma once

#include <string>
#include <limits>
#include <vector>
#include <unordered_map>
#include <utility>
#include <nlohmann/json.hpp>
#include "ArchipelagoHintTarget.h"

namespace SohExtreme {
// AP names are literal text, never textbox directives or InsertNames tokens.
// Keep complete names here; textbox wrapping and paging handle display limits.
inline std::string HintLiteral(const std::string& input) {
    std::string result;
    result.reserve(input.size());
    for (unsigned char c : input) {
        result += c < 0x20 || c == 0x7f || c == '%' || c == '&' || c == '^' || c == '@' ||
                          c == '#' || c == '$' || c == '[' || c == ']' ? ' ' : static_cast<char>(c);
    }
    return result;
}

inline std::string HintString(const nlohmann::json& row, const char* key) {
    auto value = row.find(key);
    return value != row.end() && value->is_string() ? value->get<std::string>() : "";
}

inline int64_t HintInteger(const nlohmann::json& row, const char* key, int64_t fallback = -1) {
    auto value = row.find(key);
    if (value == row.end() || !value->is_number_integer()) return fallback;
    if (value->is_number_unsigned() && value->get<uint64_t>() > uint64_t(std::numeric_limits<int64_t>::max()))
        return fallback;
    return value->get<int64_t>();
}

inline HintTarget ReadHintTarget(const nlohmann::json& row) {
    HintTarget target;
    target.locationId = HintInteger(row, "location_id");
    target.itemId = HintInteger(row, "item_id");
    const auto finder = HintInteger(row, "finding_player", 0);
    const auto recipient = HintInteger(row, "receiving_player", 0);
    const auto flags = HintInteger(row, "item_flags");
    if (finder > 0 && finder <= std::numeric_limits<int>::max()) target.finderId = static_cast<int>(finder);
    if (recipient > 0 && recipient <= std::numeric_limits<int>::max()) target.recipientId = static_cast<int>(recipient);
    if (flags >= 0 && flags <= std::numeric_limits<int>::max()) target.flags = static_cast<int>(flags);
    const auto starting = row.find("starting");
    target.starting = starting != row.end() && starting->is_boolean() && starting->get<bool>();
    target.item = HintString(row, "item");
    target.location = HintString(row, "location");
    target.finder = HintString(row, "finder");
    target.recipient = HintString(row, "recipient");
    target.game = HintString(row, "location_game");
    if (target.game.empty()) target.game = HintString(row, "game");
    target.entrance = HintString(row, "entrance");
    return target;
}

class InGameHintData {
  public:
    void Clear() { entries.clear(); loaded = false; }
    bool IsLoaded() const { return loaded; }
    bool Load(const std::string& raw) {
        if (raw.size() > 8 * 1024 * 1024) return false;
        auto data = nlohmann::json::parse(raw, nullptr, false);
        if (!data.is_object()) return false;
        std::unordered_map<std::string, std::vector<Entry>> next;
        for (auto it = data.begin(); it != data.end(); ++it) {
            if (!it.value().is_array()) continue;
            for (const auto& row : it.value()) {
                if (!row.is_object()) continue;
                const auto type = HintString(row, "type");
                if (type == "woth" || type == "barren") {
                    const auto area = HintString(row, "area"), finder = HintString(row, "finder");
                    if (area.empty() || finder.empty()) continue;
                    const auto scope = "the checks in " + HintLiteral(area) + " in " + HintLiteral(finder) + "'s world";
                    const auto text = type == "woth" ? "They say that " + scope + " are on the way of the hero."
                                                      : "They say that " + scope + " are barren of progression items.";
                    next[it.key()].push_back({{}, text});
                    continue;
                }
                if (type == "text") {
                    const auto text = HintString(row, "text");
                    if (!text.empty()) next[it.key()].push_back({{}, HintLiteral(text)});
                    continue;
                }
                if (!type.empty() && type != "item") continue;
                auto target = ReadHintTarget(row);
                if (target.location.empty() || target.finder.empty()) continue;
                next[it.key()].push_back({std::move(target), {}});
            }
        }
        entries = std::move(next);
        loaded = true;
        return true;
    }
    std::string Get(const std::string& key) const {
        auto it = entries.find(key);
        if (it == entries.end()) return {};
        std::string result;
        for (const auto& entry : it->second) {
            if (!result.empty()) result += "^";
            if (!entry.text.empty()) {
                result += entry.text;
                continue;
            }
            const auto& row = entry.target;
            if (!row.item.empty()) result += HintLiteral(row.item) +
                (row.recipient.empty() ? "" : " for " + HintLiteral(row.recipient)) + ": ";
            result += HintLiteral(row.location) + " in " + HintLiteral(row.finder) + "'s world (" + HintLiteral(row.game) + ").";
        }
        // Legacy pairs have no reliable item-to-destination association.
        if (!it->second.empty() && it->second.front().text.empty() && it->second.front().target.item.empty())
            result = HintLiteral(key) + ": " + result;
        return result;
    }
    std::vector<HintTarget> Targets(const std::string& key) const {
        const auto found = entries.find(key);
        if (found == entries.end()) return {};
        std::vector<HintTarget> targets;
        for (const auto& entry : found->second)
            if (entry.text.empty() && !entry.target.item.empty() && !entry.target.starting)
                targets.push_back(entry.target);
        return targets;
    }
  private:
    struct Entry { HintTarget target; std::string text; };
    bool loaded = false;
    std::unordered_map<std::string, std::vector<Entry>> entries;
};

struct ServerHintRecord {
    HintTarget target;
    bool found = false;
};

struct ServerHintSnapshot {
    std::string nonce, producer;
    int slot = 0;
    uint64_t request = 0, revision = 0;
    std::vector<ServerHintRecord> rows;
};

// The managed AP CommonClient transports only its already-revealed server
// hints. Validate the complete reply before replacing a visible snapshot.
inline bool ReadServerHintSnapshot(const std::string& raw, ServerHintSnapshot& result) {
    if (raw.size() > 8 * 1024 * 1024) return false;
    const auto data = nlohmann::json::parse(raw, nullptr, false);
    if (!data.is_object() || HintString(data, "soh_extreme_tracker") != "SOHExtremeFinder1" ||
        HintString(data, "kind") != "hint_snapshot") return false;
    ServerHintSnapshot next;
    next.nonce = HintString(data, "nonce");
    next.producer = HintString(data, "producer");
    const auto slot = HintInteger(data, "slot", 0), request = HintInteger(data, "request"),
               revision = HintInteger(data, "revision");
    const auto rows = data.find("rows");
    if (next.nonce.empty() || next.nonce.size() > 64 || next.producer.empty() || next.producer.size() > 64 ||
        slot <= 0 || slot > std::numeric_limits<int>::max() || request < 0 || revision < 0 ||
        rows == data.end() || !rows->is_array() || rows->size() > 20000) return false;
    next.slot = static_cast<int>(slot);
    next.request = static_cast<uint64_t>(request);
    next.revision = static_cast<uint64_t>(revision);
    for (const auto& row : *rows) {
        if (!row.is_object()) return false;
        auto target = ReadHintTarget(row);
        const auto found = row.find("found");
        if (!target.HasLocation() || target.itemId < 0 || target.recipientId <= 0 ||
            target.flags < 0 || target.item.empty() || target.location.empty() ||
            target.finder.empty() || target.recipient.empty() || found == row.end() || !found->is_boolean()) return false;
        if (target.IsProgression()) next.rows.push_back({std::move(target), found->get<bool>()});
    }
    result = std::move(next);
    return true;
}
} // namespace SohExtreme
