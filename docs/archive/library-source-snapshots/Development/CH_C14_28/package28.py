"""Create reproducible CH28 package with original CH27 dependency snapshot."""
from pathlib import Path
import hashlib,json,zipfile
D=Path(__file__).resolve().parent;BASE=D.parent
source=BASE/'Cognitum_CH_C14_27_Coupled_Fisher_Interval_Newton_Original_CH23_2026-11-02.zip'
dest=BASE/'Cognitum_CH_C14_28_Selective_MPFR_Cache_63_127_OriginalCH23_2026-11-02.zip'
if not (D/'study_summary.json').is_file() or not source.is_file():raise RuntimeError('Missing benchmark summary or source archive')
include=[]
for f in sorted(D.rglob('*')):
 if not f.is_file():continue
 rel=f.relative_to(D)
 if any(x in ('__pycache__','.pytest_cache','transport') for x in rel.parts):continue
 if rel.name.endswith('.pid') or rel.name.endswith('.pyc') or rel.name.endswith('.stdout') or rel.name=='batch.log' or rel.name=='control27.log':continue
 if 'runs' in rel.parts and (rel.name.endswith('.log') or rel.name.endswith('.stdout')):continue
 if rel.name=='SHA256SUMS_CH28.json':continue
 include.append((f,'CH_C14_28/'+str(rel)))
manifest={arc:hashlib.sha256(p.read_bytes()).hexdigest() for p,arc in include}
(D/'SHA256SUMS_CH28.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
with zipfile.ZipFile(source,'r') as z:
 old={i.filename:z.read(i.filename) for i in z.infolist() if not i.is_dir()}
with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
 for name,b in sorted(old.items()):z.writestr(name,b)
 for p,arc in include:z.write(p,arc)
 z.write(D/'SHA256SUMS_CH28.json','CH_C14_28/SHA256SUMS_CH28.json')
with zipfile.ZipFile(dest,'r') as z:
 for name,hash_ in manifest.items():
  assert hashlib.sha256(z.read(name)).hexdigest()==hash_,name
 print('PACKAGE',dest,'ZIP_FILES',len(z.namelist()),'MANIFEST',len(manifest),'SIZE',dest.stat().st_size)