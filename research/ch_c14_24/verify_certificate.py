"""Independent witness + partition replay for CH-C14-24 finite-box certificates.

Does not accept stored node upper-bound numbers as evidence. Reconstructs each
leaf's enclosure with MPFR, checks exact rational partition coverage, and
requires global upper <= independently evaluated incumbent lower + tolerance.
"""
import argparse
from collections import Counter
from decimal import Decimal
import json

import mpfr_interval as interval_lib
from mpfr_interval import MP, checked_threshold, DOWN, UP
from verified_bnb import FirthObjective, bound_node, exact_decimal, model_digest, rank_exact, candidate_lower


def validate_model(data):
    d=data['d']; raw=data['n_raw']
    assert isinstance(d,int) and 1<=d<=3
    assert isinstance(raw,int) and raw>=d
    total=0
    canonical=[]
    past=None
    for r in data['rows']:
        x=tuple(exact_decimal(z) for z in r['x'])
        if len(x)!=d or (past is not None and x<=past): raise ValueError('Unsorted/duplicate group')
        past=x
        n,s=r['n'],r['s']
        if not (type(n) is int and type(s) is int and 0<=s<=n and n>0):
            raise ValueError('Group counts invalid')
        total+=n
        canonical.append(x)
    if total!=raw or rank_exact(canonical)!=d: raise ValueError('Model invalid')


def check_tree(nodes, root_box):
    if not nodes or not isinstance(nodes,list): raise ValueError('Tree empty')
    if nodes[0]['box']!=root_box: raise ValueError('Wrong root')
    incoming=Counter()
    for i,node in enumerate(nodes):
        if type(node.get('id')) is not int or node['id']!=i: raise ValueError('Node ID mismatch')
        box=node['box']
        if not isinstance(box,list) or len(box)!=len(root_box): raise ValueError('Box dimension')
        for pair in box:
            if len(pair)!=2 or Decimal(exact_decimal(pair[0]))>=Decimal(exact_decimal(pair[1])):
                raise ValueError('Invalid node box')
        if 'children' not in node: continue
        children=node['children']; axis=node.get('split_dim')
        if not (type(axis) is int and 0<=axis<len(box) and isinstance(children,list)
                and len(children)==2 and all(type(c) is int and c>i and c<len(nodes) for c in children)
                and children[0]!=children[1]):
            raise ValueError('Invalid split')
        left=nodes[children[0]]['box'];right=nodes[children[1]]['box']
        for k in range(len(box)):
            if k==axis:
                if not (Decimal(left[k][0])==Decimal(box[k][0]) and
                        Decimal(left[k][1])==Decimal(right[k][0]) and
                        Decimal(right[k][1])==Decimal(box[k][1])):
                    raise ValueError('Non-covering split')
            else:
                if left[k]!=box[k] or right[k]!=box[k]:
                    raise ValueError('Invalid unchanged dimension')
        incoming.update(children)
    if any(incoming[i]!=1 for i in range(1,len(nodes))) or incoming[0]:
        raise ValueError('Disconnected/overlapping tree')
    leaves=[n for n in nodes if 'children' not in n]
    if not leaves:raise ValueError('No leaves')
    return leaves


def verify(cert, *, precision_bits=None, expected_digest=None):
    if cert.get('milestone')!='CH-C14-24' or cert.get('claim_scope')!='finite_root_box_only':
        raise ValueError('Claim scope mismatch')
    if cert.get('production_release')!='NO_GO': raise ValueError('Illegal release')
    if cert.get('objective')!='Jeffreys_penalized_binomial_logistic':raise ValueError('Objective')
    data=cert['model']
    validate_model(data)
    digest=model_digest(data)
    if digest!=cert.get('model_sha256') or (expected_digest and digest!=expected_digest):
        raise ValueError('Model hash mismatch')
    precision=precision_bits or max(256,int(cert['precision_bits'])+64)
    if precision<80 or precision>4096:raise ValueError('Bad precision')
    interval_lib.PRECISION=precision
    tol=exact_decimal(cert['tolerance'])
    if Decimal(tol)<=0:raise ValueError('Invalid tolerance')
    root=cert['root_box']
    for a,b in root:
        if Decimal(exact_decimal(a))>=Decimal(exact_decimal(b)):
            raise ValueError('Invalid root box')
    leaves=check_tree(cert['nodes'],root)
    if cert.get('leaf_count')!=len(leaves):raise ValueError('Leaf count mismatch')
    incumbent=[exact_decimal(z) for z in cert['incumbent']]
    if len(incumbent)!=data['d'] or any(not(Decimal(a)<=Decimal(v)<=Decimal(b))
                   for v,(a,b) in zip(incumbent,root)):
        raise ValueError('Incumbent outside root box')
    model=FirthObjective(data)
    lb=candidate_lower(model,incumbent)
    leaf_ubs=[]; methods={}
    for leaf in leaves:
        bound,method=bound_node(model,leaf['box'],curvature=True)
        leaf_ubs.append(bound.hi)
        methods[method]=methods.get(method,0)+1
    ub=leaf_ubs[0]
    for u in leaf_ubs[1:]:
        if u.cmp(ub)>0:ub=u
    proven=all(checked_threshold(u,lb,tol) for u in leaf_ubs)
    stated=cert.get('status')
    if stated not in ('CERTIFIED_BOUNDED_GAP','UNRESOLVED_REFUSE_CERTIFICATION'):
        raise ValueError('Unrecognized certification status')
    if stated=='CERTIFIED_BOUNDED_GAP' and not proven:
        raise ValueError('CLAIM_REJECTED: certificate does not establish gap')
    return {'verifier':'CH-C14-24-independent-replay',
            'result':'VERIFIED_BOUNDED_GAP' if proven else 'REPLAYED_BUT_UNRESOLVED',
            'claim_scope':'finite_root_box_only',
            'precision_bits':precision,'model_sha256':digest,
            'leaf_count':len(leaves),
            'upper_bound_ceil_display':ub.as_float(UP),
            'incumbent_lower_floor_display':lb.as_float(DOWN),
            'objective_bounds_recomputed':True,
            'partition_cover_verified':True,
            'claim_is_global_on_Rd':False,
            'production_release':'NO_GO',
            'leaf_methods':methods}


def cli():
    ap=argparse.ArgumentParser()
    ap.add_argument('certificate')
    ap.add_argument('--expected-digest',default=None)
    ap.add_argument('--bits',type=int,default=None)
    a=ap.parse_args()
    with open(a.certificate) as f:c=json.load(f)
    out=verify(c,precision_bits=a.bits,expected_digest=a.expected_digest)
    print(json.dumps(out,indent=2))
    if out['result']!='VERIFIED_BOUNDED_GAP':raise SystemExit(2)

if __name__=='__main__':cli()
