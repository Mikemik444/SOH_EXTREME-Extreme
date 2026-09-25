from pathlib import Path
import sys,types
root=Path(__file__).resolve().parents[1]
from source_path import ap_source
pkg=types.ModuleType('soh_extreme');pkg.__path__=[str(ap_source(root))];sys.modules['soh_extreme']=pkg
from soh_extreme.TrackerMirror import encode_snapshot
regions=['Kokiri Forest','LH Fishing Hole','DMC Distant Platform','Forest Temple Bow Room','GV Upper Stream','Market']
rows=[dict(id=i+1,state=2 if i%7==0 else 1,name=f'Check {i+1:04d} % literal ## text',region=regions[i%len(regions)]) for i in range(3258)]
# Synthetic display fixture, not a generated seed or tested physical placement.
(root/'validation/results/rows.b64').write_text(encode_snapshot(nonce='a'*32,producer='test',request=1,revision=1,slot=1,received=99,active=set(range(1,3260)),checked={3259},rows=rows))
