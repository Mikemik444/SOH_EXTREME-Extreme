"""Focused negative and alternate-route regressions using the real AP world/core.

No physics or live-client simulation. Restricted offline schema/bsdiff adapters
from the existing harness; production rule construction/collection are intact.
"""
from pathlib import Path
import sys, argparse, json, traceback, itertools
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from Options import OptionError
from worlds.soh_extreme import SOH_ITEM_ALIASES, RequireAnyItemGroups, RequireAnyExistingItems
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import (
    Regions, Items, Ages, can_grab, can_climb, can_crawl, can_swim,
    can_break_pots, can_break_crates, can_break_small_crates, can_bonk_trees,
    can_cut_shrubs, can_break_lower_hives, can_break_upper_beehives,
    can_interact_npc, at_day, at_night, can_use, has_item, water_timer_at_least,
)
from worlds.soh_extreme._vendor_oot_soh.Locations import LocTag, location_data_table
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True)
p.add_argument('--group', choices=['capabilities','enemy-modes','clock'], default='capabilities');args=p.parse_args()
results=[];coverage={}
def check(name, actual, expected=True, **extra):
    ok=actual==expected
    results.append(dict(name=name,passed=ok,actual=actual,expected=expected,**extra))
    if not ok: print('FAIL',name,repr(actual)[:1600],flush=True)

def snapshot(mw,w,exclude=(),only=None):
    s=CollectionState(mw);excluded=set(exclude)
    for it in mw.precollected_items[w.player]:
        if it.name in excluded or (only is not None and it.name not in only):s.remove(it)
    for it in list(mw.itempool)+[l.item for l in mw.get_filled_locations(w.player) if l.item and l.address is not None]:
        if it.name not in excluded and (only is None or it.name in only):s.collect(it,True)
    s.sweep_for_advancements([l for l in mw.get_filled_locations(w.player) if l.item and l.address is None and l.item.name not in excluded])
    return s

def bare(mw,w,names):
    s=CollectionState(mw)
    for it in mw.precollected_items[w.player]:s.remove(it)
    for n in names:s.collect(w.create_item(n),True)
    return s

def remove_all(s,w,names):
    for n in names:
        for _ in range(s.count(n,w.player)): s.remove(w.create_item(n))
    return s

def eval_rule(rule,w,state,age=Ages.CHILD):
    old=state._soh_age[w.player];state._soh_age[w.player]=age
    try:return rule.resolve(w)(state)
    finally:state._soh_age[w.player]=old

try:
    if args.group=='capabilities':
        mw=setup(1416,overrides={'shuffle_roll':True});w=mw.worlds[1];b=(Regions.ROOT,w)
        full=snapshot(mw,w)
        check('full inventory remains globally accessible', [l.name for l in w.get_locations() if not l.can_reach(full)], [])
        strength=SOH_ITEM_ALIASES['Strength Upgrade'][0]
        for label,helper,item in [('Grab',can_grab,strength),('Climb',can_climb,'Climb'),('Crawl',can_crawl,'Crawl'),('Swim',can_swim,'Progressive Scale')]:
            s=bare(mw,w,[])
            check(label+' missing blocks action',eval_rule(helper(b),w,s),False)
            s.collect(w.create_item(item),True)
            check(label+' first physical item grants action',eval_rule(helper(b),w,s))
            s.remove(w.create_item(item))
            check(label+' removal invalidates action',eval_rule(helper(b),w,s),False)
        # Positive and negative action tests: existence never supplies a method.
        cases=[
          ('pot soul only',can_break_pots,['Pot Soul'],False),
          ('pot + Grab',can_break_pots,['Pot Soul',strength],True),
          ('pot + bombs without Grab',can_break_pots,['Pot Soul','Progressive Bomb Bag'],True),
          ('pot + child sword without Grab',can_break_pots,['Pot Soul','Kokiri Sword'],True),
          ('pot + child boomerang without Grab',can_break_pots,['Pot Soul','Boomerang'],True),
          ('pot method without soul',can_break_pots,[strength,'Progressive Bomb Bag','Kokiri Sword'],False),
          ('fixed crate soul only',can_break_crates,['Crate Soul'],False),
          ('fixed crate Grab alone is not a break',can_break_crates,['Crate Soul',strength],False),
          ('fixed crate Roll',can_break_crates,['Crate Soul','Roll'],True),
          ('fixed crate bombs without Roll',can_break_crates,['Crate Soul','Progressive Bomb Bag'],True),
          ('fixed crate no soul',can_break_crates,['Roll','Progressive Bomb Bag'],False),
          ('small crate soul only',can_break_small_crates,['Crate Soul'],False),
          ('small crate lift',can_break_small_crates,['Crate Soul',strength],True),
          ('small crate sword without Roll',can_break_small_crates,['Crate Soul','Kokiri Sword'],True),
          ('tree soul without Roll',can_bonk_trees,['Tree Soul'],False),
          ('tree + Roll',can_bonk_trees,['Tree Soul','Roll'],True),
          ('tree cannot use bombs instead of Roll',can_bonk_trees,['Tree Soul','Progressive Bomb Bag'],False),
          ('tree no soul',can_bonk_trees,['Roll'],False),
          ('grass soul only',can_cut_shrubs,['Grass / Bush Soul'],False),
          ('grass bomb cut without Grab',can_cut_shrubs,['Grass / Bush Soul','Progressive Bomb Bag'],True),
          ('grass sword cut without Grab',can_cut_shrubs,['Grass / Bush Soul','Kokiri Sword'],True),
          ('grass cutting method without soul',can_cut_shrubs,['Progressive Bomb Bag','Kokiri Sword'],False),
          ('low hive bombs without soul',can_break_lower_hives,['Progressive Bomb Bag'],False),
          ('low hive bombs plus soul',can_break_lower_hives,['Progressive Bomb Bag','Beehive Soul'],True),
          ('upper hive boomerang without soul',can_break_upper_beehives,['Boomerang'],False),
          ('upper hive boomerang plus soul',can_break_upper_beehives,['Boomerang','Beehive Soul'],True),
        ]
        for name,helper,names,want in cases:check(name,eval_rule(helper(b),w,bare(mw,w,names)),want)
        for language in ('Deku','Gerudo','Goron','Hylian','Kokiri','Zora'):
            for soul,speech in itertools.product([False,True],repeat=2):
                names=(['NPC Soul'] if soul else [])+([f'Speak {language}'] if speech else [])
                check(f'NPC {language} existence={soul} speech={speech}',eval_rule(can_interact_npc(b,language),w,bare(mw,w,names)),soul and speech)
            other='Goron' if language!='Goron' else 'Hylian'
            check(f'NPC {language} rejects wrong language',eval_rule(can_interact_npc(b,language),w,bare(mw,w,['NPC Soul','Speak '+other])),False)
        # All labelled locations, including reserved shop events, not selected examples.
        tags=[('pots',LocTag.Pot,'Pot Soul'),('crates',LocTag.Crate,'Crate Soul'),('trees',LocTag.Tree,'Tree Soul'),('grass',LocTag.Overworld_Grass|LocTag.Grotto_Grass|LocTag.Dungeon_Grass,'Grass / Bush Soul'),('hives',LocTag.Bee_Hive,'Beehive Soul')]
        for label,tag,soul in tags:
            locs=[l for l in w.get_locations() if (d:=location_data_table.get(l.name)) is not None and d.tags and d.tags & tag]
            state=snapshot(mw,w,{soul});coverage[label]=len(locs)
            check(label+' metadata coverage exists',bool(locs))
            check(label+' every tagged check rejects missing soul',[l.name for l in locs if l.can_reach(state)],[])
        npc_tag=LocTag.Scrub|LocTag.Shop|LocTag.Merchant|LocTag.Trade_Location|LocTag.Shooting_Minigame|LocTag.House_of_Skulltula_Reward
        npcs=[l for l in w.get_locations() if (d:=location_data_table.get(l.name)) is not None and d.tags and d.tags & npc_tag]
        no_npc=snapshot(mw,w,{'NPC Soul'});no_talk=snapshot(mw,w,{'Speak',*[f'Speak {x}' for x in ('Deku','Gerudo','Goron','Hylian','Kokiri','Zora')]})
        coverage['tagged_npc_locations']=len(npcs)
        check('all tagged NPC interactions require NPC Soul',[l.name for l in npcs if l.can_reach(no_npc)],[])
        check('all tagged NPC interactions require language',[l.name for l in npcs if l.can_reach(no_talk)],[])
        for lang in set(w._extreme_native_interactions.values()):
            locs=[w.get_location(n) for n,l in w._extreme_native_interactions.items() if l==lang]
            s=snapshot(mw,w,{'Speak '+lang,'Speak'})
            check('exact '+lang+' locations cannot substitute another language',[l.name for l in locs if l.can_reach(s)],[])
        coverage['exact_language_locations']=len(w._extreme_native_interactions)
        speeches=[l for l in w.get_locations() if l.name.startswith('NPC Speech:')]
        coverage['first_talk_checks']=len(speeches)
        check('every first-talk check needs NPC Soul',[l.name for l in speeches if l.can_reach(no_npc)],[])
        check('every first-talk check needs speech',[l.name for l in speeches if l.can_reach(no_talk)],[])
        check('Skip Zelda automatic Impa reward remains free',w.get_location('Song from Impa').can_reach(bare(mw,w,[])))
        no_grab=snapshot(mw,w,{'Grab / Power Bracelet',*SOH_ITEM_ALIASES['Strength Upgrade']})
        for region in (Regions.GRAVEYARD_SHIELD_GRAVE,Regions.GRAVEYARD_HEART_PIECE_GRAVE,Regions.GRAVEYARD_DAMPES_GRAVE,Regions.ICE_CAVERN_BEFORE_FINAL_ROOM):
            check('Grab blocks '+region,w.get_region(region).can_reach(no_grab),False)
        for tier in (Items.GORONS_BRACELET,Items.SILVER_GAUNTLETS,Items.GOLDEN_GAUNTLETS):
            # Raw legacy strength state must not bypass the separate Grab ability.
            s=remove_all(full.copy(),w,['Grab / Power Bracelet'])
            check('strength requires Grab: '+str(tier),eval_rule(has_item(tier,b),w,s),False)
        no_swim=snapshot(mw,w,{'Swim','Progressive Scale'})
        check('boots do not permit swimming rule',eval_rule(can_use(Items.IRON_BOOTS,b),w,no_swim,Ages.ADULT),False)
        check('Zora Tunic cannot supply underwater access',eval_rule(water_timer_at_least(b,8),w,no_swim,Ages.ADULT),False)
        no_climb=snapshot(mw,w,{'Climb','Progressive Hookshot'})
        check('Deku 2F no ladder/vine ability',w.get_region('Deku Tree Lobby 2F').can_reach(no_climb),False)
        no_crawl=snapshot(mw,w,{'Crawl'})
        check('Kokiri crawlspace chest requires Crawl',w.get_location('KF Kokiri Sword Chest').can_reach(no_crawl),False)
        for rule in [RequireAnyItemGroups(((('Climb',1),('THIS_ITEM_DOES_NOT_EXIST',1)),)),RequireAnyExistingItems(('THIS_ITEM_DOES_NOT_EXIST',))]:
            try:rule.resolve(w);raised=False
            except OptionError:raised=True
            check('unknown physical requirement fails closed '+type(rule).__name__,raised)
    elif args.group=='enemy-modes':
        for mode in (0,1,2):
            mw=setup(1417,overrides={'shuffle_enemy_soul':mode});w=mw.worlds[1];full=snapshot(mw,w)
            check(f'enemy mode {mode} full inventory',[e.name for e in ENEMY_DROP_LOCATIONS if not w.get_location(e.name).can_reach(full)],[])
            nonspiders=[e for e in ENEMY_DROP_LOCATIONS if e.actor_id not in (0x037,0x095)]
            if mode==1:
                s=remove_all(full.copy(),w,['Enemy Soul'])
                check('combined: all eligible enemies need global soul',[e.name for e in nonspiders if w.get_location(e.name).can_reach(s)],[])
                s.collect(w.create_item('Enemy Soul'),True)
                check('combined: one global soul unlocks all eligible combat gates',[e.name for e in nonspiders if not w.get_location(e.name).can_reach(s)],[])
            if mode==2:
                for soul in sorted({e.soul_item for e in nonspiders}):
                    s=remove_all(full.copy(),w,[soul]);s.collect(w.create_item('Enemy Soul'),True)
                    group=[e for e in nonspiders if e.soul_item==soul]
                    check('individual: global soul cannot replace '+soul,[e.name for e in group if w.get_location(e.name).can_reach(s)],[])
                coverage['individual_enemy_checks']=len(nonspiders)
                coverage['individual_enemy_soul_groups']=len({e.soul_item for e in nonspiders})
            if mode==0:
                s=remove_all(full.copy(),w,['Enemy Soul',*[e.soul_item for e in nonspiders]])
                check('disabled: no enemy-soul demand',[e.name for e in nonspiders if not w.get_location(e.name).can_reach(s)],[])
    else:
        for start in ('day','night'):
            mw=setup(1418,overrides={'frozen_starting_time':start,'skulls_sun_song':False});w=mw.worlds[1];b=(Regions.HYRULE_FIELD,w)
            s=snapshot(mw,w,{'Flow of Time'})
            check(start+' frozen day helper',eval_rule(at_day(b),w,s),start=='day')
            check(start+' frozen night helper',eval_rule(at_night(b),w,s),start=='night')
            s.collect(w.create_item('Flow of Time'),True);s.sweep_for_advancements([l for l in mw.get_filled_locations() if l.address is None])
            check(start+' unlock permits day',eval_rule(at_day(b),w,s))
            check(start+' unlock permits night',eval_rule(at_night(b),w,s))
            # Evaluate physical drawbridge edge per age without allowing an
            # already-reached adult/Temple route to disguise the child approach.
            edge=next(e for e in w.get_region('Hyrule Field').exits if e.connected_region.name=='Market Entrance')
            f=snapshot(mw,w,{'Flow of Time'})
            for age in (Ages.CHILD,Ages.ADULT):
                old=f._soh_age[1];f._soh_age[1]=age
                actual=edge.access_rule(f);f._soh_age[1]=old
                check(start+' drawbridge '+str(age),actual,start=='day' or age==Ages.ADULT)
            # Ordinary indoor GS are not time-of-day gates.
            check(start+' no universal Flow requirement on Deku lobby GS',w.get_location('Deku Tree GS Basement Back Room').can_reach(f))
except Exception as e:
    traceback.print_exc();results.append(dict(name='unhandled capability test error',passed=False,error=repr(e),traceback=traceback.format_exc()))
report=dict(group=args.group,total=len(results),failures=sum(not r['passed'] for r in results),checks=results,coverage=coverage,
 scope='Real AP 0.6.7 graph, collection/cache and rules; no game physics or UI. Restricted offline dependency adapters only.')
args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2));print('TOTAL',report['total'],'FAILURES',report['failures'],flush=True)
raise SystemExit(bool(report['failures']))
