# COG-04L — bounded 2+1D transient scientific tensor KAN

Parent G/H `a9bc9fc81f2cddebfc66fd0ffc169866e395dcde`; unpublished I/J/K exact overlays required. Research-only. Not native or production accepted.

## Mathematical scope

`u_t - ax*u_xx - ay*u_yy + c*u = f(x,y,t)` on `[0,1]^2 × [0,1]`, with `ax,ay >= 1/16`, `c >= 0`, bounded polynomial forcing and compatible polynomial initial field; zero Dirichlet on all four spatial faces. Three separable cubic spline axes, at most five total dyadic interior knots, exact zero outer spatial coefficient slices and zero initial-time correction slice. Fit only PDE residuals and the initial lifting by weighted least squares; no target labels. Evaluate derivative orders through two with bounded numerical inputs. Retain only strict improvements of independently certified error and abstain when tolerance unmet.

Independent verifier uses rational Cox-de Boor local polynomials (not SciPy), reconstructs the represented binary64 coefficients exactly, verifies initial/boundary traces and C2 interfaces, and converts full 3-axis residual polynomials to Bernstein form. Convex hull gives each closed cell's uniform residual bound. For each time slab accumulate its spatial maximum residual times duration; comparison principle yields a uniform prefix bound. Also valid: stationary quadratic spatial barrier `R/(8*max(ax,ay))` and reaction barrier `R/c` when positive, with peak residual over the prefix. Take the minimum and maximum across prefixes. No L2 residual claim in L. Exact checkpoint replay binds problem and model digests and rejects tampering. This verifies the represented function, not general nonlinear/coupled or variable-coefficient dynamics. The method assumes the comparison-principle well-posed scalar parabolic problem; no physical units inferred.

## Local evidence

Linux Python local isolated research tests: 79 passed, no skip/failure. Four cases, each 9177 distinct evaluation points including boundaries and initial/final time. Manufactured exact polynomial plus independent truncated double sine-series references (explicit analytic tail upper bound). IEEE numerical evaluation diagnostic, not independent interval-certified reference arithmetic. Tolerances set after exploratory pilot, not blind benchmark thresholds. See included benchmark/certificate/checkpoint evidence.

| Case | Certified sup error | Sampled max error | Matched same-axis uniform bound |
|---|---:|---:|---:|
| Manufactured | 2.77363e-16 | 3.46945e-17 | 2.77363e-16 |
| Forced anisotropic | 0.00421650 | 0.000166051 | 0.00421650 |
| Reaction diffusion | 0.00483107 | 0.000217805 | 0.00478908 |
| Initial field decay | 0.02759027 | 0.00135152 | 0.02183046 |

Adaptive refinement reduced the coarse bound in all three nonpolynomial cases; tied one matched uniform run and lost two. Much tighter target and stronger adaptive advantage not demonstrated. Initial field decay remained relatively coarse. Full MEL tensor integration unsupported by existing serialization. No model advertising, authorization, or release changes. No claim of KAN advantage over established PDE solvers.

## Native publication gates

Prior G/H run 44627537828 ended 13/18: four MEL-04B stops because the workflow blob changed without re-binding its manifest cascade; G and H were skipped. Windows 3.11 C12 anytime shim test also failed (0 vs expected cost 7; root cause unconfirmed). The prior E/F workflow was green. The next publication must reconcile the five exact MEL manifests in dependency order (no weakening of source checks), qualify the C12 test, then run a single unchanged-SHA native matrix with all predecessor and G/H/I/J/K/L gates. Prepared helper performs source-pin reconciliation against the previously accepted Git tree and allowlisted blobs only. L requires same-head K receipt and strict 79/79 tests. Local overlay does not execute the native worker or installed Lu gates.
