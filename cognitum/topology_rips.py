"""C19 bounded Vietoris-Rips H0/H1 on caller-supplied numeric snapshots.

Ripser is the actual persistent-homology engine, not custom topology.
SciPy verifies zero-dimensional merges by independent minimum spanning tree.
No embeddings or topology results are declared semantic truth or Lu memory.
"""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
import json

MAX_POINTS=64
MAX_FEATURES=8
MAX_INTERVALS=256

@dataclass(frozen=True)
class TopologyQuery:
    source_id:str
    snapshot_sha256:str
    coordinate_unit:str
    metric:str             # euclidean | manhattan
    filtration:str         # vietoris_rips
    maximum_scale:float
    maximum_homology_dimension:int  # 0 | 1
    points:tuple[tuple[float,...],...]
    max_points:int=MAX_POINTS

@dataclass(frozen=True)
class Interval:
    dimension:int
    birth:float
    death:float|None   # None denotes essential (infinite) persistence

@dataclass(frozen=True)
class TopologyResult:
    status:str
    source_id:str
    snapshot_sha256:str
    metric:str
    coordinate_unit:str
    filtration:str
    maximum_scale:float
    intervals:tuple[Interval,...]=()
    connected_components_at_scale:int=0
    persistent_h1_count:int=0
    longest_finite_h1:float=0.
    h0_mst_max_deviation:float|None=None
    input_points:int=0
    unique_points:int=0
    resource_pair_bound:int=0
    limitations:tuple[str,...]=(
        "threshold_truncated_diagram_not_full_complex",
        "essential_classes_are_not_unbounded_evidence_of_real_structure",
        "topology_not_semantic_truth_or_canonical_Lu_memory",
        "metric_sampling_and_units_define_the_answer",
        "hash_is_snapshot_correlation_not_source_authentication",
    )

def snapshot_hash(points):
    return sha256(json.dumps(points,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def _id(s):
    return type(s) is str and s.isascii() and s.isidentifier() and 1<=len(s)<=64

def validate(q):
    if (type(q) is not TopologyQuery or not _id(q.source_id)
            or type(q.coordinate_unit) is not str or not _id(q.coordinate_unit)
            or q.metric not in ("euclidean","manhattan")
            or q.filtration!="vietoris_rips"
            or type(q.maximum_homology_dimension) is not int
            or q.maximum_homology_dimension not in (0,1)
            or type(q.maximum_scale) not in (int,float)
            or not isfinite(q.maximum_scale) or not 0<q.maximum_scale<=10000
            or type(q.max_points) is not int or not 3<=q.max_points<=MAX_POINTS
            or type(q.points) is not tuple or not 3<=len(q.points)<=q.max_points):
        raise ValueError("invalid bounded TDA query")
    dim=len(q.points[0]) if type(q.points[0]) is tuple else 0
    if not 1<=dim<=MAX_FEATURES:
        raise ValueError("invalid point dimension")
    if any(type(row) is not tuple or len(row)!=dim
           or any(type(v) not in (float,int) or not isfinite(v) or abs(v)>1e5
                  for v in row) for row in q.points):
        raise ValueError("invalid/nonfinite coordinates")
    if type(q.snapshot_sha256) is not str or q.snapshot_sha256!=snapshot_hash(q.points):
        raise ValueError("source snapshot digest mismatch")
    return q

def _distances(q):
    import numpy as np
    from scipy.spatial.distance import pdist,squareform
    X=np.asarray(q.points,dtype=float)
    return squareform(pdist(X,metric="cityblock" if q.metric=="manhattan" else "euclidean"))

def compute(q:TopologyQuery)->TopologyResult:
    validate(q)
    try:
        import numpy as np
        from scipy.sparse.csgraph import minimum_spanning_tree
        from ripser import ripser
    except ImportError:
        return TopologyResult("UNSUPPORTED",q.source_id,q.snapshot_sha256,
                              q.metric,q.coordinate_unit,q.filtration,q.maximum_scale)
    dist=_distances(q)
    if not np.all(np.isfinite(dist)):
        raise ValueError("nonfinite pair distances")
    n=len(q.points)
    # Independent MST zero-dimensional reference on the full metric graph.
    # Nonzero MST edges equal finite H0 deaths, including ties in the metric.
    mst=minimum_spanning_tree(dist)
    mst_lengths=sorted(float(v) for v in mst.data if v<=q.maximum_scale+1e-6)
    raw=ripser(dist,distance_matrix=True,maxdim=q.maximum_homology_dimension,
               thresh=q.maximum_scale,coeff=2,do_cocycles=False)["dgms"]
    intervals=[]
    for dim,diagram in enumerate(raw):
        for birth,death in diagram:
            b=float(birth)
            d=None if not isfinite(float(death)) else float(death)
            if not isfinite(b) or b<0 or (d is not None and d<b-1e-6):
                raise ValueError("invalid persisted interval from TDA engine")
            intervals.append(Interval(dim,b,d))
    if len(intervals)>MAX_INTERVALS:
        raise ValueError("unbounded topology output")
    intervals.sort(key=lambda x:(x.dimension,x.birth,float("inf") if x.death is None else x.death))
    h0_finite=sorted(x.death for x in intervals if x.dimension==0 and x.death is not None)
    if len(h0_finite)!=len(mst_lengths):
        raise ValueError("independent SciPy H0 merge count differs")
    deviation=max([abs(a-b) for a,b in zip(h0_finite,mst_lengths)] or [0.])
    if deviation>2e-4*max(1.,q.maximum_scale):
        raise ValueError("independent SciPy H0 MST check failed")
    # One H0 component is essential; remaining are finite or censored.
    essential=sum(x.dimension==0 and x.death is None for x in intervals)
    if essential<1:
        raise ValueError("no essential H0 class")
    h1=[x for x in intervals if x.dimension==1 and x.death is not None]
    return TopologyResult(
        "OK",q.source_id,q.snapshot_sha256,q.metric,q.coordinate_unit,
        q.filtration,q.maximum_scale,tuple(intervals),
        essential,len(h1),max((x.death-x.birth for x in h1),default=0.),
        deviation,n,len(set(q.points)),n*(n-1)//2)

def perturbation_stability(original:TopologyQuery,challenger:TopologyQuery):
    """Cross-dataset bottleneck discrepancy, descriptive not guaranteed bound."""
    validate(original);validate(challenger)
    if (original.metric!=challenger.metric or original.coordinate_unit!=challenger.coordinate_unit
            or original.maximum_scale!=challenger.maximum_scale
            or original.maximum_homology_dimension!=challenger.maximum_homology_dimension):
        raise ValueError("incomparable diagrams")
    try:
        from persim import bottleneck
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("persim_diagram_distance_unavailable") from exc
    a=compute(original);b=compute(challenger)
    if a.status!="OK" or b.status!="OK":raise RuntimeError("TDA engine unavailable")
    distances=[]
    for dim in range(original.maximum_homology_dimension+1):
        def finite(r):
            return np.asarray([(x.birth,x.death) for x in r.intervals
                 if x.dimension==dim and x.death is not None],dtype=float).reshape(-1,2)
        distances.append(float(bottleneck(finite(a),finite(b))))
    if any(not isfinite(d) for d in distances):
        raise ValueError("invalid bottleneck comparison")
    return tuple(distances)
