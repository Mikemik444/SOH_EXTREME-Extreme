/* Captured production functions before the update-owned collision fix.
 * Original z_bg_breakwall.c SHA256: ff4b3ba06e1a67aa4c7d2f9794e50cb2c80d3c44f267832117387de38e4c826d
 * The regression compiles these bodies to demonstrate the missing no-draw collider.
 */

void BgBreakwall_Draw(Actor* thisx, PlayState* play) {
    s32 pad;
    BgBreakwall* this = (BgBreakwall*)thisx;

    if (this->bombableWallDList != NULL) {
        OPEN_DISPS(play->state.gfxCtx);

        Gfx_SetupDL_25Opa(play->state.gfxCtx);
        gSPMatrix(POLY_OPA_DISP++, MATRIX_NEWMTX(play->state.gfxCtx), G_MTX_NOPUSH | G_MTX_LOAD | G_MTX_MODELVIEW);
        gSPDisplayList(POLY_OPA_DISP++, this->bombableWallDList);

        if (this->colType >= 0) {
            Vec3f colQuad[4];
            Vec3f* src = &sColQuadList[this->colType][0];
            Vec3f* dst = &colQuad[0];
            s32 i;

            for (i = 0; i < 4; i++) {
                Matrix_MultVec3f(src++, dst++);
            }

            Collider_SetQuadVertices(&this->collider, &colQuad[0], &colQuad[1], &colQuad[2], &colQuad[3]);
            CollisionCheck_SetAC(play, &play->colChkCtx, &this->collider.base);
        }

        CLOSE_DISPS(play->state.gfxCtx);
    }
}

void BgBreakwall_WaitForObject(BgBreakwall* this, PlayState* play) {
    if (Object_IsLoaded(&play->objectCtx, this->bankIndex)) {
        CollisionHeader* colHeader = NULL;
        s32 wallType = ((this->dyna.actor.params >> 13) & 3) & 0xFF;

        this->dyna.actor.objBankIndex = this->bankIndex;
        Actor_SetObjectDependency(play, &this->dyna.actor);
        this->dyna.actor.flags &= ~ACTOR_FLAG_UPDATE_CULLING_DISABLED;
        this->dyna.actor.draw = BgBreakwall_Draw;
        CollisionHeader_GetVirtual(sBombableWallInfo[wallType].colHeader, &colHeader);
        this->dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, &this->dyna.actor, colHeader);

        if (wallType == BWALL_KD_LAVA_COVER) {
            BgBreakwall_SetupAction(this, BgBreakwall_LavaCoverMove);
        } else {
            BgBreakwall_SetupAction(this, BgBreakwall_Wait);
        }
    }
}

void BgBreakwall_Update(Actor* thisx, PlayState* play) {
    BgBreakwall* this = (BgBreakwall*)thisx;

    this->actionFunc(this, play);
}
