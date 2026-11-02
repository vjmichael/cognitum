# CH23 source recovery for CH24 verified interval solver

**Date:** 2026-11-02 · **Status:** Provenance and repository recovery complete; CH23/CH24 scientific release still NO-GO.

## Original evidence

Original Library ZIP: `Cognitum_CH_C14_23_Larger_Holdout_Bounded_Global_2026-11-02.zip`; its SHA-256 is `4a8c72987b1552a7754dfb43aff4b3b67c40c7a2986832d78c1924ca2eeb5c47`.

The thirteen extracted original files are committed **byte for byte** under `../ch_c14_23/`. GitHub blob hashes were checked against Git's local original hashes for every file, including `results.jsonl` (729,690 bytes). The original `SHA256SUMS.json` verifies twelve payload files. The extracted files are also filed in Library `/Cognitum/Development/CH_C14_23/`.

An earlier CH23 documentation-only commit was `718e66e57e843f6270e082a46c1259ab888d082a`. This recovered source commit adds the complete reproducible research payload; the original archive was *not* rewritten and the binary ZIP was not duplicated in Git.

## Local verification of recovered payload (not a new study)

- SHA-256: 12/12 files matched the original `SHA256SUMS.json`.
- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q test_ch23.py`: **10 passed**.
- `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python independent_audit.py`: **PASS**, 192 datasets, 2,304 attempts, 2,298 locally validated attempts, 3 ambiguous datasets refused, 195 independently recalculated local-maximum representatives, 12 bounded-box cases, 720 sample points, **zero globally certified optimizers**.
- Raw per-dataset row CSVs are not stored in the original archive. The frozen `ch22_pinned.py` generator, `frozen_protocol.json`, `run.py`, and `results.jsonl` preserve the deterministic seed namespace, data hashes, per-start receipts and full reproduction instructions; the auditor regenerates and verifies all dataset digests.

## Next experiment handoff

- Use `../ch_c14_23/run.py::generator`, the original CH23 protocol and the recorded data digests to reconstruct every selected held-out dataset. Never synthesize substitutes for missing cases.
- Evaluate the existing `verified_bnb.py` directed-MPFR bounded-box solver on the 12 predeclared CH23 boxes, and eventually the three ambiguous zero-event cases; freeze proof tolerances and node/time budgets *before* evaluation.
- Report independently verified coefficient-domain coverage and epsilon-objective gaps; explicitly distinguish `VERIFIED_BOUNDED_GAP`, `UNRESOLVED`, and **unrestricted-global unproven**. A bounded-box certificate is not evidence of a unique maximum over all real coefficients.
- Keep historical CH23 results and CH24's original proof examples unchanged; record follow-up results in a **new milestone**. Do not edit production C14, G25, Lu, or Windows.
