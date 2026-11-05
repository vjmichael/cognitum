"""Portable Windows/Linux fresh independent CH40-F MPFR producer trace audit.

Does not load MPFR or trust the stored verification JSON. All original 15
producer traces are individually re-evaluated with an independent Fraction/
Decimal mathematical checker. The original CH39 ZIP is SHA256 pinned.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys,time,os,traceback
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from verify_trace40e import verify,PIN
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
ZIP=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
REPORT=ROOT/'CH40F_WINDOWS_RESULTS'

def sha(b):return hashlib.sha256(b).hexdigest()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)

def main():
    p=argparse.ArgumentParser();p.add_argument('--quick',action='store_true',help='only replay one full 127-node original case');p.add_argument('--output',type=pathlib.Path,default=REPORT);a=p.parse_args()
    if not ZIP.is_file() or sha(ZIP.read_bytes())!=PIN:raise RuntimeError('Original externally pinned CH39 ZIP differs or is missing')
    summary_file=ROOT/'CH40F_FULL_15_ACCEPTANCE.json'
    if not summary_file.exists():raise RuntimeError('Missing frozen CH40-F acceptance manifest')
    summary=json.loads(summary_file.read_text(encoding='utf-8'))
    if summary.get('source_archive_sha256')!=PIN or summary.get('scientific_release')!='NO_GO' or summary.get('case_count')!=15:raise RuntimeError('Untrusted acceptance manifest')
    cases=['one_event_n80_i00'] if a.quick else CASES
    out={'protocol':'CH40F-FRESH-MATH-WINDOWS-REPLAY-V1','status':'RUNNING','original_archive_sha256':PIN,'cases_required':len(cases),'results':{},'scientific_release':'NO_GO','global_optimality_certified':False}
    t0=time.perf_counter();a.output.mkdir(parents=True,exist_ok=True)
    for i,case in enumerate(cases,1):
        source=ROOT/'results'/f'{case}_127_original_mpfr_trace.json'
        if not source.is_file():raise RuntimeError('Missing original producer 127-node trace: '+case)
        raw=source.read_bytes();expected=summary['cases'][case]
        if sha(raw)!=expected['proof_trace_sha256']:raise RuntimeError('Producer trace SHA256 differs: '+case)
        t=time.perf_counter();trace=json.loads(raw);got=verify(trace,ZIP)
        checks=got['checks']
        if (got.get('case')!=case or checks['nodes']!=127 or checks['untrusted_caps']!=0 or
            checks['direct_certified']+checks['coupled_certified']!=127 or
            checks['inherited_caps_certified']!=127 or got['scientific_release']!='NO_GO' or
            got['global_optimality_certified'] or not got['all_recorded_selected_caps_certified']):
            raise RuntimeError('Independent bound proof refused: '+case)
        if checks!=expected['checks']:raise RuntimeError('Independent counts differ from accepted manifest: '+case)
        out['results'][case]={'status':'PASS','wall_seconds':round(time.perf_counter()-t,3),'direct':checks['direct_certified'],'coupled':checks['coupled_certified'],'nodes':127,'trace_sha256':sha(raw)}
        atomic_json(a.output/'CH40F_WINDOWS_REPLAY_RESULTS.json',out)
        print(f'[{i}/{len(cases)}] PASS {case}: 127 original producer caps independently certified',flush=True)
    out['status']='PASS_RESEARCH_FINITE_CAPS_ONLY';out['total_seconds']=round(time.perf_counter()-t0,3)
    out['no_production_or_global_claim']=True
    atomic_json(a.output/'CH40F_WINDOWS_REPLAY_RESULTS.json',out)
    print('CH40-F Windows full replay PASS:',len(cases),'cases. Scientific status NO_GO.',flush=True)
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        REPORT.mkdir(parents=True,exist_ok=True)
        (REPORT/'CH40F_WINDOWS_ERROR.log').write_text(traceback.format_exc(),encoding='utf-8')
        print('CH40-F FATAL',str(exc),flush=True);sys.exit(1)