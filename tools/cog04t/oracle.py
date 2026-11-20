"""Independent closed-form continuum modes and direct quadrature/whitened spectrum."""
from fractions import Fraction as Q
from math import pi
from cmath import sqrt
import numpy as np
from scipy.interpolate import BSpline
from scipy.optimize import linear_sum_assignment
from cognitum.research import kan_coupled_ritz as t

def _component_vector(C,lam):
    A=C.astype(complex)-lam*np.eye(2)
    i=int(np.argmax(np.sum(abs(A)**2,axis=1)))
    v=np.array([-A[i,1],A[i,0]])
    t.need(np.linalg.norm(v)>0,'component vector')
    v/=np.linalg.norm(v)
    t.need(np.linalg.norm(A@v)<=1e-10,'component reference residual')
    return v

def continuum(problem):
    C=np.asarray(problem.coupling,dtype=float);b=float(problem.drift)
    a,c,d,e=C.ravel()
    disc=sqrt((a-e)**2+4*c*d)
    mus=[(a+e-disc)/2,(a+e+disc)/2]
    rows=[]
    for n in (1,2):
        for mu in mus:
            rows.append(dict(mode=n,value=(n*pi)**2+b*b/4+mu,
                right=_component_vector(C,mu),left=_component_vector(C.T,mu.conjugate())))
    return rows

def direct(problem,cuts):
    edges=(0.,*map(float,cuts),1.)
    n=len(cuts)+4
    B=BSpline([0.]*3+list(edges)+[1.]*3,np.eye(n),3)
    x,w=np.polynomial.legendre.leggauss(12)
    pts=np.concatenate([(a+b)/2+(b-a)*x/2 for a,b in zip(edges,edges[1:])])
    wt=np.concatenate([(b-a)*w/2 for a,b in zip(edges,edges[1:])])
    V=B(pts)[:,1:-1];D=B(pts,nu=1)[:,1:-1]
    M=V.T@(wt[:,None]*V);K=D.T@(wt[:,None]*D);G=V.T@(wt[:,None]*D)
    mass=np.kron(np.eye(2),M)
    op=np.kron(np.eye(2),K+float(problem.drift)*G)+np.kron(np.asarray(problem.coupling,dtype=float),M)
    return mass,op,G,B,pts,wt,V

def _match(z,ref):
    # Squared distance avoids ambiguous equal L1 costs for shifted real pairs.
    i,j=linear_sum_assignment(abs(np.asarray(z)[:,None]-np.asarray(ref)[None,:])**2)
    t.need(len(i)==len(z)==len(ref) and list(i)==list(range(len(z))),'full spectral matching')
    return j

def _shape_error(U,T,wt):
    w=wt[:,None]
    denom=np.sum(w*abs(T)**2)
    coeff=np.sum(w*np.conj(T)*U)/denom
    return float(np.sqrt(np.sum(w*abs(U-coeff*T)**2)/np.sum(w*abs(U)**2)))

def verify(problem,raw,row,ref=None):
    cuts=tuple(Q(x) for x in row['cuts'])
    t.need(t.replay(problem,cuts,raw),'exact replay')
    m,a,g,B,x,w,V=direct(problem,cuts);em,ea=t.numeric(raw)
    t.need(np.allclose(m,em,atol=1e-10,rtol=1e-10) and np.allclose(a,ea,atol=1e-10,rtol=1e-10),'independent weak form')
    import json
    receipt=json.loads(raw)
    eg=np.asarray([[float(Q(v)) for v in z] for z in receipt['drift_form']])
    t.need(np.allclose(g,eg,atol=1e-10,rtol=1e-10),'independent drift form')
    L=np.linalg.cholesky(m);H=np.linalg.solve(L,a);H=np.linalg.solve(L,H.T).T
    spec=sorted(np.linalg.eigvals(H),key=lambda z:(z.real,z.imag))[:4]
    z=t.unpack(row['values']);idx=_match(z,spec);discrete=np.asarray(spec)[idx]
    t.need(np.allclose(z,discrete,atol=1e-8,rtol=1e-9),'independent complex spectrum')
    R=t.unpack(row['right_columns']);F=t.unpack(row['left_columns'])
    t.need(R.shape==F.shape==(len(m),4) and np.isfinite(R).all() and np.isfinite(F).all(),'eigenfunction shape')
    def err(A,v,lam):
        return float(np.linalg.norm(A@v-lam*(m@v),ord=np.inf)/
            max((np.linalg.norm(A,ord=np.inf)+abs(lam)*np.linalg.norm(m,ord=np.inf))*np.linalg.norm(v,ord=np.inf),1e-300))
    rr=[err(a,R[:,i],v) for i,v in enumerate(z)]
    lr=[err(a.T,F[:,i],v.conjugate()) for i,v in enumerate(z)]
    overlap=F.conj().T@m@R
    off=float(np.max(abs(overlap-np.diag(np.diag(overlap)))))
    t.need(max(rr+lr)<=1e-9 and off<=1e-8 and min(abs(np.diag(overlap)))>=1e-4,'independent left/right verification')
    t.need(np.allclose(np.diag(R.conj().T@m@R),1,atol=1e-8) and np.allclose(np.diag(F.conj().T@m@F),1,atol=1e-8),'mass normalization')
    t.need(np.max(abs(B([0.,1.])[:,1:-1]))==0,'exact essential boundary trace')
    ref=continuum(problem) if ref is None else ref
    idx=_match(z,[r['value'] for r in ref]);values=np.asarray([ref[i]['value'] for i in idx])
    scaled=abs(z-values)/np.maximum(1.,abs(values));right_errors=[];left_errors=[]
    for j,i in enumerate(idx):
        q=ref[i];n=q['mode'];b=float(problem.drift)
        for sign,mat,key,errors in [(1,R,'right',right_errors),(-1,F,'left',left_errors)]:
            U=V@mat[:,j].reshape(2,-1).T
            T=np.exp(sign*b*x[:,None]/2)*np.sin(n*pi*x[:,None])*q[key][None,:]
            errors.append(_shape_error(U,T,w))
    return dict(continuum_values=t.pack(values),continuum_spatial_modes=[ref[i]['mode'] for i in idx],
        independent_values=t.pack(discrete),scaled_errors=scaled.tolist(),right_function_errors=right_errors,left_function_errors=left_errors,
        max_independent_eigenvalue_difference=float(np.max(abs(z-discrete))),max_mass_difference=float(np.max(abs(m-em))),
        max_operator_difference=float(np.max(abs(a-ea))),max_drift_difference=float(np.max(abs(g-eg))),
        independent_right_residuals=rr,independent_left_residuals=lr,independent_off_diagonal=off,
        quadrature_points=len(x))
