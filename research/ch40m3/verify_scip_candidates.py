"""Independent Arb+rational point checks for all native SCIP feasible proposals."""
from pathlib import Path
import sys,json,time
from fractions import Fraction as F
sys.path[:0]=['/mnt/data/CH40M3/site','/mnt/data/CH40M2/source']
from frozen40m2 import load_cases,float_objective,point_lower
from flint_arb_backend import arb_point
report=json.loads(Path('/mnt/data/CH40M3/results/scip15_bounded.json').read_text());cases={c.name:c for c in load_cases(Path('/mnt/data/CH40K/traces'),Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json'))}
out=[]
for r in report['cases']:
    if not r.get('feasible_frozen_domain'):continue
    c=cases[r['case']];b=r['candidate'];t=time.process_time()
    rec={'case':c.name,'source_sha256':c.source_sha256,'candidate':b,'objective_float_candidate':float_objective(c,b),'objective_float_original':float_objective(c,c.incumbent)}
    try:
        g=arb_point(c,b);a=point_lower(c,b,Path('/mnt/data/CH40J/source'))
        lo,hi=F(g['lower']),F(g['upper'])
        rec['independent_point_overlap']=max(lo,a.lo)<=min(hi,a.hi)
        rec['flint_contains_reference']=lo<=a.lo and a.hi<=hi
        original=point_lower(c,c.incumbent,Path('/mnt/data/CH40J/source'))
        rec['strict_lower_bound_increase']=bool(a.lo>original.lo and rec['independent_point_overlap'])
        rec['material_verified_gain_over_original']=bool(a.lo>original.hi+F(1,10**8) and rec['independent_point_overlap'])
        rec['exact_gain_lower']=str(a.lo-original.hi)
        rec['verification_threshold']='1e-8 (candidate lower must exceed prior upper by this margin)'
        rec['new_bound_lower_approx']=float(a.lo)
        rec['original_bound_lower_approx']=float(original.lo)
    except Exception as e:rec['status']='UNRESOLVED';rec['error']=repr(e)[:220]
    rec['cpu_seconds']=round(time.process_time()-t,3)
    out.append(rec)
    print(c.name,'independent overlap',rec.get('independent_point_overlap'),'material improvement',rec.get('material_verified_gain_over_original'),flush=True)
Path('/mnt/data/CH40M3/results/scip_verified_candidates.json').write_text(json.dumps({'protocol':'CH40-M3-INDEPENDENT-SCIP-POINT-CHECK','scientific_release':'NO_GO','candidate_checks':out},indent=2)+'\n')

