"""C15 P2L image-backed, ID-blind MOT17 association study (no GT in tracker).

Requires actual MOT17 **train** JPEG frames. In their absence emits a blocked
status, not a fabricated appearance score. Stages three identical-box arms
for a later official TrackEval run; no metrics are computed by this command.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from cognitum.spatial_p2k_dense_identity import parse_id_blind,assign_all,Params
from cognitum.spatial_p2l_appearance import (
    descriptors_from_frames,assign_with_appearance,AppearanceConfig,P2LRejected,
    ENCODER_ID,ENCODER_DIGEST,
)


def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def _candidate_frames(frame_dir: Path, frame: int) -> Path | None:
    # Directory name is scoped by caller; never trust ZIP member paths as output paths.
    for suffix in ('.jpg','.jpeg','.png'):
        p=frame_dir/f'{frame:06d}{suffix}'
        if p.is_file():return p
    return None


def study(*, data_zip:Path, frames_dir:Path, sequence:str, frames:int, output:Path,
          params:Params=Params(), config:AppearanceConfig=AppearanceConfig()) -> dict:
    if not sequence.startswith('MOT17-') or not sequence.endswith(('-DPM','-FRCNN','-SDP')):
        raise P2LRejected('INVALID_MOT17_SEQUENCE')
    if not isinstance(frames,int) or not 1<=frames<=3000:raise P2LRejected('INVALID_FRAME_LIMIT')
    if output.exists() and any(output.iterdir()):raise P2LRejected('STAGING_DIRECTORY_NOT_EMPTY')
    if not frames_dir.is_dir():
        return {'status':'blocked_real_mot17_train_frames_missing', 'sequence':sequence,
                'expected':'MOT17 train image directory with img1/000001.jpg',
                'no_synthetic_substitute':True,'official_metrics':None}
    paths={f:_candidate_frames(frames_dir,f) for f in range(1,frames+1)}
    missing=[f for f,path in paths.items() if path is None]
    if missing:
        return {'status':'blocked_real_mot17_train_frames_missing','sequence':sequence,
                'missing_count':len(missing),'first_missing_frames':missing[:8],
                'no_synthetic_substitute':True,'official_metrics':None}
    if not data_zip.is_file():raise P2LRejected('TRACK_EVAL_DATA_MISSING')
    member=f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{sequence}.txt'
    with zipfile.ZipFile(data_zip) as z:
        raw=z.read(member)
    # Read full original predictions; then strict chronological first-N slice.
    lines=[]
    for line in raw.decode('utf-8-sig').splitlines():
        if not line:continue
        part=line.split(',')
        if len(part)!=10:raise P2LRejected('INVALID_SOURCE_ROW')
        try:f=int(float(part[0]))
        except ValueError as exc:raise P2LRejected('INVALID_SOURCE_FRAME') from exc
        if 1<=f<=frames:lines.append(line)
    if not lines:raise P2LRejected('NO_PREDICTIONS_IN_WINDOW')
    chosen=('\n'.join(lines)+'\n').encode()
    detections, rows = parse_id_blind(chosen,num_frames=frames,max_boxes=params.max_boxes)
    image_data={f:paths[f].read_bytes() for f,dets in detections.items() if dets}
    features=descriptors_from_frames(detections,image_data,sequence=sequence)
    assigned,stats=assign_with_appearance(detections,num_frames=frames,sequence=sequence,
        image_bytes=image_data,descriptors=features,params=params,config=config)
    control_pos,posstats,_=assign_all(detections,num_frames=frames,mode='position',params=params)
    control_vel,velstats,_=assign_all(detections,num_frames=frames,mode='velocity',params=params)
    versions={'CognitumP2LHistogram':assigned,'CognitumP2KPosition':control_pos,
              'CognitumP2KVelocity':control_vel}
    files={'MPNTrackOriginal.txt':chosen}
    for tracker,by_frame in versions.items():
        new_rows=[]
        for frame in range(1,frames+1):
            for line,tid in zip(rows.get(frame,[]),by_frame.get(frame,[])):
                copy=line.copy();copy[1]=str(tid)
                if copy[0]!=line[0] or copy[2:]!=line[2:]:raise P2LRejected('UNEXPECTED_GEOMETRY_CHANGE')
                new_rows.append(','.join(copy))
        if len(new_rows)!=len(lines):raise P2LRejected('ROW_COUNT_CHANGE')
        files[tracker+'.txt']= ('\n'.join(new_rows)+'\n').encode()
    output.mkdir(parents=True,exist_ok=True)
    digest={}
    for filename,data in files.items():
        (output/filename).write_bytes(data); digest[filename]=sha(data)
    evidence={'status':'image_backed_research_outputs_ready_for_official_evaluator',
        'sequence':sequence,'frames':frames,'boxes':len(lines),'research_only':True,
        'input_boxes_from':'MPNTrack predictions, not independent detections',
        'original_tracking_ids_stripped_before_matching':True,
        'encoder':ENCODER_ID,'encoder_spec_sha256':ENCODER_DIGEST.hex(),
        'learned_reid_model':False,'independently_attested_encoder_execution':False,
        'official_metrics':None,'frame_image_sha256':{str(f):sha(data) for f,data in image_data.items()},
        'source_prediction_sha256':sha(chosen),'output_sha256':digest,
        'candidate_stats':{'appearance':stats,'position':posstats,'velocity':velstats},
        'matching_params':asdict(params),'appearance_params':asdict(config)}
    (output/'manifest.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    return evidence


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-zip',type=Path,required=True)
    p.add_argument('--frames-dir',type=Path,required=True)
    p.add_argument('--sequence',required=True)
    p.add_argument('--frames',type=int,default=120)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    report=study(data_zip=args.data_zip,frames_dir=args.frames_dir,sequence=args.sequence,
                 frames=args.frames,output=args.output)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'sequence':report['sequence'],'official_metrics':None,
                      'boxes':report.get('boxes'), 'reason':report.get('expected')},sort_keys=True))
    return 0 if report['status'].startswith('image_backed_') else 2

if __name__=='__main__':sys.exit(main())
