"""Dungeon Start With keys must not bypass separate Fortress/minigame shuffles."""
from run_case import setup,BOOTSTRAP
from worlds.soh_extreme._vendor_oot_soh.KeyShuffle import small_key_option_matching
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import key_to_ring
from collections import Counter
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
for option in ('start_with','anywhere','own_dungeon'):
 m=setup(291041,overrides={'small_key_shuffle':option,'shuffle_chest_minigame':True,'skeleton_key':False,'fortress_carpenters':'normal','gerudo_fortress_key_shuffle':'anywhere'},stop_before='pre_fill')
 w=m.worlds[1];held=Counter(i.name for i in m.precollected_items[1]);pool=Counter(i.name for i in m.itempool)
 for key in small_key_option_matching(w):
  ring=key_to_ring[key];tests.append(dict(test=f'{option}/{ring}',passed=held[ring]==int(option=='start_with')))
 for ring in ('Treasure Game Key Ring','Gerudo Fortress Key Ring'):
  tests.append(dict(test=f'{option}/no unintended {ring}',passed=held[ring]==0))
 tests.append(dict(test=f'{option}/six minigame keys remain shuffled',passed=pool['Treasure Game Small Key']==6))
result=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),tests=tests)
a.report.write_text(json.dumps(result,indent=2));print('PASS' if result['passed'] else 'FAIL',len(tests))
raise SystemExit(not result['passed'])
