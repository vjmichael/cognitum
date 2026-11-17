"""Reconciliation negatives: unchanged modern wire, historical solver and shared deadline."""
import hashlib
from unittest.mock import patch

from cognitum.proto import formal_pb2 as modern, formal_solver_pb2 as legacy
from cognitum.proto import formal_backend_pb2 as b, formal_advanced_pb2 as a
from cognitum.formal_backend import ApprovedBackend,SolverRegistry
from cognitum.formal_session import run_session_frame,verify_session_frame

def wire(msg):return msg.SerializeToString(deterministic=True)

def test_distinct_modern_and_historical_protobuf_contracts():
    assert modern.VerifyRequest.DESCRIPTOR.full_name=="cognitum.formal.v1.VerifyRequest"
    assert legacy.SolveRequest.DESCRIPTOR.full_name=="cognitum.formal.v1.SolveRequest"
    assert modern.DESCRIPTOR.name=="cognitum/formal/v1/formal.proto"
    assert legacy.DESCRIPTOR.name=="cognitum/formal/v1/solve.proto"
    assert b.BackendRun.DESCRIPTOR.full_name=="cognitum.formal.backend.v1.BackendRun"
    assert a.SessionPlan.DESCRIPTOR.full_name=="cognitum.formal.advanced.v1.SessionPlan"

def fake_registry(tmp_path):
    path=tmp_path/"test-only"
    path.write_bytes(b"not an executable; runners supplied by test")
    return SolverRegistry((ApprovedBackend("z3-lib","z3-lib",str(path.resolve()),
                                         hashlib.sha256(path.read_bytes()).hexdigest()),))

def plan():
    p=a.SessionPlan(schema_version=1,backend_id="z3-lib",timeout_ms=1000)
    p.variables.add(name="x",sort=b.BOOL)
    p.steps.add(kind=a.SessionStep.CHECK)
    p.steps.add(kind=a.SessionStep.CHECK)
    return p

def test_aggregate_deadline_no_partial_checkpoint_publication(tmp_path):
    p=plan()
    clock=[10.0]
    calls=[]
    def status(*_):
        clock[0]+=.3
        return ["sat","sat"]
    def model(backend,script,timeout):
        calls.append(timeout)
        clock[0]+=.5
        return "sat\n((x true))\n"
    with patch("cognitum.formal_session.time.monotonic",side_effect=lambda:clock[0]):
        raw=run_session_frame(wire(p),fake_registry(tmp_path),host_authorized=True,
                              status_runner=status,model_runner=model)
    result=a.SessionResult.FromString(raw)
    assert len(calls)==2 and 0<calls[1]<calls[0]<1000
    assert not result.completed and not result.checkpoints
    assert result.reason_code=="SESSION_TIMEOUT"
    assert not a.SessionReceipt.FromString(verify_session_frame(wire(p),raw)).evidence_valid

def test_expired_status_budget_does_not_spawn_check_backend(tmp_path):
    p=plan()
    clock=[10.0]
    def status(*_):
        clock[0]+=1.1
        return ["sat","sat"]
    def no_model(*_):raise AssertionError("expired session dispatched")
    with patch("cognitum.formal_session.time.monotonic",side_effect=lambda:clock[0]):
        raw=run_session_frame(wire(p),fake_registry(tmp_path),host_authorized=True,
                              status_runner=status,model_runner=no_model)
    out=a.SessionResult.FromString(raw)
    assert not out.completed and not out.checkpoints and out.reason_code=="SESSION_TIMEOUT"

def test_truthy_non_boolean_host_authority_refused(tmp_path):
    p=plan()
    reg=fake_registry(tmp_path)
    q=b.BackendRun(schema_version=1,backend_id="z3-lib")
    def unexpected(*_):raise AssertionError("denied request dispatched")
    out=b.BackendResult.FromString(reg.run_frame(wire(q),host_authorized="yes",runner=unexpected))
    assert out.verdict==b.REJECTED
    response=a.SessionResult.FromString(run_session_frame(wire(p),reg,host_authorized="yes",status_runner=unexpected))
    assert response.reason_code=="HOST_AUTHORIZATION_REQUIRED" and not response.completed
