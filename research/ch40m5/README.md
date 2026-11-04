# Cognitum CH40-M.5 — native bundled CLP optimizer on 15 original frozen C14 cases

**Engineering PASS for native original-case execution (15/15) and independent feasible-point checking (15/15). Scientific NO_GO.**

## Core discovery

IBEX 2.9.1 source already bundles **CLP 1.17.6** under `lp_lib_wrapper/clp/3rd/`. No extra Debian developer packages or HTP upload were required. Built IBEX in a separate research directory using Filib and `-DLP_LIB=clp`; compile completed with `ibexopt` linked to bundled CLP. No system package or Lu changes.

IBEX 2.9.1 documentation explicitly describes its CLP backend as experimental and does not guarantee or support it. Any solver-reported bounds remain untrusted until independently certified.

## Executed original frozen CH23 cases

- 15 exact original CH40-E root-trace SHA-256s and 15 exact generated Minibex SHA-256s checked against the CH40-M.4 model manifest.
- All 15 IBEX/CLP native optimizer processes were executed. Strict run: 6/6 80-row runs returned reports; 9/9 160-row runs were terminated under a nine-second CPU cap with return code -9.
- Controlled 24-second CPU-cap replays of the 9 original 160-row cases yielded **9/9 valid native optimizer reports**. Wall times roughly 12.9–15.8 seconds including expensive setup versus ~3.8–4.1 seconds for 80-row runs.
- 15/15 finite candidate points from the respective successful runs were independently evaluated using the original frozen Fraction/Decimal `point_objective` kernel.
- All bounded-search runs hit an internal 0.15-second optimization timer. Native *reported* absolute objective gaps range from **41.4435 to 276.9450** (target 0.05). **None** is independently verified as a global bound.
- Seven evidence-contract tests passed, including original case identity, 15 independent candidate checks, strict-vs-expanded cap distinctions and scientific refusal.

## Original case matrix

| Case | Rows | CPU cap | Wall s | Solver-reported gap | Independent candidate |
|---|---:|---:|---:|---:|---|
| `one_event_n160_i00` | 160 | 24 s | 12.92 | 100.8758 | PASS (point only) |
| `one_event_n80_i00` | 80 | 9 s | 3.78 | 60.4927 | PASS (point only) |
| `quasi_separated_n160_i00` | 160 | 24 s | 12.91 | 276.9450 | PASS (point only) |
| `quasi_separated_n80_i00` | 80 | 9 s | 4.15 | 173.0755 | PASS (point only) |
| `rare_1pct_n160_i00` | 160 | 24 s | 15.77 | 96.9962 | PASS (point only) |
| `rare_1pct_n160_i13` | 160 | 24 s | 15.09 | 57.7172 | PASS (point only) |
| `rare_1pct_n80_i00` | 80 | 9 s | 3.81 | 57.8518 | PASS (point only) |
| `rare_5pct_n160_i00` | 160 | 24 s | 13.59 | 131.7186 | PASS (point only) |
| `rare_5pct_n80_i00` | 80 | 9 s | 4.12 | 76.6593 | PASS (point only) |
| `zero_balanced_n160_i00` | 160 | 24 s | 12.90 | 47.4206 | PASS (point only) |
| `zero_balanced_n80_i00` | 80 | 9 s | 3.84 | 41.4435 | PASS (point only) |
| `zero_imbalanced_n160_i00` | 160 | 24 s | 13.48 | 69.8672 | PASS (point only) |
| `zero_imbalanced_n160_i05` | 160 | 24 s | 13.25 | 87.4948 | PASS (point only) |
| `zero_imbalanced_n160_i07` | 160 | 24 s | 13.69 | 69.0878 | PASS (point only) |
| `zero_imbalanced_n80_i00` | 80 | 9 s | 3.79 | 64.0276 | PASS (point only) |

## Reproduction and security

Original CH40-E source SHA-256 `6dfd4ea081b783503c7d960419766296642da68a246033fdcf0da94282882078`; CLP bundled source SHA-256 `f9cfcdd3db23bbc2d18b562012a7e25b99a40e8ce72dc296bd46dddb2970e12a`.
The original root data, CH39 archive, acceptance pins and CH40-E proof traces are **never modified**. External packages, binary or original 12MB traces are not duplicated in this report.

Rebuild from the verified IBEX archive and existing offline Flex/Bison:

```bash
cmake -S /path/to/ibex-2.9.1 -B /isolated/build-clp -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DINTERVAL_LIB=filib -DLP_LIB=clp \
  -DFLEX_EXECUTABLE=/isolated/flex -DBISON_EXECUTABLE=/isolated/bison
cmake --build /isolated/build-clp -j 6
python research/ch40m5/replay_clp.py \
  --archive /path/to/Cognitum_CH_C14_40_E_Actual_MPFR_Producer_Traces_2026-11-03.zip \
  --ibexopt /isolated/build-clp/bin/ibexopt --out /isolated/m5-results \
  --cpu-cap 24 --wall-cap 29 --solver-seconds 0.15
```

## Trust boundary and next engineering gate

This is the first entire original 15-case run through the actual bundled CLP native optimizer. The short solver time and large gaps rule out a scientific PASS; experimental CLP outputs cannot be treated as independent MPFR interval certificates. Only pointwise feasibility was independently checked. The 0.05 global gap on frozen root boxes remains **0/15**.

Next: diagnose parser and repeated nonlinear function expansion setup overhead, reduce model size without altering exact functional semantics, increase matched solver-time budgets, and require a separately implemented interval proof of every claimed global upper bound. See Cognitum issue #51.

## Artifacts

`results/ibexopt_clp_original15.json` — initial strict-cap pilot; `results/ibexopt_clp_original160_highcap.json` — nine 160-row replays; `results/CH40M5_ACCEPTANCE.json` — final machine-readable scoped record; `optimizer_pilot.py`, `optimizer_highcap.py`, `replay_clp.py` — executable research tooling; `test40m5.py` — seven contract tests; `models/` — original 15 Minibex expressions; `results/logs/` and `results/cov/` — bounded optimizer outputs. All archive members are SHA-256 recorded.