"""C13 P3 known-variance hierarchical Gaussian partial-pooling inference.

Pure-Python precision-matrix analytic reference + independent SciPy covariance
conditioning verifier. Optional PyMC engines run in host-pinned subprocesses.
No NUTS/ADVI implementation is synthesized here. Python host flags are not Lu credentials.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import math
import os
import re
import signal
import subprocess
import tempfile
import time

from cognitum.planning import _decode, _encode, TRACE, NAME
from cognitum.proto import probability_continuous_pb2 as p

MAX_FRAME = 65536
MAX_RESPONSE = 65536
MAX_GROUPS = 16
MAX_OBS = 128
MAX_TIMEOUT = 20000
VERSION = 'C13-P3-analytic-v1'
IDS = {p.GAUSSIAN_CONJUGATE_REFERENCE: 'gaussian-analytic-reference',
       p.PYMC_NUTS: 'pymc-nuts', p.PYMC_ADVI: 'pymc-advi'}
Z95 = 1.959963984540054


@dataclass(frozen=True)
class WorkerPolicy:
    python_executable: str
    python_sha256: str
    worker_sha256: str
    adapter_sha256: str
    expected_pymc_version: str
    enabled: bool = False


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(65536): h.update(chunk)
    return h.hexdigest()


def worker_source():
    return Path(__file__).with_name('probability_pymc_worker.py')


def _parse(raw):
    req = _decode(raw, p.ContinuousRequest)
    if (req.schema_version != 1 or not TRACE.fullmatch(req.trace_id) or
            req.backend not in IDS or not 1 <= req.timeout_ms <= MAX_TIMEOUT):
        raise ValueError('INVALID_CONTINUOUS_REQUEST')
    m = req.model
    n = len(m.group_ids)
    if (not 1 <= n <= MAX_GROUPS or len(set(m.group_ids)) != n or
            'global' in m.group_ids or any(not NAME.fullmatch(g) for g in m.group_ids)):
        raise ValueError('INVALID_GROUPS')
    def sd(x): return math.isfinite(x) and 1e-6 <= x <= 1e6
    if not math.isfinite(m.global_prior_mean) or abs(m.global_prior_mean) > 1e9 or not all(
            sd(x) for x in (m.global_prior_sd, m.group_sd, m.predictive_sd)):
        raise ValueError('INVALID_PRIOR')
    if len(m.observations) > MAX_OBS or any(
            o.group >= n or not sd(o.known_sd) or not math.isfinite(o.value) or
            abs(o.value) > 1e9 for o in m.observations):
        raise ValueError('INVALID_OBSERVATIONS')
    if req.backend == p.GAUSSIAN_CONJUGATE_REFERENCE:
        if req.draws or req.warmup or req.chains:
            raise ValueError('REFERENCE_HAS_NO_MCMC')
    elif not (50 <= req.draws <= 2000 and 1 <= req.chains <= 4 and
              0 <= req.warmup <= 3000 and (req.backend != p.PYMC_NUTS or req.warmup >= 20)):
        raise ValueError('INVALID_SAMPLING_BUDGET')
    return req


def _invert(A):
    """Small positive definite precision, independently verified with SciPy."""
    n = len(A)
    aug = [[float(A[i][j]) for j in range(n)] + [float(i == j) for j in range(n)] for i in range(n)]
    for k in range(n):
        pivot = max(range(k,n), key=lambda i: abs(aug[i][k]))
        aug[k],aug[pivot] = aug[pivot],aug[k]
        d = aug[k][k]
        if not math.isfinite(d) or abs(d) < 1e-25: raise ValueError('NUMERICAL_PRECISION_FAILURE')
        aug[k] = [x / d for x in aug[k]]
        for i in range(n):
            if i == k: continue
            factor = aug[i][k]
            aug[i] = [a-factor*b for a,b in zip(aug[i], aug[k])]
    inv = [r[n:] for r in aug]
    if any(not math.isfinite(x) for row in inv for x in row): raise ValueError('NUMERICAL_PRECISION_FAILURE')
    return inv


def analytic(m):
    """Posterior precision and mean of [global mu, group theta_0, ...]."""
    n = len(m.group_ids) + 1
    q = [[0.0]*n for _ in range(n)]
    rhs = [0.0]*n
    w0 = 1/(m.global_prior_sd**2)
    wg = 1/(m.group_sd**2)
    q[0][0] = w0 + (n-1)*wg
    rhs[0] = w0 * m.global_prior_mean
    for j in range(1,n):
        q[j][j] = wg
        q[0][j] = q[j][0] = -wg
    for o in m.observations:
        w = 1/(o.known_sd**2)
        q[o.group+1][o.group+1] += w
        rhs[o.group+1] += w*o.value
    cov = _invert(q)
    means = [sum(cov[i][j]*rhs[j] for j in range(n)) for i in range(n)]
    variances = [cov[i][i] for i in range(n)]
    if any(not math.isfinite(x) for x in means + variances) or any(x <= 0 for x in variances):
        raise ValueError('NUMERICAL_PRECISION_FAILURE')
    return tuple((means[i],math.sqrt(variances[i])) for i in range(n))


def independent_oracle(m):
    """Separate covariance-conditioning derivation, using SciPy Cholesky.

    Limited to <=48 observations to bound verification work; never reuses
    the precision inverse from the reference computation.
    """
    if len(m.observations) > 48: return None
    import numpy as np
    from scipy.linalg import cho_factor, cho_solve
    g = len(m.group_ids)
    a2 = m.global_prior_sd**2
    b2 = m.group_sd**2
    prior = np.full((g+1,g+1),a2, dtype=float)
    prior[1:,1:] += np.eye(g)*b2
    base = np.full(g+1, m.global_prior_mean)
    if not m.observations:
        mu, post = base, prior
    else:
        obs = np.array([o.value for o in m.observations],dtype=float)
        pick = np.array([o.group+1 for o in m.observations])
        noise = np.array([o.known_sd**2 for o in m.observations])
        kk = prior[np.ix_(pick,pick)] + np.diag(noise)
        L = cho_factor(kk, check_finite=True)
        cross = prior[:, pick]
        mu = base + cross @ cho_solve(L,obs-base[pick])
        post = prior - cross @ cho_solve(L,cross.T)
    out = tuple((float(mu[i]), math.sqrt(float(post[i,i]))) for i in range(g+1))
    if any(not math.isfinite(v) or sd <= 0 for v,sd in out):
        raise ValueError('INDEPENDENT_PRECISION_FAILURE')
    return out


def _fill(out, moments, m):
    for i, (mean,sd) in enumerate(moments):
        row = out.moments.add(variable=('global' if i==0 else m.group_ids[i-1]),
                              mean=mean, sd=sd, central_95_lower=mean-Z95*sd,
                              central_95_upper=mean+Z95*sd)
        if i:
            row.predictive_mean = mean
            row.predictive_sd = math.hypot(sd,m.predictive_sd)


def _empty(raw):
    return p.ContinuousResult(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
                              status=p.CONTINUOUS_REJECTED, reason_code='INVALID_FRAME')


def _compute(raw, *, host_authorized, enabled, in_worker=False):
    start = time.monotonic_ns()
    out = _empty(raw)
    try:
        req = _parse(raw)
        out.trace_id, out.backend = req.trace_id, req.backend
        out.backend_id = IDS[req.backend]
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('PROBABILITY_DISABLED')
        if req.backend != p.GAUSSIAN_CONJUGATE_REFERENCE:
            if not in_worker: raise ValueError('HOST_WORKER_REQUIRED')
            try:
                moments, version, diagnostics = _run_pymc(req)
            except (ImportError, ModuleNotFoundError):
                out.status, out.reason_code = p.CONTINUOUS_UNKNOWN, 'PYMC_DEPENDENCY_INCOMPATIBLE'
                return _encode(_finish(out,start))
            out.backend_version = version
            out.actual_draws_per_chain, out.actual_chains, out.max_rhat, out.min_ess_bulk, out.divergences = diagnostics
        else:
            moments = analytic(req.model)
            out.backend_version = VERSION
        _fill(out,moments,req.model)
        out.status = p.CONTINUOUS_SUCCESS
        # For reference, independent oracle is checked with a strict relative tolerance.
        # Sampling engines need a much wider uncertainty-aware comparison.
        try:
            expected = independent_oracle(req.model)
        except ImportError:
            expected = None
        if expected is not None:
            exact = req.backend == p.GAUSSIAN_CONJUGATE_REFERENCE
            out.independent_numeric_check = _compare(out,expected,req, exact=exact)
            out.exact_gaussian_reference = exact and out.independent_numeric_check
            if not out.independent_numeric_check:
                out.ClearField('moments')
                out.status, out.reason_code = p.CONTINUOUS_REJECTED, 'INDEPENDENT_RESULT_DISAGREEMENT'
                out.exact_gaussian_reference = False
                return _encode(_finish(out,start))
        out.reason_code = ('ANALYTIC_GAUSSIAN_REFERENCE' if out.exact_gaussian_reference else
                           'POSTERIOR_SAMPLES_NOT_PROOF' if req.backend != p.GAUSSIAN_CONJUGATE_REFERENCE else
                           'INDEPENDENT_ORACLE_UNAVAILABLE')
        if time.monotonic_ns()-start > req.timeout_ms * 1000000:
            out.ClearField('moments')
            out.independent_numeric_check = out.exact_gaussian_reference = False
            out.status, out.reason_code = p.CONTINUOUS_UNKNOWN, 'TIME_LIMIT_EXCEEDED'
    except (ValueError, TypeError, OverflowError, ArithmeticError) as exc:
        out.status, out.reason_code = p.CONTINUOUS_REJECTED, str(exc)[:120]
    except (ImportError, ModuleNotFoundError):
        out.status, out.reason_code = p.CONTINUOUS_UNKNOWN, 'OPTIONAL_NUMERIC_DEPENDENCY_MISSING'
    return _encode(_finish(out,start))


def _finish(out,start):
    out.wall_ns = time.monotonic_ns()-start
    return out


def _compare(out, reference, req, *, exact):
    if len(out.moments) != len(reference): return False
    if not exact and (out.actual_chains < 1 or out.actual_draws_per_chain < 50): return False
    for i,(row,(mean,sd)) in enumerate(zip(out.moments,reference)):
        if row.variable != ('global' if i==0 else req.model.group_ids[i-1]):return False
        vals = (row.mean,row.sd,row.central_95_lower,row.central_95_upper,row.predictive_mean,row.predictive_sd)
        if any(not math.isfinite(x) for x in vals) or row.sd <= 0: return False
        # Sampling uncertainty is NOT an exact proof; allow conservative ~6 SE.
        eps = 1e-6 * max(1,abs(mean),sd) if exact else max(0.25*sd, 6*sd/math.sqrt(out.actual_chains*out.actual_draws_per_chain))
        if abs(row.mean-mean)>eps or abs(row.sd-sd)>(eps if not exact else 1e-6*max(1,sd)):return False
        if exact and (abs(row.central_95_lower-(mean-Z95*sd))>eps or
                      abs(row.central_95_upper-(mean+Z95*sd))>eps):return False
        if not exact and (row.central_95_lower>row.central_95_upper or
                          not row.central_95_lower < row.mean < row.central_95_upper):return False
        if i:
            if abs(row.predictive_mean-row.mean)>1e-6*max(1,abs(row.mean)):return False
            if abs(row.predictive_sd-math.hypot(row.sd,req.model.predictive_sd))>1e-6*max(1,row.predictive_sd):return False
        elif row.predictive_mean or row.predictive_sd:return False
    return True


def _run_pymc(req):
    """Executed only in a host-pinned child; known model template, no model code."""
    import pymc as pm
    import numpy as np
    g = len(req.model.group_ids)
    with pm.Model() as model:
        global_mean = pm.Normal('global', mu=req.model.global_prior_mean, sigma=req.model.global_prior_sd)
        theta = pm.Normal('theta',mu=global_mean,sigma=req.model.group_sd,shape=g)
        if req.model.observations:
            ids=np.array([o.group for o in req.model.observations],dtype=int)
            y=np.array([o.value for o in req.model.observations],dtype=float)
            sigma=np.array([o.known_sd for o in req.model.observations],dtype=float)
            pm.Normal('likelihood',mu=theta[ids],sigma=sigma,observed=y)
        if req.backend==p.PYMC_NUTS:
            idata=pm.sample(draws=req.draws,tune=req.warmup,chains=req.chains,cores=1,
                            random_seed=int(req.seed or 1),progressbar=False,compute_convergence_checks=False,
                            nuts_sampler='pymc',return_inferencedata=True)
            import arviz as az
            if req.chains>=2 and req.draws>=50:
                rh=az.rhat(idata,method='rank')
                ess=az.ess(idata,method='bulk')
                max_rhat=max(float(np.max(v.values)) for v in rh.data_vars.values())
                min_ess=min(float(np.min(v.values)) for v in ess.data_vars.values())
            else: max_rhat=min_ess=0.0  # unavailable, not convergence assurance
            divergences=int(np.asarray(idata.sample_stats['diverging'].values).sum())
            chains=req.chains
        else:
            fit=pm.fit(n=max(100,req.warmup),method='advi',progressbar=False,
                       random_seed=int(req.seed or 1))
            idata=fit.sample(draws=req.draws*req.chains,random_seed=int(req.seed or 1),
                             return_inferencedata=True)
            max_rhat=min_ess=0.0  # VI has no MCMC mixing diagnostic
            divergences=0
            chains=1
        mu=np.asarray(idata.posterior['global'].values).reshape(-1)
        group=np.asarray(idata.posterior['theta'].values).reshape(-1,g)
        samples=[mu]+[group[:,i] for i in range(g)]
        moments=[]
        for arr in samples:
            if not np.all(np.isfinite(arr)) or len(arr)<2: raise ValueError('INVALID_PYMC_DRAWS')
            moments.append((float(np.mean(arr)),float(np.std(arr,ddof=1))))
        return tuple(moments), str(pm.__version__), (req.draws,chains,max_rhat,min_ess,divergences)


def _terminate(proc):
    if os.name!='nt':
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    else: proc.kill() # Windows descendants require Lu Job Objects
    proc.wait()


def run_continuous_frame(raw, *, host_authorized=False, enabled=False, worker_policy=None):
    start=time.monotonic_ns()
    try: req=_parse(raw)
    except (ValueError,TypeError):
        return _compute(raw,host_authorized=host_authorized,enabled=enabled)
    if req.backend==p.GAUSSIAN_CONJUGATE_REFERENCE or not (host_authorized and enabled):
        return _compute(raw,host_authorized=host_authorized,enabled=enabled)
    if worker_policy is None or not worker_policy.enabled:
        out=_empty(raw);out.status,out.reason_code=p.CONTINUOUS_UNKNOWN,'PYMC_WORKER_DISABLED'
        return _encode(_finish(out,start))
    try:
        interpreter=Path(worker_policy.python_executable)
        if not interpreter.is_absolute() or '..' in interpreter.parts:
            raise ValueError('WORKER_EXECUTABLE_PATH_INVALID')
        interpreter.resolve(strict=True)  # verify target without dropping venv activation
        source=worker_source().resolve(strict=True)
        module=Path(__file__).resolve(strict=True)
        if (not interpreter.is_file() or
            sha256_file(interpreter)!=worker_policy.python_sha256 or
            sha256_file(source)!=worker_policy.worker_sha256 or
            sha256_file(module)!=worker_policy.adapter_sha256):
            raise ValueError('WORKER_INTEGRITY_MISMATCH')
        if not worker_policy.expected_pymc_version: raise ValueError('PYMC_VERSION_NOT_PINNED')
        env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','SYSTEMROOT','WINDIR','LD_LIBRARY_PATH')}
        env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        with tempfile.TemporaryFile() as output:
            proc=subprocess.Popen([str(interpreter),'-m','cognitum.probability_pymc_worker'],
                                  cwd=str(Path(__file__).resolve().parents[1]),env=env,stdin=subprocess.PIPE,
                                  stdout=output,stderr=subprocess.DEVNULL,
                                  start_new_session=(os.name!='nt'))
            try: proc.communicate(input=raw,timeout=req.timeout_ms/1000)
            except subprocess.TimeoutExpired:
                _terminate(proc);out=_empty(raw)
                out.status,out.reason_code=p.CONTINUOUS_UNKNOWN,'WORKER_TIMEOUT_KILLED'
                return _encode(_finish(out,start))
            if proc.returncode!=0:
                out=_empty(raw);out.status,out.reason_code=p.CONTINUOUS_UNKNOWN,'PYMC_WORKER_FAILED'
                return _encode(_finish(out,start))
            if output.tell()>MAX_RESPONSE: raise ValueError('WORKER_OUTPUT_LIMIT')
            output.seek(0);candidate=output.read(MAX_RESPONSE+1)
        reply=_decode(candidate,p.ContinuousResult)
        if reply.status==p.CONTINUOUS_SUCCESS:
            if reply.backend_version!=worker_policy.expected_pymc_version:
                raise ValueError('PYMC_VERSION_MISMATCH')
            receipt=verify_continuous_receipt(raw,candidate)
            if not receipt.evidence_valid: raise ValueError('UNVERIFIED_WORKER_RESULT')
        return candidate
    except (OSError,ValueError,TypeError,subprocess.SubprocessError) as exc:
        out=_empty(raw);out.status,out.reason_code=p.CONTINUOUS_REJECTED,str(exc)[:120]
        return _encode(_finish(out,start))


def verify_continuous_receipt(raw,result_frame):
    receipt=p.ContinuousReceipt(request_sha256=hashlib.sha256(raw).digest(),
                                result_sha256=hashlib.sha256(result_frame).digest(),
                                reason_code='NOT_VERIFIED')
    try:
        req=_parse(raw)
        res=_decode(result_frame,p.ContinuousResult)
        if (res.schema_version!=1 or res.request_sha256!=receipt.request_sha256 or
            res.trace_id!=req.trace_id or res.backend!=req.backend or
            res.backend_id!=IDS[req.backend] or not res.backend_version or
            res.status!=p.CONTINUOUS_SUCCESS or
            res.reason_code not in ('ANALYTIC_GAUSSIAN_REFERENCE','INDEPENDENT_ORACLE_UNAVAILABLE','POSTERIOR_SAMPLES_NOT_PROOF')):
            return receipt
        if req.backend==p.GAUSSIAN_CONJUGATE_REFERENCE and (res.backend_version!=VERSION or res.actual_draws_per_chain or res.actual_chains or res.max_rhat or res.min_ess_bulk or res.divergences):return receipt
        if req.backend!=p.GAUSSIAN_CONJUGATE_REFERENCE and (res.exact_gaussian_reference or res.actual_draws_per_chain!=req.draws or res.actual_chains!=(1 if req.backend==p.PYMC_ADVI else req.chains) or res.divergences>req.chains*(req.draws+req.warmup) or (req.backend==p.PYMC_ADVI and (res.max_rhat or res.min_ess_bulk or res.divergences))):
            return receipt
        expected=independent_oracle(req.model)
        if expected is None: return receipt
        exact=req.backend==p.GAUSSIAN_CONJUGATE_REFERENCE
        if not _compare(res,expected,req,exact=exact):return receipt
        if not all(math.isfinite(x) and x >= 0 for x in (res.max_rhat,res.min_ess_bulk)) or not res.independent_numeric_check or res.exact_gaussian_reference!=exact or res.reason_code!=('ANALYTIC_GAUSSIAN_REFERENCE' if exact else 'POSTERIOR_SAMPLES_NOT_PROOF'):
            return receipt
        receipt.evidence_valid=True
        receipt.analytic_reference_checked=exact
        receipt.sample_diagnostics_available=(not exact and req.backend==p.PYMC_NUTS and req.chains>=2 and req.draws>=50 and res.max_rhat>0 and res.min_ess_bulk>0)
        receipt.reason_code='INDEPENDENT_COVARIANCE_CONDITIONING'
    except (ValueError,TypeError,ImportError,OverflowError,ArithmeticError):pass
    return receipt


def make_continuous_audit(raw,result_frame,receipt=None):
    verified=verify_continuous_receipt(raw,result_frame)
    if receipt is not None and receipt!=verified:raise ValueError('FORGED_RECEIPT')
    r=_decode(result_frame,p.ContinuousResult)
    return p.ContinuousAudit(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
                             result_sha256=hashlib.sha256(result_frame).digest(),trace_id=r.trace_id,
                             backend=r.backend,status=r.status,backend_id=r.backend_id,
                             backend_version=r.backend_version,
                             independent_numeric_check=verified.evidence_valid,
                             exact_gaussian_reference=verified.analytic_reference_checked,
                             wall_ns=r.wall_ns,reason_code=r.reason_code)
