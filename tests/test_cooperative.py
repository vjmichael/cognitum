"""Actual existing-runtime graph execution plus adversarial admission tests."""
from dataclasses import replace
from hashlib import sha256
import pytest
from cognitum.contracts import HostContext
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.cooperative_cpu import (
    ROUTES,CooperativeCpu,catalog,wire,sha,type_url,compute,verify,
)
from cognitum.cooperative import (
    Plan,Step,SourceStamp,Dependency,execute,plan_digest,MAX_NODES,
)
from cognitum.proto import specialists_pb2 as math,formal_pb2 as formal
from cognitum.proto import planning_pb2 as planning,optimization_pb2 as opt
from cognitum.proto import probability_pb2 as prob

BUILD="a"*40
CTX=HostContext("workspace","user")

def runtime(*,enabled=True):
    registry=Registry()
    manifest=registry.install(CooperativeCpu,enabled=enabled)
    for op in manifest.operations:registry.nominate(op.slot,manifest.name)
    return Runtime(registry)

def node(name,operation,msg,parents=(),timeout=10000):
    r=ROUTES[operation]
    frame=wire(msg)
    return Step(name,operation,type_url(r.input_class),r.identity,frame,
                SourceStamp("fixture-"+name,"r1",sha(frame)),timeout,parents)

def graph(*steps,timeout=30000):
    return Plan("graph","workspace","user",BUILD,timeout,steps)

def linear(rhs="6"):
    q=math.LinearRequest(action="solve")
    q.a.add(entries=["2"]);q.b.add(entries=[rhs])
    return node("linear","math.linear",q)

def integer(parent=True):
    q=formal.VerifyRequest(schema_version=1,backend="exhaustive",
                           timeout_ms=1000,proof_required=True)
    q.variables.add(name="x",lower=0,upper=5)
    a=q.constraints.add(relation="ge",rhs=1);a.terms.add(name="x",coefficient=1)
    deps=(Dependency("linear","linear_integer_candidate"),) if parent else ()
    return node("formal","formal.integer",q,deps)

def run(rt,p,**kwargs):
    auth=kwargs.pop("admit",lambda claim,ctx:True)
    fresh=kwargs.pop("source_current",lambda source,ctx:True)
    stop=kwargs.pop("cancelled",lambda:False)
    return execute(rt,p,kwargs.pop("context",CTX),expected_build_sha=kwargs.pop("build",BUILD),
                   admit=auth,source_current=fresh,cancelled=stop,**kwargs)

def test_actual_linear_formal_dependency():
    rt=runtime();claims=[]
    p=graph(integer(),linear())
    def approve(claim,ctx):
        claims.append(claim)
        return True
    out=run(rt,p,admit=approve)
    assert out.status=="completed",out
    assert [x.step_id for x in out.receipts]==["linear","formal"]
    a,b=out.receipts
    assert math.LinearResult.FromString(a.frame).rows[0].entries[0]=="3"
    result=formal.VerifyResult.FromString(b.frame)
    assert result.status=="SAT" and list(result.witness)==[3]
    assert b.predecessor_receipts==(a.receipt_sha256,)
    assert b.request_sha256!=p.steps[0].source.frame_sha256
    assert b.request_sha256==result.request_sha256
    assert b.assurance=="witness_rechecked"
    assert [c.phase for c in claims]==["plan","compute","verify","compute","verify","publish"]
    assert claims[2].result_sha256==a.result_sha256
    assert claims[4].result_sha256==b.result_sha256
    assert claims[-1].predecessor_receipts==(a.receipt_sha256,b.receipt_sha256)
    assert plan_digest(p)==plan_digest(graph(*reversed(p.steps)))

def test_real_planning_schedule_dependency():
    q=planning.PlanRequest(schema_version=1,facts=["raw","processed","done"],
          initial=["raw"],goal=["done"],horizon=3,risk_budget=0,algorithm="dijkstra")
    q.actions.add(name="prepare",requires=["raw"],add=["processed"],cost=1)
    q.actions.add(name="finish",requires=["processed"],add=["done"],cost=1)
    s=opt.ScheduleRequest(schema_version=1,unit="slot",horizon=8,resources=["r1","r2"],timeout_ms=3000)
    for name in ("finish","prepare"):
        s.jobs.add(name=name,duration=2,deadline=8,eligible_resources=["r1","r2"])
    p=graph(node("plan","planning.graph",q),
            node("schedule","optimization.schedule",s,(Dependency("plan","plan_schedule_precedence"),)))
    out=run(runtime(),p)
    assert out.status=="completed",out
    a,b=out.receipts
    assert list(planning.PlanResult.FromString(a.frame).actions)==["prepare","finish"]
    jobs={x.name:x for x in opt.ScheduleResult.FromString(b.frame).assignments}
    assert jobs["finish"].start>=jobs["prepare"].end
    assert b.assurance=="feasibility_checked"
    assert b.predecessor_receipts==(a.receipt_sha256,)

def test_invalid_graphs_never_dispatch():
    rt=runtime();calls=[]
    a=linear();b=integer()
    cycle=replace(a,dependencies=(Dependency("formal","requires_verified"),))
    invalid=[graph(a,cycle),graph(b),graph(cycle,b),
             graph(a,replace(b,input_type_url=a.input_type_url)),
             graph(a,replace(b,route_sha256="0"*64)),
             graph(a,replace(b,dependencies=(Dependency("linear","plan_schedule_precedence"),))),
             graph(replace(a,source=replace(a.source,frame_sha256="0"*64))),
             graph(replace(a,frame=a.frame+b"\\x98\\x06\\x01")),
             graph(replace(a,operation="research.hdc")),
             graph(*[replace(a,step_id="x"+str(i)) for i in range(MAX_NODES+1)])]
    for p in invalid:
        out=run(rt,p,admit=lambda c,x:calls.append(c) or True)
        assert out.status=="invalid_plan" and out.receipts==()
    assert calls==[]

def test_scope_build_and_registry_gates():
    p=graph(linear())
    assert run(runtime(),p,context=HostContext("other","user")).status=="denied"
    assert run(runtime(),p,build="b"*40).status=="denied"
    assert run(runtime(),p,context=replace(CTX,allow_research=True)).status=="denied"
    assert run(runtime(enabled=False),p).status=="unavailable"
    assert run(runtime(),p,admit=lambda c,x:1).status=="denied"
    assert all(not r["default_enabled"] and not r["execution_authorized"] for r in catalog())

def test_denial_staleness_and_cancel_discard_previous_outputs():
    p=graph(linear(),integer())
    rt=runtime();seen=[]
    def deny(claim,ctx):
        seen.append((claim.step_id,claim.phase))
        return not (claim.step_id=="formal" and claim.phase=="compute")
    out=run(rt,p,admit=deny)
    assert out.status=="denied" and out.failed_step=="formal" and out.receipts==()
    assert ("linear","verify") in seen
    state={"fresh":True}
    def invalidate(claim,ctx):
        if claim.phase=="verify":state["fresh"]=False
        return True
    out=run(rt,p,admit=invalidate,source_current=lambda s,c:state["fresh"])
    assert out.status=="stale_source" and out.receipts==()
    state={"cancel":False}
    def cancel_publish(claim,ctx):
        if claim.phase=="publish":state["cancel"]=True
        return True
    out=run(rt,graph(linear()),admit=cancel_publish,cancelled=lambda:state["cancel"])
    assert out.status=="cancelled" and out.receipts==()

def test_bridge_nonintegral_and_verified_contradiction():
    out=run(runtime(),graph(linear("5"),integer()))
    assert out.status=="bridge_failed" and out.receipts==()
    out=run(runtime(),graph(linear("12"),integer()))
    assert out.status=="completed",out
    proof=formal.VerifyResult.FromString(out.receipts[-1].frame)
    assert proof.status=="UNSAT_EXHAUSTIVE"
    assert out.receipts[-1].assurance=="independent_exhaustion"

def test_tampered_result_and_nonfinite_refused():
    q=linear()
    result=math.LinearResult.FromString(compute(q.operation,q.frame))
    result.rows[0].entries[0]="4"
    with pytest.raises(ValueError):verify(q.operation,q.frame,wire(result))
    from tests.test_c13_wire import beta_case
    raw=beta_case()
    p=prob.BetaResult.FromString(compute("probability.beta",raw))
    p.alpha_posterior=float("nan")
    with pytest.raises(ValueError):verify("probability.beta",raw,wire(p))

def test_budget_cannot_be_extended_and_publish_gate_is_required():
    p=graph(linear(),timeout=1)
    # No dependence on scheduler speed: deterministic deadline progression.
    from unittest.mock import patch
    with patch("cognitum.cooperative.monotonic",side_effect=[1.,2.]):
        out=run(runtime(),p)
    assert out.status=="timed_out" and out.receipts==()
    out=run(runtime(),graph(linear()),admit=lambda c,x:c.phase!="publish")
    assert out.status=="denied" and out.receipts==()

def test_existing_runtime_adapter_for_other_cpu_domains():
    # Original accepted fixtures for actual domain computation and verification.
    from tests.test_c11_wire import allocation_request
    from tests.test_c13_wire import bayes_case,beta_case
    from tests.test_c16_ode_wire import request
    from tests.test_c17_practical_wire import state_request,hmm_request
    cases=(("optimization.allocation",allocation_request()),
           ("probability.bayes",bayes_case()),("probability.beta",beta_case()),
           ("physics.ode",request()),("temporal.kalman",state_request()),
           ("temporal.hmm",hmm_request()))
    for i,(name,raw) in enumerate(cases):
        r=ROUTES[name];n=node("s"+str(i),name,r.input_class.FromString(raw))
        out=run(runtime(),graph(n))
        assert out.status=="completed",(name,out)
        assert out.receipts[0].assurance in r.assurances
