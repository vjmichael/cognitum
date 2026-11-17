"""Bounded COG-06D specialist compositions; existing typed kernels only.

Exact integer completeness uses C10 witness checks and an independent
direct enumerator. C16 weighted idealized harmonic mixtures are conditional
on supplied, mutually exclusive/exhaustive scenario assumptions.
"""
from itertools import product
from math import prod,isfinite,fsum,cos,sin,sqrt
import operator
from .proto import composition_pb2 as pb,formal_pb2 as formal,physics_ode_pb2 as physics

MAX_CASES=4096
MAX_SOLUTIONS=128
MAX_SCENARIOS=4
MAX_STEPS=16
SET_LIMITS=("finite_declared_integer_domains_only","formalization_not_verified")
MIXTURE_ASSUMPTION="mutually_exclusive_exhaustive_scenarios"
MIXTURE_LIMITS=("conditional_on_declared_scenarios_and_weights","idealized_harmonic_model_only",
                "not_empirical_uncertainty_or_calibration")
RELATIONS={"eq":operator.eq,"ne":operator.ne,"lt":operator.lt,
           "le":operator.le,"gt":operator.gt,"ge":operator.ge}

def _formal_request(raw):
    from .cooperative_cpu import parse
    from .formal_wire import to_problem
    req=parse(raw,formal.VerifyRequest)
    problem=to_problem(req)
    if req.backend!="exhaustive" or req.proof_required is not True or not 1<=req.timeout_ms<=10000:
        raise ValueError("complete set requires bounded exhaustive assurance")
    count=prod(v.upper-v.lower+1 for v in req.variables)
    if count>MAX_CASES:raise ValueError("complete set case bound")
    return req,problem,count

def solution_set(raw):
    from .cooperative_cpu import wire,sha
    from .formal_smt import satisfies
    req,problem,count=_formal_request(raw)
    result=pb.SolutionSet(schema_version=1,status="COMPLETE",request_sha256=sha(raw),cases_checked=count,limitations=SET_LIMITS)
    for row in product(*(range(v.lower,v.upper+1) for v in req.variables)):
        if satisfies(problem,row):
            if len(result.solutions)>=MAX_SOLUTIONS:raise ValueError("complete set result bound")
            result.solutions.add(values=row)
    return wire(result)

def check_solution_set(raw,result):
    from .cooperative_cpu import parse,sha
    req,_,count=_formal_request(raw)
    out=parse(result,pb.SolutionSet)
    if (out.schema_version!=1 or out.status!="COMPLETE" or out.request_sha256!=sha(raw)
            or out.cases_checked!=count or len(out.solutions)>MAX_SOLUTIONS
            or tuple(out.limitations)!=SET_LIMITS):
        raise ValueError("invalid complete-set receipt")
    # Independent evaluation path (no call to C10 satisfies/exhaustive).
    names=tuple(v.name for v in req.variables)
    positions={n:i for i,n in enumerate(names)}
    atoms=[(tuple((positions[t.name],t.coefficient) for t in a.terms),
              RELATIONS[a.relation],a.rhs) for a in req.constraints]
    expected=[]
    for row in product(*(range(v.lower,v.upper+1) for v in req.variables)):
        if all(compare(sum(row[i]*c for i,c in terms),rhs) for terms,compare,rhs in atoms):
            expected.append(row)
            if len(expected)>MAX_SOLUTIONS:raise ValueError("complete set result bound")
    if tuple(tuple(x.values) for x in out.solutions)!=tuple(expected):
        raise ValueError("incomplete or forged solution set")
    return "complete_integer_enumeration"

def _mixture_request(raw):
    from .cooperative_cpu import parse
    from .physics_ode_wire import _model
    req=parse(raw,pb.MixtureRequest)
    if (req.schema_version!=1 or req.scenario_assumption!=MIXTURE_ASSUMPTION
            or not 2<=len(req.scenarios)<=MAX_SCENARIOS
            or len(req.weights)!=len(req.scenarios)
            or any(not isfinite(x) or not 0<=x<=1 for x in req.weights)
            or abs(fsum(req.weights)-1)>1e-12):
        raise ValueError("invalid finite mixture")
    names=[s.name for s in req.scenarios]
    if len(set(names))!=len(names) or any(not n.isascii() or not n.isidentifier() or len(n)>32 for n in names):
        raise ValueError("invalid scenario identity")
    models=[]
    for scenario in req.scenarios:
        q=parse(scenario.physical_request,physics.PhysicalRequest)
        _model(q)
        # Deliberately narrow analytical domain with a common terminal time.
        if (q.kind!="harmonic" or q.has_stop_boundary or q.validation_domain!="idealized_reference"
                or q.output_steps>MAX_STEPS or q.rtol>1e-9 or q.atol>1e-11
                or q.max_function_evals>20000):
            raise ValueError("unsupported mixture model")
        models.append(q)
    if any(q.t_end_s!=models[0].t_end_s for q in models):
        raise ValueError("different terminal time")
    return req,models

def _moments(weights,positions):
    mu=fsum(w*x for w,x in zip(weights,positions))
    variance=fsum(w*(x-mu)**2 for w,x in zip(weights,positions))
    if not isfinite(mu) or not isfinite(variance):raise ValueError("nonfinite moments")
    return mu,variance

def mixture(raw):
    from .cooperative_cpu import wire,sha,parse
    from .physics_ode_wire import execute
    req,models=_mixture_request(raw)
    out=pb.MixtureResult(schema_version=1,status="COMPLETE",request_sha256=sha(raw),limitations=MIXTURE_LIMITS)
    positions=[]
    for scenario,weight,q in zip(req.scenarios,req.weights,models):
        result=execute(scenario.physical_request)
        r=parse(result,physics.PhysicalResult)
        if r.status!="OK" or not r.reached_end or len(r.samples)!=q.output_steps+1:
            raise ValueError("scenario failed; no partial mixture")
        positions.append(r.samples[-1].position_m)
        out.scenarios.add(name=scenario.name,weight=weight,physical_result=result)
    out.mean_position_m,out.variance_position_m2=_moments(req.weights,positions)
    return wire(out)

def check_mixture(raw,result):
    from .cooperative_cpu import parse,sha,_finite_fields
    from .physics_ode_wire import verify
    req,models=_mixture_request(raw)
    out=parse(result,pb.MixtureResult)
    if (out.schema_version!=1 or out.status!="COMPLETE" or out.request_sha256!=sha(raw)
            or len(out.scenarios)!=len(req.scenarios) or tuple(out.limitations)!=MIXTURE_LIMITS):
        raise ValueError("unbound mixture")
    endpoints=[];analytic=[]
    def near(a,b):
        return isfinite(a) and isfinite(b) and abs(a-b)<=1e-7*max(1.,abs(b))
    for scenario,weight,q,r in zip(req.scenarios,req.weights,models,out.scenarios):
        if r.name!=scenario.name or r.weight!=weight:raise ValueError("scenario mapping changed")
        checked=verify(scenario.physical_request,r.physical_result)
        _finite_fields(checked)
        if (checked.status!="OK" or not checked.reached_end or len(checked.samples)!=q.output_steps+1
                or not checked.has_balance or not checked.has_analytic_comparison or checked.has_event
                or not 1<=checked.function_evals<=q.max_function_evals
                or checked.requested_rtol!=q.rtol or checked.requested_atol!=q.atol):
            raise ValueError("incomplete trajectory")
        omega=sqrt(q.spring_n_per_m/q.mass_kg)
        for i,point in enumerate(checked.samples):
            t=q.t_end_s*i/q.output_steps
            x=q.initial_position_m*cos(omega*t)+q.initial_velocity_m_per_s*sin(omega*t)/omega
            v=-q.initial_position_m*omega*sin(omega*t)+q.initial_velocity_m_per_s*cos(omega*t)
            energy=(q.mass_kg*v*v+q.spring_n_per_m*x*x)/2
            if (not near(point.t_s,t) or not near(point.position_m,x)
                    or not near(point.velocity_m_per_s,v) or not near(point.mechanical_energy_j,energy)):
                raise ValueError("trajectory fails analytic oracle")
        endpoints.append(checked.samples[-1].position_m)
        analytic.append(x)
    actual_mu,actual_var=_moments(req.weights,endpoints)
    oracle_mu=fsum(w*x for w,x in zip(req.weights,analytic))
    # Independent pairwise variance formula avoids same moment algorithm.
    oracle_var=fsum(req.weights[i]*req.weights[j]*(analytic[i]-analytic[j])**2
                    for i in range(len(analytic)) for j in range(i+1,len(analytic)))
    if (not near(out.mean_position_m,actual_mu) or not near(out.variance_position_m2,actual_var)
            or not near(out.mean_position_m,oracle_mu) or not near(out.variance_position_m2,oracle_var)
            or out.variance_position_m2<0):
        raise ValueError("mixture moments fail independent oracle")
    return "conditional_mixture_analytic_checked"
