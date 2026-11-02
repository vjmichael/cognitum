"""Independent higher-precision CH27 source-bound mathematical replay.

Checks complete binary partition of original root, all interior root-exclusion
and contraction steps, bound on all retained candidate-domain terminal boxes,
exact SPD witnesses and feasible incumbent. Independent _execution_ of same
mathematical formulas, not a formally independently implemented proof assistant.
"""
from __future__ import annotations
import hashlib,json,sys
from decimal import Decimal
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
for p in (BASE/'CH_C14_24',BASE/'CH_C14_26',BASE/'ch_c14_24',BASE/'ch_c14_26'):
    if p.is_dir() and str(p) not in sys.path:sys.path.insert(0,str(p))
import mpfr_interval as impl
from mpfr_interval import MP,UP,DOWN,checked_threshold
from verified_bnb import logistic_model,model_digest,midpoint_bounds
from verify_certificate import validate_model
from coupled27 import CoupledObjective,is_spd_exact
from interval_newton27 import interior,replay_check
from solver27 import evaluate_node,candidate_lower

def _eq(a,b):
    return len(a)==len(b) and all(len(x)==len(y) and all(Decimal(z)==Decimal(w) for z,w in zip(x,y)) for x,y in zip(a,b))

def verify(cert,reference,protocol,duals,*,replay_bits=None):
    if cert.get('milestone')!='CH-C14-27' or cert.get('claim_scope')!='finite_root_box_global_max_only':
        raise ValueError('Wrong claim scope')
    if cert.get('production_release')!='NO_GO' or cert.get('unbounded_global_claim') is not False:
        raise ValueError('Invalid release/global claim')
    if cert.get('status') not in ('CERTIFIED_BOUNDED_GAP','UNRESOLVED_REFUSE_CERTIFICATION'):
        raise ValueError('Unknown status')
    data=cert['model'];validate_model(data)
    if data!=logistic_model(reference['rows']) or model_digest(data)!=cert['model_sha256']:
        raise ValueError('Original model invalid')
    if reference['original_CH23_identity']!=cert['original_data_identity']:
        raise ValueError('Original CH23 dataset identity mismatch')
    if not _eq(reference['bounds'],cert['root_box']):raise ValueError('Original root box mismatch')
    if cert['tangent_anchors']!=reference['seeds'][:1]:raise ValueError('Unfrozen tangent anchors')
    if duals!=cert['dual_matrices'] or not all(is_spd_exact(Q) for Q in duals):
        raise ValueError('Unfrozen or not positive definite dual matrix')
    if cert['tolerance']!=protocol['objective_absolute_tolerance'] or cert['precision_bits']!=protocol['precision_bits']:
        raise ValueError('Unfrozen precision or tolerance')
    nodes=cert['nodes']
    if not(1<=len(nodes)<=protocol['node_budget_per_case']):raise ValueError('Exceeded frozen node budget')
    if cert['newton_calls']>protocol['max_newton_evaluations_per_case']:
        raise ValueError('Exceeded frozen Newton budget')
    bits=replay_bits or protocol['replay_precision_bits']
    if bits<=cert['precision_bits']:raise ValueError('Replay must use higher precision')
    impl.PRECISION=bits
    model=CoupledObjective(data,duals);model.set_tangents(reference['seeds'][:1])
    seen=set();leaves=[];exclusions=0;contractions=0
    def walk(idx,expected):
        nonlocal exclusions,contractions
        if idx in seen or idx>=len(nodes) or idx<0:raise ValueError('Duplicate or out-of-range node')
        seen.add(idx);n=nodes[idx]
        if n['id']!=idx or not _eq(n['box'],expected):raise ValueError('Partition node mismatch')
        effective=n['effective_box'];r=n.get('newton')
        if r:
            if not interior(n['box'],cert['root_box']):raise ValueError('Newton changed a boundary box')
            if max(Decimal(b)-Decimal(a) for a,b in n['box'])>Decimal(protocol['newton_max_side_width']):
                raise ValueError('Newton performed outside width gate')
            replay_check(model,n['box'],cert['root_box'],r)
            if r['status']=='NO_STATIONARY':
                exclusions+=1
                if 'children' in n:raise ValueError('Excluded node split')
                if not _eq(effective,n['box']):raise ValueError('Excluded node altered domain')
                return
            if r['status']!='CONTRACTED' or not _eq(effective,r['box']):raise ValueError('Invalid contracted box')
            contractions+=1
        elif not _eq(effective,n['box']):raise ValueError('Unjustified contraction')
        if 'children' not in n:
            leaves.append(n);return
        kids=n['children']
        if len(kids)!=2 or kids[0]==kids[1] or any(not isinstance(k,int) or k<=idx for k in kids):
            raise ValueError('Invalid descendants')
        axis=n['split_dim'];m,_=midpoint_bounds(effective)
        if not isinstance(axis,int) or not(0<=axis<len(effective)):raise ValueError('Invalid split axis')
        a=[list(x) for x in effective];b=[list(x) for x in effective]
        a[axis][1]=m[axis];b[axis][0]=m[axis]
        if not(Decimal(a[axis][0])<Decimal(a[axis][1]) and Decimal(b[axis][0])<Decimal(b[axis][1])):
            raise ValueError('Invalid midpoint split')
        walk(kids[0],a);walk(kids[1],b)
    walk(0,cert['root_box'])
    if len(seen)!=len(nodes):raise ValueError('Unreachable node')
    if not leaves or cert['leaf_count']!=len(leaves):raise ValueError('Unverified leaf count')
    if exclusions!=cert['newton_exclusions'] or contractions!=cert['newton_contractions']:
        raise ValueError('Newton decision counts incorrect')
    if exclusions+contractions>cert['newton_calls']:
        raise ValueError('Contractor count inconsistent')
    if not all(Decimal(a)<=Decimal(x)<=Decimal(b) for x,(a,b) in zip(cert['incumbent'],cert['root_box'])):
        raise ValueError('Feasible incumbent outside coefficient box')
    lb=candidate_lower(model,cert['incumbent'])
    maximum=None;methods={};good=True
    for leaf in leaves:
        u,source=evaluate_node(model,leaf['effective_box'])
        if maximum is None or u.hi.cmp(maximum)>0:maximum=u.hi
        methods[source]=methods.get(source,0)+1
        if not checked_threshold(u.hi,lb,cert['tolerance']):good=False
    if cert['status']=='CERTIFIED_BOUNDED_GAP' and not good:
        raise ValueError('Claimed global gap not proven')
    return {'milestone':'CH-C14-27',
        'replay_status':'VERIFIED_BOUNDED_GAP' if good else 'REPLAYED_BUT_UNRESOLVED',
        'leaf_count':len(leaves),'nodes_verified':len(seen),
        'newton_exclusions_verified':exclusions,'newton_contractions_verified':contractions,
        'original_data_identity':cert['original_data_identity'],
        'upper_bound_ceil_display':maximum.as_float(UP),
        'lower_bound_floor_display':lb.as_float(DOWN),
        'gap_upper_display':maximum.as_float(UP)-lb.as_float(DOWN),
        'precision_bits':bits,'methods':methods,'partition_verified':True,
        'release':'NO_GO','unbounded_global_claim':False,
        'limitations':'Replays source-bound interval inequalities; does not establish uniqueness or unrestricted optimum.'}
