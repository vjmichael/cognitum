"""CH40-A: independent Firth-binomial-logistic finite-box checker.

No CH23–CH39 or MPFR imports. All model numbers, splits and dual-SPD checks
use exact rational arithmetic. Objective bounds use a *separate* libmpdec
interval implementation (exact_decimal40.py), not inherited MPFR Jet or BnB.

Certification scope is intentionally narrow: exact 127-node partition,
independently recomputed *sound but not necessarily tight* upper bounds for
Firth's objective over all 64 leaves and exact nonzero Fisher minor for a
feasible incumbent lower. Original recorded upper numbers are not proof data.
No global claim outside finite root box, no automatic CH39 attestor promotion.
"""
from __future__ import annotations
from fractions import Fraction as F
from decimal import Decimal as D
from collections import Counter
from itertools import combinations
import hashlib, json
from exact_decimal40 import IV, value, op, ROUND_CEILING


def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def digest(obj):return hashlib.sha256(canonical(obj)).hexdigest()


def det(a):
    n=len(a)
    if n==1:return a[0][0]
    if n==2:return a[0][0]*a[1][1]-a[0][1]*a[1][0]
    if n==3:return (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
                     -a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
                     +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
    raise ValueError('Only dimension 1–3')


def model_check(model):
    if not isinstance(model,dict) or type(model.get('d')) is not int or not 1<=model['d']<=3:
        raise ValueError('Dimension')
    d=model['d'];rows=model['rows']
    if not isinstance(rows,list) or not rows or type(model['n_raw']) is not int:
        raise ValueError('Empty model')
    if sum(r['n'] for r in rows)!=model['n_raw']:raise ValueError('Raw observation count')
    last=None;xx=[]
    for r in rows:
        if len(r['x'])!=d or type(r['n']) is not int or type(r['s']) is not int or not(0<=r['s']<=r['n']) or r['n']<=0:
            raise ValueError('Invalid design/outcome')
        x=tuple(F(str(q)) for q in r['x'])
        if last is not None and x==last: raise ValueError('Duplicate design')
        last=x;xx.append(x)
    basis=None
    for inds in combinations(range(len(rows)),d):
        v=det([xx[i] for i in inds])
        if v!=0:
            basis=(inds,v);break
        # A full-combinations search is unnecessary for 3 dimensions: after
        # scanning first nonzero minors among 160 rows it usually terminates.
    if basis is None:raise ValueError('Rank-deficient design')
    return xx,basis


def exact_partition(cert):
    nodes=cert['nodes'];root=cert['root_box']
    if type(nodes) is not list or not nodes or len(nodes)>127 or len(nodes[0]['box'])!=len(root):
        raise ValueError('Invalid proof-tree size/root dimension')
    if cert.get('parent_bound_inheritance') is not True: raise ValueError('No inherited-bound proof claim')
    if nodes[0]['box']!=root:raise ValueError('Root split tampered')
    seen=set();leaves=[]
    def walk(idx,box,parent=None,depth=0):
        if type(idx) is not int or idx in seen or idx<0 or idx>=len(nodes):raise ValueError('Invalid tree topology')
        seen.add(idx);node=nodes[idx]
        def pairs(v):return [(F(str(a)),F(str(b))) for a,b in v]
        a=pairs(node['box']);b=pairs(box)
        if node['id']!=idx or node['depth']!=depth or node.get('parent_id')!=parent or a!=b or any(x>=y for x,y in a):
            raise ValueError('Corrupted node parent, depth, or exact geometry')
        if pairs(node['effective_box'])!=a:
            # Original frozen certificates have no validated Newton shrinking.
            # A contraction would require its own independent Krawczyk proof.
            raise ValueError('Unverified contraction of proof domain')
        if 'newton' in node:raise ValueError('Independent Newton proof not supported in CH40-A')
        if node.get('bound_mode') not in ('direct','coupled'):raise ValueError('Invalid bound method')
        if 'children' not in node:
            leaves.append((idx,a));return
        kids=node['children'];axis=node.get('split_dim')
        if not isinstance(kids,list) or len(kids)!=2 or type(axis) is not int or not(0<=axis<len(a)):
            raise ValueError('Invalid split')
        if any(type(k) is not int or k<=idx for k in kids) or kids[0]==kids[1]:
            raise ValueError('Invalid child IDs')
        lo,hi=a[axis];mid=(lo+hi)/2
        left=list(a);right=list(a);left[axis]=(lo,mid);right[axis]=(mid,hi)
        walk(kids[0],left,idx,depth+1)
        walk(kids[1],right,idx,depth+1)
    walk(0,root)
    if len(seen)!=len(nodes) or len(leaves)!=cert['leaf_count']:
        raise ValueError('Incomplete or disconnected tree')
    if len(nodes)!=127:raise ValueError('CH40 frozen 127-node budget only')
    if cert.get('newton_exclusions')!=0 or cert.get('newton_contractions')!=0:
        raise ValueError('Independent Newton validation required')
    return leaves


class MathematicalModel:
    def __init__(self, model):
        self.model=model;self.x,ref=model_check(model)
        self.d=model['d'];self.counts=[(r['n'],r['s']) for r in model['rows']]
        self.X=[[IV.rational(v) for v in row] for row in self.x]
        self.X2=[[IV.rational(v*v) for v in row] for row in self.x]
        ids,d=ref;self.ref_coeff=IV.rational(d*d)
        for i in ids:self.ref_coeff=self.ref_coeff*model['rows'][i]['n']
        self.ref_ids=ids
        self.nn=len(model['rows'])

    def eta(self,box):
        B=[IV(a,b) for a,b in box]
        return [sum((B[j]*xs[j] for j in range(self.d)),IV(0)) for xs in self.X]

    def probability(self,z):return IV(1)/(IV(1)+(-z).exp())

    def weight(self,z):
        # w(z)=1/(2+exp(z)+exp(-z)), symmetric and unimodal around zero.
        def at(v):
            a=IV(v)
            return IV(1)/(IV(2)+a.exp()+(-a).exp())
        left=at(z.lo);right=at(z.hi)
        low=min(left.lo,right.lo)
        upper=D('0.25') if z.lo<=0<=z.hi else max(left.hi,right.hi)
        return IV.raw(low,upper)

    def info_det(self, weights, *, point=False):
        # All x_j^2 and w_j are nonnegative; Hadamard bounds det(I)
        # above by its diagonal product; one exact Cauchy–Binet minor
        # bounds det(I) below, independent of expansion/cancellation.
        lower=self.ref_coeff
        for i in self.ref_ids:lower=lower*weights[i]
        diag=[]
        for j in range(self.d):
            total=IV(0)
            for i,(n,s) in enumerate(self.counts):
                total=total + weights[i]*self.X2[i][j]*n
            diag.append(total)
        upper=IV(1)
        for col in diag:upper=upper*col
        bottom,top=lower.lo,upper.hi
        if point:
            # Different mathematical implementation: evaluate the actual
            # 3x3 determinant formula on the tiny point intervals rather than
            # CH24/CH29 Jet differentiation or Cauchy-Binet-only relaxation.
            matrix=[[IV(0) for _ in range(self.d)] for _ in range(self.d)]
            for j in range(self.d):
                matrix[j][j]=diag[j]
                for k in range(j+1,self.d):
                    v=IV(0)
                    for i,(n,_) in enumerate(self.counts):
                        v=v+weights[i]*self.X[i][j]*self.X[i][k]*n
                    matrix[j][k]=matrix[k][j]=v
            if self.d==3:
                a=matrix
                approx=(a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
                        -a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
                        +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
            elif self.d==2:
                approx=matrix[0][0]*matrix[1][1]-matrix[0][1]*matrix[1][0]
            else:approx=matrix[0][0]
            bottom=max(bottom,approx.lo)
            top=min(top,approx.hi)
        if bottom<=0 or top<bottom:
            raise ArithmeticError('Independent Fisher determinant enclosure invalid')
        return IV.raw(bottom,top)

    def objective_bound(self,box):
        zz=self.eta(box);weights=[];llupper=IV(0)
        for z,(n,s) in zip(zz,self.counts):
            weights.append(self.weight(z))
            # For the actual original data n=1 throughout. Extreme-outcome
            # likelihood is monotonic and its extrema are exact box endpoints.
            if s==0:
                llupper=llupper+(-((IV(1)+IV(z.lo).exp()).ln()))*n
            elif s==n:
                llupper=llupper+(-((IV(1)+(-IV(z.hi)).exp()).ln()))*n
            else:
                llupper=llupper+((z*s)-(IV(1)+z.exp()).ln()*n)
        detI=self.info_det(weights)
        return (llupper+IV('0.5')*detI.ln()).hi

    def incumbent_lower(self,inc):
        zz=self.eta([(v,v) for v in inc]);ll=IV(0)
        w=[]
        for z,(n,s) in zip(zz,self.counts):
            ll=ll + z*s - (IV(1)+z.exp()).ln()*n
            w.append(self.weight(z))
        return (ll+IV('0.5')*self.info_det(w,point=True).ln()).lo


def validate_duals(cert):
    Q=cert['dual_matrices'];d=cert['model']['d']
    if not isinstance(Q,list) or not Q:raise ValueError('Missing SPD dual matrix')
    for matrix in Q:
        if len(matrix)!=d or any(len(row)!=d for row in matrix):raise ValueError('Invalid dual size')
        a=[[F(str(v)) for v in row] for row in matrix]
        if any(a[i][j]!=a[j][i] for i in range(d) for j in range(d)):
            raise ValueError('Non-symmetric dual')
        if a[0][0]<=0 or (d>=2 and det([row[:2] for row in a[:2]])<=0) or (d==3 and det(a)<=0):
            raise ValueError('Non-SPD dual')
    return len(Q)


def verify_certificate(cert, *, mathematical_cap=127):
    if cert.get('milestone')!='CH-C14-29' or cert.get('claim_scope')!='finite_root_box_global_max_only' or cert.get('unbounded_global_claim') is not False:
        raise ValueError('Unrecognized original CH29 bounded certificate')
    if cert.get('production_release')!='NO_GO':raise ValueError('Scientific release cannot be promoted')
    if cert.get('status') not in ('UNRESOLVED_REFUSE_CERTIFICATION','CERTIFIED_BOUNDED_GAP'):
        raise ValueError('Invalid status')
    if digest(cert['model'])!=cert['model_sha256']:raise ValueError('Model digest')
    validate_duals(cert)
    leaves=exact_partition(cert)
    model=MathematicalModel(cert['model'])
    inc=[F(str(v)) for v in cert['incumbent']]
    if len(inc)!=model.d or any(not F(str(a))<=v<=F(str(b)) for v,(a,b) in zip(inc,cert['root_box'])):
        raise ValueError('Incumbent out of coefficient domain')
    # Use the exact serialized incumbent; never coerce through floating point.
    lower=model.incumbent_lower(cert['incumbent'])
    uppers=[]
    for j,(idx,box) in enumerate(leaves):
        if j>=mathematical_cap:raise ValueError('Explicit mathematical budget reached')
        # Converting rational mids/halves back to decimal is exact only for
        # terminating rationals; original split bounds are dyadic/decimal.
        bd=[]
        for a,b in box:
            def dec(t):
                n=t.denominator;k=n
                while k%2==0:k//=2
                while k%5==0:k//=5
                if k!=1:raise ValueError('Nonterminating split fraction')
                # Deterministic exact decimal rendering of a dyadic/5-adic fraction.
                u=t.denominator; twos=fives=0
                while u%2==0: u//=2;twos+=1
                while u%5==0: u//=5;fives+=1
                scale=max(twos,fives)
                integer=abs(t.numerator)*5**(scale-fives)*2**(scale-twos)
                digits=str(integer).zfill(scale+1)
                decstr=digits if scale==0 else digits[:-scale]+'.'+digits[-scale:]
                return ('-' if t<0 else '')+decstr
            bd.append((dec(a),dec(b)))
        upper=model.objective_bound(bd)
        uppers.append(upper)
    ceiling=max(uppers)
    tol=D(str(cert['tolerance']))
    if tol<=0:raise ValueError('Invalid threshold')
    threshold=op('add',lower,tol,ROUND_CEILING)
    independ_proven=all(u<=threshold for u in uppers)
    if cert['status']=='CERTIFIED_BOUNDED_GAP' and not independ_proven:
        raise ValueError('Independently recomputed bounds refute certification claim')
    return {'case_identity':cert['original_data_identity'],'nodes_geometry_verified':len(cert['nodes']),
            'leaf_bounds_independently_recomputed':len(uppers),'independent_upper_ceil':str(ceiling),
            'independent_incumbent_lower':str(lower),'independent_gap_ceiling':str(op('sub',ceiling,lower,ROUND_CEILING)),
            'bounded_gap_proven_by_independent_checker':independ_proven,
            'original_status':cert['status'],'methods':'independent Decimal-directed loglik + Cauchy-Binet minor + Hadamard Fisher',
            'limitation':'Conservative independent finite-box upper; does not validate each producer local coupled or Newton bound; no global R^d claim.',
            'scientific_release':'NO_GO'}
