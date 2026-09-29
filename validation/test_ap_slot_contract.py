"""Check resolved user options against native settings and the old-seed fallback."""
from run_case import setup, BOOTSTRAP
from worlds.soh_extreme.NativeSettings import NATIVE_AP_DEFAULTS
from pathlib import Path
import argparse, json, re, dataclasses
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
r=Path(__file__).resolve().parent.parent
m=setup(290929);w=m.worlds[1];slot=w.fill_slot_data();cv=slot['extreme_soh_cvars'];results=[]
def ck(name, actual, expected):
 results.append({'name':name,'passed':actual==expected});assert actual==expected,(name,actual,expected)
native=set(re.findall(r'CVAR_RANDOMIZER_SETTING\("([^"]+)"\)',(r/'soh/Enhancements/randomizer/settings.cpp').read_text(encoding='utf-8')))
ck('Installed world and native tracker release match',w.apworld_version,'0.11.24')
fallback=dict((key,int(value)) for key,value in re.findall(r'\{ "([^"]+)", (\d+) \}',(r/'soh/Network/Archipelago/ArchipelagoNativeDefaults.inc').read_text()))
ck('Python/new-seed and C++/old-seed defaults match',fallback,NATIVE_AP_DEFAULTS)
ck('Default names all match real native CVars',set(NATIVE_AP_DEFAULTS)-native,set())
ck('All resolved AP options are published',set(slot['extreme_all_options']),{f.name for f in dataclasses.fields(w.options)})
ck('User hunt target',cv['WinconTriforceCount'],24)
ck('User wallet fill enabled',cv['FullWallets'],1)
ck('First shield purchase allowed',cv['ShopShieldsTunicsGate'],0)
ck('No implicit starting shield',cv['StartingDekuShield'],0)
ck('No implicit wallet upgrades',cv['StartingWallet'],0)
ck('No implicit bottles',[cv['StartingBottle'+str(i)] for i in range(1,5)],[0]*4)
ck('User enemy drop checks enabled',cv['ShuffleEnemyDrops'],1)
ck('User enemy souls disabled',cv['ShuffleEnemySoul'],0)
ck('User fish identity settings',[cv['Fishsanity'],cv['FishsanityPondCount'],cv['FishsanityAgeSplit']],[4,17,1])
ck('User clear scrub/merchant hints',[cv['ScrubText'],cv['MerchantText'],cv['HintClarity']],[1,1,2])
ck('User price ranges',[cv[k] for k in ['ShopsanityPriceRange1','ShopsanityPriceRange2','ScrubsPriceRange1','ScrubsPriceRange2']],[0,0,10,90])
ck('All native starting inventory has an authoritative value',{k for k in native if k.startswith('Starting')}-set(cv),set())
ck('All native MQ settings have an authoritative value',{k for k in native if k.startswith('MQDungeon')}-set(cv),set())
ck('Native unsupported entrance shuffles disabled',all(cv[k]==0 for k in native if k.startswith('Shuffle') and ('Entrance' in k or k in ('ShuffleOwlDrops','ShuffleWarpSongs','ShuffleOverworldSpawns'))),True)
ck('All published active checks exist',set(slot['extreme_active_locations']),{l.address for l in w.get_locations() if isinstance(l.address,int)})
# A second configuration catches state leaks when switching away from skips.
m2=setup(290930,overrides={'skip_child_zelda':False,'complete_mask_quest':False,'start_with_deku_shield':True,'triforce_hunt':False,'shuffle_enemy_drops':False,'shuffle_fish':'off'})
other=m2.worlds[1].fill_slot_data()['extreme_soh_cvars']
ck('Starting shield remains explicit',other['StartingDekuShield'],1)
ck('Zelda skip clears when off',other['StartingZeldasLetter'],0)
ck('Masks do not persist into next seed',[other['ShuffleMasks'],other['StartingMaskOfTruth']],[0,0])
ck('Disabled goal/drop/fish settings clear',[other['ShuffleWincon'],other['ShuffleEnemyDrops'],other['Fishsanity'],other['FishsanityPondCount']],[0,0,0,0])
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'passed':all(x['passed'] for x in results),'tests':results,'resolved_option_count':len(slot['extreme_all_options']),'native_default_count':len(NATIVE_AP_DEFAULTS),'active_checks':len(slot['extreme_active_locations'])},indent=2));print('PASS',len(results),'slot contract checks')
