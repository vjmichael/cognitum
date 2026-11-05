# Cognitum CH-C14-27 — coupled Fisher–likelihood bounds + selective interval Newton

**Status:** research/engineering verification PASS; **0/15 global-gap certificates**;
scientific/production **NO-GO**. No modifications to Cognitum production C14,
pinned G25, Lu, Windows or DLCs.

## Scope

This package uses the *original* 15 CH23 deterministic datasets (12 frozen
bounding cases and three original ambiguous zero-event cases). CH27's
`frozen_protocol.json` binds the exact input SHA-256 digests, source SHA-256s,
160-bit MPFR evaluation, 224-bit replay, finite original coefficient box,
15-node engineering budget and 0.05 absolute proof tolerance. It is an
exploratory reanalysis of **already-seen** datasets, not a scientific holdout.
The official CH23 original source and all historical receipts remain unchanged.

## What changed

- `coupled27.py`: independently valid logdet dual bound from an exactly
  positive-definite matrix Q and scalar concave supporting lines. Combines
  min with CH26's Loewner/tangent bound. All proof decisions use directed
  MPFR endpoints; binary64 is permitted only to choose supporting points.
- `interval_newton27.py`: directed interval-gradient, analytic-Hessian
  Krawczyk enclosure. **Only boxes strictly interior to the original root
  domain may be contracted or excluded.** A root-domain boundary is never
  silently discarded. No uniqueness claim.
- `solver27.py` / `verifier27.py`: complete branch-and-bound candidate-domain
  coverage with each contraction proof independently replayed. Higher
  precision replay rejects modified partitions, fake certificates and unsafe
  contractions.
- `frozen_duals.json`: original-case Q matrices with rational exact-SPD
  checks; no online numerical trust in a heuristic matrix inverse.
- `frozen_newton_probes.json` + `newton_probe_results.json`: original-seed
  narrow-box experiment (6 contracted, 7 no gain, 2 no seed). These
  contractions are **not** misrepresented as global search pruning.
- `comparator15/`: unchanged CH26 mathematical bound at the same **15 nodes**,
  with higher-precision replays. Source has not been modified. CH26's
  published 127-node benchmark is separate and not an equal-node comparator.

## Reproduction from ZIP root

Requires Linux with MPFR (`libmpfr`), Python 3.13, NumPy, SciPy, pytest.
No network access, GPU or Lu is needed. Open a shell at the extracted ZIP root:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest -q CH_C14_27/tests
python CH_C14_27/audit27.py --replay
python CH_C14_27/run_case27.py zero_balanced_n80_i00
python CH_C14_27/probe_newton27.py
```

The recorded benchmark packages are already bundled with 15 original input
JSONs, per-case solver proof trees, independent replays and CH26/15 comparator
receipts. `audit27.py --replay` is read-only except for regenerating
`study_summary.json` and checks all 15 original input hashes, the source
pins, the 15 proof trees and six local interval-Newton contractions. It does
not regenerate the CH23 optimizer dataset and does not need to; the original
CH23 archive remains available under `CH_C14_23/` for a separate source audit.

To rerun the full search, call `run_case27.py <case_id>` for the IDs listed in
`frozen_protocol.json`. The source/fixtures are also in the Cognitum GitHub
research branch `cognitum/ch-c14-27-coupled-newton-20261102`.

## Numerical outcome

Equal 15-node CH26 comparator: 12 strictly improved, 3 tied, 0 worsened;
mean objective-gap upper bound 10.7123 → 8.5111, with total solver+replay CPU
134.714 → 251.115 seconds. **0/15 finite-box 0.05-gap closures.**
Original CH23's three distinct-local-maxima ambiguity cases remain refused.
The initial experimental 63-node run exceeded the execution cap without a
certificate. These results are not a controlled equal-CPU comparison.

See `Engineering_Report_CH_C14_27.md` and `study_summary.json` for exact
per-case receipts and limitations. Outward-rounded replay is not a formal
proof assistant, does not establish global optimality on unbounded R³,
causal effect identification, nominal confidence intervals or production
readiness.