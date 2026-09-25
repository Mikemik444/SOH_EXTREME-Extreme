#pragma once
#define DEFINE_ENTRANCE(name, _1, _2, _3, _4, _5, _6) name,
typedef enum {
#include "entrance_table.h"
ENTR_MAX
} EntranceIndex;
#undef DEFINE_ENTRANCE
