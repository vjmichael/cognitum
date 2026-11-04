"""CH40-M.3 research-only SCIP compact *candidate* formulation.
Does not establish a rigorous global bound. No host permission or execution authority.
"""
from __future__ import annotations
import json,sys,time,math,resource,argparse
from pathlib import Path
sys.path.insert(0,'/mnt/data/CH40M2/source')
from frozen40m2 import Case,validated_candidate,float_objective
import numpy as np

def probe(case, seconds=5.0, mem_mb=512, prefix_rows=None):
    from pyscipopt import Model,exp,log
    model=Model('C14_compact_firth_'+case.name);model.hideOutput()
    model.setRealParam('limits/time',seconds)
    model.setRealParam('limits/memory',float(mem_mb))
    rows=case.certificate['model']['rows'][:prefix_rows]
    beta=[model.addVar(name=f'b{i}',lb=float(case.bounds[i,0]),ub=float(case.bounds[i,1])) for i in range(3)]
    terms=[];weighted=[]
    for row_no,r in enumerate(rows):
        x=[float(v) for v in r['x']];n=float(r['n']);s=float(r['s'])
        zlower=sum(x[i]*(float(case.bounds[i,0]) if x[i]>=0 else float(case.bounds[i,1])) for i in range(3))
        zupper=sum(x[i]*(float(case.bounds[i,1]) if x[i]>=0 else float(case.bounds[i,0])) for i in range(3))
        z=model.addVar(name=f'z{row_no}',lb=zlower-1e-7,ub=zupper+1e-7)
        model.addCons(z==sum(x[i]*beta[i] for i in range(3)))
        p=model.addVar(name=f'p{row_no}',lb=1e-16,ub=1-1e-15)
        model.addCons(p*(1+exp(-z))==1)
        w=model.addVar(name=f'w{row_no}',lb=0,ub=n/4+1e-8)
        model.addCons(w==n*p*(1-p))
        l=model.addVar(name=f'l{row_no}',lb=0,ub=max(zupper+2,2)+2)
        model.addCons(l==log(1+exp(z)))
        terms.append((s,z,-n,l));weighted.append((x,w))
    imat=[[None]*3 for _ in range(3)]
    for i in range(3):
      for j in range(i,3):
        lim=sum(abs(x[i]*x[j])*float(r['n'])/4 for (x,w),r in zip(weighted,rows))+1
        v=model.addVar(name=f'I{i}{j}',lb=0 if i==j else -lim,ub=lim)
        model.addCons(v==sum(x[i]*x[j]*w for x,w in weighted))
        imat[i][j]=imat[j][i]=v
    a,b,c=imat[0][0],imat[0][1],imat[0][2]
    d,e,f=imat[1][1],imat[1][2],imat[2][2]
    determinant=a*d*f+2*b*c*e-a*e*e-d*c*c-f*b*b
    det=model.addVar(name='fisher_det',lb=1e-25,ub=1e10)
    model.addCons(det==determinant)
    ld=model.addVar(name='fisher_logdet',lb=-70,ub=25)
    model.addCons(ld==log(det))
    objective=sum(s*z+neg_n*l for s,z,neg_n,l in terms)+0.5*ld
    model.setObjective(objective,'maximize')
    stats={'variables':model.getNVars(),'constraints':model.getNConss(),'rows':len(rows)}
    # record model-build time separate from solve
    t=time.process_time()
    model.optimize()
    status=str(model.getStatus());sol=model.getBestSol()
    result={'status':status,'cpu_opt_seconds':round(time.process_time()-t,4),'model':stats,
      'global_certificate':False,'solver_bound_unverified':float(model.getDualbound()) if sol else None}
    if sol:
      point=[float(model.getSolVal(sol,v)) for v in beta]
      result['candidate']=point;result['feasible_frozen_domain']=bool(validated_candidate(case,point))
      result['objective_at_candidate']=float_objective(case,point) if result['feasible_frozen_domain'] else None
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',default='one_event_n80_i00');p.add_argument('--rows',type=int);p.add_argument('--seconds',type=float,default=4);p.add_argument('--memory-mb',type=int,default=512);p.add_argument('--output',required=True);args=p.parse_args()
    limit=int(1.4*1024**3);resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    # Single original case, pinned to the accepted 15-case CH40-K SHA manifest.
    import hashlib
    pins=json.loads(Path('/mnt/data/CH40K/CH40K_ACCEPTANCE.json').read_text())['cases']
    known={v['case']:v['trace_sha256'] for v in pins}
    if len(known)!=15 or args.case not in known:raise ValueError('case not in frozen original acceptance')
    path=Path('/mnt/data/CH40K/traces')/(args.case+'_127_original_mpfr_trace.json')
    bdata=path.read_bytes();digest=hashlib.sha256(bdata).hexdigest()
    if digest!=known[args.case]:raise ValueError('frozen case hash mismatch')
    cert=json.loads(bdata)['certificate']
    rows=cert['model']['rows']
    x=np.array([[float(v) for v in row['x']] for row in rows],float)
    n=np.array([float(row['n']) for row in rows],float)
    ss=np.array([float(row['s']) for row in rows],float)
    bounds=np.array([[float(v) for v in pair] for pair in cert['root_box']],float)
    inc=np.array([float(v) for v in cert['incumbent']],float)
    if cert['model']['d']!=3 or len(rows) not in (80,160) or x.shape!=(len(rows),3):raise ValueError('unexpected frozen model shape')
    if not np.isfinite(x).all() or not np.isfinite(bounds).all() or not np.isfinite(inc).all():raise ValueError('nonfinite original model')
    if (inc<bounds[:,0]).any() or (inc>bounds[:,1]).any():raise ValueError('incumbent out of root box')
    case=Case(args.case,digest,cert,x,n,ss,bounds,inc)
    start=time.monotonic()
    try:r=probe(case,args.seconds,args.memory_mb,args.rows);r['adapter_status']='EXECUTED_NATIVE_CANDIDATE_ONLY'
    except BaseException as exc:r={'adapter_status':'FAILED_NATIVE_MODEL','error':repr(exc),'global_certificate':False}
    r['wall_total_seconds']=round(time.monotonic()-start,3);r['frozen_source_hash']=case.source_sha256
    Path(args.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2),flush=True)

