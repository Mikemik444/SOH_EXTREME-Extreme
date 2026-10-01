#pragma once

#include <stdbool.h>
#include <stdint.h>

// File-select-only pseudo quest. It is converted to QUEST_RANDOMIZER when the
// save is actually created, so the rest of SoH continues using its normal
// randomizer code paths.
#ifndef QUEST_ARCHIPELAGO
#define QUEST_ARCHIPELAGO (QUEST_BOSSRUSH + 1)
#endif

#ifdef __cplusplus
extern "C" {
#endif

// Keep optional NPC conversations available until their AP check is collected.
struct Actor;
bool Archipelago_HasPendingNpcConversation(const struct Actor* actor);
// Uncollected speech check on a visible NPC; suppressed while NPC Soul is locked.
bool Archipelago_ShouldHighlightNpcSpeech(const struct Actor* actor);
bool Archipelago_IsAuthenticatedForFileSelect(void);
// True only for the enabled AP client's current Archipelago save.
bool Archipelago_IsCurrentSaveActive(void);
// Save identity, independent of connection/enabled state, for physical seed rules.
bool Archipelago_IsCurrentSaveFile(void);
// Freeze passive outdoor time until Flow; explicit Sun's Song changes still run.
bool Archipelago_ShouldFreezeTime(void);
void Archipelago_InitSaveFile(void);
bool Archipelago_ShouldHandleCheck(int32_t randomizerCheck);
// Cheap tracker-only ownership query: never performs name resolution/scans.
bool Archipelago_IsCheckMappedActive(int32_t randomizerCheck);
// Demand-build the complete active RC mapping needed by Check Finder. This does
// not apply world placements/models and therefore does not undo scene-local v6.
bool Archipelago_PrepareCheckFinderMappings(void);
// AP-only/synthetic location helpers used by Check Finder (NPC Speech, etc.).
bool Archipelago_IsLocationActive(int64_t locationId);
bool Archipelago_IsLocationReported(int64_t locationId);
// Accepted into this save's retry queue, or confirmed by the server.
bool Archipelago_IsLocationSubmitted(int64_t locationId);
uint32_t Archipelago_GetActiveLocationCount(void);
uint32_t Archipelago_GetReportedActiveLocationCount(void);
// Resolve/apply AP placements only for checks belonging to one scene.
void Archipelago_RefreshScenePlacements(int16_t sceneNum);
void Archipelago_ReportCheck(int32_t randomizerCheck);
void Archipelago_ReportLocation(int64_t locationId);
// Retry a previously collected journal entry without replaying its presentation.
void Archipelago_ReconcileLocation(int64_t locationId);
void Archipelago_RefreshPlacementForCheck(int32_t randomizerCheck);
// Cosmetic RandomizerGet for an AP-only pickup; never grants or reports it.
int32_t Archipelago_GetLocationDisplayItem(int64_t locationId);
// Returns "<item> for <player>" for a scouted remote AP placement.
// Empty string means the check is not a known remote placement.
const char* Archipelago_GetRemoteItemDescription(int32_t randomizerCheck);
const char* Archipelago_GetRemotePickupDescription(void);
const char* Archipelago_GetSongNotePickupDescription(void);

#ifdef __cplusplus
}
#endif
