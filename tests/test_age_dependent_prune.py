from pathlib import Path
import sys,types,importlib,importlib.util
from enum import IntFlag
root=Path(__file__).parent/'work'
sys.path.insert(0,str(root))
opts=types.ModuleType('Options');opts.OptionError=type('OptionError',(Exception,),{});sys.modules['Options']=opts
r=types.ModuleType('worlds');r.__path__=[];sys.modules['worlds']=r
r=types.ModuleType('worlds.generic');r.__path__=[];sys.modules['worlds.generic']=r
r=types.ModuleType('worlds.generic.Rules');r.add_rule=lambda loc,rule:None;sys.modules['worlds.generic.Rules']=r
r=types.ModuleType('soh_extreme');r.__path__=[str(root/'soh_extreme')];r.__spec__=importlib.util.spec_from_file_location('soh_extreme',root/'soh_extreme'/'__init__.py',submodule_search_locations=r.__path__);sys.modules['soh_extreme']=r
r=types.ModuleType('soh_extreme._vendor_oot_soh');r.__path__=[str(root/'soh_extreme'/'_vendor_oot_soh')];r.LogicHelpers=types.ModuleType('LogicHelpers');sys.modules['soh_extreme._vendor_oot_soh']=r
r=types.ModuleType('soh_extreme._vendor_oot_soh.Enums');r.Regions={};r.Items=object();r.Ages=type('Ages',(),{'CHILD':0,'ADULT':1});sys.modules['soh_extreme._vendor_oot_soh.Enums']=r
r=types.ModuleType('soh_extreme._vendor_oot_soh.Locations');r.SohLocation=type('SohLocation',(),{});sys.modules['soh_extreme._vendor_oot_soh.Locations']=r
r=types.ModuleType('soh_extreme.EnemyRoomLogic');r.NativeEnemyRegions={};sys.modules['soh_extreme.EnemyRoomLogic']=r
base=types.ModuleType('BaseClasses')
class ItemClassification(IntFlag):
    filler=0
    progression=1
    useful=2
    trap=4
base.ItemClassification=ItemClassification;sys.modules['BaseClasses']=base
mod=importlib.import_module('soh_extreme.SceneTransitions')
class LocList(list):
    def __init__(self,cache,values):
        self.cache=cache;super().__init__(values)
    def remove(self,loc):
        super().remove(loc);del self.cache[loc.name]
class Loc:
    def __init__(self,name,reachable,fill=None):
        self.name=name;self.reachable=reachable;self.item=fill
        self.parent_region=None
    def can_reach(self,st):return self.reachable and self.name not in st.blocked
class Item:
    def __init__(self,name,classification):
        self.name=name;self.classification=classification;self.player=1;self.code=55
class W:
    def __init__(self,mode=2,ut=False,blocked=(),prefilled=False):
        self.using_ut=ut;self.player=1
        self.options=types.SimpleNamespace(scene_transition_checks=types.SimpleNamespace(value=mode))
        entries=[dict(name=f'Scene Check {x} [{a}]',id=i,transition_age=a) for i,(x,a) in enumerate([('A','Child'),('B','Adult'),('C','Adult'),('D','Child')],1)]
        self._scene_transition_entries=tuple(entries)
        locs=[Loc(e['name'],e['name'] not in blocked, 'fixed' if prefilled and e['name'] in blocked else None) for e in entries]
        cache={l.name:l for l in locs}
        self.region=types.SimpleNamespace(locations=LocList(cache,locs))
        self.locations=cache
        for loc in locs:loc.parent_region=self.region
        self.items=[Item('Climb',ItemClassification.progression),Item('Good Equip',ItemClassification.useful),Item('Blue Rupee',ItemClassification.filler),Item('Recovery Heart',ItemClassification.filler),Item('Ice Trap',ItemClassification.trap)]
        self.item_pool=self.items[:2]
        self.multiworld=types.SimpleNamespace(itempool=self.items.copy(),get_all_state=lambda *args,**kwargs: types.SimpleNamespace(blocked=set()))
    def get_location(self,name):return self.locations[name]

def test_prune():
    blocked=('Scene Check B [Adult]','Scene Check D [Child]')
    w=W(blocked=blocked)
    n=mod.retire_unreachable_age_checks(w)
    assert n==2,n
    assert {e['name'] for e in w._scene_transition_entries}=={'Scene Check A [Child]','Scene Check C [Adult]'}
    assert list(w.locations)==['Scene Check A [Child]','Scene Check C [Adult]']
    assert [i.name for i in w.multiworld.itempool]==['Climb','Good Equip','Ice Trap']
    assert w.item_pool[0].name=='Climb' and w.item_pool[1].name=='Good Equip'
    assert mod.retire_unreachable_age_checks(w)==0
    for kw in [dict(mode=0,blocked=blocked),dict(mode=1,blocked=blocked),dict(ut=True,blocked=blocked)]:
        x=W(**kw);assert mod.retire_unreachable_age_checks(x)==0 and len(x.locations)==4
    x=W(blocked=blocked,prefilled=True)
    try:
        mod.retire_unreachable_age_checks(x)
        raise AssertionError('plando protection failed')
    except opts.OptionError as e:assert 'plando' in str(e)
    x=W(blocked=tuple('Scene Check '+n+' ['+a+']' for n,a in [('A','Child'),('B','Adult'),('C','Adult'),('D','Child')]))
    x.multiworld.itempool=x.multiworld.itempool[:3]  # only one spare junk
    try:
        mod.retire_unreachable_age_checks(x)
        raise AssertionError('filler protection failed')
    except opts.OptionError as e:assert 'filler' in str(e)
    print('PASS: pruning only unreachable age variants; location caches and pools consistent')
    print('PASS: normal modes/UT untouched, plando protected, insufficient filler fails safely')
test_prune()
