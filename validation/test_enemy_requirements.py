"""Full active enemy catalogue AP/UT requirement audit and focused combat regressions.

Uses fresh states with no previously cleared rooms. Controlled combat tests isolate
the kill rule from traversal; catalogue tests retain real regions and events.
Neither is a physical in-game playthrough.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from BaseClasses import CollectionState
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS, ENEMY_UNUSED_OBJECT_IDS
from worlds.soh_extreme.EnemyDropRules import enemy_drop_rule
from worlds.soh_extreme._vendor_oot_soh.Enums import Events, Items, Ages
from pathlib import Path
import argparse, collections, dataclasses, json, re

p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[];coverage={}
def ck(name,actual,expected=True):
    tests.append(dict(test=name,actual=actual,expected=expected,passed=actual==expected))
    if actual!=expected: print('FAIL',name,str(actual)[:300],expected,flush=True)
options=dict(shuffle_enemy_drops=True,shuffle_enemy_soul='individual_enemies',shuffle_skulltula_soul=True,
    shuffle_npc_soul=True,shuffle_speak='individual_languages',shuffle_grab=True,shuffle_climb=True,
    shuffle_crawl=True,shuffle_roll=True,shuffle_open_chest='progressive',shuffle_swim=True,shuffle_shovel=True,shuffle_pot_soul=True,
    shuffle_flow_of_time=True,frozen_starting_time='night',closed_forest='on',door_of_time='song_only',
    starting_age='child',shuffle_master_sword=True,shuffle_deku_stick_bag=True,shuffle_deku_nut_bag=True,
    song_note_shuffle='off',shuffle_ocarina_buttons=False,tricks_in_logic=[],enable_all_tricks=False,
    start_inventory={},start_inventory_from_pool={},start_with_ocarina='off',start_with_song_of_time=False)
m=setup(930446,overrides=options);w=m.worlds[1];ev=tracker(w,a.ut_core)
entries=[e for e in ENEMY_DROP_LOCATIONS if e.address not in ENEMY_UNUSED_OBJECT_IDS]
locations={l.address:l for l in w.get_locations() if l.address is not None}
names=[i.name for i in m.itempool]+[l.item.name for l in locations.values() if l.item and l.item.name in w.item_name_to_id]
ck('739 active enemy placements',len(entries),739)
ck('all active enemy identities present',all(e.address in locations for e in entries))
finder=(a.source_root/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text()
for e in ENEMY_DROP_LOCATIONS:
    line=next(l for l in finder.splitlines() if re.search(r'\{\s*'+str(e.address)+r'LL,', l))
    ck('catalogue combat parity '+str(e.address),'EFC_'+e.combat.upper()+',' in line)
    ck('catalogue mask parity '+str(e.address),int(line.split(',')[9]),e.spawn_mask)
    ck('no entryway-only enemy parent '+str(e.address),not e.region_token.startswith('RR_') or 'ENTRYWAY' not in e.region_token)
def evaluate(label,removed,subset=None):
    received=[n for n in names if n not in removed]
    result=ev(received)
    for e in entries:
        direct=locations[e.address].can_reach(result.state)
        ck(label+' AP/UT '+str(e.address),direct,e.name in result.in_logic_locations)
        if not removed: ck('full inventory reaches '+str(e.address),direct)
        if subset and e.address in subset:ck(label+' blocked '+str(e.address),direct,False)
    coverage[label]=sum(e.name in result.in_logic_locations for e in entries)
    print('CHECKED',label,coverage[label],'reachable',flush=True)
    return result
evaluate('full',set())
souls=collections.defaultdict(list)
for e in entries:souls[e.soul_item or 'Skulltula Soul'].append(e.address)
for soul,ids in souls.items():evaluate('missing '+soul,{soul},set(ids))
for capability in ('Climb','Crawl','Grab / Power Bracelet','Roll','Open Chest','Progressive Scale','Shovel','NPC Soul','Speak Hylian','Speak Zora','Rock / Boulder Soul','Skeleton Key'):
    subset={e.address for e in entries if capability=='Shovel' and e.grotto_id>=0}
    if capability=='Progressive Scale':subset|={e.address for e in entries if e.encounter_gate=='swim'}
    if capability=='Crawl':subset|={e.address for e in entries if e.scene_id==8}
    if capability in ('NPC Soul','Speak Hylian'):subset|={e.address for e in entries if e.encounter_gate=='composer'}
    missing={capability}
    if capability=='Grab / Power Bracelet':missing.add('Strength Upgrade')
    evaluate('missing '+capability,missing,subset)
evaluate('no adult access',{'Progressive Ocarina','Song of Time'},
    {e.address for e in entries if not e.spawn_mask&3})
evaluate('frozen night without Sun song',{'Flow of Time',"Sun's Song"},
    {e.address for e in entries if e.actor_id==0x1d or not e.spawn_mask&10})
evaluate('Sun song while Flow absent',{'Flow of Time'})

# Isolated weapon regression cases: use actual AP rule construction but a known
# reachable parent, no prior room events and no extra encounter condition.
weapon_names={'Kokiri Sword','Master Sword','Biggoron Sword','Giants Knife','Progressive Goron Sword',
    'Progressive Slingshot','Progressive Bow','Progressive Hookshot','Boomerang','Megaton Hammer',
    'Progressive Bomb Bag','Progressive Bombchus','Bombchu Bag','Dins Fire','Fire Arrows','Ice Arrows',
    'Light Arrows','Progressive Stick Bag','Progressive Nut Bag','Deku Stick Capacity','Deku Nut Capacity'}
# Check actual network names rather than allowing typo-driven accidental weapons.
weapon_names|={n for n in w.item_name_to_id if any(x in n.lower() for x in ('sword','knife','stick','nut','bomb','slingshot','bow','hookshot','din\'s'))}
def combat(actor,items,adult=False,params=None):
    e=next(e for e in entries if e.actor_id==actor and (params is None or e.params&255==params))
    e=dataclasses.replace(e,address=-1,region_token='KOKIRI_FOREST',spawn_mask=12 if adult else 3,
        scene_id=85,grotto_id=-1,encounter_gate='')
    state=m.get_all_state(perform_sweep=False)
    for n in weapon_names:
        while state.count(n,1):state.remove(w.create_item(n))
    for n in items:state.collect(w.create_item(n),True)
    state.sweep_for_advancements()
    return enemy_drop_rule(w,e).resolve(w)(state)
cases=[
 (0x1b,['Boomerang'],False,False),(0x1b,['Kokiri Sword'],False,True),
 (0x2d,['Progressive Slingshot'],False,False),(0x2d,['Boomerang'],False,True),
 (0x34,['Progressive Slingshot'],False,False),(0x34,['Boomerang'],False,True),
 (0x63,['Progressive Slingshot'],False,False),(0x63,['Boomerang'],False,True),
 (0x35,['Progressive Slingshot'],False,False),(0x35,['Progressive Bow'],True,False),(0x35,['Boomerang'],False,True),
 (0x3a,['Boomerang'],False,False),(0x3a,['Progressive Slingshot'],False,True),
 (0x18c,['Boomerang'],False,False),(0x18c,['Progressive Slingshot'],False,True),
 (0x115,['Progressive Bow'],True,False),(0x115,['Master Sword'],True,True),
 (0xec,['Kokiri Sword'],False,False),(0xec,['Master Sword'],True,True),
 (0x121,['Kokiri Sword'],False,False),(0x121,['Master Sword'],True,True),
 (0xa4,['Megaton Hammer'],True,False),(0xa4,['Master Sword'],True,True),
 (0xa5,['Megaton Hammer'],True,False),(0xa5,['Kokiri Sword'],False,True),
]
for actor,items,adult,expected in cases:
    ck('combat '+hex(actor)+' '+str(items)+' adult='+str(adult),combat(actor,items,adult),expected)
# All three soul modes still allow a complete inventory and share the kill rules.
for mode in ('off','all_enemies_as_1'):
    q=setup(930447,overrides=dict(options,shuffle_enemy_soul=mode,frozen_starting_time='day' if mode=='off' else 'night')).worlds[1]
    full=q.multiworld.get_all_state(False)
    for e in entries:ck(mode+' full '+str(e.address),q.get_location(e.name).can_reach(full))
    if mode=='off':
        frozen=q.multiworld.get_all_state(perform_sweep=False)
        for n in ('Flow of Time',"Sun's Song"):
            while frozen.count(n,1):frozen.remove(q.create_item(n))
        frozen.sweep_for_advancements()
        for e in entries:
            if not e.spawn_mask&5 or e.encounter_gate=='night':
                ck('frozen day blocks '+str(e.address),q.get_location(e.name).can_reach(frozen),False)
    if mode=='all_enemies_as_1':
        empty=q.multiworld.get_all_state(perform_sweep=False)
        while empty.count('Enemy Soul',1):empty.remove(q.create_item('Enemy Soul'))
        empty.sweep_for_advancements()
        for e in entries:
            if e.soul_item and e.actor_id not in (0x37,0x95):ck('shared Soul missing '+str(e.address),q.get_location(e.name).can_reach(empty),False)
report=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),active_entries=len(entries),
    actor_types=len({e.actor_id for e in entries}),coverage=coverage,tests=tests,scope=__doc__)
a.report.write_text(json.dumps(report,indent=2));print('RESULT',report['passed'],len(tests),'assertions',flush=True)
raise SystemExit(not report['passed'])
