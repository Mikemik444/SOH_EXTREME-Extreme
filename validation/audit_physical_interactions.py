"""Source-derived local interaction constraints under fresh partial inventories.

AND/OR alternatives are preserved. Untranslated source atoms are explicitly
reported and weakened to True for necessary-condition tests, never certified.
Parent access is tested in the actual AP graph; only physically reachable ages
may satisfy an age-dependent interaction. This is not a collision playtest.
"""
from run_case import setup, BOOTSTRAP
from location_source_audit import collect
from worlds.soh_extreme.EnemyRoomLogic import parse, NativeRoomCompiler
from worlds.soh_extreme._vendor_oot_soh import LogicHelpers as H
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions,Ages,Items
from rule_builder.rules import And,Or,Has,True_,False_,Rule
from BaseClasses import CollectionState
from pathlib import Path
from collections import Counter
import argparse,json,random

class Projection(NativeRoomCompiler):
 def __init__(self,w,region):
  self.world=w;self.region=region;self.unknown=Counter();self.unknown_tricks=set();self.flags=set()
 def bundle(self,rr):return (self.region,self.world)
 def node(self,n,rr):
  if n[0]=='compare':
   op,left,right=n[1:]
   if left[0]=='call' and right[0]=='constant' and op in ('>=','>','=='):
    count=right[1]+(op=='>');b=self.bundle(rr)
    if left[1]=='GetGSCount':return Has(Items.GOLD_SKULLTULA_TOKEN,count)
    if left[1]=='StoneCount':return H.has_enough_stones(b,count)
    if left[1]=='OcarinaButtons':return H.has_enough_ocarina_buttons(b,count)
    if left[1] in ('FireTimer','WaterTimer'):return super().node(n,rr)
   self.unknown[repr(n)]+=1;return True
  if n[0] in ('and','or'):
   rules=[self.node(v,rr) for v in n[1]]
   rules=[self.as_rule(v) for v in rules]
   return And(*rules) if n[0]=='and' else Or(*rules)
  if n[0]=='select':
   # Only constant options choose a branch here. Unknown tests preserve both
   # possibilities so a necessary-condition audit cannot reject a valid route.
   test=self.node(n[1],rr)
   if isinstance(test,bool):return self.node(n[2] if test else n[3],rr)
   return Or(self.as_rule(self.node(n[2],rr)),self.as_rule(self.node(n[3],rr)))
  if n[0]=='call' and n[1] in ('AnyAgeTime','Get','HasAccessTo','Here','ChildCanAccess','AdultCanAccess'):
   self.unknown[repr(n)]+=1;return True
  try:
   result=super().node(n,rr)
   if isinstance(result,(Rule,bool,int)) or n[0]=='name':return result
   raise ValueError('unsupported atom')
  except (KeyError,ValueError,TypeError,AttributeError,NotImplementedError) as e:
   self.unknown[repr(n)]+=1;return True
  except Exception as e:
   if type(e).__name__!='OptionError':raise
   self.unknown[repr(n)]+=1;return True
 def as_rule(self,v):
  if isinstance(v,Rule):return v
  if isinstance(v,bool):return True_() if v else False_()
  self.unknown[str(v)]+=1;return True_()
 def call(self,name,a,rr,raw=()):
  b=self.bundle(rr);o=self.world.options
  helpers={'CanBreakCrates':'can_break_crates','CanCollectGrass':'can_collect_grass',
   'CanCutShrubs':'can_cut_shrubs','CanBreakRocks':'can_break_rocks',
   'CanBonkTrees':'can_bonk_trees','CanBreakLowerBeehives':'can_break_lower_hives',
   'CanBreakUpperBeehives':'can_break_upper_beehives','CanReachZrUpperCircle':'can_reach_zr_raised_ledge'}
  if name in helpers and not a:return getattr(H,helpers[name])(b)
  if name in ('CanOpenChest','CanOpenLargeChest'):
   return Has('Open Chest',2 if name=='CanOpenLargeChest' and o.shuffle_open_chest.value==2 else 1) if o.shuffle_open_chest.value else True
  if name=='SmallKeys' and a[0]=='SCENE_TREASURE_BOX_SHOP':return H.small_keys(Items.TREASURE_GAME_SMALL_KEY,a[1],b)
  if name=='Option' and a[0]=='RSK_SHUFFLE_CHEST_MINIGAME':return bool(o.shuffle_chest_minigame.value)
  return super().call(name,a,rr,raw)

def build_constraints(w,root):
 rows,_=collect(root,w)
 rules={};unknown=Counter();skipped=[]
 for row in rows:
  sources=[r for r in row['native_sources'] if '_MQ_' not in r['region']]
  if row['kind'] not in ('stock','fork') or not sources:continue
  try:region=Regions(row['ap_region'])
  except ValueError:skipped.append(dict(name=row['name'],reason='non-stock parent'));continue
  compiler=Projection(w,region);alternatives=[]
  for s in sources:
   try:rule=compiler.as_rule(compiler.node(parse(s['condition']),None))
   except Exception as e:
    compiler.unknown[s['condition']]+=1;rule=True_()
   alternatives.append(rule)
  rule=Or(*alternatives).resolve(w);w.register_rule_dependencies(rule)
  rules[row['id']]=(rule,region,row);unknown.update(compiler.unknown)
 return rules,unknown,skipped

def allows_interaction(w,state,entry):
 rule,region,row=entry;loc=w.get_location(row['name']);old=state._soh_age[w.player]
 try:
  for age in (Ages.CHILD,Ages.ADULT):
   state._soh_age[w.player]=age
   if loc.parent_region.can_reach(state) and rule(state):return True
  return False
 finally:state._soh_age[w.player]=old

def main():
 p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
 a=p.parse_args();m=setup(291036);w=m.worlds[1]
 rules,unknown,skipped=build_constraints(w,a.source_root)
 physical=[*m.itempool,*[l.item for l in w.get_locations() if l.address is not None and l.item]]
 names=[it.name for it in physical if it.name in w.item_name_to_id];counts=Counter(names)
 scenarios=[('full',{})]+[(f'without {n}',{n:0}) for n in sorted(counts)]
 for n in ('Open Chest','Strength Upgrade','Progressive Scale','Progressive Hookshot','Progressive Wallet','Progressive Ocarina','Treasure Game Small Key',*[n for n in counts if 'Silver:' in n]):
  scenarios.extend((f'{n} x{i}',{n:i,**({'Skeleton Key':0,'Treasure Game Key Ring':0} if n=='Treasure Game Small Key' else {})}) for i in range(1,counts[n]))
 for count in range(6):
  scenarios.append((f'Sun Block stick route with {count} silvers',{'Spirit Silver: Sun':count,"Din's Fire":0,'Fire Arrows':0}))
 scenarios.append(('no explosives',{'Progressive Bomb Bag':0,'Bombchu Bag':0}))
 scenarios.append(('no climb or longshot',{'Climb':0,'Progressive Hookshot':1}))
 for count in range(5):
  scenarios.append((f'maze rock without blasting, strength {count}',{'Progressive Bomb Bag':0,'Bombchu Bag':0,'Megaton Hammer':0,'Strength Upgrade':count}))
 weapons={'Kokiri Sword','Master Sword',"Biggoron's Sword","Giant's Knife",'Progressive Bomb Bag','Bombchu Bag','Progressive Bow','Progressive Slingshot','Progressive Hookshot','Boomerang','Megaton Hammer',"Din's Fire",'Progressive Magic Meter','Progressive Stick Capacity','Roll','Strength Upgrade'}
 weapons&=counts.keys()
 scenarios.append(('no physical interaction methods',{n:0 for n in weapons}))
 scenarios.extend((f'only interaction method {n}',{k:0 for k in weapons-{n}}) for n in sorted(weapons))
 rng=random.Random(291035)
 for index in range(128):
  keep=(0.55,0.7,0.85,0.95)[index%4]
  limits={n:sum(rng.random()<keep for _ in range(count)) for n,count in sorted(counts.items())}
  scenarios.append((f'partial inventory {index} at {keep}',limits))
 failures=[];stats=[]
 for label,limits in scenarios:
  state=CollectionState(m)
  for n,count in counts.items():
   for _ in range(limits.get(n,count)):state.collect(w.create_item(n),True)
  state.sweep_for_advancements([l for l in w.get_locations() if l.address is None])
  tested=0
  for i,(rule,region,row) in rules.items():
   loc=w.get_location(row['name'])
   if not loc.can_reach(state):continue
   tested+=1;valid=allows_interaction(w,state,rules[i])
   if not valid:failures.append(dict(scenario=label,name=row['name'],id=i,sources=row['native_sources']))
  stats.append(dict(scenario=label,reachable_constraints_tested=tested))
  if len(stats)%30==0:print('SCENARIOS',len(stats),'/',len(scenarios),flush=True)
 result=dict(passed=not failures,scope=__doc__,source_checks=len(rules),scenarios=len(scenarios),
  assertions=sum(s['reachable_constraints_tested'] for s in stats),failures=failures,stats=stats,
  nontrivial_constraints=sum(not rule.always_true for rule,_,_ in rules.values()),
  untranslated_atoms=dict(unknown),skipped=skipped)
 a.report.write_text(json.dumps(result,indent=2));print('PASS' if result['passed'] else 'FAIL',len(failures),'failures')
 for f in failures[:30]:print(f['scenario'],f['name'])
 return not result['passed']
if __name__=='__main__':raise SystemExit(main())
