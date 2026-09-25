"""Check source-proven necessary local prerequisites against the actual AP graph.

Unrecognized expressions provide NO requirements. OR branches intersect their
mandatory requirements, so this audit never invents an AND out of alternatives.
This does not establish exact room access or certify unrecognized expressions.
"""
from __future__ import annotations
import re,json,argparse,collections
from pathlib import Path
from run_case import setup,BOOTSTRAP
from source_index import body_at,split_top,native_metadata,native_sources,normalize,mask_comments
from location_source_audit import collect

ABILITY={
 'RG_POWER_BRACELET':('Grab / Power Bracelet','shuffle_grab'),
 'RG_CLIMB':('Climb','shuffle_climb'), 'RG_CRAWL':('Crawl','shuffle_crawl'),
 'RG_ROLL':('Roll','shuffle_roll'), 'RG_BRONZE_SCALE':('Swim','shuffle_swim'),
 'RG_NPC_SOUL':('NPC Soul','shuffle_npc_soul'), 'RG_POT_SOUL':('Pot Soul','shuffle_pot_soul'),
 'RG_CRATE_SOUL':('Crate Soul','shuffle_crate_soul'),
 'RG_GRASS_SOUL':('Grass / Bush Soul','shuffle_grass_bush_soul'),
 'RG_TREE_SOUL':('Tree Soul','shuffle_tree_soul'),
 'RG_ROCK_BOULDER_SOUL':('Rock / Boulder Soul','shuffle_rock_boulder_soul'),
 'RG_BEEHIVE_SOUL':('Beehive Soul','shuffle_beehive_soul'),
 'RG_SIGN_SOUL':('Sign Soul','shuffle_sign_soul'),
 'RG_SKULLTULA_SOUL':('Skulltula Soul','shuffle_skulltula_soul'),
 'RG_BUSINESS_SCRUB_SOUL':('Scrub Soul','shuffle_business_scrub_soul'),
 'RG_SHOVEL':('Shovel','shuffle_shovel'),
}
SOUL_CONSTRUCTORS={
 'Pot':'RG_POT_SOUL','Crate':'RG_CRATE_SOUL','SmallCrate':'RG_CRATE_SOUL','NLCrate':'RG_CRATE_SOUL',
 'Grass':'RG_GRASS_SOUL','Bush':'RG_GRASS_SOUL','Tree':'RG_TREE_SOUL','NLTree':'RG_TREE_SOUL',
 'Rock':'RG_ROCK_BOULDER_SOUL','Boulder':'RG_ROCK_BOULDER_SOUL','Sign':'RG_SIGN_SOUL',
 'GSToken':'RG_SKULLTULA_SOUL',
}
HELPERS={
 'CanBreakPots':{'RG_POT_SOUL'},'CanBreakCrates':{'RG_CRATE_SOUL'},'CanBreakSmallCrates':{'RG_CRATE_SOUL'},
 'CanCollectGrass':{'RG_GRASS_SOUL'},'CanCutShrubs':{'RG_GRASS_SOUL'},
 'CanPickUpGrass':{'RG_GRASS_SOUL','RG_POWER_BRACELET'},
 'CanBreakRocks':{'RG_ROCK_BOULDER_SOUL'},'CanBonkTrees':{'RG_TREE_SOUL','RG_ROLL'},
 'CanRead':{'RG_SIGN_SOUL'}, 'CanBreakLowerBeehives':{'RG_BEEHIVE_SOUL'},'CanBreakUpperBeehives':{'RG_BEEHIVE_SOUL'},
 'CanTalkToDampe':{'RG_NPC_SOUL','RG_SPEAK_HYLIAN'},
}

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
    m=re.fullmatch(r'logic->(?:HasItem|CanUse)\((RG_\w+)\)',expr)
    if m:
        item=m[1]
        if item in ABILITY or item.startswith(('RG_SPEAK_','RG_ANIMAL_SOUL_')):return {item}
        if item=='RG_IRON_BOOTS':return {'RG_BRONZE_SCALE'}
        if item=='RG_FISHING_POLE':return {'RG_NPC_SOUL','RG_SPEAK_HYLIAN','RG_ANIMAL_SOUL_FISH'}
    m=re.fullmatch(r'logic->HasAnimalSoul\((RG_ANIMAL_SOUL_\w+)\)',expr)
    if m:return {m[1]}
    m=re.fullmatch(r'logic->(\w+)\(\)',expr)
    if m:return HELPERS.get(m[1],set()).copy()
    return set()


def expected_for(row,srcroot):
    md=row.get('native_metadata')
    if not md:return set()
    defs=[s for s in row['native_sources'] if '_MQ_' not in s['region']]
    result=set.intersection(*(mandatory(s['condition']) for s in defs)) if defs else set()
    result.update([SOUL_CONSTRUCTORS[md['constructor']]] if md['constructor'] in SOUL_CONSTRUCTORS else [])
    if md['type']=='RCTYPE_BEEHIVE':result.add('RG_BEEHIVE_SOUL')
    if md['type']=='RCTYPE_SCRUB':result.update(('RG_NPC_SOUL','RG_SPEAK_DEKU','RG_BUSINESS_SCRUB_SOUL'))
    if md['scene']=='SCENE_GROTTOS':result.add('RG_SHOVEL')
    # This native classifier controls actor existence. No guessed NPC language.
    text=(srcroot/'soh/Enhancements/randomizer/location_access.cpp').read_text()
    section=text.split('static bool MegaIsNpcLocationActor',1)[1].split('static bool MegaIsAnimalLocationActor',1)[0]
    npc_actors=set(re.findall('case (ACTOR_\\w+)',section))
    if md['actor'] in npc_actors:result.add('RG_NPC_SOUL')
    if md['type'] in ('RCTYPE_SHOP','RCTYPE_MERCHANT'):result.add('RG_NPC_SOUL')
    return result


def resolve_item(token,w):
    if token in ABILITY:
        name,option=ABILITY[token]
        return name if getattr(w.options,option).value else None
    if token.startswith('RG_SPEAK_'):
        mode=w.options.shuffle_speak.value
        if not mode:return None
        return 'Speak' if mode==1 else 'Speak '+token[len('RG_SPEAK_'):].title()
    if token.startswith('RG_ANIMAL_SOUL_'):
        mode=w.options.shuffle_animal_soul.value
        if not mode:return None
        return 'Animal Soul' if mode==1 else token[len('RG_ANIMAL_SOUL_'):].title()+' Soul'
    raise ValueError(token)

if __name__=='__main__':
    p=argparse.ArgumentParser(parents=[BOOTSTRAP]);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    mw=setup(1717,overrides={'boss_key_shuffle':'anywhere','shuffle_roll':True,'shuffle_open_chest':'progressive'},stop_before='pre_fill');w=mw.worlds[1]
    rows,sources=collect(a.source_root,w)
    expectations={r['name']:sorted(expected_for(r,a.source_root)) for r in rows if r['kind'] in ('stock','fork')}
    allstate=mw.get_all_state(False)
    names=sorted({resolve_item(t,w) for ts in expectations.values() for t in ts}-{None})
    failures=[];counts=collections.Counter()
    for name in names:
        state=allstate.copy()
        # Swim is virtual: its first Progressive Scale receipt grants it.
        # Clearing only the virtual flag while retaining scales is not a valid
        # gameplay inventory. Remove the real receipts through world.remove.
        if name == 'Swim':
            while state.count('Progressive Scale', 1):
                state.remove(w.create_item('Progressive Scale'))
        if name != 'Swim':
            while state.count(name,1):
                previous=state.count(name,1)
                state.remove(w.create_item(name))
                assert state.count(name,1)<previous,(name,'removal did not progress')
        assert state.count(name,1)==0,name
        for r in rows:
            ts=expectations.get(r['name'],())
            if name not in {resolve_item(t,w) for t in ts}:continue
            loc=w.get_location(r['name']);counts[name]+=1
            if loc.can_reach(state):failures.append(dict(id=r['id'],name=r['name'],rc=r['rc'],missing=name,source=r['native_sources']))
    out=dict(scope='Necessary direct prerequisites only. A full inventory is used minus one required item; historical event flags are retained. No physical certification.',tested=sum(counts.values()),counts=dict(counts),failure_count=len(failures),failures=failures,expectations=expectations)
    a.report.write_text(json.dumps(out,indent=2));print({k:v for k,v in out.items() if k not in ('failures','expectations')},flush=True)
    for fail in failures:print(fail['missing'],fail['name'],flush=True)
