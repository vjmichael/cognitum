"""CH-C14-24: branch-and-bound *bounded-box* Firth-logistic maxima.

Research-only. No production estimator/causal/CI promotion. MPFR directed
rounding encloses J, gradient, Hessian. A certificate is usable ONLY when its
root-to-leaf partition and every leaf's upper bound are independently replayed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
import hashlib
import heapq
import itertools
import json
import math
import time

from mpfr_interval import Interval as I, MP, up_abs, checked_threshold, DOWN, UP


def exact_decimal(x):
    if not isinstance(x, (str, int, Decimal)) or isinstance(x, bool):
        raise TypeError("All numeric inputs must be exact decimal strings or integers")
    if len(str(x))>160:
        raise ValueError("Decimal input exceeds bounded parsing size")
    d = Decimal(str(x))
    if not d.is_finite() or abs(d.as_tuple().exponent)>1000:
        raise ValueError("Nonfinite or excessively scaled input")
    return str(d)


def terminating_fraction_string(value: Fraction):
    """Exact base-10 rendering of a rational with denominator 2**a * 5**b."""
    den=value.denominator
    a=b=0
    while den%2==0:
        den//=2;a+=1
    while den%5==0:
        den//=5;b+=1
    if den!=1:raise ValueError('Nonterminating decimal fraction')
    places=max(a,b)
    scaled=abs(value.numerator)*(2**(places-a))*(5**(places-b))
    digits=str(scaled).zfill(places+1)
    literal=digits if not places else digits[:-places]+'.'+digits[-places:]
    if '.' in literal:literal=literal.rstrip('0').rstrip('.')
    return ('-' if value<0 else '')+literal


def rank_exact(matrix):
    rows = [[Fraction(z) for z in row] for row in matrix]
    if not rows:
        return 0
    ncol = len(rows[0]); rank = 0
    for col in range(ncol):
        pivot = next((i for i in range(rank, len(rows)) if rows[i][col]), None)
        if pivot is None: continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        pv = rows[rank][col]
        for i in range(rank + 1, len(rows)):
            if rows[i][col]:
                fac = rows[i][col] / pv
                for j in range(col, ncol): rows[i][j] -= fac * rows[rank][j]
        rank += 1
    return rank


def determinant(m):
    d = len(m)
    if d == 1: return m[0][0]
    if d == 2: return m[0][0]*m[1][1] - m[0][1]*m[1][0]
    if d == 3:
        a = m
        return (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
              - a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
              + a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
    raise ValueError("Only 1..3 coefficients supported")


class Jet:
    """Order-two forward automatic differentiation using directed intervals."""
    __slots__ = ("v", "g", "h", "d")

    def __init__(self, v, g, h):
        self.v = I.coerce(v)
        self.g, self.h = g, h
        self.d = len(g)

    @classmethod
    def const(cls, x, d):
        return cls(I.coerce(x), [I(0) for _ in range(d)],
                   [[I(0) for _ in range(d)] for _ in range(d)])

    @classmethod
    def variable(cls, x, d, k):
        j = cls.const(x, d)
        j.g[k] = I(1)
        return j

    def cast(self, o):
        return o if isinstance(o, Jet) else self.const(o, self.d)

    def __add__(self, o):
        o=self.cast(o)
        return Jet(self.v+o.v,
                   [self.g[i]+o.g[i] for i in range(self.d)],
                   [[self.h[i][j]+o.h[i][j] for j in range(self.d)] for i in range(self.d)])
    __radd__ = __add__

    def __neg__(self):
        return Jet(-self.v, [-g for g in self.g], [[-h for h in row] for row in self.h])

    def __sub__(self, o):
        return self + -self.cast(o)

    def __rsub__(self, o):
        return self.cast(o) - self

    def __mul__(self, o):
        o=self.cast(o)
        return Jet(self.v*o.v,
                   [self.g[i]*o.v + self.v*o.g[i] for i in range(self.d)],
                   [[self.h[i][j]*o.v + self.g[i]*o.g[j]
                     + self.g[j]*o.g[i] + self.v*o.h[i][j] for j in range(self.d)]
                    for i in range(self.d)])
    __rmul__ = __mul__

    def compose(self, value, first, second):
        return Jet(value, [first*g for g in self.g],
                   [[second*self.g[i]*self.g[j]+first*self.h[i][j]
                     for j in range(self.d)] for i in range(self.d)])

    def reciprocal(self):
        inv = I(1)/self.v
        return self.compose(inv, -(inv*inv), I(2)*inv*inv*inv)

    def __truediv__(self, o):
        return self*self.cast(o).reciprocal()

    def __rtruediv__(self, o):
        return self.cast(o)*self.reciprocal()

    def exp(self):
        e=self.v.exp()
        return self.compose(e,e,e)

    def log(self):
        inv=I(1)/self.v
        return self.compose(self.v.log(), inv, -(inv*inv))


def logistic_model(rows):
    """Validate exact x and binary y; group repeated design rows exactly."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("Nonempty rows required")
    canonical=[]
    d=None
    for r in rows:
        x = r["x"]
        y = r["y"]
        if d is None: d=len(x)
        if d < 1 or d > 3 or len(x)!=d or y not in (0,1) or isinstance(y,bool):
            raise ValueError("Bad predictor dimension or nonbinary outcome")
        canonical.append((tuple(exact_decimal(v) for v in x), int(y)))
    if rank_exact([x for x,y in canonical]) != d:
        raise ValueError("Design must have exact full column rank")
    groups=defaultdict(lambda: [0,0])
    for x,y in canonical:
        groups[x][0] += 1
        groups[x][1] += y
    grouped=[(x, *groups[x]) for x in sorted(groups)]
    return {"d":d,"rows":[{"x":list(x),"n":n,"s":s} for x,n,s in grouped],
            "n_raw":len(rows)}


class FirthObjective:
    def __init__(self, data):
        self.data=data
        self.d=data["d"]
        self.groups=[(tuple(I(x) for x in row["x"]),row["n"],row["s"])
                     for row in data["rows"]]
        if self.d not in (1,2,3): raise ValueError("Dimension invalid")
        # Reference nonzero Cauchy-Binet minor establishes a *positive lower*
        # bound on the determinant even when interval Leibniz expansion has
        # cancellation. This makes point-witness lower bounds sound as well.
        basis=[]
        for i,r in enumerate(self.data['rows']):
            trial=basis+[i]
            if rank_exact([self.data['rows'][j]['x'] for j in trial])>len(basis):
                basis=trial
            if len(basis)==self.d:break
        if len(basis)!=self.d:raise ValueError('Not full rank')
        self.reference_minor=(tuple(basis),self._minor_coefficient(tuple(basis)))
        # Optional exact-positive sum on up to 20 distinct design vectors.
        self.minors=[]
        if len(self.groups)<=20 and self.d>=2:
            for inds in itertools.combinations(range(len(self.groups)),self.d):
                coeff=self._minor_coefficient(inds)
                if coeff is not None:self.minors.append((inds,coeff))

    def _minor_coefficient(self, inds):
        mat=[[Fraction(self.data['rows'][i]['x'][j]) for j in range(self.d)]
             for i in inds]
        if self.d==1:detx=mat[0][0]
        elif self.d==2:
            detx=mat[0][0]*mat[1][1]-mat[0][1]*mat[1][0]
        else:
            detx=mat[0][0]*(mat[1][1]*mat[2][2]-mat[1][2]*mat[2][1]) \
                - mat[0][1]*(mat[1][0]*mat[2][2]-mat[1][2]*mat[2][0]) \
                + mat[0][2]*(mat[1][0]*mat[2][1]-mat[1][1]*mat[2][0])
        if not detx:return None
        coeff=detx*detx
        for i in inds:coeff*=self.data['rows'][i]['n']
        return I(str(coeff.numerator))/I(str(coeff.denominator))

    def _weight_enclosure(self, eta):
        # w(eta)=logistic(eta)(1-logistic(eta)) is unimodal, max at 0.
        # Endpoint enclosures and w(0)=1/4 give a dependency-resistant box.
        endpoints=[]
        for v in (eta.lo,eta.hi):
            z=I.from_ends(v,v)
            endpoints.append(I(1)/(I(2)+z.exp()+(-z).exp()))
        lo=endpoints[0].lo
        for v in endpoints[1:]:
            if v.lo.cmp(lo)<0:lo=v.lo
        hi=endpoints[0].hi
        for v in endpoints[1:]:
            if v.hi.cmp(hi)>0:hi=v.hi
        if eta.lo.cmp(MP(0))<=0 and eta.hi.cmp(MP(0))>=0:
            p=MP('0.25',UP)
            if p.cmp(hi)>0:hi=p
        return I.from_ends(lo,hi)

    def _separate_loglik_upper(self, beta):
        # Each grouped binomial term is concave in its scalar predictor.
        # For s=0 / s=n the term is monotonic. For mixed counts its
        # unrestricted maximum is the negative binary entropy.
        result=I(0)
        for xx,n,s in self.groups:
            eta=sum((xx[j]*beta[j] for j in range(self.d)),I(0))
            term=eta*s - (eta.exp()+I(1)).log()*n
            if s==0:
                z=I.from_ends(eta.lo,eta.lo)
                cap=-(z.exp()+I(1)).log()*n
            elif s==n:
                z=I.from_ends(eta.hi,eta.hi)
                cap=z*n-(z.exp()+I(1)).log()*n
            else:
                a=I(s)/I(n)
                b=I(n-s)/I(n)
                cap=I(s)*a.log()+I(n-s)*b.log()
            hi=term.hi if term.hi.cmp(cap.hi)<=0 else cap.hi
            result=result+I.from_ends(hi,hi)
        return result

    def _evaluate(self, b, derivatives=False):
        d=self.d
        if len(b)!=d: raise ValueError("Dimension mismatch")
        if derivatives:
            beta=[Jet.variable(b[j],d,j) for j in range(d)]
            ll=Jet.const(0,d)
            info=[[Jet.const(0,d) for _ in range(d)] for _ in range(d)]
        else:
            beta=b
            ll=I(0)
            info=[[I(0) for _ in range(d)] for _ in range(d)]
        one=I(1)
        weights=[]
        for xx,n,s in self.groups:
            eta=sum((beta[j]*xx[j] for j in range(d)), Jet.const(0,d) if derivatives else I(0))
            ep=eta.exp()
            soft=(ep+one).log()
            ll=ll + eta*s - soft*n
            # w = exp(eta)/(1+exp(eta))^2; algebraically exact.
            denom=(-eta).exp()+one
            p=denom.reciprocal() if derivatives else one/denom
            w=p*(1-p) if derivatives else self._weight_enclosure(eta)
            weights.append(w)
            for j in range(d):
                for k in range(j,d):
                    info[j][k]=info[j][k] + w*(n*xx[j]*xx[k])
        for j in range(d):
            for k in range(j): info[j][k]=info[k][j]
        det=determinant(info)
        return ll, info, det, weights

    def objective(self, box):
        """Sound interval J, including a positive determinant lower bound.

        det(I) >= det(X_S)^2 * product(n_s*w_s) by Cauchy-Binet.
        Hadamard provides the upper det bound. All inequalities remain valid
        when determinant's naive interval expansion contains zero.
        """
        ll,info,det,weights=self._evaluate(box)
        ref_indices,ref_coeff=self.reference_minor
        refdet=ref_coeff
        for i in ref_indices:refdet=refdet*weights[i]
        if refdet.lo.cmp(MP(0))<=0:
            raise ArithmeticError('Cannot establish positive determinant minor: refuse')
        low=refdet.lo
        if det.lo.cmp(low)>0:low=det.lo
        hadamard=I(1)
        for j in range(self.d): hadamard=hadamard*info[j][j]
        high=hadamard.hi
        if det.hi.cmp(high)<0:high=det.hi
        method='reference_minor_hadamard'
        if self.minors:
            cb=I(0)
            for inds,coeff in self.minors:
                term=coeff
                for i in inds:term=term*weights[i]
                cb=cb+term
            if cb.lo.cmp(low)>0:low=cb.lo
            if cb.hi.cmp(high)<0:high=cb.hi
            method='cauchy_binet'
        if low.cmp(high)>0:
            raise ArithmeticError('Inconsistent independent determinant enclosures')
        logdet=I.from_ends(low,high).log()
        full=ll+I('0.5')*logdet
        if self.minors:
            separable=self._separate_loglik_upper(box)+I('0.5')*logdet
            if separable.hi.cmp(full.hi)<0:
                if full.lo.cmp(separable.hi)>0:
                    raise ArithmeticError('Inconsistent objective bounds')
                full=I.from_ends(full.lo,separable.hi)
                method='cauchy_binet_entropy'
        return full,method

    def jet(self, box):
        ll,info,det,_=self._evaluate(box, derivatives=True)
        if det.v.lo.cmp(MP(0))<=0:
            raise ArithmeticError("Interval determinant crosses zero: curvature unavailable")
        return ll + det.log()*I('0.5')


def midpoint_bounds(box):
    # No context rounding: both midpoint and half-width are *exact rationals*
    # with terminating decimal expansions for finite decimal endpoints.
    mid=[terminating_fraction_string((Fraction(a)+Fraction(b))/2) for a,b in box]
    radius=[terminating_fraction_string((Fraction(b)-Fraction(a))/2) for a,b in box]
    return mid,radius


def interval_box(box):
    return [I(a,b) for a,b in box]


def bound_node(model, box, curvature=True):
    direct, source=model.objective(interval_box(box))
    best=direct
    method=source
    if curvature:
        try:
            mid,radius=midpoint_bounds(box)
            center=model.jet([I(x) for x in mid])
            region=model.jet(interval_box(box))
            # Taylor in closed box, with point interval first derivative and
            # interval Hessian on the full box. The products are outward-rounded.
            linear=I(0)
            diag_cross=I(0)
            for j in range(model.d):
                linear=linear + up_abs(center.g[j])*I(radius[j])
                h_jj=region.h[j][j]
                if h_jj.hi.cmp(MP(0))>0:
                    # [0,max(0,Hjj.upper)] encloses the *positive* diagonal term.
                    diag_cross=diag_cross + I('0.5')*I.from_ends(MP(0),h_jj.hi)*I(radius[j])*I(radius[j])
                for k in range(j+1,model.d):
                    diag_cross=diag_cross+up_abs(region.h[j][k])*I(radius[j])*I(radius[k])
            # Hessian Gershgorin row upper: lambda_max(H) <= max_j (Hjj+sum |Hjk|).
            row_uppers=[]
            for j in range(model.d):
                upper=I.from_ends(region.h[j][j].hi,region.h[j][j].hi)
                for k in range(model.d):
                    if j!=k: upper=upper+up_abs(region.h[j][k])
                row_uppers.append(upper.hi)
            lam=row_uppers[0]
            for z in row_uppers[1:]:
                if z.cmp(lam)>0: lam=z
            # Diagonal/cross bound is always valid (positive diagonal part).
            taylor=center.v + linear + diag_cross
            if taylor.hi.cmp(best.hi)<0:
                best=taylor;method="interval_hessian_taylor"
            # If H(B) <= -m I, complete the square: f(x)<= f(c)+||g(c)||^2/(2m).
            if lam.cmp(MP(0))<0:
                m=-I.from_ends(lam,lam)
                gradsq=I(0)
                for g in center.g:
                    q=up_abs(g)
                    gradsq=gradsq+q*q
                strong=center.v + gradsq/(I(2)*m)
                if strong.hi.cmp(best.hi)<0:
                    best=strong;method="negative_curvature_completed_square"
        except ArithmeticError:
            pass  # Det interval unresolved; split using valid fallback instead.
    return best,method


def candidate_lower(model, coords):
    f,_=model.objective([I(x) for x in coords])
    return f.lo


def model_digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def solve(rows, bounds, *, tol='0.0001', max_nodes=1000, precision_bits=160,
          seeds=None, use_curvature=True):
    import mpfr_interval as impl
    if not isinstance(max_nodes,int) or isinstance(max_nodes,bool) or max_nodes<1:
        raise ValueError("max_nodes must be positive")
    if precision_bits < 80 or precision_bits > 4096:
        raise ValueError("MPFR precision must be 80..4096 bits")
    impl.PRECISION=precision_bits
    tol=exact_decimal(tol)
    if Decimal(tol)<=0: raise ValueError("Tolerance must be positive")
    data=logistic_model(rows)
    boxes=[]
    if len(bounds)!=data['d']: raise ValueError("Bad root box dimension")
    for lo,hi in bounds:
        a,b=exact_decimal(lo), exact_decimal(hi)
        if Decimal(a)>=Decimal(b): raise ValueError("Box widths must be positive")
        boxes.append([a,b])
    model=FirthObjective(data)
    root_point,_=midpoint_bounds(boxes)
    lb=candidate_lower(model, root_point)
    incumbent=root_point
    for s in seeds or []:
        s=[exact_decimal(z) for z in s]
        if len(s)!=data['d'] or any(not (Decimal(a)<=Decimal(v)<=Decimal(b)) for v,(a,b) in zip(s,boxes)):
            raise ValueError("Seed outside finite root box")
        v=candidate_lower(model,s)
        if v.cmp(lb)>0: lb=v;incumbent=s
    rootbound,method=bound_node(model,boxes,use_curvature)
    nodes=[{'id':0,'box':boxes,'upper_bound':rootbound.upper_float(), 'method':method}]
    queue=[(-rootbound.upper_float(),0,rootbound.hi)]
    popped=0
    while queue and len(nodes)<max_nodes:
        _,idx,ub=heapq.heappop(queue)
        node=nodes[idx]
        if checked_threshold(ub,lb,tol):
            node['closed']='bound_below_incumbent_plus_tolerance'
            continue
        box=node['box']
        mid,rad=midpoint_bounds(box)
        candidate=candidate_lower(model,mid)
        if candidate.cmp(lb)>0: lb=candidate;incumbent=mid
        if checked_threshold(ub,lb,tol):
            node['closed']='bound_below_incumbent_plus_tolerance'
            continue
        # Split widest dimension by exact decimal width. Never split at an endpoint.
        widths=[Decimal(b)-Decimal(a) for a,b in box]
        dim=max(range(data['d']),key=lambda i:widths[i])
        if widths[dim]<=0: node['closed']='unsplittable';break
        if len(nodes)+2>max_nodes: heapq.heappush(queue,(-ub.as_float(UP),idx,ub));break
        left=[pair[:] for pair in box];right=[pair[:] for pair in box]
        left[dim][1]=mid[dim];right[dim][0]=mid[dim]
        if not (Decimal(left[dim][0])<Decimal(left[dim][1]) and Decimal(right[dim][0])<Decimal(right[dim][1])):
            node['closed']='unsplittable'; break
        node['split_dim']=dim
        node['children']=[len(nodes),len(nodes)+1]
        for child_box in (left,right):
            bnd, meth=bound_node(model,child_box,use_curvature)
            number=len(nodes)
            nodes.append({'id':number,'box':child_box,'upper_bound':bnd.upper_float(),'method':meth})
            heapq.heappush(queue,(-bnd.upper_float(),number,bnd.hi))
        popped += 1
    # Collect leaves regardless of priority; truncated searches remain unresolved.
    leaves=[n for n in nodes if 'children' not in n]
    # Recompute genuine upper endpoints rather than relying on float displays.
    uppers=[]
    methods={}
    for leaf in leaves:
        bound,method=bound_node(model,leaf['box'],use_curvature)
        uppers.append(bound.hi)
        methods[method]=methods.get(method,0)+1
    maxupper=uppers[0]
    for v in uppers[1:]:
        if v.cmp(maxupper)>0:maxupper=v
    certified=all(checked_threshold(u,lb,tol) for u in uppers)
    return {
        'milestone':'CH-C14-24', 'claim_scope':'finite_root_box_only',
        'status':'CERTIFIED_BOUNDED_GAP' if certified else 'UNRESOLVED_REFUSE_CERTIFICATION',
        'precision_bits':precision_bits, 'tolerance':tol,
        'objective':'Jeffreys_penalized_binomial_logistic',
        'model':data,'model_sha256':model_digest(data),
        'root_box':boxes, 'incumbent':incumbent,
        'lower_bound_floor_display':lb.as_float(DOWN),
        'upper_bound_ceil_display':maxupper.as_float(2),
        'nodes':nodes, 'leaf_count':len(leaves), 'split_count':popped,
        'leaf_methods':methods, 'production_release':'NO_GO',
        'note':'Every bound is recomputed and proof coverage checked by verify_certificate.py; floats are display only.'
    }


def cli():
    p=argparse.ArgumentParser()
    p.add_argument('input', help='JSON with rows [{x:[decimal strings],y:0|1}], bounds [[lo,hi],...]')
    p.add_argument('--output',default='certificate.json')
    p.add_argument('--tol',default='0.001')
    p.add_argument('--max-nodes',type=int,default=1000)
    p.add_argument('--bits',type=int,default=160)
    p.add_argument('--no-curvature',action='store_true')
    a=p.parse_args()
    input_data=json.load(open(a.input))
    result=solve(input_data['rows'],input_data['bounds'],tol=a.tol,
                 max_nodes=a.max_nodes,precision_bits=a.bits,
                 seeds=input_data.get('seeds'),use_curvature=not a.no_curvature)
    with open(a.output,'w') as f:json.dump(result,f,indent=2)
    print(result['status'], 'nodes=',len(result['nodes']),
          'upper=',result['upper_bound_ceil_display'], 'lower=',result['lower_bound_floor_display'])

if __name__=='__main__': cli()
