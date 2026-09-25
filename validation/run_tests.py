#!/usr/bin/env python3
"""Compile delivered production code against isolated test services.

Run from any directory: python validation/run_tests.py
Requires clang++ and/or g++. Does not launch SoH or run seed generation.
"""
from pathlib import Path
import subprocess, shutil, re, os, json, hashlib
ROOT=Path(__file__).resolve().parents[1]
V=ROOT/'validation'; RESULTS=V/'results'; BUILD=V/'build'
RESULTS.mkdir(exist_ok=True); BUILD.mkdir(exist_ok=True)
def get_method(source: str, start: str, end: str)->str:
    i=source.index(start); return source[i:source.index(end,i)]
ap=(ROOT/'soh/Network/Archipelago/ArchipelagoClient.cpp').read_text(encoding='utf-8-sig')
traps=(ROOT/'soh/Enhancements/ExtraTraps.cpp').read_text(encoding='utf-8-sig')
ui=(ROOT/'soh/SohGui/SohMenuEnhancements.cpp').read_text(encoding='utf-8-sig')
apply=get_method(ap,'void ArchipelagoClient::ApplySlotSettings()','\nvoid ArchipelagoClient::EnforceSlotSettings()')
before=(V/'support/ApplySlotSettings.before.inc').read_text().replace('void ArchipelagoClient::ApplySlotSettings()', 'void BeforeClient::ApplySlotSettings()',1)
body=re.sub(r'^\s*#include[^\n]*','',traps,flags=re.MULTILINE)
start=ui.index('    AddWidget(path, "AP trap effects follow')
menu=ui[start:ui.index('\n    // Cheats',start)]
source='#include "EngineHarness.h"\n'+before+'\n'+apply+'\n'+body+'\nvoid BuildTrapMenu() {\n'+menu+'\n}\n'+(V/'test_trap_settings.cpp').read_text()
(BUILD/'production_trap_test.cpp').write_text(source)
summary={'tests':[], 'scope':'isolated production code with controlled engine/settings/UI/persistence services',
         'seed_simulations':0,'full_windows_build':False,'live_game_test':False}
# Guard against shipping a client regression/accidental unrelated replacement.
assert not re.search(r'CVarSet(?:Integer|String)\(\s*"gEnhancements\.ExtraTraps\.',ap)
assert 'Automatic Universal Tracker host started' in ap
assert all(k in traps for k in ['RSK_EXTREME_TRAP_POOL','Archipelago_IsCurrentSaveFile', 'ResetExtraTrapEffects'])
assert 'CVAR_REMOTE_ARCHIPELAGO' not in traps
assert 'settings.types[ADD_TELEPORT_TRAP] == TELEPORT_TRAP_ADVANCED' in traps
assert not re.search(r'CVarSet(?:Integer|String)',traps)
summary['static_guards']='passed'
for compiler in ('clang++','g++'):
    exe=shutil.which(compiler)
    if not exe:
        summary['tests'].append({'compiler':compiler,'status':'unavailable'});continue
    tag=compiler.replace('+','p')
    target=BUILD/f'trap-settings-{tag}'
    command=[exe,'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',
             '-I'+str(V/'support'),str(BUILD/'production_trap_test.cpp'),'-o',str(target)]
    c=subprocess.run(command,capture_output=True,text=True,timeout=90)
    (RESULTS/f'{tag}-compile.log').write_text(' '.join(command)+'\n'+c.stdout+c.stderr)
    if c.returncode:
        print(c.stderr[-14000:]);raise SystemExit(c.returncode)
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    run=subprocess.run([str(target)],capture_output=True,text=True,env=env,timeout=30)
    (RESULTS/f'{tag}-tests.log').write_text(run.stdout+run.stderr)
    print(compiler,run.stdout,run.stderr)
    summary['tests'].append({'compiler':compiler,'command':command,'status':'passed' if run.returncode==0 else 'failed', 'returncode':run.returncode})
    if run.returncode:
        (RESULTS/'summary.json').write_text(json.dumps(summary,indent=2));raise SystemExit(run.returncode)
summary['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'soh').rglob('*') if p.is_file()}
(RESULTS/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('Saved',RESULTS/'summary.json')
