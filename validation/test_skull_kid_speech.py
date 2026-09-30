"""Real AP/UT Skull Kid interactions: species, mode, language and instrument."""
from run_case import setup, BOOTSTRAP
from ut_harness import tracker
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(parents=[BOOTSTRAP])
p.add_argument('--ut-core', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args(); tests = []
def ck(name, actual, expected=True):
    tests.append(dict(test=name, actual=actual, expected=expected, passed=actual == expected))

targets = ['NPC Speech: Lost Woods Skull Kid 1', 'NPC Speech: Lost Woods Skull Kid Duet',
           'LW Skull Kid', 'LW Ocarina Memory Game', 'LW Skull Kid Mask Trade']
for mode in ('off', 'all_enemies_as_1', 'individual_enemies'):
    for behavior in ('gone_until_found', 'invincible_until_found'):
        m = setup(291020, overrides=dict(shuffle_enemy_soul=mode, enemy_soul_behavior=behavior,
            npc_speech_sanity=True, shuffle_npc_soul=True, shuffle_speak='individual_languages',
            closed_forest='off'), stop_before='pre_fill')
        w = m.worlds[1]; evaluate = tracker(w, a.ut_core)
        exclude = {'NPC Soul', 'Speak Kokiri', 'Skull Kid Soul', 'Enemy Soul'}
        items = [*m.itempool, *[l.item for l in w.get_locations() if type(l.address) is int and l.item]]
        base = [i.name for i in items if i.name in w.item_name_to_id and i.name not in exclude]
        for mask in range(16):
            receipt = ['NPC Soul', 'Speak Kokiri', 'Skull Kid Soul', 'Enemy Soul']
            result = evaluate(base + [name for bit, name in enumerate(receipt) if mask & (1 << bit)])
            expected = bool(mask & 1 and mask & 2 and (mode == 'off' or behavior == 'invincible_until_found'
                or mask & (8 if mode == 'all_enemies_as_1' else 4)))
            for name in targets:
                location = w.get_location(name)
                ck(f'{mode}/{behavior}/{mask} AP {name}', location.can_reach(result.state), expected)
                if location.address is not None:
                    ck(f'{mode}/{behavior}/{mask} UT {name}', name in result.in_logic_locations, expected)
        no_ocarina = evaluate([n for n in base if n != 'Progressive Ocarina'] + list(exclude))
        for name in targets:
            ck(f'{mode}/{behavior} no instrument {name}', w.get_location(name).can_reach(no_ocarina.state), False)

result = dict(passed=all(t['passed'] for t in tests), assertions=len(tests), tests=tests)
a.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
print('PASS' if result['passed'] else 'FAIL', len(tests), 'Skull Kid assertions')
for t in [t for t in tests if not t['passed']][:20]: print(t)
raise SystemExit(not result['passed'])
