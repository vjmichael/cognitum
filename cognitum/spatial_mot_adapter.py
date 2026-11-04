"""MOTChallenge ground-truth/detection parser and independent ID-switch diagnostics.

Real data is EXTERNAL and must be user-supplied/downloaded under its own
license. Ground truth is never fed to trackers as their observations.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
import csv,math,hashlib
from scipy.optimize import linear_sum_assignment

@dataclass(frozen=True)
class Box:
    frame:int
    track_id:int
    x:float;y:float;w:float;h:float
    score:float=1.0
    cls:int=1
    visibility:float=1.0

class MOTRejected(ValueError): pass

def read_mot(path:str|Path, *,kind:str, max_rows:int=1_000_000)->tuple[list[Box],str]:
    if kind not in ('gt','det','prediction'): raise MOTRejected('INVALID_DATA_ROLE')
    p=Path(path)
    if not p.is_file() or p.stat().st_size>80_000_000:raise MOTRejected('FILE_UNAVAILABLE_OR_TOO_LARGE')
    data=p.read_bytes();rows=[]
    try:
        for i,cols in enumerate(csv.reader(data.decode('utf-8-sig').splitlines())):
            if not cols:continue
            if i>=max_rows:raise MOTRejected('ROW_LIMIT')
            if len(cols)<7:raise MOTRejected('TRUNCATED_MOT_ROW')
            vals=[float(c) for c in cols[:7]]
            if not all(math.isfinite(v) for v in vals):raise MOTRejected('NONFINITE_MOT_ROW')
            frame,ident=vals[:2]
            if not (frame>=1 and frame.is_integer() and ident.is_integer()):raise MOTRejected('INVALID_FRAME_OR_TRACK_ID')
            # MOTChallenge trackers, including the original MPNTrack examples, use zero-based IDs.
            if kind=='prediction' and ident<0:raise MOTRejected('INVALID_PREDICTED_ID')
            x,y,w,h=vals[2:6]
            if not(0<w<=10000 and 0<h<=10000):raise MOTRejected('INVALID_BBOX')
            cls=1;vis=1.
            if kind=='gt' and len(cols)>=9:
                cls=int(float(cols[7]));vis=float(cols[8]);
                if not math.isfinite(vis) or not 0<=vis<=1:raise MOTRejected('INVALID_VISIBILITY')
            rows.append(Box(int(frame),int(ident),x,y,w,h,vals[6],cls,vis))
    except (UnicodeDecodeError,ValueError,OverflowError) as e:
        if isinstance(e,MOTRejected):raise
        raise MOTRejected('INVALID_MOT_FORMAT') from e
    return rows,hashlib.sha256(data).hexdigest()

def iou(a:Box,b:Box)->float:
    x1=max(a.x,b.x);y1=max(a.y,b.y);x2=min(a.x+a.w,b.x+b.w);y2=min(a.y+a.h,b.y+b.h)
    inter=max(0,x2-x1)*max(0,y2-y1)
    return inter/(a.w*a.h+b.w*b.h-inter) if inter>0 else 0.

def evaluate(gt:list[Box],pred:list[Box],threshold:float=.5)->dict:
    """Transparent CLEAR-style counts and global identity match; NOT official HOTA.

    Excludes ignore regions and crowd policy; use official TrackEval for published
    MOTChallenge comparisons. This diagnostic must never be called official MOTA.
    """
    if not(0<threshold<=1):raise MOTRejected('INVALID_IOU_THRESHOLD')
    gt_by=defaultdict(list);pred_by=defaultdict(list)
    for b in gt:
        if b.score>0 and b.cls==1:gt_by[b.frame].append(b)
    for b in pred:
        if b.track_id>=0:pred_by[b.frame].append(b)
    total_gt=sum(map(len,gt_by.values()));total_pred=sum(map(len,pred_by.values()))
    last={};pair_count=defaultdict(int);tp=0;switches=0;matches_by_frame=[]
    for frame in sorted(set(gt_by)|set(pred_by)):
        aa,bb=gt_by[frame],pred_by[frame];matched=[]
        if aa and bb:
            cost=[[1-iou(a,b) for b in bb] for a in aa]
            ii,jj=linear_sum_assignment(cost)
            matched=[(aa[i],bb[j]) for i,j in zip(ii,jj) if 1-cost[i][j]>=threshold]
        for a,b in matched:
            tp+=1;pair_count[a.track_id,b.track_id]+=1
            if a.track_id in last and last[a.track_id]!=b.track_id:switches+=1
            last[a.track_id]=b.track_id
        matches_by_frame.append((frame,len(matched)))
    unique_gt=sorted(set(k[0] for k in pair_count));unique_pred=sorted(set(k[1] for k in pair_count))
    idtp=0
    if unique_gt and unique_pred:
        weights=[[pair_count[(i,j)] for j in unique_pred] for i in unique_gt]
        ii,jj=linear_sum_assignment(weights,maximize=True)
        idtp=sum(weights[i][j] for i,j in zip(ii,jj))
    return {'gt_detections':total_gt,'pred_detections':total_pred,'matched_boxes':tp,
            'false_negatives':total_gt-tp,'false_positives':total_pred-tp,'id_switches_diagnostic':switches,
            'global_idf1_diagnostic':(2*idtp/(total_gt+total_pred) if total_gt+total_pred else None),
            'not_official_motchallenge_metrics':True,'requires_independent_detections':True}

# Explicit isolation: prediction inputs must come from an external tracker; no GT-as-detection evaluation.
