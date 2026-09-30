"""Real AP and UT regression for grotto routes, gated combat and age separation."""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS, ENEMY_GROTTO_RETIRED_IDS
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages,Regions
from ut_harness import tracker
from pathlib import Path
import argparse,json

p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args()
m=setup(290953,stop_before='pre_fill');w=m.worlds[1];evaluate=tracker(w,a.ut_core)
tests=[]
def ck(name,value,expected=True):
    tests.append(dict(test=name,actual=value,expected=expected,passed=value==expected))
    if value!=expected:print('FAIL',tests[-1])
physical=[*m.itempool,*[l.item for l in w.get_locations() if l.address is not None and l.item]]
inventory=[i.name for i in physical if i.name in w.item_name_to_id]
grotto=[e for e in ENEMY_DROP_LOCATIONS if e.scene_id==62]
wolfos=[e for e in ENEMY_DROP_LOCATIONS if e.address in (9800505,9800506,9800536)]
by_id={l.address:l for l in w.get_locations() if l.address}
ck('retired phantom IDs not generated',not ENEMY_GROTTO_RETIRED_IDS.intersection(by_id))
for e in grotto:
    ck('parent is actual physical region '+str(e.address),by_id[e.address].parent_region.name,str(Regions[e.region_token]))
weapons={n for n in inventory if any(token in n.lower() for token in ('sword','knife','hammer','stick'))}
scenarios={
    'complete':set(), 'no shovel':{'Shovel'},'no Wolfos soul':{'Wolfos Soul'},
    'no weapons':weapons,
    'speech only':set(inventory)-{'NPC Soul','Speak Kokiri','Speak Hylian','Speak Goron'},
    'no grotto opener':{n for n in inventory if 'Bomb' in n}|{'Megaton Hammer'},
}
for label,removed in scenarios.items():
    names=[name for name in inventory if name not in removed]
    state=CollectionState(m)
    for item in m.precollected_items[1]:
        if item.name in removed:state.remove(item)
    for name in names:state.collect(w.create_item(name),True)
    state.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
    result=evaluate(names)
    for entry in [*grotto,wolfos[-1]]:
        location=by_id[entry.address];direct=location.can_reach(state)
        ck(label+' AP/UT '+entry.name,direct,entry.name in result.in_logic_locations)
        if label=='complete':ck('full access '+entry.name,direct)
        if label=='no shovel' and entry.grotto_id>=0:ck('shovel gates '+entry.name,direct,False)
        if entry in wolfos and label in ('no Wolfos soul','no weapons','speech only'):
            ck(label+' blocks '+entry.name,direct,False)
        if entry.grotto_id==22 and label=='no grotto opener':ck('explosives gate '+entry.name,direct,False)
    if label=='complete':
        # Location evaluation supplies the age to rules; inspect both branches
        # explicitly to catch child-only actors borrowing an adult inventory.
        for age in (Ages.CHILD,Ages.ADULT):
            previous=state._soh_age[1];state._soh_age[1]=age
            try:
                ck('entry Wolfos age '+str(age),by_id[9800536].access_rule(state),age==Ages.CHILD)
                for address in (9800505,9800506):ck('grotto Wolfos age '+str(age)+' '+str(address),by_id[address].access_rule(state))
            finally:state._soh_age[1]=previous

report=dict(passed=all(t['passed'] for t in tests),tests=len(tests),checks=tests,scope=__doc__)
a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ASSERTIONS',len(tests),'FAILURES',sum(not t['passed'] for t in tests));raise SystemExit(0 if report['passed'] else 1)
