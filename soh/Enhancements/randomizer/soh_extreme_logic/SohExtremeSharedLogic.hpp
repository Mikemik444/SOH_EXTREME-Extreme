#pragma once

#include <functional>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>

namespace SohExtreme {

enum class AtomKind { Item, Setting };

struct RequirementAtom {
    AtomKind kind = AtomKind::Item;
    std::string name;
    std::string value = "true";
    bool negated = false;
};

struct RequirementBranch {
    std::vector<RequirementAtom> atoms;
};

struct CheckDef {
    std::string name;
    std::string region;
    std::vector<RequirementBranch> requirements;
    std::string settingRequired;
    std::string type;
    std::string room;
    int64_t apId = -1;
};

using ItemSet = std::set<std::string>;
using SettingMap = std::unordered_map<std::string, std::string>;
using RegionReachable = std::function<bool(const std::string&)>;

RequirementBranch ParseRequirementBranch(const std::string& branchText);
bool BranchSatisfied(const RequirementBranch& branch, const ItemSet& items, const SettingMap& settings);
bool CheckEnabled(const CheckDef& check, const SettingMap& settings);
bool CheckReachable(const CheckDef& check, const ItemSet& items, const SettingMap& settings, const RegionReachable& regionReachable);

bool IsSoulItem(const std::string& itemName);
bool IsSongNoteItem(const std::string& itemName);
bool IsImportantItem(const std::string& itemName);
bool IsTrapItem(const std::string& itemName);

const std::vector<std::string>& ImportantItemNames();
const std::unordered_map<std::string, std::vector<std::string>>& SilverRupeeRooms();
bool HasRoomSilverRupees(const std::string& roomName, const ItemSet& items);
std::vector<std::string> AuditEnabledCheckFamilies(const SettingMap& settings, const std::set<std::string>& registeredTypes);

} // namespace SohExtreme
