"""Compile the real NPC logic, native location Soul gate and legacy Finder gate.

Option/inventory and static location storage are isolated test boundaries. The
captured production functions are not rewritten or duplicated into the fixture.
This does not compile the full SoH application or exercise native actor updates.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time

SOURCE = Path(__file__).resolve().parents[2]
RANDO = SOURCE / 'soh/Enhancements/randomizer'
TEMPLATE = Path(__file__).with_name('soul_object_validation') / 'logic_fixture.cpp.in'


def function(text, name):
    match = re.search(r'(?:^|\n)[^\n{};]*\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', text)
    if match is None:
        raise AssertionError('Function not found: ' + name)
    start = match.start()
    depth = 1
    clean = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
                   lambda part: ' ' * len(part[0]), text, flags=re.S)
    for end in range(match.end(), len(text)):
        depth += (clean[end] == '{') - (clean[end] == '}')
        if not depth:
            return text[start:end + 1].strip()
    raise AssertionError('Function not terminated: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    paths = {'logic': RANDO / 'logic.cpp', 'locations': RANDO / 'location_access.cpp',
             'finder': RANDO / 'randomizer_check_tracker.cpp',
             'lost_woods': RANDO / 'location_access/overworld/lost_woods.cpp'}
    texts = {name: path.read_text() for name, path in paths.items()}
    source_hashes = {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in paths.values()}
    capture = {
        'NPC_LOGIC_HELPER': ('logic', 'Logic::CanSpeakToPathBlockingNpc'),
        'NPC_ACTOR_CLASSIFICATION': ('locations', 'MegaIsNpcLocationActor'),
        'ANIMAL_ACTOR_CLASSIFICATION': ('locations', 'MegaIsAnimalLocationActor'),
        'LOCATION_LANGUAGE': ('locations', 'MegaSpeakItemForLocation'),
        'LOCATION_SPEAK': ('locations', 'MegaHasSpeakForLocation'),
        'LOCATION_SOUL_GATE': ('locations', 'MegaSoulAllowsLocation'),
        'FIRST_TALK_GATE': ('finder', 'HasNpcSpeechInteractionItems'),
    }
    fragments = {token: function(texts[name], symbol) for token, (name, symbol) in capture.items()}
    entrance_expressions = {}
    for token, target in (('MIDO_FORWARD_ROUTE', 'RR_LW_BEYOND_MIDO'),
                          ('MIDO_REVERSE_ROUTE', 'RR_THE_LOST_WOODS')):
        matches = [expression.strip() for expression in re.findall(
            r'ENTRANCE\(' + target + r',\s*([^\n]+)\),', texts['lost_woods'])
            if 'logic->IsChild' in expression]
        assert len(matches) == 1, (target, matches)
        entrance_expressions[token] = matches[0]
    fragments.update(entrance_expressions)
    fixture = TEMPLATE.read_text()
    constants = set(re.findall(r'\b(?:RG|RC|RT|RSK|RAND_INF|ACTOR|SCENE|RCTYPE)_[A-Z0-9_]+\b',
                              fixture + '\n'.join(fragments.values())))
    constants.discard('CONSTANT_COUNT')
    fragments['CONSTANTS'] = 'enum { ' + ', '.join(sorted(constants)) + ', CONSTANT_COUNT };'
    for token, code in fragments.items():
        fixture = fixture.replace('@' + token + '@', code)
    assert not re.search(r'@[A-Z_]+@', fixture)
    with tempfile.TemporaryDirectory(prefix='soh-npc-logic-') as tmp:
        build = Path(tmp)
        source = build / 'npc_logic.cpp'
        source.write_text(fixture)
        binary = build / 'npc_logic'
        command = ['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-g', '-O1',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(source), '-o', str(binary)]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                   UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        result = subprocess.run([str(binary)], text=True, capture_output=True, env=env)
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(result.stderr or 'Native logic fixture failed')
        match = re.search(r'RESULT cases=(\d+) assertions=(\d+)', result.stdout)
        assert match
    assert source_hashes == {str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in paths.values()}, 'Production source changed during fixture run.'
    report = dict(status='passed', cases=int(match[1]), assertions=int(match[2]),
                  sanitizers=['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
                  source_sha256=source_hashes, template_sha256=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
                  probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  elapsed_seconds=round(time.monotonic() - started, 3),
                  captured_functions={token: symbol for token, (_, symbol) in capture.items()},
                  captured_entrance_expressions=entrance_expressions,
                  scope='Actual native NPC interaction helper, location actor classification and Soul gate, '
                        'language selector, legacy first-talk Finder gate, and both native Mido entrance '
                        'expressions compiled unchanged. '
                        'Option/inventory and static location storage are engine IO shims. '
                        'No full native build, collision simulation or gameplay.',
                  output=result.stdout.splitlines())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
