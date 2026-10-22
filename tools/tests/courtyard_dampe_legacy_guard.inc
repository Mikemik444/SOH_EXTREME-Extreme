// Original guard-selection tail; intentionally excludes animation and actor spawning.
void Baseline_InitializeCourtyardAccess(EnHeishi1* this) {
    // eventChkInf[4] & 1 = Got Zelda's Letter
    // eventChkInf[5] & 0x200 = Got item from impa
    // eventChkInf[8] & 1 = Ocarina thrown in moat
    bool metZelda = (Flags_GetEventChkInf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER)) &&
                    (Flags_GetEventChkInf(EVENTCHKINF_LEARNED_ZELDAS_LULLABY));

    if (this->type != 5) {
        if (GameInteractor_Should(VB_WONDER_HEISHI_PATROLLING,
                                  (gSaveContext.dayTime < 0xB888 || IS_DAY) &&
                                      ((!IS_RANDO && !Flags_GetEventChkInf(EVENTCHKINF_ZELDA_FLED_HYRULE_CASTLE)) ||
                                       (IS_RANDO && !metZelda)),
                                  this)) {
            this->actionFunc = EnHeishi1_SetupWalk;
        } else {
            Actor_Kill(&this->actor);
        }
    } else {
        if (GameInteractor_Should(VB_WONDER_HEISHI_PATROLLING,
                                  (gSaveContext.dayTime >= 0xB889) || !IS_DAY ||
                                      (!IS_RANDO && Flags_GetEventChkInf(EVENTCHKINF_ZELDA_FLED_HYRULE_CASTLE)) ||
                                      (IS_RANDO && metZelda),
                                  this)) {
            this->actionFunc = EnHeishi1_SetupWaitNight;
        } else {
            Actor_Kill(&this->actor);
        }
    }
}
