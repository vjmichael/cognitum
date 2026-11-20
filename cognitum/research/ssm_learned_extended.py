"""Bounded CPU reference sequence models; no production execution authority."""
import numpy as np
from scipy.optimize import least_squares
from .ssm_stochastic import need, array, receipt
from .ssm_learned import numeric, bounded, affine_scan, serial, s4_discretize, recurrence


def scan_jvp(F,G,h,dF,dG,dh):
    """Differentiate inclusive affine scan by the product rule, real or complex."""
    A,B,h,P,Q,dh=[numeric(x,d) for x,d in ((F,2),(G,2),(h,1),(dF,2),(dG,2),(dh,1))]
    need(A.shape==B.shape==P.shape==Q.shape and h.shape==dh.shape==(A.shape[1],) and len(A)<=512 and A.shape[1]<=16,'JVP shape')
    dtype=np.result_type(A,B,h,P,Q,dh);A,B,P,Q=(x.astype(dtype) for x in (A,B,P,Q));k=1
    while k<len(A):
        a,b,p,q=(x.copy() for x in (A,B,P,Q))
        A[k:]=a[k:]*a[:-k];B[k:]=b[k:]+a[k:]*b[:-k]
        P[k:]=p[k:]*a[:-k]+a[k:]*p[:-k];Q[k:]=q[k:]+p[k:]*b[:-k]+a[k:]*q[:-k]
        for x in (A,B,P,Q):bounded(x)
        k*=2
    return receipt(states=bounded(A*h+B),tangent=bounded(P*h+A*dh+Q))


def mamba1(U,kernel,log_rates,delta_weights,B,C,h0,skip=0.,gate=None,scan=True):
    """Single-channel Mamba-1-style reference: exponential Euler input, SiLU gate."""
    u,k,a,d,h=[array(x,1) for x in (U,kernel,log_rates,delta_weights,h0)];b,c=array(B,2),array(C,2);n=len(a)
    need(len(u)<=512 and len(k)<=16 and n<=16 and d.shape==(2,) and h.shape==(n,) and b.shape==c.shape==(n,2) and np.all(abs(a)<=8) and type(skip) in (int,float) and np.isfinite(skip) and abs(skip)<=100,'selective input')
    v=bounded(np.convolve(u,k)[:len(u)]);v=v*np.exp(-np.logaddexp(0,-v));dt=np.logaddexp(0,d[0]+d[1]*v);need(np.all((dt>0)&(dt<=2)),'delta budget')
    a=-np.exp(a);bv=b[:,0]+v[:,None]*b[:,1];cv=c[:,0]+v[:,None]*c[:,1];F=np.exp(dt[:,None]*a);G=dt[:,None]*bv*v[:,None];X=affine_scan(F,G,h) if scan else serial(F,G,h);y=np.sum(cv*X,1)+skip*v
    if gate is not None:
        z=array(gate,1);need(z.shape==u.shape,'gate shape');y*=z*np.exp(-np.logaddexp(0,-z))
    return receipt(states=X,outputs=bounded(y),delta=dt,final_state=X[-1])


def selective_fit(U,Y,Utest,Ytest,initial):
    """Learn one selective decay rate, step slope and readout; fixed B=1, bias=-1."""
    u,y,v,z=[array(x,1) for x in (U,Y,Utest,Ytest)];p=array(initial,1);need(u.shape==y.shape and v.shape==z.shape and 16<=len(u)<=256 and len(v)<=256 and p.shape==(3,) and np.all(abs(p)<2),'fit budget')
    def evaluate(p,u):
        s=u*np.exp(-np.logaddexp(0,-u));d=np.logaddexp(0,-1+p[1]*s);a=-np.exp(p[0]);F=np.exp(d*a)[:,None];G=(d*s)[:,None];zero=np.zeros(1);X=affine_scan(F,G,zero)[:,0];dd=s*np.exp(-np.logaddexp(0,1-p[1]*s));J=[]
        for df,dg in ((F*d[:,None]*a,np.zeros_like(G)),(F*a*dd[:,None],(dd*s)[:,None])):
            J.append(p[2]*scan_jvp(F,G,zero,df,dg,zero)['tangent'][:,0])
        return p[2]*X,np.column_stack((*J,X))
    ans=least_squares(lambda p:evaluate(p,u)[0]-y,p,jac=lambda p:evaluate(p,u)[1],bounds=(-2,2),max_nfev=150,ftol=1e-12,xtol=1e-12,gtol=1e-12);need(ans.success,'fit convergence');p=ans.x;pred,J=evaluate(p,u);fd=np.column_stack([(evaluate(p+1e-6*q,u)[0]-evaluate(p-1e-6*q,u)[0])/2e-6 for q in np.eye(3)])
    return receipt(parameters=p,training_rmse=float(np.sqrt(np.mean((pred-y)**2))),heldout_rmse=float(np.sqrt(np.mean((evaluate(p,v)[0]-z)**2))),gradient_error=float(np.max(abs(J-fd))),global_optimum=False)


def structured_fit(U,Y,Utest,Ytest,order,initial_step):
    """Fit LegS bilinear step and real readout; fixed continuous generator."""
    u,y,v,z=[array(x,1) for x in (U,Y,Utest,Ytest)];need(u.shape==y.shape and v.shape==z.shape and 16<=len(u)<=256 and len(v)<=256 and type(order) is int and 1<=order<=4 and .01<initial_step<1,'fit budget')
    def features(step,x):
        r=s4_discretize(order,float(step));return recurrence(r['F'],r['G'],np.eye(order),x[:,None],np.zeros(order))['states']
    def evaluate(p,x):return features(p[0],x)@p[1:]
    w=np.linalg.lstsq(features(initial_step,u),y,rcond=None)[0];need(np.max(abs(w))<100,'readout budget');ans=least_squares(lambda p:evaluate(p,u)-y,np.r_[initial_step,w],bounds=(np.r_[.01,np.full(order,-100.)],np.r_[1.,np.full(order,100.)]),max_nfev=150,ftol=1e-12,xtol=1e-12,gtol=1e-12);need(ans.success,'fit convergence');p=ans.x
    return receipt(step=float(p[0]),readout=p[1:],training_rmse=float(np.sqrt(np.mean((evaluate(p,u)-y)**2))),heldout_rmse=float(np.sqrt(np.mean((evaluate(p,v)-z)**2))),global_optimum=False)


def ssd(decay,B,C,U,H0,block=8):
    """Scalar transition shared across matrix state, SSD dense and chunked paths."""
    a=array(decay,1);b,c,u,h=[array(x,2) for x in (B,C,U,H0)];T=len(a);n=b.shape[1];d=u.shape[1]
    need(T<=256 and 1<=n<=16 and 1<=d<=16 and b.shape==c.shape==(T,n) and u.shape==(T,d) and h.shape==(n,d) and np.all((a>=0)&(a<=1)) and type(block) is int and 1<=block<=256,'SSD shape')
    def mask(a):
        L=np.zeros((len(a),len(a)))
        for t in range(len(a)):
            L[t,t]=1
            for j in range(t-1,-1,-1):L[t,j]=L[t,j+1]*a[j+1]
        return L
    L=mask(a);dense=(L*(c@b.T))@u+np.cumprod(a)[:,None]*(c@h);H=h.copy();ys=[];Y=[];Hserial=h.copy()
    for j in range(0,T,block):
        v=a[j:j+block];bb=b[j:j+block];cc=c[j:j+block];uu=u[j:j+block];M=mask(v);p=np.cumprod(v);ys.append((M*(cc@bb.T))@uu+p[:,None]*(cc@H));H=bounded(p[-1]*H+bb.T@(M[-1,:,None]*uu))
    for t in range(T):Hserial=bounded(a[t]*Hserial+np.outer(b[t],u[t]));Y.append(c[t]@Hserial)
    return receipt(dense=bounded(dense),chunked=bounded(np.vstack(ys)),serial=bounded(np.array(Y)),final_state=H,serial_final=Hserial)


def rotary_mimo(rates,dt,mix,B,C,U,h0,previous):
    """Complex diagonal exponential-trapezoid recurrence with explicit prior injection."""
    a=numeric(rates,1);d=array(dt,1);l=array(mix,1);b,c,u,h,p=[numeric(x,k) for x,k in ((B,3),(C,3),(U,2),(h0,1),(previous,1))];T=len(d);n=len(a)
    need(T<=512 and n<=16 and np.all((a.real<=0)&(a.real>=-100)) and np.all(abs(a.imag)<=100) and l.shape==d.shape and np.all((d>0)&(d<=2)) and np.all((l>=0)&(l<=1)) and u.shape[0]==T and u.shape[1]<=16 and b.shape==(T,n,u.shape[1]) and c.shape[0]==T and c.shape[1]<=16 and c.shape[2]==n and h.shape==p.shape==(n,),'rotary shape')
    F=np.exp(d[:,None]*a);v=np.einsum('tnm,tm->tn',b,u);prev=np.vstack((p,v[:-1]));G=d[:,None]*(l[:,None]*v+(1-l[:,None])*F*prev);X=affine_scan(F,G,h);Y=np.einsum('ton,tn->to',c,X)
    return receipt(states=X,outputs=bounded(Y),final_state=X[-1],previous_injection=v[-1])


def memory_trial(seed,train_count=128,test_count=128):
    """Synthetic parity: train scalar readout on fixed rotary vs positive decay and last-token features."""
    need(type(seed) is int and 0<=seed<2**32 and type(train_count) is int and type(test_count) is int and 32<=train_count<=256 and 32<=test_count<=256,'trial budget');rng=np.random.default_rng(seed)
    def features(n,length):
        u=rng.integers(0,2,(n,length));target=(-1.)**u.sum(1);rot=np.prod(np.exp(1j*np.pi*u),1).real;dec=np.prod(np.exp(-.1*u),1);last=u[:,-1];return [np.column_stack((np.ones(n),v)) for v in (rot,dec,last)],target
    X,y=features(train_count,12);T,z=features(test_count,24);metrics={}
    for name,D,E in zip(('rotation','positive_decay','last_token'),X,T):
        w=np.linalg.lstsq(D,y,rcond=None)[0];p=E@w;metrics[name]={'rmse':float(np.sqrt(np.mean((p-z)**2))),'accuracy':float(np.mean(np.where(p>=0,1,-1)==z))}
    return receipt(metrics=metrics,train_length=12,test_length=24,hand_designed_features=True)
