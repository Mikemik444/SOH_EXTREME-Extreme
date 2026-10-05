"""Compile production shelf identity, purchase eligibility and payment callbacks.

Checks ownership before/after delayed scouting, all eight shelf positions, local
inventory rejection reasons, sold-out flags, native stock and AP prices.
Run from an x64 Visual Studio developer environment.
"""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess, zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--baseline-zip', type=Path)
a=p.parse_args(); root=Path(__file__).resolve().parent.parent
out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
def read(name):
    if a.baseline_zip:
        with zipfile.ZipFile(a.baseline_zip) as z:
            try:return z.read(name).decode('utf-8-sig')
            except KeyError:return subprocess.check_output(['git','show','HEAD:'+name],cwd=root).decode('utf-8-sig')
    return (root/name).read_text(encoding='utf-8-sig')
rando=read('soh/Enhancements/randomizer/randomizer.cpp')
girl=read('src/overlays/actors/ovl_En_GirlA/z_en_girla.c')
code=r'''
#include <cstdint>
#include <iostream>
#include <map>
using s32=int32_t; using u8=uint8_t; using RandomizerGet=int; using GetItemID=int;
constexpr int RAND_INF_MAX=-1,RC_UNKNOWN_CHECK=-1,GI_NONE=0,ACTOR_EN_GIRLA=4;
constexpr int SCENE_BAZAAR=4,SCENE_TEST01=9,ENTR_BAZAAR_0=1,SI_RANDOMIZED_ITEM=0x32;
constexpr int CANT_OBTAIN_NEED_EMPTY_BOTTLE=1,CANT_OBTAIN_NEED_UPGRADE=2,CANT_OBTAIN_ALREADY_HAVE=3,CANT_OBTAIN_MISC=4;
constexpr int CANBUY_RESULT_NEED_BOTTLE=1,CANBUY_RESULT_CANT_GET_NOW_5=2,CANBUY_RESULT_CANT_GET_NOW=3,CANBUY_RESULT_NEED_RUPEES=4,CANBUY_RESULT_SUCCESS=5;
using ItemObtainability=int;
struct Identity{int randomizerCheck=-1,randomizerInf=-1;};
struct ShopItemIdentity{Identity identity;int ogItemId=0,itemPrice=0,enGirlAShopItem=0;};
struct GetItemEntry{};
struct {int entranceIndex=0,rupees=0;} gSaveContext;
struct Record{int rc,placement=1,price=40,obtainability=0;bool active=false,bought=false;int GetPlacedRandomizerGet(){return placement;}int GetPrice(){return price;}};
std::map<int,Record> records;
namespace Rando{
struct Location{int rc=-1;int GetRandomizerCheck(){return rc;}int GetVanillaItem(){return 1;}} location;
struct Item{int GetItemID(){return 1;}} item;
namespace StaticData{Item&RetrieveItem(int){return item;}}
struct Context{static Context*GetInstance(){static Context c;return &c;}Record*GetItemLocation(int rc){return &records.at(rc);}};
}
struct OTRGlobals{Rando::Context*gRandoContext=Rando::Context::GetInstance();static OTRGlobals*Instance;};
OTRGlobals globals; OTRGlobals*OTRGlobals::Instance=&globals;
// The production map selects stock shield/tunic callbacks for these placeholders.
std::map<int,int> randomizerGetToEnGirlShopItem={{1,10},{2,11},{3,12}};
bool valid=true;int refreshes=0,refreshedPrice=-1,paymentCalls=0,flagCalls=0;
bool Archipelago_ShouldHandleCheck(int rc){return records.contains(rc)&&records.at(rc).active;}
void Archipelago_RefreshPlacementForCheck(int rc){++refreshes;if(refreshedPrice>=0)records.at(rc).price=refreshedPrice;}
bool Flags_GetRandomizerInf(int rc){return records.at(rc).bought;}
void Flags_SetRandomizerInf(int rc){records.at(rc).bought=true;++flagCalls;}
void Rupees_ChangeBy(int delta){gSaveContext.rupees+=delta;++paymentCalls;}
struct PlayState{int sceneNum=0;}; struct EnGirlA{int randoSlotIndex=0,basePrice=0;}; struct Player{}testPlayer;
#define GET_PLAYER(p) (&testPlayer)
class Randomizer{public:ShopItemIdentity IdentifyShopItem(s32,u8);};
Rando::Location*GetCheckObjectFromActor(int,int scene,int slot){Rando::location.rc=valid?scene*8+slot:-1;return &Rando::location;}
void IdentifyCheck(Identity*id,Rando::Location*l){id->randomizerCheck=id->randomizerInf=l->rc;}
'''
code+=function(rando,'ShopItemIdentity Randomizer::IdentifyShopItem(')
code+=r'''
Randomizer randomizer;
ShopItemIdentity Randomizer_IdentifyShopItem(int scene,int slot){return randomizer.IdentifyShopItem(scene,slot);}
GetItemEntry Randomizer_GetItemFromKnownCheckWithoutObtainabilityCheck(int,int){return {};}
int Randomizer_GetItemObtainabilityFromRandomizerCheck(int rc){return records.at(rc).obtainability;}
'''
for signature in ('s32 EnGirlA_CanBuy_Randomizer(', 'void EnGirlA_ItemGive_Randomizer('):
    code+=re.sub(r'\bthis\b','self',function(girl[girl.rindex(signature):],signature))
code+=r'''
int checks=0,failures=0;
void ck(bool pass,const char*name){++checks;if(!pass){if(failures<16)std::cerr<<name<<"\n";++failures;}}
int main(){
 for(int scene=0;scene<8;++scene)for(int slot=1;slot<=8;++slot){
  int rc=scene*8+slot-1;records.emplace(rc,Record{rc});
  auto&r=records.at(rc);PlayState play{scene};EnGirlA shelf{slot,999};
  for(bool active:{false,true})for(int placement:{1,2,3,4}){
   r.active=active;r.placement=placement;
   auto id=randomizer.IdentifyShopItem(scene,slot);
   ck(id.identity.randomizerCheck==rc,"correct shelf ID");
   ck(id.enGirlAShopItem==(active||placement==4?SI_RANDOMIZED_ITEM:randomizerGetToEnGirlShopItem.at(placement)),"AP placeholder uses check callbacks; stock preserves native callbacks");
   for(int rejected=0;rejected<5;++rejected)for(bool bought:{false,true})for(int price:{0,40,500})for(int money:{0,39,40,499,500}){
    r.obtainability=rejected;r.bought=bought;r.price=price;gSaveContext.rupees=money;
    paymentCalls=flagCalls=0;shelf.basePrice=999;
    int expected=CANBUY_RESULT_SUCCESS;
    if(bought) expected=CANBUY_RESULT_CANT_GET_NOW;
    else if(!active&&rejected) expected=rejected==1?CANBUY_RESULT_NEED_BOTTLE:rejected==2?CANBUY_RESULT_CANT_GET_NOW_5:CANBUY_RESULT_CANT_GET_NOW;
    else if(money<price) expected=CANBUY_RESULT_NEED_RUPEES;
    int result=EnGirlA_CanBuy_Randomizer(&play,&shelf);
    // Native error wording for an already-bought item is immaterial; all must refuse.
    ck(bought?result!=CANBUY_RESULT_SUCCESS:result==expected,"purchase honors check, price and AP ownership");
    ck(shelf.basePrice==price&&gSaveContext.rupees==money&&paymentCalls==0&&flagCalls==0,"eligibility refreshes price without charging");
    if(expected==CANBUY_RESULT_SUCCESS){
     EnGirlA_ItemGive_Randomizer(&play,&shelf);
     ck(gSaveContext.rupees==money-price&&paymentCalls==1&&flagCalls==1&&r.bought,"purchase charges once and marks exact check");
     ck(EnGirlA_CanBuy_Randomizer(&play,&shelf)!=CANBUY_RESULT_SUCCESS,"cannot buy completed check again");
    }
   }
  }
  // While scouts are pending, an active shield shelf uses randomized callbacks.
  r.active=true;r.bought=false;r.placement=1;r.obtainability=CANT_OBTAIN_ALREADY_HAVE;
  ck(randomizer.IdentifyShopItem(scene,slot).enGirlAShopItem==SI_RANDOMIZED_ITEM,"late scout shield placeholder");
  r.placement=4;r.obtainability=CANT_OBTAIN_MISC;refreshedPrice=35;gSaveContext.rupees=35;
  ck(EnGirlA_CanBuy_Randomizer(&play,&shelf)==CANBUY_RESULT_SUCCESS&&shelf.basePrice==35,"late scout and price remain purchasable");
  refreshedPrice=-1;
 }
 valid=false;ck(randomizer.IdentifyShopItem(0,1).identity.randomizerCheck==RC_UNKNOWN_CHECK,"unknown check stays unknown");
 int before=refreshes;ck(randomizer.IdentifyShopItem(0,0).identity.randomizerCheck==RC_UNKNOWN_CHECK&&refreshes==before,"invalid slot cannot access stock");
 std::cout<<"{\"checks\":"<<checks<<",\"failures\":"<<failures<<",\"passed\":"<<(failures?"false":"true")<<"}\n";
 return failures?1:0;
}
'''
src=out/'ap_shop_checks.cpp';exe=out/'ap_shop_checks.exe'
src.write_text(code,encoding='utf-8')
build=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD',str(src),
    '/Fo'+str(out/'ap_shop_checks.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
run=subprocess.run([str(exe)],capture_output=True,text=True) if build.returncode==0 else None
(out/'native.log').write_text(build.stdout+build.stderr+(run.stderr+run.stdout if run else ''))
if build.returncode:
    print(build.stdout+build.stderr);raise SystemExit(build.returncode)
report=json.loads(run.stdout)
(out/'native.json').write_text(json.dumps(report,indent=2)+'\n')
print(report);print(run.stderr)
raise SystemExit(run.returncode)
