"""Whole-graph fresh-inventory/UT audit for every shuffled capability receipt.

All active checks are evaluated for every scenario. Source-proven necessary
requirements are additionally asserted; AP/UT agreement alone is not a proof
of physical accessibility. No saved event cache is reused between inventories.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from location_source_audit import collect
from audit_prerequisites import expected_for, resolve_item
from BaseClasses import CollectionState
from worlds.soh_extreme import NpcSpeech
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions, Ages
from pathlib import Path
from collections import Counter
import argparse, json, hashlib
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();m=setup(290939);w=m.worlds[1];evaluate=tracker(w,a.ut_core)
rows,_=collect(a.source_root,w)
expectations={r['id']:{resolve_item(t,w) for t in expected_for(r,a.source_root)}-{None}
              for r in rows if r['kind'] in ('stock','fork')}
locations={l.address:l for l in w.get_locations() if type(l.address) is int}
physical=[it for it in m.itempool]+[l.item for l in w.get_locations() if l.address is not None and l.item]
physical=[it for it in physical if it.name in w.item_name_to_id]
capabilities={'Roll','Strength Upgrade','Climb','Crawl','Progressive Scale','Open Chest',
    'Shovel','Flow of Time','Fishing Pole','Progressive Stick Capacity','Progressive Nut Capacity',
    'Progressive Ocarina','Progressive Wallet'}
capabilities|={it.name for it in physical if 'Soul' in it.name or it.name.startswith(('Speak','Song Note ','Ocarina '))}
capabilities&={it.name for it in physical}
scenarios=[('all receipts',set())]+[(name,{name}) for name in sorted(capabilities)]
failures=[];summary=[];per_location={i:dict(name=l.name,scenarios=0,source_requirements=sorted(expectations.get(i,set()))) for i,l in locations.items()}
physical_counts=Counter(it.name for it in physical)
for label,removed in scenarios:
    receipt_items=[it for it in physical if it.name not in removed]
    result=evaluate([it.name for it in receipt_items])
    s=CollectionState(m)
    for it in m.precollected_items[1]:
        if it.name in removed:s.remove(it)
    for item in receipt_items:s.collect(item,True)
    s.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
    absent=set(removed)
    if 'Strength Upgrade' in removed:absent.add('Grab / Power Bracelet')
    if 'Progressive Scale' in removed:absent.add('Swim')
    reachable=0;required_blocked=0
    for i,l in locations.items():
        direct=l.can_reach(s);ut=l.name in result.in_logic_locations
        per_location[i]['scenarios']+=1
        if direct:reachable+=1
        if direct!=ut:failures.append(dict(scenario=label,id=i,name=l.name,error='AP/UT mismatch',ap=direct,ut=ut))
        npc = NpcSpeech.BY_NAME.get(l.name)
        if direct and npc and npc['routes']:
            # Independent necessary condition: the actual age-specific graph
            # must reach a physical NPC route, regardless of its own rule.
            previous=s._soh_age[1]
            route_reachable=False
            try:
                for route in npc['routes']:
                    ages=(Ages.CHILD,Ages.ADULT) if route['age']=='either' else (Ages.CHILD,) if route['age']=='child' else (Ages.ADULT,)
                    for age in ages:
                        s._soh_age[1]=age
                        route_reachable |= w.get_region(str(Regions[route['region']])).can_reach(s)
            finally:
                s._soh_age[1]=previous
            if not route_reachable:
                failures.append(dict(scenario=label,id=i,name=l.name,error='NPC reachable without a physical route'))
        if not removed and not direct:failures.append(dict(scenario=label,id=i,name=l.name,error='blocked with complete inventory'))
        required=expectations.get(i,set())&absent
        if required:
            required_blocked+=1
            if direct:failures.append(dict(scenario=label,id=i,name=l.name,error='missing source-proven requirement',required=sorted(required)))
    # Physical note receipts must not leave their virtual song granted early.
    for song,notes in w.SONG_NOTE_GROUPS.items():
        if removed.intersection(notes) and s.has(song,1):
            failures.append(dict(scenario=label,error='song granted with missing note',song=song))
    summary.append(dict(scenario=label,removed_copies=sum(physical_counts[n] for n in removed),reachable=reachable,
        source_requirement_assertions=required_blocked))
    if len(summary)%15==0:print('SCENARIOS',len(summary),'/',len(scenarios),flush=True)
report=dict(passed=not failures,scope=__doc__,network_checks=len(locations),inventory_scenarios=len(scenarios),
    ap_ut_comparisons=len(scenarios)*len(locations),failures=failures,scenarios=summary,
    all_active_locations=per_location,options={n:getattr(w.options,n).value for n in w.options_dataclass.type_hints},
    yaml_sha256=hashlib.sha256(a.yaml.read_bytes()).hexdigest(),
    ut_sha256=hashlib.sha256(a.ut_core.read_bytes()).hexdigest())
a.report.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
print('PASS' if not failures else 'FAIL',len(locations),'locations',len(scenarios),'inventories',len(failures),'failures')
for failure in failures[:12]:print(failure)
raise SystemExit(bool(failures))
