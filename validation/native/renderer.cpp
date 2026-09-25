#include <cassert>
#include <cstdio>
#include <cstring>
#include <set>
#include <string>
#include "soh/Enhancements/randomizer/EnemySoulDraw.cpp"
static int depth=0,vertices=0;static Mtx matrix;
extern "C" void Gfx_SetupDL_25Xlu(GraphicsContext*) {}
extern "C" void Matrix_Push(void) { ++depth; }
extern "C" void Matrix_Pop(void) { --depth; }
extern "C" void Matrix_ReplaceRotation(MtxF*) {}
extern "C" void Matrix_Scale(float x,float y,float z,int mode) { assert(x==2 && y==2 && z==2 && mode==MTXMODE_APPLY); }
extern "C" Mtx* Matrix_NewMtx(GraphicsContext*,char*,int) { return &matrix; }
extern "C" void gSPVertex(Gfx* pkt,uintptr_t v,int n,int v0) { assert(v && n==4 && v0==0);vertices++;__gSPVertex(pkt,v,n,v0); }
int main() {
 const RandomizerGet ids[]={
RG_ENEMY_SOUL_STALFOS,
RG_ENEMY_SOUL_OCTOROK,
RG_ENEMY_SOUL_WALLMASTER,
RG_ENEMY_SOUL_DODONGO,
RG_ENEMY_SOUL_KEESE,
RG_ENEMY_SOUL_TEKTITE,
RG_ENEMY_SOUL_PEAHAT,
RG_ENEMY_SOUL_LIZALFOS_DINOLFOS,
RG_ENEMY_SOUL_GOHMA_LARVA,
RG_ENEMY_SOUL_SHABOM,
RG_ENEMY_SOUL_BABY_DODONGO,
RG_ENEMY_SOUL_BIRI_BARI,
RG_ENEMY_SOUL_TAILPASARAN,
RG_ENEMY_SOUL_TORCH_SLUG,
RG_ENEMY_SOUL_MOBLIN,
RG_ENEMY_SOUL_ARMOS,
RG_ENEMY_SOUL_DEKU_BABA,
RG_ENEMY_SOUL_DEKU_SCRUB,
RG_ENEMY_SOUL_BUBBLE,
RG_ENEMY_SOUL_BEAMOS,
RG_ENEMY_SOUL_FLOORMASTER,
RG_ENEMY_SOUL_REDEAD_GIBDO,
RG_ENEMY_SOUL_FLARE_DANCER,
RG_ENEMY_SOUL_DEAD_HAND,
RG_ENEMY_SOUL_SHELL_BLADE,
RG_ENEMY_SOUL_LIKE_LIKE,
RG_ENEMY_SOUL_SPIKE,
RG_ENEMY_SOUL_ANUBIS,
RG_ENEMY_SOUL_IRON_KNUCKLE,
RG_ENEMY_SOUL_SKULL_KID,
RG_ENEMY_SOUL_FLYING_POT,
RG_ENEMY_SOUL_FREEZARD,
RG_ENEMY_SOUL_STINGER,
RG_ENEMY_SOUL_WOLFOS,
RG_ENEMY_SOUL_GUAY,
RG_ENEMY_SOUL_JABU_TENTACLE,
RG_ENEMY_SOUL_DARK_LINK,
RG_ENEMY_SOUL_DOOR_TRAP,
RG_ENEMY_SOUL_FLYING_FLOOR_TILE,
RG_ENEMY_SOUL_GERUDO_THIEF,
RG_ENEMY_SOUL_POE_SISTER,
RG_ENEMY_SOUL_POE,
RG_ENEMY_SOUL_LEEVER,
RG_ENEMY_SOUL_STALCHILD,
RG_ENEMY_SOUL_BIG_OCTO,
RG_SKULLTULA_SOUL,
RG_BUSINESS_SCRUB_SOUL
 };
 GraphicsContext gfx{};PlayState play{};play.state.gfxCtx=&gfx;
 std::set<std::string> tokens;
 for (auto id:ids) {
  const char* tex=SohExtreme_GetEnemySoulIcon(id);assert(tex);assert(tokens.insert(tex).second);
  for (int disguise=0;disguise<2;++disguise) {
   GetItemEntry entry{};entry.getItemId=disguise?RG_ICE_TRAP:id;entry.drawItemId=id;
   gfx.count=0;int old=vertices;Randomizer_DrawEnemySoul(&play,&entry);
   assert(gfx.count>10 && gfx.count<256 && vertices==old+1 && depth==0);
  }
 }
 GetItemEntry bad{};bad.getItemId=RG_NONE;bad.drawItemId=RG_NONE;
 gfx.count=0;Randomizer_DrawEnemySoul(&play,&bad);assert(gfx.count==0 && depth==0);
 Randomizer_DrawEnemySoul(nullptr,&bad);Randomizer_DrawEnemySoul(&play,nullptr);
 assert(!SohExtreme_GetEnemySoulIcon(RG_GOHMA_SOUL));
 assert(!SohExtreme_GetEnemySoulIcon(RG_ENEMY_SOUL));
 assert(!SohExtreme_GetEnemySoulIcon(static_cast<RandomizerGet>(0x7fff)));
 printf("47 soul resources and 94 production renderer/disguise cases passed\n");
}
