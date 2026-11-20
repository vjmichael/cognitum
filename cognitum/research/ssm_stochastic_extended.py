"""Bounded numerical stochastic research; no execution authority."""
import numpy as np
from scipy.linalg import expm, cho_factor, cho_solve, solve_triangular
from scipy.special import logsumexp
from .ssm_stochastic import need, array, square, cov, clean, receipt, kernel, probability, gaussian_update


def vec(x,n):
    a=array(x,1);need(a.shape==(n,), 'vector shape');return a


def seed_rng(seed):
    need(type(seed) is int and 0<=seed<2**32,'seed');return np.random.default_rng(seed)


def bounded(x):
    need(np.isfinite(x).all() and np.max(np.abs(x))<=1e8,'state budget');return x


def model(A,b,c):
    A=square(A);n=len(A);return A,vec(b,n),vec(c,n)


def nonlinear_sde(A,b,c,sigma,beta,x0,dt,steps,paths,seed):
    """Ito drift Ax+b*tanh(x)+c, diagonal diffusion sigma+beta*tanh(x).
    Nested Euler grids share Brownian increments; no certified error estimate.
    """
    A,b,c=model(A,b,c);n=len(A);s=vec(sigma,n);g=vec(beta,n);x=vec(x0,n)
    need(np.all(s>=abs(g)),'nonnegative diffusion amplitude')
    need(type(dt) in (int,float) and 0<dt<=.25 and type(steps) is int and 1<=steps<=512 and dt*steps<=16 and type(paths) is int and 1<=paths<=4096 and n*paths*steps<=524288,'SDE budget')
    rng=seed_rng(seed);X=np.tile(x,(paths,1));Y=X.copy();Z=X.copy()
    def step(x,h,dw):return bounded(x+h*(x@A.T+b*np.tanh(x)+c)+(s+g*np.tanh(x))*dw)
    for _ in range(steps):
        d=rng.standard_normal((4,paths,n))*np.sqrt(dt/4)
        X=step(X,dt,d.sum(0))
        for j in (0,2):Y=step(Y,dt/2,d[j]+d[j+1])
        for dw in d:Z=step(Z,dt/4,dw)
    return receipt(coarse=X,half=Y,fine=Z,coarse_rmse=float(np.sqrt(np.mean((X-Z)**2))),half_rmse=float(np.sqrt(np.mean((Y-Z)**2))),mean=Z.mean(0),variance=Z.var(0),seed=seed)


def fokker_planck(lo,hi,cells,drift,diffusion,p0,times):
    """Scalar reflecting finite-volume upwind drift, constant diffusion D=variance_rate/2.
    Cell masses, not point densities. Generator columns sum to zero.
    """
    need(type(cells) is int and 4<=cells<=128 and all(type(v) in (int,float) and np.isfinite(v) and abs(v)<=1e4 for v in (lo,hi,diffusion)) and hi>lo and diffusion>=0,'grid budget')
    a,b,c=vec(drift,3);p=probability(p0,cells);t=array(times,1);need(len(t)<=65 and t[0]>=0 and t[-1]<=16 and np.all(np.diff(t)>=0),'time grid')
    dx=(hi-lo)/cells;edges=lo+dx*np.arange(1,cells);v=a*edges+b*np.tanh(edges)+c;right=np.maximum(v,0)/dx+diffusion/dx**2;left=np.maximum(-v,0)/dx+diffusion/dx**2
    need(max(np.max(right),np.max(left))<=1e5,'flux budget');G=np.zeros((cells,cells));i=np.arange(cells-1);G[i+1,i]=right;G[i,i+1]=left;G-=np.diag(G.sum(0));X=np.array([expm(G*u)@p for u in t]);need(np.isfinite(X).all() and X.min()>=-1e-10 and np.max(abs(X.sum(1)-1))<=1e-8,'mass/positivity drift')
    return receipt(centers=lo+dx*(np.arange(cells)+.5),masses=X,generator=G,mass_error=float(np.max(abs(X.sum(1)-1))))


def qr_factor(B):
    """Lower covariance factor of B B^T using QR, positive diagonal."""
    _,R=np.linalg.qr(B.T,mode='reduced');S=R.T;S=S*np.where(np.diag(S)<0,-1.,1.);need(np.isfinite(S).all() and np.all(np.diag(S)>0),'rank loss');return S


def linear_inputs(F,Q,H,R,m,P):
    F=square(F);n=len(F);m=vec(m,n);P=cov(P,n,True);Q=cov(Q,n);H=array(H,2);k=len(H);need(H.shape==(k,n) and k<=16,'observation matrix');R=cov(R,k,True);return F,Q,H,R,m,P


def obs_list(observations):
    need(type(observations) in (tuple,list) and 1<=len(observations)<=256,'observation budget');return observations


def sqrt_filter(F,Q,H,R,m,P,observations):
    F,Q,H,R,m,P=linear_inputs(F,Q,H,R,m,P);n=len(m);e,V=np.linalg.eigh(Q);L=V*np.sqrt(e);N=np.linalg.cholesky(R);S=np.linalg.cholesky(P);means=[m];factors=[S]
    for y in obs_list(observations):
        m=bounded(F@m);S=qr_factor(np.column_stack((F@S,L)))
        if y is not None:
            y=vec(y,len(H));HS=H@S;U=qr_factor(np.column_stack((HS,N)));K=cho_solve((U,True),HS@S.T).T;m=bounded(m+K@(y-H@m));S=qr_factor(np.column_stack(((np.eye(n)-K@H)@S,K@N)))
        means.append(m);factors.append(S)
    S=np.array(factors);return receipt(means=np.array(means),factors=S,covariances=S@S.transpose(0,2,1))


def information_filter(F,Q,H,R,m,P,observations):
    F,Q,H,R,m,P=linear_inputs(F,Q,H,R,m,P);n=len(m);I=np.eye(n);J=cho_solve(cho_factor(P),I);eta=J@m;RI=cho_solve(cho_factor(R),np.eye(len(H)));means=[m];covs=[P];infos=[J]
    for y in obs_list(observations):
        P=cho_solve(cho_factor(J),I);m=cho_solve(cho_factor(J),eta);C=F@P@F.T+Q;need(np.linalg.cond(C)<=1e12,'prediction condition');J=cho_solve(cho_factor(C),I);eta=J@bounded(F@m)
        if y is not None:J=J+H.T@RI@H;eta=eta+H.T@RI@vec(y,len(H))
        J=(J+J.T)/2;need(np.linalg.cond(J)<=1e12,'information condition');P=cho_solve(cho_factor(J),I);m=bounded(cho_solve(cho_factor(J),eta));means.append(m);covs.append(P);infos.append(J)
    return receipt(means=np.array(means),covariances=np.array(covs),information=np.array(infos))


def unscented(F,b,c,Q,H,d,R,m,P,observations):
    """Positive-weight 2n+1 unscented transform (lambda=1); tanh drift, quadratic sensor."""
    F,Q,H,R,m,P=linear_inputs(F,Q,H,R,m,P);n=len(m);b=vec(b,n);c=vec(c,n);d=array(d,2);need(d.shape==H.shape,'sensor shape');w=np.full(2*n+1,1/(2*(n+1)));w[0]=1/(n+1)
    def points(m,P):
        L=np.linalg.cholesky(P)*np.sqrt(n+1);return np.vstack((m,m+L.T,m-L.T))
    means=[m];covs=[P];nis=[]
    for y in obs_list(observations):
        X=points(m,P);Y=bounded(X@F.T+b*np.tanh(X)+c);m=w@Y;D=Y-m;P=clean((D.T*w)@D+Q)
        if y is not None:
            X=points(m,P);Y=bounded(X@H.T+(X*X)@d.T);ym=w@Y;D=Y-ym;V=clean((D.T*w)@D+R);cross=((X-m).T*w)@D;K=cho_solve(cho_factor(V),cross.T).T;r=vec(y,len(H))-ym;m=bounded(m+K@r);P=clean(P-K@V@K.T);nis.append(float(r@cho_solve(cho_factor(V),r)))
        else:nis.append(None)
        means.append(m);covs.append(P)
    return receipt(means=np.array(means),covariances=np.array(covs),nis=tuple(nis))


def posterior_paths(filtered,paths,seed):
    """FFBS for a prior SSM-04 linear Gaussian filtering result, offline only."""
    m=array(filtered['means'],2);P=array(filtered['covariances'],3);p=array(filtered['predicted'],2);C=array(filtered['predicted_cov'],3);F=array(filtered['transitions'],3);T,n=m.shape
    need(T>=2 and n<=16 and P.shape==(T,n,n) and p.shape==(T-1,n) and C.shape==F.shape==(T-1,n,n) and type(paths) is int and 1<=paths<=8192 and paths*T*n<=1048576,'FFBS shape/budget');rng=seed_rng(seed)
    def noise(P):
        e,V=np.linalg.eigh(clean(P));return rng.standard_normal((paths,n))@(V*np.sqrt(e)).T
    X=np.empty((paths,T,n));X[:,-1]=m[-1]+noise(cov(P[-1],n))
    for j in range(T-2,-1,-1):
        W=cov(C[j],n,True);need(np.linalg.cond(W)<=1e12,'prediction condition');J=cho_solve(cho_factor(W),F[j]@P[j]).T;X[:,j]=m[j]+(X[:,j+1]-p[j])@J.T+noise(P[j]-J@W@J.T)
    return receipt(paths=bounded(X),uses_future=True,seed=seed)


def ensemble(F,Q,H,R,initial,observations,seed):
    """Stochastic EnKF with independent perturbations; sample covariance, not exact posterior."""
    F=square(F);n=len(F);Q=cov(Q,n);X=array(initial,2);N=len(X);H=array(H,2);k=len(H);R=cov(R,k,True);obs=obs_list(observations);need(X.shape==(N,n) and 3<=N<=4096 and H.shape==(k,n) and N*n*len(obs)<=1048576,'ensemble budget');rng=seed_rng(seed);e,V=np.linalg.eigh(Q);L=V*np.sqrt(e);B=np.linalg.cholesky(R);means=[];covs=[]
    for y in obs:
        X=bounded(X@F.T+rng.standard_normal(X.shape)@L.T)
        if y is not None:
            D=X-X.mean(0);P=D.T@D/(N-1);K=cho_solve(cho_factor(H@P@H.T+R),H@P).T;X=bounded(X+(vec(y,k)+rng.standard_normal((N,k))@B.T-X@H.T)@K.T)
        D=X-X.mean(0);means.append(X.mean(0));covs.append(D.T@D/(N-1))
    return receipt(means=np.array(means),covariances=np.array(covs),ensemble=X,seed=seed)


def switching(P,prior,modes,m,P0,observations,H,R):
    """Enumerate small switching linear Gaussian mixtures without pruning or merging.
    Initial regime prior applies to first transition; exact enumeration, floating conditioning.
    """
    P=kernel(P);k=len(P);prior=probability(prior,k);obs=obs_list(observations);need(2<=k<=4 and k**len(obs)<=4096 and type(modes) in (list,tuple) and len(modes)==k,'switching budget');parsed=[linear_inputs(F,Q,H,R,m,P0) for F,Q in modes];m=parsed[0][4];P0=parsed[0][5];n=len(m);parts=[((),m,P0,0.)];means=[];covs=[];probs=[];ll=0.
    for y in obs:
        nxt=[]
        for path,mu,C,w in parts:
            weights=prior if not path else P[path[-1]]
            for j,pr in enumerate(weights):
                if pr==0:continue
                F,Q,H,R,_,_=parsed[j];a=bounded(F@mu);B=clean(F@C@F.T+Q);l=0.
                if y is not None:a,B,l,_=gaussian_update(a,B,H,R,y)
                nxt.append((path+(j,),a,B,w+np.log(pr)+l))
        z=logsumexp([v[3] for v in nxt]);need(np.isfinite(z),'mixture collapse');ll+=z;parts=[(p,a,B,w-z) for p,a,B,w in nxt];w=np.exp([v[3] for v in parts]);a=sum(v[1]*q for v,q in zip(parts,w));B=sum((v[2]+np.outer(v[1]-a,v[1]-a))*q for v,q in zip(parts,w));means.append(bounded(a));covs.append(clean(B));probs.append(np.bincount([v[0][-1] for v in parts],weights=w,minlength=k))
    return receipt(means=np.array(means),covariances=np.array(covs),regime_probabilities=np.array(probs),components=len(parts),log_likelihood=float(ll))
