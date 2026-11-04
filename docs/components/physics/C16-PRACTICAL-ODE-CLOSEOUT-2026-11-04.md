# C16 — Physical modeling and numerical integration: practical implementation

**Date:** 2026-11-04. **Status:** code on separate branch, native SciPy/Protobuf acceptance pending; no Lu installation or real-world physical validation.

## Requirements alignment with C16 P0–P3

**P0 typed physical model.** `cognitum/physics_ode.py` defines an immutable physical request with explicit SI metres/seconds/kilograms/newtons, dimensioned mass, spring stiffness, damping, applied force, gravity, initial position/velocity, duration, sample resolution, solver method, relative/absolute tolerances, resource cap, optional downward-crossing boundary event, and declared validation domain. User-authored Python or arbitrary equation text is never interpreted.

**P1 mature conventional integrators.** Calls actual SciPy `solve_ivp` with `RK45`, `DOP853`, `Radau`, or `BDF`, using real solver tolerances and a bounded maximum internal step. Scopes four deterministic 1-D templates:
- `harmonic`: undamped unforced spring (analytic comparison available).
- `damped`: viscous damper and spring (zero external constant force).
- `forced`: constant-force damped/spring dynamics.
- `falling_drag`: linear velocity drag and gravity, explicitly upward-positive coordinates.

A standard analytic constant-acceleration motion capability already exists separately in `cognitum/physics_motion.py` with exact reduced rational Protobuf and energy-work identity checks. It is retained as an independent reference, **not replaced**.

**P2 adversarial and failure behavior.** The new adapter rejects mixed/unknown units, NaN/Inf parameters, unphysical negative masses, inconsistent equation family, unbounded durations/step sizes, unsafe tolerances, invalid boundary conditions and unrecognized integration method. Right-hand-side evaluation is bounded and refuses nonfinite/overflow states. `EVENT_STOP`, `UNKNOWN_RESOURCE_OR_NUMERICAL_FAILURE`, `UNKNOWN_SOLVER_FAILED`, `UNKNOWN_NONFINITE`, `UNSUPPORTED` remain distinct. Source authorization, real OS cancellation and process containment are separate Lu host gates and are **not** invented as in-process SciPy guarantees.

Each numerical trajectory reports requested tolerances, solver evaluations and bounded samples. A separately integrated work/dissipation channel supports the exact ideal-model balance diagnostic
`E(t)-E(0) = integral(force * velocity - damping * velocity**2) dt`.
Undamped harmonic cases also report maximum position error versus a closed-form solution; energy drift, balance residual and event time are visible. These are diagnostics, **not rigorous error enclosures**, causal validation, empirical model uncertainty or physical sensor calibration.

**P3 genuine reference comparisons.** `tools/c16_physics_benchmark.py` exercises all four real SciPy solver methods, forced and damped energy balances, downward boundary event, and bounded RHS-evaluation failure. It emits measured process CPU and wall time, actual RHS counts, convergence/analytic error, energy balance and event evidence as JSON. This is component numerical acceptance, not Lu model A/B efficacy, GPU research or neural-ODE surrogate training.

## Distribution, typed wire and acceptance

- `proto/cognitum/physics/v1/ode.proto`, `cognitum/proto/physics_ode_pb2.py`, and `cognitum/physics_ode_wire.py` define bounded canonical Protobuf, strict request input validation, SHA-256 correlation (not user authentication), typed output and numerical reexecution for tamper/reflection checks.
- `tests/test_c16_ode.py` and `tests/test_c16_ode_wire.py` cover genuine SciPy explicit/implicit integration, analytic references, forced/damped balance, terminal event, resource exhaustion, invalid/mixed units, arbitrary equation attempt, forged numeric result and malformed Protobuf.
- `pyproject.toml` provides optional `physics-ode` extras containing NumPy/SciPy/Protobuf only; Cognitum core remains free of solver dependency.
- `.github/workflows/c16-ode.yml` tests Windows/Linux × CPython 3.11/3.13 actual solver imports, true analytic/problem tests, real benchmark, and independently compiled native Protobuf schema descriptor parity.

**Closure gate:** Must pass current-head real CI before merge. Complete numerical solver *component* scope is bounded to these conventional templates; no arbitrary PDEs, multiphysics engine, dynamic contact mesh, high-frequency CFD, stiff failure certification, hard realtime guarantees, KAN/Neural ODE training, hardware FPGA, GPU, experimental model validity or general boundary-condition language is claimed.

The original C16 design intentionally makes learned Neural ODE/KAN challengers optional, not a requirement to develop a novel solver. Actual Lu host authorization, per-turn tool grants, OS-isolated worker cancellation and independent real-task A/B analysis remain subsequent integration acceptance tasks.
