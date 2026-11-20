"""Bounded CPU stochastic dynamics research; numerical, not certified."""
import numpy as np
from scipy.linalg import expm, cho_factor, cho_solve
from scipy.special import logsumexp


def need(ok,msg):
    if not ok: raise ValueError(msg)


def array(x,ndim,limit=65536):
    a=np.asarray(x);need(a.ndim==ndim and 0<a.size<=limit and a.dtype.kind in 'iuf','shape/type budget')
    a=a.astype(float);need(np.isfinite(a).all() and np.max(np.abs(a))<=1e8,'finite magnitude budget');return a


def square(x):
    a=array(x,2);need(a.shape[0]==a.shape[1] and len(a)<=16,'square dimension');return a


def cov(x,n,strict=False):
    a=square(x);need(a.shape==(n,n) and np.allclose(a,a.T,rtol=0,atol=1e-12),'covariance symmetry')
    a=(a+a.T)/2;e=np.linalg.eigvalsh(a);need(e[0]>0 if strict else e[0]>=0,'covariance positivity');return a


def clean(a):
    a=(a+a.T)/2;need(np.isfinite(a).all(),'nonfinite covariance');e,v=np.linalg.eigh(a);need(e[0]>=-1e-10*max(1.,e[-1]),'negative covariance');return (v*np.maximum(e,0))@v.T


def receipt(**kw):return dict(**kw,certified=False,execution_authorized=False)


def probability(p,n):
    p=array(p,1);need(p.shape==(n,) and np.all(p>=0) and abs(p.sum()-1)<=1e-12,'probability vector');return p/p.sum()


def kernel(P):
    P=square(P);need(np.all(P>=0) and np.allclose(P.sum(1),1,rtol=0,atol=1e-12),'stochastic matrix');return P/P.sum(1)[:,None]


def markov(P,p,steps):
    P=kernel(P);p=probability(p,len(P));need(type(steps) is int and 1<=steps<=512,'step budget');rows=[p]
    for _ in range(steps):rows.append(rows[-1]@P)
    return receipt(states=np.array(rows))


def ctmc(G,p,times):
    G=square(G);p=probability(p,len(G));t=array(times,1);off=G-np.diag(np.diag(G));need(np.all(off>=0) and np.all(np.diag(G)<=0) and np.allclose(G.sum(1),0,atol=1e-12,rtol=0),'generator');need(len(t)<=513 and np.all(np.diff(t)>=0) and t[0]>=0 and t[-1]<=32,'time budget')
    X=np.array([p@expm(G*u) for u in t]);need(np.isfinite(X).all() and X.min()>=-1e-10 and np.max(abs(X.sum(1)-1))<=1e-9,'probability drift');return receipt(states=X,times=t)


def discretize(A,Q,dt):
    A=square(A);n=len(A);Q=cov(Q,n);need(type(dt) in (int,float) and 0<dt<=1,'time step')
    Z=np.zeros_like(A);M=expm(np.block([[A,Q],[Z,-A.T]])*dt);F=M[:n,:n];W=clean(M[:n,n:]@F.T);need(np.isfinite(F).all() and np.max(abs(F))<=1e8,'transition budget');return F,W


def ou(theta,mu,sigma,x0,dt,steps,paths,seed):
    """OU exact transition and Euler coupled to its Brownian increments."""
    need(all(type(v) in (int,float) and np.isfinite(v) and abs(v)<=1e4 for v in (theta,mu,sigma,x0,dt)) and theta>0 and sigma>=0 and 0<dt<=1 and theta*dt<=1,'OU parameters')
    need(type(steps) is int and 1<=steps<=512 and type(paths) is int and 1<=paths<=8192 and steps*paths<=1048576 and type(seed) is int and 0<=seed<2**32,'path budget')
    rng=np.random.default_rng(seed);f=np.exp(-theta*dt);c=-np.expm1(-theta*dt)/theta;v=-np.expm1(-2*theta*dt)/(2*theta);res=max(0.,v-c*c/dt);X=np.full((paths,),float(x0));Y=X.copy()
    for _ in range(steps):
        z=rng.standard_normal(paths);w=rng.standard_normal(paths);X=mu+f*(X-mu)+sigma*(c/np.sqrt(dt)*z+np.sqrt(res)*w);Y+=(theta*(mu-Y)*dt+sigma*np.sqrt(dt)*z)
    t=dt*steps;return receipt(exact=X,euler=Y,mean=mu+(x0-mu)*np.exp(-theta*t),variance=sigma*sigma*(-np.expm1(-2*theta*t))/(2*theta),coupled_rmse=float(np.sqrt(np.mean((X-Y)**2))))


def gaussian_update(m,P,H,R,y):
    n=len(m);H=array(H,2);y=array(y,1);k=len(y);need(H.shape==(k,n) and k<=16,'observation shape');R=cov(R,k,True);S=H@P@H.T+R;L=cho_factor(S);r=y-H@m;K=cho_solve(L,H@P).T;J=np.eye(n)-K@H;C=clean(J@P@J.T+K@R@K.T);nis=float(r@cho_solve(L,r));ll=-.5*(k*np.log(2*np.pi)+2*np.log(np.diag(L[0])).sum()+nis);return m+K@r,C,float(ll),nis


def kalman(A,Q,H,R,m0,P0,observations,dts):
    """Continuous linear drift, sampled observations (None = missing entire sample)."""
    A=square(A);n=len(A);Q=cov(Q,n);m=array(m0,1);need(m.shape==(n,),'state shape');P=cov(P0,n);H=array(H,2);need(H.shape[1]==n and H.shape[0]<=16,'measurement shape');R=cov(R,H.shape[0],True);need(type(observations) in (tuple,list) and 1<=len(observations)<=512 and len(dts)==len(observations),'observation budget')
    ms=[m];ps=[P];pred=[];pc=[];fs=[];ll=[];nis=[]
    for y,dt in zip(observations,dts):
        F,W=discretize(A,Q,dt);m=F@m;P=clean(F@P@F.T+W);pred.append(m);pc.append(P);fs.append(F)
        if y is not None:m,P,l,z=gaussian_update(m,P,H,R,y)
        else:l,z=0.,None
        need(np.isfinite(m).all() and np.max(abs(m))<=1e8,'state budget');ms.append(m);ps.append(P);ll.append(l);nis.append(z)
    return receipt(means=np.array(ms),covariances=np.array(ps),predicted=np.array(pred),predicted_cov=np.array(pc),transitions=np.array(fs),log_likelihood=float(sum(ll)),nis=tuple(nis))


def smooth(filtered):
    """RTS offline smoother; accepts a filter result, includes future observations."""
    m=filtered['means'].copy();P=filtered['covariances'].copy();p=filtered['predicted'];C=filtered['predicted_cov'];F=filtered['transitions'];need(len(m)==len(p)+1,'filter shape')
    for j in range(len(p)-1,-1,-1):
        need(np.linalg.eigvalsh(C[j])[0]>0 and np.linalg.cond(C[j])<=1e12,'smoother prediction singular/ill-conditioned');J=cho_solve(cho_factor(C[j]),F[j]@P[j]).T;m[j]+=J@(m[j+1]-p[j]);P[j]=clean(P[j]+J@(P[j+1]-C[j])@J.T)
    return receipt(means=m,covariances=P,uses_future=True)


def nonlinear_update(m,P,y,R,observation,method='ekf'):
    """Scalar quadratic sensor h(x)=a*x+b*x², coupled Gaussian prior; EKF or cubature."""
    m=array(m,1);n=len(m);need(n<=16,'state dimension');P=cov(P,n,True);a,b=map(lambda x:array(x,1),observation);need(a.shape==b.shape==m.shape and type(y) in (int,float) and np.isfinite(y),'sensor shape');R=cov([[R]],1,True)[0,0]
    if method=='ekf':
        H=a+2*b*m;ym=a@m+b@(m*m);S=float(H@P@H+R);K=P@H/S;J=np.eye(n)-np.outer(K,H);C=clean(J@P@J.T+R*np.outer(K,K))
    elif method=='cubature':
        L=np.linalg.cholesky(P)*np.sqrt(n);D=np.concatenate((L.T,-L.T));X=m+D;Y=X@a+(X*X)@b;ym=Y.mean();dy=Y-ym;S=float(dy@dy/(2*n)+R);K=D.T@dy/(2*n*S);C=clean(P-S*np.outer(K,K))
    else:raise ValueError('unknown nonlinear method')
    r=y-ym;z=m+K*r;need(np.isfinite(z).all() and np.max(abs(z))<=1e8,'nonlinear state budget');return receipt(mean=z,covariance=C,nis=float(r*r/S),method=method)


def particle(A,Q,H,R,particles,observations,seed,threshold=.5):
    """Bootstrap filter, Gaussian transition/likelihood, systematic ESS resampling."""
    A=square(A);n=len(A);Q=cov(Q,n);X=array(particles,2);N=len(X);H=array(H,2);k=len(H);R=cov(R,k,True);need(X.shape==(N,n) and 2<=N<=4096 and H.shape==(k,n) and type(observations) in (tuple,list) and 1<=len(observations)<=256 and N*len(observations)<=1048576 and type(seed) is int and 0<=seed<2**32 and type(threshold) in (int,float) and 0<threshold<=1,'particle shape/budget')
    rng=np.random.default_rng(seed);w=np.ones(N)/N;e,V=np.linalg.eigh(Q);L=V*np.sqrt(e);chol=cho_factor(R);means=[];ess=[];resampled=[];loglike=0.
    for y in observations:
        X=X@A.T+rng.standard_normal(X.shape)@L.T;need(np.isfinite(X).all() and np.max(abs(X))<=1e8,'particle state budget')
        if y is not None:
            y=array(y,1);need(y.shape==(k,),'observation shape');r=y-X@H.T;lp=-.5*(np.sum(r*cho_solve(chol,r.T).T,axis=1)+k*np.log(2*np.pi)+2*np.log(np.diag(chol[0])).sum());logw=np.full(N,-np.inf);np.log(w,out=logw,where=w>0);z=logsumexp(logw+lp);need(np.isfinite(z),'likelihood collapse');w=np.exp(logw+lp-z);w/=w.sum();loglike+=z
        E=float(1/(w@w));means.append(w@X);ess.append(E);resampled.append(E<threshold*N)
        if resampled[-1]:
            c=np.cumsum(w);c[-1]=1.;idx=np.searchsorted(c,(rng.random()+np.arange(N))/N,side='right');X=X[idx];w=np.ones(N)/N
    return receipt(means=np.array(means),ess=np.array(ess),resampled=tuple(resampled),particles=X,weights=w,log_likelihood=float(loglike))


def hmm(P,E,p,observations):
    """Categorical HMM: emission at time zero, scaled forward/backward and Viterbi."""
    P=kernel(P);n=len(P);E=array(E,2);p=probability(p,n);need(E.shape[0]==n and E.shape[1]<=32 and np.all(E>=0) and np.allclose(E.sum(1),1,atol=1e-12,rtol=0),'emission probabilities');need(type(observations) in (list,tuple) and 1<=len(observations)<=512 and all(type(y) is int and 0<=y<E.shape[1] for y in observations),'symbol budget')
    def log(a):
        z=np.full(a.shape,-np.inf);np.log(a,out=z,where=a>0);return z
    T=log(P);em=log(E[:,observations].T);f=[];v=[];back=[];scales=[]
    for j,row in enumerate(em):
        if j==0:q=log(p)+row;d=q
        else:q=logsumexp(f[-1][:,None]+T,axis=0)+row;score=v[-1][:,None]+T;back.append(np.argmax(score,axis=0));d=np.max(score,axis=0)+row
        z=logsumexp(q);need(np.isfinite(z),'impossible observation');f.append(q-z);scales.append(z);v.append(d)
    b=np.zeros(n);post=[np.exp(f[-1])];path=[int(np.argmax(v[-1]))]
    for j in range(len(f)-2,-1,-1):
        b=logsumexp(T+em[j+1]+b,axis=1)-scales[j+1];q=f[j]+b;post.append(np.exp(q-logsumexp(q)));path.append(int(back[j][path[-1]]))
    return receipt(filtered=np.exp(f),smoothed=np.array(post[::-1]),viterbi=tuple(path[::-1]),log_likelihood=float(sum(scales)),uses_future=True)
