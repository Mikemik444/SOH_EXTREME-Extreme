"""Castle physical routes and Skip Zelda regression tests on the actual AP graph."""
import sys,json,itertools,traceback,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_case import setup,BOOTSTRAP
from BaseClasses import CollectionState
from NetUtils import convert_to_base_types
from worlds.soh_extreme import SOH_ITEM_ALIASES
p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
results=[]
def ck(name,actual,expected):
    results.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
    if actual!=expected:print('FAIL',name,actual,'expected',expected,flush=True)
def make_state(mw,w,names):
    blocked={'Climb','Crawl','NPC Soul','Speak','Speak Hylian','Speak Gerudo','Speak Kokiri','Speak Goron','Speak Zora','Speak Deku',
      'Grab / Power Bracelet','Time Travel','Progressive Hookshot','Hookshot','Longshot','Hover Boots',*SOH_ITEM_ALIASES['Strength Upgrade']}
    state=CollectionState(mw)
    for it in mw.precollected_items[1]:
        if it.name in blocked:state.remove(it)
    for it in list(mw.itempool)+[l.item for l in mw.get_filled_locations() if l.address is not None and l.item]:
        if it.name not in blocked:state.collect(it,True)
    for n in names:state.collect(w.create_item(n),True)
    state.sweep_for_advancements([l for l in mw.get_filled_locations() if l.address is None and l.item and l.item.name not in blocked])
    return state
try:
    slot=None
    for label,skip,mode,npc_shuffle in [('skip-individual',True,2,True),('quest-individual',False,2,True),('skip-combined',True,1,True),('quest-innate-speech-soul',False,0,False),('UT-restored',True,2,True)]:
        opts={'skip_child_zelda':skip,'shuffle_climb':True,'shuffle_grab':True,'shuffle_crawl':True,'shuffle_npc_soul':npc_shuffle,'shuffle_speak':mode,'starting_age':'child'}
        if label=='UT-restored': opts.update(skip_child_zelda=False,shuffle_climb=False,shuffle_grab=False,shuffle_crawl=False,shuffle_npc_soul=False,shuffle_speak=0)
        mw=setup(1418,overrides=opts,passthrough=slot if label=='UT-restored' else None);w=mw.worlds[1]
        opts=w.options;skip=bool(opts.skip_child_zelda.value);mode=opts.shuffle_speak.value;npc_shuffle=bool(opts.shuffle_npc_soul.value)
        if label=='skip-individual':slot=convert_to_base_types(w.fill_slot_data())
        ck(label+' physical garden exists',w.get_region('HC Garden').name,'HC Garden')
        ck(label+' Impa parent',w.get_location('Song from Impa').parent_region.name,'Menu' if skip else 'HC Garden')
        windows=[l for l in w.get_locations() if 'Hc Wonder Courtyard' in l.name]
        ck(label+' two window checks',len(windows),2)
        for l in windows:ck(label+' '+l.name+' exact parent',l.parent_region.name,'HC Garden')
        for climb,npc,speak,grab,crawl in itertools.product((False,True),repeat=5):
            names=[]
            if climb:names.append('Climb')
            if npc:names.append('NPC Soul')
            if speak and mode:names.append('Speak Hylian' if mode==2 else 'Speak')
            if grab:names.append(SOH_ITEM_ALIASES['Strength Upgrade'][0])
            if crawl:names.append('Crawl')
            state=make_state(mw,w,names)
            enpc=npc or not npc_shuffle;espeak=speak or not mode
            key=f'{label}:C{int(climb)} N{int(npc)} S{int(speak)} G{int(grab)} R{int(crawl)}'
            ck(key+' front',w.get_region('Hyrule Castle Grounds').can_reach(state),True)
            ck(key+' past gate',w.get_region('HC Past Gate').can_reach(state),climb or (enpc and espeak))
            ck(key+' moat',w.get_region('HC Moat').can_reach(state),climb)
            garden=climb and grab and crawl and (skip or (enpc and espeak))
            ck(key+' garden',w.get_region('HC Garden').can_reach(state),garden)
            for loc in windows:ck(key+' '+loc.name,loc.can_reach(state),garden)
            ck(key+' Impa',w.get_location('Song from Impa').can_reach(state),True if skip else (garden and enpc and espeak))
        if mode==2:
            state=make_state(mw,w,['NPC Soul','Speak Gerudo'])
            ck(label+' wrong language cannot bribe guard',w.get_region('HC Past Gate').can_reach(state),False)
        if label=='UT-restored':
            ck('UT honors server skip setting',skip,True)
            ck('UT honors server NPC/speech settings',[npc_shuffle,mode],[True,2])
        all_state = mw.get_all_state(False)
        blocked=[l.name for l in w.get_locations() if not l.can_reach(all_state)]
        ck(label+' full inventory no blocked checks',blocked,[])
except Exception as e:
    traceback.print_exc();results.append(dict(name='exception',passed=False,error=repr(e),traceback=traceback.format_exc()))
report=dict(checks=results,total=len(results),failures=sum(not x['passed'] for x in results),scope='AP graph construction, real CollectionState, virtual items and slot-data regeneration. Test-only schema/bsdiff adapters. No in-game physics or full seed fill.')
args.report.write_text(json.dumps(report,indent=2));print('TOTAL',report['total'],'FAILURES',report['failures'],flush=True);raise SystemExit(bool(report['failures']))
