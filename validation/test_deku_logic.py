"""Real AP rules and game-owned tracker callbacks for shields/Withered Babas.

Uses AP 0.6.7 and controlled network services, without a connected game.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState, ItemClassification
from worlds.soh_extreme._vendor_oot_soh.Enums import Items, Regions, Enemies
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import can_use, can_kill_enemy, can_reflect_nuts
from worlds.soh_extreme.EnemyDropLocations import ENEMY_DROP_LOCATIONS
from worlds.soh_extreme.TrackerClient import make_context_class
from worlds.soh_extreme.TrackerMirror import PROTOCOL, encode_snapshot
from pathlib import Path
from types import SimpleNamespace as NS
import argparse, asyncio, json, subprocess, ast, logging, collections, hashlib

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--report', type=Path, required=True)
p.add_argument('--native-exe', type=Path)
p.add_argument('--ut-core', type=Path, help='Optional installed TrackerCore.py for its actual evaluator')
a = p.parse_args()
a.report.parent.mkdir(parents=True, exist_ok=True)
checks = []
def ck(name, actual, expected=True):
    row = dict(test=name, actual=actual, expected=expected, passed=actual == expected)
    checks.append(row)
    if not row['passed']: raise AssertionError(row)

m = setup(290906, overrides={'boss_key_shuffle': 'anywhere'})
w = m.worlds[1]
bundle = (Regions.KOKIRI_FOREST, w)
weapons = {'Kokiri Sword', 'Master Sword', 'Biggoron Sword', 'Progressive Goron Sword',
           'Megaton Hammer', 'Boomerang', 'Progressive Slingshot', 'Progressive Bow',
           'Progressive Hookshot', 'Bomb Bag', 'Progressive Bombchus', "Din's Fire"}
weapons |= {n for n in w.item_name_to_id if any(t in n.lower() for t in ('sword', 'knife', 'hammer', 'boomerang', 'slingshot', 'bow', 'hookshot', 'bomb', 'arrow'))}

def inventory(*, missing=(), weapon=None, live=None, child_only=False):
    w._extreme_live_shields = live
    s = CollectionState(m)
    for name in w.item_name_to_id:
        if name in missing: continue
        if child_only and any(word in name for word in ('Time Travel', 'Ocarina')): continue
        if weapon is not None and name in weapons and name != weapon: continue
        for _ in range(100 if 'Gold Skulltula Token' == name else 10): s.collect(w.create_item(name), True)
    s.sweep_for_advancements()
    return s

slingshot = ['Deku Tree Slingshot Chest', 'Deku Tree Slingshot Room Side Chest']
scrub = 'Enemy Defeat: Deku Tree Room 1 Deku Scrub 1'
missing = {'Deku Shield', 'Hylian Shield', 'Megaton Hammer'}
for owned, expected in [(None, True), (0, False), (1, True), (2, False), (3, True), (0, False)]:
    s = inventory(missing=missing, live=owned, child_only=True)
    ck(f'stock shield purchase still logically reachable {owned}', s.has(Items.BUY_DEKU_SHIELD, 1))
    for name in [*slingshot, scrub]:
        ck(f'child owned={owned}: {name}', w.get_location(name).can_reach(s), expected)
# AP receipt history must not substitute for a burned/stolen shield.
s = inventory(missing={'Megaton Hammer'}, live=0, child_only=True)
historical_shield=w.create_item(Items.DEKU_SHIELD)
historical_shield.classification |= ItemClassification.progression
s.collect(historical_shield, True)
ck('received shield exists in historical state', s.has(Items.DEKU_SHIELD, 1))
ck('lost shield blocks slingshot route despite receipt', w.get_location(slingshot[0]).can_reach(s), False)
# Adult Hylian reflection and hammer traversal remain valid alternatives.
s = inventory(missing=missing, live=2)
ck('adult Hylian shield reflects nuts in an adult-accessible region', can_reflect_nuts(bundle).resolve(w)(s))
s = inventory(missing={'Deku Shield', 'Hylian Shield'}, live=0)
ck('hammer remains usable without shields', can_use(Items.MEGATON_HAMMER, bundle).resolve(w)(s))

withered = [e for e in ENEMY_DROP_LOCATIONS if e.actor_id == 199]
regular = next(e for e in ENEMY_DROP_LOCATIONS if e.address == 9800003)
ck('all ten Withered Baba combat tags', len(withered), 10)
ck('dedicated combat tag', all(e.combat == 'sword_or_boomerang' for e in withered))
for weapon, expected in [('none', False), ('Kokiri Sword', True), ('Boomerang', True),
                          ('Megaton Hammer', False), ('Progressive Slingshot', False),
                          ('Progressive Bow', False), ('Bomb Bag', False)]:
    s = inventory(weapon=weapon)
    ck('sticks usable in weapon scenario '+weapon, can_use(Items.STICKS, bundle).resolve(w)(s))
    ck('Withered helper with '+weapon, can_kill_enemy(bundle, Enemies.WITHERED_DEKU_BABA).resolve(w)(s), expected)
    for e in withered:
        if e.region_token == 'KF_OUTSIDE_DEKU_TREE':
            ck(f'{e.address} with {weapon}', w.get_location(e.name).can_reach(s), expected)
    ck('ordinary Baba still killable with sticks: '+weapon, w.get_location(regular.name).can_reach(s))
s = inventory(weapon='Kokiri Sword', missing={'Deku Baba Soul'})
for e in withered:
    ck('missing Baba Soul '+str(e.address), w.get_location(e.name).can_reach(s), False)

# Exercise the actual tracker wrapper; only upstream display/network services are
# controlled. Every evaluation rebuilds real AP CollectionState like UT does.
active = {l.address for l in w.get_locations() if type(l.address) is int}
ut_evaluate = None
if a.ut_core:
    from BaseClasses import LocationProgressType
    tree=ast.parse(a.ut_core.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='TrackerCore')
    update=next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='updateTracker')
    scope=dict(CollectionState=CollectionState, Counter=collections.Counter,
               LocationProgressType=LocationProgressType, ItemClassification=ItemClassification,
               DeferredEntranceMode=NS(disabled='disabled'),
               CurrentTrackerState=collections.namedtuple('TrackerState',
                   'all_items prog_items glitched_locations events event_locations in_logic_locations regions unconnected readable hinted state glitches_state'),
               TrackerLogLine=lambda *args: args,
               TrackerLogLineGroup=NS(**{n:n for n in ('UT_ERROR','DEFAULT','HINTED','EXCLUDED','EXCLUDED_GLITCHED','HINTED_GLITCHED','GLITCHED','UNCONNECTED','UT_STATUS')}))
    exec(compile(ast.Module(body=[update],type_ignores=[]),str(a.ut_core),'exec'),scope)
    ut_evaluate=scope['updateTracker']

class Host:
    tags = {'AP', 'Tracker'}
    def __init__(self):
        self.game='SOH-EXTREME'; self.slot=1; self.server_locations=active
        self.checked_locations=set(); self.tracker_items_received=[]; self.sent=[]; self.calls=0
        self.tracker_core=NS(get_current_world=lambda: w, manual_items=[], ignored_locations=set(),
                             enable_glitched_logic=False, location_alias_map={})
        if ut_evaluate:
            self.tracker_items_received=[NS(item=w.item_name_to_id[name],flags=0,location=-1,player=1)
                for name in w.item_name_to_id if name not in missing and not any(t in name for t in ('Time Travel','Ocarina'))
                for _ in range(100 if name=='Gold Skulltula Token' else 10)]
            core=self.tracker_core
            core.tracker_disabled=False; core.player_id=1; core.multiworld=m; core.slot=1
            core.enforce_deferred_connections='disabled'; core.tracker_items_received=self.tracker_items_received
            core.hide_excluded=False; core.missing_locations=active; core.hints={}
            core.logger=logging.getLogger('Deku test')
            for method in ('clear_page','add_log_line','sort_log_lines','log_all_to_tab'):
                setattr(core, method, lambda *args: None)
            core.get_readable_locations=lambda: {}
    def on_package(self, cmd, args): pass
    def updateTracker(self):
        self.calls += 1
        if ut_evaluate: return ut_evaluate(self.tracker_core)
        s = inventory(missing=missing, live=w._extreme_live_shields, child_only=True)
        return NS(state=s, in_logic_locations=[l.name for l in w.get_locations()
                  if l.address in active and l.can_reach(s)], glitched_locations=[])
    async def send_msgs(self, packets): self.sent.extend(packets)
    async def disconnect(self, allow_autoreconnect=False): pass

async def callbacks():
    ctx = make_context_class(Host)(); ctx._managed_nonce='a'*32
    for seq, owned in enumerate([0, 1, 0, 2, 3], 1):
        ctx._mirror_last_request_time=0
        request=dict(soh_extreme_tracker=PROTOCOL, kind='request', slot=1,
                     nonce='a'*32, request=seq, live_shields=owned)
        ctx.on_package('Bounced', {'data': request}); await asyncio.sleep(0)
        ck(f'live callback equipment {seq}', w._extreme_live_shields, owned)
        ck(f'callback refresh count {seq}', ctx.calls, seq)
        ck(f'callback slingshot readiness {seq}', slingshot[0] in ctx._mirror_last_state.in_logic_locations, bool(owned & 1))
        if a.native_exe:
            f=a.report.parent/f'shields-{seq}.b64'; f.write_text(ctx.sent[-1]['data']['payload'])
            run=subprocess.run([str(a.native_exe), str(f), str(owned)], capture_output=True, text=True)
            ck(f'production C++ client consumes callback {seq}: '+run.stdout+run.stderr, run.returncode, 0)
    previous = ctx.calls
    for bad in (None, -1, 4, True, '1'):
        ctx._mirror_last_request_time=0
        ctx.on_package('Bounced', {'data':dict(request, live_shields=bad, request=99)})
        ck('reject invalid live shield '+repr(bad), ctx.calls, previous)
    for change in ({'slot': 2}, {'nonce': 'b'*32}, {'request': 1}):
        ctx._mirror_last_request_time=0
        ctx.on_package('Bounced', {'data':dict(request, **change)})
        ck('reject foreign/stale request '+repr(change), ctx.calls, previous)
    await ctx.disconnect()
    ck('disconnect clears live shield override', w._extreme_live_shields, None)
    # A standalone tracker must retain its generation/purchase semantics.
    standalone=make_context_class(Host)()
    standalone.on_package('Bounced', {'data':dict(request, request=1, live_shields=0)})
    await asyncio.sleep(0)
    ck('standalone tracker ignores live equipment input', w._extreme_live_shields, None)
    ck('standalone can plan a stock shield purchase', slingshot[0] in standalone._mirror_last_state.in_logic_locations)
    await standalone.disconnect()

asyncio.run(callbacks())
full=inventory()
ck('all network checks reachable with full inventory',
   [l.name for l in w.get_locations() if l.address is not None and not l.can_reach(full)], [])
a.report.write_text(json.dumps(dict(passed=True, checks=len(checks), tests=checks,
    evaluator='Installed UT TrackerCore.updateTracker with controlled display/network services' if ut_evaluate else 'Controlled UT host',
    ut_source_sha256=hashlib.sha256(a.ut_core.read_bytes()).hexdigest() if a.ut_core else None), indent=2))
print(f'PASS {len(checks)} Deku logic/transport checks')
