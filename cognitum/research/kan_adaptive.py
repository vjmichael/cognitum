"""COG-04D bounded adaptive polynomial KAN research; no approval or new route.
Exact represented-parameter certificates, not learned-target accuracy claims.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import comb
import numpy as np
from .kan_trainable import Layer, Network, _array, _need
from cognitum.mel import polynomial_witness as w


def q(x): return Q(float(x))


def _profile(model):
    _need(type(model) is Network and all(l.kind in ('spline_clamped','chebyshev') for l in model.layers), 'polynomial profile')
    return model


def _edge_poly(l,o,i,a,b):
    g=tuple(map(q,l.grid[i])); mid=(a+b)/2
    if l.kind=='chebyshev': basis=w.cheb_polys(*g,l.degree)
    else:
        span=next(j for j in range(len(g)-1) if g[j]<=mid<g[j+1])
        basis=w.spline_polys(g,l.degree,span)
    p=(Q(0),)
    for c,base in zip(l.coefficients[o,i],basis):
        p=w.plus(p,w.scale(base,q(c)*q(l.mask[o,i])))
    return p


def _bernstein(p,a,b):
    # Exact monomial -> normalized [0,1] power -> Bernstein coefficients.
    n=len(p)-1; d=b-a
    power=[w.cap(sum((p[k]*comb(k,j)*a**(k-j)*d**j for k in range(j,n+1)),Q(0))) for j in range(n+1)]
    c=[w.cap(sum((power[j]*Q(comb(i,j),comb(n,j)) for j in range(i+1)),Q(0))) for i in range(n+1)]
    return min(c),max(c)


def _pieces(l,r,o,i,derivative=False):
    g=tuple(map(q,l.grid[i])); h=tuple(map(q,r.grid[i]));_need(g[0]==h[0] and g[-1]==h[-1],'domain mismatch')
    cuts=sorted(set(g+h)); ranges=[]; differences=[]; slopes=[]
    for a,b in zip(cuts,cuts[1:]):
        p=_edge_poly(l,o,i,a,b); s=_edge_poly(r,o,i,a,b)
        ranges.append(_bernstein(p,a,b));differences.append(_bernstein(w.plus(s,w.scale(p,Q(-1))),a,b))
        if derivative:slopes.append(_bernstein(w.diff(p),a,b))
    def hull(v): return min(x[0] for x in v),max(x[1] for x in v)
    return hull(ranges),hull(differences),hull(slopes) if derivative else None


def _abs(b):return max(abs(b[0]),abs(b[1]))


@dataclass(frozen=True,slots=True)
class Certificate:
    before_sha256:str
    after_sha256:str
    layer_error_upper:tuple
    output_error_upper:tuple
    # Full declared input domain; ideal represented functions, not float64 evaluation roundoff.


def certify(before,after):
    """Full-domain uniform error; refuses incompatible or unproved intermediate domains.

    Bernstein hulls on common knot spans bound exact residual polynomials. The
    reference layer's slope bounds propagate earlier errors via the mean-value
    inequality; degree-one clamped splines are continuous and piecewise smooth.
    Both networks' intermediate ranges must fit the next layer's declared box.
    """
    _profile(before);_profile(after);_need(len(before.layers)==len(after.layers),'layer count mismatch')
    errors=[Q(0)]*before.layers[0].inputs; receipts=[]
    for idx,(l,r) in enumerate(zip(before.layers,after.layers)):
        _need((l.inputs,l.outputs)==(r.inputs,r.outputs),'layer shape mismatch')
        local=[]; propagated=[]; ranges_l=[];ranges_r=[]
        for o in range(l.outputs):
            delta=q(r.bias[o])-q(l.bias[o]); dl=dh=delta;lo=hi=q(l.bias[o]); ro=rh=q(r.bias[o]); e=Q(0)
            for i in range(l.inputs):
                v,d,s=_pieces(l,r,o,i,True); rv,_,_=_pieces(r,l,o,i)
                lo+=v[0];hi+=v[1];ro+=rv[0];rh+=rv[1]; dl+=d[0];dh+=d[1]; e+=_abs(s)*errors[i]
            local.append(_abs((dl,dh)));propagated.append(w.cap(e+local[-1]));ranges_l.append((lo,hi));ranges_r.append((ro,rh))
        if idx+1<len(before.layers):
            for layer,ranges in ((before.layers[idx+1],ranges_l),(after.layers[idx+1],ranges_r)):
                _need(all(q(layer.grid[i,0])<=a<=b<=q(layer.grid[i,-1]) for i,(a,b) in enumerate(ranges)),'intermediate domain not certified')
        receipts.append(tuple(w.outward(x,True) for x in local));errors=propagated
    return Certificate(before.research_snapshot()[1],after.research_snapshot()[1],tuple(receipts),tuple(w.outward(x,True) for x in errors))


def refine(model,layer_index,knots,max_error=1e-10):
    """One simple interior insertion per coordinate (rectangular grid profile).

    Boehm coefficient transport is exact rational arithmetic up to one explicit
    binary64 rounding. The independent common-span verifier checks the actual
    rounded model, not merely the theoretical insertion identity.
    """
    _profile(model);_need(type(layer_index) is int and 0<=layer_index<len(model.layers),'layer index')
    l=model.layers[layer_index];_need(l.kind=='spline_clamped' and l.grid.shape[1]<12,'refinement budget/profile')
    t=_array(knots);_need(t.shape==(l.inputs,),'one knot per input');p=l.degree;grids=[];coeff=np.zeros((*l.coefficients.shape[:2],l.coefficients.shape[2]+1))
    for i,v in enumerate(t):
        g=tuple(map(q,l.grid[i]));v=q(v);_need(g[0]<v<g[-1] and all(abs(v-k)>=q(1e-4) for k in g),'interior separated knot required')
        k=next(j for j in range(len(g)-1) if g[j]<v<g[j+1]);grids.append([float(a) for a in (*g[:k+1],v,*g[k+1:])])
        for o in range(l.outputs):
            c=list(map(q,l.coefficients[o,i]));new=[]
            for j in range(len(c)+1):
                if j<=k-p: val=c[j]
                elif j>k:val=c[j-1]
                else:
                    alpha=(v-g[j])/(g[j+p]-g[j]);val=(1-alpha)*c[j-1]+alpha*c[j]
                new.append(float(val))
            coeff[o,i]=new
    layers=list(model.layers);layers[layer_index]=Layer(l.kind,p,grids,coeff,l.mask,l.bias);out=Network(tuple(layers));cert=certify(model,out)
    _budget(cert,max_error);return out,cert


def _budget(cert,limit):
    _need(type(limit) in (float,int) and 0<=limit<=1 and max(cert.output_error_upper)<=limit,'certified error budget exceeded')


def prune(model,max_error,max_edges=4):
    """Deterministic backward edge deletion under a cumulative full-domain budget.

    Candidate order by coefficient magnitude is heuristic; actual acceptance is
    independent certified output error relative to ORIGINAL model. No regrowth.
    """
    _profile(model);_need(type(max_edges) is int and 0<=max_edges<=16,'prune limit');_budget(certify(model,model),max_error)
    choices=sorted((float(np.max(np.abs(l.coefficients[o,i]))),k,o,i) for k,l in enumerate(model.layers) for o in range(l.outputs) for i in range(l.inputs) if l.mask[o,i]);out=model;gone=[]
    for _,k,o,i in choices:
        if len(gone)>=max_edges:break
        l=out.layers[k];m=l.mask.copy();m[o,i]=0;ls=list(out.layers);ls[k]=Layer(l.kind,l.degree,l.grid,l.coefficients,m,l.bias);trial=Network(tuple(ls))
        try:_budget(certify(model,trial),max_error)
        except ValueError:continue
        out=trial;gone.append((k,o,i))
    return out,tuple(gone),certify(model,out)


def adaptive_fit(model,x,y,steps=2,ridge=1e-8):
    """Single-layer supervised adaptive refinement. Pick high residual spans
    from training points only, transport before refit, retain strict MSE gain.
    No held-out data used for tuning. Refitting changes the represented function.
    """
    _profile(model);_need(len(model.layers)==1 and model.layers[0].kind=='spline_clamped' and type(steps) is int and 0<=steps<=4,'adaptive fit profile')
    x,y=_array(x),_array(y);out=model.fit_linear(x,y,ridge);err=float(np.mean((out.evaluate(x)[0]-y)**2));history=[]
    for _ in range(steps):
        l=out.layers[0]
        if l.grid.shape[1]>=12:break
        residual=np.sum((out.evaluate(x)[0]-y)**2,axis=1);knots=[]
        for i in range(l.inputs):
            g=np.unique(l.grid[i]);scores=[]
            for a,b in zip(g,g[1:]):
                c=(a+b)/2
                if min(c-a,b-c)>=1e-4:
                    scores.append((float(residual[(x[:,i]>=a)&((x[:,i]<b)|((b==g[-1])&(x[:,i]==b)))].sum()),-float(a),float(c)))
            if not scores:break
            knots.append(max(scores)[-1])
        if len(knots)!=l.inputs:break
        transport,cert=refine(out,0,knots);trial=transport.fit_linear(x,y,ridge);new=float(np.mean((trial.evaluate(x)[0]-y)**2))
        if new>=err:break
        history.append(dict(knots=knots,before_mse=err,after_mse=new,transport_error_upper=cert.output_error_upper,transport_sha256=cert.after_sha256,refit_sha256=trial.research_snapshot()[1]));out,err=trial,new
    return out,tuple(history)


def compose_fit(feature,head,x,y,ridge=1e-8):
    """Frozen learned feature layer reused; fit a separate head on its outputs.

    Full-domain intermediate validity is checked via the same exact verifier.
    Held-out generalization must be assessed separately by the caller.
    """
    _profile(feature);_profile(head);_need(len(feature.layers)==len(head.layers)==1,'two layer composition profile')
    z=feature.evaluate(x)[0];fitted=head.fit_linear(z,y,ridge);out=Network(feature.layers+fitted.layers);certify(out,out);return out
