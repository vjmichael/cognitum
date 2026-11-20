# Cognitum — Comprehensive architecture, Revision 1.6
**Effective:** 2026-11-20. **Status:** normative design amendment; implemented/accepted scope remains strictly evidence-bound.

This revision updates the [R1.5 comprehensive design](Cognitum_Comprehensive_AI_Architecture_R1_5.md), [19-component technology portfolio](design/technology-portfolio-C01-C19.md), and [MEL 0.1 architecture](research/mel/ARCHITECTURE.md). Read these together: R1.6 governs where it explicitly extends earlier scope; otherwise all earlier host, security, privacy, evidence, component and release requirements remain binding. Historical documents are preserved as source evidence, especially the exact-hash-pinned HDC/KAN [master register](research/mel/MASTER_REGISTER.md). This is a design revision, not a new production release or claim of comprehensive implementation.

## 1. Mission and independent mathematical engines

Cognitum remains one heterogeneous cognitive augmentation system, scientifically useful independently of a transformer and eventually an optional Lu Core Extension. It shall provide three first-class, independently useful mathematical engines within the same package and Mathematical Execution Layer (MEL), with mature conventional numerical, symbolic, statistical and formal specialists retained. No engine is required to subsume the others or outperform conventional methods universally.

| Engine | Standing design scope | Register |
|---|---|---|
| HDC | Representational algebra, associative operations, high-dimensional geometry, vector-symbolic and functional computation, learning | H1–H60 and 85 historical research entries |
| KAN | Function representations, approximation, functional calculus, symbolic learning, scientific operators, differential and spectral problems | K1–K60 |
| SSM | General dynamical-system mathematics: deterministic and stochastic time evolution, estimation, identification, scientific simulation, control and learning | DS01–DS72 |

The historical shared instruments S01–S24 and I-01–I-20 interoperability register remain intact. Core register groups total 236 (60+60+72+24+20), not completed implementations; the proposed six SSM cooperation contracts are an additional cross-reference, not six accepted groups. See [SSM charter](research/cog05ssm/CHARTER.md), [capability register](research/cog05ssm/REGISTER.md), and [literature map](research/cog05ssm/LITERATURE.md). The scientific research program covers classical and frontier theory, not solely neural networks.

## 2. SSM mathematical design

Use declared state, input and observation spaces; real/complex and discrete/continuous profiles, units, coordinates, clock, initial conditions, coefficient/checkpoint provenance, assumptions and resource budgets. Discrete pre-update convention: x[k+1]=A[k]x[k]+B[k]u[k]+g[k], y[k]=C[k]x[k]+D[k]u[k]. Continuous model: dx/dt=f(t,x,u), y=g(t,x,u); stochastic profiles specify transition and observation distributions and stochastic calculus convention where relevant. Descriptor profiles specify E dx/dt=Ax+Bu, algebraic constraints and consistency. Legacy diagonal specialist reads from updated state; preserve its interface, with explicit C'=CA, D'=CB+D conversion for equivalent pre-update observation. No silent conversion of physical units, clocks, coordinate spaces or state convention.

| Scientific division | Design requirement |
|---|---|
| DS01–08 | State representations, exact coupled linear algebra, affine/time-varying/bilinear, transition operators, sampling, transfers, similarity/minimal realization, descriptors |
| DS09–16 | Qualitative systems analysis: spectrum, controllability/observability, Lyapunov and Riccati, Gramians, contraction, passivity, certificates |
| DS17–24 | Scientific dynamics, ODE/PDE, Hamiltonian structure, DAE/hybrid, delay and multiscale, model reduction |
| DS25–32 | Markov and stochastic dynamics, coupled covariance, Bayesian filtering, smoothing, nonlinear and particle methods, regime inference |
| DS33–40 | Identification, likelihood/EM, subspace, SINDy, DMD/Koopman, operator inference, time series, robust/change detection |
| DS41–48 | Optimal control and decision mathematics, observers, LQR/LQG, MPC, uncertainty, experiment design and simulation-only safety constraints |
| DS49–56 | HiPPO, structured LTI, S4/DSS/S4D/S5, Mamba-1/2/3, generalized recurrent families |
| DS57–64 | Neural ODE/CDE/SDE, latent dynamics, physical constraints, neural operators, probabilistic regime forecasting, expressivity and counterexamples |
| DS65–72 | Typed mathematical objects, streaming, cooperative execution, independent assurance, dataset and resource qualification |

Use exact rational arithmetic where algebra permits; label numerical matrix exponentials, integrators, approximations, residual checks and empirical estimates honestly. Rigorous certificates must have explicit hypotheses and independently verifiable witnesses; numerical cross-checks are not formal error enclosures. Minimal realization preserves zero-initial-state input/output map, not arbitrary latent initial conditions. Separate descriptor index, algebraic constraints and nonsingular dynamic blocks. Distinguish stability, marginal behavior, nonnormal transient growth, observability and identifiability; do not infer safety or causal truth from predictive performance.

## 3. Unified MEL and cooperation
Retain existing registry, reviewed descriptors, typed objects, admission/policy, supervised workers, cancellation, recovery, evidence, resource accounting and one runtime (not a competing SSM runtime or canonical state store). Internal operations use declarative models and typed contracts. Proposed ModelSpec, Observation, Control, StateBelief, Transition, Trajectory, Forecast and Certificate objects bind dimensions, units, time, model/version, input digest, uncertainty kind, exact/numerical/empirical assurance, method/solver version, limits and source. New research operations remain inert until independently qualified and explicitly admitted; host-facing interfaces remain native typed Protobuf where required by existing architecture. No arbitrary model-supplied executable code.

| Proposed cross-engine contract | Purpose |
|---|---|
| XSS-01 | HDC features and candidate regimes, verified against canonical sources |
| XSS-02 | KAN-learned vector fields and observation functions, including derivative/uncertainty handoff |
| XSS-03 | KAN weak-form mass/stiffness operators feeding time evolution, independent analytic/refinement controls |
| XSS-04 | Typed estimates and uncertainty exchange with conventional probability/statistical engines |
| XSS-05 | Simulation-only mathematical control proposals to existing planner/optimizer; no external execution authority |
| XSS-06 | Matched single-engine, conventional and cooperative evaluation |

SSM compressed state is not verified memory, candidate retrieval not fact, and a predicted state not a measured observation. Lu/ANSF remains authoritative for canonical data, consent, policy and effects. Model-facing exposure stays default-off for research; development in Cognitum confers no Lu authority. C17 retains its established temporal routes; general SSM research extends, not replaces, C17. Reuse C05/C10/C11/C12/C13/C14/C15/C16/C17 where capabilities overlap.

## 4. Scientific research and delivery policy
Scientific applications are first-class: mechanics/vibrations, circuits and battery equivalent-circuit dynamics, chemistry, population systems, signal processing, thermal/wave/fluid PDE, robotics simulation, economics and digital twins. Domain-specific physical claims require independent analytical/reference controls, known units/data provenance and scoped validation. Financial/medical/robotic examples confer no operative control. Research advances by staged literature, actual implementation, independent mathematical and adversarial tests, matched chronological/held-out evaluation, reproducible source/runtime and cross-platform receipts. Preserve negative results. CPU-first; maintained libraries for established solvers, exact independent references where helpful. C++ exact assembly optimization remains optional future research, not a release prerequisite. ARM/FPGA/accelerator measurements are deferred separate gates. No neural weight modification is a prerequisite for transformer tool augmentation.

## 5. Current evidence snapshot (not normative claims)
Source candidate `538cae8ba57bbb0e2854706e9d5fdb1ee9eafe50`. COG-04A–U and COG-05A–C have scoped prior acceptance; broader H/K groups remain open. COG-05-SSM-00 charter records 72 groups and 44 literature anchors. SSM-01/R1 new bounded research source includes exact coupled rational rollout, affine composition, impulse/transfer, similarity, finite Hankel minimum realization, supplied bilinear sequence, rational Euler/Tustin approximations, numerical ZOH/FOH, semi-explicit index-1 descriptor elimination and consistent initial conditions. Local dedicated 38/38; native batch **pending** at this design snapshot. The earlier batch failed a historical documentation identity gate (SSM tests skipped), eight integration jobs passed; original register restored and 1,650 historical pin occurrences independently reconciled. Current candidate regression [44786308159](https://github.com/vjmichael/cognitum/actions/runs/44786308159) and integration [44786308289](https://github.com/vjmichael/cognitum/actions/runs/44786308289). See [SSM01](research/cog05ssm/SSM01.md) and [R1](research/cog05ssm/SSM01_R1.md). General symbolic pole/zero theory, higher-index descriptors, sampling/alias analysis, stochastic covariance, general nonlinear dynamics and rigorous continuous enclosures remain open. Previously accepted kernels retain their evidence, not automatic new-SHA acceptance.

## 6. Execution and acceptance sequence
The [single current master task ledger](MASTER_TASK_LEDGER.md) controls scheduling. SSM-00 complete as initial charter; SSM-01-R1 native closeout pending. SSM-02 next independent mathematics: controllability/observability, reachability, stability and Lyapunov, Gramians/Riccati. SSM-03–09 follow the nine research divisions above with residual work and dependencies explicit. Research-only scopes, final architecture/library and repository consolidation, matched real-model efficacy testing and separately approved installed Lu acceptance are retained. No release promotion because of design or local tests alone.

## 7. Document ownership and preservation
R1.5, historical MEL architecture, HDC/KAN master register and historical source-pinned manifests are preserved. This version is the authoritative current extension, not a rewrite of historical evidence. Use the living design index and master ledger for the current revision. Future substantive decisions must update this design or a versioned successor plus the master ledger; do not edit files pinned to an accepted historical manifest. A documentation-only commit is not a new native test SHA. 

## 8. SSM-01 acceptance and SSM-02 implementation update (November 20)
The earlier evidence snapshot is superseded for these tasks. [SSM-01-R1 native closeout](research/cog05ssm/SSM01_CLOSEOUT.md) accepted scoped on four platforms, twelve jobs, 152 dedicated and 460 inherited tests; all evidence archived and reconciled. SSM-02 [candidate report](research/cog05ssm/SSM02.md) implements exact finite linear reachability/observability, quotient analysis, strict Lyapunov/certificates, contraction, Gramians, H2 squared, and discrete reachable-box overapproximation; Schur/transient diagnostics and CARE/DARE numerical, with exact strict stability witness for returned feedback coefficients. No controller execution or formal optimality claim. Local 78/78 combined tests; candidate acceptance pending. DS14, passivity/dissipativity, H-infinity, general nonlinear dynamics and rigorous continuous verification remain planned. [Master ledger](MASTER_TASK_LEDGER.md) controls the SSM-02-R1 closeout and subsequent tasks.

## 9. SSM-02-R1 nonlinear and bounded verification design update (November 20)
[R1 candidate](research/cog05ssm/SSM02_R1.md) extends DS13–16 with exact quadratic storage/supply verification (continuous/discrete), passivity, H-infinity interval bracketing (supplied storage upper, rational frequency/direction lower), bounded polynomial vector fields/maps, equilibrium/analytic Jacobian and strict local linearization stability, canonical saddle-node/Hopf and exact invariant-box/contraction/flow-tube enclosure. These certificates are mathematical for specified exact models only; neither failed sufficient witness nor sampled simulation proves general impossibility or physical safety. General synthesis, global frequency maximization, nonlinear continuation, adaptive verified integration and arbitrary barrier programs remain open. Combined local 111/111, native pending. Original SSM-02 predecessor batch continues; R1 staged without overlapping CI. Ledger governs sequential native closure and SSM-03 next independent development.
