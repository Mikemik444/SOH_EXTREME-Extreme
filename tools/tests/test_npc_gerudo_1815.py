"""Production function/graph fixtures without a replacement AP generator.

Loads the real enums/catalog, scrub parent resolver and authored location parents.
Gerudo predicates execute from the shipped Python and C++ source. Rule primitives
and inventory/engine IO are isolated. This is not a full AP item fill or game run.
"""
from pathlib import Path
import ast, importlib.util, json, sys, types, itertools, hashlib, subprocess, tempfile, re, argparse, os
R=Path(__file__).resolve().parents[2];W=R/'archipelago/soh_extreme';V=W/'_vendor_oot_soh'
spec=importlib.util.spec_from_file_location('fixture_enums',V/'Enums.py');E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)
def tree(path):return ast.parse(path.read_text())
def execute(nodes,env):exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<production fragments>','exec'),env)
def function(path,name):return next(n for n in ast.walk(tree(path)) if isinstance(n,ast.FunctionDef) and n.name==name)
count=0
def check(condition,message):
 global count
 count+=1
 if not condition:raise AssertionError(message)
# Use actual location IDs rather than manually transcribed catalogue anchors.
data={}
for n in ast.walk(tree(V/'Locations.py')):
 if isinstance(n,ast.Dict):
  for k,v in zip(n.keys,n.values):
   if isinstance(k,ast.Attribute) and isinstance(k.value,ast.Name) and k.value.id=='Locations' and isinstance(v,ast.Call) and isinstance(v.func,ast.Name) and v.func.id=='SohLocData':
    data[E.Locations[k.attr]]=types.SimpleNamespace(loc_id=ast.literal_eval(v.args[0]))
# Record every add_locations parent, just as the actual refill registry does even
# when a reward shuffle is off. No purchase condition is used for a conversation.
parents={}
for path in (V/'location_access').rglob('*.py'):
 for n in ast.walk(tree(path)):
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='add_locations' and isinstance(n.args[0],ast.Attribute) and isinstance(n.args[2],ast.List):
   parent=E.Regions[n.args[0].attr]
   for loc in n.args[2].elts:
    if isinstance(loc,ast.Tuple) and isinstance(loc.elts[0],ast.Attribute) and loc.elts[0].value.id=='Locations':
     parents[str(E.Locations[loc.elts[0].attr])]=parent
regions={str(r):types.SimpleNamespace(name=str(r)) for r in E.Regions}
world=types.SimpleNamespace(get_region=lambda name:regions[name],_extreme_refill_source_rules={n:(p,'UNUSED PURCHASE RULE') for n,p in parents.items()})
ns={'Regions':E.Regions,'__package__':'npc_fixture'}
fake=types.ModuleType('npc_fixture._vendor_oot_soh.Locations');fake.location_data_table=data
sys.modules[fake.__name__]=fake
execute([function(W/'NpcSpeech.py','scrub_conversation_parent')],ns)
resolver=function(W/'__init__.py','resolve_native_region')
world_tree=tree(W/'__init__.py')
aliases=next(ast.literal_eval(n.value) for n in ast.walk(world_tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='native_region_aliases' for t in n.targets))
old_env={'region_members':{r.name:r for r in E.Regions},'actual_regions':regions,'native_region_aliases':aliases}
execute([resolver],old_env);old=old_env['resolve_native_region']
catalog=json.loads((W/'NpcSpeechCatalog.json').read_text());scrubs=[e for e in catalog if e.get('native_rc')]
failures=[]
for e in scrubs:
 name=next(str(k) for k,v in data.items() if v.loc_id==e['anchor'])
 check(name in parents,'Missing authored scrub parent '+e['name'])
 expected=regions[str(parents[name])]
 for mode in ('off','one_time_only','all'):
  enabled=mode=='all' or (mode=='one_time_only' and e['anchor'] in (688,691,695))
  stock={name:types.SimpleNamespace(parent_region=expected)} if enabled else {}
  result=ns['scrub_conversation_parent'](world,e,stock,old)
  check(result is expected,f'{mode}: incorrect parent for {e["name"]}')
  check(result.name!='Menu','Conversation must never become a free Menu check')
 if old(e['native_region']) is None:failures.append(e['name'])
check(len(failures)>0,'Must reproduce missing native scrub parent without reward anchors')
check('NpcSpeech.scrub_conversation_parent(' in (W/'__init__.py').read_text(),'World must use the corrected helper')
unknown=dict(scrubs[0],anchor=-1,native_region='RR_NOT_A_REGION')
check(ns['scrub_conversation_parent'](world,unknown,{},old) is None,'Bad identities must still fail closed')
# Validate conversation gates remain local (stun/Soul/language/age), with no
# accidental inclusion of wallet/price or location reward access.
class Rule:
 def __init__(self,fn):self.fn=fn
 def __call__(self,state):return self.fn(state)
 def __and__(self,o):return Rule(lambda s:self(s) and o(s))
 def __or__(self,o):return Rule(lambda s:self(s) or o(s))
 def __bool__(self):raise TypeError('Use & and |')
def Has(name):return Rule(lambda s:name in s['names'])
def And(*rules):return Rule(lambda s:all(r(s) for r in rules))
def Or(*rules):return Rule(lambda s:any(r(s) for r in rules))
H=types.SimpleNamespace(can_stun_deku=lambda b:Has('stun'),is_child=lambda b:Rule(lambda s:s['child']))
ns.update(H=H,Has=Has,And=And,Or=Or,LANGUAGES=('Deku','Gerudo','Goron','Hylian','Kokiri','Zora'))
execute([function(W/'NpcSpeech.py','conversation_rule')],ns)
for mode,npc,soul in itertools.product(range(3),range(2),range(2)):
 world.options=types.SimpleNamespace(shuffle_speak=types.SimpleNamespace(value=mode),shuffle_npc_soul=types.SimpleNamespace(value=npc),shuffle_business_scrub_soul=types.SimpleNamespace(value=soul))
 for e in scrubs:
  name=next(str(k) for k,v in data.items() if v.loc_id==e['anchor'])
  rule=ns['conversation_rule'](world,e,str(parents[name]))
  required={'stun'}|({'NPC Soul'} if npc else set())|({'Scrub Soul'} if soul else set())|({'Speak'} if mode==1 else {'Speak '+e['language']} if mode==2 else set())
  check(rule({'child':True,'names':required}),'Properly equipped child cannot speak '+e['name'])
  for missing in required:
   check(not rule({'child':True,'names':required-{missing}}),'Missing '+missing+' was ignored')
# Execute the real Gerudo access predicates with explicit inventory rule leaves.
ns2={k:getattr(E,k) for k in ('Regions','Items','Enemies','EnemyDistance','Tricks','Locations')}
ns2.update(Rule=Rule,True_=lambda:Rule(lambda s:True),is_child=lambda b:Rule(lambda s:s['child']),is_adult=lambda b:Rule(lambda s:not s['child']),has_item=lambda i,b:Rule(lambda s:i in s['items']),
 can_do_trick=lambda i,b:Rule(lambda s:i in s['tricks']),can_use=lambda i,b:Rule(lambda s:i in s['items'] and (not s['child'] or i not in (E.Items.FAIRY_BOW,E.Items.HOOKSHOT,E.Items.LONGSHOT))),
 can_break_crates=lambda b:Has('break crates'))
ns2['can_use_any']=lambda items,b:Or(*(ns2['can_use'](i,b) for i in items))
execute([function(V/'LogicHelpers.py','can_pass_enemy')],ns2)
gf=tree(V/'location_access/overworld/gerudo_fortress.py');edges={};locations={}
for n in ast.walk(gf):
 if not(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('connect_regions','add_locations') and isinstance(n.args[0],ast.Attribute) and isinstance(n.args[2],ast.List)):continue
 src=E.Regions[n.args[0].attr]
 for pair in n.args[2].elts:
  dst=pair.elts[0]; pred=pair.elts[1]
  if not isinstance(dst,ast.Attribute):continue
  fn=eval(compile(ast.Expression(pred),'<actual GF predicate>','eval'),ns2)
  (edges if n.func.id=='connect_regions' else locations)[(src,dst.attr)]=fn
pairs=[('GERUDO_FORTRESS_OUTSKIRTS','GF_NEAR_GROTTO'),('GERUDO_FORTRESS_OUTSKIRTS','GF_OUTSIDE_GTG'),('GF_NEAR_GROTTO','GF_OUTSIDE_GTG'),('GF_OUTSIDE_GTG','GF_NEAR_GROTTO'),('GF_OUTSIDE_GTG','GF_ABOVE_GTG'),('GF_ABOVE_GTG','GF_OUTSIDE_GTG')]
for child,card,hook,bow,trick,npc_soul in itertools.product((False,True),repeat=6):
 items=({E.Items.GERUDO_MEMBERSHIP_CARD} if card else set())|({E.Items.HOOKSHOT} if hook else set())|({E.Items.FAIRY_BOW} if bow else set())
 state={'child':child,'items':items,'tricks':{E.Tricks.PASS_GUARDS_WITH_NOTHING} if trick else set(),'names':{'NPC Soul'} if npc_soul else set()}
 expected=card or (not child and (hook or bow)) or trick
 for src,dst in pairs:
  check(edges[(E.Regions[src],dst)]((E.Regions[src],world))(state)==expected,'Guard bypass '+src+' -> '+dst)
 check(edges[(E.Regions.GF_EXITING_GTG,'GF_OUTSIDE_GTG')]((E.Regions.GF_EXITING_GTG,world))(state)==card,'Arrival guard card rule')
 for src,dst in [('GF_ABOVE_GTG','THIEVES_HIDEOUT_DOUBLE_CELL'),('GF_ABOVE_GTG','THIEVES_HIDEOUT_KITCHEN_CORRIDOR'),('GF_TOP_OF_LOWER_VINES','THIEVES_HIDEOUT_KITCHEN_TOP')]:
  check(edges[(E.Regions[src],dst)]((E.Regions[src],world))(state),'Safe direct arrival was blanket-locked')
# Compile actual C++ guarded entrance expressions (engine helper result isolated).
native=R/'soh/Enhancements/randomizer/location_access/overworld/gerudo_fortress.cpp'
text=native.read_text();expr=[]
for part in text.split('areaTable[')[1:]:
 src=part.split(']')[0]
 for dst,body in re.findall(r'ENTRANCE\((RR_\w+),\s*(.*?)\),\s*$',part,re.M):
  if 'CanPassEnemy(RE_GERUDO_GUARD)' in body or (src=='RR_GF_EXITING_GTG' and dst=='RR_GF_OUTSIDE_GTG'):
   expr.append((src,dst,body))
check(len(expr)==7,'Expected six guarded approaches and direct GTG exit')
code='''#include <cassert>\n#include <cstdio>\nconstexpr int RE_GERUDO_GUARD=1,RG_GERUDO_MEMBERSHIP_CARD=2;\nstruct L {bool IsChild,pass,card;bool CanPassEnemy(int){return pass;}bool HasItem(int){return card;}};\nint main(){int count=0;for(int c=0;c<2;++c)for(int p=0;p<2;++p)for(int card=0;card<2;++card){L obj{bool(c),bool(p),bool(card)};auto* logic=&obj;\n'''
for src,dst,body in expr:
 expected='bool(card)' if src=='RR_GF_EXITING_GTG' else 'bool(p)'
 code+=f'assert(bool({body})=={expected});++count;\n'
code+='}std::printf("Native Gerudo: %d assertions passed\\n",count);}'
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'gf.cpp';p.write_text(code);exe=Path(d)/'gf'
 subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
 res=subprocess.run([str(exe)],capture_output=True,text=True,check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'))
 print(res.stdout,end='')
print(f'PASS: {count} Python fixture assertions. Reproduced missing-parent failures: '+', '.join(failures))
p=argparse.ArgumentParser();p.add_argument('--report',type=Path);args=p.parse_args()
report={'status':'passed','python_assertions':count,'native_assertions':56,'scrub_entries':len(scrubs),'old_missing_parent_cases':failures,'scope':__doc__,'sources':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [W/'NpcSpeech.py',W/'__init__.py',V/'LogicHelpers.py',V/'Enums.py',V/'Locations.py',V/'location_access/overworld/gerudo_fortress.py',native,Path(__file__)]}}
if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
