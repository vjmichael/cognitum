# C16 P0/P1 — Typed constant-acceleration reference (first Cognitum build)

**Status:** First bounded offline implementation and unit tests passed locally. Not C16 complete; not installed/advertised in Lu; no solver/sandbox approval.

**Augmentation goal:** Let a transformer request a dimensional, independently checkable calculation of a one-dimensional motion trajectory instead of guessing its arithmetic and losing physical units. A strong conventional analytic formula is the **intended implementation**, not an algorithm Cognitum must beat.

## Bounded capability

- Native `cognitum.physics.v1.LinearMotionRequest/LinearMotionResult` Protobuf; explicit `SI:m,s,kg`, reduced rational values, initial position/velocity, constant acceleration, positive mass, positive timestep and 1–256 steps / at most 1000 seconds.
- Exact equations: `x(t)=x0+v0*t+(a*t*t)/2`; `v(t)=v0+a*t`; kinetic energy `K=m*v*v/2` and signed work by force `W=m*a*(x-x0)`. Enforce `K(t)-K(0)=W(t)` for each trajectory sample.
- Bound input magnitude, denominator, raw-frame and result-frame lengths and rational bit growth. Reject noncanonical ratios, missing fields, unknown/duplicated fields, mixed unit strings and tampered results.
- Calculate `request_sha256` over exact canonical Protobuf bytes. An independent `verify` function recomputes and compares the entire deterministic result.
- No natural-language intent validation; no friction, collisions, nonconstant force, relativistic effects, coordinate transforms, integrated differential equations, stochastic uncertainty, experiment calibration or guarantee of real-world physics.

The response's `physical_model_validated` and `host_approved` remain **false**. Correct analytic arithmetic does not certify source measurements or operator safety. No file, network, model, host permission or Lu state access.

## Verified tests

Local October 29 test: **20 tests passed; 13 subtests passed**, including energy-work cross-checks, positive/negative and fractional motion, overflow limits, malformed Protobuf, unknown/duplicate fields, tampering, altered input binding and forged approval flags. Independently compiled descriptor check: **83/83 schemas match**. These counts are local and do not establish GitHub/Windows acceptance until CI finishes.

## Completion roadmap beyond first slice

1. Standard scientific ODE engine with bounded tolerances and stiffness detection, unit-safe state models and convergence diagnostics.
2. Event/collision/boundary handling and conservation drift measurements; cancellation and resource budgets under real trusted host worker.
3. Explicit uncertainty and out-of-distribution warnings; validation against held-out analytical/reference problems and physical data where available.
4. Optional learned dynamics/Neural ODE surrogates only when their transformer-task value is demonstrated, without a universal requirement to beat traditional solvers.
5. Actual Lu-approved native CE round-trip, capability discovery and failure mapping, where Lu remains authority owner.

**Alpha boundary:** A developer alpha may include this as a disabled/offline demonstration or omit it entirely. Completing this C16 slice does not delay the alpha core, nor does it finish C16.
