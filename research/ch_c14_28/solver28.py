"""CH28 bounded-box research branch-and-bound with reusable certified node bounds.

The cache is a *speed optimization* only. Verifier28 independently evaluates
all terminal leaves at higher MPFR precision using the recorded bound mode.
Neither the cache nor any binary64 priority decision can establish a proof.
"""
from __future__ import annotations
import sys,time,heapq
from decimal import Decimal
from pathlib import Path
D=Path(__file__).resolve().parent
BASE=D.parent
for dir in ('CH_C14_24','CH_C14_26','CH_C14_27'):
    sys.path.insert(0,str(BASE/dir))
import mpfr_interval as impl
from mpfr_interval import Interval as I,MP,DOWN,UP,checked_threshold
from verified_bnb import logistic_model,midpoint_bounds,model_digest,interval_box
from coupled27 import CoupledObjective
from interval_newton27 import contract,interior

def _score(model,point):
    return model.objective([I(x) for x in point])[0].lo

def bound_by_mode(model,box,mode):
    """All modes return *certified* upper bounds, not heuristic estimates."""
    direct,_=model.objective(interval_box(box))
    if mode=='direct':
        return direct,'loewner_gram_plus_binomial_envelope'
    if mode!='coupled':
        raise ValueError('Unknown upper bound mode')
    cap=model.coupled_upper(box)
    if cap.cmp(direct.hi)<0:
        if cap.cmp(direct.lo)<0:
            raise ArithmeticError('Inconsistent outward-rounded upper bound')
        return I.from_ends(direct.lo,cap),'coupled_logdet_dual'
    return direct,'loewner_gram_plus_binomial_envelope'

def solve(inp,proto,duals):
    impl.PRECISION=proto['precision_bits']
    d=logistic_model(inp['rows']);root=inp['bounds'];seeds=inp['seeds']
    if len(root)!=d['d'] or any(Decimal(a)>=Decimal(b) for a,b in root):
        raise ValueError('Invalid original box')
    for s in seeds:
        if len(s)!=d['d'] or any(not Decimal(a)<=Decimal(v)<=Decimal(b) for v,(a,b) in zip(s,root)):
            raise ValueError('Invalid original seed')
    model=CoupledObjective(d,duals)
    model.set_tangents(seeds[:1])
    mid,_=midpoint_bounds(root); incumbent=mid; lower=_score(model,mid)
    for s in seeds:
        value=_score(model,s)
        if value.cmp(lower)>0:incumbent=s;lower=value
    budget=int(proto['node_budget_per_case'])
    if budget<1:raise ValueError('Invalid budget')
    tol=proto['objective_absolute_tolerance']
    gate=Decimal(proto['newton_max_side_width'])
    newton_budget=proto['max_newton_evaluations_per_case']
    counts={'direct':0,'coupled':0,'cached_leaf':0,'newton':0,'contractions':0,'exclusions':0,'no_gain':0,'early_pruned':0,'dual_improved':0}
    nodes=[];heap=[];cached={}
    started=time.perf_counter()
    def add(box,depth):
        nonlocal lower,incumbent
        idx=len(nodes)
        rec={'id':idx,'depth':depth,'box':box,'effective_box':box}
        if counts['newton']<newton_budget and interior(box,root) and max(Decimal(b)-Decimal(a) for a,b in box)<=gate:
            counts['newton']+=1
            try:attempt=contract(model,box,root)
            except (ArithmeticError,ValueError):attempt={'status':'NO_GAIN','reason':'NUMERICAL_UNAVAILABLE'}
            if attempt['status']=='CONTRACTED':
                rec['newton']=attempt;rec['effective_box']=attempt['box'];counts['contractions']+=1
            elif attempt['status']=='NO_STATIONARY':
                rec['newton']=attempt;counts['exclusions']+=1
            else:counts['no_gain']+=1
        if rec.get('newton',{}).get('status')!='NO_STATIONARY':
            direct,_=model.objective(interval_box(rec['effective_box']))
            counts['direct']+=1
            # Only exact MPFR directed endpoint comparisons affect the proof threshold.
            # Other selective gates solely affect efficiency and node priority.
            if checked_threshold(direct.hi,lower,tol):
                counts['early_pruned']+=1
                rec['bound_mode']='direct';bound=direct;source='direct'
            else:
                strategy=proto['selective_policy']
                do_coupled=(depth<=strategy['always_depth'] or idx % strategy['cadence']==0)
                if do_coupled:
                    cap=model.coupled_upper(rec['effective_box'])
                    counts['coupled']+=1
                    if cap.cmp(direct.hi)<0:
                        if cap.cmp(direct.lo)<0:raise ArithmeticError('Unsound coupled bound')
                        bound=I.from_ends(direct.lo,cap);source='coupled_logdet_dual';counts['dual_improved']+=1
                    else:bound=direct;source='direct'
                    rec['bound_mode']='coupled'
                else:
                    bound=direct;source='direct';rec['bound_mode']='direct'
            rec['upper_method']=source
            rec['upper_bound_ceil_display']=bound.upper_float()
            cached[idx]=bound.hi
            heapq.heappush(heap,(-bound.upper_float(),idx))
        nodes.append(rec)
    add(root,0)
    while heap and len(nodes)+2<=budget:
        _,idx=heapq.heappop(heap)
        n=nodes[idx]
        ub=cached[idx]
        if checked_threshold(ub,lower,tol):continue
        eff=n['effective_box'];center,_=midpoint_bounds(eff)
        val=_score(model,center)
        if val.cmp(lower)>0:lower=val;incumbent=center
        if checked_threshold(ub,lower,tol):continue
        widths=[Decimal(b)-Decimal(a) for a,b in eff]
        axis=max(range(d['d']),key=lambda k:widths[k])
        if widths[axis]<=0:continue
        middle=center[axis]
        left=[list(z) for z in eff];right=[list(z) for z in eff]
        left[axis][1]=middle;right[axis][0]=middle
        if not(Decimal(left[axis][0])<Decimal(left[axis][1]) and Decimal(right[axis][0])<Decimal(right[axis][1])):continue
        n['children']=[len(nodes),len(nodes)+1];n['split_dim']=axis
        add(left,n['depth']+1);add(right,n['depth']+1)
    leaves=[n for n in nodes if 'children' not in n and n.get('newton',{}).get('status')!='NO_STATIONARY']
    if not leaves:raise ArithmeticError('No retained candidate-domain leaf')
    # Previously CH27 RECOMPUTED expensive bounds on every leaf. Reuse MPFR
    # endpoints already computed during this same precision-limited search.
    ceiling=max((cached[n['id']] for n in leaves),key=lambda v:v.as_float(UP))
    for n in leaves:
        counts['cached_leaf']+=1
        if cached[n['id']].cmp(ceiling)>0:ceiling=cached[n['id']]
    certified=all(checked_threshold(cached[n['id']],lower,tol) for n in leaves)
    return {'milestone':'CH-C14-28','claim_scope':'finite_root_box_global_max_only',
        'status':'CERTIFIED_BOUNDED_GAP' if certified else 'UNRESOLVED_REFUSE_CERTIFICATION',
        'original_data_identity':inp['original_CH23_identity'],'model':d,'model_sha256':model_digest(d),
        'root_box':root,'dual_matrices':duals,'tangent_anchors':seeds[:1],
        'incumbent':incumbent,'tolerance':tol,'precision_bits':proto['precision_bits'],
        'nodes':nodes,'leaf_count':len(leaves),'counters':counts,
        'newton_calls':counts['newton'],'newton_exclusions':counts['exclusions'],
        'newton_contractions':counts['contractions'],
        'upper_bound_ceil_display':ceiling.as_float(UP),
        'lower_bound_floor_display':lower.as_float(DOWN),
        'gap_upper_display':ceiling.as_float(UP)-lower.as_float(DOWN),
        'elapsed_seconds':round(time.perf_counter()-started,4),
        'production_release':'NO_GO','unbounded_global_claim':False,
        'note':'All cached upper bounds are recomputed at 224-bit verification; selective policy does not modify certified domain coverage.'}
