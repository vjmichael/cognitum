"""All frozen original CH23 cases through the patched historical producer.

Incremental results; no synthetic data, no substitution of archived signatures
for live original 160-bit MPFR calculations.
"""
import argparse,subprocess,sys,pathlib,json,time,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
ARCHIVE=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
def main():
 p=argparse.ArgumentParser();p.add_argument('--nodes',type=int,choices=[1,7,15,31,63,127],default=1);a=p.parse_args()
 out=ROOT/'results'/f'batch_{a.nodes}';out.mkdir(parents=True,exist_ok=True)
 finished={};t0=time.perf_counter()
 for index,case in enumerate(CASES,1):
  path=ROOT/'results'/f'{case}_{a.nodes}_original_mpfr_trace.json'
  cmd=[sys.executable,str(ROOT/'run_trace40e.py'),'--archive',str(ARCHIVE),'--case',case,'--nodes',str(a.nodes),'--reuse-workspace']
  if not path.exists():subprocess.run(cmd,check=True,timeout=3600)
  check=out/(case+'.json')
  run=[sys.executable,str(ROOT/'verify_trace40e.py'),'--archive',str(ARCHIVE),'--trace',str(path),'--output',str(check)]
  subprocess.run(run,check=True,stdout=subprocess.DEVNULL,timeout=3600)
  got=json.loads(check.read_text());finished[case]={'status':'PASS','checks':got['checks'],'source_trace_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  (out/'SUMMARY.json').write_text(json.dumps({'completed':len(finished),'total':len(CASES),'results':finished,'scientific':'NO_GO'},indent=2)+'\n')
  print(f'[{index}/{len(CASES)}] PASS original {case}: {got["checks"]["coupled_certified"]} coupled, {got["checks"]["direct_certified"]} direct',flush=True)
 print('FINISHED',len(finished),'cases in',round(time.perf_counter()-t0,2),'sec',flush=True)
if __name__=='__main__':main()
