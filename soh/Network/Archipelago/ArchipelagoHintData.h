#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <nlohmann/json.hpp>

namespace SohExtreme {
// AP names are literal text, never textbox directives or InsertNames tokens.
inline std::string HintLiteral(const std::string& input, size_t limit = 120) {
    std::string result;
    for (unsigned char c : input) {
        result += c < 0x20 || c == 0x7f || c == '%' || c == '&' || c == '^' || c == '@' ||
                          c == '#' || c == '[' || c == ']' ? ' ' : static_cast<char>(c);
    }
    if (result.size() > limit) {
        size_t end = limit;
        while (end && (static_cast<unsigned char>(result[end]) & 0xc0) == 0x80) --end;
        result.resize(end);
        result += "...";
    }
    return result;
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
                auto field = [&](const char* name, size_t limit) -> std::string {
                    auto found = row.find(name);
                    return found != row.end() && found->is_string() ? HintLiteral(found->get<std::string>(), limit) : "";
                };
                const auto item = field("item", 64), recipient = field("recipient", 32);
                const auto location = field("location", 120), finder = field("finder", 32), game = field("game", 48);
                if (location.empty() || finder.empty()) continue;
                next[it.key()].push_back({item, recipient, location, finder, game});
                // Slots cannot expand a single native hint without bound.
                if (next[it.key()].size() == 8) break;
            }
        }
        entries = std::move(next);
        loaded = true;
        return true;
    }
    std::string Get(const std::string& key) const {
        auto it = entries.find(key);
        if (it == entries.end()) return {};
        auto render = [&](size_t unit, bool compact) {
            std::string result;
            for (const auto& row : it->second) {
                if (!result.empty()) result += "^";
                if (!row.item.empty()) result += HintLiteral(row.item, unit * 2) +
                    (row.recipient.empty() ? "" : " for " + HintLiteral(row.recipient, unit)) + ": ";
                result += HintLiteral(row.location, unit * 3) + (compact ? " [" : " in ") + HintLiteral(row.finder, unit);
                result += compact ? " / " : "'s world (";
                result += HintLiteral(row.game, unit);
                result += compact ? "]." : ").";
            }
            return result;
        };
        auto result = render(120, false);
        // The native font buffer is 1280 bytes. Reserve space for wrapping and
        // the altar's bridge/key/win-condition text, retaining every target.
        if (result.size() > 600) result = render((600 / it->second.size() - 32) / 8, true);
        // Legacy pairs have no reliable item-to-destination association.
        if (!it->second.empty() && it->second.front().item.empty())
            result = HintLiteral(key, 64) + ": " + result;
        return result;
    }
  private:
    struct Entry { std::string item, recipient, location, finder, game; };
    bool loaded = false;
    std::unordered_map<std::string, std::vector<Entry>> entries;
};
} // namespace SohExtreme
