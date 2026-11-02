"""CH26 research-only 3D interval branch & bound; no model/scientific promotion.

All decisions about global bounded gap use directed MPFR comparisons, never float
sort/display keys.  Heuristic heap priorities only determine the split order.
"""
from __future__ import annotations
import sys,hashlib,heapq,json,time
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'CH_C14_24'))
import mpfr_interval as implementation
from mpfr_interval import Interval as I, MP, up_abs,checked_threshold,UP,DOWN
from verified_bnb import logistic_model,midpoint_bounds,interval_box,exact_decimal,model_digest
from improved_bounds import ImprovedObjective


def bound(model,box,*,curvature=False):
    direct,method=model.objective(interval_box(box))
    if not curvature: return direct,method
    center,radii=midpoint_bounds(box)
    cg,ch=model.analytic_derivatives([I(v) for v in center])
    rg,rh=model.analytic_derivatives(interval_box(box))
    c,_=model.objective([I(v) for v in center])
    linear=I('0');quadratic=I('0')
    for i in range(model.d):
        r=I(radii[i]);linear=linear+up_abs(cg[i])*r
        if rh[i][i].hi.cmp(MP('0'))>0:
            quadratic=quadratic+I('0.5')*I.from_ends(MP('0'),rh[i][i].hi)*r*r
        for j in range(i+1,model.d):
            quadratic=quadratic+up_abs(rh[i][j])*r*I(radii[j])
    cap=c+linear+quadratic
    if cap.hi.cmp(direct.hi)<0:
        if cap.hi.cmp(direct.lo)<0:raise ArithmeticError('Analytic Hessian cap contradicts objective enclosure')
        return I.from_ends(direct.lo,cap.hi),'analytic_hessian_taylor'
    return direct,method


def lower(model,point):
    v,_=model.objective([I(x) for x in point]);return v.lo


def solve(input_data,protocol):
    bits=protocol['precision_bits'];implementation.PRECISION=bits
    tol=exact_decimal(protocol['objective_absolute_tolerance'])
    nmax=protocol['node_budget_per_case']
    max_curv=protocol['max_hessian_calls_per_case']
    gate=Decimal(protocol['hessian_max_root_side_width'])
    raw=input_data['rows']; root=input_data['bounds']
    data=logistic_model(raw); model=ImprovedObjective(data)
    if len(root)!=data['d']:raise ValueError('Wrong dimension')
    for a,b in root:
        if Decimal(a)>=Decimal(b):raise ValueError('Bad box')
    seeds=input_data.get('seeds',[])
    for s in seeds:
        if len(s)!=data['d'] or any(not Decimal(a)<=Decimal(v)<=Decimal(b) for v,(a,b) in zip(s,root)):
            raise ValueError('Untrusted seed outside box')
    # Certified affine tangents at frozen inputs, independent of node search order.
    anchors=seeds[:1]
    if protocol['use_loglikelihood_tangent']:
        model.set_tangents(anchors)
    mid,_=midpoint_bounds(root)
    incumbent=mid;best=lower(model,mid)
    for s in seeds:
        v=lower(model,s)
        if v.cmp(best)>0:incumbent=list(s);best=v
    timer=time.monotonic(); call_count=0
    root_ub,method=bound(model,root,curvature=False)
    nodes=[{'id':0,'box':root,'method':method,'curvature':False,'upper_display':root_ub.upper_float()}]
    queue=[(-root_ub.upper_float(),0,root_ub.hi)]
    pops=0
    while queue and len(nodes)+2<=nmax:
        _,idx,ub=heapq.heappop(queue)
        node=nodes[idx]
        if checked_threshold(ub,best,tol):continue
        box=node['box']
        cand,_=midpoint_bounds(box)
        lb=lower(model,cand)
        if lb.cmp(best)>0:best=lb;incumbent=cand
        if checked_threshold(ub,best,tol):continue
        widths=[Decimal(b)-Decimal(a) for a,b in box]
        axis=max(range(data['d']),key=lambda i:widths[i])
        if widths[axis]<=0:raise ArithmeticError('Unsplitable interval cell')
        p=midpoint_bounds(box)[0][axis]
        left=[z[:] for z in box];right=[z[:] for z in box]
        left[axis][1]=p;right[axis][0]=p
        if not(Decimal(left[axis][0])<Decimal(left[axis][1]) and Decimal(right[axis][0])<Decimal(right[axis][1])):
            raise ArithmeticError('Unsplitable midpoint')
        node['split_dim']=axis;node['children']=[len(nodes),len(nodes)+1]
        for b in (left,right):
            do_hessian=call_count<max_curv and max(Decimal(z[1])-Decimal(z[0]) for z in b)<=gate
            ubchild,m=bound(model,b,curvature=do_hessian)
            if do_hessian:call_count+=1
            child={'id':len(nodes),'box':b,'method':m,'curvature':do_hessian,'upper_display':ubchild.upper_float()}
            nodes.append(child)
            heapq.heappush(queue,(-ubchild.upper_float(),child['id'],ubchild.hi))
        pops+=1
    # Reconstruct live leaf bounds: never certify from heap float/old incumbent.
    leaves=[n for n in nodes if 'children' not in n]
    upper=None;methods={};leaf_ubs=[]
    for n in leaves:
        ub,method=bound(model,n['box'],curvature=n['curvature'])
        methods[method]=methods.get(method,0)+1
        leaf_ubs.append(ub.hi)
        if upper is None or ub.hi.cmp(upper)>0:upper=ub.hi
    proven=all(checked_threshold(u,best,tol) for u in leaf_ubs)
    return {
        'milestone':'CH-C14-26','claim_scope':'finite_root_box_only',
        'status':'CERTIFIED_BOUNDED_GAP' if proven else 'UNRESOLVED_REFUSE_CERTIFICATION',
        'model':data,'model_sha256':model_digest(data),
        'original_data_identity':input_data['original_CH23_identity'],
        'root_box':root,'tangent_anchors':anchors if protocol['use_loglikelihood_tangent'] else [],
        'incumbent':incumbent,'precision_bits':bits,'tolerance':tol,
        'nodes':nodes,'leaf_count':len(leaves),'split_count':pops,
        'hessian_evaluations':call_count,'leaf_methods':methods,
        'upper_bound_ceil_display':upper.as_float(UP),'lower_bound_floor_display':best.as_float(DOWN),
        'gap_upper_display':upper.as_float(UP)-best.as_float(DOWN),
        'elapsed_seconds':round(time.monotonic()-timer,3),
        'production_release':'NO_GO','unbounded_global_claim':False,
        'note':'Local search; final status requires verifier26.py independent higher-precision replay.'
    }
