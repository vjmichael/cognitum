"""C14 P3C: optional, default-OFF EconML/casual-learn isolated worker candidate.

All frames are native Protobuf. A host-selected and SHA-pinned Python executable
is required; Python flags are NOT OS confinement attestation. Without an
actual isolated Lu host, no model-driven worker may be enabled in production.
External results are numeric/structural *candidates*, never causal proofs.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import hashlib
import math
import os
import subprocess
import sys
import tempfile
import time

from cognitum import causal_heterogeneity as het, causal_discovery as disc
from cognitum.causal_estimation import _decode
from cognitum.causal_dowhy_backend import sha256_file, _terminate
from cognitum.proto import (causal_mature_pb2 as m, causal_heterogeneity_pb2 as h,
                            causal_discovery_pb2 as d)

MAX_FRAME = 131072
MAX_REPLY = 32768
ECONML_VERSION = '0.17.0'
CAUSAL_LEARN_VERSION = '0.1.4.8'
BACKEND_NAMES = {m.ECONML_LINEAR_DML_0170:'econml-linear-dml-0170',
                 m.CAUSAL_LEARN_PC_0148:'causal-learn-pc-0148'}
BACKEND_PACKAGES = {m.ECONML_LINEAR_DML_0170:('econml', ECONML_VERSION),
                    m.CAUSAL_LEARN_PC_0148:('causal-learn', CAUSAL_LEARN_VERSION)}
ASSURANCE = 'MODEL_ASSUMPTIONS_UNVERIFIED_EXTERNAL_RESULT_CANDIDATE'

@dataclass(frozen=True)
class MatureWorkerPolicy:
    """Host-supplied only; model input cannot set or choose these values."""
    python_executable: str
    python_sha256: str
    worker_sha256: str
    dispatcher_sha256: str
    backend: int
    pinned_library_version: str
    enabled: bool = False
    host_isolation_attested: bool = False  # external Lu enforcement still required


def worker_source():
    return Path(__file__).with_name('causal_mature_worker.py')


def _parse(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_FRAME')
    req=_decode(raw,m.MatureCausalRequest)
    if (req.schema_version!=1 or req.backend not in BACKEND_NAMES or
        not 1<=req.timeout_ms<=30000 or not 1<=req.max_expanded_rows<=10000 or
        not 1<=req.seed<2**32 or not req.trace_id or len(req.trace_id)>64):
        raise ValueError('INVALID_MATURE_REQUEST')
    if req.backend==m.ECONML_LINEAR_DML_0170:
        if req.WhichOneof('task')!='conditional_effects':
            raise ValueError('BACKEND_TASK_MISMATCH')
        obj=req.conditional_effects
        if obj.method!=h.ECONML_CATE_OPTIONAL or obj.estimation.trace_id!=req.trace_id:
            raise ValueError('MATURE_METHOD_OR_TRACE_MISMATCH')
        nested=obj.SerializeToString(deterministic=True)
        parsed=het._parse_request(nested)
        if parsed[3]>req.max_expanded_rows:
            raise ValueError('EXPANDED_ROWS_OVER_BUDGET')
        # P3A exact standardization is a numerical reference, not truth.
        baseline=h.HeterogeneityRequest();baseline.CopyFrom(obj)
        baseline.method=h.REFERENCE_CONDITIONAL_STANDARDIZATION
        reference=het._calculate(baseline.SerializeToString(deterministic=True))
        if reference.status!=h.CONDITIONAL_EFFECTS_COMPUTED:
            raise ValueError('REFERENCE_ASSUMPTIONS_OR_OVERLAP_FAILED')
        return req,reference
    if req.WhichOneof('task')!='candidate_graph':
        raise ValueError('BACKEND_TASK_MISMATCH')
    obj=req.candidate_graph
    if obj.method!=d.CAUSAL_LEARN_PC_OPTIONAL or obj.trace_id!=req.trace_id:
        raise ValueError('MATURE_METHOD_OR_TRACE_MISMATCH')
    disc._parse(obj.SerializeToString(deterministic=True))
    if any(max(row.values[i] for row in obj.observations) -
           min(row.values[i] for row in obj.observations) < 1e-10
           for i in range(len(obj.variable_ids))):
        raise ValueError('DEGENERATE_DISCOVERY_VARIABLE')
    if (len(obj.variable_ids)>4 or obj.max_conditioning!=2 or obj.max_tests!=250 or
        len(obj.observations)>req.max_expanded_rows):
        raise ValueError('PC_COMPUTATIONAL_BUDGET_NOT_SUPPORTED')
    return req,None


def _fail(raw,status,reason,backend=0,trace='',start=None):
    out=m.MatureCausalResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        trace_id=trace,backend=backend,status=status,reason_code=reason,
        backend_id=BACKEND_NAMES.get(backend,''))
    out.wall_ns=time.monotonic_ns()-(start or time.monotonic_ns())
    return out.SerializeToString(deterministic=True)


def _result(req,raw,start):
    return m.MatureCausalResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
        trace_id=req.trace_id, backend=req.backend, backend_id=BACKEND_NAMES[req.backend],
        status=m.MATURE_INCONCLUSIVE,reason_code='NOT_COMPUTED',wall_ns=0)


def _compute_worker(raw):
    """Runs only in the separate worker process with a real installed library."""
    start=time.monotonic_ns()
    try:
        req,reference=_parse(raw)
    except Exception:
        return _fail(raw,m.MATURE_REQUEST_DENIED,'INVALID_MATURE_REQUEST',start=start)
    out=_result(req,raw,start)
    pkg,pinned=BACKEND_PACKAGES[req.backend]
    try:
        try: installed=version(pkg)
        except PackageNotFoundError:
            return _fail(raw,m.MATURE_BACKEND_UNAVAILABLE,'LIBRARY_NOT_INSTALLED',req.backend,req.trace_id,start)
        if installed!=pinned:
            return _fail(raw,m.MATURE_BACKEND_UNAVAILABLE,'LIBRARY_VERSION_MISMATCH',req.backend,req.trace_id,start)
        out.runtime_version=installed
        import numpy as np
        if req.backend==m.ECONML_LINEAR_DML_0170:
            from econml.dml import LinearDML
            from sklearn.ensemble import RandomForestRegressor,RandomForestClassifier
            src=req.conditional_effects
            adjustment=list(src.estimation.identification.adjustment)
            modifiers=list(src.modifier_indices)
            controls=[i for i in adjustment if i not in modifiers]
            rows=[]
            for r in src.estimation.observations:
                rows.extend([list(r.states)]*r.count)
            data=np.array(rows,dtype=float)
            treatment=src.estimation.identification.treatment
            outcome=src.estimation.identification.target
            X=data[:,modifiers]; W=data[:,controls] if controls else None
            # This is a limited CATE candidate, not independent causal identification.
            est=LinearDML(model_y=RandomForestRegressor(n_estimators=30,max_depth=5,
                        random_state=req.seed,n_jobs=1),
                        model_t=RandomForestClassifier(n_estimators=30,max_depth=5,
                        random_state=req.seed,n_jobs=1),
                        discrete_treatment=True,cv=2,random_state=req.seed)
            est.fit(data[:,outcome],data[:,treatment],X=X,W=W)
            for group in reference.subgroups:
                estimate=float(np.ravel(est.effect(X=np.asarray([group.modifier_states],dtype=float)))[0])
                if not math.isfinite(estimate) or abs(estimate)>2:
                    raise ValueError('UNSAFE_NONFINITE_OR_EXTREME_ESTIMATE')
                diff=abs(estimate-float(Fraction(group.estimated_effect)))
                out.effects.add(modifier_states=group.modifier_states,observations=group.observations,
                    estimated_effect=format(estimate,'.12g'),
                    reference_effect=group.estimated_effect,
                    absolute_reference_difference=format(diff,'.12g'))
            out.sample_count=len(data)
        else:
            from causallearn.search.ConstraintBased.PC import pc
            src=req.candidate_graph
            data=np.asarray([list(row.values) for row in src.observations],dtype=float)
            cg=pc(data,alpha=src.alpha,indep_test='fisherz',stable=True,
                  show_progress=False,verbose=False)
            adj=np.asarray(cg.G.graph)
            if adj.shape!=(len(src.variable_ids),len(src.variable_ids)):
                raise ValueError('UNEXPECTED_GRAPH_SHAPE')
            for i in range(len(src.variable_ids)):
                for j in range(i+1,len(src.variable_ids)):
                    if adj[i,j]!=0 or adj[j,i]!=0:
                        out.skeleton_edges.add(first=i,second=j)
            out.sample_count=len(data)
        out.status=m.MATURE_RESULT_CANDIDATE
        out.reason_code='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF'
        out.assurance=ASSURANCE
    except (ImportError,ModuleNotFoundError):
        return _fail(raw,m.MATURE_BACKEND_UNAVAILABLE,'LIBRARY_DEPENDENCY_UNAVAILABLE',req.backend,req.trace_id,start)
    except Exception:
        return _fail(raw,m.MATURE_INCONCLUSIVE,'EXTERNAL_BACKEND_EXECUTION_FAILED',req.backend,req.trace_id,start)
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def verify_mature_receipt(raw,reply):
    """Check frames and reference statistics/shape; does not prove estimation."""
    checked=False
    receipt=m.MatureCausalReceipt(request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req,reference=_parse(raw)
        out=_decode(reply,m.MatureCausalResult)
        if (out.schema_version!=1 or out.status!=m.MATURE_RESULT_CANDIDATE or
            out.request_sha256!=receipt.request_sha256 or out.trace_id!=req.trace_id or
            out.backend!=req.backend or out.backend_id!=BACKEND_NAMES[req.backend] or
            out.runtime_version!=BACKEND_PACKAGES[req.backend][1] or
            out.causal_assumptions_verified or out.orientations_published or
            out.assurance!=ASSURANCE or
            out.reason_code!='EXTERNAL_ESTIMATE_OR_SKELETON_NOT_CAUSAL_PROOF'):
            return receipt
        if req.backend==m.ECONML_LINEAR_DML_0170:
            if out.skeleton_edges or len(out.effects)!=len(reference.subgroups): return receipt
            if out.sample_count!=sum(r.count for r in req.conditional_effects.estimation.observations):
                return receipt
            for observed,expected in zip(out.effects,reference.subgroups):
                if (list(observed.modifier_states)!=list(expected.modifier_states) or
                    observed.observations!=expected.observations or
                    observed.reference_effect!=expected.estimated_effect):
                    return receipt
                v=float(observed.estimated_effect);dist=float(observed.absolute_reference_difference)
                if not math.isfinite(v) or abs(v)>2 or not math.isfinite(dist) or dist<0 or (
                    abs(dist-abs(v-float(Fraction(expected.estimated_effect))))>1e-8):
                    return receipt
        else:
            if out.effects or out.sample_count!=len(req.candidate_graph.observations):
                return receipt
            edges=[(e.first,e.second) for e in out.skeleton_edges]
            if (edges!=sorted(set(edges)) or any(i>=j or j>=len(req.candidate_graph.variable_ids)
                  for i,j in edges)):
                return receipt
        checked=True
    except Exception:
        pass
    receipt.request_bound_structure_checked=checked
    if checked: receipt.reason_code='REQUEST_BOUND_SHAPE_AND_SANITY_NOT_CAUSAL_PROOF'
    return receipt


def run_mature_frame(raw,*,host_authorized=False,enabled=False,worker_policy=None):
    start=time.monotonic_ns()
    try: req,_=_parse(raw)
    except Exception:
        return _fail(raw,m.MATURE_REQUEST_DENIED,'INVALID_MATURE_REQUEST',start=start)
    if not host_authorized:
        return _fail(raw,m.MATURE_REQUEST_DENIED,'HOST_AUTHORIZATION_REQUIRED',req.backend,req.trace_id,start)
    if not enabled:
        return _fail(raw,m.MATURE_REQUEST_DENIED,'MATURE_WORKER_DISABLED',req.backend,req.trace_id,start)
    if not worker_policy or not worker_policy.enabled:
        return _fail(raw,m.MATURE_BACKEND_UNAVAILABLE,'WORKER_POLICY_UNAVAILABLE',req.backend,req.trace_id,start)
    if not worker_policy.host_isolation_attested:
        return _fail(raw,m.MATURE_REQUEST_DENIED,'HOST_OS_ISOLATION_NOT_ATTESTED',req.backend,req.trace_id,start)
    if (worker_policy.backend!=req.backend or
        worker_policy.pinned_library_version!=BACKEND_PACKAGES[req.backend][1]):
        return _fail(raw,m.MATURE_REQUEST_DENIED,'WORKER_BACKEND_PIN_MISMATCH',req.backend,req.trace_id,start)
    try:
        # Preserve the configured virtual-environment executable for launch.
        # Resolving bin/python may switch to system Python and lose its packages.
        py=Path(worker_policy.python_executable)
        if not py.is_absolute() or ".." in py.parts:
            raise ValueError("WORKER_EXECUTABLE_PATH_INVALID")
        py.resolve(strict=True)  # validate target without replacing launch path
        worker=worker_source().resolve(strict=True)
        dispatcher=Path(__file__).resolve(strict=True)
        if not all(x.is_file() for x in (py,worker,dispatcher)) or any(
            sha256_file(path)!=digest for path,digest in ((py,worker_policy.python_sha256),
                (worker,worker_policy.worker_sha256),(dispatcher,worker_policy.dispatcher_sha256))):
            raise ValueError('WORKER_INTEGRITY_MISMATCH')
        env={k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','WINDIR','HOME','LD_LIBRARY_PATH')}
        env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                   NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryFile() as spool:
            proc=subprocess.Popen([str(py),'-I',str(worker)],cwd=str(dispatcher.parents[1]),
                env=env,stdin=subprocess.PIPE,stdout=spool,stderr=subprocess.DEVNULL,
                start_new_session=(os.name!='nt'))
            try:proc.communicate(input=raw,timeout=req.timeout_ms/1000)
            except subprocess.TimeoutExpired:
                _terminate(proc)
                return _fail(raw,m.MATURE_TIMEOUT,'WORKER_TIMEOUT_KILLED',req.backend,req.trace_id,start)
            if proc.returncode:
                return _fail(raw,m.MATURE_INCONCLUSIVE,'WORKER_PROCESS_FAILED',req.backend,req.trace_id,start)
            if spool.tell()>MAX_REPLY:raise ValueError('WORKER_OUTPUT_LIMIT')
            spool.seek(0);reply=spool.read(MAX_REPLY+1)
        if len(reply)>MAX_REPLY:raise ValueError('WORKER_OUTPUT_LIMIT')
        out=_decode(reply,m.MatureCausalResult)
        if (out.schema_version!=1 or out.request_sha256!=hashlib.sha256(raw).digest() or
            out.trace_id!=req.trace_id or out.backend!=req.backend or
            out.backend_id!=BACKEND_NAMES[req.backend]):
            raise ValueError('WORKER_REPLY_INTEGRITY_MISMATCH')
        if out.status==m.MATURE_RESULT_CANDIDATE:
            if not verify_mature_receipt(raw,reply).request_bound_structure_checked:
                raise ValueError('UNVERIFIED_WORKER_RESULT')
        elif (out.status not in (m.MATURE_BACKEND_UNAVAILABLE,m.MATURE_NOT_SUPPORTED,
                                 m.MATURE_INCONCLUSIVE,m.MATURE_TIMEOUT) or
              out.reason_code not in ('LIBRARY_NOT_INSTALLED','LIBRARY_VERSION_MISMATCH',
                                      'LIBRARY_DEPENDENCY_UNAVAILABLE',
                                      'EXTERNAL_BACKEND_EXECUTION_FAILED') or
              out.effects or out.skeleton_edges or out.assurance or
              out.causal_assumptions_verified or out.orientations_published or
              out.sample_count or out.runtime_version):
            raise ValueError('FAILED_REPLY_CONTAINS_RESULT')
        return reply
    except (OSError,ValueError,TypeError,subprocess.SubprocessError) as exc:
        reasons={'WORKER_INTEGRITY_MISMATCH','WORKER_EXECUTABLE_PATH_INVALID','WORKER_OUTPUT_LIMIT',
                 'WORKER_REPLY_INTEGRITY_MISMATCH','UNVERIFIED_WORKER_RESULT',
                 'FAILED_REPLY_CONTAINS_RESULT'}
        reason=str(exc) if str(exc) in reasons else 'WORKER_LAUNCH_FAILED'
        return _fail(raw,m.MATURE_INCONCLUSIVE,reason,req.backend,req.trace_id,start)


def mature_audit(raw,reply):
    out=_decode(reply,m.MatureCausalResult)
    return m.MatureCausalAudit(request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(reply).digest(),trace_id=out.trace_id,
        backend=out.backend,status=out.status,backend_id=out.backend_id,
        runtime_version=out.runtime_version,reason_code=out.reason_code,wall_ns=out.wall_ns)
