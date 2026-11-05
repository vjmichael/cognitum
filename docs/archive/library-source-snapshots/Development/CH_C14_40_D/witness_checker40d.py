"""CH40-D independent local proof verifier, checker-only Python/Fraction kernel.

Does NOT import producer40d, CH40B Decimal arithmetic, producer MPFR/Jet,
branch-and-bound or Newton modules. Trust scope: newly issued local finite-box
claims. Historical producer float caps remain uncertified unless this independent
proof supports them separately. Never asserts unrestricted global optimality.
"""
from __future__ import annotations
from fractions import Fraction as F
from decimal import Decimal
import hashlib,json
from rational_kernel40d import R,model_of,eta,p_of,direct_components,coupled_terms
from checker_interval40d import f_derivatives,point_firth

PROTOCOL='CH40D-LOCAL-WITNESS-V1'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')).hexdigest()

def _interval(pair):
    if type(pair) is not list or len(pair)!=2:return (_ for _ in ()).throw(ValueError('Bad interval receipt'))
    if any(type(x) is not str or len(x)>250 for x in pair):raise ValueError('Non-canonical interval literal')
    return R(pair[0],pair[1])

def _claim_pair(x,real,where):
    saved=_interval(x)
    if not isinstance(real,R):real=R.raw(F(real.lo),F(real.hi))
    if not saved.contains(real):raise ValueError('Unjustified bound at '+where)
    return saved

def _source(cert,w):
    if w.get('protocol')!=PROTOCOL or w.get('scientific_release')!='NO_GO' or w.get('scope')!='NEW_FINITE_BOX_MATHEMATICAL_WITNESS_ONLY':raise ValueError('Invalid proof protocol/scope')
    if cert.get('production_release')!='NO_GO' or cert.get('milestone')!='CH-C14-29' or cert.get('unbounded_global_claim') is not False:raise ValueError('Original source nonresearch scope')
    if cert.get('model_sha256')!=digest(cert['model']):raise ValueError('Producer model integrity failed')
    if w.get('case')!=cert['research_case_id'] or w.get('certificate_sha256')!=digest(cert) or w.get('model_sha256')!=digest(cert['model']):raise ValueError('Source model/checkpoint mismatch')
    n=w.get('node_id')
    if type(n) is not int or not 0<=n<len(cert['nodes']):raise ValueError('Unfrozen proof node')
    node=cert['nodes'][n]
    if w.get('node_sha256')!=digest(node):raise ValueError('Tampered node source')
    if w.get('source_method')!=node.get('upper_method'):raise ValueError('Producer method changed')
    if F(str(w['original_display_only']))!=F(str(node['local_upper_bound_display'])):raise ValueError('Changed display identity')
    box=w.get('box')
    if type(box) is not list or len(box)!=cert['model']['d'] or len(box)!=len(node['box']):raise ValueError('Mismatched root dimensions')
    if any(len(v)!=2 or F(str(v[0]))!=F(str(q[0])) or F(str(v[1]))!=F(str(q[1])) for v,q in zip(box,node['box'])):raise ValueError('Witness box differs from producer proof geometry')
    if any(F(a)>=F(b) for a,b in box):raise ValueError('Degenerate source box')
    if node['effective_box']!=node['box'] or 'newton' in node:raise ValueError('Uncertified historical Newton action')
    if w['kind']=='COUPLED_TANGENT' and node.get('upper_method')!='coupled_logdet_dual':raise ValueError('Witness method does not match source')
    if w['kind'] not in ('COUPLED_TANGENT','DIRECT','TAYLOR2','KRAWCZYK'):raise ValueError('Unknown witness proof rule')
    return node

def _local_box(w, cert):
    box=w['local_box'];parent=w['box'];root=cert['root_box']
    if type(box) is not list or len(box)!=len(parent):raise ValueError('Bad local dimensions')
    for (a,b),(x,y),(u,v) in zip(box,parent,root):
        a,b,x,y,u,v=map(lambda z:F(str(z)),(a,b,x,y,u,v))
        if not (u<a<b<v and x<=a and b<=y):raise ValueError('Local box not strictly inside root and source node')
    return box

def verify(cert,w):
    _source(cert,w)
    kind=w['kind'];box=w['box'];claim=w['claim'];r={'protocol':PROTOCOL,'case':w['case'],'node_id':w['node_id'],'kind':kind,'source_sha256':w['certificate_sha256'],'witness_sha256':digest(w),
       'scope':'NEW_FINITE_BOX_MATHEMATICAL_WITNESS_ONLY','scientific_release':'NO_GO','valid_local_witness':True,
       'historical_producer_cap_certified':False,'global_optimality_certified':False}
    if kind=='DIRECT':
        cap=F(str(claim['upper']));terms,detI,truth=direct_components(cert,box)
        trace=w['arithmetic_trace']
        if len(trace['loglik_rows'])!=len(terms):raise ValueError('Direct row trace count')
        saved=[_claim_pair(v,x,'direct loglik row') for v,x in zip(trace['loglik_rows'],terms)]
        determinant=_claim_pair(trace['fisher_determinant'],detI,'direct Fisher determinant')
        audited_upper=sum(saved,R(0))+R(F(1,2))*determinant.ln()
        if cap<truth.hi or cap<audited_upper.hi:raise ValueError('Forged direct upper bound')
        r['local_upper_ceiling']=str(claim['upper'])
        r['historical_producer_cap_certified']=cap<=F(str(w['original_display_only']))
    elif kind=='COUPLED_TANGENT':
        supp=w['support'];idx=supp['dual_index']
        if type(idx) is not int or idx<0 or idx>=len(cert['dual_matrices']):raise ValueError('Bad dual index')
        if supp.get('concavity_identity')!='g2=-s/p^2-(n-s)/(1-p)^2-2k<=0':raise ValueError('Unrecognized tangent justification')
        points=supp['tangent_points']
        c,terms,result,details=coupled_terms(cert,box,idx,points)
        trace=w['arithmetic_trace']
        const=_claim_pair(trace['constant'],c,'dual logdet constant')
        if len(trace['tangent_terms'])!=len(terms):raise ValueError('Tangent row count')
        saved=[_claim_pair(s,z,'tangent row '+str(i)) for i,(s,z) in enumerate(zip(trace['tangent_terms'],terms))]
        full=trace['tangent_support_evaluations']
        if len(full)!=len(details):raise ValueError('Missing tangent slope trace')
        for i,(record,proof) in enumerate(zip(full,details)):
            for key in ('value','slope','probability'):
                _claim_pair(record[key],proof[key],'tangent '+key+' row '+str(i))
        # Independent arithmetic AND published outward trace must justify the cap.
        total=const+sum(saved,R(0));cap=F(str(claim['upper']))
        if cap<result.hi or cap<total.hi:raise ValueError('Forged coupled upper cap')
        r['local_upper_ceiling']=str(claim['upper'])
        r['historical_producer_cap_certified']=cap<=F(str(w['original_display_only']))
    elif kind=='TAYLOR2':
        B=_local_box(w,cert);support=w['taylor_support'];mid=support['midpoint']
        if len(mid)!=len(B) or any(F(str(t))!=(F(str(a))+F(str(b)))/2 for t,(a,b) in zip(mid,B)):raise ValueError('Forged Taylor midpoint')
        fmid=point_firth(cert,mid)
        midgrad,_=f_derivatives(cert,[[t,t] for t in mid]);_,H=f_derivatives(cert,B)
        ff=_claim_pair(support['f0'],fmid,'Taylor center objective')
        if len(support['gradient'])!=len(midgrad) or len(support['hessian'])!=len(H):raise ValueError('Taylor dimensions')
        g=[_claim_pair(v,t,'Taylor gradient') for v,t in zip(support['gradient'],midgrad)]
        hh=[[_claim_pair(v,t,'Taylor Hessian') for v,t in zip(row,truth)] for row,truth in zip(support['hessian'],H)]
        radii=[(F(str(b))-F(str(a)))/2 for a,b in B]
        proven=ff.hi+sum((g[i].upper_abs()*radii[i] for i in range(len(B))),F(0))
        proven+=sum((F(1,2)*hh[i][j].upper_abs()*radii[i]*radii[j] for i in range(len(B)) for j in range(len(B))),F(0))
        if F(str(claim['upper']))<proven:raise ValueError('Taylor cap fails independent Hessian remainder proof')
        r['local_upper_ceiling']=claim['upper'];r['taylor_expansion_certified']=True
    else:
        B=_local_box(w,cert)
        if len(w.get('root_box',[]))!=len(cert['root_box']) or any([F(str(a)),F(str(b))]!=[F(str(u)),F(str(v))] for (a,b),(u,v) in zip(w['root_box'],cert['root_box'])):raise ValueError('Root scope substitution')
        supp=w['newton_support'];d=len(B);mid=supp['midpoint'];C=supp['preconditioner']
        if len(mid)!=d or any(F(str(z))!=(F(str(a))+F(str(b)))/2 for z,(a,b) in zip(mid,B)):raise ValueError('Invalid Newton midpoint')
        if len(C)!=d or any(len(row)!=d for row in C):raise ValueError('Bad Newton matrix')
        g0,_=f_derivatives(cert,[[x,x] for x in mid]);gbox,H=f_derivatives(cert,B)
        scoremid=[_claim_pair(v,t,'Newton midpoint score') for v,t in zip(supp['score_mid'],g0)]
        scorebox=[_claim_pair(v,t,'Newton box score') for v,t in zip(supp['score_box'],gbox)]
        Hess=[[_claim_pair(v,t,'Newton Hessian') for v,t in zip(row,rr)] for row,rr in zip(supp['hessian_box'],H)]
        pre=[[R(x) for x in row] for row in C]
        delta=[R(a,b)-R(x) for (a,b),x in zip(B,mid)]
        K=[]
        for i in range(d):
            z=R(mid[i])-sum((pre[i][k]*scoremid[k] for k in range(d)),R(0))
            for j in range(d):
                h=sum((pre[i][k]*Hess[k][j] for k in range(d)),R(0))
                z=z+(R(int(i==j))-h)*delta[j]
            K.append(z)
        traceK=supp['krawczyk_enclosure']
        if len(traceK)!=d:raise ValueError('Missing Krawczyk enclosure')
        for i,(saved_k,truth_k) in enumerate(zip(traceK,K)):
            _claim_pair(saved_k,truth_k,'Krawczyk coordinate '+str(i))
        status=claim.get('status')
        score_excludes=any(v.lo>0 or v.hi<0 for v in scorebox)
        disjoint=any(not q.intersects(R(a,b)) for q,(a,b) in zip(K,B))
        if status=='NO_STATIONARY':
            if claim.get('reason')=='GRADIENT_SIGN' and not score_excludes:raise ValueError('Forged gradient exclusion')
            elif claim.get('reason')=='KRAWCZYK_DISJOINT' and not disjoint:raise ValueError('Forged Krawczyk exclusion')
            elif claim.get('reason') not in ('GRADIENT_SIGN','KRAWCZYK_DISJOINT'):raise ValueError('Unrecognized exclusion rule')
            r['stationary_exclusion_certified']=True
        elif status=='CONTRACTED':
            if score_excludes or disjoint:raise ValueError('Contraction status inconsistent with a witnessed exclusion')
            saved=claim['box']
            if len(saved)!=d:raise ValueError('Contracted box dimension')
            strictly=False
            for (u,v),(a,b),zz in zip(saved,B,K):
                u,v,a,b=map(lambda x:F(str(x)),(u,v,a,b))
                t=zz.intersection(R(a,b))
                if not(a<=u<=t.lo<=t.hi<=v<=b):raise ValueError('Claimed contraction loses possible stationary point')
                strictly|=(u>a or v<b)
            if not strictly:raise ValueError('No actual contraction')
            r['stationary_contraction_certified']=True
        elif status=='NO_GAIN':r['stationary_contraction_certified']=False
        else:raise ValueError('Unsupported Newton conclusion')
        r['newton_scope']='INTERIOR_STATIONARY_ROOTS_ONLY_NO_BOUNDARY_EXCLUSION'
    return r