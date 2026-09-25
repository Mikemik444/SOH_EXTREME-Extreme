#include "ProgressionItemVisuals.h"
#include "soh/ResourceManagerHelpers.h"
// Keep this at global scope, outside extern "C" and outside an anonymous
// namespace. OPEN_DISPS/CLOSE_DISPS must see the native C-linkage declarations.
#include "soh/frame_interpolation.h"
#include <cstddef>
#include <cstdint>

extern "C" {
#include "z64.h"
#include "macros.h"
#include "functions.h"
}

static const ALIGN_ASSET(2) char sShovelWoodTexture[] =
    "__OTR__textures/parameter_static/gExtremeShovelWood";
static const ALIGN_ASSET(2) char sAbilityMetalTexture[] =
    "__OTR__textures/parameter_static/gExtremeAbilityMetal";

#include "ProgressionItemMeshes.inc"

static bool HasAbilityTexture(const char* texture) {
    return ResourceMgr_FileExists(texture) ||
           (ResourceMgr_IsAltAssetsEnabled() && ResourceMgr_FileAltExists(texture));
}

static void DrawAbilityTriangles(PlayState* play, Vtx* vertices, std::size_t count, const char* texture) {
    if (vertices == nullptr || count == 0 || count % 3 != 0) {
        return;
    }
    const bool textured = texture != nullptr && HasAbilityTexture(texture);
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gSPGrayscale(POLY_OPA_DISP++, false);
    gSPClearGeometryMode(POLY_OPA_DISP++, G_LIGHTING | G_CULL_BACK | G_CULL_FRONT | G_FOG |
                                           G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR);
    gSPSetGeometryMode(POLY_OPA_DISP++, G_SHADE | G_SHADING_SMOOTH | G_ZBUFFER);
    gDPSetCycleType(POLY_OPA_DISP++, G_CYC_1CYCLE);
    gDPSetRenderMode(POLY_OPA_DISP++, G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2);
    gDPSetAlphaCompare(POLY_OPA_DISP++, G_AC_NONE);
    gDPSetTextureLUT(POLY_OPA_DISP++, G_TT_NONE);
    gDPSetPrimColor(POLY_OPA_DISP++, 0, 0, 255, 255, 255, 255);
    gDPSetEnvColor(POLY_OPA_DISP++, 255, 255, 255, 255);
    if (textured) {
        gDPSetTexturePersp(POLY_OPA_DISP++, G_TP_PERSP);
        gDPSetTextureFilter(POLY_OPA_DISP++, G_TF_BILERP);
        gSPTexture(POLY_OPA_DISP++, 0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON);
        gDPSetCombineMode(POLY_OPA_DISP++, G_CC_MODULATEIA, G_CC_MODULATEIA);
        // Keep the resource token: Fast3D needs its dimensions and format.
        gDPLoadTextureBlock(POLY_OPA_DISP++, texture, G_IM_FMT_RGBA, G_IM_SIZ_32b, 32, 32, 0,
                           G_TX_CLAMP, G_TX_CLAMP, G_TX_NOMASK, G_TX_NOMASK, G_TX_NOLOD, G_TX_NOLOD);
    } else {
        // A missing optional material must not make the item disappear or
        // dereference a null resource. The complete coloured mesh still draws.
        gSPTexture(POLY_OPA_DISP++, 0, 0, 0, G_TX_RENDERTILE, G_OFF);
        gDPSetCombineMode(POLY_OPA_DISP++, G_CC_SHADE, G_CC_SHADE);
    }
    gSPMatrix(POLY_OPA_DISP++, Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);
    for (std::size_t offset = 0; offset < count; offset += 30) {
        const int batch = static_cast<int>(count - offset < 30 ? count - offset : 30);
        gSPVertex(POLY_OPA_DISP++, reinterpret_cast<uintptr_t>(vertices + offset), batch, 0);
        int i = 0;
        for (; i + 5 < batch; i += 6) {
            gSP2Triangles(POLY_OPA_DISP++, i, i + 1, i + 2, 0, i + 3, i + 4, i + 5, 0);
        }
        if (i < batch) {
            gSP1Triangle(POLY_OPA_DISP++, i, i + 1, i + 2, 0);
        }
    }
    CLOSE_DISPS(play->state.gfxCtx);
}

static void RestoreAbilityMaterial(PlayState* play) {
    OPEN_DISPS(play->state.gfxCtx);
    gDPPipeSync(POLY_OPA_DISP++);
    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gSPGrayscale(POLY_OPA_DISP++, false);
    gDPSetPrimColor(POLY_OPA_DISP++, 0, 0, 255, 255, 255, 255);
    gDPSetEnvColor(POLY_OPA_DISP++, 255, 255, 255, 255);
    CLOSE_DISPS(play->state.gfxCtx);
}

extern "C" void SohExtreme_DrawShovel(PlayState* play, GetItemEntry* entry) {
    if (play == nullptr || play->state.gfxCtx == nullptr || entry == nullptr) {
        return;
    }
    Matrix_Push();
    Matrix_RotateZ(-0.30f, MTXMODE_APPLY);
    DrawAbilityTriangles(play, sShovelWoodVertices, sizeof(sShovelWoodVertices) / sizeof(Vtx), sShovelWoodTexture);
    DrawAbilityTriangles(play, sShovelMetalVertices, sizeof(sShovelMetalVertices) / sizeof(Vtx), sAbilityMetalTexture);
    Matrix_Pop();
    RestoreAbilityMaterial(play);
}

extern "C" void SohExtreme_DrawRoll(PlayState* play, GetItemEntry* entry) {
    if (play == nullptr || play->state.gfxCtx == nullptr || entry == nullptr) {
        return;
    }
    Matrix_Push();
    // Retain the caller's world/held/shop transform. The emblem is real,
    // double-sided geometry; it never depends on a live player/enemy skeleton.
    DrawAbilityTriangles(play, sRollMetalVertices, sizeof(sRollMetalVertices) / sizeof(Vtx), sAbilityMetalTexture);
    Matrix_Pop();
    RestoreAbilityMaterial(play);
}
