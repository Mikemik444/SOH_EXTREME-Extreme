// Regression evidence from the delivered 1.8.11 source; never production code.
// Original randomizer_grotto.c SHA256: c24197093d1ba4324c518ff919d00e5f04748b51cd7a5951bbe31cc72a7924a3
// Delivered ZIP SHA256: 8d105428ddd2146abaf70a6ab4ce7b05e44aefbcccdcc8076893185ce896bc3e

void Grotto_ForceGrottoReturn(void) {
    if (lastEntranceType == GROTTO_RETURN && (Archipelago_EntranceShuffleActive() ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS))) {
        gSaveContext.respawnFlag = 2;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].playerParams = 0x0DFF;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].pos = grottoReturnTable[grottoId].pos;
        // Save the current temp flags in the grotto return point, so they'll properly keep their values.
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags = gPlayState->actorCtx.flags.tempSwch;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags = gPlayState->actorCtx.flags.tempCollect;
    }
}
