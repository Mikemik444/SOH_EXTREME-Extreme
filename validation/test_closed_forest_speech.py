"""Sparse-inventory regression for NPC rules incorrectly treating age as access.

The route oracle queries the actual age-specific region graph independently of
the conversation's rule. AP/UT agreement alone did not expose the original bug.
"""
import argparse, json
from pathlib import Path
from run_case import BOOTSTRAP, setup
from ut_harness import tracker
from BaseClasses import CollectionState
from worlds.soh_extreme import NpcSpeech
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions, Ages

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--slot-data',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args()
slot=json.loads(a.slot_data.read_text(encoding='utf-8'))
m=setup(290946,passthrough=slot,stop_before='pre_fill');w=m.worlds[1]
evaluate=tracker(w,a.ut_core);tests=[]
def ck(name,value,expected=True):
    tests.append(dict(test=name,actual=value,expected=expected,passed=value==expected))
def in_region(state,token,age):
    previous=state._soh_age[1]
    try:
        state._soh_age[1]=age
        return w.get_region(str(Regions[token])).can_reach(state)
    finally: state._soh_age[1]=previous
def has_route(state,entry):
    return any(in_region(state,route['region'],age)
        for route in entry['routes']
        for age in ((Ages.CHILD,Ages.ADULT) if route['age']=='either' else
                    (Ages.CHILD,) if route['age']=='child' else (Ages.ADULT,)))

languages=['Speak '+s for s in NpcSpeech.LANGUAGES]
scenarios={
    'empty':[],
    'bombchu bag':['Bombchu Bag'],
    'bombchus and Goron speech':['Bombchu Bag','Speak Goron','NPC Soul'],
    'all languages, no exit abilities':['Bombchu Bag','NPC Soul',*languages],
    'climb, no rock soul':['Climb','Bombchu Bag','NPC Soul',*languages],
    'soul, no explosives':['Climb','Rock / Boulder Soul','NPC Soul',*languages],
    'shortcut requirements':['Climb','Rock / Boulder Soul','Bombchu Bag','NPC Soul',*languages],
    'complete inventory':[i.name for i in m.itempool],
}
for label,names in scenarios.items():
    result=evaluate(names)
    s=CollectionState(m)
    for name in names:s.collect(w.create_item(name),True)
    s.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
    for name,entry in w._npc_conversations.items():
        location=w.get_location(name);direct=location.can_reach(s)
        ut=name in result.in_logic_locations
        ck(f'{label}: AP/UT {name}',direct,ut)
        if entry['routes']:
            # A location under Menu cannot inherit a physical route from its parent.
            ck(f'{label}: physical route {name}',not direct or has_route(s,entry))
        if label=='complete inventory':ck(f'{label}: reachable {name}',direct)
    if label in ('empty','bombchu bag','bombchus and Goron speech','all languages, no exit abilities','climb, no rock soul','soul, no explosives'):
        ck(f'{label}: Closed Forest blocks Hyrule Field',in_region(s,'HYRULE_FIELD',Ages.CHILD),False)
        ck(f'{label}: shortcut does not bypass missing prerequisite',in_region(s,'GORON_CITY',Ages.CHILD),False)
    if label=='shortcut requirements':
        ck('Climb + usable Bombchus + Rock Soul opens shortcut',in_region(s,'GORON_CITY',Ages.CHILD))
    if label=='bombchus and Goron speech':
        for name in ('NPC Speech: DMT Cavern Entrance Goron','NPC Speech: Market Bazaar Goron',
                     'NPC Speech: Fire Temple Near Boss Room Goron'):
            ck('reported seed: inaccessible '+name,w.get_location(name).can_reach(s),False)
        ck('reported seed: adult region unavailable',in_region(s,'FIRE_TEMPLE_NEAR_BOSS_ROOM',Ages.ADULT),False)

# Check the opposite direction too: adult start must not supply child access.
# Closed Forest forces child start, so use its open variant for this scenario.
m=setup(290949,overrides={'starting_age':'adult','closed_forest':'off'},stop_before='pre_fill')
w=m.worlds[1];evaluate=tracker(w,a.ut_core)
adult_inventory=['NPC Soul',*languages]
result=evaluate(adult_inventory)
s=CollectionState(m)
for name in adult_inventory:s.collect(w.create_item(name),True)
s.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
ck('adult start reaches adult Temple of Time',in_region(s,'TEMPLE_OF_TIME',Ages.ADULT))
ck('adult start cannot reach child Temple of Time',in_region(s,'TEMPLE_OF_TIME',Ages.CHILD),False)
ck('adult start has no Time Travel yet',s.has('Time Travel',1),False)
for name,entry in w._npc_conversations.items():
    if not entry['routes']:continue
    direct=w.get_location(name).can_reach(s)
    ck('adult start AP/UT '+name,direct,name in result.in_logic_locations)
    ck('adult start physical route '+name,not direct or has_route(s,entry))
    if all(route['age']=='child' for route in entry['routes']):
        ck('adult start cannot use child conversation '+name,direct,False)

passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,tests=len(tests),scenarios=len(scenarios)+1,
    failures=[t for t in tests if not t['passed']],checks=tests),indent=2),encoding='utf-8')
print('PASS' if passed else 'FAIL',len(tests),'assertions')
for t in tests:
    if not t['passed']:print(t)
raise SystemExit(0 if passed else 1)
