"""Compile actual scrub-door predicates and the manual/automatic speech hook."""
from pathlib import Path
from run_native_tests import function
import argparse, json, re, subprocess, zipfile
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--baseline-zip',type=Path)
a=p.parse_args();r=Path(__file__).resolve().parent.parent
o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
def source(n):
    if a.baseline_zip:
        with zipfile.ZipFile(a.baseline_zip) as z:
            try:return z.read(n).decode('utf-8')
            except KeyError:return subprocess.check_output(['git','show','HEAD:'+n],cwd=r).decode('utf-8')
    return (r/n).read_text(encoding='utf-8')
dt=source('soh/Enhancements/randomizer/location_access/dungeons/deku_tree.cpp')
logic=source('soh/Enhancements/randomizer/logic.cpp')
speak=source('soh/Enhancements/randomizer/ShuffleSpeak.cpp')
graph=json.loads(source('archipelago/soh_extreme/EnemyRoomGraph.json'))
exprs=re.findall(r'ENTRANCE\(RR_DEKU_TREE_(?:SLINGSHOT_ROOM|LOBBY_2F|BOSS_ENTRYWAY),\s*(AnyAgeTime\(.*?)\),',dt)
assert len(exprs)==4
for rr in ('RR_DEKU_TREE_2F_MIDDLE_ROOM','RR_DEKU_TREE_OUTSIDE_BOSS_ROOM'):
    for e in graph[rr]['exits']:
        if 'CanReflectNuts' in e['condition']:assert e['condition'] in exprs
callback=function(speak,'COND_VB_SHOULD(VB_SPEAK,')
callback=callback[callback.index('{')+1:-1]
code=r'''
#include <iostream>
#include <set>
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "include/z64actor_enum.h"
struct Opt{int value;int Get(){return value;}};
struct Context{int soulMode=2,speakMode=2;Opt GetOption(RandomizerSettingKey k){
 return {k==RSK_SHUFFLE_ENEMY_SOUL?soulMode:speakMode};}} context;
Context* ctx=&context;
bool dekuSpeech=false,otherSpeech=false;
bool Flags_GetRandomizerInf(RandomizerInf f){return f==RAND_INF_CAN_SPEAK_DEKU?dekuSpeech:otherSpeech;}
struct Logic{
 bool IsAdult=false;std::set<RandomizerGet> items;
 bool HasItem(RandomizerGet i){return items.count(i);}
 bool CanUse(RandomizerGet i){return HasItem(i)&&(i==RG_DEKU_SHIELD?!IsAdult:i==RG_MEGATON_HAMMER?IsAdult:true);}
 bool CheckRandoInf(RandomizerInf f){return Flags_GetRandomizerInf(f);}
 bool CanReflectNuts();
} value;
Logic* logic=&value;
template<class F>bool AnyAgeTime(F f){return f();}
'''+function(logic,'bool Logic::CanReflectNuts()')+'\n'
if 'static bool CanTalkDekuTreeScrub()' in dt:code+=function(dt,'static bool CanTalkDekuTreeScrub()')+'\n'
for i,e in enumerate(exprs):code+=f'bool door{i}(){{return {e};}}\n'
code+=r'''
enum {ACTORCAT_BG=1,ACTORCAT_ENEMY=5,ACTORCAT_NPC=6};
constexpr unsigned ACTOR_FLAG_TALK_OFFER_AUTO_ACCEPTED=1;
enum {OSSAN_TYPE_KOKIRI,OSSAN_TYPE_KAKARIKO_POTION,OSSAN_TYPE_BOMBCHUS,OSSAN_TYPE_MARKET_POTION,
 OSSAN_TYPE_BAZAAR,OSSAN_TYPE_ADULT,OSSAN_TYPE_TALON,OSSAN_TYPE_ZORA,OSSAN_TYPE_GORON,
 OSSAN_TYPE_INGO,OSSAN_TYPE_MASK};
struct Actor{int id,category,params;unsigned flags;};
struct Player{Actor* talkActor;};
Player player{};
#define GET_PLAYER(play) (&player)
void speech(bool* should){
'''+callback+r'''
}
int main(){int tested=0,failed=0;
 auto check=[&](bool actual,bool expected){++tested;if(actual!=expected)++failed;};
 for(int mode=0;mode<3;++mode)for(int language=0;language<3;++language)
 for(int adult=0;adult<2;++adult)for(int bits=0;bits<64;++bits){
  context.soulMode=mode;context.speakMode=language;logic->IsAdult=adult;logic->items.clear();
  const RandomizerGet names[]={RG_ENEMY_SOUL_DEKU_SCRUB,RG_ENEMY_SOUL,RG_DEKU_SHIELD,RG_HYLIAN_SHIELD,RG_MEGATON_HAMMER};
  for(int n=0;n<5;++n)if(bits&(1<<n))logic->items.insert(names[n]);
  dekuSpeech=bits&32;
  bool talk=(mode==0||(mode==1&&(bits&2))||(mode==2&&(bits&1)))&&(language==0||dekuSpeech);
  bool reflect=adult?bool(bits&8):bool(bits&4), hammer=adult&&bool(bits&16);
  check(door0(),talk&&(reflect||hammer));check(door1(),talk&&(reflect||hammer));
  check(door2(),talk&&reflect);check(door3(),talk&&reflect);
 }
 // Execute the actual VB_SPEAK callback, including a BG actor with an
 // automatic talk offer. A denied action must never be turned back on.
 for(int language=0;language<3;++language)for(int known=0;known<2;++known)
 for(int cat:{ACTORCAT_ENEMY,ACTORCAT_BG,ACTORCAT_NPC})for(int automatic=0;automatic<2;++automatic)
 for(int initial=0;initial<2;++initial){
  Actor actor{ACTOR_EN_HINTNUTS,cat,0,unsigned(automatic)};player.talkActor=&actor;
  dekuSpeech=known;otherSpeech=true;bool allowed=initial;
  if(language) speech(&allowed); // registration is disabled when Speak is innate
  check(allowed,bool(initial&&(!language||known)));
 }
 // Ordinary mandatory NPC auto-dialogue still uses the existing exception.
 for(int automatic=0;automatic<2;++automatic){
  Actor actor{ACTOR_EN_KO,ACTORCAT_NPC,0,unsigned(automatic)};player.talkActor=&actor;
  otherSpeech=false;bool allowed=true;speech(&allowed);check(allowed,bool(automatic));
 }
 player.talkActor=nullptr;bool allowed=false;speech(&allowed);check(allowed,false);
 std::cout<<tested<<" assertions, "<<failed<<" failures\n";return failed?1:0;
}
'''
src=o/'scrub.cpp';exe=o/'scrub.exe';src.write_text(code)
c=subprocess.run(['cl','/nologo','/std:c++20','/Zc:preprocessor','/EHsc','/MD',
    '/I'+str(r),'/I'+str(r/'include'),str(src),'/Fo'+str(o/'scrub.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
log=c.stdout+c.stderr+(t.stdout+t.stderr if t else '')
match=re.search(r'(\d+) assertions, (\d+) failures',log)
report=dict(passed=c.returncode==0 and t.returncode==0,checks=int(match[1]) if match else 0,
    failures=int(match[2]) if match else None,output=log,
    limitations='Production predicates and speech callback compiled with controlled inventory/actor adapters; not live gameplay.')
(o/'native.json').write_text(json.dumps(report,indent=2));print(log)
raise SystemExit(not report['passed'])
