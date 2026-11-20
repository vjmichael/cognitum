"""CPU reference scientific learning, bounded simulation only."""
import numpy as np
from scipy.optimize import least_squares, minimize
from .ssm_stochastic import need, array, receipt


def bounded(x):
    need(np.isfinite(x).all() and np.max(abs(x))<=1e8,'state budget');return x


def grid(times):
    t=array(times,1);need(2<=len(t)<=257 and t[0]>=0 and t[-1]-t[0]<=32 and np.all((np.diff(t)>0)&(np.diff(t)<=1)),'time grid');return t


def rk4(f,x,h):
    k=f(x);l=f(x+h*k/2);m=f(x+h*l/2);n=f(x+h*m);return bounded(x+h*(k+2*l+2*m+n)/6)


def neural_ode(W,b,V,x0,times,substeps=4,initial_tangent=None):
    """Fixed hidden tanh features, trainable readout V; RK4 exact discrete tangent w.r.t. V and x0."""
    W,V=array(W,2),array(V,2);b,x=array(b,1),array(x0,1);t=grid(times);k,n=W.shape;p=n*k
    need(n<=8 and k<=8 and V.shape==(n,k) and b.shape==(k,) and x.shape==(n,) and type(substeps) is int and 1<=substeps<=32 and len(t)*substeps<=4096,'ODE shape/budget')
    S=np.zeros((n,p+n));S[:,p:]=np.eye(n)
    if initial_tangent is not None:
        S=array(initial_tangent,2);need(S.shape==(n,p+n),'initial tangent')
    def f(z):
        x=z[:n];J=z[n:].reshape(n,p+n);a=np.tanh(W@x+b);D=(V*(1-a*a))@W;G=np.zeros((n,p+n));G[:,:p]=np.kron(np.eye(n),a[None,:]);return np.r_[V@a,(D@J+G).ravel()]
    z=np.r_[x,S.ravel()];X=[x];J=[S]
    for h in np.diff(t):
        for _ in range(substeps):z=rk4(f,z,h/substeps)
        X.append(z[:n]);J.append(z[n:].reshape(n,p+n))
    return receipt(states=np.array(X),jacobian=np.array(J),method='RK4 discrete forward sensitivity')


def latent_fit(W,b,decoder,times,observed,initial_readout,initial_state,substeps=4):
    """Joint fit of readout and latent initial state with fixed linear observation decoder."""
    W=array(W,2);k,n=W.shape;V=array(initial_readout,2);x=array(initial_state,1);C=array(decoder,2);Y=array(observed,2);t=grid(times);need(n<=4 and k<=4 and V.shape==(n,k) and x.shape==(n,) and C.shape[1]==n and Y.shape==(len(t),len(C)) and C.shape[0]<=8 and len(t)<=65 and np.max(abs(np.r_[V.ravel(),x]))<10,'fit budget')
    def eval(z):
        r=neural_ode(W,b,z[:n*k].reshape(n,k),z[n*k:],t,substeps);return (r['states']@C.T-Y).ravel(),np.einsum('on,tnp->top',C,r['jacobian']).reshape(Y.size,-1)
    z=np.r_[V.ravel(),x];sol=least_squares(lambda z:eval(z)[0],z,jac=lambda z:eval(z)[1],bounds=(-10,10),max_nfev=100,ftol=1e-11,gtol=1e-11,xtol=1e-11);need(sol.success,'fit convergence');r,J=eval(sol.x);s=np.linalg.svd(J,compute_uv=False);need(len(s)==len(z) and s[-1]>1e-9*s[0],'local identifiability rank');return receipt(readout=sol.x[:n*k].reshape(n,k),initial_state=sol.x[n*k:],rmse=float(np.sqrt(np.mean(r*r))),local_condition=float(s[0]/s[-1]),global_optimum=False)


def cde(W,b,V,x0,times,controls,substeps=4):
    """Neural CDE on piecewise-linear control paths; output at observed knots only."""
    W,V=array(W,2),array(V,3);b,x=array(b,1),array(x0,1);t=grid(times);U=array(controls,2);k,n=W.shape;m=U.shape[1];need(n<=8 and k<=8 and m<=8 and V.shape==(n,m,k) and b.shape==(k,) and x.shape==(n,) and len(U)==len(t) and type(substeps) is int and 1<=substeps<=32 and len(t)*substeps<=4096,'CDE shape/budget');X=[x]
    for du in np.diff(U,axis=0):
        def f(z):return np.einsum('nmk,m,k->n',V,du,np.tanh(W@z+b))
        for _ in range(substeps):x=rk4(f,x,1/substeps)
        X.append(x)
    return receipt(states=np.array(X),knot_causal=True,interior_requires_next_knot=True)


def signature(controls):
    """Level-one and level-two piecewise-linear signature, all prefixes, Chen composition."""
    U=array(controls,2);m=U.shape[1];need(2<=len(U)<=512 and m<=8,'signature budget');a=np.zeros(m);B=np.zeros((m,m));A=[a.copy()];S=[B.copy()]
    for d in np.diff(U,axis=0):B=bounded(B+np.outer(a,d)+np.outer(d,d)/2);a=bounded(a+d);A.append(a.copy());S.append(B.copy())
    return receipt(level1=np.array(A),level2=np.array(S))


def neural_sde_fit(states,next_states,dt):
    """Scalar Euler Gaussian transition likelihood; fixed tanh feature, learned drift and log diffusion."""
    x,y=array(states,1),array(next_states,1);need(x.shape==y.shape and 64<=len(x)<=8192 and type(dt) in (int,float) and 0<dt<=.25,'transition data');D=np.column_stack((np.ones(len(x)),np.tanh(x)));s=np.linalg.svd(D,compute_uv=False);need(s[-1]>1e-8*s[0],'feature rank');d=y-x
    def loss(p):
        e=d-dt*(D@p[:2]);l=D@p[2:];iv=np.exp(-2*l)/dt;return float(np.mean(l+.5*e*e*iv)),np.r_[-dt*(D.T@(e*iv))/len(x),D.T@(1-e*e*iv)/len(x)]
    init=np.r_[np.clip(np.linalg.lstsq(D,d/dt,rcond=None)[0],-5,5),0.,0.];sol=minimize(loss,init,jac=True,bounds=[(-5,5)]*4,method='L-BFGS-B',options={'maxiter':200,'ftol':1e-12,'gtol':1e-9});need(sol.success,'likelihood convergence');return receipt(parameters=sol.x,negative_log_likelihood=float(loss(sol.x)[0]+.5*np.log(2*np.pi*dt)),discretized_likelihood=True)


def neural_sde(p,x0,dt,steps,paths,seed):
    p=array(p,1);need(p.shape==(4,) and np.max(abs(p))<=5 and type(x0) in (int,float) and np.isfinite(x0) and abs(x0)<=1e6 and type(dt) in (int,float) and 0<dt<=.25 and type(steps) is int and 1<=steps<=256 and type(paths) is int and 2<=paths<=8192 and paths*steps<=1048576 and type(seed) is int and 0<=seed<2**32,'SDE budget');rng=np.random.default_rng(seed);x=np.full(paths,float(x0));y=x.copy()
    def update(x,h,dw):a=np.tanh(x);return bounded(x+h*(p[0]+p[1]*a)+np.exp(p[2]+p[3]*a)*dw)
    for _ in range(steps):
        d=rng.standard_normal((2,paths))*np.sqrt(dt/2);x=update(x,dt,d.sum(0));y=update(update(y,dt/2,d[0]),dt/2,d[1])
    return receipt(coarse=x,fine=y,mean=float(y.mean()),variance=float(y.var()),coupled_rmse=float(np.sqrt(np.mean((x-y)**2))),seed=seed)


def physics_fit(q,p,dp):
    """Fit scalar spring, quartic conservative potential and nonnegative damping from momentum derivatives."""
    from scipy.optimize import nnls
    q,p,dp=[array(x,1) for x in (q,p,dp)];need(q.shape==p.shape==dp.shape and 3<=len(q)<=8192,'physics data');D=-np.column_stack((q,q**3,p));s=np.linalg.svd(D,compute_uv=False);need(s[-1]>1e-9*s[0],'physics rank');a,_=nnls(D,dp);return receipt(parameters=a,rmse=float(np.sqrt(np.mean((D@a-dp)**2))),energy_model='unit mass quartic potential and linear damping')


def physics_sim(parameters,q0,p0,dt,steps):
    """Strang damping / symplectic Verlet splitting; energy balance diagnostic, not exact conservation."""
    a=array(parameters,1);need(a.shape==(3,) and np.all(a>=0) and np.max(a)<=100 and type(dt) in (int,float) and 0<dt<=.25 and type(steps) is int and 1<=steps<=4096,'physics budget');q,p=array([q0,p0],1);k,g,d=a;X=[[q,p]];E=[p*p/2+k*q*q/2+g*q**4/4];work=0.;W=[work]
    for _ in range(steps):
        old=p;p*=np.exp(-d*dt/2);work+=(old*old-p*p)/2;p-=dt/2*(k*q+g*q**3);q+=dt*p;p-=dt/2*(k*q+g*q**3);old=p;p*=np.exp(-d*dt/2);work+=(old*old-p*p)/2;bounded(np.array([q,p]));X.append([q,p]);E.append(p*p/2+k*q*q/2+g*q**4/4);W.append(work)
    E,W=np.array(E),np.array(W);return receipt(states=np.array(X),energy=E,dissipated=W,balance_residual=float(np.max(abs(E+W-E[0]))))
