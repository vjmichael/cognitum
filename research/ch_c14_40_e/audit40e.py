"""Independent signed-source 15-root + full 127-node read-only mathematical audit.

Runs WITHOUT MPFR; validates mathematical trace evidence with separate exact
rational plus 95-digit Decimal kernel. No production or scientific GO claim.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,time
from verify_trace40e import verify
ROOT=pathlib.Path(__file__).resolve().parent
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=ROOT);p.add_argument('--results',type=pathlib.Path,default=ROOT/'CH40E_READONLY_RESULTS');p.add_argument('--full127',action='store_true');a=p.parse_args()
 zipname='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
 original=a.root/zipname
 a.results.mkdir(parents=True,exist_ok=True);cases={};t0=time.perf_counter()
 for i,case in enumerate(CASES,1):
  f=a.root/'results'/f'{case}_1_original_mpfr_trace.json'
  rec=verify(json.loads(f.read_text()),original)
  cases[case]={'status':'PASS','source_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),**rec['checks'],'finite_root_gap_certified':rec['finite_root_gap_certified']}
  summary={'status':'PASS_PARTIAL' if i<len(CASES) else 'PASS','original_root_cases_verified':i,'expected_root_cases':15,'roots':cases,'scientific_release':'NO_GO'}
  (a.results/'CH40E_READONLY_AUDIT.json').write_text(json.dumps(summary,indent=2)+'\n')
  print(f'[{i}/15] original historical MPFR root independently certified: {case}',flush=True)
 if a.full127:
  f=a.root/'results'/'one_event_n80_i00_127_original_mpfr_trace.json'
  got=verify(json.loads(f.read_text()),original,progress=True)
  summary['full127_case']='one_event_n80_i00';summary['full127_checks']=got['checks'];summary['full127_finite_root_gap_certified']=got['finite_root_gap_certified'];summary['full127_trace_sha256']=hashlib.sha256(f.read_bytes()).hexdigest()
 summary['elapsed_seconds']=round(time.perf_counter()-t0,2)
 (a.results/'CH40E_READONLY_AUDIT.json').write_text(json.dumps(summary,indent=2)+'\n')
 print('PASS scoped research trace verification: 15 original root cases' + (' and complete 127-node one-event tree' if a.full127 else ''),flush=True)
if __name__=='__main__':main()
