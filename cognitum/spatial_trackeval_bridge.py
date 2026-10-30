"""Isolated, opt-in TrackEval MOTChallenge-format staging/runner for C15 T1 P2F.

This does not bundle TrackEval or imply that its engine is installed. It rejects
mask data and any attempt to evaluate GT or detections as tracker predictions.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from cognitum.proto import benchmark_observation_pb2 as pb
from cognitum.spatial_benchmark_observation import (
    ObservationRejected, export_mot_rows, validate_sequence,
)

_SAFE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
_METRICS = ('HOTA','DetA','AssA','MOTA','IDF1','IDP','IDR','IDSW','CLR_TP','CLR_FN','CLR_FP')


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(content,encoding='utf-8')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stage_motchallenge(gt, pred, *, root, sequence='CognitumPilot', tracker='CognitumCandidate',
                       benchmark='MOT17', split='train', seq_len=None):
    gt=list(gt); pred=list(pred)
    if not gt or not pred:raise ObservationRejected('NONEMPTY_GT_AND_PRED_REQUIRED')
    if not all(_SAFE.fullmatch(s or '') for s in (sequence,tracker,benchmark,split)):
        raise ObservationRejected('INVALID_OUTPUT_NAME')
    if benchmark not in ('MOT15','MOT16','MOT17','MOT20') or split not in ('train','test','all'):
        raise ObservationRejected('INVALID_EVALUATION_CONFIG')
    validate_sequence(gt,role=pb.GROUND_TRUTH)
    validate_sequence(pred,role=pb.TRACKER_PREDICTION)
    if any(x.HasField('mask') for x in (*gt,*pred)):
        raise ObservationRejected('MOTS_MASK_CANNOT_BE_DISCARDED_IN_BOX_EVALUATION')
    if any(x.class_id != 1 for x in (*gt,*pred)):
        raise ObservationRejected('MOT_PEDESTRIAN_ONLY_CLASS_REQUIRED')
    if {x.sequence_id for x in gt} != {x.sequence_id for x in pred}:
        raise ObservationRejected('INPUT_SEQUENCE_MISMATCH')
    # Same sequence name alone cannot prove the observations are comparable.
    for field in ('image_width', 'image_height', 'camera_frame'):
        if len({getattr(x, field) for x in (*gt, *pred)}) != 1:
            raise ObservationRejected('INPUT_FRAME_METADATA_MISMATCH')
    for field in ('dataset_id', 'dataset_version'):
        if len({getattr(x.provenance, field) for x in (*gt, *pred)}) != 1:
            raise ObservationRejected('INPUT_DATASET_PROVENANCE_MISMATCH')
    gt_timestamps={}
    for x in gt:
        if x.HasField('timestamp_ns'):
            gt_timestamps[x.frame_index]=x.timestamp_ns
    for x in pred:
        if x.HasField('timestamp_ns') and x.frame_index in gt_timestamps and x.timestamp_ns != gt_timestamps[x.frame_index]:
            raise ObservationRejected('INPUT_FRAME_TIMESTAMP_MISMATCH')
    max_frame=max(x.frame_index for x in (*gt,*pred))
    if seq_len is None:seq_len=max_frame
    if type(seq_len)!=int or seq_len<max_frame or seq_len>10000000:
        raise ObservationRejected('INVALID_SEQUENCE_LENGTH')
    root=Path(root).resolve()
    gt_root=root/'gt'; pred_root=root/'trackers'; name=f'{benchmark}-{split}'
    gt_path=gt_root/name/sequence/'gt'/'gt.txt'
    pred_path=pred_root/name/tracker/'data'/f'{sequence}.txt'
    seqinfo_path=gt_root/name/sequence/'seqinfo.ini'
    seqmap_path=gt_root/'seqmaps'/f'{name}.txt'
    paths={
        'gt':_write(gt_path,export_mot_rows(gt,role=pb.GROUND_TRUTH)),
        'prediction':_write(pred_path,export_mot_rows(pred,role=pb.TRACKER_PREDICTION)),
        'seqinfo':_write(seqinfo_path,'[Sequence]\nname='+sequence+'\nimDir=img1\nframeRate=1\nseqLength='+str(seq_len)+'\nimWidth='+str(gt[0].image_width)+'\nimHeight='+str(gt[0].image_height)+'\nimExt=.jpg\n'),
        'seqmap':_write(seqmap_path,'name\n'+sequence+'\n'),
    }
    return {
        'research_only':True,'format':'TrackEval_MOTChallenge_2D',
        'gt_root':str(gt_root),'trackers_root':str(pred_root),
        'seqmap':str(seqmap_path),'sequence':sequence,'tracker':tracker,
        'benchmark':benchmark,'split':split,'frame_count':seq_len,'source_sequence_id':gt[0].sequence_id,
        'rows':{'gt':len(gt),'prediction':len(pred)},'file_sha256':paths,
        'data_roles_separated':True,'mask_scores_supported':False,'official_evaluator_ran':False,
    }


def read_summary(path:Path):
    if not path.is_file():raise ObservationRejected('TRACK_EVAL_NO_SUMMARY_FILE')
    lines=[line.strip().split() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(lines)<2:raise ObservationRejected('TRACK_EVAL_INVALID_SUMMARY')
    headings=lines[0]
    vals=lines[1]
    if len(headings)!=len(vals) or len(set(headings))!=len(headings):
        raise ObservationRejected('TRACK_EVAL_BAD_COLUMNS')
    out={}
    for key,val in zip(headings,vals):
        if key in _METRICS:
            try:out[key]=float(val)
            except ValueError as e:raise ObservationRejected('TRACK_EVAL_NONNUMERIC_SCORE') from e
            if not math.isfinite(out[key]):raise ObservationRejected('TRACK_EVAL_NONFINITE_SCORE')
    if not all(x in out for x in ('HOTA','MOTA','IDF1')):
        raise ObservationRejected('TRACK_EVAL_INCOMPLETE_METRICS')
    return out


def run_trackeval(staging:dict, *, trackeval_root=None, timeout_sec=120):
    """Runs only explicit local source checkout; does not install dependencies.

    Returns blocked record if external engine isn't available. A successful
    invocation still requires the user to verify source revision/provenance.
    """
    rec={'research_only':True,'adapter_format':'TrackEval_MOTChallenge_2D','official_evaluator_ran':False,
         'genuine_engine_source_authenticated':False}
    if trackeval_root is None:
        return {**rec,'status':'blocked_external_engine_missing','reason':'TrackEval checkout not supplied'}
    # Refuse tampered/stale staging prior to executing a third-party benchmark.
    for key, relative in (
        ('gt', Path(staging['gt_root']) / f"{staging['benchmark']}-{staging['split']}" / staging['sequence'] / 'gt' / 'gt.txt'),
        ('prediction', Path(staging['trackers_root']) / f"{staging['benchmark']}-{staging['split']}" / staging['tracker'] / 'data' / f"{staging['sequence']}.txt"),
        ('seqinfo', Path(staging['gt_root']) / f"{staging['benchmark']}-{staging['split']}" / staging['sequence'] / 'seqinfo.ini'),
        ('seqmap', Path(staging['seqmap'])),
    ):
        if not relative.is_file() or hashlib.sha256(relative.read_bytes()).hexdigest()!=staging['file_sha256'][key]:
            return {**rec,'status':'blocked_staging_integrity_failure','file_role':key}
    root=Path(trackeval_root).resolve(); script=root/'scripts'/'run_mot_challenge.py'
    if not script.is_file() or not (root/'trackeval'/'metrics'/'hota.py').is_file():
        return {**rec,'status':'blocked_external_engine_missing','reason':'Required TrackEval source files not found'}
    if not 1 <= timeout_sec <= 3600:raise ObservationRejected('INVALID_TIMEOUT')
    run_sha=hashlib.sha256(script.read_bytes()).hexdigest()
    summary_path=Path(staging['trackers_root'])/f"{staging['benchmark']}-{staging['split']}"/staging['tracker']/'pedestrian_summary.txt'
    if summary_path.exists():
        return {**rec,'status':'blocked_stale_summary_file','runner_sha256':run_sha,
                'reason':'Use a fresh staging directory for each benchmark run'}
    cmd=[sys.executable,str(script),'--GT_FOLDER',staging['gt_root'],'--TRACKERS_FOLDER',staging['trackers_root'],
         '--BENCHMARK',staging['benchmark'],'--SPLIT_TO_EVAL',staging['split'],
         '--SEQMAP_FILE',staging['seqmap'],'--TRACKERS_TO_EVAL',staging['tracker'],
         '--CLASSES_TO_EVAL','pedestrian','--METRICS','HOTA','CLEAR','Identity',
         '--DO_PREPROC','False','--USE_PARALLEL','False','--PLOT_CURVES','False',
         '--PRINT_CONFIG','False','--TIME_PROGRESS','False']
    try:
        run=subprocess.run(cmd,cwd=str(root),capture_output=True,text=True,timeout=timeout_sec,check=False)
    except subprocess.TimeoutExpired:
        return {**rec,'status':'engine_timeout','runner_sha256':run_sha}
    stdout=run.stdout[-5000:]; stderr=run.stderr[-5000:]
    if run.returncode:
        return {**rec,'status':'engine_failed','runner_sha256':run_sha,'exit_code':run.returncode,
                'stdout_tail':stdout,'stderr_tail':stderr}
    # Depending on TrackEval OUTPUT_SUB_FOLDER, default is tracker root.
    try: scores=read_summary(summary_path)
    except ObservationRejected as e:
        return {**rec,'status':'engine_output_missing_or_invalid','runner_sha256':run_sha,'reason':str(e),
                'stdout_tail':stdout,'stderr_tail':stderr}
    return {**rec,'status':'executed_unverified_source_revision','official_evaluator_ran':True,
            'runner_sha256':run_sha,'scores':scores,'external_checkout':str(root),
            'summary_sha256':hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            'requires_external_source_authentication':True,
            'do_preproc':False,'conditions':'Fixed MOT 2D GT and prediction; no mask or detector benchmarking'}
