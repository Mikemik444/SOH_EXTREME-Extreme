#pragma once
#define OPEN_DISPS(ctx) { Gfx* POLY_XLU_DISP = (ctx)->buffer;
#define CLOSE_DISPS(ctx) (ctx)->count = (int)(POLY_XLU_DISP - (ctx)->buffer); }
