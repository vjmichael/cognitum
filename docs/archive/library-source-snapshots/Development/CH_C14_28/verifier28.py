"""CH28 independent high-precision proof replay: does not trust cached node bounds."""
from __future__ import annotations
import sys
from pathlib import Path
from decimal import Decimal
D=Path(__file__).resolve().parent;BASE=D.parent
for folder in ('CH_C14_24','CH_C14_26','CH_C14_27'):
    sys.path.insert(0,str(BASE/folder))
import mpfr_interval as impl
from mpfr_interval import checked_threshold,UP,DOWN
from verified_bnb import logistic_model,model_digest,midpoint_bounds
from verify_certificate import validate_model
from coupled27 import CoupledObjective,is_spd_exact
from interval_newton27 import interior,replay_check
from solver28 import bound_by_mode,_score

def _boxeq(a,b):
    return len(a)==len(b) and all(len(x)==len(y) and all(Decimal(u)==Decimal(v) for u,v in zip(x,y)) for x,y in zip(a,b))

def verify(cert,inp,proto,duals):
    if cert['milestone']!='CH-C14-28' or cert['claim_scope']!='finite_root_box_global_max_only':raise ValueError('Invalid claim')
    if cert['production_release']!='NO_GO' or cert['unbounded_global_claim'] is not False:raise ValueError('Unapproved release/global claim')
    if cert['status'] not in ('CERTIFIED_BOUNDED_GAP','UNRESOLVED_REFUSE_CERTIFICATION'):raise ValueError('Invalid status')
    if cert['original_data_identity']!=inp['original_CH23_identity']:raise ValueError('Input identity invalid')
    if not _boxeq(cert['root_box'],inp['bounds']):raise ValueError('Root domain altered')
    if cert['tangent_anchors']!=inp['seeds'][:1] or duals!=cert['dual_matrices'] or not all(is_spd_exact(Q) for Q in duals):raise ValueError('Invalid dual/tangent')
    if cert['precision_bits']!=proto['precision_bits'] or cert['tolerance']!=proto['objective_absolute_tolerance']:raise ValueError('Invalid tolerance/precision')
    if proto['replay_precision_bits']<=proto['precision_bits']:raise ValueError('Unsafe replay precision')
    data=logistic_model(inp['rows']);validate_model(data)
    if cert['model']!=data or cert['model_sha256']!=model_digest(data):raise ValueError('Input model altered')
    nodes=cert['nodes']
    if not nodes or len(nodes)>proto['node_budget_per_case']:raise ValueError('Invalid node budget')
    impl.PRECISION=proto['replay_precision_bits'];model=CoupledObjective(data,duals);model.set_tangents(inp['seeds'][:1])
    seen=set();leaves=[];excluded=0;contracted=0
    def walk(idx,expected,depth):
        nonlocal excluded,contracted
        if idx in seen or not(0<=idx<len(nodes)):raise ValueError('Invalid proof tree references')
        seen.add(idx);n=nodes[idx]
        if n['id']!=idx or n['depth']!=depth or not _boxeq(n['box'],expected):raise ValueError('Partition altered')
        eff=n['effective_box'];new=n.get('newton')
        if new:
            if not interior(n['box'],cert['root_box']):raise ValueError('Boundary box contracted')
            if max(Decimal(b)-Decimal(a) for a,b in n['box'])>Decimal(proto['newton_max_side_width']):raise ValueError('Newton width violated')
            replay_check(model,n['box'],cert['root_box'],new)
            if new['status']=='NO_STATIONARY':
                excluded+=1
                if 'children' in n or not _boxeq(eff,n['box']):raise ValueError('Invalid exclusion')
                return
            if new['status']!='CONTRACTED' or not _boxeq(eff,new['box']):raise ValueError('Invalid contraction')
            contracted+=1
        elif not _boxeq(eff,n['box']):raise ValueError('Unjustified box shrink')
        if n.get('bound_mode') not in ('direct','coupled'):raise ValueError('Unrecognized bound method')
        if 'children' not in n:leaves.append(n);return
        kids=n['children'];axis=n['split_dim']
        if len(kids)!=2 or kids[0]==kids[1] or any(type(k)!=int or k<=idx for k in kids):raise ValueError('Invalid partition children')
        if type(axis)!=int or not(0<=axis<len(eff)):raise ValueError('Invalid split axis')
        mid,_=midpoint_bounds(eff)
        left=[list(z) for z in eff];right=[list(z) for z in eff]
        left[axis][1]=mid[axis];right[axis][0]=mid[axis]
        if Decimal(left[axis][0])>=Decimal(left[axis][1]) or Decimal(right[axis][0])>=Decimal(right[axis][1]):raise ValueError('Invalid split')
        walk(kids[0],left,depth+1);walk(kids[1],right,depth+1)
    walk(0,cert['root_box'],0)
    if len(seen)!=len(nodes) or len(leaves)!=cert['leaf_count'] or not leaves:raise ValueError('Incomplete proof tree')
    if excluded!=cert['newton_exclusions'] or contracted!=cert['newton_contractions']:raise ValueError('Newton record mismatch')
    if excluded+contracted>cert['newton_calls'] or cert['newton_calls']>proto['max_newton_evaluations_per_case']:raise ValueError('Newton budget exceeded')
    if not all(Decimal(a)<=Decimal(v)<=Decimal(b) for v,(a,b) in zip(cert['incumbent'],cert['root_box'])):raise ValueError('Incumbent infeasible')
    lower=_score(model,cert['incumbent']); ceiling=None;method_count={};all_good=True
    for leaf in leaves:
        bound,actual=bound_by_mode(model,leaf['effective_box'],leaf['bound_mode'])
        # Do not compare binary64 display bounds for proof, even if tampered.
        if ceiling is None or bound.hi.cmp(ceiling)>0:ceiling=bound.hi
        method_count[leaf['bound_mode']]=method_count.get(leaf['bound_mode'],0)+1
        if not checked_threshold(bound.hi,lower,cert['tolerance']):all_good=False
    if cert['status']=='CERTIFIED_BOUNDED_GAP' and not all_good:raise ValueError('False global claim')
    return {'milestone':'CH-C14-28','replay_status':'VERIFIED_BOUNDED_GAP' if all_good else 'REPLAYED_BUT_UNRESOLVED',
        'original_data_identity':inp['original_CH23_identity'],'nodes_verified':len(nodes),
        'leaf_count':len(leaves),'methods':method_count,'newton_exclusions':excluded,'newton_contractions':contracted,
        'upper_bound_ceil_display':ceiling.as_float(UP),'lower_bound_floor_display':lower.as_float(DOWN),
        'gap_upper_display':ceiling.as_float(UP)-lower.as_float(DOWN),
        'precision_bits':proto['replay_precision_bits'],'partition_verified':True,'release':'NO_GO','unbounded_global_claim':False,
        'limitations':'Verified only finite coefficient box. Higher-precision replay uses shared interval arithmetic, not an independently verified proof assistant.'}