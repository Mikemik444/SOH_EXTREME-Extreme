
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "soh/Enhancements/randomizer/BombchuRefillPolicy.h"
typedef int16_t s16;
enum { ITEM_BOMB, ITEM_BOMBCHU, ITEM_BOW, ITEM_SLINGSHOT, ITEM_COUNT, ITEM_NONE=255 };
enum { ITEM00_RUPEE_GREEN, ITEM00_BOMBS_A, ITEM00_BOMBS_B, ITEM00_BOMBS_SPECIAL,
 ITEM00_BOMBCHU, ITEM00_SEEDS, ITEM00_ARROWS_SMALL, ITEM00_ARROWS_MEDIUM, ITEM00_ARROWS_LARGE,
 ITEM00_STICK, ITEM00_MAGIC_LARGE, ITEM00_MAGIC_SMALL, ITEM00_HEART,
 ITEM00_SOH_GIVE_ITEM_ENTRY, ITEM00_SOH_GIVE_ITEM_ENTRY_GI, ITEM00_SOH_DUMMY };
enum { RO_BOMBCHU_BAG_NONE, RO_BOMBCHU_BAG_SINGLE, RO_BOMBCHU_BAG_PROGRESSIVE };
enum { RSK_BOMBCHU_BAG, RSK_ENABLE_BOMBCHU_DROPS, UPG_BOMB_BAG, VB_PREVENT_ADULT_STICK };
struct { int magicLevel,healthCapacity,health;
 struct { struct { struct { struct { unsigned bombchuUpgradeLevel; } randomizer; } data; } quest; } ship;
} gSaveContext;
static int inv[ITEM_COUNT],ammo[ITEM_COUNT],is_rando,age,bag_mode,drops_enabled,enhancement,capacity;
#define INV_CONTENT(i) inv[(i)]
#define AMMO(i) ammo[(i)]
#define IS_RANDO is_rando
#define LINK_IS_ADULT age
#define CUR_CAPACITY(i) capacity
#define CVAR_ENHANCEMENT(s) s
static int Randomizer_GetSettingValue(int k) { return k==RSK_BOMBCHU_BAG ? bag_mode : drops_enabled; }
static int CVarGetInteger(const char *k,int d) { (void)k;(void)d;return enhancement; }
static int Rand_Next(void) { return 1; }
static int GameInteractor_Should(int flag,int original) { (void)flag;return original; }
s16 EnItem00_ConvertBombDropToBombchu(s16 dropId) {
    if (INV_CONTENT(ITEM_BOMBCHU) == ITEM_NONE) {
        return dropId;
    }

    if (IS_RANDO && Randomizer_GetSettingValue(RSK_BOMBCHU_BAG) != RO_BOMBCHU_BAG_NONE) {
        // A real bag is required even when some other grant left an inventory slot.
        // Zero ammo must still be refillable; ownership is NOT an ammo-count test.
        // Once both bags are owned, ordinary bomb drops stay bombs.
        return SohExtreme_UseBombchuOnlyRefill(
                   CUR_CAPACITY(UPG_BOMB_BAG) != 0,
                   Randomizer_GetSettingValue(RSK_BOMBCHU_BAG) == RO_BOMBCHU_BAG_PROGRESSIVE,
                   INV_CONTENT(ITEM_BOMBCHU) != ITEM_NONE,
                   gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel)
                   ? ITEM00_BOMBCHU : dropId;
    }

    // Preserve the optional vanilla/no-Bombchu-bag mixed-ammo enhancement.
    if (INV_CONTENT(ITEM_BOMB) == ITEM_NONE) {
        return ITEM00_BOMBCHU;
    }
    if (AMMO(ITEM_BOMB) <= 15) {
        return AMMO(ITEM_BOMB) <= AMMO(ITEM_BOMBCHU) ? dropId : ITEM00_BOMBCHU;
    }
    if (AMMO(ITEM_BOMBCHU) <= 15) {
        return ITEM00_BOMBCHU;
    }
    return Rand_Next() % 2 ? dropId : ITEM00_BOMBCHU;
}

static s16 EnItem00_ConvertOrdinaryBombDrop(s16 dropId) {
    if (dropId != ITEM00_BOMBS_A && dropId != ITEM00_BOMBS_B && dropId != ITEM00_BOMBS_SPECIAL) {
        return dropId;
    }
    // Randomizer saves obey their seed option, not a conflicting local enhancement.
    const int enabled = IS_RANDO
        ? Randomizer_GetSettingValue(RSK_ENABLE_BOMBCHU_DROPS) != 0
        : CVarGetInteger(CVAR_ENHANCEMENT("EnableBombchuDrops"), 0) != 0;
    if (enabled && (!IS_RANDO || Randomizer_GetSettingValue(RSK_BOMBCHU_BAG) != RO_BOMBCHU_BAG_NONE ||
                    CUR_CAPACITY(UPG_BOMB_BAG) != 0)) {
        return EnItem00_ConvertBombDropToBombchu(dropId);
    }
    return dropId;
}

s16 func_8001F404(s16 dropId) {
    if (LINK_IS_ADULT) {
        if (dropId == ITEM00_SEEDS) {
            dropId = ITEM00_ARROWS_SMALL;
        } else if (GameInteractor_Should(VB_PREVENT_ADULT_STICK, dropId == ITEM00_STICK)) {
            dropId = ITEM00_RUPEE_GREEN;
        }
    } else {
        if (dropId == ITEM00_ARROWS_SMALL || dropId == ITEM00_ARROWS_MEDIUM || dropId == ITEM00_ARROWS_LARGE) {
            dropId = ITEM00_SEEDS;
        }
    }

    // #region [Randomizer] [Enchancment]
    // Convert BEFORE rejecting bombs for lack of a Bomb Bag.
    dropId = EnItem00_ConvertOrdinaryBombDrop(dropId);
    // #endregion

    // This is convoluted but it seems like it must be a single condition to match
    // clang-format off
    if (((dropId == ITEM00_BOMBS_A      || dropId == ITEM00_BOMBS_SPECIAL || dropId == ITEM00_BOMBS_B)      && CUR_CAPACITY(UPG_BOMB_BAG) == 0) ||
        ((dropId == ITEM00_ARROWS_SMALL || dropId == ITEM00_ARROWS_MEDIUM || dropId == ITEM00_ARROWS_LARGE) && INV_CONTENT(ITEM_BOW) == ITEM_NONE) ||
        ((dropId == ITEM00_MAGIC_LARGE  || dropId == ITEM00_MAGIC_SMALL)                                    && gSaveContext.magicLevel == 0) ||
        ((dropId == ITEM00_SEEDS)                                                                           && INV_CONTENT(ITEM_SLINGSHOT) == ITEM_NONE)) {
        return -1;
    }
    // clang-format on

    if (dropId == ITEM00_HEART && gSaveContext.healthCapacity == gSaveContext.health) {
        return ITEM00_RUPEE_GREEN;
    }

    return dropId;
}
static void reset(int mode,int bomb,int chu,unsigned level,int enabled) {
 memset(&gSaveContext,0,sizeof(gSaveContext));
 for(int i=0;i<ITEM_COUNT;i++){ inv[i]=ITEM_NONE;ammo[i]=0; }
 is_rando=1;age=0;bag_mode=mode;capacity=bomb?20:0;drops_enabled=enabled;enhancement=0;
 if(bomb)inv[ITEM_BOMB]=ITEM_BOMB;
 if(chu)inv[ITEM_BOMBCHU]=ITEM_BOMBCHU;
 gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel=level;
}
int main(void) {
 const int drops[]={ITEM00_BOMBS_A,ITEM00_BOMBS_B,ITEM00_BOMBS_SPECIAL};
 unsigned cases=0;
 for(int mode=1;mode<=2;mode++)for(int bomb=0;bomb<=1;bomb++)
 for(int chu=0;chu<=1;chu++)for(unsigned level=0;level<=3;level++)
 for(int enabled=0;enabled<=1;enabled++)for(int k=0;k<3;k++) {
  reset(mode,bomb,chu,level,enabled);
  int owned=chu && (mode==1 || level>0);
  int expected=(enabled && owned && !bomb) ? ITEM00_BOMBCHU : bomb ? drops[k] : -1;
  assert(func_8001F404(drops[k])==expected);
  // A conflicting enhancement toggle must not override a randomizer seed.
  enhancement=!enabled; assert(func_8001F404(drops[k])==expected);
  const int assigned[]={ITEM00_SOH_GIVE_ITEM_ENTRY,ITEM00_SOH_GIVE_ITEM_ENTRY_GI,ITEM00_SOH_DUMMY};
  for(int j=0;j<3;j++)assert(func_8001F404(assigned[j])==assigned[j]);
  assert(SohExtreme_CanReceiveBombchuRefill(1,mode==2,chu,level)==owned);
  cases++;
 }
 reset(1,0,1,0,1);ammo[ITEM_BOMBCHU]=0;
 assert(func_8001F404(ITEM00_BOMBS_A)==ITEM00_BOMBCHU);
 reset(1,1,1,0,1);ammo[ITEM_BOMB]=45;ammo[ITEM_BOMBCHU]=0;
 assert(func_8001F404(ITEM00_BOMBS_A)==ITEM00_BOMBS_A);
 reset(0,1,1,0,1);ammo[ITEM_BOMB]=30;ammo[ITEM_BOMBCHU]=0;
 assert(func_8001F404(ITEM00_BOMBS_A)==ITEM00_BOMBCHU); // legacy no-bag mixed drops
 reset(0,0,1,0,1);is_rando=0;enhancement=1;
 assert(func_8001F404(ITEM00_BOMBS_A)==ITEM00_BOMBCHU); // vanilla enhancement
 for(int cap=0;cap<=50;cap++)for(int current=-1;current<=60;current++)
 for(int pack=5;pack<=20;pack+=5){
  int clamped=current<0?0:current>cap?cap:current;
  int expected=clamped+pack>cap?cap:clamped+pack;
  assert(SohExtreme_AddBombchuRefill(current,pack,cap)==expected);cases++;
 }
 assert(SohExtreme_BombchuCapacity(1,0)==0);
 assert(SohExtreme_BombchuCapacity(1,1)==20);
 assert(SohExtreme_BombchuCapacity(1,2)==30);
 assert(SohExtreme_BombchuCapacity(1,3)==50);
 assert(SohExtreme_BombchuCapacity(0,0)==50);
 assert(SohExtreme_CanReceiveBombchuRefill(0,0,0,0)); // vanilla packs may unlock inventory
 printf("ordinary-drop and capacity cases: %u passed\n",cases);
}
