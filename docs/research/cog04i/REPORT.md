# COG-04I — residual-driven adaptive differential equation learning

Parent `a9bc9fc81f2cddebfc66fd0ffc169866e395dcde`. Local development candidate; no branch change or new CI run. Existing COG-04G/H hosted gate is not a development dependency but remains a publication/acceptance dependency.

## Implemented bounded profile

- Real one-input, one-output clamped cubic KAN edge from COG-04A/B. Fit coefficients by weighted SVD least squares on the differential operator, not analytical solution labels. Gauss–Legendre nodes integrate the squared polynomial residual exactly in ideal arithmetic (degree at most 16). Native float64 fitting is not the verifier.
- On `[0,1]`, solve stable scalar IVP `u' + a*u = f` with initial value, and coercive scalar Dirichlet BVP `-u'' + a*u = f` with two endpoint values. Represented nonnegative constant `a`; polynomial forcing degree <= 8; bounded finite binary64 data. Cubic spline has at most four simple interior knots (12 total, eight coefficients). Unknown solution may be nonpolynomial. No unsupported negative-reaction, arbitrary domain, coupled/nonlinear or multidimensional approximate equation claim. COG-04H exact solver remains unchanged.
- Endpoint coefficients fixed by construction, no approximate boundary penalties. Exact monomial replay of every nonempty spline span via existing polynomial witness; check C2 matching at all interior knots. Exact Bernstein residual upper hull and exact squared L2 residual integral on each entire span. Certificate binds problem and represented-model SHA256; independent replay checks every field. Nonzero trace error denies solution error certification even with zero differential residual.
- Stable IVP integrating factor yields `||u-v||inf <= R` for continuous residual bound `R` and exact initial value, since `a>=0` and unit length. Dirichlet BVP comparison with barrier `R*x*(1-x)/2` yields `||u-v||inf <= R/8`: `-b''+a*b>=R`; compare positive and negative error with zero endpoint traces. These are bounds on the mathematical represented spline, not evaluation roundoff or uncertain input, and depend on the stated operator profile. No generic stability theorem. Positive tolerance mandatory; accepted accuracy requires independent replay and bound <= tolerance; budget exhaustion is nonconvergence, not silent success.
- Select highest certified residual span, attempt midpoint insertion and coefficient refit, retain only strict reduction of the certified solution error bound. If the highest-scoring split does not improve the bound, try remaining spans in order. No labelled analytical values used in fitting or refinement. A matched uniform-knot comparator at equal coefficient count is evidence, not an automatic fallback.

## Local Linux CPU evidence

Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0. All 53 scoped tests passed, no skips. Six analytic problems, exact residual and norm identities, C2 span coverage, independent numeric quadrature, all certificate-field tampering, mismatched problem/model, malformed inputs/budgets, hard trace failures, nonconvergence, and numerical basis independence. Three nonpolynomial cases with 1,001 disjoint evaluation points each:

| Case | Initial certified bound | Final certified bound | Sampled maximum error | Uniform matched bound |
|---|---:|---:|---:|---:|
| Exponential decay | 1.217832 | 0.02993493 | 0.000465612 | 0.04205609 |
| Reaction–diffusion | 0.1052994 | 0.006177372 | 0.000094619 | 0.006114549 |
| Relaxation | 0.01578210 | 0.000398187 | 0.000003756 | 0.000398187 |

The first two used eight coefficients; relaxation stopped at seven coefficients once its tolerance was certified. Adaptive improvement relative to the initial fit is not general superiority to uniform placement or conventional solvers. The reported bounds are conservative, and sampled error is not proof. Evidence contains full exact rational certificate fields, model bytes, analytical holdout summaries and fit timings. No claim of general learned target accuracy.

## Native gate outstanding

Full dependency checkout is not available locally; development tests use exact pinned COG-04A trainable KAN and COG-04B rational witness source recovered from preserved transfers. No mocks substituted for missing workers. `tools.cog04i.acceptance` requires the full inherited source manifest, same-head H receipt (37 passing tests and real checkpoint replay), all 53 tests, three benchmark passes, real existing MEL polynomial worker request with value/Jacobian/Hessian, exact checkpoint and residual proof replay, and request/result artifacts. The MEL worker gate has been authored but NOT executed locally. Do not publish before the existing G/H acceptance terminates and is reconciled. Follow the existing one-branch workflow; no automatic registration, training permission, new model-visible route, installed Lu, GPU or generic approximate PDE acceptance. Future tasks: multidimensional stable residual approximation, improved rigorous error estimators and matched cost comparisons.
