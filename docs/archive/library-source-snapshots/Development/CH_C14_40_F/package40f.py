"""Deterministically pack original CH40-F mathematical witness traces with hash manifest.

Refuses to ship incomplete or unverified 15-case matrix. Scientific NO_GO.
"""
from __future__ import annotations
import pathlib,hashlib,json,zipfile,os,time
ROOT=pathlib.Path(__file__).resolve().parent
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
SOURCES=['producer_batch40f.py','verify_batch40f.py','verify_tail40f.py','baseline_batch40f.py',
 'consolidate40f.py','research_receipt40f.py','test_live_research_receipt40f.py',
 'windows_readonly40f.py','RUN_CH40F_WINDOWS_READONLY.cmd','README.md',
 'Engineering_Report_CH_C14_40_F.md','CH40F_SOURCE_SHA256.json',
 'make_report40f.py','package40f.py',
 'verify_trace40e.py','rational_kernel40d.py','prepare40e.py','run_trace40e.py',
 'compare_baseline40e.py','source/producer_trace40e.py','tests/test_research_receipt40f.py',
 'logs/research_receipt_tests.log','logs/live_receipt_replay.log','logs/ch40e_inherited_adversarial17.log',
 'CH40F_RESEARCH_RECEIPT_SCOPE_TEST.json']
REPORTS=['CH40F_FULL_15_ACCEPTANCE.json','producer_progress.json','verifier_progress.json',
 'verifier_tail_progress.json','baseline_progress.json']
ORIGINAL='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
def sha(b):return hashlib.sha256(b).hexdigest()
def pack():
 accepted=json.loads((ROOT/'CH40F_FULL_15_ACCEPTANCE.json').read_text())
 if accepted['case_count']!=15 or accepted['full_node_count']!=1905 or accepted['total_checks']['untrusted_caps']!=0 or accepted['scientific_release']!='NO_GO':raise ValueError('Not full independent 15-case acceptance')
 paths=SOURCES+REPORTS+[ORIGINAL]
 paths += [f'results/{case}_127_original_mpfr_trace.json' for case in CASES]
 paths += [f'results/{case}_127_audit.json' for case in CASES]
 # All actual pass logs for scientific provenance, no unrelated user data.
 paths += [f'logs/{case}_producer.log' for case in CASES if case!='one_event_n80_i00']
 paths += [f'logs/{case}_audit.log' for case in CASES if case!='one_event_n80_i00']
 paths += [f'logs/{case}_baseline.log' for case in CASES if case!='one_event_n80_i00']
 files={};size=0
 for path in paths:
  q=ROOT/path
  if not q.is_file():raise ValueError('Missing item '+path)
  data=q.read_bytes();files[path]={'sha256':sha(data),'bytes':len(data)};size+=len(data)
 manifest={'protocol':'CH40F-EVIDENCE-MANIFEST-V1','original_archive_sha256':accepted['source_archive_sha256'],'scientific_release':'NO_GO','entries':files,'original_cases':CASES,'total_bytes_uncompressed':size}
 manifest_data=json.dumps(manifest,sort_keys=True,indent=2).encode()+b'\n'
 (ROOT/'CH40F_MANIFEST_SHA256.json').write_bytes(manifest_data)
 output=ROOT.parent/'Cognitum_CH_C14_40_F_All_15_Original_MPFR_Producer_Certificates_2026-11-03.zip'
 with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for i,path in enumerate(paths,1):
   z.write(ROOT/path,path)
   if i%15==0:print('PACK',i,'/',len(paths),path,flush=True)
  z.writestr('CH40F_MANIFEST_SHA256.json',manifest_data)
 with zipfile.ZipFile(output) as z:
  expected=set(paths)|{'CH40F_MANIFEST_SHA256.json'}
  if set(z.namelist())!=expected:raise ValueError('Archive missing/extra entry')
  for path in paths:
   if sha(z.read(path))!=files[path]['sha256']:raise ValueError('Archive member mismatch '+path)
 results={'package_sha256':sha(output.read_bytes()),'package_bytes':output.stat().st_size,
          'original_source_sha256':accepted['source_archive_sha256'],'file_count':len(expected),
          'original_cases':15,'nodes_independently_certified':1905,'scientific_release':'NO_GO',
          'repository_store':'source_and_acceptance_only; keep bulky raw case traces in the archive'}
 (ROOT/'CH40F_PACKAGE_RESULTS.json').write_text(json.dumps(results,indent=2)+'\n')
 source_out=ROOT.parent/'Cognitum_CH_C14_40_F_Source_Tests_2026-11-03.zip'
 with zipfile.ZipFile(source_out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in SOURCES+[x for x in REPORTS if x!='producer_progress.json'] + ['CH40F_MANIFEST_SHA256.json','CH40F_PACKAGE_RESULTS.json']:
   z.write(ROOT/p,p)
 print('CH40F PACKAGE PASS',json.dumps(results),flush=True)
if __name__=='__main__':pack()