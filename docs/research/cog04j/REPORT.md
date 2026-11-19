# COG-04J — adaptive multidimensional elliptic residual learning

Base `a9bc9fc81f2cddebfc66fd0ffc169866e395dcde` plus exact unpublished COG-04I overlay. Independent local development only; no branch/CI changes. Native I and J publication gates remain distinct from local acceptance.

## Bounded architecture

Solve `-ax*u_xx-ay*u_yy+c*u=f` on the unit square, with zero Dirichlet trace on all faces, constant positive diagonal diffusion (each at least 1/16 and at most 100), nonnegative constant reaction and bounded sparse tensor polynomial forcing (degree <=4 per axis). The approximation is a sum of products of clamped cubic univariate KAN spline edge basis functions, with trainable tensor coefficients. This is a new compositional tensor-product research architecture, not the existing additive KAN MEL wire representation. Up to six interior dyadic knots across both axes; no arbitrary unstructured mesh or quadtree. All four coefficient edges are fixed to zero. Float64 weighted SVD least squares uses operator samples only, never analytical targets. Six Gaussian nodes per cell and axis suffice to integrate the squared polynomial residual in exact arithmetic. SciPy's spline evaluation is cross-checked against the existing COG-04A KAN `Layer.basis` on disjoint points and derivatives (six executed tests).

## Independent certificate

The standard-library-only verifier reconstructs the tensor spline cell polynomials by exact rational Cox–de Boor recursion using local coordinates. It verifies every full trace polynomial is exactly zero and matches value, normal first and second derivatives coefficient-by-coefficient at every internal interface; tangential/mixed traces follow by differentiation. Independently computes the operator residual, exact tensor Bernstein hull and exact squared L2 residual integral on every cell. Global residual bound R is the maximum of cell bounds. Let t be the coordinate corresponding to `max(ax,ay)`. The comparison barrier `b=R*t*(1-t)/(2*max(ax,ay))` is nonnegative on the boundary and satisfies `L b >= R`. Applying the maximum principle to positive and negative solution error gives `||u-v||inf <= R/(8*max(ax,ay))`, assuming the unique Dirichlet solution of the stated coercive problem. This certifies the represented mathematical spline, not the floating evaluation, uncertain physical coefficients or generic nonlinear/mixed derivative equations. A zero residual with an incorrect trace does NOT certify a solution. The model and problem are SHA256-bound; certificate replay checks all fields. Canonical size-bounded JSON checkpoint represents exact numeric values; no claim of signed authorization, protobuf or installed worker.

Spatial refinement prioritizes the largest certified residual cell, tries inserting an x or y strip knot at its midpoint and refits the coefficients; only strict improvement of the full-domain certified bound is kept. If no candidate improves, stop and report nonconvergence. Nonuniform placement is possible, but axis-aligned tensor strips refine entire rows/columns, not arbitrary local cells. Worst-case error may remain nonzero for forcing inconsistent with the smooth zero boundary corner traces. The constant-forcing corner case is tested as a refusal to certify requested accuracy.

## Local evidence

56 tests passed (zero skipped); independent basis, hard conditions, exact residual identity, full-cell coverage, continuous bound versus numerical samples and integrated squared residual, tamper and invalid input/refinement checks, checkpoint replay, insufficient tolerance, and four analytical problems. Each benchmark uses 4,355 independent points on a shifted grid, not fitting nodes. Nonpolynomial reaction–diffusion cases are checked against a separated Fourier-sine series in x with exact y-mode solutions, with an analytic omitted-tail bound (numerically evaluated for the diagnostic, not the proof).

| Case | Initial certified bound | Final certified bound | Sampled max error | Matched near-uniform bound |
|---|---:|---:|---:|---:|
| Poisson | 1.920e-16 | 1.920e-16 | 2.776e-17 | 1.920e-16 |
| Reaction–diffusion | 0.00523088 | 0.000298821 | 0.00000322418 | 0.000298821 |
| Anisotropic | 0.00375276 | 0.000922631 | 0.0000363786 | 0.000922631 |
| Asymmetric quartic | 0.0324785 | 0.00364764 | 0.000468686 | 0.00364939 |

Matched near-uniform comparator uses equal axis knot counts, rounding to the permitted dyadic grid. The asymmetric case chooses nonuniform y knots (0.25,0.375,0.5,0.625,0.75), with only a small matched advantage (~0.048%); remaining cases tie. No general superiority claim. Bound improvements from initial coarse fit are not accuracy or cost guarantees against conventional PDE solvers.

## Publication/acceptance dependencies

Local execution used recovered exact COG-04A `kan_trainable.py` (Git blob 238f1ea9969aab6ecd87be0dcefb9966ae6a6d59) and this new overlay, no fake dependencies. The full G/H inherited tree and I overlay are pinned for native acceptance. Hosted `tools.cog04j.acceptance` requires same-head successful I receipt with 53 tests and actual prior scalar MEL worker, exact source manifest, all 56 J tests, four benchmark checkpoint replays and hashed evidence. J tensor-product checkpoints have no existing MEL wire profile, so J intentionally does not claim a MEL worker call. Full hosted acceptance NOT executed. No installed Lu, routing, training permission, model-visible capability, GPU, general PDE, 3D, mixed diffusion, nonlinear, nonzero boundary or unstructured refinement claim. Native publication must wait for predecessor reconciliation and preserve the one-branch workflow.
