"""Analytic CPU pilot for multivariate VFA, no hardware or superiority claim."""
import itertools
import json
from pathlib import Path
import numpy as np
from scipy.spatial.distance import cdist
from cognitum.research.vfa_multivariate import Mixture, TensorInterpolator, TensorFPE, Composition


def run():
    interpolation=[];features=[];composition=[]
    for d in (2,3,4):
        ell=np.linspace(.7,1.1,d);centers=np.stack([np.full(d,-.3),np.full(d,.4)]);weights=np.array([.8,-.25])
        f=Mixture.sections(centers,weights,ell)
        rng=np.random.default_rng(481+d);q=rng.uniform(-1.5,1.5,(257,d))
        exact=np.exp(-cdist(q/ell,centers/ell,'sqeuclidean')/2)@weights
        for n in (2,3,4):
            axes=tuple(np.linspace(-1,1,n) for _ in range(d));sites=np.array(list(itertools.product(*axes)))
            y=np.exp(-cdist(sites/ell,centers/ell,'sqeuclidean')/2)@weights
            model=TensorInterpolator.fit(axes,y.reshape((n,)*d),ell)
            gram=np.exp(-cdist(sites/ell,sites/ell,'sqeuclidean')/2)
            cross=np.exp(-cdist(q/ell,sites/ell,'sqeuclidean')/2)
            direct=np.linalg.solve(gram,y);pred=cross@direct
            delta=float(np.max(abs(pred-model.function.evaluate(q))))
            ref_power=np.sqrt(np.maximum(0,1-np.einsum('ij,ji->i',cross,np.linalg.solve(gram,cross.T))))
            p_delta=float(np.max(abs(ref_power-model.power(q))))
            err=np.abs(model.function.evaluate(q)-exact);bound=model.error_bound(q,f.norm())
            if delta>1e-8 or p_delta>1e-7 or np.any(err>bound+1e-8):raise AssertionError('tensor oracle mismatch')
            interpolation.append(dict(dim=d,sites_per_axis=n,sites=len(sites),max_error=float(err.max()),dense_prediction_delta=delta,dense_power_delta=p_delta,condition=model.condition,retained_factor_bytes=sum(a.nbytes for a in model.factors),dense_gram_bytes=gram.nbytes,within_bound=True))
        for D in (256,1024,4096):
            for seed in range(8):
                b=TensorFPE.random(D,ell,seed);c=b.encode_sections(f)
                err=np.abs(b.evaluate(c,q)-exact);bound=sum(abs(weights))*b.finite_pair_bound(len(q)*len(weights),.01)
                if err.max()>bound+1e-12:raise AssertionError('fixed pair bound')
                features.append(dict(dim=d,D=D,seed=seed,rmse=float(np.sqrt(np.mean(err**2))),max_error=float(err.max()),bound=float(bound),retained_bytes=b.omega.nbytes+c.nbytes))
        g=Mixture.sections([np.zeros(d)],[.8],ell)
        for degree in (1,3,5,7):
            p,bound=g.sin_polynomial(degree);err=np.max(abs(p.evaluate(q)-np.sin(g.evaluate(q))))
            if err>bound+1e-12:raise AssertionError('Taylor bound violation')
            composition.append(dict(dim=d,degree=degree,max_error=float(err),bound=bound,terms=len(p.weights)))
    return dict(interpolation=interpolation,features=features,composition=composition,production_enabled=False)


if __name__=='__main__':
    import sys
    Path(sys.argv[1]).write_text(json.dumps(run(),indent=2)+'\n',encoding='utf8')
