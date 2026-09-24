#pragma once

#include "SohExtremeSharedLogic.hpp"

#include <string>
#include <vector>

namespace SohExtreme {

// Bridge used by Check Finder and Archipelago UI code. Feed this with the same CheckDef table
// used by generation, the current save inventory, and a region-reachability callback from SoH.
std::vector<CheckDef> GetAvailableChecksForFinder(const std::vector<CheckDef>& allChecks,
                                                  const ItemSet& currentItems,
                                                  const SettingMap& currentSettings,
                                                  const RegionReachable& regionReachable);

bool IsCheckFinderImportantReward(const std::string& itemName);

} // namespace SohExtreme
