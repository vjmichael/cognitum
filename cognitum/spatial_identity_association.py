"""C15/T1 P2B: bounded, pure, research-only object association proposals.

A deliberately conservative multiple-hypothesis baseline, NOT an appearance
tracker, posterior-calibrated JPDA, trusted sensor, or automatic ID writer.
All assignments are proposed; nothing modifies canonical scene IDs.
"""
from __future__ import annotations
import hashlib
import math

from cognitum.proto import spatial_scene_pb2 as scene
from cognitum.proto import spatial_identity_pb2 as p
from cognitum import spatial_scene_reference as geometry

MAX_OBSERVATIONS = 6
MAX_TRACKS = 6


class AssociationRejected(ValueError):
    pass


def check(ok: bool, code: str):
    if not ok:
        raise AssociationRejected(code)


def digest(message):
    return hashlib.sha256(message.SerializeToString(deterministic=True)).digest()


def _finite_between(number, low, high):
    return math.isfinite(number) and low <= number <= high


def _validate(snapshot, request):
    check(isinstance(snapshot, scene.SceneSnapshot) and snapshot.schema_version == 1
          and snapshot.research_only, 'INVALID_SNAPSHOT')
    check(isinstance(request, p.AssociationRequest) and request.schema_version == 1,
          'INVALID_ASSOCIATION_SCHEMA')
    check(snapshot.scene_id == request.scene_id and
          snapshot.conversation_id == request.conversation_id, 'SCENE_OR_CONVERSATION_SCOPE_MISMATCH')
    check(all(geometry._good_id(v) for v in (request.scene_id, request.conversation_id,
          request.task_id, request.trace_id, request.request_id)), 'INVALID_REQUEST_SCOPE')
    check(request.request_id not in snapshot.processed_request_ids, 'REPLAYED_SCENE_REQUEST')
    check(len(request.scene_sha256) == 32 and request.scene_sha256 == digest(snapshot),
          'SCENE_HASH_MISMATCH')
    check(0 < len(request.observations) <= MAX_OBSERVATIONS, 'OBSERVATION_LIMIT')
    check(_finite_between(request.measurement_sigma_m, 0.001, 1_000_000), 'INVALID_MEASUREMENT_SCALE')
    check(_finite_between(request.max_speed_m_per_tick, 0.0001, 1_000_000), 'INVALID_SPEED_BOUND')
    check(_finite_between(request.unmatched_cost, 0.01, 100_000), 'INVALID_UNMATCHED_COST')
    check(_finite_between(request.ambiguity_cost_margin, 0.0, 1000), 'INVALID_AMBIGUITY_MARGIN')
    check(1 <= request.top_k <= 8, 'INVALID_TOP_K')
    check(len(request.SerializeToString()) <= 32_768, 'OVERSIZE_ASSOCIATION_REQUEST')
    frame_ids = {f.frame_id for f in snapshot.frames}
    check(len(frame_ids) == len(snapshot.frames), 'DUPLICATE_FRAMES')
    ids = [o.observation_id for o in request.observations]
    check(len(ids) == len(set(ids)), 'DUPLICATE_OBSERVATION_IDS')
    tracks = [o for o in snapshot.objects if o.visibility != scene.VISIBILITY_DELETED]
    check(len(tracks) <= MAX_TRACKS, 'TRACK_LIMIT')
    check(len({o.object_id for o in snapshot.objects}) == len(snapshot.objects), 'DUPLICATE_TRACK_IDS')
    for o in request.observations:
        check(all(geometry._good_id(v) for v in (o.observation_id,o.source_id))
              and geometry._text(o.category) and o.observed_tick > 0, 'INVALID_OBSERVATION')
        check(o.HasField('position_m') and
              (o.frame_id == 'world' or o.frame_id in frame_ids), 'INVALID_OBSERVATION_FRAME')
        geometry._vector(o.position_m)
        compatible_ticks = [t.last_observed_tick for t in tracks
                            if t.category == o.category and t.observation_source_id == o.source_id]
        if compatible_ticks:
            check(o.observed_tick > max(compatible_ticks), 'STALE_OBSERVATION_TICK')
    return tracks


def propose(snapshot: scene.SceneSnapshot, request: p.AssociationRequest) -> p.AssociationHypothesisSet:
    """Enumerate bounded one-to-one assignments under isotropic position noise.

    Ranks alternative proposals via additive -log Gaussian kernel costs. No
    ground-truth identity is ever available from position-only observations.
    """
    try:
        tracks = _validate(snapshot, request)
    except geometry.SceneRejected as exc:
        raise AssociationRejected(str(exc)) from exc
    tracks = sorted(tracks,key=lambda o:o.object_id)
    observations = sorted(request.observations,key=lambda o:o.observation_id)
    frames = {f.frame_id:f for f in snapshot.frames}
    costs = []
    any_edge = False
    for o in observations:
        try:
            current = geometry._world_position(o.frame_id, geometry._vector(o.position_m), frames)
        except geometry.SceneRejected as exc:
            raise AssociationRejected(str(exc)) from exc
        row=[]
        for t in tracks:
            if t.category != o.category or t.observation_source_id != o.source_id:
                row.append(None); continue
            dt = o.observed_tick - t.last_observed_tick
            if dt <= 0:
                row.append(None); continue
            try:
                prior = geometry._world_position(t.frame_id, geometry._vector(t.position_m), frames)
            except geometry.SceneRejected as exc:
                raise AssociationRejected(str(exc)) from exc
            dist=math.dist(current, prior)
            if not math.isfinite(dist) or dist > request.max_speed_m_per_tick * dt + 3 * request.measurement_sigma_m:
                row.append(None); continue
            norm=0.5*(dist/request.measurement_sigma_m)**2
            row.append((dist,norm));any_edge=True
        costs.append(row)

    # Exhaustive bounded assignment is intentional: keep unmatched hypotheses,
    # retain near-ties and avoid SciPy as a runtime dependency. Not scalable.
    alternatives=[]
    def enumerate_assignments(i, used, current, total):
        if i == len(observations):
            alternatives.append((total,tuple(current)))
            return
        current.append((-1,0.0,request.unmatched_cost))
        enumerate_assignments(i+1,used,current,total+request.unmatched_cost)
        current.pop()
        for j, edge in enumerate(costs[i]):
            if edge is None or j in used: continue
            current.append((j,edge[0],edge[1]))
            enumerate_assignments(i+1, used | {j}, current,total+edge[1])
            current.pop()
    enumerate_assignments(0,set(),[],0.0)
    alternatives.sort(key=lambda item:(round(item[0],12),tuple(x[0] for x in item[1])))
    best = alternatives[:request.top_k]
    weights=[math.exp(-min(745.0,x[0]-best[0][0])) for x in best]
    weight_total=sum(weights)
    output=p.AssociationHypothesisSet(
        schema_version=1,scene_id=request.scene_id,conversation_id=request.conversation_id,
        task_id=request.task_id,trace_id=request.trace_id,request_id=request.request_id,
        scene_sha256=digest(snapshot),request_sha256=digest(request),research_only=True,
        grants_authority=False)
    for (total,items),weight in zip(best,weights):
        h=output.hypotheses.add(total_cost=total,relative_weight=weight/weight_total)
        for o,(j,distance,cost) in zip(observations,items):
            h.pairs.add(observation_id=o.observation_id,
                        object_id=tracks[j].object_id if j>=0 else '',
                        distance_m=distance,normalized_cost=cost)

    ambiguous_near_tie=(len(alternatives)>1 and alternatives[1][0]-alternatives[0][0]
                        <= request.ambiguity_cost_margin)
    matched=[(o,tracks[x[0]]) for o,x in zip(observations,best[0][1]) if x[0]>=0]
    # Any two visually indistinguishable same-category tracks remain uncertain,
    # irrespective of the numerical best assignment. No appearance evidence exists.
    indistinguishable = any(
        a.category == b.category and a.source_id == b.source_id
        for i,(a,_) in enumerate(matched) for b,_ in matched[i+1:])
    if not any_edge or all(x[0]<0 for x in best[0][1]):
        output.decision=p.ASSOCIATION_NO_COMPATIBLE_MATCH
        output.warnings.append('NO_GATED_MATCH;UNMATCHED_OBSERVATIONS_ARE_NOT_NEW_ID_AUTHORIZATION')
    elif ambiguous_near_tie or indistinguishable:
        output.decision=p.ASSOCIATION_AMBIGUOUS
        if ambiguous_near_tie: output.warnings.append('NEAR_TIED_GLOBAL_ASSIGNMENT')
        if indistinguishable: output.warnings.append('SAME_CLASS_GEOMETRY_CANNOT_PROVE_IDENTITY')
    else:
        output.decision=p.ASSOCIATION_CANDIDATE_ONLY
    output.warnings.extend([
        'POSITION_ONLY_NO_APPEARANCE_OR_CONTINUOUS_TRAJECTORY',
        'TOP_K_WEIGHTS_ARE_NOT_CALIBRATED_POSTERIORS',
        'NO_CANONICAL_ID_MUTATION_OR_ACTION_AUTHORITY'])
    return output


def verify_proposal(snapshot,request,proposal):
    """Arithmetic replay, NOT independent provenance or host authorization."""
    if not isinstance(proposal,p.AssociationHypothesisSet): return False
    try:
        expected=propose(snapshot,request)
        return expected.SerializeToString(deterministic=True)==proposal.SerializeToString(deterministic=True)
    except (AssociationRejected,ValueError,TypeError):
        return False
