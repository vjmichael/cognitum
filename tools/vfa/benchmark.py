"""Fixed seeded CPU algebra pilot, independent test coordinates and analytic functions."""
import argparse
import json
from pathlib import Path
import numpy as np
from cognitum.research.vfa_periodic import Periodic


def run():
    rows=[]
    for seed in range(8):
        rng=np.random.default_rng(seed)
        x=rng.uniform(-2*np.pi,4*np.pi,2001)
        # Denominator is separated from zero, with variable conditioning.
        for amp in (.25,.65,.9):
            a,b=rng.uniform(-.5,.5,2)
            f=Periodic([1,a/2-1j*b/2,.1j]); g=Periodic([1,amp/2])
            fv=1+a*np.cos(x)+b*np.sin(x)-.2*np.sin(2*x)
            gv=1+amp*np.cos(x)
            product=float(np.max(np.abs(f.multiply(g).evaluate(x)-fv*gv)))
            for order in (4,12,24,48):
                q=f.divide(g,order=order,grid=512,max_error=100)
                err=float(np.max(np.abs(q.function.evaluate(x)-fv/gv)))
                bound=q.error_bound_estimate
                if err>bound+1e-11 or product>1e-11:
                    raise AssertionError('independent oracle exceeded bound')
                rows.append(dict(seed=seed,amplitude=amp,order=order,grid=512,heldout=2001,product_max_abs=product,quotient_max_abs=err,residual_bound=bound,meets_1e_6=bound<=1e-6,coeff_bytes=q.function.positive.nbytes))
    return dict(scope='analytic synthetic CPU; not directed-rounding, hardware or KAN superiority',rows=rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.write_text(json.dumps(run(),indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
