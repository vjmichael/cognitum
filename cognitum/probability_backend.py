"""C13 P2 typed discrete graphical-model backend adapter.

REFERENCE_EXACT is functional; pgmpy VE/BP are optional worker-only backends.
The parent never trusts solver replies: a bounded independent joint enumeration
rechecks posteriors/MAP. Numerical checks are *not* exact theorem proofs.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from importlib import metadata, util
from pathlib import Path
import hashlib
import math
import os
import signal
import subprocess
import sys
import tempfile
import time

from cognitum.planning import _decode, _encode
from cognitum import probability as base
from cognitum.proto import probability_pb2 as p, probability_backend_pb2 as q

MAX_FRAME = base.MAX_FRAME
MAX_OUTPUT = 65536
MAX_TOLERANCE_PPM = 100
VERSION = 'C13-P2-v1'
BACKENDS = {q.REFERENCE_EXACT: 'reference-exact',
            q.PGMPY_VARIABLE_ELIMINATION: 'pgmpy-variable-elimination',
            q.PGMPY_BELIEF_PROPAGATION: 'pgmpy-belief-propagation'}


@dataclass(frozen=True)
class WorkerPolicy:
    """Set solely by the host. No executable paths/digests from model requests."""
    python_executable: str
    python_sha256: str
    worker_sha256: str
    backend_module_sha256: str = ''
    expected_pgmpy_version: str = ''
    enabled: bool = False


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(65536): h.update(block)
    return h.hexdigest()


def worker_source():
    return Path(__file__).with_name('probability_pgmpy_worker.py')


def _request(raw):
    req = _decode(raw, q.GraphRequest)
    if (req.schema_version != 1 or req.backend not in BACKENDS or
            req.query not in (q.GRAPH_JOINT_POSTERIOR, q.GRAPH_MAP) or
            req.tolerance_ppm > MAX_TOLERANCE_PPM):
        raise ValueError('INVALID_GRAPH_REQUEST')
    model_req = req.inference
    if model_req.method != p.EXACT_VARIABLE_ELIMINATION or model_req.samples or model_req.random_seed:
        raise ValueError('EXACT_GRAPH_QUERY_REQUIRED')
    model = base._validate(model_req)
    return req, model


def _empty(raw):
    return q.GraphResult(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
                         status=q.GRAPH_REJECTED, reason_code='INVALID_FRAME')


def _fill(result, posterior, *, numeric):
    for key, probability in sorted(posterior.items()):
        result.posterior.add(states=key, probability=(format(float(probability), '.12f')
                                if numeric else str(probability)))


def _pgmpy_posterior(req, model):
    """Actual pgmpy API, imported only in the child worker. No model-generated code."""
    from pgmpy.models import DiscreteBayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination, BeliefPropagation

    names = [node.id for node in req.inference.model.nodes]
    edges = [(names[parent], names[i]) for i, parents in enumerate(model.parents) for parent in parents]
    graph = DiscreteBayesianNetwork(edges)
    graph.add_nodes_from(names)
    cpds = []
    for i, node in enumerate(req.inference.model.nodes):
        parent_cols = math.prod(model.dims[parent] for parent in model.parents[i])
        matrix = [[node.cpt_ppm[column * model.dims[i] + state] / base.PPM
                   for column in range(parent_cols)] for state in range(model.dims[i])]
        cpds.append(TabularCPD(names[i], model.dims[i], matrix,
                   evidence=[names[parent] for parent in model.parents[i]] or None,
                   evidence_card=[model.dims[parent] for parent in model.parents[i]] or None))
    graph.add_cpds(*cpds)
    if not graph.check_model(): raise ValueError('INVALID_PGMPY_MODEL')
    hard = {names[index]: state for index, state in model.hard.items()}
    virtual = []
    for index, weights in model.soft.items():
        if index in model.hard:
            if not weights[model.hard[index]]: raise ValueError('IMPOSSIBLE_EVIDENCE')
            continue  # constant likelihood cancels after conditioning
        mass = sum(weights)
        if mass == 0: raise ValueError('IMPOSSIBLE_EVIDENCE')
        virtual.append(TabularCPD(names[index], model.dims[index],
                                  [[float(value / mass)] for value in weights]))
    solver = (VariableElimination if req.backend == q.PGMPY_VARIABLE_ELIMINATION
              else BeliefPropagation)(graph)
    target_names = [names[i] for i in model.targets]
    free = [name for name in target_names if name not in hard]
    values = {}
    if free:
        factor = solver.query(variables=free, evidence=hard or None,
                              virtual_evidence=virtual or None, joint=True, show_progress=False)
        import numpy as np
        for states in product(*(range(model.dims[i]) for i in model.targets)):
            by_name = dict(zip(target_names, states))
            if any(by_name[name] != state for name, state in hard.items() if name in by_name):
                values[states] = 0.0
            else:
                axis = tuple(by_name[name] for name in factor.variables)
                values[states] = float(np.asarray(factor.values)[axis])
    else:
        # All target values fixed: pgmpy still must assess feasibility.
        # A full-joint reference precheck is required to prove nonzero evidence.
        oracle, _, _ = base._oracle(model)
        if oracle is None: raise ValueError('IMPOSSIBLE_EVIDENCE')
        values = {states: float(prob) for states, prob in oracle.items()}
    if any(not math.isfinite(v) or v < 0 for v in values.values()):
        raise ValueError('INVALID_PGMPY_NUMERIC_RESULT')
    total = sum(values.values())
    if not math.isfinite(total) or abs(total - 1) > 1e-6:
        raise ValueError('INVALID_PGMPY_NORMALIZATION')
    return values, metadata.version('pgmpy')


def _compute(raw, *, host_authorized, enabled, in_worker=False):
    start = time.monotonic_ns()
    out = _empty(raw)
    try:
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FRAME:
            raise ValueError('INVALID_FRAME')
        req, model = _request(raw)
        out.trace_id, out.backend, out.query = req.inference.trace_id, req.backend, req.query
        out.backend_id = BACKENDS[req.backend]
        out.backend_version = VERSION if req.backend == q.REFERENCE_EXACT else ''
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('PROBABILITY_DISABLED')
        if req.backend != q.REFERENCE_EXACT and not in_worker:
            raise ValueError('BACKEND_REQUIRES_HOST_WORKER')
        if req.backend == q.REFERENCE_EXACT:
            posterior, _ = base._exact(model)
            numeric = False
        else:
            if util.find_spec('pgmpy') is None:
                out.status = q.GRAPH_UNKNOWN
                out.reason_code = 'PGMPY_NOT_INSTALLED'
                return _encode(_finish(out, start))
            # A bounded exact preflight prevents third-party normalization of
            # zero-mass evidence into a spurious posterior. Larger models
            # retain only an uncertified numeric outcome.
            is_impossible = False
            try:
                preflight, _, _ = base._oracle(model)
                is_impossible = preflight is None
            except base.BudgetExceeded:
                pass
            if is_impossible:
                posterior, version = None, metadata.version('pgmpy')
            else:
                posterior, version = _pgmpy_posterior(req, model)
            out.backend_version = version
            numeric = True
        if posterior is None:
            out.status, out.reason_code = q.GRAPH_IMPOSSIBLE_EVIDENCE, 'ZERO_EVIDENCE_PROBABILITY'
        else:
            out.status, out.reason_code = q.GRAPH_SUCCESS, ('FLOAT_PGMPY_RESULT_NOT_PROOF' if numeric else 'RATIONAL_REFERENCE_RESULT')
            if req.query == q.GRAPH_JOINT_POSTERIOR:
                _fill(out, posterior, numeric=numeric)
            else:
                best = min(posterior, key=lambda key: (-posterior[key], key))
                out.map_states.extend(best)
                out.map_probability = (format(float(posterior[best]), '.12f')
                                       if numeric else str(posterior[best]))
            # independent oracle is separate from elimination/pgmpy
            try:
                expected, _, _ = base._oracle(model)
                if expected is None:
                    raise ValueError('INDEPENDENT_EVIDENCE_DISAGREEMENT')
                tol = Fraction(req.tolerance_ppm or 1, 1000000)
                if req.query == q.GRAPH_MAP:
                    actual = tuple(out.map_states)
                    valid = (actual in expected and expected[actual] == max(expected.values()) and
                             abs(Fraction(out.map_probability) - expected[actual]) <= (tol if numeric else 0))
                else:
                    valid = (set(posterior) == set(expected) and
                             all(abs(Fraction(str(posterior[x])) - expected[x]) <= (tol if numeric else 0)
                                 for x in posterior))
                if not valid: raise ValueError('INDEPENDENT_RESULT_DISAGREEMENT')
                out.independent_numeric_check = True
                out.exact_reference_certified = not numeric
            except base.BudgetExceeded:
                pass
        if time.monotonic_ns() - start > req.inference.timeout_ms * 1000000:
            out.ClearField('posterior')
            out.ClearField('map_states')
            out.map_probability = ''
            out.status, out.reason_code = q.GRAPH_UNKNOWN, 'TIME_LIMIT_EXCEEDED'
            out.independent_numeric_check = out.exact_reference_certified = False
    except base.BudgetExceeded as exc:
        out.status, out.reason_code = q.GRAPH_UNKNOWN, str(exc)[:120]
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        allowed = {'INDEPENDENT_EVIDENCE_DISAGREEMENT', 'INDEPENDENT_RESULT_DISAGREEMENT',
                   'INVALID_PGMPY_MODEL', 'IMPOSSIBLE_EVIDENCE', 'INVALID_PGMPY_NUMERIC_RESULT',
                   'INVALID_PGMPY_NORMALIZATION'}
        detail = str(exc)
        out.status, out.reason_code = q.GRAPH_REJECTED, (detail[:120] if not in_worker or detail in allowed
                                                        else 'PGMPY_INFERENCE_FAILURE')
    except (ImportError, ModuleNotFoundError):
        out.status, out.reason_code = q.GRAPH_UNKNOWN, 'PGMPY_DEPENDENCY_UNAVAILABLE'
    return _encode(_finish(out, start))


def _finish(result, start):
    result.wall_ns = time.monotonic_ns() - start
    return result


def _terminate(proc):
    if os.name != 'nt':
        try: os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    else:
        proc.kill()  # descendant containment still requires Lu Windows Job Objects
    proc.wait()


def run_graph_frame(raw: bytes, *, host_authorized=False, enabled=False,
                    worker_policy: WorkerPolicy | None = None) -> bytes:
    """Host-facing dispatcher; optional pgmpy goes through a pinned Python child."""
    start = time.monotonic_ns()
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FRAME:
        return _compute(b'', host_authorized=False, enabled=False)
    try:
        req, _ = _request(raw)
    except (ValueError, TypeError):
        return _compute(raw, host_authorized=host_authorized, enabled=enabled)
    if req.backend == q.REFERENCE_EXACT or not (host_authorized and enabled):
        return _compute(raw, host_authorized=host_authorized, enabled=enabled)
    if not worker_policy or not worker_policy.enabled:
        out = _empty(raw)
        out.status, out.reason_code = q.GRAPH_UNKNOWN, 'PGMPY_WORKER_DISABLED'
        return _encode(_finish(out, start))
    try:
        py = Path(worker_policy.python_executable)
        if not py.is_absolute() or '..' in py.parts:
            raise ValueError('WORKER_EXECUTABLE_PATH_INVALID')
        py.resolve(strict=True)  # verify target; preserve venv executable for launch
        source = worker_source().resolve(strict=True)
        backend_source = Path(__file__).resolve(strict=True)
        if not (py.is_file() and source.is_file() and backend_source.is_file() and
                sha256_file(py) == worker_policy.python_sha256 and
                sha256_file(source) == worker_policy.worker_sha256 and
                sha256_file(backend_source) == worker_policy.backend_module_sha256):
            raise ValueError('WORKER_INTEGRITY_MISMATCH')
        # Backend may be installed in a separate pinned interpreter/venv.
        # Never require the host Python environment to import pgmpy.
        if not worker_policy.expected_pgmpy_version:
            raise ValueError('PGMPY_VERSION_NOT_PINNED')
        with tempfile.TemporaryFile() as output:
            env = {key: value for key, value in os.environ.items() if key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'HOME', 'LD_LIBRARY_PATH')}
            env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
            proc = subprocess.Popen([str(py), '-m', 'cognitum.probability_pgmpy_worker'],
                                    cwd=str(Path(__file__).resolve().parents[1]), env=env,
                                    stdin=subprocess.PIPE, stdout=output, stderr=subprocess.DEVNULL,
                                    start_new_session=(os.name != 'nt'))
            try:
                proc.communicate(input=raw, timeout=req.inference.timeout_ms / 1000)
            except subprocess.TimeoutExpired:
                _terminate(proc)
                out = _empty(raw)
                out.status, out.reason_code = q.GRAPH_UNKNOWN, 'WORKER_TIMEOUT_KILLED'
                return _encode(_finish(out, start))
            if proc.returncode != 0:
                out = _empty(raw)
                out.status, out.reason_code = q.GRAPH_UNKNOWN, 'WORKER_FAILED'
                return _encode(_finish(out, start))
            if output.tell() > MAX_OUTPUT:
                raise ValueError('WORKER_OUTPUT_LIMIT')
            output.seek(0)
            candidate = output.read(MAX_OUTPUT + 1)
        reply = _decode(candidate, q.GraphResult)
        if reply.status == q.GRAPH_SUCCESS and reply.backend_version != worker_policy.expected_pgmpy_version:
            raise ValueError('PGMPY_VERSION_MISMATCH')
        if not verify_graph_receipt(raw, candidate).evidence_valid and reply.status in (q.GRAPH_SUCCESS, q.GRAPH_IMPOSSIBLE_EVIDENCE):
            raise ValueError('UNVERIFIED_WORKER_RESULT')
        return candidate
    except (ValueError, OSError, TypeError, subprocess.SubprocessError) as exc:
        out = _empty(raw)
        out.status, out.reason_code = q.GRAPH_REJECTED, str(exc)[:120]
        return _encode(_finish(out, start))


def _numbers(result, model, req):
    tol = Fraction(req.tolerance_ppm or 1, 1000000)
    exact = req.backend == q.REFERENCE_EXACT
    expected, _, count = base._oracle(model)
    if result.status == q.GRAPH_IMPOSSIBLE_EVIDENCE:
        return expected is None and not result.posterior and not result.map_states and not result.map_probability, count
    if result.status != q.GRAPH_SUCCESS or expected is None:
        return False, count
    if req.query == q.GRAPH_MAP:
        key = tuple(result.map_states)
        if result.posterior or key not in expected or not result.map_probability:
            return False, count
        try: v = Fraction(result.map_probability)
        except (ValueError, ZeroDivisionError): return False, count
        return (expected[key] == max(expected.values()) and
                abs(v - expected[key]) <= (0 if exact else tol) and
                (str(v) == result.map_probability if exact else 0 <= v <= 1)), count
    if result.map_states or result.map_probability or len(result.posterior) != len(expected):
        return False, count
    received = {}
    for cell in result.posterior:
        key = tuple(cell.states)
        if key not in expected or key in received:
            return False, count
        try: val = Fraction(cell.probability)
        except (ValueError, ZeroDivisionError): return False, count
        if val < 0 or val > 1 or abs(val - expected[key]) > (0 if exact else tol): return False, count
        if exact and str(val) != cell.probability: return False, count
        received[key] = val
    if abs(sum(received.values(), Fraction(0)) - 1) > (0 if exact else tol * len(expected)):
        return False, count
    return True, count


def verify_graph_receipt(raw: bytes, result_frame: bytes) -> q.GraphReceipt:
    receipt = q.GraphReceipt(request_sha256=hashlib.sha256(raw).digest(),
                             result_sha256=hashlib.sha256(result_frame).digest(),
                             reason_code='NOT_VERIFIED')
    try:
        req, model = _request(raw)
        result = _decode(result_frame, q.GraphResult)
        if (result.schema_version != 1 or result.request_sha256 != receipt.request_sha256 or
                result.trace_id != req.inference.trace_id or result.backend != req.backend or
                result.query != req.query or result.backend_id != BACKENDS[req.backend] or
                not result.backend_version or (req.backend == q.REFERENCE_EXACT and result.backend_version != VERSION) or
                result.status not in (q.GRAPH_SUCCESS, q.GRAPH_IMPOSSIBLE_EVIDENCE)):
            return receipt
        ok, count = _numbers(result, model, req)
        receipt.enumerated_assignments = count
        if not ok: return receipt
        exact = req.backend == q.REFERENCE_EXACT
        if (result.independent_numeric_check != (result.status == q.GRAPH_SUCCESS) or
                result.exact_reference_certified != (exact and result.status == q.GRAPH_SUCCESS)):
            return receipt
        if result.status == q.GRAPH_SUCCESS and result.reason_code != ('RATIONAL_REFERENCE_RESULT' if exact else 'FLOAT_PGMPY_RESULT_NOT_PROOF'):
            return receipt
        if result.status == q.GRAPH_IMPOSSIBLE_EVIDENCE and result.reason_code != 'ZERO_EVIDENCE_PROBABILITY':
            return receipt
        receipt.evidence_valid = True
        receipt.numeric_cross_checked = result.status == q.GRAPH_SUCCESS
        receipt.exact_reference_certified = exact and result.status == q.GRAPH_SUCCESS
        receipt.reason_code = 'INDEPENDENT_ENUMERATION_NUMERIC_CHECK' if not exact else 'INDEPENDENT_EXACT_ENUMERATION'
    except (ValueError, TypeError, base.BudgetExceeded, OverflowError, RecursionError):
        pass
    return receipt


def make_graph_audit(raw: bytes, result_frame: bytes, receipt: q.GraphReceipt | None = None):
    verified = verify_graph_receipt(raw, result_frame)
    if receipt is not None and receipt != verified:
        raise ValueError('FORGED_RECEIPT')
    result = _decode(result_frame, q.GraphResult)
    return q.GraphAudit(schema_version=1, request_sha256=hashlib.sha256(raw).digest(),
                        result_sha256=hashlib.sha256(result_frame).digest(),
                        trace_id=result.trace_id, backend=result.backend, status=result.status,
                        backend_id=result.backend_id, backend_version=result.backend_version,
                        numeric_cross_checked=verified.numeric_cross_checked,
                        exact_reference_certified=verified.exact_reference_certified,
                        wall_ns=result.wall_ns, reason_code=result.reason_code)
