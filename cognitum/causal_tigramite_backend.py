"""C14 P4E: Tigramite PCMCI / PCMCI+ worker *candidate*, default OFF.

Typed Protobuf only. Actual native Windows process containment, host authentication,
third-party license obligations, and the 5.2.10.1 runtime are NOT attested here.
The statistical output is a candidate conditional on substantive assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import contextlib
import hashlib
import io
import math
import os
import subprocess
import tempfile
import time

from cognitum.causal_estimation import _decode
from cognitum.causal_dowhy_backend import sha256_file, _terminate
from cognitum.causal_temporal_diagnostics import _parse as parse_p4c
from cognitum.proto import causal_temporal_discovery_pb2 as td

VERSION = '5.2.10.1'
BACKEND_ID = 'tigramite-parcorr-52101'
MAX_FRAME = 270000
MAX_REPLY = 32768
LIMITS = ('REGULAR_TIMESTAMPS_CONFIRMED_NO_INTERPOLATION;PARCORR_LINEAR_GAUSSIAN;'
          'CAUSAL_STATIONARITY_ASSUMED_NOT_VERIFIED;CAUSAL_MARKOV_FAITHFULNESS_ASSUMED;'
          'NO_HIDDEN_CONFOUNDING_ASSUMED;PCMCI_LAGGED_OR_PCMCIPLUS_PARTIAL_ORIENTATION;'
          'PC_SELECTION_ALPHA_IS_NOT_VALIDATED_EFFECT_STRENGTH;'
          'FDR_BH_PCMCI_ONLY;PCMCI_PLUS_RAW_P_WITHOUT_MULTIPLICITY_CONTROL;'
          'NO_CAUSAL_EFFECT_OR_IDENTIFICATION_PROOF;NOT_LU_WINDOWS_ATTESTED')


@dataclass(frozen=True)
class TigramiteWorkerPolicy:
    """Trusted host supplies policy. A boolean alone is not OS attestation."""
    python_executable: str
    python_sha256: str
    worker_sha256: str
    dispatcher_sha256: str
    pinned_version: str = VERSION
    enabled: bool = False
    host_isolation_attested: bool = False


def worker_source() -> Path:
    return Path(__file__).with_name('causal_tigramite_worker.py')


def _parse(raw: bytes):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_FRAME:
        raise ValueError('INVALID_TEMP_DISCOVERY_FRAME')
    req = _decode(raw, td.TemporalDiscoveryRequest)
    if (req.schema_version != 1 or req.mode not in (td.TD_PCMCI_LAGGED, td.TD_PCMCI_PLUS)
        or not 1 <= req.tau_max <= 3 or req.tau_max > req.samples.max_lag
        or not 0.001 <= req.pc_alpha <= 0.2 or not math.isfinite(req.pc_alpha)
        or not 1 <= req.timeout_ms <= 30000 or not 1 <= req.seed < 2**32
        or not req.stationarity_assumption_acknowledged):
        raise ValueError('INVALID_TEMP_DISCOVERY_REQUEST')
    parse_p4c(req.samples.SerializeToString(deterministic=True))
    differences = [y.timestamp_ms-x.timestamp_ms for x,y in
                   zip(req.samples.observations, req.samples.observations[1:])]
    if any(delta != req.samples.declared_interval_ms for delta in differences):
        raise ValueError('NONREGULAR_TIMESTAMPS_NO_INTERPOLATION')
    # Four-variable, 500-row, 3-lag reference limit. Variance alone is not
    # statistical assumption verification; constant columns are inadmissible.
    for j in range(len(req.samples.variable_ids)):
        values = [r.values[j] for r in req.samples.observations]
        if max(values)-min(values) < 1e-10:
            raise ValueError('DEGENERATE_VARIABLE')
    return req


def _failure(raw, status, reason, *, req=None, start=None):
    out = td.TemporalDiscoveryResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=status,reason_code=reason,backend_id=BACKEND_ID,
        assumptions_and_limits=LIMITS, trace_id=req.samples.trace_id if req else '',
        mode=req.mode if req else td.TD_MODE_UNSPECIFIED)
    out.wall_ns = max(0,time.monotonic_ns() - (start or time.monotonic_ns()))
    return out.SerializeToString(deterministic=True)


def _canonical_links(graph, p_matrix, req):
    """Conservative projection of PCMCI and PCMCI+ outputs to typed links."""
    import numpy as np
    n=len(req.samples.variable_ids)
    shape=(n,n,req.tau_max+1)
    g=np.asarray(graph)
    p=np.asarray(p_matrix)
    if g.shape!=shape or p.shape!=shape:
        raise ValueError('TIGRAMITE_UNEXPECTED_ARRAY_SHAPE')
    # Untested cells (notably tau=0 in PCMCI's lagged-only mode) may be
    # NaN; require valid probabilities only for actual published links.
    # Do not silently convert undefined diagnostic values into significance.
    links=[]
    for lag in range(1,req.tau_max+1):
        for src in range(n):
            for dst in range(n):
                mark=str(g[src,dst,lag])
                if mark=='':continue
                if mark!='-->':
                    raise ValueError('UNSUPPORTED_LAGGED_MARK')
                value=float(p[src,dst,lag])
                if not math.isfinite(value) or not 0<=value<=1:
                    raise ValueError('INVALID_SIGNIFICANCE_ARRAY')
                links.append((src,dst,lag,mark,format(value,'.12g')))
    if req.mode==td.TD_PCMCI_PLUS:
        for src in range(n):
            if str(g[src,src,0])!='':
                raise ValueError('SELF_CONTEMPORANEOUS_EDGE')
            for dst in range(src+1,n):
                mark=str(g[src,dst,0]); reverse=str(g[dst,src,0])
                if not mark and not reverse:continue
                inv={'-->':'<--','<--':'-->','o-o':'o-o','x-x':'x-x'}
                if mark not in inv or reverse!=inv[mark]:
                    raise ValueError('UNSUPPORTED_OR_INCONSISTENT_CONTEMP_MARK')
                value=float(p[src,dst,0])
                if not math.isfinite(value) or not 0<=value<=1:
                    raise ValueError('INVALID_SIGNIFICANCE_ARRAY')
                links.append((src,dst,0,mark,format(value,'.12g')))
    return sorted(links,key=lambda x:(x[2],x[0],x[1]))


def _compute_worker(raw):
    """Worker-only execution. Real library is required; no synthetic fallback."""
    started=time.monotonic_ns()
    try: req=_parse(raw)
    except Exception:
        return _failure(raw,td.TD_REJECTED,'INVALID_TEMP_DISCOVERY_REQUEST',start=started)
    try:
        try: installed=version('tigramite')
        except PackageNotFoundError:
            return _failure(raw,td.TD_UNAVAILABLE,'TIGRAMITE_NOT_INSTALLED',req=req,start=started)
        if installed!=VERSION:
            return _failure(raw,td.TD_UNAVAILABLE,'TIGRAMITE_VERSION_MISMATCH',req=req,start=started)
        import numpy as np
        import tigramite.data_processing as pp
        from tigramite.independence_tests.parcorr import ParCorr
        from tigramite.pcmci import PCMCI
        arr=np.asarray([list(r.values) for r in req.samples.observations],dtype=float)
        np.random.seed(req.seed)
        # Some third-party algorithms print progress; stdout is a binary wire.
        with contextlib.redirect_stdout(io.StringIO()):
            dataframe=pp.DataFrame(arr,var_names=list(req.samples.variable_ids))
            engine=PCMCI(dataframe=dataframe,cond_ind_test=ParCorr(),verbosity=0)
            if req.mode==td.TD_PCMCI_LAGGED:
                answer=engine.run_pcmci(tau_min=1,tau_max=req.tau_max,
                    pc_alpha=req.pc_alpha,alpha_level=req.pc_alpha,
                    max_conds_dim=2,max_combinations=1,max_conds_py=2,
                    max_conds_px=2,fdr_method='fdr_bh')
                graph=answer.get('graph')
                if graph is None:
                    graph=engine.get_graph_from_pmatrix(answer['p_matrix'],
                        alpha_level=req.pc_alpha,tau_min=1,tau_max=req.tau_max)
                policy='PCMCI_BH_CORRECTED_P_MATRIX'
            else:
                answer=engine.run_pcmciplus(tau_min=0,tau_max=req.tau_max,
                    pc_alpha=req.pc_alpha,max_conds_dim=2,max_combinations=1,
                    max_conds_py=2,max_conds_px=2,fdr_method='none')
                graph=answer['graph']
                policy='PCMCI_PLUS_UNCORRECTED_P_MATRIX'
        links=_canonical_links(graph,answer['p_matrix'],req)
        out=td.TemporalDiscoveryResult(schema_version=1,
            request_sha256=hashlib.sha256(raw).digest(),trace_id=req.samples.trace_id,
            mode=req.mode,status=td.TD_CANDIDATE,reason_code='PARTIAL_CAUSAL_GRAPH_CANDIDATE_NOT_PROOF',
            backend_id=BACKEND_ID,backend_version=installed,
            observed_samples=len(req.samples.observations),significance_policy=policy,
            assumptions_and_limits=LIMITS)
        for src,dst,lag,mark,significance in links:
            out.links.add(source=src,target=dst,lag=lag,marks=mark,significance=significance)
        out.wall_ns=time.monotonic_ns()-started
        return out.SerializeToString(deterministic=True)
    except (ImportError,ModuleNotFoundError):
        return _failure(raw,td.TD_UNAVAILABLE,'TIGRAMITE_DEPENDENCY_UNAVAILABLE',req=req,start=started)
    except Exception:
        return _failure(raw,td.TD_INCONCLUSIVE,'TIGRAMITE_EXECUTION_FAILED',req=req,start=started)


def verify_temporal_discovery_receipt(raw, reply):
    receipt=td.TemporalDiscoveryReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req=_parse(raw)
        got=_decode(reply,td.TemporalDiscoveryResult)
        if (got.status!=td.TD_CANDIDATE or got.schema_version!=1 or
            got.request_sha256!=receipt.request_sha256 or
            got.trace_id!=req.samples.trace_id or got.mode!=req.mode or
            got.backend_id!=BACKEND_ID or got.backend_version!=VERSION or
            got.reason_code!='PARTIAL_CAUSAL_GRAPH_CANDIDATE_NOT_PROOF' or
            got.assumptions_and_limits!=LIMITS or got.causal_assumptions_verified or
            got.causal_directions_proven or
            got.observed_samples!=len(req.samples.observations) or
            got.significance_policy!=('PCMCI_BH_CORRECTED_P_MATRIX' if req.mode==td.TD_PCMCI_LAGGED
                                     else 'PCMCI_PLUS_UNCORRECTED_P_MATRIX')):
            return receipt
        n=len(req.samples.variable_ids)
        prev=None
        for link in got.links:
            key=(link.lag,link.source,link.target)
            if (prev is not None and key<=prev or link.source>=n or link.target>=n or
                link.lag>req.tau_max or
                (link.lag>0 and link.marks!='-->') or
                (link.lag==0 and (req.mode!=td.TD_PCMCI_PLUS or
                 link.source>=link.target or link.marks not in ('-->','<--','o-o','x-x')))):
                return receipt
            p=float(link.significance)
            if not math.isfinite(p) or not 0<=p<=1:
                return receipt
            prev=key
        receipt.request_bound_structure_checked=True
        receipt.reason_code='STRUCTURE_ONLY_NOT_INDEPENDENT_CAUSAL_PROOF'
    except Exception:
        pass
    return receipt


def run_temporal_discovery_frame(raw,*,host_authorized=False,enabled=False,policy=None):
    started=time.monotonic_ns()
    try: req=_parse(raw)
    except Exception:
        return _failure(raw,td.TD_REJECTED,'INVALID_TEMP_DISCOVERY_REQUEST',start=started)
    if not host_authorized:
        return _failure(raw,td.TD_REJECTED,'HOST_AUTHORIZATION_REQUIRED',req=req,start=started)
    if not enabled:
        return _failure(raw,td.TD_REJECTED,'TEMPORAL_DISCOVERY_DISABLED',req=req,start=started)
    if not policy or not policy.enabled:
        return _failure(raw,td.TD_UNAVAILABLE,'WORKER_POLICY_UNAVAILABLE',req=req,start=started)
    if not policy.host_isolation_attested:
        return _failure(raw,td.TD_REJECTED,'HOST_OS_ISOLATION_NOT_ATTESTED',req=req,start=started)
    if policy.pinned_version!=VERSION:
        return _failure(raw,td.TD_REJECTED,'WORKER_LIBRARY_PIN_MISMATCH',req=req,start=started)
    try:
        # Keep the *configured executable path* for launch: resolving a venv's
        # bin/python symlink to /usr/bin/python changes sys.prefix and loses
        # the pinned environment/site-packages. Hash verification still follows
        # the symlink to the actual executable bytes.
        py=Path(policy.python_executable)
        if not py.is_absolute() or '..' in py.parts:
            raise ValueError('WORKER_EXECUTABLE_PATH_INVALID')
        py.resolve(strict=True)  # ensure target exists; do not use to launch
        worker=worker_source().resolve(strict=True)
        dispatcher=Path(__file__).resolve(strict=True)
        if any(not x.is_file() or sha256_file(x)!=pin for x,pin in (
            (py,policy.python_sha256),(worker,policy.worker_sha256),
            (dispatcher,policy.dispatcher_sha256))):
            raise ValueError('WORKER_INTEGRITY_MISMATCH')
        env={k:v for k,v in os.environ.items() if k in (
            'PATH','SYSTEMROOT','WINDIR','HOME','LD_LIBRARY_PATH')}
        env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                   NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryFile() as spool:
            proc=subprocess.Popen([str(py),'-I',str(worker)],cwd=str(dispatcher.parents[1]),
                env=env,stdin=subprocess.PIPE,stdout=spool,stderr=subprocess.DEVNULL,
                start_new_session=(os.name!='nt'))
            try: proc.communicate(input=raw,timeout=req.timeout_ms/1000)
            except subprocess.TimeoutExpired:
                _terminate(proc)
                return _failure(raw,td.TD_TIMEOUT,'WORKER_TIMEOUT_KILLED',req=req,start=started)
            if proc.returncode:
                return _failure(raw,td.TD_INCONCLUSIVE,'WORKER_PROCESS_FAILED',req=req,start=started)
            if spool.tell()>MAX_REPLY:raise ValueError('WORKER_REPLY_TOO_LARGE')
            spool.seek(0);reply=spool.read(MAX_REPLY+1)
        got=_decode(reply,td.TemporalDiscoveryResult)
        if (got.schema_version!=1 or got.request_sha256!=hashlib.sha256(raw).digest() or
            got.trace_id!=req.samples.trace_id or got.mode!=req.mode or got.backend_id!=BACKEND_ID):
            raise ValueError('WORKER_REPLY_INTEGRITY_MISMATCH')
        if got.status==td.TD_CANDIDATE:
            if not verify_temporal_discovery_receipt(raw,reply).request_bound_structure_checked:
                raise ValueError('UNVERIFIED_WORKER_CANDIDATE')
        elif (got.status not in (td.TD_UNAVAILABLE,td.TD_INCONCLUSIVE) or
              got.reason_code not in ('TIGRAMITE_NOT_INSTALLED','TIGRAMITE_VERSION_MISMATCH',
                                      'TIGRAMITE_DEPENDENCY_UNAVAILABLE','TIGRAMITE_EXECUTION_FAILED')
              or got.links or got.backend_version or got.causal_assumptions_verified
              or got.causal_directions_proven or got.observed_samples):
            raise ValueError('FAILED_WORKER_REPLY_CONTAINS_RESULT')
        return reply
    except (OSError,ValueError,TypeError,subprocess.SubprocessError) as exc:
        safe={'WORKER_INTEGRITY_MISMATCH','WORKER_EXECUTABLE_PATH_INVALID','WORKER_REPLY_TOO_LARGE',
              'WORKER_REPLY_INTEGRITY_MISMATCH','UNVERIFIED_WORKER_CANDIDATE',
              'FAILED_WORKER_REPLY_CONTAINS_RESULT'}
        reason=str(exc) if str(exc) in safe else 'WORKER_LAUNCH_FAILED'
        return _failure(raw,td.TD_INCONCLUSIVE,reason,req=req,start=started)
