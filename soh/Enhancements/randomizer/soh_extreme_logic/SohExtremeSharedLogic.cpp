#include "SohExtremeSharedLogic.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>

namespace SohExtreme {
namespace {

std::string Trim(std::string s) {
    auto notSpace = [](unsigned char c) { return !std::isspace(c); };
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), notSpace));
    s.erase(std::find_if(s.rbegin(), s.rend(), notSpace).base(), s.end());
    return s;
}

std::string Lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

bool EndsWith(const std::string& text, const std::string& suffix) {
    return text.size() >= suffix.size() && text.compare(text.size() - suffix.size(), suffix.size(), suffix) == 0;
}

bool StartsWith(const std::string& text, const std::string& prefix) {
    return text.size() >= prefix.size() && text.compare(0, prefix.size(), prefix) == 0;
}

RequirementAtom ParseSettingAtom(std::string token) {
    token = Trim(token);
    bool negated = false;
    if (!token.empty() && token.front() == '!') {
        negated = true;
        token = Trim(token.substr(1));
    }
    std::string key = token;
    std::string value = "true";
    size_t eq = token.find('=');
    if (eq != std::string::npos) {
        key = Trim(token.substr(0, eq));
        value = Lower(Trim(token.substr(eq + 1)));
    }
    return RequirementAtom{AtomKind::Setting, key, value, negated};
}

bool SettingIsTrue(const SettingMap& settings, const std::string& key, const std::string& expected) {
    auto it = settings.find(key);
    std::string actual = it == settings.end() ? "false" : Lower(it->second);
    return actual == Lower(expected);
}

} // namespace

RequirementBranch ParseRequirementBranch(const std::string& branchText) {
    RequirementBranch branch;
    std::stringstream ss(branchText);
    std::string token;
    while (std::getline(ss, token, ';')) {
        token = Trim(token);
        if (token.empty()) {
            continue;
        }
        if (token.front() == '[' && token.back() == ']') {
            branch.atoms.push_back(ParseSettingAtom(token.substr(1, token.size() - 2)));
        } else {
            branch.atoms.push_back(RequirementAtom{AtomKind::Item, token, "true", false});
        }
    }
    return branch;
}

bool BranchSatisfied(const RequirementBranch& branch, const ItemSet& items, const SettingMap& settings) {
    for (const RequirementAtom& atom : branch.atoms) {
        bool result = false;
        if (atom.kind == AtomKind::Item) {
            result = items.count(atom.name) != 0;
        } else {
            result = SettingIsTrue(settings, atom.name, atom.value);
        }
        if (atom.negated) {
            result = !result;
        }
        if (!result) {
            return false;
        }
    }
    return true;
}

bool CheckEnabled(const CheckDef& check, const SettingMap& settings) {
    if (check.settingRequired.empty()) {
        return true;
    }
    RequirementBranch req;
    req.atoms.push_back(ParseSettingAtom(check.settingRequired));
    return BranchSatisfied(req, {}, settings);
}

bool CheckReachable(const CheckDef& check, const ItemSet& items, const SettingMap& settings, const RegionReachable& regionReachable) {
    if (!CheckEnabled(check, settings)) {
        return false;
    }
    if (regionReachable && !regionReachable(check.region)) {
        return false;
    }
    if (check.requirements.empty()) {
        return true;
    }
    for (const RequirementBranch& branch : check.requirements) {
        if (BranchSatisfied(branch, items, settings)) {
            return true;
        }
    }
    return false;
}

bool IsSoulItem(const std::string& itemName) {
    static const std::set<std::string> souls = {
        "Enemy Soul", "NPC Soul", "Animal Soul", "Pot Soul", "Crate Soul", "Grass / Bush Soul",
        "Rock / Boulder Soul", "Tree Soul", "Beehive Soul", "Scrub Soul", "Sign Soul", "Icicle Soul", "Red Ice Soul",
    };
    return souls.count(itemName) != 0 || EndsWith(itemName, " Soul");
}

bool IsSongNoteItem(const std::string& itemName) {
    if (StartsWith(itemName, "Song Note ")) {
        const std::string suffix = itemName.substr(std::string("Song Note ").size());
        if (!suffix.empty() && std::all_of(suffix.begin(), suffix.end(), [](unsigned char c) { return std::isdigit(c); })) {
            const int note = std::stoi(suffix);
            return note >= 1 && note <= 74;
        }
    }
    return EndsWith(itemName, " Note");
}

bool IsTrapItem(const std::string& itemName) {
    return EndsWith(itemName, " Trap") || itemName == "Ice Trap";
}

const std::vector<std::string>& ImportantItemNames() {
    static const std::vector<std::string> items = {
        "Bow", "Slingshot", "Hookshot", "Longshot", "Boomerang", "Megaton Hammer", "Bomb Bag", "Bombchus",
        "Magic Meter", "Dins Fire", "Farores Wind", "Nayrus Love", "Ocarina", "Progressive Ocarina",
        "Progressive Sword", "Progressive Shield", "Progressive Strength", "Progressive Scale", "Progressive Wallet",
        "Progressive Hookshot", "Iron Boots", "Hover Boots", "Lens of Truth", "Goron Tunic", "Zora Tunic",
        "Shovel", "Flow of Time", "Open Chest", "Speak", "Roll", "Grab / Power Bracelet", "Crawl", "Climb",
        "Enemy Soul", "NPC Soul", "Animal Soul", "Pot Soul", "Crate Soul", "Grass / Bush Soul", "Rock / Boulder Soul",
        "Tree Soul", "Beehive Soul", "Scrub Soul", "Sign Soul", "Icicle Soul", "Red Ice Soul",
    };
    return items;
}

bool IsImportantItem(const std::string& itemName) {
    const auto& items = ImportantItemNames();
    if (std::find(items.begin(), items.end(), itemName) != items.end()) {
        return true;
    }
    return IsSoulItem(itemName) || IsSongNoteItem(itemName) || StartsWith(itemName, "Progressive ") ||
           StartsWith(itemName, "Small Key") || StartsWith(itemName, "Boss Key") || StartsWith(itemName, "Silver Rupee");
}

const std::unordered_map<std::string, std::vector<std::string>>& SilverRupeeRooms() {
    static const std::unordered_map<std::string, std::vector<std::string>> rooms = {
        {"Ganons Castle Spirit Trial", {"Ganons Castle Spirit Trial Silver Rupee 1", "Ganons Castle Spirit Trial Silver Rupee 2", "Ganons Castle Spirit Trial Silver Rupee 3", "Ganons Castle Spirit Trial Silver Rupee 4", "Ganons Castle Spirit Trial Silver Rupee 5"}},
        {"Ganons Castle Shadow Trial", {"Ganons Castle Shadow Trial Silver Rupee 1", "Ganons Castle Shadow Trial Silver Rupee 2", "Ganons Castle Shadow Trial Silver Rupee 3", "Ganons Castle Shadow Trial Silver Rupee 4", "Ganons Castle Shadow Trial Silver Rupee 5"}},
        {"Ganons Castle Fire Trial", {"Ganons Castle Fire Trial Silver Rupee 1", "Ganons Castle Fire Trial Silver Rupee 2", "Ganons Castle Fire Trial Silver Rupee 3", "Ganons Castle Fire Trial Silver Rupee 4", "Ganons Castle Fire Trial Silver Rupee 5"}},
        {"Ganons Castle Water Trial", {"Ganons Castle Water Trial Silver Rupee 1", "Ganons Castle Water Trial Silver Rupee 2", "Ganons Castle Water Trial Silver Rupee 3", "Ganons Castle Water Trial Silver Rupee 4", "Ganons Castle Water Trial Silver Rupee 5"}},
        {"Ice Cavern Spinning Scythe", {"Ice Cavern Spinning Scythe Silver Rupee 1", "Ice Cavern Spinning Scythe Silver Rupee 2", "Ice Cavern Spinning Scythe Silver Rupee 3", "Ice Cavern Spinning Scythe Silver Rupee 4", "Ice Cavern Spinning Scythe Silver Rupee 5"}},
        {"Shadow Temple Scythe Shortcut", {"Shadow Temple Scythe Shortcut Silver Rupee 1", "Shadow Temple Scythe Shortcut Silver Rupee 2", "Shadow Temple Scythe Shortcut Silver Rupee 3", "Shadow Temple Scythe Shortcut Silver Rupee 4", "Shadow Temple Scythe Shortcut Silver Rupee 5"}},
        {"Spirit Temple Sun Block", {"Spirit Temple Sun Block Silver Rupee 1", "Spirit Temple Sun Block Silver Rupee 2", "Spirit Temple Sun Block Silver Rupee 3", "Spirit Temple Sun Block Silver Rupee 4", "Spirit Temple Sun Block Silver Rupee 5"}},
    };
    return rooms;
}

bool HasRoomSilverRupees(const std::string& roomName, const ItemSet& items) {
    const auto& rooms = SilverRupeeRooms();
    auto it = rooms.find(roomName);
    if (it == rooms.end() || it->second.empty()) {
        return false;
    }
    for (const std::string& rupee : it->second) {
        if (items.count(rupee) == 0) {
            return false;
        }
    }
    return true;
}

std::vector<std::string> AuditEnabledCheckFamilies(const SettingMap& settings, const std::set<std::string>& registeredTypes) {
    static const std::vector<std::pair<std::string, std::string>> families = {
        {"Pot Sanity", "pots"}, {"Crate Sanity", "crates"}, {"Grass Sanity", "grass_bushes"},
        {"Rock Sanity", "rocks_boulders"}, {"Tree Sanity", "trees"}, {"Beehive Sanity", "beehives"},
        {"Icicle Sanity", "icicles"}, {"Red Ice Sanity", "red_ice"}, {"Scrub Sanity", "scrubs"},
        {"Sign Sanity", "signs"}, {"NPC Speech Sanity", "npc_speech"}, {"Enemy Sanity", "enemy_instances"},
        {"Freestanding Rupees", "freestanding_rupees"}, {"Hidden Rupees", "hidden_rupees"},
        {"Wonder Items", "wonder_items"}, {"Silver Rupees", "silver_rupees"}, {"Shop Sanity", "shops"},
    };
    std::vector<std::string> missing;
    for (const auto& [setting, family] : families) {
        if (SettingIsTrue(settings, setting, "true") && registeredTypes.count(family) == 0) {
            missing.push_back(setting + " enabled but no " + family + " checks were registered");
        }
    }
    return missing;
}

} // namespace SohExtreme
