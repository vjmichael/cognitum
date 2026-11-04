"""C17 bounded typed multichannel temporal evidence and classical filtering.

Pure CPU numerical reference using maintained NumPy/SciPy primitives.
This is not C07 canonical event state, Lu memory, host authorization, a
learned model, or a proof of sensor source authenticity.
"""
from dataclasses import dataclass
from math import isfinite, sqrt

MAX_SAMPLES=512
MAX_CHANNELS=4
MAX_TIME_MS=30*24*60*60*1000
MAX_GAP_MS=7*24*60*60*1000
MAX_FORECAST_MS=24*60*60*1000


@dataclass(frozen=True)
class TemporalSample:
    time_ms:int
    values:tuple[float|None,...]
    source_id:str
    observation_id:str


@dataclass(frozen=True)
class TemporalSequence:
    units:tuple[str,...]
    samples:tuple[TemporalSample,...]
    origin_id:str
    provenance_kind:str  # synthetic | measured | imported
    quality_declared:str # unverified | calibrated_externally


@dataclass(frozen=True)
class TemporalModel:
    kind:str              # local_level | constant_velocity
    process_variance_per_second:float
    measurement_variance:float
    prior_variance:float
    innovation_gate_sigma:float
    max_forecast_ms:int


@dataclass(frozen=True)
class TemporalPoint:
    time_ms:int
    posterior_mean:tuple[float,...]
    posterior_variance:tuple[float,...]
    normalized_innovation:tuple[float|None,...]
    missing:tuple[bool,...]
    anomalies:tuple[bool,...]


@dataclass(frozen=True)
class TemporalResult:
    status:str
    points:tuple[TemporalPoint,...]=()
    forecast_mean:tuple[float,...]=()
    forecast_variance:tuple[float,...]=()
    forecast_time_ms:int|None=None
    observed_count:int=0
    missing_count:int=0
    anomalies_count:int=0
    ood:bool=False
    limitations:tuple[str,...]=(
        "observations_caller_supplied_sources_not_authenticated",
        "kalman_uncertainty_is_assumed_model_variance_not_empirical_calibration",
        "measurement_error_model_not_certified",
        "not_canonical_event_state_or_host_authority",
    )


def _ident(s):
    return (type(s) is str and s.isascii() and s.isidentifier()
            and 1<=len(s)<=64)


def _finite(v):
    return type(v) in (float,int) and isfinite(v)


def validate(seq:TemporalSequence,model:TemporalModel):
    if type(seq) is not TemporalSequence or type(model) is not TemporalModel:
        raise ValueError("typed sequence/model required")
    if (type(seq.units) is not tuple or not 1<=len(seq.units)<=MAX_CHANNELS
            or any(not _ident(u) for u in seq.units)
            or len(set(seq.units))!=len(seq.units)
            or not _ident(seq.origin_id)
            or seq.provenance_kind not in ("synthetic","measured","imported")
            or seq.quality_declared not in ("unverified","calibrated_externally")
            or type(seq.samples) is not tuple
            or not 3<=len(seq.samples)<=MAX_SAMPLES):
        raise ValueError("invalid dimensioned temporal sequence")
    if (model.kind not in ("local_level","constant_velocity")
            or not _finite(model.process_variance_per_second)
            or not 0<=model.process_variance_per_second<=1e6
            or not _finite(model.measurement_variance)
            or not 1e-12<=model.measurement_variance<=1e6
            or not _finite(model.prior_variance)
            or not 0<=model.prior_variance<=1e9
            or not _finite(model.innovation_gate_sigma)
            or not 1<=model.innovation_gate_sigma<=10
            or type(model.max_forecast_ms) is not int
            or not 1<=model.max_forecast_ms<=MAX_FORECAST_MS):
        raise ValueError("invalid temporal state model")
    observed=0
    seen=set()
    last=None
    for sample in seq.samples:
        if (type(sample) is not TemporalSample
                or type(sample.time_ms) is not int
                or not 0<=sample.time_ms<=MAX_TIME_MS
                or (last is not None and not 0<sample.time_ms-last<=MAX_GAP_MS)
                or type(sample.values) is not tuple
                or len(sample.values)!=len(seq.units)
                or not _ident(sample.source_id) or not _ident(sample.observation_id)
                or (sample.source_id,sample.observation_id) in seen
                or any(v is not None and (not _finite(v) or abs(v)>1e9)
                       for v in sample.values)):
            raise ValueError("time order, source lineage or numeric bound invalid")
        seen.add((sample.source_id,sample.observation_id))
        observed+=sum(v is not None for v in sample.values)
        last=sample.time_ms
    if observed<len(seq.units):
        raise ValueError("insufficient measured values")
    # A filter must not search forward for its starting state: doing so
    # would leak future readings into earlier posterior estimates.
    if any(v is None for v in seq.samples[0].values):
        raise ValueError("initial sample must observe every channel; no lookahead")
    for column in range(len(seq.units)):
        if all(x.values[column] is None for x in seq.samples):
            raise ValueError("entire channel unobserved")
    return seq,model


def filter_sequence(seq:TemporalSequence,model:TemporalModel, *,
                    forecast_time_ms:int)->TemporalResult:
    validate(seq,model)
    if (type(forecast_time_ms) is not int
            or not seq.samples[-1].time_ms<=forecast_time_ms
            or forecast_time_ms-seq.samples[-1].time_ms>model.max_forecast_ms
            or forecast_time_ms>MAX_TIME_MS):
        raise ValueError("invalid future horizon")
    try:
        import numpy as np
        from scipy.linalg import eigvalsh
    except ImportError:
        return TemporalResult("UNSUPPORTED")
    n=len(seq.units)
    # Multiple independent typed channel filters; no silent cross-channel
    # coupling, covariance inference, dimension mixing or source fusion.
    state=np.zeros((n,2 if model.kind=="constant_velocity" else 1),dtype=float)
    cov=np.zeros((n,state.shape[1],state.shape[1]),dtype=float)
    first=seq.samples[0].time_ms
    for j in range(n):
        initial=next(s.values[j] for s in seq.samples if s.values[j] is not None)
        state[j,0]=initial
        cov[j]=np.eye(state.shape[1])*model.prior_variance
    points=[]
    missing=observed=anomalies=0
    previous=first
    for sample in seq.samples:
        dt=(sample.time_ms-previous)/1000.
        if model.kind=="constant_velocity":
            F=np.array(((1.,dt),(0.,1.)))
            Q=model.process_variance_per_second*np.array(
                ((dt**3/3,dt**2/2),(dt**2/2,dt)))
        else:
            F=np.eye(1)
            Q=np.array(((model.process_variance_per_second*dt,),))
        innovation=[]
        absent=[]
        alarms=[]
        for j,v in enumerate(sample.values):
            x=F@state[j]
            P=F@cov[j]@F.T+Q
            if v is None:
                missing+=1
                innovation.append(None);absent.append(True);alarms.append(False)
            else:
                observed+=1
                h=np.zeros((1,len(x)));h[0,0]=1
                residual=float(v-h@x)
                S=float((h@P@h.T)[0,0]+model.measurement_variance)
                if not isfinite(S) or S<=0:
                    return TemporalResult("UNKNOWN_NONPOSITIVE_COVARIANCE")
                z=residual/sqrt(S)
                anomaly=abs(z)>model.innovation_gate_sigma
                anomalies+=int(anomaly)
                innovation.append(z);absent.append(False);alarms.append(anomaly)
                # Large contradictions are surfaced and not silently
                # assimilated as trustworthy model-state revisions.
                if not anomaly:
                    gain=(P@h.T)/S
                    x=x+gain[:,0]*residual
                    identity=np.eye(len(x))
                    A=identity-gain@h
                    P=A@P@A.T+model.measurement_variance*(gain@gain.T)
            if not np.all(np.isfinite(x)) or not np.all(np.isfinite(P)):
                return TemporalResult("UNKNOWN_NUMERICAL_FAILURE")
            P=(P+P.T)/2
            if np.min(eigvalsh(P))<-1e-8 or np.max(np.abs(x))>1e10:
                return TemporalResult("UNKNOWN_UNSTABLE_STATE")
            state[j],cov[j]=x,P
        points.append(TemporalPoint(sample.time_ms,
            tuple(float(x[0]) for x in state),
            tuple(float(p[0,0]) for p in cov),
            tuple(innovation),tuple(absent),tuple(alarms)))
        previous=sample.time_ms
    dt=(forecast_time_ms-previous)/1000.
    forecast=[]
    variances=[]
    for x,P in zip(state,cov):
        if model.kind=="constant_velocity":
            F=np.array(((1.,dt),(0.,1.)))
            Q=model.process_variance_per_second*np.array(
                ((dt**3/3,dt**2/2),(dt**2/2,dt)))
        else:
            F=np.eye(1)
            Q=np.array(((model.process_variance_per_second*dt,),))
        x=F@x
        P=F@P@F.T+Q
        forecast.append(float(x[0]))
        variances.append(float(P[0,0]))
    if any(not isfinite(v) or v<0 or v>1e12 for v in variances):
        return TemporalResult("UNKNOWN_FORECAST_UNSTABLE")
    return TemporalResult("OK",tuple(points),tuple(forecast),
        tuple(variances),forecast_time_ms,observed,missing,anomalies,
        ood=(anomalies>0 or forecast_time_ms-previous>MAX_FORECAST_MS//2))
