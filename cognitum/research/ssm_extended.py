"""Bounded scientific reference dynamics; never grants execution authority."""
import numpy as np
from scipy.linalg import eigh, expm, solve_continuous_lyapunov
from scipy.integrate import solve_ivp


def require(ok, message):
    if not ok: raise ValueError(message)


def arr(x, ndim):
    a=np.asarray(x)
    require(a.ndim==ndim and a.size>0 and a.size<=4096 and a.dtype.kind in 'iuf', 'numeric shape/budget')
    a=a.astype(float)
    require(np.isfinite(a).all() and np.max(np.abs(a))<=1e6,'numeric budget')
    return a


def square(x):
    a=arr(x,2); require(a.shape[0]==a.shape[1] and len(a)<=32,'square matrix budget');return a


def grid(h,steps):
    require(type(steps) is int and 1<=steps<=512 and type(h) in (int,float) and 0<h<=1 and h*steps<=32,'time budget')
    return np.arange(steps+1)*h


def result(**kw):
    return dict(**kw,certified=False,execution_authorized=False)


def constrained(E,A,x0,h,steps):
    """Semi-explicit index-1 DAE: E=diag(I,0), eliminate algebraic block."""
    E,A=square(E),square(A);x=arr(x0,1);t=grid(h,steps);n=len(E)
    require(A.shape==E.shape and x.shape==(n,),'DAE shape');r=int(np.trace(E))
    require(0<r<n and np.array_equal(E,np.diag([1.]*r+[0.]*(n-r))),'semi-explicit index-1 form required')
    G=A[r:,r:];require(np.linalg.cond(G)<=1e8,'algebraic block singular/ill-conditioned')
    C=-np.linalg.solve(G,A[r:,:r]);require(np.max(np.abs(x[r:]-C@x[:r]))<=1e-9,'inconsistent initial condition')
    F=A[:r,:r]+A[:r,r:]@C;Y=np.array([expm(F*u)@x[:r] for u in t]);X=np.column_stack((Y,Y@C.T))
    require(np.isfinite(X).all() and np.max(np.abs(X))<=1e8,'trajectory budget')
    residual=float(np.max(np.abs(X@A[r:,:].T)));require(residual<=1e-8*max(1.,np.max(np.abs(X))*np.max(np.abs(A))),'algebraic residual')
    return result(times=t,states=X,algebraic_residual=residual)


def hybrid(modes,guards,x0,h,steps):
    """Ordered linear modes with affine guards and resets; no cyclic switching."""
    t=grid(h,steps);x=arr(x0,1);n=len(x)
    require(type(modes) in (tuple,list) and 1<=len(modes)<=8 and len(guards)==len(modes)-1,'mode budget')
    mats=[square(A) for A in modes];require(all(A.shape==(n,n) for A in mats),'mode shape')
    parsed=[]
    for l,b,d,R,c in guards:
        l,R,c=arr(l,1),square(R),arr(c,1)
        require(l.shape==c.shape==(n,) and R.shape==(n,n) and np.any(l) and type(d) is int and d in (-1,1) and type(b) in (int,float) and np.isfinite(b),'guard shape')
        parsed.append((l,b,d,R,c))
    def run(maxstep,rtol):
        now=0.;z=x.copy();events=[];segments=[];calls=0
        for j,A in enumerate(mats):
            def f(_,y):
                nonlocal calls
                calls+=1;require(calls<=50000 and np.isfinite(y).all() and np.max(np.abs(y))<=1e8,'hybrid budget');return A@y
            ev=None
            if j<len(parsed):
                l,b,d,R,c=parsed[j];require(d*(l@z-b)<-1e-10,'guard must start on incoming side')
                def ev(_,y):return l@y-b
                ev.direction=d;ev.terminal=True
            sol=solve_ivp(f,(now,t[-1]),z,events=ev,dense_output=True,rtol=rtol,atol=rtol/100,max_step=maxstep)
            require(sol.success,'hybrid solver failure');end=float(sol.t[-1]);segments.append((now,end,sol.sol))
            if ev is None or not len(sol.t_events[0]):break
            before=sol.y_events[0][0];z=R@before+c;require(np.isfinite(z).all() and np.max(np.abs(z))<=1e8,'reset budget');events.append((end,j,before.copy(),z.copy()));now=end
            if now>=t[-1]:break
        Y=np.array([segments[max(i for i,(a,b,_) in enumerate(segments) if a<=u)][2](u) for u in t]);
        if events and events[-1][0]==t[-1]:Y[-1]=events[-1][3]
        return Y,events
    X,e=run(h,1e-9);Y,f=run(h/2,1e-11)
    require(len(e)==len(f) and all(abs(a[0]-b[0])<=2e-7 and np.allclose(a[2],b[2],rtol=2e-7,atol=2e-9) and np.allclose(a[3],b[3],rtol=2e-7,atol=2e-9) for a,b in zip(e,f)),'guard refinement disagreement')
    # Grid samples near a reset can land on opposite sides under roundoff.
    keep=np.array([all(abs(u-v[0])>2e-7 for v in f) for u in t]);err=float(np.max(np.abs(X[keep]-Y[keep]),initial=0))
    require(err<=2e-7*max(1.,np.max(np.abs(Y))) and np.isfinite(Y).all(),'hybrid trajectory disagreement')
    return result(times=t,states=Y,events=f,event_completeness_certified=False,refinement_error=err)


def delay(A,B,history,tau,steps_per_delay,intervals):
    """Constant-history retarded linear DDE, method of steps, dense past solution."""
    A,B=square(A),square(B);x=arr(history,1);n=len(A)
    require(B.shape==A.shape and x.shape==(n,) and type(tau) in (int,float) and 0<tau<=1 and type(steps_per_delay) is int and 2<=steps_per_delay<=64 and type(intervals) is int and 1<=intervals<=8,'delay shape/budget')
    t=np.linspace(0,tau*intervals,intervals*steps_per_delay+1)
    def run(div,rtol):
        past=[];z=x.copy();calls=0
        for j in range(intervals):
            start=j*tau;end=(j+1)*tau
            def f(u,y):
                nonlocal calls
                calls+=1;require(calls<=50000 and np.isfinite(y).all() and np.max(np.abs(y))<=1e8,'delay budget');old=x if j==0 else past[j-1](np.clip(u-tau,(j-1)*tau,j*tau));return A@y+B@old
            sol=solve_ivp(f,(start,end),z,dense_output=True,rtol=rtol,atol=rtol/100,max_step=tau/div);require(sol.success,'delay solver failure');past.append(sol.sol);z=sol.y[:,-1]
        return np.array([past[min(int(u/tau),intervals-1)](u) for u in t])
    X=run(steps_per_delay,1e-9);Y=run(2*steps_per_delay,1e-11);err=float(np.max(np.abs(X-Y)))
    require(np.isfinite(Y).all() and err<=2e-7*max(1.,np.max(np.abs(Y))),'delay refinement disagreement')
    return result(times=t,states=Y,refinement_error=err)


def weak_evolution(M,K,x0,h,steps,velocity=None):
    """Mass/stiffness pair from weak-form assembly; diffusion or wave modal evolution."""
    M,K=square(M),square(K);x=arr(x0,1);t=grid(h,steps);n=len(M)
    require(K.shape==M.shape and x.shape==(n,) and np.allclose(M,M.T,rtol=0,atol=1e-12) and np.allclose(K,K.T,rtol=0,atol=1e-12),'weak form shape/symmetry')
    require(np.linalg.eigvalsh(M)[0]>0 and np.linalg.cond(M)<=1e8,'mass positive/condition')
    lam,V=eigh(K,M);require(lam[0]>=-1e-10*max(1.,abs(lam[-1])),'stiffness not PSD');lam=np.maximum(lam,0);a=V.T@M@x
    if velocity is None:
        X=(np.exp(-t[:,None]*lam)*a)@V.T;energy=np.einsum('ti,ij,tj->t',X,M,X)/2
        ref=np.array([expm(-np.linalg.solve(M,K)*u)@x for u in t])
    else:
        v=arr(velocity,1);require(v.shape==(n,),'velocity shape');b=V.T@M@v;w=np.sqrt(lam);phase=t[:,None]*w;C=np.cos(phase);S=t[:,None]*np.sinc(phase/np.pi);X=(C*a+S*b)@V.T;U=(-np.sin(phase)*w*a+C*b)@V.T;energy=(np.einsum('ti,ij,tj->t',X,K,X)+np.einsum('ti,ij,tj->t',U,M,U))/2
        F=np.block([[np.zeros_like(M),np.eye(n)],[-np.linalg.solve(M,K),np.zeros_like(M)]]);ref=np.array([(expm(F*u)@np.r_[x,v])[:n] for u in t])
    err=float(np.max(np.abs(X-ref)));require(np.isfinite(X).all() and np.isfinite(energy).all() and np.max(np.abs(X))<=1e8 and err<=2e-7*max(1.,np.max(np.abs(X))),'modal/expm disagreement')
    return result(times=t,states=X,energy=energy,eigenvalues=lam,reference_error=err)


def pod(A,snapshots,rank,x0,h,steps):
    """Euclidean POD/Galerkin reduction; errors against original, not certified bounds."""
    A=square(A);S=arr(snapshots,2);x=arr(x0,1);t=grid(h,steps);n=len(A)
    require(S.shape[0]==n and x.shape==(n,) and type(rank) is int and 1<=rank<=min(S.shape),'POD shape/rank')
    U,s,_=np.linalg.svd(S,full_matrices=False);require(s[rank-1]>1e-12*s[0] and s[0]>0,'numerical rank');V=U[:,:rank];F=V.T@A@V
    X=np.array([V@expm(F*u)@(V.T@x) for u in t]);Y=np.array([expm(A*u)@x for u in t]);require(np.isfinite(X).all() and np.isfinite(Y).all() and max(np.max(np.abs(X)),np.max(np.abs(Y)))<=1e8,'POD trajectory budget')
    return result(times=t,states=X,basis=V,reduced=F,snapshot_error=float(np.linalg.norm(S-V@(V.T@S))),trajectory_error=float(np.max(np.linalg.norm(X-Y,axis=1))),discarded_energy=float(np.sum(s[rank:]**2)))


def network(W,x0,h,steps,partition):
    """Symmetric weighted diffusion graph; exact block decomposition of RHS."""
    W=square(W);x=arr(x0,1);t=grid(h,steps);n=len(W)
    require(x.shape==(n,) and np.array_equal(W,W.T) and np.all(W>=0) and np.all(np.diag(W)==0) and np.all(x>=0),'graph shape/weights/state')
    require(type(partition) in (tuple,list) and len(partition)>0 and all(type(g) in (tuple,list) and len(g)>0 for g in partition),'partition shape');idx=[i for g in partition for i in g];require(all(type(i) is int for i in idx) and sorted(idx)==list(range(n)),'partition coverage')
    L=np.diag(W.sum(axis=1))-W;X=np.array([expm(-L*u)@x for u in t]);calls=0
    def rhs(_,y):
        nonlocal calls
        calls+=1;require(calls<=50000 and np.isfinite(y).all() and np.max(np.abs(y))<=1e8,'network solver budget')
        z=np.zeros(n)
        for g in partition:
            i=list(g);z[i]=W[i,:]@y-W[i,:].sum(axis=1)*y[i]
        return z
    sol=solve_ivp(rhs,(0,t[-1]),x,t_eval=t,rtol=1e-10,atol=1e-12,max_step=h);require(sol.success,'partition solver failure');err=float(np.max(np.abs(X-sol.y.T)));require(np.isfinite(X).all() and err<=2e-7*max(1.,np.max(X)),'partition disagreement')
    return result(times=t,states=X,laplacian=L,mass_error=float(np.max(np.abs(X.sum(axis=1)-x.sum()))),partition_error=err)


def kan_evolution(checkpoints,x0,h,steps,velocity=None):
    """Reuse COG-04P exact assembly; refuse space-time bases for spatial evolution."""
    from . import kan_weak_form as p
    import json
    from hashlib import sha256
    raw,M,K=p.matrices(checkpoints);r=json.loads(raw)
    require('t' not in r['axes'],'spatial-only basis required')
    out=weak_evolution(M,K,x0,h,steps,velocity)
    out.update(assembly_sha256=sha256(raw).hexdigest(),physical_pde_solution=False)
    return out


def balanced_reduction(A,B,C,rank):
    """Stable minimal continuous LTI, square-root balanced truncation.

    The classical discarded-HSV bound is evaluated numerically, not certified.
    """
    A=square(A);B=arr(B,2);C=arr(C,2);n=len(A)
    require(B.shape[0]==n and C.shape[1]==n and type(rank) is int and 1<=rank<n,'balanced shape/rank')
    require(np.max(np.linalg.eigvals(A).real)<-1e-8,'strict stability required')
    P=solve_continuous_lyapunov(A,-B@B.T);Q=solve_continuous_lyapunov(A.T,-C.T@C)
    P=(P+P.T)/2;Q=(Q+Q.T)/2
    require(np.linalg.eigvalsh(P)[0]>1e-12 and np.linalg.eigvalsh(Q)[0]>1e-12 and max(np.linalg.cond(P),np.linalg.cond(Q))<=1e8,'minimal well-conditioned Gramian required')
    def rel(R,S):return np.linalg.norm(R)/max(1.,np.linalg.norm(S))
    err=max(rel(A@P+P@A.T+B@B.T,B@B.T),rel(A.T@Q+Q@A+C.T@C,C.T@C));require(err<=1e-8,'Lyapunov residual')
    R=np.linalg.cholesky(P);L=np.linalg.cholesky(Q);U,h,Vh=np.linalg.svd(L.T@R)
    require(h[rank-1]-h[rank]>1e-10*h[0],'ambiguous truncation boundary')
    T=R@Vh[:rank].T/np.sqrt(h[:rank]);W=(U[:,:rank].T@L.T)/np.sqrt(h[:rank])[:,None]
    Ar=W@A@T;Br=W@B;Cr=C@T
    require(np.allclose(W@T,np.eye(rank),rtol=1e-8,atol=1e-8) and np.max(np.linalg.eigvals(Ar).real)<-1e-8,'reduced stability/projection')
    return result(A=Ar,B=Br,C=Cr,hankel_values=h,estimated_hinf_bound=float(2*sum(h[rank:])),gramian_residual=float(err))
