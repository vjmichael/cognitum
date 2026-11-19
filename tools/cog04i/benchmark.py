"""Disjoint analytical comparisons; no analytic labels are available to fit()."""
from dataclasses import asdict
import json
from pathlib import Path
import time
import numpy as np
from cognitum.research import kan_differential_learning as s


def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    cases=[('decay',s.Problem('ivp',4,(0,),1),lambda x:np.exp(-4*x),.031),
           ('reaction_diffusion',s.Problem('bvp',4,(0,),0,1),lambda x:np.sinh(2*x)/np.sinh(2),.007),
           ('relaxation',s.Problem('ivp',1,(1,),0),lambda x:1-np.exp(-x),.0004)]
    result=[]
    for name,p,exact,tolerance in cases:
        start=time.perf_counter();r=s.fit(p,tolerance);seconds=time.perf_counter()-start
        c=s.require_accuracy(p,r.model,r.certificate,tolerance)
        n=len(r.history)-1;uniform=s._fit(p,tuple(i/(n+1) for i in range(1,n+1)));uc=s.assess(p,uniform)
        x=(np.arange(1001)+.37)/1001;y=exact(x)
        measured=float(max(abs(r.model.evaluate(x[:,None])[0][:,0]-y)))
        uniform_measured=float(max(abs(uniform.evaluate(x[:,None])[0][:,0]-y)))
        if measured>float(c.solution_error_upper)+1e-13:raise RuntimeError('analytic comparison exceeds certificate')
        raw,h=r.model.research_snapshot();(out/(name+'.model.json')).write_bytes(raw)
        (out/(name+'.certificate.json')).write_text(json.dumps(asdict(c),default=str,indent=2)+'\n',encoding='utf8')
        result.append(dict(name=name,problem=asdict(p),problem_sha256=p.identity,model_sha256=h,accepted=True,tolerance=tolerance,fit_seconds=seconds,stages=[float(a.solution_error_upper) for a in r.history],knots=np.unique(r.model.layers[0].grid[0]).tolist(),full_domain_error_upper=float(c.solution_error_upper),exact_bound=str(c.solution_error_upper),exact_squared_residual_l2=str(c.squared_l2),analytic_holdout_max_error=measured,uniform_same_coefficients_error_upper=float(uc.solution_error_upper),uniform_analytic_holdout_max_error=uniform_measured,coefficients=r.model.layers[0].coefficients.size,conditions_exact=not any(c.condition_errors),heldout_points=len(x)))
    (out/'benchmark.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
