"""C15 source-aware 3D observation agreement and uncertainty abstention.

Established SciPy spatial distances and normal-distribution quantiles are used.
No learned calibration, no remote sensor trust and no statistical independence
assumption silently inferred. Contradictory camera observations are not fused.
"""
from dataclasses import dataclass
from math import isfinite
from .spatial_geometry import Frame,Scene,SceneObject,world_position,validate as validate_scene


@dataclass(frozen=True)
class MetricObservation:
    observation_id:str
    stable_id:str
    source_id:str
    frame_id:str
    point_m:tuple[float,float,float]
    sigma_m:float
    observed_at_ms:int
    source_authorization_ref:str


@dataclass(frozen=True)
class Consistency:
    status:str  # CONSISTENT | CONFLICT | INSUFFICIENT | UNSUPPORTED
    separation_m:float|None=None
    normalized_separation:float|None=None
    allowed_sigma:float|None=None
    limitations:tuple[str,...]=(
        "caller_supplied_sources_not_authenticated",
        "sigma_assumes_isotropic_3D_measurement_error",
        "source_correlation_unknown_no_weighted_fusion",
        "semantic_object_identity_not_automatically_established",
    )


def compare_observations(
    frames:tuple[Frame,...],first:MetricObservation,second:MetricObservation,
    *,epoch:int,allowed_sigma:float=3.0
)->Consistency:
    def valid(obs):
        return (type(obs) is MetricObservation
                and all(type(getattr(obs,n)) is str
                        and getattr(obs,n).isascii() and getattr(obs,n).isidentifier()
                        for n in ("observation_id","stable_id","source_id",
                                  "frame_id","source_authorization_ref"))
                and type(obs.point_m) is tuple and len(obs.point_m)==3
                and all(type(x) in (int,float) and isfinite(x)
                        and abs(x)<=1_000_000 for x in obs.point_m)
                and type(obs.sigma_m) in (int,float) and isfinite(obs.sigma_m)
                and 0.000001<=obs.sigma_m<=1_000_000
                and type(obs.observed_at_ms) is int
                and 0<=obs.observed_at_ms<=epoch)
    if (not valid(first) or not valid(second) or first.stable_id!=second.stable_id
            or first.observation_id==second.observation_id
            or first.source_id==second.source_id
            or first.observed_at_ms!=second.observed_at_ms
            or type(allowed_sigma) not in (int,float)
            or not isfinite(allowed_sigma) or not 1<=allowed_sigma<=10):
        raise ValueError("observations lack independent concurrent source claims")
    # Reuse exact validated typed frame chain; no coordinate system guessing.
    objects=(
        SceneObject("source_a",first.frame_id,first.point_m,(1.,1.,1.),True,
                    first.source_id,first.observed_at_ms),
        SceneObject("source_b",second.frame_id,second.point_m,(1.,1.,1.),True,
                    second.source_id,second.observed_at_ms),
    )
    scene=validate_scene(Scene(frames,objects,epoch))
    try:
        from scipy.spatial.distance import euclidean
    except ImportError:
        return Consistency("UNSUPPORTED")
    a=world_position(scene,"source_a")
    b=world_position(scene,"source_b")
    separation=float(euclidean(a,b))
    # Without proved independent noise or covariance, use conservative sigma
    # addition rather than sqrt(sum(sigma^2)); avoid unjustified fusion.
    combined=first.sigma_m+second.sigma_m
    normalized=separation/combined
    return Consistency("CONFLICT" if normalized>allowed_sigma else "CONSISTENT",
                       separation,normalized,allowed_sigma)
