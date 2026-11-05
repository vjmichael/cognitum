"""Package CH32 dependencies and CH33 exact original-data compaction evidence."""
import hashlib,json,shutil,tempfile,zipfile
from pathlib import Path
R=Path('/mnt/data');D=R/'CH_C14_33'
SOURCE=R/'Cognitum_CH_C14_32_Durable_Proof_Journal_Original_CH23_2026-11-02.zip'
OUT=R/'Cognitum_CH_C14_33_Compacted_Journal_Original_CH23_2026-11-02.zip'
STAGE=R/'CH33_package_stage'
if STAGE.exists():shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)
with zipfile.ZipFile(SOURCE) as z:
    if z.testzip() is not None:raise ValueError('Historical CH32 package corrupt')
    z.extractall(STAGE)
TARGET=STAGE/'CH_C14_33'
include=['compaction33.py','restart33.py','benchmark33.py','chaos33.py',
         'finalize_chaos33.py','freeze33.py','frozen_protocol.json','frozen_protocol.sha256',
         'audit33.py','tests/test_compaction.py','README.md','make_report33.py',
         'package33.py','Engineering_Report_CH_C14_33.md',
         'benchmark_results.json','checkpoint_heads.json','chaos_results.json',
         'benchmark.log','chaos.log','tests_final.log','chaos_verify2.log']
for rel in include:
    file=D/rel
    if not file.is_file():raise FileNotFoundError(file)
    dest=TARGET/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
for folder in ('active','archives','chaos_active','chaos_archives'):
    if not (D/folder).is_dir():raise FileNotFoundError(D/folder)
    shutil.copytree(D/folder,TARGET/folder,ignore=shutil.ignore_patterns('.writer.lock','.pytest_cache','__pycache__'))
allfiles=sorted([f for f in STAGE.rglob('*') if f.is_file()])
manifest={str(p.relative_to(STAGE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in allfiles}
(STAGE/'SHA256SUMS_FULL_CH33.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
    for f in sorted(p for p in STAGE.rglob('*') if p.is_file()):
        z.write(f,f.relative_to(STAGE).as_posix())
with zipfile.ZipFile(OUT) as z:
    if z.testzip() is not None:raise ValueError('Built ZIP corrupted')
    stored=json.loads(z.read('SHA256SUMS_FULL_CH33.json'))
    if len(stored)!=len(manifest):raise ValueError('Manifest count mismatch')
    for name,sha in stored.items():
        if hashlib.sha256(z.read(name)).hexdigest()!=sha:raise ValueError('Packaged SHA mismatch: '+name)
summary={'archive':OUT.name,'zip_entries':len(manifest)+1,
         'sha256_verified_files':len(manifest), 'zip_bytes':OUT.stat().st_size,
         'zip_sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
         'original_CH32_archive_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
(D/'package_summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
print(json.dumps(summary,indent=2,sort_keys=True))