# COG-04K — adaptive transient tensor KAN learning

Research-only local qualification on top of the unpublished I/J overlay of `a9bc9fc81f2cddebfc66fd0ffc169866e395dcde`. No publication, existing workflow disruption, production promotion or MEL worker authorization.

## Mathematical contract

Scalar linear parabolic u_t - a u_xx + c u = f(x,t), 1/16 <= a <= 100, 0 <= c <= 100, normalized unit spatial interval and unit time interval. Homogeneous Dirichlet spatial boundaries and polynomial initial condition g(x), degree <= 4, with both endpoints exactly zero. The represented solution is g(x)+s(x,t), where s is a tensor product of clamped cubic B-spline basis edges, trained coefficient weights and at most six interior dyadic knots total. Two axes mean one spatial coordinate and one time coordinate, NOT two spatial coordinates plus time. No arbitrary geometry, nonlinear or coupled equations, unbounded horizon, unstable reaction, wave equation or general PDE claim.

Least-squares PDE residual fitting uses SciPy spline basis and Gauss-Legendre quadrature, not labels or analytical reference values. Hard conditions fix the first time column and both outer spatial rows to zero. Refine by ranking exact cell residual bounds and testing bounded midpoint strip splits; a symmetric pair of spatial splits is also considered within the knot budget. Select only strict improvement in the verified global bound. Stop without success when the target is unmet; no silent relaxation. Uniform-grid comparison fixes the same counts on both axes and fits with identical objective.

Independent verifier uses J's exact rational local Cox-de Boor polynomials, not the numerical fit or its collocation residuals. Reconstruct all cell coefficients including the initial lift from the admitted problem; check initial trace, both spatial traces and C2 interface identities exactly. Compute residual polynomial, Bernstein convex-hull sup bound R_cell and exact integrated squared residual. All binary64 inputs are interpreted as exact rationals. For a time slab, R_j = max over spatial cells of R_cell. The comparison principle yields prefix bounds via the nonnegative barriers integral_0^t R(s) ds, R_peak*x(1-x)/(2a), and (if c>0) R_peak/c. Each barrier dominates the absolute error for continuous Dirichlet/initial data; integration is piecewise in time with no jump and inequality on each slab. Use the minimum of the integrated slab-prefix bound, R_peak/(8a), and R_peak/c if applicable. Global certificate is the maximum slab bound. Homogeneous error initial and boundary conditions are essential; otherwise no error bound is issued. Reference identity and model checkpoint digest bind replay; this is a mathematical bound on the represented solution, not an OS-signed attestation or general learned function accuracy.

## Local evidence

61 passed, zero fail/error/skip on Linux Python 3.13 with NumPy 2.3.5 / SciPy 1.17.0. Four benchmark problems, each checked on 4,623 shifted independent points including initial/final time and spatial endpoints; analytic polynomial or independently evaluated sine series, with a truncation bound (floating evaluation diagnostic only). Tolerances are engineering targets chosen following exploratory fits, not blind holdouts. Exact interval certificates do not rely on sampled reference error. The manufactured case also has an exact rational zero-residual fixture. Additional tests reject zero residual with wrong initial or spatial trace, forged certificates, invalid checkpoints and unmet accuracy; independently compare quadrature against exact L2 and sample each cell and time slab.

| case | initial bound | final bound | sampled max error | matched uniform bound |
|---|---:|---:|---:|---:|
| manufactured | 5.505e-16 | 5.505e-16 | 1.11e-16 | 5.505e-16 |
| forced heat | 0.137323 | 0.00818661 | 9.48058e-5 | 0.00671963 |
| reaction diffusion | 0.0909209 | 0.00511990 | 7.40211e-5 | 0.00566988 |
| initial decay | 0.205984 | 0.0122799 | 0.000142209 | 0.0100795 |

Adaptive vs uniform: one improvement, two regressions among nonpolynomial cases; no universal claimed advantage. Symmetric pair candidates can improve when single splits plateau. No native timing claim. The early target of 1e-8 was not achieved on the nonpolynomial cases within the six-knot budget; this limitation is not hidden by looser engineering targets.

## Acceptance / remaining

Pinned manifest inherits J closure plus J manifest and K source, tests, tools and report; K's own manifest cannot self-pin. Native acceptance requires exact host SHA and J receipt, 61 zero-skip tests, four benchmarks and replayed checkpoints. Existing tensor MEL wire unsupported; standalone research JSON profile only, with separate problem digest required for full solution meaning. Full repo dependency checkout and native installed worker remain unexecuted locally. No production or native Lu promotion. Next: broaden to 2 spatial coordinates + time, or qualify I/J/K and tensor checkpoint wire before publication.
