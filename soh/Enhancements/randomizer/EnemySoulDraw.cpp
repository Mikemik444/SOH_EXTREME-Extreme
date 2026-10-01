#include "draw.h"
#include "EnemySoulIcons.h"
#include "SoulPortraitTiles.h"
#include "soh/ResourceManagerHelpers.h"
#include "soh/frame_interpolation.h"

extern "C" {
#include "z64.h"
#include "macros.h"
#include "functions.h"
#include "objects/object_gi_fire/object_gi_fire.h"
}

#include "SoulRelicMesh.inc"

// Each tile is an independent 32x32 RGBA32 texture (4096 bytes).
// Four safe uploads form one effective 64x64 portrait without ever asking
// Fast3D/TMEM to treat a 64x64 or 128x128 RGBA32 image as one texture.
static Vtx sSoulTileQuads[4][4] = {
    { // upper-left
        { { { -42,   0, 0 }, 0, { 0, 1024 }, { 255,255,255,255 } } },
        { { {   0,   0, 0 }, 0, { 1024,1024 }, { 255,255,255,255 } } },
        { { {   0,  42, 0 }, 0, { 1024,0 }, { 255,255,255,255 } } },
        { { { -42,  42, 0 }, 0, { 0,0 }, { 255,255,255,255 } } },
    },
    { // upper-right
        { { {   0,   0, 0 }, 0, { 0,1024 }, { 255,255,255,255 } } },
        { { {  42,   0, 0 }, 0, { 1024,1024 }, { 255,255,255,255 } } },
        { { {  42,  42, 0 }, 0, { 1024,0 }, { 255,255,255,255 } } },
        { { {   0,  42, 0 }, 0, { 0,0 }, { 255,255,255,255 } } },
    },
    { // lower-left
        { { { -42, -42, 0 }, 0, { 0,1024 }, { 255,255,255,255 } } },
        { { {   0, -42, 0 }, 0, { 1024,1024 }, { 255,255,255,255 } } },
        { { {   0,   0, 0 }, 0, { 1024,0 }, { 255,255,255,255 } } },
        { { { -42,   0, 0 }, 0, { 0,0 }, { 255,255,255,255 } } },
    },
    { // lower-right
        { { {   0, -42, 0 }, 0, { 0,1024 }, { 255,255,255,255 } } },
        { { {  42, -42, 0 }, 0, { 1024,1024 }, { 255,255,255,255 } } },
        { { {  42,   0, 0 }, 0, { 1024,0 }, { 255,255,255,255 } } },
        { { {   0,   0, 0 }, 0, { 0,0 }, { 255,255,255,255 } } },
    },
};

static Vtx sSoulFallbackQuad[4] = {
    { { { -42, -42, 0 }, 0, { 0,1024 }, { 255,255,255,255 } } },
    { { {  42, -42, 0 }, 0, { 1024,1024 }, { 255,255,255,255 } } },
    { { {  42,  42, 0 }, 0, { 1024,0 }, { 255,255,255,255 } } },
    { { { -42,  42, 0 }, 0, { 0,0 }, { 255,255,255,255 } } },
};

static const SohExtremeSoulVisual* ResolveSoulVisual(const GetItemEntry& entry) {
    if (entry.drawModIndex == MOD_RANDOMIZER) {
        const auto* visual = SohExtreme_GetSoulVisual(static_cast<int>(entry.drawItemId));
        if (visual != nullptr) {
            return visual;
        }
        if (entry.drawItemId != RG_NONE) {
            return nullptr;
        }
    } else if (entry.drawModIndex != MOD_NONE || entry.drawItemId != RG_NONE) {
        return nullptr;
    }

    if (entry.modIndex != MOD_RANDOMIZER || entry.getItemId == RG_ICE_TRAP) {
        return nullptr;
    }

    const auto* visual = SohExtreme_GetSoulVisual(static_cast<int>(entry.getItemId));
    return visual != nullptr ? visual : SohExtreme_GetSoulVisual(static_cast<int>(entry.itemId));
}

static bool HasResource(const char* path) {
    return path != nullptr &&
           (ResourceMgr_FileExists(path) ||
            (ResourceMgr_IsAltAssetsEnabled() && ResourceMgr_FileAltExists(path)));
}

static void DrawSoulFlame(PlayState* play, const SohExtremeSoulVisual& visual) {
    const s32 frame = static_cast<s32>(play->state.frames & 0x7FFFu);

    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);

    gSPSegment(POLY_XLU_DISP++, 8,
               reinterpret_cast<uintptr_t>(
                   Gfx_TwoTexScrollEx(play->state.gfxCtx,
                                      0, 0, 0, 16, 32,
                                      1, frame, -frame * 8, 16, 32,
                                      0, 0, 1, -8)));

    Matrix_Push();
    Matrix_Translate(0.0f, -36.0f, -6.0f, MTXMODE_APPLY);
    Matrix_Scale(2.6f, 2.6f, 2.6f, MTXMODE_APPLY);
    Matrix_ReplaceRotation(&play->billboardMtxF);

    gSPMatrix(POLY_XLU_DISP++,
              Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);

    gDPSetGrayscaleColor(POLY_XLU_DISP++,
                         visual.flameR, visual.flameG, visual.flameB, 255);
    gSPGrayscale(POLY_XLU_DISP++, true);
    gSPDisplayList(POLY_XLU_DISP++, (Gfx*)gGiBlueFireFlameDL);
    gSPGrayscale(POLY_XLU_DISP++, false);
    Matrix_Pop();

    CLOSE_DISPS(play->state.gfxCtx);
}

static void DrawSoulSkull(PlayState* play) {
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetTextureLUT(POLY_XLU_DISP++, G_TT_NONE);
    gSPGrayscale(POLY_XLU_DISP++, false);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 255,255,255,255);
    gDPSetEnvColor(POLY_XLU_DISP++, 255,255,255,255);
    gSPMatrix(POLY_XLU_DISP++,
              Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);
    gSPDisplayList(POLY_XLU_DISP++, (Gfx*)gBossSoulSkullDL);
    CLOSE_DISPS(play->state.gfxCtx);
}

static void SetupPortraitMaterial(PlayState* play, Gfx*& polyXluDisp) {
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    gDPPipeSync(polyXluDisp++);
    gSPGrayscale(polyXluDisp++, false);
    gSPClearGeometryMode(polyXluDisp++,
                         G_LIGHTING | G_CULL_BACK | G_CULL_FRONT | G_FOG |
                         G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR);
    gDPSetCycleType(polyXluDisp++, G_CYC_1CYCLE);
    gDPSetRenderMode(polyXluDisp++,
                     G_RM_AA_ZB_XLU_SURF, G_RM_AA_ZB_XLU_SURF2);
    gDPSetAlphaCompare(polyXluDisp++, G_AC_NONE);
    gDPSetTextureLUT(polyXluDisp++, G_TT_NONE);
    gDPSetTexturePersp(polyXluDisp++, G_TP_PERSP);
    gDPSetTextureFilter(polyXluDisp++, G_TF_BILERP);
    gSPTexture(polyXluDisp++, 0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON);
    gDPSetCombineMode(polyXluDisp++,
                      G_CC_MODULATEIA_PRIM, G_CC_MODULATEIA_PRIM);
    gDPSetPrimColor(polyXluDisp++, 0, 0, 255, 255, 255, 255);
    gDPSetEnvColor(polyXluDisp++, 255, 255, 255, 255);
}

static void Draw32TextureOnQuad(Gfx*& polyXluDisp, const char* texture, Vtx* quad) {
    gDPPipeSync(polyXluDisp++);
    gDPSetTextureLUT(polyXluDisp++, G_TT_NONE);
    gDPLoadTextureBlock(polyXluDisp++, texture,
                        G_IM_FMT_RGBA, G_IM_SIZ_32b,
                        32, 32, 0,
                        G_TX_CLAMP, G_TX_CLAMP,
                        G_TX_NOMASK, G_TX_NOMASK,
                        G_TX_NOLOD, G_TX_NOLOD);
    gSPVertex(polyXluDisp++, reinterpret_cast<uintptr_t>(quad), 4, 0);
    gSP2Triangles(polyXluDisp++, 0, 1, 2, 0, 0, 2, 3, 0);
}

static void DrawSoulRim(PlayState* play, const SohExtremeSoulVisual& visual) {
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gSPGrayscale(POLY_OPA_DISP++, false);
    gSPClearGeometryMode(POLY_OPA_DISP++, G_LIGHTING | G_CULL_BACK | G_CULL_FRONT | G_FOG |
                                           G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR);
    gSPSetGeometryMode(POLY_OPA_DISP++, G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER);
    gDPSetTextureLUT(POLY_OPA_DISP++, G_TT_NONE);
    gSPTexture(POLY_OPA_DISP++, 0, 0, 0, G_TX_RENDERTILE, G_OFF);
    gDPSetCombineLERP(POLY_OPA_DISP++, SHADE, 0, PRIMITIVE, 0, 0, 0, 0, PRIMITIVE,
                     SHADE, 0, PRIMITIVE, 0, 0, 0, 0, PRIMITIVE);
    gDPSetPrimColor(POLY_OPA_DISP++, 0, 0, (255 + visual.flameR) / 2,
                   (255 + visual.flameG) / 2, (255 + visual.flameB) / 2, 255);
    gSPMatrix(POLY_OPA_DISP++, MATRIX_NEWMTX(play->state.gfxCtx), G_MTX_MODELVIEW | G_MTX_LOAD);
    constexpr int count = sizeof(sSoulRelicRim) / sizeof(sSoulRelicRim[0]);
    for (int offset = 0; offset < count; offset += 30) {
        const int batch = count - offset < 30 ? count - offset : 30;
        gSPVertex(POLY_OPA_DISP++, reinterpret_cast<uintptr_t>(sSoulRelicRim + offset), batch, 0);
        for (int i = 0; i < batch; i += 3) {
            gSP1Triangle(POLY_OPA_DISP++, i, i + 1, i + 2, 0);
        }
    }
    gDPPipeSync(POLY_OPA_DISP++);
    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPSetPrimColor(POLY_OPA_DISP++, 0, 0, 255, 255, 255, 255);
    CLOSE_DISPS(play->state.gfxCtx);
}

static bool DrawSoulPortrait(PlayState* play, const SohExtremeSoulVisual& visual) {
    const auto* tiles = SohExtreme_GetSoulPortraitTiles(visual.item);
    const auto* emblem = SohExtreme_GetSoulEmblem(visual.item);
    const char* icon = emblem != nullptr ? emblem->icon : visual.icon;

    const bool haveEmblem = emblem != nullptr && HasResource(emblem->tiles[0]) &&
                           HasResource(emblem->tiles[1]) && HasResource(emblem->tiles[2]) &&
                           HasResource(emblem->tiles[3]);

    bool haveTiles = tiles != nullptr &&
                     HasResource(tiles->tile0) &&
                     HasResource(tiles->tile1) &&
                     HasResource(tiles->tile2) &&
                     HasResource(tiles->tile3);

    if (!haveEmblem && !haveTiles && !HasResource(icon)) {
        return false;
    }

    OPEN_DISPS(play->state.gfxCtx);
    Matrix_Push();
    Matrix_ReplaceRotation(&play->billboardMtxF);
    // Gentle rocking keeps the front readable and shows the modeled bevel.
    const float phase = (play->state.frames & 0x7FFFu) * 0.035f;
    Matrix_Translate(0.0f, 1.5f * sinf(phase), 0.0f, MTXMODE_APPLY);
    Matrix_RotateY(0.16f * sinf(phase * 0.7f), MTXMODE_APPLY);
    DrawSoulRim(play, visual);
    Matrix_Translate(0.0f, 0.0f, 5.0f, MTXMODE_APPLY);
    Matrix_Scale(0.72f, 0.72f, 0.72f, MTXMODE_APPLY);
    gSPMatrix(POLY_XLU_DISP++,
              Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);

    Gfx*& polyXluDisp = POLY_XLU_DISP;
    SetupPortraitMaterial(play, polyXluDisp);

    if (haveEmblem) {
        for (int i = 0; i < 4; ++i) {
            Draw32TextureOnQuad(polyXluDisp, emblem->tiles[i], sSoulTileQuads[i]);
        }
    } else if (haveTiles) {
        // Four independent 32x32 uploads -> effective 64x64 detail.
        // No oversized texture, no source-stride tricks, no TLUT usage.
        Draw32TextureOnQuad(polyXluDisp, tiles->tile0, sSoulTileQuads[0]);
        Draw32TextureOnQuad(polyXluDisp, tiles->tile1, sSoulTileQuads[1]);
        Draw32TextureOnQuad(polyXluDisp, tiles->tile2, sSoulTileQuads[2]);
        Draw32TextureOnQuad(polyXluDisp, tiles->tile3, sSoulTileQuads[3]);
    } else {
        // Safe compatibility fallback.
        Draw32TextureOnQuad(polyXluDisp, icon, sSoulFallbackQuad);
    }

    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetTextureLUT(POLY_XLU_DISP++, G_TT_NONE);
    gSPGrayscale(POLY_XLU_DISP++, false);

    Matrix_Pop();
    CLOSE_DISPS(play->state.gfxCtx);
    return true;
}

static void RestoreSoulRenderState(PlayState* play) {
    OPEN_DISPS(play->state.gfxCtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gDPSetTextureLUT(POLY_XLU_DISP++, G_TT_NONE);
    gSPGrayscale(POLY_XLU_DISP++, false);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    gDPSetPrimColor(POLY_XLU_DISP++,0,0,255,255,255,255);
    gDPSetEnvColor(POLY_XLU_DISP++,255,255,255,255);
    CLOSE_DISPS(play->state.gfxCtx);
}

extern "C" void Randomizer_DrawEnemySoul(PlayState* play, GetItemEntry* entry) {
    if (play == nullptr || play->state.gfxCtx == nullptr || entry == nullptr) {
        return;
    }

    const auto* visual = ResolveSoulVisual(*entry);
    if (visual == nullptr) {
        return;
    }

    Matrix_Push();

    if (visual->kind == SOH_SOUL_BOSS) {
        GetItemEntry drawingEntry = *entry;
        drawingEntry.getItemId = static_cast<int16_t>(visual->item);
        drawingEntry.drawItemId = static_cast<uint16_t>(visual->item);
        Randomizer_DrawBossSoul(play, &drawingEntry);
    } else {
        DrawSoulFlame(play, *visual);

        if (visual->kind == SOH_SOUL_BEAN) {
            Randomizer_DrawBeanSprout(play, entry);
        } else if (!DrawSoulPortrait(play, *visual)) {
            DrawSoulSkull(play);
        }
    }

    Matrix_Pop();
    RestoreSoulRenderState(play);
}
