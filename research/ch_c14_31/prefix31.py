"""Produce *derived proof snapshots* from original CH29 certificates.

These are byte-for-byte original CH29 nodes truncated at an odd prefix length,
with only split edges beyond that prefix removed.  This is a verifier experiment,
NOT a new search or a claim that these checkpoints were produced by CH29.
"""
from __future__ import annotations
import copy

def project_prefix(source:dict, size:int) -> dict:
    """Return a closed prefix (for the original binary CH29 proof tree)."""
    nodes=source['nodes']
    if type(size) is not int or size<1 or size>len(nodes) or size%2!=1:
        raise ValueError('Only positive odd CH29 prefix lengths are supported')
    result=copy.deepcopy(source)
    result['nodes']=copy.deepcopy(nodes[:size])
    for n in result['nodes']:
        if 'children' in n:
            children=n['children']
            if len(children)!=2 or (children[0]<size)!=(children[1]<size):
                raise ValueError('Prefix would cut a pair of children')
            if children[0]>=size:
                del n['children'];del n['split_dim']
        elif 'split_dim' in n:
            raise ValueError('Malformed original proof node')
    result['leaf_count']=sum('children' not in n and n.get('newton',{}).get('status')!='NO_STATIONARY'
                             for n in result['nodes'])
    result['newton_exclusions']=sum(n.get('newton',{}).get('status')=='NO_STATIONARY' for n in result['nodes'])
    result['newton_contractions']=sum(n.get('newton',{}).get('status')=='CONTRACTED' for n in result['nodes'])
    # Calls with NO_GAIN were not recorded in the underlying CH29 node stream;
    # this research projection reports only externally verifiable calls.
    result['newton_calls']=result['newton_exclusions']+result['newton_contractions']
    result['counters']={'derived_proof_prefix':True,'source_milestone':'CH-C14-29',
                        'not_a_new_solver_run':True}
    result['research_projection_nodes']=size
    result['research_projection_notice']='Derived verification snapshot, NOT a fresh CH29 solver run'
    result['status']='UNRESOLVED_REFUSE_CERTIFICATION'  # Never promote a projected proof.
    return result
