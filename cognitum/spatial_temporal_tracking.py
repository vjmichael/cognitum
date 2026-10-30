"""C15/T1 P2C: finite-horizon temporal association proposals (research only).

Constant-velocity extrapolation and untrained descriptor similarity; bounded top-K
one-to-one assignment. No trusted sensors, learned tracking, calibrated posterior,
scene writes, or action authorization. Caller supplied history is untrusted.
"""
from __future__ import annotations
import math
from cognitum.proto import spatial_scene_pb2 as sp, spatial_temporal_pb2 as pb
from cognitum import spatial_identity_association as prior, spatial_scene_reference as geo

class TemporalRejected(ValueError):
    pass

def require(ok, reason):
    if not ok: raise TemporalRejected(reason)

def _vec(v):
    require(v is not None and all(math.isfinite(x) and abs(x) <= 1e9 for x in (v.x,v.y,v.z)), 'INVALID_POSITION')
    return (v.x,v.y,v.z)

def _descriptor(xs):
    require(len(xs) in (0, 2, 3, 4, 5, 6, 7, 8), 'INVALID_DESCRIPTOR_DIMENSION')
    require(all(math.isfinite(v) and abs(v) <= 1e6 for v in xs), 'INVALID_DESCRIPTOR')
    if not xs: return None
    norm=math.sqrt(sum(v*v for v in xs))
    require(norm > 1e-10, 'ZERO_DESCRIPTOR')
    return tuple(v/norm for v in xs)

def _valid_scale(value, lo, hi, reason):
    require(math.isfinite(value) and lo <= value <= hi, reason)

def propose(snapshot:sp.SceneSnapshot, request:pb.TemporalRequest)->pb.TemporalProposal:
    require(isinstance(snapshot,sp.SceneSnapshot) and snapshot.research_only and snapshot.schema_version==1, 'INVALID_SNAPSHOT')
    require(isinstance(request,pb.TemporalRequest) and request.schema_version==1, 'INVALID_SCHEMA')
    require(request.scene_id==snapshot.scene_id and request.conversation_id==snapshot.conversation_id, 'SCOPE_MISMATCH')
    require(all(geo._good_id(x) for x in (request.scene_id,request.conversation_id,request.task_id,request.trace_id,request.request_id)), 'INVALID_SCOPE')
    require(request.request_id not in snapshot.processed_request_ids, 'REPLAYED_SCENE_REQUEST')
    require(request.scene_sha256==prior.digest(snapshot), 'SNAPSHOT_HASH_MISMATCH')
    require(1<=len(request.detections)<=6 and len(request.tracks)<=6, 'INPUT_LIMIT')
    require(len(request.SerializeToString())<=32768, 'INPUT_BYTES_LIMIT')
    require(1<=request.top_k<=8 and 1<=request.max_gap_ticks<=100, 'INVALID_HORIZON_OR_TOPK')
    _valid_scale(request.observation_sigma_m,0.001,1e5,'INVALID_OBSERVATION_SIGMA')
    _valid_scale(request.process_sigma_m_per_tick,0,1e5,'INVALID_PROCESS_SIGMA')
    _valid_scale(request.max_speed_m_per_tick,0.001,1e5,'INVALID_SPEED')
    _valid_scale(request.descriptor_weight,0,100,'INVALID_DESCRIPTOR_WEIGHT')
    _valid_scale(request.unmatched_cost,0.01,1e6,'INVALID_UNMATCHED_COST')
    _valid_scale(request.ambiguity_margin,0,1e3,'INVALID_AMBIGUITY_MARGIN')
    objects={o.object_id:o for o in snapshot.objects if o.visibility!=sp.VISIBILITY_DELETED}
    require(len(objects)==len([o for o in snapshot.objects if o.visibility!=sp.VISIBILITY_DELETED]), 'DUPLICATE_SCENE_IDS')
    tids=[t.object_id for t in request.tracks]
    dids=[d.detection_id for d in request.detections]
    require(len(tids)==len(set(tids)) and len(dids)==len(set(dids)), 'DUPLICATE_IDS')
    require(all(x in objects for x in tids), 'UNKNOWN_TRACK')
    detections=sorted(request.detections,key=lambda x:x.detection_id)
    tracks=sorted(request.tracks,key=lambda x:x.object_id)
    ticks={d.tick for d in detections}
    require(len(ticks)==1 and next(iter(ticks))>0, 'MIXED_OR_INVALID_TICKS')
    current_tick=next(iter(ticks))
    for d in detections:
        require(geo._good_id(d.detection_id) and geo._good_id(d.source_id) and geo._text(d.category) and d.HasField('position_world_m'), 'INVALID_DETECTION')
        _vec(d.position_world_m);_descriptor(d.descriptor)
    frames={f.frame_id:f for f in snapshot.frames}
    states=[]
    for track in tracks:
        obj=objects[track.object_id]
        require(1<=len(track.samples)<=8 and obj.last_observed_tick>0, 'INVALID_TRACK_HISTORY')
        samples=list(track.samples)
        require(all(s.tick>0 and s.HasField('position_world_m') for s in samples), 'INVALID_HISTORY_SAMPLES')
        require(all(samples[i].tick < samples[i+1].tick for i in range(len(samples)-1)), 'NONMONOTONIC_HISTORY')
        for sample in samples:
            _vec(sample.position_world_m);_descriptor(sample.descriptor)
        latest=samples[-1]
        require(latest.tick==obj.last_observed_tick, 'HISTORY_LAST_TICK_MISMATCH')
        try:
            pos=geo._world_position(obj.frame_id,geo._vector(obj.position_m),frames)
        except (geo.SceneRejected,ValueError) as exc:
            raise TemporalRejected('SCENE_FRAME_INVALID') from exc
        require(math.dist(pos,_vec(latest.position_world_m))<=1e-7,'HISTORY_LAST_POSE_MISMATCH')
        dt=current_tick-latest.tick
        require(dt>0, 'STALE_OBSERVATION_TICK')
        velocity=(0.0,0.0,0.0)
        if len(samples)>1:
            before=samples[-2];step=latest.tick-before.tick
            velocity=tuple((a-b)/step for a,b in zip(_vec(latest.position_world_m),_vec(before.position_world_m)))
            require(math.dist((0,0,0),velocity)<=request.max_speed_m_per_tick+1e-8, 'HISTORY_SPEED_EXCEEDED')
        states.append((obj,latest,dt,velocity))
    rows=[];saw_compatible=False; missing_descriptors=False;long_gap=False
    for det in detections:
        row=[]
        for obj,latest,dt,velocity in states:
            if det.category!=obj.category or det.source_id!=obj.observation_source_id or dt>request.max_gap_ticks:
                row.append(None);continue
            last=_vec(latest.position_world_m)
            measured=_vec(det.position_world_m)
            dist_original=math.dist(last,measured)
            # Separate a physical max-speed gate from a Gaussian kinematic cost.
            if dist_original>request.max_speed_m_per_tick*dt+3*request.observation_sigma_m:
                row.append(None);continue
            predicted=tuple(last[k]+velocity[k]*dt for k in range(3))
            std=math.hypot(request.observation_sigma_m,request.process_sigma_m_per_tick*dt)
            residual=math.dist(measured,predicted)
            if residual>max(request.max_speed_m_per_tick*dt,3*std):
                row.append(None);continue
            dcost=.5*(residual/std)**2
            da=_descriptor(det.descriptor);ta=_descriptor(latest.descriptor)
            featurecost=0.0
            if da is not None and ta is not None:
                require(len(da)==len(ta), 'INCOMPATIBLE_DESCRIPTOR_DIMENSIONS')
                featurecost=request.descriptor_weight*max(0.0,min(1.0,(1-sum(x*y for x,y in zip(da,ta)))/2.0))
            else: missing_descriptors=True
            if dt>1:long_gap=True
            row.append((dcost,featurecost,std))
            saw_compatible=True
        rows.append(row)
    alternatives=[]
    def recur(i,used,pairs,total):
        if i==len(detections):
            alternatives.append((total,tuple(pairs)));return
        pairs.append((-1,request.unmatched_cost,0,0))
        recur(i+1,used,pairs,total+request.unmatched_cost);pairs.pop()
        for j,edge in enumerate(rows[i]):
            if edge is None or j in used: continue
            motion,appearance,std=edge
            pairs.append((j,motion,appearance,std));recur(i+1,used|{j},pairs,total+motion+appearance);pairs.pop()
    recur(0,set(),[],0.0)
    alternatives.sort(key=lambda x:(round(x[0],12),tuple(y[0] for y in x[1])))
    best=alternatives[:request.top_k]
    weights=[math.exp(-min(745,x[0]-best[0][0])) for x in best]
    normalizer=sum(weights)
    output=pb.TemporalProposal(schema_version=1,scene_id=request.scene_id,conversation_id=request.conversation_id,
        task_id=request.task_id,trace_id=request.trace_id,request_id=request.request_id,
        scene_sha256=prior.digest(snapshot),request_sha256=prior.digest(request),research_only=True,grants_authority=False)
    for (cost,assign),weight in zip(best,weights):
        h=output.hypotheses.add(total_cost=cost,relative_weight=weight/normalizer)
        for det,(j,mc,ac,std) in zip(detections,assign):
            h.pairs.add(detection_id=det.detection_id,object_id=tracks[j].object_id if j>=0 else '',
                        motion_cost=mc,descriptor_cost=ac,predicted_sigma_m=std)
    matched=[(det,tracks[assigned[0]]) for det,assigned in zip(detections,best[0][1]) if assigned[0]>=0]
    has_competitor=any(sum(edge is not None for edge in row)>1 for row in rows)
    near_tie=(len(alternatives)>1 and alternatives[1][0]-alternatives[0][0]<=request.ambiguity_margin)
    # Identical caller-provided descriptors cannot disambiguate two same-class
    # tracks; a low geometric cost alone must not elevate the proposal.
    descriptor_nonunique=False
    for i,(obj1,sample1,_,_) in enumerate(states):
        for obj2,sample2,_,_ in states[i+1:]:
            if obj1.category!=obj2.category or obj1.observation_source_id!=obj2.observation_source_id: continue
            a,b=_descriptor(sample1.descriptor),_descriptor(sample2.descriptor)
            if a is None or b is None or (len(a)==len(b) and sum(x*y for x,y in zip(a,b))>0.99):
                descriptor_nonunique=True
    unresolved=has_competitor and (missing_descriptors or long_gap or descriptor_nonunique)
    if not matched:
        output.decision=pb.TEMPORAL_NO_MATCH
    elif near_tie or unresolved:
        output.decision=pb.TEMPORAL_AMBIGUOUS
        if near_tie:output.warnings.append('NEAR_TIED_HYPOTHESES')
        if unresolved:output.warnings.append('INSUFFICIENT_INDEPENDENT_IDENTITY_EVIDENCE')
    else:output.decision=pb.TEMPORAL_CANDIDATE_ONLY
    output.warnings.extend(['CALLER_SUPPLIED_HISTORY_AND_DESCRIPTOR_UNAUTHENTICATED',
       'RELATIVE_TOP_K_WEIGHTS_NOT_CALIBRATED_POSTERIORS',
       'PREDICTION_SIGMA_IS_HEURISTIC_NOT_VALIDATED_COVERAGE',
       'NO_CANONICAL_ID_MUTATION_OR_ACTION_AUTHORITY'])
    return output

def verify_proposal(snapshot,request,proposal):
    if not isinstance(proposal,pb.TemporalProposal):return False
    try:
        return propose(snapshot,request).SerializeToString(deterministic=True)==proposal.SerializeToString(deterministic=True)
    except (TemporalRejected,ValueError,TypeError):return False
