"""Strict CH40-E research acceptance manifest; no scientific promotion."""
from __future__ import annotations
import pathlib,hashlib,json,re,sys
ROOT=pathlib.Path(__file__).resolve().parent
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
 orig=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
 if sha(orig)!=PIN:raise ValueError('Missing externally pinned original CH39 source')
 sub=ROOT/'results'/'batch_1'/'SUMMARY.json'; roots=json.loads(sub.read_text())
 if roots['completed']!=15 or set(roots['results'])!=set(CASES) or any(rec['status']!='PASS' or rec['checks']['nodes']!=1 or rec['checks']['untrusted_caps'] for rec in roots['results'].values()):raise ValueError('Incomplete original root source audit')
 root_trace={c:sha(ROOT/'results'/f'{c}_1_original_mpfr_trace.json') for c in CASES}
 if any(roots['results'][c]['source_trace_sha256']!=h for c,h in root_trace.items()):raise ValueError('Root file changed after verification')
 verify=json.loads((ROOT/'results'/'one_event_n80_i00_127_checked.json').read_text())
 counts=verify['checks']
 if (counts['nodes'],counts['coupled_certified'],counts['direct_certified'],counts['inherited_caps_certified'],counts['untrusted_caps'])!=(127,44,83,127,0):raise ValueError('Full producer cap certification mismatch')
 if verify['finite_root_gap_certified'] or verify['scientific_release']!='NO_GO':raise ValueError('Scientific promotion forbidden')
 baseline=(ROOT/'results'/'full127_unchanged_baseline.log').read_text()
 if 'all certificate proof fields identical' not in baseline or (ROOT/'results'/'full127_unchanged_baseline.exit').read_text().strip()!='0':raise ValueError('Original source perturbation comparison unavailable')
 tests=(ROOT/'results'/'test_trace40e_final.log').read_text()
 if not re.search(r'Ran 17 tests',tests) or not re.search(r'\nOK\s*$',tests):raise ValueError('Adversarial acceptance failed')
 source=[]
 for f in ['prepare40e.py','run_trace40e.py','verify_trace40e.py','rational_kernel40d.py','audit40e.py','batch40e.py','compare_baseline40e.py','source/producer_trace40e.py','tests/test_trace40e.py','RUN_CH40E_WINDOWS_READONLY.cmd']:
  p=ROOT/f;source.append({'path':f,'sha256':sha(p)})
 summary={
  'milestone':'CH40-E','acceptance':'PASS_SCOPED_ORIGINAL_PRODUCER_UPPER_CAP_REPLAY',
  'original_ch39_archive_sha256':PIN,
  'original_data_cases_root_verified':15,'root_results':{c:roots['results'][c]['checks'] for c in CASES},
  'producer_full_tree_case':'one_event_n80_i00','producer_full_tree_nodes':127,
  'producer_full_tree_verified':verify,'full127_source_trace_sha256':sha(ROOT/'results'/'one_event_n80_i00_127_original_mpfr_trace.json'),
  'unmodified_source_equivalence':'ALL_PROOF_FIELDS_EQUAL_EXCEPT_MEASURED_TIMINGS',
  'adversarial_tests_passed':17,'adversarial_tests_failed':0,
  'source_sha256':source,
  'root_trace_sha256':root_trace,
  'research_restrictions':['Original frozen input and CH29 source SHA-256 verified before instrumentation',
   'New emitted MPFR exact binary dyads and supporting points certified by separate Fraction/Decimal implementation',
   'No original Taylor/Newton accepted action, so those claims remain UNTESTED',
   'Other fourteen full 127-node producer trees not yet generated and audited',
   'Independent Decimal exp/ln still assumes the correctness of libmpdec',
   'CH39 live five-UID signer/admission integration not changed',
   'Finite-root 0.05 gap remains unproved and unrestricted global optimality is NO_GO',
   'New CH40-E Windows runtime not yet tested'],
  'scientific_release':'NO_GO','production_integration':False}
 dst=ROOT/'CH40E_FINAL_ACCEPTANCE.json';dst.write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({'acceptance':summary['acceptance'],'roots':15,'full_nodes':127,'source_equivalence':'PASS','tests':17,'finite_root_gap':False,'summary':str(dst)},indent=2))
if __name__=='__main__':main()