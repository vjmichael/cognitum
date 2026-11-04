"""Optional PySCIPOpt exact symbolic *shape* of Firth objective, float coefficients.
SCIP nonlinear objective modeled by epigraph auxiliary; solver status is NOT a rigorous interval proof.
"""
from __future__ import annotations
from time import process_time
from frozen40m2 import validated_candidate, float_objective


def run_scip(case,*,seconds=15.0,memory_mb=1024):
    try:from pyscipopt import Model, exp, log
    except ImportError:return {'backend':'PySCIPOpt/SCIP','status':'NOT_RUN_DEPENDENCY_MISSING'}
    start=process_time()
    try:
        model=Model('CH40M_Firth_'+case.name)
        model.hideOutput()
        model.setRealParam('limits/time',float(seconds))
        model.setRealParam('limits/memory',float(memory_mb))
        b=[model.addVar(lb=float(case.bounds[i,0]),ub=float(case.bounds[i,1]),vtype='C',name=f'b{i}') for i in range(3)]
        ll=0;I=[[0 for _ in range(3)] for _ in range(3)]
        for r in case.certificate['model']['rows']:
            x=[float(v) for v in r['x']]; n=int(r['n']);s=int(r['s'])
            z=sum((x[j]*b[j] for j in range(3)))
            e=exp(-z);w=n*e/(1+e)**2
            ll=ll+s*z-n*log(1+exp(z))
            for j in range(3):
                for k in range(j,3):I[j][k]=I[j][k]+w*x[j]*x[k]
        a,c,d=I[0][0],I[0][1],I[0][2]
        e,f,g=I[1][1],I[1][2],I[2][2]
        det=a*e*g+2*c*d*f-a*f*f-e*d*d-g*c*c
        t=model.addVar(vtype='C',name='negfirth_lower',lb=-1e6,ub=1e6)
        model.addCons(t<=ll+0.5*log(det),name='firth_hypograph')
        model.setObjective(t,'maximize');model.optimize()
        status=str(model.getStatus())
        sol=model.getBestSol()
        if sol is None:return {'backend':'PySCIPOpt/SCIP','status':'NO_FEASIBLE_SOLUTION','solver_status':status,'cpu_seconds':round(process_time()-start,6)}
        candidate=[float(model.getSolVal(sol,v)) for v in b]
        good=validated_candidate(case,candidate)
        return {'backend':'PySCIPOpt/SCIP','status':'CANDIDATE' if good else 'REFUSED_INVALID_CANDIDATE',
             'solver_status':status,'candidate':candidate,'objective_float':float_objective(case,candidate) if good else None,
             'solver_primal_float':float(model.getSolVal(sol,t)),
             'solver_dual_bound_unverified':float(model.getDualbound()),
             'global_certificate':False,'cpu_seconds':round(process_time()-start,6)}
    except Exception as exc:return {'backend':'PySCIPOpt/SCIP','status':'NOT_ACCEPTED_RUNTIME_ERROR','reason':repr(exc)[:200]}

