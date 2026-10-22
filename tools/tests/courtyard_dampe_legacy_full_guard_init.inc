void Baseline_EnHeishi1_Init(Actor* thisx, PlayState* play) {
    s32 pad;
    EnHeishi1* this = (EnHeishi1*)thisx;
    Vec3f rupeePos;
    s32 i;

    Actor_SetScale(&this->actor, 0.01f);
    SkelAnime_Init(play, &this->skelAnime, &gEnHeishiSkel, &gEnHeishiIdleAnim, this->jointTable, this->morphTable, 17);

    this->type = (this->actor.params >> 8) & 0xFF;
    this->path = this->actor.params & 0xFF;

    for (i = 0; i < ARRAY_COUNT(sAnimParamsInit[0]); i++) {
        this->animParams[i] = sAnimParamsInit[this->type][i];
    }

    // "type"
    osSyncPrintf(VT_FGCOL(GREEN) " 種類☆☆☆☆☆☆☆☆☆☆☆☆☆ %d\n" VT_RST, this->type);
    // "path data"
    osSyncPrintf(VT_FGCOL(YELLOW) " れえるでぇたぁ☆☆☆☆☆☆☆☆ %d\n" VT_RST, this->path);
    osSyncPrintf(VT_FGCOL(PURPLE) " anime_frame_speed ☆☆☆☆☆☆ %f\n" VT_RST, this->animSpeed);
    // "interpolation frame"
    osSyncPrintf(VT_FGCOL(PURPLE) " 補間フレーム☆☆☆☆☆☆☆☆☆ %f\n" VT_RST, this->transitionRate);
    // "targeted movement speed value between points"
    osSyncPrintf(VT_FGCOL(PURPLE) " point間の移動スピード目標値 ☆ %f\n" VT_RST, this->moveSpeedTarget);
    // "maximum movement speed value between points"
    osSyncPrintf(VT_FGCOL(PURPLE) " point間の移動スピード最大 ☆☆ %f\n" VT_RST, this->moveSpeedMax);
    // "(body) targeted turning angle speed value"
    osSyncPrintf(VT_FGCOL(PURPLE) " (体)反転アングルスピード目標値 %f\n" VT_RST, this->bodyTurnSpeedTarget);
    // "(body) maximum turning angle speed"
    osSyncPrintf(VT_FGCOL(PURPLE) " (体)反転アングルスピード最大☆ %f\n" VT_RST, this->bodyTurnSpeedMax);
    // "(head) targeted turning angle speed value"
    osSyncPrintf(VT_FGCOL(PURPLE) " (頭)反転アングルスピード加算値 %f\n" VT_RST, this->headTurnSpeedScale);
    // "(head) maximum turning angle speed"
    osSyncPrintf(VT_FGCOL(PURPLE) " (頭)反転アングルスピード最大☆ %f\n" VT_RST, this->headTurnSpeedMax);
    osSyncPrintf(VT_FGCOL(GREEN) " 今時間 %d\n" VT_RST, ((void)0, gSaveContext.dayTime)); // "current time"
    osSyncPrintf(VT_FGCOL(YELLOW) " チェック時間 %d\n" VT_RST, 0xBAAA);                   // "check time"
    osSyncPrintf("\n\n");

    if (this->path == 3) {
        for (i = 0; i < ARRAY_COUNT(sRupeePositions); i++) {
            rupeePos = sRupeePositions[i];
            Actor_SpawnAsChild(&play->actorCtx, &this->actor, play, ACTOR_EN_EX_RUPPY, rupeePos.x, rupeePos.y,
                               rupeePos.z, 0, 0, 0, 3);
        }
    }

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
