"""COG-06D independent held-out compositions and fail-closed controls."""
from dataclasses import replace
from math import isclose
from unittest.mock import patch
import pytest

from cognitum.cooperative import Dependency
from cognitum.cooperative_cpu import compute,verify,wire,sha,parse
from cognitum.proto import composition_pb2 as comp,formal_pb2 as formal
from cognitum.proto import probability_pb2 as prob,physics_ode_pb2 as physics
from tools.cog06d_composition_evidence import (
    equations,integer_experiment,planning_experiment,physical_experiment,
    physical_case,planning_case,
)
from tests.test_cooperative import runtime,run,graph,node

def test_historical_complete_two_solution_set():
    result=integer_experiment()
    assert result["oracle_solutions"]==[(1,5,6),(2,3,7)]
    assert len(result["single_witness"])==3
    assert result["standalone_complete"]==result["cooperative_complete"]==2

@pytest.mark.parametrize("total,weighted",[(9,22),(12,12)])
def test_heldout_integer_sets_and_empty_complete_certificate(total,weighted):
    result=integer_experiment(total,weighted)
    assert result["standalone_complete"]==result["cooperative_complete"]
    if weighted==12:assert result["oracle_solutions"]==[]

def test_plan_schedule_independent_minimum_and_precedence():
    result=planning_experiment()
    assert result["standalone_makespan"]==2
    assert result["cooperative_makespan"]==4

@pytest.mark.parametrize("likelihood",[(.8,.2),(.25,.75),(1.,0.)])
def test_bayesian_physics_conditional_mixture(likelihood):
    result=physical_experiment(likelihood)
    p=likelihood[0]/sum(likelihood)
    assert isclose(result["cooperative_mean_m"],1.5-p,abs_tol=1e-7)
    assert isclose(result["cooperative_variance_m2"],p*(1-p),abs_tol=1e-7)

def test_incomplete_duplicate_and_forged_solution_sets_rejected():
    _,q=equations()
    raw=wire(q);frame=compute("formal.solution_set",raw)
    expected=comp.SolutionSet.FromString(frame)
    assert len(expected.solutions)==2
    for kind in ("missing","duplicate","wrong_value","wrong_count","wrong_request"):
        bad=comp.SolutionSet.FromString(frame)
        if kind=="missing":del bad.solutions[-1]
        elif kind=="duplicate":bad.solutions.add(values=bad.solutions[0].values)
        elif kind=="wrong_value":bad.solutions[0].values[0]=9
        elif kind=="wrong_count":bad.cases_checked=728
        else:bad.request_sha256="0"*64
        with pytest.raises(ValueError):verify("formal.solution_set",raw,wire(bad))

def test_case_and_result_bounds_do_not_publish_partial_sets():
    _,q=equations()
    del q.constraints[:]
    # 729 satisfying triples would exceed the maximum returned set.
    out=run(runtime(),graph(node("set","formal.solution_set",q)))
    assert out.status=="compute_failed" and not out.receipts
    for v in q.variables:v.upper=32
    out=run(runtime(),graph(node("set","formal.solution_set",q)))
    assert out.status=="compute_failed" and not out.receipts
    q.backend="z3"
    out=run(runtime(),graph(node("set","formal.solution_set",q)))
    assert out.status=="compute_failed" and not out.receipts

@pytest.mark.parametrize("fault",["singular","source_mismatch"])
def test_equivalence_bridge_refuses_non_equivalent_equations(fault):
    a,q=equations()
    if fault=="singular":a.a[1].entries[:]=["4","-2"]
    else:a.b[0].entries[-1]="13"
    out=run(runtime(),graph(node("linear","math.linear",a),
        node("set","formal.solution_set",q,(Dependency("linear","linear_equivalent_equalities"),))))
    assert out.status=="bridge_failed" and not out.receipts

@pytest.mark.parametrize("fault",["weights_override","missing_hypothesis","duplicate","impossible"])
def test_uncertainty_bridge_refuses_invalid_mapping(fault):
    q,mix=physical_case()
    if fault=="weights_override":mix.weights.extend([.5,.5])
    elif fault=="missing_hypothesis":mix.scenarios[1].name="other"
    elif fault=="duplicate":mix.scenarios[1].name=mix.scenarios[0].name
    else:q.observations[0].likelihood_by_hypothesis[:]=[0.,0.]
    out=run(runtime(),graph(node("bayes","probability.bayes",q),
         node("mix","physics.mixture",mix,(Dependency("bayes","bayes_scenario_weights"),))))
    if fault=="impossible":assert out.status in ("compute_failed","verification_failed")
    else:assert out.status=="bridge_failed"
    assert not out.receipts

def test_physics_mixture_forged_moments_weights_and_trajectory():
    _,mix=physical_case()
    mix.weights.extend([.2,.8])
    raw=wire(mix);frame=compute("physics.mixture",raw)
    for kind in ("mean","variance","weight","name","trajectory","missing"):
        bad=comp.MixtureResult.FromString(frame)
        if kind=="mean":bad.mean_position_m+=.1
        elif kind=="variance":bad.variance_position_m2+=.1
        elif kind=="weight":bad.scenarios[0].weight=.5
        elif kind=="name":bad.scenarios[0].name="other"
        elif kind=="trajectory":
            p=physics.PhysicalResult.FromString(bad.scenarios[0].physical_result)
            p.samples[-1].position_m+=.01
            bad.scenarios[0].physical_result=wire(p)
        else:del bad.scenarios[-1]
        with pytest.raises(ValueError):verify("physics.mixture",raw,wire(bad))

def test_unsupported_physical_scenario_does_not_publish():
    q,mix=physical_case()
    p=physics.PhysicalRequest.FromString(mix.scenarios[0].physical_request)
    p.kind="damped";p.damping_n_s_per_m=1.
    mix.scenarios[0].physical_request=wire(p)
    out=run(runtime(),graph(node("bayes","probability.bayes",q),
         node("mix","physics.mixture",mix,(Dependency("bayes","bayes_scenario_weights"),))))
    assert out.status=="compute_failed" and not out.receipts

def test_conflicting_transferred_schedule_is_not_success():
    q,s=planning_case()
    # Reverse precedence is inconsistent with the verified plan.
    for j in s.jobs:
        if j.name=="prepare":j.after.append("finish")
    out=run(runtime(),graph(node("plan","planning.graph",q),
        node("schedule","optimization.schedule",s,(Dependency("plan","plan_schedule_precedence"),))))
    assert out.status=="compute_failed" and not out.receipts

def test_stale_source_at_final_cross_component_publication():
    a,q=equations();fresh={"ok":True}
    def admit(claim,ctx):
        if claim.phase=="publish":fresh["ok"]=False
        return True
    out=run(runtime(),graph(node("linear","math.linear",a),
         node("set","formal.solution_set",q,(Dependency("linear","linear_equivalent_equalities"),))),
         admit=admit,source_current=lambda s,c:fresh["ok"])
    assert out.status=="stale_source" and not out.receipts
