"""Exact L2/H1 metrics on certified tensor KAN fields; research only."""
from fractions import Fraction as Q
from itertools import product
from math import comb, prod
from functools import lru_cache
from cognitum.mel import tensor_field as f

PROFILE='cognitum.kan.tensor_function_metrics.v1'
MAX_TERMS=220
MAX_WORK=600000
MAX_RATIONAL_BITS=8192
MAX_RECEIPT=32768
need=f.need


def _bounded(q):
    need(q.numerator.bit_length()<=MAX_RATIONAL_BITS and
         q.denominator.bit_length()<=MAX_RATIONAL_BITS,'rational metric budget')
    return q


def _mul(a,b):
    c=[Q(0)]*(len(a)+len(b)-1)
    for i,x in enumerate(a):
        for j,y in enumerate(b):c[i+j]+=x*y
    return tuple(c)


def _shift(p,offset,scale):
    return tuple(sum((p[k]*comb(k,i)*offset**(k-i)*scale**i
                      for k in range(i,len(p))),Q(0)) for i in range(len(p)))


def _derivative(p,order,h):
    if order==0:return p
    return tuple(i*p[i]/h for i in range(1,len(p))) or (Q(0),)


def _polys(cuts,lo,hi,order):
    a,b,p=next(cell for cell in f.j._basis(cuts) if cell[0]<=lo<hi<=cell[1])
    h=b-a
    z=[_shift(_derivative(v,order,h),(lo-a)/h,(hi-lo)/h) for v in p]
    for degree in range(5):
        mon=tuple(Q(int(i==degree)) for i in range(degree+1))
        z.append(_shift(_derivative(mon,order,Q(1)),lo,hi-lo))
    return z


def _poly_inner(a,b,h):
    return h*sum((x*y/Q(i+j+1) for i,x in enumerate(a)
                  for j,y in enumerate(b)),Q(0))


def _rule():
    nodes=tuple(Q(i,10) for i in range(1,10));weights=[]
    for i,x in enumerate(nodes):
        poly=(Q(1),)
        for j,y in enumerate(nodes):
            if i!=j:poly=_mul(poly,(-y/(x-y),1/(x-y)))
        weights.append(sum((v/Q(k+1) for k,v in enumerate(poly)),Q(0)))
    need(all(sum((w*x**k for x,w in zip(nodes,weights)),Q(0))==Q(1,k+1)
             for k in range(9)),'quadrature moments')
    return nodes,tuple(weights)


NODES,WEIGHTS=_rule()


def _direct_values(cuts,x,order):
    # Independent pointwise recurrence; never uses polynomial coefficients.
    g=(Q(0),)*4+tuple(map(Q,cuts))+(Q(1),)*4
    @lru_cache(None)
    def basis(i,d):
        if d==0:return Q(int(g[i]<=x<g[i+1]))
        a,b=g[i+d]-g[i],g[i+d+1]-g[i+1]
        return ((x-g[i])/a*basis(i,d-1) if a else Q(0))+(
                (g[i+d+1]-x)/b*basis(i+1,d-1) if b else Q(0))
    def derivative(i):
        a,b=g[i+3]-g[i],g[i+4]-g[i+1]
        return (3*basis(i,2)/a if a else Q(0))-(3*basis(i+1,2)/b if b else Q(0))
    vals=[basis(i,3) if order==0 else derivative(i) for i in range(len(g)-4)]
    vals.extend(x**i if order==0 else (i*x**(i-1) if i else Q(0)) for i in range(5))
    return vals


def _axis_gram(left,right,order):
    need(type(order) is int and order in (0,1),'unsupported derivative')
    edges=sorted({Q(0),Q(1),*map(Q,left),*map(Q,right)})
    need(len(edges)<=14,'common axis partition budget')
    nl,nr=len(left)+9,len(right)+9
    total=[[Q(0)]*nr for _ in range(nl)]
    for lo,hi in zip(edges,edges[1:]):
        h=hi-lo
        a,b=_polys(left,lo,hi,order),_polys(right,lo,hi,order)
        observed=[[Q(0)]*nr for _ in range(nl)]
        # Both independent exact rules integrate degree <=8 on every cell.
        for z,w in zip(NODES,WEIGHTS):
            av,bv=_direct_values(left,lo+h*z,order),_direct_values(right,lo+h*z,order)
            for i,x in enumerate(av):
                if x:
                    for j,y in enumerate(bv):
                        if y:observed[i][j]+=h*w*x*y
        for i,ap in enumerate(a):
            for j,bp in enumerate(b):
                v=_poly_inner(ap,bp,h)
                need(v==observed[i][j],'exact Gram quadrature disagreement')
                total[i][j]=_bounded(total[i][j]+v)
    return tuple(tuple(row) for row in total)


def _field(raw):
    mod,p,m,cert=f.restore(raw)
    cuts,shape,coeff=f._tensor(mod,m)
    terms=[(idx,Q(c)) for idx,c in zip(product(*(range(n) for n in shape)),coeff) if c]
    for term in f._initial(mod,p):
        if term[-1]:terms.append((tuple(n+e for n,e in zip(shape,term[:-1])),Q(term[-1])))
    need(len(terms)<=MAX_TERMS,'tensor metric term budget')
    return mod,tuple(tuple(c) for c in cuts),tuple(terms)


def _contract(a,b,matrices):
    result=Q(0)
    for ia,ca in a:
        for ib,cb in b:
            weights=tuple(m[i][j] for m,i,j in zip(matrices,ia,ib))
            if all(weights):result=_bounded(result+ca*cb*prod(weights))
    return result


def _metric(left,right):
    lm,lc,lt=_field(left);rm,rc,rt=_field(right)
    need(lm is rm,'incompatible tensor profiles; no implicit axis conversion')
    axes=next(names for mod,names in f.PROFILES.values() if mod is lm)
    rank=len(axes)
    work=(rank+1)*(len(lt)**2+len(rt)**2+len(lt)*len(rt))
    need(work<=MAX_WORK,'aggregate tensor metric work budget')
    cache={}
    def gram(a,b,order):
        key=a,b,order
        if key not in cache:cache[key]=_axis_gram(a,b,order)
        return cache[key]
    def inner(ac,at,bc,bt,component):
        g=tuple(gram(a,b,int(i==component)) for i,(a,b) in enumerate(zip(ac,bc)))
        return _contract(at,bt,g)
    rows=[]
    for component in range(-1,rank):
        aa=inner(lc,lt,lc,lt,component)
        bb=inner(rc,rt,rc,rt,component)
        ab=inner(lc,lt,rc,rt,component)
        dd=_bounded(aa+bb-2*ab)
        need(aa>=0 and bb>=0 and dd>=0 and ab*ab<=aa*bb,'invalid exact metric identity')
        rows.append(dict(component='value' if component<0 else 'd_'+axes[component],
                         left_squared=aa,right_squared=bb,inner=ab,distance_squared=dd))
    def sum_rows(rows):
        return {k:_bounded(sum((r[k] for r in rows),Q(0))) for k in
                ('left_squared','right_squared','inner','distance_squared')}
    return dict(profile=PROFILE,left_checkpoint_sha256=f.digest(left).hex(),
                right_checkpoint_sha256=f.digest(right).hex(),axes=axes,
                work_units=work,components=rows,l2={k:v for k,v in rows[0].items() if k!='component'},
                h1_seminorm=sum_rows(rows[1:]),h1=sum_rows(rows),
                assurance='exact-represented-field-on-unit-box',
                pde_target_error_claim=False,execution_authorized=False)


def compare(left,right):
    """Exact squared metrics; normalized time is an ordinary coordinate."""
    raw=f.canonical(_metric(left,right))
    need(len(raw)<=MAX_RECEIPT,'metric receipt budget')
    return raw


def replay(left,right,receipt):
    need(type(receipt) is bytes and 0<len(receipt)<=MAX_RECEIPT,'metric receipt size')
    need(compare(left,right)==receipt,'metric receipt replay mismatch')
    return True
