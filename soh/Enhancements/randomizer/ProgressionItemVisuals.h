#pragma once

#include "draw.h"
#include "align_asset_macro.h"

// Each resource has a dedicated 32x32 RGBA32 PNG in assets/custom.
static const ALIGN_ASSET(2) char gExtremeShovelIconTex[] =
    "__OTR__textures/parameter_static/gExtremeShovelIcon";
static const ALIGN_ASSET(2) char gExtremeRollIconTex[] =
    "__OTR__textures/parameter_static/gExtremeRollIcon";

#ifdef __cplusplus
extern "C" {
#endif
void SohExtreme_DrawShovel(PlayState* play, GetItemEntry* entry);
void SohExtreme_DrawRoll(PlayState* play, GetItemEntry* entry);
#ifdef __cplusplus
}
#endif
