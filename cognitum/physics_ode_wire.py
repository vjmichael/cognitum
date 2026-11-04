"""C16 ODE native typed canonical Protobuf contract and replay verifier."""
from hashlib import sha256
from math import isfinite
from google.protobuf.message import DecodeError
from .proto import physics_ode_pb2 as pb
from .physics_ode import PhysicalModel,validate,integrate

MAX_REQUEST=8192
MAX_RESPONSE=200000
STATUSES=frozenset(("OK","EVENT_STOP","UNSUPPORTED","UNKNOWN_RESOURCE_OR_NUMERICAL_FAILURE",
                    "UNKNOWN_SOLVER_FAILED","UNKNOWN_NONFINITE"))


def _read(data,cls,limit):
    if type(data) is not bytes or not 0<len(data)<=limit:
        raise ValueError("invalid physics wire length")
    obj=cls()
    try:obj.ParseFromString(data)
    except DecodeError as exc:raise ValueError("malformed physics wire") from exc
    known=cls();known.CopyFrom(obj);known.DiscardUnknownFields()
    if known!=obj or obj.SerializeToString(deterministic=True)!=data:
        raise ValueError("noncanonical physics request or unknown fields")
    return obj


def _model(r):
    if r.schema_version!=1:
        raise ValueError("unsupported physics schema")
    return validate(PhysicalModel(
        r.kind,r.unit_system,r.mass_kg,r.spring_n_per_m,
        r.damping_n_s_per_m,r.force_n,r.gravity_m_per_s2,
        r.initial_position_m,r.initial_velocity_m_per_s,
        r.t_end_s,r.output_steps,r.rtol,r.atol,r.method,
        r.max_internal_step_s,r.max_function_evals,
        r.stop_at_position_m if r.has_stop_boundary else None,
        r.validation_domain,
    ))


def execute(request:bytes)->bytes:
    req=_read(request,pb.PhysicalRequest,MAX_REQUEST)
    model=_model(req)
    r=integrate(model)
    if r.status not in STATUSES:
        raise ValueError("unknown solver status")
    out=pb.PhysicalResult(schema_version=1,status=r.status,
        solver_method=r.solver_method,function_evals=r.function_evals,
        request_sha256=sha256(request).hexdigest(),
        limitations=r.limitations,reached_end=r.reached_end)
    if r.requested_rtol is not None:out.requested_rtol=r.requested_rtol
    if r.requested_atol is not None:out.requested_atol=r.requested_atol
    if r.status in ("OK","EVENT_STOP"):
        out.has_balance=True
        out.max_balance_residual_j=r.max_balance_residual_j
        out.max_invariant_relative_drift=r.max_invariant_relative_drift
        if r.convergence_max_error_m is not None:
            out.has_analytic_comparison=True
            out.convergence_max_error_m=r.convergence_max_error_m
        if r.event_time_s is not None:
            out.has_event=True
            out.event_time_s=r.event_time_s
        for item in r.samples:
            out.samples.add(t_s=item.t_s,position_m=item.position_m,
                            velocity_m_per_s=item.velocity_m_per_s,
                            mechanical_energy_j=item.mechanical_energy_j)
    frame=out.SerializeToString(deterministic=True)
    if len(frame)>MAX_RESPONSE:
        raise ValueError("oversized physics result")
    return frame


def verify(request:bytes,response:bytes):
    _model(_read(request,pb.PhysicalRequest,MAX_REQUEST))
    result=_read(response,pb.PhysicalResult,MAX_RESPONSE)
    if (result.schema_version!=1 or result.status not in STATUSES
            or result.request_sha256!=sha256(request).hexdigest()):
        raise ValueError("mismatched physics output")
    if result.status in ("OK","EVENT_STOP"):
        if not result.samples or not result.has_balance:
            raise ValueError("successful physical trajectory lacks samples")
    elif result.samples or result.has_event or result.has_balance or result.has_analytic_comparison:
        raise ValueError("unsuccessful solver fabricated physical trajectory")
    # Numerical solvers are independently reexecuted; tiny hardware/runtime
    # floating-point discrepancies are tolerated only within strict tolerance.
    expected=_read(execute(request),pb.PhysicalResult,MAX_RESPONSE)
    if (result.status!=expected.status or result.solver_method!=expected.solver_method
            or result.has_event!=expected.has_event
            or result.has_balance!=expected.has_balance
            or result.has_analytic_comparison!=expected.has_analytic_comparison
            or result.reached_end!=expected.reached_end
            or len(result.samples)!=len(expected.samples)):
        raise ValueError("physics solver result changed")
    def near(a,b):
        return isfinite(a) and isfinite(b) and abs(a-b)<=1e-7*max(1,abs(b))
    for a,b in zip(result.samples,expected.samples):
        if not all(near(getattr(a,k),getattr(b,k))
                   for k in ("t_s","position_m","velocity_m_per_s","mechanical_energy_j")):
            raise ValueError("physical trajectory fails independent replay")
    for k in ("max_balance_residual_j","max_invariant_relative_drift",
              "event_time_s","convergence_max_error_m"):
        if not near(getattr(result,k),getattr(expected,k)):
            raise ValueError("physical diagnostics differ")
    return result
