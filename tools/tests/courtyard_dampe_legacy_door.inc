void Baseline_EnDoor_SetupType(EnDoor* this, PlayState* play) {
    s32 doorType;

    if (Object_IsLoaded(&play->objectCtx, this->requiredObjBankIndex)) {
        doorType = this->actor.params >> 7 & 7;
        this->actor.flags &= ~ACTOR_FLAG_UPDATE_CULLING_DISABLED;
        this->actor.objBankIndex = this->requiredObjBankIndex;
        this->actionFunc = EnDoor_Idle;
        if (doorType == DOOR_EVENING) {
            doorType =
                (gSaveContext.dayTime > 0xC000 && gSaveContext.dayTime < 0xE000) ? DOOR_SCENEEXIT : DOOR_CHECKABLE;
        }
        this->actor.world.rot.y = 0x0000;
        if (doorType == DOOR_LOCKED) {
            if (GameInteractor_Should(VB_DOOR_BE_LOCKED, !Flags_GetSwitch(play, this->actor.params & 0x3F), this)) {
                this->lockTimer = 10;
            }
        } else if (doorType == DOOR_AJAR) {
            if (Actor_WorldDistXZToActor(&this->actor, &GET_PLAYER(play)->actor) > DOOR_AJAR_SLAM_RANGE) {
                this->actionFunc = EnDoor_AjarWait;
                this->actor.world.rot.y = -0x1800;
            }
        } else if (doorType == DOOR_CHECKABLE) {
            this->actor.textId = (this->actor.params & 0x3F) + 0x0200;
            if (this->actor.textId == 0x0229 && !Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE)) {
                // Talon's house door. If Talon has not been woken up at Hyrule Castle
                // this door should be openable at any time of day. Note that there is no
                // check for time of day as the scene setup for Lon Lon merely initializes
                // the door with a different text id between day and night setups
                doorType = DOOR_SCENEEXIT;
            } else {
                this->actionFunc = EnDoor_WaitForCheck;
                this->actor.flags |= ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY | ACTOR_FLAG_LOCK_ON_DISABLED;
            }
        }
        // Replace the door type it was loaded with by the new type
        this->actor.params = (this->actor.params & ~0x380) | (doorType << 7);
    }
}
