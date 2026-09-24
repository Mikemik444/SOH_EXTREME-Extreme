#include "SohExtremeCheckFinderBridge.hpp"

namespace SohExtreme {

std::vector<CheckDef> GetAvailableChecksForFinder(const std::vector<CheckDef>& allChecks,
                                                  const ItemSet& currentItems,
                                                  const SettingMap& currentSettings,
                                                  const RegionReachable& regionReachable) {
    std::vector<CheckDef> result;
    for (const CheckDef& check : allChecks) {
        if (CheckReachable(check, currentItems, currentSettings, regionReachable)) {
            result.push_back(check);
        }
    }
    return result;
}

bool IsCheckFinderImportantReward(const std::string& itemName) {
    return IsImportantItem(itemName);
}

} // namespace SohExtreme
