#pragma once
#define RANDO_ENUM_BEGIN(n) enum n {
#define RANDO_ENUM_ITEM(n, ...) n __VA_OPT__(=) __VA_ARGS__,
#define RANDO_ENUM_END(n) };
#include "RandomizerSettingKey.h"
#undef RANDO_ENUM_BEGIN
#undef RANDO_ENUM_ITEM
#undef RANDO_ENUM_END
