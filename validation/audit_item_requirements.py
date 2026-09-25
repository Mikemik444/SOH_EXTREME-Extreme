"""Source-proven direct item requirements, retaining OR alternatives.
This extends the custom capability audit to equipment, instruments, songs and
selected native helpers. It is deliberately incomplete for unrecognized C++.
"""
from __future__ import annotations
import argparse,json,re,collections
from pathlib import Path
from run_case import setup,BOOTSTRAP
from source_index import split_top,body_at
from location_source_audit import collect
from worlds.soh_extreme._vendor_oot_soh.LogicHelpers import *
ALIASES={'BIGGORON_SWORD':'BIGGORONS_SWORD','OCARINA_A_BUTTON':'OCARINA_A_BUTTON',
'OCARINA_C_LEFT_BUTTON':'OCARINA_CLEFT_BUTTON','OCARINA_C_RIGHT_BUTTON':'OCARINA_CRIGHT_BUTTON',
'OCARINA_C_UP_BUTTON':'OCARINA_CUP_BUTTON','OCARINA_C_DOWN_BUTTON':'OCARINA_CDOWN_BUTTON',
'PROGRESSIVE_MAGIC_METER':'PROGRESSIVE_MAGIC','BOMBCHU_5':'BOMBCHUS_5','BOMBCHU_10':'BOMBCHUS_10','BOMBCHU_20':'BOMBCHUS_20'}

def mandatory(expr):
 expr=expr.strip()
 while expr.startswith('('):
  inner,end=body_at(expr,1)
  if end!=len(expr)-1:break
  expr=inner.strip()
 parts=split_top(expr,'||')
 if len(parts)>1:return set.intersection(*(mandatory(p) for p in parts))
 parts=split_top(expr,'&&')
 if len(parts)>1:return set.union(*(mandatory(p) for p in parts))
 if expr.startswith('!'):return set()
 m=re.fullmatch(r'logic->(HasItem|CanUse)\((RG_\w+)\)',expr)
 if m:
  item=m[2][3:];member=getattr(Items,ALIASES.get(item,item),None)
  if member is not None:return {(m[1],str(member))}
 m=re.fullmatch(r'AnyAgeTime\(\[\]\{\s*return\s+(.*);\s*}\)',expr,flags=re.S)
 if m:return mandatory(m[1])
 return set()

def requirement(kind,item,bundle):
 # Query the local item/action only; age reachability is tested separately.
 item=Items(item)
 if kind=='CanUse' and item in ocarina_buttons_required:return can_play_song(item,bundle)
 if kind=='CanUse' and item in (Items.IRON_BOOTS,Items.FISHING_POLE):return can_use(item,bundle)
 return has_item(item,bundle)

if __name__=='__main__':
 p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 mw=setup(1717,overrides={'boss_key_shuffle':'anywhere','shuffle_roll':True,'shuffle_open_chest':'progressive'},stop_before='pre_fill');w=mw.worlds[1]
 rows,_=collect(a.source_root,w);full=mw.get_all_state(False)
 eventitems={l.item.name:l.item for l in mw.get_locations() if l.item}
 counts=collections.Counter();failures=[];skipped=[]
 requirements={}
 for row in rows:
  defs=[r for r in row['native_sources'] if '_MQ_' not in r['region']]
  if row['kind'] not in ('stock','fork') or not defs:continue
  needed=set.intersection(*(mandatory(r['condition']) for r in defs))
  # Stock helpers require a real AP Regions enum as the age context.
  try:region=Regions(row['ap_region'])
  except ValueError:
   skipped.append({'name':row['name'],'reason':'non-enum parent','requirements':sorted(needed)});continue
  for kind,name in sorted(needed):
   r=requirement(kind,name,(region,w)).resolve(w);w.register_rule_dependencies(r)
   key=(kind,name,region)
   if key not in requirements:requirements[key]=(r,[])
   requirements[key][1].append(row)
 for key,(rule,rr) in requirements.items():
  if not rule(full):
   skipped.append({'requirement':str(key),'reason':'not true with baseline full state'});continue
  deps=rule.item_dependencies()
  for dep in deps:
   if not full.count(dep,1):continue
   state=full.copy()
   if dep in w.item_name_to_id:item=w.create_item(dep)
   elif dep in eventitems:item=eventitems[dep]
   else:
    skipped.append({'requirement':str(key),'dependency':dep,'reason':'not a removable receipt'});continue
   while state.count(dep,1):
    n=state.count(dep,1);state.remove(item)
    if state.count(dep,1)>=n:raise RuntimeError(('removal did not progress',dep))
   if rule(state):continue # Another legitimate way to obtain the capability.
   for row in rr:
    counts[str(key[:2])]+=1
    if w.get_location(row['name']).can_reach(state):failures.append({'id':row['id'],'name':row['name'],'rc':row['rc'],'required':key[:2],'removed':dep,'native_sources':row['native_sources']})
 out={'scope':__doc__,'tested':sum(counts.values()),'counts':dict(counts),'failure_count':len(failures),'failures':failures,'skipped':skipped}
 a.report.write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items() if k not in ('failures','skipped')},flush=True)
 for f in failures:print(f['name'],f['required'],f['removed'],flush=True)
