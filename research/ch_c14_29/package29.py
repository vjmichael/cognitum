"""Fail-closed CH29 evidence/full-source packaging; all 60 frozen cases required."""
from __future__ import annotations
import hashlib,json,zipfile
from pathlib import Path
D=Path(__file__).resolve().parent;BASE=D.parent
protocol=json.loads((D/'frozen_protocol.json').read_text());ids=set(protocol['original_case_sha256'])
for mode in ('fixed','equal_cpu'):
 for b in (63,127):
  for sub in ('certificates','verifications','logs'):
   have={x.stem for x in (D/'runs'/mode/str(b)/sub).glob('*.json')}
   if have!=ids:raise RuntimeError(f'Incomplete CH29 benchmark {mode}/{b}/{sub}: {len(have)}/15')
assert (D/'Engineering_Report_CH_C14_29.md').is_file() and (D/'study_summary.json').is_file()
include=set(['README.md','Engineering_Report_CH_C14_29.md','study_summary.json','frozen_protocol.json','frozen_protocol.sha256','solver29.py','verifier29.py','run_case29.py','tests/test_inheritance.py','launch29.py','audit29.py','summarize29.py','make_report29.py','package29.py','SOURCE_SHA256.json'])
include.update(x.relative_to(D).as_posix() for x in (D/'runs').rglob('*.json'))
include.update(x.relative_to(D).as_posix() for x in (D/'runs').rglob('*.txt'))
missing=[p for p in include if not (D/p).is_file()]
if missing:raise RuntimeError(f'Missing package files {missing}')
manifest={k:hashlib.sha256((D/k).read_bytes()).hexdigest() for k in sorted(include)}
(D/'SHA256SUMS_CH29.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
include.add('SHA256SUMS_CH29.json')

def addzip(z,arc,data):
 info=zipfile.ZipInfo(arc,date_time=(2026,11,2,15,0,0))
 info.compress_type=zipfile.ZIP_DEFLATED
 info.external_attr=0o100644<<16
 z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)

standalone=BASE/'CH_C14_29_Evidence_Original_15_Fixed_And_CPU.zip'
with zipfile.ZipFile(standalone,'w') as z:
 for name in sorted(include):addzip(z,'CH_C14_29/'+name,(D/name).read_bytes())

full=BASE/'Cognitum_CH_C14_29_Parent_Inheritance_63_127_Equal_CPU_Original_CH23_2026-11-02.zip'
prior=BASE/'Cognitum_CH_C14_28_Selective_MPFR_Cache_63_127_OriginalCH23_2026-11-02.zip'
with zipfile.ZipFile(prior) as old, zipfile.ZipFile(full,'w') as z:
 for name in sorted(old.namelist()):addzip(z,name,old.read(name))
 for name in sorted(include):addzip(z,'CH_C14_29/'+name,(D/name).read_bytes())
for p in (standalone,full):
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  assert len(z.namelist())==len(set(z.namelist()))
 print('PACKAGED',p.name,'files',len(zipfile.ZipFile(p).namelist()),'size',p.stat().st_size,'sha256',hashlib.sha256(p.read_bytes()).hexdigest())
