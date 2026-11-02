# Cognitum CH-C14-25: Original CH23 verified-MPFR replay

This research-only milestone runs **exactly 12 CH23 index-0 bounding cases and 3 CH23 ambiguous zero-event datasets** through the CH24 branch-and-bound infrastructure. The source CH23 archive has been restored in the Cognitum repository at `research/ch_c14_23/`. No production Cognitum, Lu, G25, or scientific certification changes were made.

## Summary

- 15/15 original CH23 source data digests independently regenerated and verified.
- 15/15 finite 3D coefficient-box branch-and-bound searches executed, using directed MPFR at 160 bits.
- 15/15 completed proof-tree replays verified against original inputs using 224-bit MPFR; all remained `UNRESOLVED_REFUSE_CERTIFICATION` at **0.05 absolute objective gap**, with 31 total nodes / 15 splits / 16 leaves each.
- 15/15 full curvature **root probes** executed without tightening the broad root bound. The full-curvature-per-node Stage A run exceeded its execution budget, yielding no certificate; frozen Stage B uses outward-rounded direct likelihood/determinant bounds for its full search. The original CH24 curvature implementation is retained unchanged for targeted future research.
- The three observed ambiguous local-maxima pairs were compared using 224-bit point objective intervals. Rankings agree with CH23, but **no global uniqueness or whole-parameter-space conclusion follows**.

See [Engineering_Report_CH_C14_25.md](Engineering_Report_CH_C14_25.md) and `study_summary.json`.

## Source provenance

- CH23 `frozen_protocol.json` SHA-256: `31cd3f5d01e40e496e59d48b4160a9a3a4894645509eca9eae4cdcaf3e618bde`.
- CH25 Stage A protocol SHA-256: `dba2ddfbf740b358e82677667b93d68c9264113d44146625b00880f8843cd5f6`.
- CH25 Stage B protocol SHA-256: `6564886e0b5b84c02878e22ffe59ab009071ec2589f4f87686eff83820e414e0`.
- CH24 implementation SHA-256 values and immutable case input hashes are in `frozen_protocol_B.json`.
- Every fixture coordinate is a decimal string exactly representing its CH23 binary64 source, not a rounded-short replacement. All 15 `original_digest` fields equal CH23's original `sha256(X.tobytes()+y.tobytes())`.

## Reproduction

Requires Python, NumPy/SciPy for CH23 generator/regression audit, and `libmpfr.so.6` for the CH24 solver. Run from this directory with CH23 and CH24 sister folders in `research/`:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -q audit_ch25.py
python root_B.py zero_imbalanced_n160_i05
python solve_B.py zero_imbalanced_n160_i05
python replay_B.py zero_imbalanced_n160_i05
```

`root_B.py` evaluates the full interval-curvature root probe. `solve_B.py` performs the bounded branch-and-bound search using conservative directed-MPFR base enclosures at every node. `replay_B.py` checks the exact partition and recomputes terminal bounds at higher precision. The replay uses the same core bound formulas as the solver, not an independently formally verified implementation. A saved status is **not** a mathematical proof if the replay fails.

The per-case artifacts are in `inputs/`, `certificates/`, `verifications/`, and `logs/`. `verifications/ambiguous_local_candidate_MPFR_224bit.json` records independently rounded point-objective ordering. `SHA256SUMS.json` authenticates the exact saved artifacts. The originally selected finite box is `[-10,1]×[-5,5]×[-5,5]`. Scientific production release remains **NO-GO**.
