"""C15 T3 P2V: conservative, replayable camera/occlusion/static-map gates.

A read-only research adapter over P2U. P2Q has already transformed calibrated
rays into the caller's world frame; this module never reprojects them again.
Camera extrinsics, frame digests and T1 identities are caller supplied, not
sensor or identity authentication. Missing observations are NOT proof of occlusion.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math

from cognitum.proto import spatial_dynamic_scene_robustness_pb2 as pb
from cognitum.proto import spatial_dynamic_scene_mapping_pb2 as upb
from cognitum.proto import spatial_volume_pb2 as vpb
from cognitum.spatial_dynamic_scene_mapping import map_scene, DynamicSceneRejected
from cognitum.spatial_temporal_consistency import reconcile, TemporalConsistencyRejected
from cognitum.spatial_volume import classify, VolumeRejected

MAX_BYTES = 8_000_000
MAX_CAPTURES = 96

class RobustnessRejected(ValueError):
    pass

def _check(condition, reason):
    if not condition:
        raise RobustnessRejected(reason)

def _sha(msg):
    return hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()

def _known(msg):
    clean = type(msg)()
    clean.CopyFrom(msg)
    clean.DiscardUnknownFields()
    return clean.SerializeToString(deterministic=True) == msg.SerializeToString(deterministic=True)

def _xyz(v):
    result = (v.x, v.y, v.z)
    _check(all(math.isfinite(x) and abs(x) <= 1e6 for x in result), 'INVALID_CAMERA_TRANSLATION')
    return result

def _rotation_step(a, b):
    q1 = (a.qw, a.qx, a.qy, a.qz)
    q2 = (b.qw, b.qx, b.qy, b.qz)
    _check(all(math.isfinite(x) for x in q1 + q2), 'INVALID_CAMERA_ROTATION')
    na = math.sqrt(sum(x*x for x in q1))
    nb = math.sqrt(sum(x*x for x in q2))
    _check(abs(na-1) < 1e-5 and abs(nb-1) < 1e-5, 'INVALID_CAMERA_ROTATION')
    cos_half = min(1.0, abs(sum(x*y for x, y in zip(q1,q2))))
    return math.degrees(2 * math.acos(cos_half))

def _analyze(req: pb.P2VRobustnessRequest, *, _map_scene_eval=map_scene,
             _reconcile_temporal=reconcile) -> pb.P2VRobustnessResult:
    _check(isinstance(req,pb.P2VRobustnessRequest) and req.schema_version == 1
           and req.research_only and not req.grants_authority and _known(req)
           and req.ByteSize() <= MAX_BYTES, 'INVALID_P2V_CONTRACT')
    _check(math.isfinite(req.max_camera_translation_step_m)
           and 0 < req.max_camera_translation_step_m <= 1000
           and math.isfinite(req.max_camera_rotation_step_deg)
           and 0 < req.max_camera_rotation_step_deg <= 180
           and 1 <= req.max_static_age_ticks <= 10_000_000
           and 1 <= req.max_missing_object_ticks <= 10_000_000
           and 1 <= req.reappearance_gap_ticks <= 10_000_000
           and math.isfinite(req.missing_object_exclusion_radius_m)
           and 0 <= req.missing_object_exclusion_radius_m <= 20,
           'INVALID_P2V_POLICY')
    try:
        base = _map_scene_eval(req.dynamic_request)
    except DynamicSceneRejected as exc:
        raise RobustnessRejected('INVALID_P2U_INPUT:' + str(exc)) from exc

    # Build one canonical per-capture record and fail closed on incompatible
    # camera reference frames. P2U already rejects capture redefinition.
    capture_index = {}
    observation_ticks = defaultdict(dict)  # object_id -> capture_id -> tick
    newest_cell_capture_tick = {}
    for window in req.dynamic_request.windows:
        try:
            temporal = _reconcile_temporal(window.temporal_request)
        except TemporalConsistencyRejected as exc:
            raise RobustnessRejected('TEMPORAL_SOURCE_INVALID:' + str(exc)) from exc
        for cell in temporal.cells:
            coord = (cell.x,cell.y,cell.z)
            for evidence in cell.provenance:
                newest_cell_capture_tick[coord] = max(
                    newest_cell_capture_tick.get(coord, 0), evidence.tick)
        for capture in window.temporal_request.captures:
            d = capture.depth
            key = d.capture_id
            camera = d.camera
            frame = d.pixels[0]
            fingerprint = _sha(capture)
            if key in capture_index:
                _check(capture_index[key][3] == fingerprint, 'CAPTURE_REDEFINED')
            else:
                capture_index[key] = (frame.tick, camera, bytes(d.camera_sha256), fingerprint)
        for tr in window.tracks:
            for sample in tr.samples:
                _check(sample.capture_id in capture_index and
                       sample.tick == capture_index[sample.capture_id][0],
                       'UNBOUND_REAPPEARANCE_OBSERVATION')
                prev = observation_ticks[tr.object_id].get(sample.capture_id)
                _check(prev is None or prev == sample.tick, 'OBJECT_CAPTURE_REDEFINED')
                observation_ticks[tr.object_id][sample.capture_id] = sample.tick
    _check(1 <= len(capture_index) <= MAX_CAPTURES, 'CAMERA_RESOURCE_LIMIT')
    # Reject two genuinely different frames at the same tick; this v1 contract
    # intentionally does not solve multi-camera clock synchronization.
    frames = sorted(((tick, ident, camera, digest) for ident,(tick,camera,digest,_) in
                     capture_index.items()), key=lambda x:(x[0],x[1]))
    _check(len({r[0] for r in frames}) == len(frames), 'MULTICAMERA_CLOCK_UNSUPPORTED')
    result = pb.P2VRobustnessResult(schema_version=1,
        conversation_id=base.conversation_id, volume_id=base.volume_id,
        request_sha256=_sha(req), p2u_result_sha256=_sha(base),
        research_only=True, grants_authority=False)
    pose_disputed = False
    frame_id = frames[0][2].frame_id
    calibration_source = frames[0][2].calibration_source_ref
    previous_camera = None
    for tick, capture_id, camera, digest in frames:
        _check(bool(frame_id) and camera.frame_id == frame_id,
               'CAMERA_FRAME_DISCONTINUITY_REQUIRES_REGISTRATION')
        _check(bool(calibration_source) and camera.calibration_source_ref == calibration_source,
               'CALIBRATION_SOURCE_CHANGED_REQUIRES_REVIEW')
        if previous_camera is None:
            distance,rotation = 0.0,0.0
        else:
            distance = math.dist(_xyz(camera.translation), _xyz(previous_camera.translation))
            rotation = _rotation_step(camera,previous_camera)
        bad = distance > req.max_camera_translation_step_m + 1e-9 or (
            rotation > req.max_camera_rotation_step_deg + 1e-7)
        pose_disputed |= bad
        result.cameras.add(capture_id=capture_id,tick=tick,
            camera_frame_id=frame_id, camera_sha256=digest,
            translation_step_m=distance,rotation_step_deg=rotation,
            state=pb.P2V_CAMERA_DISCONTINUITY if bad else pb.P2V_CAMERA_CONTINUOUS)
        previous_camera = camera
    result.pose_discontinuity_found = pose_disputed
    # A track's last observation is only a caller-asserted identity hint.
    # No identity inference can be made from a missing detection alone.
    evaluation_tick = req.dynamic_request.windows[-1].temporal_request.evaluation_tick
    uncertain_centers = []
    for prior in sorted(base.objects,key=lambda x:x.object_id):
        samples = observation_ticks.get(prior.object_id,{})
        sorted_observations = sorted(((tick,cid) for cid,tick in samples.items()))
        _check(bool(sorted_observations), 'OBJECT_WITH_NO_SUPPORTING_FRAME')
        latest_tick = sorted_observations[-1][0]
        _check(latest_tick <= evaluation_tick, 'OBJECT_OBSERVED_IN_FUTURE')
        worst_gap = max((b[0]-a[0] for a,b in zip(sorted_observations,sorted_observations[1:])),default=0)
        # A long gap causes an UNVERIFIED reappearance, never a confirmed ID.
        if prior.state == upb.P2U_RETIRED or evaluation_tick-latest_tick > 2*req.max_missing_object_ticks:
            state = pb.P2V_RETIRED_UNVERIFIED
        elif evaluation_tick-latest_tick > req.max_missing_object_ticks:
            state = pb.P2V_MISSING_UNEXPLAINED
        elif worst_gap > req.reappearance_gap_ticks:
            state = pb.P2V_REAPPEARANCE_UNVERIFIED
        else:
            state = pb.P2V_OBSERVED_CANDIDATE
        record = result.identities.add(object_id=prior.object_id,state=state,
            last_observed_tick=latest_tick,gap_to_previous_observation_ticks=worst_gap,
            authenticated_identity=False)
        record.distinct_support_capture_ids.extend(cid for _,cid in sorted_observations)
        if state in (pb.P2V_MISSING_UNEXPLAINED,pb.P2V_REAPPEARANCE_UNVERIFIED):
            # Suppress nearby voxels using the last supplied world position.
            for window in reversed(req.dynamic_request.windows):
                for track in window.tracks:
                    if track.object_id == prior.object_id:
                        sample = max(track.samples,key=lambda x:x.tick)
                        if sample.tick == latest_tick:
                            uncertain_centers.append(_xyz(sample.center_world_m))
                            break
                else:
                    continue
                break
    # P2U candidates form the maximum set. P2V can only REMOVE evidence.
    candidates = {(e.x,e.y,e.z):e for e in base.stationary_hypothetical_volume.evidence}
    _check(len(candidates)==len(base.stationary_hypothetical_volume.evidence),'DUPLICATE_STATIC_EVIDENCE')
    stationary = vpb.VolumeGrid()
    stationary.CopyFrom(base.stationary_hypothetical_volume)
    accepted = set()
    voxel_size = req.dynamic_request.windows[-1].temporal_request.captures[0].depth.voxel_size_m
    for cell in base.cells:
        xyz = (cell.x,cell.y,cell.z)
        latest = newest_cell_capture_tick.get(xyz, 0)
        _check(latest <= evaluation_tick, 'FUTURE_CELL_PROVENANCE')
        age = evaluation_tick-latest
        center = tuple((x+.5)*voxel_size for x in xyz)
        nearby = any(math.dist(center,loc) <= req.missing_object_exclusion_radius_m
                     for loc in uncertain_centers)
        if not cell.static_handoff_allowed or xyz not in candidates:
            state = pb.P2V_STATIC_NOT_ELIGIBLE
        elif pose_disputed:
            state = pb.P2V_STATIC_POSE_DISPUTED
        elif latest == 0 or age > req.max_static_age_ticks:
            state = pb.P2V_STATIC_STALE
        elif nearby:
            state = pb.P2V_STATIC_OBJECT_UNCERTAIN
        else:
            state = pb.P2V_STATIC_RETAINED_PREDICTION
            accepted.add(xyz)
        result.cells.add(x=xyz[0],y=xyz[1],z=xyz[2],state=state,
                         latest_support_tick=latest,age_ticks=age,
                         retained=xyz in accepted)
    retained = [e for e in stationary.evidence if (e.x,e.y,e.z) in accepted]
    stationary.ClearField('evidence')
    stationary.evidence.extend(retained)
    try:
        audited = classify(stationary)
    except VolumeRejected as exc:
        raise RobustnessRejected('INVALID_CONSERVATIVE_STATIC_VOLUME:' + str(exc)) from exc
    _check(all(e.kind in (vpb.VOLUME_PREDICTED_FREE,vpb.VOLUME_PREDICTED_OCCUPIED)
               for e in stationary.evidence) and
           all(c.state == vpb.CELL_UNKNOWN for c in audited.cells) and
           stationary.research_only and not stationary.grants_authority,
           'UNAUTHORIZED_STATIC_EVIDENCE')
    result.conservative_static_hypothetical_volume.CopyFrom(stationary)
    result.warnings.extend([
        'POSE_CONTINUITY_IS_NOT_CAMERA_MOTION_ESTIMATION_OR_SENSOR_ATTESTATION',
        'P2Q_ALREADY_APPLIES_CALLER_SUPPLIED_CAMERA_TO_WORLD_TRANSFORM',
        'MISSING_OBJECT_MAY_BE_OCCLUDED_OUT_OF_VIEW_OR_UNDETECTED',
        'REAPPEARANCE_PRESERVES_CALLER_ID_ONLY_AND_IS_NOT_REIDENTIFICATION',
        'STATIC_VOXELS_ARE_PREDICTIONS_NOT_SAFE_SPACE_OR_PHYSICAL_TRUTH',
        'NO_SCENE_VOLUME_OR_LU_STATE_MUTATION'])
    return result

def verify(req: pb.P2VRobustnessRequest, result: pb.P2VRobustnessResult) -> bool:
    _check(isinstance(result,pb.P2VRobustnessResult) and _known(result) and
           result.SerializeToString(deterministic=True) ==
           analyze(req).SerializeToString(deterministic=True),
           'P2V_REPLAY_MISMATCH')
    return True


def analyze(req: pb.P2VRobustnessRequest) -> pb.P2VRobustnessResult:
    """Original independent, full-replay public evaluator."""
    return _analyze(req)
