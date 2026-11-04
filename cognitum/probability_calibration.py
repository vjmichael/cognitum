"""C13 standard-library scoring rules and SciPy beta credible intervals.

Credible intervals are posterior model intervals, NEVER frequentist coverage
or validation calibration. Scoring needs observed held-out labels.
"""
from dataclasses import dataclass
from math import isfinite, log


@dataclass(frozen=True)
class BetaProblem:
    successes: int
    failures: int
    alpha_prior: float
    beta_prior: float
    credibility: float
    prior_source: str
    data_source: str


@dataclass(frozen=True)
class BetaResult:
    status: str
    posterior_mean: float | None = None
    credible_lower: float | None = None
    credible_upper: float | None = None
    alpha_posterior: float | None = None
    beta_posterior: float | None = None
    limitations: tuple[str,...] = (
        "iid_bernoulli_trials_assumed_not_verified",
        "credible_interval_not_frequentist_confidence",
        "data_source_not_authenticated",
        "empirical_calibration_not_established",
    )


@dataclass(frozen=True)
class CalibrationProblem:
    probabilities: tuple[float,...]
    labels: tuple[int,...]
    source: str
    bins: int = 10


@dataclass(frozen=True)
class CalibrationResult:
    brier: float
    log_loss: float
    expected_calibration_error: float
    count: int
    bins_with_data: int
    limitations: tuple[str,...] = (
        "empirical_scores_only_for_supplied_labeled_sample",
        "not_out_of_distribution_calibration",
        "source_and_holdout_not_verified",
    )


def _source(s):
    return type(s) is str and s.isascii() and s.isidentifier() and 1<=len(s)<=48


def beta_posterior(p: BetaProblem) -> BetaResult:
    if (type(p) is not BetaProblem or type(p.successes) is not int
            or type(p.failures) is not int or min(p.successes,p.failures)<0
            or p.successes+p.failures>1000000
            or any(type(x) not in (int,float) or not isfinite(x) or x<=0 or x>1000000
                   for x in (p.alpha_prior,p.beta_prior))
            or type(p.credibility) not in (int,float) or not isfinite(p.credibility)
            or not 0.5<=p.credibility<=0.999
            or not _source(p.prior_source) or not _source(p.data_source)):
        raise ValueError("invalid bounded beta-binomial request")
    try:
        from scipy.stats import beta
    except ImportError:
        return BetaResult("UNSUPPORTED")
    alpha=p.alpha_prior+p.successes
    beta_shape=p.beta_prior+p.failures
    tail=(1-p.credibility)/2
    low,high=map(float,beta.ppf((tail,1-tail),alpha,beta_shape))
    mean=alpha/(alpha+beta_shape)
    if not all(isfinite(v) for v in (low,high,mean)) or not 0<=low<=mean<=high<=1:
        return BetaResult("NUMERICAL_FAILURE")
    return BetaResult("OK",mean,low,high,alpha,beta_shape)


def calibration_scores(p: CalibrationProblem) -> CalibrationResult:
    if (type(p) is not CalibrationProblem
            or type(p.probabilities) is not tuple or type(p.labels) is not tuple
            or not 10<=len(p.probabilities)<=100000
            or len(p.labels)!=len(p.probabilities)
            or type(p.bins) is not int or not 2<=p.bins<=20
            or not _source(p.source)):
        raise ValueError("invalid heldout calibration sample")
    if any(type(x) not in (float,int) or not isfinite(x) or not 0<=x<=1
           for x in p.probabilities):
        raise ValueError("invalid forecast probability")
    if any(type(y) is not int or y not in (0,1) for y in p.labels):
        raise ValueError("invalid binary outcome")
    n=len(p.labels)
    brier=sum((v-y)**2 for v,y in zip(p.probabilities,p.labels))/n
    # Fixed clamp is for finite log-score reporting, not altered probabilities.
    eps=1e-15
    loss=-sum(y*log(max(eps,min(1-eps,v)))+
              (1-y)*log(max(eps,min(1-eps,1-v)))
              for v,y in zip(p.probabilities,p.labels))/n
    counts=[0]*p.bins
    forecast=[0.0]*p.bins
    observed=[0.0]*p.bins
    for v,y in zip(p.probabilities,p.labels):
        i=min(int(v*p.bins),p.bins-1)
        counts[i]+=1
        forecast[i]+=v
        observed[i]+=y
    ece=sum(abs(observed[i]/c-forecast[i]/c)*c/n
            for i,c in enumerate(counts) if c)
    return CalibrationResult(brier,loss,ece,n,sum(bool(c) for c in counts))
