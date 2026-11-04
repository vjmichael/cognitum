"""C17 opt-in trained autoregressive state model using mature scikit-learn Ridge.

A small transparent learned temporal baseline, not a Mamba/S4 neural SSM.
Training is explicitly gated by trusted host admission; the Boolean here is
only an integration seam, NOT proof of Lu authorization or user consent.
No disk, network, account traces, checkpoint loading from arbitrary paths,
or mutation of Lu's base transformer or canonical memory.
"""
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite,sqrt
import json

from .temporal_statespace import TemporalSequence,TemporalSample,MAX_SAMPLES,_ident

MAX_LAGS=8


@dataclass(frozen=True)
class StateArtifact:
    schema_version:int
    architecture:str
    source_id:str
    training_sha256:str
    first_time_ms:int
    last_training_time_ms:int
    step_ms:int
    lags:int
    units:tuple[str,...]
    coefficients:tuple[tuple[float,...],...]
    intercepts:tuple[float,...]
    center:tuple[float,...]
    scale:tuple[float,...]
    residual_variance:tuple[float,...]
    minimum:tuple[float,...]
    maximum:tuple[float,...]
    training_count:int
    artifact_sha256:str


@dataclass(frozen=True)
class LearnedForecast:
    status:str
    means:tuple[tuple[float,...],...]=()
    variances:tuple[tuple[float,...],...]=()
    steps:int=0
    ood:bool=False
    limitations:tuple[str,...]=(
        "scikit_learn_ridge_autoregressive_challenger_not_neural_ssm",
        "residual_variance_not_calibrated_predictive_interval",
        "iid_weak_stationarity_assumed_not_verified",
        "artifact_checksum_not_trusted_signature",
        "training_requires_independent_host_consent_and_provenance",
    )


def _canonical(payload)->bytes:
    return json.dumps(payload,sort_keys=True,separators=(",",":"),
                      allow_nan=False).encode("utf-8")


def _fields(a:StateArtifact):
    return {name:getattr(a,name) for name in StateArtifact.__dataclass_fields__
            if name!="artifact_sha256"}


def verify_artifact(artifact:StateArtifact)->StateArtifact:
    if type(artifact) is not StateArtifact or artifact.schema_version!=1:
        raise ValueError("invalid temporal checkpoint schema")
    if (artifact.architecture!="sklearn_ridge_ar_v1"
            or not _ident(artifact.source_id)
            or type(artifact.training_sha256) is not str
            or len(artifact.training_sha256)!=64
            or type(artifact.artifact_sha256) is not str
            or len(artifact.artifact_sha256)!=64
            or any(c not in "0123456789abcdef" for c in
                   artifact.training_sha256+artifact.artifact_sha256)
            or type(artifact.lags) is not int or not 1<=artifact.lags<=MAX_LAGS
            or type(artifact.training_count) is not int
            or not 2*artifact.lags+8<=artifact.training_count<=MAX_SAMPLES
            or type(artifact.step_ms) is not int or not 1<=artifact.step_ms<=86400000
            or type(artifact.units) is not tuple
            or not 1<=len(artifact.units)<=4
            or any(not _ident(u) for u in artifact.units)):
        raise ValueError("invalid temporal model artifact metadata")
    n=len(artifact.units)
    if (len(artifact.coefficients)!=n or any(len(row)!=artifact.lags
                                             for row in artifact.coefficients)
            or any(len(x)!=n for x in (artifact.intercepts,artifact.center,
                                       artifact.scale,artifact.residual_variance,
                                       artifact.minimum,artifact.maximum))):
        raise ValueError("invalid temporal checkpoint dimensions")
    numeric=[v for rows in artifact.coefficients for v in rows]
    numeric+=list(artifact.intercepts+artifact.center+artifact.scale+
                  artifact.residual_variance+artifact.minimum+artifact.maximum)
    if (any(type(x) not in (int,float) or not isfinite(x) or abs(x)>1e12
            for x in numeric)
            or any(x<=0 for x in artifact.scale)
            or any(x<0 for x in artifact.residual_variance)
            or any(lo>hi for lo,hi in zip(artifact.minimum,artifact.maximum))):
        raise ValueError("invalid artifact numeric coefficients")
    if sha256(_canonical(_fields(artifact))).hexdigest()!=artifact.artifact_sha256:
        raise ValueError("temporal checkpoint checksum mismatch")
    return artifact


def _regular(seq:TemporalSequence):
    if type(seq) is not TemporalSequence or type(seq.samples) is not tuple:
        raise ValueError("typed sequence required")
    from .temporal_statespace import TemporalModel,validate
    validate(seq,TemporalModel("local_level",0,1,1,3,1))
    if any(v is None for sample in seq.samples for v in sample.values):
        raise ValueError("learned AR refuses missing values; use Kalman baseline")
    dt=seq.samples[1].time_ms-seq.samples[0].time_ms
    if dt<=0 or any(b.time_ms-a.time_ms!=dt
                    for a,b in zip(seq.samples,seq.samples[1:])):
        raise ValueError("learned AR requires regular timestamps")
    return dt


def train_ridge(seq:TemporalSequence,*,train_count:int,lags:int=3,
                host_admitted:bool=False)->StateArtifact:
    if host_admitted is not True:
        raise PermissionError("trusted host must admit consented training")
    step=_regular(seq)
    if (type(train_count) is not int or type(lags) is not int
            or not 1<=lags<=MAX_LAGS
            or not 2*lags+8<=train_count<len(seq.samples)-3):
        raise ValueError("strict time-ordered train/heldout split required")
    try:
        import numpy as np
        from sklearn.linear_model import Ridge
    except ImportError as exc:
        raise RuntimeError("scikit_learn_temporal_backend_unavailable") from exc
    training=seq.samples[:train_count]
    n=len(seq.units)
    coefs=[];intercepts=[];centers=[];scales=[];variances=[];mins=[];maxs=[]
    for j in range(n):
        y=np.asarray([sample.values[j] for sample in training],dtype=float)
        center=float(y.mean());scale=max(float(y.std()),1e-9)
        normalized=(y-center)/scale
        features=np.asarray([normalized[i-lags:i][::-1]
                             for i in range(lags,train_count)])
        targets=np.asarray([normalized[i] for i in range(lags,train_count)])
        regression=Ridge(alpha=1.0,fit_intercept=True,solver="cholesky")
        regression.fit(features,targets)
        predicted=regression.predict(features)
        error=(targets-predicted)*scale
        coefs.append(tuple(float(x) for x in regression.coef_))
        intercepts.append(float(regression.intercept_))
        centers.append(center);scales.append(scale)
        variances.append(max(float(np.mean(error**2)),1e-12))
        mins.append(float(y.min()));maxs.append(float(y.max()))
    material={
        "schema_version":1,"architecture":"sklearn_ridge_ar_v1",
        "source_id":seq.origin_id,
        "training_sha256":sha256(_canonical([
            (s.time_ms,s.values,s.source_id,s.observation_id)
            for s in training])).hexdigest(),
        "first_time_ms":training[0].time_ms,
        "last_training_time_ms":training[-1].time_ms,
        "step_ms":step,"lags":lags,"units":seq.units,
        "coefficients":tuple(coefs),"intercepts":tuple(intercepts),
        "center":tuple(centers),"scale":tuple(scales),
        "residual_variance":tuple(variances),"minimum":tuple(mins),
        "maximum":tuple(maxs),"training_count":train_count,
    }
    art=StateArtifact(**material,artifact_sha256=sha256(_canonical(material)).hexdigest())
    return verify_artifact(art)


def forecast(artifact:StateArtifact,history:TemporalSequence,*,
             steps:int)->LearnedForecast:
    verify_artifact(artifact)
    step=_regular(history)
    if (type(steps) is not int or not 1<=steps<=64
            or artifact.source_id!=history.origin_id
            or artifact.units!=history.units or step!=artifact.step_ms
            or history.samples[0].time_ms!=artifact.first_time_ms
            or len(history.samples)<artifact.training_count
            or history.samples[artifact.training_count-1].time_ms!=artifact.last_training_time_ms):
        raise ValueError("out-of-domain learned prediction request")
    candidate=sha256(_canonical([
        (s.time_ms,s.values,s.source_id,s.observation_id)
        for s in history.samples[:artifact.training_count]])).hexdigest()
    if candidate!=artifact.training_sha256:
        raise ValueError("training provenance mismatch or overwritten history")
    histories=[[float(s.values[j]) for s in history.samples]
               for j in range(len(artifact.units))]
    ood=False
    predicted=[]
    predicted_var=[]
    for horizon in range(steps):
        row=[];row_var=[]
        for j,h in enumerate(histories):
            if any(v<artifact.minimum[j]-3*artifact.scale[j]
                   or v>artifact.maximum[j]+3*artifact.scale[j]
                   for v in h[-artifact.lags:]):
                ood=True
            features=[(v-artifact.center[j])/artifact.scale[j]
                      for v in h[-artifact.lags:][::-1]]
            outcome=artifact.intercepts[j]+sum(a*b for a,b in
                zip(artifact.coefficients[j],features))
            value=outcome*artifact.scale[j]+artifact.center[j]
            if not isfinite(value) or abs(value)>1e12:
                return LearnedForecast("UNKNOWN_OOD_EXPLOSION",steps=horizon,ood=True)
            row.append(value)
            # Multi-step residual accumulation is a warning heuristic,
            # not a calibrated predictive distribution.
            row_var.append(artifact.residual_variance[j]*(horizon+1))
            h.append(value)
        predicted.append(tuple(row))
        predicted_var.append(tuple(row_var))
    return LearnedForecast("OOD_ABSTAIN" if ood else "OK",
                           tuple(predicted),tuple(predicted_var),steps,ood)
