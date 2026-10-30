"""C15 P2J: reproducible, *identity-only* MOT17 research ablation.

Inputs are pre-existing MPNTrack prediction boxes with IDs explicitly stripped
before any Cognitum association call. This tests ONLY re-association on the same
boxes; it is NOT an independent detector/tracker or a held-out P3 benchmark.

Pixel centers / 100 are proxy coordinates fed to the scene graph's metre-valued
fields for offline research only. They are not calibrated 3-D measurements.
The scene snapshot is ephemeral and research-only, NOT admitted by Lu.
"""
from __future__ import annotations
import configparser
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import zipfile

from cognitum import spatial_identity_association as association
from cognitum import spatial_mot17_realdata_gate as realdata
from cognitum.proto import spatial_scene_pb2 as sp
from cognitum.proto import spatial_identity_pb2 as pb
from cognitum.spatial_trackeval_bridge import read_summary

SEQUENCE='MOT17-05-DPM'
FRAMES=120
CONVERSION=100.0  # offline pseudo-space: coordinate_unit=100 image pixels
SIGMA=0.30
MAX_SPEED=3.0
UNMATCHED_COST=9.0
TOP_K=2
SCENE='mot17_05_dpm_ablation'
TRACKER_BASE='MPNTrackMatchedBoxes'
TRACKER_COG='CognitumP2JTop1'

class MatchedIdentityRejected(ValueError):
    pass

@dataclass(frozen=True)
class Detection:
    # Explicitly NO source tracker ID. Caller must not pass GT labels or ID.
    frame: int
    x: float
    y: float
    w: float
    h: float
    original_columns_without_id: tuple[str, ...]

    @property
    def center(self):
        return ((self.x + self.w / 2) / CONVERSION,
                (self.y + self.h / 2) / CONVERSION)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parsed_boxes(raw: bytes, *, frames: int=FRAMES):
    """Return IDs separately from detection inputs to enforce the blind boundary."""
    frame_boxes=defaultdict(list); frame_original=defaultdict(list)
    for line in raw.decode('utf-8').splitlines():
        parts=line.strip().split(',')
        if len(parts)!=10:raise MatchedIdentityRejected('PREDICTION_NOT_MOT_10_COLUMNS')
        try:
            f_raw=float(parts[0]); id_raw=float(parts[1]);x,y,w,h=(float(n) for n in parts[2:6])
            if not math.isfinite(f_raw) or not math.isfinite(id_raw) or f_raw!=int(f_raw) or id_raw!=int(id_raw):
                raise ValueError("fractional frame/ID")
            f=int(f_raw);ident=int(id_raw)
        except (ValueError,OverflowError) as e:raise MatchedIdentityRejected('INVALID_PREDICTION_ROW') from e
        if f<1 or ident<0 or not all(math.isfinite(x) for x in (x,y,w,h)) or w<=0 or h<=0:
            raise MatchedIdentityRejected('INVALID_PREDICTION_GEOMETRY')
        if f>frames:continue
        # ID-bearing source is stored in the BASELINE stream only.
        det=Detection(f,x,y,w,h,tuple(parts[:1]+parts[2:]))
        frame_boxes[f].append(det)
        frame_original[f].append(parts)
    if not any(frame_boxes.values()):raise MatchedIdentityRejected('NO_PREDICTIONS')
    for frame in range(1,frames+1):
        if len(frame_boxes[frame])>association.MAX_OBSERVATIONS:
            raise MatchedIdentityRejected('C15_CAPACITY_EXCEEDED_NO_SILENT_DROP')
    return frame_boxes,frame_original


def _scene(states: dict[str, tuple[float,float,int]]):
    snap=sp.SceneSnapshot(schema_version=1,scene_id=SCENE,conversation_id='research_conv',
                          revision=1,research_only=True)
    for tid,(x,y,tick) in sorted(states.items()):
        obj=snap.objects.add(object_id=tid,category='pedestrian',display_name=tid,
                              frame_id='world',observation_source_id='pred_boxes',
                              last_observed_tick=tick,confidence=1.0,
                              visibility=sp.VISIBILITY_VISIBLE)
        obj.position_m.x=x;obj.position_m.y=y;obj.rotation_xyzw.w=1.0
    return snap


def _request(snap, observations, frame):
    req=pb.AssociationRequest(schema_version=1,scene_id=SCENE,conversation_id='research_conv',
                              task_id='matched_id_only',trace_id='p2j',
                              request_id=f'frame_{frame}',scene_sha256=association.digest(snap),
                              measurement_sigma_m=SIGMA,max_speed_m_per_tick=MAX_SPEED,
                              unmatched_cost=UNMATCHED_COST,ambiguity_cost_margin=0.5,
                              top_k=TOP_K)
    for i,det in enumerate(observations):
        obs=req.observations.add(observation_id=f'box_{frame}_{i}',category='pedestrian',
                                  source_id='pred_boxes',frame_id='world',observed_tick=frame)
        obs.position_m.x, obs.position_m.y=det.center
    return req


def reassociate(frames: dict[int,list[Detection]], *, last_frame=FRAMES):
    # Offline TOP-1 POLICY: model's ambiguous status is retained in diagnostics,
    # but top hypothesis is selected for an ablation. No host-authorized ID writes.
    next_id=1;states={};output={}; counts=Counter(); assignments=[]
    for frame in range(1,last_frame+1):
        detections=frames.get(frame,[])
        if not detections:continue
        snap=_scene(states)
        if states:
            req=_request(snap,detections,frame)
            proposal=association.propose(snap,req)
            if proposal.grants_authority:raise MatchedIdentityRejected('UNEXPECTED_AUTHORITY')
            if not association.verify_proposal(snap,req,proposal):
                raise MatchedIdentityRejected('PROPOSAL_REPLAY_MISMATCH')
            pairs={x.observation_id:x.object_id for x in proposal.hypotheses[0].pairs}
            counts['proposals']+=1
            counts['decision_'+pb.AssociationDecision.Name(proposal.decision)]+=1
            counts['ambiguous_top1_forced']+=int(proposal.decision==pb.ASSOCIATION_AMBIGUOUS)
            counts['matched_pairs']+=sum(bool(v) for v in pairs.values())
        else:pairs={};counts['first_frame_without_prior']+=1
        new_states={};pairs_for_frame=[]
        for i,det in enumerate(detections):
            prev=pairs.get(f'box_{frame}_{i}','')
            tid=prev if prev else f'cog_{next_id}'
            if not prev:next_id+=1;counts['new_identity_proposals']+=1
            if tid in new_states:raise MatchedIdentityRejected('DUPLICATE_FRAME_TRACK_ID')
            new_states[tid]=(*det.center,frame)
            pairs_for_frame.append(tid)
        # Retain earlier unmatched tracks when there is spare capacity; no
        # retrospective use of ground truth or original MPNTrack identifiers.
        for tid,state in sorted(states.items(),key=lambda x:(-x[1][2],x[0])):
            if len(new_states)>=association.MAX_TRACKS:break
            if tid not in new_states:new_states[tid]=state
        if len(new_states)>association.MAX_TRACKS:raise MatchedIdentityRejected('TRACK_CAPACITY')
        states=new_states;output[frame]=pairs_for_frame
        counts['input_boxes']+=len(detections)
        assignments.append({'frame':frame,'box_count':len(detections),'ids':pairs_for_frame})
    return output,dict(counts),assignments


def _extract_inputs(data_zip:Path,labels_zip:Path,frames:int):
    prefix=f'data/gt/mot_challenge/MOT17-train/{SEQUENCE}/'
    with zipfile.ZipFile(data_zip) as z,zipfile.ZipFile(labels_zip) as l:
        gt=z.read(prefix+'gt/gt.txt');info=z.read(prefix+'seqinfo.ini')
        if gt!=l.read(f'train/{SEQUENCE}/gt/gt.txt') or info!=l.read(f'train/{SEQUENCE}/seqinfo.ini'):
            raise MatchedIdentityRejected('INDEPENDENT_LABELS_NOT_IDENTICAL')
        p=z.read(f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{SEQUENCE}.txt')
    realdata._validate_rows(gt,role='ground_truth',nframes=837)
    realdata._validate_rows(p,role='prediction',nframes=837)
    c=configparser.ConfigParser();c.read_string(info.decode('utf8'))
    if c.getint('Sequence','seqLength')<frames:raise MatchedIdentityRejected('WINDOW_LONGER_THAN_SEQUENCE')
    gt_window='\n'.join(line for line in gt.decode().splitlines() if int(line.split(',')[0])<=frames)+'\n'
    c.set('Sequence','seqLength',str(frames))
    sio=io.StringIO();c.write(sio)
    return gt_window.encode(),sio.getvalue().encode(),p, {'full_gt_sha256':sha(gt),'full_prediction_sha256':sha(p),'source_seqinfo_sha256':sha(info)}


def stage(data_zip:Path,labels_zip:Path,stage_root:Path,*,frames:int=FRAMES):
    if frames!=FRAMES:raise MatchedIdentityRejected('ONLY_FIXED_120_FRAME_PILOT')
    if stage_root.exists() and any(stage_root.iterdir()):
        raise MatchedIdentityRejected('STAGE_NOT_EMPTY')
    gt,seqinfo,raw,source=_extract_inputs(data_zip,labels_zip,frames)
    detections,original=parsed_boxes(raw,frames=frames)
    assigned,counts,assignments=reassociate(detections,last_frame=frames)
    base=[];cog=[]
    for frame in range(1,frames+1):
        for row,tid in zip(original[frame],assigned.get(frame,[])):
            base.append(','.join(row))
            cand=row.copy();cand[1]=str(int(tid.split('_')[1]))
            cog.append(','.join(cand))
    if len(base)!=counts['input_boxes'] or len(cog)!=len(base):
        raise MatchedIdentityRejected('ROW_COUNT_CHANGED')
    for a,b in zip(base,cog):
        aa=a.split(',');bb=b.split(',')
        if aa[0]!=bb[0] or aa[2:]!=bb[2:]:
            raise MatchedIdentityRejected('DETECTION_GEOMETRY_NOT_IDENTICAL')
    files={
        f'gt/MOT17-train/{SEQUENCE}/gt/gt.txt':gt,
        f'gt/MOT17-train/{SEQUENCE}/seqinfo.ini':seqinfo,
        'gt/seqmaps/MOT17-train.txt':('name\n'+SEQUENCE+'\n').encode(),
        f'trackers/MOT17-train/{TRACKER_BASE}/data/{SEQUENCE}.txt':('\n'.join(base)+'\n').encode(),
        f'trackers/MOT17-train/{TRACKER_COG}/data/{SEQUENCE}.txt':('\n'.join(cog)+'\n').encode(),
    }
    for path,data in files.items():
        target=stage_root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    report={'kind':'C15_T1_P2J_IDENTITY_ONLY_REASSOCIATION_ABLATION','research_only':True,
            'source_box_provenance':'MPNTrack predictions, NOT independent detector observations',
            'source_predictor_ids_used_by_cognitum':False,'gt_supplied_to_association':False,
            'ambiguous_hypotheses_forced_top1_for_analysis':True,
            'not_deployable_host_authority':True,'not_independent_tracker':True,
            'coordinate_mapping':'pixel center / 100 -> pseudo-metre XY (not physical metres)',
            'sequence':SEQUENCE,'frames':frames,'selection':'first 120 frames; no detection filtering or discarding',
            'input_boxes_per_frame_max':max(map(len,detections.values())),
            'source':source,'counts':counts,
            'sha256':{key:sha(data) for key,data in files.items()},
            'input_geometry_identical':True,'output_id_rows_identical_except_column_2':True,
            'parameters':{'pseudo_meters_per_pixel':1/CONVERSION,'sigma_proxy_m':SIGMA,
                          'max_speed_proxy_m_per_tick':MAX_SPEED,'unmatched_cost':UNMATCHED_COST,
                          'top_k':TOP_K},
            'official_evaluation':None}
    return report,assignments


def evaluate(stage_root:Path,report:dict,*,trackeval_root:Path,source_zip:Path,timeout_sec:int=300):
    pin=realdata.verify_pinned_trackeval_source(source_zip=source_zip,checkout=trackeval_root)
    for relative,digest in report['sha256'].items():
        if not (stage_root/relative).is_file() or sha((stage_root/relative).read_bytes())!=digest:
            raise MatchedIdentityRejected('STAGED_INPUT_TAMPERED')
    summary_paths=[stage_root/'trackers'/'MOT17-train'/name/'pedestrian_summary.txt'
                   for name in (TRACKER_BASE,TRACKER_COG)]
    if any(p.exists() for p in summary_paths):raise MatchedIdentityRejected('REFUSE_STALE_SUMMARIES')
    shim=Path(__file__).resolve().parent.parent/'tools'/'c15_trackeval_legacy_numpy_compat.py'
    script=trackeval_root/'scripts'/'run_mot_challenge.py'
    cmd=[sys.executable,str(shim),str(script),'--GT_FOLDER',str(stage_root/'gt'),
         '--TRACKERS_FOLDER',str(stage_root/'trackers'),'--BENCHMARK','MOT17','--SPLIT_TO_EVAL','train',
         '--TRACKERS_TO_EVAL',TRACKER_BASE,TRACKER_COG,'--CLASSES_TO_EVAL','pedestrian',
         '--METRICS','HOTA','CLEAR','Identity','--DO_PREPROC','True',
         '--PLOT_CURVES','False','--PRINT_CONFIG','False','--TIME_PROGRESS','False',
         '--USE_PARALLEL','False']
    try:r=subprocess.run(cmd,cwd=trackeval_root,capture_output=True,text=True,timeout=timeout_sec)
    except subprocess.TimeoutExpired as e:raise MatchedIdentityRejected('EVALUATOR_TIMEOUT') from e
    if r.returncode:raise MatchedIdentityRejected('EVALUATOR_FAILED: '+r.stdout[-800:]+' '+r.stderr[-800:])
    if realdata.verify_pinned_trackeval_source(source_zip=source_zip,checkout=trackeval_root)!=pin:
        raise MatchedIdentityRejected('SOURCE_CHANGED_DURING_RUN')
    scores={name:read_summary(path) for name,path in zip((TRACKER_BASE,TRACKER_COG),summary_paths)}
    return {'source_verified':pin,'do_preproc':True,'metrics':scores,
            'difference_cognitum_minus_baseline':{
                metric: scores[TRACKER_COG][metric]-scores[TRACKER_BASE][metric]
                for metric in ('HOTA','DetA','AssA','MOTA','IDF1','IDSW','CLR_TP','CLR_FP','CLR_FN')},
            'summary_sha256':{name:sha(path.read_bytes()) for name,path in zip((TRACKER_BASE,TRACKER_COG),summary_paths)},
            'runner_sha256':sha(script.read_bytes()),'shim_sha256':sha(shim.read_bytes())}


def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-zip',type=Path,required=True)
    ap.add_argument('--labels-zip',type=Path,required=True)
    ap.add_argument('--stage',type=Path,required=True)
    ap.add_argument('--trackeval-root',type=Path,required=True)
    ap.add_argument('--source-zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    report,assignments=stage(args.data_zip,args.labels_zip,args.stage)
    report['official_evaluation']=evaluate(args.stage,report,trackeval_root=args.trackeval_root,source_zip=args.source_zip)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    assignments_path=args.out.with_name(args.out.stem+'_assignments.json')
    assignments_path.write_text(json.dumps(assignments,separators=(',',':'))+'\n')
    print(json.dumps({'status':'complete','frames':report['frames'],'counts':report['counts'],
                      'scores':report['official_evaluation']['metrics']},sort_keys=True))

if __name__=='__main__':main()
