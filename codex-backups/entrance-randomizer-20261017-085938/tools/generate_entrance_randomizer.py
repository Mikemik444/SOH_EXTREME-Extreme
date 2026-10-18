"""Export stable physical endpoints and exact dungeon collection predicates.

Scene endpoint IDs are engine entrance indices. Room endpoint IDs occupy a
separate range; no existing item/location IDs are allocated or renumbered.
"""
from pathlib import Path
import ast
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'validation'))
from source_index import native_sources, mask_comments, split_top, body_at
from generate_scene_transitions import ALIASES, OVERRIDES


def generate():
    package = ROOT / 'archipelago/soh_extreme'
    graph = json.loads((package / 'EnemyRoomGraph.json').read_text())
    checks = json.loads((package / 'SceneTransitionCatalog.json').read_text())
    by_index = {}
    for e in checks: by_index.setdefault(e['index'], e)
    enums = ast.parse((package / '_vendor_oot_soh/Enums.py').read_text())
    regions = {n.targets[0].id: ast.literal_eval(n.value)
               for n in next(c for c in enums.body if isinstance(c, ast.ClassDef) and c.name == 'Regions').body
               if isinstance(n, ast.Assign)}
    table = (ROOT / 'include/tables/entrance_table.h').read_text()
    indices = {name: (int(index, 16), scene, int(spawn)) for index, name, scene, spawn in re.findall(
        r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_ENTRANCE\((ENTR_\w+), (SCENE_\w+), (\d+)', table)}
    scenes = {name: int(index, 16) for index, name in re.findall(
        r'/\* (0x[0-9A-Fa-f]+) \*/ DEFINE_SCENE\([^,]+,[^,]+, (SCENE_\w+)',
        (ROOT / 'include/tables/scene_table.h').read_text())}
    grotto_ids = {name: int(index, 16) for index, name in re.findall(
        r'/\* (0x[0-9A-Fa-f]+) \*/ RANDO_ENUM_ITEM\((GROTTO_\w+)',
        (ROOT / 'soh/Enhancements/randomizer/randomizerEnums/RandomizerMiscEnums.h').read_text())}
    def numeric(index):
        if index.startswith('ENTRANCE_GROTTO_'):
            return (0x700 if '_LOAD(' in index else 0x800) + grotto_ids[re.search(r'\((\w+)\)', index)[1]]
        return indices[index][0]
    def binding(rr):
        if rr in graph:
            return rr
        token = ALIASES.get(rr[3:], rr[3:])
        if token not in regions:
            raise ValueError(('Unmapped entrance region', rr, token))
        return token
    rows = {}
    def endpoint(kind, source, target, index, primary, reverse=-1):
        old = by_index.get(index)
        if kind == 'BlueWarp' and old is None: return
        if old:
            source = source if source in graph else old['source']
            target = target if target in graph else old['target']
            scene, source_scene = old['target_scene'], old['source_scene']
        else:
            source, target = binding(source), binding(target)
            scene, source_scene = scenes[indices[index][1]], -1
        if index == 'ENTR_HYRULE_FIELD_10':
            scene = scenes['SCENE_TEMPLE_OF_TIME']
        category = {'Interior': 'interiors', 'SpecialInterior': 'interiors',
                    'Dungeon': 'dungeons', 'GanonDungeon': 'dungeons', 'GanonTower': 'dungeons',
                    'GrottoGrave': 'grottos', 'ChildBoss': 'bosses', 'AdultBoss': 'bosses',
                    'OwlDrop': 'owls', 'WarpSong': 'warp_songs',
                    'Spawn': 'child_spawn' if source == 'CHILD_SPAWN' else 'adult_spawn',
                    'BlueWarp': 'blue_warps', 'Overworld': 'one_ways' if reverse < 0 else 'overworld',
                    'ThievesHideout': 'interiors'}[kind]
        value = numeric(index)
        row = dict(id=value, index=index, category=category, source=source, target=target,
                   reverse=reverse, primary=primary, scene=scene, source_scene=source_scene,
                   check_id=old['id'] if old else 0, door=-1, room=-1,
                   name=old['name'].removeprefix('Scene Transition: ') if old else source+' -> '+target)
        if old:
            for key in ('gate', 'traversal_rule', 'condition'):
                if key in old: row[key] = old[key]
        rows[value] = row
        return row
    text = mask_comments((ROOT / 'soh/Enhancements/randomizer/entrance.cpp').read_text())
    text = text.split('entranceShuffleTable = {', 1)[1].split('\n    };', 1)[0]
    expr = r'\{\s*EntranceType::(\w+),\s*(RR_\w+),\s*(RR_\w+),\s*((?:ENTR_\w+)|(?:ENTRANCE_GROTTO_\w+\(\w+\)))\s*\}'
    for m in re.finditer(r'\{\s*('+expr+r')\s*,\s*('+expr+r'|NO_RETURN_ENTRANCE)\s*\}', text):
        parts = re.findall(expr, m[0])
        first = parts[0]
        second = parts[1] if len(parts) == 2 else None
        endpoint(*first, True, numeric(second[3]) if second else -1)
        if second: endpoint(*second, False, numeric(first[3]))
    assert len(rows) >= 280, len(rows)
    # Native table omits the three actual ranch fence jump exits.
    for old in checks:
        if old.get('gate') == 'horse':
            endpoint('Overworld', old['source'], old['target'], old['index'], True)
    # Physical room doors. The direction is the same as the player's door
    # animation: side 0 travels along +yaw, side 1 along -yaw.
    doors = json.loads((package / 'DungeonDoorCatalog.json').read_text())
    door_ids = {(e['source_scene'], e['door'], e['side']):
                0x2000 + e['source_scene'] * 128 + e['door'] * 2 + e['side'] for e in doors}
    for e in doors:
        scene = e['source_scene']; key = (scene, e['door'], e['side'])
        anchors = [v[0] for v in indices.values() if scenes.get(v[1]) == scene and v[2] == 0]
        assert anchors, key
        rows[door_ids[key]] = dict(id=door_ids[key], index=e['index'], category='dungeon_doors',
            source=e['source'], target=e['target'],
            reverse=door_ids.get((scene, e['door'], 1-e['side']), -1), primary=e['side'] == 0,
            scene=scene, source_scene=scene, check_id=e['id'], door=e['door'], side=e['side'],
            from_room=e['room_from'], room=e['room_to'], position=e['position'], rotation=e['rotation'],
            anchor=min(anchors), name=e['name'].removeprefix('Dungeon Door: '),
            **{k: e[k] for k in ('condition', 'extra_condition') if k in e})
    out = sorted(rows.values(), key=lambda e: e['id'])
    assert len(out) == len({e['id'] for e in out})
    assert all(e['reverse'] < 0 or rows[e['reverse']]['reverse'] == e['id'] for e in out)
    (package / 'EntranceCatalog.json').write_text(json.dumps(out, indent=2)+'\n')
    locations, _ = native_sources(ROOT)
    external = []
    for rr, row in graph.items():
        for edge in row['exits']:
            if edge['target'] in graph or '_MQ_' in edge['target'] or edge['condition'].strip(';') == 'false': continue
            external.append(dict(source=rr, target=binding(edge['target']), condition=edge['condition']))
    (package / 'DungeonExternalEdges.json').write_text(json.dumps(external, indent=2)+'\n')
    ap_ids = dict((rc, int(number)) for rc, number in re.findall(
        r'static_cast<int>\((RC_\w+)\),\s*(\d+)LL',
        (ROOT / 'soh/Network/Archipelago/ArchipelagoLocationMap.inc').read_text()))
    routes = {str(ap_ids[rc]): [dict(region=e['region'], condition=e['condition']) for e in es if e['region'] in graph]
              for rc, es in locations.items() if rc in ap_ids and any(e['region'] in graph for e in es)}
    (package / 'DungeonLocationRoutes.json').write_text(json.dumps(routes, indent=2)+'\n')
    # One shared native manifest, including names for debug destination labels.
    lines = ['// Generated by tools/generate_entrance_randomizer.py.']
    for e in out:
        pos = e.get('position', [0, 0, 0])
        lines.append('{' + ', '.join(map(str, [e['id'], e['reverse'], e['scene'], e['source_scene'],
            e['check_id'], e['door'], e.get('side', -1), e.get('from_room', -1), e['room'],
            e.get('anchor', e['id']), *pos, e.get('rotation', 0)])) + ', '+json.dumps(e['name'])+'},')
    (ROOT / 'soh/Network/Archipelago/EntranceRandomizerData.inc').write_text('\n'.join(lines)+'\n')
    print(len(out), 'entrance endpoints;', len(routes), 'exact dungeon collection routes')


if __name__ == '__main__':
    generate()

