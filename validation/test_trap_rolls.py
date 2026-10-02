"""Exercise production Additional Traps delivery using the real ShipUtils RNG.

Engine effects/hooks are recorded by adapters; this is not a live game test.
Use --baseline with an older ExtraTraps.cpp to reproduce the same-area bug.
"""
from pathlib import Path
from run_native_tests import function
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--baseline', type=Path)
a = p.parse_args()
r = Path(__file__).resolve().parent.parent
o = a.output.resolve()
o.mkdir(parents=True, exist_ok=True)
trap_path = a.baseline or r / 'soh/Enhancements/ExtraTraps.cpp'
traps = trap_path.read_text(encoding='utf-8-sig')
harness = (r / 'validation/support/EngineHarness.h').read_text(encoding='utf-8-sig')
rng = (r / 'soh/ShipUtils.cpp').read_text(encoding='utf-8-sig')
header = (r / 'soh/ShipUtils.h').read_text(encoding='utf-8-sig')
real_rng = '''
#include <bit>
#include <random>
namespace ShipUtils {
void RandInit(uint64_t seed, uint64_t* state = nullptr);
uint32_t next32(uint64_t* state = nullptr);
uint32_t Random(uint32_t min, uint32_t max, uint64_t* state = nullptr);
'''
real_rng += function(header, 'template <typename Container> auto& RandomElement(') + '\n'
real_rng += function(header, 'template <typename Container> const auto& RandomElement(') + '\n}\n'
real_rng += rng[rng.index('static bool default_init'):rng.index('// Returns a random floating point')]
harness = harness.replace(function(harness, 'namespace ShipUtils {'), real_rng)
(o / 'TrapHarness.h').write_text(harness, encoding='utf-8')
body = re.sub(r'^\s*#include[^\n]*', '', traps, flags=re.MULTILINE)
tests = r'''
int assertions=0;
#define CK(x) do { ++assertions; if(!(x)) { std::cerr << "FAIL line " << __LINE__ << ": " << #x << "\n"; return 1; } } while(0)
void localProfile(int mask, bool enabled=true) {
    cvars.clear(); CVarSetInteger(CVAR_EXTRA_TRAPS_NAME,enabled);
    for(int i=0;i<ADD_TRAP_MAX;++i) CVarSetInteger(altTrapTypeCvars[i],!!(mask&(1<<i)));
}
void apProfile(int pool, int mask) {
    auto c=Rando::Context::GetInstance();
    c->GetOption(RSK_EXTREME_TRAP_POOL).Set(pool);
    const RandomizerSettingKey keys[]={RSK_EXTREME_ICE_TRAPS,RSK_EXTREME_FIRE_TRAPS,
        RSK_EXTREME_SLOW_TRAPS,RSK_EXTREME_MAGIC_SUCK_TRAPS,RSK_EXTREME_HEALTH_DRAIN_TRAPS};
    for(int i=0;i<5;++i)c->GetOption(keys[i]).Set(!!(mask&(1<<i)));
}
void ready() {
    ResetExtraTrapEffects(); actions.clear();
    gSaveContext.ship.pendingIceTrapCount=1;
}
int main() {
    ShipInit::InitAll();
    default_init=true; ShipUtils::RandInit(0x12345678ULL);
    // A real sequence at one scene and unchanged pickup model used to be constant.
    localProfile((1<<ADD_ICE_TRAP)|(1<<ADD_BURN_TRAP)|(1<<ADD_SHOCK_TRAP)|
                 (1<<ADD_KNOCK_TRAP)|(1<<ADD_SPEED_TRAP)|(1<<ADD_BOMB_TRAP));
    testPlay.sceneNum=81; testPlayer.getItemEntry.drawItemId=0;
    isApSave=false;
    auto choices=getEnabledAddTraps();
    std::set<int> seen;
    for(int i=0;i<256;++i) {ready(); CK(DeliverTrap());seen.insert(roll);}
    CK(seen.size()==choices.size());
    std::cout << "PASS: same scene/model produces all six enabled effects\n";

    // Every pair, with normal/local, randomizer/local, and AP normal-pool/UI settings.
    for(int mode=0;mode<3;++mode) {
        gSaveContext.ship.quest.id=mode==0?0:QUEST_RANDOMIZER;isApSave=mode==2;
        apProfile(0,31);
        for(int first=0;first<ADD_TRAP_MAX;++first)for(int second=first+1;second<ADD_TRAP_MAX;++second) {
            localProfile((1<<first)|(1<<second)); auto prefs=cvars;seen.clear();
            for(int i=0;i<128;++i) {
                ready(); const auto state=default_state;
                CK(DeliverTrap());CK(roll==first||roll==second);CK(default_state!=state);
                CK(gSaveContext.ship.pendingIceTrapCount==0); CK(actions["receipt"]==1);
                seen.insert(roll);
            }
            CK(seen.size()==2);CK(cvars==prefs);
        }
    }
    std::cout << "PASS: all 66 effect pairs across three save/settings modes\n";

    // Single effects are never silently expanded. Their actions still execute.
    isApSave=false;localProfile(1);
    for(int type=0;type<ADD_TRAP_MAX;++type) {
        localProfile(1<<type); ready();ammo.fill(10);CK(DeliverTrap());CK(roll==type);
        for(int tick=0;tick<4;++tick)OnPlayerUpdate();
        const char* names[]={"freeze","burn","shock","knock",nullptr,"bomb","void","notification","kill","teleport","magic","health"};
        if(names[type])CK(actions[names[type]]>=1);
        if(type==ADD_SPEED_TRAP)CK(GameInteractor::State::MovementSpeedMultiplier==0.5f);
        if(type==ADD_AMMO_TRAP)CK(ammo[ITEM_BOMBCHU]==5);
    }
    localProfile(0);ready();CK(DeliverTrap());CK(roll==ADD_ICE_TRAP);
    localProfile((1<<ADD_TRAP_MAX)-1,false);ready();auto state=default_state;
    CK(DeliverTrap());CK(actions["freeze"]==1);CK(default_state==state);
    std::cout << "PASS: all actions, disabled/empty UI profile and single-effect choices\n";

    // Only allowed destinations, and a fresh destination for later teleport traps.
    for(int advanced=0;advanced<2;++advanced) {
        localProfile(1<<ADD_TELEPORT_TRAP);
        CVarSetInteger(altTrapTypeCvars[ADD_TELEPORT_TRAP],advanced?TELEPORT_TRAP_ADVANCED:1);
        std::set<int> destinations;
        const auto& allowed=advanced?advancedTeleportDestinations:simpleTeleportDestinations;
        for(int i=0;i<256;++i) {
            ready();CK(DeliverTrap());CK(roll==ADD_TELEPORT_TRAP);
            CK(std::find(allowed.begin(),allowed.end(),teleportRoll)!=allowed.end());
            destinations.insert(teleportRoll);
            for(int tick=0;tick<4;++tick)OnPlayerUpdate();
            CK(lastTeleport==teleportRoll);CK(actions["teleport"]==1);
        }
        CK(destinations.size()>1);
    }
    localProfile((1<<ADD_VOID_TRAP)|(1<<ADD_TELEPORT_TRAP));
    gSaveContext.equips.buttonItems[0]=ITEM_FISHING_POLE;ready();
    CK(DeliverTrap());CK(roll==ADD_ICE_TRAP);gSaveContext.equips.buttonItems[0]=0;
    std::cout << "PASS: teleport destination variation and fishing-pole exclusions\n";

    // AP overrides retain their existing meaning; this update does not change them.
    isApSave=true;gSaveContext.ship.quest.id=QUEST_RANDOMIZER;
    localProfile((1<<ADD_TRAP_MAX)-1);apProfile(1,31);
    for(int i=0;i<32;++i){ready();CK(DeliverTrap());CK(roll==ADD_ICE_TRAP);}
    const AltTrapType apTypes[]={ADD_ICE_TRAP,ADD_BURN_TRAP,ADD_SPEED_TRAP,ADD_MAGIC_TRAP,ADD_HEALTH_TRAP};
    for(int mask=0;mask<32;++mask) {
        apProfile(2,mask);std::set<int> allowed,results;
        for(int i=0;i<5;++i)if(mask&(1<<i))allowed.insert(apTypes[i]);
        if(allowed.empty())allowed.insert(ADD_ICE_TRAP);
        for(int i=0;i<256;++i){ready();CK(DeliverTrap());CK(allowed.count(roll));results.insert(roll);}
        CK(results==allowed);
    }
    std::cout << "PASS: Ice Only and all 32 Expanded seed profiles preserved\n";

    // No reroll/reseed while idle, resetting effects, or loading another area/save.
    ready();gSaveContext.ship.pendingIceTrapCount=0;state=default_state;
    CK(!DeliverTrap());CK(default_state==state);
    ResetExtraTrapEffects();testPlay.sceneNum=1;
    GameInteractor::Dispatch<GameInteractor::OnLoadGame>(0);
    CK(default_state==state);
    GameInteractor::Dispatch<GameInteractor::OnExitGame>(0);CK(default_state==state);
    isApSave=true;localProfile(1<<ADD_BURN_TRAP);
    auto saved=Rando::Context::instance;Rando::Context::instance=nullptr;
    ready();CK(DeliverTrap());CK(roll==ADD_BURN_TRAP);Rando::Context::instance=saved;
    std::cout << "PASS: idle/load/exit and missing-context local fallback\n";
    std::cout << assertions << " trap assertions passed\n";
}
'''
source = o / 'trap_rolls.cpp'
source.write_text('#include "TrapHarness.h"\n' + body + '\n' + tests, encoding='utf-8')
exe = o / 'trap_rolls.exe'
command = ['cl', '/nologo', '/std:c++20', '/Zc:preprocessor', '/EHsc', '/MD',
           '/I' + str(r / 'validation/support'), str(source),
           '/Fo' + str(o / 'trap_rolls.obj'), '/Fe' + str(exe)]
c = subprocess.run(command, capture_output=True, text=True)
(o / 'compile.log').write_text(c.stdout + c.stderr, encoding='utf-8')
if c.returncode:
    print(c.stdout + c.stderr)
    raise SystemExit(c.returncode)
run = subprocess.run([str(exe)], capture_output=True, text=True)
report = dict(passed=run.returncode == 0, baseline=bool(a.baseline),
              output=run.stdout + run.stderr,
              trap_source_sha256=hashlib.sha256(trap_path.read_bytes()).hexdigest(),
              real_rng=True, live_game_test=False)
(o / 'results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(report['output'])
raise SystemExit(run.returncode)
