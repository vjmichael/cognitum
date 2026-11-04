"""C15 labeled temporal identity benchmark without ground-truth tracker leakage.

The evaluator receives ground-truth labels only AFTER tracker predictions are
produced. Supports deterministic IoU-only and optional descriptor challengers.
These are transparent local diagnostics, not official MOTChallenge HOTA/IDF1
or externally calibrated identity guarantees.
"""
from dataclasses import dataclass
from math import isfinite
from time import perf_counter
from .spatial_tracking import Track,Detection,update
from .spatial_appearance_core import Appearance,associate_appearance


@dataclass(frozen=True)
class EvalFrame:
    tracks:tuple[Track,...]
    detections:tuple[Detection,...]
    truth:tuple[tuple[str,str],...]  # stable track ID -> detection ID; evaluator only
    descriptors:tuple[Appearance,...] = ()


@dataclass(frozen=True)
class EvalReport:
    algorithm:str
    frames:int
    expected_matches:int
    correct_matches:int
    false_matches:int
    missed_matches:int
    ambiguous_frames:int
    recall:float
    precision:float
    wall_ms:float
    limitations:tuple[str,...]=(
        "synthetic_or_caller_supplied_labels_not_official_MOT",
        "no_truth_labels_passed_to_associator",
        "no_TrackEval_HOTA_or_official_IDF1",
        "not_camera_or_model_host_acceptance",
        "single_run_latency_not_memory_or_energy",
    )


def _truth(frame:EvalFrame):
    if (type(frame) is not EvalFrame or type(frame.truth) is not tuple
            or len(set(frame.truth))!=len(frame.truth)):
        raise ValueError("invalid evaluation frame")
    tracks={t.stable_id for t in frame.tracks}
    observations={d.detection_id for d in frame.detections}
    if (len({a for a,_ in frame.truth})!=len(frame.truth)
            or len({b for _,b in frame.truth})!=len(frame.truth)
            or any(a not in tracks or b not in observations for a,b in frame.truth)):
        raise ValueError("truth association is not one-to-one")
    return set(frame.truth)


def evaluate(frames:tuple[EvalFrame,...],*,algorithm:str)->EvalReport:
    if type(frames) is not tuple or not 1<=len(frames)<=256:
        raise ValueError("bounded labeled benchmark required")
    if algorithm not in ("geometry","appearance","capsule_descriptors"):
        raise ValueError("unsupported benchmark challenger")
    correct=false=miss=total=ambiguous=0
    started=perf_counter()
    for frame in frames:
        expected=_truth(frame)
        # Never pass expected/ground-truth associations into the matcher.
        if algorithm=="geometry":
            outcome=update(frame.tracks,frame.detections)
            candidate=set(outcome.assignments)
            if outcome.status!="ASSOCIATED":
                raise ValueError("geometry solver unavailable")
        else:
            # Caller labels external descriptors as ordinary independent
            # appearance data. Capsule model is NOT executed by this adapter.
            if not frame.descriptors:
                raise ValueError("no challenger descriptors supplied")
            outcome=associate_appearance(frame.tracks,frame.detections,frame.descriptors)
            if outcome.status not in ("ASSOCIATED","AMBIGUOUS"):
                raise ValueError("appearance solver unavailable")
            candidate=set(outcome.matches)
            ambiguous+=outcome.status=="AMBIGUOUS"
        matched=len(candidate&expected)
        correct+=matched
        false+=len(candidate-expected)
        miss+=len(expected-candidate)
        total+=len(expected)
    latency=(perf_counter()-started)*1000
    return EvalReport(algorithm,len(frames),total,correct,false,miss,ambiguous,
                      correct/(correct+miss) if correct+miss else 1.0,
                      correct/(correct+false) if correct+false else 1.0,
                      latency)


def compare(frames:tuple[EvalFrame,...],*,include_descriptors:bool=False):
    reference=evaluate(frames,algorithm="geometry")
    if not include_descriptors:
        return (reference,)
    return (reference,evaluate(frames,algorithm="appearance"))
