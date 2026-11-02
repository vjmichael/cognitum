"""Self-contained CH23-CH30 reproduction package with full SHA-256 manifest."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib,json
BASE=Path(__file__).resolve().parent.parent
D=BASE/'CH_C14_30'
old=BASE/'Cognitum_CH_C14_29_Parent_Inheritance_63_127_Equal_CPU_Original_CH23_2026-11-02.zip'
dest=BASE/'Cognitum_CH_C14_30_Incremental_Verifier_Original_CH23_2026-11-02.zip'
if not (D/'benchmark_results.json').exists():raise RuntimeError('Full 15-case benchmark not completed')
results=json.loads((D/'benchmark_results.json').read_text())
if results['cohort_size']!=15:raise RuntimeError('Incomplete original-data cohort')
add=[
 'verifier30.py','benchmark30.py','audit30.py','make_report30.py','package30.py',
 'tests/test_incremental.py','frozen_protocol.json','frozen_protocol.sha256',
 'README.md','SOURCE_SHA256.json','benchmark_results.json','Engineering_Report_CH_C14_30.md','bench_all.log']
entries={};sha=lambda b:hashlib.sha256(b).hexdigest()
with ZipFile(old,'r') as oldzip:
    for obj in oldzip.infolist():
        if obj.is_dir():continue
        name=obj.filename
        if name.startswith('/') or '\\' in name or '..' in Path(name).parts:raise ValueError('Unsafe archive path')
        if name in entries:raise ValueError('Duplicate archive file')
        entries[name]=oldzip.read(obj)
for filename in add:
    f=D/filename
    if not f.is_file():raise FileNotFoundError(f)
    key='CH_C14_30/'+filename
    if key in entries:raise ValueError('Duplicate CH30 file')
    entries[key]=f.read_bytes()
manifest={key:sha(value) for key,value in sorted(entries.items())}
manifestpath='CH_C14_30/SHA256SUMS_FULL.json'
entries[manifestpath]=(json.dumps({'scope':'Original CH23-30 replay reproduction','files':manifest},indent=2,sort_keys=True)+'\n').encode()
with ZipFile(dest,'w',ZIP_DEFLATED,compresslevel=6) as z:
    for key,value in sorted(entries.items()):z.writestr(key,value)
with ZipFile(dest) as z:
    m=json.loads(z.read(manifestpath));assert len(m['files'])==len(entries)-1
    for key,h in m['files'].items():
        if sha(z.read(key))!=h:raise AssertionError('Package hash failure '+key)
print('WROTE',dest,'ENTRIES',len(entries),'SHA_VERIFIED',len(manifest),'BYTES',dest.stat().st_size)
(D/'package_manifest_summary.json').write_text(json.dumps({'package_filename':dest.name,'package_sha256':sha(dest.read_bytes()),'entries':len(entries),'sha256_checked':len(manifest),'data_source':'exact_original_CH23_15_with_CH29_frozen_certificates'},indent=2)+'\n')
