"""Actual AP/UT Peahat checks need daytime vulnerability, not just an actor spawn."""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme._vendor_oot_soh.Enums import Ages
from ut_harness import tracker
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args();tests=[]
def ck(name,actual,expected):tests.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))
for phase in ('dawn','day','dusk','night'):
 for shuffled in (False,True):
    m=setup(300937,overrides={'frozen_starting_time':phase,'shuffle_flow_of_time':shuffled,
        'shuffle_enemy_soul':'individual_enemies','shuffle_enemy_drops':True},stop_before='pre_fill')
    w=m.worlds[1];evaluate=tracker(w,a.ut_core)
    locs=[l for l in w.get_locations() if l.address and 9800520<=l.address<=9800526]
    ck(f'{phase}/{shuffled}/seven parents',len(locs),7)
    items=[*m.itempool,*[l.item for l in w.get_locations() if l.address is not None and l.item]]
    names=[i.name for i in items if i.name in w.item_name_to_id]
    for label,remove in [('no flow',{'Flow of Time'}),
                         ('no flow or song',{'Flow of Time',"Sun's Song"}|{n for n in names if 'Ocarina' in n}),
                         ('flow collected',set()),('soul missing',{'Peahat Soul'})]:
        receipts=[n for n in names if n not in remove]
        state=CollectionState(m)
        for name in receipts:state.collect(w.create_item(name),True)
        state.sweep_for_advancements([l for l in w.get_locations() if l.address is None and l.item])
        result=evaluate(receipts)
        expected=label!='soul missing' and (not shuffled or phase!='night' or label!='no flow or song')
        for loc in locs:
            ck(f'{phase}/{shuffled}/{label}/AP/{loc.name}',loc.can_reach(state),expected)
            ck(f'{phase}/{shuffled}/{label}/UT/{loc.name}',loc.name in result.in_logic_locations,expected)
        # All seven placements exist only in child layouts.
        before=state._soh_age[1];state._soh_age[1]=Ages.ADULT
        try:
            for loc in locs:ck(f'{phase}/{shuffled}/{label}/adult/{loc.name}',loc.access_rule(state),False)
        finally:state._soh_age[1]=before
result=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),tests=tests)
a.report.write_text(json.dumps(result,indent=2));print('PASS' if result['passed'] else 'FAIL',len(tests))
for t in tests:
    if not t['passed']:print(t)
raise SystemExit(not result['passed'])
