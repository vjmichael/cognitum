# Cognitum CH40-M.3 — real native FLINT/Arb and SCIP integration baseline

**Research execution completed 2026-11-03. Scientific release: NO_GO. This package is source/results only and does not duplicate uploaded libraries or frozen original traces.**

## Executed against 15 original frozen CH23 cases

Native uploaded packages (publisher SHA-256 checked before loading) were installed in `/mnt/data/CH40M3/site` **only**, leaving system Python and Lu unchanged. Python 3.13.5, Linux x86-64. FLINT/Arb Python 0.9.0 bundles FLINT 3.6.0; PySCIPOpt 6.3.0 bundles SCIP 10.0.2.

- **Native FLINT point objective:** 15/15 point enclosure intersections match separately run original rational/Decimal checker at 256-bit Arb precision. This validates feasible *points*, not global optima.
- **Native FLINT region upper bound:** using likelihood interval upper plus Fisher Gram/Hadamard determinant upper, conservatively agrees with independently recomputed rational upper on 15/15 highest-cap original terminal boxes. It does **not** beat any of their previously signed upper bounds. Naïve interval determinant directly crosses zero on 15/15 tested highest-cap boxes; the conservative Hadamard path avoids invalid log determinant claims.
- **Measured arithmetic-kernel CPU:** 0.15450 s FLINT vs 6.38068 s existing rational/Decimal for the 15 sampled terminal boxes, **41.3x ratio at this isolated calculation level**, with Arb upper caps between about 2e-9 and 5.8e-8 looser than independent reference. Not a 41x whole-solver or end-to-end Lu benefit and not exactly identical algorithm/precision.
- **SCIP:** the CH40-M.2 expanded nonlinear Firth expression was OOM-killed during its first native attempt. CH40-M.3 replaces it with bounded auxiliary variables for row logits, probabilities, weights, row log terms, Fisher entries and logdet. It ran 15/15 original pinned cases, 1.5 s solver per case, SCIP memory limit 512 MiB, Linux process virtual-address cap 1.4 GiB, subprocess wall cap 12 s. All hit the short solver time limit, 3 returned feasible points. All three points were independently enclosed with FLINT and the rational/Decimal point checker. None gave a **material** improvement beyond original feasible incumbents at the predeclared >1e-8 threshold. Treat a ~1e-15 numerical change as noise for promotion. SCIP-reported dual bounds are **not rigorous interval certificates** and were intentionally excluded from the accepted result.
- **IBEX 2.9.1:** source and SHA pin verified. CMake configured with bundled Filib and no LP (`-DINTERVAL_LIB=filib -DLP_LIB=none`) but stopped at missing Flex/Bison before compilation. The 15 previously generated Minibex C14 models have NOT been parser-tested. `INTERVAL_LIB=direct` is not a rigorous substitute; licensing and GAOL/LP backend selection remain open.
- **Ipopt 3.14.20:** uploaded conda-forge Linux binary extracted, but dynamic loader reports `libspral.so` and `libdmumps_seq.so` absent. `cyipopt` is available as a source tarball but was not built; no Ipopt C14 objective was executed.

## Tests and scope

- `python test40m3.py -v`: 8/8 passed with original frozen fixtures and both native packages present. In clean environments, external-fixture and native import checks skip rather than substituting synthetic evidence.
- `python -m unittest discover -s HTP_IBEX_Prereqs -p test_download.py -v`: 3/3 pure offline HTP tests passed.
- All source hashes are compared against CH40-K acceptance; original CH40-J signatures and CH40-L trees remain unchanged.
- No certified global-upper-bound improvement, no 0.05 gap closure, no causal-identification guarantee, and no production enablement.

## Archive layout

`CH40M3_ACCEPTANCE.json` — machine-readable honest gate outcomes.
`results/` — independently verified Arb points, 15 region bounds, kernel timing, 15 SCIP run records, three independently checked candidates.
`logs/` — terminal logs, IBEX configure failure, SCIP OOM recovery, tests.
`check_flint15.py`, `flint_hadamard_regions.py`, `benchmark_arb_vs_rational.py`, `scip_compact.py`, `scip_15_guarded.py`, `verify_scip_candidates.py` — exact experiment code.
`HTP_IBEX_Prereqs/` — small Windows **download-only** helper for officially checksummed Debian 13 `flex` and `bison` packages needed to finish IBEX build.

These research scripts use the original Linux laboratory's `/mnt/data/CH40K`, `/mnt/data/CH40J`, `/mnt/data/CH40M2` and `/mnt/data/CH40M3` paths. For different file layouts, change those paths before execution, or stage the accepted frozen packages into the same layout. This is not yet a relocatable Cognitum runtime adapter.

## Next engineering gates

1. Download the verified Debian 13 Flex/Bison package pair with `HTP_IBEX_Prereqs/Run-IBEX-Build-Tools.cmd`, upload to `/Cognitum/Packages`, then extract only in isolated Linux research prefix. Finish IBEX compilation and **native parser** acceptance of all 15 Minibex models. A generated `.bch` file alone does not prove correctness.
2. Resolve the full Ipopt runtime dependency closure from conda-forge in an isolated environment; compile cyipopt or bind Ipopt's API and test the exact C14 objective.
3. Evaluate IBEX/SCIP and FLINT with **matched CPU/memory budgets**, independent certified upper bounds, and actual convergence results. Decide whether verified FLINT may replace the custom numerical kernel; retain the independent checker.
4. Preserve library license obligations and source provenance before optional CI/backend adoption; keep C14 scientific NO_GO.

Official build prerequisites: [IBEX installation documentation](https://ibex-team.github.io/ibex-lib/install-cmake.html). For the Debian build helper, SHA pins come from official [Flex](https://packages.debian.org/trixie/amd64/flex/download) and [Bison](https://packages.debian.org/trixie/amd64/bison/download) listings.

