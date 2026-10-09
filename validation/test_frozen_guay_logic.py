"""Real AP/UT Guay regression against the engine's frozen-clock phases.

Dusk is 0xB555; the engine sets night only after 0xC000 or before 0x4555.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions,Ages
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import at_day,at_night
from ut_harness import tracker
from pathlib import Path
import argparse,json

p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True);a=p.parse_args();checks=[]
def ck(name,actual,expected):
    row=dict(test=name,actual=actual,expected=expected,passed=actual==expected);checks.append(row)
    if not row['passed']:print('FAIL',row)

# These values are also checked against the compiled engine freeze/classify code.
for phase,clock in (('dawn',0x4555),('day',0x8000),('dusk',0xB555),('night',0x0000)):
    engine_night=clock>0xC000 or clock<0x4555
    m=setup(290960,overrides={'frozen_starting_time':phase,'shuffle_flow_of_time':True},stop_before='pre_fill')
    w=m.worlds[1];evaluate=tracker(w,a.ut_core)
    guays=[l for l in w.get_locations() if l.address and 9800705<=l.address<=9800719]
    ck(phase+' all 15 child-night Guays exist',len(guays),15)
    items=[*m.itempool,*[l.item for l in w.get_locations() if l.address is not None and l.item]]
    names=[i.name for i in items if i.name in w.item_name_to_id]
    for label,remove in (
        ('flow missing',{'Flow of Time'}),
        ('flow and song equipment missing',{'Flow of Time'}|{n for n in names if 'Ocarina' in n or n=="Sun's Song"}),
        ('time unlocked',set()),
        ('time unlocked without song equipment',{n for n in names if 'Ocarina' in n or n=="Sun's Song"}),
        ('Guay Soul missing',{'Guay Soul'}),
    ):
        receipts=[n for n in names if n not in remove]
        s=CollectionState(m)
        for item in m.precollected_items[1]:
            if item.name in remove:s.remove(item)
        for name in receipts:s.collect(w.create_item(name),True)
        s.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
        result=evaluate(receipts)
        expected=label!='Guay Soul missing' and (label!='flow and song equipment missing' or engine_night)
        for l in guays:
            direct=l.can_reach(s)
            ck(phase+' / '+label+' / '+l.name,direct,expected)
            ck(phase+' / '+label+' / AP/UT '+l.name,l.name in result.in_logic_locations,direct)
        if label=='flow missing':
            # Shared helpers also gate NPCs, Market wonders, castle entry and GS.
            for age in (Ages.CHILD,Ages.ADULT):
                previous=s._soh_extreme_age[1];s._soh_extreme_age[1]=age
                try:
                    b=(Regions.LON_LON_RANCH,w)
                    ck(phase+' day helper '+str(age),at_day(b).resolve(w)(s),True)
                    ck(phase+' night helper '+str(age),at_night(b).resolve(w)(s),True)
                finally:s._soh_extreme_age[1]=previous
        if label=='time unlocked':
            # The Ranch Guay placements are child-night only, even with time free.
            previous=s._soh_extreme_age[1];s._soh_extreme_age[1]=Ages.ADULT
            try:
                for l in guays:ck(phase+' adult cannot borrow child Guay '+l.name,l.access_rule(s),False)
            finally:s._soh_extreme_age[1]=previous

report=dict(scope=__doc__,passed=all(c['passed'] for c in checks),assertions=len(checks),
            failures=sum(not c['passed'] for c in checks),checks=checks)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ASSERTIONS',report['assertions'],'FAILURES',report['failures']);raise SystemExit(bool(report['failures']))
