from __future__ import annotations
import json, dataclasses, traceback, sys, time, argparse
from pathlib import Path
from collections import Counter
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from worlds.soh_extreme.Options import FrozenStartingTime
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS

parser=argparse.ArgumentParser(parents=[BOOTSTRAP])
parser.add_argument('--report',type=Path,default=Path('regressions.json'))
parser.add_argument('--baseline-slot',type=Path,required=True)
args=parser.parse_args()
results=[]
def check(name,actual,expected=True):
    ok=actual==expected
    results.append(dict(name=name,passed=ok,actual=actual,expected=expected))
    print(('PASS' if ok else 'FAIL'),name,repr(actual)[:700],flush=True)

def snapshot(mw, exclude=(), only=None):
    state=CollectionState(mw)
    items=list(mw.itempool)+[l.item for l in mw.get_filled_locations() if l.address is not None and l.item]
    for item in items:
        if item.name not in exclude and (only is None or item.name in only): state.collect(item,True)
    state.sweep_for_advancements([l for l in mw.get_filled_locations() if l.address is None and l.item.name not in exclude])
    return state

def reach(state,world,address):
    loc=next(l for l in world.get_locations() if l.address==address)
    return loc.can_reach(state)

try:
    for name,expected in [('random',0),('randomized',0),('dawn',1),('day',2),('dusk',3),('night',4)]:
        check('clock parse '+name,FrozenStartingTime.from_any(name).value,expected)
    mw=setup(1001); w=mw.worlds[1]
    full=snapshot(mw)
    for aid in range(9800000,9800029): check(f'Deku all-inventory {aid}',reach(full,w,aid))
    state=snapshot(mw,exclude={'Climb','Progressive Hookshot'})
    check('2F unavailable without Climb or hookshot',w.get_region('Deku Tree Lobby 2F').can_reach(state),False)
    check('3F unavailable without Climb or hookshot',w.get_region('Deku Tree Lobby 3F').can_reach(state),False)
    check('1F Baba remains available',reach(state,w,9800003))
    check('3F Skulltula unavailable from floor one',reach(state,w,9800000),False)
    check('first scrub not at entrance',reach(state,w,9800006),False)
    state=snapshot(mw,exclude={'Buy Deku Shield','Buy Hylian Shield','Deku Shield','Hylian Shield'})
    check('slingshot cannot surrender hint scrub',reach(state,w,9800006),False)
    check('last puzzle scrub requires reflection',reach(state,w,9800025),False)
    state=snapshot(mw,exclude={'Deku Scrub Soul'})
    check('hint scrub requires own soul',reach(state,w,9800006),False)
    state=snapshot(mw,exclude={'Skulltula Soul'})
    check('normal spider requires dedicated soul',reach(state,w,9800000),False)
    state=snapshot(mw,exclude={'Climb'})
    check('adult weapon cannot bypass a child-only dungeon entrance at 2F',w.get_region('Deku Tree Lobby 2F').can_reach(state),False)
    check('adult weapon cannot bypass a child-only dungeon entrance at 3F',w.get_region('Deku Tree Lobby 3F').can_reach(state),False)
    slot=json.loads(args.baseline_slot.read_text())
    ut=setup(9001,overrides={'shuffle_enemy_drops':False,'shuffle_climb':False,'frozen_starting_time':'night'},passthrough=slot)
    uw=ut.worlds[1]
    check('UT overwrites conflicting local clock',uw.options.frozen_starting_time.value,2)
    check('UT overwrites conflicting local enemy option',uw.options.shuffle_enemy_drops.value,1)
    check('UT overwrites conflicting local climb option',uw.options.shuffle_climb.value,1)
    orig_ids=sorted(l.address for l in w.get_locations() if l.address is not None)
    ut_ids=sorted(l.address for l in uw.get_locations() if l.address is not None)
    check('UT full location set',ut_ids==orig_ids)
    check('Malon speech is in child castle grounds',w.get_location('NPC Speech: Hc Malon Egg').parent_region.name,'Hyrule Castle Grounds')
    for aid in range(9600664,9600672):
        original=next(l for l in w.get_locations() if l.address==aid)
        restored=next(l for l in uw.get_locations() if l.address==aid)
        check(f'UT restored potion-shop speech parent {aid}',restored.parent_region.name,original.parent_region.name)
        check(f'Potion-shop speech is not a Menu check {aid}',restored.parent_region.name!='Menu')

    check('UT exact price table',{str(k):v for k,v in uw.shop_prices.items()}==slot['shop_prices'])
    check('UT required trial selection',set(uw.ganons_trials)==set(slot['required_trials']))
    # Identical inventory, not a rerolled fake seed's randomly chosen pocket item.
    # Only event locations are swept so no fake item placement affects these queries.
    inventories=[[], ['Kokiri Sword','Deku Baba Soul'],['Kokiri Sword','Deku Baba Soul','Climb'],
        ['Kokiri Sword','Deku Baba Soul','Climb','Skulltula Soul'],
        ['Kokiri Sword','Deku Baba Soul','Climb','Skulltula Soul','Deku Scrub Soul','Buy Deku Shield']]
    for i,names in enumerate(inventories):
        def from_names(world,names):
            s=CollectionState(world.multiworld)
            for n in names:s.collect(world.create_item(n),True)
            s.sweep_for_advancements([l for l in world.multiworld.get_filled_locations(world.player) if l.address is None])
            return s
        a,b=from_names(w,names),from_names(uw,names)
        sa={l.address for l in w.get_locations() if l.address is not None and l.can_reach(a)}
        sb={l.address for l in uw.get_locations() if l.address is not None and l.can_reach(b)}
        check(f'UT reachability parity inventory {i}',sorted(sa ^ sb),[])
    for sentinel in ('random','night'):
        m=setup(3001,overrides={'frozen_starting_time':sentinel},stop_before='create_regions')
        check(f'generated {sentinel} clock resolved',m.worlds[1].options.frozen_starting_time.value in (1,2,3,4))
    legacy=dict(slot);legacy['extreme_all_options']=dict(slot['extreme_all_options']);legacy['extreme_all_options']['frozen_starting_time']=0;legacy['frozen_starting_time']=0
    m=setup(9999,passthrough=legacy,stop_before='create_regions')
    check('legacy zero clock matches native Dawn',m.worlds[1].options.frozen_starting_time.value,1)
except Exception as e:
    traceback.print_exc();results.append({'name':'unhandled regression error','passed':False,'error':repr(e),'traceback':traceback.format_exc()})
args.report.parent.mkdir(parents=True,exist_ok=True)
args.report.write_text(json.dumps(results,indent=2))
print('TOTAL',len(results),'FAILURES',sum(not x['passed'] for x in results),flush=True)
raise SystemExit(any(not x['passed'] for x in results))
