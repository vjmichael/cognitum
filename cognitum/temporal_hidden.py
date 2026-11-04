"""C17 categorical hidden-state temporal inference via SciPy logsumexp.

Caller-declared HMM transition/emission probabilities, not self-trained facts,
semantic contradictions, or authenticated sensor states. Supports missing
emissions, strict chronology, and posterior mode/change probabilities.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class HiddenObservation:
    time_ms:int
    category:int|None
    source_id:str
    observation_id:str


@dataclass(frozen=True)
class HiddenStateModel:
    state_names:tuple[str,...]
    prior:tuple[float,...]
    transitions:tuple[tuple[float,...],...]
    emissions:tuple[tuple[float,...],...]
    sampling_interval_ms:int
    model_source:str


@dataclass(frozen=True)
class HiddenInference:
    status:str
    posteriors:tuple[tuple[float,...],...]=()
    probable_states:tuple[str,...]=()
    change_alerts:tuple[bool,...]=()
    total_log_likelihood:float|None=None
    limitations:tuple[str,...]=(
        "caller_declared_HMM_not_trained_or_empirically_calibrated",
        "state_labels_not_semantic_event_truth",
        "conditional_markov_and_emission_assumptions_unverified",
        "observation_sources_not_authenticated",
    )


def _identifier(v):
    return type(v) is str and v.isascii() and v.isidentifier() and 1<=len(v)<=48


def _distribution(xs,count):
    return (type(xs) is tuple and len(xs)==count
            and all(type(x) in (int,float) and isfinite(x) and 0<=x<=1 for x in xs)
            and abs(sum(xs)-1)<1e-10)


def validate_hmm(model:HiddenStateModel,obs:tuple[HiddenObservation,...]):
    if (type(model) is not HiddenStateModel or type(obs) is not tuple
            or not 3<=len(obs)<=512 or type(model.state_names) is not tuple
            or not 2<=len(model.state_names)<=8
            or any(not _identifier(x) for x in model.state_names)
            or len(set(model.state_names))!=len(model.state_names)
            or not _identifier(model.model_source)
            or type(model.sampling_interval_ms) is not int
            or not 1<=model.sampling_interval_ms<=86400000):
        raise ValueError("bounded hidden-state model required")
    n=len(model.state_names)
    if (not _distribution(model.prior,n)
            or type(model.transitions) is not tuple or len(model.transitions)!=n
            or any(not _distribution(row,n) for row in model.transitions)
            or type(model.emissions) is not tuple or len(model.emissions)!=n):
        raise ValueError("invalid HMM probability transition/prior")
    categories=len(model.emissions[0])
    if (not 2<=categories<=16
            or any(not _distribution(row,categories) for row in model.emissions)):
        raise ValueError("invalid HMM emission matrix")
    seen=set()
    previous=None
    observed=0
    for item in obs:
        if (type(item) is not HiddenObservation
                or type(item.time_ms) is not int or item.time_ms<0
                or item.time_ms>30*86400000
                or (previous is not None and item.time_ms-previous!=model.sampling_interval_ms)
                or item.category is not None and (type(item.category) is not int
                         or not 0<=item.category<categories)
                or not _identifier(item.source_id)
                or not _identifier(item.observation_id)
                or (item.source_id,item.observation_id) in seen):
            raise ValueError("invalid HMM chronological observation")
        observed+=item.category is not None
        seen.add((item.source_id,item.observation_id))
        previous=item.time_ms
    if observed<2:
        raise ValueError("insufficient hidden-state observations")
    return model


def infer_hidden(model:HiddenStateModel,observations:tuple[HiddenObservation,...],
                 *,alert_probability:float=.65)->HiddenInference:
    validate_hmm(model,observations)
    if (type(alert_probability) not in (int,float) or not isfinite(alert_probability)
            or not .5<=alert_probability<=.999):
        raise ValueError("invalid hidden-state alert threshold")
    try:
        import numpy as np
        from scipy.special import logsumexp
    except ImportError:
        return HiddenInference("UNSUPPORTED")
    n=len(model.state_names)
    with np.errstate(divide="ignore"):
        log_t=np.log(np.asarray(model.transitions,dtype=float))
        log_e=np.log(np.asarray(model.emissions,dtype=float))
        log_p=np.log(np.asarray(model.prior,dtype=float))
    results=[];names=[];alerts=[]
    overall=0.
    prior=log_p
    previous_mode=None
    for index,observation in enumerate(observations):
        if index:
            prior=logsumexp(prior[:,None]+log_t,axis=0)
        posterior=prior+(log_e[:,observation.category]
                         if observation.category is not None else 0.)
        z=float(logsumexp(posterior))
        if z==float("-inf"):
            return HiddenInference("IMPOSSIBLE_EVIDENCE")
        overall+=z
        posterior=posterior-z
        probabilities=np.exp(posterior)
        mode=int(np.argmax(probabilities))
        change=(previous_mode is not None and mode!=previous_mode
                and probabilities[mode]>=alert_probability)
        results.append(tuple(float(v) for v in probabilities))
        names.append(model.state_names[mode])
        alerts.append(bool(change))
        previous_mode=mode
        prior=posterior
    return HiddenInference("OK",tuple(results),tuple(names),
                           tuple(alerts),overall)
