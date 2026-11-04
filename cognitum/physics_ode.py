"""C16 bounded dimensional physical-model integration using SciPy solve_ivp.

First-party code only validates typed model templates, enforces resource
bounds, checks numerical invariants and reports uncertainty indicators.
No model-authored Python, arbitrary expression parsing, host effects or
claims that the input physical model corresponds to real-world observations.
"""
from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Literal

METHODS=frozenset(("RK45","DOP853","Radau","BDF"))
MAX_POINTS=256


@dataclass(frozen=True)
class PhysicalModel:
    kind: str            # harmonic | damped | forced | falling_drag
    unit_system: str     # SI:m,s,kg,N
    mass_kg: float
    spring_n_per_m: float
    damping_n_s_per_m: float
    force_n: float
    gravity_m_per_s2: float
    initial_position_m: float
    initial_velocity_m_per_s: float
    t_end_s: float
    output_steps: int
    rtol: float
    atol: float
    method: str
    max_internal_step_s: float
    max_function_evals: int = 20000
    stop_at_position_m: float | None = None
    validation_domain: str = "idealized_reference"


@dataclass(frozen=True)
class PhysicsSample:
    t_s: float
    position_m: float
    velocity_m_per_s: float
    mechanical_energy_j: float


@dataclass(frozen=True)
class PhysicsResult:
    status: str
    samples: tuple[PhysicsSample,...] = ()
    solver_method: str = ""
    requested_rtol: float | None = None
    requested_atol: float | None = None
    function_evals: int = 0
    convergence_max_error_m: float | None = None
    max_balance_residual_j: float | None = None
    max_invariant_relative_drift: float | None = None
    event_time_s: float | None = None
    reached_end: bool = False
    limitations: tuple[str,...] = (
        "idealized_model_inputs_caller_supplied",
        "numerical_tolerance_not_empirical_model_uncertainty",
        "source_and_units_declared_not_authenticated",
        "not_production_host_isolated_or_cancelable",
    )


def _finite_number(v):
    return type(v) in (int,float) and isfinite(v)


def validate(p: PhysicalModel)->PhysicalModel:
    if type(p) is not PhysicalModel:
        raise ValueError("typed physical model required")
    if p.kind not in ("harmonic","damped","forced","falling_drag"):
        raise ValueError("unsupported equation family")
    if p.unit_system!="SI:m,s,kg,N":
        raise ValueError("unit system mismatch; convert to SI first")
    if p.method not in METHODS:
        raise ValueError("unsupported standard SciPy integration method")
    numeric=("mass_kg","spring_n_per_m","damping_n_s_per_m","force_n",
             "gravity_m_per_s2","initial_position_m","initial_velocity_m_per_s",
             "t_end_s","rtol","atol","max_internal_step_s")
    if any(not _finite_number(getattr(p,k)) for k in numeric):
        raise ValueError("nonfinite dimensional model")
    if (not 0<p.mass_kg<=100000 or not 0<=p.spring_n_per_m<=100000
            or not 0<=p.damping_n_s_per_m<=100000
            or abs(p.force_n)>100000 or not 0<=p.gravity_m_per_s2<=100
            or abs(p.initial_position_m)>100000
            or abs(p.initial_velocity_m_per_s)>100000):
        raise ValueError("out of domain physical parameters")
    if (p.kind=="harmonic" and
        (p.spring_n_per_m<=0 or p.damping_n_s_per_m!=0 or p.force_n!=0
         or p.gravity_m_per_s2!=0)):
        raise ValueError("harmonic template requires undriven undamped spring")
    if p.kind=="damped" and (p.spring_n_per_m<=0 or p.force_n!=0 or p.gravity_m_per_s2!=0):
        raise ValueError("damped template requires spring and no external force")
    if p.kind=="forced" and (p.spring_n_per_m<=0 or p.gravity_m_per_s2!=0):
        raise ValueError("forced template requires spring and no gravity")
    if p.kind=="falling_drag" and (p.spring_n_per_m!=0 or p.force_n!=0
                                   or p.gravity_m_per_s2<=0):
        raise ValueError("falling drag requires positive downward gravity, no spring")
    if (not 0<p.t_end_s<=1000 or not 1<=p.output_steps<=MAX_POINTS
            or type(p.output_steps) is not int
            or not 1e-11<=p.rtol<=1e-3 or not 1e-13<=p.atol<=1e-3
            or not 1e-7<=p.max_internal_step_s<=p.t_end_s):
        raise ValueError("invalid integration time/tolerance/domain")
    if (type(p.max_function_evals) is not int
            or not 50<=p.max_function_evals<=100000):
        raise ValueError("invalid evaluation resource budget")
    if (type(p.validation_domain) is not str or
            p.validation_domain not in ("idealized_reference","lab_measurement","simulation_input")):
        raise ValueError("explicit input validation domain required")
    if p.stop_at_position_m is not None:
        if (not _finite_number(p.stop_at_position_m) or
                abs(p.stop_at_position_m)>100000 or
                p.initial_position_m<=p.stop_at_position_m or
                p.initial_velocity_m_per_s>0 and p.kind=="falling_drag"):
            raise ValueError("event boundary incompatible with start")
    return p


def _acceleration(p,x,v):
    if p.kind=="falling_drag":
        # Positive x is upwards, gravity is downwards; damping is linear.
        return -p.gravity_m_per_s2-p.damping_n_s_per_m*v/p.mass_kg
    return (p.force_n-p.spring_n_per_m*x-p.damping_n_s_per_m*v)/p.mass_kg


def _energy(p,x,v):
    return p.mass_kg*v*v/2 + p.spring_n_per_m*x*x/2 + (
        p.mass_kg*p.gravity_m_per_s2*x if p.kind=="falling_drag" else 0.0)


def _power(p,x,v):
    # Constant external drive minus irreversible viscous dissipation.
    return p.force_n*v-p.damping_n_s_per_m*v*v


def _analytic(p,t):
    if p.kind!="harmonic":
        return None
    from math import cos,sin
    omega=sqrt(p.spring_n_per_m/p.mass_kg)
    x=p.initial_position_m*cos(omega*t)+p.initial_velocity_m_per_s*sin(omega*t)/omega
    return x


def integrate(p:PhysicalModel)->PhysicsResult:
    validate(p)
    try:
        import numpy as np
        from scipy.integrate import solve_ivp, trapezoid
    except ImportError:
        return PhysicsResult("UNSUPPORTED",solver_method=p.method)
    count=0
    def rhs(t,y):
        nonlocal count
        count+=1
        if count>p.max_function_evals:
            raise RuntimeError("evaluation_budget_exceeded")
        if not all(isfinite(float(v)) and abs(float(v))<=1e12 for v in y):
            raise RuntimeError("physical_state_overflow")
        x,v,work=y
        return (v,_acceleration(p,x,v),_power(p,x,v))
    event=None
    if p.stop_at_position_m is not None:
        def event(t,y):
            return y[0]-p.stop_at_position_m
        event.terminal=True
        event.direction=-1
    t_grid=np.linspace(0,p.t_end_s,p.output_steps+1)
    try:
        sol=solve_ivp(rhs,(0,p.t_end_s),
                (p.initial_position_m,p.initial_velocity_m_per_s,0.),
                method=p.method,rtol=p.rtol,atol=p.atol,
                max_step=p.max_internal_step_s,dense_output=True,
                events=event)
    except (ValueError,OverflowError,RuntimeError,FloatingPointError):
        return PhysicsResult("UNKNOWN_RESOURCE_OR_NUMERICAL_FAILURE",
                             solver_method=p.method,requested_rtol=p.rtol,
                             requested_atol=p.atol,function_evals=count)
    if sol.status<0 or sol.sol is None:
        return PhysicsResult("UNKNOWN_SOLVER_FAILED",solver_method=p.method,
                             requested_rtol=p.rtol,requested_atol=p.atol,
                             function_evals=count)
    actual_end=float(sol.t[-1])
    finite_grid=t_grid[t_grid<=actual_end+1e-12]
    if len(finite_grid)==0 or finite_grid[-1]<actual_end-1e-10:
        finite_grid=np.concatenate((finite_grid,[actual_end]))
    vals=sol.sol(finite_grid)
    if not np.all(np.isfinite(vals)) or np.max(np.abs(vals))>1e12:
        return PhysicsResult("UNKNOWN_NONFINITE",solver_method=p.method,
                             function_evals=count)
    samples=tuple(PhysicsSample(float(t),float(x),float(v),_energy(p,float(x),float(v)))
                 for t,x,v in zip(finite_grid,vals[0],vals[1]))
    e0=_energy(p,p.initial_position_m,p.initial_velocity_m_per_s)
    energy_residuals=[abs(_energy(p,float(x),float(v))-e0-float(w))
                      for x,v,w in zip(vals[0],vals[1],vals[2])]
    max_res=max(energy_residuals)
    # A tolerance-scale *diagnostic*, not a rigorous numerical error bound.
    denom=max(1.,abs(e0))
    drift=max(abs(s.mechanical_energy_j-e0)/denom for s in samples)
    analytical=(max(abs(s.position_m-_analytic(p,s.t_s)) for s in samples)
                if p.kind=="harmonic" else None)
    event_t=(float(sol.t_events[0][0]) if event is not None and sol.t_events[0].size
             else None)
    # If an event boundary exists but wasn't crossed, the configured domain
    # was traversed; that is distinct from a missed-event proof.
    return PhysicsResult(
        "EVENT_STOP" if event_t is not None else "OK",
        samples,p.method,p.rtol,p.atol,count,
        analytical,max_res,drift,event_t,
        actual_end>=p.t_end_s-1e-9,
    )
