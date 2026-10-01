#ifndef SOH_EXTREME_ACTOR_DRAW_RECOVERY_H
#define SOH_EXTREME_ACTOR_DRAW_RECOVERY_H
#include <stdint.h>

// Exact failure observed in two .43 Market crashes: EnButte_Draw lost its
// upper address bits. Do not guess addresses or repair arbitrary callbacks.
// The caller also checks the actor's native update/destroy identity. This is
// containment of the observed failure, not a diagnosis of the corrupting write.
static inline int SohExtreme_IsTruncatedNativeDraw(uintptr_t actual, uintptr_t expected) {
    return sizeof(uintptr_t) > sizeof(uint32_t) && actual != 0 && expected > UINT32_MAX &&
           actual == (uintptr_t)(uint32_t)expected;
}
#endif
