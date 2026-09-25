"""Test the real AP world: native-room routes, identity, missing prerequisites,
optional internal-action pruning and Universal Tracker slot reconstruction.
No game engine or physical playthrough is represented by these tests.
"""
from __future__ import annotations
import argparse, collections, dataclasses, json, re, runpy, traceback
from pathlib import Path
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from Options import OptionError
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS, ENEMY_OFFSPRING_RETIRED_IDS
from worlds.soh_extreme.EnemyRoomLogic import GRAPH, ENEMY_ROOM_MAP, NativeEnemyRegions, resolve_enemy_region, NativeRoomCompiler, parse

p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
checks=[];coverage={};matrix={}
def check(name,actual,expected=True):
    if isinstance(expected,bool):actual=bool(actual)
    row={'test':name,'passed':actual==expected,'actual':actual,'expected':expected};checks.append(row)
    if not row['passed']:print('FAIL',name,repr(actual)[:1200],flush=True)
def byid(w,address):return next(loc for loc in w.get_locations() if loc.address==address)
def fresh_inventory(m,w,missing=(),extra=()):
    # Do not retain historical room-clear flags from an all-state sweep. These
    # tests model never having acquired the missing prerequisite, not forgetting
    # it after a switch or door was already opened.
    s=m.get_all_state(perform_sweep=False)
    for name in missing:
        while s.count(name,w.player):
            item=w.create_item(name);before=s.count(name,w.player);s.remove(item)
            assert s.count(name,w.player)<before,name
    for name in extra:s.collect(w.create_item(name),True)
    s.sweep_for_advancements()
    return s

def addresses(w,s):return {loc.address for loc in w.get_locations() if loc.address is not None and loc.can_reach(s)}

try:
    m=setup(11811,overrides={'boss_key_shuffle':'anywhere','ganons_trials':'set_number','ganons_trials_count':6},stop_before='pre_fill');w=m.worlds[1]
    full=fresh_inventory(m,w)
    check('world version',w.world_version.as_simple_string(),'0.11.18')
    check('all 753 active enemies remain',len(ENEMY_DROP_LOCATIONS),753)
    check('535 dungeon encounters explicitly mapped',len(ENEMY_ROOM_MAP),535)
    check('413 previous entryway assignments replaced',sum('ENTRYWAY' in row['previous_ap_region'] for row in ENEMY_ROOM_MAP.values()),413)
    check('none of the current enemy parents is a dungeon entryway',[e.name for e in ENEMY_DROP_LOCATIONS if 'ENTRYWAY' in e.region_token],[])
    check('offspring IDs not reused',sorted(ENEMY_OFFSPRING_RETIRED_IDS & {e.address for e in ENEMY_DROP_LOCATIONS}),[])
    check('all enemies reachable with full inventory',[e.name for e in ENEMY_DROP_LOCATIONS if not w.get_location(e.name).can_reach(full)],[])
    check('trials resolved before graph compilation',len(w.ganons_trials),6)
    native=(a.source_root/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc').read_text()
    nmap={int(i):rr for i,rr in re.findall(r'\{\s*(\d+)LL,\s*\w+,\s*(RR_\w+),',native)}
    for e in ENEMY_DROP_LOCATIONS:
        if str(e.address) not in ENEMY_ROOM_MAP:continue
        row=ENEMY_ROOM_MAP[str(e.address)]
        check('AP/native region identity '+str(e.address),nmap[e.address],e.region_token)
        check('AP actual parent '+str(e.address),w.get_location(e.name).parent_region.name,str(resolve_enemy_region(e.region_token)))
        check('native graph contains '+str(e.address),e.region_token in GRAPH)
    if a.baseline:
        old=runpy.run_path(str(a.baseline/'source/soh_extreme/EnemyDropLocations.py'))['ENEMY_DROP_LOCATIONS']
        def immutable(e):return tuple((f.name,getattr(e,f.name)) for f in dataclasses.fields(e) if f.name!='region_token')
        check('all network identities and immutable fields unchanged',[immutable(e) for e in ENEMY_DROP_LOCATIONS],[immutable(e) for e in old])
        checks[-1].update(actual=len(ENEMY_DROP_LOCATIONS),expected=len(old))
        for rel in ('soh/Enhancements/randomizer/EnemyDefeatPlacements.inc','soh/Enhancements/randomizer/EnemySpawnCatalog.h','soh/Enhancements/randomizer/EnemySpawnAliases.inc','soh/Enhancements/randomizer/EnemyChildAliases.inc','soh/Enhancements/randomizer/MegaSouls.cpp'):
            check('unchanged runtime identity/origin code '+rel,(a.source_root/rel).read_bytes()==(a.baseline/rel).read_bytes())
    text=(a.source_root/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp').read_text()
    check('removed whole-dungeon native approximation','EnemyFinderFullDungeonGate' in text,False)
    check('native local conditions inside current age/time loop',text.index('enemyLogic->IsAdult = i >= 2;') < text.index('if (!EnemyFinderRoomCondition(enemyLogic.get(), entry))'))
    # Required item absence and valid earlier encounters. No already-collected
    # local flags can open shortcuts in fresh_inventory.
    scenarios=[
      ('Bow arena does not require its guarded Bow',['Bow'],[9800720,9800721,9800722],[]),
      ('Jabu Stingers do not require their guarded Boomerang',['Boomerang'],[9800104,9800105,9800106,9800107],[9800728]),
      ('Ice entrance does not require later Blue Fire',[name for name in w.item_name_to_id if 'Bottle' in name]+['Ice Arrows'],[9800392,9800393,9800394,9800395],[]),
      ('GTG Wolves are before the heavy block',['Strength Upgrade','Grab / Power Bracelet'],[9800429,9800430,9800432,9800433],[]),
      ('DC corridor babies precede slingshot puzzle',['Slingshot','Grab / Power Bracelet'],[9800036],[]),
      ('Forest key doors cannot be skipped',['Forest Temple Small Key','Skeleton Key'],[],[9800720,9800721,9800722]),
      ('Six required trials block the tower without Light Arrows',['Light Arrows'],[],[e.address for e in ENEMY_DROP_LOCATIONS if e.scene_id==10]),
      ('Boat activation requires its playable song',['Song Note 01'],[],[9800370,9800371]),
      ('Water Temple respects missing Swim',['Progressive Scale'],[],[e.address for e in ENEMY_DROP_LOCATIONS if e.scene_id==5]),
      ('Well entrance respects Crawl',['Crawl'],[],[e.address for e in ENEMY_DROP_LOCATIONS if e.scene_id==8]),
      ('Individual Stalfos Soul is not replaced by global',['Stalfos Soul'],[],[e.address for e in ENEMY_DROP_LOCATIONS if e.soul_item=='Stalfos Soul']),
    ]
    # Item names are checked explicitly; do not silently skip a typo.
    aliases={'Bow':'Progressive Bow','Slingshot':'Progressive Slingshot'}
    for label,missing,reachable,blocked in scenarios:
        missing=[aliases.get(x,x) for x in missing]
        for n in missing:assert n in w.item_name_to_id,'Unknown test item '+n
        state=fresh_inventory(m,w,missing,extra=['Enemy Soul'] if 'Individual Stalfos' in label else [])
        matrix[label]={'missing':missing,'reachable_enemy_count':sum(w.get_location(e.name).can_reach(state) for e in ENEMY_DROP_LOCATIONS)}
        for i in reachable:check(label+' permits '+str(i),byid(w,i).can_reach(state))
        for i in blocked:check(label+' blocks '+str(i),byid(w,i).can_reach(state),False)
    # Every mapped individual soul is necessary at the actual location rule;
    # separate copies ensure the dependency isn't hidden by a cached room.
    for soul,es in __import__('itertools').groupby(sorted(ENEMY_DROP_LOCATIONS,key=lambda e:e.soul_item or ''),key=lambda e:e.soul_item):
        es=list(es)
        if not soul:continue
        state=fresh_inventory(m,w,[soul],extra=['Enemy Soul'])
        for e in es:check('individual soul requirement '+str(e.address)+' '+soul,w.get_location(e.name).can_reach(state),False)
    # Optional native helper sites are not addressed checks. Removing impossible
    # alternatives may not change the network set or full-inventory reachability.
    before_ids={loc.address for loc in w.get_locations() if loc.address is not None};before_reach=addresses(w,full)
    from worlds.soh_extreme.EnemyRoomLogic import prune_optional_native_actions
    prune_optional_native_actions(w)
    check('pruning removes zero network locations',{loc.address for loc in w.get_locations() if loc.address is not None},before_ids)
    checks[-1].update(actual=len(before_ids),expected=len(before_ids))
    check('pruning does not open network checks',addresses(w,fresh_inventory(m,w)),before_reach)
    checks[-1].update(actual=len(before_reach),expected=len(before_reach))
    check('pruned names are internal only',all(x.startswith(('EXTREME Native RR_','EXTREME Native Action: ')) for x in w._extreme_room_disabled_actions))
    # Unknown grammar, helper, region or mutable negative predicate must stop,
    # rather than convert an unsupported route into unconditional access.
    compiler=w._extreme_room_compiler
    for expr in ('UnsupportedRoomAction()','HasItem(RG_NOT_A_REAL_ITEM)','Get(LOGIC_NONEXISTENT)','!HasItem(RG_CLIMB)'):
        try:compiler.expr(expr,'RR_DEKU_TREE_LOBBY');rejected=False
        except (OptionError,KeyError):rejected=True
        check('strict compiler rejects '+expr,rejected)
    # A different seed/local configuration must use the server's required trials.
    slot=convert_to_base_types(w.fill_slot_data())
    tm=setup(11812,overrides={'boss_key_shuffle':'anywhere','ganons_trials':'skip','ganons_trials_count':0,'shuffle_climb':False,'shuffle_grab':False,'shuffle_enemy_soul':0},passthrough=slot,stop_before='pre_fill');tw=tm.worlds[1]
    prune_optional_native_actions(tw)
    check('UT restores six required trials',list(tw.ganons_trials),list(w.ganons_trials))
    check('UT restores internal action set',tw._extreme_room_disabled_actions,w._extreme_room_disabled_actions)
    compare_patterns=[[],['Climb'],['Grab / Power Bracelet'],['Crawl'],['Progressive Scale'],['Boomerang'],['Progressive Bow'],['Forest Temple Small Key','Skeleton Key'],['Light Arrows'],['Stalfos Soul'],['Progressive Ocarina'],['Song Note 01']]
    for missing in compare_patterns:
        gs=fresh_inventory(m,w,missing);ts=fresh_inventory(tm,tw,missing)
        differences=[e.name for e in ENEMY_DROP_LOCATIONS if w.get_location(e.name).can_reach(gs)!=tw.get_location(e.name).can_reach(ts)]
        check('all-enemy UT equality without '+repr(missing),differences,[])
    # In a legitimately skipped-trials world, Light Arrows must not be imposed
    # on the pre-Ganondorf tower enemies by a whole-dungeon heuristic.
    sm=setup(11813,overrides={'boss_key_shuffle':'anywhere','ganons_trials':'skip','ganons_trials_count':0},stop_before='pre_fill');sw=sm.worlds[1]
    skipstate=fresh_inventory(sm,sw,['Light Arrows'])
    for e in ENEMY_DROP_LOCATIONS:
        if e.scene_id==10:check('skipped trials retain tower access without LA '+str(e.address),sw.get_location(e.name).can_reach(skipstate))
    coverage={'mapped_dungeon_enemies':535,'active_enemies':753,'native_regions':len(GRAPH),'ut_inventory_scenarios':len(compare_patterns),'ut_enemy_comparisons':len(compare_patterns)*len(ENEMY_DROP_LOCATIONS),'internal_disabled_sites':w._extreme_room_disabled_actions,'rule_audit':w._extreme_native_room_audit}
except Exception as ex:
    traceback.print_exc();checks.append({'test':'unhandled exception','passed':False,'error':repr(ex),'traceback':traceback.format_exc()})
report={'scope':__doc__,'checks':checks,'total':len(checks),'failures':sum(not c['passed'] for c in checks),'coverage':coverage,'inventory_matrix':matrix}
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,default=lambda obj:sorted(obj) if isinstance(obj,set) else str(obj)))
print('TOTAL',report['total'],'FAILURES',report['failures'],flush=True)
raise SystemExit(bool(report['failures']))
