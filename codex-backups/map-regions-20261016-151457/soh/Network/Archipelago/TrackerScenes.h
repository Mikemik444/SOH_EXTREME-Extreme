#pragma once
#include "TrackerMirror.h"
#include <algorithm>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace SohExtreme {
struct TrackerScene {
    int scene = -1;
    int instance = 0;
    std::string name = "Other checks";
    int area = -1; // Broad physical region; separate from the scene/instance key.

    std::pair<int, int> Key() const { return { scene, instance }; }
    bool Matches(const TrackerScene& other) const {
        return scene >= 0 && instance >= 0 && Key() == other.Key();
    }
};

struct TrackerSceneGroup {
    TrackerScene scene;
    std::vector<const TrackerRow*> rows;
    size_t normal = 0;
    size_t glitched = 0;
    bool currentScene = false;
    bool currentRegion = false;
};

// The existing wire format carries UT's age annotations as a terminal suffix.
// Read only those exact suffixes; aliases and location names may mention ages.
// Zero means an older/unknown row, not an unreachable check.
inline uint8_t TrackerRowAgeMask(const TrackerRow& row) {
    const auto endsWith = [&](const std::string& suffix) {
        return row.name.size() >= suffix.size() &&
               row.name.compare(row.name.size() - suffix.size(), suffix.size(), suffix) == 0;
    };
    // Accept prior APWorld labels as well as the current compact wording.
    if (endsWith(" [Child]") || endsWith(" [Child only]")) return 1;
    if (endsWith(" [Adult]") || endsWith(" [Adult only]")) return 2;
    if (endsWith(" [Any age]") || endsWith(" [Child / Adult]")) return 3;
    return 0;
}

inline bool TrackerRowMatchesAge(const TrackerRow& row, bool adult) {
    const uint8_t ages = TrackerRowAgeMask(row);
    // Keep older snapshots usable instead of silently hiding unknown checks.
    return ages == 0 || (ages & (adult ? 2 : 1)) != 0;
}

// Select a moving NPC's route for this age/time before preferring a local
// route. Merely sharing its AP parent must never make another scene current.
inline int TrackerSceneRoutePriority(const TrackerScene& route, const TrackerScene& current,
                                     int routeAge, int routeTime, int age, int time) {
    return ((routeAge < 0 || routeAge == age) ? 4 : 0) +
           ((routeTime < 0 || routeTime == time) ? 2 : 0) + (route.Matches(current) ? 1 : 0);
}

// Display-only: retain each input row/status exactly once and resolve once per
// row. Physical scene keys, never AP logical region names, define the groups.
template <typename SceneResolver, typename Filter>
std::vector<TrackerSceneGroup> GroupTrackerRowsByScene(const TrackerSnapshot& snapshot,
    const TrackerScene& current, bool currentFirst, bool onlyCurrent, SceneResolver sceneForId, Filter filter) {
    std::map<std::pair<int, int>, TrackerSceneGroup> grouped;
    for (const auto& row : snapshot.rows) {
        const auto scene = sceneForId(row.id);
        if (!filter(row, scene)) continue;
        const bool here = scene.Matches(current);
        if (onlyCurrent && !here) continue;
        auto& group = grouped[scene.Key()];
        group.scene = scene;
        group.currentScene = here;
        group.currentRegion = scene.area >= 0 && scene.area == current.area;
        group.rows.push_back(&row);
        if (row.state == 1) ++group.normal;
        else ++group.glitched;
    }
    std::vector<TrackerSceneGroup> result;
    for (auto& [key, group] : grouped) {
        std::sort(group.rows.begin(), group.rows.end(), [](const TrackerRow* a, const TrackerRow* b) {
            if (a->state != b->state) return a->state < b->state;
            if (a->name != b->name) return a->name < b->name;
            return a->id < b->id;
        });
        result.push_back(std::move(group));
    }
    std::sort(result.begin(), result.end(), [currentFirst](const TrackerSceneGroup& a, const TrackerSceneGroup& b) {
        if (currentFirst && a.currentScene != b.currentScene) return a.currentScene;
        if (currentFirst && a.currentRegion != b.currentRegion) return a.currentRegion;
        if ((a.scene.scene < 0) != (b.scene.scene < 0)) return a.scene.scene >= 0;
        if (a.scene.name != b.scene.name) return a.scene.name < b.scene.name;
        return a.scene.Key() < b.scene.Key();
    });
    return result;
}
} // namespace SohExtreme
