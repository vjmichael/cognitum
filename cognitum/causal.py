"""C14 P1: bounded typed discrete structural-causal inference.

We reason WITHIN a user/host-specified structural causal model, not from raw
observational correlations. Shared exogenous variables represent latent common
causes. Counterfactuals reuse the same posterior exogenous assignments across
factual and intervened worlds (abduction, action, prediction).

An intervention is a mathematical override, NOT an authorized real-world action.
Results are assumption-bound and never claim nonparametric identification from
observational data. No runtime code/data executes from model frames.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
import hashlib
import math
import time
from collections import deque

import networkx as nx
from cognitum.planning import _decode, _encode, NAME, TRACE
from cognitum.proto import causal_pb2 as p

MAX_FRAME = 65536
MAX_TIMEOUT_MS = 5000
MAX_NOISE = 8
MAX_NODES = 12
MAX_STATES = 6
MAX_TABLE = 4096
MAX_ASSIGNMENTS = 4096
MAX_OUTPUT_CELLS = 64
BACKEND = 'c14-finite-scm-enumerator'
VERSION = 'C14-P1-1'
CANON_ASSURANCE = 'ASSUMED_SCM_EXACT'
BACKDOOR_ASSURANCE = 'BACKDOOR_GRAPH_CRITERION'
SUCCESS = {p.EXACT_MODEL_RESULT,p.BACKDOOR_CERTIFIED} # Negative criterion is verified, NOT certified causal identification.

class BudgetLimit(Exception):
    pass

@dataclass(frozen=True)
class Model:
    noise_dims: tuple[int, ...]
    endo_dims: tuple[int, ...]
    noise_probs: tuple[tuple[Fraction, ...], ...]
    parents: tuple[tuple[int, ...], ...]
    noise_uses: tuple[tuple[int, ...], ...]
    outputs: tuple[tuple[int, ...], ...]
    topo: tuple[int, ...]
    assignments: int


def _parse(raw: bytes):
    if len(raw) > MAX_FRAME: raise ValueError('FRAME_TOO_LARGE')
    req = _decode(raw, p.CausalRequest)
    if (req.schema_version != 1 or not TRACE.fullmatch(req.trace_id) or
        req.operation not in (p.OBSERVATIONAL_QUERY,p.INTERVENTIONAL_QUERY,p.COUNTERFACTUAL_QUERY,p.BACKDOOR_CHECK) or
        not (1 <= req.timeout_ms <= MAX_TIMEOUT_MS) or not (1 <= req.max_exogenous_assignments <= MAX_ASSIGNMENTS)):
        raise ValueError('INVALID_CAUSAL_REQUEST')
    if not NAME.fullmatch(req.model.assumption_id):
        raise ValueError('ASSUMPTION_ID_REQUIRED')
    us, vs = req.model.exogenous, req.model.endogenous
    if not (1 <= len(us) <= MAX_NOISE and 1 <= len(vs) <= MAX_NODES):
        raise ValueError('INVALID_SCM_SIZE')
    ids = [x.id for x in (*us,*vs)]
    if len(ids) != len(set(ids)) or any(not NAME.fullmatch(x) for x in ids):
        raise ValueError('INVALID_VARIABLE_IDS')
    def check_states(x):
        return 2 <= len(x.states) <= MAX_STATES and len(set(x.states)) == len(x.states) and all(NAME.fullmatch(s) for s in x.states)
    if any(not check_states(v) for v in (*us,*vs)):
        raise ValueError('INVALID_STATES')
    nd, vd = tuple(len(x.states) for x in us),tuple(len(x.states) for x in vs)
    count = math.prod(nd)
    if count > req.max_exogenous_assignments:
        raise BudgetLimit('EXOGENOUS_ENUMERATION_LIMIT')
    probs=[]
    for i,u in enumerate(us):
        if len(u.probability_ppm)!=nd[i] or sum(u.probability_ppm)!=1_000_000:
            raise ValueError('INVALID_NOISE_DISTRIBUTION')
        probs.append(tuple(Fraction(v,1_000_000) for v in u.probability_ppm))
    parents=[]; noises=[]; tables=[]
    for i,v in enumerate(vs):
        par, nos = tuple(v.parents), tuple(v.noise)
        if (len(set(par)) != len(par) or len(set(nos)) != len(nos) or
            i in par or any(x >= len(vs) for x in par) or any(x >= len(us) for x in nos)):
            raise ValueError('INVALID_STRUCTURAL_REFERENCES')
        length=math.prod([*(vd[j] for j in par),*(nd[j] for j in nos)])
        if length > MAX_TABLE or len(v.function_outputs)!=length or any(x >= vd[i] for x in v.function_outputs):
            raise ValueError('INVALID_STRUCTURAL_FUNCTION')
        parents.append(par); noises.append(nos); tables.append(tuple(v.function_outputs))
    seen=set(); active=set(); topo=[]
    def visit(i):
        if i in active: raise ValueError('CYCLIC_SCM')
        if i in seen: return
        active.add(i)
        for pa in parents[i]: visit(pa)
        active.remove(i); seen.add(i); topo.append(i)
    for i in range(len(vs)): visit(i)
    def maps(arr,tag):
        out={}
        for o in arr:
            if o.variable >= len(vs) or o.state >= vd[o.variable] or o.variable in out:
                raise ValueError('INVALID_'+tag)
            out[o.variable]=o.state
        return out
    obs=maps(req.factual_evidence,'EVIDENCE')
    intervention=maps(req.interventions,'INTERVENTION')
    if req.target >= len(vs): raise ValueError('INVALID_TARGET')
    if req.operation==p.OBSERVATIONAL_QUERY and (intervention or req.adjustment): raise ValueError('UNEXPECTED_INTERVENTION')
    if req.operation==p.INTERVENTIONAL_QUERY and (not intervention or obs or req.adjustment): raise ValueError('INVALID_INTERVENTION_QUERY')
    if req.operation==p.COUNTERFACTUAL_QUERY and (not intervention or not obs or req.adjustment): raise ValueError('INVALID_COUNTERFACTUAL_QUERY')
    if req.operation==p.BACKDOOR_CHECK:
        if obs or intervention or req.treatment >= len(vs) or req.treatment == req.target:
            raise ValueError('INVALID_BACKDOOR_QUERY')
        if (len(set(req.adjustment))!=len(req.adjustment) or
            any(j >= len(vs) or j in (req.treatment,req.target) for j in req.adjustment)):
            raise ValueError('INVALID_ADJUSTMENT_SET')
    elif req.treatment: raise ValueError('UNEXPECTED_TREATMENT')
    return req,Model(nd,vd,tuple(probs),tuple(parents),tuple(noises),tuple(tables),tuple(topo),count),obs,intervention


def _execute(model: Model, u: tuple[int,...], override: dict[int,int]):
    """Fast evaluator: mixed-radix access to grounded deterministic equations."""
    state=[0]*len(model.endo_dims)
    for i in model.topo:
        if i in override:
            state[i]=override[i]; continue
        idx=0
        for j in model.parents[i]: idx=idx*model.endo_dims[j]+state[j]
        for j in model.noise_uses[i]: idx=idx*model.noise_dims[j]+u[j]
        state[i]=model.outputs[i][idx]
    return tuple(state)


def _assignment_probability(model, u):
    return math.prod((model.noise_probs[i][j] for i,j in enumerate(u)), start=Fraction(1))


def _solve(req,model,obs,intervention, deadline):
    """Model-exact finite enumeration; factual evidence always conditions abduction."""
    weights=[Fraction(0)]*model.endo_dims[req.target]
    joint=[[Fraction(0) for _ in weights] for _ in weights]
    mass=Fraction(0)
    for u in product(*(range(d) for d in model.noise_dims)):
        if time.monotonic()>deadline: raise BudgetLimit('DEADLINE')
        probability=_assignment_probability(model,u)
        if not probability:continue
        factual=_execute(model,u,{})
        if any(factual[i]!=v for i,v in obs.items()):continue
        mass+=probability
        affected=_execute(model,u,intervention) if intervention else factual
        weights[affected[req.target]]+=probability
        if req.operation==p.COUNTERFACTUAL_QUERY:
            joint[factual[req.target]][affected[req.target]]+=probability
    if not mass: return p.IMPOSSIBLE_FACTUAL_EVIDENCE,[],[],'0'
    posterior=[p.CausalProbabilityCell(target_state=i,probability=str(w/mass)) for i,w in enumerate(weights)]
    cells=[p.CounterfactualJointCell(factual_state=i,counterfactual_state=j,probability=str(v/mass))
           for i,row in enumerate(joint) for j,v in enumerate(row)] if req.operation==p.COUNTERFACTUAL_QUERY else []
    return p.EXACT_MODEL_RESULT,posterior,cells,str(mass)


def _expanded_graph(model):
    g=nx.DiGraph(); k=len(model.noise_dims)
    g.add_nodes_from(range(k+len(model.endo_dims)))
    for i in range(len(model.endo_dims)):
        for pa in model.parents[i]:g.add_edge(k+pa,k+i)
        for u in model.noise_uses[i]:g.add_edge(u,k+i)
    return g


def _backdoor(model, treatment, outcome, adjustment):
    """Sufficient, not necessary: nondescendant Z d-separates X,Y in G_underlined_X.

    Include unobserved exogenous nodes in the graph, but NEVER allow them
    as adjustment variables. Shared exogenous causes remain latent confounders.
    """
    g=_expanded_graph(model); k=len(model.noise_dims); x=k+treatment; y=k+outcome
    z={k+j for j in adjustment}
    if any(v in nx.descendants(g,x) for v in z):return False
    g.remove_edges_from(list(g.out_edges(x)))
    # Ancestral moral-graph d-separation criterion (includes ancestors of Z).
    ancestors={x,y,*z}
    for v in tuple(ancestors):ancestors.update(nx.ancestors(g,v))
    a=g.subgraph(ancestors)
    moral=nx.Graph(); moral.add_nodes_from(a.nodes)
    moral.add_edges_from(a.edges)
    for node in a.nodes:
        par=list(a.predecessors(node))
        for i in range(len(par)):
            for j in range(i+1,len(par)):moral.add_edge(par[i],par[j])
    moral.remove_nodes_from(z)
    return not nx.has_path(moral,x,y)


def run_causal_frame(raw, *, host_authorized=False, enabled=False):
    start=time.monotonic_ns()
    out=p.CausalResult(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
                       status=p.REJECTED_CAUSAL,reason_code='INVALID_FRAME',backend_id=BACKEND,backend_version=VERSION,
                       assurance='NONE')
    try:
        req,model,obs,intervention=_parse(raw)
        out.trace_id=req.trace_id; out.operation=req.operation
        if not host_authorized: raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled: raise ValueError('CAUSAL_DISABLED')
        if req.operation == p.BACKDOOR_CHECK:
            ok=_backdoor(model,req.treatment,req.target,tuple(req.adjustment))
            out.status=p.BACKDOOR_CERTIFIED if ok else p.BACKDOOR_NOT_CERTIFIED
            out.assurance=BACKDOOR_ASSURANCE
            out.reason_code='BACKDOOR_SUFFICIENT' if ok else 'BACKDOOR_NOT_ESTABLISHED'
            out.independently_checked=(ok == _backdoor_independent(model,req.treatment,req.target,tuple(req.adjustment)))
            if not out.independently_checked:
                out.status=p.INCONCLUSIVE_CAUSAL;out.assurance='NONE';out.reason_code='IDENTIFICATION_CHECK_DISAGREEMENT'
        else:
            status,posterior,joint,mass=_solve(req,model,obs,intervention,time.monotonic()+req.timeout_ms/1000)
            out.status=status;out.posterior.extend(posterior);out.joint.extend(joint)
            out.factual_evidence_probability=mass
            if status==p.EXACT_MODEL_RESULT:
                v_mass, v_post, v_joint = _expected_finite(req,model,obs,intervention)
                if (mass!=v_mass or len(posterior)!=len(v_post or ()) or
                    any(cell.probability!=v for cell,v in zip(posterior,v_post or ())) or
                    len(joint)!=len(v_joint or ()) or
                    any(cell.probability!=v for cell,v in zip(joint,v_joint or ()))):
                    raise BudgetLimit('INDEPENDENT_CHECK_DISAGREEMENT')
            out.independently_checked=status==p.EXACT_MODEL_RESULT
            out.assurance=CANON_ASSURANCE if status==p.EXACT_MODEL_RESULT else 'NONE'
            out.reason_code='ASSUMED_SCM_ONLY' if status==p.EXACT_MODEL_RESULT else 'NO_FACTUAL_SUPPORT'
    except BudgetLimit as ex:
        out.status=p.INCONCLUSIVE_CAUSAL;out.reason_code=str(ex)
    except Exception as ex:
        out.status=p.REJECTED_CAUSAL
        out.reason_code=str(ex) if isinstance(ex,ValueError) and str(ex).isupper() and len(str(ex))<90 else 'CAUSAL_INVALID_OR_FAILED'
    out.wall_ns=time.monotonic_ns()-start
    return _encode(out)


def _replay_independent(model,u,intervention):
    """Verifier's own environment-index evaluation, without fast mixed-radix engine."""
    env={}
    def val(i):
        if i in env:return env[i]
        if i in intervention:return intervention[i]
        prefix=tuple(val(pa) for pa in model.parents[i])
        suffix=tuple(u[n] for n in model.noise_uses[i])
        shapes=[*(model.endo_dims[j] for j in model.parents[i]),*(model.noise_dims[j] for j in model.noise_uses[i])]
        row=0
        for coord,size in zip(prefix+suffix,shapes):row=row*size+coord
        env[i]=model.outputs[i][row]
        return env[i]
    return tuple(val(j) for j in range(len(model.endo_dims)))


def _expected_finite(req,model,obs,intervention):
    n=model.endo_dims[req.target]
    post=[Fraction(0) for _ in range(n)];joint=[[Fraction(0) for _ in range(n)] for _ in range(n)]
    total=Fraction(0)
    for u in product(*(range(d) for d in model.noise_dims)):
        # Alternative explicit weight multiplication, independent from solver.
        w=Fraction(1)
        for i,j in enumerate(u):w*=model.noise_probs[i][j]
        fact=_replay_independent(model,u,{})
        if not all(fact[i]==v for i,v in obs.items()):continue
        total+=w
        alt=_replay_independent(model,u,intervention) if intervention else fact
        post[alt[req.target]]+=w
        if req.operation==p.COUNTERFACTUAL_QUERY:joint[fact[req.target]][alt[req.target]]+=w
    if not total:return '0',None,None
    return str(total),tuple(str(v/total) for v in post),(tuple(str(w/total) for row in joint for w in row) if req.operation==p.COUNTERFACTUAL_QUERY else ())


def _backdoor_independent(model,treatment,outcome,adjustment):
    # Alternative d-separation using networkx's established implementation.
    g=_expanded_graph(model); k=len(model.noise_dims);x=k+treatment;y=k+outcome
    z={k+j for j in adjustment}
    if any(v in nx.descendants(g,x) for v in z):return False
    g.remove_edges_from(list(g.out_edges(x)))
    return bool(nx.is_d_separator(g,{x},{y},z))


def verify_causal_result(raw, result_frame):
    """Independent request-bound verifier; never accepts unsupported proof flags."""
    try:
        req,model,obs,intervention=_parse(raw)
        result=_decode(result_frame,p.CausalResult)
        if (result.schema_version!=1 or result.request_sha256!=hashlib.sha256(raw).digest() or
            result.trace_id!=req.trace_id or result.operation!=req.operation or
            result.backend_id!=BACKEND or result.backend_version!=VERSION):return False
        if result.status in (p.REJECTED_CAUSAL,p.INCONCLUSIVE_CAUSAL):
            return (not result.independently_checked and result.assurance=='NONE' and
                    len(result.posterior)==0 and len(result.joint)==0)
        if req.operation==p.BACKDOOR_CHECK:
            expected=_backdoor_independent(model,req.treatment,req.target,req.adjustment)
            return (result.status==(p.BACKDOOR_CERTIFIED if expected else p.BACKDOOR_NOT_CERTIFIED) and
                    result.independently_checked and result.assurance==BACKDOOR_ASSURANCE and
                    result.reason_code==('BACKDOOR_SUFFICIENT' if expected else 'BACKDOOR_NOT_ESTABLISHED') and
                    not result.posterior and not result.joint and not result.factual_evidence_probability)
        mass,post,joint=_expected_finite(req,model,obs,intervention)
        if post is None:
            return (result.status==p.IMPOSSIBLE_FACTUAL_EVIDENCE and not result.independently_checked and
                    result.assurance=='NONE' and result.reason_code=='NO_FACTUAL_SUPPORT' and
                    result.factual_evidence_probability=='0' and not result.posterior and not result.joint)
        # Exact cell ordering and canonical rational strings prevent ambiguity.
        return (result.status==p.EXACT_MODEL_RESULT and result.independently_checked and
                result.assurance==CANON_ASSURANCE and result.reason_code=='ASSUMED_SCM_ONLY' and
                result.factual_evidence_probability==mass and
                len(result.posterior)==len(post) and
                all((cell.target_state==i and cell.probability==v) for i,(cell,v) in enumerate(zip(result.posterior,post))) and
                len(result.joint)==len(joint or ()) and
                all((cell.factual_state==i//len(post) and cell.counterfactual_state==i%len(post) and cell.probability==v)
                    for i,(cell,v) in enumerate(zip(result.joint,joint or ()))))
    except (ValueError,TypeError,BudgetLimit):return False
    except Exception:return False


def causal_receipt(raw,result_frame):
    ok=verify_causal_result(raw,result_frame)
    result=p.CausalResult()
    try:result=_decode(result_frame,p.CausalResult)
    except Exception:pass
    certified=ok and result.status in SUCCESS
    return p.CausalReceipt(request_sha256=hashlib.sha256(raw).digest(),result_sha256=hashlib.sha256(result_frame).digest(),
        evidence_valid=certified,independently_checked=certified,
        assurance=result.assurance if certified else 'NONE',reason_code='VERIFIED' if certified else 'UNVERIFIED_OR_NONRESULT')


def causal_audit(raw,result_frame):
    result=_decode(result_frame,p.CausalResult)
    verified=causal_receipt(raw,result_frame).evidence_valid
    return p.CausalAudit(schema_version=1,request_sha256=hashlib.sha256(raw).digest(),
        result_sha256=hashlib.sha256(result_frame).digest(),trace_id=result.trace_id,operation=result.operation,
        status=result.status,backend_id=result.backend_id,backend_version=result.backend_version,
        wall_ns=result.wall_ns,assurance=result.assurance if verified else 'NONE',reason_code=result.reason_code if verified else 'UNVERIFIED_OR_NONRESULT')
