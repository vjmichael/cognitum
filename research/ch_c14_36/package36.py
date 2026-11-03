"""Package CH36 unmodified CH35 original-data chain plus CH36 public sources.

Never archive an authority's signing secret. All CH23–35 upstream ZIP members
are checked byte-for-byte against their existing SHA256 manifest.
"""
import hashlib,json,shutil,tempfile,zipfile
from pathlib import Path
BASE=Path('/mnt/data');D=BASE/'CH_C14_36'
UPSTREAM=BASE/'Cognitum_CH_C14_35_Independent_Witness_Original_CH23_2026-11-02.zip'
FULL=BASE/'Cognitum_CH_C14_36_All_Original_Witness_Real_ENOSPC_2026-11-02.zip'
EVIDENCE=BASE/'Cognitum_CH_C14_36_Independent_Witness_Evidence_2026-11-02.zip'
FILES=['service36.py','batch36.py','audit36.py','recover36.py','fsync_fault36.c',
       'tests/test_syscall_fsync.py','tests/test_real_enospc.py',
       'tests/real_enospc_worker36.py','tests/test_restarted_duplicate36.py',
       'README.md','Engineering_Report_CH_C14_36.md','SOURCE_SHA256.json',
       'frozen_protocol.json','original15_results.json','witness_public_key.pem',
       'syscall_fsync_results.json','real_enospc_results.json',
       'duplicate_restart_results.json','ch36_storage_suite.log',
       'audit_results.json']
FILES += [str(x.relative_to(D)) for x in sorted((D/'public_witness').rglob('*')) if x.is_file()]
assert not any('secret' in f or f.endswith('.so') for f in FILES)
for f in FILES:
    if not (D/f).is_file():raise ValueError('Missing CH36 source/evidence '+f)
with tempfile.TemporaryDirectory(prefix='ch36-package-') as work:
    root=Path(work)
    with zipfile.ZipFile(UPSTREAM) as prior:
        if prior.testzip() is not None:raise ValueError('CH35 prior archive has invalid ZIP entry')
        prior.extractall(root)
        old={v.filename:hashlib.sha256(prior.read(v.filename)).hexdigest() for v in prior.infolist() if not v.is_dir()}
    for f in FILES:
        path=root/'CH_C14_36'/f
        path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(D/f,path)
    for key,val in old.items():
        if hashlib.sha256((root/key).read_bytes()).hexdigest()!=val:
            raise ValueError('Historical CH23–CH35 member changed: '+key)
    files=sorted(p for p in root.rglob('*') if p.is_file())
    manifest={str(f.relative_to(root)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    (root/'SHA256SUMS_FULL_CH36.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    with zipfile.ZipFile(FULL,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8,allowZip64=True) as z:
        for file in sorted(p for p in root.rglob('*') if p.is_file()):z.write(file,file.relative_to(root).as_posix())
    with zipfile.ZipFile(FULL) as z:
        if z.testzip() is not None:raise ValueError('CH36 ZIP CRC failed')
        actual=json.loads(z.read('SHA256SUMS_FULL_CH36.json'))
        if len(actual)!=len(manifest):raise ValueError('CH36 manifest omitted members')
        for name,expected in actual.items():
            if hashlib.sha256(z.read(name)).hexdigest()!=expected:raise ValueError('CH36 package member wrong '+name)
        if not all(z.read(name)==(root/name).read_bytes() for name in old):
            raise ValueError('Historical CH35 evidence changed in CH36 ZIP')
    with zipfile.ZipFile(EVIDENCE,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in FILES:
            if f.startswith('public_witness/') or f in (
                 'README.md','Engineering_Report_CH_C14_36.md','SOURCE_SHA256.json',
                 'frozen_protocol.json','original15_results.json','witness_public_key.pem',
                 'syscall_fsync_results.json','real_enospc_results.json',
                 'duplicate_restart_results.json','ch36_storage_suite.log','audit_results.json'):
                z.write(D/f,'CH_C14_36/'+f)
        z.writestr('CH36_PUBLIC_EVIDENCE_ONLY_NOT_FULL_REPRODUCTION.txt',
                   'No private signing key is included. MPFR source and original data are in the full reproduction package.\n')
    with zipfile.ZipFile(EVIDENCE) as z:
        if z.testzip() is not None:raise ValueError('CH36 evidence-only ZIP corrupt')
    report={'full_zip_name':FULL.name,'evidence_zip_name':EVIDENCE.name,
            'original_CH35_members_preserved':len(old),'original_case_count':15,
            'CH36_new_file_count':len(FILES),'full_manifest_verified_members':len(manifest),
            'full_zip_bytes':FULL.stat().st_size,
            'full_zip_sha256':hashlib.sha256(FULL.read_bytes()).hexdigest(),
            'evidence_zip_bytes':EVIDENCE.stat().st_size,
            'evidence_zip_sha256':hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
            'private_signing_key_included':False}
    (D/'package_results.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
