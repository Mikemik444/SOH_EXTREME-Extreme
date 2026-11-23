"""Unit contracts for the live SceneTransitions module with an AP facade."""
import importlib,importlib.util,sys,types
from pathlib import Path
root=Path('/mnt/data/scene_all_missing_work')
sys.path.insert(0,str(root))
opt=types.ModuleType('Options');opt.OptionError=type('OptionError',(Exception,),{});sys.modules['Options']=opt
base=types.ModuleType('BaseClasses')
class ItemClassification:
  progression=1; useful=2
base.ItemClassification=ItemClassification
class CollectionState:
 def __init__(self,mw):self.mw=mw
 def sweep_for_advancements(self):pass
base.CollectionState=CollectionState
sys.modules['BaseClasses']=base
worlds=types.ModuleType('worlds');worlds.__path__=[];sys.modules['worlds']=worlds
wgen=types.ModuleType('worlds.generic');wgen.__path__=[];sys.modules['worlds.generic']=wgen
rul=types.ModuleType('worlds.generic.Rules');rul.add_rule=lambda loc,rule:None;sys.modules['worlds.generic.Rules']=rul
root_pkg=types.ModuleType('soh_extreme');root_pkg.__path__=[str(root/'soh_extreme')];root_pkg.__spec__=importlib.util.spec_from_file_location('soh_extreme',root/'soh_extreme'/'__init__.py',submodule_search_locations=root_pkg.__path__);sys.modules['soh_extreme']=root_pkg
vend=types.ModuleType('soh_extreme._vendor_oot_soh');vend.__path__=[str(root/'soh_extreme'/'_vendor_oot_soh')];vend.LogicHelpers=types.ModuleType('LogicHelpers');sys.modules[vend.__name__]=vend
enum=types.ModuleType('soh_extreme._vendor_oot_soh.Enums')
class AutoRegion(dict):
 def __missing__(self,k):return k
enum.Regions=AutoRegion();enum.Items=type('Items',(),{});enum.Ages=type('Ages',(),{'CHILD':0,'ADULT':1});sys.modules[enum.__name__]=enum
locmod=types.ModuleType('soh_extreme._vendor_oot_soh.Locations')
class Loc:
 def __init__(self,player,name,address,parent):
  self.player=player;self.name=name;self.address=address;self.parent_region=parent;self.item=None
 def can_reach_as_age(self,state,age):return self.can_reach(state)
 def can_reach(self,state):return state.mw.start_can if isinstance(state,CollectionState) else state.can
locmod.SohLocation=Loc;sys.modules[locmod.__name__]=locmod
erm=types.ModuleType('soh_extreme.EnemyRoomLogic');erm.NativeEnemyRegions=AutoRegion();sys.modules[erm.__name__]=erm
mod=importlib.import_module('soh_extreme.SceneTransitions')
class Region:
 def __init__(self):self.locations=[]
class State:
 def __init__(self,can):self.can=can
class Item:
 def __init__(self,name):self.player=1;self.name=name;self.classification=0;self.code=111
class MW:
 def __init__(self):self.itempool=[Item('Recovery Heart')];self.start_can=True
 def get_all_state(self,*a,**kw):return State(False)
class Options:
 scene_transition_checks=types.SimpleNamespace(value=2)
class W:
 def __init__(self):
  self.player=1;self.using_ut=False;self.multiworld=MW();self.options=Options();self.item_pool=list(self.multiworld.itempool)
  self.region=Region();self.loc=Loc(1,'Fountain Exit [Child]',31000011,self.region);self.region.locations.append(self.loc)
  self._scene_transition_entries=[dict(name=self.loc.name,id=self.loc.address,transition_age=0)]
 def get_location(self,name):return self.loc
w=W()
assert mod.retire_unreachable_age_checks(w)==0
assert w.loc in w.region.locations and len(w.item_pool)==1
w.multiworld.start_can=False
assert mod.retire_unreachable_age_checks(w)==1
assert not w.region.locations and not w.multiworld.itempool and not w._scene_transition_entries
print('PASS: reachable at start never pruned by contradictory full-state result; genuinely impossible child checks retired and filler balanced')
