"""Offline targeted tracker tests using real TrackerMirror (AP runtime not bundled)."""
import importlib.util,sys,types
from pathlib import Path
p=Path('/mnt/data/scene_all_missing_work/soh_extreme/TrackerMirror.py')
root=types.ModuleType('soh_extreme');root.__path__=[str(p.parent)];sys.modules['soh_extreme']=root
npc=types.ModuleType('soh_extreme.NpcSpeech');npc.display_region=lambda loc:loc.parent_region.name;sys.modules[npc.__name__]=npc
spec=importlib.util.spec_from_file_location('soh_extreme.TrackerMirror',p);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
class State:
    def __init__(self,access):self.access=access;self.stale={1:False};self.reachable_regions={1:{'stale'}};self.blocked_connections={1:{'old'}};self.invalidated=False
    def copy(self):return State(self.access)
    def _soh_extreme_invalidate(self,player):self.invalidated=True
class Location:
    def __init__(self,name,id,region,age):self.name=name;self.address=id;self.parent_region=types.SimpleNamespace(name=region);self.transition_age=age
    def can_reach(self,state):
        assert state.invalidated and state.stale[1] and not state.reachable_regions[1] and not state.blocked_connections[1]
        return state.access.get(self.address,False)
class Core:enable_glitched_logic=False;location_alias_map={}
class TrackerState:
    def __init__(self,state,names=()):self.state=state;self.glitches_state=None;self.in_logic_locations=list(names);self.glitched_locations=[]
class World:
    def __init__(self):
        self.player=1
        self.locs={
            'Portal [Child]':Location('Portal [Child]',31000010,'Fountain',0),
            'Portal [Adult]':Location('Portal [Adult]',51000010,'Fountain',1),
        }
        self._scene_transition_entries=[dict(id=loc.address,name=name) for name,loc in self.locs.items()]
        self._er_labels={31000010:'Fountain Door [Child]',51000010:'Fountain Door [Adult]'}
    def get_location(self,name):return self.locs[name]
w=World();c=Core()
state=TrackerState(State({31000010:True,51000010:False}))
r=m.snapshot_rows(c,state,w,{31000010,51000010},set())
assert [(x['id'],x['name'],x['region']) for x in r]==[(31000010,'Fountain Door [Child]','Fountain')],r
# A confirmed check is not shown again; a non-server location is not invented.
assert not m.snapshot_rows(c,state,w,{31000010}, {31000010})
assert not m.snapshot_rows(c,state,w,set(),set())
# Normal UT rows are preserved without duplication, and adult is independently gated.
state2=TrackerState(State({31000010:True,51000010:True}),['Portal [Child]'])
r=m.snapshot_rows(c,state2,w,{31000010,51000010},set())
assert sorted(x['id'] for x in r)==[31000010,51000010],r
assert len(r)==2,r
# No need for an available fallback state: compatibility with old tracker core.
assert not m.snapshot_rows(c,TrackerState(None),w,{31000010},set())
print('PASS: age-dependent transition fallback, source reachability, seed manifest, confirmed-check and duplicate guards')
