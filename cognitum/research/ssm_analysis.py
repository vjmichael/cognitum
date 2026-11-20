"""Bounded exact linear analysis and numerical Riccati diagnostics. No control execution."""
from fractions import Fraction as Q
from . import ssm_linear as s, ssm_foundations as f

mm=s._matmul
add=s._add
sub=f.sub
tr=f.transpose


def _model(m):
    s.need(type(m) is s.Model,'typed model');return len(m.a)


def _q(x):
    s.need(type(x) in (int,Q),'exact rational required');return s.bounded(Q(x))


def _zeros(n,m):return tuple((Q(0),)*m for _ in range(n))


def _horizon(k):s.need(type(k) is int and 1<=k<=s.STEPS,'horizon budget');return k


def reach_matrix(m,k=None):
    n=_model(m);k=n if k is None else _horizon(k);blocks=[];b=m.b
    for i in range(k):
        blocks.append(b)
        if i+1<k:b=mm(m.a,b)
    return tuple(tuple(x for blk in blocks for x in blk[i]) for i in range(n))


def observe_matrix(m,k=None):
    n=_model(m);k=n if k is None else _horizon(k);blocks=[];c=m.c
    for i in range(k):
        blocks.extend(c)
        if i+1<k:c=mm(c,m.a)
    return tuple(blocks)


def ranks(m):
    n=_model(m);r=len(f.pivots(reach_matrix(m)));o=len(f.pivots(observe_matrix(m)))
    return dict(controllable=r==n,observable=o==n,reach_rank=r,observe_rank=o,dimension=n,model_sha256=m.digest,execution_authorized=False)


def _column_solution(a,b):
    # Exact unconstrained feasibility with one sparse representative, not min-norm.
    cols=f.pivots(a);n=len(a);m=len(a[0]);x=[Q(0)]*m
    if cols:
        selected=f.pick(a,range(n),cols);rows=f.pivots(tr(selected));core=f.pick(a,rows,cols)
        ans=s._solve(core,tuple((b[i],) for i in rows))
        for j,v in zip(cols,ans):x[j]=v[0]
    return tuple(x) if s.mv(a,tuple(x))==b else None


def reachability(m,start,target,k):
    n=_model(m);s.need(m.domain=='discrete','discrete horizon required');k=_horizon(k);start=s.vector(start,n,_q);target=s.vector(target,n,_q)
    x=start
    for _ in range(k):x=s.mv(m.a,x)
    mat=reach_matrix(m,k);sol=_column_solution(mat,s.va(target,tuple(-v for v in x)))
    if sol is None:return dict(reachable=False,inputs=None,execution_authorized=False)
    p=len(m.input_units);us=tuple(tuple(sol[i*p:(i+1)*p]) for i in reversed(range(k)))
    x=start
    for u in us:x=s.va(s.mv(m.a,x),s.mv(m.b,u))
    s.need(x==target,'reach witness');legal=all(abs(v)<=32 and v.denominator<=1024 for u in us for v in u)
    return dict(reachable=True,inputs=us,witness_within_input_bounds=legal,execution_authorized=False)


def reconstruct(m,inputs,outputs):
    n=_model(m);s.need(m.domain=='discrete','discrete observations required');s.need(type(inputs) is tuple and type(outputs) is tuple and len(inputs)==len(outputs),'sequence shape');k=_horizon(len(inputs))
    x=(Q(0),)*n;rhs=[]
    for u,y in zip(inputs,outputs):
        u=s.vector(u,len(m.input_units));y=s.vector(y,len(m.output_units),_q);force=s.va(s.mv(m.c,x),s.mv(m.d,u));rhs.extend(s.bounded(a-b) for a,b in zip(y,force));x=s.va(s.mv(m.a,x),s.mv(m.b,u))
    a=observe_matrix(m,k);r=len(f.pivots(a));value=_column_solution(a,tuple(rhs))
    return dict(consistent=value is not None,unique=value is not None and r==n,initial=value if r==n else None,rank=r,execution_authorized=False)


def _symmetric(a,n):
    a=s.matrix(a,n,n,_q);s.need(a==tr(a),'symmetric matrix required');return a


def _ldl(a,strict):
    # Schur complement PSD/PD test: a zero diagonal pivot of a PSD matrix
    # requires the whole remaining pivot row to vanish.
    z=[list(row) for row in a];piv=[]
    for i in range(len(z)):
        p=z[i][i];piv.append(p)
        if p<0 or (strict and not p):return None
        if not p:
            if any(z[i][j] for j in range(i+1,len(z))):return None
            continue
        for j in range(i+1,len(z)):
            for k in range(i+1,len(z)):z[j][k]=s.bounded(z[j][k]-s.bounded(z[j][i]*z[i][k]/p))
    return tuple(piv)


def _difference(a,p,domain):
    return sub(p,mm(tr(a),mm(p,a))) if domain=='discrete' else f.neg(add(mm(tr(a),p),mm(p,a)))


def _lyap(a,w,domain):
    # Solve the operator P-A^T P A=W or -(A^T P+P A)=W in exact rationals.
    n=len(a);op=[];rhs=[]
    for i in range(n):
        for j in range(n):
            row=[]
            for k in range(n):
                for l in range(n):
                    if domain=='discrete':v=Q(i==k and j==l)-a[k][i]*a[l][j]
                    else:v=-(a[k][i]*int(j==l)+int(i==k)*a[l][j])
                    row.append(s.bounded(v))
            op.append(tuple(row));rhs.append((w[i][j],))
    try:flat=s._solve(tuple(op),tuple(rhs))
    except ValueError as e:
        if str(e)=='singular resolvent':return None
        raise
    p=tuple(tuple(flat[i*n+j][0] for j in range(n)) for i in range(n));s.need(p==tr(p) and _difference(a,p,domain)==w,'Lyapunov equation witness');return p


def _stability(a,domain):
    p=_lyap(a,s.eye(len(a)),domain)
    return p if p is not None and _ldl(p,True) is not None else None


def lyapunov_certificate(m,p):
    n=_model(m);p=_symmetric(p,n);w=_difference(m.a,p,m.domain);dp=_ldl(p,True);dw=_ldl(w,True)
    s.need(dp is not None and dw is not None,'not a strict Lyapunov witness')
    return s.canonical(dict(profile='cognitum.ssm.lyapunov.exact.v1',model_sha256=m.digest,p=p,difference=w,p_pivots=dp,difference_pivots=dw,strict_stability=True,autonomous_sublevel_invariance=True,execution_authorized=False))


def replay_lyapunov(m,p,receipt):
    s.need(type(receipt) is bytes and 0<len(receipt)<=s.FRAME and receipt==lyapunov_certificate(m,p),'certificate mismatch');return True


def stability(m):
    _model(m);p=_stability(m.a,m.domain)
    return dict(strictly_stable=p is not None,p=p,model_sha256=m.digest,execution_authorized=False)


def _quotient(a,b):
    n=len(a);r=[];x=b
    for i in range(n):
        r.append(x)
        if i+1<n:x=mm(a,x)
    mat=tuple(tuple(v for block in r for v in block[i]) for i in range(n));cols=f.pivots(mat);rank=len(cols)
    basis=tuple(tuple(mat[i][j] for j in cols)+s.eye(n)[i] for i in range(n));chosen=f.pivots(basis);t=f.pick(basis,range(n),chosen);z=s._solve(t,mm(a,t))
    s.need(all(not z[i][j] for i in range(rank,n) for j in range(rank)),'reachable subspace witness')
    return f.pick(z,range(rank,n),range(rank,n))


def stabilizability(m):
    _model(m);q=_quotient(m.a,m.b);o=_quotient(tr(m.a),tr(m.c))
    # The uncontrollable quotient (and dual unobservable quotient) must be
    # strictly stable. Empty quotient vacuously passes.
    return dict(stabilizable=not q or _stability(q,m.domain) is not None,detectable=not o or _stability(o,m.domain) is not None,unreachable_quotient=q,dual_unobservable_quotient=o,model_sha256=m.digest,execution_authorized=False)


def gramians(m,horizon=None):
    n=_model(m);bb=mm(m.b,tr(m.b));cc=mm(tr(m.c),m.c)
    if horizon is None:
        s.need(_stability(m.a,m.domain) is not None,'infinite horizon requires strict stability');wc=_lyap(tr(m.a),bb,m.domain);wo=_lyap(m.a,cc,m.domain)
    else:
        s.need(m.domain=='discrete','finite Gramian is discrete only');k=_horizon(horizon);wc=_zeros(n,n);wo=wc
        for _ in range(k):wc=add(mm(m.a,mm(wc,tr(m.a))),bb);wo=add(mm(tr(m.a),mm(wo,m.a)),cc)
    s.need(wc is not None and wo is not None and _ldl(wc,False) is not None and _ldl(wo,False) is not None,'Gramian PSD witness')
    return dict(reach=wc,observe=wo,model_sha256=m.digest,horizon=horizon,execution_authorized=False)


def h2_squared(m):
    n=_model(m);s.need(m.domain=='discrete' or not any(x for row in m.d for x in row),'continuous H2 requires zero feedthrough');w=gramians(m)['reach'];p=add(mm(m.c,mm(w,tr(m.c))),mm(m.d,tr(m.d)))
    return s.bounded(sum((p[i][i] for i in range(len(p))),Q(0)))


def spectrum(m,horizon):
    """Numerical Schur and sampled induced-2-norm transient diagnostic, not bound."""
    _model(m);k=_horizon(horizon)
    import numpy as np
    from scipy.linalg import schur,expm
    a=np.array(m.a,float);t,u=schur(a,output='complex');tol=2e-12;err=float(np.linalg.norm(a-u@t@u.conj().T)/max(1.,np.linalg.norm(a)));orth=float(np.linalg.norm(u.conj().T@u-np.eye(len(a))))
    s.need(err<=tol and orth<=tol,'Schur residual')
    if m.domain=='continuous':s.need(np.linalg.norm(a,np.inf)*float(m.step)*k<=32,'transient exponential budget')
    gains=[];x=np.eye(len(a));step=a if m.domain=='discrete' else expm(a*float(m.step))
    for i in range(k+1):
        gain=float(np.linalg.norm(x,2));s.need(np.isfinite(gain) and gain<=1e100,'transient growth budget');gains.append(gain)
        if i<k:x=x@step
    return dict(eigenvalues=tuple((float(z.real),float(z.imag)) for z in np.diag(t)),schur_residual=err,orthogonality=orth,sampled_gains=tuple(gains),certified=False,execution_authorized=False)


def riccati(m,q,r):
    """Numerical stabilizing CARE/DARE for PSD Q and PD R; checked residual and exact rational closed-loop strict stability for the returned float gain."""
    n=_model(m);p=len(m.input_units);q=_symmetric(q,n);r=_symmetric(r,p);s.need(_ldl(q,False) is not None and _ldl(r,True) is not None,'cost definiteness')
    # Bound conversion and prevent extreme rational costs from overflowing float.
    q=s.matrix(q,n,n,s.rat);r=s.matrix(r,p,p,s.rat)
    import numpy as np
    from scipy.linalg import solve_continuous_are,solve_discrete_are
    a,b,c,d=map(lambda v:np.array(v,float),(m.a,m.b,q,r))
    try:
        if m.domain=='continuous':
            x=solve_continuous_are(a,b,c,d);g=np.linalg.solve(d,b.T@x);terms=(a.T@x,x@a,-x@b@g,c)
        else:
            x=solve_discrete_are(a,b,c,d);g=np.linalg.solve(d+b.T@x@b,b.T@x@a);terms=(a.T@x@a,-x,-a.T@x@b@g,c)
    except np.linalg.LinAlgError as e:raise ValueError('Riccati solve unavailable') from e
    s.need(np.isfinite(x).all() and np.isfinite(g).all() and np.linalg.norm(x,np.inf)<=1e8 and np.linalg.norm(g,np.inf)<=1e8,'Riccati numerical budget')
    res=float(np.linalg.norm(sum(terms),np.inf)/max(1.,sum(np.linalg.norm(t,np.inf) for t in terms)))
    s.need(res<=2e-10 and np.linalg.norm(x-x.T,np.inf)<=2e-10*max(1.,np.linalg.norm(x,np.inf)) and np.min(np.linalg.eigvalsh((x+x.T)/2))>=-2e-10*max(1.,np.linalg.norm(x,np.inf)),'Riccati residual or PSD')
    # Exact rational interpretation of returned binary64 gain, NOT of the
    # true Riccati root. Use bounded rational witness generation independent of eigenvalue classifications.
    gain=tuple(tuple(Q(float(v)) for v in row) for row in g);closed=sub(m.a,mm(m.b,gain));cert=_stability(closed,m.domain)
    s.need(cert is not None,'returned gain not strictly stabilizing')
    return dict(p=x,gain=g,scaled_residual=res,closed_loop_p=cert,closed_loop_a=closed,closed_loop_strictly_stable=True,optimality_certified=False,execution_authorized=False)


def pbh(m,real,imag=0):
    """Exact PBH ranks at one specified rational complex candidate eigenvalue."""
    n=_model(m);real=s.rat(real);imag=s.rat(imag)
    def rank(a,b):
        d=sub(f.scale(s.eye(n),real),a);j=f.scale(s.eye(n),imag);width=len(b[0]);zero=(Q(0),)*width
        top=tuple(d[i]+b[i]+tuple(-v for v in j[i])+zero for i in range(n))
        bot=tuple(j[i]+zero+d[i]+b[i] for i in range(n));r=len(f.pivots(top+bot));s.need(r%2==0,'complex rank witness');return r//2
    return dict(reach_rank=rank(m.a,m.b),observe_rank=rank(tr(m.a),tr(m.c)),real=real,imag=imag,execution_authorized=False)


def contraction(m,p,rate):
    """Exact global autonomous linear contraction in a quadratic metric.
    Discrete: A^T P A <= rate^2 P, 0<rate<1.
    Continuous: A^T P+P A <= -2 rate P, rate>0.
    """
    n=_model(m);p=_symmetric(p,n);rate=s.rat(rate);s.need(rate>0 and (m.domain=='continuous' or rate<1),'contraction rate');s.need(_ldl(p,True) is not None,'positive metric')
    w=_difference(m.a,p,m.domain)
    w=sub(w,f.scale(p,1-rate*rate if m.domain=='discrete' else 2*rate));piv=_ldl(w,False);s.need(piv is not None,'contraction inequality')
    return dict(model_sha256=m.digest,p=p,rate=rate,slack=w,pivots=piv,execution_authorized=False)


def reach_box(m,lo,hi,inputs):
    """Exact outward overapproximation for independent input-coordinate boxes."""
    n=_model(m);s.need(m.domain=='discrete','discrete required');lo=s.vector(lo,n,_q);hi=s.vector(hi,n,_q);s.need(all(a<=b for a,b in zip(lo,hi)),'invalid state box');s.need(type(inputs) is tuple,'input boxes');_horizon(len(inputs));out=[(lo,hi)]
    def image(a,l,h):
        return tuple(s.bounded(sum((min(v*x,v*y) for v,x,y in zip(row,l,h)),Q(0))) for row in a),tuple(s.bounded(sum((max(v*x,v*y) for v,x,y in zip(row,l,h)),Q(0))) for row in a)
    for item in inputs:
        s.need(type(item) is tuple and len(item)==2,'box pair');l,h=(s.vector(v,len(m.input_units)) for v in item);s.need(all(a<=b for a,b in zip(l,h)),'invalid input box');al,ah=image(m.a,lo,hi);bl,bh=image(m.b,l,h);lo=s.va(al,bl);hi=s.va(ah,bh);out.append((lo,hi))
    return dict(boxes=tuple(out),model_sha256=m.digest,overapproximation=True,execution_authorized=False)
