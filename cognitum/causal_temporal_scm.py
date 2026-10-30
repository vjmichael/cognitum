"""C14 P4B: bounded exact time-unrolled finite SCM, reusing verified P1 semantics.

An observational distribution, a do intervention and abduction-action-prediction
are different operators. Noise is independent across times *by the declared
model*, not an assumption verified from any observations. Mathematical model
interventions never authorize physical actions.
"""
from __future__ import annotations
import hashlib
import math
import time
from cognitum.causal import run_causal_frame,verify_causal_result
from cognitum.causal_estimation import _decode
from cognitum.proto import causal_temporal_scm_pb2 as t, causal_pb2 as p
from cognitum.planning import TRACE,NAME

MAX_FRAME=90000
LIMITS=('TIME_UNROLLED_FINITE_ASSUMED_SCM_ONLY;INNOVATIONS_ASSUMED_INDEPENDENT_PER_STEP;'
        'CAUSAL_GRAPH_AND_TRANSITION_MECHANISMS_SUPPLIED_NOT_DISCOVERED;'
        'MODEL_EXACT_NOT_REAL_WORLD_CAUSAL_PROOF;DO_DOES_NOT_AUTHORIZE_EXTERNAL_ACTIONS')


def _parse(raw):
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_FRAME:
        raise ValueError('INVALID_TIME_SCM_FRAME')
    req=_decode(raw,t.TimeSCMRequest)
    count=len(req.variables)
    if (req.schema_version!=1 or not TRACE.fullmatch(req.trace_id) or
        not NAME.fullmatch(req.assumption_id) or
        not 2<=req.steps<=4 or not 1<=count<=3 or req.steps*count>8 or
        req.operation not in (t.TIME_SCM_OBSERVATIONAL,t.TIME_SCM_INTERVENTIONAL,t.TIME_SCM_COUNTERFACTUAL) or
        not 1<=req.timeout_ms<=5000 or not 1<=req.max_exogenous_assignments<=4096 or
        not req.HasField('target') or req.target.variable>=count or req.target.time>=req.steps or req.target.state):
        raise ValueError('INVALID_TIME_SCM_REQUEST')
    ids=[v.id for v in req.variables]
    if len(ids)!=len(set(ids)) or any(not NAME.fullmatch(x) or len(x)>20 for x in ids):
        raise ValueError('INVALID_TIME_VARIABLE_IDS')
    sizes=[];noise_sizes=[]
    for i,v in enumerate(req.variables):
        if (not 2<=len(v.states)<=4 or len(set(v.states))!=len(v.states) or
            not 2<=len(v.innovation_states)<=4 or len(set(v.innovation_states))!=len(v.innovation_states) or
            any(not NAME.fullmatch(x) for x in [*v.states,*v.innovation_states]) or
            len(v.initial_probability_ppm)!=len(v.states) or sum(v.initial_probability_ppm)!=1000000 or
            len(v.innovation_probability_ppm)!=len(v.innovation_states) or sum(v.innovation_probability_ppm)!=1000000):
            raise ValueError('INVALID_TIME_STATES_OR_NOISE')
        parents=[(j.variable,j.lag) for j in v.parents]
        if (len(parents)!=len(set(parents)) or
            any(j>=count or lag not in (0,1) or (lag==0 and j>=i) for j,lag in parents)):
            raise ValueError('INVALID_LAGGED_GRAPH')
        sizes.append(len(v.states));noise_sizes.append(len(v.innovation_states))
    if math.prod(len(v.states)*len(v.innovation_states)**(req.steps-1) for v in req.variables)>req.max_exogenous_assignments:
        raise ValueError('EXOGENOUS_ENUMERATION_LIMIT')
    for i,v in enumerate(req.variables):
        expected=math.prod(sizes[j.variable] for j in v.parents)*noise_sizes[i]
        if expected>4096 or len(v.transition_outputs)!=expected or any(state>=sizes[i] for state in v.transition_outputs):
            raise ValueError('INVALID_TRANSITION_TABLE')
    def timed(event):
        if event.variable>=count or event.time>=req.steps or event.state>=sizes[event.variable]:
            raise ValueError('INVALID_TIMED_STATE')
        return event.time*count+event.variable
    evidence=[]
    seen=set()
    for obs in req.factual_evidence:
        i=timed(obs)
        if i in seen:raise ValueError('DUPLICATE_FACTUAL_EVIDENCE')
        seen.add(i);evidence.append((i,obs.state))
    if req.operation==t.TIME_SCM_OBSERVATIONAL and (req.HasField('intervention') or evidence):
        raise ValueError('UNEXPECTED_TIME_SCM_EVIDENCE')
    if req.operation==t.TIME_SCM_INTERVENTIONAL and (not req.HasField('intervention') or evidence):
        raise ValueError('INVALID_TIME_INTERVENTION')
    if req.operation==t.TIME_SCM_COUNTERFACTUAL and (not req.HasField('intervention') or not evidence):
        raise ValueError('COUNTERFACTUAL_REQUIRES_FACTUAL_EVIDENCE')
    intervention=(timed(req.intervention),req.intervention.state) if req.HasField('intervention') else None
    return req,evidence,intervention


def _unroll(req,evidence,intervention):
    count=len(req.variables)
    model=p.StructuralCausalModel(assumption_id=req.assumption_id)
    for step in range(req.steps):
        for i,var in enumerate(req.variables):
            source=(var.initial_probability_ppm if step==0 else var.innovation_probability_ppm)
            states=(var.states if step==0 else var.innovation_states)
            model.exogenous.add(id=f'U_{i}_{step}',states=states,probability_ppm=source)
    for step in range(req.steps):
        for i,var in enumerate(req.variables):
            node=model.endogenous.add(id=f'V_{i}_{step}',states=var.states,noise=[step*count+i])
            if step==0:
                node.function_outputs.extend(range(len(var.states)))
            else:
                node.parents.extend((step-parent.lag)*count+parent.variable for parent in var.parents)
                node.function_outputs.extend(var.transition_outputs)
    op={t.TIME_SCM_OBSERVATIONAL:p.OBSERVATIONAL_QUERY,
        t.TIME_SCM_INTERVENTIONAL:p.INTERVENTIONAL_QUERY,
        t.TIME_SCM_COUNTERFACTUAL:p.COUNTERFACTUAL_QUERY}[req.operation]
    target=req.target.time*count+req.target.variable
    typed=p.CausalRequest(schema_version=1,trace_id=req.trace_id,model=model,operation=op,
        target=target,max_exogenous_assignments=req.max_exogenous_assignments,timeout_ms=req.timeout_ms)
    for index,state in evidence:typed.factual_evidence.add(variable=index,state=state)
    if intervention is not None:typed.interventions.add(variable=intervention[0],state=intervention[1])
    return typed


def _compute(req,evidence,intervention,raw):
    underlying=_unroll(req,evidence,intervention)
    model_hash=hashlib.sha256(underlying.model.SerializeToString(deterministic=True)).digest()
    source=underlying.SerializeToString(deterministic=True)
    reply=run_causal_frame(source,host_authorized=True,enabled=True)
    checked=verify_causal_result(source,reply)
    got=_decode(reply,p.CausalResult)
    out=t.TimeSCMResult(schema_version=1,trace_id=req.trace_id,
        request_sha256=hashlib.sha256(raw).digest(),unrolled_model_sha256=model_hash,
        status=t.TIME_SCM_INCONCLUSIVE,reason_code='MODEL_EXECUTION_NOT_VERIFIED',
        assumptions_and_limits=LIMITS)
    if not checked:return out
    if got.status==p.IMPOSSIBLE_FACTUAL_EVIDENCE:
        out.status=t.TIME_SCM_IMPOSSIBLE_EVIDENCE
        out.reason_code='ZERO_PROBABILITY_FACTUAL_WORLD'
        return out
    if got.status!=p.EXACT_MODEL_RESULT or not got.independently_checked:return out
    out.posterior.extend(got.posterior)
    out.counterfactual_joint.extend(got.joint)
    out.factual_evidence_probability=got.factual_evidence_probability
    out.finite_model_verified=True
    out.status=t.TIME_SCM_COMPUTED
    out.reason_code='ASSUMED_TIME_SCM_EXACT_ONLY'
    return out


def run_time_scm_frame(raw,*,host_authorized=False,enabled=False):
    start=time.monotonic_ns()
    out=t.TimeSCMResult(schema_version=1,
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        status=t.TIME_SCM_REJECTED,reason_code='INVALID_TIME_SCM_FRAME',assumptions_and_limits=LIMITS)
    try:
        req,evidence,intervention=_parse(raw)
        out.trace_id=req.trace_id
        if not host_authorized:raise ValueError('HOST_AUTHORIZATION_REQUIRED')
        if not enabled:raise ValueError('TIME_SCM_DISABLED')
        out=_compute(req,evidence,intervention,raw)
    except (ValueError,TypeError) as exc:
        reason=str(exc)
        out.reason_code=reason if reason.isupper() and len(reason)<100 else 'INVALID_TIME_SCM_REQUEST'
    except Exception:
        out.status=t.TIME_SCM_INCONCLUSIVE
        out.reason_code='TIME_SCM_RUNTIME_FAILURE'
    if out.status!=t.TIME_SCM_COMPUTED:
        del out.posterior[:]
        del out.counterfactual_joint[:]
        out.finite_model_verified=False
    out.wall_ns=time.monotonic_ns()-start
    return out.SerializeToString(deterministic=True)


def time_scm_receipt(raw,reply):
    out=t.TimeSCMReceipt(
        request_sha256=hashlib.sha256(raw if isinstance(raw,bytes) else b'').digest(),
        result_sha256=hashlib.sha256(reply if isinstance(reply,bytes) else b'').digest(),
        reason_code='NOT_VERIFIED')
    try:
        req,evidence,intervention=_parse(raw)
        got=_decode(reply,t.TimeSCMResult)
        if got.status!=t.TIME_SCM_COMPUTED or got.request_sha256!=out.request_sha256:return out
        expected=_compute(req,evidence,intervention,raw)
        expected.wall_ns=got.wall_ns
        if expected.status==t.TIME_SCM_COMPUTED and expected.SerializeToString(deterministic=True)==got.SerializeToString(deterministic=True):
            out.exact_model_replay=True
            out.reason_code='ASSUMED_TIME_SCM_MODEL_REPLAY_ONLY'
    except Exception:
        pass
    return out
