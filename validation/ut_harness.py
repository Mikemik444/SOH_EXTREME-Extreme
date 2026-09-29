"""Load the installed UT evaluator with controlled display/network services."""
import ast, collections, logging
from types import SimpleNamespace as NS
from BaseClasses import CollectionState, ItemClassification, LocationProgressType

def tracker(world, source):
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TrackerCore')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'updateTracker')
    scope = dict(CollectionState=CollectionState, Counter=collections.Counter,
        LocationProgressType=LocationProgressType, ItemClassification=ItemClassification,
        DeferredEntranceMode=NS(disabled='disabled'),
        CurrentTrackerState=collections.namedtuple('TrackerState',
            'all_items prog_items glitched_locations events event_locations in_logic_locations regions unconnected readable hinted state glitches_state'),
        TrackerLogLine=lambda *args: args,
        TrackerLogLineGroup=NS(**{n:n for n in ('UT_ERROR','DEFAULT','HINTED','EXCLUDED','EXCLUDED_GLITCHED','HINTED_GLITCHED','GLITCHED','UNCONNECTED','UT_STATUS')}))
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), scope)
    core = NS(game=world.game, tracker_disabled=False, player_id=1, multiworld=world.multiworld, slot=1,
        manual_items=[], ignored_locations=set(), enable_glitched_logic=False, location_alias_map={},
        enforce_deferred_connections='disabled', hide_excluded=False,
        missing_locations={l.address for l in world.get_locations() if type(l.address) is int},
        hints={}, logger=logging.getLogger('UT regression'), get_readable_locations=lambda: {})
    for name in ('clear_page','add_log_line','sort_log_lines','log_all_to_tab'):
        setattr(core, name, lambda *args: None)
    def evaluate(names):
        core.tracker_items_received = [NS(item=world.item_name_to_id[n], flags=0, location=-1, player=1) for n in names]
        return scope['updateTracker'](core)
    return evaluate
