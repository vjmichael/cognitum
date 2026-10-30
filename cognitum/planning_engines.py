"""C12 P2 optional mature planner adapters with host-pinned execution.

Fast Downward driver and Unified Planning are *optional*, not bundled or claimed
runtime-tested. Typed STRIPS requests only; generated PDDL goes to a temporary
working directory. External plan strings are replayed against original task.
Proven optimality/unreachability requires independent complete finite check.
No host authority or OS sandbox is conferred by these Python interfaces.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time

from cognitum.planning import (_task, _decode, _encode, _certify, _goal,
                               replay_plan, export_pddl_frame, MAX_TIME_MS)
from cognitum.proto import planning_pb2 as p
from cognitum.proto import planning_engines_pb2 as e

MAX_ENGINE_FRAME = 131072
MAX_PLAN_BYTES = 8192
MAX_PLAN_STEPS = 512
PLAN_LINE = re.compile(r'^\(act(0|[1-9][0-9]{0,2})\)$')
BACKENDS = ('fast-downward', 'unified-planning')


@dataclass(frozen=True)
class EnginePolicy:
    backend_id: str
    driver: Path
    driver_sha256: str
    enabled: bool = False
    python_executable: str = sys.executable
    # The host, never the model, selects this reviewed fixed configuration.
    search_configuration: str = 'lama-first'
    max_deadline_ms: int = MAX_TIME_MS


def pinned_policy(backend_id, driver, *, enabled=False, search_configuration=None):
    if backend_id not in BACKENDS:
        raise ValueError('UNSUPPORTED_BACKEND')
    driver = Path(driver).resolve(strict=True)
    return EnginePolicy(backend_id, driver, hashlib.sha256(driver.read_bytes()).hexdigest(),
                        enabled=enabled,
                        search_configuration=(search_configuration or
                            ('lama-first' if backend_id == 'fast-downward' else 'fast-downward')))


def _terminate(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()  # Windows child-tree containment requires Lu Job Objects.
    except (ProcessLookupError, PermissionError, OSError):
        try: proc.kill()
        except OSError: pass
    try: proc.communicate(timeout=1)
    except (OSError, subprocess.TimeoutExpired): pass


def _parse_plan(data, action_count):
    if not isinstance(data, bytes) or len(data) > MAX_PLAN_BYTES:
        raise ValueError('PLAN_TOO_LARGE')
    try: text=data.decode('ascii')
    except UnicodeError as exc: raise ValueError('NONASCII_PLAN') from exc
    found=[]
    for raw in text.splitlines():
        line=raw.strip()
        # Fast Downward output may contain comment-cost/metric lines.
        if not line or line.startswith(';'):
            continue
        match=PLAN_LINE.fullmatch(line)
        if not match:
            raise ValueError('INVALID_EXTERNAL_PLAN_SYNTAX')
        index=int(match.group(1))
        if index >= action_count:
            raise ValueError('UNKNOWN_EXTERNAL_ACTION')
        found.append(index)
        if len(found) > MAX_PLAN_STEPS:
            raise ValueError('PLAN_TOO_LONG')
    return found


def _result(frame, klass, classical, reason, start):
    return e.EngineResult(schema_version=1, request_sha256=hashlib.sha256(frame).digest(),
                          classical_request_sha256=hashlib.sha256(classical).digest(),
                          backend_id=klass, status=e.REJECTED, reason_code=reason,
                          interface_version='cognitum.planning.engines.v1',
                          wall_ns=time.monotonic_ns()-start)


def _validate_request(frame):
    req=_decode(frame, e.EngineRequest)
    if req.schema_version != 1 or req.backend_id not in BACKENDS or not (1 <= req.deadline_ms <= MAX_TIME_MS):
        raise ValueError('INVALID_ENGINE_REQUEST')
    classical=_decode(req.classical_request, p.PlanningRequest)
    task=_task(classical)
    return req, task


def _verify_worker_digest(policy):
    path=policy.driver.resolve(strict=True)
    if not path.is_file() or path.is_symlink():
        raise ValueError('UNTRUSTED_WORKER_PATH')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if len(policy.driver_sha256) != 64 or digest != policy.driver_sha256:
        raise ValueError('WORKER_ARTIFACT_MISMATCH')
    if policy.backend_id == 'fast-downward' and policy.search_configuration not in ('lama-first', 'seq-opt-lmcut'):
        raise ValueError('UNREVIEWED_SEARCH_CONFIGURATION')
    if policy.backend_id == 'unified-planning' and policy.search_configuration != 'fast-downward':
        raise ValueError('UNREVIEWED_SEARCH_CONFIGURATION')
    return path, bytes.fromhex(digest)


class ExternalPlannerRuntime:
    def __init__(self, policy):
        self.policy=policy
        self._disabled=threading.Event()
        self._lock=threading.Lock()
        self._active=set()

    def disable(self):
        self._disabled.set()
        with self._lock: live=tuple(self._active)
        for proc in live: _terminate(proc)

    def execute(self, frame: bytes, *, host_authorized=False, cancel_event=None) -> bytes:
        start=time.monotonic_ns()
        raw_frame=frame if isinstance(frame,bytes) else b''
        result=_result(raw_frame, self.policy.backend_id, b'', 'INVALID_REQUEST', start)
        proc=None
        try:
            if not isinstance(frame, bytes) or not (0 < len(frame) <= MAX_ENGINE_FRAME):
                raise ValueError('INVALID_REQUEST_FRAME')
            req, task=_validate_request(frame)
            result.classical_request_sha256=hashlib.sha256(req.classical_request).digest()
            if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
            if self._disabled.is_set() or not self.policy.enabled: raise ValueError('BACKEND_DISABLED')
            if req.backend_id != self.policy.backend_id: raise ValueError('BACKEND_NOT_HOST_ALLOWED')
            if req.deadline_ms > self.policy.max_deadline_ms: raise ValueError('DEADLINE_NOT_HOST_ALLOWED')
            path, digest=_verify_worker_digest(self.policy)
            result.worker_sha256=digest
            export=p.PddlExport.FromString(export_pddl_frame(req.classical_request,host_authorized=True))
            result.export_sha256=hashlib.sha256((export.domain_pddl+'\x00'+export.problem_pddl).encode()).digest()
            with tempfile.TemporaryDirectory(prefix='cognitum-pddl-') as work:
                domain=Path(work)/'domain.pddl'
                problem=Path(work)/'problem.pddl'
                plan=Path(work)/'sas_plan'
                domain.write_text(export.domain_pddl,encoding='ascii')
                problem.write_text(export.problem_pddl,encoding='ascii')
                if self.policy.backend_id=='fast-downward':
                    command=[self.policy.python_executable,str(path),'--alias',self.policy.search_configuration,
                             '--plan-file',str(plan),str(domain),str(problem)]
                else:
                    command=[self.policy.python_executable,'-I',str(path),str(domain),str(problem),
                             str(plan),self.policy.search_configuration]
                due=time.monotonic()+req.deadline_ms/1000
                proc=subprocess.Popen(command,cwd=work,stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                      start_new_session=(os.name=='posix'),close_fds=True)
                with self._lock: self._active.add(proc)
                try:
                    while True:
                        if self._disabled.is_set() or (cancel_event and cancel_event.is_set()):
                            result.status=e.UNKNOWN;result.reason_code='HOST_CANCELLED';_terminate(proc);break
                        left=due-time.monotonic()
                        if left<=0:
                            result.status=e.UNKNOWN;result.reason_code='HOST_DEADLINE_EXCEEDED';_terminate(proc);break
                        try:
                            output,_=proc.communicate(timeout=min(.05,left))
                            if self._disabled.is_set() or (cancel_event and cancel_event.is_set()):
                                result.status=e.UNKNOWN;result.reason_code='HOST_CANCELLED';break
                            if proc.returncode!=0:
                                result.status=e.UNKNOWN;result.reason_code=('HOST_CANCELLED' if self._disabled.is_set() or (cancel_event and cancel_event.is_set()) else 'BACKEND_NONZERO_EXIT');break
                            # FD may create several sas_plan.N variants for anytime search.
                            files=[plan]+[Path(work)/(f'sas_plan.{i}') for i in range(1,11)]
                            plans=[]
                            for candidate in files:
                                if candidate.is_symlink(): raise ValueError('SYMLINK_PLAN')
                                if candidate.is_file():
                                    if candidate.stat().st_size > MAX_PLAN_BYTES: raise ValueError('PLAN_TOO_LARGE')
                                    indices=_parse_plan(candidate.read_bytes(),len(task.actions))
                                    cost=replay_plan(task,indices)
                                    plans.append((cost,indices))
                            if not plans:
                                result.status=e.UNKNOWN;result.reason_code='NO_CHECKABLE_PLAN';break
                            cost,indices=min(plans,key=lambda x:x[0])
                            result.action_indices.extend(indices)
                            result.total_cost=cost
                            result.witness_verified=True
                            result.status=e.VERIFIED_PLAN
                            result.reason_code='PLAN_WITNESS_REPLAYED'
                            # Separate bounded reachable-state enumeration only; never
                            # claim external planner optimality on solver status alone.
                            certified,_=_certify(task,indices,p.VERIFIED_PLAN,due)
                            if certified:
                                result.status=e.VERIFIED_OPTIMAL
                                result.optimality_verified=True
                                result.reason_code='INDEPENDENT_FINITE_OPTIMALITY'
                            break
                        except subprocess.TimeoutExpired:
                            continue
                finally:
                    with self._lock: self._active.discard(proc)
                    _terminate(proc)
        except (ValueError, OSError, PermissionError, subprocess.SubprocessError) as exc:
            msg=str(exc)
            result.status=e.UNKNOWN if msg in ('INVALID_EXTERNAL_PLAN_SYNTAX','UNKNOWN_EXTERNAL_ACTION',
                          'INAPPLICABLE_ACTION','GOAL_NOT_REACHED','PLAN_TOO_LONG','PLAN_TOO_LARGE','NONASCII_PLAN',
                          'SYMLINK_PLAN','BACKEND_NONZERO_EXIT') else e.REJECTED
            result.reason_code=msg if msg in ('HOST_AUTHORIZATION_REQUIRED','BACKEND_DISABLED',
                  'BACKEND_NOT_HOST_ALLOWED','DEADLINE_NOT_HOST_ALLOWED','WORKER_ARTIFACT_MISMATCH',
                  'UNTRUSTED_WORKER_PATH','UNREVIEWED_SEARCH_CONFIGURATION','INVALID_REQUEST_FRAME',
                  'INVALID_ENGINE_REQUEST','INVALID_EXTERNAL_PLAN_SYNTAX','UNKNOWN_EXTERNAL_ACTION',
                  'INAPPLICABLE_ACTION','GOAL_NOT_REACHED','PLAN_TOO_LONG','PLAN_TOO_LARGE',
                  'NONASCII_PLAN','SYMLINK_PLAN') else 'BACKEND_EXECUTION_FAILED'
        result.wall_ns=time.monotonic_ns()-start
        return _encode(result,MAX_ENGINE_FRAME)


def verify_external_result(request_frame, result_frame, *, expected_worker_sha256=None):
    """Independent witness check. No trust in external status/proof assertions."""
    receipt=e.EngineReceipt(request_sha256=hashlib.sha256(request_frame).digest(),
                            result_sha256=hashlib.sha256(result_frame).digest())
    try:
        req,t=_validate_request(request_frame)
        result=_decode(result_frame,e.EngineResult)
        if (result.schema_version!=1 or result.request_sha256!=receipt.request_sha256 or
                result.classical_request_sha256!=hashlib.sha256(req.classical_request).digest() or
                result.backend_id!=req.backend_id or result.interface_version!='cognitum.planning.engines.v1' or
                (result.worker_sha256 and len(result.worker_sha256)!=32) or
                (result.export_sha256 and len(result.export_sha256)!=32)):
            raise ValueError('RESULT_BINDING_MISMATCH')
        if expected_worker_sha256 is not None and result.worker_sha256 != expected_worker_sha256:
            raise ValueError('WORKER_PROVENANCE_MISMATCH')
        if result.status in (e.VERIFIED_PLAN,e.VERIFIED_OPTIMAL):
            if not result.witness_verified or replay_plan(t,result.action_indices)!=result.total_cost:
                raise ValueError('INVALID_EXTERNAL_WITNESS')
            if not result.export_sha256 or not result.worker_sha256:
                raise ValueError('MISSING_ARTIFACT_BINDING')
            exp=p.PddlExport.FromString(export_pddl_frame(req.classical_request,host_authorized=True))
            if result.export_sha256!=hashlib.sha256((exp.domain_pddl+'\x00'+exp.problem_pddl).encode()).digest():
                raise ValueError('EXPORT_MISMATCH')
            if result.status==e.VERIFIED_OPTIMAL:
                if not result.optimality_verified or result.reason_code!='INDEPENDENT_FINITE_OPTIMALITY':
                    raise ValueError('UNSUPPORTED_PROOF_CLAIM')
                proved,checked=_certify(t,list(result.action_indices),p.VERIFIED_PLAN,
                                        time.monotonic()+MAX_TIME_MS/1000)
                receipt.reachable_states_checked=checked
                if not proved: raise ValueError('INVALID_OPTIMALITY')
                receipt.optimality_verified=True
            elif result.optimality_verified or result.reason_code!='PLAN_WITNESS_REPLAYED':
                raise ValueError('FORGED_ASSURANCE')
        elif result.status in (e.UNKNOWN,e.REJECTED):
            if result.witness_verified or result.optimality_verified or result.action_indices or result.total_cost:
                raise ValueError('FORGED_UNKNOWN_ASSURANCE')
            receipt.reason_code='NO_VERIFIED_WITNESS'
            return _encode(receipt,MAX_ENGINE_FRAME)
        else:
            raise ValueError('UNSUPPORTED_RESULT_STATUS')
        receipt.evidence_valid=True
        receipt.reason_code='VERIFIED'
    except (ValueError,TypeError) as exc:
        receipt.reason_code=str(exc)
    return _encode(receipt,MAX_ENGINE_FRAME)


def make_external_audit(request_frame,result_frame, *, expected_worker_sha256=None):
    res=_decode(result_frame,e.EngineResult)
    receipt=e.EngineReceipt.FromString(verify_external_result(
        request_frame,result_frame,expected_worker_sha256=expected_worker_sha256))
    return _encode(e.EngineAudit(schema_version=1,request_sha256=hashlib.sha256(request_frame).digest(),
             result_sha256=hashlib.sha256(result_frame).digest(),backend_id=res.backend_id,
             status=res.status,evidence_valid=receipt.evidence_valid,
             optimality_verified=receipt.optimality_verified,reason_code=receipt.reason_code,
             wall_ns=res.wall_ns,worker_sha256=res.worker_sha256,export_sha256=res.export_sha256))


def capability_manifest():
    msg=e.EngineManifest(schema_version=1)
    msg.backends.add(backend_id='fast-downward',engine='Fast Downward 26.6',
         license_note='GPL-3.0-or-later; packaging and distribution review required',
         supported_fragment='grounded STRIPS negative-preconditions/action-costs PDDL 2.2',
         available=False,runtime_tested=False,experimental=False)
    msg.backends.add(backend_id='unified-planning',engine='Unified Planning (optional local engine)',
         license_note='Apache-2.0 framework; separate solver licenses apply',
         supported_fragment='grounded STRIPS negative-preconditions/action-costs PDDL 2.2',
         available=False,runtime_tested=False,experimental=False)
    msg.manifest_sha256=hashlib.sha256(msg.SerializeToString(deterministic=True)).digest()
    return _encode(msg)


def verify_manifest(frame):
    try: return frame==capability_manifest()
    except (ValueError,TypeError):return False
