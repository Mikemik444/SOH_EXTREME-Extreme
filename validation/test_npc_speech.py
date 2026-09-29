"""Conversation identity / generation / actual Universal Tracker regressions."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from worlds.soh_extreme import NpcSpeech
from worlds.soh_extreme.SpeechLocations import SPEECH_LOCATION_NAME_TO_ID
from worlds.soh_extreme._vendor_oot_soh.Enums import Regions
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--ut-core',type=Path,required=True);p.add_argument('--old-slot',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
def ck(label,actual,expected=True):tests.append(dict(test=label,actual=actual,expected=expected,passed=actual==expected))
common=dict(npc_speech_sanity=True,shuffle_npc_soul=True,shuffle_speak='individual_languages',closed_forest='on',shuffle_climb=True,starting_age='child',enable_all_tricks=False,tricks_in_logic=[])
m=setup(290940,overrides=common,stop_before='pre_fill');w=m.worlds[1];evaluate=tracker(w,a.ut_core)
active={l.name:l.address for l in w.get_locations() if l.address is not None}
ck('new identity schema',NpcSpeech.identity_version(w),2)
ck('legacy locations absent from new seed',not set(active)&set(SPEECH_LOCATION_NAME_TO_ID))
ck('all catalog names/IDs unique',len(NpcSpeech.NAME_TO_ID)==len(NpcSpeech.CATALOG)==len(set(NpcSpeech.NAME_TO_ID.values())))
ck('all native actor IDs have routes',all(e['routes'] or e.get('native_rc') for e in NpcSpeech.CATALOG))
kokiri=[e for e in NpcSpeech.CATALOG if any(m[0]=='ACTOR_EN_KO' for m in e['matches'])]
ck('all thirteen Kokiri children have identities',len(kokiri),13)
ck('one Kokiri shopkeeper, no shelves',len([n for n in active if n=='NPC Speech: Kokiri Shopkeeper']),1)
exclude={'NPC Soul','Climb','Kokiri Sword','Progressive Shield','Deku Shield','Hylian Shield','Mirror Shield','Speak',*(f'Speak {x}' for x in NpcSpeech.LANGUAGES)}
base=[i.name for i in m.itempool if i.name not in exclude]
for soul,language,climb in [(False,'Kokiri',True),(True,'Hylian',True),(True,'Kokiri',False),(True,'Kokiri',True)]:
 result=evaluate(base+(['NPC Soul'] if soul else [])+['Speak '+language]+(['Climb'] if climb else []))
 for entry in kokiri:
  expected=soul and language=='Kokiri' and (climb or all('climb' not in route['gates'] for route in entry['routes']))
  name=entry['name'];ck(f'{soul}/{language}/{climb} AP {name}',w.get_location(name).can_reach(result.state),expected)
  ck(f'{soul}/{language}/{climb} UT {name}',name in result.in_logic_locations,expected)
 for name in ('NPC Speech: Mido','NPC Speech: Kokiri Shopkeeper'):
  expected=soul and language=='Kokiri'
  ck(f'{soul}/{language}/{climb} {name}',name in result.in_logic_locations,expected)
 # These conversation assertions deliberately omit Sword and Shield. The
 # separate native reward/path checks retain their independently tested rules.
slot=w.fill_slot_data();ck('schema exported',slot['npc_speech_identity_version'],2)
rebuilt=setup(290940,passthrough=slot,stop_before='pre_fill').worlds[1]
ck('new slot recreates exact network identities',{l.name:l.address for l in rebuilt.get_locations() if l.address is not None},active)
old=json.loads(a.old_slot.read_text(encoding='utf-8'));old.pop('npc_speech_identity_version',None)
legacy=setup(290941,passthrough=old,stop_before='pre_fill').worlds[1]
ck('old slot keeps legacy schema',NpcSpeech.identity_version(legacy),1)
old_speech={l.name:l.address for l in legacy.get_locations() if l.name.startswith('NPC Speech:')}
ck('old slot keeps all 114 locations',old_speech,SPEECH_LOCATION_NAME_TO_ID)
ck('old slot has no new names',not set(old_speech)&set(NpcSpeech.NAME_TO_ID))
# The off option adds no speech checks, even though they exist in the datapackage.
off=setup(290942,overrides={'npc_speech_sanity':False},stop_before='pre_fill').worlds[1]
ck('disabled adds no checks',not any(l.name in NpcSpeech.NAME_TO_ID or l.name in SPEECH_LOCATION_NAME_TO_ID for l in off.get_locations()))
# New entry language is explicit: area does not turn the Hylian Bean Salesman into a Zora.
ck('Bean Salesman Hylian',NpcSpeech.BY_NAME['NPC Speech: Magic Bean Salesman']['language'],'Hylian')
ck('scrub language Deku',all(e['language']=='Deku' for e in NpcSpeech.CATALOG if e.get('native_rc')))
ck('every NPC has a tracker area',all(NpcSpeech.display_region(w.get_location(n)) not in ('','Menu') for n in w._npc_conversations))
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),catalog=len(NpcSpeech.CATALOG),tests=tests),indent=2),encoding='utf-8')
print('PASS' if passed else 'FAIL',len(tests),'assertions')
for t in tests:
 if not t['passed']:print(t)
raise SystemExit(0 if passed else 1)
