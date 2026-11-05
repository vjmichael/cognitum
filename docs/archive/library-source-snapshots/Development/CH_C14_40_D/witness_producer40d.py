"""CH40-D prototype witness emitter (untrusted by checker).

This producer uses CH40-B Decimal mathematics. The *separate* CH40-D verifier
uses exact Fraction intervals and rederives the bounds independently.
The witnesses prove new local bounds, NOT missing historical MPFR float traces.
"""
from __future__ import annotations
from fractions import Fraction as F
from decimal import Decimal as D,localcontext,ROUND_FLOOR,ROUND_CEILING
import json,hashlib
from independent_checker40 import MathematicalModel,digest
from independent_bounds40b import objective_derivatives,taylor_upper,dual_coupled_upper
from independent_newton40b import krawczyk
from exact_decimal40 import IV,CONTEXT
from batch40b import finite_fraction

PAD=D('0.00000000000001') # minimum 1e-14 absolute pad
REL_PAD=D('0.000000000000000000000001') # 1e-24 relative for ill-conditioned Hessians
CAP_PAD=D('0.000001') # 1e-6 local upper cap after independent arithmetic

def out_iv(q):
    delta=max(PAD,REL_PAD*max(abs(q.lo),abs(q.hi)))
    with localcontext(CONTEXT) as ctx:
        ctx.rounding=ROUND_FLOOR;lo=q.lo-delta
        ctx.rounding=ROUND_CEILING;hi=q.hi+delta
    return [str(lo),str(hi)]

def ceil_claim(q,extra=CAP_PAD):
    with localcontext(CONTEXT) as ctx:
        ctx.rounding=ROUND_CEILING
        return str(q+extra)

def upper_from_taylor_trace(box,record):
    """Aggregate only published validated enclosures, NOT unrounded private Hessian."""
    widths=[(F(str(b))-F(str(a)))/2 for a,b in box]
    def mag(interval):return max(abs(F(interval[0])),abs(F(interval[1])))
    g=record['gradient'];H=record['hessian']
    v=F(record['f0'][1])
    v+=sum((mag(g[i])*widths[i] for i in range(len(box))),F(0))
    v+=sum((F(1,2)*mag(H[i][j])*widths[i]*widths[j] for i in range(len(box)) for j in range(len(box))),F(0))
    with localcontext(CONTEXT) as ctx:
        ctx.rounding=ROUND_CEILING
        d=D(v.numerator)/D(v.denominator)
        return str(d+D('0.000001'))

def out_strictly_positive(q):
    if q.lo<=0:raise ArithmeticError('Producer Fisher positivity unproved')
    vals=out_iv(q)
    if D(vals[0])<=0:
        with localcontext(CONTEXT) as ctx:
            ctx.rounding=ROUND_FLOOR
            vals[0]=str(q.lo/D(2))
    return vals

def upper_from_direct_trace(trace):
    vals=sum((IV(str(v[1])) for v in trace['loglik_rows']),IV(0))
    vals=vals+IV('0.5')*IV(str(trace['fisher_determinant'][1])).ln()
    return ceil_claim(vals.hi)

def obj_sha(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def exact_box(box):return [[finite_fraction(F(str(a))),finite_fraction(F(str(b)))] for a,b in box]

def base(cert,node_id):
    node=cert['nodes'][node_id]
    return {'protocol':'CH40D-LOCAL-WITNESS-V1','case':cert['research_case_id'],'certificate_sha256':digest(cert),
            'model_sha256':digest(cert['model']),'node_id':node_id,'node_sha256':obj_sha(node),
            'box':exact_box(node['box']),'source_method':node['upper_method'],
            'original_display_only':str(node['local_upper_bound_display']),
            'scope':'NEW_FINITE_BOX_MATHEMATICAL_WITNESS_ONLY','scientific_release':'NO_GO'}

def direct_witness(cert,node_id):
    m=MathematicalModel(cert['model']);b=base(cert,node_id)
    b['kind']='DIRECT';B=b['box']
    weights=[];row_terms=[]
    for row,z in zip(cert['model']['rows'],m.eta(B)):
        n,s=row['n'],row['s'];weights.append(m.weight(z))
        if s==0: term=-(IV(1)+IV(z.lo).exp()).ln()*n
        elif s==n:term=-(IV(1)+(-IV(z.hi)).exp()).ln()*n
        else:term=z*s-(IV(1)+z.exp()).ln()*n
        row_terms.append(out_iv(term))
    detI=m.info_det(weights)
    b['arithmetic_trace']={'loglik_rows':row_terms,'fisher_determinant':out_strictly_positive(detI)}
    b['claim']={'upper':upper_from_direct_trace(b['arithmetic_trace'])}
    return b

def coupled_witness(cert,node_id,dual_index=None):
    model=MathematicalModel(cert['model']);b=base(cert,node_id);b['kind']='COUPLED_TANGENT'
    if dual_index is None:
        # Choose an informative source-frozen SPD tangent matrix using the
        # mathematical producer. Verifier independently checks chosen matrix.
        candidate=dual_coupled_upper(model,b['box'],cert['dual_matrices'])
        dual_index=min(range(len(candidate['by_dual'])),key=lambda i:D(candidate['by_dual'][i]))
    Q=[[F(str(z)) for z in row] for row in cert['dual_matrices'][dual_index]]
    det=lambda a:(a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])-a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])+a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0])) if len(a)==3 else a[0][0]*a[1][1]-a[0][1]*a[1][0] if len(a)==2 else a[0][0]
    d=model.d;bound=-IV('0.5')*IV.rational(det(Q)).ln()-IV(str(d))/IV(2)
    constant=bound
    eta=model.eta(b['box']);points=[];terms=[];support_details=[]
    for row,x,predictor in zip(cert['model']['rows'],model.x,eta):
        n,s=row['n'],row['s'];pp=model.probability(predictor)
        # Optimize the concave scalar majorant only to SELECT p0. Any p0 in
        # (0,1) remains a mathematical valid tangent, regardless of floats.
        # x^T Q x is exact rational; float choice cannot affect soundness.
        leverage0=sum((x[j]*Q[j][k]*x[k] for j in range(d) for k in range(d)),F(0))
        kk=float(F(n,2)*leverage0)
        low=max(1e-13,min(1-1e-13,float(pp.lo)))
        high=max(low,min(1-1e-13,float(pp.hi)))
        def slope0(v):return s/v-(n-s)/(1-v)+kk*(1-2*v)
        if slope0(low)<=0:chosen=low
        elif slope0(high)>=0:chosen=high
        else:
            aa,bb=low,high
            for _ in range(70):
                mid0=(aa+bb)/2
                if slope0(mid0)>0:aa=mid0
                else:bb=mid0
            chosen=(aa+bb)/2
        with localcontext(CONTEXT):
            point=D(format(chosen,'.17g')).quantize(D('0.000000000001'))
        point=min(D('0.999999999999'),max(D('0.000000000001'),point))
        p=IV(str(point));points.append(str(point))
        leverage=sum((x[j]*Q[j][k]*x[k] for j in range(d) for k in range(d)),F(0))
        k=IV.rational(F(n,2)*leverage)
        val=IV(s)*p.ln()+IV(n-s)*(IV(1)-p).ln()+k*p*(IV(1)-p)
        slope=IV(s)/p-IV(n-s)/(IV(1)-p)+k*(IV(1)-IV(2)*p)
        term=val+slope*(pp-p)
        terms.append(out_iv(term));bound=bound+term
        support_details.append({'value':out_iv(val),'slope':out_iv(slope),'probability':out_iv(pp)})
    b['support']={'dual_index':dual_index,'tangent_points':points,
                  'concavity_identity':'g2=-s/p^2-(n-s)/(1-p)^2-2k<=0'}
    b['arithmetic_trace']={'constant':out_iv(constant),'tangent_terms':terms,'tangent_support_evaluations':support_details}
    b['claim']={'upper':ceil_claim(bound.hi)}
    return b

def tiny_box(cert):
    center=[F(str(x)) for x in cert['incumbent']];box=[]
    for t,(a,b) in zip(center,cert['root_box']):
        w=min(F(1,1000),(t-F(str(a)))/4,(F(str(b))-t)/4)
        if w<=0:raise ValueError('Incumbent not strictly interior')
        box.append([finite_fraction(t-w),finite_fraction(t+w)])
    return box

def taylor_witness(cert,node_id=0,box=None):
    m=MathematicalModel(cert['model']);w=base(cert,node_id);w['kind']='TAYLOR2';B=box or tiny_box(cert)
    w['local_box']=B
    midpoint=[finite_fraction((F(str(a))+F(str(b)))/2) for a,b in B]
    point=[(x,x) for x in midpoint]
    f0lower=m.incumbent_lower(midpoint);f0upper=m.objective_bound(point)
    g,_=objective_derivatives(m,point);_,h=objective_derivatives(m,B)
    w['taylor_support']={'midpoint':midpoint,'f0':out_iv(IV(str(f0lower),str(f0upper))),
                         'gradient':[out_iv(t) for t in g],
                         'hessian':[[out_iv(t) for t in row] for row in h]}
    w['claim']={'upper':upper_from_taylor_trace(B,w['taylor_support'])}
    return w

def newton_witness(cert,node_id=0,box=None):
    m=MathematicalModel(cert['model']);w=base(cert,node_id);w['kind']='KRAWCZYK';B=box or tiny_box(cert)
    w['local_box']=B;w['root_box']=cert['root_box']
    C=[['-0.01' if i==j else '0' for j in range(m.d)] for i in range(m.d)]
    mid=[finite_fraction((F(str(a))+F(str(b)))/2) for a,b in B]
    gmid,_=objective_derivatives(m,[(x,x) for x in mid]);gbox,hbox=objective_derivatives(m,B)
    outcome=krawczyk(m,B,cert['root_box'],C)
    # The independent checker derives K from the PUBLISHED rounded gradient and
    # Hessian. Emit K from exactly that public trace, never hidden narrower data.
    support={'midpoint':mid,'preconditioner':C,'score_mid':[out_iv(x) for x in gmid],
             'score_box':[out_iv(x) for x in gbox],
             'hessian_box':[[out_iv(x) for x in row] for row in hbox]}
    pre=[[IV(z) for z in row] for row in C]
    pub_g=[IV(*pair) for pair in support['score_mid']]
    pub_H=[[IV(*pair) for pair in row] for row in support['hessian_box']]
    delta=[IV(a,b)-IV(x) for (a,b),x in zip(B,mid)]
    K=[]
    for i in range(m.d):
        zz=IV(mid[i])-sum((pre[i][k]*pub_g[k] for k in range(m.d)),IV(0))
        for j in range(m.d):
            hh=sum((pre[i][k]*pub_H[k][j] for k in range(m.d)),IV(0))
            zz=zz+(IV(int(i==j))-hh)*delta[j]
        K.append(zz)
    support['krawczyk_enclosure']=[out_iv(x) for x in K]
    w['newton_support']=support
    if outcome['status']=='NO_STATIONARY':
        w['claim']={'status':'NO_STATIONARY','reason':outcome['reason']}
    elif outcome['status']=='CONTRACTED':
        # Widen the contraction outward by a small margin to ensure the independent
        # checker has room for differences in independently rounded intervals.
        result=[]
        for (a,b),(x,y) in zip(B,outcome['box']):
            lo=max(D(str(a)),D(str(x))-D('0.00000001'))
            hi=min(D(str(b)),D(str(y))+D('0.00000001'))
            result.append([str(lo),str(hi)])
        w['claim']={'status':'CONTRACTED','box':result}
    else:w['claim']={'status':'NO_GAIN'}
    return w