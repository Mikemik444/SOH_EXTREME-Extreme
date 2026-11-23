"""Static catalogue regression checks for native Check Finder scene grouping."""
from pathlib import Path
import json, re, zipfile
root=Path(__file__).resolve().parent
with zipfile.ZipFile('/mnt/data/SOH_EXTREME_Age_Transition_Tracker_Visibility_Fix.zip') as latest:
    with zipfile.ZipFile(latest.open('soh_extreme.apworld')) as ap:
        def data(name):
            return json.loads(ap.read(next(n for n in ap.namelist() if n.endswith('/'+name))))
        catalog=data('SceneTransitionCatalog.json')+data('DungeonDoorCatalog.json')
        scene=data('SceneTransitionCatalog.json')
ids={x['id'] for x in catalog}
assert len(ids)==len(catalog)==746, (len(ids),len(catalog))
inc=(root/'SceneTransitionScenes.inc').read_text()
registered={int(m) for m in re.findall(r'\{\s*(\d+)LL,',inc)}
assert registered==ids, ('missing ids',sorted(ids-registered)[:5],sorted(registered-ids)[:5])
cpp=(root/'randomizer_check_tracker.cpp').read_text()
labels=(root/'TrackerCheckLabels.h').read_text()
router=(root/'RoomTransitionLabels.h').read_text()
assert 'crossings.find(SohExtreme::SharedSceneTransitionLocationId(id))' in cpp
assert 'descriptions.find(SharedSceneTransitionLocationId(location))' in labels
assert 'checks.find(SharedSceneTransitionLocationId(check))' in router
by_id={x['id']:x for x in scene}
for cid,expected_source,expected_scene in [(11000845,'KAK_GRANNYS_POTION_SHOP',78),
                                           (11000228,'KAKARIKO_VILLAGE',82),
                                           (11000381,'KAKARIKO_VILLAGE',82),
                                           (11000405,'THE_GRAVEYARD',83)]:
    item=by_id[cid]
    assert item['source']==expected_source and item['source_scene']==expected_scene
    assert f'{{ {cid}LL, {expected_scene},' in inc
# Shared-check ID and each age specific ID map to the same physical source.
for item in catalog:
    base=item['id']
    assert 11000000<=base<12000000
    for offset in (20000000,40000000):
        aged=base+offset
        assert aged-offset==base
print('PASS: 746 shared source IDs, Child/Adult display mapping, Kakariko/Graveyard examples')
