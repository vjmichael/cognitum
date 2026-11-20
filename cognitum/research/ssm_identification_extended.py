"""Bounded statistical identification research; numerical, no execution authority."""
import numpy as np
from .ssm_stochastic import need, array, receipt, cov
from .ssm_identification import design, fit, era, library, operator_inference


def latent_em(y, phi, q, r, initial=(0.,1.), iterations=80):
    """Scalar latent AR(1), fixed initial law, missing observations; EM for phi,Q,R."""
    need(type(y) in (list,tuple) and 4<=len(y)<=2048,'sequence budget')
    obs=np.array([np.nan if z is None else z for z in y],float);mask=np.array([z is not None for z in y]);need(obs.ndim==1 and mask.sum()>=4 and np.isfinite(obs[mask]).all() and np.max(abs(obs[mask]))<=1e6,'observations')
    m0,p0=array(initial,1);need(p0>0 and all(type(v) in (int,float) and np.isfinite(v) for v in (phi,q,r)) and abs(phi)<=.99 and 1e-8<=q<=1e6 and 1e-8<=r<=1e6 and type(iterations) is int and 1<=iterations<=256,'EM parameters')
    T=len(obs)
    def est(a,Q,R):
        m=np.empty(T+1);p=np.empty(T+1);pred=np.empty(T);v=np.empty(T);m[0]=m0;p[0]=p0;ll=0.
        for j in range(T):
            pred[j]=a*m[j];v[j]=a*a*p[j]+Q;m[j+1]=pred[j];p[j+1]=v[j]
            if mask[j]:
                S=v[j]+R;d=obs[j]-pred[j];m[j+1]+=v[j]/S*d;p[j+1]=v[j]*R/S;ll-=.5*(np.log(2*np.pi*S)+d*d/S)
        J=a*p[:-1]/v;cross=np.empty(T)
        for j in range(T-1,-1,-1):
            m[j]+=J[j]*(m[j+1]-pred[j]);p[j]+=J[j]**2*(p[j+1]-v[j]);cross[j]=J[j]*p[j+1]
        need(np.isfinite(ll) and np.isfinite(m).all() and np.all(p>=-1e-10),'smoothing failure');return m,p,cross,float(ll)
    m,p,c,ll=est(phi,q,r);history=[ll]
    for _ in range(iterations):
        e=p+m*m;lag=c+m[:-1]*m[1:];den=e[:-1].sum();need(den>0,'unidentifiable transition')
        a=float(np.clip(lag.sum()/den,-.99,.99));Q=float(np.clip(np.mean(e[1:]-2*a*lag+a*a*e[:-1]),1e-8,1e6));R=float(np.clip(np.mean((obs[mask]-m[1:][mask])**2+p[1:][mask]),1e-8,1e6));m,p,c,ll=est(a,Q,R);need(ll>=history[-1]-1e-8*max(1,abs(ll)),'EM descent');history.append(ll);phi,q,r=a,Q,R
        if history[-1]-history[-2]<1e-9*max(1,abs(ll)):break
    return receipt(phi=phi,process_variance=q,measurement_variance=r,means=m,variances=p,log_likelihood=np.array(history),uses_future=True,global_optimum=False)


def noisy_era(train,validation,test,orders,blocks):
    """Order chosen only on separate validation impulse response; score untouched test."""
    train,validation,test=(array(g,3) for g in (train,validation,test));need(train.shape==validation.shape==test.shape and type(orders) in (list,tuple) and 1<=len(orders)<=8 and all(type(o) is int and 1<=o<=16 for o in orders) and len(set(orders))==len(orders),'ERA selection shape')
    def score(z,G):
        A,B,C,D=(z[k] for k in ('A','B','C','D'));Z=B.copy();pred=[D]
        for _ in range(1,len(G)):
            pred.append(C@Z);Z=A@Z;need(np.isfinite(Z).all() and np.max(abs(Z))<=1e8,'prediction budget')
        return float(np.sqrt(np.mean((np.array(pred)-G)**2)))
    candidates=[];rejected=[]
    for order in sorted(orders):
        try:z=era(train,order,blocks);err=score(z,validation)
        except ValueError:rejected.append(order);continue
        candidates.append((err,order,z))
    need(bool(candidates),'no admissible order');err,order,z=min(candidates,key=lambda t:(t[0],t[1]));return receipt(**{k:z[k] for k in ('A','B','C','D')},order=order,validation_rmse=err,test_rmse=score(z,test),validation_scores=tuple((o,e) for e,o,_ in candidates),rejected_orders=tuple(rejected),similarity_ambiguous=True)


def weak_sindy(train,test,dt,window,degree,threshold):
    """Compact sine-squared test functions, integration by parts, no numerical derivatives."""
    need(type(dt) in (float,int) and 0<dt<=1 and type(window) is int and 8<=window<=256 and type(threshold) in (float,int) and 0<threshold<=1e4,'weak form budget')
    def build(trajectories):
        need(type(trajectories) in (tuple,list) and 1<=len(trajectories)<=32,'trajectory count');D=[];Y=[];ex=None;total=0
        t=np.linspace(0,np.pi,window+1);w=np.sin(t)**2;dw=np.pi/(window*dt)*np.sin(2*t);weights=np.ones(window+1)*dt;weights[[0,-1]]*=.5
        for tr in trajectories:
            X=design(tr);total+=X.size;need(total<=262144 and len(X)>window,'trajectory budget');L,ex2=library(X,degree);need(ex is None or ex==ex2,'state mismatch');ex=ex2
            for j in range(0,len(X)-window,window):
                D.append((weights*w)@L[j:j+window+1]);Y.append(-(weights*dw)@X[j:j+window+1])
        return np.array(D),np.array(Y),ex
    D,Y,ex=build(train);E,Z,ex2=build(test);need(ex==ex2,'library mismatch');B,c=fit(D,Y)
    for _ in range(16):
        old=abs(B)>0
        for j in range(B.shape[1]):
            mask=abs(B[:,j])>=threshold;B[:,j]=0
            if mask.any():B[mask,j]=fit(D[:,mask],Y[:,j:j+1])[0][:,0]
        if np.array_equal(old,abs(B)>0):break
    return receipt(exponents=ex,coefficients=B,condition=c,weak_training_rmse=float(np.sqrt(np.mean((D@B-Y)**2))),weak_heldout_rmse=float(np.sqrt(np.mean((E@B-Z)**2))),symbolic_uniqueness=False)


def metric_operator(X,dX,Xtest,dXtest,metric,degree=2):
    """Constrain x^T P f(x)=0 via whitened coordinates z=L^T x, P=L L^T."""
    X,dX,Xtest,dXtest=map(design,(X,dX,Xtest,dXtest));n=X.shape[1];P=cov(metric,n,True);need(np.linalg.cond(P)<=1e8,'metric condition');L=np.linalg.cholesky(P);z=operator_inference(X@L,dX@L,Xtest@L,dXtest@L,degree,True);D,_=library(Xtest@L,degree);pred=np.linalg.solve(L.T,(D@z['coefficients']).T).T
    return receipt(transform=L,exponents=z['exponents'],whitened_coefficients=z['coefficients'],coefficient_conservation_residual=z['coefficient_conservation_residual'],heldout_rmse=float(np.sqrt(np.mean((pred-dXtest)**2))))


def kan_polynomial(checkpoint,train,test,degree,threshold):
    """Extract polynomial surrogate of a represented KAN scalar field, not governing dynamics."""
    from cognitum.mel import tensor_field as f
    from fractions import Fraction
    import itertools
    from hashlib import sha256
    X,T=map(design,(train,test));need(X.shape[1]==T.shape[1] and 2<=X.shape[1]<=3 and len(X)+len(T)<=96 and np.all((X>=0)&(X<=1)) and np.all((T>=0)&(T<=1)) and type(threshold) in (int,float) and 0<threshold<=1e4,'KAN sample budget')
    def sample(A):
        values=[]
        for row in A:
            q=f.make_request(checkpoint,f.pb.POINT,tuple(float(v) for v in row),derivative=(0,)*len(row));raw=f.execute(checkpoint,q);res=f.parse(raw,f.pb.Result,f.MAX_RESULT);values.append([float(Fraction(res.exact_value))])
        return np.array(values)
    need(type(degree) is int and 1<=degree<=4,'KAN degree');n=X.shape[1];ex=tuple(tuple(i.count(j) for j in range(n)) for d in range(degree+1) for i in itertools.combinations_with_replacement(range(n),d));D=np.column_stack([np.prod(X**p,axis=1) for p in ex]);E=np.column_stack([np.prod(T**p,axis=1) for p in ex]);Y,Z=sample(X),sample(T);B,c=fit(D,Y)
    for _ in range(16):
        mask=abs(B[:,0])>=threshold;old=B.copy();B[:]=0
        if mask.any():B[mask]=fit(D[:,mask],Y)[0]
        if np.array_equal(abs(B)>0,abs(old)>0):break
    return receipt(checkpoint_sha256=sha256(checkpoint).hexdigest(),exponents=ex,coefficients=B,condition=c,heldout_rmse=float(np.sqrt(np.mean((E@B-Z)**2))),represented_field_only=True)


def rolling_forecast(series,start,lags,season,alpha=.1,ridge=1e-4):
    """Expanding-window autoregression with fixed trend/season features and past-only intervals."""
    y=array(series,1);need(type(lags) is int and 1<=lags<=16 and type(season) is int and 2<=season<=64 and type(start) is int and max(lags,season)+32<=start<len(y)<=2048 and type(alpha) in (int,float) and .01<=alpha<=.5 and type(ridge) in (int,float) and 0<ridge<=1,'forecast budget');lag=max(lags,season);pred=[];lo=[];hi=[];res=[]
    def row(i):return np.r_[1,i/start,np.sin(2*np.pi*i/season),np.cos(2*np.pi*i/season),y[i-lags:i],y[i-season]]
    D=np.array([row(i) for i in range(lag,len(y))]);Y=y[lag:]
    for i in range(start,len(y)):
        X=D[:i-lag];z=Y[:i-lag];B=np.linalg.solve(X.T@X+ridge*np.eye(X.shape[1]),X.T@z);p=float(D[i-lag]@B);pred.append(p)
        # Past genuine one-step errors only. Missing early interval is explicit.
        if len(res)>=int(np.ceil(1/alpha))-1:
            k=int(np.ceil((len(res)+1)*(1-alpha)));d=float(np.sort(res)[k-1]);lo.append(p-d);hi.append(p+d)
        else:lo.append(np.nan);hi.append(np.nan)
        res.append(abs(y[i]-p))
    p=np.array(pred);truth=y[start:];l,h=np.array(lo),np.array(hi);available=np.isfinite(l);return receipt(predictions=p,lower=l,upper=h,actual=truth,rmse=float(np.sqrt(np.mean((p-truth)**2))),persistence_rmse=float(np.sqrt(np.mean((y[start-1:-1]-truth)**2))),seasonal_rmse=float(np.sqrt(np.mean((y[start-season:-season]-truth)**2))),empirical_coverage=float(np.mean((truth[available]>=l[available])&(truth[available]<=h[available]))) if available.any() else None,interval_count=int(available.sum()),coverage_guaranteed=False)


def calibrated_change(reference,calibration,monitor,alpha=.05,drift=.5,clip=4.):
    """Two-sided clipped CUSUM, split-calibrated max score over equal-length blocks.
    Rank guarantee is marginal under exchangeable null blocks conditional on reference.
    """
    ref=array(reference,1);C,M=map(design,(calibration,monitor));need(16<=len(ref)<=8192 and len(C)>=2 and C.shape[1]==M.shape[1] and 4<=C.shape[1]<=64 and type(alpha) in (int,float) and .001<=alpha<=.5 and type(drift) in (int,float) and 0<drift<clip and type(clip) in (int,float) and clip<=20,'calibration budget');sd=ref.std(ddof=1);need(sd>1e-8,'reference variance');mu=ref.mean()
    def scores(A):
        Z=np.clip((A-mu)/sd,-clip,clip);pos=np.zeros(len(A));neg=pos.copy();hist=[]
        for z in Z.T:pos=np.maximum(0,pos+z-drift);neg=np.maximum(0,neg-z-drift);hist.append(np.maximum(pos,neg))
        return np.array(hist).T
    S=scores(C).max(1);k=int(np.ceil((len(S)+1)*(1-alpha)));need(k<=len(S),'insufficient calibration blocks');threshold=float(np.sort(S)[k-1]);H=scores(M);hits=H>threshold;return receipt(threshold=threshold,alarms=hits.any(1),first_alarm=tuple(int(np.argmax(x)) if x.any() else None for x in hits),scores=H,calibration_count=len(S),nominal_marginal_false_alarm=alpha,assumption='exchangeable equal-length null blocks conditional on reference',repeated_monitoring_guaranteed=False)
