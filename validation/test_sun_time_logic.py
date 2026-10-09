"""AP and Universal Tracker time access with independent Sun's Song prerequisites.

No region reachability is forced. All other abilities/souls/items are provided;
each required song note, instrument, and button is removed independently.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions,Ages
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import at_day,at_night
from ut_harness import tracker
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args();tests=[]
def ck(name,actual,expected):tests.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))
for phase in ('day','night'):
 for notes in ('off','individual_notes'):
  for buttons in (False,True):
    prefix=f'{phase}/{notes}/buttons={buttons}'
    m=setup(300938,overrides={'frozen_starting_time':phase,'shuffle_flow_of_time':True,
        'song_note_shuffle':notes,'shuffle_ocarina_buttons':buttons,'shuffle_ocarinas':True,
        'shuffle_enemy_soul':'individual_enemies','shuffle_enemy_drops':True},stop_before='pre_fill')
    w=m.worlds[1];evaluate=tracker(w,a.ut_core)
    items=[*m.itempool,*[l.item for l in w.get_locations() if l.address is not None and l.item]]
    names=[i.name for i in items if i.name in w.item_name_to_id]
    peahats=[l for l in w.get_locations() if l.address and 9800520<=l.address<=9800526]
    guays=[l for l in w.get_locations() if l.address and 9800705<=l.address<=9800719]
    ck(prefix+'/parent counts',(len(peahats),len(guays)),(7,15))
    needed=list(w.SONG_NOTE_GROUPS["Sun's Song"]) if notes!='off' else ["Sun's Song"]
    needed+=['Progressive Ocarina']
    if buttons:needed+=['Ocarina C Up Button','Ocarina C Right Button','Ocarina C Down Button']
    cases=[('playable song',{'Flow of Time'},True),('Flow alone',set(needed),True)]
    cases += [(f'missing {n}',{'Flow of Time',n},False) for n in needed]
    # Unused buttons/other songs must not disable Sun's Song.
    if buttons:cases.append(('unneeded buttons absent',{'Flow of Time','Ocarina A Button','Ocarina C Left Button'},True))
    for label,remove,can_switch in cases:
        receipts=[n for n in names if n not in remove]
        state=CollectionState(m)
        for item in m.precollected_items[1]:
            if item.name in remove:state.remove(item)
        for name in receipts:state.collect(w.create_item(name),True)
        state.sweep_for_advancements([l for l in w.get_locations() if l.address is None and l.item])
        result=evaluate(receipts)
        for loc in peahats+guays:
            want_day=loc in peahats
            expected=can_switch or want_day==(phase=='day')
            ck(prefix+'/'+label+'/AP/'+loc.name,loc.can_reach(state),expected)
            ck(prefix+'/'+label+'/UT/'+loc.name,loc.name in result.in_logic_locations,expected)
        for age in (Ages.CHILD,Ages.ADULT):
            previous=state._soh_extreme_age[1];state._soh_extreme_age[1]=age
            try:
                bundle=(Regions.HYRULE_FIELD,w)
                ck(prefix+'/'+label+'/day/'+str(age),at_day(bundle).resolve(w)(state),can_switch or phase=='day')
                ck(prefix+'/'+label+'/night/'+str(age),at_night(bundle).resolve(w)(state),can_switch or phase=='night')
            finally:state._soh_extreme_age[1]=previous
result=dict(scope=__doc__,passed=all(t['passed'] for t in tests),assertions=len(tests),tests=tests)
a.report.write_text(json.dumps(result,indent=2));print('PASS' if result['passed'] else 'FAIL',len(tests))
for t in tests:
 if not t['passed']:print(t)
raise SystemExit(not result['passed'])
