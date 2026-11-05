"""C17 real-library time-ordered heldout benchmarks, no synthetic metric claims.

Print actual numerical errors/timings for persistence, conventional Kalman,
trained Ridge AR, and HMM state-change reference. Contains no user data,
GPU, OS-worker permissions, memory replacement or real-world validation.
"""
from dataclasses import asdict
from math import sin
import json
import platform
from time import perf_counter
from cognitum.temporal_statespace import TemporalSample,TemporalSequence,TemporalModel
from cognitum.temporal_evaluation import evaluate_heldout
from cognitum.temporal_hidden import HiddenObservation,HiddenStateModel,infer_hidden


def samples():
    return TemporalSequence(
        ("temperature",),
        tuple(TemporalSample(
            1000*i,(20.+.04*i+1.5*sin(i*.12),),
            "synthetic_probe","sample_"+str(i)) for i in range(120)),
        "synthetic_reference","synthetic","unverified")


def run():
    seq=samples()
    model=TemporalModel("constant_velocity",.002,.08,1.,4.,60000)
    started=perf_counter()
    comparisons=evaluate_heldout(seq,model,train_count=80,
                                 include_learned=True,host_admitted_training=True)
    elapsed=(perf_counter()-started)*1000
    if {x.model for x in comparisons}!={"last_value","kalman","ridge_ar"}:
        raise RuntimeError("missing real trained temporal baselines")
    if any(not 0<=x.mae<100 or not 0<=x.rmse<100 or x.count!=40
           for x in comparisons):
        raise RuntimeError("invalid measured heldout forecast errors")
    hidden=HiddenStateModel(
        ("normal","changed"),(.9,.1),
        ((.98,.02),(.05,.95)),((.95,.05),(.1,.9)),
        1000,"synthetic_hmm_source")
    observations=tuple(HiddenObservation(i*1000,0 if i<60 else 1,
                                        "synthetic_probe","hmm_"+str(i))
                       for i in range(100))
    start=perf_counter()
    outcome=infer_hidden(hidden,observations)
    hmm_ms=(perf_counter()-start)*1000
    if outcome.status!="OK" or outcome.probable_states[-1]!="changed":
        raise RuntimeError("HMM regime change synthetic reference failed")
    output={
        "schema_version":1,"benchmark":"C17_synthetic_temporal_heldout_native",
        "platform":platform.platform(),"training_samples":80,"heldout_samples":40,
        "heldout_comparisons":[asdict(x) for x in comparisons],
        "total_training_plus_benchmark_wall_ms":round(elapsed,3),
        "hmm":{"status":outcome.status,
               "state_changes":sum(outcome.change_alerts),
               "wall_ms":round(hmm_ms,3)},
        "limitations":[
            "synthetic_heldout_not_real_user_temporal_task",
            "no_Lu_model_A_B_task_success_measured",
            "scikit_learn_Ridge_not_neural_SSM_or_Mamba",
            "train_test_split_strict_by_timestamp",
            "resource_numbers_CPU_wall_only_not_energy_GPU_or_peak_memory",
            "model_training_allowed_only_on_synthetic_fixture_in_CI",
            "reported_gaussian_coverage_not_empirically_validated_uncertainty",
        ],
    }
    print(json.dumps(output,sort_keys=True,indent=2))


if __name__=="__main__":
    run()
