"""C19 deterministic subsampling and outlier sensitivity report.

The report is observational only. It never claims a persistence
stability theorem or that dropped points are noise.
"""
from dataclasses import dataclass
from math import isfinite
from .topology_rips import TopologyQuery,snapshot_hash,validate,compute,perturbation_stability,_distances

@dataclass(frozen=True)
class Sensitivity:
    status:str
    sample_original:int
    sample_retained:int
    sample_indices:tuple[int,...]
    bottleneck_by_dimension:tuple[float,...]
    original_longest_h1:float
    sampled_longest_h1:float
    longest_h1_change:float
    limitations:tuple[str,...]=(
        "farthest_point_deterministic_subsampling_changes_observed_dataset",
        "bottleneck_of_threshold_censored_intervals_is_descriptive_only",
        "sensitivity_not_confidence_interval_or_outlier_ground_truth",
    )

def deterministic_farthest(q:TopologyQuery,keep:int):
    validate(q)
    if (type(keep) is not int or keep<3 or keep>len(q.points)):
        raise ValueError("invalid retained point count")
    D=_distances(q)
    picked=[0]
    selected={0}
    while len(picked)<keep:
        candidate=max(
            (i for i in range(len(q.points)) if i not in selected),
            key=lambda i:(min(float(D[i,j]) for j in picked),-i))
        picked.append(candidate)
        selected.add(candidate)
    # Snapshot reflects exactly chosen points in selection order. The
    # ordering is deterministic and no future labels/ground truth are read.
    selected_points=tuple(q.points[i] for i in picked)
    return tuple(picked),TopologyQuery(q.source_id,snapshot_hash(selected_points),
        q.coordinate_unit,q.metric,q.filtration,q.maximum_scale,
        q.maximum_homology_dimension,selected_points,q.max_points)

def check_sensitivity(q:TopologyQuery,*,keep:int):
    indices,reduced=deterministic_farthest(q,keep)
    original=compute(q)
    sampled=compute(reduced)
    if original.status!="OK" or sampled.status!="OK":
        return Sensitivity("UNSUPPORTED",len(q.points),keep,indices,(),
                           0.,0.,0.)
    distances=perturbation_stability(q,reduced)
    return Sensitivity("MEASURED",len(q.points),keep,indices,distances,
                       original.longest_finite_h1,
                       sampled.longest_finite_h1,
                       abs(original.longest_finite_h1-sampled.longest_finite_h1))
