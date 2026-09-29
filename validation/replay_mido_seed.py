"""Read-only replay of supplied AP multidata with corrected SOH rules.

All SOH items from other games are granted at the start as an optimistic upper
bound. A remaining deadlock therefore cannot be solved by waiting for those
games. This does not run Jigsaw logic, alter the server, or edit the save.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from Utils import restricted_loads
from pathlib import Path
import argparse,hashlib,json,zlib

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--multidata',type=Path,required=True)
p.add_argument('--slot',type=int,required=True)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--recovery-item',action='append',default=[],
               help='Additional hypothetical recovery items; never sent to the server')
a=p.parse_args()
raw=a.multidata.read_bytes();assert raw[0]==3
d=restricted_loads(zlib.decompress(raw[1:]))
assert d['slot_info'][a.slot].game=='SOH-EXTREME'
slot=d['slot_data'][a.slot]
m=setup(290932,passthrough=slot,stop_before='pre_fill');w=m.worlds[1]
locations={l.address:l for l in w.get_locations() if type(l.address) is int}
placements=d['locations'][a.slot]
assert set(locations)==set(placements), (set(locations)-set(placements),set(placements)-set(locations))
by_id={v:k for k,v in w.item_name_to_id.items()}
remote=[item for other,rows in d['locations'].items() if other!=a.slot
        for item,recipient,*_ in rows.values() if recipient==a.slot]

def replay(extra=()):
    s=CollectionState(m)
    for item_id in [*d['precollected_items'].get(a.slot,[]),*remote]:
        s.collect(w.create_item(by_id[item_id]),True)
    for name in extra:s.collect(w.create_item(name),True)
    remaining=set(locations);waves=[]
    while True:
        s.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
        reachable=sorted(i for i in remaining if locations[i].can_reach(s))
        if not reachable:break
        waves.append(len(reachable));remaining.difference_update(reachable)
        for location_id in reachable:
            item_id,recipient,*_=placements[location_id]
            if recipient==a.slot:s.collect(w.create_item(by_id[item_id]),True)
    diagnostics=[]
    if len(remaining)<10:
        for i in sorted(remaining):
            rule=locations[i].access_rule
            diagnostics.append(dict(name=locations[i].name,rule=repr(rule),
                dependencies={str(n):s.count(str(n),1) for n in rule.item_dependencies()} if hasattr(rule,'item_dependencies') else {},
                inventory={str(n):c for n,c in s.prog_items[1].items() if c}))
    return dict(extra_items=list(extra),beatable=m.has_beaten_game(s),wave_sizes=waves,diagnostics=diagnostics,
        checked=len(locations)-len(remaining),blocked_count=len(remaining),
        blocked_names=[locations[i].name for i in sorted(remaining)] if len(remaining)<10 else [],
        mido_babas_blocked=[locations[i].name for i in range(9800531,9800536) if i in remaining],
        capabilities={name:s.count(name,1) for name in ('Climb','Swim','Grab / Power Bracelet','Cucco Soul',
            'Time Travel','NPC Soul','Speak Kokiri','Buy Deku Shield','Deku Baba Soul')})

normal=replay()
recovery=replay(['Climb'])
report=dict(passed=True,multidata_sha256=hashlib.sha256(raw).hexdigest(),slot=a.slot,
    network_checks=len(locations),optimistically_pregranted_other_world_items=len(remote),
    limitations=__doc__,original_placements=normal,hypothetical_climb_recovery=recovery)
if a.recovery_item:
    report['additional_hypothetical_recovery']=replay(a.recovery_item)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
