# CH40-M.2 — standard solver adapter research (no production activation)

**Scoped engineering gate PASS; C14 scientific release NO_GO.**

Real frozen data: 15 original CH23/CH40-J three-parameter cases, with exact SHA-256 pins from the independent CH40-K record. The original 800 MB expanded traces and CH40-J signed historical chain are **not modified or re-created**.

Nine Python research modules and tests live under `research/ch40m2/source` and `research/ch40m2/tests`. Source is committed, not merely documented.

## Implemented backend paths

- SciPy: bounded local candidate optimization; the previously accepted 15-case CH40-M.1 result was reused by **byte-level SHA-256 pin** `5778ec7f61dd5ccbb4a24fc9e4b6f3a467fc55dad6d56891cafdc8b37d583b16`. The two original independent feasible-incumbent improvements remain unchanged.
- SciPy differential_evolution: a new bounded 15-case float heuristic (fixed seed 31, 20 iterations) ran and found no meaningful additional gain (maximum absolute float objective change 1.387e-10). This is not a global proof.
- Optional FLINT/Arb: point Firth/log-Fisher determinant enclosure from a native Arb matrix; exact dyadic endpoints and **independent** rational/Decimal checker overlap required before accepting any result.
- IBEX: exact original objective *expression* serialized to 15 Minibex models, including Fisher 3x3 determinant and frozen parameter bounds. Requires native IBEX parser/optimizer to qualify.
- Optional Ipopt: local candidate adapter, never a global proof.
- Optional SCIP: nonlinear Firth objective with auxiliary linear objective variable; proposed solver bounds are marked unverified.

This execution environment lacked installed FLINT, IBEX, Ipopt/cyipopt and SCIP/PySCIPOpt. Their native paths therefore **have not been benchmarked or accepted**. The source uses explicit dependency-missing and refusal states rather than substituting a synthetic/approximate global certificate.

## Executed engineering checks

- 15/15 original frozen trace hashes matched; 15 native IBEX model files generated, **not parser-validated**.
- Seven original-case checks and four stdlib-only contract checks passed (**11/11**).
- A stdlib-only `python -S` test passed four tests and explicitly skipped the seven original-case tests due absent optional packages/fixtures.
- Independent extraction of the conversation package verified 35 member hashes; 11/11 tests passed from the extracted code against the external original data.
- No new interval upper bound, no 0.05 finite-root closure, no unrestricted optimum, no new scientific release.

## Reproducibility

Bring the original immutable CH40-K trace data, acceptance pins and CH40-J rational kernel. From repository root, with optional SciPy/NumPy installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/ch40m2/source/runner40m2.py \
  --traces /path/CH40K/traces \
  --pins /path/CH40K/CH40K_ACCEPTANCE.json \
  --reference-dir /path/CH40J/source \
  --previous-scipy /path/CH40M/scipy_15_results.json \
  --ibex-out /tmp/ch40m2/ibex_models --output /tmp/ch40m2/benchmark.json --execute-native
```

For frozen-fixture checks set `CH40M_TRACES`, `CH40M_PINS`, and `CH40M_REFERENCE_DIR`, then run `python -m unittest discover -s research/ch40m2/tests -v`. CI without the original fixtures must show skips, **not invented green scientific gates**.

## Supporting evidence artifact

`Cognitum_CH40M2_Standard_Solver_Adapters_All15_2026-11-03.zip` (400,356 bytes; SHA-256 `756e868290a60a797dc2dac9aef22cfca04019c6b28a470eb559529f293d5a63`) contains source, all 15 generated Minibex models, numerical result logs, acceptance file, dependency review and SHA manifest. The archive is a conversation artifact, **not committed to GitHub**.

Next gate: install license-reviewed native binaries in isolated test environments, independently validate 15 FLINT point enclosures, compile/execute 15 IBEX models, run actual Ipopt/SCIP candidate/global-search comparisons, then CPU-match and qualify rigorous bounds against the CH40 independent checker. Source availability is not runtime qualification.
