"""C15 T3 P2R: research-only bounded, correlation-aware sparse fusion.

Uses P2Q validated frame-to-ray projection without changing the existing P2C
independent-ray engine. Caller-declared per-frame correlation is *not* learned,
verified or valid across arbitrary physical sensors. No output grants authority.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math

from cognitum.proto import spatial_correlated_fusion_pb2 as pb
from cognitum.proto import spatial_volume_pb2 as vp
from cognitum.spatial_calibrated_depth import project as project_depth, CalibratedDepthRejected
from cognitum.spatial_ray_occupancy import _dda
from cognitum.spatial_temporal_occupancy import _rotate
from cognitum.spatial_volume import classify as classify_volume, VolumeRejected

MAX_BYTES = 130_000
SENSITIVITY_RHOS = (0., .25, .5, .75, 1.)


class CorrelatedFusionRejected(ValueError):
    pass


def _require(ok, reason):
    if not ok:
        raise CorrelatedFusionRejected(reason)


def _sha(message):
    return hashlib.sha256(message.SerializeToString(deterministic=True)).digest()


def _known(message):
    other = type(message)()
    other.CopyFrom(message)
    other.DiscardUnknownFields()
    return _sha(other) == _sha(message)


def _xyz(p):
    return p.x, p.y, p.z


def _logistic(v):
    return 1. / (1. + math.exp(-v))


def _clamp(v):
    return max(-8., min(8., v))


def _model(groups, rho):
    # Standard equicorrelation n_eff = n/(1+(n-1)*rho), applied to
    # temporal-weighted signed observations. NOT a calibrated sensor model.
    return _clamp(math.fsum(
        math.fsum(values) / (1. + (len(values)-1) * rho)
        for _, values in sorted(groups.items())
    ))


def fuse(req: pb.P2RFusionRequest) -> pb.P2RFusionResult:
    _require(isinstance(req, pb.P2RFusionRequest) and req.schema_version == 1
             and req.research_only and not req.grants_authority
             and req.HasField('depth') and _known(req)
             and req.ByteSize() <= MAX_BYTES,
             'INVALID_RESEARCH_FUSION_CONTRACT')
    rho = req.assumed_within_capture_rho
    _require(math.isfinite(rho) and 0. <= rho <= 1., 'INVALID_CORRELATION_ASSUMPTION')
    try:
        baseline = project_depth(req.depth)
    except CalibratedDepthRejected as exc:
        raise CorrelatedFusionRejected('INVALID_P2Q_DEPTH:' + str(exc)) from exc
    temporal = baseline.temporal_request
    _require(len(temporal.frames) == 1 and len(temporal.rays) == len(baseline.projections),
             'INCONSISTENT_PROJECTION_COUNT')
    camera = temporal.frames[0]
    q = (camera.qw, camera.qx, camera.qy, camera.qz)
    translate = _xyz(camera.translation)
    maxworld = temporal.max_axis * temporal.voxel_size_m
    provenance = {p.derived_ray_source_ref: p for p in baseline.projections}
    _require(len(provenance) == len(baseline.projections), 'DUPLICATE_DERIVED_RAY')
    evidence = defaultdict(lambda: defaultdict(list))
    counters = defaultdict(lambda: [0, 0])
    for ray in temporal.rays:
        mapping = provenance.pop(ray.source_ref, None)
        _require(mapping is not None and ray.tick == mapping.tick and
                 mapping.endpoint_hit == ray.endpoint_hit, 'RAY_PROVENANCE_MISMATCH')
        start = tuple(a+b for a,b in zip(_rotate(q, _xyz(ray.start)), translate))
        end = tuple(a+b for a,b in zip(_rotate(q, _xyz(ray.end)), translate))
        _require(all(math.isfinite(t) and 0 <= t < maxworld for t in start+end),
                 'INVALID_WORLD_RAY')
        try:
            cells = _dda(start, end, temporal.voxel_size_m, temporal.max_axis,
                         include_endpoint_cell=ray.endpoint_hit)
        except (ValueError, OverflowError) as exc:
            raise CorrelatedFusionRejected('INVALID_VOXEL_TRAVERSAL') from exc
        # Group by raw input source + same claimed frame payload, ignoring tick;
        # exact replay of the same frame cannot create new independent evidence.
        # Distinct sources/hashes are NOT asserted independent in the real world.
        cluster = (mapping.source_ref, bytes(mapping.depth_frame_sha256))
        time_weight = 2. ** (-(temporal.evaluation_tick-ray.tick)/temporal.half_life_ticks)
        for i, cell in enumerate(cells):
            hit = bool(ray.endpoint_hit and i == len(cells)-1)
            p = ray.hit_probability if hit else ray.free_probability
            evidence[cell][cluster].append(math.log(p/(1.-p)) * time_weight)
            counters[cell][0 if hit else 1] += 1
    _require(not provenance and len(evidence) <= 16384, 'UNMATCHED_RAYS_OR_CAPACITY')
    original = {(c.x,c.y,c.z):c for c in baseline.temporal_result.cells}
    _require(set(evidence) == set(original), 'INDEPENDENT_CELL_SET_MISMATCH')
    out = pb.P2RFusionResult(
        schema_version=1, conversation_id=req.depth.conversation_id,
        volume_id=req.depth.volume_id, request_sha256=_sha(req),
        baseline_p2q_sha256=_sha(baseline), research_only=True,
        grants_authority=False, assumed_within_capture_rho=rho)
    out.independent_baseline.CopyFrom(baseline)
    volume = vp.VolumeGrid(schema_version=1, conversation_id=req.depth.conversation_id,
                            volume_id=req.depth.volume_id,
                            voxel_size_m=req.depth.voxel_size_m,
                            max_axis=req.depth.max_axis,
                            research_only=True, grants_authority=False)
    source_id = 'p2r.' + out.request_sha256.hex()[:32]
    for cell, clusters in sorted(evidence.items()):
        raw = _model(clusters, 0.)
        old = original[cell]
        _require(math.isclose(raw, old.log_odds, abs_tol=1e-10, rel_tol=1e-10),
                 'RHO_ZERO_BASELINE_DISAGREEMENT')
        adjusted = _model(clusters, rho)
        sensitivity = [_logistic(_model(clusters, k)) for k in SENSITIVITY_RHOS]
        hits, frees = counters[cell]
        _require(hits == old.hit_count and frees == old.free_count,
                 'BASELINE_COUNT_DISAGREEMENT')
        out.cells.add(
            x=cell[0],y=cell[1],z=cell[2],
            independent_log_odds=old.log_odds,
            independent_probability=old.probability,
            adjusted_log_odds=adjusted,adjusted_probability=_logistic(adjusted),
            hit_count=hits,free_count=frees,
            capture_group_count=len(clusters),
            largest_correlated_group=max(map(len,clusters.values())),
            sensitivity_min_probability=min(sensitivity),
            sensitivity_max_probability=max(sensitivity),
            conflicting_observations=bool(hits and frees))
        # Strictly hypothetical output. Source ids are digests, not signatures.
        if hits and frees or .35 < _logistic(adjusted) < .65:
            continue
        occupied = adjusted >= 0
        prob = _logistic(adjusted)
        volume.evidence.add(x=cell[0],y=cell[1],z=cell[2],
            kind=vp.VOLUME_PREDICTED_OCCUPIED if occupied else vp.VOLUME_PREDICTED_FREE,
            source_id=source_id, tick=req.depth.evaluation_tick,
            reliability=max(.5, min(.999, prob if occupied else 1.-prob)))
    _require(len(volume.evidence) <= 8192, 'HYPOTHETICAL_VOLUME_CAPACITY')
    try:
        result = classify_volume(volume)
    except VolumeRejected as exc:
        raise CorrelatedFusionRejected('VOLUME_HANDOFF_REJECTED:' + str(exc)) from exc
    _require(all(c.state == vp.CELL_UNKNOWN for c in result.cells),
             'ILLEGAL_HYPOTHESIS_PROMOTION')
    out.hypothetical_volume.CopyFrom(volume)
    out.warnings.extend([
        'P2Q_INDEPENDENT_BASELINE_UNCHANGED_FOR_COMPARISON_ONLY',
        'EQUICORRELATION_RHO_CALLER_SUPPLIED_NOT_CALIBRATED',
        'SOURCE_AND_FRAME_DIGESTS_UNAUTHENTICATED_GROUP_IDENTITIES',
        'DISTINCT_FRAMES_AND_SENSORS_MAY_ALSO_BE_CORRELATED',
        'SENSITIVITY_GRID_NOT_CONFIDENCE_INTERVAL',
        'NO_REAL_WORLD_OCCUPANCY_OR_HOST_PERMISSION_CLAIMS',
        'T2_HANDOFF_PREDICTED_ONLY_NO_CANONICAL_MUTATION',
    ])
    return out


def verify(req: pb.P2RFusionRequest, result: pb.P2RFusionResult) -> bool:
    _require(isinstance(result, pb.P2RFusionResult) and _known(result),
             'INVALID_FUSION_RESULT')
    computed = fuse(req)
    _require(result.SerializeToString(deterministic=True) ==
             computed.SerializeToString(deterministic=True),
             'FUSION_EVIDENCE_MISMATCH')
    return True
