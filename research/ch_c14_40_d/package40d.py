"""Construct SHA-256-manifested, source-locked CH40-D Windows reproduction archives."""
from __future__ import annotations
import hashlib,json,pathlib,zipfile
from verify_original40 import ORIGINAL_ZIP_SHA256
R=pathlib.Path(__file__).resolve().parent
SOURCE=[
 'README.md','PROTOCOL_CH40D.md','Engineering_Report_CH_C14_40_D.md',
 'rational_kernel40d.py','checker_interval40d.py','witness_producer40d.py','witness_checker40d.py',
 'batch40d.py','finalize40d.py','package40d.py','RUN_CH40D_WINDOWS.cmd',
 'exact_decimal40.py','independent_checker40.py','verify_original40.py',
 'independent_bounds40b.py','independent_newton40b.py','batch40b.py',
 'tests/test_witness40d.py'
]
ORIGINAL='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
CASES=sorted(p.name for p in (R/'CH40D_RESULTS').glob('*.json') if p.name not in ('CH40D_SUMMARY.json',))
ASSERT=['CH40D_FINAL_ACCEPTANCE.json']
assert len(CASES)==16 and all(n in CASES for n in ASSERT),CASES
REC=[f'CH40D_RESULTS/{n}' for n in CASES]
LOGS=['ch40d_tests.log','independent_final_audit.log','replay_group1_final.log','replay_group2_final.log','replay_group3_final.log','replay_group3_repair.log']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if sha(R/ORIGINAL)!=ORIGINAL_ZIP_SHA256:raise ValueError('Untrusted original historical archive')
full=SOURCE+REC+LOGS+[ORIGINAL]
for name in full:
    if not (R/name).is_file():raise FileNotFoundError(name)
manifest={'protocol':'CH40D-LOCAL-WITNESS-V1','original_ch39_zip_sha256':ORIGINAL_ZIP_SHA256,
    'counts':{'source_files':len(SOURCE),'original_cases':15,'witnesses_accepted':60,'adversarial_tests_pass':36},
    'files':{name:sha(R/name) for name in sorted(full)},'scientific_release':'NO_GO'}
(R/'CH40D_PACKAGE_MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
full.append('CH40D_PACKAGE_MANIFEST_SHA256.json')
source=SOURCE+['CH40D_PACKAGE_MANIFEST_SHA256.json']
out=R.parent/'Cognitum_CH_C14_40_D_Checkable_Local_Proof_Witnesses_Original_CH23_2026-11-03.zip'
small=R.parent/'Cognitum_CH_C14_40_D_Source_And_Math_Tests_2026-11-03.zip'
for dst,names in ((out,full),(small,source)):
    with zipfile.ZipFile(dst,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted(names):z.write(R/name,arcname=name)
    with zipfile.ZipFile(dst) as z:
        for name in names:
            if hashlib.sha256(z.read(name)).hexdigest()!=sha(R/name):raise AssertionError('Archive corrupted: '+name)
    print(dst, dst.stat().st_size,'bytes',len(names),'members',flush=True)
(R/'CH40D_PACKAGE_RESULTS.json').write_text(json.dumps({'full_zip':out.name,'full_sha256':sha(out),'source_zip':small.name,'source_sha256':sha(small),'source_sha256_manifest':sha(R/'CH40D_PACKAGE_MANIFEST_SHA256.json')},indent=2)+'\n')
