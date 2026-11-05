# CH-C14-25 — Original CH23 datasets through the verified MPFR interval solver

**2026-11-02 | Engineering benchmark complete (15/15), global bounded gaps unresolved (0/15), production scientific release NO-GO.**

## Provenance and frozen protocol

- Original CH23 frozen protocol SHA-256: `31cd3f5d01e40e496e59d48b4160a9a3a4894645509eca9eae4cdcaf3e618bde`.
- Original CH23 `results.jsonl` SHA-256: `69a51df650ef183b8fca4c11f30df6dbad6f6628dd0479c648a25609d0d14341`.
- Stage A original planned protocol SHA-256: `dba2ddfbf740b358e82677667b93d68c9264113d44146625b00880f8843cd5f6`. Initial full-curvature 80-row run exceeded its execution cap without completing. It produced **no certificate**, and was not counted as a successful case.
- Stage B frozen **before the succeeding 15-case evaluation**: `6564886e0b5b84c02878e22ffe59ab009071ec2589f4f87686eff83820e414e0`. Its recorded adaptation retains the CH24 solver and verifier source hashes, 160-bit directed MPFR arithmetic and 0.05 absolute objective-gap tolerance, but uses root-only full interval-curvature evaluation followed by fast directed-MPFR likelihood/determinant enclosure at every branch-and-bound node.
- Original binary64 predictor values are exported to **exact decimal strings** via `Decimal.from_float`; generating each dataset with the pinned CH23 code and seed reproduces the original `sha256(X.tobytes()+y.tobytes())` exactly. No replacement data, altered seeds, rounded-short input conversion, or new SCM families.
- Root coefficient box: intercept `[-10,1]`; slopes `[-5,5]` and `[-5,5]`; at most 31 full-tree nodes per case (15 splits/16 terminal leaves). All three ambiguous CH23 local maxima pairs were used only as **feasible search seeds** when inside the root box; not as certified global solutions.
- Higher-precision verifier at 224-bit MPFR independently checks exact proof-tree covering, witness feasibility and every leaf upper bound against the original signed and hashed input. The verifier still reuses the same bound implementation, so this is **proof replay, not a second formally verified implementation**.

## Full results (finite-box gaps)

| Original CH23 dataset | n | index | events | CH23 250-node float gap | CH25 31-node MPFR gap upper | Replay |
|---|---:|---:|---:|---:|---:|---|
| zero_balanced | 80 | 0 | 0 | 2.0802 | 4.8425 | unresolved / replay PASS |
| zero_balanced | 160 | 0 | 0 | 2.6059 | 5.6177 | unresolved / replay PASS |
| zero_imbalanced | 80 | 0 | 0 | 1.9780 | 5.3209 | unresolved / replay PASS |
| zero_imbalanced | 160 | 0 | 0 | 2.3148 | 5.9379 | unresolved / replay PASS |
| one_event | 80 | 0 | 1 | 2.6166 | 8.4297 | unresolved / replay PASS |
| one_event | 160 | 0 | 1 | 2.5573 | 8.2890 | unresolved / replay PASS |
| rare_1pct | 80 | 0 | 1 | 2.7605 | 10.3717 | unresolved / replay PASS |
| rare_1pct | 160 | 0 | 1 | 3.2708 | 12.7388 | unresolved / replay PASS |
| rare_5pct | 80 | 0 | 2 | 3.6322 | 17.1995 | unresolved / replay PASS |
| rare_5pct | 160 | 0 | 7 | 6.8125 | 46.4973 | unresolved / replay PASS |
| quasi_separated | 80 | 0 | 6 | 17.0280 | 59.6543 | unresolved / replay PASS |
| quasi_separated | 160 | 0 | 16 | 43.3250 | 164.2419 | unresolved / replay PASS |
| zero_imbalanced **(ambiguous)** | 160 | 5 | 0 | — | 5.5373 | unresolved / replay PASS |
| zero_imbalanced **(ambiguous)** | 160 | 7 | 0 | — | 5.8356 | unresolved / replay PASS |
| rare_1pct **(ambiguous)** | 160 | 13 | 0 | — | 5.6233 | unresolved / replay PASS |

All 15 MPFR branch-and-bound computations finished and their 15 exact covering trees were replayed. **No** case met the frozen 0.05 gap threshold. The maximum of terminal upper bounds remains an outer bound; candidate feasible values are lower bounds; the difference is an **upper bound on possible suboptimality**, not a demonstrated difference from the true optimum.

Original CH23 floating gaps and these directed-rounding gaps are **not an apples-to-apples performance comparison**: CH23 used 250 node expansions and undirected float64 bounds; CH25 used 15 splits / 31 total nodes and conservative directed MPFR. In particular, larger CH25 gaps do **not** imply worsening statistical inference.

## Root-curvature and ambiguous-candidate diagnosis

- 15/15 full interval-curvature **root evaluations executed**, but none improved the broad root objective upper bound beyond the conservative reference-minor/Hadamard method. Exhaustive interval-Hessian curvature at *every* node is presently too expensive at n=80–160; the initial uncompleted full-curvature attempt is disclosed, not silently discarded.
- In each of the three original ambiguous zero-event datasets, the two CH23 observed locally validated candidates were within the root box. Directed MPFR **point objective** enclosures at 224 bits strictly confirm their CH23 objective order, but this does not establish that there are only two local maxima or that the higher one is globally optimal.

| Ambiguous CH23 case | Higher local candidate J | Lower local candidate J | Rounding interval ordering |
|---|---:|---:|---|
| `zero_imbalanced_n160_i05` | -1.2223659867 | -3.2653665195 | strict |
| `zero_imbalanced_n160_i07` | -1.5693078128 | -1.5780317611 | strict |
| `rare_1pct_n160_i13` | -0.6662007490 | -0.7477945720 | strict |

## Next engineering and science gates

1. Replace broad interval determinant cancellation with a stronger analytic Fisher-information enclosure (e.g., SPD-preserving interval Cholesky / expanded Cauchy–Binet lower and upper enclosures, or weighted QR), and tighten per-observation likelihood bounds. Use exact-digest-frozen inputs throughout.
2. Derive computationally cheaper **analytic score/Hessian bounds** (rather than second-order forward jets on all 80–160 observations), and test curvature on selective sub-boxes only where information matrices are demonstrably nonsingular over the interval.
3. Repeat the **same 15 original cases** with larger node budgets and explicit CPU-time accounting; do not silently change the tolerance, rounded objective, or frozen protocol. An all-`R^3` proof additionally needs rigorous exclusion of coefficients outside the compact root box.
4. Preserve CH23 ambiguous-case refusals. A bounded epsilon-gap certificate alone would still not prove unique maximum, calibrated causal interval, design identification, or external R equivalence.

## Reproduction from Cognitum repository

```bash
cd research/ch_c14_25
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -q audit_ch25.py
# Run one case using the identical input, frozen stage-B thresholds and bound implementation:
python root_B.py zero_imbalanced_n160_i05
python solve_B.py zero_imbalanced_n160_i05
python replay_B.py zero_imbalanced_n160_i05
```

Each case includes immutable input digest, source/model hashes, a complete 31-node partition, feasible incumbent, 224-bit replay receipt and refusal status. Local machine details and original CH24 implementation limitations remain as documented in `../ch_c14_24/README.md`.

**Scope: Cognitum C14 research only. No production estimator, G25, Lu, DLC, Windows, statistical-reporting, or causal-certification change.**