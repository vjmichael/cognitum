"""C13 discrete Bayesian updates using maintained SciPy numerical primitives.

Only caller-declared finite hypotheses and conditionally independent binary
observations. No causal claims, inferred independence, generated code, Lu tool
registration, or calibration claim without outcome data.
"""
from dataclasses import dataclass
from math import isfinite, log, exp

MAX_HYPOTHESES=16
MAX_OBSERVATIONS=32


@dataclass(frozen=True)
class Observation:
    name: str
    likelihood_by_hypothesis: tuple[float,...]
    observed: bool = True


@dataclass(frozen=True)
class BayesProblem:
    hypotheses: tuple[str,...]
    prior: tuple[float,...]
    observations: tuple[Observation,...]
    prior_source: str
    likelihood_source: str
    assumptions: tuple[str,...]


@dataclass(frozen=True)
class BayesResult:
    status: str
    posterior: tuple[float,...] = ()
    evidence_probability: float | None = None
    log_evidence: float | None = None
    method: str = "scipy_logsumexp"
    limitations: tuple[str,...] = (
        "priors_likelihoods_caller_supplied",
        "conditional_independence_declared_not_verified",
        "association_not_causation",
        "not_empirically_calibrated",
    )


def _ident(value):
    return (type(value) is str and value.isascii()
            and value.isidentifier() and 1<=len(value)<=48)


def validate(p: BayesProblem):
    if type(p) is not BayesProblem:
        raise ValueError("typed Bayesian problem required")
    if (type(p.hypotheses) is not tuple or not 2<=len(p.hypotheses)<=MAX_HYPOTHESES
            or len(set(p.hypotheses))!=len(p.hypotheses)
            or any(not _ident(h) for h in p.hypotheses)):
        raise ValueError("invalid hypothesis set")
    if type(p.prior) is not tuple or len(p.prior)!=len(p.hypotheses):
        raise ValueError("prior dimension mismatch")
    if any(type(x) not in (float,int) or not isfinite(x) or not 0<=x<=1 for x in p.prior):
        raise ValueError("invalid prior probability")
    if abs(sum(p.prior)-1)>1e-10:
        raise ValueError("prior distribution must normalize")
    if (not _ident(p.prior_source) or not _ident(p.likelihood_source)
            or type(p.assumptions) is not tuple
            or p.assumptions != ("conditionally_independent_observations",)):
        raise ValueError("explicit provenance and assumption required")
    if (type(p.observations) is not tuple or not 1<=len(p.observations)<=MAX_OBSERVATIONS):
        raise ValueError("observation count out of bounds")
    seen=set()
    for obs in p.observations:
        if (type(obs) is not Observation or not _ident(obs.name) or obs.name in seen
                or type(obs.observed) is not bool
                or type(obs.likelihood_by_hypothesis) is not tuple
                or len(obs.likelihood_by_hypothesis)!=len(p.hypotheses)
                or any(type(x) not in (int,float) or not isfinite(x) or not 0<=x<=1
                       for x in obs.likelihood_by_hypothesis)):
            raise ValueError("invalid/duplicate observation or likelihood")
        seen.add(obs.name)
    return p


def infer(p: BayesProblem) -> BayesResult:
    validate(p)
    try:
        from scipy.special import logsumexp
    except ImportError:
        return BayesResult("UNSUPPORTED",method="scipy_unavailable")
    weights=[]
    for i,prior in enumerate(p.prior):
        score=log(prior) if prior>0 else float("-inf")
        for obs in p.observations:
            likelihood=obs.likelihood_by_hypothesis[i]
            prob=likelihood if obs.observed else 1-likelihood
            if prob==0:
                score=float("-inf")
                break
            score+=log(prob)
        weights.append(score)
    norm=float(logsumexp(weights))
    if norm==float("-inf"):
        return BayesResult("IMPOSSIBLE_EVIDENCE",
                           method="scipy_logsumexp",
                           limitations=("observations_zero_probability_under_all_hypotheses",
                                        "do_not_invent_posterior"))
    posterior=tuple(exp(w-norm) for w in weights)
    if any(not isfinite(v) for v in posterior) or abs(sum(posterior)-1)>1e-10:
        return BayesResult("NUMERICAL_FAILURE")
    evidence=exp(norm) if norm>-745 else 0.0
    return BayesResult("OK",posterior,evidence,norm)
