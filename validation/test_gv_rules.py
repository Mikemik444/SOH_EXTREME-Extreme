"""Real AP 0.6.7 collection/reachability tests, no seed fill required.

Use the existing validation harness's restricted schema/bsdiff adapters only.
The assertions describe the user's requested two-route waterfall contract.
"""
from pathlib import Path
import sys, json, itertools, traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme import SOH_ITEM_ALIASES
from NetUtils import convert_to_base_types
import argparse
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);p.add_argument('--suite',choices=['minimal','full'],default='full');args=p.parse_args()
results=[]
def check(name, actual, expected, **extra):
    d={'name':name,'passed':actual==expected,'actual':actual,'expected':expected,**extra};results.append(d)
    if not d['passed']:print('FAIL',name,actual,expected,flush=True)

def state_for(mw, w, names, no_child=False):
    blocked={'Climb','Swim','Progressive Scale','Grab / Power Bracelet','Cucco Soul','Animal Soul',*SOH_ITEM_ALIASES['Strength Upgrade']}
    if no_child:blocked.add('Time Travel')
    state=CollectionState(mw)
    # Also remove targeted progression from precollected inventory. Never mutate
    # prog_items directly: use world.remove so rule caches/virtual tiers update.
    for it in mw.precollected_items[w.player]:
        if it.name in blocked:state.remove(it)
    items=list(mw.itempool)+[l.item for l in mw.get_filled_locations() if l.address is not None and l.item is not None]
    for it in items:
        if it.name not in blocked:state.collect(it,True)
    for n in names:state.collect(w.create_item(n),True)
    events=[l for l in mw.get_filled_locations() if l.address is None and l.item and l.item.name not in blocked]
    state.sweep_for_advancements(events)
    return state

try:
    variants=[('individual',{'shuffle_animal_soul':2}),]
    if args.suite=='full':
        variants += [('combined',{'shuffle_animal_soul':1}),('no-souls',{'shuffle_animal_soul':0}),
          ('grab-innate',{'shuffle_grab':False}),('climb-innate',{'shuffle_climb':False}),
          ('swim-innate',{'shuffle_swim':False}),('all-innate',{'shuffle_grab':False,'shuffle_climb':False,'shuffle_swim':False,'shuffle_animal_soul':0}),
          ('adult-only',{'starting_age':'adult'})]
    original_world=None;original_slot=None
    for i,(label,override) in enumerate(variants):
        opts={'shuffle_grab':True,'shuffle_climb':True,'shuffle_swim':True,'shuffle_animal_soul':2,**override}
        mw=setup(1401,overrides=opts);w=mw.worlds[1]
        check(label+' AP package version',w.world_version.as_simple_string(), '0.11.14')
        loc=w.get_location('GV Waterfall Freestanding PoH')
        check(label+' location ID stable',loc.address,121)
        mode=w.options.shuffle_animal_soul.value
        soul='Animal Soul' if mode==1 else 'Cucco Soul'
        for grab,cucco,climb,swim in itertools.product([False,True],repeat=4):
            # Use the actual first physical Strength/Scale tiers, not hand-added
            # virtual ability events. Other inventory deliberately includes
            # Boots, Longshot, bean souls, and health, testing forbidden bypasses.
            names=[]
            if grab:names.append(SOH_ITEM_ALIASES['Strength Upgrade'][0])
            if cucco:names.append(soul)
            if climb:names.append('Climb')
            if swim:names.append('Progressive Scale')
            state=state_for(mw,w,names,label=='adult-only')
            effective_grab=grab or not w.options.shuffle_grab.value
            effective_climb=climb or not w.options.shuffle_climb.value
            effective_swim=swim or not w.options.shuffle_swim.value
            effective_cucco=cucco or mode==0
            want=((label!='adult-only') and effective_cucco and effective_grab) or (effective_climb and effective_swim)
            actual=loc.can_reach(state)
            check(f'{label} grab={grab} cucco={cucco} climb={climb} swim={swim}',actual,want,
                inventory=names,upper_stream=loc.parent_region.can_reach(state),
                virtual_grab=state.has('Grab / Power Bracelet',1),virtual_swim=state.has('Swim',1))
        if label=='individual':
            wrong=state_for(mw,w,['Animal Soul',SOH_ITEM_ALIASES['Strength Upgrade'][0]])
            check('individual mode generic Animal Soul is not Cucco Soul',loc.can_reach(wrong),False)
            original_world=w; original_slot=convert_to_base_types(w.fill_slot_data())
            # Cache invalidation on removal of the first physical Scale.
            state=state_for(mw,w,['Climb','Progressive Scale'])
            check('scale plus climb before removal',loc.can_reach(state),True)
            state.remove(w.create_item('Progressive Scale'))
            check('remove scale invalidates waterfall reachability',loc.can_reach(state),False)
            state.collect(w.create_item('Progressive Scale'),True)
            check('restore scale restores waterfall reachability',loc.can_reach(state),True)
        check(label+' full-inventory waterfall',loc.can_reach(mw.get_all_state(False)),True)
    if args.suite=='full' and original_slot:
        mw=setup(1499,overrides={'shuffle_climb':False,'shuffle_grab':False,'shuffle_swim':False,'shuffle_animal_soul':0},passthrough=original_slot)
        w=mw.worlds[1];loc=w.get_location('GV Waterfall Freestanding PoH')
        check('UT uses slot options not conflicting local options',
            [w.options.shuffle_grab.value,w.options.shuffle_climb.value,w.options.shuffle_swim.value,w.options.shuffle_animal_soul.value],[1,1,1,2])
        for grab,cucco,climb,swim in itertools.product([False,True],repeat=4):
            names=([SOH_ITEM_ALIASES['Strength Upgrade'][0]] if grab else [])+(['Cucco Soul'] if cucco else [])+(['Climb'] if climb else [])+(['Progressive Scale'] if swim else [])
            state=state_for(mw,w,names)
            check(f'UT grab={grab} cucco={cucco} climb={climb} swim={swim}',loc.can_reach(state),(grab and cucco) or (climb and swim))
except Exception as e:
    traceback.print_exc();results.append({'name':'unhandled exception','passed':False,'error':repr(e),'traceback':traceback.format_exc()})
report={'checks':results,'total':len(results),'failures':sum(not x['passed'] for x in results),
 'scope':'Actual AP core/world graph, collection, virtual abilities and slot-data regeneration. No placement fill or game engine simulation. Restricted schema/bsdiff adapters only.'}
args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2))
print('TOTAL',report['total'],'FAILURES',report['failures'],flush=True)
raise SystemExit(bool(report['failures']))
