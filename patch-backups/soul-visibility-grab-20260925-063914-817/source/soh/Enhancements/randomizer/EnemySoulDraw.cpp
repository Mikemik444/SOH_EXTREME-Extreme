#include "draw.h"
#include "EnemySoulIcons.h"
#include "SoulPortraitHQ.h"
#include "soh/ResourceManagerHelpers.h"

// OPEN_DISPS/CLOSE_DISPS redeclare these hooks at block scope. Include their
// canonical C-linkage declarations before any macro expansion. Keep this header
// outside extern "C": it also declares the C++ interpolation API and includes
// <unordered_map>.
#include "soh/frame_interpolation.h"

extern "C" {
#include "z64.h"
#include "macros.h"
#include "functions.h"
#include "objects/object_gi_fire/object_gi_fire.h"
}

// These helpers must stay in the global namespace: OPEN_DISPS/CLOSE_DISPS
// declare functions at block scope. A surrounding anonymous namespace would
// give those declarations different linkage from the native interpolation API.
// Static storage keeps these helpers private to this translation unit.

// Vertices must outlive the deferred display-list execution. Do not put this
// buffer on the stack. Texture coordinates use the same 32x32 logical size as
// the existing portraits, independently of a replacement texture's resolution.
static Vtx sSoulPortraitQuad[4] = {
    { { { -32, -32, 0 }, 0, { 0, 1024 }, { 255, 255, 255, 255 } } },
    { { { 32, -32, 0 }, 0, { 1024, 1024 }, { 255, 255, 255, 255 } } },
    { { { 32, 32, 0 }, 0, { 1024, 0 }, { 255, 255, 255, 255 } } },
    { { { -32, 32, 0 }, 0, { 0, 0 }, { 255, 255, 255, 255 } } },
};


// 4 columns x 8 rows, each displaying 32x16 texels from a 128x128 texture.
// Storage must survive deferred display-list consumption; never allocate on the stack.
static Vtx sHqSoulPortraitTiles[32][4] = {
    {
        { { { -32, 24, 0 }, 0, { 0, 512 }, { 255, 255, 255, 255 } } },
        { { { -16, 24, 0 }, 0, { 1024, 512 }, { 255, 255, 255, 255 } } },
        { { { -16, 32, 0 }, 0, { 1024, 0 }, { 255, 255, 255, 255 } } },
        { { { -32, 32, 0 }, 0, { 0, 0 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, 24, 0 }, 0, { 1024, 512 }, { 255, 255, 255, 255 } } },
        { { { 0, 24, 0 }, 0, { 2048, 512 }, { 255, 255, 255, 255 } } },
        { { { 0, 32, 0 }, 0, { 2048, 0 }, { 255, 255, 255, 255 } } },
        { { { -16, 32, 0 }, 0, { 1024, 0 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, 24, 0 }, 0, { 2048, 512 }, { 255, 255, 255, 255 } } },
        { { { 16, 24, 0 }, 0, { 3072, 512 }, { 255, 255, 255, 255 } } },
        { { { 16, 32, 0 }, 0, { 3072, 0 }, { 255, 255, 255, 255 } } },
        { { { 0, 32, 0 }, 0, { 2048, 0 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, 24, 0 }, 0, { 3072, 512 }, { 255, 255, 255, 255 } } },
        { { { 32, 24, 0 }, 0, { 4096, 512 }, { 255, 255, 255, 255 } } },
        { { { 32, 32, 0 }, 0, { 4096, 0 }, { 255, 255, 255, 255 } } },
        { { { 16, 32, 0 }, 0, { 3072, 0 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, 16, 0 }, 0, { 0, 1024 }, { 255, 255, 255, 255 } } },
        { { { -16, 16, 0 }, 0, { 1024, 1024 }, { 255, 255, 255, 255 } } },
        { { { -16, 24, 0 }, 0, { 1024, 512 }, { 255, 255, 255, 255 } } },
        { { { -32, 24, 0 }, 0, { 0, 512 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, 16, 0 }, 0, { 1024, 1024 }, { 255, 255, 255, 255 } } },
        { { { 0, 16, 0 }, 0, { 2048, 1024 }, { 255, 255, 255, 255 } } },
        { { { 0, 24, 0 }, 0, { 2048, 512 }, { 255, 255, 255, 255 } } },
        { { { -16, 24, 0 }, 0, { 1024, 512 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, 16, 0 }, 0, { 2048, 1024 }, { 255, 255, 255, 255 } } },
        { { { 16, 16, 0 }, 0, { 3072, 1024 }, { 255, 255, 255, 255 } } },
        { { { 16, 24, 0 }, 0, { 3072, 512 }, { 255, 255, 255, 255 } } },
        { { { 0, 24, 0 }, 0, { 2048, 512 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, 16, 0 }, 0, { 3072, 1024 }, { 255, 255, 255, 255 } } },
        { { { 32, 16, 0 }, 0, { 4096, 1024 }, { 255, 255, 255, 255 } } },
        { { { 32, 24, 0 }, 0, { 4096, 512 }, { 255, 255, 255, 255 } } },
        { { { 16, 24, 0 }, 0, { 3072, 512 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, 8, 0 }, 0, { 0, 1536 }, { 255, 255, 255, 255 } } },
        { { { -16, 8, 0 }, 0, { 1024, 1536 }, { 255, 255, 255, 255 } } },
        { { { -16, 16, 0 }, 0, { 1024, 1024 }, { 255, 255, 255, 255 } } },
        { { { -32, 16, 0 }, 0, { 0, 1024 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, 8, 0 }, 0, { 1024, 1536 }, { 255, 255, 255, 255 } } },
        { { { 0, 8, 0 }, 0, { 2048, 1536 }, { 255, 255, 255, 255 } } },
        { { { 0, 16, 0 }, 0, { 2048, 1024 }, { 255, 255, 255, 255 } } },
        { { { -16, 16, 0 }, 0, { 1024, 1024 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, 8, 0 }, 0, { 2048, 1536 }, { 255, 255, 255, 255 } } },
        { { { 16, 8, 0 }, 0, { 3072, 1536 }, { 255, 255, 255, 255 } } },
        { { { 16, 16, 0 }, 0, { 3072, 1024 }, { 255, 255, 255, 255 } } },
        { { { 0, 16, 0 }, 0, { 2048, 1024 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, 8, 0 }, 0, { 3072, 1536 }, { 255, 255, 255, 255 } } },
        { { { 32, 8, 0 }, 0, { 4096, 1536 }, { 255, 255, 255, 255 } } },
        { { { 32, 16, 0 }, 0, { 4096, 1024 }, { 255, 255, 255, 255 } } },
        { { { 16, 16, 0 }, 0, { 3072, 1024 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, 0, 0 }, 0, { 0, 2048 }, { 255, 255, 255, 255 } } },
        { { { -16, 0, 0 }, 0, { 1024, 2048 }, { 255, 255, 255, 255 } } },
        { { { -16, 8, 0 }, 0, { 1024, 1536 }, { 255, 255, 255, 255 } } },
        { { { -32, 8, 0 }, 0, { 0, 1536 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, 0, 0 }, 0, { 1024, 2048 }, { 255, 255, 255, 255 } } },
        { { { 0, 0, 0 }, 0, { 2048, 2048 }, { 255, 255, 255, 255 } } },
        { { { 0, 8, 0 }, 0, { 2048, 1536 }, { 255, 255, 255, 255 } } },
        { { { -16, 8, 0 }, 0, { 1024, 1536 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, 0, 0 }, 0, { 2048, 2048 }, { 255, 255, 255, 255 } } },
        { { { 16, 0, 0 }, 0, { 3072, 2048 }, { 255, 255, 255, 255 } } },
        { { { 16, 8, 0 }, 0, { 3072, 1536 }, { 255, 255, 255, 255 } } },
        { { { 0, 8, 0 }, 0, { 2048, 1536 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, 0, 0 }, 0, { 3072, 2048 }, { 255, 255, 255, 255 } } },
        { { { 32, 0, 0 }, 0, { 4096, 2048 }, { 255, 255, 255, 255 } } },
        { { { 32, 8, 0 }, 0, { 4096, 1536 }, { 255, 255, 255, 255 } } },
        { { { 16, 8, 0 }, 0, { 3072, 1536 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, -8, 0 }, 0, { 0, 2560 }, { 255, 255, 255, 255 } } },
        { { { -16, -8, 0 }, 0, { 1024, 2560 }, { 255, 255, 255, 255 } } },
        { { { -16, 0, 0 }, 0, { 1024, 2048 }, { 255, 255, 255, 255 } } },
        { { { -32, 0, 0 }, 0, { 0, 2048 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, -8, 0 }, 0, { 1024, 2560 }, { 255, 255, 255, 255 } } },
        { { { 0, -8, 0 }, 0, { 2048, 2560 }, { 255, 255, 255, 255 } } },
        { { { 0, 0, 0 }, 0, { 2048, 2048 }, { 255, 255, 255, 255 } } },
        { { { -16, 0, 0 }, 0, { 1024, 2048 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, -8, 0 }, 0, { 2048, 2560 }, { 255, 255, 255, 255 } } },
        { { { 16, -8, 0 }, 0, { 3072, 2560 }, { 255, 255, 255, 255 } } },
        { { { 16, 0, 0 }, 0, { 3072, 2048 }, { 255, 255, 255, 255 } } },
        { { { 0, 0, 0 }, 0, { 2048, 2048 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, -8, 0 }, 0, { 3072, 2560 }, { 255, 255, 255, 255 } } },
        { { { 32, -8, 0 }, 0, { 4096, 2560 }, { 255, 255, 255, 255 } } },
        { { { 32, 0, 0 }, 0, { 4096, 2048 }, { 255, 255, 255, 255 } } },
        { { { 16, 0, 0 }, 0, { 3072, 2048 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, -16, 0 }, 0, { 0, 3072 }, { 255, 255, 255, 255 } } },
        { { { -16, -16, 0 }, 0, { 1024, 3072 }, { 255, 255, 255, 255 } } },
        { { { -16, -8, 0 }, 0, { 1024, 2560 }, { 255, 255, 255, 255 } } },
        { { { -32, -8, 0 }, 0, { 0, 2560 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, -16, 0 }, 0, { 1024, 3072 }, { 255, 255, 255, 255 } } },
        { { { 0, -16, 0 }, 0, { 2048, 3072 }, { 255, 255, 255, 255 } } },
        { { { 0, -8, 0 }, 0, { 2048, 2560 }, { 255, 255, 255, 255 } } },
        { { { -16, -8, 0 }, 0, { 1024, 2560 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, -16, 0 }, 0, { 2048, 3072 }, { 255, 255, 255, 255 } } },
        { { { 16, -16, 0 }, 0, { 3072, 3072 }, { 255, 255, 255, 255 } } },
        { { { 16, -8, 0 }, 0, { 3072, 2560 }, { 255, 255, 255, 255 } } },
        { { { 0, -8, 0 }, 0, { 2048, 2560 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, -16, 0 }, 0, { 3072, 3072 }, { 255, 255, 255, 255 } } },
        { { { 32, -16, 0 }, 0, { 4096, 3072 }, { 255, 255, 255, 255 } } },
        { { { 32, -8, 0 }, 0, { 4096, 2560 }, { 255, 255, 255, 255 } } },
        { { { 16, -8, 0 }, 0, { 3072, 2560 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, -24, 0 }, 0, { 0, 3584 }, { 255, 255, 255, 255 } } },
        { { { -16, -24, 0 }, 0, { 1024, 3584 }, { 255, 255, 255, 255 } } },
        { { { -16, -16, 0 }, 0, { 1024, 3072 }, { 255, 255, 255, 255 } } },
        { { { -32, -16, 0 }, 0, { 0, 3072 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, -24, 0 }, 0, { 1024, 3584 }, { 255, 255, 255, 255 } } },
        { { { 0, -24, 0 }, 0, { 2048, 3584 }, { 255, 255, 255, 255 } } },
        { { { 0, -16, 0 }, 0, { 2048, 3072 }, { 255, 255, 255, 255 } } },
        { { { -16, -16, 0 }, 0, { 1024, 3072 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, -24, 0 }, 0, { 2048, 3584 }, { 255, 255, 255, 255 } } },
        { { { 16, -24, 0 }, 0, { 3072, 3584 }, { 255, 255, 255, 255 } } },
        { { { 16, -16, 0 }, 0, { 3072, 3072 }, { 255, 255, 255, 255 } } },
        { { { 0, -16, 0 }, 0, { 2048, 3072 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, -24, 0 }, 0, { 3072, 3584 }, { 255, 255, 255, 255 } } },
        { { { 32, -24, 0 }, 0, { 4096, 3584 }, { 255, 255, 255, 255 } } },
        { { { 32, -16, 0 }, 0, { 4096, 3072 }, { 255, 255, 255, 255 } } },
        { { { 16, -16, 0 }, 0, { 3072, 3072 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -32, -32, 0 }, 0, { 0, 4096 }, { 255, 255, 255, 255 } } },
        { { { -16, -32, 0 }, 0, { 1024, 4096 }, { 255, 255, 255, 255 } } },
        { { { -16, -24, 0 }, 0, { 1024, 3584 }, { 255, 255, 255, 255 } } },
        { { { -32, -24, 0 }, 0, { 0, 3584 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { -16, -32, 0 }, 0, { 1024, 4096 }, { 255, 255, 255, 255 } } },
        { { { 0, -32, 0 }, 0, { 2048, 4096 }, { 255, 255, 255, 255 } } },
        { { { 0, -24, 0 }, 0, { 2048, 3584 }, { 255, 255, 255, 255 } } },
        { { { -16, -24, 0 }, 0, { 1024, 3584 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 0, -32, 0 }, 0, { 2048, 4096 }, { 255, 255, 255, 255 } } },
        { { { 16, -32, 0 }, 0, { 3072, 4096 }, { 255, 255, 255, 255 } } },
        { { { 16, -24, 0 }, 0, { 3072, 3584 }, { 255, 255, 255, 255 } } },
        { { { 0, -24, 0 }, 0, { 2048, 3584 }, { 255, 255, 255, 255 } } },
    },
    {
        { { { 16, -32, 0 }, 0, { 3072, 4096 }, { 255, 255, 255, 255 } } },
        { { { 32, -32, 0 }, 0, { 4096, 4096 }, { 255, 255, 255, 255 } } },
        { { { 32, -24, 0 }, 0, { 4096, 3584 }, { 255, 255, 255, 255 } } },
        { { { 16, -24, 0 }, 0, { 3072, 3584 }, { 255, 255, 255, 255 } } },
    },
};

static const SohExtremeSoulVisual* ResolveSoulVisual(const GetItemEntry& entry) {
    // The drawing namespace is separate from the received item's namespace.
    // Respect an ice trap's disguise, but never interpret a vanilla/foreign ID
    // that happens to have the same number as a RandomizerGet as a soul.
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

    // Compatibility for callers that have not filled in the optional drawing
    // fields yet. A real item may fall back to its own ID; an undisguised trap may
    // not. Normal native/AP entries already resolve in the first branch above.
    if (entry.modIndex != MOD_RANDOMIZER || entry.getItemId == RG_ICE_TRAP) {
        return nullptr;
    }
    const auto* visual = SohExtreme_GetSoulVisual(static_cast<int>(entry.getItemId));
    return visual != nullptr ? visual : SohExtreme_GetSoulVisual(static_cast<int>(entry.itemId));
}

static bool HasPortraitResource(const char* icon) {
    if (icon == nullptr) {
        return false;
    }
    return ResourceMgr_FileExists(icon) ||
           (ResourceMgr_IsAltAssetsEnabled() && ResourceMgr_FileAltExists(icon));
}

static void DrawSoulFlame(PlayState* play, const SohExtremeSoulVisual& visual) {
    // Same native animated flame, scroll parameters, billboard and scale used by
    // Randomizer_DrawBossSoul. This is geometry with the flame DL's own alpha
    // material, NOT a flat RGBA upload of the inventory's gBossSoul texture.
    const s32 frame = static_cast<s32>(play->state.frames & 0x7FFFu);
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    gSPSegment(POLY_XLU_DISP++, 8,
               reinterpret_cast<uintptr_t>(Gfx_TwoTexScrollEx(play->state.gfxCtx, 0, 0, 0, 16, 32,
                                                             1, frame, -frame * 8, 16, 32, 0, 0, 1, -8)));
    Matrix_Push();
    Matrix_Translate(0.0f, -70.0f, 0.0f, MTXMODE_APPLY);
    Matrix_Scale(5.0f, 5.0f, 5.0f, MTXMODE_APPLY);
    Matrix_ReplaceRotation(&play->billboardMtxF);
    gSPMatrix(POLY_XLU_DISP++, Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);
    gDPSetGrayscaleColor(POLY_XLU_DISP++, visual.flameR, visual.flameG, visual.flameB, 255);
    gSPGrayscale(POLY_XLU_DISP++, true);
    gSPDisplayList(POLY_XLU_DISP++, (Gfx*)gGiBlueFireFlameDL);
    gSPGrayscale(POLY_XLU_DISP++, false);
    Matrix_Pop();
    CLOSE_DISPS(play->state.gfxCtx);
}

static void DrawSoulSkull(PlayState* play) {
    // Reuse the real 3D skull from the native "Simpler Boss Soul Models" path.
    // Category/animal souls and missing optional enemy portraits use this base.
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gSPGrayscale(POLY_XLU_DISP++, false);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 255, 255, 255, 255);
    gDPSetEnvColor(POLY_XLU_DISP++, 255, 255, 255, 255);
    gSPMatrix(POLY_XLU_DISP++, Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);
    gSPDisplayList(POLY_XLU_DISP++, (Gfx*)gBossSoulSkullDL);
    CLOSE_DISPS(play->state.gfxCtx);
}

static bool DrawSoulPortrait(PlayState* play, const SohExtremeSoulVisual& visual) {
    // Rebuilt from the original portraits, NOT enlarged copies of the final 32px
    // skull composite. Use private HQ resources only at their expected size.
    // Mods/older archives may omit them; keep the 32px resource as a safe fallback.
    const char* icon = SohExtreme_GetHqSoulPortrait(visual.item);
    const bool highResolution = HasPortraitResource(icon) &&
        ResourceMgr_LoadTexWidthByName(const_cast<char*>(icon)) == 128 &&
        ResourceMgr_LoadTexHeightByName(const_cast<char*>(icon)) == 128;
    if (!highResolution) {
        icon = visual.icon;
        if (!HasPortraitResource(icon)) {
            return false;
        }
    }

    // The portrait is the foreground. Its shared soul backing is subdued in the
    // artwork, rather than a second skull model drawn on top of the enemy.
    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    Matrix_Push();
    Matrix_ReplaceRotation(&play->billboardMtxF);
    gSPMatrix(POLY_XLU_DISP++, Matrix_NewMtx(play->state.gfxCtx, (char*)__FILE__, __LINE__),
              G_MTX_MODELVIEW | G_MTX_LOAD);

    // The flame uses a different material. Explicitly restore a one-cycle,
    // texture-alpha material instead of inheriting its combiner/tile state.
    gDPPipeSync(POLY_XLU_DISP++);
    gSPGrayscale(POLY_XLU_DISP++, false);
    gSPClearGeometryMode(POLY_XLU_DISP++, G_LIGHTING | G_CULL_BACK | G_CULL_FRONT | G_FOG |
                                              G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR);
    gDPSetCycleType(POLY_XLU_DISP++, G_CYC_1CYCLE);
    gDPSetRenderMode(POLY_XLU_DISP++, G_RM_AA_ZB_XLU_SURF, G_RM_AA_ZB_XLU_SURF2);
    gDPSetAlphaCompare(POLY_XLU_DISP++, G_AC_NONE);
    gDPSetTextureLUT(POLY_XLU_DISP++, G_TT_NONE);
    gDPSetTexturePersp(POLY_XLU_DISP++, G_TP_PERSP);
    gDPSetTextureFilter(POLY_XLU_DISP++, G_TF_BILERP);
    gSPTexture(POLY_XLU_DISP++, 0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON);
    gDPSetCombineMode(POLY_XLU_DISP++, G_CC_MODULATEIA_PRIM, G_CC_MODULATEIA_PRIM);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 255, 255, 255, 255);
    gDPSetEnvColor(POLY_XLU_DISP++, 255, 255, 255, 255);

    // Pass the aligned __OTR__ token, not a decoded pixel pointer. For HQ
    // portraits, load bounded tiles from the REAL 128px source; pretending it is
    // 32px would lose its stride/coordinates and recreates corrupt rectangles.
    if (highResolution) {
        for (int row = 0; row < 8; ++row) {
            for (int column = 0; column < 4; ++column) {
                const int left = column == 0 ? 0 : column * 32 - 1;
                const int top = row == 0 ? 0 : row * 16 - 1;
                const int right = column == 3 ? 127 : (column + 1) * 32;
                const int bottom = row == 7 ? 127 : (row + 1) * 16;
                gDPPipeSync(POLY_XLU_DISP++);
                gDPLoadTextureTile(POLY_XLU_DISP++, icon, G_IM_FMT_RGBA, G_IM_SIZ_32b,
                                   128, 128, left, top, right, bottom, 0,
                                   G_TX_CLAMP, G_TX_CLAMP, G_TX_NOMASK, G_TX_NOMASK,
                                   G_TX_NOLOD, G_TX_NOLOD);
                gSPVertex(POLY_XLU_DISP++,
                          reinterpret_cast<uintptr_t>(sHqSoulPortraitTiles[row * 4 + column]), 4, 0);
                gSP2Triangles(POLY_XLU_DISP++, 0, 1, 2, 0, 0, 2, 3, 0);
            }
        }
    } else {
        gDPLoadTextureBlock(POLY_XLU_DISP++, icon, G_IM_FMT_RGBA, G_IM_SIZ_32b, 32, 32, 0,
                           G_TX_CLAMP, G_TX_CLAMP, G_TX_NOMASK, G_TX_NOMASK, G_TX_NOLOD, G_TX_NOLOD);
        gSPVertex(POLY_XLU_DISP++, reinterpret_cast<uintptr_t>(sSoulPortraitQuad), 4, 0);
        gSP2Triangles(POLY_XLU_DISP++, 0, 1, 2, 0, 0, 2, 3, 0);
    }

    Matrix_Pop();
    CLOSE_DISPS(play->state.gfxCtx);
    return true;
}

static void RestoreSoulRenderState(PlayState* play) {
    // Do not leave the one-cycle portrait material or custom grayscale enabled
    // for a later pickup, shop model, or HUD command in the same frame.
    OPEN_DISPS(play->state.gfxCtx);
    gDPPipeSync(POLY_XLU_DISP++);
    gSPGrayscale(POLY_XLU_DISP++, false);
    Gfx_SetupDL_25Xlu(play->state.gfxCtx);
    gDPSetPrimColor(POLY_XLU_DISP++, 0, 0, 255, 255, 255, 255);
    gDPSetEnvColor(POLY_XLU_DISP++, 255, 255, 255, 255);
    CLOSE_DISPS(play->state.gfxCtx);
}

// Keep the existing ABI: StaticData::InitItemTable installs this callback using
// EnemySoulIcons.h. It now covers all 84 current soul IDs, not just 47 portraits.
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
        // The original boss renderer indexes a nine-entry palette. Only verified
        // boss IDs reach it, and an ice trap uses a LOCAL drawing copy, never a
        // mutation of the live receipt or the randomizer's shared ItemTable.
        GetItemEntry drawingEntry = *entry;
        drawingEntry.getItemId = static_cast<int16_t>(visual->item);
        drawingEntry.drawItemId = static_cast<uint16_t>(visual->item);
        Randomizer_DrawBossSoul(play, &drawingEntry);
    } else {
        DrawSoulFlame(play, *visual);
        if (visual->kind == SOH_SOUL_BEAN) {
            // Preserve the bean-soul sprout, now with the same animated soul
            // flame. Its native renderer scales the matrix, hence the outer
            // push/pop is essential for subsequent shop/freestanding models.
            Randomizer_DrawBeanSprout(play, entry);
        } else if (visual->kind != SOH_SOUL_PORTRAIT || !DrawSoulPortrait(play, *visual)) {
            DrawSoulSkull(play);
        }
    }
    Matrix_Pop();
    RestoreSoulRenderState(play);
}
