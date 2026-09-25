#pragma once
#include <stdint.h>
#include <libultraship/libultra.h>
typedef struct { Gfx buffer[256]; int count; } GraphicsContext;
struct PlayState { struct { GraphicsContext* gfxCtx; } state; MtxF billboardMtxF; };
#define MTXMODE_APPLY 1
