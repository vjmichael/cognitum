"""Official pinned TrackEval full stage parity, before and after removed aliases.

Uses original pinned source with NumPy's old Python builtin aliases solely as
an isolated test oracle. The deployed scorer uses the exact source patch.
Dataset bytes remain in the runner workspace, not in evidence.
"""
from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import json
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from tools.c15_trackeval_pinned_compat import PIN,FILES,patch_pinned
from tools.c15_compare_official_trackeval import read_summary

TRACKERS=("C15","ByteTrack")

def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()

def scan_inputs(stage):
    paths=[stage/"gt/MOT17-train/MOT17-02-FRCNN/gt/gt.txt",
           stage/"gt/MOT17-train/MOT17-02-FRCNN/seqinfo.ini",
           stage/"gt/seqmaps/MOT17-train.txt"]
    paths.extend(stage/"trackers/MOT17-train"/t/"data/MOT17-02-FRCNN.txt" for t in TRACKERS)
    if any(not p.is_file() or p.is_symlink() or not 0<p.stat().st_size<=80_000_000 for p in paths):
        raise ValueError("unavailable staged evaluation inputs")
    return {str(p.relative_to(stage)):sha256(p.read_bytes()).hexdigest() for p in paths}

def evaluate(root,stage,evidence,label,legacy=False):
    runner=root/"scripts/run_mot_challenge.py"
    cmd=[sys.executable]
    if legacy:
        cmd+=["-c","import numpy as np,runpy,sys; assert np.dtype(int).itemsize==8 and np.dtype(float).itemsize==8; np.float=float; np.int=int; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"]
    cmd += [str(runner),"--GT_FOLDER",str(stage/"gt"),"--TRACKERS_FOLDER",str(stage/"trackers"),
            "--BENCHMARK","MOT17","--SPLIT_TO_EVAL","train","--TRACKERS_TO_EVAL",*TRACKERS,
            "--CLASSES_TO_EVAL","pedestrian","--METRICS","HOTA","CLEAR","Identity",
            "--DO_PREPROC","False","--PLOT_CURVES","False","--USE_PARALLEL","False",
            "--PRINT_CONFIG","False","--TIME_PROGRESS","False"]
    summaries={t:stage/"trackers/MOT17-train"/t/"pedestrian_summary.txt" for t in TRACKERS}
    if any(p.exists() for p in summaries.values()):
        raise ValueError("stale metric output")
    with (evidence/(label+".log")).open("xb") as log:
        subprocess.run(cmd,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                       timeout=300,check=True)
    return {t:(p.read_bytes(),read_summary(p)) for t,p in summaries.items()}

def main():
    p=ArgumentParser()
    for key in ("root","stage","evidence"):
        p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args();root=a.root;stage=a.stage;evidence=a.evidence
    if any(not v.is_absolute() or not v.is_dir() for v in (root,stage,evidence)):
        raise ValueError("explicit absolute local paths required")
    if git(root,"rev-parse","HEAD")!=PIN or git(root,"status","--porcelain"):
        raise ValueError("unreviewed upstream checkout")
    before=scan_inputs(stage)
    with TemporaryDirectory(prefix="trackeval-parity-") as temp:
        control=Path(temp)/"stage"
        shutil.copytree(stage,control)
        legacy=evaluate(root,control,evidence,"trackeval-legacy-dtype-control",True)
        if scan_inputs(control)!=before:
            raise ValueError("legacy input changed")
    audit=patch_pinned(root)
    if set(git(root,"diff","--name-only").splitlines())!=set(FILES):
        raise ValueError("unexpected official source modifications")
    (evidence/"trackeval-numpy-compat.json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    modern=evaluate(root,stage,evidence,"trackeval-patched")
    if scan_inputs(stage)!=before:
        raise ValueError("patched input changed")
    record={"schema":"cognitum.cog06e.trackeval-parity.v1","upstream_commit":PIN,
            "source_sha":git(root.parent,"rev-parse","HEAD"),"input_sha256":before,
            "scope":"MOT17-02-FRCNN public-detection validation subset; DO_PREPROC=False",
            "dataset_files_archived":False,"scores":{}}
    for t in TRACKERS:
        first,values=legacy[t];second,new_values=modern[t]
        # Exact summary parity, not just the three headline metrics.
        if first!=second or values!=new_values:raise ValueError("metric parity failure: "+t)
        (evidence/("trackeval-"+t+"-summary.txt")).write_bytes(second)
        record["scores"][t]={"legacy":values,"patched":new_values,
                              "summary_sha256":sha256(second).hexdigest(),"byte_identical":True}
    (evidence/"trackeval-parity.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,indent=2),flush=True)

if __name__=="__main__":main()
