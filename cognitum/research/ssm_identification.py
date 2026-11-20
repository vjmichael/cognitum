"""Bounded numerical model discovery; no execution or physical validation authority."""
import itertools
import numpy as np
from scipy.special import logsumexp
from scipy.linalg import null_space
from .ssm_stochastic import need, array, receipt


def design(x):
    x=array(x,2,262144);need(len(x)<=8192 and x.shape[1]<=64,'design budget');return x


def fit(X,Y):
    X,Y=design(X),design(Y);need(len(X)==len(Y) and len(X)>=X.shape[1],'regression shape')
    v=np.linalg.svd(X,compute_uv=False);need(v[-1]>1e-10*v[0] and v[0]>0,'rank/conditioning: no unique fit')
    B=np.linalg.lstsq(X,Y,rcond=None)[0];return B,float(v[0]/v[-1])


def normal_estimate(samples,prior):
    """Normal iid MLE and conjugate normal-inverse-gamma posterior (shape/scale)."""
    x=array(samples,1);need(2<=len(x)<=8192,'sample budget');p=array(prior,1);need(p.shape==(4,) and np.all(p[1:]>0),'NIG prior');m,k,a,b=p;n=len(x);u=x.mean();s=float(np.sum((x-u)**2));need(s>0,'no positive-variance MLE');kn=k+n;an=a+n/2;bn=b+s/2+k*n*(u-m)**2/(2*kn);mn=(k*m+n*u)/kn;v=s/n
    return receipt(mean=float(u),variance=v,log_likelihood=float(-n/2*(np.log(2*np.pi*v)+1)),posterior=(float(mn),float(kn),float(an),float(bn)),posterior_mean_variance=float(bn/(kn*(an-1))) if an>1 else None)


def mixture_em(samples,means,variances,weights,iterations=100):
    """Scalar Gaussian mixture EM with variance floor; local optimum only."""
    x=array(samples,1);m=array(means,1);k=len(m);v=array(variances,1);w=array(weights,1);need(2<=k<=4 and 2*k<=len(x)<=8192 and v.shape==w.shape==m.shape and np.all(v>=1e-8) and np.all(w>0) and abs(w.sum()-1)<1e-12 and type(iterations) is int and 1<=iterations<=256,'mixture input');w=w/w.sum()
    def est(m,v,w):
        L=np.log(w)-.5*(np.log(2*np.pi*v)+(x[:,None]-m)**2/v);z=logsumexp(L,axis=1);return np.exp(L-z[:,None]),float(z.sum())
    r,ll=est(m,v,w);history=[ll]
    for _ in range(iterations):
        n=r.sum(0);need(np.min(n)>1e-8,'component collapse');w=n/len(x);m=r.T@x/n;v=np.maximum(np.sum(r*(x[:,None]-m)**2,axis=0)/n,1e-8);r,ll=est(m,v,w);need(ll>=history[-1]-1e-8*max(1,abs(ll)),'EM descent');history.append(ll)
        if history[-1]-history[-2]<=1e-10*max(1,abs(ll)):break
    i=np.argsort(m);return receipt(means=m[i],variances=v[i],weights=w[i],log_likelihood=np.array(history),global_optimum=False)


def identify_lti(X,U,Y,Xtest,Utest,Ytest):
    """Discrete fully observed x_next=A x+B u; independent holdout supplied."""
    X,U,Y,Xtest,Utest,Ytest=map(design,(X,U,Y,Xtest,Utest,Ytest));n=X.shape[1];k=U.shape[1];need(n<=16 and k<=16 and len(X)==len(U)==len(Y) and Y.shape==X.shape and Xtest.shape==Ytest.shape and Xtest.shape[1]==n and Utest.shape==(len(Xtest),k),'LTI shape');D=np.column_stack((X,U));B,c=fit(D,Y);pred=np.column_stack((Xtest,Utest))@B
    return receipt(A=B[:n].T,B=B[n:].T,condition=c,training_rmse=float(np.sqrt(np.mean((D@B-Y)**2))),heldout_rmse=float(np.sqrt(np.mean((pred-Ytest)**2))))


def era(markov,order,blocks):
    """SISO/MIMO eigensystem realization from H0=D,H1=CB,... ."""
    G=array(markov,3);T,p,m=G.shape;need(p<=8 and m<=8 and type(blocks) is int and 2<=blocks<=16 and T>=2*blocks+1 and type(order) is int and 1<=order<min(blocks*p,blocks*m),'ERA budget')
    H0=np.block([[G[i+j+1] for j in range(blocks)] for i in range(blocks)]);H1=np.block([[G[i+j+2] for j in range(blocks)] for i in range(blocks)]);U,s,V=np.linalg.svd(H0,full_matrices=False);need(s[order-1]>s[0]*1e-10 and s[order-1]-s[order]>s[0]*1e-10,'order rank/gap');r=np.sqrt(s[:order]);O=U[:,:order]*r;R=r[:,None]*V[:order];A=(U[:,:order].T@H1@V[:order].T)/r[:,None]/r;B=R[:,:m];C=O[:p];pred=[G[0]];Z=B.copy()
    for _ in range(1,T):
        pred.append(C@Z);Z=A@Z;need(np.isfinite(Z).all() and np.max(abs(Z))<=1e8,'realization trajectory budget')
    return receipt(A=A,B=B,C=C,D=G[0],singular_values=s,impulse_rmse=float(np.sqrt(np.mean((np.array(pred)-G)**2))),similarity_ambiguous=True)


def library(X,degree):
    X=design(X);n=X.shape[1];need(n<=6 and type(degree) is int and 1<=degree<=3,'polynomial budget');ex=[(0,)*n]
    for d in range(1,degree+1):
        for i in itertools.combinations_with_replacement(range(n),d):ex.append(tuple(i.count(j) for j in range(n)))
    need(len(ex)<=64,'library budget');D=np.column_stack([np.prod(X**p,axis=1) for p in ex]);need(np.isfinite(D).all() and np.max(abs(D))<=1e8,'feature magnitude');return D,tuple(ex)


def sindy(X,dX,Xtest,dXtest,degree,threshold,iterations=12):
    """Sequential thresholded least squares on supplied derivative data."""
    D,ex=library(X,degree);E,ex2=library(Xtest,degree);Y=design(dX);Z=design(dXtest);need(ex==ex2 and Y.shape==(len(D),len(ex[0])) and Z.shape==(len(E),Y.shape[1]) and type(threshold) in (int,float) and 0<threshold<=1e4 and type(iterations) is int and 1<=iterations<=32,'SINDy shape/budget');B,c=fit(D,Y)
    for _ in range(iterations):
        prior=B.copy()
        for j in range(B.shape[1]):
            mask=abs(B[:,j])>=threshold;B[:,j]=0
            if any(mask):B[mask,j]=fit(D[:,mask],Y[:,j:j+1])[0][:,0]
        if np.array_equal(abs(B)>0,abs(prior)>0):break
    return receipt(exponents=ex,coefficients=B,condition=c,training_rmse=float(np.sqrt(np.mean((D@B-Y)**2))),heldout_rmse=float(np.sqrt(np.mean((E@B-Z)**2))),symbolic_uniqueness=False)


def dmd(X,Y,Xtest,Ytest,degree=None):
    """Full column-rank snapshot regression, optionally polynomial EDMD."""
    X,Y,Xtest,Ytest=map(design,(X,Y,Xtest,Ytest));need(X.shape==Y.shape and Xtest.shape==Ytest.shape and X.shape[1]==Xtest.shape[1],'snapshot shape')
    if degree is not None:X,Y,Xtest,Ytest=(library(t,degree)[0] for t in (X,Y,Xtest,Ytest))
    B,c=fit(X,Y);K=B.T;e=np.linalg.eigvals(K);return receipt(operator=K,eigenvalues=e,condition=c,training_rmse=float(np.sqrt(np.mean((X@B-Y)**2))),heldout_rmse=float(np.sqrt(np.mean((Xtest@B-Ytest)**2))),invariance_certified=False)


def operator_inference(X,dX,Xtest,dXtest,degree=2,conservative=False):
    """Polynomial continuous operator fit; optional x dot f(x)=0 constraint.
    Enforce coefficient cancellation by null-space regression, not sample penalties.
    """
    D,ex=library(X,degree);E,ex2=library(Xtest,degree);Y,Z=map(design,(dX,dXtest));n=len(ex[0]);p=len(ex);need(ex2==ex and Y.shape==(len(D),n) and Z.shape==(len(E),n) and type(conservative) is bool and p*n<=128,'operator shape/budget')
    B,c=fit(D,Y);residual=None
    if conservative:
        keys=sorted({tuple(v+(i==j) for i,v in enumerate(q)) for q in ex for j in range(n)});M=np.zeros((len(keys),p*n));idx={q:i for i,q in enumerate(keys)}
        for a,q in enumerate(ex):
            for j in range(n):M[idx[tuple(v+(i==j) for i,v in enumerate(q))],a*n+j]=1
        N=null_space(M);need(len(D)*n*p*n<=4000000,'constrained design budget');need(N.shape[1]>0,'no nonzero conservative model');C=np.kron(D,np.eye(n))@N;v=np.linalg.svd(C,compute_uv=False);need(len(C)>=C.shape[1] and v[-1]>1e-10*v[0] and v[0]>0,'constrained rank');B=(N@np.linalg.lstsq(C,Y.ravel(),rcond=None)[0]).reshape(p,n);residual=float(np.max(abs(M@B.ravel())));need(residual<=1e-9*max(1,np.max(abs(B))),'conservation residual')
    return receipt(exponents=ex,coefficients=B,condition=c,coefficient_conservation_residual=residual,training_rmse=float(np.sqrt(np.mean((D@B-Y)**2))),heldout_rmse=float(np.sqrt(np.mean((E@B-Z)**2))))
