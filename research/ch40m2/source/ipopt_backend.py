"""Optional standard Ipopt candidate solver. Never claims a global optimum.
cyipopt.minimize_ipopt is SciPy-style; independently verify any returned candidate.
"""
from __future__ import annotations
from time import process_time
from scipy.optimize import OptimizeResult
from frozen40m2 import float_objective, validated_candidate


def run_ipopt(case,*,iterations=75):
    try:from cyipopt import minimize_ipopt
    except ImportError: return {'status':'NOT_RUN_DEPENDENCY_MISSING','backend':'cyipopt/Ipopt'}
    start=process_time()
    try:
        result=minimize_ipopt(lambda b:-float_objective(case,b),case.incumbent,
             bounds=[tuple(v) for v in case.bounds],options={'max_iter':iterations,'print_level':0})
        candidate=[float(v) for v in result.x]
        return {'backend':'cyipopt/Ipopt','status':'CANDIDATE' if validated_candidate(case,candidate) else 'REFUSED_INVALID_CANDIDATE',
          'solver_status':str(result.message)[:300], 'solver_success':bool(result.success),
          'candidate':candidate,'objective_float':float_objective(case,candidate) if validated_candidate(case,candidate) else None,
          'cpu_seconds':round(process_time()-start,6),'global_certificate':False}
    except Exception as e:return {'backend':'cyipopt/Ipopt','status':'NOT_ACCEPTED_RUNTIME_ERROR','reason':repr(e)[:200]}

