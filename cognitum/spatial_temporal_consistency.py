"""C15 T3 P2S: research-only, bounded cross-capture occupancy change tracking.

Never interprets an occupancy prediction as certified free space. Uses P2R
per-capture (within-frame) evidence, then transparent heuristic temporal decay.
No host authority and no learned sensor statistics are assumed.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math

from cognitum.proto import spatial_temporal_consistency_pb2 as pb
from cognitum.proto import spatial_volume_pb2 as volume_pb
from cognitum.spatial_correlated_fusion import fuse as fuse_capture, CorrelatedFusionRejected
from cognitum.spatial_volume import classify as classify_volume, VolumeRejected

MAX_REQUEST_BYTES = 900_000
MAX_CAPTURES = 12
MAX_CELLS = 4096


class TemporalConsistencyRejected(ValueError):
    pass


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise TemporalConsistencyRejected(reason)


def _hash(m):
    return hashlib.sha256(m.SerializeToString(deterministic=True)).digest()


def _known(m):
    other = type(m)()
    other.CopyFrom(m)
    other.DiscardUnknownFields()
    return m.SerializeToString(deterministic=True) == other.SerializeToString(deterministic=True)


def _prob(logodds):
    return 1. / (1. + math.exp(-logodds))


def _clamp(v):
    return max(-8., min(8., v))


def reconcile(req: pb.P2STemporalRequest) -> pb.P2STemporalResult:
    _require(isinstance(req, pb.P2STemporalRequest) and req.schema_version == 1
             and req.research_only and not req.grants_authority and _known(req)
             and req.ByteSize() <= MAX_REQUEST_BYTES, 'INVALID_P2S_CONTRACT')
    _require(2 <= len(req.captures) <= MAX_CAPTURES
             and 0 < req.evaluation_tick
             and math.isfinite(req.half_life_ticks)
             and 0 < req.half_life_ticks <= 1e9
             and math.isfinite(req.historical_retention)
             and 0 <= req.historical_retention <= 1
             and 2 <= req.min_stable_observations <= MAX_CAPTURES
             and 1 <= req.max_age_ticks <= 1_000_000,
             'INVALID_TEMPORAL_POLICY')
    evidence = defaultdict(list)
    capture_ids = set()
    frame_identity = set()
    prev_tick = 0
    baseline_grid = None
    for capture in req.captures:
        d = capture.depth
        _require(d.conversation_id == req.conversation_id and d.volume_id == req.volume_id
                 and capture.research_only and not capture.grants_authority
                 and d.research_only and not d.grants_authority
                 and 1 <= len(d.pixels) <= 256,
                 'INVALID_OR_CROSS_SCOPE_CAPTURE')
        tick = d.pixels[0].tick
        frame = (d.pixels[0].source_ref, bytes(d.pixels[0].depth_frame_sha256))
        _require(tick > prev_tick and tick <= req.evaluation_tick
                 and d.evaluation_tick == tick
                 and all(p.tick == tick and
                         (p.source_ref, bytes(p.depth_frame_sha256)) == frame
                         for p in d.pixels),
                 'OUT_OF_ORDER_OR_MIXED_CAPTURE')
        _require(d.capture_id and d.capture_id not in capture_ids
                 and frame not in frame_identity,
                 'REPLAYED_OR_DUPLICATE_CAPTURE')
        spec = (d.voxel_size_m, d.max_axis)
        _require(baseline_grid is None or spec == baseline_grid,
                 'INCOMPATIBLE_VOLUME_GRID')
        baseline_grid = spec
        capture_ids.add(d.capture_id)
        frame_identity.add(frame)
        prev_tick = tick
        try:
            output = fuse_capture(capture)
        except CorrelatedFusionRejected as exc:
            raise TemporalConsistencyRejected('INVALID_P2R_CAPTURE:' + str(exc)) from exc
        for c in output.cells:
            _require(math.isfinite(c.adjusted_log_odds), 'NONFINITE_CAPTURE_LOGODDS')
            evidence[c.x, c.y, c.z].append((d.capture_id, tick,
                c.adjusted_log_odds, output.request_sha256,
                c.conflicting_observations))
        _require(len(evidence) <= MAX_CELLS, 'TEMPORAL_CELL_RESOURCE_LIMIT')

    result = pb.P2STemporalResult(
        schema_version=1, conversation_id=req.conversation_id,
        volume_id=req.volume_id, request_sha256=_hash(req),
        research_only=True, grants_authority=False,
        total_capture_count=len(req.captures))
    vox = volume_pb.VolumeGrid(schema_version=1,
        conversation_id=req.conversation_id, volume_id=req.volume_id,
        voxel_size_m=baseline_grid[0], max_axis=baseline_grid[1],
        research_only=True, grants_authority=False)
    for (x, y, z), events in sorted(evidence.items()):
        # Each event is one P2R correlation-adjusted capture, never one raw pixel.
        # A mixed free/hit P2R voxel is *not* a trusted sign, even when its
        # summed log-odds has a nonzero sign. Do not bridge through missing or
        # mixed observations when demanding a consecutive change-point streak.
        flags = [0 if e[4] else 1 if e[2] > 1e-12
                 else -1 if e[2] < -1e-12 else 0 for e in events]
        direction = flags[-1]
        latest_count = 0
        start = len(events) - 1
        if direction:
            for i in range(len(flags) - 1, -1, -1):
                if flags[i] != direction:
                    break
                latest_count += 1
                start = i
        opposed = bool(direction) and any(
            flag == -direction for flag in flags[:start])
        confirmed = opposed and latest_count >= req.min_stable_observations
        pending = opposed and not confirmed
        change_tick = events[start][1] if opposed else 0
        baseline_terms = []
        adjusted_terms = []
        cell = result.cells.add(x=x, y=y, z=z,
            observed_capture_count=len(events), latest_tick=events[-1][1],
            latest_consistent_streak=latest_count,
            change_candidate_tick=change_tick,
            opposed_across_captures=opposed,
            change_confirmed=confirmed)
        for i, (capture_id, tick, logodds, source_sha, _mixed) in enumerate(events):
            temporal_weight = 2. ** (-(req.evaluation_tick - tick) / req.half_life_ticks)
            # Only AFTER a confirmed streak: discount earlier opposite-era
            # evidence. Never delete the audit trail or assume actual motion.
            retention = req.historical_retention if confirmed and i < start else 1.
            baseline_terms.append(logodds * temporal_weight)
            adjusted_terms.append(logodds * temporal_weight * retention)
            cell.provenance.add(capture_id=capture_id, tick=tick,
                capture_log_odds=logodds, temporal_weight=temporal_weight,
                retention_multiplier=retention, capture_request_sha256=source_sha)
        cell.baseline_log_odds = _clamp(math.fsum(baseline_terms))
        cell.adjusted_log_odds = _clamp(math.fsum(adjusted_terms))
        cell.baseline_probability = _prob(cell.baseline_log_odds)
        cell.adjusted_probability = _prob(cell.adjusted_log_odds)
        if pending:
            result.pending_change_cell_count += 1
        if confirmed:
            result.confirmed_change_cell_count += 1
        if req.evaluation_tick - events[-1][1] > req.max_age_ticks:
            cell.state = pb.P2S_STALE
        elif pending or events[-1][4]:
            cell.state = pb.P2S_CONTESTED
        elif (latest_count < req.min_stable_observations or
              direction * cell.adjusted_log_odds < math.log(3)):
            # A sign-confirmed change is not a usable prediction if its total
            # weighted evidence still favors the opposite state.
            cell.state = pb.P2S_INDETERMINATE
        elif confirmed:
            cell.state = (pb.P2S_RECOVERED_OCCUPIED if direction > 0
                          else pb.P2S_RECOVERED_FREE)
        else:
            cell.state = (pb.P2S_PREDICTED_OCCUPIED if direction > 0
                          else pb.P2S_PREDICTED_FREE)
        # After a reversal, require one *extra* consistent capture before
        # forwarding even a predicted-only claim to T2. No canonical writes.
        if cell.state in (pb.P2S_PREDICTED_OCCUPIED, pb.P2S_PREDICTED_FREE,
                          pb.P2S_RECOVERED_OCCUPIED, pb.P2S_RECOVERED_FREE) and (
                not confirmed or latest_count >= req.min_stable_observations + 1):
            occupied = cell.state in (pb.P2S_PREDICTED_OCCUPIED, pb.P2S_RECOVERED_OCCUPIED)
            reliability = cell.adjusted_probability if occupied else 1 - cell.adjusted_probability
            vox.evidence.add(x=x, y=y, z=z,
                kind=(volume_pb.VOLUME_PREDICTED_OCCUPIED if occupied
                      else volume_pb.VOLUME_PREDICTED_FREE),
                source_id='p2s.' + result.request_sha256.hex()[:32],
                tick=req.evaluation_tick,
                reliability=max(.5, min(.999, reliability)))
    _require(len(vox.evidence) <= MAX_CELLS, 'HYPOTHETICAL_VOLUME_RESOURCE_LIMIT')
    try:
        assessed = classify_volume(vox)
    except VolumeRejected as exc:
        raise TemporalConsistencyRejected('INVALID_T2_PREDICTED_HANDOFF:' + str(exc)) from exc
    _require(all(c.state == volume_pb.CELL_UNKNOWN for c in assessed.cells),
             'ILLEGAL_T2_PROMOTION')
    result.hypothetical_volume.CopyFrom(vox)
    result.warnings.extend([
        'SOURCE_FRAME_IDS_AND_DEPTH_NOT_AUTHENTICATED',
        'P2R_CORRELATION_AND_CROSS_CAPTURE_INDEPENDENCE_NOT_CALIBRATED',
        'DECAY_AND_CHANGE_POINT_POLICY_ARE_CALLER_SUPPLIED_HEURISTICS',
        'CONFIRMED_CHANGE_MEANS_STREAK_TEST_NOT_PHYSICAL_GROUND_TRUTH',
        'PREDICTED_ONLY_T2_HANDOFF_NO_CANONICAL_MUTATION',
        'DO_NOT_USE_FOR_NAVIGATION_COLLISION_OR_SAFETY_DECISIONS',
    ])
    return result


def verify(req: pb.P2STemporalRequest, output: pb.P2STemporalResult) -> bool:
    _require(isinstance(output, pb.P2STemporalResult) and _known(output),
             'INVALID_P2S_RESULT')
    _require(output.SerializeToString(deterministic=True) ==
             reconcile(req).SerializeToString(deterministic=True),
             'P2S_REPLAY_MISMATCH')
    return True
