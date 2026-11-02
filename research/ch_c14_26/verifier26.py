"""Fail-closed CH26 certificate replay (does not trust saved upper numbers)."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'CH_C14_24'))
import mpfr_interval as impl
from mpfr_interval import MP,UP,DOWN,checked_threshold
from verified_bnb import exact_decimal,model_digest,rank_exact
from verify_certificate import check_tree,validate_model
from improved_bounds import ImprovedObjective
from solver26 import bound,lower
from decimal import Decimal

def verify(cert,reference,protocol,*,precision_bits=224):
    if cert.get('milestone')!='CH-C14-26' or cert.get('claim_scope')!='finite_root_box_only' or cert.get('production_release')!='NO_GO' or cert.get('unbounded_global_claim') is not False:
        raise ValueError('Bad claim scope or release')
    data=cert['model'];validate_model(data)
    if model_digest(data)!=cert['model_sha256']:
        raise ValueError('Data/model digest mismatch')
    if cert['original_data_identity']!=reference['original_CH23_identity']:
        raise ValueError('Original CH23 identity mismatch')
    from verified_bnb import logistic_model
    if logistic_model(reference['rows'])!=data:
        raise ValueError('Frozen original predictor table differs')
    if cert['root_box']!=reference['bounds']:
        raise ValueError('Box differs from frozen CH23')
    expected_anchor=reference.get('seeds',[])[:1] if protocol['use_loglikelihood_tangent'] else []
    if cert['tangent_anchors']!=expected_anchor:
        raise ValueError('Unexpected concavity tangent anchor')
    if cert['tolerance']!=protocol['objective_absolute_tolerance'] or cert['precision_bits']!=protocol['precision_bits']:
        raise ValueError('Protocol precision/tolerance not frozen')
    if len(cert['nodes'])>protocol['node_budget_per_case'] or cert.get('hessian_evaluations',0)>protocol['max_hessian_calls_per_case']:
        raise ValueError('Unfrozen resource budget')
    if precision_bits<=cert['precision_bits']:raise ValueError('Replay precision must be greater')
    impl.PRECISION=precision_bits
    model=ImprovedObjective(data);model.set_tangents(expected_anchor)
    leaves=check_tree(cert['nodes'],cert['root_box'])
    if len(leaves)!=cert['leaf_count']:raise ValueError('Mismatched partition')
    for n in cert['nodes']:
        if n['curvature'] and max(Decimal(b)-Decimal(a) for a,b in n['box'])>Decimal(protocol['hessian_max_root_side_width']):
            raise ValueError('Unfrozen curvature policy')
    lb=lower(model,cert['incumbent'])
    for x,(a,b) in zip(cert['incumbent'],cert['root_box']):
        if not Decimal(a)<=Decimal(x)<=Decimal(b):raise ValueError('Invalid feasible witness')
    best=None;methods={};leaf_ubs=[]
    for leaf in leaves:
        ub,method=bound(model,leaf['box'],curvature=leaf['curvature'])
        methods[method]=methods.get(method,0)+1
        leaf_ubs.append(ub.hi)
        if best is None or ub.hi.cmp(best)>0:best=ub.hi
    proven=all(checked_threshold(u,lb,cert['tolerance']) for u in leaf_ubs)
    if cert['status']=='CERTIFIED_BOUNDED_GAP' and not proven:
        raise ValueError('False certified gap')
    if cert['status'] not in ('CERTIFIED_BOUNDED_GAP','UNRESOLVED_REFUSE_CERTIFICATION'):
        raise ValueError('Unknown status')
    return {
        'milestone':'CH-C14-26','replay_status':'VERIFIED_BOUNDED_GAP' if proven else 'REPLAYED_BUT_UNRESOLVED',
        'original_data_identity':reference['original_CH23_identity'],
        'model_sha256':cert['model_sha256'],'replay_precision_bits':precision_bits,
        'leaf_count':len(leaves),'methods':methods,
        'lower_bound_floor_display':lb.as_float(DOWN),'upper_bound_ceil_display':best.as_float(UP),
        'gap_upper_display':best.as_float(UP)-lb.as_float(DOWN),
        'partition_verified':True,'incumbent_verified':True,'objective_bounds_recomputed':True,
        'unbounded_global_claim':False,'production_release':'NO_GO',
        'note':'Recomputes same mathematical inequalities with higher-precision MPFR; not a formally independent proof assistant.'
    }
