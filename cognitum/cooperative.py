"""Bounded, host-admitted cooperative graph over the existing Runtime.

Internal Python plan objects carry canonical domain Protobuf frames. They
are not a network protocol, model grant, scheduler service or durable store.
Only complete, independently checked graph outputs are published.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from time import monotonic
import re

from .contracts import HostContext,Request,digest
from .runtime import Runtime
from .cooperative_cpu import (ROUTES,CooperativeCpu,PLUGIN_NAME,VERSION,MAX_FRAME,
                              type_url,sha,parse,wire,encode,decode,verification_binding)

MAX_NODES=8
MAX_EDGES=16
MAX_INPUT_BYTES=32768
MAX_RESULT_BYTES=32768
MAX_PLAN_MS=30000
MAX_STEP_MS=10000
_ID=re.compile(r"[A-Za-z0-9_.:-]{1,48}\Z",re.ASCII)
_HASH=re.compile(r"[0-9a-f]{64}\Z",re.ASCII)
_BUILD=re.compile(r"[0-9a-f]{40}\Z",re.ASCII)
BRIDGES={
    "linear_integer_candidate":("math.linear","formal.integer"),
    "plan_schedule_precedence":("planning.graph","optimization.schedule"),
}

def _id(value):
    if type(value) is not str or not _ID.fullmatch(value):raise ValueError("invalid identity")
    return value

def _hash(value):
    if type(value) is not str or not _HASH.fullmatch(value):raise ValueError("invalid digest")
    return value

@dataclass(frozen=True)
class SourceStamp:
    source_id: str
    revision: str
    frame_sha256: str

@dataclass(frozen=True)
class Dependency:
    predecessor: str
    bridge: str

@dataclass(frozen=True)
class Step:
    step_id: str
    operation: str
    input_type_url: str
    route_sha256: str
    frame: bytes
    source: SourceStamp
    timeout_ms: int=10000
    dependencies: tuple[Dependency,...]=()

@dataclass(frozen=True)
class Plan:
    plan_id: str
    workspace_id: str
    subject_id: str
    build_sha: str
    timeout_ms: int
    steps: tuple[Step,...]

@dataclass(frozen=True)
class Admission:
    """Trusted host callback input. This record is never itself a grant."""
    plan_sha256: str
    plan_id: str
    workspace_id: str
    subject_id: str
    build_sha: str
    phase: str
    step_id: str=""
    operation: str=""
    request_sha256: str=""
    predecessor_receipts: tuple[str,...]=()
    result_sha256: str=""

@dataclass(frozen=True)
class StepReceipt:
    step_id: str
    operation: str
    route_sha256: str
    source: SourceStamp
    request_sha256: str
    result_sha256: str
    output_type_url: str
    assurance: str
    predecessor_receipts: tuple[str,...]
    verification_sha256: str
    receipt_sha256: str
    frame: bytes

@dataclass(frozen=True)
class Outcome:
    status: str
    plan_sha256: str=""
    failed_step: str=""
    receipts: tuple[StepReceipt,...]=()
    limitation: str="host_reference_only_not_authenticated_or_os_confined"

class _Stop(Exception):
    def __init__(self,status):
        self.status=status

def _validate(plan):
    if type(plan) is not Plan:raise ValueError("typed plan required")
    for x in (plan.plan_id,plan.workspace_id,plan.subject_id):_id(x)
    if type(plan.build_sha) is not str or not _BUILD.fullmatch(plan.build_sha):
        raise ValueError("source build identity required")
    if type(plan.timeout_ms) is not int or not 1<=plan.timeout_ms<=MAX_PLAN_MS:
        raise ValueError("plan budget")
    if type(plan.steps) is not tuple or not 1<=len(plan.steps)<=MAX_NODES:
        raise ValueError("graph bound")
    nodes={};input_bytes=0;edges=0
    for step in plan.steps:
        if type(step) is not Step:raise ValueError("typed step required")
        _id(step.step_id)
        if step.step_id in nodes:raise ValueError("duplicate step")
        if type(step.operation) is not str or step.operation not in ROUTES:
            raise ValueError("unreviewed operation")
        route=ROUTES[step.operation]
        if (type(step.input_type_url) is not str or type(step.route_sha256) is not str
                or step.input_type_url!=type_url(route.input_class) or step.route_sha256!=route.identity):
            raise ValueError("route or type mismatch")
        parse(step.frame,route.input_class)
        if type(step.source) is not SourceStamp:raise ValueError("source stamp required")
        _id(step.source.source_id);_id(step.source.revision)
        if _hash(step.source.frame_sha256)!=sha(step.frame):raise ValueError("input source digest mismatch")
        if type(step.timeout_ms) is not int or not 1<=step.timeout_ms<=MAX_STEP_MS:
            raise ValueError("step budget")
        if type(step.dependencies) is not tuple or len(step.dependencies)>MAX_EDGES:raise ValueError("typed dependency tuple required")
        parents=set();data_edges=0
        for dep in step.dependencies:
            if type(dep) is not Dependency:raise ValueError("typed dependency required")
            _id(dep.predecessor)
            if dep.predecessor==step.step_id or dep.predecessor in parents:
                raise ValueError("duplicate or self dependency")
            if type(dep.bridge) is not str or dep.bridge not in (*BRIDGES,"requires_verified"):
                raise ValueError("unknown dependency adapter")
            data_edges+=dep.bridge!="requires_verified"
            parents.add(dep.predecessor)
        if data_edges>1:raise ValueError("conflicting input transformations")
        edges+=len(parents);input_bytes+=len(step.frame);nodes[step.step_id]=step
    if edges>MAX_EDGES or input_bytes>MAX_INPUT_BYTES:raise ValueError("aggregate graph bound")
    for step in plan.steps:
        for dep in step.dependencies:
            if dep.predecessor not in nodes:raise ValueError("missing dependency")
            if dep.bridge!="requires_verified" and BRIDGES[dep.bridge]!=(nodes[dep.predecessor].operation,step.operation):
                raise ValueError("dependency type mismatch")
    # Deterministic topological order; preflight cycle detection before workers.
    ordered=[];seen=set()
    while len(ordered)<len(nodes):
        available=sorted(k for k,n in nodes.items() if k not in seen
                         and all(d.predecessor in seen for d in n.dependencies))
        if not available:raise ValueError("dependency cycle")
        for k in available:
            ordered.append(nodes[k]);seen.add(k)
    return tuple(ordered)

def plan_digest(plan):
    _validate(plan)
    return digest({"schema":"cooperative.plan.v1","plan":plan.plan_id,
                   "workspace":plan.workspace_id,"subject":plan.subject_id,
                   "build":plan.build_sha,"timeout":plan.timeout_ms,
                   "steps":[{"id":n.step_id,"operation":n.operation,"route":n.route_sha256,
                             "type":n.input_type_url,"source":(n.source.source_id,n.source.revision,
                             n.source.frame_sha256),"timeout":n.timeout_ms,
                             "dependencies":[(d.predecessor,d.bridge) for d in n.dependencies]}
                            for n in sorted(plan.steps,key=lambda s:s.step_id)]})

def _transform(bridge,parent_request,parent,child_frame):
    source=ROUTES[parent.operation]
    out=parse(parent.frame,source.output_class)
    original=parse(parent_request,source.input_class)
    target=ROUTES[BRIDGES[bridge][1]]
    req=parse(child_frame,target.input_class)
    if bridge=="linear_integer_candidate":
        # Check a C05 solution against separate C10 integer constraints.
        # Each row maps by the explicitly ordered variables in the host plan.
        if original.action!="solve" or len(out.rows)!=len(req.variables):
            raise ValueError("linear solution cannot supply integer candidate")
        for row,var in zip(out.rows,req.variables):
            if len(row.entries)!=1:raise ValueError("invalid solution dimension")
            value=Fraction(row.entries[0])
            if value.denominator!=1 or abs(value.numerator)>2**31-1:
                raise ValueError("nonintegral or oversized candidate")
            atom=req.constraints.add(relation="eq",rhs=value.numerator)
            atom.terms.add(name=var.name,coefficient=1)
    elif bridge=="plan_schedule_precedence":
        # Plan actions become explicit precedence, never durations or units.
        names=tuple(out.actions)
        jobs={j.name:j for j in req.jobs}
        if not names or len(set(names))!=len(names) or len(jobs)!=len(req.jobs) or set(names)!=set(jobs):
            raise ValueError("plan and schedule job identity mismatch")
        for a,b in zip(names,names[1:]):
            if a not in jobs[b].after:jobs[b].after.append(a)
    else:raise ValueError("unreviewed transformation")
    return wire(req)

def execute(runtime,plan,context,*,expected_build_sha,admit,source_current,cancelled):
    """Only trusted host code supplies callbacks and the existing Runtime.

    Admission is checked for the complete plan and each concrete compute and
    verify request; source versions and cancellation are checked before/after
    each worker and before publication. Existing disposable worker timeouts
    bound calls, not hard OS memory/custody, which remain host obligations.
    No user/model-supplied callbacks, paths, executable expressions or grants.
    """
    key="";current=""
    try:
        ordered=_validate(plan);key=plan_digest(plan)
        if (type(context) is not HostContext or
            (context.workspace_id,context.subject_id)!=(plan.workspace_id,plan.subject_id)
            or context.allow_research is not False or plan.build_sha!=expected_build_sha
            or type(runtime) is not Runtime or not all(callable(x) for x in (admit,source_current,cancelled))):
            raise _Stop("denied")
    except _Stop as exc:return Outcome(exc.status,key)
    except (ValueError,TypeError,AttributeError,OverflowError):return Outcome("invalid_plan",key)

    deadline=monotonic()+plan.timeout_ms/1000
    results={};requests={};total_output=0;total_input=0
    expected_manifest=digest(CooperativeCpu().manifest().describe())
    def check(limit):
        if cancelled() is not False:raise _Stop("cancelled")
        if monotonic()>=limit:raise _Stop("timed_out")
        for n in ordered:
            if source_current(n.source,context) is not True:raise _Stop("stale_source")
        if monotonic()>=limit:raise _Stop("timed_out")
        if cancelled() is not False:raise _Stop("cancelled")
    def admission(phase,node=None,raw=None,parents=(),response=None):
        claim=Admission(key,plan.plan_id,plan.workspace_id,plan.subject_id,plan.build_sha,
                        phase,node.step_id if node else "",node.operation if node else "",
                        sha(raw) if raw is not None else "",parents,
                        sha(response) if response is not None else "")
        if admit(claim,context) is not True:raise _Stop("denied")
    def invoke(step,phase,raw,limit,parents,response=None):
        route=ROUTES[step.operation];op=route.worker_operation(phase)
        check(limit);admission(phase,step,raw,parents,response);check(limit)
        # One existing registry lock pins the installed factory and manifest
        # through dispatch. Revocation applies to the next admission.
        with runtime.registry.lock:
            entry=runtime.registry.resolve(op,False)
            if entry is None:raise _Stop("unavailable")
            plugin,spec=entry
            if (plugin.factory is not CooperativeCpu or plugin.manifest.name!=PLUGIN_NAME
                or digest(plugin.manifest.describe())!=expected_manifest
                or spec.effects or spec.deterministic is not True):
                raise _Stop("unavailable")
            ms=min(MAX_STEP_MS,int((limit-monotonic())*1000))
            if ms<1:raise _Stop("timed_out")
            payload={"frame":encode(raw)}
            if response is not None:payload["result"]=encode(response)
            request=Request(plan.plan_id+":"+step.step_id+":"+phase,plan.plan_id,op,payload,
                            plan.workspace_id,plan.subject_id,
                            operation_schema_version=spec.schema_version,timeout_ms=ms)
            reply=runtime.call(request,context)
        check(limit)
        if reply.execution_status=="timed_out":raise _Stop("timed_out")
        if reply.execution_status=="denied":raise _Stop("denied")
        if reply.execution_status=="unavailable":raise _Stop("unavailable")
        if (reply.execution_status!="completed" or reply.module!={"name":PLUGIN_NAME,"version":VERSION}
                or reply.request_id!=request.request_id or reply.correlation_id!=plan.plan_id
                or reply.operation!=op or type(reply.result) is not dict):
            raise _Stop("verification_failed" if phase=="verify" else "compute_failed")
        spec.output.validate(reply.result)
        return reply.result
    try:
        check(deadline);admission("plan");check(deadline)
        # Confirm all routes are installed before any worker runs.
        with runtime.registry.lock:
            for n in ordered:
                for phase in ("compute","verify"):
                    resolved=runtime.registry.resolve(ROUTES[n.operation].worker_operation(phase),False)
                    if (resolved is None or resolved[0].factory is not CooperativeCpu
                        or digest(resolved[0].manifest.describe())!=expected_manifest):
                        current=n.step_id;raise _Stop("unavailable")
        for step in ordered:
            current=step.step_id;limit=min(deadline,monotonic()+step.timeout_ms/1000)
            check(limit);raw=step.frame
            parent_hashes=tuple(results[d.predecessor].receipt_sha256 for d in step.dependencies)
            for dep in step.dependencies:
                if dep.bridge!="requires_verified":
                    try:raw=_transform(dep.bridge,requests[dep.predecessor],results[dep.predecessor],raw)
                    except (ValueError,TypeError,OverflowError,ZeroDivisionError):raise _Stop("bridge_failed")
            check(limit)
            route=ROUTES[step.operation]
            parse(raw,route.input_class)
            total_input+=len(raw)
            if total_input>MAX_INPUT_BYTES:raise _Stop("resource_limit")
            try:
                response=decode(invoke(step,"compute",raw,limit,parent_hashes)["frame"])
                parse(response,route.output_class)
            except (ValueError,TypeError,KeyError):raise _Stop("compute_failed")
            total_output+=len(response)
            if total_output>MAX_RESULT_BYTES:raise _Stop("resource_limit")
            try:
                verifier=invoke(step,"verify",raw,limit,parent_hashes,response)
                assurance=verifier["assurance"];bound=verifier["receipt"]
                if assurance not in route.assurances or bound!=verification_binding(route,raw,response,assurance):
                    raise ValueError("unbound verifier response")
            except (ValueError,TypeError,KeyError):raise _Stop("verification_failed")
            check(limit)
            receipt=digest({"plan":key,"step":step.step_id,"route":route.identity,
                            "source":(step.source.source_id,step.source.revision,step.source.frame_sha256),
                            "request":sha(raw),"result":sha(response),"parents":parent_hashes,
                            "verification":bound,"assurance":assurance})
            requests[current]=raw
            results[current]=StepReceipt(current,step.operation,route.identity,step.source,
                sha(raw),sha(response),type_url(route.output_class),assurance,parent_hashes,bound,receipt,response)
        current=""
        check(deadline);admission("publish",parents=tuple(x.receipt_sha256 for x in results.values()))
        check(deadline)
        return Outcome("completed",key,receipts=tuple(results.values()))
    except _Stop as exc:
        return Outcome(exc.status,key,current)
    except Exception:
        # Do not leak arbitrary host/worker exception text or partially computed
        # outputs; underlying Runtime trace remains the host diagnostic source.
        return Outcome("execution_error",key,current)
