#pragma once

#include "align_asset_macro.h"
#include "randomizerEnums.h"
#include "soh_assets.h"
#include "textures/icon_item_static/icon_item_static.h"

// Resource-name tokens, not decoded pixel pointers. Fast3D needs the resource
// metadata when these 32x32 RGBA32 portraits are PNG-backed or replaced by mods.
// Preserve these public names for existing item-table/tracker users.
static const ALIGN_ASSET(2) char gExtremeSoul_STALFOS[] =
    "__OTR__textures/parameter_static/gExtremeSoul_STALFOS";
static const ALIGN_ASSET(2) char gExtremeSoul_OCTOROK[] =
    "__OTR__textures/parameter_static/gExtremeSoul_OCTOROK";
static const ALIGN_ASSET(2) char gExtremeSoul_WALLMASTER[] =
    "__OTR__textures/parameter_static/gExtremeSoul_WALLMASTER";
static const ALIGN_ASSET(2) char gExtremeSoul_DODONGO[] =
    "__OTR__textures/parameter_static/gExtremeSoul_DODONGO";
static const ALIGN_ASSET(2) char gExtremeSoul_KEESE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_KEESE";
static const ALIGN_ASSET(2) char gExtremeSoul_TEKTITE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_TEKTITE";
static const ALIGN_ASSET(2) char gExtremeSoul_PEAHAT[] =
    "__OTR__textures/parameter_static/gExtremeSoul_PEAHAT";
static const ALIGN_ASSET(2) char gExtremeSoul_LIZALFOS_DINOLFOS[] =
    "__OTR__textures/parameter_static/gExtremeSoul_LIZALFOS_DINOLFOS";
static const ALIGN_ASSET(2) char gExtremeSoul_GOHMA_LARVA[] =
    "__OTR__textures/parameter_static/gExtremeSoul_GOHMA_LARVA";
static const ALIGN_ASSET(2) char gExtremeSoul_SHABOM[] =
    "__OTR__textures/parameter_static/gExtremeSoul_SHABOM";
static const ALIGN_ASSET(2) char gExtremeSoul_BABY_DODONGO[] =
    "__OTR__textures/parameter_static/gExtremeSoul_BABY_DODONGO";
static const ALIGN_ASSET(2) char gExtremeSoul_BIRI_BARI[] =
    "__OTR__textures/parameter_static/gExtremeSoul_BIRI_BARI";
static const ALIGN_ASSET(2) char gExtremeSoul_TAILPASARAN[] =
    "__OTR__textures/parameter_static/gExtremeSoul_TAILPASARAN";
static const ALIGN_ASSET(2) char gExtremeSoul_TORCH_SLUG[] =
    "__OTR__textures/parameter_static/gExtremeSoul_TORCH_SLUG";
static const ALIGN_ASSET(2) char gExtremeSoul_MOBLIN[] =
    "__OTR__textures/parameter_static/gExtremeSoul_MOBLIN";
static const ALIGN_ASSET(2) char gExtremeSoul_ARMOS[] =
    "__OTR__textures/parameter_static/gExtremeSoul_ARMOS";
static const ALIGN_ASSET(2) char gExtremeSoul_DEKU_BABA[] =
    "__OTR__textures/parameter_static/gExtremeSoul_DEKU_BABA";
static const ALIGN_ASSET(2) char gExtremeSoul_DEKU_SCRUB[] =
    "__OTR__textures/parameter_static/gExtremeSoul_DEKU_SCRUB";
static const ALIGN_ASSET(2) char gExtremeSoul_BUBBLE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_BUBBLE";
static const ALIGN_ASSET(2) char gExtremeSoul_BEAMOS[] =
    "__OTR__textures/parameter_static/gExtremeSoul_BEAMOS";
static const ALIGN_ASSET(2) char gExtremeSoul_FLOORMASTER[] =
    "__OTR__textures/parameter_static/gExtremeSoul_FLOORMASTER";
static const ALIGN_ASSET(2) char gExtremeSoul_REDEAD_GIBDO[] =
    "__OTR__textures/parameter_static/gExtremeSoul_REDEAD_GIBDO";
static const ALIGN_ASSET(2) char gExtremeSoul_FLARE_DANCER[] =
    "__OTR__textures/parameter_static/gExtremeSoul_FLARE_DANCER";
static const ALIGN_ASSET(2) char gExtremeSoul_DEAD_HAND[] =
    "__OTR__textures/parameter_static/gExtremeSoul_DEAD_HAND";
static const ALIGN_ASSET(2) char gExtremeSoul_SHELL_BLADE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_SHELL_BLADE";
static const ALIGN_ASSET(2) char gExtremeSoul_LIKE_LIKE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_LIKE_LIKE";
static const ALIGN_ASSET(2) char gExtremeSoul_SPIKE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_SPIKE";
static const ALIGN_ASSET(2) char gExtremeSoul_ANUBIS[] =
    "__OTR__textures/parameter_static/gExtremeSoul_ANUBIS";
static const ALIGN_ASSET(2) char gExtremeSoul_IRON_KNUCKLE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_IRON_KNUCKLE";
static const ALIGN_ASSET(2) char gExtremeSoul_SKULL_KID[] =
    "__OTR__textures/parameter_static/gExtremeSoul_SKULL_KID";
static const ALIGN_ASSET(2) char gExtremeSoul_FLYING_POT[] =
    "__OTR__textures/parameter_static/gExtremeSoul_FLYING_POT";
static const ALIGN_ASSET(2) char gExtremeSoul_FREEZARD[] =
    "__OTR__textures/parameter_static/gExtremeSoul_FREEZARD";
static const ALIGN_ASSET(2) char gExtremeSoul_STINGER[] =
    "__OTR__textures/parameter_static/gExtremeSoul_STINGER";
static const ALIGN_ASSET(2) char gExtremeSoul_WOLFOS[] =
    "__OTR__textures/parameter_static/gExtremeSoul_WOLFOS";
static const ALIGN_ASSET(2) char gExtremeSoul_GUAY[] =
    "__OTR__textures/parameter_static/gExtremeSoul_GUAY";
static const ALIGN_ASSET(2) char gExtremeSoul_JABU_TENTACLE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_JABU_TENTACLE";
static const ALIGN_ASSET(2) char gExtremeSoul_DARK_LINK[] =
    "__OTR__textures/parameter_static/gExtremeSoul_DARK_LINK";
static const ALIGN_ASSET(2) char gExtremeSoul_DOOR_TRAP[] =
    "__OTR__textures/parameter_static/gExtremeSoul_DOOR_TRAP";
static const ALIGN_ASSET(2) char gExtremeSoul_FLYING_FLOOR_TILE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_FLYING_FLOOR_TILE";
static const ALIGN_ASSET(2) char gExtremeSoul_GERUDO_THIEF[] =
    "__OTR__textures/parameter_static/gExtremeSoul_GERUDO_THIEF";
static const ALIGN_ASSET(2) char gExtremeSoul_POE_SISTER[] =
    "__OTR__textures/parameter_static/gExtremeSoul_POE_SISTER";
static const ALIGN_ASSET(2) char gExtremeSoul_POE[] =
    "__OTR__textures/parameter_static/gExtremeSoul_POE";
static const ALIGN_ASSET(2) char gExtremeSoul_LEEVER[] =
    "__OTR__textures/parameter_static/gExtremeSoul_LEEVER";
static const ALIGN_ASSET(2) char gExtremeSoul_STALCHILD[] =
    "__OTR__textures/parameter_static/gExtremeSoul_STALCHILD";
static const ALIGN_ASSET(2) char gExtremeSoul_BIG_OCTO[] =
    "__OTR__textures/parameter_static/gExtremeSoul_BIG_OCTO";
static const ALIGN_ASSET(2) char gExtremeSoul_SKULLTULA[] =
    "__OTR__textures/parameter_static/gExtremeSoul_SKULLTULA";
static const ALIGN_ASSET(2) char gExtremeSoul_BUSINESS_SCRUB[] =
    "__OTR__textures/parameter_static/gExtremeSoul_BUSINESS_SCRUB";

// Every soul in the current RandomizerGet enum is explicitly listed below.
// Do not infer membership from numeric ranges: the last eight enemy souls were
// appended AFTER unrelated items, and the bean/boss groups live elsewhere.
typedef enum SohExtremeSoulVisualKind {
    SOH_SOUL_SKULL,
    SOH_SOUL_PORTRAIT,
    SOH_SOUL_BEAN,
    SOH_SOUL_BOSS,
} SohExtremeSoulVisualKind;

typedef struct SohExtremeSoulVisual {
    RandomizerGet item;
    const char* icon;
    SohExtremeSoulVisualKind kind;
    unsigned char flameR;
    unsigned char flameG;
    unsigned char flameB;
} SohExtremeSoulVisual;

static const SohExtremeSoulVisual sSohExtremeSoulVisuals[] = {
    { RG_ENEMY_SOUL_STALFOS, gExtremeSoul_STALFOS, SOH_SOUL_PORTRAIT, 170, 210, 255 },
    { RG_ENEMY_SOUL_OCTOROK, gExtremeSoul_OCTOROK, SOH_SOUL_PORTRAIT, 85, 180, 223 },
    { RG_ENEMY_SOUL_WALLMASTER, gExtremeSoul_WALLMASTER, SOH_SOUL_PORTRAIT, 170, 95, 230 },
    { RG_ENEMY_SOUL_DODONGO, gExtremeSoul_DODONGO, SOH_SOUL_PORTRAIT, 237, 95, 95 },
    { RG_ENEMY_SOUL_KEESE, gExtremeSoul_KEESE, SOH_SOUL_PORTRAIT, 155, 110, 235 },
    { RG_ENEMY_SOUL_TEKTITE, gExtremeSoul_TEKTITE, SOH_SOUL_PORTRAIT, 245, 130, 70 },
    { RG_ENEMY_SOUL_PEAHAT, gExtremeSoul_PEAHAT, SOH_SOUL_PORTRAIT, 115, 205, 95 },
    { RG_ENEMY_SOUL_LIZALFOS_DINOLFOS, gExtremeSoul_LIZALFOS_DINOLFOS, SOH_SOUL_PORTRAIT, 115, 200, 95 },
    { RG_ENEMY_SOUL_GOHMA_LARVA, gExtremeSoul_GOHMA_LARVA, SOH_SOUL_PORTRAIT, 100, 240, 80 },
    { RG_ENEMY_SOUL_SHABOM, gExtremeSoul_SHABOM, SOH_SOUL_PORTRAIT, 130, 230, 245 },
    { RG_ENEMY_SOUL_BABY_DODONGO, gExtremeSoul_BABY_DODONGO, SOH_SOUL_PORTRAIT, 245, 140, 95 },
    { RG_ENEMY_SOUL_BIRI_BARI, gExtremeSoul_BIRI_BARI, SOH_SOUL_PORTRAIT, 90, 215, 255 },
    { RG_ENEMY_SOUL_TAILPASARAN, gExtremeSoul_TAILPASARAN, SOH_SOUL_PORTRAIT, 100, 220, 255 },
    { RG_ENEMY_SOUL_TORCH_SLUG, gExtremeSoul_TORCH_SLUG, SOH_SOUL_PORTRAIT, 255, 100, 50 },
    { RG_ENEMY_SOUL_MOBLIN, gExtremeSoul_MOBLIN, SOH_SOUL_PORTRAIT, 195, 150, 95 },
    { RG_ENEMY_SOUL_ARMOS, gExtremeSoul_ARMOS, SOH_SOUL_PORTRAIT, 195, 190, 145 },
    { RG_ENEMY_SOUL_DEKU_BABA, gExtremeSoul_DEKU_BABA, SOH_SOUL_PORTRAIT, 105, 225, 115 },
    { RG_ENEMY_SOUL_DEKU_SCRUB, gExtremeSoul_DEKU_SCRUB, SOH_SOUL_PORTRAIT, 105, 205, 95 },
    { RG_ENEMY_SOUL_BUBBLE, gExtremeSoul_BUBBLE, SOH_SOUL_PORTRAIT, 110, 185, 255 },
    { RG_ENEMY_SOUL_BEAMOS, gExtremeSoul_BEAMOS, SOH_SOUL_PORTRAIT, 230, 150, 85 },
    { RG_ENEMY_SOUL_FLOORMASTER, gExtremeSoul_FLOORMASTER, SOH_SOUL_PORTRAIT, 175, 100, 230 },
    { RG_ENEMY_SOUL_REDEAD_GIBDO, gExtremeSoul_REDEAD_GIBDO, SOH_SOUL_PORTRAIT, 155, 115, 190 },
    { RG_ENEMY_SOUL_FLARE_DANCER, gExtremeSoul_FLARE_DANCER, SOH_SOUL_PORTRAIT, 255, 110, 45 },
    { RG_ENEMY_SOUL_DEAD_HAND, gExtremeSoul_DEAD_HAND, SOH_SOUL_PORTRAIT, 200, 135, 220 },
    { RG_ENEMY_SOUL_SHELL_BLADE, gExtremeSoul_SHELL_BLADE, SOH_SOUL_PORTRAIT, 110, 200, 245 },
    { RG_ENEMY_SOUL_LIKE_LIKE, gExtremeSoul_LIKE_LIKE, SOH_SOUL_PORTRAIT, 235, 175, 120 },
    { RG_ENEMY_SOUL_SPIKE, gExtremeSoul_SPIKE, SOH_SOUL_PORTRAIT, 110, 195, 225 },
    { RG_ENEMY_SOUL_ANUBIS, gExtremeSoul_ANUBIS, SOH_SOUL_PORTRAIT, 240, 180, 75 },
    { RG_ENEMY_SOUL_IRON_KNUCKLE, gExtremeSoul_IRON_KNUCKLE, SOH_SOUL_PORTRAIT, 205, 165, 85 },
    { RG_ENEMY_SOUL_SKULL_KID, gExtremeSoul_SKULL_KID, SOH_SOUL_PORTRAIT, 170, 210, 85 },
    { RG_ENEMY_SOUL_FLYING_POT, gExtremeSoul_FLYING_POT, SOH_SOUL_PORTRAIT, 240, 170, 110 },
    { RG_ENEMY_SOUL_FREEZARD, gExtremeSoul_FREEZARD, SOH_SOUL_PORTRAIT, 110, 225, 255 },
    { RG_ENEMY_SOUL_STINGER, gExtremeSoul_STINGER, SOH_SOUL_PORTRAIT, 95, 190, 235 },
    { RG_ENEMY_SOUL_WOLFOS, gExtremeSoul_WOLFOS, SOH_SOUL_PORTRAIT, 190, 195, 245 },
    { RG_ENEMY_SOUL_GUAY, gExtremeSoul_GUAY, SOH_SOUL_PORTRAIT, 175, 135, 235 },
    { RG_ENEMY_SOUL_JABU_TENTACLE, gExtremeSoul_JABU_TENTACLE, SOH_SOUL_PORTRAIT, 220, 100, 160 },
    { RG_ENEMY_SOUL_DARK_LINK, gExtremeSoul_DARK_LINK, SOH_SOUL_PORTRAIT, 125, 110, 180 },
    { RG_ENEMY_SOUL_DOOR_TRAP, gExtremeSoul_DOOR_TRAP, SOH_SOUL_PORTRAIT, 210, 155, 105 },
    { RG_ENEMY_SOUL_FLYING_FLOOR_TILE, gExtremeSoul_FLYING_FLOOR_TILE, SOH_SOUL_PORTRAIT, 190, 170, 125 },
    { RG_ENEMY_SOUL_GERUDO_THIEF, gExtremeSoul_GERUDO_THIEF, SOH_SOUL_PORTRAIT, 240, 160, 70 },
    { RG_ENEMY_SOUL_POE_SISTER, gExtremeSoul_POE_SISTER, SOH_SOUL_PORTRAIT, 200, 100, 245 },
    { RG_ENEMY_SOUL_POE, gExtremeSoul_POE, SOH_SOUL_PORTRAIT, 175, 115, 240 },
    { RG_ENEMY_SOUL_LEEVER, gExtremeSoul_LEEVER, SOH_SOUL_PORTRAIT, 175, 220, 80 },
    { RG_ENEMY_SOUL_STALCHILD, gExtremeSoul_STALCHILD, SOH_SOUL_PORTRAIT, 180, 210, 240 },
    { RG_ENEMY_SOUL_BIG_OCTO, gExtremeSoul_BIG_OCTO, SOH_SOUL_PORTRAIT, 100, 190, 235 },
    { RG_SKULLTULA_SOUL, gExtremeSoul_SKULLTULA, SOH_SOUL_PORTRAIT, 240, 205, 70 },
    { RG_BUSINESS_SCRUB_SOUL, gExtremeSoul_BUSINESS_SCRUB, SOH_SOUL_PORTRAIT, 105, 220, 115 },
    { RG_ENEMY_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 235, 100, 160 },
    { RG_NPC_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 170, 155, 255 },
    { RG_ANIMAL_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 120, 220, 210 },
    { RG_POT_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 240, 150, 100 },
    { RG_CRATE_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 210, 165, 95 },
    { RG_GRASS_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 105, 230, 110 },
    { RG_ROCK_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 150, 185, 220 },
    { RG_TREE_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 95, 200, 120 },
    { RG_BEEHIVE_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 245, 200, 70 },
    { RG_SIGN_SOUL, gBossSoulTex, SOH_SOUL_SKULL, 210, 175, 125 },
    { RG_ANIMAL_SOUL_COW, gBossSoulTex, SOH_SOUL_SKULL, 180, 220, 255 },
    { RG_ANIMAL_SOUL_CUCCO, gBossSoulTex, SOH_SOUL_SKULL, 245, 235, 160 },
    { RG_ANIMAL_SOUL_DOG, gBossSoulTex, SOH_SOUL_SKULL, 230, 170, 125 },
    { RG_ANIMAL_SOUL_FISH, gBossSoulTex, SOH_SOUL_SKULL, 95, 195, 255 },
    { RG_ANIMAL_SOUL_BUG, gBossSoulTex, SOH_SOUL_SKULL, 125, 225, 100 },
    { RG_ANIMAL_SOUL_BUTTERFLY, gBossSoulTex, SOH_SOUL_SKULL, 225, 140, 245 },
    { RG_ANIMAL_SOUL_FROG, gBossSoulTex, SOH_SOUL_SKULL, 135, 220, 90 },
    { RG_ANIMAL_SOUL_HORSE, gBossSoulTex, SOH_SOUL_SKULL, 235, 180, 100 },
    { RG_DEATH_MOUNTAIN_CRATER_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_DEATH_MOUNTAIN_TRAIL_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_DESERT_COLOSSUS_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_GERUDO_VALLEY_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_GRAVEYARD_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_KOKIRI_FOREST_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_LAKE_HYLIA_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_LOST_WOODS_BRIDGE_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_LOST_WOODS_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_ZORAS_RIVER_BEAN_SOUL, gItemIconMagicBeanTex, SOH_SOUL_BEAN, 110, 235, 100 },
    { RG_GOHMA_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 0, 255, 0 },
    { RG_KING_DODONGO_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 255, 0, 100 },
    { RG_BARINADE_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 50, 255, 255 },
    { RG_PHANTOM_GANON_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 4, 195, 46 },
    { RG_VOLVAGIA_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 237, 95, 95 },
    { RG_MORPHA_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 85, 180, 223 },
    { RG_BONGO_BONGO_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 126, 16, 177 },
    { RG_TWINROVA_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 222, 158, 47 },
    { RG_GANON_SOUL, gBossSoulTex, SOH_SOUL_BOSS, 150, 150, 150 },
};

enum {
    SOH_EXTREME_SOUL_VISUAL_COUNT = sizeof(sSohExtremeSoulVisuals) / sizeof(sSohExtremeSoulVisuals[0])
};

// Accept an int so an invalid/foreign get-item ID can be rejected without first
// converting it to a RandomizerGet enum or indexing an unrelated boss palette.
static inline const SohExtremeSoulVisual* SohExtreme_GetSoulVisual(int item) {
    for (unsigned int i = 0; i < SOH_EXTREME_SOUL_VISUAL_COUNT; ++i) {
        if ((int)sSohExtremeSoulVisuals[i].item == item) {
            return &sSohExtremeSoulVisuals[i];
        }
    }
    return 0;
}

// Compatibility entry point. StaticData::InitItemTable already calls this for
// EVERY item and installs Randomizer_DrawEnemySoul for each non-null result.
// Returning all soul icons here extends that existing registration to category,
// animal, bean and boss souls, without altering any Item/GetItemEntry identity,
// progression flag, get-item animation, Archipelago ID, or ownership rule.
// Enemy portraits are unchanged; beans and bosses retain their existing UI icons.
static inline const char* SohExtreme_GetEnemySoulIcon(RandomizerGet item) {
    const SohExtremeSoulVisual* visual = SohExtreme_GetSoulVisual((int)item);
    return visual != 0 ? visual->icon : 0;
}
