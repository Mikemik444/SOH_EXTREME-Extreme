#pragma once
#include <cstddef>
#include <cstdint>
namespace SohExtreme {
// Authored entries whose object dependencies are absent in the original scenes.
// Reserve their old IDs for explicit AP slot-manifest compatibility only.
inline bool IsUnusedObjectEnemyPlacement(int32_t index) {
    return index == 552 || (index >= 621 && index <= 627);
}
// Retired 0.11.12 Peahat larval slots. Keep the receipt table append-only,
// but never bind or award these identities, even with stale server slot data.
inline bool IsEnemyOffspringPlacement(int32_t index) {
    return index >= 765 && index <= 785;
}
// Keep receipt indices stable when removing nonexistent grotto placements.
// These came from confusing the scene's entrance number with its room number.
inline bool IsRetiredEnemyPlacement(int32_t index) {
    return IsEnemyOffspringPlacement(index) || index == 496 || index == 497 || index == 498 ||
           index == 503 || index == 504 || index == 507;
}
// Exact resource identity, recorded before actor init mutates params/home/room.
struct EnemySpawnKey {
    int16_t scene, room, grotto, actorIndex, actorId;
    uint16_t params;
    int32_t x, y, z;
};
inline bool SameEnemySpawn(const EnemySpawnKey& a, const EnemySpawnKey& b) {
    return a.scene == b.scene && a.room == b.room && a.grotto == b.grotto &&
        a.actorIndex == b.actorIndex && a.actorId == b.actorId && a.params == b.params &&
        a.x == b.x && a.y == b.y && a.z == b.z;
}
struct EnemySpawnAlias { EnemySpawnKey key; int32_t placement; };
struct EnemyChildAlias {
    EnemySpawnKey source;
    int16_t childId;
    uint16_t params, mask;
    int16_t slot;
    int32_t placement;
};
static constexpr EnemySpawnAlias kEnemySpawnAliases[] = {
#include "EnemySpawnAliases.inc"
};
static constexpr EnemyChildAlias kEnemyChildAliases[] = {
#include "EnemyChildAliases.inc"
};
inline int32_t FindExactEnemySpawn(const EnemySpawnKey& key) {
    for (const auto& entry : kEnemySpawnAliases)
        if (!IsRetiredEnemyPlacement(entry.placement) && SameEnemySpawn(key, entry.key)) return entry.placement;
    return -1;
}
template <typename Occupied>
inline int32_t FindExactEnemyChild(const EnemySpawnKey& source, int16_t childId,
                                  uint16_t params, int16_t slot, Occupied occupied) {
    for (const auto& entry : kEnemyChildAliases) {
        if (!IsRetiredEnemyPlacement(entry.placement) && SameEnemySpawn(source, entry.source) && entry.childId == childId &&
            (params & entry.mask) == (entry.params & entry.mask) &&
            (slot < 0 || entry.slot == slot) && !occupied(entry.placement)) return entry.placement;
    }
    return -1;
}
} // namespace SohExtreme
