"""First traversal of physical scene portals and dungeon room doors.

The catalogue is shared with the native client. A directed crossing inherits
the fully resolved source entrance rule, after all ability/key/soul overlays.
Reaching a destination through some other entrance does not check this one.
"""
import json
from importlib.resources import files
from Options import OptionError
from ._vendor_oot_soh import LogicHelpers as H
from ._vendor_oot_soh.Enums import Regions, Items
from ._vendor_oot_soh.Locations import SohLocation

CATALOG_VERSION = 2
CATALOG = tuple(e for filename in ('SceneTransitionCatalog.json','DungeonDoorCatalog.json')
                for e in json.loads(files(__package__).joinpath(filename).read_text(encoding='utf-8')))
NAME_TO_ID = {e['name']: e['id'] for e in CATALOG}

def active_entries(world):
    if not world.options.scene_transition_checks.value:
        return ()
    if world.using_ut:
        # Old servers have no locations for this feature, regardless of local
        # YAML defaults. The slot manifest is authoritative on regeneration.
        ids=set(world.passthrough.get('extreme_active_locations',()))
        return tuple(e for e in CATALOG if e['id'] in ids)
    # Triforce Hunt removes Ganon's boss key from the pool and ends at the
    # collection goal. Do not place checks behind its permanently locked door.
    hunt=bool(world.options.triforce_hunt.value)
    pots=world.options.shuffle_pots.value in (1,3)
    return tuple(e for e in CATALOG if not (hunt and (
        e.get('requires_final_ganon_key') or e['index']=='ENTR_GANONDORF_BOSS_0' or
        (e['mode']=='door' and e['source_scene']==10 and (e['door']==8 or (e['door'] in (6,7) and not pots))))))

def create_locations(world):
    world._scene_transition_entries=active_entries(world)
    for entry in world._scene_transition_entries:
        source=world.get_region(region_name(entry['source']))
        source.locations.append(SohLocation(world.player,entry['name'],entry['id'],source))

def region_name(key):
    if key.startswith('RR_'):
        from .EnemyRoomLogic import NativeEnemyRegions
        return str(NativeEnemyRegions[key])
    return str(Regions[key])

def install_rules(world):
    errors=[]
    for entry in world._scene_transition_entries:
        source=world.get_region(region_name(entry['source']))
        target=region_name(entry['target'])
        location=world.get_location(entry['name'])
        if 'traversal_rule' in entry:
            from rule_builder.rules import True_
            bundle=(Regions[entry['source']],world)
            world.set_rule(location,H.at_day(bundle) if entry['traversal_rule']=='day' else True_())
            continue
        if 'condition' in entry:
            world.set_rule(location,world._extreme_room_compiler.expr(entry['condition'],entry['source']))
            continue
        exits=[e for e in source.exits if e.connected_region and e.connected_region.name==target]
        if len(exits)!=1:
            errors.append(f"{entry['index']}: {source.name} -> {target} ({len(exits)})")
            continue
        location.access_rule=exits[0].access_rule
        early_pot_door=(entry['mode']=='door' and entry['source_scene']==10 and
                        entry['door'] in (6,7) and world.options.shuffle_pots.value in (1,3))
        if 'extra_condition' in entry and not early_pot_door:
            from rule_builder.rules import And
            extra=world._extreme_room_compiler.expr(entry['extra_condition'],entry['source']).resolve(world)
            location.access_rule=And.Resolved((location.access_rule,extra),player=world.player)
        if entry.get('gate')=='swim':
            from rule_builder.rules import And
            location.access_rule=And.Resolved((location.access_rule,H.can_swim((Regions[entry['source']],world)).resolve(world)),player=world.player)
        if entry.get('gate')=='horse':
            from rule_builder.rules import And
            location.access_rule=And.Resolved((location.access_rule,H.can_use(Items.EPONA,(Regions[entry['source']],world)).resolve(world)),player=world.player)

    if errors:raise OptionError("Unmapped physical portals: "+"; ".join(errors))
