# Cognitum C14 CH40-B — independent coupled, Taylor, and Krawczyk mathematics

Research continuation of accepted CH40-A on November 3, 2026.

## Run

On Windows, extract the **complete** reproduction package and double-click `RUN_CH40B_INDEPENDENT_WINDOWS.cmd`. Python 3.14 is supported. The core checker uses the Python standard library; one optional numeric derivative cross-check uses `mpmath` and is explicitly **skipped** if unavailable. The original pinned 6.1 MB CH39 archive is included; no MSYS2/MPFR runtime is needed for CH40-B itself.

On Linux/macOS: `python -m unittest discover -s tests -p test_ch40b.py -v`, then `python batch40b.py --jobs 4`.

Reports are `CH40B_WINDOWS_TESTS.log` and `CH40B_WINDOWS_ORIGINAL15_RESULTS.json` (or `CH40B_original15_results.json` for the development run). Case results are written after each completion. This run does **not** use a previously cached SUCCESS as proof of mathematical validation; each invocation recomputes every requested case.

## What CH40-B verifies

- Uses only the independently authored CH40-A `exact_decimal40.py`, `independent_checker40.py` and `verify_original40.py` for arithmetic, exact partition/source pinning and data loading.
- Every frozen CH33/CH29 127-node partition, model and external SHA-256 pin is verified; every one of 960 leaves receives a newly computed coupled likelihood–Fisher upper bound. Independent exact Sylvester tests guard the SPD duals.
- The dual inequality is `log det(F) <= tr(Q F) - log det(Q) - d` for SPD Q; each one-observation logistic surrogate is upper-bounded with a concave supporting line. Float bisection selects tangent positions **only**; all proof evaluation is outward Decimal interval arithmetic.
- Checks against a feasible objective lower bound **within each leaf**, not the global incumbent. Combines independently derived direct and coupled enclosures to produce conservative finite-box upper bounds.
- Independently derives the Firth score and Hessian using Fisher matrix derivatives, a direct interval determinant intersected with a positive Cauchy–Binet minor, and an interval adjugate inverse. This supports a second-order Taylor bound around the original incumbent for each case.
- Applies Krawczyk root inclusion/disjointness on **separate small, strictly interior test boxes** around each incumbent. A forged narrower contraction, false exclusion, bad matrix shape, or boundary application fails closed.
- Original CH29 producer proof contains **zero actual Newton contractions/exclusions**. The CH40-B Krawczyk experiments DO NOT retroactively add such contractions to the original certificate or certify its producer-local Taylor/Newton upper bounds.

## Tested scope and limitations

The original 15 frozen CH23 cases, each with 127 archived certificate nodes and 64 terminal leaves, passed independent CH40-B finite-box checks. Twenty independent unit/adversarial tests passed on the development host. Coupled bounds were tighter than the independent CH40-A direct bound on 766 of 960 leaves; this is **not** a comparison against the producer's specialized MPFR coupled bound. Five independent interior test boxes contracted, two excluded stationary points, and eight returned no gain; these are diagnostic test boxes, not frozen proof-tree pruning events.

The verifier is genuinely implemented with different arithmetic and analytic formulas from Cognitum's MPFR/Jet code, but **does not yet certify equivalence to every original CH27–CH39 optimized producer-local bound**, and only tests Taylor/Krawczyk on small boxes near original incumbents. No full real-space (`R^d`) global-optimality proof exists. All 15 remain `REPLAYED_BUT_UNRESOLVED`; production promotion **NO_GO**. There is no new Windows execution result until the user runs this kit, and no changes to Lu or production C14/G25.

All downloaded inputs are pinned to the immutable CH39 package SHA-256 `9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b`.