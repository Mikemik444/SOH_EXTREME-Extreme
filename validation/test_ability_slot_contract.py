"""Validate all shuffled capability settings at the generator/native boundary."""
from run_case import setup, BOOTSTRAP
from worlds.soh_extreme.NativeSettings import NATIVE_AP_DEFAULTS
from pathlib import Path
import argparse, json, re, dataclasses
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
mapping={
 'ShuffleRoll':'shuffle_roll','ShuffleGrab':'shuffle_grab','ShuffleClimb':'shuffle_climb',
 'ShuffleCrawl':'shuffle_crawl','ShuffleSwim':'shuffle_swim','ShuffleSpeak':'shuffle_speak',
 'ShuffleOpenChest':'shuffle_open_chest','ShuffleShovel':'shuffle_shovel',
 'ShuffleFlowOfTime':'shuffle_flow_of_time','ShuffleEnemySoul':'shuffle_enemy_soul',
 'ShuffleAnimalSoul':'shuffle_animal_soul','ShuffleNpcSoul':'shuffle_npc_soul',
 'ShufflePotSoul':'shuffle_pot_soul','ShuffleCrateSoul':'shuffle_crate_soul',
 'ShuffleGrassSoul':'shuffle_grass_bush_soul','ShuffleRockSoul':'shuffle_rock_boulder_soul',
 'ShuffleTreeSoul':'shuffle_tree_soul','ShuffleBeehiveSoul':'shuffle_beehive_soul',
 'ShuffleSignSoul':'shuffle_sign_soul','ShuffleSkulltulaSoul':'shuffle_skulltula_soul',
 'ShuffleBusinessScrubSoul':'shuffle_business_scrub_soul','ShuffleBeanSouls':'shuffle_bean_souls',
 'ShuffleFishingPole':'shuffle_fishing_pole','ShuffleDekuStickBag':'shuffle_deku_stick_bag',
 'ShuffleDekuNutBag':'shuffle_deku_nut_bag','ShuffleOcarinas':'shuffle_ocarinas',
 'ShuffleOcarinaButtons':'shuffle_ocarina_buttons','SongNoteShuffle':'song_note_shuffle',
 'ShuffleSilver':'shuffle_silver',
}
tests=[]
def ck(name,actual,expected):
 tests.append(dict(test=name,passed=actual==expected,actual=actual,expected=expected))
native=set(re.findall(r'CVAR_RANDOMIZER_SETTING\("([^"]+)"\)',(root/'soh/Enhancements/randomizer/settings.cpp').read_text(encoding='utf-8')))
version=re.search(r'kTrackerVersion = "([^"]+)"',(root/'soh/Network/Archipelago/TrackerMirror.h').read_text())[1]
fallback=dict((k,int(v)) for k,v in re.findall(r'\{ "([^"]+)", (\d+) \}',(root/'soh/Network/Archipelago/ArchipelagoNativeDefaults.inc').read_text()))
ck('Python and C++ fallback defaults agree',fallback,NATIVE_AP_DEFAULTS)
ck('Default keys are actual native settings',sorted(set(NATIVE_AP_DEFAULTS)-native),[])
for label,overrides in [('user YAML',{}),('abilities disabled',{n:0 for n in mapping.values()})]:
 m=setup(290942,overrides=overrides);w=m.worlds[1];s=w.fill_slot_data();cv=s['extreme_soh_cvars']
 ck(label+' release match',w.apworld_version,version)
 ck(label+' all resolved options published',sorted(s['extreme_all_options']),sorted(f.name for f in dataclasses.fields(w.options)))
 for key,opt in mapping.items():
  ck(label+' '+key,cv[key],getattr(w.options,opt).value)
 ck(label+' frozen starting time',cv['FrozenStartingTime'],w.options.frozen_starting_time.value)
 ck(label+' native boss-soul toggle',cv['ShuffleBossSouls'],int(bool(w.options.shuffle_boss_souls.value)))
 ck(label+' resolved hunt target',cv['WinconTriforceCount'],s['triforce_hunt_pieces_required'] if w.options.triforce_hunt.value else 0)
 ck(label+' wallet-fill setting',cv['FullWallets'],w.options.full_wallets.value)
 ck(label+' first shield purchase allowed',cv['ShopShieldsTunicsGate'],0)
 ck(label+' all native starting inventory explicit',sorted({k for k in native if k.startswith('Starting')}-set(cv)),[])
 ck(label+' all native MQ settings explicit',sorted({k for k in native if k.startswith('MQDungeon')}-set(cv)),[])
 ck(label+' exact active location IDs',sorted(s['extreme_active_locations']),sorted(l.address for l in w.get_locations() if type(l.address) is int))
 # Avoid repeating thousands of equal location IDs in the report.
 tests[-1].update(actual=len(tests[-1]['actual']),expected=len(tests[-1]['expected']))
report=dict(passed=all(t['passed'] for t in tests),tests=tests,total=len(tests),scope=__doc__)
a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PASS' if report['passed'] else 'FAIL',len(tests),flush=True)
raise SystemExit(not report['passed'])
