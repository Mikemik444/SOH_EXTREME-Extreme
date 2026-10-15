"""Export physical scene portals, not logical region edges. IDs derive from engine indices.

The explicit AP bindings below account for contracted/renamed regions. Every
binding is checked against the live AP graph by SceneTransitions.install_rules.
"""
from pathlib import Path
import ast, json, re
from generate_finder_scenes import catalogues

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'soh/Enhancements/randomizer'
BASE = 11000000
ALIASES = {
    'THE_LOST_WOODS':'LOST_WOODS', 'THE_MARKET':'MARKET',
    'LH_FISHING_POND':'LH_FISHING_HOLE', 'BOTW_ENTRYWAY':'BOTTOM_OF_THE_WELL_ENTRYWAY',
    'KF_LINKS_PORCH':'KOKIRI_FOREST', 'KF_OUTSIDE_LOST_WOODS':'KOKIRI_FOREST',
    'KAK_ODD_POTION_BUILDING':'KAK_GRANNYS_POTION_SHOP', 'KAK_WINDMILL_LOWER':'KAK_WINDMILL',
    'KAK_POTION_SHOP':'KAK_POTION_SHOP_FRONT', 'KAK_BEHIND_POTION_SHOP':'KAK_BACKYARD',
    'GF_OUTSKIRTS':'GERUDO_FORTRESS_OUTSKIRTS', 'ZORAS_RIVER':'ZORA_RIVER', 'ZR_ATOP_LADDER':'ZORA_RIVER',
    'DMC_TEMPLE_EXIT':'DMC_CENTRAL_LOCAL', 'DMC_TEMPLE_ENTRY':'DMC_CENTRAL_LOCAL',
    'DMC_BLOCKED_EXIT':'DMC_LOWER_NEARBY', 'DMC_BLOCKED_ENTRY':'DMC_LOWER_LOCAL',
    'DMC_POT_GROTTO_EXIT':'DMC_LOWER_NEARBY', 'DMC_POT_GROTTO_ENTRY':'DMC_LOWER_LOCAL',
    'DMC_SCRUB_GROTTO':'DMC_HAMMER_GROTTO', 'DMC_ROCK_GROTTO':'DMC_UPPER_NEARBY',
    'DMC_ROCKS_GROTTO_ENTRY':'DMC_UPPER_LOCAL', 'DMC_POTS_ENTRY':'DMC_LOWER_NEARBY',
    'DMC_POTS':'DMC_LOWER_NEARBY', 'DMC_UPPER_ENTRY':'DMC_UPPER_NEARBY',
    'DMC_CRATE':'DMC_UPPER_NEARBY', 'DMC_PAD_ENTRY':'DMC_CENTRAL_LOCAL',
    'DEATH_MOUNTAIN_ROCKFALL':'DEATH_MOUNTAIN_TRAIL',
    'SFM_OUTSIDE_FAIRY_GROTTO':'SACRED_FOREST_MEADOW', 'HF_TO_LAKE_HYLIA':'HYRULE_FIELD',
    'GANONS_TOWER_STAIRS_1':'GANONS_TOWER_FLOOR_1',
    'JABU_JABUS_BELLY_BOSS_EXIT':'JABU_JABUS_BELLY_BOSS_ENTRYWAY',
    **{'TH_'+s:'THIEVES_HIDEOUT_'+s for s in ('1_TORCH_CELL','STEEP_SLOPE_CELL','DOUBLE_CELL','DEAD_END_CELL',
        'KITCHEN_CORRIDOR','KITCHEN_BY_CORRIDOR','KITCHEN_OPPOSITE_CORRIDOR','BREAK_ROOM','BREAK_ROOM_UPPER_CORRIDOR')},
    'TH_KITCHEN_BY_CORRIDOR':'THIEVES_HIDEOUT_KITCHEN_TOP',
    'TH_KITCHEN_OPPOSITE_CORRIDOR':'THIEVES_HIDEOUT_KITCHEN_TOP',
    'TH_BREAK_ROOM_UPPER_CORRIDOR':'THIEVES_HIDEOUT_BREAK_ROOM_CORRIDOR',
    'GANONS_TOWER_BEFORE_GANONDORF_LAIR':'GANONS_TOWER_BEFORE_GANONDORFS_LAIR',
    'GANONS_TOWER_GANONDORF_LAIR':'GANONDORFS_LAIR',
}
# Per-portal bindings where one native region was split or several contracted.
OVERRIDES = {
    'ENTR_POTION_SHOP_KAKARIKO_BACK':('KAK_BACKYARD','KAK_POTION_SHOP_BACK'),
    'ENTR_KAKARIKO_VILLAGE_OUTSIDE_POTION_SHOP_BACK':('KAK_POTION_SHOP_BACK','KAK_BACKYARD'),
    'ENTR_CASTLE_GROUNDS_GREAT_FAIRY_EXIT':('HC_GREAT_FAIRY_FOUNTAIN','HC_PAST_GATE'),
    'ENTR_POTION_SHOP_KAKARIKO_1':('OGC_GREAT_FAIRY_FOUNTAIN','CASTLE_GROUNDS'),
    'ENTR_DEATH_MOUNTAIN_CRATER_UPPER_EXIT':('DEATH_MOUNTAIN_SUMMIT','DMC_UPPER_LOCAL'),
    'ENTR_DEATH_MOUNTAIN_CRATER_GC_EXIT':('GC_DARUNIAS_CHAMBER','DMC_LOWER_LOCAL'),
    'ENTRANCE_GROTTO_EXIT(GROTTO_HC_STORMS_OFFSET)':('HC_STORMS_GROTTO','HC_MOAT'),
    'ENTRANCE_GROTTO_EXIT(GROTTO_LW_DEKU_THEATRE_OFFSET)':('DEKU_THEATER','LOST_WOODS'),
}

def generate():
    regions, _, _, grotto_regions = catalogues()
    enum_tree=ast.parse((ROOT/'archipelago/soh_extreme/_vendor_oot_soh/Enums.py').read_text())
    ap={n.targets[0].id:ast.literal_eval(n.value) for n in next(n for n in enum_tree.body if isinstance(n,ast.ClassDef) and n.name=='Regions').body if isinstance(n,ast.Assign)}
    def binding(rr):
        key=rr.removeprefix('RR_'); key=ALIASES.get(key,key)
        assert key in ap,(rr,key)
        return key
    table=(ROOT/'include/tables/entrance_table.h').read_text()
    entrances={m[1]:(int(m[0],16),m[2],int(m[3])) for m in re.findall(r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_ENTRANCE\((ENTR_\w+), (SCENE_\w+), (\d+)',table)}
    scenes={s:int(i,16) for i,s in re.findall(r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_SCENE\([^,]+,[^,]+, (SCENE_\w+)',(ROOT/'include/tables/scene_table.h').read_text())}
    grottos={s:int(i,16) for i,s in re.findall(r'/\* (0x[0-9A-Fa-f]+) \*/ RANDO_ENUM_ITEM\((GROTTO_\w+)',(NATIVE/'randomizerEnums/RandomizerMiscEnums.h').read_text())}
    load=re.findall(r'\.entranceIndex = (ENTR_\w+),\s*\.content = (0x\w+),\s*\.scene = (SCENE_\w+)',(NATIVE/'randomizer_grotto.c').read_text())
    tracker={}
    for line in (NATIVE/'randomizer_entrance_tracker.cpp').read_text().splitlines():
        m=re.match(r'\s*\{ ((?:ENTR_\w+)|(?:ENTRANCE_GROTTO_\w+\(\w+\))),.*?"([^"]*)",\s*"([^"]*)"',line)
        if m:tracker[m[1]]=(m[2],m[3])
    raw=re.findall(r'\{ EntranceType::(\w+),\s*(RR_\w+),\s*(RR_\w+),\s*((?:ENTR_\w+)|(?:ENTRANCE_GROTTO_\w+\(\w+\)))\s*\}',(NATIVE/'entrance.cpp').read_text())
    entries=[]
    def add(typ,s,t,idx,label=None,source_scene=None,route=None,gate=None,rule=None,id_override=None):
        if typ=='Spawn' or idx in ('ENTR_OUTSIDE_GANONS_CASTLE_1_2','ENTR_JABU_JABU_BOSS_DOOR',
                'ENTR_FIRE_TEMPLE_BOSS_DOOR','ENTR_FOREST_TEMPLE_BOSS_DOOR','ENTR_SHADOW_TEMPLE_BOSS_DOOR',
                'ENTR_SPIRIT_TEMPLE_BOSS_DOOR','ENTR_WATER_TEMPLE_BOSS_DOOR'):
            return # save loads, synthetic ER-only blue warp, and Barinade's non-existent return door
        a,c=route or OVERRIDES.get(idx) or (binding(s),binding(t))
        source_scene=source_scene or regions[s][1]
        grotto=-1; content=-1; mode='entrance'; targets=[]
        if idx.startswith('ENTRANCE_GROTTO_'):
            grotto=grottos[re.search(r'\((\w+)\)',idx)[1]]
            engine,content_text,outside=load[grotto]; content=int(content_text,16)
            entering='_LOAD(' in idx
            key=(0x700 if entering else 0x800)+grotto
            mode='grotto_load' if entering else 'grotto_exit'
            target=entrances[engine][1] if entering else outside
            # Logic regions group fairy fountains under SCENE_GROTTOS, but
            # physical crossing recognition must use the loaded engine scene.
            source_scene=outside if entering else entrances[engine][1]
            targets=[entrances[engine][0]] if entering else []
        else:
            key,target,spawn=entrances[idx]
            # Exactly the four ordinary age/time layers, not cutscene entries.
            targets=[key]
        if typ=='WarpSong':source_scene='SCENE_ID_MAX'
        # AP and native randomizer repurpose this unused potion-shop index.
        if idx=='ENTR_POTION_SHOP_KAKARIKO_1':target='SCENE_OUTSIDE_GANONS_CASTLE'
        src_label,dst_label=tracker.get(idx,(regions.get(s,(ap.get(a,a),))[0],regions.get(t,(ap.get(c,c),))[0]))
        if not label:label=src_label+' -> '+dst_label
        entry=dict(id=id_override or BASE+key,name='Scene Transition: '+label,index=idx,kind=typ,
                   source=a,target=c,mode=mode,entrances=targets,
                   source_scene=scenes.get(source_scene,-1),target_scene=scenes[target],
                   source_scene_token=source_scene,target_scene_token=target,
                   grotto=grotto,content=content)
        if gate:entry['gate']=gate
        if rule:entry['traversal_rule']=rule
        entries.append(entry)
        return entry
    for row in raw:add(*row)
    # Non-shuffled physical scene portals missing from entranceShuffleTable.
    for idx,s,t in [('ENTR_BACK_ALLEY_DAY_0','THE_MARKET','MARKET_BACK_ALLEY'),
                    ('ENTR_BACK_ALLEY_DAY_1','THE_MARKET','MARKET_BACK_ALLEY'),
                    ('ENTR_MARKET_DAY_3','MARKET_BACK_ALLEY','THE_MARKET'),
                    ('ENTR_MARKET_DAY_4','MARKET_BACK_ALLEY','THE_MARKET'),
                    ('ENTR_DOG_LADY_HOUSE_0','MARKET_BACK_ALLEY','MARKET_DOG_LADY_HOUSE'),
                    ('ENTR_BACK_ALLEY_DAY_4','MARKET_DOG_LADY_HOUSE','MARKET_BACK_ALLEY')]:
        add('Interior','RR_'+s,'RR_'+t,idx,label=regions['RR_'+s][0]+' -> '+regions['RR_'+t][0]+' ('+idx.rsplit('_',1)[1]+')')
    add('Overworld','RR_HYRULE_FIELD','RR_ZR_FRONT','ENTR_ZORAS_RIVER_3','Hyrule Field -> Zora River (water exit)',gate='swim')
    add('Overworld','RR_ZR_FRONT','RR_HYRULE_FIELD','ENTR_HYRULE_FIELD_14','Zora River -> Hyrule Field (water exit)',gate='swim')
    add('Dungeon','RR_GANONS_TOWER_BEFORE_GANONDORF_LAIR','RR_GANONS_TOWER_GANONDORF_LAIR','ENTR_GANONDORF_BOSS_0')
    # The exterior hand ledges are distinct scenes even though native logic
    # groups them with Spirit Temple. Reuse their precise private room edges.
    for hand,spawn in [('RIGHT',2),('LEFT',3)]:
        inside='RR_SPIRIT_TEMPLE_'+hand+'_HAND_EXIT'; outside='RR_SPIRIT_TEMPLE_OUTER_'+hand+'_HAND'
        add('Dungeon',inside,outside,f'ENTR_DESERT_COLOSSUS_{spawn}',route=(inside,outside))
        add('Dungeon',outside,inside,f'ENTR_SPIRIT_TEMPLE_{spawn}',route=(outside,inside),source_scene='SCENE_DESERT_COLOSSUS')
    # The ranch fence jumps are one-way. The unused ranch arrival indices are
    # not entrances that can be jumped to from Hyrule Field.
    for i,label in [(11,'west fence'),(12,'north fence'),(13,'east fence')]:
        add('Overworld','RR_LON_LON_RANCH','RR_HYRULE_FIELD',f'ENTR_HYRULE_FIELD_{i}',
            'Lon Lon Ranch -> Hyrule Field ('+label+')',gate='horse')
    add('Interior','RR_HC_DRAIN_LEDGE','RR_HC_GARDEN','ENTR_CASTLE_COURTYARD_GUARDS_DAY_0',
        'Hyrule Castle drain -> Castle Courtyard guards')
    add('Interior','RR_HC_GARDEN','RR_HC_DRAIN_LEDGE','ENTR_CASTLE_GROUNDS_RAINBOW_BRIDGE_EXIT',
        'Castle Courtyard guards -> Hyrule Castle drain',source_scene='SCENE_CASTLE_COURTYARD_GUARDS_DAY',
        id_override=11400000+scenes['SCENE_CASTLE_COURTYARD_GUARDS_DAY']*4096+entrances['ENTR_CASTLE_GROUNDS_RAINBOW_BRIDGE_EXIT'][0])
    add('Interior','RR_HC_GARDEN','RR_HC_GARDEN','ENTR_CASTLE_COURTYARD_ZELDA_0',
        'Castle Courtyard guards -> Zelda Courtyard',source_scene='SCENE_CASTLE_COURTYARD_GUARDS_DAY',rule='day')
    add('Interior','RR_HC_GARDEN','RR_HC_GARDEN','ENTR_CASTLE_COURTYARD_GUARDS_DAY_1',
        'Zelda Courtyard -> Castle Courtyard guards',rule='day')
    e=add('Dungeon','RR_GANONS_TOWER_GANONDORF_LAIR','RR_GANONS_CASTLE_ESCAPE','ENTR_GANONS_TOWER_COLLAPSE_EXTERIOR_0',
          "Ganondorf's Lair -> Castle escape")
    e['requires_final_ganon_key']=True
    # Escape exits are actual collision portals. The two Stalfos are spawned
    # by En_Zl3 on the 260-unit floor; lower floors require clearing that fight.
    for target,source,spawns in [
        ('GANONS_TOWER_COLLAPSE_EXTERIOR','GANONS_TOWER_COLLAPSE_INTERIOR',range(1,8)),
        ('GANONS_TOWER_COLLAPSE_INTERIOR','GANONS_TOWER_COLLAPSE_EXTERIOR',range(7)),
        ('INSIDE_GANONS_CASTLE_COLLAPSE','GANONS_TOWER_COLLAPSE_INTERIOR',[0]),
        ('GANONS_TOWER_COLLAPSE_INTERIOR','INSIDE_GANONS_CASTLE_COLLAPSE',[7]),
        ('GANON_BOSS','INSIDE_GANONS_CASTLE_COLLAPSE',[0])]:
        for spawn in spawns:
            past_fight=(target=='GANONS_TOWER_COLLAPSE_EXTERIOR' and spawn>=6) or (
                target=='GANONS_TOWER_COLLAPSE_INTERIOR' and spawn>=5) or target in ('GANON_BOSS','INSIDE_GANONS_CASTLE_COLLAPSE')
            e=add('Dungeon','RR_GANONS_CASTLE_ESCAPE','RR_GANONS_CASTLE_ESCAPE',f'ENTR_{target}_{spawn}',
                source.replace('_',' ').title()+' -> '+target.replace('_',' ').title()+f' (entrance {spawn+1})',
                source_scene='SCENE_'+source,route=('RR_GANONS_CASTLE_ESCAPE','RR_GANONS_CASTLE_ESCAPE'))
            e.update(condition='CanKillEnemy(RE_STALFOS, ED_CLOSE, true, 2)' if past_fight else 'true',
                     requires_final_ganon_key=True)
    assert len({e['id'] for e in entries})==len(entries)
    assert len({e['name'] for e in entries})==len(entries)
    entries.sort(key=lambda e:e['id'])
    (ROOT/'archipelago/soh_extreme/SceneTransitionCatalog.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    print('Exported',len(entries),'directed portals')
    return entries

if __name__=='__main__':generate()
