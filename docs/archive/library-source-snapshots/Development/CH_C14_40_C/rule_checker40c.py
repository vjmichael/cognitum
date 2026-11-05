"""CH40-C independent rule-based replay of frozen CH29 producer tree.

Does not import producer MPFR/BnB/Newton. Uses CH40-B's separately
implemented Decimal coupled/direct mathematical enclosures.

Crucial distinction: source `*_display` numbers are not proof witnesses.
Only producer cap values for which this independent checker derives an
upper bound <= the displayed value are marked justified. Otherwise:
UNATTESTED_DISPLAY_CAP, not a false certification.
"""
from __future__ import annotations
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
from independent_checker40 import MathematicalModel, exact_partition, canonical, digest
from independent_bounds40b import dual_coupled_upper
from batch40b import finite_fraction
from exact_decimal40 import op, ROUND_CEILING

RULES = {('direct','direct'), ('coupled','direct'), ('coupled','coupled_logdet_dual')}

def _number(x):
    if type(x) not in (str,int,float): raise ValueError('Non-numeric upper bound display')
    v=Decimal(str(x))
    if not v.is_finite():raise ValueError('Non-finite upper bound display')
    return v

def exact_nodes(cert):
    if cert.get('milestone') != 'CH-C14-29' or cert.get('claim_scope') != 'finite_root_box_global_max_only' or cert.get('production_release') != 'NO_GO':
        raise ValueError('Unexpected historical certificate scope or release claim')
    if digest(cert['model']) != cert['model_sha256']:
        raise ValueError('Modified producer mathematical model')
    leaves=exact_partition(cert)
    nodes=cert['nodes']
    if len(nodes)!=127 or len(leaves)!=64:raise ValueError('Frozen proof topology mismatch')
    by_id={n['id']:n for n in nodes}
    for n in nodes:
        if (n.get('bound_mode'),n.get('upper_method')) not in RULES:
            raise ValueError('Unknown or inconsistent producer bound rule')
        if n['effective_box'] != n['box'] or 'newton' in n:
            raise ValueError('Original proof has an unvalidated contraction/exclusion')
        if n['id']!=0 and (type(n['parent_id']) is not int or n['parent_id'] not in by_id or n['parent_id']>=n['id']):
            raise ValueError('Malformed ancestor relation')
        local_display = _number(n['local_upper_bound_display'])
        cap_display = _number(n['upper_bound_ceil_display'])
        if n['id'] == 0:
            expected_display = local_display
        else:
            expected_display = min(local_display,_number(by_id[n['parent_id']]['upper_bound_ceil_display']))
        if cap_display != expected_display:
            raise ValueError('Historical displayed parent-bound inheritance inconsistent')
    return leaves

def verify_tree(cert, *, max_nodes=None):
    """Replay rules, not exact MPFR numeric computation; explicit fail-closed scope."""
    exact_nodes(cert)
    nodes=cert['nodes']; model=MathematicalModel(cert['model'])
    if max_nodes is None:max_nodes=len(nodes)
    if type(max_nodes) is not int or not 1<=max_nodes<=len(nodes):raise ValueError('Invalid node budget')
    inherited={}; per_node=[]; stats=Counter()
    for n in nodes[:max_nodes]:
        box=[(finite_fraction(Fraction(str(a))), finite_fraction(Fraction(str(b)))) for a,b in n['box']]
        direct=model.objective_bound(box)
        if n['upper_method']=='coupled_logdet_dual':
            from_dual=dual_coupled_upper(model,box,cert['dual_matrices'])['upper']
            # Independent safe enclosure may be taken as a minimum of two proven rules.
            local=min(direct,from_dual)
            stats['coupled_rules_evaluated']+=1
        else:
            local=direct;stats['direct_rules_evaluated']+=1
        parent=n.get('parent_id')
        # Verify inherited cap using our own independent bound, NEVER the producer's float.
        cap=local if parent is None else min(local,inherited[parent])
        inherited[n['id']]=cap
        independent_can_support_local=local<=_number(n['local_upper_bound_display'])
        independent_can_support_effective=cap<=_number(n['upper_bound_ceil_display'])
        if independent_can_support_local:stats['producer_local_displays_justified']+=1
        if independent_can_support_effective:stats['producer_inherited_displays_justified']+=1
        if n['id'] and cap>inherited[parent]:raise ArithmeticError('Independent inherited cap failed monotonicity')
        per_node.append({'id':n['id'],'parent':parent,'rule':n['upper_method'],
          'independent_local_upper':str(local),'independent_inherited_upper':str(cap),
          'producer_local_display_justified':independent_can_support_local,
          'producer_inherited_display_justified':independent_can_support_effective})
    complete=len(per_node)==len(nodes)
    if complete:
        leaves=[n for n in nodes if 'children' not in n]
        u=max(inherited[n['id']] for n in leaves)
        lb=model.incumbent_lower(cert['incumbent'])
        threshold=op('add',lb,Decimal(str(cert['tolerance'])),ROUND_CEILING)
        finite_gap=u<=threshold
    else:u=lb=threshold=None;finite_gap=False
    # The archived original format includes no tangent point per observation,
    # no full outgoing rounded intervals, no accepted Newton event. It cannot
    # serve as a complete producer-rule certificate irrespective of display match.
    return {'protocol':'CH40C-DECIMAL-INHERITED-RULE-REPLAY-V1','case':cert['research_case_id'],
      'certificate_sha256':digest(cert),'nodes_replayed':len(per_node),'nodes_total':len(nodes),
      'stats':dict(stats),'producer_display_caps_all_justified':complete and stats['producer_inherited_displays_justified']==len(nodes),
      'producer_optimized_rules_fully_certified':False,
      'producer_missing_proof_material':['per-row coupled tangent choices','outward-rounded local cap proof objects','historical Newton proof events (none accepted)'],
      'verified_independent_leaf_ceiling':None if u is None else str(u),
      'independent_incumbent_floor':None if lb is None else str(lb),
      'independent_finite_gap_proven':bool(finite_gap),
      'scientific_release':'NO_GO','nodes':per_node,
      'admission_scope':'INDEPENDENT_FINITE_BOX_CONSISTENCY_ONLY'}


def require_independent_support_for_producer_caps(result):
    if (result.get('nodes_replayed') != 127 or
        result.get('stats',{}).get('producer_inherited_displays_justified') != 127):
        raise ValueError('One or more producer display cap numbers lack independent justification')
    # Even support for floats is insufficient to reproduce full directed rounding rules.
    if result.get('producer_optimized_rules_fully_certified') is not True:
        raise ValueError('Missing producer proof witnesses; cannot certify original optimized rule')
    raise ValueError('Global/prod promotion not offered by CH40-C')

def audit_claim(cert,claimed):
    """Recompute source-bound semantic claim; reject incomplete producer promotions."""
    if claimed.get('producer_optimized_rules_fully_certified') is not False:
        raise ValueError('Producer optimized proof claims cannot be certified from this format')
    got=verify_tree(cert,max_nodes=len(claimed.get('nodes',[])))
    if canonical(got)!=canonical(claimed):raise ValueError('Altered mathematical receipt')
    return got