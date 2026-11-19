"""Independent analytic target, fixed sites/queries, explicit refusal records."""
import json
from pathlib import Path
import numpy as np
from cognitum.research.vfa_rkhs import Gaussian, Interpolator, FPE


def run():
    x=np.linspace(-3,3,257)
    f=Gaussian.sections([-.7,.4],[1.2,-.3],.8)
    truth=1.2*np.exp(-.5*((x+.7)/.8)**2)-.3*np.exp(-.5*((x-.4)/.8)**2)
    rows=[]
    for n in (3,5,8,12,16,24):
        sites=np.linspace(-2,2,n)
        try:
            model=Interpolator.fit(sites,f.evaluate(sites),.8)
        except ValueError as exc:
            rows.append(dict(n=n,refused=str(exc)));continue
        bound=model.error_bound(x,f.norm());err=np.abs(model.function.evaluate(x)-truth)
        if np.any(err>bound+1e-8):raise AssertionError('power bound violation')
        rows.append(dict(n=n,condition=model.condition,inside_max=float(err[abs(x)<=2].max()),outside_max=float(err[abs(x)>2].max()),max_bound=float(bound.max())))
    random=[]
    for d in (256,1024,4096,16384):
        for seed in range(8):
            b=FPE.random(d,.8,seed);c=b.encode_sections(f)
            estimate=b.evaluate(c,x);err=np.abs(estimate-truth)
            bound=float(np.sum(abs(f.weights))*b.finite_pair_bound(len(x)*2,.01))
            random.append(dict(d=d,seed=seed,rmse=float(np.sqrt(np.mean(err**2))),max_error=float(err.max()),bound=bound,within_bound=bool(err.max()<=bound),retained_bytes=b.omega.nbytes+c.nbytes))
    return dict(interpolation=rows,random_features=random,production_enabled=False)


if __name__=='__main__':
    import sys
    Path(sys.argv[1]).write_text(json.dumps(run(),indent=2)+'\n',encoding='utf8')
