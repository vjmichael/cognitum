"""C15 reproducible matched baselines on frozen labeled temporal fixtures.

Runs actual SciPy geometry+appearance assignment. Ground truth is only
accessible to the evaluator after each tracker has returned predictions.
Capsule-model challenger is an opt-in descriptor interface, not a pretrained
capsule network or evidence of learned accuracy.
"""
import json
from time import perf_counter
from cognitum.spatial_tracking import Track,Detection
from cognitum.spatial_appearance_core import Appearance
from cognitum.spatial_identity_eval import EvalFrame,evaluate

DIGEST="e"*64

def feature(identity,vector,frame):
    return Appearance(identity,vector,"frozen_descriptor_reference",DIGEST,
                      "synthetic_fixture","obs_"+identity,frame)


def fixtures():
    frames=[]
    for index in range(1,9):
        # Two objects on opposite sides of the frame, then crossing. Spatial
        # proximity grows ambiguous at the crossing while identity descriptors
        # distinguish the hypothetical tracks.
        a_x=float(index*4)
        b_x=float(40-index*4)
        tracks=(Track("left_origin",a_x-1,0,9,9),
                Track("right_origin",b_x+1,0,9,9))
        detections=(Detection("det_a",a_x,0,9,9,"test_camera"),
                    Detection("det_b",b_x,0,9,9,"test_camera"))
        truth=(("left_origin","det_a"),("right_origin","det_b"))
        desc=(feature("left_origin",(1.,0.,0.),index),
              feature("right_origin",(0.,1.,0.),index),
              feature("det_a",(0.99,0.01,0.),index),
              feature("det_b",(0.01,0.99,0.),index))
        frames.append(EvalFrame(tracks,detections,truth,desc))
    return tuple(frames)


def run():
    frames=fixtures()
    records=[]
    for engine in ("geometry","appearance","capsule_descriptors"):
        t=perf_counter()
        report=evaluate(frames,algorithm=engine)
        elapsed_ms=round((perf_counter()-t)*1000,3)
        if (report.expected_matches!=16 or report.correct_matches<0
                or report.false_matches<0 or report.missed_matches<0):
            raise RuntimeError("C15 evaluation invalid")
        if engine!="geometry" and report.correct_matches!=16:
            raise RuntimeError("C15 frozen appearance comparator regression")
        records.append(dict(algorithm=engine,frames=report.frames,
                            ground_truth_matches=report.expected_matches,
                            correct_matches=report.correct_matches,
                            missed_matches=report.missed_matches,
                            false_matches=report.false_matches,
                            precision=report.precision,recall=report.recall,
                            ambiguous_frames=report.ambiguous_frames,
                            measured_ms=elapsed_ms))
    print(json.dumps({
        "schema_version":1,
        "benchmark":"C15_SYNTHETIC_MATCHED_IDENTITY_BASELINES",
        "results":records,
        "limitations":[
            "all_descriptors_predeclared_synthetic_not_captured_pixels",
            "capsule_descriptors_uses_supplied_vectors_not_a_capsule_network",
            "not_official_MOT17_TAO_BDD100K_TrackEval",
            "no_camera_or_dataset_provenance_authentication",
            "no_GPU_VRAM_measurement_CPU_reference_only",
            "no_Lu_model_A_B_or_real_data_accuracy_claim",
        ],
    },sort_keys=True,indent=2))


if __name__=="__main__":
    run()
