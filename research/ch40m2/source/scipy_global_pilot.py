"""Standard SciPy differential_evolution search on the 15 pinned original cases.
Returns float candidates ONLY. No global certificate; exact checker must accept a point.
"""
from __future__ import annotations
import argparse,hashlib,json,time
from pathlib import Path
from scipy.optimize import differential_evolution
from frozen40m2 import load_cases,float_objective,validated_candidate


def main():
 p=argparse.ArgumentParser();p.add_argument('--traces',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--previous-scipy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--maxiter',type=int,default=20);args=p.parse_args()
 if not 1<=args.maxiter<=300:raise ValueError('iteration limit')
 cases=load_cases(args.traces,args.pins)
 import runner40m2
 if hashlib.sha256(args.previous_scipy.read_bytes()).hexdigest()!=runner40m2.PINNED_M1_SHA256:raise ValueError('Untrusted historical SciPy comparator')
 old={r['case']:r for r in json.loads(args.previous_scipy.read_text())['cases']}
 report={'protocol':'CH40M2_SCIPY_DIFFERENTIAL_EVOLUTION_HEURISTIC_V1','scientific_release':'NO_GO',
         'seed':31,'maxiter':args.maxiter,'popsize':6,'result_class':'FLOAT_CANDIDATES_ONLY_UNCHECKED_NO_GLOBAL_PROOF','cases':[]}
 for c in cases:
  t=time.process_time(); bounds=[tuple(r) for r in c.bounds]
  res=differential_evolution(lambda b:-float_objective(c,b),bounds,seed=31,maxiter=args.maxiter,popsize=6,
                             workers=1,polish=True,tol=1e-6,updating='immediate')
  v=float_objective(c,res.x); historic=float(old[c.name]['candidate_float'])
  ok=validated_candidate(c,res.x)
  rec={'case':c.name,'sha256':c.source_sha256,'candidate':[str(float(v)) for v in res.x],
       'new_float_value':v,'old_float_value':historic,'heuristic_delta_vs_old':v-historic,
       'new_candidate_feasible':ok,'nfev':int(res.nfev),'success':bool(res.success),
       'cpu_seconds_search_only':round(time.process_time()-t,6),'independently_certified':False}
  report['cases'].append(rec);args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
  print(c.name,f'heuristic delta {v-historic:+.7f}',flush=True)
 report['complete']=True;args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()

