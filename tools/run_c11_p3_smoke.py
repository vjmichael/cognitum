"""Focused C11 P3 smoke: no model, benchmark, host authentication or Lu dispatch."""
from cognitum.optimization_runtime import (
    OptimizationWorkerRuntime, capability_manifest, fixed_worker_policy,
    verify_execution_shape, verify_manifest,
)
from cognitum.proto import workflows_pb2 as wf, optimization_runtime_pb2 as rt


def wire(x):
    return x.SerializeToString(deterministic=True)


def smoke():
    assert verify_manifest(capability_manifest())
    req = wf.WorkflowRequest(schema_version=1, trace_id='C11P3Smoke', timeout_ms=3000)
    req.assignment.workers=2
    req.assignment.jobs=2
    req.assignment.edges.add(worker=0,job=0,cost=1)
    req.assignment.edges.add(worker=0,job=1,cost=8)
    req.assignment.edges.add(worker=1,job=0,cost=8)
    req.assignment.edges.add(worker=1,job=1,cost=2)
    frame=wire(req)
    denied = rt.ExecutionEnvelope.FromString(OptimizationWorkerRuntime(fixed_worker_policy(enabled=True)).execute(frame))
    assert denied.record.outcome==rt.DENIED
    disabled = rt.ExecutionEnvelope.FromString(OptimizationWorkerRuntime(fixed_worker_policy()).execute(frame,host_authorized=True))
    assert disabled.record.outcome==rt.DENIED
    runtime=OptimizationWorkerRuntime(fixed_worker_policy(enabled=True))
    output=runtime.execute(frame,host_authorized=True)
    envelope=rt.ExecutionEnvelope.FromString(output)
    assert envelope.record.outcome==rt.COMPLETED
    assert verify_execution_shape(frame,output)
    assert envelope.record.optimality_verified
    assert wf.WorkflowResult.FromString(envelope.result_frame).objective_value==3
    runtime.disable()
    post = rt.ExecutionEnvelope.FromString(runtime.execute(frame,host_authorized=True))
    assert post.record.outcome==rt.DENIED
    print('PASS: 5/5 C11 P3 targeted smoke assertions; no benchmarks or Lu host execution')


if __name__=='__main__':smoke()
