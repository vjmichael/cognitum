"""15 original frozen-case standard library adoption harness. No synthetic replacements."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,platform,sys,time
from pathlib import Path
from scipy.optimize import minimize

# Research-approved CH40-M.1 baseline, exact 15-case frozen benchmark bytes.
PINNED_M1_SHA256 = '5778ec7f61dd5ccbb4a24fc9e4b6f3a467fc55dad6d56891cafdc8b37d583b16'
from frozen40m2 import load_cases,float_objective,point_lower,validated_candidate
from ibex_model import write_model, probe_ibex
from flint_arb_backend import compare_point,BackendUnavailable
from ipopt_backend import run_ipopt
from scip_backend import run_scip


def packages():
    names=['flint','cyipopt','pyscipopt','scipy','numpy','statsmodels','sympy']
    return {n:bool(importlib.util.find_spec(n)) for n in names}


def try_scipy(case, refdir, maxiter=65):
    from scipy import __version__ as scipy_version
    import numpy as np
    start=time.process_time()
    origfloat=float_objective(case,case.incumbent)
    bestfloat=origfloat
    bestpoint=case.incumbent.copy()
    attempts=[]
    for method in ('L-BFGS-B','Powell'):
        for startpoint in (case.incumbent,(case.bounds[:,0]+case.bounds[:,1])/2):
            t=time.process_time()
            f=lambda b:-float_objective(case,b) if float_objective(case,b)!=float('-inf') else 1e100
            try:
                opt=minimize(f,startpoint,method=method,bounds=[tuple(z) for z in case.bounds],options={'maxiter':maxiter})
                ok=validated_candidate(case,opt.x)
                rec={'method':method,'success':bool(opt.success),'feasible':ok,'cpu_seconds':round(time.process_time()-t,5)}
                if ok:
                    value=float_objective(case,opt.x)
                    rec['float_objective']=value
                    if value>bestfloat+1e-8:bestpoint=opt.x.copy();bestfloat=value
                attempts.append(rec)
            except (ValueError,OverflowError,FloatingPointError,ArithmeticError) as e:attempts.append({'method':method,'error':str(e)[:100]})
    # Only the best float candidate is sent to expensive rigorous checking.
    # Prior independently checked CH40-M.1 comparator serves as the unchanged baseline.
    orig=point_lower(case,case.incumbent,refdir)
    if bestfloat>origfloat+1e-8:
        new=point_lower(case,bestpoint,refdir)
        if new.lo<=orig.lo:bestpoint=case.incumbent.copy();new=orig
    else:new=orig
    gain=new.lo-orig.lo
    return {'backend':'SciPy','version':scipy_version,'status':'INDEPENDENT_POINT_LOWER_IMPROVED' if gain>0 else 'NO_VERIFIED_GAIN',
            'verified_gain':str(gain),'candidate':[str(float(v)) for v in bestpoint],
            'verified_point_lower':str(new.lo), 'original_point_lower':str(orig.lo),
            'cpu_seconds_including_point_checks':round(time.process_time()-start,5),'attempts':attempts,
            'global_certificate':False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--traces',type=Path,required=True);p.add_argument('--pins',type=Path,required=True)
    p.add_argument('--reference-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ibex-out',type=Path,required=True);p.add_argument('--maxiter',type=int,default=65)
    p.add_argument('--previous-scipy',type=Path,help='Previously accepted CH40-M.1 frozen benchmark; reuse as comparator rather than rerun')
    p.add_argument('--execute-native',action='store_true',help='Run installed Ipopt/SCIP/IBEX; default probe-only')
    args=p.parse_args()
    if not 1<=args.maxiter<=1000:raise ValueError('maxiter must be 1..1000')
    cases=load_cases(args.traces,args.pins)
    inherited={}
    if args.previous_scipy:
        base_bytes=args.previous_scipy.read_bytes()
        if hashlib.sha256(base_bytes).hexdigest()!=PINNED_M1_SHA256:raise ValueError('Historical SciPy comparison bytes changed')
        base=json.loads(base_bytes)
        if base['protocol']!='CH40M-SCIPY-INCUMBENT-PILOT-V1' or len(base['cases'])!=15 or not base['certification_enabled']:
            raise ValueError('Unaccepted SciPy benchmark reference')
        inherited={c['case']:c for c in base['cases']}
        if len(inherited)!=15 or set(inherited)!={c.name for c in cases}:raise ValueError('Changed or missing previous cases')
        if any(inherited[c.name]['trace_sha256']!=c.source_sha256 for c in cases):raise ValueError('Previous case SHA mismatch')
    result={'protocol':'CH40M2-STANDARD-SOLVER-COMPARISON-V1','scientific_release':'NO_GO',
      'claim':'ONLY_INDEPENDENTLY_CHECKED_FEASIBLE_POINT_LOWER_IF_EXECUTED',
      'previous_scipy_source_sha256':hashlib.sha256(base_bytes).hexdigest() if inherited else None,
      'case_count':len(cases),'python':platform.python_version(),'platform':platform.platform(),
      'available':packages(),'native_execution_enabled':args.execute_native,'cases':[],
      'warnings':['Native runtime presence is not scientific acceptance','CH40-J signatures and CH23 trees unchanged',
                  'IBEX file generation does NOT imply parser acceptance or objective certification']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for idx,case in enumerate(cases):
        record={'case':case.name,'trace_sha256':case.source_sha256}
        record['ibex_model']=write_model(case,args.ibex_out)
        record['scipy']=({'backend':'SciPy/CH40-M.1','status':inherited[case.name]['status'],
            'verified_gain':inherited[case.name]['verified_gain'],
            'candidate':inherited[case.name]['candidate'],
            'cpu_seconds_search_only':inherited[case.name]['cpu_seconds'],
            'reused_previous_accepted_comparator':True, 'global_certificate':False}
            if inherited else try_scipy(case,args.reference_dir,args.maxiter))
        from numpy import array
        candidate=array([float(v) for v in record['scipy']['candidate']]);
        try:record['flint_arb']=compare_point(case,candidate,args.reference_dir)
        except BackendUnavailable:record['flint_arb']={'status':'NOT_RUN_DEPENDENCY_MISSING'}
        except Exception as e:record['flint_arb']={'status':'NOT_ACCEPTED','reason':repr(e)[:180]}
        if args.execute_native:
            record['ibex']=probe_ibex(case,args.ibex_out/(case.name+'.bch'),timeout=5)
            record['ipopt']=run_ipopt(case)
            record['scip']=run_scip(case)
            # If an alternate library finds a new float candidate, independent validation is mandatory.
            for name in ('ipopt','scip'):
                rr=record[name]
                if rr.get('status')=='CANDIDATE':
                    try:
                        a=point_lower(case,rr['candidate'],args.reference_dir)
                        rr['independent_point_lower']=str(a.lo)
                        rr['point_verified']=True
                    except Exception as e:rr['status']='REFUSED_FAILED_INDEPENDENT_VERIFICATION';rr['reason']=repr(e)[:100]
        else:
            record['ibex']={'status':'NOT_RUN_DEFAULT_OFF'}
            record['ipopt']={'status':'NOT_RUN_DEFAULT_OFF'}
            record['scip']={'status':'NOT_RUN_DEFAULT_OFF'}
        result['cases'].append(record)
        args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(f'{idx+1}/15 {case.name}: SciPy status={record["scipy"]["status"]} | FLINT={record["flint_arb"].get("status","POINT_CHECKED")}',flush=True)
    result['complete']=len(result['cases'])==15
    result['scipy_improved_count']=sum(x['scipy']['status']=='INDEPENDENT_POINT_LOWER_IMPROVED' for x in result['cases'])
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()

