"""C12 independent conventional plan validation using Unified Planning.

This adapter converts ONLY validated declarative bounded facts/actions.
Unified Planning's built-in sequential validator checks symbolic semantics;
Cognitum's separate exact replay remains responsible for bounded risk/horizon
and cost. A VALID result alone is not model-intent or permission evidence.
"""
from .planning_graph import PlanProblem,validate,check_plan


def verify_with_unified_planning(p:PlanProblem,steps:tuple[str,...])->str:
    validate(p)
    if type(steps) is not tuple or any(type(name) is not str for name in steps):
        raise ValueError("typed plan sequence required")
    try:
        from unified_planning.shortcuts import (
            Problem,Fluent,BoolType,InstantaneousAction,Not,PlanValidator,
        )
        from unified_planning.plans import SequentialPlan,ActionInstance
        from unified_planning.engines import ValidationResultStatus
    except ImportError:
        return "UNSUPPORTED"
    problem=Problem("c12_bounded_symbolic")
    fluents={fact:Fluent("c12_"+fact,BoolType()) for fact in p.facts}
    for fact,fluent in fluents.items():
        problem.add_fluent(fluent,default_initial_value=False)
        if fact in p.initial:
            problem.set_initial_value(fluent,True)
    for fact in p.goal:
        problem.add_goal(fluents[fact])
    for fact in p.goal_forbids:
        problem.add_goal(Not(fluents[fact]))
    actions={}
    for action in p.actions:
        up_action=InstantaneousAction("c12_"+action.name)
        for fact in action.requires:
            up_action.add_precondition(fluents[fact])
        for fact in action.forbids:
            up_action.add_precondition(Not(fluents[fact]))
        for fact in action.add:
            up_action.add_effect(fluents[fact],True)
        for fact in action.delete:
            up_action.add_effect(fluents[fact],False)
        problem.add_action(up_action)
        actions[action.name]=up_action
    if any(name not in actions for name in steps):
        return "INVALID"
    candidate=SequentialPlan([ActionInstance(actions[name]) for name in steps])
    # A specific maintained in-library validator, not plugin auto-discovery.
    with PlanValidator(name="sequential_plan_validator") as validator:
        verdict=validator.validate(problem,candidate).status
    if verdict==ValidationResultStatus.INVALID:
        return "INVALID"
    if verdict!=ValidationResultStatus.VALID:
        return "UNKNOWN"
    # UP validates the Boolean action semantics; our exact checker additionally
    # enforces risk, step horizon, and cost, not represented in this UP model.
    return "VALID" if check_plan(p,steps) is not None else "INVALID"
