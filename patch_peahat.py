from pathlib import Path
root=Path(__file__).resolve().parent
loc=root/'archipelago/soh_extreme/EnemyDropLocations.py'
rules=root/'archipelago/soh_extreme/EnemyDropRules.py'
native=root/'soh/Enhancements/randomizer/randomizer_check_tracker.cpp'
finder=root/'soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc'

def once(path, old, new):
    data=path.read_text(encoding='utf-8')
    count=data.count(old)
    if count!=1:raise AssertionError(f'{path}: expected one match, got {count} for {old!r}')
    path.write_text(data.replace(old,new),encoding='utf-8')

for n in (6,7):
    name=f'Enemy Defeat: Hyrule Field Room 0 Peahat {n}'
    data=loc.read_text()
    matching=[x for x in data.splitlines() if name in x]
    assert len(matching)==1, matching
    assert ", 'Peahat Soul', 'peahat', 'HYRULE_FIELD', 3, ''" in matching[0]
    once(loc, matching[0], matching[0].replace("'Peahat Soul', 'peahat'", "'Peahat Soul', 'peahat_flying'"))

once(rules, '            "peahat": melee | sling | bow | hook,',
     '''            "peahat": melee | sling | bow | hook,
            # Native En_Peehat: params == 0 is the airborne larva-spawning
            # variant. The parent can rise out of child melee reach; ranged
            # damage is needed to defeat the actual parent (not its larvae).
            # These two Hyrule Field placements are child-only (spawn_mask=3),
            # so their usable weapon in logic is Slingshot. Adult variants
            # could instead use Bow, Hookshot or Longshot.
            "peahat_flying": sling | bow | hook | (can_use(Items.LONGSHOT, b) if adult else False_()),''')

once(native,
     '    EFC_SWORD, EFC_TEKTITE, EFC_PEAHAT, EFC_SHABOM, EFC_JELLYFISH,',
     '    EFC_SWORD, EFC_TEKTITE, EFC_PEAHAT, EFC_PEAHAT_FLYING, EFC_SHABOM, EFC_JELLYFISH,')
once(native,
     '        case EFC_PEAHAT: return melee || sling || bow || hook;',
     '''        case EFC_PEAHAT: return melee || sling || bow || hook;
        // En_Peehat params 0 flies upward. Child Slingshot is required for
        // these child-only placements; sword/sticks cannot hit the airborne
        // parent and defeating spawned larvae does not count for this check.
        case EFC_PEAHAT_FLYING: return sling || bow || hook;''')
for n in (6,7):
    line=[x for x in finder.read_text().splitlines() if f'Peahat {n}"' in x]
    assert len(line)==1, line
    once(finder, line[0], line[0].replace('EFC_PEAHAT,','EFC_PEAHAT_FLYING,'))

print('Patched four source files')
