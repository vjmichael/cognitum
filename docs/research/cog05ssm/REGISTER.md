# COG-05-SSM — State-space and dynamical systems capability register

Frozen research charter 2026-11-20. 72 capability groups; 29 partial scoped accepted/source/historical or candidate evidence and 43 open. Neither status is comprehensive qualification. Every group requires either new scoped acceptance or a justified explicit deferral; not every named variant must be implemented, but no family silently erased. Literature IDs link to [bibliography](LITERATURE.md). DS01–DS72 do not overlap H1–H60, K1–K60, shared S01–S24 or I-01–I-20.

## COG-05-SSM-01 — Foundations, representation and exact linear dynamics

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS01 | State spaces, time domains and state conventions | PARTIAL: Bounded exact typed deterministic state and clock; coordinate metadata not certified units (R1 scoped native acceptance reconciled) | L03, L06 | Validate dimensions, units, initial/terminal and pre/post-update indexing against scalar closed forms. |
| DS02 | Continuous and discrete LTI, SISO/MIMO | PARTIAL: Coupled discrete MIMO exact and numerical ZOH/FOH; arbitrary interval certification open (R1 scoped native acceptance reconciled) | L03, L42 | Exact rational discrete recurrence; matrix exponential comparison for coupled continuous system. |
| DS03 | Time-varying, affine and bilinear systems | PARTIAL: Exact bounded time-indexed affine and bilinear supplied input sequence; general continuous/nonlinear open (R1 scoped native acceptance reconciled) | L03, L39 | Piecewise time-indexed matrices and known forcing; compare literal noncommutative products. |
| DS04 | Flow composition and semigroup/transition operator | PARTIAL: Exact ordered affine composition and numerical semigroup/hold controls (R1 scoped native acceptance reconciled) | L03, L09 | Check exp((s+t)A), transition composition and singular A cases; exact discrete associativity. |
| DS05 | Discretization and sampling | PARTIAL: Numerical ZOH/FOH, exact rational Euler/Tustin approximation coefficients; alias and stochastic covariance open (R1 scoped native acceptance reconciled) | L02, L03, L42 | ZOH block exponential, first-order hold, Euler/Tustin error and aliasing; irregular timestamps. |
| DS06 | Transfer functions, poles, zeros and impulse responses | PARTIAL: Exact rational resolvent/impulse and canceled-pole examples; general pole/zero analysis open (R1 scoped native acceptance reconciled) | L03, L06 | Rational transfer vs impulse convolution; pole-zero cancellations and feedthrough. |
| DS07 | Coordinate transforms and minimal realization | PARTIAL: Exact rational similarity and finite Hankel minimal zero-initial I/O realization including rank zero; bounds and refusals (R1 scoped native acceptance reconciled) | L03, L06 | Similarity-invariant input/output, Hankel rank, Ho–Kalman reconstruction, nonminimal example. |
| DS08 | Descriptor/DAE and algebraic constraints | PARTIAL: Exact semi-explicit index-1 descriptor reduction and consistent-state constraints; general/higher-index DAE open (R1 scoped native acceptance reconciled) | L03, L09 | Index-1 consistent initial conditions and residuals; refuse singular/unsupported index cases. |

## COG-05-SSM-02 — Qualitative dynamics, numerical analysis and mathematical assurance

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS09 | Eigenstructure, Schur/Jordan and nonnormal dynamics | PARTIAL: Numerical complex Schur residual/orthogonality and sampled nonnormal/defective transient gains; global bounds/Jordan open (native pending) | L03, L04 | Defective and transient-growth examples; Schur residual and norm bounds, not eigenvalues alone. |
| DS10 | Controllability, reachability and stabilizability | PARTIAL: Exact rank, rational-complex PBH, invariant quotient stabilizability and finite discrete unconstrained target witnesses; constrained reach open (native pending) | L03, L06 | Exact small controllability rank, PBH and Gramian checks; unreachable unstable counterexample. |
| DS11 | Observability, detectability and identifiability distinction | PARTIAL: Exact rank, rational-complex PBH, dual quotient detectability and known-input state reconstruction; parameter identifiability open (native pending) | L03, L06, L37 | Exact observability rank/PBH and indistinguishable-state pairs; reject nonidentifiable claims. |
| DS12 | Lyapunov stability and invariant sets | PARTIAL: Exact strict continuous/discrete Lyapunov solve, PD witnesses, replay and autonomous invariance; general marginal classification open (native pending) | L03, L04, L34 | Rational P positive definite and negative residual; unstable and marginal cases; continuous/discrete conventions. |
| DS13 | Riccati equations, Gramians and induced gains | PARTIAL: Exact finite discrete/infinite stable Gramians and H2 squared; numerical CARE/DARE with exact feedback stability; exact supplied-storage H-infinity upper and rational-frequency lower witnesses; synthesis and global search open (R1 local pass; native pending) | L03, L04 | Check CARE/DARE and Lyapunov residuals, stabilizing root and H2/H-infinity scope. |
| DS14 | Nonlinear equilibria, linearization and bifurcations | PARTIAL: Bounded rational polynomial equilibrium/Jacobian checks, strict local Lyapunov linearization and canonical saddle-node/Hopf classification; enumeration/continuation open (R1 local pass; native pending) | L03, L10 | Analytic saddle-node/Hopf examples, Jacobian prediction vs nonlinear trajectories; local vs global. |
| DS15 | Contraction, passivity and dissipativity | PARTIAL: Exact linear quadratic contraction, general quadratic supply/passivity verification, polynomial invariant-box infinity-norm contraction; storage synthesis open (R1 local pass; native pending) | L04, L14, L15 | Storage inequality, contraction metric on stated region, counterexample outside region. |
| DS16 | Validated integration, interval/reachability and barrier certificates | PARTIAL: Discrete box overapproximation, exact polynomial invariant faces/map inclusion and strict continuous tube/endpoint enclosure; general barriers/adaptive verified flow open (R1 local pass; native pending) | L04, L34, L35 | Outward-rounded or exact certificate checker; reject sample-only proof; enclose small known trajectories. |

## COG-05-SSM-03 — Simulation, physical structure and infinite-dimensional dynamics

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS17 | ODE integration, stiffness and event localization | OPEN | L03, L09, L28 | Analytic solution and independent solver refinement; stiff test; event-time bracket. |
| DS18 | Hamiltonian, Lagrangian and symplectic methods | OPEN | L09, L14 | Harmonic oscillator and nonlinear pendulum; symplectic condition, bounded energy drift not exact conservation by default. |
| DS19 | Port-Hamiltonian and dissipative networks | OPEN | L15, L13 | Skew J, PSD R, power balance; RLC and damped oscillator. |
| DS20 | Constrained, switching and hybrid automata | OPEN | L34, L35, L39 | Guard/reset paths, mode-specific invariants; no Zeno or missed event claims without bounds. |
| DS21 | Delay, distributed and hereditary systems | OPEN | L03, L04 | Known delay differential fixture and mesh convergence; explicitly account history and memory. |
| DS22 | PDE evolution, semigroups and spatial discretization | OPEN | L12, L13, L32 | Use existing KAN exact weak forms; diffusion/wave modal closed forms and mass-matrix time evolution. |
| DS23 | Model reduction and balanced truncation/POD | OPEN | L06, L12, L40 | Stable minimal LTI bound where valid; POD reconstruction and out-of-sample trajectory error. |
| DS24 | Multiscale, coupled, graph and network dynamics | OPEN | L39, L40 | Graph Laplacian diffusion and coupled oscillators; conservation and partition equivalence. |

## COG-05-SSM-04 — Stochastic dynamics and Bayesian inference

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS25 | Markov processes, transition kernels and generators | OPEN | L05, L08 | Probability mass, stochasticity, matrix-exponential CTMC and finite enumeration. |
| DS26 | Itô SDEs, diffusion and Fokker–Planck | OPEN | L02, L05, L31 | Ornstein–Uhlenbeck moments, seeded path weak/strong convergence; no unqualified SDE precision. |
| DS27 | Linear Gaussian Kalman and Kalman–Bucy | PARTIAL: Decimal scalar and independent local-level/velocity channels | L01, L02, L05 | Coupled full covariance, known Gaussian conditioning, irregular sampling and missing data; noise assumptions explicit. |
| DS28 | Square-root, information and numerically robust filters | PARTIAL: Existing Joseph update not full square-root/information | L05, L07 | Ill-conditioned covariance, Cholesky/QR parity and PSD; compare Joseph form; reject invalid covariance. |
| DS29 | Smoothing and posterior path sampling | OPEN | L05, L07 | Rauch–Tung–Striebel vs joint batch Gaussian and fixed-lag vs full smoothing; separate future access. |
| DS30 | EKF, UKF and cubature filters | OPEN | L05 | Linear-limit parity and nonlinear known-reference Monte Carlo; NEES/NIS diagnostics under assumptions. |
| DS31 | Particle/ensemble filtering and resampling | OPEN | L05, L08 | Exact small posterior and convergence across seeds, degeneracy, ESS, resampling parity; no single-seed guarantee. |
| DS32 | HMM, switching LDS and regime inference | PARTIAL: Categorical HMM forward filter with declared matrices only | L05, L39, L41 | Finite exact enumeration/forward-backward; label permutation, Viterbi, impossible emission, regime changes. |

## COG-05-SSM-05 — Statistical inference, identification and mathematical discovery

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS33 | Likelihood, EM and Bayesian parameter estimation | OPEN | L05, L08, L44 | Known parameters, batch likelihood and EM monotonicity when applicable; parameter uncertainty. |
| DS34 | System identification and persistent excitation | OPEN | L03, L06, L37, L39 | Fit unknown LTI with held-out controls; rank deficiency prevents unique claim; similarity ambiguity. |
| DS35 | Subspace methods, realization from data and ERA | OPEN | L06, L37 | Noise-free impulse recovery; noisy order selection and uncertainty; compare Ho–Kalman. |
| DS36 | Sparse discovery, symbolic dynamics and SINDy | OPEN | L10, L39 | Recover bounded polynomial equations; derivative noise, collinearity, wrong library controls; KAN cross-check. |
| DS37 | DMD, extended DMD and Koopman approximation | OPEN | L11, L39 | Known spectral modes, residual/error, non-invariant dictionary warning; no finite exact Koopman universal claim. |
| DS38 | Operator inference and structure-preserving identification | OPEN | L12, L13, L14, L15, L33 | Learn linear/quadratic operators, independent known matrices, exact-recovery assumptions, unseen excitation/noise. |
| DS39 | Statistical time series, trend, seasonal and dynamic factor | PARTIAL: Ridge autoregression and simple forecast evaluation | L05, L44 | ARIMA/SARIMAX, unobserved components, factor models, rolling chronological evaluation vs persistence/seasonal naive. |
| DS40 | Change detection, robust likelihood, missing/OOD | PARTIAL: Innovation thresholds and HMM mode alerts; not calibrated | L05, L07, L41 | Known shifts, outliers and outages; false alarms, detection delay, coverage/abstention across seeds. |

## COG-05-SSM-06 — Optimization, feedback and decision mathematics

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS41 | Luenberger and unknown-input observers | OPEN | L03, L04 | Error-dynamics and observer pole placement; unknown-input identifiability refusal. |
| DS42 | State feedback, pole placement and LQR | OPEN | L03, L04 | Independently verify closed-loop pole placement, Riccati solution and cost against finite-horizon dynamic programming. |
| DS43 | LQG, Kalman-controller separation and duality | OPEN | L01, L03, L05 | Joint filter/controller benchmark under exact assumptions; no separation claim for generic nonlinear systems. |
| DS44 | Model predictive control and constrained planning | OPEN | L03, L04, L16 | Finite-horizon convex control, feasible constraints and KKT residual; C11/C12 adapter; infeasible refusal. |
| DS45 | Robust, stochastic and chance-constrained control | OPEN | L04, L16 | Bounded uncertainty and explicit risk; independent reachability or independent sample coverage as distinct evidence. |
| DS46 | Adaptive, robust and data-enabled predictive control | OPEN | L16, L37, L39 | Persistently exciting vs deficient datasets; compare model-first MPC and closed-loop simulation; no guarantees beyond conditions. |
| DS47 | Optimal experiment design and sensor placement | OPEN | L03, L05, L37 | Finite candidate enumeration and observability/Fisher information; distinguish local identifiability. |
| DS48 | Safety filters, reach-avoid and certified controllers | OPEN | L04, L34, L35 | Certificate verification separate from synthesis, unsafe initial state and infeasible commands; simulation only. |

## COG-05-SSM-07 — Structured and selective learned state spaces

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS49 | HiPPO and online orthogonal projection | OPEN | L17 | Analytic polynomial moments, streaming history approximation and explicit truncation/reconstruction error. |
| DS50 | LTI learned recurrence, convolution, complex/dense/low-rank | PARTIAL: Historical P23 training report; original checkpoint custody missing | L18, L19 | Impulse kernel vs recurrence incl initial state, gradient check, trained synthetic identification. |
| DS51 | S4 and structured DPLR/NPLR | OPEN | L18 | Reference convolution, direct recurrence and initialization parity; train genuine small CPU trials. |
| DS52 | DSS/S4D, complex diagonal and LRU candidates | OPEN | L19, L38 | Complex conjugacy, stable parameterization and long-memory stress; compare simple AR and GRU. |
| DS53 | S5 MIMO and associative scan | OPEN | L20 | Serial, associative and chunked recurrence equality; irregular-step policy and finite-precision differentiation. |
| DS54 | Mamba-1 selective update and causal convolution | OPEN: Historical gated P23b is not Mamba | L21 | Actual input-dependent delta/B/C, correct discretization, serial vs scan output/gradient and causal mask tests. |
| DS55 | Mamba-2/SSD and semiseparable kernels | OPEN | L22 | Structured matrix product vs recurrent step and block scan, shape/order/initial-state parity; no GPU performance extrapolation. |
| DS56 | Mamba-3 and generalized recurrence variants | OPEN | L23, L24, L25, L26, L27 | Complex/rotation and MIMO, discretization comparison; adjacent DeltaNet/Householder controls, permutation/recall negative cases. |

## COG-05-SSM-08 — Learned continuous dynamics, scientific operators and frontier models

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS57 | Neural/latent ODE and differentiable simulation | OPEN | L28, L29 | Analytic short trajectories, finite-difference gradient vs adjoint, solver sensitivity and held-out initial states. |
| DS58 | Neural CDE, path signatures and irregular observations | OPEN | L30, L31 | Causal interpolants; perturb future inputs, step refinement and irregular/censored data. |
| DS59 | Neural SDEs and probabilistic latent dynamics | OPEN | L31, L05 | Known diffusion moments, posterior predictive tests, variance calibration vs classical SDE. |
| DS60 | Physics-informed, Hamiltonian and dissipative learning | OPEN | L13, L14, L15, L32 | Conservation and dissipation contract; compare black-box learner, KAN vector field and standard simulator. |
| DS61 | Deep Kalman, variational, differentiable particle filters | OPEN | L05, L08, L36 | Likelihood/ELBO sanity and independent posterior reference; importance weight degeneracy and failure modes. |
| DS62 | State-space neural operators and spatiotemporal science | OPEN | L32, L40 | Held-out forcing, boundary and resolution; compare exact KAN forms and conventional PDE integrator; mesh transfer limits. |
| DS63 | Probabilistic regime-conditioned SSM forecasting | OPEN | L41, L44 | Time-split multiple datasets, proper scoring/coverage, regime ablation, leakage and distribution shift. |
| DS64 | Expressivity, formal languages, recall and hybrid architectures | OPEN | L24, L25, L26, L27, L38 | Exact automata and permutation composition, associative recall, long-horizon degradation, attention/GRU/linear recurrence controls. |

## COG-05-SSM-09 — Interoperability, research experiments and delivery assurance

| ID | Mathematical capability | Present coverage | References | Minimum independent acceptance |
|---|---|---|---|---|
| DS65 | Typed state, belief, trajectories, model and control objects | PARTIAL: C17 Protobuf and explicit diagonal state; no common general profile | L03, L05 | Versioned units, shapes/time semantics, provenance, numerical class and bounded canonical encoding; existing registry. |
| DS66 | Resumable streaming, batching, state reset and chunk semantics | PARTIAL: Bounded diagonal 64-step streaming and tests | L17, L18, L21 | Every partition and reset equals full recurrence under tolerance; stale/wrong model state refused; causal prefix invariance. |
| DS67 | HDC interoperability: regime features and associative retrieval | PARTIAL: Historical P23c/d sidecar reports, source/receipt custody not requalified | L05, L24, L41 | Match state IDs and timestamps against canonical records; HDC candidates not facts; compare exact search. |
| DS68 | KAN interoperability: nonlinear dynamics/observation functions | OPEN | L10, L13, L32 | Pure KAN f/g or field operator, derivatives/Jacobians, numerical integration comparison; propagate model uncertainty. |
| DS69 | Exact and approximate evidence, uncertainty and calibration | PARTIAL: Existing scoped C17 assumptions and OOD flags | L04, L05, L25, L34 | Separate exact algebra, floating residual, empirical calibration and certificate assumptions; coverage and falsification. |
| DS70 | Scientific datasets and non-AI application validation | PARTIAL: Existing CSV adapter; historical synthetic comparisons only verified by report here | L37, L39, L40, L44 | Known simulators plus licensed real traces with frozen splits and unit/reference provenance; independent domain controls. |
| DS71 | CPU, memory, long streams and bounded resource execution | PARTIAL: Bounded reference; no new comprehensive SSM resource study | L18, L21, L22, L23 | Matched CPU-first cold/warm/streaming and memory, retain failure/energy caveats; no new native C++ benchmark requirement. |
| DS72 | Independent acceptance, safe composition and deployment gates | PARTIAL: Existing default-off research route and native baseline | L04, L05, L34, L35 | Cross-platform pinned source, refusal tests, proof replay where possible, isolated workers, no control authority or production promotion. |
