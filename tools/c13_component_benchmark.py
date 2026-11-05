"""C13 fixed genuine SciPy reference cases with measured wall/CPU latency.

Component-level benchmark only. No real-model Lu A/B, hidden probability
calibration claims, source authentication, or unmeasured hardware advantages.
"""
import json
import platform
from time import perf_counter,process_time
from cognitum.probability_bayes import BayesProblem,Observation,infer
from cognitum.probability_calibration import (
    BetaProblem,CalibrationProblem,beta_posterior,calibration_scores,
)


def measured(name,callback):
    begin_wall=perf_counter()
    begin_cpu=process_time()
    result=callback()
    return (name,result,round(1000*(perf_counter()-begin_wall),3),
            round(1000*(process_time()-begin_cpu),3))


def run():
    records=[]
    inputs=(
        ("rare_condition",lambda: infer(BayesProblem(
            ("yes","no"),(0.01,0.99),
            (Observation("positive",(0.9,0.05)),),
            "source_prior","source_test",
            ("conditionally_independent_observations",)))),
        ("impossible_evidence",lambda: infer(BayesProblem(
            ("a","b"),(0.4,0.6),
            (Observation("impossible",(0.0,0.0)),),
            "prior_source","likelihood_source",
            ("conditionally_independent_observations",)))),
        ("beta_posterior",lambda: beta_posterior(
            BetaProblem(80,20,1,1,0.95,"predefined_prior","observed_counts"))),
        ("perfect_forecasts",lambda: calibration_scores(
            CalibrationProblem((1.0,)*50+(0.0,)*50,
                               (1,)*50+(0,)*50,"heldout_labels"))),
        ("baseline_forecasts",lambda: calibration_scores(
            CalibrationProblem((0.5,)*100,(0,1)*50,"heldout_labels"))),
    )
    for name,callback in inputs:
        name,result,wall,cpu=measured(name,callback)
        if name=="impossible_evidence":
            if result.status!="IMPOSSIBLE_EVIDENCE":
                raise RuntimeError("expected impossible-evidence abstention")
        elif name=="rare_condition":
            if result.status!="OK" or not 0<result.posterior[0]<0.5:
                raise RuntimeError("base-rate inversion failed")
        elif name=="beta_posterior":
            if result.status!="OK" or not result.credible_lower<result.posterior_mean<result.credible_upper:
                raise RuntimeError("beta posterior invalid")
        elif not 0<=result.brier<=1:
            raise RuntimeError("calibration benchmark invalid")
        records.append({"case":name,"wall_ms":wall,"cpu_ms":cpu,
                        "status":getattr(result,"status","SCORED"),
                        "posterior":list(result.posterior) if hasattr(result,"posterior") else None,
                        "brier":getattr(result,"brier",None),
                        "ece":getattr(result,"expected_calibration_error",None)})
    print(json.dumps({"schema_version":1,
                      "benchmark":"C13_real_scipy_reference",
                      "platform":platform.platform(),
                      "results":records,
                      "limitations":["not_Lu_model_A_B",
                         "caller_supplied_sources_not_authenticated",
                         "single_run_times_not_energy_or_peak_memory",
                         "calibration_only_estimated_on_supplied_holdout",
                         "assumptions_not_proven"]},sort_keys=True,indent=2))


if __name__=="__main__":
    run()
