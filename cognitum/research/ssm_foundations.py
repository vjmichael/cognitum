"""Additional bounded state-space foundations. Research-only; no execution authority."""
from fractions import Fraction as Q
from . import ssm_linear as s


def neg(a):
    return tuple(tuple(-x for x in row) for row in a)


def scale(a,h):
    return tuple(tuple(s.bounded(h*x) for x in row) for row in a)


def sub(a,b):
    return s._add(a,neg(b))


def pick(a,rows,cols):
    return tuple(tuple(a[i][j] for j in cols) for i in rows)


def transpose(a):
    return tuple(zip(*a))


def pivots(a):
    """Exact rectangular elimination, returning independent original columns."""
    z=[list(row) for row in a];r=0;cols=[]
    for j in range(len(z[0])):
        i=next((i for i in range(r,len(z)) if z[i][j]),None)
        if i is None:continue
        z[r],z[i]=z[i],z[r];p=z[r][j]
        z[r]=[s.bounded(v/p) for v in z[r]]
        for i in range(r+1,len(z)):
            p=z[i][j];z[i]=[s.bounded(x-s.bounded(p*y)) for x,y in zip(z[i],z[r])]
        cols.append(j);r+=1
        if r==len(z):break
    return tuple(cols)


def similarity(model,t,new_units):
    """x=T z, with separately caller-declared coordinate unit metadata."""
    s.need(type(model) is s.Model,'typed model');n=len(model.a)
    t=s.matrix(t,n,n);inv=s._solve(t,s.eye(n))
    result=s.Model(s._matmul(inv,s._matmul(model.a,t)),s._matmul(inv,model.b),s._matmul(model.c,t),model.d,new_units,model.input_units,model.output_units,model.domain,model.step)
    s.need(s._matmul(t,inv)==s.eye(n) and s._matmul(inv,t)==s.eye(n),'inverse witness')
    return result,inv


def moments(model,count):
    """C A^j B, excluding direct feedthrough, valid for either time domain."""
    s.need(type(model) is s.Model and type(count) is int and 1<=count<=2*s.DIM+1,'moment budget')
    x=model.b;out=[]
    for i in range(count):
        out.append(s._matmul(model.c,x))
        if i+1<count:x=s._matmul(model.a,x)
    return tuple(out)


def minimal(model):
    """Exact finite-block Hankel realization of the zero-initial-state I/O map.

    A reduced direct-feedthrough-only map returns model=None. No arbitrary
    initial-state equivalence is asserted. Out-of-profile coefficients refuse.
    """
    s.need(type(model) is s.Model,'typed model');n=len(model.a);m=len(model.input_units);p=len(model.output_units)
    g=moments(model,2*n+1)
    h=tuple(tuple(g[i//p+j//m][i%p][j%m] for j in range(n*m)) for i in range(n*p))
    shifted=tuple(tuple(g[i//p+j//m+1][i%p][j%m] for j in range(n*m)) for i in range(n*p))
    cols=pivots(h);r=len(cols)
    if not r:
        s.need(all(not v for block in g for row in block for v in row),'static moment witness')
        return dict(rank=0,model=None,d=model.d,input_units=model.input_units,output_units=model.output_units,domain=model.domain,step=model.step,rows=(),cols=(),execution_authorized=False)
    selected=pick(h,range(n*p),cols);rows=pivots(transpose(selected));s.need(len(rows)==r,'Hankel rank witness')
    core=pick(h,rows,cols);ar=s._solve(core,pick(shifted,rows,cols));br=s._solve(core,pick(h,rows,range(m)));cr=pick(h,range(p),cols)
    reduced=s.Model(ar,br,cr,model.d,('coord',)*r,model.input_units,model.output_units,model.domain,model.step)
    # Full factorization and one-step shift, not just selected minor parity.
    right=s._solve(core,pick(h,rows,range(n*m)))
    s.need(s._matmul(selected,right)==h and s._matmul(s._matmul(selected,ar),right)==shifted,'Hankel shift witness')
    s.need(moments(reduced,2*n+1)==g,'moment witness')
    return dict(rank=r,model=reduced,d=model.d,input_units=model.input_units,output_units=model.output_units,domain=model.domain,step=model.step,rows=rows,cols=cols,execution_authorized=False)


def varying(models,x,inputs,biases,ticks):
    """Bounded explicitly indexed affine discrete trajectory, no implicit clocks."""
    s.need(type(models) is tuple and 1<=len(models)<=s.STEPS and all(type(v) is s.Model and v.domain=='discrete' for v in models),'model sequence')
    first=models[0];n=len(first.a);m=len(first.input_units);length=len(models)
    s.need(all((v.state_units,v.input_units,v.output_units,v.step)==(first.state_units,first.input_units,first.output_units,first.step) for v in models),'coordinate/clock mismatch')
    s.need(type(inputs) is tuple and type(biases) is tuple and len(inputs)==len(biases)==length,'sequence shape')
    s.need(type(ticks) is tuple and len(ticks)==length and all(type(k) is int and 0<=k<s.CLOCK for k in ticks) and all(b==a+1 for a,b in zip(ticks,ticks[1:])),'clock sequence')
    x=s.vector(x,n,s.bounded);outputs=[];trans=(s.eye(n),(Q(0),)*n)
    for v,u,g in zip(models,inputs,biases):
        u=s.vector(u,m);g=s.vector(g,n);outputs.append(s.va(s.mv(v.c,x),s.mv(v.d,u)))
        offset=s.va(s.mv(v.b,u),g);x=s.va(s.mv(v.a,x),offset);trans=s.compose(trans,(v.a,offset))
    return dict(final=x,outputs=tuple(outputs),transition=trans,next_index=ticks[-1]+1,model_digests=tuple(v.digest for v in models),execution_authorized=False)


def bilinear(model,interactions,x,inputs):
    """Caller-specified A(u)=A+sum u_i N_i, finite known input sequence."""
    s.need(type(model) is s.Model and model.domain=='discrete','discrete model required');n=len(model.a);m=len(model.input_units)
    s.need(type(interactions) is tuple and len(interactions)==m,'interaction shape')
    interactions=tuple(s.matrix(a,n,n) for a in interactions)
    s.need(type(inputs) is tuple and 1<=len(inputs)<=s.STEPS,'sequence budget');models=[]
    for u in inputs:
        u=s.vector(u,m);a=model.a
        for v,t in zip(u,interactions):a=s._add(a,scale(t,v))
        models.append(s.Model(a,model.b,model.c,model.d,model.state_units,model.input_units,model.output_units,model.domain,model.step))
    return varying(tuple(models),x,inputs,((Q(0),)*n,)*len(inputs),tuple(range(len(inputs))))


def approximate_discrete(model,h,method):
    """Exact coefficient arithmetic for Euler/Tustin approximations, not exact flow."""
    s.need(type(model) is s.Model and model.domain=='continuous','continuous model required');h=s.rat(h);s.need(h>0,'positive interval');n=len(model.a)
    if method=='euler':
        a=s._add(s.eye(n),scale(model.a,h));b=scale(model.b,h);c=model.c;d=model.d
    elif method=='tustin':
        half=h/2;left=sub(s.eye(n),scale(model.a,half));right=s._add(s.eye(n),scale(model.a,half));a=s._solve(left,right);b=s._solve(left,scale(model.b,h));c=s._matmul(model.c,s._solve(left,s.eye(n)));d=s._add(model.d,scale(s._matmul(model.c,b),Q(1,2)))
    else:raise ValueError('unsupported discretization')
    return s.Model(a,b,c,d,model.state_units,model.input_units,model.output_units,'discrete',h)


def foh(model,h):
    """Physical-coordinate first-order hold: x+=Ad*x+B0*u0+B1*u1."""
    s.need(type(model) is s.Model and model.domain=='continuous','continuous model required');h=s.rat(h);s.need(h>0,'positive interval')
    import numpy as np
    from scipy.linalg import expm
    n=len(model.a);m=len(model.input_units);size=n+2*m
    z=np.zeros((size,size));z[:n,:n]=np.array(model.a,dtype=float)*float(h);z[:n,n:n+m]=np.array(model.b,dtype=float)*float(h);z[n:n+m,n+m:]=np.eye(m)
    norm=float(np.linalg.norm(z,np.inf));s.need(norm<=8,'exponential norm budget');k=0
    while norm/(2**k)>0.5:k+=1
    a=z/(2**k);series=np.eye(size);term=series.copy()
    for i in range(1,33):term=term@a/i;series+=term
    for _ in range(k):series=series@series
    direct=expm(z);err=float(np.linalg.norm(direct-series,np.inf)/max(1.,np.linalg.norm(direct,np.inf)))
    s.need(np.isfinite(direct).all() and np.isfinite(series).all() and err<=2e-12,'exponential cross-check')
    b1=direct[:n,n+m:];b0=direct[:n,n:n+m]-b1
    return dict(a=direct[:n,:n],b0=b0,b1=b1,step=str(h),scaled_crosscheck=err,certified=False,execution_authorized=False)


def descriptor(model,dynamic,e):
    """Semi-explicit index-1 E=diag(E_d,0), invertible E_d and A_aa only."""
    s.need(type(model) is s.Model and model.domain=='continuous','continuous descriptor required');n=len(model.a);m=len(model.input_units)
    s.need(type(dynamic) is int and 1<=dynamic<n,'descriptor partition');k=dynamic
    e=s.matrix(e,n,n);s.need(all(not e[i][j] for i in range(n) for j in range(n) if i>=k or j>=k),'unsupported descriptor shape')
    dd=range(k);aa=range(k,n);uu=range(m);yy=range(len(model.c))
    ed=pick(e,dd,dd);a11=pick(model.a,dd,dd);a12=pick(model.a,dd,aa);a21=pick(model.a,aa,dd);a22=pick(model.a,aa,aa);b1=pick(model.b,dd,uu);b2=pick(model.b,aa,uu);c1=pick(model.c,yy,dd);c2=pick(model.c,yy,aa)
    x=s._solve(a22,neg(a21));u=s._solve(a22,neg(b2));a=s._solve(ed,s._add(a11,s._matmul(a12,x)));b=s._solve(ed,s._add(b1,s._matmul(a12,u)))
    c=s._add(c1,s._matmul(c2,x));d=s._add(model.d,s._matmul(c2,u))
    s.need(s._matmul(a22,x)==neg(a21) and s._matmul(a22,u)==neg(b2),'algebraic residual')
    reduced=s.Model(a,b,c,d,model.state_units[:k],model.input_units,model.output_units,'continuous',model.step)
    return dict(model=reduced,algebraic_x=x,algebraic_u=u,execution_authorized=False)


def consistent_state(model,dynamic,e,x,u):
    reduced=descriptor(model,dynamic,e);x=s.vector(x,len(model.a),s.bounded);u=s.vector(u,len(model.input_units))
    s.need(x[dynamic:]==s.va(s.mv(reduced['algebraic_x'],x[:dynamic]),s.mv(reduced['algebraic_u'],u)),'inconsistent algebraic initial state')
    return x[:dynamic]
