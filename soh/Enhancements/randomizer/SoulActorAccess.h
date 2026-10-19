#pragma once

#include <stdbool.h>
#include <stdint.h>

struct Actor;

#ifdef __cplusplus
extern "C" {
#endif

// The Kokiri Forest exit boy and adult Lost Woods Mido retain blocking movement
// and solid collision while hidden. Every locked NPC rejects player interactions.
// The placement helper matches scenes; the live actor helper also checks Mido's age.
bool MegaSoul_IsPathBlockingNpcPlacement(int16_t actorId, int16_t params, int16_t scene);
bool MegaSoul_IsPathBlockingNpc(const struct Actor* actor);

bool MegaSoul_IsNpcSoulLocked(const struct Actor* actor);
bool MegaSoul_CanInteractWithActor(const struct Actor* actor);
bool MegaSoul_ShouldDisableActorCollision(const struct Actor* actor);

// Render suppression is separate from actor lifetime, AI, and collision.
bool MegaSoul_ShouldHideActor(const struct Actor* actor);
bool MegaSoul_CanUseRock(void);
bool MegaSoul_CanUseCrate(void);

#ifdef __cplusplus
}
#endif
