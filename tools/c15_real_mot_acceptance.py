"""C15 genuine MOTChallenge data evaluation: detections -> tracking -> held-out GT.

Uses measured externally supplied *detector* detections. Ground truth is
loaded AFTER producing predictions; never fed into matcher or ID assignment.
No fake "real-world" scores and no dataset auto-download. Optional strict
TrackEval is run separately on licensed host-staged output.
"""
from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
import json
import sys

from cognitum.spatial_mot_adapter import read_mot,evaluate as diagnostic
from cognitum.spatial_tracking import Track,Detection,update


def _trusted_file(path,*,maximum=80_000_000):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>maximum:
        raise ValueError("missing, symlinked or oversized benchmark input")
    return path


def _mot_table(path,kind):
    source=_trusted_file(path)
    return read_mot(source,kind=kind)


def real_tracking(detections,*,iou_gate=.05,distance_gate=80.,
                  max_missed=4):
    """Detections only. Stable identity is created on first unmatched hit.

    This is a simple independently executed conventional baseline, not a
    trained appearance tracker. Track age is bounded and source-independent.
    """
    by_frame=defaultdict(list)
    for d in detections:
        if d.frame<1 or d.w<=0 or d.h<=0:
            raise ValueError("invalid detector observation")
        by_frame[d.frame].append(d)
    if not by_frame:
        raise ValueError("no independent detections supplied")
    next_id=1
    active=()
    predictions=[]
    total_wall=0.
    for frame in range(1,max(by_frame)+1):
        detections_for_frame=tuple(
            Detection("det_"+str(frame)+"_"+str(i),d.x,d.y,d.w,d.h,"public_detector")
            for i,d in enumerate(by_frame.get(frame,())))
        start=perf_counter()
        result=update(active,detections_for_frame,min_iou=iou_gate,
                      max_distance=distance_gate,max_missed=max_missed)
        if result.status!="ASSOCIATED":
            raise RuntimeError("native SciPy association unavailable")
        indices={d.detection_id:i for i,d in enumerate(detections_for_frame)}
        mapped={detection_id:stable_id for stable_id,detection_id in result.assignments}
        next_active=list(result.tracks)
        ids={x.stable_id for x in next_active}
        for d in detections_for_frame:
            if d.detection_id not in mapped:
                sid="track_"+str(next_id)
                next_id+=1
                if sid in ids:
                    raise RuntimeError("new track ID collided")
                next_active.append(Track(sid,d.x,d.y,d.width,d.height,
                                         0,"public_detector"))
                mapped[d.detection_id]=sid
                ids.add(sid)
        active=tuple(next_active)
        total_wall+=perf_counter()-start
        for d in detections_for_frame:
            tid=int(mapped[d.detection_id].split("_")[-1])
            # MOT convention requires input detection frame score, not GT.
            original=by_frame[frame][indices[d.detection_id]]
            predictions.append((frame,tid,d.x,d.y,d.width,d.height,
                                original.score))
    return tuple(predictions),total_wall*1000


def _save_predictions(path,pred):
    file=Path(path)
    if file.exists() and file.is_symlink():
        raise ValueError("benchmark output symlink refused")
    if not file.parent.is_dir():
        raise ValueError("benchmark output directory must already exist")
    if file.exists():
        raise ValueError("refuse overwrite of an existing evaluation artifact")
    lines=[]
    for frame,tid,x,y,w,h,score in pred:
        lines.append(f"{frame},{tid},{x:.9g},{y:.9g},{w:.9g},{h:.9g},{score:.9g},-1,-1,-1\n")
    data="".join(lines).encode("ascii")
    if not 0<len(data)<=80_000_000:
        raise ValueError("generated benchmark predictions oversize")
    file.write_bytes(data)
    return sha256(data).hexdigest()


def run(gt_file,det_file,output_file,*,sequence_id,licensed_use):
    if not licensed_use:
        raise ValueError("must attest permission to use this real dataset")
    for file in (gt_file,det_file):
        _trusted_file(file)
    if Path(gt_file).resolve()==Path(det_file).resolve():
        raise ValueError("ground-truth and detector paths are identical")
    det,det_hash=_mot_table(det_file,"det")
    # Generate predictions BEFORE reading ground-truth in this process.
    prediction,wall_ms=real_tracking(det)
    prediction_digest=_save_predictions(output_file,prediction)
    gt,gt_hash=_mot_table(gt_file,"gt")
    if gt_hash==det_hash:
        raise ValueError("GT and detector contents identical: leakage risk")
    pred,_=_mot_table(output_file,"prediction")
    stats=diagnostic(gt,pred)
    result={
        "schema":"c15.real-mot-v1",
        "status":"REAL_DETECTION_INPUTS_EVALUATED_DIAGNOSTIC_ONLY",
        "sequence":sequence_id,
        "input_gt_sha256":gt_hash,
        "independent_det_sha256":det_hash,
        "tracker_prediction_sha256":prediction_digest,
        "tracker":"c15_scipy_hungarian_iou_distance_v1",
        "wall_ms_tracking":round(wall_ms,3),
        "frames":max([d.frame for d in det],default=0),
        "detection_rows":len(det),
        "prediction_rows":len(pred),
        "metrics":stats,
        "limitations":[
            "no_source_authentication_beyond_local_digest",
            "not_official_TrackEval_metrics",
            "no_appearance_model_in_this_baseline",
            "dataset_license_attestation_caller_supplied",
            "requires_official_TrackEval_for_HOTA_MOTA_IDF1",
            "ground_truth_loaded_only_after_predictions_created",
        ],
    }
    print(json.dumps(result,sort_keys=True,indent=2))
    return result


def main():
    parser=ArgumentParser()
    parser.add_argument("--gt",required=True)
    parser.add_argument("--det",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--sequence",required=True)
    parser.add_argument("--i-have-dataset-rights",action="store_true")
    opts=parser.parse_args()
    run(opts.gt,opts.det,opts.output,sequence_id=opts.sequence,
        licensed_use=opts.i_have_dataset_rights)


if __name__=="__main__":
    main()
