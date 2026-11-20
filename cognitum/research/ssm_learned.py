"""CPU reference learned SSM mathematics; bounded, no execution authority."""
import numpy as np
from numpy.polynomial.legendre import leggauss, legvander
from scipy.optimize import least_squares
from .ssm_stochastic import need, array, receipt


def numeric(x,dim):
    a=np.asarray(x);need(a.ndim==dim and 0<a.size<=262144 and a.dtype.kind in 'iufc','array budget/type');a=a.astype(complex if a.dtype.kind=='c' else float);need(np.isfinite(a).all() and np.max(abs(a))<=1e8,'finite magnitude');return a


def bounded(a):
    need(np.isfinite(a).all() and np.max(abs(a))<=1e8,'state budget');return a


def hippo(values,durations,order):
    """LegS projection of piecewise constant history, irregular intervals; quadrature exact in polynomial arithmetic."""
    u=array(values,1);dt=array(durations,1);need(u.shape==dt.shape and np.all(dt>0) and len(u)<=512 and type(order) is int and 1<=order<=16,'projection budget');q,w=leggauss(order+1);z=(q+1)/2;w=w/2;scale=np.sqrt(2*np.arange(order)+1);V=legvander(q,order-1)*scale;c=np.zeros(order);time=energy=0.;C=[];error=[]
    for v,h in zip(u,dt):
        new=time+h;r=time/new;old=legvander(2*r*z-1,order-1)*scale;tail=legvander(2*(r+(1-r)*z)-1,order-1)*scale;c=bounded(r*(old.T*w)@V@c+(1-r)*v*(tail.T@w));energy+=h*v*v;time=new;err=energy/time-c@c;need(err>=-1e-9*max(1,energy/time),'projection energy drift');C.append(c);error.append(max(0.,err))
    return receipt(coefficients=np.array(C),mean_square_truncation=np.array(error),duration=float(time))


def legs(order):
    need(type(order) is int and 1<=order<=16,'LegS order');s=np.sqrt(2*np.arange(order)+1);A=-np.tril(np.outer(s,s),-1)-np.diag(np.arange(1,order+1));B=s[:,None];p=s/np.sqrt(2);N=A+np.outer(p,p);w,V=np.linalg.eigh((N+.5*np.eye(order))/1j);lam=-.5+1j*w;q=V.conj().T@p;return receipt(A=A,B=B,eigenbasis=V,diagonal=lam,low_rank=q)


def s4_discretize(order,dt):
    """LegS NPLR/DPLR bilinear reference, rank-one Woodbury solve in normal basis."""
    need(type(dt) in (int,float) and 0<dt<=2,'step');r=legs(order);V,l,q,A,B=(r[k] for k in ('eigenbasis','diagonal','low_rank','A','B'));M=np.diag(l)-np.outer(q,q.conj());d=1/(1-dt*l/2);v=d*q;den=1+dt/2*(q.conj()@v);need(abs(den)>1e-12,'Woodbury singular');inv=np.diag(d)-dt/2*np.outer(v,q.conj()*d)/den;F=V@inv@(np.eye(order)+dt*M/2)@V.conj().T;G=V@inv@V.conj().T@B*dt;need(max(np.max(abs(F.imag)),np.max(abs(G.imag)))<1e-10,'conjugacy');F,G=F.real,G.real;need(np.max(abs(F-np.linalg.solve(np.eye(order)-dt*A/2,np.eye(order)+dt*A/2)))<1e-10,'dense residual');return receipt(F=F,G=G)


def recurrence(F,G,C,U,h0):
    F,G,C,U,h=map(lambda p:numeric(*p),((F,2),(G,2),(C,2),(U,2),(h0,1)));n=len(F);need(n<=16 and F.shape==(n,n) and G.shape[0]==n and C.shape[1]==n and U.shape[1]==G.shape[1] and h.shape==(n,) and len(U)<=512 and G.shape[1]<=16 and C.shape[0]<=16,'recurrence shape');X=[]
    for u in U:h=bounded(F@h+G@u);X.append(h)
    X=np.array(X);return receipt(states=X,outputs=bounded(X@C.T),final_state=h)


def convolution(F,G,C,U,h0):
    F,G,C,U,h=map(lambda p:numeric(*p),((F,2),(G,2),(C,2),(U,2),(h0,1)));n=len(F);need(n<=16 and F.shape==(n,n) and G.shape[0]==n and C.shape[1]==n and U.shape[1]==G.shape[1] and h.shape==(n,) and len(U)<=512 and G.shape[1]<=16 and C.shape[0]<=16,'convolution shape');K=[];initial=[];M=G.copy()
    for _ in U:K.append(C@M);M=bounded(F@M);h=bounded(F@h);initial.append(C@h)
    Y=np.array(initial,dtype=np.result_type(F,G,C,U,h));K=np.array(K)
    for i in range(C.shape[0]):
        for j in range(G.shape[1]):Y[:,i]+=np.convolve(U[:,j],K[:,i,j])[:len(U)]
    return receipt(outputs=bounded(Y),kernel=K)


def diag_steps(rates,B,C,U,h0,dt,scan=False):
    """Stable complex diagonal exact ZOH; S4D/S5-style MIMO reference."""
    a=numeric(rates,1);B,C,U,h=map(lambda p:numeric(*p),((B,2),(C,2),(U,2),(h0,1)));d=array(dt,1);n=len(a);need(n<=16 and np.all(a.real<0) and np.all(a.real>=-100) and np.all(abs(a.imag)<=100) and B.shape[0]==n and C.shape[1]==n and h.shape==(n,) and U.shape[1]==B.shape[1] and d.shape==(len(U),) and len(U)<=512 and np.all((d>0)&(d<=2)) and B.shape[1]<=16 and C.shape[0]<=16,'diagonal shape/stability');F=np.exp(d[:,None]*a);G=np.expm1(d[:,None]*a)/a*(U@B.T);X=affine_scan(F,G,h) if scan else serial(F,G,h);return receipt(states=X,outputs=bounded(X@C.T),final_state=X[-1])


def serial(F,G,h):
    X=[]
    for a,b in zip(F,G):h=bounded(a*h+b);X.append(h)
    return np.array(X)


def affine_scan(F,G,h):
    """Inclusive parallel-doubling affine composition, independent of recurrence order."""
    A=numeric(F,2).copy();B=numeric(G,2).copy();h=numeric(h,1);need(A.shape==B.shape and h.shape==(A.shape[1],) and len(A)<=512 and A.shape[1]<=16,'scan shape');stride=1
    while stride<len(A):
        a=A.copy();b=B.copy();A[stride:]=a[stride:]*a[:-stride];B[stride:]=b[stride:]+a[stride:]*b[:-stride];bounded(A);bounded(B);stride*=2
    return bounded(A*h+B)


def selective(U,kernel,rates,delta_w,delta_bias,B,C,h0,scan=False):
    """Single-input selective SSM reference: causal convolution, input-dependent delta/B/C, exact ZOH."""
    u=array(U,1);k=array(kernel,1);a=array(rates,1);b=array(B,2);c=array(C,2);h=array(h0,1);n=len(a);need(len(u)<=512 and len(k)<=16 and n<=16 and np.all((a<0)&(a>=-100)) and b.shape==c.shape==(n,2) and h.shape==(n,) and all(type(v) in (int,float) and np.isfinite(v) and abs(v)<=100 for v in (delta_w,delta_bias)),'selective profile');v=bounded(np.convolve(u,k)[:len(u)]);d=np.logaddexp(0,delta_w*v+delta_bias);need(np.all((d>0)&(d<=2)),'delta budget');Bv=b[:,0]+v[:,None]*b[:,1];Cv=c[:,0]+v[:,None]*c[:,1];F=np.exp(d[:,None]*a);G=np.expm1(d[:,None]*a)/a*Bv*v[:,None];X=affine_scan(F,G,h) if scan else serial(F,G,h);return receipt(states=X,outputs=bounded(np.sum(Cv*X,axis=1)),delta=d,final_state=X[-1])


def diagonal_fit(U,Y,Utest,Ytest,initial):
    """Learn real discrete stable poles and readout, analytic recurrence Jacobian; zero initial state."""
    u,y,v,t=(array(a,1) for a in (U,Y,Utest,Ytest));p=array(initial,1);n=len(p);need(len(u)==len(y) and len(v)==len(t) and 16<=len(u)<=512 and len(v)<=512 and 1<=n<=4 and np.all((p>.001)&(p<.999)),'learning profile')
    def features(u,p):
        x=np.zeros(n);d=x.copy();X=[];D=[]
        for a in u:d=x+p*d;x=p*x+a;X.append(x);D.append(d)
        return np.array(X),np.array(D)
    def pred(z,u):X,D=features(u,z[:n]);return X@z[n:],np.column_stack((D*z[n:],X))
    X,_=features(u,p);w=np.linalg.lstsq(X,y,rcond=None)[0];need(np.max(abs(w))<100,'initial readout budget');z=np.r_[p,w];lo=np.r_[np.full(n,.001),np.full(n,-100.)];hi=np.r_[np.full(n,.999),np.full(n,100.)];sol=least_squares(lambda z:pred(z,u)[0]-y,z,jac=lambda z:pred(z,u)[1],bounds=(lo,hi),max_nfev=200,ftol=1e-12,xtol=1e-12,gtol=1e-12);need(sol.success,'learning convergence');q=sol.x;P,J=pred(q,u);Z,_=pred(q,v);eps=1e-6;fd=np.column_stack([(pred(q+eps*np.eye(2*n)[i],u)[0]-pred(q-eps*np.eye(2*n)[i],u)[0])/(2*eps) for i in range(2*n)]);return receipt(poles=q[:n],readout=q[n:],training_rmse=float(np.sqrt(np.mean((P-y)**2))),heldout_rmse=float(np.sqrt(np.mean((Z-t)**2))),gradient_error=float(np.max(abs(J-fd))),global_optimum=False)


def fit_readout(train_states,targets,test_states,test_targets):
    """Train readout on fixed structured state features; independent supplied holdout."""
    X,y,T,z=map(lambda p:numeric(*p),((train_states,2),(targets,2),(test_states,2),(test_targets,2)));need(X.shape[1]==T.shape[1] and len(y)==len(X) and len(z)==len(T) and y.shape[1]==z.shape[1] and len(X)<=512 and len(T)<=512 and X.shape[1]<=16,'readout shape');s=np.linalg.svd(X,compute_uv=False);need(len(s)==X.shape[1] and s[-1]>1e-10*s[0],'readout rank');C=np.linalg.lstsq(X,y,rcond=None)[0];return receipt(readout=C.T,training_rmse=float(np.sqrt(np.mean(abs(X@C-y)**2))),heldout_rmse=float(np.sqrt(np.mean(abs(T@C-z)**2))))
