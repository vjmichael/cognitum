"""C15 appearance-aided assignment with independently supplied feature vectors.

No image reading, weight loading, embedding generation, camera access or ground
truth leakage. Descriptors are versioned source observations; they are NOT
provenances, permissions or authenticated identity evidence on their own.
"""
from dataclasses import dataclass
from math import isfinite
from .spatial_tracking import Track,Detection,validate as validate_boxes,overlap

MAX_DIM=256
MAX_OBSERVATIONS=64


@dataclass(frozen=True)
class Appearance:
    identity:str             # track stable ID or raw detection ID
    vector:tuple[float,...]
    encoder_id:str
    encoder_digest:str       # SHA256 of approved model artifact, only as claim
    source_id:str
    observation_id:str
    frame_index:int


@dataclass(frozen=True)
class AppearanceAssociation:
    status:str
    matches:tuple[tuple[str,str],...]=()
    ambiguous_tracks:tuple[str,...]=()
    unmatched_detections:tuple[str,...]=()
    limitations:tuple[str,...]=(
        "appearance_embeddings_supplied_by_caller_not_authenticated",
        "encoder_digest_not_verified_by_this_adapter",
        "no_raw_frame_or_model_execution",
        "identity_confidence_not_calibrated",
    )


def _identifier(value):
    return type(value) is str and value.isascii() and value.isidentifier() and 1<=len(value)<=48


def validate_descriptors(tracks,observations,descriptors):
    validate_boxes(tracks,observations)
    if type(descriptors) is not tuple or len(descriptors)>len(tracks)+len(observations):
        raise ValueError("appearance descriptor bound")
    keys=set()
    known={t.stable_id for t in tracks}|{d.detection_id for d in observations}
    for d in descriptors:
        if (type(d) is not Appearance or not _identifier(d.identity)
                or d.identity not in known or d.identity in keys
                or not _identifier(d.encoder_id) or not _identifier(d.source_id)
                or not _identifier(d.observation_id)
                or type(d.encoder_digest) is not str or len(d.encoder_digest)!=64
                or any(c not in "0123456789abcdef" for c in d.encoder_digest)
                or type(d.frame_index) is not int or d.frame_index<0
                or type(d.vector) is not tuple
                or not 2<=len(d.vector)<=MAX_DIM
                or any(type(x) not in (float,int) or not isfinite(x)
                       or abs(x)>1_000_000 for x in d.vector)
                or not 1e-12<sum(x*x for x in d.vector)<1e12):
            raise ValueError("invalid or unsupported appearance evidence")
        keys.add(d.identity)
    if not descriptors:
        raise ValueError("no appearance evidence")
    dims={len(d.vector) for d in descriptors}
    specs={(d.encoder_id,d.encoder_digest) for d in descriptors}
    if len(dims)!=1 or len(specs)!=1:
        raise ValueError("cannot compare incompatible appearance encoders")
    return descriptors


def associate_appearance(
    tracks:tuple[Track,...],detections:tuple[Detection,...],
    descriptors:tuple[Appearance,...], *,
    max_distance:float=40.0,
    max_cosine_distance:float=0.35,
    ambiguity_margin:float=0.05,
)->AppearanceAssociation:
    validate_descriptors(tracks,detections,descriptors)
    if (type(max_distance) not in (float,int) or not isfinite(max_distance)
            or not 0<max_distance<=10000
            or type(max_cosine_distance) not in (float,int)
            or not isfinite(max_cosine_distance) or not 0<=max_cosine_distance<=2
            or type(ambiguity_margin) not in (float,int)
            or not isfinite(ambiguity_margin) or not 0<=ambiguity_margin<=1):
        raise ValueError("invalid appearance association gates")
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
        from scipy.spatial.distance import cosine
    except ImportError:
        return AppearanceAssociation("UNSUPPORTED",
                     unmatched_detections=tuple(d.detection_id for d in detections))
    vectors={d.identity:np.array(d.vector,dtype=np.float64) for d in descriptors}
    n,m=len(tracks),len(detections)
    if not n or not m:
        return AppearanceAssociation("ASSOCIATED",
                     unmatched_detections=tuple(d.detection_id for d in detections))
    weights=np.full((n,m+n),2.1,dtype=float)
    distances={}
    for i,t in enumerate(tracks):
        if t.stable_id not in vectors:
            continue
        for j,d in enumerate(detections):
            if d.detection_id not in vectors:
                continue
            center_dist=float(np.hypot(
                t.x+t.width/2-d.x-d.width/2,
                t.y+t.height/2-d.y-d.height/2))
            if center_dist>max_distance:
                continue
            c=float(cosine(vectors[t.stable_id],vectors[d.detection_id]))
            if not isfinite(c) or c>max_cosine_distance:
                continue
            weights[i,j]=c+0.01*(center_dist/max_distance)
            distances[(i,j)]=c
        weights[i,m+i]=1.05
    # Disallow rows with no available evidence instead of assigning bad edges.
    rows,cols=linear_sum_assignment(weights)
    matches=[]
    ambiguous=[]
    used=set()
    for i,j in zip(rows,cols):
        if j>=m or (i,j) not in distances:
            continue
        # Independent per-track ambiguity test; without enough separation,
        # refuse confident re-identification rather than force an ID switch.
        choices=sorted(distances[(i,k)] for k in range(m) if (i,k) in distances)
        if len(choices)>1 and choices[1]-choices[0]<=ambiguity_margin:
            ambiguous.append(tracks[i].stable_id)
            continue
        # Detect competing track hypotheses for this observation as well.
        opposing=sorted(distances[(k,j)] for k in range(n) if (k,j) in distances)
        if len(opposing)>1 and opposing[1]-opposing[0]<=ambiguity_margin:
            ambiguous.append(tracks[i].stable_id)
            continue
        matches.append((tracks[i].stable_id,detections[j].detection_id))
        used.add(j)
    return AppearanceAssociation("AMBIGUOUS" if ambiguous else "ASSOCIATED",
        tuple(matches),tuple(sorted(set(ambiguous))),
        tuple(d.detection_id for j,d in enumerate(detections) if j not in used))
