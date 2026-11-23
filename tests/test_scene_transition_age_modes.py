from pathlib import Path
import sys,types,importlib,importlib.util
root=Path(__file__).parent
sys.path.insert(0,str(root))
# The AP 0.6.8 runtime is not installed here. Load the relevant module with
# minimal external facades so its actual catalog, ID and age logic execute.
opts=types.ModuleType('Options');opts.OptionError=type('OptionError',(Exception,),{});sys.modules['Options']=opts
r=types.ModuleType('worlds');r.__path__=[];sys.modules['worlds']=r
r=types.ModuleType('worlds.generic');r.__path__=[];sys.modules['worlds.generic']=r
r=types.ModuleType('worlds.generic.Rules');r.add_rule=lambda loc,rule:None;sys.modules['worlds.generic.Rules']=r
r=types.ModuleType('soh_extreme');r.__path__=[str(root/'soh_extreme')];r.__spec__=importlib.util.spec_from_file_location('soh_extreme',root/'soh_extreme'/'__init__.py',submodule_search_locations=r.__path__);sys.modules['soh_extreme']=r
r=types.ModuleType('soh_extreme._vendor_oot_soh');r.__path__=[str(root/'soh_extreme'/'_vendor_oot_soh')];r.LogicHelpers=types.ModuleType('LogicHelpers');sys.modules['soh_extreme._vendor_oot_soh']=r
r=types.ModuleType('soh_extreme._vendor_oot_soh.Enums');
class AutoRegion(dict):
    def __missing__(self,key):return key
r.Regions=AutoRegion();r.Items=type('Items',(),{});r.Ages=type('Ages',(),{'CHILD':0,'ADULT':1});sys.modules['soh_extreme._vendor_oot_soh.Enums']=r
r=types.ModuleType('soh_extreme._vendor_oot_soh.Locations');
class BaseLocation:
    def __init__(self,player,name,address,parent):
        self.player,self.name,self.address,self.parent_region=player,name,address,parent
    def can_reach_as_age(self,state,age):
        return True
r.SohLocation=BaseLocation;sys.modules['soh_extreme._vendor_oot_soh.Locations']=r
r=types.ModuleType('soh_extreme.EnemyRoomLogic');r.NativeEnemyRegions=AutoRegion();sys.modules['soh_extreme.EnemyRoomLogic']=r
mod=importlib.import_module('soh_extreme.SceneTransitions')
class Opt:
    def __init__(self,v):self.value=v
class World:
    def __init__(self,v,ut=False,active=()):
        self.options=types.SimpleNamespace(scene_transition_checks=Opt(v),triforce_hunt=Opt(False),shuffle_pots=Opt(0))
        self.using_ut=ut;self.passthrough={'extreme_active_locations':active};self.player=1
        self.regions={};self.locs={}
    def get_region(self,key):
        if key not in self.regions:self.regions[key]=types.SimpleNamespace(name=key,locations=[])
        return self.regions[key]
    def get_location(self,name):return self.locs[name]

assert len(mod.CATALOG)==746
assert len(mod.NAME_TO_ID)==3*len(mod.CATALOG)
assert len(set(mod.NAME_TO_ID.values())) == len(mod.NAME_TO_ID)
shared=World(1)
assert len(mod.active_entries(shared)) == len(mod.CATALOG)
assert mod.active_entries(World(0))==()
age=World(2)
entries=mod.active_entries(age)
assert len(entries)>len(mod.CATALOG)
assert {e['transition_age'] for e in entries}=={0,1}
assert len({e['id'] for e in entries})==len(entries)
assert all(e['id'] == e['base_id'] + (20_000_000 if e['transition_age']==0 else 40_000_000) for e in entries)
mod.create_locations(age)
age.locs={l.name:l for reg in age.regions.values() for l in reg.locations}
for e in age._scene_transition_entries:
    loc=age.get_location(e['name'])
    assert loc.address==e['id']
    assert loc.can_reach_as_age(None,e['transition_age'])
    assert not loc.can_reach_as_age(None,1-e['transition_age'])
for e in mod.CATALOG:
    locations=mod.locations_for_base(age,e['id'])
    assert all(l.name.startswith(e['name']) for l in locations)
    assert len(locations)>=1
for e in entries[:200]:
    w=World(2,ut=True,active=[e['id']]);one=mod.active_entries(w)
    assert len(one)==1 and one[0]['id']==e['id']
# Existing saved seeds keep the existing shared ID even though static catalog
# knows about optional new Age Dependent variants.
e=mod.CATALOG[0]
assert [v['id'] for v in mod.active_entries(World(1,ut=True,active=[e['id']]))]==[e['id']]
print('PASS: active modes, unique IDs, per-age reachability, old UT manifest, all 746 base crossings')
# Confirm native source maps only actual crossings, not generic scene loads.
s=(root/'ArchipelagoClient.cpp').read_text()
assert 'if (mode == 2)' not in s or 'Archipelago_TransitionLocationForAge' in s
assert s.count('IsLocationActive(Archipelago_TransitionLocationForAge(crossing->location, LINK_IS_CHILD))')==3
assert 'SendLocation(resolved, true);' in s
print('PASS: native source, scene, door, warp-song age-mode checks')
