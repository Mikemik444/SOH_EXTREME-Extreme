"""Compile the real save-menu state machine with recorded engine/save services.

Covers save-before-warp, age spawn, scene choices, reload and cancellation.
Does not launch the game or write a user save.
"""
from pathlib import Path
from run_native_tests import function
import argparse
import hashlib
import json
import re
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--baseline',type=Path)
a=p.parse_args();r=Path(__file__).resolve().parent.parent;o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
path=a.baseline or r/'soh/Enhancements/QoL/BetterSaveMenu.cpp'
s=path.read_text(encoding='utf-8-sig')
body='\n'.join(function(s,signature) for signature in (
    ('static int16_t GetAgeSpawnEntrance(',) if 'static int16_t GetAgeSpawnEntrance(' in s else ())+
    ('bool IsSceneDungeon(', 'void HandleSaveMenu('))
constants=sorted(set(re.findall(r'\b(?:SCENE|TEXT|NA|DO_ACTION|BTN|TRANS_TYPE|SEQ_PLAYER|MAGIC_STATE)_\w+',body))|
    {'SCENE_LINKS_HOUSE','SCENE_THIEVES_HIDEOUT','SCENE_HYRULE_FIELD','SCENE_GROTTOS','SCENE_FAIRYS_FOUNTAIN'})
scene_ids=sorted(n for n in constants if n.startswith('SCENE_'))
if not a.baseline:
    assert '#define CVAR_BETTERSAVE_DEFAULT 1' in s
    ui=(r/'soh/SohGui/SohMenuEnhancements.cpp').read_text(encoding='utf-8-sig')
    widget=ui[ui.index('    AddWidget(path, "Better Save Menu"'):]
    widget=widget[:widget.index('\n\n')]
    assert '.DefaultValue(true)' in widget
    assert 'Return to Spawn' in widget
    assert 'CVAR_BETTERSAVE_VALUE' in s
code=r'''
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
enum Constants {'''+','.join(constants)+r'''};
constexpr int ENTR_LINKS_HOUSE_CHILD_SPAWN=0xBB, ENTR_HYRULE_FIELD_10=0x282,
    ENTR_TEMPLE_OF_TIME_WARP_PAD=0x5F4;
struct PauseContext{int state=7,unk_1EC=0,promptChoice=0;float unk_204=0;};
struct InterfaceContext{int unk_244=0;};
struct MessageContext{int choiceIndex=0,textId=0,state=TEXT_STATE_CHOICE;};
struct GameState{bool running=true;};
struct PlayState { PauseContext pauseCtx;InterfaceContext interfaceCtx;MessageContext msgCtx;
    GameState state;int gameplayFrames=1000,sceneNum=SCENE_HYRULE_FIELD,objectCtx=0,colCtx=0;};
struct SaveContext {struct{int resetToSpawn=0;}ship;
    int savedSceneNum=SCENE_HYRULE_FIELD,entranceIndex=321,fileNum=1,linkAge=1;
    int buttonStatus[9]{},hudVisibilityMode=3,nextTransitionType=0,healthAccumulator=0,
        magicState=1,prevMagicState=1,magicCapacity=96,magicFillTarget=0,magicLevel=2,magic=80,
        seqId=1,natureAmbienceId=0;
    int ownedItems=67,checkedLocations=539,pendingApChecks=3,receivedApItems=712;
}gSaveContext,saved;
bool rando=true,advance=false,remember=false,shuffleSpawn=false;
int saveWrites=0,loads=0,flags=0,exits=0,loadHooks=0,overrides=0,worldStarts=0;
std::vector<std::string>order;
PlayState testPlay;
#define IS_RANDO rando
#define LINK_IS_CHILD (gSaveContext.linkAge==1)
#define CVAR_ENHANCEMENT(k) k
int CVarGetInteger(const char*,int){return remember;}
int16_t Entrance_OverrideNextIndex(int16_t index){++overrides;return index+(shuffleSpawn?5000:0);}
void Message_StartTextbox(PlayState*p,int id,void*){p->msgCtx.textId=id;p->msgCtx.state=TEXT_STATE_CHOICE;advance=false;}
int Message_GetState(MessageContext*c){return c->state;}
bool Message_ShouldAdvance(PlayState*){bool result=advance;advance=false;return result;}
void Message_Update(PlayState*){}
void Play_PerformSave(PlayState*p){++saveWrites;order.push_back("save");gSaveContext.savedSceneNum=p->sceneNum;saved=gSaveContext;}
void Play_SaveSceneFlags(PlayState*){++flags;order.push_back("flags");}
void Sram_OpenSave(){++loads;order.push_back("reload");gSaveContext=saved;gSaveContext.entranceIndex=700;}
void GameInteractor_ExecuteOnExitGame(int){++exits;order.push_back("exit");}
void GameInteractor_ExecuteOnLoadGame(int){++loadHooks;order.push_back("load");}
int wreg[30]{},yreg[30]{},R_UPDATE_RATE=0,R_PAUSE_MENU_MODE=0;
#define WREG(i) wreg[i]
#define YREG(i) yreg[i]
int gSfxDefaultPos=0,gSfxDefaultFreqAndVolScale=0,gSfxDefaultReverb=0;
template<class...T>void Audio_PlaySfxGeneral(T...){}
void Interface_SetDoAction(PlayState*,int){}
void Interface_ChangeHudVisibilityMode(int){}
void func_800F64E0(int){}
void func_800981B8(int*){}
void func_800418D0(int*,PlayState*){}
void Audio_QueueSeqCmd(uint32_t){}
#define SET_NEXT_GAMESTATE(...) (++worldStarts)
'''+body+r'''
int assertions=0;
#define CK(x) do{++assertions;if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
void reset(int scene,int age,bool isRando,bool remembered,bool shuffled){
    testPlay={};testPlay.sceneNum=scene;gSaveContext={};gSaveContext.linkAge=age;
    saved={};rando=isRando;remember=remembered;shuffleSpawn=shuffled;advance=false;
    saveWrites=loads=flags=exits=loadHooks=overrides=worldStarts=0;order.clear();
}
void tick(){bool should=true;HandleSaveMenu(&should,&testPlay);}
void select(int choice){testPlay.msgCtx.choiceIndex=choice;advance=true;tick();}
bool intact(){return gSaveContext.ownedItems==67&&gSaveContext.checkedLocations==539&&
    gSaveContext.pendingApChecks==3&&gSaveContext.receivedApItems==712;}
int main(){
    const int scenes[]={'''+','.join(scene_ids)+r'''};
    for(int scene:scenes)for(int age=0;age<2;++age)for(bool isRando:{false,true})
    for(bool remembered:{false,true})for(bool shuffled:{false,true}){
        reset(scene,age,isRando,remembered,shuffled);
        tick();CK(testPlay.msgCtx.textId==TEXT_SAVE_MSG);CK(saveWrites==0&&loads==0);
        tick();CK(saveWrites==0);select(0);CK(saveWrites==1&&loads==0);
        CK(testPlay.pauseCtx.unk_1EC==4);
        const bool restartOffered=IsSceneDungeon(scene)||remembered;
        CK(testPlay.msgCtx.textId==(restartOffered?TEXT_CONTINUE_DUNGEON_MSG:TEXT_CONTINUE_OVERWORLD_MSG));
        select(restartOffered?2:1);CK(loads==1&&flags==1);CK(gSaveContext.ship.resetToSpawn==1);
        CK(testPlay.state.running);CK(exits==0&&loadHooks==0);
        for(int frame=0;frame<26;++frame)tick();
        const int native=age==1?ENTR_LINKS_HOUSE_CHILD_SPAWN:(isRando?ENTR_HYRULE_FIELD_10:ENTR_TEMPLE_OF_TIME_WARP_PAD);
        CK(gSaveContext.entranceIndex==native+(isRando&&shuffled?5000:0));
        CK(overrides==(isRando?1:0));CK(gSaveContext.linkAge==age);CK(intact());
        CK(gSaveContext.ship.resetToSpawn==0);CK(!testPlay.state.running);CK(worldStarts==1);
        CK(testPlay.gameplayFrames==0);CK(exits==1&&loadHooks==1);
        CK((order==std::vector<std::string>{"save","flags","reload","exit","load"}));
        tick();CK(exits==1&&loadHooks==1&&loads==1&&saveWrites==1);

        // Continue never reloads or warps. Declining a save does not offer a warp.
        reset(scene,age,isRando,remembered,shuffled);tick();select(0);select(0);
        CK(testPlay.pauseCtx.unk_1EC==5);CK(saveWrites==1&&loads==0&&exits==0&&overrides==0);
        CK(gSaveContext.entranceIndex==321&&intact());
        reset(scene,age,isRando,remembered,shuffled);gSaveContext.ship.resetToSpawn=1;
        tick();CK(gSaveContext.ship.resetToSpawn==0);select(1);
        CK(testPlay.pauseCtx.unk_1EC==2);CK(saveWrites==0&&loads==0&&worldStarts==0&&intact());

        if(restartOffered){
            reset(scene,age,isRando,remembered,shuffled);tick();select(0);select(1);
            CK(gSaveContext.ship.resetToSpawn==0);
            for(int frame=0;frame<26;++frame)tick();
            CK(gSaveContext.entranceIndex==700);CK(overrides==0);CK(loads==1&&worldStarts==1&&intact());
        }
    }
    std::cout<<assertions<<" save/spawn assertions passed across "<<std::size(scenes)
        <<" scene categories, both ages, normal/randomizer, remembered locations and spawn overrides\n";
}
'''
src=o/'save_spawn.cpp';src.write_text(code,encoding='utf-8');exe=o/'save_spawn.exe'
c=subprocess.run(['cl','/nologo','/std:c++20','/EHsc','/MD',str(src),'/Fo'+str(o/'save_spawn.obj'),'/Fe'+str(exe)],capture_output=True,text=True)
(o/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:
    print(c.stdout+c.stderr);raise SystemExit(c.returncode)
run=subprocess.run([str(exe)],capture_output=True,text=True)
report=dict(passed=run.returncode==0,baseline=bool(a.baseline),output=run.stdout+run.stderr,
            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),live_game_test=False)
(o/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(report['output']);raise SystemExit(run.returncode)
