"""C13 P4 trusted conjugate Bayesian templates, posterior predictive checks.

Three explicitly limited statistical families; this is not an arbitrary probabilistic
program or a replacement for PyMC/Pyro/NumPyro. SciPy provides established
probability distributions; no code or shell arguments originate in model frames.
The numerical verifier recomputes closed-form formulas; this is an integrity
check, NOT a general formal proof or sampling convergence certificate.
"""
from __future__ import annotations
import hashlib
import math
import time
from cognitum.planning import _decode, _encode, TRACE
from cognitum.proto import probability_conjugate_pb2 as p

VERSION = 'C13-P4-conjugate-scipy-1'
MAX_FRAME = 65536
MAX_TIMEOUT = 20000
FIELDS = ('shape_a','shape_b','location','strength','posterior_mean',
          'posterior_variance','credible_lower_95','credible_upper_95',
          'predictive_mean','predictive_variance','predictive_lower_95','predictive_upper_95')
FLAGS = ('posterior_mean_defined','posterior_variance_defined',
         'predictive_mean_defined','predictive_variance_defined')


def _parse(raw):
    if len(raw)>MAX_FRAME: raise ValueError('FRAME_TOO_LARGE')
    req=_decode(raw,p.ConjugateRequest)
    family=req.WhichOneof('model')
    if req.schema_version!=1 or not TRACE.fullmatch(req.trace_id) or not 1<=req.timeout_ms<=MAX_TIMEOUT or family is None:
        raise ValueError('INVALID_CONJUGATE_REQUEST')
    def positive(v): return math.isfinite(v) and 1e-4<=v<=1e4
    if family=='beta_binomial':
        m=req.beta_binomial
        if not positive(m.prior_alpha) or not positive(m.prior_beta) or m.successes>100000 or m.failures>100000 or m.future_trials>1000:
            raise ValueError('INVALID_BETA_BINOMIAL')
    elif family=='gamma_poisson':
        m=req.gamma_poisson
        if not positive(m.prior_shape) or not positive(m.prior_rate) or not 1e-4<=m.future_exposure<=10000 or len(m.observations)>128 or any(o.count>100000 or not positive(o.exposure) for o in m.observations):
            raise ValueError('INVALID_GAMMA_POISSON')
    else:
        m=req.normal_inverse_gamma
        if not all(positive(v) for v in (m.prior_kappa,m.prior_alpha,m.prior_beta)) or not math.isfinite(m.prior_mu) or abs(m.prior_mu)>1e5 or len(m.observations)>128 or any(not math.isfinite(x) or abs(x)>1e5 for x in m.observations):
            raise ValueError('INVALID_NORMAL_INVERSE_GAMMA')
    return req,family


def _numeric_summary(req,family):
    """Closed-form posterior updates; established SciPy quantiles."""
    from scipy import stats
    out={key:0.0 for key in FIELDS}
    out.update({key:False for key in FLAGS})
    if family=='beta_binomial':
        m=req.beta_binomial
        a=m.prior_alpha+m.successes; b=m.prior_beta+m.failures; n=m.future_trials
        out.update(shape_a=a,shape_b=b,posterior_mean=a/(a+b),
                   posterior_variance=a*b/((a+b)**2*(a+b+1)),
                   credible_lower_95=float(stats.beta.ppf(.025,a,b)),
                   credible_upper_95=float(stats.beta.ppf(.975,a,b)),
                   predictive_mean=n*a/(a+b),
                   predictive_variance=n*a*b*(a+b+n)/((a+b)**2*(a+b+1)),
                   predictive_lower_95=float(stats.betabinom.ppf(.025,n,a,b)),
                   predictive_upper_95=float(stats.betabinom.ppf(.975,n,a,b)))
        for key in FLAGS:out[key]=True
    elif family=='gamma_poisson':
        m=req.gamma_poisson
        a=m.prior_shape+sum(o.count for o in m.observations)
        b=m.prior_rate+sum(o.exposure for o in m.observations)
        exposure=m.future_exposure
        pred_mean=exposure*a/b
        out.update(shape_a=a,shape_b=b,posterior_mean=a/b,posterior_variance=a/b**2,
                   credible_lower_95=float(stats.gamma.ppf(.025,a,scale=1/b)),
                   credible_upper_95=float(stats.gamma.ppf(.975,a,scale=1/b)),
                   predictive_mean=pred_mean,predictive_variance=pred_mean*(1+exposure/b),
                   predictive_lower_95=float(stats.nbinom.ppf(.025,a,b/(b+exposure))),
                   predictive_upper_95=float(stats.nbinom.ppf(.975,a,b/(b+exposure))))
        for key in FLAGS:out[key]=True
    else:
        m=req.normal_inverse_gamma
        n=len(m.observations); k=m.prior_kappa+n
        bar=math.fsum(m.observations)/n if n else 0.0
        mu=(m.prior_kappa*m.prior_mu + n*bar)/k
        a=m.prior_alpha + n/2
        b=m.prior_beta + (math.fsum((x-bar)**2 for x in m.observations) + (m.prior_kappa*n/k)*(bar-m.prior_mu)**2)/2
        df=2*a
        locscale=math.sqrt(b/(a*k))
        predscale=math.sqrt(b*(k+1)/(a*k))
        out.update(shape_a=a,shape_b=b,location=mu,strength=k,
                   credible_lower_95=float(stats.t.ppf(.025,df,loc=mu,scale=locscale)),
                   credible_upper_95=float(stats.t.ppf(.975,df,loc=mu,scale=locscale)),
                   predictive_lower_95=float(stats.t.ppf(.025,df,loc=mu,scale=predscale)),
                   predictive_upper_95=float(stats.t.ppf(.975,df,loc=mu,scale=predscale)))
        if a>.5:
            out['posterior_mean_defined']=out['predictive_mean_defined']=True
            out['posterior_mean']=out['predictive_mean']=mu
        if a>1:
            out['posterior_variance_defined']=out['predictive_variance_defined']=True
            out['posterior_variance']=b/(k*(a-1))
            out['predictive_variance']=b*(k+1)/(k*(a-1))
    if any(not math.isfinite(out[k]) or abs(out[k])>1e16 for k in FIELDS):
        raise ArithmeticError('NUMERIC_RANGE_EXCEEDED')
    if (out['credible_lower_95']>out['credible_upper_95'] or
        out['predictive_lower_95']>out['predictive_upper_95']):
        raise ArithmeticError('NUMERIC_QUANTILE_FAILED')
    return out


def _independent_rederive(req,family):
    """Recompute sufficient statistics using independent algebraic updates.

    Quantiles still come from the same SciPy distributions; this is a separate
    numeric consistency check, not a proof that the chosen model is correct.
    """
    from scipy import stats
    import numpy as np
    if family=='beta_binomial':
        m=req.beta_binomial
        a=float(np.sum([m.prior_alpha,float(m.successes)])); b=float(np.sum([m.prior_beta,float(m.failures)])); n=m.future_trials
        post=stats.beta(a,b); predictive=stats.betabinom(n,a,b)
        ma,va=post.stats(moments='mv'); mp,vp=predictive.stats(moments='mv')
        data=dict(shape_a=a,shape_b=b,location=0.,strength=0.,posterior_mean=float(ma),posterior_variance=float(va),
                  credible_lower_95=float(post.ppf(.025)),credible_upper_95=float(post.ppf(.975)),
                  predictive_mean=float(mp),predictive_variance=float(vp),predictive_lower_95=float(predictive.ppf(.025)),predictive_upper_95=float(predictive.ppf(.975)))
        flags={x:True for x in FLAGS}
    elif family=='gamma_poisson':
        m=req.gamma_poisson
        a=float(np.sum([m.prior_shape,*[float(o.count) for o in m.observations]]))
        b=float(np.sum([m.prior_rate,*[o.exposure for o in m.observations]]))
        post=stats.gamma(a,scale=1/b); predictive=stats.nbinom(a,b/(b+m.future_exposure))
        ma,va=post.stats(moments='mv'); mp,vp=predictive.stats(moments='mv')
        data=dict(shape_a=a,shape_b=b,location=0.,strength=0.,posterior_mean=float(ma),posterior_variance=float(va),
                  credible_lower_95=float(post.ppf(.025)),credible_upper_95=float(post.ppf(.975)),
                  predictive_mean=float(mp),predictive_variance=float(vp),predictive_lower_95=float(predictive.ppf(.025)),predictive_upper_95=float(predictive.ppf(.975)))
        flags={x:True for x in FLAGS}
    else:
        m=req.normal_inverse_gamma
        obs=np.asarray(m.observations,dtype=float)
        n=len(obs); k=m.prior_kappa+n
        total=float(obs.sum()); ss=float(np.dot(obs,obs))
        a=m.prior_alpha + .5*n
        # Stable alternate centered formula derived from sums (not raw squared sums).
        if n:
            avg=total/n
            scatter=max(0., ss-total*total/n)
            b=m.prior_beta+.5*(scatter+m.prior_kappa*n/k*(avg-m.prior_mu)**2)
        else: b=m.prior_beta
        mu=m.prior_mu+(total-n*m.prior_mu)/k
        posterior=stats.t(df=2*a,loc=mu,scale=math.sqrt(b/(a*k)))
        predictive=stats.t(df=2*a,loc=mu,scale=math.sqrt(b*(k+1)/(a*k)))
        flags={'posterior_mean_defined':a>.5,'predictive_mean_defined':a>.5,
               'posterior_variance_defined':a>1,'predictive_variance_defined':a>1}
        data=dict(shape_a=a,shape_b=b,location=mu,strength=k,
                  posterior_mean=mu if a>.5 else 0.,predictive_mean=mu if a>.5 else 0.,
                  posterior_variance=b/(k*(a-1)) if a>1 else 0.,
                  predictive_variance=b*(k+1)/(k*(a-1)) if a>1 else 0.,
                  credible_lower_95=float(posterior.ppf(.025)),credible_upper_95=float(posterior.ppf(.975)),
                  predictive_lower_95=float(predictive.ppf(.025)),predictive_upper_95=float(predictive.ppf(.975)))
    return data,flags


def _matching(summary,req,family):
    reference,flags=_independent_rederive(req,family)
    if any(getattr(summary,key)!=flags[key] for key in FLAGS):return False
    for key in FIELDS:
        a=getattr(summary,key); b=reference[key]
        if not math.isfinite(a) or not math.isfinite(b):return False
        if abs(a-b)>1e-7*max(1,abs(a),abs(b)):return False
    return True


def run_conjugate_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    out=p.ConjugateResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),reason_code='INVALID_FRAME')
    try:
        req,family=_parse(raw)
        out.trace_id=req.trace_id; out.model_family=family
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('PROBABILITY_DISABLED')
        vals=_numeric_summary(req,family)
        for name,value in vals.items():setattr(out,name,value)
        out.backend_version=VERSION
        out.independently_recomputed=_matching(out,req,family)
        if not out.independently_recomputed:raise ArithmeticError('NUMERICAL_DISAGREEMENT')
        out.status=p.CONJUGATE_SUCCESS
        out.reason_code='CONJUGATE_FORMULA_RECOMPUTED'
        if time.monotonic_ns()-start>req.timeout_ms*1000000:
            out.Clear()
            out.schema_version=1;out.request_sha256=hashlib.sha256(raw).digest()
            out.status=p.CONJUGATE_UNKNOWN;out.reason_code='TIME_LIMIT_EXCEEDED'
    except (ValueError,TypeError,OverflowError) as e:
        out.status=p.CONJUGATE_REJECTED;out.reason_code=str(e)[:100]
    except (ArithmeticError,ImportError) as e:
        out.Clear()
        out.schema_version=1;out.request_sha256=hashlib.sha256(raw).digest()
        out.status=p.CONJUGATE_UNKNOWN;out.reason_code='NUMERICAL_UNAVAILABLE'
    out.wall_ns=time.monotonic_ns()-start
    return _encode(out)


def verify_conjugate_receipt(raw,result_frame):
    receipt=p.ConjugateReceipt(request_sha256=hashlib.sha256(raw).digest(),
                               result_sha256=hashlib.sha256(result_frame).digest(),reason_code='NOT_VERIFIED')
    try:
        req,family=_parse(raw);res=_decode(result_frame,p.ConjugateResult)
        if (res.schema_version!=1 or res.request_sha256!=receipt.request_sha256 or
            res.trace_id!=req.trace_id or res.model_family!=family or res.status!=p.CONJUGATE_SUCCESS or
            res.reason_code!='CONJUGATE_FORMULA_RECOMPUTED' or not res.independently_recomputed or
            res.backend_version!=VERSION):return receipt
        if not _matching(res,req,family):return receipt
        receipt.evidence_valid=True
        receipt.assurance='RECOMPUTED_CONJUGATE_FORMULAS_NOT_MODEL_VALIDITY'
        receipt.reason_code='SCIPY_DISTRIBUTION_CROSSCHECK'
    except (ValueError,TypeError,ArithmeticError,ImportError,OverflowError):pass
    return receipt


def make_conjugate_audit(raw,result_frame,receipt=None):
    checked=verify_conjugate_receipt(raw,result_frame)
    if receipt is not None and checked!=receipt:raise ValueError('FORGED_RECEIPT')
    r=_decode(result_frame,p.ConjugateResult)
    return p.ConjugateAudit(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
             result_sha256=hashlib.sha256(result_frame).digest(),trace_id=r.trace_id,
             model_family=r.model_family,status=r.status,backend_version=r.backend_version,
             independently_recomputed=checked.evidence_valid,wall_ns=r.wall_ns,reason_code=r.reason_code)
