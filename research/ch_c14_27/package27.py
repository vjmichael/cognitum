"""Bundle complete CH27 research artifacts with deterministic SHA256 manifest."""
from __future__ import annotations
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parent.parent;D=ROOT/'CH_C14_27'
C23=ROOT/'recovered_ch23'/'CH_C14_23';C24=ROOT/'CH_C14_24';C25=ROOT/'CH_C14_25';C26=ROOT/'CH_C14_26'
files={}
def add(name,path):
 if not path.is_file():raise FileNotFoundError(str(path))
 files[name]=path.read_bytes()
for file in ['frozen_protocol.json','ch22_pinned.py','run.py','bounded_global.py','independent_audit.py',
             'test_ch23.py','results.jsonl','bounded_results.json','audit.json','execution.log',
             'Engineering_Report_CH_C14_23.md','README.md','SHA256SUMS.json']:
 add('CH_C14_23/'+file,C23/file)
for file in ['mpfr_interval.py','verified_bnb.py','verify_certificate.py']:
 add('CH_C14_24/'+file,C24/file)
for file in ['frozen_protocol_B.json','frozen_protocol_B.sha256','study_summary.json']:
 add('CH_C14_25/'+file,C25/file)
for path in sorted((C25/'inputs').glob('*.json')):
 add('CH_C14_25/inputs/'+path.name,path)
for file in ['improved_bounds.py','solver26.py','verifier26.py','frozen_protocol.json','study_summary.json']:
 add('CH_C14_26/'+file,C26/file)
source=['coupled27.py','interval_newton27.py','solver27.py','verifier27.py','freeze27.py',
        'frozen_duals.json','frozen_protocol.json','frozen_protocol.sha256',
        'frozen_newton_probes.json','probe_newton27.py','run_case27.py','compare_ch26_15.py',
        'root_profile27.py','root_profile.json','newton_probe_results.json','audit27.py',
        'study_summary.json','Engineering_Report_CH_C14_27.md','README.md','make_report27.py',
        'package27.py']
for name in source:add('CH_C14_27/'+name,D/name)
for subfolder in ['certificates','verifications','comparator15','logs','tests']:
 for path in sorted((D/subfolder).glob('*.json' if subfolder!='tests' else 'test_*.py')):
  if subfolder=='logs' and path.name.startswith('compare26_'):continue
  add('CH_C14_27/'+subfolder+'/'+path.name,path)
add('CH_C14_27/audit.stdout',D/'audit.stdout')
manifest={'milestone':'CH-C14-27','notes':'Exact SHA-256 of every bundled research file, excluding manifest itself.',
          'files_sha256':{path:hashlib.sha256(data).hexdigest() for path,data in sorted(files.items())}}
manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
(D/'SHA256SUMS.json').write_bytes(manifest_bytes)
files['CH_C14_27/SHA256SUMS.json']=manifest_bytes
all_pkg=ROOT/'Cognitum_CH_C14_27_Coupled_Fisher_Interval_Newton_Original_CH23_2026-11-02.zip'
evidence_pkg=ROOT/'CH_C14_27_Evidence_Original15.zip'
for out,subset in [(all_pkg,sorted(files)),(evidence_pkg,sorted(p for p in files if p.startswith('CH_C14_27/') or p.startswith('CH_C14_25/inputs/')))]:
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name in subset:z.writestr(name,files[name])
 with zipfile.ZipFile(out) as z:
  assert z.testzip() is None
  names=z.namelist()
  if out==all_pkg:
   assert len(names)==len(files)
   for name,h in manifest['files_sha256'].items():assert hashlib.sha256(z.read(name)).hexdigest()==h,name
 print('ZIP',out,'bytes',out.stat().st_size,'files',len(subset),'sha256',hashlib.sha256(out.read_bytes()).hexdigest())
print('MANIFEST',len(manifest['files_sha256']))
