"""Deterministic research package with explicit SHA256 manifest and no keys."""
from __future__ import annotations
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent
FULL=OUT/'Cognitum_CH_C14_40_E_Actual_MPFR_Producer_Traces_2026-11-03.zip'
SOURCE=OUT/'Cognitum_CH_C14_40_E_Source_And_Adversarial_Tests_2026-11-03.zip'
BASE_FILES=['README.md','Engineering_Report_CH_C14_40_E.md','prepare40e.py','run_trace40e.py',
  'verify_trace40e.py','rational_kernel40d.py','batch40e.py','compare_baseline40e.py',
  'audit40e.py','finalize40e.py','pack40e.py','RUN_CH40E_WINDOWS_READONLY.cmd',
  'source/producer_trace40e.py','tests/test_trace40e.py','CH40E_FINAL_ACCEPTANCE.json']
REPLAY_FILES=[
  'results/'+p.name for p in sorted((ROOT/'results').glob('*_1_original_mpfr_trace.json'))
]+['results/one_event_n80_i00_127_original_mpfr_trace.json',
  'results/one_event_n80_i00_127_checked.json',
  'results/one_event_n80_i00_31_checked.json',
  'results/full127_unchanged_baseline.log',
  'results/full127_verified_final_outward.log',
  'results/test_trace40e_final.log',
  'results/batch_1/SUMMARY.json',
  'CH40E_READONLY_RESULTS/CH40E_READONLY_AUDIT.json']
ARCHIVE='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 cases=[f for f in REPLAY_FILES if f.endswith('_1_original_mpfr_trace.json')]
 if len(cases)!=15:raise RuntimeError(f'Missing original root case traces: {len(cases)}')
 files=sorted(set(BASE_FILES+REPLAY_FILES+[ARCHIVE]))
 manifest={'protocol':'CH40E-FILE-MANIFEST-V1','scientific_release':'NO_GO','file_sha256':{}}
 for rel in files:
  b=(ROOT/rel).read_bytes();manifest['file_sha256'][rel]=sha(b)
 if manifest['file_sha256'][ARCHIVE]!='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b':raise ValueError('Pinned original archive altered')
 (ROOT/'CH40E_MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n')
 def build(dst,selection):
  with zipfile.ZipFile(dst,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for name in sorted(selection+['CH40E_MANIFEST_SHA256.json']):
    z.write(ROOT/name,arcname=name)
  with zipfile.ZipFile(dst) as z:
   for name in selection:
    if sha(z.read(name))!=manifest['file_sha256'][name]:raise RuntimeError('ZIP data changed on write '+name)
  return {'name':dst.name,'size':dst.stat().st_size,'sha256':sha(dst.read_bytes()),'file_count':len(selection)+1}
 a=build(FULL,files)
 b=build(SOURCE,sorted(set(BASE_FILES)))
 record={'full':a,'source':b,'source_zip':ARCHIVE,'source_pinned_sha256':manifest['file_sha256'][ARCHIVE],
         'original_root_traces':15,'full127_traces':1,'scientific_release':'NO_GO'}
 (ROOT/'CH40E_PACKAGE_RESULTS.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record,indent=2))
if __name__=='__main__':main()