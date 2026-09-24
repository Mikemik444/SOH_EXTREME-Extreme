#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
struct Actor;
struct PlayState;
int32_t MegaSoul_FindEnemyDefeatSpawn(int16_t scene, int8_t room, int16_t actorIndex,
    int16_t actorId, uint16_t params, float x, float y, float z);
bool MegaSoul_IsEnemyDefeatPlacementPending(int32_t index);
int32_t MegaSoul_FindEnemyDefeatChild(const struct Actor* source, int16_t actorId, uint16_t params, int16_t slot);
void MegaSoul_CaptureEnemyDefeatIdentityAt(struct Actor* actor, int32_t index);
void MegaSoul_CaptureEnemyDefeatIdentityFrom(struct Actor* actor, int32_t index, const struct Actor* source);
bool MegaSoul_IsEnemySpawnSource(const struct Actor* source);
void MegaSoul_ResetEnemyDefeatLife(struct Actor* actor);
struct Actor* MegaSoul_SpawnEnemyChild(struct PlayState* play, struct Actor* source, int16_t slot,
    int16_t actorId, float x, float y, float z, int16_t rx, int16_t ry, int16_t rz, int16_t params);
struct Actor* MegaSoul_SpawnEnemy(struct PlayState* play, struct Actor* source, int16_t slot,
    int16_t actorId, float x, float y, float z, int16_t rx, int16_t ry, int16_t rz, int16_t params);
int32_t MegaSoul_GetEnemyDefeatPlacement(const struct Actor* actor);
void MegaSoul_BeginEnemyDefeatLife(struct Actor* actor, int32_t index);
bool MegaSoul_HasPendingEnemyInRoom(int16_t scene, int8_t room, int16_t actorId);
void MegaSoul_CaptureEnemyDefeatIdentity(struct Actor* actor);
bool MegaSoul_IsEnemyDefeatSpawnPending(int16_t scene, int8_t room, int16_t actorIndex,
                                      int16_t actorId, uint16_t params);
bool MegaSoul_IsEnemyDefeatLocationPending(const struct Actor* actor);
bool MegaSoul_IsEnemyDefeatPickup(const struct Actor* actor);
bool MegaSoul_TryCollectEnemyDefeatPickup(struct Actor* actor);
bool MegaSoul_HandlesEnemyLoot(const struct Actor* actor);
int MegaSoul_ConsumeNormalEnemyDrop(struct Actor* actor);
#ifdef __cplusplus
}
#endif
