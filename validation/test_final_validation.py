"""Exercise final validation with real AP collection and cross-player delivery.

Small synthetic worlds deliberately inject unreachable goals, self locks,
unreachable Full checks and a late placement change. No runtime simulation.
"""
from run_case import BOOTSTRAP
from BaseClasses import MultiWorld, CollectionState, Region, Location, Item, ItemClassification
from worlds.AutoWorld import World
from worlds.soh_extreme import SohExtremeWorld
from Fill import FillError
from types import SimpleNamespace
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--report', type=Path, required=True)
a = p.parse_args()
tests = []

def world(players=1, full=True):
    m = MultiWorld(players)
    m.set_seed(290970)
    m.player_name = {}
    for player in m.player_ids:
        m.game[player] = 'SOH-EXTREME' if player == 1 else 'TestRemote'
        m.player_name[player] = f'Tester{player}'
        w = World(m, player)
        w.game = m.game[player]
        w.options = SimpleNamespace(starting_hearts=SimpleNamespace(value=3),
            accessibility=SimpleNamespace(current_key='full' if full and player == 1 else 'minimal'))
        m.worlds[player] = w
        m.regions.append(Region('Menu', player, m))
        m.completion_condition[player] = lambda state, p=player: state.has('Victory', p)
    m.state = CollectionState(m)
    return m

def location(m, player, name, item, recipient=None, rule=lambda s: True, event=False, filler=False):
    r = m.get_region('Menu', player)
    loc = Location(player, name, None if event else 100+len(m.get_locations()), r)
    loc.access_rule = rule
    r.locations.append(loc)
    if item is not None:
        it = Item(item, ItemClassification.filler if filler else ItemClassification.progression,
                  None if event else 1, recipient or player)
        loc.place_locked_item(it)
    return loc

def expect(name, m, passes, message=None):
    try:
        SohExtremeWorld.stage_pre_output(m)
    except FillError as e:
        assert not passes, (name, str(e))
        assert message is None or message in str(e), (name, str(e))
    else:
        assert passes, name + ' was incorrectly accepted'
        assert m._soh_final_validation['passed']
    tests.append(name)

m=world(); location(m,1,'Start','Victory'); expect('single player reachable goal',m,True)
m=world(); location(m,1,'Locked Climb','Climb',rule=lambda s:s.has('Climb',1))
location(m,1,'Goal','Victory',rule=lambda s:s.has('Climb',1))
expect('self-locked Climb cannot bootstrap',m,False,'unreachable goal')
m=world(2); location(m,1,'Remote key','Key',2,lambda s:s.has('Key',1))
location(m,2,'SOH key','Key',1,lambda s:s.has('Key',2))
for player in m.player_ids: location(m,player,'Goal','Victory',rule=lambda s,p=player:s.has('Key',p))
expect('cross-game circular dependency rejected',m,False,'unreachable goal')
m=world(2); location(m,1,'Remote key','Key',2)
location(m,2,'SOH key','Key',1,lambda s:s.has('Key',2))
for player in m.player_ids: location(m,player,'Goal','Victory',rule=lambda s,p=player:s.has('Key',p))
expect('earned cross-game deliveries succeed',m,True)
m=world(2); location(m,1,'Goal','Victory'); location(m,2,'Goal','Victory')
location(m,1,'Unreachable filler','Rupee',rule=lambda s:False,filler=True)
expect('multiplayer Full rejects unreachable filler despite victory',m,False,'Full-accessibility')
m=world(full=False); location(m,1,'Goal','Victory')
location(m,1,'Unreachable filler','Rupee',rule=lambda s:False,filler=True)
expect('Minimal permits unnecessary unreachable filler',m,True)
m=world(2); location(m,1,'Goal','Victory'); location(m,2,'Goal','Victory')
location(m,2,'Unused remote filler','Rupee',rule=lambda s:False,filler=True)
expect('other game Minimal is preserved',m,True)
m=world(2); location(m,1,'Goal','Victory'); location(m,2,'Goal','Victory')
location(m,2,'Remote SOH progression','Climb',1,lambda s:False)
expect('Full SOH progression in another game must be reachable',m,False,'Full-accessibility')
m=world(); location(m,1,'Unfilled',None); location(m,1,'Goal','Victory')
expect('unfilled network check rejected',m,False,'unfilled checks')
m=world(); key=location(m,1,'Start','Key')
location(m,1,'Goal','Victory',rule=lambda s:s.has('Key',1))
expect('valid before final placement change',m,True)
key.access_rule=lambda s:s.has('Key',1)
expect('late mutation is revalidated without cached success',m,False,'unreachable goal')
m=world(); location(m,1,'One piece','Piece',event=True)
location(m,1,'Goal needs two','Victory',rule=lambda s:s.has('Piece',1,2))
expect('one event cannot count as two receipts',m,False,'unreachable goal')
m=world(); m.push_precollected(Item('Key',ItemClassification.progression,1,1))
location(m,1,'Goal','Victory',rule=lambda s:s.has('Key',1))
expect('actual precollected items count',m,True)
a.report.write_text(json.dumps(dict(passed=True,tests=tests,assertions=len(tests)),indent=2))
print(f'PASS {len(tests)} final validation scenarios')
