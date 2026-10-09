"""Check the atomic CMake dependency patch used by normal/source builds."""
from pathlib import Path
import argparse,json,subprocess
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--cmake',required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=Path(__file__).resolve().parent.parent
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
original=a.baseline.read_text(encoding='utf-8');assert 'SOH-EXTREME connection identity' not in original
cases=[]
def run(name,source,success=True):
 d=out/name;d.mkdir(exist_ok=True);target=d/'Archipelago.cpp';target.write_text(source,encoding='utf-8')
 script=d/'patch.cmake';script.write_text(f'set(apcpp_SOURCE_DIR "{d.as_posix()}")\ninclude("{(r/"Cmake/SohExtremeAPCppIdentity.cmake").as_posix()}")\n')
 c=subprocess.run([a.cmake,'-P',str(script)],capture_output=True,text=True)
 after=target.read_text(encoding='utf-8')
 assert (c.returncode==0)==success,(name,c.stdout,c.stderr)
 if not success:assert after==source
 cases.append(name);return after
fixed=run('normal',original)
assert fixed.count('SOH-EXTREME connection identity 0.11.61')==1
assert run('idempotent',fixed)==fixed
run('missing-late-anchor',original.replace('std::string key = slot_itr.key().asString();','std::string renamed = slot_itr.key().asString();'),False)
anchor='''            ap_player_team = root[i]["team"].asInt();
            sohHintKey = "_read_hints_" + std::to_string(ap_player_team) + "_" + std::to_string(ap_player_id);
            sohHints = Json::nullValue;
            sohHintsLoaded = false;'''
hints=anchor.split('\n',1)[1]
start=fixed.index(anchor)+len(anchor)
end=fixed.index('                identityCallback->second(writer.write(identity));',start)
end=fixed.index('            }',end)+len('            }')
identity=fixed[start:end]
current=anchor+identity
legacy=anchor.split('\n',1)[0]+identity+'\n'+hints
assert run('legacy-upgrade',fixed.replace(current,legacy))==fixed
assert run('legacy-after-hints',fixed.replace(current,current+'\n'+hints))==fixed
run('duplicate-legacy',fixed.replace(current,legacy+'\n'+legacy),False)
run('duplicate-anchor',original.replace(anchor,anchor+'\n'+anchor),False)
run('modified-patch',fixed.replace('identity["seed"] = lib_room_info.seed_name;','identity["seed"] = "wrong";'),False)
(out/'patch.json').write_text(json.dumps({'passed':True,'cases':cases},indent=2))
print('PASS '+', '.join(cases))
