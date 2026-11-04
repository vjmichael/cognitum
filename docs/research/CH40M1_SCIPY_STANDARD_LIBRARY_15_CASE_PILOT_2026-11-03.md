# CH40-M.1 — standard-library-first incumbent pilot (2026-11-03)

**Executed engineering baseline, not scientific release.**

Cognitum's C14 original CH23 frozen dataset set was evaluated with the already-available SciPy `minimize` L-BFGS-B and Powell optimizers, 3 bounded starts/method and 65 maximum iterations per start, controlled to one OpenBLAS thread. All **15/15** input trace SHA-256 hashes were checked against CH40-K's previously signed binding records. Unlike a new custom solver, these optimizers are maintained external algorithms.

For every float64-proposed improvement, the existing *independent rational-interval point-objective evaluator* was called on the exact feasible point before improvement was accepted. **2/15** cases have a stronger feasible-point lower-bound enclosure:
- `quasi_separated_n160_i00`: lower-bound gain ≈ **0.81985551243794** (reproduction of already-reported CH40-L improvement; **do not double count**).
- `quasi_separated_n80_i00`: lower-bound gain ≈ **0.97643387889151** (an additional verified incumbent improvement).
- Other thirteen cases: no better candidate under this specific budget.

**4/4** focused tests passed: complete frozen hash pins, candidate feasibility, no global-proof promotion, singular-information refusal. The benchmark's reported search CPU totals ~0.589s (single process, 15 cases, excludes independent verification/IO); **this is not a matched-CPU algorithm superiority finding**.

Python environment had SciPy, NumPy, statsmodels, SymPy, mpmath, and native MPFR, but did not have python-flint, IBEX, Ipopt or SCIP. **No FLINT/IBEX/Ipopt/SCIP speed or mathematical correctness benchmark has occurred.** FLINT's Arb and python-flint are priority candidates for the next interval-verification adapter; IBEX interval contractor modeling, native distribution/licensing and CPU-matched comparisons remain open.

Source, runnable adapter, test suite, full per-case results, log and manifest: conversation artifact `Cognitum_CH40M1_SciPy_Standard_Library_15_Case_Pilot_2026-11-03.zip` (SHA-256 `82a932b4b9bd7c0ded7801f45e452cf46ef95f527d8bcf2a924627b4fff18829`). This GitHub commit records results only; executable source is in the linked conversation artifact.

The 0.05 finite-root gap has **not** been proved closed. A local optimizer's feasible solution improves only a *lower* bound and neither certifies a global maximum nor validates causal identification. Preserve the signed CH40-J historical chain unchanged. C14 scientific release remains **NO_GO**.

Next: implement an optional `python-flint` Arb matrix/objective enclosure baseline with cross-library checking, then IBEX contractor/B&B modeling feasibility review; compare with identical data, objective and certified outcomes, accounting for full CPU budget and build/distribution requirements. 
