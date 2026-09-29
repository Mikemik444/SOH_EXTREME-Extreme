#pragma once
#include <cstdint>

namespace SohExtreme {
// Match only actual characters. Dialogue IDs, shop contents, item rewards and
// receipt order never select the identity. All optional fields are explicit.
struct NpcSpeechIdentity {
    int64_t location;
    int actor, scene, mask, params, room, age, language;
    bool matchHome;
    int home[3];
};
inline constexpr NpcSpeechIdentity kNpcSpeechIdentities[] = {
#include "NpcSpeechIdentityTable.inc"
};
inline const NpcSpeechIdentity* ResolveNpcSpeechIdentity(int actor, int scene, int params,
        int room, bool adult, int homeX, int homeY, int homeZ) {
    for (const auto& e : kNpcSpeechIdentities) {
        if (e.actor != actor || (e.scene >= 0 && e.scene != scene) ||
            (static_cast<uint16_t>(params) & e.mask) != e.params ||
            (e.room >= 0 && e.room != room) || (e.age >= 0 && e.age != (adult ? 1 : 0))) continue;
        if (e.matchHome && (homeX != e.home[0] || homeY != e.home[1] || homeZ != e.home[2])) continue;
        return &e;
    }
    return nullptr;
}
} // namespace SohExtreme
