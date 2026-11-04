"""C12 bounded deterministic planning on a mature NetworkX graph engine.

All facts/actions are *declarative*, never executable programs or host effects.
Search results are checked through an independent action simulator. Optional
NetworkX performs A*/Dijkstra/BFS. A small horizon-layer DP is a reference
alternative on its acyclic, explicitly expanded graph (not a new planner).
"""
from dataclasses import dataclass

MAX_FACTS=12
MAX_ACTIONS=24
MAX_HORIZON=12
MAX_RISK=30
MAX_GRAPH_NODES=4096
MAX_GRAPH_EDGES=40000


@dataclass(frozen=True)
class Action:
    name: str
    requires: tuple[str,...] = ()
    forbids: tuple[str,...] = ()
    add: tuple[str,...] = ()
    delete: tuple[str,...] = ()
    cost: int = 1
    risk: int = 0


@dataclass(frozen=True)
class PlanProblem:
    facts: tuple[str,...]
    initial: tuple[str,...]
    goal: tuple[str,...]
    goal_forbids: tuple[str,...]
    actions: tuple[Action,...]
    horizon: int
    risk_budget: int = 0


@dataclass(frozen=True)
class PlanResult:
    status: str
    actions: tuple[str,...] = ()
    final_state: tuple[str,...] = ()
    total_cost: int | None = None
    total_risk: int | None = None
    expanded_states: int = 0
    backend: str = "networkx"
    assurance: str = "bounded_planning_reference"
    limitations: tuple[str,...] = (
        "state_and_actions_caller_supplied_not_authenticated",
        "no_real_world_effects_executed",
        "optimality_only_when_expanded_graph_complete",
    )


def validate(p: PlanProblem) -> PlanProblem:
    if type(p) is not PlanProblem or type(p.facts) is not tuple or type(p.actions) is not tuple:
        raise ValueError("typed planning problem required")
    def identifier(v):
        return type(v) is str and v.isascii() and v.isidentifier() and 1<=len(v)<=32
    if (not 1<=len(p.facts)<=MAX_FACTS or len(set(p.facts))!=len(p.facts)
            or any(not identifier(f) for f in p.facts)
            or not 1<=len(p.actions)<=MAX_ACTIONS
            or type(p.horizon) is not int or not 0<=p.horizon<=MAX_HORIZON
            or type(p.risk_budget) is not int or not 0<=p.risk_budget<=MAX_RISK):
        raise ValueError("planning domain limits")
    facts=set(p.facts)
    for subset in (p.initial,p.goal,p.goal_forbids):
        if (type(subset) is not tuple or len(subset)!=len(set(subset))
                or any(x not in facts for x in subset)):
            raise ValueError("invalid fact assignment or goal")
    if set(p.goal)&set(p.goal_forbids):
        raise ValueError("contradictory goal")
    names=set()
    for a in p.actions:
        if type(a) is not Action or not identifier(a.name) or a.name in names:
            raise ValueError("invalid action identity")
        names.add(a.name)
        for subset in (a.requires,a.forbids,a.add,a.delete):
            if (type(subset) is not tuple or len(subset)!=len(set(subset))
                    or any(x not in facts for x in subset)):
                raise ValueError("invalid action facts")
        if set(a.requires)&set(a.forbids) or set(a.add)&set(a.delete):
            raise ValueError("contradictory action preconditions or effects")
        if (type(a.cost) is not int or not 1<=a.cost<=100
                or type(a.risk) is not int or not 0<=a.risk<=10):
            raise ValueError("invalid action cost/risk")
    return p


def transition(p: PlanProblem, state: tuple[str,...], action: Action):
    """Re-evaluate preconditions and effects; returns None if inapplicable."""
    validate(p)
    if (type(state) is not tuple or len(set(state))!=len(state)
            or any(f not in p.facts for f in state)
            or type(action) is not Action or action not in p.actions):
        raise ValueError("invalid typed plan state/action")
    present=set(state)
    if not set(action.requires)<=present or set(action.forbids)&present:
        return None
    return tuple(f for f in p.facts if f in ((present-set(action.delete))|set(action.add)))


def goal_satisfied(p: PlanProblem, state: tuple[str,...]) -> bool:
    validate(p)
    present=set(state)
    return set(p.goal)<=present and not (set(p.goal_forbids)&present)


def check_plan(p: PlanProblem, steps: tuple[str,...]):
    """Independent full plan replay: no solver path or heuristics trusted.

    Returns (final_state, total_cost, total_risk) or None for invalid steps.
    Empty plan may be valid if initial state already satisfies the goal.
    """
    validate(p)
    if type(steps) is not tuple or len(steps)>p.horizon:
        return None
    by_name={a.name:a for a in p.actions}
    current=tuple(f for f in p.facts if f in p.initial)
    cost=risk=0
    for name in steps:
        if type(name) is not str or name not in by_name:
            return None
        a=by_name[name]
        nxt=transition(p,current,a)
        if nxt is None:
            return None
        cost+=a.cost
        risk+=a.risk
        if risk>p.risk_budget:
            return None
        current=nxt
    return (current,cost,risk) if goal_satisfied(p,current) else None


def _build_graph(p,nx):
    """Enumerate bounded reachable horizon/risk states; never pretend truncated
    expansion proves global optimality or unreachability."""
    g=nx.DiGraph()
    initial_bits=sum(1<<i for i,f in enumerate(p.facts) if f in p.initial)
    start=(initial_bits,0,0)
    terminal=("goal",)
    g.add_node(start)
    frontier=[start]
    seen={start}
    goals=[]
    name_to_bit={f:1<<i for i,f in enumerate(p.facts)}
    expanded=0
    truncated=False
    for node in frontier:
        bits,depth,risk=node
        expanded+=1
        if all(bits & name_to_bit[f] for f in p.goal) and all(
                not bits & name_to_bit[f] for f in p.goal_forbids):
            goals.append(node)
        if depth>=p.horizon:
            continue
        for action in p.actions:
            if (any(not (bits & name_to_bit[f]) for f in action.requires)
                    or any(bits & name_to_bit[f] for f in action.forbids)
                    or risk+action.risk>p.risk_budget):
                continue
            target_bits=bits
            for fact in action.delete:
                target_bits &= ~name_to_bit[fact]
            for fact in action.add:
                target_bits |= name_to_bit[fact]
            target=(target_bits,depth+1,risk+action.risk)
            if target not in seen and len(seen)>=MAX_GRAPH_NODES:
                truncated=True
                continue
            if g.number_of_edges()>=MAX_GRAPH_EDGES:
                truncated=True
                continue
            if target not in seen:
                seen.add(target)
                frontier.append(target)
            # Multiple actions can lead to same state; preserve lowest-cost
            # edge. Independent replay still checks the named action.
            previous=g.get_edge_data(node,target)
            if previous is None or action.cost<previous["weight"]:
                g.add_edge(node,target,weight=action.cost,action=action.name)
    for node in goals:
        g.add_edge(node,terminal,weight=0,action=None)
    return g,start,terminal,expanded,truncated


def _dag_path(g,nx,start,end):
    """Bounded horizon-layer dynamic programming on a DAG (no user code)."""
    dist={start:0}
    pred={}
    for node in nx.topological_sort(g):
        if node not in dist:
            continue
        for successor,data in g[node].items():
            new=dist[node]+data["weight"]
            if new<dist.get(successor,float("inf")):
                dist[successor]=new
                pred[successor]=node
    if end not in dist:
        raise nx.NetworkXNoPath
    output=[end]
    while output[-1]!=start:
        output.append(pred[output[-1]])
    return list(reversed(output))


def plan(p: PlanProblem, *, algorithm: str="dijkstra") -> PlanResult:
    validate(p)
    if algorithm not in ("dijkstra","astar","bfs","dag_dp"):
        raise ValueError("unsupported planning algorithm")
    try:
        import networkx as nx
    except ImportError:
        return PlanResult("UNSUPPORTED",backend="networkx",limitations=("networkx_unavailable",))
    g,start,end,expanded,truncated=_build_graph(p,nx)
    if not g.has_node(end):
        return PlanResult("UNKNOWN_LIMIT" if truncated else "UNREACHABLE_EXHAUSTIVE",
                          expanded_states=expanded,backend="networkx_"+algorithm)
    try:
        if algorithm=="dijkstra":
            nodes=nx.shortest_path(g,start,end,weight="weight",method="dijkstra")
        elif algorithm=="astar":
            nodes=nx.astar_path(g,start,end,heuristic=lambda _a,_b:0,weight="weight")
        elif algorithm=="bfs":
            nodes=nx.shortest_path(g,start,end)
        else:
            nodes=_dag_path(g,nx,start,end)
    except nx.NetworkXNoPath:
        return PlanResult("UNKNOWN_LIMIT" if truncated else "UNREACHABLE_EXHAUSTIVE",
                          expanded_states=expanded,backend="networkx_"+algorithm)
    steps=tuple(g[a][b]["action"] for a,b in zip(nodes,nodes[1:]) if g[a][b]["action"])
    checked=check_plan(p,steps)
    if checked is None:
        return PlanResult("INVALID_SOLUTION",expanded_states=expanded,
                          backend="networkx_"+algorithm)
    final,cost,risk=checked
    return PlanResult("FEASIBLE" if (truncated or (algorithm=="bfs"\n                          and len({a.cost for a in p.actions})>1)) else "OPTIMAL",
                      steps,final,cost,risk,expanded,
                      backend="networkx_"+algorithm,
                      limitations=("state_and_actions_caller_supplied_not_authenticated",
                                   "no_real_world_effects_executed",
                                   "search_truncated_no_optimality_claim" if truncated
                                   else "complete_bounded_state_graph",
                                   "bfs_optimizes_steps_not_cost" if algorithm=="bfs"
                                   else "nonnegative_edge_cost_shortest_path"))
