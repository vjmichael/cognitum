"""Five narrow C12 P4 functionality checks, not comparative benchmarks."""
import hashlib
from cognitum.proto import planning_pb2 as p
from cognitum.proto import planning_guidance_pb2 as g
from cognitum.planning_guidance import GuidanceRegistry, verify_guided_frame, frame, artifact_digest


def make():
    r=g.GuidedRequest(schema_version=1)
    t=r.planning
    t.schema_version=1;t.engine=p.ASTAR_HMAX;t.trace_id='smoke';t.timeout_ms=1500
    d=t.task
    d.facts.extend(['atA','atB','done']);d.initial_true.append(0);d.goal_true.append(2)
    d.max_states=64;d.max_expansions=64
    d.actions.add(id='step1',require_true=[0],add=[1],cost=1)
    d.actions.add(id='step2',require_true=[1],add=[2],cost=1)
    d.actions.add(id='slow',require_true=[0],add=[2],cost=8)
    a=r.guidance
    a.schema_version=1;a.backend_id='offline-transition-classifier-v1'
    a.source_reference='doi:10.3233/FAIA251375'
    a.model_sha256=hashlib.sha256(b'example-fixture').digest()
    a.hints.add(state_bits=1,action_index=0,label=g.PREDICTED_DEAD_END)
    a.content_sha256=artifact_digest(a)
    return r


def run():
    req=make(); pin=req.guidance.content_sha256
    reg=GuidanceRegistry(enabled=True,approved_artifact_digests={pin})
    good=g.GuidedResult.FromString(reg.solve_frame(frame(req),host_authorized=True))
    assert good.status==p.VERIFIED_OPTIMAL and good.total_cost==2
    assert g.GuidedReceipt.FromString(verify_guided_frame(frame(req),frame(good),trusted_artifact_sha256=pin)).optimality_verified
    print('PASS: optimum recovered despite false dead-end prediction')
    assert g.GuidedResult.FromString(reg.solve_frame(frame(req))).status==p.REJECTED
    print('PASS: host denial')
    reg.disable()
    assert g.GuidedResult.FromString(reg.solve_frame(frame(req),host_authorized=True)).status==p.REJECTED
    print('PASS: disable switch')
    assert not g.GuidedReceipt.FromString(verify_guided_frame(frame(req),frame(good))).evidence_valid
    print('PASS: unpinned advice cannot certify')
    forged=g.GuidedResult();forged.CopyFrom(good);forged.total_cost=20
    assert not g.GuidedReceipt.FromString(verify_guided_frame(frame(req),frame(forged),trusted_artifact_sha256=pin)).evidence_valid
    print('PASS: forged witness denied')

if __name__ == '__main__':run()
