from __future__ import annotations
import sys, time, json, random, traceback, argparse, os
from pathlib import Path
BOOTSTRAP = argparse.ArgumentParser(add_help=False)
BOOTSTRAP.add_argument('--ap-root', type=Path, default=Path(os.environ.get('AP_ROOT', '.')),
                       help='Archipelago 0.6.7 source directory')
BOOTSTRAP.add_argument('--yaml', type=Path, default=Path(__file__).with_name('SOH-EXTREME.yaml'))
BOOTSTRAP.add_argument('--offline-adapters', action='store_true',
                       help='Use restricted test-only adapters for unavailable schema/bsdiff4 dependencies')
BOOT_ARGS, _ = BOOTSTRAP.parse_known_args()
sys.path.insert(0, str(BOOT_ARGS.ap_root.resolve()))
if BOOT_ARGS.offline_adapters:
    import offline_bootstrap
import yaml
from BaseClasses import MultiWorld, CollectionState
from worlds.AutoWorld import call_all
from worlds.soh_extreme import SohExtremeWorld
from Fill import distribute_items_restrictive
from Generate import roll_settings
from NetUtils import convert_to_base_types

YAML_PATH = BOOT_ARGS.yaml

def setup(seed=1001, players=1, overrides=None, stop_before=None, passthrough=None):
    random.seed(seed)
    weights=yaml.safe_load(Path(YAML_PATH).read_text())
    if overrides: weights['SOH-EXTREME'].update(overrides)
    rolls=[roll_settings(weights) for _ in range(players)]
    multiworld=MultiWorld(players)
    multiworld.game={p:SohExtremeWorld.game for p in multiworld.player_ids}
    multiworld.player_name={p:f'Tester{p}' for p in multiworld.player_ids}
    multiworld.set_seed(seed)
    multiworld.seed_name=str(seed)
    if passthrough is not None: multiworld.re_gen_passthrough={SohExtremeWorld.game:passthrough}
    options=argparse.Namespace()
    for name in SohExtremeWorld.options_dataclass.type_hints:
        setattr(options,name,{p:getattr(rolls[p-1],name) for p in multiworld.player_ids})
    multiworld.set_options(options)
    multiworld.state=CollectionState(multiworld)
    for step in ('generate_early','create_regions','create_items','set_rules','connect_entrances','generate_basic','pre_fill'):
        if step==stop_before: break
        t=time.monotonic()
        print('STAGE',seed,step,flush=True)
        # These two phases follow supplied Main.py, not custom world behavior.
        # The normal test YAML has empty common inventory; dedicated tests below
        # exercise both common starting-item paths and actual pool depletion.
        if step == 'pre_fill':
            depletion={p:multiworld.worlds[p].options.start_inventory_from_pool.value.copy()
                       for p in multiworld.player_ids}
            replaced={p:0 for p in multiworld.player_ids}
            new_pool=[]
            for item in multiworld.itempool:
                if depletion[item.player].get(item.name,0):
                    depletion[item.player][item.name]-=1
                    replaced[item.player]+=1
                else:new_pool.append(item)
            for player,count in replaced.items():
                new_pool.extend(multiworld.worlds[player].create_filler() for _ in range(count))
            assert len(new_pool)==len(multiworld.itempool)
            multiworld.itempool[:]=new_pool
        call_all(multiworld,step)
        if step == 'generate_early':
            for player in multiworld.player_ids:
                world=multiworld.worlds[player]
                for option in (world.options.start_inventory,world.options.start_inventory_from_pool):
                    for name,count in option.value.items():
                        for _ in range(count):
                            multiworld.push_precollected(multiworld.create_item(name,player))
        print('DONE',step,round(time.monotonic()-t,3),flush=True)
    return multiworld

def main():
    args=argparse.ArgumentParser(parents=[BOOTSTRAP]); args.add_argument('--seed',type=int,default=1001); args.add_argument('--players',type=int,default=1); args.add_argument('--overrides',default='{}'); args.add_argument('--all-state-only',action='store_true'); args.add_argument('--report',required=True)
    a=args.parse_args(); Path(a.report).parent.mkdir(parents=True,exist_ok=True); result={'seed':a.seed,'players':a.players,'overrides':json.loads(a.overrides),'passed':False,'harness':('AP 0.6.7 core, restricted offline dependency adapters; no nonempty item links or binary patch export' if BOOT_ARGS.offline_adapters else 'AP 0.6.7 core with normal dependencies')}
    start=time.monotonic()
    try:
        mw=setup(a.seed,a.players,result['overrides'])
        all_state=mw.get_all_state(False)
        blocked=[(loc.player,loc.name) for loc in mw.get_locations() if not loc.can_reach(all_state)]
        result.update(locations=len(mw.get_locations()),
                      network_locations=sum(l.address is not None for l in mw.get_locations()),
                      pool=len(mw.itempool),all_state_blocked=blocked,
                      resolved_world_options={str(p):{
                          'frozen_starting_time':w.options.frozen_starting_time.value,
                          'boss_key_shuffle':w.options.boss_key_shuffle.current_key,
                          'triforce_hunt':w.options.triforce_hunt.value,
                      } for p,w in mw.worlds.items()})
        print('ALL_STATE',len(blocked),blocked[:30],flush=True)
        if blocked: raise AssertionError(f'{len(blocked)} locations blocked with all items')
        if not a.all_state_only:
            t=time.monotonic(); print('STAGE fill',flush=True)
            distribute_items_restrictive(mw)
            print('DONE fill',round(time.monotonic()-t,3),flush=True)
            call_all(mw,'post_fill'); call_all(mw,'finalize_multiworld')
            state=CollectionState(mw); remaining=set(mw.get_locations()); spheres=[]
            while remaining:
                remaining.difference_update(state.advancements)
                sphere={loc for loc in remaining if loc.can_reach(state)}
                if not sphere: break
                remaining.difference_update(sphere); spheres.append(len(sphere))
                for loc in sorted(sphere,key=lambda l:(l.player,l.name)):
                    if loc.item is not None and loc not in state.advancements: state.collect(loc.item,True,loc)
            result.update(sphere_sizes=spheres,replay_blocked=[(l.player,l.name) for l in remaining],beatable=mw.has_beaten_game(state))
            assert result['beatable'],'Goal not met'
            assert not remaining,'Full accessibility failed independent replay'
            for p,w in mw.worlds.items():
                slot=convert_to_base_types(w.fill_slot_data()); json.dumps(slot)
                Path(a.report+f'.slot{p}.json').write_text(json.dumps(slot))
        result['passed']=True
    except Exception as e:
        result['error']=repr(e); result['traceback']=traceback.format_exc(); traceback.print_exc()
    result['seconds']=round(time.monotonic()-start,3)
    Path(a.report).parent.mkdir(parents=True,exist_ok=True)
    Path(a.report).write_text(json.dumps(result,indent=2))
    print('RESULT',json.dumps(result),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__': raise SystemExit(main())
