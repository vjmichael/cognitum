"""C11 P3: audit-ready bounded optimization subprocess and capability manifest.

Security model: host-selected fixed, SHA-256-pinned worker executable; no
model-controlled commands/paths. Python child process provides a killable
boundary, NOT a hardened OS sandbox or proof of host authorization. All
results are independently checked with C11 P2. No benchmark run is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import os

from cognitum.formal_solver import _decode, _encode
from cognitum.optimization_workflows import (
    MAX_FRAME, MAX_RESPONSE, _select_backend, _validate, verify_workflow_frame,
)
from cognitum.proto import optimization_runtime_pb2 as rt
from cognitum.proto import workflows_pb2 as wf

MAX_ENVELOPE = 160 * 1024
# Known built-ins only. Research entries describe a future interface; they are
# not downloadable, runnable or safely enabled by an untrusted request.
_CAPABILITIES = (
    ('assignment:scipy-assignment', 'assignment', rt.ESTABLISHED, 'scipy.optimize.linear_sum_assignment', 'BSD-3-Clause', '', True, False, True),
    ('packing:scipy-highs', 'packing', rt.ESTABLISHED, 'SciPy milp/HiGHS', 'BSD-3-Clause', '', True, False, True),
    ('flow:networkx-simplex', 'flow', rt.ESTABLISHED, 'NetworkX network_simplex', 'BSD-3-Clause', '', True, False, True),
    ('scheduling:scipy-highs', 'scheduling', rt.ESTABLISHED, 'SciPy milp/HiGHS', 'BSD-3-Clause', '', True, False, True),
    ('routing:networkx-greedy', 'routing', rt.ESTABLISHED, 'NetworkX greedy_tsp', 'BSD-3-Clause', '', True, False, True),
    ('scheduling:ortools-cpsat', 'scheduling', rt.ESTABLISHED, 'Google OR-Tools CP-SAT', 'Apache-2.0', '', True, True, False),
    ('packing:research-neighborhood-search', 'packing', rt.RESEARCH_CANDIDATE, 'reserved interface only', '', '2025 ICLR research on large-neighborhood search; independent implementation review required', False, True, False),
    ('scheduling:research-learned-branching', 'scheduling', rt.RESEARCH_CANDIDATE, 'reserved interface only', '', '2026 learned branching research; no compatible backend installed', False, True, False),
)


def capability_manifest() -> bytes:
    msg = rt.CapabilityManifest(schema_version=1)
    for row in _CAPABILITIES:
        name, kind, maturity, implementation, license_id, reference, supported, opt_in, tested = row
        msg.backends.add(backend_id=name, workflow_kind=kind, maturity=maturity,
                         implementation=implementation, license_id=license_id,
                         research_reference=reference, available_in_p2=supported,
                         opt_in_required=opt_in, runtime_tested=tested,
                         interface_version='cognitum.optimization.workflow.v1')
    msg.manifest_sha256 = hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()
    return _encode(msg, 64 * 1024)


def verify_manifest(frame: bytes) -> bool:
    try:
        msg = _decode(frame, rt.CapabilityManifest, 64 * 1024)
        sig = msg.manifest_sha256
        msg.ClearField('manifest_sha256')
        return bool(msg.schema_version == 1 and len(sig) == 32 and
                    sig == hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()
                    and frame == capability_manifest())
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class WorkerPolicy:
    worker_script: Path
    expected_sha256: str
    enabled: bool = False
    # Native Lu must supply separately authenticated host authorization.
    allowed_backends: tuple[str, ...] = (
        'assignment:scipy-assignment', 'packing:scipy-highs',
        'flow:networkx-simplex', 'scheduling:scipy-highs', 'routing:networkx-greedy')
    deadline_ceiling_ms: int = 5_000
    # Host-reviewed, version-pinned Python interpreter path; not request data.
    python_executable: str = sys.executable


def fixed_worker_policy(*, enabled=False) -> WorkerPolicy:
    worker = Path(__file__).resolve().parents[1] / 'tools' / 'c11_worker.py'
    return WorkerPolicy(worker, hashlib.sha256(worker.read_bytes()).hexdigest(), enabled=enabled)


def _terminate_group(proc):
    if proc.poll() is not None:
        return
    try:
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()  # Windows descendants require Lu Job Object integration.
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.communicate(timeout=1)
    except (subprocess.TimeoutExpired, OSError):
        pass


class OptimizationWorkerRuntime:
    def __init__(self, policy: WorkerPolicy):
        self._policy = policy
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._active: set[subprocess.Popen] = set()

    def disable(self):
        self._stopped.set()
        with self._lock:
            procs = tuple(self._active)
        for proc in procs:
            _terminate_group(proc)

    def execute(self, request_frame: bytes, *, host_authorized=False, cancel_event=None) -> bytes:
        start = time.monotonic_ns()
        record = rt.ExecutionRecord(schema_version=1, outcome=rt.DENIED,
                                    reason_code='HOST_AUTHORIZATION_REQUIRED',
                                    measurement_source='python-host-monotonic-ns')
        result_frame, receipt_frame = b'', b''
        proc = None
        try:
            if not isinstance(request_frame, bytes) or not (0 < len(request_frame) <= MAX_FRAME):
                raise ValueError('INVALID_REQUEST_FRAME')
            record.request_sha256 = hashlib.sha256(request_frame).digest()
            req = _decode(request_frame, wf.WorkflowRequest, MAX_FRAME)
            record.trace_id = req.trace_id
            record.workflow_kind = req.WhichOneof('problem') or ''
            if not host_authorized:
                raise ValueError('HOST_AUTHORIZATION_REQUIRED')
            if self._stopped.is_set() or not self._policy.enabled:
                raise ValueError('WORKER_DISABLED')
            kind = _validate(req)
            backend = _select_backend(req, kind)
            record.backend_id = backend
            if backend not in self._policy.allowed_backends:
                raise ValueError('BACKEND_NOT_HOST_ALLOWED')
            max_time = req.timeout_ms or 2000
            if not 1 <= max_time <= self._policy.deadline_ceiling_ms <= 5000:
                raise ValueError('INVALID_DEADLINE')
            record.deadline_ms = max_time
            path = self._policy.worker_script.resolve(strict=True)
            actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_digest != self._policy.expected_sha256 or len(actual_digest) != 64:
                raise ValueError('WORKER_ARTIFACT_MISMATCH')
            record.worker_sha256 = bytes.fromhex(actual_digest)
            # No shell, no network access needed, no caller-provided commands.
            due = time.monotonic() + max_time / 1000.0
            proc = subprocess.Popen([self._policy.python_executable, '-I', str(path)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, start_new_session=(os.name == 'posix'),
                                    cwd=str(path.parent), close_fds=True)
            with self._lock:
                self._active.add(proc)
            try:
                # Explicit monotonic deadline; testable cancellation and kill switch.
                stdin_bytes = request_frame
                while True:
                    if (self._stopped.is_set() or (cancel_event is not None and cancel_event.is_set())):
                        record.outcome = rt.CANCELLED
                        record.reason_code = 'HOST_CANCELLED'
                        _terminate_group(proc)
                        break
                    remaining = due - time.monotonic()
                    if remaining <= 0:
                        record.outcome = rt.TIMED_OUT
                        record.reason_code = 'HOST_DEADLINE_EXCEEDED'
                        _terminate_group(proc)
                        break
                    try:
                        output, _ = proc.communicate(input=stdin_bytes, timeout=min(.05, remaining))
                        if proc.returncode != 0:
                            cancelled = self._stopped.is_set() or (cancel_event is not None and cancel_event.is_set())
                            record.outcome = rt.CANCELLED if cancelled else rt.PROCESS_FAILED
                            record.reason_code = 'HOST_CANCELLED' if cancelled else 'WORKER_NONZERO_EXIT'
                            record.exit_code = proc.returncode
                            break
                        if len(output) > MAX_RESPONSE:
                            raise ValueError('OVERSIZED_WORKER_RESULT')
                        res = _decode(output, wf.WorkflowResult, MAX_RESPONSE)
                        check = verify_workflow_frame(request_frame, output)
                        receipt = _decode(check, wf.WorkflowReceipt, MAX_RESPONSE)
                        if (res.status in (wf.VERIFIED_OPTIMAL, wf.VERIFIED_FEASIBLE, wf.VERIFIED_INFEASIBLE)
                                and (not receipt.evidence_valid or receipt.optimality_verified != res.optimality_verified)):
                            raise ValueError('FALSE_WORKER_ASSURANCE')
                        if res.status in (wf.UNKNOWN, wf.REJECTED) and (res.witness_verified or res.optimality_verified
                            or res.HasField('solution') or receipt.evidence_valid):
                            raise ValueError('FALSE_WORKER_ASSURANCE')
                        result_frame, receipt_frame = output, check
                        record.result_sha256 = hashlib.sha256(output).digest()
                        record.receipt_sha256 = hashlib.sha256(check).digest()
                        record.backend_version = res.backend_version
                        record.witness_verified = receipt.evidence_valid and res.witness_verified
                        record.optimality_verified = receipt.optimality_verified
                        record.exit_code = proc.returncode
                        record.outcome = rt.COMPLETED
                        record.reason_code = res.reason_code
                        break
                    except subprocess.TimeoutExpired:
                        stdin_bytes = None  # input sent at most once by communicate
                        continue
            except (ValueError, TypeError, OSError):
                record.outcome = rt.RESULT_REJECTED
                record.reason_code = 'WORKER_RESULT_REJECTED'
                _terminate_group(proc)
            finally:
                with self._lock:
                    self._active.discard(proc)
        except (ValueError, TypeError, OSError) as ex:
            record.outcome = rt.DENIED
            record.reason_code = str(ex)[:80] if isinstance(ex, ValueError) else 'WORKER_START_FAILED'
        finally:
            record.elapsed_ns = max(1, time.monotonic_ns()-start)
        envelope = rt.ExecutionEnvelope(schema_version=1, record=record,
                                        result_frame=result_frame, receipt_frame=receipt_frame)
        return _encode(envelope, MAX_ENVELOPE)


def verify_execution_shape(request_frame: bytes, envelope_frame: bytes) -> bool:
    """Integrity of envelope semantics only; no host signature / runtime attestation."""
    try:
        envelope = _decode(envelope_frame, rt.ExecutionEnvelope, MAX_ENVELOPE)
        record = envelope.record
        if (envelope.schema_version != 1 or record.schema_version != 1 or record.host_approved or
                len(record.request_sha256) != 32 or record.request_sha256 != hashlib.sha256(request_frame).digest()
                or record.measurement_source != 'python-host-monotonic-ns' or record.elapsed_ns == 0):
            return False
        if record.outcome != rt.COMPLETED:
            return not (envelope.result_frame or envelope.receipt_frame or record.result_sha256 or
                        record.receipt_sha256 or record.witness_verified or record.optimality_verified)
        if (not envelope.result_frame or not envelope.receipt_frame or
                record.result_sha256 != hashlib.sha256(envelope.result_frame).digest() or
                record.receipt_sha256 != hashlib.sha256(envelope.receipt_frame).digest() or
                len(record.worker_sha256) != 32):
            return False
        req = _decode(request_frame, wf.WorkflowRequest, MAX_FRAME)
        kind = _validate(req)
        if (record.workflow_kind != kind or record.backend_id != _select_backend(req, kind)
                or record.deadline_ms != (req.timeout_ms or 2000)):
            return False
        res = _decode(envelope.result_frame, wf.WorkflowResult, MAX_RESPONSE)
        receipt = _decode(envelope.receipt_frame, wf.WorkflowReceipt, MAX_RESPONSE)
        freshly_checked = verify_workflow_frame(request_frame, envelope.result_frame)
        return (envelope.receipt_frame == freshly_checked and
                record.backend_id == res.backend_id and record.trace_id == res.trace_id and
                record.backend_version == res.backend_version and record.witness_verified == (receipt.evidence_valid and res.witness_verified)
                and record.optimality_verified == receipt.optimality_verified and
                record.reason_code == res.reason_code and record.exit_code == 0 and
                (res.status in (wf.UNKNOWN, wf.REJECTED) or receipt.evidence_valid))
    except (ValueError, TypeError, OSError):
        return False
