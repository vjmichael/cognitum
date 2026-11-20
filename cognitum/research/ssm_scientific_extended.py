"""Bounded CPU scientific inference references; no external execution authority."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, ndtr
from numpy.polynomial.hermite import hermgauss
from .ssm_stochastic import need, array, receipt, kernel, probability


def variational(y,a,q,r,decoder,initial=(0.,1.)):
    """Scalar Gaussian latent AR(1), linear+tanh decoder; joint mean-field ELBO."""
    y=array(y,1);d=array(decoder,1);m0,p0=array(initial,1);T=len(y)
    need(2<=T<=64 and d.shape in ((2,),(3,)) and all(type(v) in (int,float) and np.isfinite(v) for v in (a,q,r)) and abs(a)<=1 and 1e-4<=q<=100 and 1e-4<=r<=100 and 1e-4<=p0<=100,'latent profile')
    z,w=hermgauss(24);z=z*np.sqrt(2);w=w/np.sqrt(np.pi);const=np.log(2*np.pi)
    def calc(p):
        m=p[:T];l=p[T:];s=np.exp(l);v=s*s;X=m[:,None]+s[:,None]*z;t=np.tanh(X);h=d[0]*X+d[1]*t;dh=d[0]+d[1]*(1-t*t)
        if len(d)==3:
            u=np.tanh(2*t+.25);h+=d[2]*u;dh+=2*d[2]*(1-u*u)*(1-t*t)
        e=h-y[:,None];g=(e*dh/r)*w
        loss=.5*((m[0]-m0)**2+v[0])/p0+.5*(const+np.log(p0));gm=np.zeros(T);gl=np.zeros(T);gm[0]=(m[0]-m0)/p0;gl[0]=v[0]/p0
        b=m[1:]-a*m[:-1];loss+=.5*np.sum((b*b+v[1:]+a*a*v[:-1])/q+const+np.log(q));gm[1:]+=b/q;gm[:-1]-=a*b/q;gl[1:]+=v[1:]/q;gl[:-1]+=a*a*v[:-1]/q
        loss+=.5*np.sum((e*e)@w/r+const+np.log(r));gm+=g.sum(1);gl+=np.sum(g*s[:,None]*z,1);loss-=np.sum(l+.5*(1+const));gl-=1
        return float(loss),np.r_[gm,gl]
    start=np.r_[np.clip(y,-10,10),np.zeros(T)];sol=minimize(calc,start,jac=True,bounds=[(-100,100)]*T+[(-8,4)]*T,method='L-BFGS-B',options={'maxiter':500,'ftol':1e-13,'gtol':1e-8});need(sol.success,'variational convergence');p=sol.x;value,g=calc(p);need(np.isfinite(value),'ELBO finite');eps=1e-5;direction=np.linspace(-1,1,2*T);fd=(calc(p+eps*direction)[0]-calc(p-eps*direction)[0])/(2*eps)
    return receipt(means=p[:T],variances=np.exp(2*p[T:]),elbo=-value,initial_elbo=-calc(start)[0],directional_gradient_error=float(abs(g@direction-fd)),uses_future=True,mean_field=True,quadrature_order=24)


def variational_train(sequences,a,q,r,decoder,rounds=4):
    """Variational EM for a fixed two-layer nonlinear feature decoder; learn three readout weights."""
    Y=array(sequences,2);d=array(decoder,1);need(2<=len(Y)<=8 and 2<=Y.shape[1]<=32 and d.shape==(3,) and type(rounds) is int and 1<=rounds<=12,'training budget');z,w=hermgauss(24);z=z*np.sqrt(2);w=w/np.sqrt(np.pi);history=[]
    for j in range(rounds+1):
        posts=[variational(y,a,q,r,d.tolist()) for y in Y];value=sum(t['elbo'] for t in posts);need(not history or value>=history[-1]-1e-6*max(1,abs(value)),'variational EM descent');history.append(value)
        if j==rounds:break
        M=np.zeros((3,3));b=np.zeros(3)
        for y,t in zip(Y,posts):
            X=t['means'][:,None]+np.sqrt(t['variances'])[:,None]*z;h=np.tanh(X);F=np.stack((X,h,np.tanh(2*h+.25)),-1);M+=np.einsum('tqi,tqj,q->ij',F,F,w);b+=np.einsum('tqi,t,q->i',F,y,w)
        need(np.linalg.cond(M)<=1e8,'decoder feature rank');d=np.linalg.solve(M,b);need(np.max(abs(d))<=100,'decoder budget')
    return receipt(decoder=d,elbo_history=np.array(history),fixed_hidden_layers=True,global_optimum=False)


def particle_gradient(y,x0,noise,a,b,sigma,r,min_ess=.01):
    """Reparameterized scalar bootstrap importance filter, no resampling, d log Z / db."""
    y=array(y,1);x=array(x0,1);E=array(noise,2,524288);N=len(x);need(2<=N<=8192 and len(y)<=64 and E.shape==(len(y),N) and all(type(v) in (int,float) and np.isfinite(v) for v in (a,b,sigma,r,min_ess)) and abs(a)<=1 and abs(b)<=4 and 0<=sigma<=10 and 1e-4<=r<=100 and 0<min_ess<=1,'particle profile');w=np.full(N,-np.log(N));dx=np.zeros(N);dw=np.zeros(N);means=[];ess=[];ll=grad=0.
    for obs,e in zip(y,E):
        z=np.tanh(x);dx=(a+b*(1-z*z))*dx+z;x=a*x+b*z+sigma*e;need(np.isfinite(x).all() and np.max(abs(x))<=1e8,'particle state');v=obs-x;s=w-.5*(v*v/r+np.log(2*np.pi*r));ds=dw+v*dx/r;c=logsumexp(s);p=np.exp(s-c);g=p@ds;w=s-c;dw=ds-g;ll+=c;grad+=g;ne=1/(p@p);need(ne>=N*min_ess,'importance degeneracy');ess.append(ne);means.append(p@x)
    return receipt(log_likelihood=float(ll),gradient=float(grad),means=np.array(means),ess=np.array(ess),resampled=False,conditional_on_noise=True)


def modes(x,k):
    x=array(x,2,262144);n=x.shape[1];need(8<=n<=512 and type(k) is int and 1<=k<=16 and 2*k<n,'periodic mode budget');z=np.fft.rfft(x,axis=1)/n;return z[:,:k+1],float(np.max(abs(z[:,k+1:])))


def operator_fit(states,forcing,next_states,k):
    """Periodic spectral state-space operator; linear state/forcing plus fixed tanh neural feature."""
    X=array(states,2,262144);U=array(forcing,2,262144);Y=array(next_states,2,262144);need(X.shape==U.shape==Y.shape and 3<=len(X)<=512,'operator training shape');A,ax=modes(X,k);B,bx=modes(U,k);C,_=modes(np.tanh(U),k);Z,zx=modes(Y,k);need(max(ax,bx,zx)<=1e-8,'training outside band');weights=[]
    for j in range(k+1):
        D=np.column_stack((A[:,j],B[:,j],C[:,j]));D=np.vstack((D.real,D.imag));v=np.r_[Z[:,j].real,Z[:,j].imag];s=np.linalg.svd(D,compute_uv=False);need(s[-1]>1e-9*s[0],'operator feature rank');w=np.linalg.lstsq(D,v,rcond=None)[0];need(0<=w[0]<=1 and np.max(abs(w))<=100,'unstable operator');weights.append(w)
    return receipt(weights=np.array(weights),domain='periodic unit interval',training_resolution=X.shape[1],modes=k)


def operator_roll(weights,x0,forcing):
    w=array(weights,2);k=len(w)-1;X=array(x0,1);U=array(forcing,2,262144);need(w.shape==(k+1,3) and np.all((w[:,0]>=0)&(w[:,0]<=1)) and np.max(abs(w))<=100 and U.shape[1]==len(X) and len(U)<=512,'operator rollout');a,tail=modes(X[None,:],k);b,ut=modes(U,k);c,ct=modes(np.tanh(U),k);need(max(tail,ut)<=1e-8,'input outside band');z=a[0];N=len(X);Y=[X]
    for i in range(len(U)):
        z=w[:,0]*z+w[:,1]*b[i]+w[:,2]*c[i];q=np.zeros(N//2+1,complex);q[:k+1]=N*z;v=np.fft.irfft(q,n=N);need(np.isfinite(v).all() and np.max(abs(v))<=1e8,'operator state');Y.append(v)
    return receipt(states=np.array(Y),discarded_neural_feature_max=ct,resolution=N,domain='periodic unit interval')


def regime_fit(y,labels,k):
    """Fit labeled categorical transitions and scalar Gaussian emissions from training only."""
    y=array(y,1);L=np.asarray(labels);need(type(k) is int and 2<=k<=4 and L.shape==y.shape and L.dtype.kind in 'iu' and len(y)<=8192 and np.all((L>=0)&(L<k)),'regime training');P=np.ones((k,k));m=[];v=[]
    for i in range(k):
        z=y[L==i];need(len(z)>=8 and z.var()>=1e-4,'regime sample/variance');m.append(z.mean());v.append(z.var())
    np.add.at(P,(L[:-1],L[1:]),1);return receipt(transition=P/P.sum(1)[:,None],means=np.array(m),variances=np.array(v),baseline_mean=float(y.mean()),baseline_variance=float(y.var()))


def regime_forecast(P,means,variances,prior,observations,baseline_mean,baseline_variance):
    """Prequential Gaussian mixture scoring; update posterior only after scoring observation."""
    P=kernel(P);k=len(P);m,v=array(means,1),array(variances,1);p=probability(prior,k);y=array(observations,1);need(2<=k<=4 and m.shape==v.shape==(k,) and np.all((v>=1e-4)&(v<=1e6)) and len(y)<=2048 and np.isfinite(baseline_mean) and np.isfinite(baseline_variance) and baseline_variance>=1e-4,'forecast profile');pred=[];scores=[];pit=[];priors=[];flags=[];baseline=[]
    for obs in y:
        p=p@P;priors.append(p.copy());pred.append(p@m);logp=np.full(k,-np.inf);mask=p>0;logp[mask]=np.log(p[mask]);z=(obs-m)/np.sqrt(v);l=logp-.5*(z*z+np.log(2*np.pi*v));s=logsumexp(l);scores.append(-s);pit.append(p@ndtr(z));flags.append(bool(np.min(abs(z))>5));baseline.append(.5*((obs-baseline_mean)**2/baseline_variance+np.log(2*np.pi*baseline_variance)));p=np.exp(l-s)
    pit=np.array(pit);return receipt(predictions=np.array(pred),priors=np.array(priors),negative_log_score=float(np.mean(scores)),baseline_log_score=float(np.mean(baseline)),central_90_coverage=float(np.mean((pit>=.05)&(pit<=.95))),pit=pit,ood=np.array(flags),final_posterior=p)


def automaton(transitions,tokens,initial,accept):
    """Exact finite automaton and associative transition-function composition."""
    A=np.asarray(transitions);t=np.asarray(tokens);need(A.ndim==2 and A.dtype.kind in 'iu' and 1<=A.shape[0]<=8 and 1<=A.shape[1]<=16 and np.all((A>=0)&(A<A.shape[1])) and t.ndim==1 and t.dtype.kind in 'iu' and 1<=len(t)<=1024 and np.all((t>=0)&(t<len(A))) and type(initial) is int and 0<=initial<A.shape[1] and type(accept) in (tuple,list) and all(type(j) is int and 0<=j<A.shape[1] for j in accept),'automaton profile');F=A[t].copy();paths=[];x=initial
    for j in t:x=int(A[j,x]);paths.append(x)
    h=1
    while h<len(F):f=F.copy();F[h:]=np.take_along_axis(f[h:],f[:-h],axis=1);h*=2
    need(np.array_equal(F[:,initial],paths),'composition mismatch');return receipt(states=np.array(paths),accepted=x in accept,transition=F[-1])


def recall_trial(seed,train_count=128,test_count=128):
    """Fixed key-value retrieval vs decay and last-token baselines; learned scalar readouts."""
    need(type(seed) is int and 0<=seed<2**32 and type(train_count) is int and type(test_count) is int and 32<=train_count<=512 and 32<=test_count<=512,'recall budget');rng=np.random.default_rng(seed)
    def features(n,length):
        keys=np.array([rng.permutation(length) for _ in range(n)]);values=rng.choice([-1.,1.],size=(n,length));query=rng.integers(0,length,n);target=np.sum(values*(keys==query[:,None]),1);att=np.sum(values*(keys==query[:,None]),1);dec=values@(.8**np.arange(length-1,-1,-1));last=values[:,-1];return [np.column_stack((np.ones(n),f)) for f in (att,dec,last)],target
    X,y=features(train_count,8);T,z=features(test_count,16);metrics={}
    for name,D,E in zip(('exact_key','decay','last_token'),X,T):
        w=np.linalg.lstsq(D,y,rcond=None)[0];p=E@w;metrics[name]={'accuracy':float(np.mean(np.where(p>=0,1,-1)==z)),'rmse':float(np.sqrt(np.mean((p-z)**2)))}
    return receipt(metrics=metrics,train_length=8,test_length=16,hand_designed_features=True)
