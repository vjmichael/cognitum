"""ORCH-01A native and inherited COG-06 graph-safety acceptance."""
from dataclasses import FrozenInstanceError, replace
import pytest
from cognitum.cooperative import Dependency, SourceStamp, execute, plan_digest
from cognitum.cooperative_cpu import ROUTES, CooperativeCpu, sha, type_url, wire
from cognitum.contracts import HostContext
from cognitum.orc_graph import ScientificTask, catalog, reviewed_edges, route
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.proto import specialists_pb2 as maths, formal_pb2 as formal

BUILD = "a" * 40
CTX = HostContext("workspace", "user")


def linear(action="solve"):
    q = maths.LinearRequest(action=action)
    q.a.add(entries=["2"])
    if action == "solve": q.b.add(entries=["6"])
    return wire(q)


def integer(backend="exhaustive", proof=True):
    q = formal.VerifyRequest(schema_version=1, backend=backend,
                             timeout_ms=1000, proof_required=proof)
    q.variables.add(name="x",lower=0,upper=5)
    atom = q.constraints.add(relation="ge",rhs=1)
    atom.terms.add(name="x",coefficient=1)
    return wire(q)


def task(goal="exact_linear", frames=None):
    f = frames if frames is not None else (
        (linear(),) if goal == "exact_linear" else (linear(),integer()))
    return ScientificTask(goal,f,tuple(SourceStamp("data"+str(i),"r1",sha(raw) if type(raw) is bytes else "0"*64)
                                        for i,raw in enumerate(f)))


def compile_task(t=None,**kwargs):
    return route(t if t is not None else task(),plan_id="orc",
                 workspace_id="workspace",subject_id="user",
                 build_sha=kwargs.pop("build_sha",BUILD),**kwargs)


def runtime(enabled=True):
    r = Registry()
    m = r.install(CooperativeCpu,enabled=enabled)
    for op in m.operations: r.nominate(op.slot,m.name)
    return Runtime(r)


def run(p,*,rt=None,context=CTX,build=BUILD,
        admit=lambda claim,ctx: True,
        source_current=lambda source,ctx: True,cancelled=lambda: False):
    return execute(rt if rt is not None else runtime(),p.plan,context,
                   expected_build_sha=build,admit=admit,
                   source_current=source_current,cancelled=cancelled)


def test_catalog_matches_original_reviewed_route_hashes():
    items={x.operation:x for x in catalog()}
    assert len(items)==len(ROUTES)+4
    for name,r in ROUTES.items():
        x=items[name]
        assert x.route_sha256==r.identity
        assert x.input_type_url==type_url(r.input_class)
        assert x.output_type_url==type_url(r.output_class)
        assert x.assurances==r.assurances
        assert x.eligibility=="existing_host_admission_required"
        assert not x.execution_authorized


def test_research_sources_visible_but_not_executable():
    items={x.operation:x for x in catalog()}
    for name in ("research.hdc","research.kan","research.ssm","statistical.ridge"):
        x=items[name]
        assert x.route_sha256 is None and x.input_type_url is None
        assert x.eligibility=="not_wired_or_authorized" and not x.execution_authorized


def test_existing_bridge_inventory_is_unchanged():
    from cognitum.cooperative import BRIDGES
    assert dict((n,(a,b)) for n,a,b in reviewed_edges())==dict(BRIDGES)


def test_compiled_plan_is_inert_and_deterministic():
    p,q=compile_task(),compile_task()
    assert p.plan_sha256==q.plan_sha256 and not p.execution_authorized
    assert p.route_names==("math.linear",)
    with pytest.raises(FrozenInstanceError): p.plan_sha256="forged"


def test_exact_linear_real_runtime_and_verification():
    p=compile_task();phases=[]
    out=run(p,admit=lambda claim,ctx: phases.append(claim.phase) or True)
    assert out.status=="completed",out
    assert len(out.receipts)==1 and out.receipts[0].assurance=="exact_linear_checked"
    assert maths.LinearResult.FromString(out.receipts[0].frame).rows[0].entries[0]=="3"
    assert phases==["plan","compute","verify","publish"]


def test_real_two_node_linear_integer_graph():
    p=compile_task(task("verified_integer_linear"))
    out=run(p)
    assert out.status=="completed",out
    assert [r.step_id for r in out.receipts]==["linear","integer"]
    assert out.receipts[1].assurance=="witness_rechecked"
    assert list(formal.VerifyResult.FromString(out.receipts[1].frame).witness)==[3]
    assert out.receipts[1].predecessor_receipts==(out.receipts[0].receipt_sha256,)


@pytest.mark.parametrize("goal",["","research.hdc","research.kan","research.ssm",
                                 "statistical.ridge","python.exec","temporal.kalman"])
def test_unknown_goal_refused(goal):
    with pytest.raises(ValueError,match="unreviewed scientific goal"): task(goal)


@pytest.mark.parametrize("frames",[[],[linear()],(),("wrong",),(b"",),
                                   (b"corrupted",),(linear(),linear())])
def test_wrong_input_shape_or_wire_refused(frames):
    with pytest.raises(ValueError):
        compile_task(task(frames=frames))


@pytest.mark.parametrize("action",["determinant","multiply"])
def test_unsolved_bridge_refused(action):
    with pytest.raises(ValueError,match="requires solved"):
        compile_task(task("verified_integer_linear",(linear(action),integer())))


@pytest.mark.parametrize("backend,proof",[("z3",True),("exhaustive",False)])
def test_nonexhaustive_integer_bridge_refused(backend,proof):
    with pytest.raises(ValueError,match="exhaustive"):
        compile_task(task("verified_integer_linear",(linear(),integer(backend,proof))))


def test_source_stamp_tamper_refused():
    t=task()
    with pytest.raises(ValueError):
        compile_task(replace(t,sources=(replace(t.sources[0],frame_sha256="0"*64),)))


def test_scope_build_and_research_denials_remain():
    with pytest.raises(ValueError): compile_task(build_sha="not_sha")
    p=compile_task()
    assert run(p,context=HostContext("other","user")).status=="denied"
    assert run(p,context=replace(CTX,allow_research=True)).status=="denied"
    assert run(p,build="b"*40).status=="denied"


def test_registry_and_host_admission_remain_authoritative():
    p=compile_task()
    assert run(p,rt=runtime(False)).status=="unavailable"
    assert run(p,admit=lambda claim,ctx: False).status=="denied"


def test_revoked_source_and_cancel_suppress_publication():
    p=compile_task(task("verified_integer_linear"))
    assert run(p,source_current=lambda source,ctx: False).status=="stale_source"
    assert run(p,cancelled=lambda: True).status=="cancelled"


def test_unknown_operation_or_bridge_refused_before_dispatch():
    p=compile_task(task("verified_integer_linear"))
    a,b=p.plan.steps
    with pytest.raises(ValueError): plan_digest(replace(p.plan,steps=(a,replace(b,operation="research.ssm"))))
    with pytest.raises(ValueError): plan_digest(replace(p.plan,steps=(a,replace(b,dependencies=(Dependency("linear","unreviewed"),)))))


def test_graph_cycle_refused_before_dispatch():
    p=compile_task(task("verified_integer_linear"))
    a,b=p.plan.steps
    with pytest.raises(ValueError,match="dependency cycle"):
        plan_digest(replace(p.plan,steps=(replace(a,dependencies=(Dependency("integer","requires_verified"),)),b)))


def test_no_second_runtime_registry_or_worker():
    import cognitum.orc_graph as orc
    assert not hasattr(orc,"execute") and not hasattr(orc,"Registry")
