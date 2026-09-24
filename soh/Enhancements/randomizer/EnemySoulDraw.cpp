#include "draw.h"
#include "EnemySoulIcons.h"
#include "soh/ResourceManagerHelpers.h"

extern "C" {
#include "z64.h"
#include "macros.h"
#include "functions.h"
}

// The shared soul base and portrait are precomposited into one transparent
// texture. A single billboard avoids object-bank/lifetime dependencies on a
// live enemy actor and remains visible while the held item rotates.
static Vtx sEnemySoulIconQuad[4] = {
    { { { -16, -16, 0 }, 0, { 0, 1024 }, { 255, 255, 255, 255 } } },
    { { { 16, -16, 0 }, 0, { 1024, 1024 }, { 255, 255, 255, 255 } } },
    { { { 16, 16, 0 }, 0, { 1024, 0 }, { 255, 255, 255, 255 } } },
    { { { -16, 16, 0 }, 0, { 0, 0 }, { 255, 255, 255, 255 } } },
};

extern "C" void Randomizer_DrawEnemySoul(PlayState* play, GetItemEntry* entry) {
    if (play == nullptr || entry == nullptr) return;
    // Ice-trap disguises use drawItemId. Never index a boss array with an enemy ID.
    const char* icon = SohExtreme_GetEnemySoulIcon(static_cast<RandomizerGet>(entry->drawItemId));
    if (icon == nullptr) icon = SohExtreme_GetEnemySoulIcon(static_cast<RandomizerGet>(entry->getItemId));
    if (icon == nullptr) return;

    // EnemySoulIcons stores OTR resource-name tokens. gDPLoadTextureBlock needs
    // the actual decoded texture bytes, not the address of the resource-name
    // string. Passing the token itself produced the large garbled/grass-like
    // square seen in the get-item animation (and could feed invalid texture
    // state into Fast3D when texture packs were active).
    char* textureData = ResourceMgr_LoadTexOrDListByName(icon);
    if (textureData == nullptr) return;

    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    Matrix_Push();
    Matrix_ReplaceRotation(&play->billboardMtxF);
    Matrix_Scale(2.0f, 2.0f, 2.0f, MTXMODE_APPLY);
    gSPMatrix(POLY_XLU_DISP++, Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);
    gDPPipeSync(POLY_XLU_DISP++);
    gSPClearGeometryMode(POLY_XLU_DISP++, G_LIGHTING | G_CULL_BACK | G_CULL_FRONT);
    gSPTexture(POLY_XLU_DISP++, 0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON);
    gDPSetCombineMode(POLY_XLU_DISP++, G_CC_MODULATEIA_PRIM, G_CC_MODULATEIA_PRIM);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 255, 255, 255, 255);
    gDPLoadTextureBlock(POLY_XLU_DISP++, textureData, G_IM_FMT_RGBA, G_IM_SIZ_32b, 32, 32, 0,
                       G_TX_CLAMP, G_TX_CLAMP, G_TX_NOMASK, G_TX_NOMASK, G_TX_NOLOD, G_TX_NOLOD);
    // The bridge expects uintptr_t, not an implicit Vtx* conversion on MSVC.
    gSPVertex(POLY_XLU_DISP++, reinterpret_cast<uintptr_t>(sEnemySoulIconQuad), 4, 0);
    gSP2Triangles(POLY_XLU_DISP++, 0, 1, 2, 0, 0, 2, 3, 0);
    Matrix_Pop();
    CLOSE_DISPS(play->state.gfxCtx);
}
