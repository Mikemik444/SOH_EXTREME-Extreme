"""Ruto's carrying requirements in real generation/UT inventories, without injected events."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from NetUtils import convert_to_base_types
from pathlib import Path
import argparse, json

p=argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args();tests=[]
opts=dict(starting_age='child',closed_forest='off',kakariko_gate='open',
    door_of_time='song_only',start_with_song_of_time=False,song_note_shuffle='off',
    lock_overworld_doors=False,shuffle_ocarina_buttons=False,shuffle_grab=True,
    shuffle_speak=2,shuffle_npc_soul=True,start_inventory={},start_inventory_from_pool={},
    tricks_in_logic=[],enable_all_tricks=False)

def ck(label,actual,expected):
    tests.append(dict(test=label,actual=actual,expected=expected,passed=actual==expected))

def verify(w,label):
    ev=tracker(w,a.ut_core);o=w.options
    pool=[i.name for i in w.multiworld.itempool if i.code is not None]
    pool += [l.item.name for l in w.get_locations() if l.address is not None and l.item and l.item.code is not None]
    # Physical Strength #1 grants virtual Grab when shuffled. Remove those
    # items too, otherwise a supposedly Grab-free inventory still has Grab.
    capabilities={'Grab / Power Bracelet','Strength Upgrade','Progressive Strength Upgrade','NPC Soul','Speak','Speak Zora'}
    pool=[n for n in pool if n not in capabilities|{'Song of Time'}]
    spell='Speak' if o.shuffle_speak.value==1 else 'Speak Zora'
    for bits in range(8):
        inv=pool+[name for bit,name in ((1,'Grab / Power Bracelet'),(2,'NPC Soul'),(4,spell)) if bits&bit]
        result=ev(inv)
        tag=f'{label}/{bits}'
        ck(tag+' actual Grab ownership',result.state.has('Grab / Power Bracelet',1),bool(bits&1))
        carry=(bool(bits&1) or not o.shuffle_grab.value) and (bool(bits&2) or not o.shuffle_npc_soul.value) and (bool(bits&4) or not o.shuffle_speak.value)
        child=o.starting_age.current_key=='child'
        reachable=carry and child
        ck(tag+' no age switching',result.state.has('Time Travel',1),False)
        event='Jabu Jabus Belly Ruto In 1F Rescued'
        ck(tag+' Ruto rescue event',result.state.has(event,1),reachable)
        for name in ('Jabu Jabus Belly Boomerang Chest','Jabu Jabus Belly Map Chest','Jabu Jabus Belly Compass Chest',
                     'Jabu Jabus Belly Above Big Octo Pot 1','Jabu Jabus Belly Barinade Heart Container','Barinade'):
            loc=w.get_location(name)
            ck(tag+' AP '+name,loc.can_reach(result.state),reachable)
            ck(tag+' UT '+name,name in result.in_logic_locations,reachable)
        # Removing Grab alone must not hide the initial accessible dungeon.
        if (bits&6)==6:
            for name in ('Jabu Jabus Belly Platform Room Small Crate 1','Jabu Jabus Belly Platform Room Small Crate 2'):
                ck(tag+' early AP '+name,w.get_location(name).can_reach(result.state),child)
                ck(tag+' early UT '+name,name in result.in_logic_locations,child)
        # Enemy room routes already use the native rescue event. Verify they
        # agree with the corrected stock-check graph when those checks exist.
        for loc in w.get_locations():
            if loc.name.startswith('Enemy Defeat: Jabu Jabu') and any(part in loc.name for part in ('Room 6 ', 'Room 10 ', 'Room 15 Big Octo')):
                ck(tag+' enemy AP '+loc.name,loc.can_reach(result.state),reachable)
                ck(tag+' enemy UT '+loc.name,loc.name in result.in_logic_locations,reachable)
    result=ev(pool+['Strength Upgrade','NPC Soul',spell])
    ck(label+' physical strength grants shuffled Grab',result.state.has('Grab / Power Bracelet',1),bool(o.shuffle_grab.value))
    ck(label+' physical strength permits rescue',result.state.has('Jabu Jabus Belly Ruto In 1F Rescued',1),o.starting_age.current_key=='child')

w=setup(100160,overrides=opts,stop_before='pre_fill').worlds[1]
verify(w,'individual')
slot=convert_to_base_types(w.fill_slot_data())
for label,changes,passthrough in (
    ('shared speech',{'shuffle_speak':1},None),
    ('grab innate',{'shuffle_grab':False},None),
    ('NPC innate',{'shuffle_npc_soul':False},None),
    ('speech innate',{'shuffle_speak':0},None),
    ('all innate',{'shuffle_grab':False,'shuffle_npc_soul':False,'shuffle_speak':0},None),
    ('no private graph',{'shuffle_enemy_drops':False,'shuffle_silver':0},None),
    ('adult without child access',{'starting_age':'adult'},None),
    ('restored slot',{'shuffle_grab':False,'shuffle_npc_soul':False,'shuffle_speak':0},slot),
):
    world=setup(100160,overrides={**opts,**changes},passthrough=passthrough,stop_before='pre_fill').worlds[1]
    verify(world,label)
passed=all(t['passed'] for t in tests)
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(dict(passed=passed,checks=len(tests),failures=sum(not t['passed'] for t in tests),tests=tests),indent=2))
print('RESULT',passed,len(tests),flush=True)
for t in [t for t in tests if not t['passed']][:20]:print(t)
raise SystemExit(not passed)
