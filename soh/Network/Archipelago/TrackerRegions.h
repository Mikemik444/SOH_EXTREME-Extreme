#pragma once
#include "TrackerMirror.h"
#include <algorithm>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace SohExtreme {
struct TrackerRegionGroup {
    std::string region;
    std::vector<const TrackerRow*> rows;
    size_t normal = 0;
    size_t glitched = 0;
    bool currentArea = false;
    bool sharedRegion = false;
};
// Display-only transformation: every input ID/status is retained exactly once.
// Area resolver uses the native AP-ID map for highlighting, not reachability.
template <typename AreaResolver, typename Filter>
std::vector<TrackerRegionGroup> GroupTrackerRows(const TrackerSnapshot& snapshot, int currentArea,
                                                bool currentFirst, bool onlyCurrent,
                                                AreaResolver areaForId, Filter filter) {
    // A shared NPC can be physically present in Kakariko while its AP parent
    // region is Market. Never let that one row mark all Market checks as here.
    std::map<std::pair<std::string, bool>, TrackerRegionGroup> grouped;
    std::map<std::string, std::set<int>> regionAreas;
    for (const auto& row : snapshot.rows) {
        const int area = areaForId(row.id);
        regionAreas[row.region].insert(area);
        if (!filter(row)) continue;
        const bool here = currentArea >= 0 && area == currentArea;
        if (onlyCurrent && !here) continue;
        auto& group = grouped[{row.region, here}];
        group.region = row.region.empty() ? "Unassigned region" : row.region;
        group.currentArea = here;
        group.rows.push_back(&row);
        if (row.state == 1) ++group.normal;
        else ++group.glitched;
    }
    std::vector<TrackerRegionGroup> result;
    for (auto& entry : grouped) {
        auto& group = entry.second;
        group.sharedRegion = regionAreas[entry.first.first].size() > 1;
        std::sort(group.rows.begin(), group.rows.end(), [](const TrackerRow* a, const TrackerRow* b) {
            if (a->state != b->state) return a->state < b->state;
            if (a->name != b->name) return a->name < b->name;
            return a->id < b->id;
        });
        result.push_back(std::move(group));
    }
    std::stable_sort(result.begin(), result.end(), [currentFirst](const TrackerRegionGroup& a, const TrackerRegionGroup& b) {
        if (currentFirst && a.currentArea != b.currentArea) return a.currentArea;
        return a.region < b.region;
    });
    return result;
}
} // namespace SohExtreme
