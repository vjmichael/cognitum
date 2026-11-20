"""Independent field quadrature and Cholesky-whitened dense spectral reference."""
from fractions import Fraction as Q
from itertools import combinations_with_replacement
import json
import numpy as np
from tools.cog04o.oracle import reference
from cognitum.research import kan_weak_form as p

def verify(checkpoints,raw,spectrum):
    p.need(p.replay(checkpoints,raw),'exact replay')
    r=json.loads(raw);n=len(checkpoints)
    m=np.zeros((n,n));s=np.zeros((n,n));points=0
    for i,j in combinations_with_replacement(range(n),2):
        rows,pts=reference(checkpoints[i],checkpoints[j]);points+=pts
        m[i,j]=m[j,i]=rows[0]['inner']
        s[i,j]=s[j,i]=sum(rows[k+1]['inner'] for k,a in enumerate(r['axes']) if a in r['stiffness_axes'])
    diffs=[]
    for key,observed in [('mass',m),('stiffness',s)]:
        exact=np.array([[float(Q(v)) for v in row] for row in r[key]])
        p.need(np.allclose(exact,observed,atol=1e-10,rtol=1e-10),'independent weak matrix disagreement')
        diffs.append(float(np.max(np.abs(exact-observed))))
    # Independent numerical matrices from direct field evaluation, not exact Gram input.
    l=np.linalg.cholesky(m)
    a=np.linalg.solve(l,s)
    h=np.linalg.solve(l,a.T).T
    p.need(np.allclose(h,h.T,rtol=1e-9,atol=1e-9),'whitened symmetry')
    values=np.linalg.eigvalsh((h+h.T)/2)
    primary=np.array(spectrum['values'])
    p.need(np.allclose(primary,values,rtol=1e-7,atol=1e-8),'independent spectral disagreement')
    return dict(quadrature_points=points,max_mass_difference=diffs[0],max_stiffness_difference=diffs[1],
        independent_values=values.tolist(),max_eigenvalue_difference=float(np.max(np.abs(primary-values))),
        method='direct SciPy B-spline Gauss quadrature; NumPy Cholesky and symmetric eigvalsh')
