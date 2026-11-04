"""C16 fixed-case real SciPy reference benchmark, not fabricated evidence.

Reports measured solver effort, error vs closed-form harmonic reference,
energy-balance diagnostic and resource/cancellation boundaries. No actual
host cancellation, GPU, neural surrogate or experimental physical calibration.
"""
import json
from dataclasses import replace
from math import pi
from time import perf_counter,process_time
from cognitum.physics_ode import PhysicalModel,integrate


def base():
    return PhysicalModel(
        "harmonic","SI:m,s,kg,N",2,8,0,0,0,1,0,pi,64,1e-9,1e-11,
        "RK45",.02,
    )


def cases():
    ref=base()
    return (
        ("harmonic_RK45",ref),
        ("harmonic_DOP853",replace(ref,method="DOP853")),
        ("harmonic_Radau",replace(ref,method="Radau")),
        ("harmonic_BDF",replace(ref,method="BDF")),
        ("damped",replace(ref,kind="damped",damping_n_s_per_m=.3)),
        ("forced",replace(ref,kind="forced",damping_n_s_per_m=.3,force_n=1)),
        ("falling_event",replace(ref,kind="falling_drag",spring_n_per_m=0,
                                 damping_n_s_per_m=.5,gravity_m_per_s2=9.81,
                                 initial_position_m=10,t_end_s=5,
                                 stop_at_position_m=0.)),
        ("resource_exhaustion",replace(ref,max_function_evals=50,
                                       max_internal_step_s=.001)),
    )


def main():
    results=[]
    for name,problem in cases():
        wall=perf_counter()
        cpu=process_time()
        out=integrate(problem)
        elapsed_wall=round(1000*(perf_counter()-wall),3)
        elapsed_cpu=round(1000*(process_time()-cpu),3)
        expected="UNKNOWN_RESOURCE_OR_NUMERICAL_FAILURE" if name=="resource_exhaustion" else (
            "EVENT_STOP" if name=="falling_event" else "OK")
        if out.status!=expected:
            raise RuntimeError(name+" status mismatch "+out.status)
        if out.status in ("OK","EVENT_STOP"):
            if (out.max_balance_residual_j is None
                    or out.max_balance_residual_j>0.02
                    or len(out.samples)>257):
                raise RuntimeError(name+" invalid physical invariant diagnostics")
            if name.startswith("harmonic") and (out.convergence_max_error_m is None
                                                  or out.convergence_max_error_m>2e-5):
                raise RuntimeError(name+" violates analytic reference")
        results.append({
            "case":name,"status":out.status,"method":out.solver_method,
            "evaluations":out.function_evals,"trajectory_samples":len(out.samples),
            "analytic_max_error_m":out.convergence_max_error_m,
            "max_energy_balance_residual_j":out.max_balance_residual_j,
            "invariant_drift_relative":out.max_invariant_relative_drift,
            "event_time_s":out.event_time_s,
            "wall_ms":elapsed_wall,"cpu_ms":elapsed_cpu,
        })
    print(json.dumps({
        "schema_version":1,"benchmark":"C16_actual_SciPy_ODE",
        "cases":results,
        "limitations":[
            "idealized_dimensioned_models_not_real_world_verified",
            "single_run_per_solver_no_statistical_error_bound",
            "rtol_atol_are_solver_controls_not_experiment_uncertainty",
            "no_Lu_host_OS_worker_cancellation",
            "no_learned_Neural_ODE_KAN_challenger",
            "no_GPU_or_energy_consumption_metrics",
        ]},indent=2,sort_keys=True))


if __name__=="__main__":
    main()
