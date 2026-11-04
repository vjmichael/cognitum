"""C15 opt-in external official TrackEval runner for host-staged MOT data.

No automatic downloads or source trust. Executes only a trusted/pinned external
TrackEval checkout on host-owned paths in an OS-confined worker; this Python
adapter is NOT the isolation boundary and must never be exposed as a model
callable filesystem/shell tool.
"""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
import subprocess
import sys

MAX_INPUT_BYTES=80_000_000
SAFE=re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
METRICS=("HOTA","MOTA","IDF1")


@dataclass(frozen=True)
class MOTManifest:
    data_root:Path
    trackeval_root:Path
    benchmark:str
    split:str
    sequence:str
    tracker:str
    gt_sha256:str
    prediction_sha256:str
    seqmap_sha256:str
    runner_sha256:str
    timeout_seconds:int=120


@dataclass(frozen=True)
class OfficialEvaluation:
    status:str
    scores:tuple[tuple[str,float],...]=()
    runner_sha256:str=""
    input_sha256:tuple[str,str]=()
    limitations:tuple[str,...]=(
        "dataset_license_and_source_attestation_not_checked",
        "tracker_pred_independence_not_cryptographically_proven",
        "local_external_binary_execution_requires_OS_worker",
        "no_Lu_model_A_B_or_real_task_end_to_end_claim",
    )


def _digest_file(path:Path)->str:
    if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_INPUT_BYTES:
        raise ValueError("missing, symlinked or oversized external evaluation file")
    h=sha256()
    with path.open("rb") as file:
        while block:=file.read(1024*1024):
            h.update(block)
    return h.hexdigest()


def _validate(m:MOTManifest):
    if type(m) is not MOTManifest or any(not isinstance(v,Path)
                                         or not v.is_absolute()
                                         for v in (m.data_root,m.trackeval_root)):
        raise ValueError("host-controlled absolute paths required")
    if any(not SAFE.fullmatch(v or "") for v in (m.benchmark,m.split,m.sequence,m.tracker)):
        raise ValueError("invalid external evaluation namespace")
    if m.benchmark not in ("MOT15","MOT16","MOT17","MOT20") or m.split not in ("train","test"):
        raise ValueError("unsupported MOT evaluation domain")
    for key in (m.gt_sha256,m.prediction_sha256,m.seqmap_sha256,m.runner_sha256):
        if type(key) is not str or len(key)!=64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("pinned source/runner digests required")
    if type(m.timeout_seconds) is not int or not 1<=m.timeout_seconds<=3600:
        raise ValueError("invalid external timeout")
    target=m.benchmark+"-"+m.split
    gt=m.data_root/"gt"/target/m.sequence/"gt"/"gt.txt"
    pred=m.data_root/"trackers"/target/m.tracker/"data"/(m.sequence+".txt")
    seqmap=m.data_root/"gt"/"seqmaps"/(target+".txt")
    runner=m.trackeval_root/"scripts"/"run_mot_challenge.py"
    if (_digest_file(gt)!=m.gt_sha256
            or _digest_file(pred)!=m.prediction_sha256
            or _digest_file(seqmap)!=m.seqmap_sha256
            or _digest_file(runner)!=m.runner_sha256):
        raise ValueError("source or trusted TrackEval runner digest mismatch")
    if m.gt_sha256==m.prediction_sha256:
        raise ValueError("prediction identical to ground truth: possible GT leakage")
    if not (m.trackeval_root/"trackeval"/"metrics"/"hota.py").is_file():
        raise ValueError("unavailable native TrackEval source")
    return gt,pred,seqmap,runner


def _summary(file:Path):
    if not file.is_file() or file.is_symlink() or file.stat().st_size>65536:
        raise ValueError("missing or oversized external evaluator summary")
    lines=[line.strip().split() for line in file.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    if len(lines)<2 or len(lines[0])!=len(lines[1]):
        raise ValueError("invalid TrackEval summary")
    scores={}
    for label,value in zip(lines[0],lines[1]):
        if label in METRICS:
            number=float(value)
            if not isfinite(number):
                raise ValueError("nonfinite official metric")
            scores[label]=number
    if set(scores)!=set(METRICS):
        raise ValueError("missing official evaluation metrics")
    return tuple(sorted(scores.items()))


def run(m:MOTManifest)->OfficialEvaluation:
    try:
        _,_,seqmap,runner=_validate(m)
    except (OSError,ValueError,UnicodeError):
        return OfficialEvaluation("BLOCKED_INPUT_OR_SOURCE_INTEGRITY")
    target=m.benchmark+"-"+m.split
    summary=m.data_root/"trackers"/target/m.tracker/"pedestrian_summary.txt"
    if summary.exists():
        return OfficialEvaluation("BLOCKED_STALE_SUMMARY")
    command=[sys.executable,str(runner),
             "--GT_FOLDER",str(m.data_root/"gt"),
             "--TRACKERS_FOLDER",str(m.data_root/"trackers"),
             "--BENCHMARK",m.benchmark,"--SPLIT_TO_EVAL",m.split,
             "--SEQMAP_FILE",str(seqmap),
             "--TRACKERS_TO_EVAL",m.tracker,
             "--CLASSES_TO_EVAL","pedestrian",
             "--METRICS","HOTA","CLEAR","Identity",
             "--DO_PREPROC","False","--USE_PARALLEL","False",
             "--PLOT_CURVES","False","--PRINT_CONFIG","False",
             "--TIME_PROGRESS","False"]
    try:
        result=subprocess.run(command,cwd=str(m.trackeval_root),
                              stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=m.timeout_seconds,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return OfficialEvaluation("ENGINE_UNAVAILABLE_OR_TIMEOUT")
    if result.returncode!=0 or len(result.stdout)>2_000_000 or len(result.stderr)>2_000_000:
        return OfficialEvaluation("ENGINE_FAILED")
    try:
        scores=_summary(summary)
    except (OSError,ValueError,UnicodeError):
        return OfficialEvaluation("ENGINE_RESULT_NOT_VERIFIED")
    return OfficialEvaluation("TRACK_EVAL_EXECUTED_SOURCE_UNATTESTED",scores,
                              m.runner_sha256,(m.gt_sha256,m.prediction_sha256))
