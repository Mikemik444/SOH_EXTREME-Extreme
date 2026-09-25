"""Enumerate the complete configured AP graph and link it to source definitions.

This is a structural/source audit, NOT a certificate of physical playability.
Unknown/contracted regions and unmatched identities remain explicit findings.
"""
from __future__ import annotations
import argparse, json, re, collections
from pathlib import Path
from run_case import setup, BOOTSTRAP
from worlds.soh_extreme._vendor_oot_soh.Enums import Locations
from worlds.soh_extreme._vendor_oot_soh.Locations import location_data_table
from worlds.soh_extreme.ForkLocations import FORK_LOCATIONS
from worlds.soh_extreme.SpeechLocations import SPEECH_LOCATIONS
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS


from source_index import normalize, native_metadata, native_sources as parse_native_sources

def collect(root,w):
    sources,regions=parse_native_sources(root)
    metadata=native_metadata(root)
    name_index=collections.defaultdict(set)
    for rc,entry in metadata.items():
        if entry["spoiler_name"]:name_index[normalize(entry["spoiler_name"])].add(rc)
    text=(root/'soh/Network/Archipelago/ArchipelagoLocationMap.inc').read_text()
    rc_by_id={int(id_):rc for rc,id_ in re.findall(r'static_cast<int>\((RC_\w+)\),\s*(\d+)LL',text)}
    fork={f.address:f for f in FORK_LOCATIONS};enemy={e.address:e for e in ENEMY_DROP_LOCATIONS}
    speeches={s.address:s for s in SPEECH_LOCATIONS}
    stock={d.loc_id:k for k,d in location_data_table.items() if d.loc_id is not None}
    native_norm=collections.defaultdict(set)
    for rc in sources:native_norm[normalize(rc[3:])].add(rc)
    rows=[]
    for l in sorted(w.get_locations(),key=lambda l:(l.address is None,l.address or 0,l.name)):
        r=dict(name=l.name,id=l.address,ap_region=l.parent_region.name,kind='stock',source_match=None,rc=None,native_sources=[],findings=[],physical_verified=False)
        if l.address in enemy:
            e=enemy[l.address];r.update(kind='enemy',source_match='placement_catalogue',scene=e.scene_id,room=e.room,actor=e.actor_id,combat=e.combat,encounter_gate=e.encounter_gate)
            r['findings'].append('room_route_unreviewed' if e.region_token.endswith('ENTRYWAY') else 'physical_encounter_not_playtested')
        elif l.address in speeches:
            e=speeches[l.address];r.update(kind='speech',source_match='speech_catalogue',rc=e.rc)
            r['findings'].append('first_talk_runtime_identity_requires_review')
        else:
            if l.address in fork:r.update(kind='fork',source_match='explicit_fork_id',rc=fork[l.address].rc,family=fork[l.address].family)
            elif l.address in rc_by_id:r.update(source_match='explicit_native_id',rc=rc_by_id[l.address])
            elif l.address in stock:
                member=stock[l.address];candidates=native_norm[normalize(member.name)]
                if len(candidates)==1:r.update(source_match='unique_enum_normalization',rc=next(iter(candidates)))
            if not r['rc'] and len(name_index[normalize(l.name)])==1:
                r.update(source_match='unique_runtime_spoiler_name',rc=next(iter(name_index[normalize(l.name)])))
            if l.address is None:r['kind']='event'
        if r['rc']:
            r['native_sources']=sources.get(r['rc'],[])
            r['native_metadata']=metadata.get(r['rc'])
            if not r['native_sources']:r['findings'].append('no_native_location_expression')
        elif r['kind'] not in ('enemy','event'):r['findings'].append('native_identity_not_resolved')
        if r['native_sources']:
            exact=[s for s in r['native_sources'] if normalize(s['region'][3:]).replace('THE','')==normalize(next((reg.name for reg in __import__('worlds.soh_extreme._vendor_oot_soh.Enums',fromlist=['Regions']).Regions if str(reg)==l.parent_region.name),l.parent_region.name)).replace('THE','')]
            if not exact:r['findings'].append('native_ap_region_crosswalk_requires_review')
        if l.parent_region.name=='Menu' and l.address not in (11,12) and l.address is not None:r['findings'].append('neutral_parent_requires_explicit_complete_route')
        rows.append(r)
    return rows,sources

if __name__=='__main__':
    p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    m=setup(1717,overrides={'boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1]
    rows,sources=collect(a.source_root,w)
    result={'scope':'All graph locations for resolved supplied YAML; source inspection only, not physical certification.','locations':len(rows),'network_locations':sum(r['id'] is not None for r in rows),'kind_counts':dict(collections.Counter(r['kind'] for r in rows)), 'identity_match_counts':dict(collections.Counter(r['source_match'] for r in rows)), 'finding_counts':dict(collections.Counter(x for r in rows for x in r['findings'])),'native_location_definitions':sum(map(len,sources.values())),'native_unique_checks':len(sources),'rows':rows}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k!='rows'},flush=True)
