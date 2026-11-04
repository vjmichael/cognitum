"""C19 independent GUDHI cross-engine diagram comparison against Ripser.

Rips filtration semantics: a simplex appears at the maximum edge distance.
Finite H0/H1 intervals are compared with numerical tolerance, not mixed
with their censoring-dependent essential classes at the scale boundary.
"""
from dataclasses import dataclass
from math import isfinite
from .topology_rips import TopologyQuery,compute,validate,_distances

@dataclass(frozen=True)
class CrossCheck:
    status:str
    compared_finite_intervals:int=0
    maximum_endpoint_deviation:float|None=None
    ripser_h0_essential:int=0
    gudhi_h0_essential:int=0
    limitations:tuple[str,...]=(
        "two_engines_share_Vietoris_Rips_filtration_assumptions",
        "finite_endpoint_equality_not_semantic_or_source_validity",
        "bounded_to_40_points_for_expanded_2_skeleton",
    )

def crosscheck(q:TopologyQuery):
    validate(q)
    if len(q.points)>40:
        return CrossCheck("UNSUPPORTED_COMPLEX_SIZE")
    try:
        import gudhi
    except ImportError:
        return CrossCheck("UNSUPPORTED_GUDHI")
    result=compute(q)
    if result.status!="OK":
        return CrossCheck("UNSUPPORTED_RIPSER")
    distances=_distances(q)
    tree=gudhi.RipsComplex(distance_matrix=distances.tolist(),
                          max_edge_length=q.maximum_scale).create_simplex_tree(
                              max_dimension=q.maximum_homology_dimension+1)
    bars=tree.persistence(homology_coeff_field=2,min_persistence=0.)
    def convert(from_engine):
        output={}
        for dim,b,d in from_engine:
            if dim>q.maximum_homology_dimension:
                continue
            if not isfinite(b):
                raise ValueError("invalid persistence birth")
            if d is not None and not isfinite(d):
                d=None
            output.setdefault(dim,[]).append((float(b),None if d is None else float(d)))
        return output
    first=convert((x.dimension,x.birth,x.death) for x in result.intervals)
    # GUDHI returns (homology_dimension, (birth, death)), unlike Ripser's
    # already-flattened Interval objects. Expand the nested tuple explicitly.
    second=convert((dimension,float(interval[0]),float(interval[1]))
                   for dimension,interval in bars)
    largest=0.
    compared=0
    for dim in range(q.maximum_homology_dimension+1):
        x=sorted((a,b) for a,b in first.get(dim,()) if b is not None)
        y=sorted((a,b) for a,b in second.get(dim,()) if b is not None)
        if len(x)!=len(y):
            raise ValueError("different finite homology interval counts")
        for (ab,ad),(bb,bd) in zip(x,y):
            largest=max(largest,abs(ab-bb),abs(ad-bd))
            compared+=1
    if largest>2e-4*max(1.,q.maximum_scale):
        raise ValueError("disagreeing independent Rips persistence endpoints")
    return CrossCheck("MATCH",compared,largest,
           sum(x.death is None and x.dimension==0 for x in result.intervals),
           sum(d is None for b,d in second.get(0,())))
