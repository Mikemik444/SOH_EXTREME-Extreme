#pragma once
// Engine-independent policy, also compiled by tests/enemy_drop_policy_test.cpp.
namespace SohExtreme {
struct EnemyLifeDropState {
    bool deathObserved = false;
    bool defeatHandled = false;
    bool normalDropHandled = false;
    bool rewardWasAp = false;
};
// -1: suppress; 0: leave vanilla handling intact; 1: use shuffled normal loot.
inline int ConsumeNormalEnemyDrop(EnemyLifeDropState& life, bool eligible,
                                 bool enabled, bool hasSoul, bool pendingApCheck) {
    if (!eligible || !enabled) return 0;
    if (!hasSoul || pendingApCheck || life.rewardWasAp || life.normalDropHandled) return -1;
    life.normalDropHandled = true;
    return 1;
}
inline bool EnemyCheckPending(bool apSave, bool active, bool reported, bool collected) {
    return apSave && active && !reported && !collected;
}
inline bool CanConsumeEnemyPickup(bool apSave, bool active, bool reported) {
    return apSave && active && reported;
}
} // namespace SohExtreme
