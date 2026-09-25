
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "z64item.h"
#include "soh/Enhancements/randomizer/BombchuRefillPolicy.h"
typedef uint8_t u8;
enum { RO_BOMBCHU_BAG_NONE, RO_BOMBCHU_BAG_SINGLE, RO_BOMBCHU_BAG_PROGRESSIVE };
enum { RSK_BOMBCHU_BAG, MOD_NONE, VB_CHECK_BOMBCHU_CAPACITY };
static int is_rando,bag_mode,capacity,inv[256],ammo[256],calls,last_item,hook_calls;
struct { struct { struct { struct { struct { unsigned bombchuUpgradeLevel; } randomizer; } data; } quest; } ship; } gSaveContext;
#define INV_CONTENT(i) inv[(i)]
#define AMMO(i) ammo[(i)]
#define IS_RANDO is_rando
#define CUR_CAPACITY(i) capacity
#define osSyncPrintf(...) ((void)0)
static int Randomizer_GetSettingValue(int k){(void)k;return bag_mode;}
static int GameInteractor_Should(int k,int value){assert(k==VB_CHECK_BOMBCHU_CAPACITY);hook_calls++;return value;}
static u8 Return_Item(u8 item,int mod,int ret){assert(mod==MOD_NONE);last_item=item;calls++;return ret;}
static u8 production_grants(u8 item) {
    // Ammo packs are not Bombchu Bag upgrades. This also protects AP filler
    // received before the bag, and leaves the original item-receive identity intact.
    if ((item == ITEM_BOMBCHU || item == ITEM_BOMBCHUS_5 || item == ITEM_BOMBCHUS_20) &&
        !SohExtreme_CanReceiveBombchuRefill(
            IS_RANDO && Randomizer_GetSettingValue(RSK_BOMBCHU_BAG) != RO_BOMBCHU_BAG_NONE,
            IS_RANDO && Randomizer_GetSettingValue(RSK_BOMBCHU_BAG) == RO_BOMBCHU_BAG_PROGRESSIVE,
            INV_CONTENT(ITEM_BOMBCHU) != ITEM_NONE,
            gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel)) {
        return Return_Item(item, MOD_NONE, ITEM_NONE);
    }

 static const int sAmmoRefillCounts[]={5,10,20,30};
 if (0) {
    } else if (item == ITEM_BOMB) {
        // "Bomb  Bomb  Bomb  Bomb Bomb   Bomb Bomb"
        osSyncPrintf(" 爆弾  爆弾  爆弾  爆弾 爆弾   爆弾 爆弾 \n");
        if ((AMMO(ITEM_BOMB) += 1) > CUR_CAPACITY(UPG_BOMB_BAG)) {
            AMMO(ITEM_BOMB) = CUR_CAPACITY(UPG_BOMB_BAG);
        }
        return Return_Item(item, MOD_NONE, ITEM_NONE);
    } else if ((item >= ITEM_BOMBS_5) && (item <= ITEM_BOMBS_30)) {
        if ((AMMO(ITEM_BOMB) += sAmmoRefillCounts[item - ITEM_BOMBS_5]) > CUR_CAPACITY(UPG_BOMB_BAG)) {
            AMMO(ITEM_BOMB) = CUR_CAPACITY(UPG_BOMB_BAG);
        }
        return Return_Item(item, MOD_NONE, ITEM_NONE);
    } else if (item == ITEM_BOMBCHU || item == ITEM_BOMBCHUS_5 || item == ITEM_BOMBCHUS_20) {
        const int refill = item == ITEM_BOMBCHU ? 10 : (item == ITEM_BOMBCHUS_5 ? 5 : 20);
        const int capacity = SohExtreme_BombchuCapacity(
            IS_RANDO && Randomizer_GetSettingValue(RSK_BOMBCHU_BAG) == RO_BOMBCHU_BAG_PROGRESSIVE,
            gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel);
        const int previous = INV_CONTENT(ITEM_BOMBCHU) == ITEM_NONE ? 0 : AMMO(ITEM_BOMBCHU);
        INV_CONTENT(ITEM_BOMBCHU) = ITEM_BOMBCHU;
        AMMO(ITEM_BOMBCHU) = SohExtreme_AddBombchuRefill(previous, refill, capacity);
        // Retain the existing capacity hook for other compatible enhancements.
        GameInteractor_Should(VB_CHECK_BOMBCHU_CAPACITY, true);
        return Return_Item(item, MOD_NONE, ITEM_NONE);

 }
 return item;
}

static void reset(int rando,int mode,int owned,unsigned level,int current,int bomb) {
 is_rando=rando;bag_mode=mode;capacity=bomb?20:0;calls=0;hook_calls=0;last_item=-1;
 for(int i=0;i<256;i++){inv[i]=ITEM_NONE;ammo[i]=0;}
 inv[ITEM_BOMBCHU]=owned?ITEM_BOMBCHU:ITEM_NONE;ammo[ITEM_BOMBCHU]=current;
 gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel=level;
}
int main(void){
 const int packs[]={ITEM_BOMBCHUS_5,ITEM_BOMBCHU,ITEM_BOMBCHUS_20};
 const int counts[]={5,10,20};unsigned cases=0;
 for(int rando=0;rando<2;rando++)for(int mode=0;mode<3;mode++)
 for(int owned=0;owned<2;owned++)for(unsigned level=0;level<5;level++)
 for(int current=0;current<61;current++)for(int p=0;p<3;p++) {
  reset(rando,mode,owned,level,current,0);
  int allowed=!rando || mode==0 || (owned && (mode==1 || level>0));
  int cap=rando && mode==2 ? (level==0?0:level==1?20:level==2?30:50) : 50;
  production_grants(packs[p]);
  assert(calls==1 && last_item==packs[p]); // identity retained even for an unavailable refill
  assert(gSaveContext.ship.quest.data.randomizer.bombchuUpgradeLevel==level);
  if(allowed){
   int old=owned?current:0; if(old>cap)old=cap;
   int want=old+counts[p]>cap?cap:old+counts[p];
   assert(inv[ITEM_BOMBCHU]==ITEM_BOMBCHU && ammo[ITEM_BOMBCHU]==want && hook_calls==1);
  } else {
   assert(inv[ITEM_BOMBCHU]==(owned?ITEM_BOMBCHU:ITEM_NONE));
   assert(ammo[ITEM_BOMBCHU]==current && hook_calls==0);
  }
  cases++;
 }
 const int bombs[]={ITEM_BOMB,ITEM_BOMBS_5,ITEM_BOMBS_10,ITEM_BOMBS_20,ITEM_BOMBS_30};
 const int bombcounts[]={1,5,10,20,30};
 for(int bag=0;bag<2;bag++)for(int p=0;p<5;p++) {
  reset(1,1,1,0,0,bag);production_grants(bombs[p]);
  assert(ammo[ITEM_BOMBCHU]==0 && inv[ITEM_BOMBCHU]==ITEM_BOMBCHU);
  int expected=bag?(bombcounts[p]>20?20:bombcounts[p]):0;
  assert(ammo[ITEM_BOMB]==expected && last_item==bombs[p] && calls==1);cases++;
 }
 printf("Item_Give Bombchu/assigned-bomb branch cases: %u passed\n",cases);
}
