"""C17 strictly chronological held-out temporal prediction evaluator.

No training/evaluation overlap. Explicit last-value baseline, conventional
Kalman one-step filter and opt-in trained Ridge autoregression. Metrics are
only for supplied future labels; no claims of calibrated confidence or
real-world outcomes from synthetic data.
"""
from dataclasses import dataclass
from math import isfinite,sqrt
from time import perf_counter

from .temporal_statespace import TemporalSequence,TemporalModel,filter_sequence,validate
from .temporal_learned import train_ridge,forecast


@dataclass(frozen=True)
class HoldoutMetric:
    model:str
    count:int
    mae:float
    rmse:float
    mean_wall_ms:float
    forecast_coverage_90:float|None
    ood_count:int
    limitations:tuple[str,...]=(
        "one_step_teacher_forced_metrics_not_recursive_future_accuracy",
        "heldout_labels_caller_supplied_not_source_authenticated",
        "90pct_coverage_uses_assumed_gaussian_not_calibrated_interval",
        "host_worker_energy_and_peak_memory_not_measured",
    )


def evaluate_heldout(seq:TemporalSequence,model:TemporalModel, *,
                     train_count:int,include_learned:bool=False,
                     host_admitted_training:bool=False)->tuple[HoldoutMetric,...]:
    validate(seq,model)
    if (len(seq.units)!=1 or type(train_count) is not int
            or not 16<=train_count<=len(seq.samples)-8):
        raise ValueError("bounded single-channel train/test split required")
    dt=seq.samples[1].time_ms-seq.samples[0].time_ms
    if any(b.time_ms-a.time_ms!=dt for a,b in zip(seq.samples,seq.samples[1:])):
        raise ValueError("heldout reference requires regular sample spacing")
    if any(v is None for s in seq.samples for v in s.values):
        raise ValueError("heldout evaluation must have actual future labels")
    if include_learned and not host_admitted_training:
        raise PermissionError("host must admit learned temporal training")
    artifact=(train_ridge(seq,train_count=train_count,
                          host_admitted=host_admitted_training)
              if include_learned else None)
    # Each prediction uses history strictly before the target index. Hidden
    # future labels are never injected into any model at prediction time.
    losses={"last_value":[],"kalman":[]}
    if artifact is not None:
        losses["ridge_ar"]=[]
    timings={k:[] for k in losses}
    cover={k:[] for k in losses}
    ood={k:0 for k in losses}
    for idx in range(train_count,len(seq.samples)):
        prefix=TemporalSequence(seq.units,seq.samples[:idx],seq.origin_id,
                                seq.provenance_kind,seq.quality_declared)
        observed=float(seq.samples[idx].values[0])
        predictions={}
        wall=perf_counter()
        predictions["last_value"]=(float(seq.samples[idx-1].values[0]),None,False)
        timings["last_value"].append((perf_counter()-wall)*1000)
        wall=perf_counter()
        kr=filter_sequence(prefix,model,forecast_time_ms=seq.samples[idx].time_ms)
        if kr.status!="OK":
            raise RuntimeError("Kalman holdout benchmark failed: "+kr.status)
        predictions["kalman"]=(kr.forecast_mean[0],kr.forecast_variance[0],kr.ood)
        timings["kalman"].append((perf_counter()-wall)*1000)
        if artifact is not None:
            wall=perf_counter()
            ar=forecast(artifact,prefix,steps=1)
            if ar.status not in ("OK","OOD_ABSTAIN"):
                raise RuntimeError("learned model forecast failed: "+ar.status)
            predictions["ridge_ar"]=(ar.means[0][0],ar.variances[0][0],ar.ood)
            timings["ridge_ar"].append((perf_counter()-wall)*1000)
        for name,(estimate,variance,is_ood) in predictions.items():
            if not isfinite(estimate):
                raise RuntimeError("nonfinite temporal prediction")
            errors=estimate-observed
            losses[name].append(errors)
            ood[name]+=int(is_ood)
            if variance is not None:
                if not isfinite(variance) or variance<0:
                    raise RuntimeError("invalid forecast variance")
                cover[name].append(abs(errors)<=1.6448536269514722*sqrt(variance))
    return tuple(HoldoutMetric(
        name,len(errors),
        sum(abs(x) for x in errors)/len(errors),
        sqrt(sum(x*x for x in errors)/len(errors)),
        sum(timings[name])/len(errors),
        (sum(cover[name])/len(cover[name]) if cover[name] else None),
        ood[name],
    ) for name,errors in losses.items())
