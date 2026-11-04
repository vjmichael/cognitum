# CH40-M.4 continuation — all-15 independent rational/Arb candidate checks

**Date:** 2026-11-03 Arizona time / 2026-11-04 UTC.
**Scope:** Native original-case research, not production or scientific certification.

This *supplements* the [main CH40-M.4 research record](https://github.com/vjmichael/cognitum/tree/main/research/ch40m4), which already contains IBEX/SoPlex 1-second runs and two representative rational/Arb dual-point comparisons.

## New executed experiment

1. Re-used IBEX 2.9.1, Filib 3.0.2.2 and bundled SoPlex 4.0.2 compiled from original official sources, verified via the HTP offline packages. The CLP backend is **excluded**: it SIGSEGVs even on an upstream IBEX sample.
2. Regenerated the exact original 15 CH23 Minibex models from the original CH40-K trace hash-pinned datasets. Each byte stream matched the original CH40-M.2 model archive. A native SoPlex/IBEX optimizer ran all 15 with `--rigor --simpl=0 --timeout=0.4 --abs-eps-f=0.05`, a 1.5 GiB process virtual-memory limit, and a 27s wall watchdog each.
3. The 15 real native runs returned exit code 0 and an IBEX-reported interval, but **15/15 terminated at their own solver time limit**. Width range: **41.3886447061–276.9450088032**, **0/15** achieved the target 0.05. This shorter run is not CPU-matched against CH40 or the longer one-second native package.
4. Parsed IBEX's **printed, rounded** 3-coordinate candidate for each case. Treated the printed point as an *independent new point* (not the exact internal IBEX candidate). For all 15 cases, reevaluated the full Firth objective using native 256-bit FLINT/Arb and the separate rational/Decimal checker. The intervals overlapped in **15/15** original cases. All 15 feasible values were weaker than their respective frozen feasible incumbents.
5. All 15 IBEX intervals intersect the original CH40-L **independently certified max-objective intervals** after reversing objective sign (IBEX minimizes negative Firth); no proof conflict was observed. **This intersection is an audit sanity check, not an independent validation of IBEX's global bounds**.
6. The known convex test `min (x-1)^2+(y-1)^2` with `x in [0,2]`, `y in [-1,3]`, constraint `x>=0`, succeeded using SoPlex/IBEX rigor mode with certified optimum interval `[0,0.0140123787187]` containing the known global minimum 0.0. The same toy and an upstream IBEX benchmark crashed in the CLP build; don't ship CLP.

## Contents

- `IBEX15_SOPLEX_04S.json`: native SoPlex/IBEX interval reports and command line results for all original cases (unverified global bounds)
- `IBEX15_INDEPENDENT_AUDIT.json`: original trace hashes, exact model hashes, original CH40-L intervals, exact 256-bit Arb and independent rational point-enclosure boundaries
- `opt15_soplex.py`: bounded native 15-case runner; refuses altered model files
- `audit_native15.py`: actual independent FLINT and rational point re-evaluator; verifies original C14 source hashes and model-byte equivalence
- `test_acceptance.py`: pure-stdlib tampering/refusal tests
- `MANIFEST_SHA256.json`: SHA-256 pins for every artifact in this package

All original 800 MiB CH40 traces and downloaded 16+ MiB native packages remain external and unchanged; research scripts currently use the local Linux research paths `/mnt/data/CH40K`, `/mnt/data/CH40M2`, `/mnt/data/CH40M3`, etc. To repeat on another computer, stage those exact packages or adapt the paths. Do not substitute synthetic data.

**Engineering assessment:** Established IBEX provides a working native interval-optimization baseline, but the current *naïve full Firth/Gram determinant expression* performs poorly under the bounded search. Factor the model / introduce shared Fisher subexpressions / use interval contractors, then compare same CH40 leaf boxes with identical budgets and a separate global-bound verifier. Keep SoPlex as the research backend and FLINT/Arb as a promising arithmetic engine; C14 scientific release remains **NO_GO**.
