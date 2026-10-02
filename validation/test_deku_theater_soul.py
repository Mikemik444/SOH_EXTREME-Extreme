"""Deku Theater reward leader existence, including restored old seed options.

Skull Mask uses the leader's automatic walk-up textbox. Mask of Truth uses
OfferTalk and requires Deku speech. Both require NPC Soul when shuffled.
"""
from run_case import setup,BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
options=dict(closed_forest='off',complete_mask_quest=True,shuffle_npc_soul=True,
             shuffle_speak='individual_languages',starting_age='child',
             shuffle_shovel=True,start_inventory={},start_inventory_from_pool={})
def ck(name,actual,expected):tests.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))
def verify(w,label,npc_shuffle,speak_mode):
    ev=tracker(w,a.ut_core)
    all_items=[it.name for it in w.multiworld.itempool]
    # Keep path access intact; only remove the Deku language and leader soul.
    base=[it for it in all_items if it not in ('NPC Soul','Speak Deku','Speak','Skull Mask','Mask of Truth')]
    for npc in (False,True):
        for speech in (False,True):
            for mask in ('Skull Mask','Mask of Truth'):
                inv=base+(['NPC Soul'] if npc else [])+(['Speak' if speak_mode=='on' else 'Speak Deku'] if speech else [])
                # Shared Speak is also needed for some unrelated routes. The
                # child theater route itself has no conversation gate.
                r=ev(inv)
                name='LW Deku Theater '+mask
                expected=(npc or not npc_shuffle) and (mask=='Skull Mask' or speech or speak_mode=='off')
                prefix=f'{label}/{npc}/{speech}/{mask}'
                ck(prefix+' region',w.get_location(name).parent_region.can_reach(r.state),True)
                ck(prefix+' AP',w.get_location(name).can_reach(r.state),expected)
                ck(prefix+' UT',name in r.in_logic_locations,expected)
    r=ev([it for it in base if it!='Shovel']+['NPC Soul','Speak','Speak Deku'])
    for mask in ('Skull Mask','Mask of Truth'):
        ck(label+' missing Shovel '+mask,'LW Deku Theater '+mask in r.in_logic_locations,False)
for mode,soul in (('individual_languages',True),('on',True),('off',True),('individual_languages',False),('on',False),('off',False)):
    w=setup(100151,overrides={**options,'shuffle_speak':mode,'shuffle_npc_soul':soul},stop_before='pre_fill').worlds[1]
    verify(w,f'{mode}/{soul}',soul,mode)
    if mode=='individual_languages' and soul:
        slot=convert_to_base_types(w.fill_slot_data())
        restored=setup(100151,overrides={**options,'shuffle_speak':'off','shuffle_npc_soul':False},passthrough=slot,stop_before='pre_fill').worlds[1]
        verify(restored,'restored shuffled settings',True,mode)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),tests=tests),indent=2),encoding='utf8')
print('RESULT',passed,len(tests))
for t in [t for t in tests if not t['passed']][:12]:print(t)
raise SystemExit(not passed)
