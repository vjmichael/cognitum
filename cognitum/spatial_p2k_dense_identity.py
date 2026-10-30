"""C15 P2K: optional offline, ID-blind, capacity-checked 2-D association study.

NOT the native six-by-six Protobuf hypothesis engine; NOT a production tracker.
Consumes bounding boxes from another tracker's predictions with ID fields removed.
The original predictor's boxes, their detector provenance, and MOT17 GT are not
independent of that tracker. Forced assignments have no Lu action authority.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Mapping

MAX_BOXES_PER_FRAME = 64
MAX_ACTIVE_TRACKS = 512

class DenseAssociationRejected(ValueError):
    pass

@dataclass(frozen=True)
class Detection:
    frame: int
    x: float
    y: float
    w: float
    h: float
    @property
    def center(self):
        return (self.x+self.w/2, self.y+self.h/2)

@dataclass(frozen=True)
class Params:
    sigma_px: float = 35.
    max_speed_px_per_frame: float = 160.
    max_gap_frames: int = 12
    unmatched_cost: float = 12.
    near_tie_margin: float = 0.75
    max_boxes: int = MAX_BOXES_PER_FRAME
    max_tracks: int = MAX_ACTIVE_TRACKS

@dataclass
class Track:
    tid: int
    x: float
    y: float
    frame: int
    vx: float = 0.
    vy: float = 0.
    hits: int = 1


def validate_parameters(p: Params):
    if type(p.max_boxes)!=int or not 1<=p.max_boxes<=64 or type(p.max_tracks)!=int or not 1<=p.max_tracks<=512:
        raise DenseAssociationRejected('INVALID_CAPACITY')
    if type(p.max_gap_frames)!=int or not 1<=p.max_gap_frames<=30:
        raise DenseAssociationRejected('INVALID_GAP_BOUND')
    if not all(math.isfinite(x) for x in (p.sigma_px,p.max_speed_px_per_frame,p.unmatched_cost,p.near_tie_margin)):
        raise DenseAssociationRejected('NONFINITE_CONFIGURATION')
    if not (1<=p.sigma_px<=1000 and 1<=p.max_speed_px_per_frame<=2000 and 0.01<=p.unmatched_cost<=100000 and 0<=p.near_tie_margin<=100):
        raise DenseAssociationRejected('INVALID_ASSIGNMENT_CONFIGURATION')


def parse_id_blind(raw:bytes, *, num_frames:int, max_boxes:int=MAX_BOXES_PER_FRAME):
    """Return detections separately from the source's ID-bearing control rows."""
    if not isinstance(raw,bytes) or type(num_frames)!=int or not 1<=num_frames<=100_000 or type(max_boxes)!=int or not 1<=max_boxes<=64:
        raise DenseAssociationRejected('INVALID_SOURCE_OR_CAPACITY')
    obs=defaultdict(list); rows=defaultdict(list)
    try:lines=raw.decode('utf-8-sig').splitlines()
    except UnicodeError as exc:raise DenseAssociationRejected('INVALID_ENCODING') from exc
    if not lines or len(lines)>500_000:raise DenseAssociationRejected('INVALID_ROW_COUNT')
    for number,line in enumerate(lines,1):
        parts=line.split(',')
        if len(parts)!=10:raise DenseAssociationRejected(f'INVALID_MOT_ROW_COLUMNS:{number}')
        try:
            values=[float(s) for s in parts]
            if not all(math.isfinite(v) for v in values):raise ValueError('nonfinite')
            f,ident=values[:2]
            if f!=int(f) or not 1<=f<=num_frames or ident!=int(ident) or ident<0:
                raise ValueError('frame or id')
            if values[4]<=0 or values[5]<=0:raise ValueError('geometry')
        except (ValueError,OverflowError) as exc:raise DenseAssociationRejected(f'INVALID_MOT_ROW:{number}') from exc
        f=int(f)
        # Only geometry crosses the ID-blind boundary; never keep source ID, even
        # as auxiliary metadata or a sort key on the proposed association side.
        obs[f].append(Detection(f,*values[2:6]));rows[f].append(parts)
        if len(obs[f])>max_boxes:raise DenseAssociationRejected(f'DENSITY_EXCEEDS_CAPACITY:frame={f}')
    return obs,rows


def assign_all(frames:Mapping[int,list[Detection]], *, num_frames:int, mode:str, params:Params=Params()):
    """Hungarian assignment over active tracks and independent unmatched dummies.

    The deterministic top-choice is a *research-only forced label* for TrackEval.
    No calibrated identity confidence or authorization is computed here.
    """
    validate_parameters(params)
    if mode not in ('position','velocity') or type(num_frames)!=int or not 1<=num_frames<=100_000:
        raise DenseAssociationRejected('INVALID_MODE_OR_FRAMES')
    from scipy.optimize import linear_sum_assignment  # optional SciPy dependency
    import numpy as np
    states:dict[int,Track]={}; output={}; next_tid=1;counts=Counter(); frame_details=[]
    if any(type(f)!=int or f<1 or f>num_frames for f in frames):
        raise DenseAssociationRejected('INVALID_FRAME_INDEX')
    for frame in range(1,num_frames+1):
        # An absent frame is a valid empty frame; never compress time.
        states={k:v for k,v in states.items() if frame-v.frame<=params.max_gap_frames}
        dets=frames.get(frame,[])
        if len(dets)>params.max_boxes:raise DenseAssociationRejected(f'DENSITY_EXCEEDS_CAPACITY:frame={frame}')
        if len(states)>params.max_tracks:raise DenseAssociationRejected(f'ACTIVE_TRACK_LIMIT:frame={frame}')
        if any(not isinstance(d,Detection) or d.frame!=frame or
               not all(math.isfinite(v) for v in (d.x,d.y,d.w,d.h)) or d.w<=0 or d.h<=0
               for d in dets):raise DenseAssociationRejected('INVALID_DETECTION')
        if not dets:
            counts['frames_without_detections']+=1
            continue
        active=sorted(states.values(),key=lambda t:t.tid)
        n=len(dets);t=len(active)
        matrix=np.full((n,t+n),1e12,dtype=np.float64)
        matrix[:,t:]=params.unmatched_cost + 1e-10*np.arange(n)[None,:]
        allowed=[]
        for i,d in enumerate(dets):
            cx,cy=d.center;row=[]
            for j,old in enumerate(active):
                dt=frame-old.frame
                pred_x=old.x+(old.vx*dt if mode=='velocity' and old.hits>=2 else 0.)
                pred_y=old.y+(old.vy*dt if mode=='velocity' and old.hits>=2 else 0.)
                dist=math.hypot(cx-pred_x,cy-pred_y)
                cost=0.5*(dist/params.sigma_px)**2
                admissible=(dist<=params.max_speed_px_per_frame*dt+3*params.sigma_px and
                            math.isfinite(cost) and cost<=params.unmatched_cost)
                if admissible:matrix[i,j]=cost+1e-9*j
                row.append((j,cost) if admissible else None)
            allowed.append(row)
        chosen_rows,chosen_cols=linear_sum_assignment(matrix)
        if len(chosen_rows)!=n:raise DenseAssociationRejected('INCOMPLETE_ASSIGNMENT')
        ids=[None]*n
        near_ties=0;matched=0;unmatched=0
        for i,j in zip(chosen_rows.tolist(),chosen_cols.tolist()):
            cx,cy=dets[i].center
            if j<t and matrix[i,j]<1e11:
                old=active[j]
                dt=frame-old.frame
                vx=(cx-old.x)/dt;vy=(cy-old.y)/dt
                # The velocity candidate retains the last actual observed
                # displacement; no appearance or camera motion model exists.
                states[old.tid]=Track(old.tid,cx,cy,frame,vx,vy,old.hits+1)
                tid=old.tid;matched+=1
                other_costs=[edge[1] for edge in allowed[i] if edge is not None and edge[0]!=j]
                other_costs.append(params.unmatched_cost)
                if min(other_costs)-matrix[i,j]<=params.near_tie_margin:near_ties+=1
            else:
                tid=next_tid;next_tid+=1
                states[tid]=Track(tid,cx,cy,frame);unmatched+=1
            ids[i]=tid
        if len(set(ids))!=n:raise DenseAssociationRejected('DUPLICATE_FRAME_IDS')
        if len(states)>params.max_tracks:raise DenseAssociationRejected(f'ACTIVE_TRACK_LIMIT:frame={frame}')
        counts.update({'observed_frames':1,'input_boxes':n,'matched_boxes':matched,
                       'new_identity_proposals':unmatched,'heuristically_near_tied_matches':near_ties})
        counts['max_active_tracks']=max(counts['max_active_tracks'],len(states))
        counts['max_frame_boxes']=max(counts['max_frame_boxes'],n)
        if n>6:counts['frames_over_legacy_six_observation_limit']+=1
        output[frame]=ids
        frame_details.append({'frame':frame,'boxes':n,'near_tie_matches':near_ties,'new_ids':unmatched,
                              'has_multiple_indistinguishable_class_boxes':n>1})
    # Every multi-object frame remains identity-uncertain by design, even when
    # the nearest distance is separated; this is not a posterior probability.
    counts['multi_object_frames_without_identity_proof']=sum(x['has_multiple_indistinguishable_class_boxes'] for x in frame_details)
    counts['missing_frames_or_no_detections']=num_frames-counts['observed_frames']
    return output,dict(counts),frame_details
