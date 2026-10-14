#pragma once
#include <cstdio>
#include <cstring>

namespace SohExtreme {
// Release labels are metadata, not a save schema or an AP seed identity.
// Updating only these fields preserves all inventory, checks and receipt data.
template <typename Stats>
bool UpdateSaveBuildVersion(Stats& stats, const char* version, int major, int minor, int patch) {
    const bool changed = std::strncmp(stats.buildVersion, version, sizeof(stats.buildVersion)) != 0 ||
                         stats.buildVersionMajor != major || stats.buildVersionMinor != minor ||
                         stats.buildVersionPatch != patch;
    if (changed) {
        std::snprintf(stats.buildVersion, sizeof(stats.buildVersion), "%s", version);
        stats.buildVersionMajor = major;
        stats.buildVersionMinor = minor;
        stats.buildVersionPatch = patch;
    }
    return changed;
}
} // namespace SohExtreme
