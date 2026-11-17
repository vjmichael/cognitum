"""COG-06D independent, bounded reference experiments (not an LLM benchmark).

Run with the original CPU worker runtime. Each arm is source-bound, separately
admitted and independently checked. Output is acceptance evidence, not a grant.
"""
from dataclasses import asdict
from itertools import product
from math import isclose,pi
from time import perf_counter
import json
import os
from pathlib import Path

from cognitum.contracts import HostContext
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.cooperative import Plan,Step,Dependency,SourceStamp,execute
from cognitum.cooperative_cpu import ROUTES,CooperativeCpu,wire,sha,type_url,parse
from cognitum.proto import (specialists_pb2 as math,formal_pb2 as formal,
    planning_pb2 as planning,optimization_pb2 as opt,probability_pb2 as prob,
    physics_ode_pb2 as physics,composition_pb2 as comp)

# Test-only build fallback; actual CI uses authenticated checkout SHA.
BUILD=os.environ.get("COG06B_EXPECTED_SHA","a"*40)
CONTEXT=HostContext("cog06d","fixture-owner")

def step(name,operation,msg,deps=()):
    route=ROUTES[operation];raw=wire(msg)
    return Step(name,operation,type_url(route.input_class),route.identity,raw,
                SourceStamp("fixture-"+name,"v1",sha(raw)),10000,deps)

def run_arm(name,*steps):
    registry=Registry();manifest=registry.install(CooperativeCpu,enabled=True)
    for op in manifest.operations:registry.nominate(op.slot,manifest.name)
    runtime=Runtime(registry);sources=frozenset(s.source for s in steps)
    plan=Plan(name,CONTEXT.workspace_id,CONTEXT.subject_id,BUILD,30000,steps)
    admissions=[]
    def admit(claim,ctx):
        admissions.append(asdict(claim))
        return ctx==CONTEXT and claim.build_sha==BUILD and claim.plan_id==name
    start=perf_counter()
    out=execute(runtime,plan,CONTEXT,expected_build_sha=BUILD,admit=admit,
                source_current=lambda stamp,ctx:ctx==CONTEXT and stamp in sources,
                cancelled=lambda:False)
    elapsed=perf_counter()-start
    assert out.status=="completed",out
    assert len(out.receipts)==len(steps)
    assert len(runtime.trace.events)==2*len(steps)
    assert all(e["execution_status"]=="completed" for e in runtime.trace.events)
    assert len(admissions)==2*len(steps)+2
    evidence={"plan_sha256":out.plan_sha256,"wall_seconds":elapsed,
              "templates":[{"step_id":s.step_id,"operation":s.operation,
                            "type_url":s.input_type_url,"frame_hex":s.frame.hex(),
                            "source":asdict(s.source),"dependencies":[asdict(d) for d in s.dependencies]} for s in steps],
              "receipts":[{**asdict(r),"frame":r.frame.hex()} for r in out.receipts],
              "admissions":admissions,"runtime_trace":runtime.trace.events}
    return out.receipts,evidence

def equations(total=12,weighted=29):
    req=formal.VerifyRequest(schema_version=1,backend="exhaustive",
                             timeout_ms=1000,proof_required=True)
    for n in ("x","y","z"):req.variables.add(name=n,lower=1,upper=9)
    for coefficients,rhs in [((1,1,1),total),((1,2,3),weighted)]:
        a=req.constraints.add(relation="eq",rhs=rhs)
        for n,c in zip(("x","y","z"),coefficients):a.terms.add(name=n,coefficient=c)
    for left,right in (("x","y"),("y","z")):
        a=req.constraints.add(relation="lt",rhs=0)
        a.terms.add(name=left,coefficient=1);a.terms.add(name=right,coefficient=-1)
    linear=math.LinearRequest(action="multiply")
    linear.a.add(entries=["2","-1"]);linear.a.add(entries=["-1","1"])
    linear.b.add(entries=["1","1","1",str(total)])
    linear.b.add(entries=["1","2","3",str(weighted)])
    return linear,req

def integer_experiment(total=12,weighted=29):
    linear,req=equations(total,weighted)
    # Independently calculate all triples directly in original problem.
    oracle=[(x,y,z) for x,y,z in product(range(1,10),repeat=3)
            if x<y<z and x+y+z==total and x+2*y+3*z==weighted]
    standalone_math,em=run_arm("math_only",step("linear","math.linear",linear))
    one,e1=run_arm("formal_single",step("witness","formal.integer",req))
    one= formal.VerifyResult.FromString(one[0].frame)
    assert (one.status=="SAT" and tuple(one.witness) in oracle) if oracle else one.status=="UNSAT_EXHAUSTIVE"
    direct,e2=run_arm("formal_set",step("complete","formal.solution_set",req))
    raw=comp.SolutionSet.FromString(direct[0].frame)
    assert [tuple(r.values) for r in raw.solutions]==oracle and raw.cases_checked==729
    combined,e3=run_arm("linear_formal",step("linear","math.linear",linear),
        step("complete","formal.solution_set",req,(Dependency("linear","linear_equivalent_equalities"),)))
    matrix=math.LinearResult.FromString(combined[0].frame)
    # Independent fixed row transform, including its original RHS binding.
    expected=[["1","0","-1",str(2*total-weighted)],
              ["0","1","2",str(weighted-total)]]
    assert [list(row.entries) for row in matrix.rows]==expected
    standalone_matrix=math.LinearResult.FromString(standalone_math[0].frame)
    assert standalone_matrix==matrix
    output=comp.SolutionSet.FromString(combined[1].frame)
    assert [tuple(r.values) for r in output.solutions]==oracle
    assert output.cases_checked==729 and output.status=="COMPLETE"
    assert output.request_sha256!=sha(wire(req))
    assert combined[1].predecessor_receipts==(combined[0].receipt_sha256,)
    # A row transform is not proof of a performance improvement.
    return {"oracle_solutions":oracle,"single_witness":list(one.witness),
            "standalone_complete":len(raw.solutions),"cooperative_complete":len(output.solutions),
            "enumerated_cases":729,"transformed_equalities":expected,
            "arms":{"standalone_math":em,"single_formal":e1,"standalone_formal_set":e2,"cooperative":e3}}

def planning_case():
    q=planning.PlanRequest(schema_version=1,facts=["raw","processed","done"],
          initial=["raw"],goal=["done"],horizon=3,risk_budget=0,algorithm="dijkstra")
    q.actions.add(name="prepare",requires=["raw"],add=["processed"],cost=1)
    q.actions.add(name="finish",requires=["processed"],add=["done"],cost=1)
    # Same durations/resources in both arms; no manually supplied precedence.
    s=opt.ScheduleRequest(schema_version=1,unit="slot",horizon=8,resources=["r1","r2"],timeout_ms=3000)
    for name in ("finish","prepare"):
        s.jobs.add(name=name,duration=2,deadline=8,eligible_resources=["r1","r2"])
    return q,s

def schedule_oracle(precedence):
    # Enumerate all starts and resources; no OR-Tools or planning engine.
    valid=[]
    for a,b,ra,rb in product(range(7),range(7),("r1","r2"),("r1","r2")):
        if precedence and b<a+2:continue
        if ra==rb and a<b+2 and b<a+2:continue
        valid.append(max(a+2,b+2))
    return min(valid)

def planning_experiment():
    q,s=planning_case()
    p,e1=run_arm("plan_only",step("plan","planning.graph",q))
    assert list(planning.PlanResult.FromString(p[0].frame).actions)==["prepare","finish"]
    d,e2=run_arm("schedule_only",step("schedule","optimization.schedule",s))
    d=opt.ScheduleResult.FromString(d[0].frame)
    c,e3=run_arm("plan_schedule",step("plan","planning.graph",q),
        step("schedule","optimization.schedule",s,(Dependency("plan","plan_schedule_precedence"),)))
    plan=planning.PlanResult.FromString(c[0].frame)
    assert list(plan.actions)==["prepare","finish"] and plan.total_cost==2 and plan.total_risk==0
    result=opt.ScheduleResult.FromString(c[1].frame)
    def replay(out,ordered):
        jobs={j.name:j for j in out.assignments}
        assert len(jobs)==2 and set(jobs)=={"prepare","finish"}
        assert all(j.resource in ("r1","r2") and 0<=j.start<j.end<=8 and j.end-j.start==2 for j in jobs.values())
        a,b=jobs["prepare"],jobs["finish"]
        assert a.resource!=b.resource or a.end<=b.start or b.end<=a.start
        consistent=a.end<=b.start
        if ordered:assert consistent
        assert out.makespan==max(a.end,b.end)
        return consistent
    assert not replay(d,False) and replay(result,True)
    assert d.makespan==schedule_oracle(False)==2
    assert result.makespan==schedule_oracle(True)==4
    assert c[1].predecessor_receipts==(c[0].receipt_sha256,)
    assert c[1].request_sha256!=sha(wire(s))
    return {"standalone_makespan":d.makespan,"standalone_plan_consistent":False,
            "cooperative_makespan":result.makespan,"cooperative_plan_consistent":True,
            "oracle_unconstrained":2,"oracle_with_precedence":4,
            "arms":{"planner":e1,"schedule_only":e2,"cooperative":e3}}

def physical_case(likelihood=(.8,.2)):
    q=prob.BayesRequest(schema_version=1,hypotheses=["low","high"],prior=[.5,.5],
        prior_source="fixture_prior",likelihood_source="fixture_likelihood",
        assumptions=["conditionally_independent_observations"])
    q.observations.add(name="signal",likelihood_by_hypothesis=likelihood,observed=True)
    mix=comp.MixtureRequest(schema_version=1,scenario_assumption="mutually_exclusive_exhaustive_scenarios")
    # Reverse order deliberately: hypothesis-to-scenario mapping must use IDs.
    for name,position in (("high",3.),("low",1.)):
        p=physics.PhysicalRequest(schema_version=1,kind="harmonic",unit_system="SI:m,s,kg,N",
            mass_kg=2,spring_n_per_m=8,initial_position_m=position,
            t_end_s=pi/6,output_steps=8,rtol=1e-9,atol=1e-11,method="DOP853",
            max_internal_step_s=.02,max_function_evals=20000,validation_domain="idealized_reference")
        mix.scenarios.add(name=name,physical_request=wire(p))
    return q,mix

def physical_experiment(likelihood=(.8,.2)):
    q,mix=physical_case(likelihood)
    probability,e1=run_arm("bayes_only",step("bayes","probability.bayes",q))
    posterior=prob.BayesResult.FromString(probability[0].frame)
    low=likelihood[0]/sum(likelihood);high=1-low
    assert isclose(posterior.posterior[0],low,abs_tol=1e-12)
    assert isclose(posterior.posterior[1],high,abs_tol=1e-12)
    # Prior-only C16 distribution is a matched baseline, same trajectories.
    prior=comp.MixtureRequest();prior.CopyFrom(mix);prior.weights.extend([.5,.5])
    prior_result,e2=run_arm("physics_prior",step("mixture","physics.mixture",prior))
    prior_result=comp.MixtureResult.FromString(prior_result[0].frame)
    records,e3=run_arm("bayes_physics",step("bayes","probability.bayes",q),
        step("mixture","physics.mixture",mix,(Dependency("bayes","bayes_scenario_weights"),)))
    result=comp.MixtureResult.FromString(records[1].frame)
    # Closed form: omega=2, terminal angle=pi/3, cos=1/2, v0=0.
    mu=.5*low+1.5*high;var=low*high*(1.5-.5)**2
    assert isclose(prior_result.mean_position_m,1.,abs_tol=1e-7)
    assert isclose(prior_result.variance_position_m2,.25,abs_tol=1e-7)
    assert isclose(result.mean_position_m,mu,abs_tol=1e-7)
    assert isclose(result.variance_position_m2,var,abs_tol=1e-7)
    assert [s.name for s in result.scenarios]==["high","low"]
    assert isclose(result.scenarios[0].weight,high,abs_tol=1e-12)
    assert isclose(result.scenarios[1].weight,low,abs_tol=1e-12)
    for s,x in zip(result.scenarios,(1.5,.5)):
        trajectory=physics.PhysicalResult.FromString(s.physical_result)
        assert isclose(trajectory.samples[-1].position_m,x,abs_tol=1e-7)
    assert records[1].predecessor_receipts==(records[0].receipt_sha256,)
    assert records[1].request_sha256!=sha(wire(mix))
    return {"posterior":[low,high],"prior_mean_m":prior_result.mean_position_m,
            "prior_variance_m2":prior_result.variance_position_m2,
            "cooperative_mean_m":result.mean_position_m,"cooperative_variance_m2":result.variance_position_m2,
            "analytic_mean_m":mu,"analytic_variance_m2":var,
            "arms":{"bayes_only":e1,"physics_prior":e2,"cooperative":e3}}

def main():
    if "COG06B_EXPECTED_SHA" not in os.environ:
        raise RuntimeError("acceptance run requires source-bound checkout identity")
    result={"schema":"cognitum.cog06d.composition-evidence.v1","source_sha":BUILD,
            "model_trial":False,"production_enabled":False,
            "integer":integer_experiment(),"planning":planning_experiment(),"physics":physical_experiment()}
    out=Path("cog06b-artifacts");out.mkdir(exist_ok=True)
    (out/"cross_component_evidence.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:{a:b for a,b in result[k].items() if a!="arms"} for k in ("integer","planning","physics")},allow_nan=False))

if __name__=="__main__":main()
