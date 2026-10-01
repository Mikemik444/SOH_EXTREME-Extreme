"""Check all AP notes against full-song models and exercise native draw commands.

Uses real mapping/table/draw code with controlled graphics services; does not
render a game frame. Requires the VS x64 compiler on PATH.
"""
from pathlib import Path
import argparse, ast, json, re, subprocess
from run_native_tests import function
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
ap=(r/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8')
table=(r/'soh/Enhancements/randomizer/item_list.cpp').read_text(encoding='utf-8')
draw=(r/'src/code/z_draw.c').read_text(encoding='utf-8')
native=(r/'soh/Enhancements/randomizer/randomizer.cpp').read_text(encoding='utf-8')
world=ast.parse((r/'archipelago/soh_extreme/__init__.py').read_text(encoding='utf-8'))
expected=next(ast.literal_eval(n.value) for n in ast.walk(world) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SONG_NOTE_LAYOUT' for t in n.targets))
layout=ap[ap.index('struct SongNotes {'):ap.index('static std::string BuildApSongNotePickupDescription(')]
rows=re.findall(r'\{"([^"]+)", (\d+), (QUEST_\w+), (RG_AP_NOTE_\w+)\}',layout)
assert [(n,int(c)) for n,c,_,_ in rows]==list(expected)
entries={rg:re.search(r'itemTable\['+rg+r'\]\s*=\s*Item\(.*?;',table,re.S)[0] for _,_,_,rg in rows}
contracts=[]
for name,count,quest,rg in rows:
 entry=entries[rg]
 assert 'ITEMTYPE_ITEM' in entry and 'LOGIC_NONE' in entry and 'MOD_RANDOMIZER' in entry
 assert 'CHEST_ANIM_LONG' in entry and 'ITEM_CATEGORY_MAJOR' in entry
 gid=re.search(r'\bGID_SONG_\w+',entry)[0]
 full=re.search(r'itemTable\[RG_\w+\]\s*=\s*Item\([^\n]*Text\{ "'+re.escape(name)+r'"[^\n]+;',table)[0]
 assert gid==re.search(r'\bGID_SONG_\w+',full)[0],(name,gid)
 contracts.append(dict(song=name,count=int(count),display=rg,gid=gid))
# Every display entry shares the existing harmless AP switch branch, not a song grant.
noop=native[native.index('        case RG_AP_REMOTE_IMPORTANT:',native.index('Randomizer_Item_Give')):]
noop=noop[:noop.index('        default:')]
assert all('case '+row['display']+':' in noop for row in contracts)
assert noop.count('break;')==1 and not any(s in noop for s in ('Flags_Set','Item_Give(', 'questItems'))
enum=re.search(r'typedef enum \{([^{}]+)\} GetItemDrawID;', (r/'include/z64item.h').read_text(), re.S)[0]
rg_names=re.findall(r'^RANDO_ENUM_ITEM\((\w+)\)',(r/'soh/Enhancements/randomizer/randomizerEnums/RandomizerGet.h').read_text(),re.M)
code=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <string>
#include <unordered_map>
#include <vector>
#include <array>
using s16=int16_t;using s32=int32_t;using u8=uint8_t;using Gfx=int;
'''+enum+'\nenum RandomizerGet{'+','.join(rg_names)+'};\n'
code+='enum Quest{'+','.join(q for _,_,q,_ in rows)+'};\n'
code+='constexpr int64_t AP_FIRST_SONG_NOTE=9500020, AP_LAST_SONG_NOTE=9500093;\n'+layout+'\n'
code+=function(ap,'static RandomizerGet MapApItemNameToRandomizerGet(')+'\n'
code+=r'''
struct Text{std::string name;};
constexpr int ITEMTYPE_ITEM=0,LOGIC_NONE=0,RHT_NONE=0,OBJECT_GI_MELODY=1,TEXT_RANDOMIZER_CUSTOM_ITEM=2,CHEST_ANIM_LONG=1,ITEM_CATEGORY_MAJOR=1,MOD_RANDOMIZER=1;
struct Entry{int getItemId=0,gid=0,itemId=0;};
struct Item {Entry e;
 Item()=default;
 Item(int rg,Text,int,int gi,bool,int,int,int item,int,int gid,int,int,int,int,int){e={gi,gid,item};assert(rg==gi);}
};
Item itemTable[RG_MAX];
struct PlayState{struct{void*gfxCtx=nullptr;}state;}play;
struct DrawEntry{void(*drawFunc)(PlayState*,s16)=nullptr;Gfx*dlists[8]={};};
DrawEntry sDrawItemTable[GID_MAXIMUM];
std::array<int,3> color;bool grayscale=false;std::vector<Gfx*>lists;
Gfx commands[100];Gfx*poly=commands;
#define POLY_XLU_DISP poly
#define OPEN_DISPS(...) ((void)0)
#define CLOSE_DISPS(...) ((void)0)
#define gSPMatrix(...) ((void)0)
#define gDPSetGrayscaleColor(p,r,g,b,a) (color=std::array<int,3>{r,g,b})
#define gSPGrayscale(p,v) (grayscale=v)
#define gSPDisplayList(p,dl) lists.push_back(dl)
void Gfx_SetupDL_25Opa(void*){}void Gfx_SetupDL_25Xlu(void*){}
'''
for sig in ['void GetItem_DrawGenericMusicNote(PlayState* play, s16 drawId) {','void GetItem_DrawXlu01(PlayState* play, s16 drawId) {','void GetItem_Draw(PlayState* play, s16 drawId) {']:
 code+=function(draw,sig)+'\n'
draw_table=function(draw,'DrawItemTableEntry sDrawItemTable[] =')
draw_rows=re.findall(r'\{\s*(GetItem_Draw\w+),\s*\{([^{}]*)\}\s*\}',draw_table)
song_rows=[(i,f,ls.strip()) for i,(f,ls) in enumerate(draw_rows) if 'gGiSongNoteDL' in ls]
symbols=sorted(set(re.findall(r'\bgGi\w+', ' '.join(ls for _,_,ls in song_rows))))
code+='\n'.join('Gfx '+s+'[1]={};' for s in symbols)+'\n'
code+='int main(){int checks=0;auto ck=[&](bool ok){assert(ok);++checks;};\n'
code+='\n'.join(entries.values())+'\n'
code+='\n'.join(f'sDrawItemTable[{i}] = {{{f}, {{{ls}}}}};' for i,f,ls in song_rows)+'\n'
offset=0
for row in contracts:
 for n in range(offset+1,offset+row['count']+1):
  code+=f'ck(GetApSongNoteDisplay({9500019+n})=={row["display"]});ck(MapApItemNameToRandomizerGet("Song Note {n:02d}")=={row["display"]});\n'
 offset+=row['count']
 code+=f'ck(itemTable[{row["display"]}].e.gid=={row["gid"]});\n'
code+=r'''
for(auto name:{"Song Note","Song Note ","Song Note 00","Song Note 75","Song Note -1","Song Note 1x","Song Note 99999999999999999999"})ck(MapApItemNameToRandomizerGet(name)==RG_NONE);
ck(GetApSongNoteDisplay(AP_FIRST_SONG_NOTE-1)==RG_NONE);ck(GetApSongNoteDisplay(AP_LAST_SONG_NOTE+1)==RG_NONE);
const int expected[7][3]={{255,255,255},{109,73,143},{217,110,48},{62,109,23},{237,231,62},{98,177,211},{146,146,146}};
for(int i=0;i<7;++i){lists.clear();GetItem_Draw(&play,GID_SONG_GENERIC+i);
 ck(color==std::array<int,3>{expected[i][0],expected[i][1],expected[i][2]});
 ck(!grayscale&&lists.size()==1&&lists[0]==gGiSongNoteDL);
}
'''
for row in contracts[6:]:
 dl=next(ls for _,_,ls in song_rows if row['song'].split()[0].lower() in ls.lower())
 dlist=re.search(r'(gGi\w+ColorDL)',dl)[0]
 code+=f'lists.clear();GetItem_Draw(&play,{row["gid"]});ck(lists.size()==2&&lists[0]=={dlist}&&lists[1]==gGiSongNoteDL);\n'
code+='std::printf("%d assertions passed\\n",checks);}\n'
src=o/'colors.cpp';src.write_text(code,encoding='utf-8');exe=o/'colors.exe'
c=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD','/I',str(r/'soh/Network/Archipelago'),str(src),'/Fo'+str(o/'colors.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
report=dict(passed=c.returncode==0 and t.returncode==0,compile_output=c.stdout+c.stderr,output=t.stdout+t.stderr if t else '',songs=contracts,scope=__doc__)
(o/'colors.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report['passed'])
