"""Matched standalone C15, direct ByteTrack and integrated C15 ByteTrack.

Separate prediction processes receive only detector paths; GT is opened
only after all three predictions are frozen. No tuning against these inputs.
Official evaluator uses reviewed pinned source, not self-reported tracker scores.
"""
from argparse import ArgumentParser
from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter,process_time
from importlib.metadata import version
import json,os,shutil,subprocess,sys

from cognitum.contracts import HostContext
from cognitum.spatial_tracking import Detection,MAX_DETECTIONS
from cognitum.spatial_mot_adapter import read_mot
from cognitum.spatial_bytetrack import (Scope,Frame,execute,CONFIG,MAX_FRAMES,_engine,VERSION)
from tools.c15_real_mot_acceptance import real_tracking,_save_predictions
from tools.c15_compare_official_trackeval import read_summary
from tools.c15_trackeval_pinned_compat import PIN,FILES,patch_pinned

ARMS=("C15","DirectByteTrack","IntegratedByteTrack")
SEQUENCES=("MOT17-02-FRCNN","MOT17-05-FRCNN")
BUILD=os.environ.get("COG06B_EXPECTED_SHA","")

def sha(path):return sha256(path.read_bytes()).hexdigest()

def frames_for(rows,source_hash):
    by=defaultdict(list)
    for row in rows:by[row.frame].append(row)
    count=max(by,default=0)
    if not 1<=count<=MAX_FRAMES:raise ValueError("benchmark sequence outside frame bound")
    selected=[];frames=[];dropped=0
    for n in range(1,count+1):
        sorted_rows=sorted(by.get(n,()),key=lambda d:(-d.score,d.x,d.y))
        part=sorted_rows[:MAX_DETECTIONS];dropped+=len(sorted_rows)-len(part)
        if any(not 0<=d.score<=1 for d in part):
            raise ValueError("unreviewed detector confidence domain")
        selected.append(part)
        frames.append(Frame(n,"public_detector","validation_v1",source_hash,
                     tuple(Detection("det_"+str(n)+"_"+str(i),d.x,d.y,d.w,d.h,"public_detector")
                           for i,d in enumerate(part)),tuple(d.score for d in part)))
    return tuple(frames),selected,dropped

def as_predictions(frame,part,assignments):
    for index,d in enumerate(part):
        key=frame.detections[index].detection_id
        if key in assignments:
            yield (frame.number,assignments[key],d.x,d.y,d.w,d.h,d.score)

def arm(det,path,sequence,name):
    if len(BUILD)!=40:raise ValueError("frozen source identity required")
    rows,det_hash=read_mot(det,kind="det")
    fs,selected,dropped=frames_for(rows,det_hash)
    track_rows=[];extra={};start=perf_counter();cpu=process_time()
    if name=="C15":
        pred,inner_ms,total_drops=real_tracking(rows)
        track_rows=list(pred);extra["bounded_capacity_drops"]=total_drops
    elif name=="DirectByteTrack":
        np,sv,engine,backend_hash=_engine()
        for f,part in zip(fs,selected):
            boxes=np.asarray([[d.x,d.y,d.x+d.width,d.y+d.height] for d in f.detections],
                             dtype=np.float64).reshape(-1,4)
            detections=sv.Detections(xyxy=boxes,confidence=np.asarray(f.confidence,dtype=np.float64),
                                     data={"c15_index":np.arange(len(part),dtype=np.int64)})
            out=engine.update(detections)
            assigned={}
            if len(out):
                for index,tid in zip(out.data["c15_index"],out.tracker_id):
                    if int(tid)>=0:assigned[f.detections[int(index)].detection_id]=int(tid)
            track_rows.extend(as_predictions(f,part,assigned))
        extra["backend_sha256"]=backend_hash
        extra["configuration"]=dict(CONFIG)
    elif name=="IntegratedByteTrack":
        ctx=HostContext("cog06g","fixture_owner")
        scope=Scope(ctx.workspace_id,ctx.subject_id,sequence,BUILD)
        immutable=frozenset(fs);counts=defaultdict(int)
        def admit(claim,context):
            counts[claim.phase]+=1
            return context==ctx and claim.phase in ("sequence","associate","verify","publish")
        result=execute(scope,fs,ctx,expected_build_sha=BUILD,admit=admit,
                       source_current=lambda f,c:c==ctx and f in immutable,cancelled=lambda:False)
        if result.status!="COMPLETED":raise RuntimeError("integrated backend failed closed: "+result.status)
        if len(result.frame_results)!=len(fs) or counts!={"sequence":1,"associate":len(fs),
                "verify":len(fs),"publish":1}:
            raise ValueError("incomplete source-bound admissions")
        for f,part,r in zip(fs,selected,result.frame_results):
            mapped={did:int(sid.rsplit("_",1)[1]) for sid,did in r.update.assignments}
            track_rows.extend(as_predictions(f,part,mapped))
        extra.update(backend_sha256=result.seal.backend_sha256,
                     sequence_receipt=asdict(result.seal),admissions=dict(counts),
                     max_internal_tracks=max(x.live_internal_count for x in result.frame_results),
                     configuration=dict(CONFIG),
                     unassigned=sum(len(x.update.unmatched_detections) for x in result.frame_results),
                     retired=sum(len(x.update.retired_ids) for x in result.frame_results),
                     new_confirmed=sum(len(x.new_ids) for x in result.frame_results),
                     missed_track_frames=sum(sum(t.missed>0 for t in x.update.tracks) for x in result.frame_results))
    else:raise ValueError("unknown benchmark arm")
    cpu_ms=(process_time()-cpu)*1000;wall_ms=(perf_counter()-start)*1000
    pred_hash=_save_predictions(path,track_rows)
    memory=None
    if sys.platform.startswith("linux"):
        import resource
        memory=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    info={"source_sha":BUILD,"arm":name,"sequence":sequence,"det_sha256":det_hash,
          "prediction_sha256":pred_hash,"input_rows":len(rows),"selected_rows":len(rows)-dropped,
          "detector_capacity_excluded":dropped,"predictions":len(track_rows),
          "frames":len(fs),"wall_ms":wall_ms,"cpu_ms":cpu_ms,"peak_process_rss_kib":memory,
          "versions":{x:version(x) for x in ("numpy","scipy","trackers","supervision")},
          **extra}
    print(json.dumps(info,allow_nan=False))

def score_sequence(data,sequence,evidence,evaluator):
    gt=data/sequence/"gt"/"gt.txt";det=data/sequence/"det"/"det.txt"
    if not gt.is_file() or not det.is_file() or gt.resolve()==det.resolve():
        raise ValueError("matched original detector and GT inputs required")
    with TemporaryDirectory(prefix="c15-matched-") as temporary:
        tmp=Path(temporary);metadata={};predictions={}
        for name in ARMS:
            dest=tmp/(name+".txt")
            p=subprocess.run([sys.executable,"-m","tools.c15_bytetrack_benchmark",
              "--arm",name,"--det",str(det),"--output",str(dest),"--sequence",sequence],
              capture_output=True,check=True,timeout=100,text=True)
            (evidence/(sequence+"-"+name+".json")).write_text(p.stdout,encoding="utf-8")
            info=json.loads(p.stdout)
            if info["source_sha"]!=BUILD or info["det_sha256"]!=sha(det) or info["prediction_sha256"]!=sha(dest):
                raise ValueError("unbound benchmark arm")
            metadata[name]=info;predictions[name]=dest
        if (predictions["DirectByteTrack"].read_bytes()!=predictions["IntegratedByteTrack"].read_bytes()
                or metadata["DirectByteTrack"]["backend_sha256"]!=metadata["IntegratedByteTrack"]["backend_sha256"]):
            raise ValueError("integrated assignment differs from actual direct ByteTrack")
        if len({v["det_sha256"] for v in metadata.values()})!=1 or len({v["selected_rows"] for v in metadata.values()})!=1:
            raise ValueError("unmatched detector workload")
        # Only NOW read GT. Neither prediction process is passed a GT path.
        gt_rows,gt_hash=read_mot(gt,kind="gt")
        if not gt_rows or gt_hash==sha(det):raise ValueError("invalid independent GT")
        seq_len=max(x.frame for x in gt_rows)
        if any(v["frames"]>seq_len for v in metadata.values()):
            raise ValueError("prediction exceeds GT sequence length")
        stage=tmp/"stage";g=stage/"gt/MOT17-train"/sequence/"gt/gt.txt"
        g.parent.mkdir(parents=True);shutil.copyfile(gt,g)
        # DO_PREPROC=False pinned evaluator uses only seqLength. No invented camera
        # geometry, frame rate, or footage needed for frame-index association scores.
        (g.parent.parent/"seqinfo.ini").write_text("[Sequence]\nname="+sequence+"\nseqLength="+str(seq_len)+"\n",encoding="ascii")
        seqmap=stage/"gt/seqmaps/MOT17-train.txt";seqmap.parent.mkdir(parents=True)
        seqmap.write_text("name\n"+sequence+"\n",encoding="ascii")
        for name in ARMS:
            dest=stage/"trackers/MOT17-train"/name/"data"/(sequence+".txt")
            dest.parent.mkdir(parents=True);shutil.copyfile(predictions[name],dest)
        cmd=[sys.executable,str(evaluator/"scripts/run_mot_challenge.py"),"--GT_FOLDER",str(stage/"gt"),
             "--TRACKERS_FOLDER",str(stage/"trackers"),"--BENCHMARK","MOT17","--SPLIT_TO_EVAL","train",
             "--TRACKERS_TO_EVAL",*ARMS,"--CLASSES_TO_EVAL","pedestrian","--METRICS","HOTA","CLEAR","Identity",
             "--DO_PREPROC","False","--PLOT_CURVES","False","--USE_PARALLEL","False",
             "--PRINT_CONFIG","False","--TIME_PROGRESS","False"]
        with (evidence/(sequence+"-official.log")).open("xb") as log:
            subprocess.run(cmd,cwd=evaluator,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
        scores={}
        for name in ARMS:
            path=stage/"trackers/MOT17-train"/name/"pedestrian_summary.txt"
            scores[name]=read_summary(path)
            shutil.copyfile(path,evidence/(sequence+"-"+name+"-summary.txt"))
        if scores["DirectByteTrack"]!=scores["IntegratedByteTrack"]:
            raise ValueError("official integrated/direct metric mismatch")
        report={"source_sha":BUILD,"sequence":sequence,"ground_truth_sha256":gt_hash,
                "gt_frames":seq_len,"scope":"public detector validation, DO_PREPROC=False; not leaderboard",
                "direct_integrated_prediction_bytes_identical":True,"official_scores":scores,
                "arms":metadata,"configuration_frozen":dict(CONFIG),"default_promoted":False}
        (evidence/(sequence+"-comparison.json")).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,indent=2))

def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()

def main():
    p=ArgumentParser()
    p.add_argument("--arm",choices=ARMS);p.add_argument("--det",type=Path);p.add_argument("--output",type=Path)
    p.add_argument("--sequence",choices=SEQUENCES);p.add_argument("--data",type=Path)
    p.add_argument("--evidence",type=Path);p.add_argument("--evaluator",type=Path)
    a=p.parse_args()
    if a.arm:
        arm(a.det,a.output,a.sequence,a.arm);return
    if (len(BUILD)!=40 or git(Path.cwd(),"rev-parse","HEAD")!=BUILD
        or not all(v is not None for v in (a.data,a.evidence,a.evaluator))):
        raise ValueError("exact source and explicit directories required")
    evidence=a.evidence.resolve();evidence.mkdir(exist_ok=False)
    data=a.data.resolve();root=a.evaluator.resolve()
    if git(root,"rev-parse","HEAD")!=PIN or git(root,"status","--porcelain"):
        raise ValueError("unreviewed evaluator")
    audit=patch_pinned(root)
    if set(git(root,"diff","--name-only").splitlines())!=set(FILES):
        raise ValueError("unexpected evaluator mutation")
    (evidence/"dtype-audit.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    for seq in SEQUENCES:score_sequence(data,seq,evidence,root)
    if git(Path.cwd(),"rev-parse","HEAD")!=BUILD or git(Path.cwd(),"status","--porcelain","--untracked-files=no"):
        raise ValueError("source changed")
if __name__=="__main__":main()
