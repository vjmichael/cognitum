"""C11 P2: bounded, typed combinatorial workflows with independent arithmetic receipts.

Mature SciPy/HiGHS and NetworkX engines are *untrusted* witnesses. Exact finite
checks do not depend on these engines. No host permissions, model side effects,
process isolation or production worker cancellation are provided here.
"""
from __future__ import annotations

import hashlib
import itertools
import math
import re
import time
from typing import Callable

from cognitum.formal_solver import _decode, _encode
from cognitum.proto import workflows_pb2 as p

MAX_FRAME = 64 * 1024
MAX_RESPONSE = 64 * 1024
MAX_TIME_MS = 5_000
MAX_ABS_COST = 1_000_000
MAX_EXACT_STATES = 4096
IDENT = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z', re.ASCII)
TRACE = re.compile(r'[A-Za-z0-9_.:-]{0,64}\Z', re.ASCII)


def _validate(req: p.WorkflowRequest) -> str:
    if req.schema_version != 1:
        raise ValueError('UNSUPPORTED_REQUEST_SCHEMA')
    if req.timeout_ms > MAX_TIME_MS or not TRACE.fullmatch(req.trace_id):
        raise ValueError('INVALID_RESOURCE_LIMIT')
    kind = req.WhichOneof('problem')
    if kind is None:
        raise ValueError('MISSING_WORKFLOW')
    if kind == 'assignment':
        a = req.assignment
        if not (1 <= a.jobs <= a.workers <= 10) or len(a.edges) > 100:
            raise ValueError('INVALID_ASSIGNMENT_SIZE')
        seen = set()
        for e in a.edges:
            if e.worker >= a.workers or e.job >= a.jobs or (e.worker,e.job) in seen or abs(e.cost)>MAX_ABS_COST:
                raise ValueError('INVALID_ASSIGNMENT_EDGE')
            seen.add((e.worker,e.job))
    elif kind == 'packing':
        b = req.packing
        if not 1 <= len(b.items) <= 32 or b.capacity > 100_000:
            raise ValueError('INVALID_PACKING_SIZE')
        names = set()
        for item in b.items:
            if not IDENT.fullmatch(item.id) or item.id in names or item.weight > 100_000 or abs(item.value)>MAX_ABS_COST:
                raise ValueError('INVALID_PACKING_ITEM')
            names.add(item.id)
    elif kind == 'flow':
        f = req.flow
        if not (2 <= len(f.nodes) <= 16) or not (1 <= len(f.arcs) <= 64):
            raise ValueError('INVALID_FLOW_SIZE')
        names = set()
        for n in f.nodes:
            if not IDENT.fullmatch(n.id) or n.id in names or abs(n.supply)>100_000:
                raise ValueError('INVALID_FLOW_NODE')
            names.add(n.id)
        if sum(n.supply for n in f.nodes) != 0:
            raise ValueError('UNBALANCED_FLOW')
        edges = set()
        for a in f.arcs:
            if (a.from_node >= len(f.nodes) or a.to_node >= len(f.nodes) or a.from_node==a.to_node
                or (a.from_node,a.to_node) in edges or a.capacity > 100_000 or abs(a.cost)>MAX_ABS_COST):
                raise ValueError('INVALID_FLOW_ARC')
            edges.add((a.from_node,a.to_node))
    elif kind == 'scheduling':
        s = req.scheduling
        if not (1 <= len(s.tasks) <= 10) or not (1 <= len(s.resources) <= 8) or not (1 <= s.horizon <= 40) or len(s.precedences)>64:
            raise ValueError('INVALID_SCHEDULE_SIZE')
        resources = {}
        for r in s.resources:
            if not IDENT.fullmatch(r.id) or r.id in resources or not 1<=r.capacity<=100:
                raise ValueError('INVALID_RESOURCE')
            resources[r.id] = r.capacity
        tasks = set()
        for t in s.tasks:
            if (not IDENT.fullmatch(t.id) or t.id in tasks or t.resource_id not in resources or
                not 1<=t.duration<=s.horizon or not 1<=t.demand<=resources[t.resource_id] or
                t.earliest_start > t.latest_start or t.latest_start+t.duration>s.horizon):
                raise ValueError('INVALID_SCHEDULE_TASK')
            tasks.add(t.id)
        precedences = set()
        for a in s.precedences:
            if a.before>=len(s.tasks) or a.after>=len(s.tasks) or a.before==a.after or (a.before,a.after) in precedences:
                raise ValueError('INVALID_PRECEDENCE')
            precedences.add((a.before,a.after))
    elif kind == 'routing':
        rt = req.routing
        if not 3<=rt.nodes<=10 or len(rt.costs)!=rt.nodes**2:
            raise ValueError('INVALID_ROUTE_SIZE')
        for i in range(rt.nodes):
            for j in range(rt.nodes):
                v = rt.costs[i*rt.nodes+j]
                if v<0 or v>MAX_ABS_COST or (i==j and v!=0) or v!=rt.costs[j*rt.nodes+i]:
                    raise ValueError('INVALID_ROUTE_MATRIX')
    _select_backend(req,kind)
    return kind


def _select_backend(req,kind):
    defaults={'assignment':'scipy-assignment','packing':'scipy-highs','flow':'networkx-simplex',
              'scheduling':'scipy-highs','routing':'networkx-greedy'}
    permitted={kind:{default} for kind,default in defaults.items()}
    permitted['scheduling'].add('ortools-cpsat')
    choice=req.backend_id or defaults[kind]
    if choice not in permitted[kind]:
        raise ValueError('INVALID_BACKEND_SELECTION')
    return kind+':'+choice


def _solution_cost(req, sol) -> int:
    """Exact independent workflow constraints and objective, no solver import."""
    kind = _validate(req)
    if kind == 'assignment':
        edges = {(e.worker,e.job):e.cost for e in req.assignment.edges}
        pairs = [(x.first,x.second) for x in sol.assignment]
        if (len(pairs)!=req.assignment.jobs or len(set(x for x,y in pairs))!=len(pairs)
            or sorted(y for x,y in pairs)!=list(range(req.assignment.jobs))
            or any(pair not in edges for pair in pairs) or sol.packed_indices or sol.flows or sol.starts or sol.tour):
            raise ValueError('INVALID_ASSIGNMENT_WITNESS')
        return sum(edges[pair] for pair in pairs)
    if kind == 'packing':
        choices = list(sol.packed_indices)
        if (len(choices)!=len(set(choices)) or any(i>=len(req.packing.items) for i in choices)
            or sum(req.packing.items[i].weight for i in choices)>req.packing.capacity
            or sol.assignment or sol.flows or sol.starts or sol.tour):
            raise ValueError('INVALID_PACKING_WITNESS')
        return sum(req.packing.items[i].value for i in choices)
    if kind == 'flow':
        f=req.flow
        values = [(x.index,x.value) for x in sol.flows]
        if (len(values)!=len(f.arcs) or sorted(i for i,v in values)!=list(range(len(f.arcs)))
            or any(v<0 or v>f.arcs[i].capacity for i,v in values)
            or sol.assignment or sol.packed_indices or sol.starts or sol.tour):
            raise ValueError('INVALID_FLOW_WITNESS')
        net=[0]*len(f.nodes)
        cost=0
        for i,v in values:
            arc=f.arcs[i];net[arc.from_node]+=v;net[arc.to_node]-=v;cost+=v*arc.cost
        if net!=[n.supply for n in f.nodes]:
            raise ValueError('FLOW_CONSERVATION_VIOLATED')
        return cost
    if kind == 'scheduling':
        s=req.scheduling
        starts = [(x.index,x.value) for x in sol.starts]
        if (len(starts)!=len(s.tasks) or sorted(i for i,v in starts)!=list(range(len(s.tasks)))
            or sol.assignment or sol.packed_indices or sol.flows or sol.tour):
            raise ValueError('INVALID_SCHEDULE_WITNESS')
        times=dict(starts)
        for i,v in starts:
            t=s.tasks[i]
            if v<t.earliest_start or v>t.latest_start:
                raise ValueError('SCHEDULE_TIME_OUT_OF_RANGE')
        for a in s.precedences:
            if times[a.before]+s.tasks[a.before].duration>times[a.after]:
                raise ValueError('PRECEDENCE_VIOLATION')
        capacities={r.id:r.capacity for r in s.resources}
        for time_slot in range(s.horizon):
            loads={rid:0 for rid in capacities}
            for i,t in enumerate(s.tasks):
                if times[i]<=time_slot<times[i]+t.duration:
                    loads[t.resource_id]+=t.demand
            if any(load>capacities[rid] for rid,load in loads.items()):
                raise ValueError('RESOURCE_OVERLOAD')
        return max(times[i]+t.duration for i,t in enumerate(s.tasks))
    if kind == 'routing':
        t=list(sol.tour);n=req.routing.nodes
        if (len(t)!=n+1 or t[0]!=0 or t[-1]!=0 or sorted(t[:-1])!=list(range(n))
            or sol.assignment or sol.packed_indices or sol.flows or sol.starts):
            raise ValueError('INVALID_ROUTE_WITNESS')
        return sum(req.routing.costs[a*n+b] for a,b in zip(t,t[1:]))
    raise ValueError('UNKNOWN_WORKFLOW')


def _finite_oracle(req):
    """Return (best, states) for bounded independent complete enumeration, else None.

    best=None proves infeasibility only if all finite states were checked.
    """
    kind=_validate(req)
    states=0;best=None
    def candidate(sol):
        nonlocal states,best
        states+=1
        try:
            score=_solution_cost(req, sol)
        except ValueError:
            return
        if best is None or ((score>best) if kind=='packing' else (score<best)):
            best=score
    sol=p.WorkflowSolution()
    if kind=='assignment':
        a=req.assignment
        total=math.perm(a.workers,a.jobs)
        if total>MAX_EXACT_STATES:return None
        for assignment in itertools.permutations(range(a.workers),a.jobs):
            sol.Clear();sol.assignment.extend(p.IntPair(first=worker,second=job) for job,worker in enumerate(assignment))
            candidate(sol)
    elif kind=='packing':
        b=req.packing
        if 2**len(b.items)>MAX_EXACT_STATES:return None
        for mask in range(2**len(b.items)):
            sol.Clear();sol.packed_indices.extend(i for i in range(len(b.items)) if mask>>i&1)
            candidate(sol)
    elif kind=='flow':
        f=req.flow
        total=math.prod(a.capacity+1 for a in f.arcs)
        if total>MAX_EXACT_STATES:return None
        for vals in itertools.product(*(range(a.capacity+1) for a in f.arcs)):
            sol.Clear();sol.flows.extend(p.IndexValue(index=i,value=v) for i,v in enumerate(vals))
            candidate(sol)
    elif kind=='scheduling':
        s=req.scheduling
        total=math.prod(t.latest_start-t.earliest_start+1 for t in s.tasks)
        if total>MAX_EXACT_STATES:return None
        for vals in itertools.product(*(range(t.earliest_start,t.latest_start+1) for t in s.tasks)):
            sol.Clear();sol.starts.extend(p.IndexValue(index=i,value=v) for i,v in enumerate(vals))
            candidate(sol)
    elif kind=='routing':
        n=req.routing.nodes
        if math.factorial(n-1)>MAX_EXACT_STATES:return None
        for perm in itertools.permutations(range(1,n)):
            sol.Clear();sol.tour.extend((0,*perm,0))
            candidate(sol)
    return best,states


def _solve_assignment(req, timeout):
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    import scipy
    a=req.assignment
    matrix=np.full((a.jobs,a.workers),np.inf)
    for e in a.edges:matrix[e.job,e.worker]=float(e.cost)
    try:
        rows,cols=linear_sum_assignment(matrix)
    except ValueError:
        return None,'INFEASIBLE','scipy-'+scipy.__version__
    if not np.isfinite(matrix[rows,cols]).all():return None,'INFEASIBLE','scipy-'+scipy.__version__
    sol=p.WorkflowSolution()
    sol.assignment.extend(p.IntPair(first=int(w),second=int(j)) for j,w in zip(rows,cols))
    return sol,'OPTIMAL','scipy-'+scipy.__version__


def _solve_packing(req, timeout):
    import numpy as np
    from scipy.optimize import milp, Bounds, LinearConstraint
    import scipy
    b=req.packing
    vals=np.array([i.value for i in b.items],dtype=float)
    wt=np.array([[i.weight for i in b.items]],dtype=float)
    res=milp(-vals,integrality=np.ones(len(b.items)),bounds=Bounds(np.zeros(len(b.items)),np.ones(len(b.items))),
             constraints=[LinearConstraint(wt,[0],[b.capacity])],options={'time_limit':timeout/1000,'mip_rel_gap':0.0})
    if res.x is None:return None,{2:'INFEASIBLE',1:'LIMIT'}.get(res.status,'ERROR'),'scipy-'+scipy.__version__
    if any(abs(x-round(x))>1e-6 for x in res.x):return None,'INVALID_WITNESS','scipy-'+scipy.__version__
    sol=p.WorkflowSolution()
    sol.packed_indices.extend(i for i,x in enumerate(res.x) if int(round(x))==1)
    return sol,('OPTIMAL' if res.status==0 else 'FEASIBLE'),'scipy-'+scipy.__version__


def _solve_flow(req,timeout):
    import networkx as nx
    f=req.flow
    graph=nx.DiGraph()
    for i,node in enumerate(f.nodes):graph.add_node(i,demand=-node.supply)
    for a in f.arcs:graph.add_edge(a.from_node,a.to_node,capacity=a.capacity,weight=a.cost)
    try:
        _,flows=nx.network_simplex(graph)
    except nx.NetworkXUnfeasible:
        return None,'INFEASIBLE','networkx-'+nx.__version__
    except nx.NetworkXError:
        return None,'ERROR','networkx-'+nx.__version__
    sol=p.WorkflowSolution()
    sol.flows.extend(p.IndexValue(index=i,value=flows.get(a.from_node,{}).get(a.to_node,0)) for i,a in enumerate(f.arcs))
    return sol,'OPTIMAL','networkx-'+nx.__version__


def _solve_scheduling(req,timeout):
    # Time-indexed MIP, bounded by 10 tasks and horizon 40. Integrated HiGHS.
    import numpy as np
    import scipy
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import lil_matrix
    s=req.scheduling
    slots=[(i,t) for i,task in enumerate(s.tasks) for t in range(task.earliest_start,task.latest_start+1)]
    count=len(slots); total=count+1
    rows=[];lo=[];hi=[]
    def add(coeff, lower=-math.inf, upper=math.inf):
        rows.append(coeff);lo.append(lower);hi.append(upper)
    for i,task in enumerate(s.tasks):
        add({j:1 for j,(ti,_) in enumerate(slots) if ti==i},1,1)
        add({j:t+task.duration for j,(ti,t) in enumerate(slots) if ti==i}|{count:-1},upper=0)
    for resource in s.resources:
        for time_slot in range(s.horizon):
            active={j:s.tasks[i].demand for j,(i,t) in enumerate(slots)
                    if s.tasks[i].resource_id==resource.id and t<=time_slot<t+s.tasks[i].duration}
            if active:add(active,upper=resource.capacity)
    for arc in s.precedences:
        coeff={j:(t+s.tasks[i].duration if i==arc.before else -t) for j,(i,t) in enumerate(slots) if i in (arc.before,arc.after)}
        add(coeff,upper=0)
    matrix=lil_matrix((len(rows),total),dtype=float)
    for i,row in enumerate(rows):
        for j,val in row.items():matrix[i,j]=val
    objective=np.zeros(total);objective[-1]=1
    mins=np.zeros(total);maxs=np.ones(total);maxs[-1]=s.horizon
    out=milp(objective,integrality=np.ones(total),bounds=Bounds(mins,maxs),
             constraints=LinearConstraint(matrix.tocsr(),lo,hi),options={'time_limit':timeout/1000,'mip_rel_gap':0.0})
    if out.x is None:return None,{2:'INFEASIBLE',1:'LIMIT'}.get(out.status,'ERROR'),'scipy-'+scipy.__version__
    if any(abs(x-round(x))>1e-6 for x in out.x):return None,'INVALID_WITNESS','scipy-'+scipy.__version__
    sol=p.WorkflowSolution()
    for i in range(len(s.tasks)):
        chosen=[t for j,(task,t) in enumerate(slots) if task==i and round(out.x[j])==1]
        if len(chosen)!=1:return None,'INVALID_WITNESS','scipy-'+scipy.__version__
        sol.starts.add(index=i,value=chosen[0])
    return sol,('OPTIMAL' if out.status==0 else 'FEASIBLE'),'scipy-'+scipy.__version__


def _solve_routing(req,timeout):
    import networkx as nx
    rt=req.routing;n=rt.nodes
    g=nx.complete_graph(n)
    nx.set_edge_attributes(g,{(i,j):int(rt.costs[i*n+j]) for i,j in g.edges},'weight')
    tour=nx.algorithms.approximation.greedy_tsp(g,source=0,weight='weight')
    sol=p.WorkflowSolution();sol.tour.extend(tour)
    return sol,'HEURISTIC','networkx-'+nx.__version__


def _solve_ortools_scheduling(req,timeout):
    # Optional installed CP-SAT adapter: no user-controlled Python code or paths.
    from ortools.sat.python import cp_model
    import ortools
    s=req.scheduling
    model=cp_model.CpModel()
    starts=[];ends=[];intervals={r.id:[] for r in s.resources};demands={r.id:[] for r in s.resources}
    for task in s.tasks:
        start=model.new_int_var(task.earliest_start,task.latest_start,'start_'+task.id)
        end=model.new_int_var(task.earliest_start+task.duration,task.latest_start+task.duration,'end_'+task.id)
        interval=model.new_interval_var(start,task.duration,end,'interval_'+task.id)
        starts.append(start);ends.append(end)
        intervals[task.resource_id].append(interval);demands[task.resource_id].append(task.demand)
    for resource in s.resources:
        model.add_cumulative(intervals[resource.id],demands[resource.id],resource.capacity)
    for arc in s.precedences:model.add(starts[arc.after]>=ends[arc.before])
    makespan=model.new_int_var(0,s.horizon,'makespan')
    model.add_max_equality(makespan,ends)
    model.minimize(makespan)
    solver=cp_model.CpSolver()
    solver.parameters.max_time_in_seconds=timeout/1000
    solver.parameters.num_search_workers=1
    status=solver.solve(model)
    if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        return None,('INFEASIBLE' if status==cp_model.INFEASIBLE else 'LIMIT'),'ortools-'+getattr(ortools,'__version__','unknown')
    sol=p.WorkflowSolution()
    sol.starts.extend(p.IndexValue(index=i,value=int(solver.value(x))) for i,x in enumerate(starts))
    return sol,('OPTIMAL' if status==cp_model.OPTIMAL else 'FEASIBLE'),'ortools-'+getattr(ortools,'__version__','unknown')


BACKENDS:dict[str,Callable]={
    'assignment:scipy-assignment':_solve_assignment,
    'packing:scipy-highs':_solve_packing,
    'flow:networkx-simplex':_solve_flow,
    'scheduling:scipy-highs':_solve_scheduling,
    'scheduling:ortools-cpsat':_solve_ortools_scheduling,
    'routing:networkx-greedy':_solve_routing,
}


class WorkflowRegistry:
    def __init__(self,*,enabled=False):
        self.enabled=bool(enabled)
        self.backends=BACKENDS.copy()
    def disable(self):
        self.enabled=False
    def run_frame(self,frame:bytes,*,host_authorized=False)->bytes:
        req=_decode(frame,p.WorkflowRequest,MAX_FRAME)
        kind=req.WhichOneof('problem')
        result=p.WorkflowResult(schema_version=1,request_sha256=hashlib.sha256(frame).digest(),
                                backend_id=(kind or ''),trace_id=req.trace_id,
                                status=p.REJECTED,reason_code='HOST_AUTHORIZATION_REQUIRED')
        if not host_authorized:return _encode(result,MAX_RESPONSE)
        if not self.enabled:
            result.reason_code='REGISTRY_DISABLED'
            return _encode(result,MAX_RESPONSE)
        start=time.monotonic_ns()
        try:
            kind=_validate(req)
            key=_select_backend(req,kind)
            result.backend_id=key
            sol,claim,version=self.backends[key](req,req.timeout_ms or 2000)
            result.backend_version=str(version)[:80];result.backend_claim=claim
            if claim not in ('OPTIMAL','FEASIBLE','HEURISTIC','INFEASIBLE','LIMIT','ERROR','INVALID_WITNESS'):
                raise ValueError('UNRECOGNIZED_BACKEND_STATUS')
            oracle=_finite_oracle(req)
            if sol is not None:
                val=_solution_cost(req,sol)
                if abs(val)>2**63-1:raise ValueError('OBJECTIVE_OVERFLOW')
                if claim in ('INFEASIBLE','ERROR','LIMIT','INVALID_WITNESS'):
                    raise ValueError('INCONSISTENT_BACKEND_CLAIM')
                result.solution.CopyFrom(sol);result.objective_value=val;result.witness_verified=True
                result.status=p.VERIFIED_FEASIBLE;result.reason_code='EXACT_WITNESS_CHECKED'
                if oracle is not None and oracle[0]==val:
                    result.status=p.VERIFIED_OPTIMAL;result.optimality_verified=True
                    result.exact_states_checked=oracle[1]
                    result.reason_code='FINITE_OPTIMUM_CHECKED'
            elif oracle is not None and oracle[0] is None:
                result.status=p.VERIFIED_INFEASIBLE;result.optimality_verified=True
                result.exact_states_checked=oracle[1]
                result.reason_code='FINITE_INFEASIBILITY_CHECKED'
            else:
                result.status=p.UNKNOWN;result.reason_code='BACKEND_CLAIM_UNVERIFIED'
        except (ValueError,RuntimeError,ImportError,TypeError,OverflowError,OSError) as e:
            msg=str(e)
            result.status=p.REJECTED if msg.startswith(('UNSUPPORTED_','INVALID_','MISSING_','UNBALANCED_')) else p.UNKNOWN
            result.reason_code=(msg if isinstance(e,ValueError) else 'BACKEND_UNAVAILABLE_OR_FAILED')[:80]
            result.ClearField('solution');result.witness_verified=False;result.optimality_verified=False
            result.exact_states_checked=0
        finally:
            result.wall_ns=time.monotonic_ns()-start
        return _encode(result,MAX_RESPONSE)


def verify_workflow_frame(request_frame:bytes,result_frame:bytes)->bytes:
    receipt=p.WorkflowReceipt(request_sha256=hashlib.sha256(request_frame).digest(),
                              result_sha256=hashlib.sha256(result_frame).digest(),reason_code='UNVERIFIED')
    try:
        req=_decode(request_frame,p.WorkflowRequest,MAX_FRAME)
        res=_decode(result_frame,p.WorkflowResult,MAX_RESPONSE)
        kind=_validate(req)
        if (res.schema_version!=1 or res.request_sha256!=receipt.request_sha256 or res.backend_id!=_select_backend(req,kind) or
            res.trace_id!=req.trace_id or res.host_approved):
            raise ValueError('UNBOUND_RESULT')
        if res.status in (p.UNKNOWN,p.REJECTED):
            if res.HasField('solution') or res.witness_verified or res.optimality_verified or res.exact_states_checked:
                raise ValueError('FALSE_ASSURANCE')
            return _encode(receipt,MAX_RESPONSE)
        oracle=_finite_oracle(req)
        if res.status==p.VERIFIED_INFEASIBLE:
            if (res.HasField('solution') or res.witness_verified or not res.optimality_verified or
                oracle is None or oracle[0] is not None or res.exact_states_checked!=oracle[1]):
                raise ValueError('UNPROVEN_INFEASIBILITY')
            receipt.evidence_valid=True;receipt.optimality_verified=True
            receipt.states_checked=oracle[1];receipt.reason_code='FINITE_INFEASIBILITY_RECHECKED'
            return _encode(receipt,MAX_RESPONSE)
        if res.status not in (p.VERIFIED_FEASIBLE,p.VERIFIED_OPTIMAL) or not res.HasField('solution') or not res.witness_verified:
            raise ValueError('MISSING_WITNESS')
        val=_solution_cost(req,res.solution)
        if val!=res.objective_value:raise ValueError('FALSE_OBJECTIVE')
        if res.status==p.VERIFIED_OPTIMAL or res.optimality_verified or res.exact_states_checked:
            if (res.status!=p.VERIFIED_OPTIMAL or not res.optimality_verified or oracle is None or
                oracle[0]!=val or res.exact_states_checked!=oracle[1]):
                raise ValueError('UNPROVEN_OPTIMALITY')
            receipt.optimality_verified=True;receipt.states_checked=oracle[1]
        receipt.evidence_valid=True;receipt.reason_code='DOMAIN_WITNESS_RECHECKED'
    except (ValueError,OverflowError,TypeError):
        receipt.reason_code='INVALID_OR_UNBOUND_EVIDENCE'
    return _encode(receipt,MAX_RESPONSE)


def make_workflow_audit(request_frame:bytes,result_frame:bytes)->bytes:
    req=_decode(request_frame,p.WorkflowRequest,MAX_FRAME)
    res=_decode(result_frame,p.WorkflowResult,MAX_RESPONSE)
    if (res.schema_version!=1 or res.request_sha256!=hashlib.sha256(request_frame).digest() or
        res.backend_id!=_select_backend(req,_validate(req)) or res.trace_id!=req.trace_id or res.host_approved):
        raise ValueError('UNBOUND_AUDIT_EVIDENCE')
    checked=p.WorkflowReceipt.FromString(verify_workflow_frame(request_frame,result_frame))
    if (res.status in (p.VERIFIED_FEASIBLE,p.VERIFIED_OPTIMAL,p.VERIFIED_INFEASIBLE) and
        (not checked.evidence_valid or checked.optimality_verified!=res.optimality_verified)):
        raise ValueError('UNVERIFIED_ASSURANCE')
    if (res.status in (p.UNKNOWN,p.REJECTED) and
        (res.witness_verified or res.optimality_verified or res.HasField('solution'))):
        raise ValueError('FALSE_ASSURANCE')
    audit=p.WorkflowAudit(schema_version=1,request_sha256=res.request_sha256,
          result_sha256=hashlib.sha256(result_frame).digest(),trace_id=res.trace_id,
          backend_id=res.backend_id,backend_version=res.backend_version,status=res.status,
          reason_code=res.reason_code,wall_ns=res.wall_ns,witness_verified=res.witness_verified,
          optimality_verified=res.optimality_verified)
    return _encode(audit,MAX_RESPONSE)
