"""CH27 research-only global-max over a finite 3D coefficient box.

Search upper bounds: Fisher--likelihood dual plus CH26 independent bound.
Selective interior-box interval-Newton contractor is safe *for global-max*
only because original-domain boundary boxes remain covered unchanged.
No unique/unbounded/global statistical inference claims.
"""
from __future__ import annotations
from decimal import Decimal
from pathlib import Path
import sys,time,heapq
BASE=Path(__file__).resolve().parent.parent
for p in (BASE/'CH_C14_24',BASE/'CH_C14_26',BASE/'ch_c14_24',BASE/'ch_c14_26'):
    if p.is_dir() and str(p) not in sys.path:sys.path.insert(0,str(p))
import mpfr_interval as implementation
from mpfr_interval import Interval as I, MP, checked_threshold, UP, DOWN
from verified_bnb import logistic_model,midpoint_bounds,model_digest
from coupled27 import CoupledObjective
from interval_newton27 import contract,interior

def candidate_lower(model,point):
    return model.objective([I(x) for x in point])[0].lo

def evaluate_node(model,box):
    return model.bound(box)

def solve(inp,protocol,duals):
    implementation.PRECISION=protocol['precision_bits']
    d=logistic_model(inp['rows'])
    root=inp['bounds']
    if len(root)!=d['d']:raise ValueError('Original dimension incorrect')
    for a,b in root:
        if Decimal(a)>=Decimal(b):raise ValueError('Invalid coefficient box')
    seeds=inp['seeds']
    for s in seeds:
        if len(s)!=d['d'] or any(not Decimal(a)<=Decimal(v)<=Decimal(b) for v,(a,b) in zip(s,root)):
            raise ValueError('Original seed outside coefficient box')
    model=CoupledObjective(d,duals)
    model.set_tangents(seeds[:1])
    mid,_=midpoint_bounds(root)
    incumbent=mid;lb=candidate_lower(model,mid)
    for s in seeds:
        v=candidate_lower(model,s)
        if v.cmp(lb)>0:lb=v;incumbent=s
    max_nodes=protocol['node_budget_per_case'];max_newton=protocol['max_newton_evaluations_per_case']
    gate=Decimal(protocol['newton_max_side_width'])
    tol=protocol['objective_absolute_tolerance']
    counts={'calls':0,'contracted':0,'excluded':0,'no_gain':0,'noninterior':0}
    start=time.monotonic()
    nodes=[];heap=[]
    def make_node(box):
        idx=len(nodes)
        rec={'id':idx,'box':box,'effective_box':box}
        if counts['calls']<max_newton and interior(box,root) and max(Decimal(b)-Decimal(a) for a,b in box)<=gate:
            counts['calls']+=1
            try:
                attempt=contract(model,box,root)
            except (ArithmeticError,ValueError):
                # Failure to compute a validated contractor does NOT remove a box.
                attempt={'status':'NO_GAIN','reason':'NUMERICAL_UNAVAILABLE'}
            if attempt['status']=='CONTRACTED':
                rec['newton']=attempt;rec['effective_box']=attempt['box'];counts['contracted']+=1
            elif attempt['status']=='NO_STATIONARY':
                rec['newton']=attempt;counts['excluded']+=1
            else:counts['no_gain']+=1
        if rec.get('newton',{}).get('status')!='NO_STATIONARY':
            ub,source=evaluate_node(model,rec['effective_box'])
            rec['upper_bound_display']=ub.upper_float();rec['upper_method']=source
            heapq.heappush(heap,(-ub.upper_float(),idx,ub.hi))
        nodes.append(rec)
    make_node(root)
    while heap and len(nodes)+2<=max_nodes:
        _,idx,ub=heapq.heappop(heap)
        n=nodes[idx]
        if checked_threshold(ub,lb,tol):continue
        eff=n['effective_box']
        center,_=midpoint_bounds(eff)
        val=candidate_lower(model,center)
        if val.cmp(lb)>0:lb=val;incumbent=center
        if checked_threshold(ub,lb,tol):continue
        widths=[Decimal(b)-Decimal(a) for a,b in eff]
        axis=max(range(d['d']),key=lambda k:widths[k])
        if widths[axis]<=0:continue
        middle=center[axis]
        l=[z[:] for z in eff];r=[z[:] for z in eff]
        l[axis][1]=middle;r[axis][0]=middle
        if not(Decimal(l[axis][0])<Decimal(l[axis][1]) and Decimal(r[axis][0])<Decimal(r[axis][1])):continue
        n['split_dim']=axis;n['children']=[len(nodes),len(nodes)+1]
        make_node(l);make_node(r)
    leaves=[n for n in nodes if 'children' not in n and n.get('newton',{}).get('status')!='NO_STATIONARY']
    if not leaves:raise ArithmeticError('No feasible candidate-domain leaf retained')
    leaf_bound=[];methods={}
    for n in leaves:
        b,source=evaluate_node(model,n['effective_box'])
        leaf_bound.append(b.hi);methods[source]=methods.get(source,0)+1
    upper=max(leaf_bound,key=lambda x:x.as_float(UP))
    for u in leaf_bound:
        if u.cmp(upper)>0:upper=u
    verified=all(checked_threshold(u,lb,tol) for u in leaf_bound)
    return {'milestone':'CH-C14-27','claim_scope':'finite_root_box_global_max_only',
       'status':'CERTIFIED_BOUNDED_GAP' if verified else 'UNRESOLVED_REFUSE_CERTIFICATION',
       'original_data_identity':inp['original_CH23_identity'],
       'model':d,'model_sha256':model_digest(d),'root_box':root,
       'dual_matrices':duals,'tangent_anchors':seeds[:1],
       'incumbent':incumbent,'tolerance':tol,'precision_bits':protocol['precision_bits'],
       'nodes':nodes,'leaf_count':len(leaves),'newton_calls':counts['calls'],
       'newton_exclusions':counts['excluded'],'newton_contractions':counts['contracted'],
       'newton_no_gain':counts['no_gain'],'leaf_methods':methods,
       'upper_bound_ceil_display':upper.as_float(UP),
       'lower_bound_floor_display':lb.as_float(DOWN),
       'gap_upper_display':upper.as_float(UP)-lb.as_float(DOWN),
       'elapsed_seconds':round(time.monotonic()-start,3),
       'production_release':'NO_GO','unbounded_global_claim':False,
       'note':'Original coefficient domain only; higher-precision verifier required. Interior Newton contraction preserves global maxima but does not bound J everywhere.'}
