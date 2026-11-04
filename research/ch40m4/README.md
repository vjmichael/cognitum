# Cognitum CH40-M.4 — IBEX native original-case parser and point-enclosure validation

**Engineering scope: PASS (15/15 parser, 15/15 independent point intersections). Scientific release: NO-GO. Date: 2026-11-03 America/Phoenix (2026-11-04 UTC).**

## Why this experiment was run

CH40-M.3 had configured IBEX 2.9.1, but its compile was blocked by offline Flex/Bison prerequisites. The fifteen generated Minibex models were not native parser-checked. This experiment uses the previously uploaded, SHA-pinned IBEX source tarball and offline Debian 13 Flex/Bison `.deb` packages, fully isolated beneath `/mnt/data/CH40M4`, with no system package installation.

## Native build

- IBEX 2.9.1 source SHA-256: `b3cd09c3be137fd2ff0f2570c3bcbdfcd9ea62fcf04d45d058db3b0dbb1d8872`.
- Flex 2.6.4 `.deb` SHA-256: `75f963765232c356d0a2fb70e780dfa9de2425aca036ec60eefb7fc98a2c905b`.
- Bison 3.8.2 `.deb` SHA-256: `ce6eb1f7aad18850e32d223a68f54bcbe756d74f138c8ec5460ad9d220f4d335`.
- CMake `-DCMAKE_BUILD_TYPE=Release -DINTERVAL_LIB=filib -DLP_LIB=none`. Configured and linked `libibex.a`, `ibexsolve`, and `ibexopt`. Bison non-system data path was resolved with `BISON_PKGDATADIR=<isolated-prefix>/usr/share/bison`.
- `ibexopt` **cannot operate without an LP backend**; this binary exits with the native error `ibexopt requires a LP Solver`. This is not an optimizer success.

## Original-case provenance

The 15 immutable root traces were read from the accepted CH40-E original-producer archive, archive SHA-256 `6dfd4ea081b783503c7d960419766296642da68a246033fdcf0da94282882078`. Each original root trace SHA-256 was checked against the `CH40E_MANIFEST_SHA256.json` inside that archive. Every case has dimension 3, 80 or 160 original observations, and original coefficient box `[-10,1] × [-5,5] × [-5,5]`. No synthetic/rounded-short fixture was substituted.

The Minibex generator reproduces the expression generator from `research/ch40m2/source/ibex_model.py` exactly: per-row logistic contribution, per-row Fisher weight, six unique Fisher information entries, 3x3 determinant, and negative Firth penalized log likelihood as minimization goal. Models were saved with SHA-256 in `results/model_manifest.json`.

## Actual gates

1. **Native parser and bounded solve execution:** 15/15 original Minibex models accepted by `ibexsolve`. Command per case: `ibexsolve --simpl=0 -t0.08 --stop-at-first CASE.bch`, with Linux AS limit 1.4 GB, CPU limit 6 sec, and subprocess wall timeout 7 sec. A successful parser/execution response proves neither unique solutions nor a bounded global optimum. The generated `.cov` files are solver artifacts, not independently certified C14 optima.
2. **Independent numerical point-enclosure equivalence:** 15/15 model incumbents evaluated by the newly compiled native C++ `ibex::System` / `goal->eval` interval code; each resulting native Filib minimization interval overlaps the separate CH40-E rational/Decimal `point_objective` enclosure after correct objective sign reversal. This is *single-point* equivalence, not full-domain formula proof.
3. **Evidence/refusal integrity:** seven local evidence/identity/negative tests passed, including model-tamper mismatch and refusal to mark global optimization certified. Results recorded in `results/CH40M4_ACCEPTANCE.json`, `results/ibex15_parser_execution.json`, `results/ibex15_point_intersections.json`.

## Explicit scientific and engineering limits

- **Scientific release NO-GO**. 0 new globally optimized certified upper bounds; 0 gaps newly closed to the 0.05 threshold.
- The LP-free IBEX build does **not** run global optimization. Native parser validation and interval evaluation cannot be promoted to global proof.
- No comparison of equal-budget full global solvers, no proof of equivalence for all coefficient values, no production enablement, no causal-identification conclusion.
- Native point interval and rational reference use the same original binary64 incumbent (Fraction from each rounded binary float) and distinct arithmetic implementations.
- Source/binaries of IBEX and its dependencies are not redistributed in the engineering evidence ZIP. Before distribution, review licenses (IBEX source includes LGPL-3.0 terms; SoPlex has academic/commercial licensing considerations). The supplied benchmark sources are research-only.

## Next CH40-M.5 gate

Resolve an **LP-enabled IBEX build**, preferably using COIN-OR CLP with matching development headers/library closure and documented licensing, then run `ibexopt` on all 15 original models with bounded CPU/memory. CLP shared runtime libraries are present on the test host, but `ClpSimplex.hpp` and development linkage were not available: the currently compiled optimizer requires additional development packages. Check each claimed global upper bound with the independent rational/MPFR verifier before any promotion. Then compare matched CPU/memory budgets with custom MPFR, FLINT/Arb and SCIP. Ipopt's missing SPRAL/MUMPS dependency closure is a separate local-optimization task, not a replacement for certified global optimization.
## Repository replay commands

The self-contained, immutable-source CLI harness is `research/ch40m4/run_original15.py`. It imports the existing `research/ch40m2/source/ibex_model.py` expression serializer, never substitutes synthetic original cases, and refuses an altered CH40-E archive.

```bash
cmake -S research/ch40m4/native -B /tmp/ch40m4-native \
  -DCMAKE_PREFIX_PATH=/path/to/isolated/ibex/install
cmake --build /tmp/ch40m4-native
python research/ch40m4/run_original15.py \
  --archive /path/to/Cognitum_CH_C14_40_E_Actual_MPFR_Producer_Traces_2026-11-03.zip \
  --ibexsolve /path/to/ibexsolve --ibex-point /tmp/ch40m4-native/ibex_point \
  --out /path/to/isolated/ch40m4-results
```

Replays are *not* a substitute for an LP-enabled optimizer or full independent global-bound verification. For the accepted source/pin and per-case result bundle, see the conversation artifact identified by SHA-256 `5df3098b44e22b8ab036bcb4f3bab59f4b46cf3fe716d3b17e3abea6608972e3`.
