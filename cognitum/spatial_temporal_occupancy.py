"""C15 T3 P2C: time-discounted rays and frame registration, heldout diagnostics.

Does not authenticate readings, calibrate a sensor, infer actual physical safety,
or claim that a changing environment satisfies static occupancy assumptions.
"""
from __future__ import annotations
from collections import defaultdict
import math
from cognitum.proto import temporal_occupancy_pb2 as pb
from cognitum.spatial_ray_occupancy import _dda

class TemporalOccupancyRejected(ValueError):
    pass

def _require(ok,why):
    if not ok:raise TemporalOccupancyRejected(why)

def _ident(s):
    return isinstance(s,str) and 0<len(s)<=128 and all(ch.isascii() and (ch.isalnum() or ch in '_-.:') for ch in s)

def _known(message):
    c=type(message)();c.CopyFrom(message);c.DiscardUnknownFields();return c==message

def _point(p):return (p.x,p.y,p.z)

def _rotate(q,v):
    # q=(w,x,y,z); R(v) = v + 2*w*(u x v) + 2*u x (u x v)
    w,x,y,z=q
    u=(x,y,z)
    t=(2*(y*v[2]-z*v[1]),2*(z*v[0]-x*v[2]),2*(x*v[1]-y*v[0]))
    c=(y*t[2]-z*t[1],z*t[0]-x*t[2],x*t[1]-y*t[0])
    return tuple(v[i]+w*t[i]+c[i] for i in range(3))

def integrate(req:pb.TemporalOccupancyRequest)->pb.TemporalOccupancyResult:
    _require(isinstance(req,pb.TemporalOccupancyRequest) and req.schema_version==1 and req.research_only and not req.grants_authority,'INVALID_CONTRACT')
    _require(_known(req),'UNKNOWN_PROTO_FIELDS')
    _require(_ident(req.conversation_id) and _ident(req.volume_id) and math.isfinite(req.voxel_size_m) and 0.001<=req.voxel_size_m<=1000 and 1<=req.max_axis<=128 and req.evaluation_tick>0 and math.isfinite(req.half_life_ticks) and 0<req.half_life_ticks<=1e9,'INVALID_GRID')
    _require(1<=len(req.rays)<=256 and 1<=len(req.frames)<=32 and len(req.holdout_labels)<=4096 and len(req.calibration_labels)<=4096 and len(req.SerializeToString())<=160000,'RESOURCE_LIMIT')
    frames={}
    for f in req.frames:
        q=(f.qw,f.qx,f.qy,f.qz);translation=_point(f.translation)
        _require(_ident(f.frame_id) and f.frame_id not in frames and f.HasField('translation') and all(map(math.isfinite,q+translation)) and abs(sum(z*z for z in q)-1)<1e-5,'INVALID_OR_NONUNIT_FRAME')
        frames[f.frame_id]=(q,translation)
    grouped=defaultdict(list);events=set();maxcoord=req.voxel_size_m*req.max_axis
    for ray in req.rays:
        _require(_ident(ray.source_ref) and ray.tick>0 and ray.tick<=req.evaluation_tick and ray.frame_id in frames and ray.HasField('start') and ray.HasField('end'),'INVALID_RAY_PROVENANCE')
        _require(math.isfinite(ray.hit_probability) and math.isfinite(ray.free_probability) and 0.5<ray.hit_probability<0.999 and 0.001<ray.free_probability<0.5,'INVALID_SENSOR_MODEL')
        q,t=frames[ray.frame_id]
        start=tuple(a+b for a,b in zip(_rotate(q,_point(ray.start)),t))
        end=tuple(a+b for a,b in zip(_rotate(q,_point(ray.end)),t))
        _require(all(math.isfinite(z) and 0<=z<maxcoord for z in start+end) and math.dist(start,end)>1e-12,'INVALID_REGISTERED_RAY')
        try:cells=_dda(start,end,req.voxel_size_m,req.max_axis,
                       include_endpoint_cell=ray.endpoint_hit)
        except (ValueError,OverflowError) as exc:raise TemporalOccupancyRejected('INVALID_RAY_TRAVERSAL') from exc
        weight=2**(-(req.evaluation_tick-ray.tick)/req.half_life_ticks)
        for i,cell in enumerate(cells):
            key=(ray.source_ref,ray.tick,cell)
            outcome=bool(ray.endpoint_hit and i==len(cells)-1)
            _require(key not in events,'DUPLICATE_SOURCE_TICK_VOXEL')
            events.add(key)
            p=ray.hit_probability if outcome else ray.free_probability
            grouped[cell].append((outcome,math.log(p/(1-p))*weight))
    _require(len(grouped)<=16384,'SPARSE_RESOURCE_LIMIT')
    result=pb.TemporalOccupancyResult(conversation_id=req.conversation_id,volume_id=req.volume_id,research_only=True,grants_authority=False)
    lookup={}
    def read_labels(items,kind):
        values={}
        for label in items:
            key=(label.x,label.y,label.z)
            _require(_ident(label.source_ref) and all(0<=v<req.max_axis for v in key) and key not in values,'INVALID_OR_DUPLICATE_'+kind)
            values[key]=int(label.occupied)
        return values
    train=read_labels(req.calibration_labels,'TRAINING_LABEL')
    labels=read_labels(req.holdout_labels,'HOLDOUT_LABEL')
    _require(not(set(train)&set(labels)),'TRAIN_HOLDOUT_OVERLAP')
    raw={coord:max(-8.,min(8.,sum(w for _,w in updates))) for coord,updates in grouped.items()}
    _require(all(key in raw for key in set(train)|set(labels)),'LABEL_AT_UNOBSERVED_CELL')
    # A bounded, auditable scalar temperature fit on *separate*, caller-declared
    # training labels. Minimizes Bernoulli NLL, not a production-calibration claim.
    candidates=(0.5,0.75,1.0,1.5,2.0,3.0,4.0)
    def _temp_prob(logodds,temperature):return 1/(1+math.exp(-logodds/temperature))
    def train_loss(temp):
        return sum(-math.log(max(1e-12,min(1-1e-12, _temp_prob(raw[key],temp) if y else 1-_temp_prob(raw[key],temp)))) for key,y in train.items())/len(train)
    temperature=min(candidates,key=lambda t:(train_loss(t),abs(t-1))) if train else 1.0
    result.holdout.training_count=len(train)
    result.holdout.selected_temperature=temperature
    for coord,updates in sorted(grouped.items()):
        hit=sum(v[0] for v in updates);free=len(updates)-hit
        logodds=max(-8.,min(8.,sum(w for _,w in updates)))
        probability=1/(1+math.exp(-logodds))
        result.cells.add(x=coord[0],y=coord[1],z=coord[2],log_odds=logodds,probability=probability,hit_count=hit,free_count=free,conflicted=bool(hit and free),calibrated_probability=probability if not train else 1/(1+math.exp(-logodds/temperature)))
        lookup[coord]=probability
    # Evaluation labels are heldout only if supplied independently by the caller.

    if labels:
        pairs=[(lookup[c],target) for c,target in sorted(labels.items())]
        bs=sum((p-y)**2 for p,y in pairs)/len(pairs)
        # Five equal-width bins, including p==1.0 in final bin.
        bins=5;parts=[[] for _ in range(bins)]
        for prob,target in pairs:parts[min(int(prob*bins),bins-1)].append((prob,target))
        ece=sum(len(part)/len(pairs)*abs(sum(p for p,y in part)/len(part)-sum(y for p,y in part)/len(part)) for part in parts if part)
        result.holdout.evaluated_count=len(labels);result.holdout.brier_score=bs
        result.holdout.expected_calibration_error=ece;result.holdout.bins=bins
        result.holdout.assessment='SEPARATE_HOLDOUT_DIAGNOSTIC_NOT_AUTHENTICATED'
        calibrated=[(_temp_prob(raw[c],temperature),target) for c,target in sorted(labels.items())]
        result.holdout.calibrated_brier=sum((p-y)**2 for p,y in calibrated)/len(calibrated)
        cbins=[[] for _ in range(bins)]
        for p,target in calibrated:cbins[min(int(p*bins),bins-1)].append((p,target))
        result.holdout.calibrated_expected_calibration_error=sum(len(part)/len(calibrated)*abs(sum(p for p,y in part)/len(part)-sum(y for p,y in part)/len(part)) for part in cbins if part)
    else:result.holdout.assessment='NO_HOLDOUT_LABELS'
    result.warnings.extend(['CALLER_POSES_AND_SENSOR_PROBABILITIES_NOT_AUTHENTICATED','TEMPORAL_DECAY_HEURISTIC_NOT_VALIDATED','RAY_CORRELATION_IGNORED','TRAINING_AND_HOLDOUT_LABELS_CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED','TEMPERATURE_FIT_DOES_NOT_ESTABLISH_REAL_WORLD_CALIBRATION','NO_SAFETY_OR_ACTION_AUTHORITY'])
    if any(c.conflicted for c in result.cells):result.warnings.append('CONTRADICTORY_TIME_SERIES_RETAINED')
    return result
