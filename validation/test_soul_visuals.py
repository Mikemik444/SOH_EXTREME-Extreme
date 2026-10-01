"""Compile real soul draw code with recorded GPU services; audit shipped art.

Checks draw identity, safe texture dimensions, mesh indices, missing-resource
fallbacks and balanced matrix/display scopes. This is not an in-game playtest.
"""
from pathlib import Path
import argparse, json, re, subprocess
from PIL import Image
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[1];o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
d=r/'soh/Enhancements/randomizer'
def clean(name):
 return re.sub(r'^\s*#(?:include|pragma)[^\n]*','',(d/name).read_text(),flags=re.M)
headers='\n'.join(clean(n) for n in ['SoulEmblemAssets.h','SoulPortraitHQ.h','EnemySoulIcons.h','SoulPortraitTiles.h'])
body=clean('SoulRelicMesh.inc')+'\n'+clean('EnemySoulDraw.cpp')
enums=re.findall(r'RANDO_ENUM_ITEM\((RG_\w+)\)',(d/'randomizerEnums/RandomizerGet.h').read_text())
expected={n for n in enums if '_SOUL' in n}
mapped=re.findall(r'^\s*\{ (RG_\w+), \w+, SOH_SOUL_\w+,',headers,re.M)
assert len(mapped)==len(set(mapped))==84 and set(mapped)==expected
art=[]
for token in sorted(set(re.findall(r'"__OTR__(textures/parameter_static/gSoulEmblem_[^"]+)"',headers))):
 f=r/'soh/assets/custom'/ (token+'.rgba32.png')
 with Image.open(f) as im:
  size=128 if token.endswith('_GUI') else 32
  assert im.size==(size,size) and im.mode=='RGBA',f
  assert im.getchannel('A').getextrema()==(0,255),f
  art.append(dict(resource=token,size=size))
assert len(art)==222
constants=set(re.findall(r'\b(?:G_[A-Z_a-z0-9]+|MTXMODE_[A-Z_]+)\b',body))
code='''#include <cstdint>
#include <cmath>
#include <cassert>
#include <iostream>
#include <set>
#include <string>
#include <vector>
using s32=int32_t;
#define ALIGN_ASSET(x)
enum RandomizerGet {'''+','.join(enums)+'''};
enum { MOD_NONE, MOD_RANDOMIZER, MOD_FOREIGN };
'''+''.join('#define '+c+' 0\n' for c in sorted(constants))+'''
const char gBossSoulTex[]="__OTR__skull";
const char gItemIconMagicBeanTex[]="__OTR__bean";
'''+headers+r'''
struct Vtx{struct{int pos[3];int flag;int uv[2];uint8_t color[4];}v;};
struct Gfx{};struct GraphicsContext{}gfx;Gfx opa[10000],xlu[10000];Gfx* op=opa;Gfx* xp=xlu;
struct PlayState{struct{GraphicsContext*gfxCtx=&gfx;uint32_t frames=0;}state;int billboardMtxF=0;}play;
struct GetItemEntry{int drawModIndex=MOD_RANDOMIZER,drawItemId=RG_NONE,modIndex=MOD_RANDOMIZER,getItemId=RG_NONE,itemId=RG_NONE;};
int stack=0,scopes=0,boss=0,bean=0,skulls=0,vertexBatch=0,triangles=0;bool allResources=true,iconsOnly=false;
std::set<std::string> absent;std::vector<std::string> loads;
bool ResourceMgr_FileExists(const char*t){return allResources && !absent.count(t) && (!iconsOnly||std::string(t).find("Tile")==std::string::npos);}
bool ResourceMgr_IsAltAssetsEnabled(){return false;}bool ResourceMgr_FileAltExists(const char*){return false;}
const char gGiBlueFireFlameDL[]="flame",gBossSoulSkullDL[]="skull";
void Gfx_SetupDL_25Xlu(GraphicsContext*){}void Gfx_SetupDL_25Opa(GraphicsContext*){}
void Matrix_Push(){++stack;}void Matrix_Pop(){assert(stack>0);--stack;}
void Matrix_Translate(float x,float y,float z,int){assert(std::isfinite(x+y+z));}
void Matrix_Scale(float x,float y,float z,int){assert(x>0&&y>0&&z>0);}
void Matrix_RotateY(float y,int){assert(std::isfinite(y));}void Matrix_ReplaceRotation(int*){}
void Randomizer_DrawBossSoul(PlayState*,GetItemEntry*e){assert(e->getItemId==e->drawItemId);++boss;}
void Randomizer_DrawBeanSprout(PlayState*,GetItemEntry*){++bean;}
#define OPEN_DISPS(...) { ++scopes;
#define CLOSE_DISPS(...) --scopes; }
#define POLY_OPA_DISP op
#define POLY_XLU_DISP xp
#define gDPPipeSync(p) ((void)(p))
#define gDPSetTextureLUT(p,...) ((void)(p))
#define gSPGrayscale(p,...) ((void)(p))
#define gDPSetPrimColor(p,...) ((void)(p))
#define gDPSetEnvColor(p,...) ((void)(p))
#define gSPMatrix(p,...) ((void)(p))
#define gSPClearGeometryMode(p,...) ((void)(p))
#define gSPSetGeometryMode(p,...) ((void)(p))
#define gDPSetCycleType(p,...) ((void)(p))
#define gDPSetRenderMode(p,...) ((void)(p))
#define gDPSetAlphaCompare(p,...) ((void)(p))
#define gDPSetTexturePersp(p,...) ((void)(p))
#define gDPSetTextureFilter(p,...) ((void)(p))
#define gSPTexture(p,...) ((void)(p))
#define gDPSetCombineMode(p,...) ((void)(p))
#define gDPSetCombineLERP(p,...) ((void)(p))
#define gDPSetGrayscaleColor(p,...) ((void)(p))
#define gSPSegment(p,...) ((void)(p))
#define gSPDisplayList(p,dl) do{(void)(p);if((void*)(dl)==(void*)gBossSoulSkullDL)++skulls;}while(0)
#define gDPLoadTextureBlock(p,t,f,s,w,h,...) do{(void)(p);assert(w==32&&h==32);loads.push_back(t);}while(0)
#define gSPVertex(p,v,n,i) do{(void)(p);vertexBatch=(n);assert(vertexBatch>0&&vertexBatch<=32);}while(0)
#define gSP1Triangle(p,a,b,c,...) do{(void)(p);assert(a<vertexBatch&&b<vertexBatch&&c<vertexBatch);++triangles;}while(0)
#define gSP2Triangles(p,a,b,c,d,e,f,g,h) do{(void)(p);assert(a<vertexBatch&&b<vertexBatch&&c<vertexBatch&&e<vertexBatch&&f<vertexBatch&&g<vertexBatch);triangles+=2;}while(0)
'''+body+r'''
int assertions=0;
#define CK(x) do{++assertions;if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
void reset(){op=opa;xp=xlu;loads.clear();boss=bean=skulls=triangles=0;}
int main(){
 for(const auto&v:sSohExtremeSoulVisuals){
  CK(SohExtreme_GetSoulGuiIcon(v.item)!=nullptr);CK(SohExtreme_GetEnemySoulIcon(v.item)!=nullptr);
  for(int mode=0;mode<4;++mode)for(int frame:{0,1,90,32767,65535}){
   reset();play.state.frames=frame;allResources=mode!=2;iconsOnly=mode==1;
   GetItemEntry e;e.drawItemId=v.item;e.getItemId=mode==3?RG_ICE_TRAP:v.item;e.itemId=v.item;
   auto original=e;Randomizer_DrawEnemySoul(&play,&e);
   CK(stack==0&&scopes==0);CK(e.drawItemId==original.drawItemId&&e.getItemId==original.getItemId);
   if(v.kind==SOH_SOUL_BOSS){CK(boss==1&&loads.empty());}
   else if(v.kind==SOH_SOUL_BEAN){CK(bean==1&&loads.empty());}
   else if(mode==2){CK(skulls==1&&loads.empty());}
   else {CK(loads.size()==(mode==1?1:4));CK(triangles>=130);}
  }
  reset();allResources=true;iconsOnly=false;GetItemEntry e;e.getItemId=v.item;
  CK(ResolveSoulVisual(e)==&v);
  e.drawModIndex=MOD_FOREIGN;CK(ResolveSoulVisual(e)==nullptr);
  e.drawModIndex=MOD_RANDOMIZER;e.drawItemId=RG_ICE_TRAP;CK(ResolveSoulVisual(e)==nullptr);
 }
 for(int bad:{-1,999999}){GetItemEntry e;e.drawItemId=bad;reset();Randomizer_DrawEnemySoul(&play,&e);CK(loads.empty()&&boss==0&&bean==0&&stack==0);}
 reset();Randomizer_DrawEnemySoul(nullptr,nullptr);Randomizer_DrawEnemySoul(&play,nullptr);CK(stack==0&&scopes==0);
 GetItemEntry e;e.drawItemId=RG_NPC_SOUL;play.state.gfxCtx=nullptr;Randomizer_DrawEnemySoul(&play,&e);CK(loads.empty());
 play.state.gfxCtx=&gfx;
 allResources=true;iconsOnly=false;const auto* emblem=SohExtreme_GetSoulEmblem(RG_NPC_SOUL);
 for(int i=0;i<4;++i){reset();absent={emblem->tiles[i]};Randomizer_DrawEnemySoul(&play,&e);CK(loads.size()==1&&loads[0]==emblem->icon&&stack==0&&scopes==0);}
 CK(sizeof(sSoulRelicRim)/sizeof(Vtx)%3==0);
 for(const auto&v:sSoulRelicRim){CK(abs(v.v.pos[0])<=39&&abs(v.v.pos[1])<=39&&v.v.pos[2]>=-5&&v.v.pos[2]<=4);}
 std::cout<<assertions<<" soul draw assertions passed\n";
}
'''
src=o/'soul_draw.cpp';src.write_text(code);exe=o/'soul_draw.exe'
c=subprocess.run(['cl','/nologo','/EHsc','/std:c++20','/Zc:preprocessor',str(src),'/Fo'+str(o/'soul_draw.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
report=dict(passed=c.returncode==0 and t.returncode==0,souls=len(mapped),assets=art,output=c.stdout+c.stderr+(t.stdout+t.stderr if t else ''),scope=__doc__)
(o/'visuals.json').write_text(json.dumps(report,indent=2));print(report['output']);raise SystemExit(not report['passed'])
