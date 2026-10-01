"""Child-only Dodongo's Cavern lobby-switch regression in AP and real UT.

Never collect room-clear events before removing prerequisites: these tests model
a fresh approach with no Lizalfos Soul, not losing a soul after clearing a room.
"""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
from NetUtils import convert_to_base_types
from worlds.soh_extreme._vendor_oot_soh.Enums import Events
from worlds.soh_extreme.EnemyRoomLogic import event_item
import argparse, json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
def ck(label,actual,expected=True):
 tests.append(dict(test=label,actual=bool(actual),expected=expected,passed=bool(actual)==expected))
 if bool(actual)!=expected:print('FAIL',label,actual,expected,flush=True)
options=dict(closed_forest='off',door_of_time='song_only',starting_age='child',
 shuffle_enemy_drops=True,shuffle_enemy_soul='individual_enemies',shuffle_grab=True,shuffle_climb=True,
 song_note_shuffle='off',shuffle_ocarina_buttons=False,start_with_ocarina='off',
 start_with_song_of_time=False,start_inventory={},start_inventory_from_pool={},
 tricks_in_logic=[],enable_all_tricks=False,shuffle_master_sword=True,start_with_master_sword=False)
def names(w):
 return [i.name for i in w.multiworld.itempool if i.player==w.player]+[l.item.name for l in w.get_locations()
  if l.address is not None and l.item and l.item.name in w.item_name_to_id]
def run(w,tag,mode='individual_enemies',adult=False):
 ev=tracker(w,a.ut_core)
 blocked={'Progressive Ocarina','Song of Time','Lizalfos and Dinolfos Soul','Enemy Soul'}
 base=[n for n in names(w) if n not in blocked]
 for has_soul in (False,True):
  soul='Enemy Soul' if mode=='all_enemies_as_1' else 'Lizalfos and Dinolfos Soul'
  result=ev(base+([soul] if has_soul else []))
  ck(tag+' time travel is unavailable '+str(has_soul),result.state.has(Events.TIME_TRAVEL,1),False)
  native_switch=result.state.has(event_item('LOGIC_DC_STAIRS_ROOM_DOOR'),1)
  ck(tag+' lobby switch '+str(has_soul),native_switch,adult or mode=='off' or has_soul)
  for i in range(1,4):
   name=f"Enemy Defeat: Dodongo's Cavern Room 10 Baby Dodongo {i}"
   expected=(adult or mode=='off' or has_soul) and (mode!='all_enemies_as_1' or has_soul)
   ck(tag+' AP '+name+' soul='+str(has_soul),w.get_location(name).can_reach(result.state),expected)
   ck(tag+' UT '+name+' soul='+str(has_soul),name in result.in_logic_locations,expected)
  if mode=='individual_enemies' and has_soul:
   no_baby=ev([n for n in base if n!='Baby Dodongo Soul']+[soul])
   ck(tag+' route open without Baby Dodongo Soul',no_baby.state.has(event_item('LOGIC_DC_STAIRS_ROOM_DOOR'),1))
   for i in range(1,4):
    name=f"Enemy Defeat: Dodongo's Cavern Room 10 Baby Dodongo {i}"
    ck(tag+' destination soul still required '+name,name in no_baby.in_logic_locations,False)
 return w
w=run(setup(930441,overrides=options,stop_before='pre_fill').worlds[1],'child individual')
slot=convert_to_base_types(w.fill_slot_data())
rw=setup(930441,overrides=dict(options,shuffle_enemy_soul='off'),passthrough=slot,stop_before='pre_fill').worlds[1]
run(rw,'slot reconstructed')
for mode in ('all_enemies_as_1','off'):
 run(setup(930442,overrides=dict(options,shuffle_enemy_soul=mode),stop_before='pre_fill').worlds[1],'child '+mode,mode)
run(setup(930443,overrides=dict(options,starting_age='adult'),stop_before='pre_fill').worlds[1],'adult real shortcut',adult=True)
report=dict(passed=all(t['passed'] for t in tests),assertions=len(tests),tests=tests,scope=__doc__)
a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2))
print('PASS' if report['passed'] else 'FAIL',len(tests),'DC lobby assertions');raise SystemExit(not report['passed'])
