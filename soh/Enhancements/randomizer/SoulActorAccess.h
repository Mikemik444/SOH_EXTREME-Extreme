#pragma once

#include <stdbool.h>
#include <stdint.h>

struct Actor;

#ifdef __cplusplus
extern "C" {
#endif

// These NPCs retain their normal path blocking and player interactions while
// hidden. Language, item, story, and other vanilla requirements still apply.
bool MegaSoul_IsPathBlockingNpcPlacement(int16_t actorId, int16_t params, int16_t scene);
bool MegaSoul_IsPathBlockingNpc(const struct Actor* actor);

// Render suppression is separate from actor lifetime, AI, and collision.
bool MegaSoul_ShouldHideActor(const struct Actor* actor);
bool MegaSoul_CanUseRock(void);

#ifdef __cplusplus
}
#endif
