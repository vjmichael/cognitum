"""P2K reproducible full-sequence MOT17 identity-only challenge, research only.

Three prespecified scenes, the same MPNTrack boxes/score/GT in each arm.
MPNTrack identities are withheld from the two experimental assignment arms.
Outputs are mandatory top-1 research hypotheses despite ambiguity; do not
infer actionable identity certainty or independent detection from scores.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from cognitum import spatial_mot17_realdata_gate as rd
from cognitum import spatial_p2k_dense_identity as di
from cognitum.spatial_trackeval_bridge import read_summary

SEQUENCES=('MOT17-02-DPM','MOT17-05-DPM','MOT17-13-DPM')
TRACKERS=('MPNTrackOriginal','CognitumP2KPosition','CognitumP2KVelocity')
MODES=('position','velocity')

class P2KRejected(ValueError): pass

def hashbytes(data:bytes):return hashlib.sha256(data).hexdigest()

def _staged_write(root:Path, name:str, data:bytes, hashes:dict):
    dest=root/name
    if dest.exists():raise P2KRejected('STAGED_FILE_ALREADY_EXISTS')
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    if dest.read_bytes()!=data:raise P2KRejected('STAGED_WRITE_MISMATCH')
    hashes[name]=hashbytes(data)

def stage(*, data_zip:Path, labels_zip:Path, out_dir:Path, params:di.Params=di.Params()):
    di.validate_parameters(params)
    if out_dir.exists() and any(out_dir.iterdir()):raise P2KRejected('OUTPUT_DIRECTORY_NOT_EMPTY')
    originals={};plans={};records=[];hashes={}
    with zipfile.ZipFile(data_zip) as dz,zipfile.ZipFile(labels_zip) as lz:
        for seq in SEQUENCES:
            root=f'data/gt/mot_challenge/MOT17-train/{seq}/'
            gt=rd._read(dz,root+'gt/gt.txt')
            seqinfo=rd._read(dz,root+'seqinfo.ini')
            if gt!=rd._read(lz,f'train/{seq}/gt/gt.txt') or seqinfo!=rd._read(lz,f'train/{seq}/seqinfo.ini'):
                raise P2KRejected('INDEPENDENT_MOT17_LABELS_MISMATCH')
            meta=rd._seq_metadata(seqinfo,seq)
            pred=rd._read(dz,f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{seq}.txt')
            rd._validate_rows(gt,role='ground_truth',nframes=meta['frames'])
            rd._validate_rows(pred,role='prediction',nframes=meta['frames'])
            obs,originals[seq]=di.parse_id_blind(pred,num_frames=meta['frames'],max_boxes=params.max_boxes)
            versions={};stats={};details={}
            for mode in MODES:
                assigned,counts,frame_details=di.assign_all(obs,num_frames=meta['frames'],mode=mode,params=params)
                lines=[]
                for frame in range(1,meta['frames']+1):
                    source_rows=originals[seq].get(frame,[])
                    output_ids=assigned.get(frame,[])
                    if len(source_rows)!=len(output_ids):raise P2KRejected('ROW_COUNT_MISMATCH')
                    for row,tid in zip(source_rows,output_ids):
                        if tid<1:raise P2KRejected('INVALID_NEW_ID')
                        new=row.copy();new[1]=str(tid)
                        if new[0]!=row[0] or new[2:]!=row[2:]:raise P2KRejected('SOURCE_GEOMETRY_CHANGED')
                        lines.append(','.join(new))
                if len(lines)!=sum(map(len,originals[seq].values())):raise P2KRejected('OUTPUT_ROW_LOSS')
                versions[mode]=('\n'.join(lines)+'\n').encode()
                stats[mode]=counts
                details[mode]=frame_details
            plans[f'gt/MOT17-train/{seq}/gt/gt.txt']=gt
            plans[f'gt/MOT17-train/{seq}/seqinfo.ini']=seqinfo
            plans[f'trackers/MOT17-train/{TRACKERS[0]}/data/{seq}.txt']=pred
            for mode,tracker in zip(MODES,TRACKERS[1:]):
                plans[f'trackers/MOT17-train/{tracker}/data/{seq}.txt']=versions[mode]
            records.append({'sequence':seq,'metadata':meta,'source_gt_sha256':hashbytes(gt),
                            'source_prediction_sha256':hashbytes(pred),
                            'input_boxes':sum(len(v) for v in obs.values()),
                            'modes':stats,'frame_diagnostics':details})
    plans['gt/seqmaps/MOT17-train.txt']=('name\n'+'\n'.join(SEQUENCES)+'\n').encode()
    # All validation completed before writing to the staging directory.
    for name,data in plans.items():_staged_write(out_dir,name,data,hashes)
    return {'milestone':'C15_P2K_FULL_SEQUENCE_ID_BLIND_MATCHED_BOXES',
            'research_only':True,'no_host_authority':True,
            'not_same_as_six_by_six_protobuf_associator':True,
            'not_independent_detector_or_tracker':True,
            'source_boxes':'MPNTrack prediction boxes, not independent detector boxes',
            'source_ids_exposed_to_associator':False,'ground_truth_exposed_to_associator':False,
            'top1_forced_despite_unproven_identity':True,
            'multi_object_frames_ambiguous_for_authorization':True,
            'candidate_backends':'SciPy Hungarian, position and constant-velocity prediction',
            'experiment_parameters_frozen_before_scoring':asdict(params),
            'selected_seqs_before_scoring':list(SEQUENCES),
            'staged_sha256':hashes,'sequences':records,'official_evaluation':None}

def evaluate(*, out_dir:Path, evidence:dict, trackeval_root:Path, source_zip:Path, timeout:int=300):
    pin=rd.verify_pinned_trackeval_source(source_zip=source_zip,checkout=trackeval_root)
    for name,digest in evidence['staged_sha256'].items():
        target=out_dir/name
        if not target.is_file() or hashbytes(target.read_bytes())!=digest:
            raise P2KRejected('STAGED_DATA_CHANGED:'+name)
    summaries=[out_dir/'trackers'/'MOT17-train'/name/'pedestrian_summary.txt' for name in TRACKERS]
    if any(p.exists() for p in summaries):raise P2KRejected('STALE_EVALUATOR_OUTPUT')
    shim=Path(__file__).resolve().parent.parent/'tools'/'c15_trackeval_legacy_numpy_compat.py'
    runner=trackeval_root/'scripts'/'run_mot_challenge.py'
    command=[sys.executable,str(shim),str(runner),'--GT_FOLDER',str(out_dir/'gt'),
             '--TRACKERS_FOLDER',str(out_dir/'trackers'),'--BENCHMARK','MOT17',
             '--SPLIT_TO_EVAL','train','--TRACKERS_TO_EVAL',*TRACKERS,
             '--CLASSES_TO_EVAL','pedestrian','--METRICS','HOTA','CLEAR','Identity',
             '--DO_PREPROC','True','--PLOT_CURVES','False','--PRINT_CONFIG','False',
             '--TIME_PROGRESS','False','--USE_PARALLEL','False']
    try:
        result=subprocess.run(command,cwd=trackeval_root,capture_output=True,text=True,timeout=timeout,check=False)
    except subprocess.TimeoutExpired as exc:raise P2KRejected('OFFICIAL_EVALUATOR_TIMEOUT') from exc
    if result.returncode:
        raise P2KRejected('OFFICIAL_EVALUATOR_FAILED: '+result.stdout[-1500:]+' '+result.stderr[-500:])
    if rd.verify_pinned_trackeval_source(source_zip=source_zip,checkout=trackeval_root)!=pin:
        raise P2KRejected('TRACK_EVAL_SOURCE_CHANGED')
    for name,digest in evidence['staged_sha256'].items():
        if hashbytes((out_dir/name).read_bytes())!=digest:raise P2KRejected('INPUT_CHANGED_DURING_EVAL')
    metrics={k:read_summary(p) for k,p in zip(TRACKERS,summaries)}
    return {'status':'official_trackeval_completed','pinned_source':pin,
            'do_preproc':True,'scores':metrics,
            'differences':{tracker:{key:metrics[tracker][key]-metrics[TRACKERS[0]][key]
                                    for key in ('HOTA','DetA','AssA','MOTA','IDF1','IDSW','CLR_TP','CLR_FP','CLR_FN')}
                           for tracker in TRACKERS[1:]},
            'summary_sha256':{k:hashbytes(p.read_bytes()) for k,p in zip(TRACKERS,summaries)},
            'official_runner_sha256':hashbytes(runner.read_bytes()),
            'compat_shim_sha256':hashbytes(shim.read_bytes()),
            'stdout_tail':result.stdout[-1100:]}
