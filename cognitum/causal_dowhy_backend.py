"""C14 P2B: opt-in, host-pinned DoWhy 0.14 worker adapter.

No DoWhy import in the host. Worker replies are treated as untrusted and checked
against exact P2A standardized counts. This is *not* proof of causal assumptions.
The embedding Lu host must enforce OS sandboxing; a local flag is not attestation.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import hashlib
import math
import os
import signal
import subprocess
import sys
import tempfile
import time

from cognitum import causal, causal_estimation as ref
from cognitum.proto import causal_dowhy_pb2 as d, causal_estimation_pb2 as q

MAX_FRAME = ref.MAX_FRAME
MAX_OUTPUT = 16384
MAX_EXPANDED = 10000
BACKEND_ID = 'dowhy-isolated-backdoor-linear-regression'
SUPPORTED_VERSION = '0.14'
COMPARISON_TOLERANCE = 1e-5
ASSURANCE = 'ASSUMED_GRAPH_NUMERIC_CROSSCHECK'


@dataclass(frozen=True)
class DoWhyWorkerPolicy:
    """Host-controlled immutable configuration. Never populated from model input."""
    python_executable: str
    python_sha256: str
    worker_sha256: str
    dispatcher_sha256: str
    expected_dowhy_version: str = SUPPORTED_VERSION
    enabled: bool = False
    host_isolation_attested: bool = False  # Not evidence by itself; Lu must enforce.


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def worker_source():
    return Path(__file__).with_name('causal_dowhy_worker.py')


def _parse(raw):
    req = ref._decode(raw, d.DoWhyRequest)
    if (req.schema_version != 1 or req.estimation.backend != q.DOWHY_OPTIONAL_WORKER or
        req.method not in (d.DOWHY_BACKDOOR_LINEAR_REGRESSION, d.DOWHY_FRONTDOOR_RESERVED,
                           d.DOWHY_INSTRUMENTAL_VARIABLE_RESERVED) or
        req.refutation not in (d.DOWHY_REFUTATION_NONE, d.DOWHY_PLACEBO_PERMUTATION) or
        not 1 <= req.max_expanded_rows <= MAX_EXPANDED or
        (req.refutation != d.DOWHY_REFUTATION_NONE and req.random_seed == 0)):
        raise ValueError('INVALID_DOWHY_REQUEST')
    eraw = req.estimation.SerializeToString(deterministic=True)
    _, model, total, buckets = ref._parse(eraw)
    if total > req.max_expanded_rows:
        raise ValueError('EXPANDED_SAMPLE_BUDGET')
    return req, model, total, buckets


def _empty(raw):
    return d.DoWhyResult(schema_version=1,
            request_sha256=hashlib.sha256(raw if isinstance(raw, bytes) else b'').digest(),
            status=d.DOWHY_DENIED, reason_code='INVALID_FRAME',
            backend_id=BACKEND_ID)


def _final(out, start):
    out.wall_ns = time.monotonic_ns() - start
    return out.SerializeToString(deterministic=True)


def _fail(raw, code, status=d.DOWHY_INCONCLUSIVE, *, trace_id='', start=None):
    out = _empty(raw)
    out.status, out.reason_code, out.trace_id = status, code, trace_id
    return _final(out, start or time.monotonic_ns())


def _preflight(req, model, total, buckets):
    base = req.estimation.identification
    check1 = causal._backdoor(model, base.treatment, base.target, tuple(base.adjustment))
    check2 = causal._backdoor_independent(model, base.treatment, base.target, tuple(base.adjustment))
    if check1 != check2:
        raise ValueError('GRAPH_CHECK_DISAGREEMENT')
    if not check1:
        raise ValueError('BACKDOOR_SUFFICIENCY_NOT_ESTABLISHED')
    for arms in buckets.values():
        if min(arms[0][0], arms[1][0]) < req.estimation.min_arm_count:
            raise ValueError('INSUFFICIENT_ARM_OVERLAP')
    return ref._effect(buckets, total)


def _compute_worker(raw):
    """Run only in child worker; executes installed DoWhy, never a simulated API."""
    start = time.monotonic_ns()
    out = _empty(raw)
    try:
        req, model, total, buckets = _parse(raw)
        out.trace_id = req.estimation.trace_id
        out.method = req.method
        out.refutation = req.refutation
        if req.method != d.DOWHY_BACKDOOR_LINEAR_REGRESSION:
            return _fail(raw, 'METHOD_NOT_INTEGRATED', d.DOWHY_UNSUPPORTED,
                         trace_id=out.trace_id, start=start)
        expected = _preflight(req, model, total, buckets)
        out.graph_criterion_checked = True
        from importlib.metadata import version
        try:
            version_str = version('dowhy')
        except Exception:
            return _fail(raw, 'DOWHY_NOT_INSTALLED', d.DOWHY_BACKEND_UNAVAILABLE,
                         trace_id=out.trace_id, start=start)
        if version_str != SUPPORTED_VERSION:
            return _fail(raw, 'DOWHY_VERSION_MISMATCH', d.DOWHY_BACKEND_UNAVAILABLE,
                         trace_id=out.trace_id, start=start)
        from dowhy import CausalModel
        import pandas as pd
        import networkx as nx
        import numpy as np
        variables = list(req.estimation.identification.model.endogenous)
        noises = list(req.estimation.identification.model.exogenous)
        graph = nx.DiGraph()
        for i in range(len(variables)):
            graph.add_node('v'+str(i), observed='yes')
        for i in range(len(noises)):
            graph.add_node('u'+str(i), observed='no')
        for i,node in enumerate(variables):
            for parent in node.parents: graph.add_edge('v'+str(parent), 'v'+str(i))
            for noise in node.noise: graph.add_edge('u'+str(noise), 'v'+str(i))
        graph_gml = '\n'.join(nx.generate_gml(graph))
        rows=[]
        for r in req.estimation.observations:
            rows.extend([list(r.states)] * r.count)
        dataframe=pd.DataFrame(rows, columns=['v'+str(i) for i in range(len(variables))], dtype=int)
        base = req.estimation.identification
        model_obj=CausalModel(data=dataframe, treatment='v'+str(base.treatment),
                              outcome='v'+str(base.target), graph=graph_gml,
                              proceed_when_unidentifiable=False)
        identified=model_obj.identify_effect(proceed_when_unidentifiable=False)
        chosen = set(identified.get_backdoor_variables() or [])
        supplied = {'v'+str(i) for i in base.adjustment}
        if chosen != supplied:
            raise ValueError('DOWHY_ADJUSTMENT_SET_MISMATCH')
        # Still require our independent graph criterion; DoWhy's success alone
        # does not establish a true causal graph or causal identification in nature.
        estimate=model_obj.estimate_effect(identified, method_name='backdoor.linear_regression',
                                           control_value=0, treatment_value=1,
                                           target_units='ate', test_significance=False,
                                           confidence_intervals=False)
        actual=float(estimate.value)
        if not math.isfinite(actual):
            raise ValueError('NONFINITE_ESTIMATE')
        distance=abs(actual - float(expected))
        if distance > COMPARISON_TOLERANCE:
            raise ValueError('REFERENCE_NUMERIC_DISAGREEMENT')
        out.status, out.reason_code = d.DOWHY_EFFECT_ESTIMATED, 'SUPPLIED_GRAPH_NOT_EMPIRICALLY_VERIFIED'
        out.backend_version = version_str
        out.numeric_crosschecked = True
        out.estimated_ate = format(actual, '.12g')
        out.exact_standardized_reference_ate = str(expected)
        out.absolute_reference_difference = format(distance, '.12g')
        out.total_observations = total
        out.assurance = ASSURANCE
        if req.refutation == d.DOWHY_PLACEBO_PERMUTATION:
            # This is a robustness *diagnostic*, not proof of causation. Seed is typed.
            result = model_obj.refute_estimate(identified, estimate,
                       method_name='placebo_treatment_refuter', placebo_type='permute',
                       random_state=int(req.random_seed % (2**32)), num_simulations=10)
            new_effect = float(result.new_effect)
            if not math.isfinite(new_effect): raise ValueError('NONFINITE_REFUTATION')
            out.refutation_executed = True
            out.refutation_estimated_effect = format(new_effect, '.12g')
            out.refutation_reason_code = 'PLACEBO_DIAGNOSTIC_ONLY'
    except ValueError as exc:
        code = str(exc)
        code = code if code in {'INVALID_DOWHY_REQUEST','EXPANDED_SAMPLE_BUDGET',
          'GRAPH_CHECK_DISAGREEMENT','BACKDOOR_SUFFICIENCY_NOT_ESTABLISHED',
          'INSUFFICIENT_ARM_OVERLAP','NONFINITE_ESTIMATE','NONFINITE_REFUTATION',
          'REFERENCE_NUMERIC_DISAGREEMENT','DOWHY_ADJUSTMENT_SET_MISMATCH'} else 'DOWHY_EXECUTION_FAILED'
        return _fail(raw, code, trace_id=out.trace_id, start=start)
    except (ImportError, ModuleNotFoundError):
        return _fail(raw, 'DOWHY_DEPENDENCY_UNAVAILABLE', d.DOWHY_BACKEND_UNAVAILABLE,
                     trace_id=out.trace_id, start=start)
    except Exception:
        return _fail(raw, 'DOWHY_EXECUTION_FAILED', trace_id=out.trace_id, start=start)
    return _final(out, start)


def _terminate(proc):
    if os.name != 'nt':
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    else:
        proc.kill()  # Lu Windows Job Object descendant containment still pending.
    proc.wait()


def run_dowhy_frame(raw: bytes, *, host_authorized=False, enabled=False,
                    worker_policy: DoWhyWorkerPolicy | None = None):
    """Host-side dispatch. Requires external OS isolation already enforced by Lu."""
    start = time.monotonic_ns()
    try:
        req,model,total,buckets=_parse(raw)
    except (ValueError,TypeError):
        return _fail(raw, 'INVALID_DOWHY_REQUEST', d.DOWHY_DENIED, start=start)
    trace = req.estimation.trace_id
    if not host_authorized:
        return _fail(raw, 'HOST_AUTHORIZATION_REQUIRED', d.DOWHY_DENIED, trace_id=trace, start=start)
    if not enabled:
        return _fail(raw, 'CAUSAL_DOWHY_DISABLED', d.DOWHY_DENIED, trace_id=trace, start=start)
    if req.method != d.DOWHY_BACKDOOR_LINEAR_REGRESSION:
        return _fail(raw,'METHOD_NOT_INTEGRATED',d.DOWHY_UNSUPPORTED,trace_id=trace,start=start)
    try:
        _preflight(req,model,total,buckets)
    except ValueError as exc:
        return _fail(raw,str(exc),d.DOWHY_INCONCLUSIVE,trace_id=trace,start=start)
    if not worker_policy or not worker_policy.enabled:
        return _fail(raw,'DOWHY_WORKER_DISABLED',d.DOWHY_BACKEND_UNAVAILABLE,
                     trace_id=trace,start=start)
    if not worker_policy.host_isolation_attested:
        return _fail(raw,'HOST_OS_ISOLATION_NOT_ATTESTED',d.DOWHY_DENIED,
                     trace_id=trace,start=start)
    try:
        # Preserve the configured virtual-environment executable for launch.
        # Resolving bin/python may switch to system Python and lose its packages.
        py=Path(worker_policy.python_executable)
        if not py.is_absolute() or ".." in py.parts:
            raise ValueError("WORKER_EXECUTABLE_PATH_INVALID")
        py.resolve(strict=True)  # validate target without replacing launch path
        worker=worker_source().resolve(strict=True)
        dispatcher=Path(__file__).resolve(strict=True)
        if (not all(x.is_file() for x in (py,worker,dispatcher)) or
            sha256_file(py)!=worker_policy.python_sha256 or
            sha256_file(worker)!=worker_policy.worker_sha256 or
            sha256_file(dispatcher)!=worker_policy.dispatcher_sha256):
            raise ValueError('WORKER_INTEGRITY_MISMATCH')
        if worker_policy.expected_dowhy_version != SUPPORTED_VERSION:
            raise ValueError('DOWHY_VERSION_NOT_PINNED')
        env={k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','WINDIR','HOME','LD_LIBRARY_PATH')}
        env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                   NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryFile() as output:
            proc=subprocess.Popen([str(py), '-I', str(worker)],
                   cwd=str(dispatcher.parents[1]), env=env,
                   stdin=subprocess.PIPE, stdout=output,stderr=subprocess.DEVNULL,
                   start_new_session=(os.name!='nt'))
            try:
                proc.communicate(input=raw,timeout=req.estimation.timeout_ms/1000)
            except subprocess.TimeoutExpired:
                _terminate(proc)
                return _fail(raw,'WORKER_TIMEOUT_KILLED',d.DOWHY_TIMEOUT,trace_id=trace,start=start)
            if proc.returncode:
                return _fail(raw,'WORKER_FAILED',trace_id=trace,start=start)
            if output.tell()>MAX_OUTPUT:
                raise ValueError('WORKER_OUTPUT_LIMIT')
            output.seek(0)
            candidate=output.read(MAX_OUTPUT+1)
        if len(candidate)>MAX_OUTPUT:
            raise ValueError('WORKER_OUTPUT_LIMIT')
        reply=ref._decode(candidate,d.DoWhyResult)
        if (reply.schema_version!=1 or reply.trace_id!=trace or reply.backend_id!=BACKEND_ID or
            reply.request_sha256!=hashlib.sha256(raw).digest() or reply.method not in (req.method,0) or
            reply.refutation not in (req.refutation,0)):
            raise ValueError('WORKER_REPLY_INTEGRITY_MISMATCH')
        if reply.status==d.DOWHY_EFFECT_ESTIMATED:
            if reply.backend_version!=worker_policy.expected_dowhy_version or not verify_dowhy_receipt(raw,candidate).numeric_verified:
                raise ValueError('UNVERIFIED_DOWHY_ESTIMATE')
        elif any((reply.estimated_ate,reply.exact_standardized_reference_ate,
                  reply.absolute_reference_difference,reply.numeric_crosschecked,reply.assurance,
                  reply.refutation_executed,reply.refutation_estimated_effect)):
            raise ValueError('FAILED_REPLY_CONTAINS_ESTIMATE')
        return candidate
    except (OSError,ValueError,TypeError,subprocess.SubprocessError) as exc:
        safe={'WORKER_INTEGRITY_MISMATCH','WORKER_EXECUTABLE_PATH_INVALID','DOWHY_VERSION_NOT_PINNED',
              'WORKER_OUTPUT_LIMIT','WORKER_REPLY_INTEGRITY_MISMATCH',
              'UNVERIFIED_DOWHY_ESTIMATE','FAILED_REPLY_CONTAINS_ESTIMATE'}
        reason=str(exc) if str(exc) in safe else 'WORKER_LAUNCH_FAILED'
        return _fail(raw,reason,d.DOWHY_INCONCLUSIVE,trace_id=trace,start=start)


def verify_dowhy_receipt(raw, reply):
    """Verify request binding and independent empirical contrast, NOT DoWhy internals."""
    receipt=d.DoWhyReceipt(request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
          result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
          reason_code='UNVERIFIED_DOWHY_RESULT')
    try:
        req,model,total,buckets=_parse(raw)
        out=ref._decode(reply,d.DoWhyResult)
        if (out.schema_version!=1 or out.request_sha256!=receipt.request_sha256 or
            out.trace_id!=req.estimation.trace_id or out.backend_id!=BACKEND_ID or
            out.backend_version!=SUPPORTED_VERSION or out.status!=d.DOWHY_EFFECT_ESTIMATED or
            out.method!=req.method or out.refutation!=req.refutation or
            out.reason_code!='SUPPLIED_GRAPH_NOT_EMPIRICALLY_VERIFIED' or
            out.assurance!=ASSURANCE or not out.graph_criterion_checked or
            not out.numeric_crosschecked or out.total_observations!=total):
            return receipt
        expected=_preflight(req,model,total,buckets)
        v=Fraction(out.estimated_ate)
        reference=Fraction(out.exact_standardized_reference_ate)
        distance=Fraction(out.absolute_reference_difference)
        if not all(math.isfinite(float(x)) for x in (v,reference,distance)):
            return receipt
        if (reference!=expected or distance<0 or
            abs(float(v-expected))>COMPARISON_TOLERANCE or
            abs(float(distance-abs(v-expected)))>1e-8):
            return receipt
        if req.refutation==d.DOWHY_REFUTATION_NONE:
            if out.refutation_executed or out.refutation_estimated_effect or out.refutation_reason_code:
                return receipt
        else:
            if (not out.refutation_executed or out.refutation_reason_code!='PLACEBO_DIAGNOSTIC_ONLY' or
                not math.isfinite(float(out.refutation_estimated_effect))):
                return receipt
        receipt.numeric_verified=True
        receipt.reason_code='REFERENCE_STATISTIC_CROSSCHECK_NOT_CAUSAL_PROOF'
    except Exception:
        pass
    return receipt


def dowhy_audit(raw,reply):
    result=ref._decode(reply,d.DoWhyResult)
    return d.DoWhyAudit(request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(reply).digest(),trace_id=result.trace_id,
        status=result.status,backend_id=result.backend_id,
        backend_version=result.backend_version,reason_code=result.reason_code,
        wall_ns=result.wall_ns)
