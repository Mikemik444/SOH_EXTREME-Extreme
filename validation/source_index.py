"""Source-only C++ location/metadata indexing. No execution or guessed coordinates.

Names are matched only when exactly unique after punctuation/case normalization.
This index is evidence of a definition, not a physical route verification.
"""
from __future__ import annotations
import re, collections, json
from pathlib import Path


def mask_comments(text: str) -> str:
    pat=r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pat, lambda m:re.sub(r'[^\n]',' ',m[0]) if m[0].startswith('/') else m[0],text)


def split_top(text: str, separator: str=',') -> list[str]:
    out=[];start=0;depth=0;i=0;quote=None
    while i<len(text):
        c=text[i]
        if quote:
            if c=='\\':i+=2;continue
            if c==quote:quote=None
        elif c in '\"\'':quote=c
        elif c in '([{':depth+=1
        elif c in ')]}':depth-=1
        elif depth==0 and text.startswith(separator,i):
            out.append(text[start:i].strip());i+=len(separator);start=i;continue
        i+=1
    out.append(text[start:].strip());return out


def body_at(text: str, start: int) -> tuple[str,int]:
    depth=1;i=start;quote=None
    while i<len(text):
        c=text[i]
        if quote:
            if c=='\\':i+=2;continue
            if c==quote:quote=None
        elif c in '\"\'':quote=c
        elif c=='(':depth+=1
        elif c==')':
            depth-=1
            if depth==0:return text[start:i],i
        i+=1
    raise ValueError('unbalanced source expression')


def normalize(name: str) -> str:
    return re.sub('[^A-Z0-9]','',name.upper())


def native_sources(root: Path):
    records=collections.defaultdict(list)
    regions={}
    for file in sorted((root/'soh/Enhancements/randomizer/location_access').rglob('*.cpp')):
        text=mask_comments(file.read_text())
        defs=list(re.finditer(r'areaTable\[(RR_\w+)\]\s*=\s*Region\(',text))
        for k,d in enumerate(defs):
            section=text[d.end():defs[k+1].start() if k+1<len(defs) else len(text)]
            name=re.match(r'\s*"([^"]*)"',section)
            base=dict(file=str(file.relative_to(root)),line=text.count('\n',0,d.start())+1)
            reg=dict(name=name[1] if name else None,exits=[],events=[],**base)
            for macro in ('LOCATION','ENTRANCE','EVENT_ACCESS'):
                for m in re.finditer(r'\b'+macro+r'\(',section):
                    body,end=body_at(section,m.end());args=split_top(body)
                    # Two macro arguments plus optional entrance metadata in some forks.
                    if len(args)<2: raise ValueError((file,macro,args))
                    pos=d.end()+m.start()
                    rec=dict(region=d[1],condition=args[1],file=base['file'],line=text.count('\n',0,pos)+1)
                    if macro=='LOCATION':records[args[0]].append(rec)
                    elif macro=='ENTRANCE':reg['exits'].append(dict(target=args[0],**rec))
                    else:reg['events'].append(dict(event=args[0],**rec))
            regions[d[1]]=reg
    return records,regions


def native_metadata(root: Path):
    # Same area ordering as production SohUtils::GetRCAreaPrefix / rcareaPrefixes.
    area_names=('KOKIRI_FOREST','LOST_WOODS','SACRED_FOREST_MEADOW','HYRULE_FIELD',
      'LAKE_HYLIA','GERUDO_VALLEY','GERUDO_FORTRESS','WASTELAND','DESERT_COLOSSUS',
      'MARKET','HYRULE_CASTLE','KAKARIKO_VILLAGE','GRAVEYARD','DEATH_MOUNTAIN_TRAIL',
      'GORON_CITY','DEATH_MOUNTAIN_CRATER','ZORAS_RIVER','ZORAS_DOMAIN','ZORAS_FOUNTAIN',
      'LON_LON_RANCH','DEKU_TREE','DODONGOS_CAVERN','JABU_JABUS_BELLY','FOREST_TEMPLE',
      'FIRE_TEMPLE','WATER_TEMPLE','SPIRIT_TEMPLE','SHADOW_TEMPLE','BOTTOM_OF_THE_WELL',
      'ICE_CAVERN','GERUDO_TRAINING_GROUND','GANONS_CASTLE')
    util=(root/'soh/util.cpp').read_text();prefix_body=util.split('rcareaPrefixes = {',1)[1].split('};',1)[0]
    prefixes=re.findall(r'"([^\"]*)"',prefix_body)
    assert len(prefixes)==len(area_names),(len(prefixes),len(area_names))
    area_prefix={'RCAREA_'+a:p for a,p in zip(area_names,prefixes)}
    impl=mask_comments((root/'soh/Enhancements/randomizer/location.cpp').read_text())
    scene_area={}
    for m in re.finditer(r'((?:\s*case\s+SCENE_\w+\s*:)+)\s*return\s+(RCAREA_\w+)\s*;',impl):
        for s in re.findall(r'case\s+(SCENE_\w+)',m[1]):scene_area[s]=m[2]
    data={}
    for f in sorted((root/'soh/Enhancements/randomizer').glob('*.cpp')):
        text=mask_comments(f.read_text())
        for m in re.finditer(r'locationTable\[(RC_\w+)\]\s*=\s*Location::(\w+)\(',text):
            body,end=body_at(text,m.end());a=split_top(body)
            assert a[0]==m[1],(f,m[1],a[0])
            area=next((x for x in a if x.startswith('RCAREA_')),None)
            scene=next((x for x in a if x.startswith('SCENE_')),None)
            area=area or scene_area.get(scene)
            actor=next((x for x in a if x.startswith('ACTOR_')),None)
            quest=next((x for x in a if x.startswith('RCQUEST_')),None)
            typ=next((x for x in a if x.startswith('RCTYPE_')),None)
            strings=[json.loads(x) for x in a if re.fullmatch(r'"(?:\\.|[^"\\])*"',x)]
            short=strings[0] if strings else None
            # Base has one overload with explicit spoilerName after shortName.
            name=(strings[1] if len(strings)>1 else (area_prefix.get(area,'')+' '+short).strip() if short else None)
            rec=dict(rc=m[1],constructor=m[2],quest=quest,type=typ,area=area,scene=scene,
                     actor=actor,short_name=short,spoiler_name=name,
                     file=str(f.relative_to(root)),line=text.count('\n',0,m.start())+1)
            if actor:
                i=a.index(actor);rec['actor_params']=a[i+2] if i+2<len(a) else None
            data[m[1]]=rec
    return data


def mandatory_age(e):
 e=e.strip()
 while e.startswith('('):
  inner,end=body_at(e,1)
  if end!=len(e)-1:break
  e=inner.strip()
 parts=split_top(e,'||')
 if len(parts)>1:return set.intersection(*(mandatory_age(p) for p in parts))
 parts=split_top(e,'&&')
 if len(parts)>1:return set.union(*(mandatory_age(p) for p in parts))
 return {e} if e in ('logic->IsChild','logic->IsAdult') else set()



def mandatory_time(e):
 e=e.strip()
 while e.startswith('('):
  inner,end=body_at(e,1)
  if end!=len(e)-1:break
  e=inner.strip()
 parts=split_top(e,'||')
 if len(parts)>1:return set.intersection(*(mandatory_time(p)for p in parts))
 parts=split_top(e,'&&')
 if len(parts)>1:return set.union(*(mandatory_time(p)for p in parts))
 return {e} if e in ('logic->AtDay','logic->AtNight') else set()

