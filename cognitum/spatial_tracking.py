"""C15 bounded multi-object box association via SciPy Hungarian assignment.

This component accepts *detections*, not raw image/video capture. No claim of
real-world sensor authentication, re-identification after arbitrary occlusion,
or TrackEval-quality MOT accuracy. Explicitly preserve unmatched/occluded IDs.
"""
from dataclasses import dataclass
from math import hypot,isfinite

MAX_TRACKS=64
MAX_DETECTIONS=64
MAX_AGE=8


@dataclass(frozen=True)
class Detection:
    detection_id:str
    x:float
    y:float
    width:float
    height:float
    source:str


@dataclass(frozen=True)
class Track:
    stable_id:str
    x:float
    y:float
    width:float
    height:float
    missed:int=0
    last_source:str="unknown"


@dataclass(frozen=True)
class TrackUpdate:
    tracks:tuple[Track,...]
    assignments:tuple[tuple[str,str],...]
    unmatched_detections:tuple[str,...]
    retired_ids:tuple[str,...]
    status:str="ASSOCIATED"
    limitations:tuple[str,...]=(
        "caller_supplied_detections_not_authenticated",
        "no_appearance_embedding_or_reidentification",
        "occlusion_keeps_identity_as_unobserved_hypothesis",
    )


def _ident(s):
    return type(s) is str and s.isascii() and s.isidentifier() and 1<=len(s)<=48


def _box(obj):
    return (all(type(getattr(obj,f)) in (int,float)
                and isfinite(getattr(obj,f))
                and abs(getattr(obj,f))<=1_000_000
                for f in ("x","y","width","height"))
            and 0<obj.width<=100000 and 0<obj.height<=100000)


def validate(tracks, detections):
    if (type(tracks) is not tuple or type(detections) is not tuple
            or len(tracks)>MAX_TRACKS or len(detections)>MAX_DETECTIONS):
        raise ValueError("tracking size bounds")
    ids=set()
    for tr in tracks:
        if (type(tr) is not Track or not _ident(tr.stable_id)
                or tr.stable_id in ids or not _ident(tr.last_source)
                or type(tr.missed) is not int or not 0<=tr.missed<=MAX_AGE
                or not _box(tr)):
            raise ValueError("invalid typed track")
        ids.add(tr.stable_id)
    ids=set()
    for det in detections:
        if (type(det) is not Detection or not _ident(det.detection_id)
                or det.detection_id in ids or not _ident(det.source)
                or not _box(det)):
            raise ValueError("invalid typed detection")
        ids.add(det.detection_id)


def overlap(a,b):
    """Independent exact rectangle intersection-over-union reference."""
    x=max(0,min(a.x+a.width,b.x+b.width)-max(a.x,b.x))
    y=max(0,min(a.y+a.height,b.y+b.height)-max(a.y,b.y))
    inter=x*y
    union=a.width*a.height+b.width*b.height-inter
    return inter/union if union>0 else 0.0


def update(tracks:tuple[Track,...],detections:tuple[Detection,...], *,
           min_iou:float=0.05, max_distance:float=30,
           max_missed:int=3)->TrackUpdate:
    validate(tracks,detections)
    if (type(min_iou) not in (int,float) or not isfinite(min_iou)
            or not 0<=min_iou<=1 or type(max_distance) not in (int,float)
            or not isfinite(max_distance) or max_distance<=0 or max_distance>10000
            or type(max_missed) is not int or not 0<=max_missed<=MAX_AGE):
        raise ValueError("invalid association gate")
    if not tracks or not detections:
        keep=tuple(Track(t.stable_id,t.x,t.y,t.width,t.height,t.missed+1,t.last_source)
                   for t in tracks if t.missed<max_missed)
        retired=tuple(t.stable_id for t in tracks if t.missed>=max_missed)
        return TrackUpdate(keep,(),tuple(d.detection_id for d in detections),retired)
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        return TrackUpdate(tracks,(),tuple(d.detection_id for d in detections),
                           (),status="UNSUPPORTED")
    # Add dummy columns for every prior track, ensuring no bad forced match.
    n,m=len(tracks),len(detections)
    penalty=1.001
    costs=np.full((n,m+n),penalty,dtype=np.float64)
    for i,t in enumerate(tracks):
        for j,d in enumerate(detections):
            dist=hypot((t.x+t.width/2)-(d.x+d.width/2),
                       (t.y+t.height/2)-(d.y+d.height/2))
            iou=overlap(t,d)
            if iou>=min_iou and dist<=max_distance:
                costs[i,j]=1-iou+1e-6*dist/max_distance
        costs[i,m+i]=1.0
    rows,cols=linear_sum_assignment(costs)
    accepted={}
    used=set()
    for i,j in zip(rows,cols):
        if j<m and costs[i,j]<1.0:
            accepted[i]=j
            used.add(j)
    out=[]
    retired=[]
    links=[]
    for i,t in enumerate(tracks):
        if i in accepted:
            d=detections[accepted[i]]
            out.append(Track(t.stable_id,d.x,d.y,d.width,d.height,0,d.source))
            links.append((t.stable_id,d.detection_id))
        elif t.missed>=max_missed:
            retired.append(t.stable_id)
        else:
            out.append(Track(t.stable_id,t.x,t.y,t.width,t.height,t.missed+1,
                             t.last_source))
    return TrackUpdate(tuple(out),tuple(links),
                       tuple(d.detection_id for j,d in enumerate(detections) if j not in used),
                       tuple(retired))
