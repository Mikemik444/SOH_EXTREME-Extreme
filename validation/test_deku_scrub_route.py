"""Real AP/UT checks beyond the talking scrub, including its defeat checks."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args(); tests=[]
opts=dict(starting_age='child',closed_forest='off',kakariko_gate='open',
    door_of_time='song_only',start_with_song_of_time=False,song_note_shuffle='off',
    lock_overworld_doors=False,shuffle_ocarina_buttons=False,
    shuffle_climb=True,shuffle_open_chest=True,shuffle_enemy_soul=2,
    shuffle_speak=2,shuffle_npc_soul=True,shuffle_business_scrub_soul=True,
    start_inventory={},start_inventory_from_pool={},tricks_in_logic=[],enable_all_tricks=False)
scrub='Enemy Defeat: Deku Tree Room 1 Deku Scrub 1'
chests=['Deku Tree Slingshot Chest','Deku Tree Slingshot Room Side Chest']

def ck(label,actual,expected):
    tests.append(dict(test=label,actual=actual,expected=expected,passed=actual==expected))

def verify(w,label):
    ev=tracker(w,a.ut_core);o=w.options
    room=w.get_region('Deku Tree Slingshot Room')
    pickups=[l.name for l in room.locations if l.address is not None]
    ck(label+' both chests covered',all(n in pickups for n in chests),True)
    for mask in range(64):
        inv=['Kokiri Sword','Grass / Bush Soul']
        for bit,item in ((1,'Climb'),(2,'Enemy Soul' if o.shuffle_enemy_soul.value==1 else 'Deku Scrub Soul'),
                (4,'Speak' if o.shuffle_speak.value==1 else 'Speak Deku'),(8,'Open Chest'),
                (16,'NPC Soul'),(32,'Scrub Soul')):
            if mask&bit:inv.append(item)
        soul=bool(mask&2) or not o.shuffle_enemy_soul.value
        speech=bool(mask&4) or not o.shuffle_speak.value
        for shield in (0,1,2):
            w._extreme_live_shields=shield
            # Hylian Shield on child and owned adult Hammer cannot substitute.
            result=ev(inv+['Megaton Hammer','Deku Shield'])
            approach=bool(mask&1)
            clear=approach and soul and speech and shield==1
            tag=f'{label}/{mask}/live shield={shield}'
            ck(tag+' no time travel',result.state.has('Time Travel',1),False)
            ck(tag+' middle room approach',w.get_region('Deku Tree 2F Middle Room').can_reach(result.state),approach)
            ck(tag+' slingshot region',room.can_reach(result.state),clear)
            ck(tag+' private slingshot region',w.get_region('EXTREME Enemy Route: Deku Tree Slingshot Room').can_reach(result.state),clear)
            for name in pickups+[scrub]:
                want=clear and (name not in chests or bool(mask&8))
                ck(tag+' AP '+name,w.get_location(name).can_reach(result.state),want)
                ck(tag+' UT '+name,name in result.in_logic_locations,want)
    # A merchant soul or unrelated language cannot replace this enemy's soul
    # and Deku language, even when the shield and physical approach are valid.
    w._extreme_live_shields=1
    result=ev(['Climb','Open Chest','Scrub Soul','NPC Soul','Speak Hylian'])
    want=not o.shuffle_enemy_soul.value and not o.shuffle_speak.value
    ck(label+' wrong souls/language',chests[0] in result.in_logic_locations,want)

w=setup(100157,overrides=opts,stop_before='pre_fill').worlds[1]
verify(w,'individual')
slot=convert_to_base_types(w.fill_slot_data())
for label,changes,passthrough in (
    ('shared',{'shuffle_enemy_soul':1,'shuffle_speak':1},None),
    ('enemy innate',{'shuffle_enemy_soul':0},None),
    ('speech innate',{'shuffle_speak':0},None),
    ('restored',{'shuffle_enemy_soul':0,'shuffle_speak':0},slot),
):
    world=setup(100157,overrides={**opts,**changes},passthrough=passthrough,stop_before='pre_fill').worlds[1]
    verify(world,label)

# Start fresh with each missing prerequisite. Never copy already-latched clear
# events from an all-inventory state into the negative inventory.
w._extreme_live_shields=1;ev=tracker(w,a.ut_core)
pool=[i.name for i in w.multiworld.itempool if i.code is not None]
pool += [l.item.name for l in w.get_locations() if l.address is not None and l.item and l.item.code is not None]
for missing in (set(),{'Deku Scrub Soul'},{'Speak Deku'},{'NPC Soul','Scrub Soul'}):
    result=ev([n for n in pool if n not in missing|{'Song of Time'}])
    want=not bool(missing&{'Deku Scrub Soul','Speak Deku'})
    ck(str(missing)+' outside boss reachable',w.get_region('Deku Tree Outside Boss Room').can_reach(result.state),True)
    ck(str(missing)+' boss door',w.get_region('Deku Tree Boss Entryway').can_reach(result.state),want)
    for l in w.get_locations():
        if l.name.startswith('Enemy Defeat: Deku Tree Room 9 Deku Scrub'):
            ck(str(missing)+' boss scrub AP '+l.name,l.can_reach(result.state),want)
            ck(str(missing)+' boss scrub UT '+l.name,l.name in result.in_logic_locations,want)

passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),failures=sum(not t['passed'] for t in tests),tests=tests),indent=2))
print('RESULT',passed,len(tests),flush=True)
for t in [t for t in tests if not t['passed']][:20]:print(t)
raise SystemExit(not passed)
