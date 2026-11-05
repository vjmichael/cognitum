"""Reproducible source-manifest packages; never include private keys/caches."""
from __future__ import annotations
import hashlib,json,pathlib,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=['rule_checker40c.py','attestation_policy40c.py','batch40c.py',
 'exact_decimal40.py','independent_checker40.py','verify_original40.py',
 'independent_bounds40b.py','independent_newton40b.py','batch40b.py',
 'tests/test_rule_attestation40c.py','RUN_CH40C_WINDOWS.cmd',
 'README.md','Engineering_Report_CH_C14_40_C.md','ch40c_tests.log',
 'CH40C_batch_verified.log','CH40C_RESULTS_VERIFIED/CH40C_SUMMARY.json']
SOURCE.extend('CH40C_RESULTS_VERIFIED/'+p.name for p in sorted((ROOT/'CH40C_RESULTS_VERIFIED').glob('*.json')) if p.name!='CH40C_SUMMARY.json')
ORIGINAL='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
expected='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
assert hashlib.sha256((ROOT/ORIGINAL).read_bytes()).hexdigest()==expected
for path in SOURCE:
 assert (ROOT/path).is_file(),path
source={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE+[ORIGINAL]}
(ROOT/'CH40C_SOURCE_MANIFEST_SHA256.json').write_text(json.dumps({'version':'CH40-C','files':source,'scientific_release':'NO_GO'},indent=2)+'\n')
def mk(dest,include_original):
 names=SOURCE+['CH40C_SOURCE_MANIFEST_SHA256.json']+([ORIGINAL] if include_original else [])
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
  for name in names:
   data=(ROOT/name).read_bytes()
   entry=zipfile.ZipInfo(name,date_time=(2026,11,3,12,0,0))
   entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16
   z.writestr(entry,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=7)
 with zipfile.ZipFile(dest) as z:
  for name in names:
   assert z.read(name)==(ROOT/name).read_bytes(),name
 return {'name':dest.name,'size':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'entries':len(names)}
full=mk(ROOT.parent/'Cognitum_CH_C14_40_C_Producer_Rule_Replay_Original_CH23_2026-11-03.zip',True)
sourcepkg=mk(ROOT.parent/'Cognitum_CH_C14_40_C_Source_And_Tests_2026-11-03.zip',False)
report={'full':full,'source':sourcepkg,'original_source_pin':expected,'source_member_count':len(source)}
(ROOT/'CH40C_PACKAGE_RESULTS.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))