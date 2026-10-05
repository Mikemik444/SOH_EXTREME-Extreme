"""Run production AP price/placement and merchant payment functions with engine stubs.

Run from a VS x64 developer terminal. This validates transactions in isolation,
not a live game or server. No Archipelago Python dependencies are required.
"""
from pathlib import Path
import argparse
import json
import re
import subprocess
from run_native_tests import function

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
parser.add_argument('--output', type=Path, default=Path('work/ap-purchase-tests'))
args = parser.parse_args()
root = args.source_root.resolve()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
def read(path):
    return (root/path).read_text(encoding='utf-8')
ap = read('soh/Network/Archipelago/ArchipelagoClient.cpp')
loc = read('soh/Enhancements/randomizer/item_location.cpp')
hooks = read('soh/Enhancements/randomizer/hook_handlers.cpp')
girl = read('src/overlays/actors/ovl_En_GirlA/z_en_girla.c')
code = r'''
#include <cassert>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>
#define SPDLOG_INFO(...) ((void)0)
#define SPDLOG_DEBUG(...) ((void)0)
using RandomizerGet = int;
using RandomizerCheck = int;
using u32 = uint32_t;
using s32 = int32_t;
constexpr int RG_NONE=0, RG_ICE_TRAP=3, ITEMTYPE_SHOP=1;
struct Item {int price=0,type=0;int GetPrice()const{return price;}int GetItemType()const{return type;}};
namespace Rando {
namespace StaticData {
std::unordered_map<int,Item> items{{0,{0,0}},{1,{0,0}},{2,{50,ITEMTYPE_SHOP}},{3,{0,0}},{4,{0,0}}};
const Item& RetrieveItem(int id){return items.at(id);}
}
class ItemLocation {public:
 int placedItem=0;uint16_t price=0;bool hasCustomPrice=false,obtained=false;
 void SetPlacedItem(RandomizerGet);uint16_t GetPrice()const;void SetPrice(uint16_t);void SetCustomPrice(uint16_t);
 int GetPlacedRandomizerGet()const{return placedItem;}bool HasObtained()const{return obtained;}
};
struct Context {
 std::unordered_map<int,ItemLocation> locations;
 static Context*GetInstance(){static Context ctx;return &ctx;}
 ItemLocation*GetItemLocation(RandomizerCheck rc){auto it=locations.find(rc);return it==locations.end()?nullptr:&it->second;}
};
'''
code += '\n'.join(function(loc, sig) for sig in (
    'void ItemLocation::SetPlacedItem(', 'uint16_t ItemLocation::GetPrice()',
    'void ItemLocation::SetPrice(', 'void ItemLocation::SetCustomPrice('))
code += r'''
}
int AP_GetPlayerID(){return 1;}
int GetRemoteArchipelagoDisplay(int){return 4;}
class ArchipelagoClient {public:
 struct Scout {int playerId=1;std::string itemName="Reward",locationName="Scrub",playerName="Player";int64_t itemId=1;int flags=0;};
 bool active=true;
 std::unordered_map<int64_t,Scout>scoutedLocations;
 std::unordered_map<int64_t,uint16_t>shopPrices;
 std::unordered_map<int32_t,int64_t>rcToApLocation;
 std::unordered_map<int64_t,int32_t>apLocationToRc;
 static ArchipelagoClient&GetInstance(){static ArchipelagoClient c;return c;}
 bool IsGameplaySessionActive()const{return active;}
 int64_t ResolveApLocationForCheck(int32_t rc){auto it=rcToApLocation.find(rc);return it==rcToApLocation.end()?-1:it->second;}
 int MapApItemNameToRandomizerGet(const std::string&){return RG_NONE;}
 int MapApItemToRandomizerGet(int64_t id){return static_cast<int>(id);}
 int GetIceTrapDisguise(int64_t){return 2;}
 void RefreshPlacementForCheck(int32_t);void ApplyScoutedPlacements();
};
'''
code += function(ap, 'void ArchipelagoClient::RefreshPlacementForCheck(')
code += function(ap, 'void ArchipelagoClient::ApplyScoutedPlacements()')
code += r'''
void Archipelago_RefreshPlacementForCheck(int32_t rc){ArchipelagoClient::GetInstance().RefreshPlacementForCheck(rc);}
struct Identity {int randomizerInf=10,randomizerCheck=10;};
struct ScrubIdentity {Identity identity;int itemPrice=0;};
struct DnsItemEntry {int itemPrice=0;};
struct EnDns {DnsItemEntry*dnsItemEntry;};
ScrubIdentity scrubIdentity;
struct ObjectExtension {
 static ObjectExtension&GetInstance(){static ObjectExtension o;return o;}
 template<typename T>T*Get(EnDns*){return &scrubIdentity;}
};
struct {int rupees=0;}gSaveContext;
std::unordered_set<int> bought;
int paymentCalls=0;
bool Flags_GetRandomizerInf(int id){return bought.contains(id);}
void Flags_SetRandomizerInf(int id){bought.insert(id);}
void Rupees_ChangeBy(int delta){gSaveContext.rupees+=delta;++paymentCalls;}
constexpr int DNS_CANBUY_RESULT_CANT_GET_NOW=3,DNS_CANBUY_RESULT_NEED_RUPEES=0,DNS_CANBUY_RESULT_SUCCESS=4;
'''
code += function(hooks, 'u32 EnDns_RandomizerPurchaseableCheck(')
code += function(hooks, 'void EnDns_RandomizerPurchase(')
code += r'''
struct Player{}testPlayer;
struct PlayState {int sceneNum=1;};
#define GET_PLAYER(x) (&testPlayer)
struct EnGirlA {int randoSlotIndex=20,basePrice=0;};
struct ShopItemIdentity {Identity identity;int ogItemId=0,itemPrice=0;};
struct GetItemEntry{};
using ItemObtainability=int;
constexpr int CANT_OBTAIN_NEED_EMPTY_BOTTLE=1,CANT_OBTAIN_NEED_UPGRADE=2,CANT_OBTAIN_ALREADY_HAVE=3,CANT_OBTAIN_MISC=4;
constexpr int CANBUY_RESULT_NEED_BOTTLE=1,CANBUY_RESULT_CANT_GET_NOW_5=2,CANBUY_RESULT_CANT_GET_NOW=3,CANBUY_RESULT_NEED_RUPEES=4,CANBUY_RESULT_SUCCESS=5;
ShopItemIdentity Randomizer_IdentifyShopItem(int,int rc){
 Archipelago_RefreshPlacementForCheck(rc);
 return {{rc,rc},0,Rando::Context::GetInstance()->GetItemLocation(rc)->GetPrice()};
}
GetItemEntry Randomizer_GetItemFromKnownCheckWithoutObtainabilityCheck(int,int){return {};}
int Randomizer_GetItemObtainabilityFromRandomizerCheck(int){return 0;}
bool Archipelago_ShouldHandleCheck(int){return true;}
'''
for sig in ('s32 EnGirlA_CanBuy_Randomizer(', 'void EnGirlA_ItemGive_Randomizer('):
    code += re.sub(r'\bthis\b', 'self', function(girl[girl.rindex(sig):], sig))
code += r'''
int main(){
 auto&c=ArchipelagoClient::GetInstance();auto*ctx=Rando::Context::GetInstance();
 c.rcToApLocation={{10,1010},{20,1020},{30,1030}};
 c.apLocationToRc={{1010,10},{1020,20},{1030,30}};
 for(int rc:{10,20,30})ctx->locations.emplace(rc,Rando::ItemLocation{});
 auto&scrub=ctx->locations.at(10);auto&shop=ctx->locations.at(20);
 c.shopPrices={{1010,40},{1020,0},{1030,75}};
 // Price data must apply before any scouts arrive. Different price settings stay separate.
 c.RefreshPlacementForCheck(10);c.RefreshPlacementForCheck(20);
 assert(scrub.GetPrice()==40&&shop.GetPrice()==0&&scrub.hasCustomPrice&&shop.hasCustomPrice);
 // A local reward model and a remote player's model must not reset the location price.
 c.scoutedLocations[1010]={};c.RefreshPlacementForCheck(10);assert(scrub.GetPrice()==40);
 c.scoutedLocations[1010].playerId=2;c.RefreshPlacementForCheck(10);assert(scrub.GetPrice()==40);
 // Stock item prices and ice-trap disguises cannot override explicit prices, including zero.
 c.scoutedLocations[1020].itemId=2;c.RefreshPlacementForCheck(20);assert(shop.GetPrice()==0);
 c.scoutedLocations[1010].playerId=1;c.scoutedLocations[1010].itemId=3;
 c.RefreshPlacementForCheck(10);assert(scrub.GetPrice()==40);
 c.shopPrices[1010]=60;c.ApplyScoutedPlacements();assert(scrub.GetPrice()==60);
 // Old native custom prices are overridden by this slot; completed checks still keep their price.
 scrub.SetCustomPrice(5);scrub.obtained=true;c.RefreshPlacementForCheck(10);assert(scrub.GetPrice()==60);
 scrub.obtained=false;
 // Normal local saves and unknown locations do not receive AP price/model changes.
 c.active=false;shop.SetCustomPrice(25);c.RefreshPlacementForCheck(20);assert(shop.GetPrice()==25);
 c.ApplyScoutedPlacements();assert(shop.GetPrice()==25);c.active=true;
 c.RefreshPlacementForCheck(999);c.RefreshPlacementForCheck(20);
 // With no explicit price, the native stock-price behavior is retained.
 Rando::ItemLocation vanilla;vanilla.SetPlacedItem(2);assert(vanilla.GetPrice()==50);
 vanilla.SetPlacedItem(1);assert(vanilla.GetPrice()==0);
 // Scrub purchase refreshes a stale actor cache, refuses insufficient funds, and charges once.
 DnsItemEntry entry;EnDns actor{&entry};gSaveContext.rupees=59;
 assert(EnDns_RandomizerPurchaseableCheck(&actor)==DNS_CANBUY_RESULT_NEED_RUPEES);
 assert(entry.itemPrice==60&&gSaveContext.rupees==59&&paymentCalls==0);
 gSaveContext.rupees=100;assert(EnDns_RandomizerPurchaseableCheck(&actor)==DNS_CANBUY_RESULT_SUCCESS);
 EnDns_RandomizerPurchase(&actor);assert(gSaveContext.rupees==40&&paymentCalls==1);
 assert(EnDns_RandomizerPurchaseableCheck(&actor)==DNS_CANBUY_RESULT_CANT_GET_NOW);
 assert(gSaveContext.rupees==40&&paymentCalls==1);
 // A free scrub is free because of its own price, independent of shop settings.
 bought.clear();c.shopPrices[1010]=0;gSaveContext.rupees=0;
 assert(EnDns_RandomizerPurchaseableCheck(&actor)==DNS_CANBUY_RESULT_SUCCESS);
 EnDns_RandomizerPurchase(&actor);assert(gSaveContext.rupees==0);
 // A free shop stays free; a priced shop refreshes the same cache used for payment.
 bought.clear();PlayState play;EnGirlA shelf;gSaveContext.rupees=100;paymentCalls=0;
 assert(EnGirlA_CanBuy_Randomizer(&play,&shelf)==CANBUY_RESULT_SUCCESS);
 EnGirlA_ItemGive_Randomizer(&play,&shelf);assert(gSaveContext.rupees==100&&shelf.basePrice==0);
 bought.clear();c.shopPrices[1020]=75;shelf.basePrice=0;gSaveContext.rupees=74;
 assert(EnGirlA_CanBuy_Randomizer(&play,&shelf)==CANBUY_RESULT_NEED_RUPEES);
 assert(shelf.basePrice==75&&gSaveContext.rupees==74);
 gSaveContext.rupees=100;assert(EnGirlA_CanBuy_Randomizer(&play,&shelf)==CANBUY_RESULT_SUCCESS);
 EnGirlA_ItemGive_Randomizer(&play,&shelf);assert(gSaveContext.rupees==25);
 assert(EnGirlA_CanBuy_Randomizer(&play,&shelf)==CANBUY_RESULT_CANT_GET_NOW);
}
'''
src = out/'ap_purchase_prices.cpp'
exe = out/'ap_purchase_prices.exe'
src.write_text(code, encoding='utf-8')
build = subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD',str(src),
    '/Fo'+str(out/'ap_purchase_prices.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run = subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode == 0 else None
passed = build.returncode == 0 and run.returncode == 0
log = build.stdout+build.stderr+(run.stdout+run.stderr if run else '')
(out/'ap_purchase_prices.log').write_text(log)
checks = [dict(name='Production AP price/placement and scrub/shop payment regression',passed=passed)]
# Actor identity must refresh before caching price, not just when an item later draws.
for name, text, sig in [('scrub',hooks,'static ScrubIdentity IdentifyScrub('),
                      ('shop',read('soh/Enhancements/randomizer/randomizer.cpp'),'ShopItemIdentity Randomizer::IdentifyShopItem(')]:
    body = function(text,sig)
    valid = body.index('Archipelago_RefreshPlacementForCheck') < body.index('->GetPrice()')
    checks.append(dict(name=f'{name} identity initializes from AP location price',passed=valid))
scene = function(ap,'void ArchipelagoClient::RefreshPlacementsForScene(')
checks.append(dict(name='Scene prices refresh before scout responses',passed='scoutedLocations.empty()' not in scene))
(out/'results.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
if not passed:
    print(log[-6000:])
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
