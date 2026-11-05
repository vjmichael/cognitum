"""Produce small, hash-verified CH33 evidence archive for GitHub research branch."""
import hashlib,json,shutil,zipfile
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parent
STAGE=R/'CH33_evidence_stage';OUT=R/'Cognitum_CH_C14_33_Evidence_15_OriginalCH23_2026-11-02.zip'
if STAGE.exists():shutil.rmtree(STAGE)
STAGE.mkdir()
for name in ['active','archives','chaos_active','chaos_archives']:
    shutil.copytree(D/name,STAGE/name,ignore=shutil.ignore_patterns('.writer.lock'))
for f in ['Engineering_Report_CH_C14_33.md','README.md','frozen_protocol.json','frozen_protocol.sha256',
          'benchmark_results.json','checkpoint_heads.json','chaos_results.json',
          'benchmark.log','chaos.log','chaos_verify2.log','tests_final.log']:
    shutil.copy2(D/f,STAGE/f)
files=sorted(p for p in STAGE.rglob('*') if p.is_file())
manifest={str(p.relative_to(STAGE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(STAGE/'SHA256SUMS_EVIDENCE_CH33.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(p for p in STAGE.rglob('*') if p.is_file()):z.write(f,f.relative_to(STAGE).as_posix())
with zipfile.ZipFile(OUT) as z:
    if z.testzip():raise ValueError('Evidence ZIP not readable')
    listed=json.loads(z.read('SHA256SUMS_EVIDENCE_CH33.json'))
    for p,h in listed.items():
        if hashlib.sha256(z.read(p)).hexdigest()!=h:raise ValueError('Evidence bytes altered')
out_sha=hashlib.sha256(OUT.read_bytes()).hexdigest()
(D/'evidence_package_summary.json').write_text(json.dumps({'filename':OUT.name,'bytes':OUT.stat().st_size,
   'sha256':out_sha,'verified_files':len(manifest),'total_archive_entries':len(manifest)+1},indent=2,sort_keys=True)+'\n')
print('Evidence ZIP',OUT,'bytes',OUT.stat().st_size,'entries',len(manifest)+1,'sha256',out_sha)