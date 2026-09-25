"""AP result -> production Python encoder -> production C++ client/view.
Controlled UT host exercises the subclass's real callbacks without a live GUI.
"""
from run_case import setup, BOOTSTRAP
from BaseClasses import CollectionState
from pathlib import Path
from types import SimpleNamespace
import argparse,asyncio,json,subprocess,base64,struct
from worlds.soh_extreme.TrackerMirror import encode_snapshot,snapshot_rows,PROTOCOL
from worlds.soh_extreme.TrackerClient import make_context_class,register_launcher
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--native-exe',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
checks=[];fixtures=[];a.report.parent.mkdir(parents=True,exist_ok=True)
def ck(name,ok):
 checks.append({'test':name,'passed':bool(ok)})
 if not ok:raise AssertionError(name)
m=setup(11941,overrides={'boss_key_shuffle':'anywhere'},stop_before='pre_fill');w=m.worlds[1]
active={l.address for l in w.get_locations() if type(l.address) is int}
physical=list(m.itempool)+[l.item for l in w.get_locations() if l.address is not None and l.item is not None]
notes={n for n in w.item_name_to_id if n.startswith('Song Note ')}
base_missing={'NPC Soul','Speak Goron','Grab / Power Bracelet','Strength Upgrade','Rock / Boulder Soul','Bolero of Fire','Progressive Ocarina'}|notes|{n for n in w.item_name_to_id if 'Button' in n}
for i,missing in enumerate((set(),{'NPC Soul'},{'Speak Hylian'},{"Din's Fire",'Fire Arrows'},base_missing)):
 state=CollectionState(m);received=[]
 for item in physical:
  if item.name not in missing:
   received.append(item);state.collect(item,True)
 state.sweep_for_advancements(locations=[l for l in w.get_locations() if l.address is None])
 normal=[l for l in w.get_locations() if l.address in active and l.can_reach(state)]
 # Exercise checked removal, a filtered-out reachable row, and a distinct
 # glitched-only row. These are display inputs, never game-state mutations.
 checked={normal[0].address} if normal else set();ignored={normal[1].address} if len(normal)>1 else set()
 names=[l.name for l in normal if l.address not in checked|ignored]
 glitched=[l.name for l in w.get_locations() if l.address in active and l.address not in checked|ignored and l not in normal][:2]
 core=SimpleNamespace(enable_glitched_logic=True,location_alias_map={},manual_items=['Test override'],ignored_locations=ignored,
                      get_current_world=lambda:w)
 result=SimpleNamespace(state=state,in_logic_locations=names,glitched_locations=glitched)
 rows=snapshot_rows(core,result,w,active,checked)
 ck('normal exact IDs '+str(i),{r['id'] for r in rows if r['state']==1}=={w.get_location(n).address for n in names})
 ck('glitched not promoted '+str(i),{r['id'] for r in rows if r['state']==2}=={w.get_location(n).address for n in glitched})
 payload=encode_snapshot(nonce='a'*32,producer='b'*32,request=1,revision=1,slot=1,received=len(received),active=active,checked=checked,rows=rows,manual_count=1,ignored_count=len(ignored))
 fixture=a.report.parent/('119-snapshot-'+str(i)+'.b64');fixture.write_text(payload)
 r=subprocess.run([str(a.native_exe),str(fixture)],capture_output=True,text=True)
 (fixture.with_suffix('.native.log')).write_text(r.stdout+r.stderr)
 ck('actual C++ client/view consumes snapshot '+str(i),r.returncode==0)
 output=r.stdout.splitlines();echo={int(line.split('\t',2)[0]):(int(line.split('\t',2)[1]),line.split('\t',2)[2]) for line in output[1:]}
 expected={row['id']:(row['state'],row['region']+' | '+row['name']) for row in rows}
 ck('every rendered ID/status/name equals producer '+str(i),echo==expected)
 fixtures.append({'scenario':i,'rows':len(rows),'native_assertions':int(output[0].split('\t')[1]),'bytes':len(base64.b64decode(payload))})
 # Actual subclass callbacks; only base UT/network services are controlled.
 class Host:
  tags={'AP','Tracker'}
  def __init__(self):
   self.game='SOH-EXTREME';self.slot=1;self.server_locations=active;self.checked_locations=checked
   self.tracker_items_received=received;self.tracker_core=core;self.sent=[];self.calls=0
  def on_package(self,cmd,args):pass
  def updateTracker(self):self.calls+=1;return result
  async def send_msgs(self,packets):self.sent.extend(packets)
  async def disconnect(self,allow_autoreconnect=False):pass
 async def exercise():
  ctx=make_context_class(Host)()
  req={'data':{'soh_extreme_tracker':PROTOCOL,'kind':'request','slot':1,'nonce':'a'*32,'request':1}}
  ctx.on_package('Bounced',req);await asyncio.sleep(0)
  ck('wrapper calls upstream evaluator '+str(i),ctx.calls==1)
  ck('wrapper sends snapshot to this slot '+str(i),len(ctx.sent)==1 and ctx.sent[0]['slots']==[1])
  fixture2=a.report.parent/('119-callback-'+str(i)+'.b64');fixture2.write_text(ctx.sent[0]['data']['payload'])
  rr=subprocess.run([str(a.native_exe),str(fixture2)],capture_output=True,text=True)
  ck('actual callback payload consumed by C++ '+str(i),rr.returncode==0)
  ctx.on_package('Bounced',{'data':dict(req['data'],slot=2)})
  ck('another slot does not publish '+str(i),ctx.calls==1)
  await ctx.disconnect();ck('disconnect clears subscription '+str(i),ctx._mirror_subscription is None)
 asyncio.run(exercise())
 # Disable glitched display exactly as UT does, not a union with normal.
 core.enable_glitched_logic=False
 ck('UT glitched display preference preserved '+str(i),all(r['state']==1 for r in snapshot_rows(core,result,w,active,checked)))
# Strict encoder malformed and retired/inactive row tests.
kwargs=dict(nonce='a'*32,producer='b'*32,request=1,revision=1,slot=1,received=0,active={11,12},checked={12},rows=[{'id':11,'state':1,'name':'NPC %s ##not-an-ID','region':'Test'}])
for name,change in [('inactive',{'rows':[{'id':13,'state':1,'name':'X','region':'Y'}]}),('checked',{'rows':[{'id':12,'state':1,'name':'X','region':'Y'}]}),('duplicate',{'rows':kwargs['rows']*2}),('invalid-state',{'rows':[dict(kwargs['rows'][0],state=3)]}),('control',{'rows':[dict(kwargs['rows'][0],name='x\nY')]}),('negative-id',{'active':{-1}})]:
 failed=False
 try:encode_snapshot(**dict(kwargs,**change))
 except ValueError:failed=True
 ck('encoder rejects '+name,failed)
from worlds.LauncherComponents import components
register_launcher();register_launcher();ck('one launcher component',sum(c.display_name=='SOH-EXTREME Universal Tracker' for c in components)==1)
a.report.write_text(json.dumps({'passed':True,'checks':len(checks),'fixtures':fixtures,'tests':checks,'scope':'production transport, client methods and view with controlled AP/UT-host/ImGui services; no live network or UI'},indent=2));print(a.report.read_text())
